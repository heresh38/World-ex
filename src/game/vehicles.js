// Hover cars: summon (V), enter/exit (E), arcade hover physics with collision, boost, damage.
import * as THREE from 'three';

const _v = new THREE.Vector3(), _q = new THREE.Quaternion();
const SPECS = {
  car_sport: { max: 40, boost: 58, accel: 22, turn: 1.9, hp: 400, name: 'Vanta GT' },
  car_utility: { max: 31, boost: 44, accel: 17, turn: 1.6, hp: 650, name: 'Mule Hauler' },
};

export class Car {
  constructor(game, model, paint, pos, yaw) {
    this.g = game; this.model = model; this.S = SPECS[model];
    this.root = game.assets.clone(model);
    this.root.traverse(o => {
      if (o.isMesh) {
        o.material = o.material.clone();
        if (o.material.name === 'car_paint') { o.material.color.set(paint); o.material.envMapIntensity = 1.4; }
        if (o.material.name === 'hover_glow') this.glow = o.material;
      }
    });
    this.seat = this.root.getObjectByName('seat');
    this.pos = pos.clone(); this.vel = new THREE.Vector3(); this.yaw = yaw; this.steer = 0; this.roll = 0; this.pitch = 0;
    this.hp = this.S.hp; this.alive = true; this.bob = Math.random() * 6;
    this.root.position.copy(pos); this.root.rotation.y = yaw;
    game.scene.add(this.root);
  }

  damage(n) {
    if (!this.alive) return;
    this.hp -= n;
    if (this.hp <= 0) {
      this.alive = false;
      const p = this.root.position.clone(); p.y += 1;
      this.g.fx.explosion(p, 6); this.g.audio.explosion(p);
      if (this.g.vehicles.current === this) { this.g.vehicles.exit(true); this.g.player.damage(40, p); }
      this.root.visible = false;
    }
  }

  update(dt, driving, input) {
    const world = this.g.world.collision, S = this.S;
    let thr = 0, st = 0, boost = false, brake = false;
    if (driving && input.enabled) {
      thr = (input.key('KeyW') ? 1 : 0) - (input.key('KeyS') ? 1 : 0);
      st = (input.key('KeyA') ? 1 : 0) - (input.key('KeyD') ? 1 : 0);
      boost = input.key('ShiftLeft') || input.key('ShiftRight'); brake = input.key('Space');
    }
    const fwd = _v.set(Math.sin(this.yaw), 0, Math.cos(this.yaw));
    let vf = this.vel.x * fwd.x + this.vel.z * fwd.z;
    const vs = this.vel.x * fwd.z - this.vel.z * fwd.x;            // lateral
    const max = boost ? S.boost : S.max;
    if (thr > 0) vf += (vf < max ? S.accel * (boost ? 1.5 : 1) : -S.accel * .5) * dt;
    else if (thr < 0) vf -= (vf > 0 ? S.accel * 1.6 : S.accel * .6) * dt;
    else vf *= 1 - .6 * dt;
    if (brake) vf *= 1 - 3 * dt;
    vf = Math.max(-12, vf);
    this.steer += (st - this.steer) * Math.min(1, dt * 6);
    const turnRate = S.turn * this.steer * Math.min(1, Math.abs(vf) / 6) * (vf < 0 ? -1 : 1) * (1 - Math.min(.45, Math.abs(vf) / 120));
    this.yaw += turnRate * dt;
    const nf = _v.set(Math.sin(this.yaw), 0, Math.cos(this.yaw));
    const grip = brake ? 1.5 : 4.5;
    const lat = vs * (1 - Math.min(1, grip * dt));
    this.vel.x = nf.x * vf + nf.z * lat; this.vel.z = nf.z * vf - nf.x * lat;
    // hover over terrain/obstacles: physics on a "feet" point, visual hovers above
    const p = this.pos; const before = Math.hypot(this.vel.x, this.vel.z);
    this.vel.y = 0;
    world.moveCapsule(p, this.vel, 1.25, 1.4, dt, .9);
    const after = Math.hypot(this.vel.x, this.vel.z);
    if (before - after > 10 && driving) { this.damage((before - after) * 1.5); this.g.player.shake = Math.min(1, (before - after) / 25); this.g.audio.land(); }
    // align to terrain slope
    const h0 = world.ground(p.x + nf.x * 2, p.z + nf.z * 2), h1 = world.ground(p.x - nf.x * 2, p.z - nf.z * 2);
    this.pitch += (Math.atan2(h1 - h0, 4) - this.pitch) * Math.min(1, dt * 5);
    this.roll += (-this.steer * Math.min(1, Math.abs(vf) / 30) * .22 - this.roll) * Math.min(1, dt * 4);
    this.bob += dt * 2.4;
    this.root.position.set(p.x, p.y + .25 + Math.sin(this.bob) * .05, p.z);
    this.root.rotation.set(this.pitch, this.yaw, this.roll, 'YXZ');
    if (this.glow) this.glow.emissiveIntensity = 1.6 + Math.abs(vf) * .04 + Math.sin(this.bob * 7) * .15;
    this.speed = Math.abs(vf);
    if (driving) this.g.save.stats.carDistance += this.speed * dt;
  }

  dispose() { this.root.removeFromParent(); }
}

export class Vehicles {
  constructor(game) { this.g = game; this.cars = []; this.current = null; this.mine = null; }

  clear() { this.cars.forEach(c => c.dispose()); this.cars = []; this.current = null; this.mine = null; }

  spawn(model, paint, pos, yaw) { const c = new Car(this.g, model, paint, pos, yaw); this.cars.push(c); return c; }

  summon() {
    const g = this.g, p = g.player;
    if (!g.world.allowCars || p.mode !== 'foot') { g.audio.ui('deny'); return; }
    if (this.mine) { this.mine.dispose(); this.cars.splice(this.cars.indexOf(this.mine), 1); }
    const yaw = p.yaw;
    // find a clear spot beside the player
    let pos = null;
    for (const off of [[3.5, 0], [-3.5, 0], [0, 4.5], [0, -4.5], [6, 0], [-6, 0]]) {
      const x = p.pos.x + Math.cos(yaw) * off[0] + Math.sin(yaw) * off[1], z = p.pos.z - Math.sin(yaw) * off[0] + Math.cos(yaw) * off[1];
      const near = [...g.world.collision.near(x, z, 2)].some(b => b.max.y > g.world.collision.ground(x, z) + .9 && x > b.min.x - 1.5 && x < b.max.x + 1.5 && z > b.min.z - 1.5 && z < b.max.z + 1.5);
      if (!near) { pos = new THREE.Vector3(x, g.world.collision.ground(x, z), z); break; }
    }
    if (!pos) { g.hud.toast('No room to land the car here'); g.audio.ui('deny'); return; }
    this.mine = this.spawn(g.save.car.model, g.save.car.paint, pos, yaw);
    g.fx.emit(_v.copy(pos).setY(pos.y + 1), 40, 5, 0x3ad6ff, .6, 2, .1);
    g.audio.ui('open');
  }

  nearest(p, r = 3.6) {
    let best = null, bd = r;
    for (const c of this.cars) { if (!c.alive) continue; const d = Math.hypot(c.pos.x - p.x, c.pos.z - p.z); if (d < bd) { bd = d; best = c; } }
    return best;
  }

  enter(c) {
    const g = this.g, p = g.player;
    this.current = c; p.mode = 'car';
    p.avatar.attachGun(null);
    p.avatar.play('Sit', .2);
    g.audio.carLoop(); g.audio.door();
    g.hud.dirty = true;
  }

  exit(forced = false) {
    const g = this.g, p = g.player, c = this.current; if (!c) return;
    this.current = null; p.mode = 'foot';
    const side = new THREE.Vector3(Math.cos(c.yaw), 0, -Math.sin(c.yaw));
    let out = c.pos.clone().addScaledVector(side, 2.4);
    if ([...g.world.collision.near(out.x, out.z, 1)].some(b => out.x > b.min.x - .4 && out.x < b.max.x + .4 && out.z > b.min.z - .4 && out.z < b.max.z + .4 && b.max.y > out.y + .5))
      out = c.pos.clone().addScaledVector(side, -2.4);
    out.y = g.world.collision.ground(out.x, out.z);
    p.pos.copy(out); p.vel.set(0, 0, 0); p.yaw = c.yaw;
    p.avatar.root.position.copy(out); p.avatar.root.rotation.set(0, c.yaw, 0);
    g.audio.updateCar(false, 0); g.audio.door();
    g.weapons.refreshModel(); g.hud.dirty = true;
  }

  update(dt, input) {
    const g = this.g, p = g.player;
    for (const c of this.cars) if (c.alive) c.update(dt, c === this.current, input);
    if (this.current) {
      const c = this.current;
      if (c.seat) { c.seat.getWorldPosition(_v); c.root.getWorldQuaternion(_q); }
      p.avatar.root.position.copy(_v).y -= .48; p.avatar.root.quaternion.copy(_q);
      p.pos.copy(c.pos); p.yaw = c.yaw;
      g.audio.updateCar(true, c.speed);
    }
  }
}
