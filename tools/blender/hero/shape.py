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
  head    cranium, brow, eye sockets with eyelid shells over the eyeballs, cheekbones, maxilla, nose (dorsum, tip,
          alae, nostrils), lips, jaw and chin, ears
"""
import math
import numpy as np
from mathutils import Vector
import sdf
from sdf import smin, smax, ellipsoid, capsule, round_cone, round_box, Loft, sphere
import skeleton

F32 = np.float32


def V(v):
    return np.asarray(tuple(v), F32)


def frame_rows(a, up):
    """rows (a, v, w): a along, v toward `up` (orthogonalised), w = a x v"""
    a = Vector(a).normalized()
    v = (Vector(up) - a * Vector(up).dot(a)).normalized()
    w = a.cross(v)
    return np.array([a, v, w], F32)


class Body:
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
        # (z, half width, front, back, centre y (+ back))
        st = [
            (z0, H["w"] * .41, H["d"] * .40, H["d"] * .42, .012),
            (T["crotch_z"] + .02, H["w"] * .47, H["d"] * .45, H["d"] * .50, .014),
            (H["z"], H["w"] / 2, H["d"] * .47, H["d"] * .53, .015),
            (lerp(H["z"], Wst["z"], .5), lerp(H["w"], Wst["w"], .6) / 2, lerp(H["d"], Wst["d"], .5) * .5, lerp(H["d"], Wst["d"], .6) * .48, .008),
            (Wst["z"], Wst["w"] / 2, Wst["d"] * .5, Wst["d"] * .48, .0),
            (lerp(Wst["z"], U["z"], .5), lerp(Wst["w"], U["w"], .5) / 2, lerp(Wst["d"], U["d"], .5) * .5, lerp(Wst["d"], U["d"], .5) * .5, -.002),
            (U["z"], U["w"] / 2, U["d"] * .5, U["d"] * .5, -.003),
            (C["z"], chest_hw, C["d"] * (.47 if m else .45), C["d"] * .5, .0),
            (T["shoulder_z"] - .105, bz * .43, C["d"] * .44, C["d"] * .5, .006),
            (T["shoulder_z"] - .055, bz * .42, C["d"] * .36, C["d"] * .46, .014),
            (T["shoulder_z"] - .015, bz * .37, C["d"] * .34, C["d"] * .40, .022),
            (z1, T["neck_w"] * .66, T["neck_d"] * .52, T["neck_d"] * .58, .026),
        ]
        zs = np.array([s[0] for s in st])
        tt = (zs - z0) / (z1 - z0)
        self.torso_loft = Loft((0, 0, z0), (0, 0, z1), dict(t=tt, rv_pos=[s[1] for s in st], rw_neg=[s[2] for s in st],
                                                           rw_pos=[s[3] for s in st], cw=[s[4] for s in st],
                                                           n=np.full(len(st), 2.25), nb=np.full(len(st), 2.4)), v_axis=(1, 0, 0), cap=.6)
        # neck: tilted slightly forward going up
        nb, nt = Vector((0, .028, T["neck_base_z"] - .03)), Vector((0, .010, T["chin_z"] + .085))
        nw, nd = T["neck_w"] / 2, T["neck_d"] / 2
        self.neck_loft = Loft(V(nb), V(nt), dict(t=[0, .5, 1], rv_pos=[nw * 1.12, nw, nw * .98], rw_neg=[nd * .95, nd * .9, nd * .85],
                                                  rw_pos=[nd * 1.05, nd * 1.02, nd]), v_axis=(1, 0, 0), cap=.8)
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
        self.thigh = Loft(V(L["H"] + Vector((-.006, 0, .02))), V(kn), dict(
            t=[0, .15, .45, .75, 1], rv_pos=[th["w"] * .50, th["w"] * .50, th["w"] * .46, th["w"] * .37, th["w"] * .30],
            rv_neg=[th["w"] * .44, th["w"] * .46, th["w"] * .40, th["w"] * .32, th["w"] * .29],
            rw_neg=[th["d"] * .46, th["d"] * .49, th["d"] * .47, th["d"] * .37, th["d"] * .29],
            rw_pos=[th["d"] * .50, th["d"] * .50, th["d"] * .45, th["d"] * .36, th["d"] * .31]), v_axis=(1, 0, 0), cap=.8)
        ank = L["A"]
        self.calf = Loft(V(kn + Vector((0, 0, .015))), V(ank + Vector((0, 0, .02))), dict(
            t=[0, .2, .38, .6, .85, 1], rv_pos=[ca["w"] * .46, ca["w"] * .50, ca["w"] * .47, ca["w"] * .37, ca["w"] * .29, ca["w"] * .30],
            rv_neg=[ca["w"] * .46, ca["w"] * .52, ca["w"] * .49, ca["w"] * .37, ca["w"] * .29, ca["w"] * .30],
            rw_neg=[ca["d"] * .40, ca["d"] * .38, ca["d"] * .36, ca["d"] * .30, ca["d"] * .25, ca["d"] * .26],
            rw_pos=[ca["d"] * .44, ca["d"] * .62, ca["d"] * .58, ca["d"] * .40, ca["d"] * .27, ca["d"] * .27]), v_axis=(1, 0, 0), cap=.8)
        Fo = self.foot
        heel, ball = Fo["heel"], Fo["ball"]
        fw = Fo["width"]
        self.foot_loft = Loft(V(heel + Vector((0, .010, .0))), V(ball + Vector((-.004, -.035, 0))), dict(
            t=[0, .15, .4, .7, 1], rv_pos=[fw * .30, fw * .36, fw * .40, fw * .46, fw * .44],
            rv_neg=[fw * .30, fw * .34, fw * .36, fw * .46, fw * .48],
            rw_pos=[.040, .052, .052, .030, .020], rw_neg=[.030, .030, .028, .024, .018],
            cw=[.004, .016, .016, .006, .002]), v_axis=(1, 0, 0), cap=.7)

    # ------------------------------------------------------------------ parts (left side; P already mirrored)
    def torso(self, P):
        T, m = self.T, self.m
        d = self.torso_loft(P)
        C = T["chest"]
        if m:
            # pectorals: broad, flat plates high on the chest
            d = smin(d, ellipsoid(P, (.070, -C["d"] * .39, C["z"] + .036), (.085, .026, .060)), .04)
        else:
            d = smin(d, ellipsoid(P, (.064, -C["d"] * .36, C["z"] + .045), (.06, .028, .04)), .03)     # pectoral under the breast
            R = frame_rows((0, -1, -.12), (.25, 0, 1))
            d = smin(d, ellipsoid(P, (.082, -C["d"] * .43, C["z"] - .004), (.058, .052, .062), None), .03)   # breast
        # glutes, scapulae, lats
        Hh = T["hips"]
        d = smin(d, ellipsoid(P, (.066, Hh["d"] * .34, Hh["z"] - .012), (.078 if m else .088, .058, .092)), .035)
        d = smin(d, ellipsoid(P, (.095, C["d"] * .40, T["shoulder_z"] - .110), (.042, .014, .058)), .025)    # scapula
        # trapezius: neck to acromion
        d = smin(d, round_cone(P, (.035, .036, T["neck_base_z"] + .035), (.150 * T["biacromial"] / .41, .020, T["shoulder_z"] - .008),
                               .048 if m else .036, .026), .045)
        # clavicles
        d = smin(d, capsule(P, (.018, -T["neck_d"] * .40, T["neck_base_z"] - .030), (.16 * T["biacromial"] / .41, -.025, T["shoulder_z"] - .010), .012), .035)
        return d

    def neck(self, P):
        d = self.neck_loft(P)
        if self.m:
            T = self.T
            d = smin(d, capsule(P, (.050, .020, T["chin_z"] + .07), (.016, -T["neck_d"] * .42, T["neck_base_z"] - .01), .011), .015)
            d = smin(d, ellipsoid(P, (0, -T["neck_d"] * .30, T["chin_z"] - .032), (.008, .006, .011)), .010)   # thyroid cartilage
        return d

    def arm_part(self, P):
        T, A = self.T, self.arm
        a, dor = A["a"], A["dorsal"]
        ur = T["upper_arm_r"]
        d = smin(self.uarm(P), self.farm(P), .02)
        # deltoid: wraps the shoulder from the clavicle to a third down the arm
        c = A["S"] + a * .035 + dor * .012
        d = smin(d, ellipsoid(P, V(c), (.085, ur * 1.08, ur * 1.12), self.arm_rows), .03)
        # biceps / triceps bellies
        fwd = (A["thumb"] - a * A["thumb"].dot(a)).normalized()
        d = smin(d, ellipsoid(P, V(A["S"] + a * .16 + fwd * ur * .45), (.075, ur * .55, ur * .6), self.arm_rows), .025)
        d = smin(d, ellipsoid(P, V(A["S"] + a * .14 - fwd * ur * .55), (.085, ur * .6, ur * .6), self.arm_rows), .025)
        # elbow (olecranon) and the forearm extensors
        d = smin(d, sphere(P, V(A["E"] - fwd * ur * .55), .022), .02)
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
        d = smin(d, ellipsoid(P, V(K + Vector((0, -.004, .005))), (.052, .046, .045)), .02)
        d = smin(d, ellipsoid(P, V(K + Vector((0, -.046, .018))), (.026, .014, .030)), .012)
        # vastus medialis (teardrop above the knee, inside)
        d = smin(d, ellipsoid(P, V(K + Vector((-.030, -.026, .075))), (.032, .028, .05)), .02)
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
        for t in F["toes"]:
            b = t["base"] + Vector((0, .012, 0))
            tip = t["base"] + t["dir"] * t["len"]
            r = t["width"] / 2
            d = smin(d, round_cone(P, V(b + Vector((0, 0, r * .9))), V(tip + Vector((0, 0, r * .75))), r * .95, r * .78), .005)
        # flat sole: cut everything below the floor
        d = np.maximum(d, -P[:, 2] + .0)
        return d

    # ------------------------------------------------------------------ head
    # landmark heights above the menton in head heights: ours (adult norms, Farkas) and the measured reference's
    LM_OURS = dict(pog=.075, sto=.217, sn=.313, prn=.372, n=.552, g=.595)
    LM_REF = dict(pog=.091, sto=.273, sn=.343, prn=.392, n=.574, g=.649)

    def _load_head(self):
        import json, os
        hm = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "head_measure.json")))
        G = np.array([[np.nan if v is None else v for v in row] for row in hm["r"]], float)
        th, ph = np.array(hm["theta"], float), np.array(hm["phi"], float)
        # below the jaw the reference rays reach its neck / shoulders: our body has its own neck, so those rows take
        # the jaw-line row's radius (the head is cut along the jaw line anyway)
        for i, p in enumerate(ph):
            if p <= -40:
                for j in range(len(th)):
                    if np.isnan(G[i, j]) or G[i, j] > .75 or th[j] >= 60:
                        G[i, j] = np.nan
        # fill the gaps (ears, neck) across each row, then down the columns
        for i in range(len(ph)):
            row = G[i]
            ok = ~np.isnan(row)
            if ok.sum() >= 2:
                G[i] = np.interp(th, th[ok], row[ok])
        for j in range(len(th)):
            col = G[:, j]
            ok = ~np.isnan(col)
            G[:, j] = np.interp(ph, ph[ok], col[ok])
        self._hm, self._G, self._th, self._ph = hm, G, th, ph

    @staticmethod
    def _cr(t):
        """Catmull-Rom weights for the 4 samples around t"""
        t2, t3 = t * t, t * t * t
        return (-.5 * t3 + t2 - .5 * t, 1.5 * t3 - 2.5 * t2 + 1, -1.5 * t3 + 2 * t2 + .5 * t, .5 * t3 - .5 * t2)

    def _radius(self, th, ph):
        G, gt, gp = self._G, self._th, self._ph
        ft = np.clip((th - gt[0]) / (gt[1] - gt[0]), 0, len(gt) - 1.0001)
        fp = np.clip((ph - gp[0]) / (gp[1] - gp[0]), 0, len(gp) - 1.0001)
        i, j = np.floor(fp).astype(int), np.floor(ft).astype(int)
        wp, wt = self._cr(fp - i), self._cr(ft - j)
        out = np.zeros(len(th))
        for a in range(4):
            ii = np.clip(i + a - 1, 0, len(gp) - 1)
            row = np.zeros(len(th))
            for b in range(4):
                jj = np.abs(j + b - 1)                       # mirror across theta = 0 (the midline)
                jj = np.where(jj > len(gt) - 1, 2 * (len(gt) - 1) - jj, jj)
                row += wt[b] * G[ii, jj]
            out += wp[a] * row
        return out

    def head_base(self, P):
        """the head's overall shape from the measured radial map, scaled to our breadth / length / height and warped
        to our landmark heights; signed distance (approx.), negative inside"""
        T = self.T
        if not hasattr(self, "_G"):
            self._load_head()
        hm = self._hm
        h, chin = T["head_h"], T["chin_z"]
        sx = (T["head_breadth"] / h) / hm["breadth"]
        sy = (T["head_length"] / h) / hm["length"]
        zf = (P[:, 2] - chin) / h
        lo = [-.5, 0.0] + [self.LM_OURS[k] for k in ("pog", "sto", "sn", "prn", "n", "g")] + [1.0, 1.5]
        lr = [-.5, 0.0] + [self.LM_REF[k] for k in ("pog", "sto", "sn", "prn", "n", "g")] + [1.0, 1.5]
        zr = np.interp(zf, lo, lr) - hm["centre_above_menton"]
        cy = .008 * h / .23 - .006 * h / .242
        qx = np.abs(P[:, 0]) / h / sx
        qy = (P[:, 1] - cy) / h / sy
        rho = np.sqrt(qx * qx + qy * qy + zr * zr) + 1e-9
        th = np.degrees(np.arctan2(qx, -qy))
        ph = np.degrees(np.arcsin(np.clip(zr / rho, -1, 1)))
        return ((rho - self._radius(th, ph)) * h).astype(F32)

    def head_geometry(self):
        T, m = self.T, self.m
        h = T["head_h"]
        hs = h / .23
        chin = T["chin_z"]
        L = {k: chin + v * h for k, v in self.LM_OURS.items()}

        def front(z, x=0.0):
            """the base head's front surface y at height z, |x| = x (bisection along -y)"""
            lo_, hi_ = -.25, .05
            for _ in range(40):
                mid = (lo_ + hi_) / 2
                inside = self.head_base(np.array([[x, mid, z]], F32))[0] < 0
                if inside:
                    hi_ = mid
                else:
                    lo_ = mid
            return (lo_ + hi_) / 2
        if not hasattr(self, "_g"):
            ez = T["eye_z"]
            ex = T["interpupil"] / 2
            self._g = dict(
                hs=hs, ez=ez, h=h, chin=chin,
                eye_c=Vector((ex, front(ez, ex) + .0118, ez)), eye_r=.0122,
                nasion=Vector((0, front(L["n"]), L["n"])),
                subnasale=Vector((0, front(L["sn"] - .004), L["sn"])),
                pronasale=Vector((0, front(L["prn"]) - .006, L["prn"])),
                stomion=Vector((0, front(L["sto"]), L["sto"])),
                mouth_w=(.052 if m else .048) * hs,
                pogonion=Vector((0, front(L["pog"]), L["pog"])),
                tragion=Vector((.072 * hs, .008 * hs, chin + .51 * h)),
                vertex_z=chin + h,
            )
        return self._g

    def head_part(self, P):
        T, m = self.T, self.m
        g = self.head_geometry()
        hs, h, chin = g["hs"], g["h"], g["chin"]
        d = self.head_base(P)
        # cut under the jaw: a line rising from just under the chin toward the back of the jaw
        jaw = (chin + .004 + np.maximum(0, P[:, 1] - (g["pogonion"].y + .03)) * .40 - P[:, 2]).astype(F32)
        d = smax(d, jaw, .012)
        # lips (fuller on her), on the mouth
        st, mw = g["stomion"], g["mouth_w"]
        if not hasattr(self, "_lips"):
            full = 1.0 if m else 1.2
            tt = [0, .1, .25, .42, .5, .58, .75, .9, 1]
            yo = .0040
            up = Loft(V(st + Vector((-mw / 2, yo, .0006))), V(st + Vector((mw / 2, yo, .0006))), dict(
                t=tt, rv_pos=[.0008, .0028, .0050, .0058, .0052, .0058, .0050, .0028, .0008],
                rv_neg=[.0006, .0012, .0018, .0020, .0020, .0020, .0018, .0012, .0006],
                rw_pos=[f * full * 1.25 for f in (.0010, .0026, .0046, .0056, .0058, .0056, .0046, .0026, .0010)],
                rw_neg=[.004] * 9), v_axis=(0, 0, 1), cap=.9)
            lo = Loft(V(st + Vector((-mw * .46, yo + .001, -.0008))), V(st + Vector((mw * .46, yo + .001, -.0008))), dict(
                t=tt, rv_pos=[.0006, .0012, .0016, .0018, .0018, .0018, .0016, .0012, .0006],
                rv_neg=[f * full for f in (.0008, .0030, .0052, .0062, .0064, .0062, .0052, .0030, .0008)],
                rw_pos=[f * full * 1.25 for f in (.0010, .0028, .0048, .0056, .0058, .0056, .0048, .0028, .0010)],
                rw_neg=[.004] * 9), v_axis=(0, 0, 1), cap=.9)
            self._lips = (up, lo)
        d = smin(d, self._lips[0](P), .003)
        d = smin(d, self._lips[1](P), .003)
        # the eye: lids as a thin shell over the eyeball
        ec, er = g["eye_c"], g["eye_r"]
        d = smin(d, sphere(P, V(ec), er + .0014), .005)
        # nose: dorsum, tip, wings on the measured nose; nostrils hollowed
        tip, sub = g["pronasale"], g["subnasale"]
        nk = 1.0 if m else .86
        d = smin(d, round_cone(P, V(g["nasion"] + Vector((0, .005, 0))), V(tip + Vector((0, .008, .005))), .0060 * nk, .0076 * nk), .010)
        d = smin(d, ellipsoid(P, V(tip + Vector((0, .0050, -.001))), (.0095 * nk, .0078, .0082)), .006)
        d = smin(d, ellipsoid(P, V(sub + Vector((.0138 * nk, .0060, .0062))), (.0070 * nk, .0080, .0062)), .006)
        d = smax(d, -ellipsoid(P, V(sub + Vector((.0066 * nk, .0045, -.0004))), (.0036 * nk, .0050, .0020)), .0016)
        # ears
        d = smin(d, self.ear(P, g), .006)
        return d

    def ear(self, P, g):
        hs = g["hs"]
        c = g["tragion"] + Vector((.006 * hs, .010 * hs, .006 * hs))
        tilt = math.radians(14)
        R = np.array([[1, 0, 0], [0, math.cos(tilt), -math.sin(tilt)], [0, math.sin(tilt), math.cos(tilt)]], F32)
        outer = ellipsoid(P, V(c), (.0085 * hs, .0175 * hs, .0305 * hs), R)
        bowl = ellipsoid(P, V(c + Vector((.008 * hs, -.002 * hs, -.005 * hs))), (.006 * hs, .010 * hs, .013 * hs), R)
        return smax(outer, -bowl, .003)

    # ------------------------------------------------------------------ whole body
    PARTS = ("torso", "neck", "arm", "hand", "leg", "foot", "head")

    def part(self, name, P):
        P = np.asarray(P, F32).copy()
        P[:, 0] = np.abs(P[:, 0])
        return {"torso": self.torso, "neck": self.neck, "arm": self.arm_part, "hand": self.hand_part, "leg": self.leg_part,
                "foot": self.foot_part, "head": self.head_part}[name](P)

    def __call__(self, P):
        P = np.asarray(P, F32).copy()
        P[:, 0] = np.abs(P[:, 0])
        d = self.torso(P)
        d = smin(d, self.neck(P), .045)
        d = smin(d, self.head_part(P), .03)
        d = smin(d, self.arm_part(P), .025)
        d = smin(d, self.hand_part(P), .015)
        d = smin(d, self.leg_part(P), .04)
        d = smin(d, self.foot_part(P), .02)
        return d
