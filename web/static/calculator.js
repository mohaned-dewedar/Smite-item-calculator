/**
 * Smite 2 Build Calculator
 *
 * EHP formulas (PTS-verified, additive stacking):
 *   totalAAReduction      = min(plating, 35) + dmgMit
 *   totalAbilityReduction = min(dampening, 35) + dmgMit
 *
 *   EHP_vs_AA         = HP / ((1 - totalAAReduction/100)       * 100/(100+physProt))
 *   EHP_vs_PhysAbility= HP / ((1 - totalAbilityReduction/100)  * 100/(100+physProt))
 *   EHP_vs_MagAbility = HP / ((1 - totalAbilityReduction/100)  * 100/(100+magProt))
 *   EHP_vs_True       = HP / (1 - dmgMit/100)
 */

// ── State ──────────────────────────────────────────────────────────────────

let allItems = [];     // full item list from API
let allGods  = [];     // full god list from API
let selectedGod = null;
let buildA = [];       // Build A items (up to 6)
let buildB = [];       // Build B items (up to 6)
let activeBuild = "A"; // "A" | "B"
let activeCategory = "All";
let passiveTogglesA = new Set();  // item IDs with passive triggered in Build A
let passiveTogglesB = new Set();  // item IDs with passive triggered in Build B

function getActiveBuild()    { return activeBuild === "A" ? buildA : buildB; }
function getPassiveToggles() { return activeBuild === "A" ? passiveTogglesA : passiveTogglesB; }

// Maps DB stat_key → sumItemStats object key
const PASSIVE_STAT_KEY_MAP = {
  health:               "hp",
  physical_protection:  "physProt",
  magical_protection:   "magProt",
  plating:              "plating",
  dampening:            "dampening",
  damage_mitigation:    "dmgMit",
  health_regen:         "health_regen",
  mana:                 "mana",
  mana_regen:           "mana_regen",
  strength:             "strength",
  intelligence:         "intelligence",
  movement_speed:       "movement_speed",
  cooldown_reduction:   "cooldown_reduction",
  tenacity:             "tenacity",
  basic_attack_power:   "basic_attack_power",
  attack_speed:         "attack_speed",
  lifesteal:            "lifesteal",
  critical_chance:      "critical_chance",
  physical_penetration: "physical_penetration",
  magical_penetration:  "magical_penetration",
};

// ── Boot ───────────────────────────────────────────────────────────────────

async function init() {
  const [itemsRes, godsRes] = await Promise.all([fetch("/api/items"), fetch("/api/gods")]);
  allItems = await itemsRes.json();
  allGods  = await godsRes.json();
  renderItemList();
  bindEvents();
  recalculate();
}

// ── Event Binding ──────────────────────────────────────────────────────────

/**
 * Safely evaluate simple math expressions like "1300 + 150" or "35*2".
 * Only allows digits, spaces, and + - * / ( ) . — nothing else.
 */
function evalExpr(str) {
  const s = String(str).trim();
  if (/^[\d\s+\-*/().]+$/.test(s)) {
    try {
      const result = Function("return (" + s + ")")();
      if (typeof result === "number" && isFinite(result)) return Math.round(result * 10) / 10;
    } catch (_) {}
  }
  return parseFloat(s) || 0;
}

function bindEvents() {
  // Base stat inputs → evaluate expression on blur, recalculate on any change
  document.querySelectorAll(".stat-inputs input").forEach(inp => {
    inp.addEventListener("input", recalculate);
    inp.addEventListener("blur", () => {
      const val = evalExpr(inp.value);
      inp.value = val;
      recalculate();
    });
    inp.addEventListener("keydown", e => {
      if (e.key === "Enter") inp.blur();
    });
  });

  // God search
  const godSearch = document.getElementById("god-search");
  const godDropdown = document.getElementById("god-dropdown");

  godSearch.addEventListener("input", () => {
    const q = godSearch.value.trim().toLowerCase();
    if (!q) { godDropdown.classList.add("hidden"); return; }
    const matches = allGods.filter(g => g.name.toLowerCase().includes(q));
    if (matches.length === 0) { godDropdown.classList.add("hidden"); return; }
    godDropdown.innerHTML = matches.map(g => {
      const icon = g.icon_url
        ? `<img class="god-icon-sm" src="${escHtml(g.icon_url)}" alt="" onerror="this.style.display='none'">`
        : `<span class="god-icon-sm" style="background:var(--bg3);border-radius:4px;display:inline-block;flex-shrink:0"></span>`;
      return `<div class="god-option" data-id="${g.id}">${icon}${escHtml(g.name)}${g.role ? ` <span class="god-role">${escHtml(g.role)}</span>` : ""}</div>`;
    }).join("");
    godDropdown.classList.remove("hidden");
    godDropdown.querySelectorAll(".god-option").forEach(el => {
      el.addEventListener("click", () => selectGod(parseInt(el.dataset.id)));
    });
  });

  godSearch.addEventListener("blur", () => {
    setTimeout(() => godDropdown.classList.add("hidden"), 150);
  });

  document.getElementById("god-level").addEventListener("input", () => {
    document.getElementById("level-display").textContent =
      document.getElementById("god-level").value;
    applyGodStats();
  });

  document.getElementById("clear-god").addEventListener("click", clearGod);

  // Build tabs
  document.querySelectorAll(".build-tab").forEach(btn => {
    btn.addEventListener("click", () => {
      activeBuild = btn.dataset.build;
      document.querySelectorAll(".build-tab").forEach(b => b.classList.toggle("active", b === btn));
      renderBuildSlots();
      renderItemList();
      recalculate();
    });
  });

  // Category filter buttons
  document.getElementById("category-filters").addEventListener("click", e => {
    const btn = e.target.closest(".filter-btn");
    if (!btn) return;
    document.querySelectorAll(".filter-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    activeCategory = btn.dataset.cat;
    renderItemList();
  });

  // Search box
  document.getElementById("item-search").addEventListener("input", renderItemList);

  // Tooltip hide on scroll
  document.getElementById("item-list").addEventListener("scroll", hideTooltip);
}

// ── God Selector ───────────────────────────────────────────────────────────

function selectGod(id) {
  selectedGod = allGods.find(g => g.id === id) || null;
  const nameEl = document.getElementById("god-selected-name");
  const selectedEl = document.getElementById("god-selected");
  const searchEl = document.getElementById("god-search");
  if (selectedGod) {
    const icon = selectedGod.icon_url
      ? `<img class="god-icon-sm" src="${escHtml(selectedGod.icon_url)}" alt="" onerror="this.style.display='none'">`
      : "";
    nameEl.innerHTML = icon + escHtml(selectedGod.name + (selectedGod.role ? ` · ${selectedGod.role}` : ""));
    selectedEl.classList.remove("hidden");
    searchEl.value = "";
    searchEl.classList.add("hidden");
  }
  document.getElementById("god-dropdown").classList.add("hidden");
  applyGodStats();
}

function clearGod() {
  selectedGod = null;
  document.getElementById("god-selected").classList.add("hidden");
  const searchEl = document.getElementById("god-search");
  searchEl.classList.remove("hidden");
  searchEl.value = "";
  document.getElementById("god-level").value = "1";
  document.getElementById("level-display").textContent = "1";
  // Reset to defaults
  document.getElementById("base-hp").value = "1800";
  document.getElementById("base-phys-prot").value = "35";
  document.getElementById("base-mag-prot").value = "35";
  recalculate();
}

function godStatAt(base, perLvl, level) {
  return (base || 0) + (perLvl || 0) * (level - 1);
}

function applyGodStats() {
  if (!selectedGod) return;
  const level = parseInt(document.getElementById("god-level").value);
  const s = selectedGod.stats;
  if (s.hp_base != null) {
    document.getElementById("base-hp").value =
      Math.round(godStatAt(s.hp_base, s.hp_per_lvl, level));
  }
  if (s.phys_prot_base != null) {
    document.getElementById("base-phys-prot").value =
      fmt1(godStatAt(s.phys_prot_base, s.phys_prot_per_lvl, level));
  }
  if (s.mag_prot_base != null) {
    document.getElementById("base-mag-prot").value =
      fmt1(godStatAt(s.mag_prot_base, s.mag_prot_per_lvl, level));
  }
  recalculate();
}

// ── Item List Rendering ────────────────────────────────────────────────────

const OTHER_CATS = new Set(["Relic", "Curio", "Consumable", "God Specific", "Tier_I", "Tier_II",
                             "Upgraded_Starters", "Tier_III_Offensive", "Tier_III_Defensive",
                             "Tier_III_Hybrid"]);
const MAIN_CATS  = new Set(["Offensive", "Defensive", "Hybrid", "Starter"]);

function matchesCategory(item) {
  if (activeCategory === "All") return true;
  if (activeCategory === "Other") return !MAIN_CATS.has(item.category);
  return item.category === activeCategory;
}

function renderItemList() {
  const query = document.getElementById("item-search").value.trim().toLowerCase();
  const list  = document.getElementById("item-list");
  const inBuildIds = new Set(getActiveBuild().map(i => i.id));

  const filtered = allItems.filter(item => {
    if (!matchesCategory(item)) return false;
    if (query && !item.name.toLowerCase().includes(query)) return false;
    return true;
  });

  if (filtered.length === 0) {
    list.innerHTML = '<div class="loading">No items found</div>';
    return;
  }

  list.innerHTML = filtered.map(item => {
    const inBuild = inBuildIds.has(item.id);
    const tier    = item.tier ? `T${item.tier}` : "—";
    const tierCls = item.tier ? `t${item.tier}` : "";
    const chips   = buildStatChips(item.stats);
    const icon    = item.icon_url
      ? `<img class="item-icon" src="${escHtml(item.icon_url)}" alt="" onerror="this.style.display='none'">`
      : `<span class="item-icon-placeholder"></span>`;

    return `<div class="item-entry ${inBuild ? "in-build" : ""}"
                 data-id="${item.id}"
                 data-name="${escHtml(item.name)}">
      ${icon}
      <span class="item-tier ${tierCls}">${tier}</span>
      <span class="item-name">${escHtml(item.name)}</span>
      <div class="item-stat-chips">${chips}</div>
    </div>`;
  }).join("");

  // Click to add
  list.querySelectorAll(".item-entry:not(.in-build)").forEach(el => {
    el.addEventListener("click", () => addItem(parseInt(el.dataset.id)));
    el.addEventListener("mouseenter", e => showTooltip(e, parseInt(el.dataset.id)));
    el.addEventListener("mouseleave", hideTooltip);
  });
}

function buildStatChips(stats) {
  const chips = [];
  if (stats.physical_protection) chips.push(`<span class="chip phys">P.Prot ${stats.physical_protection}</span>`);
  if (stats.magical_protection)  chips.push(`<span class="chip mag">M.Prot ${stats.magical_protection}</span>`);
  if (stats.health)              chips.push(`<span class="chip hp">HP ${stats.health}</span>`);
  return chips.slice(0, 3).join("");
}

// ── Build Management ───────────────────────────────────────────────────────

function addItem(id) {
  const current = getActiveBuild();
  if (current.length >= 6) return;
  const item = allItems.find(i => i.id === id);
  if (!item || current.find(i => i.id === id)) return;
  current.push(item);
  renderBuildSlots();
  renderItemList();
  recalculate();
}

function removeItem(id) {
  if (activeBuild === "A") { buildA = buildA.filter(i => i.id !== id); passiveTogglesA.delete(id); }
  else                     { buildB = buildB.filter(i => i.id !== id); passiveTogglesB.delete(id); }
  renderBuildSlots();
  renderItemList();
  recalculate();
}

function renderBuildSlots() {
  const container = document.getElementById("build-slots");
  const current = getActiveBuild();
  if (current.length === 0) {
    container.innerHTML = '<div class="build-empty">No items selected</div>';
    return;
  }
  const toggles = getPassiveToggles();
  container.innerHTML = current.map(item => {
    const tier       = item.tier ? `T${item.tier}` : "—";
    const tierCls    = item.tier ? `t${item.tier}` : "";
    const cost       = item.total_cost ? `${item.total_cost}g` : item.cost ? `${item.cost}g` : "";
    const icon       = item.icon_url
      ? `<img class="item-icon item-icon-sm" src="${escHtml(item.icon_url)}" alt="" onerror="this.style.display='none'">`
      : `<span class="item-icon-placeholder item-icon-sm"></span>`;
    const hasPassive = item.passive_stats && item.passive_stats.length > 0;
    const toggled    = toggles.has(item.id);
    const conditions = hasPassive
      ? [...new Set(item.passive_stats.map(p => p.condition))].join(", ")
      : "";
    const passiveBtn = hasPassive
      ? `<button class="passive-toggle ${toggled ? "active" : ""}" data-id="${item.id}"
                 title="${toggled ? "Passive ON" : "Passive OFF"}: ${escHtml(conditions)}">&#9889;</button>`
      : "";
    return `<div class="build-item">
      ${icon}
      <span class="item-tier ${tierCls}">${tier}</span>
      <span class="item-name">${escHtml(item.name)}</span>
      <span class="item-cost">${cost}</span>
      ${passiveBtn}
      <button class="remove-btn" data-id="${item.id}" title="Remove">&#x2715;</button>
    </div>`;
  }).join("");

  container.querySelectorAll(".remove-btn").forEach(btn => {
    btn.addEventListener("click", () => removeItem(parseInt(btn.dataset.id)));
  });

  container.querySelectorAll(".passive-toggle").forEach(btn => {
    btn.addEventListener("click", () => {
      const id = parseInt(btn.dataset.id);
      const t = getPassiveToggles();
      t.has(id) ? t.delete(id) : t.add(id);
      renderBuildSlots();
      recalculate();
    });
  });
}

// ── Calculation ────────────────────────────────────────────────────────────

function getBaseStats() {
  return {
    hp:         parseFloat(document.getElementById("base-hp").value)        || 0,
    physProt:   parseFloat(document.getElementById("base-phys-prot").value) || 0,
    magProt:    parseFloat(document.getElementById("base-mag-prot").value)  || 0,
    plating:    parseFloat(document.getElementById("base-plating").value)   || 0,
    dampening:  parseFloat(document.getElementById("base-dampening").value) || 0,
    dmgMit:     parseFloat(document.getElementById("base-dmg-mit").value)   || 0,
  };
}

function sumItemStats(buildArr, toggleSet = new Set()) {
  const s = { hp: 0, physProt: 0, magProt: 0, plating: 0, dampening: 0, dmgMit: 0,
              mana: 0, health_regen: 0, mana_regen: 0, cooldown_reduction: 0,
              attack_speed: 0, movement_speed: 0, lifesteal: 0,
              strength: 0, intelligence: 0,
              physical_penetration: 0, magical_penetration: 0, penetration: 0,
              critical_chance: 0, tenacity: 0, basic_attack_power: 0 };

  // Pass 1: sum base item stats (no passives)
  for (const item of (buildArr || getActiveBuild())) {
    const st = item.stats;
    s.hp                   += st.health               || 0;
    s.physProt             += st.physical_protection  || 0;
    s.magProt              += st.magical_protection   || 0;
    s.plating              += st.plating              || 0;
    s.dampening            += st.dampening            || 0;
    s.dmgMit               += st.damage_mitigation    || 0;
    s.mana                 += st.mana                 || 0;
    s.health_regen         += st.health_regen         || 0;
    s.mana_regen           += st.mana_regen           || 0;
    s.cooldown_reduction   += st.cooldown_reduction   || 0;
    s.attack_speed         += st.attack_speed         || 0;
    s.movement_speed       += st.movement_speed       || 0;
    s.lifesteal            += st.lifesteal            || 0;
    s.strength             += st.strength             || 0;
    s.intelligence         += st.intelligence         || 0;
    s.physical_penetration += st.physical_penetration || 0;
    s.magical_penetration  += st.magical_penetration  || 0;
    s.penetration          += st.penetration          || 0;
    s.critical_chance      += st.critical_chance      || 0;
    s.tenacity             += st.tenacity             || 0;
    s.basic_attack_power   += st.basic_attack_power   || 0;
  }

  // Pass 2: apply toggled passive stats
  // Snapshot base totals so pct_of_item_stat uses pre-passive values
  const base = { ...s };
  for (const item of (buildArr || getActiveBuild())) {
    if (!toggleSet.has(item.id) || !item.passive_stats) continue;
    // For adaptive items: determine dominant stat from base totals
    const strDominant = base.strength >= base.intelligence;
    for (const ps of item.passive_stats) {
      const jsKey = PASSIVE_STAT_KEY_MAP[ps.stat_key];
      if (jsKey === undefined) continue;
      // Skip non-dominant branch for adaptive stats
      if (ps.is_adaptive) {
        if (ps.stat_key === "strength"     && !strDominant) continue;
        if (ps.stat_key === "intelligence" && strDominant)  continue;
      }
      if (ps.value_type === "pct_of_item_stat") {
        s[jsKey] = (s[jsKey] || 0) + (base[jsKey] || 0) * ps.value / 100;
      } else {
        s[jsKey] = (s[jsKey] || 0) + ps.value;
      }
    }
  }
  return s;
}

/**
 * EHP calculation.
 * platingOrDamp: raw value (capped at 35 inside)
 * dmgMit: raw % (additive with plating/dampening, no cap)
 */
function calcEHP(hp, prot, platingOrDamp, dmgMit) {
  const cappedExtra    = Math.min(platingOrDamp, 35);
  const totalReduction = (cappedExtra + dmgMit) / 100;
  const damageFraction = (1 - totalReduction) * (100 / (100 + prot));
  if (damageFraction <= 0) return Infinity;
  return Math.round(hp / damageFraction);
}

function calcAllEHP(total) {
  return {
    vsAA:      calcEHP(total.hp, total.physProt, total.plating,   total.dmgMit),
    vsMagAA:   calcEHP(total.hp, total.magProt,  total.plating,   total.dmgMit),
    vsPhysAb:  calcEHP(total.hp, total.physProt, total.dampening, total.dmgMit),
    vsMagAb:   calcEHP(total.hp, total.magProt,  total.dampening, total.dmgMit),
    vsTrue:    calcEHP(total.hp, 0,              0,               total.dmgMit),
  };
}

function mergeStats(base, items) {
  return {
    hp:         base.hp        + items.hp,
    physProt:   base.physProt  + items.physProt,
    magProt:    base.magProt   + items.magProt,
    plating:    base.plating   + items.plating,
    dampening:  base.dampening + items.dampening,
    dmgMit:     base.dmgMit    + items.dmgMit,
  };
}

function recalculate() {
  const base    = getBaseStats();
  const itemsA  = sumItemStats(buildA, passiveTogglesA);
  const itemsB  = sumItemStats(buildB, passiveTogglesB);
  const totalA  = mergeStats(base, itemsA);
  const totalB  = mergeStats(base, itemsB);

  renderCompareTable(calcAllEHP(totalA), calcAllEHP(totalB));
  const activeItems = activeBuild === "A" ? itemsA : itemsB;
  renderTotalStats(base, activeItems);
  renderItemDeltas(base, activeItems, activeBuild === "A" ? buildA : buildB);
}

// ── Rendering Results ──────────────────────────────────────────────────────

const EHP_ROWS = [
  { label: "vs Phys Basic Attacks", key: "vsAA",     sub: "Phys prot + Plating + DmgMit" },
  { label: "vs Mag Basic Attacks",  key: "vsMagAA",  sub: "Mag prot + Plating + DmgMit" },
  { label: "vs Phys Abilities",     key: "vsPhysAb", sub: "Phys prot + Dampening + DmgMit" },
  { label: "vs Mag Abilities",      key: "vsMagAb",  sub: "Mag prot + Dampening + DmgMit" },
  { label: "vs True Damage",        key: "vsTrue",   sub: "HP + DmgMit only" },
];

function renderCompareTable(ehpA, ehpB) {
  const fmt = v => v === Infinity ? "∞" : v.toLocaleString();
  const container = document.getElementById("compare-table");

  const header = `<div class="compare-header">
    <span class="compare-label"></span>
    <span class="compare-cell col-a-hdr">A</span>
    <span class="compare-cell col-b-hdr">B</span>
    <span class="compare-cell delta-hdr">Δ</span>
  </div>`;

  const rows = EHP_ROWS.map(r => {
    const a = ehpA[r.key];
    const b = ehpB[r.key];
    const d = (a === Infinity || b === Infinity) ? null : b - a;
    const dStr = d === null ? "∞" : d === 0 ? "—" : (d > 0 ? "+" : "") + d.toLocaleString();
    const dCls = d === null || d === 0 ? "delta-zero" : d > 0 ? "delta-pos" : "delta-neg";
    return `<div class="compare-row">
      <span class="compare-label">${r.label}<br><span class="compare-sub">${r.sub}</span></span>
      <span class="compare-cell col-a">${fmt(a)}</span>
      <span class="compare-cell col-b">${fmt(b)}</span>
      <span class="compare-cell ${dCls}">${dStr}</span>
    </div>`;
  }).join("");

  container.innerHTML = header + rows;
}

const DISPLAY_STATS = [
  { key: "hp",                  label: "HP",           itemKey: "hp" },
  { key: "physProt",            label: "Phys Prot",    itemKey: "physProt" },
  { key: "magProt",             label: "Mag Prot",     itemKey: "magProt" },
  { key: "strength",            label: "Strength",     itemKey: "strength" },
  { key: "intelligence",        label: "Intelligence", itemKey: "intelligence" },
  { key: "plating",             label: "Plating %",    itemKey: "plating" },
  { key: "dampening",           label: "Dampening %",  itemKey: "dampening" },
  { key: "dmgMit",              label: "Dmg Mit %",    itemKey: "dmgMit" },
  { key: "cooldown_reduction",  label: "CDR",          itemKey: "cooldown_reduction" },
  { key: "mana",                label: "Mana",         itemKey: "mana" },
  { key: "health_regen",        label: "HP Regen",     itemKey: "health_regen" },
  { key: "mana_regen",          label: "Mana Regen",   itemKey: "mana_regen" },
  { key: "attack_speed",        label: "Atk Speed",    itemKey: "attack_speed" },
  { key: "movement_speed",      label: "Move Spd",     itemKey: "movement_speed" },
  { key: "lifesteal",           label: "Lifesteal",    itemKey: "lifesteal" },
  { key: "physical_penetration",label: "Phys Pen",     itemKey: "physical_penetration" },
  { key: "magical_penetration", label: "Mag Pen",      itemKey: "magical_penetration" },
  { key: "penetration",         label: "Penetration",  itemKey: "penetration" },
  { key: "critical_chance",     label: "Crit %",       itemKey: "critical_chance" },
  { key: "tenacity",            label: "Tenacity",     itemKey: "tenacity" },
  { key: "basic_attack_power",  label: "BAP",          itemKey: "basic_attack_power" },
];

function renderTotalStats(base, items) {
  const container = document.getElementById("total-stats");
  const rows = [];

  for (const s of DISPLAY_STATS) {
    const baseVal  = base[s.key] || 0;
    const itemVal  = items[s.itemKey] || 0;
    const total    = baseVal + itemVal;
    if (total === 0) continue;

    const deltaHtml = itemVal > 0
      ? `<span class="stat-delta">+${fmt1(itemVal)}</span>`
      : "";
    rows.push(`<div class="stat-row">
      <span class="stat-name">${s.label}</span>
      <span class="stat-val">${fmt1(total)}${deltaHtml}</span>
    </div>`);
  }

  container.innerHTML = rows.length ? rows.join("") : '<div class="build-empty">—</div>';
}

function renderItemDeltas(base, itemTotals, buildArr) {
  const container = document.getElementById("item-deltas");
  if (!buildArr || buildArr.length === 0) {
    container.innerHTML = '<div class="delta-empty">Add items to see contributions</div>';
    return;
  }

  const totalWithAll = mergeStats(base, itemTotals);

  const rows = buildArr.map(item => {
    // Stats without this item
    const withoutItemStats = {
      hp:        itemTotals.hp        - (item.stats.health              || 0),
      physProt:  itemTotals.physProt  - (item.stats.physical_protection || 0),
      magProt:   itemTotals.magProt   - (item.stats.magical_protection  || 0),
      plating:   itemTotals.plating   - (item.stats.plating             || 0),
      dampening: itemTotals.dampening - (item.stats.dampening           || 0),
      dmgMit:    itemTotals.dmgMit    - (item.stats.damage_mitigation   || 0),
    };
    const without = mergeStats(base, withoutItemStats);
    const ehpWith    = calcAllEHP(totalWithAll);
    const ehpWithout = calcAllEHP(without);

    const dAA    = ehpWith.vsAA     - ehpWithout.vsAA;
    const dMagAA = ehpWith.vsMagAA  - ehpWithout.vsMagAA;
    const dPhys  = ehpWith.vsPhysAb - ehpWithout.vsPhysAb;
    const dMag   = ehpWith.vsMagAb  - ehpWithout.vsMagAb;
    const dTrue  = ehpWith.vsTrue   - ehpWithout.vsTrue;

    const vals = [
      dAA    ? `<span class="delta-val aa">Phys AA +${dAA.toLocaleString()}</span>`       : "",
      dMagAA ? `<span class="delta-val mag-aa">Mag AA +${dMagAA.toLocaleString()}</span>` : "",
      dPhys  ? `<span class="delta-val phys">Phys Ab +${dPhys.toLocaleString()}</span>`   : "",
      dMag   ? `<span class="delta-val mag">Mag Ab +${dMag.toLocaleString()}</span>`      : "",
      dTrue  ? `<span class="delta-val true-dmg">True +${dTrue.toLocaleString()}</span>`  : "",
    ].filter(Boolean).join("");

    return `<div class="delta-row">
      <div class="delta-name">${escHtml(item.name)}</div>
      <div class="delta-values">${vals || '<span style="font-size:10px;color:var(--text-dim)">No defensive stats</span>'}</div>
    </div>`;
  });

  container.innerHTML = rows.join("");
}

// ── Tooltip ────────────────────────────────────────────────────────────────

const STAT_LABELS = {
  health: "Health", physical_protection: "Phys Prot", magical_protection: "Mag Prot",
  mana: "Mana", cooldown_reduction: "CDR", attack_speed: "Atk Speed",
  movement_speed: "Move Speed", lifesteal: "Lifesteal", strength: "Strength",
  intelligence: "Intelligence", physical_penetration: "Phys Pen", magical_penetration: "Mag Pen",
  health_regen: "HP Regen", mana_regen: "Mana Regen", damage_mitigation: "Dmg Mit %",
  plating: "Plating %", dampening: "Dampening %", basic_attack_power: "BAP",
  critical_chance: "Crit %", penetration: "Penetration", tenacity: "Tenacity",
};

function showTooltip(e, id) {
  const item = allItems.find(i => i.id === id);
  if (!item) return;

  const statLines = Object.entries(item.stats)
    .filter(([, v]) => v)
    .map(([k, v]) => `<div class="tt-stat">${STAT_LABELS[k] || k}: <span>${fmt1(v)}</span></div>`)
    .join("");

  const passive = item.passive
    ? `<div class="tt-passive"><em>Passive:</em> ${escHtml(item.passive)}</div>`
    : "";
  const active = item.active
    ? `<div class="tt-passive"><em>Active:</em> ${escHtml(item.active)}</div>`
    : "";

  const tip = document.getElementById("tooltip");
  const ttIcon = item.icon_url
    ? `<img class="tt-icon" src="${escHtml(item.icon_url)}" alt="" onerror="this.style.display='none'">`
    : "";
  tip.innerHTML = `
    <div class="tt-header">${ttIcon}<div class="tt-name">${escHtml(item.name)}</div></div>
    <div class="tt-stats">${statLines}</div>
    ${passive}${active}
  `;
  tip.classList.remove("hidden");
  positionTooltip(e);
}

function positionTooltip(e) {
  const tip = document.getElementById("tooltip");
  const x = e.clientX + 12;
  const y = e.clientY + 12;
  const maxX = window.innerWidth  - tip.offsetWidth  - 8;
  const maxY = window.innerHeight - tip.offsetHeight - 8;
  tip.style.left = Math.min(x, maxX) + "px";
  tip.style.top  = Math.min(y, maxY) + "px";
}

function hideTooltip() {
  document.getElementById("tooltip").classList.add("hidden");
}

// ── Utils ──────────────────────────────────────────────────────────────────

function fmt1(v) {
  return Number.isInteger(v) || Math.abs(v) >= 10 ? Math.round(v) : v.toFixed(1);
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// ── Start ──────────────────────────────────────────────────────────────────
init();
