// Enemies: troopers, brutes (humanoid, skinned), drones, turrets and outpost generators.
import * as THREE from 'three';
import { Avatar } from './avatar.js';
import { raySphere, rayCyl } from './combat.js';

const _v = new THREE.Vector3(), _d = new THREE.Vector3(), _h = new THREE.Vector3(), _a = new THREE.Vector3();

const TYPES = {
  trooper: { model: 'enemy_trooper', gun: 'gun_pulse', hp: 110, speed: 3.4, range: 32, dmg: 6, burst: 3, gap: [1.2, 2.2], xp: 40, scale: 1, name: 'Raider Trooper', loot: .14 },
  brute: { model: 'enemy_brute', gun: 'gun_shotgun', hp: 420, speed: 2.8, range: 15, dmg: 5, pellets: 5, burst: 1, gap: [1.6, 2.4], xp: 120, scale: 1.22, name: 'Raider Brute', loot: .45 },
  drone: { hp: 70, speed: 7, range: 30, dmg: 5, burst: 2, gap: [1.0, 1.8], xp: 35, name: 'Seeker Drone', loot: .15 },
  turret: { hp: 260, range: 40, dmg: 6, burst: 4, gap: [1.4, 2.0], xp: 60, name: 'Sentry Turret', loot: .3 },
  generator: { hp: 900, xp: 200, name: 'Raider Generator', loot: 1 },
};

export class Enemy {
  constructor(game, type, pos, level, opts = {}) {
    this.g = game; this.type = type; this.T = TYPES[type]; this.level = level;
    this.side = 'enemy'; this.alive = true; this.pos = pos.clone(); this.home = pos.clone();
    this.vel = new THREE.Vector3(); this.yaw = Math.random() * 6.28;
    this.maxHp = this.hp = Math.round(this.T.hp * (1 + level * .12));
    this.dmgMul = 1 + level * .08;
    this.state = 'idle'; this.alertT = 0; this.fireT = 1 + Math.random() * 2; this.burstLeft = 0; this.burstT = 0;
    this.thinkT = Math.random() * .4; this.seen = false; this.strafe = Math.random() < .5 ? 1 : -1; this.strafeT = 0;
    this.deadT = 0; this.hitT = 9; this.onDeath = opts.onDeath || null; this.group = opts.group || null;
    this.radius = type === 'brute' ? .7 : type === 'generator' ? 1.3 : type === 'turret' ? .9 : .5;
    if (this.T.model) {
      this.av = new Avatar(game.assets, this.T.model);
      this.av.attachGun(this.T.gun, m => { if (m.material.name === 'gun_glow') { m.material.color.set('#ff3326'); m.material.emissive.set('#ff3326'); } if (m.material.name === 'gun_body') m.material.color.set('#2c2f36'); });
      this.av.play('Idle', 0);
      this.obj = this.av.root;
    } else {
      const sub = { drone: 'PR_drone', turret: 'PR_turret', generator: 'PR_generator' }[type];
      this.obj = game.assets.clone('props_world', sub);
      this.head = this.obj.getObjectByName('turret_head');
      if (opts.police) {
        // city security drone: same airframe, white and blue livery, no loot
        this.police = true; this.T = { ...this.T, name: 'Security Drone', loot: 0 };
        this.obj.traverse(o => { if (o.isMesh) { o.material = o.material.clone(); const m = o.material;
          if (m.emissive && m.emissive.r > .5 && m.emissive.b < .5) { m.color.set('#3aa0ff'); m.emissive.set('#3aa0ff'); }
          else if (m.name === 'enemy_plate') m.color.set('#d9dde2'); } });
      }
      this.muzzle = this.obj.getObjectByName('turret_muzzle');
      if (type === 'drone') { this.pos.y += 6 + Math.random() * 3; this.hover = this.pos.y - game.world.collision.ground(pos.x, pos.z); }
    }
    this.obj.position.copy(this.pos); this.obj.rotation.y = this.yaw;
    game.scene.add(this.obj);
    game.combat.targets.add(this);
    if (type === 'turret' || type === 'generator') {
      this.box = game.world.collision.add(new THREE.Box3().setFromCenterAndSize(
        _v.set(pos.x, pos.y + (type === 'generator' ? 1.4 : 1), pos.z), _d.set(type === 'generator' ? 2.2 : 1.6, type === 'generator' ? 2.8 : 2, type === 'generator' ? 2.2 : 1.6)), 'enemy');
    }
  }

  center(out) {
    out.copy(this.pos);
    if (this.type === 'drone') return out;
    out.y += this.type === 'generator' ? 1.4 : this.type === 'turret' ? 1.2 : (this.type === 'brute' ? 1.2 : 1.0);
    return out;
  }

  hitTest(o, d, max) {
    let best = -1, crit = false;
    if (this.av) {
      const s = this.T.scale;
      if (this.av.head) {
        this.av.head.getWorldPosition(_h); _h.y += .1 * s;
        const t = raySphere(o, d, _h, .17 * s);
        if (t >= 0 && t < max) { best = t; crit = true; }
      }
      const t2 = rayCyl(o, d, this.pos.x, this.pos.z, this.pos.y, this.pos.y + 1.52 * s, .32 * s);
      if (t2 >= 0 && t2 < max && (best < 0 || t2 < best - .05)) { best = t2; crit = false; }
    } else if (this.type === 'drone') {
      const t = raySphere(o, d, this.pos, .75); if (t >= 0 && t < max) best = t;
      // the red eye is a weak point
      _h.set(Math.sin(this.yaw) * .5, 0, Math.cos(this.yaw) * .5).add(this.pos);
      const te = raySphere(o, d, _h, .22); if (te >= 0 && te < max && (best < 0 || te <= best + .1)) { best = te; crit = true; }
    } else if (this.type === 'turret') {
      const t = rayCyl(o, d, this.pos.x, this.pos.z, this.pos.y, this.pos.y + 1.9, .75); if (t >= 0 && t < max) best = t;
    } else {
      const t = rayCyl(o, d, this.pos.x, this.pos.z, this.pos.y, this.pos.y + 2.8, 1.1); if (t >= 0 && t < max) best = t;
      _h.set(this.pos.x, this.pos.y + 1.4, this.pos.z);
      const tc = raySphere(o, d, _h, .62); if (tc >= 0 && tc < max && tc <= best + .05) { best = tc; crit = true; }
    }
    return best >= 0 ? { dist: best, crit } : null;
  }

  takeDamage(dmg, crit, point, dir, side) {
    if (!this.alive) return { killed: false };
    this.hp -= dmg; this.hitT = 0;
    if (this.state === 'idle') this.alert();
    if (this.hp <= 0) { this.die(crit); return { killed: true }; }
    return { killed: false };
  }

  alert() {
    if (this.state !== 'idle') return;
    this.state = 'combat'; this.g.audio.alert(this.pos);
    this.g.music && (this.g.audio.combat = 1);
    // wake the squad
    if (this.group) for (const e of this.group) if (e !== this && e.alive && e.state === 'idle') { e.state = 'combat'; }
  }

  die(crit) {
    this.alive = false; this.state = 'dead'; this.deadT = 0;
    const g = this.g;
    g.combat.targets.delete(this);
    if (this.box) { g.world.collision.remove(this.box); this.box = null; }
    if (this.av) this.av.play('Death', .1);
    if (this.type === 'drone' || this.type === 'turret' || this.type === 'generator') {
      const p = this.center(_v).clone();
      g.fx.explosion(p, this.type === 'generator' ? 8 : 3); g.audio.explosion(p);
      if (this.type === 'generator') g.combat.splash(p, 7, 60, 'world');
    }
    g.onEnemyKilled(this, crit);
    if (this.police && g.world.wanted) g.world.wanted.onPoliceKilled();
    g.combat.drop(this.center(_v).clone(), this.type, this.level, this.T.loot);
    this.onDeath && this.onDeath(this);
  }

  canSee(target) {
    _a.copy(this.pos); _a.y += this.type === 'drone' ? 0 : 1.5;
    _h.copy(target); _h.y += 1.4;
    return this.g.world.collision.lineOfSight(_a, _h);
  }

  shoot(p) {
    const T = this.T;
    let from;
    if (this.av) from = this.av.muzzleWorld(_a).clone();
    else if (this.muzzle) from = this.muzzle.getWorldPosition(_a).clone();
    else from = this.pos.clone();
    const aim = _h.copy(p.pos); aim.y += 1.1;
    // lead slightly and add inaccuracy (better when the player is still)
    aim.addScaledVector(p.vel, .25);
    const dist = from.distanceTo(aim);
    const err = (p.aiming ? .9 : 1.25) * (.6 + dist * .03) * (Math.hypot(p.vel.x, p.vel.z) > 4 ? 1.6 : 1);
    const n = T.pellets || 1;
    for (let k = 0; k < n; k++) {
      _d.copy(aim).add(_v.set((Math.random() - .5) * err, (Math.random() - .5) * err * .6, (Math.random() - .5) * err)).sub(from).normalize();
      this.g.combat.bolt(from, _d, this.type === 'brute' ? 34 : 40, T.dmg * this.dmgMul * this.g.dmgScale(), this.type === 'brute' ? 0xff7a1a : 0xff3326);
    }
    this.g.audio.shot('bolt', from, true);
    this.g.fx.flash(from, 0xff4020, 15, .05, 6);
  }

  update(dt) {
    const g = this.g, p = g.player;
    if (!this.alive) {
      this.deadT += dt;
      if (this.av) this.av.update(dt);
      else if (this.type === 'drone') { this.pos.y -= dt * 9; this.obj.rotation.z += dt * 4; this.obj.position.copy(this.pos); if (this.pos.y < g.world.collision.ground(this.pos.x, this.pos.z)) this.obj.visible = false; }
      else this.obj.visible = this.deadT < .2 ? true : false;
      return this.deadT < 4;
    }
    this.hitT += dt;
    const dx = p.pos.x - this.pos.x, dz = p.pos.z - this.pos.z, dist = Math.hypot(dx, dz);
    this.thinkT -= dt;
    if (this.thinkT <= 0) {
      this.thinkT = .35 + Math.random() * .2;
      const range = (this.T.range || 0) + 14;
      this.seen = !p.dead && dist < range && this.type !== 'generator' && this.canSee(p.pos);
      if (this.seen && this.state === 'idle') this.alert();
      if (this.state === 'combat' && dist > 90) this.state = 'idle';
    }
    const facePlayer = () => { const t = Math.atan2(dx, dz); let d = t - this.yaw; d = Math.atan2(Math.sin(d), Math.cos(d)); this.yaw += d * Math.min(1, dt * 8); };
    if (this.type === 'generator') { this.obj.rotation.y += dt * .3; return true; }
    if (this.type === 'turret') {
      if (this.state === 'combat') { facePlayer(); if (this.head) this.head.rotation.y = this.yaw - this.obj.rotation.y; }
      this.fireLogic(dt, p, dist);
      return true;
    }
    if (this.type === 'drone') {
      const gy = g.world.collision.ground(this.pos.x, this.pos.z);
      let tx = 0, tz = 0;
      if (this.state === 'combat') {
        // orbit the player at ~14m
        const ang = Math.atan2(-dx, -dz) + this.strafe * dt * .6;
        const want = 14;
        tx = (p.pos.x + Math.sin(ang) * want - this.pos.x); tz = (p.pos.z + Math.cos(ang) * want - this.pos.z);
        facePlayer();
      } else { tx = this.home.x + Math.sin(g.time * .3 + this.home.z) * 8 - this.pos.x; tz = this.home.z + Math.cos(g.time * .3 + this.home.x) * 8 - this.pos.z; this.yaw += dt * .5; }
      const l = Math.hypot(tx, tz) || 1, sp = Math.min(this.T.speed, l);
      this.vel.x += (tx / l * sp - this.vel.x) * dt * 2; this.vel.z += (tz / l * sp - this.vel.z) * dt * 2;
      this.pos.x += this.vel.x * dt; this.pos.z += this.vel.z * dt;
      const ty = Math.max(gy + 5, (p.pos.y + 6)) + Math.sin(g.time * 2 + this.home.x) * .6;
      this.pos.y += (ty - this.pos.y) * dt * 1.5;
      this.obj.position.copy(this.pos); this.obj.rotation.set(this.vel.z * .03, this.yaw, -this.vel.x * .03);
      this.fireLogic(dt, p, dist);
      return true;
    }
    // humanoids
    const T = this.T; let mx = 0, mz = 0, speed = T.speed, run = false;
    if (this.state === 'combat') {
      facePlayer();
      const fx = dx / (dist || 1), fz = dz / (dist || 1);
      const charge = this.type === 'brute' && this.hp < this.maxHp * .5;
      const pref = this.type === 'brute' ? (charge ? 1.5 : 7) : 16;
      this.strafeT -= dt; if (this.strafeT <= 0) { this.strafeT = 1.5 + Math.random() * 2; this.strafe = -this.strafe; }
      if (dist > pref + 4 || !this.seen) { mx = fx; mz = fz; run = dist > pref + 12 || charge; }
      else if (dist < pref - 4) { mx = -fx * .7; mz = -fz * .7; }
      mx += -fz * this.strafe * .6; mz += fx * this.strafe * .6;
      if (charge) { speed = 7.5; run = true; if (dist < 2.2) { this.meleeT = (this.meleeT || 0) - dt; if (this.meleeT <= 0) { this.meleeT = 1.2; p.damage(38 * this.dmgMul * g.dmgScale(), this.pos); g.fx.emit(_v.copy(p.pos).setY(p.pos.y + 1.2), 12, 5, 0xff7a1a, .3, 5); } } }
      else if (run) speed = T.speed * 1.8;
      if (this.seen) this.fireLogic(dt, p, dist);
    } else {
      // idle wander near home
      this.wanderT = (this.wanderT || 0) - dt;
      if (this.wanderT <= 0) { this.wanderT = 3 + Math.random() * 4; this.wx = this.home.x + (Math.random() - .5) * 10; this.wz = this.home.z + (Math.random() - .5) * 10; }
      const wx = this.wx - this.pos.x, wz = this.wz - this.pos.z, wl = Math.hypot(wx, wz);
      if (wl > 1) { mx = wx / wl * .5; mz = wz / wl * .5; const t = Math.atan2(wx, wz); let d = t - this.yaw; d = Math.atan2(Math.sin(d), Math.cos(d)); this.yaw += d * Math.min(1, dt * 4); }
    }
    const ml = Math.hypot(mx, mz); if (ml > 1) { mx /= ml; mz /= ml; }
    this.vel.x += (mx * speed - this.vel.x) * Math.min(1, dt * 8); this.vel.z += (mz * speed - this.vel.z) * Math.min(1, dt * 8);
    this.vel.y -= 18 * dt;
    g.world.collision.moveCapsule(this.pos, this.vel, .4 * (T.scale || 1), 1.8 * (T.scale || 1), dt);
    this.obj.position.copy(this.pos); this.obj.rotation.y = this.yaw;
    const hs = Math.hypot(this.vel.x, this.vel.z);
    if (hs > 4.5) this.av.play('Run', .2, hs / 7); else if (hs > .4) this.av.play('Walk', .2, Math.max(.6, hs / 3.4)); else this.av.play('Idle', .25);
    this.av.aimPitch = this.state === 'combat' ? Math.atan2(p.pos.y - this.pos.y, Math.max(1, dist)) * .8 : 0;
    // only animate skinned meshes that are near enough to matter
    this.av.update(dist < 120 ? dt : 0);
    return true;
  }

  fireLogic(dt, p, dist) {
    if (!this.seen || p.dead || dist > (this.T.range || 30) + 6) return;
    this.fireT -= dt;
    if (this.burstLeft > 0) {
      this.burstT -= dt;
      if (this.burstT <= 0) { this.shoot(p); this.burstLeft--; this.burstT = .14; }
    } else if (this.fireT <= 0) {
      this.burstLeft = this.T.burst; this.burstT = 0;
      this.fireT = this.T.gap[0] + Math.random() * (this.T.gap[1] - this.T.gap[0]);
    }
  }

  dispose() {
    this.g.combat.targets.delete(this);
    if (this.box) this.g.world.collision.remove(this.box);
    this.obj.removeFromParent();
  }
}

export class EnemyManager {
  constructor(game) { this.g = game; this.list = []; }
  spawn(type, pos, level, opts) { const e = new Enemy(this.g, type, pos, level, opts); this.list.push(e); return e; }
  update(dt) {
    let combat = 0;
    for (let i = this.list.length - 1; i >= 0; i--) {
      const e = this.list[i];
      if (!e.update(dt)) { e.dispose(); this.list.splice(i, 1); continue; }
      if (e.alive && e.state === 'combat') combat++;
    }
    this.combatCount = combat;
  }
  clear() { this.list.forEach(e => e.dispose()); this.list = []; }
  removeWhere(fn) { for (let i = this.list.length - 1; i >= 0; i--) if (fn(this.list[i])) { this.list[i].dispose(); this.list.splice(i, 1); } }
}
