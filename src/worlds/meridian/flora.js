// Flora: the Blender-grown trees of tools/blender/trees.py (trees.glb, roots TR_*) planted as instanced meshes with
// three levels of detail. Every variant has TR_x (hero, 3-6k tris), TR_x_mid (~600 tris) and TR_x_lod (two crossed
// impostor cards from a shared atlas). Instances are bucketed by distance from the camera whenever it has moved a few
// metres, so thousands of trees cost a handful of draw calls. Tiers never swap in one frame: across a distance band
// both are drawn and cross-fade with a screen-door dither evaluated per frame in the shader (core/lodfade.js), and
// small things (bushes, rocks) fade out far away instead of vanishing. Streamed instances (addLive) dither in over
// ~1.6 s and out again on removeLive. Leaves are alpha-tested double-sided cards whose normals
// point out of the crown (no back-face flip), with an alpha boost on distant mips so crowns don't thin out.
// Wind: gusts roll across the island (a slow travelling wave in world space); the whole crown bends with the gust
// (branches and leaves share one bend so they never separate), and leaf cards add their own flutter on top. near()
// lists trees around a point (falling leaves in meridian/atmos.js).
import * as THREE from 'three';
import { FADE_TIME, APPEAR, fadeShader, fadeGeometry, fadeAttr } from '../../core/lodfade.js';

// Level-of-detail distances in metres (scaled by the quality preset's draw factor and the tree's height):
// [end of the hero band, end of the mid band, cull distance for small things]; each switch cross-fades over the
// last BAND fraction before it. Rocks have one tier and only fade out.
export const LOD = { hero: 78, mid: 290, small: 330, rock: 430, band: .3, step: 4 };

// Planting pools (variant names in trees.glb). Earth picks a pool per area.
export const POOLS = {
  cherry: ['TR_cherry_a', 'TR_cherry_b'],
  park: ['TR_oak_a', 'TR_oak_b', 'TR_maple_a', 'TR_maple_b', 'TR_maple_autumn_a', 'TR_ash_b'],
  riverside: ['TR_willow_a', 'TR_willow_b', 'TR_willow_a', 'TR_ash_a', 'TR_ash_young'],
  suburb: ['TR_maple_a', 'TR_maple_b', 'TR_maple_autumn_a', 'TR_maple_autumn_b', 'TR_birch_a', 'TR_birch_b', 'TR_birch_c', 'TR_ash_young'],
  village: ['TR_oak_a', 'TR_oak_b', 'TR_ash_a', 'TR_ash_b', 'TR_maple_a', 'TR_maple_autumn_b', 'TR_birch_a'],
  field: ['TR_oak_a', 'TR_oak_b', 'TR_oak_gold', 'TR_ash_a', 'TR_ash_b', 'TR_umbrella_a', 'TR_umbrella_b'],
  lowland: ['TR_oak_a', 'TR_oak_b', 'TR_ash_a', 'TR_ash_b', 'TR_maple_a', 'TR_maple_b', 'TR_maple_autumn_a', 'TR_birch_a', 'TR_birch_b', 'TR_birch_c', 'TR_ash_young', 'TR_oak_gold'],
  rainforest: ['TR_emergent_a', 'TR_emergent_b', 'TR_understory_a', 'TR_understory_b', 'TR_understory_a', 'TR_understory_b'],
  mixed: ['TR_birch_a', 'TR_birch_c', 'TR_spruce_a', 'TR_spruce_b', 'TR_spruce_c', 'TR_pine_b', 'TR_ash_young', 'TR_maple_autumn_b'],
  conifer: ['TR_spruce_a', 'TR_spruce_b', 'TR_spruce_c', 'TR_spruce_b', 'TR_pine_a', 'TR_pine_b'],
  snow: ['TR_spruce_snow_a', 'TR_spruce_snow_b', 'TR_spruce_snow_a', 'TR_pine_snow', 'TR_bare_snow_a', 'TR_bare_snow_b'],
  bush: ['TR_bush_a', 'TR_bush_b', 'TR_bush_flower'],
  rock: ['TR_rock_a', 'TR_rock_b', 'TR_rock_c'],
  rock_snow: ['TR_rock_snow_a', 'TR_rock_snow_b', 'TR_rock_snow_c'],
  // frontier worlds (planet.js): savanna mesas, the jungle basin, the glacier shelf
  savanna: ['TR_umbrella_a', 'TR_umbrella_b', 'TR_umbrella_a', 'TR_oak_gold'],
  jungle: ['TR_emergent_a', 'TR_emergent_b', 'TR_understory_a', 'TR_understory_b', 'TR_understory_a', 'TR_understory_b', 'TR_willow_b'],
};

const _m = new THREE.Matrix4(), _q = new THREE.Quaternion(), _p = new THREE.Vector3(), _s = new THREE.Vector3(), Y = new THREE.Vector3(0, 1, 0);

// crown bend shared by bark and leaves: grows with height squared, gusts travel across the island
const BEND = `
  #ifdef USE_INSTANCING
    vec3 ip = instanceMatrix[3].xyz;
  #else
    vec3 ip = vec3(0.);
  #endif
  float gust = .55 + .45 * sin(uTime * .37 - ip.x * .011 - ip.z * .007) * sin(uTime * .19 + ip.z * .009 + 1.3);
  float bk = clamp(position.y * .1, 0., 1.6); bk *= bk;
  float bw = uTime * 1.1 + ip.x * .05 + ip.z * .04;
  vec2 bend = vec2(.8, .45) * gust * (.16 + .05 * sin(bw)) + vec2(sin(bw * 1.7), cos(bw * 1.3)) * .035 * gust;
  transformed.xz += bend * bk;
  transformed.y -= dot(bend, bend) * bk * .5;`;

function prepMaterial(m, time) {
  if (m.userData.flora) return;
  m.userData.flora = true;
  const n = m.name || '';
  if (/^bark_/.test(n) || n === 'snow') {
    // (snow lies on branches: it bends with them; on rocks the bend is a few millimetres)
    if (n === 'snow') { m.roughness = .55; m.envMapIntensity = .6; } else { m.envMapIntensity = .3; m.metalness = 0; }
    m.onBeforeCompile = sh => {
      sh.uniforms.uTime = time;
      sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\nuniform float uTime;')
        .replace('#include <begin_vertex>', '#include <begin_vertex>\n' + BEND);
      fadeShader(sh);
    };
    m.customProgramCacheKey = () => 'florab2';
    m.needsUpdate = true;
  } else if (/^leaves_/.test(n)) {
    const imp = n === 'leaves_impostor';
    m.alphaTest = imp ? .42 : .5; m.transparent = false; m.depthWrite = true;
    m.side = THREE.DoubleSide; m.shadowSide = THREE.DoubleSide;
    m.envMapIntensity = .35; m.roughness = Math.max(m.roughness, .7); m.metalness = 0;
    if (imp) m.color.multiplyScalar(.82);          // impostor cards face the sky: keep them from out-shining the hero crowns
    m.onBeforeCompile = sh => {
      sh.uniforms.uTime = time;
      if (!imp) {
        sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\nuniform float uTime;')
          .replace('#include <begin_vertex>', `#include <begin_vertex>
            ${BEND}
            // leaf flutter: fast, small, stronger in a gust and toward the outside of the crown
            float wk = clamp(position.y * .08, 0., 1.6) * (.5 + gust);
            float wt = uTime * 2.2 + ip.x * .07 + ip.z * .05;
            transformed.x += (sin(wt + position.y * .35) * .05 + sin(wt * 3.7 + position.x * 2.3 + position.z) * .03) * wk;
            transformed.z += (cos(wt * .8 + position.y * .3) * .04 + sin(wt * 4.1 + position.z * 2.1 + position.x) * .03) * wk;
            transformed.y += sin(wt * 2.9 + position.x * 3.1) * .02 * wk;`);
      }
      sh.fragmentShader = sh.fragmentShader
        // foliage normals already point out of the crown: don't flip them on back faces
        .replace('float faceDirection = gl_FrontFacing ? 1.0 : - 1.0;', 'float faceDirection = 1.0;')
        // keep coverage on small mips (alpha-tested cards otherwise thin out with distance)
        .replace('#include <map_fragment>', `#include <map_fragment>
          #ifdef USE_MAP
            vec2 fdx = dFdx(vMapUv * 1024.), fdy = dFdy(vMapUv * 1024.);
            float mipL = max(0., .5 * log2(max(dot(fdx, fdx), dot(fdy, fdy))));
            diffuseColor.a *= 1. + mipL * .28;
          #endif`);
      fadeShader(sh);
    };
    m.customProgramCacheKey = () => 'flora2' + (imp ? 'i' : 'l');
    m.needsUpdate = true;
  } else {
    // rocks: no wind, just the LOD fade
    m.onBeforeCompile = sh => fadeShader(sh);
    m.customProgramCacheKey = () => 'florar';
    m.needsUpdate = true;
  }
}

export class Flora {
  constructor(g, scene, gltf) {
    this.g = g; this.scene = scene; this.kit = gltf.scene;
    this.time = { value: 0 };
    this.kinds = new Map();
    this.last = new THREE.Vector3(1e9, 0, 1e9); this.timer = 0;
    this.kit.updateMatrixWorld(true);
    for (const root of this.kit.children) {
      const name = root.name;
      if (!/^TR_/.test(name) || /_(mid|lod)$/.test(name)) continue;
      const tiers = [root, this.kit.getObjectByName(name + '_mid'), this.kit.getObjectByName(name + '_lod')].map(r => r ? this.parts(r) : null);
      const u = root.userData || {};
      this.kinds.set(name, { name, root, tiers, h: u.h || 8, w: u.w || 3, trunk: u.trunk || .3, species: u.species || '', list: [], collide: [], meshes: null });
    }
  }

  // meshes under a root with their transform relative to it
  parts(root) {
    const inv = new THREE.Matrix4().copy(root.matrixWorld).invert(), out = [];
    root.traverse(o => {
      if (!o.isMesh) return;
      const local = new THREE.Matrix4().multiplyMatrices(inv, o.matrixWorld);
      let geo = o.geometry;
      if (!local.equals(new THREE.Matrix4())) { geo = geo.clone().applyMatrix4(local); }
      geo.userData.shared = true;
      const mats = Array.isArray(o.material) ? o.material : [o.material];
      for (const m of mats) prepMaterial(m, this.time);
      out.push({ geo, mat: o.material });
    });
    return out;
  }

  has(name) { return this.kinds.has(name); }

  pick(what, rnd) {
    if (!POOLS[what]) return this.kinds.get(what);
    const p = POOLS[what].filter(n => this.kinds.has(n));
    return p.length ? this.kinds.get(p[Math.floor(rnd() * p.length)]) : null;
  }

  // streamed worlds: reserve instance slots per pool before build(), then addLive/removeLive as chunks come and go
  reserve(what, cap) { for (const n of POOLS[what] || [what]) { const k = this.kinds.get(n); if (k) k.cap = Math.max(k.cap || 0, cap); } }

  // appear: dither in over APPEAR seconds (props streamed in while playing); removeLive dithers them out again before
  // the slot is reused
  addLive(what, x, y, z, rnd = Math.random, scale = 1, appear = false) {
    const k = this.pick(what, rnd); if (!k || !k.meshes) return null;
    let i = k.free.pop();
    if (i === undefined) { if (k.n >= k.capacity) return null; i = k.n++; }
    _m.compose(_p.set(x, y, z), _q.setFromAxisAngle(Y, rnd() * Math.PI * 2), _s.setScalar(scale)).toArray(k.mats, i * 16);
    k.pos[i * 3] = x; k.pos[i * 3 + 1] = y; k.pos[i * 3 + 2] = z; k.alive[i] = 1;
    k.born[i] = appear ? Math.max(1e-3, this.now()) : 0;
    this.dirty = true;
    return { k, i };
  }

  removeLive(h, fade = true) {
    if (!h || h.k.alive[h.i] !== 1) return;
    if (fade) { h.k.alive[h.i] = 2; h.k.born[h.i] = -Math.max(1e-3, this.now()); (this.dying = this.dying || []).push(h); }
    else { h.k.alive[h.i] = 0; h.k.free.push(h.i); }
    this.dirty = true;
  }

  now() { return FADE_TIME.value = this.g.time || 0; }

  // pool name or variant name; returns the variant used (or null)
  add(what, x, y, z, rnd = Math.random, scale = 1, { collide = true, yaw } = {}) {
    let name = what;
    if (POOLS[what]) { const p = POOLS[what].filter(n => this.kinds.has(n)); if (!p.length) return null; name = p[Math.floor(rnd() * p.length)]; }
    const k = this.kinds.get(name); if (!k) return null;
    const m = new THREE.Matrix4().compose(_p.set(x, y, z), _q.setFromAxisAngle(Y, yaw ?? rnd() * Math.PI * 2), _s.setScalar(scale));
    k.list.push(m);
    if (collide && k.species !== 'bush') k.collide.push(m);
    return name;
  }

  get count() { let n = 0; for (const k of this.kinds.values()) if (k.alive) { for (let i = 0; i < k.n; i++) if (k.alive[i] === 1) n++; } else n += k.list.length; return n; }

  // instanced meshes: one per tier part, all parts of a tier share one instance-matrix buffer and one fade buffer
  build() {
    for (const k of this.kinds.values()) {
      const n = Math.max(k.list.length, k.cap || 0); if (!n) continue;
      k.capacity = n; k.n = k.list.length; k.free = []; k.alive = new Uint8Array(n).fill(1, 0, k.list.length);
      k.pos = new Float32Array(n * 3); k.mats = new Float32Array(n * 16); k.born = new Float32Array(n);
      k.list.forEach((m, i) => { m.toArray(k.mats, i * 16); k.pos[i * 3] = m.elements[12]; k.pos[i * 3 + 1] = m.elements[13]; k.pos[i * 3 + 2] = m.elements[14]; });
      k.meshes = k.tiers.map((parts, t) => {
        if (!parts || !parts.length) return null;
        const attr = new THREE.InstancedBufferAttribute(new Float32Array(n * 16), 16); attr.setUsage(THREE.DynamicDrawUsage);
        const fade = fadeAttr(n);
        const ms = parts.map(({ geo, mat }) => {
          const im = new THREE.InstancedMesh(fadeGeometry(geo, fade), mat, n);
          im.instanceMatrix = attr; im.count = 0; im.frustumCulled = false; im.visible = false;
          im.castShadow = t < 2; im.receiveShadow = true;
          this.scene.add(im); return im;
        });
        return { attr, fade, ms, count: 0 };
      });
    }
    this.update(this.g.camera, 0, true);
  }

  // distance plan of a kind: present tiers and where each hands over, scaled by quality and tree size
  plan(k) {
    const q = this.g.renderer.q || {}, f = (.55 + .45 * (q.draw || .8)) * (this.g.renderer.touch ? .9 : 1);
    if (k.planF === f) return k.plan;
    const big = 1 + k.h / 40, small = k.h < 3.5, rock = k.species === 'rock';
    const tiers = [0, 1, 2].filter(t => k.meshes[t]);
    // switch distances between consecutive present tiers, then the far cull (Infinity for trees: impostors stay)
    const at = [LOD.hero * f * big * (small ? .8 : 1), LOD.mid * f * big * (small ? .55 : 1)];
    const ends = [];
    for (let j = 0; j < tiers.length - 1; j++) ends.push(at[tiers[j + 1] - 1]);
    const cull = rock ? LOD.rock * f : small ? LOD.small * f : Infinity;
    ends.push(cull);
    k.planF = f;
    return (k.plan = { tiers, ends, cull });
  }

  update(cam, dt, force = false) {
    this.time.value += dt;
    const now = this.now();
    this.timer -= dt;
    const c = cam.position;
    if (!force && !this.dirty && this.timer > 0 && c.distanceToSquared(this.last) < LOD.step * LOD.step) return;
    this.timer = .5; this.last.copy(c); this.dirty = false;
    // streamed instances that have finished fading out free their slot
    if (this.dying && this.dying.length) this.dying = this.dying.filter(h => {
      if (h.k.alive[h.i] !== 2) return false;
      if (now + h.k.born[h.i] < APPEAR) return true;
      h.k.alive[h.i] = 0; h.k.free.push(h.i); return false;
    });
    const MARGIN = LOD.step + 2, B = LOD.band;
    for (const k of this.kinds.values()) {
      if (!k.meshes) continue;
      const { tiers, ends } = this.plan(k), nt = tiers.length;
      const T = k.meshes, cnt = [0, 0, 0];
      const n = k.n, P = k.pos, M = k.mats, A = k.alive, BO = k.born;
      const put = (t, i, s, e) => {
        const o = cnt[t]++, F = T[t].fade.array;
        T[t].attr.array.set(M.subarray(i * 16, i * 16 + 16), o * 16);
        F[o * 3] = s; F[o * 3 + 1] = e; F[o * 3 + 2] = BO[i];
      };
      for (let i = 0; i < n; i++) {
        if (!A[i]) continue;
        if (this.forceTier != null) { put(tiers.includes(this.forceTier) ? this.forceTier : tiers[0], i, 0, 0); continue; }     // tests: one tier everywhere
        const dx = P[i * 3] - c.x, dz = P[i * 3 + 2] - c.z, d = Math.sqrt(dx * dx + dz * dz);
        // tier j covers [ends[j-1] band start, ends[j]]: fades in over the band before its range (complement of the
        // tier before it) and fades out over the band at its end
        for (let j = 0; j < nt; j++) {
          const e = ends[j], s = e * (1 - B), pe = j ? ends[j - 1] : 0, ps = pe * (1 - B);
          if (d > e + MARGIN || (j && d < ps - MARGIN)) continue;
          // which band is nearer decides the encoding (the bands are far apart compared to the re-bucket step)
          if (j && (e === Infinity || d < (pe + s) / 2)) put(tiers[j], i, -ps, -pe);
          else put(tiers[j], i, e === Infinity ? 0 : s, e === Infinity ? 0 : e);
        }
      }
      for (let t = 0; t < 3; t++) {
        if (!T[t]) continue;
        const a = T[t].attr, fa = T[t].fade;
        a.needsUpdate = true; a.clearUpdateRanges(); a.addUpdateRange(0, cnt[t] * 16);
        fa.needsUpdate = true; fa.clearUpdateRanges(); fa.addUpdateRange(0, cnt[t] * 3);
        for (const im of T[t].ms) { im.count = cnt[t]; im.visible = cnt[t] > 0; }
      }
    }
  }

  // trees within r of (x, z): calls fn(x, y, z, kind) for each (kind: { name, h, w, species })
  near(x, z, r, fn) {
    const r2 = r * r;
    for (const k of this.kinds.values()) {
      if (!k.pos || k.species === 'rock' || k.species === 'bush' || k.h < 4) continue;
      const P = k.pos, A = k.alive;
      for (let i = 0; i < k.n; i++) {
        if (!A[i]) continue;
        const dx = P[i * 3] - x, dz = P[i * 3 + 2] - z;
        if (dx * dx + dz * dz < r2) fn(P[i * 3], P[i * 3 + 1], P[i * 3 + 2], k);
      }
    }
  }

  // per-variant matrices for the trunk colliders (kitColliders in earth.js)
  colliders() {
    const out = [];
    for (const k of this.kinds.values()) if (k.collide.length) out.push({ root: k.root, mats: k.collide, trunk: k.trunk, rock: k.species === 'rock', h: k.h });
    return out;
  }
}
