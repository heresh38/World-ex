// Small city life for New Meridian: flocks of pigeons and sparrows pecking on the plazas, park lawns and the heritage
// avenue, and a few stray cats by the alley mouths. Models from tools/blender/fauna.py (fauna.glb).
//  Birds: one InstancedMesh per species; the wings fold, spread and flap and the head pecks in the vertex shader
//    (`_wing` / `_head` vertex attributes, per-instance aBird = spread, wing angle, peck). They peck, walk and hop,
//    burst up when the player runs or drives close or a shot is fired, fly to a rooftop, and drift back down later.
//    Flocks live around the player and are re-placed out of sight; at night they roost (none on the ground).
//  Cats: skinned clones (clips Idle, Look, Sit, Walk, Run) that sit, groom and slink along the building line, and bolt
//    into the nearest alley when approached; eyeshine at night.
import * as THREE from 'three';
import { PITCH, CITY_N, CITY_EDGE, HERITAGE } from './layout.js';
import { mulberry } from '../../game/state.js';

const _m = new THREE.Matrix4(), _q = new THREE.Quaternion(), _e = new THREE.Euler(0, 0, 0, 'YXZ'), _p = new THREE.Vector3(), _s = new THREE.Vector3();
const _sph = new THREE.Sphere();
const SPECIES = { pigeon: { mesh: 'BIRD_pigeon', S: 1, scale: [.95, 1.1] }, sparrow: { mesh: 'BIRD_sparrow', S: .55, scale: [.9, 1.1] } };
const wrapA = a => Math.atan2(Math.sin(a), Math.cos(a));
const sstep = x => x <= 0 ? 0 : x >= 1 ? 1 : x * x * (3 - 2 * x);

function birdMaterial(src, S) {
  const m = src.clone();
  m.vertexColors = true; m.roughness = .8; m.metalness = 0;
  m.onBeforeCompile = sh => {
    sh.vertexShader = sh.vertexShader
      .replace('#include <common>', `#include <common>
attribute float _wing; attribute float _head; attribute vec3 aBird;`)
      .replace('#include <begin_vertex>', `#include <begin_vertex>
{
  float S = ${S.toFixed(3)};
  vec3 p = transformed;
  if (_wing > .001) {
    float sx = sign(p.x), sh = .035 * S, dx = max(abs(p.x) - sh, 0.), span = clamp(dx / (.27 * S), 0., 1.);
    // folded: laid back along the flank; spread: rotated about the body axis by the wing angle (tips bend more)
    vec3 fold = vec3(sx * (sh + dx * .2), p.y + dx * .12, p.z - dx * .78);
    float a = aBird.y * (.55 + .45 * span);
    vec3 spread = vec3(sx * (sh + dx * cos(a)), p.y + dx * sin(a), p.z - dx * .12 * (1. - aBird.x));
    p = mix(p, mix(fold, spread, aBird.x), _wing);
  }
  if (_head > .001) {
    vec3 piv = vec3(0., .15 * S, .06 * S);
    float ang = aBird.z * 1.15 * _head, c = cos(ang), s = sin(ang);
    vec3 r = p - piv;
    p = piv + vec3(r.x, r.y * c - r.z * s, r.y * s + r.z * c);
  }
  transformed = p;
}`);
  };
  m.customProgramCacheKey = () => 'bird' + S;
  return m;
}

export class Fauna {
  constructor(game, world, nav, map) {
    this.g = game; this.w = world; this.nav = nav; this.map = map; this.scene = world.scene; this.col = world.collision;
    this.rnd = mulberry(777); this.time = 0; this.frame = 0;
    const touch = !!game.touch;
    // ---- birds
    this.spots = this.findSpots();
    this.flocks = []; this.birds = [];
    const FLOCKS = touch ? 4 : 8, PER = touch ? 6 : 8;
    const kit = game.assets.models.fauna.scene;
    this.meshes = {};
    for (const [k, sp] of Object.entries(SPECIES)) {
      const src = kit.getObjectByName(sp.mesh); if (!src) continue;
      let mesh = src.isMesh ? src : null; if (!mesh) src.traverse(o => { if (!mesh && o.isMesh) mesh = o; });
      const n = FLOCKS * PER;
      const geo = mesh.geometry.clone(); geo.userData.shared = false;
      const attr = new THREE.InstancedBufferAttribute(new Float32Array(n * 3), 3); attr.setUsage(THREE.DynamicDrawUsage);
      geo.setAttribute('aBird', attr);
      const im = new THREE.InstancedMesh(geo, birdMaterial(mesh.material, sp.S), n);
      im.instanceMatrix.setUsage(THREE.DynamicDrawUsage); im.count = 0; im.frustumCulled = false;
      im.castShadow = false; im.receiveShadow = false;
      this.scene.add(im);
      this.meshes[k] = { im, attr, n, list: [] };
    }
    for (let f = 0; f < FLOCKS; f++) {
      const kind = f % 3 === 2 ? 'sparrow' : 'pigeon', M = this.meshes[kind]; if (!M) continue;
      const F = { kind, birds: [], active: false, x: 0, z: 0, y: 0, cool: 0 };
      for (let i = 0; i < PER; i++) { const b = { F, kind, i: M.list.length, pos: new THREE.Vector3(), yaw: 0, state: 'off', t: 0, sc: 1 }; M.list.push(b); F.birds.push(b); this.birds.push(b); }
      this.flocks.push(F);
    }
    // ---- cats
    this.cats = [];
    const clips = game.assets.clips('fauna') || [];
    const CATS = touch ? 2 : 4, COATS = [['#d8924e', '#f4e6d2'], ['#9a9a9e', '#f0f0f0'], ['#4a3a2c', '#c8b49a'], ['#2a2a2c', '#2e2e30'], ['#2a2a2c', '#f2f2f2'], ['#c8b8a0', '#f6f0e6']];
    if (kit.getObjectByName('CAT')) for (let i = 0; i < CATS; i++) {
      const o = game.assets.clone('fauna', 'CAT');
      const mats = [];
      o.traverse(m => { if (m.isMesh) { m.material = m.material.clone(); mats.push(m.material); m.castShadow = true; m.receiveShadow = false; m.frustumCulled = false; } });
      const [coat, light] = COATS[i % COATS.length];
      for (const m of mats) { if (m.name === 'cat_coat') m.color.set(coat); if (m.name === 'cat_light') m.color.set(light); }
      const s = .92 + this.rnd() * .2; o.scale.setScalar(s);
      const mixer = new THREE.AnimationMixer(o), acts = {};
      for (const c of clips) acts[c.name] = mixer.clipAction(c);
      this.cats.push({ o, mixer, acts, cur: null, mats, eye: mats.find(m => m.name === 'cat_eye'), pos: new THREE.Vector3(), yaw: 0, state: 'off', t: 0, vel: new THREE.Vector3() });
    }
  }

  // places birds like: open paving on the plazas, park lawns, the heritage avenue, round the planters
  findSpots() {
    const out = [], P = this.nav.pois;
    for (const p of P.perch) out.push({ x: p.x, z: p.z, r: 3.5, park: p.park });
    for (const R of this.nav.rings || []) for (let k = 0; k < 4; k++) { const a = k / 4 * Math.PI * 2 + .4, rr = R.park ? 26 : R.r + 4; out.push({ x: R.x + Math.cos(a) * rr, z: R.z + Math.sin(a) * rr, r: R.park ? 5 : 3, park: !!R.park }); }
    for (let bx = -2; bx <= 2; bx++) for (const t of [-27, 0, 27]) out.push({ x: bx * PITCH + t, z: HERITAGE.z + (this.rnd() - .5) * 3, r: 2.5, heritage: true });
    // keep only spots clear of furniture
    return out.filter(s => !this.blocked(s.x, s.z, .6));
  }

  blocked(x, z, pad = .3) {
    for (const b of this.col.near(x, z, pad + 1)) {
      if (b.tag === 'tram' || b.max.y < .2) continue;
      if (x > b.min.x - pad && x < b.max.x + pad && z > b.min.z - pad && z < b.max.z + pad) return true;
    }
    return false;
  }

  inView(x, y, z, r, frus) { _sph.center.set(x, y, z); _sph.radius = r; return frus.intersectsSphere(_sph); }

  // a fright at pos (gunshot, explosion, crash): everything near takes off / bolts
  scare(pos, radius) {
    for (const F of this.flocks) if (F.active && F.state !== 'air' && Math.hypot(F.x - pos.x, F.z - pos.z) < radius) this.takeOff(F, pos);
    for (const c of this.cats) if (c.state !== 'off' && c.state !== 'bolt' && c.pos.distanceTo(pos) < radius) this.bolt(c, pos);
  }

  // ---------------------------------------------------------------- birds
  placeFlock(F, s) {
    const r = this.rnd;
    F.active = true; F.state = 'ground'; F.x = s.x; F.z = s.z; F.y = this.groundY(s.x, s.z); F.spot = s; F.cool = 0; F.landT = 0;
    for (const b of F.birds) {
      let x = 0, z = 0;
      for (let k = 0; k < 6; k++) { const a = r() * Math.PI * 2, d = Math.sqrt(r()) * s.r; x = s.x + Math.cos(a) * d; z = s.z + Math.sin(a) * d; if (!this.blocked(x, z, .15)) break; }
      b.pos.set(x, F.y, z); b.yaw = r() * Math.PI * 2; b.state = 'ground'; b.t = r() * 3; b.act = 'peck'; b.phase = r() * 10;
      b.sc = (SPECIES[b.kind].scale[0] + r() * (SPECIES[b.kind].scale[1] - SPECIES[b.kind].scale[0]));
      b.spread = 0; b.ang = 0; b.peck = 0;
    }
  }

  groundY(x, z) { return Math.abs(x) < CITY_EDGE && Math.abs(z) < CITY_EDGE ? .04 : this.map.height(x, z) + .02; }

  takeOff(F, from) {
    const r = this.rnd;
    F.state = 'air'; F.cool = 25 + r() * 25;
    // a rooftop nearby to land on (else just up and away)
    let roof = null, bd = 1e9;
    for (const b of this.col.near(F.x, F.z, 60)) {
      if (b.tag !== 'building' || b.max.y < 6 || b.max.y > 60) continue;
      const cx = (b.min.x + b.max.x) / 2, cz = (b.min.z + b.max.z) / 2, d = Math.hypot(cx - F.x, cz - F.z);
      const away = from ? ((cx - F.x) * (F.x - from.x) + (cz - F.z) * (F.z - from.z)) : 1;
      const sc = d - (away > 0 ? 20 : 0) + r() * 15;
      if (d > 15 && d < 75 && sc < bd) { bd = sc; roof = b; }
    }
    for (const b of F.birds) {
      b.state = 'air'; b.t = -r() * .45;                      // a ragged burst, not all at once
      b.from = b.pos.clone();
      const ax = from ? b.pos.x - from.x : r() - .5, az = from ? b.pos.z - from.z : r() - .5, L = Math.hypot(ax, az) || 1;
      if (roof) b.to = new THREE.Vector3(roof.min.x + 1 + r() * (roof.max.x - roof.min.x - 2), roof.max.y + .05, roof.min.z + 1 + r() * (roof.max.z - roof.min.z - 2));
      else b.to = new THREE.Vector3(b.pos.x + ax / L * 70 + (r() - .5) * 20, 26 + r() * 10, b.pos.z + az / L * 70 + (r() - .5) * 20);
      b.mid = new THREE.Vector3((b.from.x + b.to.x) / 2 + ax / L * 6 + (r() - .5) * 8, Math.max(b.from.y, b.to.y) + 5 + r() * 4, (b.from.z + b.to.z) / 2 + az / L * 6 + (r() - .5) * 8);
      b.dur = Math.max(2.2, b.from.distanceTo(b.to) / (7 + r() * 3)); b.roof = !!roof;
    }
  }

  stepBird(b, dt, P, ppos, threat) {
    const r = this.rnd;
    b.t += dt;
    if (b.state === 'ground') {
      // peck, walk a few steps (pigeons nod), hop (sparrows), turn
      b.spread += (0 - b.spread) * Math.min(1, dt * 8);
      b.ang = .15;
      if (b.t > 0) {
        b.t = -(.8 + r() * 2.5);
        const x = r();
        b.act = x < .45 ? 'peck' : x < .8 ? 'walk' : x < .92 ? 'turn' : 'look';
        if (b.act === 'walk' || b.act === 'turn') { b.tyaw = b.yaw + (r() - .5) * 2.4; }
        // stay near the flock spot
        const dx = b.F.x - b.pos.x, dz = b.F.z - b.pos.z;
        if (Math.hypot(dx, dz) > (b.F.spot ? b.F.spot.r : 3)) b.tyaw = Math.atan2(dx, dz);
      }
      b.peck = b.act === 'peck' ? sstep(Math.sin((b.t + b.phase) * 7) * 1.6) * .9 : b.act === 'look' ? -.25 : 0;
      if (b.act === 'walk' || b.act === 'turn') {
        b.yaw += wrapA(b.tyaw - b.yaw) * Math.min(1, dt * 6);
        if (b.act === 'walk') {
          const sp = b.kind === 'sparrow' ? .5 : .32, hop = b.kind === 'sparrow' ? Math.abs(Math.sin((b.t + b.phase) * 9)) * .05 : 0;
          const nx = b.pos.x + Math.sin(b.yaw) * sp * dt, nz = b.pos.z + Math.cos(b.yaw) * sp * dt;
          if (!this.blocked(nx, nz, .08)) { b.pos.x = nx; b.pos.z = nz; }
          b.pos.y = b.F.y + hop;
          if (b.kind === 'pigeon') b.peck = .25 * Math.max(0, Math.sin((b.t + b.phase) * 11));
        }
      }
      // walkers brushing past: a short flutter aside
      if (threat && threat.d < 1.1) { b.state = 'hopaway'; b.t = 0; b.from = b.pos.clone(); const ax = b.pos.x - threat.x, az = b.pos.z - threat.z, L = Math.hypot(ax, az) || 1; b.to = new THREE.Vector3(b.pos.x + ax / L * 2.2, b.F.y, b.pos.z + az / L * 2.2); }
    } else if (b.state === 'hopaway') {
      const k = Math.min(1, b.t / .7);
      b.pos.lerpVectors(b.from, b.to, k); b.pos.y = b.F.y + Math.sin(k * Math.PI) * .7;
      b.yaw = Math.atan2(b.to.x - b.from.x, b.to.z - b.from.z);
      b.spread = Math.sin(k * Math.PI); b.ang = Math.sin(b.t * 70) * .9;
      if (k >= 1) { b.state = 'ground'; b.t = -1; }
    } else if (b.state === 'air') {
      if (b.t < 0) { b.peck = 0; b.spread = Math.min(1, b.spread + dt * 3); b.ang = .6; return; }
      const k = Math.min(1, b.t / b.dur), e = k < .5 ? 2 * k * k : 1 - 2 * (1 - k) * (1 - k);
      // quadratic bezier from -> mid -> to, a steep climb at the start
      const u = 1 - e, x = u * u * b.from.x + 2 * u * e * b.mid.x + e * e * b.to.x, z = u * u * b.from.z + 2 * u * e * b.mid.z + e * e * b.to.z;
      const yk = Math.min(1, k * 1.6), y = (1 - yk) * (1 - yk) * b.from.y + 2 * (1 - yk) * yk * b.mid.y + yk * yk * (b.roof ? Math.max(b.to.y, b.mid.y * .85 + b.to.y * .15) : b.to.y);
      const yy = k > .8 && b.roof ? y + (b.to.y - y) * sstep((k - .8) / .2) : y;
      const dx = x - b.pos.x, dz = z - b.pos.z;
      if (dx * dx + dz * dz > 1e-6) b.yaw = Math.atan2(dx, dz);
      b.pitch = Math.max(-.6, Math.min(.6, -Math.atan2(yy - b.pos.y, Math.hypot(dx, dz) + 1e-4) * .7));
      b.pos.set(x, yy, z);
      b.spread = 1; b.peck = 0;
      // fast flapping on take-off, glides with bursts of flaps on the way, a flare to land
      const flap = b.t < 1.4 || (k > .82 && b.roof) || Math.sin(b.t * 1.7 + b.phase) > .2;
      b.ang = flap ? Math.sin(b.t * (b.kind === 'sparrow' ? 70 : 52) + b.phase) * 1.05 + .1 : .08 + Math.sin(b.t * 3) * .05;
      if (k >= 1) {
        if (b.landing) { b.state = 'ground'; b.landing = false; b.pos.y = b.F.y; b.t = -1; }
        else if (b.roof) { b.state = 'roof'; b.t = 0; }
        else b.state = 'gone';
        b.pitch = 0;
      }
    } else if (b.state === 'roof') {
      b.spread += (0 - b.spread) * Math.min(1, dt * 5); b.ang = .15; b.pitch = 0;
      b.peck = Math.sin(b.t * .7 + b.phase) > .9 ? .3 : 0;
    }
  }

  updateBirds(dt, focus, frus) {
    const r = this.rnd, g = this.g, P = g.player, clock = g.clock;
    const night = clock ? clock.daylight() < .2 : false;
    // the threat: the player on foot (running counts much more), in a car, on a board
    const car = P.mode === 'car' && g.vehicles.current, pv = car ? g.vehicles.carVel(car) : P.vel;
    const pspeed = Math.hypot(pv.x, pv.z), ppos = car ? car.pos : P.pos;
    const R = car ? (pspeed > 3 ? 16 : 6) : P.running || pspeed > 6 ? 9 : pspeed > 2 ? 3.2 : 1.8;
    for (const F of this.flocks) {
      F.cool -= dt;
      const d = Math.hypot(F.x - focus.x, F.z - focus.z);
      // re-place flocks that are far behind / gone, out of sight (none on the ground at night)
      if (!F.active || d > 190 || F.birds.every(b => b.state === 'gone')) {
        if (F.active && F.birds.some(b => b.state !== 'gone' && b.state !== 'roof' && this.inView(b.pos.x, b.pos.y, b.pos.z, 1, frus) && d < 120)) continue;
        F.active = false;
        if (night) { for (const b of F.birds) b.state = 'off'; continue; }
        for (let k = 0; k < 12; k++) {
          const s = this.spots[Math.floor(r() * this.spots.length)];
          const ds = Math.hypot(s.x - focus.x, s.z - focus.z);
          if (ds < 22 || ds > 150 || this.flocks.some(o => o !== F && o.active && Math.hypot(o.x - s.x, o.z - s.z) < 8)) continue;
          if (ds < 90 && this.inView(s.x, .2, s.z, s.r, frus)) continue;
          this.placeFlock(F, s); break;
        }
        continue;
      }
      if (F.state === 'ground') {
        if (Math.hypot(F.x - ppos.x, F.z - ppos.z) < R + 3 && F.birds.some(b => b.state === 'ground' && Math.hypot(b.pos.x - ppos.x, b.pos.z - ppos.z) < R)) this.takeOff(F, ppos);
      } else if (F.state === 'air' && F.cool <= 0 && F.birds.every(b => b.state === 'roof' || b.state === 'gone') && Math.hypot(F.x - ppos.x, F.z - ppos.z) > 18 && !night) {
        // back down to the spot once things are quiet
        F.state = 'ground';
        for (const b of F.birds) {
          if (b.state !== 'roof') continue;
          b.state = 'air'; b.t = -r() * 2; b.from = b.pos.clone(); b.roof = true;
          b.to = new THREE.Vector3(F.x + (r() - .5) * 5, F.y, F.z + (r() - .5) * 5);
          b.mid = new THREE.Vector3((b.from.x + b.to.x) / 2, b.from.y + 3, (b.from.z + b.to.z) / 2);
          b.dur = Math.max(2.5, b.from.distanceTo(b.to) / 7); b.landing = true;
        }
      }
    }
    // pedestrians brushing past
    const peds = this.w.population ? this.w.population.cell : null;
    for (const M of Object.values(this.meshes)) {
      let n = 0;
      const A = M.attr.array;
      for (const b of M.list) {
        if (!b.F.active || b.state === 'off' || b.state === 'gone') continue;
        const d = Math.hypot(b.pos.x - focus.x, b.pos.z - focus.z);
        const throttle = d > 70 ? 3 : 1;
        b.acc = (b.acc || 0) + dt;
        if ((this.frame + b.i) % throttle === 0) {
          let threat = null;
          if (b.state === 'ground' && peds && d < 70) {
            const l = peds.get(Math.floor(b.pos.x / 2) * 7919 + Math.floor(b.pos.z / 2));
            if (l) for (const q of l) { const dd = Math.hypot(q.pos.x - b.pos.x, q.pos.z - b.pos.z); if (dd < 1.1 && q.state === 'walk') { threat = { d: dd, x: q.pos.x, z: q.pos.z }; break; } }
          }
          this.stepBird(b, Math.min(b.acc, .3), P, ppos, threat); b.acc = 0;
        }
        if (d > 160 || b.state === 'gone') continue;
        _e.set(b.pitch || 0, b.yaw, 0); _q.setFromEuler(_e);
        _m.compose(b.pos, _q, _s.setScalar(b.sc));
        _m.toArray(M.im.instanceMatrix.array, n * 16);
        A[n * 3] = b.spread; A[n * 3 + 1] = b.ang; A[n * 3 + 2] = b.peck;
        n++;
      }
      M.im.count = n; M.im.instanceMatrix.needsUpdate = true; M.attr.needsUpdate = true;
    }
  }

  // ---------------------------------------------------------------- cats
  // a spot by an alley mouth (the gaps between the buildings on the block centre lines), against the wall
  catSpot(focus, frus) {
    const r = this.rnd;
    for (let k = 0; k < 20; k++) {
      const bx = Math.round(focus.x / PITCH) + Math.floor(r() * 5) - 2, bz = Math.round(focus.z / PITCH) + Math.floor(r() * 5) - 2;
      if (Math.abs(bx) > CITY_N || Math.abs(bz) > CITY_N) continue;
      const cx = bx * PITCH, cz = bz * PITCH, side = Math.floor(r() * 4);
      const n = [[0, -1], [1, 0], [0, 1], [-1, 0]][side];
      // mouth on that side, then a little along the wall
      const along = (r() < .5 ? -1 : 1) * (1.5 + r() * 5);
      const x = cx + n[0] * 41.8 + (n[1] ? along : 0), z = cz + n[1] * 41.8 + (n[0] ? along : 0);
      const d = Math.hypot(x - focus.x, z - focus.z);
      if (d < 25 || d > 130 || this.blocked(x, z, .25)) continue;
      if (d < 100 && this.inView(x, .3, z, 1, frus)) continue;
      // the alley: straight in toward the block centre must be open for a few metres
      let open = true; for (let s = 2; s <= 10; s += 2) if (this.blocked(cx + n[0] * (41.8 - s), cz + n[1] * (41.8 - s), .2)) { open = false; break; }
      const ax = cx + n[0] * 41.8, az = cz + n[1] * 41.8;
      return { x, z, n, alley: open ? { x: ax, z: az, in: [-n[0], -n[1]] } : null };
    }
    return null;
  }

  play(c, name, fade = .25, ts = 1) {
    const a = c.acts[name]; if (!a) return;
    a.timeScale = ts;
    if (c.cur === a) return;
    a.reset(); a.enabled = true; a.setEffectiveWeight(1); a.play();
    if (c.cur && fade > 0) a.crossFadeFrom(c.cur, fade, false); else if (c.cur) c.cur.stop();
    c.cur = a;
  }

  bolt(c, from) {
    c.state = 'bolt'; c.t = 0;
    // run along the wall away from the threat, then into the alley if there is one
    const S = c.spot;
    if (S && S.alley) c.goal = [{ x: S.alley.x, z: S.alley.z }, { x: S.alley.x + S.alley.in[0] * 18, z: S.alley.z + S.alley.in[1] * 18 }];
    else { const ax = c.pos.x - from.x, az = c.pos.z - from.z, L = Math.hypot(ax, az) || 1; c.goal = [{ x: c.pos.x + ax / L * 20, z: c.pos.z + az / L * 20 }]; }
    this.play(c, 'Run', .12, 1);
  }

  updateCats(dt, focus, frus) {
    const r = this.rnd, g = this.g, P = g.player, night = g.clock ? g.clock.daylight() < .25 : false;
    const car = P.mode === 'car' && g.vehicles.current, ppos = car ? car.pos : P.pos, pv = car ? g.vehicles.carVel(car) : P.vel;
    const pspeed = Math.hypot(pv.x, pv.z), R = car ? 11 : P.running || pspeed > 5 ? 9 : 4.5;
    for (const c of this.cats) {
      const d = c.state === 'off' ? 1e9 : Math.hypot(c.pos.x - focus.x, c.pos.z - focus.z);
      if (c.state === 'off' || d > 170 || c.state === 'gone') {
        if (c.state !== 'off' && c.state !== 'gone' && d < 170) continue;
        if (c.o.parent) c.o.removeFromParent();
        c.state = 'off'; c.wait = (c.wait || 0) - dt; if (c.wait > 0) continue;
        const s = this.catSpot(focus, frus); if (!s) { c.wait = 2; continue; }
        c.spot = s; c.pos.set(s.x, this.groundY(s.x, s.z) - .03, s.z);
        if (s.n[0]) c.yaw = r() < .5 ? 0 : Math.PI; else c.yaw = r() < .5 ? Math.PI / 2 : -Math.PI / 2;
        c.state = r() < .5 ? 'sit' : 'idle'; c.t = 4 + r() * 12; c.cur = null; c.mixer.stopAllAction();
        this.play(c, c.state === 'sit' ? 'Sit' : 'Idle', 0);
        this.scene.add(c.o);
        continue;
      }
      c.t -= dt;
      const pd = Math.hypot(c.pos.x - ppos.x, c.pos.z - ppos.z);
      if (c.state !== 'bolt' && pd < R) this.bolt(c, ppos);
      else if (c.state !== 'bolt' && pd < R * 2.2 && c.state !== 'look') { c.state = 'look'; c.t = 2 + r() * 2; this.play(c, 'Look', .3); c.yaw += wrapA(Math.atan2(ppos.x - c.pos.x, ppos.z - c.pos.z) - c.yaw) * .35; }
      if (c.state === 'bolt') {
        const G = c.goal[0];
        const dx = G.x - c.pos.x, dz = G.z - c.pos.z, L = Math.hypot(dx, dz);
        if (L < .6) { c.goal.shift(); if (!c.goal.length) { c.state = this.inView(c.pos.x, .3, c.pos.z, 1, frus) && d < 60 ? 'hide' : 'gone'; c.t = 8 + r() * 10; this.play(c, 'Sit', .3); } }
        else {
          const sp = Math.min(5.2, 2.5 - c.t * 8);          // c.t counts down from 0: a quick burst to full speed
          c.vel.set(dx / L * sp, -9, dz / L * sp);
          const x0 = c.pos.x, z0 = c.pos.z;
          this.col.moveCapsule(c.pos, c.vel, .14, .35, dt);
          if (Math.hypot(c.pos.x - x0, c.pos.z - z0) < sp * dt * .3) c.goal = [{ x: c.pos.x - dz / L * 6, z: c.pos.z + dx / L * 6 }];
          c.yaw += wrapA(Math.atan2(dx, dz) - c.yaw) * Math.min(1, dt * 10);
        }
      } else if (c.state === 'walk') {
        const sp = .55, nx = c.pos.x + Math.sin(c.yaw) * sp * dt, nz = c.pos.z + Math.cos(c.yaw) * sp * dt;
        if (this.blocked(nx, nz, .15) || Math.hypot(nx - c.spot.x, nz - c.spot.z) > 7) { c.state = 'idle'; c.t = 2 + r() * 4; c.yaw += Math.PI; this.play(c, 'Idle', .3); }
        else { c.pos.x = nx; c.pos.z = nz; }
        if (c.t <= 0) { c.state = r() < .5 ? 'sit' : 'idle'; c.t = 5 + r() * 10; this.play(c, c.state === 'sit' ? 'Sit' : 'Idle', .35); }
      } else if (c.state === 'hide') {
        if (c.t <= 0 && (!this.inView(c.pos.x, .3, c.pos.z, 1, frus) || d > 60)) c.state = 'gone';
      } else if (c.t <= 0) {
        // sit / groom / look round -> slink a few steps along the wall
        const x = r();
        if (x < .45) { c.state = 'walk'; c.t = 3 + r() * 6; this.play(c, 'Walk', .3, 1); if (r() < .5) c.yaw += Math.PI; }
        else if (x < .75) { c.state = 'sit'; c.t = 6 + r() * 14; this.play(c, 'Sit', .4); }
        else { c.state = 'idle'; c.t = 3 + r() * 6; this.play(c, 'Idle', .35); }
      }
      if (c.state === 'gone') { if (c.o.parent) c.o.removeFromParent(); c.wait = 6 + r() * 10; continue; }
      c.o.position.copy(c.pos); c.o.rotation.y = c.yaw;
      if (c.eye) c.eye.emissiveIntensity = night ? 2.2 : .05;
      // animate only when it can be seen
      c.acc = (c.acc || 0) + dt;
      if (d < 70 && this.inView(c.pos.x, .25, c.pos.z, .6, frus)) { c.mixer.update(Math.min(c.acc, .2)); c.acc = 0; }
    }
  }

  update(dt, focus, frus) {
    this.time += dt; this.frame++;
    this.updateBirds(dt, focus, frus);
    this.updateCats(dt, focus, frus);
  }

  stats() {
    const st = { birds: {}, cats: {} };
    for (const b of this.birds) st.birds[b.state] = (st.birds[b.state] || 0) + 1;
    for (const c of this.cats) st.cats[c.state] = (st.cats[c.state] || 0) + 1;
    st.flocks = this.flocks.filter(f => f.active).length;
    return st;
  }

  dispose() {
    for (const M of Object.values(this.meshes)) { M.im.removeFromParent(); M.im.geometry.dispose(); M.im.material.dispose(); }
    for (const c of this.cats) { c.o.removeFromParent(); c.mixer.stopAllAction(); for (const m of c.mats) m.dispose(); c.o.traverse(o => { if (o.isSkinnedMesh) o.skeleton.dispose(); }); }
  }
}
