// Pedestrian navigation for New Meridian (used by population.js): a walk graph over the city's sidewalks with
// crossings at every corner, the heritage avenue, the transit-mall walkways, the river bridges and rings round the
// plazas and parks, plus the places people go: seats (park and plaza benches, cafe chairs, planter edges), food kiosks,
// shop windows, building doors (work / shop / hotel / home), tram platform spots and meeting points.
// A* over a few thousand nodes; every place hangs off the graph by a short straight walk checked against colliders.
import { BLOCK, PITCH, CITY_N, CITY_EDGE, RIVER_Z, HERITAGE, TRANSIT, isDowntown } from './layout.js';
import { mulberry } from '../../game/state.js';

const H = BLOCK / 2 - 1.8;                // sidewalk line (same as earth.js cityPaths)
const GRID = 24;
const SKIP_TAGS = new Set(['platform', 'bridge', 'tram', 'edge', 'skywalk']);

// binary min-heap on f-scores
class Heap {
  constructor() { this.a = []; this.f = []; }
  push(v, f) { const a = this.a, F = this.f; a.push(v); F.push(f); let i = a.length - 1; while (i > 0) { const p = (i - 1) >> 1; if (F[p] <= F[i]) break; [a[p], a[i]] = [a[i], a[p]]; [F[p], F[i]] = [F[i], F[p]]; i = p; } }
  pop() {
    const a = this.a, F = this.f, top = a[0], last = a.pop(), lf = F.pop();
    if (a.length) {
      a[0] = last; F[0] = lf; let i = 0;
      for (;;) { const l = 2 * i + 1, r = l + 1; let m = i; if (l < a.length && F[l] < F[m]) m = l; if (r < a.length && F[r] < F[m]) m = r; if (m === i) break; [a[m], a[i]] = [a[i], a[m]]; [F[m], F[i]] = [F[i], F[m]]; i = m; }
    }
    return top;
  }
  get size() { return this.a.length; }
}

export class NavGraph {
  constructor(world) {
    this.w = world; this.col = world.collision;
    this.nodes = []; this.grid = new Map();
    this.pois = { seat: [], kiosk: [], window: [], door: [], platform: [], meet: [], perch: [] };
    this.blocks = new Map();
    this.rnd = mulberry(5150);
    // cafe sets collide as their parasol's whole bounding box (earth.js kitColliders); for walking past and
    // pulling a chair out only the table and chairs count: an oriented box per set
    this.soft = new Map();
    const dt = world.downtown;
    if (dt) for (const it of (dt.furn.DT_cafe || [])) {
      const e = it.m.elements, x = e[12], z = e[14], yaw = Math.atan2(e[8], e[10]);
      for (const b of this.col.near(x, z, 1)) if (b.tag === 'prop' && b.max.y > 2 && Math.abs((b.min.x + b.max.x) / 2 - x) < .4 && Math.abs((b.min.z + b.max.z) / 2 - z) < .4) this.soft.set(b, { x, z, c: Math.cos(yaw), s: Math.sin(yaw), hx: 1, hz: .42 });
    }
    this.build();
  }

  // ---------------------------------------------------------------- graph primitives
  node(x, z, y = 0, tag = null) {
    const k = Math.round(x * 4) + ',' + Math.round(z * 4);
    const ex = this._byPos && this._byPos.get(k); if (ex !== undefined) return ex;
    const id = this.nodes.length;
    this.nodes.push({ id, x, z, y, e: [], tag, dt: false });
    (this._byPos = this._byPos || new Map()).set(k, id);
    const g = this.gkey(x, z); let l = this.grid.get(g); if (!l) this.grid.set(g, l = []); l.push(id);
    return id;
  }

  gkey(x, z) { return Math.floor(x / GRID) * 4099 + Math.floor(z / GRID); }

  link(a, b, cross = null) {
    if (a === b || a == null || b == null) return;
    const A = this.nodes[a], B = this.nodes[b];
    if (A.e.some(e => e.to === b)) return;
    const c = Math.hypot(A.x - B.x, A.z - B.z) * (cross ? 1.6 : 1);     // a small penalty keeps people off roads
    A.e.push({ to: b, c, cross }); B.e.push({ to: a, c, cross });
  }

  nearest(x, z, maxD = 40, filter = null) {
    let best = -1, bd = maxD * maxD;
    const r = Math.ceil(maxD / GRID);
    const ix = Math.floor(x / GRID), iz = Math.floor(z / GRID);
    for (let a = ix - r; a <= ix + r; a++) for (let b = iz - r; b <= iz + r; b++) {
      const l = this.grid.get(a * 4099 + b); if (!l) continue;
      for (const id of l) {
        const n = this.nodes[id]; if (!n.e.length || (filter && !filter(n))) continue;
        const d = (n.x - x) ** 2 + (n.z - z) ** 2;
        if (d < bd) { bd = d; best = id; }
      }
    }
    return best;
  }

  // straight walk from (ax, az) to (bx, bz) clear of colliders (props, buildings, trees)?
  clear(ax, az, bx, bz, pad = .32) {
    const L = Math.hypot(bx - ax, bz - az), n = Math.max(1, Math.ceil(L / 3)), seen = new Set();
    for (let i = 0; i <= n; i++) {
      const t = i / n, x = ax + (bx - ax) * t, z = az + (bz - az) * t;
      for (const b of this.col.near(x, z, 2)) {
        if (seen.has(b)) continue; seen.add(b);
        if (SKIP_TAGS.has(b.tag) || b.max.y < .3 || b.min.y > 1.6) continue;
        const o = this.soft.get(b);
        if (o) {
          const p = Math.min(pad, .2), L0 = toLocal(o, ax, az), L1 = toLocal(o, bx, bz);
          if (segBox(L0[0], L0[1], L1[0], L1[1], -o.hx - p, -o.hz - p, o.hx + p, o.hz + p)) return false;
          continue;
        }
        if (segBox(ax, az, bx, bz, b.min.x - pad, b.min.z - pad, b.max.x + pad, b.max.z + pad)) return false;
      }
    }
    return true;
  }

  // a place off the graph: attach it to the closest node it can walk to in a straight line
  attach(x, z, maxD = 26) {
    const cand = [];
    const r = Math.ceil(maxD / GRID), ix = Math.floor(x / GRID), iz = Math.floor(z / GRID);
    for (let a = ix - r; a <= ix + r; a++) for (let b = iz - r; b <= iz + r; b++) {
      const l = this.grid.get(a * 4099 + b); if (!l) continue;
      for (const id of l) { const n = this.nodes[id], d = Math.hypot(n.x - x, n.z - z); if (d < maxD && n.e.length) cand.push([d, id]); }
    }
    cand.sort((p, q) => p[0] - q[0]);
    for (let i = 0; i < Math.min(6, cand.length); i++) { const n = this.nodes[cand[i][1]]; if (this.clear(x, z, n.x, n.z)) return cand[i][1]; }
    return -1;
  }

  // ---------------------------------------------------------------- A*
  path(a, b) {
    if (a < 0 || b < 0) return null;
    if (a === b) return [a];
    const N = this.nodes, goal = N[b];
    const g = this._g || (this._g = new Float32Array(N.length)), from = this._from || (this._from = new Int32Array(N.length));
    const stamp = this._st || (this._st = new Uint32Array(N.length)), closed = this._cl || (this._cl = new Uint32Array(N.length));
    const s = this._s = (this._s || 0) + 1;
    const h = i => Math.hypot(N[i].x - goal.x, N[i].z - goal.z);
    const open = new Heap();
    stamp[a] = s; g[a] = 0; from[a] = -1; open.push(a, h(a));
    let iter = 0;
    while (open.size && iter++ < 6000) {
      const cur = open.pop();
      if (cur === b) break;
      if (closed[cur] === s) continue; closed[cur] = s;
      for (const e of N[cur].e) {
        const ng = g[cur] + e.c;
        if (stamp[e.to] === s && ng >= g[e.to]) continue;
        stamp[e.to] = s; g[e.to] = ng; from[e.to] = cur;
        open.push(e.to, ng + h(e.to));
      }
    }
    if (stamp[b] !== s) return null;
    const out = []; for (let i = b; i !== -1; i = from[i]) out.push(i);
    return out.reverse();
  }

  edge(a, b) { return this.nodes[a].e.find(e => e.to === b); }

  // ---------------------------------------------------------------- build
  build() {
    const N = CITY_N;
    const riverRow = cz => Math.abs(cz - RIVER_Z) < BLOCK / 2;
    // sidewalk rings: corners + nodes every ~22 m, extra side nodes where the avenues meet the block edge
    for (let bx = -N; bx <= N; bx++) for (let bz = -N; bz <= N; bz++) {
      const cx = bx * PITCH, cz = bz * PITCH;
      if (riverRow(cz)) continue;
      const dt = isDowntown(bx, bz) || (Math.abs(bx) <= 2 && Math.abs(bz) <= 2);
      const heritage = cz === HERITAGE.z && cx > HERITAGE.x0 && cx < HERITAGE.x1;
      const transit = cz === TRANSIT.z && cx > TRANSIT.x0 && cx < TRANSIT.x1;
      const ts = [-H, -H / 2, 0, H / 2, H];
      const sideExtra = heritage ? [-4.6, 4.6] : transit ? [-8.6, 8.6] : [];
      const sideT = [...new Set([...ts, ...sideExtra])].sort((p, q) => p - q);
      // walk the ring: north side west->east, east side north->south, south side east->west, west side south->north
      const ring = [];
      for (const t of ts) ring.push([cx + t, cz - H]);
      for (const t of sideT) if (t > -H) ring.push([cx + H, cz + t]);
      for (const t of [...ts].reverse()) if (t < H) ring.push([cx + t, cz + H]);
      for (const t of [...sideT].reverse()) if (t > -H && t < H) ring.push([cx - H, cz + t]);
      const ids = ring.map(([x, z]) => this.node(x, z));
      for (let i = 0; i < ids.length; i++) this.link(ids[i], ids[(i + 1) % ids.length]);
      for (const id of ids) { this.nodes[id].dt = dt; this.nodes[id].blk = [cx, cz]; }
      const at = (x, z) => this.node(x, z);
      this.blocks.set(bx + ',' + bz, { cx, cz, ids, at, heritage, transit, dt });
    }
    // corner crossings (zebra lines downtown) between neighbouring blocks
    for (const [key, B] of this.blocks) {
      const [bx, bz] = key.split(',').map(Number), cx = B.cx, cz = B.cz;
      const E = this.blocks.get((bx + 1) + ',' + bz), S = this.blocks.get(bx + ',' + (bz + 1));
      if (E) for (const sz of [-1, 1]) this.link(this.node(cx + H, cz + sz * H), this.node(E.cx - H, cz + sz * H), { ax: 'x', c: (bx + .5) * PITCH });
      if (S) for (const sx of [-1, 1]) this.link(this.node(cx + sx * H, cz + H), this.node(cx + sx * H, S.cz - H), { ax: 'z', c: (bz + .5) * PITCH });
      // the avenues continue across the north-south streets
      if (E && (B.heritage || B.transit) && (E.heritage || E.transit)) {
        const off = B.heritage ? 4.6 : 8.6;
        for (const sz of [-1, 1]) this.link(this.node(cx + H, cz + sz * off), this.node(E.cx - H, cz + sz * off), { ax: 'x', c: (bx + .5) * PITCH });
      }
    }
    this.buildAvenues();
    this.buildBridges();
    this.buildPlazas();
    this.buildPlaces();
    this._byPos = null;
    // keep only the largest connected component reachable (no one plans into an island)
    const comp = new Int32Array(this.nodes.length).fill(-1); let c = 0;
    for (let i = 0; i < this.nodes.length; i++) {
      if (comp[i] >= 0) continue;
      const st = [i]; comp[i] = c;
      while (st.length) { const k = st.pop(); for (const e of this.nodes[k].e) if (comp[e.to] < 0) { comp[e.to] = c; st.push(e.to); } }
      c++;
    }
    const size = new Array(c).fill(0); for (let i = 0; i < comp.length; i++) size[comp[i]]++;
    const main = size.indexOf(Math.max(...size));
    for (const n of this.nodes) n.main = comp[n.id] === main;
    for (const k of Object.keys(this.pois)) this.pois[k] = this.pois[k].filter(p => p.node < 0 || this.nodes[p.node].main);
  }

  // heritage avenue (two walk lines either side of the trees, kiosks and benches) and the transit-mall walkways
  buildAvenues() {
    for (const B of this.blocks.values()) {
      if (!B.heritage && !B.transit) continue;
      const off = B.heritage ? 4.6 : 8.6, n = 8, stations = (this.w.downtown && this.w.downtown.stations) || [];
      for (const sz of [-1, 1]) {
        const row = [];
        for (let k = 0; k <= n; k++) {
          const x = B.cx - H + 2 * H * k / n, z = B.cz + sz * off;
          let y = 0;
          // the platforms are 0.35 m up: walkway nodes on them, a short ramp at each end
          if (B.transit) for (const sx of stations) if (Math.abs(x - sx) <= 21.5) y = .35;
          const id = this.node(x, z, y); this.nodes[id].dt = true; this.nodes[id].avenue = B.heritage ? 'heritage' : 'transit';
          this.nodes[id].blk = [B.cx, B.cz];
          row.push(id);
        }
        if (B.transit) for (const sx of stations) for (const e of [-22.5, 22.5]) {
          if (Math.abs(sx + e - B.cx) < H) { const id = this.node(sx + e, B.cz + sz * off, 0); this.nodes[id].dt = true; this.nodes[id].blk = [B.cx, B.cz]; row.push(id); }
        }
        row.sort((p, q) => this.nodes[p].x - this.nodes[q].x);
        for (let k = 1; k < row.length; k++) this.link(row[k - 1], row[k]);
        (B.rows = B.rows || []).push(row);
      }
      // across the heritage avenue wherever nothing stands in between
      if (B.heritage) for (let k = 0; k < B.rows[0].length; k++) {
        const a = this.nodes[B.rows[0][k]], b = this.nodes[B.rows[1][k]];
        if (b && this.clear(a.x, a.z, b.x, b.z, .25)) this.link(a.id, b.id);
      }
    }
  }

  // footways on the bridges over the river (one each side of every north-south street)
  buildBridges() {
    const rS = RIVER_Z + BLOCK / 2 - 2, rN = RIVER_Z - BLOCK / 2 + 2;   // bridge deck ends
    for (let i = -CITY_N - 1; i <= CITY_N; i++) {
      const c = (i + .5) * PITCH;
      for (const sx of [-1, 1]) {
        const bxS = this.blocks.get((sx < 0 ? i : i + 1) + ',' + Math.round((RIVER_Z + PITCH) / PITCH));
        const bxN = this.blocks.get((sx < 0 ? i : i + 1) + ',' + Math.round((RIVER_Z - PITCH) / PITCH));
        if (!bxS || !bxN) continue;
        const a = this.node(c + sx * (PITCH / 2 - H) * 1, bxS.cz - H), d = this.node(c + sx * (PITCH / 2 - H), bxN.cz + H);
        const b = this.node(c + sx * 8, rS), e = this.node(c + sx * 8, rN);
        this.link(a, b, { ax: 'z', c: RIVER_Z + PITCH / 2 }); this.link(b, e); this.link(e, d, { ax: 'z', c: RIVER_Z - PITCH / 2 });
        for (const id of [b, e]) this.nodes[id].bridge = true;
      }
    }
  }

  // walk rings round the downtown plazas, the parks' fountains and the rotunda, joined to the sidewalks
  buildPlazas() {
    const dt = this.w.downtown, rings = [];
    if (dt) for (const p of dt.plazas || []) rings.push({ x: (p.x0 + p.x1) / 2, z: (p.z0 + p.z1) / 2, r: 11, meet: 14, plaza: p, dt: true });
    for (const b of this.col.boxes) if (b.tag === 'fountain') rings.push({ x: (b.min.x + b.max.x) / 2, z: (b.min.z + b.max.z) / 2, r: 13.5, meet: 15.5, park: true });
    if (this.w.plaza) rings.push({ x: this.w.plaza[0], z: this.w.plaza[1], r: 16, meet: 19, rotunda: true });
    this.rings = rings;
    for (const R of rings) {
      const ids = [];
      for (let k = 0; k < 12; k++) { const a = k / 12 * Math.PI * 2; ids.push(this.node(R.x + Math.cos(a) * R.r, R.z + Math.sin(a) * R.r)); }
      for (const id of ids) { this.nodes[id].dt = !!R.dt; this.nodes[id].plaza = true; }
      for (let k = 0; k < 12; k++) {
        const A = this.nodes[ids[k]], B = this.nodes[ids[(k + 1) % 12]];
        if (this.clear(A.x, A.z, B.x, B.z, .2)) this.link(A.id, B.id);
      }
      // spokes: every ring node to its nearest sidewalk node in a straight clear line (at most 5 spokes)
      let spokes = 0;
      const order = ids.map(id => { const n = this.nodes[id], s = this.nearest(n.x, n.z, 45, m => !m.plaza && !m.avenue); return [s >= 0 ? Math.hypot(this.nodes[s].x - n.x, this.nodes[s].z - n.z) : 1e9, id, s]; }).sort((p, q) => p[0] - q[0]);
      for (const [d, id, s] of order) {
        if (spokes >= 5 || s < 0 || d > 44) continue;
        const n = this.nodes[id], m = this.nodes[s];
        if (this.clear(n.x, n.z, m.x, m.z)) { this.link(id, s); spokes++; }
      }
      // chat spots: open paving between the ring and the edge
      for (let k = 0; k < 6; k++) {
        const a = k / 6 * Math.PI * 2 + .26, x = R.x + Math.cos(a) * R.meet, z = R.z + Math.sin(a) * R.meet;
        const node = this.attach(x, z, 14);
        if (node >= 0 && this.clear(x - 1.2, z, x + 1.2, z, .2) && this.clear(x, z - 1.2, x, z + 1.2, .2)) this.pois.meet.push({ x, z, y: 0, node, dt: !!R.dt, park: !!R.park, users: [] });
      }
      // birds peck on the open paving / lawn round the centre
      for (let k = 0; k < 3; k++) { const a = k / 3 * Math.PI * 2 + .9; this.pois.perch.push({ x: R.x + Math.cos(a) * (R.r - 3), z: R.z + Math.sin(a) * (R.r - 3), y: 0, park: !!R.park, node: -1 }); }
    }
  }

  // ---------------------------------------------------------------- places people go to
  buildPlaces() {
    const W = this.w, dt = W.downtown, P = this.pois;
    const fwd = yaw => [Math.sin(yaw), Math.cos(yaw)];
    const addSeat = (x, z, yaw, kind, y = 0, approach = .7, side = null) => {
      const [fx, fz] = side || fwd(yaw), ax = x + fx * approach, az = z + fz * approach;
      const node = this.attach(ax, az, 26);
      if (node < 0) return;
      P.seat.push({ x, z, y, yaw, kind, ax, az, node, dt: this.nodes[node].dt, by: null });
    };
    // benches (earth.js parks and downtown) registered through World.addSeat
    for (const s of W.seatSpots || []) addSeat(s.pos.x, s.pos.z, s.yaw, 'bench', s.pos.y);
    if (dt) {
      const _yaw = m => { const e = m.elements; return Math.atan2(e[8], e[10]); };
      // cafe sets: two chairs facing the table across it (downtown.py cafe(): chairs at local x = +-0.75)
      for (const it of (dt.furn.DT_cafe || [])) {
        const e = it.m.elements, x = e[12], z = e[14], yaw = _yaw(it.m), c = Math.cos(yaw), s = Math.sin(yaw);
        for (const sx of [-1, 1]) {
          const px = x + sx * .75 * c, pz = z - sx * .75 * s, n0 = P.seat.length;
          // pull the chair out from behind, or step in beside it (tables stand close together on the avenue)
          for (const [dx, dz, k] of [[sx * c, -sx * s, .85], [s, c, .8], [-s, -c, .8]]) {
            addSeat(px, pz, yaw - sx * Math.PI / 2, 'cafe', -.04, k, [dx, dz]);
            if (P.seat.length > n0) { P.seat[n0].table = [x, z]; break; }
          }
        }
      }
      // planter edges: perch on the long sides, facing out
      for (const it of (dt.furn.DT_planter || [])) {
        const e = it.m.elements, x = e[12], z = e[14], yaw = _yaw(it.m), c = Math.cos(yaw), s = Math.sin(yaw);
        for (const sz of [-1, 1]) {
          // local +-z side (Blender y); outward normal rotated by yaw; hips on the rim, feet on the paving
          const nx = sz * s, nz = sz * c, px = x + nx * .5, pz = z + nz * .5;
          if (this.rnd() < .6) addSeat(px, pz, Math.atan2(nx, nz), 'planter', .12, .62);
        }
      }
      // food kiosks: a queue in front of the counter (local +z)
      for (const it of (dt.furn.DT_kiosk || [])) {
        const e = it.m.elements, x = e[12], z = e[14], yaw = _yaw(it.m), [fx, fz] = fwd(yaw);
        const q = [];
        for (let k = 0; k < 3; k++) q.push([x + fx * (2.2 + k * .85), z + fz * (2.2 + k * .85)]);
        const node = this.attach(q[2][0], q[2][1], 26);
        if (node >= 0 && this.clear(q[0][0], q[0][1], q[2][0], q[2][1], .2)) P.kiosk.push({ x, z, yaw: yaw + Math.PI, q, users: [null, null, null], node, dt: true });
      }
      // building fronts: doors (and shop windows on the old low-rises)
      for (const B of dt.placed) {
        const kind = /hotel/.test(B.name) ? 'hotel' : /residential/.test(B.name) ? 'home' : /hist|derelict/.test(B.name) ? 'shop'
          : /parkade|construction|obs_tower/.test(B.name) ? null : 'work';
        if (!kind) continue;
        const r = B.rect, f = B.face;
        const n = f === 's' ? [0, 1] : f === 'n' ? [0, -1] : f === 'e' ? [1, 0] : [-1, 0];
        const fx = f === 'e' ? r[2] : f === 'w' ? r[0] : (r[0] + r[2]) / 2, fz = f === 's' ? r[3] : f === 'n' ? r[1] : (r[1] + r[3]) / 2;
        const along = f === 's' || f === 'n' ? [1, 0] : [0, 1], w = f === 's' || f === 'n' ? r[2] - r[0] : r[3] - r[1];
        this.addDoor(fx, fz, n, kind, true, B.h);
        if (kind === 'shop' || kind === 'hotel') for (const t of [-.3, .3]) {
          const x = fx + along[0] * w * t + n[0] * 1.3, z = fz + along[1] * w * t + n[1] * 1.3;
          const node = this.attach(x, z, 20);
          if (node >= 0) P.window.push({ x, z, y: 0, yaw: Math.atan2(-n[0], -n[1]), node, dt: true, by: null, heritage: Math.abs(z - HERITAGE.z) < 12 });
        }
      }
      // tram platform spots (stand facing the tracks)
      for (const sx of dt.stations || []) for (const sz of [-1, 1]) for (let k = -4; k <= 4; k++) {
        const x = sx + k * 4.2 + (k % 2) * .6, z = TRANSIT.z + sz * 6.5;
        const node = this.nearest(x, TRANSIT.z + sz * 8.6, 8, m => m.avenue === 'transit');
        if (node >= 0) P.platform.push({ x, z, y: .35, yaw: sz < 0 ? 0 : Math.PI, side: sz, station: sx, node, by: null, dt: true });
      }
    }
    // the rest of the city: doors on the street faces of the mid-ring buildings and the suburban houses
    for (const b of this.col.boxes) {
      if (b.tag !== 'building' || b.max.y < 3) continue;
      const x = (b.min.x + b.max.x) / 2, z = (b.min.z + b.max.z) / 2;
      const bx = Math.round(x / PITCH), bz = Math.round(z / PITCH);
      if (Math.abs(bx) > CITY_N || Math.abs(bz) > CITY_N || isDowntown(bx, bz) || (bx === 1 && bz === 1)) continue;
      const cx = bx * PITCH, cz = bz * PITCH;
      const gaps = [[b.min.z - (cz - H), [0, -1]], [b.min.x - (cx - H), [-1, 0]], [(cx + H) - b.max.x, [1, 0]], [(cz + H) - b.max.z, [0, 1]]]
        .filter(g => g[0] > -1).sort((p, q) => p[0] - q[0]);
      if (!gaps.length || gaps[0][0] > 26) continue;
      const n = gaps[0][1];
      const fx = n[0] ? (n[0] > 0 ? b.max.x : b.min.x) : x, fz = n[1] ? (n[1] > 0 ? b.max.z : b.min.z) : z;
      const house = b.max.y < 8 && b.max.x - b.min.x < 13;
      const edge = Math.max(Math.abs(bx), Math.abs(bz));
      this.addDoor(fx, fz, n, house || edge >= 3 ? 'home' : this.rnd() < .55 ? 'home' : 'work', false, b.max.y);
    }
  }

  addDoor(fx, fz, n, kind, dt, h) {
    const ax = fx + n[0] * 1.5, az = fz + n[1] * 1.5;
    const node = this.attach(ax, az, 30);
    if (node < 0) return;
    this.pois.door.push({ x: fx - n[0] * .9, z: fz - n[1] * .9, ax, az, n, kind, dt, h, node, yaw: Math.atan2(-n[0], -n[1]) });
  }

  stats() {
    const P = this.pois, out = { nodes: this.nodes.length, main: this.nodes.filter(n => n.main).length, edges: this.nodes.reduce((a, n) => a + n.e.length, 0) / 2 };
    for (const k of Object.keys(P)) out[k] = P[k].length;
    out.seatKinds = {}; for (const s of P.seat) out.seatKinds[s.kind] = (out.seatKinds[s.kind] || 0) + 1;
    out.doorKinds = {}; for (const s of P.door) out.doorKinds[s.kind] = (out.doorKinds[s.kind] || 0) + 1;
    return out;
  }
}

function toLocal(o, x, z) { const dx = x - o.x, dz = z - o.z; return [dx * o.c - dz * o.s, dx * o.s + dz * o.c]; }

// 2D segment vs axis-aligned rectangle (slab test)
function segBox(ax, az, bx, bz, x0, z0, x1, z1) {
  let t0 = 0, t1 = 1;
  const dx = bx - ax, dz = bz - az;
  for (const [p, d, lo, hi] of [[ax, dx, x0, x1], [az, dz, z0, z1]]) {
    if (Math.abs(d) < 1e-9) { if (p < lo || p > hi) return false; continue; }
    let ta = (lo - p) / d, tb = (hi - p) / d; if (ta > tb) [ta, tb] = [tb, ta];
    t0 = Math.max(t0, ta); t1 = Math.min(t1, tb); if (t0 > t1) return false;
  }
  return true;
}

export { H as SIDEWALK, CITY_EDGE };
