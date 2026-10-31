// Verlet ragdoll for the shared 20-bone rig: particles at every joint, bone-length and torso-shape constraints, gravity,
// ground contact with friction. Bones are re-aimed every frame toward their child particle, so any skinned character
// (player, enemies, aliens, pedestrians) falls physically when it dies instead of playing a canned clip.
import * as THREE from 'three';

const _a = new THREE.Vector3(), _b = new THREE.Vector3(), _d = new THREE.Vector3(), _cur = new THREE.Vector3();
const _q = new THREE.Quaternion(), _qp = new THREE.Quaternion(), _m = new THREE.Matrix4(), _s = new THREE.Vector3();
const UP = new THREE.Vector3(0, 1, 0);

// leaf bones: estimated tail length (metres at scale 1) along the bone's +Y
const LEAF = { head: .2, handL: .1, handR: .1, footL: .14, footR: .14 };
// [bone, from particle, to particle]
const SEGS = [['hips', 'hips', 'spine'], ['spine', 'spine', 'chest'], ['chest', 'chest', 'neck'], ['neck', 'neck', 'head'], ['head', 'head', 'headTip'],
  ['upperarmL', 'upperarmL', 'forearmL'], ['forearmL', 'forearmL', 'handL'], ['handL', 'handL', 'handLTip'],
  ['upperarmR', 'upperarmR', 'forearmR'], ['forearmR', 'forearmR', 'handR'], ['handR', 'handR', 'handRTip'],
  ['thighL', 'thighL', 'shinL'], ['shinL', 'shinL', 'footL'], ['footL', 'footL', 'footLTip'],
  ['thighR', 'thighR', 'shinR'], ['shinR', 'shinR', 'footR'], ['footR', 'footR', 'footRTip']];
// extra links that keep the pelvis, ribcage and shoulders in shape (stiffness 0..1)
const SHAPE = [['hips', 'thighL', 1], ['hips', 'thighR', 1], ['thighL', 'thighR', 1], ['spine', 'thighL', 1], ['spine', 'thighR', 1],
  ['chest', 'upperarmL', 1], ['chest', 'upperarmR', 1], ['upperarmL', 'upperarmR', 1], ['neck', 'upperarmL', 1], ['neck', 'upperarmR', 1],
  ['hips', 'chest', .5], ['spine', 'neck', .6], ['head', 'chest', .7], ['upperarmL', 'thighL', .25], ['upperarmR', 'thighR', .25]];
// joints that must not fold flat (min distance as a fraction of the rest distance)
const MINS = [['thighL', 'footL', .55], ['thighR', 'footR', .55], ['upperarmL', 'handL', .45], ['upperarmR', 'handR', .45]];

export class Ragdoll {
  constructor(avatar, impulse, ground) {
    this.av = avatar; this.ground = ground; this.t = 0; this.asleep = false;
    const B = avatar.bones;
    this.bones = {};
    for (const [n] of SEGS) if (B[n]) this.bones[n] = B[n];
    this.ok = !!(this.bones.hips && this.bones.chest && this.bones.head);
    if (!this.ok) return;
    avatar.root.updateMatrixWorld(true);
    avatar.root.getWorldScale(_s); this.scale = _s.y;
    const P = this.p = {}, prev = this.prev = {};
    for (const n of Object.keys(this.bones)) P[n] = this.bones[n].getWorldPosition(new THREE.Vector3());
    for (const [n, L] of Object.entries(LEAF)) {
      const b = this.bones[n]; if (!b) continue;
      b.getWorldQuaternion(_q);
      P[n + 'Tip'] = P[n].clone().add(UP.clone().applyQuaternion(_q).multiplyScalar(L * this.scale));
    }
    // rest lengths
    this.links = [];
    const link = (a, b, k = 1, min = 0) => { if (P[a] && P[b]) this.links.push([a, b, P[a].distanceTo(P[b]), k, min]); };
    for (const [, a, b] of SEGS) link(a, b);
    for (const [a, b, k] of SHAPE) link(a, b, k);
    for (const [a, b, f] of MINS) if (P[a] && P[b]) this.links.push([a, b, P[a].distanceTo(P[b]), 0, f]);
    // initial motion: the hit pushes the upper body harder than the legs
    const imp = impulse || new THREE.Vector3();
    for (const n of Object.keys(P)) {
      const upper = /chest|neck|head|arm|hand/.test(n) ? 1 : /spine|hips/.test(n) ? .7 : .35;
      prev[n] = P[n].clone().addScaledVector(imp, -upper / 60).add(_d.set((Math.random() - .5) * .01, 0, (Math.random() - .5) * .01));
    }
  }

  step(dt) {
    if (!this.ok || this.asleep) return;
    this.t += dt;
    const P = this.p, prev = this.prev, h = 1 / 60;
    const n = Math.min(3, Math.max(1, Math.round(dt / h)));
    let energy = 0;
    for (let s = 0; s < n; s++) {
      for (const k in P) {
        const x = P[k], o = prev[k];
        const vx = (x.x - o.x) * .985, vy = (x.y - o.y) * .985, vz = (x.z - o.z) * .985;
        o.copy(x);
        x.x += vx; x.y += vy - 9.8 * h * h; x.z += vz;
        energy += vx * vx + vy * vy + vz * vz;
      }
      for (let it = 0; it < 8; it++) {
        for (const [a, b, L, k, min] of this.links) {
          const A = P[a], Bp = P[b];
          _d.subVectors(Bp, A); const d = _d.length() || 1e-6;
          let target = L;
          if (k === 0) { if (d >= L * min) continue; target = L * min; }
          const diff = (d - target) / d * .5 * (k || 1);
          A.addScaledVector(_d, diff); Bp.addScaledVector(_d, -diff);
        }
        // ground contact with friction
        for (const kk in P) {
          const x = P[kk], g = this.ground(x.x, x.z) + .05 * this.scale;
          if (x.y < g) { x.y = g; const o = prev[kk]; o.x += (x.x - o.x) * .6; o.z += (x.z - o.z) * .6; }
        }
      }
    }
    if (this.t > 1.2 && energy / n < 1e-6) this.asleep = true;
    if (this.t > 6) this.asleep = true;
    this.apply();
  }

  // aim every bone at its child particle (parents first), and move the pelvis
  apply() {
    const P = this.p, B = this.bones;
    const hips = B.hips;
    if (hips.parent) { hips.parent.updateMatrixWorld(true); _m.copy(hips.parent.matrixWorld).invert(); hips.position.copy(P.hips).applyMatrix4(_m); }
    for (const [n, a, b] of SEGS) {
      const bone = B[n]; if (!bone || !P[a] || !P[b]) continue;
      bone.updateMatrixWorld(true);
      bone.getWorldQuaternion(_q);
      _cur.copy(UP).applyQuaternion(_q);
      _d.subVectors(P[b], P[a]); if (_d.lengthSq() < 1e-8) continue; _d.normalize();
      const delta = _qp.setFromUnitVectors(_cur, _d);
      _q.premultiply(delta);
      bone.parent.getWorldQuaternion(_qp);
      bone.quaternion.copy(_qp.invert().multiply(_q));
      bone.updateMatrixWorld(true);
    }
  }
}
