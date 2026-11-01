// Physical reloads. Every kinetic and horror gun GLB carries named moving parts (weapons.py `moving`/`loose`):
//   mag, bolt, charge, slide, pump, crane > cylinder > rounds, hatch, biomass, and spare props x_shell, x_round,
//   x_casing, x_speedloader (hidden; cloned when needed).
// A reload is a list of keyframed segments (procedural, no clips): the gun pose (holder offsets), the off hand (a gun-space
// target resolved against moving parts, so it stays on the mag / bolt / shell while they move), part offsets, visibility
// state and timed events (drop the old mag, seat the new one, grant ammo, sounds). The same pose drives the first-person
// viewmodel and the third-person avatar's gun (the avatar's left arm reaches the hand target by two-bone IK).
// Old magazines, casings, the speedloader and spent biomass husks fall into the world as pooled physical drops.
import * as THREE from 'three';
import { ARCHETYPES } from './data.js';

const _v = new THREE.Vector3(), _v2 = new THREE.Vector3(), _q = new THREE.Quaternion(), _q2 = new THREE.Quaternion(),
  _e = new THREE.Euler(), _m = new THREE.Matrix4(), _box = new THREE.Box3();
const Z = new THREE.Vector3(0, 0, 1), X = new THREE.Vector3(1, 0, 0);
const BACK = new THREE.Vector3(0, 0, -1);           // gun space: barrel +Z, so rearward is -Z
const PARTS = ['mag', 'bolt', 'charge', 'slide', 'pump', 'crane', 'cylinder', 'rounds', 'hatch', 'biomass'];

// ------------------------------------------------------------------ easing + sampling
const EASE = {
  s: x => x * x * x * (x * (x * 6 - 15) + 10),            // smootherstep (default)
  lin: x => x,
  out: x => 1 - (1 - x) ** 3,                              // fast start (a snap, a slap, a spring)
  in: x => x * x * x,
  back: x => { const c = 1.9; return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2; },   // overshoot (wet pops)
};
// keys: [[t, v0, v1, ..., ease?], ...] with t in 0..1 of the segment; writes n values into out
function sampleKeys(keys, t, n, out) {
  if (!keys || !keys.length) { for (let i = 0; i < n; i++) out[i] = 0; return out; }
  let k = 0; while (k < keys.length - 1 && keys[k + 1][0] <= t) k++;
  const a = keys[k], b = keys[Math.min(k + 1, keys.length - 1)];
  if (a === b || t <= a[0]) { for (let i = 0; i < n; i++) out[i] = +a[1 + i] || 0; return out; }
  const f = Math.min(1, (t - a[0]) / Math.max(1e-6, b[0] - a[0]));
  const ez = EASE[typeof b[b.length - 1] === 'string' ? b[b.length - 1] : 's'] || EASE.s, w = ez(f);
  for (let i = 0; i < n; i++) { const x = +a[1 + i] || 0, y = +b[1 + i] || 0; out[i] = x + (y - x) * w; }
  return out;
}
const lerp = (a, b, t) => a + (b - a) * t;

// ------------------------------------------------------------------ model info (rest transforms + local boxes per archetype)
const INFO = {};
function localBox(obj) {
  const box = new THREE.Box3();
  obj.updateMatrixWorld(true);
  const inv = _m.copy(obj.matrixWorld).invert();
  obj.traverse(o => {
    if (!o.isMesh) return;
    if (!o.geometry.boundingBox) o.geometry.computeBoundingBox();
    const b = _box.copy(o.geometry.boundingBox).applyMatrix4(new THREE.Matrix4().multiplyMatrices(inv, o.matrixWorld));
    box.union(b);
  });
  return box;
}
export function gunInfo(assets, arch) {
  if (INFO[arch]) return INFO[arch];
  const A = ARCHETYPES[arch], gl = assets.models[A.model];
  const info = { parts: {}, box: {} };
  if (gl && gl.scene) {
    const sc = gl.scene; sc.updateMatrixWorld(true);
    sc.traverse(o => {
      if (PARTS.includes(o.name) || o.name.startsWith('x_')) {
        info.parts[o.name] = true;
        info.box[o.name] = localBox(o);
      }
      if (o.name === 'foregrip') info.fore = o.getWorldPosition(new THREE.Vector3());
    });
  }
  info.fore = info.fore || new THREE.Vector3(0, -.02, .3);
  return (INFO[arch] = info);
}

// ------------------------------------------------------------------ a posable gun clone (viewmodel, avatar, or a hidden proxy)
export class GunRig {
  constructor(root, arch, assets) {
    this.root = root; this.arch = arch; this.info = gunInfo(assets, arch);
    this.p = {}; this.rest = {};
    root.traverse(o => {
      if (PARTS.includes(o.name) && !this.p[o.name]) this.p[o.name] = o;
      if (o.name.startsWith('x_')) { o.visible = false; this.p[o.name] = o; }
    });
    for (const [k, o] of Object.entries(this.p)) this.rest[k] = { pos: o.position.clone(), q: o.quaternion.clone() };
    this.extra = {};
    this.posed = false;
  }

  // lazily cloned props: spare mag next to the real one, shells, rounds, the speedloader (on the cylinder)
  prop(name) {
    if (this.extra[name] !== undefined) return this.extra[name];
    let o = null;
    const src = name === 'spare' ? this.p.mag : name === 'loader' ? this.p.x_speedloader : name === 'husk' ? this.p.biomass : this.p['x_' + name];
    if (src) {
      o = src.clone(true); o.visible = false; o.name = 'rl_' + name;
      const parent = name === 'loader' ? this.p.cylinder : (src.parent || this.root);
      if (parent) parent.add(o);
      if (name === 'husk') o.traverse(m => { if (m.isMesh) { m.material = m.material.clone(); m.material.color.multiplyScalar(.35); if (m.material.emissive) m.material.emissiveIntensity *= .15; } });
    }
    return (this.extra[name] = o);
  }

  set(name, pos, q, vis = true) {
    const o = this.p[name]; if (!o) return;
    const r = this.rest[name];
    o.position.copy(r.pos); if (pos) o.position.add(pos);
    o.quaternion.copy(r.q); if (q) o.quaternion.multiply(q);
    o.visible = vis;
  }

  // apply a pose (null = rest). pose fields are gun-space offsets from each part's rest transform.
  apply(P) {
    const p = this.p;
    if (!P) {
      if (!this.posed) return;
      this.posed = false;
      for (const [k, r] of Object.entries(this.rest)) { const o = p[k]; o.position.copy(r.pos); o.quaternion.copy(r.q); o.visible = !k.startsWith('x_'); }
      for (const o of Object.values(this.extra)) if (o) o.visible = false;
      return;
    }
    this.posed = true;
    const st = P.st;
    // magazine (old) and spare
    if (p.mag) {
      this.set('mag', _v.fromArray(P.mag, 0), _q.setFromEuler(_e.set(P.mag[3], P.mag[4], P.mag[5])), st.mag);
      const sp = st.spare ? this.prop('spare') : this.extra.spare;
      if (sp) {
        sp.visible = st.spare;
        if (st.spare) {
          const r = this.rest.mag;
          sp.position.copy(r.pos).add(_v.fromArray(P.spare, 0));
          sp.quaternion.copy(r.q).multiply(_q.setFromEuler(_e.set(P.spare[3], P.spare[4], P.spare[5])));
        }
      }
    }
    for (const k of ['bolt', 'charge', 'slide', 'pump']) {
      if (!p[k]) continue;
      _v.copy(BACK).multiplyScalar(P[k]);
      if (k === 'charge' && P.chargeUp) _v.y += P.chargeUp;
      this.set(k, _v, k === 'bolt' && P.boltRot ? _q.setFromAxisAngle(Z, P.boltRot) : null);
    }
    if (p.crane) this.set('crane', null, _q.setFromAxisAngle(Z, P.crane));
    if (p.cylinder) this.set('cylinder', null, _q.setFromAxisAngle(Z, P.spin));
    if (p.rounds) p.rounds.visible = st.rounds;
    if (p.hatch) this.set('hatch', null, _q.setFromAxisAngle(this.hatchAxis(), P.hatch));
    if (p.biomass) this.set('biomass', _v.fromArray(P.bio, 0), _q.setFromEuler(_e.set(P.bio[3], P.bio[4], P.bio[5])), st.bio);
    // loose props
    if (p.x_speedloader) {
      const L = st.loader ? this.prop('loader') : this.extra.loader;
      if (L) { L.visible = st.loader; if (st.loader) { L.position.set(0, 0, -.0245 + P.loader[2]).add(_v.set(P.loader[0], P.loader[1], 0)); L.quaternion.setFromAxisAngle(Z, P.loader[3]); } }
    }
    for (const k of ['shell', 'round']) {
      if (!p['x_' + k]) continue;
      const o = st[k] ? this.prop(k) : this.extra[k];
      if (o) { o.visible = !!st[k]; if (st[k]) { o.position.fromArray(P[k], 0); o.quaternion.setFromEuler(_e.set(P[k][3], P[k][4], P[k][5])); } }
    }
  }

  hatchAxis() { return this.arch === 'brood' ? X : Z; }

  // gun-space anchor for the off hand (uses the parts as currently posed)
  anchor(name, out) {
    const p = this.p, b = this.info.box;
    this.root.updateMatrixWorld(true);
    const inv = _m.copy(this.root.matrixWorld).invert();
    const at = (o, local) => out.copy(local).applyMatrix4(o.matrixWorld).applyMatrix4(inv);
    switch (name) {
      case 'mag': if (p.mag && b.mag) return at(p.mag, _v2.set((b.mag.min.x + b.mag.max.x) / 2, b.mag.min.y + .035, (b.mag.min.z + b.mag.max.z) / 2)); break;
      case 'spare': { const s = this.prop('spare'); if (s && b.mag) return at(s, _v2.set((b.mag.min.x + b.mag.max.x) / 2, b.mag.min.y + .035, (b.mag.min.z + b.mag.max.z) / 2)); break; }
      case 'magbase': if (p.mag && b.mag) return at(p.mag, _v2.set((b.mag.min.x + b.mag.max.x) / 2, b.mag.min.y, (b.mag.min.z + b.mag.max.z) / 2)); break;
      case 'loader': { const L = this.prop('loader'); if (L) return at(L, _v2.set(0, 0, -.03)); break; }
      case 'cyl': if (p.cylinder) return at(p.cylinder, _v2.set(.012, -.01, 0)); break;
      case 'ejector': if (p.crane) return at(p.crane, _v2.set(-.004, .025, .06)); break;
      case 'shell': { const o = this.prop('shell'); if (o) return at(o, _v2.set(0, -.016, -.05)); break; }
      case 'round': { const o = this.prop('round'); if (o) return at(o, _v2.set(-.008, .004, -.02)); break; }
      default: {
        const o = p[name];
        if (o) { const bb = b[name]; return at(o, bb ? bb.getCenter(_v2) : _v2.set(0, 0, 0)); }
      }
    }
    return out.copy(this.info.fore);
  }
}

// ------------------------------------------------------------------ sequences
// gun: holder offsets [x, y, z, pitch(+ muzzle up), yaw(+ muzzle left), roll(- shows the left flank / mag well)] in view space
// hand: [t, anchor, dx, dy, dz, rx, ry, rz] — anchor 'cur' = where the hand was when the segment began
// mag / spare / bio / shell / round: [dx, dy, dz, rx, ry, rz]; scalars: bolt, charge, slide, pump (m back), boltRot, crane, spin, hatch
// ev: [t, name, arg] (sfx:<kind>, drop, spare, seat, grant, eject, rounds, loader, release, husk, glow, drip, cur)
const POUCH = ['pouch', 0, 0, 0, .5, .3, -.6];

function seg(dur, ch, ev = []) { return { dur, ch, ev }; }

// gun pose while chambering (empty reloads)
const G2 = { rifle: [-.05, .05, .03, .2, .3, -.3], dmr: [-.05, .05, .03, .2, .3, -.3], carbine: [-.04, .05, .03, .2, .2, -.2],
  ksmg: [-.04, .05, .03, .2, .2, -.2], pistol: [-.06, .05, .05, .3, .1, .2] };
// magazine guns: per-gun differences in how the old mag leaves, how the new one seats and how a round is chambered
function magReload(arch, empty) {
  const segs = [];
  const tilt = { rifle: [-.04, .03, .03, .22, .32, -.55], carbine: [-.05, .04, .02, .16, .26, -.42], dmr: [-.05, .02, .05, .26, .3, -.5],
    ksmg: [-.06, .05, .02, .12, .36, -.62], pistol: [-.09, .06, .06, .38, .22, -.35] }[arch];
  const t2 = tilt.slice(); t2[5] *= .8; t2[3] += .06;
  // old mag out
  let magOut, handOut;
  if (arch === 'rifle') {          // stamped rifle: thumb the catch, rock the mag forward off its front lip, toss it
    magOut = [[0, 0, 0, 0, 0, 0, 0], [.25, 0, 0, 0, 0, 0, 0], [.42, 0, -.004, .004, -.45, 0, 0], [.55, 0, -.07, .02, -.6, 0, .1]];
    handOut = [[0, 'fore', 0, 0, 0, 0, 0, 0], [.22, 'mag', 0, -.01, -.01, -.2, 0, -.3], [.55, 'mag', 0, -.01, -.01, -.3, 0, -.3], [.7, 'pouch', .04, .1, .1, .4, .3, -.5]];
  } else if (arch === 'ksmg') {    // compact SMG: hook the mag with the fingers and strip it forward out of the well
    magOut = [[0, 0, 0, 0, 0, 0, 0], [.24, 0, 0, 0, 0, 0, 0], [.4, 0, -.03, .012, -.15, 0, 0], [.52, 0, -.09, .05, -.35, 0, 0]];
    handOut = [[0, 'fore', 0, 0, 0, 0, 0, 0], [.2, 'mag', 0, -.02, .02, -.3, 0, -.2], [.52, 'mag', 0, -.02, .03, -.4, 0, -.2], [.7, 'pouch', .05, .12, .1, .4, .3, -.5]];
  } else {                         // drop-free: press the release, the empty falls clear on its own
    magOut = [[0, 0, 0, 0, 0, 0, 0], [.2, 0, 0, 0, 0, 0, 0], [.32, 0, -.035, 0, .04, 0, 0, 'in']];
    handOut = [[0, 'fore', 0, 0, 0, 0, 0, 0], [.2, 'fore', -.01, -.06, -.04, .25, .1, -.2], [.42, 'pouch', .02, .14, .12, .4, .25, -.4]];
    if (arch === 'pistol') handOut = [[0, 'fore', 0, 0, 0, 0, 0, 0], [.2, 'fore', .02, -.04, .02, .2, .1, -.2], [.42, 'pouch', .02, .18, .14, .4, .25, -.4]];
  }
  const dropT = magOut[magOut.length - 1][0];
  // new mag: from the pouch, line up under the well, insert, seat (style per gun)
  const pre = arch === 'rifle' ? [0, -.035, .012, -.42, 0, 0] : arch === 'ksmg' ? [0, -.05, .006, -.08, 0, 0] : [0, -.05, -.002, .06, 0, 0];
  const seatT = arch === 'dmr' ? .9 : arch === 'pistol' ? .86 : .88;
  const spare = [[0, 0, -.42, -.18, .5, .2, .3], [.62, 0, -.42, -.18, .5, .2, .3], [.74, ...pre.map(v => v * 1.7)], [.8, ...pre]];
  if (arch === 'rifle') spare.push([.86, 0, -.004, .003, -.32, 0, 0], [.92, 0, 0, 0, 0, 0, 0, 'out']);               // hook the lip, rock back
  else if (arch === 'dmr') spare.push([.85, 0, -.008, 0, 0, 0, 0], [.9, 0, 0, 0, 0, 0, 0, 'out']);                   // firm push
  else spare.push([seatT, 0, 0, 0, 0, 0, 0, 'out']);
  const hand = handOut.slice();
  hand.push([.62, 'pouch', 0, 0, 0, .5, .3, -.6], [.74, 'spare', 0, 0, 0, -.25, .05, -.25], [.84, 'spare', 0, 0, 0, -.2, 0, -.2]);
  if (arch === 'dmr') hand.push([.93, 'magbase', 0, -.03, 0, -.1, 0, -.1], [.97, 'magbase', 0, -.004, 0, -.1, 0, -.1, 'out']);      // tap the base
  else if (arch === 'carbine' || arch === 'pistol') hand.push([.9, 'magbase', 0, -.035, 0, -.1, 0, -.15], [.94, 'magbase', 0, -.006, 0, -.1, 0, -.15, 'out']);  // slap
  else hand.push([.95, 'spare', 0, -.006, 0, -.2, 0, -.2]);
  hand.push([1, 'spare', 0, -.012, 0, -.2, 0, -.2]);
  const slapT = arch === 'dmr' ? .97 : arch === 'carbine' || arch === 'pistol' ? .94 : seatT;
  const gun = [[0, 0, 0, 0, 0, 0, 0], [.22, ...tilt], [.4, ...tilt.map((v, i) => i === 1 ? v - .01 : v)], [.5, ...tilt],
    [.7, ...t2], [.84, ...t2], [slapT, ...t2.map((v, i) => i === 1 ? v + .012 : i === 3 ? v + .05 : v), 'out'], [1, ...t2]];
  const ev = [[.18, 'sfx', 'magrelease'], [dropT, 'drop'], [.5, 'sfx', 'pouch'], [.62, 'spare'], [seatT - .04, 'sfx', 'magin'], [slapT, 'seat'],
    [slapT, 'sfx', arch === 'dmr' ? 'tap' : 'slap']];
  if (arch === 'pistol' || arch === 'carbine') ev.push([.36, 'sfx', 'magclatter']);
  const ch1 = { gun, hand, mag: magOut, spare };
  if (empty && arch === 'pistol') ch1.slide = [[0, .045]];          // locked back on the empty mag
  segs.push(seg(1, ch1, ev));
  // empty: chamber a round (per-gun manual of arms)
  if (empty) {
    const H = { rifle: ['bolt', .004, -.03, -.01, -.35, 0, .25], carbine: ['charge', .0, .02, -.02, -.6, 0, -.25], dmr: ['bolt', .004, -.032, .0, -.35, 0, .25],
      ksmg: ['charge', .01, -.0, .0, -.3, 0, -.5], pistol: ['slide', 0, .015, -.06, -.5, -.2, -.35] }[arch];
    const g2 = G2[arch];
    const travel = { rifle: .095, carbine: .065, dmr: .07, ksmg: .08, pistol: .045 }[arch];
    const k = arch === 'pistol' ? 'slide' : arch === 'carbine' || arch === 'ksmg' ? 'charge' : 'bolt';
    const pull = [[0, 0], [.42, 0], [.62, travel], [.7, travel], [.76, 0, 'out']];
    const ch = { gun: [[0, ...t2], [.35, ...g2], [.62, ...g2.map((v, i) => i === 2 ? v + .015 : v)], [.76, ...g2.map((v, i) => i === 3 ? v + .04 : v), 'out'], [1, ...g2]],
      hand: [[0, 'cur', 0, 0, 0, .2, 0, -.2], [.4, H[0], ...H.slice(1)], [.62, H[0], ...H.slice(1)], [.72, H[0], H[1], H[2] + .02, H[3] - .03, H[4], H[5], H[6]], [1, 'fore', .02, .03, .04, .1, 0, 0]] };
    ch[k] = pull;
    if (k === 'charge' && arch !== 'ksmg') ch.bolt = [[0, 0], [.42, 0], [.62, .05], [.7, .05], [.76, 0, 'out']];
    if (arch === 'ksmg') { ch.chargeUp = [[0, 0], [.62, 0], [.68, .006], [.72, .006], [.76, 0, 'out']]; ch.bolt = [[0, 0], [.42, 0], [.62, .05], [.7, .05], [.76, 0, 'out']]; }
    if (arch === 'pistol') ch.slide = [[0, .045], [.42, .045], [.6, .05], [.66, 0, 'out']];     // slingshot from slide lock
    segs.push(seg(.32, ch, [[.6, 'sfx', arch === 'pistol' ? 'slideback' : 'rackback'], [arch === 'pistol' ? .66 : .76, 'sfx', arch === 'pistol' ? 'slidefwd' : 'rackfwd']]));
  }
  // back on the foregrip
  segs.push(seg(.24, { gun: [[0, ...(empty ? G2[arch] : t2)], [1, 0, 0, 0, 0, 0, 0]],
    hand: [[0, 'cur', 0, 0, 0, .2, 0, -.2], [.85, 'fore', 0, 0, 0, 0, 0, 0], [1, 'fore', 0, 0, 0, 0, 0, 0]] }));
  return segs;
}

function revolverReload() {
  const g1 = [-.06, .03, .05, .25, .3, -.7], g2 = [-.08, .12, .03, 1.05, .3, -.35], g3 = [-.06, .02, .05, .1, .25, -.75];
  return [seg(1, {
    gun: [[0, 0, 0, 0, 0, 0, 0], [.12, ...g1], [.24, ...g1], [.32, ...g2], [.4, ...g2.map((v, i) => i === 1 ? v - .02 : v)], [.46, ...g2], [.56, ...g3], [.82, ...g3],
      [.87, ...g3.map((v, i) => i === 5 ? v - .15 : v), 'out'], [1, 0, 0, 0, 0, 0, 0]],
    hand: [[0, 'fore', 0, 0, 0, 0, 0, 0], [.12, 'cyl', .01, 0, 0, -.2, 0, -.6], [.22, 'cyl', .01, 0, 0, -.2, 0, -.6], [.32, 'ejector', 0, 0, .01, -.2, 0, -.4],
      [.38, 'ejector', 0, 0, -.012, -.2, 0, -.4], [.42, 'ejector', 0, 0, .01, -.2, 0, -.4], [.52, 'pouch', 0, .05, .05, .5, .3, -.6], [.6, 'pouch', 0, 0, 0, .5, .3, -.6],
      [.7, 'loader', 0, 0, 0, -.2, 0, -.5], [.76, 'loader', 0, 0, 0, -.2, 0, -.5], [.8, 'loader', .01, 0, -.02, -.2, 0, -.5], [.84, 'cyl', .03, .0, -.01, -.2, 0, -.6],
      [.88, 'cyl', -.006, .0, 0, -.2, 0, -.6, 'out'], [1, 'fore', 0, 0, 0, 0, 0, 0]],
    crane: [[0, 0], [.16, 0], [.24, -1.5, 'back'], [.84, -1.5], [.89, 0, 'out']],
    spin: [[0, 0], [.24, 0], [.3, .6, 'out'], [.84, .6], [1, .6 + Math.PI * 2 / 3 * 4, 'out']],
    loader: [[0, .03, -.2, -.3, 0], [.6, .03, -.2, -.3, 0], [.7, 0, 0, -.05, 0], [.74, 0, 0, -.01, 0], [.76, 0, 0, 0, .25], [.79, 0, 0, 0, .25], [.82, -.03, .02, -.12, .25]],
  }, [[.1, 'sfx', 'latch'], [.22, 'sfx', 'cylopen'], [.37, 'eject'], [.37, 'sfx', 'eject'], [.5, 'sfx', 'pouch'], [.6, 'loader'], [.74, 'sfx', 'speedload'],
    [.77, 'release'], [.77, 'seat'], [.8, 'drop', 'loader'], [.88, 'sfx', 'cylclose']])];
}

// pump: one shell at a time into the tube from the loading port under the receiver; racks at the end if it was empty
function pumpReload(n, empty) {
  const g = [-.05, .04, .04, .18, .2, -.95];
  const segs = [seg(1, { gun: [[0, 0, 0, 0, 0, 0, 0], [1, ...g]], hand: [[0, 'fore', 0, 0, 0, 0, 0, 0], [1, 'pouch', .02, .1, .12, .5, .3, -.6]] }, [[.6, 'sfx', 'pouch']])];
  for (let i = 0; i < n; i++) {
    segs.push(seg(1, {
      gun: [[0, ...g], [.62, ...g], [.72, ...g.map((v, i) => i === 1 ? v + .006 : i === 3 ? v + .03 : v), 'out'], [1, ...g]],
      shell: [[0, .02, -.3, -.15, 0, 0, 0], [.35, .015, -.07, .02, -.2, 0, 0], [.55, 0, -.012, .065, -.08, 0, 0], [.72, 0, .046, .14, 0, 0, 0, 'out']],
      hand: [[0, 'pouch', 0, 0, 0, .5, .3, -.6], [.1, 'shell', 0, 0, 0, -.3, 0, -.5], [.55, 'shell', 0, 0, 0, -.2, 0, -.5], [.66, 'free', 0, .01, .12, -.2, 0, -.5],
        [.74, 'free', 0, .015, .15, -.15, 0, -.5], [1, 'pouch', .01, .05, .06, .5, .3, -.6]],
    }, [[0, 'shell', 1], [.6, 'sfx', 'shellin'], [.72, 'shell', 0], [.72, 'grant', 1]]));
  }
  const end = { gun: [[0, ...g], [.5, -.03, .02, .02, .1, .1, -.3], [1, 0, 0, 0, 0, 0, 0]], hand: [[0, 'cur', 0, 0, 0, .5, .3, -.6], [.6, 'pump', 0, -.02, 0, 0, 0, 0], [1, 'pump', 0, -.02, 0, 0, 0, 0]] };
  const ev = [];
  if (empty) {
    end.pump = [[0, 0], [.6, 0], [.75, .075, 'out'], [.92, 0, 'out']];
    end.gun.splice(2, 0, [.75, -.03, .015, .0, .14, .1, -.2], [.92, -.03, .02, .03, .12, .1, -.25]);
    ev.push([.68, 'sfx', 'pumpback'], [.88, 'sfx', 'pumpfwd']);
  }
  segs.push(seg(empty ? 1.6 : .9, end, ev));
  return segs;
}
// bolt-action: roll the rifle to show the port, bolt up and back, thumb rounds in one by one, bolt forward and down
function boltReload(n) {
  const g = [-.07, .09, .06, .2, .22, .6];
  const knob = ['bolt', 0, 0, 0, -.45, -.2, -.5];
  const segs = [seg(1, {
    gun: [[0, 0, 0, 0, 0, 0, 0], [.4, ...g], [1, ...g]],
    hand: [[0, 'fore', 0, 0, 0, 0, 0, 0], [.35, ...knob], [.7, ...knob], [1, 'pouch', -.04, .12, .12, .5, .3, -.6]],
    boltRot: [[0, 0], [.4, 0], [.52, -1.05, 'out'], [1, -1.05]], bolt: [[0, 0], [.52, 0], [.68, .085, 'out'], [1, .085]],
  }, [[.5, 'sfx', 'boltup'], [.66, 'sfx', 'boltback'], [.9, 'sfx', 'pouch']])];
  for (let i = 0; i < n; i++) {
    segs.push(seg(1, {
      gun: [[0, ...g], [.6, ...g], [.7, ...g.map((v, i) => i === 1 ? v - .005 : v), 'out'], [1, ...g]],
      boltRot: [[0, -1.05]], bolt: [[0, .085]],
      round: [[0, -.15, -.15, -.2, 0, 0, 0], [.35, -.07, .1, -.005, 0, .2, 0], [.55, -.022, .09, 0, 0, 0, 0], [.7, -.004, .072, .002, 0, 0, 0, 'out']],
      hand: [[0, 'pouch', 0, 0, 0, .5, .3, -.6], [.12, 'round', 0, 0, 0, -.45, -.2, -.5], [.55, 'round', 0, 0, 0, -.45, -.2, -.5], [.7, 'round', 0, -.004, 0, -.45, -.2, -.5],
        [1, 'pouch', -.03, .1, .1, .5, .3, -.6]],
    }, [[0, 'round', 1], [.66, 'sfx', 'roundin'], [.7, 'round', 0], [.7, 'grant', 1]]));
  }
  segs.push(seg(1.15, {
    gun: [[0, ...g], [.55, ...g], [.62, ...g.map((v, i) => i === 3 ? v + .03 : v), 'out'], [1, 0, 0, 0, 0, 0, 0]],
    hand: [[0, 'cur', 0, 0, 0, .5, .3, -.6], [.3, ...knob], [.65, ...knob], [1, 'fore', 0, 0, 0, 0, 0, 0]],
    bolt: [[0, .085], [.32, .085], [.46, 0, 'out']], boltRot: [[0, -1.05], [.48, -1.05], [.6, 0, 'out']],
  }, [[.44, 'sfx', 'boltfwd'], [.58, 'sfx', 'boltdown']]));
  return segs;
}
// living guns: the hatch peels open wetly, the spent husk slops out, a fresh biomass is pushed in, the hatch squelches shut
function bioReload(arch) {
  const brood = arch === 'brood', bile = arch === 'bile';
  const open = brood ? 1.25 : bile ? -1.35 : 1.45;        // brood lid lifts at the back (about X); flank flaps swing out (about Z)
  const g = brood ? [-.07, -.1, -.03, -.42, .3, -.2] : [-.1, .06, .1, .22, .5, -.8];
  const bioOff = brood ? [0, .2, -.16] : [.16, -.1, -.12];
  return [seg(1, {
    gun: [[0, 0, 0, 0, 0, 0, 0], [.16, ...g], [.26, ...g.map((v, i) => i === 1 ? v + .01 : v), 'out'], [.34, ...g], [.84, ...g],
      [.9, ...g.map((v, i) => i === 3 ? v + .05 : v), 'out'], [1, 0, 0, 0, 0, 0, 0]],
    hand: [[0, 'fore', 0, 0, 0, 0, 0, 0], [.14, 'hatch', 0, .02, 0, -.2, 0, -.4], [.22, 'hatch', 0, .03, 0, -.2, 0, -.4], [.4, 'pouch', 0, .1, .1, .5, .3, -.6],
      [.5, 'pouch', 0, 0, 0, .5, .3, -.6], [.62, 'biomass', 0, -.025, 0, -.3, 0, -.5], [.74, 'biomass', 0, -.022, 0, -.3, 0, -.5], [.8, 'biomass', 0, -.01, 0, -.3, 0, -.5],
      [.86, 'hatch', 0, .015, 0, -.2, 0, -.4], [.9, 'hatch', 0, .005, 0, -.2, 0, -.4, 'out'], [1, 'fore', 0, 0, 0, 0, 0, 0]],
    hatch: [[0, 0], [.18, 0], [.26, open * 1.15, 'back'], [.32, open * .92], [.4, open], [.8, open], [.86, open * .2, 'in'], [.9, -open * .06, 'out'], [.95, 0]],
    bio: [[0, 0, 0, 0, 0, 0, 0], [.3, 0, 0, 0, 0, 0, 0], [.301, ...bioOff, .6, .4, 0, 'lin'], [.5, ...bioOff, .6, .4, 0], [.66, ...bioOff.map(v => v * .25), .2, .1, 0], [.76, ...bioOff.map(v => v * .05), 0, 0, 0], [.8, 0, 0, 0, 0, 0, 0, 'out']],
  }, [[.2, 'sfx', 'hatchopen'], [.22, 'drip', 'hatch'], [.3, 'husk'], [.45, 'sfx', 'pouch'], [.5, 'bio', 1], [.76, 'sfx', 'bioin'], [.8, 'seat'], [.8, 'drip', 'biomass'],
    [.88, 'sfx', 'hatchclose'], [.9, 'glow'], [.92, 'drip', 'hatch']])];
}

// post-shot cycling (no ammo change): pump racks, bolt throws, slide/bolt blowback is a separate kick envelope
function cycleSeq(arch) {
  if (arch === 'pump') return [seg(.62, {
    pump: [[0, 0], [.32, 0], [.55, .075, 'out'], [.82, 0, 'out']],
    gun: [[0, 0, 0, 0, 0, 0, 0], [.32, 0, 0, 0, 0, 0, 0], [.55, -.01, -.01, .025, .02, .04, -.12], [.82, 0, -.005, .01, .03, .02, -.06], [1, 0, 0, 0, 0, 0, 0]],
    hand: [[0, 'pump', 0, -.02, 0, 0, 0, 0], [1, 'pump', 0, -.02, 0, 0, 0, 0]],
  })];
  if (arch === 'bolt') return [seg(1.05, {
    gun: [[0, 0, 0, 0, 0, 0, 0], [.2, -.02, .02, .03, .06, .08, .35], [.8, -.02, .02, .03, .06, .08, .35], [1, 0, 0, 0, 0, 0, 0]],
    hand: [[0, 'fore', 0, 0, 0, 0, 0, 0], [.3, 'bolt', 0, 0, 0, -.45, -.2, -.5], [.75, 'bolt', 0, 0, 0, -.45, -.2, -.5], [1, 'fore', 0, 0, 0, 0, 0, 0]],
    boltRot: [[0, 0], [.32, 0], [.42, -1.05, 'out'], [.66, -1.05], [.74, 0, 'out']], bolt: [[0, 0], [.42, 0], [.52, .085, 'out'], [.58, .085], [.66, 0, 'out']],
  }, [[.5, 'eject']])];
  return null;
}

// ------------------------------------------------------------------ the controller (one per Weapons)
const SCAL = ['bolt', 'charge', 'slide', 'pump', 'boltRot', 'crane', 'spin', 'hatch', 'chargeUp'];
export class Reload {
  constructor(game) {
    this.g = game;
    this.drops = new Drops(game);
    this.P = this.blank();
    this.seq = null; this.cycle = null; this.kickT = 9;
    this.proxy = null; this.proxyArch = null;
    this.handPos = new THREE.Vector3(); this.handRot = [0, 0, 0];
    this.gunPose = [0, 0, 0, 0, 0, 0];
  }

  blank() {
    const P = { mag: new Array(6).fill(0), spare: new Array(6).fill(0), bio: new Array(6).fill(0), shell: new Array(6).fill(0), round: new Array(6).fill(0),
      loader: [0, 0, 0, 0], gun: [0, 0, 0, 0, 0, 0], hand: new THREE.Vector3(), handRot: [0, 0, 0], handW: 0,
      st: { mag: true, spare: false, rounds: true, bio: true, loader: false, shell: 0, round: 0 } };
    for (const k of SCAL) P[k] = 0;
    return P;
  }

  get active() { return !!this.seq; }

  rigFor(arch) {
    if (this.proxyArch !== arch) {
      const A = ARCHETYPES[arch];
      this.proxy = new GunRig(this.g.assets.clone(A.model), arch, this.g.assets);
      this.proxyArch = arch;
    }
    return this.proxy;
  }

  // start: w weapon, S stats, a ammo state; returns the total duration (s)
  start(w, S, a) {
    const A = ARCHETYPES[w.arch], arch = w.arch, empty = a.mag <= 0;
    this.cycle = null;
    let segs = null, loop = null;
    if (A.cls === 'kinetic' && ['rifle', 'carbine', 'dmr', 'ksmg', 'pistol'].includes(arch)) segs = magReload(arch, empty);
    else if (arch === 'revolver') segs = revolverReload();
    else if (arch === 'pump') { const n = Math.min(S.mag - a.mag, a.reserve); segs = pumpReload(n, empty); loop = { from: 1, to: n }; }
    else if (arch === 'bolt') { const n = Math.min(S.mag - a.mag, a.reserve); segs = boltReload(n); loop = { from: 1, to: n }; }
    else if (A.cls === 'horror') segs = bioReload(arch);
    if (!segs) { this.seq = { w, arch, energy: true, t: 0, dur: S.reload, segs: [], i: 0, a, S }; return S.reload; }
    // scale: tactical = the weapon's reload time, an empty reload adds the chambering; per-round guns use it per round
    let nominal = 0; for (const s of segs) nominal += s.dur;
    let k;
    if (loop) {
      const per = S.reload / (arch === 'pump' ? 7.2 : 6.5);      // seconds per nominal unit (pump 2.8 s ≈ 0.39 s a shell)
      k = per;
    } else k = S.reload / (segs.length > 1 ? segs[0].dur + segs[segs.length - 1].dur : segs[0].dur);
    for (const s of segs) s.dur *= k;
    const dur = segs.reduce((x, s) => x + s.dur, 0);
    this.seq = { w, arch, t: 0, dur, segs, i: 0, local: 0, a, S, loop, fired: new Set(), empty };
    this.P = this.blank();
    this.P.st.shell = 0;
    this.snap();
    this.g.audio.reloadSfx && this.g.audio.reloadSfx('start');
    return dur;
  }

  snap() { this.snapHand = this.handPos.clone(); this.snapRot = this.handRot.slice(); this.snapGun = this.gunPose.slice(); }

  // firing during a per-round reload: skip to the last segment (bolt closes / hand back to the pump)
  interrupt() {
    const q = this.seq; if (!q || !q.loop || q.i >= q.segs.length - 1 || q.i === 0) return false;
    q.i = q.segs.length - 1; q.local = 0; q.fired = new Set(); this.snap();
    this.P.st.shell = 0; this.P.st.round = 0;            // the one in hand goes back in the pouch
    q.dur = q.t + q.segs[q.i].dur;
    return true;
  }

  cancel() {
    this.seq = null; this.cycle = null;
    this.P = this.blank();
  }

  // a shot just fired: blowback envelope + pump/bolt cycling
  shot(w) {
    this.kickT = 0;
    const segs = cycleSeq(w.arch);
    if (segs) this.cycle = { arch: w.arch, t: 0, delay: w.arch === 'bolt' ? .3 : .22, segs, i: 0, local: 0, fired: new Set(), dur: segs[0].dur };
  }

  // advance; grant(n) adds rounds to the magazine. Returns true when the reload finished this step.
  update(dt, grant, ctx) {
    this.kickT += dt;
    const q = this.seq;
    if (!q) { this.updateCycle(dt, ctx); this.compose(null, ctx); return false; }
    q.t += dt;
    if (q.energy) {          // energy line: the old cell-swap dip
      const f = Math.min(1, q.t / q.dur), d = Math.sin(f * Math.PI);
      this.P.gun = [0, -d * .12, 0, d * .5, 0, d * .4]; this.P.handW = 0;
      if (q.t >= q.dur) { grant(-1); this.seq = null; this.P = this.blank(); return true; }
      return false;
    }
    q.local += dt;
    while (q.i < q.segs.length && q.local >= q.segs[q.i].dur) {
      this.fire(q, q.segs[q.i], 1.0001, grant, ctx);
      this.sample(q.segs[q.i], 1, ctx); this.snap();
      q.local -= q.segs[q.i].dur; q.i++; q.fired = new Set();
    }
    if (q.i >= q.segs.length) { this.seq = null; this.P = this.blank(); this.compose(null, ctx); return true; }
    const s = q.segs[q.i], t = q.local / s.dur;
    this.fire(q, s, t, grant, ctx);
    this.sample(s, t, ctx);
    this.compose(q, ctx);
    return false;
  }

  updateCycle(dt, ctx) {
    const c = this.cycle; if (!c) return;
    if (c.delay > 0) { c.delay -= dt; return; }
    c.local += dt;
    const s = c.segs[0];
    if (c.local >= s.dur) { this.cycle = null; this.P = this.blank(); return; }
    const t = c.local / s.dur;
    for (const e of s.ev) if (e[0] <= t && !c.fired.has(e)) { c.fired.add(e); if (e[1] === 'eject' && ctx && ctx.casing) ctx.casing(); }
    this.sample(s, t, ctx);
  }

  fire(q, s, t, grant, ctx) {
    const st = this.P.st;
    for (const e of s.ev) {
      if (e[0] > t || q.fired.has(e)) continue;
      q.fired.add(e);
      const [, name, arg] = e;
      switch (name) {
        case 'sfx': this.g.audio.reloadSfx && this.g.audio.reloadSfx(arg); break;
        case 'drop': if (arg === 'loader') { ctx && ctx.drop && ctx.drop('loader'); st.loader = false; } else { ctx && ctx.drop && ctx.drop('mag'); st.mag = false; } break;
        case 'spare': st.spare = true; break;
        case 'seat':
          if (st.spare) { st.spare = false; st.mag = true; this.P.mag.fill(0); }
          if (q.arch !== 'pump' && q.arch !== 'bolt') grant(-1);
          break;
        case 'grant': grant(arg || 1); break;
        case 'shell': st.shell = arg; break;
        case 'round': st.round = arg; break;
        case 'eject': st.rounds = false; ctx && ctx.drop && ctx.drop('casings'); break;
        case 'loader': st.loader = true; break;
        case 'release': st.rounds = true; break;
        case 'husk': st.bio = false; ctx && ctx.drop && ctx.drop('husk'); break;
        case 'bio': st.bio = true; break;
        case 'glow': ctx && ctx.glow && ctx.glow(); break;
        case 'drip': ctx && ctx.drip && ctx.drip(arg); break;
      }
    }
  }

  // sample a segment's channels into this.P (hand resolved against the proxy rig)
  sample(s, t, ctx) {
    const P = this.P, ch = s.ch, tmp = [0, 0, 0, 0, 0, 0, 0];
    if (ch.gun) sampleKeys(ch.gun, t, 6, P.gun);
    for (const k of ['mag', 'spare', 'bio', 'shell', 'round']) if (ch[k]) sampleKeys(ch[k], t, 6, P[k]);
    if (ch.loader) sampleKeys(ch.loader, t, 4, P.loader);
    for (const k of SCAL) if (ch[k]) P[k] = sampleKeys(ch[k], t, 1, tmp)[0];
    this.gunPose = P.gun.slice();
    if (ch.hand) this.resolveHand(ch.hand, t, ctx);
  }

  resolveHand(keys, t, ctx) {
    const P = this.P, rig = ctx && ctx.arch ? this.rigFor(ctx.arch) : null;
    if (!rig) return;
    rig.apply(P);
    let k = 0; while (k < keys.length - 1 && keys[k + 1][0] <= t) k++;
    const a = keys[k], b = keys[Math.min(k + 1, keys.length - 1)];
    const pa = this.anchorPos(rig, a, new THREE.Vector3()), pb = a === b ? pa : this.anchorPos(rig, b, new THREE.Vector3());
    let f = a === b || t <= a[0] ? 0 : Math.min(1, (t - a[0]) / Math.max(1e-6, b[0] - a[0]));
    const ez = EASE[typeof b[b.length - 1] === 'string' && b.length > 8 ? b[b.length - 1] : 's'] || EASE.s; f = ez(f);
    P.hand.lerpVectors(pa, pb, f);
    const ra = a[1] === 'cur' ? this.snapRot : a.slice(5, 8), rb = b[1] === 'cur' ? this.snapRot : b.slice(5, 8);
    for (let i = 0; i < 3; i++) P.handRot[i] = lerp(+ra[i] || 0, +rb[i] || 0, f);
    this.handPos.copy(P.hand); this.handRot = P.handRot.slice();
    // off-hand weight for the third-person IK: on while the hand is away from the foregrip
    P.handW = 1;
  }

  anchorPos(rig, key, out) {
    const name = key[1];
    if (name === 'cur') return out.copy(this.snapHand || rig.info.fore);
    if (name === 'fore') out.copy(rig.info.fore);
    else if (name === 'pouch') out.set(.1, -.42, -.22);
    else if (name === 'free') out.set(0, 0, 0);
    else rig.anchor(name, out);
    return out.add(_v.set(key[2] || 0, key[3] || 0, key[4] || 0));
  }

  // final pose: blowback for pistols / carriers, slide lock on an empty pistol
  compose(q, ctx) {
    const P = this.P;
    if (!q) {
      const k = this.kickT, env = k < .03 ? k / .03 : Math.max(0, 1 - (k - .03) / .07);
      const arch = ctx && ctx.arch, a = ctx && ctx.ammo;
      const lock = arch === 'pistol' && a && a.mag <= 0;
      if (arch === 'pistol') P.slide = lock ? .045 : .045 * env;
      else if (arch === 'carbine' || arch === 'ksmg' || arch === 'rifle' || arch === 'dmr') { if (!this.cycle) P.bolt = (arch === 'rifle' ? .06 : .04) * env; }
      if (!this.cycle && !this.seq) { P.handW = 0; }
    }
  }

  // third-person IK weight for the off hand: eases in and out at both ends of a reload / cycle
  handWeight() {
    const q = this.seq, c = this.cycle;
    if (q && !q.energy) return Math.max(0, Math.min(1, q.t / .15, (q.dur - q.t) / .15));
    if (c && c.delay <= 0) return Math.max(0, Math.min(1, c.local / .1, (c.dur - c.local) / .1));
    return 0;
  }

  // the pose rigs should show (null when nothing is displaced)
  pose() {
    const P = this.P;
    if (this.seq) return P;
    if (this.cycle && this.cycle.delay <= 0) return P;
    if (P.slide || P.bolt) return P;
    return null;
  }
}

// ------------------------------------------------------------------ physical drops (mags, casings, loaders, husks)
const MAX_DROPS = 14;
export class Drops {
  constructor(game) { this.g = game; this.list = []; }

  // obj: a posed Object3D whose world transform is taken; kind: sound + rest behaviour
  spawn(obj, kind, vel, spin = 6, life = 22, at = null) {
    const g = this.g; if (!g.scene || !obj) return null;
    obj.updateWorldMatrix(true, true);            // parents too: the viewmodel graph is otherwise only refreshed at render
    const c = obj.clone(true); c.visible = true;
    c.traverse(o => { o.visible = true; if (o.isMesh) { o.castShadow = true; o.frustumCulled = true; } });
    // pivot at the centre of the local box so it tumbles around its middle and rests on its side
    const box = localBox(obj), ctr = box.getCenter(new THREE.Vector3()), size = box.getSize(new THREE.Vector3());
    const root = new THREE.Group(); root.add(c); c.position.copy(ctr).negate(); c.quaternion.identity(); c.scale.set(1, 1, 1);
    if (at) { root.position.copy(at.pos); root.quaternion.copy(at.q); } else obj.matrixWorld.decompose(root.position, root.quaternion, root.scale);
    root.scale.set(1, 1, 1);
    root.position.add(ctr.clone().applyQuaternion(root.quaternion));
    g.scene.add(root);
    // the thinnest side ends up facing the floor
    const ax = size.x <= size.y && size.x <= size.z ? 0 : size.y <= size.z ? 1 : 2;
    const half = Math.max(.003, Math.min(size.x, size.y, size.z) / 2);
    const d = { root, v: vel.clone(), w: new THREE.Vector3((Math.random() - .5) * spin, (Math.random() - .5) * spin, (Math.random() - .5) * spin),
      life, kind, half, ax, rest: false, bounces: 0, t: 0 };
    if (this.list.length >= MAX_DROPS) this.remove(this.list[0]);
    this.list.push(d);
    return d;
  }

  remove(d) { d.root.removeFromParent(); const i = this.list.indexOf(d); if (i >= 0) this.list.splice(i, 1); }
  clear() { for (const d of this.list.slice()) this.remove(d); }

  update(dt) {
    const g = this.g, col = g.world && g.world.collision;
    for (const d of this.list.slice()) {
      d.t += dt; d.life -= dt;
      if (d.life <= 0) { this.remove(d); continue; }
      if (d.life < .6) d.root.scale.setScalar(Math.max(.01, d.life / .6));
      if (d.rest) continue;
      const r = d.root;
      d.v.y -= 9.81 * dt;
      r.position.addScaledVector(d.v, dt);
      if (d.w.lengthSq() > 1e-6) { const a = d.w.length(); r.quaternion.premultiply(_q.setFromAxisAngle(_v.copy(d.w).divideScalar(a), a * dt)); }
      const floor = col ? col.support(r.position.x, r.position.z, r.position.y + .05) : -1e9;
      const water = g.water && g.water.depthAt ? g.water.depthAt(r.position) : 0;
      if (water > .05 && d.kind !== 'husk') {   // sinks out of sight in water
        if (!d.wet) { d.wet = true; g.water.splash && g.water.splash(r.position.clone(), 'small'); }
        d.v.multiplyScalar(Math.pow(.05, dt)); d.v.y -= 1 * dt;
        if (r.position.y < floor + d.half) { d.rest = true; }
        continue;
      }
      if (r.position.y < floor + d.half) {
        r.position.y = floor + d.half;
        const vy = -d.v.y;
        if (vy > .6 && d.bounces < 4) {
          d.bounces++;
          const e = d.kind === 'husk' ? .05 : d.kind === 'casing' ? .42 : .28;
          d.v.y = vy * e; d.v.x *= .55; d.v.z *= .55;
          d.w.multiplyScalar(.5).add(_v.set((Math.random() - .5) * 4, 0, (Math.random() - .5) * 4).multiplyScalar(d.kind === 'casing' ? 3 : 1));
          g.audio.dropSfx && g.audio.dropSfx(d.kind, r.position, Math.min(1, vy / 5));
          if (d.kind === 'husk' && g.fx) g.fx.slime(r.position.clone(), new THREE.Vector3(0, 1, 0), .35, 0x9aff4a);
        } else {
          d.v.set(0, 0, 0); d.w.set(0, 0, 0);
          this.settle(d);
        }
      }
    }
  }

  // lie flat: rotate the thin axis to vertical (shortest arc) and stop
  settle(d) {
    const r = d.root;
    const local = d.ax === 0 ? _v.set(1, 0, 0) : d.ax === 1 ? _v.set(0, 1, 0) : _v.set(0, 0, 1);
    local.applyQuaternion(r.quaternion);
    const up = _v2.set(0, local.y >= 0 ? 1 : -1, 0);
    r.quaternion.premultiply(_q2.setFromUnitVectors(local.normalize(), up));
    d.rest = true;
  }
}
