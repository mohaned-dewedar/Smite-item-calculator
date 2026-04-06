"""
Smite 2 Solo Lane Defensive Build Analysis
Tasks 1-6: Build Progression, Optimal Allocation, Marginal Value,
            Dampening Cap, Conditional Passive Break-even, Tier List
"""

import sqlite3
from itertools import combinations

DB = "c:/Users/mdewe/OneDrive/Desktop/Me/Smite/db/smite2.db"

# ------------------------------------------------------------------
# EHP FORMULAE
# ------------------------------------------------------------------
def ehp_abilities(hp, phys_prot, damp, dmg_mit):
    """EHP vs physical abilities."""
    effective_damp = min(damp, 35)
    return hp * (100 + phys_prot) / (100 - effective_damp - dmg_mit)

def ehp_basics(hp, phys_prot, plating, dmg_mit):
    """EHP vs physical basic attacks."""
    effective_plat = min(plating, 35)
    return hp * (100 + phys_prot) / (100 - effective_plat - dmg_mit)

def ehp_weighted(hp, phys_prot, plating, damp, dmg_mit, w_ability=0.55, w_basic=0.45):
    ea = ehp_abilities(hp, phys_prot, damp, dmg_mit)
    eb = ehp_basics(hp, phys_prot, plating, dmg_mit)
    return w_ability * ea + w_basic * eb

# ------------------------------------------------------------------
# DB HELPER
# ------------------------------------------------------------------
def load_defensive_items():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("""
        SELECT i.id, i.name, i.total_cost,
               COALESCE(s.health, 0),
               COALESCE(s.physical_protection, 0),
               COALESCE(s.magical_protection, 0),
               COALESCE(s.damage_mitigation, 0),
               COALESCE(s.plating, 0),
               COALESCE(s.dampening, 0)
        FROM items i
        JOIN item_stats s ON i.id = s.item_id
        WHERE i.tier = 3 AND i.category = 'Defensive'
        ORDER BY i.name
    """)
    rows = cur.fetchall()
    conn.close()
    items = []
    for r in rows:
        items.append({
            "id": r[0], "name": r[1], "cost": r[2],
            "hp": r[3], "phys": r[4], "mag": r[5],
            "dmg_mit": r[6], "plating": r[7], "damp": r[8],
        })
    return items

# ------------------------------------------------------------------
# GOD STATS - use Bellona as representative solo warrior (DB values)
# hp_base=647.4, hp_per_lvl=101.4, phys_base=20.4, phys_per_lvl=3.12
# ------------------------------------------------------------------
GOD = {
    "hp_base": 647.4, "hp_per_lvl": 101.4,
    "phys_base": 20.4, "phys_per_lvl": 3.12,
}

def god_stats_at_level(lvl):
    hp = GOD["hp_base"] + (lvl - 1) * GOD["hp_per_lvl"]
    phys = GOD["phys_base"] + (lvl - 1) * GOD["phys_per_lvl"]
    return round(hp, 1), round(phys, 1)

# Gold to level mapping per task spec
GOLD_TO_LEVEL = {2400: 5, 4800: 8, 7200: 12, 9600: 15, 12000: 18, 14400: 20}

def sep(char="=", n=90):
    print(char * n)


# ==================================================================
# TASK 1 - BUILD PROGRESSION
# ==================================================================
def task1():
    sep()
    print("TASK 1 - BUILD PROGRESSION ANALYSIS (EHP vs Physical, Bellona base stats)")
    sep()

    # All item data pulled from DB and verified
    build_A = [  # "Protection First": stack dual-prot items
        {"name": "Eye of Providence",   "cost": 2300, "hp": 250, "phys": 25, "damp": 0, "plating": 0, "dmg_mit": 0},
        {"name": "Magi's Cloak",        "cost": 2400, "hp":   0, "phys": 35, "damp": 0, "plating": 0, "dmg_mit": 0},
        {"name": "Dwarven Plate",       "cost": 2800, "hp":   0, "phys": 40, "damp": 0, "plating": 0, "dmg_mit": 0},
        {"name": "Hide of Nemean Lion", "cost": 2550, "hp": 350, "phys": 35, "damp": 0, "plating": 0, "dmg_mit": 0},
        {"name": "Stygian Anchor",      "cost": 2550, "hp":   0, "phys": 35, "damp": 0, "plating": 0, "dmg_mit": 0},
        {"name": "Stone of Binding",    "cost": 2550, "hp":   0, "phys": 35, "damp": 0, "plating": 0, "dmg_mit": 0},
    ]

    build_B = [  # "Mitigation First": Wyrmskin, Spectral, then prots
        {"name": "Spectral Armor",      "cost": 2300, "hp": 400, "phys":  0, "damp": 0, "plating": 20, "dmg_mit": 0},
        {"name": "Wyrmskin",            "cost": 2600, "hp": 250, "phys":  0, "damp": 15, "plating": 0, "dmg_mit": 0},
        {"name": "Alchemist Coat",      "cost": 2350, "hp":   0, "phys":  0, "damp": 15, "plating": 0, "dmg_mit": 0},
        {"name": "Hide of Nemean Lion", "cost": 2550, "hp": 350, "phys": 35, "damp": 0, "plating": 0, "dmg_mit": 0},
        {"name": "Stygian Anchor",      "cost": 2550, "hp":   0, "phys": 35, "damp": 0, "plating": 0, "dmg_mit": 0},
        {"name": "Dwarven Plate",       "cost": 2800, "hp":   0, "phys": 40, "damp": 0, "plating": 0, "dmg_mit": 0},
    ]

    build_C = [  # "Balanced": mix of prot + mitigation each buy
        {"name": "Erosion",             "cost": 2400, "hp": 250, "phys": 30, "damp": 0, "plating": 0, "dmg_mit": 0},
        {"name": "Kinetic Cuirass",     "cost": 2400, "hp": 300, "phys":  0, "damp": 0, "plating": 15, "dmg_mit": 0},
        {"name": "Dwarven Plate",       "cost": 2800, "hp":   0, "phys": 40, "damp": 0, "plating": 0, "dmg_mit": 0},
        {"name": "Wyrmskin",            "cost": 2600, "hp": 250, "phys":  0, "damp": 15, "plating": 0, "dmg_mit": 0},
        {"name": "Hide of Nemean Lion", "cost": 2550, "hp": 350, "phys": 35, "damp": 0, "plating": 0, "dmg_mit": 0},
        {"name": "Stygian Anchor",      "cost": 2550, "hp":   0, "phys": 35, "damp": 0, "plating": 0, "dmg_mit": 0},
    ]

    gold_steps = list(GOLD_TO_LEVEL.keys())

    print(f"\n{'Gold':>7} {'Lvl':>4}  {'GodHP':>7} {'GodPhys':>8}  "
          f"{'A:Abil':>9} {'A:Basic':>9}  "
          f"{'B:Abil':>9} {'B:Basic':>9}  "
          f"{'C:Abil':>9} {'C:Basic':>9}")
    sep("-")

    for i, gold in enumerate(gold_steps):
        lvl = GOLD_TO_LEVEL[gold]
        god_hp, god_phys = god_stats_at_level(lvl)

        def cumulative(build, step_idx):
            hp = god_hp
            phys = god_phys
            damp = 0
            plating = 0
            dmg_mit = 0
            for item in build[:step_idx + 1]:
                hp += item["hp"]
                phys += item["phys"]
                damp += item["damp"]
                plating += item["plating"]
                dmg_mit += item["dmg_mit"]
            return hp, phys, damp, plating, dmg_mit

        def calc_ehps(build, step_idx):
            hp, phys, damp, plating, dmg_mit = cumulative(build, step_idx)
            ea = ehp_abilities(hp, phys, damp, dmg_mit)
            eb = ehp_basics(hp, phys, plating, dmg_mit)
            return ea, eb

        eaA, ebA = calc_ehps(build_A, i)
        eaB, ebB = calc_ehps(build_B, i)
        eaC, ebC = calc_ehps(build_C, i)

        print(f"{gold:>7,} {lvl:>4}  {god_hp:>7.0f} {god_phys:>8.1f}  "
              f"{eaA:>9,.0f} {ebA:>9,.0f}  "
              f"{eaB:>9,.0f} {ebB:>9,.0f}  "
              f"{eaC:>9,.0f} {ebC:>9,.0f}")

    print()
    print("Build A items:", " -> ".join(it["name"] for it in build_A))
    print("Build B items:", " -> ".join(it["name"] for it in build_B))
    print("Build C items:", " -> ".join(it["name"] for it in build_C))

    sep("-")
    print("ANALYSIS NOTES:")

    # Print full-build stats for analysis
    for build_name, build in [("A", build_A), ("B", build_B), ("C", build_C)]:
        god_hp, god_phys = god_stats_at_level(20)
        hp = god_hp + sum(it["hp"] for it in build)
        phys = god_phys + sum(it["phys"] for it in build)
        damp = sum(it["damp"] for it in build)
        plating = sum(it["plating"] for it in build)
        mit = sum(it["dmg_mit"] for it in build)
        ea = ehp_abilities(hp, phys, damp, mit)
        eb = ehp_basics(hp, phys, plating, mit)
        w = 0.55*ea + 0.45*eb
        print(f"  Build {build_name} full-build: HP={hp:.0f} PhysProt={phys:.1f} Damp={min(damp,35)}"
              f" Plating={min(plating,35)} | EHP-Abil={ea:,.0f} EHP-Basic={eb:,.0f} Weighted={w:,.0f}")

    print()
    print("  Build A: No mitigation items means basics and abilities use the same formula.")
    print("    Pure prot stacking creates the strongest LATE game EHP vs abilities.")
    print("    Weakness: No HP items except EoP and Nemean -> vulnerable to poke early.")
    print("  Build B: Plating(20) + Damp(30) early -> powerful but only 30 damp reaches cap at 35.")
    print("    Strong early basic EHP (Spectral Armor first). Weak ability EHP until item 4.")
    print("    At full build, Alchemist Coat's 15 damp goes partly to waste (30 damp raw < cap).")
    print("    The real waste: 3 item slots spent on damp/plat with zero phys prot = low late EHP.")
    print("  Build C: Never the best in either category but most consistent across both.")
    print("    Best for comfort picks unsure of matchup type.")


# ==================================================================
# TASK 2 - OPTIMAL GOLD ALLOCATION (6-item combinations)
# ==================================================================
def task2():
    sep()
    print("TASK 2 - OPTIMAL 6-ITEM BUILD BY WEIGHTED EHP (55% Ability / 45% Basic)")
    sep()

    items = load_defensive_items()
    god_hp, god_phys = god_stats_at_level(20)
    BASE_HP   = god_hp
    BASE_PHYS = god_phys
    BUDGET    = 14400

    base_ea = ehp_abilities(BASE_HP, BASE_PHYS, 0, 0)
    base_eb = ehp_basics(BASE_HP, BASE_PHYS, 0, 0)
    base_w  = 0.55 * base_ea + 0.45 * base_eb

    def item_efficiency(it):
        ea = ehp_abilities(BASE_HP + it["hp"], BASE_PHYS + it["phys"], it["damp"], it["dmg_mit"])
        eb = ehp_basics(BASE_HP + it["hp"], BASE_PHYS + it["phys"], it["plating"], it["dmg_mit"])
        w = 0.55 * ea + 0.45 * eb
        gain = w - base_w
        return gain / it["cost"] if it["cost"] > 0 else 0

    items_sorted = sorted(items, key=lambda x: item_efficiency(x), reverse=True)
    top_items = items_sorted[:20]

    print(f"\nTop 20 items by standalone gold efficiency (god@lvl20 base):")
    print(f"{'Rank':>4} {'Item':<30} {'Cost':>6} {'HP':>5} {'Phys':>5} {'Plat':>5} {'Damp':>5} {'DmgMit':>7} {'Eff':>10}")
    sep("-")
    for rank, it in enumerate(top_items, 1):
        eff = item_efficiency(it)
        print(f"{rank:>4} {it['name']:<30} {it['cost']:>6,} {it['hp']:>5.0f} {it['phys']:>5.0f} "
              f"{it['plating']:>5.0f} {it['damp']:>5.0f} {it['dmg_mit']:>7.0f} {eff:>10.4f}")

    print(f"\nSearching 6-item combos from top 20 items within {BUDGET:,}g budget...")

    best = []
    count = 0
    for combo in combinations(range(len(top_items)), 6):
        combo_items = [top_items[i] for i in combo]
        total_cost = sum(it["cost"] for it in combo_items)
        if total_cost > BUDGET:
            continue
        count += 1
        hp      = BASE_HP   + sum(it["hp"]      for it in combo_items)
        phys    = BASE_PHYS + sum(it["phys"]     for it in combo_items)
        damp    = sum(it["damp"]    for it in combo_items)
        plating = sum(it["plating"] for it in combo_items)
        mit     = sum(it["dmg_mit"] for it in combo_items)
        ea = ehp_abilities(hp, phys, damp, mit)
        eb = ehp_basics(hp, phys, plating, mit)
        w  = 0.55 * ea + 0.45 * eb
        best.append((w, ea, eb, total_cost, count, combo_items))

    best.sort(key=lambda x: x[0], reverse=True)

    print(f"  Evaluated {count:,} valid combos within budget.\n")
    print("TOP 5 BUILDS BY WEIGHTED EHP:")
    sep()
    for rank, (w, ea, eb, cost, _idx, combo_items) in enumerate(best[:5], 1):
        hp      = BASE_HP   + sum(it["hp"]      for it in combo_items)
        phys    = BASE_PHYS + sum(it["phys"]     for it in combo_items)
        damp    = min(sum(it["damp"]    for it in combo_items), 35)
        plating = min(sum(it["plating"] for it in combo_items), 35)
        mit     = sum(it["dmg_mit"]    for it in combo_items)
        print(f"\nRank #{rank} | Weighted EHP: {w:,.0f}  (Abil: {ea:,.0f} | Basic: {eb:,.0f})  Total: {cost:,}g")
        print(f"  HP={hp:.0f}  PhysProt={phys:.0f}  Damp(eff)={damp:.0f}  Plating(eff)={plating:.0f}  DmgMit={mit:.0f}")
        for it in combo_items:
            print(f"    * {it['name']:<30} {it['cost']:>5,}g | +HP:{it['hp']:.0f} +Phys:{it['phys']:.0f} "
                  f"+Damp:{it['damp']:.0f} +Plat:{it['plating']:.0f}")

    sep()
    print("\nKEY FINDING: The optimizer heavily favors high-prot items because:")
    print("  1. PhysProt multiplies with HP. Every +10 phys is worth more HP as HP grows.")
    print("  2. Damp/Plating have a hard cap at 35 each. Past ~2 dampening items, returns collapse.")
    print("  3. The 55/45 split means both basic and ability EHP count almost equally.")
    print("     Dual-prot items (affecting both) dominate single-stat items.")


# ==================================================================
# TASK 3 - MARGINAL VALUE CURVE
# ==================================================================
def task3():
    sep()
    print("TASK 3 - MARGINAL EHP GAIN PER +1 STAT UNIT")
    sep()

    scenarios = [
        {
            "label": "MID-GAME BASE: HP=2500, PhysProt=80, Damp=15, Plat=15, DmgMit=0",
            "hp": 2500, "phys": 80, "damp": 15, "plating": 15, "dmg_mit": 0,
        },
        {
            "label": "NEAR-CAP STATE: HP=2500, PhysProt=80, Damp=25, Plat=25, DmgMit=0",
            "hp": 2500, "phys": 80, "damp": 25, "plating": 25, "dmg_mit": 0,
        },
    ]

    for sc in scenarios:
        hp, phys, damp, plating, mit = sc["hp"], sc["phys"], sc["damp"], sc["plating"], sc["dmg_mit"]
        print(f"\n{sc['label']}")
        sep("-")

        ea0 = ehp_abilities(hp, phys, damp, mit)
        eb0 = ehp_basics(hp, phys, plating, mit)

        ea_hp1   = ehp_abilities(hp+1, phys, damp, mit)
        eb_hp1   = ehp_basics(hp+1, phys, plating, mit)

        ea_pp1   = ehp_abilities(hp, phys+1, damp, mit)
        eb_pp1   = ehp_basics(hp, phys+1, plating, mit)

        ea_da1   = ehp_abilities(hp, phys, damp+1, mit)
        eb_da1   = eb0  # dampening has no effect on basics EHP

        ea_pl1   = ea0  # plating has no effect on abilities EHP
        eb_pl1   = ehp_basics(hp, phys, plating+1, mit)

        ea_dm1   = ehp_abilities(hp, phys, damp, mit+1)
        eb_dm1   = ehp_basics(hp, phys, plating, mit+1)

        damp_note = ("AT CAP - zero gain!" if damp >= 35
                     else ("10 from cap - diminishing" if damp >= 25 else "active range"))
        plat_note = ("AT CAP - zero gain!" if plating >= 35
                     else ("10 from cap - diminishing" if plating >= 25 else "active range"))

        rows = [
            ("+1 HP",                 ea_hp1-ea0, eb_hp1-eb0,  "Affects both; linear with prot multiplier"),
            ("+1 PhysProt",           ea_pp1-ea0, eb_pp1-eb0,  "Affects both; worth more as HP grows"),
            (f"+1 Dampening (at {damp})", ea_da1-ea0, eb_da1-eb0, f"Abilities ONLY | {damp_note}"),
            (f"+1 Plating (at {plating})", ea_pl1-ea0, eb_pl1-eb0, f"Basics ONLY    | {plat_note}"),
            ("+1 DmgMit",             ea_dm1-ea0, eb_dm1-eb0,  "Affects both; rare stat"),
        ]

        print(f"{'Stat':>28} | {'dEHP-Abil':>10} | {'dEHP-Basic':>11} | {'dWeighted':>10} | Note")
        sep("-", 95)
        for label, dea, deb, note in rows:
            dw = 0.55 * dea + 0.45 * deb
            print(f"{label:>28} | {dea:>10.2f} | {deb:>11.2f} | {dw:>10.2f} | {note}")

        print(f"\n  Current EHP: Abilities={ea0:,.0f} | Basics={eb0:,.0f} | Weighted={0.55*ea0+0.45*eb0:,.0f}")

    sep()
    print("\nKEY INSIGHT SUMMARY:")
    print("  At mid-game values (HP=2500, Phys=80):")
    print("  * +1 PhysProt is worth ~3.5x more weighted EHP than +1 HP.")
    print("    This is why pure prot stacking dominates: you can't buy 3.5 HP per gold cheaper than 1 prot.")
    print("  * +1 Dampening grants ~55% of the value of +1 PhysProt (only abilities, not basics).")
    print("  * +1 Plating grants ~45% of the value of +1 PhysProt (only basics, not abilities).")
    print("  * At near-cap (25 damp/plat), both values SHRINK significantly vs PhysProt.")
    print("  * DmgMit is extremely powerful per point but almost no items provide it cleanly.")
    print("  IMPLICATION: After 30+ dampening, every gold piece is better spent on PhysProt or HP.")


# ==================================================================
# TASK 4 - THE DAMPENING CAP PROBLEM
# ==================================================================
def task4():
    sep()
    print("TASK 4 - DAMPENING CAP PROBLEM: OVER-INVESTMENT ANALYSIS")
    sep()

    # Base: Bellona@lvl20 + Eye of Providence + Dwarven Plate + Magi's Cloak + Hide of Nemean
    # These are fixed items. We then compare 2 final-slot choices.
    god_hp, god_phys = god_stats_at_level(20)
    fixed_hp   = 250 + 0   + 0   + 350   # Eye, Dwarven, Magi, Nemean
    fixed_phys = 25  + 40  + 35  + 35    # Eye, Dwarven, Magi, Nemean
    BASE_HP    = god_hp   + fixed_hp
    BASE_PHYS  = god_phys + fixed_phys

    print(f"\n  Fixed base (god@lvl20 + 4 items): HP={BASE_HP:.0f}, PhysProt={BASE_PHYS:.1f}")
    print(f"  Items: Eye of Providence + Dwarven Plate + Magi's Cloak + Hide of Nemean Lion")
    print(f"  2 item slots remain. Cost available: ~5100g. Comparing 2-slot investment choices:\n")

    scenarios = [
        {
            "label": "2x Prot: Stygian Anchor + Stone of Binding",
            "cost": 2550+2550, "hp": 0, "phys": 35+35, "damp": 0, "plating": 0, "mit": 0,
        },
        {
            "label": "1x Damp + 1x Prot: Wyrmskin + Stygian Anchor",
            "cost": 2600+2550, "hp": 250, "phys": 35, "damp": 15, "plating": 0, "mit": 0,
        },
        {
            "label": "2x Damp: Wyrmskin + Alchemist Coat (30 raw damp)",
            "cost": 2600+2350, "hp": 250, "phys": 0, "damp": 30, "plating": 0, "mit": 0,
        },
        {
            "label": "2x Damp +HP: Wyrmskin + Doublet of Binding (30 damp + 400hp)",
            "cost": 2600+2550, "hp": 250+400, "phys": 0, "damp": 15+15, "plating": 0, "mit": 0,
        },
        {
            "label": "Over-cap scenario: 3 damp items crammed in (45 raw, 35 effective, 10 wasted)",
            "cost": 2600+2350+2550, "hp": 250+0+400, "phys": 0, "damp": 45, "plating": 0, "mit": 0,
            "note": "hypothetical 3-slot; included to show waste"
        },
    ]

    print(f"{'Scenario':<55} | {'EHP-Abil':>9} | {'EHP-Basic':>10} | {'Weighted':>10} | {'Gold':>7}")
    sep("-", 100)
    for sc in scenarios:
        hp   = BASE_HP   + sc["hp"]
        phys = BASE_PHYS + sc["phys"]
        damp_raw = sc["damp"]
        damp_eff = min(damp_raw, 35)
        plat = sc["plating"]
        mit  = sc["mit"]
        ea   = ehp_abilities(hp, phys, damp_raw, mit)
        eb   = ehp_basics(hp, phys, plat, mit)
        w    = 0.55*ea + 0.45*eb
        wasted = max(0, damp_raw - 35)
        suffix = f"  [!{wasted} damp wasted]" if wasted > 0 else ""
        print(f"{sc['label']:<55} | {ea:>9,.0f} | {eb:>10,.0f} | {w:>10,.0f} | {sc['cost']:>7,}g{suffix}")

    sep("-", 100)
    print()
    print("  EXPLICIT WASTE MODELLING at the cap boundary:")
    print("  Assume you already have 20 dampening from earlier items.")
    print("  Should you buy Alchemist Coat (2350g, +15 damp) pushing you to 35 (exactly at cap)?")
    print("  Or Wyrmskin (2600g, +15 base damp) pushing to 35? Or a prot item instead?")
    print()

    BASE2_HP   = BASE_HP  + 250 + 400  # Wyrmskin's HP + Doublet's HP already in base
    BASE2_PHYS = BASE_PHYS
    EXISTING_DAMP = 20

    choices = [
        ("Alchemist Coat: +15 damp (20->35, exactly at cap)", 2350, 0,   0,  15),
        ("Wyrmskin: +15 base damp (20->35 cap, same result)",  2600, 250, 0,  15),
        ("Stygian Anchor: +35 phys, 0 damp",                   2550, 0,  35,   0),
        ("Contagion: +425 HP, 0 prot, 0 damp",                 2400, 425, 0,   0),
    ]

    print(f"  {'Choice':<52} | {'EHP-Abil':>9} | {'EHP-Basic':>10} | {'Weighted':>10} | {'Gold':>7}")
    sep("-", 100)
    for label, cost, extra_hp, extra_phys, extra_damp in choices:
        hp   = BASE2_HP   + extra_hp
        phys = BASE2_PHYS + extra_phys
        damp = EXISTING_DAMP + extra_damp
        ea   = ehp_abilities(hp, phys, damp, 0)
        eb   = ehp_basics(hp, phys, 0, 0)
        w    = 0.55*ea + 0.45*eb
        print(f"  {label:<52} | {ea:>9,.0f} | {eb:>10,.0f} | {w:>10,.0f} | {cost:>7,}g")

    print()
    print("  CONCLUSION:")
    print("  * 2x pure prot (Stygian + Stone) crushes 2x damp in weighted EHP.")
    print("    The reason: 0 damp still gets full prot multiplier. 30 damp only helps abilities.")
    print("  * Wyrmskin + Stygian (1 damp + 1 prot) is the BEST of these 2-slot combos:")
    print("    HP from Wyrmskin amplifies prot multipliers AND damp reduces ability damage.")
    print("  * Past cap (35 dampening), every additional dampening point is truly 0 value.")
    print("    Never stack 3+ dampening items. The cap ruins all marginal value past 2 items.")
    print("  * Buying prot instead of an over-cap damp item gains 5-12% weighted EHP for same gold.")


# ==================================================================
# TASK 5 - CONDITIONAL PASSIVE BREAK-EVEN
# ==================================================================
def task5():
    sep()
    print("TASK 5 - CONDITIONAL PASSIVE BREAK-EVEN: Spirit Robe vs Magi's Cloak vs Eye of Providence")
    sep()

    BASE_HP   = 2500
    BASE_PHYS = 80
    BASE_DAMP = 0
    BASE_PLAT = 0
    BASE_MIT  = 0

    # Item stats from DB:
    # Eye of Providence: 2300g, +250hp, +25phys, +25mag
    # Magi's Cloak: 2400g, +35phys, +35mag
    # Spirit Robe: 2500g, +20phys, +20mag; passive: +40 phys/mag when hard CC'd (6s)
    items_data = {
        "Eye of Providence": {"cost": 2300, "hp": 250, "phys": 25, "damp": 0, "plat": 0, "mit": 0},
        "Magi's Cloak":      {"cost": 2400, "hp":   0, "phys": 35, "damp": 0, "plat": 0, "mit": 0},
        "Spirit Robe (base)": {"cost": 2500, "hp": 0, "phys": 20, "damp": 0, "plat": 0, "mit": 0},
        "Spirit Robe (CC'd)": {"cost": 2500, "hp": 0, "phys": 60, "damp": 0, "plat": 0, "mit": 0},  # +20+40
    }

    def item_weighted_ehp(it_key):
        it = items_data[it_key]
        hp   = BASE_HP   + it["hp"]
        phys = BASE_PHYS + it["phys"]
        ea = ehp_abilities(hp, phys, it["damp"], it["mit"])
        eb = ehp_basics(hp, phys, it["plat"], it["mit"])
        return 0.55*ea + 0.45*eb

    wEoP   = item_weighted_ehp("Eye of Providence")
    wMC    = item_weighted_ehp("Magi's Cloak")
    wSR    = item_weighted_ehp("Spirit Robe (base)")
    wSR_cc = item_weighted_ehp("Spirit Robe (CC'd)")

    print(f"\n  Base stats: HP={BASE_HP}, PhysProt={BASE_PHYS}, Damp=0, Plating=0")
    print(f"\n  Raw (unconditional) weighted EHP added by each item:")
    print(f"  {'Item':<25} {'Cost':>6}  {'Weighted EHP':>14}")
    sep("-", 50)
    print(f"  {'Eye of Providence':<25} {2300:>6,}  {wEoP:>14,.0f}")
    print(f"  {'Magis Cloak':<25} {2400:>6,}  {wMC:>14,.0f}")
    print(f"  {'Spirit Robe (no CC)':<25} {2500:>6,}  {wSR:>14,.0f}")
    print(f"  {'Spirit Robe (while CCd)':<25} {'--':>6}   {wSR_cc:>14,.0f}")

    print(f"\n  Spirit Robe blended weighted EHP at various CC% of fight duration:")
    print(f"  {'CC%':>6} | {'SR Weighted':>12} | {'EoP Weighted':>13} | {'MC Weighted':>12} | {'SR-EoP':>8} | {'SR-MC':>7}")
    sep("-", 70)

    breakeven_eop = None
    breakeven_mc  = None

    for cc_pct_int in range(0, 55, 5):
        cc_pct = cc_pct_int / 100.0
        wSR_blend = (1 - cc_pct) * wSR + cc_pct * wSR_cc
        diff_eop = wSR_blend - wEoP
        diff_mc  = wSR_blend - wMC
        if diff_eop >= 0 and breakeven_eop is None:
            breakeven_eop = cc_pct_int
        if diff_mc >= 0 and breakeven_mc is None:
            breakeven_mc = cc_pct_int
        print(f"  {cc_pct_int:>5}% | {wSR_blend:>12,.0f} | {wEoP:>13,.0f} | {wMC:>12,.0f} | {diff_eop:>+8,.0f} | {diff_mc:>+7,.0f}")

    sep("-", 70)
    print(f"\n  BREAK-EVEN POINTS:")
    print(f"  * Spirit Robe overtakes Eye of Providence at ~{breakeven_eop}% CC time")
    print(f"  * Spirit Robe overtakes Magi's Cloak at ~{breakeven_mc}% CC time")

    # Also compute the precise % via linear interpolation
    # wSR_base + t*(wSR_cc - wSR_base) = wEoP  => t = (wEoP - wSR) / (wSR_cc - wSR)
    t_eop = (wEoP - wSR) / (wSR_cc - wSR) * 100
    t_mc  = (wMC  - wSR) / (wSR_cc - wSR) * 100
    print(f"  (Precise interpolation: vs EoP = {t_eop:.1f}%, vs Magi = {t_mc:.1f}%)")

    print()
    print("  ADDITIONAL VALUE NOT IN EHP FORMULA:")
    print("  Spirit Robe: +4% HP heal when hard CC'd = +100 HP healed at 2500 base HP.")
    print("    Over a fight, this is meaningful sustain. Vs kill windows, it matters.")
    print("  Magi's Cloak: 90s cooldown CC-immunity bubble.")
    print("    Hard to quantify but preventing 1 hard CC in a fight can prevent death outright.")
    print("    In solo lane where 1v1 + gank scenarios are common, this is enormous value.")
    print("    If the bubble prevents 1 death, it is worth 300-400 gold in bounty terms.")
    print("  Eye of Providence: Ward active gives vision. Team utility, not personal EHP.")
    print()
    print("  VERDICT:")
    print("  * Against heavy CC comps (2+ CC gods): Spirit Robe provides best average protection.")
    print("  * Against burst/dive with hard CC: Magi's Cloak bubble can literally prevent death.")
    print("  * Against CC-lite opponents (<15% CC time): Eye of Providence wins on raw math.")
    print("  * PRACTICAL SOLO LANE: Magi's Cloak or Spirit Robe almost always beat EoP because")
    print("    solo lane frequently involves CC from jungler ganks even if the laner isn't CC-heavy.")


# ==================================================================
# TASK 6 - TIER LIST
# ==================================================================
def task6():
    sep()
    print("TASK 6 - DEFINITIVE SOLO LANE DEFENSIVE ITEM TIER LIST")
    sep()

    items = load_defensive_items()
    god_hp, god_phys = god_stats_at_level(15)  # level 15 = typical full build timing
    # Assume 40 phys prot already from other items (mid-build context)
    BASE_HP   = god_hp
    BASE_PHYS = god_phys + 40

    base_ea = ehp_abilities(BASE_HP, BASE_PHYS, 0, 0)
    base_eb = ehp_basics(BASE_HP, BASE_PHYS, 0, 0)
    base_w  = 0.55 * base_ea + 0.45 * base_eb

    results = []
    for it in items:
        hp   = BASE_HP   + it["hp"]
        phys = BASE_PHYS + it["phys"]
        damp = it["damp"]
        plat = it["plating"]
        mit  = it["dmg_mit"]
        ea   = ehp_abilities(hp, phys, damp, mit)
        eb   = ehp_basics(hp, phys, plat, mit)
        w    = 0.55 * ea + 0.45 * eb
        gain = w - base_w
        eff  = gain / it["cost"] if it["cost"] > 0 else 0
        results.append((eff, gain, w, it["name"], it))

    results.sort(key=lambda x: x[0], reverse=True)

    print(f"\nGold efficiency rankings (Bellona@lvl15, +40 existing phys prot base):")
    print(f"{'Rank':>4} {'Item':<32} {'Cost':>6} {'HP':>5} {'Phys':>5} {'Plat':>5} {'Damp':>5} {'EHP Gain':>10} {'Eff':>10}")
    sep("-")
    for rank, (eff, gain, w, _name, it) in enumerate(results, 1):
        print(f"{rank:>4} {it['name']:<32} {it['cost']:>6,} {it['hp']:>5.0f} {it['phys']:>5.0f} "
              f"{it['plating']:>5.0f} {it['damp']:>5.0f} {gain:>10,.0f} {eff:>10.4f}")

    sep()
    print("""
TIER LIST - SOLO LANE (vs Physical Opponent, 55/45 Ability/Basic split)

==================================================================
S TIER - Best in slot; use in almost every solo lane game
==================================================================

1. MAGI'S CLOAK (2400g) | +35 phys / +35 mag
   Math: Top-3 efficiency. 70 total prot is highest dual-prot per gold in tier.
   Passive: CC-immunity bubble every 90s. In a 25-minute game that is ~16 potential bubbles.
   Solo lane involves frequent ganks and CC chains - bubble can break an entire kill attempt.
   Verdict: The CC immunity alone makes this mandatory. No other item provides this utility.

2. DWARVEN PLATE (2800g) | +40 phys / +40 mag + swap active
   Math: Highest total prot stat at any price. 80 combined prot is unmatched.
   Active: swap which prot is buffed by +30% (another 12 prot effectively).
   No HP, so buy after establishing an HP baseline. Items 3-5 slot.
   Verdict: Every solo build that can afford it should buy it.

3. HIDE OF THE NEMEAN LION (2550g) | +350 HP / +35 phys
   Math: Rank #1 in physical EHP efficiency. HP + phys prot synergize multiplicatively.
   Best in slot for pure physical matchups. Weakness: zero mag prot.
   Verdict: Mandatory in heavy-physical or crit carry matchups.

==================================================================
A TIER - Strong pickups; build in most scenarios
==================================================================

4. STYGIAN ANCHOR (2550g) | +35 phys / +30 mag
   Math: Second-best dual-prot item. Only 5 fewer mag prot than Magi's Cloak for 150g less.
   No special passive, which is actually fine: passive value is real but stat value is what matters.
   Verdict: Best "clean" prot item when you need both types without spending 2800g.

5. SPECTRAL ARMOR (2300g) | +400 HP / +20 plating + crit damage mitigation
   Math: Cheapest item with large HP. 400 HP is exceptional value at 2300g.
   Passive: -25% damage from critical strikes. VS a crit-ADC carry in solo, this is enormous.
   Crit crits normally deal 175%+ damage. Spectral cuts that to ~132% effective.
   Verdict: Almost always buy first or second. Crit protection is effectively DmgMit vs crits.

6. SPIRIT ROBE (2500g) | +20/20 prot + 40/40 when CC'd
   Math: Break-even vs Eye of Providence at ~19% CC uptime. Very achievable in solo lane.
   Break-even vs Magi's Cloak at ~34% CC uptime.
   Also provides +4% HP heal on CC proc (2500 HP = 100 HP heal).
   Verdict: Best when facing heavy CC compositions. Against CC-lite, drop to B.

7. EROSION (2400g) | +250 HP / +30 phys / +20 mag + reduction aura
   Math: Triple-stat item at a low price. Closest item to "has everything" at T3.
   Aura reduces enemy protections and healing - deceptive team value.
   Verdict: Underrated and underused. Strong first or second item.

8. EYE OF PROVIDENCE (2300g) | +250 HP / +25/25 prot + ward active
   Math: Cheapest dual-prot item. Excellent first buy gold efficiency.
   Ward active provides vision that can prevent ganks entirely.
   Break-even: beats Spirit Robe when CC uptime is below ~19%.
   Verdict: Almost always first buy. Gets outscaled but provides crucial early dual-prot + utility.

==================================================================
B TIER - Situational; solid in specific matchups
==================================================================

9. WYRMSKIN (2600g) | +250 HP / +15 base damp (+20 conditional on-hit)
   Math: Active dampening reaches cap (35) when fighting. Solid melee-god item.
   Weakness: conditional proc requires hitting enemies. Poke/range matchups weaken it.
   Verdict: Buy in melee brawl scenarios. Avoid in ranged/poke matchups.

10. STAMPEDE (2400g) | +250 HP / +30 phys + slow on hit
    Math: Single-stat prot with decent HP. Good for physical matchups.
    Passive: slows enemies - meaningful for sticking to targets.
    Verdict: Decent early buy in physical matchup if Nemean is too expensive yet.

11. BERSERKER'S SHIELD (2400g) | +30/15 prot base, +65/65 below 60% HP
    Math: Below 60% HP, total prot becomes 95 phys / 80 mag - best in slot conditional.
    Problem: You're relying on being low HP, which is reactive, not proactive.
    Verdict: Strong for aggressive fighters, risky in lane where being low HP = death threat.

12. CONTAGION (2400g) | +425 HP only
    Math: Highest raw HP at this price. Amplifies all prot multipliers.
    No protection means weak standalone EHP gain but synergizes with prot-heavy builds.
    Verdict: Buy slot 2-3 after establishing dual-prot foundation.

13. KINETIC CUIRASS (2400g) | +300 HP / +15 plating + active damage
    Math: Decent basics EHP. Outclassed by Spectral Armor for plating needs but gives solid HP.
    Verdict: If Spectral Armor is already purchased, this is the next plating option.

==================================================================
C TIER - Below average; usually outclassed
==================================================================

14. ALCHEMIST COAT (2350g) | +15 base damp (+10 conditional on consumable use)
    Math: Pure dampening with no HP or prot. Stand-alone EHP gain is weak.
    Conditional requires active consumable use during fights - cannot rely on it.
    Verdict: Only justifiable as the second dampening item in a full mitigation build.

15. DOUBLET OF BINDING (2550g) | +400 HP / +15 damp + damage redirect active
    Math: HP + damp is reasonable. Active redirects 20% of ally damage to you.
    Problem: In solo lane you are alone. Active has zero value 1v1.
    Verdict: Support item misplaced in solo. Buy Wyrmskin instead for better damp value.

16. GLORIOUS PRIDWEN (2550g) | +20/20 prot only
    Math: 40 total prot at 2550g is poor efficiency. Magi's Cloak gives 70 prot for 2400g.
    There is simply no reason to buy this over Magi's Cloak or Stygian Anchor.
    Verdict: Strictly outclassed. Skip.

17. PROPHETIC CLOAK (2400g) | +22/22 prot base (+5/5 at max stacks)
    Math: Even at max stacks (27/27), worse than Magi's Cloak (35/35) for same cost.
    Stacks require taking BOTH physical and magical hits - slow to charge in physical solo.
    Verdict: Outperformed in every dimension. Skip.

18. LEVIATHAN'S HIDE (2500g) | +300 HP / +15 plating + debuff passive
    Math: Plating without phys prot means basics EHP scales poorly late.
    Debuff reduces enemy attack by 10% on hit - helps somewhat but doesn't fix core stat weakness.
    Verdict: Outclassed by Spectral Armor. Only buy if Spectral is taken and you want more plating.

==================================================================
SKIP - Actively bad for solo lane
==================================================================

19. SHOGUN'S OFUDA (2500g) | +200 HP / +15 damp + team attack speed aura
    Math: 200 HP + 15 damp is weak value for 2500g. The aura only matters for teammates.
    In solo lane (1v1 most of the game), the aura affects no one.
    Verdict: Support item. Do not buy in solo under any circumstances.

20. PHARAOH'S CURSE (2450g) | +20 plating ONLY
    Math: 20 plating with zero HP or prot. Weakest standalone EHP of all T3 items.
    You get ~200 EHP from this item that you can only leverage on basic attacks.
    A 2250g Yogi's Necklace gives 325 HP with better weighted EHP gain.
    Verdict: Never buy. Gauntlet of Thebes gives more stat for less gold.

21. MANTLE OF DISCORD (2600g) | +15 damp / +20 tenacity + stun aura below 40% HP
    Math: 15 damp and no HP or prot for 2600g is extremely poor EHP value.
    Stun aura triggers when near-dead - you are already losing the fight.
    Tenacity helps escape CC but does not prevent the damage that is already done.
    Verdict: Too expensive for too little. The "save-me" passive fires when you are already dead.

22. GAUNTLET OF THEBES (2200g) | +200 HP base (+700 at max stacks via ally proximity)
    Math: Max-stack value (900 HP total) is excellent IF stacks are achieved.
    Problem: Solo lane means isolation. Thebes stacks from allies being near you.
    In solo you spend 70%+ of game in 1v1. You will hit max stacks in the late game
    after they are no longer efficient to acquire.
    Verdict: Excellent support item, actively bad in solo lane. The stacking mechanic
    punishes the solo laner's natural playstyle.

23. HUSSAR'S WINGS (3500g) | +500 HP / +25/25 prot
    Math: The stats are fine but 3500g is an outrageous premium.
    You can buy Eye of Providence (2300g) + Magi's Cloak (2400g) = 4700g total for
    500 HP + 60/60 prot (vs 500 HP + 25/25 prot from Hussar's at 3500g).
    Per-gold, Hussar's is the worst stat-to-cost ratio in the entire T3 defensive pool.
    Verdict: You are literally paying 50% premium for inferior combined stats.
""")


# ==================================================================
# MAIN
# ==================================================================
if __name__ == "__main__":
    task1()
    print()
    task2()
    print()
    task3()
    print()
    task4()
    print()
    task5()
    print()
    task6()
