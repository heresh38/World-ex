"""The foot (Project Orion male): its own all-quad cage grafted onto the leg, bare (boots come later as clothing),
27 cm long, turned out a little as the sheet stands. Its FORM is the foot's anatomy (footshape.py, a field: the
ankle's two bones, the Achilles tendon, the heel, the instep, the arch, the ball, five toes on their own bones);
the cage only carries the flow of the surface: every one of its vertices is put ON that field, and the subdivided
skin is laid onto it afterwards (project_skin), so what is seen is the anatomy, not the cage.

Topology (one foot):
  * the leg's lowest rings (16) are laid on the field (the lower leg narrowing, the ankle bones, the tendon);
  * the ankle's ring turns forward round a bend of five rings whose planes turn about a line across the front of the
    ankle: the heel is the outside of the bend, rounding out behind the ankle and down to the floor, the instep the
    inside (the owner marked the crease a sharper bend left there);
  * the midfoot's ring (16) widens in one band to a ring of 24 (four 1-to-3 patterns: two over the instep, two
    under the sole), then a second ring of 24 behind the ball and the ball's own end, whose 12 columns over the top
    and 12 under the sole stand at the toes: at each web and over each toe;
  * the big toe leaves through three of its 11 segments (a ring of 8, a 2 x 2 cap at its tip), each other toe through
    two (rings of 6, a 1 x 2 cap), four rings along each toe's bones.
"""
import math
import numpy as np

import footshape as FS
import sdf

FOOT_LEN = 0.270
TOE_OUT = 7.0                    # degrees the foot turns out
MID_F = .086                     # the midfoot's ring of 16, square to the foot (m forward of the ankle's axis)
# the bend's rings, from the ankle's (level) ring to the midfoot's: where each meets the instep and where the heel
# (shares of the way along each: the heel's way is long and round, so its rings come closer together at first)
BEND_FRONT = [.14, .29, .43, .57, .71, .86]
BEND_BACK = [.085, .18, .29, .42, .57, .77]
# the forefoot's rings of 24 lie a third and two thirds of the way from the midfoot's ring to the toes' roots, so
# they slant back to the little toe as the toes' joints do
FORE_SHARES = [1 / 3, 2 / 3]
# rings along each toe beyond its root, as shares of the way to where its tip starts to round
TOE_STATIONS = [.18, .40, .60, .79, .95]


def unit(v):
    v = np.asarray(v, float)
    return v / max(float(np.linalg.norm(v)), 1e-12)


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


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

    def d(self, df, dl, dz):
        """a direction given in the foot's frame"""
        return self.fw * df + self.lat * dl + self.up * dz


def cast(fs, O, D, tmax=.16, step=.0015):
    """for each origin O[i] (inside the field) and direction D[i] the first point where the field turns positive:
    marched, then bisected"""
    O = np.asarray(O, float); D = np.asarray(D, float)
    D = D / np.linalg.norm(D, axis=1)[:, None]
    n = len(O)
    inside = fs(O.astype(np.float32)) < 0
    if not inside.all():
        print(f"[foot] {int((~inside).sum())} of {n} rays start outside the foot", flush=True)
    lo = np.zeros(n); hi = np.full(n, np.nan)
    for k in range(1, int(tmax / step) + 1):
        todo = np.isnan(hi)
        if not todo.any():
            break
        t = k * step
        v = fs((O[todo] + D[todo] * t).astype(np.float32))
        idx = np.nonzero(todo)[0]
        hit = v > 0
        hi[idx[hit]] = t
        lo[idx[~hit]] = t
    hi = np.where(np.isnan(hi), tmax, hi)
    for _ in range(18):
        m = .5 * (lo + hi)
        v = fs((O + D * m[:, None]).astype(np.float32))
        lo = np.where(v < 0, m, lo); hi = np.where(v < 0, hi, m)
    return O + D * (.5 * (lo + hi))[:, None]


def cast_in(fs, O, D, tmax=.12, step=.0008):
    """for each origin O[i] (outside the field) and direction D[i] the first point where the field turns negative"""
    O = np.asarray(O, float); D = np.asarray(D, float)
    D = D / np.linalg.norm(D, axis=1)[:, None]
    n = len(O)
    lo = np.zeros(n); hi = np.full(n, np.nan)
    for k in range(1, int(tmax / step) + 1):
        todo = np.isnan(hi)
        if not todo.any():
            break
        t = k * step
        v = fs((O[todo] + D[todo] * t).astype(np.float32))
        idx = np.nonzero(todo)[0]
        hit = v < 0
        hi[idx[hit]] = t
        lo[idx[~hit]] = t
    if np.isnan(hi).any():
        print(f"[foot] {int(np.isnan(hi).sum())} rays from outside found nothing", flush=True)
    hi = np.where(np.isnan(hi), tmax, hi)
    for _ in range(18):
        m = .5 * (lo + hi)
        v = fs((O + D * m[:, None]).astype(np.float32))
        lo = np.where(v > 0, m, lo); hi = np.where(v > 0, hi, m)
    return O + D * (.5 * (lo + hi))[:, None]


def ring_rays(F, centre, e_top, angles, lat=None):
    """directions in a ring's plane: angle 0 along e_top, 90 outward (the frame's lateral unless given), 180 back,
    270 inward"""
    lat = F.lat if lat is None else lat
    return np.array([e_top * math.cos(math.radians(a)) + lat * math.sin(math.radians(a)) for a in angles])


def outline(fs, F, centre, e_top, n=720, lat=None):
    """the section's outline round a centre (a dense ring of rays) and its arc length, starting inward (270) and
    going over the top"""
    ang = (270.0 + np.arange(n) * 360.0 / n) % 360
    P = cast(fs, np.repeat([centre], n, 0), ring_rays(F, centre, e_top, ang, lat))
    seg = np.linalg.norm(np.diff(np.vstack([P, P[:1]]), axis=0), axis=1)
    s = np.concatenate([[0], np.cumsum(seg)])
    return P, s


def even_columns(fs, F, centre, e_top, m, lat=None, u_top=None, u_bot=None):
    """a ring of 2m round a section: m columns over its top and m under it, both returned inward to outward, by
    arc length from the inner side's middle (u: 0 there, 1 at the outer side's middle; evenly unless given)"""
    P, s = outline(fs, F, centre, e_top, lat=lat)
    half = int(len(P) / 2)
    top_len, bot_len = s[half], s[-1] - s[half]
    ev = [(i + .5) / m for i in range(m)]
    u_top = ev if u_top is None else u_top
    u_bot = ev if u_bot is None else u_bot
    D = [P[np.searchsorted(s[:half + 1], top_len * u) % len(P)] for u in u_top]
    # under the sole the outline runs outward -> inward
    B = [P[min(half + np.searchsorted(s[half:] - s[half], bot_len * (1 - u)), len(P) - 1)] for u in u_bot]
    return D, B


def sagittal(fs, F, l0=-.004, c=(.015, .045), n=1440):
    """the foot's outline in the plane along it at l0: world points, their f and z, and each ray's angle (deg: 0
    forward, 90 up, 180 back, 270 down) from a point inside"""
    a = np.arange(n) * 2 * math.pi / n
    D = np.array([F.d(math.cos(t), 0, math.sin(t)) for t in a])
    W = cast(fs, np.repeat([F.p(c[0], l0, c[1])], n, 0), D, tmax=.36, step=.002)
    d = W - np.array([F.A[0], F.A[1], 0.0])
    return W, d @ F.fw, W[:, 2], np.degrees(a)


def pick(ang, val, target, a0, a1):
    """the outline's point within angles a0..a1 whose value is nearest the target"""
    idx = np.nonzero((ang >= a0) & (ang <= a1))[0]
    return int(idx[np.argmin(np.abs(val[idx] - target))])


def path(W, i0, i1):
    """the outline's points from index i0 to i1 (increasing angle)"""
    return W[i0:i1 + 1] if i1 >= i0 else np.vstack([W[i0:], W[:i1 + 1]])


def along(P, share):
    """the point a share of the way along a polyline, by length"""
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    s = np.concatenate([[0], np.cumsum(seg)])
    t = share * s[-1]
    i = min(int(np.searchsorted(s, t)) - 1, len(seg) - 1)
    i = max(i, 0)
    return P[i] + (P[i + 1] - P[i]) * ((t - s[i]) / max(seg[i], 1e-12))


def build_foot(C, leg_rings, F, log=print):
    """adds one foot to the cage C on the leg (its rings, lowest last: 16 vertex indices each; the leg's j-th vertex
    sits at 326.25 + 22.5 j degrees round the leg on the left, 326.25 - 22.5 j on the right (its mirror): 0 front,
    90 outside, 180 back, 270 inside) and lays the leg's lowest rings on the foot's field"""
    sx = F.sx
    fs = FS.FootShape(F)
    angs = [(326.25 + sx * 22.5 * j) % 360 for j in range(16)]
    at = lambda a: min(range(16), key=lambda j: abs(math.remainder(angs[j] - a, 360)))

    # the leg's lowest rings onto the field, each vertex along its own direction from the ring's middle
    for ring in leg_rings:
        P = np.array([C.V[v] for v in ring])
        z = float(P[:, 2].mean())
        w = float(smoothstep(.215, .135, z))
        if w <= 0:
            continue
        c = P.mean(0)
        D = P - c; D[:, 2] = 0
        H = cast(fs, np.repeat([c], len(P), 0), D)
        for v, p, h in zip(ring, P, H):
            C.V[v] = p + (h - p) * w
    ankle = list(leg_rings[-1])

    # the bend: each ring's plane goes through a point on the instep and one round the heel (the foot's outline
    # along its middle), spread by length along each
    za = float(np.mean([C.V[v][2] for v in ankle]))
    W, f_, z_, ang = sagittal(fs, F)
    a_front = pick(ang, z_, za, 20, 89)
    a_back = pick(ang, z_, za, 91, 175)
    m_top = pick(ang, f_, MID_F, 1, 89)
    m_bot = pick(ang, f_, MID_F, 271, 359)
    front = path(W, m_top, a_front)[::-1]                          # the instep: down from the ankle
    back = path(W, a_back, m_bot)                                   # the heel: from the ankle round to the sole
    rings = [ankle]
    for sf, sb in zip(BEND_FRONT, BEND_BACK):
        p_f, p_b = along(front, sf), along(back, sb)
        c = .5 * (p_f + p_b)
        e = unit(p_f - p_b)
        H = cast(fs, np.repeat([c], 16, 0), ring_rays(F, c, e, angs))
        rings.append([C.add(h, "foot") for h in H])
    c = .5 * (W[m_top] + W[m_bot])
    H = cast(fs, np.repeat([c], 16, 0), ring_rays(F, c, F.up, angs))
    rings.append([C.add(h, "foot") for h in H])
    for r0, r1 in zip(rings, rings[1:]):
        C.strip(r0, r1)
    last = rings[-1]
    D16 = [last[at(281.25 + 22.5 * k)] for k in range(8)]          # over the top, inward -> outward
    P16 = [last[at(258.75 - 22.5 * k)] for k in range(8)]          # under the sole, inward -> outward

    # the forefoot: rings as columns over the top and under the sole, the same columns from ring to ring so nothing
    # twists, ending at the toes' roots, where the row runs ROUND each toe (a ring of 8 square to its first bone)
    # and between two toes through the web: where their two rings meet, one vertex over the web and one under it,
    # shared, as a hand's knuckle row runs over each knuckle and down into each web. (A web of its own face, or a
    # row cast straight down at the roots, left slots and folds between the toes.)
    chains = fs.toes
    toes = FS.TOES
    nt = len(chains)
    R, RC = [], []                       # per toe: its root ring (world points, the toe's own order) and middle
    for ch in chains:
        # the web three quarters along the first bone (at its middle the clefts ran deep and their sides crossed)
        c, u, lat_t, up_t = toe_frame(ch, .72 * float(np.linalg.norm(ch[0][1] - ch[0][0])), 1.0)
        O = np.repeat([F.p(*c)], 8, 0)
        Dw = [F.d(*(up_t * math.cos(math.radians(a)) + lat_t * math.sin(math.radians(a)))) for a in TOE_ANG]
        R.append(cast(fs, O, Dw, tmax=.04, step=.0006))
        RC.append(F.p(*c))
    Wt, Wb = [], []
    for i in range(nt - 1):
        for pa, pb, out in ((R[i][3], R[i + 1][0], Wt), (R[i][4], R[i + 1][7], Wb)):
            out.append(sdf.project(fs, np.array([.5 * (pa + pb)], np.float32), 6, .003)[0].astype(float))
    Dr = [R[0][0], R[0][1], R[0][2]]; Pr = [R[0][7], R[0][6], R[0][5]]
    for i in range(1, nt):
        Dr += [Wt[i - 1], R[i][1], R[i][2]]; Pr += [Wb[i - 1], R[i][6], R[i][5]]
    Dr.append(R[-1][3]); Pr.append(R[-1][4])
    assert len(Dr) == 16, len(Dr)
    loc = lambda q: np.array([(q - F.A) @ F.fw, (q - F.A) @ F.lat, q[2]])
    col_l = np.array([.5 * (loc(a)[1] + loc(b)[1]) for a, b in zip(Dr, Pr)])
    col_f = np.array([.5 * (loc(a)[0] + loc(b)[0]) for a, b in zip(Dr, Pr)])
    rl = col_l; rf = col_f

    def base_f(l):
        if l < rl[0]:
            return float(rf[0] + (l - rl[0]) * (rf[1] - rf[0]) / max(rl[1] - rl[0], 1e-6))
        if l > rl[-1]:
            return float(rf[-1] + (l - rl[-1]) * (rf[-1] - rf[-2]) / max(rl[-1] - rl[-2], 1e-6))
        return float(np.interp(l, rl, rf))

    def loc_l(p):
        return float((np.asarray(p) - F.A) @ F.lat)

    # where each of the roots' columns lies round the roots' row (u: 0 at the inner side's middle, 1 at the outer
    # side's, by length along the row over the top and along it under the sole)
    def fractions(row):
        L = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(np.array(row), axis=0), axis=1))])
        return .03 + .94 * L / L[-1]
    u_top_b, u_bot_b = fractions(Dr), fractions(Pr)
    # the roots' row slants back to the little toe: the rings before it turn toward it a share at a time
    slant = math.atan2(col_f[0] - col_f[-1], col_l[-1] - col_l[0])
    f_mid = base_f(.005)

    def columns(share, m):
        """a ring of m + m columns a share of the way from the midfoot's ring to the toes' roots: a section of the
        field in its own (turned) plane, the columns by length round it, evenly for 12, for 16 moving toward the
        roots' own columns"""
        t = slant * share
        lat = -F.fw * math.sin(t) + F.lat * math.cos(t)
        c = F.p(MID_F + (f_mid - MID_F) * share, .005, .030 - .008 * share)
        if m == 16:
            ev = (np.arange(m) + .5) / m
            ut = ev * (1 - share) + u_top_b * share; ub = ev * (1 - share) + u_bot_b * share
        else:
            ut = ub = None
        T, Bm = even_columns(fs, F, c, F.up, m, lat, ut, ub)
        part = "fore" if m == 16 else "foot"                         # the forefoot's last rings: see solve_cage's free
        return [C.add(p, part) for p in T], [C.add(p, part) for p in Bm]

    def plain(a, b, c, d):
        C.quad(a, b, d, c)

    def triple(a, b, top):
        c, d, e, f_ = top
        pa, pb = C.V[a], C.V[b]
        m1 = C.add(.5 * (pa + (pb - pa) / 3) + .5 * C.V[d], "foot")
        m2 = C.add(.5 * (pa + (pb - pa) * 2 / 3) + .5 * C.V[e], "foot")
        C.quad(a, m1, d, c); C.quad(m1, m2, e, d); C.quad(m2, b, f_, e); C.quad(a, b, m2, m1)
        return [m1, m2]

    def band(Da, Pa, Db, Pb, splits_top, centre):
        """rows a to rows b (more columns): the named segments each become three; over the top inward -> outward
        (the ring's own order), under the sole the other way"""
        na = len(Da)
        inner = []
        for ra, rb, splits in ((Da, Db, splits_top), (Pa[::-1], Pb[::-1], tuple(na - 2 - k for k in splits_top))):
            kb = 0
            for k in range(na - 1):
                if k in splits:
                    inner += triple(ra[k], ra[k + 1], rb[kb:kb + 4])
                    kb += 3
                else:
                    plain(ra[k], ra[k + 1], rb[kb], rb[kb + 1])
                    kb += 1
            assert kb == len(rb) - 1, (kb, len(rb))
        C.quad(Pa[0], Da[0], Db[0], Pb[0])
        C.quad(Da[-1], Pa[-1], Pb[-1], Db[-1])
        c = F.p(*centre)
        for v in inner:                                             # the patterns' inner vertices onto the field
            C.V[v] = cast(fs, [c], [C.V[v] - c])[0]

    def strips(Da, Pa, Db, Pb):
        n = len(Da)
        for ra, rb in ((Da, Db), (Pa[::-1], Pb[::-1])):
            for k in range(n - 1):
                plain(ra[k], ra[k + 1], rb[k], rb[k + 1])
        C.quad(Pa[0], Da[0], Db[0], Pb[0])
        C.quad(Da[-1], Pa[-1], Pb[-1], Db[-1])

    D24, P24 = columns(FORE_SHARES[0], 12)
    band(D16, P16, D24, P24, (1, 4), (.092, .005, .030))            # 16 -> 24
    # the ring of 32 half way from the ring of 24 to the roots' row, column by column (the roots' row is no plane: it
    # runs forward over the big toe and back to the little one, so no plane between could follow it)
    t = slant * FORE_SHARES[0]
    lat24 = -F.fw * math.sin(t) + F.lat * math.cos(t)
    c24 = F.p(MID_F + (f_mid - MID_F) * FORE_SHARES[0], .005, .030 - .008 * FORE_SHARES[0])
    V24t, V24b = even_columns(fs, F, c24, F.up, 16, lat24, u_top_b, u_bot_b)
    half = lambda a, b: sdf.project(fs, np.array([.5 * (a + b)], np.float32), 8, .003)[0].astype(float)
    D32 = [C.add(half(a, b), "fore") for a, b in zip(V24t, Dr)]
    P32 = [C.add(half(a, b), "fore") for a, b in zip(V24b, Pr)]
    band(D24, P24, D32, P32, (3, 7), (.112, .006, .024))            # 24 -> 32
    DB = [C.add(p, "fore") for p in Dr]
    PB = [C.add(p, "fore") for p in Pr]
    strips(D32, P32, DB, PB)

    # the toes
    for k, (t, ch) in enumerate(zip(toes, chains)):
        base = DB[3 * k:3 * k + 4] + PB[3 * k:3 * k + 4][::-1]
        toe(C, fs.toe_only(k), F, ch, base, t["name"])
    log(f"foot: {'left' if sx > 0 else 'right'}")


TOE_ANG = [-67.5, -22.5, 22.5, 67.5, 112.5, 157.5, 202.5, 247.5]   # a toe's ring: over it inward -> outward, under back


def toe_frame(chain, s, lean):
    """the toe's middle at s along its bones (beyond the last: on along its way) and its frame there: along, outward,
    up; lean 1: the section square to the foot more than to the first bone (the bone rises)"""
    pts = chain[0]
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    s_all = np.concatenate([[0], np.cumsum(seg)])
    i = max(min(int(np.searchsorted(s_all, s) - 1), len(seg) - 1), 0)
    u = unit(pts[i + 1] - pts[i])
    c = pts[i] + u * (s - s_all[i])
    u = unit(u * (1 - .6 * lean) + np.array([1.0, 0, 0]) * .6 * lean)
    lat_t = unit(np.array([0, 1.0, 0]) - u * u[1])
    up_t = unit(np.cross(u, lat_t))
    return c, u, lat_t, up_t


def toe(C, fs, F, chain, base, name):
    """rings round the toe's bones at TOE_STATIONS (sections square to them, on the field), a cap at its tip"""
    pts, w, h = chain
    n = len(base)
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    s_all = np.concatenate([[0], np.cumsum(seg)])
    total = s_all[-1]
    angles = TOE_ANG
    rings = [list(base)]
    s_root = .5 * seg[0]
    s_end = total + .55 * h[-1]                                      # where the tip starts to round
    # the first ring a little ahead of the toe's own root ring everywhere (its webs can lie ahead of its root: a
    # shorter toe's web is where its longer neighbour parts from it)
    u0 = unit(pts[1] - pts[0])
    loc = lambda q: np.array([(q - F.A) @ F.fw, (q - F.A) @ F.lat, q[2]])
    s_base = max(float((loc(np.asarray(C.V[v])) - pts[0]) @ u0) for v in base)
    s_first = max(s_root + TOE_STATIONS[0] * (s_end - s_root), s_base + .0045)
    for st in TOE_STATIONS:
        s = s_first + (st - TOE_STATIONS[0]) / (1 - TOE_STATIONS[0]) * (s_end - s_first)
        c, u, lat_t, up_t = toe_frame(chain, s, max(0.0, 1 - st / .45))   # the first rings: square to the foot
        O = np.repeat([F.p(*c)], n, 0)
        Dw = [F.d(*(up_t * math.cos(math.radians(a)) + lat_t * math.sin(math.radians(a)))) for a in angles]
        H = cast(fs, O, Dw, tmax=.04, step=.0006)
        # a toe's rings are not fitted exactly (lab.py leaves them free: an exact fit overshoots between toes), so
        # each stands out from the toe's middle by what the subdivision takes back (a ring of n round a circle
        # comes in to (4 + 2 cos(360/n)) / 6 of it)
        cw = F.p(*c)
        H = cw + (H - cw) * (6 / (4 + 2 * math.cos(2 * math.pi / n)))
        rings.append([C.add(p, f"toe_{name}") for p in H])
    for r0, r1 in zip(rings, rings[1:]):
        C.strip(r0, r1)
    # the tip: forward of the last bone, between its way and the foot's (a curled toe's tip faces forward, its pad
    # down)
    u = unit(unit(pts[-1] - pts[-2]) + np.array([1.0, 0, 0]))
    tip = cast(fs, [F.p(*(pts[-1] - u * .002))], [F.d(*u)], tmax=.04, step=.0005)[0] + F.d(*u) * .0015
    r = rings[-1]
    if n == 8:
        C.cap(r, f"toe_{name}")
        v = len(C.V) - 1                                             # the cap's one inner vertex
        C.V[v] = tip
    else:
        # three quads round one vertex at the very tip (a round end, not a cut one)
        c = C.add(tip, f"toe_{name}")
        C.quad(r[0], r[1], r[2], c); C.quad(r[2], r[3], r[4], c); C.quad(r[4], r[5], r[0], c)


TOE_NAMES = [t["name"] for t in FS.TOES]


def skin_offsets(P, N, frames, toe_w=None, edges=None, iters=6, reach=.006, smooth=3):
    """how far each vertex of the subdivided skin moves along its own normal to lie on the foot's anatomy (the cage
    gives the flow, the field the form): Newton steps, fully below 16 cm, fading out by 23.5 cm. A vertex of a toe
    (toe_w: per vertex and toe, how much it belongs to it, carried through the subdivision) is laid on the foot with
    that toe alone, blended by that weight, so a toe's side never reaches into its neighbour. Only where the field's
    own normal agrees with the skin's and the steps converged; then the offsets are smoothed over the mesh (edges),
    so nothing is left as a step or a sliver."""
    P = np.asarray(P, np.float32)
    N = np.asarray(N, np.float32)
    disp = np.zeros(len(P), np.float32)
    nt = len(FS.TOES)
    if toe_w is None:
        toe_w = np.zeros((len(P), nt), np.float32)

    def along(field, Q0, n):
        e = 3e-4
        g = np.stack([(field(Q0 + np.array(v, np.float32) * e) - field(Q0 - np.array(v, np.float32) * e)) / (2 * e)
                      for v in ((1, 0, 0), (0, 1, 0), (0, 0, 1))], 1)
        g /= np.maximum(np.linalg.norm(g, axis=1), 1e-9)[:, None]
        agree = smoothstep(.3, .7, (g * n).sum(1))
        Q = Q0.copy(); t = np.zeros(len(Q0), np.float32)
        for _ in range(iters):
            st = np.clip(field(Q), -.004, .004)
            Q = Q - n * st[:, None]; t -= st
        ok = smoothstep(.003, .001, np.abs(field(Q)))
        return (np.clip(t, -reach, reach) * agree * ok).astype(np.float32)

    for F in frames:
        fs = FS.FootShape(F)
        L = fs.local(P)
        near = (L[:, 2] < .235) & (np.abs(L[:, 1]) < .13) & (L[:, 0] > -.14) & (L[:, 0] < .30) & (P[:, 0] * F.sx > 0)
        idx = np.nonzero(near)[0]
        if not len(idx):
            continue
        w = smoothstep(.235, .16, L[idx, 2]).astype(np.float32)
        d_all = along(fs, P[idx], N[idx])
        tw = np.clip(toe_w[idx], 0, 1)
        d_toe = np.zeros(len(idx), np.float32)
        for k in range(nt):
            m = tw[:, k] > .01
            if m.any():
                d_toe[m] += along(fs.with_toe(k), P[idx[m]], N[idx[m]]) * tw[m, k]
        wsum = np.clip(tw.sum(1), 0, 1)
        disp[idx] = d_all * (1 - wsum) * w
    if edges is not None and smooth:
        e0, e1 = edges[:, 0], edges[:, 1]
        deg = np.bincount(e0, minlength=len(P)) + np.bincount(e1, minlength=len(P))
        for _ in range(smooth):
            acc = np.bincount(e0, weights=disp[e1], minlength=len(P)) + np.bincount(e1, weights=disp[e0], minlength=len(P))
            disp = (.5 * disp + .5 * acc / np.maximum(deg, 1)).astype(np.float32)
    return disp


def separate_toes(P, frames, toe_w, margin=.0009, edges=None, spread=10):
    """toes press together but never into each other: every vertex of a toe kept on its own side of the plane
    between it and its neighbour (footshape's cuts), by how much more it belongs to that toe than to the other (the
    web itself, shared by two toes, stays where it is). Given the mesh's edges each toe's share is first spread a
    few rings into the forefoot: the skin in a cleft's neck belonged to no toe, nothing held it, and the two sides
    of the cleft crossed and folded there (thin fins between the toes)"""
    P = np.asarray(P, np.float32).copy()
    toe_w = np.asarray(toe_w, np.float32)
    if edges is not None and spread:
        n = len(P)
        e0, e1 = edges[:, 0], edges[:, 1]
        deg = np.maximum(np.bincount(e0, minlength=n) + np.bincount(e1, minlength=n), 1)
        T = toe_w.astype(np.float64)
        for _ in range(spread):
            acc = np.zeros_like(T)
            for c in range(T.shape[1]):
                acc[:, c] = np.bincount(e0, weights=T[e1, c], minlength=n) + np.bincount(e1, weights=T[e0, c], minlength=n)
            T = np.maximum(T, .85 * acc / deg[:, None])                 # spread out, never taken back
        toe_w = T.astype(np.float32)
    for F in frames:
        fs = FS.FootShape(F)
        side = (P[:, 0] * F.sx > 0)
        L = fs.local(P)
        near = side & (L[:, 2] < .08) & (L[:, 0] > .09)
        idx = np.nonzero(near)[0]
        if not len(idx):
            continue
        Q = L[idx].copy()
        for i, (m, n) in enumerate(fs.cuts):
            s = (Q - m) @ n
            ta, tb = toe_w[idx, i], toe_w[idx, i + 1]
            wa = np.clip((ta - tb) * 8, 0, 1)                          # the toe inward of the plane
            wb = np.clip((tb - ta) * 8, 0, 1)                          # the toe outward of it
            Q -= n[None, :] * (np.maximum(s + margin, 0) * wa)[:, None]
            Q += n[None, :] * (np.maximum(margin - s, 0) * wb)[:, None]
        W = np.array([F.A[0], F.A[1], 0.0]) + Q[:, :1] * F.fw + Q[:, 1:2] * F.lat
        W[:, 2] = Q[:, 2]
        P[idx] = W
    return P
