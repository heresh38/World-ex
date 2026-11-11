"""Meridian's alien ecosystem (docs/operation/ART_DIRECTION.md section 5): its own plant language, growing the way
plants grow. Years of it: rope-thick vines that climb and wrap, roots that split the ground, curtains hanging from
whatever overhangs, broad fleshy leaves, shelf fungus, bulbs that glow, moss. Beautiful and a little threatening.

Everything is built from a stem (a tapering, wandering tube in ru_bark), a leaf (a cupped paddle in ru_leaf) and a
bulb (a small lantern in ru_bio: the light). g = what is thick enough to stand behind (trunks, big roots: collides),
gd = the rest (never collides).

  vine(gd, pts, r)                 one stem along points, leaves and the odd bulb along it
  climber(gd, foot, n, height, ..)  a plant climbing a wall: stems up from the foot, branching, hugging the face
  curtain(gd, a, b, drop)          strands hanging from an edge between a and b, bulbs at their ends
  roots(g, gd, c, r)               thick roots breaking out of the ground round a point, the paving lifted
  tree(g, gd, c, h)                a braided trunk, a crown of great fans, light under them
  fungus(gd, p, n, r)              shelf brackets up a wall
  moss(gd, c, r)                   a low cushion of it, bright specks
  bulbs(gd, c, n)                  a stand of lanterns on stalks
  pads(g, gd, c, r)                wide floating pads where water stood (the canal)
"""
import math
import random
from mathutils import Vector, Matrix
import ruinkit as rk

TAU = 2 * math.pi


def _wander(a, b, n, amp, rnd, sag=0.0):
    """n+1 points from a to b that wander like something that grew (and sag like something that hangs)"""
    a, b = Vector(a), Vector(b)
    d = b - a
    side = d.cross(Vector((0, 0, 1)))
    if side.length < 1e-4:
        side = Vector((1, 0, 0))
    side.normalize()
    up = side.cross(d).normalized()
    ph1, ph2 = rnd.uniform(0, TAU), rnd.uniform(0, TAU)
    pts = []
    for i in range(n + 1):
        t = i / n
        env = math.sin(math.pi * t)
        p = a + d * t + side * (amp * env * math.sin(t * 5.3 + ph1)) + up * (amp * .6 * env * math.sin(t * 7.1 + ph2))
        p.z -= sag * env
        pts.append(p)
    return pts


def leaf(gd, p, out, size, rnd, mat="ru_leaf"):
    """a cupped paddle on a short stalk, facing roughly `out`, drooping"""
    p = Vector(p)
    o = Vector(out)
    o.z -= rnd.uniform(.1, .6)
    o.normalize()
    side = o.cross(Vector((0, 0, 1)))
    if side.length < 1e-3:
        side = Vector((1, 0, 0))
    side.normalize()
    up = side.cross(o).normalized()
    L, W = size, size * rnd.uniform(.5, .75)
    rows = ((0.0, .12), (.35, 1.0), (.75, .8), (1.0, .05))
    vs, faces = [], []
    for (t, wd) in rows:
        c = p + o * (L * t) - up * (L * .25 * t * t)
        for s in (-1, 0, 1):
            vs.append(tuple(c + side * (s * W * .5 * wd) + up * (abs(s) * W * .16 * wd)))
    for r in range(3):
        for k in range(2):
            a = r * 3 + k
            faces.append((a, a + 1, a + 4, a + 3))
            faces.append((a + 3, a + 4, a + 1, a))
    gd.add(vs, faces, mat, smooth=True)


def bulb(gd, p, r, mat="ru_bio"):
    """a small lantern: a glowing drop"""
    p = Vector(p)
    n = 6
    vs = [tuple(p + Vector((0, 0, r * 1.5)))]
    for (zz, rr) in ((.7, .75), (0.0, 1.0), (-.8, .6)):
        for i in range(n):
            a = TAU * i / n
            vs.append(tuple(p + Vector((math.cos(a) * r * rr, math.sin(a) * r * rr, r * zz))))
    vs.append(tuple(p + Vector((0, 0, -r * 1.3))))
    faces = [(0, 1 + (i + 1) % n, 1 + i) for i in range(n)]
    for ring in range(2):
        for i in range(n):
            a, b = 1 + ring * n + i, 1 + ring * n + (i + 1) % n
            faces.append((a, b, b + n, a + n))
    last = len(vs) - 1
    faces += [(last, 1 + 2 * n + i, 1 + 2 * n + (i + 1) % n) for i in range(n)]
    gd.add(vs, faces, mat, smooth=True)


def vine(gd, pts, r, seed, leaves=1.0, glow=.15, out=None):
    """one stem along the points: thick at the foot, thin at the tip, leaves along it, a bulb now and then"""
    rnd = random.Random(seed)
    pts = [Vector(p) for p in pts]
    rk.tube(gd, "ru_bark", [tuple(p) for p in pts], r, 6, r_end=max(r * .25, .012))
    for i in range(1, len(pts)):
        if rnd.random() < .75 * leaves:
            d = (pts[i] - pts[i - 1]).normalized()
            o = Vector(out) if out is not None else d.cross(Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), .3)))
            if o.length < 1e-3:
                o = Vector((1, 0, 0))
            o = (o.normalized() + Vector((rnd.uniform(-.5, .5), rnd.uniform(-.5, .5), rnd.uniform(-.2, .4)))).normalized()
            leaf(gd, pts[i], o, rnd.uniform(.28, .6) * (.6 + r * 6), rnd)
        if rnd.random() < glow:
            bulb(gd, pts[i] + Vector((rnd.uniform(-.1, .1), rnd.uniform(-.1, .1), -.12)), rnd.uniform(.05, .1))


def climber(gd, foot, normal, height, width, seed, density=1.0):
    """A plant climbing a wall from `foot` (on the ground at the wall), `normal` the wall's outward normal: main stems
    go up hugging the face, wander sideways, branch; the higher, the thinner; leaves stand off the wall."""
    rnd = random.Random(seed)
    n = Vector((normal[0], normal[1], 0)).normalized()
    t = Vector((-n.y, n.x, 0))
    foot = Vector(foot)
    for k in range(max(1, int(round((2 + width / 2.5) * density)))):
        u0 = rnd.uniform(-width / 2, width / 2)
        top = height * rnd.uniform(.45, 1.0)
        a = foot + t * u0 + n * .1
        b = foot + t * (u0 + rnd.uniform(-2.5, 2.5)) + n * .09 + Vector((0, 0, top))
        pts = _wander(a, b, max(5, int(top / 1.1)), .5, rnd)
        for p in pts:                                             # keep it on the face, not in it
            off = (p - foot).dot(n)
            p -= n * (off - rnd.uniform(.07, .16))
        r = rnd.uniform(.035, .09) * (.7 + top / 20)
        vine(gd, pts, r, seed * 13 + k, leaves=.8, glow=.12, out=n)
        for j in range(rnd.randint(1, 3)):                        # branches
            i = rnd.randrange(1, len(pts) - 1)
            e = pts[i] + t * rnd.uniform(-2.2, 2.2) + Vector((0, 0, rnd.uniform(.3, 2.2)))
            br = _wander(pts[i], e, 4, .25, rnd)
            for p in br:
                off = (p - foot).dot(n)
                p -= n * (off - rnd.uniform(.07, .14))
            vine(gd, br, r * .5, seed * 17 + k * 5 + j, leaves=1.0, glow=.2, out=n)


def curtain(gd, a, b, drop, seed, density=1.0):
    """strands hanging from the edge a-b: each its own length, a few leaves, a lantern at the end of some"""
    rnd = random.Random(seed)
    a, b = Vector(a), Vector(b)
    L = (b - a).length
    for k in range(max(2, int(L * 1.3 * density))):
        s = a.lerp(b, rnd.random())
        length = drop * rnd.uniform(.3, 1.0)
        e = s + Vector((rnd.uniform(-.25, .25), rnd.uniform(-.25, .25), -length))
        pts = _wander(s, e, max(3, int(length / .9)), .12, rnd)
        vine(gd, pts, rnd.uniform(.018, .04), seed * 19 + k, leaves=.35, glow=0.0)
        if rnd.random() < .4:
            bulb(gd, e + Vector((0, 0, -.08)), rnd.uniform(.06, .12))


def roots(g, gd, c, r, seed, lift=True):
    """thick roots breaking out of the ground round c and going back into it; the paving they lifted lies tilted"""
    rnd = random.Random(seed)
    c = Vector(c)
    for k in range(rnd.randint(4, 7)):
        a = TAU * (k + rnd.random() * .6) / 6
        d = Vector((math.cos(a), math.sin(a), 0))
        L = r * rnd.uniform(.6, 1.0)
        thick = rnd.uniform(.12, .3)
        pts = [c + d * (L * t) + Vector((rnd.uniform(-.2, .2), rnd.uniform(-.2, .2), -.15 + math.sin(math.pi * min(t * 1.15, 1)) * thick * 2.2))
               for t in (0, .2, .45, .7, .9, 1.0)]
        rk.tube(g if thick > .2 else gd, "ru_bark", [tuple(p) for p in pts], thick, 7, r_end=thick * .3)
        if rnd.random() < .5:
            leaf(gd, pts[2], d, rnd.uniform(.5, .9), rnd)
        if lift and rnd.random() < .6:
            p = c + d * (L * .5)
            R = Matrix.Rotation(a, 3, 'Z') @ Matrix.Rotation(rnd.uniform(.15, .45), 3, 'Y')
            rk.box(g, "ru_fracture", (p.x, p.y, c.z + .12), (rnd.uniform(.5, .9), rnd.uniform(.4, .7), .07), R=R)


def tree(g, gd, c, h, seed, crown=1.0):
    """a tree of this place: a trunk of braided stems, a crown of great drooping fans with lanterns under them"""
    rnd = random.Random(seed)
    c = Vector(c)
    top = c + Vector((rnd.uniform(-.6, .6), rnd.uniform(-.6, .6), h))
    for k in range(4):
        a = TAU * k / 4 + rnd.random()
        pts = []
        for i in range(9):
            t = i / 8
            rad = (.38 * (1 - t) + .1) * h / 8
            pts.append(c.lerp(top, t) + Vector((math.cos(a + t * 4.5) * rad, math.sin(a + t * 4.5) * rad, 0)))
        rk.tube(g, "ru_bark", [tuple(p) for p in pts], .2 * h / 8, 7, r_end=.07 * h / 8)
    for k in range(int(9 * crown)):
        a = TAU * k / (9 * crown) + rnd.uniform(-.2, .2)
        reach = h * rnd.uniform(.3, .55)
        d = Vector((math.cos(a), math.sin(a), 0))
        e = top + d * reach + Vector((0, 0, rnd.uniform(-.25, .15) * h))
        pts = _wander(top, e, 5, .3, rnd, sag=-reach * .15)
        rk.tube(gd, "ru_bark", [tuple(p) for p in pts], .06 * h / 8, 5, r_end=.02)
        for i in range(2, len(pts)):
            leaf(gd, pts[i], d, rnd.uniform(.9, 1.6) * h / 8, rnd)
            if rnd.random() < .35:
                bulb(gd, pts[i] + Vector((0, 0, -.35)), rnd.uniform(.08, .16))
    roots(g, gd, c, h * .32, seed + 3)


def fungus(gd, p, normal, r, seed, mat="ru_fungus"):
    """shelf brackets stepping up a wall: half discs, the big ones low, their rims alight"""
    rnd = random.Random(seed)
    n = Vector((normal[0], normal[1], 0)).normalized()
    t = Vector((-n.y, n.x, 0))
    p = Vector(p)
    for k in range(rnd.randint(3, 6)):
        rr = r * (1 - k * .13) * rnd.uniform(.7, 1.0)
        c = p + t * rnd.uniform(-r, r) + Vector((0, 0, k * r * rnd.uniform(.5, .9)))
        m = 8
        vs = [tuple(c)]
        for i in range(m + 1):
            a = math.pi * i / m
            q = c + t * (math.cos(a) * rr) + n * (math.sin(a) * rr * .8) + Vector((0, 0, -rr * .12))
            vs.append(tuple(q))
        under = len(vs)
        vs.append(tuple(c + Vector((0, 0, -rr * .35))))
        faces = [(0, i + 1, i + 2) for i in range(m)] + [(under, i + 2, i + 1) for i in range(m)]
        gd.add(vs, faces, mat, smooth=True)
        if rnd.random() < .5:
            bulb(gd, c + n * rr * .7 + Vector((0, 0, -rr * .3)), rr * .12)


def moss(gd, c, r, seed, mat="ru_moss"):
    """a low cushion over whatever is under it"""
    rnd = random.Random(seed)
    c = Vector(c)
    m, rings = 10, 3
    vs = [tuple(c + Vector((0, 0, r * .16)))]
    for k in range(1, rings + 1):
        for i in range(m):
            a = TAU * i / m + k * .3
            rr = r * k / rings * rnd.uniform(.8, 1.1)
            vs.append(tuple(c + Vector((math.cos(a) * rr, math.sin(a) * rr, r * .16 * (1 - (k / rings) ** 2) + .015))))
    faces = [(0, 1 + i, 1 + (i + 1) % m) for i in range(m)]
    for k in range(rings - 1):
        for i in range(m):
            a, b = 1 + k * m + i, 1 + k * m + (i + 1) % m
            faces.append((a, a + m, b + m, b))
    gd.add(vs, faces, mat, smooth=True)


def bulbs(gd, c, n, seed, spread=1.2):
    """a stand of lanterns on thin stalks"""
    rnd = random.Random(seed)
    c = Vector(c)
    for k in range(n):
        p = c + Vector((rnd.uniform(-spread, spread), rnd.uniform(-spread, spread), 0))
        hgt = rnd.uniform(.3, 1.1)
        top = p + Vector((rnd.uniform(-.15, .15), rnd.uniform(-.15, .15), hgt))
        rk.tube(gd, "ru_bark", [tuple(p), tuple(p.lerp(top, .5) + Vector((.05, 0, 0))), tuple(top)], .018, 4, r_end=.01)
        bulb(gd, top + Vector((0, 0, .08)), rnd.uniform(.06, .13))
        if rnd.random() < .6:
            leaf(gd, p + Vector((0, 0, .05)), (rnd.uniform(-1, 1), rnd.uniform(-1, 1), .4), rnd.uniform(.3, .5), rnd)


def pads(g, gd, c, r, seed):
    """wide pads on short thick stems where water stood, a lantern rising from some"""
    rnd = random.Random(seed)
    c = Vector(c)
    for k in range(rnd.randint(4, 8)):
        p = c + Vector((rnd.uniform(-r, r), rnd.uniform(-r, r), 0))
        rr = rnd.uniform(.5, 1.3)
        hgt = rnd.uniform(.12, .45)
        rk.cyl(gd, "ru_bark", (p.x, p.y), .07, c.z, c.z + hgt, n=6, smooth=False)
        rk.cyl(gd, "ru_leaf", (p.x, p.y), rr, c.z + hgt, c.z + hgt + .05, n=12, r1=rr * 1.05, smooth=False)
        if rnd.random() < .4:
            top = p + Vector((0, 0, hgt + rnd.uniform(.4, .9)))
            rk.tube(gd, "ru_bark", [(p.x, p.y, c.z + hgt), tuple(top)], .02, 4)
            bulb(gd, top + Vector((0, 0, .1)), rnd.uniform(.08, .14))
