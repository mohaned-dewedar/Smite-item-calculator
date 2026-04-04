"""
Download all item icons using Playwright (bypasses Cloudflare hotlink protection).

Strategy per item:
  1. Try the existing icon_url from the DB directly (many are correct).
  2. If 404, visit the item's wiki page and extract the real icon src.
  3. Download the image bytes and save to web/static/icons/{item_id}.png
  4. Update the DB icon_url to point at the corrected wiki URL.

Usage:
    cd scraper
    python download_icons.py

Requires: pip install playwright && playwright install chromium
"""

import os
import sqlite3
import sys

ROOT    = os.path.join(os.path.dirname(__file__), "..")
DB_PATH = os.path.join(ROOT, "db", "smite2.db")
OUT_DIR = os.path.join(ROOT, "web", "static", "icons")
BASE    = "https://wiki.smite2.com"


def resolve_icon_url(page, item_name, wiki_slug, icon_url):
    """Return the correct absolute image URL for this item."""
    # Try the stored URL first
    if icon_url:
        abs_url = icon_url if icon_url.startswith("http") else BASE + icon_url
        resp = page.goto(abs_url, timeout=10000)
        if resp and resp.status == 200 and "image" in (resp.headers.get("content-type", "")):
            return abs_url, resp.body()

    # Fall back: scrape the item's wiki page for the infobox icon
    wiki_url = f"{BASE}/w/{wiki_slug}"
    try:
        page.goto(wiki_url, timeout=15000, wait_until="domcontentloaded")
    except Exception:
        return None, None

    # The item icon is the first <img> inside .item-infobox, or the first large item image
    selectors = [
        ".item-infobox img",
        ".infobox img",
        "img[src*='T1_'], img[src*='T2_'], img[src*='T3_']",
        "img[src*='Relic_'], img[src*='Curio_'], img[src*='Consumable_']",
    ]
    src = None
    for sel in selectors:
        el = page.query_selector(sel)
        if el:
            src = el.get_attribute("src")
            if src:
                break

    if not src:
        return None, None

    # Strip thumbnail sizing (/thumb/X/NNpx-X → /X)
    if "/thumb/" in src:
        # /images/thumb/FILE.png/32px-FILE.png -> /images/FILE.png
        parts = src.split("/thumb/")
        inner = parts[1]  # FILE.png/32px-FILE.png?cache
        filename = inner.split("/")[0]
        src = f"/images/{filename}"

    # Remove cache-busting query string
    src = src.split("?")[0]

    abs_url = src if src.startswith("http") else BASE + src
    resp = page.goto(abs_url, timeout=10000)
    if resp and resp.status == 200:
        return abs_url, resp.body()

    return None, None


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT id, name, wiki_slug, icon_url FROM items").fetchall()

    # Only process items that don't already have a local file
    to_do = [(id_, name, slug, url) for id_, name, slug, url in rows
             if not os.path.exists(os.path.join(OUT_DIR, f"{id_}.png"))]

    print(f"Items to download: {len(to_do)} / {len(rows)} total")
    if not to_do:
        print("All icons already downloaded.")
        return

    from playwright.sync_api import sync_playwright

    ok = fail = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Prime session with a wiki visit so Cloudflare sets cookies
        page.goto(BASE, timeout=15000, wait_until="domcontentloaded")

        for idx, (item_id, name, wiki_slug, icon_url) in enumerate(to_do, 1):
            dest = os.path.join(OUT_DIR, f"{item_id}.png")
            print(f"[{idx}/{len(to_do)}] {name} ...", end=" ", flush=True)

            try:
                resolved_url, data = resolve_icon_url(page, name, wiki_slug, icon_url)
            except Exception as e:
                print(f"ERROR: {e}")
                fail += 1
                continue

            if data:
                with open(dest, "wb") as f:
                    f.write(data)
                # Update DB with the corrected wiki URL
                if resolved_url and resolved_url != icon_url:
                    conn.execute("UPDATE items SET icon_url=? WHERE id=?", (resolved_url, item_id))
                    conn.commit()
                print(f"OK ({len(data):,} bytes)")
                ok += 1
            else:
                print("FAIL (no image found)")
                fail += 1

        browser.close()

    conn.close()
    print(f"\nDone -- {ok} downloaded, {fail} failed.")


if __name__ == "__main__":
    main()
