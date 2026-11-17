"""The foot's ANATOMY (Project Orion male) as a signed distance field: the shape the foot's cage is sampled from and
the subdivided skin is laid onto (foot.py). Built the way a foot is: the lower leg narrowing above the ankle, the
Achilles tendon standing out behind it with a hollow either side, the two ankle bones (the inner higher and further
forward, the outer lower and further back), the heel rounding out behind and under the ankle, the instep sloping
from the shin's front down to the toes (highest over the inner side), the arch raised under the inner side, the ball
of the foot under the metatarsals' heads, and five toes on their own bones: the big toe straight and broad, the
others shorter in turn, each raised at its first joint and curling down to its pad on the floor. Everything that
bears weight is flattened on the floor.

Coordinates: the foot's own frame (foot.Frame): f forward from the ankle's axis, l outward (lateral), z above the
floor, in metres; the right foot is the left's mirror (its frame is). A 1.84 m man's foot: 27 cm from the heel's back
to the big toe's tip, 10.2 cm across the ball, 6.6 cm across the heel, the instep 6.6 cm high, the ankle bones 7 and
8.6 cm above the floor.
"""
import math
import os
import sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
from sdf import smin, smax, length, Loft, smooth_curve, round_cone  # noqa: E402

F32 = np.float32

# --- the lower leg (a column along z, its section: out, in, front, back half widths) -------------------------------
COLUMN_Z = [.300, .250, .200, .160, .130, .100, .075, .050]
COLUMN = dict(out=[.041, .038, .035, .032, .030, .0295, .0295, .029],
              inn=[.041, .038, .034, .031, .029, .0290, .0290, .029],
              front=[.047, .044, .040, .036, .034, .036, .041, .046],
              back=[.052, .047, .042, .039, .038, .038, .038, .038])
ACHILLES = [((-.037, .001, .250), .0110), ((-.039, .001, .150), .0075), ((-.042, .002, .085), .0072),
            ((-.046, .002, .045), .0088)]
# the ankle bones are the ENDS of the shin's two bones: each a ridge coming out of the leg above (buried at its top)
# and ending in a rounded knob: the inner (the tibia's) higher and further forward, the outer (the fibula's) lower,
# further back and standing out more
MALLEOLI = [((.006, -.017, .175), .006, (.004, -.0215, .083), .0112),
            ((-.006, .018, .185), .006, (-.011, .0245, .066), .0118)]        # the outer (lateral): lower, further back
HEEL = ((-.034, .003, .031), (.029, .031, .032))               # the calcaneus in its pad
# --- the midfoot: its outline and heights along it ------------------------------------------------------------------
MID_F = [-.030, .000, .025, .050, .075, .100, .120, .140, .152]
MID = dict(top=[.080, .084, .080, .073, .064, .054, .042, .028, .022],      # the instep over its highest line
           ridge=[-.002, -.004, -.006, -.008, -.010, -.012, -.014, -.016, -.017],  # where it is highest (l)
           med_edge=[.040, .042, .044, .042, .038, .034, .031, .030, .030],   # the side's height at the inner edge
           lat_edge=[.034, .032, .030, .027, .025, .024, .023, .022, .021],   # ... at the outer edge
           med=[-.028, -.028, -.028, -.029, -.032, -.038, -.044, -.046, -.046],
           lat=[.033, .037, .040, .043, .047, .051, .054, .054, .051])
ARCH = ((.040, -.044, -.006), (.058, .030, .021))              # what the arch lifts off the floor under the inner side
# --- the ball and the toes ------------------------------------------------------------------------------------------
# per toe: the joint at its root (MTP: f, l, z), the ball's pad under it (radius), the bones' lengths, the joints'
# bends (deg: the first raises the toe, the next curl it down), the yaw (deg, + outward), the half width and half
# height at the root, at the last joint and at the tip
TOES = [dict(name="big", mtp=(.134, -.0285, .023), pad=.0140, bones=(.032, .025), bend=(9.0, -6.0), yaw=-1.5,
             w=(.0135, .0128, .0122), h=(.0110, .0100, .0090)),
        dict(name="second", mtp=(.139, -.0055, .020), pad=.0110, bones=(.026, .013, .0095), bend=(12.0, -36.0, -18.0),
             yaw=0.0, w=(.0100, .0094, .0097), h=(.0084, .0080, .0076)),
        dict(name="third", mtp=(.132, .0135, .019), pad=.0105, bones=(.023, .0115, .009), bend=(12.0, -36.0, -18.0),
             yaw=1.5, w=(.0096, .0090, .0093), h=(.0080, .0076, .0072)),
        dict(name="fourth", mtp=(.122, .0315, .0175), pad=.0100, bones=(.020, .0105, .0085), bend=(12.0, -36.0, -18.0),
             yaw=3.0, w=(.0092, .0086, .0088), h=(.0076, .0072, .0068)),
        dict(name="little", mtp=(.108, .0475, .016), pad=.0096, bones=(.017, .009, .0078), bend=(11.0, -34.0, -17.0),
             yaw=4.5, w=(.0089, .0083, .0084), h=(.0072, .0066, .0062))]
TOE_GAP = .0036                  # toes press together, never into each other: each is cut at the plane between them
FLOOR_K = .006                   # how round the edge of what the floor flattens is


def ellipsoid(Q, c, r):
    q = (Q - np.asarray(c, F32)) / np.asarray(r, F32)
    k0 = length(q)
    k1 = length(q / np.asarray(r, F32))
    return k0 * (k0 - 1) / np.maximum(k1, 1e-9)


def round_int(a, b, r):
    """the rounded intersection of two half-spaces' distances (a corner of radius r)"""
    return length(np.c_[np.maximum(a + r, 0), np.maximum(b + r, 0)]) + np.minimum(np.maximum(a, b) + r, 0) - r


def toe_chain(t):
    """the joints of a toe (its root, each joint, the tip) and its half widths / heights there"""
    p = np.array(t["mtp"], float)
    yaw = math.radians(t["yaw"])
    pitch = 0.0
    pts = [p.copy()]
    for L, b in zip(t["bones"], t["bend"]):
        pitch += math.radians(b)
        d = np.array([math.cos(pitch) * math.cos(yaw), math.cos(pitch) * math.sin(yaw), math.sin(pitch)])
        p = p + d * L
        pts.append(p.copy())
    n = len(pts)
    w = np.interp(np.linspace(0, 1, n), [0, .6, 1], t["w"])
    h = np.interp(np.linspace(0, 1, n), [0, .6, 1], t["h"])
    return np.array(pts), w, h


class FootShape:
    """the field in the foot's frame F (foot.Frame: A, fw, lat); world points in, metres out (negative inside)"""

    def __init__(self, F=None):
        self.F = F
        self.column = Loft((0, 0, COLUMN_Z[0]), (0, 0, COLUMN_Z[-1]),
                           dict(t=[(COLUMN_Z[0] - z) / (COLUMN_Z[0] - COLUMN_Z[-1]) for z in COLUMN_Z],
                                rv_pos=COLUMN["out"], rv_neg=COLUMN["inn"],
                                rw_pos=COLUMN["front"], rw_neg=COLUMN["back"], n=[2.0] * len(COLUMN_Z)),
                           v_axis=(0, 1, 0), cap=.6)
        tt = np.linspace(0, 1, 256)
        self.mid_t = tt
        ts = (np.array(MID_F) - MID_F[0]) / (MID_F[-1] - MID_F[0])
        self.mid = {k: smooth_curve(ts, v, tt) for k, v in MID.items()}
        self.toes = [toe_chain(t) for t in TOES]
        # where each toe parts from its neighbours: half way along its first bone (the webs); the midfoot ends just
        # beyond that line, slanting back to the little toe as the toes' joints do
        self.roots = [ch[0][0] + (ch[0][1] - ch[0][0]) * .5 for ch in self.toes]
        rl = [r[1] for r in self.roots]; rf = [r[0] for r in self.roots]
        self.front_l = np.array([rl[0] - .03] + rl + [rl[-1] + .03])
        self.front_f = np.array([rf[0]] + rf + [rf[-1] - .006]) - .007
        # the planes between neighbouring toes: through the middle of their facing sides at the root, square to the
        # mean of their ways
        self.cuts = []
        for (pa, wa, _), (pb, wb, _) in zip(self.toes, self.toes[1:]):
            ua = (pa[1] - pa[0]) / np.linalg.norm(pa[1] - pa[0]); ub = (pb[1] - pb[0]) / np.linalg.norm(pb[1] - pb[0])
            u = ua + ub; u[2] = 0; u /= np.linalg.norm(u)
            n = np.array([-u[1], u[0], 0.0])                          # outward (toward the next toe)
            if n[1] < 0:
                n = -n
            ra, rb = pa[0] + (pa[1] - pa[0]) * .5, pb[0] + (pb[1] - pb[0]) * .5
            m = .5 * ((ra + n * wa[0]) + (rb - n * wb[0]))
            self.cuts.append((m.astype(F32), n.astype(F32)))

    def local(self, P):
        P = np.asarray(P, F32)
        if self.F is None:
            return P
        d = P - np.array([self.F.A[0], self.F.A[1], 0.0], F32)
        return np.c_[d @ self.F.fw.astype(F32), d @ self.F.lat.astype(F32), P[:, 2]].astype(F32)

    def midfoot(self, Q):
        f, l, z = Q[:, 0], Q[:, 1], Q[:, 2]
        t = np.clip((f - MID_F[0]) / (MID_F[-1] - MID_F[0]), 0, 1)
        g = {k: np.interp(t, self.mid_t, v).astype(F32) for k, v in self.mid.items()}
        # the top: highest along the ridge, falling to each edge's height in a rounded section
        side = np.where(l < g["ridge"], (g["ridge"] - l) / np.maximum(g["ridge"] - g["med"], 1e-4),
                        (l - g["ridge"]) / np.maximum(g["lat"] - g["ridge"], 1e-4))
        edge = np.where(l < g["ridge"], g["med_edge"], g["lat_edge"])
        s = np.clip(side, 0, 1.2)
        top = g["top"] - (g["top"] - edge) * s ** 2.2
        d_top = z - top
        d_bot = -z - .002
        d_side = np.maximum(l - g["lat"], g["med"] - l)
        d_end = np.maximum(MID_F[0] - f, f - np.interp(l, self.front_l, self.front_f).astype(F32))
        up = round_int(d_top, d_side, .016)
        dn = round_int(d_bot, d_side, .009)
        d = np.maximum(up, dn)
        return round_int(d, d_end, .02)

    def toe(self, Q, chain):
        """each bone a tapered capsule with an oval section (wider than high, a little flatter over the nail and
        fuller under the pads), measured in a space where that oval is round"""
        pts, w, h = chain
        d = np.full(len(Q), 1e3, F32)
        for i in range(len(pts) - 1):
            a, b = pts[i], pts[i + 1]
            ax = b - a
            L = float(np.linalg.norm(ax)); u = ax / L
            side = np.cross(u, [0, 0, 1.0]); side /= np.linalg.norm(side)
            up = np.cross(side, u)
            q = Q - a.astype(F32)
            x = q @ u.astype(F32); y = q @ side.astype(F32); zz = q @ up.astype(F32)
            tt = np.clip(x / L, 0, 1)
            s = (h[i] + (h[i + 1] - h[i]) * tt) / (w[i] + (w[i + 1] - w[i]) * tt)
            zz = np.where(zz > 0, zz / .92, zz / 1.06)
            S = np.c_[x, y * s, zz].astype(F32)
            d = np.minimum(d, round_cone(S, (0, 0, 0), (L, 0, 0), float(h[i]), float(h[i + 1])))
        return d

    def body(self, Q):
        """everything but the toes (local points)"""
        ankle = self.column(Q)
        ach = np.full(len(Q), 1e3, F32)
        for (c0, r0), (c1, r1) in zip(ACHILLES, ACHILLES[1:]):
            S = Q.copy(); S[:, 1] = (S[:, 1] - c0[1]) * 1.6 + c0[1]            # wider than deep
            ach = np.minimum(ach, round_cone(S, c0, c1, r0, r1))
        d = smin(ankle, ach, .015)
        for a, ra, b, rb in MALLEOLI:
            d = smin(d, round_cone(Q, a, b, ra, rb), .012)
        heel = ellipsoid(Q, *HEEL)
        d = smin(d, heel, .022)
        mid = self.midfoot(Q)
        mid = smax(mid, -ellipsoid(Q, *ARCH), .012)
        d = smin(d, mid, .028)
        ball = np.full(len(Q), 1e3, F32)
        for t in TOES:
            c = np.array(t["mtp"], float); c[2] = t["pad"] - .002
            ball = smin(ball, ellipsoid(Q, c, (t["pad"] * 1.25, t["pad"] * 1.05, t["pad"])), .010)
        return smin(d, ball, .012)

    def toe_d(self, Q, i):
        """toe i alone (local points): its bones and the pad at its tip"""
        ch = self.toes[i]
        tip = ch[0][-1]
        pad = ellipsoid(Q, (tip[0] - .002, tip[1], tip[2] - ch[2][-1] * .25),
                        (ch[1][-1] * 1.1, ch[1][-1] * 1.08, ch[2][-1] * 1.12))
        d = smin(self.toe(Q, ch), pad, .004)
        if i > 0:                                                       # not into the toe inward of it
            m, n = self.cuts[i - 1]
            d = smax(d, -((Q - m) @ n) + TOE_GAP / 2, .002)
        if i < len(self.cuts):                                          # nor into the one outward
            m, n = self.cuts[i]
            d = smax(d, (Q - m) @ n + TOE_GAP / 2, .002)
        return d

    def __call__(self, P, only=None):
        """the foot (world points); only=i: with toe i alone (its own surface, never a neighbour's)"""
        Q = self.local(P)
        d = self.body(Q)
        toes = np.full(len(Q), 1e3, F32)
        for i in (range(len(TOES)) if only is None else [only]):
            toes = np.minimum(toes, self.toe_d(Q, i))
        d = smin(d, toes, .010)
        return smax(d, -Q[:, 2], FLOOR_K)

    def with_toe(self, i):
        return lambda P: self(P, only=i)

    def toe_only(self, i):
        """toe i on its own, flattened on the floor (world points): its rings hug it, never the foot behind it"""
        def f(P):
            Q = self.local(P)
            return smax(self.toe_d(Q, i), -Q[:, 2], FLOOR_K)
        return f

    def bounds(self):
        if self.F is None:
            return np.array([-.10, -.07, -.005]), np.array([.24, .08, .30])
        corners = np.array([[f, l, z] for f in (-.10, .24) for l in (-.08, .08) for z in (-.005, .30)])
        W = np.array([self.F.A[0], self.F.A[1], 0]) + corners[:, :1] * self.F.fw + corners[:, 1:2] * self.F.lat
        W[:, 2] = corners[:, 2]
        return W.min(0), W.max(0)
