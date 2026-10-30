"""The player's ship (hub): bridge -> commons -> hangar bay. Replaces the old main menu.

Exports assets/models/ship_interior.glb and ship_interior.json:
  colliders: AABBs in three.js space [minx,miny,minz,maxx,maxy,maxz]
  stations:  id -> {pos, look} interaction points (three.js space)
  lights:    named anchors for runtime lights (skylight sun, spots, strip lights)
Layout (Blender): nose toward -Y. Bridge y[-20,-10], commons y[-10,4], hangar y[4,30].
"""
import bpy, math, os, sys, json
sys.path.insert(0, os.path.dirname(__file__))
import bl, props
from mathutils import Vector

R90 = math.pi / 2
SOLIDS = []      # objects whose world AABB becomes a collider
STATIONS = {}
LIGHTS = []


def solid(o):
    SOLIDS.append(o); return o


def to3(v):
    return [round(v[0], 3), round(v[2], 3), round(-v[1], 3)]


def main():
    bl.reset()
    m = props.M()
    floor_h = bl.mat('floor_tread', '#8d9096', .7, .45, image='tread_c.jpg', normal='tread_n.jpg', uv_scale=1)
    floor_c = bl.mat('floor_panel', '#7b7f86', .5, .5, image='panel_c.jpg', normal='panel_n.jpg')
    wall = bl.mat('wall_panel', '#b9bdc4', .35, .5, image='panel_c.jpg', normal='panel_n.jpg')
    wall_dark = bl.mat('wall_dark', '#4a4f57', .5, .5, image='panel_c.jpg', normal='panel_n.jpg')
    sky_glass = bl.mat('skylight_glass', '#cfe8ff', 0, .02, alpha=.12)
    win_glass = bl.mat('window_glass', '#a8d0ff', 0, .02, alpha=.1)
    light_panel = bl.mat('light_panel', '#fff4e2', 0, .4, emit='#fff4e2', strength=7)
    strip_c = m['cyan']; strip_a = m['amber']
    girder = bl.mat('girder', '#3c4148', .8, .45)
    parts_static = []

    def slab(name, size, loc, mt, uv=4.0, is_solid=True, bevel=0.0):
        o = bl.box(name, size, loc, mt, bevel=bevel)
        bl.uv_box(o, uv)
        if is_solid:
            solid(o)
        parts_static.append(o)
        return o

    # ---------------- floors / ceilings
    slab('floor_bridge', (14, 10, .4), (0, -15, -.2), floor_c)
    slab('floor_commons', (12, 14, .4), (0, -3, -.2), floor_c)
    slab('floor_hangar', (24, 26, .4), (0, 17, -.2), floor_h, uv=3)
    slab('ceil_bridge', (14, 10, .4), (0, -15, 5.2), wall_dark, is_solid=False)
    slab('ceil_commons', (12, 14, .4), (0, -3, 4.7), wall_dark, is_solid=False)
    # hazard border around the car pad
    for (sx, sy, x, y) in ((6.4, .3, 6, 14.6), (6.4, .3, 6, 21.4), (.3, 7.1, 2.95, 18), (.3, 7.1, 9.05, 18)):
        o = bl.box('hazard_line', (sx, sy, .02), (x, y, .01), m['hazard']); bl.uv_box(o, 1.5); parts_static.append(o)
    pad = bl.cyl('car_pad', 2.9, .06, (6, 18, .03), m['gunmetal'], 40); parts_static.append(pad)
    parts_static.append(bl.torus('car_pad_ring', 2.9, .05, (6, 18, .07), strip_c, maj=48, mn=6))

    # ---------------- bridge walls + windshield
    for sx in (1, -1):
        slab('bridge_wall', (.5, 10, 5.4), (sx * 7.25, -15, 2.5), wall)
        # angled cheek windows
        g = bl.box('cheek_glass', (.05, 6, 2.6), (sx * 6.95, -16, 2.6), win_glass); parts_static.append(g)
    slab('bridge_front_low', (14, .5, 1.3), (0, -20.25, .45), wall_dark)
    slab('bridge_front_top', (14, .5, .9), (0, -20.25, 4.85), wall_dark, is_solid=False)
    for x in (-4.5, 0, 4.5):
        slab('mullion', (.25, .5, 3.4), (x, -20.25, 2.8), girder, is_solid=False)
    wg = bl.box('windshield', (14, .06, 3.4), (0, -20.2, 2.8), win_glass); parts_static.append(wg)
    solid(bl.box('windshield_col', (14, .5, 3.4), (0, -20.25, 2.8), None)).hide_render = True
    # dais + console rows
    slab('dais', (4.0, 4.0, .2), (0, -14, .1), m['gunmetal'], bevel=.04)
    parts_static.append(bl.torus('dais_ring', 1.9, .03, (0, -14, .21), strip_c, maj=40, mn=5))
    chair = props.captain_chair((0, -14, .2), 0)
    solid(chair)
    for sx in (1, -1):
        t = props.terminal('bridge_console', (sx * 3.6, -18.2, 0), math.pi, amber=sx < 0); solid(t)
        t = props.terminal('bridge_console_side', (sx * 6.2, -13.0, 0), -sx * R90); solid(t)
    nav = bl.sphere('nav_holo', .5, (0, -17.0, 1.9), m['holo'], 20, 12)
    parts_static.append(bl.cyl('nav_emitter', .45, .9, (0, -17.0, .45), m['gunmetal'], 20))
    solid(parts_static[-1])
    STATIONS['captain'] = dict(pos=to3((0, -12.9, 0)), look=to3((0, -20, 1.5)), label='Captain’s Chair', verb='Navigate', seat=to3((0, -14.05, .2)))
    LIGHTS.append(dict(kind='spot', name='bridge_key', pos=to3((0, -12, 4.9)), target=to3((0, -15, 0)), color='#cfe3ff', intensity=60, angle=.9))
    for x in (-4, 4):
        LIGHTS.append(dict(kind='point', name='bridge_fill', pos=to3((x, -16, 4.4)), color='#7fc8ff', intensity=10, dist=12))

    # ---------------- divider wall bridge/commons (y=-10) with 4m door
    for sx in (1, -1):
        slab('div1', (5.0, .5, 5.4), (sx * 4.5, -10, 2.5), wall)
    slab('div1_head', (4.0, .5, 1.6), (0, -10, 4.2), wall, is_solid=False)
    for sx in (1, -1):
        parts_static.append(bl.box('doorglow', (.06, .55, 3.4), (sx * 2.0, -10, 1.7), strip_c))
    # ---------------- commons walls (x=+-6) with porthole strips
    for sx in (1, -1):
        slab('commons_wall', (.5, 14, 4.9), (sx * 6.25, -3, 2.25), wall)
        parts_static.append(bl.box('porthole', (.06, 8, .9), (sx * 5.98, -3, 2.6), win_glass))
        parts_static.append(bl.box('porthole_frame', (.1, 8.2, .12), (sx * 5.96, -3, 3.12), girder))
        parts_static.append(bl.box('porthole_frame', (.1, 8.2, .12), (sx * 5.96, -3, 2.08), girder))
        parts_static.append(bl.box('wallstrip', (.04, 13.6, .05), (sx * 5.98, -3, .25), strip_a))
    for y in (-8, -3, 2):
        parts_static.append(bl.box('ceil_light', (3.0, .6, .05), (0, y, 4.47), light_panel))
    LIGHTS.append(dict(kind='point', name='commons_a', pos=to3((0, -6, 4.0)), color='#ffe8cc', intensity=18, dist=14))
    LIGHTS.append(dict(kind='point', name='commons_b', pos=to3((0, 1, 4.0)), color='#ffe8cc', intensity=18, dist=14))

    ht = props.holo_table((0, -3.5, 0)); solid(ht)
    STATIONS['briefing'] = dict(pos=to3((0, -1.6, 0)), look=to3((0, -3.5, 1.2)), label='Briefing Table', verb='Contracts & Field Guide')
    pod = props.locker_pod((-4.8, -6.5, 0), 0)
    STATIONS['wardrobe'] = dict(pos=to3((-3.2, -6.5, 0)), look=to3((-4.8, -6.5, 1.2)), label='Wardrobe Pod', verb='Customize', stand=to3((-4.8, -6.5, .15)))
    for i in range(5):  # pod ribs as colliders (open toward +X)
        a = math.pi * .35 + i * math.pi * .32
        solid(bl.box('pod_col', (.3, .3, 2.6), (-4.8 + math.cos(a) * .95, -6.5 + math.sin(a) * .95, 1.3), None)).hide_render = True
    t = props.terminal('ST_engineering', (5.2, -6.5, 0), -R90); solid(t)
    STATIONS['engineering'] = dict(pos=to3((4.0, -6.5, 0)), look=to3((5.4, -6.5, 1.3)), label='Engineering Terminal', verb='Settings & Controls')
    t = props.terminal('ST_record', (5.2, -.5, 0), -R90, amber=True); solid(t)
    STATIONS['record'] = dict(pos=to3((4.0, -.5, 0)), look=to3((5.4, -.5, 1.3)), label='Service Record', verb='Stats')
    for (x, y) in ((-4.6, 1.8), (-4.6, -.6)):
        props.bench((x, y, 0), R90 if x < 0 else -R90)
        solid(bl.box('bench_col', (.6, 1.9, .9), (x, y, .45), None)).hide_render = True

    # ---------------- divider commons/hangar (y=4) with 5m door
    slab('div2L', (9.5, .5, 11), (-7.25, 4, 5.5), wall)
    slab('div2R', (9.5, .5, 11), (7.25, 4, 5.5), wall)
    slab('div2_head', (5.0, .5, 7.0), (0, 4, 7.5), wall, is_solid=False)
    for sx in (1, -1):
        parts_static.append(bl.box('doorglow2', (.06, .55, 4.0), (sx * 2.5, 4, 2.0), strip_c))
    parts_static.append(bl.box('door_sign', (2.2, .06, .35), (0, 3.72, 4.4), strip_a))

    # ---------------- hangar shell
    for sx in (1, -1):
        slab('hangar_wall', (.6, 26, 11), (sx * 12.3, 17, 5.5), wall)
        for y in range(6, 30, 4):  # structural ribs
            parts_static.append(bl.box('rib', (.6, .5, 11), (sx * 11.8, y, 5.5), girder))
        # catwalk
        parts_static.append(bl.box('catwalk', (1.6, 25, .15), (sx * 11.0, 17, 4.6), m['gunmetal']))
        parts_static.append(bl.box('rail', (.06, 25, .06), (sx * 10.2, 17, 5.6), m['steel']))
        for y in range(5, 30, 2):
            parts_static.append(bl.box('post', (.06, .06, 1.0), (sx * 10.2, y, 5.1), m['steel']))
        parts_static.append(bl.box('wall_strip', (.05, 25, .06), (sx * 11.98, 17, .3), strip_c))
    # rear bay door
    slab('bay_door', (24, .6, 11), (0, 30.3, 5.5), wall_dark)
    for i in range(6):
        parts_static.append(bl.box('door_seg', (22, .1, .08), (0, 29.95, 1.5 + i * 1.6), girder))
    o = bl.box('door_hazard', (22, .05, .6), (0, 29.95, .5), m['hazard']); bl.uv_box(o, 1.5); parts_static.append(o)
    parts_static.append(bl.box('door_status', (3.0, .06, .3), (0, 29.95, 9.6), m['red']))
    # roof: beams + skylights (big glass panes)
    for x in range(-12, 13, 4):
        parts_static.append(bl.box('roof_beam_x', (.45, 26, .7), (x, 17, 10.8), girder))
    for y in range(4, 31, 4):
        parts_static.append(bl.box('roof_beam_y', (24.5, .45, .7), (0, y, 10.8), girder))
    for x in range(-10, 11, 4):
        for y in range(6, 30, 4):
            g = bl.box('skylight', (3.55, 3.55, .05), (x, y, 10.95), sky_glass); parts_static.append(g)
    # hanging industrial lamps
    for (x, y) in ((-6, 9), (6, 9), (-6, 25), (6, 25)):
        parts_static.append(bl.cyl('lamp_cable', .02, 3.0, (x, y, 9.0), m['rubber'], 6))
        parts_static.append(bl.cyl('lamp_shade', .6, .5, (x, y, 7.3), girder, 16, r2=.15))
        parts_static.append(bl.cyl('lamp_bulb', .45, .05, (x, y, 7.03), light_panel, 16))
        LIGHTS.append(dict(kind='spot', name='hangar_lamp', pos=to3((x, y, 6.9)), target=to3((x, y, 0)), color='#ffe2b8', intensity=140, angle=.75))
    LIGHTS.append(dict(kind='sun', name='skylight_sun', pos=to3((-10, 6, 40)), target=to3((2, 18, 0)), color='#fff1dc', intensity=3.2))

    # ---------------- hangar contents
    STATIONS['garage'] = dict(pos=to3((3.0, 18, 0)), look=to3((6, 18, .8)), label='Hover Car', verb='Garage', car=to3((6, 18, .0)))
    solid(bl.box('car_col', (2.2, 4.8, 1.4), (6, 18, .7), None)).hide_render = True
    rack = props.armory_rack((-11.6, 9.5, 0), R90); solid(rack)
    STATIONS['armory'] = dict(pos=to3((-9.6, 9.5, 0)), look=to3((-11.6, 9.5, 1.3)), label='Armory', verb='Loadout')
    bench = props.gunsmith_bench((-11.3, 15.0, 0), R90); solid(bench)
    STATIONS['gunsmith'] = dict(pos=to3((-9.6, 15.0, 0)), look=to3((-11.3, 15.0, 1.1)), label='Gunsmith Bench', verb='Upgrade Weapons')
    # welding cell: robot arm working on an engine nacelle on a stand
    wl = props.welder((-6.0, 23.5, 0), 0); solid(bl.box('welder_col', (1.6, 1.6, 2.5), (-6.0, 23.5, 1.2), None)).hide_render = True
    parts_static.append(bl.box('stand', (2.6, 1.6, .9), (-6.0, 26.3, .45), m['gunmetal'], bevel=.04)); solid(parts_static[-1])
    eng = bl.cyl('nacelle', 1.0, 3.2, (-6.0, 26.3, 1.95), m['hull'], 24, rot=(0, R90, 0)); parts_static.append(eng); solid(eng)
    parts_static.append(bl.torus('nacelle_ring', 1.02, .08, (-7.2, 26.3, 1.95), m['brass'], rot=(0, R90, 0), maj=28, mn=6))
    parts_static.append(bl.cyl('nacelle_glow', .75, .05, (-7.65, 26.3, 1.95), strip_c, 24, rot=(0, R90, 0)))
    for (x, y) in ((-8.5, 21), (-3.5, 21)):
        parts_static.append(bl.box('safety_post', (.1, .1, 1.1), (x, y, .55), m['hazard']))
    LIGHTS.append(dict(kind='weld', name='weld_spark', pos=to3((-6.0, 25.3, 2.0))))
    ld = props.loader((8.5, 26.5, 0), R90 * .5); solid(ld)
    ft = props.fuel_tank((9.0, 8.5, 0), R90); solid(ft)
    # crate stacks
    import random
    rnd = random.Random(7)
    for (x, y, n) in ((-9.5, 28.0, 3), (-3.0, 28.5, 2), (10.3, 13.0, 2), (-9.8, 5.6, 2), (3.0, 28.5, 1)):
        for k in range(n):
            c = props.crate('crate', (x + rnd.uniform(-.1, .1), y, k * 1.2), rnd.uniform(-.2, .2), orange=(k % 2 == 1))
            solid(c)
    for (x, y) in ((10.8, 16), (10.8, 17), (10.0, 16.5), (-3.2, 6.0)):
        solid(props.barrel('barrel', (x, y, 0)))

    # spawn + bay exit marker
    STATIONS['_spawn'] = dict(pos=to3((0, 1.6, 0)), look=to3((0, -3.5, 1.2)))
    # ---------------- export
    for o in parts_static:
        bl.apply_all(o)
    # snapshot colliders of architecture slabs before they are merged by material
    pre = []
    for o in parts_static:
        if o in SOLIDS:
            lo = Vector((1e9,) * 3); hi = Vector((-1e9,) * 3)
            for c in o.bound_box:
                w = o.matrix_world @ Vector(c)
                lo = Vector(map(min, lo, w)); hi = Vector(map(max, hi, w))
            pre.append([round(lo.x, 3), round(lo.z, 3), round(-hi.y, 3), round(hi.x, 3), round(hi.z, 3), round(-lo.y, 3)])
            SOLIDS.remove(o)
    # join static architecture by material to minimise draw calls
    by_mat = {}
    for o in parts_static:
        if o.hide_render or not o.data.materials:
            continue
        by_mat.setdefault(o.data.materials[0].name, []).append(o)
    for k, objs in by_mat.items():
        bl.join(objs, 'arch_' + k)
    # colliders
    cols = pre
    dg = bpy.context.evaluated_depsgraph_get()

    def aabb(o):
        lo = Vector((1e9,) * 3); hi = Vector((-1e9,) * 3)
        stack = [o]
        while stack:
            x = stack.pop(); stack.extend(x.children)
            if x.type == 'MESH':
                for c in x.bound_box:
                    w = x.matrix_world @ Vector(c)
                    lo = Vector(map(min, lo, w)); hi = Vector(map(max, hi, w))
        return lo, hi
    bpy.context.view_layer.update()
    for o in SOLIDS:
        try:
            lo, hi = aabb(o)
        except ReferenceError:
            continue
        if lo.x > hi.x:
            continue
        cols.append([round(lo.x, 3), round(lo.z, 3), round(-hi.y, 3), round(hi.x, 3), round(hi.z, 3), round(-lo.y, 3)])
    # remove hidden collider-only boxes from the visual export
    for o in list(bpy.context.scene.objects):
        if o.type == 'MESH' and o.hide_render:
            bpy.data.objects.remove(o)
    json.dump(dict(colliders=cols, stations=STATIONS, lights=LIGHTS), open(os.path.join(bl.MODELS, 'ship_interior.json'), 'w'), indent=1)
    print('colliders', len(cols))
    bl.export('ship_interior.glb')


main()
