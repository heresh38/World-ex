"""The collected items' models, for the armoury's pictures of them (icons.py goods -> SourceArt/Icons/goods/
icon_goods_<id>.png; Data/game_data.json "goods"; the owner's armoury reference, 2026-11-20: "an inventory to hold items
we collect"). Each is built from our own parts in its maker's look: the Sarketh's (pale enamel over forged iron, amber
crystal, a little gold, their light), the Institute's (white polymer, steel, cyan), the living guns' (resin, violet).
Materials carry their own detail for Cycles (roughness that varies, a fine grain, chips down to the iron at the edges):
these models are pictures, never in the world.

    import goods; objs = goods.build('amber')       (into the current scene; icons.py lights and frames it)
    blender --background --python tools/blender/goods.py -- <out.png>    (a contact sheet of every item, quick)
"""
import math
import os
import random
import sys
sys.path.insert(0, os.path.dirname(__file__))
import bpy
import bmesh
from mathutils import Vector, Matrix, Euler
import bl

TAU = 2 * math.pi


# ---------------------------------------------------------------- materials (Cycles; the detail is in the shader)
def _noise(nt, scale, detail=8.0, coord='Object'):
    tc = nt.nodes.new('ShaderNodeTexCoord')
    nz = nt.nodes.new('ShaderNodeTexNoise')
    nz.inputs['Scale'].default_value = scale
    nz.inputs['Detail'].default_value = detail
    nt.links.new(tc.outputs[coord], nz.inputs['Vector'])
    return nz


def pbr(name, base, metal=0.0, rough=0.5, rough_var=0.10, grain=0.00025, scale=240.0, coat=0.0, emit=None, strength=0.0,
        transmission=0.0, ior=1.45, sss=0.0, sheen=0.0):
    """a principled surface whose roughness wanders and which carries a fine grain (object space: the item's own size)"""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*bl.hexrgb(base), 1)
    b.inputs['Metallic'].default_value = metal
    b.inputs['Roughness'].default_value = rough
    if transmission:
        b.inputs['Transmission Weight'].default_value = transmission
        b.inputs['IOR'].default_value = ior
    if coat:
        b.inputs['Coat Weight'].default_value = coat
        b.inputs['Coat Roughness'].default_value = .06
    if emit:
        b.inputs['Emission Color'].default_value = (*bl.hexrgb(emit), 1)
        b.inputs['Emission Strength'].default_value = strength
    if sss:
        b.inputs['Subsurface Weight'].default_value = sss
    if sheen:
        b.inputs['Sheen Weight'].default_value = sheen
    if rough_var > 0 or grain > 0:
        nz = _noise(nt, scale)
        if rough_var > 0:
            mr = nt.nodes.new('ShaderNodeMapRange')
            mr.inputs['To Min'].default_value = max(0.0, rough - rough_var)
            mr.inputs['To Max'].default_value = min(1.0, rough + rough_var)
            nt.links.new(nz.outputs['Fac'], mr.inputs['Value'])
            nt.links.new(mr.outputs['Result'], b.inputs['Roughness'])
        if grain > 0:
            bp = nt.nodes.new('ShaderNodeBump')
            bp.inputs['Distance'].default_value = grain
            nt.links.new(nz.outputs['Fac'], bp.inputs['Height'])
            nt.links.new(bp.outputs['Normal'], b.inputs['Normal'])
    return m


def chipped(name, top, under, rough=.36, coat=.25, chips=.7, scale=70.0):
    """an enamel coat over forged iron, chipped down to the iron where it is worn: at the edges (the surface's
    pointiness) and in patches"""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    out = nt.nodes['Material Output']
    enamel = nt.nodes['Principled BSDF']
    enamel.inputs['Base Color'].default_value = (*bl.hexrgb(top), 1)
    enamel.inputs['Roughness'].default_value = rough
    enamel.inputs['Coat Weight'].default_value = coat
    iron = nt.nodes.new('ShaderNodeBsdfPrincipled')
    iron.inputs['Base Color'].default_value = (*bl.hexrgb(under), 1)
    iron.inputs['Metallic'].default_value = .9
    iron.inputs['Roughness'].default_value = .5
    nz = _noise(nt, scale, detail=12.0)
    geo = nt.nodes.new('ShaderNodeNewGeometry')
    edge = nt.nodes.new('ShaderNodeMapRange')                  # (pointiness: .5 on a flat, more on an outside edge)
    edge.inputs['From Min'].default_value = .5
    edge.inputs['From Max'].default_value = .62
    nt.links.new(geo.outputs['Pointiness'], edge.inputs['Value'])
    patch = nt.nodes.new('ShaderNodeMapRange')
    patch.inputs['From Min'].default_value = chips
    patch.inputs['From Max'].default_value = chips + .05
    nt.links.new(nz.outputs['Fac'], patch.inputs['Value'])
    add = nt.nodes.new('ShaderNodeMath'); add.operation = 'MAXIMUM'
    nt.links.new(patch.outputs['Result'], add.inputs[0])
    nt.links.new(edge.outputs['Result'], add.inputs[1])
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.interpolation = 'CONSTANT'
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[1].position = .5
    nt.links.new(add.outputs[0], ramp.inputs['Fac'])
    mix = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(ramp.outputs['Color'], mix.inputs['Fac'])
    nt.links.new(enamel.outputs[0], mix.inputs[1])
    nt.links.new(iron.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])
    bp = nt.nodes.new('ShaderNodeBump')
    bp.inputs['Distance'].default_value = .0003
    nt.links.new(ramp.outputs['Color'], bp.inputs['Height'])
    nt.links.new(bp.outputs['Normal'], enamel.inputs['Normal'])
    return m


def crystal(name, base, absorb, density, emit, strength):
    """a crystal: clear-cut, its colour deepening with the depth of it (absorption inside), a light of its own"""
    m = pbr(name, base, rough=.05, rough_var=.03, grain=0, transmission=1.0, ior=1.56, emit=emit, strength=strength)
    nt = m.node_tree
    vol = nt.nodes.new('ShaderNodeVolumeAbsorption')
    vol.inputs['Color'].default_value = (*absorb, 1)
    vol.inputs['Density'].default_value = density
    nt.links.new(vol.outputs[0], nt.nodes['Material Output'].inputs['Volume'])
    return m


def resin_mat():
    """set sap: dark olive, half clear, a violet light running in fine veins through it (the edges of cells in space,
    only where a slower noise lets them)"""
    m = pbr('g_resin', '#3a5418', rough=.18, rough_var=.12, grain=.0003, transmission=.35, ior=1.5, sss=.45, scale=90)
    nt = m.node_tree
    b = nt.nodes['Principled BSDF']
    tc = nt.nodes.new('ShaderNodeTexCoord')
    vo = nt.nodes.new('ShaderNodeTexVoronoi')
    vo.feature = 'DISTANCE_TO_EDGE'
    vo.inputs['Scale'].default_value = 38.0
    nt.links.new(tc.outputs['Object'], vo.inputs['Vector'])
    line = nt.nodes.new('ShaderNodeMapRange')                  # (a thin line along every cell's edge)
    line.inputs['From Min'].default_value = .0
    line.inputs['From Max'].default_value = .045
    line.inputs['To Min'].default_value = 1.0
    line.inputs['To Max'].default_value = 0.0
    nt.links.new(vo.outputs['Distance'], line.inputs['Value'])
    nz = _noise(nt, 22.0, detail=4.0)
    where = nt.nodes.new('ShaderNodeMapRange')                 # (only some of them run)
    where.inputs['From Min'].default_value = .5
    where.inputs['From Max'].default_value = .62
    nt.links.new(nz.outputs['Fac'], where.inputs['Value'])
    vein = nt.nodes.new('ShaderNodeMath'); vein.operation = 'MULTIPLY'
    nt.links.new(line.outputs['Result'], vein.inputs[0])
    nt.links.new(where.outputs['Result'], vein.inputs[1])
    glow = nt.nodes.new('ShaderNodeMath'); glow.operation = 'MULTIPLY'; glow.inputs[1].default_value = 14.0
    nt.links.new(vein.outputs[0], glow.inputs[0])
    b.inputs['Emission Color'].default_value = (*bl.hexrgb('#b456ff'), 1)
    nt.links.new(glow.outputs[0], b.inputs['Emission Strength'])
    return m


M = {}


def mats():
    if M:
        return
    M['amber'] = crystal('g_amber', '#ffbe48', (1.0, .74, .16), 130.0, '#ff8c00', .22)
    M['amber_dim'] = crystal('g_amber_dim', '#eca838', (1.0, .66, .1), 190.0, '#d86800', .12)
    M['void'] = crystal('g_void', '#8a50f0', (.52, .12, 1.0), 240.0, '#7a26ff', .45)
    M['clear'] = pbr('g_clear', '#e8f2ff', rough=.03, rough_var=.02, grain=0, transmission=1.0, ior=1.5)
    M['glass_cyan'] = pbr('g_glass_cyan', '#bff4ff', rough=.04, rough_var=.02, grain=0, transmission=.95, ior=1.45)
    M['steel'] = pbr('g_steel', '#9aa1aa', metal=1.0, rough=.30, rough_var=.12, grain=.0002, scale=320)
    M['iron'] = pbr('g_iron', '#3a3836', metal=.9, rough=.52, rough_var=.14, grain=.00035, scale=160)
    M['dark'] = pbr('g_dark', '#1c1e22', metal=.3, rough=.6, rough_var=.1, grain=.0002)
    M['gold'] = pbr('g_gold', '#d9a646', metal=1.0, rough=.26, rough_var=.1, grain=.00018, scale=280)
    M['brass'] = pbr('g_brass', '#b8893d', metal=1.0, rough=.4, rough_var=.16, grain=.0003, scale=200)
    M['enamel'] = chipped('g_enamel', '#ddd5c4', '#3c3936')
    M['plate_enamel'] = chipped('g_plate_enamel', '#cfc5b0', '#36332f', rough=.46, chips=.56, scale=55.0)
    M['enamel_clean'] = pbr('g_enamel_clean', '#ddd5c4', rough=.34, rough_var=.08, grain=.00018, coat=.25, scale=200)
    M['polymer'] = pbr('g_polymer', '#d5d8dd', rough=.44, rough_var=.08, grain=.00015, scale=300)
    M['polymer_dark'] = pbr('g_polymer_dark', '#2a2e34', rough=.55, rough_var=.08, grain=.00015, scale=300)
    M['accent'] = pbr('g_accent', '#24b9dd', rough=.38, rough_var=.06, grain=.00012)
    M['rubber'] = pbr('g_rubber', '#15171a', rough=.86, rough_var=.06, grain=.0004, scale=500)
    M['cyan'] = pbr('g_cyan', '#7fe9ff', rough=.3, rough_var=0, grain=0, emit='#30d6ff', strength=9.0)
    M['liquid'] = pbr('g_liquid', '#72ffb0', rough=.1, rough_var=0, grain=0, transmission=.5, emit='#28ff86', strength=1.6)
    M['resin'] = resin_mat()
    M['vein'] = pbr('g_vein', '#d08cff', rough=.3, rough_var=0, grain=0, emit='#b050ff', strength=16.0)
    M['cloth'] = pbr('g_cloth', '#4a0609', rough=.8, rough_var=.08, grain=.0003, scale=900)
    M['leather'] = pbr('g_leather', '#3a2618', rough=.7, rough_var=.12, grain=.0003, scale=400)


# ---------------------------------------------------------------- parts
def finish(o, bevel=0.0, smooth=False, segs=2):
    """normals out, an optional bevel to catch the light, flat (facets) or smooth"""
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(o.data)
    bm.free()
    if bevel > 0:
        md = o.modifiers.new('bv', 'BEVEL')
        md.width = bevel
        md.segments = segs
        md.limit_method = 'ANGLE'
        bpy.context.view_layer.objects.active = o
        bpy.ops.object.modifier_apply(modifier=md.name)
    for p in o.data.polygons:
        p.use_smooth = smooth
    return o


def tube(name, pts, r, m, sides=12, cap=True):
    """a round section swept along points"""
    bm = bmesh.new()
    rings = []
    for i, p in enumerate(pts):
        t = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        a = t.cross(Vector((0, 0, 1)) if abs(t.z) < .9 else Vector((1, 0, 0))).normalized()
        b = t.cross(a).normalized()
        rr = r(i / max(len(pts) - 1, 1)) if callable(r) else r
        rings.append([bm.verts.new(p + (a * math.cos(TAU * k / sides) + b * math.sin(TAU * k / sides)) * rr) for k in range(sides)])
    for r0, r1 in zip(rings, rings[1:]):
        for k in range(sides):
            bm.faces.new((r0[k], r0[(k + 1) % sides], r1[(k + 1) % sides], r1[k]))
    if cap:
        bm.faces.new(rings[0][::-1])
        bm.faces.new(rings[-1])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    o.data.materials.append(m)
    return finish(o, smooth=True)


def shard(name, at, up, length, radius, m, seed, sides=6, waist=.72, bevel=.0005):
    """a crystal: an irregular prism of `sides` faces that runs to a point, chipped at its base"""
    R = random.Random(seed)
    up = Vector(up).normalized()
    a = up.orthogonal().normalized()
    b = up.cross(a)
    at = Vector(at)
    rings = []
    for h, rr in ((0.0, radius * .78), (.16, radius), (waist, radius * .88)):
        ring = []
        for k in range(sides):
            ang = TAU * k / sides + R.uniform(-.16, .16)
            ring.append(at + up * (h * length) + (a * math.cos(ang) + b * math.sin(ang)) * rr * R.uniform(.86, 1.1))
        rings.append(ring)
    tip = at + up * length + (a * R.uniform(-.25, .25) + b * R.uniform(-.25, .25)) * radius
    verts = [v for ring in rings for v in ring] + [tip]
    faces = []
    for i in range(2):
        for k in range(sides):
            faces.append((i * sides + k, i * sides + (k + 1) % sides, (i + 1) * sides + (k + 1) % sides, (i + 1) * sides + k))
    t = len(verts) - 1
    for k in range(sides):
        faces.append((2 * sides + k, 2 * sides + (k + 1) % sides, t))
    faces.append(tuple(range(sides))[::-1])
    o = bl.mesh_from(name, verts, faces, m)
    return finish(o, bevel=bevel)


def gem(name, at, r, m, seed, stretch=(1, 1, 1)):
    """a faceted bead (an icosphere cut once)"""
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=1, radius=r)
    R = random.Random(seed)
    for v in bm.verts:
        v.co = Vector((v.co.x * stretch[0], v.co.y * stretch[1], v.co.z * stretch[2])) * R.uniform(.94, 1.06)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    o.location = at
    o.data.materials.append(m)
    return finish(o, bevel=r * .06)


def disc(name, r, h, at, m, verts=64, bevel=.0008, rot=(0, 0, 0)):
    return bl.cyl(name, r, h, at, m, verts=verts, rot=rot, bevel=bevel)


def place(objs, rot=(0, 0, 0), at=(0, 0, 0)):
    """turns and moves a whole item about its origin"""
    M_ = Matrix.Translation(Vector(at)) @ Euler(rot).to_matrix().to_4x4()
    bpy.context.view_layer.update()                              # (objects made from data have no world matrix yet)
    for o in objs:
        o.matrix_world = M_ @ o.matrix_world
    return objs


# ---------------------------------------------------------------- the items
def amber():
    # chipped condensate: a cluster of shards of their crystal broken off the fallen
    out = [shard('amber_main', (0, 0, 0), (.15, .1, 1), .085, .015, M['amber'], 1)]
    R = random.Random(7)
    for i in range(6):
        a = TAU * i / 6 + R.uniform(-.3, .3)
        d = Vector((math.cos(a), math.sin(a), 0))
        out.append(shard(f'amber_{i}', d * .012, d * .9 + Vector((0, 0, .9)), R.uniform(.03, .055), R.uniform(.007, .011),
                         M['amber'] if i % 2 else M['amber_dim'], 10 + i))
    return out


def parts():
    # machined parts: a coil spring, a milled block with its bores, a grooved pin, two screws
    out = []
    pts = [Vector((.009 * math.cos(TAU * 7 * t), .009 * math.sin(TAU * 7 * t), .055 * t)) for t in [i / 280 for i in range(281)]]
    s = tube('spring', pts, .0013, M['steel'], sides=10)
    s.rotation_euler = (math.radians(90), 0, math.radians(20))
    s.location = (-.03, .012, .0105)
    out.append(s)
    blk = bl.box('block', (.034, .022, .013), (.012, -.006, .0065), M['steel'], bevel=.0016, segs=3)
    out.append(blk)
    for x in (.002, .022):
        out.append(disc('bore', .0034, .0008, (x, -.006, .0131), M['dark'], verts=32, bevel=0))
    out.append(bl.box('mill', (.03, .0012, .0006), (.012, -.017, .0131), M['dark']))
    pin = bl.cyl('pin', .0032, .05, (.0, .022, .0032), M['steel'], verts=32, rot=(0, math.radians(90), math.radians(-12)), bevel=.0006)
    out.append(pin)
    out.append(bl.torus('groove', .0032, .0006, (.012, .0195, .0032), M['dark'], rot=(0, math.radians(90), math.radians(-12)), maj=32, mn=6))
    for i, (x, y, a) in enumerate(((.038, .016, 30), (.046, -.012, -50))):
        rot = (math.radians(90), 0, math.radians(a))
        head = bl.cyl('head', .0048, .0028, (x, y, .0048), M['steel'], verts=32, rot=rot, bevel=.0006)
        d = Vector((math.cos(math.radians(a + 90)), math.sin(math.radians(a + 90)), 0))
        shaft = tube('shaft', [Vector((x, y, .0048)) - d * .001 - d * t * .018 for t in (0, .5, 1)], .0021, M['steel'], sides=16)
        out += [head, shaft]
    return out


def resin():
    # brood resin: a lump of a living gun's sap, set hard, a slow pulse in its veins
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=4, radius=.032)
    R = random.Random(3)
    for v in bm.verts:
        p = v.co
        wob = .004 * math.sin(p.x * 160 + 1.3) * math.cos(p.y * 140) + .003 * math.sin(p.z * 210 + p.x * 90)
        v.co = Vector((p.x * 1.25, p.y * 1.0, p.z * .78)) * (1 + wob / .032)
    me = bpy.data.meshes.new('resin')
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new('resin', me)
    bpy.context.scene.collection.objects.link(o)
    o.data.materials.append(M['resin'])
    out = [finish(o, smooth=True)]
    return out


def plate():
    # forged plate: a shard of a Sarketh shell, enamel over iron, broken off along a ragged edge, two rivets left in it
    R = random.Random(11)
    corners = []
    for k in range(14):
        a = TAU * k / 14
        corners.append((a, (1.0 if k % 3 else R.uniform(.64, .8)) * R.uniform(.92, 1.05)))
    corners.append((TAU, corners[0][1]))

    def edge(a):
        # the broken outline's radius at an angle: between its corners, with a fine break along it
        for (a0, r0), (a1, r1) in zip(corners, corners[1:]):
            if a0 <= a <= a1:
                t = (a - a0) / (a1 - a0)
                return (r0 + (r1 - r0) * t) * (1 + .025 * math.sin(a * 37) + .015 * math.sin(a * 91))
        return 1.0

    def bend(x, y):
        return -5.4 * x * x - 1.5 * y * y

    rings, around = 9, 96
    bm = bmesh.new()
    centre = bm.verts.new((0, 0, 0))
    grid = []
    for i in range(1, rings + 1):
        row = []
        for k in range(around):
            a = TAU * k / around
            r = edge(a) * i / rings
            x, y = math.cos(a) * .052 * r, math.sin(a) * .036 * r
            row.append(bm.verts.new((x, y, bend(x, y))))
        grid.append(row)
    for k in range(around):
        bm.faces.new((centre, grid[0][k], grid[0][(k + 1) % around]))
    for r0, r1 in zip(grid, grid[1:]):
        for k in range(around):
            bm.faces.new((r0[k], r1[k], r1[(k + 1) % around], r0[(k + 1) % around]))
    me = bpy.data.meshes.new('plate')
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new('plate', me)
    bpy.context.scene.collection.objects.link(o)
    o.data.materials.append(M['plate_enamel'])
    o.data.materials.append(M['iron'])
    sd = o.modifiers.new('sd', 'SOLIDIFY')
    sd.thickness = .0045
    sd.offset = -1
    sd.material_offset = 1
    sd.material_offset_rim = 1
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.modifier_apply(modifier=sd.name)
    out = [finish(o, bevel=.0007, smooth=True)]
    for x, y in ((-.024, .012), (-.010, .017)):
        out.append(bl.sphere('rivet', .0028, (x, y, bend(x, y) + .0006), M['iron'], seg=24, rings=12, scale=(1, 1, .45)))
    seam = [Vector((-.03 + .06 * t, -.012 + .006 * t, bend(-.03 + .06 * t, -.012 + .006 * t) + .00025)) for t in [i / 24 for i in range(25)]]
    out.append(tube('seam', seam, .0005, M['dark'], sides=6))
    return out


def void_crystal():
    # the empire's crystal: one long point grown from a little cluster of its own
    out = [shard('void_main', (0, 0, 0), (.05, -.08, 1), .11, .016, M['void'], 5, sides=6, waist=.8)]
    for i, (a, l, r) in enumerate(((.4, .04, .007), (2.4, .032, .006), (4.3, .045, .0075))):
        d = Vector((math.cos(a), math.sin(a), 0))
        out.append(shard(f'void_{i}', d * .01, d + Vector((0, 0, 1.4)), l, r, M['void'], 20 + i))
    return out


def stim():
    # an Institute auto-injector: white body, the grip's rubber band, a window on the dose, a cyan cap, the needle's end
    out = []
    ax = (0, math.radians(90), 0)
    out.append(bl.cyl('body', .0085, .07, (0, 0, 0), M['polymer'], verts=48, rot=ax, bevel=.0008))
    out.append(bl.cyl('grip', .0089, .022, (-.02, 0, 0), M['rubber'], verts=48, rot=ax, bevel=.0006))
    for x in (-.028, -.024, -.020, -.016, -.012):
        out.append(bl.torus('rib', .0089, .0007, (x, 0, 0), M['rubber'], rot=ax, maj=40, mn=6))
    out.append(bl.cyl('window', .00868, .02, (.016, 0, 0), M['glass_cyan'], verts=48, rot=ax))
    out.append(bl.cyl('dose', .0072, .019, (.016, 0, 0), M['liquid'], verts=32, rot=ax))
    out.append(bl.cyl('cap', .0092, .016, (.042, 0, 0), M['accent'], verts=48, rot=ax, bevel=.0009))
    out.append(bl.cyl('tip', .0064, .006, (.0528, 0, 0), M['polymer_dark'], verts=32, rot=ax, r2=.0045, bevel=.0004))
    out.append(bl.cyl('button', .0052, .007, (-.0375, 0, 0), M['accent'], verts=32, rot=ax, bevel=.0008))
    out.append(bl.cyl('stripe', .00866, .0026, (.0, 0, 0), M['cyan'], verts=48, rot=ax))
    out.append(bl.box('clip', (.03, .0028, .0016), (-.002, 0, .0096), M['steel'], bevel=.0006))
    return place(out, rot=(math.radians(-8), math.radians(-24), math.radians(-18)))


def cell():
    # a shield cell: a six-sided charged cell in dark polymer, its core lit through a window, steel ends, gold contacts
    out = [bl.cyl('body', .017, .05, (0, 0, 0), M['polymer_dark'], verts=6, bevel=.0012, smooth=False)]
    out.append(bl.cyl('window', .0173, .02, (0, 0, .002), M['glass_cyan'], verts=6, smooth=False))
    out.append(bl.cyl('core', .0105, .046, (0, 0, 0), M['cyan'], verts=24))
    for s in (1, -1):
        out.append(bl.cyl('end', .0178, .006, (0, 0, s * .027), M['steel'], verts=6, bevel=.001, smooth=False))
        out.append(bl.cyl('ring', .0181, .0015, (0, 0, s * .0225), M['accent'], verts=6, smooth=False))
    for k in range(3):
        a = TAU * k / 3 + .5
        out.append(bl.cyl('contact', .0024, .003, (math.cos(a) * .008, math.sin(a) * .008, .0312), M['gold'], verts=20, bevel=.0004))
    out.append(bl.box('tab', (.012, .003, .004), (.0145, 0, .021), M['steel'], bevel=.0006, rot=(0, 0, math.radians(30))))
    return place(out, rot=(math.radians(14), math.radians(-18), 0))


def overcharge():
    # a splinter of void crystal sealed in glass between two gold caps
    out = [bl.cyl('vial', .0095, .052, (0, 0, 0), M['clear'], verts=48)]
    out.append(bl.sphere('bottom', .0095, (0, 0, -.026), M['clear'], seg=48, rings=16, scale=(1, 1, .7)))
    out.append(bl.cyl('cap', .0102, .009, (0, 0, .03), M['gold'], verts=48, bevel=.0008))
    out.append(bl.cyl('seal', .0066, .004, (0, 0, .0365), M['gold'], verts=40, bevel=.0006))
    out.append(bl.torus('band', .0099, .0009, (0, 0, .0245), M['gold'], maj=48, mn=8))
    out.append(shard('splinter', (0, .001, -.017), (.18, .1, 1), .034, .0045, M['void'], 9, waist=.8))
    return place(out, rot=(math.radians(10), math.radians(-28), math.radians(10)))


def command_core():
    # the commander's core: an amber crystal held in four pale claws from a forged collar, gold at the joints and the
    # Sarketh's light in a row of dashes round the collar
    out = []
    core = shard('core', (0, 0, -.034), (0, 0, 1), .068, .011, M['amber'], 4, sides=6, waist=.5)
    out.append(core)
    out.append(shard('core_low', (0, 0, -.006), (0, 0, -1), .034, .0102, M['amber'], 6, sides=6))
    out.append(bl.torus('collar', .021, .0042, (0, 0, -.004), M['iron'], maj=48, mn=10))
    out.append(bl.cyl('collar_band', .0195, .006, (0, 0, -.004), M['iron'], verts=48))
    for k in range(10):
        a = TAU * k / 10
        out.append(bl.box('light', (.0042, .0012, .0018), (math.cos(a) * .0252, math.sin(a) * .0252, -.004), M['cyan'], rot=(0, 0, a + math.pi / 2)))
    for k in range(4):
        a = TAU * k / 4 + math.pi / 4
        d = Vector((math.cos(a), math.sin(a), 0))
        for s in (1, -1):
            pts = [d * (.022 - .009 * t * t) + Vector((0, 0, -.004 + s * (.006 + .03 * t))) for t in [i / 16 for i in range(17)]]
            out.append(tube('claw', pts, lambda t: .0034 * (1 - .55 * t), M['enamel_clean'], sides=10))
            out.append(bl.sphere('knuckle', .0036, d * .022 + Vector((0, 0, -.004 + s * .006)), M['gold'], seg=20, rings=10))
    out.append(bl.cyl('foot', .012, .006, (0, 0, -.045), M['iron'], verts=32, bevel=.001))
    return place(out, rot=(math.radians(8), math.radians(-12), 0))


def emblem(at, scale, m, raise_=.0012):
    """the Sarketh's mark raised on a face lying in XY: the brow's chevron over the lozenge, three dashes either side"""
    x0, y0, z0 = at
    out = []
    for s in (1, -1):
        out.append(bl.box('brow', (.011 * scale, .0026 * scale, raise_), (x0 + s * .0048 * scale, y0 + .0082 * scale, z0 + raise_ / 2), m,
                          rot=(0, 0, s * math.radians(-28)), bevel=raise_ * .3))
        for k in range(3):
            out.append(bl.box('dash', (.0030 * scale, .0011 * scale, raise_), (x0 + s * (.0095 + .0042 * k) * scale, y0 - .0012 * scale, z0 + raise_ / 2), m, bevel=raise_ * .25))
    out.append(bl.box('lozenge', (.0068 * scale, .0068 * scale, raise_), (x0, y0 - .0012 * scale, z0 + raise_ / 2), m, rot=(0, 0, math.radians(45)), bevel=raise_ * .3))
    out.append(bl.box('slit', (.0012 * scale, .0062 * scale, raise_ * .4), (x0, y0 - .0012 * scale, z0 + raise_ + raise_ * .2), M['dark']))
    return out


def seal():
    # the Galleria's gate seal: a heavy gold disc, a raised rim, their mark struck in it, an iron loop for its cord
    out = [disc('disc', .03, .006, (0, 0, .003), M['gold'], bevel=.0012)]
    out.append(bl.torus('rim', .0272, .0014, (0, 0, .006), M['gold'], maj=96, mn=10))
    out += emblem((0, -.002, .006), 1.28, M['gold'])
    for k in range(24):
        a = TAU * k / 24
        out.append(bl.box('tick', (.0024, .0008, .0007), (math.cos(a) * .0236, math.sin(a) * .0236, .00635), M['gold'], rot=(0, 0, a)))
    out.append(bl.torus('loop', .0058, .0016, (0, .0352, .003), M['iron'], rot=(math.radians(90), 0, 0), maj=32, mn=10))
    return place(out, rot=(math.radians(52), 0, math.radians(-14)))


def cord():
    # a captain's cord: three strands of red twisted round one line, coiled once, gold at both ends and at the knot
    path = []
    for i in range(301):
        t = i / 300
        a = TAU * 1.15 * t
        r = .028 - .01 * t
        path.append(Vector((math.cos(a) * r, math.sin(a) * r, .006 + .004 * math.sin(TAU * t * 2))))
    path = [Vector((.05, -.018, .006))] + path
    length = 0.0
    out = []
    pos = [0.0]
    for p0, p1 in zip(path, path[1:]):
        length += (p1 - p0).length
        pos.append(length)
    for s in range(3):
        pts = []
        for i, p in enumerate(path):
            t = (path[min(i + 1, len(path) - 1)] - path[max(i - 1, 0)]).normalized()
            a = t.cross(Vector((0, 0, 1))).normalized()
            b = t.cross(a).normalized()
            th = pos[i] / .007 * TAU + TAU * s / 3
            pts.append(p + (a * math.cos(th) + b * math.sin(th)) * .0013)
        out.append(tube(f'strand_{s}', pts, .00115, M['cloth'], sides=8))
    for end, nxt in ((path[0], path[1]), (path[-1], path[-2])):
        d = (end - nxt).normalized()
        out.append(tube('aglet', [end - d * .001, end + d * .009], lambda t: .0026 * (1 - .25 * t), M['gold'], sides=20))
    out.append(bl.torus('knot', .0034, .0011, path[150], M['gold'], rot=(0, math.radians(90), math.atan2(path[151].y - path[149].y, path[151].x - path[149].x)), maj=24, mn=8))
    return out


def lens():
    # a Speaker's signal lens: a glass in an iron frame with a gold ring, the half-message still flickering in it
    out = [bl.sphere('glass', .021, (0, 0, 0), M['glass_cyan'], seg=48, rings=24, scale=(1, 1, .22))]
    out.append(bl.torus('frame', .0222, .0026, (0, 0, 0), M['iron'], maj=64, mn=12))
    out.append(bl.torus('ring', .0196, .0009, (0, 0, .0022), M['gold'], maj=64, mn=8))
    R = random.Random(2)
    for i in range(4):
        a0 = R.uniform(0, TAU)
        rr = R.uniform(.005, .015)
        pts = [Vector((math.cos(a0 + t * 1.9) * rr, math.sin(a0 + t * 1.9) * rr, .0005 * math.sin(t * 13))) for t in [k / 20 for k in range(21)]]
        out.append(tube(f'flicker_{i}', pts, .00032, M['cyan'], sides=6))
    out.append(bl.box('tab', (.012, .0055, .0042), (.0275, 0, 0), M['iron'], bevel=.0008))
    out.append(bl.cyl('rivet', .0016, .0052, (.0305, 0, 0), M['gold'], verts=20, bevel=.0003))
    return place(out, rot=(math.radians(58), 0, math.radians(-20)))


def brand():
    # a pack leader's brand: a brass plate with their mark and a row of tally dashes, an iron eyelet at one end
    out = [bl.box('plate', (.056, .032, .0034), (0, 0, .0017), M['brass'], bevel=.0011, segs=3)]
    out += emblem((-.004, .002, .0034), 1.0, M['brass'], raise_=.0008)
    for k in range(6):
        out.append(bl.box('mark', (.0016, .0058, .0005), (-.02 + k * .0042, -.0105, .00365), M['brass'], bevel=.0002))
    out.append(bl.torus('eyelet', .0046, .0013, (.0215, 0, .0034), M['iron'], maj=32, mn=10))
    out.append(disc('hole', .0034, .0008, (.0215, 0, .0034), M['dark'], verts=32, bevel=0))
    return place(out, rot=(math.radians(48), 0, math.radians(-16)))


def tally():
    # a hunter's tally: notched crystal beads strung on a leather thong, amber and clear in turn
    path = [Vector((-.045 + .09 * t, .016 * math.sin(math.pi * t) - .004, .003 + .003 * math.sin(TAU * t))) for t in [i / 60 for i in range(61)]]
    out = [tube('thong', path, .0011, M['leather'], sides=10)]
    R = random.Random(4)
    for i in range(7):
        t = .14 + .72 * i / 6
        p = path[int(t * 60)]
        r = R.uniform(.0042, .006)
        b = gem(f'bead_{i}', p, r, M['amber'] if i % 2 == 0 else M['clear'], 30 + i, stretch=(1, 1, 1.15))
        b.rotation_euler = (R.uniform(0, 3), R.uniform(0, 3), R.uniform(0, 3))
        out.append(b)
        out.append(bl.torus('notch', r * .96, .0003, p, M['dark'], rot=b.rotation_euler, maj=24, mn=4))
    return place(out, rot=(math.radians(28), 0, math.radians(-10)))


ITEMS = dict(amber=amber, parts=parts, resin=resin, plate=plate, void_crystal=void_crystal, stim=stim, cell=cell,
             overcharge=overcharge, command_core=command_core, seal=seal, cord=cord, lens=lens, brand=brand, tally=tally)
# where the camera looks from (the default: in front, to the left, a little above)
VIEW = dict(plate=(-.35, .62, -.72), parts=(-.4, .7, -.6), cord=(-.3, .55, -.78), resin=(-.5, .75, -.42))


def build(gid):
    """builds the item into the current scene; returns its objects"""
    mats()
    before = set(bpy.context.scene.objects)
    ITEMS[gid]()
    return [o for o in bpy.context.scene.objects if o not in before and o.type == 'MESH']


if __name__ == '__main__':
    # a quick contact sheet of every item (workbench), for building them
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    out = args[0] if args else os.path.join(os.path.dirname(__file__), 'goods_sheet.png')
    bl.reset()
    for i, gid in enumerate(ITEMS):
        objs = build(gid)
        place(objs, at=((i % 5) * .14, -(i // 5) * .14, 0))
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_WORKBENCH'
    sc.render.resolution_x, sc.render.resolution_y = 1400, 900
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.type = 'ORTHO'
    cam.data.ortho_scale = .78
    cam.location = (.28, -.14 - .9, .9)
    cam.rotation_euler = (math.radians(45), 0, 0)
    sc.render.filepath = out
    bpy.ops.render.render(write_still=True)
    print('[goods] sheet', out)
