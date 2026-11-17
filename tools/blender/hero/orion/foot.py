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
TOES = [("big", 0, 2, .036, .027, -4.0), ("second", 2, 1, .028, .0168, 0.0), ("third", 3, 1, .025, .0160, 3.0),
        ("fourth", 4, 1, .022, .0152, 6.0), ("little", 5, 1, .018, .0145, 10.0)]


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
RINGS = [(.066, .042, .066, .008),            # the instep, sloping forward and down from the ankle
         (.104, .046, .056, .015),            # the arch
         (.145, .049, .043, .005),            # behind the ball
         (.170, .050, .030, .000)]            # the ball of the foot, low at its front where the toes start
HEEL = dict(back=(-.050, .024), front=(.042, .078), hw=.036)   # the tilted ring: its low back, its high front


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
    """a toe: from its segments of the ball's end, rings round its own oval (as wide as the toe, a little lower than
    wide), raised at its middle knuckle and down to its tip on the floor, a cap at the tip. The base ring's order
    round the toe is kept: its first vertices on the toe's back from the inside out, then under it back again."""
    pts = np.array([C.V[v] for v in base])
    n = len(base)
    t = math.radians(splay)
    d = unit(F.fw * math.cos(t) + F.lat * math.sin(t))
    lat = unit(np.cross(d, F.up)) * (1 if F.sx > 0 else -1) * -1
    root = pts.mean(0)
    root[2] = .015 if n == 4 else .017
    # angles round the toe (0 = outward, 90 = up): back from the inside out, the sole back again
    half = n // 2
    back = np.linspace(150, 30, half) if half > 2 else np.array([135.0, 45.0])
    angs = list(back) + [-a for a in back[::-1]]
    plan = [(.22, 1.10, .006), (.58, 1.0, .007), (.86, .90, .003)]     # share along, width, rise above the line
    rings = [list(base)]
    for share, ws, rise in plan:
        c = root + d * L * share
        c[2] = root[2] + (.0085 - root[2]) * share ** 1.6 + rise
        ring = []
        for a in angs:
            r = math.radians(a)
            tall = (.50 if a > 0 else .46) * (1.15 - .3 * share)               # thick at the root, lower at the tip
            off = lat * (wd * ws / 2 * math.cos(r)) + F.up * (wd * ws * tall * math.sin(r))
            ring.append(C.add(c + off, f"toe_{name}"))
        rings.append(ring)
    for r0, r1 in zip(rings, rings[1:]):
        C.strip(r0, r1)
    if n == 4:
        C.cap(rings[-1], f"toe_{name}", wd * .35, d)
    else:
        C.cap_rect(rings[-1], 1, n // 2 - 1, f"toe_{name}", wd * .35, d)
