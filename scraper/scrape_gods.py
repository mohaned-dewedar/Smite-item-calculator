"""
Smite 2 god stats scraper — wiki.smite2.com
Uses Playwright (real Chromium browser) to bypass Cloudflare protection.

Usage:
    cd scraper
    python scrape_gods.py

Outputs: ../db/smite2.db  (gods + god_stats tables)
"""

import os
import re
import sqlite3
import time

from playwright.sync_api import sync_playwright

from parser import _field  # reuse the same |key=value extractor

BASE_URL    = "https://wiki.smite2.com"
DB_PATH     = os.path.join(os.path.dirname(__file__), "..", "db", "smite2.db")
DELAY       = 1.5


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def upsert_god(conn, name, wiki_slug, pantheon, role, icon_url):
    conn.execute(
        """INSERT OR REPLACE INTO gods (name, wiki_slug, pantheon, role, icon_url)
           VALUES (?, ?, ?, ?, ?)""",
        (name, wiki_slug, pantheon, role, icon_url),
    )
    conn.commit()
    return conn.execute("SELECT id FROM gods WHERE name=?", (name,)).fetchone()[0]


def upsert_god_stats(conn, god_id, stats):
    conn.execute(
        """INSERT OR REPLACE INTO god_stats (
               god_id,
               hp_base, hp_per_lvl,
               mp_base, mp_per_lvl,
               hp_regen_base, hp_regen_per_lvl,
               mp_regen_base, mp_regen_per_lvl,
               phys_prot_base, phys_prot_per_lvl,
               mag_prot_base, mag_prot_per_lvl,
               attack_speed_base, attack_speed_per_lvl,
               move_speed_base, move_speed_per_lvl
           ) VALUES (
               :god_id,
               :hp_base, :hp_per_lvl,
               :mp_base, :mp_per_lvl,
               :hp_regen_base, :hp_regen_per_lvl,
               :mp_regen_base, :mp_regen_per_lvl,
               :phys_prot_base, :phys_prot_per_lvl,
               :mag_prot_base, :mag_prot_per_lvl,
               :attack_speed_base, :attack_speed_per_lvl,
               :move_speed_base, :move_speed_per_lvl
           )""",
        {"god_id": god_id, **stats},
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _float(val):
    if val is None:
        return None
    try:
        return float(val.strip().replace(',', '.'))
    except (ValueError, AttributeError):
        return None


def _slug(name):
    """Convert god name to wiki slug (spaces → underscores, keep apostrophes as-is)."""
    return name.strip().replace(" ", "_")


def parse_god(wikitext, slug):
    """
    Parse raw wikitext from a god page.
    Returns dict or None if not a god page.
    """
    if "{{god infobox" not in wikitext.lower():
        return None

    name     = _field(wikitext, "name") or slug.replace("_", " ")
    pantheon = _field(wikitext, "pantheon")
    role     = _field(wikitext, "role1")
    image    = _field(wikitext, "image")
    icon_url = f"{BASE_URL}/images/{image.strip().replace(' ', '_')}" if image else None

    stats = {
        "hp_base":              _float(_field(wikitext, "HP")),
        "hp_per_lvl":           _float(_field(wikitext, "HP per lvl")),
        "mp_base":              _float(_field(wikitext, "MP")),
        "mp_per_lvl":           _float(_field(wikitext, "MP per lvl")),
        "hp_regen_base":        _float(_field(wikitext, "HPR")),
        "hp_regen_per_lvl":     _float(_field(wikitext, "HPR per lvl")),
        "mp_regen_base":        _float(_field(wikitext, "MPR")),
        "mp_regen_per_lvl":     _float(_field(wikitext, "MPR per lvl")),
        "phys_prot_base":       _float(_field(wikitext, "PProt")),
        "phys_prot_per_lvl":    _float(_field(wikitext, "PProt per lvl")),
        "mag_prot_base":        _float(_field(wikitext, "MProt")),
        "mag_prot_per_lvl":     _float(_field(wikitext, "MProt per lvl")),
        "attack_speed_base":    _float(_field(wikitext, "AS")),
        "attack_speed_per_lvl": _float(_field(wikitext, "AS per lvl")),
        "move_speed_base":      _float(_field(wikitext, "MS")),
        "move_speed_per_lvl":   _float(_field(wikitext, "MS per lvl")),
    }

    return {"name": name, "wiki_slug": slug, "pantheon": pantheon,
            "role": role, "icon_url": icon_url, "stats": stats}


def extract_god_names(wikitext):
    """
    Extract god names from the Gods list page raw wikitext.
    Template format: {{God link|Name}} or {{God link2|Name}}
    """
    names = re.findall(r'\{\{God link[^|]*\|([^}|]+)\}\}', wikitext)
    # Deduplicate while preserving order
    seen = set()
    result = []
    for n in names:
        n = n.strip()
        if n and n not in seen:
            seen.add(n)
            result.append(n)
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

ONLY_GODS = [
    "Cerberus", "Charon", "Chiron", "Ganesha", "Gilgamesh",
    "Janus", "Kali", "Morgan Le Fay", "Ne Zha", "Osiris", "Susano",
]


def main():
    conn = sqlite3.connect(DB_PATH)

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

        # Prime session with Cloudflare
        page.goto(BASE_URL, wait_until="domcontentloaded", timeout=15_000)

        # Fetch god list
        print("Fetching god list...")
        page.goto(
            f"{BASE_URL}/index.php?title=Gods&action=raw",
            wait_until="domcontentloaded", timeout=15_000,
        )
        all_names = extract_god_names(page.inner_text("body"))
        god_names = [n for n in all_names if n in ONLY_GODS] if ONLY_GODS else all_names
        print(f"Found {len(all_names)} gods total, scraping {len(god_names)}")

        saved = skipped = 0
        for i, name in enumerate(god_names, 1):
            slug = _slug(name)
            url  = f"{BASE_URL}/index.php?title={slug}&action=raw"
            print(f"[{i}/{len(god_names)}] {name} ...", end=" ", flush=True)

            try:
                resp = page.goto(url, wait_until="domcontentloaded", timeout=20_000)
                if resp is None or resp.status != 200:
                    print(f"HTTP {resp.status if resp else '?'} -- skip")
                    skipped += 1
                    time.sleep(DELAY)
                    continue
                wikitext = page.inner_text("body")
            except Exception as e:
                print(f"ERROR: {e}")
                skipped += 1
                time.sleep(DELAY)
                continue

            god = parse_god(wikitext, slug)
            if god is None:
                print("not a god page -- skip")
                skipped += 1
                time.sleep(DELAY)
                continue

            god_id = upsert_god(conn, god["name"], god["wiki_slug"],
                                 god["pantheon"], god["role"], god["icon_url"])
            upsert_god_stats(conn, god_id, god["stats"])
            print(f"OK (HP {god['stats']['hp_base']})")
            saved += 1
            time.sleep(DELAY)

        browser.close()

    conn.close()
    print(f"\nDone -- {saved} gods saved, {skipped} skipped.")


if __name__ == "__main__":
    main()
