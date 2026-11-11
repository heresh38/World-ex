"""What stops the player, made of things (the owner, 2026-11-11: "instead of invisible barrier ... use the buildings
walls as the barrier ... rubble or maybe something else collapsed blocking the other side ... be creative and don't
just use invisible walls").

The route's edge is a row of buildings a player can walk into (citykit.building(front=...): open to the street, blind
and whole on its other sides) and, in every gap between two of them, one of these:

  containers   freight boxes stacked three and four high across a street (the Verge: the roads out were closed with
               them in the last days)
  twall        prefabricated wall sections with wire along the top (the quarantine round the Stacks, the army's line)
  collapse     floors that slid into an alley and stand on edge in their own rubble
  growth       a palisade the Altered grew: tall ribs of chitin with a membrane between them (where the hive holds
               the ground)

Every one stands over 7.7 m: a double jump and a clamber reach about six. None has a ledge to stand on below that.
`NET` collects where an unseen wall still runs: BEHIND each of these and behind the buildings' backs, never where
anybody walks. It is a net under a climber, not the boundary; the level reports any touch of it.
"""
import math
import random
from mathutils import Vector, Matrix
import ruinkit as rk

TAU = 2 * math.pi
PI = math.pi
NET = []                                                             # [((E, N), (E, N))]: segments of the unseen net
PLUGS = []                                                           # [(kind, (E, N), (E, N))]: every barrier built (for the plan drawing)
CRATES = ("ru_corrugate", "ru_box_red", "ru_box_green", "ru_box_ochre")


def _frame(a, b, out):
    a, b = Vector((a[0], a[1], 0)), Vector((b[0], b[1], 0))
    t = (b - a)
    L = t.length
    t /= L
    o = Vector((out[0], out[1], 0)).normalized()
    return a, b, t, o, L, math.atan2(t.y, t.x)


def net(a, b, out, back=2.0):
    a, b, t, o, L, yaw = _frame(a, b, out)
    NET.append(((a + o * back - t * 1.0).to_2d().to_tuple(), (b + o * back + t * 1.0).to_2d().to_tuple()))


def container(g, gd, c, yaw, length, mat, rnd, doors=True):
    """a freight box, its foot's middle at c: corrugated sides between a steel frame, doors with their lock rods at
    one end"""
    W, Hh = 2.44, 2.59
    R = Matrix.Rotation(yaw, 3, 'Z')
    c = Vector(c)

    def P(x, y, z):
        return tuple(c + R @ Vector((x, y, z)))

    def bx(t, m, x, y, z, hx, hy, hz):
        rk.box(t, m, P(x, y, z), (hx, hy, hz), yaw)
    bx(g, mat, 0, 0, Hh / 2, length / 2 - .04, W / 2 - .04, Hh / 2 - .06)
    for sx in (-1, 1):                                               # corner posts, top and bottom rails
        for sy in (-1, 1):
            bx(gd, "ru_metal", sx * (length / 2 - .07), sy * (W / 2 - .07), Hh / 2, .07, .07, Hh / 2)
    for sy in (-1, 1):
        for z in (.08, Hh - .08):
            bx(gd, "ru_metal", 0, sy * (W / 2 - .05), z, length / 2, .05, .08)
    for sx in (-1, 1):
        for z in (.08, Hh - .08):
            bx(gd, "ru_metal", sx * (length / 2 - .05), 0, z, .05, W / 2, .08)
    if doors:                                                        # the doors: two leaves, four rods, their handles
        x = length / 2 + .005
        for sy in (-1, 1):
            bx(gd, "ru_metal", x, sy * W / 4, Hh / 2, .012, W / 4 - .04, Hh / 2 - .18)
            for q in (.28, .78):
                yy = sy * W / 2 * q
                rk.tube(gd, "ru_block_dark", [P(x + .03, yy, .2), P(x + .03, yy, Hh - .2)], .017, 5)
                bx(gd, "ru_block_dark", x + .04, yy + .08, 1.15, .012, .1, .02)
    if rnd.random() < .5:                                            # a number plate of bars, never words
        for k in range(rnd.randint(3, 6)):
            bx(gd, "ru_paint", -length / 2 + .5 + k * .16, W / 2 - .03, Hh - .5, .05, .006, .09)


def containers(g, gd, a, b, out, seed, tall=None, z=0.0, loose=True):
    """a street closed with freight boxes: one box long, three or four high, the upper ones a hand off true"""
    PLUGS.append(("containers", (a[0], a[1]), (b[0], b[1])))
    rnd = random.Random(seed)
    a, b, t, o, L, yaw = _frame(a, b, out)
    n = 1 if L + 1.6 <= 12.19 else math.ceil((L + 1.6) / 12.19)
    length = 12.19 if (L + 1.6) / n > 6.06 else 6.06
    m = (a + b) / 2 + o * 1.25
    for k in range(n):
        along = (k - (n - 1) / 2) * (length + .06)
        levels = tall or rnd.choice((3, 4, 4))
        for lv in range(levels):
            j = t * (along + rnd.uniform(-.035, .035)) + o * rnd.uniform(-.035, .035)
            p = m + j + Vector((0, 0, z + lv * 2.59))
            container(g, gd, p, yaw + rnd.uniform(-.006, .006) + (PI if rnd.random() < .5 else 0), length, rnd.choice(CRATES), rnd, doors=lv < 2)
    # what was left at its foot: a pallet jack's worth of loose things, tyre marks are the road's own
    for k in range(rnd.randint(2, 4) if loose else 0):
        p = m - o * rnd.uniform(1.6, 2.6) + t * rnd.uniform(-L / 2, L / 2)
        s = rnd.uniform(.25, .4)
        rk.box(g, "ru_wood", (p.x, p.y, z + s), (s * 1.2, s, s), yaw + rnd.uniform(-.5, .5))
    net(a, b, out, 3.6)


def twall(g, gd, a, b, out, seed, height=8.2, wire=True):
    """prefabricated wall sections stood shoulder to shoulder: a splayed foot each, lifting eyes, a band of paint at
    head height with hazard bars, wire along the top"""
    PLUGS.append(("twall", (a[0], a[1]), (b[0], b[1])))
    rnd = random.Random(seed)
    a, b, t, o, L, yaw = _frame(a, b, out)
    a, L = a - t * .5, L + 1.0
    n = max(1, round(L / 2.0))
    w = L / n
    for k in range(n):
        m = a + t * ((k + .5) * w) + o * (1.0 + rnd.uniform(-.02, .02))
        hh = height + rnd.uniform(-.04, .04)
        rk.box(g, "ru_concrete", (m.x, m.y, hh / 2), (w / 2 - .015, .2, hh / 2), yaw + rnd.uniform(-.004, .004))
        rk.box(g, "ru_concrete", (m.x, m.y, .2), (w / 2 - .015, .75, .2), yaw)                       # the foot
        f = m - o * .21
        rk.box(gd, "ru_paint", (f.x, f.y, 1.9), (w / 2 - .05, .006, .28), yaw)
        if k % 3 == 1:
            for q in range(4):
                e = f + t * ((q - 1.5) * .22) - o * .004
                rk.box(gd, "ru_block_dark", (e.x, e.y, 1.9), (.05, .006, .24), yaw, offsets=[(.1 if sz > 0 else -.1, 0, 0) for (sx, sy, sz) in (
                    (-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1), (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1))])
        for s in (-1, 1):                                            # lifting eyes
            e = f + t * (s * w * .28)
            rk.tube(gd, "ru_metal", [(e.x, e.y, hh - .9), tuple(Vector((e.x, e.y, hh - .78)) - o * .09), (e.x, e.y, hh - .66)], .014, 4)
    if wire:                                                         # a coil of wire along the top on its brackets
        pts = []
        turns = int(L / .45)
        for i in range(turns * 8 + 1):
            u = i / 8
            p = a + t * (u * .45) + o * (1.0 + math.cos(u * TAU) * .32)
            pts.append((p.x, p.y, height + .42 + math.sin(u * TAU) * .32))
        rk.tube(gd, "ru_metal", pts, .008, 3, cap=False)
        for k in range(n + 1):
            p = a + t * (k * w) + o * 1.0
            rk.tube(gd, "ru_metal", [(p.x, p.y, height - .1), (p.x, p.y, height + .3), tuple(Vector((p.x, p.y, height + .75)) - o * .3)], .02, 4)
    net(a + t * .5, b, out, 2.4)


def collapse(g, gd, a, b, out, seed, height=10.6):
    """an alley filled by the floors that slid into it: slabs standing on edge and leaning on one another, their bars
    out of the broken ends, in a bank of their own rubble"""
    PLUGS.append(("collapse", (a[0], a[1]), (b[0], b[1])))
    rnd = random.Random(seed)
    a, b, t, o, L, yaw = _frame(a, b, out)
    m = (a + b) / 2
    along_n = abs(t.y) > abs(t.x)
    c = m + o * 1.8
    rk.heap(g, (c.x, c.y, 0), 3.2 if along_n else L / 2 + 1.6, 1.6, seed * 3 + 1, chunks=12, res=.4, ry=L / 2 + 1.6 if along_n else 3.2)
    k = 0
    for i in range(rnd.randint(4, 6)):
        hh = height * rnd.uniform(.92, 1.12) if i < 3 else height * rnd.uniform(.55, .8)       # the back ones stand full height
        lean = rnd.uniform(.08, .4) * rnd.choice((-1, 1))
        roll = rnd.uniform(-.1, .1)
        p = m + o * (1.0 + i * .55 + rnd.uniform(-.1, .1)) + t * rnd.uniform(-.25, .25)
        R = Matrix.Rotation(yaw, 3, 'Z') @ Matrix.Rotation(lean, 3, 'X') @ Matrix.Rotation(roll, 3, 'Y')
        ctr = Vector((p.x, p.y, 0)) + R @ Vector((0, 0, hh / 2 - .5))
        ragged = [(rnd.uniform(-.25, .25), 0, rnd.uniform(-.5, .3) if sz > 0 else 0) for (sx, sy, sz) in (
            (-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1), (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1))]
        rk.box(g, "ru_concrete", tuple(ctr), (L / 2 + .3, .17, hh / 2), R=R, top_mat="ru_fracture", offsets=ragged)
        for q in range(rnd.randint(3, 7)):                           # bars out of its top edge
            s = ctr + R @ Vector((rnd.uniform(-L / 2, L / 2), rnd.uniform(-.1, .1), hh / 2 - .2))
            rk.tube(gd, "ru_metal", [tuple(s), tuple(s + R @ Vector((rnd.uniform(-.3, .3), rnd.uniform(-.3, .3), rnd.uniform(.4, 1.3))))], .014, 4, cap=False)
        k += 1
    for i in range(2):                                               # two that fell flat on the bank, in front
        p = m - o * rnd.uniform(.2, 1.6) + t * rnd.uniform(-L / 4, L / 4)
        R = Matrix.Rotation(yaw + rnd.uniform(-.5, .5), 3, 'Z') @ Matrix.Rotation(rnd.uniform(1.1, 1.35) * rnd.choice((-1, 1)), 3, 'X')
        rk.box(g, "ru_concrete", (p.x, p.y, rnd.uniform(.5, 1.0)), (rnd.uniform(1.2, 2.0), .16, rnd.uniform(.9, 1.5)), R=R, top_mat="ru_fracture")
    net(a, b, out, 5.4)


def growth(g, gd, a, b, out, seed, height=9.6, own_net=True):
    """a palisade the Altered grew across a street: ribs of chitin as thick as a man, bowed toward whoever comes, a
    membrane stretched between them, light in its veins"""
    PLUGS.append(("growth", (a[0], a[1]), (b[0], b[1])))
    rnd = random.Random(seed)
    a, b, t, o, L, yaw = _frame(a, b, out)
    a, L = a - t * .8, L + 1.6
    n = max(2, round(L / 1.5))
    cols = []
    for k in range(n + 1):
        base = a + t * (k * L / n) + o * (1.0 + rnd.uniform(-.2, .2))
        hh = height * rnd.uniform(.9, 1.2)
        bow = rnd.uniform(.5, 1.1)
        pts = [base + Vector((0, 0, hh * q / 7)) - o * (bow * math.sin(q / 7 * PI) * (1 - .25 * q / 7)) + t * (.12 * math.sin(q * 1.3 + k)) for q in range(8)]
        rk.tube(g, "ru_hive", [tuple(p) for p in pts], rnd.uniform(.36, .5), 8, r_end=.05)
        cols.append(pts)
        if rnd.random() < .6:                                        # a vein of light up it
            rk.tube(gd, "ru_glow", [tuple(p - o * .42 * (1 - q / 9)) for q, p in enumerate(pts[:6])], .025, 4, cap=False)
    for k in range(n):                                               # the membrane between each pair, to seven tenths of their height
        A, B = cols[k], cols[k + 1]
        vs, faces = [], []
        rows, across = 7, 4
        for r in range(rows + 1):
            pa, pb = A[min(r, 7)], B[min(r, 7)]
            for q in range(across + 1):
                u = q / across
                p = pa.lerp(pb, u) + o * (.22 * math.sin(u * PI)) + Vector((0, 0, -.25 * math.sin(u * PI) * (r / rows)))
                vs.append(tuple(p))
        for r in range(rows):
            for q in range(across):
                i0 = r * (across + 1) + q
                faces += [(i0, i0 + 1, i0 + across + 2, i0 + across + 1), (i0 + across + 1, i0 + across + 2, i0 + 1, i0)]
        g.add(vs, faces, "ru_hive", smooth=True)
    for k in range(rnd.randint(1, 3)):
        p = a + t * rnd.uniform(1, L - 1) - o * rnd.uniform(.2, 1.0)
        rk.pod(g, gd, (p.x, p.y, 0), rnd.uniform(.6, 1.0), seed * 5 + k)
    if own_net:                                                  # (not where the net behind it would stand on walked ground)
        net(a + t * .8, b, out, 3.0)


def palisade(g, gd, a, b, out, seed, height=8.2):
    """a security fence of steel pales, too high and too sharp to climb, that is seen through (what it keeps people
    out of is still part of the view)"""
    PLUGS.append(("palisade", (a[0], a[1]), (b[0], b[1])))
    rnd = random.Random(seed)
    a, b, t, o, L, yaw = _frame(a, b, out)
    m = (a + b) / 2
    vis, col = g.vis, g.col                                          # what it stops: one sheet, never drawn
    g.vis, g.col = False, True
    rk.box(g, "ru_metal", (m.x, m.y, height / 2), (L / 2, .05, height / 2), yaw)
    g.vis, g.col = vis, col
    n = max(1, round(L / 2.75))
    for k in range(n + 1):
        p = a + t * (k * L / n)
        rk.box(gd, "ru_metal", (p.x, p.y, height / 2 + .1), (.06, .06, height / 2 + .1), yaw)
    for z in (.35, height * .5, height - .5):
        rk.box(gd, "ru_metal", (m.x, m.y, z), (L / 2, .025, .035), yaw)
    k = 0
    x = .12
    while x < L - .1:
        p = a + t * x - o * .04
        lean = rnd.uniform(-.25, .25) if rnd.random() < .03 else 0.0  # one bent here and there
        hh = height - (.0 if k % 2 else .08)
        rk.box(gd, "ru_metal", (p.x, p.y, hh / 2 + .1), (.028, .008, hh / 2), yaw,
               offsets=[(0, 0, 0)] * 4 + [(lean - .02 * sx, 0, .1 if sx < 0 else -.02) for (sx, sy) in ((-1, -1), (1, -1), (1, 1), (-1, 1))])
        x += .16
        k += 1
    net(a, b, out, 2.0)


KINDS = dict(containers=containers, twall=twall, collapse=collapse, growth=growth, palisade=palisade)


def seal(g, gd, a, b, out, kind, seed):
    """close the gap from a to b (E, N), `out` pointing away from the route"""
    KINDS[kind](g, gd, a, b, out, seed)


def run(g, gd, pts, kind, seed, outside, **kw):
    """a barrier along a polyline [(E, N)]; `outside` is any point beyond it (which side is out)"""
    for k, (a, b) in enumerate(zip(pts, pts[1:])):
        d = Vector((b[0] - a[0], b[1] - a[1]))
        nrm = Vector((-d.y, d.x)).normalized()
        m = Vector(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2))
        if nrm.dot(Vector(outside) - m) < 0:
            nrm = -nrm
        KINDS[kind](g, gd, a, b, (nrm.x, nrm.y), seed + k, **kw)
