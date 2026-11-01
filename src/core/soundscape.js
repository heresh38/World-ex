// Positional ambience: a pool of a few voices shared by many emitters. A world registers emitters (fountains, cafes,
// construction sites, trams, highways, the river, birds and crickets ...) with a position (or a function for moving
// sources), an audible radius, a loudness and an activity curve over the hour of day. Four times a second the nearest
// loud-enough emitters are picked; each gets a voice (procedural generator -> distance low-pass -> equal-power stereo
// pan -> gain) on the audio's ambience bus, so the master/effects volumes and the master bus (resetBus) apply. Voices of
// emitters that drop out fade and are torn down. Generators are cheap: one looping noise source and a filter or an
// oscillator or two, plus short scheduled one-shots (chirps, clinks, clanks, bubbles).
// All synthesis is procedural (src/core/audio.js has the noise buffer and tone/nz helpers).

const smooth = x => x <= 0 ? 0 : x >= 1 ? 1 : x * x * (3 - 2 * x);

// ---------------------------------------------------------------- generators: build(audio, dest, em) -> { tick(dt, k, em), nodes }
// k is the voice level 0..1 (distance and activity already applied by the gain); tick runs every update for one-shots.
const GEN = {
  // bubbling basin + falling water hiss, the odd big drop
  fountain(A, dest) {
    const c = A.ctx, hiss = A.noiseLoop(dest, 2200, 'bandpass', .6), low = A.noiseLoop(dest, 380, 'lowpass', .7);
    const hg = c.createGain(); hg.gain.value = .55; hiss.fl.disconnect(); hiss.fl.connect(hg); hg.connect(dest);
    const lg = c.createGain(); lg.gain.value = .5; low.fl.disconnect(); low.fl.connect(lg); lg.connect(dest);
    let t = 0;
    return { nodes: [hiss.src, low.src], tick(dt) {
      t -= dt; if (t > 0) return; t = .05 + Math.random() * .25;
      const now = c.currentTime, f = 500 + Math.random() * 900;
      A.tone(dest, now, .05 + Math.random() * .05, f, f * (1.5 + Math.random()), 'sine', .05 + Math.random() * .05);
    } };
  },
  // a terrace of people talking (formant-ish band noise swelling and falling), cups and cutlery, soft music in the evening
  cafe(A, dest, em) {
    const c = A.ctx, a = A.noiseLoop(dest, 520, 'bandpass', 1.4), b = A.noiseLoop(dest, 1500, 'bandpass', 2.2);
    const ga = c.createGain(), gb = c.createGain(); ga.gain.value = .5; gb.gain.value = .16;
    a.fl.disconnect(); a.fl.connect(ga); ga.connect(dest); b.fl.disconnect(); b.fl.connect(gb); gb.connect(dest);
    const mg = c.createGain(); mg.gain.value = 0; const mf = c.createBiquadFilter(); mf.type = 'lowpass'; mf.frequency.value = 1400; mf.connect(mg); mg.connect(dest);
    const osc = [0, 1, 2].map(i => { const o = c.createOscillator(); o.type = i ? 'triangle' : 'sine'; o.frequency.value = 220; const g = c.createGain(); g.gain.value = i ? .05 : .09; o.connect(g); g.connect(mf); o.start(); return o; });
    const CH = [[57, 64, 69], [55, 62, 67], [53, 60, 65], [52, 59, 64]], mtof = m => 440 * Math.pow(2, (m - 69) / 12);
    let tv = 0, tc = 0, tm = 0, ci = 0;
    return { nodes: [a.src, b.src, ...osc], tick(dt) {
      const now = c.currentTime;
      tv -= dt; if (tv <= 0) { tv = .25 + Math.random() * .6; ga.gain.setTargetAtTime(.25 + Math.random() * .55, now, .12); gb.gain.setTargetAtTime(.06 + Math.random() * .16, now, .08); a.fl.frequency.setTargetAtTime(420 + Math.random() * 260, now, .15); }
      tc -= dt; if (tc <= 0) { tc = .6 + Math.random() * 2.5; const f = 2400 + Math.random() * 2600; A.tone(dest, now, .12, f, f * .98, 'triangle', .035 + Math.random() * .03); if (Math.random() < .3) A.tone(dest, now + .07, .1, f * 1.2, f * 1.18, 'triangle', .025); }
      const music = em.music ? em.music() : 0;
      mg.gain.setTargetAtTime(music * .9, now, .8);
      tm -= dt; if (music > .01 && tm <= 0) { tm = 3.2; const ch = CH[ci++ % CH.length]; osc.forEach((o, i) => o.frequency.setTargetAtTime(mtof(ch[i] - (i ? 0 : 12)), now, .25)); }
    } };
  },
  // working hours: hammer clanks, an angle grinder now and then, the crane's slewing motor
  construction(A, dest) {
    const c = A.ctx, mot = c.createOscillator(); mot.type = 'sawtooth'; mot.frequency.value = 58;
    const mf = c.createBiquadFilter(); mf.type = 'lowpass'; mf.frequency.value = 240; const mg = c.createGain(); mg.gain.value = .0;
    mot.connect(mf); mf.connect(mg); mg.connect(dest); mot.start();
    const gr = A.noiseLoop(dest, 3800, 'bandpass', 3); const gg = c.createGain(); gg.gain.value = 0; gr.fl.disconnect(); gr.fl.connect(gg); gg.connect(dest);
    let tk = 0, tg = 3 + Math.random() * 5, tmo = 0, grind = 0;
    return { nodes: [mot, gr.src], tick(dt) {
      const now = c.currentTime;
      tk -= dt; if (tk <= 0) {
        tk = .35 + Math.random() * (Math.random() < .3 ? 2.5 : .7);
        const f = 380 + Math.random() * 700, v = .14 + Math.random() * .14;
        A.tone(dest, now, .16, f, f * .97, 'triangle', v); A.tone(dest, now, .09, f * 2.7, f * 2.6, 'square', v * .12); A.nz(dest, now, .06, 3000, 900, 2, 'bandpass', v * .7);
      }
      tg -= dt; if (tg <= 0) { if (grind > 0) { grind = 0; gg.gain.setTargetAtTime(0, now, .1); tg = 5 + Math.random() * 12; } else { grind = 1; gg.gain.setTargetAtTime(.22, now, .05); gr.fl.frequency.setValueAtTime(3200 + Math.random() * 1600, now); tg = 1.5 + Math.random() * 3; } }
      if (grind) gr.fl.frequency.setTargetAtTime(3000 + Math.random() * 2200, now, .08);
      tmo -= dt; if (tmo <= 0) { tmo = 2 + Math.random() * 6; const on = Math.random() < .5; mg.gain.setTargetAtTime(on ? .22 : 0, now, .6); mot.frequency.setTargetAtTime(on ? 52 + Math.random() * 14 : 48, now, .8); }
    } };
  },
  // a tram: traction hum rising with speed, wheel clatter over rail joints, the bell when it leaves a stop
  tram(A, dest, em) {
    const c = A.ctx, o = c.createOscillator(); o.type = 'sawtooth'; o.frequency.value = 90;
    const f = c.createBiquadFilter(); f.type = 'lowpass'; f.frequency.value = 500; const og = c.createGain(); og.gain.value = 0;
    o.connect(f); f.connect(og); og.connect(dest); o.start();
    const w = c.createOscillator(); w.type = 'sine'; w.frequency.value = 600; const wg = c.createGain(); wg.gain.value = 0; w.connect(wg); wg.connect(dest); w.start();
    const rumble = A.noiseLoop(dest, 300, 'lowpass', .8); const rg = c.createGain(); rg.gain.value = 0; rumble.fl.disconnect(); rumble.fl.connect(rg); rg.connect(dest);
    let joint = 0, waiting = null;
    return { nodes: [o, w, rumble.src], tick(dt) {
      const now = c.currentTime, T = em.tram, v = T ? T.v : 0, k = Math.min(1, v / 12);
      og.gain.setTargetAtTime(.08 + .22 * k, now, .2); o.frequency.setTargetAtTime(70 + v * 9, now, .3);
      wg.gain.setTargetAtTime(.025 * k, now, .3); w.frequency.setTargetAtTime(380 + v * 55, now, .3);
      rg.gain.setTargetAtTime(.35 * k, now, .2);
      if (v > .5) { joint -= dt * v; if (joint <= 0) { joint = 12; A.nz(dest, now, .05, 1800, 600, 1.5, 'bandpass', .3 * k); A.nz(dest, now + .09, .05, 1700, 600, 1.5, 'bandpass', .26 * k); } }
      const w2 = !!(T && T.wait > 0);
      if (waiting === true && !w2 && T) for (const [dt2, fr] of [[0, 1245], [.32, 1245]]) { A.tone(dest, now + dt2, .9, fr, fr, 'sine', .22); A.tone(dest, now + dt2, .6, fr * 2.76, fr * 2.76, 'sine', .06); }
      waiting = w2;
    } };
  },
  // steady highway roar with passing swells
  traffic(A, dest) {
    const c = A.ctx, a = A.noiseLoop(dest, 650, 'lowpass', .6), b = A.noiseLoop(dest, 1900, 'bandpass', .7);
    const ag = c.createGain(), bg = c.createGain(); ag.gain.value = .6; bg.gain.value = .12;
    a.fl.disconnect(); a.fl.connect(ag); ag.connect(dest); b.fl.disconnect(); b.fl.connect(bg); bg.connect(dest);
    let t = 0;
    return { nodes: [a.src, b.src], tick(dt) {
      t -= dt; if (t > 0) return; t = 1.5 + Math.random() * 3; const now = c.currentTime;
      ag.gain.setTargetAtTime(.4 + Math.random() * .5, now, .9); bg.gain.setTargetAtTime(.06 + Math.random() * .16, now, .7); b.fl.frequency.setTargetAtTime(1500 + Math.random() * 900, now, 1.2);
    } };
  },
  // water lapping at the quay wall
  river(A, dest) {
    const c = A.ctx, a = A.noiseLoop(dest, 600, 'bandpass', 1.1); const ag = c.createGain(); ag.gain.value = .3; a.fl.disconnect(); a.fl.connect(ag); ag.connect(dest);
    let t = 0, tp = 1;
    return { nodes: [a.src], tick(dt) {
      const now = c.currentTime;
      t -= dt; if (t <= 0) { t = .4 + Math.random() * 1.1; ag.gain.setTargetAtTime(.15 + Math.random() * .45, now, .18); a.fl.frequency.setTargetAtTime(380 + Math.random() * 500, now, .25); }
      tp -= dt; if (tp <= 0) { tp = .8 + Math.random() * 2.5; const f = 180 + Math.random() * 260; A.tone(dest, now, .12, f, f * 2.2, 'sine', .08); }
    } };
  },
  // birds by day, crickets at night (em.night() 0..1), wind in the leaves
  nature(A, dest, em) {
    const c = A.ctx, cr = c.createOscillator(); cr.type = 'sine'; cr.frequency.value = 4300 + Math.random() * 500;
    const cg = c.createGain(); cg.gain.value = 0; const pul = c.createOscillator(); pul.type = 'square'; pul.frequency.value = 26 + Math.random() * 8;
    const pg = c.createGain(); pg.gain.value = .5; pul.connect(pg); pg.connect(cg.gain);
    const cm = c.createGain(); cm.gain.value = 0; cr.connect(cg); cg.connect(cm); cm.connect(dest); cr.start(); pul.start();
    const wind = A.noiseLoop(dest, 900, 'bandpass', .9); const wg = c.createGain(); wg.gain.value = .08; wind.fl.disconnect(); wind.fl.connect(wg); wg.connect(dest);
    let tb = Math.random() * 2, tc = 0, tw = 0;
    return { nodes: [cr, pul, wind.src], tick(dt) {
      const now = c.currentTime, n = em.night ? em.night() : 0;
      // crickets: chirp groups gated on and off
      tc -= dt; if (tc <= 0) { tc = .3 + Math.random() * .9; cm.gain.setTargetAtTime(n * (Math.random() < .7 ? .06 : 0), now, .04); }
      tw -= dt; if (tw <= 0) { tw = 2 + Math.random() * 4; wg.gain.setTargetAtTime(.04 + Math.random() * .08 + n * .04, now, 1.2); wind.fl.frequency.setTargetAtTime(600 + Math.random() * 700, now, 1.5); }
      // birdsong: short phrases of sweeping whistles and chips
      tb -= dt; if (tb <= 0 && n < .6) {
        tb = .8 + Math.random() * 3.5;
        const kind = Math.random(), base = 2600 + Math.random() * 2600, nn = 2 + Math.floor(Math.random() * 5), v = (.05 + Math.random() * .05) * (1 - n);
        for (let i = 0; i < nn; i++) {
          const at = now + i * (.09 + Math.random() * .08);
          if (kind < .5) A.tone(dest, at, .07, base * (1 + Math.random() * .3), base * (.75 + Math.random() * .5), 'sine', v);
          else if (kind < .8) A.tone(dest, at, .11, base * .8, base * 1.35, 'sine', v);
          else A.tone(dest, at, .04, base * 1.4, base * 1.3, 'triangle', v * .6);
        }
      }
    } };
  },
};

export class Soundscape {
  constructor(audio, { voices = 6 } = {}) {
    this.A = audio; this.max = voices;
    this.emitters = []; this.voices = []; this.t = 0; this.peak = 0;
    this._p = { x: 0, y: 0, z: 0 };
  }

  // em: { kind, pos: {x,y,z} | () => {x,y,z}, r (audible radius m), gain, active: hour => 0..1, ...generator extras }
  add(em) { em.gain = em.gain ?? 1; em.r = em.r || 60; this.emitters.push(em); return em; }

  where(em) { return typeof em.pos === 'function' ? em.pos(this._p) : em.pos; }

  level(em, lp, hour) {
    const p = this.where(em); if (!p) return 0;
    const dx = p.x - lp.x, dy = (p.y || 0) - lp.y, dz = p.z - lp.z, d = Math.sqrt(dx * dx + dy * dy + dz * dz);
    if (d > em.r) return 0;
    const act = em.active ? em.active(hour) : 1; if (act <= .01) return 0;
    return em.gain * act / (1 + (d / (em.r * .22)) ** 2) * (1 - smooth((d - em.r * .7) / (em.r * .3)));
  }

  update(dt, lp, yaw, hour) {
    const A = this.A; if (!A.ready || !A.ctx || A.ctx.state !== 'running') return;
    this.t -= dt;
    if (this.t <= 0) {
      this.t = .25;
      const scored = [];
      for (const em of this.emitters) { const l = this.level(em, lp, hour); if (l > .004) scored.push([l, em]); }
      scored.sort((a, b) => b[0] - a[0]);
      const want = new Set(scored.slice(0, this.max).map(s => s[1]));
      for (const v of this.voices) if (!v.dying && !want.has(v.em)) this.release(v);
      for (const em of want) if (!this.voices.some(v => v.em === em && !v.dying) && this.voices.filter(v => !v.dying).length < this.max) this.voice(em);
    }
    // per-frame: gain, pan and distance filtering of each voice; generator one-shots
    const c = A.ctx, now = c.currentTime, rx = Math.cos(yaw), rz = -Math.sin(yaw);
    for (let i = this.voices.length - 1; i >= 0; i--) {
      const v = this.voices[i];
      if (v.dying) { if (now > v.dieAt) { this.kill(v); this.voices.splice(i, 1); } continue; }
      const p = this.where(v.em); if (!p) continue;
      const dx = p.x - lp.x, dy = (p.y || 0) - lp.y, dz = p.z - lp.z, d = Math.sqrt(dx * dx + dy * dy + dz * dz);
      const l = this.level(v.em, lp, hour);
      v.g.gain.setTargetAtTime(l, now, .12);
      v.pan.pan.setTargetAtTime(d > .5 ? Math.max(-1, Math.min(1, (dx * rx + dz * rz) / d)) * .85 : 0, now, .08);
      v.lp.frequency.setTargetAtTime(700 + 15000 / (1 + d / 14), now, .2);
      try { v.gen.tick(dt, l, v.em); } catch (e) { /* a generator must never break the frame */ }
    }
    this.peak = Math.max(this.peak, this.voices.filter(v => !v.dying).length);
  }

  voice(em) {
    const A = this.A, c = A.ctx;
    const g = c.createGain(); g.gain.value = 0;
    const pan = c.createStereoPanner(), lp = c.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = 4000;
    const src = c.createGain(); src.gain.value = 1;
    src.connect(lp); lp.connect(pan); pan.connect(g); g.connect(A.amb);
    const gen = (GEN[em.kind] || GEN.traffic)(A, src, em);
    this.voices.push({ em, g, pan, lp, src, gen });
  }

  release(v) { v.dying = true; v.dieAt = this.A.ctx.currentTime + 1.2; v.g.gain.setTargetAtTime(0, this.A.ctx.currentTime, .3); }

  kill(v) {
    for (const n of v.gen.nodes || []) { try { n.stop(); } catch (e) { /* not started */ } }
    try { v.g.disconnect(); v.src.disconnect(); } catch (e) { /* gone */ }
  }

  stats() { return { emitters: this.emitters.length, voices: this.voices.filter(v => !v.dying).length, fading: this.voices.filter(v => v.dying).length, max: this.max, peak: this.peak, kinds: this.voices.filter(v => !v.dying).map(v => v.em.kind) }; }

  dispose() { for (const v of this.voices) this.kill(v); this.voices = []; this.emitters = []; }
}
