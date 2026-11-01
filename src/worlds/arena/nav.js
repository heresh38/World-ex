// Navigation graph for Shellbreak bots, baked by tools/blender/arena.py into arena_<map>.json: one node per walkable
// 1 m cell on every level (ground, platform, wagons, container roofs, mezzanines, gatehouse), edges 'w' walk (stairs
// included), 'd' drop off a ledge, 'm' mantle up a ledge (0.5-2.4 m, like the player's findLedge climb). A* with a binary
// heap over typed arrays; cover points (a node beside a box that hides a crouching or standing body) with their facing.
const SQ2 = Math.SQRT2;

export class NavGraph {
  constructor(J) {
    const N = J.nodes, n = this.n = N.length / 3;
    this.x = new Float32Array(n); this.y = new Float32Array(n); this.z = new Float32Array(n);
    for (let i = 0; i < n; i++) { this.x[i] = N[i * 3] / 10; this.y[i] = N[i * 3 + 1] / 100; this.z[i] = N[i * 3 + 2] / 10; }
    // CSR adjacency with a per-edge type and cost
    let m = 0; for (const a of J.adj) m += a.length;
    this.off = new Int32Array(n + 1); this.to = new Int32Array(m); this.type = new Uint8Array(m); this.cost = new Float32Array(m);
    let k = 0;
    for (let i = 0; i < n; i++) {
      this.off[i] = k;
      const a = J.adj[i], t = J.typ[i];
      for (let j = 0; j < a.length; j++) {
        const b = a[j], c = t[j], dx = this.x[b] - this.x[i], dz = this.z[b] - this.z[i], dy = this.y[b] - this.y[i];
        const d = Math.hypot(dx, dz);
        this.to[k] = b; this.type[k] = c === 'w' ? 0 : c === 'd' ? 1 : 2;
        this.cost[k] = c === 'w' ? d + Math.abs(dy) * .5 : c === 'd' ? d + .6 : d + 1.2 + dy;
        k++;
      }
    }
    this.off[n] = k;
    // spatial buckets (2 m) for nearest-node queries
    this.cs = 2; this.grid = new Map();
    for (let i = 0; i < n; i++) {
      const key = this.key(Math.floor(this.x[i] / this.cs), Math.floor(this.z[i] / this.cs));
      let l = this.grid.get(key); if (!l) this.grid.set(key, l = []); l.push(i);
    }
    // cover: node -> [dx, dz, h] (direction toward the sheltering box, 1 crouch / 2 full)
    this.cover = new Map(); this.coverList = [];
    for (const [i, dx, dz, h] of J.cover || []) { this.cover.set(i, [dx, dz, h]); this.coverList.push(i); }
    // A* scratch
    this.g = new Float32Array(n); this.f = new Float32Array(n); this.came = new Int32Array(n); this.stamp = new Uint32Array(n); this.closed = new Uint32Array(n);
    this.heap = new Int32Array(m + n + 16); this.run = 0;
    this.stats = { searches: 0, ms: 0, expanded: 0 };
  }

  key(ix, iz) { return ix * 4096 + iz; }

  // nearest node to a point, preferring the same level (height differences count 3x); null when nothing within maxD
  nearest(x, y, z, maxD = 4) {
    let best = -1, bd = maxD * maxD;
    const r = Math.ceil(maxD / this.cs), cx = Math.floor(x / this.cs), cz = Math.floor(z / this.cs);
    for (let ix = cx - r; ix <= cx + r; ix++) for (let iz = cz - r; iz <= cz + r; iz++) {
      const l = this.grid.get(this.key(ix, iz)); if (!l) continue;
      for (const i of l) {
        const dx = this.x[i] - x, dz = this.z[i] - z, dy = this.y[i] - y;
        const d = dx * dx + dz * dz + (dy > 0 ? dy * dy * 9 : dy * dy * 3);
        if (d < bd) { bd = d; best = i; }
      }
    }
    return best;
  }

  // nodes within r of a point (same level band)
  within(x, y, z, r, out = []) {
    out.length = 0;
    const R = Math.ceil(r / this.cs), cx = Math.floor(x / this.cs), cz = Math.floor(z / this.cs);
    for (let ix = cx - R; ix <= cx + R; ix++) for (let iz = cz - R; iz <= cz + R; iz++) {
      const l = this.grid.get(this.key(ix, iz)); if (!l) continue;
      for (const i of l) { const dx = this.x[i] - x, dz = this.z[i] - z; if (dx * dx + dz * dz <= r * r && Math.abs(this.y[i] - y) < 2.6) out.push(i); }
    }
    return out;
  }

  // A*: node ids from a to b (inclusive) or null. extra(i) adds cost per node (danger, crowding).
  path(a, b, extra = null, maxExpand = 7000) {
    if (a < 0 || b < 0) return null;
    if (a === b) return [a];
    const t0 = performance.now();
    const run = ++this.run, g = this.g, f = this.f, came = this.came, st = this.stamp, cl = this.closed, H = this.heap;
    const bx = this.x[b], by = this.y[b], bz = this.z[b];
    const h = i => Math.hypot(this.x[i] - bx, this.z[i] - bz) + Math.abs(this.y[i] - by) * .5;
    let size = 0;
    const push = i => { let k = size++; H[k] = i; while (k > 0) { const p = (k - 1) >> 1; if (f[H[p]] <= f[i]) break; H[k] = H[p]; k = p; } H[k] = i; };
    const pop = () => {
      const top = H[0], last = H[--size]; let k = 0;
      for (;;) { let c = k * 2 + 1; if (c >= size) break; if (c + 1 < size && f[H[c + 1]] < f[H[c]]) c++; if (f[H[c]] >= f[last]) break; H[k] = H[c]; k = c; }
      H[k] = last; return top;
    };
    st[a] = run; g[a] = 0; f[a] = h(a); came[a] = -1; push(a);
    let found = false, exp = 0;
    while (size > 0) {
      const i = pop();
      if (cl[i] === run) continue;
      cl[i] = run; exp++;
      if (i === b) { found = true; break; }
      if (exp > maxExpand) break;
      for (let e = this.off[i], E = this.off[i + 1]; e < E; e++) {
        const j = this.to[e]; if (cl[j] === run) continue;
        const ng = g[i] + this.cost[e] + (extra ? extra(j) : 0);
        if (st[j] !== run || ng < g[j]) { st[j] = run; g[j] = ng; f[j] = ng + h(j); came[j] = i; push(j); }
      }
    }
    this.stats.searches++; this.stats.ms += performance.now() - t0; this.stats.expanded += exp;
    if (!found) return null;
    const out = []; for (let i = b; i !== -1; i = came[i]) out.push(i);
    return out.reverse();
  }

  // type of the edge a -> b (0 walk, 1 drop, 2 mantle) or -1
  edgeType(a, b) {
    for (let e = this.off[a], E = this.off[a + 1]; e < E; e++) if (this.to[e] === b) return this.type[e];
    return -1;
  }

  // random node near a point (for spreading out goals)
  around(x, y, z, r, rnd = Math.random) {
    const l = this.within(x, y, z, r, this._w || (this._w = []));
    return l.length ? l[Math.floor(rnd() * l.length)] : this.nearest(x, y, z, r + 4);
  }
}
