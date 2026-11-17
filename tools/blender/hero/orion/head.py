"""The new male head (Project Orion), built from zero to the owner's portrait (art/reference/player/
orion_tpose_bodysuit.png, right) and the canon (8 heads: 23 cm from the crown to the chin).

How it is made: the head is SCULPTED as a signed distance field in centimetres, in its own frame
(x to his left, y forward NEGATIVE, z up; x = 0 the midline, y = 0 the ear canal, z = 0 the pupils):

  * the base: horizontal CROSS-SECTIONS of the head every 1-2 cm from the neck to the forehead, each drawn through
    anatomical points (glabella, the orbital rims, the cheekbones, the dental arch, the jaw's angle, the chin, the
    neck's muscles), lofted together (monotone cubics, no overshoot), and above the forehead the vault of the skull;
  * the nose: its profile (nasion, the bony hump, the tip's two domes, the columella, the subnasale) lofted with a
    section that runs from a ridge at the bridge to a round lobule, the alae (wings) and the nostrils;
  * the lips: the upper and lower vermilion swept along the dental arch (the Cupid's bow, the tubercle, the full
    lower lip), the philtrum, the corners tucked in, the slit between them;
  * the eyes: real eyeballs (separate meshes, eye_white / eye_iris) in sockets, the lids a shell draped over them,
    cut along an almond fissure, the crease and the hood of the brow over it, the tear trough under it;
  * the ears: helix, antihelix with its two crura, concha, tragus, antitragus, lobe, standing out from the head;
  * the neck: sternomastoids, the larynx.

Every number is a place on a real head (Farkas' adult norms for a 23 cm head, the portrait's character: a heavy
brow, deep-set eyes, a straight strong nose, full lips, a broad square jaw and a strong chin). Faces differ by the
PARAMS (the customisation), never by editing the shapes.

The world: the pupils at z = 1.73 m, the ear canal at y = -0.034 m (the sheet's profile), metres = cm / 100.
"""
import math
import os
import sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
from sdf import smin, smax, smooth_curve, length  # noqa: E402

F32 = np.float32
Z0, Y0 = 1.73, -0.034            # world metres of the head frame's origin
YC = -0.5                        # the loft's axis (cm): every section is star-shaped round (0, YC)

# ---------------------------------------------------------------------------------------------------------------
# the base head: half cross-sections (x, y) from the front midline round to the back's, at each height z (cm)

SECTIONS = {
    6.0: [(0, -10.1), (2.0, -9.85), (3.8, -9.2), (5.3, -8.0), (6.4, -6.0), (7.0, -3.0), (7.2, .5), (6.9, 4.0),
          (5.6, 6.6), (3.0, 8.0), (0, 8.5)],
    4.0: [(0, -10.6), (2.0, -10.4), (3.8, -9.8), (5.3, -8.6), (6.4, -6.5), (7.1, -3.5), (7.45, .5), (7.2, 4.2),
          (5.8, 6.9), (3.1, 8.3), (0, 8.7)],
    2.3: [(0, -11.2), (1.2, -11.12), (2.4, -10.98), (3.6, -10.72), (4.7, -10.12), (5.6, -8.95), (6.4, -6.7),
          (7.2, -3.6), (7.6, .5), (7.35, 4.2), (5.9, 6.9), (3.1, 8.35), (0, 8.75)],
    1.15: [(0, -10.75), (1.1, -10.45), (2.0, -9.75), (3.2, -9.35), (4.4, -9.4), (5.25, -8.95), (6.1, -7.25),
           (7.0, -4.0), (7.55, .3), (7.35, 4.1), (5.9, 6.8), (3.1, 8.3), (0, 8.7)],
    0.0: [(0, -10.35), (1.0, -9.85), (1.5, -9.15), (2.15, -8.35), (2.95, -8.05), (3.85, -8.15), (4.55, -7.85),
          (5.25, -7.2), (6.25, -5.9), (7.05, -3.2), (7.5, 0.0), (7.3, 4.0), (5.9, 6.7), (3.1, 8.2), (0, 8.6)],
    -1.25: [(0, -10.0), (1.1, -9.75), (2.0, -9.45), (3.0, -9.25), (4.0, -9.05), (4.9, -8.45), (5.7, -7.45),
            (6.5, -5.6), (7.2, -3.0), (7.5, 0.0), (7.2, 3.8), (5.8, 6.5), (3.0, 8.0), (0, 8.4)],
    -2.6: [(0, -10.0), (1.2, -9.95), (2.4, -9.85), (3.7, -9.62), (4.7, -9.1), (5.6, -8.15), (6.5, -6.5),
           (7.15, -4.0), (7.3, -1.0), (7.0, 2.5), (5.4, 5.6), (2.8, 7.2), (0, 7.6)],
    -4.0: [(0, -10.05), (1.4, -10.05), (2.6, -9.75), (3.7, -9.05), (4.7, -8.1), (5.6, -7.0), (6.4, -5.4),
           (6.9, -3.0), (7.0, -.5), (6.6, 2.5), (5.0, 5.0), (2.6, 6.5), (0, 6.9)],
    -5.3: [(0, -10.6), (1.2, -10.6), (2.3, -10.0), (3.4, -9.05), (4.5, -7.95), (5.4, -6.85), (6.2, -5.1),
           (6.7, -3.0), (6.8, -.5), (6.3, 2.3), (4.7, 4.6), (2.4, 5.9), (0, 6.3)],
    -6.6: [(0, -10.45), (1.2, -10.4), (2.3, -9.85), (3.3, -9.0), (4.4, -7.75), (5.35, -6.4), (6.05, -4.7),
           (6.5, -2.6), (6.5, -.4), (5.9, 2.0), (4.4, 4.1), (2.2, 5.4), (0, 5.8)],
    -7.45: [(0, -10.3), (1.2, -10.2), (2.4, -9.55), (3.3, -8.85), (4.4, -7.5), (5.35, -6.1), (6.0, -4.4),
            (6.35, -2.3), (6.3, -.3), (5.7, 1.8), (4.2, 3.8), (2.1, 5.0), (0, 5.4)],
    -8.6: [(0, -10.2), (1.2, -10.08), (2.4, -9.55), (3.4, -8.6), (4.5, -7.1), (5.45, -5.4), (6.0, -3.4),
           (6.1, -1.4), (5.85, .5), (5.0, 2.5), (3.6, 4.0), (1.8, 4.9), (0, 5.2)],
    -9.8: [(0, -10.55), (1.2, -10.35), (2.4, -9.4), (3.5, -8.3), (4.6, -6.6), (5.45, -4.8), (5.85, -3.0),
           (5.85, -1.1), (4.95, 1.0), (4.2, 2.8), (3.0, 4.0), (1.5, 4.7), (0, 4.9)],
    -11.0: [(0, -11.05), (1.0, -10.9), (2.0, -10.35), (3.0, -9.35), (3.95, -7.9), (4.65, -6.2), (5.2, -4.0),
            (5.5, -1.3), (5.25, .9), (4.7, 2.7), (3.4, 3.9), (1.8, 4.6), (0, 4.8)],
    -12.0: [(0, -10.0), (1.0, -9.85), (2.0, -9.35), (3.0, -8.45), (3.8, -7.05), (4.3, -5.0), (5.0, -2.2),
            (5.45, .2), (5.0, 2.3), (3.9, 3.7), (2.0, 4.4), (0, 4.6)],
    -12.8: [(0, -8.4), (1.4, -8.2), (2.6, -7.55), (3.6, -6.45), (4.35, -4.7), (5.0, -2.4), (5.6, 0.0),
            (5.5, 2.0), (4.4, 3.5), (2.2, 4.3), (0, 4.5)],
    -13.9: [(0, -6.0), (1.6, -5.9), (3.0, -5.3), (4.2, -4.15), (5.2, -2.45), (5.9, -.3), (5.85, 1.9), (4.65, 3.5),
            (2.3, 4.3), (0, 4.5)],
    -15.6: [(0, -4.7), (1.4, -4.5), (2.8, -3.95), (4.2, -3.05), (5.4, -1.6), (6.1, .3), (6.0, 2.2), (4.9, 3.8),
            (2.5, 4.7), (0, 4.9)],
    -18.0: [(0, -4.45), (1.5, -4.3), (3.0, -3.75), (4.4, -2.65), (5.6, -.9), (6.3, 1.1), (6.2, 3.0), (5.1, 4.6),
            (2.6, 5.6), (0, 5.8)],
    -21.0: [(0, -4.9), (1.8, -4.7), (3.6, -4.0), (5.2, -2.8), (6.6, -.8), (7.6, 1.6), (7.5, 4.0), (6.0, 6.0),
            (3.0, 7.3), (0, 7.6)],
    -24.0: [(0, -5.6), (2.0, -5.4), (4.0, -4.6), (6.0, -3.0), (7.8, -.6), (9.0, 2.2), (8.8, 5.0), (7.0, 7.2),
            (3.5, 8.6), (0, 9.0)],
}

TH = np.radians(np.linspace(0.0, 180.0, 721))        # the loft's grid round the axis (quarter degrees)
ZG = np.linspace(-24.0, 12.0, 721)                    # and up it (0.05 cm)


def spline(xs, ys, xq):
    """a natural cubic spline through (xs, ys), evaluated at xq (held level past the ends): C2, so a loft through
    it has no flat band at each section the way a monotone cubic's zero slopes at every extremum make"""
    xs, ys = np.asarray(xs, float), np.asarray(ys, float)
    n = len(xs)
    h = np.diff(xs)
    A = np.zeros((n, n)); r = np.zeros(n)
    A[0, 0] = A[-1, -1] = 1.0
    for i in range(1, n - 1):
        A[i, i - 1], A[i, i], A[i, i + 1] = h[i - 1], 2 * (h[i - 1] + h[i]), h[i]
        r[i] = 3 * ((ys[i + 1] - ys[i]) / h[i] - (ys[i] - ys[i - 1]) / h[i - 1])
    c = np.linalg.solve(A, r)
    b = (ys[1:] - ys[:-1]) / h - h * (2 * c[:-1] + c[1:]) / 3
    dd = (c[1:] - c[:-1]) / (3 * h)
    xq = np.clip(np.asarray(xq, float), xs[0], xs[-1])
    i = np.clip(np.searchsorted(xs, xq) - 1, 0, n - 2)
    t = xq - xs[i]
    return ys[i] + b[i] * t + c[i] * t * t + dd[i] * t ** 3


def section_r(pts):
    """a half section's radius round the loft's axis at every TH"""
    th = np.array([math.atan2(x, -(y - YC)) for x, y in pts])
    r = np.array([math.hypot(x, y - YC) for x, y in pts])
    th[0], th[-1] = 0.0, math.pi
    assert np.all(np.diff(th) > 0), "a section must go round the axis one way"
    # mirror a little past both ends so the slope at the midlines is level
    th_ext = np.r_[-th[1:3][::-1], th, 2 * math.pi - th[-3:-1][::-1]]
    r_ext = np.r_[r[1:3][::-1], r, r[-3:-1][::-1]]
    return spline(th_ext, r_ext, TH)


def build_loft(sections=None):
    sections = SECTIONS if sections is None else sections
    zs = sorted(sections)
    rs = np.array([section_r(sections[z]) for z in zs])          # (nz, nth)
    R = np.empty((len(ZG), len(TH)), F32)
    for j in range(len(TH)):
        R[:, j] = spline(np.array(zs), rs[:, j], ZG)
    Rz = np.gradient(R, ZG, axis=0)
    Rt = np.gradient(R, TH, axis=1)
    return R, Rz, Rt


def lerp_grid(G, z, th):
    """bilinear lookup on the (ZG, TH) grid"""
    fz = np.clip(np.nan_to_num((z - ZG[0]) / (ZG[1] - ZG[0])), 0, len(ZG) - 1.001)
    ft = np.clip(np.nan_to_num(th / (TH[1] - TH[0])), 0, len(TH) - 1.001)
    i, j = fz.astype(int), ft.astype(int)
    a, b = fz - i, ft - j
    return ((G[i, j] * (1 - a) + G[i + 1, j] * a) * (1 - b) + (G[i, j + 1] * (1 - a) + G[i + 1, j + 1] * a) * b)


def supershape(Q, c, r_front, r_back, rx, rz_top, rz_bot, n):
    """a superellipsoid with its own half depth front / back and half height up / down: roughly a distance"""
    d = Q - np.asarray(c, F32)
    ry = np.where(d[:, 1] < 0, r_front, r_back)
    rz = np.where(d[:, 2] > 0, rz_top, rz_bot)
    f = ((np.abs(d[:, 0]) / rx) ** n + (np.abs(d[:, 1]) / ry) ** n + (np.abs(d[:, 2]) / rz) ** n) ** (1.0 / n)
    return (f - 1.0) * np.minimum(np.minimum(rx, ry), rz)


def ell(Q, c, r):
    """axis-aligned ellipsoid, roughly a distance"""
    q = (Q - np.asarray(c, F32)) / np.asarray(r, F32)
    k0 = length(q)
    k1 = length(q / np.asarray(r, F32))
    return k0 * (k0 - 1.0) / np.maximum(k1, 1e-6)


def capsule(Q, a, b, r):
    a, b = np.asarray(a, F32), np.asarray(b, F32)
    pa, ba = Q - a, b - a
    h = np.clip((pa @ ba) / (ba @ ba), 0, 1)
    return length(pa - h[:, None] * ba) - r


def tube(Q, pts, radii):
    """a smooth tube through points, radius interpolated (a chain of round cones)"""
    out = None
    for i in range(len(pts) - 1):
        a, b = np.asarray(pts[i], F32), np.asarray(pts[i + 1], F32)
        ra, rb = radii[i], radii[i + 1]
        pa, ba = Q - a, b - a
        L2 = float(ba @ ba)
        h = np.clip((pa @ ba) / L2, 0, 1)
        d = length(pa - h[:, None] * ba) - (ra + (rb - ra) * h)
        out = d if out is None else smin(out, d, .15)
    return out


def smooth_path(pts, radii, k=6):
    """a Catmull-Rom curve through the points (k pieces a span), the radii along it: a tube through the points
    themselves is a chain of straight cones, a polygon wherever the path bends (the ear's rim read as a decagon)"""
    P = np.asarray(pts, float); R = np.asarray(radii, float)
    Pe = np.vstack([2 * P[0] - P[1], P, 2 * P[-1] - P[-2]]); Re = np.r_[2 * R[0] - R[1], R, 2 * R[-1] - R[-2]]
    out, rad = [], []
    for i in range(len(P) - 1):
        p0, p1, p2, p3 = Pe[i:i + 4]; r0, r1, r2, r3 = Re[i:i + 4]
        for j in range(k):
            t = j / k
            w = np.array([-t + 2 * t * t - t ** 3, 2 - 5 * t * t + 3 * t ** 3, t + 4 * t * t - 3 * t ** 3,
                          -t * t + t ** 3]) * .5
            out.append(w[0] * p0 + w[1] * p1 + w[2] * p2 + w[3] * p3)
            rad.append(w[0] * r0 + w[1] * r1 + w[2] * r2 + w[3] * r3)
    out.append(P[-1]); rad.append(R[-1])
    return [tuple(q) for q in out], rad


def tube_smooth(Q, pts, radii, k=6):
    """a round tube along a smooth curve through the points (round cones joined by their union: they share their
    ends and radii, so nothing bulges at the joints)"""
    S, Rr = smooth_path(pts, radii, k)
    out = None
    for i in range(len(S) - 1):
        a, b = np.asarray(S[i], F32), np.asarray(S[i + 1], F32)
        pa, ba = Q - a, b - a
        L2 = max(float(ba @ ba), 1e-9)
        h = np.clip((pa @ ba) / L2, 0, 1)
        d = length(pa - h[:, None] * ba) - (Rr[i] + (Rr[i + 1] - Rr[i]) * h)
        out = d if out is None else np.minimum(out, d)
    return out


def spow(x, p):
    """a power of something that may dip a hair below zero (a float32 sine of pi): never NaN"""
    return np.maximum(x, 0.0) ** p


def smoothstep_np(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def G(x, c, w):
    return np.exp(-0.5 * ((x - c) / w) ** 2)


def curve(xs, ys):
    xs, ys = np.asarray(xs, float), np.asarray(ys, float)
    return lambda t: smooth_curve(xs, ys, np.asarray(t, float))


# ---------------------------------------------------------------------------------------------------------------
# the features

EYE = np.array([3.2, -7.45, 0.1], F32)      # the left eyeball's centre: 6.4 cm between the pupils, deep under the brow
EYE_R = 1.2
# the fissure in the front view (x, z) of the left eye: the canthi, the margins' highest / lowest points
EN = (1.66, 0.02)                             # the inner canthus (3.3 cm between them: a man's, Farkas)
EX = (4.6, 0.22)                              # the outer canthus (a little higher: the male's slight upward tilt)
LID_UP, LID_LO = 0.44, 0.42                   # the margins' rise / fall over the line between the canthi (the upper over the iris's top: no stare)
# the face's landmarks on the midline (z, y), from the owner's portrait: the nose shortish, the mouth high over a
# long, strong chin. The nose and the lips are drawn from these, so moving one moves its whole feature.
NASION = (0.55, -10.35)
TIP = (-3.9, -12.95)                          # the pronasale
SUBNASALE = (-4.65, -11.15)
STOMION_Z = -7.25


class Head:
    Y0, Z0 = Y0, Z0                              # the head frame's origin in the world (metres)

    def __init__(self, params=None):
        self.p = dict(params or {})
        self.anatomy = self.p.get("base", "anatomy") == "anatomy"
        if self.anatomy:
            import headbase
            self.hb = headbase.HeadBase(self.p)
            self.R, self.Rz, self.Rt = build_loft(headbase.sections())
        else:
            self.R, self.Rz, self.Rt = build_loft()
        self.set_landmarks(NASION, TIP, SUBNASALE, STOMION_Z)

    def set_landmarks(self, nasion, tip, subnasale, stomion_z):
        """the nose's and the lips' curves from the midline's landmarks"""
        (zn, yn), (zt, yt), (zs, ys) = nasion, tip, subnasale
        self.nasion, self.tip, self.subn, self.stom_z = nasion, tip, subnasale, stomion_z
        # the dorsum: nasion to tip with the bony hump 40 % down it, then the supratip, the tip, the infratip lobule,
        # the columella back to the subnasale
        f = np.array([0.0, .2, .4, .6, .78, .9])
        g = np.array([0.0, .15, .37, .57, .76, .885])
        zd = zn + (zt - zn) * f
        yd = yn + (yt - yn) * g - np.array([0, .03, .09, .05, 0, 0])
        zz = list(zd) + [zt, zt - .33, zt - .62, zs + .14, zs]
        yy = list(yd) + [yt, yt + .2, yt + .62, ys - .55, ys]
        order = np.argsort(zz)
        self.n_prof = curve(np.array(zz)[order], np.array(yy)[order])
        # half width up the nose: the alae at its base, the tip's lobule, the narrow bony bridge, wider at the root
        L = zn - zs
        s_ = np.array([0.0, .07, .16, (zt - zs) / L, (zt - zs) / L + .12, .45, .68, .88, 1.0])
        w_ = np.array([1.55, 1.80, 1.62, 1.30, 1.18, 1.08, 1.08, 1.16, 1.35])
        self.n_half = curve(zs + s_ * L, w_)
        self.n_pow = curve(zs + np.array([0.0, .15, .3, .5, 1.0]) * L, [2.6, 2.4, 2.1, 1.8, 1.8])
        # the underside: the sills rising from the subnasale to the tip's lowest point (rising y)
        self.n_floor = curve([yt - .2, yt + .2, yt + .7, ys - .9, ys - .35, ys + .2],
                             [zt - .45, zt - .62, zt - .82, zs + .12, zs + .04, zs])
        # the mouth: the stomion level with a touch of a downturn, the Cupid's bow, the lower lip's border
        st = stomion_z
        self.stom = curve([0, 1.0, 2.0, 2.65], [st, st - .02, st - .06, st - .14])
        self.up_top = curve([0, .3, .6, 1.0, 1.6, 2.2, 2.65],
                            [st + .9, st + .96, st + 1.03, st + .97, st + .74, st + .38, st - .1])
        self.lo_bot = curve([0, 1.0, 1.8, 2.3, 2.65], [st - 1.1, st - 1.06, st - .85, st - .52, st - .16])
        # the lips' midline profile: heights from the subnasale to the stomion scaled to this face's upper lip
        span = zs - st
        up_z = st + span * np.array([1.0, .76, .58, .42, .385, .33, .2, .08, .02])
        up_d = [0.0, .05, .12, .17, .16, .25, .33, .29, .13]
        lo_z = st - np.array([0.0, .1, .3, .6, .9, 1.1, 1.3, 1.63, 2.03])
        lo_d = [.03, .13, .36, .47, .41, .25, .15, .05, 0.0]
        self.LIP_Z = list(up_z) + list(lo_z)
        self.LIP_D = up_d + lo_d
        self.arch = lambda x: (ys + .45) + .22 * x * x + .022 * x ** 4

    def k(self, name, default=1.0):
        return float(self.p.get(name, default))

    # --- the base -------------------------------------------------------------------------------------------
    def base(self, Q):
        x, y, z = np.abs(Q[:, 0]), Q[:, 1], Q[:, 2]
        dy = -(y - YC)
        th = np.arctan2(x, dy)
        r = np.sqrt(x * x + dy * dy)
        zc = np.clip(z, ZG[0], ZG[-1])
        R = lerp_grid(self.R, zc, th)
        Rz = lerp_grid(self.Rz, zc, th)
        Rt = lerp_grid(self.Rt, zc, th)
        d = (r - R) / np.sqrt(1 + Rz * Rz + (Rt / np.maximum(r, 1.0)) ** 2)
        # the vault of the skull above the forehead
        vault = supershape(Q, (0, -.2, 2.6), 9.2, 10.4, 8.0, 8.5, 12.0, 2.55) if self.anatomy else             supershape(Q, (0, -.9, 2.8), 9.55, 9.5, 7.55, 8.2, 12.0, 2.25)
        if self.anatomy:                            # the measured sections run up to the crown (headbase.py)
            import headbase
            return smax(d, z - headbase.CROWN_Z, .3)
        t = np.clip((z - 4.6) / 1.6, 0, 1)
        t = t * t * (3 - 2 * t)
        return d * (1 - t) + vault * t

    # --- the nose -------------------------------------------------------------------------------------------
    def nose(self, Q):
        x, y, z = np.abs(Q[:, 0]), Q[:, 1], Q[:, 2]
        zc = np.clip(z, self.subn[0] - .45, self.nasion[0] + .25)
        yp = self.n_prof(zc)
        b = self.n_half(zc) * self.k("nose_width")
        n = self.n_pow(zc)
        yb = np.full_like(yp, -8.9)
        h = yb - yp
        f = ((x / b) ** n + (np.clip(yb - y, 0, None) / h) ** n) ** (1 / n)
        d = (f - 1) * np.minimum(b, h) * .8
        d = np.where(y > yb, np.maximum(d, y - yb), d)
        # the loft's ends: into the brow at the top, flat underneath at the base (the nostrils' sills)
        d = smax(d, z - (self.nasion[0] + .25), .6)
        floor = -(z - self.n_floor(np.clip(y, self.tip[1] - .2, self.subn[1] + .2)))
        d = smax(d, floor, .14)
        # the tip's two domes catch the light: a touch fuller either side of the midline
        zt, yt = self.tip
        zs, ys = self.subn
        d = smin(d, ell(np.c_[x, y, z], (.36, yt + .37, zt + .03), (.30, .28, .33)), .26)
        # the alar groove: where the wing meets the tip's lobule, curving up and back from the nostril's rim
        u = (x - 1.18) / .62
        v = (z - (zs + .18)) / .62
        r = np.sqrt(u * u + v * v)
        groove = np.exp(-((r - 1.0) / .17) ** 2) * (v > -.35) * G(y, ys - .8, .7)
        d = d + .07 * groove
        # the nostrils: openings under the tip, running back and up
        ny = ys - .95
        nos = ell(np.c_[x, y, z], (.58, ny, float(self.n_floor(np.array([ny]))[0]) - .02), (.30, .62, .30))
        d = smax(d, -nos, .10)
        return d

    def alar_crease(self, Q):
        """the groove round the ala where it meets the cheek and the lip"""
        x, y, z = np.abs(Q[:, 0]), Q[:, 1], Q[:, 2]
        u = (x - 1.0) / .88                                   # round the wing where it is now (headbase.NOSE_ALA)
        v = (z + 4.3) / .56
        r = np.sqrt(u * u + v * v)
        return np.exp(-((r - 1.0) / .26) ** 2) * (x > 1.0) * G(y, -10.35, .6)    # a soft fold, not a cut line

    # --- the lips -------------------------------------------------------------------------------------------
    def lips(self, Q):
        """how far the lips push the face out at each point: the midline's profile, its heights scaled at every x
        to that x's vermilion (narrowing to nothing at the corners), its depth fading there"""
        x, y, z = np.abs(Q[:, 0]), Q[:, 1], Q[:, 2]
        xc = np.clip(x, 0, 2.62)
        u = np.clip(x / 2.75, 0, 1)
        st, top, bot = self.stom(xc), self.up_top(xc), self.lo_bot(xc)
        st0 = self.stom_z
        top0, bot0 = float(self.up_top(np.array([0.0]))[0]), float(self.lo_bot(np.array([0.0]))[0])
        above = (z - st) * ((top0 - st0) / np.maximum(top - st, .04))
        below = (z - st) * ((st0 - bot0) / np.maximum(st - bot, .04))
        zl = np.clip(st0 + np.where(z > st, above, below), min(self.LIP_Z), max(self.LIP_Z))
        o = np.argsort(self.LIP_Z)
        prof = np.clip(spline(np.array(self.LIP_Z)[o], np.array(self.LIP_D)[o], zl), 0, None)
        fade = spow(1 - u ** 2.4, .6) * (x < 2.9)
        front = smoothstep_np(-7.4, -9.0, y)                           # only on the face's front
        # the white roll: a fine ridge along each vermilion's border
        roll = .045 * (np.exp(-((z - top) / .07) ** 2) + .8 * np.exp(-((z - bot) / .08) ** 2)) * fade
        # the philtrum: two columns from under the nose to the bow's peaks, the groove between them
        zs = self.subn[0]
        tz = np.clip((zs - z) / max(zs - float(self.up_top(np.array([0.0]))[0]), .1), 0, 1)
        colx = .32 + .26 * tz
        phil = (.07 * np.exp(-((x - colx) / .13) ** 2) - .04 * np.exp(-(x / .2) ** 2)) * (z < zs - .1) * (z > top - .05)
        return (prof * self.k("lips") * fade + roll + phil) * front

    def mouth_slit(self, Q):
        """the line the lips meet on: through the lips only (it ran on past the corners into the cheek), thinning
        into each corner"""
        x, y, z = np.abs(Q[:, 0]), Q[:, 1], Q[:, 2]
        import headbase as HB
        W = HB.MOUTH_W * self.k("mouth_width")
        u = np.clip(x / W, 0, 1.2)
        st = self.stom(np.clip(x, 0, W))
        slab = np.abs(z - st) - (.015 + .015 * np.clip(1 - u ** 4, 0, 1))      # a line the mesh can hold (thinner broke into dashes)
        slab = np.maximum(slab, y - (-10.2 + 1.1 * u * u))
        slab = np.maximum(slab, x - (W - .1))
        return slab

    # --- the eyes -------------------------------------------------------------------------------------------
    def fissure(self, x, z):
        """signed: negative inside the left eye's opening (front view)"""
        u = (x - EN[0]) / (EX[0] - EN[0])
        uc = np.clip(u, 0, 1)
        z0 = EN[1] + (EX[1] - EN[1]) * uc
        up = z0 + LID_UP * self.k("eye_open") * spow(np.sin(np.pi * uc ** .82), .85)
        lo = z0 - LID_LO * self.k("eye_open") * spow(np.sin(np.pi * uc ** 1.28), 1.05)
        mid = .5 * (up + lo)
        half = .5 * (up - lo)
        dz = np.abs(z - mid) - half
        dx = np.maximum(-u, u - 1) * (EX[0] - EN[0])
        return np.maximum(dz, dx), up, lo

    def eyes(self, Q, d):
        x, y, z = np.abs(Q[:, 0]), Q[:, 1], Q[:, 2]
        P = np.c_[x, y, z]
        near = length(P - EYE) < 3.2
        if not near.any():
            return d
        dn = d[near]
        Pn = P[near]
        xn, yn, zn = Pn[:, 0], Pn[:, 1], Pn[:, 2]
        fis, up, lo = self.fissure(xn, zn)
        # the lids: a shell wrapped close round the globe's front (its inside a hair off the cornea, so the
        # margins rest on the eye and the cornea shows only through the opening), thicker over the top, its
        # outer corner reaching round the globe's side
        L = Pn - EYE
        rq = length(L / np.array([1.0, 1.0, .96], F32))
        thick = .15 + .08 * np.clip((zn - up) / .6, 0, 1) + .04 * np.clip((lo - zn) / .6, 0, 1)
        lid = np.abs(rq - (EYE_R + .2 + thick)) - thick
        lid = np.where(yn > EYE[1] + .35, np.maximum(lid, yn - (EYE[1] + .35)), lid)
        # cut along the fissure: the margins' edges are the lid's own thickness
        lid = smax(lid, -fis, .035)
        dn = smin(dn, lid, .28)
        # the crease over the upper lid and the hood of the brow's skin coming down over it, more on the outside
        u = np.clip((xn - EN[0]) / (EX[0] - EN[0]), 0, 1)
        cz = up + .55 - .12 * u ** 2
        crease = np.exp(-((zn - cz) / .11) ** 2) * spow(np.sin(np.pi * u), .6) * (yn < EYE[1] - .55)
        dn = dn + .04 * crease * self.k("crease")
        hood = np.exp(-((zn - (cz + .18)) / .22) ** 2) * spow(np.sin(np.pi * np.clip(u * .9 + .12, 0, 1)), 1.2)
        dn = dn - .05 * hood * self.k("hood") * (yn < EYE[1] - .95)
        # under the lower lid: the lid's lower edge and the tear trough running down and out from the inner corner
        lz = lo - .55 + .1 * u
        dn = dn + .022 * np.exp(-((zn - lz) / .08) ** 2) * spow(np.sin(np.pi * u), .7)
        tt = np.exp(-(((zn - EYE[2] + 1.25) + .35 * (xn - EN[0] - .34)) / .22) ** 2) * G(xn, EN[0] + .54, .6)
        dn = dn + .06 * tt * self.k("tear_trough")
        # round the globe's sides the socket is closed (the conjunctiva: through the corners of a 3 cm opening
        # the 2.4 cm globe's side is seen, and past it the empty socket was a black hole at the outer corner)
        dn = smin(dn, np.maximum(length(Pn - EYE) - (EYE_R + .3), (EYE[1] - .35) - yn), .15)
        # the globe sits in its socket: nothing of the head inside it
        globe = length(Pn - EYE) - (EYE_R + .025)
        dn = smax(dn, -globe, .05)
        # the inner corner's caruncle
        dn = smin(dn, length(Pn - np.array([EN[0] + .2, EYE[1] - .76, EN[1] - .01], F32)) - .16, .08)
        out = d.copy()
        out[near] = dn
        return out

    # --- the ears -------------------------------------------------------------------------------------------
    def ear(self, Q):
        """the left ear in its own frame: s back along it, t up it, w out of its plane; mirrored"""
        P = np.c_[np.abs(Q[:, 0]), Q[:, 1], Q[:, 2]]
        o = np.array([7.05, 0.15, -1.6], F32)                 # the canal's opening
        EARS = 1.0 / 1.06                                         # a man's ear, 6.7 cm long
        tilt, out = math.radians(17), math.radians(19)
        # the ear's axes: up its length (tilted back), back across it, out of it (turned forward)
        a_t = np.array([0, math.sin(tilt), math.cos(tilt)], F32)
        n0 = np.array([1, 0, 0], F32)
        a_s = np.cross(a_t, n0); a_s /= np.linalg.norm(a_s)            # back (+y)
        c, s_ = math.cos(out), math.sin(out)
        a_w = n0 * c - a_s * s_                                         # out, and a little forward
        a_s2 = a_s * c + n0 * s_                                        # back, and out (the shell leans off the head)
        near = length(P - o) < 6.5
        full = np.full(len(P), 10.0, F32)
        if not near.any():
            return full
        P = P[near]
        d3 = P - o
        s = (d3 @ a_s2) * EARS
        t = (d3 @ a_t) * EARS
        w = (d3 @ a_w) * EARS
        L = np.c_[s, t, w]
        # the auricle: a thin shell of an oval, thicker at its rim, its back on the head at the front
        oval = ell_2d(s - 1.55, t - .25, 1.75, 3.15)
        plate = np.maximum(np.maximum(oval, np.abs(w - .55) - .42), .1 - s)
        d = plate
        # the helix: a rolled rim from the crus over the top and down the back to the lobe
        hel = [(.25, 1.0, .55), (.55, 2.35, .75), (1.4, 3.3, .85), (2.45, 3.05, .95), (3.15, 2.0, 1.0),
               (3.25, .6, 1.0), (2.95, -.9, .95), (2.35, -2.05, .85)]
        d = smin(d, tube_smooth(L, hel, [.17, .24, .30, .31, .31, .30, .27, .22]), .12)
        # the lobe: soft, full, at the bottom
        d = smin(d, ell(L, (1.35, -2.45, .62), (.95, .78, .36)), .3)
        # the scapha: the groove inside the helix
        sca = tube_smooth(L, [(1.0, 2.75, 1.1), (2.05, 2.75, 1.2), (2.7, 1.8, 1.25), (2.75, .5, 1.22), (2.45, -.8, 1.1)],
                   [.16, .2, .22, .2, .16])
        d = smax(d, -sca, .1)
        # the antihelix and its crura
        anti = tube_smooth(L, [(1.55, -1.55, .95), (2.0, -.4, 1.0), (2.15, .75, 1.0), (1.95, 1.6, .98), (1.5, 2.35, .9)],
                    [.2, .25, .26, .23, .18])
        d = smin(d, anti, .15)
        d = smin(d, tube_smooth(L, [(2.0, 1.25, .98), (1.25, 1.55, .9), (.65, 1.4, .82)], [.19, .17, .14]), .12)
        # the concha: the bowl in front of the antihelix, down to the canal
        con = ell(L, (.9, -.2, 1.2), (.92, 1.05, .62))
        d = smax(d, -con, .18)
        d = smax(d, -ell(L, (1.15, 1.35, 1.12), (.55, .32, .35)), .08)    # the triangular fossa
        # tragus and antitragus
        d = smin(d, ell(L, (-.05, -.25, .78), (.32, .55, .3)), .14)
        d = smin(d, ell(L, (1.45, -1.55, .92), (.36, .3, .28)), .12)
        # the canal
        d = smax(d, -capsule(L, (.35, -.25, .9), (.25, -.15, -.5), .3), .1)
        full[near] = d / EARS
        return full

    # --- the neck -------------------------------------------------------------------------------------------
    def neck_detail(self, Q, d):
        x, y, z = np.abs(Q[:, 0]), Q[:, 1], Q[:, 2]
        P = np.c_[x, y, z]
        # the larynx, the sternomastoids from behind the ear to the notch
        lar = ell(P, (0, -4.35, -15.0), (1.1, .8, 1.5))
        d = smin(d, lar, .8)
        return d

    # --- the masses on the skull: soft blobs that push the skin out (+) or let it sink (-), cm --------------------
    # (centre, half sizes, amount, the customisation key that scales it)
    MASSES = [
        ((4.3, -9.2, -2.3), (1.55, 1.0, 1.15), .32, "cheekbones"),        # the malar mass on the cheekbone
        ((6.3, -6.3, -1.6), (.75, 1.9, .6), .14, "cheekbones"),           # the zygomatic arch running back
        ((6.45, -5.6, 2.3), (.9, 1.5, 1.3), -.16, "temples"),              # the temple's hollow
        ((5.1, -7.2, -5.3), (1.0, 1.1, 1.3), -.22, "cheek_hollow"),        # the hollow under the cheekbone
        ((6.05, -3.0, -7.0), (.8, 1.9, 2.3), .20, "jaw"),                  # masseter on the ramus
        ((0.0, -10.95, -10.6), (1.4, .8, 1.0), .12, "chin"),               # the chin's pad
        ((1.5, -10.7, -11.4), (.6, .6, .55), .10, "chin"),                 # its corners
        ((3.15, -10.95, 1.75), (1.9, .75, .5), .34, "brow"),               # the brow's ridge, low over the eye
        ((0.0, -11.3, 1.55), (.85, .6, .7), .14, "brow"),                  # glabella
        ((3.0, -10.1, 5.0), (1.8, 1.0, 1.8), .12, "forehead"),             # the frontal eminences
        ((2.6, -10.2, -5.6), (.85, .7, 1.35), .14, "cheeks"),              # the cheek beside the nasolabial fold
    ]

    def jawline(self, Q):
        """the mandible's lower border as one clean ridge from the chin round the angle and up the ramus's back,
        the soft shadow under it"""
        P = np.c_[np.abs(Q[:, 0]), Q[:, 1], Q[:, 2]]
        pts = np.array([(1.6, -10.4, -11.8), (3.2, -8.5, -11.3), (4.7, -6.0, -10.9), (5.8, -3.1, -10.45),
                        (6.1, -1.5, -10.15), (6.0, -.5, -8.2)], F32)
        best = np.full(len(P), 1e9, F32)
        along = np.zeros(len(P), F32)
        for i in range(len(pts) - 1):
            a, b = pts[i], pts[i + 1]
            ba = b - a
            h = np.clip(((P - a) @ ba) / float(ba @ ba), 0, 1)
            dd = length(P - a - h[:, None] * ba)
            m = dd < best
            best = np.where(m, dd, best)
            along = np.where(m, i + h, along)
        w = np.clip(along / 1.2, 0, 1) * np.clip((len(pts) - 1 - along) / .8, 0, 1)
        return .16 * np.exp(-(best / .45) ** 2) * w * self.k("jaw")

    def masses(self, Q):
        P = np.c_[np.abs(Q[:, 0]), Q[:, 1], Q[:, 2]]
        out = np.zeros(len(P), F32)
        for c, r, a, key in self.MASSES:
            q = (P - np.asarray(c, F32)) / np.asarray(r, F32)
            out += a * self.k(key) * np.exp(-(q * q).sum(1))
        return out

    # --- all of it ------------------------------------------------------------------------------------------
    def cm(self, Q):
        d = self.base(Q)
        if self.anatomy:                            # the anatomical base's soft forms (headbase.py)
            d = self.hb.relief(Q, d)
        else:
            d = d - self.masses(Q) - self.jawline(Q)
        x, y, z = np.abs(Q[:, 0]), Q[:, 1], Q[:, 2]
        # the nasolabial fold: from beside the ala down and out past the mouth's corner
        fa, fb = np.array([1.95, -4.95]), np.array([3.45, -8.3])
        t = np.clip(((x - fa[0]) * (fb[0] - fa[0]) + (z - fa[1]) * (fb[1] - fa[1])) / ((fb - fa) ** 2).sum(), 0, 1)
        dist = np.sqrt((x - fa[0] - t * (fb[0] - fa[0])) ** 2 + (z - fa[1] - t * (fb[1] - fa[1])) ** 2)
        fold = np.exp(-(dist / .32) ** 2) * spow(np.sin(np.pi * np.clip(t * .95 + .05, 0, 1)), .5) * (y < -8.5)
        d = d + .05 * fold * self.k("nasolabial")
        if self.anatomy:
            import headbase as HB
            d = smin(d, HB.nose(Q, self.k), .42)
            d = d + .03 * self.alar_crease(Q)
            lp, _, _ = HB.lips(Q, self.stom_z, self.k)
            d = smin(d, lp, .3)
        else:
            d = smin(d, self.nose(Q), .48)
            d = d + .085 * self.alar_crease(Q)
            d = d - self.lips(Q)
        d = smax(d, -self.mouth_slit(Q), .04)
        # the corners of the mouth tucked in, the modiolus beside each
        d = d + .08 * np.exp(-(((x - 2.65) / .26) ** 2 + ((z + 7.4) / .22) ** 2)) * (y < -8)
        d = d - .05 * np.exp(-(((x - 3.08) / .45) ** 2 + ((z + 7.35) / .5) ** 2)) * (y < -8)
        d = self.eyes(Q, d)
        d = smin(d, self.ear(Q), .35)
        if not self.anatomy:
            d = self.neck_detail(Q, d)
        return d

    # --- the world ------------------------------------------------------------------------------------------
    def __call__(self, P):
        Q = np.empty_like(np.asarray(P, F32))
        Q[:, 0] = P[:, 0] * 100
        Q[:, 1] = (P[:, 1] - Y0) * 100
        Q[:, 2] = (P[:, 2] - Z0) * 100
        return (self.cm(Q) / 100).astype(F32)

    def bounds(self):
        return (np.array([-.095, Y0 - .15, Z0 - .245], F32), np.array([.095, Y0 + .105, Z0 + .118], F32))

    def focus(self):
        return (0.0, Y0 - .06, Z0 - .02)

    def extras(self):
        """the eyeballs: a globe and its clear cornea, each eye, as small meshes for the lab"""
        out = []
        for sx in (1, -1):
            V, Fq = uv_sphere(32, 20)
            C = EYE.copy(); C[0] *= sx
            Vg = V * EYE_R
            # the cornea's bulge over the iris
            fwd = -Vg[:, 1]
            bulge = np.clip((fwd - .95) / .25, 0, 1) ** 1.5 * .24
            Vg[:, 1] -= bulge
            W = (Vg + C) / 100.0
            W[:, 1] += Y0; W[:, 2] += Z0
            out.append((f"eye_{'L' if sx > 0 else 'R'}", (W.astype(F32), Fq, (.85, .82, .78, 1))))
        return out


def ell_2d(dy, dz, ry, rz):
    """an ellipse in the (y, z) plane, roughly a distance"""
    q0 = np.sqrt((dy / ry) ** 2 + (dz / rz) ** 2)
    q1 = np.sqrt((dy / ry ** 2) ** 2 + (dz / rz ** 2) ** 2)
    return q0 * (q0 - 1.0) / np.maximum(q1, 1e-6)


def uv_sphere(nu, nv):
    V, F = [], []
    for j in range(1, nv):
        ph = math.pi * j / nv
        for i in range(nu):
            th = 2 * math.pi * i / nu
            V.append((math.sin(ph) * math.cos(th), -math.cos(ph), math.sin(ph) * math.sin(th)))
    V.append((0, -1, 0)); V.append((0, 1, 0))
    n = nu
    for j in range(nv - 2):
        for i in range(nu):
            a, b = j * n + i, j * n + (i + 1) % n
            F.append((a, b, b + n, a + n))
    top, bot = len(V) - 2, len(V) - 1
    for i in range(nu):
        F.append((top, (i + 1) % n, i))
        F.append((bot, (nv - 2) * n + i, (nv - 2) * n + (i + 1) % n))
    return np.array(V, F32), F


def lab_head():
    return Head()
