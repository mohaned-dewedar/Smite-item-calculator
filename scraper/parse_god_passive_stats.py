"""
parse_god_passive_stats.py
Extracts numeric stat bonuses from god ability descriptions (all slots).
Writes to god_ability_stats table (linked via ability_id).

Run:  python scraper/parse_god_passive_stats.py [--clear]
"""

import argparse
import os
import re
import sqlite3
import sys

ROOT    = os.path.join(os.path.dirname(__file__), "..")
DB_PATH = os.path.join(ROOT, "db", "smite2.db")

sys.path.insert(0, os.path.dirname(__file__))
from parse_passive_stats_regex import detect_condition

# Stats where a trailing "%" means the value is a multiplier (pct of current stat),
# NOT a flat % (e.g. "Protections: 10%" = 10% of your current prots added on top).
# Contrast with stats that are inherently percentages (attack_speed, damage_mitigation, etc.)
# where "40%" just denotes the unit.
PCT_OF_TOTAL_STATS = {
    "physical_protection", "magical_protection",
    "health", "strength", "intelligence",
}

# Stat aliases for god abilities.
# Order matters — more specific patterns first.
GOD_STAT_ALIASES = [
    (r"physical\s+protection",        ["physical_protection"]),
    (r"magical\s+protection",         ["magical_protection"]),
    (r"phys(?:ical)?\s+prot\b",       ["physical_protection"]),
    (r"mag(?:ical)?\s+prot\b",        ["magical_protection"]),
    (r"damage\s+mitigation",          ["damage_mitigation"]),
    (r"dampening",                    ["dampening"]),
    (r"plating",                      ["plating"]),
    (r"health\s+regen(?:eration)?",   ["health_regen"]),
    (r"protections?\b",               ["physical_protection", "magical_protection"]),
    (r"lifesteal",                    ["lifesteal"]),
    (r"health\b",                     ["health"]),
    (r"strength\s*&\s*intelligence",  ["strength", "intelligence"]),
    (r"strength\b",                   ["strength"]),
    (r"intelligence\b",               ["intelligence"]),
    (r"movement\s+speed",             ["movement_speed"]),
    (r"attack\s+speed",               ["attack_speed"]),
    (r"cooldown\s+reduction",         ["cooldown_reduction"]),
    (r"mana\b",                       ["mana"]),
    (r"tenacity",                     ["tenacity"]),
]

# Matches "VALUE + VALUE Per Level" (e.g. "25 + 10 Per Level")
RE_BASE_PLUS_LVL = re.compile(
    r'(\d+(?:\.\d+)?)\s*\+\s*(\d+(?:\.\d+)?)\s*%?\s*per\s*level', re.IGNORECASE
)
# Matches "VALUE Per Level" with no preceding "+" base (e.g. "1 Per Level")
RE_LVL_ONLY = re.compile(
    r'(\d+(?:\.\d+)?)\s*%?\s*per\s*level', re.IGNORECASE
)
# Matches "VALUE Per Stack"
RE_PER_STACK = re.compile(
    r'(\d+(?:\.\d+)?)\s*%?\s*per\s*stack', re.IGNORECASE
)


def _extract_value(clause: str):
    """
    Try to extract (value, value_per_level, condition, is_pct) from a single stat clause.
    Returns None if no numeric value is found.
    is_pct=True means the number had a trailing '%', which may indicate pct_of_total
    depending on the stat type.
    """
    cl = clause.lower()

    # 1. "BASE + PER_LVL per level"
    m = RE_BASE_PLUS_LVL.search(cl)
    if m:
        return float(m.group(1)), float(m.group(2)), None, False

    # 2. "VALUE per level" (no base)
    m = RE_LVL_ONLY.search(cl)
    if m:
        return 0.0, float(m.group(1)), None, False

    # 3. "VALUE per stack"
    m = RE_PER_STACK.search(cl)
    if m:
        return float(m.group(1)), 0.0, "per stack", False

    # 4. "+VALUE" or "gain VALUE" free-text patterns
    gain_m = re.search(r'(?:\+|gain)\s*(\d+(?:\.\d+)?)\s*(%?)', cl)
    if gain_m:
        is_pct = bool(gain_m.group(2))
        return float(gain_m.group(1)), 0.0, detect_condition(clause), is_pct

    # 5. "STAT: N1 N2 N3 N4 N5" — take the last (max rank) value, detect trailing %
    colon_pos = cl.find(':')
    if colon_pos >= 0:
        after = cl[colon_pos + 1:].strip()
        # Skip if any "per X" qualifier (would have been caught by patterns 1-3)
        if not re.search(r'\bper\s', after):
            all_nums = re.findall(r'(\d+(?:\.\d+)?)\s*(%?)', after)
            if all_nums:
                val_str, pct = all_nums[-1]
                val = float(val_str)
                is_pct = bool(pct)
                return val, 0.0, None, is_pct

    return None


def extract_god_ability_stats(description: str, is_passive: bool = True) -> list[dict]:
    """
    Parse an ability description and extract stat bonuses.
    Returns list of dicts: stat_key, value, value_per_level, condition, value_type.

    is_passive: True for Passive slot (detect_condition used), False for active abilities.
    """
    if not description:
        return []

    results: dict[str, dict] = {}  # stat_key → result dict

    # Split on bullet markers and newlines
    clauses = re.split(r'[*\n]+', description)

    for clause in clauses:
        clause = clause.strip()
        if not clause:
            continue

        cl = clause.lower()

        # Skip damage/heal/attack scaling clauses (stat is used as a multiplier, not a self-buff)
        if re.search(r'\b(damage|heal|attack|ability|bonus\s+damage)\s+scaling\b', cl):
            continue

        # Skip damage scaling or lore references containing "from items"
        if re.search(r'from items', cl):
            continue

        # Detect if this is a "Scaling" line (e.g. "Protections Scaling: 0.4 Per Level")
        is_scaling = bool(re.search(r'\bscaling\b', cl))

        for alias_pattern, stat_keys in GOD_STAT_ALIASES:
            alias_match = re.search(alias_pattern, cl)
            if not alias_match:
                continue

            # Skip when stat is used as a damage scaling reference: "X% Strength"
            if re.search(r'\d+(?:\.\d+)?\s*%\s*' + alias_pattern, cl):
                continue

            # Skip enemy debuff variants: "Protections Reduced:", "Physical Prot Reduced:"
            after_stat = cl[alias_match.end():alias_match.end() + 20].strip()
            if re.match(r's?\s*reduc', after_stat):
                continue

            # Skip "stolen" debuff variants (stealing from enemies is handled separately;
            # here we just skip to avoid double-counting or ambiguity)
            # Actually "Protections Stolen" CAN mean the god GAINS them, keep it.

            extracted = _extract_value(clause)
            if extracted is None:
                continue

            val, val_per_lvl, cond, is_pct = extracted

            if val == 0.0 and val_per_lvl == 0.0:
                continue

            # Skip unreasonably large values for cap-bounded stats
            if any(k in ('dampening', 'plating', 'damage_mitigation') for k in stat_keys):
                if val > 100:
                    continue

            if cond is None and is_passive:
                cond = detect_condition(clause)

            for stat_key in stat_keys:
                # Determine value_type: pct_of_total if "%" detected AND stat is a
                # naturally-flat stat (not already expressed as a percentage)
                vtype = "pct_of_total" if (is_pct and stat_key in PCT_OF_TOTAL_STATS) else "flat"

                if is_scaling and stat_key in results:
                    # Update the per-level on the existing entry
                    results[stat_key]["value_per_level"] = val_per_lvl or val
                elif stat_key not in results:
                    results[stat_key] = {
                        "stat_key":        stat_key,
                        "value":           val,
                        "value_per_level": val_per_lvl,
                        "condition":       cond,
                        "value_type":      vtype,
                    }
            break  # matched this clause, move on

    return list(results.values())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--clear", action="store_true",
                        help="Clear existing rows before inserting")
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    if args.clear:
        conn.execute("DELETE FROM god_ability_stats")
        conn.commit()
        print("Cleared existing god ability stats.")

    rows = conn.execute("""
        SELECT a.id AS ability_id, a.slot, g.name AS god_name, a.description
        FROM god_abilities a
        JOIN gods g ON g.id = a.god_id
        WHERE a.description IS NOT NULL
          AND a.description != ''
        ORDER BY g.name, a.slot
    """).fetchall()

    print(f"Processing {len(rows)} abilities across all slots...")

    inserted_total = 0
    abilities_with_stats = 0

    for row in rows:
        is_passive = (row["slot"] == "Passive")
        stats = extract_god_ability_stats(row["description"], is_passive=is_passive)
        if not stats:
            continue

        conn.executemany(
            """INSERT INTO god_ability_stats
               (ability_id, stat_key, value, value_per_level, condition, value_type)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [(row["ability_id"], s["stat_key"], s["value"],
              s["value_per_level"], s["condition"], s.get("value_type", "flat"))
             for s in stats],
        )
        conn.commit()
        inserted_total += len(stats)
        abilities_with_stats += 1

        labels = []
        for s in stats:
            lvl = f"+{s['value_per_level']}/lvl" if s["value_per_level"] else ""
            pct = "%" if s.get("value_type") == "pct_of_total" else ""
            labels.append(
                f'+{s["value"]}{pct}{lvl} {s["stat_key"]} ({s["condition"]}) [{s.get("value_type","flat")}]'
            )
        print(f'  [{row["god_name"]} / {row["slot"]}]: {", ".join(labels)}')

    conn.close()
    print(
        f"\nDone. {abilities_with_stats}/{len(rows)} abilities had extractable stats. "
        f"Inserted {inserted_total} rows."
    )


if __name__ == "__main__":
    main()
