// Pedestrians: a fixed crowd placed across the whole map when Earth loads (sidewalks, village lanes, farm yards).
// Nobody is recycled or teleported: they stroll, panic and flee around buildings (capsule collision), can be shot or
// run over, and stay down when they die.
import * as THREE from 'three';
import { Avatar } from '../../game/avatar.js';
import { raySphere, rayCyl } from '../../game/combat.js';

const SKIN = ['#f4d6c6', '#e8bfa5', '#d4a184', '#b9805f', '#8f5b3f', '#6b4130', '#4a2d22'];
const HAIR = ['#1a1310', '#2b1d14', '#4a3020', '#7a5432', '#b88b4e', '#d8c08a', '#8a8a8a', '#5a1f17'];
const EYES = ['#6f8fae', '#4f7a9e', '#6b8a5a', '#7a5a3a', '#4a3424', '#8a8f99'];
const SHIRT = ['#e8e6e2', '#2a2d33', '#7a1f2a', '#1f4a7a', '#2f6a4a', '#c9a24a', '#6a4a8a', '#d86a3a', '#9aa0a8', '#4a3a2a', '#e0b0c0', '#3a6a8a'];
const PANTS = ['#2a3a5a', '#1f2228', '#4a4030', '#6a6a70', '#2f3a2a', '#8a7a60', '#ffffff'];
const DENIM = ['#ffffff', '#ffffff', '#c8d2e6', '#7a7f8c', '#3a3c44'];
const SHOES = ['#1c1c1c', '#5a3a26', '#e6e6e6', '#3a3a3a', '#8a5a3a'];
const pick = (a, r) => a[Math.floor(r() * a.length)];
// Pedestrians use the player bodies (crowd LOD player_<sex>_npc.glb from players.py) with a random face and outfit.
const MODEL = { female: 'player_female_npc', male: 'player_male_npc' };
const MODEL_H = { female: 1.68, male: 1.84 };            // anatomy.Body heights
const WEAR = {                                           // everyday pieces per slot (players.py NPC_KEEP item ids)
  female: { top: ['tee', 'tank', 'blouse', 'sweater'], legs: ['jeans', 'chinos', 'shorts', 'skirt'],
    dress: ['sundress'], outer: ['hoodie', 'jacket'], feet: ['sneakers', 'sneakers', 'ankle_boots'], head: ['beanie', 'cap'] },
  male: { top: ['tee', 'tee', 'flannel', 'sweater'], legs: ['jeans', 'jeans', 'chinos', 'shorts', 'cargo'],
    outer: ['hoodie', 'jacket'], feet: ['sneakers', 'sneakers', 'ankle_boots'], head: ['beanie', 'cap'] },
};

// A random but plausible look: always dressed (top + legs, or a dress), shoes, underwear stays on (locked slots).
export function randomCharacter(av, sex, r = Math.random) {
  const W = av.wardrobe, M = (av.meta && av.meta.morphs) || { groups: {}, sliders: [] };
  const pool = slot => (WEAR[sex][slot] || []).filter(id => W[slot] && W[slot][id]);
  const pickW = slot => { const l = pool(slot); return l.length ? pick(l, r) : 'none'; };
  const wear = {};
  for (const slot of Object.keys(av.items)) wear[slot] = 'none';
  wear.hair = W.hair ? pick(Object.keys(W.hair), r) : 'none';
  if (sex === 'male' && r() < .05) wear.hair = 'none';
  if (sex === 'female' && pool('dress').length && r() < .28) wear.dress = pickW('dress');
  else { wear.top = pickW('top'); wear.legs = pickW('legs'); }
  if (r() < .3) wear.outer = pickW('outer');
  wear.feet = pickW('feet');
  if (r() < .14) wear.head = pickW('head');
  const tints = {};
  for (const slot of ['top', 'outer', 'dress', 'head']) tints[slot] = pick(SHIRT, r);
  tints.legs = /jeans|shorts/.test(wear.legs) ? pick(DENIM, r) : pick(PANTS, r);
  tints.feet = pick(SHOES, r);
  const face = {}, sliders = {};
  for (const [g, list] of Object.entries(M.groups)) face[g] = r() < .65 ? pick(list, r) : null;
  for (const n of M.sliders) sliders[n] = +((r() * 2 - 1) * .7).toFixed(2);
  return { v: 3, body: sex, skin: pick(SKIN, r), eyes: pick(EYES, r), hairColor: pick(HAIR, r), brow: Math.floor(r() * 4),
    face, sliders, wear, tints, glow: null };
}
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
    if (av.isPlayerBody) {
      this.look = randomCharacter(av, this.sex, r);
      av.applyCharacter(this.look);
      // peds never change clothes: drop the hidden wardrobe pieces from the scene graph (fewer objects to update)
      const hidden = [];
      av.model.traverse(o => { if (!o.visible && !o.isBone && o !== av.model) hidden.push(o); });
      for (const o of hidden) o.removeFromParent();
      av.allMats = []; av.model.traverse(o => { if (o.isMesh) av.allMats.push(o.material); });
    } else {
      av.setLook(pick(av.outfits, r), pick(av.hairStyles, r));
      const tint = (prefix, hex) => av.allMats.forEach(m => { if (m.name.startsWith(prefix)) { m.color.copy(m.userData.base).multiply(new THREE.Color(hex)); } });
      tint('skin', pick(SKIN, r)); tint('hair', pick(HAIR, r)); tint('shirt', pick(SHIRT, r)); tint('pants', pick(PANTS, r)); tint('shoes', pick(SHOES, r));
    }
    av.root.scale.setScalar((this.baseScale || 1) * (.98 + r() * .04));
  }

  // shadows only for nearby peds, nothing drawn far away (the crowd is spread over the whole map)
  lod(d) {
    const sh = d < 45, vis = d < 170 || !this.alive;
    if (sh !== this.shadow) { this.shadow = sh; this.av.model.traverse(o => { if (o.isMesh) o.castShadow = sh; }); }
    if (this.av.root.visible !== vis) this.av.root.visible = vis;
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
    if (point) this.g.fx.blood(point, dir ? dir.clone().negate() : null, crit ? 1.4 : .9);
    this.g.world.population.alarm(this.pos, 30, point);
    if (this.hp <= 0) { this.die(side === 'player', dir ? dir.clone().setY(Math.max(.2, dir.y)).multiplyScalar(crit ? 6 : 4) : null); return { killed: true }; }
    this.flee(point || this.g.player.pos);
    return { killed: false };
  }

  die(byPlayer, impulse = null) {
    this.alive = false; this.state = 'dead'; this.deadT = 0;
    this.g.combat.targets.delete(this);
    this.av.ragdoll(impulse || new THREE.Vector3(0, 1, 0), (x, z) => this.g.world.collision.ground(x, z));
    this.g.fx.bloodPool(this.pos.clone(), 1);
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

const TARGET_H = { female: 1.65, male: 1.77 };
const modelH = {};

export class Population {
  constructor(game, map, paths) {
    this.g = game; this.map = map; this.paths = paths;
    this.peds = [];
    const COUNT = game.touch ? 60 : 150;          // phones: smaller crowd (each pedestrian is a full skinned body)
    // spread the crowd along every path, weighted by path length
    const total = paths.reduce((a, p) => a + p.total, 0);
    for (let i = 0; i < COUNT; i++) {
      const sex = i % 2 ? 'male' : 'female';
      const npc = !!(game.assets.models && game.assets.models[MODEL[sex]]) && !window.__civPeds;   // __civPeds: old crowd (A/B tests)
      const model = npc ? MODEL[sex] : (sex === 'male' ? 'civ_male' : 'civ_female');
      const av = new Avatar(game.assets, model);
      if (npc) modelH[model] = MODEL_H[sex];
      if (!modelH[model]) { av.root.updateMatrixWorld(true); modelH[model] = new THREE.Box3().setFromObject(av.model).getSize(_v).y || TARGET_H[sex]; }
      av.root.traverse(o => { if (o.isMesh) o.frustumCulled = true; });
      game.world.scene.add(av.root);
      const q = new Ped(game, av, sex);
      q.baseScale = TARGET_H[sex] / modelH[model];
      let r = Math.random() * total, path = paths[0];
      for (const pth of paths) { r -= pth.total; if (r <= 0) { path = pth; break; } }
      this.place(q, path, Math.random() * path.total);
      this.peds.push(q);
    }
    this.frame = 0;
  }

  place(ped, path, s) {
    ped.path = path; ped.s = s; ped.dir = Math.random() < .5 ? 1 : -1;
    ped.speed = 1.15 + Math.random() * .5;
    ped.active = true; ped.alive = true; ped.state = 'walk'; ped.hp = 55; ped.deadT = 0; ped.hitT = 9; ped.idleT = 4 + Math.random() * 10;
    ped.vel = new THREE.Vector3();
    ped.dress(Math.random);
    ped.av.root.visible = true; ped.av.mixer.stopAllAction(); ped.av.current = null; ped.av.play('WalkRelaxed', 0);
    ped.yaw = this.pointOn(path, s, ped.pos);
    ped.pos.y = this.map.height(ped.pos.x, ped.pos.z);
    ped.av.root.position.copy(ped.pos);
    this.g.combat.targets.add(ped);
  }

  // paths: [{pts:[Vector3...], closed:true}]
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

  alarm(pos, radius, from = null) {
    for (const q of this.peds) if (q.alive && q.pos.distanceTo(pos) < radius) q.flee(from || pos);
  }

  get activeCount() { return this.peds.length; }

  // walk with collision (fleeing, returning to the sidewalk): slide around walls instead of passing through them
  move(q, dir, speed, dt) {
    const col = this.g.world.collision;
    q.vel.set(dir.x * speed, -9, dir.z * speed);
    const x0 = q.pos.x, z0 = q.pos.z;
    col.moveCapsule(q.pos, q.vel, .3, 1.7, dt);
    const moved = Math.hypot(q.pos.x - x0, q.pos.z - z0);
    return moved > speed * dt * .4;
  }

  update(dt) {
    const g = this.g, p = g.player.mode === 'car' && g.vehicles.current ? g.vehicles.current.pos : g.player.pos;
    this.frame++;
    for (let i = 0; i < this.peds.length; i++) {
      const q = this.peds[i], av = q.av;
      const d = q.pos.distanceTo(p);
      // far away: same life, updated a quarter as often
      const far = d > 220;
      if (far && (i + this.frame) % 4) continue;
      const step = far ? dt * 4 : dt;
      if (!q.alive) { q.deadT += step; av.update(d < 60 ? step : 0); continue; }
      q.hitT += step;
      // every car (the player's, traffic, parked ones rolling) is solid: slow contact pushes people aside,
      // a hit above ~6 m/s runs them over (vehicles.pedContact tests the car's real footprint)
      const hit = g.vehicles.pedContact(q);
      if (hit) {
        const hitBy = hit.car, hv = g.vehicles.carVel(hitBy), dir = new THREE.Vector3(hv.x, 0, hv.z).normalize();
        g.fx.blood && g.fx.blood(_v.copy(q.pos).setY(q.pos.y + 1), dir.clone().setY(.4), 1.6);
        q.die(hitBy === g.vehicles.current, dir.setY(.5).multiplyScalar(Math.min(14, hit.speed * .6)));
        if (hitBy.traffic) hitBy.traffic.hitSomeone(hitBy);
        this.alarm(q.pos, 35, hitBy.pos); continue;
      }
      let speed = q.speed, anim = 'WalkRelaxed', animSpeed = 1;
      if (q.state === 'flee') {
        q.fleeT -= step; speed = 4.6; anim = 'RunRelaxed'; animSpeed = .95;
        if (!this.move(q, q.fleeDir, speed, step)) {
          // blocked: turn and run along the wall
          const s2 = Math.random() < .5 ? 1 : -1;
          q.fleeDir.set(-q.fleeDir.z * s2, 0, q.fleeDir.x * s2);
        }
        q.yaw = Math.atan2(q.fleeDir.x, q.fleeDir.z);
        if (q.fleeT <= 0) {
          q.state = 'return';
          let best = 0, bd = 1e9;
          for (let s = 0; s < q.path.total; s += 4) { this.pointOn(q.path, s, _h); const dd = _h.distanceTo(q.pos); if (dd < bd) { bd = dd; best = s; } }
          q.s = best;
        }
      } else if (q.state === 'return') {
        // walk back to the sidewalk instead of snapping
        this.pointOn(q.path, q.s, _h);
        _h.sub(q.pos).setY(0); const L = _h.length();
        if (L < .8) q.state = 'walk';
        else { _h.divideScalar(L); if (!this.move(q, _h, speed * 1.2, step)) { q.state = 'walk'; } q.yaw = Math.atan2(_h.x, _h.z); }
      } else if (q.state === 'idle') {
        q.idleT -= step; anim = 'IdleRelaxed';
        if (q.idleT <= 0) { q.state = 'walk'; q.idleT = 6 + Math.random() * 14; }
      } else {
        q.s += q.dir * speed * step;
        const yaw = this.pointOn(q.path, q.s, _h);
        q.pos.x += (_h.x - q.pos.x) * Math.min(1, step * 3); q.pos.z += (_h.z - q.pos.z) * Math.min(1, step * 3);
        q.yaw = yaw + (q.dir < 0 ? Math.PI : 0);
        q.idleT -= step;
        if (q.idleT <= 0) { q.state = 'idle'; q.idleT = 2 + Math.random() * 4; }
        if (!far) {
          const pd = Math.hypot(q.pos.x - g.player.pos.x, q.pos.z - g.player.pos.z);
          if (pd < .9 && g.player.mode === 'foot') { q.pos.x += (q.pos.x - g.player.pos.x) / pd * .05; q.pos.z += (q.pos.z - g.player.pos.z) / pd * .05; }
          if (g.player.aiming && pd < 14) q.flee(g.player.pos);
        }
      }
      if (q.state !== 'flee' && q.state !== 'return') q.pos.y = this.map.height(q.pos.x, q.pos.z);
      if (!far) g.vehicles.pedContact(q);          // walked into a car: slide around it (hard hits are handled above)
      av.root.position.copy(q.pos); av.root.rotation.y = q.yaw;
      q.lod(d);
      if (!far) { av.play(anim, .25, animSpeed); av.update(d < 70 ? step : (Math.random() < .3 ? step * 3 : 0)); }
    }
  }

  clear() { for (const q of this.peds) { this.g.combat.targets.delete(q); q.av.dispose(); } }
}
