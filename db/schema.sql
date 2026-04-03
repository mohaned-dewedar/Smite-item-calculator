CREATE TABLE IF NOT EXISTS items (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT    NOT NULL UNIQUE,
    tier       INTEGER,          -- 1, 2, 3 or NULL for relics/consumables
    category   TEXT,             -- Offensive, Defensive, Hybrid, Starter, Relic, Curio, Consumable
    cost       INTEGER,          -- upgrade/shop cost
    total_cost INTEGER,          -- full recipe cost
    icon_url   TEXT,
    wiki_slug  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS item_stats (
    item_id              INTEGER PRIMARY KEY REFERENCES items(id) ON DELETE CASCADE,
    strength             REAL,   -- {{Str}}
    intelligence         REAL,   -- {{Int}}
    health               REAL,   -- {{HP}}
    health_regen         REAL,   -- {{HPR}}
    mana                 REAL,   -- {{MP}}
    mana_regen           REAL,   -- {{MPR}}
    physical_protection  REAL,   -- {{PProt}}
    magical_protection   REAL,   -- {{MProt}}
    attack_speed         REAL,   -- {{AS}}
    physical_penetration REAL,   -- {{PPen}}
    magical_penetration  REAL,   -- {{MPen}}
    lifesteal            REAL,   -- {{LS}}
    movement_speed       REAL,   -- {{MS}}
    cooldown_reduction   REAL,   -- {{CDR}}
    damage_mitigation    REAL,   -- {{DmgMit}}
    plating              REAL,   -- {{Plating}} / {{Plat}}
    dampening            REAL,   -- {{Damp}}
    basic_attack_power   REAL,   -- {{BAP}}
    critical_chance      REAL,   -- {{Crit}}
    echo                 REAL,   -- {{Echo}}
    pathfinding          REAL,   -- {{Path}}
    penetration          REAL,   -- {{Pen}}
    tenacity             REAL    -- {{Ten}}
);

CREATE TABLE IF NOT EXISTS item_passives (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id      INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    passive_text TEXT,
    active_text  TEXT,
    cooldown     REAL    -- seconds, if mentioned in passive text
);

CREATE TABLE IF NOT EXISTS item_components (
    parent_item_id      INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    component_item_name TEXT    NOT NULL
);
