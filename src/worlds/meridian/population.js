// Pedestrians of New Meridian with daily routines. The crowd lives around the player: people step out of doors, off
// trams or in from out of view, follow the in-game clock (g.clock) with goals of their own and walk there over the
// sidewalk graph (npcnav.js), waiting at the kerb for a gap in the traffic before they cross:
//   morning commute: out of homes and off the trams, into the office towers; coffee at the kiosks
//   lunch: queues at the food kiosks, cafe tables and benches fill up on the heritage avenue and the plazas
//   afternoon: errands, shop windows, friends meeting on the plazas
//   evening: home, or out on the heritage avenue (cafes, chatting groups, the hotel); late at night only a few owls
// Walkers who meet may stop, face each other and talk for a while; seated neighbours talk too (head and hand
// gestures are added on top of the clips). People who reach their door or board a tram leave the scene and come back
// elsewhere out of sight, so the crowd size follows the time of day. Gunfire, aiming and crashes still scatter them;
// they can be shot or run over, and the dead stay down until the player has moved on.
// Villages, farms and the spaceport keep the simple loop walkers (rural paths).
// Cost control: decisions and movement are ticked every frame near the player, every few frames further out and
// rarely far away; skinned animation only runs for people in view, at a reduced rate with distance.
import * as THREE from 'three';
import { Avatar } from '../../game/avatar.js';
import { raySphere, rayCyl } from '../../game/combat.js';
import { mulberry } from '../../game/state.js';
import { NavGraph } from './npcnav.js';
import { Fauna } from './fauna.js';
import { CITY_EDGE, TRANSIT } from './layout.js';

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
  const face = {}, sliders = {};
  for (const [g, list] of Object.entries(M.groups)) face[g] = r() < .65 ? pick(list, r) : null;
  for (const n of M.sliders) sliders[n] = +((r() * 2 - 1) * .7).toFixed(2);
  return { v: 3, body: sex, skin: pick(SKIN, r), eyes: pick(EYES, r), hairColor: pick(HAIR, r), brow: Math.floor(r() * 4),
    face, sliders, wear, tints: randomTints(wear, r), glow: null };
}
function randomTints(wear, r) {
  const tints = {};
  for (const slot of ['top', 'outer', 'dress', 'head']) tints[slot] = pick(SHIRT, r);
  tints.legs = /jeans|shorts/.test(wear.legs) ? pick(DENIM, r) : pick(PANTS, r);
  tints.feet = pick(SHOES, r);
  return tints;
}

// ---------------------------------------------------------------- the daily rhythm
// crowd size (fraction of COUNT) through the day
const DENSITY = [[0, .16], [4.5, .1], [6.3, .4], [7.5, 1], [9.2, .9], [10.2, .68], [11.6, .85], [12.3, 1], [13.8, 1], [14.6, .7],
  [16.4, .8], [17.2, 1], [19, .95], [20.5, .85], [22, .6], [23.2, .3], [24, .16]];
// what people set out to do (weights), by the hour they start
const MIX = [
  [0, { home: 5, wander: 3, seat: 1, meet: 1.2, hotel: 1 }],
  [5.5, { work: 5, platform: 1.6, kiosk: 1.5, wander: 1.2, home: .4, seat: .3, window: .3 }],
  [9.4, { window: 2, wander: 2, seat: 1.6, kiosk: 1, meet: 1.8, work: 1.3, platform: .8, shop: 1.1, home: .5 }],
  [11.6, { kiosk: 2.6, seat: 3.6, meet: 2.2, window: 1, wander: .8, work: .7, platform: .3 }],
  [14, { window: 2, wander: 2, seat: 1.6, kiosk: .8, meet: 1.8, work: 1.4, platform: .8, shop: 1.1, home: .6 }],
  [16.6, { home: 3.4, platform: 2.4, wander: 1, seat: .9, meet: 1.1, window: .8, kiosk: .4, hotel: .5 }],
  [19, { seat: 3, meet: 3.2, window: 1.4, wander: 2, hotel: 1, home: 1.3, kiosk: .5 }],
  [22.5, { home: 4, wander: 2, seat: .6, meet: .8, hotel: .8 }],
];
const DOOR_OF = { work: ['work'], home: ['home'], hotel: ['hotel'], shop: ['shop'] };
const lerpTable = (T, h) => { for (let i = 1; i < T.length; i++) if (h <= T[i][0]) { const [a, va] = T[i - 1], [b, vb] = T[i]; return va + (vb - va) * (h - a) / (b - a); } return T[T.length - 1][1]; };
const mixAt = h => { let m = MIX[0][1]; for (const [s, w] of MIX) if (h >= s) m = w; return m; };
const rollKind = (m, r) => { let t = 0; for (const k in m) t += m[k]; let x = r() * t; for (const k in m) { x -= m[k]; if (x <= 0) return k; } return 'wander'; };

const VIS_D = 170, RECYCLE_D = 300, SPAWN_MIN = 30, SPAWN_MAX = 235;
const _v = new THREE.Vector3(), _h = new THREE.Vector3(), _q = new THREE.Quaternion(), _q2 = new THREE.Quaternion(), _ax = new THREE.Vector3();
const _sph = new THREE.Sphere(new THREE.Vector3(), 1.2), _frus = new THREE.Frustum(), _pm = new THREE.Matrix4();
const UP = new THREE.Vector3(0, 1, 0);
const wrapA = a => Math.atan2(Math.sin(a), Math.cos(a));

// bend a bone about a world axis (converted into its parent's space); the avatar resets touched bones every update
function bend(av, bone, axis, ang) {
  if (!bone || !bone.parent || !ang) return;
  bone.parent.getWorldQuaternion(_q);
  _ax.copy(axis).applyQuaternion(_q.invert()).normalize();
  bone.quaternion.premultiply(_q2.setFromAxisAngle(_ax, ang));
  av.touched.add(bone);
}

class Ped {
  constructor(game, av, sex) {
    this.g = game; this.av = av; this.sex = sex; this.side = 'civilian'; this.alive = false; this.active = false;
    this.pos = new THREE.Vector3(); this.yaw = 0; this.radius = .5;
    this.T = { name: 'Civilian' };
    this.state = 'gone'; this.vel = new THREE.Vector3(); this.wps = null; this.wi = 0;
    this.acc = 0; this.social = Math.random() < .6; this.chatCd = Math.random() * 20; this.speed = 1.3;
    this.restP = new Map(); av.model.traverse(o => { if (o.isBone) this.restP.set(o, o.position.clone()); });
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
      this.retint(r);
    }
    av.root.scale.setScalar((this.baseScale || 1) * (.98 + r() * .04));
  }

  // a "new" person on respawn: same garments (the hidden ones are gone), new skin, hair and clothing colours
  retint(r) {
    const av = this.av;
    if (av.isPlayerBody && this.look) {
      const c = this.look;
      c.skin = pick(SKIN, r); c.hairColor = pick(HAIR, r); c.eyes = pick(EYES, r); c.tints = randomTints(c.wear, r);
      av.applyCharacter(c);
    } else {
      const tint = (prefix, hex) => av.allMats.forEach(m => { if (m.name.startsWith(prefix)) { m.color.copy(m.userData.base).multiply(new THREE.Color(hex)); } });
      tint('skin', pick(SKIN, r)); tint('hair', pick(HAIR, r)); tint('shirt', pick(SHIRT, r)); tint('pants', pick(PANTS, r)); tint('shoes', pick(SHOES, r));
    }
  }

  // shadows only for nearby peds; the body leaves the scene graph when far (no matrix updates for it)
  lod(d, scene) {
    const sh = d < 45, vis = this.state !== 'gone' && (d < VIS_D || (!this.alive && d < 260));
    if (sh !== this.shadow) { this.shadow = sh; this.av.model.traverse(o => { if (o.isMesh) o.castShadow = sh; }); }
    if (vis && !this.av.root.parent) scene.add(this.av.root);
    else if (!vis && this.av.root.parent) this.av.root.removeFromParent();
    this.av.root.visible = vis;
  }

  center(out) { return out.copy(this.pos).setY(this.pos.y + 1.0); }

  hitTest(o, d, max) {
    if (!this.av.head || this.state === 'gone') return null;
    this.av.head.getWorldPosition(_h); _h.y += .08;
    const th = raySphere(o, d, _h, .14);
    let best = th >= 0 && th < max ? th : -1, crit = best >= 0;
    const tb = rayCyl(o, d, this.pos.x, this.pos.z, this.pos.y, this.pos.y + (this.state === 'sit' ? 1.2 : 1.5), .28);
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
    const pop = this.g.world.population;
    pop.leaveSpot(this);
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
    if (!this.alive || this.state === 'gone') return;
    this.g.world.population.leaveSpot(this);
    if (this.state === 'sit' || this.state === 'settle') this.pos.y = this.mode === 'nav' ? 0 : this.pos.y;
    this.state = 'flee'; this.fleeT = 7 + Math.random() * 5; this.scared = 60 + Math.random() * 60;
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
    this.w = game.world; this.scene = game.world.scene;
    this.peds = []; this.groups = []; this.rnd = mulberry(90210);
    const t0 = performance.now();
    this.nav = new NavGraph(this.w);
    this.navMs = performance.now() - t0;
    // seats close together (a bench's two halves, the chairs across a cafe table): neighbours talk
    const S = this.nav.pois.seat;
    for (const a of S) a.nb = S.filter(b => b !== a && Math.abs(b.x - a.x) < 1.8 && Math.abs(b.z - a.z) < 1.8 && Math.hypot(b.x - a.x, b.z - a.z) < 1.7);
    // rural paths (villages, farms, spaceport): the simple loop walkers
    this.rural = paths.filter(p => p.pts.some(v => Math.abs(v.x) > CITY_EDGE + 5 || Math.abs(v.z) > CITY_EDGE + 5));
    this.ruralPts = [];
    for (const p of this.rural) for (let s = 0; s < p.total; s += 12) { this.pointOn(p, s, _v); this.ruralPts.push({ x: _v.x, z: _v.z, path: p, s }); }
    this.COUNT = game.touch ? 60 : 150;          // phones: smaller crowd (each pedestrian is a full skinned body)
    for (let i = 0; i < this.COUNT; i++) {
      const sex = i % 2 ? 'male' : 'female';
      const npc = !!(game.assets.models && game.assets.models[MODEL[sex]]) && !window.__civPeds;   // __civPeds: old crowd (A/B tests)
      const model = npc ? MODEL[sex] : (sex === 'male' ? 'civ_male' : 'civ_female');
      const av = new Avatar(game.assets, model);
      if (npc) modelH[model] = MODEL_H[sex];
      if (!modelH[model]) { av.root.updateMatrixWorld(true); modelH[model] = new THREE.Box3().setFromObject(av.model).getSize(_v).y || TARGET_H[sex]; }
      av.root.traverse(o => { if (o.isMesh) o.frustumCulled = true; });
      const q = new Ped(game, av, sex);
      q.baseScale = TARGET_H[sex] / modelH[model];
      q.dress(Math.random); q.idx = i;
      this.peds.push(q);
    }
    this.frame = 0; this.time = 0; this.seeded = false; this.spawnT = 0; this.cullT = 0;
    this.focus = new THREE.Vector3(); this.lastFocus = null;
    this.tramSeen = new Map();
    this.cell = new Map();
    this.fauna = game.assets.models && game.assets.models.fauna ? new Fauna(game, this.w, this.nav, map) : null;
    this.perf = { ms: 0, n: 0 };
  }

  get activeCount() { return this.peds.filter(q => q.state !== 'gone').length; }
  get hour() { return this.g.clock ? this.g.clock.hour : 12; }
  density(h = this.hour) { return lerpTable(DENSITY, h); }
  target() { return Math.round(this.COUNT * this.density()); }

  // ---------------------------------------------------------------- loop paths (rural walkers)
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

  // ---------------------------------------------------------------- spawning
  activate(q, x, z, y) {
    const av = q.av;
    if (av.rag || !q.alive) {
      // recycled body: undo the ragdoll pose
      av.rag = null;
      for (const [b, r] of av.restQ) b.quaternion.copy(r);
      for (const [b, p] of q.restP) b.position.copy(p);
    }
    q.retint(this.rnd);
    q.pos.set(x, y, z); q.vel.set(0, 0, 0);
    q.active = true; q.alive = true; q.hp = 55; q.deadT = 0; q.hitT = 9; q.scared = 0;
    q.speed = 1.15 + this.rnd() * .45 + (this.g.clock && (this.g.clock.between(7, 9.3) || this.g.clock.between(16.8, 18.8)) ? .15 : 0);
    q.lane = .1 + this.rnd() * .35; q.chatCd = 8 + this.rnd() * 20; q.group = null; q.spot = null; q.wps = null; q.goal = null;
    q.acc = 0; q.stateT = 0; q.crossOk = false; q.anim = 'IdleRelaxed'; q.animSpeed = 1; q.partner = null;
    av.mixer.stopAllAction(); av.current = null; av.play('IdleRelaxed', 0);
    this.g.combat.targets.add(q);
    av.root.position.copy(q.pos);
  }

  deactivate(q) {
    this.leaveSpot(q);
    q.state = 'gone'; q.active = false; q.alive = false; q.wps = null; q.goal = null; q.av.rag = null;
    this.g.combat.targets.delete(q);
    if (q.av.root.parent) q.av.root.removeFromParent();
  }

  inView(x, y, z, r = 1.2) { _sph.center.set(x, y + .9, z); _sph.radius = r; return _frus.intersectsSphere(_sph); }

  spawnOne(seed) {
    const q = this.peds.find(p => p.state === 'gone'); if (!q) return false;
    const F = this.focus, r = this.rnd, h = this.hour, nav = this.nav;
    const near2 = (x, z, lo, hi) => { const d = (x - F.x) ** 2 + (z - F.z) ** 2; return d > lo * lo && d < hi * hi; };
    // rural: when the player is out by a village / farm / the spaceport, people stroll the loops there
    if (this.ruralPts.length && r() < .5) {
      for (let k = 0; k < 24; k++) {
        const c = this.ruralPts[Math.floor(r() * this.ruralPts.length)];
        if (!near2(c.x, c.z, seed ? 6 : SPAWN_MIN, SPAWN_MAX)) continue;
        if (!seed && this.inView(c.x, 0, c.z) && Math.hypot(c.x - F.x, c.z - F.z) < VIS_D) continue;
        this.activate(q, c.x, c.z, this.map.height(c.x, c.z));
        q.mode = 'loop'; q.path = c.path; q.s = c.s; q.dir = r() < .5 ? 1 : -1; q.state = 'walk'; q.idleT = 4 + r() * 10;
        return true;
      }
    }
    if (seed && this.seedPlace(q)) return true;
    // out of a door (morning: homes; evening: offices; otherwise anything)
    const P = nav.pois;
    if (r() < .38) {
      const want = h > 5.5 && h < 9.5 ? 'home' : h > 16.5 && h < 19.5 ? 'work' : null;
      for (let k = 0; k < 30; k++) {
        const d = P.door[Math.floor(r() * P.door.length)];
        if (!d || (want && d.kind !== want && r() < .7) || !near2(d.x, d.z, seed ? 8 : 20, SPAWN_MAX)) continue;
        this.activate(q, d.x, d.z, 0); q.mode = 'nav'; q.yaw = Math.atan2(d.n[0], d.n[1]);
        this.planFrom(q, { x: d.ax, z: d.az, node: d.node });
        return true;
      }
    }
    // in from out of view somewhere on the sidewalks
    for (let k = 0; k < 60; k++) {
      const n = nav.nodes[Math.floor(r() * nav.nodes.length)];
      if (!n.main || n.bridge || !near2(n.x, n.z, seed ? 6 : SPAWN_MIN, SPAWN_MAX)) continue;
      if (!seed && this.inView(n.x, n.y, n.z) && Math.hypot(n.x - F.x, n.z - F.z) < VIS_D + 5) continue;
      this.activate(q, n.x + (r() - .5) * .6, n.z + (r() - .5) * .6, n.y); q.mode = 'nav';
      this.planFrom(q, { x: n.x, z: n.z, node: n.id });
      if (seed && q.wps && q.wps.length > 2) {
        // mid-journey: start somewhere along the route
        const k2 = 1 + Math.floor(r() * (q.wps.length - 1)); const w = q.wps[k2 - 1];
        q.pos.set(w.x, w.y, w.z); q.wi = k2;
      }
      return true;
    }
    return false;
  }

  // the crowd at load / after a teleport: some already seated, chatting or browsing
  seedPlace(q) {
    const r = this.rnd, F = this.focus, P = this.nav.pois, roll = r(), h = this.hour;
    const night = h < 6 || h > 22.5;
    const free = (list, test) => { for (let k = 0; k < 40; k++) { const s = list[Math.floor(r() * list.length)]; if (s && test(s) && Math.hypot(s.x - F.x, s.z - F.z) < 200 && Math.hypot(s.x - F.x, s.z - F.z) > 4) return s; } return null; };
    if (roll < (night ? .12 : .26)) {
      const s = free(P.seat, s => !s.by && !this.playerOn(s)); if (!s) return false;
      this.activate(q, s.x, s.z, s.y); q.mode = 'nav'; q.goal = { kind: 'seat', poi: s }; s.by = q; q.spot = s;
      q.state = 'sit'; q.yaw = s.yaw; q.stateT = 10 + r() * 80; q.anim = 'Sit'; q.av.play('Sit', 0);
      return true;
    }
    if (roll < (night ? .2 : .36)) {
      const m = free(P.meet, m => !m.users.length); if (!m) return false;
      const q2 = this.peds.find(p => p.state === 'gone' && p !== q); if (!q2) return false;
      for (const p of [q, q2]) { this.activate(p, m.x, m.z, 0); p.mode = 'nav'; p.goal = { kind: 'meet', poi: m }; m.users.push(p); p.spot = m; }
      this.startTalk(m.users.slice(), m.x, m.z, 8 + r() * 16, m);
      for (const p of m.users) { p.pos.x = p.slot.x; p.pos.z = p.slot.z; }
      return true;
    }
    if (roll < .42 && !night) {
      const w = free(P.window, w => !w.by); if (!w) return false;
      this.activate(q, w.x, w.z, 0); q.mode = 'nav'; q.goal = { kind: 'window', poi: w }; w.by = q; q.spot = w;
      q.state = 'browse'; q.yaw = w.yaw; q.stateT = 4 + r() * 10;
      return true;
    }
    return false;
  }

  playerOn(s) { const p = this.g.player; return p.mode === 'sit' && p.seat && Math.hypot(p.seat.pos.x - s.x, p.seat.pos.z - s.z) < .4; }

  // ---------------------------------------------------------------- goals and routes
  chooseGoal(q) {
    const r = this.rnd, h = this.hour, P = this.nav.pois;
    let kind = rollKind(mixAt(h), r);
    if (q.scared > 0 && r() < .6) kind = 'home';
    const lunch = h > 11.5 && h < 14.2, evening = h > 18.8 && h < 23.5;
    const px = this.g.player.pos.x, pz = this.g.player.pos.z;
    const score = (p, dmin = 12, dmax = 230) => {
      const d = Math.hypot(p.x - q.pos.x, p.z - q.pos.z);
      if (d < dmin || d > dmax * 1.4) return 0;
      let w = d > dmax ? .25 : 1;
      w *= 1 + 1.5 * Math.exp(-Math.hypot(p.x - px, p.z - pz) / 110);          // life where the player is
      if (evening && (p.heritage || p.dt)) w *= p.heritage ? 4 : 2;
      if (lunch && p.dt) w *= 2;
      return w;
    };
    const best = (list, ok, dmin, dmax, bias) => {
      let tot = 0; const c = [];
      for (const p of list) { if (!ok(p)) continue; let w = score(p, dmin, dmax); if (bias) w *= bias(p); if (w > 0) { c.push([p, w]); tot += w; } }
      let x = r() * tot; for (const [p, w] of c) { x -= w; if (x <= 0) return p; }
      return null;
    };
    let poi = null;
    if (kind === 'seat') poi = best(P.seat, s => !s.by && !this.playerOn(s), 8, 200, s => (s.kind === 'cafe' ? (lunch || evening ? 3 : 1.2) : 1) * (this.partnerAt(s) ? 3 : 1));
    else if (kind === 'kiosk') poi = best(P.kiosk, k => k.users.some(u => !u), 10, 220);
    else if (kind === 'window') poi = best(P.window, w => !w.by, 10, 200);
    else if (kind === 'platform') poi = best(P.platform, p => !p.by, 20, 320);
    else if (kind === 'meet') poi = best(P.meet, m => m.users.length < 3, 10, 200, m => m.users.length === 1 ? 8 : m.users.length === 2 ? 2 : 1);
    else if (DOOR_OF[kind]) poi = best(P.door, d => DOOR_OF[kind].includes(d.kind), 25, 300);
    if (!poi) {
      kind = 'wander';
      const n = this.nav.nodes;
      for (let k = 0; k < 40 && !poi; k++) {
        const c = n[Math.floor(r() * n.length)];
        const d = Math.hypot(c.x - q.pos.x, c.z - q.pos.z);
        if (c.main && d > 40 && d < 200 && Math.hypot(c.x - px, c.z - pz) < 280) poi = { x: c.x, z: c.z, node: c.id, wander: true };
      }
      if (!poi) return null;
    }
    // reserve single spots now so two people do not head for the same chair
    if (kind === 'seat' || kind === 'window' || kind === 'platform') poi.by = q;
    if (kind === 'kiosk') { const i = poi.users.indexOf(null); poi.users[i] = q; q.qi = i; }
    if (kind === 'meet') poi.users.push(q);
    if (kind !== 'wander') q.spot = poi;
    return { kind, poi };
  }

  partnerAt(s) {
    // someone already sitting across the table / on the other half of the bench
    for (const o of s.nb || []) if (o.by && o.by.state === 'sit') return o.by;
    return null;
  }

  // release whatever spot this person holds (seat, window, platform, kiosk queue place, meeting point, talk group)
  leaveSpot(q) {
    const s = q.spot;
    if (s) {
      if (s.by === q) s.by = null;
      if (s.users) { const i = s.users.indexOf(q); if (i >= 0) { if (s.q) s.users[i] = null; else s.users.splice(i, 1); } }
      q.spot = null;
    }
    if (q.group) {
      const G = q.group; G.members = G.members.filter(m => m !== q); q.group = null;
      if (G.members.length < 2) this.endTalk(G);
    }
  }

  // plan a route from (where the person stands, or a start node) to a fresh goal
  planFrom(q, start = null) {
    const nav = this.nav;
    q.goal = this.chooseGoal(q);
    if (!q.goal) { q.state = 'idle'; q.stateT = 3 + this.rnd() * 5; return; }
    const a = start ? start.node : nav.nearest(q.pos.x, q.pos.z, 60, n => n.main);
    const g = q.goal.poi, b = g.node;
    const route = a >= 0 && b >= 0 ? nav.path(a, b) : null;
    if (!route) { this.leaveSpot(q); q.goal = null; q.state = 'idle'; q.stateT = 2 + this.rnd() * 4; return; }
    const W = [];
    if (start) W.push({ x: start.x, z: start.z, y: q.pos.y, off: false });
    let prev = null;
    for (const id of route) {
      const n = nav.nodes[id], e = prev !== null ? nav.edge(prev, id) : null;
      W.push({ x: n.x, z: n.z, y: n.y, cross: e && e.cross, off: !n.plaza && !n.bridge });
      prev = id;
    }
    // the last stretch off the graph: to the seat / window / queue / door / platform spot
    const k = q.goal.kind;
    if (k === 'seat') W.push({ x: g.ax, z: g.az, y: g.y > .05 ? 0 : g.y, off: false, end: true });
    else if (k === 'kiosk') { const p = g.q[2]; W.push({ x: p[0], z: p[1], y: 0, off: false, end: true }); }
    else if (k === 'window' || k === 'platform') W.push({ x: g.x, z: g.z, y: g.y || 0, off: false, end: true });
    else if (k === 'meet') W.push({ x: g.x, z: g.z, y: 0, off: false, end: true });
    else if (DOOR_OF[k]) { W.push({ x: g.ax, z: g.az, y: 0, off: false }); W.push({ x: g.x, z: g.z, y: 0, off: false, end: true, door: true }); }
    else W[W.length - 1].end = true;
    q.wps = W; q.wi = 0; q.state = 'walk'; q.crossOk = false;
  }

  // ---------------------------------------------------------------- talking
  startTalk(members, cx, cz, dur, meet = null) {
    const G = { members, cx, cz, until: this.time + dur, speaker: 0, swapT: 0, meet };
    const n = members.length, a0 = this.rnd() * Math.PI * 2, R = n > 2 ? .72 : .58;
    members.forEach((m, i) => {
      m.group = G; m.state = 'talk'; m.stateT = 0;
      const a = a0 + i / n * Math.PI * 2;
      m.slot = { x: cx + Math.cos(a) * R, z: cz + Math.sin(a) * R };
    });
    this.groups.push(G);
    return G;
  }

  endTalk(G) {
    const i = this.groups.indexOf(G); if (i >= 0) this.groups.splice(i, 1);
    for (const m of G.members) {
      m.group = null; m.chatCd = 50 + this.rnd() * 60;
      if (G.meet) { this.leaveSpot(m); this.planFrom(m); }
      else if (m.wps && m.wi < m.wps.length) m.state = 'walk';
      else this.planFrom(m);
    }
    G.members = [];
  }

  // ---------------------------------------------------------------- events
  alarm(pos, radius, from = null) {
    for (const q of this.peds) if (q.alive && q.state !== 'gone' && q.pos.distanceTo(pos) < radius) q.flee(from || pos);
    if (this.fauna) this.fauna.scare(pos, radius * 1.2);
  }

  // walk with collision (fleeing, returning to the sidewalk): slide around walls instead of passing through them
  move(q, dir, speed, dt) {
    const col = this.g.world.collision;
    q.vel.set(dir.x * speed, -9, dir.z * speed);
    const x0 = q.pos.x, z0 = q.pos.z;
    col.moveCapsule(q.pos, q.vel, .3, 1.7, dt);
    const moved = Math.hypot(q.pos.x - x0, q.pos.z - z0);
    return moved > speed * dt * .4;
  }

  // a gap in the traffic on the road this crossing spans
  roadClear(cross, x, z) {
    const V = this.g.vehicles;
    for (const c of V.cars) {
      if (!c.pos) continue;
      const v = V.carVel(c);
      // along: distance along the road from the crossing; side: across the road
      const along = cross.ax === 'x' ? c.pos.z - z : c.pos.x - x, side = cross.ax === 'x' ? c.pos.x - cross.c : c.pos.z - cross.c;
      if (Math.abs(side) > 11 || Math.abs(along) > 60) continue;
      const va = cross.ax === 'x' ? v.z : v.x;
      if (Math.abs(along) < 6.5) return false;
      if (along * va < 0 && Math.abs(along) < 7 + Math.abs(va) * 3.4) return false;
    }
    return true;
  }

  // ---------------------------------------------------------------- per frame
  update(dt) {
    const t0 = performance.now();
    const g = this.g, P = g.player;
    const F = this.focus.copy(P.mode === 'car' && g.vehicles.current ? g.vehicles.current.pos : P.pos);
    this.frame++; this.time += dt;
    const cam = g.camera;
    cam.updateMatrixWorld(); _pm.multiplyMatrices(cam.projectionMatrix, cam.matrixWorldInverse); _frus.setFromProjectionMatrix(_pm);
    // first frame or a teleport: lay the crowd out around the player at once
    if (!this.seeded || (this.lastFocus && this.lastFocus.distanceTo(F) > 150)) {
      for (const q of this.peds) if (q.state !== 'gone') this.deactivate(q);
      for (const G of this.groups.slice()) this.endTalk(G);
      const n = this.target();
      for (let i = 0; i < n * 3 && this.activeCount < n; i++) this.spawnOne(true);
      this.seeded = true;
    }
    this.lastFocus = (this.lastFocus || new THREE.Vector3()).copy(F);
    this.manageCrowd(dt);
    this.tramStops();
    // neighbour grid (separation, chance meetings) for the people near the player
    const cell = this.cell; cell.clear();
    for (const q of this.peds) {
      if (q.state === 'gone' || !q.alive) continue;
      q.d = Math.hypot(q.pos.x - F.x, q.pos.z - F.z);
      if (q.d < 70) { const k = Math.floor(q.pos.x / 2) * 7919 + Math.floor(q.pos.z / 2); let l = cell.get(k); if (!l) cell.set(k, l = []); l.push(q); }
    }
    for (const G of this.groups.slice()) {
      if (this.time > G.until) { this.endTalk(G); continue; }
      G.swapT -= dt; if (G.swapT <= 0) { G.speaker = (G.speaker + 1 + Math.floor(this.rnd() * (G.members.length - 1))) % G.members.length; G.swapT = 2 + this.rnd() * 3.5; }
    }
    const scene = this.scene;
    for (let i = 0; i < this.peds.length; i++) {
      const q = this.peds[i];
      if (q.state === 'gone') continue;
      const d = q.alive ? q.d : q.pos.distanceTo(F);
      // throttle: think + move every frame near, every 3rd / 8th / 20th frame further out
      const every = d < 50 ? 1 : d < 120 ? 3 : d < 220 ? 8 : 20;
      q.acc += dt; q.animAcc = (q.animAcc || 0) + dt;
      if ((i + this.frame) % every) { this.animate(q, d); continue; }
      const step = Math.min(q.acc, .7); q.acc = 0;
      if (!q.alive) {
        q.deadT += step;
        if (q.deadT > 25 && d > 120 && !this.inView(q.pos.x, q.pos.y, q.pos.z, 2)) { this.deactivate(q); continue; }
        q.lod(d, scene); if (d < 60) q.av.update(step); continue;
      }
      q.hitT += step; q.chatCd -= step; q.scared -= step;
      // every car is solid; a hit above ~6 m/s runs people over (only near the player, where it can be seen)
      if (d < 120 && q.state !== 'sit' && q.state !== 'settle') {
        const hit = g.vehicles.pedContact(q);
        if (hit) {
          const hitBy = hit.car, hv = g.vehicles.carVel(hitBy), dir = new THREE.Vector3(hv.x, 0, hv.z).normalize();
          g.fx.blood && g.fx.blood(_v.copy(q.pos).setY(q.pos.y + 1), dir.clone().setY(.4), 1.6);
          q.die(hitBy === g.vehicles.current, dir.setY(.5).multiplyScalar(Math.min(14, hit.speed * .6)));
          if (hitBy.traffic) hitBy.traffic.hitSomeone(hitBy);
          this.alarm(q.pos, 35, hitBy.pos); continue;
        }
      }
      if (q.mode === 'loop') this.stepLoop(q, step, d);
      else this.stepNav(q, step, d);
      if (q.state === 'gone') continue;
      q.av.root.position.copy(q.pos); q.av.root.rotation.y = q.yaw;
      q.lod(d, scene);
      this.animate(q, d);
    }
    if (this.fauna) this.fauna.update(dt, F, _frus);
    this.perf.ms += performance.now() - t0; this.perf.n++;
  }

  // skinned animation only for people in view (or close by), at a lower rate with distance
  animate(q, d) {
    const av = q.av;
    if (!q.alive || !av.root.visible) return;
    const rate = d < 30 ? 1 : d < 70 ? 2 : 4;
    if ((this.frame + (q.idx || 0)) % rate) return;
    if (d > 12 && !this.inView(q.pos.x, q.pos.y, q.pos.z, 1.3)) return;
    const a = Math.min(q.animAcc, .5); q.animAcc = 0;
    av.play(q.anim || 'IdleRelaxed', .3, q.animSpeed || 1);
    av.update(a);
    if (d < 32 && (q.group || q.state === 'sit' && q.partner && q.partner.state === 'sit') && a > 0) this.gesture(q);
  }

  // talk: turn the head to the partner, nod, and the speaker gestures with a hand
  gesture(q) {
    const av = q.av, G = q.group, t = this.time + (q.idx || 0) * 1.7;
    let tx, tz, speaking;
    if (G) { const me = G.members.indexOf(q); speaking = G.members[G.speaker] === q; const o = G.members[(me + 1) % G.members.length]; tx = o.pos.x; tz = o.pos.z; if (G.members.length > 2 && !speaking) { const s = G.members[G.speaker]; tx = s.pos.x; tz = s.pos.z; } }
    else { const o = q.partner; tx = o.pos.x; tz = o.pos.z; speaking = Math.sin(t * .45 + (q.idx || 0)) > 0; }
    const yaw = q.yaw, right = _h.set(Math.cos(yaw), 0, -Math.sin(yaw));
    const look = THREE.MathUtils.clamp(wrapA(Math.atan2(tx - q.pos.x, tz - q.pos.z) - yaw), -.7, .7);
    av.root.updateMatrixWorld(true);
    bend(av, av.head, UP, look * .8);
    bend(av, av.head, right, (speaking ? .05 : .09) * Math.sin(t * (speaking ? 3.1 : 1.3)) - .04);
    if (speaking) {
      const k = .5 + .5 * Math.sin(t * 1.7), side = Math.sin(t * .37 + (q.idx || 0)) > 0 ? 'R' : 'L';
      const up = av.bones['upperarm' + side], fore = av.bones['forearm' + side];
      bend(av, up, right, -(.25 + .2 * k));
      bend(av, fore, right, -(.6 + .35 * k + .12 * Math.sin(t * 4.3)));
    } else bend(av, av.chest || av.spine, UP, look * .15);
  }

  // ---------------------------------------------------------------- city walkers
  stepNav(q, dt, d) {
    const g = this.g, r = this.rnd, near = d < 60;
    q.anim = 'IdleRelaxed'; q.animSpeed = 1;
    if (g.player.aiming && near && d < 14 && q.state !== 'flee' && q.state !== 'return') q.flee(g.player.pos);
    switch (q.state) {
      case 'flee': {
        q.fleeT -= dt; q.anim = 'RunRelaxed'; q.animSpeed = .95;
        if (!this.move(q, q.fleeDir, 4.6, dt)) { const s2 = r() < .5 ? 1 : -1; q.fleeDir.set(-q.fleeDir.z * s2, 0, q.fleeDir.x * s2); }
        q.yaw = Math.atan2(q.fleeDir.x, q.fleeDir.z);
        if (q.fleeT <= 0) {
          q.state = 'return';
          q.retNode = this.nav.nearest(q.pos.x, q.pos.z, 70, n => n.main);
          if (q.retNode < 0) { if (d > 60 || !this.inView(q.pos.x, q.pos.y, q.pos.z)) this.deactivate(q); else { q.state = 'idle'; q.stateT = 6; } }
        }
        return;
      }
      case 'return': {
        const n = this.nav.nodes[q.retNode];
        _h.set(n.x - q.pos.x, 0, n.z - q.pos.z); const L = _h.length();
        q.anim = 'WalkRelaxed';
        if (L < .8 || !this.move(q, _h.divideScalar(Math.max(L, 1e-3)), q.speed * 1.2, dt)) { q.pos.y = n.y; this.planFrom(q, { x: q.pos.x, z: q.pos.z, node: n.id }); }
        else q.yaw = Math.atan2(_h.x, _h.z);
        return;
      }
      case 'walk': this.walk(q, dt, d); return;
      case 'wait': {
        // at the kerb: a gap in the traffic (or tired of waiting)
        q.stateT -= dt;
        const w = q.wps[q.wi], p = q.wps[q.wi - 1] || w;
        q.yaw = Math.atan2(w.x - p.x, w.z - p.z);
        q.waitT = (q.waitT || 0) + dt;
        if (q.stateT <= 0) { q.stateT = .4; if (d > 140 || q.waitT > 22 || this.roadClear(w.cross, p.x, p.z)) { q.crossOk = true; q.state = 'walk'; q.waitT = 0; } }
        return;
      }
      case 'idle': case 'browse': case 'queue': case 'platform': case 'meetwait':
        this.linger(q, dt, d); return;
      case 'talk': {
        // step into place in the circle, then face the middle
        const G = q.group; if (!G) { q.state = 'walk'; return; }
        _h.set(q.slot.x - q.pos.x, 0, q.slot.z - q.pos.z); const L = _h.length();
        if (L > .12) { q.anim = 'WalkRelaxed'; q.animSpeed = .7; const s = Math.min(L, dt * .9); q.pos.x += _h.x / L * s; q.pos.z += _h.z / L * s; q.yaw = Math.atan2(_h.x, _h.z); }
        else q.yaw = turn(q.yaw, Math.atan2(G.cx - q.pos.x, G.cz - q.pos.z), dt * 3);
        return;
      }
      case 'settle': case 'rise': {
        // ease into / out of a seat
        const s = q.spot; q.stateT += dt;
        const k = Math.min(1, q.stateT / .7), e = k * k * (3 - 2 * k);
        if (!s) { q.state = 'idle'; q.stateT = 1; return; }
        if (q.state === 'settle') {
          q.pos.set(s.ax + (s.x - s.ax) * e, s.y * e, s.az + (s.z - s.az) * e); q.yaw = turn(q.yaw, s.yaw, dt * 6); q.anim = 'Sit';
          if (k >= 1) { q.state = 'sit'; q.yaw = s.yaw; q.stateT = this.sitTime(s); q.partner = this.partnerAt(s); }
        } else {
          q.pos.set(s.x + (s.ax - s.x) * e, s.y * (1 - e), s.z + (s.az - s.z) * e);
          if (k >= 1) { this.leaveSpot(q); q.pos.y = 0; this.planFrom(q); }
        }
        return;
      }
      case 'sit': {
        q.anim = 'Sit'; q.stateT -= dt;
        const s = q.spot;
        // the player took this seat (or a close neighbour talks to us)
        if (s && this.playerOn(s)) q.stateT = 0;
        if (q.stateT % 3 < dt) q.partner = s ? this.partnerAt(s) : null;
        if (q.stateT <= 0) { q.state = 'rise'; q.stateT = 0; q.partner = null; }
        return;
      }
      case 'board': {
        // step toward the tram doors, then gone
        q.anim = 'WalkRelaxed'; q.stateT -= dt;
        const tz = TRANSIT.z + q.spot.side * 3.6;
        q.pos.z += Math.sign(tz - q.pos.z) * Math.min(Math.abs(tz - q.pos.z), dt * 1.2); q.yaw = q.spot.side < 0 ? 0 : Math.PI;
        if (q.stateT <= 0 || Math.abs(tz - q.pos.z) < .05) this.deactivate(q);
        return;
      }
      default: q.state = 'idle'; q.stateT = 2;
    }
  }

  sitTime(s) { const h = this.hour, lunch = h > 11.5 && h < 14.2, eve = h > 19 && h < 23.5; return (s.kind === 'cafe' ? (lunch || eve ? 50 : 30) : 25) + this.rnd() * (s.kind === 'cafe' ? 70 : 50); }

  walk(q, dt, d) {
    const W = q.wps; if (!W) { this.planFrom(q); return; }
    let w = W[q.wi];
    if (!w) { this.arrive(q); return; }
    // about to step onto a road: wait for a gap
    if (w.cross && !q.crossOk) { q.state = 'wait'; q.stateT = .2 + this.rnd() * .5; q.waitT = 0; return; }
    const prev = W[q.wi - 1];
    // keep to the right of the sidewalk, a little apart from the next person
    let tx = w.x, tz = w.z;
    if (w.off && prev) { const sx = w.x - prev.x, sz = w.z - prev.z, L = Math.hypot(sx, sz) || 1; tx += sz / L * -q.lane; tz += -sx / L * -q.lane; }
    let dx = tx - q.pos.x, dz = tz - q.pos.z, L = Math.hypot(dx, dz);
    if (L < (w.end ? .25 : .7)) {
      q.wi++; if (w.cross) q.crossOk = false;
      if (q.wi >= W.length) { this.arrive(q); return; }
      return;
    }
    let vx = dx / L * q.speed, vz = dz / L * q.speed;
    if (d < 60) { const s = this.steer(q, vx, vz); vx = s[0]; vz = s[1]; }
    const sp = Math.hypot(vx, vz);
    const stp = Math.min(L, sp * dt);
    if (sp > 1e-3) { q.pos.x += vx / sp * stp; q.pos.z += vz / sp * stp; }
    if (prev) { const seg = Math.hypot(w.x - prev.x, w.z - prev.z) || 1, k = 1 - Math.min(1, Math.hypot(w.x - q.pos.x, w.z - q.pos.z) / seg); q.pos.y = prev.y + (w.y - prev.y) * k; }
    if (sp > .05) q.yaw = turn(q.yaw, Math.atan2(vx, vz), dt * 6);
    q.anim = 'WalkRelaxed'; q.animSpeed = THREE.MathUtils.clamp(sp / 1.35, .7, 1.25);
  }

  // local avoidance: push apart, pass on the right, make way for the player; sometimes stop for a chat
  steer(q, vx, vz) {
    const fx = Math.sin(q.yaw), fz = Math.cos(q.yaw);
    let ax = 0, az = 0;
    const ix = Math.floor(q.pos.x / 2), iz = Math.floor(q.pos.z / 2);
    for (let a = ix - 1; a <= ix + 1; a++) for (let b = iz - 1; b <= iz + 1; b++) {
      const l = this.cell.get(a * 7919 + b); if (!l) continue;
      for (const o of l) {
        if (o === q) continue;
        const rx = o.pos.x - q.pos.x, rz = o.pos.z - q.pos.z, dd = Math.hypot(rx, rz);
        if (dd > 2.6 || dd < 1e-3) continue;
        if (dd < .85) { const k = (.85 - dd) / .85 * 1.6; ax -= rx / dd * k; az -= rz / dd * k; }
        const ahead = rx * fx + rz * fz, lat = rx * fz - rz * fx;
        if (ahead > 0 && ahead < 2.4 && Math.abs(lat) < .8) {
          // pass on the right (right of facing = (fz, -fx))
          const k = (1 - ahead / 2.4) * .7; ax += fz * k; az -= fx * k;
          if (o.state === 'walk' && q.social && o.social && q.chatCd <= 0 && o.chatCd <= 0 && dd < 2.2 && (Math.sin(o.yaw) * fx + Math.cos(o.yaw) * fz) < -.6
            && !(q.wps[q.wi] && q.wps[q.wi].cross) && !(o.wps && o.wps[o.wi] && o.wps[o.wi].cross)) {
            q.chatCd = o.chatCd = 45;
            if (this.rnd() < .35) { this.startTalk([q, o], (q.pos.x + o.pos.x) / 2, (q.pos.z + o.pos.z) / 2, 10 + this.rnd() * 6); return [0, 0]; }
          }
        }
      }
    }
    const P = this.g.player;
    if (P.mode === 'foot') {
      const rx = P.pos.x - q.pos.x, rz = P.pos.z - q.pos.z, dd = Math.hypot(rx, rz);
      if (dd < 1.0 && dd > 1e-3) { const k = (1 - dd) * 2.2; ax -= rx / dd * k; az -= rz / dd * k; }
      else if (dd < 3) { const ahead = rx * fx + rz * fz, lat = rx * fz - rz * fx; if (ahead > 0 && Math.abs(lat) < .9) { const k = (1 - ahead / 3) * .9 * (lat > 0 ? -1 : 1); ax += fz * k; az -= fx * k; } }
    }
    return [vx + ax, vz + az];
  }

  // at the end of the route: sit down, queue, browse, wait for a tram, meet friends, go through a door
  arrive(q) {
    const G = q.goal, r = this.rnd;
    if (!G) { this.planFrom(q); return; }
    const p = G.poi;
    switch (G.kind) {
      case 'seat':
        if (p.by && p.by !== q || this.playerOn(p)) { this.leaveSpot(q); this.planFrom(q); return; }
        p.by = q; q.state = 'settle'; q.stateT = 0; return;
      case 'kiosk': q.state = 'queue'; q.stateT = 0; return;
      case 'window': q.state = 'browse'; q.yaw = p.yaw; q.stateT = 5 + r() * 12; return;
      case 'platform': q.state = 'platform'; q.yaw = p.yaw; q.stateT = 60 + r() * 50; q.since = 0; q.pos.y = p.y; return;
      case 'meet': {
        const others = p.users.filter(u => u !== q && u.state === 'meetwait' || u !== q && u.group && u.group.meet === p);
        if (others.length) {
          const grp = others.find(u => u.group) && others.find(u => u.group).group;
          if (grp && grp.members.length < 3) {
            grp.members.push(q); q.group = grp; q.state = 'talk';
            const n = grp.members.length; grp.members.forEach((m, i) => { const a = i / n * Math.PI * 2; m.slot = { x: grp.cx + Math.cos(a) * .72, z: grp.cz + Math.sin(a) * .72 }; });
            grp.until = Math.max(grp.until, this.time + 8 + r() * 8);
          } else this.startTalk([...others.filter(u => !u.group), q], p.x, p.z, 12 + r() * 16, p);
        } else { q.state = 'meetwait'; q.stateT = 18 + r() * 20; }
        return;
      }
      case 'wander': q.state = 'idle'; q.stateT = r() < .5 ? 2 + r() * 6 : 0; return;
      default:
        if (DOOR_OF[G.kind]) { this.deactivate(q); return; }
        this.planFrom(q);
    }
  }

  // standing still: browsing, queueing, waiting for a tram or for friends
  linger(q, dt, d) {
    q.stateT -= dt; q.anim = 'IdleRelaxed';
    const p = q.spot;
    if (q.state === 'queue' && p) {
      // move up the queue; the first in line is served after a few seconds
      let i = p.users.indexOf(q);
      if (i < 0) { this.leaveSpot(q); this.planFrom(q); return; }
      if (i > 0 && !p.users[i - 1]) { p.users[i - 1] = q; p.users[i] = null; i--; q.stateT = 0; }
      const spot = p.q[i];
      _h.set(spot[0] - q.pos.x, 0, spot[1] - q.pos.z); const L = _h.length();
      if (L > .1) { q.anim = 'WalkRelaxed'; q.animSpeed = .8; const s = Math.min(L, dt * 1.1); q.pos.x += _h.x / L * s; q.pos.z += _h.z / L * s; q.yaw = Math.atan2(_h.x, _h.z); return; }
      q.yaw = turn(q.yaw, p.yaw, dt * 4);
      if (i === 0) { q.served = (q.served || 0) + dt; if (q.served > 5 + this.rnd() * 6) { q.served = 0; this.leaveSpot(q); this.afterSnack(q); } }
      return;
    }
    if (q.state === 'platform' && p) {
      const tram = (this.w.downtown && this.w.downtown.trams || []).find(t => t.wait > 1 && Math.abs(t.x - p.station) < 1 && Math.sign(t.lane) === p.side);
      q.since = (q.since || 0) + dt;
      if (tram && q.since > 3) { q.state = 'board'; q.stateT = 3.5; return; }
      if (q.stateT <= 0) { this.leaveSpot(q); this.planFrom(q); }
      return;
    }
    if (q.state === 'meetwait') {
      // look around for the friend
      q.yaw += Math.sin(this.time * .5 + (q.idx || 0)) * dt * .4;
      if (q.stateT <= 0) { this.leaveSpot(q); this.planFrom(q); }
      return;
    }
    if (q.stateT <= 0) { this.leaveSpot(q); this.planFrom(q); }
  }

  // after buying food: sit down nearby to eat, or walk on
  afterSnack(q) {
    const P = this.nav.pois.seat;
    let best = null, bd = 45;
    for (const s of P) { if (s.by || this.playerOn(s)) continue; const dd = Math.hypot(s.x - q.pos.x, s.z - q.pos.z); if (dd < bd && dd > 2) { bd = dd; best = s; } }
    if (best && this.rnd() < .75) {
      const a = this.nav.nearest(q.pos.x, q.pos.z, 40, n => n.main), route = a >= 0 ? this.nav.path(a, best.node) : null;
      if (route) {
        best.by = q; q.spot = best; q.goal = { kind: 'seat', poi: best };
        q.wps = [...route.map(id => { const n = this.nav.nodes[id]; return { x: n.x, z: n.z, y: n.y, off: !n.plaza }; }), { x: best.ax, z: best.az, y: 0, end: true }];
        for (let i = 1; i < route.length; i++) { const e = this.nav.edge(route[i - 1], route[i]); if (e && e.cross) q.wps[i].cross = e.cross; }
        q.wi = 0; q.state = 'walk'; q.crossOk = false; return;
      }
    }
    this.planFrom(q);
  }

  // villages, farms, spaceport: stroll the loop paths with pauses
  stepLoop(q, step, d) {
    const g = this.g;
    let speed = q.speed;
    q.anim = 'WalkRelaxed'; q.animSpeed = 1;
    if (q.state === 'flee') {
      q.fleeT -= step; speed = 4.6; q.anim = 'RunRelaxed'; q.animSpeed = .95;
      if (!this.move(q, q.fleeDir, speed, step)) { const s2 = Math.random() < .5 ? 1 : -1; q.fleeDir.set(-q.fleeDir.z * s2, 0, q.fleeDir.x * s2); }
      q.yaw = Math.atan2(q.fleeDir.x, q.fleeDir.z);
      if (q.fleeT <= 0) {
        q.state = 'return';
        let best = 0, bd = 1e9;
        for (let s = 0; s < q.path.total; s += 4) { this.pointOn(q.path, s, _h); const dd = _h.distanceTo(q.pos); if (dd < bd) { bd = dd; best = s; } }
        q.s = best;
      }
    } else if (q.state === 'return') {
      this.pointOn(q.path, q.s, _h);
      _h.sub(q.pos).setY(0); const L = _h.length();
      if (L < .8) q.state = 'walk';
      else { _h.divideScalar(L); if (!this.move(q, _h, speed * 1.2, step)) { q.state = 'walk'; } q.yaw = Math.atan2(_h.x, _h.z); }
    } else if (q.state === 'idle') {
      q.idleT -= step; q.anim = 'IdleRelaxed';
      if (q.idleT <= 0) { q.state = 'walk'; q.idleT = 6 + Math.random() * 14; }
    } else {
      q.s += q.dir * speed * step;
      const yaw = this.pointOn(q.path, q.s, _h);
      q.pos.x += (_h.x - q.pos.x) * Math.min(1, step * 3); q.pos.z += (_h.z - q.pos.z) * Math.min(1, step * 3);
      q.yaw = yaw + (q.dir < 0 ? Math.PI : 0);
      q.idleT -= step;
      if (q.idleT <= 0) { q.state = 'idle'; q.idleT = 2 + Math.random() * 4; }
      if (d < 60) {
        const pd = Math.hypot(q.pos.x - g.player.pos.x, q.pos.z - g.player.pos.z);
        if (pd < .9 && g.player.mode === 'foot') { q.pos.x += (q.pos.x - g.player.pos.x) / pd * .05; q.pos.z += (q.pos.z - g.player.pos.z) / pd * .05; }
        if (g.player.aiming && pd < 14) q.flee(g.player.pos);
      }
    }
    if (q.state !== 'flee' && q.state !== 'return') q.pos.y = this.map.height(q.pos.x, q.pos.z);
  }

  // ---------------------------------------------------------------- crowd size
  manageCrowd(dt) {
    const F = this.focus, tgt = this.target();
    let active = 0; for (const q of this.peds) if (q.state !== 'gone') active++;
    // far behind the player: back into the pool (they are out of sight)
    for (const q of this.peds) {
      if (q.state === 'gone') continue;
      const d = Math.hypot(q.pos.x - F.x, q.pos.z - F.z);
      if (d > RECYCLE_D && q.alive) { this.deactivate(q); active--; }
    }
    // too many for the hour: a few quietly leave (out of view only)
    this.cullT -= dt;
    if (active > tgt * 1.08 + 2 && this.cullT <= 0) {
      this.cullT = .35;
      let cand = null, cd = 0;
      for (const q of this.peds) {
        if (q.state === 'gone' || !q.alive || q.group || q.state === 'sit') continue;
        const d = Math.hypot(q.pos.x - F.x, q.pos.z - F.z);
        if ((d > VIS_D || !this.inView(q.pos.x, q.pos.y, q.pos.z, 1.5)) && d > 40 && d > cd) { cd = d; cand = q; }
      }
      if (cand) { this.deactivate(cand); active--; }
    }
    // too few: bring people in (doors, out of view, off trams)
    this.spawnT -= dt;
    if (active < tgt && this.spawnT <= 0) {
      this.spawnT = this.g.touch ? .25 : .12;
      for (let k = 0; k < 2 && active < tgt; k++) if (this.spawnOne(false)) active++;
    }
  }

  // trams arriving at a station let a few people off
  tramStops() {
    const dt = this.w.downtown; if (!dt || !dt.trams) return;
    const F = this.focus;
    for (const t of dt.trams) {
      const was = this.tramSeen.get(t) || 0;
      this.tramSeen.set(t, t.wait);
      if (!(t.wait > 0 && was <= 0)) continue;
      const st = (dt.stations || []).find(s => Math.abs(s - t.x) < 1); if (st === undefined) continue;
      if (Math.hypot(t.x - F.x, TRANSIT.z - F.z) > SPAWN_MAX) continue;
      const side = Math.sign(t.lane), n = Math.round((1 + this.rnd() * 3) * this.density());
      for (let k = 0; k < n; k++) {
        const q = this.peds.find(p => p.state === 'gone'); if (!q) break;
        this.activate(q, t.x + (this.rnd() - .5) * 26, TRANSIT.z + side * 5.6, .35); q.mode = 'nav';
        q.yaw = side < 0 ? Math.PI : 0;
        const node = this.nav.nearest(q.pos.x, TRANSIT.z + side * 8.6, 15, m => m.avenue === 'transit');
        if (node < 0) { this.deactivate(q); break; }
        this.planFrom(q, { x: q.pos.x, z: TRANSIT.z + side * 7.6, node });
      }
    }
  }

  // ---------------------------------------------------------------- tests / debugging
  stats() {
    const st = {}, F = this.focus;
    let near = 0;
    for (const q of this.peds) { st[q.state] = (st[q.state] || 0) + 1; if (q.state !== 'gone' && q.pos.distanceTo(F) < 80) near++; }
    const goals = {}; for (const q of this.peds) if (q.goal && q.state !== 'gone') goals[q.goal.kind] = (goals[q.goal.kind] || 0) + 1;
    return { hour: +this.hour.toFixed(2), target: this.target(), active: this.activeCount, near80: near, states: st, goals, groups: this.groups.length,
      talkers: this.groups.reduce((a, G) => a + G.members.length, 0), perfMs: this.perf.n ? +(this.perf.ms / this.perf.n).toFixed(3) : 0 };
  }

  clear() {
    for (const q of this.peds) { this.g.combat.targets.delete(q); q.av.dispose(); }
    if (this.fauna) this.fauna.dispose();
  }
}

function turn(a, b, k) { return a + wrapA(b - a) * Math.min(1, k); }
