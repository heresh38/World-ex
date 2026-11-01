// In-world HUD: vitals, weapon/ammo, compass with markers, objectives, crosshair, hit markers,
// floating damage numbers, enemy health bars, pickup feed, banners and the interaction prompt.
import * as THREE from 'three';
import { ARCHETYPES, RARITY, SLOT_NAMES } from '../game/data.js';
import { weaponStats, xpForLevel } from '../game/state.js';

const _v = new THREE.Vector3();
const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

export class HUD {
  constructor(game) {
    this.g = game;
    this.el = document.getElementById('hud');
    this.promptEl = document.getElementById('prompt');
    this.el.innerHTML = `
      <div class="h-dmg"></div>
      <div class="h-loc"></div>
      <div class="h-obj"></div>
      <div class="h-compass"><div class="strip"></div></div>
      <div class="h-scope hidden"><svg viewBox="-100 -100 200 200"><circle r="99" fill="none" stroke="#000" stroke-width="2"/>
        <line x1="-99" y1="0" x2="-6" y2="0" stroke="#000" stroke-width="1.1"/><line x1="6" y1="0" x2="99" y2="0" stroke="#000" stroke-width="1.1"/>
        <line x1="0" y1="-99" x2="0" y2="-6" stroke="#000" stroke-width="1.1"/><line x1="0" y1="6" x2="0" y2="99" stroke="#000" stroke-width="1.1"/>
        <line x1="-99" y1="0" x2="-55" y2="0" stroke="#000" stroke-width="3.5"/><line x1="55" y1="0" x2="99" y2="0" stroke="#000" stroke-width="3.5"/>
        <line x1="0" y1="55" x2="0" y2="99" stroke="#000" stroke-width="3.5"/>
        ${[-40, -30, -20, -10, 10, 20, 30, 40].map(v => `<circle cx="${v}" cy="0" r=".9" fill="#000"/><circle cx="0" cy="${v}" r=".9" fill="#000"/>`).join('')}
        <circle r="1.4" fill="#ff3b2f"/></svg></div>
      <div class="h-cross"></div><div class="h-hit"></div>
      <div class="h-feed"></div>
      <div class="h-vitals"></div>
      <div class="h-weap"></div>
      <div class="h-car hidden"></div>
      <div class="h-banner"><small></small><b></b></div>
      <div class="h-hint"></div>
      <div class="h-nums"></div>
      <div class="h-fps hidden"></div>
      <div class="h-wanted"></div>
      <div class="h-boss hidden"><div class="bn"></div><div class="bb"><i></i><u></u></div><div class="bs"></div></div>
      <div class="h-radio"><b></b><span></span></div>
      <div class="h-lore"><small></small><b></b><div class="lt"></div></div>
      <canvas class="h-mini hidden" width="180" height="180"></canvas>`;
    const q = s => this.el.querySelector(s);
    this.dmgEl = q('.h-dmg'); this.locEl = q('.h-loc'); this.objEl = q('.h-obj'); this.compEl = q('.h-compass .strip');
    this.scopeEl = q('.h-scope');
    this.crossEl = q('.h-cross'); this.hitEl = q('.h-hit'); this.feedEl = q('.h-feed'); this.vitEl = q('.h-vitals');
    this.weapEl = q('.h-weap'); this.carEl = q('.h-car'); this.banEl = q('.h-banner'); this.hintEl = q('.h-hint');
    this.numsEl = q('.h-nums'); this.fpsEl = q('.h-fps');
    this.wantedEl = q('.h-wanted'); this.miniEl = q('.h-mini'); this.mini = this.miniEl.getContext('2d');
    this.bossEl = q('.h-boss'); this.radioEl = q('.h-radio'); this.loreEl = q('.h-lore');
    this.radioQ = []; this.radioCur = null; this.loreT = 0;
    this.nums = []; this.bars = [];
    this.dirty = true; this.t = 0; this.markers = [];
    this.combatMode = false;
    this.lastPrompt = '';
    this.compassBuilt = false;
    this.buildCompass();
  }

  show(on) { this.el.classList.toggle('hidden', !on); if (!on) this.prompt(null); }

  setMode(combat) {
    this.combatMode = combat;
    this.vitEl.style.display = combat ? '' : 'none';
    this.weapEl.style.display = combat ? '' : 'none';
    this.crossEl.style.display = combat ? '' : 'none';
    this.el.querySelector('.h-compass').style.display = combat ? '' : 'none';
    this.dirty = true;
  }

  setLocation(region, name) { this.locEl.innerHTML = `${esc(region)}<b>${esc(name)}</b>`; }
  setHint(t) { t = t || ''; if (t !== this.hintText) { this.hintText = t; this.hintEl.textContent = t; } }

  buildCompass() {
    const dirs = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
    let h = '';
    for (let rep = -1; rep <= 1; rep++) for (let i = 0; i < 8; i++) {
      const x = (rep * 8 + i) * 120;
      h += `<span class="${i % 2 ? '' : 'c'}" style="left:${x}px">${dirs[i]}</span>`;
      for (let k = 1; k < 3; k++) h += `<span style="left:${x + k * 40}px;opacity:.4">·</span>`;
    }
    this.compEl.innerHTML = h + '<div class="mk"></div>';
    this.mkEl = this.compEl.querySelector('.mk');
  }

  // heading: 0 = north (-Z). camYaw 0 looks toward -Z.
  updateCompass() {
    const p = this.g.player;
    const heading = ((-p.camYaw * 180 / Math.PI) % 360 + 360) % 360; // deg clockwise from north
    const px = heading / 45 * 120;
    this.compEl.style.transform = `translateX(${260 - px}px)`;
    // markers
    let h = '';
    for (const m of this.markers) {
      const dx = m.pos.x - p.pos.x, dz = m.pos.z - p.pos.z;
      const ang = ((Math.atan2(dx, -dz) * 180 / Math.PI) + 360) % 360;
      let rel = ang - heading; rel = ((rel + 540) % 360) - 180;
      if (Math.abs(rel) > 70) continue;
      const d = Math.hypot(dx, dz);
      h += `<span class="m" style="left:${px + rel / 45 * 120}px;color:${m.color || '#e3c26c'}">${m.icon || '◆'}<small style="display:block;font-size:10px;opacity:.8">${d < 1000 ? Math.round(d) + 'm' : (d / 1000).toFixed(1) + 'km'}</small></span>`;
    }
    this.mkEl.innerHTML = h;
  }

  setObjectives(list) {
    this.objEl.innerHTML = (list || []).map(o => `<div class="o">${esc(o.text)}${o.sub ? `<small>${esc(o.sub)}</small>` : ''}${o.p !== undefined ? `<div class="pb"><i style="width:${Math.min(100, o.p * 100)}%"></i></div>` : ''}</div>`).join('');
  }

  scope(on) {
    if (on === this.scopeOn) return;
    this.scopeOn = on; this.scopeEl.classList.toggle('hidden', !on); this.crossEl.style.visibility = on ? 'hidden' : '';
  }

  crosshair(arch) {
    const st = { shotgun: 14, rocket: 10, sniper: 0, auto: 9, pulse: 7, scout: 5, handcannon: 6 }[arch] ?? 8;
    this.crossEl.innerHTML = `<i class="d"></i>` + (st ? [0, 90, 180, 270].map(a => {
      const r = a * Math.PI / 180, x = Math.cos(r) * st, y = Math.sin(r) * st, horiz = a % 180 === 0;
      return `<i style="left:${x - (horiz ? (x > 0 ? 0 : 7) : 1)}px;top:${y - (horiz ? 1 : (y > 0 ? 0 : 7))}px;width:${horiz ? 7 : 2}px;height:${horiz ? 2 : 7}px"></i>`;
    }).join('') : '');
    this.crossArch = arch;
  }

  hitMarker(crit, kill, immune = false) {
    const e = this.hitEl; e.className = 'h-hit on' + (immune ? ' imm' : crit ? ' crit' : '') + (kill ? ' kill' : '');
    clearTimeout(this.hitTO); this.hitTO = setTimeout(() => e.className = 'h-hit', kill ? 220 : 90);
  }

  damageFlash(a) {
    this.dmgEl.style.boxShadow = `inset 0 0 ${120 + a * 120}px rgba(255,40,30,${.25 + a * .45})`;
    clearTimeout(this.dfTO); this.dfTO = setTimeout(() => this.dmgEl.style.boxShadow = 'inset 0 0 160px rgba(255,40,30,0)', 120);
  }

  // n: a number, or a word ('IMMUNE' when a shield takes the hit)
  damageNumber(pos, n, crit) {
    let d = this.nums.find(x => x.t <= 0);
    if (!d) { const el = document.createElement('div'); el.className = 'h-num'; this.numsEl.appendChild(el); d = { el, t: 0, p: new THREE.Vector3() }; this.nums.push(d); }
    const word = typeof n === 'string';
    d.p.copy(pos); d.p.x += (Math.random() - .5) * .3; d.t = .8; d.el.textContent = word ? n : Math.round(n); d.el.className = 'h-num' + (word ? ' imm' : crit ? ' crit' : '');
    d.el.style.display = '';
  }

  // the number for a hit result from takeDamage(): IMMUNE when blocked, otherwise what was actually dealt
  hitNumber(pos, out, dmg, crit) {
    if (out && out.immune) { if (this.immFrame !== this.frame) { this.immFrame = this.frame; this.damageNumber(pos, 'IMMUNE', false); } return; }
    this.damageNumber(pos, out && out.dealt != null ? out.dealt : dmg, crit);
  }

  // ---------------------------------------------------------------- boss health bar (name, health, shield state)
  // b = { name, hp, max, shield: bool, state: 'text', mark: fraction for a phase tick } or null to hide
  bossBar(b) {
    const el = this.bossEl;
    if (!b) { if (this.bossOn) { this.bossOn = false; el.classList.add('hidden'); } return; }
    if (!this.bossOn) { this.bossOn = true; el.classList.remove('hidden'); }
    const key = b.name + '|' + Math.round(b.hp / b.max * 400) + '|' + b.shield + '|' + b.state + '|' + b.mark;
    if (key === this.bossKey) return; this.bossKey = key;
    el.querySelector('.bn').textContent = b.name;
    el.querySelector('i').style.width = Math.max(0, b.hp / b.max * 100) + '%';
    const u = el.querySelector('u'); u.style.display = b.mark ? '' : 'none'; if (b.mark) u.style.left = b.mark * 100 + '%';
    el.classList.toggle('shield', !!b.shield); el.classList.toggle('stagger', b.state && /stagger|reel/i.test(b.state) && !b.shield);
    el.querySelector('.bs').textContent = b.state || '';
  }

  // ---------------------------------------------------------------- radio transmissions (speaker + line, queued)
  radio(who, text, o = {}) {
    const dur = o.dur || Math.max(3.2, Math.min(9, 1.6 + text.length * .055));
    this.radioQ.push({ who, text, dur, color: o.color || null, cb: o.cb || null, tag: o.tag });
    if (this.radioQ.length > 12) this.radioQ.shift();
  }
  radioBusy() { return !!this.radioCur || this.radioQ.length > 0; }
  clearRadio() { this.radioQ = []; this.radioCur = null; this.radioEl.classList.remove('on'); }
  updateRadio(dt) {
    const c = this.radioCur;
    if (c) { c.t -= dt; if (c.t <= 0) { this.radioCur = null; this.radioEl.classList.remove('on'); this.radioGap = .35; if (c.cb) c.cb(); } return; }
    if ((this.radioGap = (this.radioGap || 0) - dt) > 0 || !this.radioQ.length) return;
    const n = this.radioCur = this.radioQ.shift(); n.t = n.dur;
    const b = this.radioEl.querySelector('b'); b.textContent = n.who; b.style.color = n.color || '';
    this.radioEl.querySelector('span').textContent = n.text;
    this.radioEl.classList.add('on');
    this.g.audio.radio && this.g.audio.radio();
  }

  // ---------------------------------------------------------------- lore / summary card (terminal logs, operation results)
  lore(kicker, title, html, dur = 12) {
    const el = this.loreEl;
    el.querySelector('small').textContent = kicker; el.querySelector('b').textContent = title;
    el.querySelector('.lt').innerHTML = html;
    el.classList.add('on'); this.el.classList.add('lore-on'); this.loreT = dur;
  }
  hideLore() { this.loreT = 0; this.loreEl.classList.remove('on'); this.el.classList.remove('lore-on'); }

  feed(text, color = '#fff') {
    const d = document.createElement('div'); d.textContent = text; d.style.borderColor = color; d.style.color = color === '#ffffff' ? '' : color;
    this.feedEl.appendChild(d);
    while (this.feedEl.children.length > 5) this.feedEl.firstChild.remove();
    setTimeout(() => { d.style.transition = 'opacity .5s'; d.style.opacity = 0; setTimeout(() => d.remove(), 520); }, 4200);
  }

  toast(t) { this.feed(t, '#e3c26c'); }

  banner(title, sub = '', dur = 3.2) {
    this.banEl.querySelector('b').textContent = title; this.banEl.querySelector('small').textContent = sub;
    this.banEl.classList.add('on'); clearTimeout(this.banTO); this.banTO = setTimeout(() => this.banEl.classList.remove('on'), dur * 1000);
  }

  prompt(p) {
    const key = p ? p.key + p.label + p.verb : '';
    if (key === this.lastPrompt) return;
    this.lastPrompt = key;
    if (!p) { this.promptEl.classList.add('hidden'); return; }
    this.promptEl.innerHTML = `<kbd>${esc(p.key || 'E')}</kbd><div class="p-t"><small>${esc(p.verb)}</small><b>${esc(p.label)}</b></div>`;
    this.promptEl.classList.remove('hidden');
  }

  update(dt) {
    const g = this.g, p = g.player, cam = g.camera;
    this.t += dt;
    // projected elements every frame
    const W = innerWidth, H = innerHeight;
    for (const d of this.nums) {
      if (d.t <= 0) continue;
      d.t -= dt; d.p.y += dt * .9;
      _v.copy(d.p).project(cam);
      if (d.t <= 0 || _v.z > 1) { d.el.style.display = 'none'; continue; }
      d.el.style.left = ((_v.x + 1) / 2 * W) + 'px'; d.el.style.top = ((1 - _v.y) / 2 * H) + 'px';
      d.el.style.opacity = Math.min(1, d.t * 3);
    }
    this.updateBars();
    this.updateRadio(dt);
    if (this.loreT > 0 && (this.loreT -= dt) <= 0) this.hideLore();
    this.frame = (this.frame || 0) + 1;
    if (this.combatMode) this.updateCompass();
    this.updateMinimap();
    if (!(this.dirty || this.t > .12)) return;
    this.t = 0; this.dirty = false;
    if (g.save.settings.showFps) { this.fpsEl.classList.remove('hidden'); this.fpsEl.textContent = Math.round(g.fps) + ' fps · ' + Math.round(g.renderer.scale * 100) + '%'; }
    else this.fpsEl.classList.add('hidden');
    const wl = g.world && g.world.wanted ? g.world.wanted.level : 0;
    if (wl !== this.wl) { this.wl = wl; this.wantedEl.innerHTML = wl ? Array.from({ length: 5 }, (_, i) => `<span class="${i < wl ? 'on' : ''}">\u2605</span>`).join('') : ''; }
    if (!this.combatMode) return;
    const s = g.save;
    this.vitEl.innerHTML = `<div class="lv"><b>${g.power()}</b>POWER · LEVEL ${s.level}</div>
      <div class="bar sh"><i style="width:${p.shield / p.maxShield * 100}%"></i></div>
      <div class="bar hp ${p.health < 35 ? 'low' : ''}"><i style="width:${p.health / p.maxHealth * 100}%"></i></div>
      <div class="bar xp"><i style="width:${s.xp / xpForLevel(s.level) * 100}%"></i></div>`;
    const wpn = g.weapons;
    let h = '';
    for (let i = 2; i >= 0; i--) {
      const w = wpn.equipped(i); if (!w) continue;
      const on = i === wpn.slot, A = ARCHETYPES[w.arch], a = wpn.ammoOf(w);
      h += `<div class="slot ${on ? 'on' : ''}"><span class="nm">${esc(w.name)}</span><span class="rar" style="background:${RARITY[w.rarity].color}"></span>
        <div style="font-size:11px;letter-spacing:.24em;opacity:.7">${SLOT_NAMES[i]} · ${A.name}</div>
        ${on ? `<div class="ammo">${wpn.reloading > 0 ? '<span style="font-size:20px;letter-spacing:.3em">RELOADING</span>' : a.mag}<small>${a.reserve}</small></div>` : ''}</div>`;
      if (on && this.crossArch !== w.arch) this.crosshair(w.arch);
    }
    this.weapEl.innerHTML = h;
    const car = g.vehicles.current;
    this.carEl.classList.toggle('hidden', !car);
    if (car) this.carEl.innerHTML = `${Math.round(car.speed * 3.6)}<small>KM/H · ${car.S.name}</small><div class="bar sh" style="width:180px;margin-left:auto"><i style="width:${Math.max(0, car.hp / car.S.hp * 100)}%"></i></div>`;
    this.crossEl.style.display = this.combatMode && !car && p.armed && !p.dead ? '' : 'none';
    this.weapEl.style.display = this.combatMode && !car ? '' : 'none';
  }

  // Rotating minimap around the player, on every destination. Worlds may supply a pre-drawn map
  // ({canvas, scale, half} or {canvas, scale, ox, oz, view}); otherwise one is built from the world itself.
  updateMinimap() {
    const g = this.g, w = g.world;
    if (w && w.minimap === undefined) w.minimap = autoMinimap(w);
    const mm = w && w.minimap;
    const show = !!mm && g.state === 'play' && !g.stationId && !document.body.classList.contains('touch');
    this.miniEl.classList.toggle('hidden', !show);
    if (!show) return;
    const x = this.mini, S = 180, R = S / 2, p = g.player, c = p.mode === 'car' && g.vehicles.current ? g.vehicles.current.pos : p.pos;
    if (mm.refresh) mm.refresh(c.x, c.z);
    const ox = mm.ox != null ? mm.ox : -mm.half, oz = mm.oz != null ? mm.oz : -mm.half;
    const view = mm.view ? mm.view * (p.mode === 'car' ? 1.6 : 1) : null;
    const zoom = view ? R / (view * mm.scale) : (p.mode === 'car' ? 1.6 : 2.6);
    const ppm = zoom * mm.scale;                                   // screen pixels per metre
    x.save(); x.clearRect(0, 0, S, S);
    x.beginPath(); x.arc(R, R, R - 2, 0, Math.PI * 2); x.clip();
    x.fillStyle = mm.bg || '#1e465c'; x.fillRect(0, 0, S, S);
    x.save();
    x.translate(R, R); x.rotate(p.camYaw); x.scale(zoom, zoom);
    x.translate(-(c.x - ox) * mm.scale, -(c.z - oz) * mm.scale);
    x.drawImage(mm.canvas, 0, 0);
    x.restore();
    // blips in screen space so they can sit on the rim when out of range
    const cs = Math.cos(p.camYaw), sn = Math.sin(p.camYaw);
    const toScr = (wx, wz) => { const dx = (wx - c.x) * ppm, dz = (wz - c.z) * ppm; return [R + dx * cs - dz * sn, R + dx * sn + dz * cs]; };
    const blip = (wx, wz, col, r, icon = null, clamp = false) => {
      let [sx, sy] = toScr(wx, wz); const dx = sx - R, dy = sy - R, d = Math.hypot(dx, dy), lim = R - 9;
      if (d > lim) { if (!clamp) return; sx = R + dx / d * lim; sy = R + dy / d * lim; }
      x.fillStyle = col;
      if (icon) { x.font = '700 13px Rajdhani, sans-serif'; x.textAlign = 'center'; x.textBaseline = 'middle'; x.shadowColor = '#000'; x.shadowBlur = 3; x.fillText(icon, sx, sy); x.shadowBlur = 0; }
      else { x.beginPath(); x.arc(sx, sy, r, 0, 7); x.fill(); }
    };
    // interaction points (stations, caches, lifts, doors): small pale dots
    for (const it of w.interactables) { if (it.enabled && !it.enabled()) continue; const q = typeof it.pos === 'function' ? it.pos() : it.pos; if (q) blip(q.x, q.z, 'rgba(236,230,216,.75)', 2.2); }
    // hostiles in range
    if (w.combat) for (const e of g.enemies.list) if (e.alive && e.state !== 'idle') blip(e.pos.x, e.pos.z, '#ff4a3d', 2.4);
    // world markers (objectives, landing zone, loot): icons, pinned to the rim when far away
    for (const m of this.markers) blip(m.pos.x, m.pos.z, m.color, 3, m.icon || null, true);
    x.restore();
    // player arrow (camera-up)
    x.fillStyle = '#e3c26c'; x.beginPath(); x.moveTo(R, R - 8); x.lineTo(R + 5, R + 6); x.lineTo(R, R + 3); x.lineTo(R - 5, R + 6); x.closePath(); x.fill();
    x.strokeStyle = 'rgba(236,230,216,.5)'; x.lineWidth = 2; x.beginPath(); x.arc(R, R, R - 2, 0, Math.PI * 2); x.stroke();
  }

  updateBars() {
    const g = this.g, cam = g.camera, W = innerWidth, H = innerHeight;
    // bosses have the big bar; worlds may add their own targets (shield conduits) through barTargets()
    const extra = g.world && g.world.barTargets ? g.world.barTargets() : [];
    const list = [...extra, ...g.enemies.list.filter(e => e.alive && !e.boss && e.hitT < 6 && e.pos.distanceTo(g.player.pos) < 70)].slice(0, 7);
    while (this.bars.length < list.length) {
      const el = document.createElement('div'); el.style.cssText = 'position:absolute;width:90px;transform:translate(-50%,-100%);text-align:center;font:600 11px Rajdhani,sans-serif;letter-spacing:.14em;text-transform:uppercase;text-shadow:0 1px 2px #000';
      el.innerHTML = '<div class="n"></div><div style="height:4px;background:rgba(0,0,0,.5);margin-top:2px"><i style="display:block;height:100%;background:#ff4a3d"></i></div>';
      this.numsEl.appendChild(el); this.bars.push(el);
    }
    this.bars.forEach((el, i) => {
      const e = list[i];
      if (!e) { el.style.display = 'none'; return; }
      e.center(_v); _v.y += e.barY != null ? e.barY : e.type === 'brute' ? 1.3 : e.type === 'drone' ? .9 : e.type === 'generator' ? 2 : 1.1;
      _v.project(cam);
      if (_v.z > 1) { el.style.display = 'none'; return; }
      el.style.display = ''; el.style.left = ((_v.x + 1) / 2 * W) + 'px'; el.style.top = ((1 - _v.y) / 2 * H) + 'px';
      el.querySelector('.n').textContent = e.T.name;
      const bi = el.querySelector('i'); bi.style.width = Math.max(0, e.hp / e.maxHp * 100) + '%'; bi.style.background = e.barColor || '#ff4a3d';
    });
  }
}

// Minimap for worlds without a hand-drawn one.
// Endless terrain (frontier planets): a hill-shaded patch re-rendered around the player as they travel.
// Interiors (ship, metro): walls drawn from the collision boxes.
function autoMinimap(w) {
  if (w.height) {
    const N = 160, span = 700, c = document.createElement('canvas'); c.width = c.height = N;
    const x = c.getContext('2d'), mm = { canvas: c, scale: N / span, ox: 0, oz: 0, view: 140, bg: '#28302a', cx: 1e9, cz: 1e9 };
    const tint = (w.dest && w.dest.orb && /#([0-9a-f]{6})/i.exec(w.dest.orb)) ? parseInt(/#([0-9a-f]{6})/i.exec(w.dest.orb)[1], 16) : 0x6a7a5a;
    const tr = (tint >> 16) & 255, tg = (tint >> 8) & 255, tb = tint & 255;
    mm.refresh = (px, pz) => {
      if (Math.hypot(px - mm.cx, pz - mm.cz) < span * .22) return;
      mm.cx = px; mm.cz = pz; mm.ox = px - span / 2; mm.oz = pz - span / 2;
      const img = x.createImageData(N, N), st = span / N, H = new Float32Array((N + 1) * (N + 1));
      for (let j = 0; j <= N; j++) for (let i = 0; i <= N; i++) H[j * (N + 1) + i] = w.height(mm.ox + i * st, mm.oz + j * st);
      const h0 = w.height(px, pz);
      for (let j = 0; j < N; j++) for (let i = 0; i < N; i++) {
        const h = H[j * (N + 1) + i], hx = H[j * (N + 1) + i + 1] - h, hz = H[(j + 1) * (N + 1) + i] - h;
        const shade = Math.max(.35, Math.min(1.4, 1 + (-hx - hz) * .9 / st)), lift = Math.max(-.25, Math.min(.35, (h - h0) / 120));
        const k = (j * N + i) * 4, f = shade * (.55 + lift);
        img.data[k] = Math.min(255, tr * f + 18); img.data[k + 1] = Math.min(255, tg * f + 22); img.data[k + 2] = Math.min(255, tb * f + 18); img.data[k + 3] = 255;
      }
      x.putImageData(img, 0, 0);
    };
    return mm;
  }
  const boxes = w.collision.boxes.filter(b => b.max.y - b.min.y > .8 && b.min.y < 1.6 && b.max.y > .4).map(b => [b.min.x, b.min.y, b.min.z, b.max.x, b.max.y, b.max.z]);
  if (!boxes.length) return null;
  let x0 = 1e9, z0 = 1e9, x1 = -1e9, z1 = -1e9;
  for (const b of boxes) { x0 = Math.min(x0, b[0]); z0 = Math.min(z0, b[2]); x1 = Math.max(x1, b[3]); z1 = Math.max(z1, b[5]); }
  x0 = Math.max(x0, -800) - 10; z0 = Math.max(z0, -800) - 10; x1 = Math.min(x1, 800) + 10; z1 = Math.min(z1, 800) + 10;
  const sc = Math.min(6, 1024 / Math.max(x1 - x0, z1 - z0));
  const c = document.createElement('canvas'); c.width = Math.ceil((x1 - x0) * sc); c.height = Math.ceil((z1 - z0) * sc);
  const x = c.getContext('2d');
  // floor: everything inside the walls' footprint reads as deck
  x.fillStyle = '#1b2a33'; x.fillRect(0, 0, c.width, c.height);
  x.fillStyle = '#9fb4c2';
  for (const b of boxes) x.fillRect((b[0] - x0) * sc, (b[2] - z0) * sc, Math.max(1, (b[3] - b[0]) * sc), Math.max(1, (b[5] - b[2]) * sc));
  return { canvas: c, scale: sc, ox: x0, oz: z0, view: w.kind === 'ship' ? 26 : 48, bg: '#0d1418' };
}
