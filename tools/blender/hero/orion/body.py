"""The new male body (Project Orion), built from zero to the owner's T-pose sheet
(art/reference/player/orion_tpose_bodysuit.png, read into numbers by concept.py) and the owner's canon
(2026-11-16): 8 heads tall, shoulders 2.5 heads, arm span = height, torso 3 heads, legs 4 heads.

How it is made (the way a base mesh is modelled, in code):
  * ONE all-quad cage: the torso as rings round the body, the legs split from it through the crotch, the arms
    bridged into a window on each side of the chest, the neck on top; the head, hands and feet are grafted onto
    the last ring of each (plain caps until their own modules exist);
  * every cage vertex is given a TARGET on the body's surface: the torso's cross-section at its height (width
    from the sheet's front view, depth from its side view, the shape between from anatomy: pecs, lats, the spine's
    groove, glutes), each leg's section from the leg's own outline in both views, each arm's from its outline
    along the arm;
  * the cage is then solved so its Catmull-Clark LIMIT surface passes through the targets (the limit stencil
    (n^2 v + 4 sum e + sum f) / (n (n + 5)), iterated), so the smooth body meets the sheet's outline instead of
    shrinking inside it; then subdivided.

Heights: the sheet's rows are mapped to metres through the canon's landmarks (the skull's top 1.84 m, the chin
1.61 = one head down, the crotch 0.92 = four heads up, the floor), widths at the sheet's own scale (CPX).
Coordinates: metres, Z up, the body faces -Y, its left is +X, the floor at z = 0.
"""
import json, math, os
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
STATURE = 1.84
HEAD = STATURE / 8.0                           # the owner's canon: 8 heads
CPX = 0.00383                                  # metres per pixel across the sheet
FRONT_C = 258.0                                # the front view's centre column (box pixels)
SIDE_C = 79.3                                  # the side view's column of y = 0 (the ankle at y = +3 cm)
# the sheet's rows (front view box) of the skull's top, the chin, the crotch and the floor under his bare feet
# (his shoes' soles are 2.5 cm), and where the canon puts them
LAND_ROWS = [13.0, 70.5, 262.0, 493.5]
LAND_Z = [STATURE, STATURE - HEAD, 4 * HEAD, 0.0]


def smooth1(a, sigma):
    """gaussian smoothing of a 1-D array, NaNs left out"""
    a = np.asarray(a, float)
    r = int(3 * sigma) + 1
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    ok = np.isfinite(a)
    num = np.convolve(np.where(ok, a, 0.0), k, "same")
    den = np.convolve(ok.astype(float), k, "same")
    return np.where(den > 1e-6, num / np.maximum(den, 1e-9), np.nan)


class Concept:
    """the sheet's outlines as functions of height (metres)"""

    def __init__(self, path=os.path.join(HERE, "concept_male.json")):
        J = json.load(open(path))
        f, s = J["front"], J["side"]
        self.ftop, self.stop = f["top"], s["top"]
        tl, tr, ll, lr, rl, rr = ([] for _ in range(6))
        for row in f["runs"]:
            t = [(a, b) for a, b in row if a - 1 <= FRONT_C <= b + 1]
            tl.append(t[0][0] if t else np.nan); tr.append(t[0][1] if t else np.nan)
            left = [(a, b) for a, b in row if a > FRONT_C + 1]          # the body's LEFT leg is on the image's right
            right = [(a, b) for a, b in row if b < FRONT_C - 1]
            ll.append(min(a for a, b in left) if left else np.nan); lr.append(max(b for a, b in left) if left else np.nan)
            rl.append(min(a for a, b in right) if right else np.nan); rr.append(max(b for a, b in right) if right else np.nan)
        sm = lambda a: smooth1(a, 1.6)
        self.t_l, self.t_r = sm(tl), sm(tr)
        self.leg_in, self.leg_out, self.legR_in, self.legR_out = sm(ll), sm(lr), sm(rr), sm(rl)
        sf, sb = [], []
        for row in s["runs"]:
            sf.append(max(b for a, b in row) if row else np.nan)
            sb.append(min(a for a, b in row) if row else np.nan)
        self.s_f, self.s_b = sm(sf), sm(sb)
        A = np.array(J["arm"], float)
        self.arm_dx, self.arm_top, self.arm_bot = A[:, 0], smooth1(A[:, 1], 2.0), smooth1(A[:, 2], 2.0)

    @staticmethod
    def z(row):
        """the height of a sheet row: piecewise through the canon's landmarks, carried on straight past the first
        and last (np.interp alone would hold every row above the hair at the skull's height)"""
        R, Z = LAND_ROWS, LAND_Z
        if row < R[0]:
            return Z[0] + (R[0] - row) * (Z[0] - Z[1]) / (R[1] - R[0])
        if row > R[-1]:
            return Z[-1] - (row - R[-1]) * (Z[-2] - Z[-1]) / (R[-1] - R[-2])
        return float(np.interp(row, R, Z))

    @staticmethod
    def row(z):
        R, Z = LAND_ROWS, LAND_Z
        if z > Z[0]:
            return R[0] - (z - Z[0]) * (R[1] - R[0]) / (Z[0] - Z[1])
        if z < Z[-1]:
            return R[-1] + (Z[-1] - z) * (R[-1] - R[-2]) / (Z[-2] - Z[-1])
        return float(np.interp(z, Z[::-1], R[::-1]))

    def _at(self, arr, top, z):
        r = self.row(z) - top
        i = int(np.floor(r)); t = r - i
        n = len(arr)
        a, b = arr[min(max(i, 0), n - 1)], arr[min(max(i + 1, 0), n - 1)]
        if not np.isfinite(a):
            return b
        if not np.isfinite(b):
            return a
        return a * (1 - t) + b * t

    def torso_w(self, z):
        """half the torso's width at z (front view)"""
        return 0.5 * (self._at(self.t_r, self.ftop, z) - self._at(self.t_l, self.ftop, z) + 1) * CPX

    def side(self, z):
        """(y_front, y_back) of the side view's silhouette at z"""
        return (-(self._at(self.s_f, self.stop, z) + .5 - SIDE_C) * CPX,
                -(self._at(self.s_b, self.stop, z) - .5 - SIDE_C) * CPX)

    def leg(self, z):
        """the left leg's (x_inner, x_outer) at z (front view; both legs averaged, mirrored)"""
        li, lo = self._at(self.leg_in, self.ftop, z), self._at(self.leg_out, self.ftop, z)
        ri, ro = self._at(self.legR_in, self.ftop, z), self._at(self.legR_out, self.ftop, z)
        xi = 0.5 * ((li - .5 - FRONT_C) + (FRONT_C - ri - .5)) * CPX
        xo = 0.5 * ((lo + .5 - FRONT_C) + (FRONT_C - ro + .5)) * CPX
        return xi, xo

    def arm(self, x):
        """(z_centre, half thickness) of the arm's outline at a distance x (m, the sheet's) out from the centre"""
        dx = x / CPX
        top = float(np.interp(dx, self.arm_dx, self.arm_top)) - .5
        bot = float(np.interp(dx, self.arm_dx, self.arm_bot)) + .5
        return self.z(.5 * (top + bot)), .5 * (bot - top) * CPX


# ----------------------------------------------------------------------------------------------------------------
# the body's measurements: the sheet where it shows them, the canon's lengths, adult anatomy for the rest

SHOULDER = np.array([0.178, -0.030, 1.486])     # the left glenohumeral joint
ARM_DROP = math.radians(6.0)                      # the sheet's arms hang 6 degrees below level
UPPER_ARM, FOREARM, HAND = 0.290, 0.252, 0.200    # joint to fingertip 0.742: arm span = stature; the hand 20 cm
SHEET_ARM = 0.760                                 # the sheet's own joint-to-fingertip (its arms are 2 % long)
CROTCH_Z = 4 * HEAD

T_Z = [0.968, 1.030, 1.095, 1.155, 1.215, 1.280, 1.345, 1.405, 1.488, 1.568]
T_SHAPE = {        # z: (front squareness, back squareness, widest point as a share of the depth from the front)
    0.96: (2.2, 2.6, .46), 1.09: (2.3, 2.5, .50), 1.21: (2.4, 2.5, .52), 1.35: (2.9, 2.6, .55), 1.50: (2.9, 2.5, .55),
}
N_T, N_L, N_A = 24, 16, 12                         # round the torso / neck / head's base, each leg, each arm
WINDOW = (4, 8)                                    # the left arm's window: columns 4..8 of rings 7..9


def bump(x, c, w):
    return math.exp(-0.5 * ((x - c) / w) ** 2)


def smoothstep(e0, e1, x):
    t = min(max((x - e0) / (e1 - e0), 0.0), 1.0)
    return t * t * (3 - 2 * t)


def band(z, z0, z1, soft):
    """1 between z0 and z1, eased out over `soft` on either side"""
    return smoothstep(z0 - soft, z0 + soft, z) * (1 - smoothstep(z1 - soft, z1 + soft, z))


def shape_at(z):
    ks = sorted(T_SHAPE)
    vals = np.array([T_SHAPE[k] for k in ks])
    return [float(np.interp(z, ks, vals[:, i])) for i in range(3)]


def torso_mod(theta, z):
    """anatomy on the torso's section (metres along its outward normal); theta in degrees: 0 the front midline,
    90 the side, 180 the back's midline"""
    d = 0.0
    d += .010 * band(z, 1.375, 1.52, .018) * bump(theta, 32, 20)            # the pectoral mass (its forms: anatomy.py)
    d -= .006 * band(z, 1.32, 1.54, .02) * bump(theta, 0, 7)                 # the sternum's groove

    d += .004 * band(z, 1.30, 1.43, .03) * bump(theta, 108, 22)              # lats behind the side (their form: anatomy.py)
    d += .008 * band(z, 1.38, 1.58, .03) * bump(theta, 148, 20)              # the scapulae
    d -= .010 * band(z, 1.03, 1.57, .03) * bump(theta, 180, 9)               # the spine's groove
    d += .010 * band(z, 1.03, 1.26, .03) * bump(theta, 163, 12)              # the erectors either side
    d += .016 * band(z, 0.90, 1.03, .025) * bump(theta, 154, 24)             # glutes
    d -= .022 * band(z, 0.88, 1.015, .02) * bump(theta, 180, 7)              # the cleft between them
    return d


WAIST_ADD = 0.012          # half width added at the waist (the owner: "widen the waist just a little")
THIGH_ADD = -0.007         # round the thigh against the sheet's (the owner first asked for "more natural volume",
                           # then: "tone down the muscles ... not a tank, thighs seem very big")
TONE = 0.96                # the lats', the arms' and the calves' bulk against the sheet's: athletic, not a tank


def torso_width(cc, z):
    """half the torso's own width: the sheet's below the armpits (the waist a little wider, the owner's note);
    above them its outline is the arms', so the chest narrows from the lats to the shoulder's socket"""
    if z <= 1.392:
        lats = 1 - (1 - TONE) * band(z, 1.24, 1.40, .04)
        return cc.torso_w(z) * lats + WAIST_ADD * bump(z, 1.18, .075)
    return float(np.interp(z, [1.392, 1.405, 1.488, 1.568], [cc.torso_w(1.392), .212, .186, .172]))


def torso_depth(cc, z):
    """the side view's front and back; above the armpits the arm crosses the side view, so the upper chest is held
    within the chest's own front and the upper back within the scapulae"""
    yf, yb = cc.side(z)
    if z > 1.40:
        yf = max(yf, float(np.interp(z, [1.40, 1.49, 1.57], [-.176, -.150, -.110])))
        yb = min(yb, float(np.interp(z, [1.40, 1.49, 1.57], [.122, .124, .112])))
    return yf, yb


def torso_section(cc, z, n_half=13):
    """the left half of the torso's section at z: n_half points from the front midline (k = 0) to the back's
    (k = 12), held to the sheet's width and depth"""
    w = torso_width(cc, z)
    yf, yb = torso_depth(cc, z)
    nf, nb, share = shape_at(z)
    ys = yf + share * (yb - yf)
    t = np.linspace(0, np.pi / 2, 400)
    front = np.c_[w * np.sin(t) ** (2 / nf), ys - (ys - yf) * np.cos(t) ** (2 / nf)]
    back = np.c_[w * np.cos(t) ** (2 / nb), ys + (yb - ys) * np.sin(t) ** (2 / nb)][1:]
    arc = np.vstack([front, back])
    seg = np.r_[0, np.cumsum(np.linalg.norm(np.diff(arc, axis=0), axis=1))]
    Lf = seg[len(front) - 1]
    half = (n_half - 1) // 2
    sel = np.r_[np.linspace(0, Lf, half + 1), Lf + np.linspace(0, seg[-1] - Lf, half + 1)[1:]]
    P = np.c_[np.interp(sel, seg, arc[:, 0]), np.interp(sel, seg, arc[:, 1])]
    tang = np.gradient(P, axis=0)
    nrm = np.c_[tang[:, 1], -tang[:, 0]]
    nrm /= np.linalg.norm(nrm, axis=1)[:, None] + 1e-12
    nrm[0], nrm[-1] = (0, -1), (0, 1)
    theta = np.degrees(np.arctan2(P[:, 0], -(P[:, 1] - ys)))
    P = P + nrm * np.array([torso_mod(th, z) for th in theta])[:, None]
    P[0, 0] = P[-1, 0] = 0.0
    P[:, 0] *= w / max(P[:, 0].max(), 1e-6)
    lo, hi = P[:, 1].min(), P[:, 1].max()
    P[:, 1] = yf + (P[:, 1] - lo) * (yb - yf) / max(hi - lo, 1e-6)
    return P


# ----------------------------------------------------------------------------------------------------------------

class Cage:
    """vertices (their targets), quads, a part per vertex"""

    def __init__(self):
        self.V, self.F, self.part = [], [], []

    def add(self, p, part):
        self.V.append(np.asarray(p, float))
        self.part.append(part)
        return len(self.V) - 1

    def quad(self, a, b, c, d):
        self.F.append((a, b, c, d))

    def cap_rect(self, ring, m, n, part, bulge=0.0, normal=None):
        """closes a ring of 2 (m + n) vertices with an n (along) x m (across) grid"""
        assert len(ring) == 2 * (m + n)
        G = {}
        for a in range(n + 1):
            G[(a, 0)] = ring[a]
            G[(a, m)] = ring[2 * n + m - a]
        for b in range(m + 1):
            G[(n, b)] = ring[n + b]
            G[(0, b)] = ring[(2 * n + 2 * m - b) % len(ring)]
        pos = lambda key: self.V[G[key]]
        for a in range(1, n):
            for b in range(1, m):
                u, v = a / n, b / m
                p = ((1 - v) * pos((a, 0)) + v * pos((a, m)) + (1 - u) * pos((0, b)) + u * pos((n, b))
                     - ((1 - u) * (1 - v) * pos((0, 0)) + u * (1 - v) * pos((n, 0)) + (1 - u) * v * pos((0, m))
                        + u * v * pos((n, m))))
                if normal is not None:
                    p = p + np.asarray(normal, float) * bulge * math.sin(math.pi * u) * math.sin(math.pi * v)
                G[(a, b)] = self.add(p, part)
        for a in range(n):
            for b in range(m):
                self.quad(G[(a, b)], G[(a + 1, b)], G[(a + 1, b + 1)], G[(a, b + 1)])

    def compact(self):
        """drops vertices no quad uses (a window's inside) and renumbers"""
        used = sorted({v for f in self.F for v in f})
        new = {o: n for n, o in enumerate(used)}
        self.V = [self.V[o] for o in used]
        self.part = [self.part[o] for o in used]
        self.F = [tuple(new[v] for v in f) for f in self.F]

    def strip(self, r0, r1):
        n = len(r0)
        assert n == len(r1), (n, len(r1))
        for j in range(n):
            k = (j + 1) % n
            self.quad(r0[j], r0[k], r1[k], r1[j])

    def cap(self, ring, part, bulge=0.0, normal=None):
        """closes a ring of 4m vertices with an m x m grid: a Coons patch of the ring, pushed out by `bulge` along
        `normal` in its middle"""
        n = len(ring)
        m = n // 4
        assert 4 * m == n
        G = {}
        for a in range(m + 1):
            G[(a, 0)] = ring[a]
            G[(a, m)] = ring[3 * m - a]
        for b in range(m + 1):
            G[(m, b)] = ring[m + b]
            G[(0, b)] = ring[(4 * m - b) % n]
        pos = lambda key: self.V[G[key]]
        for a in range(1, m):
            for b in range(1, m):
                u, v = a / m, b / m
                p = ((1 - v) * pos((a, 0)) + v * pos((a, m)) + (1 - u) * pos((0, b)) + u * pos((m, b))
                     - ((1 - u) * (1 - v) * pos((0, 0)) + u * (1 - v) * pos((m, 0)) + (1 - u) * v * pos((0, m))
                        + u * v * pos((m, m))))
                if normal is not None:
                    p = p + np.asarray(normal, float) * bulge * math.sin(math.pi * u) * math.sin(math.pi * v)
                G[(a, b)] = self.add(p, part)
        for a in range(m):
            for b in range(m):
                self.quad(G[(a, b)], G[(a + 1, b)], G[(a + 1, b + 1)], G[(a, b + 1)])


def build(cc=None, log=print):
    cc = cc or Concept()
    C = Cage()
    T = []
    w_lo, w_hi = WINDOW
    win_l = set(range(w_lo + 1, w_hi))
    win_r = {N_T - k for k in win_l}
    for i, z in enumerate(T_Z):
        half = torso_section(cc, z)
        ring = []
        for k in range(N_T):
            if i == 8 and (k in win_l or k in win_r):
                ring.append(None)                           # inside an arm's window
                continue
            kk = k if k <= 12 else N_T - k
            x, y = half[kk]
            ring.append(C.add((x if k <= 12 else -x, y, z), "torso"))
        T.append(ring)
    shoulder_socket(C, T)
    shoulder_top(C, T)
    for i in range(len(T) - 1):
        for k in range(N_T):
            kn = (k + 1) % N_T
            q = (T[i][k], T[i][kn], T[i + 1][kn], T[i + 1][k])
            if None in q:
                continue
            if i in (7, 8) and (w_lo <= k < w_hi or N_T - w_hi <= k < N_T - w_lo):
                continue
            C.quad(*q)
    neck = neck_rings(C)
    C.strip(T[-1], neck[0])
    for r0, r1 in zip(neck, neck[1:]):
        C.strip(r0, r1)
    crotch = crotch_verts(C, T[0])
    legs = {sx: leg(C, T[0], crotch, sx, cc) for sx in (1, -1)}
    arms = {sx: arm(C, T, sx, cc) for sx in (1, -1)}
    # placeholders until the head, hands and feet are grafted on
    C.cap(neck[-1], "head", .10, (0, 0, 1))
    import hand as hand_mod
    import foot as foot_mod
    frames, feet = [], []
    for sx in (1, -1):
        S_, a, up, back = arm_axis(sx)
        F = hand_mod.Frame(S_ + a * (UPPER_ARM + FOREARM), a, up, sx)
        frames.append(F)
        hand_mod.build_hand(C, arms[sx][-1], F, log=log)
        ank = np.mean([C.V[v] for v in legs[sx][-1]], axis=0)
        FF = foot_mod.Frame((ank[0], ank[1] + .004, ank[2]), sx)
        feet.append(FF)
        foot_mod.build_foot(C, legs[sx][-3:], FF, log=log)
    C.compact()
    log(f"cage: {len(C.V)} vertices, {len(C.F)} quads")
    return C, dict(T=T, neck=neck, legs=legs, arms=arms, crotch=crotch, hands=frames, feet=feet)


# --- the shoulder: a window of 12 round each arm's socket ------------------------------------------------------------

WIN_C = np.array([0.196, -0.024, 1.488])          # the left socket's centre on the chest's side
WIN_AY, WIN_AZ = 0.074, 0.084                      # its half depth (y) and half height (z)


def window_angles():
    """psi of the 12 window vertices (degrees: 0 back, 90 up, 180 front, 270 down) in loop order from the armpit's
    front corner: evenly spaced, so the arm's rings need not twist"""
    return [210 + 30 * j for j in range(12)]


def socket_point(psi, sx=1):
    p = math.radians(psi)
    c, s = math.cos(p), math.sin(p)
    x = WIN_C[0] - .012 * max(-s, 0) ** 1.5 + .004 * c - .006 * max(s, 0)     # the armpit sits in a little
    return np.array([sx * x, WIN_C[1] + WIN_AY * c, WIN_C[2] + WIN_AZ * s])


def window_loop(T, sx):
    col = (lambda k: k) if sx > 0 else (lambda k: N_T - k)
    return ([T[7][col(k)] for k in range(4, 9)] + [T[8][col(8)]] + [T[9][col(k)] for k in range(8, 3, -1)]
            + [T[8][col(4)]])


def shoulder_socket(C, T):
    for sx in (1, -1):
        for v, psi in zip(window_loop(T, sx), window_angles()):
            C.V[v] = socket_point(psi, sx)


# ring 9 away from the windows: the clavicles in front (rising gently to the shoulder), the trapezius and the
# scapulae's spine behind (columns 0..3 and 9..12 of the left side; the right mirrors them)
T9_FRONT = [(0.000, -.104, 1.512), (0.048, -.101, 1.520), (0.094, -.096, 1.531), (0.140, -.090, 1.545)]
T9_BACK = [(0.150, .092, 1.574), (0.104, .110, 1.582), (0.052, .118, 1.586), (0.000, .112, 1.584)]


def shoulder_top(C, T):
    for k in range(N_T):
        kk = k if k <= 12 else N_T - k
        sx = 1 if k <= 12 else -1
        if kk <= 3:
            x, y, z = T9_FRONT[kk]
        elif kk >= 9:
            x, y, z = T9_BACK[kk - 9]
        else:
            continue
        C.V[T[9][k]] = np.array([sx * x, y, z])


def neck_rings(C):
    """the neck's base and two rings up it, tilted (the front from the sternum's notch, the back from the 7th
    vertebra up), the sternomastoids either side of the windpipe"""
    rings = []
    for zf, zb, w, yf, yb in [(1.548, 1.630, .084, -.071, .078),
                              (1.590, 1.672, .071, -.066, .068),
                              (1.626, 1.712, .066, -.061, .062)]:
        ring = []
        for k in range(N_T):
            a = 2 * math.pi * k / N_T                    # 0 front, pi/2 left, pi back
            s, c = math.sin(a), math.cos(a)
            y = yf * c if c > 0 else -yb * c
            z = zf + (zb - zf) * (1 - c) / 2
            r = 1 + .06 * bump(abs(math.degrees(a) - 180), 130, 22)
            ring.append(C.add((w * s * r, y * r, z), "neck"))
        rings.append(ring)
    return rings


# --- legs --------------------------------------------------------------------------------------------------------

L_Z = [0.875, 0.800, 0.725, 0.650, 0.585, 0.540, 0.500, 0.460, 0.410, 0.345, 0.270, 0.200, 0.135, 0.095]


def crotch_verts(C, T0):
    """the three vertices under the crotch, shared by both legs' first rings: front, the perineum, back"""
    p0, p12 = C.V[T0[0]], C.V[T0[12]]
    c1 = C.add((0.0, p0[1] * .55 + .006, CROTCH_Z - .004), "torso")
    c2 = C.add((0.0, .5 * (p0[1] + p12[1]) - .005, CROTCH_Z - .020), "torso")
    c3 = C.add((0.0, p12[1] * .55 - .02, CROTCH_Z - .006), "torso")
    return [c1, c2, c3]


def leg_mod(phi, z):
    """anatomy on the leg's section (metres): phi 0 front, 90 outside, 180 back, 270 inside"""
    d = 0.0
    th = band(z, 0.60, 0.87, .04)
    d += .008 * th * bump(phi, 40, 30)                                   # rectus and vastus lateralis
    d += .004 * th * bump(phi, 105, 20)
    d += .006 * band(z, 0.565, 0.67, .03) * bump(phi, 320, 22)           # the vastus medialis' teardrop
    d += .005 * band(z, 0.64, 0.84, .04) * bump(phi, 200, 30)            # hamstrings
    d -= .004 * band(z, 0.66, 0.89, .04) * bump(phi, 275, 25)            # the inner thigh's flat
    d += .004 * band(z, 0.495, 0.545, .015) * bump(phi, 0, 22)           # the kneecap
    d -= .004 * band(z, 0.48, 0.55, .02) * bump(phi, 180, 25)            # behind the knee
    d += .010 * band(z, 0.32, 0.46, .04) * bump(phi, 200, 30)            # the calf, its inner head lower
    d += .006 * band(z, 0.29, 0.42, .04) * bump(phi, 235, 22)
    d -= .003 * band(z, 0.16, 0.46, .03) * bump(phi, 350, 18)            # the shin's flat face
    d += .004 * band(z, 0.075, 0.115, .015) * (bump(phi, 92, 16) + bump(phi, 268, 16))   # the ankle bones
    d -= .004 * band(z, 0.10, 0.21, .03) * (bump(phi, 150, 15) + bump(phi, 210, 15))   # either side of the heel's tendon
    return d


def leg_section(cc, z, sx, n=N_L, phi0=None):
    if phi0 is None:
        phi0 = 320.0 + 6.25 * smoothstep(0.80, 0.095, z)
    xi, xo = cc.leg(z)
    yf, yb = cc.side(z)
    xc, a = .5 * (xi + xo), .5 * (xo - xi)
    yc, b = .5 * (yf + yb), .5 * (yb - yf)
    full = THIGH_ADD * band(z, 0.58, 0.86, .06)            # the thigh's volume against the sheet's
    a, xc, b, yc = a + .75 * full, xc + .25 * full, b + full, yc - .3 * full
    a = a + .007 * math.exp(-((z - .51) / .045) ** 2)                     # the knee: not pinched
    calf = 1 - (1 - TONE) * band(z, 0.20, 0.46, .05)
    a, b = a * calf, b * calf
    ank = smoothstep(0.27, 0.11, z) ** 1.3
    a, b = a + (.035 - a) * ank, b + (.045 - b) * ank
    xc, yc = xc + (.207 - xc) * ank, yc + (.030 - yc) * ank
    pts = []
    for j in range(n):
        phi = (phi0 + 360.0 * j / n) % 360
        p = math.radians(phi)
        s, c = math.sin(p), math.cos(p)
        e = 2.3
        x = a * math.copysign(abs(s) ** (2 / e), s)
        y = -b * math.copysign(abs(c) ** (2 / e), c)
        r = math.hypot(x, y) + 1e-9
        d = leg_mod(phi, z)
        x, y = x + d * x / r, y + d * y / r
        pts.append((sx * (xc + x), yc + y, z))
    return pts


def leg(C, T0, crotch, sx, cc):
    """the leg's first ring is the torso's lowest from the front midline round the outside to the back's midline
    and back under the crotch; the rest are its own, every ring going round the same way"""
    c1, c2, c3 = crotch
    if sx > 0:
        L0 = [T0[k] for k in range(0, 13)] + [c3, c2, c1]
    else:
        L0 = [T0[0], c1, c2, c3] + [T0[k] for k in range(12, N_T)]
    rings = [L0]
    for z in L_Z:
        pts = leg_section(cc, z, sx)
        if sx < 0:
            # the left ring starts front-inside and goes out round the front; mirrored, the right one must start at
            # the same place and run the other way: its j-th point is the left ring's (N - j)-th, rotated so its
            # first point sits by the front midline as L0's does
            pts = [pts[0]] + pts[1:][::-1]
        rings.append([C.add(p, "leg") for p in pts])
    for r0, r1 in zip(rings, rings[1:]):
        C.strip(r0, r1)
    return rings


# --- arms --------------------------------------------------------------------------------------------------------

A_S = [0.058, 0.097, 0.143, 0.195, 0.244, 0.290, 0.330, 0.384, 0.437, 0.490, 0.542]


def arm_axis(sx):
    a = np.array([sx * math.cos(ARM_DROP), 0.0, -math.sin(ARM_DROP)])
    up = np.array([sx * math.sin(ARM_DROP), 0.0, math.cos(ARM_DROP)])
    back = np.array([0.0, 1.0, 0.0])
    S = SHOULDER.copy(); S[0] *= sx
    return S, a, up, back


def arm_mod(psi, s):
    """anatomy round the arm (metres): psi 0 back, 90 up (the outside when it hangs), 180 front, 270 down"""
    d = 0.0
    d += .010 * band(s, 0.05, 0.15, .03) * bump(psi, 95, 45)             # the deltoid over the top
    d += .006 * band(s, 0.12, 0.25, .03) * bump(psi, 185, 30)            # biceps
    d += .005 * band(s, 0.10, 0.23, .03) * bump(psi, 20, 35)             # triceps
    d -= .004 * band(s, 0.265, 0.30, .02) * bump(psi, 190, 25)           # the elbow's crease
    d += .006 * band(s, 0.30, 0.41, .03) * bump(psi, 140, 30)            # brachioradialis and the extensors
    d += .004 * band(s, 0.30, 0.42, .03) * bump(psi, 300, 30)            # the flexors underneath
    return d


def arm(C, T, sx, cc):
    S, a, up, back = arm_axis(sx)
    rings = [window_loop(T, sx)]
    for s in A_S:
        P = S + a * s
        # the sheet's outline at the same share of the arm (its arms are 2 % long)
        x_sheet = SHOULDER[0] + (abs(P[0]) - SHOULDER[0]) * SHEET_ARM / (UPPER_ARM + FOREARM + HAND)
        zc, rv = cc.arm(x_sheet)
        rv *= TONE
        rh = rv * float(np.interp(s, [0.058, 0.25, 0.29], [1.02, .97, .95]))
        # from below the elbow: the forearm's own thickness (vertical, back to palm) and width (across)
        fa_s = [0.29, 0.33, 0.38, 0.44, 0.49, 0.542]
        fa_v = [.042, .040, .035, .029, .024, .020]
        fa_h = [.040, .045, .042, .037, .034, .031]
        k = smoothstep(0.27, 0.33, s)
        rv = rv * (1 - k) + float(np.interp(s, fa_s, fa_v)) * k
        rh = rh * (1 - k) + float(np.interp(s, fa_s, fa_h)) * k
        zc = zc * (1 - k) + P[2] * k
        centre = P.copy(); centre[2] = zc
        ring = []
        twist = 15.0 * smoothstep(0.30, 0.542, s)
        for psi0 in window_angles():
            psi = psi0 + twist
            p = math.radians(psi)
            off = back * (rh * math.cos(p)) + up * (rv * math.sin(p))
            off = off + off / (np.linalg.norm(off) + 1e-9) * arm_mod(psi, s)
            ring.append(C.add(centre + off, "arm"))
        rings.append(ring)
    for r0, r1 in zip(rings, rings[1:]):
        C.strip(r0, r1)
    return rings


# ----------------------------------------------------------------------------------------------------------------
# the limit surface through the targets

def limit_operator(n, F):
    """the limit stencil of a closed all-quad Catmull-Clark mesh as (rows, cols, weights): limit = M @ cage"""
    nbr = [set() for _ in range(n)]
    diag = [[] for _ in range(n)]
    for f in F:
        for i in range(4):
            v = f[i]
            nbr[v].add(f[(i + 1) % 4]); nbr[v].add(f[(i - 1) % 4])
            diag[v].append(f[(i + 2) % 4])
    R, Cc, W = [], [], []
    for v in range(n):
        k = len(nbr[v])
        den = k * (k + 5.0)
        R.append(v); Cc.append(v); W.append(k * k / den)
        for e in nbr[v]:
            R.append(v); Cc.append(e); W.append(4.0 / den)
        for f in diag[v]:
            R.append(v); Cc.append(f); W.append(1.0 / den)
    return np.array(R), np.array(Cc), np.array(W)


def apply_op(op, X):
    R, Cc, W = op
    out = np.zeros_like(X)
    np.add.at(out, R, W[:, None] * X[Cc])
    return out


def solve_cage(V, F, iters=80, log=print, free=None):
    """cage positions whose limit surface passes through V (the targets). free: per vertex 0..1, how much it is
    left as its own target instead (the limit surface then runs a little inside it, never overshooting: toes
    between toes, where an exact fit pushed neighbouring sides into each other)"""
    P = np.asarray(V, float)
    op = limit_operator(len(P), F)
    X = P.copy()
    keep = 1.0 if free is None else (1.0 - np.asarray(free, float))[:, None]
    for it in range(iters):
        err = P - apply_op(op, X)
        X += err * keep
        if it in (0, iters - 1):
            e = np.linalg.norm(err, axis=1)
            log(f"limit fit {it}: mean {e.mean() * 1000:.2f} mm, max {e.max() * 1000:.2f} mm")
    return X
