"""Things in the world that explode (ASOExplosive; the owner's effects guide: "environmental explosion: reactive
environment; vehicle explosion: massive and dramatic"), modelled at their real size, each with its origin at the middle
of its foot and a convex collision hull (UCX_<name>_<n>), into assets/models/explosives.glb:

  EX_drum      a 200-litre steel drum, 58.5 cm across and 88 cm tall: rolled chimes top and bottom, two rolling
               hoops, a lid with its two screwed bungs, knocked in where it was dropped, FUEL stencilled round it
  EX_cylinder  a gas bottle, 23 cm across and 1.47 m tall: a foot ring, the body rounded into a domed shoulder (painted
               white: what is in it), the neck ring, a brass valve with its handwheel and outlet under a steel guard
  EX_cell      a Sarketh crystal cell (their power: the condensers of their guns, their machines): an amber crystal
               column held by three pale claws on a forged iron base, a collar round it, small amber lights round the base
  EX_car       a wrecked city car, 4.3 m: the body cut round its wheel arches and tapered in to the roof, its glass dark
               with dirt, bumpers, lamps, mirrors, the sills rusted through; its fuel tank under the back seat

The car faces +X; everything stands on Z = 0. Material names are an API (import_assets.explosives gives each its
texture set and its colour): ex_paint_red / _blue / _white / _car (industrial enamel: explosive_maps.py ex_paint, the
instance's tint is its colour), ex_stencil (the same paint, white), ex_rust (explosive_maps.py), ex_steel (wpn_steel),
ex_brass, ex_rubber (wpn_rubber), ex_glass, ex_lamp, ex_tail, ex_iron (wpn_metal: the Sarketh's forged iron),
ex_pale (wpn_paint: their pale ceramic), ex_crystal (their amber, lit).

    blender --background --python tools/blender/explosives.py [-- --look=<dir>]
"""
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bl                                                            # noqa: E402

TILE = .5                                                            # the ex_ sets' repeat (explosive_maps.TILE)
WPN = .22                                                            # the gun sets' repeat (surface_maps.TILE)
TAU = 2 * math.pi
M = {}


# ---------------------------------------------------------------- materials
def tex_mat(name, tex, rough=.5, metal=0.0, nstr=1.0, tint=(1, 1, 1)):
    """a material on a texture engine set (assets/textures/<tex>_c.jpg, _n.png, _m.png: R occlusion, G roughness,
    B metal), wired the way the glTF exporter reads it; tint: what the game's instance multiplies it by (shown here)"""
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    b = nt.nodes.get('Principled BSDF')
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal

    def img(f, data):
        n = nt.nodes.new('ShaderNodeTexImage')
        n.image = bpy.data.images.load(os.path.join(bl.TEXTURES, f), check_existing=True)
        if data:
            n.image.colorspace_settings.name = 'Non-Color'
        return n
    c = img(tex + '_c.jpg', False)
    if tint != (1, 1, 1):
        mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'; mix.blend_type = 'MULTIPLY'
        mix.inputs['Factor'].default_value = 1.0
        nt.links.new(c.outputs['Color'], mix.inputs[6]); mix.inputs[7].default_value = (*tint, 1)
        nt.links.new(mix.outputs[2], b.inputs['Base Color'])
    else:
        nt.links.new(c.outputs['Color'], b.inputs['Base Color'])
    n = img(tex + '_n.png', True); nm = nt.nodes.new('ShaderNodeNormalMap'); nm.inputs['Strength'].default_value = nstr
    nt.links.new(n.outputs['Color'], nm.inputs['Color']); nt.links.new(nm.outputs['Normal'], b.inputs['Normal'])
    r = img(tex + '_m.png', True); sp = nt.nodes.new('ShaderNodeSeparateColor')
    nt.links.new(r.outputs['Color'], sp.inputs['Color'])
    nt.links.new(sp.outputs['Green'], b.inputs['Roughness']); nt.links.new(sp.outputs['Blue'], b.inputs['Metallic'])
    m.use_backface_culling = True
    return m


def mats():
    M['red'] = tex_mat('ex_paint_red', 'ex_paint', tint=(.40, .065, .03))
    M['blue'] = tex_mat('ex_paint_blue', 'ex_paint', tint=(.10, .17, .26))
    M['white'] = tex_mat('ex_paint_white', 'ex_paint', tint=(.86, .85, .82))
    M['car'] = tex_mat('ex_paint_car', 'ex_paint', tint=(.07, .105, .115))
    M['stencil'] = tex_mat('ex_stencil', 'ex_paint', tint=(.95, .95, .93))
    M['rust'] = tex_mat('ex_rust', 'ex_rust')
    M['steel'] = tex_mat('ex_steel', 'wpn_steel')
    M['brass'] = tex_mat('ex_brass', 'wpn_brass')
    M['rubber'] = tex_mat('ex_rubber', 'wpn_rubber')
    M['iron'] = tex_mat('ex_iron', 'wpn_metal')
    M['pale'] = tex_mat('ex_pale', 'wpn_paint', tint=(.86, .84, .79))
    M['glass'] = bl.mat('ex_glass', '#0d1113', metal=.0, rough=.18)
    M['lamp'] = bl.mat('ex_lamp', '#c9c3b2', metal=.1, rough=.12)
    M['tail'] = bl.mat('ex_tail', '#5d0d0a', metal=.0, rough=.2)
    M['crystal'] = bl.mat('ex_crystal', '#a8460a', rough=.07, emit='#ff7a14', strength=.75)   # (its facets catch the light: a lamp of a crystal, not a flat glow)
    M['amber'] = bl.mat('ex_amber', '#ffc070', rough=.3, emit='#ffa844', strength=10.0)


# ---------------------------------------------------------------- shape helpers
def obj(name, bm, m):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    if m is not None:
        me.materials.append(m)
    return o


def lathe(name, prof, m, seg=48, tile=TILE, phase=0.0, mats_by_z=None):
    """a turned part: prof = [(r, z), ...] from the bottom up, revolved about Z; UVs round it (u: metres round at the
    profile's widest / tile, v: metres along the profile / tile: a seam at the back). mats_by_z: [(z0, z1, material)]
    for the faces whose middle lies in a band (a painted band)."""
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new('UVMap')
    rmax = max(r for r, _ in prof)
    s = [0.0]
    for (r0, z0), (r1, z1) in zip(prof, prof[1:]):
        s.append(s[-1] + math.hypot(r1 - r0, z1 - z0))
    rings = []
    for (r, z) in prof:
        if r < 1e-9:                                                 # (on the axis: one point)
            v = bm.verts.new((0.0, 0.0, z))
            rings.append([v] * (seg + 1))
            continue
        ring = [bm.verts.new((r * math.cos(TAU * k / seg + phase), r * math.sin(TAU * k / seg + phase), z)) for k in range(seg)]
        ring.append(ring[0])
        rings.append(ring)
    slots = [m] + [mm for _, _, mm in (mats_by_z or []) if mm is not m]
    for i in range(len(prof) - 1):
        for k in range(seg):
            a, b_, c, d = rings[i][k], rings[i][k + 1], rings[i + 1][k + 1], rings[i + 1][k]
            if len({a, b_, c, d}) < 3:
                continue
            vs = [a, b_, c, d]
            uvs = [(k / seg, s[i]), ((k + 1) / seg, s[i]), ((k + 1) / seg, s[i + 1]), (k / seg, s[i + 1])]
            if a is b_:                                              # (the profile starts on the axis: a fan)
                vs, uvs = [a, c, d], [uvs[0], uvs[2], uvs[3]]
            elif c is d:                                             # (it ends on the axis: a fan)
                vs, uvs = [a, b_, c], [uvs[0], uvs[1], uvs[2]]
            try:
                f = bm.faces.new(vs)
            except ValueError:
                continue
            zc = (prof[i][1] + prof[i + 1][1]) / 2
            for lo, hi, mm in (mats_by_z or []):
                if lo <= zc <= hi:
                    f.material_index = slots.index(mm)
            for loop, (u_, v_) in zip(f.loops, uvs):
                loop[uv].uv = (u_ * TAU * rmax / tile, v_ / tile)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    o = obj(name, bm, None)
    for mm in slots:
        o.data.materials.append(mm)
    for p in o.data.polygons:
        p.use_smooth = True
    bl.autosmooth(o, 40)
    return o


def ring_prof(r_in, r_out, z0, z1, round_=.004):
    """a ring's section (a tube's wall, a band) as a lathe profile, its corners rounded"""
    e = round_
    return [(r_in + e, z0), (r_out - e, z0), (r_out, z0 + e), (r_out, z1 - e), (r_out - e, z1), (r_in + e, z1), (r_in, z1 - e), (r_in, z0 + e), (r_in + e, z0)]


def box(name, size, loc, m, bevel=.01, rot=(0, 0, 0), segs=3):
    o = bl.box(name, size, loc=loc, m=m, bevel=bevel, rot=rot, segs=segs)
    return o


def cube_uv(o, tile=TILE):
    bl.uv_box(o, tile)


def ucx(name, verts):
    """a convex collision hull (export_fbx.py names it UCX_<mesh>_NN for Unreal)"""
    bm = bmesh.new()
    for v in verts:
        bm.verts.new(v)
    bmesh.ops.convex_hull(bm, input=bm.verts)
    o = obj('UCX_' + name, bm, None)
    o.display_type = 'WIRE'
    o.hide_render = True
    return o


def cyl_pts(r, z0, z1, n=16, cx=0.0, cy=0.0):
    return [(cx + r * math.cos(TAU * k / n), cy + r * math.sin(TAU * k / n), z) for z in (z0, z1) for k in range(n)]


def dent(o, centre, radius, depth):
    """knocks a surface in round a point (a smooth dish, deepest in the middle)"""
    c = Vector(centre)
    for v in o.data.vertices:
        d = (v.co - c).length
        if d < radius:
            n = Vector((v.co.x, v.co.y, 0)).normalized() if abs(v.normal.z) < .7 else v.normal
            v.co -= n * depth * (math.cos(math.pi * d / radius) * .5 + .5)


def stencil(text, size, R, angle, z, m, name):
    """painted letters round a drum: Blender's own text, filled, laid on the curve of radius R (a hair proud of it),
    centred on `angle`, its foot at z"""
    cu = bpy.data.curves.new(name, 'FONT')
    cu.body = text
    cu.size = size
    cu.align_x = 'CENTER'
    cu.space_character = 1.12
    try:
        cu.fill_mode = 'BOTH'
    except TypeError:
        pass
    t = bpy.data.objects.new(name, cu)
    bpy.context.scene.collection.objects.link(t)
    bpy.context.view_layer.objects.active = t
    t.select_set(True)
    bpy.ops.object.convert(target='MESH')
    o = bpy.context.view_layer.objects.active
    o.select_set(False)
    for v in o.data.vertices:
        x, y = v.co.x, v.co.y
        a = angle + x / R
        v.co = Vector((R * math.cos(a), R * math.sin(a), z + y))
    o.data.materials.clear()
    o.data.materials.append(m)
    bm = bmesh.new(); bm.from_mesh(o.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    for f in bm.faces:                                               # (facing out of the drum)
        mid = f.calc_center_median()
        if f.normal.dot(Vector((mid.x, mid.y, 0))) < 0:
            f.normal_flip()
    uvl = bm.loops.layers.uv.new('UVMap')
    for f in bm.faces:
        for lp in f.loops:
            lp[uvl].uv = (lp.vert.co.z / TILE, math.atan2(lp.vert.co.y, lp.vert.co.x) * R / TILE)
    bm.to_mesh(o.data); bm.free()
    return o


# ---------------------------------------------------------------- the drum
def drum():
    R, H = .2865, .884
    hoop = lambda zc: [(R, zc - .018), (R + .004, zc - .009), (R + .0075, zc), (R + .004, zc + .009), (R, zc + .018)]
    prof = [(0, .012), (.20, .012), (.272, .012), (.279, .006), (.288, .0), (.294, .002), (.2975, .008), (.2975, .017),
            (.294, .023), (R, .030)] + hoop(.295) + hoop(.590) + \
           [(R, .852), (.292, .860), (.2965, .867), (.2975, .876), (.295, .882), (.289, .884), (.281, .880), (.276, .872),
            (.20, .872), (0, .872)]
    body = lathe('EX_drum', prof, M['red'], seg=64, mats_by_z=[(-1, .031, M['rust']), (.853, 1, M['rust'])])
    # knocked about: a dent low on one side where it was dropped, one high on the other, a crease on the top's rim
    dent(body, (R * math.cos(.6), R * math.sin(.6), .16), .14, .016)
    dent(body, (R * math.cos(3.4), R * math.sin(3.4), .66), .11, .010)
    dent(body, (R * math.cos(5.1), R * math.sin(5.1), .45), .07, .006)
    parts = [body]
    # the two bungs in the lid: a 2-inch with its hex boss, a 3/4-inch, each in a pressed flange
    for (x, y, r, tag) in ((.185, 0.0, .032, 'big'), (-.195, .02, .019, 'small')):
        fl = lathe(f'EX_drum_flange_{tag}', [(0, .872), (r + .012, .872), (r + .014, .876), (r + .010, .879), (r, .878), (0, .878)], M['red'], seg=24, tile=TILE)
        fl.location = (x, y, 0)
        cap = lathe(f'EX_drum_bung_{tag}', [(0, .876), (r, .876), (r + .002, .880), (r + .002, .889), (r - .002, .893), (0, .893)], M['steel'], seg=24, tile=WPN)
        cap.location = (x, y, 0)
        boss = lathe(f'EX_drum_boss_{tag}', [(0, .893), (r * .55, .893), (r * .55, .904), (r * .5, .907), (0, .907)], M['steel'], seg=6, tile=WPN)
        boss.location = (x, y, 0)
        parts += [fl, cap, boss]
    # FUEL round it twice, a stock number under one
    for i, a in enumerate((.3, .3 + math.pi)):
        parts.append(stencil('FUEL', .085, R + .0007, a, .40, M['stencil'], f'EX_drum_fuel_{i}'))
    parts.append(stencil('UN 1203  ·  200 L', .028, R + .0007, .3, .355, M['stencil'], 'EX_drum_code'))
    o = bl.join(parts, 'EX_drum')
    ucx('EX_drum', cyl_pts(.298, 0, H, 16)).parent = o
    return o


# ---------------------------------------------------------------- the gas bottle
def cylinder():
    R = .115
    prof = [(0, .045), (.05, .045), (.088, .052), (.106, .068), (.113, .088), (R, .11), (R, 1.17), (.113, 1.205),
            (.106, 1.24), (.092, 1.272), (.072, 1.298), (.050, 1.318), (.036, 1.328), (.034, 1.335)]
    body = lathe('EX_cylinder', prof + [(.034, 1.36), (0, 1.36)], M['blue'], seg=48, mats_by_z=[(1.18, 1.34, M['white'])])
    dent(body, (R * math.cos(2.2), R * math.sin(2.2), .7), .09, .006)
    parts = [body]
    foot = lathe('EX_cylinder_foot', ring_prof(.104, .121, 0.0, .058), M['steel'], seg=48, tile=WPN)
    neck = lathe('EX_cylinder_neck', ring_prof(.033, .047, 1.318, 1.352, .003), M['steel'], seg=32, tile=WPN)
    valve = lathe('EX_cylinder_valve', [(0, 1.352), (.021, 1.352), (.021, 1.42), (.016, 1.43), (.010, 1.44), (0, 1.44)], M['brass'], seg=20, tile=WPN)
    wheel = lathe('EX_cylinder_wheel', ring_prof(.020, .032, 1.438, 1.452, .003), M['steel'], seg=24, tile=WPN)
    parts += [foot, neck, valve, wheel]
    for k in range(3):                                               # the handwheel's spokes
        a = TAU * k / 3
        parts.append(box(f'EX_cylinder_spoke{k}', (.026, .004, .006), (math.cos(a) * .012, math.sin(a) * .012, 1.445), M['steel'], .001, rot=(0, 0, a)))
    out = bl.cyl('EX_cylinder_outlet', .009, .045, loc=(.036, 0, 1.395), m=M['brass'], verts=12, rot=(0, math.pi / 2, 0))
    nut = bl.cyl('EX_cylinder_nut', .013, .012, loc=(.058, 0, 1.395), m=M['brass'], verts=6, rot=(0, math.pi / 2, 0))
    parts += [out, nut]
    # the guard: a ring over the valve on three posts from the shoulder
    guard = lathe('EX_cylinder_guard', ring_prof(.058, .068, 1.47, 1.485, .003), M['steel'], seg=32, tile=WPN)
    parts.append(guard)
    for k in range(3):
        a = TAU * k / 3 + .5
        p0 = Vector((math.cos(a) * .075, math.sin(a) * .075, 1.29))
        p1 = Vector((math.cos(a) * .063, math.sin(a) * .063, 1.478))
        parts.append(bl.loft(f'EX_cylinder_post{k}', [[(p.x + .005 * math.cos(TAU * j / 8), p.y + .005 * math.sin(TAU * j / 8), p.z) for j in range(8)] for p in (p0, p1)], M['steel']))
    for p in parts[-3:]:
        cube_uv(p, WPN)
    for p in (out, nut):
        cube_uv(p, WPN)
    o = bl.join(parts, 'EX_cylinder')
    ucx('EX_cylinder', cyl_pts(.122, 0, 1.49, 12)).parent = o
    return o


# ---------------------------------------------------------------- the Sarketh cell
def claw_section(w, t, n=10):
    """a claw's section: a lens, wide across, thin through"""
    return [(w * math.cos(TAU * k / n), t * math.sin(TAU * k / n)) for k in range(n)]


def cell():
    parts = []
    # the base: a forged hexagon, a step, a pale ring with its lights
    base = lathe('EX_cell', [(0, 0), (.20, 0), (.212, .008), (.212, .04), (.205, .052), (.188, .058), (.17, .062), (0, .062)], M['iron'], seg=6, tile=WPN, phase=math.pi / 6)
    ring = lathe('EX_cell_ring', ring_prof(.10, .165, .062, .088, .005), M['pale'], seg=6, tile=WPN, phase=math.pi / 6)
    parts += [base, ring]
    for k in range(6):
        a = TAU * k / 6
        parts.append(box(f'EX_cell_light{k}', (.03, .008, .012), (math.cos(a) * .205, math.sin(a) * .205, .03), M['amber'], .002, rot=(0, 0, a + math.pi / 2)))
    # the crystal: six faces, a little uneven (it was grown), a point at the top
    rnd = random.Random(7)
    bm = bmesh.new()
    rows = []
    for z, r in ((.08, .055), (.12, .078), (.46, .074), (.56, .052), (.66, .016)):
        rows.append([bm.verts.new((math.cos(TAU * k / 6 + .2) * r * rnd.uniform(.93, 1.07), math.sin(TAU * k / 6 + .2) * r * rnd.uniform(.93, 1.07), z + rnd.uniform(-.006, .006))) for k in range(6)])
    tip = bm.verts.new((.004, -.003, .71))
    for r0, r1 in zip(rows, rows[1:]):
        for k in range(6):
            bm.faces.new((r0[k], r0[(k + 1) % 6], r1[(k + 1) % 6], r1[k]))
    for k in range(6):
        bm.faces.new((rows[-1][k], rows[-1][(k + 1) % 6], tip))
    bm.faces.new(rows[0][::-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    crystal = obj('EX_cell_crystal', bm, M['crystal'])
    cube_uv(crystal, WPN)
    parts.append(crystal)
    # the collar: forged iron round the crystal's waist, three tabs out to the claws
    collar = lathe('EX_cell_collar', ring_prof(.072, .094, .30, .345, .006), M['iron'], seg=6, tile=WPN, phase=.2)
    parts.append(collar)
    # three claws up from the base's rim, curling in to hold the crystal
    for k in range(3):
        a = TAU * k / 3 + .2 + math.pi / 6
        out = Vector((math.cos(a), math.sin(a), 0))
        side = Vector((-math.sin(a), math.cos(a), 0))
        path = []
        for i in range(9):
            t = i / 8
            r = .178 - .100 * t ** 1.3 + .022 * math.sin(math.pi * t)      # (out round the crystal, then in onto it)
            z = .07 + .42 * t + .02 * math.sin(math.pi * t)
            path.append(out * r + Vector((0, 0, z)))
        secs = []
        for i, p in enumerate(path):
            t = i / 8
            w, th = .046 * (1 - .7 * t) + .008, .018 * (1 - .55 * t) + .004
            tan = (path[min(i + 1, 8)] - path[max(i - 1, 0)]).normalized()
            nrm = out.cross(tan).normalized()                       # across the claw (its wide way)
            thick = tan.cross(nrm).normalized()
            secs.append([tuple(p + nrm * x * (1 if w > 0 else 1) + thick * y) for x, y in claw_section(w, th)])
        cl = bl.loft(f'EX_cell_claw{k}', secs, M['pale'])
        cube_uv(cl, WPN)
        parts.append(cl)
        tab = box(f'EX_cell_tab{k}', (.08, .022, .032), tuple(out * .128 + Vector((0, 0, .322))), M['iron'], .005, rot=(0, 0, a))
        parts.append(tab)
    for p in (base, ring, collar):
        pass
    o = bl.join(parts, 'EX_cell')
    ucx('EX_cell', cyl_pts(.215, 0, .72, 6)).parent = o
    return o


# ---------------------------------------------------------------- the car
def arch_profile(L=4.30, wheelbase=2.62, r_arch=.40, z_floor=.22, z_belt=.90):
    """the body's side outline (X along the car, Z up), cut round its two wheel arches"""
    xf, xr = wheelbase / 2, -wheelbase / 2
    pts = [(-L / 2, .46), (-L / 2 + .03, .34), (-L / 2 + .14, .26)]
    for xc in (xr, xf):
        pts.append((xc - r_arch - .10, z_floor))
        for i in range(13):
            a = math.pi - math.pi * i / 12
            pts.append((xc + r_arch * math.cos(a), .33 + r_arch * math.sin(a) * .98))
        pts.append((xc + r_arch + .10, z_floor))
    pts += [(L / 2 - .14, .27), (L / 2 - .02, .36), (L / 2, .50), (L / 2 - .02, .66), (L / 2 - .22, .76),
            (.95, z_belt - .04), (-1.30, z_belt), (-L / 2 + .25, z_belt - .01), (-L / 2 + .04, .80), (-L / 2, .62)]
    return pts


def car():
    W = .88                                                          # half the body's width at the sills
    rnd = random.Random(11)
    side = arch_profile()
    bm = bmesh.new()
    # the side outline extruded across the car; above the belt line drawn in (the body's curve in plan)
    left = [bm.verts.new((x, -W, z)) for x, z in side]
    right = [bm.verts.new((x, W, z)) for x, z in side]
    n = len(side)
    bm.faces.new(left[::-1])
    bm.faces.new(right)
    for i in range(n):
        bm.faces.new((left[i], left[(i + 1) % n], right[(i + 1) % n], right[i]))
    for v in bm.verts:
        z, x = v.co.z, v.co.x
        pinch = .06 * max(0.0, (z - .62) / .3) + .05 * max(0.0, abs(x) - 1.7) / .45
        v.co.y *= 1 - pinch
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    body = obj('EX_car', bm, M['car'])
    body.data.materials.append(M['rust'])
    bpy.context.view_layer.objects.active = body
    # a pressed body: the slab remeshed even (so a dent has surface to push in), its edges rounded by smoothing
    md = body.modifiers.new('remesh', 'REMESH'); md.mode = 'VOXEL'; md.voxel_size = .022
    bpy.ops.object.modifier_apply(modifier='remesh')
    md = body.modifiers.new('smooth', 'SMOOTH'); md.factor = .7; md.iterations = 8
    bpy.ops.object.modifier_apply(modifier='smooth')
    # the sills and the arches' lips rusted through
    for p in body.data.polygons:
        c = p.center
        if c.z < .30 or (c.z < .74 and any(abs(c.x - xc) < .52 and (c.x - xc) ** 2 + (c.z - .33) ** 2 < .52 ** 2 for xc in (-1.31, 1.31))):
            p.material_index = 1
    # knocked about: the front wing pushed in, a door creased, the rear quarter dented
    for centre, radius, depth in (((1.55, -W, .62), .36, .05), ((.1, W, .55), .40, .035), ((-1.6, -W, .7), .28, .03), ((1.9, .3, .8), .3, .03)):
        dent(body, centre, radius, depth)
    tris = sum(len(p.vertices) - 2 for p in body.data.polygons)
    md = body.modifiers.new('dec', 'DECIMATE'); md.ratio = min(1.0, 7600.0 / max(tris, 1))
    bpy.ops.object.modifier_apply(modifier='dec')
    for p in body.data.polygons:                                     # (again: the decimation made new faces)
        c = p.center
        p.material_index = 1 if (c.z < .30 or (c.z < .74 and any((c.x - xc) ** 2 + (c.z - .33) ** 2 < .50 ** 2 for xc in (-1.31, 1.31)))) else 0
    cube_uv(body, TILE)
    for p in body.data.polygons:
        p.use_smooth = True
    bl.autosmooth(body, 35)
    parts = [body]
    # the cabin: drawn in toward the roof, its windows inset (dark with dirt); the roof and the pillars painted
    bm = bmesh.new()
    lo = [(1.00, -.80, .90), (1.00, .80, .90), (-1.28, .80, .90), (-1.28, -.80, .90)]
    hi = [(.22, -.66, 1.40), (.22, .66, 1.40), (-.80, .66, 1.40), (-.80, -.66, 1.40)]
    vl = [bm.verts.new(p) for p in lo]
    vh = [bm.verts.new(p) for p in hi]
    bm.faces.new(vh)
    sides = [bm.faces.new((vl[i], vl[(i + 1) % 4], vh[(i + 1) % 4], vh[i])) for i in range(4)]
    bm.faces.new(vl[::-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    glass = bmesh.ops.inset_individual(bm, faces=sides, thickness=.065, depth=-.012)['faces']
    for f in bm.faces:
        f.material_index = 1 if f in sides else 0
    cab = obj('EX_car_cabin', bm, M['car'])
    cab.data.materials.append(M['glass'])
    md = cab.modifiers.new('bev', 'BEVEL'); md.width = .045; md.segments = 4; md.limit_method = 'ANGLE'; md.angle_limit = math.radians(30)
    bpy.context.view_layer.objects.active = cab
    bpy.ops.object.modifier_apply(modifier='bev')
    cube_uv(cab, TILE)
    bl.autosmooth(cab, 35)
    parts.append(cab)
    # bumpers, the grille, lamps, mirrors
    for x, s in ((2.17, 1), (-2.17, -1)):
        parts.append(box(f'EX_car_bumper{s}', (.12, 1.66, .16), (x, 0, .40), M['rubber'], .03))
    parts.append(box('EX_car_grille', (.04, .9, .16), (2.13, 0, .56), M['rubber'], .01))
    for y in (-.62, .62):                                            # (lamps behind their dirty glass)
        parts.append(box(f'EX_car_head{y}', (.05, .30, .11), (2.10, y, .61), M['glass'], .015))
        parts.append(box(f'EX_car_tail{y}', (.05, .26, .12), (-2.12, y, .70), M['glass'], .015))
        parts.append(box(f'EX_car_mirror{y}', (.12, .05, .08), (.94, y * 1.38, 1.0), M['car'], .015))
        parts.append(box(f'EX_car_mirrorarm{y}', (.05, .09, .025), (.96, y * 1.31, .96), M['car'], .006))
    # the wheels: tyres sagging on their rims, a hub
    for xc in (-1.31, 1.31):
        for s in (-1, 1):
            y = s * (W - .09)
            tyre = lathe(f'EX_car_tyre{xc}{s}', [(.20, -.105), (.29, -.11), (.322, -.09), (.332, -.05), (.332, .05), (.322, .09), (.29, .11), (.20, .105)], M['rubber'], seg=32, tile=WPN)
            rim = lathe(f'EX_car_rim{xc}{s}', [(0, .02), (.05, .03), (.17, .06), (.205, .07), (.205, .10), (.18, .105)], M['car'], seg=24, tile=WPN)   # (painted steel wheels)
            for w in (tyre, rim):
                w.rotation_euler = (math.pi / 2 * s, 0, 0)
                w.location = (xc, y, .32 - (.02 if rnd.random() < .5 else 0))
                bl.apply_all(w)
            parts += [tyre, rim]
    for p in parts[2:]:
        if not p.data.uv_layers:
            cube_uv(p, WPN)
    o = bl.join(parts, 'EX_car')
    ucx('EX_car_0', [(x, y * W, z) for x in (-2.2, 2.2) for y in (-1, 1) for z in (.2, .92)]).parent = o
    ucx('EX_car_1', [(x, y, z) for x, y, z in lo + hi]).parent = o
    return o


def look(out_dir):
    """a quick look (Cycles): each one alone, three quarters, under a plain studio"""
    import bakekit
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'; sc.cycles.samples = 48; sc.cycles.use_denoising = True
    bakekit._gpu(sc)
    sc.view_settings.view_transform = 'AgX'
    w = bpy.data.worlds.new('w'); sc.world = w; w.use_nodes = True
    w.node_tree.nodes['Background'].inputs[0].default_value = (.36, .38, .42, 1)
    w.node_tree.nodes['Background'].inputs[1].default_value = .55
    sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN')); sun.data.energy = 3.2
    sun.rotation_euler = (math.radians(50), 0, math.radians(35)); sc.collection.objects.link(sun)
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); sc.collection.objects.link(cam); sc.camera = cam
    objs = [o for o in sc.objects if o.type == 'MESH' and not o.name.startswith('UCX_')]
    for o in objs:
        o.hide_render = True
    sc.render.resolution_x, sc.render.resolution_y = 900, 900
    for o in objs:
        o.hide_render = False
        bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
        lo_ = Vector((min(p.x for p in bb), min(p.y for p in bb), min(p.z for p in bb)))
        hi_ = Vector((max(p.x for p in bb), max(p.y for p in bb), max(p.z for p in bb)))
        c = (lo_ + hi_) / 2
        size = (hi_ - lo_).length
        d = Vector((1.0, -1.25, .55)).normalized()
        cam.location = c + d * size * 1.55
        cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
        cam.data.lens = 50
        sc.render.filepath = os.path.join(out_dir, f'{o.name}.png')
        bpy.ops.render.render(write_still=True)
        o.hide_render = True


def main():
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    look_dir = next((x.split('=', 1)[1] for x in a if x.startswith('--look=')), None)
    bl.reset()
    mats()
    built = []
    for f in (drum, cylinder, cell, car):
        o = f()
        built.append(o)
        print('[explosives]', o.name, sum(len(p.vertices) - 2 for p in o.data.polygons), 'tris', flush=True)
    if look_dir:
        os.makedirs(look_dir, exist_ok=True)
        look(os.path.abspath(look_dir))
    bl.export('explosives.glb')
    # each alone too, for the gate (asset_check.py --class=prop)
    for o in built:
        hulls = [h for h in bpy.context.scene.objects if h.name.startswith('UCX_' + o.name)]
        bl.export(o.name.lower().replace('ex_', 'explosive_') + '.glb', selected=[o] + hulls)


if __name__ == '__main__':
    main()
