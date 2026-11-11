"""Meridian's buildings: COMPLETE buildings that were then ruined (docs/operation/ART_DIRECTION.md: never a bare
skeleton, a construction site or a grey box).

building(g, gd, c, w, d, floors, ...) makes one: finished outer walls in the district's cladding with windows (frames,
glass whole / broken / gone), balconies, trim at every floor, corner piers, a ground storey of shop fronts, doors,
canopies and signs, floors and ceilings inside, a core and partitions so nobody sees through it, a roof with a parapet
and its plant (condensers, ducts, tanks, masts, a stair head). Then the damage: a field takes the top away raggedly
and bites holes in the sides; where a wall is gone and the floor behind it is not, the broken edges show fracture and
rebar and what was in the room (a bed, a sofa, desks, racks) is still there to be seen; the rubble lies at its foot.

Styles (one architecture per district): resi (ceramic panels, balconies, condensers), office (curtain wall, sun
shades), civic (sandstone, pilasters, tall windows, cornices), industrial (corrugated sheds, strip windows, roller
doors), mixed (housing over shops), lab (composite, few windows, roof tanks).
lod: 0 beside the route, 1 behind the first row (no frames, furniture or small plant), 2 the far skyline
(far_building: textured blocks with setbacks and a broken crown).

g = structure (collides up to col_top above the foot), gd = detail (never collides).
"""
import math
import random
from mathutils import Vector, Matrix, noise
import ruinkit as rk

TAU = 2 * math.pi
PI = math.pi

STYLES = {
    "resi": dict(bay=3.4, floor=3.2, ground=4.0, wall="ru_ceramic", trim="ru_concrete", frame="ru_metal", inner="ru_plaster",
                 floor_mat="ru_tile", win=(1.7, 1.45, .95), balcony=.42, shop=.25, plant="resi"),
    "mixed": dict(bay=3.6, floor=3.3, ground=4.8, wall="ru_ceramic", trim="ru_composite", frame="ru_metal", inner="ru_plaster",
                  floor_mat="ru_tile", win=(1.9, 1.5, .9), balcony=.25, shop=.8, plant="resi"),
    "office": dict(bay=3.6, floor=3.9, ground=5.2, wall="ru_composite", trim="ru_metal", frame="ru_brass", inner="ru_plaster",
                   floor_mat="ru_tile", curtain=True, shop=.55, plant="plant"),
    "civic": dict(bay=4.2, floor=4.4, ground=6.0, wall="ru_sandstone", trim="ru_sandstone", frame="ru_brass", inner="ru_plaster",
                  floor_mat="ru_stone", win=(1.4, 2.7, .85), pilaster=True, shop=0.0, plant="civic"),
    "industrial": dict(bay=5.0, floor=4.6, ground=6.2, wall="ru_corrugate", trim="ru_metal", frame="ru_metal", inner="ru_concrete",
                       floor_mat="ru_concrete", win=(3.6, .9, 2.7), blank=.55, doors=.4, shop=0.0, plant="shed"),
    "lab": dict(bay=4.0, floor=4.2, ground=5.0, wall="ru_composite", trim="ru_metal", frame="ru_metal", inner="ru_plaster",
                floor_mat="ru_tile", win=(2.4, 1.2, 1.3), blank=.35, shop=0.0, plant="tanks"),
}
SIGNS = ("ru_holo_cyan", "ru_holo_magenta", "ru_sign_amber")
# Where a plant can climb: (zone, foot on the ground at a wall, the wall's outward normal, how high the wall still
# stands there, how wide). Filled by building() for the buildings beside the route; meridian_flora.py grows from them.
ANCHORS = []
# Every building beside the route: (zone, centre, w, d, yaw, how high it still stands, foot z). The plants take some
# of them whole.
BUILDINGS = []
# Every building a player can walk into: (zone, the door's foot, the way in (unit E, N), centre, w, d, yaw).
ENTERABLE = []
SIDES = ((Vector((0, -1)), Vector((1, 0)), 0.0), (Vector((1, 0)), Vector((0, 1)), PI / 2),
         (Vector((0, 1)), Vector((-1, 0)), PI), (Vector((-1, 0)), Vector((0, -1)), 1.5 * PI))


def building(g, gd, c, w, d, floors, yaw=0.0, seed=0, style="resi", damage=.5, base_z=0.0, heaps=True, lod=0,
             col_top=None, intact_below=0, front=None):
    """One building centred at c (x, y), w along its local x, d along local y, turned by yaw. damage 0 = whole,
    1 = little left. Returns its height.

    front = (E, N) toward the route: this building is part of the route's edge. A player walks in through its street
    door (and its shop windows); its other three sides are blind and whole for the first three storeys, its floors
    whole that far up, no balcony below the fourth: nothing to climb to, no way out the back. The ground floor has a
    floor, what stood in its rooms, and a fall of rubble against the back wall."""
    S = STYLES[style]
    rnd = random.Random(seed * 7919 + 13)
    first_face = len(g.F)
    cy, sy = math.cos(yaw), math.sin(yaw)
    fs = None
    if front is not None:
        fs = max(range(4), key=lambda q: (SIDES[q][0].x * cy - SIDES[q][0].y * sy) * front[0] + (SIDES[q][0].x * sy + SIDES[q][0].y * cy) * front[1])
        intact_below = max(intact_below, 3)
        floors = max(floors, 4)

    def P(x, y, z):
        return (c[0] + x * cy - y * sy, c[1] + x * sy + y * cy, base_z + z)

    def box(target, mat, x, y, z, hx, hy, hz, ang=0.0, **kw):
        rk.box(target, mat, P(x, y, z), (hx, hy, hz), yaw + ang, **kw)

    levels = [0.0]
    for k in range(floors):
        levels.append(levels[-1] + (S["ground"] if k == 0 and base_z < .5 else S["floor"]))
    H = levels[-1]
    nbx, nby = max(2, round(w / S["bay"])), max(2, round(d / S["bay"]))
    bw = (w / nbx, d / nby)
    xs = [-w / 2 + w * i / nbx for i in range(nbx + 1)]
    ys = [-d / 2 + d * j / nby for j in range(nby + 1)]
    half = (d / 2, w / 2, d / 2, w / 2)
    length = (w, d, w, d)
    count = (nbx, nby, nbx, nby)

    # ---- the damage field: a ragged top, a corner that came away, blast bites in the sides
    lo = max(.12, 1.0 - damage)
    ph = Vector((rnd.uniform(0, 50), rnd.uniform(0, 50), 0))
    tilt = (rnd.uniform(-1, 1), rnd.uniform(-1, 1))
    wedge = (rnd.choice((-1, 1)) * w / 2, rnd.choice((-1, 1)) * d / 2, rnd.uniform(.3, .75) + (1 - damage) * .6)
    blasts = []
    for _ in range(int(round(damage * 3.4 + rnd.random() * .8))):
        s = rnd.randrange(4)
        u = rnd.uniform(-.4, .4)
        hx, hy = [(u * w, -d / 2), (w / 2, u * d), (u * w, d / 2), (-w / 2, u * d)][s]
        blasts.append((Vector((hx, hy, rnd.uniform(.15, .8) * H)), rnd.uniform(3.2, 6.5) * (.6 + damage * .7)))

    def top_h(x, y):
        nv = noise.noise(Vector((x * .05, y * .05, 0)) + ph) * .7 + noise.noise(Vector((x * .17, y * .17, 3)) + ph) * .3
        t = lo + (1.0 - lo) * (.5 + .5 * nv) * 1.25
        h = H * t + (tilt[0] * x / max(w, 1) + tilt[1] * y / max(d, 1)) * H * .3 * (1 - lo)
        dw = math.hypot((x - wedge[0]) / max(w, 1), (y - wedge[1]) / max(d, 1))
        return min(h, H * (wedge[2] + dw * 1.5))

    def gone(x, y, z):
        if z <= levels[min(intact_below, floors)] + .01:
            return False
        if z > top_h(x, y):
            return True
        p = Vector((x, y, z))
        return any((p - bc).length < br * (.8 + .35 * noise.noise(p * .3 + ph)) for bc, br in blasts)

    # ---- which floor cells and which wall panels are still there
    cell = {}
    for k in range(1, floors + 1):
        for i in range(nbx):
            for j in range(nby):
                cell[(k, i, j)] = not gone((xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2, levels[k] - .3)
    for k in range(2, floors + 1):                                 # nothing floats: a cell needs one under it or two beside it
        for i in range(nbx):
            for j in range(nby):
                if cell[(k, i, j)] and not cell.get((k - 1, i, j), True):
                    if sum(cell.get((k, i + a, j + b), False) for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1))) < 2:
                        cell[(k, i, j)] = False

    def behind(s, i):
        """the floor cell behind bay i of side s"""
        return [(i, 0), (nbx - 1, i), (nbx - 1 - i, nby - 1), (0, nby - 1 - i)][s]

    def fxy(s, u, q):
        n, t, _ = SIDES[s]
        p = t * u + n * (half[s] - q)
        return p.x, p.y

    panel = {}
    for s in range(4):
        for i in range(count[s]):
            ci, cj = behind(s, i)
            u = -length[s] / 2 + (i + .5) * bw[s % 2]
            x, y = fxy(s, u, 0)
            for k in range(floors):
                panel[(s, i, k)] = cell[(k + 1, ci, cj)] and not gone(x, y, (levels[k] + levels[k + 1]) / 2)

    # ---- floors and ceilings (what is seen through every window and every hole)
    thick = .3
    for k in range(1, floors + 1):
        z = levels[k]
        vs, faces, mats = [], [], []
        for i in range(nbx):
            for j in range(nby):
                if not cell[(k, i, j)]:
                    continue
                o = len(vs)
                x0, x1, y0, y1 = xs[i], xs[i + 1], ys[j], ys[j + 1]
                vs += [P(x0, y0, z), P(x1, y0, z), P(x1, y1, z), P(x0, y1, z), P(x0, y0, z - thick), P(x1, y0, z - thick),
                       P(x1, y1, z - thick), P(x0, y1, z - thick)]
                faces.append((o, o + 1, o + 2, o + 3)); mats.append("ru_asphalt" if k == floors else S["floor_mat"])
                faces.append((o + 4, o + 7, o + 6, o + 5)); mats.append(S["inner"])
                for (a, b), f in (((0, -1), (o, o + 4, o + 5, o + 1)), ((1, 0), (o + 1, o + 5, o + 6, o + 2)),
                                  ((0, 1), (o + 2, o + 6, o + 7, o + 3)), ((-1, 0), (o + 3, o + 7, o + 4, o))):
                    if not cell.get((k, i + a, j + b), False):
                        faces.append(f); mats.append("ru_fracture" if (k, i + a, j + b) in cell else S["trim"])
        if vs:
            g.add(vs, faces, mats)

    # ---- the walls: a panel per bay per storey with its opening, capped with fracture where its neighbour is gone
    T = .3

    def wall_panel(s, u0, u1, z0, z1, hole, caps, mat):
        O = [(u0, z0), (u1, z0), (u1, z1), (u0, z1)]
        vs, faces, mats = [], [], []

        def v(u, z, q):
            x, y = fxy(s, u, q)
            vs.append(P(x, y, z))
            return len(vs) - 1
        of = [v(u, z, 0) for u, z in O]
        ob = [v(u, z, T) for u, z in O]
        if hole:
            a0, a1, b0, b1 = hole
            I = [(a0, b0), (a1, b0), (a1, b1), (a0, b1)]
            inf = [v(u, z, 0) for u, z in I]
            inb = [v(u, z, T) for u, z in I]
            for e in range(4):
                n = (e + 1) % 4
                faces.append((of[e], of[n], inf[n], inf[e])); mats.append(mat)
                faces.append((ob[n], ob[e], inb[e], inb[n])); mats.append(S["inner"])
                faces.append((inf[e], inf[n], inb[n], inb[e])); mats.append(S["trim"])
        else:
            faces.append(tuple(of)); mats.append(mat)
            faces.append(tuple(ob[::-1])); mats.append(S["inner"])
        for e in range(4):
            if caps[e]:
                n = (e + 1) % 4
                faces.append((of[n], of[e], ob[e], ob[n])); mats.append("ru_fracture")
        g.add(vs, faces, mats)

    def glazing(s, hole, mullion=False):
        """frame and glass in an opening: whole, broken to shards, or gone"""
        a0, a1, b0, b1 = hole
        um, zm = (a0 + a1) / 2, (b0 + b1) / 2
        _, _, ang = SIDES[s]
        if lod == 0:
            fw = .055
            for (u, z, hu, hz) in ((um, b0 + fw, (a1 - a0) / 2, fw), (um, b1 - fw, (a1 - a0) / 2, fw),
                                   (a0 + fw, zm, fw, (b1 - b0) / 2), (a1 - fw, zm, fw, (b1 - b0) / 2)):
                x, y = fxy(s, u, .12)
                box(gd, S["frame"], x, y, z, hu, .05, hz, ang)
            if mullion:
                x, y = fxy(s, um, .12)
                box(gd, S["frame"], x, y, zm, .035, .05, (b1 - b0) / 2, ang)
        r = rnd.random()
        whole = .5 - damage * .42
        if r < whole:
            x, y = fxy(s, um, .13)
            box(gd, "ru_glass", x, y, zm, (a1 - a0) / 2 - .03, .012, (b1 - b0) / 2 - .03, ang)
        elif r < whole + .3 and lod == 0:
            vs, faces = [], []
            for (cu, cz, du, dz) in ((a0, b0, 1, 1), (a1, b0, -1, 1), (a1, b1, -1, -1), (a0, b1, 1, -1)):
                if rnd.random() < .6:
                    lu, lz = rnd.uniform(.25, .6) * (a1 - a0), rnd.uniform(.25, .7) * (b1 - b0)
                    o = len(vs)
                    for (u, z) in ((cu, cz), (cu + du * lu, cz), (cu, cz + dz * lz)):
                        x, y = fxy(s, u, .13)
                        vs.append(P(x, y, z))
                    faces += [(o, o + 1, o + 2), (o + 2, o + 1, o)]
            if vs:
                gd.add(vs, faces, "ru_glass")

    plain = S.get("blank", 0.0)
    for s in range(4):
        n, t, ang = SIDES[s]
        b = bw[s % 2]
        door_bay = rnd.randrange(count[s]) if count[s] > 2 else -1
        if fs is not None:                                         # the street door in the middle of the front, none elsewhere
            door_bay = count[s] // 2 if s == fs else -1
        for i in range(count[s]):
            u0 = -length[s] / 2 + i * b
            u1 = u0 + b
            um = (u0 + u1) / 2
            for k in range(floors):
                if not panel[(s, i, k)]:
                    continue
                z0, z1 = levels[k], levels[k + 1]
                caps = (k > 0 and not panel[(s, i, k - 1)], i < count[s] - 1 and not panel[(s, i + 1, k)],
                        not panel.get((s, i, k + 1), False), i > 0 and not panel[(s, i - 1, k)])
                hole, mull, kind = None, False, "wall"
                ground = k == 0 and base_z < .5
                if fs is not None and s != fs and k < 3:           # the sides nobody is meant to pass: blind
                    pass
                elif ground:
                    if i == door_bay:
                        hole, kind = (um - .95, um + .95, 0.02, 2.5), "door"
                    elif rnd.random() < S["shop"]:
                        hole, kind, mull = (u0 + .28, u1 - .28, .5, z1 - 1.15), "shop", True
                    elif rnd.random() < S.get("doors", 0.0):
                        hole, kind = (um - 1.9, um + 1.9, 0.02, min(4.4, z1 - 1.0)), "roller"
                    elif "win" in S and rnd.random() > plain:
                        ww, wh, sill = S["win"]
                        hole = (um - ww / 2, um + ww / 2, sill + .3, min(sill + .3 + wh, z1 - .5))
                elif S.get("curtain"):
                    hole, mull = (u0 + .14, u1 - .14, z0 + .8, z1 - .14), True
                elif rnd.random() > plain:
                    ww, wh, sill = S["win"]
                    if rnd.random() < S.get("balcony", 0.0) and not (fs is not None and k < 3):
                        hole, kind = (um - .85, um + .85, z0 + .06, z0 + 2.25), "balcony"
                    else:
                        hole = (um - ww / 2, um + ww / 2, z0 + sill, min(z0 + sill + wh, z1 - .35))
                wall_panel(s, u0, u1, z0, z1, hole, caps, S["wall"])
                if hole and kind in ("wall", "shop", "balcony"):
                    glazing(s, hole, mull)
                # the floor's edge band on the face, proud of the cladding
                if lod < 2 and k > 0:
                    x, y = fxy(s, um, -.05)
                    box(g, S["trim"], x, y, z0, b / 2, .06, .16, ang)
                if lod > 0:
                    continue
                if kind == "door":
                    x, y = fxy(s, um, -.75)
                    box(g, S["trim"], x, y, 2.78, 1.6, .85, .08, ang)                    # the canopy
                    if fs is not None:                                               # the leaf back against the wall: the way is clear
                        x, y = fxy(s, um - 1.02, .78)
                        box(gd, "ru_metal", x, y, 1.25, .03, .45, 1.2, ang)
                        x, y = fxy(s, um, .2)
                        o = P(0, 0, 0)
                        wn = P(n.x, n.y, 0)
                        ENTERABLE.append((rk.ZONE, P(x, y, .06), (o[0] - wn[0], o[1] - wn[1]), (c[0], c[1]), w, d, yaw))
                    else:
                        x, y = fxy(s, um - .5, .5)
                        box(g, "ru_metal", x, y, 1.25, .45, .03, 1.2, ang + rnd.uniform(.5, 1.3))   # a leaf standing open
                    x, y = fxy(s, um + 1.25, -.08)
                    box(gd, "ru_sign_amber" if rnd.random() < .4 else "ru_metal", x, y, 1.6, .12, .03, .2, ang)
                elif kind == "shop":
                    lit = rnd.random() < .22
                    x, y = fxy(s, um, -.09)
                    box(g, rnd.choice(SIGNS) if lit else "ru_composite", x, y, z1 - .72, b / 2 - .35, .07, .3, ang)
                    if rnd.random() < .35:                                               # an awning, sagging
                        R = Matrix.Rotation(yaw + ang, 3, 'Z') @ Matrix.Rotation(rnd.uniform(.25, .5), 3, 'X')
                        x, y = fxy(s, um, -.7)
                        rk.box(g, "ru_banner", P(x, y, z1 - 1.5), (b / 2 - .4, .75, .03), R=R)
                elif kind == "roller":
                    x, y = fxy(s, um, .1)
                    drop = rnd.uniform(.2, 1.0)
                    hh = (hole[3] - hole[2]) * drop / 2
                    box(g, "ru_metal", x, y, hole[3] - hh, 1.9, .04, hh, ang)
                elif kind == "balcony":
                    x, y = fxy(s, um, -.68)
                    box(g, S["trim"], x, y, z0 - .02, b / 2 - .18, .68, .08, ang)
                    x, y = fxy(s, um, -1.3)
                    box(g, "ru_composite" if rnd.random() < .7 else "ru_glass", x, y, z0 + .55, b / 2 - .18, .03, .5, ang)
                    for su in (-1, 1):
                        x, y = fxy(s, um + su * (b / 2 - .2), -.68)
                        box(g, "ru_metal", x, y, z0 + .55, .03, .62, .5, ang)
                    if rnd.random() < .5:                                                # what was left out there
                        x, y = fxy(s, um + rnd.uniform(-.8, .8), -.7)
                        box(gd, rnd.choice(("ru_plaster", "ru_metal", "ru_banner")), x, y, z0 + .3, .25, .22, .24, ang + rnd.random())
                elif kind == "wall" and hole and style in ("resi", "mixed") and rnd.random() < .22:
                    x, y = fxy(s, um, -.2)                                               # a condenser under the window
                    box(g, "ru_metal", x, y, hole[2] - .42, .46, .19, .3, ang)
                    x, y = fxy(s, um, -.4)
                    rk.cyl(gd, "ru_composite", P(x, y, 0)[:2], .22, base_z + hole[2] - .46, base_z + hole[2] - .38, n=10, smooth=False)
                if S.get("pilaster") and i > 0 and panel.get((s, i - 1, k), False):
                    x, y = fxy(s, u0, -.1)
                    box(g, S["trim"], x, y, (z0 + z1) / 2, .26, .12, (z1 - z0) / 2, ang)
                if S.get("pilaster") and (k == 0 or k == floors - 1):
                    x, y = fxy(s, um, -.2)
                    box(g, S["trim"], x, y, z1 - .22, b / 2, .22, .22, ang)                  # a cornice
                if S.get("curtain") and k % 2 == 1 and s % 2 == 0:
                    x, y = fxy(s, um, -.3)
                    box(g, S["frame"], x, y, z1 - .2, b / 2, .3, .035, ang)                  # a sun shade
        # a blade sign up one corner of a commercial front
        if lod == 0 and style in ("office", "mixed") and rnd.random() < .45 and panel[(s, 0, min(1, floors - 1))]:
            x, y = fxy(s, -length[s] / 2 + .5, -.55)
            hh = min(H * .3, 5.0)
            box(g, "ru_metal", x, y, levels[1] + hh, .09, .5, hh, ang)
            box(gd, rnd.choice(SIGNS) if rnd.random() < .5 else "ru_composite", x, y, levels[1] + hh, .1, .42, hh - .25, ang)

    if lod == 0 and base_z < .5 and rk.ZONE:
        for s in range(4):
            if rnd.random() < .6:
                n, t, ang = SIDES[s]
                u = rnd.uniform(-.35, .35) * length[s]
                x, y = fxy(s, u, -.02)
                wn = P(n.x, n.y, 0)
                o = P(0, 0, 0)
                ANCHORS.append((rk.ZONE, P(x, y, 0), (wn[0] - o[0], wn[1] - o[1]), min(H, max(top_h(x, y), levels[1])), min(length[s] * .5, 9.0)))

    # ---- corner piers, the core, partitions: nobody sees through a building
    for (px, py) in ((-w / 2, -d / 2), (w / 2, -d / 2), (w / 2, d / 2), (-w / 2, d / 2)):
        zt = min(H, max(top_h(px * .96, py * .96), levels[1] * .6))
        box(g, S["trim"], px * (1 - .3 / w), py * (1 - .3 / d), zt / 2, .34, .34, zt / 2, top_mat="ru_fracture" if zt < H - .2 else None)
    cw, cd = min(w * .16, 3.2), min(d * .18, 3.6)
    core_top = min(H + 2.4, top_h(0, 0) + rnd.uniform(.5, 3.0))
    if core_top > 1.0:
        box(g, "ru_concrete", 0, 0, core_top / 2, cw, cd, core_top / 2, top_mat="ru_fracture" if core_top < H else "ru_asphalt")
    if lod < 2:
        for k in range(floors):
            z0, z1 = levels[k], levels[k + 1] - thick
            for i in range(1, nbx, 2):
                j = rnd.randrange(nby)
                if cell[(k + 1, i, j)] and cell[(k + 1, i - 1, j)]:
                    y0, y1 = ys[j], ys[j + 1]
                    box(g, S["inner"], xs[i], (y0 + y1) / 2, (z0 + z1) / 2, .07, (y1 - y0) / 2, (z1 - z0) / 2)
            for j in range(1, nby, 2):
                i = rnd.randrange(nbx)
                if cell[(k + 1, i, j)] and cell[(k + 1, i, j - 1)]:
                    x0, x1 = xs[i], xs[i + 1]
                    box(g, S["inner"], (x0 + x1) / 2, ys[j], (z0 + z1) / 2, (x1 - x0) / 2, .07, (z1 - z0) / 2)

    # ---- a building on the route's edge: its ground floor is somewhere to go
    if fs is not None and lod == 0 and base_z < .5:
        box(g, S["floor_mat"], 0, 0, .03, w / 2 - .31, d / 2 - .31, .03)
        n_, t_, ang_ = SIDES[fs]
        for i in range(nbx):
            for j in range(nby):
                x, y = (xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2
                if abs(x) < cw + 1.2 and abs(y) < cd + 1.2:
                    continue                                       # the core
                dist = half[fs] - (x * n_.x + y * n_.y)            # how far in from the front
                along = x * t_.x + y * t_.y
                if dist < bw[(fs + 1) % 2] * 1.2 and abs(along) < 2.2:
                    continue                                       # inside the door: left clear
                if rnd.random() < .42:
                    room(box, gd, g, style, x, y, .06, ang_ + rnd.choice((0, PI / 2, PI)), rnd)
        # why there is no way through: the back of it came down inside
        bs = (fs + 2) % 4
        for q in range(2):
            x, y = fxy(bs, rnd.uniform(-.3, .3) * length[bs], rnd.uniform(1.6, 2.6))
            pp = P(x, y, 0)
            rk.heap(g, (pp[0], pp[1], base_z + .04), rnd.uniform(2.2, 3.4), rnd.uniform(1.2, 1.9), seed * 11 + q, chunks=7, res=.4)
            x, y = fxy(bs, rnd.uniform(-.3, .3) * length[bs], rnd.uniform(.9, 1.6))
            R_ = Matrix.Rotation(yaw + ang_, 3, 'Z') @ Matrix.Rotation(rnd.uniform(.5, .85), 3, 'X')
            rk.box(g, "ru_concrete", P(x, y, rnd.uniform(1.1, 1.6)), (rnd.uniform(1.4, 2.4), 1.5, .15), R=R_, top_mat=S["floor_mat"])

    # ---- what the holes show: the rooms' things, the broken edges
    if lod == 0:
        shown = 0
        for (s, i, k), there in sorted(panel.items()):
            ci, cj = behind(s, i)
            if there or shown > 14 or not cell.get((k, ci, cj), k == 0) or k >= floors:
                continue
            if k > 0 and not cell[(k, ci, cj)]:
                continue
            shown += 1
            n, t, ang = SIDES[s]
            um = -length[s] / 2 + (i + .5) * bw[s % 2]
            z = levels[k]
            x, y = fxy(s, um + rnd.uniform(-.6, .6), rnd.uniform(1.2, 2.4))
            room(box, gd, g, style, x, y, z, ang, rnd)
            for _ in range(2):                                                           # the wall's stumps and its bars
                x, y = fxy(s, um + rnd.uniform(-1.4, 1.4), .15)
                hh = rnd.uniform(.15, .5)
                box(g, "ru_fracture", x, y, z + hh, rnd.uniform(.2, .6), .16, hh, ang, offsets=[(0, 0, 0)] * 4 + [
                    (rnd.uniform(-.1, .1), 0, rnd.uniform(-.25, .1)) for _ in range(4)])
                p0 = Vector(P(x, y, z + hh * 2))
                rk.tube(gd, "ru_metal", [tuple(p0), tuple(p0 + Vector((rnd.uniform(-.2, .2), rnd.uniform(-.2, .2), rnd.uniform(.3, .9))))], .012, 4, cap=False)

    # ---- the roof: a parapet where the top storey stands, and its plant
    roof = [(i, j) for i in range(nbx) for j in range(nby) if cell[(floors, i, j)]]
    for s in range(4):
        n, t, ang = SIDES[s]
        for i in range(count[s]):
            if panel[(s, i, floors - 1)]:
                um = -length[s] / 2 + (i + .5) * bw[s % 2]
                x, y = fxy(s, um, .12)
                box(g, S["wall"], x, y, H + .42, bw[s % 2] / 2, .12, .42, ang, top_mat=S["trim"])
    if roof and lod < 2:
        for _ in range(min(len(roof), 2 + (len(roof) // 5 if lod == 0 else 1))):
            i, j = rnd.choice(roof)
            x, y = (xs[i] + xs[i + 1]) / 2 + rnd.uniform(-.5, .5), (ys[j] + ys[j + 1]) / 2 + rnd.uniform(-.5, .5)
            plant(box, g, gd, P, S["plant"], x, y, H, rnd, lod)

    if heaps and base_z < .5:
        for _ in range(1 + int(damage * 2.5)):
            s = rnd.randrange(4)
            x, y = fxy(s, rnd.uniform(-.45, .45) * length[s], -1.6)
            p = P(x, y, 0)
            rk.heap(g, (p[0], p[1], base_z), rnd.uniform(3, 6) * (.6 + damage * .6), min(rnd.uniform(1.0, 3.0) * (.5 + damage * .7), 1.3 if fs is not None else 9.0),
                    seed * 7 + s + _, chunks=6, res=.4)
    if rk.ZONE and lod < 2 and base_z < .5:
        BUILDINGS.append((rk.ZONE, (c[0], c[1]), w, d, yaw, max([levels[k] for (k, i, j), on in cell.items() if on] or [levels[1]]), base_z))
    limit = rk.COL_TOP if col_top is None else col_top
    for fi in range(first_face, len(g.F)):
        if g.C[fi] and (limit <= 0 or min(g.V[v][2] for v in g.F[fi]) - base_z > limit):
            g.C[fi] = False
    return H


def room(box, gd, g, style, x, y, z, ang, rnd):
    """what stood in a room whose wall is gone (each thing once, where it would have been)"""
    r = rnd.random()
    a = ang + rnd.uniform(-.25, .25)
    if style in ("resi", "mixed"):
        if r < .34:                                                # a bed, its mattress half off
            box(g, "ru_plaster", x, y, z + .22, 1.0, .75, .22, a)
            box(gd, "ru_banner", x + .15, y + .1, z + .52, .95, .7, .09, a + .12)
            box(gd, "ru_plaster", x - .7, y, z + .66, .22, .4, .07, a)
        elif r < .67:                                              # a sofa and a low table
            box(g, "ru_banner", x, y, z + .24, 1.0, .42, .24, a)
            box(g, "ru_banner", x, y + .34, z + .58, 1.0, .1, .3, a)
            box(gd, "ru_metal", x + .1, y - 1.0, z + .2, .5, .3, .03, a + .3)
        else:                                                      # a kitchen run: counter, a tall unit
            box(g, "ru_ceramic", x, y, z + .45, 1.3, .3, .45, a)
            box(g, "ru_metal", x + 1.0, y, z + .95, .35, .32, .95, a)
    elif style in ("office", "lab"):
        if r < .5:                                                 # desks in a row, a screen each
            for k in (-1, 0, 1):
                box(g, "ru_composite", x + k * 1.5, y, z + .72, .65, .35, .03, a)
                box(gd, "ru_metal", x + k * 1.5, y, z + .36, .04, .3, .36, a)
                box(gd, "ru_glass", x + k * 1.5, y + .2, z + 1.0, .28, .02, .18, a)
        else:                                                      # racks, one still blinking
            for k in (-1, 0, 1):
                box(g, "ru_metal", x + k * .75, y, z + 1.0, .32, .45, 1.0, a)
            box(gd, "ru_holo_cyan" if r < .75 else "ru_sign_amber", x, y - .46, z + 1.4, .2, .01, .02, a)
    elif style == "civic":
        box(g, "ru_sandstone", x, y, z + .5, .45, .45, .5, a)        # a plinth, its figure gone
        box(gd, "ru_brass", x, y, z + 1.05, .3, .3, .05, a)
    else:                                                          # crates and a drum
        box(g, "ru_corrugate", x, y, z + .6, .8, .6, .6, a)
        box(g, "ru_metal", x + 1.3, y + .2, z + .35, .45, .45, .35, a + .6)


def plant(box, g, gd, P, kind, x, y, z, rnd, lod):
    """one piece of roof plant"""
    r = rnd.random()
    a = rnd.choice((0.0, PI / 2))
    if kind in ("resi", "plant") and r < .45:                      # a condenser bank on a frame, fans on top
        box(g, "ru_metal", x, y, z + .7, 1.1, .6, .55, a)
        box(g, "ru_metal", x, y, z + .1, 1.2, .7, .08, a)
        if lod == 0:
            for k in (-1, 1):
                p = P(x + (k * .55 if a == 0 else 0), y + (0 if a == 0 else k * .55), 0)
                rk.cyl(gd, "ru_composite", p[:2], .36, p[2] + z + 1.25, p[2] + z + 1.31, n=12, smooth=False)
    elif kind in ("resi", "tanks") and r < .7:                     # a water tank on legs
        p = P(x, y, 0)
        rk.cyl(g, "ru_metal", p[:2], .95, p[2] + z + .7, p[2] + z + 2.5, n=14)
        for dx, dy in ((-.6, -.6), (.6, -.6), (.6, .6), (-.6, .6)):
            box(g, "ru_metal", x + dx, y + dy, z + .35, .05, .05, .35)
    elif kind == "shed" and r < .6:                                # a ridge ventilator
        box(g, "ru_corrugate", x, y, z + .45, 1.6, .5, .45, a)
        box(g, "ru_metal", x, y, z + .95, 1.8, .7, .05, a)
    elif kind == "civic" and r < .5:                               # a flag mast, bent
        p = Vector(P(x, y, z))
        rk.tube(g, "ru_brass", [tuple(p), tuple(p + Vector((0, 0, 4))), tuple(p + Vector((rnd.uniform(-1.5, 1.5), rnd.uniform(-1.5, 1.5), 7)))], .07, 6, r_end=.03)
    elif r < .85:                                                  # the stair head: a door, a lamp over it
        box(g, "ru_concrete", x, y, z + 1.3, 1.5, 1.3, 1.3, a, top_mat="ru_asphalt")
        box(gd, "ru_metal", x + (1.52 if a == 0 else 0), y + (0 if a == 0 else 1.32), z + 1.05, .02 if a == 0 else .45, .45 if a == 0 else .02, 1.05)
    else:                                                          # a mast with its dishes
        p = Vector(P(x, y, z))
        rk.tube(g, "ru_metal", [tuple(p), tuple(p + Vector((0, 0, rnd.uniform(4, 8))))], .06, 6, r_end=.03)
        for k in range(2):
            q = p + Vector((0, 0, 2.0 + k * 1.4))
            rk.tube(gd, "ru_metal", [tuple(q), tuple(q + Vector((rnd.uniform(-.8, .8), rnd.uniform(-.8, .8), .1)))], .025, 4)
    if kind == "plant" and lod == 0 and r > .5:                    # a duct run across the roof
        box(g, "ru_metal", x, y + 1.8, z + .35, rnd.uniform(1.5, 3.0), .22, .22, a)


def far_building(g, c, w, d, height, yaw, seed):
    """the far skyline (lod 2): a complete, textured block with setbacks and a broken crown. No collision."""
    rnd = random.Random(seed * 31 + 5)
    mat = "ru_far_a" if rnd.random() < .55 else "ru_far_b"
    was = g.col
    g.col = False
    z = 0.0
    tiers = 1 if height < 40 else rnd.choice((2, 2, 3))
    ww, dd = w, d
    for k in range(tiers):
        h = height * ((.62, .26, .12)[k] if tiers == 3 else ((.7, .3)[k] if tiers == 2 else 1.0))
        last = k == tiers - 1
        off = None
        if last:                                                   # a crown that came down unevenly
            b = h * rnd.uniform(.1, .45)
            off = [(0, 0, 0)] * 4 + [(0, 0, -rnd.uniform(0, b)) for _ in range(4)]
        rk.box(g, mat, (c[0], c[1], z + h / 2), (ww / 2, dd / 2, h / 2), yaw, top_mat="ru_fracture" if last else "ru_asphalt", offsets=off)
        z += h
        ww *= rnd.uniform(.62, .82)
        dd *= rnd.uniform(.62, .82)
    if rnd.random() < .5:                                          # a mast or a stair head against the sky
        rk.box(g, "ru_concrete", (c[0] + rnd.uniform(-2, 2), c[1] + rnd.uniform(-2, 2), z - height * .02), (2.0, 2.0, 2.5), yaw)
    if rnd.random() < .35:
        rk.tube(g, "ru_metal", [(c[0], c[1], z - 3), (c[0] + rnd.uniform(-1, 1), c[1], z + rnd.uniform(8, 22))], .5, 5, r_end=.1)
    g.col = was
