// Vehicles: modern road cars (cars.glb) with four-wheel suspension physics, and the player's hover board (V).
// Cars fall, land and roll on the terrain and on box tops (bridges, ramps); they collide with walls, each other, the
// player and pedestrians at all times. Cars are combat targets: bullets leave holes and cracked glass, heavy damage
// smokes and burns, and a traffic driver can be shot through the glass (the car then rolls to a stop).
import * as THREE from 'three';
import { raySphere } from './combat.js';

export const CAR_MODELS = ['car_hatch', 'car_sedan', 'car_suv', 'car_pickup', 'car_van'];
export const BOARDS = ['board_sport', 'board_utility'];
const LEGACY = { car_sport: ['car_hatch', 'car_sedan'], car_utility: ['car_suv', 'car_pickup', 'car_van'] };
export const ROAD_PAINTS = ['#e8e6e2', '#f4f4f2', '#1a1b1e', '#2b2d31', '#8d9196', '#b9bcc0', '#5a5e63', '#1d2f4f', '#2a4f7a', '#7a1418',
  '#a3121f', '#3d4a3a', '#5b4a3a', '#c9c2b0', '#0f4b5c', '#d96a1b'];

// handling per model (accel m/s^2, top m/s, grip 1/s, mass kg)
const SPECS = {
  car_hatch: { node: 'hatch', mass: 1150, accel: 7.6, top: 46, grip: 10, steer: .62, hp: 520 },
  car_sedan: { node: 'sedan', mass: 1450, accel: 8.2, top: 56, grip: 10, steer: .58, hp: 600 },
  car_suv: { node: 'suv', mass: 1900, accel: 7.0, top: 50, grip: 9, steer: .56, hp: 700 },
  car_pickup: { node: 'pickup', mass: 2200, accel: 6.4, top: 48, grip: 8.5, steer: .52, hp: 760 },
  car_van: { node: 'van', mass: 2100, accel: 5.6, top: 42, grip: 8.5, steer: .54, hp: 720 },
  // frontier all-terrain rover: soft long-travel suspension, lugged tyres (dropped by the ship on V while boarding)
  car_rover: { node: 'rover', mass: 1500, accel: 8.4, top: 38, grip: 7.5, steer: .62, hp: 1100, droop: .26, bump: .2, static: .1 },
  board_sport: { board: true, name: 'Vanta Glide', mass: 90, accel: 13, top: 25, boost: 36, turn: 2.3, hp: 320 },
  board_utility: { board: true, name: 'Mule Deck', mass: 120, accel: 10, top: 21, boost: 30, turn: 1.9, hp: 480 },
};
// how high the Sit clip puts the hips above the avatar root
const HIP = { player_male: .48, player_female: .44, civ_male: .45, civ_female: .39 };
const G = 9.8, DROOP = .13, BUMP = .11, STATIC = .06;     // default suspension travel (m); specs may override

const _v = new THREE.Vector3(), _w = new THREE.Vector3(), _q = new THREE.Quaternion(), _e = new THREE.Euler(), _m = new THREE.Matrix4();
const _o = new THREE.Vector3(), _d = new THREE.Vector3(), _ray = new THREE.Raycaster(), _inv = new THREE.Matrix4();
const _f = new THREE.Vector3(), _r = new THREE.Vector3();
const STANCE = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), Math.PI / 2);

export function boardModel(m) { return BOARDS.includes(m) ? m : (m === 'car_utility' ? 'board_utility' : 'board_sport'); }
export function roadModel(m, seed = Math.random()) {
  if (SPECS[m] && !SPECS[m].board) return m;
  const list = LEGACY[m] || CAR_MODELS;
  return list[Math.floor(Math.abs(seed) * list.length) % list.length];
}
function hashXZ(p) { const s = Math.sin(p.x * 12.9898 + p.z * 78.233) * 43758.5453; return s - Math.floor(s); }
const wrap = a => Math.atan2(Math.sin(a), Math.cos(a));

// water surface below (x,z) if the water module is present
function waterY(g, x, z) { const w = g.water; if (!w || !w.heightAt) return null; const h = w.heightAt(x, z); return h === undefined ? null : h; }

// ---------------------------------------------------------------- shared decal resources
let DECAL = null;
function decals(g) {
  if (DECAL) return DECAL;
  const T = g.assets.textures;
  DECAL = {
    geo: new THREE.PlaneGeometry(1, 1),
    hole: new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: .6, metalness: .4, transparent: true, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -4 }),
    crack: new THREE.MeshStandardMaterial({ color: 0xdfe8ee, roughness: .1, metalness: .2, transparent: true, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -4, side: THREE.DoubleSide }),
  };
  const load = (name, mat, key) => {
    if (T[name]) { mat[key] = T[name]; mat.needsUpdate = true; return; }
    g.assets.loadTexture(name.endsWith('_e') ? 'veh_' + name.replace(/_e$/, '') + '_e.jpg' : 'veh_' + name.replace(/_c$/, '') + '_c.jpg', !name.endsWith('_e'))
      .then(t => { T[name] = t; mat[key] = t; mat.needsUpdate = true; }).catch(() => {});
  };
  load('bullethole_c', DECAL.hole, 'map'); load('bullethole_e', DECAL.hole, 'alphaMap');
  load('glasscrack_c', DECAL.crack, 'map'); load('glasscrack_e', DECAL.crack, 'alphaMap');
  return DECAL;
}

// ================================================================ road car
export class Car {
  constructor(game, model, paint, pos, yaw) {
    const g = this.g = game;
    model = roadModel(model, hashXZ(pos));
    this.model = model;
    const sp = SPECS[model];
    const node = g.assets.clone('cars', 'CAR_' + sp.node);
    const meta = this.meta = JSON.parse(node.userData.worldex || '{}');
    this.S = { ...sp, name: meta.name || model, max: sp.top };
    this.root = new THREE.Group(); this.root.add(node); this.node = node;
    this.paint = paint || ROAD_PAINTS[Math.floor(hashXZ(pos) * ROAD_PAINTS.length)];
    // per-car materials: paint, brake lights, number plate offset
    const own = new Map();
    const plate = Math.floor(Math.random() * 8);
    node.traverse(o => {
      if (!o.isMesh) return;
      o.castShadow = !/glass/.test(o.material.name);
      const n = o.material.name;
      if (n === 'car_paint' || n === 'lamp_tail' || n === 'plate') {
        if (!own.has(n)) {
          const m = o.material.clone();
          if (n === 'car_paint') { m.color.set(this.paint); m.envMapIntensity = 1.3; }
          if (n === 'plate' && m.map) { m.map = m.map.clone(); m.map.offset.set((plate % 2) * .5, -Math.floor(plate / 2) * .25); m.map.needsUpdate = true; }
          own.set(n, m);
        }
        o.material = own.get(n);
      }
      if (/glass/.test(n)) o.material.side = THREE.DoubleSide;
    });
    this.mats = own; this.tail = own.get('lamp_tail'); this.paintMat = own.get('car_paint');
    const find = re => { let r = null; node.traverse(o => { if (!r && re.test(o.name)) r = o; }); return r; };
    this.hi = find(/^hi_/); this.lo = find(/^lo_/);
    this.steerWheel = find(/^steer_/); this.needleS = find(/^needleS_/); this.needleR = find(/^needleR_/);
    for (const n of [this.steerWheel, this.needleS, this.needleR]) if (n) n.userData.q0 = n.quaternion.clone();
    this.body = find(/^body_/);
    this.wheels = ['FL', 'FR', 'RL', 'RR'].map(k => {
      const piv = find(new RegExp('^wheel_' + k)), spin = find(new RegExp('^spin_' + k));
      const front = k[0] === 'F', left = k[1] === 'L';
      return { k, piv, spin, front, lx: (left ? 1 : -1) * meta.track / 2, lz: front ? meta.axleF : meta.axleR, off: 0, prev: 0, contact: false, rot: 0 };
    });
    const seat = find(/^seat_/), eye = find(/^eye_/);
    this.seatL = seat ? seat.position.clone() : new THREE.Vector3(.37, .45, 0);
    this.eyeL = eye ? eye.position.clone() : new THREE.Vector3(.37, 1.2, 0);
    // footprint (half extents) for collisions
    this.hw = meta.wid / 2 - .03; this.hlF = meta.front - .05; this.hlB = -meta.back - .05;
    this.hl = (this.hlF + this.hlB) / 2; this.cz = (this.hlF - this.hlB) / 2;      // box centre offset along +Z
    this.pos = pos.clone(); this.vel = new THREE.Vector3(); this.yaw = yaw; this.pitch = 0; this.roll = 0;
    this.yawRate = 0; this.pitchRate = 0; this.rollRate = 0; this.steer = 0; this.speed = 0; this.vF = 0;
    this.hp = this.S.hp; this.alive = true; this.burnt = false; this.dynamic = true; this.sleep = true;
    this.side = 'civilian'; this.radius = 2.2; this.T = { name: this.S.name };
    this.holes = []; this.smokeT = 0; this.hornT = 0; this.airT = 0; this.lastY = pos.y; this.upsideT = 0;
    this.lodNear = null;                 // forces the first LOD switch (both levels are visible in the file)
    this.settle();
    this.syncRoot();
    g.scene.add(this.root);
    g.combat && g.combat.targets.add(this);
  }

  get mass() { return this.S.mass; }

  // drop onto whatever is below without simulation (spawn / traffic placement)
  settle() {
    const h = this.groundUnder();
    this.pos.y = h.y; this.pitch = h.pitch; this.roll = h.roll; this.vel.y = 0;
    for (const w of this.wheels) { w.off = 0; w.prev = 0; }
  }

  // average support under the four wheels -> height, pitch and roll (cheap; used for traffic and spawning)
  groundUnder(yHint = null) {
    const col = this.g.world.collision, s = Math.sin(this.yaw), c = Math.cos(this.yaw);
    const yRef = yHint === null ? this.pos.y + 1.2 : yHint;
    const hs = this.wheels.map(w => {
      const x = this.pos.x + c * w.lx + s * w.lz, z = this.pos.z - s * w.lx + c * w.lz;
      return col.support(x, z, yRef);
    });
    const front = (hs[0] + hs[1]) / 2, back = (hs[2] + hs[3]) / 2, left = (hs[0] + hs[2]) / 2, right = (hs[1] + hs[3]) / 2;
    const wb = this.meta.axleF - this.meta.axleR, tr = this.meta.track;
    return { y: (front + back) / 2, pitch: -Math.atan2(front - back, wb), roll: Math.atan2(left - right, tr) };
  }

  syncRoot() {
    this.root.position.copy(this.pos);
    this.root.rotation.set(this.pitch, this.yaw, this.roll, 'YXZ');
  }

  wake() { this.sleep = false; }

  // ---------------------------------------------------------------- physics (dynamic cars)
  physics(dt, ctl) {
    const g = this.g, col = g.world.collision, S = this.S, M = this.mass;
    const DR = S.droop || DROOP, BU = S.bump || BUMP, ST = S.static || STATIC;
    const k = M * G / (4 * ST), c = .75 * Math.sqrt(k * M / 4);
    _e.set(this.pitch, this.yaw, this.roll, 'YXZ'); _q.setFromEuler(_e);
    let Fy = 0, tp = 0, tr = 0, contacts = 0, push = 0;
    for (const w of this.wheels) {
      _v.set(w.lx, this.meta.rw, w.lz).applyQuaternion(_q).add(this.pos);
      let gy = col.support(_v.x, _v.z, _v.y + .25);
      const wy = waterY(g, _v.x, _v.z);
      w.water = wy !== null && wy > gy + .3 ? wy : null;
      let off = gy + this.meta.rw - _v.y;
      if (off < -DR) { w.contact = false; w.off += (-DR - w.off) * Math.min(1, dt * 10); w.prev = w.off; continue; }
      w.contact = true; contacts++;
      if (off > BU) { push = Math.max(push, off - BU); off = BU; }
      const rate = (off - w.prev) / dt; w.prev = off; w.off = off;
      const F = Math.max(0, k * (off + ST) + c * rate);
      Fy += F; tp += F * w.lz; tr += F * w.lx;
    }
    // buoyancy when the body sinks into water: floats low, drifts, heavy drag
    const wy = waterY(g, this.pos.x, this.pos.z);
    let inWater = 0;
    if (wy !== null && wy > this.pos.y + .3) {
      inWater = Math.min(1, (wy - this.pos.y - .3) / 1.0);
      Fy += M * G * 1.05 * inWater;
      if (!this.wet) { this.wet = true; g.water.splash && g.water.splash(this.pos.clone().setY(wy), 3); g.audio.land(); }
    } else if (this.wet && (wy === null || wy < this.pos.y)) this.wet = false;
    const Ip = M * 1.6, Ir = M * .5;
    this.vel.y += (Fy / M - G) * dt;
    this.pitchRate += (-tp / Ip) * dt; this.rollRate += (tr / Ir) * dt;
    if (push > 0) { this.pos.y += push; if (this.vel.y < 0) this.vel.y *= .2; }
    const cf = contacts / 4;
    // drive / steer / grip
    _f.set(Math.sin(this.yaw), 0, Math.cos(this.yaw)); _r.set(Math.cos(this.yaw), 0, -Math.sin(this.yaw));
    let vF = this.vel.x * _f.x + this.vel.z * _f.z, vL = this.vel.x * _r.x + this.vel.z * _r.z;
    const { thr = 0, st = 0, brake = false, boost = false, hand = false } = ctl;
    this.steer += (st - this.steer) * Math.min(1, dt * 5);
    if (cf > 0) {
      const top = S.top * (boost ? 1.15 : 1);
      if (thr > 0) vF += (vF < 0 ? S.accel * 1.8 : S.accel * (boost ? 1.3 : 1) * Math.max(0, 1 - (vF / top) ** 2)) * thr * dt * cf;
      else if (thr < 0) vF += (vF > .5 ? -S.accel * 1.9 : -S.accel * .55 * (vF > -12 ? 1 : 0)) * -thr * dt * cf;
      const roll = (ctl.driver ? .25 : 1.6) + .0005 * vF * vF;               // no driver: engine braking stops it
      vF -= Math.sign(vF) * Math.min(Math.abs(vF), roll * dt * cf);
      if (brake) vF -= Math.sign(vF) * Math.min(Math.abs(vF), 14 * dt * cf);
      if (hand) vF -= Math.sign(vF) * Math.min(Math.abs(vF), 4 * dt * cf);
      vF += G * Math.sin(this.pitch) * dt * cf * (ctl.driver || !this.parked ? 1 : 0);   // rolls downhill
      const ang = this.steer * S.steer * (1 - Math.min(.65, Math.abs(vF) / 55));
      const target = vF * Math.tan(ang) / Math.max(1, this.meta.wb);
      this.yawRate += (target - this.yawRate) * Math.min(1, dt * 9 * cf);
      const grip = (hand ? 1.6 : S.grip) * cf;
      vL *= Math.max(0, 1 - grip * dt);
    } else this.yawRate *= 1 - .3 * dt;
    if (inWater) { vF *= 1 - Math.min(1, 1.8 * inWater * dt); vL *= 1 - Math.min(1, 2 * inWater * dt); this.vel.y *= 1 - Math.min(1, 2 * inWater * dt); }
    this.yaw += this.yawRate * dt;
    _f.set(Math.sin(this.yaw), 0, Math.cos(this.yaw)); _r.set(Math.cos(this.yaw), 0, -Math.sin(this.yaw));
    this.vel.x = _f.x * vF + _r.x * vL; this.vel.z = _f.z * vF + _r.z * vL;
    // angular damping, integrate
    this.pitchRate *= 1 - Math.min(1, (cf > 0 ? 1.5 : .2) * dt); this.rollRate *= 1 - Math.min(1, (cf > 0 ? 1.5 : .2) * dt);
    this.pitch += this.pitchRate * dt; this.roll += this.rollRate * dt;
    this.pitch = THREE.MathUtils.clamp(this.pitch, -1.3, 1.3); this.roll = THREE.MathUtils.clamp(this.roll, -1.4, 1.4);
    const vy0 = this.vel.y;
    this.pos.addScaledVector(this.vel, dt);
    // never sink through the ground (belly)
    const gc = col.support(this.pos.x, this.pos.z, this.pos.y + 1.2);
    if (this.pos.y < gc - .25) { this.pos.y = gc - .25; if (this.vel.y < 0) this.vel.y = 0; }
    if (this.pos.y < -80) { this.pos.y = col.ground(this.pos.x, this.pos.z) + 1; this.vel.set(0, 0, 0); }
    this.vF = vF; this.speed = Math.abs(vF); this.contacts = contacts;
    // landing thump
    if (contacts && this.airT > .35) { const f = Math.min(1, -vy0 / 10); if (f > .25) { this.g.audio.land(); if (this === this.g.vehicles.current) this.g.player.shake = Math.min(1, f * .7); if (-vy0 > 13) this.damage((-vy0 - 13) * 18); } }
    this.airT = contacts ? 0 : this.airT + dt;
    // stuck on its roof/side: right itself after a moment
    if (Math.abs(this.roll) > 1.0 || Math.abs(this.pitch) > 1.0) { this.upsideT += dt; if (this.upsideT > 2.5) { this.roll = 0; this.pitch = 0; this.rollRate = this.pitchRate = 0; this.pos.y += .8; this.upsideT = 0; } }
    else this.upsideT = 0;
    // fall asleep when at rest on the ground (parked, abandoned)
    if (!ctl.driver && contacts === 4 && this.vel.lengthSq() < .01 && Math.abs(this.pitchRate) + Math.abs(this.rollRate) < .02) { this.restT = (this.restT || 0) + dt; if (this.restT > 1.5) this.sleep = true; }
    else this.restT = 0;
  }

  // push out of static boxes (walls, buildings, trees). Returns the impact speed.
  collideWorld() {
    const col = this.g.world.collision;
    let impact = 0;
    const s = Math.sin(this.yaw), c = Math.cos(this.yaw);
    const cx = this.pos.x + s * this.cz, czz = this.pos.z + c * this.cz;
    const bottom = this.pos.y + .35, top = this.pos.y + this.meta.roof;
    for (const b of col.near(cx, czz, this.hl + 1)) {
      if (b.max.y <= bottom || b.min.y >= top || b.car) continue;
      const hit = obbBox(cx, czz, s, c, this.hw, this.hl, b);
      if (!hit) continue;
      this.pos.x += hit.nx * hit.d; this.pos.z += hit.nz * hit.d;
      const vn = this.vel.x * hit.nx + this.vel.z * hit.nz;
      if (vn < 0) { this.vel.x -= vn * hit.nx * 1.2; this.vel.z -= vn * hit.nz * 1.2; impact = Math.max(impact, -vn); this.yawRate *= .5; }
    }
    return impact;
  }

  // ---------------------------------------------------------------- per-frame visuals
  visuals(dt, ctl = {}) {
    const g = this.g, cam = g.camera.position;
    const d2 = (cam.x - this.pos.x) ** 2 + (cam.z - this.pos.z) ** 2;
    const near = d2 < 48 * 48 || this === g.vehicles.current;
    if (near !== this.lodNear) { this.lodNear = near; this.hi.visible = near; this.lo.visible = !near; }
    this.node.visible = d2 < 420 * 420 || this === g.vehicles.current;
    this.syncRoot();
    if (!near) return;
    // wheels: spin, steer, suspension travel
    const ang = this.steer * this.S.steer * (1 - Math.min(.65, this.speed / 55));
    for (const w of this.wheels) {
      if (!w.piv) continue;
      w.rot += (this.vF / this.meta.rw) * dt;
      w.spin.rotation.x = w.rot;
      w.piv.position.y = this.meta.rw + THREE.MathUtils.clamp(w.off, -(this.S.droop || DROOP), this.S.bump || BUMP);
      if (w.front) w.piv.rotation.y = ang;
    }
    if (this.steerWheel) this.steerWheel.quaternion.copy(this.steerWheel.userData.q0).multiply(_q.setFromAxisAngle(_v.set(0, 0, 1), -this.steer * 2.4));
    // gauges: speed 0-240 km/h, revs from a simple 6-speed box; 240 degree sweep
    const kmh = this.speed * 3.6;
    const gears = [0, 4, 9, 14, 21, 30, 42, 99], v = this.speed;
    let gi = 1; while (gi < 6 && v > gears[gi + 1] * 1.05) gi++;
    const rpm = this.driverAlive() || this === g.vehicles.current ? 900 + Math.min(1, Math.max(0, (v - gears[gi - 1] * .7) / (gears[gi + 1] - gears[gi - 1] * .7))) * 5200 + (ctl.thr > 0 ? 400 : 0) : 0;
    this.rpm = (this.rpm || 0) + (rpm - (this.rpm || 0)) * Math.min(1, dt * 6);
    const na = f => -2.094 + 4.189 * Math.min(1, Math.max(0, f));
    if (this.needleS) this.needleS.quaternion.copy(this.needleS.userData.q0).multiply(_q.setFromAxisAngle(_v.set(0, 0, 1), na(kmh / 240)));
    if (this.needleR) this.needleR.quaternion.copy(this.needleR.userData.q0).multiply(_q.setFromAxisAngle(_v.set(0, 0, 1), na(this.rpm / 8000)));
    if (this.tail && !this.burnt) this.tail.emissiveIntensity = ctl.brake || (ctl.thr < 0 && this.vF > .5) ? 3.2 : 1.0;
  }

  driverAlive() { return this.driver ? this.driver.alive : false; }

  // ---------------------------------------------------------------- combat target
  center(out) { return out.copy(this.pos).setY(this.pos.y + .8); }

  // ray vs the lower body box and the cabin box (car space). A ray through the glass that would hit the driver
  // returns nothing, so the driver target takes the bullet.
  hitTest(o, d, max) {
    if (this.burnt && !this.alive) return null;
    const dx = o.x - this.pos.x, dz = o.z - this.pos.z;
    if (dx * dx + dz * dz > (max + 4) * (max + 4)) return null;
    _inv.copy(this.root.matrixWorld).invert();
    _o.copy(o).applyMatrix4(_inv); _d.copy(d).transformDirection(_inv);
    const m = this.meta;
    const t1 = rayBox(_o, _d, -this.hw, m.clear + .05, -this.hlB + .05, this.hw, m.belt, this.hlF - .05);
    const t2 = rayBox(_o, _d, -this.hw + .12, m.belt - .01, m.cab[0], this.hw - .12, m.roof - .03, m.cab[1]);
    let t = -1, glass = false;
    if (t1 >= 0 && (t2 < 0 || t1 <= t2)) t = t1;
    else if (t2 >= 0) { t = t2; glass = true; }
    if (t < 0 || t > max) return null;
    if (glass && this.driver && this.driver.alive && this.driver.inCar && this.driver.hitTest(o, d, max)) return null;
    return { dist: t, crit: false };
  }

  takeDamage(dmg, crit, point, dir, side) {
    if (!this.alive) return { killed: false };
    const g = this.g;
    this.wake();
    if (point) {
      const hit = this.surfaceHit(point, dir);
      if (hit) this.decal(hit);
      g.fx.emit(point, 7, 5, 0xffd27a, .22, 9, .03);
      if (hit && hit.glass) g.fx.emit(point, 12, 3, 0xd8f0ff, .6, 9, .025);
      if (dir && this.dynamic) { this.vel.addScaledVector(dir, Math.min(.6, dmg / this.mass * 4)); }
    }
    if (this.traffic) this.traffic.onShot(this, side);
    return { killed: this.damage(dmg * .55) };
  }

  // exact surface point under a hit (mesh raycast against the detailed body) for decals
  surfaceHit(point, dir) {
    if (!dir) return null;
    this.root.updateMatrixWorld(true);
    _ray.set(_o.copy(point).addScaledVector(dir, -1.6), dir); _ray.far = 3.2;
    const hits = _ray.intersectObject(this.hi, true);
    const h = hits.find(x => x.object.isMesh && x.face && !/needle|steer/.test(x.object.parent ? x.object.parent.name : ''));
    if (!h) return null;
    const nrm = h.face.normal.clone().transformDirection(h.object.matrixWorld);
    if (nrm.dot(dir) > 0) nrm.negate();
    return { point: h.point.clone(), normal: nrm, glass: /glass/.test(h.object.material.name) };
  }

  decal(hit) {
    const D = decals(this.g);
    const m = new THREE.Mesh(D.geo, hit.glass ? D.crack : D.hole);
    const s = hit.glass ? .32 + Math.random() * .2 : .05 + Math.random() * .025;
    m.scale.set(s, s, 1);
    this.root.updateMatrixWorld(true);
    _inv.copy(this.root.matrixWorld).invert();
    m.position.copy(hit.point).addScaledVector(hit.normal, hit.glass ? .004 : .003).applyMatrix4(_inv);
    _v.copy(hit.normal).transformDirection(_inv);
    m.quaternion.setFromUnitVectors(_w.set(0, 0, 1), _v);
    m.rotateZ(Math.random() * 6.28);
    m.castShadow = false;
    this.root.add(m); this.holes.push(m);
    if (this.holes.length > 40) this.holes.shift().removeFromParent();
  }

  // returns true when this hit destroyed the car
  damage(n) {
    if (!this.alive) return false;
    this.hp -= n;
    if (this.hp > 0) return false;
    this.alive = false;
    const g = this.g, p = this.pos.clone(); p.y += 1;
    g.fx.explosion(p, 6); g.audio.explosion(p);
    g.combat && g.combat.targets.delete(this);
    if (this.driver && this.driver.alive) this.driver.kill(false, new THREE.Vector3(0, 1, 0));
    if (g.vehicles.current === this) { g.vehicles.exit(true); g.player.damage(40, p); }
    this.burn();
    this.vel.y += 4; this.pitchRate += (Math.random() - .5) * 2; this.rollRate += (Math.random() - .5) * 3; this.wake();
    if (this.traffic) this.traffic.onWrecked(this);
    return true;
  }

  // burnt-out wreck: dark paint, no glass, smoulders
  burn() {
    this.burnt = true;
    const m = this.paintMat; if (m) { m.color.set('#1a1715'); m.roughness = 1; m.metalness = .2; if ('clearcoat' in m) m.clearcoat = 0; }
    this.node.traverse(o => { if (o.isMesh && /glass/.test(o.material.name)) o.visible = false; });
    if (this.tail) this.tail.emissiveIntensity = 0;
  }

  effects(dt) {
    const g = this.g;
    const frac = this.hp / this.S.hp;
    if (frac < .45 || this.burnt) {
      this.smokeT -= dt;
      if (this.smokeT <= 0) {
        const cam = g.camera.position;
        if ((cam.x - this.pos.x) ** 2 + (cam.z - this.pos.z) ** 2 < 160 * 160) {
          this.smokeT = this.burnt ? .18 : .12 + frac * .3;
          _v.set(0, this.meta.hood[1] + .1, this.meta.hood[2]).applyMatrix4(this.root.matrixWorld);
          const dark = frac < .2 || this.burnt;
          g.fx.emit(_v, 2, .8, dark ? 0x2a2826 : 0x8a8a88, 1.8, -2.2, .35, .6, null, .9);
          if (frac < .18 && !this.burnt) g.fx.emit(_v, 2, 1.2, 0xff8a30, .45, -3, .18, .5);
        } else this.smokeT = .5;
      }
      if (frac < .2 && !this.burnt && this.alive) this.damage(6 * dt);     // it burns down
    }
    // a dead driver slumped on the horn
    if (this.hornT > 0) {
      this.hornT -= dt; this.hornBeat = (this.hornBeat || 0) - dt;
      const a = g.audio;
      if (this.hornBeat <= 0 && a.ready && a.ctx) {
        this.hornBeat = .5;
        const o = a.out(this.pos, 90), t = a.ctx.currentTime;
        a.tone(o, t, .56, 392, 392, 'sawtooth', .07, .02); a.tone(o, t, .56, 466, 466, 'square', .04, .02);
      }
    }
  }

  dispose() {
    this.root.removeFromParent();
    this.g.combat && this.g.combat.targets.delete(this);
    if (this.driver) this.driver.dispose();
  }
}

// ================================================================ hover board
export class Board {
  constructor(game, model, paint, pos, yaw) {
    const g = this.g = game;
    this.model = model = boardModel(model); this.board = true;
    this.S = { ...SPECS[model], max: SPECS[model].top };
    this.root = new THREE.Group();
    const m = g.assets.clone(model);
    this.root.add(m);
    this.glow = [];
    m.traverse(o => {
      if (!o.isMesh) return;
      o.material = o.material.clone();
      if (o.material.name === 'car_paint') { o.material.color.set(paint); o.material.envMapIntensity = 1.5; }
      if (o.material.name === 'hover_glow') this.glow.push(o.material);
    });
    let meta = {}; try { meta = JSON.parse(m.userData.worldex || '{}'); } catch (e) { /* ignore */ }
    this.deck = meta.deck || .05; this.len = meta.len || 1.3;
    this.pos = pos.clone(); this.vel = new THREE.Vector3(); this.yaw = yaw; this.yawRate = 0; this.pitch = 0; this.roll = 0; this.steer = 0;
    this.speed = 0; this.vF = 0; this.hp = this.S.hp; this.alive = true; this.dynamic = true; this.sleep = false; this.hover = .42;
    this.bob = Math.random() * 6; this.wakeT = 0; this.air = 0; this.side = 'player';
    this.hw = .3; this.hl = this.len / 2; this.cz = 0; this.meta = { roof: .3, belt: .2, clear: 0 };
    const gy = this.surface(pos.x, pos.z, pos.y + 1);
    this.pos.y = Math.max(pos.y, gy + this.hover);
    this.root.position.copy(this.pos);
    g.scene.add(this.root);
  }

  // ground or water surface the board rides on
  wake() { /* boards never sleep */ }

  surface(x, z, yRef) {
    const g = this.g, col = g.world.collision;
    let h = col.support(x, z, yRef);
    const wy = waterY(g, x, z);
    if (wy !== null && wy > h) h = wy;
    if (g.world.lava !== undefined && g.world.lava > h) h = g.world.lava;
    return h;
  }

  damage(n) {
    if (!this.alive) return false;
    this.hp -= n;
    if (this.hp <= 0) {
      this.alive = false;
      const p = this.root.position.clone(); p.y += .5;
      this.g.fx.explosion(p, 3); this.g.audio.explosion(p);
      if (this.g.vehicles.current === this) { this.g.vehicles.exit(true); this.g.player.damage(25, p); }
      this.root.visible = false;
      return true;
    }
    return false;
  }

  update(dt, riding, input) {
    const g = this.g, S = this.S, col = g.world.collision;
    let thr = 0, st = 0, boost = false, jump = false;
    if (riding && input.enabled) {
      thr = (input.key('KeyW') ? 1 : 0) - (input.key('KeyS') ? 1 : 0);
      st = (input.key('KeyA') ? 1 : 0) - (input.key('KeyD') ? 1 : 0);
      boost = input.key('ShiftLeft') || input.key('ShiftRight'); jump = input.pressed('Space');
      if (input.axisX || input.axisY) { thr = Math.abs(input.axisY) > .2 ? Math.sign(input.axisY) : 0; st = -input.axisX; }
    }
    this.ctl = { thr, st, brake: thr < 0, boost };
    // hover: probe front, centre and back
    const s = Math.sin(this.yaw), c = Math.cos(this.yaw), L = this.len * .42;
    const yRef = this.pos.y + .6;
    const hf = this.surface(this.pos.x + s * L, this.pos.z + c * L, yRef), hb = this.surface(this.pos.x - s * L, this.pos.z - c * L, yRef);
    const hc = this.surface(this.pos.x, this.pos.z, yRef);
    const gnd = Math.max(hc, (hf + hb) / 2);
    const h = this.pos.y - gnd;
    const near = h < 1.6;
    if (near) {
      this.vel.y += (110 * (this.hover - h) - 9 * this.vel.y) * dt * (h < this.hover + .6 ? 1 : .35);
      if (this.air > .5 && this.vel.y < -6) { g.audio.land(); if (riding) g.player.shake = Math.min(1, -this.vel.y / 18); }
      this.air = 0;
    } else this.air += dt;
    this.vel.y -= 14 * dt;
    if (jump && h < this.hover + .5) { this.vel.y = 7.2; g.audio.jump(); g.fx.emit(this.pos, 16, 4, 0x3ad6ff, .4, 2, .08); }
    if (this.pos.y < gnd + .12) { this.pos.y = gnd + .12; if (this.vel.y < 0) this.vel.y = 0; }
    // carve: speed along heading, grip sideways, lean into turns
    _f.set(s, 0, c); _r.set(c, 0, -s);
    let vF = this.vel.x * _f.x + this.vel.z * _f.z, vL = this.vel.x * _r.x + this.vel.z * _r.z;
    const top = boost ? S.boost : S.top;
    if (thr > 0) vF += (vF < top ? S.accel * (boost ? 1.4 : 1) : -S.accel * .4) * dt;
    else if (thr < 0) vF -= (vF > 0 ? S.accel * 1.6 : S.accel * .5) * dt;
    else vF *= 1 - (near ? .35 : .05) * dt;
    vF = Math.max(-7, vF);
    vF += -G * Math.sin(Math.atan2(hf - hb, 2 * L)) * dt * (near ? .7 : 0);       // downhill speeds up
    this.steer += (st - this.steer) * Math.min(1, dt * 7);
    const turn = S.turn * this.steer * Math.min(1, (Math.abs(vF) + 1.5) / 6) * (1 - Math.min(.5, Math.abs(vF) / 70));
    this.yawRate += (turn * (near ? 1 : .4) - this.yawRate) * Math.min(1, dt * 8);
    this.yaw += this.yawRate * dt;
    vL *= Math.max(0, 1 - (near ? 6 : .5) * dt);
    _f.set(Math.sin(this.yaw), 0, Math.cos(this.yaw)); _r.set(Math.cos(this.yaw), 0, -Math.sin(this.yaw));
    this.vel.x = _f.x * vF + _r.x * vL; this.vel.z = _f.z * vF + _r.z * vL;
    this.pos.addScaledVector(this.vel, dt);
    // walls: circle push-out, crash damage
    let impact = 0;
    const r = .45;
    for (const b of col.near(this.pos.x, this.pos.z, 1.5)) {
      if (b.max.y <= this.pos.y + .25 || b.min.y >= this.pos.y + 1.6 || b.car) continue;
      const cx = Math.max(b.min.x, Math.min(this.pos.x, b.max.x)), cz = Math.max(b.min.z, Math.min(this.pos.z, b.max.z));
      let dx = this.pos.x - cx, dz = this.pos.z - cz; const d2 = dx * dx + dz * dz;
      if (d2 >= r * r) continue;
      const dd = Math.sqrt(d2) || 1e-3; dx /= dd; dz /= dd;
      this.pos.x += dx * (r - dd); this.pos.z += dz * (r - dd);
      const vn = this.vel.x * dx + this.vel.z * dz;
      if (vn < 0) { this.vel.x -= vn * dx * 1.3; this.vel.z -= vn * dz * 1.3; impact = Math.max(impact, -vn); }
    }
    if (impact > 9 && riding) { this.damage(impact * 2); g.player.shake = Math.min(1, impact / 20); g.audio.land(); g.world.onCrash && g.world.onCrash(this.pos.clone()); }
    this.vF = vF; this.speed = Math.abs(vF);
    // visuals
    this.pitch += (-Math.atan2(hf - hb, 2 * L) * (near ? 1 : .3) - this.vel.y * .01 - this.pitch) * Math.min(1, dt * 6);
    this.roll += (-this.yawRate * Math.min(1, Math.abs(vF) / 12) * .35 - this.roll) * Math.min(1, dt * 6);
    this.bob += dt * 3;
    this.root.position.set(this.pos.x, this.pos.y + Math.sin(this.bob) * (near ? .025 : 0), this.pos.z);
    this.root.rotation.set(this.pitch, this.yaw, this.roll, 'YXZ');
    const glow = 1.4 + this.speed * .05 + (boost && thr > 0 ? 1.4 : 0) + Math.sin(this.bob * 5) * .12;
    for (const m of this.glow) m.emissiveIntensity = glow;
    if (riding && boost && thr > 0) { _v.set(0, .05, -this.len / 2).applyMatrix4(this.root.matrixWorld); g.fx.emit(_v, 2, 1.2, 0x3ad6ff, .25, 0, .06); }
    // wake over water
    const wy = waterY(g, this.pos.x, this.pos.z);
    if (wy !== null && wy >= hc - .01 && this.pos.y - wy < 1.2 && this.speed > 2) {
      this.wakeT -= dt;
      if (this.wakeT <= 0) { this.wakeT = .15; g.water.splash && g.water.splash(new THREE.Vector3(this.pos.x, wy, this.pos.z), .4); }
    }
    if (riding) g.save.stats.carDistance += this.speed * dt;
  }

  dispose() { this.root.removeFromParent(); }
}

// ---------------------------------------------------------------- geometry helpers
// slab test, box in local space; returns entry distance or -1
function rayBox(o, d, x0, y0, z0, x1, y1, z1) {
  let tmin = 0, tmax = Infinity;
  for (const [oo, dd, a, b] of [[o.x, d.x, x0, x1], [o.y, d.y, y0, y1], [o.z, d.z, z0, z1]]) {
    if (Math.abs(dd) < 1e-9) { if (oo < a || oo > b) return -1; continue; }
    let t1 = (a - oo) / dd, t2 = (b - oo) / dd; if (t1 > t2) { const t = t1; t1 = t2; t2 = t; }
    tmin = Math.max(tmin, t1); tmax = Math.min(tmax, t2); if (tmin > tmax) return -1;
  }
  return tmin;
}

// 2D SAT: car box (centre cx,cz; forward (s,c); half width hw, half length hl) vs an AABB. Returns push for the car.
function obbBox(cx, cz, s, c, hw, hl, b) {
  const bx = (b.min.x + b.max.x) / 2, bz = (b.min.z + b.max.z) / 2, ex = (b.max.x - b.min.x) / 2, ez = (b.max.z - b.min.z) / 2;
  const dx = bx - cx, dz = bz - cz;
  let best = Infinity, nx = 0, nz = 0;
  for (const [ax, az] of [[1, 0], [0, 1], [s, c], [c, -s]]) {
    const rc = hw * Math.abs(c * ax - s * az) + hl * Math.abs(s * ax + c * az);
    const rb = ex * Math.abs(ax) + ez * Math.abs(az);
    const dist = dx * ax + dz * az;
    const o = rc + rb - Math.abs(dist);
    if (o <= 0) return null;
    if (o < best) { best = o; const sg = dist > 0 ? -1 : 1; nx = ax * sg; nz = az * sg; }
  }
  return { nx, nz, d: best };
}

// 2D SAT between two cars; normal points from b to a
function obbObb(a, b) {
  const sa = Math.sin(a.yaw), ca = Math.cos(a.yaw), sb = Math.sin(b.yaw), cb = Math.cos(b.yaw);
  const ax0 = a.pos.x + sa * a.cz, az0 = a.pos.z + ca * a.cz, bx0 = b.pos.x + sb * b.cz, bz0 = b.pos.z + cb * b.cz;
  const dx = bx0 - ax0, dz = bz0 - az0;
  let best = Infinity, nx = 0, nz = 0;
  for (const [x, z] of [[sa, ca], [ca, -sa], [sb, cb], [cb, -sb]]) {
    const ra = a.hw * Math.abs(ca * x - sa * z) + a.hl * Math.abs(sa * x + ca * z);
    const rb = b.hw * Math.abs(cb * x - sb * z) + b.hl * Math.abs(sb * x + cb * z);
    const dist = dx * x + dz * z, o = ra + rb - Math.abs(dist);
    if (o <= 0) return null;
    if (o < best) { best = o; const sg = dist > 0 ? -1 : 1; nx = x * sg; nz = z * sg; }
  }
  return { nx, nz, d: best };
}

// circle (x,z,r) vs car footprint: returns {nx, nz, d, local} pushing the circle out, or null
function circleCar(car, x, z, r) {
  const s = Math.sin(car.yaw), c = Math.cos(car.yaw);
  const rx = x - car.pos.x, rz = z - car.pos.z;
  const lx = rx * c - rz * s, lz = rx * s + rz * c - car.cz;      // car local: x = left, z = forward
  const qx = Math.max(-car.hw, Math.min(car.hw, lx)), qz = Math.max(-car.hl, Math.min(car.hl, lz));
  let dx = lx - qx, dz = lz - qz; const d2 = dx * dx + dz * dz;
  let nlx, nlz, d;
  if (d2 > 1e-8) { if (d2 >= r * r) return null; const dd = Math.sqrt(d2); nlx = dx / dd; nlz = dz / dd; d = r - dd; }
  else {
    const px = car.hw - Math.abs(lx), pz = car.hl - Math.abs(lz);
    if (px < pz) { nlx = Math.sign(lx) || 1; nlz = 0; d = px + r; } else { nlx = 0; nlz = Math.sign(lz) || 1; d = pz + r; }
  }
  return { nx: nlx * c + nlz * s, nz: -nlx * s + nlz * c, d, lz: lz + car.cz };
}

// ================================================================ manager
export class Vehicles {
  constructor(game) { this.g = game; this.cars = []; this.current = null; this.mine = null; this.grid = new Map(); this.frame = 0; }

  clear() { this.cars.forEach(c => c.dispose()); this.cars = []; this.current = null; this.mine = null; this.rover = null; this.grid.clear(); }

  // parked / scripted cars: legacy model names map onto the modern line-up
  spawn(model, paint, pos, yaw) {
    const m = roadModel(model, hashXZ(pos));
    const c = new Car(this.g, m, model in LEGACY ? null : paint, pos, yaw);
    c.parked = true;
    this.cars.push(c); return c;
  }

  // V: the hover board drops in under the player, who steps straight on. On frontier worlds, V again while on the
  // board calls down the all-terrain rover instead.
  summon() {
    const g = this.g, p = g.player;
    if (g.world.allowCars && !p.dead && this.current && this.current.board && g.world.kind !== 'city') { this.dropRover(); return; }
    if (!g.world.allowCars || p.mode !== 'foot' || p.dead) { g.audio.ui('deny'); return; }
    if (g.world.kind !== 'city' && !this.roverHint) { this.roverHint = true; setTimeout(() => g.hud.toast('Press V again to call down the rover'), 1200); }
    const model = boardModel(g.save.car.model);
    if (this.mine && (!this.mine.alive || this.mine.model !== model)) { this.mine.dispose(); this.cars.splice(this.cars.indexOf(this.mine), 1); this.mine = null; }
    if (!this.mine) { this.mine = new Board(g, model, g.save.car.paint, p.pos.clone(), p.yaw); this.cars.push(this.mine); }
    const b = this.mine;
    b.pos.copy(p.pos); b.pos.y = b.surface(p.pos.x, p.pos.z, p.pos.y + .5) + b.hover; b.vel.set(0, 0, 0); b.yaw = p.yaw; b.root.visible = true;
    g.fx.emit(_v.copy(b.pos).setY(b.pos.y + .2), 30, 4, 0x3ad6ff, .5, 2, .08);
    g.audio.ui('open');
    this.enter(b);
  }

  // the ship drops the rover beside the board; it lands on its suspension and the player climbs in
  dropRover() {
    const g = this.g, b = this.current;
    const yaw = b.yaw, side = new THREE.Vector3(Math.cos(yaw), 0, -Math.sin(yaw));
    this.exit();
    const pos = b.pos.clone().addScaledVector(side, -3.2).addScaledVector(new THREE.Vector3(Math.sin(yaw), 0, Math.cos(yaw)), 2);
    if (this.rover && this.rover.alive) { this.rover.pos.copy(pos); this.rover.vel.set(0, 0, 0); this.rover.yaw = yaw; }
    else {
      if (this.rover) { this.rover.dispose(); this.cars.splice(this.cars.indexOf(this.rover), 1); }
      this.rover = new Car(g, 'car_rover', '#e9e6df', pos, yaw); this.cars.push(this.rover);
    }
    const r = this.rover;
    r.pos.y = g.world.collision.support(pos.x, pos.z, pos.y + 2) + 3.5; r.pitch = r.roll = 0; r.vel.y = -2;
    r.wake();
    b.vel.set(0, 0, 0);
    g.fx.emit(_v.copy(r.pos), 40, 6, 0xd9661f, .6, 4, .1);
    g.audio.ui('open');
    this.enter(r);
  }

  nearest(p, r = 2.2) {
    let best = null, bd = r;
    for (const c of this.cars) {
      if (!c.alive) continue;
      if (Math.abs(c.pos.x - p.x) > 8 || Math.abs(c.pos.z - p.z) > 8) continue;
      let d;
      if (c.board) d = Math.hypot(c.pos.x - p.x, c.pos.z - p.z) - .6;
      else { const h = circleCar(c, p.x, p.z, 3); d = h ? 3 - h.d : 9; if (h && h.d > 3) d = 0; }
      if (d < bd) { bd = d; best = c; }
    }
    return best;
  }

  enter(c) {
    const g = this.g, p = g.player;
    if (c.traffic && g.world.traffic) g.world.traffic.hijack(c);   // the driver bails out (or a body is pulled out)
    else if (c.driver && !c.driver.alive) c.driver.eject();
    this.current = c; p.mode = 'car'; c.wake(); c.parked = false;
    p.avatar.attachGun(null);
    p.avatar.play(c.board ? 'IdleRelaxed' : 'Sit', .2);
    g.audio.carLoop(); if (!c.board) g.audio.door();
    p.camYaw = c.yaw + Math.PI; p.camPitch = -.12; p.snapCamera = true;
    g.hud.dirty = true;
  }

  exit(forced = false) {
    const g = this.g, p = g.player, c = this.current; if (!c) return;
    this.current = null; p.mode = 'foot';
    const side = new THREE.Vector3(Math.cos(c.yaw), 0, -Math.sin(c.yaw));
    const off = c.board ? .9 : c.hw + .75;
    let out = c.pos.clone().addScaledVector(side, off);
    const blocked = q => [...g.world.collision.near(q.x, q.z, 1)].some(b => !b.car && q.x > b.min.x - .4 && q.x < b.max.x + .4 && q.z > b.min.z - .4 && q.z < b.max.z + .4 && b.max.y > q.y + .5);
    if (blocked(out)) out = c.pos.clone().addScaledVector(side, -off);
    out.y = g.world.collision.support(out.x, out.z, c.pos.y + 1);
    p.pos.copy(out); p.vel.set(c.vel.x * .3, 0, c.vel.z * .3); p.yaw = c.yaw;
    p.avatar.root.position.copy(out); p.avatar.root.rotation.set(0, c.yaw, 0); p.avatar.root.quaternion.setFromEuler(p.avatar.root.rotation);
    resetCrouch(p.avatar);
    g.audio.updateCar(false, 0); if (!c.board) g.audio.door();
    g.weapons.refreshModel(); g.hud.dirty = true;
    p.snapCamera = true;
  }

  // controls for the player's car
  playerControl(input) {
    let thr = 0, st = 0, hand = false, boost = false;
    if (input.enabled) {
      thr = (input.key('KeyW') ? 1 : 0) - (input.key('KeyS') ? 1 : 0);
      st = (input.key('KeyA') ? 1 : 0) - (input.key('KeyD') ? 1 : 0);
      boost = input.key('ShiftLeft') || input.key('ShiftRight'); hand = input.key('Space');
      if (input.axisX || input.axisY) { thr = Math.abs(input.axisY) > .2 ? Math.sign(input.axisY) : 0; st = -input.axisX; }
    }
    return { thr, st, hand, boost, brake: false, driver: true };
  }

  update(dt, input) {
    const g = this.g, p = g.player;
    this.frame++;
    const cam = g.camera.position;
    for (const c of this.cars) {
      if (c.board) { if (c.alive) c.update(dt, c === this.current, input); continue; }
      if (!c.alive && !c.burnt) continue;
      const driving = c === this.current;
      if (c.dynamic && !c.sleep) {
        const ctl = driving ? this.playerControl(input) : (c.ctl || { driver: c.driverAlive() });
        c.lastCtl = ctl;
        // sub-step for stable springs at low frame rates
        const n = dt > 1 / 45 ? 2 : 1;
        for (let i = 0; i < n; i++) c.physics(dt / n, ctl);
        const impact = c.collideWorld();
        if (impact > 7) {
          c.damage((impact - 7) * (driving ? 22 : 12));
          g.audio.land();
          if (driving) { p.shake = Math.min(1, impact / 22); g.world.onCrash && g.world.onCrash(c.pos.clone()); }
        }
        if (driving) g.save.stats.carDistance += c.speed * dt;
      }
      c.visuals(dt, c.lastCtl || c.ctl || {});
      c.effects(dt);
    }
    this.collideCars();
    this.buildGrid();
    this.pushPlayer(dt);
    this.pushEnemies();
    // rider / driver placement
    if (this.current) {
      const c = this.current, av = p.avatar;
      c.root.updateMatrixWorld(true);
      if (c.board) {
        _v.set(0, c.deck, 0).applyMatrix4(c.root.matrixWorld);
        av.root.position.copy(_v);
        c.root.getWorldQuaternion(_q);
        av.root.quaternion.copy(_q).multiply(STANCE);            // sideways stance, leading foot forward
        crouch(av, .38 + Math.min(.25, c.speed / 60));
      } else {
        const hip = HIP[av.modelName] || .46;
        _v.copy(c.seatL); _v.y -= hip; _v.applyMatrix4(c.root.matrixWorld);
        av.root.position.copy(_v);
        c.root.getWorldQuaternion(av.root.quaternion);
      }
      p.pos.copy(c.pos); p.yaw = c.yaw; p.vel.copy(c.vel);
      g.audio.updateCar(true, c.speed * (c.board ? .7 : 1));
    }
  }

  // car vs car (all pairs that are close): separate, exchange momentum, wake kinematic traffic on a real hit
  collideCars() {
    const cars = this.cars;
    for (let i = 0; i < cars.length; i++) {
      const a = cars[i]; if (a.board || (!a.alive && !a.burnt)) continue;
      const aMoving = a.dynamic && !a.sleep;
      for (let j = i + 1; j < cars.length; j++) {
        const b = cars[j]; if (b.board || (!b.alive && !b.burnt)) continue;
        const bMoving = b.dynamic && !b.sleep;
        if (!a.dynamic && !b.dynamic) continue;                       // two lane-following cars: traffic.js keeps them apart
        if (!aMoving && !bMoving && !(a.speed > 1 || b.speed > 1)) continue;
        const dx = a.pos.x - b.pos.x, dz = a.pos.z - b.pos.z;
        if (dx * dx + dz * dz > 49 || Math.abs(a.pos.y - b.pos.y) > 2) continue;
        const h = obbObb(a, b); if (!h) continue;
        // relative velocity along the normal (n points from b to a)
        const va = a.dynamic ? a.vel : a.kvel || a.vel, vb = b.dynamic ? b.vel : b.kvel || b.vel;
        const rel = (va.x - vb.x) * h.nx + (va.z - vb.z) * h.nz;
        if (rel < -2.5) { if (a.traffic && !a.dynamic) a.traffic.knock(a); if (b.traffic && !b.dynamic) b.traffic.knock(b); }
        const ma = a.dynamic ? a.mass : 1e9, mb = b.dynamic ? b.mass : 1e9;
        const wa = mb / (ma + mb), wb = ma / (ma + mb);
        if (a.dynamic) { a.pos.x += h.nx * h.d * wa; a.pos.z += h.nz * h.d * wa; a.wake(); }
        if (b.dynamic) { b.pos.x -= h.nx * h.d * wb; b.pos.z -= h.nz * h.d * wb; b.wake(); }
        if (rel < 0) {
          const jn = -(1.25) * rel / (1 / ma + 1 / mb);
          if (a.dynamic) { a.vel.x += h.nx * jn / ma; a.vel.z += h.nz * jn / ma; a.yawRate += (Math.random() - .5) * Math.min(2, -rel * .08); }
          if (b.dynamic) { b.vel.x -= h.nx * jn / mb; b.vel.z -= h.nz * jn / mb; b.yawRate += (Math.random() - .5) * Math.min(2, -rel * .08); }
          if (-rel > 6) {
            const dmg = (-rel - 6) * 14;
            a.damage(dmg * wa * 2); b.damage(dmg * wb * 2);
            const cp = a.pos.clone().lerp(b.pos, .5).setY(a.pos.y + .7);
            this.g.fx.emit(cp, 14, 6, 0xffd27a, .3, 9, .04); this.g.audio.land();
            if (a === this.current || b === this.current) { this.g.player.shake = Math.min(1, -rel / 20); this.g.world.onCrash && this.g.world.onCrash(cp); }
          }
        }
      }
    }
  }

  // spatial hash of cars (16 m cells) for the many people checks
  buildGrid() {
    this.grid.clear();
    for (const c of this.cars) {
      if (c.board || (!c.alive && !c.burnt)) continue;
      const k = (Math.floor(c.pos.x / 16) * 7919) ^ Math.floor(c.pos.z / 16);
      let l = this.grid.get(k); if (!l) this.grid.set(k, l = []); l.push(c);
    }
  }

  carsNear(x, z, out = []) {
    out.length = 0;
    const ix = Math.floor(x / 16), iz = Math.floor(z / 16);
    for (let a = ix - 1; a <= ix + 1; a++) for (let b = iz - 1; b <= iz + 1; b++) { const l = this.grid.get((a * 7919) ^ b); if (l) for (const c of l) out.push(c); }
    return out;
  }

  // velocity of a car's body at rest or moving (kinematic traffic keeps kvel)
  carVel(c) { return c.dynamic ? c.vel : (c.kvel || c.vel); }

  // the player on foot always collides with every car: pushed out, knocked down by fast cars, can stand on roofs
  pushPlayer(dt) {
    const g = this.g, p = g.player;
    if (p.mode !== 'foot' || p.dead) return;
    for (const c of this.carsNear(p.pos.x, p.pos.z, this._near || (this._near = []))) {
      const base = c.pos.y, top = base + (c.meta.roof || 1.4);
      if (p.pos.y > top - .05 || p.pos.y + 1.8 < base + .2) continue;
      const h = circleCar(c, p.pos.x, p.pos.z, .38); if (!h) continue;
      const inCab = h.lz > c.meta.cab[0] && h.lz < c.meta.cab[1];
      const surf = base + (inCab ? c.meta.roof : c.meta.belt) - .02;
      // standing on the bonnet / roof (came from above)
      if (p.pos.y > surf - .45 && p.vel.y <= 0 && h.d > .3) { p.pos.y = surf; p.vel.y = 0; p.grounded = true; p.airTime = 0; continue; }
      const v = this.carVel(c), vn = v.x * h.nx + v.z * h.nz;          // car speed toward the player (n points car -> player)
      p.pos.x += h.nx * h.d; p.pos.z += h.nz * h.d;
      const pv = p.vel.x * h.nx + p.vel.z * h.nz; if (pv < 0) { p.vel.x -= pv * h.nx; p.vel.z -= pv * h.nz; }
      if (vn > 6 && !(p.hitCd > 0)) {
        p.hitCd = 1;
        p.damage(Math.min(90, (vn - 4) * 6), c.pos.clone().setY(c.pos.y + 1));
        p.vel.x += h.nx * vn * .7; p.vel.z += h.nz * vn * .7; p.vel.y = 3 + vn * .15;
        if (c.traffic) c.traffic.hitSomeone(c);
      } else if (vn > 1.5) { p.vel.x += h.nx * vn; p.vel.z += h.nz * vn; }
    }
    p.hitCd = (p.hitCd || 0) - dt;
  }

  pushEnemies() {
    const g = this.g; if (!g.enemies) return;
    for (const e of g.enemies.list) {
      if (!e.alive || !e.pos) continue;
      for (const c of this.carsNear(e.pos.x, e.pos.z, this._near2 || (this._near2 = []))) {
        if (e.pos.y > c.pos.y + c.meta.roof || e.pos.y + 1.8 < c.pos.y) continue;
        const h = circleCar(c, e.pos.x, e.pos.z, .5); if (!h) continue;
        e.pos.x += h.nx * h.d; e.pos.z += h.nz * h.d;
        const v = this.carVel(c), vn = v.x * h.nx + v.z * h.nz;
        if (vn > 7 && e.takeDamage && !(e.carCd > g.time)) { e.carCd = g.time + 1; e.takeDamage(vn * 12, false, e.pos.clone().setY(e.pos.y + 1), new THREE.Vector3(-h.nx, .3, -h.nz), c === this.current ? 'player' : 'traffic'); }
      }
    }
  }

  // Pedestrian contact (population.js): pushes the person out of the car. Returns {car, speed} when the car hit
  // them hard enough to run them over.
  pedContact(q, r = .32) {
    for (const c of this.carsNear(q.pos.x, q.pos.z, this._near3 || (this._near3 = []))) {
      if (q.pos.y > c.pos.y + c.meta.roof || q.pos.y + 1.7 < c.pos.y + .1) continue;
      const h = circleCar(c, q.pos.x, q.pos.z, r); if (!h) continue;
      const v = this.carVel(c), vn = v.x * h.nx + v.z * h.nz, sp = Math.hypot(v.x, v.z);
      if (vn > 6 || (sp > 6 && h.d > r * .5)) return { car: c, speed: Math.max(vn, sp) };
      q.pos.x += h.nx * h.d; q.pos.z += h.nz * h.d;
      if (vn > 1.5 && q.flee) q.flee(c.pos);
    }
    return null;
  }

  // First-person seat camera (and the board's head camera). Returns true when it placed the camera.
  camera(cam, dt) {
    const g = this.g, p = g.player, c = this.current;
    if (!c || !g.carFirstPerson()) return false;
    c.root.updateMatrixWorld(true);
    if (c.board) {
      const eye = (p.avatar.modelName === 'player_male' ? 1.66 : 1.52) - .1;
      cam.position.set(c.pos.x, c.root.position.y + c.deck + eye, c.pos.z);
      cam.rotation.order = 'YXZ';
      cam.rotation.set(p.camPitch, p.camYaw, 0);
    } else {
      _v.copy(c.eyeL); if (p.avatar.modelName !== 'player_male') _v.y -= .07;
      _v.applyMatrix4(c.root.matrixWorld);
      cam.position.copy(_v);
      // look relative to the car: yaw/pitch offsets from straight ahead, clamped to what a head can turn
      let rel = wrap(p.camYaw - (c.yaw + Math.PI));
      rel = THREE.MathUtils.clamp(rel, -2.5, 2.5); p.camYaw = c.yaw + Math.PI + rel;
      p.camPitch = THREE.MathUtils.clamp(p.camPitch, -.9, .7);
      c.root.getWorldQuaternion(_q);
      cam.quaternion.copy(_q).multiply(new THREE.Quaternion().setFromEuler(_e.set(p.camPitch, Math.PI + rel, 0, 'YXZ')));
    }
    p.shake = Math.max(0, p.shake - dt * 2.5);
    if (p.shake > 0) { const sk = p.shake * p.shake * .04; cam.rotateX((Math.random() - .5) * sk); cam.rotateY((Math.random() - .5) * sk); }
    const fov = g.save.settings.fov + (c.board ? Math.min(14, c.speed * .4) : Math.min(8, c.speed * .12));
    if (Math.abs(cam.fov - fov) > .05) { cam.fov += (fov - cam.fov) * Math.min(1, dt * 6); cam.updateProjectionMatrix(); }
    p.camCur = 0;
    g.audio.listener(cam.position, p.camYaw);
    return true;
  }
}

// slight crouch on the board: knees bend, hips drop (applied after the mixer each frame)
const _qa = new THREE.Quaternion(), _qb = new THREE.Quaternion(), _ax = new THREE.Vector3();
function bend(bone, axisWorld, ang) {
  if (!bone || !bone.parent) return;
  bone.parent.getWorldQuaternion(_qa);
  _ax.copy(axisWorld).applyQuaternion(_qa.invert()).normalize();
  bone.quaternion.premultiply(_qb.setFromAxisAngle(_ax, ang));
  bone.updateMatrixWorld(true);
}
function crouch(av, a) {
  const B = av.bones;
  av.root.updateMatrixWorld(true);
  av.root.getWorldQuaternion(_q);
  const right = new THREE.Vector3(1, 0, 0).applyQuaternion(_q);
  for (const s of ['L', 'R']) { bend(B['thigh' + s], right, -a); bend(B['shin' + s], right, a * 2); bend(B['foot' + s], right, -a); }
  bend(B.spine, right, a * .4);
  av.model.position.y = -(1 - Math.cos(a)) * .85;
  av.crouched = true;
}
function resetCrouch(av) { if (av.crouched) { av.model.position.y = 0; av.crouched = false; } }
