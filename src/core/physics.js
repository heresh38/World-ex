// Lightweight collision world: static AABBs in a spatial hash + optional terrain height function.
// Characters are vertical capsules (radius r, height h) resolved against boxes in XZ with step-up.
import * as THREE from 'three';

const CELL = 16;
const _ray = new THREE.Ray(), _v = new THREE.Vector3();

export class CollisionWorld {
  constructor() { this.clear(); }

  clear() {
    this.boxes = []; this.grid = new Map(); this.terrain = null; this.floorY = -Infinity; this.dynamic = [];
  }

  key(ix, iz) { return ix * 73856093 ^ iz * 19349663; }

  add(box, tag = null) {
    const b = box.isBox3 ? box : new THREE.Box3(new THREE.Vector3(box[0], box[1], box[2]), new THREE.Vector3(box[3], box[4], box[5]));
    b.tag = tag; b.id = this.boxes.length;
    this.boxes.push(b);
    for (let ix = Math.floor(b.min.x / CELL); ix <= Math.floor(b.max.x / CELL); ix++)
      for (let iz = Math.floor(b.min.z / CELL); iz <= Math.floor(b.max.z / CELL); iz++) {
        const k = this.key(ix, iz); let l = this.grid.get(k); if (!l) this.grid.set(k, l = []); l.push(b);
      }
    return b;
  }

  remove(b) {
    if (!b) return;
    for (const l of this.grid.values()) { const i = l.indexOf(b); if (i >= 0) l.splice(i, 1); }
    const i = this.boxes.indexOf(b); if (i >= 0) this.boxes.splice(i, 1);
  }

  addObject(obj, tag, shrink = 0) {
    const b = new THREE.Box3().setFromObject(obj);
    if (shrink) b.expandByVector(new THREE.Vector3(-shrink, 0, -shrink));
    return this.add(b, tag);
  }

  near(x, z, r) {
    const out = new Set();
    for (let ix = Math.floor((x - r) / CELL); ix <= Math.floor((x + r) / CELL); ix++)
      for (let iz = Math.floor((z - r) / CELL); iz <= Math.floor((z + r) / CELL); iz++) {
        const l = this.grid.get(this.key(ix, iz)); if (l) for (const b of l) out.add(b);
      }
    for (const d of this.dynamic) out.add(d);
    return out;
  }

  ground(x, z) {
    let g = this.terrain ? this.terrain(x, z) : 0;
    return Math.max(g, this.floorY);
  }

  // Height you would stand on at (x,z) coming from height y: terrain or the top of a box within reach below.
  support(x, z, y) {
    let s = this.ground(x, z);
    for (const b of this.near(x, z, 0)) {
      if (x >= b.min.x && x <= b.max.x && z >= b.min.z && z <= b.max.z && b.max.y <= y + .6 && b.max.y > s) s = b.max.y;
    }
    return s;
  }

  // Resolve a capsule at pos (feet) moving; returns {grounded, groundY}. Mutates pos.
  moveCapsule(pos, vel, r, h, dt, step = .45) {
    pos.x += vel.x * dt; pos.z += vel.z * dt; pos.y += vel.y * dt;
    let gy = this.ground(pos.x, pos.z);
    // two passes of push-out against nearby boxes
    for (let pass = 0; pass < 2; pass++) {
      for (const b of this.near(pos.x, pos.z, r + 1)) {
        if (b.max.y <= pos.y + step && b.max.y >= pos.y - 1.2) {
          // walkable top within step height: stand on it if we overlap its footprint
          if (pos.x > b.min.x - r * .5 && pos.x < b.max.x + r * .5 && pos.z > b.min.z - r * .5 && pos.z < b.max.z + r * .5) gy = Math.max(gy, b.max.y);
          continue;
        }
        if (b.min.y >= pos.y + h || b.max.y <= pos.y) continue;
        const cx = Math.max(b.min.x, Math.min(pos.x, b.max.x)), cz = Math.max(b.min.z, Math.min(pos.z, b.max.z));
        let dx = pos.x - cx, dz = pos.z - cz; const d2 = dx * dx + dz * dz;
        if (d2 >= r * r) continue;
        if (d2 > 1e-8) {
          const d = Math.sqrt(d2), push = r - d; dx /= d; dz /= d;
          pos.x += dx * push; pos.z += dz * push;
          const vn = vel.x * dx + vel.z * dz; if (vn < 0) { vel.x -= vn * dx; vel.z -= vn * dz; }
        } else {
          // centre inside the box: push out along the shallowest axis
          const ex = [pos.x - b.min.x + r, b.max.x - pos.x + r, pos.z - b.min.z + r, b.max.z - pos.z + r];
          const m = Math.min(...ex), k = ex.indexOf(m);
          if (k === 0) pos.x -= m; else if (k === 1) pos.x += m; else if (k === 2) pos.z -= m; else pos.z += m;
        }
      }
    }
    // ceiling
    for (const b of this.near(pos.x, pos.z, r)) {
      if (vel.y > 0 && b.min.y > pos.y && b.min.y < pos.y + h && pos.x > b.min.x && pos.x < b.max.x && pos.z > b.min.z && pos.z < b.max.z) {
        pos.y = b.min.y - h; vel.y = 0;
      }
    }
    let grounded = false;
    if (pos.y <= gy + .02 && vel.y <= 0) { pos.y = gy; vel.y = 0; grounded = true; }
    else if (pos.y < gy) { pos.y = gy; vel.y = Math.max(vel.y, 0); grounded = true; }
    return { grounded, groundY: gy };
  }

  // Ray vs boxes (+terrain). Returns {dist, point, normal, box} or null.
  raycast(origin, dir, maxDist, ignoreTag = null) {
    let best = maxDist, hit = null;
    _ray.origin.copy(origin); _ray.direction.copy(dir);
    // gather candidate cells along the ray (sample every CELL/2)
    const seen = new Set();
    const steps = Math.ceil(maxDist / (CELL * .5));
    for (let i = 0; i <= steps; i++) {
      const t = Math.min(maxDist, i * CELL * .5);
      const px = origin.x + dir.x * t, pz = origin.z + dir.z * t;
      for (const b of this.near(px, pz, 1)) {
        if (seen.has(b)) continue; seen.add(b);
        if (ignoreTag && b.tag === ignoreTag) continue;
        if (_ray.intersectBox(b, _v)) {
          const d = _v.distanceTo(origin);
          if (d < best) { best = d; hit = { dist: d, point: _v.clone(), box: b }; }
        }
      }
      if (hit && t > best) break;
    }
    if (this.terrain || this.floorY > -Infinity) {
      // march terrain
      const stepL = 1.0; let prev = 0;
      for (let t = 0; t < best; t += stepL) {
        const px = origin.x + dir.x * t, py = origin.y + dir.y * t, pz = origin.z + dir.z * t;
        if (py < this.ground(px, pz)) {
          // refine
          let a = prev, b2 = t;
          for (let k = 0; k < 6; k++) { const m = (a + b2) / 2; const qx = origin.x + dir.x * m, qy = origin.y + dir.y * m, qz = origin.z + dir.z * m; if (qy < this.ground(qx, qz)) b2 = m; else a = m; }
          best = b2; hit = { dist: b2, point: new THREE.Vector3(origin.x + dir.x * b2, origin.y + dir.y * b2, origin.z + dir.z * b2), terrain: true };
          break;
        }
        prev = t;
      }
    }
    if (hit && !hit.normal) {
      if (hit.box) {
        const b = hit.box, p = hit.point, e = 1e-3;
        hit.normal = new THREE.Vector3(
          Math.abs(p.x - b.min.x) < e ? -1 : Math.abs(p.x - b.max.x) < e ? 1 : 0,
          Math.abs(p.y - b.min.y) < e ? -1 : Math.abs(p.y - b.max.y) < e ? 1 : 0,
          Math.abs(p.z - b.min.z) < e ? -1 : Math.abs(p.z - b.max.z) < e ? 1 : 0);
        if (hit.normal.lengthSq() === 0) hit.normal.set(0, 1, 0);
        hit.normal.normalize();
      } else hit.normal = new THREE.Vector3(0, 1, 0);
    }
    return hit;
  }

  lineOfSight(a, b) {
    const d = _v.subVectors(b, a); const len = d.length(); if (len < .01) return true;
    const dir = d.clone().divideScalar(len);
    const h = this.raycast(a, dir, len - .3);
    return !h;
  }
}
