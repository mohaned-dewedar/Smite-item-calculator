"""
parse_passive_stats_regex.py
Regex-based fallback for extracting numeric stat bonuses from item passives.
Covers the majority of simple patterns without needing an API key.

Run:  python scraper/parse_passive_stats_regex.py
Re-run with --clear to wipe and re-insert.
"""

import argparse
import os
import re
import sqlite3

ROOT    = os.path.join(os.path.dirname(__file__), "..")
DB_PATH = os.path.join(ROOT, "db", "smite2.db")

# Maps text phrases → stat_key (order matters — longer matches first)
STAT_ALIASES = [
    (r"physical\s+protection",  "physical_protection"),
    (r"magical\s+protection",   "magical_protection"),
    (r"phys(?:ical)?\s+prot",   "physical_protection"),
    (r"mag(?:ical)?\s+prot",    "magical_protection"),
    (r"damage\s+mitigation",    "damage_mitigation"),
    (r"health\s+regen(?:eration)?", "health_regen"),
    (r"mana\s+regen(?:eration)?",   "mana_regen"),
    (r"basic\s+attack\s+power", "basic_attack_power"),
    (r"attack\s+speed",         "attack_speed"),
    (r"movement\s+speed",       "movement_speed"),
    (r"cooldown\s+reduction",   "cooldown_reduction"),
    (r"critical\s+chance",      "critical_chance"),
    (r"physical\s+penetration", "physical_penetration"),
    (r"magical\s+penetration",  "magical_penetration"),
    (r"dampening",              "dampening"),
    (r"plating",                "plating"),
    (r"lifesteal",              "lifesteal"),
    (r"tenacity",               "tenacity"),
    (r"intelligence",           "intelligence"),
    (r"strength",               "strength"),
    (r"health",                 "health"),
    (r"mana",                   "mana"),
]

# Condition keywords to extract from surrounding text
CONDITION_PATTERNS = [
    (r"while\s+below\s+\d+%\s+health",    lambda m: m.group(0).strip()),
    (r"when\s+cc'?d",                      lambda m: "when CC'd"),
    (r"when\s+crowd\s+controlled",         lambda m: "when CC'd"),
    (r"on\s+ability\s+hit",                lambda m: "on ability hit"),
    (r"on\s+basic\s+attack\s+hit",         lambda m: "on basic attack hit"),
    (r"on\s+hit",                          lambda m: "on hit"),
    (r"on\s+kill(?:\s+or\s+assist)?",      lambda m: "on kill/assist"),
    (r"on\s+use",                          lambda m: "on active use"),
    (r"after\s+using",                     lambda m: "after using active"),
    (r"when\s+you\s+hit\s+a\s+god",        lambda m: "when hitting a god"),
    (r"when\s+damaged",                    lambda m: "when damaged"),
    (r"when\s+healed",                     lambda m: "when healed"),
    (r"upon\s+taking\s+damage",            lambda m: "on taking damage"),
    (r"while\s+in\s+\w+\s+(?:stance|form)", lambda m: m.group(0).strip()),
    (r"for\s+\d+s\b",                      lambda m: m.group(0).strip()),  # "for 5s" → transient
]

# Patterns that indicate the bonus is NOT a player stat (skip these)
ENEMY_DEBUFF_PATTERNS = [
    r"debuff(?:s)?\s+that\s+god",
    r"target\s+gains",
    r"apply\s+to\s+(?:enemy|target)",
    r"reduce(?:s)?\s+(?:enemy|their|target)",
    r"-\d+(?:\.\d+)?%\s+(?:physical|magical)\s+protection",  # enemy protection reduction
]


def is_enemy_debuff(sentence: str) -> bool:
    sl = sentence.lower()
    return any(re.search(p, sl) for p in ENEMY_DEBUFF_PATTERNS)


def detect_condition(sentence: str) -> str:
    sl = sentence.lower()
    for pattern, extractor in CONDITION_PATTERNS:
        m = re.search(pattern, sl)
        if m:
            result = extractor(m)
            # Truncate to 40 chars
            return result[:40]
    return "when triggered"


def extract_stats(passive_text: str) -> list[dict]:
    results = []
    # Split into sentences/clauses on . * newline
    clauses = re.split(r'[.*\n]+', passive_text)

    for clause in clauses:
        if not clause.strip():
            continue
        if is_enemy_debuff(clause):
            continue

        cl = clause.lower()

        for alias_pattern, stat_key in STAT_ALIASES:
            # Look for: +NUMBER STAT or STAT: +NUMBER or +NUMBER ... STAT (within ~30 chars)
            patterns = [
                rf'\+\s*(\d+(?:\.\d+)?)\s*{alias_pattern}',
                rf'{alias_pattern}[^+\d]{{0,30}}\+\s*(\d+(?:\.\d+)?)',
                rf'gain\s+(\d+(?:\.\d+)?)\s*{alias_pattern}',
            ]
            for pat in patterns:
                m = re.search(pat, cl)
                if m:
                    value = float(m.group(1))
                    if value <= 0:
                        continue
                    # Skip large percentage values for flat stats (likely a % bonus, not flat)
                    if stat_key in ("dampening", "plating", "damage_mitigation") and value > 100:
                        continue
                    condition = detect_condition(clause)
                    # Avoid duplicate stat_key from the same clause
                    if not any(r["stat_key"] == stat_key for r in results):
                        results.append({"stat_key": stat_key, "value": value, "condition": condition})
                    break

    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--clear", action="store_true", help="Clear existing rows before inserting")
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    if args.clear:
        conn.execute("DELETE FROM item_passive_stats")
        conn.commit()
        print("Cleared existing passive stats.")

    already_done = set()
    if not args.clear:
        for r in conn.execute("SELECT DISTINCT item_id FROM item_passive_stats"):
            already_done.add(r["item_id"])

    rows = conn.execute("""
        SELECT i.id, i.name, p.passive_text
        FROM items i
        JOIN item_passives p ON p.item_id = i.id
        WHERE p.passive_text IS NOT NULL AND p.passive_text != ''
        ORDER BY i.name
    """).fetchall()

    to_process = [r for r in rows if r["id"] not in already_done]
    print(f"Items to process: {len(to_process)} (skipping {len(already_done)} already done)")

    inserted_total = 0
    items_with_stats = 0
    for row in to_process:
        stats = extract_stats(row["passive_text"])
        if stats:
            conn.executemany(
                "INSERT INTO item_passive_stats (item_id, stat_key, value, condition) VALUES (?, ?, ?, ?)",
                [(row["id"], s["stat_key"], s["value"], s["condition"]) for s in stats]
            )
            conn.commit()
            inserted_total += len(stats)
            items_with_stats += 1
            labels = [f'+{s["value"]} {s["stat_key"]} ({s["condition"]})' for s in stats]
            print(f'  [{row["name"]}]: {", ".join(labels)}')

    conn.close()
    print(f"\nDone. {items_with_stats}/{len(to_process)} items had extractable stats. Inserted {inserted_total} rows.")


if __name__ == "__main__":
    main()
