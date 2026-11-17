"""The foot (Project Orion male): its own all-quad cage grafted onto the leg's ankle ring, bare (boots come later as
clothing), 27 cm long, turned out a little as the sheet stands.

Topology (cage, one foot): the ankle's ring of 16 bends forward like an elbow (the heel the outside of the bend,
the instep the inside) through four rings to the ball of the foot; there its front half is the back of the foot
(8 across) and its back half the sole (8 across); five toes leave from the end, the big toe from two of its seven
segments (a ring of 6), the others from one each (rings of 4), the segment beyond the little toe the foot's own end;
each toe runs in rings to a cap at its tip. Targets: each ring round the foot's section in its own plane (a flat
sole, a rounded back, the arch raised on the inside), each toe round its bones, the tips on the floor.
"""
import math
import numpy as np

FOOT_LEN = 0.270
TOE_OUT = 7.0                    # degrees the foot turns out
# toes: name, segments of the ball's end (first, count), length, width at the root, splay (deg, + outward)
TOES = [("big", 0, 2, .046, .027, -3.0), ("second", 2, 1, .036, .0175, 1.0), ("third", 3, 1, .031, .0165, 4.0),
        ("fourth", 4, 1, .027, .0155, 7.0), ("little", 5, 1, .022, .0145, 11.0)]


def unit(v):
    v = np.asarray(v, float)
    return v / max(float(np.linalg.norm(v)), 1e-12)


class Frame:
    """the foot's frame at the ankle: forward along it, out (lateral), up"""

    def __init__(self, ankle, sx):
        self.A = np.asarray(ankle, float)
        t = math.radians(TOE_OUT)
        self.fw = np.array([sx * math.sin(t), -math.cos(t), 0.0])
        self.lat = np.array([sx * math.cos(t), math.sin(t), 0.0])
        self.up = np.array([0.0, 0.0, 1.0])
        self.sx = sx

    def p(self, f, l, z):
        """f forward of the ankle, l outward, z above the floor"""
        q = self.A + self.fw * f + self.lat * l
        q[2] = z
        return q


# the foot's upright rings after the heel's: along the foot (m), half width, the top of its back, how far the inner
# side's sole is raised (the arch)
RINGS = [(.040, .041, .068, .006),            # in front of the ankle, the heel's front under it
         (.095, .045, .058, .014),            # the arch
         (.150, .049, .046, .004),            # behind the ball
         (.178, .051, .038, .000)]            # the ball of the foot
HEEL = dict(back=(-.052, .018), front=(.012, .088), hw=.038)   # the tilted ring: its low back, its high front


def build_foot(C, ankle_ring, F, log=print):
    """adds one foot to the cage C on the leg's ankle ring (16 vertex indices; the leg's j-th vertex sits at
    326.25 + 22.5 j degrees round the leg: 0 front, 90 outside, 180 back, 270 inside)"""
    sx = F.sx
    angs = [(326.25 + 22.5 * j) % 360 for j in range(16)]
    rings = [list(ankle_ring)]
    (fb, zb), (ff, zf) = HEEL["back"], HEEL["front"]
    cf, cz = .5 * (fb + ff), .5 * (zb + zf)
    ax_f, ax_z = (ff - fb) / 2, (zf - zb) / 2
    ring = []
    for phi in angs:
        p = math.radians(phi)
        s, c = math.sin(p), math.cos(p)             # s: outward, c: toward the front (the instep) / back (the heel)
        f = cf + ax_f * c
        z = cz + ax_z * c - .010 * (1 - abs(c)) * (c < 0)     # the heel rounder low down
        ring.append(C.add(F.p(f, HEEL["hw"] * math.copysign(abs(s) ** .85, s), z), "foot"))
    rings.append(ring)
    for f, hw, top, arch in RINGS:
        ring = []
        for phi in angs:
            p = math.radians(phi)
            s, c = math.sin(p), math.cos(p)
            l = hw * math.copysign(abs(s) ** .8, s)
            if c >= 0:                                 # the back of the foot: rounded
                z = max(top * abs(c) ** .55, .012)
            else:                                      # the sole: flat, the arch raised on the inside
                z = arch * max(0.0, -s) * (1 - abs(c) ** 4) * .9
            ring.append(C.add(F.p(f, l, z), "foot"))
        rings.append(ring)
    for r0, r1 in zip(rings, rings[1:]):
        C.strip(r0, r1)
    ball = rings[-1]
    # the ball's end: back of the foot (inside -> outside) and sole (inside -> outside)
    order_d = [14, 15, 0, 1, 2, 3, 4, 5]
    order_p = [13, 12, 11, 10, 9, 8, 7, 6]
    D = [ball[j] for j in order_d]
    P = [ball[j] for j in order_p]
    C.quad(D[6], D[7], P[7], P[6])                    # beyond the little toe
    for name, i0, nseg, L, wd, splay in TOES:
        base = D[i0:i0 + nseg + 1] + P[i0:i0 + nseg + 1][::-1]
        toe(C, F, base, name, L, wd, splay)
    log(f"foot: {'left' if sx > 0 else 'right'}")


def toe(C, F, base, name, L, wd, splay):
    pts = np.array([C.V[v] for v in base])
    root = pts.mean(0)
    t = math.radians(splay)
    d = unit(F.fw * math.cos(t) + F.lat * math.sin(t))
    n = len(base)
    # the toe: forward from the ball, then down to its tip on the floor
    plan = [(.30, 1.0), (.62, .92), (.88, .80)]
    rings = [list(base)]
    centre = pts.mean(0)
    rel = pts - centre
    for share, ws in plan:
        c = root + d * L * share
        c[2] = root[2] + (.012 - root[2]) * share ** 1.4
        ring = []
        for k in range(n):
            r = rel[k] * (ws * (1 - .25 * share))
            r[2] = rel[k][2] * ws * (1 - .35 * share)
            ring.append(C.add(c + r, f"toe_{name}"))
        rings.append(ring)
    for r0, r1 in zip(rings, rings[1:]):
        C.strip(r0, r1)
    if n == 4:
        C.cap(rings[-1], f"toe_{name}", .006, d)
    else:
        C.cap_rect(rings[-1], 1, n // 2 - 1, f"toe_{name}", .006, d)
