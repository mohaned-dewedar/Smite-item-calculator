"""
Parses raw wikitext from wiki.smite2.com item pages into structured dicts.

Expected input: the raw wikitext string from ?action=raw
Expected output: dict with keys matching db columns
"""

import re
from stat_map import STAT_MAP

_UNKNOWN_SHORTCODES: set[str] = set()


def parse_item(wikitext: str, slug: str) -> dict | None:
    """
    Parse a single item's raw wikitext.
    Returns a dict or None if the page isn't an item page.
    """
    # Must contain an Item infobox
    if "{{Item infobox" not in wikitext and "{{item infobox" not in wikitext:
        return None

    item: dict = {"wiki_slug": slug, "stats": {}, "passive": None, "active": None, "components": []}

    # --- Basic fields ---
    item["name"]       = _field(wikitext, "name")  or slug.replace("_", " ")
    item["tier"]       = _int(_field(wikitext, "tier"))
    item["category"]   = _field(wikitext, "type")
    item["cost"]       = _int(_field(wikitext, "cost"))
    item["total_cost"] = _int(_field(wikitext, "totalcost"))
    item["icon_url"]   = _build_icon_url(_field(wikitext, "image"))

    # --- Stats: |stat1={{PProt|35}} |stat2={{MP|200}} ... ---
    for shortcode, raw_val in re.findall(r'\|stat\d+\s*=\s*\{\{(\w+)\|([^}]+)\}\}', wikitext):
        col = STAT_MAP.get(shortcode)
        if col:
            try:
                item["stats"][col] = float(raw_val.strip())
            except ValueError:
                pass
        else:
            _UNKNOWN_SHORTCODES.add(shortcode)

    # --- Passive ---
    passive_raw = _field(wikitext, "passive")
    if passive_raw:
        item["passive"] = _strip_wiki_markup(passive_raw)

    # --- Active (some items have one) ---
    active_raw = _field(wikitext, "active")
    if active_raw:
        item["active"] = _strip_wiki_markup(active_raw)

    # --- Build path: parse the {{Recipe}} template section ---
    # Recipe template uses |item=Name for each node; the top item is this item itself,
    # everything else is a component (T2 sub-items for T3 items, T1 items for T2 items).
    item["components"] = _parse_recipe_components(wikitext, item["name"])

    return item


def get_unknown_shortcodes() -> set[str]:
    return set(_UNKNOWN_SHORTCODES)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _field(wikitext: str, key: str) -> str | None:
    """Extract |key=value from the infobox, handling multi-line values."""
    # Match from |key= up to the next | at the start of a template param or }}
    pattern = rf'\|{re.escape(key)}[^\S\n]*=[^\S\n]*(.*?)(?=\n\s*\||\n\s*\}}|\Z)'
    m = re.search(pattern, wikitext, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return None


def _int(val: str | None) -> int | None:
    if val is None:
        return None
    try:
        return int(val.strip())
    except (ValueError, AttributeError):
        return None


def _build_icon_url(image_name: str | None) -> str | None:
    if not image_name:
        return None
    encoded = image_name.strip().replace(" ", "_")
    return f"https://wiki.smite2.com/images/{encoded}"


def _parse_recipe_components(wikitext: str, item_name: str) -> list[str]:
    """
    Extract all component item names from the ==Recipe== section.
    The Recipe template is nested: {{Recipe |item=X |i1={{Recipe |item=Y ...}} ...}}
    We pull every |item= value and exclude the top-level item itself.
    """
    # Find the Recipe section
    m = re.search(r'==\s*Recipe\s*==\s*(.*?)(?===|\Z)', wikitext, re.DOTALL | re.IGNORECASE)
    if not m:
        return []
    recipe_block = m.group(1)
    # Extract all |item= values
    all_items = re.findall(r'\|item\s*=\s*([^\n|{}\]]+)', recipe_block)
    seen: set[str] = set()
    result: list[str] = []
    for name in all_items:
        name = name.strip()
        if name and name != item_name and name not in seen:
            seen.add(name)
            result.append(name)
    return result


def _strip_wiki_markup(text: str) -> str:
    """Remove common wiki markup to produce plain text."""
    # Remove [[File:...]] and [[Image:...]]
    text = re.sub(r'\[\[(?:File|Image):[^\]]+\]\]', '', text, flags=re.IGNORECASE)
    # [[link|display]] → display,  [[link]] → link
    text = re.sub(r'\[\[(?:[^\]|]+\|)?([^\]]+)\]\]', r'\1', text)
    # {{template|...}} → strip entirely or keep inner content
    text = re.sub(r'\{\{[^}]+\}\}', '', text)
    # HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Wiki bold/italic
    text = re.sub(r"'{2,3}", '', text)
    return re.sub(r'\s+', ' ', text).strip()
