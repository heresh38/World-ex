"""Shared helpers for the headless Blender asset scripts.

Every script in this folder is run as:  blender --background --python tools/blender/<script>.py
Blender is Z-up with -Y forward; the glTF exporter converts to Y-up so models face +Z in three.js.
"""
import bpy, bmesh, math, os, sys
from mathutils import Vector, Matrix, Euler

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
MODELS = os.path.join(ROOT, 'assets', 'models')
TEXTURES = os.path.join(ROOT, 'assets', 'textures')
os.makedirs(MODELS, exist_ok=True)
os.makedirs(TEXTURES, exist_ok=True)


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    _MATS.clear()


def coll(name):
    c = bpy.data.collections.get(name)
    if not c:
        c = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(c)
    return c


# ---------------------------------------------------------------- materials
_MATS = {}


def hexrgb(h):
    h = h.lstrip('#')
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    # sRGB -> linear
    return tuple(((x + .055) / 1.055) ** 2.4 if x > .04045 else x / 12.92 for x in c)


def mat(name, color='#808080', metal=0.0, rough=0.5, emit=None, strength=1.0, coat=0.0, alpha=1.0,
        image=None, normal=None, uv_scale=1.0):
    """Principled material that round-trips cleanly through glTF."""
    if name in _MATS:
        return _MATS[name]
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    b = nt.nodes.get('Principled BSDF')
    b.inputs['Base Color'].default_value = (*hexrgb(color), 1)
    b.inputs['Metallic'].default_value = metal
    b.inputs['Roughness'].default_value = rough
    if coat:
        b.inputs['Coat Weight'].default_value = coat
        b.inputs['Coat Roughness'].default_value = .03
    if emit:
        b.inputs['Emission Color'].default_value = (*hexrgb(emit), 1)
        b.inputs['Emission Strength'].default_value = strength
    if alpha < 1:
        b.inputs['Alpha'].default_value = alpha
        try:
            m.surface_render_method = 'BLENDED'
        except Exception:
            pass
    if image:
        tn = nt.nodes.new('ShaderNodeTexImage')
        tn.image = bpy.data.images.load(os.path.join(TEXTURES, image))
        if uv_scale != 1.0:
            mp = nt.nodes.new('ShaderNodeMapping'); uv = nt.nodes.new('ShaderNodeTexCoord')
            mp.inputs['Scale'].default_value = (uv_scale, uv_scale, 1)
            nt.links.new(uv.outputs['UV'], mp.inputs['Vector']); nt.links.new(mp.outputs['Vector'], tn.inputs['Vector'])
        mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'; mix.blend_type = 'MULTIPLY'
        mix.inputs['Factor'].default_value = 1.0
        mix.inputs[7].default_value = (*hexrgb(color), 1)
        nt.links.new(tn.outputs['Color'], mix.inputs[6])
        nt.links.new(mix.outputs[2], b.inputs['Base Color'])
        if normal:
            nn = nt.nodes.new('ShaderNodeTexImage'); nn.image = bpy.data.images.load(os.path.join(TEXTURES, normal))
            nn.image.colorspace_settings.name = 'Non-Color'
            if uv_scale != 1.0:
                nt.links.new(mp.outputs['Vector'], nn.inputs['Vector'])
            nm = nt.nodes.new('ShaderNodeNormalMap')
            nt.links.new(nn.outputs['Color'], nm.inputs['Color']); nt.links.new(nm.outputs['Normal'], b.inputs['Normal'])
    _MATS[name] = m
    return m


# Shared art-direction palette (bone-white ceramic, gunmetal, brass, neon) -------------
def palette():
    return dict(
        bone=mat('bone', '#e8e2d4', 0.0, .38),
        gunmetal=mat('gunmetal', '#3a3f47', .85, .35),
        dark=mat('darkmetal', '#1c1f24', .8, .45),
        brass=mat('brass', '#c79a45', 1.0, .28),
        rubber=mat('rubber', '#141516', 0.0, .85),
        cyan=mat('neon_cyan', '#1ad8ff', 0, .4, emit='#1ad8ff', strength=6),
        magenta=mat('neon_magenta', '#ff2fa8', 0, .4, emit='#ff2fa8', strength=6),
        amber=mat('neon_amber', '#ffae2f', 0, .4, emit='#ffae2f', strength=6),
        red=mat('neon_red', '#ff3326', 0, .4, emit='#ff3326', strength=6),
        glass=mat('glass', '#9fc6d8', 0.0, .05, alpha=.25),
        steel=mat('steel', '#8a9099', .9, .3),
    )


# ---------------------------------------------------------------- primitives
def _finish(o, m, name, bevel=0.0, segs=2, smooth=False, parent=None):
    o.name = name
    if m is not None:
        o.data.materials.clear(); o.data.materials.append(m)
    bpy.context.view_layer.objects.active = o
    o.select_set(True)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel > 0:
        md = o.modifiers.new('bv', 'BEVEL'); md.width = bevel; md.segments = segs; md.limit_method = 'ANGLE'
        bpy.ops.object.modifier_apply(modifier=md.name)
    if smooth:
        bpy.ops.object.shade_smooth()
    else:
        bpy.ops.object.shade_flat()
    if bevel > 0 and segs > 1:
        try:
            bpy.ops.object.shade_auto_smooth(angle=math.radians(35))
        except Exception:
            pass
    o.select_set(False)
    if parent:
        o.parent = parent
    return o


def box(name, size, loc=(0, 0, 0), m=None, bevel=0.0, rot=(0, 0, 0), segs=2, parent=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
    o = bpy.context.object
    o.scale = size
    return _finish(o, m, name, bevel, segs, parent=parent)


def cyl(name, r, h, loc=(0, 0, 0), m=None, verts=16, rot=(0, 0, 0), r2=None, bevel=0.0, smooth=True, parent=None):
    if r2 is None:
        bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=h, location=loc, rotation=rot)
    else:
        bpy.ops.mesh.primitive_cone_add(vertices=verts, radius1=r, radius2=r2, depth=h, location=loc, rotation=rot)
    o = bpy.context.object
    o = _finish(o, m, name, bevel, 1, smooth=False, parent=parent)
    if smooth:
        autosmooth(o)
    return o


def sphere(name, r, loc=(0, 0, 0), m=None, seg=16, rings=10, scale=(1, 1, 1), rot=(0, 0, 0), parent=None):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=seg, ring_count=rings, radius=r, location=loc, rotation=rot)
    o = bpy.context.object
    o.scale = scale
    o = _finish(o, m, name, smooth=True, parent=parent)
    return o


def torus(name, R, r, loc=(0, 0, 0), m=None, rot=(0, 0, 0), maj=24, mn=8, parent=None):
    bpy.ops.mesh.primitive_torus_add(major_radius=R, minor_radius=r, location=loc, rotation=rot,
                                     major_segments=maj, minor_segments=mn)
    o = bpy.context.object
    return _finish(o, m, name, smooth=True, parent=parent)


def autosmooth(o, ang=35):
    bpy.context.view_layer.objects.active = o
    o.select_set(True)
    bpy.ops.object.shade_smooth()
    try:
        bpy.ops.object.shade_auto_smooth(angle=math.radians(ang))
    except Exception:
        pass
    o.select_set(False)


def mesh_from(name, verts, faces, m=None, loc=(0, 0, 0), smooth=False, parent=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata([Vector(v) for v in verts], [], faces)
    me.validate(); me.update()
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    o.location = loc
    if m:
        me.materials.append(m)
    if smooth:
        autosmooth(o)
    if parent:
        o.parent = parent
    return o


def loft(name, sections, m=None, cap=True, smooth=True):
    """sections: list of rings (each a list of (x,y,z)) with equal vertex counts -> closed tube."""
    n = len(sections[0])
    verts = [v for s in sections for v in s]
    faces = []
    for i in range(len(sections) - 1):
        for j in range(n):
            a = i * n + j; b = i * n + (j + 1) % n
            faces.append((a, b, b + n, a + n))
    if cap:
        faces.append(tuple(range(n))[::-1])
        faces.append(tuple(range((len(sections) - 1) * n, len(sections) * n)))
    o = mesh_from(name, verts, faces, m)
    bpy.context.view_layer.objects.active = o
    o.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.normals_make_consistent(inside=False); bpy.ops.object.mode_set(mode='OBJECT')
    o.select_set(False)
    if smooth:
        autosmooth(o, 40)
    return o


def empty(name, loc=(0, 0, 0), parent=None, rot=(0, 0, 0)):
    o = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(o)
    o.location = loc; o.rotation_euler = rot
    o.empty_display_size = .2
    if parent:
        o.parent = parent
    return o


def mirror_x(o):
    """Duplicate an object mirrored across X (Blender X); returns the copy."""
    c = o.copy(); c.data = o.data.copy()
    bpy.context.scene.collection.objects.link(c)
    c.name = o.name.replace('.L', '.R').replace('_L', '_R') if ('.L' in o.name or '_L' in o.name) else o.name + '_m'
    c.location.x = -c.location.x
    c.scale.x = -c.scale.x
    bpy.context.view_layer.objects.active = c; c.select_set(True)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.flip_normals(); bpy.ops.object.mode_set(mode='OBJECT')
    c.select_set(False)
    c.parent = o.parent
    return c


def join(objs, name):
    objs = [o for o in objs if o and o.type == 'MESH']
    if not objs:
        return None
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    o = bpy.context.object
    o.name = name
    o.select_set(False)
    return o


def apply_all(o):
    bpy.context.view_layer.objects.active = o
    o.select_set(True)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    o.select_set(False)


def uv_box(o, scale=1.0):
    """World-scale cube projection so tiling textures keep a constant texel density."""
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = o; o.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.cube_project(cube_size=scale, scale_to_bounds=False, correct_aspect=False)
    bpy.ops.object.mode_set(mode='OBJECT'); o.select_set(False)


def decimate(o, ratio):
    md = o.modifiers.new('dec', 'DECIMATE'); md.ratio = ratio
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.modifier_apply(modifier=md.name)


def tri_count():
    t = 0
    for o in bpy.context.scene.objects:
        if o.type == 'MESH':
            t += sum(len(p.vertices) - 2 for p in o.data.polygons)
    return t


def export(fname, animations=False, selected=None):
    path = os.path.join(MODELS, fname)
    kw = dict(filepath=path, export_format='GLB', export_apply=True, export_yup=True,
              export_extras=True, export_image_format='JPEG', export_jpeg_quality=85,
              export_animations=animations, export_lights=False, export_cameras=False)
    if animations:
        kw.update(export_animation_mode='ACTIONS', export_force_sampling=True, export_optimize_animation_size=True)
    if selected is not None:
        bpy.ops.object.select_all(action='DESELECT')
        for o in selected:
            o.select_set(True)
        kw['use_selection'] = True
    try:
        bpy.ops.export_scene.gltf(**kw)
    except TypeError:
        for k in ('export_jpeg_quality', 'export_optimize_animation_size'):
            kw.pop(k, None)
        bpy.ops.export_scene.gltf(**kw)
    print('[export] %s  %d tris  %.0f KB' % (fname, tri_count(), os.path.getsize(path) / 1024))
    return path


def rng(seed):
    import random
    return random.Random(seed)
