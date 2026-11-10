"""Void Requiem modelling kit (used by requiem_guns.py): the raid set's own shapes, built as direct meshes (no booleans).

  talon      a swept blade plate: a spine curve in the side view, a width that runs out to a point, a raised ridge
             (the polished shards layered along every gun), with an optional gold bead on one edge and a line of
             light tucked under the other
  plate      a hard-surface armour plate: side profile, chamfered outer face
  prism      a centred extrusion with chamfered flanks (frames, struts, magazines)
  lathe      a turned part round the bore (barrels, muzzles, chambers, tubes); lathe_x the same across the gun (cores)
  crystal    a faceted void crystal between two points
  vein       a crack of light: a jagged thin strand through 3D points
  core       the set's signature: a gold-ringed void core on both flanks with a crystal star standing in it
  chamber    the plasma chamber seen through the shroud: a tube of light, dark ribs, a hot core line, arcs

Frame: weapons.py's (origin = top of the pistol grip, barrel along -Y, Z up, the gun's right side is -X). Profiles are
(y, z) in the side view. Materials come from mats(): the energy line's names (an API) plus this set's variants
gun_metal__void (polished silver), gun_glow__dim / gun_glow__crystal (the rarity colour at lower strengths: Unreal tints
every gun_glow* slot).
"""
import bpy, bmesh, math, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import bl
import gunkit as K


def mats():
    M = K.energy_mats()
    M['silver'] = bl.mat('gun_metal__void', '#8f8c9e', 1.0, .26)
    M['dim'] = bl.mat('gun_glow__dim', '#3d1a8c', 0, .35, emit='#1ad8ff', strength=.9)
    M['crystal'] = bl.mat('gun_glow__crystal', '#7a4dff', .2, .08, emit='#1ad8ff', strength=.55)
    return M


# ------------------------------------------------------------------ mesh plumbing
def mk(name, verts, faces, m, sharp=30, weld=True):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(map(float, v)) for v in verts], [], faces)
    me.update()
    bm = bmesh.new(); bm.from_mesh(me)
    if weld:
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=1e-7)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    o = K._obj(name, me, m)
    return K.harden(o, sharp)


def spl(pts, n=16):
    """Smooth curve through pts (any dimension): Catmull-Rom on chord length; returns (n, d) samples and their 0..1
    parameters at the control points."""
    P = np.asarray(pts, float)
    if len(P) == 2:
        t = np.linspace(0, 1, n)[:, None]
        return P[0] * (1 - t) + P[1] * t, np.array([0., 1.])
    d = np.linalg.norm(np.diff(P, axis=0), axis=1)
    u = np.concatenate([[0], np.cumsum(d)]); u /= u[-1]
    T = np.zeros_like(P)
    T[1:-1] = (P[2:] - P[:-2]) / (u[2:] - u[:-2])[:, None]
    T[0] = (P[1] - P[0]) / (u[1] - u[0]); T[-1] = (P[-1] - P[-2]) / (u[-1] - u[-2])
    out = []
    for s in np.linspace(0, 1, n):
        i = min(np.searchsorted(u, s, side='right') - 1, len(P) - 2)
        h = u[i + 1] - u[i]; t = (s - u[i]) / h
        h00 = 2 * t ** 3 - 3 * t ** 2 + 1; h10 = t ** 3 - 2 * t ** 2 + t; h01 = -2 * t ** 3 + 3 * t ** 2; h11 = t ** 3 - t ** 2
        out.append(h00 * P[i] + h10 * h * T[i] + h01 * P[i + 1] + h11 * h * T[i + 1])
    return np.array(out), u


def poly_offset(pts, d):
    """Inset (d > 0) a simple side-profile polygon by d with mitred corners."""
    P = np.asarray(pts, float); n = len(P)
    area = sum(P[i][0] * P[(i + 1) % n][1] - P[(i + 1) % n][0] * P[i][1] for i in range(n))
    sg = 1.0 if area > 0 else -1.0
    out = []
    for i in range(n):
        a, b, c = P[i - 1], P[i], P[(i + 1) % n]
        e0 = b - a; e1 = c - b
        e0 /= np.linalg.norm(e0) + 1e-12; e1 /= np.linalg.norm(e1) + 1e-12
        n0 = sg * np.array([-e0[1], e0[0]]); n1 = sg * np.array([-e1[1], e1[0]])
        m = n0 + n1; L = np.linalg.norm(m)
        if L < 1e-6:
            out.append(b + n0 * d); continue
        m /= L
        k = min(d / max(m @ n0, .34), d * 3)
        out.append(b + m * k)
    return [tuple(p) for p in out]


# ------------------------------------------------------------------ blades
def talon(name, spine, wid, m, x=0.0, t=.005, sym=True, n=14, bias=0.0, lean=0.0, back=.004, two=False,
          trim=None, glow=None, g=.0016, sharp=24, side=1):
    """A swept blade plate. spine [(y, z)] root -> tip in the side view; wid = full width at each control point (the
    last is usually 0: a point). The plate stands on the +X flank at x (and mirrored on -X when sym) with its ridge
    raised t; `bias` (-1..1) moves the ridge toward one edge, `lean` flares the upper edge outward, `two` makes a
    centre blade with a ridge on both faces. Normal side: N is on the left of the direction of travel seen from +X
    (up for a spine running forward). trim / glow: materials for a bead along the N edge / a light line under the
    other. Returns a list of objects."""
    C, u = spl(spine, n)
    W = np.interp(np.linspace(0, 1, n), u, np.asarray(wid, float))
    T = np.gradient(C, axis=0); T /= np.linalg.norm(T, axis=1)[:, None] + 1e-12
    N = np.stack([T[:, 1], -T[:, 0]], 1)
    wmax = max(W.max(), 1e-6)
    out = []

    def build(nm, ring_fn, mat):
        V = []; F = []
        rings = []
        for i in range(n):
            pts = ring_fn(i)
            if pts is None:                       # a point
                rings.append([len(V)]); V.append(tip(i))
            else:
                rings.append(list(range(len(V), len(V) + len(pts)))); V += pts
        for i in range(n - 1):
            a, b = rings[i], rings[i + 1]
            if len(a) == 1 and len(b) == 1:
                continue
            k = max(len(a), len(b))
            for j in range(k):
                if len(a) == 1:
                    F.append((a[0], b[j], b[(j + 1) % k]))
                elif len(b) == 1:
                    F.append((a[j], a[(j + 1) % k], b[0]))
                else:
                    F.append((a[j], a[(j + 1) % k], b[(j + 1) % k], b[j]))
        if len(rings[0]) > 1:
            F.append(tuple(rings[0]))
        if len(rings[-1]) > 1:
            F.append(tuple(rings[-1]))
        VV = list(V); FF = list(F)
        if side < 0 and not sym:
            VV = [(-p[0], p[1], p[2]) for p in V]
        if sym:
            k = len(V)
            VV += [(-p[0], p[1], p[2]) for p in V]
            FF += [tuple(i + k for i in f) for f in F]
        return mk(nm, VV, FF, mat, sharp)

    def tip(i):
        return (x, C[i][0], C[i][1])

    def body(i):
        h = W[i] / 2
        if h < 1e-5:
            return None
        tt = t * (W[i] / wmax) ** .5
        c = C[i]; nn = N[i]
        U = (x + lean * h, *(c + nn * h)); L = (x - lean * h, *(c - nn * h))
        R = (x + tt + lean * h * bias, *(c + nn * h * bias))
        Kb = (x - tt + lean * h * bias, *(c + nn * h * bias)) if two else (x - back, *c)
        return [U, R, L, Kb]

    out.append(build(name, body, m))

    def strip(sign, mat, proud):
        def ring(i):
            h = W[i] / 2
            gg = g * (W[i] / wmax) ** .5
            if h < 1e-5 or gg < 1e-5:
                return None
            c = C[i]; nn = N[i] * sign
            e = c + nn * h; ex = x + sign * lean * h
            tt = t * (W[i] / wmax) ** .5
            slope = tt / max(h * (1 - sign * bias), 1e-5)             # the plate's rise per unit width from this edge
            return [(ex, *(e + nn * gg * .45)), (ex + proud + gg * .9, *(e - nn * gg * .2)),
                    (ex + slope * gg * 1.9 + .0003, *(e - nn * gg * 1.9)), (ex - gg * .6, *(e - nn * gg * .5))]
        return ring
    if trim is not None:
        out.append(build(name + '_trim', strip(1, trim, .0004), trim))
    if glow is not None:
        out.append(build(name + '_light', strip(-1, glow, -.0002), glow))
    return out


def plate(name, pts, m, x0, x1, ch=.0015, sym=True, sharp=30, side=1):
    """Hard-surface armour plate: side profile pts [(y, z)] from x0 (inside the body) out to x1, the outer face inset
    by ch (a chamfer all round)."""
    n = len(pts); ins = poly_offset(pts, ch)
    V = [(x0, y, z) for y, z in pts] + [(x1 - ch, y, z) for y, z in pts] + [(x1, y, z) for y, z in ins]
    F = []
    for i in range(n):
        j = (i + 1) % n
        F += [(i, j, n + j, n + i), (n + i, n + j, 2 * n + j, 2 * n + i)]
    F += [tuple(range(n)), tuple(range(2 * n, 3 * n))]
    if side < 0 and not sym:
        V = [(-p[0], p[1], p[2]) for p in V]
    if sym:
        k = len(V)
        V += [(-p[0], p[1], p[2]) for p in V]
        F += [tuple(i + k for i in f) for f in F]
    return mk(name, V, F, m, sharp)


def prism(name, pts, w, m, ch=.002, x=0.0, sharp=30):
    """Side profile extruded across the gun (width w, centred on x) with chamfered flanks."""
    n = len(pts); ins = poly_offset(pts, ch)
    xs = [(x - w / 2, ins), (x - w / 2 + ch, pts), (x + w / 2 - ch, pts), (x + w / 2, ins)]
    V = [(xx, y, z) for xx, pp in xs for y, z in pp]
    F = []
    for r in range(3):
        for i in range(n):
            j = (i + 1) % n
            F.append((r * n + i, r * n + j, (r + 1) * n + j, (r + 1) * n + i))
    F += [tuple(range(n)), tuple(range(3 * n, 4 * n))]
    return mk(name, V, F, m, sharp)


# ------------------------------------------------------------------ turned parts
def _lathe(prof, n, place, closed=False):
    V = []; rings = []
    for a, r in prof:
        if r < 1e-6:
            rings.append([len(V)]); V.append(place(a, 0, 0))
        else:
            rings.append(list(range(len(V), len(V) + n)))
            V += [place(a, r, k * 2 * math.pi / n) for k in range(n)]
    F = []
    for i in range(len(rings) - 1):
        a, b = rings[i], rings[i + 1]
        for j in range(n):
            k = (j + 1) % n
            if len(a) == 1 and len(b) == 1:
                continue
            if len(a) == 1:
                F.append((a[0], b[j], b[k]))
            elif len(b) == 1:
                F.append((a[j], a[k], b[0]))
            else:
                F.append((a[j], a[k], b[k], b[j]))
    if closed:                                     # a ring section: the profile is a loop, no caps
        a, b = rings[-1], rings[0]
        for j in range(n):
            k = (j + 1) % n
            F.append((a[j], a[k], b[k], b[j]))
        return V, F
    for r in (rings[0], rings[-1]):
        if len(r) > 1:
            F.append(tuple(r))
    return V, F


def lathe(name, prof, m, z, x=0.0, n=40, sharp=32, phase=0.0, closed=False):
    """Profile [(y, r)] turned round the bore axis through (x, z). n = facets (6 / 8 for a faceted part); closed =
    the profile is a loop (a hollow ring: tubes, bells)."""
    V, F = _lathe(prof, n, lambda a, r, th: (x + r * math.cos(th + phase), a, z + r * math.sin(th + phase)), closed)
    return mk(name, V, F, m, sharp)


def lathe_x(name, prof, c, m, n=40, side=1, sharp=32, phase=0.0, closed=False):
    """Profile [(dx, r)] turned round the cross axis through c = (x, y, z); dx runs outward on `side`."""
    V, F = _lathe(prof, n, lambda a, r, th: (c[0] + side * a, c[1] + r * math.cos(th + phase), c[2] + r * math.sin(th + phase)), closed)
    return mk(name, V, F, m, sharp)


def crystal(name, a, b, r, m, n=6, k0=.22, k1=.62, twist=0.0, flat=1.0, r1=None):
    """A faceted void crystal from a (base point) to b (tip): girdles at k0 and k1 along it. flat < 1 flattens it
    across the gun (X)."""
    from mathutils import Vector
    a, b = Vector(a), Vector(b); d = (b - a)
    ax = d.normalized()
    ref = Vector((1, 0, 0)) if abs(ax.x) < .9 else Vector((0, 0, 1))
    e1 = ax.cross(ref).normalized(); e2 = ax.cross(e1).normalized()
    V = [tuple(a)]
    for kk, rr, tw in ((k0, r, 0.0), (k1, r * .8 if r1 is None else r1, twist)):
        c = a + d * kk
        for i in range(n):
            th = i * 2 * math.pi / n + tw
            p = c + e1 * (rr * math.cos(th)) + e2 * (rr * math.sin(th))
            p.x = c.x + (p.x - c.x) * flat
            V.append(tuple(p))
    V.append(tuple(b))
    F = []
    for i in range(n):
        j = (i + 1) % n
        F += [(0, 1 + i, 1 + j), (1 + i, 1 + j, 1 + n + j, 1 + n + i), (1 + n + i, 1 + n + j, 1 + 2 * n)]
    return mk(name, V, F, m, 12)


def vein(name, pts, m, r=.0008, seed=0, jit=.0035, sub=4, taper=True):
    """A crack of light: a jagged three-sided strand through 3D points (each span broken `sub` times and shaken)."""
    from mathutils import Vector
    rng = np.random.default_rng(seed)
    P = [Vector(p) for p in pts]; Q = [P[0]]
    for a, b in zip(P[:-1], P[1:]):
        for k in range(1, sub + 1):
            p = a.lerp(b, k / sub)
            if k < sub:
                p += Vector((0, *(rng.normal(size=2) * jit)))
            Q.append(p)
    V = []; F = []; nq = len(Q)
    for i, p in enumerate(Q):
        d = (Q[min(i + 1, nq - 1)] - Q[max(i - 1, 0)]).normalized()
        ref = Vector((1, 0, 0))
        e1 = d.cross(ref)
        if e1.length < 1e-4:
            e1 = d.cross(Vector((0, 0, 1)))
        e1.normalize(); e2 = d.cross(e1).normalized()
        rr = r * (math.sin(math.pi * (i + .6) / (nq + .2)) ** .5 if taper else 1.0)
        for k in range(3):
            th = k * 2 * math.pi / 3
            V.append(tuple(p + e1 * (rr * math.cos(th)) + e2 * (rr * math.sin(th))))
    for i in range(nq - 1):
        for k in range(3):
            j = (k + 1) % 3
            F.append((i * 3 + k, i * 3 + j, i * 3 + 3 + j, i * 3 + 3 + k))
    F += [(0, 1, 2), (nq * 3 - 3, nq * 3 - 2, nq * 3 - 1)]
    return mk(name, V, F, m, 60)


def arc(name, pts, x, m, r=.0008, seed=0, jit=.003, sym=True):
    """A vein lying on a flank: side-view points at x (both flanks when sym)."""
    out = [vein(name, [(x, y, z) for y, z in pts], m, r, seed, jit)]
    if sym:
        out.append(vein(name, [(-x, y, z) for y, z in pts], m, r, seed + 7, jit))
    return out


# ------------------------------------------------------------------ the set's signature parts
def round_(name, M, a, L, r, x=0.0, z=0.0, tip=1.0):
    """A crystal round lying along the bore: gold case from y = a forward, a crystal point (L long overall)."""
    return [lathe(name + '_case', [(a, 0), (a, r * 1.08), (a - .002, r * 1.08), (a - .003, r), (a - L * .42, r), (a - L * .42, 0)], M['trim'], z, x, 10),
            crystal(name + '_tip', (x, a - L * .4, z), (x, a - L * tip, z), r * .92, M['crystal'], 6, .12, .5)]


def core(M, y, z, r, w, P, spikes=True, name='core'):
    """The void core on both flanks at (y, z), radius r, on a body w wide: a dark notched seat, a gold bezel, a dish of
    light with a hot centre, a four-point crystal star standing in it, gold claws, and gold points fore and aft."""
    for s in (1, -1):
        x = s * w / 2
        c = (x, y, z)
        # seat: a twelve-sided dark ring, stepped
        P.append(lathe_x(name + '_seat', [(-.004, r * 1.22), (.0022, r * 1.22), (.0034, r * 1.14), (.0034, r * .98), (-.004, r * .98)],
                         c, M['dark'], 12, s, phase=math.pi / 12))
        # bezel: gold, chamfered both ways
        P.append(lathe_x(name + '_bezel', [(-.003, r * 1.06), (.0036, r * 1.06), (.0062, r * .98), (.0062, r * .86), (.0034, r * .78), (-.003, r * .78)],
                         c, M['trim'], 48, s))
        # inner dark step and the dish of light
        P.append(lathe_x(name + '_step', [(-.003, r * .8), (.0026, r * .8), (.0026, r * .7), (.0008, r * .64), (-.003, r * .64)], c, M['dark'], 48, s))
        P.append(lathe_x(name + '_dish', [(.0006, r * .66), (-.0006, r * .3), (-.001, 0)], c, M['dim'], 40, s))
        P.append(lathe_x(name + '_hot', [(-.0004, r * .26), (.0002, r * .12), (.0006, 0)], c, M['glow'], 24, s))
        # the star: a tall crystal, a short cross one, four small diagonals
        for k, (ang, L, rr) in enumerate(((math.pi / 2, .62, .15), (0, .4, .12), (math.pi / 4, .26, .07), (3 * math.pi / 4, .26, .07))):
            dy, dz = math.cos(ang) * r * L, math.sin(ang) * r * L
            for sg in (1, -1):
                P.append(crystal(name + '_star', (x + s * .0012, y, z), (x + s * .0012, y + sg * dy, z + sg * dz), r * rr, M['crystal' if k else 'glow'],
                                 4, .16, .3, flat=.55))
        # claws over the bezel
        for k in range(8):
            a = k * math.pi / 4 + math.pi / 8
            cy, cz = math.cos(a), math.sin(a)
            P.append(K.B(name + '_claw', (.0036, r * .16, r * .34), (x + s * .0048, y + cy * r * 1.0, z + cz * r * 1.0), M['dark'], .0008,
                         rot=(a - math.pi / 2, 0, 0), segs=1))
    if spikes:
        for sg in (1, -1):
            P += talon(name + '_point', [(y + sg * r * .98, z), (y + sg * r * 1.5, z + .001), (y + sg * r * 2.15, z)],
                       [r * .5, r * .3, 0], M['trim'], x=w / 2 + .001, t=.0038, n=8)


def chamber(M, y0, y1, z, r, P, ribs=5, x=0.0, seed=1, name='plasma', arcs=3):
    """The plasma chamber between y0 (rear) and y1 (front): a tube of dim light, a hot line through it, dark turned
    ribs with gold lips, arcs of light crawling over the tube."""
    L = y0 - y1
    P.append(lathe(name + '_tube', [(y0, 0), (y0, r), (y1, r), (y1, 0)], M['dim'], z, x, 20))
    P.append(lathe(name + '_line', [(y0 + .002, 0), (y0, r * .34), (y1, r * .34), (y1 - .002, 0)], M['glow'], z, x, 8))
    for i in range(ribs):
        y = y0 - L * (i + .5) / ribs
        P.append(lathe(name + '_rib', [(y + .0035, r * .9), (y + .0035, r * 1.22), (y + .0015, r * 1.34), (y - .0015, r * 1.34),
                                       (y - .0035, r * 1.22), (y - .0035, r * .9)], M['dark'], z, x, 24))
    rng = np.random.default_rng(seed)
    for k in range(arcs):
        a0 = rng.uniform(0, 6.28)
        pts = []
        for j in range(5):
            a = a0 + j * rng.uniform(.3, .8)
            y = y0 - L * (j + rng.uniform(.1, .9)) / 5
            pts.append((x + math.cos(a) * r * 1.05, y, z + math.sin(a) * r * 1.05))
        P.append(vein(name + '_arc', pts, M['glow'], .0007, seed * 10 + k, r * .25, 3))


def barrel(name, M, y0, y1, z, r, P, x=0.0, bore=None, flutes=0, m=None, rings=()):
    """A turned barrel from y0 (rear) to the muzzle face y1: a crowned, bored muzzle; `rings` = [(y, r, len)] steps."""
    m = m or M['dark']; bore = bore or r * .5
    prof = [(y0, 0), (y0, r)]
    for ry, rr, rl in sorted(rings, key=lambda t: -t[0]):
        prof += [(ry + rl / 2 + .0015, r), (ry + rl / 2, rr), (ry - rl / 2, rr), (ry - rl / 2 - .0015, r)]
    prof += [(y1 + .002, r), (y1, r - .0018), (y1, bore), (y1 + .03, bore), (y1 + .03, 0)]
    P.append(lathe(name, prof, m, z, x, 32))


def studs(M, pts, x, P, r=.0022, m=None, sym=True):
    """Small domed studs on a flank (gold by default)."""
    m = m or M['trim']
    for y, z in pts:
        for s in ((1, -1) if sym else (1,)):
            P.append(lathe_x('stud', [(-.001, r), (.0006, r), (.0013, r * .55), (.0015, 0)], (s * x, y, z), m, 10, s))


def lights(M, pts, x, P, r=.0022, sym=True):
    """Small lit lenses in a dark collar on a flank."""
    for y, z in pts:
        for s in ((1, -1) if sym else (1,)):
            P.append(lathe_x('eye_collar', [(-.001, r * 1.5), (.001, r * 1.5), (.0014, r * 1.2), (.0014, r), (-.001, r)], (s * x, y, z), M['dark'], 12, s))
            P.append(lathe_x('eye', [(.0006, r), (.0012, r * .5), (.0013, 0)], (s * x, y, z), M['glow'], 10, s))


def feathers(name, M, P, y0, y1, z, n=3, w=.04, x=.022, t=.006, up=1, rise=.01, bulge=.004, overlap=.42, lean=.25, bias=.45, trim=True,
             glow=True, step=.0016, m=None, taper=.8):
    """A row of overlapping blade plates along a flank from y0 (rear) to y1 (the last tip), each pointing forward and
    lying over the root of the next (rear outermost). up = +1 for a row whose tips flick up (the crown of a shroud),
    -1 for the keel row under it."""
    L = (y0 - y1) / (1 + (n - 1) * (1 - overlap))
    for i in range(n):
        ys = y0 - i * L * (1 - overlap); ye = ys - L
        ww = w * taper ** i
        P += talon('%s%d' % (name, i), [(ys, z - up * bulge), (ys - L * .45, z + up * bulge), (ye, z + up * rise)], [ww * .62, ww, 0], m or M['silver'],
                   x=x - i * step, t=t * taper ** i, lean=lean * up, bias=bias * up, trim=M['trim'] if (trim and up > 0) else None,
                   glow=M['glow'] if (glow and up > 0) else None, n=12)
        if trim and up < 0:
            P += talon('%s%d_bead' % (name, i), [(ys - L * .1, z - up * bulge - ww * .3), (ys - L * .5, z + up * bulge - ww * .46), (ye + L * .08, z + up * rise * .9)],
                       [.003, .0034, 0], M['trim'], x=x - i * step + .0012, t=.0016, n=10)
