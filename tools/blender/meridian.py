"""Meridian, the ruined capital of the first operation (tools/operation/meridian_plan.py has the layout and the
mission). A dark storm over a dead city: ruined towers, the great wall and its gate, a tower-lined boulevard under a
fallen overpass, the round Concord Ring with its broken monument, the High Terraces up the east side, the Crown
Bridge, and the Crown itself, a round platform with a beam into the sky under the broken orbital ring of the far spire.

Output assets/models/meridian.glb, one root per piece (export_fbx.py writes one FBX each):
  MR_<zone>          the zone's structure (Unreal: Nanite, drawn only)
  MR_<zone>_solid    what of it collides, exactly as drawn (Unreal: not Nanite, hidden, complex-as-simple collision:
                     a Nanite mesh's own collision comes from its simplified fallback and stops nothing where it should)
  MR_<zone>_detail   rebar, glass, mullions, small debris, banners, crystals (no collision)
  MR_backdrop        the skyline, the spire and its broken ring (no collision)
  MR_blockers        invisible walls along the route's edges (collision only, hidden in game)
  MRK_conduit        the Colossus's shield conduit (an actor; origin at its foot)
  MRK_barrier        an energy barrier, 1 x 1 m (x across, z up; the actor scales it)
zones: verge, stacks, galleria, deepline, sluice, causeway (meridian_south.py: the long way in), approach, gate,
boulevard, ring, terraces, crown, ground.
Also writes unreal/ShatteredOrbit/Data/op_meridian_art.json: where the lights go (void crystals, fires, the crown).

Every surface uses the ru_* sets (ruins_textures.py) through ruinkit.py; coordinates are the plan's (E, N, up) metres.

Run: blender --background --python tools/blender/meridian.py [-- --save=x.blend] [-- --zones=ring,crown]
"""
import bpy, json, math, os, random, sys
from mathutils import Vector, Matrix
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'operation'))
import bl
import ruinkit as rk
import meridian_plan as P
import meridian_south as south
import meridian_flora as flora
import meridian_story as story

TAU = rk.TAU
ART = os.path.join(P.ROOT, "unreal", "ShatteredOrbit", "Data", "op_meridian_art.json")
LIGHTS = []


def log(*a):
    print('[meridian]', *a, flush=True)


def light(kind, p, radius=1200.0, intensity=None):
    LIGHTS.append(dict(kind=kind, at=[round(p[1] * 100, 1), round(p[0] * 100, 1), round(p[2] * 100 + 60, 1)], radius=radius,
                       intensity=intensity))


def void_growth(g, p, size, seed, up=(0, 0, 1)):
    rk.crystal_cluster(g, p, size, seed, up)
    light("void", p, 900 + size * 250)


def fire(g, p, seed):
    """a burning heap of junk (a warm light in the dark)"""
    rk.chunks(g, p, 1.0, 6, seed, size=(.2, .5), z=p[2])
    light("fire", p, 1100)


# ------------------------------------------------------------------ street furniture / cover
def jersey(g, c, yaw, length=3.0, broken=False):
    """a concrete jersey barrier (the classic tapered profile) along yaw"""
    prof = [(-.31, 0), (.31, 0), (.31, .08), (.12, .33), (.09, .81), (-.09, .81), (-.12, .33), (-.31, .08)]
    T = rk._rz(yaw)
    half = length / 2
    vs, faces = [], []
    n = len(prof)
    for s, x in enumerate((-half, half)):
        for (py, pz) in prof:
            dx, dy = T(x, py)
            vs.append((c[0] + dx, c[1] + dy, c[2] + pz))
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, n + i, n + j, j))
    faces.append(tuple(range(n))[::-1]); faces.append(tuple(range(n, 2 * n)))
    g.add(vs, faces, "ru_concrete")


def hedgehog(g, c, seed):
    """three steel beams crossed (an anti-vehicle obstacle, now cover)"""
    rnd = random.Random(seed)
    base = rnd.uniform(0, TAU)
    for k in range(3):
        R = Matrix.Rotation(base, 3, 'Z') @ Matrix.Rotation(k * TAU / 3, 3, Vector((1, 1, 1)).normalized())
        rk.box(g, "ru_metal", (c[0], c[1], c[2] + .75), (1.1, .09, .09), R=R)


def lamp_post(g, gd, p, yaw, seed, broken=False):
    rnd = random.Random(seed)
    h = 7.5 if not broken else rnd.uniform(2.5, 5)
    tilt = Matrix.Rotation(rnd.uniform(.1, .5) if broken else 0, 3, Vector((math.cos(yaw), math.sin(yaw), 0)))
    top = Vector(p) + tilt @ Vector((0, 0, h))
    rk.tube(g, "ru_metal", [p, (Vector(p) + top) / 2, top], .11, 8, r_end=.07)
    if not broken:
        arm = top + Vector((math.cos(yaw), math.sin(yaw), 0)) * 1.6
        rk.tube(gd, "ru_metal", [top - Vector((0, 0, .3)), top + (arm - top) * .5 + Vector((0, 0, .15)), arm], .05, 6)
        rk.box(gd, "ru_metal", tuple(arm - Vector((0, 0, .12))), (.35, .14, .07), yaw)


def ground_slab(g, mat, x0, x1, y0, y1, z=0.0, thick=.05):
    rk.prism(g, mat, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], z - thick, z, side=mat)


# ------------------------------------------------------------------ zones
def zone_ground(G):
    """the ground under everything: rubble and ash out to the horizon"""
    g = G["ground"][0]
    # one sheet a metre thick, cut out where something is dug into it and open to the sky (the plan's pits): bands
    # between the pits' north / south edges, each band the strips between the pits that cross it
    E0, E1, N0, N1 = -1700.0, 1700.0, -2900.0, 1700.0
    cuts = sorted({N0, N1} | {p[2] for p in P.PITS} | {p[3] for p in P.PITS})
    for a, b in zip(cuts, cuts[1:]):
        spans = sorted((p[0], p[1]) for p in P.PITS if p[2] <= a and p[3] >= b)
        e = E0
        for s0, s1 in spans + [(E1, E1)]:
            if s0 - e > .01:
                rk.prism(g, "ru_rubble", [(e, a), (s0, a), (s0, b), (e, b)], -1.0, 0.0, side="ru_rubble")
            e = max(e, s1)


def zone_approach(G):
    g, gd = G["approach"]
    A = P.APPROACH
    n0, n1, half = A["n0"], A["n1"], A["half"]
    ground_slab(g, "ru_asphalt", -A["road"], A["road"], n0 - 20, n1 + 10, .03)
    rnd = random.Random(11)
    # low ruins down both sides (the corridor's walls) and higher ones behind
    for side in (-1, 1):
        n = n0 - 14
        k = 0
        while n < n1 - 8:
            L = rnd.uniform(16, 26)
            e = side * (half + rnd.uniform(8, 12))
            rk.tower(g, gd, (e, n + L / 2), rnd.uniform(14, 18), L, rnd.randint(2, 5), yaw=math.pi / 2 + rnd.uniform(-.05, .05),
                     seed=100 + k * 2 + (side > 0), style=rnd.choice(("panel", "concrete")), top=(.3, 1.0), holes=2)
            rk.tower(g, gd, (side * (half + 34 + rnd.uniform(0, 10)), n + L / 2), rnd.uniform(16, 22), L, rnd.randint(6, 12),
                     yaw=rnd.uniform(-.1, .1), seed=200 + k * 2 + (side > 0), style=rnd.choice(("panel", "concrete")),
                     top=(.4, 1.0), holes=2, rebar=False)
            n += L + rnd.uniform(3, 6)
            k += 1
        # rubble banks against them
        for i in range(6):
            rk.heap(g, (side * (half - rnd.uniform(1, 5)), rnd.uniform(n0, n1 - 10), 0), rnd.uniform(4, 8), rnd.uniform(1.5, 3.5),
                    300 + i + (side > 0) * 10, ry=rnd.uniform(5, 9))
    # the broken viaduct crossing overhead (diagonal), its east span down on the road
    a, b = Vector((-80, -292, 9.0)), Vector((80, -250, 9.0))
    d = (b - a).normalized()
    cut0, cut1 = .47, .63
    for t0, t1 in ((0.0, cut0), (cut1, 1.0)):
        p0, p1 = a.lerp(b, t0), a.lerp(b, t1)
        rk.path_deck(g, "ru_asphalt", "ru_concrete", [tuple(p0), tuple(p1)], 12.0, 1.4, end_mat="ru_fracture")
        for s in (-1, 1):
            off = Vector((-d.y, d.x, 0)) * s * 5.8
            rk.wall_path(g, "ru_concrete", [tuple(p0 + off), tuple(p1 + off)], .35, 1.0, rnd=rnd, broken=.4)
    # the fallen span: one end on the deck's break, the other on the road
    top = a.lerp(b, cut1) - d * .5
    foot = a.lerp(b, cut0 + .02) + Vector((0, 0, -9.0 + .7))
    rk.path_deck(g, "ru_asphalt", "ru_concrete", [tuple(foot), tuple(top - Vector((0, 0, .6)))], 11.0, 1.2, end_mat="ru_fracture")
    for t in (cut0, cut1):                                          # rebar at the breaks
        p = a.lerp(b, t)
        for k in range(14):
            o = Vector((-d.y, d.x, 0)) * rnd.uniform(-5.5, 5.5)
            s = p + o + Vector((0, 0, -rnd.uniform(.2, 1.2)))
            dirn = d * (1 if t == cut0 else -1)
            L = rnd.uniform(.6, 2.2)
            rk.tube(gd, "ru_metal", [tuple(s), tuple(s + dirn * L * .6 - Vector((0, 0, L * .2))), tuple(s + dirn * L - Vector((0, 0, L * .6)))], .02, 5, cap=False)
    for t in (.12, .3, .8, .95):                                     # piers
        p = a.lerp(b, t)
        rk.box(g, "ru_concrete", (p.x, p.y, 3.8), (1.2, 2.6, 3.8), math.atan2(d.y, d.x))
        rk.box(g, "ru_concrete", (p.x, p.y, 7.9), (1.6, 6.4, .5), math.atan2(d.y, d.x))
    # a wrecked checkpoint before the wall: barriers, hedgehogs, a fire
    for i, (e, n, y) in enumerate(((-10, -232, .1), (-6.5, -234, .0), (6, -230, -.1), (10, -233, .2), (-14, -226, 1.2),
                                   (2, -222, .05), (-2, -244, 1.5), (13, -246, 1.4))):
        jersey(g, (e, n, 0), y)
    for i, (e, n) in enumerate(((-18, -238), (18, -240), (-20, -258), (21, -262), (4, -270))):
        hedgehog(g, (e, n, 0), 40 + i)
    fire(gd, (-3.0, -236.0, 0.0), 51)
    rk.chunks(gd, (0, -255), 14, 40, 52)
    rk.chunks(gd, (0, -290), 12, 25, 53)
    for i, (e, n) in enumerate(((-7, -300), (7.5, -284), (-7.5, -262), (7.5, -240), (-7.5, -218))):
        lamp_post(g, gd, (e, n, 0), 0.0 if e < 0 else math.pi, 60 + i, broken=i % 2 == 0)
    void_growth(gd, (-22, -250, 0), 2.6, 70)
    void_growth(gd, (24, -214, 0), 3.2, 71)


def zone_gate(G):
    """the city wall, the great gate and the court behind it"""
    g, gd = G["gate"]
    W = P.WALL
    n, t, H = W["n"], W["thick"], W["height"]
    gw = W["gate_w"] / 2
    rnd = random.Random(21)
    # the wall in 4 m segments with a broken crest, buttresses on the outer (south) face, a walkway lip on top
    for side in (-1, 1):
        e = gw + 8.0
        while e < W["span"]:
            L = 4.0
            hh = H - (rnd.uniform(0, 7) if rnd.random() < .3 else rnd.uniform(0, .6))
            ec = side * (e + L / 2)
            rk.box(g, "ru_concrete", (ec, n, hh / 2), (L / 2 + .02, t / 2, hh / 2), top_mat="ru_fracture" if hh < H - 1 else None)
            if int(e) % 12 < 4:
                rk.box(g, "ru_concrete", (ec, n - t / 2 - 1.0, (hh - 3) / 2), (1.1, 1.0, (hh - 3) / 2))
            rk.box(g, "ru_panel", (ec, n - t / 2 - .08, hh * .45), (L / 2 - .3, .1, hh * .3))   # cladding panels
            e += L
        # the gate towers
        tc = side * (gw + 4.0)
        rk.box(g, "ru_concrete", (tc, n, 15.0), (4.0, t / 2 + 2.0, 15.0))
        rk.box(g, "ru_concrete", (tc, n, 30.6), (4.4, t / 2 + 2.4, .6))
        for k in range(4):                                        # vertical slots
            rk.box(gd, "ru_glow" if k == 1 else "ru_metal", (tc + (k - 1.5) * 1.6, n - t / 2 - 2.02, 18.0), (.18, .05, 7.0))
        rk.banner(gd, (tc, n - t / 2 - 2.2, 27.0), 3.4, 11.0, 0.0, 80 + side)
        rk.banner(gd, (tc, n + t / 2 + 2.2, 27.0), 3.4, 11.0, math.pi, 82 + side)
    # the arch over the opening: stepped infill above an arch ring (radius gw, springing at 5 m)
    spring = W["gate_h"] - gw
    k = 24
    for i in range(k):
        e0 = -gw + 2 * gw * i / k; e1 = e0 + 2 * gw / k
        em = (e0 + e1) / 2
        zc = spring + math.sqrt(max(gw * gw - em * em, 0))
        rk.box(g, "ru_concrete", (em, n, (zc + H) / 2), ((e1 - e0) / 2 + .01, t / 2, (H - zc) / 2))
    arc = [(gw * math.cos(math.pi * i / 32), n - t / 2 - .3, spring + gw * math.sin(math.pi * i / 32)) for i in range(33)]
    for dn in (0.0, t + .6):
        rk.tube(g, "ru_concrete", [(p[0], p[1] + dn, p[2]) for p in arc], .6, 8, smooth=False)
    # the gate leaves: one torn off and lying in the court, one hanging open
    rk.box(g, "ru_metal", (-3.0, n + 11.0, .9), (gw * .5, .35, 7.0), R=Matrix.Rotation(.25, 3, 'Z') @ Matrix.Rotation(-math.pi / 2 + .09, 3, 'X'))
    hinge = Vector((gw, n + t / 2, 0))
    R = Matrix.Rotation(math.radians(-70), 3, 'Z')
    rk.box(g, "ru_metal", tuple(hinge + R @ Vector((-gw * .5, .35, 7.0))), (gw * .5, .3, 7.0), R=R)
    # the court: cracked asphalt, buildings on both flanks, cover
    C = P.COURT
    ground_slab(g, "ru_asphalt", -C["half"], C["half"], C["n0"], C["n1"], .03)
    for side in (-1, 1):
        nn = C["n0"] + 2
        i = 0
        while nn < C["n1"] - 4:
            L = rnd.uniform(16, 22)
            rk.tower(g, gd, (side * (C["half"] + 10), nn + L / 2), 18, L, rnd.randint(4, 9), yaw=math.pi / 2, seed=120 + i * 2 + (side > 0),
                     style="concrete" if i % 2 else "panel", top=(.35, 1.0), holes=2)
            nn += L + 2
            i += 1
    cover = [(-14, -186, .3), (12, -183, -.4), (-22, -170, 1.4), (20, -168, 1.6), (-6, -160, .1), (8, -155, -.2),
             (-26, -150, 1.5), (25, -152, 1.7)]
    for i, (e, nn, y) in enumerate(cover):
        jersey(g, (e, nn, 0), y, 3.2)
        jersey(g, (e + math.cos(y) * 3.3, nn + math.sin(y) * 3.3, 0), y + rnd.uniform(-.15, .15), 3.2)
    for i, (e, nn) in enumerate(((0, -172), (-28, -186), (27, -184), (-10, -146), (14, -142))):
        rk.heap(g, (e, nn, 0), rnd.uniform(3, 5), rnd.uniform(1.2, 2.4), 140 + i)
    for i, (e, nn) in enumerate(((-17, -178), (17, -176), (0, -150))):
        hedgehog(g, (e, nn, 0), 150 + i)
    # a toppled column across the court
    rk.tube(g, "ru_concrete", [(-24, -163, 1.0), (-8, -158, 1.0)], 1.0, 12, smooth=True)
    rk.chunks(gd, (0, -170), 26, 70, 160)
    fire(gd, (16, -160, 0), 161)
    void_growth(gd, (-30, -194, 0), 3.0, 162)
    void_growth(gd, (31, -144, 0), 2.6, 163)
    void_growth(gd, (-gw - 1, n + t / 2 + .5, 8.0), 2.0, 164, up=(0, 1, .3))


def zone_boulevard(G):
    g, gd = G["boulevard"]
    B = P.BOULEVARD
    n0, n1, road, walk, lots = B["n0"], B["n1"], B["road"], B["walk"], B["lots"]
    rnd = random.Random(31)
    ground_slab(g, "ru_asphalt", -road, road, n0, n1 + 6, .03)
    for side in (-1, 1):
        x0, x1 = sorted((side * road, side * walk))
        ground_slab(g, "ru_stone", x0, x1, n0, n1, .18)
        # tall towers along the lots
        nn = n0 + 1
        i = 0
        while nn < n1 - 6:
            L = rnd.uniform(18, 28)
            depth = lots - walk - 2
            rk.tower(g, gd, (side * (walk + 1 + depth / 2), nn + L / 2), depth, L, rnd.randint(8, 14), yaw=0.0,
                     seed=300 + i * 2 + (side > 0), style="panel" if (i + (side > 0)) % 2 else "concrete", top=(.45, 1.0), holes=3)
            # the alley between lots, choked with rubble
            rk.heap(g, (side * (walk + 6), nn + L + 2.0, 0), 4.5, 3.0, 320 + i + (side > 0) * 20, ry=3.0)
            nn += L + 4
            i += 1
        for k in range(6):
            lamp_post(g, gd, (side * (road + .8), n0 + 8 + k * 16, .18), math.pi if side > 0 else 0.0, 330 + k + (side > 0) * 10, broken=k % 3 == 1)
    # the overpass at N -96: the west half spans the road and ends in a break; the east half lies across the road
    nO, zO = B["overpass_n"], B["overpass_z"]
    rk.path_deck(g, "ru_asphalt", "ru_concrete", [(-70, nO, zO), (-3, nO, zO)], 12, 1.3, end_mat="ru_fracture")
    rk.path_deck(g, "ru_asphalt", "ru_concrete", [(14, nO, zO), (70, nO, zO)], 12, 1.3, end_mat="ru_fracture")
    rk.path_deck(g, "ru_asphalt", "ru_concrete", [(-1.0, nO + .6, .6), (13.2, nO + .3, zO - .7)], 11.5, 1.1, end_mat="ru_fracture")
    for e in (-34, -20, 20, 34):
        rk.box(g, "ru_concrete", (e, nO, (zO - 1.3) / 2), (1.0, 2.2, (zO - 1.3) / 2))
    for side in (-1, 1):
        rk.wall_path(g, "ru_concrete", [(-70, nO + side * 5.8, zO), (-3, nO + side * 5.8, zO)], .35, 1.0, rnd=rnd, broken=.3)
    for k in range(16):
        s = Vector((-3 + rnd.uniform(-.2, .3), nO + rnd.uniform(-5.5, 5.5), zO - rnd.uniform(.2, 1.1)))
        L = rnd.uniform(.6, 2.5)
        rk.tube(gd, "ru_metal", [tuple(s), tuple(s + Vector((L * .6, 0, -L * .3))), tuple(s + Vector((L, 0, -L * .8)))], .02, 5, cap=False)
    rk.heap(g, (5, nO - 3, 0), 6, 2.0, 340)
    # cover down the road
    for i, (e, nn, y) in enumerate(((-6, -128, .2), (5, -120, -.3), (-8, -110, 1.3), (7, -78, 1.5), (-4, -66, .1), (9, -58, .4))):
        jersey(g, (e, nn, 0), y)
    rk.chunks(gd, (0, -100), 20, 60, 341)
    void_growth(gd, (-15, -74, .18), 2.4, 342)
    void_growth(gd, (16, -126, .18), 2.0, 343)
    fire(gd, (-9, -88, 0), 344)


def zone_ring(G):
    """Concord Ring: the plaza, its sunken circle and broken monument, the towers round it"""
    g, gd = G["ring"]
    R = P.PLAZA
    rnd = random.Random(41)
    sunk = R["sunk"]
    rk.annulus(g, "ru_stone", (0, 0), R["inner"] + 3.0, R["r"], -.2, .04, n=96)
    for k in range(3):                                            # three steps down
        r0 = R["inner"] + k * 1.0
        rk.annulus(g, "ru_stone", (0, 0), r0, r0 + 1.0, -sunk - .2, -sunk + (k + 1) * sunk / 3, n=96)
    rk.cyl(g, "ru_stone", (0, 0), R["inner"], -sunk - .3, -sunk, n=96, smooth=False)
    rk.annulus(g, "ru_asphalt", (0, 0), R["r"], R["ring_in"] + 2, -.2, .02, n=96)
    # the boulevard joins from the south
    ground_slab(g, "ru_asphalt", -P.BOULEVARD["walk"], P.BOULEVARD["walk"], P.BOULEVARD["n1"], -R["r"] + 1, .03)
    # the monument: an octagonal plinth, the snapped obelisk, the great ring tilted and broken, its piece fallen
    oct_ = [(5.0 * math.cos(TAU * i / 8 + math.pi / 8), 5.0 * math.sin(TAU * i / 8 + math.pi / 8)) for i in range(8)]
    rk.prism(g, "ru_concrete", oct_, -sunk, 2.6)
    rk.prism(g, "ru_stone", [(x * .8, y * .8) for x, y in oct_], 2.6, 3.3)
    rk.box(g, "ru_concrete", (0, 0, 7.0), (1.0, 1.0, 3.8), .2, top_mat="ru_fracture", offsets=[(0, 0, 0)] * 4 + [(0, 0, -.5), (0, 0, .4), (0, 0, -.2), (0, 0, .3)])
    ring_c = Vector((0, 0, 9.5))
    Rt = Matrix.Rotation(.35, 3, 'X') @ Matrix.Rotation(.2, 3, 'Y')
    arc = [ring_c + Rt @ Vector((7.0 * math.cos(a), 7.0 * math.sin(a), 0)) for a in [math.radians(40 + 260 * i / 40) for i in range(41)]]
    rk.tube(g, "ru_metal", [tuple(p) for p in arc], .55, 10, smooth=True)
    for p in arc[::5]:
        rk.tube(gd, "ru_glow", [tuple(p + Vector((0, 0, .5))), tuple(p + Vector((0, 0, .62)))], .2, 6)
    fall = [Vector((9 + 6.5 * math.cos(a), -6 + 6.5 * math.sin(a), .55)) for a in [math.radians(200 + 80 * i / 14) for i in range(15)]]
    rk.tube(g, "ru_metal", [tuple(p) for p in fall], .55, 10, smooth=True)
    void_growth(gd, (0, 0, 3.3), 3.6, 410)
    # planters and benches round the sunken circle
    for i in range(10):
        a = TAU * i / 10 + .1
        c = (math.cos(a) * 28, math.sin(a) * 28)
        if abs(math.degrees(a) % 360 - 270) < 14 or math.degrees(a) % 360 < 12 or math.degrees(a) % 360 > 348:
            continue
        rk.cyl(g, "ru_concrete", c, 1.6, .0, .8, n=20, cap_mat="ru_rubble")
        if i % 3 == 0:
            rk.tube(g, "ru_metal", [(c[0], c[1], .8), (c[0] + .3, c[1] + .2, 3.0), (c[0] - .2, c[1] + .5, 4.5)], .12, 6, r_end=.04)
    for i in range(8):
        lamp_post(g, gd, (math.cos(TAU * i / 8 + .2) * 35, math.sin(TAU * i / 8 + .2) * 35, .04), TAU * i / 8 + .2 + math.pi, 420 + i, broken=i % 2 == 1)
    # cover in the open: heaps and barriers
    for i, (a, r) in enumerate(((60, 24), (120, 30), (200, 26), (240, 31), (300, 22), (330, 30), (20, 31), (150, 22))):
        p = (math.cos(math.radians(a)) * r, math.sin(math.radians(a)) * r)
        if i % 2:
            rk.heap(g, (p[0], p[1], 0), rnd.uniform(2.5, 4), rnd.uniform(1.1, 1.8), 430 + i)
        else:
            jersey(g, (p[0], p[1], .04), math.radians(a) + math.pi / 2, 3.2)
            jersey(g, (p[0] + math.cos(math.radians(a) + math.pi / 2) * 3.3, p[1] + math.sin(math.radians(a) + math.pi / 2) * 3.3, .04), math.radians(a) + math.pi / 2 + .2, 3.2)
    # the towers round the ring (gaps south for the boulevard and east for the ramp; the north and west breaches
    # are where the Altered come from: rubble slopes between the towers)
    angles = [22, 47, 72, 97, 122, 147, 172, 197, 222, 247, 293, 318, 338]
    for i, a in enumerate(angles):
        r = 58 + rnd.uniform(-2, 2)
        c = (math.cos(math.radians(a)) * r, math.sin(math.radians(a)) * r)
        rk.tower(g, gd, c, rnd.uniform(16, 20), 22, rnd.randint(7, 15), yaw=math.radians(a) + math.pi / 2, seed=450 + i,
                 style="panel" if i % 2 else "concrete", top=(.4, 1.0), holes=3)
    for i, a in enumerate((85, 110, 160, 185, 210)):
        p = (math.cos(math.radians(a)) * 47, math.sin(math.radians(a)) * 47)
        rk.heap(g, (p[0], p[1], 0), 6.5, 4.0, 480 + i, ry=4.5)
    rk.chunks(gd, (0, 0), 34, 90, 490)
    for i, a in enumerate((35, 135, 225, 315)):
        p = (math.cos(math.radians(a)) * 40, math.sin(math.radians(a)) * 40, 0)
        void_growth(gd, p, 2.8, 491 + i)
    fire(gd, (-20, 12, 0), 495)
    fire(gd, (14, -24, 0), 496)


def zone_terraces(G):
    """the ramp up the east side and the elevated deck loop (east leg north, north leg west)"""
    g, gd = G["terraces"]
    Rm, T = P.RAMP, P.TERRACE
    z = T["z"]
    rnd = random.Random(51)
    # ramp: it tops out AT the deck's inner edge (it used to run on under the deck to the deck's middle: the last
    # five metres were a wall, which only the old simplified collision let anyone through)
    top_e = T["east_e"] - T["w"] / 2 + .4
    rk.path_deck(g, "ru_asphalt", "ru_concrete", [(Rm["e0"] - 2, 0, .02), (top_e, 0, z)], Rm["half"] * 2, .8)
    for side in (-1, 1):
        rk.wall_path(g, "ru_concrete", [(Rm["e0"] + 2, side * (Rm["half"] - .2), 0), (top_e - .6, side * (Rm["half"] - .2), z - .8)], .3, 1.1, rnd=rnd)
    for e in (54, 63):
        zz = (e - Rm["e0"] + 2) / (top_e - Rm["e0"] + 2) * z
        rk.box(g, "ru_concrete", (e, 0, (zz - .8) / 2), (.9, Rm["half"] - 1, (zz - .8) / 2))
    # the deck loop
    E, Nn, w = T["east_e"], T["north_n"], T["w"]
    path = [(E, T["n0"], z), (E, Nn, z), (T["west_e"], Nn, z)]
    rk.path_deck(g, "ru_stone", "ru_concrete", path, w, .9)
    # balustrades: inner (left of travel) and outer (right), with openings for the ramp and the bridge
    inner = rk.offset_path(path, w / 2 - .2); outer = rk.offset_path(path, -(w / 2 - .2))

    def skip_inner(i, t):
        if i == 0:
            nn = T["n0"] + (Nn - T["n0"]) * t
            return abs(nn) < Rm["half"] + .5
        return False

    def skip_outer(i, t):
        if i == 1:
            ee = E + (T["west_e"] - E) * t
            return abs(ee - P.BRIDGE["e"]) < P.BRIDGE["half"] + .5
        return False
    rk.wall_path(g, "ru_concrete", inner, .3, 1.05, top_mat="ru_metal", skip=skip_inner, rnd=rnd, broken=.25)
    rk.wall_path(g, "ru_concrete", outer, .3, 1.05, top_mat="ru_metal", skip=skip_outer, rnd=rnd, broken=.25)
    # piers under the deck and girders
    for leg in range(2):
        a, b = Vector(path[leg]), Vector(path[leg + 1])
        L = (b - a).length
        for k in range(int(L / 13) + 1):
            p = a.lerp(b, k * 13 / L)
            rk.box(g, "ru_concrete", (p.x, p.y, (z - .9) / 2), (.8, .8, (z - .9) / 2))
            for s in (-1, 1):
                o = Vector((-(b - a).y, (b - a).x, 0)).normalized() * s * (w / 2 - 1.5)
                rk.box(g, "ru_concrete", (p.x + o.x, p.y + o.y, (z - .9) / 2), (.6, .6, (z - .9) / 2))
    # towers on the outer side, their upper floors flanking the deck
    for i, nn in enumerate(range(-6, 112, 24)):
        rk.tower(g, gd, (E + w / 2 + 14, nn + 10), 20, 20, rnd.randint(9, 15), yaw=math.pi / 2, seed=520 + i,
                 style="panel" if i % 2 else "concrete", top=(.55, 1.0), holes=2)
    for i, ee in enumerate(range(26, 92, 24)):
        rk.tower(g, gd, (ee, Nn + w / 2 + 14), 20, 20, rnd.randint(9, 15), yaw=0.0, seed=540 + i,
                 style="concrete" if i % 2 else "panel", top=(.55, 1.0), holes=2)
    # the city below, inside the loop: low ruins and rubble
    for i in range(8):
        c = (rnd.uniform(52, 66), rnd.uniform(-30, 100))
        rk.tower(g, gd, c, rnd.uniform(10, 14), rnd.uniform(10, 16), rnd.randint(2, 4), yaw=rnd.uniform(0, TAU), seed=560 + i,
                 style="concrete", top=(.3, 1.0), holes=1, rebar=False)
    for i in range(6):
        rk.heap(g, (rnd.uniform(20, 70), rnd.uniform(60, 100), 0), rnd.uniform(5, 9), rnd.uniform(2, 4), 580 + i)
    # cover on the deck
    for i, (e, n_) in enumerate(((E - 3, 20), (E + 3, 36), (E - 2, 58), (E + 3, 80), (60, Nn - 2), (40, Nn + 3), (22, Nn - 3))):
        if i % 3 == 2:
            hedgehog(g, (e, n_, z), 590 + i)
        else:
            jersey(g, (e, n_, z), math.pi / 2 if i < 4 else 0.0, 3.2)
    rk.chunks(gd, (E, 50), 6, 30, 595, z=z)
    for i, (e, n_) in enumerate(((E + 6, 10), (E - 6, 70), (50, Nn + 6), (10, Nn - 6))):
        void_growth(gd, (e, n_, z), 2.4, 600 + i)
    for i, n_ in enumerate((0, 40, 80)):
        rk.banner(gd, (E + w / 2 + 4.1, n_ + 10, z + 12), 3.0, 9.0, math.pi / 2, 610 + i)


def zone_crown(G):
    """the Crown Bridge and the Crown: the round platform, the emitter and its beam"""
    g, gd = G["crown"]
    Br, C = P.BRIDGE, P.CROWN
    z = C["z"]
    cx, cy = C["c"]
    rnd = random.Random(61)
    # the bridge: deck on two arches, balustrades with lamp posts and banners
    rk.path_deck(g, "ru_stone", "ru_concrete", [(Br["e"], Br["n0"] - 1, z), (Br["e"], Br["n1"] + 2, z)], Br["half"] * 2, 1.0)
    for side in (-1, 1):
        rk.wall_path(g, "ru_concrete", [(side * (Br["half"] - .2), Br["n0"], z), (side * (Br["half"] - .2), Br["n1"], z)], .35, 1.1, top_mat="ru_metal")
        for k, n_ in enumerate((126, 140, 154)):
            lamp_post(g, gd, (side * (Br["half"] - .2), n_, z + 1.1), math.pi if side > 0 else 0.0, 620 + k + (side > 0) * 5)
    for n_ in (131, 151):
        arc = [(Br["e"] - Br["half"] + .5, n_ + 9 * math.cos(math.pi * i / 16), (z - 1) * math.sin(math.pi * i / 16)) for i in range(17)]
        for e in (-Br["half"] + 1, Br["half"] - 1):
            rk.tube(g, "ru_concrete", [(e, p[1], p[2]) for p in arc], .9, 8, smooth=False)
    for e in (-Br["half"] + 1, Br["half"] - 1):
        for n_ in (122, 140, 160):
            rk.box(g, "ru_concrete", (e, n_, (z - 1) / 2), (1.2, 1.2, (z - 1) / 2))
    # the platform: pedestal down to the ground with buttress fins, a dark metal rim with a glow channel,
    # stone rings inlaid between radial seams
    r = C["r"]
    rk.cyl(g, "ru_concrete", (cx, cy), r + 1.5, -1.0, z - 1.2, n=96, r1=r, smooth=True)
    rk.annulus(g, "ru_metal", (cx, cy), r - 2.2, r, z - 1.2, z + .1, n=128)
    rk.annulus(gd, "ru_glow", (cx, cy), r - 1.45, r - 1.15, z + .1, z + .14, n=128, inner=False, outer=False)
    for k, (r0, r1) in enumerate(((0, 9.5), (9.5, 18), (18, 26), (26, r - 2.2))):
        if r0 == 0:
            rk.cyl(g, "ru_stone", (cx, cy), r1, z - 1.2, z, n=64, smooth=False)
        else:
            rk.annulus(g, "ru_stone", (cx, cy), r0 + .12, r1, z - 1.2, z, n=96)
            rk.annulus(gd, "ru_glow" if k == 2 else "ru_metal", (cx, cy), r0 - .12, r0 + .12, z - .1, z + .02, n=96, inner=False, outer=False)
    for i in range(24):                                          # radial seams of dark metal
        a = TAU * i / 24
        p0 = (cx + math.cos(a) * 9.6, cy + math.sin(a) * 9.6); p1 = (cx + math.cos(a) * (r - 2.3), cy + math.sin(a) * (r - 2.3))
        mid = ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2, z + .01)
        rk.box(gd, "ru_metal", mid, ((r - 11.9) / 2, .07, .02), a)
    for i in range(16):                                          # buttress fins round the pedestal
        a = TAU * i / 16 + .1
        p = (cx + math.cos(a) * (r + 1.2), cy + math.sin(a) * (r + 1.2))
        rk.box(g, "ru_concrete", (p[0], p[1], (z - 1.5) / 2), (2.0, .8, (z - 1.5) / 2), a, offsets=[(-1.5, 0, 0), (1.5, 0, 0), (1.5, 0, 0), (-1.5, 0, 0)] + [(0, 0, 0)] * 4)
    # the rim balustrade, broken in places, open to the bridge
    for i in range(72):
        a = TAU * i / 72
        if abs(math.degrees(a) - 270) < 12 or rnd.random() < .12:
            continue
        p = (cx + math.cos(a) * (r - .5), cy + math.sin(a) * (r - .5))
        hh = 1.1 if rnd.random() > .15 else rnd.uniform(.3, .8)
        rk.box(g, "ru_concrete", (p[0], p[1], z + hh / 2), (r * TAU / 72 / 2 + .02, .25, hh / 2), a + math.pi / 2, top_mat="ru_metal")
    # broken columns for cover
    for i, a in enumerate(C["column_angles"]):
        p = (cx + math.cos(math.radians(a)) * C["column_r"], cy + math.sin(math.radians(a)) * C["column_r"])
        hh = rnd.uniform(5, 13)
        rk.cyl(g, "ru_concrete", p, 1.3, z, z + hh, n=20, cap_mat="ru_fracture", smooth=True)
        rk.cyl(g, "ru_concrete", p, 1.7, z, z + .8, n=20, smooth=False)
        fallen = (p[0] + math.cos(math.radians(a) + 1.2) * 4.5, p[1] + math.sin(math.radians(a) + 1.2) * 4.5)
        rk.tube(g, "ru_concrete", [(fallen[0] - math.cos(math.radians(a)) * 2.5, fallen[1] - math.sin(math.radians(a)) * 2.5, z + 1.2),
                                (fallen[0] + math.cos(math.radians(a)) * 2.5, fallen[1] + math.sin(math.radians(a)) * 2.5, z + 1.2)], 1.2, 16, smooth=False)
    # pylon sockets (the conduits are actors standing on them)
    for p in P.PYLONS:
        rk.cyl(g, "ru_metal", (p[0], p[1]), 2.6, z, z + .35, n=24, smooth=False)
        rk.annulus(gd, "ru_glow", (p[0], p[1]), 2.2, 2.35, z + .35, z + .38, n=48, inner=False, outer=False)
    # the emitter: stepped rings, six claws leaning in, the crystal held between them, the beam
    rk.cyl(g, "ru_metal", (cx, cy), 9.0, z, z + .4, n=64, smooth=False)
    rk.cyl(g, "ru_stone", (cx, cy), 6.5, z + .4, z + 1.2, n=64, smooth=False)
    rk.annulus(gd, "ru_glow", (cx, cy), 5.0, 5.4, z + 1.2, z + 1.25, n=64, inner=False, outer=False)
    for i in range(6):
        a = TAU * i / 6 + .26
        base = Vector((cx + math.cos(a) * 5.6, cy + math.sin(a) * 5.6, z + 1.2))
        pts = [base + Vector((math.cos(a) * (.8 * math.sin(t * 2.2) - 2.6 * t * t), math.sin(a) * (.8 * math.sin(t * 2.2) - 2.6 * t * t), 10.5 * t))
               for t in [k / 10 for k in range(11)]]
        rk.tube(g, "ru_metal", [tuple(q) for q in pts], .75, 8, r_end=.12)
        rk.tube(gd, "ru_glow", [tuple(q + Vector((math.cos(a) * -.6, math.sin(a) * -.6, 0))) for q in pts[2:9]], .09, 5)
    crystal_c = Vector((cx, cy, z + 8.0))
    rk.crystal_cluster(gd, tuple(crystal_c - Vector((0, 0, 1.8))), 4.2, 640)
    rk.cyl(gd, "ru_beam", (cx, cy), 1.0, z + 1.2, 420.0, n=24, r1=1.4)
    light("beam", (cx, cy, z + 8.0), 4000)
    for i in range(8):
        a = TAU * i / 8
        light("rim", (cx + math.cos(a) * (r - 1.3), cy + math.sin(a) * (r - 1.3), z), 1400)
    rk.chunks(gd, (cx, cy), r - 4, 60, 650, size=(.2, .7), z=z)
    for i, a in enumerate((30, 150, 250, 330)):
        p = (cx + math.cos(math.radians(a)) * 35, cy + math.sin(math.radians(a)) * 35, z)
        void_growth(gd, p, 3.0, 660 + i)
    # the ground round the pedestal, far below: scorched rubble
    for i in range(10):
        a = TAU * i / 10 + .3
        rk.heap(g, (cx + math.cos(a) * (r + 9), cy + math.sin(a) * (r + 9), 0), rnd.uniform(5, 9), rnd.uniform(2, 5), 670 + i)


AMBIENCE = []


def ambience(kind, p, radius, volume=1.0, spores=False):
    AMBIENCE.append(dict(kind=kind, at=[round(p[1] * 100, 1), round(p[0] * 100, 1), round(p[2] * 100 + 80, 1)], radius=radius * 100.0,
                         volume=volume, spores=spores))


def zone_hive(G):
    """the Altered have made the city their base: grown barricades round every post they hold (cover for both sides),
    growth over the walls and floors with egg pods, the Choir's spires humming, cables of light slung over the streets"""
    PI = math.pi
    T = P.TERRACE
    z = T["z"]

    def growth(zone, c, r, seed, wall=None):
        rk.hive_growth(G[zone][0], G[zone][1], c, r, seed, wall)
        ambience("hive", c, 14, 0.8, spores=True)
        light("void", c, 700 + r * 120)

    def spire(zone, c, h, seed):
        rk.alien_spire(G[zone][0], G[zone][1], c, h, seed)
        ambience("hum", c, 30, 1.0)
        light("void", (c[0], c[1], c[2] + h * .9), 1600)

    # the approach: a forward post behind barricades, growth up the side ruins, a spire before the wall
    for i, (e, n, yaw) in enumerate(((-12, -249, PI), (11, -252, PI), (0, -262, PI + .1), (-21, -236, PI - .2))):
        rk.alien_barricade(G["approach"][0], (e, n, 0), yaw, 900 + i)
    growth("approach", (-25, -262, 0), 4.5, 910, wall=(1, 0))
    growth("approach", (26, -226, 0), 4.0, 911, wall=(-1, 0))
    spire("approach", (-19, -214, 0), 12.0, 912)
    for n in (-290, -270, -240):
        rk.cable(G["approach"][1], (-30, n, 11), (30, n + 6, 13), 2.5)
    # the gate court: the garrison's line
    for i, (e, n, yaw) in enumerate(((-14, -152, PI), (0, -150, PI), (15, -153, PI), (-27, -172, PI), (27, -170, PI), (-6, -182, PI + .3))):
        rk.alien_barricade(G["gate"][0], (e, n, 0), yaw, 920 + i)
    growth("gate", (-15, -194.5, 0), 4.0, 930, wall=(0, 1))
    growth("gate", (16, -194.5, 0), 3.5, 931, wall=(0, 1))
    spire("gate", (9, -141, 0), 13.0, 932)
    # the boulevard
    for i, (e, n, yaw) in enumerate(((-8, -88, PI), (8, -91, PI), (-6, -112, PI + .2), (7, -64, PI - .2))):
        rk.alien_barricade(G["boulevard"][0], (e, n, 0), yaw, 940 + i)
    growth("boulevard", (-16.5, -120, .18), 3.5, 950, wall=(1, 0))
    growth("boulevard", (16.5, -76, .18), 3.5, 951, wall=(-1, 0))
    for n in (-132, -116, -80, -62, -50):
        rk.cable(G["boulevard"][1], (-19, n, 14 + (n % 3)), (19, n + 4, 16), 3.0)
    # the ring: barricades round the plaza facing in, spires at the breaches, the monument overgrown
    for i, a in enumerate((20, 70, 110, 160, 200, 330)):
        ar = math.radians(a)
        rk.alien_barricade(G["ring"][0], (math.cos(ar) * 31, math.sin(ar) * 31, .04), ar + PI / 2, 960 + i)
    spire("ring", (-6.9, 39.4, 0), 15.0, 970)
    spire("ring", (-40.0, 0.0, 0), 13.0, 971)
    growth("ring", (0, 0, -P.PLAZA["sunk"]), 7.0, 972)
    growth("ring", (24, 26, 0), 3.0, 973)
    # the terraces
    for i, (e, n, yaw) in enumerate(((77, 30, PI), (83, 48, PI), (78, 70, PI), (82, 90, PI))):
        rk.alien_barricade(G["terraces"][0], (e, n, z), yaw, 980 + i)
    for i, (e, n) in enumerate(((60, 111), (42, 117), (25, 112))):
        rk.alien_barricade(G["terraces"][0], (e, n, z), -PI / 2, 990 + i)
    growth("terraces", (85.5, 60, z), 3.0, 995, wall=(-1, 0))
    growth("terraces", (50, 120.5, z), 3.0, 996, wall=(0, -1))
    spire("terraces", (84, 117, z), 10.0, 997)
    for n in (20, 55, 90):
        rk.cable(G["terraces"][1], (73, n, z + 9), (100, n + 5, z + 14), 2.0)
    # the crown: growth over the platform's rim and up its pedestal, two spires at the rim
    growth("crown", (25, 215, z), 3.0, 1000)
    growth("crown", (-28, 190, z), 3.0, 1001)
    growth("crown", (45, 200, 0), 6.0, 1002, wall=(1, 0))
    growth("crown", (-45, 205, 0), 6.0, 1003, wall=(-1, 0))
    spire("crown", (34.0, 213.0, z), 9.0, 1004)
    spire("crown", (-34.0, 214.0, z), 9.0, 1005)
    # the hive's voices far off, everywhere
    for p in ((0, -230, 0), (0, -100, 0), (0, 0, 0), (60, 80, 10), (0, 190, 10)):
        ambience("chorus", p, 160, 0.55)


def zone_backdrop(G):
    """the skyline round the route, the far spire and its broken orbital ring"""
    g = G["backdrop"][0]
    rnd = random.Random(71)
    route = P.ROUTE

    def near_route(x, y, m):
        for (a, b), (c, d) in zip(route, route[1:]):
            dx, dy = c - a, d - b
            t = max(0, min(1, ((x - a) * dx + (y - b) * dy) / (dx * dx + dy * dy)))
            if math.hypot(x - a - dx * t, y - b - dy * t) < m:
                return True
        return False
    count = 0
    tries = 0
    while count < 220 and tries < 20000:
        tries += 1
        x, y = rnd.uniform(-520, 520), rnd.uniform(-2560, 620)
        if near_route(x, y, 120) or math.hypot(x - P.SPIRE["c"][0], y - P.SPIRE["c"][1]) < 70:
            continue
        dist = min(math.hypot(x - a, y - b) for a, b in route)
        floors = int(rnd.uniform(10, 26) + dist / 25)
        rk.tower(g, g, (x, y), rnd.uniform(20, 34), rnd.uniform(20, 34), floors, yaw=rnd.uniform(0, TAU), seed=700 + count,
                 style=rnd.choice(("panel", "concrete")), top=(.4, 1.0), holes=2, rebar=False, heaps=False, detail=False, cell_target=6.0)
        count += 1
    # the low city between: broken blocks of two to four floors, cheap boxes with ragged tops
    k = 0
    tries = 0
    while k < 800 and tries < 30000:
        tries += 1
        x, y = rnd.uniform(-600, 600), rnd.uniform(-2650, 700)
        if near_route(x, y, 85):
            continue
        w, d_ = rnd.uniform(10, 26), rnd.uniform(10, 26)
        h = rnd.uniform(4, 14)
        off = [(0, 0, 0)] * 4 + [(0, 0, -rnd.uniform(0, h * .6)) for _ in range(4)]
        rk.box(g, rnd.choice(("ru_concrete", "ru_panel")), (x, y, h / 2), (w / 2, d_ / 2, h / 2), rnd.uniform(0, TAU), top_mat="ru_fracture", offsets=off)
        k += 1
    # the spire: a tapering octagonal shaft in tiers with fins, glowing seams, a broken crown of spikes
    sx, sy = P.SPIRE["c"]
    Hs = P.SPIRE["height"]
    tiers = 9
    for k in range(tiers):
        z0, z1 = Hs * k / tiers, Hs * (k + 1) / tiers
        r0 = 34 * (1 - .82 * k / tiers); r1 = 34 * (1 - .82 * (k + 1) / tiers)
        poly = [(sx + r0 * math.cos(TAU * i / 8 + math.pi / 8), sy + r0 * math.sin(TAU * i / 8 + math.pi / 8)) for i in range(8)]
        poly1 = [(sx + r1 * math.cos(TAU * i / 8 + math.pi / 8), sy + r1 * math.sin(TAU * i / 8 + math.pi / 8)) for i in range(8)]
        vs = [(x, y, z0) for x, y in poly] + [(x, y, z1 - 3) for x, y in poly1]
        g.add(vs, [(i, (i + 1) % 8, 8 + (i + 1) % 8, 8 + i) for i in range(8)], "ru_panel")
        rk.prism(g, "ru_metal", [(sx + (r1 + 2.5) * math.cos(TAU * i / 8 + math.pi / 8), sy + (r1 + 2.5) * math.sin(TAU * i / 8 + math.pi / 8)) for i in range(8)], z1 - 3, z1)
        rk.annulus(g, "ru_glow", (sx, sy), r1 + 2.5, r1 + 2.9, z1 - 1.8, z1 - 1.2, n=8, a0=math.pi / 8, inner=False)
        for i in range(8):                                        # fins
            a = TAU * i / 8
            rk.box(g, "ru_metal", (sx + math.cos(a) * (r0 * .92 + 4), sy + math.sin(a) * (r0 * .92 + 4), (z0 + z1) / 2), (4.5, .8, (z1 - z0) / 2 * .9), a)
    for i in range(7):
        a = TAU * i / 7
        base = Vector((sx + math.cos(a) * 6, sy + math.sin(a) * 6, Hs))
        h = rnd.uniform(25, 60) * (.5 if i % 3 == 0 else 1)
        rk.tube(g, "ru_metal", [tuple(base), tuple(base + Vector((math.cos(a) * 4, math.sin(a) * 4, h * .6))),
                                tuple(base + Vector((math.cos(a) * 2, math.sin(a) * 2, h)))], 2.2, 6, r_end=.2)
    # the broken orbital ring: truss arcs round the spire, tilted, with gaps and one arc fallen
    Rr = P.SPIRE["ring_r"]
    tilt = Matrix.Rotation(math.radians(14), 3, 'X') @ Matrix.Rotation(math.radians(-8), 3, 'Y')
    cz = Hs * .55
    for (a0, a1) in ((-20, 70), (95, 170), (190, 240), (262, 330)):
        pts = [Vector((sx, sy, cz)) + tilt @ Vector((Rr * math.cos(math.radians(a)), Rr * math.sin(math.radians(a)), 0))
               for a in [a0 + (a1 - a0) * i / 40 for i in range(41)]]
        for o in (Vector((0, 0, 4.5)), Vector((0, 0, -4.5))):
            rk.tube(g, "ru_metal", [tuple(p + tilt @ o) for p in pts], 2.2, 8)
        rk.tube(g, "ru_glow", [tuple(p) for p in pts], .8, 6)
        for p in pts[::2]:                                        # the truss struts
            rk.tube(g, "ru_metal", [tuple(p + tilt @ Vector((0, 0, 4.5))), tuple(p + tilt @ Vector((0, 0, -4.5)))], .9, 5)
    pts = [Vector((sx - 120, sy - 150, 30)) + Vector((70 * math.cos(math.radians(a)), 0, 70 * math.sin(math.radians(a)) * .5)) for a in range(200, 300, 4)]
    rk.tube(g, "ru_metal", [tuple(p) for p in pts], 2.2, 8)
    # a second, smaller ring higher up
    tilt2 = Matrix.Rotation(math.radians(-22), 3, 'X')
    for (a0, a1) in ((10, 150), (175, 320)):
        pts = [Vector((sx, sy, Hs * .82)) + tilt2 @ Vector((95 * math.cos(math.radians(a)), 95 * math.sin(math.radians(a)), 0))
               for a in [a0 + (a1 - a0) * i / 30 for i in range(31)]]
        rk.tube(g, "ru_metal", [tuple(p) for p in pts], 1.4, 8)
        rk.tube(g, "ru_glow", [tuple(p + Vector((0, 0, 1.6))) for p in pts], .5, 6)


def zone_blockers(G):
    """invisible walls along the route's edges, 9 m above whatever is walkable: an air jump and a clamber together
    reach nearly six (they were 4 m, which was enough before there was an air jump), and nothing beside them is taller"""
    g = G["blockers"][0]

    def wall(a, b, z0=-1.0, z1=14.0):
        a, b = Vector(a), Vector(b)
        d = b - a
        m = (a + b) / 2
        rk.box(g, "ru_block", (m.x, m.y, (z0 + z1) / 2), (d.length / 2 + .3, .3, (z1 - z0) / 2), math.atan2(d.y, d.x))
    A, Cc, B, R, Rm, T, Br, C = P.APPROACH, P.COURT, P.BOULEVARD, P.PLAZA, P.RAMP, P.TERRACE, P.BRIDGE, P.CROWN
    h = A["half"] + 1
    for s in (-1, 1):
        wall((s * h, A["n0"] - 2), (s * 10.0, A["n0"] - 2))            # (the causeway comes in between these)
        wall((s * h, A["n0"] - 2), (s * h, P.WALL["n"] - 3))
        wall((s * (Cc["half"] - 1), Cc["n0"]), (s * (Cc["half"] - 1), Cc["n1"]))
        wall((s * (Cc["half"] - 1), Cc["n1"]), (s * (B["walk"] + .5), Cc["n1"]))
        wall((s * (B["walk"] + .5), B["n0"]), (s * (B["walk"] + .5), -math.sqrt(R["ring_in"] ** 2 - B["walk"] ** 2) + 1))
    south.blockers(g)
    # the ring: a circle at the inner face of the towers, open south (boulevard) and east (ramp)
    seg = 48
    for i in range(seg):
        a0, a1 = TAU * i / seg, TAU * (i + 1) / seg
        am = math.degrees((a0 + a1) / 2)
        rr = R["ring_in"]
        if abs(am - 270) < math.degrees(math.asin((B["walk"] + .5) / rr)) or am < math.degrees(math.asin((Rm["half"] + .5) / rr)) or am > 360 - math.degrees(math.asin((Rm["half"] + .5) / rr)):
            continue
        wall((math.cos(a0) * rr, math.sin(a0) * rr), (math.cos(a1) * rr, math.sin(a1) * rr))
    # the ramp's sides, then both edges of the deck loop (the inner one open to the ramp, the outer to the bridge)
    for s in (-1, 1):
        wall((math.sqrt(R["ring_in"] ** 2 - Rm["half"] ** 2), s * (Rm["half"] + .4)), (T["east_e"] - T["w"] / 2, s * (Rm["half"] + .4)), -1, T["z"] + 9)
    E, Nn, w, z = T["east_e"], T["north_n"], T["w"], T["z"]
    zt = z + 9.0
    wall((E - w / 2 - .3, T["n0"]), (E - w / 2 - .3, -Rm["half"] - .4), z - 2, zt)
    wall((E - w / 2 - .3, Rm["half"] + .4), (E - w / 2 - .3, Nn - w / 2 - .3), z - 2, zt)
    wall((E - w / 2 - .3, Nn - w / 2 - .3), (T["west_e"] - .3, Nn - w / 2 - .3), z - 2, zt)
    wall((T["west_e"] - .3, Nn - w / 2 - .3), (T["west_e"] - .3, Nn + w / 2 + .3), z - 2, zt)
    wall((E + w / 2 + .3, T["n0"] - .3), (E + w / 2 + .3, Nn + w / 2 + .3), z - 2, zt)
    wall((E + w / 2 + .3, Nn + w / 2 + .3), (Br["e"] + Br["half"] + .4, Nn + w / 2 + .3), z - 2, zt)
    wall((E - w / 2 - .3, T["n0"] - .3), (E + w / 2 + .3, T["n0"] - .3), z - 2, zt)
    wall((T["west_e"] - .3, Nn + w / 2 + .3), (Br["e"] - Br["half"] - .4, Nn + w / 2 + .3), z - 2, zt)
    for s in (-1, 1):
        wall((Br["e"] + s * (Br["half"] + .4), Nn + w / 2 + .3), (Br["e"] + s * (Br["half"] + .4), C["c"][1] - math.sqrt((C["r"] + .4) ** 2 - (Br["half"] + .4) ** 2)), z - 2, zt)
    # the crown's rim, open to the bridge
    cx, cy = C["c"]
    for i in range(seg):
        a0, a1 = TAU * i / seg, TAU * (i + 1) / seg
        am = math.degrees((a0 + a1) / 2)
        if abs(am - 270) < math.degrees(math.asin((Br["half"] + .4) / (C["r"] + .4))):
            continue
        rr = C["r"] + .4
        wall((cx + math.cos(a0) * rr, cy + math.sin(a0) * rr), (cx + math.cos(a1) * rr, cy + math.sin(a1) * rr), z - 2, z + 9)


# ------------------------------------------------------------------ actor pieces
def kit_conduit():
    """the Colossus's shield conduit: a stone foot, a spiked cage of dark metal and a glowing core (origin at its foot)"""
    g = rk.Geo("MRK_conduit")
    rk.cyl(g, "ru_stone", (0, 0), 1.6, 0.0, .6, n=8, r1=1.3, smooth=False)
    rk.cyl(g, "ru_metal", (0, 0), 1.0, .6, 1.4, n=8, r1=.8, smooth=False)
    for i in range(5):
        a = TAU * i / 5
        base = Vector((math.cos(a) * .95, math.sin(a) * .95, 1.0))
        pts = [base + Vector((math.cos(a) * .6 * math.sin(t * 3), math.sin(a) * .6 * math.sin(t * 3), 5.2 * t)) for t in [k / 8 for k in range(9)]]
        rk.tube(g, "ru_metal", [tuple(p) for p in pts], .22, 6, r_end=.04)
    rk.crystal_cluster(g, (0, 0, 1.4), 3.4, 777)
    rk.cyl(g, "ru_glow", (0, 0), .35, 1.4, 4.4, n=8, smooth=False)
    o = rk.build(g)
    return o


def kit_barrier():
    """an energy barrier panel 1 x 1 m: x across (-0.5..0.5), z up (0..1), a thin glow sheet with a frame"""
    g = rk.Geo("MRK_barrier")
    vs = [(-.5, 0, 0), (.5, 0, 0), (.5, 0, 1), (-.5, 0, 1)]
    g.add(vs, [(0, 1, 2, 3), (3, 2, 1, 0)], "ru_glow", uvs=[[(0, 0), (1, 0), (1, 1), (0, 1)], [(0, 1), (1, 1), (1, 0), (0, 0)]])
    o = rk.build(g)
    return o


# ------------------------------------------------------------------ main
class Helpers:
    light = staticmethod(light)
    void_growth = staticmethod(void_growth)
    fire = staticmethod(fire)
    jersey = staticmethod(jersey)
    hedgehog = staticmethod(hedgehog)
    lamp_post = staticmethod(lamp_post)
    ground_slab = staticmethod(ground_slab)
    ambience = staticmethod(lambda *a, **k: ambience(*a, **k))


ZONES = dict(ground=zone_ground, approach=zone_approach, gate=zone_gate, boulevard=zone_boulevard, ring=zone_ring,
             terraces=zone_terraces, crown=zone_crown, backdrop=zone_backdrop, blockers=zone_blockers, hive=zone_hive)
for _name, _fn in south.ZONES.items():
    ZONES[_name] = (lambda fn: lambda G: fn(G, Helpers))(_fn)
ZONES["story"] = lambda G: story.zone_story(G, Helpers)          # what was left in the streets, district by district
ZONES["flora"] = lambda G: flora.zone_flora(G, Helpers)          # (last: it grows on what the others built)
# Each district's architecture (citykit.STYLES): what its buildings were before they were ruined.
ZONE_STYLES = dict(verge=("industrial", "industrial", "office"), stacks=("resi",), galleria=("mixed", "office"),
                   deepline=("mixed",), sluice=("industrial", "lab", "lab"), causeway=("mixed", "resi", "industrial"),
                   approach=("mixed", "resi", "mixed"), gate=("civic", "mixed"), boulevard=("office", "civic", "office"),
                   ring=("civic", "office", "civic"), terraces=("office", "civic"), crown=("civic",))
# what never collides (drawn only), and where the towers stand beside a raised deck
NO_COLLISION = ("backdrop",)
HIGH_DECKS = ("ring", "terraces", "crown")


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    flags = {a.split('=')[0]: (a.split('=', 1)[1] if '=' in a else True) for a in argv}
    want = flags.get('--zones', '').split(',') if isinstance(flags.get('--zones'), str) else list(ZONES)
    bl.reset()
    G = {z: (rk.Geo(f"MR_{z}"), rk.Geo(f"MR_{z}_detail")) for z in ZONES}
    for z in want:
        log("zone", z)
        rk.COL_TOP = 34.0 if z in HIGH_DECKS else 16.0
        rk.CITY = dict(far=True) if z == "backdrop" else (dict(styles=ZONE_STYLES[z]) if z in ZONE_STYLES else None)
        rk.ZONE = z
        ZONES[z](G)
        rk.CITY = None
    for z, (g, gd) in G.items():
        for x in (g, gd):
            if len(x):
                rk.build(x)
                log(f"  {x.name}: {len(x)} faces")
        # what collides, as its own exact mesh (the blockers are their own collision; the backdrop has none)
        if len(g) and z not in NO_COLLISION and z != "blockers":
            col = rk.collision_of(g)
            if len(col):
                rk.build(col)
                log(f"  {col.name}: {len(col)} faces")
    kit_conduit()
    kit_barrier()
    if '--save' in flags:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(flags['--save']))
    if not isinstance(flags.get('--zones'), str):
        with open(ART, 'w', encoding='utf-8') as f:
            json.dump(dict(lights=LIGHTS, ambience=AMBIENCE), f, indent=1)
        log("wrote", ART, len(LIGHTS), "lights")
    if '--noexport' not in flags:
        bl.export("meridian.glb")


main()
