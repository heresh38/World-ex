"""Renders an HQ character in one outfit + hair (the way the game shows it) from several angles.

blender --background --python tools/blender/preview_char.py -- out.png player_female.glb outfit hair [Action frame]
"""
import bpy, sys, os, json, math
from mathutils import Vector
sys.path.insert(0, os.path.dirname(__file__))
import bl

a = sys.argv[sys.argv.index('--') + 1:]
out, glb, outfit, hair = a[:4]
action = a[4] if len(a) > 4 else 'IdleRelaxed'
frame = int(a[5]) if len(a) > 5 else 1
RES = int(os.environ.get('RES', '420'))
bl.reset()
bpy.ops.import_scene.gltf(filepath=os.path.join(bl.MODELS, glb))
arm = [o for o in bpy.context.scene.objects if o.type == 'ARMATURE'][0]
meta = json.loads(arm.get('worldex', '{}'))
hide = set(meta.get('outfits', {}).get(outfit, []))
for o in bpy.context.scene.objects:
    if o.type != 'MESH':
        continue
    n = o.name
    vis = True
    if n.startswith('O_'):
        vis = n == 'O_' + outfit
    elif n.startswith('H_'):
        vis = n == 'H_' + hair
    elif n.startswith('B_'):
        vis = n[2:] not in hide
    o.hide_render = not vis
arm.animation_data_create(); arm.animation_data.action = bpy.data.actions[action]
try:
    arm.animation_data.action_slot = arm.animation_data.action.slots[0]
except Exception:
    pass
sc = bpy.context.scene; sc.frame_set(frame)
sc.render.engine = 'CYCLES'; sc.cycles.samples = int(os.environ.get('SAMPLES', '24')); sc.cycles.device = 'CPU'
sc.render.resolution_x = RES; sc.render.resolution_y = int(RES * 1.6)
sc.view_settings.view_transform = 'AgX' if 'AgX' in [v.identifier for v in type(sc.view_settings).bl_rna.properties['view_transform'].enum_items] else 'Filmic'
w = bpy.data.worlds.new('w'); sc.world = w
bg = w.node_tree.nodes['Background']; bg.inputs[0].default_value = (.08, .1, .13, 1); bg.inputs[1].default_value = .9
for loc, e, col in (((2.5, -3.5, 3.5), 900, (1, .96, .9)), ((-3, -1, 2.5), 350, (.8, .9, 1)), ((0, 3, 3), 500, (.6, .8, 1))):
    L = bpy.data.objects.new('l', bpy.data.lights.new('l', 'AREA')); L.data.energy = e; L.data.size = 2; L.data.color = col
    L.location = loc; L.rotation_euler = (Vector((0, 0, 1)) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler(); sc.collection.objects.link(L)
H = 1.83 if 'male' in glb and 'female' not in glb else 1.58
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); sc.collection.objects.link(cam); sc.camera = cam
views = [('front', Vector((0, -1, .05)), H * .52, 1.0, 50), ('q', Vector((.7, -1, .1)), H * .52, 1.0, 50), ('back', Vector((.2, 1, .1)), H * .52, 1.0, 50),
         ('face', Vector((.25, -1, .02)), H * .91, .2, 85)]
tiles = []
for i, (n, d, cz, dist, lens) in enumerate(views):
    cam.data.lens = lens
    target = Vector((0, 0, cz))
    cam.location = target + d.normalized() * (H * 2.2 * dist if n != 'face' else .9)
    cam.rotation_euler = (target - cam.location).to_track_quat('-Z', 'Y').to_euler()
    p = os.path.join(os.path.dirname(out), '_c%d.png' % i)
    sc.render.filepath = p; bpy.ops.render.render(write_still=True); tiles.append(p)
import numpy as np
imgs = [bpy.data.images.load(p) for p in tiles]
Wd, Ht = imgs[0].size
sheet = np.zeros((Ht, Wd * len(imgs), 4), dtype=np.float32)
for i, im in enumerate(imgs):
    sheet[:, i * Wd:(i + 1) * Wd] = np.array(im.pixels[:], dtype=np.float32).reshape(Ht, Wd, 4)
im = bpy.data.images.new('sheet', Wd * len(imgs), Ht); im.pixels = sheet.ravel()
im.filepath_raw = out; im.file_format = 'PNG'; im.save()
for p in tiles:
    os.remove(p)
print('preview ->', out)
