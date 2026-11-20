"""The male body's ANATOMY (Project Orion), built first, the way the owner asked on 2026-11-16 ("build the underlying
human anatomy first. The undersuit should follow the body rather than determine its shape"):

  * the skeleton's landmarks for the owner's canon (8 heads at 1.84 m, shoulders 2.5 heads, arm span = height,
    torso 3 heads, legs 4) in the sheet's T-pose (arms 6 degrees below level, feet apart as the sheet stands);
  * the deep volumes (ribcage, abdomen, pelvis, the neck's core, the long bones) and the bones that show under
    the skin (clavicles, sternum, the scapulae's spines, the 7th vertebra, the iliac crests, the kneecaps, the
    tibia's front, the ankles, the elbows, the wrists);
  * the MUSCLES, each a belly lofted from its origin to its insertion: a flattened section whose width runs from
    the origin's span to the tendon's and whose thickness swells to the belly, laid along a path that follows
    the body's curve, its thickness outward from the bone or the trunk it lies on;
  * a thin athletic layer of fat over them (more on the lower belly, the flanks and the buttocks), the skin
    their envelope.

The undersuit is made afterwards, ON this skin. The owner's notes of 2026-11-16 are in the numbers: hands a little
larger (20 cm), thighs of natural volume, the waist a little wider than the sheet's.

A signed distance field in metres (world: Z up, the body faces -Y, its left is +X); the left side is modelled and
the right is its mirror (|x|).
"""
import math
import os
import sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
from sdf import smin, smax, length  # noqa: E402

F32 = np.float32


def V(*a):
    return np.array(a, F32)


def unit(v):
    v = np.asarray(v, F32)
    return v / max(float(np.linalg.norm(v)), 1e-9)


# --- the skeleton (left side) ------------------------------------------------------------------------------------

STATURE = 1.84
DROP = math.radians(6.0)
UPPER_ARM, FOREARM, HAND = 0.312, 0.272, 0.200          # (body.py's: an adult man's arm, 58.4 cm joint to wrist)
UK = UPPER_ARM / 0.290                                     # the upper arm's muscles were placed on a .290 humerus
A_DIR = V(math.cos(DROP), 0, -math.sin(DROP))            # along the left arm
A_UP = V(math.sin(DROP), 0, math.cos(DROP))              # the arm's top (its outside when it hangs)
FR, BK = V(0, -1, 0), V(0, 1, 0)
S = V(0.178, -0.030, 1.486)                              # glenohumeral joint (as body.py's)
E = S + A_DIR * UPPER_ARM                                # elbow
W = S + A_DIR * (UPPER_ARM + FOREARM)                    # wrist
H = V(0.095, -0.025, 0.925)                              # hip joint
K = V(0.150, -0.010, 0.505)                              # knee
A = V(0.205, 0.030, 0.085)                               # ankle
J = V(0.0, -0.068, 1.505)                                # jugular notch
XI = V(0.0, -0.112, 1.290)                               # xiphoid
C7 = V(0.0, 0.080, 1.556)
ASIS = V(0.118, -0.082, 1.025)
PSIS = V(0.045, 0.082, 1.045)
GT = V(0.170, -0.005, 0.897)                             # greater trochanter


# --- primitives --------------------------------------------------------------------------------------------------

def sphere(P, c, r):
    return length(P - c) - r


def ell(P, c, r):
    q = (P - c) / r
    k0 = length(q)
    k1 = length(q / r)
    return k0 * (k0 - 1.0) / np.maximum(k1, 1e-9)


def capsule(P, a, b, r):
    pa, ba = P - a, b - a
    h = np.clip((pa @ ba) / float(ba @ ba), 0, 1)
    return length(pa - h[:, None] * ba) - r


def cone(P, a, b, ra, rb):
    pa, ba = P - a, b - a
    h = np.clip((pa @ ba) / float(ba @ ba), 0, 1)
    return length(pa - h[:, None] * ba) - (ra + (rb - ra) * h)


def tube(P, pts, radii, k=.004):
    out = None
    for i in range(len(pts) - 1):
        d = cone(P, V(*pts[i]), V(*pts[i + 1]), radii[i], radii[i + 1])
        out = d if out is None else smin(out, d, k)
    return out


def superell(P, c, rx, ryf, ryb, rzt, rzb, n):
    d = P - c
    ry = np.where(d[:, 1] < 0, ryf, ryb)
    rz = np.where(d[:, 2] > 0, rzt, rzb)
    f = ((np.abs(d[:, 0]) / rx) ** n + (np.abs(d[:, 1]) / ry) ** n + (np.abs(d[:, 2]) / rz) ** n) ** (1 / n)
    return (f - 1) * np.minimum(np.minimum(rx, ry), rz)


def ellipse2(u, v, a, b):
    """roughly the distance to an ellipse of half axes a, b (arrays) in its own plane"""
    q0 = np.sqrt((u / a) ** 2 + (v / b) ** 2)
    q1 = np.sqrt((u / (a * a)) ** 2 + (v / (b * b)) ** 2)
    return q0 * (q0 - 1.0) / np.maximum(q1, 1e-9)


# --- a muscle ----------------------------------------------------------------------------------------------------

def ease(x):
    """0 -> 1 with no slope at either end (smoothstep)"""
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def fillet(a, m, b, n=10):
    """the corner of the path a - m - b rounded: a quadratic arc from halfway along the shorter leg before m to as
    far after it (a sharp corner made the nearest segment, and with it the footprint's across-direction, jump on
    the line out from the corner: a step in the relief)"""
    f = .5 * min(float(np.linalg.norm(a - m)), float(np.linalg.norm(b - m)))
    p1 = m + (a - m) * f / max(float(np.linalg.norm(a - m)), 1e-9)
    p2 = m + (b - m) * f / max(float(np.linalg.norm(b - m)), 1e-9)
    s = np.linspace(0, 1, n + 1)
    return [(1 - q) ** 2 * p1 + 2 * q * (1 - q) * m + q * q * p2 for q in s]


class Muscle:
    """a muscle as how far it raises the body over the deep layer under it: a footprint that runs along a path from
    its origin (a line o0-o1, or a point) through `mid` to its insertion (i0-i1), as wide as the origin's span at
    one end and the tendon's at the other (or `w` at the belly), raised by a thickness that swells to `T` at `tb`
    of the way and falls to nothing at its edges, so it bends round whatever it lies on and two neighbours leave a
    groove between them. `inside` is the line it lies on (the bone, the trunk's axis): only the side facing away
    from it is raised."""

    # (a step lower on the trapezius, the chest and the arms: the owner, "still a little too bulky"; the deltoids
    # kept round: the shoulders' width makes the V that reads athletic rather than bulky)
    # (then up again toward the owner's sheet, 2026-11-20: his man is lean and CUT, not bulky: the chest's plates and
    # their lower edge, the abdomen's blocks, the deltoids' caps, the arms' heads told apart, the quads' heads)
    # (the arm's muscles a step above the rest the same day: at .26-.32 on a thin cage the arm was a tube with a
    # groove down it and the brachialis, with no entry here, showed at the .20 default: the owner, "the arms seem
    # extremely unrealistic compared to rest of body"; body.ARM_VOL gives the volume, these the forms on it)
    SHOW = {"delt_front": .42, "delt_side": .40, "delt_rear": .40, "trap_upper": .24, "pec_sternal": .36,
            "pec_clav": .32, "pec_abd": .32, "rectus_abd": .46, "serratus0": .6, "serratus1": .6, "serratus2": .6,
            "serratus3": .6, "biceps": .44, "brachialis": .40, "triceps_long": .40, "triceps_lat": .42,
            "gastro_med": .36, "gastro_lat": .36, "vast_med": .34, "vast_lat": .32, "rect_fem": .32, "oblique": .30,
            "lat": .28, "brachiorad": .42, "extensors": .36, "flexors": .36, "tib_ant": .28, "scm": .40, "glute_max": .30,
            "infraspinatus": .26, "teres_major": .30, "trap_mid": .22, "trap_lower": .26, "erector": .28}

    def __init__(self, name, o, i, T, tb=.45, mid=None, inside=None, w=None, edge=1.6, depth=.05):
        self.name = name
        self.show = self.SHOW.get(name)
        o0, o1 = (V(*o[0]), V(*o[1])) if len(o) == 2 and np.ndim(o[0]) else (V(*o), V(*o))
        i0, i1 = (V(*i[0]), V(*i[1])) if len(i) == 2 and np.ndim(i[0]) else (V(*i), V(*i))
        self.w0, self.w1 = max(float(np.linalg.norm(o1 - o0)) / 2, .006), max(float(np.linalg.norm(i1 - i0)) / 2, .005)
        self.u0 = unit(o1 - o0) if np.linalg.norm(o1 - o0) > 1e-6 else None
        self.u1 = unit(i1 - i0) if np.linalg.norm(i1 - i0) > 1e-6 else None
        a, b = (o0 + o1) / 2, (i0 + i1) / 2
        self.path = [a] + (fillet(a, V(*mid), b) if mid is not None else []) + [b]
        self.seg = [float(np.linalg.norm(self.path[k + 1] - self.path[k])) for k in range(len(self.path) - 1)]
        self.L = sum(self.seg)
        self.T, self.tb, self.wb, self.edge, self.depth = T, tb, w, edge, depth
        self.inside = (V(*inside[0]), V(*inside[1])) if inside is not None else (V(0, 0, 0.9), V(0, 0, 1.6))
        pts = np.array(self.path)
        r = max(self.w0, self.w1, w or 0) + T + depth + .02
        self.lo, self.hi = pts.min(0) - r, pts.max(0) + r

    def thickness(self, t):
        a = math.log(.5) / math.log(min(max(self.tb, .05), .95))
        t = np.clip(t, 0, 1)
        s = np.sin(np.pi * t ** a)
        # eased into its ends (the bare power rose from them with no limit to its slope: a crease along the origin's
        # and the insertion's lines, the slit on the shoulder's top under the suit)
        return self.T * np.maximum(s, 0) ** .7 * ease(t / .22) * ease((1 - t) / .22)

    def width(self, t):
        base = self.w0 + (self.w1 - self.w0) * t
        if self.wb is not None:
            bell = ease(np.sin(np.pi * np.clip(t, 0, 1)) / .6)
            base = base * (1 - bell) + self.wb * bell
        return np.maximum(base, .004)

    def raise_(self, P):
        """how far this muscle raises the skin at each point (metres, >= 0)"""
        out = np.zeros(len(P), F32)
        m = np.all((P >= self.lo) & (P <= self.hi), axis=1)
        if not m.any():
            return out
        Q = P[m]
        best = np.full(len(Q), 1e9, F32)
        t = np.zeros(len(Q), F32)
        C = np.zeros_like(Q)
        Tg = np.zeros_like(Q)
        acc = 0.0
        for k in range(len(self.path) - 1):
            a, b = self.path[k], self.path[k + 1]
            ba = b - a
            L2 = float(ba @ ba)
            h = (Q - a) @ ba / L2
            p = a + np.clip(h, 0, 1)[:, None] * ba
            dd = length(Q - p)
            sel = dd < best
            best = np.where(sel, dd, best)
            t = np.where(sel, (acc + h * self.seg[k]) / self.L, t)
            C = np.where(sel[:, None], p, C)
            Tg = np.where(sel[:, None], ba / math.sqrt(L2), Tg)
            acc += self.seg[k]
        tc = np.clip(t, 0, 1)
        # the direction away from what it lies on, square to the path
        p0, p1 = self.inside
        d01 = p1 - p0
        hh = np.clip((C - p0) @ d01 / float(d01 @ d01), 0, 1)
        n = C - (p0 + hh[:, None] * d01)
        n = n - (n * Tg).sum(1)[:, None] * Tg
        n /= np.maximum(length(n), 1e-9)[:, None]
        # the width direction: the origin's line turning to the insertion's, square to the path and to n
        u0 = self.u0 if self.u0 is not None else self.u1
        u1 = self.u1 if self.u1 is not None else self.u0
        if u0 is None:
            u = np.cross(Tg, n)
        else:
            if float(u0 @ u1) < 0:
                u1 = -u1
            u = u0[None, :] * (1 - tc[:, None]) + u1[None, :] * tc[:, None]
            u = u - (u * Tg).sum(1)[:, None] * Tg - (u * n).sum(1)[:, None] * n
            bad = length(u) < 1e-4
            u = np.where(bad[:, None], np.cross(Tg, n), u)
        u /= np.maximum(length(u), 1e-9)[:, None]
        rel = Q - C
        cu, cn = (rel * u).sum(1), (rel * n).sum(1)
        s_ = np.abs(cu) / self.width(tc)
        prof = np.maximum(1 - s_ ** 2, 0) ** self.edge
        ends = np.clip(1 - np.maximum(-t, t - 1) * self.L / .015, 0, 1)
        win = ease((cn + self.depth) / (self.depth * .6))               # only the side facing away
        out[m] = self.thickness(tc) * prof * ends * win
        return out


# --- the body -----------------------------------------------------------------------------------------------------

def arm_pt(base, along=0.0, up=0.0, fr=0.0, bk=0.0):
    p = V(*base) if not isinstance(base, np.ndarray) else base.copy()
    return tuple(p + A_DIR * along + A_UP * up + FR * fr + BK * bk)


TRUNK = ((0, .01, .95), (0, .01, 1.55))
FEMUR = (tuple(V(0.115, -0.015, 0.89)), tuple(K))
TIBIA = (tuple(K), tuple(A))
HUMERUS = (tuple(S - A_DIR * .03), tuple(E))
FOREARM_L = (tuple(E), tuple(W))


def muscles():
    M = []
    add = lambda *a, **k: M.append(Muscle(*a, **k))
    # --- chest and shoulder
    # (a man's pectoral is a PLATE: flat across, square at its outer lower corner where the fold before the armpit
    # is thickest; peaking at .40 of the way from the sternum with a round profile it was a mound inside and below,
    # a breast under the sheet's light: the owner, 2026-11-20)
    add("pec_clav", ((0.022, -0.080, 1.508), (0.095, -0.087, 1.518)),
        (arm_pt(S, .06, .004, .026), arm_pt(S, .095, 0, .024)), .022, .50, mid=(0.125, -0.093, 1.498), inside=TRUNK,
        edge=1.0)
    add("pec_sternal", ((0.012, -0.093, 1.482), (0.016, -0.113, 1.318)),
        (arm_pt(S, .065, -.012, .022), arm_pt(S, .105, -.020, .018)), .032, .60, mid=(0.120, -0.112, 1.408),
        inside=TRUNK, edge=1.0)
    add("pec_abd", ((0.030, -0.112, 1.302), (0.090, -0.104, 1.312)),
        (arm_pt(S, .075, -.030, .012), arm_pt(S, .100, -.035, .008)), .014, .35, mid=(0.135, -0.098, 1.360),
        inside=TRUNK)
    add("delt_front", ((0.115, -0.074, 1.524), (0.170, -0.056, 1.538)),
        (arm_pt(S, .120, .018, .012), arm_pt(S, .145, .016, .008)), .032, .40,
        mid=arm_pt(S, .04, .030, .045), inside=HUMERUS)
    add("delt_side", ((0.185, -0.035, 1.548), (0.205, 0.005, 1.548)),
        (arm_pt(S, .120, .024), arm_pt(S, .150, .022)), .039, .38, mid=arm_pt(S, .05, .052), inside=HUMERUS)
    add("delt_rear", ((0.110, 0.102, 1.500), (0.190, 0.032, 1.545)),
        (arm_pt(S, .120, .018, bk=.012), arm_pt(S, .145, .016, bk=.008)), .030, .40,
        mid=arm_pt(S, .03, .025, bk=.050), inside=HUMERUS)
    # --- back
    # (the upper trapezius' belly ON the slope from the neck to the shoulder, lower and further out: at 1.588 beside
    # the neck's base it stood a mound each side of the neck; the middle fibres flat between the shoulder blades)
    add("trap_upper", ((0.012, 0.058, 1.665), (0.012, 0.077, 1.558)), ((0.125, -0.035, 1.556), (0.195, 0.0, 1.552)),
        .028, .50, mid=(0.105, 0.040, 1.564), inside=((0, 0, 1.45), (0, 0, 1.66)))
    add("trap_mid", ((0.0, 0.088, 1.540), (0.0, 0.108, 1.430)), ((0.075, 0.118, 1.470), (0.190, 0.035, 1.545)),
        .012, .40, mid=(0.090, 0.116, 1.490), inside=((0, 0, 1.3), (0, 0, 1.6)), edge=1.0)
    add("trap_lower", ((0.0, 0.112, 1.420), (0.0, 0.098, 1.220)), ((0.070, 0.120, 1.468), (0.080, 0.120, 1.465)),
        .008, .45, mid=(0.050, 0.118, 1.360), inside=((0, 0, 1.2), (0, 0, 1.5)))
    add("lat", ((0.0, 0.108, 1.300), (0.120, 0.062, 1.065)), (arm_pt(S, .060, -.030, bk=.004), arm_pt(S, .085, -.030)),
        .030, .38, mid=(0.142, 0.085, 1.270), inside=((0, 0, 1.1), (0, 0, 1.45)))
    add("teres_major", ((0.085, 0.118, 1.340), (0.110, 0.110, 1.360)),
        (arm_pt(S, .060, -.028, bk=.008), arm_pt(S, .070, -.028)), .018, .50, mid=(0.150, 0.085, 1.390),
        inside=((0, 0, 1.3), (0, 0, 1.5)))
    add("infraspinatus", ((0.068, 0.124, 1.450), (0.085, 0.122, 1.355)),
        (arm_pt(S, 0, .008, bk=.032), arm_pt(S, 0, -.008, bk=.030)), .016, .40, mid=(0.130, 0.112, 1.430),
        inside=((0, 0, 1.3), (0, 0, 1.5)), edge=1.0)
    for k in range(4):                                      # the serratus' slips on the ribs under the arm
        z = 1.36 - .04 * k
        add(f"serratus{k}", ((0.118 + .006 * k, -0.080 + .006 * k, z), (0.122 + .006 * k, -0.076 + .006 * k, z - .018)),
            ((0.152, 0.035, z + .045), (0.150, 0.040, z + .020)), .010, .35, inside=((0, 0, 1.2), (0, 0, 1.45)),
            depth=.03)
    add("oblique", ((0.118, -0.088, 1.310), (0.155, 0.020, 1.170)), ((0.112, -0.088, 1.035), (0.158, -0.005, 1.075)),
        .030, .62, mid=(0.152, -0.045, 1.150), inside=((0, 0, 1.0), (0, 0, 1.3)))
    add("rectus_abd", ((0.006, -0.084, 0.948), (0.042, -0.085, 0.952)), ((0.008, -0.113, 1.310), (0.088, -0.107, 1.316)),
        .022, .50, mid=(0.040, -0.112, 1.130), inside=((0, .02, 1.0), (0, .02, 1.3)))
    add("erector", ((0.015, 0.088, 1.000), (0.048, 0.078, 1.035)), ((0.012, 0.118, 1.360), (0.058, 0.118, 1.360)),
        .028, .30, mid=(0.035, 0.106, 1.150), inside=((0, .02, 1.0), (0, .02, 1.4)))
    # --- hip
    add("glute_max", ((0.062, 0.088, 1.065), (0.020, 0.088, 0.925)), ((0.168, 0.012, 0.865), (0.158, 0.018, 0.800)),
        .050, .45, mid=(0.100, 0.116, 0.930), inside=((0.06, 0, .85), (0.06, 0, 1.05)))
    add("glute_med", ((0.122, -0.035, 1.045), (0.128, 0.055, 1.065)), ((0.165, -0.012, 0.905), (0.170, 0.008, 0.900)),
        .035, .45, mid=(0.158, 0.005, 0.990), inside=((0.05, 0, .9), (0.05, 0, 1.05)))
    add("tfl", ((0.118, -0.080, 1.022), (0.124, -0.070, 1.025)), ((0.172, -0.040, 0.820), (0.175, -0.025, 0.800)),
        .025, .45, mid=(0.157, -0.066, 0.930), inside=FEMUR)
    # --- thigh: natural volume (the owner's note)
    add("rect_fem", ((0.104, -0.075, 0.985), (0.110, -0.072, 0.985)), ((0.143, -0.060, 0.552), (0.160, -0.060, 0.552)),
        .045, .42, mid=(0.132, -0.100, 0.770), inside=FEMUR, w=.040)
    add("vast_lat", ((0.168, -0.012, 0.865), (0.165, 0.012, 0.700)), ((0.163, -0.055, 0.565), (0.183, -0.022, 0.552)),
        .058, .45, mid=(0.194, -0.035, 0.720), inside=FEMUR)
    add("vast_med", ((0.112, -0.022, 0.800), (0.122, -0.012, 0.620)), ((0.134, -0.058, 0.545), (0.140, -0.050, 0.530)),
        .048, .72, mid=(0.114, -0.056, 0.600), inside=FEMUR)
    add("sartorius", ((0.120, -0.086, 1.020), (0.122, -0.082, 1.018)), ((0.128, -0.022, 0.455), (0.130, -0.015, 0.450)),
        .008, .50, mid=(0.096, -0.084, 0.760), inside=FEMUR, w=.011)
    add("adductors", ((0.024, -0.062, 0.925), (0.052, 0.022, 0.885)), ((0.136, 0.0, 0.780), (0.132, 0.002, 0.585)),
        .060, .32, mid=(0.074, -0.030, 0.800), inside=FEMUR)
    add("gracilis", ((0.020, -0.060, 0.920), (0.024, -0.050, 0.915)), ((0.125, -0.012, 0.470), (0.127, -0.008, 0.465)),
        .007, .50, mid=(0.068, -0.024, 0.700), inside=FEMUR, w=.012)
    add("biceps_fem", ((0.060, 0.046, 0.875), (0.064, 0.044, 0.870)), ((0.188, 0.012, 0.470), (0.192, 0.010, 0.465)),
        .042, .45, mid=(0.152, 0.052, 0.690), inside=FEMUR, w=.032)
    add("semis", ((0.056, 0.042, 0.875), (0.060, 0.040, 0.870)), ((0.122, 0.016, 0.470), (0.128, 0.012, 0.465)),
        .046, .50, mid=(0.100, 0.057, 0.680), inside=FEMUR, w=.034)
    # --- lower leg
    add("gastro_med", ((0.128, 0.022, 0.530), (0.138, 0.025, 0.525)), ((0.198, 0.062, 0.200), (0.205, 0.062, 0.198)),
        .046, .35, mid=(0.152, 0.070, 0.370), inside=TIBIA, w=.032)
    add("gastro_lat", ((0.168, 0.024, 0.530), (0.176, 0.022, 0.525)), ((0.205, 0.062, 0.220), (0.210, 0.060, 0.218)),
        .038, .30, mid=(0.198, 0.060, 0.390), inside=TIBIA, w=.028)
    add("soleus", ((0.165, 0.030, 0.440), (0.198, 0.030, 0.400)), ((0.200, 0.060, 0.130), (0.208, 0.060, 0.130)),
        .030, .45, mid=(0.190, 0.055, 0.280), inside=TIBIA)
    add("achilles", ((0.200, 0.062, 0.200), (0.210, 0.062, 0.200)), ((0.203, 0.068, 0.045), (0.207, 0.068, 0.045)),
        .006, .50, inside=TIBIA, w=.008)
    add("tib_ant", ((0.165, -0.038, 0.440), (0.172, -0.030, 0.400)), ((0.188, -0.025, 0.090), (0.190, -0.020, 0.085)),
        .026, .30, mid=(0.180, -0.046, 0.300), inside=TIBIA, w=.016)
    add("peroneus", ((0.196, 0.000, 0.440), (0.200, 0.005, 0.400)), ((0.232, 0.048, 0.090), (0.234, 0.050, 0.085)),
        .020, .35, mid=(0.218, 0.016, 0.280), inside=TIBIA, w=.012)
    # --- arm (T-pose, palms down, thumbs forward)
    add("biceps", (arm_pt(S, .035, -.005, .024), arm_pt(S, .045, .006, .022)),
        (arm_pt(E, .025, 0, .016), arm_pt(E, .035, 0, .014)), .028, .58, mid=arm_pt(S, .17 * UK, 0, .040), inside=HUMERUS,
        w=.022)
    # the brachialis shows on the OUTSIDE of the arm (up, in the T-pose), between the biceps and the triceps' lateral
    # head below the deltoid's point (written on the front-inside it was under the biceps and drew nothing)
    add("brachialis", (arm_pt(S, .14 * UK, .018, .010), arm_pt(S, .15 * UK, .012, .014)),
        (arm_pt(E, .020, .006, .006), arm_pt(E, .025, .002, .008)), .016, .60, mid=arm_pt(S, .21 * UK, .026, .016),
        inside=HUMERUS, w=.022)
    add("triceps_long", (arm_pt(S, 0, -.030, bk=.020), arm_pt(S, .02, -.032, bk=.020)),
        (arm_pt(E, 0, 0, bk=.024), arm_pt(E, 0, .004, bk=.024)), .024, .45, mid=arm_pt(S, .14 * UK, -.012, bk=.042),
        inside=HUMERUS, w=.020)
    add("triceps_lat", (arm_pt(S, .05 * UK, .016, bk=.022), arm_pt(S, .09 * UK, .018, bk=.022)),
        (arm_pt(E, 0, .008, bk=.024), arm_pt(E, 0, .010, bk=.020)), .022, .42, mid=arm_pt(S, .16 * UK, .012, bk=.040),
        inside=HUMERUS, w=.019)
    add("brachiorad", (arm_pt(E, -.07, .020, .012), arm_pt(E, -.04, .024, .010)),
        (arm_pt(W, 0, 0, .020), arm_pt(W, 0, .004, .020)), .020, .25, mid=arm_pt(E, .06, .012, .032),
        inside=FOREARM_L, w=.018)
    add("extensors", (arm_pt(E, 0, .030), arm_pt(E, .01, .030, bk=.008)),
        (arm_pt(W, 0, .014), arm_pt(W, 0, .013, bk=.012)), .017, .30, mid=arm_pt(E, .09, .030, bk=.006),
        inside=FOREARM_L, w=.020)
    add("flexors", (arm_pt(E, 0, -.032), arm_pt(E, 0, -.030, .008)),
        (arm_pt(W, 0, -.012), arm_pt(W, 0, -.012, .012)), .020, .30, mid=arm_pt(E, .08, -.034, .006),
        inside=FOREARM_L, w=.024)
    # --- neck
    add("scm", ((0.058, 0.025, 1.705), (0.062, 0.032, 1.700)), ((0.012, -0.068, 1.512), (0.040, -0.074, 1.518)),
        .014, .45, mid=(0.045, -0.025, 1.620), inside=((0, 0, 1.5), (0, 0, 1.7)), w=.014)
    return M


class Anatomy:
    def __init__(self, params=None):
        self.p = dict(params or {})
        self.M = muscles()

    def k(self, name, default=1.0):
        return float(self.p.get(name, default))

    def core(self, P):
        """the deep layer: ribcage, belly, pelvis, the neck's core, the long bones with the deep muscles round them"""
        wz = self.k("waist")
        d = superell(P, V(0, .002, 1.335), .150, .126, .118, .168, .17, 2.3)                    # ribcage
        d = smin(d, ell(P, V(0, -.012, 1.115), V(.140 * wz, .098, .12)), .04)                     # belly
        d = smin(d, ell(P, V(0, .010, .99), V(.140, .088, .085)), .04)                             # pelvis
        d = smin(d, capsule(P, V(0, .008, 1.46), V(0, -.004, 1.64), .050), .03)                     # neck
        d = smin(d, capsule(P, V(.105, -.018, .90), K, .050), .03)                                  # thigh's deep core
        d = smin(d, ell(P, K + V(0, .006, .01), V(.050, .046, .040)), .015)                        # knee
        d = smin(d, cone(P, K + V(0, .008, -.03), V(.202, .028, .11), .036, .022), .015)            # shin's core
        d = smin(d, capsule(P, S, E, .032), .02)                                                    # upper arm
        d = smin(d, sphere(P, S, .042), .02)                                                        # shoulder
        d = smin(d, ell(P, E, V(.034, .030, .034)), .012)                                           # elbow
        d = smin(d, cone(P, E, W, .030, .021), .012)                                                # forearm
        return d

    def bones(self, P):
        """bones near the skin: what shows through"""
        d = tube(P, [(.022, -.073, 1.505), (.075, -.085, 1.515), (.135, -.065, 1.530), (.190, -.022, 1.545)],
                 [.010, .009, .0085, .009])                                                   # clavicle
        d = smin(d, ell(P, V(0, -.103, 1.40), V(.018, .008, .10)), .006)                      # sternum
        d = smin(d, tube(P, [(.07, .122, 1.468), (.13, .095, 1.50), (.195, .02, 1.545)], [.007, .007, .008]), .006)
        d = smin(d, sphere(P, C7 + V(0, .003, 0), .012), .004)                                # 7th vertebra
        d = smin(d, tube(P, [tuple(ASIS), (.142, -.05, 1.062), (.152, -.005, 1.078), (.13, .045, 1.07), tuple(PSIS)],
                         [.011, .012, .012, .011, .010]), .008)                              # iliac crest
        d = smin(d, ell(P, V(.150, -.052, .525), V(.022, .012, .025)), .004)                  # kneecap
        d = smin(d, sphere(P, V(.232, .038, .072), .014), .004)                               # ankles
        d = smin(d, sphere(P, V(.188, .022, .088), .014), .004)
        d = smin(d, sphere(P, E + A_UP * .031, .012), .004)                                   # elbow: epicondyles
        d = smin(d, sphere(P, E - A_UP * .031, .013), .004)
        d = smin(d, sphere(P, E + BK * .020, .012), .004)                                     # olecranon
        d = smin(d, sphere(P, W + BK * .012 - A_UP * .004, .010), .003)                       # the ulna's head
        return d

    def hand(self, P):
        """placeholder hand until the hand's own module: palm and digits along the arm, palm down"""
        sc = HAND / .195
        knu = W + A_DIR * .104 * sc
        d = cone(P, W + A_DIR * .012, knu - A_DIR * .012, .028, .034)
        d = smax(d, np.abs((P - W) @ A_UP) - .016, .006)
        for k, (off, L) in enumerate(((-.030, .088), (-.010, .097), (.010, .092), (.029, .074))):
            b = knu + FR * off * -1
            dirn = unit(A_DIR - A_UP * .25)
            d = smin(d, cone(P, b, b + dirn * L * sc, .0095, .0075), .008)
        tb = W + A_DIR * .035 + FR * .030 - A_UP * .010
        d = smin(d, cone(P, tb, tb + unit(A_DIR * .7 + FR * .55 - A_UP * .3) * .075 * sc, .012, .008), .01)
        return d

    def foot(self, P):
        heel = A + V(0, .052, -.050)
        ball = A + V(-.008, -.150, -.062)
        d = cone(P, heel, ball, .032, .040)
        d = smax(d, -(P[:, 2] - .004), .006)
        d = smin(d, cone(P, ball, ball + V(-.004, -.062, -.006), .036, .016), .02)
        d = smin(d, capsule(P, A, heel + V(0, -.01, .03), .036), .02)
        return d

    def head(self, P):
        """a plain head until head.py's is ready: the skull and the jaw"""
        d = ell(P, V(0, -.028, 1.735), V(.076, .099, .112))
        d = smin(d, ell(P, V(0, -.070, 1.655), V(.062, .065, .052)), .03)
        return d

    def fat(self, P):
        x, y, z = np.abs(P[:, 0]), P[:, 1], P[:, 2]
        f = .0028 + .0040 * np.exp(-((z - 1.04) / .07) ** 2) * (y < .02) * np.exp(-((x - .09) / .09) ** 2)
        f = f + .0045 * np.exp(-((z - .93) / .06) ** 2) * (y > .03)                   # buttocks
        f = f + .0020 * np.exp(-((z - 1.10) / .05) ** 2) * np.exp(-((x - .15) / .03) ** 2)   # flanks
        f = f - .0012 * (z < .45) - .0010 * (x > .40)                                 # lean shins, forearms
        return np.maximum(f, .0012)

    POSTURE_Z = [0.0, 0.50, 0.80, 0.95, 1.10, 1.20, 1.38, 1.55, 1.90]
    POSTURE_Y = [0.0, 0.0, -.030, -.045, -.052, -.052, -.030, -.022, -.022]

    def posture(self, P):
        """the body is modelled upright; the sheet stands it with the hips and the chest forward of the ankles"""
        Q = P.copy()
        Q[:, 1] -= np.interp(P[:, 2], self.POSTURE_Z, self.POSTURE_Y).astype(F32)
        return Q

    def __call__(self, P):
        P = self.posture(np.asarray(P, F32))
        Q = P.copy()
        Q[:, 0] = np.abs(Q[:, 0])
        d = self.core(Q)
        # every muscle raises the skin over its footprint; where two meet, the higher wins with a little blend, so a
        # groove stays between them
        h = np.zeros(len(Q), F32)
        for m in self.M:
            h = -smin(-h, -m.raise_(Q), .004)
        d = d - h
        d = smin(d, self.bones(Q), .006)
        d = smin(d, self.hand(Q), .01)
        d = smin(d, self.foot(Q), .012)
        d = smin(d, self.head(P), .03)
        # the rectus' tendinous lines and the linea alba
        x, y, z = Q[:, 0], Q[:, 1], Q[:, 2]
        front = (y < -.06) & (x < .085)
        for zz in (1.170, 1.228, 1.284):
            d = d + .0028 * np.exp(-((z - zz - .006 * x / .08) / .0045) ** 2) * front * (x > .004)
        d = d + .0026 * np.exp(-(x / .0035) ** 2) * front * (z > .98) * (z < 1.31)
        return (d - self.fat(Q)).astype(F32)

    def bounds(self):
        return (V(-.95, -.20, -.01), V(.95, .16, 1.88))

    # --- the anatomy as the skin's forms over a body of the right volume ----------------------------------------
    DEFINITION = .20           # how much of each muscle's bulk shows as its own form on the skin (toned down:
                               # the owner, "not a tank")
    GROOVE = .0034             # how far the skin sinks where no muscle raises it (the separations)
    # how much of that relief the skin shows: with the 8.3 mm floor gone (see detail) every muscle stood its full
    # height, the thighs and calves 11-13 mm (the owner circled the legs: "too bulky"): the body's at a little over
    # half, the legs' lower still (a hero's legs read long and lean under the suit)
    RELIEF, LEG_RELIEF = .55, .44
    LEGS = {"glute_max", "glute_med", "tfl", "rect_fem", "vast_lat", "vast_med", "sartorius", "adductors",
            "gracilis", "biceps_fem", "semis", "gastro_med", "gastro_lat", "soleus", "achilles", "tib_ant",
            "peroneus"}

    def detail(self, P):
        """how far the anatomy moves the skin of a body of the right volume, along its normal (metres): each
        muscle raises its footprint by a share of its bulk, the skin sinks a little between them, the rectus' lines,
        the linea alba, the spine's groove"""
        P = self.posture(np.asarray(P, F32))
        Q = P.copy()
        Q[:, 0] = np.abs(Q[:, 0])
        h = np.zeros(len(Q), F32)
        for m in self.M:
            depth, m.depth = m.depth, .09
            r = m.raise_(Q) * (m.show or self.DEFINITION) * (self.LEG_RELIEF if m.name in self.LEGS else self.RELIEF)
            # a smooth max that blends only where something stands: its radius shrinks with what it blends. A fixed
            # 9 mm radius added up to a quarter of it each time it met nothing: after the 90 muscles the whole skin
            # stood 8.3 mm out, the GROOVE took 3.4 back, and the body carried 4.9 mm everywhere (1 cm on every
            # width and depth: the owner's "too bulky"), its muscles drowned under that floor (soft, undefined)
            k = np.maximum(.009 * np.clip(np.maximum(h, r) / .009, 0, 1), 1e-6)
            h = -smin(-h, -r, k)
            m.depth = depth
        out = h - self.GROOVE * self.k("definition") * self.RELIEF
        x, y, z = Q[:, 0], Q[:, 1], Q[:, 2]
        # the separations are soft valleys a finger wide, never cuts (QC: no two faces of the skin turning more
        # than a few degrees from each other); each fades in and out (switched on and off by a hard bound they
        # ended in a step, buried under the old floor and a crease without it)
        ramp = lambda v: np.clip(v, 0, 1)
        front = ramp((-.06 - y) / .02)
        for zz in (1.170, 1.228, 1.284):
            out -= (.0030 * np.exp(-((z - zz - .006 * x / .08) / .0105) ** 2) * front * ramp((1.30 - z) / .02)
                    * ramp(x / .012) * ramp((.095 - x) / .025))
        out -= .0028 * np.exp(-(x / .0095) ** 2) * front * ramp((z - .98) / .03) * ramp((1.31 - z) / .03)
        out -= (.0028 * np.exp(-(x / .014) ** 2) * ramp((y - .03) / .025) * ramp((z - 1.0) / .04)
                * ramp((1.42 - z) / .06))                                                      # the spine (lumbar)
        out += .0025 * np.exp(-(x / .012) ** 2) * np.exp(-((z - 1.556) / .015) ** 2) * ramp((y - .03) / .025)  # C7
        # the pec's lower edge: from the sternum (1.338) rising to the armpit (1.41 at 16 cm out). It was written
        # .55 (x - .02)^2 / .03, five times as steep: the groove climbed diagonally across the chest to the top of
        # the shoulder (a sawtooth V on the chest, a pit at the shoulder's front corner, a slit under the suit)
        # (then, 2026-11-20: rising steadily from the sternum, 3.6 (x - .02)^2, it was the curve under a breast: a
        # man's runs nearly level to the outer third of the chest and turns up into the armpit only there)
        pz = 1.336 + .05 * x + 8.0 * np.maximum(x - .10, 0) ** 2
        out -= (.0032 * np.exp(-((z - pz) / .0125) ** 2) * ease((-.05 - y) / .02) * np.clip((x - .008) / .015, 0, 1)
                * np.clip((.18 - x) / .02, 0, 1))
        # the separations and the ridges a lean man shows (the owner's sheet: cut, not bulky), drawn as valleys a
        # finger wide along each border and ridges where the bone lies just under the skin (metres, the upright
        # frame the muscles are written in; each fades out over its ends)
        snapped = []
        for pts, amount, width in self.lines():
            # each of the line's points onto the skin itself (the nearest of the body's own vertices): written to a
            # centimetre or two of it, a line a centimetre under the skin drew nothing
            pts = np.asarray(pts, F32)
            far = 0.0
            for i in range(len(pts)):
                d2 = ((Q - pts[i]) ** 2).sum(1)
                j = int(np.argmin(d2))
                far = max(far, float(np.sqrt(d2[j])))
                pts[i] = Q[j]
            snapped.append(far)
            dist, along = seg_dist3(Q, pts)
            n_ = len(pts) - 1
            fade = np.clip(along / .45, 0, 1) * np.clip((n_ - along) / .45, 0, 1)
            out -= amount * np.exp(-(dist / width) ** 2) * fade
        print(f"[orion] separations: {len(snapped)} lines, their points up to {max(snapped) * 1000:.1f} mm off the skin")
        return out

    def lines(self):
        """(polyline, metres down (+) or up (-), half width): the borders between the muscles and the bony ridges"""
        ap = arm_pt
        L = []
        # the chest: the deltopectoral groove from the clavicle's outer third to the armpit's front
        L.append(([(0.120, -0.078, 1.526), (0.150, -0.088, 1.505), (0.180, -0.088, 1.478), (0.205, -0.080, 1.455)], 0.0031, 0.012))
        # the clavicle: a ridge from the notch out to the shoulder
        L.append(([(0.015, -0.072, 1.503), (0.060, -0.080, 1.512), (0.110, -0.080, 1.522), (0.160, -0.062, 1.528)], -0.0012, 0.010))
        # the rectus's outer border (the linea semilunaris), curving in to the pubis
        L.append(([(0.085, -0.104, 1.318), (0.084, -0.108, 1.230), (0.078, -0.104, 1.150), (0.066, -0.096, 1.060),
                   (0.048, -0.086, 0.980)], 0.0025, 0.012))
        # the groin's line from the hip bone to the pubis
        L.append(([(0.120, -0.084, 1.020), (0.085, -0.085, 0.985), (0.050, -0.078, 0.950), (0.028, -0.070, 0.935)], 0.0028, 0.012))
        # the iliac crest: a ridge from the front of the hip bone up and round to the back
        L.append(([(0.120, -0.082, 1.028), (0.145, -0.045, 1.055), (0.158, 0.000, 1.072), (0.140, 0.040, 1.070),
                   (0.100, 0.070, 1.058), (0.050, 0.082, 1.045)], -0.0015, 0.012))
        # under the arm: the lat's front border over the serratus and the obliques
        L.append(([(0.165, 0.040, 1.400), (0.168, 0.015, 1.330), (0.160, -0.010, 1.260), (0.150, -0.030, 1.200)], 0.0022, 0.012))
        # the arm: the biceps and the triceps told apart on its outside and its inside, the brachialis between
        L.append(([ap(S, .10, .030, .008), ap(S, .18, .030, .010), ap(S, .26, .026, .010)], 0.0025, 0.012))
        L.append(([ap(S, .10, -.030, .004), ap(S, .18, -.030, .006), ap(S, .27, -.026, .004)], 0.0020, 0.012))
        # the forearm: the ridge muscles from the elbow told apart from the extensors on its top
        L.append(([ap(E, .04, .022, .010), ap(E, .12, .020, .007), ap(E, .20, .017, .004)], 0.0017, 0.012))
        # the thigh: the rectus femoris between the two vasti, the band down its outside, the hamstrings behind
        L.append(([(0.150, -0.075, 0.860), (0.158, -0.068, 0.760), (0.163, -0.062, 0.660), (0.165, -0.058, 0.580)], 0.0025, 0.012))
        L.append(([(0.100, -0.084, 0.820), (0.108, -0.082, 0.730), (0.117, -0.070, 0.630), (0.126, -0.060, 0.570)], 0.0022, 0.012))
        L.append(([(0.178, -0.020, 0.820), (0.185, -0.018, 0.700), (0.188, -0.020, 0.600)], 0.0020, 0.012))
        L.append(([(0.172, 0.030, 0.820), (0.180, 0.022, 0.700), (0.186, 0.018, 0.590)], 0.0017, 0.012))
        # the calf's two heads, the shin bone's crest
        L.append(([(0.165, 0.058, 0.470), (0.168, 0.068, 0.400), (0.170, 0.068, 0.330)], 0.0025, 0.012))
        L.append(([(0.140, -0.052, 0.455), (0.150, -0.050, 0.350), (0.165, -0.044, 0.230), (0.182, -0.036, 0.120)], -0.0013, 0.009))
        return [([tuple(float(c) for c in p) for p in pts], a, w) for pts, a, w in L]


def seg_dist3(P, pts):
    """the distance from each point to a polyline (metres) and where along it (0..len-1)"""
    best = np.full(len(P), 1e9, F32)
    along = np.zeros(len(P), F32)
    for i in range(len(pts) - 1):
        a, b = np.asarray(pts[i], F32), np.asarray(pts[i + 1], F32)
        ba = b - a
        h = np.clip(((P - a) @ ba) / float(ba @ ba), 0, 1)
        dd = length(P - a - h[:, None] * ba)
        m = dd < best
        best = np.where(m, dd, best)
        along = np.where(m, i + h, along)
    return best, along


def lab_body():
    return Anatomy()
