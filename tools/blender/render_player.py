"""Renders a player GLB wearing an outfit (EEVEE studio lighting): full body front / three-quarter / back and a head
close-up, side by side in one sheet. For checking players.py / wardrobe.py work.

blender --background --python tools/blender/render_player.py -- out.png player_male.glb [slot=item ...] [--pose=Idle:1]

Without slot=item arguments the GLB's default outfit (armature extra `worldex` defaults) is worn. Body regions the
worn items hide are hidden, like the game does.
"""
import bpy, sys, os, json, math
from mathutils import Vector, Euler
sys.path.insert(0, os.path.dirname(__file__))
import bl

args = sys.argv[sys.argv.index('--') + 1:]
out, glb = args[0], args[1]
pose = next((a.split('=', 1)[1] for a in args if a.startswith('--pose=')), 'Idle:1')
over = dict(a.split('=', 1) for a in args[2:] if '=' in a and not a.startswith('--'))
RES = int(os.environ.get('RES', '700'))

bl.reset()
bpy.ops.import_scene.gltf(filepath=glb if os.path.isabs(glb) else os.path.join(bl.MODELS, glb))
arm = next(o for o in bpy.context.scene.objects if o.type == 'ARMATURE')
meta = json.loads(arm.get('worldex', '{}')) if arm.get('worldex') else {}
wear = dict(meta.get('defaults', {}))
wear.update(over)
items = meta.get('wardrobe', {})
hidden = set()
for slot, item in wear.items():
    info = items.get(slot, {}).get(item, {}) if isinstance(items.get(slot), dict) else {}
    hidden.update(info.get('hide', []))
for o in list(bpy.context.scene.objects):
    if o.type != 'MESH':
        continue
    n = o.name.split('.')[0]
    if n.startswith('C_'):
        slot, item = n[2:].split('__', 1) if '__' in n else (n[2:], '')
        if wear.get(slot) != item:
            o.hide_render = True
    elif n.startswith('B_') and n[2:] in hidden:
        o.hide_render = True
    if n.endswith('_npc') or n.startswith('Icosphere'):
        o.hide_render = True

# pose
action, frame = (pose.split(':') + ['1'])[:2]
if action in bpy.data.actions:
    arm.animation_data_create()
    arm.animation_data.action = bpy.data.actions[action]
    try:
        arm.animation_data.action_slot = arm.animation_data.action.slots[0]
    except Exception:
        pass
bpy.context.scene.frame_set(int(frame))

sc = bpy.context.scene
engines = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items]
sc.render.engine = 'BLENDER_EEVEE_NEXT' if 'BLENDER_EEVEE_NEXT' in engines else 'BLENDER_EEVEE'
sc.render.resolution_x = int(RES * .62)
sc.render.resolution_y = RES
sc.render.film_transparent = False
sc.view_settings.view_transform = 'AgX' if 'AgX' in [v.identifier for v in bpy.types.ColorManagedViewSettings.bl_rna.properties['view_transform'].enum_items] else 'Filmic'
w = bpy.data.worlds.new('w'); sc.world = w
w.use_nodes = True
w.node_tree.nodes['Background'].inputs[0].default_value = (0.05, 0.06, 0.08, 1)
w.node_tree.nodes['Background'].inputs[1].default_value = 1.0


def light(name, kind, energy, loc, rot, color=(1, 1, 1), size=1.0):
    L = bpy.data.lights.new(name, kind); L.energy = energy; L.color = color
    if kind == 'AREA':
        L.size = size
    o = bpy.data.objects.new(name, L); o.location = loc; o.rotation_euler = Euler([math.radians(a) for a in rot])
    sc.collection.objects.link(o)


light('key', 'AREA', 320, (1.6, -2.4, 2.6), (55, 0, 35), (1, .96, .9), 2.0)
light('fill', 'AREA', 110, (-2.4, -1.6, 1.4), (70, 0, -55), (.75, .82, 1), 3.0)
light('rim', 'AREA', 380, (0.4, 2.6, 2.2), (-60, 0, 175), (.55, .75, 1), 1.5)

# the game tints skin, hair and brows at runtime (white in the GLB): preview with a default look
TINTS = {'skin': (.78, .56, .45), 'hair': (.05, .036, .028), 'brow': (.05, .036, .028)}
for mt in bpy.data.materials:
    key = next((k for k in TINTS if mt.name == k or mt.name.startswith(k + '__') or mt.name.startswith(k + '.')), None)
    if key and mt.node_tree:
        b = mt.node_tree.nodes.get('Principled BSDF')
        src = b.inputs['Base Color'].links[0].from_socket if b and b.inputs['Base Color'].links else None
        mul = mt.node_tree.nodes.new('ShaderNodeMix'); mul.data_type = 'RGBA'; mul.blend_type = 'MULTIPLY'
        mul.inputs[0].default_value = 1.0
        mul.inputs[7].default_value = (*TINTS[key], 1)
        if src is not None:
            mt.node_tree.links.new(src, mul.inputs[6])
        else:
            mul.inputs[6].default_value = b.inputs['Base Color'].default_value
        mt.node_tree.links.new(mul.outputs[2], b.inputs['Base Color'])
floor = bpy.data.meshes.new('floor')
floor.from_pydata([(-5, -5, 0), (5, -5, 0), (5, 5, 0), (-5, 5, 0)], [], [(0, 1, 2, 3)])
fo = bpy.data.objects.new('floor', floor); sc.collection.objects.link(fo)
fm = bpy.data.materials.new('floor'); fm.use_nodes = True
fm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (.06, .065, .075, 1)
fm.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = .5
floor.materials.append(fm)

cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); sc.collection.objects.link(cam); sc.camera = cam
shots = [('front', 0, 4.2, 0.95, 1.0, 50), ('three', 35, 4.2, 0.95, 1.0, 50), ('back', 180, 4.2, 0.95, 1.0, 50),
         ('face', 15, 0.9, 1.68, 1.62, 70)]
tiles = []
base = os.path.splitext(out)[0]
for tag, yaw, dist, aim_z, eye_z, lens in shots:
    cam.data.lens = lens
    a = math.radians(yaw)
    cam.location = Vector((math.sin(a) * dist, -math.cos(a) * dist, eye_z if tag == 'face' else 1.0))
    target = Vector((0, 0, aim_z))
    cam.rotation_euler = (target - cam.location).to_track_quat('-Z', 'Y').to_euler()
    path = f'{base}_{tag}.png'
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    tiles.append(path)

# one sheet
imgs = [bpy.data.images.load(p) for p in tiles]
W = sum(i.size[0] for i in imgs); H = max(i.size[1] for i in imgs)
sheet = bpy.data.images.new('sheet', W, H)
import numpy as np
buf = np.zeros((H, W, 4), np.float32)
x = 0
for i in imgs:
    px = np.array(i.pixels[:], np.float32).reshape(i.size[1], i.size[0], 4)
    buf[:i.size[1], x:x + i.size[0]] = px
    x += i.size[0]
sheet.pixels = buf.ravel()
sheet.filepath_raw = out
sheet.file_format = 'PNG'
sheet.save()
print('[render_player] wrote', out)
