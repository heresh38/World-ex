"""Anatomy of the player base bodies as signed-distance fields (see sdf.py).

Blender coordinates: Z up, the character faces -Y, +X is the character's left. Left-side parts are modelled once and
mirrored for the right. The head lives in its own local frame (origin between the ears) and is meshed at a finer
resolution; hands and feet too. Each part is cut with an overlap band so the separate meshes meet without gaps.
"""
import numpy as np
import sdf
from sdf import smin, smax, sphere, ellipsoid, capsule, round_cone, smoothstep, Loft, length

F32 = np.float32


def mirror(fn):
    """Evaluate a left-side shape for the right side."""
    def g(P):
        Q = P.copy(); Q[:, 0] = -Q[:, 0]
        return fn(Q)
    return g


def both(fn):
    return lambda P: np.minimum(fn(P), mirror(fn)(P))


def lerp(a, b, t):
    return a + (b - a) * t


# ====================================================================== head
class Head:
    """Head in local coordinates (metres). Front is -Y. Feature dict `f` drives the base shape (sex)."""

    def __init__(self, sex):
        self.sex = sex
        m = sex == 'male'
        self.m = m
        s = 1.1 if m else 1.07          # overall head scale (heroic proportions: slightly large heads)
        self.s = s
        # eye centre (left eye) and radius
        self.eye_r = (.0122 if sex == 'female' else .0118) * s
        self.eye = np.array([.0312, -.0588, .012]) * s
        self.ear = np.array([.066, .006, -.004]) * s

    def lid_opening(self, P, side_eye):
        """2D almond opening around the eye, in the plane facing -Y. Negative inside the opening."""
        s = self.s
        E = side_eye
        a = (P[:, 0] - E[0]) * np.sign(E[0])        # + outward (temple side)
        b = P[:, 2] - E[2]
        tilt = .07 if not self.m else .04          # outer corner up
        ca, sa = np.cos(tilt), np.sin(tilt)
        a, b = a * ca + b * sa, -a * sa + b * ca
        w = (.0152 if not self.m else .0146) * s
        hu = (.0072 if not self.m else .0058) * s   # upper lid height
        hd = (.0043 if not self.m else .0038) * s   # lower lid
        R1 = (w * w + hu * hu) / (2 * hu); c1 = hu - R1
        R2 = (w * w + hd * hd) / (2 * hd); c2 = -hd + R2
        sh = .0012 * s                               # peak of the upper lid sits slightly inward
        d1 = np.sqrt((a + sh) ** 2 + (b - c1) ** 2) - R1
        d2 = np.sqrt((a - sh * .6) ** 2 + (b - c2) ** 2) - R2
        return np.maximum(d1, d2)

    # head silhouette: z, centre y (front -), front depth, back depth, half width, front exponent
    PROFILE_F = [
        (-.099, -.060, .006, .010, .010, 2.0),
        (-.093, -.055, .016, .022, .026, 2.0),
        (-.085, -.045, .026, .034, .040, 2.0),
        (-.074, -.032, .038, .048, .050, 2.0),
        (-.055, -.019, .052, .055, .057, 2.05),
        (-.035, -.010, .063, .059, .061, 2.1),
        (-.012, -.004, .070, .072, .065, 2.2),
        (.010, .002, .072, .081, .067, 2.2),
        (.032, .006, .074, .089, .0695, 2.2),
        (.055, .009, .075, .090, .0695, 2.4),
        (.076, .012, .075, .087, .067, 2.2),
        (.094, .015, .070, .079, .061, 2.1),
        (.108, .017, .058, .068, .051, 2.0),
        (.119, .019, .040, .046, .035, 2.0),
        (.125, .020, .010, .015, .012, 2.0)]
    PROFILE_M = [
        (-.108, -.058, .008, .012, .012, 2.0),
        (-.101, -.053, .018, .026, .028, 2.0),
        (-.092, -.044, .026, .040, .044, 2.1),
        (-.078, -.033, .038, .051, .055, 2.2),
        (-.058, -.021, .052, .057, .061, 2.25),
        (-.036, -.011, .063, .061, .064, 2.3),
        (-.012, -.005, .069, .072, .066, 2.4),
        (.010, .002, .071, .085, .068, 2.4),
        (.032, .006, .074, .089, .0705, 2.3),
        (.055, .009, .075, .090, .0705, 2.4),
        (.076, .012, .072, .092, .068, 2.2),
        (.094, .015, .064, .083, .062, 2.1),
        (.108, .017, .050, .068, .052, 2.0),
        (.119, .019, .030, .046, .036, 2.0),
        (.125, .020, .010, .015, .012, 2.0)]

    def base(self):
        if getattr(self, '_base', None) is None:
            s = self.s
            pr = np.array(self.PROFILE_M if self.m else self.PROFILE_F)
            z0, z1 = pr[0, 0] * s, pr[-1, 0] * s
            t = (pr[:, 0] * s - z0) / (z1 - z0)
            self._base = Loft((0, 0, z0), (0, 0, z1), dict(t=t, rv_pos=pr[:, 4] * s, rw_pos=pr[:, 2] * s, rw_neg=pr[:, 3] * s,
                                                           cw=-pr[:, 1] * s, n=pr[:, 5], nb=np.full(len(t), 2.0)),
                              v_axis=(-1, 0, 0), cap=.6)
        return self._base

    def __call__(self, P):
        m, s = self.m, self.s
        S = lambda v: np.asarray(v, F32) * s
        d = self.base()(P)
        # cheeks: one broad soft volume that stays inside the face outline; male gets a subtle cheekbone
        for sx in (1, -1):
            d = smin(d, ellipsoid(P, S((sx * .03, -.04, -.016)), S((.028, .028, .03) if not m else (.029, .027, .031))), .034 * s)
            if m:
                d = smin(d, ellipsoid(P, S((sx * .044, -.05, -.002)), S((.014, .016, .01))), .02 * s)
        lz = .004 if not m else 0.0
        # chin
        d = smin(d, ellipsoid(P, S((0, -.055, -.088 + lz)), S((.022, .015, .015) if not m else (.026, .015, .015))), .024 * s)
        # brow ridge + forehead
        if m:
            for sx in (1, -1):
                d = smin(d, round_cone(P, S((sx * .012, -.073, .027)), S((sx * .044, -.063, .029)), .0065 * s, .0045 * s), .02 * s)
        # muzzle (teeth/alveolar mass under the lips)
        d = smin(d, ellipsoid(P, S((0, -.056, -.046)), S((.029, .026, .026))), .02 * s)
        # eye sockets
        for sx in (1, -1):
            E = self.eye * np.array([sx, 1, 1])
            d = smax(d, -ellipsoid(P, E + S((sx * .001, -.012, .005)), S((.015, .007, .009))), .008 * s)
        # nose
        d = smin(d, self.nose(P), .006 * s)
        # lips
        d = self.lips(P, d)
        # eyelids
        for sx in (1, -1):
            E = (self.eye * np.array([sx, 1, 1])).astype(F32)
            shell = sphere(P, E, self.eye_r + .001 * s)
            op = self.lid_opening(P, E)
            cut = np.maximum(op, P[:, 1] - (E[1] - .003 * s))
            lids = smax(shell, -cut, .0008 * s)
            d = smin(d, lids, .0035 * s)
        # ears
        d = smin(d, self.ear_sdf(P), .003 * s)
        d = smin(d, mirror(self.ear_sdf)(P), .003 * s)
        return d

    def nose(self, P):
        m, s = self.m, self.s
        S = lambda v: np.asarray(v, F32) * s
        wide = .92 if not m else 1.08
        L = .9 if not m else 1.0
        tip = S((0, -.0875 - .004 * L, -.0175 - .003 * L))
        n = round_cone(P, S((0, -.068, .012)), tip + S((0, .004, .004)), .0034 * s, .0052 * s)        # bridge
        n = smin(n, ellipsoid(P, tip, S((.0082 * wide, .0082, .0074))), .005 * s)                     # tip
        for sx in (1, -1):
            n = smin(n, ellipsoid(P, S((sx * .0105 * wide, -.0805, -.0255)), S((.0068, .0075, .0062))), .0045 * s)  # alae
        # nostrils, opening downwards
        for sx in (1, -1):
            n = smax(n, -ellipsoid(P, S((sx * .0062 * wide, -.0845, -.0295)), S((.0034, .0052, .0022))), .0012 * s)
        return n

    def lips(self, P, d):
        m, s = self.m, self.s
        S = lambda v: np.asarray(v, F32) * s
        full = .85 if m else 1.15
        lz = .002 if not m else 0.0
        mw = .02 if not m else .022
        up = ellipsoid(P, S((0, -.0775, -.0455 + lz)), S((mw, .0085, .0058 * full)))
        lo = ellipsoid(P, S((0, -.0755, -.0545 + lz)), S((mw * .86, .0088, .0068 * full)))
        # cupid's bow: two small bumps
        for sx in (1, -1):
            up = smin(up, ellipsoid(P, S((sx * .0045, -.0795, -.0445 + lz)), S((.006, .005, .004 * full))), .002 * s)
        lp = smin(up, lo, .002 * s)
        d = smin(d, lp, .0045 * s)
        # philtrum groove
        # mouth line: thin slit between the lips, deeper at the centre
        slit = ellipsoid(P, S((0, -.084, -.0503 + lz)), S((mw + .0015, .014, .00075)))
        d = smax(d, -slit, .0009 * s)
        # corners
        for sx in (1, -1):
            d = smax(d, -sphere(P, S((sx * (mw + .0005), -.071, -.0505 + lz)), .0022 * s), .002 * s)
        return d

    def ear_sdf(self, P):
        """Left ear. Plate + helix rim + antihelix, concha bowl and lobe."""
        m, s = self.m, self.s
        S = lambda v: np.asarray(v, F32) * s
        c = self.ear
        # ear frame: plane faces outward (+X) and slightly forward, tilted back ~14 degrees
        R = sdf.rot((0, 0, 1), -.30) @ sdf.rot((1, 0, 0), -.22)
        q = (P - c) @ R.astype(F32)        # rows of R^T -> local coords: x out, y back, z up
        x, y, z = q[:, 0], q[:, 1], q[:, 2]
        hs = 1.0 if not m else 1.05
        # 2D shape in (y, z): egg, wider at the top
        ry = (.0145 + .0025 * np.clip(z / (.028 * s), -1, 1)) * s * hs
        rz = .0275 * s * hs
        e2 = np.sqrt((y / ry) ** 2 + ((z + .002 * s) / rz) ** 2)
        d2 = (e2 - 1) * np.minimum(ry, rz)
        thick = .0035 * s
        plate = np.maximum(d2, np.abs(x - .006 * s) - thick)
        rim = np.sqrt((d2 + .0028 * s) ** 2 + (x - .0085 * s) ** 2) - .0031 * s
        ear = smin(plate, rim, .002 * s)
        # concha bowl
        ear = smax(ear, -ellipsoid(q, S((.012, -.002, -.006)), S((.007, .009, .013))), .0025 * s)
        # antihelix ridge
        ear = smin(ear, np.sqrt((np.sqrt((y / (ry * .62)) ** 2 + ((z - .004 * s) / (rz * .66)) ** 2) - 1) ** 2 * (.012 * s) ** 2
                                + (x - .0075 * s) ** 2) - .0018 * s, .0015 * s)
        # lobe
        ear = smin(ear, ellipsoid(q, S((.006, -.004, -.026)), S((.004, .009, .008))), .003 * s)
        # root: attach to the head on the inner side
        ear = smin(ear, ellipsoid(q, S((-.002, .001, -.004)), S((.006, .011, .02))), .004 * s)
        return ear


# ====================================================================== body
def prof(rows, keys):
    a = np.array(rows, float)
    return {k: a[:, i] for i, k in enumerate(keys)}


class Body:
    """Whole base body. Joints follow the shared rig's bone names (characters.make_armature)."""

    def __init__(self, sex):
        self.sex = sex; m = self.m = sex == 'male'
        self.H = 1.84 if m else 1.68
        self.head = Head(sex)
        hs = self.head.s
        self.head_o = np.array([0, .004, self.H - .125 * hs], F32)    # head-local origin in world
        if m:
            self.zsh, self.sx = 1.512, .192
            self.elbow = np.array([.25, .024, 1.18]); self.wrist = np.array([.292, .004, .922]); self.tip = np.array([.308, -.008, .724])
            self.hip = np.array([.094, 0, .955]); self.knee = np.array([.098, -.012, .52]); self.ankle = np.array([.096, .03, .088])
            self.toe = np.array([.098, -.17, .02])
            self.z = dict(navel=1.09, chest=1.30, neck=1.525, crotch=.86)
        else:
            self.zsh, self.sx = 1.378, .162
            self.elbow = np.array([.214, .022, 1.074]); self.wrist = np.array([.252, .004, .838]); self.tip = np.array([.266, -.008, .66])
            self.hip = np.array([.084, 0, .872]); self.knee = np.array([.088, -.01, .474]); self.ankle = np.array([.086, .026, .078])
            self.toe = np.array([.088, -.152, .018])
            self.z = dict(navel=1.005, chest=1.19, neck=1.392, crotch=.77)
        self.shoulder = np.array([self.sx, .006, self.zsh])
        self.build()

    # -------------------------------------------------------------- rig joints (Blender space)
    def joints(self):
        from mathutils import Vector as V
        z = self.z
        J = {}
        J['hips'] = (V((0, 0, self.hip[2])), V((0, 0, z['navel'])))
        J['spine'] = (V((0, 0, z['navel'])), V((0, 0, z['chest'])))
        J['chest'] = (V((0, 0, z['chest'])), V((0, .004, z['neck'])))
        neck_top = self.head_o + np.array([0, .004, -.035 * self.head.s])
        J['neck'] = (V((0, .004, z['neck'])), V(tuple(neck_top)))
        J['head'] = (V(tuple(neck_top)), V(tuple(self.head_o + np.array([0, 0, .125 * self.head.s]))))
        for side, sx in (('L', 1), ('R', -1)):
            mv = lambda p: V((p[0] * sx, p[1], p[2]))
            J['upperarm.' + side] = (mv(self.shoulder), mv(self.elbow))
            J['forearm.' + side] = (mv(self.elbow), mv(self.wrist))
            J['hand.' + side] = (mv(self.wrist), mv(self.tip))
            J['thigh.' + side] = (mv(self.hip), mv(self.knee))
            J['shin.' + side] = (mv(self.knee), mv(self.ankle))
            J['foot.' + side] = (mv(self.ankle), mv(self.toe))
        return J

    # -------------------------------------------------------------- parts
    def build(self):
        m = self.m
        if m:
            T = [(.83, .05, .045, .045, 0, 2.0), (.87, .115, .068, .078, 0, 2.2), (.91, .155, .084, .098, .001, 2.3),
                 (.95, .166, .088, .100, .002, 2.4),
                 (1.00, .162, .093, .090, .004, 2.4), (1.07, .150, .098, .084, .006, 2.4), (1.14, .150, .101, .086, .006, 2.5),
                 (1.22, .160, .105, .094, .004, 2.6), (1.30, .172, .108, .100, .002, 2.7), (1.38, .180, .104, .103, 0, 2.7),
                 (1.44, .168, .084, .095, -.004, 2.6), (1.495, .128, .064, .076, -.006, 2.4), (1.535, .062, .048, .054, -.004, 2.1)]
        else:
            T = [(.75, .045, .040, .040, 0, 2.0), (.79, .105, .062, .075, 0, 2.2), (.83, .150, .076, .098, 0, 2.3),
                 (.87, .168, .081, .098, .002, 2.4), (.92, .162, .082, .082, .005, 2.4), (.98, .143, .083, .071, .008, 2.3),
                 (1.035, .127, .079, .067, .008, 2.3), (1.09, .128, .081, .069, .006, 2.4), (1.15, .137, .087, .077, .003, 2.5),
                 (1.21, .145, .088, .084, 0, 2.6), (1.27, .149, .082, .088, 0, 2.6), (1.325, .145, .072, .084, -.004, 2.5),
                 (1.36, .118, .058, .068, -.007, 2.3), (1.40, .058, .044, .048, -.005, 2.1)]
        T = np.array(T)
        z0, z1 = T[0, 0], T[-1, 0]
        self.torso_z = (z0, z1)
        self.torso = Loft((0, 0, z0), (0, 0, z1), dict(t=(T[:, 0] - z0) / (z1 - z0), rv_pos=T[:, 1], rw_pos=T[:, 2],
                                                       rw_neg=T[:, 3], cw=T[:, 4], n=T[:, 5], nb=np.minimum(T[:, 5], 2.3)),
                          v_axis=(-1, 0, 0), cap=.7)
        # neck: base inside the shoulders, top inside the skull
        hn = self.head_o
        nz0 = self.z['neck'] - .05
        self.neck = Loft((0, .0, nz0), (0, .012, hn[2] - .005), dict(
            t=[0, .35, .7, 1], rv_pos=np.array([.052, .043, .041, .042]) * (1.18 if m else 1),
            rw_pos=np.array([.046, .041, .040, .040]) * (1.12 if m else 1), rw_neg=np.array([.05, .044, .043, .045]) * (1.12 if m else 1),
            cw=[0, .002, .004, .006], n=[2.2, 2.1, 2.0, 2.0]), v_axis=(-1, 0, 0), cap=.5)
        # arms (left)
        k = 1.22 if m else 1.0
        up = prof([(0, .043, .040, .044, .044), (.2, .040, .037, .041, .042), (.45, .036, .034, .037, .038),
                   (.75, .032, .030, .032, .032), (1, .029, .028, .028, .030)], ('t', 'rv_pos', 'rv_neg', 'rw_pos', 'rw_neg'))
        if m:
            up = prof([(0, .054, .050, .054, .054), (.2, .051, .047, .052, .053), (.45, .046, .043, .050, .049),
                       (.75, .041, .038, .043, .042), (1, .036, .035, .036, .038)], ('t', 'rv_pos', 'rv_neg', 'rw_pos', 'rw_neg'))
        fo = prof([(0, .031, .029, .032, .032), (.2, .033, .031, .035, .034), (.45, .029, .027, .031, .030),
                   (.75, .021, .020, .025, .024), (1, .018, .017, .024, .023)], ('t', 'rv_pos', 'rv_neg', 'rw_pos', 'rw_neg'))
        if m:
            fo = {kk: (v * 1.2 if kk != 't' else v) for kk, v in fo.items()}
        sh, el, wr = self.shoulder, self.elbow, self.wrist
        self.upper = Loft(sh + np.array([-.004, 0, .012]), el, up, v_axis=(1, 0, 0), cap=.8)
        self.fore = Loft(el + (el - wr) / np.linalg.norm(el - wr) * .01, wr + (wr - el) / np.linalg.norm(wr - el) * .012, fo,
                         v_axis=(1, 0, 0), cap=.7)
        # legs (left)
        th = prof([(0, .072, .056, .068, .075), (.12, .080, .072, .076, .080), (.35, .074, .068, .074, .074),
                   (.6, .064, .058, .064, .063), (.85, .054, .048, .054, .052), (1, .048, .044, .049, .046)],
                  ('t', 'rv_pos', 'rv_neg', 'rw_pos', 'rw_neg'))
        sn = prof([(0, .046, .044, .044, .044), (.15, .045, .044, .039, .054), (.35, .046, .045, .037, .058),
                   (.6, .039, .037, .032, .044), (.85, .029, .028, .026, .029), (1, .026, .025, .024, .027)],
                  ('t', 'rv_pos', 'rv_neg', 'rw_pos', 'rw_neg'))
        if m:
            th = {kk: (v * 1.06 if kk != 't' else v) for kk, v in th.items()}
            sn = {kk: (v * 1.1 if kk != 't' else v) for kk, v in sn.items()}
        hp, kn, an = self.hip, self.knee, self.ankle
        self.thigh = Loft(hp + np.array([.006, 0, .05]), kn, th, v_axis=(1, 0, 0), cap=.8)
        self.shin = Loft(kn + (kn - an) / np.linalg.norm(kn - an) * .01, an + np.array([0, 0, -.01]), sn, v_axis=(1, 0, 0), cap=.6)

    def torso_sdf(self, P):
        m = self.m
        z = self.z
        d = self.torso(P)
        zsh = self.zsh
        if m:
            for sx in (1, -1):   # pectorals
                d = smin(d, ellipsoid(P, (sx * .072, -.07, 1.372), (.078, .034, .056), sdf.rot((0, 1, 0), sx * .18)), .03)
            for i, zz in enumerate((1.11, 1.165, 1.225)):   # abdominals
                for sx in (1, -1):
                    d = smin(d, ellipsoid(P, (sx * .024, -.088 + i * .002, zz), (.021, .014, .024)), .012)
        else:
            for sx in (1, -1):   # breasts
                d = smin(d, ellipsoid(P, (sx * .071, -.062, 1.205), (.058, .05, .054), sdf.rot((0, 0, 1), -sx * .2)), .032)
        # glutes
        gz = .845 if not m else .925
        for sx in (1, -1):
            d = smin(d, ellipsoid(P, (sx * .064, .056 if not m else .058, gz), (.078, .05, .08) if not m else (.07, .044, .072)), .05)
        # shoulder girdle: trapezius, clavicles, scapulae
        for sx in (1, -1):
            d = smin(d, round_cone(P, (sx * .028, .022, z['neck'] + .012), (sx * (self.sx - .03), .012, zsh + .004),
                                   .036 if m else .024, .026 if m else .017), .035)
            d = smin(d, round_cone(P, (sx * .025, -.044 if not m else -.05, zsh + .022), (sx * (self.sx - .025), -.018, zsh + .026),
                                   .007 if not m else .009, .006), .025)
            d = smin(d, ellipsoid(P, (sx * .068, .062 if not m else .074, zsh - .095), (.045, .016, .06)), .04)
        # spine groove
        for z0, z1 in ((self.torso_z[0] + .2, zsh - .02),):
            d = smax(d, -capsule(P, (0, .092 if m else .078, z0), (0, .1 if m else .088, z1), .005), .016)
        return d

    def arm_sdf(self, P):
        """Left arm incl. deltoid (no hand)."""
        m = self.m
        a = smin(self.upper(P), self.fore(P), .03)
        u = self.elbow - self.shoulder; u = u / np.linalg.norm(u)
        R = sdf.frame(u, (0, 0, 1))
        dc = self.shoulder + np.array([.012, 0, -.03])
        a = smin(a, ellipsoid(P, dc, (.08 if m else .07, .056 if m else .046, .054 if m else .046), R), .025)
        # elbow point
        a = smin(a, sphere(P, self.elbow + np.array([0, .028 if m else .024, 0]), .012), .015)
        return a

    def leg_sdf(self, P):
        m = self.m
        d = smin(self.thigh(P), self.shin(P), .045)
        kn = self.knee
        d = smin(d, ellipsoid(P, kn + np.array([0, -.04 if not m else -.044, .012]), (.024, .014, .028)), .016)
        return d

    def hand_sdf(self, P):
        """Left hand, relaxed curl. Local frame: x along the hand, y towards the thumb (front), z dorsal (outward)."""
        m = self.m
        sc = 1.12 if m else 1.0
        wr, tp = self.wrist, self.tip
        ux = (tp - wr) / np.linalg.norm(tp - wr)
        uz = np.array([1.0, 0, 0]); uz = uz - np.dot(uz, ux) * ux; uz /= np.linalg.norm(uz)
        uy = np.cross(uz, ux)
        R = np.array([ux, uy, uz], F32)
        q = ((P - wr) @ R.T) / sc
        S = lambda *v: np.array(v, F32)
        d = sdf.round_box(q, S(.047, 0, .001), S(.046, .036, .0125), .011)                  # palm
        d = smin(d, ellipsoid(q, S(.03, .021, -.008), S(.032, .017, .014)), .012)           # thenar
        d = smin(d, ellipsoid(q, S(.045, -.024, -.007), S(.035, .012, .011)), .01)          # hypothenar
        d = smin(d, ellipsoid(q, S(.002, 0, 0), S(.02, .03, .016)), .015)                   # wrist
        fingers = [(.024, (.044, .026, .021), .0088, .02), (.008, (.048, .029, .022), .0092, .0),
                   (-.009, (.045, .027, .021), .0088, -.02), (-.025, (.035, .021, .019), .0076, -.05)]
        for i, (fy, segs, r0, splay) in enumerate(fingers):
            p = S(.09 - abs(fy) * .25, fy, .002)
            ang = 0.0
            dirs = []
            for j, L in enumerate(segs):
                ang += (.22, .35, .28)[j] + .05 * i
                dvec = np.array([np.cos(ang), splay * (1 - .3 * j), -np.sin(ang)]); dvec /= np.linalg.norm(dvec)
                p2 = p + dvec * L
                r1 = r0 * (1 - .1 * (j + 1))
                d = smin(d, round_cone(q, p, p2, r0 * (1 - .1 * j), r1), .004 if j else .01)
                if j == 0:   # knuckle
                    d = smin(d, sphere(q, p + S(0, 0, .004), r0 * .9), .006)
                p = p2
        # thumb
        t0 = S(.016, .03, -.006); t1 = S(.048, .052, -.02); t2 = S(.074, .058, -.032); t3 = S(.094, .056, -.04)
        d = smin(d, round_cone(q, t0, t1, .013, .011), .012)
        d = smin(d, round_cone(q, t1, t2, .0105, .0095), .004)
        d = smin(d, round_cone(q, t2, t3, .009, .0078), .003)
        return d * sc

    def foot_sdf(self, P):
        """Left bare foot with the sole flat on the ground."""
        m = self.m
        sc = 1.1 if m else 1.0
        A = self.ankle
        q = (P - np.array([A[0], A[1], 0], F32)) / sc
        S = lambda *v: np.array(v, F32)
        az = A[2] / sc
        d = ellipsoid(q, S(0, .028, .036), S(.031, .042, .036))                                  # heel
        d = smin(d, ellipsoid(q, S(.002, -.04, .042), S(.037, .062, .03)), .03)                  # midfoot
        d = smin(d, ellipsoid(q, S(-.004, -.125, .024), S(.044, .032, .021)), .03)               # ball
        d = smin(d, round_cone(q, S(0, .0, az), S(0, -.06, .05), .028, .026), .03)               # instep
        for sx, r in ((1, .013), (-1, .012)):                                                     # malleoli (outer lower)
            d = smin(d, sphere(q, S(sx * .024, .004, az - (.006 if sx > 0 else 0)), r), .01)
        # arch (inner side, medial is -x for the left foot)
        d = smax(d, -ellipsoid(q, S(-.04, -.05, .0), S(.02, .045, .018)), .02)
        toes = [(-.022, .0115, .036, -.155), (-.002, .0082, .03, -.152), (.013, .0075, .027, -.146), (.026, .0068, .023, -.138),
                (.037, .0062, .019, -.128)]
        for tx, r, L, ty in toes:
            a = S(tx, ty + .012, .018); b = S(tx * 1.08, ty - L + .012, .01 + r * .4)
            d = smin(d, round_cone(q, a, b, r * 1.05, r * .9), .006)
        d = smax(d, -q[:, 2] + .0005, .004)                                                       # flat sole
        return d * sc


# ====================================================================== composite field
def bounded(fn, lo, hi, margin=.07):
    """Evaluate fn only inside an AABB (+margin); outside return the (positive) distance to the box."""
    lo = np.asarray(lo, F32) - margin; hi = np.asarray(hi, F32) + margin

    def g(P):
        inside = np.all((P >= lo) & (P <= hi), axis=1)
        out = length(np.maximum(np.maximum(lo - P, P - hi), 0)) + margin
        if inside.any():
            out[inside] = fn(P[inside])
        return out
    return g


class Field:
    """The complete naked body as one field, plus per-part fields for skin weights."""

    def __init__(self, body):
        B = self.B = body
        hs = B.head.s
        ho = B.head_o
        self.head_w = bounded(lambda P: B.head(P - ho), ho + np.array([-.1, -.12, -.12]) * hs, ho + np.array([.1, .12, .135]) * hs)
        sh, el, wr, tp = B.shoulder, B.elbow, B.wrist, B.tip
        self.arm_l = bounded(B.arm_sdf, np.minimum(sh, wr) - .09, np.maximum(sh, wr) + np.array([.09, .09, .09]))
        lo = np.minimum(wr, tp) - .07; hi = np.maximum(wr, tp) + .07
        self.hand_l = bounded(B.hand_sdf, lo, hi)
        self.leg_l = bounded(B.leg_sdf, np.minimum(B.hip, B.ankle) + np.array([-.11, -.1, -.03]),
                             np.maximum(B.hip, B.ankle) + np.array([.11, .1, .1]))
        A = B.ankle
        self.foot_l = bounded(B.foot_sdf, np.array([A[0] - .08, A[1] - .26, -.01]), np.array([A[0] + .08, A[1] + .08, A[2] + .07]))
        self.torso_b = bounded(lambda P: smin(B.torso_sdf(P), B.neck(P), .03), np.array([-.25, -.2, B.torso_z[0] - .05]),
                               np.array([.25, .2, B.head_o[2] + .02]))

    def parts(self, P):
        B = self.B
        z = P[:, 2]; ax = np.abs(P[:, 0])
        tor = smin(self.torso_b(P), self.head_w(P), .018)
        out = {'torso': tor}
        for side, Q in (('L', P), ('R', P * np.array([-1, 1, 1], F32))):
            out['arm' + side] = smin(self.arm_l(Q), self.hand_l(Q), .012)
            out['leg' + side] = smin(self.leg_l(Q), self.foot_l(Q), .02)
        return out

    def __call__(self, P):
        B = self.B
        z = P[:, 2]; ax = np.abs(P[:, 0])
        p = self.parts(P)
        d = p['torso']
        ka = .034 * smoothstep(B.zsh - .17, B.zsh - .07, z) + .002
        d = smin(d, p['armL'], ka); d = smin(d, p['armR'], ka)
        kl = (.06 * smoothstep(.015, .09, ax) + .006) * smoothstep(B.hip[2] - .32, B.hip[2] - .14, z) + .002
        legs = np.minimum(p['legL'], p['legR'])
        d = smin(d, legs, kl)
        return d
