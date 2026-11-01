// Flora: the Blender-grown trees of tools/blender/trees.py (trees.glb, roots TR_*) planted as instanced meshes with
// three levels of detail. Every variant has TR_x (hero, 3-6k tris), TR_x_mid (~600 tris) and TR_x_lod (two crossed
// impostor cards from a shared atlas). Instances are bucketed by distance from the camera whenever it has moved a few
// metres, so thousands of trees cost a handful of draw calls. Leaves are alpha-tested double-sided cards whose normals
// point out of the crown (no back-face flip), with an alpha boost on distant mips so crowns don't thin out.
// Wind: gusts roll across the island (a slow travelling wave in world space); the whole crown bends with the gust
// (branches and leaves share one bend so they never separate), and leaf cards add their own flutter on top. near()
// lists trees around a point (falling leaves in meridian/atmos.js).
import * as THREE from 'three';

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
    };
    m.customProgramCacheKey = () => 'florab';
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
    };
    m.customProgramCacheKey = () => 'flora' + (imp ? 'i' : 'l');
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

  addLive(what, x, y, z, rnd = Math.random, scale = 1) {
    const k = this.pick(what, rnd); if (!k || !k.meshes) return null;
    let i = k.free.pop();
    if (i === undefined) { if (k.n >= k.capacity) return null; i = k.n++; }
    _m.compose(_p.set(x, y, z), _q.setFromAxisAngle(Y, rnd() * Math.PI * 2), _s.setScalar(scale)).toArray(k.mats, i * 16);
    k.pos[i * 3] = x; k.pos[i * 3 + 1] = y; k.pos[i * 3 + 2] = z; k.alive[i] = 1;
    this.dirty = true;
    return { k, i };
  }

  removeLive(h) { if (!h || !h.k.alive[h.i]) return; h.k.alive[h.i] = 0; h.k.free.push(h.i); this.dirty = true; }

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

  get count() { let n = 0; for (const k of this.kinds.values()) n += k.alive ? k.alive.reduce((a, b) => a + b, 0) : k.list.length; return n; }

  // instanced meshes: one per tier part, all parts of a tier share one instance-matrix buffer
  build() {
    for (const k of this.kinds.values()) {
      const n = Math.max(k.list.length, k.cap || 0); if (!n) continue;
      k.capacity = n; k.n = k.list.length; k.free = []; k.alive = new Uint8Array(n).fill(1, 0, k.list.length);
      k.pos = new Float32Array(n * 3); k.mats = new Float32Array(n * 16);
      k.list.forEach((m, i) => { m.toArray(k.mats, i * 16); k.pos[i * 3] = m.elements[12]; k.pos[i * 3 + 1] = m.elements[13]; k.pos[i * 3 + 2] = m.elements[14]; });
      k.meshes = k.tiers.map((parts, t) => {
        if (!parts || !parts.length) return null;
        const attr = new THREE.InstancedBufferAttribute(new Float32Array(n * 16), 16); attr.setUsage(THREE.DynamicDrawUsage);
        const ms = parts.map(({ geo, mat }) => {
          const im = new THREE.InstancedMesh(geo, mat, n);
          im.instanceMatrix = attr; im.count = 0; im.frustumCulled = false; im.visible = false;
          im.castShadow = t < 2; im.receiveShadow = true;
          this.scene.add(im); return im;
        });
        return { attr, ms, count: 0 };
      });
    }
    this.update(this.g.camera, 0, true);
  }

  update(cam, dt, force = false) {
    this.time.value += dt;
    this.timer -= dt;
    const c = cam.position;
    if (!force && !this.dirty && this.timer > 0 && c.distanceToSquared(this.last) < 16) return;
    this.timer = .5; this.last.copy(c); this.dirty = false;
    const q = this.g.renderer.q || {}, f = .55 + .45 * (q.draw || .8);
    const HERO = 58 * f, MID = 230 * f;
    for (const k of this.kinds.values()) {
      if (!k.meshes) continue;
      const big = 1 + k.h / 40, small = k.h < 3.5;
      const h2 = (HERO * big) ** 2, m2 = (MID * big * (small ? .6 : 1)) ** 2, far2 = small ? (MID * .75) ** 2 : k.tiers[2] ? Infinity : (MID * 1.4) ** 2;
      const T = k.meshes, cnt = [0, 0, 0];
      const n = k.n, P = k.pos, M = k.mats, A = k.alive;
      for (let i = 0; i < n; i++) {
        if (!A[i]) continue;
        const dx = P[i * 3] - c.x, dz = P[i * 3 + 2] - c.z, d2 = dx * dx + dz * dz;
        let t = d2 < h2 ? 0 : d2 < m2 ? 1 : d2 < far2 ? 2 : -1;
        if (t < 0) continue;
        while (t < 2 && !T[t]) t++;                  // missing tier: use the next cheaper one
        if (!T[t]) { t = T[1] ? 1 : 0; if (!T[t]) continue; }
        T[t].attr.array.set(M.subarray(i * 16, i * 16 + 16), cnt[t] * 16); cnt[t]++;
      }
      for (let t = 0; t < 3; t++) {
        if (!T[t]) continue;
        T[t].attr.needsUpdate = true; T[t].attr.clearUpdateRanges(); T[t].attr.addUpdateRange(0, cnt[t] * 16);
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
