"""The Wayfarer's jumpship (ship_jumper.glb): the landing craft that carries the player between orbit and the surface.

Industrial gunship silhouette: chamfered-octagon fuselage in two-tone paint with orange livery stripes, faceted cockpit
canopy, stub wings with tip pods, two engine nacelles with glowing exhausts (material engine_glow), four landing legs with
pads, belly hover thrusters, dorsal cargo pods, RCS blocks, antennas, landing lights and stencil markings.
Textures come from ship_textures.py (hullplate, paintmetal, deckplate, stencil) with world-scale box UVs.

Conventions the game relies on (keep them): origin on the ground under the hull centre, nose toward Blender -Y (+Z in
three), length ~16 m, hull half-width ~2.4 m, wings ~+-7.8 m. Root node 'ship_jumper' (main hull material 'ship_hull' is
re-tinted for visitor ships). Child 'ramp' = rear boarding ramp, origin on its hinge, modelled closed; extras
'lower' = radians about its local X to lower it onto the ground (earth.js setRamp). Empties: 'ramp_exit' (foot of the
lowered ramp), 'thruster' x2 (main exhausts).
Run: blender --background --python tools/blender/jumpship.py
"""
import bpy, bmesh, math, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import bl
from mathutils import Vector, Matrix

R90 = math.pi / 2
TILE = {}


def tmat(name, color, metal, rough, tex=None, tile=1.0, emit=None, strength=1.0):
    m = bl.mat(name, color, metal, rough, emit=emit, strength=strength,
               image=(tex + '_c.jpg') if tex else None, normal=(tex + '_n.jpg') if tex else None)
    if tex:
        TILE[name] = tile
    return m


def materials():
    P = bl.palette()
    M = dict(P)
    M.update(
        hull=tmat('ship_hull', '#ecebe6', .25, .42, 'hullplate', 4.0),
        dark=tmat('ship_hull_dark', '#5b6168', .45, .4, 'hullplate', 4.0),
        accent=tmat('ship_accent', '#d8661e', .35, .42, 'paintmetal', 1.0),
        frame=tmat('ship_frame', '#3b4148', .7, .4, 'paintmetal', 1.0),
        tread=tmat('ship_tread', '#ffffff', .6, .5, 'deckplate', 1.5),
        hold=tmat('ship_hold', '#8d939b', .4, .5, 'shipwall', 2.0),
        glass=bl.mat('ship_glass', '#0b131a', .6, .05, emit='#0b2a3a', strength=.5),
        glow=bl.mat('engine_glow', '#7fd8ff', 0, .3, emit='#7fd8ff', strength=8),
        lamp=bl.mat('ship_light', '#f2f7ff', 0, .3, emit='#f2f7ff', strength=10),
        green=bl.mat('neon_green', '#30ff70', 0, .4, emit='#30ff70', strength=6),
        hazard=bl.mat('hazard', '#ffffff', .2, .6, image='hazard_c.jpg'),
    )
    TILE['hazard'] = 1.0
    st = bl.mat('stencil', '#f2efe6', 0, .7)
    nt = st.node_tree; b = nt.nodes.get('Principled BSDF')
    tn = nt.nodes.new('ShaderNodeTexImage'); tn.image = bpy.data.images.load(os.path.join(bl.TEXTURES, 'stencil_c.png'))
    nt.links.new(tn.outputs['Color'], b.inputs['Base Color']); nt.links.new(tn.outputs['Alpha'], b.inputs['Alpha'])
    try:
        st.surface_render_method = 'BLENDED'
    except Exception:
        pass
    M['stencil'] = st
    return M


PARTS = []


def part(o):
    m = o.data.materials[0] if o.data.materials else None
    if m is not None and m.name in TILE:
        bl.uv_box(o, TILE[m.name])
    PARTS.append(o)
    return o


def mesh(name, verts, faces, m, uvs=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata([Vector(v) for v in verts], [], faces)
    if uvs:
        uvl = me.uv_layers.new(name='UVMap')
        for i, uv in enumerate(uvs):
            uvl.data[i].uv = uv
    me.validate(); me.update()
    o = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(o)
    me.materials.append(m)
    if not uvs:
        if m.name in TILE:
            bl.uv_box(o, TILE[m.name])
    PARTS.append(o)
    return o


def fill(name, loops, normal, m):
    bm = bmesh.new(); edges = []
    for loop in loops:
        vs = [bm.verts.new(Vector(p)) for p in loop]
        for i in range(len(vs)):
            edges.append(bm.edges.new((vs[i], vs[(i + 1) % len(vs)])))
    bmesh.ops.triangle_fill(bm, use_beauty=True, use_dissolve=False, edges=edges, normal=Vector(normal))
    for f in bm.faces:
        if f.normal.dot(Vector(normal)) < 0:
            f.normal_flip()
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(o); me.materials.append(m)
    if m.name in TILE:
        bl.uv_box(o, TILE[m.name])
    PARTS.append(o)
    return o


def beam(p0, p1, w, d, m, up=(0, 0, 1), name='beam'):
    p0, p1 = Vector(p0), Vector(p1)
    ax = p1 - p0; L = ax.length
    y = ax / L; z = Vector(up); z = (z - y * z.dot(y)).normalized(); x = y.cross(z)
    o = bl.box(name, (w, L, d), (0, 0, 0), m)
    M4 = Matrix((x, y, z)).transposed().to_4x4(); M4.translation = (p0 + p1) / 2
    o.matrix_world = M4
    return part(o)


def revolve(name, m, cx, cz, rings, seg=28, cap=None, cap_m=None):
    """Surface of revolution about an axis parallel to Y through (cx, cz). rings: [(y, r)]."""
    V = []; F = []
    for (y, r) in rings:
        for k in range(seg):
            a = k / seg * 2 * math.pi
            V.append((cx + r * math.cos(a), y, cz + r * math.sin(a)))
    for i in range(len(rings) - 1):
        for k in range(seg):
            a, b = i * seg + k, i * seg + (k + 1) % seg
            F.append((a, a + seg, b + seg, b))
    o = mesh(name, V, F, m)
    if cap is not None:
        y, r = rings[-1] if cap == 'last' else rings[0]
        PARTS.append(bl.cyl(name + '_cap', r, .01, (cx, y, cz), cap_m or m, seg, rot=(R90, 0, 0)))
    return o


def oct_ring(y, W, zb, zt):
    c = min(.6, W * .32); c2 = min(.85, W * .36)
    return [(-W + c, y, zb), (-W, y, zb + c), (-W, y, zt - c2), (-W + c2, y, zt),
            (W - c2, y, zt), (W, y, zt - c2), (W, y, zb + c), (W - c, y, zb)]


FUSE = [(-8.0, .32, 1.95, 2.3), (-7.2, .95, 1.7, 2.8), (-6.0, 1.6, 1.45, 3.2), (-4.5, 2.05, 1.3, 3.55),
        (-2.5, 2.3, 1.22, 3.78), (1.0, 2.4, 1.2, 3.86), (5.0, 2.4, 1.2, 3.86), (7.0, 2.25, 1.25, 3.72), (7.6, 2.1, 1.3, 3.58)]


def fuse_at(y):
    for (ya, *a), (yb, *b) in zip(FUSE[:-1], FUSE[1:]):
        if ya <= y <= yb:
            t = (y - ya) / (yb - ya)
            return [a[k] * (1 - t) + b[k] * t for k in range(3)]
    return FUSE[-1][1:]


def build(name='ship_jumper'):
    bl.reset()
    PARTS.clear(); TILE.clear()
    M = materials()

    # ---------------- fuselage: two-tone loft (light upper hull, dark belly band)
    rings = [oct_ring(y, W, zb, zt) for (y, W, zb, zt) in FUSE]
    body = bl.loft('fuselage', rings, M['hull'], cap=False, smooth=False)
    body.data.materials.append(M['dark'])
    for p in body.data.polygons:
        c = p.center
        W, zb, zt = fuse_at(c.y)
        if c.z < zb + (zt - zb) * .36:
            p.material_index = 1
    bl.uv_box(body, 4.0)
    PARTS.append(body)
    fill('nose_cap', [[Vector(p) for p in rings[0]]], (0, -1, 0), M['dark'])
    # rear bulkhead with the cargo door; the hold behind it is lit
    rear = [Vector(p) for p in rings[-1]]
    door = [Vector(p) for p in ((-.92, 7.6, 1.36), (.92, 7.6, 1.36), (.92, 7.6, 3.2), (.62, 7.6, 3.42), (-.62, 7.6, 3.42), (-.92, 7.6, 3.2))]
    fill('rear', [rear, door], (0, 1, 0), M['dark'])
    for (a, b) in zip(door, door[1:] + door[:1]):
        beam(a + Vector((0, .03, 0)), b + Vector((0, .03, 0)), .12, .1, M['frame'], up=(0, 1, 0))
    part(bl.box('hold', (1.9, 3.0, 2.1), (0, 6.1, 2.4), M['hold']))          # seen from inside (double-sided)
    part(bl.box('hold_floor', (1.84, 2.95, .02), (0, 6.1, 1.37), M['tread']))
    part(bl.box('hold_light', (1.2, .25, .02), (0, 6.0, 3.43), M['lamp']))
    for sx in (-1, 1):
        part(bl.box('hold_strip', (.03, 2.6, .05), (sx * .93, 6.1, 1.6), M['cyan']))

    # ---------------- cockpit canopy: faceted glass with frames
    cr = []
    for (y, w, h) in ((-7.0, .45, .08), (-6.1, 1.2, .48), (-4.9, 1.55, .66), (-3.6, 1.45, .6), (-2.7, 1.0, .25)):
        W, zb, zt = fuse_at(y); z0 = zt - .06
        cr.append([(-w, y, z0), (-w * .78, y, z0 + h * .72), (-w * .36, y, z0 + h), (w * .36, y, z0 + h), (w * .78, y, z0 + h * .72), (w, y, z0)])
    can = bl.loft('canopy', cr, M['glass'], cap=True, smooth=False)
    PARTS.append(can)
    for i in range(len(cr) - 1):
        for k in range(1, 5):
            beam(cr[i][k], cr[i + 1][k], .06, .05, M['frame'], up=(0, 0, 1))
    for r in cr[1:-1]:
        for k in range(5):
            beam(r[k], r[k + 1], .07, .05, M['frame'], up=(0, 0, 1))
    for sx in (-1, 1):   # side windows below the canopy line
        beam((sx * 1.62, -5.9, 2.75), (sx * 2.02, -4.5, 2.9), .03, .22, M['glass'], up=(sx, 0, .3))

    # ---------------- layered armour plates, stripes, vents
    for sx in (-1, 1):
        for (y0, y1, z) in ((-3.8, -.2, 2.55), (.3, 3.9, 2.55), (4.3, 7.1, 2.5)):
            Wa = fuse_at(y0)[0]; Wb = fuse_at(y1)[0]
            beam((sx * (Wa + .04), y0, z), (sx * (Wb + .04), y1, z), .08, .9, M['hull'], up=(sx, 0, 0))
        for (y0, y1) in ((-6.6, 7.3),):
            beam((sx * (fuse_at(-6.6)[0] + .02), y0, 3.12), (sx * (fuse_at(-2.5)[0] + .09), -2.5, 3.12), .04, .2, M['accent'], up=(sx, 0, 0))
            beam((sx * 2.49, -2.5, 3.12), (sx * 2.49, 7.0, 3.12), .04, .2, M['accent'], up=(sx, 0, 0))
            beam((sx * 2.49, -2.5, 2.9), (sx * 2.49, 7.0, 2.9), .04, .06, M['accent'], up=(sx, 0, 0))
        # RCS blocks fore and aft
        for (y, z) in ((-5.6, 2.9), (6.6, 3.3)):
            W = fuse_at(y)[0]
            part(bl.box('rcs', (.35, .6, .4), (sx * (W + .1), y, z), M['frame'], bevel=.05))
            part(bl.cyl('rcs_n', .07, .14, (sx * (W + .3), y, z), M['dark'], 8, rot=(0, R90, 0)))
    for k in range(5):       # dorsal heat-exchanger vents ahead of the pods
        part(bl.box('vent', (1.2, .14, .06), (0, -1.6 + k * .32, 3.9), M['frame']))
    part(bl.box('spine', (.6, 9.0, .32), (0, 2.6, 3.98), M['dark'], bevel=.08))
    part(bl.box('spine_glow', (.06, 7.0, .04), (0, 2.6, 4.15), M['glow']))
    # dorsal cargo pods
    for sx in (-1, 1):
        part(bl.box('pod', (.9, 3.8, .62), (sx * 1.25, 3.6, 4.15), M['dark'], bevel=.12, segs=2))
        for y in (1.75, 5.45):
            part(bl.box('pod_cap', (.94, .22, .66), (sx * 1.25, y, 4.15), M['accent'], bevel=.06))
        part(bl.box('pod_band', (.94, .1, .66), (sx * 1.25, 3.6, 4.15), M['frame']))
    # sensor mast, antennas, nose sensor
    part(bl.cyl('mast', .05, .9, (.6, -1.2, 4.3), M['steel'], 8))
    part(bl.sphere('mast_tip', .07, (.6, -1.2, 4.76), M['red'], 8, 6))
    part(bl.cyl('whip', .02, 1.4, (-.7, 6.6, 4.4), M['steel'], 6))
    part(bl.sphere('nose_sensor', .22, (0, -7.85, 2.05), M['glass'], 12, 8))
    # landing / position lights
    for sx in (-1, 1):
        part(bl.box('landlight', (.3, .08, .12), (sx * .6, -7.05, 1.66), M['lamp'], rot=(-.6, 0, 0)))
    # stencil markings
    def decal(cell, c, n, up, w, h):
        c, n, up = Vector(c), Vector(n).normalized(), Vector(up).normalized()
        r = up.cross(n); c = c + n * .015
        col, row = cell % 4, cell // 4; u0, v0 = col / 4, 1 - (row + 1) / 4
        pts = [c - r * w / 2 - up * h / 2, c + r * w / 2 - up * h / 2, c + r * w / 2 + up * h / 2, c - r * w / 2 + up * h / 2]
        mesh('decal', pts, [(0, 1, 2, 3)], M['stencil'], uvs=[(u0 + .01, v0 + .01), (u0 + .24, v0 + .01), (u0 + .24, v0 + .24), (u0 + .01, v0 + .24)])
    decal(1, (-2.4, 1.6, 3.45), (-1, 0, 0), (0, 0, 1), .8, .8)      # '02'
    decal(1, (2.4, 1.6, 3.45), (1, 0, 0), (0, 0, 1), .8, .8)
    decal(7, (2.41, 6.2, 1.9), (1, 0, 0), (0, 0, 1), .5, .5)        # hazard triangle near the hold

    # ---------------- stub wings with tip pods
    for sx in (-1, 1):
        root = [(-1.4, 2.25, .22), (1.0, 2.3, .26), (5.6, 2.3, .2)]
        tip = [(2.4, 2.45, .1), (3.6, 2.5, .12), (5.1, 2.45, .08)]
        xr, xt = sx * 2.3, sx * 7.4
        V = []
        for (x, pts) in ((xr, root), (xt, tip)):
            top = [(x, y, z + t) for (y, z, t) in pts]; bot = [(x, y, z - t) for (y, z, t) in pts[::-1]]
            V += top + bot
        n = 6
        F = [(k, (k + 1) % n, n + (k + 1) % n, n + k) for k in range(n)] + [tuple(range(n))[::-1], tuple(range(n, 2 * n))]
        w = mesh('wing', V, F, M['hull'])
        bpy.context.view_layer.objects.active = w; w.select_set(True)
        bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.normals_make_consistent(inside=False); bpy.ops.object.mode_set(mode='OBJECT'); w.select_set(False)
        beam((sx * 5.0, 3.0, 2.62), (sx * 7.3, 3.7, 2.6), .5, .03, M['accent'], up=(0, 0, 1))
        part(bl.box('tip_pod', (.38, 3.0, .5), (sx * 7.55, 3.75, 2.45), M['dark'], bevel=.1))
        part(bl.box('tip_fin', (.08, 1.4, .9), (sx * 7.55, 4.4, 1.95), M['dark'], bevel=.03, rot=(-.25, 0, 0)))
        part(bl.sphere('navlight', .1, (sx * 7.77, 2.4, 2.45), M['green'] if sx > 0 else M['red'], 8, 6))
        part(bl.box('tip_glow', (.03, 2.2, .06), (sx * 7.75, 3.9, 2.45), M['glow']))

    # ---------------- engine nacelles
    for sx in (-1, 1):
        cx, cz = sx * 3.35, 2.4
        revolve('nacelle', M['hull'], cx, cz, [(.9, .7), (1.05, .93), (1.4, 1.0), (6.6, 1.0), (7.6, .86), (8.0, .82)])
        revolve('intake', M['frame'], cx, cz, [(.9, .7), (1.2, .55), (1.6, .45)], cap='last', cap_m=M['dark'])
        revolve('nozzle', M['frame'], cx, cz, [(8.0, .82), (8.25, .78), (8.25, .62), (7.9, .55)], cap='last', cap_m=M['glow'])
        part(bl.torus('exhaust_ring', .66, .05, (cx, 8.2, cz), M['glow'], rot=(R90, 0, 0), maj=28, mn=5))
        for (ya, yb) in ((1.55, 1.95), (6.9, 7.25)):
            revolve('band', M['accent'], cx, cz, [(ya, 1.02), (yb, 1.0 if yb < 7 else .92)])
        for yy in (3.2, 4.6):
            part(bl.torus('seam', 1.0, .025, (cx, yy, cz), M['frame'], rot=(R90, 0, 0), maj=28, mn=4))
        part(bl.box('pylon', (.5, 4.2, .9), (sx * 2.75, 4.4, 2.3), M['dark'], bevel=.08))
        bl.empty('thruster', (cx, 8.3, cz))

    # ---------------- belly: hover thrusters, landing legs
    for sx in (-1, 1):
        for sy in (-1, 1):
            x, y = sx * 1.55, sy * 3.5
            part(bl.cyl('hover_ring', .5, .1, (x, y, 1.16), M['frame'], 20))
            part(bl.cyl('hover_glow', .38, .02, (x, y, 1.105), M['glow'], 20))
    legs = [(-1.45, -4.7), (1.45, -4.7), (-1.9, 4.6), (1.9, 4.6)]
    for (x, y) in legs:
        sx = 1 if x > 0 else -1
        foot = Vector((x + sx * .45, y, .07))
        top = Vector((x, y, 1.15))
        part(bl.box('gear_bay', (.7, 1.0, .12), (x, y, 1.2), M['frame']))
        beam(top, foot + Vector((0, 0, .45)), .2, .2, M['dark'], up=(0, 1, 0))
        beam(foot + Vector((0, 0, .45)), foot + Vector((0, 0, .12)), .12, .12, M['steel'], up=(0, 1, 0))
        beam(top + Vector((0, .35 * (-1 if y > 0 else 1), 0)), foot + Vector((-sx * .05, 0, .6)), .07, .07, M['steel'], up=(1, 0, 0))
        part(bl.cyl('pad', .42, .1, foot, M['frame'], 16, bevel=.02))
        part(bl.cyl('pad_rim', .44, .03, foot + Vector((0, 0, .06)), M['hazard'], 16))
        part(bl.box('gear_door', (.05, 1.0, .55), (x + sx * .42, y, .95), M['dark'], rot=(0, sx * .5, 0)))

    # ---------------- join, ramp, empties
    for o in PARTS:
        if o.name in bpy.context.scene.objects:
            bl.apply_all(o)
    g = bl.join([o for o in PARTS if o.name in bpy.context.scene.objects], name)
    # rear boarding ramp, modelled closed (vertical over the door), origin on the hinge
    rp = []
    rp.append(bl.box('ramp_outer', (1.9, .1, 2.05), (0, .1, 1.025), M['dark'], bevel=.02))
    rp.append(bl.box('ramp_tread', (1.7, .02, 1.95), (0, .04, 1.0), M['tread']))
    for sx in (-1, 1):
        rp.append(bl.box('ramp_rail', (.08, .14, 2.05), (sx * .9, .06, 1.025), M['frame']))
        rp.append(bl.box('ramp_lamp', (.03, .02, 1.7), (sx * .84, .03, 1.0), M['cyan']))
    rp.append(bl.box('ramp_stripe', (1.9, .02, .2), (0, .16, 1.75), M['accent']))
    for o in rp:
        if o.data.materials and o.data.materials[0].name in TILE:
            bl.uv_box(o, TILE[o.data.materials[0].name])
        bl.apply_all(o)
    ramp = bl.join(rp, 'ramp')
    ramp.location = (0, 7.52, 1.36)
    ramp.parent = g
    hinge, Lr = 1.36, 2.05
    ramp['lower'] = -round(R90 + math.asin(min(1.0, (hinge - .05) / Lr)), 4)
    bl.empty('ramp_exit', (0, 7.52 + Lr * math.cos(math.asin((hinge - .05) / Lr)) + .6, 0), g)
    for o in list(bpy.context.scene.objects):
        if o.type == 'EMPTY' and o.name.startswith('thruster'):
            o.parent = g
    bl.export(name + '.glb')


if __name__ == '__main__':
    build()
