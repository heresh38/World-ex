// Procedural audio: every sound is synthesised with WebAudio (no sample files).
// Positional one-shots are panned/attenuated relative to the listener set each frame.
const MUSIC = {
  ship: { root: 45, chords: [[0, 7, 12, 16], [5, 12, 17, 21], [3, 10, 15, 19], [7, 14, 19, 22]], tempo: 7, bright: 900 },
  earth: { root: 43, chords: [[0, 7, 14, 16], [-2, 5, 12, 17], [3, 10, 14, 19], [5, 12, 16, 21]], tempo: 6, bright: 1300 },
  planet: { root: 40, chords: [[0, 7, 12, 15], [-4, 3, 8, 12], [-2, 5, 10, 14], [-5, 2, 7, 10]], tempo: 8, bright: 700 },
  title: { root: 38, chords: [[0, 7, 12, 19], [-4, 3, 12, 15], [-7, 0, 9, 12], [-2, 5, 10, 17]], tempo: 9, bright: 800 },
};
const mtof = m => 440 * Math.pow(2, (m - 69) / 12);

export class Audio {
  constructor(settings) {
    this.settings = settings;
    this.ctx = null; this.ready = false;
    this.lp = { x: 0, y: 0, z: 0 }; this.lyaw = 0;
    this.loops = {};
    this.combat = 0;
  }

  // Must be called from a user gesture.
  start() {
    if (this.ctx) { if (this.ctx.state === 'suspended') this.ctx.resume(); return; }
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return;
    const c = this.ctx = new AC();
    this.master = c.createGain(); this.master.connect(c.destination);
    const comp = c.createDynamicsCompressor(); comp.threshold.value = -14; comp.ratio.value = 4;
    comp.connect(this.master);
    this.bus = comp;
    this.sfx = c.createGain(); this.sfx.connect(comp);
    this.mus = c.createGain(); this.mus.connect(comp);
    this.amb = c.createGain(); this.amb.connect(comp);
    // shared reverb for music/ambience
    this.verb = c.createConvolver(); this.verb.buffer = this.impulse(2.8);
    const vg = c.createGain(); vg.gain.value = .35; this.verb.connect(vg); vg.connect(comp);
    const len = c.sampleRate * 2;
    this.noise = c.createBuffer(1, len, c.sampleRate);
    const d = this.noise.getChannelData(0);
    for (let i = 0; i < len; i++) d[i] = Math.random() * 2 - 1;
    this.ready = true;
    this.applyVolumes();
  }

  impulse(sec) {
    const c = this.ctx, n = c.sampleRate * sec, b = c.createBuffer(2, n, c.sampleRate);
    for (let ch = 0; ch < 2; ch++) {
      const d = b.getChannelData(ch);
      for (let i = 0; i < n; i++) d[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / n, 3);
    }
    return b;
  }

  applyVolumes() {
    if (!this.ready) return;
    const s = this.settings, t = this.ctx.currentTime;
    this.master.gain.setTargetAtTime(s.muted ? 0 : s.master, t, .05);
    this.sfx.gain.setTargetAtTime(s.sfx, t, .05);
    this.mus.gain.setTargetAtTime(s.music * .55, t, .05);
    this.amb.gain.setTargetAtTime(s.sfx * .8, t, .05);
  }

  listener(p, yaw) { this.lp = p; this.lyaw = yaw; }

  // gain/pan for a world position
  spatial(pos, range = 60) {
    if (!pos) return { g: 1, pan: 0 };
    const dx = pos.x - this.lp.x, dy = (pos.y || 0) - this.lp.y, dz = pos.z - this.lp.z;
    const d = Math.sqrt(dx * dx + dy * dy + dz * dz);
    const g = 1 / (1 + (d / (range * .25)) ** 2);
    // listener right vector for yaw (camera looks toward -sin(yaw), -cos(yaw))
    const rx = Math.cos(this.lyaw), rz = -Math.sin(this.lyaw);
    const pan = d > .01 ? Math.max(-1, Math.min(1, (dx * rx + dz * rz) / d)) : 0;
    return { g, pan };
  }

  out(pos, range) {
    const c = this.ctx, g = c.createGain(), p = c.createStereoPanner();
    const s = this.spatial(pos, range);
    g.gain.value = s.g; p.pan.value = s.pan * .8;
    g.connect(p); p.connect(this.sfx);
    return g;
  }

  nz(dest, t, dur, f0, f1, q = 1, type = 'lowpass', vol = 1, attack = .002) {
    const c = this.ctx, src = c.createBufferSource(); src.buffer = this.noise;
    src.playbackRate.value = .8 + Math.random() * .4;
    const f = c.createBiquadFilter(); f.type = type; f.Q.value = q;
    f.frequency.setValueAtTime(f0, t); f.frequency.exponentialRampToValueAtTime(Math.max(20, f1), t + dur);
    const g = c.createGain(); g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(vol, t + attack);
    g.gain.exponentialRampToValueAtTime(.0008, t + dur);
    src.connect(f); f.connect(g); g.connect(dest);
    src.start(t, Math.random() * 1.5); src.stop(t + dur + .05);
  }

  tone(dest, t, dur, f0, f1, type = 'sine', vol = 1, attack = .003) {
    const c = this.ctx, o = c.createOscillator(); o.type = type;
    o.frequency.setValueAtTime(f0, t); o.frequency.exponentialRampToValueAtTime(Math.max(20, f1), t + dur);
    const g = c.createGain(); g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(vol, t + attack);
    g.gain.exponentialRampToValueAtTime(.0008, t + dur);
    o.connect(g); g.connect(dest); o.start(t); o.stop(t + dur + .05);
  }

  // ------------------------------------------------------------- one-shots
  shot(kind, pos = null, enemy = false) {
    if (!this.ready) return;
    const t = this.ctx.currentTime, o = this.out(pos, enemy ? 90 : 200);
    const v = enemy ? .55 : .9;
    switch (kind) {
      case 'auto': this.nz(o, t, .12, 4200, 600, .7, 'lowpass', v); this.tone(o, t, .09, 160, 55, 'triangle', v * .8); break;
      case 'pulse': this.nz(o, t, .09, 5200, 900, 1, 'bandpass', v); this.tone(o, t, .08, 640, 180, 'square', v * .18); break;
      case 'scout': this.nz(o, t, .2, 3000, 300, .8, 'lowpass', v); this.tone(o, t, .16, 140, 45, 'triangle', v); break;
      case 'handcannon': this.nz(o, t, .32, 2600, 200, .7, 'lowpass', v * 1.1); this.tone(o, t, .25, 110, 38, 'sine', v * 1.2); break;
      case 'shotgun': this.nz(o, t, .38, 2200, 150, .6, 'lowpass', v * 1.2); this.tone(o, t, .3, 90, 35, 'sine', v * 1.3); break;
      case 'sniper': this.nz(o, t, .6, 3600, 120, .6, 'lowpass', v * 1.2); this.tone(o, t, .45, 120, 30, 'sine', v * 1.3);
        this.nz(o, t + .05, .9, 900, 80, .5, 'lowpass', v * .3, .05); break;
      case 'rocket': this.nz(o, t, .6, 600, 2400, .8, 'bandpass', v * .8, .03); this.tone(o, t, .4, 90, 200, 'sawtooth', v * .1); break;
      case 'smg': this.nz(o, t, .08, 5200, 900, .8, 'lowpass', v * .8); this.tone(o, t, .06, 220, 90, 'triangle', v * .6); break;
      case 'sidearm': this.nz(o, t, .14, 3800, 400, .8, 'lowpass', v * .9); this.tone(o, t, .1, 180, 60, 'triangle', v * .8); break;
      case 'hmg': this.nz(o, t, .1, 2600, 300, .7, 'lowpass', v); this.tone(o, t, .08, 110, 45, 'sine', v); break;
      case 'energy': this.tone(o, t, .35, 1400, 300, 'sawtooth', v * .14); this.tone(o, t, .3, 220, 70, 'sine', v); this.nz(o, t, .25, 6000, 1200, 2, 'bandpass', v * .5); break;
      case 'bolt': this.tone(o, t, .18, 900, 220, 'sawtooth', v * .16); this.nz(o, t, .12, 3000, 800, 2, 'bandpass', v * .5); break;
      // kinetic firearms: sharp crack + body thump, mechanical tails (bolt throw, pump rack)
      case 'rifle': this.nz(o, t, .16, 3400, 380, .7, 'lowpass', v * 1.05); this.tone(o, t, .12, 150, 48, 'triangle', v * .9); this.nz(o, t, .03, 7000, 3000, 1, 'highpass', v * .4); break;
      case 'carbine': this.nz(o, t, .12, 4600, 500, .7, 'lowpass', v); this.tone(o, t, .09, 170, 60, 'triangle', v * .75); this.nz(o, t, .025, 8000, 4000, 1, 'highpass', v * .45); break;
      case 'dmr': this.nz(o, t, .28, 3000, 220, .7, 'lowpass', v * 1.15); this.tone(o, t, .2, 120, 40, 'sine', v * 1.1); this.nz(o, t + .04, .5, 900, 90, .5, 'lowpass', v * .25, .04); break;
      case 'ksmg': this.nz(o, t, .07, 4200, 700, .8, 'lowpass', v * .75); this.tone(o, t, .05, 240, 100, 'triangle', v * .5); break;
      case 'boltaction': this.nz(o, t, .7, 3200, 100, .6, 'lowpass', v * 1.3); this.tone(o, t, .5, 110, 28, 'sine', v * 1.4);
        this.nz(o, t + .06, 1.1, 800, 70, .5, 'lowpass', v * .35, .06);
        this.nz(o, t + .55, .06, 2600, 1200, 3, 'bandpass', v * .3); this.nz(o, t + .75, .07, 3200, 1500, 3, 'bandpass', v * .35); break;
      case 'pistol': this.nz(o, t, .13, 4000, 420, .8, 'lowpass', v * .9); this.tone(o, t, .09, 200, 70, 'triangle', v * .7); break;
      case 'revolver': this.nz(o, t, .34, 2400, 180, .7, 'lowpass', v * 1.15); this.tone(o, t, .26, 105, 36, 'sine', v * 1.25); break;
      case 'pump': this.nz(o, t, .4, 2000, 140, .6, 'lowpass', v * 1.2); this.tone(o, t, .3, 85, 33, 'sine', v * 1.3);
        this.nz(o, t + .38, .09, 1800, 700, 2, 'bandpass', v * .35); this.nz(o, t + .52, .08, 2400, 900, 2, 'bandpass', v * .4); break;
      // horror: wet hawks, retching gurgles, a heavy womb-pop
      case 'spit': this.nz(o, t, .18, 900, 2400, 3, 'bandpass', v * .5, .01); this.tone(o, t, .12, 180, 420, 'sine', v * .35); this.nz(o, t + .04, .14, 600, 200, 4, 'bandpass', v * .3); break;
      case 'bile': this.nz(o, t, .55, 300, 900, 5, 'bandpass', v * .7, .03); this.tone(o, t, .5, 70, 45, 'sawtooth', v * .12, .04);
        for (let k = 0; k < 5; k++) this.tone(o, t + .05 + k * .07, .06, 260 + Math.random() * 300, 120, 'sine', v * .18); break;
      case 'brood': this.tone(o, t, .25, 90, 220, 'sine', v * .9, .01); this.nz(o, t, .3, 400, 1600, 4, 'bandpass', v * .5, .01);
        this.nz(o, t + .12, .5, 500, 150, 3, 'bandpass', v * .3, .05); break;
      default: this.nz(o, t, .12, 3000, 400, .7, 'lowpass', v);
    }
  }

  explosion(pos) {
    if (!this.ready) return;
    const t = this.ctx.currentTime, o = this.out(pos, 260);
    this.nz(o, t, 1.4, 1800, 60, .5, 'lowpass', 1.3, .005);
    this.tone(o, t, .9, 70, 24, 'sine', 1.4);
    this.nz(o, t + .08, 1.8, 500, 40, .5, 'lowpass', .5, .1);
  }

  // a glob of slime bursting on something (horror weapons)
  splat(pos, big = false) {
    if (!this.ready) return;
    const t = this.ctx.currentTime, o = this.out(pos, 50);
    this.nz(o, t, big ? .4 : .2, 1400, 250, 3, 'bandpass', big ? .6 : .35, .005);
    this.tone(o, t, .12, big ? 160 : 260, 60, 'sine', big ? .4 : .2);
  }

  hit(crit, kill) {
    if (!this.ready) return;
    const t = this.ctx.currentTime;
    this.tone(this.sfx, t, .06, crit ? 2400 : 1500, crit ? 1800 : 1200, 'square', .06);
    if (kill) { this.tone(this.sfx, t + .03, .22, 520, 260, 'triangle', .22); this.nz(this.sfx, t, .3, 3000, 400, 1, 'bandpass', .2); }
  }

  step(run, surface = 'metal') {
    if (!this.ready) return;
    const t = this.ctx.currentTime, v = run ? .22 : .13;
    if (surface === 'metal') { this.nz(this.sfx, t, .08, 2600, 900, 2, 'bandpass', v); this.tone(this.sfx, t, .05, 180, 90, 'triangle', v * .4); }
    else if (surface === 'snow' || surface === 'sand') this.nz(this.sfx, t, .14, 1400, 300, .7, 'lowpass', v * 1.2, .02);
    else this.nz(this.sfx, t, .09, 1800, 250, .8, 'lowpass', v);
  }

  land() { if (this.ready) { const t = this.ctx.currentTime; this.nz(this.sfx, t, .18, 1200, 120, .6, 'lowpass', .35); } }
  jump() { if (this.ready) { const t = this.ctx.currentTime; this.nz(this.sfx, t, .25, 400, 2400, 1, 'bandpass', .12, .05); } }

  ui(kind = 'click') {
    if (!this.ready) return;
    const t = this.ctx.currentTime, s = this.sfx;
    if (kind === 'hover') this.tone(s, t, .05, 1800, 1700, 'sine', .04);
    else if (kind === 'confirm') { this.tone(s, t, .12, 880, 880, 'triangle', .12); this.tone(s, t + .08, .2, 1320, 1320, 'triangle', .1); }
    else if (kind === 'back') this.tone(s, t, .12, 660, 440, 'triangle', .1);
    else if (kind === 'open') { this.nz(s, t, .35, 300, 3000, 1.2, 'bandpass', .12, .1); this.tone(s, t, .3, 220, 440, 'sine', .08, .05); }
    else if (kind === 'deny') { this.tone(s, t, .12, 200, 160, 'square', .06); }
    else this.tone(s, t, .05, 1200, 1000, 'triangle', .08);
  }

  pickup(rarity = 0) {
    if (!this.ready) return;
    const t = this.ctx.currentTime, notes = [0, 4, 7, 12, 16, 19].slice(0, 2 + rarity);
    notes.forEach((n, i) => this.tone(this.sfx, t + i * .06, .35, mtof(76 + n), mtof(76 + n), 'triangle', .1));
    if (rarity >= 3) this.nz(this.sfx, t, 1.0, 6000, 2000, 1, 'highpass', .08, .2);
  }

  ammo() { if (this.ready) { const t = this.ctx.currentTime; this.tone(this.sfx, t, .08, 900, 1200, 'square', .04); } }
  reload(stage = 0) {
    if (!this.ready) return;
    const t = this.ctx.currentTime;
    this.nz(this.sfx, t, .07, stage ? 3500 : 1800, 900, 3, 'bandpass', .3);
    this.tone(this.sfx, t, .04, stage ? 900 : 500, 300, 'square', .05);
  }
  empty() { if (this.ready) this.tone(this.sfx, this.ctx.currentTime, .04, 1400, 900, 'square', .05); }
  hurt() { if (this.ready) { const t = this.ctx.currentTime; this.nz(this.sfx, t, .25, 900, 150, .8, 'lowpass', .35); this.tone(this.sfx, t, .2, 160, 70, 'sine', .3); } }
  shieldBreak() {
    if (!this.ready) return;
    const t = this.ctx.currentTime;
    this.nz(this.sfx, t, .6, 7000, 500, 2, 'bandpass', .3); this.tone(this.sfx, t, .5, 1400, 200, 'sawtooth', .06);
  }
  shieldUp() { if (this.ready) { const t = this.ctx.currentTime; this.tone(this.sfx, t, .5, 300, 900, 'sine', .07, .1); } }
  levelUp() { if (this.ready) { const t = this.ctx.currentTime;[0, 4, 7, 12, 16].forEach((n, i) => this.tone(this.sfx, t + i * .09, .7, mtof(72 + n), mtof(72 + n), 'triangle', .1)); } }
  alert(pos) { if (this.ready) { const t = this.ctx.currentTime, o = this.out(pos, 80); this.tone(o, t, .15, 700, 900, 'square', .08); this.tone(o, t + .16, .15, 700, 900, 'square', .08); } }
  warp() {
    if (!this.ready) return;
    const t = this.ctx.currentTime;
    this.nz(this.sfx, t, 2.6, 120, 4000, 1.5, 'bandpass', .5, 1.4);
    this.tone(this.sfx, t, 2.6, 50, 300, 'sawtooth', .08, 1.5);
    this.tone(this.sfx, t + 2.2, 1.6, 90, 30, 'sine', .6, .02);
  }
  door() { if (this.ready) { const t = this.ctx.currentTime; this.nz(this.sfx, t, .7, 200, 900, 1, 'bandpass', .25, .1); } }

  // ------------------------------------------------------------- loops
  loop(name, build) {
    if (!this.ready || this.loops[name]) return this.loops[name];
    const l = build();
    this.loops[name] = l;
    return l;
  }

  stopLoop(name) {
    const l = this.loops[name]; if (!l) return;
    const t = this.ctx.currentTime;
    l.gain.gain.setTargetAtTime(0, t, .3);
    setTimeout(() => { l.nodes.forEach(n => { try { n.stop(); } catch (e) { /* not started */ } }); l.gain.disconnect(); }, 1500);
    delete this.loops[name];
  }

  stopAllLoops() { Object.keys(this.loops).forEach(k => this.stopLoop(k)); }

  noiseLoop(dest, f, type = 'lowpass', q = .7) {
    const c = this.ctx, src = c.createBufferSource(); src.buffer = this.noise; src.loop = true;
    const fl = c.createBiquadFilter(); fl.type = type; fl.frequency.value = f; fl.Q.value = q;
    src.connect(fl); fl.connect(dest); src.start();
    return { src, fl };
  }

  ambience(kind) {
    if (!this.ready) return;
    ['amb_ship', 'amb_city', 'amb_wind'].forEach(k => this.stopLoop(k));
    const c = this.ctx;
    if (kind === 'ship') {
      this.loop('amb_ship', () => {
        const g = c.createGain(); g.gain.value = 0; g.connect(this.amb); g.gain.setTargetAtTime(.5, c.currentTime, 1);
        const nodes = [];
        [41, 55.2, 82.5].forEach((f, i) => { const o = c.createOscillator(); o.frequency.value = f; o.type = i ? 'sine' : 'triangle'; const og = c.createGain(); og.gain.value = [.16, .08, .03][i]; o.connect(og); og.connect(g); o.start(); nodes.push(o); });
        const n = this.noiseLoop(g, 380); nodes.push(n.src);
        const ng = c.createGain(); ng.gain.value = .05; n.fl.disconnect(); n.fl.connect(ng); ng.connect(g);
        return { gain: g, nodes };
      });
    } else if (kind === 'city') {
      this.loop('amb_city', () => {
        const g = c.createGain(); g.gain.value = 0; g.connect(this.amb); g.gain.setTargetAtTime(.45, c.currentTime, 1);
        const a = this.noiseLoop(g, 500, 'lowpass', .5), b = this.noiseLoop(g, 2400, 'bandpass', .4);
        const lfo = c.createOscillator(); lfo.frequency.value = .07; const lg = c.createGain(); lg.gain.value = 250; lfo.connect(lg); lg.connect(a.fl.frequency); lfo.start();
        const bg = c.createGain(); bg.gain.value = .15; b.fl.disconnect(); b.fl.connect(bg); bg.connect(g);
        return { gain: g, nodes: [a.src, b.src, lfo] };
      });
    } else if (kind === 'wind') {
      this.loop('amb_wind', () => {
        const g = c.createGain(); g.gain.value = 0; g.connect(this.amb); g.gain.setTargetAtTime(.5, c.currentTime, 1.5);
        const a = this.noiseLoop(g, 600, 'bandpass', 1.2);
        const lfo = c.createOscillator(); lfo.frequency.value = .11; const lg = c.createGain(); lg.gain.value = 380; lfo.connect(lg); lg.connect(a.fl.frequency); lfo.start();
        return { gain: g, nodes: [a.src, lfo] };
      });
    }
  }

  // welding crackle: a looping source whose gain the caller modulates by distance
  weldLoop() {
    return this.loop('weld', () => {
      const c = this.ctx, g = c.createGain(); g.gain.value = 0; const p = c.createStereoPanner(); g.connect(p); p.connect(this.sfx);
      const a = this.noiseLoop(g, 3800, 'highpass', .8);
      const crackle = c.createGain(); a.fl.disconnect(); a.fl.connect(crackle); crackle.connect(g);
      const hum = c.createOscillator(); hum.type = 'sawtooth'; hum.frequency.value = 100; const hg = c.createGain(); hg.gain.value = .03; hum.connect(hg); hg.connect(g); hum.start();
      return { gain: g, pan: p, crackle, nodes: [a.src, hum] };
    });
  }

  updateWeld(pos, on) {
    const l = this.loops.weld; if (!l) return;
    const s = this.spatial(pos, 30), t = this.ctx.currentTime;
    l.gain.gain.setTargetAtTime(on ? s.g * .5 : 0, t, .03);
    l.pan.pan.setTargetAtTime(s.pan * .8, t, .05);
    l.crackle.gain.setTargetAtTime(Math.random() < .5 ? .2 : 1, t, .01);
  }

  carLoop() {
    return this.loop('car', () => {
      const c = this.ctx, g = c.createGain(); g.gain.value = 0; g.connect(this.sfx);
      const o = c.createOscillator(); o.type = 'sawtooth'; o.frequency.value = 60;
      const f = c.createBiquadFilter(); f.type = 'lowpass'; f.frequency.value = 400;
      const og = c.createGain(); og.gain.value = .12; o.connect(f); f.connect(og); og.connect(g); o.start();
      const n = this.noiseLoop(g, 900, 'bandpass', 1); const ng = c.createGain(); ng.gain.value = .25; n.fl.disconnect(); n.fl.connect(ng); ng.connect(g);
      return { gain: g, osc: o, f, nf: n.fl, nodes: [o, n.src] };
    });
  }

  updateCar(on, speed) {
    const l = this.loops.car; if (!l) return;
    const t = this.ctx.currentTime;
    l.gain.gain.setTargetAtTime(on ? .45 : 0, t, .15);
    l.osc.frequency.setTargetAtTime(55 + speed * 2.2, t, .1);
    l.f.frequency.setTargetAtTime(300 + speed * 25, t, .1);
    l.nf.frequency.setTargetAtTime(600 + speed * 40, t, .1);
  }

  // ------------------------------------------------------------- generative music
  music(kind) {
    if (!this.ready) return;
    if (this.musicKind === kind) return;
    this.musicKind = kind;
    clearTimeout(this.musicTimer);
    this.chordIx = 0;
    const tick = () => {
      const def = MUSIC[this.musicKind]; if (!def) return;
      this.playChord(def);
      this.musicTimer = setTimeout(tick, def.tempo * 1000 * (this.combat > .5 ? .5 : 1));
    };
    this.musicTimer = setTimeout(tick, 400);
  }

  playChord(def) {
    const c = this.ctx, t = c.currentTime + .05, dur = def.tempo * 1.25;
    const ch = def.chords[this.chordIx++ % def.chords.length];
    const g = c.createGain(); g.gain.value = 0; g.connect(this.mus); g.connect(this.verb);
    g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(.09, t + dur * .35); g.gain.linearRampToValueAtTime(0, t + dur);
    const f = c.createBiquadFilter(); f.type = 'lowpass'; f.frequency.value = def.bright * (1 + this.combat); f.connect(g);
    ch.forEach((n, i) => {
      for (const det of [-6, 6]) {
        const o = c.createOscillator(); o.type = i === 0 ? 'triangle' : 'sawtooth';
        o.frequency.value = mtof(def.root + 12 + n); o.detune.value = det;
        const og = c.createGain(); og.gain.value = i === 0 ? .5 : .16; o.connect(og); og.connect(f);
        o.start(t); o.stop(t + dur + .1);
      }
    });
    // sparse arpeggio sparkle
    for (let k = 0; k < 3; k++) {
      const n = ch[(Math.random() * ch.length) | 0] + 24;
      this.tone(this.verb, t + dur * (.2 + k * .22), 1.2, mtof(def.root + n), mtof(def.root + n), 'sine', .025 * this.settings.music, .02);
    }
    // combat pulse
    if (this.combat > .5) {
      const beat = 60 / 120;
      for (let b = 0; b < Math.floor(def.tempo * .5 / beat); b++) {
        this.tone(this.mus, t + b * beat, .25, mtof(def.root + ch[0] - 12) * 2, mtof(def.root + ch[0] - 12), 'sine', .35);
        this.nz(this.mus, t + b * beat + beat / 2, .06, 8000, 4000, 1, 'highpass', .06);
      }
    }
  }
}
