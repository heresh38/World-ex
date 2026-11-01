// Combat hub: target registry, ray tracing against targets + world, splash damage, enemy bolts, loot pickups.
import * as THREE from 'three';
import { RARITY, ARCHETYPES } from './data.js';
import { rollRarity, rollWeapon } from './state.js';

const _v = new THREE.Vector3(), _w = new THREE.Vector3();

// ray vs sphere -> distance or -1
export function raySphere(o, d, c, r) {
  _v.subVectors(o, c); const b = _v.dot(d), cc = _v.lengthSq() - r * r, h = b * b - cc;
  if (h < 0) return -1; const t = -b - Math.sqrt(h); return t >= 0 ? t : (-b + Math.sqrt(h) >= 0 ? 0 : -1);
}
// ray vs vertical cylinder (x,z centre, y0..y1, radius) -> distance or -1
export function rayCyl(o, d, cx, cz, y0, y1, r) {
  const ox = o.x - cx, oz = o.z - cz, a = d.x * d.x + d.z * d.z;
  if (a < 1e-8) return -1;
  const b = ox * d.x + oz * d.z, c = ox * ox + oz * oz - r * r, h = b * b - a * c;
  if (h < 0) return -1;
  let t = (-b - Math.sqrt(h)) / a;
  if (t < 0) t = (-b + Math.sqrt(h)) / a;
  if (t < 0) return -1;
  const y = o.y + d.y * t;
  return (y >= y0 && y <= y1) ? t : -1;
}

export class Combat {
  constructor(game) {
    this.g = game;
    this.targets = new Set();
    this.bolts = []; this.pickups = [];
    this.boltGeo = new THREE.CylinderGeometry(.05, .05, 1, 6, 1, true); this.boltGeo.rotateX(Math.PI / 2);
  }

  reset() {
    this.targets.clear();
    this.bolts.forEach(b => b.m.removeFromParent()); this.bolts = [];
    this.pickups.forEach(p => this.freePickup(p)); this.pickups = [];
  }

  // nearest hit among targets (excluding owner side) and world geometry
  trace(o, d, max, side) {
    let best = max, tgt = null, crit = false;
    for (const t of this.targets) {
      if (!t.alive || t.side === side) continue;
      const h = t.hitTest(o, d, best);
      if (h && h.dist < best) { best = h.dist; tgt = t; crit = h.crit; }
    }
    const wh = this.g.world.collision.raycast(o, d, best);
    if (wh && wh.dist < best) return { hit: true, dist: wh.dist, point: wh.point, normal: wh.normal, terrain: wh.terrain, box: wh.box };
    const point = o.clone().addScaledVector(d, best);
    if (tgt) return { target: tgt, crit, dist: best, point };
    return { dist: max, point };
  }

  splash(p, r, dmg, side, exclude = null) {
    const kills = [];
    for (const t of this.targets) {
      if (!t.alive || t.side === side || t === exclude) continue;
      const c = t.center(_w); const d = c.distanceTo(p);
      if (d < r + (t.radius || .5)) {
        const f = 1 - Math.min(1, d / (r + .5)) * .6;
        const out = t.takeDamage(dmg * f, false, c, _v.subVectors(c, p).normalize(), side);
        this.g.hud.hitNumber(c, out, dmg * f, false);
        if (out.killed) kills.push(t);
      }
    }
    if (side !== 'player') {
      const pp = this.g.player; const d = _w.copy(pp.pos).setY(pp.pos.y + 1).distanceTo(p);
      if (d < r) pp.damage(dmg * (1 - d / r * .6), p);
    }
    return kills;
  }

  // ---------------------------------------------------------------- enemy bolts
  bolt(from, dir, speed, dmg, color = 0xff3326, victim = null) {
    const m = new THREE.Mesh(this.boltGeo, new THREE.MeshBasicMaterial({ color: new THREE.Color(color).multiplyScalar(5), toneMapped: false }));
    m.scale.set(1.4, 1.4, 1.6); m.position.copy(from); m.lookAt(_v.copy(from).add(dir));
    this.g.scene.add(m);
    this.bolts.push({ m, dir: dir.clone(), speed, dmg, life: 3.5, victim });
  }

  updateBolts(dt) {
    const p = this.g.player, world = this.g.world.collision;
    for (let i = this.bolts.length - 1; i >= 0; i--) {
      const b = this.bolts[i]; b.life -= dt;
      const step = b.speed * dt;
      let done = b.life <= 0;
      // faction infighting: a bolt aimed at a rival enemy only hits that enemy
      if (!done && b.victim) {
        const v = b.victim, sc = v.T.scale || 1;
        const t = v.alive ? rayCyl(b.m.position, b.dir, v.pos.x, v.pos.z, v.pos.y, v.pos.y + 1.7 * sc, .5 * sc) : -1;
        if (t >= 0 && t <= step) { v.takeDamage(b.dmg, false, b.m.position, b.dir, 'rival'); this.g.fx.impact(b.m.position, b.dir.clone().negate(), 'enemy'); done = true; }
        if (!done && world.raycast(b.m.position, b.dir, step)) done = true;
        if (!done) b.m.position.addScaledVector(b.dir, step);
        if (done || b.life <= 0) { b.m.removeFromParent(); b.m.material.dispose(); this.bolts.splice(i, 1); }
        continue;
      }
      // player capsule hit test (closest approach of the segment to the body axis)
      if (!done && !p.dead && p.mode !== 'car') {
        const t = rayCyl(b.m.position, b.dir, p.pos.x, p.pos.z, p.pos.y, p.pos.y + 1.85, .45);
        if (t >= 0 && t <= step) { p.damage(b.dmg, b.m.position); this.g.fx.impact(b.m.position, b.dir.clone().negate(), 'enemy'); done = true; }
      }
      if (!done && p.mode === 'car' && this.g.vehicles.current) {
        const c = this.g.vehicles.current.root.position;
        const t = raySphere(b.m.position, b.dir, _w.copy(c).setY(c.y + .8), 2.2);
        if (t >= 0 && t <= step) { this.g.vehicles.current.damage(b.dmg); done = true; }
      }
      if (!done) {
        const h = world.raycast(b.m.position, b.dir, step);
        if (h) { this.g.fx.impact(h.point, h.normal, 'metal'); done = true; }
        // water: bolts fizzle out in a splash where they cross the surface
        else if (this.g.water && this.g.water.hitTest(b.m.position, _v.copy(b.m.position).addScaledVector(b.dir, step), 'bolt')) done = true;
      }
      if (done) { b.m.removeFromParent(); b.m.material.dispose(); this.bolts.splice(i, 1); continue; }
      b.m.position.addScaledVector(b.dir, step);
    }
  }

  // ---------------------------------------------------------------- loot
  drop(pos, kind, level, chance = .15) {
    const g = this.g;
    const credits = Math.round(8 + Math.random() * 10 + level * 2);
    g.gain('credits', credits, true);
    if (Math.random() < .35) this.spawnPickup(pos, 'ammo');
    if (Math.random() < chance) {
      const rarity = rollRarity(level * .006 + (kind === 'brute' ? .12 : 0));
      this.spawnPickup(pos, 'core', { rarity, level });
    }
  }

  spawnPickup(pos, type, data = {}) {
    const g = this.g;
    const obj = g.assets.clone('props_world', type === 'core' ? 'PR_core' : 'PR_ammo');
    const color = type === 'core' ? RARITY[data.rarity].color : '#ffffff';
    obj.traverse(o => {
      if (o.isMesh) {
        o.material = o.material.clone(); o.castShadow = false;
        if (/core_glow|ammo_glow/.test(o.material.name)) { o.material.color.set(color); o.material.emissive.set(color); o.material.emissiveIntensity = type === 'core' ? 2.2 : 1.2; }
      }
    });
    obj.position.copy(pos); obj.position.x += (Math.random() - .5); obj.position.z += (Math.random() - .5);
    const gy = g.world.collision.ground(obj.position.x, obj.position.z);
    obj.position.y = Math.max(gy, pos.y - 1.2) + (type === 'core' ? .8 : .05);
    g.scene.add(obj);
    let beam = null;
    if (type === 'core' && data.rarity >= 2) {
      beam = new THREE.Mesh(new THREE.CylinderGeometry(.05, .2, 14, 8, 1, true),
        new THREE.MeshBasicMaterial({ color: new THREE.Color(color).multiplyScalar(2), transparent: true, opacity: .35, blending: THREE.AdditiveBlending, depthWrite: false, toneMapped: false }));
      beam.position.y = 7; obj.add(beam);
    }
    this.pickups.push({ obj, type, data, t: 0, life: 90, baseY: obj.position.y });
  }

  updatePickups(dt) {
    const g = this.g, p = g.player;
    for (let i = this.pickups.length - 1; i >= 0; i--) {
      const k = this.pickups[i]; k.t += dt; k.life -= dt;
      if (k.type === 'core') { k.obj.rotation.y += dt * 1.8; k.obj.position.y = k.baseY + Math.sin(k.t * 2.5) * .12; }
      const d = Math.hypot(k.obj.position.x - p.pos.x, k.obj.position.z - p.pos.z);
      const near = d < 1.6 && Math.abs(k.obj.position.y - p.pos.y) < 2.2 && !p.dead;
      if (near || k.life <= 0) {
        if (near) this.collect(k);
        this.freePickup(k); this.pickups.splice(i, 1);
      }
    }
  }

  collect(k) {
    const g = this.g;
    if (k.type === 'ammo') {
      for (let i = 0; i < 3; i++) {
        const w = g.weapons.equipped(i); if (!w) continue;
        const a = g.weapons.ammoOf(w), A = ARCHETYPES[w.arch];
        a.reserve = Math.min(A.reserve * 1.5, a.reserve + Math.ceil(A.reserve * (A.slot === 2 ? .15 : .25)));
      }
      g.audio.ammo(); g.hud.feed('Ammo synthesised', '#ffffff'); g.hud.dirty = true;
    } else {
      const power = Math.max(1, g.power() + Math.round((Math.random() - .3) * 6) + (k.data.rarity >= 3 ? 4 : 0));
      const w = rollWeapon(power, { rarity: k.data.rarity });            // random archetype, perks, rolls and sight
      g.addWeapon(w);
      g.audio.pickup(k.data.rarity);
      g.hud.feed(w.name + ' · ' + ARCHETYPES[w.arch].name + ' · ' + w.power, RARITY[w.rarity].color);
    }
  }

  // a pickup owns its cloned materials and its light-beam geometry (the mesh geometry is the shared model's)
  freePickup(k) {
    k.obj.removeFromParent();
    k.obj.traverse(o => { if (!o.isMesh) return; o.material.dispose(); if (o.geometry.type === 'CylinderGeometry') o.geometry.dispose(); });
  }

  update(dt) { this.updateBolts(dt); this.updatePickups(dt); }
}
