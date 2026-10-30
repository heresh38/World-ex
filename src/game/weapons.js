// Player weapons: hitscan with spread/falloff, bursts, pellets, rockets with splash, perks, reload, switching.
import * as THREE from 'three';
import { ARCHETYPES, RARITY, SHADERS } from './data.js';
import { weaponStats } from './state.js';

const _o = new THREE.Vector3(), _d = new THREE.Vector3(), _m = new THREE.Vector3(), _t = new THREE.Vector3();

export class Weapons {
  constructor(game) {
    this.g = game;
    this.slot = 0; this.cool = 0; this.reloading = 0; this.swap = 0; this.burstLeft = 0; this.burstCool = 0;
    this.ammo = {};       // uid -> {mag, reserve}
    this.lastFire = 9; this.rampage = 0; this.rampageT = 0;
    this.rockets = [];
  }

  equipped(i = this.slot) {
    const id = this.g.save.equipped[i];
    return this.g.save.inventory.find(w => w.uid === id) || null;
  }

  ammoOf(w) {
    if (!w) return null;
    if (!this.ammo[w.uid]) { const s = weaponStats(w); this.ammo[w.uid] = { mag: s.mag, reserve: s.reserve }; }
    return this.ammo[w.uid];
  }

  refill() {
    for (let i = 0; i < 3; i++) { const w = this.equipped(i); if (w) { const s = weaponStats(w); this.ammo[w.uid] = { mag: s.mag, reserve: s.reserve }; } }
  }

  firingRecently() { return this.lastFire < .9; }

  zoom() { const w = this.equipped(); return w ? ARCHETYPES[w.arch].zoom : 1; }

  refreshModel() {
    const p = this.g.player; if (!p || !p.avatar) return;
    if (!p.armed) { p.avatar.attachGun(null); return; }
    const w = this.equipped(); if (!w) { p.avatar.attachGun(null); return; }
    const A = ARCHETYPES[w.arch];
    p.avatar.attachGun(A.model, mesh => Weapons.styleMesh(mesh, w));
  }

  static styleMesh(mesh, w) {
    const m = mesh.material, rc = RARITY[w.rarity].color;
    if (m.name === 'gun_glow') { m.color.set(rc); m.emissive.set(rc); m.emissiveIntensity = 3.5; }
    if (m.name === 'gun_body') { const sh = SHADERS.find(s => s.id === w.shader) || SHADERS[0]; m.color.set(sh.body); }
  }

  select(i) {
    if (i === this.slot || !this.equipped(i)) return;
    this.slot = i; this.swap = .35; this.reloading = 0; this.burstLeft = 0;
    this.refreshModel(); this.g.audio.reload(1);
    this.g.hud.dirty = true;
  }

  update(dt, input) {
    const p = this.g.player;
    this.cool -= dt; this.swap -= dt; this.lastFire += dt; this.burstCool -= dt;
    if (this.rampageT > 0) { this.rampageT -= dt; if (this.rampageT <= 0) this.rampage = 0; }
    this.updateRockets(dt);
    // autoload perk: stowed weapons top up
    for (let i = 0; i < 3; i++) {
      if (i === this.slot) continue; const w = this.equipped(i);
      if (w && w.perks.includes('autoload')) { const a = this.ammoOf(w), s = weaponStats(w); if (a.mag < s.mag && a.reserve > 0) { const n = Math.min(s.mag - a.mag, a.reserve); a.mag += n; a.reserve -= n; } }
    }
    if (!p.armed || p.mode !== 'foot' || p.dead) return;
    if (input.enabled) {
      for (let i = 0; i < 3; i++) if (input.pressed('Digit' + (i + 1))) this.select(i);
      if (input.wheel) { let n = this.slot; for (let k = 0; k < 3; k++) { n = (n + (input.wheel > 0 ? 1 : 2)) % 3; if (this.equipped(n)) break; } this.select(n); }
    }
    const w = this.equipped(); if (!w) return;
    const A = ARCHETYPES[w.arch], S = weaponStats(w), a = this.ammoOf(w);
    if (this.reloading > 0) {
      this.reloading -= dt;
      const gun = p.avatar.gun; if (gun) gun.rotation.x = Math.sin(Math.min(1, 1 - this.reloading / S.reload) * Math.PI) * .9;
      if (this.reloading <= 0) {
        const n = Math.min(S.mag - a.mag, a.reserve); a.mag += n; a.reserve -= n;
        this.g.audio.reload(1); this.g.hud.dirty = true;
        if (gun) gun.rotation.x = 0;
      }
      return;
    }
    if (input.enabled && input.pressed('KeyR') && a.mag < S.mag && a.reserve > 0) { this.startReload(S); return; }
    if (this.swap > 0) return;
    // continue a pulse burst
    if (this.burstLeft > 0 && this.burstCool <= 0 && a.mag > 0) { this.fire(w, A, S, a); this.burstLeft--; this.burstCool = 60 / A.burstRpm; return; }
    const trigger = input.enabled && input.locked && (A.auto ? input.lmb : input.lmbHit);
    if (!trigger || this.cool > 0 || this.burstLeft > 0) return;
    if (a.mag <= 0) {
      if (a.reserve > 0) this.startReload(S); else if (input.lmbHit) this.g.audio.empty();
      return;
    }
    const frenzy = w.perks.includes('frenzy') && p.shield <= 0 ? 1.2 : 1;
    this.cool = 60 / (S.rpm * frenzy);
    if (A.burst) { this.fire(w, A, S, a); this.burstLeft = A.burst - 1; this.burstCool = 60 / A.burstRpm; this.cool += (A.burst - 1) * 60 / A.burstRpm; }
    else this.fire(w, A, S, a);
  }

  startReload(S) {
    this.reloading = S.reload; this.burstLeft = 0; this.g.audio.reload(0);
  }

  fire(w, A, S, a) {
    const g = this.g, p = g.player, cam = g.camera;
    a.mag--; this.lastFire = 0; g.hud.dirty = true;
    g.save.stats.shots++;
    p.recoil = Math.min(1.5, p.recoil + (A.recoil || (A.dmg > 100 ? 1 : .35)) / S.spread * .3 + .15);
    p.camPitch += (w.arch === 'sniper' || w.arch === 'handcannon' ? .012 : .0035) * (p.aiming ? .6 : 1);
    p.avatar.muzzleWorld(_m);
    p.camForward(_d);
    g.fx.muzzle(_m, _d, w.arch === 'rocket' ? 0xffa040 : 0xffc070);
    g.audio.shot(A.sound);
    if (A.projectile) { this.launchRocket(_m.clone(), this.aimPoint(), S, w); return; }
    const pellets = A.pellets || 1;
    let anyHit = false, crit = false, killed = false;
    for (let k = 0; k < pellets; k++) {
      // spread cone
      const moving = Math.hypot(p.vel.x, p.vel.z) > .5;
      const sp = THREE.MathUtils.degToRad(S.spread * (p.aiming ? .45 : 1) * (moving ? 1.35 : 1) * (p.grounded ? 1 : 1.6));
      p.camForward(_d);
      const rx = (Math.random() - .5) * 2 * sp, ry = (Math.random() - .5) * 2 * sp;
      _t.set(Math.cos(p.camYaw), 0, -Math.sin(p.camYaw));
      _d.addScaledVector(_t, rx); _d.y += ry; _d.normalize();
      _o.copy(cam.position).addScaledVector(_d, p.camCur * .9);
      const res = g.combat.trace(_o, _d, Math.max(250, S.range * 4), 'player');
      const end = res.point;
      g.fx.tracer(_m, end, RARITY[w.rarity].id === 'exotic' ? 0xffd070 : 0xffd9a0, w.arch === 'sniper' ? .03 : .015, w.arch === 'sniper' ? .2 : .06);
      if (res.target) {
        const dist = res.dist;
        const fall = dist < S.range ? 1 : Math.max(.5, 1 - (dist - S.range) / (S.range * 2));
        let dmg = S.dmg * fall * (1 + this.rampage * .15);
        if (res.crit) dmg *= S.crit;
        const out = res.target.takeDamage(dmg, res.crit, end, _d, 'player');
        anyHit = true; crit = crit || res.crit; killed = killed || out.killed;
        g.fx.impact(end, res.normal || _d.clone().negate(), res.crit ? 'crit' : 'enemy');
        g.hud.damageNumber(end, dmg, res.crit);
        if (res.crit && w.perks.includes('explosive')) { g.combat.splash(end, 2.5, dmg * .3, 'player', res.target); g.fx.emit(end, 14, 6, 0xff8a40, .3, 4, .08); }
        if (out.killed) this.onKill(w, res.crit, res.target);
      } else if (res.hit) {
        g.fx.impact(end, res.normal, res.terrain ? 'dirt' : 'metal');
      }
    }
    if (anyHit) { g.save.stats.hits++; g.hud.hitMarker(crit, killed); g.audio.hit(crit, killed); }
  }

  aimPoint() {
    const g = this.g, p = g.player;
    p.camForward(_d);
    _o.copy(g.camera.position).addScaledVector(_d, p.camCur * .9);
    return g.combat.trace(_o, _d, 300, 'player').point;
  }

  onKill(w, crit, target) {
    const g = this.g;
    if (w.perks.includes('rampage')) { this.rampage = Math.min(3, this.rampage + 1); this.rampageT = 4; }
    if (w.perks.includes('vampire')) g.player.health = Math.min(g.player.maxHealth, g.player.health + 25);
  }

  launchRocket(from, to, S, w) {
    const g = this.g;
    const dir = to.clone().sub(from).normalize();
    const m = new THREE.Mesh(new THREE.SphereGeometry(.12, 8, 6), new THREE.MeshBasicMaterial({ color: new THREE.Color(0xffa040).multiplyScalar(4), toneMapped: false }));
    m.position.copy(from); g.scene.add(m);
    this.rockets.push({ m, dir, speed: 48, life: 5, dmg: S.dmg * (1 + this.rampage * .15), w, splash: ARCHETYPES[w.arch].splash, owner: 'player' });
  }

  updateRockets(dt) {
    const g = this.g;
    for (let i = this.rockets.length - 1; i >= 0; i--) {
      const r = this.rockets[i];
      r.life -= dt;
      const step = r.speed * dt;
      const res = g.combat.trace(r.m.position, r.dir, step, r.owner);
      g.fx.emit(r.m.position, 3, 1.5, 0xff9040, .35, -1, .14, 1);
      if (res.hit || res.target || r.life <= 0) {
        const p = res.hit || res.target ? res.point : r.m.position;
        const kills = g.combat.splash(p, r.splash, r.dmg, r.owner);
        g.fx.explosion(p, r.splash); g.audio.explosion(p);
        const dd = p.distanceTo(g.player.pos); if (dd < 30) g.player.shake = Math.min(1, g.player.shake + (1 - dd / 30));
        if (kills) { g.hud.hitMarker(false, true); g.audio.hit(false, true); kills.forEach(() => this.onKill(r.w, false)); }
        r.m.removeFromParent(); r.m.geometry.dispose(); this.rockets.splice(i, 1);
        continue;
      }
      r.m.position.addScaledVector(r.dir, step);
    }
  }

  clearRockets() { this.rockets.forEach(r => r.m.removeFromParent()); this.rockets = []; }
}
