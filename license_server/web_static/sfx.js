// 🔊 เสียงประกอบเว็บเกม (2026-08-14)
// สังเคราะห์สดด้วย WebAudio — ไม่มีไฟล์เสียงให้โหลด จึงไม่กินเน็ต ไม่ต้องรอ
// และไม่ติดข้อจำกัดเรื่องโหลดไฟล์จากภายนอก
//
// เบราว์เซอร์ห้ามเล่นเสียงก่อนผู้ใช้แตะจอ — เราจึงสร้าง AudioContext ตอนคลิกครั้งแรก
// ปิด/เปิดได้ที่ปุ่มลำโพง ค่าที่เลือกจำไว้ใน localStorage

const SFX = (() => {
  let ctx = null;
  let on = localStorage.getItem('sfx') !== 'off';
  let master = null;

  function ensure() {
    if (ctx) return ctx;
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return null;
    ctx = new AC();
    master = ctx.createGain();
    master.gain.value = .22;                    // เบาไว้ก่อน เกมนี้เล่นยาว
    master.connect(ctx.destination);
    return ctx;
  }

  /** โน้ตเดียว — type: sine/square/triangle/sawtooth */
  function tone({ freq = 440, dur = .12, type = 'square', vol = 1, slide = 0, delay = 0 }) {
    const c = ensure();
    if (!c || !on) return;
    const t0 = c.currentTime + delay;
    const osc = c.createOscillator();
    const g = c.createGain();
    osc.type = type;
    osc.frequency.setValueAtTime(freq, t0);
    if (slide) osc.frequency.exponentialRampToValueAtTime(Math.max(20, freq + slide), t0 + dur);
    g.gain.setValueAtTime(0, t0);
    g.gain.linearRampToValueAtTime(vol, t0 + .008);          // เข้าเร็ว กันเสียงป๊อก
    g.gain.exponentialRampToValueAtTime(.001, t0 + dur);
    osc.connect(g); g.connect(master);
    osc.start(t0); osc.stop(t0 + dur + .02);
  }

  /** เสียงซ่า ๆ ใช้ทำเสียงฟาด/ระเบิด */
  function noise({ dur = .18, vol = .6, delay = 0, hp = 800 }) {
    const c = ensure();
    if (!c || !on) return;
    const t0 = c.currentTime + delay;
    const len = Math.floor(c.sampleRate * dur);
    const buf = c.createBuffer(1, len, c.sampleRate);
    const data = buf.getChannelData(0);
    for (let i = 0; i < len; i++) data[i] = (Math.random() * 2 - 1) * (1 - i / len);
    const src = c.createBufferSource();
    src.buffer = buf;
    const f = c.createBiquadFilter();
    f.type = 'highpass'; f.frequency.value = hp;
    const g = c.createGain();
    g.gain.setValueAtTime(vol, t0);
    g.gain.exponentialRampToValueAtTime(.001, t0 + dur);
    src.connect(f); f.connect(g); g.connect(master);
    src.start(t0);
  }

  // เสียงประจำเหตุการณ์ — เรียกด้วย SFX.play('ชื่อ')
  const BANK = {
    click:   () => tone({ freq: 520, dur: .05, type: 'square', vol: .5 }),
    walk:    () => { tone({ freq: 300, dur: .06, type: 'triangle', vol: .4 });
                     tone({ freq: 260, dur: .06, type: 'triangle', vol: .35, delay: .12 }); },
    hit:     () => { noise({ dur: .14, vol: .7, hp: 600 });
                     tone({ freq: 180, dur: .1, type: 'square', vol: .5, slide: -90 }); },
    hurt:    () => { noise({ dur: .2, vol: .5, hp: 300 });
                     tone({ freq: 220, dur: .18, type: 'sawtooth', vol: .5, slide: -140 }); },
    skill:   () => { tone({ freq: 440, dur: .09, type: 'sine', vol: .5 });
                     tone({ freq: 660, dur: .09, type: 'sine', vol: .5, delay: .07 });
                     tone({ freq: 880, dur: .14, type: 'sine', vol: .45, delay: .14 }); },
    win:     () => [523, 659, 784, 1047].forEach((f, i) =>
                     tone({ freq: f, dur: .17, type: 'square', vol: .5, delay: i * .1 })),
    lose:    () => [392, 330, 262, 196].forEach((f, i) =>
                     tone({ freq: f, dur: .24, type: 'sawtooth', vol: .45, delay: i * .14 })),
    coin:    () => { tone({ freq: 988, dur: .07, type: 'square', vol: .45 });
                     tone({ freq: 1319, dur: .13, type: 'square', vol: .4, delay: .06 }); },
    dice:    () => [0, .06, .12, .18].forEach(d =>
                     noise({ dur: .05, vol: .35, delay: d, hp: 1600 })),
    levelup: () => [523, 659, 784, 1047, 1319].forEach((f, i) =>
                     tone({ freq: f, dur: .2, type: 'sine', vol: .5, delay: i * .09 })),
    error:   () => tone({ freq: 160, dur: .22, type: 'square', vol: .45, slide: -60 }),
    flee:    () => tone({ freq: 700, dur: .28, type: 'sine', vol: .4, slide: 900 }),
  };

  return {
    play(name) { try { (BANK[name] || (() => {}))(); } catch (e) { /* เสียงพังห้ามทำให้เกมพัง */ } },
    get enabled() { return on; },
    toggle() {
      on = !on;
      localStorage.setItem('sfx', on ? 'on' : 'off');
      if (on) { ensure(); this.play('click'); }
      return on;
    },
    names() { return Object.keys(BANK); },
  };
})();
