"""Contact sheet of the Void Requiem guns as the game dresses them (Requiem Black body, the Legendary violet glow),
rendered with Cycles on a dark ground.

blender --background --python tools/blender/requiem_sheet.py -- out.png gun_vr_rifle:s gun_vr_rifle:q[:zoom] ...
views: s side (left flank, orthographic), r right flank, q front quarter, b rear quarter, t top, fp first person
env: RES (tile width, default 960), SAMPLES (default 48), COLS (tiles per row, default 2)
"""
import bpy, sys, os, math
import numpy as np
from mathutils import Vector
sys.path.insert(0, os.path.dirname(__file__))
import bl

args = sys.argv[sys.argv.index('--') + 1:]
RES = int(os.environ.get('RES', '960')); SAMPLES = int(os.environ.get('SAMPLES', '48')); COLS = int(os.environ.get('COLS', '2'))
H = int(RES * 9 / 16)
out, items = args[0], args[1:]
VIOLET = (.36, .09, 1.0)
BODY = bl.hexrgb('#17161c')


def dress():
    for m in bpy.data.materials:
        nt = m.node_tree
        b = nt.nodes.get('Principled BSDF') if nt else None
        if not b:
            continue
        if m.name.startswith('gun_glow'):
            b.inputs['Emission Color'].default_value = (*VIOLET, 1)
            if 'crystal' in m.name:
                b.inputs['Base Color'].default_value = (.18, .06, .6, 1)
            elif 'dim' in m.name:
                b.inputs['Base Color'].default_value = (.05, .01, .2, 1)
            else:
                b.inputs['Base Color'].default_value = (*VIOLET, 1)
        elif m.name.startswith('gun_body'):
            for l in list(nt.links):
                if l.to_socket == b.inputs['Base Color']:
                    nt.links.remove(l)
            b.inputs['Base Color'].default_value = (*BODY, 1)


def glare(sc):
    """Bloom on the lights, as the game's post-process gives them."""
    try:
        nt = bpy.data.node_groups.new('vr_comp', 'CompositorNodeTree')
        sc.compositing_node_group = nt
        nt.interface.new_socket('Image', in_out='OUTPUT', socket_type='NodeSocketColor')
        rl = nt.nodes.new('CompositorNodeRLayers'); gl = nt.nodes.new('CompositorNodeGlare'); go = nt.nodes.new('NodeGroupOutput')
        for k, v in (('Type', 'Bloom'), ('Threshold', 1.2), ('Strength', .9), ('Size', .55), ('Saturation', 1.0)):
            try:
                gl.inputs[k].default_value = v
            except Exception as e:
                print('glare input', k, e)
        nt.links.new(rl.outputs['Image'], gl.inputs['Image']); nt.links.new(gl.outputs['Image'], go.inputs[0])
    except Exception as e:
        print('glare', e)


def render(i, it):
    parts = it.split(':')
    name = parts[0]; view = parts[1] if len(parts) > 1 else 's'; zoom = float(parts[2]) if len(parts) > 2 else 1.0
    bl.reset()
    path = name if os.path.isabs(name) else os.path.join(bl.MODELS, name + ('' if name.endswith('.glb') else '.glb'))
    bpy.ops.import_scene.gltf(filepath=path)
    dress()
    sc = bpy.context.scene
    for o in sc.objects:                                 # loose reload props sit out of the way: not in the picture
        if o.name.startswith('x_'):
            o.hide_render = True
    lo = Vector((1e9,) * 3); hi = Vector((-1e9,) * 3)
    for o in sc.objects:
        if o.type == 'MESH' and not o.hide_render:
            for c in o.bound_box:
                w = o.matrix_world @ Vector(c)
                lo = Vector(map(min, lo, w)); hi = Vector(map(max, hi, w))
    c = (lo + hi) / 2; size = hi - lo
    sc.render.engine = 'CYCLES'; sc.cycles.samples = SAMPLES; sc.cycles.device = 'CPU'
    try:
        sc.cycles.use_denoising = True
    except Exception:
        pass
    sc.render.resolution_x = RES; sc.render.resolution_y = H
    try:
        sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = 'AgX - Punchy'
    except Exception as e:
        print('view', e)
    glare(sc)
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); sc.collection.objects.link(cam); sc.camera = cam
    L = max(size.y, .2)
    dirs = {'s': Vector((1, 0, 0)), 'r': Vector((-1, 0, 0)), 'q': Vector((.75, -1.0, .35)), 'b': Vector((.7, 1.0, .45)),
            't': Vector((.001, .0, 1)), 'u': Vector((.4, -.2, -1)), 'rq': Vector((-.75, -1.0, .35))}
    if view == 'fp':
        cam.data.lens = 24
        cam.location = Vector((.11, .34, .2)); tgt = Vector((-.02, -.6, .06))
        cam.rotation_euler = (tgt - cam.location).to_track_quat('-Z', 'Y').to_euler()
    else:
        d = dirs[view].normalized()
        if view in ('s', 'r', 't', 'u'):
            cam.data.type = 'ORTHO'
            span = max(size.y * 1.08, size.z * 1.08 * 16 / 9, (size.x * 1.08 * 16 / 9) if view in ('t', 'u') else 0)
            cam.data.ortho_scale = span / zoom
            cam.location = c + d * 3
        else:
            cam.data.lens = 70
            cam.location = c + d * (L * 2.1 / zoom)
        up = 'Y'
        cam.rotation_euler = (c - cam.location).to_track_quat('-Z', up).to_euler()
        if view in ('t', 'u'):
            cam.rotation_euler = (math.radians(0 if view == 't' else 180), 0, math.radians(90 if view == 't' else -90))
    for loc, e, col, sz in (((1.2, -.6, 1.6), 46, (1, .97, .94), 1.4), ((1.0, .9, .1), 30, (.7, .75, 1), 1.6),
                            ((-1.0, .3, .9), 60, (.55, .3, 1), .8), ((.4, -.2, -1.2), 10, (.5, .4, .9), 1.0)):
        ld = bpy.data.lights.new('l', 'AREA'); ld.energy = e * L * L; ld.color = col; ld.size = sz * L
        lo_ = bpy.data.objects.new('l', ld); lo_.location = c + Vector(loc) * L
        lo_.rotation_euler = (c - lo_.location).to_track_quat('-Z', 'Y').to_euler(); sc.collection.objects.link(lo_)
    w = bpy.data.worlds.new('w'); sc.world = w
    try:
        w.use_nodes = True
        w.node_tree.nodes['Background'].inputs[0].default_value = (.035, .035, .06, 1)
        w.node_tree.nodes['Background'].inputs[1].default_value = 1.0
    except Exception:
        w.color = (.012, .012, .02)
    p = os.path.join(os.path.dirname(out), '_vr_tile%d.png' % i)
    sc.render.filepath = p; bpy.ops.render.render(write_still=True)
    return p


tiles = [render(i, it) for i, it in enumerate(items)]
imgs = [bpy.data.images.load(p) for p in tiles]
n = len(imgs); cols = min(COLS, n); rows = (n + cols - 1) // cols
sheet = np.zeros((H * rows, RES * cols, 4), dtype=np.float32); sheet[..., 3] = 1; sheet[..., :3] = (.012, .012, .02)
for i, im in enumerate(imgs):
    px = np.array(im.pixels[:], dtype=np.float32).reshape(H, RES, 4)
    r = rows - 1 - i // cols; cc = i % cols
    sheet[r * H:(r + 1) * H, cc * RES:(cc + 1) * RES] = px
im = bpy.data.images.new('sheet', RES * cols, H * rows)
im.pixels = sheet.ravel()
im.filepath_raw = out; im.file_format = 'PNG'; im.save()
for p in tiles:
    os.remove(p)
print('sheet ->', out)
