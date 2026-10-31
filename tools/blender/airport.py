"""New Meridian Spaceport: the airport where the Wayfarer's jumpship lands, south of the city across the ring road.

airport.glb, root 'AP_site' (origin = centre of landing pad 1, placed by earth.js at AIRPORT.x/z):
  AP_ground   runway, taxiways, apron, pads, landside roads and parking with painted markings and tyre marks
  AP_build    terminal (walkable hall with a glass curtain wall), control tower, hangars, fuel farm
  AP_lights   runway edge / threshold / approach / PAPI lights, taxiway lights, pad ring lights (emissive)
  AP_props    fuel trucks, tug and baggage carts, stairs truck, power units, signs, fence
  AP_radar    the tower's radar head (spun in-engine), AP_windsock x2 (child 'windsock_sock' sways in-engine)
The root carries extras.worldex (JSON): AABB colliders, pad centres, spawn, vendor spot and windsock/radar
anchors, all already in three space (x east, y up, z south) relative to the root.

Textures are baked first (Cycles + numpy) into assets/textures/ap_*.{jpg,png} and embedded in the GLB:
runway/apron concrete slabs, worn paint, tyre rubber streaks, metal cladding, glass smudges, terrazzo, chain-link.
Usage: blender --background --python tools/blender/airport.py [-- --fast]   (--fast reuses existing textures)
"""
import bpy, bmesh, math, os, sys, json
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import bl
from textures import G, bake, setup as tex_setup

R90 = math.pi / 2
FAST = '--fast' in sys.argv

# ---------------------------------------------------------------- layout (three space, metres, relative to pad 1)
RWY_Z, RWY_X0, RWY_X1, RWY_W = 100.0, -365.0, 235.0, 45.0
TWY_Z, TWY_X0, TWY_X1, TWY_W = 50.0, -345.0, 215.0, 23.0
LINKS = (-345.0, -65.0, 215.0)
APRON = (-345.0, -40.0, 200.0, 38.5)
PADS = ((0.0, 0.0), (-120.0, 0.0), (120.0, 0.0))
HANGARS = (-315.0, -255.0, -195.0)
HANGAR_Z0, HANGAR_Z1, HANGAR_W, HANGAR_H = -34.0, 10.0, 54.0, 12.0
TERM = (-80.0, -80.0, 80.0, -42.0)          # x0, z0 (landside facade), x1, z1 (airside facade)
TERM_H = 13.0
DOORS = (-40.0, 0.0, 40.0)
TOWER = (130.0, -66.0)
FUEL = (160.0, -84.0, 210.0, -50.0)
FENCE = (-420.0, -90.0, 315.0, 150.0)
FORECOURT_Z, ROAD_W = -104.0, 12.0
LOTS = ((-235.0, -132.0, -128.0, -96.0), (128.0, -132.0, 235.0, -96.0))

COLLIDERS = []


def col(x0, y0, z0, x1, y1, z1, tag='airport'):
    COLLIDERS.append([round(min(x0, x1), 3), round(min(y0, y1), 3), round(min(z0, z1), 3),
                      round(max(x0, x1), 3), round(max(y0, y1), 3), round(max(z0, z1), 3), tag])


def L(x, y, z):
    """three (x, y, z) -> Blender location."""
    return (x, -z, y)


def B(name, size, pos, m, yaw=0.0, bevel=0.0, segs=2):
    """Box: size (sx, sy, sz) and centre pos in three space, yaw about the vertical."""
    sx, sy, sz = size
    o = bl.box(name, (sx, sz, sy), L(*pos), m, bevel=bevel, rot=(0, 0, yaw), segs=segs)
    bl.apply_all(o)
    return o


def C(name, r, h, base, m, verts=16, r2=None, smooth=True):
    """Vertical cylinder standing on base (three space)."""
    x, y, z = base
    o = bl.cyl(name, r, h, L(x, y + h / 2, z), m, verts, r2=r2, smooth=smooth)
    bl.apply_all(o)
    return o


def CX(name, r, length, centre, m, verts=12, axis='x'):
    """Horizontal cylinder along three x or z."""
    rot = (0, R90, 0) if axis == 'x' else (R90, 0, 0)
    o = bl.cyl(name, r, length, L(*centre), m, verts, rot=rot)
    bl.apply_all(o)
    return o


def dup(o, pos, yaw=0.0):
    """Cheap copy of an applied prototype at pos (three space) turned by yaw; joined later."""
    c = o.copy(); c.data = o.data.copy()
    bpy.context.scene.collection.objects.link(c)
    c.location = L(*pos); c.rotation_euler = (0, 0, yaw)
    return c


def quad(name, x0, z0, x1, z1, y, m, tile=10.0, uv=None):
    """Flat ground quad in three space with world-scale UVs (u along x, v along z)."""
    verts = [L(x0, y, z0), L(x1, y, z0), L(x1, y, z1), L(x0, y, z1)]
    o = bl.mesh_from(name, verts, [(0, 3, 2, 1)], m)
    me = o.data; lay = me.uv_layers.new(name='UVMap')
    pts = uv or [(x0 / tile, z0 / tile), (x1 / tile, z0 / tile), (x1 / tile, z1 / tile), (x0 / tile, z1 / tile)]
    order = [0, 3, 2, 1]
    for li, loop in enumerate(me.polygons[0].loop_indices):
        u, v = pts[order[li]]
        lay.data[loop].uv = (u, -v)
    return o


def strip(name, xa, za, xb, zb, w, y, m, tile=4.0):
    """A painted line of width w from (xa, za) to (xb, zb)."""
    dx, dz = xb - xa, zb - za; ln = math.hypot(dx, dz) or 1
    nx, nz = -dz / ln * w / 2, dx / ln * w / 2
    P = [(xa + nx, za + nz), (xb + nx, zb + nz), (xb - nx, zb - nz), (xa - nx, za - nz)]
    verts = [L(px, y, pz) for px, pz in P]
    o = bl.mesh_from(name, verts, [(0, 3, 2, 1)], m)
    me = o.data; lay = me.uv_layers.new(name='UVMap')
    uvs = [(0, 0), (ln / tile, 0), (ln / tile, w / tile), (0, w / tile)]
    order = [0, 3, 2, 1]
    for li, loop in enumerate(me.polygons[0].loop_indices):
        lay.data[loop].uv = uvs[order[li]]
    return face_up(o)


def face_up(o):
    """Flip any face whose normal points down (flat ground pieces)."""
    bm = bmesh.new(); bm.from_mesh(o.data)
    for f in bm.faces:
        f.normal_update()
        if f.normal.z < 0:
            f.normal_flip()
    bm.to_mesh(o.data); bm.free()
    return o


def disc(name, cx, cz, r0, r1, y, m, n=64, tile=6.0):
    """Flat ring (r0 = 0 -> filled disc) in three space."""
    verts, faces = [], []
    for k in range(n):
        a = k / n * math.tau
        verts.append(L(cx + math.cos(a) * r1, y, cz + math.sin(a) * r1))
        verts.append(L(cx + math.cos(a) * r0, y, cz + math.sin(a) * r0))
    for k in range(n):
        a, b = k * 2, ((k + 1) % n) * 2
        faces.append((a, b, b + 1, a + 1))
    o = bl.mesh_from(name, verts, faces, m)
    me = o.data; lay = me.uv_layers.new(name='UVMap')
    for p in me.polygons:
        for loop in p.loop_indices:
            v = me.vertices[me.loops[loop].vertex_index].co
            lay.data[loop].uv = (v.x / tile, v.y / tile)
    bm = bmesh.new(); bm.from_mesh(me); bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    for f in bm.faces:
        if f.normal.z < 0:
            f.normal_flip()
    bm.to_mesh(me); bm.free()
    return o


def text(name, body, size, pos, m, yaw=0.0, flat=False, extrude=0.0, align='CENTER'):
    """Blender text converted to mesh. flat=True lays it on the ground (reads from +z looking -z when yaw=0)."""
    bpy.ops.object.text_add(location=(0, 0, 0))
    o = bpy.context.object
    o.data.body = body; o.data.size = size; o.data.extrude = extrude
    o.data.align_x = align; o.data.align_y = 'CENTER'
    bpy.ops.object.convert(target='MESH')
    o = bpy.context.object; o.name = name
    o.data.materials.clear(); o.data.materials.append(m)
    if flat:
        o.rotation_euler = (0, 0, yaw)
    else:
        o.rotation_euler = (R90, 0, yaw)
    o.location = L(*pos)
    bl.apply_all(o)
    return o


def solidify(o, t):
    md = o.modifiers.new('sd', 'SOLIDIFY'); md.thickness = t; md.offset = -1
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.modifier_apply(modifier=md.name)
    return o


def grid_surface(name, xs, zs, yfn, m, uv_scale=8.0):
    """Height-field surface (three space) over the grid xs * zs."""
    verts = [L(x, yfn(x, z), z) for z in zs for x in xs]
    nx = len(xs); faces = []
    for j in range(len(zs) - 1):
        for i in range(nx - 1):
            a = j * nx + i
            faces.append((a, a + nx, a + nx + 1, a + 1))
    o = bl.mesh_from(name, verts, faces, m)
    bl.uv_box(o, uv_scale)
    return o


# ---------------------------------------------------------------- textures
def tex_noise(g, fu, fv, detail=4, rough=.55, seed=0.0):
    """Seamless 4D noise with different feature counts along u and v (streaks, slabs)."""
    tc = g.n('ShaderNodeTexCoord')
    sep = g.n('ShaderNodeSeparateXYZ'); g.nt.links.new(tc.outputs['UV'], sep.inputs[0])
    out = []
    for comp, f in ((sep.outputs[0], fu), (sep.outputs[1], fv)):
        R = f / (2 * math.pi); ang = g.math('MULTIPLY', comp, 2 * math.pi)
        out.append(g.math('MULTIPLY', g.math('COSINE', ang), R)); out.append(g.math('MULTIPLY', g.math('SINE', ang), R))
    cmb = g.n('ShaderNodeCombineXYZ')
    for i in range(3):
        g.nt.links.new(out[i], cmb.inputs[i])
    w = g.math('ADD', out[3], seed * 17.31)
    nd = g.n('ShaderNodeTexNoise', noise_dimensions='4D')
    g.nt.links.new(cmb.outputs[0], nd.inputs['Vector']); g.nt.links.new(w, nd.inputs['W'])
    nd.inputs['Scale'].default_value = 1.0; nd.inputs['Detail'].default_value = detail; nd.inputs['Roughness'].default_value = rough
    return nd.outputs['Fac']


def save_rgba(name, arr):
    """arr: HxWx4 float 0..1 (row 0 = top) -> assets/textures/<name>.png"""
    h, w = arr.shape[:2]
    img = bpy.data.images.new(name, w, h, alpha=True)
    img.pixels = np.ascontiguousarray(arr[::-1]).astype(np.float32).ravel()
    img.filepath_raw = os.path.join(bl.TEXTURES, name + '.png'); img.file_format = 'PNG'; img.save()
    print('[texture]', name + '.png')


def bake_textures():
    p = tex_setup()
    bpy.context.scene.cycles.samples = 8

    # runway / apron concrete: 2 x 2 cast slabs per tile with sawn joints, per-slab tone, aggregate, rubber and oil
    def slab_c(g):
        b = g.brick(.5, .5, offset=0.0, mortar=.006, c1=(.60, .60, .58), c2=(.53, .53, .51), bias=0)
        agg = g.ramp(g.noise(90, 3, .6, 3), [(.35, '#ffffff'), (.65, '#cfcbc4')])
        cloud = g.ramp(g.noise(5, 6, .62, 4), [(.3, '#f2f0ea'), (.7, '#a9a59d')])
        oil = g.ramp(tex_noise(g, 3, 9, 5, .6, 5), [(.62, '#ffffff'), (.78, '#7d7a76')])
        cr = g.voronoi(7, 6, 'DISTANCE_TO_EDGE', 'Distance')
        crack = g.ramp(cr, [(0.0, '#5a5854'), (.012, '#ffffff')])
        c = g.mix(b.outputs['Color'], agg, 1.0, 'MULTIPLY')
        c = g.mix(c, cloud, 1.0, 'MULTIPLY'); c = g.mix(c, oil, 1.0, 'MULTIPLY')
        c = g.mix(c, crack, .65, 'MULTIPLY')
        return g.mix(c, (.16, .16, .16), b.outputs['Fac'])

    def slab_h(g):
        b = g.brick(.5, .5, offset=0.0, mortar=.006)
        cr = g.voronoi(7, 6, 'DISTANCE_TO_EDGE', 'Distance')
        crk = g.math('MULTIPLY', g.math('LESS_THAN', cr, .01), -.4)
        return g.math('ADD', g.math('ADD', g.math('MULTIPLY', b.outputs['Fac'], -1.0), g.math('MULTIPLY', g.noise(60, 4, .6, 8), .12)), crk)
    bake(p, 'ap_slab', slab_c, slab_h, strength=.55, size=1024)

    # worn paint for markings (white; tinted yellow / red in the material)
    def paint_c(g):
        chip = g.ramp(g.noise(14, 6, .7, 11), [(.28, '#77736d'), (.34, '#ffffff')])
        grime = g.ramp(g.noise(4, 5, .6, 12), [(.3, '#ffffff'), (.8, '#c9c6bf')])
        spk = g.ramp(g.noise(120, 2, .5, 13), [(.6, '#ffffff'), (.75, '#a8a49c')])
        return g.mix(g.mix(chip, grime, 1.0, 'MULTIPLY'), spk, 1.0, 'MULTIPLY')
    bake(p, 'ap_paint', paint_c, None, size=512)

    # corrugated metal cladding: trapezoid ribs, sheet laps, rain streaks
    def clad_c(g):
        rib = g.brick(1 / 24, 1.0, offset=0.0, mortar=.012, c1=(.72, .74, .76), c2=(.70, .72, .74))
        lap = g.brick(1.0, .5, offset=0.0, mortar=.004)
        streak = g.ramp(tex_noise(g, 40, 2, 5, .6, 21), [(.35, '#ffffff'), (.72, '#8d8f8f')])
        dirt = g.ramp(g.noise(5, 6, .6, 22), [(.4, '#ffffff'), (.8, '#b9b4aa')])
        c = g.mix(rib.outputs['Color'], (.52, .54, .56), rib.outputs['Fac'])
        c = g.mix(c, (.35, .36, .37), lap.outputs['Fac'])
        return g.mix(g.mix(c, streak, 1.0, 'MULTIPLY'), dirt, 1.0, 'MULTIPLY')

    def clad_h(g):
        rib = g.brick(1 / 24, 1.0, offset=0.0, mortar=.012)
        lap = g.brick(1.0, .5, offset=0.0, mortar=.004)
        return g.math('ADD', g.math('MULTIPLY', rib.outputs['Fac'], 1.0), g.math('MULTIPLY', lap.outputs['Fac'], -.6))
    bake(p, 'ap_clad', clad_c, clad_h, strength=.9, size=1024)

    # glass smudges / water marks (near white; multiplies the glass tint)
    def glass_c(g):
        s = g.ramp(tex_noise(g, 6, 1, 6, .65, 31), [(.3, '#ffffff'), (.75, '#c8d2d8')])
        d = g.ramp(g.noise(20, 4, .6, 32), [(.55, '#ffffff'), (.7, '#dfe4e6')])
        return g.mix(s, d, 1.0, 'MULTIPLY')
    bake(p, 'ap_glass', glass_c, None, size=512)

    # terrazzo floor for the terminal hall
    def terr_c(g):
        base = g.ramp(g.noise(8, 4, .5, 41), [(.3, '#d9d4cc'), (.7, '#cbc5bb')])
        v = g.voronoi(70, 42, 'F1', 'Distance')
        chips = g.ramp(g.voronoi(70, 42, 'F1', 'Color'), [(0.0, '#5d6670'), (.5, '#a89a86'), (1.0, '#3d3a38')])
        c = g.mix(base, chips, g.math('LESS_THAN', v, .18))
        tile = g.brick(.25, .25, offset=0.0, mortar=.003)
        return g.mix(c, (.55, .54, .52), tile.outputs['Fac'])
    bake(p, 'ap_terrazzo', terr_c, None, size=1024)

    rs = np.random.RandomState(7)
    # tyre rubber streaks (RGBA, tiles along u = the runway)
    W, H = 1024, 256
    a = np.zeros((H, W), np.float32)
    u = np.arange(W) / W
    for k in range(70):
        v0 = H * (.12 + .76 * rs.rand()); wid = 1.5 + rs.rand() * 6
        ph = rs.rand(4) * math.tau; fr = rs.randint(1, 6, 4)
        dens = .5 + .5 * np.sin(u * math.tau * fr[0] + ph[0]) * np.sin(u * math.tau * fr[1] + ph[1])
        dens = np.clip(dens * 1.4 - .2, 0, 1) * (.35 + .65 * rs.rand())
        drift = (np.sin(u * math.tau * fr[2] + ph[2]) * 3 + np.sin(u * math.tau * fr[3] + ph[3]) * 1.5)
        rows = np.arange(H)[:, None]
        a += dens[None, :] * np.exp(-((rows - v0 - drift[None, :]) / wid) ** 2)
    a = np.clip(a * .9, 0, 1)
    edge = np.clip(np.minimum(np.arange(H), H - 1 - np.arange(H)) / (H * .12), 0, 1)[:, None]
    grain = rs.rand(H, W).astype(np.float32) * .25 + .75
    alpha = np.clip(a * edge * grain, 0, .92)
    rgba = np.zeros((H, W, 4), np.float32); rgba[..., 0] = .045; rgba[..., 1] = .043; rgba[..., 2] = .04; rgba[..., 3] = alpha
    save_rgba('ap_tyre', rgba)
    # chain-link diamond mesh
    S = 256
    yy, xx = np.mgrid[0:S, 0:S] / S * 4.0
    d1 = np.abs(((xx + yy) % 1.0) - .5); d2 = np.abs(((xx - yy) % 1.0) - .5)
    wire = np.clip(1 - np.minimum(.5 - d1, .5 - d2) / .035, 0, 1)
    rgba = np.zeros((S, S, 4), np.float32); rgba[..., :3] = .62; rgba[..., 3] = wire
    save_rgba('ap_chainlink', rgba)


# ---------------------------------------------------------------- materials
def mats():
    p = bl.palette()
    T = lambda n: n if os.path.exists(os.path.join(bl.TEXTURES, n)) else None
    p.update(
        runway=bl.mat('ap_runway', '#cfccc6', 0, .82, image='ap_slab_c.jpg', normal='ap_slab_n.jpg'),
        apron=bl.mat('ap_apron', '#e2ded6', 0, .8, image='ap_slab_c.jpg', normal='ap_slab_n.jpg'),
        pad=bl.mat('ap_pad', '#b9bcc0', .1, .62, image='ap_slab_c.jpg', normal='ap_slab_n.jpg'),
        asphalt=bl.mat('ap_asphalt', '#8e8e94', 0, .85, image='asphalt_c.jpg', normal='asphalt_n.jpg'),
        kerb=bl.mat('ap_kerb', '#d4cfc6', 0, .85, image='concrete_c.jpg', normal='concrete_n.jpg'),
        white=bl.mat('ap_paint_white', '#f4f2ec', 0, .6, image='ap_paint_c.jpg'),
        yellow=bl.mat('ap_paint_yellow', '#f2b51c', 0, .6, image='ap_paint_c.jpg'),
        redpaint=bl.mat('ap_paint_red', '#b8231d', 0, .6, image='ap_paint_c.jpg'),
        black=bl.mat('ap_paint_black', '#1a1a1c', 0, .7, image='ap_paint_c.jpg'),
        tyre=bl.mat('ap_tyre', '#ffffff', 0, .9, image=T('ap_tyre.png'), alpha=.99),
        clad=bl.mat('ap_cladding', '#d9dde2', .65, .38, image='ap_clad_c.jpg', normal='ap_clad_n.jpg'),
        clad_dark=bl.mat('ap_cladding_dark', '#5b6470', .65, .4, image='ap_clad_c.jpg', normal='ap_clad_n.jpg'),
        roof=bl.mat('ap_roof', '#e8e6e0', .3, .45, image='ap_clad_c.jpg', normal='ap_clad_n.jpg'),
        soffit=bl.mat('ap_soffit', '#c8a27a', .1, .55, image='ap_clad_c.jpg'),
        glass=bl.mat('ap_glass', '#9cc4d4', .2, .04, image='ap_glass_c.jpg', alpha=.32),
        mullion=bl.mat('ap_mullion', '#a9b0b8', .9, .28),
        floor=bl.mat('ap_floor', '#ffffff', 0, .22, image='ap_terrazzo_c.jpg'),
        concrete=bl.mat('ap_concrete', '#c4bfb6', 0, .85, image='concrete_c.jpg', normal='concrete_n.jpg'),
        fence=bl.mat('ap_fence', '#ffffff', .6, .5, image=T('ap_chainlink.png'), alpha=.99),
        lw=bl.mat('ap_light_white', '#fff4dc', 0, .3, emit='#fff1d6', strength=9),
        lb=bl.mat('ap_light_blue', '#2a6aff', 0, .3, emit='#3a7aff', strength=9),
        lg=bl.mat('ap_light_green', '#2aff6a', 0, .3, emit='#2aff70', strength=9),
        lr=bl.mat('ap_light_red', '#ff2a1a', 0, .3, emit='#ff2a1a', strength=9),
        la=bl.mat('ap_light_amber', '#ffae2f', 0, .3, emit='#ffae2f', strength=9),
        lc=bl.mat('ap_light_cyan', '#40e0ff', 0, .3, emit='#40e0ff', strength=9),
        panel=bl.mat('ap_ceiling_light', '#fff6e8', 0, .3, emit='#fff1dc', strength=3),
        screen=bl.mat('ap_screen', '#081820', 0, .25, emit='#2ad0ff', strength=2.2),
        sign=bl.mat('ap_sign_glow', '#e8f8ff', 0, .3, emit='#d8f4ff', strength=5),
        truck=bl.mat('ap_truck_white', '#e8e6e0', .2, .4),
        truck_y=bl.mat('ap_truck_yellow', '#e0a81c', .3, .42),
        tank=bl.mat('ap_tank', '#d8dadc', .7, .3),
        tyres=bl.mat('ap_tyres', '#161617', 0, .9),
        orange=bl.mat('ap_sock_orange', '#ff6a12', 0, .7),
        sockw=bl.mat('ap_sock_white', '#f0eee8', 0, .7),
        seat=bl.mat('ap_seat', '#2a3442', .2, .5),
        wood=bl.mat('ap_counter', '#7a5a3e', 0, .45),
        plant=bl.mat('ap_plant', '#3f6e34', 0, .85),
    )
    # alpha-cut maps: wire the image alpha into the shader so the glTF gets the cut-out
    for k in ('tyre', 'fence'):
        nt = p[k].node_tree; tn = [n for n in nt.nodes if n.type == 'TEX_IMAGE']
        if tn:
            nt.links.new(tn[0].outputs['Alpha'], nt.nodes['Principled BSDF'].inputs['Alpha'])
    return p


# ---------------------------------------------------------------- ground: runway, taxiways, apron, landside
def ground(m):
    P = []
    y0 = .06
    # runway with paved shoulders
    P.append(quad('rwy', RWY_X0, RWY_Z - RWY_W / 2, RWY_X1, RWY_Z + RWY_W / 2, y0, m['runway'], 15))
    P.append(quad('shoulderN', RWY_X0 - 10, RWY_Z - RWY_W / 2 - 6, RWY_X1 + 10, RWY_Z - RWY_W / 2, y0 - .01, m['asphalt'], 10))
    P.append(quad('shoulderS', RWY_X0 - 10, RWY_Z + RWY_W / 2, RWY_X1 + 10, RWY_Z + RWY_W / 2 + 6, y0 - .01, m['asphalt'], 10))
    P.append(quad('blastW', RWY_X0 - 40, RWY_Z - RWY_W / 2, RWY_X0, RWY_Z + RWY_W / 2, y0 - .01, m['asphalt'], 10))
    P.append(quad('blastE', RWY_X1, RWY_Z - RWY_W / 2, RWY_X1 + 40, RWY_Z + RWY_W / 2, y0 - .01, m['asphalt'], 10))
    # taxiway + links to the runway
    P.append(quad('twy', TWY_X0 - TWY_W / 2, TWY_Z - TWY_W / 2, TWY_X1 + TWY_W / 2, TWY_Z + TWY_W / 2, y0 + .005, m['asphalt'], 10))
    for x in LINKS:
        P.append(quad('link', x - TWY_W / 2, TWY_Z + TWY_W / 2, x + TWY_W / 2, RWY_Z - RWY_W / 2, y0 + .005, m['asphalt'], 10))
    # apron and pads
    ax0, az0, ax1, az1 = APRON
    P.append(quad('apron', ax0, az0, ax1, az1, y0 + .01, m['apron'], 15))
    for k, (px, pz) in enumerate(PADS):
        P.append(disc('pad', px, pz, 0, 15, y0 + .03, m['pad'], 64, 8))
    # (hangar floors are the apron slab itself)
    # landside: forecourt road, spur to the ring road, kerb walk, parking lots
    P.append(quad('forecourt', -128, FORECOURT_Z - ROAD_W / 2, 128, FORECOURT_Z + ROAD_W / 2, y0, m['asphalt'], 10))
    P.append(quad('spur', -ROAD_W / 2, -137, ROAD_W / 2, FORECOURT_Z - ROAD_W / 2, y0, m['asphalt'], 10))
    P.append(quad('kerbwalk', -130, FORECOURT_Z + ROAD_W / 2, 130, TERM[1], y0 + .1, m['kerb'], 6))
    for x0, z0, x1, z1 in LOTS:
        P.append(quad('lot', x0, z0, x1, z1, y0, m['asphalt'], 10))
    # tower and fuel farm yards
    P.append(quad('toweryard', TOWER[0] - 14, TOWER[1] - 14, TOWER[0] + 14, TOWER[1] + 14, y0 + .01, m['apron'], 12))
    P.append(quad('fuelyard', FUEL[0] - 4, FUEL[1] - 4, FUEL[2] + 4, FUEL[3] + 4, y0 + .01, m['concrete'], 8))
    # service road from the fuel farm round to the apron
    P.append(quad('service', FUEL[0] - 4, FUEL[3] + 4, FUEL[0] + 8, APRON[1], y0, m['asphalt'], 10))
    return P


def markings(m):
    W, Y_, R, K = m['white'], m['yellow'], m['redpaint'], m['black']
    P = []
    y = .085
    hw = RWY_W / 2
    # edge lines and centreline dashes (30 m painted, 20 m gap)
    for s in (-1, 1):
        P.append(strip('edge', RWY_X0, RWY_Z + s * (hw - .9), RWY_X1, RWY_Z + s * (hw - .9), .9, y, W))
    x = RWY_X0 + 60
    while x + 30 < RWY_X1 - 60:
        P.append(strip('cl', x, RWY_Z, x + 30, RWY_Z, .9, y, W)); x += 50
    for end, sgn in ((RWY_X0, 1), (RWY_X1, -1)):
        # threshold piano keys: 6 stripes each side of the centreline
        for s in (-1, 1):
            for k in range(6):
                zc = RWY_Z + s * (3.2 + k * 3.1)
                P.append(strip('thr', end + sgn * 6, zc, end + sgn * 36, zc, 1.8, y, W))
        # threshold bar
        P.append(strip('thrbar', end + sgn * 2, RWY_Z - hw + 1, end + sgn * 2, RWY_Z + hw - 1, 1.8, y, W))
        # designation numbers (heading 09 at the west end reads from the approach, 27 at the east end)
        num = '09' if sgn > 0 else '27'
        P.append(text('rwnum', num, 15, (end + sgn * 52, y + .002, RWY_Z), W, yaw=(R90 if sgn > 0 else -R90), flat=True))
        # touchdown zone bars and aiming point blocks
        for dist, n in ((95, 3), (150, 2), (205, 1)):
            for s in (-1, 1):
                for k in range(n):
                    zc = RWY_Z + s * (5 + k * 3)
                    P.append(strip('tdz', end + sgn * dist, zc, end + sgn * (dist + 22), zc, 1.8, y, W))
        for s in (-1, 1):
            P.append(strip('aim', end + sgn * 120, RWY_Z + s * 9.5, end + sgn * 165, RWY_Z + s * 9.5, 6, y, W))
        # blast pad chevrons
        for k in range(3):
            xa = end - sgn * (8 + k * 11)
            for s in (-1, 1):
                P.append(strip('chev', xa, RWY_Z, xa - sgn * 9, RWY_Z + s * 14, 1.2, y, Y_))
    # taxiway centreline + edges (yellow), lead-ins and hold-short lines
    P.append(strip('tcl', TWY_X0, TWY_Z, TWY_X1, TWY_Z, .3, y, Y_))
    for s in (-1, 1):
        P.append(strip('tedge', TWY_X0 - TWY_W / 2 + .6, TWY_Z + s * (TWY_W / 2 - .5), TWY_X1 + TWY_W / 2 - .6, TWY_Z + s * (TWY_W / 2 - .5), .25, y, Y_))
    for lx in LINKS:
        P.append(strip('lcl', lx, TWY_Z, lx, RWY_Z - hw + 2, .3, y, Y_))
        zh = RWY_Z - hw - 12
        for k in range(4):
            zz = zh - k * .7
            if k < 2:
                P.append(strip('hold', lx - TWY_W / 2 + 1, zz, lx + TWY_W / 2 - 1, zz, .3, y, Y_))
            else:
                xx = lx - TWY_W / 2 + 1
                while xx < lx + TWY_W / 2 - 1:
                    P.append(strip('holdd', xx, zz, xx + .9, zz, .3, y, Y_)); xx += 1.8
        P.append(text('holdtxt', 'A' if lx < -100 else 'B' if lx < 100 else 'C', 3.2, (lx, y + .002, zh - 6), Y_, yaw=0, flat=True))
    # apron: lead-in lines from the taxiway to each pad, stand numbers, safety lines along the terminal
    for k, (px, pz) in enumerate(PADS):
        P.append(strip('lead', px, TWY_Z - TWY_W / 2 + 1, px, pz + 15.5, .3, y, Y_))
        P.append(disc('padring', px, pz, 13.6, 14.4, y + .03, W, 64))
        P.append(disc('padinner', px, pz, 8.6, 9.2, y + .03, Y_, 64))
        P.append(text('padnum', str(k + 1), 7, (px, y + .032, pz + 11.4), W, yaw=0, flat=True))
        for s in (-1, 1):
            P.append(strip('padbar', px + s * 4.2, pz - 4.2, px + s * 4.2, pz + 4.2, 1.1, y + .032, W))
        P.append(strip('padbarh', px - 4.2, pz, px + 4.2, pz, 1.1, y + .032, W))
    P.append(strip('safety', TERM[0] - 20, TERM[3] + 6, TERM[2] + 20, TERM[3] + 6, .25, y, R))
    P.append(strip('safety2', TERM[0] - 20, TERM[3] + 6.6, TERM[2] + 20, TERM[3] + 6.6, .25, y, R))
    x = APRON[0] + 5
    while x < APRON[2] - 5:
        P.append(strip('apz', x, APRON[3] - 1.5, x + 3, APRON[3] - 1.5, .25, y, Y_)); x += 6
    # walkway from pad 1 to the terminal door (zebra)
    for k in range(9):
        zc = -16 - k * 2.6
        P.append(strip('zebra', -3, zc, 3, zc, 1.2, y, W))
    # landside: road dashes, crossings, parking bays
    x = -126
    while x < 126:
        P.append(strip('rd', x, FORECOURT_Z, x + 3, FORECOURT_Z, .2, y, W)); x += 8
    for k in range(6):
        xc = -4.5 + k * 1.8
        P.append(strip('zebra2', xc, FORECOURT_Z - ROAD_W / 2 + .5, xc, FORECOURT_Z + ROAD_W / 2 - .5, .9, y, W))
    z = -136
    while z < FORECOURT_Z - 8:
        P.append(strip('sd', 0, z, 0, z + 3, .2, y, W)); z += 8
    for x0, z0, x1, z1 in LOTS:
        for row_z, dirz in ((z0 + 5.5, 1), (z1 - 5.5, -1)):
            xx = x0 + 3
            while xx <= x1 - 3:
                P.append(strip('bay', xx, row_z - 2.75, xx, row_z + 2.75, .12, y, W)); xx += 2.7
        P.append(strip('aisle', x0 + 3, (z0 + z1) / 2, x1 - 3, (z0 + z1) / 2, .15, y, W))
    # tyre rubber on the touchdown zones (decals, 140 m each end)
    for end, sgn in ((RWY_X0, 1), (RWY_X1, -1)):
        xa, xb = end + sgn * 70, end + sgn * 260
        o = quad('tyre', min(xa, xb), RWY_Z - 9, max(xa, xb), RWY_Z + 9, y + .004, m['tyre'], uv=[(0, 0), (3, 0), (3, 1), (0, 1)])
        P.append(o)
    # kerb edges along the landside walk
    P.append(B('kerbstone', (260, .16, .3), (0, .08, FORECOURT_Z + ROAD_W / 2 + .15), m['kerb']))
    P.append(B('kerbstone2', (260, .16, .3), (0, .08, FORECOURT_Z - ROAD_W / 2 - .15), m['kerb']))
    return P


# ---------------------------------------------------------------- terminal
def terminal(m):
    P = []
    x0, z0, x1, z1 = TERM
    zc = (z0 + z1) / 2
    P.append(B('tfloor', (x1 - x0 + 4, .2, z1 - z0 + 4), (0, .1, zc), m['floor']))
    col(x0 - 2, 0, z0 - 2, x1 + 2, .2, z1 + 2, 'terminal_floor')
    # wave roof slab with deep overhangs on both sides
    xs = [x0 - 8 + i * (x1 - x0 + 16) / 40 for i in range(41)]
    zs = [z0 - 13 + j * (z1 - z0 + 21) / 16 for j in range(17)]

    def roof_y(x, z):
        t = (z - (z0 - 13)) / (z1 - z0 + 21)
        return TERM_H + 1.6 + 2.6 * math.sin(math.pi * t)
    top = grid_surface('roof', xs, zs, roof_y, m['roof'], 10)
    solidify(top, .9)
    P.append(top)
    under = grid_surface('soffit', xs, zs, lambda x, z: roof_y(x, z) - .92, m['soffit'], 3)
    bpy.context.view_layer.objects.active = under; under.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT'); bpy.ops.mesh.flip_normals(); bpy.ops.object.mode_set(mode='OBJECT')
    under.select_set(False)
    P.append(under)
    # clerestory bands close the gap between the curtain wall and the roof soffit
    for zf in (z0, z1):
        top = roof_y(0, zf) - .9
        P.append(B('clerestory', (x1 - x0, top - TERM_H + .2, .35), (0, (top + TERM_H) / 2, zf), m['clad_dark']))
    # fascia glow along the landside roof edge
    P.append(B('fascia', (x1 - x0 + 16, .35, .25), (0, roof_y(0, z0 - 13) - .5, z0 - 13.05), m['lc']))
    # glass curtain walls with mullions and transoms; three door openings per side
    mull = B('mull', (.14, TERM_H, .3), (0, TERM_H / 2, 0), m['mullion'])
    for zf in (z0, z1):
        segs = []
        edges = [x0] + [v for d in DOORS for v in (d - 3, d + 3)] + [x1]
        for a, b in zip(edges[::2], edges[1::2]):
            segs.append((a, b))
        for a, b in segs:
            P.append(B('pane', (b - a, TERM_H - .2, .05), ((a + b) / 2, TERM_H / 2 + .1, zf), m['glass']))
            col(a, 0, zf - .25, b, TERM_H, zf + .25, 'glass')
            n = max(1, round((b - a) / 2.5))
            for k in range(n + 1):
                P.append(dup(mull, (a + (b - a) * k / n, 0, zf)))
            for h in (3.4, 7.0, 10.4, TERM_H - .1):
                P.append(B('transom', (b - a, .16, .28), ((a + b) / 2, h, zf), m['mullion']))
        for d in DOORS:
            P.append(B('doorhead', (6.4, .9, .5), (d, 3.4, zf), m['mullion']))
            P.append(B('doorglass', (6, TERM_H - 3.9, .05), (d, (TERM_H + 3.9) / 2, zf), m['glass']))
            for s in (-1, 1):
                P.append(B('doorleaf', (1.4, 2.9, .06), (d + s * 3.6, 1.65, zf + .1), m['glass']))
            P.append(B('doormat', (6, .02, 3), (d, .21, zf), m['tyres']))
    bpy.data.objects.remove(mull)
    # end walls (cladding) and a service core
    for xe in (x0, x1):
        P.append(B('endwall', (.6, TERM_H + 1, z1 - z0), (xe, (TERM_H + 1) / 2, zc), m['clad']))
        col(xe - .3, 0, z0, xe + .3, TERM_H + 1, z1, 'wall')
    # tree columns holding the roof
    for xcol in range(-70, 71, 20):
        P.append(C('col', .42, TERM_H + 1, (xcol, .2, zc), m['mullion'], 16))
        col(xcol - .45, 0, zc - .45, xcol + .45, TERM_H + 2, zc + .45, 'column')
        for s in (-1, 1):
            o = bl.cyl('strut', .16, 7, L(xcol, TERM_H - 1.4, zc + s * 2.6), m['mullion'], 8, rot=(s * .75, 0, 0)); bl.apply_all(o); P.append(o)
    # ceiling light strips
    for zl in (z0 + 6, zc, z1 - 6):
        P.append(B('lightstrip', (x1 - x0 - 6, .08, .7), (0, roof_y(0, zl) - 1.0, zl), m['panel']))
    # check-in islands (landside half)
    for xi in (-55, -25, 25, 55):
        P.append(B('desk', (16, 1.1, 2.4), (xi, .75, z0 + 9), m['wood'], bevel=.05))
        P.append(B('desktop', (16.2, .06, 2.6), (xi, 1.33, z0 + 9), m['mullion']))
        P.append(B('belt', (16, .45, 1.2), (xi, .42, z0 + 11), m['tyres']))
        P.append(B('deskback', (16, 2.6, .3), (xi, 1.5, z0 + 12.2), m['clad_dark']))
        P.append(B('deskscreen', (14, 1.1, .08), (xi, 2.4, z0 + 12.0), m['screen']))
        col(xi - 8, 0, z0 + 7.8, xi + 8, 2.8, z0 + 12.4, 'desk')
    # departure boards hanging over the central concourse
    for xb in (-14, 14):
        P.append(B('board', (9, 2.4, .25), (xb, 7.6, zc), m['screen']))
        P.append(B('boardframe', (9.4, 2.8, .2), (xb, 7.6, zc + .14), m['clad_dark']))
        for s in (-1, 1):
            P.append(C('hanger', .03, 5, (xb + s * 4, 8.8, zc), m['steel'], 4))
    # gate seating (airside half): rows of linked seats
    seat = bl.join([B('seat_base', (8, .45, .55), (0, .45, 0), m['seat']), B('seat_back', (8, .6, .1), (0, .9, .27), m['seat']),
                    B('seat_leg', (.1, .45, .4), (-3.6, .22, 0), m['steel']), B('seat_leg2', (.1, .45, .4), (3.6, .22, 0), m['steel'])], 'seatrow')
    for xr in (-60, -45, -30, 30, 45, 60):
        for zr, yaw in ((z1 - 9, 0.0), (z1 - 6.5, math.pi)):
            P.append(dup(seat, (xr, .2, zr), yaw))
            col(xr - 4, 0, zr - .5, xr + 4, 1.1, zr + .5, 'seats')
    bpy.data.objects.remove(seat)
    # planters
    for xp in (-70, -10, 10, 70):
        P.append(B('planter', (3, .8, 3), (xp, .6, zc + 4), m['concrete']))
        P.append(bl.sphere('shrub', 1.4, L(xp, 1.9, zc + 4), m['plant'], 10, 8, scale=(1, 1, .8)))
        bl.apply_all(P[-1])
        col(xp - 1.5, 0, zc + 2.5, xp + 1.5, 1, zc + 5.5, 'planter')
    # Quartermaster kiosk just inside the airside door: counter + back shelf
    P.append(B('qmcounter', (5, 1.05, 1.2), (14, .72, z1 - 7.5), m['clad_dark'], bevel=.05))
    P.append(B('qmtop', (5.2, .06, 1.4), (14, 1.27, z1 - 7.5), m['lc']))
    P.append(B('qmshelf', (6, 2.6, .6), (14, 1.5, z1 - 10.2), m['clad_dark']))
    P.append(B('qmsign', (4, .7, .1), (14, 3.4, z1 - 10.5), m['lc']))
    col(11.5, 0, z1 - 8.1, 16.5, 1.3, z1 - 6.9, 'counter')
    # roof sign over the landside entrance
    P.append(text('signtxt', 'NEW MERIDIAN SPACEPORT', 2.6, (0, TERM_H + 4.6, z0 - 13.3), m['sign'], yaw=math.pi, extrude=.08))
    P.append(B('signback', (40, 3.6, .3), (0, TERM_H + 4.6, z0 - 13.0), m['clad_dark']))
    # kerbside canopy columns
    for xk in range(-60, 61, 30):
        P.append(C('kcol', .3, roof_y(xk, z0 - 11) - .9, (xk, .16, z0 - 11), m['mullion'], 12))
        col(xk - .35, 0, z0 - 11.35, xk + .35, 8, z0 - 10.65, 'column')
    return P


# ---------------------------------------------------------------- control tower
def tower(m):
    tx, tz = TOWER
    P = [B('tbase', (16, 6, 16), (tx, 3, tz), m['clad']),
         B('tbaseglass', (16.1, 2, 16.1), (tx, 3.5, tz), m['glass']),
         B('tbaseroof', (16.6, .5, 16.6), (tx, 6.25, tz), m['concrete'])]
    col(tx - 8, 0, tz - 8, tx + 8, 6.5, tz + 8, 'tower')
    P.append(C('shaft', 3.2, 31, (tx, 6, tz), m['kerb'], 24, r2=2.6))
    for k in range(4):
        P.append(C('fin', .5, 30, (tx + math.cos(k * R90 + .4) * 2.9, 6.3, tz + math.sin(k * R90 + .4) * 2.9), m['clad'], 8))
    P.append(C('cabfloor', 6.2, 1.0, (tx, 36, tz), m['clad_dark'], 8, r2=6.6, smooth=False))
    P.append(C('cab', 6.6, 4.6, (tx, 37, tz), m['glass'], 8, r2=7.4, smooth=False))
    for k in range(8):
        a = k / 8 * math.tau + math.pi / 8
        o = bl.cyl('cabpost', .12, 4.7, L(tx + math.cos(a) * 7.0, 39.3, tz + math.sin(a) * 7.0), m['mullion'], 6,
                   rot=(0, 0, 0)); bl.apply_all(o); P.append(o)
    P.append(C('cabroof', 7.9, .7, (tx, 41.6, tz), m['clad_dark'], 8, r2=7.2, smooth=False))
    P.append(C('cabcap', 3, 1.5, (tx, 42.3, tz), m['clad'], 12))
    P.append(C('mast', .15, 9, (tx + 2, 43.8, tz), m['steel'], 6))
    P.append(bl.sphere('beacon', .35, L(tx + 2, 52.9, tz), m['lr'], 8, 6)); bl.apply_all(P[-1])
    P.append(B('consoles', (9, 1, 1.2), (tx, 37.5, tz - 4.8), m['screen']))
    col(tx - 3.3, 0, tz - 3.3, tx + 3.3, 44, tz + 3.3, 'tower')
    return P


def radar(m, tx, tz):
    r = bl.empty('AP_radar', L(tx, 43.8, tz))
    P = [bl.cyl('rped', .5, 1.0, (0, 0, .5), m['clad_dark'], 10),
         bl.box('rarm', (.3, .3, 1.4), (0, 0, 1.5), m['steel']),
         bl.box('rdish', (5, .3, 1.2), (0, -.35, 2.3), m['clad'], rot=(.25, 0, 0), bevel=.05),
         bl.box('rfeed', (.4, .9, .3), (0, -1.0, 1.8), m['dark'])]
    for o in P:
        bl.apply_all(o)
    g = bl.join(P, 'AP_radar_mesh'); g.parent = r
    return r


# ---------------------------------------------------------------- hangars
def hangars(m):
    P = []
    hw = HANGAR_W / 2
    rise = 7.0
    for hx in HANGARS:
        xs = [hx - hw - .5 + i * (HANGAR_W + 1) / 28 for i in range(29)]
        zs = [HANGAR_Z0 - .6, (HANGAR_Z0 + HANGAR_Z1) / 2, HANGAR_Z1 + 1.2]
        ay = lambda x, z, hx=hx: HANGAR_H + rise * math.sqrt(max(0, 1 - ((x - hx) / (hw + .5)) ** 2))
        roof = grid_surface('hroof', xs, zs, ay, m['roof'], 8); solidify(roof, .5); P.append(roof)
        for s in (-1, 1):
            P.append(B('hside', (.5, HANGAR_H, HANGAR_Z1 - HANGAR_Z0), (hx + s * hw, HANGAR_H / 2, (HANGAR_Z0 + HANGAR_Z1) / 2), m['clad']))
            col(hx + s * hw - .3, 0, HANGAR_Z0, hx + s * hw + .3, HANGAR_H + 2, HANGAR_Z1, 'hangar')
            # door pockets (doors slid open to each side)
            P.append(B('hdoor', (12, HANGAR_H + 1.5, .5), (hx + s * (hw - 6.5), (HANGAR_H + 1.5) / 2, HANGAR_Z1 + .4), m['clad_dark']))
            col(hx + s * hw - 13, 0, HANGAR_Z1, hx + s * hw, HANGAR_H + 1.5, HANGAR_Z1 + .8, 'hangar')
            P.append(B('hstripe', (12, .8, .52), (hx + s * (hw - 6.5), 1.0, HANGAR_Z1 + .41), m['yellow']))
        # gable walls follow the arch
        for zf, solid in ((HANGAR_Z0, True), (HANGAR_Z1, False)):
            verts, faces = [], []
            n = 28
            for i in range(n + 1):
                x = hx - hw + i * HANGAR_W / n
                verts.append(L(x, HANGAR_H + rise * math.sqrt(max(0, 1 - ((x - hx) / (hw + .5)) ** 2)), zf))
                verts.append(L(x, 0 if solid else HANGAR_H + 1.5, zf))
            for i in range(n):
                a = i * 2
                faces.append((a, a + 2, a + 3, a + 1) if zf == HANGAR_Z0 else (a, a + 1, a + 3, a + 2))
            o = bl.mesh_from('gable', verts, faces, m['clad']); bl.uv_box(o, 8); solidify(o, .4); P.append(o)
        col(hx - hw, 0, HANGAR_Z0 - .4, hx + hw, HANGAR_H + rise, HANGAR_Z0 + .2, 'hangar')
        col(hx - hw, HANGAR_H + 1.5, HANGAR_Z1 - .2, hx + hw, HANGAR_H + rise, HANGAR_Z1 + .4, 'hangar')
        # roof lights inside, skylight band, number board
        for k in range(3):
            P.append(B('hlight', (40, .12, .6), (hx, HANGAR_H + rise - 1.2, HANGAR_Z0 + 8 + k * 14), m['panel']))
        P.append(text('hnum', 'H%d' % (HANGARS.index(hx) + 1), 3.5, (hx, HANGAR_H + 3.8, HANGAR_Z1 + 1.0), m['white'], extrude=.05))
        # tool racks and crates inside along the back wall
        for k in range(4):
            P.append(B('rack', (6, 3.2, 1.2), (hx - 18 + k * 12, 1.6, HANGAR_Z0 + 1.4), m['clad_dark']))
            col(hx - 21 + k * 12, 0, HANGAR_Z0 + .6, hx - 15 + k * 12, 3.2, HANGAR_Z0 + 2.2, 'rack')
    return P


# ---------------------------------------------------------------- fuel farm
def fuel_farm(m):
    x0, z0, x1, z1 = FUEL
    P = []
    for k in range(3):
        tx, tz = x0 + 10 + k * 15, (z0 + z1) / 2
        P.append(C('ftank', 6, 11, (tx, .1, tz), m['tank'], 32))
        P.append(C('ftop', 6.1, 1.2, (tx, 11.1, tz), m['tank'], 32, r2=2))
        P.append(C('fband', 6.05, .4, (tx, 1.0, tz), m['redpaint'], 32))
        o = bl.box('fladder', (.6, .1, 11), L(tx + 6.05, 5.6, tz), m['steel'], rot=(0, 0, 0)); bl.apply_all(o); P.append(o)
        col(tx - 6, 0, tz - 6, tx + 6, 12.3, tz + 6, 'tank')
    for (a, b, c, d) in ((x0, z0, x1, z0), (x0, z1, x1, z1), (x0, z0, x0, z1), (x1, z0, x1, z1)):
        if a == c:
            P.append(B('bund', (.5, 1.2, d - b), (a, .6, (b + d) / 2), m['concrete']))
            col(a - .25, 0, b, a + .25, 1.2, d, 'bund')
        else:
            P.append(B('bund', (c - a, 1.2, .5), ((a + c) / 2, .6, b), m['concrete']))
            col(a, 0, b - .25, c, 1.2, b + .25, 'bund')
    P.append(CX('fpipe', .3, x1 - x0 + 8, (x0 + (x1 - x0) / 2, 1.6, z1 + 2), m['yellow'], 10, 'x'))
    P.append(B('pumphouse', (6, 3.2, 4), (x1 - 3, 1.6, z1 + 6), m['clad']))
    col(x1 - 6, 0, z1 + 4, x1, 3.2, z1 + 8, 'pump')
    return P


# ---------------------------------------------------------------- ground vehicles (static)
def wheels(P, m, xs, zs, r=.55, w=.4, y=0.0):
    for x in xs:
        for z in zs:
            P.append(CX('wheel', r, w, (x, y + r, z), m['tyres'], 12, 'x'))


def fuel_truck(m, pos, yaw):
    """Tanker along its local +z: cab at the front, tank behind."""
    P = [B('chassis', (2.4, .5, 10), (0, .9, 0), m['dark']),
         B('cab', (2.5, 2.2, 2.4), (0, 2.1, 3.8), m['truck_y'], bevel=.12),
         B('wind', (2.3, .8, .05), (0, 2.6, 5.01), m['glass']),
         CX('tankbody', 1.25, 6.6, (0, 2.45, -1.2), m['tank'], 20, 'z'),
         B('tankband', (2.6, .3, .12), (0, 1.3, -1.2), m['redpaint']),
         B('hose', (2.6, .9, .9), (0, 1.3, -4.6), m['dark']),
         bl.sphere('beacon', .18, L(0, 3.3, 3.6), m['la'], 8, 6),
         B('lamps', (2.0, .15, .06), (0, 1.3, 5.02), m['lw'])]
    bl.apply_all(P[6])
    wheels(P, m, (-1.15, 1.15), (3.4, -2.2, -3.6))
    return place(P, pos, yaw, 'fueltruck', (1.3, 3.6, 5.1))


def tug(m, pos, yaw):
    P = [B('tugbody', (2.2, 1.0, 3.6), (0, .8, 0), m['truck_y'], bevel=.1),
         B('tugcab', (1.6, 1.2, 1.2), (0, 1.9, -.8), m['dark']),
         B('tugseat', (.6, .5, .6), (0, 1.55, .4), m['seat']),
         bl.sphere('beacon', .14, L(0, 2.6, -.8), m['la'], 8, 6)]
    bl.apply_all(P[3])
    wheels(P, m, (-1.0, 1.0), (1.2, -1.2), .45, .35)
    return place(P, pos, yaw, 'tug', (1.2, 2.6, 1.9))


def cart(m, pos, yaw):
    P = [B('cartbed', (2.0, .2, 3.0), (0, .7, 0), m['dark']),
         B('cartbox', (1.9, 1.6, 2.8), (0, 1.6, 0), m['clad'], bevel=.05),
         B('cartbar', (.15, .15, 1.0), (0, .6, 1.9), m['steel'])]
    wheels(P, m, (-.9, .9), (1.0, -1.0), .3, .2)
    return place(P, pos, yaw, 'cart', (1.0, 2.4, 1.6))


def stairs_truck(m, pos, yaw):
    P = [B('stchassis', (2.4, .6, 7), (0, .9, 0), m['dark']),
         B('stcab', (2.4, 2.0, 2.0), (0, 2.0, 2.6), m['truck'], bevel=.1),
         B('stbase', (2.0, .5, 3.5), (0, 1.5, -1.5), m['truck_y'])]
    for k in range(14):
        P.append(B('step', (1.6, .12, .4), (0, 1.9 + k * .32, .2 - k * .38), m['steel']))
    for s in (-1, 1):
        o = bl.box('strail', (.08, 6.4, .08), L(s * .85, 4.7, -2.4), m['steel'], rot=(-.7, 0, 0)); bl.apply_all(o); P.append(o)
    P.append(B('stplat', (2, .15, 1.6), (0, 6.3, -5.6), m['steel']))
    wheels(P, m, (-1.15, 1.15), (2.4, -2.4))
    return place(P, pos, yaw, 'stairs', (1.3, 6.5, 4.2))


def power_unit(m, pos, yaw):
    P = [B('gpu', (1.6, 1.4, 2.4), (0, 1.1, 0), m['truck'], bevel=.08),
         B('gpustripe', (1.62, .25, 2.42), (0, .7, 0), m['yellow']),
         B('gpucable', (.2, .2, 1.2), (0, .6, 1.6), m['dark'])]
    wheels(P, m, (-.75, .75), (.8, -.8), .3, .2)
    return place(P, pos, yaw, 'gpu', (.9, 1.8, 1.3))


def place(P, pos, yaw, tag, half):
    """Join a vehicle built at the origin, move it to pos (three space), add its footprint collider."""
    o = bl.join(P, tag)
    o.location = L(*pos); o.rotation_euler = (0, 0, yaw)
    bl.apply_all(o)
    hx, hy, hz = half
    c, s = abs(math.cos(yaw)), abs(math.sin(yaw))
    ex, ez = hx * c + hz * s, hx * s + hz * c
    col(pos[0] - ex, 0, pos[2] - ez, pos[0] + ex, hy, pos[2] + ez, 'vehicle')
    return o


def vehicles(m):
    P = [fuel_truck(m, (26, 0, -24), 0.0), fuel_truck(m, (152, 0, -28), R90 * .5), fuel_truck(m, (186, 0, -42), R90),
         stairs_truck(m, (-102, 0, -22), 0.0), power_unit(m, (-22, 0, -24), 0.4), power_unit(m, (104, 0, -26), -.3)]
    P.append(tug(m, (-52, 0, -30), R90))
    for k in range(3):
        P.append(cart(m, (-58 - k * 3.6, 0, -30), R90))
    for k in range(4):
        P.append(cart(m, (-280 + k * 4, 0, 18), 0.0))
    P.append(tug(m, (-270, 0, 26), math.pi))
    return P


# ---------------------------------------------------------------- lights
def lights(m):
    P = []
    # fixture prototypes
    base = bl.cyl('lbase', .12, .35, (0, 0, .175), m['dark'], 8); bl.apply_all(base)

    def fixture(lm, name):
        cap = bl.sphere(name + 'cap', .16, (0, 0, .38), lm, 8, 5, scale=(1, 1, .7)); bl.apply_all(cap)
        b2 = base.copy(); b2.data = base.data.copy(); bpy.context.scene.collection.objects.link(b2)
        return bl.join([b2, cap], name)
    proto = {k: fixture(m[k], 'fx_' + k) for k in ('lw', 'lb', 'lg', 'lr', 'la', 'lc')}
    bpy.data.objects.remove(base)
    hw = RWY_W / 2
    x = RWY_X0
    while x <= RWY_X1 + .1:
        for s in (-1, 1):
            P.append(dup(proto['la' if RWY_X1 - x < 120 or x - RWY_X0 < 0 else 'lw'], (x, .06, RWY_Z + s * (hw + 1.5))))
        x += 30
    for end, sgn in ((RWY_X0, 1), (RWY_X1, -1)):
        for k in range(13):
            z = RWY_Z - hw + 2 + k * (RWY_W - 4) / 12
            P.append(dup(proto['lg'], (end - sgn * .8, .06, z)))
            P.append(dup(proto['lr'], (end - sgn * 2.2, .06, z)))
        # approach light bars on poles beyond the threshold
        for k in range(3):
            xa = end - sgn * (15 + k * 15)
            h = .4 + k * .5
            P.append(B('apbar', (.15, .15, 14), (xa, h, RWY_Z), m['steel']))
            P.append(C('appole', .12, h, (xa, 0, RWY_Z), m['steel'], 6))
            for j in range(5):
                P.append(dup(proto['lw'], (xa, h - .2, RWY_Z - 6 + j * 3)))
        # PAPI: four boxes left of the touchdown zone
        for j in range(4):
            px, pz = end + sgn * 130, RWY_Z - sgn * (hw + 8 + j * 3)
            P.append(B('papi', (1.2, .7, 1.0), (px, .5, pz), m['dark']))
            P.append(B('papilens', (.05, .32, .7), (px - sgn * .62, .56, pz), m['lr'] if j < 2 else m['lw']))
    # taxiway edge lights (blue)
    x = TWY_X0
    while x <= TWY_X1 + .1:
        for s in (-1, 1):
            if all(abs(x - lx) > TWY_W / 2 + 1 for lx in LINKS) or s < 0:
                P.append(dup(proto['lb'], (x, .06, TWY_Z + s * (TWY_W / 2 + 1))))
        x += 25
    for lx in LINKS:
        for zz in (TWY_Z + 20, RWY_Z - hw - 6):
            for s in (-1, 1):
                P.append(dup(proto['lb'], (lx + s * (TWY_W / 2 + 1), .06, zz)))
    # pad ring lights (cyan) and apron edge
    for px, pz in PADS:
        for k in range(16):
            a = k / 16 * math.tau
            P.append(dup(proto['lc'], (px + math.cos(a) * 15.6, .08, pz + math.sin(a) * 15.6)))
    for k in proto.values():
        bpy.data.objects.remove(k)
    return P


# ---------------------------------------------------------------- fence, signs, windsocks
def fence(m):
    P = []
    x0, z0, x1, z1 = FENCE
    H = 2.6
    lines = [((x0, z0), (TERM[0] - 2, z0)), ((TERM[0] - 2, z0), (TERM[0] - 2, TERM[1])),
             ((TERM[2] + 2, TERM[1]), (TERM[2] + 2, z0)), ((TERM[2] + 2, z0), (x1, z0)),
             ((x1, z0), (x1, z1)), ((x1, z1), (x0, z1)), ((x0, z1), (x0, z0))]
    post = bl.cyl('fpost', .06, H + .5, (0, 0, (H + .5) / 2), m['steel'], 6); bl.apply_all(post)
    arm = bl.box('farm', (.05, .05, .6), (0, .15, H + .62), m['steel'], rot=(-.6, 0, 0)); bl.apply_all(arm)
    pp = bl.join([post, arm], 'fpost_proto')
    for (ax, az), (bx, bz) in lines:
        ln = math.hypot(bx - ax, bz - az)
        verts = [L(ax, .05, az), L(bx, .05, bz), L(bx, H, bz), L(ax, H, az)]
        o = bl.mesh_from('mesh', verts, [(0, 1, 2, 3)], m['fence'])
        lay = o.data.uv_layers.new(name='UVMap')
        for li, loop in enumerate(o.data.polygons[0].loop_indices):
            lay.data[loop].uv = [(0, 0), (ln / 1.2, 0), (ln / 1.2, H / 1.2), (0, H / 1.2)][li]
        P.append(o)
        for h in (.1, H):
            P.append(strip('frail', ax, az, bx, bz, .06, h, m['steel']))
        yaw = math.atan2(-(bz - az), bx - ax)
        n = max(1, int(ln / 3.2))
        for k in range(n + 1):
            t = k / n
            P.append(dup(pp, (ax + (bx - ax) * t, 0, az + (bz - az) * t), yaw - R90))
        # colliders in ~25 m pieces
        n2 = max(1, int(ln / 25))
        for k in range(n2):
            t0, t1 = k / n2, (k + 1) / n2
            pa = (ax + (bx - ax) * t0, az + (bz - az) * t0); pb = (ax + (bx - ax) * t1, az + (bz - az) * t1)
            col(min(pa[0], pb[0]) - .12, 0, min(pa[1], pb[1]) - .12, max(pa[0], pb[0]) + .12, H + .4, max(pa[1], pb[1]) + .12, 'fence')
    bpy.data.objects.remove(pp)
    # gate at the fuel farm service road (closed boom)
    return P


def signs(m):
    """Taxiway location / direction boards (black on yellow, yellow on black)."""
    P = []
    for k, lx in enumerate(LINKS):
        sx, sz = lx + TWY_W / 2 + 4, RWY_Z - RWY_W / 2 - 16
        P.append(B('signbox', (3.6, 1.1, .5), (sx, .9, sz), m['black']))
        P.append(B('signpanel', (1.6, .9, .52), (sx - .9, .9, sz), m['yellow']))
        P.append(text('signl', 'ABC'[k], .7, (sx + .9, .9, sz + .27), m['yellow'], extrude=.01))
        P.append(text('signr', '09-27', .48, (sx - .9, .9, sz + .27), m['black'], extrude=.01))
        P.append(text('signl2', 'ABC'[k], .7, (sx + .9, .9, sz - .27), m['yellow'], yaw=math.pi, extrude=.01))
        col(sx - 1.8, 0, sz - .3, sx + 1.8, 1.5, sz + .3, 'sign')
    return P


def windsock(m, name, pos):
    r = bl.empty(name, L(*pos))
    P = [bl.cyl('wmast', .09, 6.5, (0, 0, 3.25), m['steel'], 8), bl.cyl('wbase', .6, .3, (0, 0, .15), m['concrete'], 12),
         bl.torus('wring', .48, .04, (0, -.2, 6.4), m['steel'], rot=(R90, 0, 0), maj=16, mn=4)]
    for o in P:
        bl.apply_all(o)
    mast = bl.join(P, name + '_mast'); mast.parent = r
    sock = bl.empty('windsock_sock', (0, 0, 6.4), parent=r)
    bands = []
    for k in range(5):
        r0 = .46 - k * .06; r1 = r0 - .06
        o = bl.cyl('band', r0, .72, (0, -(.2 + k * .72 + .36), 0), m['orange' if k % 2 == 0 else 'sockw'], 14, rot=(R90, 0, 0), r2=r1, smooth=True)
        bl.apply_all(o); bands.append(o)
    s = bl.join(bands, 'windsock_sock_mesh'); s.parent = sock
    col(pos[0] - .6, 0, pos[2] - .6, pos[0] + .6, 6.5, pos[2] + .6, 'windsock')
    return r


def main():
    if not FAST or not os.path.exists(os.path.join(bl.TEXTURES, 'ap_slab_c.jpg')):
        bake_textures()
    bl.reset()
    m = mats()
    root = bl.empty('AP_site')
    groups = {'AP_ground': ground(m) + markings(m), 'AP_build': terminal(m) + tower(m) + hangars(m) + fuel_farm(m),
              'AP_lights': lights(m), 'AP_props': vehicles(m) + fence(m) + signs(m)}
    for name, parts in groups.items():
        g = bl.join(parts, name); g.parent = root
    radar(m, *TOWER).parent = root
    socks = [(RWY_X0 + 70, 0, RWY_Z + 45), (RWY_X1 - 70, 0, RWY_Z - 45)]
    for k, p in enumerate(socks):
        windsock(m, 'AP_windsock_%d' % k, p).parent = root
    meta = {
        'colliders': COLLIDERS,
        'pads': [[x, .1, z] for x, z in PADS],
        'spawn': [0, .07, -12.5], 'spawnYaw': math.pi,
        'ship': [0, .1, 0], 'vendor': [14, .2, TERM[3] - 9.0], 'vendorYaw': 0.0, 'vendorTerminal': [16.4, 1.27, TERM[3] - 7.5],
        'terminal': list(TERM), 'runway': [RWY_X0, RWY_Z, RWY_X1, RWY_W], 'taxiway': [TWY_X0, TWY_Z, TWY_X1, TWY_W],
        'apron': list(APRON), 'lots': [list(l) for l in LOTS], 'hangars': [[x, (HANGAR_Z0 + HANGAR_Z1) / 2] for x in HANGARS],
        'fence': list(FENCE), 'tower': list(TOWER), 'radar': [TOWER[0], 43.8, TOWER[1]],
        'paths': [[[-120, -95], [120, -95], [120, -86], [-120, -86]], [[-66, -74], [66, -74], [66, -54], [-66, -54]]],
    }
    root['worldex'] = json.dumps(meta)
    bl.export('airport.glb')
    print('[airport] colliders', len(COLLIDERS))


main()
