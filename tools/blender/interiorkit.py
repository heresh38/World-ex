"""What the insides were fitted out with (Meridian Fall, stage 6 of the overhaul): shop fronts, ceilings, doors, and
the furniture of each trade, left the way it was left. Everything is laid out in a LOCAL frame (`Local`): for a shop the
origin is the middle of its front on the floor, +x runs into the shop, y along the front, z up.

Rules these pieces keep:
  * what stops a body or a bullet is ONE hidden box per piece of furniture (`solid`); everything drawn goes into the
    detail mesh. A shelf unit drawn board by board and collided board by board is a comb people get caught in.
  * no pane of whole glass stands where it can be shot at or seen through: collision is all-or-nothing, a creature
    could not see through a pane that the player can. Glazing in play is broken (shards in the frame) or gone.
  * a thing with rows of small things on it (a stocked shelf, a bookcase) is a block with a picture of the row on its
    front (`ru_goods`, `ru_books`: explicit UVs pick a window of one row); cloth picks its colour the same way from
    the four bands of `ru_fabric`.
  * signs are bars of light, never words.
"""
import math
import random
from mathutils import Vector, Matrix
import ruinkit as rk

TAU = 2 * math.pi
PI = math.pi
BOX = [(-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1), (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)]
BOX_F = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]


class Local:
    """a frame at o (E, N, z) turned yaw about up; tilt (3x3) lays what is built in it over (a fallen chair)"""

    def __init__(self, o, yaw=0.0, tilt=None):
        self.o = Vector(o)
        self.yaw = yaw
        self.tilt = tilt
        self.R = Matrix.Rotation(yaw, 3, 'Z') @ tilt if tilt else Matrix.Rotation(yaw, 3, 'Z')

    def P(self, x, y, z=0.0):
        return tuple(self.o + self.R @ Vector((x, y, z)))

    def D(self, x, y, z=0.0):
        return self.R @ Vector((x, y, z))

    def sub(self, x, y, z=0.0, ang=0.0, tilt=None):
        return Local(self.P(x, y, z), self.yaw + ang, tilt)

    def box(self, t, mat, x, y, z, hx, hy, hz, ang=0.0, **kw):
        if self.tilt:
            rk.box(t, mat, self.P(x, y, z), (hx, hy, hz), R=self.R @ Matrix.Rotation(ang, 3, 'Z'), **kw)
        else:
            rk.box(t, mat, self.P(x, y, z), (hx, hy, hz), self.yaw + ang, **kw)

    def uvbox(self, t, mat, x, y, z, hx, hy, hz, ang, uv, offsets=None):
        """a box whose every face shows the window uv = (u0, v0, u1, v1) of its texture"""
        R = self.R @ Matrix.Rotation(ang, 3, 'Z')
        c = Vector(self.P(x, y, z))
        vs = []
        for i, (sx, sy, sz) in enumerate(BOX):
            p = Vector((sx * hx, sy * hy, sz * hz))
            if offsets:
                p += Vector(offsets[i])
            vs.append(tuple(R @ p + c))
        u0, v0, u1, v1 = uv
        q = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
        t.add(vs, BOX_F, mat, uvs=[q] * 6)

    def cyl(self, t, mat, x, y, r, z0, z1, **kw):
        p = self.P(x, y, 0)
        rk.cyl(t, mat, (p[0], p[1]), r, p[2] + z0, p[2] + z1, **kw)

    def tube(self, t, mat, pts, r, sides=6, **kw):
        rk.tube(t, mat, [self.P(*p) for p in pts], r, sides, **kw)

    def quad(self, t, mat, pts, uv=None, facing=None, both=False):
        """one flat face through pts (local); facing: the local direction it is seen from"""
        vs = [self.P(*p) for p in pts]
        if facing is not None:
            n = (Vector(vs[1]) - Vector(vs[0])).cross(Vector(vs[2]) - Vector(vs[0]))
            if n.dot(self.D(*facing)) < 0:
                vs = vs[::-1]
                uv = uv[::-1] if uv else None
        idx = tuple(range(len(vs)))
        t.add(vs, [idx], mat, uvs=[uv] if uv else None)
        if both:
            t.add(vs, [idx[::-1]], mat, uvs=[uv[::-1]] if uv else None)


def solid(F, g, x, y, z, hx, hy, hz, ang=0.0, mat="ru_metal"):
    """what a piece of furniture stops: one box, collided with, never drawn"""
    vis, col = g.vis, g.col
    g.vis, g.col = False, True
    F.box(g, mat, x, y, z, hx, hy, hz, ang)
    g.vis, g.col = vis, col


def lathe(F, t, mat, x, y, prof, n=12):
    """a turned shape about the upright through (x, y): prof = [(radius, z)] from the bottom up"""
    c = F.P(x, y, 0)
    vs = [(c[0] + math.cos(TAU * i / n) * r, c[1] + math.sin(TAU * i / n) * r, c[2] + z) for (r, z) in prof for i in range(n)]
    faces = []
    for k in range(len(prof) - 1):
        for i in range(n):
            a, b = k * n + i, k * n + (i + 1) % n
            faces.append((a, b, b + n, a + n))
    t.add(vs, faces, mat, smooth=True)
    o = (len(prof) - 1) * n
    if prof[-1][0] > .012:
        t.add(vs[o:o + n], [tuple(range(n))], mat)


# ------------------------------------------------------------------ glass, signs
def shards(F, gd, y0, y1, z0, z1, rnd, x=0.0, amount=1.0):
    """what is left of a pane in its frame: teeth of glass standing from the sill, hanging from the head, along the
    sides"""
    w, h = y1 - y0, z1 - z0

    def tooth(a, b, tip):
        F.quad(gd, "ru_glass", [(x, a[0], a[1]), (x, b[0], b[1]), (x, tip[0], tip[1])], both=True)
    for _ in range(int(rnd.randint(2, 5) * amount)):                # from the sill
        a = y0 + rnd.random() * w * .85
        b = min(y1, a + rnd.uniform(.12, .5))
        tooth((a, z0), (b, z0), (rnd.uniform(a, b), z0 + rnd.uniform(.12, .65) * min(1.0, h)))
    for _ in range(int(rnd.randint(1, 4) * amount)):                # from the head
        a = y0 + rnd.random() * w * .85
        b = min(y1, a + rnd.uniform(.12, .45))
        tooth((a, z1), (b, z1), (rnd.uniform(a, b), z1 - rnd.uniform(.1, .5) * min(1.0, h)))
    for yy, s in ((y0, 1), (y1, -1)):                               # down the sides
        for _ in range(int(rnd.randint(0, 2) * amount)):
            a = z0 + rnd.random() * h * .8
            b = min(z1, a + rnd.uniform(.15, .5))
            tooth((yy, a), (yy, b), (yy + s * rnd.uniform(.08, .3), rnd.uniform(a, b)))


def crumbs(F, gd, x, y, r, n, rnd, z=.012):
    """broken glass on the floor"""
    for _ in range(n):
        a = rnd.uniform(0, TAU)
        d = r * math.sqrt(rnd.random())
        px, py, s, t = x + math.cos(a) * d, y + math.sin(a) * d, rnd.uniform(.03, .11), rnd.uniform(0, TAU)
        F.quad(gd, "ru_glass", [(px + math.cos(t + k * TAU / 3) * s * (1 if k else 1.6), py + math.sin(t + k * TAU / 3) * s, z) for k in range(3)],
               facing=(0, 0, 1))


def sign(F, gd, y0, y1, z, mat, rnd, x, hgt=.34, dead=.12):
    """a name in bars of light on a dark board: a mark, then strokes of different widths (never letters)"""
    F.box(gd, "ru_block_dark", x + .02, (y0 + y1) / 2, z, .03, (y1 - y0) / 2 + .18, hgt / 2 + .13)
    F.box(gd, mat if rnd.random() > dead else "ru_block_dark", x - .02, y0 + .2, z, .02, .2, hgt / 2)          # the mark
    y = y0 + .62
    while y < y1 - .2:
        w = rnd.uniform(.14, .5)
        if y + w > y1:
            break
        tall = rnd.random() < .65
        m = mat if rnd.random() > dead else "ru_block_dark"
        F.box(gd, m, x - .02, y + w / 2, z - (0 if tall else hgt * .2), .018, w / 2, hgt / 2 if tall else hgt * .3)
        y += w + rnd.uniform(.08, .16) + (rnd.uniform(.2, .4) if rnd.random() < .15 else 0)


# ------------------------------------------------------------------ the shop front
def shopfront(F, g, gd, top, kind, rnd, sign_mat, lit, wall_top):
    """A shop's front in its 8 m opening (y -4..4, floor..top). kind: 'open' (the glazed front, its doors parked open),
    'stuck' (the same with the shutter caught part-way down), 'shut' (the shutter down: nobody gets in),
    'forced' (the shutter down and one corner levered up: a way in on your knees), 'bare' (the frame only)."""
    for s in (-1, 1):                                                # the frame: jambs, the head, the shutter's guides
        F.box(g, "ru_brass", 0, s * 3.94, top / 2, .1, .06, top / 2)
        F.box(gd, "ru_metal", -.13, s * 3.9, top / 2, .03, .05, top / 2)
    F.box(g, "ru_brass", 0, 0, top - .06, .1, 4.0, .06)
    F.box(gd, "ru_metal", -.15, 0, top - .16, .13, 3.98, .15)        # the shutter's box
    # the name over it, and a blade sign standing out from the wall
    zs = top + min(.5, (wall_top - top) * .5)
    sign(F, gd, -3.3, 3.3, zs, sign_mat if lit else "ru_paint", rnd, -.26, dead=.12 if lit else 0.0)
    if rnd.random() < .6:
        s = rnd.choice((-1, 1))
        F.box(gd, "ru_metal", -.45, s * 4.35, top - .25, .25, .02, .02)
        F.box(gd, "ru_block_dark", -.62, s * 4.35, top - .62, .3, .04, .34)
        for f in (-1, 1):
            F.box(gd, sign_mat if lit and rnd.random() < .8 else "ru_paint", -.62, s * 4.35 + f * .045, top - .62, .22, .006, .26)
    if kind == "bare":
        return
    if kind in ("open", "stuck"):
        for s in (-1, 1):                                            # a side light each side on a low plinth
            F.box(g, "ru_composite", 0, s * 3.0, .2, .13, .94, .2)
            F.box(g, "ru_brass", 0, s * 2.03, top / 2, .06, .05, top / 2)
            F.box(gd, "ru_brass", 0, s * 3.0, 2.62, .05, .95, .04)
            if rnd.random() < .8:
                shards(F, gd, s * 3.0 - .9, s * 3.0 + .9, .4, 2.58, rnd, amount=rnd.uniform(.5, 1.3))
            crumbs(F, gd, rnd.uniform(-.5, .9), s * 3.0, 1.1, rnd.randint(5, 12), rnd)
            F.quad(gd, "ru_glass", [(0, s * 3.0 - .92, 2.66), (0, s * 3.0 + .92, 2.66), (0, s * 3.0 + .92, top - .13), (0, s * 3.0 - .92, top - .13)],
                   both=True)                                        # the light over the transom: out of reach, whole
        F.box(g, "ru_brass", 0, 0, 2.66, .07, 2.0, .05)              # the door head
        F.quad(gd, "ru_glass", [(0, -1.95, 2.72), (0, 1.95, 2.72), (0, 1.95, top - .13), (0, -1.95, top - .13)], both=True)
        for s in (-1, 1):                                            # the sliding leaves: parked open, or one on the floor
            if rnd.random() < .28:
                L = F.sub(rnd.uniform(1.0, 1.9), s * rnd.uniform(.9, 1.7), .03, rnd.uniform(-.6, .6), Matrix.Rotation(PI / 2, 3, 'Y'))
                leaf(L, gd, rnd, 0.0)
            else:
                leaf(F.sub(.16, s * 2.56, .02), gd, rnd, .7)
        if kind == "stuck":                                          # the shutter caught on its way down, one side lower
            low = rnd.uniform(2.05, 2.5)
            d = rnd.uniform(.15, .5) * rnd.choice((-1, 1))
            off = [(0, 0, max(0, d)), (0, 0, max(0, d)), (0, 0, max(0, -d)), (0, 0, max(0, -d)), (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0)]
            F.box(gd, "ru_shutter", -.13, 0, (low + top) / 2, .02, 3.86, (top - low) / 2, offsets=off)
        return
    # the shutter down
    if kind == "shut":
        F.box(g, "ru_shutter", -.13, 0, top / 2, .02, 3.86, top / 2)
        F.box(gd, "ru_metal", -.13, 0, .05, .035, 3.86, .05)
        F.box(gd, "ru_block_dark", -.16, rnd.uniform(-1, 1), .5, .012, .09, .07)          # the lock
        return
    s = rnd.choice((-1, 1))                                          # forced: the corner by one jamb levered up and out
    hole_w, hole_h = 2.3, 1.45
    F.box(g, "ru_shutter", -.13, -s * hole_w / 2, top / 2, .02, 3.86 - hole_w / 2, top / 2)
    F.box(g, "ru_shutter", -.13, s * (3.86 - hole_w / 2), (hole_h + top) / 2, .02, hole_w / 2, (top - hole_h) / 2)
    flap = [(0, 0, 0)] * 8
    out = -.75
    flap = [(out, 0, .25) if (sy * s > 0 and sz < 0) else ((out * .35, 0, .1) if sz < 0 else (0, 0, 0)) for (sx, sy, sz) in BOX]
    F.box(gd, "ru_shutter", -.13, s * (3.86 - hole_w / 2), hole_h * .72, .02, hole_w / 2, hole_h * .3, offsets=flap)
    F.tube(gd, "ru_metal", [(-.5, s * 2.2, .02), (-1.3, s * 2.9, .03)], .016, 5)        # the bar they used
    crumbs(F, gd, .6, s * 2.8, .9, 6, rnd)


def leaf(F, gd, rnd, glass):
    """a sliding door leaf standing at the frame's origin (1 m wide along y, 2.5 high): the frame, what glass it kept"""
    w, h = .5, 2.5
    for s in (-1, 1):
        F.box(gd, "ru_brass", 0, s * (w - .03), h / 2, .02, .03, h / 2)
    F.box(gd, "ru_brass", 0, 0, .05, .02, w, .05)
    F.box(gd, "ru_brass", 0, 0, h - .03, .02, w, .03)
    F.box(gd, "ru_brass", 0, 0, 1.05, .018, w - .05, .02)
    if rnd.random() < glass:
        shards(F, gd, -w + .06, w - .06, .1, 1.03, rnd, amount=.6)
        shards(F, gd, -w + .06, w - .06, 1.07, h - .06, rnd, amount=.7)


# ------------------------------------------------------------------ ceilings and what runs over them
def ceiling(F, gd, x0, x1, y0, y1, z, rnd, missing=.08, lit=.06, pitch=3):
    """A suspended ceiling at z over the rectangle: 1.2 m cells of four tiles, a light fitting every `pitch` cells,
    holes where tiles came down (one or two patches, and the odd one), tiles hanging and lying under the holes; a duct
    and a cable tray in the void over it, seen through the holes."""
    nx, ny = max(1, round((x1 - x0) / 1.2)), max(1, round((y1 - y0) / 1.2))
    cx, cy = (x1 - x0) / nx, (y1 - y0) / ny
    falls = [(rnd.uniform(x0, x1), rnd.uniform(y0, y1), rnd.uniform(1.2, 2.8)) for _ in range(rnd.randint(0, 2))]
    for i in range(nx):
        for j in range(ny):
            ax, ay = x0 + i * cx, y0 + j * cy
            mx, my = ax + cx / 2, ay + cy / 2
            gone = rnd.random() < missing or any(math.hypot(mx - fx, my - fy) < fr and rnd.random() < .8 for fx, fy, fr in falls)
            if gone:
                if rnd.random() < .3:                                # a tile hanging by one edge
                    d = rnd.uniform(.25, .55)
                    F.quad(gd, "ru_ceiling", [(ax, ay, z), (ax + .6, ay, z), (ax + .6, ay + .25, z - d), (ax, ay + .25, z - d)],
                           [(0, 0), (.25, 0), (.25, .25), (0, .25)], both=True)
                if rnd.random() < .45:                               # and one on the floor under the hole
                    F.box(gd, "ru_ceiling", mx + rnd.uniform(-.4, .4), my + rnd.uniform(-.4, .4), .02, .3, .3, .012, rnd.uniform(0, PI))
                continue
            u, v = rnd.randrange(2) * .5, rnd.randrange(2) * .5
            F.quad(gd, "ru_ceiling", [(ax, ay, z), (ax + cx, ay, z), (ax + cx, ay + cy, z), (ax, ay + cy, z)],
                   [(u, v), (u + .5, v), (u + .5, v + .5), (u, v + .5)], facing=(0, 0, -1))
            if i % pitch == 1 and j % pitch == 1:                    # a light fitting: 0.6 x 1.2, a few still burning
                m = "ru_lightpanel" if rnd.random() < lit else "ru_paint"
                F.quad(gd, m, [(mx - .28, ay + .02, z - .006), (mx + .28, ay + .02, z - .006), (mx + .28, ay + cy - .02, z - .006), (mx - .28, ay + cy - .02, z - .006)],
                       facing=(0, 0, -1))
    yd = y0 + (y1 - y0) * rnd.uniform(.25, .75)                      # the void over it
    F.box(gd, "ru_metal", (x0 + x1) / 2, yd, z + .34, (x1 - x0) / 2 - .1, .28, .17)
    F.box(gd, "ru_block_dark", (x0 + x1) / 2, yd + rnd.choice((-1.6, 1.6)), z + .16, (x1 - x0) / 2 - .1, .14, .02)


def services(F, gd, L, z, rnd, gap=None):
    """What hangs under a slab along a concourse (the frame's x runs along it, 0..L; z = the slab's underside; y = 0 is
    the middle of the strip): a supply duct with its flanges and hangers, a cable tray, a sprinkler main with its
    drops, strip lights. gap(x) -> True where nothing hangs (the rotunda's hole). A length of duct has come down at
    one end here and there; a light hangs by one cable."""
    def clear(a, b):
        return not gap or not (gap(a) or gap(b))
    x = 0.0
    k = 0
    while x < L - .1:                                                # the duct, in 2.4 m lengths
        x1 = min(L, x + 2.4)
        if clear(x, x1):
            if rnd.random() < .035:                                  # one end let go
                drop = rnd.uniform(.6, 1.5)
                off = [(0, 0, 0)] * 8
                off = [(0, 0, -drop) if sx > 0 else (0, 0, 0) for (sx, sy, sz) in BOX]
                F.box(gd, "ru_metal", (x + x1) / 2, 2.0, z - .36, (x1 - x) / 2 - .02, .45, .22, offsets=off)
            else:
                F.box(gd, "ru_metal", (x + x1) / 2, 2.0, z - .36, (x1 - x) / 2, .45, .22)
                F.box(gd, "ru_metal", x + .02, 2.0, z - .36, .025, .49, .26)                  # the flange
                if k % 2 == 0:
                    for s in (-1, 1):
                        F.tube(gd, "ru_metal", [(x + 1.2, 2.0 + s * .5, z), (x + 1.2, 2.0 + s * .5, z - .6)], .008, 4, cap=False)
                    F.box(gd, "ru_metal", x + 1.2, 2.0, z - .6, .02, .52, .012)
                if k % 5 == 2:                                       # a grille in its underside
                    F.box(gd, "ru_block_dark", x + 1.2, 2.0, z - .585, .45, .3, .006)
        x = x1
        k += 1
    x = 0.0
    while x < L - .1:                                                # the cable tray and what lies in it
        x1 = min(L, x + 3.0)
        if clear(x, x1):
            F.box(gd, "ru_metal", (x + x1) / 2, -2.4, z - .2, (x1 - x) / 2, .16, .008)
            for s in (-1, 1):
                F.box(gd, "ru_metal", (x + x1) / 2, -2.4 + s * .16, z - .17, (x1 - x) / 2, .006, .03)
            F.tube(gd, "ru_block_dark", [(x, -2.44, z - .17), (x1, -2.44, z - .17)], .022, 5, cap=False)
            F.tube(gd, "ru_block_dark", [(x, -2.34, z - .175), (x1, -2.34, z - .175)], .016, 5, cap=False)
            if rnd.random() < .07:                                   # a cable down out of it
                xa = rnd.uniform(x, x1)
                F.tube(gd, "ru_block_dark", [(xa, -2.36, z - .17), (xa + .2, -2.2, z - .9), (xa + .3, -2.25, z - rnd.uniform(1.4, 2.4))], .014, 5)
        x = x1
    x = 0.0
    while x < L - .1:                                                # the sprinkler main and its heads
        x1 = min(L, x + 3.6)
        if clear(x, x1):
            F.tube(gd, "ru_car_red", [(x, 4.6, z - .14), (x1, 4.6, z - .14)], .035, 6, cap=False)
            F.tube(gd, "ru_metal", [(x + 1.8, 4.6, z - .14), (x + 1.8, 4.6, z - .3)], .012, 4)
            F.cyl(gd, "ru_brass", x + 1.8, 4.6, .03, z - .33, z - .3, n=8)
        x = x1
    x = 4.0
    while x < L - 2:                                                 # strip lights between the duct and the tray
        if clear(x - 1, x + 1):
            m = "ru_lightpanel" if rnd.random() < .3 else "ru_paint"
            if rnd.random() < .12:                                   # hanging by one cable
                off = [(0, 0, -.7) if sx > 0 else (0, 0, 0) for (sx, sy, sz) in BOX]
                F.box(gd, "ru_metal", x, -.3, z - .1, .75, .09, .035, offsets=off)
                F.tube(gd, "ru_block_dark", [(x + .7, -.3, z), (x + .72, -.3, z - .75)], .006, 4)
            else:
                F.box(gd, "ru_metal", x, -.3, z - .05, .75, .09, .035)
                F.quad(gd, m, [(x - .72, -.37, z - .087), (x + .72, -.37, z - .087), (x + .72, -.23, z - .087), (x - .72, -.23, z - .087)], facing=(0, 0, -1))
        x += 9.0


# ------------------------------------------------------------------ furniture
def stock(F, gd, x0, x1, y, z, depth, facing, rnd, fill, tex="ru_goods", row_h=.3):
    """things standing on a shelf from x0 to x1, their fronts at y (seen from facing = -1 / +1 along y)"""
    x = x0
    while x < x1 - .15:
        w = min(rnd.uniform(.45, 1.3), x1 - x)
        if rnd.random() < fill:
            h = row_h * rnd.uniform(.74, .98)
            F.box(gd, "ru_block_dark", x + w / 2, y - facing * depth / 2, z + h / 2, w / 2 - .012, depth / 2, h / 2)
            row, u0 = rnd.randrange(4), rnd.random()
            vb = 1 - (row + 1) / 4 + .004
            u1, vt, yf = u0 + (w - .024) / 1.2, vb + h / 1.2, y + facing * .004
            F.quad(gd, tex, [(x + .012, yf, z), (x + w - .012, yf, z), (x + w - .012, yf, z + h), (x + .012, yf, z + h)],
                   [(u0, vb), (u1, vb), (u1, vt), (u0, vt)], facing=(0, facing, 0))
        x += w


def gondola(F, g, gd, L, rnd, fill=.6, H=1.5, tex="ru_goods"):
    """a two-sided shelf unit down the middle of a floor, along the frame's x"""
    solid(F, g, 0, 0, H / 2, L / 2, .42, H / 2)
    F.box(gd, "ru_metal", 0, 0, .07, L / 2, .42, .07)
    F.box(gd, "ru_paint", 0, 0, H / 2 + .07, L / 2, .02, H / 2 - .07)
    for e in (-1, 1):
        F.box(gd, "ru_metal", e * (L / 2 - .02), 0, H / 2, .02, .42, H / 2)
    F.box(gd, "ru_metal", 0, 0, H, L / 2, .05, .02)
    for k in range(int((H - .2) / .36)):
        z = .16 + k * .36
        for s in (-1, 1):
            F.box(gd, "ru_paint", 0, s * .22, z, L / 2 - .04, .2, .012)
            stock(F, gd, -L / 2 + .06, L / 2 - .06, s * .4, z + .012, .32, s, rnd, fill * (1.0 if k else .75), tex)


def wall_unit(F, g, gd, L, rnd, fill=.6, H=2.0, tex="ru_goods", mat="ru_wood"):
    """shelving against a wall: the wall is behind the frame's +y, the shelves face -y, along x"""
    solid(F, g, 0, -.2, H / 2, L / 2, .2, H / 2)
    F.box(gd, mat, 0, -.015, H / 2, L / 2, .015, H / 2)
    n = max(1, round(L / 1.2))
    for i in range(n + 1):
        F.box(gd, mat, -L / 2 + i * L / n, -.2, H / 2, .015, .2, H / 2)
    F.box(gd, mat, 0, -.2, H - .02, L / 2, .2, .02)
    F.box(gd, mat, 0, -.2, .05, L / 2, .2, .05)
    for k in range(int((H - .25) / .36)):
        z = .12 + k * .36
        F.box(gd, mat, 0, -.2, z, L / 2 - .02, .19, .012)
        for i in range(n):
            stock(F, gd, -L / 2 + i * L / n + .03, -L / 2 + (i + 1) * L / n - .03, -.37, z + .012, .3, -1, rnd, fill, tex)


def garment(F, gd, x, y, z_top, length, band, ang, rnd, w=.22):
    """something on a hanger: cloth narrower at the shoulders, its colour one band of the cloth texture"""
    off = [(0, 0, 0)] * 4 + [(0, -sy * w * .3, 0) for (sx, sy, sz) in BOX[4:]]
    u0 = band / 4 + .04
    v0 = rnd.random()
    F.uvbox(gd, "ru_fabric", x, y, z_top - length / 2, .014, w, length / 2, ang, (u0, v0, u0 + .17, v0 + length), offsets=off)


def rail(F, g, gd, L, rnd, fill=.7):
    """a clothes rail along the frame's x, what still hangs on it, what slid off"""
    solid(F, g, 0, 0, .8, L / 2, .24, .8)
    for e in (-1, 1):
        F.tube(gd, "ru_metal", [(e * L / 2, 0, .03), (e * L / 2, 0, 1.55)], .018, 6)
        F.box(gd, "ru_metal", e * L / 2, 0, .02, .03, .28, .02)
    F.tube(gd, "ru_metal", [(-L / 2, 0, 1.55), (L / 2, 0, 1.55)], .016, 6)
    x = -L / 2 + .12
    while x < L / 2 - .12:
        if rnd.random() < fill:
            garment(F, gd, x, 0, 1.52, rnd.uniform(.65, 1.05), rnd.randrange(4), rnd.uniform(-.12, .12), rnd)
        elif rnd.random() < .12:                                     # on the floor under it
            b = rnd.randrange(4)
            F.uvbox(gd, "ru_fabric", x, rnd.uniform(-.5, .5), .025, .3, .22, .02, rnd.uniform(0, PI), (b / 4 + .04, 0, b / 4 + .21, .6),
                    offsets=[(rnd.uniform(-.06, .06), rnd.uniform(-.06, .06), rnd.uniform(0, .03)) for _ in range(8)])
        x += rnd.uniform(.06, .11)


def round_rack(F, g, gd, rnd, fill=.7):
    solid(F, g, 0, 0, .7, .5, .5, .7)
    F.cyl(gd, "ru_metal", 0, 0, .3, 0, .03, n=14)
    F.cyl(gd, "ru_metal", 0, 0, .025, .03, 1.42, n=8)
    ring = [(math.cos(TAU * i / 16) * .5, math.sin(TAU * i / 16) * .5, 1.38) for i in range(17)]
    F.tube(gd, "ru_metal", ring, .014, 5, cap=False)
    for a in (0, PI / 2):
        F.tube(gd, "ru_metal", [(-math.cos(a) * .5, -math.sin(a) * .5, 1.38), (math.cos(a) * .5, math.sin(a) * .5, 1.38)], .012, 5, cap=False)
    n = 22
    for i in range(n):
        if rnd.random() < fill:
            a = TAU * i / n
            garment(F, gd, math.cos(a) * .5, math.sin(a) * .5, 1.35, rnd.uniform(.6, .95), rnd.randrange(4), a - PI / 2, rnd, w=.2)


def dress_form(F, gd, x, y):
    """a tailor's form on a stand in the window"""
    F.cyl(gd, "ru_metal", x, y, .2, 0, .025, n=12)
    F.cyl(gd, "ru_metal", x, y, .018, .025, .95, n=6)
    lathe(F, gd, "ru_paint", x, y, [(.02, .93), (.14, .95), (.155, 1.05), (.125, 1.2), (.15, 1.36), (.175, 1.46), (.16, 1.54), (.07, 1.6), (.05, 1.66), (.012, 1.67)], n=12)


def folded(F, gd, x, y, z, rnd):
    """a pile of folded things on a table"""
    for k in range(rnd.randint(2, 5)):
        b = rnd.randrange(4)
        F.uvbox(gd, "ru_fabric", x + rnd.uniform(-.01, .01), y + rnd.uniform(-.01, .01), z + .022 + k * .044, .17, .13, .022, rnd.uniform(-.08, .08),
                (b / 4 + .04, 0, b / 4 + .21, .3))


def table(F, g, gd, L, W, rnd, h=.75, mat="ru_wood"):
    solid(F, g, 0, 0, h / 2, L / 2, W / 2, h / 2)
    F.box(gd, mat, 0, 0, h - .02, L / 2, W / 2, .02)
    for sx in (-1, 1):
        for sy in (-1, 1):
            F.box(gd, "ru_metal", sx * (L / 2 - .06), sy * (W / 2 - .06), (h - .04) / 2, .02, .02, (h - .04) / 2)


def chair(F, gd, rnd, fallen=False):
    C = F.sub(0, 0, .22, 0, Matrix.Rotation(PI / 2, 3, 'X')) if fallen else F
    C.box(gd, "ru_wood", 0, 0, .45, .21, .21, .018)
    C.box(gd, "ru_wood", -.2, 0, .72, .014, .2, .18)
    for sx in (-1, 1):
        for sy in (-1, 1):
            C.box(gd, "ru_metal", sx * .18, sy * .18, .43 if sx < 0 else .22, .013, .013, .43 if sx < 0 else .22)


def stool(F, gd, x, y):
    F.cyl(gd, "ru_metal", x, y, .2, 0, .02, n=12)
    F.cyl(gd, "ru_metal", x, y, .022, .02, .7, n=6)
    F.cyl(gd, "ru_block_dark", x, y, .17, .7, .75, n=14)


def cafe_table(F, g, gd, x, y, rnd):
    solid(F, g, x, y, .37, .3, .3, .37)
    F.cyl(gd, "ru_metal", x, y, .25, 0, .025, n=14)
    F.cyl(gd, "ru_metal", x, y, .03, .025, .71, n=8)
    F.cyl(gd, "ru_wood", x, y, .4, .71, .74, n=20)
    for _ in range(rnd.randint(0, 2)):
        a = rnd.uniform(0, TAU)
        F.cyl(gd, "ru_paint", x + math.cos(a) * .18, y + math.sin(a) * .18, .038, .74, .83, n=8)


def counter(F, g, gd, L, rnd, till=True, case=False, mat="ru_wood"):
    """a counter along the frame's x; whoever is served stands on its -y side"""
    solid(F, g, 0, 0, .48, L / 2, .34, .48)
    F.box(gd, mat, 0, 0, .45, L / 2, .3, .45)
    F.box(gd, "ru_composite", 0, 0, .93, L / 2 + .03, .35, .03)
    F.box(gd, "ru_block_dark", 0, -.305, .05, L / 2, .008, .05)
    if case:                                                         # a display case on one half
        F.box(gd, "ru_glass", -L / 4, 0, 1.15, L / 4 - .06, .3, .19)
        F.box(gd, "ru_brass", -L / 4, 0, 1.35, L / 4 - .04, .32, .012)
    if till:
        x = L * .28
        F.box(gd, "ru_block_dark", x, .05, 1.0, .17, .15, .045)
        F.tube(gd, "ru_metal", [(x, .14, 1.04), (x, .16, 1.22)], .012, 5)
        F.box(gd, "ru_block_dark", x, .15, 1.3, .15, .012, .1, ang=0.0)


def screen(F, gd, x, y, z, w, h, ang, mat="ru_glass"):
    """a display hung at (x, y, z), facing the sub-frame's -y"""
    S = F.sub(x, y, z, ang)
    S.box(gd, "ru_block_dark", 0, 0, 0, w / 2, .02, h / 2)
    S.quad(gd, mat, [(-w / 2 + .03, -.023, -h / 2 + .03), (w / 2 - .03, -.023, -h / 2 + .03), (w / 2 - .03, -.023, h / 2 - .03), (-w / 2 + .03, -.023, h / 2 - .03)],
           facing=(0, -1, 0))


def fridge(F, g, gd, L, rnd, lit=False, fill=.5):
    """a run of glass-door coolers against a wall (the wall behind +y), along x"""
    H = 2.05
    solid(F, g, 0, -.35, H / 2, L / 2, .35, H / 2)
    F.box(gd, "ru_paint", 0, -.02, H / 2, L / 2, .02, H / 2)
    F.box(gd, "ru_block_dark", 0, -.35, H - .12, L / 2, .35, .12)
    F.box(gd, "ru_sign_white" if lit else "ru_paint", 0, -.705, H - .12, L / 2 - .06, .005, .06)
    F.box(gd, "ru_block_dark", 0, -.35, .1, L / 2, .35, .1)
    n = max(1, round(L / .75))
    w = L / n
    for i in range(n + 1):
        F.box(gd, "ru_paint" if i in (0, n) else "ru_metal", -L / 2 + i * w, -.35, H / 2, .02, .35, H / 2 - .12)
    for k in range(5):
        z = .24 + k * .33
        F.box(gd, "ru_paint", 0, -.3, z, L / 2 - .03, .26, .008)
        stock(F, gd, -L / 2 + .04, L / 2 - .04, -.5, z + .008, .28, -1, rnd, fill)
    for i in range(n):
        x0, x1 = -L / 2 + i * w + .03, -L / 2 + (i + 1) * w - .03
        if rnd.random() < .4:
            F.quad(gd, "ru_glass", [(x0, -.7, .22), (x1, -.7, .22), (x1, -.7, H - .26), (x0, -.7, H - .26)], facing=(0, -1, 0))
        else:
            S = F.sub((x0 + x1) / 2, -.7, 0, PI / 2)                  # (shards are laid out across a frame's y)
            shards(S, gd, -(x1 - x0) / 2, (x1 - x0) / 2, .22, H - .26, rnd, amount=.8)
        F.box(gd, "ru_metal", x1 - .05, -.715, 1.1, .012, .012, .2)   # the handle


def door(F, gd, w, h, rnd, state="shut", mat="ru_paint"):
    """a door in a wall: the wall's face is the frame's y = 0, the room on its -y side, the door across x"""
    for s in (-1, 1):
        F.box(gd, "ru_metal", s * (w / 2 + .04), -.02, h / 2, .04, .05, h / 2)
    F.box(gd, "ru_metal", 0, -.02, h + .04, w / 2 + .08, .05, .04)
    F.box(gd, "ru_block_dark", 0, -.004, h / 2, w / 2, .004, h / 2)   # the dark behind it
    a = 0.0 if state == "shut" else rnd.uniform(.25, 1.2)
    D = F.sub(-w / 2, -.04, 0, -a)
    D.box(gd, mat, w / 2, 0, h / 2, w / 2 - .005, .022, h / 2 - .005)
    D.box(gd, "ru_metal", w / 2, -.024, .16, w / 2 - .04, .003, .13)
    D.box(gd, "ru_metal", w - .1, -.05, 1.02, .012, .03, .07)
    D.quad(gd, "ru_glass", [(w - .32, -.0235, 1.3), (w - .16, -.0235, 1.3), (w - .16, -.0235, 1.75), (w - .32, -.0235, 1.75)], facing=(0, -1, 0))


def bedroll(F, gd, rnd):
    """where someone slept: a mat along the frame's x, a blanket thrown back, a pillow"""
    b = rnd.sample(range(4), 3)
    F.uvbox(gd, "ru_fabric", 0, 0, .035, .95, .36, .035, 0, (b[0] / 4 + .04, 0, b[0] / 4 + .21, 1.9))
    cr = [(rnd.uniform(-.05, .05), rnd.uniform(-.05, .05), rnd.uniform(0, .05)) for _ in range(8)]
    F.uvbox(gd, "ru_fabric", rnd.uniform(-.1, .35), rnd.uniform(-.08, .08), .1, .5, .34, .03, rnd.uniform(-.25, .25), (b[1] / 4 + .04, 0, b[1] / 4 + .21, 1.0), offsets=cr)
    F.uvbox(gd, "ru_fabric", -.72, 0, .11, .15, .22, .045, rnd.uniform(-.2, .2), (b[2] / 4 + .04, 0, b[2] / 4 + .21, .3))


def crate(F, g, gd, x, y, s, rnd, z=0.0):
    if z == 0.0:
        solid(F, g, x, y, s, s, s, s)
    a = rnd.uniform(-.3, .3)
    F.box(gd, "ru_wood", x, y, z + s, s, s, s, a)
    for e in (-1, 1):
        F.box(gd, "ru_metal", x, y, z + s + e * s * .6, s + .008, s + .008, .012, a)


def bin_(F, gd, x, y):
    lathe(F, gd, "ru_metal", x, y, [(.2, 0), (.24, .05), (.24, .78), (.21, .82), (.12, .86), (.012, .87)], n=14)
    F.cyl(gd, "ru_block_dark", x, y, .245, .5, .56, n=14)


def totem(F, g, gd, rnd, lit=True):
    """a directory: a slab with a plan of the place on both faces (across the frame's y)"""
    solid(F, g, 0, 0, 1.05, .09, .5, 1.05)
    F.box(gd, "ru_composite", 0, 0, 1.05, .08, .48, 1.05)
    F.box(gd, "ru_brass", 0, 0, 2.11, .09, .5, .02)
    for s in (-1, 1):
        m = "ru_sign_white" if lit and rnd.random() < .6 else "ru_glass"
        F.quad(gd, m, [(s * .083, -.4, .9), (s * .083, .4, .9), (s * .083, .4, 1.9), (s * .083, -.4, 1.9)], facing=(s, 0, 0))
        for k in range(5):                                           # the plan: blocks along a spine
            F.box(gd, "ru_block_dark", s * .086, -.3 + k * .15, 1.2 + (k % 2) * .28, .002, .05, .1)
        F.box(gd, "ru_block_dark", s * .086, 0, 1.4, .002, .34, .012)


# ------------------------------------------------------------------ a shop, by what it sold
SIGNS = dict(clothing=("ru_holo_magenta", "ru_sign_white"), electronics=("ru_holo_cyan",), cafe=("ru_sign_amber",), pharmacy=("ru_sign_green",),
             market=("ru_sign_red", "ru_sign_white"), books=("ru_sign_white", "ru_sign_amber"), shelter=("ru_sign_white",), stripped=("ru_holo_cyan", "ru_sign_amber"))
D, W = 13.7, 5.75                                                    # a shop's clear depth and half width
# Kept clear in every shop: the lane in from the door (|y| < 1.7 as far as x = 8.5) and the middle of the floor
# (2.2 m round (7, 0)): creatures are put down there and have to walk out.


def fit(F, g, gd, kind, rnd, lit=False):
    """a shop's inside; returns [(kind, local point, radius cm, intensity)] for lights it wants"""
    lights = []
    if kind in ("clothing", "books"):
        F.box(gd, "ru_carpet", D / 2 + .15, 0, .008, D / 2 - .1, W, .008)
    if kind == "clothing":
        for s in (-1, 1):
            rail(F.sub(5.0, s * (W - .45), 0), g, gd, 6.0, rnd, rnd.uniform(.45, .85))
            round_rack(F.sub(3.2, s * 3.3, 0), g, gd, rnd, rnd.uniform(.3, .8))
            round_rack(F.sub(6.5, s * 3.5, 0), g, gd, rnd, rnd.uniform(.3, .8))
            T = F.sub(10.0, s * 2.9, 0)
            table(T, g, gd, 1.8, .9, rnd)
            for k in range(4):
                if rnd.random() < .7:
                    folded(T, gd, -.6 + k * .4, rnd.uniform(-.15, .15), .75, rnd)
            dress_form(F, gd, .9, s * 3.0)
        counter(F.sub(11.9, 0, 0, PI / 2), g, gd, 3.0, rnd)
        for k in range(3):                                           # fitting rooms along the back: partitions, curtains
            y = -W + .1 + k * 1.3
            F.box(gd, "ru_wood", D - .6, y, 1.05, .6, .02, 1.05)
            if rnd.random() < .75:
                b = rnd.randrange(4)
                F.uvbox(gd, "ru_fabric", D - 1.2, y + .65, 1.1, .015, rnd.uniform(.3, .62), .95, 0, (b / 4 + .04, 0, b / 4 + .21, 1.9))
        F.box(gd, "ru_wood", D - .6, -W + .1 + 3 * 1.3, 1.05, .6, .02, 1.05)
        F.tube(gd, "ru_metal", [(D - 1.2, -W, 2.08), (D - 1.2, -W + 4.0, 2.08)], .012, 5)
        F.quad(gd, "ru_glass", [(D - .01, 1.6, .3), (D - .01, 4.4, .3), (D - .01, 4.4, 2.2), (D - .01, 1.6, 2.2)], facing=(-1, 0, 0))   # a mirror
    elif kind == "electronics":
        for r in range(2):                                           # the wall of screens: dark, a few cracked alive
            for k in range(5):
                m = "ru_holo_cyan" if lit and rnd.random() < .12 else "ru_glass"
                screen(F, gd, 2.4 + k * 1.45, W - .04, 1.25 + r * .85, 1.25, .72, PI, m)
        for k in range(3):
            T = F.sub(3.0 + k * 3.0, -3.3, 0)
            table(T, g, gd, 2.0, .9, rnd, h=.9, mat="ru_composite")
            for q in range(5):                                       # what was on show: most of it gone, the stands left
                T.box(gd, "ru_metal", -.8 + q * .4, 0, .93, .03, .03, .03)
                if rnd.random() < .35:
                    T.box(gd, "ru_block_dark", -.8 + q * .4, -.02, 1.0, .09, .006, .06, rnd.uniform(-.2, .2))
        wall_unit(F.sub(5.0, -W + .02, 0, PI), g, gd, 6.0, rnd, .2, 1.9, mat="ru_composite")
        counter(F.sub(11.6, 1.0, 0, PI / 2), g, gd, 3.6, rnd, case=True, mat="ru_composite")
        for k in range(rnd.randint(3, 6)):                           # cartons from the stock room, pulled out and gone through
            s = rnd.uniform(.2, .32)
            F.box(gd, "ru_sack", rnd.uniform(10.5, 13.0), rnd.uniform(-5.2, -2.6), s, s * 1.3, s, s, rnd.uniform(0, PI))
    elif kind == "cafe":
        counter(F.sub(10.8, 0, 0, PI / 2), g, gd, 6.4, rnd, case=True)
        B = F.sub(D - .05, 0, 0, -PI / 2)                            # the back run: a worktop and what stood on it
        solid(B, g, 0, -.3, .47, 3.6, .3, .47)
        B.box(gd, "ru_metal", 0, -.3, .45, 3.6, .3, .45)
        B.box(gd, "ru_composite", 0, -.3, .92, 3.62, .32, .02)
        for k in range(4):
            if rnd.random() < .75:
                B.box(gd, "ru_metal", -2.6 + k * 1.6, -.28, 1.2, .26, .22, .26)
                B.box(gd, "ru_block_dark", -2.6 + k * 1.6, -.51, 1.25, .16, .006, .1)
        for k in range(3):                                           # the boards over it: what they sold, in bars
            m = "ru_sign_amber" if lit and rnd.random() < .5 else "ru_block_dark"
            B.box(gd, "ru_block_dark", -2.2 + k * 2.2, -.04, 2.5, 1.0, .03, .45)
            for q in range(4):
                B.box(gd, m, -2.2 + k * 2.2 - .5 + rnd.uniform(0, .2), -.075, 2.75 - q * .17, rnd.uniform(.2, .45), .004, .03)
        for (x, y) in ((3.0, 3.7), (3.0, -3.7), (5.9, 4.0), (5.9, -4.0), (8.6, 3.3), (8.6, -3.3)):
            if rnd.random() < .12:
                continue
            cafe_table(F, g, gd, x, y, rnd)
            for q in range(rnd.randint(1, 3)):
                a = TAU * q / 3 + rnd.uniform(-.4, .4)
                fallen = rnd.random() < .3
                d = .78 if not fallen else rnd.uniform(.9, 1.3)
                chair(F.sub(x + math.cos(a) * d, y + math.sin(a) * d, 0, a + (0 if fallen else PI) + rnd.uniform(-.3, .3)), gd, rnd, fallen)
        F.box(gd, "ru_wood", .75, 3.6, 1.05, .2, 1.7, .025)           # a bar along the window, its stools
        for k in range(3):
            if rnd.random() < .8:
                stool(F, gd, 1.25, 2.4 + k * 1.05)
    elif kind in ("pharmacy", "market"):
        hi = kind == "market"
        fl = rnd.uniform(.35, .7) if hi else rnd.uniform(.15, .45)   # the chemist's was cleared out first
        for y in (-4.55, -2.9, 2.9, 4.55):
            gondola(F.sub(5.0, y, 0), g, gd, 6.0, rnd, fl, 1.6 if hi else 1.4)
        if hi:
            fridge(F.sub(D - .02, 0, 0, -PI / 2), g, gd, 9.0, rnd, lit and rnd.random() < .6, fl)
            counter(F.sub(1.9, -3.9, 0, 0), g, gd, 2.4, rnd)
            for k in range(rnd.randint(2, 5)):                       # baskets by the door
                F.box(gd, "ru_car_red", 1.0, 2.6 + rnd.uniform(-.05, .05), .1 + k * .07, .22, .15, .1, rnd.uniform(-.1, .1))
        else:
            counter(F.sub(10.4, 0, 0, PI / 2), g, gd, 8.0, rnd, case=True, mat="ru_paint")
            wall_unit(F.sub(D - .02, 0, 0, -PI / 2), g, gd, 9.0, rnd, fl * .6, 2.1, mat="ru_paint")
            F.box(gd, "ru_block_dark", 9.9, -2.0, 2.45, .02, .34, .34)                 # the cross, hung over the counter
            m = "ru_sign_green" if lit else "ru_paint"
            F.box(gd, m, 9.875, -2.0, 2.45, .006, .27, .09)
            F.box(gd, m, 9.875, -2.0, 2.45, .006, .09, .27)
    elif kind == "books":
        for s in (-1, 1):
            wall_unit(F.sub(5.4, s * (W - .02), 0, 0 if s > 0 else PI), g, gd, 8.4, rnd, rnd.uniform(.5, .9), 2.1, "ru_books")
            gondola(F.sub(4.8, s * 3.2, 0), g, gd, 4.8, rnd, rnd.uniform(.4, .8), 1.3, "ru_books")
        wall_unit(F.sub(D - .02, 0, 0, -PI / 2), g, gd, 8.4, rnd, rnd.uniform(.4, .8), 2.1, "ru_books")
        T = F.sub(10.6, 0, 0, PI / 2)
        table(T, g, gd, 2.4, 1.1, rnd)
        for k in range(rnd.randint(2, 6)):                           # books left open and in piles on the table
            T.uvbox(gd, "ru_books", rnd.uniform(-.9, .9), rnd.uniform(-.35, .35), .765 + rnd.random() * .02, .11, .08, .015 + rnd.random() * .03, rnd.uniform(0, PI),
                    (rnd.random(), .02, rnd.random() * .05 + .1, .2))
        for q in range(4):
            a = PI / 2 * q + PI / 4
            chair(F.sub(10.6 + math.cos(a) * 1.25, math.sin(a) * 1.4, 0, a + PI + rnd.uniform(-.3, .3)), gd, rnd, rnd.random() < .25)
        counter(F.sub(1.9, 3.9, 0, 0), g, gd, 2.2, rnd)
    elif kind == "shelter":                                          # a shop the shelter spread into: beds in rows, what they had
        for s in (-1, 1):
            for k in range(5):
                if rnd.random() < .85:
                    bedroll(F.sub(2.2 + k * 2.3, s * (W - 1.3), 0, PI / 2 * s + rnd.uniform(-.12, .12)), gd, rnd)
                if rnd.random() < .5:
                    F.box(gd, "ru_sack", 2.2 + k * 2.3 + .75, s * (W - .5), .14, .2, .14, .14, rnd.uniform(0, PI))
        for k in range(3):                                           # the shop's own shelving, pushed to the back wall and emptied
            wall_unit(F.sub(D - .02, -3.6 + k * 3.6, 0, -PI / 2), g, gd, 3.2, rnd, .05, 1.9)
        crate(F, g, gd, 10.6, -2.6, .34, rnd)
        crate(F, g, gd, 11.3, -2.3, .34, rnd)
        crate(F, g, gd, 10.9, -2.5, .26, rnd, z=.68)
        solid(F, g, 10.8, 2.8, .45, .3, .3, .45)
        lathe(F, gd, "ru_car_blue", 10.8, 2.8, [(.27, 0), (.29, .04), (.29, .86), (.27, .9), (.012, .9)], n=14)   # a water drum
        F.cyl(gd, "ru_sign_amber", 10.9, -2.5, .045, 1.2, 1.31, n=8)                    # a lamp left burning on a crate
        lights.append(("fire", (10.9, -2.5, 1.5), 500, None))
        F.tube(gd, "ru_metal", [(9.0, -W, 2.2), (9.0, W, 2.2)], .006, 4)                # a line across, sheets over it
        for k in range(3):
            if rnd.random() < .7:
                b = rnd.randrange(4)
                F.uvbox(gd, "ru_fabric", 9.0, -3.4 + k * 3.2, 1.45, .012, rnd.uniform(.7, 1.3), .75, 0, (b / 4 + .04, 0, b / 4 + .21, 1.5))
    else:                                                            # stripped: the fittings left, everything else carried off
        for s in (-1, 1):
            wall_unit(F.sub(5.0, s * (W - .02), 0, 0 if s > 0 else PI), g, gd, 7.2, rnd, .04, 2.0, mat="ru_paint")
        counter(F.sub(11.4, rnd.uniform(-1.5, 1.5), 0, PI / 2 + rnd.uniform(-.25, .25)), g, gd, 3.0, rnd, till=False)
        for k in range(rnd.randint(2, 4)):
            s = rnd.uniform(.18, .3)
            F.box(gd, "ru_sack", rnd.uniform(9.5, 13.0), rnd.choice((-1, 1)) * rnd.uniform(2.4, 5.0), s, s * 1.3, s, s, rnd.uniform(0, PI))
    door(F.sub(D + .29, rnd.choice((-1, 1)) * 4.4, 0, PI / 2 + PI), gd, .95, 2.1, rnd, "shut" if rnd.random() < .7 else "ajar")
    return lights
