// 🔊 เสียงประกอบเว็บเกม (2026-08-14)
// สังเคราะห์สดด้วย WebAudio — ไม่มีไฟล์เสียงให้โหลด จึงไม่กินเน็ต ไม่ต้องรอ
// และไม่ติดข้อจำกัดเรื่องโหลดไฟล์จากภายนอก
//
// เบราว์เซอร์ห้ามเล่นเสียงก่อนผู้ใช้แตะจอ — เราจึงสร้าง AudioContext ตอนคลิกครั้งแรก
// ปิด/เปิดได้ที่ปุ่มลำโพง (เอฟเฟกต์) กับปุ่มโน้ต (เพลงพื้นหลัง) แยกกัน
// เพราะคนที่อยากได้เสียงตีมอนแต่ไม่อยากได้เพลงคลอมีจริง — ค่าที่เลือกจำไว้ใน localStorage

const SFX = (() => {
  let ctx = null;
  let on = localStorage.getItem('sfx') !== 'off';
  let mon = localStorage.getItem('bgm') !== 'off';
  let master = null;
  let mbus = null;                              // บัสเพลงพื้นหลัง แยกจากเอฟเฟกต์เพื่อหรี่/ตัดได้ทันที

  function ensure() {
    if (ctx) { if (ctx.state === 'suspended') ctx.resume(); return ctx; }
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return null;
    ctx = new AC();
    master = ctx.createGain();
    master.gain.value = .22;                    // เบาไว้ก่อน เกมนี้เล่นยาว
    master.connect(ctx.destination);
    return ctx;
  }

  /** บัสเพลง — สร้างใหม่ทุกครั้งที่เปิดเพลง เพื่อให้ "หยุด" ตัดโน้ตที่จองคิวไว้ได้ทันที */
  function musicBus() {
    if (mbus) return mbus;
    if (!ensure()) return null;
    mbus = ctx.createGain();
    mbus.gain.value = .42;                      // เพลงคลอต้องเบากว่าเอฟเฟกต์เสมอ ไม่งั้นกลบเสียงตีมอน
    mbus.connect(master);
    return mbus;
  }

  function out(chan) { return chan === 'mus' ? musicBus() : master; }

  /** โน้ตเดียว — type: sine/square/triangle/sawtooth */
  function tone({ freq = 440, dur = .12, type = 'square', vol = 1, slide = 0, delay = 0, chan }) {
    const c = ensure();
    if (!c || !on) return;
    const dest = out(chan);
    if (!dest) return;
    const t0 = c.currentTime + delay;
    const osc = c.createOscillator();
    const g = c.createGain();
    osc.type = type;
    osc.frequency.setValueAtTime(freq, t0);
    if (slide) osc.frequency.exponentialRampToValueAtTime(Math.max(20, freq + slide), t0 + dur);
    g.gain.setValueAtTime(0, t0);
    g.gain.linearRampToValueAtTime(vol, t0 + .008);          // เข้าเร็ว กันเสียงป๊อก
    g.gain.exponentialRampToValueAtTime(.001, t0 + dur);
    osc.connect(g); g.connect(dest);
    osc.start(t0); osc.stop(t0 + dur + .02);
  }

  /** เสียงซ่า ๆ ใช้ทำเสียงฟาด/ระเบิด */
  function noise({ dur = .18, vol = .6, delay = 0, hp = 800, chan }) {
    const c = ensure();
    if (!c || !on) return;
    const dest = out(chan);
    if (!dest) return;
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
    src.connect(f); f.connect(g); g.connect(dest);
    src.start(t0);
  }

  // เสียงประจำเหตุการณ์ — เรียกด้วย SFX.play('ชื่อ')
  const BANK = {
    click:   () => tone({ freq: 520, dur: .05, type: 'square', vol: .5 }),
    // ก้าวเดียว — สลับซ้าย/ขวาด้วยระดับเสียงต่างกันนิดเดียว ให้ฟังเป็นคนเดินจริงไม่ใช่เสียงปี๊บซ้ำ
    walk:    () => { noise({ dur: .07, vol: .3, hp: 700 });
                     tone({ freq: 105, dur: .09, type: 'triangle', vol: .3, slide: -35 }); },
    walk2:   () => { noise({ dur: .07, vol: .26, hp: 900 });
                     tone({ freq: 88, dur: .09, type: 'triangle', vol: .28, slide: -28 }); },
    hit:     () => { noise({ dur: .14, vol: .7, hp: 600 });
                     tone({ freq: 180, dur: .1, type: 'square', vol: .5, slide: -90 }); },
    hurt:    () => { noise({ dur: .2, vol: .5, hp: 300 });
                     tone({ freq: 220, dur: .18, type: 'sawtooth', vol: .5, slide: -140 }); },
    // มอนกินดาเมจ — เสียงเนื้อโดนกระแทกกับเสียงร้องสั้น ๆ คนละตัวกับเสียงเหวี่ยงอาวุธ (hit)
    foehit:  () => { noise({ dur: .16, vol: .6, hp: 260 });
                     tone({ freq: 150, dur: .14, type: 'square', vol: .5, slide: -70 });
                     tone({ freq: 420, dur: .16, type: 'sawtooth', vol: .32, delay: .05, slide: -260 }); },
    // ดาเมจก้อนใหญ่ (คริติคอล/สกิลเข้าเต็ม ๆ) — หนักกว่าเดิมให้รู้ว่าเข้าแรง
    foecrit: () => { noise({ dur: .3, vol: .8, hp: 160 });
                     tone({ freq: 110, dur: .3, type: 'square', vol: .6, slide: -55 });
                     tone({ freq: 520, dur: .26, type: 'sawtooth', vol: .4, delay: .06, slide: -380 });
                     tone({ freq: 1568, dur: .18, type: 'sine', vol: .25, delay: .04 }); },
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

    // ── ของเข้ากระเป๋า/ของหาย ──
    item:    () => [784, 1047, 1568].forEach((f, i) =>              // เก็บของได้ — ใสสั้น กดรัว ๆ ก็ไม่รำคาญ
                     tone({ freq: f, dur: .1, type: 'triangle', vol: .45, delay: i * .05 })),
    use:     () => { tone({ freq: 320, dur: .22, type: 'sine', vol: .45, slide: 420 });
                     noise({ dur: .1, vol: .2, delay: .16, hp: 2200 }); },
    equip:   () => { noise({ dur: .1, vol: .5, hp: 2400 });         // เหล็กกระทบเหล็กตอนสวมใส่
                     tone({ freq: 220, dur: .16, type: 'square', vol: .4 });
                     tone({ freq: 1320, dur: .3, type: 'sine', vol: .22, delay: .05 }); },
    craft:   () => [0, .16, .34].forEach((d, i) => {                 // ตีค้อน 3 ที ทีสุดท้ายดังสุด
                     noise({ dur: .12, vol: .45 + i * .12, delay: d, hp: 2000 });
                     tone({ freq: 300 - i * 30, dur: .12, type: 'square', vol: .35, delay: d, slide: -120 }); }),

    // ── เจอเหตุการณ์ระหว่างทาง — แต่ละอย่างต้องฟังออกตั้งแต่ยังไม่อ่านข้อความ ──
    calm:    () => noise({ dur: .7, vol: .09, hp: 320 }),               // ลมพัดเบา ๆ ทางโล่ง
    village: () => { tone({ freq: 784, dur: .7, type: 'sine', vol: .4 });        // ระฆังหมู่บ้าน
                     tone({ freq: 1047, dur: .8, type: 'sine', vol: .3, delay: .16 });
                     tone({ freq: 523, dur: .9, type: 'triangle', vol: .22, delay: .3 }); },
    npc:     () => { tone({ freq: 523, dur: .14, type: 'triangle', vol: .4 });   // ทักทาย "สวัสดี?"
                     tone({ freq: 659, dur: .14, type: 'triangle', vol: .4, delay: .13 });
                     tone({ freq: 587, dur: .26, type: 'triangle', vol: .35, delay: .27 }); },
    dungeon: () => { tone({ freq: 62, dur: 1.1, type: 'sawtooth', vol: .38 });   // ลมหวีดจากปากถ้ำ
                     noise({ dur: .8, vol: .2, hp: 180 });
                     tone({ freq: 1568, dur: .1, type: 'sine', vol: .18, delay: .35 });   // น้ำหยดก้องไกล
                     tone({ freq: 1568, dur: .1, type: 'sine', vol: .1, delay: .62 }); },
    treasure: () => [1047, 1319, 1568, 2093].forEach((f, i) =>          // เห็นหีบวาววับแต่ไกล
                      tone({ freq: f, dur: .3, type: 'sine', vol: .34 - i * .04, delay: i * .09 })),
    foe:     () => { tone({ freq: 70, dur: .45, type: 'sawtooth', vol: .55, slide: 60 });  // คำรามพุ่งเข้ามา
                     noise({ dur: .3, vol: .45, hp: 240 });
                     tone({ freq: 330, dur: .3, type: 'square', vol: .3, delay: .12, slide: -150 }); },
    danger:  () => [0, .22, .44].forEach(d => {                          // ไซเรน — โจร/ถูกปล้น
                     tone({ freq: 740, dur: .16, type: 'square', vol: .4, delay: d });
                     tone({ freq: 554, dur: .16, type: 'square', vol: .4, delay: d + .11 }); }),
    special: () => [440, 622, 880, 622, 1244].forEach((f, i) =>          // ระยิบระยับลึกลับ
                     tone({ freq: f, dur: .38, type: 'sine', vol: .3, delay: i * .12, slide: 40 })),

    // ── พาหนะข้ามทวีป — คนละคันต้องคนละเสียง ──
    veh_airship: () => { noise({ dur: .55, vol: .35, hp: 400 });         // หัวเผาเรือเหาะพ่นไฟ
                         tone({ freq: 180, dur: .7, type: 'triangle', vol: .3, slide: 140 });
                         tone({ freq: 880, dur: .3, type: 'sine', vol: .18, delay: .4 }); },
    veh_ship:    () => { tone({ freq: 104, dur: .95, type: 'square', vol: .45, slide: -12 });  // หวูดเรือ
                         tone({ freq: 156, dur: .9, type: 'triangle', vol: .28, delay: .05 });
                         noise({ dur: .6, vol: .16, delay: .5, hp: 300 }); },               // คลื่นซัด
    veh_portal:  () => { tone({ freq: 180, dur: .6, type: 'sine', vol: .4, slide: 1500 });     // ดูดเข้ามิติ
                         tone({ freq: 1400, dur: .5, type: 'sine', vol: .25, delay: .3, slide: -1000 });
                         noise({ dur: .4, vol: .22, delay: .2, hp: 2400 }); },
    veh_caravan: () => { [0, .15, .28, .42].forEach(d => {                                     // เสียงกีบม้า
                           noise({ dur: .07, vol: .35, delay: d, hp: 500 });
                           tone({ freq: 96, dur: .09, type: 'triangle', vol: .32, delay: d }); });
                         tone({ freq: 1319, dur: .3, type: 'sine', vol: .2, delay: .2 }); },   // กระดิ่งเกวียน

    chest:   () => { noise({ dur: .09, vol: .45, hp: 1400 });          // สลักหีบดีดขึ้น
                     tone({ freq: 120, dur: .46, type: 'sawtooth', vol: .28, slide: 80 });  // ฝาไม้เอี๊ยด
                     [1319, 1568, 1976].forEach((f, i) =>              // แสงวาบจากในหีบ
                       tone({ freq: f, dur: .2, type: 'sine', vol: .3, delay: .3 + i * .07 })); },

    // ── กับดัก/หนีไม่รอด ──
    trap:    () => { noise({ dur: .3, vol: .75, hp: 200 });          // ตูมทึบ ๆ แล้วลากต่ำลง
                     tone({ freq: 140, dur: .34, type: 'sawtooth', vol: .55, slide: -90 });
                     tone({ freq: 90, dur: .4, type: 'square', vol: .4, delay: .05 }); },
    caught:  () => [0, .18].forEach(d => {                           // หนีไม่พ้น — เสียงเตือนสองที
                     tone({ freq: 330, dur: .15, type: 'sawtooth', vol: .5, delay: d, slide: -120 });
                     noise({ dur: .12, vol: .35, delay: d + .04, hp: 500 }); }),

    // ── รางวัล/ความสำเร็จ ──
    reward:  () => [523, 659, 784, 1047, 1319, 1568].forEach((f, i) => {
                     tone({ freq: f, dur: .22, type: 'square', vol: .42, delay: i * .08 });
                     tone({ freq: f / 2, dur: .22, type: 'triangle', vol: .3, delay: i * .08 }); }),

    // ── คาสิโน ──
    slot:    () => [0, .07, .14, .21, .28, .35, .42, .49].forEach(d =>   // วงล้อหมุน
                     noise({ dur: .05, vol: .3, delay: d, hp: 2600 })),
    reel:    () => { tone({ freq: 440, dur: .07, type: 'square', vol: .45 });   // วงล้อหยุดทีละอัน
                     noise({ dur: .05, vol: .3, hp: 1200 }); },
    card:    () => { noise({ dur: .07, vol: .4, hp: 3000 });                    // แจกไพ่
                     tone({ freq: 700, dur: .05, type: 'triangle', vol: .25 }); },
    bust:    () => { tone({ freq: 120, dur: .38, type: 'sawtooth', vol: .5, slide: -50 });
                     noise({ dur: .2, vol: .3, hp: 200 }); },

    // ── ธนาคาร/ทองคำ/ร้านค้า ──
    bank:    () => { tone({ freq: 1175, dur: .09, type: 'square', vol: .4 });   // กริ๊งเครื่องคิดเงิน
                     tone({ freq: 1568, dur: .16, type: 'square', vol: .35, delay: .07 });
                     noise({ dur: .1, vol: .2, delay: .07, hp: 3000 }); },
    gold:    () => { tone({ freq: 160, dur: .2, type: 'square', vol: .45 });    // แท่งหนัก ๆ วางลงโต๊ะ
                     noise({ dur: .12, vol: .35, hp: 1800 });
                     tone({ freq: 1568, dur: .5, type: 'sine', vol: .25, delay: .06 }); },
    buy:     () => { tone({ freq: 880, dur: .08, type: 'square', vol: .4 });
                     tone({ freq: 1319, dur: .14, type: 'square', vol: .38, delay: .07 }); },

    // ── สัตว์เลี้ยง ──
    pet:     () => { tone({ freq: 900, dur: .09, type: 'sine', vol: .4, slide: 500 });
                     tone({ freq: 1250, dur: .12, type: 'sine', vol: .35, delay: .09, slide: -300 }); },
  };

  // ══════ เพลงพื้นหลัง ══════
  // ลูปสั้น ๆ สังเคราะห์เอง: lead (ทำนอง) + bass (เบสต่ำลงหนึ่งช่วงเสียง) + perc (ไฮแฮต)
  // ตัวเลขคือระยะครึ่งเสียงจากโน้ตหลัก · null = พัก · หนึ่งช่อง = โน้ตเขบ็ต 1 ชั้น
  const MUSIC = {
    // 🌿 กลางแจ้ง — เมนหลัก/ป่าเอลฟ์/แดนลอยฟ้า
    field:  { bpm: 108, root: 196.00, wave: 'triangle', vol: .5,
              lead: [0, 4, 7, 4, 9, 7, 4, 2, 0, 4, 7, 12, 11, 9, 7, 4],
              bass: [0, null, 7, null, 5, null, 7, null] },
    // 🏘️ หมู่บ้าน — ช้า อุ่น ไว้ตอนแวะพัก
    town:   { bpm: 84, root: 261.63, wave: 'triangle', vol: .45,
              lead: [0, 2, 4, 7, 4, 2, 0, null, 5, 4, 2, 0, 2, null, null, null],
              bass: [0, null, 4, null, 5, null, 4, null] },
    // 💀 แดนมืด — ปีศาจ/นรก
    dark:   { bpm: 72, root: 146.83, wave: 'sawtooth', vol: .34,
              lead: [0, null, 3, null, 2, null, 0, null, -2, null, 0, null, 3, null, null, null],
              bass: [0, 0, null, 0, 3, null, null, null] },
    // 🔥 ภูเขาไฟ/แดนจักรกล — กระแทกเป็นจังหวะโรงตีเหล็ก
    forge:  { bpm: 120, root: 164.81, wave: 'square', vol: .32, perc: true,
              lead: [0, 0, 3, 0, 5, 3, 0, null, 0, 0, 3, 7, 5, 3, 2, 0],
              bass: [0, 0, 0, null, 3, 3, null, null] },
    // ❄️ น้ำแข็ง/ใต้ทะเล — ลอย ๆ ห่าง ๆ
    deep:   { bpm: 66, root: 220.00, wave: 'sine', vol: .45,
              lead: [0, null, 7, null, 5, null, 4, null, 2, null, 4, null, 0, null, null, null],
              bass: [0, null, null, null, 5, null, null, null] },
    // ⚔️ ต่อสู้ — เร็ว ดัน ๆ
    battle: { bpm: 152, root: 220.00, wave: 'square', vol: .34, perc: true,
              lead: [0, 7, 0, 7, 3, 7, 3, 7, 5, 7, 5, 7, 3, 2, 3, 5],
              bass: [0, 0, 3, 3, 5, 5, 2, 2] },
    // 🎰 คาสิโน — เริงร่าชวนเสียเงิน
    casino: { bpm: 128, root: 261.63, wave: 'square', vol: .3, perc: true,
              lead: [0, 4, 7, 10, 9, 7, 4, null, 5, 9, 12, 9, 7, 4, 2, null],
              bass: [0, null, 7, null, 5, null, 7, null] },
  };

  let wanted = null;        // เพลงที่ "ควรจะ" เล่นอยู่ — จำไว้เผื่อเบราว์เซอร์ยังไม่ยอมให้เปิดเสียง
  let timer = null;
  let nextAt = 0;           // นาทีทีของ ctx ที่ท่อนถัดไปต้องเริ่ม (กันเสียงขาดช่วงตอนต่อท่อน)

  const hz = (root, n) => root * Math.pow(2, n / 12);

  /** จองโน้ตทั้งท่อนไว้ล่วงหน้า — คืนความยาวท่อน (วินาที) */
  function queueBar(t, at) {
    const step = 60 / t.bpm / 2;
    t.lead.forEach((n, i) => {
      if (n === null) return;
      tone({ freq: hz(t.root, n), dur: step * .92, type: t.wave, vol: t.vol,
             delay: at + i * step, chan: 'mus' });
    });
    for (let i = 0; i < t.lead.length; i++) {
      const n = t.bass[i % t.bass.length];
      if (n !== null && i % 2 === 0)
        tone({ freq: hz(t.root, n - 12), dur: step * 1.6, type: 'triangle', vol: t.vol * .8,
               delay: at + i * step, chan: 'mus' });
      if (t.perc && i % 2 === 1)
        noise({ dur: .04, vol: .12, delay: at + i * step, hp: 5000, chan: 'mus' });
    }
    return t.lead.length * step;
  }

  /** จองท่อนถัดไปก่อนท่อนปัจจุบันจบ — ไม่งั้น setTimeout ที่เพี้ยนจะทำให้เพลงสะดุด */
  function pump() {
    timer = null;
    const t = MUSIC[wanted];
    if (!t || !on || !mon || !ensure()) return;
    const now = ctx.currentTime;
    if (nextAt < now) nextAt = now + .06;                  // เพิ่งเริ่ม/หลุดไปนาน → ตั้งต้นใหม่
    nextAt += queueBar(t, nextAt - now);
    timer = setTimeout(pump, Math.max(60, (nextAt - ctx.currentTime - .3) * 1000));
  }

  function halt() {
    if (timer) { clearTimeout(timer); timer = null; }
    nextAt = 0;
    // ทิ้งบัสทั้งก้อน — โน้ตที่จองคิวไว้แล้วจะเงียบทันที ไม่ต้องรอจนจบท่อน
    if (mbus) { try { mbus.disconnect(); } catch (e) { /* ปิดไปแล้วก็ช่าง */ } mbus = null; }
  }

  // 👣 ฝีเท้าตอนออกเดินทาง — ต้องเดินไปเรื่อย ๆ จนถึงที่หมาย ไม่ใช่ดังชุดเดียวจบ
  // (ระยะเวลาเดินไม่แน่นอน ขึ้นกับเซิร์ฟเวอร์ตอบเร็วแค่ไหน จึงต้องสั่งหยุดเอง)
  let feet = null, foot = 0;
  function feetLoop(go) {
    if (feet) { clearInterval(feet); feet = null; }
    if (!go) return;
    const step = () => { try { BANK[foot++ % 2 ? 'walk2' : 'walk'](); } catch (e) { /* ช่างมัน */ } };
    step();
    feet = setInterval(step, 290);
  }

  return {
    play(name) { try { (BANK[name] || (() => {}))(); } catch (e) { /* เสียงพังห้ามทำให้เกมพัง */ } },

    /** เริ่ม/หยุดเสียงฝีเท้า — เรียก walking(false) ทุกทางออก ไม่งั้นเดินไม่หยุด */
    walking(go) { try { feetLoop(!!go && on); } catch (e) { /* เสียงพังห้ามทำให้เกมพัง */ } },

    /** เปิดเพลงพื้นหลัง — เรียกซ้ำชื่อเดิมไม่รีสตาร์ท, ส่ง '' หรือ null เพื่อหยุด */
    music(name) {
      try {
        name = name && MUSIC[name] ? name : null;
        if (name === wanted) return;
        wanted = name;
        halt();
        if (name) pump();
      } catch (e) { /* เพลงพังห้ามทำให้เกมพัง */ }
    },

    get enabled() { return on; },
    get musicEnabled() { return mon; },

    toggle() {
      on = !on;
      localStorage.setItem('sfx', on ? 'on' : 'off');
      if (on) { ensure(); this.play('click'); if (wanted) { halt(); pump(); } }
      else { halt(); feetLoop(false); }        // ปิดเสียงกลางทางแล้วฝีเท้าต้องหยุดด้วย
      return on;
    },

    toggleMusic() {
      mon = !mon;
      localStorage.setItem('bgm', mon ? 'on' : 'off');
      halt();
      if (mon && wanted) pump();
      return mon;
    },

    /** สะกิดให้เพลงที่สั่งค้างไว้เริ่มเล่น หลังเบราว์เซอร์ยอมปลดล็อกเสียงแล้ว */
    resume() { try { if (wanted && !timer) { halt(); pump(); } } catch (e) { /* ไม่เป็นไร */ } },

    names() { return Object.keys(BANK); },
    tracks() { return Object.keys(MUSIC); },
  };
})();

// เบราว์เซอร์ปลดล็อกเสียงตอนผู้ใช้แตะจอครั้งแรกเท่านั้น — เพลงที่สั่งเปิดไว้ก่อนหน้านั้น
// จะเงียบไปเฉย ๆ จึงต้องสะกิดให้เริ่มใหม่ตอนแตะครั้งแรก
document.addEventListener('pointerdown', () => SFX.resume(), { once: true });
