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
let build = [];        // selected items (up to 6), each is an item object
let activeCategory = "All";

// ── Boot ───────────────────────────────────────────────────────────────────

async function init() {
  const res = await fetch("/api/items");
  allItems = await res.json();
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
  const inBuildIds = new Set(build.map(i => i.id));

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

    return `<div class="item-entry ${inBuild ? "in-build" : ""}"
                 data-id="${item.id}"
                 data-name="${escHtml(item.name)}">
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
  if (build.length >= 6) return;
  const item = allItems.find(i => i.id === id);
  if (!item || build.find(i => i.id === id)) return;
  build.push(item);
  renderBuildSlots();
  renderItemList();
  recalculate();
}

function removeItem(id) {
  build = build.filter(i => i.id !== id);
  renderBuildSlots();
  renderItemList();
  recalculate();
}

function renderBuildSlots() {
  const container = document.getElementById("build-slots");
  if (build.length === 0) {
    container.innerHTML = '<div class="build-empty">No items selected</div>';
    return;
  }
  container.innerHTML = build.map(item => {
    const tier    = item.tier ? `T${item.tier}` : "—";
    const tierCls = item.tier ? `t${item.tier}` : "";
    const cost    = item.total_cost ? `${item.total_cost}g` : item.cost ? `${item.cost}g` : "";
    return `<div class="build-item">
      <span class="item-tier ${tierCls}">${tier}</span>
      <span class="item-name">${escHtml(item.name)}</span>
      <span class="item-cost">${cost}</span>
      <button class="remove-btn" data-id="${item.id}" title="Remove">✕</button>
    </div>`;
  }).join("");

  container.querySelectorAll(".remove-btn").forEach(btn => {
    btn.addEventListener("click", () => removeItem(parseInt(btn.dataset.id)));
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

function sumItemStats() {
  const s = { hp: 0, physProt: 0, magProt: 0, plating: 0, dampening: 0, dmgMit: 0,
              mana: 0, health_regen: 0, mana_regen: 0, cooldown_reduction: 0,
              attack_speed: 0, movement_speed: 0, lifesteal: 0,
              strength: 0, intelligence: 0 };
  for (const item of build) {
    const st = item.stats;
    s.hp               += st.health               || 0;
    s.physProt         += st.physical_protection  || 0;
    s.magProt          += st.magical_protection   || 0;
    s.plating          += st.plating              || 0;
    s.dampening        += st.dampening            || 0;
    s.dmgMit           += st.damage_mitigation    || 0;
    s.mana             += st.mana                 || 0;
    s.health_regen     += st.health_regen         || 0;
    s.mana_regen       += st.mana_regen           || 0;
    s.cooldown_reduction += st.cooldown_reduction || 0;
    s.attack_speed     += st.attack_speed         || 0;
    s.movement_speed   += st.movement_speed       || 0;
    s.lifesteal        += st.lifesteal            || 0;
    s.strength         += st.strength             || 0;
    s.intelligence     += st.intelligence         || 0;
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
  const base      = getBaseStats();
  const itemTotals = sumItemStats();
  const total     = mergeStats(base, itemTotals);
  const ehp       = calcAllEHP(total);

  renderEHP(ehp);
  renderTotalStats(base, itemTotals);
  renderItemDeltas(base, itemTotals);
}

// ── Rendering Results ──────────────────────────────────────────────────────

function renderEHP(ehp) {
  const fmt = v => v === Infinity ? "∞" : v.toLocaleString();
  document.querySelector("#ehp-aa .ehp-value").textContent      = fmt(ehp.vsAA);
  document.querySelector("#ehp-mag-aa .ehp-value").textContent  = fmt(ehp.vsMagAA);
  document.querySelector("#ehp-phys-ab .ehp-value").textContent = fmt(ehp.vsPhysAb);
  document.querySelector("#ehp-mag-ab .ehp-value").textContent  = fmt(ehp.vsMagAb);
  document.querySelector("#ehp-true .ehp-value").textContent    = fmt(ehp.vsTrue);
}

const DISPLAY_STATS = [
  { key: "hp",         label: "HP",         itemKey: "hp" },
  { key: "physProt",   label: "Phys Prot",  itemKey: "physProt" },
  { key: "magProt",    label: "Mag Prot",   itemKey: "magProt" },
  { key: "plating",    label: "Plating %",  itemKey: "plating" },
  { key: "dampening",  label: "Dampening %",itemKey: "dampening" },
  { key: "dmgMit",     label: "Dmg Mit %",  itemKey: "dmgMit" },
  { key: "cooldown_reduction", label: "CDR",  itemKey: "cooldown_reduction" },
  { key: "mana",       label: "Mana",       itemKey: "mana" },
  { key: "attack_speed", label: "Atk Speed", itemKey: "attack_speed" },
  { key: "movement_speed", label: "Move Spd", itemKey: "movement_speed" },
  { key: "strength",   label: "Strength",   itemKey: "strength" },
  { key: "intelligence", label: "Intelligence", itemKey: "intelligence" },
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

function renderItemDeltas(base, itemTotals) {
  const container = document.getElementById("item-deltas");
  if (build.length === 0) {
    container.innerHTML = '<div class="delta-empty">Add items to see contributions</div>';
    return;
  }

  const totalWithAll = mergeStats(base, itemTotals);

  const rows = build.map(item => {
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
  tip.innerHTML = `
    <div class="tt-name">${escHtml(item.name)}</div>
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
