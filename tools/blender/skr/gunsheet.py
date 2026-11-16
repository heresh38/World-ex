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
    # glass as glass (the game's M_SOGlass is clear): transmission in place of the exported alpha
    for mt in bpy.data.materials:
        if mt.name.startswith('gun_glass') and mt.node_tree:
            b_ = mt.node_tree.nodes.get('Principled BSDF')
            if b_:
                b_.inputs['Transmission Weight'].default_value = 1.0; b_.inputs['Roughness'].default_value = .02
                b_.inputs['Alpha'].default_value = 1.0; b_.inputs['IOR'].default_value = 1.5
    # STUDIO=1: soft boxes round the piece that only its reflections see (polished steel shows what it reflects: in the
    # dark studio a mirror blade read as black)
    if os.environ.get('STUDIO'):
        # what the reflections see: a soft sky (the camera itself still sees the dark backdrop)
        wn = w.node_tree.nodes; wl = w.node_tree.links
        sky = wn.new('ShaderNodeTexSky'); sky.sky_type = 'MULTIPLE_SCATTERING' if hasattr(sky, 'sky_type') else sky.sky_type
        try:
            sky.sun_disc = False
        except Exception:
            pass
        bgs = wn.new('ShaderNodeBackground'); bgs.inputs['Strength'].default_value = .5
        wl.new(sky.outputs[0], bgs.inputs[0])
        lp = wn.new('ShaderNodeLightPath'); mx = wn.new('ShaderNodeMixShader')
        wl.new(lp.outputs['Is Camera Ray'], mx.inputs[0]); wl.new(bgs.outputs[0], mx.inputs[1])
        wl.new(wn['Background'].outputs[0], mx.inputs[2]); wl.new(mx.outputs[0], wn['World Output'].inputs[0])
        em = bpy.data.materials.new('softbox'); em.use_nodes = True
        nt_ = em.node_tree; nt_.nodes.clear()
        e_ = nt_.nodes.new('ShaderNodeEmission'); e_.inputs['Strength'].default_value = 6.0
        o_ = nt_.nodes.new('ShaderNodeOutputMaterial'); nt_.links.new(e_.outputs[0], o_.inputs[0])
        for i, (loc, rot, sz) in enumerate((((0, 0, 1.3), (0, 0, 0), (2.2, .5)), ((1.4, 0, .4), (0, 1.2, 0), (2.2, .35)),
                                            ((-1.3, 0, .6), (0, -1.0, 0), (2.2, .5)), ((0, 0, -1.2), (math.pi, 0, 0), (2.2, .3)))):
            bpy.ops.mesh.primitive_plane_add(size=1, location=c + Vector(loc) * k)
            pl = bpy.context.object; pl.scale = (sz[1] * k, sz[0] * k, 1); pl.rotation_euler = rot
            pl.data.materials.append(em); pl.visible_camera = False
    cd = bpy.data.cameras.new('c'); cam = bpy.data.objects.new('c', cd); sc.collection.objects.link(cam); sc.camera = cam
    VIEWS = {'side': ((1, 0, 0), (1600, 700)), 'quarter': ((1, -.8, .45), (1400, 900)), 'top': ((0, 0, 1), (1600, 500)),
             'front': ((0, -1, .15), (900, 700)), 'back3q': ((-1, .8, .35), (1400, 900)),
             'under': ((.9, -.5, -.6), (1400, 900)), 'muzzle': ((.55, -1, .25), (1100, 900)),
             'sight': ((.8, -.7, .45), (1100, 900)), 'sightback': ((.25, 1, .18), (1100, 900))}
    for view in os.environ.get('VIEWS', 'side,quarter').split(','):
        d, res = VIEWS[view]
        sc.render.resolution_x, sc.render.resolution_y = res
        dv = Vector(d).normalized()
        if view in ('side', 'top'):
            cd.type = 'ORTHO'; cd.ortho_scale = size * 1.12
        else:
            cd.type = 'PERSP'; cd.lens = 70
        cam.location = c + dv * size * 2.6
        if view in ('muzzle', 'sight', 'sightback'):     # close on the muzzle end / on the sight (the optic, by name)
            if view == 'muzzle':
                tgt = c + Vector((0, -(hi - lo).y * .42, 0))
                cam.location = tgt + dv * size * .9
            else:
                op = [o.matrix_world @ Vector(q) for o in sc.objects if o.type == 'MESH' and 'OPTIC' in o.name.upper() for q in o.bound_box]
                tgt = sum(op, Vector()) / len(op) if op else c
                cam.location = tgt + dv * size * .32
            cam.rotation_euler = (tgt - cam.location).to_track_quat('-Z', 'Y').to_euler()
            sc.render.filepath = os.path.join(out, f'{nm}_{view}.png')
            bpy.ops.render.render(write_still=True)
            continue
        cam.rotation_euler = (c - cam.location).to_track_quat('-Z', 'Y').to_euler()
        if view == 'top':
            cam.rotation_euler = (0.0, 0.0, math.radians(-90))   # looking down, the barrel across the picture
        sc.render.filepath = os.path.join(out, f'{nm}_{view}.png')
        bpy.ops.render.render(write_still=True)
    print('[gunsheet]', nm, flush=True)
