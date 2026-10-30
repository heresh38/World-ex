// Pedestrians: a pooled crowd that lives around the player on sidewalks, village lanes and farm yards.
// They stroll, panic and flee from gunfire and crashes, can be shot or run over, and stay down when they die.
import * as THREE from 'three';
import { Avatar } from '../../game/avatar.js';
import { raySphere, rayCyl } from '../../game/combat.js';

const SKIN = ['#f4d6c6', '#e8bfa5', '#d4a184', '#b9805f', '#8f5b3f', '#6b4130', '#4a2d22'];
const HAIR = ['#1a1310', '#2b1d14', '#4a3020', '#7a5432', '#b88b4e', '#d8c08a', '#8a8a8a', '#5a1f17'];
const SHIRT = ['#e8e6e2', '#2a2d33', '#7a1f2a', '#1f4a7a', '#2f6a4a', '#c9a24a', '#6a4a8a', '#d86a3a', '#9aa0a8', '#4a3a2a', '#e0b0c0', '#3a6a8a'];
const PANTS = ['#2a3a5a', '#1f2228', '#4a4030', '#6a6a70', '#2f3a2a', '#8a7a60', '#ffffff'];
const SHOES = ['#1c1c1c', '#5a3a26', '#e6e6e6', '#3a3a3a', '#8a5a3a'];
const pick = (a, r) => a[Math.floor(r() * a.length)];
const _v = new THREE.Vector3(), _h = new THREE.Vector3();

class Ped {
  constructor(game, av, sex) {
    this.g = game; this.av = av; this.sex = sex; this.side = 'civilian'; this.alive = false; this.active = false;
    this.pos = new THREE.Vector3(); this.yaw = 0; this.radius = .5;
    this.T = { name: 'Civilian' };
    av.root.visible = false;
  }

  dress(r) {
    const av = this.av;
    av.setLook(pick(av.outfits, r), pick(av.hairStyles, r));
    const tint = (prefix, hex) => av.allMats.forEach(m => { if (m.name.startsWith(prefix)) { m.color.copy(m.userData.base).multiply(new THREE.Color(hex)); } });
    const skin = pick(SKIN, r);
    tint('skin', skin); tint('hair', pick(HAIR, r)); tint('shirt', pick(SHIRT, r)); tint('pants', pick(PANTS, r)); tint('shoes', pick(SHOES, r));
    av.root.scale.setScalar(.94 + r() * .12);
  }

  center(out) { return out.copy(this.pos).setY(this.pos.y + 1.0); }

  hitTest(o, d, max) {
    if (!this.av.head) return null;
    this.av.head.getWorldPosition(_h); _h.y += .08;
    const th = raySphere(o, d, _h, .14);
    let best = th >= 0 && th < max ? th : -1, crit = best >= 0;
    const tb = rayCyl(o, d, this.pos.x, this.pos.z, this.pos.y, this.pos.y + 1.5, .28);
    if (tb >= 0 && tb < max && (best < 0 || tb < best - .05)) { best = tb; crit = false; }
    return best >= 0 ? { dist: best, crit } : null;
  }

  takeDamage(dmg, crit, point, dir, side) {
    if (!this.alive) return { killed: false };
    this.hp -= dmg; this.hitT = 0;
    this.g.world.population.alarm(this.pos, 30, point);
    if (this.hp <= 0) { this.die(side === 'player'); return { killed: true }; }
    this.flee(point || this.g.player.pos);
    return { killed: false };
  }

  die(byPlayer) {
    this.alive = false; this.state = 'dead'; this.deadT = 0;
    this.g.combat.targets.delete(this);
    this.av.play('Death', .08);
    this.g.save.stats.civilians = (this.g.save.stats.civilians || 0) + 1;
    if (byPlayer) this.g.world.wanted.crime(1, this.pos);
    if (Math.random() < .35) this.g.gain('credits', 5 + Math.floor(Math.random() * 25), true);
    this.g.audio.hurt();
  }

  flee(from) {
    if (!this.alive) return;
    this.state = 'flee'; this.fleeT = 7 + Math.random() * 5;
    this.fleeDir = new THREE.Vector3().subVectors(this.pos, from).setY(0);
    if (this.fleeDir.lengthSq() < .01) this.fleeDir.set(Math.random() - .5, 0, Math.random() - .5);
    this.fleeDir.normalize();
  }
}

export class Population {
  constructor(game, map, paths) {
    this.g = game; this.map = map; this.paths = paths;
    this.peds = [];
    const POOL = 34;
    for (let i = 0; i < POOL; i++) {
      const sex = i % 2 ? 'male' : 'female';
      const av = new Avatar(game.assets, sex === 'male' ? 'civ_male' : 'civ_female');
      game.world.scene.add(av.root);
      this.peds.push(new Ped(game, av, sex));
    }
    this.spawnT = 0; this.rnd = Math.random;
  }

  // paths: [{pts:[Vector3...], closed:true, density}]
  pointOn(path, s, out) {
    const pts = path.pts, n = pts.length;
    s = ((s % path.total) + path.total) % path.total;
    let acc = 0;
    for (let i = 0; i < n; i++) {
      const a = pts[i], b = pts[(i + 1) % n], L = a.distanceTo(b);
      if (acc + L >= s) { const t = (s - acc) / L; out.lerpVectors(a, b, t); return Math.atan2(b.x - a.x, b.z - a.z); }
      acc += L;
    }
    out.copy(pts[0]); return 0;
  }

  spawnAround(p) {
    const ped = this.peds.find(q => !q.active);
    if (!ped) return;
    // choose a path with a point 30..110 m from the player
    for (let tries = 0; tries < 12; tries++) {
      const path = this.paths[Math.floor(Math.random() * this.paths.length)];
      const s = Math.random() * path.total;
      this.pointOn(path, s, _v);
      const d = _v.distanceTo(p);
      if (d < 30 || d > 115) continue;
      ped.path = path; ped.s = s; ped.dir = Math.random() < .5 ? 1 : -1;
      ped.speed = 1.15 + Math.random() * .5;
      ped.active = true; ped.alive = true; ped.state = 'walk'; ped.hp = 55; ped.deadT = 0; ped.hitT = 9; ped.idleT = 4 + Math.random() * 10;
      ped.dress(Math.random);
      ped.av.root.visible = true; ped.av.mixer.stopAllAction(); ped.av.current = null; ped.av.play('WalkRelaxed', 0);
      ped.pos.copy(_v); ped.pos.y = this.map.height(_v.x, _v.z);
      this.g.combat.targets.add(ped);
      return;
    }
  }

  release(ped) {
    ped.active = false; ped.alive = false; ped.av.root.visible = false;
    this.g.combat.targets.delete(ped);
  }

  alarm(pos, radius, from = null) {
    for (const q of this.peds) if (q.active && q.alive && q.pos.distanceTo(pos) < radius) q.flee(from || pos);
  }

  get activeCount() { return this.peds.filter(q => q.active).length; }

  update(dt) {
    const g = this.g, p = g.player.mode === 'car' && g.vehicles.current ? g.vehicles.current.pos : g.player.pos;
    // density: busy downtown, quiet countryside
    const dist = this.map.district(p.x, p.z);
    const target = dist === 'Downtown' ? 30 : dist === 'New Meridian' ? 24 : ['Harrow', 'Millbrook', 'Eastwell'].includes(dist) ? 16 : 6;
    this.spawnT -= dt;
    if (this.spawnT <= 0) { this.spawnT = .25; const n = this.activeCount; for (let k = 0; k < Math.min(3, target - n); k++) this.spawnAround(p); }
    const car = g.vehicles.current;
    for (const q of this.peds) {
      if (!q.active) continue;
      const d = q.pos.distanceTo(p);
      if (d > 140 || (!q.alive && q.deadT > 20)) { this.release(q); continue; }
      const av = q.av;
      if (!q.alive) { q.deadT += dt; av.update(d < 60 ? dt : 0); continue; }
      q.hitT += dt;
      // run over by the player's car
      if (car && car.speed > 6 && q.pos.distanceTo(car.pos) < 2.2) {
        g.fx.impact(_v.copy(q.pos).setY(q.pos.y + 1), new THREE.Vector3(0, 1, 0), 'enemy');
        q.die(true); this.alarm(q.pos, 35, car.pos); continue;
      }
      let speed = q.speed, anim = 'WalkRelaxed', animSpeed = 1;
      if (q.state === 'flee') {
        q.fleeT -= dt;
        speed = 4.6; anim = 'RunRelaxed'; animSpeed = .95;
        _v.copy(q.fleeDir).multiplyScalar(speed * dt);
        q.pos.add(_v);
        q.yaw = Math.atan2(q.fleeDir.x, q.fleeDir.z);
        if (q.fleeT <= 0) {
          // calm down: rejoin the nearest point of the path
          q.state = 'walk';
          let best = 0, bd = 1e9;
          for (let s = 0; s < q.path.total; s += 4) { this.pointOn(q.path, s, _h); const dd = _h.distanceTo(q.pos); if (dd < bd) { bd = dd; best = s; } }
          q.s = best;
        }
      } else if (q.state === 'idle') {
        q.idleT -= dt; anim = 'IdleRelaxed';
        if (q.idleT <= 0) { q.state = 'walk'; q.idleT = 6 + Math.random() * 14; }
      } else {
        q.s += q.dir * speed * dt;
        const yaw = this.pointOn(q.path, q.s, _h);
        // ease toward the path (after fleeing they walk back to it)
        q.pos.x += (_h.x - q.pos.x) * Math.min(1, dt * 3); q.pos.z += (_h.z - q.pos.z) * Math.min(1, dt * 3);
        q.yaw = yaw + (q.dir < 0 ? Math.PI : 0);
        q.idleT -= dt;
        if (q.idleT <= 0) { q.state = 'idle'; q.idleT = 2 + Math.random() * 4; }
        // step aside for the player
        const pd = Math.hypot(q.pos.x - g.player.pos.x, q.pos.z - g.player.pos.z);
        if (pd < .9 && g.player.mode === 'foot') { q.pos.x += (q.pos.x - g.player.pos.x) / pd * .05; q.pos.z += (q.pos.z - g.player.pos.z) / pd * .05; }
        // a gun pointed at you is scary
        if (g.player.aiming && pd < 14) q.flee(g.player.pos);
      }
      q.pos.y = this.map.height(q.pos.x, q.pos.z);
      av.root.position.copy(q.pos); av.root.rotation.y = q.yaw;
      av.play(anim, .25, animSpeed);
      av.update(d < 70 ? dt : (Math.random() < .3 ? dt * 3 : 0));
    }
  }

  clear() { for (const q of this.peds) { this.release(q); q.av.dispose(); } }
}
