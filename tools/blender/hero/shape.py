"""The anatomical target the subdivided cage is fitted to: a signed-distance body (negative inside) built from the
targets (targets.py) and the shared skeleton (skeleton.py). Evaluated on (|x|, y, z): the body is exactly symmetric and
every paired part is modelled once, on the left (+X).

Parts (each also callable on its own, so fit.py can project a vertex onto the part it belongs to first):
  torso   cross-section loft crotch -> neck base (hips, waist, ribcage, chest), pectorals / breasts, scapulae,
          glutes, trapezius, clavicles
  neck    loft with the sternocleidomastoids
  arm     deltoid, upper-arm loft (biceps / triceps), elbow, forearm loft, wrist
  hand    palm block, three phalanges per finger, the thumb with its thenar pad
  leg     thigh loft (quadriceps, hamstrings, adductors), patella and knee, calf loft, ankle bones
  foot    heel-to-ball loft with a flat sole and the arch, five toes
  head    headshape.py: cranium, face loft, brow, orbits with eyelid shells over the eyeballs, cheekbones, jaw and
          chin, nose (dorsum, tip, alae, nostrils), lips, ears
"""
import math
import numpy as np
from mathutils import Vector
import sdf
from sdf import smin, smax, ellipsoid, capsule, round_cone, round_box, Loft, sphere
import skeleton
from headshape import HeadShape

F32 = np.float32


def V(v):
    return np.asarray(tuple(v), F32)


def frame_rows(a, up):
    """rows (a, v, w): a along, v toward `up` (orthogonalised), w = a x v"""
    a = Vector(a).normalized()
    v = (Vector(up) - a * Vector(up).dot(a)).normalized()
    w = a.cross(v)
    return np.array([a, v, w], F32)


class Body(HeadShape):
    def __init__(self, T):
        self.T = T
        self.m = T["sex"] == "male"
        self._build()

    # ------------------------------------------------------------------ construction
    def _build(self):
        T, m = self.T, self.m
        lerp = lambda a, b, t: a + (b - a) * t
        H, Wst, U, C = T["hips"], T["waist"], T["underbust"], T["chest"]
        bz = T["biacromial"]
        z0, z1 = T["crotch_z"] - .035, T["neck_base_z"] + .012
        chest_hw = C["w"] / 2 if m else U["w"] / 2 * 1.04
        # the ribcage's depth: his chest measurement; hers is taken over the bust, so her ribcage follows the underbust
        # (the breasts are added in torso())
        rd = C["d"] if m else U["d"] * 1.06
        self.rib_d = rd
        # (z, half width, front, back, centre y (+ back))
        st = [
            (z0, H["w"] * .41, H["d"] * .40, H["d"] * .42, .012),
            (T["crotch_z"] + .02, H["w"] * .47, H["d"] * .45, H["d"] * .50, .014),
            (H["z"], H["w"] / 2, H["d"] * .47, H["d"] * .53, .015),
            (lerp(H["z"], Wst["z"], .5), lerp(H["w"], Wst["w"], .6) / 2, lerp(H["d"], Wst["d"], .5) * .5, lerp(H["d"], Wst["d"], .6) * .48, .008),
            (Wst["z"], Wst["w"] / 2, Wst["d"] * .5, Wst["d"] * .44, .0),         # the lumbar curve: the back comes in
            (lerp(Wst["z"], U["z"], .5), lerp(Wst["w"], U["w"], .5) / 2, lerp(Wst["d"], U["d"], .5) * .5, lerp(Wst["d"], U["d"], .5) * .5, -.002),
            (U["z"], U["w"] / 2, U["d"] * .5, U["d"] * .52, -.003),
            (C["z"], chest_hw, rd * (.47 if m else .48), rd * .5, .0),
            (T["shoulder_z"] - .105, bz * .43, rd * .44, rd * (.5 if m else .47), .006),
            (T["shoulder_z"] - .055, bz * .42, rd * .36, rd * .46, .014),
            (T["shoulder_z"] - .015, bz * .37, rd * .34, rd * .40, .022),
            (z1, T["neck_w"] * .66, T["neck_d"] * .52, T["neck_d"] * .58, .026),
        ]
        # back sections: rounder at the hips, flatter and fuller across the ribcage (the back is broad, not a tube)
        BACK_N = ([2.25, 2.25, 2.25, 2.3, 2.4, 2.5, 2.6, 2.6, 2.5, 2.4, 2.3, 2.0] if m else
                  [2.2, 2.2, 2.2, 2.2, 2.2, 2.2, 2.25, 2.25, 2.2, 2.2, 2.1, 2.0])
        zs = np.array([s[0] for s in st])
        tt = (zs - z0) / (z1 - z0)
        self.torso_loft = Loft((0, 0, z0), (0, 0, z1), dict(t=tt, rv_pos=[s[1] for s in st], rw_neg=[s[2] for s in st],
                                                           rw_pos=[s[3] for s in st], cw=[s[4] for s in st],
                                                           n=BACK_N, nb=np.full(len(st), 2.4)), v_axis=(1, 0, 0), cap=.6)
        # neck: a thick column tilted slightly forward going up, straight-sided from the trapezius into the base of the
        # skull (full width at the back and sides up to the occiput, as a real neck: no pinch under the skull); only
        # its front (the throat) is set back under the chin
        nb, nt = Vector((0, .028, T["neck_base_z"] - .03)), Vector((0, .012, T["chin_z"] + .090))
        nw, nd = T["neck_w"] / 2, T["neck_d"] / 2
        self.neck_loft = Loft(V(nb), V(nt), dict(t=[0, .5, 1], rv_pos=[nw * 1.0, nw * .92, nw * .84], rw_neg=[nd * .95, nd * .90, nd * .86],
                                                  rw_pos=[nd * 1.02, nd * .86, nd * .66], cw=[0, nd * .06, nd * .20]),
                                  v_axis=(1, 0, 0), cap=.5)      # (its top a D: widest toward the back, under the skull)
        self.arm = skeleton.arm(T)
        self.hand = skeleton.hand(T)
        self.leg = skeleton.leg(T)
        self.foot = skeleton.foot(T)
        A = self.arm
        a, d = A["a"], A["dorsal"]
        fw_ = (A["thumb"] - a * A["thumb"].dot(a)).normalized()       # anterior (biceps) side
        ur, fr = T["upper_arm_r"], T["forearm_r"]
        # upper arm: v = dorsal (lateral), w = a x dorsal; profile in that frame
        self.uarm = Loft(V(A["S"] + a * .02), V(A["E"]), dict(
            t=[0, .2, .5, .8, 1], rv_pos=[ur * 1.05, ur * 1.0, ur * .92, ur * .82, ur * .78],
            rv_neg=[ur * .95, ur * .90, ur * .86, ur * .78, ur * .74],
            rw_pos=[ur * .96, ur * .98, ur * 1.0, ur * .85, ur * .72], rw_neg=[ur * .96, ur * .98, ur * 1.0, ur * .85, ur * .72]),
            v_axis=tuple(d), cap=.8)
        self.farm = Loft(V(A["E"] - a * .01), V(A["W"]), dict(
            t=[0, .25, .55, .85, 1], rv_pos=[fr * 1.02, fr * 1.08, fr * .92, fr * .74, fr * .70],
            rv_neg=[fr * .98, fr * 1.0, fr * .85, fr * .70, fr * .68],
            rw_pos=[fr * .92, fr * .96, fr * .80, fr * .55, fr * .48], rw_neg=[fr * .92, fr * .94, fr * .78, fr * .54, fr * .48]),
            v_axis=tuple(fw_), cap=.8)
        self.arm_rows = frame_rows(a, d)
        L = self.leg
        th, ca = T["thigh"], T["calf"]
        kn = L["K"]
        self.thigh = Loft(V(L["H"] + Vector((-.006, 0, -.005))), V(kn), dict(
            # outer sweep high on the thigh (rv_pos = lateral), the inner thigh full at the top and slim above the knee
            t=[0, .15, .45, .75, 1], rv_pos=[th["w"] * (.50 if m else .56), th["w"] * (.54 if m else .57), th["w"] * .47, th["w"] * .33, th["w"] * .28],
            rv_neg=[th["w"] * .46, th["w"] * .45, th["w"] * .34, th["w"] * .26, th["w"] * .26],
            rw_neg=[th["d"] * .46, th["d"] * .49, th["d"] * .47, th["d"] * .37, th["d"] * .29],
            # (rw_pos is the front, as on the calf: the thigh's top front stays under the pelvis, no step at the hip)
            rw_pos=[th["d"] * .42, th["d"] * .47, th["d"] * .45, th["d"] * .36, th["d"] * .31]), v_axis=(1, 0, 0), cap=.8)
        ank = L["A"]
        self.calf = Loft(V(kn + Vector((0, 0, .015))), V(ank + Vector((0, 0, .02))), dict(
            # the calf's inner head fuller and lower than the outer; a slim ankle
            t=[0, .2, .38, .6, .85, 1], rv_pos=[ca["w"] * .46, ca["w"] * .51, ca["w"] * .44, ca["w"] * .33, ca["w"] * .26, ca["w"] * .27],
            rv_neg=[ca["w"] * .46, ca["w"] * .55, ca["w"] * .53, ca["w"] * .38, ca["w"] * .26, ca["w"] * .27],
            # (frame: u runs down the leg, so w = u x v points forward: rw_pos is the shin, rw_neg the calf muscle)
            rw_pos=[ca["d"] * .40, ca["d"] * .38, ca["d"] * .36, ca["d"] * .30, ca["d"] * .25, ca["d"] * .26],
            rw_neg=[ca["d"] * .44, ca["d"] * .62, ca["d"] * .58, ca["d"] * .40, ca["d"] * .27, ca["d"] * .27]), v_axis=(1, 0, 0), cap=.8)
        Fo = self.foot
        heel, ball = Fo["heel"], Fo["ball"]
        fw = Fo["width"]
        self.foot_loft = Loft(V(heel + Vector((0, .010, .0))), V(ball + Vector((-.004, -.022, 0))), dict(
            t=[0, .15, .4, .7, 1], rv_pos=[fw * .30, fw * .36, fw * .40, fw * .46, fw * .44],
            rv_neg=[fw * .30, fw * .34, fw * .36, fw * .46, fw * .48],
            rw_pos=[.040, .052, .048, .024, .012], rw_neg=[.030, .030, .028, .024, .020],
            cw=[.004, .016, .014, .000, -.006]), v_axis=(1, 0, 0), cap=.7)

    # ------------------------------------------------------------------ parts (left side; P already mirrored)
    def torso(self, P):
        T, m = self.T, self.m
        d = self.torso_loft(P)
        C = T["chest"]
        if m:
            # pectorals: broad, flat plates high on the chest
            # a broad, flat plate from the sternum out under the deltoid; its lower border is the pectoral line
            R = frame_rows((1, .28, .15), (0, 0, 1))
            d = smin(d, ellipsoid(P, (.074, -C["d"] * .36, C["z"] + .030), (.088, .066, .040), np.array([R[0], R[1], -R[2]], F32)), .045)
        else:
            d = smin(d, ellipsoid(P, (.062, -C["d"] * .34, C["z"] + .045), (.055, .020, .036)), .03)    # pectoral under the breast
            R = frame_rows((0, -1, -.12), (.25, 0, 1))
            # breast: a teardrop, the upper pole sloping down from the pectoral, the fuller lower pole
            Rb = frame_rows((0, -.35, -1), (1, 0, 0))                     # tilted: the upper pole slopes, the lower is full
            d = smin(d, ellipsoid(P, (.074, -C["d"] * .36, C["z"] - .002), (.040, .042, .038), Rb), .06)      # breast
        # glutes, scapulae, lats
        Hh = T["hips"]
        # glutes: low and behind the hips (with the lumbar curve above them, the side view's S)
        d = smin(d, ellipsoid(P, (.064, Hh["d"] * .37, Hh["z"] - .035), (.076 if m else .084, .060, .086)), .035)
        # latissimus dorsi: the broad back from under the arm down toward the waist (the back tapers, no shelf)
        U = T["underbust"]
        if m:                                                          # (her back stays smooth)
            d = smin(d, ellipsoid(P, (U["w"] * .36, self.rib_d * .28, U["z"] + .02), (.045, .036, .12)), .05)
        d = smin(d, ellipsoid(P, (.090 if m else .085, self.rib_d * (.405 if m else .38), T["shoulder_z"] - .115), (.048 if m else .036, .030 if m else .022, .068 if m else .052)), .045 if m else .05)     # scapula
        # trapezius: neck to acromion
        d = smin(d, round_cone(P, (.032, .040, T["neck_base_z"] + .002), (.150 * T["biacromial"] / .41, .020, T["shoulder_z"] - .010),
                               .034 if m else .022, .024 if m else .020), .04)
        # clavicles
        d = smin(d, capsule(P, (.018, -T["neck_d"] * .40, T["neck_base_z"] - .030), (.16 * T["biacromial"] / .41, -.025, T["shoulder_z"] - .010), .012), .035)
        return d

    def neck(self, P):
        d = self.neck_loft(P)
        if self.m:
            T = self.T
            d = smin(d, capsule(P, (.050, .020, T["chin_z"] + .07), (.018, -T["neck_d"] * .40, T["neck_base_z"] - .01), .0095), .03)
            d = smin(d, ellipsoid(P, (0, -T["neck_d"] * .27, T["chin_z"] - .036), (.007, .0045, .010)), .010)  # thyroid cartilage
        return d

    def arm_part(self, P):
        T, A = self.T, self.arm
        a, dor = A["a"], A["dorsal"]
        ur = T["upper_arm_r"]
        d = smin(self.uarm(P), self.farm(P), .035)
        # deltoid: wraps the shoulder from the clavicle to a third down the arm
        # (a long teardrop over the shoulder, not a ball: its centre a little down the arm, blended wide)
        c = A["S"] + a * .055 + dor * .010
        d = smin(d, ellipsoid(P, V(c), (.095, ur * .98, ur * 1.02), self.arm_rows), .04)
        # biceps / triceps bellies
        fwd = (A["thumb"] - a * A["thumb"].dot(a)).normalized()
        d = smin(d, ellipsoid(P, V(A["S"] + a * .16 + fwd * ur * .45), (.075, ur * .55, ur * .6), self.arm_rows), .025)
        d = smin(d, ellipsoid(P, V(A["S"] + a * .14 - fwd * ur * .55), (.085, ur * .6, ur * .6), self.arm_rows), .025)
        # elbow (olecranon) and the forearm extensors
        d = smin(d, sphere(P, V(A["E"] - fwd * ur * .50), .016), .02)
        # the forearm's muscle mass just below the elbow (flexors / extensors / brachioradialis): no doll joint
        fr = T["forearm_r"]
        d = smin(d, ellipsoid(P, V(A["E"] + a * .060), (.070, fr * .98, fr * .92), self.arm_rows), .03)
        return d

    def hand_part(self, P):
        T, Hd = self.T, self.hand
        A = Hd["arm"]
        a, dor, th = A["a"], A["dorsal"], A["thumb"]
        Pm = T["palm"]
        R = frame_rows(a, dor)
        c = A["W"] + a * (Pm["l"] * .50)
        d = round_box(P, V(c), (Pm["l"] * .50, Pm["t"] / 2 * .92, Pm["w"] / 2 * .96), .012, np.array([R[0], R[1], R[2]], F32))
        # thenar / hypothenar pads on the palm side
        d = smin(d, ellipsoid(P, V(A["W"] + a * (Pm["l"] * .35) + th * (Pm["w"] * .28) - dor * (Pm["t"] * .30)), (.032, .014, .02), R), .012)
        d = smin(d, ellipsoid(P, V(A["W"] + a * (Pm["l"] * .40) - th * (Pm["w"] * .33) - dor * (Pm["t"] * .25)), (.034, .012, .015), R), .012)
        # wrist joint
        d = smin(d, ellipsoid(P, V(A["W"] + a * .005), (.022, T["wrist"]["d"] / 2 * 1.02, T["wrist"]["w"] / 2 * 1.02), R), .015)
        for f, ch in Hd["fingers"].items():
            J = ch["joints"]
            w = ch["width"] / 2
            for i in range(3):
                r0 = w * (1.0, .92, .84)[i]
                r1 = w * (.92, .84, .74)[i]
                d = smin(d, round_cone(P, V(J[i]), V(J[i + 1]), r0, r1), .006)
        tc = Hd["thumb"]
        J = tc["joints"]
        w = tc["width"] / 2
        for i in range(3):
            d = smin(d, round_cone(P, V(J[i]), V(J[i + 1]), w * (1.25, 1.0, .9)[i], w * (1.0, .9, .78)[i]), .008)
        return d

    def leg_part(self, P):
        T, L = self.T, self.leg
        d = smin(self.thigh(P), self.calf(P), .03)
        K = L["K"]
        # knee: condyles and the patella in front, the hollow behind
        d = smin(d, ellipsoid(P, V(K + Vector((0, -.004, .005))), (.046, .042, .040)), .025)
        d = smin(d, ellipsoid(P, V(K + Vector((0, -.046, .018))), (.026, .014, .030)), .012)
        # vastus medialis (teardrop above the knee, inside)
        vk = 1.0 if self.m else .75
        d = smin(d, ellipsoid(P, V(K + Vector((-.026, -.022, .070))), (.025 * vk, .021 * vk, .042 * vk)), .025)
        # ankle bones
        A = L["A"]
        d = smin(d, sphere(P, V(A + Vector((.026, .004, .002))), .016), .012)
        d = smin(d, sphere(P, V(A + Vector((-.022, -.004, .012))), .016), .012)
        return d

    def foot_part(self, P):
        F = self.foot
        d = self.foot_loft(P)
        d = smin(d, sphere(P, V(F["heel"] + Vector((0, .006, .012))), .034), .02)            # heel
        d = smin(d, ellipsoid(P, V(F["ankle"] + Vector((0, -.012, -.030))), (.034, .045, .035)), .025)
        d = smin(d, self.toes(P, sole=False), .003)
        # flat sole: cut everything below the floor
        d = np.maximum(d, -P[:, 2] + .0)
        return d

    def toes(self, P, sole=True):
        """the five toes alone (fit.py projects the toes' own vertices onto these, not onto the foot's front)"""
        d = None
        for t in self.foot["toes"]:
            r = t["width"] / 2
            # from the ball of the foot (the joint sits up in the forefoot) sloping down to the tip on the floor
            b = t["base"] + Vector((0, .012, skeleton.TOE_ROOT_Z - t["base"].z))
            tip = t["base"] + t["dir"] * t["len"] + Vector((0, 0, r * .80 - t["base"].z))
            e = round_cone(P, V(b), V(tip), r * .90, r * .76)
            d = e if d is None else np.minimum(d, e)
        return np.maximum(d, -P[:, 2]) if sole else d

    # ------------------------------------------------------------------ whole body
    PARTS = ("torso", "neck", "arm", "hand", "leg", "foot", "head")

    def part(self, name, P):
        P = np.asarray(P, F32).copy()
        P[:, 0] = np.abs(P[:, 0])
        return {"torso": self.torso, "neck": self.neck, "arm": self.arm_part, "hand": self.hand_part, "leg": self.leg_part,
                "foot": self.foot_part, "toe": self.toes, "head": self.head_part, "ear": self.ear,
                "skull": lambda Q: self.head_part(Q, ear=False)}[name](P)

    def __call__(self, P):
        P = np.asarray(P, F32).copy()
        P[:, 0] = np.abs(P[:, 0])
        d = self.torso(P)
        d = smin(d, self.neck(P), .045)
        d = smin(d, self.head_part(P), .022)                 # tight enough to keep the jawline edge
        d = smin(d, self.arm_part(P), .045)
        d = smin(d, self.hand_part(P), .015)
        d = smin(d, self.leg_part(P), .05)
        d = smin(d, self.foot_part(P), .02)
        return d
