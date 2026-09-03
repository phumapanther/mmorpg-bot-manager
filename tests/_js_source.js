// เอนจินรวมซอร์สหน้าเล่นเกม — คู่กับ conftest.py::play_js_source() ฝั่งไพทอน
//
// เทส JS หลายไฟล์ (bot_reveal.js, drop_reveal.js, frame_clock.js, over_timing.js,
// render_over.js, reveal_flow.js) เคยอ่าน play.js ไฟล์เดียวแล้ว grab() ฟังก์ชัน wm*
// ออกมาด้วยการค้นข้อความ — พอผ่า play.js ออกเป็นหลายไฟล์ (09-02 ขั้นที่ 5)
// ฟังก์ชันพวกนั้นอาจย้ายไปอยู่ games/worms_ui.js แล้ว ต้องรวมซอร์สก่อนค้นหา
// ไม่งั้น grab() จะโยน "หาไม่เจอ" ทั้งที่โค้ดจริงยังอยู่ครบ
const fs = require('fs');
const path = require('path');

const WEB = path.join(__dirname, '..', 'license_server', 'web_static');

function playSource() {
  return ['play.js', 'games/worms_ui.js', 'shop_ui.js']
    .map(p => path.join(WEB, p))
    .filter(p => fs.existsSync(p))
    .map(p => fs.readFileSync(p, 'utf8'))
    .join('\n');
}

module.exports = { playSource, WEB };
