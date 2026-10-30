// Road traffic: hover cars following lanes around the player. They brake for obstacles, react to crashes,
// can be shot up, and can be hijacked (E) - the driver bails out and runs.
import * as THREE from 'three';
import { Car } from '../../game/vehicles.js';

const MODELS = ['car_sport', 'car_utility'];
const PAINTS = ['#a3121f', '#2a4f7a', '#e8e2d4', '#1c1f24', '#c79a45', '#2f6b55', '#6a4fa0', '#d96a1b', '#8a9099', '#0f4b5c', '#f2f2f2', '#3a3a3a'];
const _p = new THREE.Vector3(), _d = new THREE.Vector3(), _o = new THREE.Vector3();

export class Traffic {
  constructor(game, map) {
    this.g = game; this.map = map; this.cars = []; this.spawnT = 0;
  }

  spawn(nearPos) {
    const lanes = this.map.lanes;
    for (let tries = 0; tries < 16; tries++) {
      const lane = lanes[Math.floor(Math.random() * lanes.length)];
      const s = Math.random() * lane.total;
      this.map.lanePoint(lane, s, _p, _d);
      const d = _p.distanceTo(nearPos);
      if (d < 90 || d > 260) continue;
      if (this.cars.some(t => t.lane === lane && Math.abs(t.s - s) < 18)) continue;
      const car = new Car(this.g, MODELS[Math.random() < .7 ? 0 : 1], PAINTS[Math.floor(Math.random() * PAINTS.length)], _p, Math.atan2(_d.x, _d.z));
      car.ai = true;
      const t = { car, lane, s, v: lane.speed * (.8 + Math.random() * .3), want: lane.speed * (.8 + Math.random() * .3), stopT: 0 };
      car.traffic = t;
      t.box = new THREE.Box3(); t.box.tag = 'traffic'; t.box.car = car;
      this.g.world.collision.dynamic.push(t.box);
      this.g.vehicles.cars.push(car);
      this.cars.push(t);
      return;
    }
  }

  remove(t, keepCar = false) {
    const i = this.cars.indexOf(t); if (i >= 0) this.cars.splice(i, 1);
    const di = this.g.world.collision.dynamic.indexOf(t.box); if (di >= 0) this.g.world.collision.dynamic.splice(di, 1);
    if (!keepCar) {
      const ci = this.g.vehicles.cars.indexOf(t.car); if (ci >= 0) this.g.vehicles.cars.splice(ci, 1);
      t.car.dispose();
    }
    t.car.traffic = null;
  }

  // the player takes the car: the driver bails out and runs
  hijack(car) {
    const t = car.traffic; if (!t) return;
    this.remove(t, true);
    car.ai = false; car.vel.set(Math.sin(car.yaw), 0, Math.cos(car.yaw)).multiplyScalar(t.v * .3);
    const side = new THREE.Vector3(Math.cos(car.yaw), 0, -Math.sin(car.yaw));
    const pop = this.g.world.population;
    pop.alarm(car.pos, 25, this.g.player.pos);
    const g = this.g;
    // a nearby pedestrian (or the driver) saw it
    const witnesses = pop.peds.some(q => q.active && q.alive && q.pos.distanceTo(car.pos) < 35);
    if (witnesses || Math.random() < .5) g.world.wanted.crime(1, car.pos);
    g.hud.toast('Vehicle hijacked');
    return side;
  }

  obstacleAhead(t, pos, dir) {
    const g = this.g;
    const check = (q, r = 2.4) => {
      _o.subVectors(q, pos); const ahead = _o.dot(dir);
      if (ahead < 0 || ahead > 16) return false;
      const lat = Math.abs(_o.x * dir.z - _o.z * dir.x);
      return lat < r;
    };
    if (g.player.mode === 'foot' && check(g.player.pos, 2)) return true;
    if (g.vehicles.current && check(g.vehicles.current.pos, 2.8)) return true;
    for (const o of this.cars) if (o !== t && check(o.car.pos, 2.4)) return true;
    for (const q of g.world.population.peds) if (q.active && q.alive && check(q.pos, 1.8)) return true;
    return false;
  }

  update(dt) {
    const g = this.g, map = this.map;
    const p = g.player.mode === 'car' && g.vehicles.current ? g.vehicles.current.pos : g.player.pos;
    const urban = Math.abs(p.x) < 600 && Math.abs(p.z) < 600;
    const target = urban ? 18 : 9;
    this.spawnT -= dt;
    if (this.spawnT <= 0) { this.spawnT = .4; if (this.cars.length < target) this.spawn(p); }
    for (let i = this.cars.length - 1; i >= 0; i--) {
      const t = this.cars[i], car = t.car;
      if (!car.alive) { this.remove(t, true); continue; }
      map.lanePoint(t.lane, t.s, _p, _d);
      if (_p.distanceTo(p) > 320) { this.remove(t); continue; }
      t.stopT -= dt;
      const blocked = this.obstacleAhead(t, _p, _d) || t.stopT > 0;
      const want = blocked ? 0 : t.want;
      t.v += Math.max(-14 * dt, Math.min(5 * dt, want - t.v));
      t.s += t.v * dt;
      if (t.s >= t.lane.total) {
        const next = map.nextLane(t.lane.pts[t.lane.pts.length - 1], t.lane);
        if (!next) { this.remove(t); continue; }
        t.lane = next; t.s = 0; t.want = next.speed * (.8 + Math.random() * .3);
      }
      map.lanePoint(t.lane, t.s, _p, _d);
      const yaw = Math.atan2(_d.x, _d.z);
      let dy = yaw - car.yaw; dy = Math.atan2(Math.sin(dy), Math.cos(dy));
      car.yaw += dy * Math.min(1, dt * 6);
      car.pos.copy(_p); car.speed = t.v;
      car.bob += dt * 2.4;
      car.root.position.set(_p.x, _p.y + .25 + Math.sin(car.bob) * .05, _p.z);
      car.root.rotation.set(0, car.yaw, -dy * .3, 'YXZ');
      if (car.glow) car.glow.emissiveIntensity = 1.6 + t.v * .04;
      t.box.min.set(_p.x - 2.1, _p.y, _p.z - 2.1); t.box.max.set(_p.x + 2.1, _p.y + 1.6, _p.z + 2.1);
      // a car rolling into the player on foot
      if (g.player.mode === 'foot' && !g.player.dead && t.v > 6 && Math.hypot(g.player.pos.x - _p.x, g.player.pos.z - _p.z) < 2) {
        g.player.damage(25, _p); g.player.vel.addScaledVector(_d, 6); g.player.vel.y = 4; t.stopT = 3;
      }
    }
  }

  // the player's car crashed into something near this point: nearby traffic stops for a moment
  crash(pos) { for (const t of this.cars) if (t.car.pos.distanceTo(pos) < 12) t.stopT = 3 + Math.random() * 3; }

  clear() { for (const t of [...this.cars]) this.remove(t); }
}
