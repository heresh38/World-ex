"""Build a Sarketh: the sculpted under-body, its chitin, the rig; render it as the owner's sheet shows it.

blender -b -P tools/blender/skr/build.py -- male|female [--h=.003] [--save=x.blend] [--look=dir] [--views=front,quarter,side,back,head]
  --look renders the body lit as the design sheet is (a dark grey studio, a warm key, cold rims behind) from each view

Parts: SKR_<sex>_body (the creature: skin, claws, eyes) and one armour part per slot, SKR_<sex>_A_<slot> (helmet, neck,
chest, back, shoulders, arms, hands, belt, legs, feet), all on one skeleton: a set is swapped, added to or made heavier
slot by slot, never by touching the body. Materials (names are an API): skr_skin (the dark scaled body), skr_claw,
skr_armour (the pale metal armour), skr_armour_dark (its dark plates and the visor), skr_glow (eyes, lights): a set's
colour is a tint on the armour materials. Bones: anatomy.ORDER.
"""
import math
import os
import sys
import time
import bpy
import numpy as np
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import bl            # noqa: E402
import fleshkit as fk   # noqa: E402
import bakekit       # noqa: E402
import anatomy       # noqa: E402
import chitin        # noqa: E402

T0 = time.time()


def log(*a):
    print('[skr %5.1fs]' % (time.time() - T0), *a, flush=True)


def opts():
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    o = {'sex': 'male', 'h': .003, 'save': None, 'look': None, 'views': 'front,quarter,side,back,head,headside'}
    for x in a:
        if x.startswith('--'):
            k, _, v = x[2:].partition('=')
            o[k] = v if v else True
        else:
            o['sex'] = x
    o['h'] = float(o['h'])
    return o


def materials():
    return {
        'skin': fk.tmat('skr_skin', 'skr_skin', rough=.45, nstr=1.0),
        'armour': fk.tmat('skr_armour', 'skr_armour', rough=.32, metal=.62, nstr=1.0),
        'dark': fk.tmat('skr_armour_dark', 'skr_dark', rough=.24, metal=.6, nstr=.8),
        'claw': fk.tmat('skr_claw', 'skr_dark', rough=.30, nstr=.6),
        'glow': bl.mat('skr_glow', '#cfe2ff', 0, .3, emit='#d8e8ff', strength=14.0),
    }


def build(o):
    sex = o['sex']
    layout = __import__(sex).layout
    J, S = anatomy.sculpt(sex)
    M = materials()
    top = max(J['head'][1][2], 2.0) + .12
    lo, hi = (-.56, -.34, -.03), (.56, .34, top)
    body = fk.build_mesh(S, f'SKR_{sex}_body', lo, hi, o['h'], 900000, {'skin': M['skin']}, uv_scale=.24, ao_dist=.05,
                         mottle=.25, bruise=('#8f86a8', .22, 5.0), veins=('#7a7aa8', .18, 7.0), seed=4)
    A = chitin.Armour(S, M, seed=11 if sex == 'male' else 13)
    layout(A, J)
    log('chitin:', A.count, 'pieces')
    parts = A.join(f'SKR_{sex}_A')
    log('armour parts:', ', '.join(sorted(parts)))
    arm = fk.make_rig(J, anatomy.PARENT, anatomy.ORDER)
    arm.name = f'SKR_{sex}_rig'
    for ob in [body] + list(parts.values()):
        ob.parent = arm
        md = ob.modifiers.new('Armature', 'ARMATURE'); md.object = arm
    tris = sum(sum(len(p.vertices) - 2 for p in ob.data.polygons) for ob in [body] + list(parts.values()))
    log('triangles (sculpt resolution, before the game version):', tris)
    return body, parts, arm


# ------------------------------------------------------------------ the look
def look(o, out):
    sc = bpy.context.scene
    os.makedirs(out, exist_ok=True)
    sc.render.engine = 'CYCLES'
    dev = bakekit._gpu(sc)
    sc.cycles.samples = 96
    sc.cycles.use_denoising = True
    sc.render.film_transparent = False
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.look = 'AgX - Medium High Contrast'
    w = bpy.data.worlds.new('studio'); sc.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes['Background']; bg.inputs['Color'].default_value = (.030, .030, .034, 1); bg.inputs['Strength'].default_value = 1.0
    bpy.ops.mesh.primitive_plane_add(size=12, location=(0, 0, 0))
    fl = bpy.context.active_object
    fl.data.materials.append(bl.mat('floor', '#141416', 0, .30))

    def area(name, loc, rot, power, size, col):
        ld = bpy.data.lights.new(name, 'AREA'); ld.energy = power; ld.size = size; ld.color = col
        ob = bpy.data.objects.new(name, ld); sc.collection.objects.link(ob)
        ob.location = loc; ob.rotation_euler = rot
        return ob

    def aim(ob, target=(0, 0, 1.2)):
        d = Vector(target) - ob.location
        ob.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()

    key = area('key', (-2.2, -2.6, 3.4), (0, 0, 0), 480, 2.2, (1.0, .95, .90)); aim(key)
    fill = area('fill', (2.6, -2.2, 1.6), (0, 0, 0), 120, 3.0, (.80, .86, 1.0)); aim(fill)
    for nm, x in (('rimL', -1.8), ('rimR', 1.8)):
        r = area(nm, (x, 2.4, 2.6), (0, 0, 0), 1100, 1.0, (.86, .90, 1.0)); aim(r, (0, 0, 1.3))
    topl = area('top', (0, .4, 4.2), (0, 0, 0), 300, 2.0, (1, 1, 1)); aim(topl, (0, 0, 1.0))
    cam_d = bpy.data.cameras.new('cam'); cam = bpy.data.objects.new('cam', cam_d); sc.collection.objects.link(cam); sc.camera = cam
    H = 2.4 if o['sex'] == 'male' else 2.25
    views = {
        'front': ((0, -1, 0), 1.10, 85, (720, 1280)),
        'quarter': ((-.75, -1, 0), 1.10, 85, (720, 1280)),
        'side': ((1, 0, 0), 1.10, 85, (720, 1280)),
        'back': ((0, 1, 0), 1.10, 85, (720, 1280)),
        'head': ((-.6, -1, .15), 1.98 if o['sex'] == 'male' else 1.86, 135, (900, 900)),
        'headside': ((1, -.15, .1), 1.98 if o['sex'] == 'male' else 1.86, 135, (900, 900)),
        'hand': ((-1, -.6, 0), 0.95 if o['sex'] == 'male' else .90, 135, (900, 900)),
        'foot': ((-1, -.8, .25), 0.12, 120, (900, 900)),
    }
    for v in o['views'].split(','):
        d, tz, lens, res = views[v]
        d = Vector(d).normalized()
        cam_d.lens = lens
        sc.render.resolution_x, sc.render.resolution_y = res
        tgt = Vector((0.40 if v == 'hand' else (.14 if v == 'foot' else 0), -.05 if v == 'foot' else 0, tz))
        if v in ('front', 'quarter', 'side', 'back'):
            dist = 6.3
        else:
            dist = 1.6 if v.startswith('head') else 1.4
        cam.location = tgt + d * dist
        cam.rotation_euler = (tgt - cam.location).to_track_quat('-Z', 'Y').to_euler()
        sc.render.filepath = os.path.join(out, f'{o["sex"]}_{v}.png')
        bpy.ops.render.render(write_still=True)
        log('rendered', v, 'on', dev)


if __name__ == '__main__':
    o = opts()
    bl.reset()
    build(o)
    if o['save']:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(o['save']))
    if o['look']:
        look(o, o['look'])
