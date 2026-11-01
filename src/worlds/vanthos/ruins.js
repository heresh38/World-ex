// What is left of VANTHOS: the ruin designs of tools/blender/ruins.py (vanthos_ruins.glb, roots VR_*) placed across the
// city and drawn as instanced meshes. Standing ruins have a hero and a far tier (VR_x / VR_x_lod) that cross-fade with
// the screen-door dither of core/lodfade.js; rubble, wrecks and weeds have one tier that fades out with distance.
// Every root carries extras `vr`: colliders (AABBs, three space, fronts +z), an optional rubble `mound` (folded into the
// world's height function so players and creatures walk over it) and `spots` (sheltered ground-floor points, perches,
// places where something grows, the odd dead lamp). place() turns those into world space for the districts.
import * as THREE from 'three';
import { fadeMaterial, fadeGeometry, fadeAttr } from '../../core/lodfade.js';

const _m = new THREE.Matrix4(), _q = new THREE.Quaternion(), _p = new THREE.Vector3(), _s = new THREE.Vector3(), _v = new THREE.Vector3();
const Y = new THREE.Vector3(0, 1, 0);
const BAND = .28;
// per kind: hero / far switch distance (m) and far cull (m); fog hides everything past ~700 m
const RANGE = { tower: [260, 1100], mid: [190, 900], hall: [170, 800], low: [150, 700], stub: [0, 330], rubble: [150, 520], prop: [0, 210], weeds: [0, 70] };
const MOUND_CELL = 64;

export class Ruins {
  constructor(world) {
    this.w = world; this.g = world.g; this.scene = world.scene;
    const kit = this.g.assets.models.vanthos_ruins.scene;
    kit.updateMatrixWorld(true);
    this.designs = new Map(); this.mounds = []; this.mgrid = new Map(); this.glowMats = [];
    this.spots = { inside: [], perch: [], tree: [], glow: [] };
    for (const root of kit.children) {
      if (!/^VR_/.test(root.name) || /_lod$/.test(root.name)) continue;
      const meta = JSON.parse(root.userData.vr || '{}');
      this.designs.set(root.name, { name: root.name, root, lod: kit.getObjectByName(root.name + '_lod'), meta, list: [] });
    }
    kit.traverse(o => { if (o.isMesh) for (const m of [].concat(o.material)) this.prep(m); });
  }

  prep(m) {
    if (m.userData.vr) return; m.userData.vr = true;
    m.envMapIntensity = .35;
    if (/^vr_(ivy|weeds)$/.test(m.name)) {
      m.transparent = false; m.depthWrite = true; m.alphaTest = .45; m.side = THREE.DoubleSide; m.shadowSide = THREE.DoubleSide; m.roughness = .9; m.metalness = 0;
    }
    if (m.name === 'vr_glow') { m.emissiveIntensity = .2; this.glowMats.push(m); }
    m.needsUpdate = true;
  }

  has(name) { return this.designs.has(name); }
  meta(name) { const D = this.designs.get(name); return D && D.meta; }

  // footprint half sizes after a yaw (quarter turns swap w / d)
  half(name, rot) { const M = this.meta(name), q = Math.abs(Math.round(rot / (Math.PI / 2))) % 2; return q ? [M.d / 2, M.w / 2] : [M.w / 2, M.d / 2]; }

  // place a design: y defaults to the ground at x/z; returns {x, z, rot, meta, top}
  place(name, x, z, rot = 0, o = {}) {
    const D = this.designs.get(name); if (!D) return null;
    const y = o.y !== undefined ? o.y : this.w.groundBase(x, z);
    const s = o.scale || 1;
    const M = new THREE.Matrix4().compose(_p.set(x, y, z), _q.setFromAxisAngle(Y, rot), _s.set(s, s, s));
    D.list.push(M);
    const meta = D.meta, c = Math.cos(rot), sn = Math.sin(rot);
    const tf = (lx, ly, lz) => [x + (lx * c + lz * sn) * s, y + ly * s, z + (-lx * sn + lz * c) * s];
    if (o.collide !== false) for (const b of meta.col || []) {
      // a rotated AABB: the box around its four rotated corners (exact for quarter turns)
      let x0 = 1e9, z0 = 1e9, x1 = -1e9, z1 = -1e9;
      for (const [lx, lz] of [[b[0], b[2]], [b[3], b[2]], [b[3], b[5]], [b[0], b[5]]]) { const [px, , pz] = tf(lx, 0, lz); x0 = Math.min(x0, px); x1 = Math.max(x1, px); z0 = Math.min(z0, pz); z1 = Math.max(z1, pz); }
      this.w.collision.add([x0, y + b[1] * s - (b[1] < .1 ? 2 : 0), z0, x1, y + b[4] * s, z1], 'ruin');
    }
    if (meta.mound) {
      const [H, rx, rz, cx, cz] = meta.mound, [mx, , mz] = tf(cx, 0, cz);
      this.addMound(mx, y, mz, H * s, rx * s, rz * s, rot);
    }
    const spots = {};
    for (const k in meta.spots || {}) for (const sp of meta.spots[k]) { const [px, py, pz] = tf(...sp), v = new THREE.Vector3(px, py, pz); this.spots[k].push(v); (spots[k] = spots[k] || []).push(v); }
    return { x, z, rot, meta, y, spots, top: y + (meta.h || 0) * s };
  }

  // ---------------------------------------------------------------- rubble surfaces in the height function
  addMound(x, y, z, H, rx, rz, rot) {
    const m = { x, y, z, H, rx, rz, c: Math.cos(rot), s: Math.sin(rot) }, R = Math.max(rx, rz);
    this.mounds.push(m);
    for (let i = Math.floor((x - R) / MOUND_CELL); i <= Math.floor((x + R) / MOUND_CELL); i++)
      for (let j = Math.floor((z - R) / MOUND_CELL); j <= Math.floor((z + R) / MOUND_CELL); j++) {
        const k = i * 73856093 ^ j * 19349663; let l = this.mgrid.get(k); if (!l) this.mgrid.set(k, l = []); l.push(m);
      }
  }

  moundAt(x, z) {
    const l = this.mgrid.get(Math.floor(x / MOUND_CELL) * 73856093 ^ Math.floor(z / MOUND_CELL) * 19349663);
    if (!l) return -Infinity;
    let best = -Infinity;
    for (const m of l) {
      const dx = x - m.x, dz = z - m.z, lx = dx * m.c - dz * m.s, lz = dx * m.s + dz * m.c;
      const d = Math.hypot(lx / m.rx, lz / m.rz);
      if (d >= 1) continue;
      const c = Math.cos(d * Math.PI / 2), h = m.y + m.H * c * c - .06;
      if (h > best) best = h;
    }
    return best;
  }

  // ---------------------------------------------------------------- instancing
  parts(root) {
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
  }

  finish() {
    this.sets = [];
    for (const D of this.designs.values()) {
      const n = D.list.length; if (!n) continue;
      const kind = D.meta.kind || 'prop', [near, far] = RANGE[kind] || RANGE.prop;
      const set = { D, kind, near: D.lod ? near : 0, far, pos: D.list.map(m => new THREE.Vector3().setFromMatrixPosition(m)), tiers: [], r: Math.hypot(D.meta.w || 4, D.meta.d || 4) / 2 };
      for (const [t, root] of [[0, D.root], [1, D.lod]]) {
        const P = this.parts(root); if (!P) { set.tiers.push(null); continue; }
        const attr = new THREE.InstancedBufferAttribute(new Float32Array(n * 16), 16); attr.setUsage(THREE.DynamicDrawUsage);
        const fade = fadeAttr(n);
        const ms = P.map(({ geo, mat }) => {
          const fm = fadeMaterial(mat);
          if (mat.name === 'vr_glow' && !this.glowMats.includes(fm)) this.glowMats.push(fm);
          const im = new THREE.InstancedMesh(fadeGeometry(geo, fade), fm, n);
          im.instanceMatrix = attr; im.count = 0; im.visible = false; im.frustumCulled = true;
          im.castShadow = kind !== 'weeds' && !/^vr_(weeds|glow)$/.test(mat.name) && (t === 0 || kind === 'tower'); im.receiveShadow = kind !== 'weeds';
          this.scene.add(im); return im;
        });
        set.tiers.push({ attr, fade, ms });
      }
      this.sets.push(set);
    }
    this.update(this.g.camera, 0, true);
  }

  update(cam, dt, force = false) {
    this.t = (this.t || 0) + dt;
    // dead lamps: almost always off; once in a while a weak red sputter
    if (this.glowMats.length) { const f = Math.sin(this.t * 31) > .7 && Math.sin(this.t * .37) > .85 ? 1.4 : .08; for (const m of this.glowMats) m.emissiveIntensity = f; }
    this.timer = (this.timer || 0) - dt;
    const p = cam.position;
    if (!force && this.timer > 0 && this.last && p.distanceToSquared(this.last) < 16) return;
    this.timer = .4; this.last = (this.last || new THREE.Vector3()).copy(p);
    const q = this.g.renderer.q || {}, k = (.55 + .45 * (q.draw || .8)) * (this.g.renderer.touch ? .85 : 1), MARGIN = 8;
    for (const S of this.sets || []) {
      const cnt = [0, 0], H = S.tiers, L = S.D.list;
      const e = S.near * k + S.r * .5, s = e * (1 - BAND), far = S.far * (S.kind === 'weeds' ? 1 : k) + S.r, fs = far * (1 - BAND * .6);
      const put = (t, i, a, b) => { const o = cnt[t]++; L[i].toArray(H[t].attr.array, o * 16); const F = H[t].fade.array; F[o * 3] = a; F[o * 3 + 1] = b; F[o * 3 + 2] = 0; };
      for (let i = 0; i < L.length; i++) {
        const c = S.pos[i], d = Math.hypot(c.x - p.x, c.z - p.z);
        if (d > far + MARGIN) continue;
        if (!H[1]) { put(0, i, fs, far); continue; }
        if (d < e + MARGIN) put(0, i, s, e);
        if (d > s - MARGIN) put(1, i, d > fs - MARGIN ? fs : -s, d > fs - MARGIN ? far : -e);
      }
      for (let t = 0; t < 2; t++) {
        if (!H[t]) continue;
        H[t].attr.needsUpdate = true; H[t].fade.needsUpdate = true;
        H[t].attr.clearUpdateRanges(); H[t].attr.addUpdateRange(0, cnt[t] * 16);
        H[t].fade.clearUpdateRanges(); H[t].fade.addUpdateRange(0, cnt[t] * 3);
        for (const im of H[t].ms) { im.count = cnt[t]; im.visible = cnt[t] > 0; im.boundingSphere = null; if (cnt[t]) im.computeBoundingSphere(); }
      }
    }
  }

  stats() {
    const per = {}; let n = 0;
    for (const D of this.designs.values()) if (D.list.length) { per[D.name] = D.list.length; n += D.list.length; }
    return { placed: n, per, mounds: this.mounds.length, spots: Object.fromEntries(Object.entries(this.spots).map(([k, v]) => [k, v.length])) };
  }
}
