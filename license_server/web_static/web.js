// เว็บไซต์เกม — ตัวช่วยร่วมทุกหน้า (navbar/footer/api/markdown)
// 🎨 แก้ชื่อเกม/คำโปรยได้ที่นี่จุดเดียว
const SITE = {
  name: "Fragment Rift",
  tagline: tr("MMORPG ผจญภัยเต็มรูปแบบใน Discord — 9 ทวีป 7 ธาตุ บอสลับ กิลด์วอร์ และเพื่อนร่วมทาง"),
};

// 401 จากสามอันนี้แปลว่า "ยังไม่ได้ล็อกอิน" ซึ่งเป็นเรื่องปกติ ไม่ใช่ session หมดอายุ
// หน้า /admin ยิง admin/ping ถามก่อนโชว์ฟอร์มกรอกรหัส ถ้าเด้งป้ายเต็มจอทับ ฟอร์มก็กดไม่ได้เลย
// และกรอกรหัสผิดก็ตอบ 401 เหมือนกัน ต้องปล่อยให้ผู้เรียกบอกเองว่า "รหัสไม่ถูกต้อง"
const AUTH_PROBES = ["/me/session", "/admin/ping", "/admin/login"];

async function api(method, url, body) {
  const opts = { method, headers: {} };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(url, opts);
  const data = await res.json().catch(() => ({}));
  if (res.status === 401 && !AUTH_PROBES.some((p) => url.includes(p))) {
    // session หมดอายุ/ถูกลบ — บอกให้รู้แล้วพากลับไปล็อกอิน ไม่ใช่ปล่อยให้กดแล้วเงียบ
    onSessionExpired();
    throw new Error(data.detail || tr("หมดเวลาเข้าสู่ระบบ — กรุณาล็อกอินใหม่"));
  }
  if (!res.ok) {
    // แนบสถานะกับเวลาที่ต้องรอไปด้วย — ผู้เรียกจะได้ถอยเองเมื่อโดนจำกัดอัตรา (429)
    const err = new Error(data.detail || res.statusText);
    err.status = res.status;
    err.retryAfter = +(res.headers.get("Retry-After") || 0);
    throw err;
  }
  return data;
}

let _expiredShown = false;

/** เรียกเมื่อเซิร์ฟเวอร์ตอบ 401 — เตือนครั้งเดียวแล้วพากลับหน้าล็อกอิน */
function onSessionExpired() {
  if (_expiredShown) return;
  _expiredShown = true;
  const box = document.createElement("div");
  box.style.cssText = "position:fixed;inset:0;z-index:9999;display:grid;place-items:center;" +
    "background:rgba(8,6,4,.86);color:#f2e7d8;font-family:inherit;text-align:center;padding:24px";
  box.innerHTML = '<div style="max-width:420px">' +
    '<div style="font-size:44px;margin-bottom:10px">🔒</div>' +
    '<h2 style="margin:0 0 8px">' + tr("หมดเวลาเข้าสู่ระบบ") + '</h2>' +
    '<p style="color:#a99274;margin:0 0 18px">' + tr("เพื่อความปลอดภัย ระบบให้ล็อกอินใหม่อีกครั้ง") + '</p>' +
    '<a href="' + (location.pathname.startsWith("/admin") ? "/admin" : "/login") +
    '" style="display:inline-block;padding:12px 26px;border-radius:10px;' +
    'background:#c8452f;color:#fff;text-decoration:none;font-weight:700">' + tr("ไปหน้าล็อกอิน") + '</a></div>';
  document.body.appendChild(box);
}


function esc(s) {
  return String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

// mini-markdown: # ## ### **หนา** *เอียง* - ลิสต์ [ลิงก์](url) ![รูป](url) — เรนเดอร์ข่าวจากแอดมิน
function md(src) {
  const safeUrl = (u) => (/^(https?:\/\/|\/)/.test(u) ? u : "#");
  let h = esc(src);
  h = h.replace(/!\[([^\]]*)\]\(([^)\s]+)\)/g, (_, a, u) => `<img src="${safeUrl(u)}" alt="${a}">`);
  h = h.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (_, t, u) => `<a href="${safeUrl(u)}" target="_blank" rel="noopener">${t}</a>`);
  h = h.replace(/^### (.*)$/gm, "<h3>$1</h3>").replace(/^## (.*)$/gm, "<h2>$1</h2>").replace(/^# (.*)$/gm, "<h1>$1</h1>");
  h = h.replace(/\*\*([^*\n]+)\*\*/g, "<b>$1</b>").replace(/\*([^*\n]+)\*/g, "<i>$1</i>");
  h = h.replace(/`([^`\n]+)`/g, "<code>$1</code>");
  h = h.replace(/(?:^- .*(?:\n|$))+/gm, (m) => `<ul>${m.trim().split("\n").map((l) => `<li>${l.slice(2)}</li>`).join("")}</ul>`);
  return h.split(/\n{2,}/).map((b) => (/^<(h\d|ul|img)/.test(b.trim()) ? b : `<p>${b.replace(/\n/g, "<br>")}</p>`)).join("\n");
}

const CATEGORY_LABEL = { news: tr("📢 ข่าว"), patch: tr("🛠️ แพทช์"), event: tr("🎪 อีเวนต์") };

// ── navbar + footer ใช้ร่วมทุกหน้า ──
const NAV_ITEMS = [
  ["/", tr("หน้าแรก")], ["/news", tr("ข่าวสาร")], ["/game", tr("ข้อมูลเกม")],
  ["/play", tr("🎮 เล่นเกม")], ["/wold", "🏰 WOLD Arture"], ["/calendar", tr("📅 ปฏิทิน")], ["/topup", tr("เติมเกม")],
];

async function renderChrome(active) {
  const nav = document.getElementById("navbar");
  const links = NAV_ITEMS.map(([href, label]) =>
    `<a class="nav-link${active === href ? " active" : ""}" href="${href}">${label}</a>`).join("");
  // 🌐 ปุ่มเลือกภาษา — ชื่อภาษาเขียนด้วยภาษาตัวเอง · เลือกแล้ว i18n.js จำในคุกกี้แล้วรีโหลด
  const langPick = `<select class="lang-pick" aria-label="${tr("ภาษา")}">` +
    I18N_LANGS.map((c) => `<option value="${c}"${c === I18N_LANG ? " selected" : ""}>${I18N_NAMES[c]}</option>`).join("") +
    "</select>";
  // 📱 มือถือ: เมนูพับเก็บได้ ไม่ให้กินครึ่งจอ — ใช้ <details> ของเบราว์เซอร์ตรง ๆ
  // เปิด/ปิดเอง กดคีย์บอร์ดได้ ไม่ต้องเขียน JS สักบรรทัด · จอกว้าง CSS สั่งกางค้างไว้
  nav.innerHTML = `<details class="nav">
    <summary class="navbar-toggle">
      <a class="logo" href="/">${esc(SITE.name)}</a>
      <span class="burger" aria-hidden="true"><i></i><i></i><i></i></span>
    </summary>
    <div class="links">${links}<a class="nav-link" id="navProfile" href="/login">${tr("🔑 ล็อกอิน")}</a>${langPick}</div>
  </details>`;
  nav.querySelector(".lang-pick").addEventListener("change", (e) => setLang(e.target.value));

  // จอกว้าง = กางค้างไว้เสมอ (ไม่มีปุ่มพับให้เห็นด้วยซ้ำ) · จอแคบ = เริ่มแบบพับเก็บ
  // ไม่บังคับปิดตอน resize เพราะบนมือถือคีย์บอร์ดเด้งก็นับเป็น resize เมนูจะหุบเองกลางคัน
  const bar = nav.querySelector(".nav");
  const wide = () => !window.matchMedia("(max-width: 640px)").matches;
  bar.open = wide();
  window.addEventListener("resize", () => { if (wide()) bar.open = true; });

  const foot = document.getElementById("footer");
  if (foot) {
    foot.innerHTML = `<div class="container">
      <div class="cols">
        <div><h4>${esc(SITE.name)}</h4><p>${esc(SITE.tagline)}</p></div>
        <div><h4>${tr("เมนู")}</h4><a href="/">${tr("หน้าแรก")}</a><a href="/news">${tr("ข่าวสาร")}</a><a href="/game">${tr("ข้อมูลเกม")}</a><a href="/play">${tr("เล่นเกม")}</a><a href="/calendar">${tr("ปฏิทิน")}</a><a href="/topup">${tr("เติมเกม")}</a></div>
        <div><h4>${tr("ชุมชน")}</h4><a id="footDiscord" href="#" target="_blank" rel="noopener">${tr("💬 Discord เซิร์ฟหลัก")}</a><a href="/me">${tr("โปรไฟล์ของฉัน")}</a></div>
      </div>
      <p class="tiny">© ${new Date().getFullYear()} ${esc(SITE.name)} — ${tr("เล่นฟรีใน Discord")}</p>
    </div>`;
  }

  // สถานะล็อกอิน (endpoint มาจากระบบล็อกอิน — ยังไม่ล็อกอิน/ยังไม่มีระบบ = โชว์ปุ่มล็อกอินตามเดิม)
  try {
    const s = await api("GET", "/api/web/me/session");
    if (s.discord_id) {
      const el = document.getElementById("navProfile");
      el.textContent = tr("👤 โปรไฟล์");
      el.href = "/me";
    }
  } catch (e) { /* ไม่ล็อกอิน */ }
}

async function fillDiscordInvite() {
  try {
    const g = await api("GET", "/api/web/gamedata");
    document.querySelectorAll("#footDiscord, .js-invite").forEach((a) => {
      if (g.invite) a.href = g.invite; else a.classList.add("hidden");
    });
    return g;
  } catch (e) { return null; }
}
