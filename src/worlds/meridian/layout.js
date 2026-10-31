// New Meridian map layout: a 2.8 km island with the city in the middle, villages and farms joined by highways.
// Heights live in a 4 m grid (natural hills + flattened city/villages/farms/roads) sampled bilinearly.
import * as THREE from 'three';

export const SIZE = 2800, HALF = SIZE / 2, CELL = 4, N = SIZE / CELL + 1;
export const BLOCK = 92, ROAD = 18, CITY_N = 4, PITCH = BLOCK + ROAD;
export const CITY_EDGE = (CITY_N + .5) * PITCH;     // 495 m: the outer ring road
export const SEA = -3;
// Snow line (m): the Meridian Peaks massif on the north coast rises well above it; earth.js whitens the terrain above it
// (slope-dependent, snow on rock ledges) and flora.js plants snow-covered conifers and bare snowy trees there.
export const SNOW_LINE = 68;
const PEAKS = [[-300, -1060, 48, 150], [-60, -1100, 66, 175], [190, -1050, 44, 140], [-560, -990, 26, 130]];   // x, z, height, spread
// The river (owner's city art): straight through the city's north side in block row -3, winding to the sea outside.
export const RIVER_Z = -3 * PITCH, RIVER_W = 33, RIVER_BANK = 4;
// New Meridian Spaceport (owner request: "where we land in the city"): the starship landing zone just south of the city
// across the ring road, joined to it by the street at x = -275. SPACEPORT.x/z is the origin of tools/blender/spaceport.py
// (landing pad 1); `area` is the flattened footprint [x0, z0, x1, z1] (landing field, terminal, yard, landside lots).
export const SPACEPORT = { x: -275, z: 640, area: [-705, 492, 52, 800] };
export const inSpaceport = (x, z, pad = 0) => x > SPACEPORT.area[0] - pad && x < SPACEPORT.area[2] + pad && z > SPACEPORT.area[1] - pad && z < SPACEPORT.area[3] + pad;
export function riverZ(x) {
  const o = Math.abs(x) - (CITY_EDGE + 30);
  if (o <= 0) return RIVER_Z;
  const t = Math.min(1, o / 120);
  return RIVER_Z + Math.sign(x) * 70 * Math.sin(o / 170) * t * t * (3 - 2 * t);
}

function hash2(x, z, s) { let h = (Math.imul(x, 374761393) + Math.imul(z, 668265263) + Math.imul(s, 982451653)) | 0; h = Math.imul(h ^ (h >>> 13), 1274126177); return ((h ^ (h >>> 16)) >>> 0) / 4294967295; }
function vnoise(x, z, s) {
  const xi = Math.floor(x), zi = Math.floor(z), xf = x - xi, zf = z - zi, u = xf * xf * (3 - 2 * xf), v = zf * zf * (3 - 2 * zf);
  const a = hash2(xi, zi, s), b = hash2(xi + 1, zi, s), c = hash2(xi, zi + 1, s), d = hash2(xi + 1, zi + 1, s);
  return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v;
}
export function fbm(x, z, s, o = 5) { let t = 0, a = .5, n = 0; for (let i = 0; i < o; i++) { t += a * vnoise(x, z, s + i * 17); n += a; x *= 2.03; z *= 2.03; a *= .5; } return t / n; }
const ss = (a, b, x) => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); };

export const VILLAGES = [
  { name: 'Harrow', pos: [-860, 640], r: 110 },
  { name: 'Millbrook', pos: [900, 520], r: 110 },
  { name: 'Eastwell', pos: [640, -880], r: 100 },
];
export const FARMS = [
  { name: 'Brannock Farm', pos: [-700, -620], w: 260, d: 200 },
  { name: 'Whitlow Fields', pos: [-1040, 160], w: 200, d: 260 },
  { name: 'Corran Ranch', pos: [1060, -240], w: 220, d: 240 },
  { name: 'Ashgrove Farm', pos: [300, 1020], w: 280, d: 180 },
];
// highways: polylines (x, z); each joins the outer ring road to the countryside
const ROAD_DEFS = [
  [[-CITY_EDGE, 275], [-640, 360], [-780, 560], [-860, 640], [-930, 760], [-1080, 860]],
  [[CITY_EDGE, 275], [660, 360], [800, 470], [900, 520], [1040, 600], [1180, 700]],
  [[275, -CITY_EDGE], [420, -660], [560, -800], [640, -880], [700, -1020], [760, -1160]],
  [[-275, -CITY_EDGE], [-420, -560], [-560, -600], [-700, -620], [-860, -660], [-1040, -760]],
  [[-860, 640], [-960, 460], [-1040, 300], [-1040, 160], [-1000, 0], [-860, -220], [-760, -440], [-700, -620]],
  [[900, 520], [1000, 360], [1060, 120], [1060, -240], [960, -520], [800, -720], [640, -880]],
  [[55, CITY_EDGE], [120, 700], [220, 880], [300, 1020], [180, 1160]],
];

function catmull(pts, step = 6) {
  const out = [];
  const P = [pts[0], ...pts, pts[pts.length - 1]];
  for (let i = 1; i < P.length - 2; i++) {
    const [p0, p1, p2, p3] = [P[i - 1], P[i], P[i + 1], P[i + 2]];
    const len = Math.hypot(p2[0] - p1[0], p2[1] - p1[1]);
    const n = Math.max(2, Math.ceil(len / step));
    for (let k = 0; k < n; k++) {
      const t = k / n, t2 = t * t, t3 = t2 * t;
      out.push([0, 1].map(j => .5 * (2 * p1[j] + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t2 + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t3)));
    }
  }
  out.push(pts[pts.length - 1]);
  return out;
}

export class MeridianMap {
  constructor() {
    this.h = new Float32Array(N * N);
    this.flatW = new Float32Array(N * N); this.flatH = new Float32Array(N * N);
    this.roads = []; this.lanes = []; this.paths = [];
    this.build();
  }

  natural(x, z) {
    const d = Math.max(Math.abs(x), Math.abs(z));
    let h = (fbm(x * .0022 + 7, z * .0022 - 3, 11) - .45) * 70;
    h += Math.pow(1 - Math.abs(fbm(x * .0011, z * .0011, 23, 4) * 2 - 1), 2) * 55;      // ridges
    h *= ss(CITY_EDGE - 40, CITY_EDGE + 260, Math.hypot(x, z) * .85 + d * .15);       // calm near the city
    h += ss(1100, 1380, d) * (-28);                                                    // drop to the sea at the edges
    // the Meridian Peaks: a craggy massif on the north coast, easing down before the shore
    let pk = 0;
    for (const [px, pz, ph, pr] of PEAKS) { const dx = x - px, dz = z - pz; pk += ph * Math.exp(-(dx * dx + dz * dz) / (2 * pr * pr)); }
    if (pk > .5) h += pk * (.8 + .45 * Math.pow(1 - Math.abs(fbm(x * .006 + 11, z * .006 - 5, 31, 4) * 2 - 1), 2)) * (1 - ss(1180, 1370, d));
    // a lake to the north-west
    const lx = x + 420, lz = z - 820; h -= 22 * Math.exp(-(lx * lx + lz * lz) / (2 * 110 * 110));
    return h;
  }

  idx(i, j) { return j * N + i; }

  stampDisk(cx, cz, r, height, feather = 18, strength = 1) {
    const i0 = Math.max(0, Math.floor((cx - r - feather + HALF) / CELL)), i1 = Math.min(N - 1, Math.ceil((cx + r + feather + HALF) / CELL));
    const j0 = Math.max(0, Math.floor((cz - r - feather + HALF) / CELL)), j1 = Math.min(N - 1, Math.ceil((cz + r + feather + HALF) / CELL));
    for (let j = j0; j <= j1; j++) for (let i = i0; i <= i1; i++) {
      const x = i * CELL - HALF, z = j * CELL - HALF, d = Math.hypot(x - cx, z - cz);
      const w = (1 - ss(r, r + feather, d)) * strength, k = this.idx(i, j);
      if (w > this.flatW[k]) { this.flatW[k] = w; this.flatH[k] = height; }
    }
  }

  stampRect(cx, cz, w, d, height, feather = 20) {
    const i0 = Math.max(0, Math.floor((cx - w / 2 - feather + HALF) / CELL)), i1 = Math.min(N - 1, Math.ceil((cx + w / 2 + feather + HALF) / CELL));
    const j0 = Math.max(0, Math.floor((cz - d / 2 - feather + HALF) / CELL)), j1 = Math.min(N - 1, Math.ceil((cz + d / 2 + feather + HALF) / CELL));
    for (let j = j0; j <= j1; j++) for (let i = i0; i <= i1; i++) {
      const x = i * CELL - HALF, z = j * CELL - HALF;
      const dx = Math.max(0, Math.abs(x - cx) - w / 2), dz = Math.max(0, Math.abs(z - cz) - d / 2);
      const wgt = 1 - ss(0, feather, Math.hypot(dx, dz)), k = this.idx(i, j);
      if (wgt > this.flatW[k]) { this.flatW[k] = wgt; this.flatH[k] = height; }
    }
  }

  build() {
    // natural terrain
    for (let j = 0; j < N; j++) for (let i = 0; i < N; i++) this.h[this.idx(i, j)] = this.natural(i * CELL - HALF, j * CELL - HALF);
    // the city is flat at 0
    this.stampRect(0, 0, CITY_EDGE * 2 + 40, CITY_EDGE * 2 + 40, 0, 60);
    // the spaceport is a level field at street height
    const [ax0, az0, ax1, az1] = SPACEPORT.area;
    this.stampRect((ax0 + ax1) / 2, (az0 + az1) / 2, ax1 - ax0, az1 - az0, 0, 70);
    // villages and farms sit on gentle terraces at their natural height
    for (const v of VILLAGES) { v.y = Math.max(1, this.sampleNatural(v.pos[0], v.pos[1])); this.stampDisk(v.pos[0], v.pos[1], v.r, v.y, 50); }
    for (const f of FARMS) { f.y = Math.max(1, this.sampleNatural(f.pos[0], f.pos[1])); this.stampRect(f.pos[0], f.pos[1], f.w + 40, f.d + 40, f.y, 50); }
    // roads: smooth the elevation along each highway, then cut/fill a corridor
    for (const def of ROAD_DEFS) {
      const pts = catmull(def, 6);
      const raw = pts.map(([x, z]) => this.currentHeight(x, z));
      const sm = raw.map((_, i) => { let s = 0, n = 0; for (let k = -8; k <= 8; k++) { const q = raw[Math.min(raw.length - 1, Math.max(0, i + k))]; s += q; n++; } return Math.max(.5, s / n); });
      const road = { pts: pts.map(([x, z], i) => new THREE.Vector3(x, sm[i], z)), width: 11 };
      for (const p of road.pts) this.stampDisk(p.x, p.z, 8, p.y, 16, 1);
      this.roads.push(road);
    }
    // apply flats
    for (let k = 0; k < N * N; k++) if (this.flatW[k] > 0) this.h[k] += (this.flatH[k] - this.h[k]) * this.flatW[k];
    // re-sample road heights from the final terrain so ribbons hug the ground
    for (const r of this.roads) for (const p of r.pts) p.y = this.height(p.x, p.z);
    this.carveRiver();
    this.buildLanes();
  }

  // Cut the river bed below sea level (the bay's water fills it); highways cross on causeways.
  carveRiver() {
    const reach = RIVER_W + RIVER_BANK;
    this.riverCrossings = [];
    for (const r of this.roads) {
      for (let i = 1; i < r.pts.length; i++) {
        const a = r.pts[i - 1], b = r.pts[i];
        const da = a.z - riverZ(a.x), db = b.z - riverZ(b.x);
        if (da * db <= 0) this.riverCrossings.push({ x: (a.x + b.x) / 2, y: (a.y + b.y) / 2, z: (a.z + b.z) / 2, ang: Math.atan2(b.x - a.x, b.z - a.z) });
      }
    }
    for (let j = 0; j < N; j++) for (let i = 0; i < N; i++) {
      const x = i * CELL - HALF, z = j * CELL - HALF, d = Math.abs(z - riverZ(x));
      if (d > reach) continue;
      if (this.riverCrossings.some(c => Math.hypot(c.x - x, c.z - z) < 14)) continue;
      const k = this.idx(i, j), bed = SEA - 4.5 + 2 * (d / RIVER_W) ** 2;
      const t = d < RIVER_W ? 0 : (d - RIVER_W) / RIVER_BANK;
      this.h[k] = Math.min(this.h[k], bed + (this.h[k] - bed) * t * t);
    }
  }

  sampleNatural(x, z) { return this.natural(x, z); }

  currentHeight(x, z) {
    const i = Math.round((x + HALF) / CELL), j = Math.round((z + HALF) / CELL);
    if (i < 0 || j < 0 || i >= N || j >= N) return SEA;
    const k = this.idx(i, j);
    return this.h[k] + (this.flatH[k] - this.h[k]) * this.flatW[k];
  }

  height(x, z) {
    const fx = (x + HALF) / CELL, fz = (z + HALF) / CELL;
    const i = Math.floor(fx), j = Math.floor(fz);
    if (i < 0 || j < 0 || i >= N - 1 || j >= N - 1) return SEA - 10;
    const u = fx - i, v = fz - j, a = this.h[this.idx(i, j)], b = this.h[this.idx(i + 1, j)], c = this.h[this.idx(i, j + 1)], d = this.h[this.idx(i + 1, j + 1)];
    return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v;
  }

  // Directional lanes for traffic (right-hand driving): city grid lines + highways.
  buildLanes() {
    const L = this.lanes;
    const off = 3.2;
    for (let i = -CITY_N - 1; i <= CITY_N; i++) {
      const c = (i + .5) * PITCH;
      for (const ax of [0, 1]) for (const dir of [1, -1]) {
        const pts = [];
        for (let t = -CITY_EDGE; t <= CITY_EDGE + .1; t += 10) {
          const s = dir > 0 ? t : -t;
          pts.push(ax ? new THREE.Vector3(c - dir * off, 0, s) : new THREE.Vector3(s, 0, c + dir * off));
        }
        L.push({ pts, city: true, speed: 13 });
      }
    }
    for (const r of this.roads) {
      for (const dir of [1, -1]) {
        const src = dir > 0 ? r.pts : [...r.pts].reverse();
        const pts = src.map((p, i) => {
          const a = src[Math.max(0, i - 1)], b = src[Math.min(src.length - 1, i + 1)];
          const tx = b.x - a.x, tz = b.z - a.z, l = Math.hypot(tx, tz) || 1;
          const q = new THREE.Vector3(p.x - tz / l * off, 0, p.z + tx / l * off);   // right side of travel
          q.y = this.height(q.x, q.z);
          return q;
        });
        L.push({ pts, city: false, speed: 22 });
      }
    }
    for (const l of L) {
      l.len = [0];
      for (let i = 1; i < l.pts.length; i++) l.len.push(l.len[i - 1] + l.pts[i].distanceTo(l.pts[i - 1]));
      l.total = l.len[l.len.length - 1];
    }
  }

  lanePoint(l, s, out, dirOut) {
    s = Math.max(0, Math.min(l.total, s));
    let lo = 0, hi = l.len.length - 1;
    while (hi - lo > 1) { const m = (lo + hi) >> 1; if (l.len[m] <= s) lo = m; else hi = m; }
    const a = l.pts[lo], b = l.pts[hi], t = (s - l.len[lo]) / Math.max(1e-6, l.len[hi] - l.len[lo]);
    out.lerpVectors(a, b, t);
    if (dirOut) dirOut.subVectors(b, a).normalize();
    return out;
  }

  // nearest lane start to a point (for chaining lanes end to start)
  nextLane(pos, exclude) {
    let best = null, bd = 30;
    for (const l of this.lanes) {
      if (l === exclude) continue;
      const d = l.pts[0].distanceTo(pos);
      if (d < bd) { bd = d; best = l; }
    }
    return best;
  }

  district(x, z) {
    if (Math.abs(x) < CITY_EDGE && Math.abs(z) < CITY_EDGE) {
      if (Math.abs(z - RIVER_Z) < 75) return 'Riverside';
      if (Math.max(Math.abs(x), Math.abs(z)) > CITY_EDGE - PITCH) return 'Meridian Heights';
      return Math.hypot(x, z) < 200 ? 'Downtown' : 'New Meridian';
    }
    if (inSpaceport(x, z)) return 'Meridian Spaceport';
    if (Math.abs(z - riverZ(x)) < RIVER_W) return 'Meridian River';
    for (const v of VILLAGES) if (Math.hypot(x - v.pos[0], z - v.pos[1]) < v.r + 80) return v.name;
    for (const f of FARMS) if (Math.abs(x - f.pos[0]) < f.w / 2 + 60 && Math.abs(z - f.pos[1]) < f.d / 2 + 60) return f.name;
    if (this.height(x, z) < SEA + .5) return 'Meridian Bay';
    const hh = this.height(x, z);
    return hh > SNOW_LINE ? 'Meridian Peaks' : hh > 45 ? 'Highlands' : 'Countryside';
  }

  // keep-out test for scatter (roads, city, villages, farms)
  developed(x, z, pad = 0) {
    if (Math.abs(x) < CITY_EDGE + 30 + pad && Math.abs(z) < CITY_EDGE + 30 + pad) return true;
    if (inSpaceport(x, z, 25 + pad)) return true;
    for (const v of VILLAGES) if (Math.hypot(x - v.pos[0], z - v.pos[1]) < v.r + 20 + pad) return true;
    for (const f of FARMS) if (Math.abs(x - f.pos[0]) < f.w / 2 + 10 + pad && Math.abs(z - f.pos[1]) < f.d / 2 + 10 + pad) return true;
    return false;
  }

  nearRoad(x, z, r) {
    for (const rd of this.roads) {
      for (let i = 0; i < rd.pts.length; i += 2) { const p = rd.pts[i]; if (Math.abs(p.x - x) < r && Math.abs(p.z - z) < r && Math.hypot(p.x - x, p.z - z) < r) return true; }
    }
    return false;
  }
}
