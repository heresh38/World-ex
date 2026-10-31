// Road traffic: a fixed population of everyday cars created with the world (nothing spawns or despawns).
// Cars follow the lanes, turn at city crossings, brake for anything ahead and are updated less often far away.
// Every car has a visible driver (civilian model in the Sit pose). Shoot the driver through the glass and the car
// rolls to a stop with the horn blaring; ram a car and it becomes a physics body (the driver rejoins the lane once
// it has stopped); hijack it with E and the driver bails out and runs.
import * as THREE from 'three';
import { Car, CAR_MODELS, ROAD_PAINTS } from '../../game/vehicles.js';
import { Avatar } from '../../game/avatar.js';
import { raySphere, rayCyl } from '../../game/combat.js';
import { PITCH, CITY_EDGE } from './layout.js';

const COUNT_CITY = 96, COUNT_HWY = 26;
const WEIGHTS = [['car_hatch', .28], ['car_sedan', .3], ['car_suv', .2], ['car_pickup', .1], ['car_van', .12]];
const SKIN = ['#f4d6c6', '#e8bfa5', '#d4a184', '#b9805f', '#8f5b3f', '#6b4130', '#4a2d22'];
const HAIR = ['#1a1310', '#2b1d14', '#4a3020', '#7a5432', '#b88b4e', '#d8c08a', '#8a8a8a'];
const SHIRT = ['#e8e6e2', '#2a2d33', '#7a1f2a', '#1f4a7a', '#2f6a4a', '#c9a24a', '#6a4a8a', '#9aa0a8', '#3a6a8a'];
const PANTS = ['#2a3a5a', '#1f2228', '#4a4030', '#6a6a70', '#2f3a2a'];
const HIP = { civ_male: .45, civ_female: .39 };
const TARGET_H = { female: 1.65, male: 1.77 };
const modelH = {};
const pick = (a, r) => a[Math.floor(r() * a.length)];
const _p = new THREE.Vector3(), _d = new THREE.Vector3(), _o = new THREE.Vector3(), _h = new THREE.Vector3(), _q = new THREE.Quaternion();
const wrap = a => Math.atan2(Math.sin(a), Math.cos(a));

function bendWorld(bone, axis, ang) {
  if (!bone || !bone.parent) return;
  bone.parent.getWorldQuaternion(_q);
  const ax = axis.clone().applyQuaternion(_q.invert()).normalize();
  bone.quaternion.premultiply(new THREE.Quaternion().setFromAxisAngle(ax, ang));
  bone.updateMatrixWorld(true);
}

// ---------------------------------------------------------------- the person at the wheel
class Driver {
  constructor(game, car, r) {
    this.g = game; this.car = car;
    this.sex = r() < .5 ? 'male' : 'female';
    const model = this.sex === 'male' ? 'civ_male' : 'civ_female';
    const av = this.av = new Avatar(game.assets, model);
    if (!modelH[model]) { av.root.updateMatrixWorld(true); modelH[model] = new THREE.Box3().setFromObject(av.model).getSize(_h).y || TARGET_H[this.sex]; }
    const sc = TARGET_H[this.sex] / modelH[model];
    av.root.scale.setScalar(sc);
    av.setLook(pick(av.outfits, r), pick(av.hairStyles, r));
    const tint = (prefix, hex) => av.allMats.forEach(m => { if (m.name.startsWith(prefix)) m.color.copy(m.userData.base).multiply(new THREE.Color(hex)); });
    tint('skin', pick(SKIN, r)); tint('hair', pick(HAIR, r)); tint('shirt', pick(SHIRT, r)); tint('pants', pick(PANTS, r));
    av.root.traverse(o => { if (o.isMesh) { o.frustumCulled = true; o.castShadow = false; } });
    av.mixer.stopAllAction(); av.current = null; av.play('Sit', 0); av.mixer.update(.01);
    av.root.position.copy(car.seatL); av.root.position.y -= HIP[model] * sc;
    (car.hi || car.root).add(av.root);
    this.alive = true; this.inCar = true; this.hp = 45; this.side = 'civilian'; this.radius = .5;
    this.T = { name: 'Driver' }; this.pos = new THREE.Vector3();
    game.combat.targets.add(this);
  }

  center(out) { return this.inCar ? this.car.pos && out.copy(this.car.pos).setY(this.car.pos.y + 1.1) : out.copy(this.pos).setY(this.pos.y + 1); }

  hitTest(o, d, max) {
    const av = this.av;
    if (this.inCar && !this.car.hi.visible) {
      // far away the detailed car (and its driver) is not drawn: approximate the head from the seat
      _h.copy(this.car.eyeL).applyMatrix4(this.car.root.matrixWorld);
      const t = raySphere(o, d, _h, .18);
      return t >= 0 && t < max ? { dist: t, crit: true } : null;
    }
    if (!av.head) return null;
    av.head.getWorldPosition(_h); _h.y += .07;
    const th = raySphere(o, d, _h, .14);
    let best = th >= 0 && th < max ? th : -1, crit = best >= 0;
    let tb = -1;
    if (this.inCar) { (av.chest || av.spine).getWorldPosition(_o); tb = raySphere(o, d, _o, .22); }
    else tb = rayCyl(o, d, this.pos.x, this.pos.z, this.pos.y, this.pos.y + 1.5, .28);
    if (tb >= 0 && tb < max && (best < 0 || tb < best - .05)) { best = tb; crit = false; }
    return best >= 0 ? { dist: best, crit } : null;
  }

  takeDamage(dmg, crit, point, dir, side) {
    if (!this.alive) return { killed: false };
    const g = this.g;
    this.hp -= dmg;
    if (point) g.fx.blood(point, dir ? dir.clone().negate() : null, crit ? 1.3 : .8);
    if (this.inCar && point && dir) {
      // the bullet went through the glass first: crack it where it entered
      const hit = this.car.surfaceHit(point.clone().addScaledVector(dir, -.4), dir);
      if (hit && hit.glass) { this.car.decal(hit); g.fx.emit(hit.point, 12, 3, 0xd8f0ff, .6, 9, .025); }
    }
    g.world.population && g.world.population.alarm(point || this.pos, 30, point);
    if (this.hp <= 0) { this.kill(side === 'player', dir ? dir.clone().setY(.3).multiplyScalar(3) : null); return { killed: true }; }
    if (this.inCar && this.car.t) this.car.t.panicT = 8;
    else if (!this.inCar) this.fleeFrom(point || g.player.pos);
    return { killed: false };
  }

  kill(byPlayer, impulse) {
    if (!this.alive) return;
    const g = this.g;
    this.alive = false;
    g.combat.targets.delete(this);
    g.save.stats.civilians = (g.save.stats.civilians || 0) + 1;
    if (byPlayer && g.world.wanted) g.world.wanted.crime(1, this.inCar ? this.car.pos : this.pos);
    g.audio.hurt();
    if (this.inCar) {
      // slump forward onto the wheel; the car rolls on with nobody driving
      this.car.root.updateMatrixWorld(true);
      const right = new THREE.Vector3(1, 0, 0).applyQuaternion(this.car.root.getWorldQuaternion(new THREE.Quaternion()));
      bendWorld(this.av.spine, right, .35); bendWorld(this.av.chest, right, .25); bendWorld(this.av.head, right, .5);
      this.car.hornT = 3 + Math.random() * 4;
      if (this.car.t && this.car.t.mgr) this.car.t.mgr.onDriverDead(this.car);
    } else {
      this.av.ragdoll(impulse || new THREE.Vector3(0, 1, 0), (x, z) => g.world.collision.ground(x, z));
      g.fx.bloodPool(this.pos.clone(), 1);
    }
  }

  // move out of the car into the world (keeps the current world transform)
  leaveCar(side) {
    const g = this.g;
    this.inCar = false;
    g.scene.attach(this.av.root);
    const c = this.car;
    this.pos.copy(c.pos).add(new THREE.Vector3(Math.cos(c.yaw), 0, -Math.sin(c.yaw)).multiplyScalar(c.hw + .7 * side));
    this.pos.y = g.world.collision.support(this.pos.x, this.pos.z, c.pos.y + 1);
    this.av.root.position.copy(this.pos);
    this.av.root.quaternion.setFromAxisAngle(new THREE.Vector3(0, 1, 0), c.yaw);
  }

  // a dead driver pulled out when the player takes the car
  eject() {
    if (!this.inCar) return;
    this.leaveCar(1);
    this.av.mixer.stopAllAction(); this.av.current = null;
    this.av.ragdoll(new THREE.Vector3(Math.cos(this.car.yaw), .5, -Math.sin(this.car.yaw)).multiplyScalar(2), (x, z) => this.g.world.collision.ground(x, z));
  }

  // a living driver jumps out and runs
  bail() {
    if (!this.inCar) return;
    this.leaveCar(1);
    this.vel = new THREE.Vector3(); this.fleeFrom(this.g.player.pos);
    this.av.play('RunRelaxed', .1);
  }

  fleeFrom(p) {
    this.state = 'flee'; this.fleeT = 7 + Math.random() * 4;
    this.dir = new THREE.Vector3().subVectors(this.pos, p).setY(0);
    if (this.dir.lengthSq() < .01) this.dir.set(Math.random() - .5, 0, Math.random() - .5);
    this.dir.normalize();
  }

  // on foot after bailing out
  walk(dt) {
    const g = this.g, av = this.av;
    if (!this.alive) { av.update(dt); return; }
    if (this.state === 'flee') {
      this.fleeT -= dt;
      this.vel.set(this.dir.x * 4.4, -9, this.dir.z * 4.4);
      const x0 = this.pos.x, z0 = this.pos.z;
      g.world.collision.moveCapsule(this.pos, this.vel, .3, 1.7, dt);
      if (Math.hypot(this.pos.x - x0, this.pos.z - z0) < 4.4 * dt * .4) { const s = Math.random() < .5 ? 1 : -1; this.dir.set(-this.dir.z * s, 0, this.dir.x * s); }
      const hit = g.vehicles.pedContact(this);
      if (hit) { this.kill(hit.car === g.vehicles.current, new THREE.Vector3(Math.sin(hit.car.yaw), .5, Math.cos(hit.car.yaw)).multiplyScalar(Math.min(14, hit.speed * .6))); return; }
      av.root.position.copy(this.pos); av.root.rotation.set(0, Math.atan2(this.dir.x, this.dir.z), 0);
      if (this.fleeT <= 0) { this.state = 'idle'; av.play('IdleRelaxed', .3); }
    }
    if (this.pos.distanceTo(g.player.pos) < 80) av.update(dt);
  }

  flee(p) { if (!this.inCar && this.alive) this.fleeFrom(p); }

  dispose() { if (this.disposed) return; this.disposed = true; this.g.combat.targets.delete(this); this.av.dispose(); }
}

// ---------------------------------------------------------------- traffic
export class Traffic {
  constructor(game, map) {
    this.g = game; this.map = map; this.cars = []; this.bailed = []; this.frame = 0;
    this.pedGrid = new Map();
    this.indexLanes();
    let seed = 777;
    const r = () => { seed = (seed * 16807) % 2147483647; return (seed - 1) / 2147483646; };
    const city = map.lanes.filter(l => l.city), hwy = map.lanes.filter(l => !l.city);
    this.populate(city, COUNT_CITY, r);
    this.populate(hwy, COUNT_HWY, r);
  }

  // city lanes are straight lines: remember axis, direction and road centre so cars can turn at crossings
  indexLanes() {
    this.byKey = new Map();
    for (const l of this.map.lanes) {
      if (!l.city) continue;
      const a = l.pts[0], b = l.pts[1];
      l.ax = Math.abs(a.x - b.x) < 1e-3 ? 1 : 0;                       // 1: runs along z
      l.dir = Math.sign(l.ax ? b.z - a.z : b.x - a.x);
      l.c = l.ax ? a.x + l.dir * 3.2 : a.z - l.dir * 3.2;
      this.byKey.set(l.ax + ',' + l.dir + ',' + Math.round(l.c), l);
    }
  }

  populate(lanes, n, r) {
    const total = lanes.reduce((a, l) => a + l.total, 0);
    for (let i = 0, tries = 0; i < n && tries < n * 20; tries++) {
      let x = r() * total, lane = lanes[0];
      for (const l of lanes) { x -= l.total; if (x <= 0) { lane = l; break; } }
      const s = 10 + r() * (lane.total - 20);
      if (this.cars.some(t => t.lane === lane && Math.abs(t.s - s) < 22)) continue;
      this.map.lanePoint(lane, s, _p, _d);
      if (Math.abs(_p.x) < 25 && Math.abs(_p.z) < 45) continue;           // keep the spaceport apron clear
      let w = r(), model = WEIGHTS[0][0];
      for (const [m, k] of WEIGHTS) { w -= k; if (w <= 0) { model = m; break; } }
      const car = new Car(this.g, model, pick(ROAD_PAINTS, r), _p, Math.atan2(_d.x, _d.z));
      car.dynamic = false; car.sleep = false; car.traffic = this; car.kvel = new THREE.Vector3();
      const sp = lane.speed * (.8 + r() * .3);
      const t = { car, lane, s, v: sp * .5, want: sp, stopT: 0, blockT: 0, ignoreT: 0, panicT: 0, mode: 'lane', acc: 0, mgr: this, idx: i };
      car.t = t;
      car.driver = new Driver(this.g, car, r);
      this.g.vehicles.cars.push(car);
      this.cars.push(t);
      i++;
    }
  }

  // ---------------------------------------------------------------- events from vehicles.js
  toPhysics(car) {
    const t = car.t; if (!t || t.mode === 'dyn') return;
    t.mode = 'dyn'; t.restT = 0;
    car.dynamic = true; car.sleep = false;
    car.vel.copy(car.kvel || car.vel); car.yawRate = 0;
  }

  knock(car) { this.toPhysics(car); }

  onDriverDead(car) {
    this.toPhysics(car);
    car.ctl = { thr: 0, st: (Math.random() - .5) * .5, driver: false };
  }

  onWrecked(car) { this.toPhysics(car); car.ctl = { thr: 0, st: 0, driver: false }; }

  onShot(car, side) {
    const t = car.t; if (!t || !car.driverAlive()) return;
    t.panicT = 8; t.stopT = Math.min(t.stopT, .8);
    this.g.world.population && this.g.world.population.alarm(car.pos, 25, this.g.player.pos);
  }

  hitSomeone(car) { if (car.t) car.t.stopT = 4; }

  // the player takes the car: the driver bails out (or the body is pulled out)
  hijack(car) {
    const t = car.t; if (!t) return;
    const i = this.cars.indexOf(t); if (i >= 0) this.cars.splice(i, 1);
    const g = this.g;
    car.traffic = null; car.t = null;
    car.dynamic = true; car.sleep = false; car.vel.copy(car.kvel || car.vel).multiplyScalar(.3);
    const d = car.driver;
    if (d) { if (d.alive) { d.bail(); this.bailed.push(d); } else d.eject(); car.driver = null; this.bailed.includes(d) || this.bailed.push(d); }
    const pop = g.world.population;
    pop && pop.alarm(car.pos, 25, g.player.pos);
    const witnesses = pop && pop.peds.some(q => q.active && q.alive && q.pos.distanceTo(car.pos) < 35);
    if ((witnesses || Math.random() < .5) && g.world.wanted) g.world.wanted.crime(1, car.pos);
    g.hud.toast('Vehicle hijacked');
  }

  // ---------------------------------------------------------------- driving
  buildPedGrid() {
    this.pedGrid.clear();
    const pop = this.g.world.population; if (!pop) return;
    for (const q of pop.peds) {
      if (!q.alive || !q.active) continue;
      const k = (Math.floor(q.pos.x / 16) * 7919) ^ Math.floor(q.pos.z / 16);
      let l = this.pedGrid.get(k); if (!l) this.pedGrid.set(k, l = []); l.push(q.pos);
    }
  }

  obstacleAhead(t, pos, dir, far) {
    const g = this.g, look = 9 + t.v * .9;
    const check = (q, r) => {
      _o.subVectors(q, pos); const ahead = _o.x * dir.x + _o.z * dir.z;
      if (ahead < 1 || ahead > look || Math.abs(_o.y) > 4) return false;
      return Math.abs(_o.x * dir.z - _o.z * dir.x) < r;
    };
    const p = g.player;
    if (p.mode === 'foot' && !p.dead && check(p.pos, 2.1)) return 'p';
    const fx = pos.x + dir.x * look * .5, fz = pos.z + dir.z * look * .5;
    if (t.ignoreT <= 0) for (const c of g.vehicles.carsNear(fx, fz, this._cn || (this._cn = []))) {
      if (c === t.car) continue;
      if (check(c.pos, 2.5)) {
        // same lane and heading away from us: follow instead of stopping dead
        return 'c';
      }
    }
    if (g.vehicles.current && g.vehicles.current.board && check(g.vehicles.current.pos, 2)) return 'p';
    if (far) return false;
    const ix = Math.floor(fx / 16), iz = Math.floor(fz / 16);
    for (let a = ix - 1; a <= ix + 1; a++) for (let b = iz - 1; b <= iz + 1; b++) {
      const l = this.pedGrid.get((a * 7919) ^ b); if (l) for (const q of l) if (check(q, 1.7)) return 'q';
    }
    return false;
  }

  // at a city crossing: maybe turn onto the cross street
  maybeTurn(t, aPrev, aNow) {
    const L = t.lane; if (!L.city || L.ax === undefined) return false;
    const k0 = Math.floor(aPrev / PITCH - .5), k1 = Math.floor(aNow / PITCH - .5);
    if (k0 === k1) return false;
    const roll = Math.random();
    if (roll > .34) return false;
    const crossC = (Math.max(k0, k1) + .5) * PITCH;
    const hx = L.ax ? 0 : L.dir, hz = L.ax ? L.dir : 0;
    const right = [-hz, hx], turn = roll < .22 ? right : [hz, -hx];
    const nax = turn[0] !== 0 ? 0 : 1, ndir = Math.sign(turn[0] || turn[1]);
    const nl = this.byKey.get(nax + ',' + ndir + ',' + Math.round(crossC));
    if (!nl) return false;
    const coord = nax ? t.car.pos.z : t.car.pos.x;
    const s = ndir > 0 ? coord + CITY_EDGE : CITY_EDGE - coord;
    if (s < 12 || s > nl.total - 12) return false;
    t.blend = { from: t.car.pos.clone(), t: 0, dur: 1.6 };
    t.lane = nl; t.s = s + 3; t.v = Math.min(t.v, 7);
    return true;
  }

  update(dt) {
    const g = this.g, map = this.map;
    this.frame++;
    this.buildPedGrid();
    const P = g.player.mode === 'car' && g.vehicles.current ? g.vehicles.current.pos : g.player.pos;
    for (let i = 0; i < this.cars.length; i++) {
      const t = this.cars[i], car = t.car;
      if (t.mode === 'dyn') { this.updateDyn(t, dt); continue; }
      const d2 = (car.pos.x - P.x) ** 2 + (car.pos.z - P.z) ** 2;
      const far = d2 > 260 * 260;
      // far away: the same drive, simulated a fifth as often
      t.acc += dt;
      if (far && (i + this.frame) % 5) continue;
      const step = Math.min(.5, t.acc); t.acc = 0;
      t.stopT -= step; t.ignoreT -= step; t.panicT -= step;
      map.lanePoint(t.lane, t.s, _p, _d);
      const ob = t.stopT > 0 ? 's' : this.obstacleAhead(t, car.pos, _d, far);
      if (ob === 'c') { t.blockT += step; if (t.blockT > 7) { t.ignoreT = 2.5; t.blockT = 0; } } else if (!ob) t.blockT = 0;
      const want = ob ? 0 : t.want * (t.panicT > 0 ? 1.6 : 1);
      t.v += Math.max(-10 * step, Math.min(4 * step, want - t.v));
      if (t.v < 0) t.v = 0;
      const a0 = t.lane.ax ? car.pos.z : car.pos.x;
      t.s += t.v * step;
      if (t.s >= t.lane.total) {
        const next = map.nextLane(t.lane.pts[t.lane.pts.length - 1], t.lane);
        if (next) { t.blend = { from: car.pos.clone(), t: 0, dur: 1.8 }; t.lane = next; t.s = 0; t.want = next.speed * (.8 + Math.random() * .3); t.v = Math.min(t.v, 6); }
        else t.s = t.lane.total;
      }
      map.lanePoint(t.lane, t.s, _p, _d);
      if (!t.blend && t.lane.city) this.maybeTurn(t, a0, t.lane.ax ? _p.z : _p.x) && map.lanePoint(t.lane, t.s, _p, _d);
      if (t.blend) {
        t.blend.t += step; const k = Math.min(1, t.blend.t / t.blend.dur), e = k * k * (3 - 2 * k);
        _p.lerpVectors(t.blend.from, _p, e);
        if (k >= 1) t.blend = null;
      }
      const tx = _p.x - car.pos.x, tz = _p.z - car.pos.z;
      const yawT = (tx * tx + tz * tz > 1e-4 && t.v > .3) ? Math.atan2(tx, tz) : Math.atan2(_d.x, _d.z);
      const dy = wrap(yawT - car.yaw);
      car.yaw += dy * Math.min(1, step * 5);
      car.kvel.set(tx / Math.max(step, 1e-3), 0, tz / Math.max(step, 1e-3));
      if (car.kvel.lengthSq() > 900) car.kvel.setLength(30);
      car.pos.x = _p.x; car.pos.z = _p.z;
      if (d2 < 160 * 160) { const gu = car.groundUnder(); car.pos.y = gu.y; car.pitch += (gu.pitch - car.pitch) * Math.min(1, step * 8); car.roll += (gu.roll - car.roll) * Math.min(1, step * 8); }
      else { car.pos.y = _p.y; car.pitch = car.roll = 0; }
      car.speed = t.v; car.vF = t.v; car.steer = THREE.MathUtils.clamp(dy * 4, -1, 1);
      car.ctl = { thr: want > t.v + .5 ? 1 : 0, brake: !!ob && t.v > .3 };
    }
    for (const d of this.bailed) d.walk(dt);
  }

  // crashed / knocked cars run on physics; a living driver brakes and rejoins the lane once stopped
  updateDyn(t, dt) {
    const car = t.car;
    const alive = car.driverAlive() && car.alive;
    car.ctl = alive ? { thr: 0, st: 0, brake: true, driver: true } : (car.ctl || { driver: false });
    if (!alive) return;
    if (car.speed < .3 && Math.abs(car.roll) < .3 && Math.abs(car.pitch) < .3) {
      t.restT = (t.restT || 0) + dt;
      if (t.restT > 5) {
        // closest point on the lane
        let best = -1, bd = 25;
        for (let s = Math.max(0, t.s - 40); s < Math.min(t.lane.total, t.s + 40); s += 2) {
          this.map.lanePoint(t.lane, s, _p, _d); const d = (_p.x - car.pos.x) ** 2 + (_p.z - car.pos.z) ** 2; if (d < bd) { bd = d; best = s; }
        }
        if (best >= 0) {
          t.mode = 'lane'; t.s = best; t.v = 0; t.stopT = 1; t.blend = { from: car.pos.clone(), t: 0, dur: 2.5 };
          car.dynamic = false; car.vel.set(0, 0, 0); car.yawRate = 0;
        }
        t.restT = 0;
      }
    } else t.restT = 0;
  }

  // the player's car crashed near here: nearby traffic stops for a moment
  crash(pos) { for (const t of this.cars) if (t.car.pos.distanceTo(pos) < 14) t.stopT = 3 + Math.random() * 3; }

  clear() {
    for (const d of this.bailed) d.dispose();
    for (const t of this.cars) if (t.car.driver) t.car.driver.dispose();
    this.bailed = []; this.cars = [];
  }
}
