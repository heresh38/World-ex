"""Meridian's landmarks: one thing per district that is seen from far off and tells you where you are
(docs/operation/ART_DIRECTION.md section 11: strong silhouettes, large-scale landmarks, memorable spaces).

  Ashfall Verge   the transit control tower beside the landing pad; the great sign gantry over the highway
  The Stacks      the three tall slabs the estate is named for, joined by sky bridges (one down)
  Galleria        the glazed arch over its doors, the vault over its atrium, the sign pylon in the forecourt
  Deepline        the station's canopy over the stair, its ring sign still alight
  The Sluice      the research annex and its silo on the west bank, the pipe bridge over the canal, two cooling towers
  The Causeway    the gunship that came down across it
  Concord Ring    the Assembly's dome over the plaza, split open

Hand-built, each once. zone_landmarks(G, H) runs after the districts and before the streets' story.
"""
import math
import random
from mathutils import Vector, Matrix
import ruinkit as rk
import citykit
import meridian_plan as P

TAU = rk.TAU
PI = math.pi


def lathe(g, mat, c, profile, n=24, a0=0.0, a1=TAU, top_mat=None, smooth=True):
    """a turned shape round the vertical through c (x, y): profile [(radius, z)], optionally only the arc a0..a1"""
    whole = a1 - a0 >= TAU - 1e-6
    m = n if whole else n + 1
    vs = []
    for (r, z) in profile:
        for i in range(m):
            a = a0 + (a1 - a0) * i / n
            vs.append((c[0] + math.cos(a) * r, c[1] + math.sin(a) * r, z))
    faces = []
    for k in range(len(profile) - 1):
        for i in range(n if whole else n):
            j = (i + 1) % m if whole else i + 1
            a, b = k * m + i, k * m + j
            faces.append((a, b, b + m, a + m))
    g.add(vs, faces, mat, smooth=smooth)


def arc_rib(g, mat, e0, e1, n, z0, rise, r=.2, seg=18, a_to=PI):
    """a rib arching over from (e0, n) to (e1, n): a half ellipse `rise` high (a_to < pi: it broke off part way)"""
    ec, hw = (e0 + e1) / 2, abs(e1 - e0) / 2
    pts = [(ec - math.cos(a_to * i / seg) * hw, n, z0 + math.sin(a_to * i / seg) * rise) for i in range(seg + 1)]
    rk.tube(g, mat, pts, r, 6)
    return pts


def zone_landmarks(G, H):
    rnd = random.Random(8101)
    V, S, M, D, L, C = P.VERGE, P.STACKS, P.GALLERIA, P.DEEPLINE, P.SLUICE, P.CAUSEWAY
    far = lambda g: setattr(g, "col", False)                         # (seen, never reached)

    # ---------------- Ashfall Verge: the control tower, the sign gantry
    g, gd = G["verge"]
    far(g)
    tc = (-47.0, V["pad"][1] + 2.0)
    lathe(g, "ru_ceramic", tc, [(2.6, 0), (2.4, 8), (2.2, 22), (2.3, 25)], n=16)
    lathe(g, "ru_composite", tc, [(2.3, 25), (5.4, 28.2), (5.6, 28.6)], n=16)
    for i in range(16):                                              # the cab: mullions, and what glass is left
        a = TAU * i / 16
        p = (tc[0] + math.cos(a) * 5.6, tc[1] + math.sin(a) * 5.6)
        rk.tube(g, "ru_metal", [(p[0], p[1], 28.6), (p[0] * 1.0 + math.cos(a) * .5, p[1] + math.sin(a) * .5, 31.2)], .07, 5)
    lathe(gd, "ru_glass", tc, [(5.62, 28.7), (6.08, 31.1)], n=16, a0=.4, a1=4.3)
    lathe(g, "ru_composite", tc, [(6.3, 31.2), (6.5, 31.6), (4.0, 32.6), (1.2, 33.0)], n=16)
    for k, (dx, dy, hh) in enumerate(((0, 0, 9.0), (1.6, .6, 5.0), (-1.2, 1.4, 6.5))):
        top = (tc[0] + dx + (2.2 if k == 0 else 0), tc[1] + dy, 33.0 + hh * (.55 if k == 0 else 1))
        rk.tube(g, "ru_metal", [(tc[0] + dx, tc[1] + dy, 33.0), top], .09, 5, r_end=.03)
    rk.box(gd, "ru_sign_amber", (tc[0], tc[1], 32.9), (.3, .3, .12))
    H.light("lamp", (tc[0], tc[1], 30.0), 2600, 40.0)
    g.col = True
    gn = V["n1"] + 12.0                                              # the gantry: two lattice legs, a board in four panels
    for s in (-1, 1):
        for dx in (-.5, .5):
            for dy in (-.5, .5):
                rk.tube(g, "ru_metal", [(s * 13.0 + dx, gn + dy, 0), (s * 13.0 + dx * .6, gn + dy * .6, 13.5)], .07, 5)
        for k in range(6):
            z = 1.5 + k * 2.2
            rk.tube(gd, "ru_metal", [(s * 13.0 - .5, gn - .5, z), (s * 13.0 + .5, gn + .5, z + 1.1)], .04, 4)
    rk.box(g, "ru_metal", (0, gn, 13.2), (13.6, .25, .25))
    rk.box(g, "ru_metal", (0, gn, 8.6), (13.6, .2, .2))
    far(g)
    for k in range(4):
        e = -9.6 + k * 6.4
        if k == 2:                                                   # one panel hanging by a corner
            R = Matrix.Rotation(.5, 3, 'Y')
            rk.box(g, "ru_composite", (e + 1.0, gn - .1, 9.4), (3.0, .08, 2.0), R=R)
        else:
            rk.box(g, ("ru_holo_magenta", "ru_composite", "ru_composite", "ru_holo_cyan")[k], (e, gn - .1, 10.9), (3.0, .08, 2.1))
    g.col = True

    # ---------------- The Stacks: the three slabs and their sky bridges
    g, gd = G["stacks"]
    far(g)
    rk.ZONE = "stacks"                                             # (so what grows on them is the Stacks')
    slabs = ((-84.0, -1902.0, 19), (-87.0, -1852.0, 26), (-84.0, -1802.0, 22))
    for i, (e, n, fl) in enumerate(slabs):
        citykit.building(g, gd, (e, n), 20.0, 40.0, fl, 0.0, 8200 + i, "resi", .22 + .1 * i, 0.0, False, 1, 0)
    for i, (n, z, broken) in enumerate(((-1877.0, 38.0, False), (-1827.0, 51.0, True), (-1877.0, 22.0, False))):
        if broken:                                                   # one end still fixed, the span hanging
            R = Matrix.Rotation(.9, 3, 'X')
            rk.box(g, "ru_composite", (-85.0, n - 3.2, z - 2.6), (2.0, 3.6, 1.5), R=R)
        else:
            rk.box(g, "ru_composite", (-85.0, n, z), (2.0, 5.2, 1.5))
            rk.box(gd, "ru_glass", (-82.95, n, z + .2), (.02, 4.8, .8))
    rk.box(gd, "ru_sign_amber", (-74.0, -1852.0, 84.5), (.2, 3.0, .6))
    g.col = True

    # ---------------- Meridian Galleria: the arch over the doors, the vault over the atrium, the sign pylon
    g, gd = G["galleria"]
    n0, n1, roof = M["n0"], M["n1"], M["roof"]
    ribs = []
    for k in range(4):
        n = n0 - 11.0 + k * 3.6
        ribs.append(arc_rib(g, "ru_brass", -24.0, 24.0, n, 5.8, 11.5, .22, 20, PI if k != 2 else PI * .62))
    for i in range(2, 19, 3):                                        # purlins tying the ribs, glass in some bays
        pts = [ribs[k][i] for k in (0, 1, 3)]                      # (the third rib broke off part way: nothing ties to it)
        rk.tube(g, "ru_brass", pts, .1, 5)
        if i < 17 and rnd.random() < .45:
            vs = [ribs[0][i], ribs[1][i], ribs[1][i + 3], ribs[0][i + 3]]
            gd.add(vs, [(0, 1, 2, 3), (3, 2, 1, 0)], "ru_glass")
    for s in (-1, 1):                                                # the arch's feet
        rk.box(g, "ru_ceramic", (s * 24.0, n0 - 5.6, 2.9), (.8, 6.0, 2.9))
    px, pn = 30.5, M["fore_n0"] + 9.0                                # the pylon: a tall blade, bars of light up it
    rk.box(g, "ru_composite", (px, pn, 9.5), (.35, .9, 9.5), .2)
    rk.box(g, "ru_brass", (px, pn, 19.2), (.5, 1.1, .25), .2)
    for k in range(7):
        if k not in (2, 5):
            rk.box(gd, "ru_holo_cyan" if k % 2 else "ru_holo_magenta", (px - .37, pn - .07, 3.0 + k * 2.3), (.02, .6, .8), .2)
    H.light("lamp", (px - 1.5, pn, 10.0), 1600, 30.0)
    was = g.col
    far(g)
    rot_n, rr = M["rot_n"], M["rot_r"]
    n = n0 + 6.0
    while n < n1 - 4:                                                # the vault over the atrium, gone over the rotunda
        gone = abs(n - rot_n) < rr + 5
        if not gone:
            arc_rib(g, "ru_brass", -M["void"], M["void"], n, roof + .1, 4.2, .11, 10)
        elif abs(n - rot_n) > rr - 2:
            arc_rib(g, "ru_brass", -M["void"], M["void"], n, roof + .1, 4.2, .11, 10, PI * rnd.uniform(.25, .45))
        n += 6.0
    for e in (-M["void"] * .6, 0.0, M["void"] * .6):
        z = roof + .1 + math.sqrt(max(1 - (e / M["void"]) ** 2, 0)) * 4.2
        rk.tube(g, "ru_brass", [(e, n0 + 4, z), (e, rot_n - rr - 5, z)], .07, 5)
        rk.tube(g, "ru_brass", [(e, rot_n + rr + 5, z), (e, n1 - 4, z)], .07, 5)
    g.col = was

    # ---------------- Deepline: the canopy over the stair, the ring sign
    g, gd = G["deepline"]
    s0, s1, sh = D["stair_n0"], D["stair_n1"], D["stair_half"]
    for (e, n) in ((-sh - 1.2, s0 - 1.5), (sh + 1.2, s0 - 1.5), (-sh - 1.2, s1 - 6.0), (sh + 1.2, s1 - 6.0)):
        rk.tube(g, "ru_metal", [(e, n, 0), (e, n, 5.6 if n > s0 - 2 else 6.6)], .16, 8)
    R = Matrix.Rotation(-.05, 3, 'X')
    rk.box(g, "ru_composite", (0.0, (s0 + s1) / 2 - 2.2, 6.2), (sh + 2.2, (s1 - s0) / 2 + 1.0, .16), R=R, top_mat="ru_metal")
    rk.box(g, "ru_brass", (0.0, s0 - 2.6, 5.5), (sh + 2.2, .12, .35))
    mast = (sh + 4.0, s0 - 3.0)
    rk.tube(g, "ru_metal", [(mast[0], mast[1], 0), (mast[0], mast[1], 8.4)], .12, 7)
    ring = [(mast[0], mast[1] + math.cos(TAU * i / 20) * 1.5, 8.4 + math.sin(TAU * i / 20) * 1.5) for i in range(21)]
    rk.tube(g, "ru_holo_cyan", ring, .16, 6)
    rk.box(g, "ru_holo_cyan", (mast[0], mast[1], 8.4), (.1, 1.9, .2))
    H.light("lamp", (mast[0] - 1.0, mast[1], 7.6), 1500, 28.0)
    H.light("lamp", (0.0, s0 + 6.0, 4.6), 1400, 24.0)

    # ---------------- The Sluice: the research annex and its silo, the pipe bridge, the cooling towers
    g, gd = G["sluice"]
    far(g)
    half, pn = L["half"], L["pump_n"]
    rk.ZONE = "sluice"
    citykit.building(g, gd, (-half - 36.0, pn - 34.0), 30.0, 44.0, 6, 0.0, 8300, "lab", .4, 0.0, True, 1, 0)
    sc = (-half - 40.0, pn + 12.0)
    lathe(g, "ru_composite", sc, [(8.0, 0), (8.0, 20), (7.2, 23), (4.5, 25.5), (0.4, 26.5)], n=20)
    for k in range(4):
        lathe(g, "ru_metal", sc, [(8.12, 3 + k * 5), (8.12, 3.4 + k * 5)], n=20)
    rk.tube(g, "ru_metal", [(sc[0] + 8.2, sc[1] - 2, 0), (sc[0] + 8.2, sc[1] - 2, 25)], .18, 6)
    bn = pn - 52.0                                                   # the pipe bridge: two mains and a walkway on trestles
    for dy, r in ((-.9, .7), (.9, .55)):
        rk.tube(g, "ru_metal", [(-half - 21.0, bn + dy, 6.2), (half + 50.0, bn + dy, 6.2), (half + 52.0, bn + dy - 8.0, 4.0)], r, 10)
    rk.box(g, "ru_metal", (0.0, bn, 5.3), (half + 19.0, 1.8, .12))
    for e in (-half - 18.0, -half - 3.0, half + 3.0, half + 16.0, half + 30.0, half + 44.0):
        for dy in (-1.6, 1.6):
            rk.tube(g, "ru_metal", [(e, bn + dy, 0), (e, bn + dy * .5, 5.3)], .14, 6)
    for e in range(-18, 19, 6):
        rk.tube(gd, "ru_metal", [(e, bn - 1.8, 5.4), (e + 3, bn - 1.8, 6.4), (e + 6, bn - 1.8, 5.4)], .05, 4)
    for i, (e, n, r0, hh, broken) in enumerate(((half + 62.0, -768.0, 13.0, 46.0, False), (half + 84.0, -706.0, 12.0, 42.0, True))):
        prof = []
        top = hh * (.62 if broken else 1.0)
        for k in range(11):
            z = top * k / 10
            prof.append((r0 * (.62 + .38 * ((z - hh * .68) / (hh * .68)) ** 2), z))
        lathe(g, "ru_concrete", (e, n), prof, n=22)
        if broken:                                                   # its top came down beside it
            rk.heap(g, (e - 16.0, n + 6.0, 0), 11.0, 5.0, 8310, chunks=10, res=.5)
    g.col = True
    # the plant's yard between the bank and the towers: a fence line, transformers, tanks on their sides, the growth
    yard_n = (pn - 100.0, pn + 10.0)
    for k in range(12):
        n = yard_n[0] + (yard_n[1] - yard_n[0]) * k / 11
        rk.tube(gd, "ru_metal", [(half + 8.0, n, 0), (half + 8.0, n, 2.6), (half + 8.4, n, 3.0)], .05, 5)
        if k and k not in (4, 9):                                    # the mesh panels, two torn out
            rk.box(gd, "ru_metal", (half + 8.0, n - (yard_n[1] - yard_n[0]) / 22, 1.3), (.015, (yard_n[1] - yard_n[0]) / 22 - .05, 1.2))
    for (e, n, yaw) in ((half + 22.0, pn - 84.0, .1), (half + 27.0, pn - 84.5, .1), (half + 20.0, pn - 22.0, -.2)):
        Rz = Matrix.Rotation(yaw, 3, 'Z')
        rk.box(g, "ru_metal", (e, n, 1.3), (1.5, 1.1, 1.3), R=Rz)                               # transformers, finned
        for f in range(-3, 4):
            rk.box(gd, "ru_block_dark", (e + f * .4 * math.cos(yaw), n + f * .4 * math.sin(yaw), 1.3), (.04, 1.35, 1.0), R=Rz)
        for f in (-.8, 0.0, .8):
            rk.cyl(gd, "ru_ceramic", (e + f * math.cos(yaw), n + f * math.sin(yaw)), .13, 2.6, 3.5, n=8)
    for (e, n, yaw, L) in ((half + 30.0, pn - 40.0, .4, 9.0), (half + 36.0, pn - 6.0, 1.3, 7.0)):
        d = Vector((math.cos(yaw), math.sin(yaw), 0)) * (L / 2)
        rk.tube(g, "ru_composite", [(e - d.x, n - d.y, 1.6), (e + d.x, n + d.y, 1.6)], 1.6, 14)
    rk.heap(g, (half + 40.0, pn - 62.0, 0), 7.0, 2.4, 8320, chunks=8, res=.4)
    H.light("bio", (half + 24.0, pn - 54.0, 3.0), 2600, 46.0)
    H.light("bio", (half + 62.0, pn - 68.0 + 14.0, 9.0), 3800, 70.0)                            # up the first tower's flank
    H.light("bio", (-half - 34.0, pn - 34.0, 8.0), 3000, 54.0)                                  # the annex's canal face
    H.light("lamp", (-half - 20.0, pn - 52.0, 7.5), 1600, 30.0)                                 # where the mains leave it

    # ---------------- the Causeway: the gunship that came down across it
    g, gd = G["causeway"]
    c = Vector((22.0, -503.0, 1.7))
    R = Matrix.Rotation(.35, 3, 'Z') @ Matrix.Rotation(-.16, 3, 'Y') @ Matrix.Rotation(.3, 3, 'X')

    def gp(x, y, z):
        return tuple(c + R @ Vector((x, y, z)))

    def gb(mat, x, y, z, hx, hy, hz, offsets=None, target=None):
        rk.box(target or g, mat, gp(x, y, z), (hx, hy, hz), R=R, offsets=offsets)
    nose = [(0, 0, 0), (-.2, .35, .35), (-.2, -.35, .35), (0, 0, 0), (0, 0, 0), (-1.4, .6, -.5), (-1.4, -.6, -.5), (0, 0, 0)]
    gb("ru_car_green", 2.0, 0, 0, 4.6, 1.5, 1.25, nose)                               # the forward hull, the nose in the road
    gb("ru_block_dark", 5.4, 0, .55, .9, 1.0, .5, [(0, 0, 0)] * 4 + [(-.3, .2, 0), (-.9, .2, -.2), (-.9, -.2, -.2), (-.3, -.2, 0)])
    gb("ru_glass", 5.3, 0, .9, .8, .9, .22, target=gd)
    gb("ru_car_green", -4.6, .4, .5, 2.4, 1.3, 1.0, [(.4, 0, -.3)] * 4 + [(0, 0, 0)] * 4)   # the aft hull, broken from it
    gb("ru_fracture", -2.4, .2, .1, .35, 1.3, 1.0)
    for s in (-1, 1):                                                # stub wings and their engines: one torn away
        gb("ru_car_green", .6, s * 3.0, .7, 1.3, 1.6, .14)
        if s > 0:
            rk.tube(g, "ru_metal", [gp(-.9, s * 4.4, .6), gp(2.4, s * 4.4, .6)], 1.0, 12)
            rk.tube(g, "ru_block_dark", [gp(2.4, s * 4.4, .6), gp(2.7, s * 4.4, .6)], .8, 12)
    rk.tube(g, "ru_metal", [(31.5, -495.0, 1.0), (34.6, -494.2, 1.0)], 1.0, 12)                # the other engine, in the road
    rk.tube(g, "ru_block_dark", [(34.6, -494.2, 1.0), (34.9, -494.1, 1.0)], .8, 12)
    for s in (-1, 1):                                                # twin tail booms, one standing
        rk.tube(g, "ru_car_green", [gp(-6.6, s * 1.0, .9), gp(-10.5, s * 1.3, 1.5 if s > 0 else .2)], .28, 6, r_end=.16)
    gb("ru_car_green", -10.6, 1.3, 2.5, .9, .08, 1.1)
    gb("ru_sign_amber", 1.2, -1.52, .3, .25, .02, .08, target=gd)
    rk.heap(g, (17.5, -505.5, 0), 6.0, 2.2, 8401, ry=4.5)                                       # what it ploughed up
    rk.chunks(gd, (26.0, -500.0), 7, 40, 8402)
    H.light("fire", (19.0, -500.0, .5), 1400)

    # ---------------- Concord Ring: the Assembly's dome over the plaza, split open
    g, gd = G["ring"]
    far(g)
    dc = (-98.0, 16.0)
    # (on a tall podium: it has to stand over the Ring's towers to be the Ring's landmark)
    lathe(g, "ru_sandstone", dc, [(24.0, 0), (24.0, 20), (21.0, 21), (21.0, 36), (19.5, 36.6), (19.5, 46)], n=28)
    for i in range(14):                                              # the drum's colonnade
        a = TAU * i / 14
        rk.cyl(g, "ru_sandstone", (dc[0] + math.cos(a) * 20.4, dc[1] + math.sin(a) * 20.4), .9, 36.6, 45.4, n=10)
    lathe(g, "ru_sandstone", dc, [(20.6, 46), (20.9, 47.2), (19.4, 47.6)], n=28)
    dome = [(19.2 * math.cos(PI / 2 * k / 9), 47.6 + 17.5 * math.sin(PI / 2 * k / 9)) for k in range(10)]
    lathe(g, "ru_brass", dc, dome, n=28, a0=.9, a1=.9 + TAU * .78)                              # a quarter of the shell gone
    for i in range(6):                                               # its ribs standing in the gap
        a = .9 + TAU * (.78 + .22 * (i + .5) / 6)
        hi = rnd.randint(4, 9)
        rk.tube(g, "ru_metal", [(dc[0] + math.cos(a) * r, dc[1] + math.sin(a) * r, z) for r, z in dome[:hi + 1]], .22, 5)
    rk.tube(g, "ru_brass", [(dc[0], dc[1], 65.1), (dc[0] + 1.5, dc[1], 72.0)], .3, 6, r_end=.06)
    rk.heap(g, (dc[0] + 20.0, dc[1] - 16.0, 0), 12.0, 6.0, 8501, chunks=12, res=.5)
    g.col = True
