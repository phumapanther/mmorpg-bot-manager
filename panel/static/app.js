"use strict";

const state = {
  config: null,
  guilds: [],
  channels: [],
  roles: [],
};

// ---------- generic helpers ----------

async function api(method, url, body) {
  const opts = { method, headers: {} };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(url, opts);
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(text || res.statusText);
  }
  return res.json();
}

function toast(msg) {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.classList.add("show");
  setTimeout(() => el.classList.remove("show"), 2500);
}

// ---------- config load/save ----------

async function loadConfig() {
  state.config = await api("GET", "/api/config");
}

async function saveConfig(showToast = true) {
  await api("PUT", "/api/config", state.config);
  if (showToast) toast("บันทึกแล้ว — กด Restart บอทเพื่อให้มีผล");
}

// ---------- setup tab ----------

async function verifyToken() {
  const errEl = document.getElementById("setupError");
  errEl.textContent = "";
  const token = document.getElementById("tokenInput").value.trim();
  state.config.bot_token = token;
  try {
    await saveConfig(false);
    state.guilds = await api("GET", "/api/discord/guilds");
    fillGuildSelect();
    toast("เชื่อมต่อสำเร็จ");
  } catch (e) {
    errEl.textContent = "เชื่อมต่อไม่สำเร็จ: " + e.message;
  }
}

function fillGuildSelect() {
  const sel = document.getElementById("guildSelect");
  sel.innerHTML = '<option value="">-- เลือกกิลด์ --</option>';
  for (const g of state.guilds) {
    const opt = document.createElement("option");
    opt.value = g.id;
    opt.textContent = g.name;
    sel.appendChild(opt);
  }
  if (state.config.guild_id != null) {
    sel.value = String(state.config.guild_id);
  }
}

async function onGuildChange() {
  const sel = document.getElementById("guildSelect");
  const guildId = sel.value;
  state.config.guild_id = guildId || null;
  if (!guildId) {
    state.channels = [];
    state.roles = [];
    renderChannels();
    renderPermissions();
    renderTrade();
    renderShop();
    renderSkillsTab();
    renderItemsCatalog();
    renderRankRewards();
    return;
  }
  try {
    const [channels, roles] = await Promise.all([
      api("GET", `/api/discord/channels?guild_id=${guildId}`),
      api("GET", `/api/discord/roles?guild_id=${guildId}`),
    ]);
    state.channels = channels;
    state.roles = roles;
  } catch (e) {
    toast("โหลดข้อมูลกิลด์ไม่สำเร็จ: " + e.message);
    state.channels = [];
    state.roles = [];
  }
  renderChannels();
  renderPermissions();
  renderTrade();
  renderShop();
  renderSkillsTab();
  renderItemsCatalog();
  renderRankRewards();
}

async function setupSave() {
  state.config.license_key = document.getElementById("licenseKeyInput").value.trim();
  // 🌍 โหมดหลายเซิร์ฟ (P8)
  state.config.guest_bot_token = document.getElementById("guestTokenInput").value.trim();
  const mainId = document.getElementById("mainGuildIdInput").value.trim();
  // ⚠️ ไอดี Discord ยาวเกินความแม่นยำของ Number ใน JS (>2^53) — ต้องเก็บเป็น string เท่านั้น
  state.config.main_guild_id = mainId || null;
  state.config.main_server_invite = document.getElementById("mainInviteInput").value.trim();
  await saveConfig();
}

// ---------- dashboard tab ----------

async function refreshStatus() {
  const s = await api("GET", "/api/bot/status");
  applyStatus(s);
}

function applyStatus(s) {
  const dot = document.getElementById("statusDot");
  const text = document.getElementById("statusText");
  const pid = document.getElementById("statusPid");
  if (s.running) {
    dot.className = "dot running";
    text.textContent = "กำลังทำงาน";
    pid.textContent = s.pid != null ? `PID ${s.pid}` : "";
  } else {
    dot.className = "dot stopped";
    text.textContent = "หยุดทำงาน";
    pid.textContent = "";
  }
}

async function pollLog() {
  try {
    const r = await api("GET", "/api/bot/log");
    const pre = document.getElementById("log");
    const atBottom = pre.scrollTop + pre.clientHeight >= pre.scrollHeight - 5;
    pre.textContent = r.lines.join("\n");
    if (atBottom) pre.scrollTop = pre.scrollHeight;
  } catch (e) {
    // ignore transient errors while polling
  }
}

async function startBot() {
  applyStatus(await api("POST", "/api/bot/start"));
}
async function stopBot() {
  applyStatus(await api("POST", "/api/bot/stop"));
}
async function restartBot() {
  applyStatus(await api("POST", "/api/bot/restart"));
}

// ---------- channels tab ----------

function refreshChannelOptions() {
  const selects = Array.from(document.querySelectorAll("#channelsTable select"));
  const currentValues = selects.map((sel) => sel.value);
  selects.forEach((sel, i) => {
    const used = new Set(currentValues.filter((v, j) => j !== i && v));
    Array.from(sel.options).forEach((opt) => {
      if (!opt.value) return;
      opt.hidden = used.has(opt.value) && opt.value !== sel.value;
    });
  });
}

function renderChannels() {
  const tbody = document.querySelector("#channelsTable tbody");
  tbody.innerHTML = "";
  const channels = state.config.channels || {};
  for (const key of Object.keys(channels)) {
    const entry = channels[key];
    const tr = document.createElement("tr");

    const tdLabel = document.createElement("td");
    tdLabel.textContent = entry.label || key;
    tr.appendChild(tdLabel);

    const tdSelect = document.createElement("td");
    const sel = document.createElement("select");
    sel.dataset.key = key;
    sel.innerHTML = '<option value="">-- ไม่ระบุ --</option>';
    for (const c of state.channels) {
      const opt = document.createElement("option");
      opt.value = c.id;
      opt.textContent = "#" + c.name;
      sel.appendChild(opt);
    }
    if (entry.channel_id != null) sel.value = String(entry.channel_id);
    sel.addEventListener("change", refreshChannelOptions);
    tdSelect.appendChild(sel);
    tr.appendChild(tdSelect);

    const tdMention = document.createElement("td");
    if (Object.prototype.hasOwnProperty.call(entry, "mention_player")) {
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.className = "mention-toggle";
      cb.checked = !!entry.mention_player;
      tdMention.appendChild(cb);
    }
    tr.appendChild(tdMention);

    tbody.appendChild(tr);
  }
  refreshChannelOptions();
}

async function channelsSave() {
  const tbody = document.querySelector("#channelsTable tbody");
  tbody.querySelectorAll("tr").forEach((tr) => {
    const sel = tr.querySelector("select");
    const key = sel.dataset.key;
    state.config.channels[key].channel_id = sel.value || null;
    const mentionCb = tr.querySelector(".mention-toggle");
    if (mentionCb) {
      state.config.channels[key].mention_player = mentionCb.checked;
    }
  });
  await saveConfig();
}

// ---------- permissions tab ----------

function renderPermissions() {
  const root = document.getElementById("permissionsGroups");
  root.innerHTML = "";
  const groups = state.config.permission_groups || {};
  for (const key of Object.keys(groups)) {
    const group = groups[key];
    const wrap = document.createElement("div");
    wrap.className = "perm-group";
    wrap.dataset.key = key;

    const h = document.createElement("h3");
    h.textContent = group.label || key;
    wrap.appendChild(h);

    const list = document.createElement("div");
    list.className = "role-list";
    const current = new Set((group.role_ids || []).map(String));
    for (const r of state.roles) {
      const label = document.createElement("label");
      label.className = "role-check";
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.value = r.id;
      cb.checked = current.has(String(r.id));
      label.appendChild(cb);
      label.appendChild(document.createTextNode(r.name));
      list.appendChild(label);
    }
    wrap.appendChild(list);
    root.appendChild(wrap);
  }
}

async function permissionsSave() {
  document.querySelectorAll("#permissionsGroups .perm-group").forEach((wrap) => {
    const key = wrap.dataset.key;
    const ids = [];
    wrap.querySelectorAll('input[type="checkbox"]:checked').forEach((cb) => {
      ids.push(cb.value);
    });
    state.config.permission_groups[key].role_ids = ids;
  });
  await saveConfig();
}

// ---------- auto-trade tab ----------

function refreshTradeRoleOptions() {
  const selects = Array.from(document.querySelectorAll("#darkTable select.trade-role, #lightTable select.trade-role"));
  const currentValues = selects.map((sel) => sel.value);
  selects.forEach((sel, i) => {
    const used = new Set(currentValues.filter((v, j) => j !== i && v));
    Array.from(sel.options).forEach((opt) => {
      if (!opt.value) return;
      opt.hidden = used.has(opt.value) && opt.value !== sel.value;
    });
  });
}

function roleSelectHtml(selectedId) {
  const sel = document.createElement("select");
  sel.className = "trade-role";
  sel.innerHTML = '<option value="">-- ไม่ระบุ --</option>';
  for (const r of state.roles) {
    const opt = document.createElement("option");
    opt.value = r.id;
    opt.textContent = r.name;
    sel.appendChild(opt);
  }
  if (selectedId != null) sel.value = String(selectedId);
  sel.addEventListener("change", refreshTradeRoleOptions);
  return sel;
}

function renderTradeTable(listKey, tableId) {
  const tbody = document.querySelector(`#${tableId} tbody`);
  tbody.innerHTML = "";
  const rows = state.config.auto_trade_roles[listKey] || [];
  rows.forEach((item, idx) => {
    const tr = document.createElement("tr");
    tr.dataset.idx = idx;

    const tdLabel = document.createElement("td");
    const labelInput = document.createElement("input");
    labelInput.type = "text";
    labelInput.className = "trade-label";
    labelInput.value = item.label || "";
    tdLabel.appendChild(labelInput);
    tr.appendChild(tdLabel);

    const tdPrice = document.createElement("td");
    const priceInput = document.createElement("input");
    priceInput.type = "number";
    priceInput.className = "trade-price";
    priceInput.value = item.price != null ? item.price : 0;
    tdPrice.appendChild(priceInput);
    tr.appendChild(tdPrice);

    const tdRole = document.createElement("td");
    const sel = roleSelectHtml(item.role_id);
    tdRole.appendChild(sel);
    tr.appendChild(tdRole);

    const tdDel = document.createElement("td");
    const delBtn = document.createElement("button");
    delBtn.type = "button";
    delBtn.textContent = "ลบ";
    delBtn.onclick = () => {
      state.config.auto_trade_roles[listKey].splice(idx, 1);
      renderTrade();
    };
    tdDel.appendChild(delBtn);
    tr.appendChild(tdDel);

    tbody.appendChild(tr);
  });
}

function renderTrade() {
  renderTradeTable("dark", "darkTable");
  renderTradeTable("light", "lightTable");
  document.getElementById("gachaPrice").value = state.config.auto_trade_roles.gacha_price ?? 0;
  document.getElementById("gachaPoolPrice").value = state.config.auto_trade_roles.gacha_pool_price ?? 0;
  refreshTradeRoleOptions();
}

function addTradeRow(listKey) {
  state.config.auto_trade_roles[listKey].push({
    label: "ยศใหม่",
    value: "role_" + Date.now(),
    price: 0,
    role_id: null,
    emoji: "",
  });
  renderTrade();
}

function collectTradeTable(listKey, tableId) {
  const tbody = document.querySelector(`#${tableId} tbody`);
  const rows = state.config.auto_trade_roles[listKey];
  tbody.querySelectorAll("tr").forEach((tr) => {
    const idx = parseInt(tr.dataset.idx, 10);
    const item = rows[idx];
    item.label = tr.querySelector(".trade-label").value;
    item.price = parseInt(tr.querySelector(".trade-price").value, 10) || 0;
    const roleVal = tr.querySelector(".trade-role").value;
    item.role_id = roleVal || null;
  });
}

async function tradeSave() {
  collectTradeTable("dark", "darkTable");
  collectTradeTable("light", "lightTable");
  state.config.auto_trade_roles.gacha_price = parseInt(document.getElementById("gachaPrice").value, 10) || 0;
  state.config.auto_trade_roles.gacha_pool_price = parseInt(document.getElementById("gachaPoolPrice").value, 10) || 0;
  await saveConfig();
}

// ---------- shop tab ----------

const SHOP_TYPES = [
  { value: "rank_role", label: "ซื้อยศตรง" },
  { value: "gacha_human", label: "กาชาสุ่มเผ่ามนุษย์" },
  { value: "gacha_monster", label: "กาชาสุ่มเผ่าปีศาจ" },
  { value: "gacha_class", label: "กาชาสุ่มคลาสอาชีพ" },
];

function refreshShopRoleOptions() {
  const selects = Array.from(document.querySelectorAll("#shopTable select.shop-role"));
  const currentValues = selects.map((sel) => (sel.disabled ? "" : sel.value));
  selects.forEach((sel, i) => {
    const used = new Set(currentValues.filter((v, j) => j !== i && v));
    Array.from(sel.options).forEach((opt) => {
      if (!opt.value) return;
      opt.hidden = used.has(opt.value) && opt.value !== sel.value;
    });
  });
}

function shopRoleSelectHtml(selectedId, enabled) {
  const sel = document.createElement("select");
  sel.className = "shop-role";
  sel.innerHTML = '<option value="">-- ไม่ระบุ --</option>';
  for (const r of state.roles) {
    const opt = document.createElement("option");
    opt.value = r.id;
    opt.textContent = r.name;
    sel.appendChild(opt);
  }
  if (selectedId != null) sel.value = String(selectedId);
  sel.disabled = !enabled;
  sel.addEventListener("change", refreshShopRoleOptions);
  return sel;
}

function shopTypeSelectHtml(selectedType) {
  const sel = document.createElement("select");
  sel.className = "shop-type";
  for (const t of SHOP_TYPES) {
    const opt = document.createElement("option");
    opt.value = t.value;
    opt.textContent = t.label;
    sel.appendChild(opt);
  }
  sel.value = selectedType || "rank_role";
  return sel;
}

function renderShop() {
  const tbody = document.querySelector("#shopTable tbody");
  tbody.innerHTML = "";
  const items = state.config.shop_items || [];
  items.forEach((item, idx) => {
    const tr = document.createElement("tr");
    tr.dataset.idx = idx;

    const tdNum = document.createElement("td");
    tdNum.textContent = idx + 1;
    tr.appendChild(tdNum);

    const tdName = document.createElement("td");
    const nameInput = document.createElement("input");
    nameInput.type = "text";
    nameInput.className = "shop-name";
    nameInput.value = item.name || "";
    tdName.appendChild(nameInput);
    tr.appendChild(tdName);

    const tdPrice = document.createElement("td");
    const priceInput = document.createElement("input");
    priceInput.type = "number";
    priceInput.className = "shop-price";
    priceInput.value = item.price != null ? item.price : 0;
    tdPrice.appendChild(priceInput);
    tr.appendChild(tdPrice);

    const tdType = document.createElement("td");
    const typeSel = shopTypeSelectHtml(item.type);
    tdType.appendChild(typeSel);
    tr.appendChild(tdType);

    const tdRole = document.createElement("td");
    const roleSel = shopRoleSelectHtml(item.role_id, typeSel.value === "rank_role");
    tdRole.appendChild(roleSel);
    tr.appendChild(tdRole);
    typeSel.addEventListener("change", () => {
      roleSel.disabled = typeSel.value !== "rank_role";
      refreshShopRoleOptions();
    });

    const tdDel = document.createElement("td");
    const delBtn = document.createElement("button");
    delBtn.type = "button";
    delBtn.textContent = "ลบ";
    delBtn.onclick = () => {
      state.config.shop_items.splice(idx, 1);
      renderShop();
    };
    tdDel.appendChild(delBtn);
    tr.appendChild(tdDel);

    tbody.appendChild(tr);
  });
  refreshShopRoleOptions();
}

function addShopRow() {
  if (!state.config.shop_items) state.config.shop_items = [];
  state.config.shop_items.push({ name: "ไอเทมใหม่", price: 0, type: "rank_role", role_id: null });
  renderShop();
}

async function shopSave() {
  const tbody = document.querySelector("#shopTable tbody");
  const items = [];
  tbody.querySelectorAll("tr").forEach((tr) => {
    const name = tr.querySelector(".shop-name").value;
    const price = parseInt(tr.querySelector(".shop-price").value, 10) || 0;
    const type = tr.querySelector(".shop-type").value;
    const roleSel = tr.querySelector(".shop-role");
    const role_id = type === "rank_role" ? (roleSel.value || null) : null;
    items.push({ name, price, type, role_id });
  });
  state.config.shop_items = items;
  await saveConfig();
}

// ---------- skills tab ----------

const SKILL_FIELD_LABELS = {
  chance_base: "โอกาสติดสกิลพื้นฐาน (%)",
  chance_lvl_scale: "โอกาสเพิ่มต่อเลเวล (%)",
  damage_multiplier: "ตัวคูณดาเมจ",
  duration: "ระยะเวลาบัพ (เทิร์น)",
  reduction_base: "% ลดดาเมจพื้นฐาน",
  reduction_lvl_scale: "% ลดดาเมจเพิ่มต่อเลเวล",
  burn_base: "% ดาเมจเผาไหม้พื้นฐาน (จาก HP บอส)",
  burn_lvl_scale: "% ดาเมจเผาไหม้เพิ่มต่อเลเวล",
  duration_base: "ระยะเวลาพื้นฐาน (เทิร์น)",
  duration_lvl_scale: "ระยะเวลาเพิ่มต่อเลเวล",
  damage_reduce: "% หักล้างดาเมจ",
  damage_reflect_mult: "ตัวคูณดาเมจสะท้อนกลับ",
  heal_percent_base: "% ฮีลพื้นฐาน (จาก Max HP)",
  heal_lvl_scale: "% ฮีลเพิ่มต่อเลเวล",
};

const SKILL_LABELS = {
  Warrior: { heavy_strike: "เจาะเกราะสุดพลัง (heavy_strike)", shield_bash: "โล่กระแทก (shield_bash)" },
  Mage: { fireball: "ลูกไฟ (fireball)", frostbolt: "ธนูน้ำแข็ง (frostbolt)" },
  Rogue: { backstab: "แทงข้างหลัง (backstab)", evasion: "หลบหลีก (evasion)" },
  Cleric: { heal: "รักษา (heal)", holy_aura: "ออร่าศักดิ์สิทธิ์ (holy_aura)" },
};

const ROLE_BONUS_TYPES = [
  { value: "voice_exp_multiplier", label: "ตัวคูณ EXP ห้องเสียง" },
  { value: "chat_event_multiplier", label: "ตัวคูณสถิติแชทกิจกรรม" },
  { value: "chat_gold_multiplier", label: "ตัวคูณเงินแชท" },
];

function renderSkillCards() {
  const root = document.getElementById("skillCards");
  root.innerHTML = "";
  const skills = state.config.skills || {};
  for (const className of Object.keys(SKILL_LABELS)) {
    const classSkills = skills[className] || {};
    const classHeader = document.createElement("h3");
    classHeader.textContent = className;
    root.appendChild(classHeader);
    for (const skillKey of Object.keys(SKILL_LABELS[className])) {
      const fields = classSkills[skillKey] || {};
      const card = document.createElement("div");
      card.className = "skill-card";
      card.dataset.class = className;
      card.dataset.skill = skillKey;
      const title = document.createElement("strong");
      title.textContent = SKILL_LABELS[className][skillKey];
      card.appendChild(title);
      for (const fieldKey of Object.keys(fields)) {
        const row = document.createElement("div");
        row.className = "field";
        const label = document.createElement("label");
        label.textContent = SKILL_FIELD_LABELS[fieldKey] || fieldKey;
        const input = document.createElement("input");
        input.type = "number";
        input.step = "any";
        input.className = "skill-field";
        input.dataset.field = fieldKey;
        input.value = fields[fieldKey];
        row.appendChild(label);
        row.appendChild(input);
        card.appendChild(row);
      }
      root.appendChild(card);
    }
  }
}

function roleBonusRoleSelectHtml(selectedId) {
  const sel = document.createElement("select");
  sel.className = "bonus-role";
  sel.innerHTML = '<option value="">-- ไม่ระบุ --</option>';
  for (const r of state.roles) {
    const opt = document.createElement("option");
    opt.value = r.id;
    opt.textContent = r.name;
    sel.appendChild(opt);
  }
  if (selectedId != null) sel.value = String(selectedId);
  return sel;
}

function roleBonusTypeSelectHtml(selectedType) {
  const sel = document.createElement("select");
  sel.className = "bonus-type";
  for (const t of ROLE_BONUS_TYPES) {
    const opt = document.createElement("option");
    opt.value = t.value;
    opt.textContent = t.label;
    sel.appendChild(opt);
  }
  sel.value = selectedType || ROLE_BONUS_TYPES[0].value;
  return sel;
}

function renderRoleBonuses() {
  const tbody = document.querySelector("#roleBonusTable tbody");
  tbody.innerHTML = "";
  const bonuses = state.config.role_bonuses || [];
  bonuses.forEach((item, idx) => {
    const tr = document.createElement("tr");
    tr.dataset.idx = idx;

    const tdLabel = document.createElement("td");
    const labelInput = document.createElement("input");
    labelInput.type = "text";
    labelInput.className = "bonus-label";
    labelInput.value = item.label || "";
    tdLabel.appendChild(labelInput);
    tr.appendChild(tdLabel);

    const tdRole = document.createElement("td");
    const roleSel = roleBonusRoleSelectHtml(item.role_id);
    tdRole.appendChild(roleSel);
    tr.appendChild(tdRole);

    const tdType = document.createElement("td");
    const typeSel = roleBonusTypeSelectHtml(item.bonus_type);
    tdType.appendChild(typeSel);
    tr.appendChild(tdType);

    const tdValue = document.createElement("td");
    const valueInput = document.createElement("input");
    valueInput.type = "number";
    valueInput.step = "any";
    valueInput.className = "bonus-value";
    valueInput.value = item.value != null ? item.value : 1.0;
    tdValue.appendChild(valueInput);
    tr.appendChild(tdValue);

    const tdDel = document.createElement("td");
    const delBtn = document.createElement("button");
    delBtn.type = "button";
    delBtn.textContent = "ลบ";
    delBtn.onclick = () => {
      state.config.role_bonuses.splice(idx, 1);
      renderRoleBonuses();
    };
    tdDel.appendChild(delBtn);
    tr.appendChild(tdDel);

    tbody.appendChild(tr);
  });
}

function renderSkillsTab() {
  renderSkillCards();
  renderRoleBonuses();
}

function addRoleBonusRow() {
  if (!state.config.role_bonuses) state.config.role_bonuses = [];
  state.config.role_bonuses.push({ label: "โบนัสใหม่", role_id: null, bonus_type: ROLE_BONUS_TYPES[0].value, value: 1.0 });
  renderRoleBonuses();
}

async function skillsSave() {
  const skills = state.config.skills || {};
  document.querySelectorAll("#skillCards .skill-card").forEach((card) => {
    const className = card.dataset.class;
    const skillKey = card.dataset.skill;
    const fields = {};
    card.querySelectorAll(".skill-field").forEach((input) => {
      const parsed = parseFloat(input.value);
      fields[input.dataset.field] = isNaN(parsed) ? 0 : parsed;
    });
    if (!skills[className]) skills[className] = {};
    skills[className][skillKey] = fields;
  });
  state.config.skills = skills;

  const tbody = document.querySelector("#roleBonusTable tbody");
  const bonuses = [];
  tbody.querySelectorAll("tr").forEach((tr) => {
    const label = tr.querySelector(".bonus-label").value;
    const role_id = tr.querySelector(".bonus-role").value || null;
    const bonus_type = tr.querySelector(".bonus-type").value;
    const parsedValue = parseFloat(tr.querySelector(".bonus-value").value);
    const value = isNaN(parsedValue) ? 1.0 : parsedValue;
    bonuses.push({ label, role_id, bonus_type, value });
  });
  state.config.role_bonuses = bonuses;

  await saveConfig();
}

// ---------- items tab ----------

const ITEM_TYPES = [
  { value: "use", label: "ใช้ได้ (Consumable)" },
  { value: "armor", label: "เกราะ" },
  { value: "weapon", label: "อาวุธ" },
  { value: "bag", label: "กระเป๋า" },
  { value: "junk", label: "ของเก็บ (Junk)" },
  { value: "drop", label: "ดรอปพิเศษ" },
];

// ⚠️ ต้องมี effect ครบทุกแบบที่เกมรองรับ — เดิมมีแค่ 5 แบบ ทำให้ไอเทม 38 ชิ้นที่ใช้ effect
// นอกลิสต์ถูกล้างค่าทิ้งเงียบ ๆ ทันทีที่กดบันทึกแท็บนี้ (ยาเลิกฮีล อาร์ติแฟกต์เลิกใส่ได้)
const ITEM_EFFECTS = [
  { value: "", label: "-- ไม่มี --" },
  { value: "heal", label: "ฟื้น HP (heal)" },
  { value: "repair", label: "ซ่อมอุปกรณ์ (repair)" },
  { value: "revive", label: "ชุบชีวิต (revive)" },
  { value: "set_state", label: "ตั้งค่าเหตุการณ์ (set_state)" },
  { value: "apply_status", label: "ติดสถานะ (apply_status)" },
  { value: "cure_status", label: "ล้างสถานะ (cure_status)" },
  { value: "equip_artifact", label: "สวมอาร์ติแฟกต์ (equip_artifact)" },
  { value: "artifact_slot_up", label: "💠 เจาะช่องอาร์ติแฟกต์ (artifact_slot_up)" },
  { value: "artifact_remove", label: "🔧 ถอดอาร์ติแฟกต์ (artifact_remove)" },
  { value: "gamble_status", label: "สุ่มสถานะดี/ร้าย (gamble_status)" },
  { value: "emergency_ration", label: "เสบียงฉุกเฉิน (emergency_ration)" },
  { value: "dye_profile", label: "ย้อมสีโปรไฟล์ (dye_profile)" },
  { value: "random_continent", label: "วาร์ปสุ่มทวีป (random_continent)" },
  { value: "choose_continent", label: "เลือกทวีปเอง (choose_continent)" },
  { value: "wedding_ring", label: "💍 แหวนแต่งงาน (wedding_ring)" },
];

function renderItemsCatalog() {
  const cat = state.config.item_catalog || {};
  renderItemsTable(cat.items || {});
  renderKvStatsTable(cat.armor_stats || {}, "armorStatsTable", ["hp", "eva", "dur", "vis"]);
  renderKvStatsTable(cat.weapon_stats || {}, "weaponStatsTable", ["atk", "dur"]);
  renderKvStatsTable(cat.bag_stats || {}, "bagStatsTable", ["capacity"]);
  renderRecipesTable(cat.crafting_recipes || {});
}

function renderItemsTable(items) {
  const tbody = document.querySelector("#itemsTable tbody");
  tbody.innerHTML = "";
  Object.keys(items).forEach((id) => {
    const item = items[id];
    const tr = document.createElement("tr");
    tr.dataset.id = id;

    const tdId = document.createElement("td");
    tdId.textContent = id;
    tr.appendChild(tdId);

    const tdName = document.createElement("td");
    const nameInput = document.createElement("input");
    nameInput.type = "text";
    nameInput.className = "item-name";
    nameInput.value = item.name || "";
    tdName.appendChild(nameInput);
    tr.appendChild(tdName);

    const tdBuy = document.createElement("td");
    const buyInput = document.createElement("input");
    buyInput.type = "number";
    buyInput.className = "item-buy";
    buyInput.value = item.buy != null ? item.buy : 0;
    tdBuy.appendChild(buyInput);
    tr.appendChild(tdBuy);

    const tdSell = document.createElement("td");
    const sellInput = document.createElement("input");
    sellInput.type = "number";
    sellInput.className = "item-sell";
    sellInput.value = item.sell != null ? item.sell : 0;
    tdSell.appendChild(sellInput);
    tr.appendChild(tdSell);

    const tdType = document.createElement("td");
    const typeSel = document.createElement("select");
    typeSel.className = "item-type";
    for (const t of ITEM_TYPES) {
      const opt = document.createElement("option");
      opt.value = t.value;
      opt.textContent = t.label;
      typeSel.appendChild(opt);
    }
    typeSel.value = item.type || "use";
    tdType.appendChild(typeSel);
    tr.appendChild(tdType);

    const tdPurchasable = document.createElement("td");
    const purchasableCb = document.createElement("input");
    purchasableCb.type = "checkbox";
    purchasableCb.className = "item-purchasable";
    purchasableCb.checked = item.purchasable !== false;
    tdPurchasable.appendChild(purchasableCb);
    tr.appendChild(tdPurchasable);

    const tdExtra = document.createElement("td");
    const equipKeyInput = document.createElement("input");
    equipKeyInput.type = "text";
    equipKeyInput.className = "item-equip-key";
    equipKeyInput.placeholder = "equip_key (armor/weapon/bag)";
    equipKeyInput.value = item.equip_key || "";
    const effectSel = document.createElement("select");
    effectSel.className = "item-effect";
    for (const e of ITEM_EFFECTS) {
      const opt = document.createElement("option");
      opt.value = e.value;
      opt.textContent = e.label;
      effectSel.appendChild(opt);
    }
    // effect แปลกที่ไม่มีในลิสต์ (ของที่แอดมินเพิ่มเอง) — ใส่เป็นตัวเลือกไว้ จะได้ไม่โดนล้างตอนบันทึก
    if (item.effect && !ITEM_EFFECTS.some(e => e.value === item.effect)) {
      const custom = document.createElement("option");
      custom.value = item.effect;
      custom.textContent = `${item.effect} (กำหนดเอง)`;
      effectSel.appendChild(custom);
    }
    effectSel.value = item.effect || "";
    const effectValInput = document.createElement("input");
    effectValInput.type = "text";
    effectValInput.className = "item-effect-value";
    effectValInput.placeholder = "effect_amount / effect_value";
    effectValInput.value = item.effect_amount != null ? item.effect_amount : (item.effect_value || "");
    tdExtra.appendChild(equipKeyInput);
    tdExtra.appendChild(effectSel);
    tdExtra.appendChild(effectValInput);
    tr.appendChild(tdExtra);

    const tdDel = document.createElement("td");
    const delBtn = document.createElement("button");
    delBtn.type = "button";
    delBtn.textContent = "ลบ";
    delBtn.onclick = () => {
      delete state.config.item_catalog.items[id];
      renderItemsCatalog();
    };
    tdDel.appendChild(delBtn);
    tr.appendChild(tdDel);

    tbody.appendChild(tr);
  });
}

function addNewItem() {
  if (!state.config.item_catalog) state.config.item_catalog = {};
  if (!state.config.item_catalog.items) state.config.item_catalog.items = {};
  const items = state.config.item_catalog.items;
  let n = 1;
  while (items[String(n)]) n++;
  items[String(n)] = { name: "ไอเทมใหม่", buy: 0, sell: 0, type: "use", purchasable: true };
  renderItemsCatalog();
}

function renderKvStatsTable(statsObj, tableId, fieldNames) {
  const tbody = document.querySelector(`#${tableId} tbody`);
  tbody.innerHTML = "";
  Object.keys(statsObj).forEach((key) => {
    const entry = statsObj[key];
    const tr = document.createElement("tr");
    tr.dataset.key = key;

    const tdKey = document.createElement("td");
    const keyInput = document.createElement("input");
    keyInput.type = "text";
    keyInput.className = "stat-key";
    keyInput.value = key;
    tdKey.appendChild(keyInput);
    tr.appendChild(tdKey);

    const tdName = document.createElement("td");
    const nameInput = document.createElement("input");
    nameInput.type = "text";
    nameInput.className = "stat-name";
    nameInput.value = entry.name || "";
    tdName.appendChild(nameInput);
    tr.appendChild(tdName);

    for (const field of fieldNames) {
      const td = document.createElement("td");
      const input = document.createElement("input");
      input.type = "number";
      input.className = "stat-field";
      input.dataset.field = field;
      input.value = entry[field] != null ? entry[field] : 0;
      td.appendChild(input);
      tr.appendChild(td);
    }

    const tdDel = document.createElement("td");
    const delBtn = document.createElement("button");
    delBtn.type = "button";
    delBtn.textContent = "ลบ";
    delBtn.onclick = () => {
      delete statsObj[key];
      renderItemsCatalog();
    };
    tdDel.appendChild(delBtn);
    tr.appendChild(tdDel);

    tbody.appendChild(tr);
  });
}

function addStatRow(catalogField, tableId, fieldNames) {
  if (!state.config.item_catalog) state.config.item_catalog = {};
  if (!state.config.item_catalog[catalogField]) state.config.item_catalog[catalogField] = {};
  const statsObj = state.config.item_catalog[catalogField];
  let n = 1;
  while (statsObj["new_" + n]) n++;
  const entry = { name: "ใหม่" };
  for (const f of fieldNames) entry[f] = 0;
  statsObj["new_" + n] = entry;
  renderItemsCatalog();
}

function renderRecipesTable(recipes) {
  const tbody = document.querySelector("#recipesTable tbody");
  tbody.innerHTML = "";
  Object.keys(recipes).forEach((itemId) => {
    const r = recipes[itemId];
    const tr = document.createElement("tr");
    tr.dataset.itemId = itemId;

    const tdItem = document.createElement("td");
    const itemIdInput = document.createElement("input");
    itemIdInput.type = "text";
    itemIdInput.className = "recipe-item-id";
    itemIdInput.value = itemId;
    tdItem.appendChild(itemIdInput);
    tr.appendChild(tdItem);

    const tdIngredients = document.createElement("td");
    const ingredientsInput = document.createElement("input");
    ingredientsInput.type = "text";
    ingredientsInput.className = "recipe-ingredients";
    ingredientsInput.value = Object.entries(r.recipe || {}).map(([id, qty]) => `${id}:${qty}`).join(",");
    tdIngredients.appendChild(ingredientsInput);
    tr.appendChild(tdIngredients);

    const tdFail = document.createElement("td");
    const failInput = document.createElement("input");
    failInput.type = "number";
    failInput.step = "any";
    failInput.className = "recipe-fail-rate";
    failInput.value = r.fail_rate != null ? r.fail_rate : 0;
    tdFail.appendChild(failInput);
    tr.appendChild(tdFail);

    const tdDel = document.createElement("td");
    const delBtn = document.createElement("button");
    delBtn.type = "button";
    delBtn.textContent = "ลบ";
    delBtn.onclick = () => {
      delete state.config.item_catalog.crafting_recipes[itemId];
      renderItemsCatalog();
    };
    tdDel.appendChild(delBtn);
    tr.appendChild(tdDel);

    tbody.appendChild(tr);
  });
}

function addRecipeRow() {
  if (!state.config.item_catalog) state.config.item_catalog = {};
  if (!state.config.item_catalog.crafting_recipes) state.config.item_catalog.crafting_recipes = {};
  const recipes = state.config.item_catalog.crafting_recipes;
  let n = 1;
  while (recipes["new_" + n]) n++;
  recipes["new_" + n] = { recipe: {}, fail_rate: 0.1 };
  renderItemsCatalog();
}

function parseIngredients(text) {
  const result = {};
  text.split(",").map((s) => s.trim()).filter(Boolean).forEach((pair) => {
    const [id, qty] = pair.split(":").map((s) => s.trim());
    if (id) {
      const parsedQty = parseInt(qty, 10);
      result[id] = isNaN(parsedQty) ? 1 : parsedQty;
    }
  });
  return result;
}

async function itemsSave() {
  const items = {};
  document.querySelectorAll("#itemsTable tbody tr").forEach((tr) => {
    const id = tr.dataset.id;
    const type = tr.querySelector(".item-type").value;
    const effect = tr.querySelector(".item-effect").value;
    const extraVal = tr.querySelector(".item-effect-value").value;
    const entry = {
      name: tr.querySelector(".item-name").value,
      buy: parseInt(tr.querySelector(".item-buy").value, 10) || 0,
      sell: parseInt(tr.querySelector(".item-sell").value, 10) || 0,
      type,
      purchasable: tr.querySelector(".item-purchasable").checked,
    };
    const equipKey = tr.querySelector(".item-equip-key").value.trim();
    if (["armor", "weapon", "bag"].includes(type) && equipKey) entry.equip_key = equipKey;
    if (effect) {
      entry.effect = effect;
      if (effect === "heal") entry.effect_amount = parseInt(extraVal, 10) || 0;
      if (effect === "set_state") entry.effect_value = extraVal.trim();
    }
    items[id] = entry;
  });

  function collectStats(tableId, fieldNames) {
    const out = {};
    document.querySelectorAll(`#${tableId} tbody tr`).forEach((tr) => {
      const key = tr.querySelector(".stat-key").value.trim();
      if (!key) return;
      const entry = { name: tr.querySelector(".stat-name").value };
      tr.querySelectorAll(".stat-field").forEach((input) => {
        const parsed = parseFloat(input.value);
        entry[input.dataset.field] = isNaN(parsed) ? 0 : parsed;
      });
      out[key] = entry;
    });
    return out;
  }

  const armor_stats = collectStats("armorStatsTable", ["hp", "eva", "dur", "vis"]);
  const weapon_stats = collectStats("weaponStatsTable", ["atk", "dur"]);
  const bag_stats = collectStats("bagStatsTable", ["capacity"]);

  const crafting_recipes = {};
  document.querySelectorAll("#recipesTable tbody tr").forEach((tr) => {
    const itemId = tr.querySelector(".recipe-item-id").value.trim();
    if (!itemId) return;
    const fail = parseFloat(tr.querySelector(".recipe-fail-rate").value);
    crafting_recipes[itemId] = {
      recipe: parseIngredients(tr.querySelector(".recipe-ingredients").value),
      fail_rate: isNaN(fail) ? 0 : fail,
    };
  });

  state.config.item_catalog = { items, armor_stats, weapon_stats, bag_stats, crafting_recipes };
  await saveConfig();
}

// ---------- rank rewards tab ----------

function renderRankRewards() {
  document.getElementById("rankRewardCooldown").value = (state.config.rank_rewards || {}).cooldown_hours ?? 24;
  const tbody = document.querySelector("#rankRewardsTable tbody");
  tbody.innerHTML = "";
  const ranks = (state.config.rank_rewards || {}).ranks || [];
  ranks.forEach((r, idx) => {
    const tr = document.createElement("tr");
    tr.dataset.idx = idx;

    const tdLabel = document.createElement("td");
    const labelInput = document.createElement("input");
    labelInput.type = "text";
    labelInput.className = "rank-label";
    labelInput.value = r.label || "";
    tdLabel.appendChild(labelInput);
    tr.appendChild(tdLabel);

    const tdRole = document.createElement("td");
    const roleSel = roleBonusRoleSelectHtml(r.role_id);
    tdRole.appendChild(roleSel);
    tr.appendChild(tdRole);

    const tdCash = document.createElement("td");
    const cashInput = document.createElement("input");
    cashInput.type = "number";
    cashInput.className = "rank-cash";
    cashInput.value = r.cash || 0;
    tdCash.appendChild(cashInput);
    tr.appendChild(tdCash);

    const tdExp = document.createElement("td");
    const expInput = document.createElement("input");
    expInput.type = "number";
    expInput.className = "rank-exp";
    expInput.value = r.exp || 0;
    tdExp.appendChild(expInput);
    tr.appendChild(tdExp);

    const tdItems = document.createElement("td");
    const itemsInput = document.createElement("input");
    itemsInput.type = "text";
    itemsInput.className = "rank-items";
    itemsInput.value = (r.items || []).map((it) => `${it.item_id}:${it.amount}`).join(",");
    tdItems.appendChild(itemsInput);
    tr.appendChild(tdItems);

    const tdDel = document.createElement("td");
    const delBtn = document.createElement("button");
    delBtn.type = "button";
    delBtn.textContent = "ลบ";
    delBtn.onclick = () => {
      state.config.rank_rewards.ranks.splice(idx, 1);
      renderRankRewards();
    };
    tdDel.appendChild(delBtn);
    tr.appendChild(tdDel);

    tbody.appendChild(tr);
  });
}

function addRankRewardRow() {
  if (!state.config.rank_rewards) state.config.rank_rewards = { cooldown_hours: 24, ranks: [] };
  if (!state.config.rank_rewards.ranks) state.config.rank_rewards.ranks = [];
  state.config.rank_rewards.ranks.push({ label: "ยศใหม่", role_id: null, cash: 0, exp: 0, items: [] });
  renderRankRewards();
}

async function rankRewardsSave() {
  const cooldown = parseFloat(document.getElementById("rankRewardCooldown").value);
  const ranks = [];
  document.querySelectorAll("#rankRewardsTable tbody tr").forEach((tr) => {
    const items = [];
    const parsed = parseIngredients(tr.querySelector(".rank-items").value);
    Object.entries(parsed).forEach(([item_id, amount]) => items.push({ item_id, amount }));
    ranks.push({
      label: tr.querySelector(".rank-label").value,
      role_id: tr.querySelector(".bonus-role").value || null,
      cash: parseInt(tr.querySelector(".rank-cash").value, 10) || 0,
      exp: parseInt(tr.querySelector(".rank-exp").value, 10) || 0,
      items,
    });
  });
  state.config.rank_rewards = { cooldown_hours: isNaN(cooldown) ? 24 : cooldown, ranks };
  await saveConfig();
}

// ---------- payment tab ----------

function renderPayment() {
  const p = state.config.payment || {};
  document.getElementById("paymentCurrency").value = p.currency || "THB";
  document.getElementById("paymentExchangeRate").value = p.exchange_rate ?? 1;
  document.getElementById("paymentMinAmount").value = p.min_amount ?? 0;
  document.getElementById("paymentMaxAmount").value = p.max_amount ?? 0;
  const pp = p.promptpay || {};
  document.getElementById("promptpayEnabled").checked = !!pp.enabled;
  document.getElementById("promptpayId").value = pp.id || "";
  document.getElementById("promptpayName").value = pp.name || "";
  const paypal = p.paypal || {};
  document.getElementById("paypalEnabled").checked = !!paypal.enabled;
  document.getElementById("paypalLink").value = paypal.link || "";
  const tm = p.truemoney || {};
  document.getElementById("truemoneyEnabled").checked = !!tm.enabled;
  document.getElementById("truemoneyPhone").value = tm.phone || "";
}

async function paymentSave() {
  state.config.payment = {
    currency: document.getElementById("paymentCurrency").value.trim() || "THB",
    exchange_rate: parseFloat(document.getElementById("paymentExchangeRate").value) || 0,
    min_amount: parseFloat(document.getElementById("paymentMinAmount").value) || 0,
    max_amount: parseFloat(document.getElementById("paymentMaxAmount").value) || 0,
    promptpay: {
      enabled: document.getElementById("promptpayEnabled").checked,
      id: document.getElementById("promptpayId").value.trim(),
      name: document.getElementById("promptpayName").value.trim(),
    },
    paypal: {
      enabled: document.getElementById("paypalEnabled").checked,
      link: document.getElementById("paypalLink").value.trim(),
    },
    truemoney: {
      enabled: document.getElementById("truemoneyEnabled").checked,
      phone: document.getElementById("truemoneyPhone").value.trim(),
    },
  };
  await saveConfig();
}

// ---------- images tab (🖼️ event_images) ----------

function renderImagesToggle() {
  const ei = state.config.event_images || {};
  document.getElementById("eventImagesEnabled").checked = ei.enabled !== false;
}

async function imagesSave() {
  state.config.event_images = { enabled: document.getElementById("eventImagesEnabled").checked };
  await saveConfig();
}

let imageRows = [];

async function loadImageList() {
  try {
    imageRows = (await api("GET", "/api/event-images")).images || [];
  } catch (e) {
    imageRows = []; // โฟลเดอร์ภาพยังไม่มี/อ่านไม่ได้ — โชว์ตารางว่างพอ ไม่ต้องพังทั้งหน้า
  }
  renderImageTable();
}

function renderImageTable() {
  const q = document.getElementById("imageFilter").value.trim().toLowerCase();
  const tbody = document.querySelector("#imagesTable tbody");
  tbody.innerHTML = "";
  imageRows.filter((r) => !q || r.key.includes(q)).forEach((r) => {
    const tr = document.createElement("tr");
    const bust = r.bust ? `?t=${r.bust}` : "";
    tr.innerHTML = `
      <td><img src="/api/event-images/${r.key}${bust}" loading="lazy" alt="${r.key}"
               style="width:56px;height:56px;image-rendering:pixelated;border-radius:4px"></td>
      <td><code>${r.key}</code></td>
      <td>${Math.round(r.size / 1024)} KB</td>
      <td><button class="img-upload-btn" data-key="${r.key}">📤 อัพโหลดแทน</button></td>`;
    tbody.appendChild(tr);
  });
  tbody.querySelectorAll(".img-upload-btn").forEach((b) => {
    b.addEventListener("click", () => pickImageFor(b.dataset.key));
  });
}

function pickImageFor(key) {
  const input = document.getElementById("imageUploadInput");
  input.onchange = async () => {
    const file = input.files[0];
    input.value = "";
    if (!file) return;
    try {
      // ส่ง raw bytes ตรงๆ (ไม่ใช่ multipart) — ฝั่ง server อ่านจาก request.body
      const res = await fetch(`/api/event-images/${key}`, { method: "POST", body: file });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "อัพโหลดไม่สำเร็จ");
      const row = imageRows.find((r) => r.key === key);
      if (row) { row.size = data.size || row.size; row.bust = Date.now(); }
      renderImageTable();
      toast(`เปลี่ยนภาพ ${key} แล้ว — มีผลในเกมทันที`);
    } catch (e) {
      alert(`อัพโหลดภาพ ${key} ไม่สำเร็จ: ${e.message}`);
    }
  };
  input.click();
}

// ---------- tabs ----------

function switchTab(name) {
  document.querySelectorAll(".tab-btn").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  document.querySelectorAll(".tab-panel").forEach((p) => p.classList.toggle("active", p.id === "tab-" + name));
}

// ---------- init ----------

async function init() {
  document.querySelectorAll(".tab-btn").forEach((b) => {
    b.addEventListener("click", () => switchTab(b.dataset.tab));
  });

  document.getElementById("verifyBtn").addEventListener("click", verifyToken);
  document.getElementById("guildSelect").addEventListener("change", onGuildChange);
  document.getElementById("setupSaveBtn").addEventListener("click", setupSave);
  document.getElementById("balanceSaveBtn").addEventListener("click", balanceSave);
  document.getElementById("retentionSaveBtn").addEventListener("click", retentionSave);

  document.getElementById("startBtn").addEventListener("click", startBot);
  document.getElementById("stopBtn").addEventListener("click", stopBot);
  document.getElementById("restartBtn").addEventListener("click", restartBot);

  document.getElementById("channelsSaveBtn").addEventListener("click", channelsSave);
  document.getElementById("permissionsSaveBtn").addEventListener("click", permissionsSave);

  document.getElementById("darkAddBtn").addEventListener("click", () => addTradeRow("dark"));
  document.getElementById("lightAddBtn").addEventListener("click", () => addTradeRow("light"));
  document.getElementById("tradeSaveBtn").addEventListener("click", tradeSave);

  document.getElementById("shopAddBtn").addEventListener("click", addShopRow);
  document.getElementById("shopSaveBtn").addEventListener("click", shopSave);

  document.getElementById("roleBonusAddBtn").addEventListener("click", addRoleBonusRow);
  document.getElementById("skillsSaveBtn").addEventListener("click", skillsSave);

  document.getElementById("itemAddBtn").addEventListener("click", addNewItem);
  document.getElementById("armorStatAddBtn").addEventListener("click", () => addStatRow("armor_stats", "armorStatsTable", ["hp", "eva", "dur", "vis"]));
  document.getElementById("weaponStatAddBtn").addEventListener("click", () => addStatRow("weapon_stats", "weaponStatsTable", ["atk", "dur"]));
  document.getElementById("bagStatAddBtn").addEventListener("click", () => addStatRow("bag_stats", "bagStatsTable", ["capacity"]));
  document.getElementById("recipeAddBtn").addEventListener("click", addRecipeRow);
  document.getElementById("itemsSaveBtn").addEventListener("click", itemsSave);

  document.getElementById("rankRewardAddBtn").addEventListener("click", addRankRewardRow);
  document.getElementById("rankRewardsSaveBtn").addEventListener("click", rankRewardsSave);
  document.getElementById("paymentSaveBtn").addEventListener("click", paymentSave);
  document.getElementById("imagesSaveBtn").addEventListener("click", imagesSave);
  document.getElementById("imageFilter").addEventListener("input", renderImageTable);

  try {
    const v = await api("GET", "/api/version");
    document.getElementById("versionBadge").textContent = "v" + v.version;
  } catch (e) {
    // ไม่ใช่ตัวบล็อกการทำงาน แค่แสดงเลขเวอร์ชันเฉยๆ
  }

  await loadConfig();
  document.getElementById("tokenInput").value = state.config.bot_token || "";
  document.getElementById("licenseKeyInput").value = state.config.license_key || "";
  document.getElementById("guestTokenInput").value = state.config.guest_bot_token || "";
  document.getElementById("mainGuildIdInput").value = state.config.main_guild_id || "";
  document.getElementById("mainInviteInput").value = state.config.main_server_invite || "";

  // best-effort auto-restore: if a token + guild are already configured,
  // silently fetch guilds/channels/roles so tabs are pre-populated.
  if (state.config.bot_token) {
    try {
      state.guilds = await api("GET", "/api/discord/guilds");
      fillGuildSelect();
      if (state.config.guild_id != null) {
        await onGuildChange();
      }
    } catch (e) {
      // token may be invalid/expired; user can re-verify manually
    }
  }

  renderChannels();
  renderPermissions();
  renderTrade();
  renderShop();
  renderSkillsTab();
  renderItemsCatalog();
  renderRankRewards();
  renderPayment();
  renderImagesToggle();
  loadImageList();

  // Dashboard ต้องขึ้นเสมอ — แท็บอื่นพังไม่ควรทำให้สถานะบอท/ล็อกหายไปทั้งหน้า
  await refreshStatus();
  setInterval(refreshStatus, 1500);
  setInterval(pollLog, 1500);
  pollLog();

  // แท็บพวกนี้พังต้องไม่ลากทั้งหน้าไปด้วย (เคยเจอมาแล้ว — แดชบอร์ดจอดำทั้งหน้า)
  for (const [name, fn] of [["Balance", renderBalance], ["Retention", renderRetention]]) {
    try {
      fn();
    } catch (e) {
      console.error(`render${name} ล้มเหลว:`, e);
      toast(`แท็บ ${name} โหลดไม่ได้ (ดู console) — ส่วนอื่นใช้งานได้ปกติ`);
    }
  }
}

document.addEventListener("DOMContentLoaded", init);

// ---------- ⚖️ balance tab (กลุ่ม A: ค่าที่เคยฟิกในโค้ด) ----------

const BAL_FIELDS = {
  balGuild: [
    ["guild.create_cost", "ค่าก่อตั้งกิลด์ (ทองสด)"],
    ["guild.rename_cost", "ค่าเปลี่ยนชื่อกิลด์"],
  ],
  balGuildWar: [
    ["guild_war.duration_min", "ระยะเวลาศึก (นาที)"],
    ["guild_war.idle_warn_sec", "เงียบกี่วินาทีถึงเตือน"],
    ["guild_war.idle_grace_sec", "หลังเตือน รออีกกี่วินาทีถึงจบ"],
    ["guild_war.fight_cooldown_sec", "คูลดาวน์ !fight (วิ)"],
    ["guild_war.chances.soldier", "โอกาสเจอทหาร %"],
    ["guild_war.chances.leader", "โอกาสเจอหัวหน้า %"],
    ["guild_war.chances.fort", "โอกาสเจอป้อม %"],
    ["guild_war.chances.castle", "โอกาสเจอปราสาท %"],
    ["guild_war.points.soldier", "แต้มล้มทหาร"],
    ["guild_war.points.leader", "แต้มล้มหัวหน้า"],
    ["guild_war.points.fort", "แต้มทำลายป้อม (ติดลบ=หักศัตรู)"],
    ["guild_war.points.castle", "แต้มทำลายปราสาท"],
  ],
  balPvp: [
    ["pvp.min_level", "เลเวลขั้นต่ำที่ PvP ได้"],
    ["pvp.reward_exp_base", "EXP ฐานเมื่อฆ่าสำเร็จ"],
    ["pvp.reward_exp_per_level", "EXP ต่อเลเวลเหยื่อ"],
    ["pvp.reward_gold_base", "ทองฐานเมื่อฆ่าสำเร็จ"],
    ["pvp.reward_gold_per_level", "ทองต่อเลเวลเหยื่อ"],
    ["pvp.kill_cooldown_min_sec", "คูลดาวน์หลังฆ่า ต่ำสุด (วิ)"],
    ["pvp.kill_cooldown_max_sec", "คูลดาวน์หลังฆ่า สูงสุด (วิ)"],
    ["pvp.sanity_loss_base", "สติที่เสียต่อครั้ง (ฐาน)"],
    ["pvp.sanity_loss_per_level", "สติที่เสียต่อเลเวลผู้โจมตี"],
    ["pvp.jail_base_min", "ติดคุกฐาน (นาที)"],
    ["pvp.jail_per_deficit_min", "ติดคุกเพิ่มต่อสติติดลบ 1"],
    ["pvp.fine_base", "ค่าปรับวิสามัญ (ฐาน)"],
    ["pvp.fine_per_deficit", "ค่าปรับเพิ่มต่อสติติดลบ 1"],
  ],
  balRewards: [
    ["bounty.base", "ค่าหัวฐาน"],
    ["bounty.per_deficit", "ค่าหัวเพิ่มต่อสติติดลบ 1"],
    ["bounty.cap", "เพดานค่าหัว"],
    ["bounty.hunt_sanity_reward", "สติที่ได้คืนเมื่อล่าโจรสำเร็จ"],
    ["bestiary.continent_reward", "รางวัลสมุดครบ 1 ทวีป"],
    ["bestiary.star_reward", "รางวัลดาวไร้พ่าย"],
    ["bestiary.complete_reward", "รางวัลสมุดครบทั้งเล่ม"],
    ["artifact.max_slots", "🏺 ช่องอาร์ติแฟกต์สูงสุด (เจาะได้กี่รู)"],
    ["artifact.punch_drop_chance", "💠 โอกาสดรอปสว่านเจาะรูจากบอสไร้พ่าย %"],
    ["bestiary.element_rank_rewards.Common", "🧬 สมุดธาตุ: ครบมอนธรรมดา 7 ธาตุ"],
    ["bestiary.element_rank_rewards.Mini-Boss", "🧬 สมุดธาตุ: ครบมินิบอส 7 ธาตุ"],
    ["bestiary.element_rank_rewards.Main-Boss", "🧬 สมุดธาตุ: ครบบอสใหญ่ 7 ธาตุ"],
    ["bestiary.element_rank_rewards.Secret", "🧬 สมุดธาตุ: ครบมอนลับ 7 ธาตุ"],
    ["bestiary.element_rank_rewards.Unbeatable", "🧬 สมุดธาตุ: ครบไร้พ่าย 7 ธาตุ"],
    ["faction_war.gold_mult", "สงครามฝ่าย: ตัวคูณทอง"],
    ["faction_war.exp_mult", "สงครามฝ่าย: ตัวคูณ EXP"],
    ["faction_war.encounter_chance", "โอกาสเจอแชมเปี้ยน %"],
  ],
  balMisc: [
    ["drops.normal_chance", "โอกาสดรอปของทั่วไป %"],
    ["drops.rare_chance", "โอกาสดรอปของหายาก %"],
    ["drops.respawn_hp_percent", "HP ที่ได้ตอนฟื้นจากตาย %"],
    ["events.travel_chance", "โอกาสเจอพาหนะข้ามทวีป %"],
    ["events.calm_chance", "โอกาสเจออีเวนต์สงบ %"],
    ["element_flee_chance.light", "✨ มอนธาตุแสง: โอกาสหนีต่อเทิร์น %"],
    ["element_flee_chance.dark", "🌑 มอนธาตุมืด: โอกาสหนี %"],
    ["element_flee_chance.fire", "🔥 มอนธาตุไฟ: โอกาสหนี %"],
    ["element_flee_chance.water", "💧 มอนธาตุน้ำ: โอกาสหนี %"],
    ["element_flee_chance.earth", "🪨 มอนธาตุดิน: โอกาสหนี %"],
    ["element_flee_chance.wind", "💨 มอนธาตุลม: โอกาสหนี %"],
    ["element_flee_chance.wood", "🌿 มอนธาตุไม้: โอกาสหนี %"],
    ["cooldowns.play_sec", "คูลดาวน์ !play (วิ)"],
    ["cooldowns.profile_sec", "คูลดาวน์ !profile (วิ)"],
    ["cooldowns.adv_sec", "คูลดาวน์ !adv (วิ)"],
    ["cooldowns.shop_sec", "คูลดาวน์ !shop (วิ)"],
    ["village.rest_cost", "ค่าพักแรมในหมู่บ้าน"],
    ["village.rest_cost_per_level", "ค่าพักแรมเพิ่มต่อเลเวล (0 = คิดเท่ากันทุกเลเวล)"],
    ["village.heal_fee", "ค่ารักษาของนักบวช (!heal)"],
    ["death.force_respawn_fee", "(ไม่ใช้แล้ว — ค่าชุบใช้ตารางตามเลเวล)"],
    ["weekly_tax.enabled", "🏛️ ภาษีรวยรายสัปดาห์ (1=เปิด 0=ปิด)"],
    ["weekly_tax.share_90_pct", "🏛️ ถือ ≥90% ของเซิร์ฟ: หักภาษี %"],
    ["weekly_tax.share_75_pct", "🏛️ ถือ ≥75%: หักภาษี %"],
    ["weekly_tax.share_50_pct", "🏛️ ถือ ≥50%: หักภาษี %"],
  ],
  balExtra: [
    ["new_player.cash", "ผู้เล่นใหม่: ทองเริ่มต้น"],
    ["new_player.capacity", "ผู้เล่นใหม่: ช่องกระเป๋า"],
    ["new_player.max_hp", "ผู้เล่นใหม่: HP สูงสุด"],
    ["new_player.hp", "ผู้เล่นใหม่: HP เริ่มต้น"],
    ["new_player.sanity", "ผู้เล่นใหม่: สติ"],
    ["duel.rounds", "ประลอง !challenge: จำนวนยก"],
    ["duel.bet", "ประลอง !challenge: เงินเดิมพัน"],
  ],
};

const BAL_RANK_COLS = ["dice_count", "hp_min", "hp_max", "flee_chance", "gold_mult", "exp_reward"];

function balGet(path) {
  let node = state.config.game_balance || {};
  for (const k of path.split(".")) {
    if (node == null || typeof node !== "object") return "";
    node = node[k];
  }
  return node == null ? "" : node;
}

function balSet(path, value) {
  if (!state.config.game_balance) state.config.game_balance = {};
  const keys = path.split(".");
  let node = state.config.game_balance;
  for (const k of keys.slice(0, -1)) {
    if (typeof node[k] !== "object" || node[k] == null) node[k] = {};
    node = node[k];
  }
  node[keys[keys.length - 1]] = value === "" ? null : Number(value);
}

function balSetRaw(path, value) {
  /* เขียนค่าที่ไม่ใช่ตัวเลข (เช่น object ทั้งแถวของตาราง) ลง game_balance */
  if (!state.config.game_balance) state.config.game_balance = {};
  const keys = path.split(".");
  let node = state.config.game_balance;
  for (const k of keys.slice(0, -1)) {
    if (typeof node[k] !== "object" || node[k] == null) node[k] = {};
    node = node[k];
  }
  node[keys[keys.length - 1]] = value;
}

function renderBalance() {
  for (const [containerId, fields] of Object.entries(BAL_FIELDS)) {
    const box = document.getElementById(containerId);
    if (!box) continue;
    box.innerHTML = fields.map(([path, label]) =>
      `<label>${label}<input type="number" step="any" data-bal="${path}" value="${balGet(path)}"></label>`
    ).join("");
  }
  // ยศสำคัญ — ใช้ dropdown ยศเดียวกับแท็บอื่น
  const roleFields = [["balRoleKing", "king_role_id"], ["balRoleDivider", "guild_divider_role_id"],
                      ["balRoleLeader", "guild_leader_role_id"]];
  for (const [elId, key] of roleFields) {
    const el = document.getElementById(elId);
    if (!el) continue;
    // roleSelectHtml คืน "อิลิเมนต์" ไม่ใช่สตริง — ต้อง appendChild (เคยเรียก .replace แล้วหน้าพังทั้งหน้า)
    const sel = roleSelectHtml(balGet(`roles.${key}`) || null);
    sel.dataset.balRole = key;
    el.innerHTML = "";
    el.appendChild(sel);
  }
  renderEventWeights();
  renderSpawnTable();
  renderStatusTable();
  // ตารางแรงค์มอนสเตอร์
  const tbody = document.querySelector("#balRanksTable tbody");
  if (tbody) {
    const ranks = state.config.monster_ranks || {};
    tbody.innerHTML = Object.entries(ranks).map(([name, r]) =>
      `<tr><td>${name}</td>` + BAL_RANK_COLS.map(c =>
        `<td><input type="number" step="any" data-rank="${name}" data-col="${c}" value="${r[c] ?? ""}"></td>`).join("") + "</tr>"
    ).join("");
  }
}

// ── ตารางน้ำหนักอีเวนต์ + ตารางสถานะ (ตารางใหญ่ในแท็บ Balance) ──

const EVENT_COLS = ["monster", "village", "treasure", "dungeon", "npc", "trap"];
const EVENT_ROW_LABEL = {
  village: "🏡 หมู่บ้าน", dungeon_inside: "💀 ในดันเจี้ยน", monster: "👹 มอนสเตอร์",
  treasure: "💰 หีบสมบัติ", npc: "🧙 NPC", trap: "⚠️ กับดัก", none: "🚶 เริ่มใหม่/ไม่มี",
};

function renderEventWeights() {
  const tbody = document.querySelector("#balEventsTable tbody");
  if (!tbody) return;
  const rows = balGet("events.weights") || {};
  tbody.innerHTML = Object.keys(EVENT_ROW_LABEL).filter(k => rows[k]).map(situation =>
    `<tr><td>${EVENT_ROW_LABEL[situation]}</td>` + EVENT_COLS.map(col =>
      `<td><input type="number" min="0" data-evt="${situation}" data-col="${col}"
        value="${rows[situation][col] ?? 0}"></td>`).join("") + "</tr>"
  ).join("");
}

const SPAWN_RANKS = ["Common", "Mini-Boss", "Main-Boss", "Secret", "Unbeatable"];

function renderSpawnTable() {
  const tbody = document.querySelector("#balSpawnTable tbody");
  if (!tbody) return;
  const rows = balGet("spawn_weights") || {};
  const levels = Object.keys(rows).sort((a, b) => Number(b) - Number(a));
  tbody.innerHTML = levels.map(lv =>
    `<tr><td>เลเวล ${lv}+</td>` + SPAWN_RANKS.map(rank =>
      `<td><input type="number" min="0" data-spawn="${lv}" data-col="${rank}"
        value="${rows[lv][rank] ?? 0}"></td>`).join("") + "</tr>"
  ).join("");
}

function renderStatusTable() {
  const tbody = document.querySelector("#balStatusTable tbody");
  if (!tbody) return;
  const rows = balGet("status_overrides") || {};
  tbody.innerHTML = Object.entries(rows).map(([key, s]) => {
    const cell = (col) => `<td><input type="number" min="0" data-status="${key}" data-col="${col}"
        value="${s[col] ?? ""}" ${s.dmg_min === undefined && col.startsWith("dmg") ? 'placeholder="—" disabled' : ""}></td>`;
    return `<tr><td>${s.label || key}</td>${cell("turns")}<td>${s.unit || "ก้าว"}</td>${cell("dmg_min")}${cell("dmg_max")}</tr>`;
  }).join("");
}

async function balanceSave() {
  document.querySelectorAll("[data-evt]").forEach(inp => {
    const row = balGet(`events.weights.${inp.dataset.evt}`) || {};
    row[inp.dataset.col] = Number(inp.value || 0);
    balSetRaw(`events.weights.${inp.dataset.evt}`, row);
  });
  document.querySelectorAll("[data-spawn]").forEach(inp => {
    const row = balGet(`spawn_weights.${inp.dataset.spawn}`) || {};
    row[inp.dataset.col] = Number(inp.value || 0);
    balSetRaw(`spawn_weights.${inp.dataset.spawn}`, row);
  });
  document.querySelectorAll("[data-status]").forEach(inp => {
    if (inp.disabled || inp.value === "") return;
    const row = balGet(`status_overrides.${inp.dataset.status}`) || {};
    row[inp.dataset.col] = Number(inp.value);
    balSetRaw(`status_overrides.${inp.dataset.status}`, row);
  });
  document.querySelectorAll("[data-bal]").forEach(inp => balSet(inp.dataset.bal, inp.value));
  document.querySelectorAll("[data-bal-role]").forEach(sel => {
    if (!state.config.game_balance) state.config.game_balance = {};
    if (!state.config.game_balance.roles) state.config.game_balance.roles = {};
    // ไอดียศเป็น snowflake เหมือนกัน — ห้ามแปลงเป็น Number (จะปัดเศษหลักท้าย)
    state.config.game_balance.roles[sel.dataset.balRole] = sel.value || null;
  });
  document.querySelectorAll("[data-rank]").forEach(inp => {
    if (!state.config.monster_ranks) state.config.monster_ranks = {};
    const r = state.config.monster_ranks[inp.dataset.rank] || (state.config.monster_ranks[inp.dataset.rank] = {});
    if (inp.value !== "") r[inp.dataset.col] = Number(inp.value);
  });
  await saveConfig();
}

// ---------- 🎮 retention tab (กลุ่ม C: เควส/ซีซั่น/อันดับ/ความสำเร็จ/สัตว์เลี้ยง/ตลาด/คู่หู) ----------
// ทุกหมวดอ่าน-เขียนที่ "รากของ config" (ไม่ใช่ game_balance) จึงมี helper แยกจากแท็บ Balance

function cfgGet(path, root) {
  let node = root || state.config || {};
  for (const k of path.split(".")) {
    if (node == null || typeof node !== "object") return undefined;
    node = node[k];
  }
  return node;
}

function cfgSet(path, value) {
  const keys = path.split(".");
  let node = state.config;
  for (const k of keys.slice(0, -1)) {
    if (typeof node[k] !== "object" || node[k] == null) node[k] = {};
    node = node[k];
  }
  node[keys[keys.length - 1]] = value;
}

// ค่าเดี่ยว ๆ — [path, label, type] (type: number ค่าเริ่มต้น | text | bool)
const CFG_FIELDS = {
  retDailyMisc: [
    ["daily_quests.all_clear_bonus.gold", "โบนัสเคลียร์ครบทุกภารกิจ: ทอง"],
    ["daily_quests.all_clear_bonus.exp", "โบนัสเคลียร์ครบทุกภารกิจ: EXP"],
    ["daily_quests.streak_daily_gold", "ทองที่ได้ตอนเช็คอินวันใหม่"],
  ],
  retSeasonMisc: [
    ["season_pass.enabled", "เปิดใช้ซีซั่นพาส", "bool"],
    ["season_pass.price_gold", "ราคาสายพรีเมียม (ทองสด)"],
  ],
  retWeeklyMisc: [
    ["weekly_ranking.enabled", "เปิดใช้อันดับรายสัปดาห์", "bool"],
    ["weekly_ranking.min_points", "แต้มขั้นต่ำถึงมีสิทธิ์รับรางวัล"],
  ],
  retPetChance: [
    ["pets.tame_chance.Common", "โอกาสจับจากมอนธรรมดา %"],
    ["pets.tame_chance.Mini-Boss", "โอกาสจับจากมินิบอส %"],
    ["pets.tame_chance.Main-Boss", "โอกาสจับจากบอสใหญ่ %"],
    ["pets.tame_chance.Secret", "โอกาสจับจากมอนลับ %"],
    ["pets.tame_chance.Unbeatable", "โอกาสจับจากไร้พ่าย %"],
  ],
  retMarketPartner: [
    ["market.enabled", "เปิดใช้ตลาดผู้เล่น", "bool"],
    ["market.tax_percent", "ค่าธรรมเนียมตลาด % (หักจากคนขาย)"],
    ["market.min_price", "ราคาต่ำสุดที่ลงขายได้"],
    ["market.max_price", "ราคาสูงสุดที่ลงขายได้"],
    ["market.max_listings_per_player", "ลงขายได้สูงสุดกี่รายการต่อคน"],
    ["partner.ring_item", "เลขไอเทมแหวนแต่งงาน (เว้นว่าง = ไม่ต้องใช้แหวน)", "text"],
    ["partner.wedding_cost", "ค่าจัดงานคู่หู (คนละเท่านี้)"],
    ["partner.divorce_cost", "ค่าดำเนินการหย่า"],
    ["partner.solo_bonus_percent", "โบนัสตอนมีคู่ %"],
    ["partner.together_bonus_percent", "โบนัสตอนคู่เล่นวันเดียวกัน %"],
  ],
};

// ตารางแถวซ้ำ — cols: [คีย์ในแถว, ชนิด, อ่านอย่างเดียว?]
const ROW_TABLES = {
  retDailyQuests: { path: "daily_quests.quests", cols: [
    ["key", "text", true], ["label", "text"], ["target", "number"], ["gold", "number"], ["exp", "number"]] },
  retStreak: { path: "daily_quests.streak_rewards", cols: [
    ["day", "number"], ["gold", "number"], ["item", "text"]] },
  retWeeklyRewards: { path: "weekly_ranking.rewards", cols: [["gold", "number"], ["exp", "number"]],
    rowLabel: i => ["🥇 อันดับ 1", "🥈 อันดับ 2", "🥉 อันดับ 3"][i] || `อันดับ ${i + 1}` },
  retSeasonTiers: { path: "season_pass.tiers", cols: [
    ["points", "number"], ["free.gold", "number"], ["free.exp", "number"], ["free.item", "text"],
    ["premium.gold", "number"], ["premium.exp", "number"], ["premium.item", "text"]],
    rowLabel: i => `ขั้น ${i + 1}` },
  retAchievements: { path: "achievements", cols: [
    ["key", "text", true], ["label", "text"], ["desc", "text"], ["stat", "text", true],
    ["target", "number"], ["gold", "number"], ["title", "text"]] },
  retPets: { path: "pets.list", cols: [
    ["key", "text", true], ["name", "text"], ["desc", "text"], ["from_rank", "text", true], ["dice", "number"]] },
};

function renderRetention() {
  for (const [boxId, fields] of Object.entries(CFG_FIELDS)) {
    const box = document.getElementById(boxId);
    if (!box) continue;
    box.innerHTML = fields.map(([path, label, type]) => {
      const v = cfgGet(path);
      if (type === "bool") {
        return `<label>${label}<select data-cfg="${path}" data-type="bool">
          <option value="1"${v ? " selected" : ""}>เปิด</option>
          <option value="0"${v ? "" : " selected"}>ปิด</option></select></label>`;
      }
      return `<label>${label}<input type="${type === "text" ? "text" : "number"}" step="any"
        data-cfg="${path}" data-type="${type || "number"}" value="${v ?? ""}"></label>`;
    }).join("");
  }

  for (const [tableId, spec] of Object.entries(ROW_TABLES)) {
    const tbody = document.querySelector(`#${tableId} tbody`);
    if (!tbody) continue;
    const rows = cfgGet(spec.path) || [];
    tbody.innerHTML = rows.map((row, i) => {
      const lead = spec.rowLabel ? `<td>${spec.rowLabel(i)}</td>` : "";
      return `<tr>${lead}` + spec.cols.map(([col, type, ro]) =>
        `<td><input type="${type === "text" ? "text" : "number"}" step="any"
          data-table="${tableId}" data-i="${i}" data-col="${col}" data-type="${type}"
          value="${cfgGet(col, row) ?? ""}"${ro ? " readonly class=\"ro\"" : ""}></td>`).join("") + "</tr>";
    }).join("");
  }
}

async function retentionSave() {
  document.querySelectorAll("[data-cfg]").forEach(inp => {
    const t = inp.dataset.type;
    if (t === "bool") return cfgSet(inp.dataset.cfg, inp.value === "1");
    if (t === "text") return cfgSet(inp.dataset.cfg, inp.value.trim() || null);
    cfgSet(inp.dataset.cfg, inp.value === "" ? null : Number(inp.value));
  });

  document.querySelectorAll("[data-table]").forEach(inp => {
    const spec = ROW_TABLES[inp.dataset.table];
    const rows = cfgGet(spec.path);
    if (!Array.isArray(rows)) return;
    const row = rows[Number(inp.dataset.i)];
    if (!row) return;
    const value = inp.dataset.type === "text"
      ? (inp.value.trim() || null)
      : (inp.value === "" ? null : Number(inp.value));
    // คีย์แบบ "free.gold" = เขียนซ้อนชั้นเข้าไปในแถว
    const keys = inp.dataset.col.split(".");
    let node = row;
    for (const k of keys.slice(0, -1)) {
      if (typeof node[k] !== "object" || node[k] == null) node[k] = {};
      node = node[k];
    }
    node[keys[keys.length - 1]] = value;
  });

  await saveConfig();
}
