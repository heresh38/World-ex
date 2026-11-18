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
        # where each of the rim's vertices lies on the opening: u from the inner corner to the outer, t 0 on the lower
        # lid's margin, 1 on the upper (the bottom of the window runs along u, the top back)
        feats[side + "_rim"] = (list(loops[3]), np.r_[u, u[::-1]], np.r_[np.zeros(nb), np.ones(nb)])
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
    # (both inside the window's own rings: over the window's top ring the tip's patch overlapped the band above it
    # and the skin folded across the nose there, a dark line on each side of it)
    zb_ = max(zb_, zr(RINGS[5], 0.0) + .15)
    zt_ = min(zt_, zr(RINGS[6], 0.0) - .15)
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
    # ---- the ears: their windows left OPEN; ear.py lays each ear (a ring grid on the sculpt's own ear) into the
    # subdivided window and stitches it to the window's loop. (Lifted out round the rim, capped over and laid onto the
    # sculpt by nearest points, the cage's ear crumpled over the helix and into the concha)
    for side, sx in (("ear_L", 1), ("ear_R", -1)):
        loop, n, m = window_loop(side)
        if EAR_OPEN:
            # a plain cap over the window (the cage's solve needs it closed: an open window's border was fitted 5 cm
            # off the head); ear.py cuts its subdivided faces out again
            f0 = len(C.F)
            C.cap_rect(loop, m, n, "head")
            feats[side] = (loop, [], list(range(f0, len(C.F))))
            continue
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


EAR_OPEN = True                  # the cage leaves the ears' windows open (ear.py)


RIM_OFF = .06                    # cm the eye's rim stands off the globe (the cage's innermost loop)


def lid_outline(hd, u, t):
    """the eye's opening in the front view (head cm, his left eye: x, z) at its places along it (u: inner corner 0 ->
    outer 1, t: 0 the lower lid's margin -> 1 the upper's), for the sculpt hd as its sliders make it (head.Head.fissure:
    eye_open its height, eye_size its scale round the eye)"""
    u = np.asarray(u, np.float64); t = np.clip(np.asarray(t, np.float64), 0, 1)
    es = hd.k("eye_size")
    x = H.EN[0] + (H.EX[0] - H.EN[0]) * u
    z0 = H.EN[1] + (H.EX[1] - H.EN[1]) * u
    uc = np.clip(u, 0, 1)
    up = z0 + H.LID_UP * hd.k("eye_open") * np.sin(np.pi * uc ** .82) ** .85
    lo = z0 - H.LID_LO * hd.k("eye_open") * np.sin(np.pi * uc ** 1.28) ** 1.05
    z = lo * (1 - t) + up * t
    ex_, _ey, ez_ = H.EYE
    return ex_ + (x - ex_) * es, ez_ + (z - ez_) * es


def rim_points(hd, side, u, t):
    """the eye's rim on the globe (world metres) at its places along the opening (lid_outline)"""
    X, Z = lid_outline(hd, u, t)
    ex_, ey_, ez_ = H.EYE
    Rm = H.EYE_R + RIM_OFF
    dx, dz = X - ex_, Z - ez_
    Y = ey_ - np.sqrt(np.maximum(Rm * Rm - dx * dx - dz * dz, .01))
    sx = 1.0 if side > 0 else -1.0
    return np.c_[sx * X / 100, hd.Y0 + Y / 100, hd.Z0 + Z / 100]


def unwarp(hd, Q):
    """where the sliders' warp of the sculpt's space (head.Head.warp) shows a point of the sculpt (head cm, first
    order)"""
    Q = np.asarray(Q, np.float64)
    return Q + (Q - hd.warp(Q.astype(F32)).astype(np.float64))


def lid_rings(edges, rim, k=4):
    """the rings of vertices straight out from an eye's rim (the opening's border), each in the rim's order: ring j's
    i-th vertex is the one the rim's i-th reaches j steps out (-1 where the grid is not regular)"""
    nb = {}
    for a, b in np.asarray(edges):
        nb.setdefault(int(a), []).append(int(b))
        nb.setdefault(int(b), []).append(int(a))
    rings = [np.asarray(rim, np.int64)]
    seen = set(int(v) for v in rim)
    for _ in range(k):
        cur = rings[-1]
        nxt = np.full(len(cur), -1, np.int64)
        for i, v in enumerate(cur):
            if v < 0:
                continue
            cand = [w for w in nb.get(int(v), []) if w not in seen]
            if len(cand) == 1:
                nxt[i] = cand[0]
        seen.update(int(v) for v in nxt if v >= 0)
        rings.append(nxt)
    return rings[1:]


LID_EDGE = .04                   # cm outside the opening where the lid's front edge is taken (its rounding is .035)


def front_lids(P, hf, lids):
    """the lids' fronts (rings 4 to 8 out from each rim: from the cage's lid loop out to the orbit's) put where a ray
    from in front meets the sculpt, before the head is laid by nearest points: the subdivision drew them back toward
    the rim on the globe, and from there the nearest skin was the lower lid's inside (folded faces along its outer
    half). A ray that passes the opening into the eye's pocket is not taken"""
    toQ = lambda X: np.c_[X[:, 0] * 100, (X[:, 1] - H.Y0) * 100, (X[:, 2] - H.Z0) * 100]
    toW = lambda Q: np.c_[Q[:, 0] / 100, H.Y0 + Q[:, 1] / 100, H.Z0 + Q[:, 2] / 100]
    for L in lids:
        ids = np.concatenate([np.asarray(r) for r in L.get("front", [])] or [np.zeros(0, np.int64)])
        ids = ids[ids >= 0]
        if not len(ids):
            continue
        Q = toQ(P[ids])
        hit = hf.front(Q[:, 0], Q[:, 2]).astype(np.float64)
        ok = hit[:, 1] < H.EYE[1] - 1.0
        P[ids[ok]] = toW(hit[ok])
    return P


def place_lids(P, hf, lids):
    """the lids' bands laid by construction (P in metres, changed in place). head.py's lid is a shell cut along the
    fissure: its margin a wall straight back from the front edge to the lid's inside. Ring 3 goes on the lid's front
    halfway from the opening to ring 4, ring 2 on the front just outside the opening's edge, ring 1 on the outline at
    the margin's back edge (never behind the rim, which stays pinned on the globe). Laid by nearest points the band's
    inner rings found the lid's own inside and folded back on themselves along every lower lid"""
    hd = hf.hd
    toQ = lambda X: np.c_[X[:, 0] * 100, (X[:, 1] - H.Y0) * 100, (X[:, 2] - H.Z0) * 100]
    toW = lambda Q: np.c_[Q[:, 0] / 100, H.Y0 + Q[:, 1] / 100, H.Z0 + Q[:, 2] / 100]
    for L in lids:
        sx, u, t = L["side"], np.asarray(L["u"], np.float64), np.asarray(L["t"], np.float64)
        rim = np.asarray(L["rim"])
        r1, r2, r3, r4 = (np.asarray(r) for r in L["rings"])
        ok = (r1 >= 0) & (r2 >= 0) & (r3 >= 0) & (r4 >= 0)
        if not ok.any():
            continue
        u, t, rim, r1, r2, r3, r4 = u[ok], t[ok], rim[ok], r1[ok], r2[ok], r3[ok], r4[ok]
        n = len(u)
        X, Z = lid_outline(hd, u, t)
        W = unwarp(hd, np.c_[sx * X, np.full(n, -8.9), Z])
        O = W[:, [0, 2]]
        Xc, Zc = lid_outline(hd, np.clip(u, .15, .85), np.full(n, .5))      # the opening's middle line
        Wc = unwarp(hd, np.c_[sx * Xc, np.full(n, -8.9), Zc])
        out = O - Wc[:, [0, 2]]
        out /= np.maximum(np.linalg.norm(out, axis=1), 1e-9)[:, None]
        q4 = toQ(P[r4])
        xz3 = O + .45 * (q4[:, [0, 2]] - O)
        q3 = hf.front(xz3[:, 0], xz3[:, 1]).astype(np.float64)
        xz2 = O + LID_EDGE * out
        q2 = hf.front(xz2[:, 0], xz2[:, 1]).astype(np.float64)
        # the margin's back edge: straight back along y just inside the cut, from where the lid begins to where it ends
        xz1 = O + .012 * out
        D = np.tile(np.array([0, 1, 0], F32), (n, 1))
        S = np.c_[xz1[:, 0], q2[:, 1] - .2, xz1[:, 1]].astype(F32)
        enter = hf.exit(S, D, t0=0.0, t1=.8, n=160, from_inside=False).astype(np.float64)
        leave = hf.exit((enter + np.array([0, .01, 0])).astype(F32), D, t0=0.0, t1=.7, n=140,
                        from_inside=True).astype(np.float64)
        found = hf.f(leave.astype(F32)) > -1e-3
        y1 = np.where(found, leave[:, 1] - .02, enter[:, 1] + .22)
        qr = toQ(P[rim])
        y1 = np.minimum(y1, qr[:, 1] - .03)
        y2 = np.minimum(q2[:, 1], y1 - .02)
        q1 = np.c_[O[:, 0], y1, O[:, 1]]
        q2 = np.c_[q2[:, 0], y2, q2[:, 2]]
        P[r1], P[r2], P[r3] = toW(q1), toW(q2), toW(q3)
    return P


def lay_on_head(P, N, w, hf, edges=None, faces=None, rounds=12, log=print, pins=None, band=None, lids=None):
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
    if pins is not None:                                              # vertices put in place and held (the ears' bases)
        pi, pp = pins
        P[pi] = pp
        hold[pi] = True
    # the lids' bands (from the eye's rim on the globe over the margin to the lid's front): never laid on the sculpt
    # by nearest points (there the nearest skin is the lid's own inside: the band folded back on itself along every
    # lower lid), filled after the rest as a membrane between the rim and the lid
    fill = np.zeros(n, bool) if band is None else (np.asarray(band, bool) & ~hold)
    hold = hold | fill
    for L in lids or []:                                              # the lids' bands: laid by construction
        for r in L["rings"][:3]:
            r = np.asarray(r)
            hold[r[r >= 0]] = True
    if faces is not None:                                             # the eyes' openings (edges with one face)
        F = np.asarray(faces)
        e = np.sort(np.c_[F.ravel(), np.roll(F, -1, axis=1).ravel()], axis=1)
        uniq, cnt = np.unique(e, axis=0, return_counts=True)
        hold[uniq[cnt == 1].ravel()] = True
    X0 = P[on].copy()
    if lids:
        front_lids(P, hf, lids)
    free_on = on[~hold[on]]
    P[free_on] = project(P[free_on])
    if lids:
        place_lids(P, hf, lids)
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
    if fill.any() and edges is not None:
        e0, e1 = edges[:, 0], edges[:, 1]
        deg = np.maximum(np.bincount(e0, minlength=n) + np.bincount(e1, minlength=n), 1).astype(np.float64)
        fi = np.flatnonzero(fill)
        for _ in range(300):
            acc = np.zeros((n, 3))
            for c in range(3):
                acc[:, c] = np.bincount(e0, weights=P[e1, c], minlength=n) + np.bincount(e1, weights=P[e0, c], minlength=n)
            P[fi] = acc[fi] / deg[fi, None]
    if lids:
        place_lids(P, hf, lids)
    # where the head's share fades (down the neck) the old place keeps its share
    P[on] = X0 + (P[on] - X0) * np.where(hold[on], 1.0, w[on])[:, None]
    moved = np.linalg.norm(P[on] - X0, axis=1)
    log(f"head laid on its sculpt: {len(on)} vertices, moved {np.median(moved) * 1000:.1f} mm (median), "
        f"{moved.max() * 1000:.1f} at most; off it {np.abs(f_m(P[on])).max() * 1000:.2f} mm at most")
    return P


# the face's sliders (the owner, 2026-11-16: "the face will be heavily customizable in game when the player first
# starts"): each a parameter of the sculpt (head.py) and the value a full slider gives; the game plays each morph
# both ways (a negative weight is the other way)
FACE_SLIDERS = {
    "jaw": 1.5, "chin": 1.6, "cheekbones": 1.7, "cheeks": 1.6, "cheek_hollow": 1.8, "temples": 1.8,
    "brow": 1.7, "forehead": 1.8, "nose_width": 1.3, "nose_length": 1.2, "nose_tip": 1.3, "nasolabial": 2.0,
    "mouth_width": 1.25, "lips": 1.5, "eye_open": 1.25, "eye_size": 1.12, "crease": 1.8, "hood": 1.8,
    "tear_trough": 1.8, "eye_bags": 1.8, "ear_size": 1.2, "ear_out": 1.6,
}


def with_params(hf, params):
    """the same sculpt with other face parameters (sharing its loft: building one takes seconds)"""
    import copy
    hd2 = copy.copy(hf.hd)
    hd2.p = dict(params)
    if getattr(hd2, "anatomy", False):
        import headbase
        hd2.hb = headbase.HeadBase(hd2.p)
    hd2.set_landmarks(H.NASION, *hd2.nose_points(), H.STOMION_Z)
    out = HeadField.__new__(HeadField)
    out.hd = hd2
    return out


EAR_KEYS = ("ear_size", "ear_out")          # the sliders that move the ears (the others leave them where they are)


def face_keys(P, N, w, hf, edges, log=print, ears=None, rims=None, band=None, lids=None):
    """one morph per face slider: the head laid onto the sculpt with that parameter at its full value, less the
    head laid the same way onto the unchanged sculpt (so whatever the laying itself does cancels). The eyes'
    openings are laid too here (their lids move with the eye's sliders)"""
    quiet = lambda *a: None
    # ears: {side sx: (loop vertex indices, ring0 (n, 3), inner (m, 3), ...)} from ear.py for the unchanged field; the
    # ears' new vertices follow the mesh's own (in the order of the sides given), their deltas appended
    ears = ears or {}
    sides = sorted(ears, reverse=True)

    def pins_of(rings):
        if not sides:
            return None
        return (np.concatenate([ears[s][0] for s in sides]), np.concatenate([rings[s] for s in sides]))
    base_ring = {s: ears[s][1] for s in sides}

    def with_rims(pins, hd):
        """the ears' pins and the eyes' rims (rims: [(vertex ids, side, u, t)]) as one set of pins"""
        if not rims:
            return pins
        ids = [r[0] for r in rims]
        pts = [rim_points(hd, r[1], r[2], r[3]) for r in rims]
        if pins is not None:
            ids.insert(0, pins[0]); pts.insert(0, pins[1])
        return np.concatenate(ids), np.concatenate(pts)
    base = lay_on_head(P, N, w, hf, edges=edges, faces=None, log=quiet, pins=with_rims(pins_of(base_ring), hf.hd),
                       band=band, lids=lids)
    keys = {}
    for name, val in FACE_SLIDERS.items():
        hp = with_params(hf, {name: val})
        rings, inners = base_ring, {s: ears[s][2] for s in sides}
        if name in EAR_KEYS and sides:
            import ear as EAR
            rings, inners = {}, {}
            for s in sides:
                r0, inner, _ = EAR.build(hp, s, ears[s][1], log=quiet)
                rings[s], inners[s] = r0, inner
        X = lay_on_head(P, N, w, hp, edges=edges, faces=None, log=quiet, pins=with_rims(pins_of(rings), hp.hd),
                        band=band, lids=lids)
        D = X - base
        if sides:
            D = np.r_[D, np.concatenate([inners[s] - ears[s][2] for s in sides])]
        D[np.linalg.norm(D, axis=1) < 2e-5] = 0
        keys[name] = D
        log(f"face key {name}: {np.linalg.norm(D, axis=1).max() * 1000:.1f} mm at most, "
            f"{int((np.abs(D).sum(1) > 0).sum())} vertices")
    return keys
