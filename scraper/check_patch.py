"""
Smite 2 patch checker — smite2.com/news
Checks for new patch notes and triggers a full re-scrape if a new patch is found.

Usage:
    cd scraper
    python check_patch.py

Schedule weekly with Windows Task Scheduler (see schedule_patch_check.bat).
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime

from playwright.sync_api import sync_playwright

NEWS_URL     = "https://www.smite2.com/news"
TRACKER_PATH = os.path.join(os.path.dirname(__file__), "..", "db", "patch_tracker.json")
SCRAPER_DIR  = os.path.dirname(os.path.abspath(__file__))

# Matches: /news/open-beta-32-update-notes or /news/open-beta-32-update-note
PATCH_URL_RE = re.compile(r"/news/open-beta-(\d+)-update-notes?/?", re.IGNORECASE)

# Scrapers to run in order when a new patch is found
SCRAPERS = ["scrape_items.py", "scrape_gods.py"]


def load_tracker() -> dict:
    if os.path.exists(TRACKER_PATH):
        with open(TRACKER_PATH, "r") as f:
            return json.load(f)
    return {"last_patch": 0, "last_checked": None}


def save_tracker(data: dict) -> None:
    with open(TRACKER_PATH, "w") as f:
        json.dump(data, f, indent=2)


def get_latest_patch(page) -> tuple | None:
    """Returns (patch_number, slug) of the highest-numbered patch note, or None."""
    print(f"  Fetching {NEWS_URL} ...")
    page.goto(NEWS_URL, wait_until="networkidle", timeout=30_000)

    best_num  = 0
    best_slug = None

    for link in page.query_selector_all("a[href]"):
        href = link.get_attribute("href") or ""
        m = PATCH_URL_RE.search(href)
        if m:
            num = int(m.group(1))
            if num > best_num:
                best_num = num
                # Normalise to just the slug portion
                best_slug = href.split("/news/")[1].rstrip("/")

    return (best_num, best_slug) if best_num > 0 else None


def run_scrapers() -> bool:
    """Run each scraper in sequence. Returns True if all succeeded."""
    all_ok = True
    for script in SCRAPERS:
        path = os.path.join(SCRAPER_DIR, script)
        if not os.path.exists(path):
            print(f"  [SKIP] {script} not found")
            continue
        print(f"  [RUN]  {script} ...")
        result = subprocess.run([sys.executable, path], cwd=SCRAPER_DIR)
        if result.returncode != 0:
            print(f"  [WARN] {script} exited with code {result.returncode}")
            all_ok = False
        else:
            print(f"  [OK]   {script} completed")
    return all_ok


def main():
    tracker    = load_tracker()
    last_patch = tracker.get("last_patch", 0)

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Checking for new Smite 2 patches...")
    print(f"  Last known patch: OB{last_patch}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page    = browser.new_page()
        result  = get_latest_patch(page)
        browser.close()

    tracker["last_checked"] = datetime.now().isoformat()

    if result is None:
        print("  [WARN] No patch note links found on the news page.")
        save_tracker(tracker)
        return

    latest_num, latest_slug = result
    print(f"  Latest patch on site: OB{latest_num} ({latest_slug})")

    if latest_num <= last_patch:
        print("  No new patch detected. Nothing to do.")
    else:
        print(f"  New patch detected: OB{latest_num}! Starting scrapers...")
        success = run_scrapers()
        if success:
            tracker["last_patch"]      = latest_num
            tracker["last_patch_slug"] = latest_slug
            tracker["last_updated"]    = datetime.now().isoformat()
            print(f"  DB updated for OB{latest_num}.")
        else:
            print("  [WARN] One or more scrapers failed — last_patch NOT updated.")

    save_tracker(tracker)
    print("Done.")


if __name__ == "__main__":
    main()
