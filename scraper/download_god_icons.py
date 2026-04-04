"""
Download all god card icons using Playwright (bypasses Cloudflare hotlink protection).

Visits each god's wiki page, extracts the real infobox image URL,
downloads the image bytes, and saves to web/static/icons/gods/{god_id}.png

Usage:
    cd scraper
    python download_god_icons.py
"""

import os
import sqlite3

ROOT    = os.path.join(os.path.dirname(__file__), "..")
DB_PATH = os.path.join(ROOT, "db", "smite2.db")
OUT_DIR = os.path.join(ROOT, "web", "static", "icons", "gods")
BASE    = "https://wiki.smite2.com"


def resolve_god_icon(page, wiki_slug, icon_url):
    """Return (resolved_url, image_bytes) for this god."""
    # Try the stored URL first
    if icon_url and icon_url.startswith("http"):
        try:
            resp = page.goto(icon_url, timeout=10000)
            if resp and resp.status == 200 and "image" in (resp.headers.get("content-type", "")):
                return icon_url, resp.body()
        except Exception:
            pass

    # Fall back: scrape the god's wiki page for the infobox card image
    wiki_url = f"{BASE}/w/{wiki_slug}"
    try:
        page.goto(wiki_url, timeout=15000, wait_until="domcontentloaded")
    except Exception:
        return None, None

    selectors = [
        ".god-infobox img",
        ".infobox img",
        ".smite-infobox img",
        "img[src*='T_'][src*='Default']",
        "img[src*='GodCard']",
        ".mw-parser-output .infobox img",
        "table.infobox img",
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

    # Strip thumbnail sizing
    if "/thumb/" in src:
        parts = src.split("/thumb/")
        filename = parts[1].split("/")[0]
        src = f"/images/{filename}"

    src = src.split("?")[0]
    abs_url = src if src.startswith("http") else BASE + src

    try:
        resp = page.goto(abs_url, timeout=10000)
        if resp and resp.status == 200:
            return abs_url, resp.body()
    except Exception:
        pass

    return None, None


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT id, name, wiki_slug, icon_url FROM gods").fetchall()

    to_do = [(id_, name, slug, url) for id_, name, slug, url in rows
             if not os.path.exists(os.path.join(OUT_DIR, f"{id_}.png"))]

    print(f"Gods to download: {len(to_do)} / {len(rows)} total")
    if not to_do:
        print("All god icons already downloaded.")
        return

    from playwright.sync_api import sync_playwright

    ok = fail = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(BASE, timeout=15000, wait_until="domcontentloaded")

        for idx, (god_id, name, wiki_slug, icon_url) in enumerate(to_do, 1):
            dest = os.path.join(OUT_DIR, f"{god_id}.png")
            print(f"[{idx}/{len(to_do)}] {name} ...", end=" ", flush=True)

            try:
                resolved_url, data = resolve_god_icon(page, wiki_slug, icon_url)
            except Exception as e:
                print(f"ERROR: {e}")
                fail += 1
                continue

            if data:
                with open(dest, "wb") as f:
                    f.write(data)
                if resolved_url and resolved_url != icon_url:
                    conn.execute("UPDATE gods SET icon_url=? WHERE id=?", (resolved_url, god_id))
                    conn.commit()
                print(f"OK ({len(data):,} bytes)")
                ok += 1
            else:
                print("FAIL")
                fail += 1

        browser.close()

    conn.close()
    print(f"\nDone -- {ok} downloaded, {fail} failed.")


if __name__ == "__main__":
    main()
