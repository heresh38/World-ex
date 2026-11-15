"""The Sarketh weapons laid out as the design sheet shows them: each from its left flank (muzzle to the left), in the
sheet's dark studio light, one PNG per weapon plus a three-quarter view.

blender -b -P tools/blender/skr/gunsheet.py -- <outdir> gun_skr_rifle gun_skr_sniper ...
"""
import math
import os
import sys
import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import bl        # noqa: E402
import bakekit   # noqa: E402

args = sys.argv[sys.argv.index('--') + 1:]
out, names = args[0], args[1:]
os.makedirs(out, exist_ok=True)
for nm in names:
    bl.reset()
    bpy.ops.import_scene.gltf(filepath=os.path.join(bl.MODELS, nm + '.glb'))
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'; bakekit._gpu(sc); sc.cycles.samples = 96; sc.cycles.use_denoising = True
    sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = 'AgX - Medium High Contrast'
    w = bpy.data.worlds.new('w'); sc.world = w; w.use_nodes = True
    w.node_tree.nodes['Background'].inputs['Color'].default_value = (.035, .035, .04, 1)
    pts = [o.matrix_world @ Vector(c) for o in sc.objects if o.type == 'MESH' for c in o.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    c = (lo + hi) / 2; size = max((hi - lo).y, (hi - lo).z * 1.8, .12)

    def area(n, loc, power, s, col):
        ld = bpy.data.lights.new(n, 'AREA'); ld.energy = power; ld.size = s; ld.color = col
        ob = bpy.data.objects.new(n, ld); sc.collection.objects.link(ob); ob.location = c + Vector(loc)
        ob.rotation_euler = (c - ob.location).to_track_quat('-Z', 'Y').to_euler()
    k = size
    area('key', (1.4 * k, -.6 * k, 1.2 * k), 120 * k * k, .8 * k, (1, .96, .9))
    area('rim', (-1.2 * k, .8 * k, .9 * k), 160 * k * k, .5 * k, (.85, .9, 1))
    area('top', (.2 * k, 0, 1.6 * k), 60 * k * k, 1.0 * k, (1, 1, 1))
    area('under', (.8 * k, 0, -1.0 * k), 25 * k * k, 1.0 * k, (.8, .85, 1))
    cd = bpy.data.cameras.new('c'); cam = bpy.data.objects.new('c', cd); sc.collection.objects.link(cam); sc.camera = cam
    for view, d, res in (('side', (1, 0, 0), (1600, 700)), ('quarter', (1, -.8, .45), (1400, 900))):
        sc.render.resolution_x, sc.render.resolution_y = res
        dv = Vector(d).normalized()
        if view == 'side':
            cd.type = 'ORTHO'; cd.ortho_scale = size * 1.12
        else:
            cd.type = 'PERSP'; cd.lens = 70
        cam.location = c + dv * size * 2.6
        cam.rotation_euler = (c - cam.location).to_track_quat('-Z', 'Y').to_euler()
        sc.render.filepath = os.path.join(out, f'{nm}_{view}.png')
        bpy.ops.render.render(write_still=True)
    print('[gunsheet]', nm, flush=True)
