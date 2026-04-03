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
from flask import Flask, jsonify, render_template

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
    conn.close()

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
        result.append({
            "id":         row["id"],
            "name":       row["name"],
            "tier":       row["tier"],
            "category":   row["category"],
            "cost":       row["cost"],
            "total_cost": row["total_cost"],
            "icon_url":   row["icon_url"],
            "stats":      stats,
            "passive":    row["passive_text"],
            "active":     row["active_text"],
        })

    return jsonify(result)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
