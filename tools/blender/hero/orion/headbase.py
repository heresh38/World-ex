"""The head's ANATOMY (Project Orion male): the base form the face's features (head.py: the nose, the lips, the lids,
the ears) are laid on.

Every horizontal section of the head, from the neck's base to the forehead, is one smooth closed curve drawn from
a few anatomical measures at that height: how far forward the face reaches on the midline, how wide the head is
and where (front to back) it is widest, how far back it reaches, and how round its front and back are (a
superellipse's exponent each). The measures run as smooth curves up the head (an adult man's, Farkas' norms, on
the owner's portrait: a heavy brow over deep-set eyes, strong cheekbones, a broad jaw, a strong chin), so the face
turns round its front as a face does and the jaw goes into the neck through the soft fall under it: no plane, no
box, no ledge (the first head, lofted through hand-drawn points, read as a mask with a box jaw on a post).
Over that: the orbits the eyes sit deep in, the brow's ridge over each, the cheekbones, the mandible's border and
angle, the masseter, the temples' hollows, the sternomastoids and the larynx, each a soft form, and above the
forehead the vault of the skull (head.py).

Frame (head.py's): centimetres, x to his left (the left side is modelled, the right is its mirror), y forward
NEGATIVE, z up; y = 0 the ear canal, z = 0 the pupils.
"""
import math
import os
import sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
from sdf import smin, smax, length, smooth_curve  # noqa: E402

F32 = np.float32

# the measures up the head (cm): z, the midline's front (y), the half width, where it is widest (y), the back (y),
# the front's and the back's roundness (2 = an ellipse, more = squarer)
MEASURES = np.array([
    # z      front    half w   widest   back    n front  n back
    [-23.55, -5, 8.1, 2.244, 8.887, 2, 2.1],
    [-19.55, -4.05, 6.45, 2.045, 7.94, 2, 2.1],
    [-16.55, -3.861, 5.95, 1.952, 7.566, 2, 2.1],
    [-14.55, -4.35, 5.85, 1.5, 7.439, 1.9, 1.95],
    [-13.55, -5, 5.85, 1.3, 7.414, 1.75, 1.9],
    [-12.85, -6.2, 5.88, 1.1, 7.402, 1.4, 1.9],
    [-12.25, -9, 5.966, 0.9, 7.408, 1.3, 1.92],
    [-11.57, -10.05, 5.902, 0.55, 7.414, 1.45, 1.97],
    [-10.66, -10.65, 5.898, -0.05, 7.449, 1.85, 2.05],
    [-10.05, -10.72, 6.117, -0.75, 7.502, 1.98, 2.15],
    [-9.354, -10.45, 6.386, -1.35, 7.569, 2.08, 2.2],
    [-8.462, -10.35, 6.53, -1.7, 7.688, 2.08, 2.25],
    [-7, -10.92, 6.655, -2.3, 7.98, 2.08, 2.3],
    [-6, -11.02, 6.85, -2.55, 8.25, 2.12, 2.3],
    [-5, -10.98, 7.1, -2.8, 8.55, 2.2, 2.3],
    [-4, -10.05, 7.3, -3.2, 8.95, 2.26, 2.3],
    [-3, -9.65, 7.48, -3.6, 9.4, 2.32, 2.3],
    [-2, -9.35, 7.6, -3.8, 9.75, 2.36, 2.3],
    [-1, -9.05, 7.625, -3.7, 9.9, 2.36, 2.3],
    [0, -9.1, 7.601, -3.2, 9.95, 2.3, 2.3],
    [0.8, -9.65, 7.727, -2.4, 10, 2.2, 2.3],
    [1.8, -10.55, 8.037, -1.2, 10.05, 2.08, 2.3],
    [2.6, -10.75, 8.213, 0.4, 10.05, 2.02, 2.2],
    [3.6, -10.45, 8.15, 0.85, 10, 2, 2.15],
    [4.6, -10.02, 8.03, 1.05, 9.88, 1.99, 2.12],
    [5.6, -9.52, 7.95, 1.15, 9.7, 1.99, 2.1],
    [6.557, -8.95, 7.66, 1.15, 9.42, 1.99, 2.08],
    [7.486, -8.25, 7.2, 1.12, 8.93, 1.98, 2.06],
    [8.414, -7.38, 6.45, 1.08, 8.28, 1.97, 2.05],
    [9.343, -6.22, 5.42, 1.02, 7.4, 1.96, 2.04],
    [10.09, -4.95, 4.38, 0.96, 6.32, 1.96, 2.03],
    [10.64, -3.55, 3.22, 0.9, 5.1, 1.97, 2.02],
    [11.01, -2.25, 2.18, 0.86, 3.92, 1.98, 2.02],
    [11.2, -1.3, 1.45, 0.84, 3, 2, 2],
    [11.32, -0.62, 0.86, 0.82, 2.28, 2, 2],
    [11.40, -0.72, 0.50, 0.40, 1.55, 2, 2],   # the dome closed to its top round the loft's axis (y -.5): the
    [11.45, -0.64, 0.20, 0.05, 0.72, 2, 2],   # sections stopped 1.7 x 2.9 cm wide and a cap flattened what was left
])                                            # into a disc the hair stacked on
CROWN_Z = 11.47                   # the cap: at the top itself, blended wide


_TABLE = {}


def _smoothed():
    """the measures on a fine even grid, each smoothed up the head (a Gaussian of half a centimetre; under a quarter
    round the jaw, whose underside is a turn: smoothed wide it was a slope down to the throat, a double chin), so no
    section steps from the next: a measure that changes fast between two rows rang round the neck as creases. The
    ends are padded by reflection (a constant pad made the top fatter than its measures)"""
    if "zz" not in _TABLE:
        zs = MEASURES[:, 0]
        zz = np.arange(zs[0], zs[-1] + 1e-6, .05)
        n = 60

        def smooth(v, sig):
            k = np.exp(-.5 * (np.arange(-n, n + 1) * .05 / sig) ** 2); k /= k.sum()
            vp = np.r_[2 * v[0] - v[n:0:-1], v, 2 * v[-1] - v[-2:-n - 2:-1]]
            return np.convolve(vp, k, mode="same")[n:-n]

        jaw = np.clip((zz + 14.6) / .8, 0, 1) * np.clip((-8.6 - zz) / .8, 0, 1)
        jaw = jaw * jaw * (3 - 2 * jaw)
        cols = []
        for c in range(1, 7):
            v = np.interp(zz, zs, MEASURES[:, c])
            cols.append(smooth(v, .5) * (1 - jaw) + smooth(v, .22) * jaw if c in (1, 5) else smooth(v, .5))
        _TABLE["zz"], _TABLE["cols"] = zz, cols
    return _TABLE["zz"], _TABLE["cols"]


def measures(z):
    zz, cols = _smoothed()
    q = np.atleast_1d(np.asarray(z, float))
    return [np.interp(q, zz, c) for c in cols]


def _round_tip(xs, ys, xr):
    """the quadrant within xr of the midline as a parabola tangent to it at xr: a superellipse under 2 comes to a
    point on the midline (its curvature runs to infinity there), a crease down the chin and the throat"""
    if xr <= 1e-3 or xs[-1] <= 2 * xr:
        return ys
    h = .02 * xr
    yr = float(np.interp(xr, xs, ys))
    k = (float(np.interp(xr + h, xs, ys)) - float(np.interp(xr - h, xs, ys))) / (2 * h)
    a = k / (2 * xr)
    m = xs < xr
    ys = ys.copy()
    ys[m] = yr + a * (xs[m] ** 2 - xr * xr)
    return ys


def section(z, n=40):
    """the half section at height z: points (x, y) from the front midline round the side to the back midline"""
    yf, w, yw, yb, nf, nb = (float(v[0]) for v in measures(z))
    m = n // 2
    t = np.linspace(0.0, .5 * math.pi, m + 1)
    s, c = np.sin(t), np.cos(t)
    ef, eb = 2.0 / nf, 2.0 / nb
    xf, yfq = w * s ** ef, yw - (yw - yf) * c ** ef              # the front quadrant: the midline's front to the widest
    xb, ybq = w * s ** eb, yw + (yb - yw) * c ** eb              # the back quadrant: the midline's back to the widest
    xr = .14 * w
    if nf < 2.05:
        yfq = _round_tip(xf, yfq, xr)
    if nb < 2.05:
        ybq = _round_tip(xb, ybq, xr)
    pts = [(float(x), float(y)) for x, y in zip(xf, yfq)]
    pts += [(float(x), float(y)) for x, y in zip(xb[::-1][1:], ybq[::-1][1:])]
    pts[0] = (0.0, float(yfq[0])); pts[-1] = (0.0, float(ybq[0]))
    return pts


def sections(step=.5):
    zs = np.arange(MEASURES[0, 0], 10.4, step)
    zs = np.r_[zs, np.arange(zs[-1] + .1, CROWN_Z + .021, .1)]
    zj = np.arange(-14.0, -9.0, .25)                    # and every quarter round the jaw's underside
    zs = np.unique(np.round(np.r_[zs, zj], 4))
    return {float(z): section(z) for z in zs}


def ell(P, c, r):
    q = (P - np.asarray(c, F32)) / np.asarray(r, F32)
    k0 = length(q)
    k1 = length(q / np.asarray(r, F32))
    return k0 * (k0 - 1.0) / np.maximum(k1, 1e-6)


def G3(P, c, r):
    q = (P - np.asarray(c, F32)) / np.asarray(r, F32)
    return np.exp(-(q * q).sum(1))


def seg_dist(P, pts):
    """the distance to a polyline and where along it (0..len-1)"""
    best = np.full(len(P), 1e9, F32); along = np.zeros(len(P), F32)
    for i in range(len(pts) - 1):
        a, b = np.asarray(pts[i], F32), np.asarray(pts[i + 1], F32)
        ba = b - a
        h = np.clip(((P - a) @ ba) / float(ba @ ba), 0, 1)
        dd = length(P - a - h[:, None] * ba)
        m = dd < best
        best = np.where(m, dd, best); along = np.where(m, i + h, along)
    return best, along


ORBIT = ((3.2, -7.45, .15), (1.75, 1.6, 1.45))                  # each eye's socket: just the room the lids need
JAW_BORDER = [(1.4, -10.6, -11.6), (3, -8.9, -11.2), (4.5, -6.4, -10.6), (5.55, -3.3, -9.96),
              (5.85, -1.9, -9.27), (5.75, -1, -6.8)]          # the mandible's lower border to the angle, up the ramus


class HeadBase:
    """the soft forms over the lofted sections (cm in, cm out: positive pushes the skin in, negative out)"""

    def __init__(self, params=None):
        self.p = dict(params or {})

    def k(self, name, default=1.0):
        return float(self.p.get(name, default))

    def relief(self, Q, d):
        P = np.c_[np.abs(Q[:, 0]), Q[:, 1], Q[:, 2]].astype(F32)
        x, y, z = P[:, 0], P[:, 1], P[:, 2]
        front = np.clip((-y - 4.0) / 3.0, 0, 1)                       # only on the face
        # the brow's ridge over each eye (heavier at its middle, fading out to the temple) and the glabella
        d = d - .26 * self.k("brow") * G3(P, (3.1, -10.4, 1.68), (1.9, .95, .85)) * front
        d = d - .16 * self.k("brow") * G3(P, (0.0, -11.0, 1.5), (.9, .7, .75))
        # the cheekbones: the malar mass and the arch back toward the ear
        d = d - .5 * self.k("cheekbones") * G3(P, (4.55, -7.9, -1.75), (1.45, 1.15, 1.1))
        d = d - .2 * self.k("cheekbones") * G3(P, (6.25, -5.6, -1.4), (.8, 1.9, .7))
        # the hollow under the cheekbone, the temple's hollow
        d = d + .42 * self.k("cheek_hollow") * G3(P, (5.0, -7.3, -4.9), (1.15, 1.6, 1.35))   # the hollow under the
        # cheekbone, deeper (full to the jaw the lower face read wide and soft: the owner's portrait's is hollow)
        d = d + .12 * self.k("temples") * G3(P, (6.85, -5.2, 2.6), (.9, 1.7, 1.6))
        # the cheek's soft pad beside the nose and above the mouth's corner, and its apple under the eye (the fat
        # pad's fullness: without it the face was a mannequin's plane from the eye to the jaw)
        d = d - .22 * self.k("cheeks") * G3(P, (2.9, -9.6, -3.6), (1.2, .8, 1.4))
        d = d - .14 * self.k("cheeks") * G3(P, (3.5, -9.25, -2.5), (1.15, .7, 1.0))
        # the lower lid's soft bag over the cheek (the lid-cheek junction under it is head.py's tear trough)
        d = d - .05 * self.k("eye_bags") * G3(P, (3.25, -8.85, -.7), (.95, .45, .32))
        # the cheek full beside the nasolabial fold (the fold itself is head.py's soft line)
        dist, along = seg_dist(P, [(2.55, -9.9, -4.55), (3.3, -9.85, -6.2), (3.85, -9.3, -8.0)])
        d = d - .1 * self.k("nasolabial") * np.exp(-(dist / .55) ** 2) * (y < -8.0)
        # the forehead's two broad swells (the frontal eminences)
        d = d - .1 * self.k("forehead") * G3(P, (2.9, -9.8, 5.4), (1.8, .9, 1.6)) * front
        # the mandible: its border a soft ridge from the chin round the angle, the angle itself, the masseter
        dist, along = seg_dist(P, JAW_BORDER)
        w = np.clip(along / 1.0, 0, 1) * np.clip((len(JAW_BORDER) - 1 - along) / .7, 0, 1)
        d = d - .1 * self.k("jaw") * np.exp(-(dist / .8) ** 2) * w
        d = d - .22 * self.k("jaw") * G3(P, (5.7, -2.2, -8.85), (.75, 1.1, .9))
        d = d - .16 * self.k("jaw") * G3(P, (5.6, -3.4, -6.4), (.7, 1.8, 2.2))
        # the chin's mound and its two corners
        d = d - .24 * self.k("chin") * G3(P, (0.0, -11.0, -10.1), (1.4, .7, 1.0))
        d = d - .1 * self.k("chin") * G3(P, (1.55, -10.75, -10.88), (.6, .6, .55))
        # the groove between the lower lip and the chin (the mentolabial sulcus)
        d = d + .06 * self.k("chin") * np.exp(-((z + 8.85) / .3) ** 2) * np.exp(-(x / 1.9) ** 2) * (y < -9.0)
        # the philtrum: two soft columns from the columella's foot down to the bow's peaks, a shallow groove between
        ph = np.clip((-4.75 - z) / .4, 0, 1) * np.clip((z + 6.2) / .35, 0, 1) * (y < -9.8)
        colx = .3 + .22 * np.clip((-4.8 - z) / 1.3, 0, 1)
        d = d - .03 * ph * np.exp(-((x - colx) / .24) ** 2) + .02 * ph * np.exp(-(x / .26) ** 2)
        # the orbits: the eyes sit deep under the brow
        d = smax(d, -ell(P, *ORBIT), .6)
        # the neck: the sternomastoids from behind the ears to the notch, the larynx
        dist, along = seg_dist(P, [(5.3, 1.9, -6.0), (4.2, -.8, -11.55), (2.6, -3.4, -16.55), (1.4, -4.8, -21.55)])
        d = d - .38 * np.exp(-(dist / 1.25) ** 2) * np.clip((along - .1) / .7, 0, 1) ** 2
        d = smin(d, ell(P, (0.0, -4.05, -14.9), (1.0, .7, 1.35)), 1.4)
        return d


# --- the nose and the mouth as volumes (cm) ------------------------------------------------------------------------
# A man's nose (Farkas): 5.35 cm from the nasion to the subnasale, the tip 2.0 cm out from the subnasale, the ridge at
# 30 degrees to the face, 3.7 cm across the wings. Built as a WEDGE, not a rod on the face (the first nose: a ridge
# 7 mm wide standing 1.2 cm proud of flat cheeks, then a ball for the tip and a ball for each wing; the template's,
# measured beside it, is 1.2 cm across its ridge and opens back into the cheeks): the ridge rounded 5.5-8.5 mm (the
# bony bridge the narrowest), the side walls opening at 28-33 degrees back to the cheeks and the eyes' inner
# corners; the lobule two soft domes over the tip; the columella sloping back to the lip (the nasolabial angle
# about 100 degrees); the wings round lobes either side, joined to the lobule by their groove; the nostrils under
# them, turned in toward the tip.
NOSE_RIDGE = np.array([   # z, the ridge's front (y), its rounding, the side walls' half angle (degrees), how deep
    [1.60, -10.00, .55, 36, 1.6],
    [0.55, -10.40, .55, 33, 1.7],
    [0.00, -10.70, .58, 31, 2.0],
    [-1.00, -11.36, .63, 29, 2.7],
    [-2.00, -12.02, .68, 28, 3.1],
    [-2.80, -12.50, .74, 28, 3.2],
    [-3.30, -12.72, .80, 29, 3.2],
    [-3.65, -12.80, .8, 30, 3.1],              # the tip (pronasale)
    [-4.00, -12.70, .78, 31, 2.9],             # under it the front turns back: the infratip, the columella
    [-4.20, -12.45, .68, 31, 2.6],             # narrowing to the columella (a broad lobule read as a snout)
    [-4.38, -12.05, .56, 32, 2.2],
    [-4.52, -11.62, .46, 32, 1.7],
    [-4.65, -11.20, .4, 32, 1.2],              # the subnasale
], F32)
NOSE_ALA = ((1.0, -10.95, -4.3), (.85, .72, .48))          # set back: the tip stands in front, narrow
NOSTRIL = ((.58, -11.45, -4.55), (.27, .62, .26), 22.0)   # centre, half sizes, turned in toward the tip (degrees)


def _ridge(P, k):
    """the nose as one solid: at each height a wedge opening backward from the ridge's line, rounded at its front,
    as deep as the table says (behind that the eyes' corners and the cheeks), from the root down past the tip to
    the subnasale; its underside sloping up toward the tip"""
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    T = NOSE_RIDGE[::-1]
    col = lambda c, q: np.interp(q, T[:, 0], T[:, c]).astype(F32)
    yd, r, al, depth = col(1, z), col(2, z), np.radians(col(3, z)), col(4, z)
    slope = (col(1, z + .05) - col(1, z - .05)) / .1
    ta = np.tan(al) * k("nose_width")
    ca = 1.0 / np.sqrt(1 + ta * ta); sa = ta * ca
    qx, qy = x, y - (yd + r)
    front = qx * sa + qy * ca < 0
    d = np.where(front, np.sqrt(qx * qx + qy * qy), qx * ca - qy * sa) - r
    d = d / np.sqrt(1 + np.minimum(slope * slope, 4.0))       # the ridge leans: its true distance is shorter
    d = smax(d, y - (yd + depth), .5)
    d = smax(d, z - 1.6, .6)
    under = -4.65 + .3 * np.clip(-11.2 - y, 0, 2.0)           # the underside, rising toward the tip
    under = under + .18 * np.clip((x - .35) / .9, 0, 1)        # and to the wings' rims (seen from the front a soft
    #                                                            gull's wing, not a flat line)
    return smax(d, under - z, .2)


def nose(Q, k=lambda n: 1.0):
    P = np.c_[np.abs(Q[:, 0]), Q[:, 1], Q[:, 2]].astype(F32)
    w = k("nose_width")
    d = _ridge(P, k)
    ac, ar = NOSE_ALA
    d = smin(d, ell(P, (ac[0] * w, ac[1], ac[2]), ar), .6)     # the wings: broad lobes flowing out of the tip's sides
    # the nostrils: into the underside, from beside the columella back and out, turned in toward the tip
    nc, nr, turn = NOSTRIL
    t = math.radians(turn)
    dx, dy = P[:, 0] - nc[0] * w, P[:, 1] - nc[1]
    L = np.c_[dx * math.cos(t) - dy * math.sin(t), dx * math.sin(t) + dy * math.cos(t), P[:, 2] - nc[2]]
    d = smax(d, -ell(L, (0, 0, 0), nr), .15)                  # soft rims (a tight cut punched round holes)
    return d


def capsule_d(P, a, b, r):
    a, b = np.asarray(a, F32), np.asarray(b, F32)
    pa, ba = P - a, b - a
    h = np.clip((pa @ ba) / float(ba @ ba), 0, 1)
    return length(pa - h[:, None] * ba) - r


MOUTH_W = 2.58                    # half the mouth's width (cm): 5.2 cm corner to corner (Farkas: 5.3)


def lips(Q, stom=-7.25, k=lambda n: 1.0):
    """the upper and the lower lip (their red parts), each fullest at its top and sloping back below it (the upper
    lip pouts at its border and falls back to the stomion, the lower rolls out under the stomion and back into the
    fold over the chin: the first lips were round rolls, two balls in profile), thinning into the corners (cm)"""
    P = np.c_[np.abs(Q[:, 0]), Q[:, 1], Q[:, 2]].astype(F32)
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    W = MOUTH_W * k("mouth_width")                               # the corner
    u = np.clip(x / W, 0, 1.2)
    curve = 1.1 * u ** 2                                          # the lips' front seen from above: a gentle arch
    fade = np.clip(1 - u ** 2.8, 0, 1) ** .5                 # full well out from the middle, tapering into each corner
    full = 1.2 * k("lips")
    # the upper lip: from the stomion up to its border (the bow's peaks, the dip between them), sheared back
    bow = .98 + .14 * np.exp(-((x - .55) / .36) ** 2) - .06 * np.exp(-(x / .26) ** 2)   # the bow's peaks, a soft dip
    hu = np.maximum(1.1 * bow * fade, .08)
    zu, bu = stom + .5 * hu, .52 * hu
    au = np.maximum(.56 * fade * full, .08)
    yu = -11.3 + curve + au + .38 * (zu - z)
    up = np.sqrt(((y - yu) / au) ** 2 + ((z - zu) / bu) ** 2)
    up = (up - 1) * np.minimum(au, bu)
    # the lower lip: fuller, from the stomion down, sheared back below its fullest
    hl = np.maximum(1.25 * fade, .08)
    zl, bl = stom - .5 * hl, .55 * hl
    al = np.maximum(.58 * fade * full, .08)
    yl = -11.05 + curve + al + .6 * (zl - z)
    lo = np.sqrt(((y - yl) / al) ** 2 + ((z - zl) / bl) ** 2)
    lo = (lo - 1) * np.minimum(al, bl)
    # each lip ends at the mouth's corner (round, no further)
    up = smax(up, x - W, .15); lo = smax(lo, x - W, .15)
    return smin(up, lo, .06), up, lo
