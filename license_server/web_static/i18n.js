// 🌐 แปลภาษาหน้าเว็บ — ข้อความไทยคือคีย์ · คู่กับ bot/i18n.py (ไฟล์คำแปลชุดเดียวกัน)
// ต้องโหลด "ก่อน" web.js ทุกหน้า (tests/test_i18n_js.py เช็ค) แล้วมันจะแปลป้ายในหน้าให้ทันที:
//   tr("ได้รับ {gold} ทอง", { gold: 5 })        แปล + เติมตัวแปร (ตัวแรกต้องเป็นข้อความตรง ๆ)
//   <p data-i18n>ข้อความล้วน</p>                 แปล textContent
//   <p data-i18n-html>มี <b id="x"></b> แท็ก</p>  แปล innerHTML (คำแปลต้องมีแท็ก/id ครบ)
//   <input placeholder="..." data-i18n-attr="placeholder,title">
// ชื่อ tr ไม่ใช่ t — โค้ดเดิมใช้ t เป็นตัวแปร local อยู่ 26 จุด
// สเปก: docs/superpowers/specs/2026-10-05-i18n-design.md

const I18N_LANGS = ["th", "en", "zh", "ja"];
// ชื่อภาษาเขียนด้วยภาษาตัวเองเสมอ — คนอ่านไทยไม่ออกก็หาภาษาตัวเองในปุ่มเลือกเจอ
const I18N_NAMES = { th: "ไทย", en: "English", zh: "中文", ja: "日本語" };

/** รหัสภาษาเบราว์เซอร์/คุกกี้ → th/en/zh/ja · ว่าง → th · ภาษาอื่น → en (คู่กับ normalize() ใน bot/i18n.py) */
function normLang(code) {
  const base = String(code || "").trim().toLowerCase().replace(/_/g, "-").split("-")[0];
  if (!base) return "th";
  return I18N_LANGS.includes(base) ? base : "en";
}

/** คุกกี้ lang ก่อน → ภาษาเบราว์เซอร์ → ไทย */
function pickLang() {
  const ck = (typeof document !== "undefined" && document.cookie) || "";
  const m = ck.match(/(?:^|;\s*)lang=([^;]*)/);
  if (m) return normLang(m[1]);      // ไม่ decodeURIComponent — คุกกี้ "lang=%" จะ throw ทั้งไฟล์ แล้ว web.js พังตาม
  const nav = typeof navigator !== "undefined" && navigator
    ? ((navigator.languages && navigator.languages[0]) || navigator.language) : "";
  return normLang(nav);
}

const I18N_LANG = pickLang();
let I18N_DICT = {};
if (I18N_LANG !== "th" && typeof XMLHttpRequest !== "undefined") {
  // ponytail: XHR แบบ sync = บล็อกหน้าเท่า <script src> ธรรมดา (คอนโซลเตือน deprecated)
  // แลกกับ tr() พร้อมใช้ก่อน web.js/play.js รัน ไม่ต้องรื้อทุกหน้าให้รอ promise
  // ถ้าเบราว์เซอร์เลิกรองรับ → ทำ route /locales/<lang>.js ฝั่งเซิร์ฟเวอร์แล้วโหลดด้วย <script>
  try {
    const x = new XMLHttpRequest();
    x.open("GET", "/locales/" + I18N_LANG + ".json", false);
    x.send();
    if (x.status === 200) I18N_DICT = JSON.parse(x.responseText);
  } catch (e) { /* เน็ตสะดุด/ไฟล์พัง → แสดงไทยไปก่อน */ }
}

const _i18nMissing = new Set();

/** ข้อความไทย → ภาษาที่เลือก แล้วเติม {ตัวแปร} · ไม่มีคำแปล = ไทยเดิม (เตือนในคอนโซลครั้งเดียว) */
function tr(text, vars) {
  let s = text;
  if (I18N_LANG !== "th") {
    if (Object.hasOwn(I18N_DICT, text) && I18N_DICT[text]) s = I18N_DICT[text];
    else if (!_i18nMissing.has(text)) { _i18nMissing.add(text); console.warn("[i18n] ไม่มีคำแปล:", text); }
  }
  return vars ? s.replace(/\{(\w+)\}/g, (m, k) => (k in vars ? vars[k] : m)) : s;
}

/** คีย์ของข้อความ/HTML/แอตทริบิวต์ในหน้า = ยุบช่องว่างก่อน (คู่กับ norm() ใน scripts/i18n_extract.py) */
function i18nKey(s) { return String(s).replace(/\s+/g, " ").trim(); }

/** แปลทุก [data-i18n*] ใต้ root — ไฟล์นี้เรียกให้ทั้งหน้าเองตอนโหลด */
function applyI18n(root) {
  if (I18N_LANG === "th" || !root || !root.querySelectorAll) return;
  root.querySelectorAll("[data-i18n]").forEach((el) => { el.textContent = tr(i18nKey(el.textContent)); });
  root.querySelectorAll("[data-i18n-html]").forEach((el) => { el.innerHTML = tr(i18nKey(el.innerHTML)); });
  root.querySelectorAll("[data-i18n-attr]").forEach((el) => {
    el.getAttribute("data-i18n-attr").split(",").forEach((a) => {
      const name = a.trim();
      const v = name && el.getAttribute(name);
      if (v) el.setAttribute(name, tr(i18nKey(v)));
    });
  });
}

/** ปุ่มเลือกภาษาเรียก — จำในคุกกี้ 1 ปี (เซิร์ฟเวอร์อ่านได้ในก้อน 2) แล้วโหลดหน้าใหม่ */
function setLang(code) {
  document.cookie = "lang=" + normLang(code) + "; path=/; max-age=31536000; samesite=lax";
  location.reload();
}

// รันตอนโหลด: สคริปต์นี้อยู่ใต้เนื้อหาทั้งหมดและก่อนสคริปต์อื่น → แปลก่อนใครแตะ DOM
if (typeof document !== "undefined" && document.documentElement) {
  document.documentElement.lang = I18N_LANG;      // CSS เลือกฟอนต์จีน/ญี่ปุ่นจากค่านี้
  applyI18n(document);
}
