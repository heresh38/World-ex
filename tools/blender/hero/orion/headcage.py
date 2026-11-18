"""His game head (Project Orion male): an all-quad cage of its own, built on the body's neck and laid on the head's
sculpt (head.py), so the game has a head with real edge loops where a face needs them (the owner, 2026-11-17: "put the
player in the game", "don't use things made for the old model"). Built the way the body is: rings round it, windows
cut for what is not a ring.

  * the neck's top ring (24, the body's) widens in one band to the head's rings of 40: over the face (+-60 degrees)
    every 15-degree column splits in three (5 degrees a column there), behind it stays 15 (the face needs the
    resolution, the back of the head does not);
  * 15 rings up the head, tilted at the bottom along the jaw (under the chin in front, the nape behind) and level
    from the nose up, each vertex where a ray from the head's axis leaves the sculpt;
  * the eyes: a window of 7 x 1 cells each, inset three times (the orbit, the lid, the lid's margin round the eye's
    opening, 16 vertices, on the eyeball); the mouth: 6 x 1 cells inset three times (round the mouth, the lips'
    border, the line they meet on), closed by a row of thin quads (the lips together); the nose: 2 x 2 cells pushed
    forward and capped (its tip the cap's middle); the ears: 2 x 3 cells each pushed out and capped;
  * over the crown the 40 narrow back to 24 and a 6 x 6 grid closes it.
Every vertex gets a target on the sculpt; the cage is solved with the body's (body.solve_cage) and the subdivided
skin is laid onto the sculpt (lay_on_head)."""
import math
import numpy as np
import head as H

F32 = np.float32
# the columns round the head (degrees, 0 the face's midline, + toward his left)
ANG = list(range(0, 60, 5)) + list(range(60, 300, 15)) + list(range(300, 360, 5))
NA = len(ANG)                                                       # 40
# the rings (head frame, cm): (height at the front, height at the back): along the jaw, then level
RINGS = [(-12.4, -6.6), (-11.2, -5.6), (-10.3, -4.8), (-9.2, -4.0), (-5.4, -3.0), (-4.6, -2.7), (-3.3, -2.2),
         (-1.5, -1.3), (1.7, 1.7), (3.0, 3.0), (4.4, 4.4), (6.0, 6.0), (7.6, 7.6), (9.0, 9.0), (10.2, 10.2)]
CROWN = 10.9                                                        # the ring of 24 under the crown's cap
NECK = [(-15.4, -9.6), (-13.9, -8.0)]                               # the body's two upper neck rings, on the sculpt
# the windows: (first column's angle, last's, first ring, last ring)
EYE_WIN = (5, 40, 7, 8)
MOUTH_WIN = (-25, 25, 3, 4)          # wider and taller than the lips' loops inside it (narrower, they folded)
NOSE_WIN = (-15, 15, 5, 6)           # the tip and the wings (narrower, the nose came out a block); the bridge is rings
EAR_WIN = (90, 120, 3, 8)            # round the ear's root: it stands back from the canal and hangs low


def col(a):
    """the 40-column index of an angle (degrees)"""
    return ANG.index(int(round(a)) % 360)


def zr(ring_h, a):
    """a ring's height at angle a (degrees): its front's and back's, eased round the head"""
    zf, zb = ring_h
    return zf + (zb - zf) * (1 - math.cos(math.radians(a))) / 2


class HeadField:
    """the sculpt (head.py) in the head's frame (cm in, cm out), and rays through it"""

    def __init__(self, params=None):
        self.hd = H.Head(params)

    def f(self, Q):
        return self.hd.cm(np.asarray(Q, F32))

    def exit(self, O, D, t0=.3, t1=16.0, n=480, from_inside=True):
        """the first point along O + t D (t in cm) where the sculpt is left (from inside) / met (from outside)"""
        O = np.asarray(O, F32); D = np.asarray(D, F32)
        ts = np.linspace(t0, t1, n, dtype=F32)
        P = O[:, None, :] + D[:, None, :] * ts[None, :, None]
        v = self.f(P.reshape(-1, 3)).reshape(len(O), n)
        hit = v > 0 if from_inside else v < 0
        k = np.where(hit.any(1), hit.argmax(1), n - 1)
        a, b = ts[np.maximum(k - 1, 0)], ts[k]
        for _ in range(14):
            m = .5 * (a + b)
            vm = self.f(O + D * m[:, None])
            before = (vm <= 0) if from_inside else (vm >= 0)
            a = np.where(before, m, a); b = np.where(before, b, m)
        return O + D * (.5 * (a + b))[:, None]

    def radial(self, z, angles):
        """points on the sculpt at height z (array) along rays from the head's axis at `angles` (degrees)"""
        a = np.radians(np.asarray(angles, float))
        O = np.c_[np.zeros(len(a)), np.full(len(a), H.YC), np.asarray(z, float)].astype(F32)
        D = np.c_[np.sin(a), -np.cos(a), np.zeros(len(a))].astype(F32)
        return self.exit(O, D)

    def front(self, x, z, y0=-17.0):
        """points on the sculpt seen from in front: rays from y0 straight back at (x, z)"""
        x = np.asarray(x, float); z = np.asarray(z, float)
        O = np.c_[x, np.full(len(x), y0), z].astype(F32)
        D = np.tile(np.array([0, 1, 0], F32), (len(x), 1))
        return self.exit(O, D, t0=0.0, t1=12.0, n=600, from_inside=False)

    def side(self, y, z, sx, x0=16.0):
        """points on the sculpt seen from his side (sx = 1 his left): rays from x0 straight in at (y, z)"""
        y = np.asarray(y, float); z = np.asarray(z, float)
        O = np.c_[np.full(len(y), sx * x0), y, z].astype(F32)
        D = np.tile(np.array([-sx, 0, 0], F32), (len(y), 1))
        return self.exit(O, D, t0=0.0, t1=16.0, n=640, from_inside=False)


def ring_points(hf, ring_h, angles):
    """a ring's points on the sculpt; through an eye's socket a ray finds the pocket the eyeball sits in, so there
    the face's own radius is taken from just over and under it"""
    z = np.array([zr(ring_h, a) for a in angles], F32)
    P = hf.radial(z, angles)
    r = np.hypot(P[:, 0], P[:, 1] - H.YC)
    a = np.asarray(angles, float) % 360
    eye = ((a > 0) & (a < 50)) | ((a > 310) & (a < 360))
    lo = (z > -2.0) & (z < 2.2) & eye & (r < 8.6)
    if lo.any():
        Pa = hf.radial(z[lo] + 1.6, np.asarray(angles)[lo])
        Pb = hf.radial(z[lo] - 1.6, np.asarray(angles)[lo])
        rr = .5 * (np.hypot(Pa[:, 0], Pa[:, 1] - H.YC) + np.hypot(Pb[:, 0], Pb[:, 1] - H.YC))
        ang = np.radians(np.asarray(angles, float)[lo])
        P[lo, 0] = np.sin(ang) * rr
        P[lo, 1] = H.YC - np.cos(ang) * rr
    return P


def build_head(C, neck, log=print, params=None):
    """adds the head to the body's cage C on its neck rings `neck` (lists of 24, k = 0 the front, 6 his left); returns
    what the fit and the face keys need (the head's vertices, its features' loops)"""
    hf = HeadField(params)
    toW = lambda q: np.array([q[0] / 100, H.Y0 + q[1] / 100, H.Z0 + q[2] / 100])
    placed = set()

    def put(v, q):
        C.V[v] = toW(q); placed.add(v)
    # the body's two upper neck rings onto the sculpt (in the lab they were drawn in under its head)
    na = [15 * k for k in range(24)]
    for ring, rh in zip(neck[-2:], NECK):
        for v, q in zip(ring, ring_points(hf, rh, na)):
            put(v, q)
    top24 = neck[-1]
    # ---- the head's rings of 40
    rings = []
    for rh in RINGS:
        rg = [C.add(np.zeros(3), "head") for _ in ANG]
        for v, q in zip(rg, ring_points(hf, rh, ANG)):
            put(v, q)
        rings.append(rg)

    def triple(a, b, top, below=True):
        """one segment (a, b) to three (top: four vertices); below = the one is under the three"""
        c_, d_, e_, f_ = top
        pa, pb = C.V[a], C.V[b]
        m1 = C.add(.5 * (pa + (pb - pa) / 3) + .5 * C.V[d_], "head")
        m2 = C.add(.5 * (pa + (pb - pa) * 2 / 3) + .5 * C.V[e_], "head")
        if below:
            C.quad(a, m1, d_, c_); C.quad(m1, m2, e_, d_); C.quad(m2, b, f_, e_); C.quad(a, b, m2, m1)
        else:
            C.quad(c_, d_, m1, a); C.quad(d_, e_, m2, m1); C.quad(e_, f_, b, m2); C.quad(m1, m2, b, a)
    # ---- the band from the neck's 24 to the first ring of 40: each front segment to three
    R0 = rings[0]
    for j in range(24):
        a0 = 15 * j
        c0, c1 = col(a0), col((a0 + 15) % 360)
        a, b = top24[j], top24[(j + 1) % 24]
        if a0 < 60 or a0 >= 300:
            triple(a, b, [R0[(c0 + i) % NA] for i in range(4)])
        else:
            C.quad(a, b, R0[c1], R0[c0])
    # ---- the strips between the rings, the windows left open
    wins = {"eye_L": EYE_WIN, "eye_R": (-EYE_WIN[1], -EYE_WIN[0], EYE_WIN[2], EYE_WIN[3]), "mouth": MOUTH_WIN,
            "nose": NOSE_WIN, "ear_L": EAR_WIN, "ear_R": (-EAR_WIN[1], -EAR_WIN[0], EAR_WIN[2], EAR_WIN[3])}

    def cols_of(a0, a1):
        c = col(a0); cs = [c]
        while cs[-1] != col(a1):
            cs.append((cs[-1] + 1) % NA)
        return cs
    cells = set()
    for a0, a1, r0, r1 in wins.values():
        cs = cols_of(a0, a1)
        for ci in cs[:-1]:
            for ri in range(r0, r1):
                cells.add((ci, ri))
    for ri in range(len(rings) - 1):
        r0, r1 = rings[ri], rings[ri + 1]
        for ci in range(NA):
            if (ci, ri) in cells:
                continue
            k = (ci + 1) % NA
            C.quad(r0[ci], r0[k], r1[k], r1[ci])

    def window_loop(name):
        """the window's border: along the bottom ring, up the far side, back along the top, down the near side"""
        a0, a1, r0, r1 = wins[name]
        cs = cols_of(a0, a1)
        bottom = [rings[r0][c] for c in cs]
        right = [rings[r][cs[-1]] for r in range(r0 + 1, r1)]
        top = [rings[r1][c] for c in reversed(cs)]
        left = [rings[r][cs[0]] for r in range(r1 - 1, r0, -1)]
        return bottom + right + top + left, len(cs) - 1, r1 - r0

    def inset(loop, part="head"):
        inner = [C.add(C.V[v], part) for v in loop]
        for i in range(len(inner)):
            j = (i + 1) % len(inner)
            C.quad(loop[i], loop[j], inner[j], inner[i])
        return inner
    feats = {}
    # ---- the eyes: three loops in; the innermost the lid's margin, on the eyeball round the opening
    hd = hf.hd
    for side, sx in (("eye_L", 1), ("eye_R", -1)):
        loop, n, m = window_loop(side)                              # n + 1 along the bottom, n + 1 back on top
        loops = [loop]
        for _ in range(3):
            loops.append(inset(loops[-1]))
        nb = n + 1
        # along the window's bottom from its first column: inner to outer on his left, outer to inner on his right
        # (laid the same way on both, the right eye's loops crossed their window's and twisted the cage)
        u = np.linspace(.03, .97, nb) if sx > 0 else np.linspace(.97, .03, nb)
        x = H.EN[0] + (H.EX[0] - H.EN[0]) * u
        z0 = H.EN[1] + (H.EX[1] - H.EN[1]) * u
        lid_up = hd.k("eye_open")
        zu = z0 + H.LID_UP * lid_up * np.sin(np.pi * u ** .82) ** .85
        zl = z0 - H.LID_LO * lid_up * np.sin(np.pi * u ** 1.28) ** 1.05
        ex_, ey_, ez_ = H.EYE
        Rm = H.EYE_R + .06
        for k, (gw, gh) in ((3, (1.0, 1.0)), (2, (1.22, 1.55)), (1, (1.46, 2.25))):
            xs = ex_ + (x - ex_) * gw
            zt = ez_ + (zu - ez_) * gh + (.25 if k == 1 else 0)
            zb = ez_ + (zl - ez_) * gh
            X = np.r_[xs, xs[::-1]] * sx
            Z = np.r_[zb, zt[::-1]]
            if k == 3:                                               # on the globe, just over it
                dx, dz = np.abs(X) - ex_, Z - ez_
                Y = ey_ - np.sqrt(np.maximum(Rm * Rm - dx * dx - dz * dz, .01))
                Q = np.c_[X, Y, Z]
            else:
                Q = hf.front(X, Z)
            for v, q in zip(loops[k], Q):
                put(v, q)
        feats[side] = loops
        for k, w in ((3, 1.0), (2, .6), (1, .25)):
            for v in loops[k]:
                C.soft[v] = max(C.soft.get(v, 0.0), w)
    # ---- the mouth: three loops in, closed by a row of thin quads (the lips together)
    loop, n, m = window_loop("mouth")
    loops = [loop]
    for _ in range(3):
        loops.append(inset(loops[-1]))
    nb = n + 1
    last = loops[-1]
    for i in range(n):
        C.quad(last[i], last[i + 1], last[2 * nb - 2 - i], last[2 * nb - 1 - i])
    xs = np.linspace(-1, 1, nb) * H.MOUTH_W if hasattr(H, "MOUTH_W") else np.linspace(-1, 1, nb) * 2.58
    ax = np.abs(xs)
    st = hd.stom(ax * .98)
    up, lo = hd.up_top(ax * .98), hd.lo_bot(ax * .98)
    for k, (wx, du, dl) in ((3, (.98, .05, .05)), (2, (1.04, 0, 0)), (1, (1.20, .50, .50))):
        if k == 3:
            zt, zb = st + du, st - dl
        else:
            zt, zb = up + du, lo - dl
        X = np.r_[xs * wx, (xs * wx)[::-1]]
        Z = np.r_[zb, zt[::-1]]
        for v, q in zip(loops[k], hf.front(X, Z)):
            put(v, q)
    feats["mouth"] = loops
    for k, w in ((3, 1.0), (2, .6), (1, .25)):
        for v in loops[k]:
            C.soft[v] = max(C.soft.get(v, 0.0), w)
    # ---- the nose: its window's border lifted forward, capped; the cap's middle its tip
    loop, n, m = window_loop("nose")
    frontl = [C.add(C.V[v], "head") for v in loop]
    for i in range(len(frontl)):
        j = (i + 1) % len(frontl)
        C.quad(loop[i], loop[j], frontl[j], frontl[i])
    before = len(C.V)
    C.cap_rect(frontl, m, n, "head")
    tipv = list(range(before, len(C.V)))
    nb = n + 1
    zb_, zt_ = H.SUBNASALE[0] + .25, H.TIP[0] + .75                  # the wings' bottom, over the tip
    xb = np.linspace(-1, 1, nb) * float(hd.n_half(np.array([zb_]))[0]) * .92
    xt = np.linspace(-1, 1, nb) * float(hd.n_half(np.array([zt_]))[0]) * .92
    X = np.r_[xb, xt[::-1]]
    Z = np.r_[np.full(nb, zb_), np.full(nb, zt_)]
    for v, q in zip(frontl, hf.front(X, Z)):
        put(v, q)
    if tipv:
        for v, q in zip(tipv, hf.front(np.zeros(len(tipv)), np.full(len(tipv), H.TIP[0]))):
            put(v, q)
    feats["nose"] = (loop, frontl, tipv)
    for v in frontl + tipv:
        C.soft[v] = max(C.soft.get(v, 0.0), .4)
    # ---- the ears: their windows' borders lifted out round the rim, capped over the auricle
    for side, sx in (("ear_L", 1), ("ear_R", -1)):
        loop, n, m = window_loop(side)
        out = [C.add(C.V[v], "head") for v in loop]
        for i in range(len(out)):
            j = (i + 1) % len(out)
            C.quad(loop[i], loop[j], out[j], out[i])
        before = len(C.V)
        C.cap_rect(out, m, n, "head")
        inner = list(range(before, len(C.V)))
        P0 = np.array([C.V[v] for v in loop])
        Q0 = np.c_[P0[:, 0] * 100, (P0[:, 1] - H.Y0) * 100, (P0[:, 2] - H.Z0) * 100]
        # the ear's own slice (it stands clear of the head there): its middle, and its outline toward each of the
        # window's vertices
        XS = 8.6
        gy, gz = np.meshgrid(np.linspace(-5, 6, 111), np.linspace(-7, 6, 131))
        G = np.c_[np.full(gy.size, sx * XS), gy.ravel(), gz.ravel()].astype(F32)
        ins = hf.f(G) < 0
        yc, zc = float(G[ins, 1].mean()), float(G[ins, 2].mean())
        wy, wz = Q0[:, 1].mean(), Q0[:, 2].mean()
        th = np.arctan2(Q0[:, 2] - wz, Q0[:, 1] - wy)
        O = np.c_[np.full(len(th), sx * XS), np.full(len(th), yc), np.full(len(th), zc)].astype(F32)
        D = np.c_[np.zeros(len(th)), np.cos(th), np.sin(th)].astype(F32)
        rim = hf.exit(O, D, t0=.05, t1=8.0, n=320)
        rim = rim - D * .25                                            # just inside the rim's edge
        for v, q in zip(out, rim):
            put(v, q)
        Pin = np.array([C.V[v] for v in inner])
        k_ = len(inner)
        Ys = yc + (np.linspace(-1, 1, k_) * .6 if k_ > 1 else np.zeros(1))
        Zs = zc + (np.linspace(1, -1, k_) * 1.6 if k_ > 1 else np.zeros(1))
        for v, q in zip(inner, hf.side(Ys, Zs, sx)):
            put(v, q)
        feats[side] = (loop, out, inner)
        for v in out + inner:
            C.soft[v] = max(C.soft.get(v, 0.0), .5)
    # ---- the crown: 40 back to 24 (each front column's three to one), a 6 x 6 cap
    top40 = rings[-1]
    top24h = [C.add(np.zeros(3), "head") for _ in range(24)]
    for v, q in zip(top24h, ring_points(hf, (CROWN, CROWN), na)):
        put(v, q)
    for j in range(24):
        a0 = 15 * j
        c0, c1 = col(a0), col((a0 + 15) % 360)
        a, b = top24h[j], top24h[(j + 1) % 24]
        if a0 < 60 or a0 >= 300:
            triple(a, b, [top40[(c0 + i) % NA] for i in range(4)], below=False)
        else:
            C.quad(top40[c0], top40[c1], b, a)
    C.cap(top24h, "head", .006, (0, 0, 1))
    # ---- whatever was made between placed vertices (the bands' inner vertices, the caps' grids): onto the sculpt
    # along a ray from the head's axis
    head_vs = [v for v in range(len(C.V)) if C.part[v] == "head"]
    rest = [v for v in head_vs if v not in placed]
    if rest:
        P = np.array([C.V[v] for v in rest])
        Q = np.c_[P[:, 0] * 100, (P[:, 1] - H.Y0) * 100, (P[:, 2] - H.Z0) * 100]
        ang = np.degrees(np.arctan2(Q[:, 0], -(Q[:, 1] - H.YC)))
        top = Q[:, 2] > 10.0
        Qr = hf.radial(Q[:, 2], ang)
        if top.any():                                                # the cap: straight up from inside
            O = Q[top] * np.array([1, 1, 0]) + np.array([0, 0, 2.0])
            O[:, 1] = Q[top, 1]
            Qr[top] = hf.exit(O.astype(F32), np.tile(np.array([0, 0, 1], F32), (int(top.sum()), 1)))
        for v, q in zip(rest, Qr):
            put(v, q)
    log(f"head cage: {len(head_vs)} vertices, {len(rest)} laid by rays")
    return dict(field=hf, rings=rings, feats=feats, top24=top24h, verts=head_vs)


def lay_on_head(P, N, w, hf, edges=None, faces=None, rounds=12, log=print):
    """the subdivided skin laid onto the sculpt: each vertex of the head (w its share, carried down from the cage)
    moved to the NEAREST point of the sculpt (steps down its gradient), then the vertices spaced evenly over it (each
    toward its neighbours' middle within the surface), again, a round at a time; the eyes' openings held. A step along
    each vertex's own normal crossed other parts of the surface under the nose and in the ears (crumpled)"""
    P = np.asarray(P, np.float64).copy()
    w = np.clip(np.asarray(w, np.float64), 0, 1)
    on = np.flatnonzero(w > .01)
    if not len(on):
        return P
    toQ = lambda X: np.c_[X[:, 0] * 100, (X[:, 1] - H.Y0) * 100, (X[:, 2] - H.Z0) * 100].astype(F32)

    def f_m(X):                                                       # metres
        return hf.f(toQ(X)).astype(np.float64) / 100

    def grad(X, e=.0004):
        g = np.zeros_like(X)
        for k in range(3):
            d = np.zeros(3); d[k] = e
            g[:, k] = (f_m(X + d) - f_m(X - d)) / (2 * e)
        n = np.linalg.norm(g, axis=1)
        return g / np.maximum(n, 1e-9)[:, None]

    def project(X, steps=4):
        for _ in range(steps):
            d = f_m(X)
            X = X - grad(X) * np.clip(d, -.004, .004)[:, None]
        return X
    n = len(P)
    hold = np.zeros(n, bool)
    if faces is not None:                                             # the eyes' openings (edges with one face)
        F = np.asarray(faces)
        e = np.sort(np.c_[F.ravel(), np.roll(F, -1, axis=1).ravel()], axis=1)
        uniq, cnt = np.unique(e, axis=0, return_counts=True)
        hold[uniq[cnt == 1].ravel()] = True
    X0 = P[on].copy()
    P[on] = project(P[on])
    if edges is not None:
        e0, e1 = edges[:, 0], edges[:, 1]
        deg = np.maximum(np.bincount(e0, minlength=n) + np.bincount(e1, minlength=n), 1).astype(np.float64)
        moving = on[~hold[on]]
        for r in range(rounds):
            acc = np.zeros((n, 3))
            for c in range(3):
                acc[:, c] = np.bincount(e0, weights=P[e1, c], minlength=n) + np.bincount(e1, weights=P[e0, c], minlength=n)
            L = acc[moving] / deg[moving, None] - P[moving]
            g = grad(P[moving])
            L -= g * (L * g).sum(1)[:, None]                          # within the surface
            P[moving] += .5 * L * w[moving, None]
            P[moving] = project(P[moving], steps=2)
    # where the head's share fades (down the neck) the old place keeps its share
    P[on] = X0 + (P[on] - X0) * w[on, None]
    moved = np.linalg.norm(P[on] - X0, axis=1)
    log(f"head laid on its sculpt: {len(on)} vertices, moved {np.median(moved) * 1000:.1f} mm (median), "
        f"{moved.max() * 1000:.1f} at most; off it {np.abs(f_m(P[on])).max() * 1000:.2f} mm at most")
    return P
