// เว็บไซต์เกม — ตัวช่วยร่วมทุกหน้า (navbar/footer/api/markdown)
// 🎨 แก้ชื่อเกม/คำโปรยได้ที่นี่จุดเดียว
const SITE = {
  name: "Fragment Rift",
  tagline: "MMORPG ผจญภัยเต็มรูปแบบใน Discord — 9 ทวีป 7 ธาตุ บอสลับ กิลด์วอร์ และเพื่อนร่วมทาง",
};

async function api(method, url, body) {
  const opts = { method, headers: {} };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(url, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || res.statusText);
  return data;
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

const CATEGORY_LABEL = { news: "📢 ข่าว", patch: "🛠️ แพทช์", event: "🎪 อีเวนต์" };

// ── navbar + footer ใช้ร่วมทุกหน้า ──
const NAV_ITEMS = [
  ["/", "หน้าแรก"], ["/news", "ข่าวสาร"], ["/game", "ข้อมูลเกม"], ["/topup", "เติมเกม"],
];

async function renderChrome(active) {
  const nav = document.getElementById("navbar");
  const links = NAV_ITEMS.map(([href, label]) =>
    `<a class="nav-link${active === href ? " active" : ""}" href="${href}">${label}</a>`).join("");
  nav.innerHTML = `<div class="nav">
    <a class="logo" href="/">${esc(SITE.name)}</a>
    <div class="links">${links}<a class="nav-link" id="navProfile" href="/login">🔑 ล็อกอิน</a></div>
  </div>`;

  const foot = document.getElementById("footer");
  if (foot) {
    foot.innerHTML = `<div class="container">
      <div class="cols">
        <div><h4>${esc(SITE.name)}</h4><p>${esc(SITE.tagline)}</p></div>
        <div><h4>เมนู</h4><a href="/">หน้าแรก</a><a href="/news">ข่าวสาร</a><a href="/game">ข้อมูลเกม</a><a href="/topup">เติมเกม</a></div>
        <div><h4>ชุมชน</h4><a id="footDiscord" href="#" target="_blank" rel="noopener">💬 Discord เซิร์ฟหลัก</a><a href="/me">โปรไฟล์ของฉัน</a></div>
      </div>
      <p class="tiny">© ${new Date().getFullYear()} ${esc(SITE.name)} — เล่นฟรีใน Discord</p>
    </div>`;
  }

  // สถานะล็อกอิน (endpoint มาจากระบบล็อกอิน — ยังไม่ล็อกอิน/ยังไม่มีระบบ = โชว์ปุ่มล็อกอินตามเดิม)
  try {
    const s = await api("GET", "/api/web/me/session");
    if (s.discord_id) {
      const el = document.getElementById("navProfile");
      el.textContent = "👤 โปรไฟล์";
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
