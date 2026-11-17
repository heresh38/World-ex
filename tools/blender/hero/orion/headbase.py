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
    [-24, -5.9, 7.9, 1.6, 7.9, 2, 2.1],
    [-20, -5.35, 6.9, 1.5, 7.4, 2, 2.1],
    [-17, -5.15, 6.6, 1.4, 7, 2, 2.1],
    [-15, -5.35, 6.45, 1.2, 6.6, 1.95, 2.1],
    [-14, -6.5, 6.4, 1, 6.4, 1.85, 2.1],
    [-13.3, -8, 6.35, 0.8, 5.95, 1.75, 2.1],
    [-12.7, -9.35, 6.3, 0.5, 5.95, 1.68, 2.1],
    [-12, -10.3, 6.3, 0.2, 6, 1.66, 2.1],
    [-11, -11, 6.45, -0.3, 6.15, 1.7, 2.15],
    [-10.3, -11.1, 6.7, -0.9, 6.3, 1.76, 2.2],
    [-9.5, -10.85, 6.95, -1.3, 6.5, 1.82, 2.2],
    [-8.5, -10.65, 7.05, -1.4, 6.9, 1.92, 2.25],
    [-7, -10.9, 7.1, -1.4, 7.5, 2.05, 2.3],
    [-6, -10.9, 7.2, -1.4, 8, 2.12, 2.3],
    [-5, -10.75, 7.3, -1.4, 8.5, 2.18, 2.3],
    [-4, -10.5, 7.42, -1.3, 9, 2.24, 2.3],
    [-3, -10.3, 7.52, -1.15, 9.35, 2.3, 2.3],
    [-2, -10.15, 7.6, -1, 9.65, 2.33, 2.3],
    [-1, -9.85, 7.65, -0.8, 9.85, 2.33, 2.3],
    [0, -9.85, 7.5, -0.55, 9.95, 2.3, 2.3],
    [0.8, -10.2, 7.58, -0.3, 10, 2.25, 2.3],
    [1.8, -10.7, 7.66, 0, 10.05, 2.18, 2.3],
    [2.6, -10.75, 7.72, 0.3, 10.05, 2.12, 2.3],
    [3.6, -10.5, 7.8, 0.55, 10, 2.1, 2.3],
    [4.6, -10.1, 7.85, 0.8, 9.9, 2.08, 2.3],
    [5.6, -9.7, 7.85, 1, 9.75, 2.06, 2.3],
    [6.6, -9.25, 7.8, 1.15, 9.55, 2.05, 2.3],
])


def measures(z):
    zs = MEASURES[:, 0]
    return [smooth_curve(zs, MEASURES[:, k], np.atleast_1d(np.asarray(z, float))) for k in range(1, 7)]


def section(z, n=40):
    """the half section at height z: points (x, y) from the front midline round the side to the back midline"""
    yf, w, yw, yb, nf, nb = (float(v[0]) for v in measures(z))
    pts = []
    for i in range(n + 1):
        t = math.pi * i / n
        s, c = math.sin(t), math.cos(t)
        if c >= 0:                                    # the front quadrant: from the midline's front to the widest
            e = 2.0 / nf
            x = w * s ** e
            y = yw - (yw - yf) * c ** e
        else:
            e = 2.0 / nb
            x = w * s ** e
            y = yw + (yb - yw) * (-c) ** e
        pts.append((x, y))
    pts[0] = (0.0, yf); pts[-1] = (0.0, yb)
    return pts


def sections(step=.5):
    zs = np.arange(MEASURES[0, 0], MEASURES[-1, 0] + 1e-6, step)
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


ORBIT = ((2.95, -8.1, .05), (1.62, 1.36, 1.2))                  # each eye's socket: just the room the lids need
JAW_BORDER = [(1.4, -10.6, -12.05), (3.0, -8.9, -11.55), (4.5, -6.4, -10.9), (5.55, -3.3, -10.2),
              (5.85, -1.9, -9.4), (5.75, -1.0, -6.8)]          # the mandible's lower border to the angle, up the ramus


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
        d = d - .26 * self.k("brow") * G3(P, (2.85, -10.45, 1.6), (1.9, .95, .85)) * front
        d = d - .16 * self.k("brow") * G3(P, (0.0, -11.0, 1.5), (.9, .7, .75))
        # the cheekbones: the malar mass and the arch back toward the ear
        d = d - .42 * self.k("cheekbones") * G3(P, (4.45, -8.55, -1.85), (1.5, 1.15, 1.2))
        d = d - .2 * self.k("cheekbones") * G3(P, (6.25, -5.6, -1.4), (.8, 1.9, .7))
        # the hollow under the cheekbone, the temple's hollow
        d = d + .22 * self.k("cheek_hollow") * G3(P, (5.25, -6.9, -5.3), (1.0, 1.5, 1.3))
        d = d + .2 * self.k("temples") * G3(P, (6.85, -5.2, 2.6), (.9, 1.7, 1.6))
        # the cheek's soft pad beside the nose and above the mouth's corner
        d = d - .22 * self.k("cheeks") * G3(P, (2.9, -10.2, -3.6), (1.2, .8, 1.4))
        # the mandible: its border a soft ridge from the chin round the angle, the angle itself, the masseter
        dist, along = seg_dist(P, JAW_BORDER)
        w = np.clip(along / 1.0, 0, 1) * np.clip((len(JAW_BORDER) - 1 - along) / .7, 0, 1)
        d = d - .1 * self.k("jaw") * np.exp(-(dist / .8) ** 2) * w
        d = d - .22 * self.k("jaw") * G3(P, (5.7, -2.2, -9.2), (.75, 1.1, .9))
        d = d - .16 * self.k("jaw") * G3(P, (5.6, -3.4, -6.4), (.7, 1.8, 2.2))
        # the chin's mound and its two corners
        d = d - .2 * self.k("chin") * G3(P, (0.0, -11.0, -10.5), (1.4, .7, 1.0))
        d = d - .1 * self.k("chin") * G3(P, (1.55, -10.75, -11.3), (.6, .6, .55))
        # the orbits: the eyes sit deep under the brow
        d = smax(d, -ell(P, *ORBIT), .45)
        # the neck: the sternomastoids from behind the ears to the notch, the larynx
        dist, along = seg_dist(P, [(5.3, 1.9, -6.0), (4.2, -.8, -12.0), (2.6, -3.4, -17.0), (1.4, -4.8, -22.0)])
        d = d - .38 * np.exp(-(dist / 1.25) ** 2) * (along > .2)
        d = smin(d, ell(P, (0.0, -4.9, -15.3), (1.0, .95, 1.45)), .9)
        return d


# --- the nose and the mouth as volumes (cm) ------------------------------------------------------------------------
# A man's nose (Farkas): 5.6 cm from the nasion to the subnasale, the tip 2.3 cm out from the lip, 3.7 cm across the
# wings; the bony bridge narrow, the cartilage wider down to a rounded lobule with two soft domes; the wings round
# lobes set back on each side, joined to the cheek by their crease, the nostrils under them, the columella between.
NOSE_DORSUM = [((0, -10.0, .45), .46), ((0, -10.6, -.6), .44), ((0, -11.1, -1.6), .46), ((0, -11.6, -2.7), .52),
               ((0, -12.0, -3.45), .6)]
NOSE_SIDE = [((0, -9.2, .1), .42), ((0, -9.5, -1.0), .5), ((0, -9.85, -2.3), .58), ((0, -10.1, -3.4), .64)]
NOSE_TIP = ((0, -11.85, -3.9), (.84, .74, .72))
NOSE_DOMES = ((.32, -12.12, -3.82), (.4, .36, .42))
NOSE_WING = ((1.12, -10.85, -4.5), (.52, .9, .5))
NOSE_BASE = ((0, -11.4, -4.62), (.66, 1.05, .4))
NOSTRIL = ((.52, -11.5, -5.0), (.22, .48, .16))
NOSE_WIDTH_SCALE = 1.33           # the bridge's round cones measured in a space narrower across: a ridge, not a pipe


def nose(Q, k=lambda n: 1.0):
    P = np.c_[np.abs(Q[:, 0]), Q[:, 1], Q[:, 2]].astype(F32)
    S = P.copy(); S[:, 0] *= NOSE_WIDTH_SCALE / k("nose_width")
    d = None
    for (a, ra), (b, rb) in zip(NOSE_DORSUM, NOSE_DORSUM[1:]):
        aa, bb = np.asarray(a, F32), np.asarray(b, F32)
        pa, ba = S - aa, bb - aa
        h = np.clip((pa @ ba) / float(ba @ ba), 0, 1)
        dd = length(pa - h[:, None] * ba) - (ra + (rb - ra) * h)
        d = dd if d is None else smin(d, dd, .25)
    w = k("nose_width")
    # the nose's sidewalls: broad behind the ridge, sloping down into the cheeks (a pyramid, not a rod on the face)
    side = None
    for (a, ra), (b, rb) in zip(NOSE_SIDE, NOSE_SIDE[1:]):
        aa, bb = np.asarray(a, F32), np.asarray(b, F32)
        pa, ba = P - aa, bb - aa
        h = np.clip((pa @ ba) / float(ba @ ba), 0, 1)
        dd = length(pa - h[:, None] * ba) - (ra + (rb - ra) * h)
        side = dd if side is None else smin(side, dd, .4)
    d = smin(d, side, .45)
    d = smin(d, ell(P, NOSE_TIP[0], np.array(NOSE_TIP[1]) * [w, 1, 1]), .45)
    d = smin(d, ell(P, NOSE_DOMES[0], NOSE_DOMES[1]), .22)
    wc, wr = NOSE_WING
    d = smin(d, ell(P, (wc[0] * w, wc[1], wc[2]), wr), .55)
    d = smin(d, ell(P, *NOSE_BASE), .35)
    # the wing's rim: a soft groove where the ala meets the tip's lobule, round from the nostril up and back
    u = (P[:, 0] - .95 * w) / .55; v = (P[:, 2] + 4.25) / .55
    r = np.sqrt(u * u + v * v)
    d = d + .05 * np.exp(-((r - 1.0) / .2) ** 2) * (v > -.4) * np.exp(-((P[:, 1] + 11.6) / .7) ** 2)
    # the nostrils: openings under the tip, running back and out, the columella between them
    nc, nr = NOSTRIL
    d = smax(d, -ell(P, (nc[0] * w, nc[1], nc[2]), nr), .12)
    # flat underneath, back into the lip at the subnasale
    d = smax(d, -(P[:, 2] + 5.08), .18)
    return d


def lips(Q, stom=-7.25, k=lambda n: 1.0):
    """the upper and the lower lip as rolls swept along the mouth's arch: the upper with its bow and tubercle, the
    lower fuller, both thinning into the corners (cm)"""
    P = np.c_[np.abs(Q[:, 0]), Q[:, 1], Q[:, 2]].astype(F32)
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    W = 2.62 * k("mouth_width")                                  # the corner
    u = np.clip(x / W, 0, 1.2)
    arch = -11.42 + 1.3 * u ** 2 + 1.0 * u ** 4                   # the lips' front line seen from above
    fade = np.clip(1 - u ** 2.2, 0, 1) ** .7
    full = 1.18 * k("lips")
    # the upper lip: from the stomion up to its border (the bow's peaks, the dip between them)
    bow = .86 + .1 * np.exp(-((x - .55) / .32) ** 2) - .06 * np.exp(-(x / .22) ** 2)
    hu = np.maximum(bow * fade * full, .08)
    zu = stom + .52 * hu
    au = np.maximum(.52 * fade * full, .1)
    up = np.sqrt(((y - (arch + au * .95)) / au) ** 2 + ((z - zu) / (.58 * hu)) ** 2)
    up = (up - 1) * np.minimum(au, .58 * hu)
    # the tubercle: the upper lip's middle a touch fuller and lower
    up = smin(up, ell(P, (0, -10.9, stom + .22), (.42, .3, .2)), .12)
    # the lower lip: fuller, rounder, from the stomion down
    hl = np.maximum(1.08 * fade * full, .08)
    zl = stom - .5 * hl
    al = np.maximum(.58 * fade * full, .1)
    lo = np.sqrt(((y - (arch + .12 + al * .95)) / al) ** 2 + ((z - zl) / (.55 * hl)) ** 2)
    lo = (lo - 1) * np.minimum(al, .55 * hl)
    # each lip ends at the mouth's corner (round, no further)
    up = smax(up, x - W, .15); lo = smax(lo, x - W, .15)
    return smin(up, lo, .06), up, lo
