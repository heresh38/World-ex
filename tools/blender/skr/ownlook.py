"""A gun rendered wearing its OWN maps the way the game's material reads them (M_SOStandard, roughly): the tiling set's
colour darkened by the baked occlusion and by dirt in the hollows, brightened where an edge is rubbed, polished where a
hand lies; the sheet's studio light. For judging the texture step before the game import.

blender -b -P tools/blender/skr/ownlook.py -- <outdir> gun_skr_rifle
"""
import math
import os
import sys
import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import bl       # noqa: E402
import bakekit  # noqa: E402

out, nm = sys.argv[sys.argv.index('--') + 1:][:2]
os.makedirs(out, exist_ok=True)
bl.reset()
bpy.ops.import_scene.gltf(filepath=os.path.join(bl.MODELS, nm + '.glb'))
m1 = bpy.data.images.load(os.path.join(bl.TEXTURES, nm + '_u_m1.png'))
m2 = bpy.data.images.load(os.path.join(bl.TEXTURES, nm + '_u_m2.png'))
for im in (m1, m2):
    im.colorspace_settings.name = 'Non-Color'
done = set()
for o in bpy.context.scene.objects:
    if o.type != 'MESH' or len(o.data.uv_layers) < 2:
        continue
    uv1 = o.data.uv_layers[1].name
    for slot in o.material_slots:
        m = slot.material
        if not m or m.name in done or not m.use_nodes:
            continue
        done.add(m.name)
        nt = m.node_tree
        b = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
        if not b or 'glow' in m.name:
            continue
        src = b.inputs['Base Color'].links[0].from_socket if b.inputs['Base Color'].links else None
        base = nt.nodes.new('ShaderNodeRGB'); base.outputs[0].default_value = b.inputs['Base Color'].default_value
        uvn = nt.nodes.new('ShaderNodeUVMap'); uvn.uv_map = uv1
        t1 = nt.nodes.new('ShaderNodeTexImage'); t1.image = m1
        t2 = nt.nodes.new('ShaderNodeTexImage'); t2.image = m2
        nt.links.new(uvn.outputs['UV'], t1.inputs['Vector']); nt.links.new(uvn.outputs['UV'], t2.inputs['Vector'])
        s1 = nt.nodes.new('ShaderNodeSeparateColor'); nt.links.new(t1.outputs['Color'], s1.inputs['Color'])
        s2 = nt.nodes.new('ShaderNodeSeparateColor'); nt.links.new(t2.outputs['Color'], s2.inputs['Color'])
        # colour x occlusion, toward grime by dirt, toward bright metal by wear
        mul = nt.nodes.new('ShaderNodeMix'); mul.data_type = 'RGBA'; mul.blend_type = 'MULTIPLY'; mul.inputs['Factor'].default_value = 1.0
        nt.links.new(src if src else base.outputs[0], mul.inputs[6])
        nt.links.new(s1.outputs['Red'], mul.inputs[7])
        dirt = nt.nodes.new('ShaderNodeMix'); dirt.data_type = 'RGBA'
        nt.links.new(s1.outputs['Blue'], dirt.inputs['Factor']); nt.links.new(mul.outputs[2], dirt.inputs[6])
        dirt.inputs[7].default_value = (.035, .030, .028, 1)
        mf = nt.nodes.new('ShaderNodeMath'); mf.operation = 'MULTIPLY'; mf.inputs[1].default_value = .55
        nt.links.new(s1.outputs['Blue'], mf.inputs[0]); nt.links.new(mf.outputs[0], dirt.inputs['Factor'])
        wear = nt.nodes.new('ShaderNodeMix'); wear.data_type = 'RGBA'
        nt.links.new(s1.outputs['Green'], wear.inputs['Factor']); nt.links.new(dirt.outputs[2], wear.inputs[6])
        wear.inputs[7].default_value = (.55, .55, .56, 1)
        nt.links.new(wear.outputs[2], b.inputs['Base Color'])
        rough = nt.nodes.new('ShaderNodeMath'); rough.operation = 'MULTIPLY_ADD'
        nt.links.new(s2.outputs['Red'], rough.inputs[0]); rough.inputs[1].default_value = -.25; rough.inputs[2].default_value = b.inputs['Roughness'].default_value
        if not b.inputs['Roughness'].links:
            nt.links.new(rough.outputs[0], b.inputs['Roughness'])
sc = bpy.context.scene
sc.render.engine = 'CYCLES'; bakekit._gpu(sc); sc.cycles.samples = 128; sc.cycles.use_denoising = True
sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = 'AgX - Medium High Contrast'
w = bpy.data.worlds.new('w'); sc.world = w; w.use_nodes = True
w.node_tree.nodes['Background'].inputs['Color'].default_value = (.035, .035, .04, 1)
pts = [o.matrix_world @ Vector(c) for o in sc.objects if o.type == 'MESH' for c in o.bound_box]
lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
c = (lo + hi) / 2; size = max((hi - lo).y, (hi - lo).z * 1.8)


def area(n, loc, power, s, col):
    ld = bpy.data.lights.new(n, 'AREA'); ld.energy = power; ld.size = s; ld.color = col
    ob = bpy.data.objects.new(n, ld); sc.collection.objects.link(ob); ob.location = c + Vector(loc)
    ob.rotation_euler = (c - ob.location).to_track_quat('-Z', 'Y').to_euler()
k = size
area('key', (1.4 * k, -.6 * k, 1.2 * k), 140 * k * k, .8 * k, (1, .96, .9))
area('rim', (-1.2 * k, .8 * k, .9 * k), 180 * k * k, .5 * k, (.85, .9, 1))
area('top', (.2 * k, 0, 1.6 * k), 70 * k * k, 1.0 * k, (1, 1, 1))
cd = bpy.data.cameras.new('c'); cam = bpy.data.objects.new('c', cd); sc.collection.objects.link(cam); sc.camera = cam
views = {'side': ((1, 0, .05), (1800, 760), None), 'quarter': ((1, -.8, .45), (1400, 900), None),
         'close': ((1, -.25, .25), (1400, 900), .45)}
for v, (d, res, zoom) in views.items():
    sc.render.resolution_x, sc.render.resolution_y = res
    dv = Vector(d).normalized()
    if v == 'side':
        cd.type = 'ORTHO'; cd.ortho_scale = size * 1.08
        cam.location = c + dv * size * 2.6
        tgt = c
    else:
        cd.type = 'PERSP'; cd.lens = 70
        tgt = c + Vector((0, size * .12, 0)) if zoom else c
        cam.location = tgt + dv * size * (2.6 * (zoom or 1))
    cam.rotation_euler = (tgt - cam.location).to_track_quat('-Z', 'Y').to_euler()
    sc.render.filepath = os.path.join(out, f'{nm}_{v}.png')
    bpy.ops.render.render(write_still=True)
print('[ownlook] done', flush=True)
