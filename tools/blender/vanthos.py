"""VANTHOS, the Fallen Metropolis: modular kit for the first major open-world destination (vanthos.glb, roots VX_*).

Every root has its origin at ground centre, +Y (Blender) = the side facing the street. Categories:
  Spire (central megastructure), residential, commercial, industrial, military, research, infrastructure
  (elevated highway, broken bridge, rubble, barriers, metro entrance, rooftop lift, holo ads), story set pieces
  (crashed evacuation shuttle, APC, frozen train, giant alien organism, survivor camp, wrecks) and the metro
  dungeon pieces (tunnel, junction, station). Material names are an API: facade/ribbon get window emission in
  the game, alien_glow pulses, holo_ad scrolls.
"""
import bpy, math, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import bl
from mathutils import Vector

R90 = math.pi / 2


def M():
    p = bl.palette()
    p.update(
        facade=bl.mat('facade', '#ffffff', .6, .25, image='facade_c.jpg', normal='facade_n.jpg'),
        ribbon=bl.mat('ribbon', '#ffffff', .4, .35, image='ribbon_c.jpg', normal='ribbon_n.jpg'),
        concrete=bl.mat('concrete', '#b9b3a8', 0, .85, image='concrete_c.jpg', normal='concrete_n.jpg'),
        dirty=bl.mat('vx_concrete_dark', '#6f6a62', 0, .9, image='concrete_c.jpg', normal='concrete_n.jpg'),
        rust=bl.mat('vx_rust', '#7a4a2e', .6, .7, image='panel_c.jpg', normal='panel_n.jpg'),
        panel=bl.mat('vx_panel', '#7d838b', .7, .45, image='panel_c.jpg', normal='panel_n.jpg'),
        white=bl.mat('vx_lab_white', '#e6e8ea', .1, .3, image='panel_c.jpg', normal='panel_n.jpg'),
        roof=bl.mat('roof', '#4a4d52', .3, .7, image='panel_c.jpg', normal='panel_n.jpg'),
        green=bl.mat('roof_green', '#6f8f4a', 0, .95, image='moss_c.jpg'),
        leaves=bl.mat('roof_leaves', '#4a6e34', 0, .9),
        flesh=bl.mat('alien_flesh', '#3a1f46', .1, .45),
        flesh2=bl.mat('alien_flesh_dark', '#1e1226', .2, .5),
        aglow=bl.mat('alien_glow', '#b46cff', 0, .3, emit='#b46cff', strength=6),
        acid=bl.mat('alien_acid', '#7dffb0', 0, .3, emit='#7dffb0', strength=5),
        core=bl.mat('core_glow', '#7fe8ff', 0, .2, emit='#7fe8ff', strength=14),
        holo=bl.mat('holo_ad', '#40e0ff', 0, .3, emit='#40e0ff', strength=4),
        holo2=bl.mat('holo_ad_magenta', '#ff3fb4', 0, .3, emit='#ff3fb4', strength=4),
        emer=bl.mat('emergency_light', '#ff3326', 0, .3, emit='#ff3326', strength=9),
        hazard=bl.mat('hazard', '#ffffff', .2, .6, image='hazard_c.jpg'),
        water=bl.mat('vx_water', '#24424e', .2, .05),
        cloth=bl.mat('vx_cloth', '#6b5d48', 0, .9),
        track=bl.mat('vx_track', '#2c2c2e', .8, .5),
    )
    return p


def B(name, size, loc, m, bevel=0.0, rot=(0, 0, 0)):
    return bl.box(name, size, loc, m, bevel=bevel, rot=rot)


def C(name, r, h, loc, m, verts=16, rot=(0, 0, 0), r2=None):
    return bl.cyl(name, r, h, loc, m, verts, rot=rot, r2=r2)


def fac(o, s=24):
    bl.uv_box(o, s)
    return o


def finish(name, x0, P, uv=None):
    r = bl.empty(name, (x0, 0, 0))
    for o in P:
        bl.apply_all(o)
    g = bl.join(P, name + '_mesh')
    if uv:
        bl.uv_box(g, uv)
    g.parent = r
    return r


RG = bl.rng(77)


def jag(m, cx, cy, z, w, d, n=10, seed=0):
    """Broken top: jagged slabs, bent rebar and debris on a cut floor."""
    rg = bl.rng(seed)
    P = []
    for k in range(n):
        x = cx + (rg.random() - .5) * w; y = cy + (rg.random() - .5) * d
        h = 1 + rg.random() * 7
        P.append(B('shard', (2 + rg.random() * 5, 1 + rg.random() * 3, h), (x, y, z + h / 2 - .5), m, rot=(rg.random() * .5, rg.random() * .5, rg.random() * 3)))
    for k in range(n // 2):
        x = cx + (rg.random() - .5) * w; y = cy + (rg.random() - .5) * d
        P.append(C('rebar', .08, 3 + rg.random() * 3, (x, y, z + 1.5), M()['rust'], 5, rot=(rg.random() * .7, rg.random() * .7, 0)))
    return P


def rubble(m, cx, cy, z, r, n, seed):
    rg = bl.rng(seed)
    P = []
    for k in range(n):
        a = rg.random() * 6.28; d = rg.random() * r
        s = .6 + rg.random() * 2.4
        P.append(B('rubble', (s * 1.6, s, s * .7), (cx + math.cos(a) * d, cy + math.sin(a) * d, z + s * .3), m, rot=(rg.random(), rg.random(), rg.random() * 3)))
    return P


def growth(m, cx, cy, z, size, seed, up=0.0):
    """Alien growth: lumpy masses, climbing tendrils and glowing pustules."""
    rg = bl.rng(seed)
    P = []
    for k in range(int(5 + size)):
        a = rg.random() * 6.28; d = rg.random() * size
        r = size * (.25 + rg.random() * .35)
        P.append(bl.sphere('mass', r, (cx + math.cos(a) * d, cy + math.sin(a) * d, z + r * .3), m['flesh'] if k % 3 else m['flesh2'], 10, 7,
                           scale=(1, 1, .6)))
    for k in range(int(3 + size / 2)):
        a = rg.random() * 6.28
        x, y, zz = cx + math.cos(a) * size * .5, cy + math.sin(a) * size * .5, z
        r = size * .12
        for s in range(6):
            nx = x + (rg.random() - .5) * size * .4; ny = y + (rg.random() - .5) * size * .4
            nz = zz + size * (.3 + rg.random() * .4) + up * .2
            v = Vector((nx - x, ny - y, nz - zz)); L = v.length
            o = C('tendril', r, L, ((x + nx) / 2, (y + ny) / 2, (zz + nz) / 2), m['flesh'], 7, r2=r * .75)
            o.rotation_mode = 'QUATERNION'; o.rotation_quaternion = v.to_track_quat('Z', 'Y')
            P.append(o)
            x, y, zz, r = nx, ny, nz, r * .8
    for k in range(int(4 + size)):
        a = rg.random() * 6.28; d = rg.random() * size * .8
        P.append(bl.sphere('pod', size * .07 + .3, (cx + math.cos(a) * d, cy + math.sin(a) * d, z + rg.random() * size * .5 + .3),
                           m['aglow'] if k % 2 else m['acid'], 8, 6))
    return P


def windows_tower(name, m, w, d, h, mat_key='facade', s=22):
    return fac(B(name, (w, d, h), (0, 0, h / 2), m[mat_key]), s)


# ====================================================================== the Spire
def spire(x0):
    m = M(); P = []
    # circular foundation ring with buttresses
    P.append(fac(C('found', 92, 26, (0, 0, 13), m['dirty'], 48), 30))
    P.append(C('foundcap', 88, 3, (0, 0, 27.5), m['panel'], 48))
    for k in range(16):
        a = k / 16 * 6.283
        P.append(B('buttress', (10, 26, 34), (math.cos(a) * 92, math.sin(a) * 92, 15), m['concrete'], rot=(0, 0, a + R90)))
        P.append(B('buttglow', (10.4, 1, 1), (math.cos(a) * 99, math.sin(a) * 99, 26), m['cyan'], rot=(0, 0, a + R90)))
    # central core tower and the exposed energy core
    P.append(fac(C('core', 24, 330, (0, 0, 28 + 165), m['ribbon'], 24), 28))
    for z in range(60, 340, 30):
        P.append(C('coreband', 25, 2, (0, 0, z), m['panel'], 24))
    for k in range(8):
        a = k / 8 * 6.283
        P.append(B('cage', (2.4, 2.4, 50), (math.cos(a) * 20, math.sin(a) * 20, 358 + 25), m['dark'], rot=(math.cos(a) * .15, math.sin(a) * .15, 0)))
    P.append(bl.sphere('energycore', 15, (0, 0, 380), m['core'], 32, 20))
    P.append(bl.torus('corering', 22, 1.2, (0, 0, 380), m['cyan'], maj=48, mn=8))
    P.append(bl.torus('corering2', 19, .8, (0, 0, 380), m['cyan'], rot=(R90 * .6, 0, 0), maj=48, mn=8))
    P.append(C('crown', 8, 14, (0, 0, 412), m['dark'], 12, r2=2))
    # satellite towers (two of them broken)
    towers = [(0, 240, False), (1.26, 290, False), (2.51, 300, True), (3.77, 260, False), (5.03, 230, True)]
    for i, (a, h, broken) in enumerate(towers):
        x, y = math.cos(a) * 52, math.sin(a) * 52
        hh = h * (.62 if broken else 1)
        o = fac(B('tower', (30, 30, hh), (x, y, 28 + hh / 2), m['facade'], rot=(0, 0, a)), 24); P.append(o)
        P.append(B('fin', (2, 32, hh), (x + math.cos(a) * 15, y + math.sin(a) * 15, 28 + hh / 2), m['panel'], rot=(0, 0, a)))
        if broken:
            P += jag(m['dirty'], x, y, 28 + hh, 26, 26, 14, i)
            # the fallen top section leaning against its neighbour
            P.append(fac(B('fallen', (28, 28, h * .3), (x + math.cos(a + .6) * 30, y + math.sin(a + .6) * 30, 28 + hh * .7), m['facade'],
                           rot=(.45, .2, a)), 24))
        else:
            P.append(B('towercap', (24, 24, 6), (x, y, 28 + hh + 3), m['roof'], rot=(0, 0, a)))
            P.append(C('mast', .8, 30, (x, y, 28 + hh + 21), m['steel'], 8))
        # skybridges to the core
        for zb in (110, 170, 230):
            if zb < hh:
                bx, by = math.cos(a) * 33, math.sin(a) * 33
                P.append(B('skybridge', (18, 6, 4), (bx, by, 28 + zb), m['ribbon'], rot=(0, 0, a)))
                P.append(B('sbglow', (18, 6.4, .4), (bx, by, 28 + zb - 2), m['cyan'], rot=(0, 0, a)))
    # suspended walkway ring
    P.append(bl.torus('walkring', 70, 1.6, (0, 0, 150), m['panel'], maj=64, mn=6))
    for k in range(12):
        a = k / 12 * 6.283
        P.append(C('hanger', .4, 120, (math.cos(a) * 70, math.sin(a) * 70, 210), m['steel'], 6))
    # alien growth climbing the base and up the core
    P += growth(m, 60, -40, 28, 22, 3, up=80)
    P += growth(m, -55, 50, 28, 18, 4, up=60)
    P += growth(m, 10, 90, 0, 16, 5)
    for k in range(10):
        a = k * .9; z0 = 30 + k * 18
        P.append(C('vine', 3.2 - k * .2, 24, (math.cos(a) * 25, math.sin(a) * 25, z0 + 12), m['flesh'], 8, rot=(.25, 0, a)))
        P.append(bl.sphere('vinepod', 2.4, (math.cos(a) * 26, math.sin(a) * 26, z0 + 22), m['aglow'], 10, 8))
    return finish('VX_spire', x0, P)


# ====================================================================== residential
def apartment(name, x0, floors, w, d, ruined=False, seed=0):
    m = M(); P = []
    h = floors * 3.2
    hh = h * (.55 if ruined else 1)
    P.append(windows_tower('body', m, w, d, hh))
    P.append(B('shopband', (w + .4, d + .4, 4), (0, 0, 2), m['concrete']))
    P.append(B('shopglass', (w - 2, .3, 2.8), (0, -d / 2 - .2, 1.7), m['glass']))
    P.append(B('awning', (w - 1, 2.4, .25), (0, -d / 2 - 1.2, 3.8), m['rust'] if ruined else m['panel'], rot=(-.15, 0, 0)))
    P.append(B('sign', (w * .4, .3, 1.4), (-w * .2, -d / 2 - .3, 5), m['magenta'] if seed % 2 else m['amber']))
    for z in range(6, int(hh) - 2, 6):
        P.append(B('balcony', (w * .7, 1.6, .3), (0, -d / 2 - .8, z), m['concrete']))
        P.append(B('rail', (w * .7, .08, 1.0), (0, -d / 2 - 1.55, z + .6), m['steel']))
    # external staircase on the side
    for z in range(0, int(hh) - 3, 3):
        P.append(B('stair', (2, 3.2, .25), (w / 2 + 1.1, ((z // 3) % 2 - .5) * 1.4, z + 1.5), m['rust'], rot=(.5 if (z // 3) % 2 else -.5, 0, 0)))
    P.append(B('stairrail', (.1, 3.4, hh), (w / 2 + 2.1, 0, hh / 2), m['rust']))
    if ruined:
        P += jag(m['dirty'], 0, 0, hh, w * .9, d * .9, 10, seed)
        P += rubble(m['dirty'], 0, -d / 2 - 6, 0, 8, 14, seed + 1)
        P.append(B('barricade', (w * .5, .8, 2.6), (0, -d / 2 - 2.2, 1.3), m['rust'], rot=(0, 0, .05)))
    else:
        P.append(B('garden', (w - 2, d - 2, .5), (0, 0, hh + .25), m['green']))
        rg = bl.rng(seed)
        for k in range(8):
            P.append(bl.sphere('shrub', 1 + rg.random(), ((rg.random() - .5) * (w - 4), (rg.random() - .5) * (d - 4), hh + 1.1), m['leaves'], 8, 6, scale=(1, 1, .7)))
        P.append(C('watertank', 2, 3, (w / 2 - 3, d / 2 - 3, hh + 1.5), m['rust'], 12))
    return finish(name, x0, P)


def market_row(x0):
    m = M(); P = [windows_tower('row', m, 44, 14, 16, 'facade', 14)]
    for k in range(6):
        x = -18 + k * 7.2
        P.append(B('stall', (5.5, 3, .2), (x, -9, 3), m['cloth'] if k % 2 else m['rust'], rot=(-.2, 0, 0)))
        P.append(B('counter', (5, 1.2, 1.1), (x, -8.6, .55), m['panel']))
        P.append(B('neon', (3, .2, .8), (x, -7.2, 5.2), [m['cyan'], m['magenta'], m['amber']][k % 3]))
    return finish('VX_res_market', x0, P)


# ====================================================================== commercial
def skyscraper(name, x0, h, w, ruined=False, round_=False, seed=0):
    m = M(); P = []
    P.append(fac(B('atrium', (w + 12, w + 12, 12), (0, 0, 6), m['ribbon']), 18))
    P.append(B('atriumroof', (w + 13, w + 13, .8), (0, 0, 12.2), m['panel']))
    hh = h * (.6 if ruined else 1)
    if round_:
        P.append(fac(C('shaft', w / 2, hh, (0, 0, 12 + hh / 2), m['ribbon'], 24), 24))
    else:
        P.append(fac(B('shaft', (w, w, hh), (0, 0, 12 + hh / 2), m['ribbon']), 24))
    for z in range(30, int(hh), 40):
        P.append(B('band', (w + .6, w + .6, 1.2), (0, 0, 12 + z), m['panel']) if not round_ else C('band', w / 2 + .4, 1.2, (0, 0, 12 + z), m['panel'], 24))
    if ruined:
        P += jag(m['dirty'], 0, 0, 12 + hh, w, w, 14, seed)
        P.append(fac(B('topchunk', (w * .9, w * .9, h * .25), (w * .9, w * .4, 12 + hh * .55), m['ribbon'], rot=(.6, .3, .4)), 24))
        P += rubble(m['dirty'], w * .9, -w * .5, 0, 16, 20, seed + 3)
    else:
        P.append(B('crown', (w * .8, w * .8, 6), (0, 0, 12 + hh + 3), m['roof']))
        P.append(B('crownglow', (w * .82, w * .82, .5), (0, 0, 12 + hh + .6), m['cyan']))
    return finish(name, x0, P)


def skybridge(x0):
    m = M()
    P = [fac(B('tube', (6, 40, 4.5), (0, 0, 0), m['ribbon']), 10), B('floor', (6.4, 40, .6), (0, 0, -2.4), m['panel']),
         B('glow', (6.6, 40, .2), (0, 0, -2.8), m['cyan'])]
    return finish('VX_skybridge', x0, P)


# ====================================================================== industrial
def factory(x0):
    m = M(); P = [fac(B('hall', (60, 40, 16), (0, 0, 8), m['dirty']), 12)]
    for k in range(6):
        P.append(B('sawtooth', (10, 40, 4), (-25 + k * 10, 0, 18), m['rust'], rot=(0, .35, 0)))
    for x in (-18, 14):
        P.append(C('chimney', 2.6, 46, (x, 14, 23), m['dirty'], 16, r2=2))
        P.append(C('chimneyband', 2.9, 1, (x, 14, 40), m['red'], 16))
    for k in range(4):
        P.append(C('pipe', .7, 58, (0, -20.8, 4 + k * 2.4), m['rust'], 10, rot=(0, R90, 0)))
    P.append(B('walkway', (60, 2, .3), (0, -21.5, 13), m['panel']))
    P.append(B('rail', (60, .1, 1), (0, -22.4, 13.6), m['steel']))
    P.append(B('door', (10, .4, 9), (0, -20.2, 4.5), m['hazard']))
    return finish('VX_ind_factory', x0, P)


def refinery(x0):
    m = M(); P = []
    for k, (x, y, r, h) in enumerate(((-14, -8, 7, 18), (2, -8, 7, 18), (-14, 10, 5, 24), (8, 10, 6, 14))):
        P.append(C('tank', r, h, (x, y, h / 2), m['white'] if k % 2 else m['panel'], 24))
        P.append(C('tankring', r + .3, .6, (x, y, h * .7), m['rust'], 24))
    for k in range(5):
        P.append(C('rack', .5, 40, (0, -18 + k * 1.2, 7), m['rust'], 8, rot=(0, R90, 0)))
    for x in (-18, 0, 18):
        P.append(B('rackpost', (.6, 7, 8), (x, -15.6, 4), m['rust']))
    P.append(C('flare', 1, 40, (20, 16, 20), m['dark'], 10))
    P.append(bl.sphere('flame', 1.6, (20, 16, 41), m['amber'], 10, 8))
    return finish('VX_ind_refinery', x0, P)


def warehouse(x0):
    m = M(); P = [fac(B('wh', (50, 30, 12), (0, 0, 6), m['panel']), 10), B('roof', (51, 31, 1), (0, 0, 12.4), m['rust'])]
    for k in range(4):
        P.append(B('rollup', (7, .3, 7), (-18 + k * 12, -15.1, 3.5), m['dark']))
        P.append(B('stripe', (7, .35, .6), (-18 + k * 12, -15.15, 7.3), m['hazard']))
    for k in range(6):
        P.append(B('crate', (2.4, 2.4, 2.4), (-20 + k * 7, -19, 1.2), m['rust'] if k % 2 else m['panel'], rot=(0, 0, k * .3)))
    return finish('VX_ind_warehouse', x0, P)


def power_station(x0):
    m = M(); P = []
    P.append(C('cooling', 22, 50, (-12, 0, 25), m['concrete'], 32, r2=15))
    P.append(C('coolinglip', 15.5, 4, (-12, 0, 52), m['concrete'], 32, r2=17))
    P.append(fac(B('turbinehall', (24, 30, 18), (20, 0, 9), m['dirty']), 12))
    for k in range(4):
        P.append(B('transformer', (4, 3, 4), (20 + (k % 2) * 8 - 4, -22 - (k // 2) * 6, 2), m['panel']))
        P.append(C('insulator', .4, 3, (20 + (k % 2) * 8 - 4, -22 - (k // 2) * 6, 5.5), m['cyan'], 8))
    return finish('VX_ind_power', x0, P)


# ====================================================================== military
def bunker(x0):
    m = M(); P = [B('bunker', (28, 18, 6), (0, 0, 3), m['dirty'], bevel=1.2), B('roofslab', (30, 20, 1.4), (0, 0, 6.6), m['concrete'], bevel=.5)]
    for k in range(4):
        P.append(B('slit', (4, .4, .6), (-9 + k * 6, -9.1, 4.2), m['dark']))
    P.append(B('blastdoor', (6, .8, 4.5), (0, -9.2, 2.25), m['panel']))
    P.append(B('doorstripe', (6.2, .9, .5), (0, -9.25, 4.6), m['hazard']))
    P.append(B('ramp', (8, 10, .5), (0, -14, .1), m['concrete'], rot=(.1, 0, 0)))
    return finish('VX_mil_bunker', x0, P)


def watchtower(x0):
    m = M(); P = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            P.append(B('leg', (.6, .6, 16), (sx * 2.5, sy * 2.5, 8), m['panel'], rot=(sy * .06, -sx * .06, 0)))
    P += [B('cabin', (7, 7, 3.2), (0, 0, 17.6), m['dirty']), B('cabinroof', (8, 8, .5), (0, 0, 19.5), m['panel']),
          B('window', (7.1, 7.1, 1), (0, 0, 18), m['glass']), bl.sphere('searchlight', .7, (0, -3.8, 18.6), m['amber'], 10, 8)]
    for z in range(2, 16, 3):
        P.append(B('ladder', (.8, .1, .1), (0, 2.9, z), m['steel']))
    return finish('VX_mil_tower', x0, P)


def wall_segment(x0):
    m = M(); P = [B('wall', (20, 3, 8), (0, 0, 4), m['dirty'], bevel=.3), B('walk', (20, 2, .3), (0, 2, 6.5), m['panel']),
                  B('parapet', (20, .5, 1.2), (0, -1.3, 8.6), m['concrete'])]
    for k in range(4):
        P.append(B('hazardstripe', (2, 3.1, .6), (-7.5 + k * 5, 0, 1.2), m['hazard']))
    return finish('VX_mil_wall', x0, P)


def gate(x0):
    m = M(); P = []
    for sx in (-1, 1):
        P.append(B('pillar', (4, 5, 12), (sx * 9, 0, 6), m['dirty'], bevel=.4))
        P.append(bl.sphere('gatelight', .6, (sx * 9, -2.6, 11), m['red'], 8, 6))
    P += [B('gateL', (7, 1, 9), (-3.6, 0, 4.5), m['panel']), B('gateR', (7, 1, 9), (3.6, 0, 4.5), m['panel']),
          B('lintel', (22, 5, 2), (0, 0, 13), m['concrete']), B('stripe', (14.4, 1.1, .8), (0, 0, 1), m['hazard'])]
    return finish('VX_mil_gate', x0, P)


def depot(x0):
    m = M(); P = [B('mound', (40, 26, 7), (0, 0, 3.5), m['dirty'], bevel=3), B('front', (40, 2, 7), (0, -13, 3.5), m['concrete'])]
    for k in range(3):
        P.append(B('blastdoor', (7, .6, 5), (-12 + k * 12, -14.2, 2.5), m['panel']))
        P.append(B('lamp', (1, .4, .4), (-12 + k * 12, -14.4, 5.6), m['amber']))
    for k in range(5):
        P.append(B('ammocrate', (2, 1.4, 1.2), (-15 + k * 7, -18, .6), m['rust'], rot=(0, 0, k * .4)))
    return finish('VX_mil_depot', x0, P)


# ====================================================================== research
def lab(x0):
    m = M(); P = [fac(B('lab', (40, 30, 20), (0, 0, 10), m['white']), 10), B('band', (40.4, 30.4, 1.6), (0, 0, 14), m['dark']),
                  B('glassband', (40.6, 30.6, 3), (0, 0, 8), m['glass']), B('roofunit', (14, 10, 4), (8, 4, 22), m['dark'])]
    P.append(B('stripglow', (40.8, .2, .4), (0, -15.3, 15.2), m['cyan']))
    P.append(B('entrance', (10, 4, 6), (0, -17, 3), m['dark']))
    P += growth(m, -16, -12, 0, 6, 9)
    return finish('VX_lab_a', x0, P)


def containment(x0):
    m = M(); P = [C('base', 8, 1.2, (0, 0, .6), m['dark'], 32), C('chamber', 6.5, 9, (0, 0, 5.7), m['glass'], 32),
                  C('cap', 8, 1.6, (0, 0, 11), m['dark'], 32), bl.torus('ring', 7, .3, (0, 0, 1.4), m['acid'], maj=48, mn=6)]
    P += growth(m, 0, 0, 1.2, 3.5, 11)
    for k in range(6):
        a = k / 6 * 6.283
        P.append(B('strut', (.6, .6, 10), (math.cos(a) * 7.5, math.sin(a) * 7.5, 6), m['white']))
    return finish('VX_lab_containment', x0, P)


def hospital(x0):
    m = M(); P = [fac(B('wing', (50, 22, 24), (0, 0, 12), m['white']), 12), fac(B('tower', (18, 18, 40), (16, 6, 20), m['white']), 12)]
    for z in range(4, 40, 4):
        P.append(B('glassrow', (18.4, 18.4, 1.2), (16, 6, z), m['glass']))
    P += [B('canopy', (16, 6, .6), (-10, -14, 5), m['dark']), B('crossH', (6, .4, 1.8), (-10, -11.3, 18), m['emer']),
          B('crossV', (1.8, .4, 6), (-10, -11.3, 18), m['emer'])]
    for k in range(6):
        P.append(bl.sphere('emergency', .4, (-22 + k * 9, -11.4, 3.6), m['emer'], 8, 6))
    P.append(B('ambulance', (2.6, 6, 2.4), (-14, -18, 1.3), m['white'], bevel=.2, rot=(0, 0, .4)))
    return finish('VX_hospital', x0, P)


# ====================================================================== infrastructure
def highway(name, x0, broken=False):
    m = M(); P = []
    L, W, H = 50, 25, 12
    if broken:
        P += [B('deck', (W, L * .45, 1.6), (0, L * .27, H - .8), m['concrete']),
              B('fallen', (W, L * .5, 1.6), (0, -L * .22, H * .45), m['concrete'], rot=(-.42, .05, 0))]
        P += rubble(m['dirty'], 0, -L * .4, 0, 8, 16, 21)
        P += jag(m['dirty'], 0, 2, H, W * .8, 3, 8, 22)
    else:
        P.append(B('deck', (W, L, 1.6), (0, 0, H - .8), m['concrete']))
        P.append(B('asphalt', (W - 3, L, .1), (0, 0, H + .05), m['roof']))
    for sx in (-1, 1):
        P.append(B('barrier', (.6, L * (.45 if broken else 1), 1.1), (sx * (W / 2 - .3), L * .27 if broken else 0, H + .55), m['concrete']))
        P.append(B('glow', (.2, L * (.45 if broken else 1), .15), (sx * (W / 2 - .8), L * .27 if broken else 0, H + .15), m['cyan']))
    for y in ((L * .3,) if broken else (-L * .3, L * .3)):
        P.append(B('pier', (3, 3, H - 1.6), (0, y, (H - 1.6) / 2), m['concrete']))
        P.append(B('piercap', (W * .7, 4, 1.4), (0, y, H - 2.3), m['concrete']))
    return finish(name, x0, P)


def broken_bridge(x0):
    m = M(); P = [B('deckL', (16, 30, 1.4), (0, 22, 6), m['concrete']), B('deckR', (16, 26, 1.4), (0, -24, 3), m['concrete'], rot=(.25, 0, 0)),
                  B('pierL', (3, 3, 6), (0, 30, 3), m['concrete'])]
    P += jag(m['dirty'], 0, 8, 6.5, 14, 2, 8, 31) + rubble(m['dirty'], 0, -6, -2, 8, 12, 32)
    for sx in (-1, 1):
        P.append(B('rail', (.3, 30, 1), (sx * 7.8, 22, 7.2), m['steel']))
    return finish('VX_bridge_broken', x0, P)


def roadblock(x0):
    m = M(); P = []
    for k in range(7):
        P.append(B('jersey', (3.6, .8, 1.1), (-12 + k * 4, (k % 2) * .6, .55), m['concrete'], rot=(0, 0, (k % 3 - 1) * .2)))
    P += [B('wreck', (2, 4.6, 1.4), (-4, -5, .9), m['rust'], bevel=.3, rot=(0, .2, .7)), B('wreck2', (2, 4.6, 1.4), (6, 4, .9), m['dark'], bevel=.3, rot=(0, -.1, -.4))]
    P += rubble(m['dirty'], 0, 0, 0, 10, 10, 41)
    return finish('VX_roadblock', x0, P)


def rubble_pile(x0):
    m = M(); return finish('VX_rubble', x0, rubble(m['dirty'], 0, 0, 0, 7, 24, 51) + jag(m['concrete'], 0, 0, 0, 10, 10, 6, 52))


def metro_entrance(x0):
    m = M(); P = [B('frame', (6, 10, .5), (0, 0, 3.4), m['panel']), B('postL', (.4, .4, 3.4), (-2.8, -4.6, 1.7), m['panel']),
                  B('postR', (.4, .4, 3.4), (2.8, -4.6, 1.7), m['panel']), B('stairs', (5, 9, .4), (0, 0, -1.6), m['concrete'], rot=(.4, 0, 0)),
                  B('pit', (5.4, 9.4, .2), (0, 0, .02), m['dark']), B('sign', (5, .2, 1), (0, -4.8, 4.2), m['cyan']),
                  B('railL', (.1, 9, 1), (-2.6, 0, .5), m['steel']), B('railR', (.1, 9, 1), (2.6, 0, .5), m['steel'])]
    return finish('VX_metro_entrance', x0, P)


def lift(x0):
    m = M(); P = [C('pad', 2, .3, (0, 0, .15), m['dark'], 24), bl.torus('padglow', 1.8, .1, (0, 0, .32), m['cyan'], maj=32, mn=6)]
    for sx in (-1, 1):
        P.append(B('rail', (.3, .3, 6), (sx * 2.2, 0, 3), m['panel']))
    P.append(B('beam', (4.8, .4, .4), (0, 0, 6), m['panel']))
    P.append(B('beacon', (.6, .6, .6), (0, 0, 6.5), m['cyan']))
    return finish('VX_lift', x0, P)


def holo_ad(name, x0, mat):
    m = M(); P = [B('pole', (1, 1, 30), (0, 0, 15), m['dark']), B('frame', (22, 1.2, 13), (0, 0, 36), m['dark']),
                  B('panel', (21, .3, 12), (0, -.7, 36), m[mat])]
    return finish(name, x0, P)


# ====================================================================== story set pieces
def shuttle(x0):
    m = M(); P = [C('fuselage', 3.2, 22, (0, 0, 2.6), m['white'], 20, rot=(R90, .25, .3)),
                  C('nose', 3.2, 5, (2.4, -12.5, 1.6), m['white'], 20, rot=(R90 + .25, .25, .3), r2=.8),
                  B('wingL', (12, 6, .5), (-6, 1, 1.6), m['panel'], rot=(.1, .3, .3)), B('wingR', (6, 5, .5), (7, 4, .7), m['panel'], rot=(-.4, -.2, .9)),
                  B('stripe', (.2, 18, 1), (3.3, 0, 3.2), m['amber'], rot=(0, .25, .3)), B('hatch', (2, 3, 2.6), (-3, 2, 1.4), m['dark'], rot=(0, 0, .3))]
    P += rubble(m['dirty'], 0, -14, 0, 6, 8, 61)
    rg = bl.rng(62)
    for k in range(18):
        a = rg.random() * 6.28; d = 4 + rg.random() * 10
        P.append(B('luggage', (.5 + rg.random() * .5, .25 + rg.random() * .2, .7 + rg.random() * .3), (math.cos(a) * d, math.sin(a) * d + 6, .3),
                   [m['rust'], m['cloth'], m['panel'], m['red']][k % 4], rot=(rg.random() * 1.5, rg.random(), rg.random() * 3)))
    return finish('VX_shuttle', x0, P)


def apc(x0):
    m = M(); P = [B('hull', (3.2, 7.5, 2.2), (0, 0, 1.9), m['panel'], bevel=.3), B('nose', (3.2, 2, 1.4), (0, -4.2, 1.5), m['panel'], rot=(-.5, 0, 0)),
                  C('turret', 1.1, .8, (0, .5, 3.4), m['dark'], 12), C('barrel', .12, 3, (0, -1.4, 3.5), m['dark'], 8, rot=(R90, 0, 0)),
                  B('door', (2, .2, 1.6), (0, 3.8, 1.2), m['dark'], rot=(-.9, 0, 0))]
    for sx in (-1, 1):
        for y in (-2.5, 0, 2.5):
            P.append(C('wheel', .75, .6, (sx * 1.7, y, .75), m['rubber'], 14, rot=(0, R90, 0)))
    return finish('VX_apc', x0, P)


def train(x0):
    m = M(); P = []
    for k, (y, rx, rz) in enumerate(((0, 0, 0), (21, .05, .15), (41, .18, .3))):
        P.append(fac(B('car', (3.2, 20, 3.6), (0, y, 2.2 + k * .3), m['white'], bevel=.4, rot=(rx, 0, rz)), 8))
        P.append(B('windows', (3.3, 18, 1), (0, y, 3 + k * .3), m['glass'], rot=(rx, 0, rz)))
        P.append(B('stripe', (3.3, 20, .3), (0, y, 1.6 + k * .3), m['cyan'], rot=(rx, 0, rz)))
    P += [B('rails', (2, 70, .2), (0, 20, .1), m['track'])]
    P += rubble(m['dirty'], 0, 48, 0, 8, 20, 71)
    return finish('VX_train', x0, P)


def organism(x0):
    """Enormous alien organism: a trunk of flesh bursting through a ruined skyscraper."""
    m = M(); P = []
    P.append(fac(B('host', (28, 28, 70), (0, 0, 35), m['facade']), 22))
    P += jag(m['dirty'], 0, 0, 70, 26, 26, 14, 81)
    P.append(C('trunk', 9, 90, (4, -2, 45), m['flesh'], 16, r2=5))
    for k in range(9):
        a = k * .7; z = 20 + k * 9
        v = Vector((math.cos(a) * 16, math.sin(a) * 16, -22 - k * 2)); L = v.length
        o = C('arm', 3 - k * .2, L, (4 + v.x / 2, -2 + v.y / 2, 60 + k * 4 + v.z / 2), m['flesh2'], 10, r2=.8)
        o.rotation_mode = 'QUATERNION'; o.rotation_quaternion = v.to_track_quat('Z', 'Y'); P.append(o)
        P.append(bl.sphere('pustule', 1.6, (4 + v.x * .5, -2 + v.y * .5, 60 + k * 4 + v.z * .5), m['aglow'], 10, 8))
    rg = bl.rng(83)
    for k in range(9):                                       # irregular crown of flesh with spines, no face
        a = rg.random() * 6.28; d = rg.random() * 9
        r = 4 + rg.random() * 6
        P.append(bl.sphere('crownmass', r, (4 + math.cos(a) * d, -2 + math.sin(a) * d, 84 + rg.random() * 14), m['flesh'] if k % 2 else m['flesh2'],
                           12, 9, scale=(1, .8 + rg.random() * .4, .7 + rg.random() * .5)))
    for k in range(10):
        a = rg.random() * 6.28; t = rg.random() * .9 + .2
        v = Vector((math.cos(a) * t, math.sin(a) * t, .6 + rg.random())); v.normalize()
        L = 10 + rg.random() * 14
        o = C('spine', 1.3, L, (4 + v.x * (8 + L / 2), -2 + v.y * (8 + L / 2), 90 + v.z * L / 2), m['flesh2'], 8, r2=.1)
        o.rotation_mode = 'QUATERNION'; o.rotation_quaternion = v.to_track_quat('Z', 'Y'); P.append(o)
    for k in range(14):
        a = rg.random() * 6.28
        P.append(bl.sphere('glowpod', 1 + rg.random() * 1.5, (4 + math.cos(a) * 10, -2 + math.sin(a) * 10, 80 + rg.random() * 20), m['aglow'], 8, 6))
    P += growth(m, 0, 0, 0, 20, 82)
    return finish('VX_organism', x0, P)


def growth_cluster(name, x0, size, seed):
    m = M(); return finish(name, x0, growth(m, 0, 0, 0, size, seed))


def camp(x0):
    m = M(); P = []
    for k in range(4):
        a = k * 1.4
        P.append(B('tent', (4, 3, 2.4), (math.cos(a) * 7, math.sin(a) * 7, 1.2), m['cloth'], rot=(0, .2, a)))
    P += [C('fire', .9, .4, (0, 0, .2), m['dirty'], 10), bl.sphere('flame', .6, (0, 0, .7), m['amber'], 8, 6),
          B('table', (2, 1, .9), (3, -2, .45), m['rust'])]
    for k in range(6):
        P.append(B('crate', (1.2, 1.2, 1.2), (-6 + k * 2.2, 9, .6), m['panel'] if k % 2 else m['rust'], rot=(0, 0, k)))
    for k in range(8):
        a = k / 8 * 6.28
        P.append(bl.sphere('stringlight', .15, (math.cos(a) * 10, math.sin(a) * 10, 3.5), m['amber'], 6, 4))
    return finish('VX_camp', x0, P)


# ====================================================================== the Operation (operation.js): mission props
# Material names are an API: the game recolours / dims `conduit_glow`, `relay_glow`, `terminal_screen` and
# `reliquary_glow` per instance (state lights), so each prop keeps its own glow material.
def conduit(x0):
    """Shield conduit: a hexagonal pylon that feeds the Spire Warden's barrier (shootable; the core glows magenta)."""
    m = M(); P = []
    cg = bl.mat('conduit_glow', '#ff3fb4', 0, .3, emit='#ff3fb4', strength=8)
    P += [C('base', 1.6, .45, (0, 0, .22), m['dark'], 6), C('plinth', 1.2, .7, (0, 0, .8), m['panel'], 6, r2=1.05)]
    for k in range(3):
        a = k * 2.0944 + .5
        P.append(B('fin', (1.3, .32, 3.8), (math.cos(a) * .95, math.sin(a) * .95, 3.0), m['panel'], bevel=.06, rot=(0, 0, a)))
        P.append(B('finglow', (.9, .05, 2.6), (math.cos(a) * 1.13, math.sin(a) * 1.13, 3.0), cg, rot=(0, 0, a)))
        P.append(C('cable', .1, 2.4, (math.cos(a + 1.05) * 1.9, math.sin(a + 1.05) * 1.9, .12), m['rubber'], 6, rot=(R90, 0, a + 1.05 + R90)))
    P += [C('core', .38, 3.4, (0, 0, 2.9), cg, 12), C('collarlo', .62, .35, (0, 0, 1.3), m['dark'], 12), C('collarhi', .62, .35, (0, 0, 4.5), m['dark'], 12),
          bl.torus('halo', 1.0, .08, (0, 0, 4.95), cg, maj=28, mn=6), C('cap', .75, .45, (0, 0, 5.0), m['dark'], 6, r2=.3),
          bl.sphere('emitter', .3, (0, 0, 5.45), cg, 10, 8)]
    return finish('VX_conduit', x0, P)


def relay(x0):
    """Signal relay mast: braced lattice tower, dish and a field console (relay_glow: amber dead, cyan linked)."""
    m = M(); P = []
    rg = bl.mat('relay_glow', '#ffae2f', 0, .3, emit='#ffae2f', strength=7)
    P.append(B('slab', (5.5, 5.5, .35), (0, 0, .17), m['dirty']))
    H = 15
    for sx in (-1, 1):
        for sy in (-1, 1):
            P.append(C('leg', .13, H, (sx * 1.0, sy * 1.0, H / 2 + .3), m['steel'], 6))
    for z in range(2, H, 3):
        for s in (-1, 1):
            P.append(B('brace', (2.1, .1, .1), (0, s * 1.0, z + .3), m['steel']))
            P.append(B('brace', (.1, 2.1, .1), (s * 1.0, 0, z + .3), m['steel']))
            P.append(B('diag', (2.6, .07, .07), (0, s * 1.0, z + 1.8), m['steel'], rot=(0, .95, 0)))
    P += [B('deck', (2.8, 2.8, .15), (0, 0, H + .35), m['panel']),
          C('dish', 2.3, .35, (0, -1.2, H + 2.2), m['steel'], 24, rot=(1.05, 0, 0), r2=.5),
          C('feed', .06, 1.8, (0, -1.9, H + 2.8), m['steel'], 5, rot=(1.05, 0, 0)),
          C('mast', .1, 3.4, (.9, .9, H + 2.0), m['steel'], 6), bl.sphere('beacon', .28, (.9, .9, H + 3.8), rg, 10, 8),
          B('lamp', (.4, .15, .25), (0, -1.05, 8.3), rg),
          B('console', (1.6, .8, 1.0), (0, -3.1, .85), m['panel'], bevel=.05), B('screen', (1.3, .05, .55), (0, -3.5, 1.35), rg, rot=(-.5, 0, 0)),
          B('cabinet', (1.0, 1.0, 1.8), (1.6, 1.6, 1.2), m['dark'], bevel=.05), B('cabinetglow', (.06, .7, .1), (1.1, 1.6, 1.8), rg)]
    for k in range(3):
        P.append(C('cable', .07, 2.6, (-.2 + k * .2, -2.2, .4), m['rubber'], 5, rot=(R90 + .25, 0, 0)))
    return finish('VX_relay', x0, P)


def terminal(x0):
    """Field terminal / console (lore logs, the lift controls, the nest purge). The screen faces -Y (the street)."""
    m = M()
    sc = bl.mat('terminal_screen', '#40e0ff', 0, .25, emit='#40e0ff', strength=5)
    P = [B('foot', (1.3, .9, .2), (0, 0, .1), m['dark']), B('body', (.95, .55, 1.1), (0, .05, .75), m['panel'], bevel=.04),
         B('head', (1.15, .65, .55), (0, -.1, 1.48), m['panel'], bevel=.04, rot=(-.45, 0, 0)),
         B('screen', (.92, .04, .42), (0, -.4, 1.52), sc, rot=(-.45, 0, 0)), B('keys', (.85, .32, .05), (0, -.34, 1.12), m['dark'], rot=(-.2, 0, 0)),
         B('stripe', (.96, .02, .06), (0, -.24, .5), m['amber']), C('antenna', .025, .9, (.45, .15, 2.1), m['steel'], 5),
         bl.sphere('tip', .06, (.45, .15, 2.56), m['amber'], 6, 4)]
    return finish('VX_terminal', x0, P)


def reliquary(x0):
    """The Warden's reliquary: an ornate sealed chest on a plinth. Child 'reliquary_lid' hinges open on its back edge."""
    m = M(); r = bl.empty('VX_reliquary', (x0, 0, 0))
    gl = bl.mat('reliquary_glow', '#ffcf3f', 0, .3, emit='#ffcf3f', strength=9)
    body = [B('plinth', (3.0, 2.1, .32), (0, 0, .16), m['dark'], bevel=.06), B('step', (2.5, 1.7, .2), (0, 0, .42), m['panel'], bevel=.04),
            B('chest', (2.1, 1.3, .85), (0, 0, .95), m['panel'], bevel=.07), B('band', (2.16, 1.36, .1), (0, 0, 1.2), m['brass']),
            B('bandlo', (2.16, 1.36, .1), (0, 0, .66), m['brass']), B('seal', (.5, .05, .45), (0, -.67, .95), gl),
            B('glowL', (.05, 1.0, .5), (-1.06, 0, .95), gl), B('glowR', (.05, 1.0, .5), (1.06, 0, .95), gl)]
    for sx in (-1, 1):
        for sy in (-1, 1):
            body.append(C('post', .09, 1.15, (sx * 1.05, sy * .65, .97), m['brass'], 8))
            body.append(bl.sphere('knob', .12, (sx * 1.05, sy * .65, 1.58), m['brass'], 8, 6))
    for o in body:
        bl.apply_all(o)
    g = bl.join(body, 'VX_reliquary_mesh'); g.parent = r
    lid = bl.empty('reliquary_lid', (0, .65, 1.38), r)
    L = [B('lid', (2.12, 1.32, .3), (0, -.65, .15), m['panel'], bevel=.07), B('lidband', (.16, 1.36, .32), (0, -.65, .16), m['brass']),
         B('lidglow', (1.5, .8, .02), (0, -.65, .31), gl), B('crest', (.4, .4, .12), (0, -.65, .36), m['brass'], rot=(0, 0, .785))]
    for o in L:
        bl.apply_all(o)
    lm = bl.join(L, 'reliquary_lid_mesh'); lm.parent = lid
    return r


def car_wreck(x0):
    m = M(); P = [B('body', (2, 4.4, 1.1), (0, 0, .75), m['rust'], bevel=.3), B('cabin', (1.8, 2.2, .8), (0, .3, 1.6), m['dark'], bevel=.2)]
    for sx in (-1, 1):
        for y in (-1.4, 1.4):
            P.append(C('wheel', .4, .3, (sx * 1, y, .35), m['rubber'], 10, rot=(0, R90, .3)))
    return finish('VX_car_wreck', x0, P)


# ====================================================================== underground (metro dungeon)
def tunnel(x0):
    m = M(); L = 20
    P = [B('floor', (10, L, .5), (0, 0, -.25), m['dirty']), B('ceiling', (10, L, .6), (0, 0, 7.3), m['dirty']),
         B('wallL', (.6, L, 7.6), (-5.3, 0, 3.6), m['concrete']), B('wallR', (.6, L, 7.6), (5.3, 0, 3.6), m['concrete']),
         B('rail1', (.15, L, .2), (-.8, 0, .1), m['track']), B('rail2', (.15, L, .2), (.8, 0, .1), m['track'])]
    for y in (-6, 6):
        P.append(B('lamp', (1.4, .3, .2), (0, y, 7), m['amber']))
        P.append(B('rib', (10.6, .8, .6), (0, y, 7), m['panel']))
    for k in range(4):
        P.append(C('cable', .12, L, (-5, 0, 5 + k * .3), m['dark'], 6, rot=(R90, 0, 0)))
    return finish('VX_tunnel', x0, P)


def junction(x0):
    m = M(); S = 20
    P = [B('floor', (S, S, .5), (0, 0, -.25), m['dirty']), B('ceiling', (S, S, .6), (0, 0, 9.3), m['dirty'])]
    for sx in (-1, 1):
        for sy in (-1, 1):
            P.append(B('corner', (5, 5, 9.6), (sx * 7.5, sy * 7.5, 4.6), m['concrete']))
    P += [C('pillar', 1, 9.6, (0, 0, 4.6), m['concrete'], 12), B('light', (2, 2, .3), (0, 0, 9), m['emer'])]
    P += growth(m, 4, -3, 0, 3, 91)
    return finish('VX_junction', x0, P)


def station(x0):
    m = M(); L = 40
    P = [B('floor', (24, L, .5), (0, 0, -.25), m['dirty']), B('ceiling', (24, L, .8), (0, 0, 9.4), m['dirty']),
         B('wallL', (.8, L, 9.8), (-12.4, 0, 4.7), m['white']), B('wallR', (.8, L, 9.8), (12.4, 0, 4.7), m['white']),
         B('platformL', (7, L, 1.2), (-8.5, 0, .6), m['concrete']), B('platformR', (7, L, 1.2), (8.5, 0, .6), m['concrete']),
         B('edgeL', (.3, L, .1), (-5.1, 0, 1.25), m['amber']), B('edgeR', (.3, L, .1), (5.1, 0, 1.25), m['amber']),
         B('rail1', (.15, L, .2), (-.8, 0, .1), m['track']), B('rail2', (.15, L, .2), (.8, 0, .1), m['track'])]
    for y in range(-15, 20, 10):
        P.append(C('column', .6, 8.2, (-8.5, y, 5.3), m['white'], 10)); P.append(C('column', .6, 8.2, (8.5, y, 5.3), m['white'], 10))
        P.append(B('sign', (3, .2, .8), (-12, y, 5), m['cyan']))
    P += growth(m, -8, 12, 1.2, 4, 92) + growth(m, 9, -14, 1.2, 3, 93)
    return finish('VX_station', x0, P)


def main():
    bl.reset()
    x = [0]

    def nx(w):
        x[0] += w
        return x[0]
    spire(nx(0))
    apartment('VX_res_a', nx(260), 8, 24, 16, seed=1); apartment('VX_res_b', nx(60), 13, 20, 20, seed=2)
    apartment('VX_res_c', nx(60), 5, 30, 14, seed=3); apartment('VX_res_ruin', nx(60), 12, 22, 18, ruined=True, seed=4)
    market_row(nx(70))
    skyscraper('VX_com_a', nx(90), 110, 30, seed=5); skyscraper('VX_com_b', nx(90), 160, 26, seed=6)
    skyscraper('VX_com_c', nx(90), 80, 36, round_=True, seed=7); skyscraper('VX_com_ruin', nx(100), 120, 30, ruined=True, seed=8)
    skybridge(nx(90))
    factory(nx(90)); refinery(nx(90)); warehouse(nx(80)); power_station(nx(90))
    bunker(nx(80)); watchtower(nx(50)); wall_segment(nx(50)); gate(nx(50)); depot(nx(60))
    lab(nx(70)); containment(nx(60)); hospital(nx(70))
    highway('VX_hwy', nx(80)); highway('VX_hwy_broken', nx(60), broken=True); broken_bridge(nx(60))
    roadblock(nx(50)); rubble_pile(nx(40)); metro_entrance(nx(40)); lift(nx(30))
    holo_ad('VX_holo_a', nx(40), 'holo'); holo_ad('VX_holo_b', nx(40), 'holo2')
    shuttle(nx(60)); apc(nx(40)); train(nx(40)); organism(nx(100)); camp(nx(60)); car_wreck(nx(30))
    growth_cluster('VX_growth_s', nx(30), 4, 101); growth_cluster('VX_growth_l', nx(40), 10, 102)
    tunnel(nx(50)); junction(nx(40)); station(nx(50))
    conduit(nx(40)); relay(nx(20)); terminal(nx(20)); reliquary(nx(20))
    bl.export('vanthos.glb')


if __name__ == '__main__':
    main()
