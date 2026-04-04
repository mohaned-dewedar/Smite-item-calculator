"""
Smite 2 Build Calculator — Flask backend
Serves the calculator UI and exposes item data from smite2.db.

Usage:
    cd web
    python app.py
Then open http://localhost:5000
"""

import os
import sqlite3
import urllib.request
from collections import defaultdict
from flask import Flask, jsonify, render_template, request, Response

ICONS_DIR      = os.path.join(os.path.dirname(__file__), "static", "icons")
GOD_ICONS_DIR  = os.path.join(os.path.dirname(__file__), "static", "icons", "gods")

app = Flask(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "db", "smite2.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/items")
def items():
    conn = get_db()
    rows = conn.execute("""
        SELECT
            i.id, i.name, i.tier, i.category, i.cost, i.total_cost, i.icon_url,
            s.strength, s.intelligence, s.health, s.health_regen,
            s.mana, s.mana_regen, s.physical_protection, s.magical_protection,
            s.attack_speed, s.physical_penetration, s.magical_penetration,
            s.lifesteal, s.movement_speed, s.cooldown_reduction,
            s.damage_mitigation, s.plating, s.dampening,
            s.basic_attack_power, s.critical_chance, s.echo,
            s.pathfinding, s.penetration, s.tenacity,
            p.passive_text, p.active_text
        FROM items i
        LEFT JOIN item_stats s ON i.id = s.item_id
        LEFT JOIN item_passives p ON i.id = p.item_id
        ORDER BY i.tier DESC NULLS LAST, i.name
    """).fetchall()

    passive_stats_rows = conn.execute(
        "SELECT item_id, stat_key, value, condition, is_adaptive, value_type FROM item_passive_stats"
    ).fetchall()
    conn.close()

    passive_stats_map = defaultdict(list)
    for r in passive_stats_rows:
        passive_stats_map[r["item_id"]].append({
            "stat_key":    r["stat_key"],
            "value":       r["value"],
            "condition":   r["condition"],
            "is_adaptive": r["is_adaptive"],
            "value_type":  r["value_type"],
        })

    stat_cols = [
        "strength", "intelligence", "health", "health_regen",
        "mana", "mana_regen", "physical_protection", "magical_protection",
        "attack_speed", "physical_penetration", "magical_penetration",
        "lifesteal", "movement_speed", "cooldown_reduction",
        "damage_mitigation", "plating", "dampening",
        "basic_attack_power", "critical_chance", "echo",
        "pathfinding", "penetration", "tenacity",
    ]

    result = []
    for row in rows:
        stats = {col: row[col] for col in stat_cols if row[col] is not None}
        item_id = row["id"]
        local_icon = f"/static/icons/{item_id}.png"
        if not os.path.exists(os.path.join(ICONS_DIR, f"{item_id}.png")):
            wiki_url = row["icon_url"]
            local_icon = f"/api/icon?url={wiki_url}" if wiki_url else None

        result.append({
            "id":            item_id,
            "name":          row["name"],
            "tier":          row["tier"],
            "category":      row["category"],
            "cost":          row["cost"],
            "total_cost":    row["total_cost"],
            "icon_url":      local_icon,
            "stats":         stats,
            "passive":       row["passive_text"],
            "active":        row["active_text"],
            "passive_stats": passive_stats_map.get(item_id, []),
        })

    return jsonify(result)


@app.route("/api/gods")
def gods():
    conn = get_db()
    rows = conn.execute("""
        SELECT g.id, g.name, g.pantheon, g.role, g.icon_url,
               s.hp_base, s.hp_per_lvl,
               s.mp_base, s.mp_per_lvl,
               s.hp_regen_base, s.hp_regen_per_lvl,
               s.mp_regen_base, s.mp_regen_per_lvl,
               s.phys_prot_base, s.phys_prot_per_lvl,
               s.mag_prot_base, s.mag_prot_per_lvl,
               s.attack_speed_base, s.attack_speed_per_lvl,
               s.move_speed_base, s.move_speed_per_lvl
        FROM gods g
        LEFT JOIN god_stats s ON g.id = s.god_id
        ORDER BY g.name
    """).fetchall()
    conn.close()

    stat_cols = [
        "hp_base", "hp_per_lvl", "mp_base", "mp_per_lvl",
        "hp_regen_base", "hp_regen_per_lvl", "mp_regen_base", "mp_regen_per_lvl",
        "phys_prot_base", "phys_prot_per_lvl", "mag_prot_base", "mag_prot_per_lvl",
        "attack_speed_base", "attack_speed_per_lvl", "move_speed_base", "move_speed_per_lvl",
    ]

    result = []
    for row in rows:
        stats = {col: row[col] for col in stat_cols if row[col] is not None}
        god_id = row["id"]
        if os.path.exists(os.path.join(GOD_ICONS_DIR, f"{god_id}.png")):
            god_icon = f"/static/icons/gods/{god_id}.png"
        elif row["icon_url"]:
            god_icon = f"/api/icon?url={row['icon_url']}"
        else:
            god_icon = None

        result.append({
            "id":       god_id,
            "name":     row["name"],
            "pantheon": row["pantheon"],
            "role":     row["role"],
            "icon_url": god_icon,
            "stats":    stats,
        })

    return jsonify(result)


@app.route("/api/icon")
def icon_proxy():
    """Proxy wiki item icons to avoid hotlink blocking."""
    url = request.args.get("url", "")
    if not url.startswith("https://wiki.smite2.com/images/"):
        return Response("Forbidden", status=403)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = resp.read()
            content_type = resp.headers.get("Content-Type", "image/png")
    except Exception:
        return Response(status=404)
    return Response(data, content_type=content_type,
                    headers={"Cache-Control": "public, max-age=86400"})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
