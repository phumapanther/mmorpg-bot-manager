// วงจรจริงของแท็บ Retention: config → render → ผู้ใช้แก้ช่อง → save → config ใหม่
// รันด้วย node (เรียกจาก tests/test_panel_retention_tab.py) — จับเคส path ผิด/คอลัมน์ผิดที่เทสข้อความจับไม่ได้
import fs from "node:fs";
import assert from "node:assert";

const src = fs.readFileSync("panel/static/app.js", "utf8");
const cfg = JSON.parse(fs.readFileSync("config.example.json", "utf8"));

// ── DOM จำลองเท่าที่โค้ดใช้จริง ──
const nodes = [];
class El {
  constructor(id) {
    this.id = id; this._html = ""; this.inputs = []; this.textContent = "";
    this.classList = { add() {}, remove() {} };     // toast() ใช้
  }
  set innerHTML(v) {
    this._html = v;
    this.inputs = [...v.matchAll(/<(input|select|option)\b([^>]*)>/g)].map(m => {
      const attrs = {};
      for (const a of m[2].matchAll(/([\w-]+)="([^"]*)"/g)) attrs[a[1]] = a[2];
      const el = { tag: m[1], dataset: {}, disabled: /\bdisabled\b/.test(m[2]), value: attrs.value ?? "" };
      for (const [k, v] of Object.entries(attrs)) {
        if (k.startsWith("data-")) {
          el.dataset[k.slice(5).replace(/-(\w)/g, (_, c) => c.toUpperCase())] = v;
        }
      }
      return el;
    });
    // <select> เก็บค่าที่ selected ไว้ใน option — ยุบให้เหลือ element เดียวเหมือน DOM จริง
    if (v.includes("<select")) {
      const sel = this.inputs.find(i => i.tag === "select");
      if (sel) {
        const chosen = /<option value="1" selected>/.test(v) ? "1" : "0";
        sel.value = chosen;
        this.inputs = this.inputs.filter(i => i.tag !== "option");
      }
    }
    if (!nodes.includes(this)) nodes.push(this);
  }
  get innerHTML() { return this._html; }
}

const registry = new Map();
const getEl = (id) => {
  if (!registry.has(id)) registry.set(id, new El(id));
  return registry.get(id);
};

globalThis.document = {
  getElementById: (id) => (id.endsWith("SaveBtn") ? { addEventListener() {} } : getEl(id)),
  querySelector: (sel) => {
    const m = sel.match(/^#([\w-]+) tbody$/);
    return m ? getEl(m[1]) : null;
  },
  querySelectorAll: (sel) => {
    const attr = sel.replace(/[[\]]/g, "");
    const key = attr.replace(/^data-/, "").replace(/-(\w)/g, (_, c) => c.toUpperCase());
    return nodes.flatMap(n => n.inputs).filter(i => key in i.dataset);
  },
  addEventListener() {},
};
globalThis.state = { config: cfg, guilds: [], channels: [], roles: [] };
globalThis.fetch = async () => ({ ok: true, json: async () => ({}) });

// โหลดเฉพาะส่วนที่ต้องใช้ (ตัด init/DOMContentLoaded ที่ยิง network ออก)
const body = src.replace(/document\.addEventListener\("DOMContentLoaded", init\);/, "");
const mod = new Function(`${body}
  return { renderRetention, retentionSave, cfgGet, state };`)();
mod.state.config = cfg;   // app.js ประกาศ state ของตัวเอง — ยัด config เข้าไปเหมือนตอน loadConfig()

// ── 1. render แล้วต้องได้ช่องกรอกครบ ──
mod.renderRetention();
const all = document.querySelectorAll("[data-table]");
assert.ok(all.length > 40, `ช่องในตารางน้อยผิดปกติ (${all.length})`);
assert.ok(document.querySelectorAll("[data-cfg]").length > 15, "ช่องค่าเดี่ยวน้อยผิดปกติ");

// ── 2. ค่าที่ render ต้องตรงกับ config จริง ──
const q0 = all.find(i => i.dataset.table === "retDailyQuests" && i.dataset.i === "0" && i.dataset.col === "target");
assert.strictEqual(Number(q0.value), cfg.daily_quests.quests[0].target, "เควสข้อแรกแสดงเป้าไม่ตรง config");
const tier0 = all.find(i => i.dataset.table === "retSeasonTiers" && i.dataset.i === "0" && i.dataset.col === "premium.gold");
assert.strictEqual(Number(tier0.value), cfg.season_pass.tiers[0].premium.gold, "ซีซั่นพาสอ่านคีย์ซ้อนชั้นไม่ถูก");

// ── 3. ผู้ใช้แก้ค่า แล้ว save ต้องเข้า config ที่ตำแหน่งถูกต้อง ──
q0.value = "77";
tier0.value = "12345";
const pet = all.find(i => i.dataset.table === "retPets" && i.dataset.i === "0" && i.dataset.col === "dice");
pet.value = "9";
const ach = all.find(i => i.dataset.table === "retAchievements" && i.dataset.i === "0" && i.dataset.col === "title");
ach.value = "ฉายาใหม่";
const tax = document.querySelectorAll("[data-cfg]").find(i => i.dataset.cfg === "market.tax_percent");
tax.value = "13";
const onoff = document.querySelectorAll("[data-cfg]").find(i => i.dataset.cfg === "season_pass.enabled");
onoff.value = "0";

await mod.retentionSave();

const c = mod.state.config;
assert.strictEqual(c.daily_quests.quests[0].target, 77, "เป้าเควสไม่ถูกบันทึก");
assert.strictEqual(c.season_pass.tiers[0].premium.gold, 12345, "รางวัลพรีเมียมไม่ถูกบันทึก");
assert.strictEqual(c.pets.list[0].dice, 9, "โบนัสเต๋าสัตว์เลี้ยงไม่ถูกบันทึก");
assert.strictEqual(c.achievements[0].title, "ฉายาใหม่", "ตำแหน่งความสำเร็จไม่ถูกบันทึก");
assert.strictEqual(c.market.tax_percent, 13, "ค่าธรรมเนียมตลาดไม่ถูกบันทึก");
assert.strictEqual(c.season_pass.enabled, false, "สวิตช์เปิด/ปิดต้องเก็บเป็น boolean");

// ── 4. ห้ามทำโครงสร้างเดิมพัง ──
assert.strictEqual(c.daily_quests.quests.length, cfg.daily_quests.quests.length);
assert.ok(c.achievements.every(a => a.key), "คีย์ความสำเร็จหายระหว่างบันทึก");

console.log("✅ วงจร render → แก้ → save ของแท็บ Retention ผ่านครบ");
