"""Meridian's alien ecosystem, placed (alienflora.py is the plants; this is where they grow and why).

It came up out of the canal and the tunnels and has had years: densest there and at the Crown (the hive's seat),
thinning toward the Verge. It grows where plants grow: up the faces of buildings from their feet (citykit records
where: ANCHORS), over the rubble (ruinkit records the heaps: HEAPS), down from whatever overhangs, out of standing
water, in the dark and the damp. The big compositions are placed by hand: the tree through the Galleria's rotunda, the
one in the estate's fountain, the canal's pads and wall growth, the tunnel's fungus.

zone_flora(G, H) runs after every other zone and adds to each zone's own meshes.
"""
import math
import random
from mathutils import Vector
import ruinkit as rk
import citykit
import alienflora as af
import meridian_plan as P

TAU = rk.TAU


def density(n):
    """how much of it there is at northing n: 1.25 at its sources (canal, tunnel, Crown), .25 far from them"""
    d = min(abs(n + 700.0), abs(n + 1000.0), abs(n - 200.0))
    return max(.25, min(1.25, 1.25 - d / 900.0))


def zone_flora(G, H):
    rnd = random.Random(9001)
    lit = 0

    def glow(p, radius=900.0):
        nonlocal lit
        if lit < 60:
            H.light("bio", p, radius)
            lit += 1

    # ---- up the buildings, from their feet
    for k, (zone, foot, normal, height, width) in enumerate(citykit.ANCHORS):
        if zone not in G:
            continue
        dens = density(foot[1])
        if rnd.random() > dens * .55:
            continue
        g, gd = G[zone]
        af.climber(gd, foot, normal, min(height, 26.0) * rnd.uniform(.5, 1.0), width, 9100 + k, dens)
        if rnd.random() < dens * .35:
            af.roots(g, gd, (foot[0] + normal[0] * 1.2, foot[1] + normal[1] * 1.2, foot[2]), rnd.uniform(1.5, 3.0), 9300 + k)
        if rnd.random() < dens * .4:
            af.fungus(gd, (foot[0] + normal[0] * .05, foot[1] + normal[1] * .05, foot[2] + rnd.uniform(.4, 1.6)), normal, rnd.uniform(.25, .5), 9500 + k)
        if rnd.random() < .25:
            glow((foot[0] + normal[0] * 1.5, foot[1] + normal[1] * 1.5, foot[2] + 1.5), 800)
    # ---- over the rubble
    for k, (zone, c, r) in enumerate(rk.HEAPS):
        if zone not in G or zone == "backdrop":
            continue
        dens = density(c[1])
        if rnd.random() > dens * .6:
            continue
        g, gd = G[zone]
        a = rnd.uniform(0, TAU)
        p = (c[0] + math.cos(a) * r * .75, c[1] + math.sin(a) * r * .75, c[2])
        af.moss(gd, (c[0] + math.cos(a + 2) * r * .5, c[1] + math.sin(a + 2) * r * .5, c[2] + .05), rnd.uniform(.8, 1.8), 9700 + k)
        af.bulbs(gd, p, rnd.randint(3, 7), 9800 + k, spread=r * .35)
        if rnd.random() < dens * .5:
            q = (c[0] + math.cos(a + 3.5) * r * 1.1, c[1] + math.sin(a + 3.5) * r * 1.1, c[2])
            af.vine(gd, af._wander(q, (c[0], c[1], c[2] + r * .35), 6, .4, rnd), rnd.uniform(.04, .08), 9900 + k, glow=.25)

    V, S, M, D, L = P.VERGE, P.STACKS, P.GALLERIA, P.DEEPLINE, P.SLUICE
    # ---- the Verge: only the first of it, hanging from the toll canopy and the broken flyover
    g, gd = G["verge"]
    tn = V["toll_n"]
    af.curtain(gd, (-28.0, tn - 6.5, 5.6), (9.0, tn - 6.5, 5.6), 2.2, 9001, .5)
    af.curtain(gd, (-30.0, -2252.0, 8.0), (-8.0, -2246.0, 8.0), 3.5, 9002, .5)
    af.roots(g, gd, (-24.0, -2188.0, 0), 2.5, 9003)
    # ---- the Stacks: the fountain's tree, growth out of the lobby's hole, the yard's walls
    g, gd = G["stacks"]
    yc = (0.0, (S["yard"]["n0"] + S["yard"]["n1"]) / 2, 0.0)
    af.tree(g, gd, (yc[0], yc[1], 1.9), 7.5, 9010, crown=.9)
    glow((yc[0], yc[1], 5.0), 1500)
    b0 = S["block"]["n0"]
    af.curtain(gd, (-5.0, b0 + 14, 4.5), (5.0, b0 + 14, 4.5), 2.6, 9011)
    af.curtain(gd, (-5.0, b0 + 26, 4.5), (5.0, b0 + 26, 4.5), 2.2, 9012)
    af.bulbs(gd, (1.5, b0 + 21, 1.2), 6, 9013)
    for i, n in enumerate((S["yard"]["n0"] + 20, S["yard"]["n0"] + 52, S["yard"]["n0"] + 80)):
        for s in (-1, 1):
            af.climber(gd, (s * (S["half"] - .3), n + i * 3 * s, 0), (-s, 0), rnd.uniform(4, 9), 6.0, 9020 + i * 2 + (s > 0), density(n))
    for i in range(4):
        n = S["yard"]["n0"] + 18 + i * 22
        af.curtain(gd, (-20.0 + i * 6, n + 1.5, 7.6), (-8.0 + i * 6, n + 2.2, 7.7), 1.8, 9030 + i, .6)
    al = S["alley"]
    for i, dn in enumerate((30.0, 66.0, 118.0)):
        s = (-1) ** i
        af.climber(gd, (s * (al["half"] - .05), al["n0"] + dn, 0), (-s, 0), rnd.uniform(5, 10), 5.0, 9040 + i, density(al["n0"] + dn))
    # ---- the Galleria: the tree through the rotunda, curtains off the bridges and the gallery, the fountain's moss
    g, gd = G["galleria"]
    rot = (0.0, M["rot_n"])
    af.tree(g, gd, (rot[0], rot[1], 2.3), 12.5, 9050, crown=1.3)
    glow((rot[0], rot[1], 9.0), 2400)
    glow((rot[0] + 6, rot[1] - 5, 3.0), 1200)
    af.moss(gd, (rot[0] + 2.5, rot[1] + 1.0, .14), 1.6, 9051)
    af.moss(gd, (rot[0] - 2.0, rot[1] - 2.4, .14), 1.2, 9052)
    af.bulbs(gd, (rot[0] - 3.0, rot[1] + 3.0, .14), 7, 9053)
    for i, bn in enumerate(M["bridges"]):
        for dn in (-3.0, 3.0):
            af.curtain(gd, (-M["void"], bn + dn, M["z1"] - .36), (M["void"], bn + dn, M["z1"] - .36), 3.0, 9060 + i * 2 + (dn > 0), .5)
    for i in range(8):
        s = (-1) ** i
        n = M["n0"] + 26 + i * 34
        if abs(n - rot[1]) > M["rot_r"] + 4:
            af.curtain(gd, (s * M["void"], n, M["z1"] - .36), (s * M["void"], n + 9, M["z1"] - .36), 2.4, 9070 + i, .5)
            af.climber(gd, (s * (M["conc"] - .25), n + 4, 0), (-s, 0), rnd.uniform(3, 4.4), 5.0, 9080 + i, density(n))
    af.curtain(gd, (-M["void"], rot[1] - M["rot_r"], M["roof"] - .4), (M["void"], rot[1] - M["rot_r"], M["roof"] - .4), 4.5, 9090, .7)
    af.curtain(gd, (-M["void"], rot[1] + M["rot_r"], M["roof"] - .4), (M["void"], rot[1] + M["rot_r"], M["roof"] - .4), 4.5, 9091, .7)
    # ---- Deepline: the dark and the damp. Fungus up the walls, strands off the ribs, lanterns down the track
    g, gd = G["deepline"]
    z, track, wl, th = D["z"], D["track"], D["wall"], D["tun_half"]
    for i in range(9):
        n = D["hall_n1"] + 8 + i * 11
        s = (-1) ** i
        af.fungus(gd, (s * (wl - .05), n, track + rnd.uniform(.6, 1.8)), (-s, 0), rnd.uniform(.35, .7), 9100 + i)
        af.bulbs(gd, (s * 7.5, n + 4, track), rnd.randint(3, 6), 9110 + i, spread=1.6)
        if i % 3 == 0:
            glow((s * 7.0, n, track + 1.2), 900)
    for i in range(4):
        n = D["hall_n1"] + 18 + i * 20
        af.curtain(gd, (-3.0, n, D["top"] - .05), (3.0, n, D["top"] - .05), 1.6, 9120 + i, .6)
        af.moss(gd, ((-1) ** i * 4.0, n + 3, z + .02), 1.0, 9125 + i)
    f0, f1 = D["fall_n"]
    n = D["plat_n1"] + 14
    i = 0
    while n < D["tun_n1"] - 6:
        if not (f0 - 4 < n < f1 + 4):
            s = (-1) ** i
            af.fungus(gd, (s * (th - .05), n, track + rnd.uniform(.5, 2.2)), (-s, 0), rnd.uniform(.3, .65), 9130 + i)
            af.curtain(gd, (-th + .4, n + 3, D["tun_top"] - .5), (th - .4, n + 3, D["tun_top"] - .5), 1.5, 9160 + i, .35)
            af.bulbs(gd, (-s * rnd.uniform(2.5, 4.2), n + 6, track), rnd.randint(2, 5), 9190 + i, spread=.8)
            if i % 2 == 0:
                glow((-s * 3.0, n + 6, track + 1.0), 800)
        n += 13.0
        i += 1
    # ---- the Sluice: where it came from. Pads in the bed, growth down both walls, roots round the pump house, strands
    # off the bridges
    g, gd = G["sluice"]
    zc, half = L["z"], L["half"]
    for i in range(12):
        n = L["n0"] + 16 + i * 28
        e = rnd.uniform(-9, 9)
        af.pads(g, gd, (e, n, zc), rnd.uniform(2.0, 4.0), 9200 + i)
        if i % 3 == 0:
            glow((e, n, zc + 1.0), 1100)
    R = L["ramp"]
    for i in range(11):
        n = L["n0"] + 12 + i * 31
        for s in (-1, 1):
            if s > 0 and R["n0"] - 4 < n < R["n1"] + 4:
                continue
            af.climber(gd, (s * (half - .05), n + s * 6, zc), (-s, 0), rnd.uniform(3.5, 6.0), 7.0, 9220 + i * 2 + (s > 0), density(n))
            if (i + (s > 0)) % 3 == 0:
                af.curtain(gd, (s * (half - .2), n - 8, 1.0), (s * (half - .2), n - 1, 1.0), 3.5, 9250 + i * 2 + (s > 0), .6)
    pn = L["pump_n"]
    for i, e in enumerate((-10.0, 0.0, 10.0)):
        af.roots(g, gd, (e, pn - 7.5, zc), 3.2, 9270 + i)
        af.climber(gd, (e, pn - 5.05, zc), (0, -1), 6.5, 3.0, 9275 + i, 1.2)
    for i, bn in enumerate(L["bridges"]):
        af.curtain(gd, (-half, bn - 2.0, .1), (half if i == 0 else -2.0, bn - 2.0, .1), 3.6, 9280 + i, .7)
        af.curtain(gd, (-half, bn + 2.0, .1), (half if i == 0 else -2.0, bn + 2.0, .1), 3.0, 9283 + i, .5)
    af.tree(g, gd, (-11.5, -640.0, zc), 9.0, 9290, crown=1.0)
    af.tree(g, gd, (11.0, -812.0, zc), 7.5, 9291, crown=.8)
    glow((-11.5, -640.0, zc + 6.0), 1800)
    glow((11.0, -812.0, zc + 5.0), 1600)
    # ---- the old city: the gate's arch, the Ring's planters gone to trees, the Crown's rim
    g, gd = G["gate"]
    W = P.WALL
    af.curtain(gd, (-W["gate_w"] / 2 + 1, W["n"] - W["thick"] / 2 - .4, W["gate_h"] - 1.0), (W["gate_w"] / 2 - 1, W["n"] - W["thick"] / 2 - .4, W["gate_h"] - 1.0), 4.5, 9300, .6)
    for i, e in enumerate((-40.0, -24.0, 26.0, 44.0)):
        af.climber(gd, (e, W["n"] - W["thick"] / 2 - .12, 0), (0, -1), rnd.uniform(9, 18), 8.0, 9310 + i, .9)
    g, gd = G["ring"]
    for i in (1, 4, 6, 8):
        a = TAU * i / 10 + .1
        c = (math.cos(a) * 28, math.sin(a) * 28, .8)
        af.tree(g, gd, c, rnd.uniform(5.5, 7.5), 9320 + i, crown=.8)
        glow((c[0], c[1], 4.5), 1300)
    af.roots(g, gd, (6.0, -4.0, -P.PLAZA["sunk"]), 4.0, 9330)
    af.moss(gd, (-6.0, 3.0, -P.PLAZA["sunk"] + .02), 2.2, 9331)
    g, gd = G["crown"]
    cx, cy = P.CROWN["c"]
    for i in range(6):
        a = TAU * i / 6 + .4
        af.roots(g, gd, (cx + math.cos(a) * 33, cy + math.sin(a) * 33, P.CROWN["z"]), 3.5, 9340 + i, lift=False)
        af.bulbs(gd, (cx + math.cos(a + .3) * 30, cy + math.sin(a + .3) * 30, P.CROWN["z"]), 5, 9350 + i)
