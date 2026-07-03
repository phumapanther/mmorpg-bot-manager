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
}

async function setupSave() {
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

  await loadConfig();
  document.getElementById("tokenInput").value = state.config.bot_token || "";

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

  await refreshStatus();
  setInterval(refreshStatus, 1500);
  setInterval(pollLog, 1500);
  pollLog();
}

document.addEventListener("DOMContentLoaded", init);
