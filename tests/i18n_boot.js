// 🔬 i18n.js ในกล่อง vm — เลือกภาษา · tr() · แปล [data-i18n*] · ตั้งคุกกี้
// รัน: node tests/i18n_boot.js '<JSON รายการรหัสภาษา>'   (tests/test_i18n_js.py เรียกให้)
// บรรทัดสุดท้ายพิมพ์ "NORM [...]" = ผล normLang() ของรายการนั้น ให้ไพทอนเทียบกับ normalize()
const fs = require('fs'), vm = require('vm');
const SRC = fs.readFileSync('license_server/web_static/i18n.js', 'utf8');
let fail = 0;
const ok = (cond, msg) => { if (!cond) { fail++; console.log('❌ ' + msg); } };

function boot({ cookie, languages, dict = {}, status = 200, elements = {} } = {}) {
  const asked = [];
  const doc = {
    cookie,
    documentElement: { lang: 'th' },
    querySelectorAll: (sel) => elements[sel] || [],
  };
  const sb = {
    console: { warn() {} },
    document: doc,
    XMLHttpRequest: function () {
      this.open = (method, url, async) => asked.push({ url, async });
      this.send = () => { this.status = status; this.responseText = JSON.stringify(dict); };
    },
    location: { reload() { sb.reloaded = true; } },
  };
  if (languages) sb.navigator = { languages, language: languages[0] };
  vm.createContext(sb);
  vm.runInContext(SRC, sb);
  sb.LANG = vm.runInContext('I18N_LANG', sb);
  return { sb, asked, doc };
}

// 1) ไม่มีคุกกี้ ไม่มี navigator (เหมือนเทส worms_boot.js) → ไทย ไม่ยิงอะไรเลย
{
  const { sb, asked, doc } = boot();
  ok(sb.LANG === 'th', 'ไม่มีข้อมูลอะไรเลยต้องเป็นไทย ได้ ' + sb.LANG);
  ok(asked.length === 0, 'ภาษาไทยต้องไม่โหลดไฟล์คำแปล');
  ok(doc.documentElement.lang === 'th', '<html lang> ต้องเป็น th');
  ok(sb.tr('ทอง {n}', { n: 3 }) === 'ทอง 3', 'ไทยต้องเติมตัวแปรได้');
}

// 2) คุกกี้ lang=en → โหลดแบบ sync แล้วแปลป้ายทั้งสามแบบ
{
  const textEl = { textContent: '  สวัสดี\n   โลก ' };
  const htmlEl = { innerHTML: 'เงิน <b id="c"></b> ทอง' };
  const attrEl = {
    attrs: { 'data-i18n-attr': 'placeholder, title', placeholder: 'เช่น 100', title: '' },
    getAttribute(a) { return a in this.attrs ? this.attrs[a] : null; },
    setAttribute(a, v) { this.attrs[a] = v; },
  };
  const { sb, asked, doc } = boot({
    cookie: 'x=1; lang=en',
    dict: { 'ทอง {n}': '{n} gold', 'สวัสดี โลก': 'Hello world',
            'เงิน <b id="c"></b> ทอง': 'Cash <b id="c"></b> gold', 'เช่น 100': 'e.g. 100' },
    elements: { '[data-i18n]': [textEl], '[data-i18n-html]': [htmlEl], '[data-i18n-attr]': [attrEl] },
  });
  ok(sb.LANG === 'en', 'คุกกี้ lang=en ต้องได้ en');
  ok(asked.length === 1 && asked[0].url === '/locales/en.json' && asked[0].async === false,
     'ต้องโหลด /locales/en.json แบบ sync ครั้งเดียว ได้ ' + JSON.stringify(asked));
  ok(doc.documentElement.lang === 'en', '<html lang> ต้องเป็น en');
  ok(textEl.textContent === 'Hello world', 'data-i18n ต้องแปล (ยุบช่องว่างก่อนหา) ได้ ' + textEl.textContent);
  ok(htmlEl.innerHTML === 'Cash <b id="c"></b> gold', 'data-i18n-html ต้องแปลและคง id ไว้');
  ok(attrEl.attrs.placeholder === 'e.g. 100', 'data-i18n-attr ต้องแปล placeholder');
  ok(attrEl.attrs.title === '', 'แอตทริบิวต์ว่างต้องไม่ถูกแตะ');
  ok(sb.tr('ทอง {n}', { n: 3 }) === '3 gold', 'tr ต้องแปลแล้วเติมตัวแปร');
  ok(sb.tr('ไม่มีในไฟล์') === 'ไม่มีในไฟล์', 'ไม่มีคำแปลต้องคืนไทยเดิม');
}

// 3) ไม่มีคุกกี้ เบราว์เซอร์ภาษาญี่ปุ่น → ja
{
  const { sb, asked } = boot({ languages: ['ja-JP', 'en-US'] });
  ok(sb.LANG === 'ja', 'เบราว์เซอร์ ja-JP ต้องได้ ja');
  ok(asked[0] && asked[0].url === '/locales/ja.json', 'ต้องโหลด ja.json');
}

// 4) คุกกี้ชนะภาษาเบราว์เซอร์ · คุกกี้แปลก ๆ ต้องไม่พัง
{
  ok(boot({ cookie: 'lang=th', languages: ['en-US'] }).sb.LANG === 'th', 'คุกกี้ต้องชนะภาษาเบราว์เซอร์');
  ok(boot({ cookie: 'lang=fr' }).sb.LANG === 'en', 'คุกกี้ภาษาที่ไม่รองรับต้องได้ en');
  ok(boot({ cookie: 'lang=' }).sb.LANG === 'th', 'คุกกี้ว่างต้องได้ th');
  ok(boot({ cookie: 'lang=EN-us' }).sb.LANG === 'en', 'คุกกี้ตัวใหญ่ต้องได้ en');
  ok(boot({ cookie: 'lang=%' }).sb.LANG === 'en', 'คุกกี้ % เพี้ยนต้องไม่ throw');
}

// 5) ไฟล์คำแปล 404 → ไทยเดิม ไม่ throw
{
  const { sb } = boot({ cookie: 'lang=zh', status: 404 });
  ok(sb.LANG === 'zh', 'ยังเป็น zh');
  ok(sb.tr('ทอง') === 'ทอง', '404 แล้ว tr ต้องคืนไทย');
}

// 6) setLang จำในคุกกี้ 1 ปีแล้วรีโหลด
{
  const { sb, doc } = boot();
  sb.setLang('zh-CN');
  ok(doc.cookie === 'lang=zh; path=/; max-age=31536000; samesite=lax', 'คุกกี้ผิด: ' + doc.cookie);
  ok(sb.reloaded === true, 'ต้องรีโหลดหน้า');
}

// 7) เทียบ normLang กับไพทอน
{
  const { sb } = boot();
  const cases = JSON.parse(process.argv[2] || '[]');
  console.log('NORM ' + JSON.stringify(cases.map((c) => sb.normLang(c))));
}

process.exit(fail ? 1 : 0);
