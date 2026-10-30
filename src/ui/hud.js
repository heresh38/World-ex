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
      <div class="h-cross"></div><div class="h-hit"></div>
      <div class="h-feed"></div>
      <div class="h-vitals"></div>
      <div class="h-weap"></div>
      <div class="h-car hidden"></div>
      <div class="h-banner"><small></small><b></b></div>
      <div class="h-hint"></div>
      <div class="h-nums"></div>
      <div class="h-fps hidden"></div>`;
    const q = s => this.el.querySelector(s);
    this.dmgEl = q('.h-dmg'); this.locEl = q('.h-loc'); this.objEl = q('.h-obj'); this.compEl = q('.h-compass .strip');
    this.crossEl = q('.h-cross'); this.hitEl = q('.h-hit'); this.feedEl = q('.h-feed'); this.vitEl = q('.h-vitals');
    this.weapEl = q('.h-weap'); this.carEl = q('.h-car'); this.banEl = q('.h-banner'); this.hintEl = q('.h-hint');
    this.numsEl = q('.h-nums'); this.fpsEl = q('.h-fps');
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

  crosshair(arch) {
    const st = { shotgun: 14, rocket: 10, sniper: 0, auto: 9, pulse: 7, scout: 5, handcannon: 6 }[arch] ?? 8;
    this.crossEl.innerHTML = `<i class="d"></i>` + (st ? [0, 90, 180, 270].map(a => {
      const r = a * Math.PI / 180, x = Math.cos(r) * st, y = Math.sin(r) * st, horiz = a % 180 === 0;
      return `<i style="left:${x - (horiz ? (x > 0 ? 0 : 7) : 1)}px;top:${y - (horiz ? 1 : (y > 0 ? 0 : 7))}px;width:${horiz ? 7 : 2}px;height:${horiz ? 2 : 7}px"></i>`;
    }).join('') : '');
    this.crossArch = arch;
  }

  hitMarker(crit, kill) {
    const e = this.hitEl; e.className = 'h-hit on' + (crit ? ' crit' : '') + (kill ? ' kill' : '');
    clearTimeout(this.hitTO); this.hitTO = setTimeout(() => e.className = 'h-hit', kill ? 220 : 90);
  }

  damageFlash(a) {
    this.dmgEl.style.boxShadow = `inset 0 0 ${120 + a * 120}px rgba(255,40,30,${.25 + a * .45})`;
    clearTimeout(this.dfTO); this.dfTO = setTimeout(() => this.dmgEl.style.boxShadow = 'inset 0 0 160px rgba(255,40,30,0)', 120);
  }

  damageNumber(pos, n, crit) {
    let d = this.nums.find(x => x.t <= 0);
    if (!d) { const el = document.createElement('div'); el.className = 'h-num'; this.numsEl.appendChild(el); d = { el, t: 0, p: new THREE.Vector3() }; this.nums.push(d); }
    d.p.copy(pos); d.p.x += (Math.random() - .5) * .3; d.t = .8; d.el.textContent = Math.round(n); d.el.className = 'h-num' + (crit ? ' crit' : '');
    d.el.style.display = '';
  }

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
    if (this.combatMode) this.updateCompass();
    if (!(this.dirty || this.t > .12)) return;
    this.t = 0; this.dirty = false;
    if (g.save.settings.showFps) { this.fpsEl.classList.remove('hidden'); this.fpsEl.textContent = Math.round(g.fps) + ' fps · ' + Math.round(g.renderer.scale * 100) + '%'; }
    else this.fpsEl.classList.add('hidden');
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

  updateBars() {
    const g = this.g, cam = g.camera, W = innerWidth, H = innerHeight;
    const list = g.enemies.list.filter(e => e.alive && e.hitT < 6 && e.pos.distanceTo(g.player.pos) < 70).slice(0, 6);
    while (this.bars.length < list.length) {
      const el = document.createElement('div'); el.style.cssText = 'position:absolute;width:90px;transform:translate(-50%,-100%);text-align:center;font:600 11px Rajdhani,sans-serif;letter-spacing:.14em;text-transform:uppercase;text-shadow:0 1px 2px #000';
      el.innerHTML = '<div class="n"></div><div style="height:4px;background:rgba(0,0,0,.5);margin-top:2px"><i style="display:block;height:100%;background:#ff4a3d"></i></div>';
      this.numsEl.appendChild(el); this.bars.push(el);
    }
    this.bars.forEach((el, i) => {
      const e = list[i];
      if (!e) { el.style.display = 'none'; return; }
      e.center(_v); _v.y += e.type === 'brute' ? 1.3 : e.type === 'drone' ? .9 : e.type === 'generator' ? 2 : 1.1;
      _v.project(cam);
      if (_v.z > 1) { el.style.display = 'none'; return; }
      el.style.display = ''; el.style.left = ((_v.x + 1) / 2 * W) + 'px'; el.style.top = ((1 - _v.y) / 2 * H) + 'px';
      el.querySelector('.n').textContent = e.T.name;
      el.querySelector('i').style.width = Math.max(0, e.hp / e.maxHp * 100) + '%';
    });
  }
}
