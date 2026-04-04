"""
parse_passive_stats.py
Reads item passive texts from the DB, uses Claude to extract numeric stat bonuses
that apply TO THE PLAYER, and inserts them into item_passive_stats.

Run once:  python scraper/parse_passive_stats.py
Re-run:    python scraper/parse_passive_stats.py --clear   (wipes and re-inserts)
"""

import argparse
import json
import os
import sqlite3
import time

import anthropic

ROOT    = os.path.join(os.path.dirname(__file__), "..")
DB_PATH = os.path.join(ROOT, "db", "smite2.db")

VALID_STAT_KEYS = {
    "health", "physical_protection", "magical_protection",
    "plating", "dampening", "damage_mitigation",
    "health_regen", "mana", "mana_regen",
    "strength", "intelligence", "movement_speed",
    "cooldown_reduction", "tenacity", "basic_attack_power",
    "attack_speed", "lifesteal", "critical_chance",
    "physical_penetration", "magical_penetration",
}

SYSTEM_PROMPT = f"""You are a Smite 2 game data analyst.
Given an item passive description, extract numeric stat bonuses that the item grants TO THE PLAYER when the passive triggers.

Rules:
- Only extract stats the PLAYER receives (ignore debuffs applied to enemies).
- Only use these exact stat_key values: {sorted(VALID_STAT_KEYS)}
- value must be the numeric amount (e.g. 10, 20, 15.5). For percentages like "+10% Cooldown Reduction", use the number 10.
- condition is a short human-readable clause (max ~40 chars) describing when the bonus applies, e.g. "when CC'd", "below 50% HP", "on ability hit", "always". Use "always" only if the bonus is unconditional.
- If a passive grants a range or scales (e.g. "up to +60 Intelligence"), use the maximum value.
- Skip multiplicative bonuses like "+7.5% of all stats from items" — these can't be represented as flat values.
- Skip bonuses that require kills, stacks, or complex chains where the per-trigger value is unclear.
- Return a JSON array. Each element: {{"stat_key": "...", "value": <number>, "condition": "..."}}.
- If no extractable player stat bonus exists, return [].
- Return ONLY valid JSON — no prose, no markdown fences."""


def parse_passive(client: anthropic.Anthropic, item_name: str, passive_text: str) -> list[dict]:
    prompt = f"Item: {item_name}\nPassive: {passive_text}"
    try:
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()
        # Strip accidental markdown fences
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw)
        if not isinstance(data, list):
            return []
        result = []
        for entry in data:
            key = entry.get("stat_key", "")
            val = entry.get("value")
            cond = entry.get("condition", "")
            if key in VALID_STAT_KEYS and isinstance(val, (int, float)) and val != 0:
                result.append({"stat_key": key, "value": float(val), "condition": str(cond)[:60]})
        return result
    except Exception as e:
        print(f"  ERROR parsing '{item_name}': {e}")
        return []


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--clear", action="store_true", help="Clear existing passive stats before re-inserting")
    args = parser.parse_args()

    client = anthropic.Anthropic()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    if args.clear:
        conn.execute("DELETE FROM item_passive_stats")
        conn.commit()
        print("Cleared existing passive stats.")

    # Find items with passive text not yet processed
    rows = conn.execute("""
        SELECT i.id, i.name, p.passive_text
        FROM items i
        JOIN item_passives p ON p.item_id = i.id
        WHERE p.passive_text IS NOT NULL AND p.passive_text != ''
        ORDER BY i.name
    """).fetchall()

    # Skip items already in item_passive_stats (unless --clear was used)
    already_done = set()
    if not args.clear:
        for r in conn.execute("SELECT DISTINCT item_id FROM item_passive_stats"):
            already_done.add(r["item_id"])

    to_process = [r for r in rows if r["id"] not in already_done]
    print(f"Items to process: {len(to_process)} (skipping {len(already_done)} already done)")

    inserted_total = 0
    for i, row in enumerate(to_process, 1):
        print(f"[{i}/{len(to_process)}] {row['name']} ... ", end="", flush=True)
        stats = parse_passive(client, row["name"], row["passive_text"])
        if stats:
            conn.executemany(
                "INSERT INTO item_passive_stats (item_id, stat_key, value, condition) VALUES (?, ?, ?, ?)",
                [(row["id"], s["stat_key"], s["value"], s["condition"]) for s in stats]
            )
            conn.commit()
            inserted_total += len(stats)
            labels = [f'+{s["value"]} {s["stat_key"]} ({s["condition"]})' for s in stats]
            print(f'{", ".join(labels)}')
        else:
            print("(no extractable stats)")
        # Small delay to avoid rate limiting
        time.sleep(0.1)

    conn.close()
    print(f"\nDone. Inserted {inserted_total} passive stat rows for {len(to_process)} items.")


if __name__ == "__main__":
    main()
