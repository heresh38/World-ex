"""Meridian, the long way in: everything south of the old approach (tools/operation/meridian_plan.py has the numbers).

  verge     Ashfall Verge: the landing pad at the city's edge, the dead highway, the fallen flyover, the toll plaza
  stacks    The Stacks: the gatehouse block (rooms you fight through), the walled yard, the archway, the alley
  galleria  Meridian Galleria: forecourt, two storeys of shops round a long atrium, the rotunda under the fallen
            skylight, the food court and the service gate, the loading yard behind
  deepline  Deepline: the stair down, the ticket hall, the island platform and its track beds, the tunnel with its
            collapse and the service corridor round it
  sluice    The Sluice: the drained canal, its pump house and footbridges, the spillway up the east bank
  causeway  the road from the spillway up to the old approach

meridian.py calls zones(G, H): G = {zone: (structure Geo, detail Geo)}, H = its helpers (light, fire, void_growth,
jersey, hedgehog, lamp_post, ground_slab, ambience). Everything is built from ruinkit pieces: closed, thick solids
(what is drawn is what collides).
"""
import math
import random
from mathutils import Vector, Matrix
import ruinkit as rk
import meridian_plan as P

TAU = rk.TAU
PI = math.pi


# ------------------------------------------------------------------ pieces
def growth(g, gd, c, r, seed, wall=None):
    rk.hive_growth(g, gd, c, r, seed, wall, res=.19)


def wall(g, mat, a, b, z0, z1, thick=.35, openings=(), top_mat=None):
    """A straight wall from a to b (E, N), z0..z1. openings: (from, to, top) or (from, to, sill, top), metres along
    the wall and above z0: a doorway (to the floor) or a window (above a sill), with the wall carried over it."""
    a, b = Vector((a[0], a[1])), Vector((b[0], b[1]))
    d = b - a
    L = d.length
    u = d / L
    yaw = math.atan2(u.y, u.x)

    def piece(s0, s1, za, zb):
        if s1 - s0 < .03 or zb - za < .03:
            return
        m = a + u * ((s0 + s1) / 2)
        rk.box(g, mat, (m.x, m.y, (za + zb) / 2), ((s1 - s0) / 2, thick / 2, (zb - za) / 2), yaw, top_mat=top_mat)
    s = 0.0
    for o in sorted(openings):
        o0, o1 = max(o[0], 0.0), min(o[1], L)
        sill, top = (0.0, o[2]) if len(o) == 3 else (o[2], o[3])
        piece(s, o0, z0, z1)
        piece(o0, o1, z0, z0 + sill)
        piece(o0, o1, z0 + top, z1)
        s = o1
    piece(s, L, z0, z1)


def block(g, mat, e0, e1, n0, n1, z0, z1, top_mat=None):
    rk.box(g, mat, ((e0 + e1) / 2, (n0 + n1) / 2, (z0 + z1) / 2), (abs(e1 - e0) / 2, abs(n1 - n0) / 2, (z1 - z0) / 2), top_mat=top_mat)


def slab(g, mat, e0, e1, n0, n1, z, thick, cell=3.0, keep=None, edge="ru_fracture", under=None):
    """a floor slab (top at z) as a grid of cells; keep(e, n) drops cells (holes, voids): the broken edges get `edge`"""
    ne, nn = max(1, round((e1 - e0) / cell)), max(1, round((n1 - n0) / cell))
    ce, cn = (e1 - e0) / ne, (n1 - n0) / nn
    on = [[keep is None or keep(e0 + (i + .5) * ce, n0 + (j + .5) * cn) for j in range(nn)] for i in range(ne)]
    vs, faces, mats = [], [], []
    for i in range(ne):
        for j in range(nn):
            if not on[i][j]:
                continue
            x0, x1, y0, y1 = e0 + i * ce, e0 + (i + 1) * ce, n0 + j * cn, n0 + (j + 1) * cn
            o = len(vs)
            vs += [(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z), (x0, y0, z - thick), (x1, y0, z - thick), (x1, y1, z - thick), (x0, y1, z - thick)]
            faces.append((o, o + 1, o + 2, o + 3)); mats.append(mat)
            faces.append((o + 4, o + 7, o + 6, o + 5)); mats.append(under or mat)
            for (di, dj), f in (((0, -1), (o, o + 4, o + 5, o + 1)), ((1, 0), (o + 1, o + 5, o + 6, o + 2)),
                                ((0, 1), (o + 2, o + 6, o + 7, o + 3)), ((-1, 0), (o + 3, o + 7, o + 4, o))):
                a, b = i + di, j + dj
                inside = 0 <= a < ne and 0 <= b < nn
                if inside and on[a][b]:
                    continue
                faces.append(f); mats.append(edge if inside else (under or mat))
    g.add(vs, faces, mats)


def sloped(g, mat, p0, p1, half_w, thick, lift=0.0):
    """a plank from p0 to p1 (E, N, z of its top surface's middle line), half_w wide each side"""
    a, b = Vector(p0), Vector(p1)
    d = b - a
    L = d.length
    x = d / L
    side = Vector((-x.y, x.x, 0.0)).normalized()
    up = x.cross(side)
    if up.z < 0:
        up = -up
    R = Matrix((x, side, up)).transposed()
    c = (a + b) / 2 - up * (thick / 2) + Vector((0, 0, lift))
    rk.box(g, mat, tuple(c), (L / 2, half_w, thick / 2), R=R)


def escalator(g, gd, e, n_foot, n_top, z1, width=4.0):
    """a dead escalator: a ridged metal ramp between two balustrades"""
    rk.path_deck(g, "ru_metal", "ru_metal", [(e, n_foot, 0.02), (e, n_top, z1)], width, .5)
    for s in (-1, 1):
        x = e + s * (width / 2 + .12)
        sloped(g, "ru_panel", (x, n_foot, 1.0), (x, n_top, z1 + 1.0), .1, 1.0)
        rk.tube(g, "ru_metal", [(x, n_foot, 1.05), (x, n_top, z1 + 1.05)], .07, 6)
    L = abs(n_top - n_foot)
    k = int(L / .4)
    for i in range(1, k):                                         # the treads
        t = i / k
        rk.box(gd, "ru_metal", (e, n_foot + (n_top - n_foot) * t, z1 * t + .035), (width / 2 - .05, .03, .02))


def table(g, c, r=.55, h=.74):
    rk.cyl(g, "ru_metal", (c[0], c[1]), .07, c[2], c[2] + h - .04, n=6, smooth=False)
    rk.cyl(g, "ru_panel", (c[0], c[1]), r, c[2] + h - .04, c[2] + h, n=14, smooth=False)


def ruin_rows(g, gd, rnd, n0, n1, e_in, seed, low=(2, 5), high=(6, 12), near=(14, 18)):
    """low ruins down both sides of a straight street (N n0..n1, their inner faces e_in from the middle), taller behind"""
    for side in (-1, 1):
        n = n0
        k = 0
        while n < n1 - 8:
            L = rnd.uniform(16, 26)
            w = rnd.uniform(*near)
            rk.tower(g, gd, (side * (e_in + w / 2 + rnd.uniform(0, 3)), n + L / 2), w, L, rnd.randint(*low), yaw=rnd.uniform(-.04, .04),
                     seed=seed + k * 2 + (side > 0), style=rnd.choice(("panel", "concrete")), top=(.3, 1.0), holes=2, col_top=7.0)
            # (behind the first row and the invisible wall: seen, never touched)
            rk.tower(g, gd, (side * (e_in + w + 14 + rnd.uniform(0, 10)), n + L / 2), rnd.uniform(16, 22), L, rnd.randint(*high),
                     yaw=rnd.uniform(-.1, .1), seed=seed + 500 + k * 2 + (side > 0), style=rnd.choice(("panel", "concrete")),
                     top=(.4, 1.0), holes=2, rebar=False, detail=False, heaps=False, cell_target=6.0, col_top=0)
            n += L + rnd.uniform(3, 6)
            k += 1


# ------------------------------------------------------------------ Ashfall Verge
def zone_verge(G, H):
    g, gd = G["verge"]
    V = P.VERGE
    n0, n1, half, road = V["n0"], V["n1"], V["half"], V["road"]
    rnd = random.Random(1101)
    H.ground_slab(g, "ru_asphalt", -road, road, n0 - 4, n1 + 2, .03)
    # the landing pad: a round apron with its lights still on
    pe, pn = V["pad"]
    rk.cyl(g, "ru_stone", (pe, pn), 9.0, 0.0, .12, n=48, smooth=False)
    rk.annulus(g, "ru_metal", (pe, pn), 9.0, 9.5, 0.0, .16, n=48)
    for i in range(12):
        a = TAU * i / 12
        rk.box(gd, "ru_glow", (pe + math.cos(a) * 8.2, pn + math.sin(a) * 8.2, .14), (.45, .09, .03), a + PI / 2)
    H.light("rim", (pe, pn, 1.0), 1700)
    for s in (-1, 1):                                             # two beacon masts
        rk.tube(g, "ru_metal", [(pe + s * 11.5, pn - 2, 0), (pe + s * 11.5, pn - 2, 6.5)], .14, 8, r_end=.09)
        rk.box(gd, "ru_glow", (pe + s * 11.5, pn - 2, 6.6), (.16, .16, .22))
        H.light("rim", (pe + s * 11.5, pn - 2, 6.0), 900)
    ruin_rows(g, gd, rnd, n0 - 14, n1 - 4, half + 8, 1200)
    for side in (-1, 1):
        for i in range(9):
            rk.heap(g, (side * (half - rnd.uniform(1, 5)), rnd.uniform(n0 + 30, n1 - 10), 0), rnd.uniform(4, 8), rnd.uniform(1.5, 3.5),
                    1300 + i + (side > 0) * 20, ry=rnd.uniform(5, 9))
    # the flyover: the old ring road crossing overhead, one span down on the road (a ramp of broken deck to fight round)
    a, b = Vector((-90.0, -2262.0, 9.5)), Vector((90.0, -2214.0, 9.5))
    d = (b - a).normalized()
    cut0, cut1 = .45, .62
    for t0, t1 in ((0.0, cut0), (cut1, 1.0)):
        p0, p1 = a.lerp(b, t0), a.lerp(b, t1)
        rk.path_deck(g, "ru_asphalt", "ru_concrete", [tuple(p0), tuple(p1)], 13.0, 1.5, end_mat="ru_fracture")
        for s in (-1, 1):
            off = Vector((-d.y, d.x, 0)) * s * 6.3
            rk.wall_path(g, "ru_concrete", [tuple(p0 + off), tuple(p1 + off)], .35, 1.0, rnd=rnd, broken=.4)
    top = a.lerp(b, cut1) - d * .5
    foot = a.lerp(b, cut0 + .03) + Vector((0, 0, -9.5 + .75))
    rk.path_deck(g, "ru_asphalt", "ru_concrete", [tuple(foot), tuple(top - Vector((0, 0, .7)))], 12.0, 1.3, end_mat="ru_fracture")
    for t in (.1, .27, .82, .96):
        p = a.lerp(b, t)
        rk.box(g, "ru_concrete", (p.x, p.y, 4.0), (1.3, 2.8, 4.0), math.atan2(d.y, d.x))
        rk.box(g, "ru_concrete", (p.x, p.y, 8.4), (1.7, 6.8, .5), math.atan2(d.y, d.x))
    for t in (cut0, cut1):
        p = a.lerp(b, t)
        for k in range(16):
            o = Vector((-d.y, d.x, 0)) * rnd.uniform(-6, 6)
            s = p + o + Vector((0, 0, -rnd.uniform(.2, 1.3)))
            dirn = d * (1 if t == cut0 else -1)
            L = rnd.uniform(.6, 2.2)
            rk.tube(gd, "ru_metal", [tuple(s), tuple(s + dirn * L * .6 - Vector((0, 0, L * .2))), tuple(s + dirn * L - Vector((0, 0, L * .6)))], .02, 5, cap=False)
    # a sign gantry over the road, its east leg buckled and the beam down on that side
    gn = -2176.0
    rk.tube(g, "ru_metal", [(-11.5, gn, 0), (-11.5, gn, 7.6)], .26, 8)
    rk.tube(g, "ru_metal", [(11.5, gn, 0), (11.9, gn + .4, 2.2), (12.6, gn + 1.4, 3.1)], .26, 8)
    for dz in (0.0, 1.1):
        rk.tube(g, "ru_metal", [(-11.5, gn, 7.4 - dz), (0, gn + .5, 5.6 - dz), (11.6, gn + 1.3, 2.7 - dz * .6)], .12, 6)
    for k in range(9):
        t = k / 8
        e = -11.5 + 23.1 * t
        z = 7.4 - 4.7 * t ** 1.3
        rk.tube(gd, "ru_metal", [(e, gn + .5 * t, z), (e + 1.2, gn + .5 * t, z - 1.1 + .25 * t)], .05, 5)
    rk.box(g, "ru_panel", (-5.5, gn + .25, 6.0), (4.2, .08, 1.3), R=Matrix.Rotation(-.16, 3, 'Y'))      # the blank sign
    # the toll plaza: a canopy on columns (its east end down), six booths on their islands
    tn = V["toll_n"]
    block(g, "ru_concrete", -28.0, 9.0, tn - 6.5, tn + 6.5, 5.6, 6.05, top_mat="ru_asphalt")
    sloped(g, "ru_concrete", (9.5, tn, 5.9), (27.0, tn + 1.5, 1.2), 6.3, .45)
    for e in (-25.0, -17.0, -9.0, -1.0, 7.0):
        for dn in (-4.6, 4.6):
            block(g, "ru_concrete", e - .3, e + .3, tn + dn - .3, tn + dn + .3, 0.0, 5.6)
    rk.box(g, "ru_concrete", (16.0, tn + 4.6, 1.4), (.3, .3, 1.4), top_mat="ru_fracture")
    for i, e in enumerate((-21.0, -13.0, -5.0, 3.0, 11.0, 19.0)):
        block(g, "ru_concrete", e - 1.4, e + 1.4, tn - 6.0, tn + 6.0, 0.0, .22)
        block(g, "ru_panel", e - 1.05, e + 1.05, tn - 2.4, tn + 2.4, .22, 1.25)
        for de in (-1.0, 1.0):                                    # corner posts and the roof: a booth you can see through
            for dn in (-2.35, 2.35):
                block(g, "ru_metal", e + de - .06, e + de + .06, tn + dn - .06, tn + dn + .06, 1.25, 2.7)
        block(g, "ru_panel", e - 1.2, e + 1.2, tn - 2.6, tn + 2.6, 2.7, 2.86)
        if i % 3 != 1:
            rk.box(gd, "ru_glass", (e, tn - 2.36, 1.95), (.95, .015, .68))
        rk.tube(gd, "ru_metal", [(e + 1.2, tn - 3.2, 1.0), (e + 1.2 + (3.6 if i % 2 else 1.4), tn - 3.2, 1.0 + (0 if i % 2 else 2.6))], .05, 6)
        rk.box(gd, "ru_glow" if i % 2 else "ru_metal", (e, tn - 6.5, 5.3), (.5, .06, .22))
    for i, (e, n, y) in enumerate(((-17, tn - 16, .2), (-9, tn - 19, -.1), (-1, tn - 15, .1), (7, tn - 20, .3), (15, tn - 17, -.2),
                                   (-6, tn + 16, 1.4), (9, tn + 22, 1.6), (-14, tn + 34, .1), (4, tn + 46, -.2), (-5, -2040, 1.5),
                                   (12, -2030, .2), (-12, -2022, -.2))):
        H.jersey(g, (e, n, 0), y, 3.2)
    for i, (e, n) in enumerate(((-22, tn - 30), (20, tn - 34), (-3, tn - 44), (22, -2052), (-21, -2044))):
        H.hedgehog(g, (e, n, 0), 1400 + i)
    for i, (e, n) in enumerate(((-9.8, -2280), (9.8, -2246), (-9.8, -2200), (9.8, -2150), (-9.8, -2084), (9.8, -2050), (-9.8, -2018))):
        H.lamp_post(g, gd, (e, n, 0), 0.0 if e < 0 else PI, 1410 + i, broken=i % 2 == 1)
    H.fire(gd, (-6.0, tn - 9.0, 0.0), 1420)
    H.fire(gd, (14.0, -2064.0, 0.0), 1421)
    rk.chunks(gd, (0, -2240), 16, 50, 1422)
    rk.chunks(gd, (0, tn + 10), 20, 70, 1423)
    H.void_growth(gd, (-24, -2190, 0), 2.8, 1424)
    H.void_growth(gd, (25, -2096, 0), 3.0, 1425)
    # the Altered's forward picket: grown barricades behind the booths, a spire, the first growth
    for i, (e, n, yaw) in enumerate(((-17, tn + 9, PI), (-1, tn + 11, PI), (15, tn + 9, PI), (-9, -2064, PI + .1), (8, -2046, PI - .1))):
        rk.alien_barricade(g, (e, n, 0), yaw, 1430 + i)
    rk.alien_spire(g, gd, (-22.0, -2078.0, 0), 11.0, 1440)
    H.ambience("hum", (-22.0, -2078.0, 0), 30, 1.0)
    H.light("void", (-22.0, -2078.0, 10.0), 1600)
    growth(g, gd, (27.0, -2030.0, 0), 4.0, 1441, (-1, 0))
    H.ambience("hive", (27.0, -2030.0, 0), 14, .8, spores=True)
    H.light("void", (27.0, -2030.0, 0), 1100)
    for n in (-2150, -2090, -2030):
        rk.cable(gd, (-30, n, 10), (30, n + 6, 12), 2.5)


# ------------------------------------------------------------------ The Stacks
def zone_stacks(G, H):
    g, gd = G["stacks"]
    S = P.STACKS
    half = S["half"]
    B, Y, A, AL = S["block"], S["yard"], S["arch"], S["alley"]
    rnd = random.Random(1501)
    # the street up to the estate, closed in by ruins
    H.ground_slab(g, "ru_asphalt", -9.0, 9.0, S["n0"] - 2, B["n0"], .03)
    H.ground_slab(g, "ru_stone", -half, half, B["n0"] - 14, B["n0"], .08)
    ruin_rows(g, gd, rnd, S["n0"] - 6, B["n0"] - 14, 31.0, 1600, low=(3, 6))
    for s in (-1, 1):
        wall(g, "ru_concrete", (s * half, B["n0"] - 14), (s * 31.0, B["n0"] - 14), 0, 5.0, .5, top_mat="ru_fracture")
        wall(g, "ru_concrete", (s * half, B["n0"] - 14), (s * half, B["n0"]), 0, 5.0, .5, top_mat="ru_fracture")
    # ---- the gatehouse block: the ground storey is rooms (walls a man is not seen through, doors, windows to fire from)
    b0, b1, H1 = B["n0"], B["n1"], 4.5
    lob = B["lobby"]
    block(g, "ru_stone", -half, half, b0, b1, -.1, .06)
    win = lambda xs: [(x - 1.5, x + 1.5, 1.1, 2.9) for x in xs]
    # south face: the lobby's doors in the middle, windows down both wings
    wall(g, "ru_concrete", (-half, b0), (half, b0), 0, H1, .5, [(half - 4.0, half + 4.0, 3.6)] + win([8, 17, 26, 35, half + 12, half + 21, half + 30, half + 39]))
    # north face onto the yard: a wide door from the lobby, a door from each wing
    wall(g, "ru_concrete", (-half, b1), (half, b1), 0, H1, .5, [(half - 3.0, half + 3.0, 3.4), (half - 31.5, half - 28.5, 2.8), (half + 28.5, half + 31.5, 2.8)]
         + win([7, 23, 33, half + 13, half + 23, half + 39]))
    for s in (-1, 1):
        wall(g, "ru_concrete", (s * half, b0), (s * half, b1), 0, H1, .5)
        # the lobby's side walls, a door into each wing front and back
        wall(g, "ru_panel", (s * lob, b0), (s * lob, b1), 0, H1, .3, [(8.0, 10.6, 2.8), (28.0, 30.6, 2.8)])
        # the wings: two cross walls with doors, and a wall along the middle of the outer rooms
        wall(g, "ru_panel", (s * 21.0, b0), (s * 21.0, b1), 0, H1, .3, [(4.0, 6.4, 2.8), (24.0, 26.4, 2.8)] if s < 0 else [(13.0, 15.4, 2.8), (31.0, 33.4, 2.8)])
        wall(g, "ru_panel", (s * 34.0, b0), (s * 34.0, b1), 0, H1, .3, [(16.0, 18.4, 2.8)] if s < 0 else [(6.0, 8.4, 2.8), (27.0, 29.4, 2.8)])
        wall(g, "ru_panel", (s * 21.0, b0 + 20), (s * half, b0 + 20), 0, H1, .3, [(4.0, 6.4, 2.8), (17.0, 19.4, 2.8)])
    # the ceiling: whole but for where the upper floors came through it (a shaft of moonlight in the lobby, one wing open)
    holes = ((-5.0, 5.0, b0 + 14, b0 + 26), (23.0, 33.0, b0 + 22, b0 + 36), (-44.0, -36.0, b0 + 4, b0 + 14))

    def ceiling(e, n):
        return not any(x0 < e < x1 and y0 < n < y1 for x0, x1, y0, y1 in holes)
    slab(g, "ru_concrete", -half, half, b0, b1, H1 + .34, .34, 2.0, ceiling)
    rk.heap(g, (0.0, b0 + 20, 0), 4.2, 1.5, 1510, ry=5.0)
    rk.heap(g, (28.0, b0 + 29, 0), 4.5, 2.0, 1511, ry=6.0)
    rk.heap(g, (-40.0, b0 + 9, 0), 3.4, 1.4, 1512)
    H.light("moon", (0.0, b0 + 20, 3.4), 1500)
    # what is left in the rooms: the porter's desk, lockers, overturned tables (cover at every door)
    block(g, "ru_panel", -2.8, 2.8, b0 + 30, b0 + 31, 0, 1.1)
    for i, (e, n, yaw) in enumerate(((-14, b0 + 8, 0), (-14, b0 + 30, 0), (14, b0 + 12, 0), (15, b0 + 32, 0), (-27, b0 + 12, PI / 2),
                                     (-27, b0 + 30, PI / 2), (27, b0 + 10, PI / 2), (-40, b0 + 28, 0), (40, b0 + 9, 0), (40, b0 + 31, 0))):
        if i % 2:
            rk.box(g, "ru_metal", (e, n, 1.0), (.3, 1.4, 1.0), yaw)                       # lockers
        else:
            rk.box(g, "ru_panel", (e, n, .55), (1.0, .06, .55), yaw + rnd.uniform(-.3, .3))  # a table on its side
    for i, (e, n) in enumerate(((-30, b0 + 4), (30, b0 + 36), (10, b0 + 4), (-12, b0 + 36))):
        rk.chunks(gd, (e, n), 4, 14, 1520 + i)
    H.fire(gd, (-14.0, b0 + 19, 0.0), 1525)
    for e, n in ((33.0, b0 + 8), (-28.0, b0 + 34), (27.0, b0 + 26), (-40.0, b0 + 12), (14.0, b0 + 30), (-14.0, b0 + 8)):
        H.light("lamp", (e, n, 3.6), 1000)
    for e in (-7.0, 7.0):                                             # over the doors, outside
        H.light("lamp", (e, b0 - 1.6, 3.9), 1300)
    # the floors above: a ruin standing on the ceiling
    rk.tower(g, gd, (0.0, (b0 + b1) / 2), 2 * half, b1 - b0, 7, yaw=0.0, seed=1530, style="concrete", top=(.3, 1.0), holes=4,
             base_z=H1 + .34, heaps=False, col_top=5.0)
    # ---- the yard: paving, the estate's two long blocks down its sides, a dead fountain, low walls and planters
    y0, y1 = Y["n0"], Y["n1"]
    H.ground_slab(g, "ru_stone", -half, half, y0, y1, .06)
    for s in (-1, 1):
        wall(g, "ru_concrete", (s * half, y0), (s * half, y1), 0, 5.2, .5, win([10, 22, 34, 46, 58, 70, 82, 94]))
        rk.tower(g, gd, (s * (half + 10.5), (y0 + y1) / 2), 20, y1 - y0, 10, yaw=0.0, seed=1540 + (s > 0), style="panel", top=(.45, 1.0),
                 holes=3, base_z=0.0, col_top=10.0, heaps=False)
    yc = (0.0, (y0 + y1) / 2)
    rk.annulus(g, "ru_stone", yc, 5.0, 5.7, 0.0, .7, n=40)
    rk.cyl(g, "ru_concrete", yc, 5.0, 0.0, .12, n=40, smooth=False)
    rk.cyl(g, "ru_stone", yc, 1.1, 0.0, 1.9, n=12, r1=.8, smooth=False)
    rk.tube(g, "ru_metal", [(yc[0], yc[1], 1.9), (yc[0] + .4, yc[1] + .2, 3.1), (yc[0] + 1.4, yc[1] + .5, 3.5)], .1, 6, r_end=.04)
    for i, (e, n, w, d_) in enumerate(((-26, y0 + 22, 7, .5), (26, y0 + 26, 7, .5), (-18, y0 + 52, .5, 6), (20, y0 + 56, .5, 6),
                                       (-30, y0 + 74, 8, .5), (30, y0 + 78, 8, .5), (0, y0 + 14, 6, .5), (-8, y0 + 82, .5, 5), (9, y0 + 84, .5, 5))):
        block(g, "ru_concrete", e - w / 2, e + w / 2, n - d_ / 2, n + d_ / 2, 0, 1.05 if i % 3 else .6, top_mat="ru_stone")
    for i, (e, n) in enumerate(((-36, y0 + 40), (36, y0 + 44), (-12, y0 + 30), (13, y0 + 68))):
        block(g, "ru_concrete", e - 2.2, e + 2.2, n - .9, n + .9, 0, .85, top_mat="ru_rubble")
        rk.tube(g, "ru_metal", [(e, n, .85), (e + .2, n + .1, 2.6), (e - .3, n + .3, 3.8)], .09, 6, r_end=.03)
    sloped(g, "ru_concrete", (-41.0, y0 + 60, 3.2), (-30.0, y0 + 62, .35), 3.0, .34)        # a slab off the west block, leant on the ground
    sloped(g, "ru_concrete", (38.0, y0 + 18, .34), (30.0, y0 + 16, .34), 2.6, .34)
    for i, (e, n) in enumerate(((-41, y0 + 8), (41, y0 + 92), (-40, y0 + 94), (40, y0 + 6))):
        rk.heap(g, (e, n, 0), rnd.uniform(3.5, 5), rnd.uniform(1.4, 2.6), 1550 + i)
    for i in range(4):                                            # washing lines nobody took in
        n = y0 + 18 + i * 22
        rk.cable(gd, (-half + .5, n, 7.5), (half - .5, n + 3, 8.0), 1.6)
        rk.banner(gd, (rnd.uniform(-25, 25), n + 1.5, 6.4), 1.6, 2.2, 0.0, 1560 + i)
    for i, (e, n, yaw) in enumerate(((-22, y0 + 36, PI), (0, y0 + 40, PI), (22, y0 + 38, PI), (-12, y0 + 66, PI), (14, y0 + 70, PI), (0, y0 + 88, PI))):
        rk.alien_barricade(g, (e, n, 0), yaw, 1570 + i)
    rk.alien_spire(g, gd, (33.0, y0 + 64, 0), 12.0, 1580)
    H.ambience("hum", (33.0, y0 + 64, 0), 30, 1.0)
    H.light("void", (33.0, y0 + 64, 11.0), 1700)
    growth(g, gd, (-half + .6, y0 + 46, 0), 4.5, 1581, (1, 0))
    H.ambience("hive", (-half + 1, y0 + 46, 0), 14, .8, spores=True)
    H.light("void", (-half + 2, y0 + 46, 1.0), 1200)
    H.fire(gd, (10.0, y0 + 24, 0.0), 1582)
    H.fire(gd, (-24.0, y0 + 80, 0.0), 1583)
    rk.chunks(gd, yc, 40, 90, 1584)
    H.void_growth(gd, (-3.0, y0 + 50, 1.9), 2.2, 1585)
    # ---- the north block and the archway under it
    a0, a1, ah, AH = A["n0"], A["n1"], A["half"], 5.0
    for s in (-1, 1):
        wall(g, "ru_concrete", (s * ah, a0), (s * ah, a1), 0, AH, .6)
        wall(g, "ru_concrete", (s * ah, a0), (s * half, a0), 0, AH, .5, win([8, 18, 28, 38]))
        wall(g, "ru_concrete", (s * ah, a1), (s * half, a1), 0, AH, .5)
        wall(g, "ru_concrete", (s * half, a0), (s * half, a1), 0, AH, .5)
    slab(g, "ru_concrete", -half, half, a0, a1, AH + .34, .34, 3.0)
    H.ground_slab(g, "ru_asphalt", -ah, ah, a0, a1, .05)
    rk.tower(g, gd, (0.0, (a0 + a1) / 2), 2 * half, a1 - a0, 9, yaw=0.0, seed=1590, style="panel", top=(.4, 1.0), holes=3, base_z=AH + .34, heaps=False,
             col_top=4.6)
    for k in range(3):                                            # the passage's ribs and its one working lamp
        n = a0 + 5 + k * 10
        block(g, "ru_concrete", -ah, ah, n - .3, n + .3, AH - .5, AH)
    H.light("lamp", (0.0, (a0 + a1) / 2, 4.0), 1000)
    # ---- the alley between the tenements: closets off it, lines of washing, a slab fallen across overhead
    l0, l1, lh = AL["n0"], AL["n1"], AL["half"]
    H.ground_slab(g, "ru_asphalt", -lh, lh, l0, l1 + 2, .04)
    doors = {-1: (18.0, 52.0, 96.0, 128.0), 1: (34.0, 74.0, 112.0)}
    for s in (-1, 1):
        wall(g, "ru_concrete", (s * (lh + .25), l0), (s * (lh + .25), l1), 0, 4.6, .5,
             [(d0, d0 + 3.0, 2.9) for d0 in doors[s]] + win([x for x in (8, 28, 44, 64, 86, 104, 122, 140) if all(abs(x - d0 - 1.5) > 4 for d0 in doors[s])]))
        for d0 in doors[s]:                                       # a closet behind each door: three walls and a ceiling
            n = l0 + d0
            wall(g, "ru_panel", (s * (lh + 5.0), n - 1.5), (s * (lh + 5.0), n + 4.5), 0, 3.4, .3)
            wall(g, "ru_panel", (s * (lh + .5), n - 1.5), (s * (lh + 5.0), n - 1.5), 0, 3.4, .3)
            wall(g, "ru_panel", (s * (lh + .5), n + 4.5), (s * (lh + 5.0), n + 4.5), 0, 3.4, .3)
            block(g, "ru_concrete", min(s * (lh + .5), s * (lh + 5.15)), max(s * (lh + .5), s * (lh + 5.15)), n - 1.65, n + 4.65, 3.4, 3.7)
        n = l0 + 2
        i = 0
        while n < l1 - 10:
            L = rnd.uniform(20, 30)
            rk.tower(g, gd, (s * (lh + .5 + 9.5), n + L / 2), 19, L, rnd.randint(7, 12), yaw=0.0, seed=1700 + i * 2 + (s > 0),
                     style="panel" if (i + (s > 0)) % 2 else "concrete", top=(.45, 1.0), holes=3, base_z=4.6, heaps=False, col_top=4.2)
            n += L + 2
            i += 1
        wall(g, "ru_concrete", (s * (lh + .25), l1), (s * P.GALLERIA["half"], l1), 0, 5.0, .5)     # out onto the forecourt
    sloped(g, "ru_concrete", (-lh - .3, l0 + 60, 7.4), (lh + .3, l0 + 63, 5.6), 3.2, .4)
    for i in range(6):
        n = l0 + 12 + i * 24
        rk.cable(gd, (-lh, n, 6.2 + (i % 2)), (lh, n + 2, 6.8), 1.2)
        if i % 2 == 0:
            rk.banner(gd, (rnd.uniform(-5, 5), n + 1, 5.6), 1.4, 2.0, 0.0, 1720 + i)
    for i, (e, n, y) in enumerate(((-5, l0 + 26, .2), (4, l0 + 44, -.2), (-4, l0 + 82, 1.4), (5, l0 + 106, .1), (-5, l0 + 132, -.1))):
        H.jersey(g, (e, n, 0), y, 3.0)
    for i, (e, n) in enumerate(((6.5, l0 + 16), (-6.5, l0 + 70), (6.0, l0 + 122))):
        rk.heap(g, (e, n, 0), 3.0, 1.6, 1730 + i, ry=4.0)
    for i, (e, n, yaw) in enumerate(((-3, l0 + 54, PI), (3, l0 + 92, PI), (0, l0 + 140, PI))):
        rk.alien_barricade(g, (e, n, 0), yaw, 1740 + i)
    for dn in (24.0, 76.0, 128.0):
        H.light("lamp", (0.0, l0 + dn, 5.4), 1300)
    H.fire(gd, (-6.0, l0 + 38, 0.0), 1745)
    H.fire(gd, (6.0, l0 + 100, 0.0), 1746)
    growth(g, gd, (lh - .2, l0 + 78, 0), 3.2, 1747, (-1, 0))
    H.ambience("hive", (lh - 1, l0 + 78, 0), 12, .7, spores=True)
    H.light("void", (lh - 1.5, l0 + 78, 1.0), 1000)
    rk.chunks(gd, (0, (l0 + l1) / 2), 9, 60, 1748)


# ------------------------------------------------------------------ Meridian Galleria
def zone_galleria(G, H):
    g, gd = G["galleria"]
    M = P.GALLERIA
    n0, n1, half, conc, void, z1, roof, bay = M["n0"], M["n1"], M["half"], M["conc"], M["void"], M["z1"], M["roof"], M["bay"]
    rot = (0.0, M["rot_n"])
    rr = M["rot_r"]
    rnd = random.Random(2101)
    nb = int(round((n1 - n0) / bay))
    # ---- the forecourt: paving, the entrance canopy, planters
    f0 = M["fore_n0"]
    H.ground_slab(g, "ru_stone", -half, half, f0, n0, .06)
    for s in (-1, 1):
        wall(g, "ru_concrete", (s * (half + .3), f0), (s * (half + .3), n0), 0, 5.0, .6)
    block(g, "ru_concrete", -24.0, 24.0, n0 - 11.0, n0 - .3, 5.4, 5.8, top_mat="ru_metal")
    for e in (-21.0, -7.0, 7.0, 21.0):
        block(g, "ru_metal", e - .25, e + .25, n0 - 10.4, n0 - 9.9, 0, 5.4)
    for i, e in enumerate((-18.0, -10.0, -2.0, 6.0, 14.0)):           # what is left of the name over the doors: bars of light
        if i != 3:
            rk.box(gd, "ru_glow", (e + 2, n0 - 11.05, 6.5), (2.6, .06, .5))
    H.light("lamp", (0.0, n0 - 8.0, 4.6), 1500)
    for i, (e, n) in enumerate(((-26, f0 + 12), (26, f0 + 14), (-12, f0 + 22), (12, f0 + 20), (0, f0 + 9))):
        block(g, "ru_concrete", e - 2.6, e + 2.6, n - 1.0, n + 1.0, 0, .9, top_mat="ru_rubble")
    for i, (e, n, yaw) in enumerate(((-9, f0 + 30, PI), (9, f0 + 31, PI))):
        rk.alien_barricade(g, (e, n, 0), yaw, 2110 + i)
    rk.heap(g, (-30.0, n0 - 5, 0), 4.0, 2.0, 2112)
    rk.heap(g, (31.0, f0 + 5, 0), 3.5, 1.6, 2113)
    H.fire(gd, (20.0, f0 + 27, 0.0), 2114)
    # ---- the shell: floor, outer walls, the doors in the south wall, the service gate in the north one
    block(g, "ru_stone", -half, half, n0, n1, -.1, .05)
    for s in (-1, 1):
        wall(g, "ru_concrete", (s * (half + .3), n0), (s * (half + .3), n1), 0, roof, .6)
    wall(g, "ru_concrete", (-half - .6, n0), (half + .6, n0), 0, roof, .6, [(half + .6 + e - 3.0, half + .6 + e + 3.0, 4.0) for e in M["doors"]])
    gh = M["gate_half"]
    wall(g, "ru_concrete", (-half - .6, n1), (half + .6, n1), 0, roof, .6, [(half + .6 - gh, half + .6 + gh, 4.6)])
    for s in (-1, 1):                                                 # the gate's frame
        block(g, "ru_metal", s * gh - .35, s * gh + .35, n1 - .7, n1 + .7, 0, 4.9)
    block(g, "ru_metal", -gh - .35, gh + .35, n1 - .7, n1 + .7, 4.6, 5.2)
    # ---- the gallery floor round the void: gone over the rotunda and the escalators, crossed by two bridges
    esc = M["esc"]

    def gallery(e, n):
        if math.hypot(e - rot[0], n - rot[1]) < rr:
            return False
        for ee, nf, nt in esc:
            if abs(e - ee) < 3.0 and min(nf, nt) < n < max(nf, nt):
                return False
        if 24.0 < e < 34.0 and -1492.0 < n < -1474.0:                 # the east gallery fell in here
            return False
        if abs(e) < void:
            return any(abs(n - bn) < 3.0 for bn in M["bridges"])
        return True
    slab(g, "ru_stone", -half, half, n0, n1, z1, .36, 3.0, gallery, under="ru_concrete")
    rk.heap(g, (29.0, -1483.0, 0), 5.0, 2.6, 2120, ry=7.0)
    # ---- shop fronts on both storeys: piers and a lintel round each opening, a shutter down over some
    open_ = {}
    for lv, (za, zb, top) in enumerate(((0.0, z1 - .36, 3.6), (z1, roof - .35, 3.4))):
        for s in (-1, 1):
            ops = []
            for k in range(nb):
                shut = rnd.random() < (.3 if lv == 0 else .45)
                open_[(lv, s, k)] = not shut
                if shut:
                    rk.box(g, "ru_metal", (s * (conc - .22), n0 + k * bay + bay / 2, za + top / 2), (.05, 4.0, top / 2))
                else:
                    ops.append((k * bay + 2.0, k * bay + 10.0, top))
            wall(g, "ru_panel", (s * conc, n0), (s * conc, n1), za, zb, .4, ops)
            for k in range(1, nb):                                    # the walls between shops
                wall(g, "ru_panel", (s * (conc + .2), n0 + k * bay), (s * half, n0 + k * bay), za, zb, .25)
    # what is left in the open shops: a counter and shelving (cover, and somewhere for them to wait)
    for (lv, s, k), is_open in sorted(open_.items()):
        if not is_open:
            continue
        z = 0.0 if lv == 0 else z1
        nc = n0 + k * bay + bay / 2
        if lv == 1 and s > 0 and -1492.0 < nc < -1474.0:
            continue
        r = rnd.random()
        rk.box(g, "ru_panel", (s * (conc + 4.5 + r * 3), nc + (r - .5) * 3, z + .55), (.45, 1.8, .55), rnd.uniform(-.2, .2))
        for dn in (-bay / 2 + .5, bay / 2 - .5):
            if rnd.random() < .7:
                rk.box(g, "ru_metal", (s * (conc + 8.0), nc + dn, z + 1.0), (3.6, .22, 1.0))
        if rnd.random() < .5:
            rk.chunks(gd, (s * (conc + 6), nc), 4.0, 8, 2200 + k + lv * 40 + (s > 0) * 80, z=z)
        if lv == 0 and k % 4 == 1:
            H.light("lamp", (s * (conc + 5), nc, 3.0), 800)
    # ---- columns down the void's edge, railings between them, the bridges' rails
    for k in range(nb + 1):
        n = n0 + k * bay
        for s in (-1, 1):
            if math.hypot(s * void - rot[0], n - rot[1]) < rr + 1.5:
                continue
            block(g, "ru_concrete", s * void - .32, s * void + .32, n - .32, n + .32, 0.0, roof - .35)

    def rail(a, b):
        rk.wall_path(g, "ru_metal", [a, b], .1, 1.1, rnd=rnd, broken=.3)
    for s in (-1, 1):
        cuts = sorted([(bn - 3.0, bn + 3.0) for bn in M["bridges"]] + [(rot[1] - rr - 1, rot[1] + rr + 1)])
        n = n0 + .5
        for c0, c1 in cuts:
            rail((s * (void + .1), n, z1), (s * (void + .1), c0, z1))
            n = c1
        rail((s * (void + .1), n, z1), (s * (void + .1), n1 - .5, z1))
    for bn in M["bridges"]:
        for dn in (-3.0, 3.0):
            rail((-void, bn + dn, z1), (void, bn + dn, z1))
    for ee, nf, nt in esc:                                            # the escalators and the rails round their wells
        escalator(g, gd, ee, nf, nt, z1)
        for de in (-3.0, 3.0):
            rail((ee + de, nf, z1), (ee + de, nt, z1))
        rail((ee - 3.0, nf, z1), (ee + 3.0, nf, z1))
    # ---- the roof: solid over the shops and galleries, a skylight down the middle that came down over the rotunda
    for s in (-1, 1):
        block(g, "ru_concrete", min(s * void, s * (half + .6)), max(s * void, s * (half + .6)), n0, n1, roof - .35, roof, top_mat="ru_asphalt")
        block(g, "ru_metal", s * void - .25, s * void + .25, n0, n1, roof - .7, roof - .35)
    k = 0
    n = n0 + 3.0
    while n < n1 - 2:
        fallen = abs(n - rot[1]) < rr + 4
        if not fallen:
            block(g, "ru_metal", -void, void, n - .14, n + .14, roof - .1, roof + .25)
            if rnd.random() < .55:
                rk.box(gd, "ru_glass", (0.0, n + 3.0, roof + .1), (void - .3, 2.8, .02))
        n += 6.0
        k += 1
    # ---- the rotunda: the dead fountain, the skylight's truss lying in it, moonlight coming down the hole
    rk.annulus(g, "ru_stone", rot, 4.3, 5.0, 0.0, .75, n=40)
    rk.cyl(g, "ru_concrete", rot, 4.3, 0.0, .14, n=40, smooth=False)
    rk.cyl(g, "ru_stone", rot, 1.3, 0.0, 2.3, n=12, r1=.9, smooth=False)
    rk.heap(g, (6.5, rot[1] + 5.0, 0), 5.0, 2.2, 2130, ry=6.5)
    rk.heap(g, (-8.0, rot[1] - 7.0, 0), 4.0, 1.7, 2131)
    for i, (a, b) in enumerate((((-11, rot[1] - 3, .3), (4, rot[1] + 2, 3.6)), ((10, rot[1] - 10, .25), (-2, rot[1] - 6, 2.4)),
                                ((-6, rot[1] + 11, .25), (9, rot[1] + 9, 1.8)), ((2, rot[1] + 13, .3), (12, rot[1] + 3, 4.4)))):
        sloped(g, "ru_metal", a, b, .16, .34)
    rk.chunks(gd, rot, rr, 80, 2132, size=(.12, .4))
    H.light("moon", (0.0, rot[1], 7.5), 3400, 90.0)
    H.light("moon", (0.0, rot[1], 1.5), 1800, 30.0)
    # ---- the concourse's cover: planters, kiosks, benches; fires and growth for light
    j = 0
    n = n0 + 20.0
    while n < n1 - 46:
        if abs(n - rot[1]) > rr + 6 and all(abs(n - bn) > 5 for bn in M["bridges"]):
            e = (-1) ** j * 5.5
            if j % 3 == 0:                                            # a kiosk: a counter round a pillar, a roof on posts
                block(g, "ru_panel", e - 1.5, e + 1.5, n - 1.5, n + 1.5, 0, 1.1)
                block(g, "ru_metal", e - .2, e + .2, n - .2, n + .2, 1.1, 2.7)
                block(g, "ru_panel", e - 1.8, e + 1.8, n - 1.8, n + 1.8, 2.7, 2.86)
            elif j % 3 == 1:
                block(g, "ru_concrete", e - 2.4, e + 2.4, n - .8, n + .8, 0, .85, top_mat="ru_rubble")
                rk.tube(g, "ru_metal", [(e, n, .85), (e + .2, n, 2.4), (e - .3, n + .2, 3.4)], .08, 6, r_end=.03)
            else:
                block(g, "ru_stone", e - 2.0, e + 2.0, n - .3, n + .3, 0, .48)
                block(g, "ru_stone", e - 2.0, e + 2.0, n + .2, n + .34, .48, 1.0)
            rk.alien_barricade(g, (-e * 1.3, n + 6, 0), PI, 2140 + j, w=3.0)
            if j % 2 == 0:
                H.fire(gd, (-e, n - 5, 0.0), 2160 + j)
            else:
                H.void_growth(gd, (-e * 2.6, n + 2, 0), 2.0, 2180 + j)
        n += 22.0
        j += 1
    for i, (e, n, w) in enumerate(((-conc + .4, -1528.0, (1, 0)), (conc - .4, -1414.0, (-1, 0)), (-conc + .4, -1380.0, (1, 0)))):
        growth(g, gd, (e, n, 0), 3.4, 2190 + i, w)
        H.ambience("hive", (e, n, 0), 12, .7, spores=True)
        H.light("void", (e * .9, n, 1.0), 1100)
    rk.alien_spire(g, gd, (-12.0, rot[1] + 16, 0), 8.5, 2195)
    H.ambience("hum", (-12.0, rot[1] + 16, 0), 30, 1.0)
    H.light("void", (-12.0, rot[1] + 16, 7.5), 1500)
    for bn in (-1580.0, -1500.0, -1400.0, -1330.0):
        rk.cable(gd, (-void, bn, z1 + 3.2), (void, bn + 5, z1 + 3.6), 1.4)
    for i in range(6):                                                # what little light the gallery has
        H.light("lamp", ((-1) ** i * 15.0, n0 + 30 + i * 46, z1 + 3.0), 1100)
    for i in range(8):                                                # ...and the concourse under it
        H.light("lamp", ((-1) ** i * 12.0, n0 + 18 + i * 36, 3.9), 1400)
    # ---- the food court before the gate: tables, the counters along the north wall
    for i in range(14):
        e = -26 + (i % 7) * 8.6 + rnd.uniform(-1, 1)
        n = -1336 + (i // 7) * 9 + rnd.uniform(-1, 1)
        if abs(e - 15) < 4.5 and n < -1329:
            continue
        table(g, (e, n, .05))
    for s in (-1, 1):
        block(g, "ru_panel", s * 9.0 if s > 0 else -19.0, 19.0 if s > 0 else -9.0, n1 - 3.4, n1 - 2.4, 0, 1.1)
    # ---- the loading yard behind: docks, the way down to the station
    yn = M["yard_n1"]
    yh = M["yard_half"]
    H.ground_slab(g, "ru_asphalt", -yh, yh, n1, yn, .04)
    D = P.DEEPLINE
    for s in (-1, 1):
        wall(g, "ru_concrete", (s * (yh + .3), n1), (s * (yh + .3), D["stair_n1"]), 0, 5.0, .6)
        block(g, "ru_concrete", min(s * 9.0, s * 19.0), max(s * 9.0, s * 19.0), n1 + 3.0, n1 + 15.0, 0, 1.2)
        wall(g, "ru_concrete", (s * D["stair_half"], D["stair_n1"] + .3), (s * (yh + .6), D["stair_n1"] + .3), 0, 5.0, .6)
        H.jersey(g, (s * 8.0, yn - 4.0, 0), PI / 2, 3.0)
    block(g, "ru_metal", -3.0, 3.0, n1 + 20.0, n1 + 21.0, 0, 1.0)
    H.fire(gd, (-15.0, yn - 6.0, 0.0), 2198)
    H.light("lamp", (14.0, n1 + 9.0, 3.2), 1000)


# ------------------------------------------------------------------ Deepline
def zone_deepline(G, H):
    g, gd = G["deepline"]
    D = P.DEEPLINE
    rnd = random.Random(2601)
    s0, s1, sh = D["stair_n0"], D["stair_n1"], D["stair_half"]
    z, top, track = D["z"], D["top"], D["track"]
    # ---- the way down: a wide stair between two walls (the hand rails still up)
    rk.path_deck(g, "ru_concrete", "ru_concrete", [(0.0, s0, 0.02), (0.0, s1, z)], sh * 2, .6)
    kk = int(abs(z) / .2)
    for i in range(1, kk):
        t = i / kk
        rk.box(gd, "ru_stone", (0.0, s0 + (s1 - s0) * t, z * t + .03), (sh - .02, .04, .02))
    for s in (-1, 1):
        block(g, "ru_concrete", min(s * sh, s * (sh + .6)), max(s * sh, s * (sh + .6)), s0, s1, z - .6, 1.05)
        rk.tube(g, "ru_metal", [(s * (sh - .25), s0, 1.0), (s * (sh - .25), s1, z + 1.0)], .05, 6)
    rk.tube(g, "ru_metal", [(0.0, s0, 1.0), (0.0, s1, z + 1.0)], .05, 6)
    H.light("lamp", (0.0, s1 + 3, z + 3.4), 1200)
    # ---- the ticket hall
    h1, hh = D["hall_n1"], D["hall_half"]
    block(g, "ru_stone", -hh, hh, s1, h1, z - .4, z)
    for s in (-1, 1):
        wall(g, "ru_panel", (s * (hh + .3), s1 - .6), (s * (hh + .3), h1), z, top, .6)
        wall(g, "ru_panel", (s * sh, s1 - .3), (s * (hh + .6), s1 - .3), z, top, .6)
        wall(g, "ru_panel", (s * D["wall"], h1), (s * (hh + .6), h1), z, top, .6)
        block(g, "ru_concrete", s * 8.0 - .35, s * 8.0 + .35, s1 + 11.7, s1 + 12.4, z, top)
        block(g, "ru_concrete", s * 8.0 - .35, s * 8.0 + .35, s1 + 25.7, s1 + 26.4, z, top)
        block(g, "ru_panel", min(s * 11.0, s * 15.4), max(s * 11.0, s * 15.4), s1 + 4.0, s1 + 9.0, z, z + 2.6)       # the ticket offices
    for i in range(7):                                                # the gate line: stiles with gaps between
        e = -9.0 + i * 3.0
        block(g, "ru_metal", e - .22, e + .22, s1 + 17.2, s1 + 19.0, z, z + 1.0)
    for i, e in enumerate((-12.5, 12.5)):
        block(g, "ru_stone", e - 2.0, e + 2.0, s1 + 29.0, s1 + 29.6, z, z + .46)
    rk.chunks(gd, (0.0, (s1 + h1) / 2), 13, 40, 2610, z=z)
    H.fire(gd, (-11.0, s1 + 22.0, z), 2611)
    for e, dn in ((9.0, 14.0), (-9.0, 27.0), (9.0, 31.0), (-12.0, 6.0)):
        H.light("lamp", (e, s1 + dn, z + 3.6), 1100)
    # ---- the platform hall: an island platform between two track beds, columns down it
    p1, ph, wl = D["plat_n1"], D["plat_half"], D["wall"]
    block(g, "ru_stone", -ph, ph, h1, p1, track - .4, z)
    for s in (-1, 1):
        block(g, "ru_concrete", min(s * ph, s * wl), max(s * ph, s * wl), h1, p1 + 8.0, track - .4, track, top_mat="ru_rubble")
        wall(g, "ru_panel", (s * (wl + .3), h1), (s * (wl + .3), p1 + 8.0), track, top, .6)
        wall(g, "ru_concrete", (s * D["tun_half"], p1 + 8.3), (s * (wl + .6), p1 + 8.3), track, top, .6)      # the side beds' ends
        rk.heap(g, (s * 7.5, p1 + 5.5, track), 2.4, 2.6, 2620 + (s > 0), ry=3.0)
        # the way from the hall down onto each bed, and the yellow line nobody stands behind now
        rk.path_deck(g, "ru_concrete", "ru_concrete", [(s * 7.5, h1, z), (s * 7.5, h1 + 7.0, track)], 5.0, .4)
        rk.box(gd, "ru_glow", (s * (ph - .5), (h1 + p1) / 2, z + .012), (.07, (p1 - h1) / 2 - 1, .01))
        for dx in (-.72, .72):                                        # the rails
            rk.tube(gd, "ru_metal", [(s * 7.5 + dx, h1 + 7.0, track + .09), (s * 7.5 + dx, p1 + 3.0, track + .09)], .045, 5)
    n = h1 + 8.0
    k = 0
    while n < p1 - 4:
        for s in (-1, 1):
            block(g, "ru_concrete", s * 3.2 - .3, s * 3.2 + .3, n - .3, n + .3, z, top)
        if k % 2 == 0:
            block(g, "ru_stone", -1.6, 1.6, n + 4.6, n + 5.2, z, z + .46)
        else:
            block(g, "ru_metal", -.9, .9, n + 4.4, n + 5.4, z, z + 2.1)        # a map board
        n += 10.0
        k += 1
    rk.path_deck(g, "ru_concrete", "ru_concrete", [(0.0, p1, z), (0.0, p1 + 8.0, track)], ph * 2, .5)
    # the nest: growth over the walls and the beds, pods, the hearts' light
    for i, (e, n, w) in enumerate(((-wl + .3, -1176.0, (1, 0)), (wl - .3, -1146.0, (-1, 0)), (-wl + .3, -1118.0, (1, 0)), (0.0, -1196.0, None))):
        growth(g, gd, (e, n, track if w else z), 3.6, 2630 + i, w)
        H.ambience("hive", (e, n, z), 14, .9, spores=True)
        H.light("void", (e * .85, n, z + 1.2), 1300)
    for i, (e, n) in enumerate(((-7.5, -1160.0), (7.5, -1130.0), (-7.5, -1108.0), (7.0, -1188.0))):
        rk.pod(g, gd, (e, n, track), rnd.uniform(.9, 1.3), 2640 + i)
    H.ambience("chorus", (0.0, -1150.0, z), 60, .6)
    for i in range(3):
        H.light("lamp", ((-1) ** i * 2.0, h1 + 16 + i * 34, top - .5), 1100)
    # ---- the tunnel: a ribbed tube, pipes down one wall, its roof down half way along and a service corridor round that
    t1, th, tt = D["tun_n1"], D["tun_half"], D["tun_top"]
    t0 = p1 + 8.0
    rn = D["rise_n"]
    block(g, "ru_concrete", -th, th, t0, rn, track - .4, track, top_mat="ru_rubble")
    rk.path_deck(g, "ru_concrete", "ru_concrete", [(0.0, rn, track), (0.0, t1, P.SLUICE["z"])], th * 2, .5)
    f0, f1 = D["fall_n"]
    c0, c1 = D["side"]
    east_doors = [(f0 - 7.0 - t0, f0 - 5.0 - t0, 2.4), (f1 + 5.0 - t0, f1 + 7.0 - t0, 2.4)]
    wall(g, "ru_concrete", (th + .3, t0), (th + .3, t1), track - .4, tt, .6, east_doors)
    wall(g, "ru_concrete", (-th - .3, t0), (-th - .3, t1), track - .4, tt, .6)
    block(g, "ru_concrete", -th - .6, th + .6, t0, t1, tt, top + .001)
    n = t0 + 6.0
    while n < t1 - 4:
        if not (f0 - 10 < n < f1 + 10):                               # (none at the fall, nor in the service doors)
            block(g, "ru_concrete", -th, th, n - .3, n + .3, tt - .45, tt)
            for s in (-1, 1):
                block(g, "ru_concrete", min(s * (th - .35), s * th), max(s * (th - .35), s * th), n - .3, n + .3, track, tt - .45)
        n += 12.0
    for zz, r in ((track + 3.4, .16), (track + 2.9, .1)):
        rk.tube(gd, "ru_metal", [(-th + .25, t0 + 1, zz), (-th + .25, f0 - 3, zz)], r, 6)
        rk.tube(gd, "ru_metal", [(-th + .25, f1 + 3, zz), (-th + .25, t1 - 1, zz)], r, 6)
    for dx in (-.72, .72):
        rk.tube(gd, "ru_metal", [(dx, t0 + 1, track + .09), (dx, f0 - 4, track + .09)], .045, 5)
    # the fall: the roof came down and filled the tube
    fm = (f0 + f1) / 2
    block(g, "ru_rubble", -th, th, fm - 7.0, fm + 7.0, track, tt)                # the plug itself: nothing gets past it
    rk.heap(g, (0.0, fm, track), th + .6, 5.9, 2650, ry=(f1 - f0) / 2 - 3, chunks=26)
    rk.heap(g, (-1.5, fm - 9, track), 4.6, 4.2, 2651, ry=6.0)
    rk.heap(g, (1.5, fm + 9, track), 4.6, 4.4, 2652, ry=6.0)
    for i, (e, n, a) in enumerate(((-2.0, f0 + 5, .5), (2.4, f1 - 6, -.6), (0.0, fm, .2))):
        rk.box(g, "ru_concrete", (e, n, track + 2.6), (2.6, 1.8, .2), R=Matrix.Rotation(a, 3, 'X') @ Matrix.Rotation(a * .7, 3, 'Y'))
    # the service corridor round it
    block(g, "ru_concrete", th - .1, c1, f0 - 9.0, f1 + 9.0, track - .4, track)      # (from the tunnel's floor: no gap under the doors)
    wall(g, "ru_concrete", (c1 + .25, f0 - 9.3), (c1 + .25, f1 + 9.3), track, track + 2.7, .5)
    for nn in (f0 - 9.0, f1 + 9.0):
        wall(g, "ru_concrete", (c0, nn), (c1 + .5, nn), track, track + 2.7, .5)
    block(g, "ru_concrete", c0, c1 + .5, f0 - 9.25, f1 + 9.25, track + 2.7, track + 3.1)
    for i in range(4):
        rk.box(gd, "ru_glow", (c1 - .05, f0 - 4 + i * 16, track + 2.3), (.03, .5, .06))
        H.light("lamp", ((c0 + c1) / 2, f0 - 4 + i * 16, track + 2.0), 600, 8.0)
    rk.tube(gd, "ru_metal", [(c0 + .2, f0 - 8.5, track + 2.4), (c0 + .2, f1 + 8.5, track + 2.4)], .08, 6)
    # what lives down here
    for i, (n, e) in enumerate(((-1070.0, -2.5), (-1046.0, 2.0), (-950.0, -1.5), (-926.0, 2.5))):
        rk.alien_barricade(g, (e, n, track), PI, 2660 + i, w=3.0)
    for i, (e, n, w) in enumerate(((-th + .3, -1058.0, (1, 0)), (th - .3, -1034.0, (-1, 0)), (-th + .3, -944.0, (1, 0)), (th - .3, -918.0, (-1, 0)))):
        growth(g, gd, (e, n, track), 3.2, 2670 + i, w)
        H.ambience("hive", (e, n, track), 12, .9, spores=True)
        H.light("void", (e * .8, n, track + 1.2), 1200)
    for i, (e, n) in enumerate(((3.2, -1082.0), (-3.4, -1022.0), (3.0, -962.0), (-3.2, -932.0), (3.4, -900.0))):
        rk.pod(g, gd, (e, n, track), rnd.uniform(.8, 1.2), 2680 + i)
        if i % 2 == 0:
            H.void_growth(gd, (-e, n + 6, track), 1.6, 2690 + i)
    for n in (-1088.0, -1064.0, -1000.0, -984.0, -910.0, -892.0):
        H.light("lamp", (0.0, n, tt - .6), 700, 9.0)
    H.ambience("chorus", (0.0, -990.0, track), 80, .5)


# ------------------------------------------------------------------ The Sluice
def zone_sluice(G, H):
    g, gd = G["sluice"]
    S = P.SLUICE
    D = P.DEEPLINE
    n0, n1, half, z = S["n0"], S["n1"], S["half"], S["z"]
    rnd = random.Random(3101)
    R = S["ramp"]
    block(g, "ru_concrete", -half, half, n0, n1, z - .5, z, top_mat="ru_rubble")
    # the banks: a wall and a parapet each side, the east one open at the spillway
    wall(g, "ru_concrete", (-half - .4, n0 - .8), (-half - .4, n1 + .8), z - .5, 0.0, .8)
    wall(g, "ru_concrete", (-half - .2, n0), (-half - .2, n1), 0.0, 1.1, .4, top_mat="ru_stone")
    for a, b in ((n0 - .8, R["n0"]), (R["n1"], n1 + .8)):
        wall(g, "ru_concrete", (half + .4, a), (half + .4, b), z - .5, 0.0, .8)
        wall(g, "ru_concrete", (half + .2, max(a, n0)), (half + .2, min(b, n1)), 0.0, 1.1, .4, top_mat="ru_stone")
    # the south end: the tunnel's mouth; the north end: the dam and its dead gates
    th = D["tun_half"]
    wall(g, "ru_concrete", (-half - .8, n0 - .4), (half + .8, n0 - .4), z - .5, 1.1, .8, [(half + .8 - th, half + .8 + th, D["tun_top"] - z + .5)])
    wall(g, "ru_concrete", (-half - .8, n1 + .6), (half + .8, n1 + .6), z - .5, 2.4, 1.2)
    for e in (-9.0, 0.0, 9.0):
        block(g, "ru_metal", e - 2.6, e + 2.6, n1 - .3, n1, z + .4, z + 4.6)
        block(g, "ru_concrete", e - 3.1, e - 2.6, n1 - 1.0, n1, z, 2.4)
        block(g, "ru_concrete", e + 2.6, e + 3.1, n1 - 1.0, n1, z, 2.4)
    # the spillway up the east bank
    rk.path_deck(g, "ru_concrete", "ru_concrete", [(half, (R["n0"] + R["n1"]) / 2, z), (R["e1"], (R["n0"] + R["n1"]) / 2, 0.02)], R["n1"] - R["n0"], .7)
    for nn in (R["n0"] - .3, R["n1"] + .3):
        wall(g, "ru_concrete", (half, nn), (R["e1"], nn), z - .5, 1.1, .6, top_mat="ru_stone")
    # the pump house: three piers across the bed with a deck over them, two of its gates hanging
    pn = S["pump_n"]
    for e in (-10.0, 0.0, 10.0):
        block(g, "ru_concrete", e - 1.5, e + 1.5, pn - 5.0, pn + 5.0, z, 2.2)
        block(g, "ru_concrete", e - 1.9, e + 1.9, pn - 6.2, pn - 5.0, z, z + 1.6, top_mat="ru_stone")      # the cutwater
    block(g, "ru_concrete", -half - .8, half + .8, pn - 5.0, pn + 5.0, 2.2, 2.9, top_mat="ru_asphalt")
    for e0, e1 in ((-8.5, -1.5), (11.5, half)):
        block(g, "ru_metal", e0, e1, pn - .25, pn + .25, z + 3.4, 2.2)
    block(g, "ru_panel", -6.0, 6.0, pn - 4.0, pn + 4.0, 2.9, 6.4)
    block(g, "ru_concrete", -6.6, 6.6, pn - 4.6, pn + 4.6, 6.4, 6.8, top_mat="ru_asphalt")
    # the footbridges: one whole, one with its east half down in the bed
    b0, b1 = S["bridges"]
    block(g, "ru_concrete", -half - .8, half + .8, b0 - 2.0, b0 + 2.0, .1, .6, top_mat="ru_stone")
    block(g, "ru_concrete", -half - .8, -2.0, b1 - 2.0, b1 + 2.0, .1, .6, top_mat="ru_fracture")
    sloped(g, "ru_concrete", (half + .2, b1 + .6, .5), (3.0, b1 - 1.0, z + .5), 2.0, .5)
    for bn, e1 in ((b0, half + .8), (b1, -2.0)):
        for dn in (-1.9, 1.9):
            rk.wall_path(g, "ru_metal", [(-half - .8, bn + dn, .6), (e1, bn + dn, .6)], .08, 1.0, rnd=rnd, broken=.3)
    for e in (-6.0, 6.0):
        block(g, "ru_concrete", e - .6, e + .6, b0 - 1.4, b0 + 1.4, z, .1)
    block(g, "ru_concrete", -7.6, -6.4, b1 - 1.4, b1 + 1.4, z, .1)
    # what the water left: pipes, silt, blocks, sluice plates
    for i, (e, n, yaw, L) in enumerate(((-9.0, -850.0, PI / 2, 12.0), (8.0, -818.0, PI / 2 + .3, 10.0), (-6.0, -760.0, .2, 9.0), (7.0, -742.0, PI / 2, 14.0),
                                         (-8.5, -660.0, PI / 2 - .2, 11.0), (5.0, -640.0, .1, 8.0), (-7.0, -585.0, PI / 2, 12.0), (9.5, -600.0, PI / 2, 9.0))):
        dx, dy = math.cos(yaw) * L / 2, math.sin(yaw) * L / 2
        rk.tube(g, "ru_concrete", [(e - dx, n - dy, z + 1.05), (e + dx, n + dy, z + 1.05)], 1.05, 14, smooth=True)
    for i, (e, n) in enumerate(((10.0, -868.0), (-11.0, -826.0), (11.0, -780.0), (-10.5, -728.0), (0.0, -668.0), (11.0, -628.0), (-11.0, -606.0),
                                (4.0, -548.0), (-9.0, -540.0))):
        rk.heap(g, (e, n, z), rnd.uniform(3, 4.5), rnd.uniform(1.0, 2.0), 3110 + i, ry=rnd.uniform(4, 6))
    for i, (e, n) in enumerate(((0.0, -842.0), (-3.0, -790.0), (4.0, -770.0), (-2.0, -735.0), (2.0, -652.0), (-4.0, -615.0), (0.0, -575.0))):
        s = rnd.uniform(.7, 1.0)
        rk.box(g, "ru_concrete", (e, n, z + s), (s * 1.3, s, s), rnd.uniform(0, 1.5), top_mat="ru_fracture")
    for i, (e, n, yaw) in enumerate(((-5.0, -822.0, PI), (6.0, -806.0, PI), (-11.0, -716.0, PI), (5.0, -716.0, PI), (-5.0, -683.0, PI),
                                     (11.5, -683.0, PI), (-6.0, -596.0, PI), (6.0, -592.0, PI))):
        rk.alien_barricade(g, (e, n, z), yaw, 3130 + i)
    for i, (e, n, w) in enumerate(((-half + .3, -770.0, (1, 0)), (half - .3, -650.0, (-1, 0)), (-half + .3, -560.0, (1, 0)))):
        growth(g, gd, (e, n, z), 4.0, 3140 + i, w)
        H.ambience("hive", (e, n, z), 14, .8, spores=True)
        H.light("void", (e * .85, n, z + 1.2), 1300)
    rk.alien_spire(g, gd, (-9.0, -756.0, z), 11.0, 3145)
    H.ambience("hum", (-9.0, -756.0, z), 30, 1.0)
    H.light("void", (-9.0, -756.0, z + 10.0), 1700)
    for i, (e, n) in enumerate(((8.0, -846.0), (-8.0, -705.0), (9.0, -612.0), (0.0, -536.0))):
        H.fire(gd, (e, n, z), 3150 + i)
    for n in (-860.0, -780.0, -740.0, -660.0, -580.0):
        rk.cable(gd, (-half - 1, n, 5.0), (half + 1, n + 6, 6.5), 3.0)
    rk.chunks(gd, (0.0, -700.0), 14, 120, 3160, z=z)
    rk.chunks(gd, (0.0, -820.0), 14, 80, 3161, z=z)
    rk.chunks(gd, (0.0, -590.0), 14, 80, 3162, z=z)
    # the banks: lamp posts along the parapets, ruins standing back from them
    for i in range(9):
        for s in (-1, 1):
            n = n0 + 20 + i * 40
            if s > 0 and R["n0"] - 6 < n < R["n1"] + 6:
                continue
            H.lamp_post(g, gd, (s * (half + 2.2), n, 0), PI if s > 0 else 0.0, 3170 + i * 2 + (s > 0), broken=(i + (s > 0)) % 3 == 0)
    for s in (-1, 1):
        n = n0 + 4
        k = 0
        while n < n1 - 20:
            L = rnd.uniform(18, 28)
            if not (s > 0 and n + L > R["n0"] - 14):
                rk.tower(g, gd, (s * (half + 20 + rnd.uniform(0, 6)), n + L / 2), rnd.uniform(16, 20), L, rnd.randint(4, 9), yaw=rnd.uniform(-.05, .05),
                         seed=3200 + k * 2 + (s > 0), style=rnd.choice(("panel", "concrete")), top=(.35, 1.0), holes=2, col_top=7.0)
            n += L + rnd.uniform(4, 8)
            k += 1


# ------------------------------------------------------------------ The Causeway
def zone_causeway(G, H):
    g, gd = G["causeway"]
    C = P.CAUSEWAY
    rnd = random.Random(3601)
    pts = [(e, n, .06) for e, n in C["path"]]
    rk.path_deck(g, "ru_asphalt", "ru_concrete", pts, C["half"] * 2 + 2, .14)
    R = P.SLUICE["ramp"]
    H.ground_slab(g, "ru_asphalt", R["e1"] - .5, 57.0, R["n0"] - .5, R["n1"] + 8, .05)
    k = 0
    for side, line in ((1, C["east"]), (-1, C["west"])):
        for (a, b) in zip(line[1:], line[2:]):
            a, b = Vector(a), Vector(b)
            d = (b - a)
            L = d.length
            u = d / L
            nrm = Vector((u.y, -u.x)) * side
            if nrm.x * side < 0:
                nrm = -nrm
            s = 2.0
            while s < L - 14:
                w = rnd.uniform(16, 22)
                c = a + u * (s + w / 2) + nrm * (8 + rnd.uniform(0, 4) + 8)
                rk.tower(g, gd, (c.x, c.y), 16, w, rnd.randint(3, 8), yaw=math.atan2(u.y, u.x) + PI / 2, seed=3700 + k,
                         style=rnd.choice(("panel", "concrete")), top=(.3, 1.0), holes=2, col_top=7.0)
                s += w + rnd.uniform(3, 7)
                k += 1
            for i in range(2):
                p = a + u * rnd.uniform(4, L - 4) + nrm * rnd.uniform(-1.5, 1.0)
                rk.heap(g, (p.x, p.y, 0), rnd.uniform(3, 5), rnd.uniform(1.2, 2.6), 3750 + k * 3 + i, ry=rnd.uniform(4, 7))
    for i, (e, n, y) in enumerate(((44, -530, .3), (38, -506, 1.2), (27, -488, .4), (20, -470, 1.0), (8, -448, .6), (-3, -410, .1), (4, -390, -.1),
                                   (-4, -362, 1.5), (5, -340, .2))):
        H.jersey(g, (e, n, 0), y, 3.2)
    for i, (e, n) in enumerate(((49, -520), (33, -500), (11, -440), (-6, -396), (6, -352))):
        H.hedgehog(g, (e, n, 0), 3770 + i)
    for i, (e, n, yaw) in enumerate(((40, -512, PI + .3), (26, -482, PI + .5), (12, -452, PI + .4), (0, -404, PI), (0, -366, PI))):
        rk.alien_barricade(g, (e, n, 0), yaw, 3780 + i)
    H.fire(gd, (36.0, -494.0, 0.0), 3790)
    H.fire(gd, (-5.0, -376.0, 0.0), 3791)
    H.void_growth(gd, (22.0, -452.0, 0), 2.6, 3792)
    H.void_growth(gd, (-7.5, -420.0, 0), 2.2, 3793)
    rk.chunks(gd, (20.0, -470.0), 12, 50, 3794)
    rk.chunks(gd, (0.0, -380.0), 9, 40, 3795)
    for i, (e, n) in enumerate(((50.5, -540), (35, -520), (9, -455), (-8.6, -400), (8.6, -350))):
        H.lamp_post(g, gd, (e, n, 0), PI if e > 0 else 0.0, 3796 + i, broken=i % 2 == 0)


# ------------------------------------------------------------------ the route's invisible edges
def blockers(g):
    """pawn-only walls and lids along the new districts: nothing to climb out over (a double jump and a clamber reach
    about six metres; the lids sit above what is meant to be reached)"""
    def w(a, b, z0=-1.0, z1=16.0):
        a, b = Vector(a), Vector(b)
        d = b - a
        m = (a + b) / 2
        rk.box(g, "ru_block", (m.x, m.y, (z0 + z1) / 2), (d.length / 2 + .3, .3, (z1 - z0) / 2), math.atan2(d.y, d.x))

    def lid(e0, e1, n0, n1, z):
        rk.box(g, "ru_block", ((e0 + e1) / 2, (n0 + n1) / 2, z + .3), ((e1 - e0) / 2, (n1 - n0) / 2, .3))
    V, S, M, D, L, C = P.VERGE, P.STACKS, P.GALLERIA, P.DEEPLINE, P.SLUICE, P.CAUSEWAY
    h = V["half"] + 1
    w((-h, V["n0"] - 4), (h, V["n0"] - 4))
    for s in (-1, 1):
        w((s * h, V["n0"] - 4), (s * h, S["block"]["n0"] - 14))
        w((s * (S["half"] + .9), S["block"]["n0"] - 14), (s * (S["half"] + .9), S["arch"]["n1"]))
        w((s * (S["alley"]["half"] + .9), S["arch"]["n1"]), (s * (S["alley"]["half"] + .9), S["alley"]["n1"]))
        w((s * (M["yard_half"] - .2), M["n1"]), (s * (M["yard_half"] - .2), D["stair_n1"]))
        w((s * D["stair_half"], D["stair_n1"] + .1), (s * M["yard_half"], D["stair_n1"] + .1))
    # nothing above the first storey in the estate (the upper floors are scenery), nor over the alley's walls
    lid(-S["half"] - 1, S["half"] + 1, S["block"]["n0"] - 14, S["arch"]["n1"], 9.6)
    lid(-S["alley"]["half"] - 1, S["alley"]["half"] + 1, S["arch"]["n1"], S["alley"]["n1"], 8.4)
    lid(-M["half"], M["half"], M["n0"], M["n1"], 9.3)                            # not out through the skylight
    w((-D["stair_half"], D["stair_n1"] + .1), (D["stair_half"], D["stair_n1"] + .1), .2, 16.0)   # not along the stair's parapets
    for s in (-1, 1):
        w((s * (M["half"] - .1), M["fore_n0"]), (s * (M["half"] - .1), M["n0"]))
    # the canal: its banks, round the spillway, the dam
    R = L["ramp"]
    w((-L["half"] + .1, L["n0"]), (-L["half"] + .1, L["n1"]), L["z"] - 1, 16.0)
    w((L["half"] - .1, L["n0"]), (L["half"] - .1, R["n0"]), L["z"] - 1, 16.0)
    w((L["half"] - .1, R["n1"]), (L["half"] - .1, L["n1"]), L["z"] - 1, 16.0)
    w((-L["half"], L["n1"] - .2), (L["half"], L["n1"] - .2), L["z"] - 1, 16.0)
    w((L["half"], R["n0"] + .1), (R["e1"] + .4, R["n0"] + .1), L["z"] - 1, 16.0)
    w((L["half"], R["n1"] - .1), (R["e1"] + .4, R["n1"] - .1), L["z"] - 1, 16.0)
    for line in (C["east"], C["west"]):
        for a, b in zip(line, line[1:]):
            w(a, b)


ZONES = dict(verge=zone_verge, stacks=zone_stacks, galleria=zone_galleria, deepline=zone_deepline, sluice=zone_sluice,
             causeway=zone_causeway)
