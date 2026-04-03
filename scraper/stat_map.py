# Maps wikitext template shortcodes to item_stats column names.
# When the scraper encounters an unknown shortcode it logs it
# so we can add it here.

STAT_MAP: dict[str, str] = {
    "Str":      "strength",
    "Int":      "intelligence",
    "HP":       "health",
    "HPR":      "health_regen",
    "MP":       "mana",
    "MPR":      "mana_regen",
    "PProt":    "physical_protection",
    "MProt":    "magical_protection",
    "AS":       "attack_speed",
    "PPen":     "physical_penetration",
    "MPen":     "magical_penetration",
    "LS":       "lifesteal",
    "MS":       "movement_speed",
    "CDR":      "cooldown_reduction",
    "DmgMit":   "damage_mitigation",
    "Plating":  "plating",
    "Plat":     "plating",
    "Damp":     "dampening",
    # Discovered from first scrape run
    "BAP":      "basic_attack_power",
    "Crit":     "critical_chance",
    "Echo":     "echo",
    "Path":     "pathfinding",
    "Pen":      "penetration",
    "Ten":      "tenacity",
}
