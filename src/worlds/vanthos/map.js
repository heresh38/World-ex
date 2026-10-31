// VANTHOS city plan: an irregular circular city ~4 km across around the Spire.
// The Crown rings the Spire's crater; six sector districts fill the middle band; the Outskirts run around the edge.
// Roads: three radial highways (25 m, elevated through the middle band), two ring roads (25 m), and an
// axis-aligned street grid per district (14 m streets, 80 x 100 m blocks split into lots by 6 m alleys).
import { DISTRICTS } from './districts.js';

export const CROWN_R = 600, OUTER_R = 1450, SPIRE_R = 92, CRATER_R = 255;
export const HIGHWAYS = [105, 225, 345].map(d => d * Math.PI / 180);
export const MAJOR = 25, STREET = 14, ALLEY = 6, BW = 80, BD = 100;
export const WATER_Y = -1.2;

function hash(x, z, s) { let h = (Math.imul(x | 0, 374761393) + Math.imul(z | 0, 668265263) + Math.imul(s, 982451653)) | 0; h = Math.imul(h ^ (h >>> 13), 1274126177); return ((h ^ (h >>> 16)) >>> 0) / 4294967295; }
function vnoise(x, z, s) {
  const xi = Math.floor(x), zi = Math.floor(z), xf = x - xi, zf = z - zi, u = xf * xf * (3 - 2 * xf), v = zf * zf * (3 - 2 * zf);
  const a = hash(xi, zi, s), b = hash(xi + 1, zi, s), c = hash(xi, zi + 1, s), d = hash(xi + 1, zi + 1, s);
  return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v;
}
export function fbm(x, z, s, o = 4) { let t = 0, a = .5, n = 0; for (let i = 0; i < o; i++) { t += a * vnoise(x, z, s + i * 17); n += a; x *= 2.03; z *= 2.03; a *= .5; } return t / n; }
const ss = (a, b, x) => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); };
const angOf = (x, z) => { let a = Math.atan2(z, x); if (a < 0) a += Math.PI * 2; return a; };
const DEG = Math.PI / 180;

export class VanthosMap {
  constructor(seed = 4401) {
    this.seed = seed;
    this.lots = [];          // {x, z, w, d, district}
    this.blocks = [];        // {x, z, w, d, district}
    this.build();
  }

  // City edge: an irregular circle.
  edge(a) { return 1850 + 110 * Math.sin(3 * a + 1) + 70 * Math.sin(5 * a + 2.3) + 40 * Math.sin(9 * a); }

  district(x, z) {
    const r = Math.hypot(x, z), a = angOf(x, z);
    if (r < CROWN_R) return DISTRICTS.find(d => d.id === 'crown');
    if (r > OUTER_R + 15) return DISTRICTS.find(d => d.id === 'outskirts');
    for (const d of DISTRICTS) if (d.a0 !== undefined && this.inSector(a, d.a0, d.a1)) return d;
    return DISTRICTS[0];
  }

  inSector(a, a0, a1, pad = 0) {
    const s = (a0 + pad) * DEG, e = (a1 - pad) * DEG;
    const A = ((a - s) % (Math.PI * 2) + Math.PI * 2) % (Math.PI * 2);
    return A <= e - s;
  }

  flooded(x, z) {
    const d = DISTRICTS.find(q => q.id === 'flooded'), r = Math.hypot(x, z), a = angOf(x, z);
    const ang = Math.min(Math.abs(((a - d.a0 * DEG) + Math.PI * 3) % (Math.PI * 2) - Math.PI), Math.abs(((a - d.a1 * DEG) + Math.PI * 3) % (Math.PI * 2) - Math.PI));
    if (!this.inSector(a, d.a0, d.a1)) return 0;
    const edge = Math.min(ang * r, r - CROWN_R, OUTER_R - r);
    return ss(0, 50, edge);
  }

  // Ground height: flat streets, the Spire's crater, the flooded basin, hills beyond the city edge.
  height(x, z) {
    const r = Math.hypot(x, z), a = angOf(x, z);
    let h = 0;
    if (r < CRATER_R + 50) {
      if (r < SPIRE_R) h = 0;
      else {
        const t = (r - SPIRE_R) / (CRATER_R - SPIRE_R);
        h = r < CRATER_R ? -16 * Math.sin(Math.min(1, t) * Math.PI) ** .8 + (fbm(x * .05, z * .05, 3) - .5) * 3 : 2.2 * (1 - ss(CRATER_R, CRATER_R + 50, r));
      }
    }
    const f = this.flooded(x, z);
    if (f > 0) h = h * (1 - f) - 2.4 * f;
    const E = this.edge(a);
    if (r > E - 40) {
      const o = r - E + 40;
      h += o * .05 + ss(0, 300, o) * (fbm(x * .004, z * .004, 9) * 60 + Math.pow(fbm(x * .0012, z * .0012, 13), 2) * 90);
    }
    return h;
  }

  nearHighway(x, z, pad) {
    const r = Math.hypot(x, z);
    for (const a of HIGHWAYS) {
      const t = x * Math.cos(a) + z * Math.sin(a);
      if (t < 0) continue;
      const d = Math.abs(-x * Math.sin(a) + z * Math.cos(a));
      if (d < MAJOR / 2 + pad && r > SPIRE_R) return true;
    }
    return false;
  }

  nearRing(r, pad) { return Math.abs(r - CROWN_R) < MAJOR / 2 + pad || Math.abs(r - OUTER_R) < MAJOR / 2 + pad; }

  // Blocks and lots, district by district (each district has its own grid offset and density).
  build() {
    const pitchX = BW + STREET, pitchZ = BD + STREET;
    for (const D of DISTRICTS) {
      const ox = hash(D.id.length, 3, this.seed) * pitchX, oz = hash(D.id.length, 7, this.seed) * pitchZ;
      for (let gx = -24; gx <= 24; gx++) for (let gz = -24; gz <= 24; gz++) {
        const cx = gx * pitchX + ox, cz = gz * pitchZ + oz;
        if (this.district(cx, cz) !== D) continue;
        const ok = [[-1, -1], [1, -1], [-1, 1], [1, 1], [0, 0]].every(([sx, sz]) => {
          const x = cx + sx * BW / 2, z = cz + sz * BD / 2, r = Math.hypot(x, z);
          return this.district(x, z) === D && !this.nearRing(r, 6) && !this.nearHighway(x, z, 8) && r > CRATER_R + 50 && r < this.edge(angOf(x, z)) - 60;
        });
        if (!ok) continue;
        if (D.sparse && hash(gx, gz, this.seed + 5) > D.sparse) continue;
        const b = { x: cx, z: cz, w: BW, d: BD, district: D, gx, gz };
        this.blocks.push(b);
        // lots: 2 x 2 split by alleys, or one big lot for landmarks
        const big = hash(gx, gz, this.seed + 11) < (D.bigLots || .15);
        if (big) this.lots.push({ x: cx, z: cz, w: BW - 4, d: BD - 4, district: D, block: b, big: true });
        else for (const [sx, sz] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) {
          const w = (BW - ALLEY) / 2, d = (BD - ALLEY) / 2;
          this.lots.push({ x: cx + sx * (w + ALLEY) / 2, z: cz + sz * (d + ALLEY) / 2, w: w - 2, d: d - 2, district: D, block: b });
        }
      }
    }
  }

  // street axes for markings / minimap
  streetLines(D) {
    const out = [];
    for (const b of this.blocks) if (b.district === D) out.push(b);
    return out;
  }
}
