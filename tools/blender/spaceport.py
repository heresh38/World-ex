"""New Meridian Spaceport: the starship landing zone where the Wayfarer's jumpship sets down, south of the city across
the ring road. Ships land vertically: no runways. VTOL pads with glowing rings, heavy hexagonal pads with blast deflectors,
umbilical gantries running fuel and power lines to the pads, landing-guidance pylons and beacon masts, a traffic-control
tower with sensor dishes, a glass-fronted terminal, ship-sized hangars, a container yard with a straddle crane, a fuel farm.

spaceport.glb, root 'SP_site' (origin = centre of landing pad 1, placed by earth.js at SPACEPORT.x/z):
  SP_ground   landing field, pads, landside road and parking, painted markings and scorch marks
  SP_build    terminal (walkable hall with a glass curtain wall), control tower, hangars, fuel farm, blast deflectors
  SP_lights   pad ring and hex-edge lights, guidance pylon heads, beacons (emissive)
  SP_props    gantries + fuel / power lines, containers, crane, ground vehicles, fence
  SP_radar    the tower's sensor head (spun in-engine)
Separate roots (static ship props, placed and animated by earth.js): SP_ship_hauler (heavy freighter, ~40 m),
SP_ship_courier (fast courier, ~24 m), SP_ship_lander (shuttle, ~14 m, also flies the ambient arrivals). Their engine
nozzles use the emissive material 'sp_engine'.
The root carries extras.worldex (JSON): AABB colliders, pads, spawn, vendor spot and anchors, in three space (x east,
y up, z south) relative to the root.

Textures are baked first (Cycles + numpy) into assets/textures/sp_*.{jpg,png} and embedded in the GLB: field concrete
slabs, worn paint, scorch marks, metal cladding, glass smudges, terrazzo, chain-link.
Usage: blender --background --python tools/blender/spaceport.py [-- --fast]   (--fast reuses the Cycles-baked textures)
"""
import bpy, bmesh, math, os, sys, json
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import bl
from textures import G, bake, setup as tex_setup

R90 = math.pi / 2
FAST = '--fast' in sys.argv

# ---------------------------------------------------------------- layout (three space, metres, relative to pad 1)
FIELD = (-345.0, -40.0, 215.0, 150.0)       # the landing field slab
PADS = ((0.0, 0.0), (-120.0, 0.0), (120.0, 0.0))                       # row A: VTOL pads (r 15) by the terminal
PAD_R = 15.0
HEAVY = ((-290.0, 98.0), (-180.0, 98.0), (-70.0, 98.0), (40.0, 98.0), (150.0, 98.0))   # row B: heavy hex pads
HEAVY_R = 24.0
HANGARS = (-315.0, -255.0, -195.0)
HANGAR_Z0, HANGAR_Z1, HANGAR_W, HANGAR_H = -34.0, 10.0, 54.0, 16.0
TERM = (-80.0, -80.0, 80.0, -42.0)          # x0, z0 (landside facade), x1, z1 (airside facade)
TERM_H = 13.0
DOORS = (-40.0, 0.0, 40.0)
TOWER = (130.0, -66.0)
FUEL = (160.0, -84.0, 210.0, -50.0)
YARD = (232.0, -40.0, 300.0, 136.0)         # container yard
FENCE = (-420.0, -90.0, 315.0, 150.0)
FORECOURT_Z, ROAD_W = -104.0, 12.0
LOTS = ((-235.0, -132.0, -128.0, -96.0), (128.0, -132.0, 235.0, -96.0))

COLLIDERS = []


def col(x0, y0, z0, x1, y1, z1, tag='spaceport'):
    COLLIDERS.append([round(min(x0, x1), 3), round(min(y0, y1), 3), round(min(z0, z1), 3),
                      round(max(x0, x1), 3), round(max(y0, y1), 3), round(max(z0, z1), 3), tag])


def apply(o):
    """Bake the object transform into its mesh without an operator (operators slow down as the scene grows)."""
    if o.type == 'MESH':
        o.data.transform(o.matrix_basis)
    from mathutils import Matrix
    o.matrix_basis = Matrix.Identity(4)


def L(x, y, z):
    """three (x, y, z) -> Blender location."""
    return (x, -z, y)


def B(name, size, pos, m, yaw=0.0, bevel=0.0, segs=2):
    """Box: size (sx, sy, sz) and centre pos in three space, yaw about the vertical."""
    sx, sy, sz = size
    o = bl.box(name, (sx, sz, sy), L(*pos), m, bevel=bevel, rot=(0, 0, yaw), segs=segs)
    apply(o)
    return o


def C(name, r, h, base, m, verts=16, r2=None, smooth=True):
    """Vertical cylinder standing on base (three space)."""
    x, y, z = base
    o = bl.cyl(name, r, h, L(x, y + h / 2, z), m, verts, r2=r2, smooth=smooth)
    apply(o)
    return o


def CX(name, r, length, centre, m, verts=12, axis='x'):
    """Horizontal cylinder along three x or z."""
    rot = (0, R90, 0) if axis == 'x' else (R90, 0, 0)
    o = bl.cyl(name, r, length, L(*centre), m, verts, rot=rot)
    apply(o)
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
    apply(o)
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
    if not FAST or not os.path.exists(os.path.join(bl.TEXTURES, 'sp_slab_c.jpg')):
        p = tex_setup()
        bpy.context.scene.cycles.samples = 8
        # landing-field concrete: 2 x 2 cast slabs per tile with sawn joints, per-slab tone, aggregate, rubber and oil
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
        bake(p, 'sp_slab', slab_c, slab_h, strength=.55, size=1024)

        # worn paint for markings (white; tinted yellow / red in the material)
        def paint_c(g):
            chip = g.ramp(g.noise(14, 6, .7, 11), [(.28, '#77736d'), (.34, '#ffffff')])
            grime = g.ramp(g.noise(4, 5, .6, 12), [(.3, '#ffffff'), (.8, '#c9c6bf')])
            spk = g.ramp(g.noise(120, 2, .5, 13), [(.6, '#ffffff'), (.75, '#a8a49c')])
            return g.mix(g.mix(chip, grime, 1.0, 'MULTIPLY'), spk, 1.0, 'MULTIPLY')
        bake(p, 'sp_paint', paint_c, None, size=512)

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
        bake(p, 'sp_clad', clad_c, clad_h, strength=.9, size=1024)

        # glass smudges / water marks (near white; multiplies the glass tint)
        def glass_c(g):
            s = g.ramp(tex_noise(g, 6, 1, 6, .65, 31), [(.3, '#ffffff'), (.75, '#c8d2d8')])
            d = g.ramp(g.noise(20, 4, .6, 32), [(.55, '#ffffff'), (.7, '#dfe4e6')])
            return g.mix(s, d, 1.0, 'MULTIPLY')
        bake(p, 'sp_glass', glass_c, None, size=512)

        # terrazzo floor for the terminal hall
        def terr_c(g):
            base = g.ramp(g.noise(8, 4, .5, 41), [(.3, '#d9d4cc'), (.7, '#cbc5bb')])
            v = g.voronoi(70, 42, 'F1', 'Distance')
            chips = g.ramp(g.voronoi(70, 42, 'F1', 'Color'), [(0.0, '#5d6670'), (.5, '#a89a86'), (1.0, '#3d3a38')])
            c = g.mix(base, chips, g.math('LESS_THAN', v, .18))
            tile = g.brick(.25, .25, offset=0.0, mortar=.003)
            return g.mix(c, (.55, .54, .52), tile.outputs['Fac'])
        bake(p, 'sp_terrazzo', terr_c, None, size=1024)
    rs = np.random.RandomState(7)
    # scorch: soot burned into a pad by engine exhaust, radial streaks and a heat-tinted halo (RGBA)
    S = 512
    yy, xx = (np.mgrid[0:S, 0:S] + .5) / S * 2 - 1
    r = np.sqrt(xx * xx + yy * yy); a = np.arctan2(yy, xx)
    streak = np.zeros_like(r)
    for k in range(1, 40):
        streak += np.cos(a * k + rs.rand() * math.tau) * rs.rand() / k ** .6
    streak = (streak - streak.min()) / (np.ptp(streak) + 1e-6)
    blotch = np.zeros_like(r)
    for k in range(60):
        cx, cy, s = rs.randn() * .3, rs.randn() * .3, .08 + rs.rand() * .25
        blotch += np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (s * s)) * rs.rand()
    blotch = blotch / blotch.max()
    core = np.clip(1 - r / (.55 + .25 * streak), 0, 1) ** .7
    alpha = np.clip(core * (.55 + .45 * blotch) + np.clip(1 - r, 0, 1) ** 3 * .25 * streak, 0, .9) * np.clip((1 - r) * 4, 0, 1)
    rgba = np.zeros((S, S, 4), np.float32)
    halo = np.clip((r - .35) * 3, 0, 1) * np.clip((.9 - r) * 4, 0, 1)
    rgba[..., 0] = .05 + .05 * halo; rgba[..., 1] = .045 + .03 * halo; rgba[..., 2] = .04 + .07 * halo; rgba[..., 3] = alpha
    save_rgba('sp_scorch', rgba)
    # chain-link diamond mesh
    S = 256
    yy, xx = np.mgrid[0:S, 0:S] / S * 4.0
    d1 = np.abs(((xx + yy) % 1.0) - .5); d2 = np.abs(((xx - yy) % 1.0) - .5)
    wire = np.clip(1 - np.minimum(.5 - d1, .5 - d2) / .035, 0, 1)
    rgba = np.zeros((S, S, 4), np.float32); rgba[..., :3] = .62; rgba[..., 3] = wire
    save_rgba('sp_chainlink', rgba)


# ---------------------------------------------------------------- materials
def mats():
    p = bl.palette()
    T = lambda n: n if os.path.exists(os.path.join(bl.TEXTURES, n)) else None
    p.update(
        field=bl.mat('sp_field', '#dcd8d0', 0, .8, image='sp_slab_c.jpg', normal='sp_slab_n.jpg'),
        pad=bl.mat('sp_pad', '#b9bcc0', .1, .62, image='sp_slab_c.jpg', normal='sp_slab_n.jpg'),
        heavy=bl.mat('sp_pad_heavy', '#8f949a', .2, .55, image='sp_slab_c.jpg', normal='sp_slab_n.jpg'),
        asphalt=bl.mat('sp_asphalt', '#8e8e94', 0, .85, image='asphalt_c.jpg', normal='asphalt_n.jpg'),
        kerb=bl.mat('sp_kerb', '#d4cfc6', 0, .85, image='concrete_c.jpg', normal='concrete_n.jpg'),
        white=bl.mat('sp_paint_white', '#f4f2ec', 0, .6, image='sp_paint_c.jpg'),
        yellow=bl.mat('sp_paint_yellow', '#f2b51c', 0, .6, image='sp_paint_c.jpg'),
        redpaint=bl.mat('sp_paint_red', '#b8231d', 0, .6, image='sp_paint_c.jpg'),
        black=bl.mat('sp_paint_black', '#1a1a1c', 0, .7, image='sp_paint_c.jpg'),
        scorch=bl.mat('sp_scorch', '#ffffff', 0, .95, image=T('sp_scorch.png'), alpha=.99),
        clad=bl.mat('sp_cladding', '#d9dde2', .65, .38, image='sp_clad_c.jpg', normal='sp_clad_n.jpg'),
        clad_dark=bl.mat('sp_cladding_dark', '#5b6470', .65, .4, image='sp_clad_c.jpg', normal='sp_clad_n.jpg'),
        deflector=bl.mat('sp_deflector', '#6a6560', .7, .5, image='sp_clad_c.jpg', normal='sp_clad_n.jpg'),
        roof=bl.mat('sp_roof', '#e8e6e0', .3, .45, image='sp_clad_c.jpg', normal='sp_clad_n.jpg'),
        soffit=bl.mat('sp_soffit', '#c8a27a', .1, .55, image='sp_clad_c.jpg'),
        glass=bl.mat('sp_glass', '#9cc4d4', .2, .04, image='sp_glass_c.jpg', alpha=.32),
        mullion=bl.mat('sp_mullion', '#a9b0b8', .9, .28),
        floor=bl.mat('sp_floor', '#ffffff', 0, .22, image='sp_terrazzo_c.jpg'),
        concrete=bl.mat('sp_concrete', '#c4bfb6', 0, .85, image='concrete_c.jpg', normal='concrete_n.jpg'),
        fence=bl.mat('sp_fence', '#ffffff', .6, .5, image=T('sp_chainlink.png'), alpha=.99),
        lw=bl.mat('sp_light_white', '#fff4dc', 0, .3, emit='#fff1d6', strength=9),
        lg=bl.mat('sp_light_green', '#2aff6a', 0, .3, emit='#2aff70', strength=9),
        lr=bl.mat('sp_light_red', '#ff2a1a', 0, .3, emit='#ff2a1a', strength=9),
        la=bl.mat('sp_light_amber', '#ffae2f', 0, .3, emit='#ffae2f', strength=9),
        lc=bl.mat('sp_light_cyan', '#40e0ff', 0, .3, emit='#40e0ff', strength=9),
        panel=bl.mat('sp_ceiling_light', '#fff6e8', 0, .3, emit='#fff1dc', strength=3),
        screen=bl.mat('sp_screen', '#081820', 0, .25, emit='#2ad0ff', strength=2.2),
        sign=bl.mat('sp_sign_glow', '#e8f8ff', 0, .3, emit='#d8f4ff', strength=5),
        truck=bl.mat('sp_truck_white', '#e8e6e0', .2, .4),
        truck_y=bl.mat('sp_truck_yellow', '#e0a81c', .3, .42),
        tank=bl.mat('sp_tank', '#d8dadc', .7, .3),
        tyres=bl.mat('sp_tyres', '#161617', 0, .9),
        seat=bl.mat('sp_seat', '#2a3442', .2, .5),
        wood=bl.mat('sp_counter', '#7a5a3e', 0, .45),
        plant=bl.mat('sp_plant', '#3f6e34', 0, .85),
        cable=bl.mat('sp_cable', '#1b1c1e', .2, .6),
        # ship props
        hull=bl.mat('sp_hull', '#d9dbe0', .35, .38, image='panel_c.jpg', normal='panel_n.jpg'),
        hull_dark=bl.mat('sp_hull_dark', '#3b4048', .6, .4, image='panel_c.jpg', normal='panel_n.jpg'),
        hull_orange=bl.mat('sp_hull_orange', '#d2691e', .3, .42, image='panel_c.jpg', normal='panel_n.jpg'),
        hull_yellow=bl.mat('sp_hull_yellow', '#d9a21b', .35, .4, image='panel_c.jpg', normal='panel_n.jpg'),
        canopy=bl.mat('sp_canopy', '#142230', .7, .08),
        nozzle=bl.mat('sp_nozzle', '#2a2b2e', .9, .45),
        engine=bl.mat('sp_engine', '#7fd8ff', 0, .3, emit='#7fd8ff', strength=7),
    )
    for k, c in (('c_red', '#9a3324'), ('c_blue', '#2c5a8a'), ('c_white', '#d8d8d2'), ('c_green', '#3d6b4a'), ('c_orange', '#d2742a'), ('c_grey', '#6c7076')):
        p[k] = bl.mat('sp_container_' + k[2:], c, .45, .55, image='sp_clad_c.jpg', normal='sp_clad_n.jpg')
    # alpha-cut maps: wire the image alpha into the shader so the glTF gets the cut-out
    for k in ('scorch', 'fence'):
        nt = p[k].node_tree; tn = [n for n in nt.nodes if n.type == 'TEX_IMAGE']
        if tn:
            nt.links.new(tn[0].outputs['Alpha'], nt.nodes['Principled BSDF'].inputs['Alpha'])
    return p


def hexagon(name, cx, cz, r, y, m, tile=8.0):
    verts = [L(cx, y, cz)] + [L(cx + math.cos(k / 6 * math.tau) * r, y, cz + math.sin(k / 6 * math.tau) * r) for k in range(6)]
    faces = [(0, k + 1, (k + 1) % 6 + 1) for k in range(6)]
    o = bl.mesh_from(name, verts, faces, m)
    lay = o.data.uv_layers.new(name='UVMap')
    for pl in o.data.polygons:
        for loop in pl.loop_indices:
            v = o.data.vertices[o.data.loops[loop].vertex_index].co
            lay.data[loop].uv = (v.x / tile, v.y / tile)
    return face_up(o)


# ---------------------------------------------------------------- ground: landing field, pads, landside
def ground(m):
    P = []
    y0 = .06
    fx0, fz0, fx1, fz1 = FIELD
    P.append(quad('field', fx0, fz0, fx1, fz1, y0 + .01, m['field'], 15))
    for px, pz in PADS:
        P.append(disc('pad', px, pz, 0, PAD_R, y0 + .03, m['pad'], 64, 8))
    for hx, hz in HEAVY:
        P.append(hexagon('hpad', hx, hz, HEAVY_R, y0 + .03, m['heavy'], 9))
    # container yard slab and the lane out to the field
    P.append(quad('yard', YARD[0] - 4, YARD[1] - 4, YARD[2] + 4, YARD[3] + 4, y0, m['concrete'], 8))
    P.append(quad('yardlane', FIELD[2], 40, YARD[0] - 4, 60, y0, m['asphalt'], 10))
    # landside: forecourt road, spur to the ring road, kerb walk, parking lots
    P.append(quad('forecourt', -128, FORECOURT_Z - ROAD_W / 2, 128, FORECOURT_Z + ROAD_W / 2, y0, m['asphalt'], 10))
    P.append(quad('spur', -ROAD_W / 2, -137, ROAD_W / 2, FORECOURT_Z - ROAD_W / 2, y0, m['asphalt'], 10))
    P.append(quad('kerbwalk', -130, FORECOURT_Z + ROAD_W / 2, 130, TERM[1], y0 + .1, m['kerb'], 6))
    for x0, z0, x1, z1 in LOTS:
        P.append(quad('lot', x0, z0, x1, z1, y0, m['asphalt'], 10))
    P.append(quad('toweryard', TOWER[0] - 14, TOWER[1] - 14, TOWER[0] + 14, TOWER[1] + 14, y0 + .01, m['field'], 12))
    P.append(quad('fuelyard', FUEL[0] - 4, FUEL[1] - 4, FUEL[2] + 4, FUEL[3] + 4, y0 + .01, m['concrete'], 8))
    P.append(quad('service', FUEL[0] - 4, FUEL[3] + 4, FUEL[0] + 8, FIELD[1], y0, m['asphalt'], 10))
    return P


def markings(m):
    W, Y_, R = m['white'], m['yellow'], m['redpaint']
    P = []
    y = .085
    # row A pads: white boundary ring, yellow touchdown ring, cross, number; scorch where the exhaust hits
    for k, (px, pz) in enumerate(PADS):
        P.append(disc('padring', px, pz, PAD_R - 1.4, PAD_R - .6, y + .03, W, 64))
        P.append(disc('padinner', px, pz, 8.6, 9.2, y + .03, Y_, 64))
        P.append(text('padnum', str(k + 1), 7, (px, y + .032, pz + 11.4), W, yaw=0, flat=True))
        for s in (-1, 1):
            P.append(strip('padbar', px + s * 4.2, pz - 4.2, px + s * 4.2, pz + 4.2, 1.1, y + .032, W))
        P.append(strip('padbarh', px - 4.2, pz, px + 4.2, pz, 1.1, y + .032, W))
        P.append(quad('scorch', px - 11, pz - 11, px + 11, pz + 11, y + .036, m['scorch'], uv=[(0, 0), (1, 0), (1, 1), (0, 1)]))
    # heavy pads: hex boundary, hazard band, yellow ring, big numbers, heavy scorch
    for k, (hx, hz) in enumerate(HEAVY):
        for j in range(6):
            a0, a1 = j / 6 * math.tau, (j + 1) / 6 * math.tau
            for rr, w, mm in ((HEAVY_R - 1.2, 1.2, W), (HEAVY_R - 3.4, .6, Y_)):
                P.append(strip('hexedge', hx + math.cos(a0) * rr, hz + math.sin(a0) * rr, hx + math.cos(a1) * rr, hz + math.sin(a1) * rr, w, y + .032, mm))
        P.append(disc('hring', hx, hz, 13.2, 14.2, y + .033, Y_, 72))
        P.append(text('hnum', str(k + 4), 9, (hx, y + .042, hz + 17.2), W, yaw=0, flat=True))
        P.append(quad('scorch', hx - 18, hz - 18, hx + 18, hz + 18, y + .038, m['scorch'], uv=[(0, 0), (1, 0), (1, 1), (0, 1)]))
    # field service lanes (yellow, dashed) and the hold line in front of the terminal
    for zl in (44.0, 56.0):
        x = FIELD[0] + 4
        while x < FIELD[2] - 4:
            P.append(strip('lane', x, zl, x + 6, zl, .3, y, Y_)); x += 10
    P.append(strip('safety', TERM[0] - 20, TERM[3] + 6, TERM[2] + 20, TERM[3] + 6, .25, y, R))
    P.append(strip('safety2', TERM[0] - 20, TERM[3] + 6.6, TERM[2] + 20, TERM[3] + 6.6, .25, y, R))
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
        for row_z in (z0 + 5.5, z1 - 5.5):
            xx = x0 + 3
            while xx <= x1 - 3:
                P.append(strip('bay', xx, row_z - 2.75, xx, row_z + 2.75, .12, y, W)); xx += 2.7
        P.append(strip('aisle', x0 + 3, (z0 + z1) / 2, x1 - 3, (z0 + z1) / 2, .15, y, W))
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
            o = bl.cyl('strut', .16, 7, L(xcol, TERM_H - 1.4, zc + s * 2.6), m['mullion'], 8, rot=(s * .75, 0, 0)); apply(o); P.append(o)
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
        apply(P[-1])
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


# ---------------------------------------------------------------- traffic-control tower with sensor dishes and antennas
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
        o = bl.cyl('cabpost', .12, 4.7, L(tx + math.cos(a) * 7.0, 39.3, tz + math.sin(a) * 7.0), m['mullion'], 6); apply(o); P.append(o)
    P.append(C('cabroof', 7.9, .7, (tx, 41.6, tz), m['clad_dark'], 8, r2=7.2, smooth=False))
    P.append(C('cabcap', 3, 1.5, (tx, 42.3, tz), m['clad'], 12))
    P.append(B('consoles', (9, 1, 1.2), (tx, 37.5, tz - 4.8), m['screen']))
    # antenna array on the cab roof
    for k in range(6):
        a = k / 6 * math.tau
        x, z = tx + math.cos(a) * 5.6, tz + math.sin(a) * 5.6
        h = 5 + (k % 3) * 2.5
        P.append(C('ant', .08, h, (x, 42.3, z), m['steel'], 6))
        P.append(B('antx', (1.4, .06, .06), (x, 42.3 + h * .7, z), m['steel'], yaw=a))
        P.append(bl.sphere('anttip', .16, L(x, 42.3 + h, z), m['lr'] if k % 2 else m['lw'], 8, 6)); apply(P[-1])
    # sensor dishes on the base roof
    for s, yaw in ((-1, .6), (1, -2.2)):
        bx, bz = tx + s * 5, tz + 5
        P.append(C('dishped', .45, 2.4, (bx, 6.5, bz), m['clad_dark'], 10))
        o = bl.cyl('dishbowl', 2.3, .5, L(bx, 9.4, bz), m['clad'], 24, r2=.6, rot=(.9, 0, yaw)); apply(o); P.append(o)
        o = bl.cyl('feed', .06, 2.2, L(bx, 10.3, bz), m['steel'], 6, rot=(.9, 0, yaw)); apply(o); P.append(o)
    col(tx - 3.3, 0, tz - 3.3, tx + 3.3, 44, tz + 3.3, 'tower')
    return P


def radar(m, tx, tz):
    r = bl.empty('SP_radar', L(tx, 43.8, tz))
    P = [bl.cyl('rped', .5, 1.0, (0, 0, .5), m['clad_dark'], 10),
         bl.box('rarm', (.3, .3, 1.4), (0, 0, 1.5), m['steel']),
         bl.box('rdish', (5, .3, 1.2), (0, -.35, 2.3), m['clad'], rot=(.25, 0, 0), bevel=.05),
         bl.box('rfeed', (.4, .9, .3), (0, -1.0, 1.8), m['dark'])]
    for o in P:
        apply(o)
    g = bl.join(P, 'SP_radar_mesh'); g.parent = r
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
        o = bl.box('fladder', (.6, .1, 11), L(tx + 6.05, 5.6, tz), m['steel'], rot=(0, 0, 0)); apply(o); P.append(o)
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


# ---------------------------------------------------------------- pad furniture: deflectors, gantries, pylons, beacons
def blast_deflector(m, hx, hz):
    """Curved, buttressed blast wall on the terminal side of a heavy pad."""
    P = []
    R, n, H = HEAVY_R + 7, 14, 6.5
    a0, a1 = -math.pi / 2 - 1.0, -math.pi / 2 + 1.0
    for k in range(n):
        a = a0 + (a1 - a0) * (k + .5) / n
        seg = 2 * R * math.sin((a1 - a0) / n / 2) + .1
        x, z = hx + math.cos(a) * R, hz + math.sin(a) * R
        yaw = -(a + R90)
        P.append(B('defl', (seg, H, .8), (x, H / 2, z), m['deflector'], yaw=yaw))
        P.append(B('deflcap', (seg, .4, 1.4), (x, H + .2, z), m['clad_dark'], yaw=yaw))
        if k % 3 == 1:
            bx, bz = hx + math.cos(a) * (R + 1.6), hz + math.sin(a) * (R + 1.6)
            P.append(B('buttress', (.8, H * .8, 3), (bx, H * .4, bz), m['concrete'], yaw=yaw))
        col(x - seg / 2 - .4, 0, z - seg / 2 - .4, x + seg / 2 + .4, H, z + seg / 2 + .4, 'deflector')
    return P


def catenary(name, a, b, sag, r, m, n=12):
    """Cable from a to b (three space) hanging by `sag` metres."""
    P = []
    pts = []
    for k in range(n + 1):
        t = k / n
        pts.append([a[i] + (b[i] - a[i]) * t for i in range(3)])
        pts[-1][1] -= sag * 4 * t * (1 - t)
    for k in range(n):
        p0, p1 = pts[k], pts[k + 1]
        dx, dy, dz = p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]
        ln = math.sqrt(dx * dx + dy * dy + dz * dz)
        bx, by, bz = dx, -dz, dy       # Blender direction
        o = bl.cyl(name, r, ln * 1.02, L((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2, (p0[2] + p1[2]) / 2), m, 6)
        o.rotation_mode = 'QUATERNION'
        from mathutils import Vector
        o.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(Vector((bx, by, bz)).normalized())
        apply(o); P.append(o)
    return P


def gantry(m, hx, hz):
    """Umbilical tower east of a heavy pad: lattice tower, swing arm, fuel line and power cable to the pad."""
    P = []
    gx, gz, H = hx + HEAVY_R + 9, hz - 6, 22.0
    for sx in (-1.5, 1.5):
        for sz in (-1.5, 1.5):
            P.append(B('gpost', (.35, H, .35), (gx + sx, H / 2, gz + sz), m['truck_y']))
    for y in range(3, int(H), 4):
        for (xa, za, xb, zb) in ((-1.5, -1.5, 1.5, -1.5), (-1.5, 1.5, 1.5, 1.5), (-1.5, -1.5, -1.5, 1.5), (1.5, -1.5, 1.5, 1.5)):
            P.append(strip_beam(m, gx + xa, y, gz + za, gx + xb, y + 3.4, gz + zb))
        P.append(B('gdeck', (3.6, .15, 3.6), (gx, y, gz), m['steel']))
    P.append(B('gcab', (3.6, 2.6, 3.6), (gx, H + 1.3, gz), m['clad_dark']))
    P.append(B('garm', (HEAVY_R - 2, .9, 1.1), (gx - (HEAVY_R - 2) / 2 - 1.6, H - 2.5, gz), m['truck_y']))
    P.append(bl.sphere('gbeacon', .3, L(gx, H + 2.9, gz), m['la'], 8, 6)); apply(P[-1])
    tip = (gx - HEAVY_R + .4, H - 3.0, gz)
    P += catenary('power', tip, (hx + 8, .7, hz - 3), 3.5, .14, m['cable'])
    P += catenary('power2', (tip[0] + 2, tip[1], gz + .4), (hx + 9, .7, hz + 1), 4.2, .1, m['cable'])
    # fuel line along the ground to a coupling at the pad rim
    P.append(CX('fuelline', .32, gx - (hx + HEAVY_R - 2), ((gx + hx + HEAVY_R - 2) / 2, .45, gz + 2), m['yellow'], 10, 'x'))
    P.append(B('coupling', (1.4, 1.1, 1.4), (hx + HEAVY_R - 2, .55, gz + 2), m['clad_dark']))
    P.append(B('gbase', (5, .6, 5), (gx, .3, gz), m['concrete']))
    col(gx - 2.5, 0, gz - 2.5, gx + 2.5, H + 2.6, gz + 2.5, 'gantry')
    col(hx + HEAVY_R - 2.7, 0, gz + 1.3, hx + HEAVY_R - 1.3, 1.1, gz + 2.7, 'coupling')
    return P


def strip_beam(m, xa, ya, za, xb, yb, zb, r=.08):
    dx, dy, dz = xb - xa, yb - ya, zb - za
    ln = math.sqrt(dx * dx + dy * dy + dz * dz)
    from mathutils import Vector
    o = bl.cyl('brace', r, ln, L((xa + xb) / 2, (ya + yb) / 2, (za + zb) / 2), m['steel'], 4)
    o.rotation_mode = 'QUATERNION'; o.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(Vector((dx, -dz, dy)).normalized())
    apply(o)
    return o


def umbilical_post(m, px, pz, a):
    """Small service post at a VTOL pad: power pillar and a hose lying out to the pad edge."""
    P = []
    x, z = px + math.cos(a) * (PAD_R + 3.5), pz + math.sin(a) * (PAD_R + 3.5)
    P.append(B('upost', (1.2, 2.6, 1.2), (x, 1.3, z), m['clad_dark']))
    P.append(B('upanel', (1.25, .5, 1.25), (x, 2.2, z), m['lc']))
    P += catenary('hose', (x, 1.6, z), (px + math.cos(a) * (PAD_R - 2), .25, pz + math.sin(a) * (PAD_R - 2)), .6, .12, m['cable'], 8)
    col(x - .6, 0, z - .6, x + .6, 2.6, z + .6, 'post')
    return P


def pylon(m, x, z, h, lm):
    """Landing-guidance pylon: slim tapered mast, glowing head, strobe band."""
    P = [C('pyl', .32, h, (x, 0, z), m['clad'], 8, r2=.18),
         C('pylbase', .6, .5, (x, 0, z), m['concrete'], 10),
         C('pylhead', .34, .7, (x, h, z), lm, 10),
         C('pylband', .3, .25, (x, h * .55, z), m['la'], 10)]
    col(x - .4, 0, z - .4, x + .4, h + .7, z + .4, 'pylon')
    return P


def beacon_mast(m, x, z, h=26.0):
    P = [C('bmast', .55, h, (x, 0, z), m['clad'], 10, r2=.3), C('bmbase', 1.4, .8, (x, 0, z), m['concrete'], 12)]
    for f in (.5, 1.0):
        P.append(bl.sphere('bmlight', .45, L(x, h * f + .3, z), m['lr'], 10, 6)); apply(P[-1])
    P.append(C('bmstrobe', .4, .5, (x, h + .7, z), m['lw'], 10))
    for k in range(3):
        a = k / 3 * math.tau
        P.append(strip_beam(m, x, h * .45, z, x + math.cos(a) * 5, 0, z + math.sin(a) * 5, .05))
    col(x - .6, 0, z - .6, x + .6, h, z + .6, 'mast')
    return P


def pad_furniture(m):
    P = []
    for k, (px, pz) in enumerate(PADS):
        for j in range(4):
            a = j / 4 * math.tau + math.pi / 4
            P += pylon(m, px + math.cos(a) * (PAD_R + 3), pz + math.sin(a) * (PAD_R + 3), 4.2, m['lc'])
        P += umbilical_post(m, px, pz, math.pi * (.15 if k != 1 else .85))
    for hx, hz in HEAVY:
        P += blast_deflector(m, hx, hz)
        P += gantry(m, hx, hz)
        for j in range(6):
            a = j / 6 * math.tau
            if math.sin(a) < -.6:
                continue                            # the deflector side
            P += pylon(m, hx + math.cos(a) * (HEAVY_R + 3.5), hz + math.sin(a) * (HEAVY_R + 3.5), 7.0, m['la'] if j % 2 else m['lc'])
    for x, z in ((-405, -78), (-405, 138), (FENCE[2] - 10, 138), (FENCE[2] - 10, -78), (-120, 138)):
        P += beacon_mast(m, x, z)
    return P


# ---------------------------------------------------------------- container yard + straddle crane
def containers(m):
    P = []
    rg = bl.rng(17)
    cols = ['c_red', 'c_blue', 'c_white', 'c_green', 'c_orange', 'c_grey']
    x0, z0, x1, z1 = YARD
    proto = {}
    for c in cols:
        o = B('cont', (2.44, 2.59, 12.2), (0, 1.3, 0), m[c]); bl.uv_box(o, 3)
        rib = B('contend', (2.5, 2.65, .2), (0, 1.3, 6.0), m['steel'])
        rib2 = B('contend2', (2.5, 2.65, .2), (0, 1.3, -6.0), m['steel'])
        proto[c] = bl.join([o, rib, rib2], 'cont_' + c)
    bz = z0 + 2
    while bz + 12.2 < z1:
        for bxi in range(2):
            bx = x0 + 3 + bxi * 34
            hmax = 0
            for k in range(8):
                x = bx + k * 2.8
                h = 1 + int(rg.random() * 3)
                if rg.random() < .12:
                    continue
                for lvl in range(h):
                    P.append(dup(proto[cols[int(rg.random() * len(cols))]], (x, lvl * 2.61, bz + 6.1), 0.0))
                hmax = max(hmax, h)
            col(bx - 1.3, 0, bz, bx + 7 * 2.8 + 1.3, hmax * 2.61, bz + 12.2, 'containers')
        bz += 15.5
    for o in proto.values():
        bpy.data.objects.remove(o)
    # straddle crane over the middle lane
    cx, cz, w, d, h = x0 + 31, z0 + 60, 12.0, 14.0, 17.0
    for sx in (-1, 1):
        for sz in (-1, 1):
            P.append(B('cleg', (.9, h, .9), (cx + sx * w / 2, h / 2, cz + sz * d / 2), m['truck_y']))
            P.append(B('cwheel', (1.4, 1.2, 2.4), (cx + sx * w / 2, .6, cz + sz * d / 2), m['dark']))
            col(cx + sx * w / 2 - .7, 0, cz + sz * d / 2 - 1.2, cx + sx * w / 2 + .7, h, cz + sz * d / 2 + 1.2, 'crane')
        P.append(B('cbeam', (1.2, 1.4, d + 1), (cx + sx * w / 2, h + .7, cz), m['truck_y']))
    for sz in (-1, 1):
        P.append(B('cbeamx', (w + 1, 1.4, 1.2), (cx, h + .7, cz + sz * d / 2), m['truck_y']))
    P.append(B('ccab', (2.4, 2.2, 2.4), (cx + w / 2 - 1.6, h - 1.6, cz + d / 2 - 1.6), m['clad_dark']))
    P.append(B('spreader', (2.8, .6, 12.4), (cx, h - 6, cz), m['truck_y']))
    for sz in (-5, 5):
        P.append(C('ccable', .05, 5.4, (cx, h - 5.7, cz + sz), m['cable'], 4))
    P.append(dup_cont(m, cx, h - 8.95, cz))
    return P


def dup_cont(m, x, y, z):
    o = B('ccont', (2.44, 2.59, 12.2), (x, y + 1.3, z), m['c_orange']); bl.uv_box(o, 3)
    return o


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
    apply(P[6])
    wheels(P, m, (-1.15, 1.15), (3.4, -2.2, -3.6))
    return place(P, pos, yaw, 'fueltruck', (1.3, 3.6, 5.1))


def tug(m, pos, yaw):
    P = [B('tugbody', (2.2, 1.0, 3.6), (0, .8, 0), m['truck_y'], bevel=.1),
         B('tugcab', (1.6, 1.2, 1.2), (0, 1.9, -.8), m['dark']),
         B('tugseat', (.6, .5, .6), (0, 1.55, .4), m['seat']),
         bl.sphere('beacon', .14, L(0, 2.6, -.8), m['la'], 8, 6)]
    apply(P[3])
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
        o = bl.box('strail', (.08, 6.4, .08), L(s * .85, 4.7, -2.4), m['steel'], rot=(-.7, 0, 0)); apply(o); P.append(o)
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
    apply(o)
    hx, hy, hz = half
    c, s = abs(math.cos(yaw)), abs(math.sin(yaw))
    ex, ez = hx * c + hz * s, hx * s + hz * c
    col(pos[0] - ex, 0, pos[2] - ez, pos[0] + ex, hy, pos[2] + ez, 'vehicle')
    return o


def vehicles(m):
    P = [fuel_truck(m, (26, 0, -24), 0.0), fuel_truck(m, (152, 0, -28), R90 * .5), fuel_truck(m, (186, 0, -42), R90),
         fuel_truck(m, (-150, 0, 70), .3), stairs_truck(m, (-102, 0, -22), 0.0), power_unit(m, (-22, 0, -24), 0.4),
         power_unit(m, (104, 0, -26), -.3), power_unit(m, (60, 0, 64), 1.2)]
    P.append(tug(m, (-52, 0, -30), R90))
    for k in range(3):
        P.append(cart(m, (-58 - k * 3.6, 0, -30), R90))
    for k in range(4):
        P.append(cart(m, (218 + k * 3.4, 0, 50), R90))
    P.append(tug(m, (212, 0, 50), R90))
    return P


# ---------------------------------------------------------------- ship props (static; nose toward +z)
def ship_root(name, parts, offset):
    r = bl.empty(name, (offset, 3000, 0))
    g = bl.join(parts, name + '_mesh'); g.parent = r
    return r


def legs(m, P, pts, top, foot=.9):
    for x, z in pts:
        P.append(strip_beam(m, x * .82, top, z * .92, x, .6, z, .28))
        P.append(strip_beam(m, x * .82, top - .6, z * .92 - .8, x, .9, z, .12))
        P.append(C('foot', foot, .35, (x, 0, z), m['dark'], 12))


def nozzle(m, P, x, y, z, r, ln=2.2):
    o = bl.cyl('noz', r, ln, L(x, y, z), m['nozzle'], 16, rot=(R90, 0, 0), r2=r * .75); apply(o); P.append(o)
    o = bl.cyl('glow', r * .78, .12, L(x, y, z - ln / 2 + .1), m['engine'], 16, rot=(R90, 0, 0)); apply(o); P.append(o)


def ship_hauler(m):
    """Heavy freighter: armoured spine, cockpit block forward, cargo pods slung either side, twin fuel tanks
    on the back, four main engines and four landing legs (refs: industrial haulers with cylindrical tanks)."""
    P = [B('spine', (6, 4.6, 30), (0, 6.6, -1), m['hull'], bevel=.3),
         B('keel', (4.2, 1.6, 26), (0, 3.9, 0), m['hull_dark']),
         B('nose', (7.4, 5.2, 7.4), (0, 6.9, 17.2), m['hull'], bevel=.7),
         B('nosechin', (5.6, 2.2, 3.4), (0, 4.9, 19.4), m['hull_dark'], bevel=.4),
         B('band', (7.6, .5, 1.0), (0, 9.3, 14.6), m['hull_orange'])]
    o = bl.box('canopy', (5.4, 1.3, 2.6), L(0, 8.6, 20.4), m['canopy'], rot=(.75, 0, 0)); apply(o); P.append(o)
    for s in (-1, 1):
        for k, zc in enumerate((-9.5, -.5, 8.5)):
            P.append(B('pod', (4, 4.2, 7.6), (s * 5.4, 6.0, zc), m['hull_orange' if k == 1 else 'hull_dark'], bevel=.2))
            P.append(B('podstrap', (4.2, .3, .6), (s * 5.4, 8.2, zc + 2.6), m['steel']))
            P.append(B('podstrap2', (4.2, .3, .6), (s * 5.4, 8.2, zc - 2.6), m['steel']))
        P.append(CX('tank', 1.7, 16, (s * 2.3, 10.1, -1.5), m['hull_yellow'], 20, 'z'))
        for e in (-1, 1):
            o = bl.sphere('tankcap', 1.7, L(s * 2.3, 10.1, -1.5 + e * 8), m['hull_yellow'], 16, 8, scale=(1, 1, .55)); apply(o); P.append(o)
        P.append(B('radiator', (.18, 3.0, 6), (s * 3.6, 11.4, -11), m['dark']))
        P.append(bl.sphere('nav', .22, L(s * 3.8, 9.3, 19.5), m['lr'] if s < 0 else m['lg'], 8, 6)); apply(P[-1])
    P.append(B('engblock', (12, 6.2, 6), (0, 6.6, -18.6), m['hull_dark'], bevel=.4))
    for x in (-3.2, 3.2):
        for y in (5.0, 8.3):
            nozzle(m, P, x, y, -22.6, 1.25)
    P.append(C('mast', .1, 4, (1.6, 8.9, 3), m['steel'], 6))
    P.append(B('dish', (1.6, .2, 1.6), (-1.6, 9.2, 5), m['clad'], bevel=.1))
    legs(m, P, [(-5.4, 12), (5.4, 12), (-6, -13), (6, -13)], 4.0, 1.1)
    return ship_root('SP_ship_hauler', P, 0)


def ship_courier(m):
    """Fast courier: lofted hexagonal hull tapering to a wedge nose, swept wings carrying twin nacelles, canted fins."""
    P = []
    secs = [(-11, 3.1, 2.3), (-7, 3.6, 2.6), (-1, 3.5, 2.5), (5, 2.7, 2.0), (9.5, 1.5, 1.3), (12.5, .35, .45)]
    rings = []
    for z, w, h in secs:
        yc = 3.7 + (h - 2.3) * .1
        ring = [(w, 0), (w * .72, h), (-w * .72, h), (-w, 0), (-w * .62, -h * .72), (w * .62, -h * .72)]
        rings.append([L(x, yc + y, z) for x, y in ring])
    o = bl.loft('hull', rings, m['hull'], smooth=False); bl.uv_box(o, 3); P.append(o)
    o = bl.box('canopy', (2.6, 1.0, 3.6), L(0, 5.9, 4.6), m['canopy'], rot=(.32, 0, 0), bevel=.2); apply(o); P.append(o)
    P.append(B('stripe', (7.3, .3, 1.2), (0, 5.4, -4), m['hull_orange']))
    for s in (-1, 1):
        verts = [L(s * 2.8, 3.4, 3), L(s * 9.5, 3.0, -6.5), L(s * 9.5, 3.0, -10), L(s * 2.8, 3.4, -9)]
        w = bl.mesh_from('wing', verts, [(0, 1, 2, 3)], m['hull']); solidify(w, .35); bl.uv_box(w, 3); P.append(w)
        P.append(CX('nacelle', 1.15, 9.5, (s * 6.4, 3.4, -5.5), m['hull_dark'], 18, 'z'))
        P.append(CX('nacband', 1.2, 1.0, (s * 6.4, 3.4, -2.2), m['hull_orange'], 18, 'z'))
        o = bl.sphere('intake', 1.15, L(s * 6.4, 3.4, -.75), m['hull_dark'], 16, 8, scale=(1, 1, .7)); apply(o); P.append(o)
        nozzle(m, P, s * 6.4, 3.4, -11.2, .95, 1.6)
        o = bl.box('fin', (.25, 3.2, 3.6), L(s * 1.9, 7.0, -8.5), m['hull'], rot=(0, s * .35, 0), bevel=.05); apply(o); P.append(o)
        P.append(bl.sphere('nav', .18, L(s * 9.5, 3.2, -8), m['lr'] if s < 0 else m['lg'], 8, 6)); apply(P[-1])
    nozzle(m, P, 0, 3.8, -12, 1.2, 1.6)
    legs(m, P, [(0, 7.5), (-3.2, -6.5), (3.2, -6.5)], 2.3, .7)
    return ship_root('SP_ship_courier', P, 80)


def ship_lander(m):
    """Shuttle: compact boxy cabin with a glazed nose, four tilting VTOL thruster pods, landing skids."""
    P = [B('body', (5, 3.0, 9.5), (0, 3.4, 0), m['hull_orange'], bevel=.45),
         B('roof', (4.2, .8, 7.0), (0, 5.2, -.6), m['hull'], bevel=.3),
         B('nose', (4.2, 2.3, 2.8), (0, 3.3, 5.8), m['hull'], bevel=.5),
         B('rear', (4.6, 2.6, 1.2), (0, 3.4, -5.2), m['hull_dark'], bevel=.2)]
    o = bl.box('canopy', (3.6, 1.1, 1.8), L(0, 4.4, 6.4), m['canopy'], rot=(.6, 0, 0), bevel=.15); apply(o); P.append(o)
    for sx in (-1, 1):
        for sz in (-1, 1):
            x, z = sx * 3.7, sz * 3.4
            P.append(B('podarm', (1.6, .5, .8), (sx * 2.8, 4.0, z), m['hull_dark']))
            P.append(C('pod', 1.0, 1.8, (x, 3.1, z), m['hull_dark'], 16))
            P.append(C('podring', 1.05, .3, (x, 4.6, z), m['hull_orange'], 16))
            P.append(C('podglow', .8, .1, (x, 3.02, z), m['engine'], 16))
        P.append(B('skid', (.35, .3, 8.4), (sx * 2.1, .15, 0), m['dark']))
        for z in (-2.6, 2.6):
            P.append(B('skidstrut', (.25, 1.9, .25), (sx * 2.1, 1.1, z), m['steel']))
    for x in (-1.2, 1.2):
        nozzle(m, P, x, 3.3, -6.3, .55, 1.0)
    P.append(bl.sphere('beacon', .2, L(0, 5.7, -2), m['lr'], 8, 6)); apply(P[-1])
    return ship_root('SP_ship_lander', P, 140)


# ---------------------------------------------------------------- lights
def lights(m):
    P = []
    base = bl.cyl('lbase', .12, .35, (0, 0, .175), m['dark'], 8); apply(base)

    def fixture(lm, name):
        cap = bl.sphere(name + 'cap', .16, (0, 0, .38), lm, 8, 5, scale=(1, 1, .7)); apply(cap)
        b2 = base.copy(); b2.data = base.data.copy(); bpy.context.scene.collection.objects.link(b2)
        return bl.join([b2, cap], name)
    proto = {k: fixture(m[k], 'fx_' + k) for k in ('lw', 'la', 'lc')}
    bpy.data.objects.remove(base)
    for px, pz in PADS:
        for k in range(16):
            a = k / 16 * math.tau
            P.append(dup(proto['lc'], (px + math.cos(a) * (PAD_R + .6), .08, pz + math.sin(a) * (PAD_R + .6))))
    for hx, hz in HEAVY:
        for j in range(6):
            a0, a1 = j / 6 * math.tau, (j + 1) / 6 * math.tau
            for t in (0, .25, .5, .75):
                x = hx + (math.cos(a0) + (math.cos(a1) - math.cos(a0)) * t) * (HEAVY_R + .6)
                z = hz + (math.sin(a0) + (math.sin(a1) - math.sin(a0)) * t) * (HEAVY_R + .6)
                P.append(dup(proto['la' if t == 0 else 'lc'], (x, .08, z)))
        for k in range(12):
            a = k / 12 * math.tau
            P.append(dup(proto['lw'], (hx + math.cos(a) * 13.7, .09, hz + math.sin(a) * 13.7)))
    for zl in (44.0, 56.0):
        x = FIELD[0] + 10
        while x < FIELD[2]:
            P.append(dup(proto['la'], (x, .07, zl))); x += 30
    for k in proto.values():
        bpy.data.objects.remove(k)
    return P


def fence(m):
    P = []
    x0, z0, x1, z1 = FENCE
    H = 2.6
    lines = [((x0, z0), (TERM[0] - 2, z0)), ((TERM[0] - 2, z0), (TERM[0] - 2, TERM[1])),
             ((TERM[2] + 2, TERM[1]), (TERM[2] + 2, z0)), ((TERM[2] + 2, z0), (x1, z0)),
             ((x1, z0), (x1, z1)), ((x1, z1), (x0, z1)), ((x0, z1), (x0, z0))]
    post = bl.cyl('fpost', .06, H + .5, (0, 0, (H + .5) / 2), m['steel'], 6); apply(post)
    arm = bl.box('farm', (.05, .05, .6), (0, .15, H + .62), m['steel'], rot=(-.6, 0, 0)); apply(arm)
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


def main():
    bake_textures()
    bl.reset()
    m = mats()
    root = bl.empty('SP_site')
    groups = {'SP_ground': ground(m) + markings(m), 'SP_build': terminal(m) + tower(m) + hangars(m) + fuel_farm(m),
              'SP_lights': lights(m), 'SP_props': pad_furniture(m) + containers(m) + vehicles(m) + fence(m)}
    for name, parts in groups.items():
        g = bl.join(parts, name); g.parent = root
    radar(m, *TOWER).parent = root
    ship_hauler(m); ship_courier(m); ship_lander(m)
    meta = {
        'colliders': COLLIDERS,
        'pads': [[x, .1, z] for x, z in PADS], 'heavy': [[x, .1, z] for x, z in HEAVY], 'padR': PAD_R, 'heavyR': HEAVY_R,
        'spawn': [0, .07, -12.5], 'spawnYaw': math.pi,
        'ship': [0, .1, 0], 'vendor': [14, .2, TERM[3] - 9.0], 'vendorYaw': 0.0,
        'terminal': list(TERM), 'field': list(FIELD), 'yard': list(YARD),
        'lots': [list(l) for l in LOTS], 'hangars': [[x, (HANGAR_Z0 + HANGAR_Z1) / 2] for x in HANGARS],
        'fence': list(FENCE), 'tower': list(TOWER), 'radar': [TOWER[0], 43.8, TOWER[1]],
        'paths': [[[-120, -95], [120, -95], [120, -86], [-120, -86]], [[-66, -74], [66, -74], [66, -54], [-66, -54]]],
    }
    root['worldex'] = json.dumps(meta)
    bl.export('spaceport.glb')
    print('[spaceport] colliders', len(COLLIDERS))


main()
