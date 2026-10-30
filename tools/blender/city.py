"""Earth city building kit + world prop bundle.

city_buildings.glb: root nodes BLD_<n> (origin at ground centre). Facade materials ('facade', 'ribbon')
get their emissive window maps in-engine. props_world.glb: every reusable prop/machine as a root node.
"""
import bpy, math, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import bl, props
from mathutils import Vector

R90 = math.pi / 2


def mats():
    p = props.M()
    p.update(facade=bl.mat('facade', '#ffffff', .6, .25, image='facade_c.jpg', normal='facade_n.jpg'),
             ribbon=bl.mat('ribbon', '#ffffff', .4, .35, image='ribbon_c.jpg', normal='ribbon_n.jpg'),
             concrete=bl.mat('concrete', '#c9c4ba', 0, .8, image='concrete_c.jpg', normal='concrete_n.jpg'),
             roof=bl.mat('roof', '#4a4d52', .3, .7, image='panel_c.jpg', normal='panel_n.jpg'),
             neon_m=bl.mat('neon_magenta_s', '#ff2fa8', 0, .3, emit='#ff2fa8', strength=5),
             neon_c=bl.mat('neon_cyan_s', '#1ad8ff', 0, .3, emit='#1ad8ff', strength=5),
             beacon=bl.mat('beacon', '#ff3326', 0, .3, emit='#ff3326', strength=8))
    return p


def fac(o, scale=28):
    bl.uv_box(o, scale)
    return o


def building(i, x0):
    m = mats()
    r = bl.empty('BLD_%d' % i, (x0, 0, 0))
    P = []
    if i == 0:   # glass tower
        h = 110
        P.append(fac(bl.box('t', (26, 26, h), (0, 0, h / 2), m['ribbon']), 24))
        for cx in (-13, 13):
            for cy in (-13, 13):
                P.append(bl.box('col', (1.6, 1.6, h + 1), (cx, cy, (h + 1) / 2), m['gunmetal']))
        P.append(bl.box('crown', (20, 20, 6), (0, 0, h + 3), m['roof'], bevel=.5))
        P.append(bl.box('crownglow', (20.4, 20.4, .5), (0, 0, h + 1.2), m['neon_c']))
        P.append(bl.cyl('mast', .4, 18, (0, 0, h + 15), m['steel'], 8))
        P.append(bl.sphere('beacon', .7, (0, 0, h + 24.5), m['beacon'], 8, 6))
    elif i == 1:  # stepped tower
        for k, (w, z0, z1) in enumerate(((30, 0, 40), (24, 40, 75), (17, 75, 98))):
            P.append(fac(bl.box('s%d' % k, (w, w, z1 - z0), (0, 0, (z0 + z1) / 2), m['facade'])))
            P.append(bl.box('ledge%d' % k, (w + 1, w + 1, 1), (0, 0, z1), m['concrete'], bevel=.2))
        P.append(bl.box('cap', (10, 10, 4), (0, 0, 100), m['roof']))
    elif i == 2:  # cylindrical tower
        P.append(fac(bl.cyl('c', 14, 90, (0, 0, 45), m['facade'], 16, smooth=False), 22))
        P.append(bl.cyl('ring1', 14.6, 1.2, (0, 0, 30), m['neon_m'], 16))
        P.append(bl.cyl('ring2', 14.6, 1.2, (0, 0, 60), m['neon_m'], 16))
        P.append(bl.cyl('top', 11, 6, (0, 0, 93), m['roof'], 16, r2=6))
    elif i == 3:  # brutalist block
        P.append(fac(bl.box('b', (40, 24, 36), (0, 0, 18), m['concrete']), 12))
        for z in range(4, 36, 4):
            P.append(fac(bl.box('band', (40.4, 24.4, 1.6), (0, 0, z), m['ribbon']), 14))
        P.append(bl.box('roofbox', (12, 10, 4), (8, 4, 38), m['roof']))
        P.append(bl.box('roofbox2', (6, 6, 3), (-10, -5, 37.5), m['roof']))
    elif i == 4:  # residential with balconies
        P.append(fac(bl.box('r', (22, 18, 60), (0, 0, 30), m['facade']), 20))
        for z in range(6, 60, 6):
            P.append(bl.box('balcony', (22.6, 2.0, .35), (0, -9.8, z), m['concrete']))
            P.append(bl.box('rail', (22.6, .1, 1.0), (0, -10.75, z + .6), m['glass']))
        P.append(bl.box('roof', (22, 18, 1), (0, 0, 60.5), m['roof']))
    elif i == 5:  # landmark spire
        P.append(fac(bl.box('base', (34, 34, 20), (0, 0, 10), m['ribbon']), 20))
        P.append(fac(bl.cyl('spire', 9, 150, (0, 0, 95), m['facade'], 8, r2=4, smooth=False), 24))
        for z in (40, 70, 100, 130):
            P.append(bl.torus('halo', 9.5 - (z - 20) / 150 * 4.5, .5, (0, 0, z), m['neon_c'], maj=24, mn=6))
        P.append(bl.cyl('needle', .5, 30, (0, 0, 185), m['steel'], 8))
        P.append(bl.sphere('beacon', .8, (0, 0, 200), m['beacon'], 8, 6))
    elif i == 6:  # street shops block with signage
        P.append(fac(bl.box('shop', (30, 16, 12), (0, 0, 6), m['concrete']), 10))
        P.append(bl.box('awning', (30, 3, .3), (0, -9, 4.2), m['gunmetal']))
        P.append(bl.box('glassfront', (28, .2, 3.6), (0, -8.05, 1.9), m['glass']))
        P.append(bl.box('sign1', (8, .3, 1.6), (-8, -8.3, 6.5), m['neon_m']))
        P.append(bl.box('sign2', (6, .3, 1.6), (6, -8.3, 6.5), m['neon_c']))
        P.append(bl.box('roofvent', (4, 4, 2), (8, 2, 13), m['roof']))
    elif i == 7:  # mid-rise office
        P.append(fac(bl.box('o', (28, 22, 48), (0, 0, 24), m['ribbon']), 18))
        P.append(bl.box('lobby', (29, 23, 5), (0, 0, 2.5), m['concrete']))
        P.append(bl.box('roof', (28, 22, 1.5), (0, 0, 48.7), m['roof']))
        P.append(bl.box('roofglow', (28.4, 22.4, .3), (0, 0, 47.9), m['neon_m']))
    for o in P:
        bl.apply_all(o)
    g = bl.join(P, 'BLD_%d_mesh' % i)
    g.parent = r
    return r


def spaceport(x0):
    """Landing platform where the player's ship sets down in the city."""
    m = mats()
    r = bl.empty('BLD_port', (x0, 0, 0))
    P = [bl.box('deck', (40, 40, 1.2), (0, 0, .6), m['concrete'], bevel=.3),
         bl.box('ramp', (10, 16, .6), (0, -27, .3), m['concrete'], rot=(-.07, 0, 0))]
    o = bl.box('hzX', (34, 1, .05), (0, 17, 1.22), m['hazard']); bl.uv_box(o, 2); P.append(o)
    o = bl.box('hzX2', (34, 1, .05), (0, -17, 1.22), m['hazard']); bl.uv_box(o, 2); P.append(o)
    P.append(bl.torus('padring', 12, .25, (0, 0, 1.25), m['neon_c'], maj=48, mn=6))
    for k in range(4):
        a = k * R90 + math.pi / 4
        P.append(bl.box('tower', (1.2, 1.2, 8), (math.cos(a) * 26, math.sin(a) * 26, 4), m['gunmetal']))
        P.append(bl.sphere('tlight', .5, (math.cos(a) * 26, math.sin(a) * 26, 8.4), m['amber'], 8, 6))
    for o in P:
        bl.apply_all(o)
    bl.uv_box(P[0], 8)
    g = bl.join(P, 'BLD_port_mesh'); g.parent = r
    return r


def main():
    bl.reset()
    for i in range(8):
        building(i, i * 60)
    spaceport(8 * 60)
    bl.export('city_buildings.glb')

    bl.reset()
    x = 0
    roots = []

    def nx(w=6):
        nonlocal x
        x += w
        return (x, 0, 0)
    roots += [props.crate('PR_crate', nx()), props.crate('PR_crate_orange', nx(), orange=True),
              props.barrel('PR_barrel', nx()), props.fuel_tank(nx(8)), props.barricade(nx()),
              props.barricade(nx(), enemy=False), props.lamp_post(nx()), props.bench(nx()),
              props.holo_sign(nx(), color='#ff2fa8'), props.holo_sign(nx(), color='#1ad8ff'),
              props.antenna(nx()), props.loot_cache(nx()), props.generator(nx(), enemy=True),
              props.turret(nx()), props.drone(nx()), props.loader(nx(8)), props.terminal('PR_terminal', nx())]
    names = ['PR_crate', 'PR_crate_orange', 'PR_barrel', 'PR_fuel_tank', 'PR_barricade', 'PR_barricade_friendly',
             'PR_lamp', 'PR_bench', 'PR_sign_magenta', 'PR_sign_cyan', 'PR_antenna', 'PR_cache', 'PR_generator',
             'PR_turret', 'PR_drone', 'PR_loader', 'PR_terminal']
    for r, n in zip(roots, names):
        r.name = n
    for i in range(6):
        props.rock('PR_rock_%d' % i, 100 + i, nx(), scale=(1.5 + i * .4, 1.3 + i * .3, 1.4 + i * .3))
    for i, c in enumerate(('#9b5cff', '#3ad6ff', '#ff6a3a')):
        props.crystal('PR_crystal_%d' % i, 200 + i, c).location = nx()
    for i, (st, gl) in enumerate((('#3d6b3a', '#7dffb0'), ('#5a3a6b', '#ff7ae0'), ('#6b5a3a', '#ffd27a'))):
        props.alien_plant('PR_plant_%d' % i, 300 + i, st, gl).location = nx()
    props.data_core().location = nx()
    props.ammo_box().location = nx()
    bl.export('props_world.glb')


main()
