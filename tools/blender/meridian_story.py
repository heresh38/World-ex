"""What happened in Meridian, told by what is left (docs/operation/ART_DIRECTION.md section 4; streetkit.py is the
props). Every piece here has a reason:

  Ashfall Verge   the evacuation. A jam of cars heading out of the city, stopped at the toll plaza for good; a bus
                  over on its side; luggage where it was dropped; the landing pad's crates and floodlights still set
                  out for shuttles that stopped coming.
  The Stacks      quarantine. Barriers and a checkpoint before the gatehouse; relief tents and cots in the yard; cars
                  left in the alley.
  Galleria        the shelter that was overrun. Queue barriers at the doors, rows of cots under the gallery, supply
                  crates by the food court.
  Deepline        where people hid. Bedding along the hall's walls; the train that never left, stopped in the tunnel.
  The Sluice      where it began. The research annex's containment tanks on the west bank, burst, their pipes down
                  into the bed.
  Causeway and Approach   the army's line, facing the canal: sandbag emplacements, carriers (one burnt out), floodlights.
  The Boulevard   the capital's avenue, stopped mid-afternoon: cars, a bus at its stop, signals, shelters.

zone_story(G, H) runs after the districts are built and adds to each zone's own meshes.
"""
import math
import random
from mathutils import Vector
import ruinkit as rk
import streetkit as sk
import meridian_plan as P

PI = math.pi
SOUTH, NORTH = -PI / 2, PI / 2          # a vehicle's heading (its local +x): out of the city, into it


def cot(g, gd, p, yaw, rnd):
    """a relief cot: a low frame, a blanket left on it"""
    rk.box(g, "ru_metal", (p[0], p[1], p[2] + .3), (.95, .36, .03), yaw)
    for dx in (-.85, .85):
        rk.box(gd, "ru_metal", (p[0] + math.cos(yaw) * dx, p[1] + math.sin(yaw) * dx, p[2] + .15), (.03, .36, .15), yaw)
    if rnd.random() < .7:
        rk.box(gd, rnd.choice(("ru_sack", "ru_banner", "ru_car_blue")), (p[0], p[1], p[2] + .36), (.6, .3, .04), yaw + rnd.uniform(-.2, .2))


def tent(g, gd, c, yaw, rnd):
    """a relief tent: four posts, a sagging canvas roof, one wall still up, cots inside"""
    Pp = sk._T(c, yaw)
    for x in (-2.4, 2.4):
        for y in (-1.8, 1.8):
            rk.tube(g, "ru_metal", [Pp(x, y, 0), Pp(x, y, 2.3)], .04, 5)
    rk.box(g, "ru_sack", Pp(0, 0, 2.38), (2.6, 2.0, .04), yaw, offsets=[(0, 0, 0)] * 4 + [(0, 0, -.2), (0, 0, .1), (0, 0, -.1), (0, 0, .15)])
    rk.box(g, "ru_sack", Pp(0, 1.82, 1.2), (2.4, .02, 1.1), yaw)
    for x in (-1.2, 1.2):
        cot(g, gd, Pp(x, .2, 0), yaw + PI / 2, rnd)


def tank(g, gd, c, h, rnd, burst):
    """a containment tank: a glass cylinder in a steel frame, something still alight in it, or burst and empty"""
    rk.cyl(g, "ru_metal", (c[0], c[1]), 1.25, c[2], c[2] + .5, n=16, smooth=False)
    rk.cyl(g, "ru_metal", (c[0], c[1]), 1.25, c[2] + h - .4, c[2] + h, n=16, smooth=False)
    for k in range(4):
        a = PI / 4 + k * PI / 2
        rk.tube(g, "ru_metal", [(c[0] + math.cos(a) * 1.2, c[1] + math.sin(a) * 1.2, c[2] + .5), (c[0] + math.cos(a) * 1.2, c[1] + math.sin(a) * 1.2, c[2] + h - .4)], .06, 5)
    if burst:
        rk.cyl(gd, "ru_glass", (c[0], c[1]), 1.1, c[2] + .5, c[2] + .5 + h * rnd.uniform(.15, .4), n=16, smooth=False)
    else:
        rk.cyl(gd, "ru_glass", (c[0], c[1]), 1.1, c[2] + .5, c[2] + h - .4, n=16, smooth=False)
        rk.cyl(gd, "ru_bio", (c[0], c[1]), .35, c[2] + .7, c[2] + h * .7, n=8, smooth=False)


def zone_story(G, H):
    rnd = random.Random(7001)
    V, S, M, D, L, C = P.VERGE, P.STACKS, P.GALLERIA, P.DEEPLINE, P.SLUICE, P.CAUSEWAY

    # ---------------- Ashfall Verge: the evacuation
    g, gd = G["verge"]
    tn = V["toll_n"]
    sk.street(g, gd, (0, V["n0"] + 28), (0, tn - 8), 18.0, 7010, walk=2.6)
    sk.street(g, gd, (0, tn + 8), (0, V["n1"] + 2), 18.0, 7011, walk=2.6)
    k = 0
    for lane, e in enumerate((-6.6, -2.3, 2.3, 6.6)):               # four lanes of cars that never got through the toll
        n = tn + 12 + lane * 1.5
        while n < -2008:
            if rnd.random() < (.8 if abs(e) > 3 else .45):
                burnt = rnd.random() < .18
                sk.car(g, gd, (e + rnd.uniform(-.5, .5), n, .04), SOUTH + rnd.uniform(-.14, .14), 7020 + k, burnt=burnt)
                if rnd.random() < .35:
                    sk.luggage(gd, (e + rnd.choice((-1.6, 1.6)), n + rnd.uniform(-1, 1), .04), 7100 + k, rnd.randint(2, 5))
            n += rnd.uniform(6.2, 9.5)
            k += 1
    sk.bus(g, gd, (-5.5, -2034.0, .04), SOUTH + .5, 7150, roll=PI / 2)
    sk.car(g, gd, (11.5, tn - 4.0, .22), SOUTH + .3, 7151, burnt=True)   # one that tried the booth lane
    for i, (e, n, yaw) in enumerate(((-9.6, tn - 22, 0.0), (9.6, tn + 30, PI), (-9.6, -2040, 0.0))):
        sk.signal(g, gd, (e, n, .04), yaw, 7160 + i)
    for i, (e, n) in enumerate(((10.2, -2262), (-10.2, -2210), (10.2, -2168), (-10.2, -2082), (10.2, -2016))):
        sk.sign(g, gd, (e, n, .04), PI / 2 if e > 0 else -PI / 2, 7170 + i)
    sk.shelter(g, gd, (-11.5, -2196.0, .2), -PI / 2, 7180)
    pe, pn = V["pad"]
    sk.crates(g, gd, (pe - 12.5, pn + 6.0, 0), 7181, 5)
    sk.crates(g, gd, (pe + 13.0, pn + 9.0, 0), 7182, 3)
    sk.luggage(gd, (pe + 6.0, pn + 12.0, .12), 7183, 7)
    for i, (e, n, yaw) in enumerate(((pe - 10.5, pn + 11.5, .6), (pe + 10.5, pn + 11.5, PI - .6))):
        at = sk.floodlight(g, gd, (e, n, 0), yaw, 7184 + i, lit=i == 0)
        if at:
            H.light("lamp", at, 1500, 60.0)
    sk.bollards(g, (pe - 8.0, pn + 13.0, 0), (pe + 8.0, pn + 13.0, 0), 9, 7186)

    # ---------------- The Stacks: quarantine
    g, gd = G["stacks"]
    b0 = S["block"]["n0"]
    sk.street(g, gd, (0, S["n0"]), (0, b0 - 15), 18.0, 7200, walk=2.6)
    sk.sandbags(g, (-9.0, b0 - 9.0, .08), 0.0, 5.0, 7201)
    sk.sandbags(g, (9.5, b0 - 10.0, .08), 0.1, 5.0, 7202)
    sk.bollards(g, (-5.5, b0 - 7.0, .08), (5.5, b0 - 7.0, .08), 6, 7203)
    sk.luggage(gd, (3.5, b0 - 4.0, .08), 7204, 8)
    sk.luggage(gd, (-14.0, b0 - 6.0, .08), 7205, 5)
    sk.floodlight(g, gd, (-13.0, b0 - 11.5, .08), .3, 7206)
    y0 = S["yard"]["n0"]
    for i, (e, n, yaw) in enumerate(((-29.0, y0 + 30.0, .1), (28.0, y0 + 60.0, PI / 2), (-25.0, y0 + 70.0, -.2))):
        tent(g, gd, (e, n, .06), yaw, rnd)
    sk.crates(g, gd, (18.0, y0 + 30.0, .06), 7210, 5)
    sk.crates(g, gd, (-12.0, y0 + 46.0, .06), 7211, 3)
    for i, a in enumerate((.6, 2.2, 3.9, 5.3)):
        sk.bench(g, (math.cos(a) * 7.6, (y0 + S["yard"]["n1"]) / 2 + math.sin(a) * 7.6, .06), a + PI / 2)
    al = S["alley"]
    sk.street(g, gd, (0, al["n0"] + 1), (0, al["n1"]), 17.6, 7220)
    for i, (e, dn, yaw, burnt) in enumerate(((-5.6, 20.0, NORTH + .1, False), (5.3, 62.0, SOUTH - .2, True), (-5.2, 112.0, NORTH, False),
                                             (5.6, 136.0, NORTH + .4, False))):
        sk.car(g, gd, (e, al["n0"] + dn, .05), yaw, 7230 + i, burnt=burnt)
    sk.luggage(gd, (2.0, al["n0"] + 24.0, .05), 7235, 5)
    for i, dn in enumerate((48.0, 96.0)):
        sk.sign(g, gd, ((-1) ** i * 8.3, al["n0"] + dn, .05), PI / 2, 7240 + i)

    # ---------------- Meridian Galleria: the shelter that was overrun
    g, gd = G["galleria"]
    f0, n0, n1 = M["fore_n0"], M["n0"], M["n1"]
    sk.bollards(g, (-20.0, f0 + 5.0, .06), (20.0, f0 + 5.0, .06), 15, 7300)
    sk.shelter(g, gd, (-29.0, f0 + 12.0, .06), PI / 2, 7301)
    sk.car(g, gd, (16.5, n0 - 13.5, .06), NORTH + .5, 7302)
    sk.car(g, gd, (-17.0, f0 + 16.0, .06), SOUTH + 1.1, 7303, burnt=True)
    for i, e in enumerate(M["doors"]):                              # the queue at each door
        sk.bollards(g, (e - 2.4, n0 + 3.0, .05), (e - 2.4, n0 + 9.0, .05), 4, 7310 + i)
        sk.bollards(g, (e + 2.4, n0 + 3.0, .05), (e + 2.4, n0 + 9.0, .05), 4, 7320 + i)
    for row, e in enumerate((-14.5, -11.5, 11.5, 14.5)):            # cots under the gallery, in rows
        for k in range(6):
            n = -1528.0 + k * 3.1
            if rnd.random() < .85:
                cot(g, gd, (e, n, .05), rnd.uniform(-.1, .1), rnd)
    sk.crates(g, gd, (-17.0, -1352.0, .05), 7330, 6)
    sk.crates(g, gd, (18.0, -1356.0, .05), 7331, 4)
    sk.luggage(gd, (0.0, -1512.0, .05), 7332, 9)
    sk.luggage(gd, (-6.0, -1396.0, .05), 7333, 6)

    # ---------------- Deepline: where people hid; the train that never left
    g, gd = G["deepline"]
    z, track = D["z"], D["track"]
    s1 = D["stair_n1"]
    for i in range(7):
        s = (-1) ** i
        cot(g, gd, (s * 13.6, s1 + 12.0 + i * 3.0, z), PI / 2, rnd)
    sk.luggage(gd, (-6.0, s1 + 24.0, z), 7400, 8)
    sk.luggage(gd, (7.0, s1 + 8.0, z), 7401, 6)
    sk.crates(g, gd, (12.0, s1 + 30.0, z), 7402, 3)
    for i, n in enumerate((-1077.3, -1060.5)):
        sk.train_car(g, gd, (-1.9, n, track), NORTH, 7410 + i)
    H.light("lamp", (-1.9, -1068.0, track + 3.0), 900, 22.0)
    sk.luggage(gd, (2.0, -1066.0, track), 7412, 5)

    # ---------------- The Sluice: where it began
    g, gd = G["sluice"]
    half, zc, pn = L["half"], L["z"], L["pump_n"]
    rk.box(g, "ru_concrete", (-half - 9.0, pn - 30.0, .2), (6.5, 16.0, .2))            # the annex's yard on the west bank
    for i, (dn, burst) in enumerate(((-42.0, True), (-36.0, False), (-30.0, True), (-24.0, True), (-18.0, False))):
        c = (-half - 6.0, pn + dn, .4)
        tank(g, gd, c, 4.6, rnd, burst)
        rk.tube(g, "ru_metal", [(c[0] + 1.2, c[1], .9), (-half - 1.2, c[1], 1.6), (-half + .6, c[1] + .5, .6), (-half + 1.6, c[1] + .8, zc + .3)], .22, 7)
        if not burst:
            H.light("bio", (c[0], c[1], 2.6), 1100)
    tank(g, gd, (-8.0, pn - 28.0, zc), 3.4, rnd, True)                                  # one that came down into the bed
    sk.crates(g, gd, (6.0, pn - 34.0, zc), 7500, 4)
    sk.signal(g, gd, (half + 3.0, L["bridges"][0] + 3.5, 0), PI, 7501)

    # ---------------- the Causeway and the Approach: the army's line, facing the canal
    g, gd = G["causeway"]
    pts = C["path"]
    for i, (a, b) in enumerate(zip(pts[1:], pts[2:])):
        sk.street(g, gd, a, b, 16.0, 7600 + i, z=.08)
    sk.carrier(g, gd, (-5.4, -352.0, .08), SOUTH + .2, 7610)
    sk.carrier(g, gd, (31.0, -500.0, .08), SOUTH - .9, 7611, burnt=True)
    sk.emplacement(g, gd, (5.5, -334.0, .08), PI, 7612)
    sk.emplacement(g, gd, (10.0, -446.0, .08), PI - .5, 7613)
    sk.sandbags(g, (-5.0, -428.0, .08), .3, 5.5, 7614)
    sk.crates(g, gd, (-6.5, -338.0, .08), 7615, 4)
    for i, (e, n, yaw, lit) in enumerate(((8.6, -346.0, PI * .75, True), (-8.6, -398.0, PI * .25, False), (24.0, -478.0, PI * .8, True))):
        at = sk.floodlight(g, gd, (e, n, .08), yaw, 7620 + i, lit=lit)
        if at:
            H.light("lamp", at, 1600, 70.0)
    g, gd = G["approach"]
    A = P.APPROACH
    sk.street(g, gd, (0, A["n0"] + 2), (0, A["n1"] - 2), 16.0, 7700)
    sk.emplacement(g, gd, (-13.5, -286.0, 0), PI + .15, 7701)
    sk.emplacement(g, gd, (14.0, -280.0, 0), PI - .15, 7702)
    sk.carrier(g, gd, (17.5, -300.0, 0), SOUTH + .6, 7703, burnt=True)
    sk.sandbags(g, (0.0, -276.0, 0), 0.0, 6.0, 7704)
    at = sk.floodlight(g, gd, (-9.5, -272.0, 0), PI * .3, 7705, lit=True)
    H.light("lamp", at, 1600, 70.0)
    sk.crates(g, gd, (9.0, -288.0, 0), 7706, 5)

    # ---------------- the Boulevard: stopped mid-afternoon
    g, gd = G["boulevard"]
    B = P.BOULEVARD
    sk.street(g, gd, (0, B["n0"] + 2), (0, B["n1"]), B["road"] * 2 - .6, 7800)
    for i, (e, n, yaw, burnt) in enumerate(((6.5, -126.0, NORTH, False), (-7.0, -116.0, SOUTH, False), (7.2, -70.0, NORTH + .2, True),
                                             (-5.0, -55.0, SOUTH - .3, False), (2.5, -62.0, NORTH + 1.2, False))):
        sk.car(g, gd, (e, n, .04), yaw, 7810 + i, burnt=burnt)
    sk.bus(g, gd, (-8.6, -72.0, .04), NORTH, 7820)
    for i, (e, n) in enumerate(((-14.6, -118.0), (14.6, -74.0))):
        sk.shelter(g, gd, (e, n, .2), -PI / 2 if e < 0 else PI / 2, 7830 + i)
    for i, (e, yaw) in enumerate(((-12.6, 0.0), (12.6, PI))):
        sk.signal(g, gd, (e, -48.0, .18), yaw, 7840 + i)
    sk.luggage(gd, (-3.0, -108.0, .04), 7850, 6)
