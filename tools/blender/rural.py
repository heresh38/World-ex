"""Countryside kit for New Meridian's outskirts: rural.glb (root nodes RU_*).

Trees and bushes, village houses, a farm (barn, silo, fences, hay, crops, tractor), wind turbine, water tower,
gas station, road signs. Textures (roof tiles, planks, siding, bark, leaves, field rows) are generated here.
"""
import bpy, bmesh, math, os, sys
import numpy as np
from mathutils import Vector
sys.path.insert(0, os.path.dirname(__file__))
import bl, props

R90 = math.pi / 2


def tex_image(name, fn, S=256):
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32) / S
    rng = np.random.default_rng(abs(hash(name)) % 1000)
    img = np.ones((S, S, 4), np.float32)
    img[..., :3] = np.clip(fn(xx, yy, rng), 0, 1)
    im = bpy.data.images.new(name, S, S); im.pixels = img[::-1].ravel()
    sc = bpy.context.scene; sc.render.image_settings.file_format = 'JPEG'; sc.render.image_settings.quality = 88
    im.save_render(os.path.join(bl.TEXTURES, name + '.jpg'))


def make_textures():
    def tiles(x, y, r):
        row = np.floor(y * 8); off = (row % 2) * .5
        u = (x * 6 + off) % 1; v = (y * 8) % 1
        shade = .75 + .25 * np.clip(v * 1.4, 0, 1) - .3 * (u < .05) - .2 * (v > .92)
        base = np.array([.55, .22, .16])
        return base * shade[..., None] * (.9 + .1 * r.random(x.shape))[..., None]
    tex_image('roof_tiles_c', tiles)
    def planks(x, y, r):
        v = (y * 6) % 1
        grain = .85 + .1 * np.sin(x * 90 + np.sin(y * 30) * 3) + .05 * r.random(x.shape)
        seam = 1 - .45 * (v < .04)
        return np.array([.52, .38, .25]) * (grain * seam)[..., None]
    tex_image('planks_c', planks)
    def siding(x, y, r):
        v = (y * 10) % 1
        return np.array([.92, .9, .86]) * (.86 + .14 * v - .25 * (v < .06))[..., None]
    tex_image('siding_c', siding)
    def bark(x, y, r):
        n = np.sin(x * 60 + np.sin(y * 9) * 2) * .5 + .5
        return np.array([.32, .24, .18]) * (.7 + .3 * n + .1 * r.random(x.shape))[..., None]
    tex_image('bark_c', bark)
    def leaves(x, y, r):
        n = r.random(x.shape)
        blot = np.sin(x * 40) * np.sin(y * 37) * .5 + .5
        return np.array([.2, .34, .14]) * (.65 + .35 * n * .6 + .3 * blot)[..., None]
    tex_image('leaves_c', leaves)
    def field(x, y, r):
        rows = .5 + .5 * np.sin(x * 2 * np.pi * 16)
        return (np.array([.42, .32, .2]) * (1 - rows[..., None]) + np.array([.42, .5, .22]) * rows[..., None]) * (.9 + .1 * r.random(x.shape))[..., None]
    tex_image('field_rows_c', field)
    def wheat(x, y, r):
        rows = .5 + .5 * np.sin(x * 2 * np.pi * 16)
        return np.array([.78, .66, .36]) * (.75 + .25 * rows + .1 * r.random(x.shape))[..., None]
    tex_image('wheat_c', wheat)
    def barn(x, y, r):
        u = (x * 8) % 1
        return np.array([.55, .14, .11]) * (.82 + .18 * (u > .06) + .06 * r.random(x.shape))[..., None]
    tex_image('barn_red_c', barn)


def M():
    p = props.M()
    p.update(roof=bl.mat('roof_tiles', '#ffffff', 0, .7, image='roof_tiles_c.jpg'),
             planks=bl.mat('planks', '#ffffff', 0, .8, image='planks_c.jpg'),
             siding=bl.mat('siding', '#ffffff', 0, .7, image='siding_c.jpg'),
             plaster=bl.mat('plaster', '#e9dfcc', 0, .85, image='concrete_c.jpg', normal='concrete_n.jpg'),
             bark=bl.mat('bark', '#ffffff', 0, .9, image='bark_c.jpg'),
             leaves=bl.mat('leaves', '#ffffff', 0, .8, image='leaves_c.jpg'),
             leaves2=bl.mat('leaves_autumn', '#c99a5a', 0, .8, image='leaves_c.jpg'),
             pine=bl.mat('pine', '#7f9a7a', 0, .85, image='leaves_c.jpg'),
             barnred=bl.mat('barn_red', '#ffffff', 0, .8, image='barn_red_c.jpg'),
             window=bl.mat('house_window', '#2a3a48', .3, .15, emit='#ffd9a0', strength=.35),
             door=bl.mat('house_door', '#5a3a26', 0, .6),
             trim=bl.mat('house_trim', '#f2efe8', 0, .6),
             hay=bl.mat('hay', '#c9a95a', 0, .9, image='wheat_c.jpg'),
             wheat=bl.mat('wheat', '#ffffff', 0, .9, image='wheat_c.jpg'),
             corn=bl.mat('corn', '#6a8a3a', 0, .8, image='leaves_c.jpg'),
             galv=bl.mat('galvanized', '#aab0b5', .8, .4),
             tractor=bl.mat('tractor_green', '#2f6a2a', .3, .45),
             white=bl.mat('paint_white', '#eeeeea', .1, .5))
    return p


def root(name, x):
    r = bl.empty(name, (x, 0, 0)); r['solid'] = 1
    return r


def pack(r, parts):
    for o in parts:
        bl.apply_all(o)
    g = bl.join(parts, r.name + '_mesh'); g.parent = r
    return r


def blob(name, r, loc, m, seed, scale=(1, 1, 1), sub=1, amp=.22):
    import random
    rnd = random.Random(seed)
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=sub, radius=r, location=loc)
    o = bpy.context.object; o.name = name
    for v in o.data.vertices:
        d = v.co - Vector(loc)
        v.co = Vector(loc) + d * (1 + rnd.uniform(-amp, amp))
    o.scale = scale
    o = bl._finish(o, m, name, smooth=True)
    bl.uv_box(o, 1.5)
    return o


def tree_round(name, x, seed, m, h=7.0):
    P = M(); r = root(name, x); r['solid'] = 0
    parts = [bl.cyl('trunk', .28, h * .55, (0, 0, h * .275), P['bark'], 7, r2=.18)]
    import random
    rnd = random.Random(seed)
    for i in range(3):
        a = i * 2.1
        parts.append(blob('canopy', h * .25 * rnd.uniform(.85, 1.15), (math.cos(a) * h * .13, math.sin(a) * h * .13, h * (.6 + .08 * (i % 2))), m, seed + i))
    parts.append(blob('crown', h * .26, (0, 0, h * .8), m, seed + 9))
    for o in parts[1:]:
        bl.uv_box(o, 1.2)
    return pack(r, parts)


def tree_pine(name, x, seed, h=11.0):
    P = M(); r = root(name, x); r['solid'] = 0
    parts = [bl.cyl('trunk', .25, h * .9, (0, 0, h * .45), P['bark'], 8, r2=.1)]
    for i in range(5):
        t = i / 5
        parts.append(bl.cyl('tier', h * (.3 - .05 * i), h * .28, (0, 0, h * (.3 + .14 * i)), P['pine'], 9, r2=.05))
    for o in parts[1:]:
        bl.uv_box(o, 1.5)
    return pack(r, parts)


def bush(name, x, seed):
    P = M(); r = root(name, x); r['solid'] = 0
    return pack(r, [blob('b', 1.0, (0, 0, .6), P['leaves'], seed, scale=(1.3, 1.1, .8)), blob('b2', .7, (.6, .3, .45), P['leaves'], seed + 1)])


def gable_house(name, x, w=8, d=10, h=3.2, floors=1, wall='plaster', roofc=None):
    P = M(); r = root(name, x)
    H = h * floors
    parts = [bl.box('walls', (w, d, H), (0, 0, H / 2), P[wall])]
    bl.uv_box(parts[0], 3 if wall == 'siding' else 4)
    rh = w * .38
    # roof: two slabs meeting at the ridge, with overhang
    for sx in (1, -1):
        ang = math.atan2(rh, w / 2)
        L = math.hypot(w / 2, rh) + .5
        s = bl.box('roof', (L, d + .8, .18), (sx * w / 4, 0, H + rh / 2), P['roof'], rot=(0, sx * -ang, 0))
        bl.uv_box(s, 3); parts.append(s)
    # gable ends
    for sy in (1, -1):
        g = bl.mesh_from('gable', [(-w / 2, sy * d / 2, H), (w / 2, sy * d / 2, H), (0, sy * d / 2, H + rh)], [(0, 1, 2)], P[wall])
        parts.append(g)
    # chimney
    parts.append(bl.box('chimney', (.7, .7, 2.2), (w * .25, d * .2, H + rh * .6), P['plaster']))
    # door + windows on the front (-Y)
    parts.append(bl.box('door', (1.0, .1, 2.1), (-w * .2, -d / 2 - .03, 1.05), P['door']))
    parts.append(bl.box('doortrim', (1.2, .08, .12), (-w * .2, -d / 2 - .04, 2.15), P['trim']))
    for f in range(floors):
        for wx in ((w * .2,) if f == 0 else (-w * .25, w * .2)):
            parts.append(bl.box('win', (1.2, .08, 1.2), (wx, -d / 2 - .03, 1.6 + f * h), P['window']))
            parts.append(bl.box('sill', (1.4, .14, .1), (wx, -d / 2 - .05, .95 + f * h), P['trim']))
        for sx in (1, -1):
            parts.append(bl.box('sidewin', (.08, 1.2, 1.2), (sx * (w / 2 + .03), 0, 1.6 + f * h), P['window']))
    # porch
    parts.append(bl.box('porch', (w * .6, 1.6, .2), (-w * .1, -d / 2 - .8, .1), P['planks']))
    return pack(r, parts)


def shop(name, x):
    P = M(); r = root(name, x)
    parts = [bl.box('walls', (12, 9, 4.5), (0, 0, 2.25), P['plaster']), bl.box('roof', (12.6, 9.6, .3), (0, 0, 4.6), P['gunmetal']),
             bl.box('front', (10, .1, 2.6), (0, -4.55, 1.5), P['glass']), bl.box('awning', (11, 1.6, .15), (0, -5.3, 3.1), bl.mat('awning', '#2f6a8a', 0, .7)),
             bl.box('sign', (6, .2, .9), (0, -4.6, 3.9), bl.mat('shopsign', '#ffcf6a', 0, .4, emit='#ffcf6a', strength=2))]
    bl.uv_box(parts[0], 4)
    return pack(r, parts)


def barn(name, x):
    P = M(); r = root(name, x)
    w, d, h = 12, 18, 5
    parts = [bl.box('walls', (w, d, h), (0, 0, h / 2), P['barnred'])]
    bl.uv_box(parts[0], 6)
    # gambrel roof as a loft
    prof = [(-w / 2 - .3, h), (-w * .35, h + 2.6), (0, h + 4), (w * .35, h + 2.6), (w / 2 + .3, h)]
    verts = [(px, sy * (d / 2 + .4), pz) for sy in (-1, 1) for px, pz in prof]
    faces = [(i, i + 1, i + 6, i + 5) for i in range(4)]
    roof = bl.mesh_from('roof', verts, faces, P['gunmetal'])
    md = roof.modifiers.new('s', 'SOLIDIFY'); md.thickness = .15
    bpy.context.view_layer.objects.active = roof; roof.select_set(True); bpy.ops.object.modifier_apply(modifier=md.name); roof.select_set(False)
    parts.append(roof)
    for sy in (1, -1):
        g = bl.mesh_from('gable', [(prof[0][0] + .3, sy * d / 2, h), (prof[1][0], sy * d / 2, prof[1][1]), (0, sy * d / 2, prof[2][1]), (prof[3][0], sy * d / 2, prof[3][1]), (prof[4][0] - .3, sy * d / 2, h)],
                         [(0, 1, 2, 3, 4)], P['barnred'])
        parts.append(g)
    parts.append(bl.box('door', (4.5, .15, 4), (0, -d / 2 - .05, 2), P['planks']))
    for a in (1, -1):
        parts.append(bl.box('x', (6, .1, .25), (0, -d / 2 - .12, 2), P['white'], rot=(0, a * .73, 0)))
    parts.append(bl.box('loft', (2, .15, 1.6), (0, -d / 2 - .05, h + 1.8), P['planks']))
    return pack(r, parts)


def silo(name, x):
    P = M(); r = root(name, x)
    parts = [bl.cyl('silo', 2.4, 12, (0, 0, 6), P['galv'], 24), bl.sphere('dome', 2.45, (0, 0, 12), P['galv'], 24, 10, scale=(1, 1, .6))]
    for z in range(1, 12, 2):
        parts.append(bl.torus('band', 2.42, .04, (0, 0, z), P['gunmetal'], maj=24, mn=4))
    parts.append(bl.box('ladder', (.4, .1, 12), (0, -2.45, 6), P['gunmetal']))
    return pack(r, parts)


def fence(name, x, L=6):
    P = M(); r = root(name, x)
    parts = []
    for i in range(4):
        parts.append(bl.box('post', (.15, .15, 1.3), (-L / 2 + i * L / 3, 0, .65), P['planks']))
    for z in (.45, .95):
        parts.append(bl.box('rail', (L, .08, .14), (0, 0, z), P['planks']))
    return pack(r, parts)


def hay(name, x):
    P = M(); r = root(name, x); r['solid'] = 1
    return pack(r, [bl.cyl('bale', .75, 1.3, (0, 0, .75), P['hay'], 16, rot=(R90, 0, 0))])


def crop(name, x, kind):
    P = M(); r = root(name, x); r['solid'] = 0
    parts = []
    import random
    rnd = random.Random(len(name))
    for i in range(5):
        h = (.9 if kind == 'wheat' else 2.0) * rnd.uniform(.85, 1.15)
        a = rnd.random() * 6.28; d = rnd.random() * .25
        parts.append(bl.cyl('stalk', .05 if kind == 'wheat' else .07, h, (math.cos(a) * d, math.sin(a) * d, h / 2), P[kind], 5, r2=.02))
        if kind == 'corn':
            for j in range(3):
                parts.append(bl.box('leaf', (.6, .05, .02), (math.cos(a) * d, math.sin(a) * d, h * (.3 + .2 * j)), P['corn'], rot=(0, .5, a + j * 2)))
    return pack(r, parts)


def tractor(name, x):
    P = M(); r = root(name, x)
    parts = [bl.box('body', (1.6, 3.0, 1.2), (0, 0, 1.3), P['tractor'], bevel=.08),
             bl.box('cab', (1.5, 1.4, 1.6), (0, .6, 2.6), P['glass'], bevel=.05), bl.box('roofc', (1.6, 1.5, .1), (0, .6, 3.45), P['tractor']),
             bl.cyl('stack', .08, 1.2, (.4, -1.0, 2.4), P['gunmetal'], 8)]
    for sx in (1, -1):
        parts.append(bl.cyl('rear', .85, .5, (sx * 1.0, .8, .85), P['rubber'], 18, rot=(0, R90, 0)))
        parts.append(bl.cyl('front', .5, .35, (sx * .9, -1.1, .5), P['rubber'], 14, rot=(0, R90, 0)))
        parts.append(bl.cyl('hub', .35, .52, (sx * 1.0, .8, .85), P['machine_yellow'] if 'machine_yellow' in P else P['yellow'], 12, rot=(0, R90, 0)))
    return pack(r, parts)


def turbine(name, x):
    P = M(); r = root(name, x)
    parts = [bl.cyl('tower', 1.2, 40, (0, 0, 20), P['white'], 16, r2=.6), bl.box('nacelle', (1.4, 4, 1.6), (0, -.5, 40.6), P['white'], bevel=.3)]
    pack(r, parts)
    hub = bl.empty('turbine_rotor', (0, -2.7, 40.6), r)
    blades = [bl.sphere('hub', .7, (0, 0, 0), P['white'], 12, 8, scale=(1, 1.4, 1))]
    for i in range(3):
        a = i * 2 * math.pi / 3
        blades.append(bl.box('blade', (.6, .15, 16), (math.sin(a) * 8, 0, math.cos(a) * 8), P['white'], rot=(0, a, 0)))
    for o in blades:
        bl.apply_all(o)
    g = bl.join(blades, 'rotor_mesh'); g.parent = hub
    return r


def water_tower(name, x):
    P = M(); r = root(name, x)
    parts = [bl.cyl('tank', 4, 5, (0, 0, 17), P['galv'], 20), bl.cyl('cone', 4.2, 2, (0, 0, 20.5), P['galv'], 20, r2=.3)]
    for i in range(4):
        a = i * R90 + math.pi / 4
        parts.append(bl.box('leg', (.35, .35, 15), (math.cos(a) * 3, math.sin(a) * 3, 7.5), P['gunmetal'], rot=(0, 0, a)))
    return pack(r, parts)


def gas_station(name, x):
    P = M(); r = root(name, x)
    parts = [bl.box('canopy', (14, 9, .6), (0, 0, 5), P['white']), bl.box('canopyband', (14.1, 9.1, .3), (0, 0, 4.8), bl.mat('gasred', '#c42b23', .2, .5)),
             bl.box('kiosk', (8, 6, 3.4), (0, 9, 1.7), P['plaster']), bl.box('kioskglass', (6, .1, 2), (0, 5.95, 1.4), P['glass'])]
    for sx in (-3, 3):
        parts.append(bl.box('pillar', (.5, .5, 5), (sx, 0, 2.5), P['white']))
        parts.append(bl.box('pump', (.8, 1.4, 1.8), (sx, 0, .9), bl.mat('pump', '#e0e0e0', .2, .4), bevel=.08))
    parts.append(bl.box('sign', (.4, 2.4, 6), (8.5, 0, 3), bl.mat('gassign', '#c42b23', .2, .5, emit='#ff6a4a', strength=1)))
    return pack(r, parts)


def sign(name, x, color='#2f7a3a'):
    P = M(); r = root(name, x); r['solid'] = 0
    return pack(r, [bl.cyl('pole', .06, 3, (0, 0, 1.5), P['steel'], 8), bl.box('board', (2.4, .08, 1.0), (0, 0, 2.7), bl.mat('roadsign' + color, color, .2, .5))])


def main():
    bl.reset()
    make_textures()
    P = M()
    x = 0
    def nx(w=30):
        nonlocal x
        x += w
        return x
    tree_round('RU_tree_oak', nx(), 1, P['leaves']); tree_round('RU_tree_maple', nx(), 7, P['leaves2'], 6.0)
    tree_round('RU_tree_birch', nx(), 13, P['leaves'], 8.5); tree_pine('RU_tree_pine', nx(), 3); bush('RU_bush', nx(), 5)
    gable_house('RU_house_a', nx(), 8, 10, 3.2, 1, 'plaster'); gable_house('RU_house_b', nx(), 9, 11, 3.0, 2, 'siding')
    gable_house('RU_house_c', nx(), 7, 9, 3.0, 1, 'siding'); gable_house('RU_farmhouse', nx(), 10, 12, 3.2, 2, 'plaster')
    shop('RU_shop', nx()); barn('RU_barn', nx(40)); silo('RU_silo', nx()); fence('RU_fence', nx()); hay('RU_hay', nx())
    crop('RU_wheat', nx(), 'wheat'); crop('RU_corn', nx(), 'corn'); tractor('RU_tractor', nx())
    turbine('RU_turbine', nx(40)); water_tower('RU_watertower', nx(30)); gas_station('RU_gas', nx(40)); sign('RU_sign', nx())
    bl.export('rural.glb')


main()
