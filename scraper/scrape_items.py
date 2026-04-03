"""
Smite 2 item scraper — wiki.smite2.com
Uses Playwright (real Chromium browser) to bypass Cloudflare protection.

Usage:
    cd scraper
    python scrape_items.py

Outputs: ../db/smite2.db
"""

import json
import os
import re
import sqlite3
import sys
import time

from playwright.sync_api import sync_playwright

from parser import get_unknown_shortcodes, parse_item

BASE_URL    = "https://wiki.smite2.com"
LIST_PATH   = os.path.join(os.path.dirname(__file__), "..", "db", "items_list.json")
DB_PATH     = os.path.join(os.path.dirname(__file__), "..", "db", "smite2.db")
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "..", "db", "schema.sql")
DELAY       = 1.5  # seconds between page fetches

# ---------------------------------------------------------------------------
# DB helpers (unchanged from before)
# ---------------------------------------------------------------------------

def init_db(conn: sqlite3.Connection) -> None:
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()


def insert_item(conn: sqlite3.Connection, item: dict) -> int:
    cur = conn.execute(
        """INSERT OR REPLACE INTO items (name, tier, category, cost, total_cost, icon_url, wiki_slug)
           VALUES (:name, :tier, :category, :cost, :total_cost, :icon_url, :wiki_slug)""",
        {
            "name":       item["name"],
            "tier":       item.get("tier"),
            "category":   item.get("category"),
            "cost":       item.get("cost"),
            "total_cost": item.get("total_cost"),
            "icon_url":   item.get("icon_url"),
            "wiki_slug":  item["wiki_slug"],
        },
    )
    conn.commit()
    return cur.lastrowid


def insert_stats(conn: sqlite3.Connection, item_id: int, stats: dict) -> None:
    if not stats:
        return
    cols = ", ".join(stats.keys())
    placeholders = ", ".join(f":{k}" for k in stats)
    conn.execute(
        f"INSERT OR REPLACE INTO item_stats (item_id, {cols}) VALUES ({item_id}, {placeholders})",
        stats,
    )
    conn.commit()


def insert_passive(conn: sqlite3.Connection, item_id: int, passive: str | None, active: str | None) -> None:
    if not passive and not active:
        return
    cooldown = None
    if passive:
        m = re.search(r'(\d+(?:\.\d+)?)\s*s(?:econd)?\s*[Cc]ooldown', passive)
        if m:
            cooldown = float(m.group(1))
    conn.execute(
        "INSERT INTO item_passives (item_id, passive_text, active_text, cooldown) VALUES (?, ?, ?, ?)",
        (item_id, passive, active, cooldown),
    )
    conn.commit()


def insert_components(conn: sqlite3.Connection, item_id: int, components: list[str]) -> None:
    for name in components:
        conn.execute(
            "INSERT INTO item_components (parent_item_id, component_item_name) VALUES (?, ?)",
            (item_id, name),
        )
    conn.commit()


# ---------------------------------------------------------------------------
# Item list loader
# ---------------------------------------------------------------------------

def load_item_slugs() -> list[tuple[str, str]]:
    """
    Returns list of (slug, category) tuples from the pre-built items_list.json.
    Category is the section name e.g. 'Tier_III_Offensive', 'Relics', etc.
    """
    with open(LIST_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    result: list[tuple[str, str]] = []
    for category, slugs in data.items():
        for slug in slugs:
            result.append((slug, category))
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    items = load_item_slugs()
    print(f"Loaded {len(items)} items from items_list.json")

    saved = 0
    skipped = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()

        for i, (slug, list_category) in enumerate(items, 1):
            url = f"{BASE_URL}/index.php?title={slug}&action=raw"
            print(f"[{i}/{len(items)}] {slug}")

            try:
                response = page.goto(url, wait_until="domcontentloaded", timeout=20_000)
                if response is None or response.status != 200:
                    print(f"  [WARN] HTTP {response.status if response else '?'}")
                    skipped += 1
                    time.sleep(DELAY)
                    continue

                # Raw wikitext comes back as plain text inside <pre> or as body text
                wikitext = page.inner_text("body")

            except Exception as e:
                print(f"  [ERROR] {e}")
                skipped += 1
                time.sleep(DELAY)
                continue

            item = parse_item(wikitext, slug)
            if item is None:
                print(f"  Skipped (not an item page)")
                skipped += 1
                time.sleep(DELAY)
                continue

            # Use the category from our list if the infobox didn't provide one
            if not item.get("category"):
                item["category"] = list_category

            item_id = insert_item(conn, item)
            insert_stats(conn, item_id, item["stats"])
            insert_passive(conn, item_id, item.get("passive"), item.get("active"))
            insert_components(conn, item_id, item.get("components", []))
            saved += 1
            time.sleep(DELAY)

        browser.close()

    conn.close()
    print(f"\nDone. {saved} items saved, {skipped} skipped.")

    unknown = get_unknown_shortcodes()
    if unknown:
        print(f"\n[WARN] Unknown stat shortcodes (add to stat_map.py):")
        for s in sorted(unknown):
            print(f"  {s}")


if __name__ == "__main__":
    main()
