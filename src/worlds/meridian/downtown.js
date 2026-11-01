// Downtown New Meridian: the core of the city built from the Blender kit of tools/blender/downtown.py (downtown.glb:
// building designs DT_* with a low-detail DT_*_lod each; downtown_street.glb: skywalks, light rail, tower cranes,
// street furniture). The layout follows a prairie river city's downtown: a street grid of avenues and streets with many
// plots per block, historic sandstone and brick low-rises lining a car-free heritage avenue (mid-block in row -1),
// a light-rail transit mall one block nearer the river (mid-block in row -2) with platforms, catenary and two trams,
// 1970s-80s concrete / bronze-glass towers next to new glass towers, a crescent tower facing a plaza, an observation
// tower, parking garages, two construction sites with slewing tower cranes, plazas at tower feet, enclosed skywalks at
// ~5 m linking neighbouring buildings across streets, and the tallest towers in the middle ring falling off outward.
// Everything is placed from a fixed seed. Buildings are instanced per design and material, with hero / low-detail
// buckets chosen by camera distance (like flora.js); street furniture is instanced in chunks.
import * as THREE from 'three';
import { BLOCK, PITCH, ROAD, HERITAGE, TRANSIT, isDowntown, DT_N } from './layout.js';
import { mulberry } from '../../game/state.js';

const Y = new THREE.Vector3(0, 1, 0);
const _m = new THREE.Matrix4(), _q = new THREE.Quaternion(), _p = new THREE.Vector3(), _s = new THREE.Vector3(1, 1, 1);
const FACE = { s: 0, n: Math.PI, e: Math.PI / 2, w: -Math.PI / 2 };
const IN = 41.5;                    // building faces stay inside +-IN of the block centre (sidewalk and walkers beyond)
const FACADE = /^dt_(glass_(blue|teal|silver|dark|bronze|green)|ribbon|precast|punched|brick|stone|limestone|derelict|shop)/;

// block plans: rows of designs per plot strip (first that fits wins, the rest of the list is tried in order)
const PLAN = {
  // transit mall row (bz -2): N half faces the tracks (south), S half faces north
  '-2,-2': { N: ['DT_residential', 'DT_hist_terracotta', 'DT_hist_brick'], S: ['DT_parkade', 'DT_hist_brick_dark', 'DT_derelict'] },
  '-1,-2': { N: ['DT_crown', 'DT_midglass', 'DT_hist_brick'], S: ['DT_slab70', 'DT_hist_sandstone', 'DT_hist_brick'] },
  '0,-2': { N: ['DT_midglass', 'DT_residential', 'DT_hist_brick_dark'], S: ['DT_hist_bank', 'DT_slab70', 'DT_hist_brick'] },
  '1,-2': { N: ['DT_residential', 'DT_hist_brick_dark', 'DT_hist_sandstone'], S: ['DT_parkade', 'DT_hist_terracotta', 'DT_hist_brick'] },
  // heritage avenue row (bz -1)
  '-2,-1': { N: ['DT_ribbed', 'DT_hist_brick', 'DT_hist_terracotta', 'DT_hist_sandstone'], S: ['DT_hist_sandstone', 'DT_hist_brick_dark', 'DT_derelict', 'DT_hist_brick', 'DT_hist_terracotta'] },
  '-1,-1': { N: ['DT_hist_bank', 'DT_hist_brick', 'DT_crown', 'DT_hist_brick_dark'], S: ['DT_slab70', 'DT_hist_terracotta', 'DT_hist_sandstone', 'DT_hist_brick'] },
  '0,-1': { N: ['DT_hist_sandstone', 'DT_ribbed_warm', 'DT_hist_brick', 'DT_hist_brick_dark'], S: ['DT_hist_terracotta', 'DT_hist_bank', 'DT_derelict', 'DT_hist_brick'] },
  '1,-1': { N: ['DT_ribbed', 'DT_hist_brick', 'DT_hist_sandstone', 'DT_hist_brick_dark'], S: ['DT_hist_brick_dark', 'DT_slab70', 'DT_hist_sandstone'] },
  '2,-1': { N: ['DT_hist_terracotta', 'DT_residential', 'DT_hist_brick', 'DT_hist_sandstone'], S: ['DT_hist_brick', 'DT_hist_sandstone', 'DT_derelict', 'DT_hist_brick_dark'] },
  // fringe row (bz 2): lower mid-rises and old blocks
  '-2,2': { N: ['DT_midglass', 'DT_hist_brick', 'DT_hist_brick_dark'], S: ['DT_residential', 'DT_hist_terracotta', 'DT_hist_sandstone'] },
  '-1,2': { N: ['DT_hotel', 'DT_hist_brick'], S: ['DT_parkade', 'DT_hist_brick_dark', 'DT_hist_brick'] },
  '0,2': { N: ['DT_residential', 'DT_hist_sandstone', 'DT_hist_brick'], S: ['DT_midglass', 'DT_derelict', 'DT_hist_brick'] },
  '1,2': { N: ['DT_hist_terracotta', 'DT_slab70', 'DT_hist_brick_dark'], S: ['DT_residential', 'DT_hist_brick', 'DT_hist_sandstone'] },
  '2,2': { N: ['DT_parkade', 'DT_hist_brick', 'DT_hist_sandstone'], S: ['DT_midglass', 'DT_hist_sandstone', 'DT_hist_brick_dark'] },
};
// cranes on the construction sites: design -> [local x, local z, mast]
const CRANES = { DT_construction: [19.5, -19.5, 'DT_crane_mast_a', 96], DT_construction_b: [11, -11, 'DT_crane_mast_b', 48] };

export class Downtown {
  // helpers: { instanceKit, kitColliders } from earth.js
  constructor(world, helpers) {
    this.w = world; this.g = world.g; this.scene = world.scene; this.col = world.collision; this.h = helpers;
    const A = this.g.assets;
    this.kit = A.models.downtown.scene; this.street = A.models.downtown_street.scene;
    this.kit.updateMatrixWorld(true); this.street.updateMatrixWorld(true);
    this.time = { value: 0 };
    for (const k of [this.kit, this.street]) k.traverse(o => { if (o.isMesh) for (const m of [].concat(o.material)) this.prepMaterial(m); });
    this.designs = new Map();
    for (const r of this.kit.children) {
      if (!/^DT_/.test(r.name) || /_lod$/.test(r.name)) continue;
      const meta = JSON.parse(r.userData.dt || '{}');
      const box = this.localBox(r);
      this.designs.set(r.name, { name: r.name, root: r, lod: this.kit.getObjectByName(r.name + '_lod'), meta, box, list: [] });
    }
    this.placed = []; this.paths = []; this.skywalks = []; this.footprints = []; this.cranes = []; this.trams = [];
    this.furn = {};             // street kit name -> matrices
    this.rnd = mulberry(1912);
  }

  prepMaterial(m) {
    if (m.userData.dt) return; m.userData.dt = true;
    const n = m.name || '';
    if (FACADE.test(n) && m.metalnessMap) {
      // the _m map: R lit-window mask (night glow), G roughness, B metalness
      const glass = /glass/.test(n);
      m.emissiveMap = m.metalnessMap; m.emissive = new THREE.Color(1, .8, .55); m.emissiveIntensity = glass ? .09 : .16;     // golden hour: a few warm windows, not a lantern
      m.envMapIntensity = glass ? 1.55 : .55;
      m.onBeforeCompile = sh => {
        sh.fragmentShader = sh.fragmentShader.replace('#include <emissivemap_fragment>',
          '#ifdef USE_EMISSIVEMAP\n  totalEmissiveRadiance *= texture2D( emissiveMap, vEmissiveMapUv ).r;\n#endif');
      };
      m.customProgramCacheKey = () => 'dtfacade';
      m.needsUpdate = true;
    } else if (n === 'dt_plain_glow') {
      // merged emissive parts (crown lights, signs, lamps): the glow takes the vertex colour
      m.onBeforeCompile = sh => {
        sh.fragmentShader = sh.fragmentShader.replace('#include <emissivemap_fragment>', '#include <emissivemap_fragment>\n#ifdef USE_COLOR\n  totalEmissiveRadiance *= vColor.rgb;\n#endif');
      };
      m.customProgramCacheKey = () => 'dtglowv';
      m.needsUpdate = true;
    } else if (n === 'dt_plain_metal') {
      m.envMapIntensity = 1.1;
    } else if (/^dt_lattice/.test(n)) {
      m.transparent = false; m.alphaTest = .4; m.depthWrite = true; m.side = THREE.DoubleSide; m.opacity = 1;
    } else if (/^dt_net/.test(n)) {
      m.transparent = true; m.opacity = 1; m.depthWrite = false; m.side = THREE.DoubleSide;
    } else if (/^dt_glass_(clear|rail)/.test(n)) {
      m.side = THREE.DoubleSide; m.envMapIntensity = 1.6;
    } else if (n === 'dt_glass_tinted') {
      m.envMapIntensity = 1.3;
    } else if (/^dt_(metal|steel|bronze|copper)/.test(n)) m.envMapIntensity = 1.1;
  }

  // bounding box of a kit root in its own space
  localBox(root) {
    const inv = new THREE.Matrix4().copy(root.matrixWorld).invert(), bb = new THREE.Box3();
    root.traverse(o => { if (o.isMesh) { o.geometry.computeBoundingBox(); bb.union(o.geometry.boundingBox.clone().applyMatrix4(new THREE.Matrix4().multiplyMatrices(inv, o.matrixWorld))); } });
    return bb;
  }

  // ---------------------------------------------------------------- placement
  // rotated footprint of a design (yaw multiple of 90 degrees): [x0, z0, x1, z1] around the origin
  foot(D, yaw) {
    const b = D.box, c = Math.round(Math.cos(yaw)), s = Math.round(Math.sin(yaw));
    const xs = [], zs = [];
    for (const x of [b.min.x, b.max.x]) for (const z of [b.min.z, b.max.z]) { xs.push(x * c + z * s); zs.push(-x * s + z * c); }
    return [Math.min(...xs), Math.min(...zs), Math.max(...xs), Math.max(...zs)];
  }

  overlaps(r, pad = .6) { return this.placed.some(p => r[0] < p.rect[2] + pad && r[2] > p.rect[0] - pad && r[1] < p.rect[3] + pad && r[3] > p.rect[1] - pad); }

  // place a design so its footprint's centre is at (x, z), front toward `face`
  put(name, x, z, face, blk) {
    const D = this.designs.get(name); if (!D) return null;
    const yaw = FACE[face], f = this.foot(D, yaw);
    const ox = x - (f[0] + f[2]) / 2, oz = z - (f[1] + f[3]) / 2;
    const rect = [f[0] + ox, f[1] + oz, f[2] + ox, f[3] + oz];
    if (this.overlaps(rect)) return null;
    if (blk && (rect[0] < blk[0] - IN - .05 || rect[2] > blk[0] + IN + .05 || rect[1] < blk[1] - IN - .05 || rect[3] > blk[1] + IN + .05)) return null;
    const mat = new THREE.Matrix4().compose(_p.set(ox, 0, oz), _q.setFromAxisAngle(Y, yaw), _s.set(1, 1, 1));
    D.list.push(mat);
    const c = Math.round(Math.cos(yaw)), s = Math.round(Math.sin(yaw));
    for (const b of D.meta.col || []) {
      const xs = [b[0] * c + b[2] * s, b[3] * c + b[5] * s, b[0] * c + b[5] * s, b[3] * c + b[2] * s];
      const zs = [-b[0] * s + b[2] * c, -b[3] * s + b[5] * c, -b[0] * s + b[5] * c, -b[3] * s + b[2] * c];
      this.col.add([Math.min(...xs) + ox, b[1], Math.min(...zs) + oz, Math.max(...xs) + ox, b[4], Math.max(...zs) + oz], 'building');
    }
    const P = { name, rect, h: D.meta.h || D.box.max.y, yaw, x: ox, z: oz, kind: D.meta.kind, face, blk };
    this.placed.push(P); this.footprints.push(rect);
    if (CRANES[name]) this.addCrane(P, ...CRANES[name]);
    return P;
  }

  // fill a strip along x (faces s / n) or z (faces e / w) with the first designs of `names` that fit; front edge at `front`
  fillRow(a0, a1, front, depth, face, names, blk, gap = 1.2) {
    let cur = a0;
    const alongX = face === 's' || face === 'n', out = [];
    for (const name of names) {
      const D = this.designs.get(name); if (!D) continue;
      const f = this.foot(D, FACE[face]), wid = alongX ? f[2] - f[0] : f[3] - f[1], dep = alongX ? f[3] - f[1] : f[2] - f[0];
      if (dep > depth + .01 || cur + wid > a1 + .01) continue;
      const c = cur + wid / 2, sgn = face === 's' || face === 'e' ? -1 : 1, d = front + sgn * dep / 2;
      const P = alongX ? this.put(name, c, d, face, blk) : this.put(name, d, c, face, blk);
      if (P) { out.push(P); cur += wid + gap + this.rnd() * 1.5; }
    }
    // a leftover gap at the end of the strip becomes a pocket plaza
    if (a1 - cur >= 12) {
      const dep = Math.min(depth, 22), sgn = face === 's' || face === 'e' ? -1 : 1, f0 = front, f1 = front + sgn * dep;
      const r = alongX ? [cur, Math.min(f0, f1), a1, Math.max(f0, f1)] : [Math.min(f0, f1), cur, Math.max(f0, f1), a1];
      if (!this.overlaps(r, .2)) (this.pockets = this.pockets || []).push(r);
    }
    return { used: cur, out };
  }

  build() {
    const r = this.rnd;
    const blocks = [];
    for (let bx = -DT_N; bx <= DT_N; bx++) for (let bz = -DT_N; bz <= DT_N; bz++) if (isDowntown(bx, bz)) blocks.push([bx, bz]);
    this.plazas = [];
    for (const [bx, bz] of blocks) {
      const cx = bx * PITCH, cz = bz * PITCH, key = bx + ',' + bz, blk = [cx, cz], plan = PLAN[key];
      const transit = cz === TRANSIT.z && cx > TRANSIT.x0 && cx < TRANSIT.x1, heritage = cz === HERITAGE.z;
      if (plan) {
        const shuffled = l => {          // first stays first; Fisher-Yates on the rest (same result in every JS engine)
          const t = l.slice(1);
          for (let i = t.length - 1; i > 0; i--) { const j = Math.floor(r() * (i + 1)); [t[i], t[j]] = [t[j], t[i]]; }
          return [l[0], ...t];
        };
        if (transit || heritage) {      // split by the mid-block avenue: both halves face it
          const half = transit ? TRANSIT.half + .5 : HERITAGE.half + 1;
          this.fillRow(cx - IN, cx + IN, cz - half, IN - half, 's', shuffled(plan.N), blk);
          this.fillRow(cx - IN, cx + IN, cz + half, IN - half, 'n', shuffled(plan.S), blk);
        } else {                        // back to back, facing the avenues north and south of the block
          this.fillRow(cx - IN, cx + IN, cz - IN, IN - 1, 'n', shuffled(plan.N), blk);
          this.fillRow(cx - IN, cx + IN, cz + IN, IN - 1, 's', shuffled(plan.S), blk);
        }
        continue;
      }
      this.landmarkBlock(key, cx, cz, blk);
    }
    this.buildSkywalks();
    this.buildHeritage();
    this.buildTransit();
    this.buildPlazas();
    this.buildKerbs();
    this.finish();
  }

  // hand-planned blocks with landmarks, plazas and construction sites
  landmarkBlock(key, cx, cz, blk) {
    const P = (n, x, z, f) => this.put(n, cx + x, cz + z, f, blk);
    const row = (names, face = 's', depth = 22) => this.fillRow(cx - IN, cx + IN, face === 's' ? cz + IN : cz - IN, depth, face, names, blk);
    const plaza = (x0, z0, x1, z1, opts = {}) => this.plazas.push({ x0: cx + x0, z0: cz + z0, x1: cx + x1, z1: cz + z1, ...opts });
    switch (key) {
      case '-2,0': P('DT_setback', -19, -16, 's'); P('DT_parkade', 26, -12, 'e'); row(['DT_hist_brick', 'DT_hist_sandstone', 'DT_hist_terracotta', 'DT_hist_brick_dark'], 's', 20); break;
      case '-1,0': P('DT_crescent', 0, -25, 's'); plaza(-41, -7, 41, 41, { sculpture: true, cherry: true, cafe: true }); break;
      case '1,0': P('DT_obs_tower', -21, -20, 's'); P('DT_hotel', 20, -11, 's'); plaza(-41, 3, -2, 41, { kiosk: true, trees: 4 }); break;
      case '2,0': P('DT_twist', -20, -20, 's'); P('DT_residential', 28, -14, 'e'); row(['DT_hist_brick', 'DT_hist_sandstone', 'DT_hist_terracotta', 'DT_derelict', 'DT_hist_brick_dark'], 's', 20); break;
      case '-2,1': P('DT_construction_b', -19, -19, 's'); P('DT_residential', 28, -18, 'e'); row(['DT_midglass', 'DT_hist_brick_dark', 'DT_hist_sandstone'], 's', 28); break;
      case '-1,1': P('DT_glass_tower', 0, -17, 's'); plaza(-41, 9, 41, 41, { fountainless: true, trees: 6, cafe: true, sculpture: false, kiosk: true }); break;
      case '0,1': P('DT_construction', -18, -18, 's'); P('DT_parkade', 26, -14, 'e'); row(['DT_hist_sandstone', 'DT_hist_brick', 'DT_derelict', 'DT_hist_terracotta'], 's', 21); break;
      case '2,1': P('DT_ribbed_warm', -20, -20, 's'); P('DT_slab70', 30, -17, 'e'); row(['DT_residential', 'DT_hist_brick', 'DT_hist_brick_dark'], 's', 24); break;
      default: row(['DT_midglass', 'DT_hist_brick', 'DT_hist_sandstone'], 's', 40);
    }
  }

  addCrane(P, lx, lz, mastName, H) {
    const A = this.g.assets;
    const c = Math.cos(P.yaw), s = Math.sin(P.yaw);
    const x = P.x + lx * c + lz * s, z = P.z - lx * s + lz * c;
    const mast = A.clone('downtown_street', mastName); mast.position.set(x, 0, z); this.scene.add(mast);
    const jib = A.clone('downtown_street', 'DT_crane_jib'); jib.position.set(x, H, z); this.scene.add(jib);
    for (const o of [mast, jib]) o.traverse(q => { if (q.isMesh) { q.castShadow = true; q.receiveShadow = false; } });
    const ph = this.rnd() * 6;
    jib.rotation.y = ph;
    this.cranes.push({ jib, ph, H });
    this.col.add([x - 2.5, 0, z - 2.5, x + 2.5, 1.2, z + 2.5], 'crane');
    this.col.add([x - 1.1, 1.2, z - 1.1, x + 1.1, H, z + 1.1], 'crane');
  }

  // ---------------------------------------------------------------- skywalks (enclosed bridges at ~5 m)
  buildSkywalks() {
    const ok = p => p.h >= 13 && !/construction|obs_tower|derelict/.test(p.name);
    const cand = [];
    const P = this.placed.filter(ok);
    for (let i = 0; i < P.length; i++) for (let j = 0; j < P.length; j++) {
      if (i === j) continue;
      const a = P[i], b = P[j];
      // a west of b across a street or the avenue (gap along x), overlapping in z
      const gx = b.rect[0] - a.rect[2], oz0 = Math.max(a.rect[1], b.rect[1]), oz1 = Math.min(a.rect[3], b.rect[3]);
      if (gx > 18 && gx < 34 && oz1 - oz0 > 9) cand.push({ ax: 'x', a, b, s0: a.rect[2], s1: b.rect[0], c: (oz0 + oz1) / 2 });
      const gz = b.rect[1] - a.rect[3], ox0 = Math.max(a.rect[0], b.rect[0]), ox1 = Math.min(a.rect[2], b.rect[2]);
      if (gz > 12 && gz < 34 && ox1 - ox0 > 9) cand.push({ ax: 'z', a, b, s0: a.rect[3], s1: b.rect[1], c: (ox0 + ox1) / 2 });
    }
    cand.sort((p, q) => (q.a.h + q.b.h) - (p.a.h + p.b.h));
    const used = new Map(), mats = {};
    for (const k of cand) {
      if (this.skywalks.length >= 16) break;
      if ((used.get(k.a) || 0) >= 2 || (used.get(k.b) || 0) >= 2) continue;
      if (this.skywalks.some(s => s.ax === k.ax && Math.abs(s.c - k.c) < 30 && Math.abs((s.s0 + s.s1) / 2 - (k.s0 + k.s1) / 2) < 40)) continue;
      if (k.ax === 'z' && (k.s0 + k.s1) / 2 > TRANSIT.z - 20 && (k.s0 + k.s1) / 2 < TRANSIT.z + 20) continue;
      used.set(k.a, (used.get(k.a) || 0) + 1); used.set(k.b, (used.get(k.b) || 0) + 1);
      const L = k.s1 - k.s0 + 1.2, name = L <= 12 ? 'DT_skywalk_10' : L <= 22 ? 'DT_skywalk_18' : 'DT_skywalk_28', base = +name.split('_')[2];
      const mid = (k.s0 + k.s1) / 2;
      const m = new THREE.Matrix4().compose(k.ax === 'x' ? _p.set(mid, 0, k.c) : _p.set(k.c, 0, mid), _q.setFromAxisAngle(Y, k.ax === 'x' ? 0 : Math.PI / 2), _s.set(L / base, 1, 1));
      (mats[name] = mats[name] || []).push(m);
      const r = k.ax === 'x' ? [k.s0 - .6, k.c - 2.1, k.s1 + .6, k.c + 2.1] : [k.c - 2.1, k.s0 - .6, k.c + 2.1, k.s1 + .6];
      this.col.add([r[0], 4.7, r[1], r[2], 8.5, r[3]], 'skywalk');
      this.skywalks.push({ ...k, rect: r });
    }
    for (const [n, list] of Object.entries(mats)) this.addLod(this.street.getObjectByName(n), this.street.getObjectByName(n + '_lod'), list, 90);
  }

  underSkywalk(x, z, pad = 3) { return this.skywalks.some(s => x > s.rect[0] - pad && x < s.rect[2] + pad && z > s.rect[1] - pad && z < s.rect[3] + pad); }

  // ---------------------------------------------------------------- heritage avenue (car-free, mid-block in row -1)
  buildHeritage() {
    const r = this.rnd, fl = this.w.flora, z = HERITAGE.z, hh = HERITAGE.half;
    for (let bx = -DT_N; bx <= DT_N; bx++) {
      const cx = bx * PITCH;
      this.ground(cx - BLOCK / 2, z - hh - 1, cx + BLOCK / 2, z + hh + 1, 0x8f8a82, .036);
      // walkers on both sides of the avenue
      this.paths.push(this.loop([[cx - 45, z - 4.6], [cx + 45, z - 4.6], [cx + 45, z + 4.6], [cx - 45, z + 4.6]], 3));
      for (let k = 0; k < 5; k++) {
        const x = cx - 36 + k * 18;
        if (this.underSkywalk(x, z, 5)) { this.f('DT_planter', x, z, 0); continue; }
        if (k % 2 === 0) fl.add(['TR_ash_young', 'TR_maple_a', 'TR_birch_c'][k % 3], x, 0, z, r, .62 + r() * .12);
        else if (r() < .5) this.f('DT_planter', x, z, r() < .5 ? 0 : Math.PI);
        else this.f('DT_kiosk', x, z, r() < .5 ? 0 : Math.PI);
        if (k < 4) {
          for (const sz of [-1, 1]) this.bench(x + 9, z + sz * 1.7, sz < 0 ? Math.PI : 0);
          if (!this.underSkywalk(x + 4.5, z, 2)) this.f('DT_banner', x + 4.5, z + (k % 2 ? 2.4 : -2.4), Math.PI / 2);
        }
      }
      for (let k = 0; k < 6; k++) {
        const x = cx - 37.5 + k * 15;
        if (!this.skywalks.some(s => x > s.rect[0] - 3 && x < s.rect[2] + 3 && Math.abs(z - (s.rect[1] + s.rect[3]) / 2) < 12)) this.f('DT_stringlights', x, z, 0, false);
      }
      // cafe tables in front of some shopfronts
      for (const sz of [-1, 1]) for (let k = 0; k < 3; k++) if (r() < .7) {
        const x0 = cx - 30 + k * 26 + r() * 6;
        for (let t = 0; t < 2 + (r() * 2 | 0); t++) this.f('DT_cafe', x0 + t * 2.6, z + sz * 6.6, r() * .4);
      }
      for (const sx of [-1, 1]) this.f('DT_bollards', cx + sx * 43.5, z, Math.PI / 2, true);
      this.f('DT_bikerack', cx + 22, z + 2.2, 0); this.f('DT_bin', cx - 13, z + 2.4, 0); this.f('DT_bin', cx + 31, z - 2.4, 0);
    }
    // zebra crossings where the avenue meets the north-south streets
    for (let i = -DT_N - 1; i <= DT_N; i++) this.zebra((i + .5) * PITCH, z, true);
  }

  // ---------------------------------------------------------------- transit mall: track bed, platforms, catenary, trams
  buildTransit() {
    const z = TRANSIT.z, x0 = TRANSIT.x0 + 1, x1 = TRANSIT.x1 - 1;
    for (let bx = -DT_N; bx <= 1; bx++) this.ground(bx * PITCH - BLOCK / 2, z - TRANSIT.half, bx * PITCH + BLOCK / 2, z + TRANSIT.half, 0x9a948a, .036);
    const trk = [], cat = [];
    const n = Math.ceil((x1 - x0) / 20), step = (x1 - x0) / n;
    for (let k = 0; k < n; k++) {
      const x = x0 + step * (k + .5);
      trk.push(new THREE.Matrix4().compose(_p.set(x, .025, z), _q.identity(), _s.set(step / 20, 1, 1)));
      const dStreet = Math.min(...[-3, -2, -1, 0, 1, 2].map(i => Math.abs(x - (i + .5) * PITCH)));
      if (dStreet > 12) cat.push(new THREE.Matrix4().compose(_p.set(x, 0, z), _q.identity(), _s.set(step / 20, 1, 1)));
    }
    this.addLod(this.street.getObjectByName('DT_track'), this.street.getObjectByName('DT_track_lod'), trk, 70, false);
    this.h.instanceKit(this.scene, this.street.getObjectByName('DT_catenary'), cat, { shadow: false });
    for (const m of cat) { m.decompose(_p, _q, _s); this.col.add([_p.x - .15, 0, _p.z - .15, _p.x + .15, 7.2, _p.z + .15], 'prop'); }
    // stations mid-block at -1 and 1: a platform on each side of the tracks
    const plat = [];
    this.stations = [-PITCH, PITCH];
    for (const sx of this.stations) for (const sz of [-1, 1]) {
      plat.push(new THREE.Matrix4().compose(_p.set(sx, 0, z + sz * 7.3), _q.setFromAxisAngle(Y, sz < 0 ? Math.PI : 0), _s.set(1, 1, 1)));
      this.col.add([sx - 22, 0, z + sz * 7.3 - 2.1, sx + 22, .35, z + sz * 7.3 + 2.1], 'platform');
      this.paths.push(this.loop([[sx - 20, z + sz * 6.4], [sx + 20, z + sz * 6.4], [sx + 20, z + sz * 8.4], [sx - 20, z + sz * 8.4]], 1.5));
    }
    this.addLod(this.street.getObjectByName('DT_platform'), this.street.getObjectByName('DT_platform_lod'), plat, 120);
    for (let bx = -DT_N; bx <= 1; bx++) this.paths.push(this.loop([[bx * PITCH - 45, z - 8.6], [bx * PITCH + 45, z - 8.6], [bx * PITCH + 45, z + 8.6], [bx * PITCH - 45, z + 8.6]], 1.5));
    for (const x of [x0 + 1, x1 - 1]) this.f('DT_bollards', x, z, Math.PI / 2, true);
    for (let i = -DT_N - 1; i <= 1; i++) this.zebra((i + .5) * PITCH, z, true);
    // two trams shuttling between the end stops, pausing at the stations
    const ends = [x0 + 20, x1 - 20];
    for (const [lane, dir, start] of [[-2.2, -1, ends[1]], [2.2, 1, ends[0] + 90]]) {
      const o = this.g.assets.clone('downtown_street', 'DT_tram');
      o.traverse(q => { if (q.isMesh) { q.castShadow = true; q.receiveShadow = true; } });
      o.position.set(start, .03, z + lane); this.scene.add(o);
      const box = new THREE.Box3(); box.tag = 'tram'; this.col.dynamic.push(box);
      this.trams.push({ o, lane, dir, x: start, v: 0, wait: 0, ends, stops: [...this.stations, ...ends], box, z: z + lane });
    }
  }

  updateTram(t, dt) {
    if (t.wait > 0) { t.wait -= dt; if (t.wait <= 0 && (t.x <= t.ends[0] + .5 || t.x >= t.ends[1] - .5)) t.dir = -t.dir; }
    else {
      // next stop ahead in the travel direction
      let next = t.dir > 0 ? t.ends[1] : t.ends[0];
      for (const s of t.stops) if ((s - t.x) * t.dir > .6 && Math.abs(s - t.x) < Math.abs(next - t.x)) next = s;
      const d = Math.abs(next - t.x), vmax = Math.min(12, Math.sqrt(2 * 1.1 * d));
      t.v = Math.min(vmax, t.v + 1.2 * dt);
      t.x += t.dir * t.v * dt;
      if (Math.abs(next - t.x) < .3) { t.x = next; t.v = 0; t.wait = 9 + Math.random() * 5; }
    }
    t.o.position.x = t.x; t.o.rotation.y = 0;
    t.box.min.set(t.x - 18.6, 0, t.z - 1.45); t.box.max.set(t.x + 18.6, 3.7, t.z + 1.45);
  }

  // ---------------------------------------------------------------- plazas
  buildPlazas() {
    const r = this.rnd, fl = this.w.flora;
    for (const p of this.plazas) {
      const cx = (p.x0 + p.x1) / 2, cz = (p.z0 + p.z1) / 2, w = p.x1 - p.x0, d = p.z1 - p.z0;
      this.ground(p.x0, p.z0, p.x1, p.z1, 0xb3aca0, .034);
      if (p.sculpture) this.f('DT_sculpture', cx, cz, r() * 6, true);
      else this.f('DT_kiosk', cx, cz, Math.PI, true);
      const ring = Math.min(w, d) * .32;
      for (let k = 0; k < 8; k++) {
        const a = k / 8 * Math.PI * 2 + .2, x = cx + Math.cos(a) * ring * (w / Math.min(w, d)) * .9, z = cz + Math.sin(a) * ring;
        if (k % 2) this.f('DT_planter', x, z, -a + Math.PI / 2, true);
        else fl.add(p.cherry ? 'cherry' : ['TR_maple_a', 'TR_ash_young', 'TR_birch_c'][k / 2 % 3], x, 0, z, r, .7 + r() * .15);
      }
      for (let k = 0; k < 6; k++) { const a = k / 6 * Math.PI * 2 + .5; this.bench(cx + Math.cos(a) * 6.5, cz + Math.sin(a) * 6.5, -a - Math.PI / 2); }
      if (p.cafe) for (let k = 0; k < 5; k++) this.f('DT_cafe', p.x0 + 4 + k * 3, p.z1 - 6 - (k % 2) * 2.5, r());
      if (p.kiosk && p.sculpture !== false) this.f('DT_kiosk', p.x1 - 5, p.z0 + 5, Math.PI / 2, true);
      this.f('DT_bikerack', p.x0 + 4, p.z0 + 4, 0); this.f('DT_bin', p.x1 - 3, p.z1 - 3, 0);
      this.paths.push(this.loop(Array.from({ length: 12 }, (_, i) => [cx + Math.cos(i / 12 * 6.28) * 11, cz + Math.sin(i / 12 * 6.28) * 11]), 2));
    }
    // pocket plazas in the gaps between buildings: paving, a tree or two, benches, a planter
    for (const [x0, z0, x1, z1] of this.pockets || []) {
      const cx = (x0 + x1) / 2, cz = (z0 + z1) / 2, alongX = x1 - x0 >= z1 - z0;
      this.ground(x0, z0, x1, z1, 0xa59e92, .033);
      const L = alongX ? x1 - x0 : z1 - z0;
      for (let k = 0; k < Math.max(1, Math.floor(L / 12)); k++) {
        const t = (k + .5) / Math.max(1, Math.floor(L / 12)) - .5, x = alongX ? cx + t * L : cx, z = alongX ? cz : cz + t * L;
        if (!this.underSkywalk(x, z, 5)) fl.add(['TR_maple_a', 'TR_ash_young', 'TR_maple_autumn_a'][k % 3], x, 0, z, r, .6 + r() * .15);
        this.bench(alongX ? x + 3 : x + 2, alongX ? z + 2 : z + 3, alongX ? 0 : Math.PI / 2);
      }
      this.f('DT_planter', alongX ? x0 + 2.5 : cx, alongX ? cz : z0 + 2.5, alongX ? Math.PI / 2 : 0, true);
    }
  }

  // ---------------------------------------------------------------- kerbside furniture, signals, crossings
  buildKerbs() {
    const r = this.rnd;
    const lampAt = t => { const u = ((t - 11 + 440) % 34 + 34) % 34; return u < 3 || u > 31; };
    for (let bx = -DT_N; bx <= DT_N; bx++) for (let bz = -DT_N; bz <= DT_N; bz++) {
      if (!isDowntown(bx, bz)) continue;
      const cx = bx * PITCH, cz = bz * PITCH, e = 45.5;
      const sides = [[0, -1], [0, 1], [-1, 0], [1, 0]];
      for (const [sx, sz] of sides) {
        for (let k = 0; k < 4; k++) {
          const t = -30 + k * 20 + (r() - .5) * 6;
          const x = sx ? cx + sx * e : cx + t, z = sz ? cz + sz * e : cz + t;
          if (lampAt(sx ? z : x)) continue;
          if (Math.abs(z - HERITAGE.z) < 9 || Math.abs(z - TRANSIT.z) < 11) continue;
          if (this.skywalks.some(s => x > s.rect[0] - 2 && x < s.rect[2] + 2 && z > s.rect[1] - 2 && z < s.rect[3] + 2)) continue;
          const yaw = sx ? (sx > 0 ? -Math.PI / 2 : Math.PI / 2) : (sz > 0 ? Math.PI : 0);
          const pick = r();
          if (pick < .14 && k === 1) this.f('DT_shelter', x - (sx ? sx * .4 : 0), z - (sz ? sz * .4 : 0), yaw, true);
          else if (pick < .4) this.f('DT_bin', x, z, yaw);
          else if (pick < .55) this.f('DT_hydrant', x, z, yaw);
          else if (pick < .7) this.f('DT_bikerack', sx ? x : x, z, sx ? 0 : Math.PI / 2);
        }
      }
    }
    // signals on two opposite corners of every downtown crossing, zebra crossings on all four arms
    for (let i = -DT_N - 1; i <= DT_N; i++) for (let j = -DT_N - 1; j <= DT_N; j++) {
      const x = (i + .5) * PITCH, z = (j + .5) * PITCH;
      if (j <= -3) continue;
      this.f('DT_signal', x - 10.4, z - 10.4, 0, true);
      this.f('DT_signal', x + 10.4, z + 10.4, Math.PI, true);
      this.zebra(x, z - 12.5, true); this.zebra(x, z + 12.5, true);
      this.zebra(x - 12.5, z, false); this.zebra(x + 12.5, z, false);
    }
  }

  zebra(x, z, acrossNS, half = ROAD / 2 - 1) {
    // stripes across a road at (x, z): acrossNS = the road runs north-south (stripes lie along x)
    this.zebras = this.zebras || [];
    const n = Math.floor(half / 1.6);
    for (let k = -n; k <= n; k++) this.zebras.push(acrossNS ? [x + k * 1.6, z, 0] : [x, z + k * 1.6, 1]);
  }

  // ---------------------------------------------------------------- helpers
  f(name, x, z, yaw = 0, solid = undefined) {
    (this.furn[name] = this.furn[name] || []).push({ m: new THREE.Matrix4().compose(_p.set(x, 0, z), _q.setFromAxisAngle(Y, yaw), _s.set(1, 1, 1)), solid });
  }

  bench(x, z, yaw) { (this.benches = this.benches || []).push(new THREE.Matrix4().compose(_p.set(x, 0, z), _q.setFromAxisAngle(Y, yaw), _s.set(1, 1, 1))); }

  loop(xz, w = 1) {
    const pts = xz.map(([x, z]) => new THREE.Vector3(x, 0, z));
    let total = 0; for (let i = 0; i < pts.length; i++) total += pts[i].distanceTo(pts[(i + 1) % pts.length]);
    return { pts, total, w };
  }

  // paved ground (avenues, plazas): planes collected per tint and merged into one mesh each in finish()
  ground(x0, z0, x1, z1, tint, y) {
    const w = x1 - x0, d = z1 - z0, g = new THREE.PlaneGeometry(w, d);
    g.rotateX(-Math.PI / 2); g.translate((x0 + x1) / 2, y, (z0 + z1) / 2);
    const uv = g.attributes.uv; for (let i = 0; i < uv.count; i++) uv.setXY(i, uv.getX(i) * w / 6, uv.getY(i) * d / 6);   // 6 m paver tile
    ((this.grounds = this.grounds || {})[tint] = this.grounds[tint] || []).push(g);
  }

  buildGrounds() {
    let src = null; this.street.traverse(o => { if (o.isMesh && o.material.name === 'dt_pavers') src = o.material; });
    for (const [tint, list] of Object.entries(this.grounds || {})) {
      const mat = new THREE.MeshStandardMaterial({ color: +tint, roughness: .78, envMapIntensity: .5, polygonOffset: true, polygonOffsetFactor: -1, polygonOffsetUnits: -2 });
      if (src && src.map) { mat.map = src.map; src.map.wrapS = src.map.wrapT = THREE.RepeatWrapping; }
      if (src && src.normalMap) { mat.normalMap = src.normalMap; src.normalMap.wrapS = src.normalMap.wrapT = THREE.RepeatWrapping; }
      const pos = [], uv = [], nrm = [], idx = []; let base = 0;
      for (const g of list) {
        pos.push(...g.attributes.position.array); uv.push(...g.attributes.uv.array); nrm.push(...g.attributes.normal.array);
        for (const i of g.index.array) idx.push(i + base);
        base += g.attributes.position.count; g.dispose();
      }
      const geo = new THREE.BufferGeometry();
      geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); geo.setAttribute('normal', new THREE.Float32BufferAttribute(nrm, 3));
      geo.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2)); geo.setIndex(idx);
      const m = new THREE.Mesh(geo, mat); m.receiveShadow = true; this.scene.add(m);
    }
  }

  // hero / low-detail instanced pair for a root (shared instance buffer per tier, buckets by distance)
  addLod(hi, lo, list, near = 160, shadow = true, loShadow = shadow) {
    if (!hi || !list.length) return;
    const parts = root => {
      if (!root) return null;
      const inv = new THREE.Matrix4().copy(root.matrixWorld).invert(), out = [];
      root.traverse(o => {
        if (!o.isMesh) return;
        const local = new THREE.Matrix4().multiplyMatrices(inv, o.matrixWorld);
        let geo = o.geometry; if (!local.equals(new THREE.Matrix4())) geo = geo.clone().applyMatrix4(local);
        geo.userData.shared = true;
        out.push({ geo, mat: o.material });
      });
      return out;
    };
    const box = this.localBox(hi), size = box.getSize(new THREE.Vector3()), ctr = box.getCenter(new THREE.Vector3());
    const n = list.length;
    const set = { list, near, radius: size.length() / 2, pos: list.map(m => ctr.clone().applyMatrix4(m)), tiers: [] };
    for (const [t, root] of [[0, hi], [1, lo]]) {
      const P = parts(root); if (!P) { set.tiers.push(null); continue; }
      const attr = new THREE.InstancedBufferAttribute(new Float32Array(n * 16), 16); attr.setUsage(THREE.DynamicDrawUsage);
      const ms = P.map(({ geo, mat }) => {
        const im = new THREE.InstancedMesh(geo, mat, n);
        im.instanceMatrix = attr; im.count = 0; im.visible = false;
        im.castShadow = (t ? loShadow : shadow) && !/glass|glow|net/.test(mat.name); im.receiveShadow = true;
        this.scene.add(im); return im;
      });
      set.tiers.push({ attr, ms });
    }
    (this.lods = this.lods || []).push(set);
  }

  finish() {
    this.buildGrounds();
    for (const D of this.designs.values()) if (D.list.length) this.addLod(D.root, D.lod, D.list, 150 + (D.meta.h || 40) * .4, true, (D.meta.h || 0) > 50);
    // street furniture: instanced in chunks, solid pieces get colliders
    const props = this.g.assets.models.props_world.scene;
    for (const [name, items] of Object.entries(this.furn)) {
      const root = this.street.getObjectByName(name); if (!root) continue;
      const mats = items.map(i => i.m);
      this.h.instanceKit(this.scene, root, mats, { shadow: !/bin|hydrant|bollards|stringlights|bikerack|cafe|banner|signal/.test(name) });
      const meta = JSON.parse(root.userData.dt || '{}');
      for (const it of items) {
        if (it.solid === false) continue;
        if (/stringlights|banner/.test(name)) { if (name === 'DT_banner') { it.m.decompose(_p, _q, _s); this.col.add([_p.x - .12, 0, _p.z - .12, _p.x + .12, 6, _p.z + .12], 'prop'); } continue; }
        if (/signal/.test(name)) { it.m.decompose(_p, _q, _s); this.col.add([_p.x - .15, 0, _p.z - .15, _p.x + .15, 6.2, _p.z + .15], 'prop'); continue; }
        if (/bollards/.test(name)) { this.h.kitColliders(this.col, root, [it.m], { box: true }, 'prop'); continue; }
        if (meta.col && meta.col.length || /kiosk|shelter|planter|cafe|sculpture|bin|hydrant|bikerack/.test(name)) this.h.kitColliders(this.col, root, [it.m], { box: true }, 'prop');
      }
    }
    if (this.benches && this.benches.length) {
      const b = props.getObjectByName('PR_bench');
      this.h.instanceKit(this.scene, b, this.benches, { shadow: false });
      this.h.kitColliders(this.col, b, this.benches, { box: true }, 'bench');
      for (const m of this.benches) {
        const c = new THREE.Vector3(), q = new THREE.Quaternion(), sc = new THREE.Vector3(); m.decompose(c, q, sc);
        const yaw = new THREE.Euler().setFromQuaternion(q, 'YXZ').y, side = new THREE.Vector3(Math.cos(yaw), 0, -Math.sin(yaw));
        for (const k of [-.45, .45]) this.w.addSeat(c.clone().addScaledVector(side, k), yaw, 'Bench');
      }
    }
    if (this.zebras && this.zebras.length) {
      const geo = new THREE.PlaneGeometry(.8, 1); geo.rotateX(-Math.PI / 2);
      const im = new THREE.InstancedMesh(geo, this.w.lineMat, this.zebras.length);
      this.zebras.forEach(([x, z, rot], i) => im.setMatrixAt(i, _m.compose(_p.set(x, .043, z), _q.setFromAxisAngle(Y, rot ? Math.PI / 2 : 0), _s.set(1, 1, 4))));
      im.receiveShadow = true; im.computeBoundingSphere(); this.scene.add(im);
    }
    this.update(this.g.camera, 0, true);
  }

  // ---------------------------------------------------------------- per frame
  update(cam, dt, force = false) {
    this.time.value += dt;
    for (const c of this.cranes) c.jib.rotation.y = c.ph + 1.3 * Math.sin(this.time.value * .045 + c.ph) + this.time.value * .012;
    for (const t of this.trams) this.updateTram(t, dt);
    this.timer = (this.timer || 0) - dt;
    const p = cam.position;
    if (!force && this.timer > 0 && this.last && p.distanceToSquared(this.last) < 36) return;
    this.timer = .4; this.last = (this.last || new THREE.Vector3()).copy(p);
    const q = this.g.renderer.q || {}, k = .55 + .45 * (q.draw || .8);
    for (const S of this.lods || []) {
      const cnt = [0, 0], H = S.tiers;
      const n2 = (S.near * k + S.radius * .5) ** 2;
      for (let i = 0; i < S.list.length; i++) {
        const c = S.pos[i], d2 = (c.x - p.x) ** 2 + (c.z - p.z) ** 2 + (c.y - p.y) ** 2 * .25;
        let t = d2 < n2 ? 0 : 1;
        if (!H[t]) t = H[0] ? 0 : 1;
        S.list[i].toArray(H[t].attr.array, cnt[t]++ * 16);
      }
      for (let t = 0; t < 2; t++) {
        if (!H[t]) continue;
        H[t].attr.needsUpdate = true;
        for (const im of H[t].ms) { im.count = cnt[t]; im.visible = cnt[t] > 0; im.boundingSphere = null; if (cnt[t]) im.computeBoundingSphere(); }
      }
    }
  }

  // for tests / debugging
  stats() {
    const per = {};
    for (const D of this.designs.values()) if (D.list.length) per[D.name] = D.list.length;
    return { designs: Object.keys(per).length, buildings: this.placed.length, per, skywalks: this.skywalks.length, cranes: this.cranes.length, trams: this.trams.length, plazas: this.plazas.length, pockets: (this.pockets || []).length };
  }
}
