"""Inventory icons rendered from our own models with Cycles (transparent background, studio lighting).

  guns:   assets/models/gun_<x>.glb -> <out>/guns/icon_gun_<x>.png    side view, muzzle to the right (768 x 384)

blender --background --python tools/blender/icons.py -- <out dir> [guns] [--only=a,b]
"""
import bpy, sys, os, math, json, glob
from mathutils import Vector, Euler
sys.path.insert(0, os.path.dirname(__file__))
import bl

args = sys.argv[sys.argv.index('--') + 1:]
OUT = os.path.abspath(args[0])
DO_GUNS = True
ONLY = next((a.split('=', 1)[1].split(',') for a in args if a.startswith('--only=')), None)
SAMPLES = int(os.environ.get('ICON_SAMPLES', '48'))


def studio(sc):
    sc.render.engine = 'CYCLES'
    sc.cycles.samples = SAMPLES
    sc.cycles.use_denoising = True
    sc.cycles.device = 'CPU'
    sc.render.film_transparent = True
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_mode = 'RGBA'
    try:
        sc.view_settings.view_transform = 'AgX'
        sc.view_settings.look = 'AgX - Medium High Contrast'
    except Exception:
        sc.view_settings.view_transform = 'Filmic'
    w = bpy.data.worlds.new('w'); sc.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes['Background']
    bg.inputs[0].default_value = (.32, .36, .44, 1); bg.inputs[1].default_value = .35

    def light(name, energy, loc, color, size):
        L = bpy.data.lights.new(name, 'AREA'); L.energy = energy; L.color = color; L.size = size
        o = bpy.data.objects.new(name, L); o.location = loc
        o.rotation_euler = (Vector((0, 0, 0)) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
        sc.collection.objects.link(o)
    light('key', 260, (-1.4, -1.0, 1.6), (1, .97, .92), 1.6)
    light('fill', 90, (-1.2, 1.6, .4), (.7, .8, 1), 2.4)
    light('rim', 320, (1.4, .2, 1.2), (.55, .78, 1), 1.0)       # cyan-blue rim from behind (the world's light)
    light('under', 40, (-.6, 0, -1.2), (.6, .5, 1), 2.0)        # a faint violet kick from below


def frame(cam, objs, view_dir, up=(0, 0, 1), margin=1.08, ortho=True, left_only=False):
    """Orthographic camera along view_dir fitting the objects' world bounds (left_only: just the +X half, e.g. one
    of a pair of gloves)."""
    if left_only:
        pts = [o.matrix_world @ v.co for o in objs for v in o.data.vertices]
        pts = [p for p in pts if p.x > 0.02]
    else:
        pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    c = (lo + hi) / 2
    d = Vector(view_dir).normalized()
    cam.location = c - d * 10
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    cam.data.type = 'ORTHO'
    # extent across the view
    right = d.cross(Vector(up)).normalized(); upv = right.cross(d).normalized()
    sx = max(abs((p - c).dot(right)) for p in pts) * 2
    sy = max(abs((p - c).dot(upv)) for p in pts) * 2
    sc = bpy.context.scene
    aspect = sc.render.resolution_x / sc.render.resolution_y
    cam.data.ortho_scale = max(sx, sy * aspect) * margin
    cam.data.clip_end = 40


def render(path):
    sc = bpy.context.scene
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print('[icons]', os.path.basename(path), flush=True)


def guns():
    os.makedirs(os.path.join(OUT, 'guns'), exist_ok=True)
    for path in sorted(glob.glob(os.path.join(bl.MODELS, 'gun_*.glb'))):
        stem = os.path.splitext(os.path.basename(path))[0]
        if stem in ('gun_attach',) or (ONLY and stem not in ONLY):
            continue
        bl.reset()
        sc = bpy.context.scene
        sc.render.resolution_x, sc.render.resolution_y = 768, 384
        studio(sc)
        bpy.ops.import_scene.gltf(filepath=path)
        objs = []
        for o in sc.objects:
            n = o.name.split('.')[0]
            if o.type == 'MESH':
                hide = n.startswith('x_') or n in ('spare',) or any(p.name.split('.')[0].startswith('x_') for p in [o.parent] if p)
                o.hide_render = hide
                if not hide:
                    objs.append(o)
        if not objs:
            continue
        cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); sc.collection.objects.link(cam); sc.camera = cam
        # the gun's right side (barrel along -Y, right = -X): looking +X puts the muzzle on the right; a touch from above
        frame(cam, objs, (1, 0, -.12), margin=1.06)
        render(os.path.join(OUT, 'guns', 'icon_' + stem + '.png'))


if DO_GUNS:
    guns()
