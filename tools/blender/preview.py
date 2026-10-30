"""Renders contact-sheet previews of exported GLBs with Cycles (for checking models/poses headless).

blender --background --python tools/blender/preview.py -- out.png model.glb[:Action[:frame]] ...
"""
import bpy, sys, os, math
from mathutils import Vector
sys.path.insert(0, os.path.dirname(__file__))
import bl

args = sys.argv[sys.argv.index('--') + 1:]
out, items = args[0], args[1:]
tiles = []
for i, it in enumerate(items):
    parts = it.split(':')
    path = parts[0]; action = parts[1] if len(parts) > 1 else None; frame = int(parts[2]) if len(parts) > 2 else 1
    view = parts[3] if len(parts) > 3 else 'q'
    bl.reset()
    bpy.ops.import_scene.gltf(filepath=path if os.path.isabs(path) else os.path.join(bl.MODELS, path))
    objs = [o for o in bpy.context.scene.objects]
    if action:
        for o in objs:
            if o.type == 'ARMATURE':
                o.animation_data_create(); o.animation_data.action = bpy.data.actions[action]
                try:
                    o.animation_data.action_slot = o.animation_data.action.slots[0]
                except Exception:
                    pass
    sc = bpy.context.scene
    sc.frame_set(frame)
    bpy.context.view_layer.update()
    lo = Vector((1e9,) * 3); hi = Vector((-1e9,) * 3)
    dg = bpy.context.evaluated_depsgraph_get()
    for o in objs:
        if o.type == 'MESH':
            oe = o.evaluated_get(dg)
            for v in oe.to_mesh().vertices:
                w = o.matrix_world @ v.co
                lo = Vector(map(min, lo, w)); hi = Vector(map(max, hi, w))
    c = (lo + hi) / 2; r = max((hi - lo).length / 2, .1)
    sc.render.engine = 'CYCLES'; sc.cycles.samples = 12; sc.cycles.device = 'CPU'
    sc.render.resolution_x = sc.render.resolution_y = 360
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); sc.collection.objects.link(cam); sc.camera = cam
    dirs = {'q': Vector((1.0, -1.6, .7)), 'f': Vector((0, -1, .15)), 's': Vector((1, 0, .1)), 't': Vector((0.01, -.01, 1)),
            'b': Vector((-.6, 1.4, .5))}
    d = dirs.get(view, dirs['q']).normalized()
    cam.data.lens = 50
    cam.location = c + d * r * 3.1
    cam.rotation_euler = (c - cam.location).to_track_quat('-Z', 'Y').to_euler()
    for loc, e in (((3, -4, 6), 900), ((-4, 2, 3), 300)):
        L = bpy.data.objects.new('l', bpy.data.lights.new('l', 'POINT')); L.data.energy = e * r * r
        L.location = c + Vector(loc) * r; sc.collection.objects.link(L)
    w = bpy.data.worlds.new('w'); sc.world = w; w.color = (.15, .16, .2)
    try:
        w.node_tree.nodes['Background'].inputs[0].default_value = (.15, .16, .2, 1)
    except Exception:
        pass
    p = os.path.join(os.path.dirname(out), '_tile%d.png' % i)
    sc.render.filepath = p; bpy.ops.render.render(write_still=True)
    tiles.append(p)
# contact sheet
imgs = [bpy.data.images.load(p) for p in tiles]
n = len(imgs); W = 360
import numpy as np
sheet = np.zeros((W, W * n, 4), dtype=np.float32)
for i, im in enumerate(imgs):
    px = np.array(im.pixels[:], dtype=np.float32).reshape(W, W, 4)
    sheet[:, i * W:(i + 1) * W] = px
im = bpy.data.images.new('sheet', W * n, W)
im.pixels = sheet.ravel()
im.filepath_raw = out; im.file_format = 'PNG'; im.save()
for p in tiles:
    os.remove(p)
print('preview ->', out)
