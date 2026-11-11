"""Meridian's streets and what was left in them (docs/operation/ART_DIRECTION.md sections 4, 6, 7): real city streets
that were abandoned in a day. Road markings, curbs, drains, manholes, potholes; lamps, signals, signs, shelters,
bollards, benches; the army's sandbags, emplacements and floodlights; and our own vehicles, wrecked where they stopped:
cars, vans, a bus, armoured carriers, a train.

Everything is ours (Blender, this file). g = what you can stand behind (collides), gd = detail (never collides).
"""
import math
import random
from mathutils import Vector, Matrix
import ruinkit as rk

TAU = 2 * math.pi
PI = math.pi
PAINTS = ("ru_car_red", "ru_car_blue", "ru_car_white", "ru_car_green")


def _T(c, yaw):
    cy, sy = math.cos(yaw), math.sin(yaw)

    def P(x, y, z):
        return (c[0] + x * cy - y * sy, c[1] + x * sy + y * cy, c[2] + z)
    return P


def _box(target, mat, P, yaw, x, y, z, hx, hy, hz, ang=0.0, **kw):
    rk.box(target, mat, P(x, y, z), (hx, hy, hz), yaw + ang, **kw)


# ------------------------------------------------------------------ the street itself
def street(g, gd, a, b, width, seed, lanes=2, walk=0.0, z=0.04):
    """Dress a straight street from a to b (x, y): a worn centre line, edge lines, curbs (and raised pavements `walk`
    wide beyond them), drains at the curbs, manholes, potholes and patches."""
    rnd = random.Random(seed)
    a, b = Vector(a), Vector(b)
    d = b - a
    L = d.length
    u = d / L
    n = Vector((-u.y, u.x))
    yaw = math.atan2(u.y, u.x)

    def at(s, off, zz=z):
        p = a + u * s + n * off
        return (p.x, p.y, zz)
    # markings: dashes down the middle (worn away in places), a line at each edge
    s = 2.0
    while s < L - 4:
        if rnd.random() < .7:
            ln = rnd.uniform(2.0, 3.0)
            rk.box(gd, "ru_paint", at(s + ln / 2, 0, z + .012), (ln / 2, .07, .004), yaw)
        s += 6.0
    for side in (-1, 1):
        s = 0.0
        while s < L:
            ln = min(rnd.uniform(6, 16), L - s)
            if rnd.random() < .75:
                rk.box(gd, "ru_paint", at(s + ln / 2, side * (width / 2 - .35), z + .012), (ln / 2, .05, .004), yaw)
            s += ln + rnd.uniform(.5, 3)
        # the curb, and the pavement behind it
        rk.box(g, "ru_concrete", at(L / 2, side * (width / 2 + .12), z + .07), (L / 2, .12, .09), yaw)
        if walk > 0:
            rk.box(g, "ru_stone", at(L / 2, side * (width / 2 + .24 + walk / 2), z + .06), (L / 2, walk / 2, .09), yaw)
        s = rnd.uniform(6, 14)
        while s < L - 4:                                           # drains in the gutter
            rk.box(gd, "ru_metal", at(s, side * (width / 2 - .28), z + .01), (.45, .2, .006), yaw)
            for k in range(5):
                rk.box(gd, "ru_block_dark", at(s - .36 + k * .18, side * (width / 2 - .28), z + .018), (.03, .16, .003), yaw)
            s += rnd.uniform(22, 36)
    for k in range(int(L / 28) + 1):                               # manholes
        s, off = rnd.uniform(3, L - 3), rnd.uniform(-width / 4, width / 4)
        p = at(s, off)
        rk.cyl(gd, "ru_metal", (p[0], p[1]), .42, z, z + .02, n=14, smooth=False)
    for k in range(int(L / 16) + 1):                               # potholes and old patches
        s, off = rnd.uniform(2, L - 2), rnd.uniform(-width / 2 + 1, width / 2 - 1)
        p = at(s, off)
        r = rnd.uniform(.5, 1.6)
        m = 9
        vs = [(p[0], p[1], z + .008)] + [(p[0] + math.cos(TAU * i / m) * r * rnd.uniform(.6, 1.1), p[1] + math.sin(TAU * i / m) * r * rnd.uniform(.5, 1.0), z + .008) for i in range(m)]
        gd.add(vs, [(0, 1 + i, 1 + (i + 1) % m) for i in range(m)], "ru_rubble" if rnd.random() < .6 else "ru_fracture")


# ------------------------------------------------------------------ street furniture
def signal(g, gd, p, yaw, seed):
    """a traffic signal on a mast with an arm over the road; dead, one lamp hanging by its cable"""
    rnd = random.Random(seed)
    P = _T(p, yaw)
    rk.tube(g, "ru_metal", [P(0, 0, 0), P(0, 0, 5.6)], .11, 8, r_end=.09)
    rk.tube(g, "ru_metal", [P(0, 0, 5.4), P(1.6, 0, 5.75), P(4.2, 0, 5.7)], .07, 6)
    for k, x in enumerate((2.2, 4.0)):
        drop = .35 if not (k == 1 and rnd.random() < .5) else 1.4
        rk.box(g, "ru_block_dark", P(x, 0, 5.7 - drop), (.16, .14, .42), yaw + (rnd.uniform(-.6, .6) if drop > 1 else 0))
        rk.tube(gd, "ru_metal", [P(x, 0, 5.7), P(x, 0, 5.7 - drop + .42)], .015, 4)
        for i in range(3):
            rk.box(gd, "ru_glass", P(x, -.145, 5.96 - drop - i * .26), (.09, .005, .09), yaw)


def sign(g, gd, p, yaw, seed):
    """a road sign: a post, a blank coloured plate (nothing to read: the paint went), bent"""
    rnd = random.Random(seed)
    P = _T(p, yaw)
    lean = rnd.uniform(-.25, .25)
    top = P(lean * 2.6, 0, 2.7)
    rk.tube(g, "ru_metal", [P(0, 0, 0), top], .04, 6)
    R = Matrix.Rotation(yaw, 3, 'Z') @ Matrix.Rotation(lean, 3, 'Y')
    kind = rnd.random()
    if kind < .5:
        rk.box(gd, rnd.choice(("ru_car_blue", "ru_car_white", "ru_car_green")), (top[0], top[1], top[2] - .1), (.5, .02, .34), R=R)
    else:
        rk.cyl(gd, rnd.choice(("ru_car_red", "ru_car_white")), (top[0], top[1]), .34, top[2] - .12, top[2] - .08, n=3 if kind > .8 else 14, smooth=False)


def shelter(g, gd, p, yaw, seed):
    """a stop shelter: a roof on two frames, a glass back, a bench, an advert panel that still flickers"""
    rnd = random.Random(seed)
    P = _T(p, yaw)
    for x in (-1.9, 1.9):
        _box(g, "ru_metal", P, yaw, x, .6, 1.25, .05, .05, 1.25)
        _box(g, "ru_metal", P, yaw, x, -.5, 1.25, .05, .05, 1.25)
    _box(g, "ru_composite", P, yaw, 0, 0, 2.55, 2.1, .85, .05)
    if rnd.random() < .6:
        _box(gd, "ru_glass", P, yaw, 0, .62, 1.3, 1.85, .012, 1.0)
    _box(g, "ru_metal", P, yaw, -.3, .3, .45, 1.2, .2, .03)
    _box(g, rnd.choice(("ru_holo_cyan", "ru_holo_magenta", "ru_composite", "ru_composite")), P, yaw, 1.5, -.1, 1.25, .04, .55, .9)


def bollards(g, a, b, n, seed):
    rnd = random.Random(seed)
    a, b = Vector(a), Vector(b)
    for k in range(n):
        p = a.lerp(b, k / max(n - 1, 1))
        if rnd.random() < .85:
            rk.cyl(g, "ru_metal", (p.x, p.y), .1, p.z, p.z + rnd.choice((.9, .9, .9, .5)), n=8, smooth=False)


def bench(g, p, yaw):
    P = _T(p, yaw)
    _box(g, "ru_stone", P, yaw, 0, 0, .22, .95, .22, .22)
    _box(g, "ru_brass", P, yaw, 0, .2, .62, .95, .03, .2)


def crates(g, gd, p, seed, n=4):
    """supply crates stacked and spilled, a lid off"""
    rnd = random.Random(seed)
    for k in range(n):
        x, y = p[0] + rnd.uniform(-1.4, 1.4), p[1] + rnd.uniform(-1.4, 1.4)
        s = rnd.uniform(.35, .6)
        zz = p[2] + s + (2 * .45 if k == 0 and n > 2 else 0)
        rk.box(g, "ru_car_green" if rnd.random() < .6 else "ru_corrugate", (x, y, zz), (s * 1.3, s, s), rnd.uniform(0, PI))
    rk.box(gd, "ru_car_green", (p[0] + 1.8, p[1] + .6, p[2] + .03), (.6, .45, .03), rnd.uniform(0, PI))


def luggage(gd, p, seed, n=6):
    """what people carried and dropped"""
    rnd = random.Random(seed)
    for k in range(n):
        x, y = p[0] + rnd.uniform(-2, 2), p[1] + rnd.uniform(-2, 2)
        s = rnd.uniform(.2, .38)
        R = Matrix.Rotation(rnd.uniform(0, TAU), 3, 'Z') @ Matrix.Rotation(rnd.choice((0, 0, PI / 2)), 3, 'X')
        rk.box(gd, rnd.choice(("ru_banner", "ru_car_blue", "ru_plaster", "ru_car_red")), (x, y, p[2] + s * .45), (s, s * .55, s * .32), R=R)


# ------------------------------------------------------------------ the army's line
def sandbags(g, c, yaw, length, seed, rows=3):
    """a sandbag wall: bags laid in courses, the top one slumped"""
    rnd = random.Random(seed)
    P = _T(c, yaw)
    n = max(2, int(length / .62))
    for r in range(rows):
        for k in range(n - (r % 2)):
            if r == rows - 1 and rnd.random() < .25:
                continue
            x = -length / 2 + (k + .5 + (r % 2) * .5) * length / n
            off = [(rnd.uniform(-.03, .03), rnd.uniform(-.03, .03), rnd.uniform(-.03, .02)) for _ in range(8)]
            rk.box(g, "ru_sack", P(x, rnd.uniform(-.04, .04), .14 + r * .25), (.3, .19, .125), yaw + rnd.uniform(-.08, .08), offsets=off)


def emplacement(g, gd, c, yaw, seed):
    """a gun position: a horseshoe of sandbags, a heavy gun on its mount (spent), ammunition tins"""
    P = _T(c, yaw)
    sandbags(g, P(0, 1.3, 0), yaw, 3.6, seed)
    sandbags(g, P(-1.9, .3, 0), yaw + PI / 2, 2.2, seed + 1)
    sandbags(g, P(1.9, .3, 0), yaw + PI / 2, 2.2, seed + 2)
    for a in (0, TAU / 3, 2 * TAU / 3):
        rk.tube(g, "ru_metal", [P(math.cos(a) * .55, .2 + math.sin(a) * .55, 0), P(0, .2, .95)], .035, 5)
    _box(g, "ru_block_dark", P, yaw, 0, .35, 1.08, .12, .42, .12)
    rk.tube(g, "ru_block_dark", [P(0, .7, 1.1), P(0, 2.0, 1.22)], .04, 6)
    _box(gd, "ru_car_green", P, yaw, .7, -.2, .14, .2, .14, .14)
    _box(gd, "ru_car_green", P, yaw, -.8, -.4, .14, .2, .14, .14, .5)


def floodlight(g, gd, p, yaw, seed, lit=False):
    """a mast with a bank of lamps; returns where its light is (or None when dead)"""
    rnd = random.Random(seed)
    P = _T(p, yaw)
    h = 6.5
    lean = rnd.uniform(-.06, .06)
    top = P(lean * h, 0, h)
    rk.tube(g, "ru_metal", [P(0, 0, 0), top], .09, 7)
    for a in (0, TAU / 3, 2 * TAU / 3):
        rk.tube(gd, "ru_metal", [P(math.cos(a) * 1.1, math.sin(a) * 1.1, 0), P(0, 0, 1.4)], .03, 5)
    for k in (-1, 1):
        rk.box(g, "ru_sign_amber" if lit else "ru_block_dark", (top[0], top[1], top[2] - .1 + k * .32), (.5, .12, .14), yaw)
    return (top[0], top[1], top[2]) if lit else None


# ------------------------------------------------------------------ vehicles (ours)
def _wheel(g, P, x, y, r=.36, w=.26):
    rk.tube(g, "ru_block_dark", [P(x, y - w / 2 if y < 0 else y + w / 2, r), P(x, y + w / 2 if y < 0 else y - w / 2, r)], r, 10, smooth=False)


def car(g, gd, c, yaw, seed, burnt=False, roll=0.0):
    """a city car: a low rounded hull, a glass cabin, four wheels; doors open where they ran, burnt where it burned"""
    rnd = random.Random(seed)
    paint = "ru_metal" if burnt else rnd.choice(PAINTS)
    cy, sy = math.cos(yaw), math.sin(yaw)
    R = Matrix.Rotation(yaw, 3, 'Z') @ Matrix.Rotation(roll, 3, 'X')
    lift = abs(math.sin(roll)) * .85

    def P(x, y, z):
        v = R @ Vector((x, y, z))
        return (c[0] + v.x, c[1] + v.y, c[2] + v.z + lift)

    def bx(target, mat, x, y, z, hx, hy, hz, offsets=None):
        rk.box(target, mat, P(x, y, z), (hx, hy, hz), R=R, offsets=offsets)
    L, W = 2.15, .9
    nose = [(0, 0, 0)] * 4 + [(-.25, 0, -.12), (.3, 0, -.14), (.3, 0, -.14), (-.25, 0, -.12)]
    bx(g, paint, 0, 0, .62, L, W, .3, nose)                                             # the hull
    cab = [(0, 0, 0)] * 4 + [(.55, .12, 0), (-.75, .12, 0), (-.75, -.12, 0), (.55, -.12, 0)]
    bx(g, paint, -.15, 0, 1.2, 1.25, W - .04, .3, cab)                                  # the cabin
    if not burnt:
        for s in (-1, 1):
            if rnd.random() < .7:
                bx(gd, "ru_glass", -.15, s * (W - .1), 1.2, .9, .012, .2)
        if rnd.random() < .6:
            bx(gd, "ru_glass", .92, 0, 1.2, .012, W - .2, .2, [(0, 0, 0)] * 4 + [(-.28, 0, 0)] * 4)
    for sx in (-1.35, 1.35):
        for s in (-1, 1):
            if not (burnt and rnd.random() < .3):
                rk.tube(g, "ru_block_dark", [P(sx, s * (W - .02), .36), P(sx, s * (W - .3), .36)], .36, 10, smooth=False)
    bx(g, "ru_block_dark", L + .04, 0, .5, .05, W - .05, .12)
    bx(g, "ru_block_dark", -L - .04, 0, .5, .05, W - .05, .12)
    for s in (-1, 1):
        bx(gd, "ru_sign_amber" if (not burnt and rnd.random() < .12) else "ru_glass", L + .09, s * .62, .64, .02, .16, .06)
    if not burnt and roll == 0.0 and rnd.random() < .5:                                   # a door left open
        s = rnd.choice((-1, 1))
        Rd = R @ Matrix.Rotation(s * rnd.uniform(.7, 1.2), 3, 'Z')
        p = P(.55, s * (W + .02), .85)
        v = Rd @ Vector((-.5, 0, 0))
        rk.box(g, paint, (p[0] + v.x, p[1] + v.y, p[2]), (.5, .03, .42), R=Rd)


def bus(g, gd, c, yaw, seed, roll=0.0):
    """a city bus: a long box with a band of windows, doors, six wheels; on its side where it went over"""
    rnd = random.Random(seed)
    R = Matrix.Rotation(yaw, 3, 'Z') @ Matrix.Rotation(roll, 3, 'X')
    lift = abs(math.sin(roll)) * 1.3

    def P(x, y, z):
        v = R @ Vector((x, y, z))
        return (c[0] + v.x, c[1] + v.y, c[2] + v.z + lift)

    def bx(target, mat, x, y, z, hx, hy, hz):
        rk.box(target, mat, P(x, y, z), (hx, hy, hz), R=R)
    paint = rnd.choice(("ru_car_white", "ru_car_blue"))
    bx(g, paint, 0, 0, 1.0, 5.6, 1.3, .65)
    bx(g, paint, 0, 0, 2.95, 5.6, 1.3, .2)
    bx(g, "ru_composite", 0, 0, 3.2, 4.6, 1.0, .08)
    for k in range(9):                                                                   # the window band: posts and glass
        x = -5.2 + k * 1.3
        for s in (-1, 1):
            bx(g, paint, x, s * 1.27, 2.2, .06, .04, .55)
            if rnd.random() < .5:
                bx(gd, "ru_glass", x + .65, s * 1.27, 2.2, .58, .012, .5)
    bx(g, paint, 5.55, 0, 2.2, .05, 1.3, .55)
    bx(g, paint, -5.55, 0, 2.2, .05, 1.3, .55)
    for sx in (-4.0, 2.9, 4.2):
        for s in (-1, 1):
            rk.tube(g, "ru_block_dark", [P(sx, s * 1.32, .5), P(sx, s * 1.0, .5)], .5, 10, smooth=False)
    bx(gd, rnd.choice(("ru_holo_cyan", "ru_sign_amber", "ru_composite")), 5.62, 0, 2.95, .02, .9, .14)


def carrier(g, gd, c, yaw, seed, burnt=False):
    """an armoured carrier: a wedge-nosed hull on six wheels, a small turret, hatches open; where the line broke"""
    rnd = random.Random(seed)
    P = _T(c, yaw)
    paint = "ru_metal" if burnt else "ru_car_green"
    nose = [(0, 0, 0), (-.5, 0, .25), (-.5, 0, .25), (0, 0, 0), (0, .25, 0), (-1.1, .25, 0), (-1.1, -.25, 0), (0, -.25, 0)]
    rk.box(g, paint, P(0, 0, 1.25), (3.3, 1.35, .7), yaw, offsets=nose)
    _box(g, paint, P, yaw, -.3, 0, 2.15, 1.0, .8, .25)
    rk.tube(g, "ru_block_dark", [P(.4, 0, 2.2), P(2.6, 0, 2.3 + rnd.uniform(-.3, .2))], .07, 6)
    for sx in (-2.2, -.2, 1.8):
        for s in (-1, 1):
            if not (burnt and rnd.random() < .35):
                rk.tube(g, "ru_block_dark", [P(sx, s * 1.4, .58), P(sx, s * 1.05, .58)], .58, 10, smooth=False)
    Rh = Matrix.Rotation(yaw, 3, 'Z') @ Matrix.Rotation(-1.2, 3, 'Y')
    p = P(-2.2, .5, 2.1)
    rk.box(g, paint, p, (.35, .3, .03), R=Rh)                                             # a hatch thrown back
    _box(g, paint, P, yaw, -3.35, 0, 1.1, .04, .7, .5, rnd.uniform(.3, .9))                 # the rear door, open
    for s in (-1, 1):
        _box(gd, "ru_glass", P, yaw, 2.5, s * .7, 1.6, .02, .18, .07)


def train_car(g, gd, c, yaw, seed):
    """a metro car: a long shell with a window band and door openings, bogies, the lights long dead (one flickers)"""
    rnd = random.Random(seed)
    P = _T(c, yaw)
    L, W, H = 8.6, 1.42, 2.75
    _box(g, "ru_car_white", P, yaw, 0, 0, .55, L, W, .25)                                   # the floor frame
    _box(g, "ru_car_white", P, yaw, 0, 0, .8 + H, L, W, .12)                                # the roof
    for s in (-1, 1):
        _box(g, "ru_car_blue", P, yaw, 0, s * (W - .03), 1.25, L, .03, .45)                 # below the windows
        _box(g, "ru_car_white", P, yaw, 0, s * (W - .03), .8 + H - .35, L, .03, .25)        # above them
        for k in range(8):
            x = -L + .3 + k * (2 * L - .6) / 7
            door = k in (2, 5)
            if not door:
                _box(g, "ru_car_white", P, yaw, x, s * (W - .03), 2.25, .12, .03, .58)
                if k < 7 and rnd.random() < .55 and k + 1 not in (2, 5):
                    _box(gd, "ru_glass", P, yaw, x + (2 * L - .6) / 14, s * (W - .03), 2.25, (2 * L - .6) / 14 - .12, .012, .5)
    for x in (-L, L):
        _box(g, "ru_car_blue", P, yaw, x, 0, 1.9, .05, W, 1.35)
    for sx in (-5.6, 5.6):
        _box(g, "ru_block_dark", P, yaw, sx, 0, .28, 1.2, 1.1, .2)
    for k in range(5):                                                                   # seats down both sides
        x = -6.5 + k * 3.2
        for s in (-1, 1):
            _box(g, "ru_car_blue", P, yaw, x, s * (W - .35), 1.02, .9, .22, .08)
    _box(gd, "ru_sign_amber" if rnd.random() < .5 else "ru_glass", P, yaw, 2.0, 0, .8 + H - .16, 1.2, .1, .02)
