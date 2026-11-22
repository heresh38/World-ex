"""A part of a Sarketh built fast, to look at it beside the owner's sheet while it is being made (the whole body takes
five minutes in build.py; here the head about forty seconds, the whole body at a coarse cell under two minutes):

    blender -b -P tools/blender/skr/lab.py -- male|female --part=head|full [--h=.002] [--out=dir] [--bare]
            [--views=sheet,head,headfront,headside,headtop,headback,eye,front,side,back,torso,legs,armback]
            [--pose=Idle:1] [--yaw=28]

part head: the body's surface only round the head and neck, and the helmet and the neck's plates (male.head_parts);
part full: the whole body at a coarse cell (h .006) with all of its armour. --bare: no armour at all (the sculpt alone).
The view `sheet` is the owner's sheet's own view of this body: orthographic at the sheet's scale (the floor at y 968 of
1024, the male's 2.03 m at y 80, the body at x 330 (male) or 640 (female) of the 1536), turned `yaw` degrees, over
nothing, so it can be laid over the sheet or set beside the same crop of it.
Renders under the sheet's light (SKR_LAB_LIGHT scales it): a warm key front left, cold rims behind, a near-black ground.

--portraits=<species>[,<species>] (with --part=full): the journal's pictures of those ranks (the armoury's JOURNAL tab):
each in its rank's colours (RANK_TINTS: the game's ASOEnemy::PlateTint / LacquerTint / LightTint), the whole body three
quarters from the front 512 x 768 and the head and shoulders 256 x 256, over nothing, into <out>/journal_<species>.png
and journal_<species>_bust.png (SO_IMPORT_ONLY=journal reads them from SourceArt/Icons/journal).
"""
import math
import os
import sys
import time

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import bl            # noqa: E402
import fleshkit as fk   # noqa: E402
import bakekit       # noqa: E402
import anatomy       # noqa: E402
import chitin        # noqa: E402
import build as B    # noqa: E402

T0 = time.time()


def log(*a):
    print('[skr_lab %5.1fs]' % (time.time() - T0), *a, flush=True)


def opts():
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    o = {'sex': 'male', 'part': 'head', 'h': None, 'out': None, 'bare': False, 'views': None, 'pose': None}
    for x in a:
        if x.startswith('--'):
            k, _, v = x[2:].partition('=')
            o[k] = v if v else True
        else:
            o['sex'] = x
    return o


def studio(sc):
    sc.render.engine = 'CYCLES'
    bakekit._gpu(sc)
    sc.cycles.samples = 64
    sc.cycles.use_denoising = True
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.look = 'AgX - Medium High Contrast'
    w = bpy.data.worlds.new('studio'); sc.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes['Background']; bg.inputs['Color'].default_value = (.022, .022, .026, 1); bg.inputs['Strength'].default_value = 1.0

    def area(name, loc, power, size, col, target):
        ld = bpy.data.lights.new(name, 'AREA'); ld.energy = power; ld.size = size; ld.color = col
        ob = bpy.data.objects.new(name, ld); sc.collection.objects.link(ob)
        ob.location = loc
        ob.rotation_euler = (Vector(target) - ob.location).to_track_quat('-Z', 'Y').to_euler()
    k = float(os.environ.get('SKR_LAB_LIGHT', '.36'))      # (at 1 the pale plates read white: the sheet's lit plates are a mid grey)
    area('key', (-2.4, -2.8, 3.2), 420 * k, 2.6, (1.0, .96, .92), (0, 0, 1.2))
    area('fill', (2.8, -2.0, 1.4), 90 * k, 3.2, (.78, .84, 1.0), (0, 0, 1.1))
    area('rimL', (-1.9, 2.4, 2.6), 560 * k, 1.2, (.86, .90, 1.0), (0, 0, 1.3))
    area('rimR', (1.9, 2.4, 2.6), 560 * k, 1.2, (.86, .90, 1.0), (0, 0, 1.3))
    area('top', (0, .4, 4.2), 220 * k, 2.0, (1, 1, 1), (0, 0, 1.0))


# a rank's colours, as the game lays them (ASOEnemy::ApplyRankColours: the plates and claws times PlateTint, the dark
# lacquer times LacquerTint, the small lights' glow LightTint; white / black: as made)
RANK_TINTS = {
    'stalker_feral': ((1.26, 1.06, .70), (1.22, 1.04, .80), (1.0, .72, .26)),
    'remnant': ((1, 1, 1), (1, 1, 1), None),
    'stalker': ((.68, .84, 1.18), (.80, .96, 1.40), (.40, .85, 1.0)),
    'veilborn': ((.70, 1.10, .96), (.80, 1.32, 1.14), (.30, 1.0, .75)),
    'bulwark': ((1.32, 1.14, .76), (1.20, 1.08, .84), (1.0, .85, .40)),
    'bearer': ((1.16, .82, .52), (1.24, .98, .74), (1.0, .50, .15)),
    'colossus': ((1.22, .64, .58), (1.50, .80, .80), (1.0, .22, .15)),
}


def tint_nodes():
    """a multiply in front of the base colour of the plates, the claws and the lacquer, and the amber lights' glow:
    {'plate': [mix nodes], 'dark': [...], 'light': [(principled, its colour as made)]}"""
    out = {'plate': [], 'dark': [], 'light': []}
    for m in bpy.data.materials:
        n = m.name.split('.')[0]
        kind = 'plate' if n in ('skr_armour', 'skr_claw') else 'dark' if n == 'skr_armour_dark' else 'light' if n == 'skr_glow_amber' else None
        if not kind or not m.node_tree:
            continue
        nt = m.node_tree
        b = next((x for x in nt.nodes if x.type == 'BSDF_PRINCIPLED'), None)
        if not b:
            continue
        if kind == 'light':
            out['light'].append((b, tuple(b.inputs['Emission Color'].default_value)))
            continue
        mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'; mix.blend_type = 'MULTIPLY'
        mix.inputs['Factor'].default_value = 1.0
        src = b.inputs['Base Color'].links[0].from_socket if b.inputs['Base Color'].links else None
        if src is not None:
            nt.links.new(src, mix.inputs[6])
        else:
            mix.inputs[6].default_value = b.inputs['Base Color'].default_value
        mix.inputs[7].default_value = (1, 1, 1, 1)
        nt.links.new(mix.outputs[2], b.inputs['Base Color'])
        out[kind].append(mix)
    return out


def set_rank(nodes, species):
    plate, dark, light = RANK_TINTS[species]
    for mix in nodes['plate']:
        mix.inputs[7].default_value = (*plate, 1)
    for mix in nodes['dark']:
        mix.inputs[7].default_value = (*dark, 1)
    for b, made in nodes['light']:
        b.inputs['Emission Color'].default_value = (*light, 1) if light else made


def portraits(o, sc, cam, cam_d, sex, out, hd):
    """the journal's pictures: each rank asked for in its colours, the whole body and the head and shoulders"""
    nodes = tint_nodes()
    sc.render.film_transparent = True
    # (on the armoury's dark glass: the lights a little up from the sheet's, the rims up more, so the dark lacquer
    # keeps its outline)
    for ob in sc.objects:
        if ob.type == 'LIGHT':
            ob.data.energy *= 1.9 if ob.name.startswith('rim') else 1.45
    yaw = math.radians(float(o.get('yaw') or 24))
    d = Vector((-math.sin(yaw), -math.cos(yaw), .06)).normalized()
    Hh = Vector(hd)
    tall = Hh.z + .32                                 # (the crest over the head)
    shots = (
        # name, size, what it looks at, how far (half the height it frames over the lens's half angle), lens
        ('', (512, 768), Vector((0, 0, tall * .49)), tall * .5 / math.tan(math.atan(18 / 85)) * 1.16, 85),
        ('_bust', (256, 256), Hh + Vector((0, .01, .06)), .47 / math.tan(math.atan(18 / 85)), 85),
    )
    for species in o['portraits'].split(','):
        set_rank(nodes, species)
        for suffix, res, tgt, dist, lens in shots:
            cam_d.type = 'PERSP'
            cam_d.lens = lens
            cam_d.sensor_fit = 'AUTO'
            sc.render.resolution_x, sc.render.resolution_y = res
            cam.location = tgt + d * dist
            cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
            sc.render.filepath = os.path.join(out, f'journal_{species}{suffix}.png')
            bpy.ops.render.render(write_still=True)
            log('rendered', os.path.basename(sc.render.filepath))
    sc.render.film_transparent = False


def main():
    o = opts()
    bl.reset()
    sex = o['sex']
    layout_mod = __import__(sex)
    J, S = anatomy.sculpt(sex)
    M = B.materials()
    hd = J['head'][0]
    if o['part'] == 'head':
        h = float(o['h'] or .002)
        lo, hi = (hd[0] - .12, hd[1] - .21, hd[2] - .20), (hd[0] + .12, hd[1] + .19, hd[2] + .23)
    else:
        h = float(o['h'] or .006)
        top = max(J['head'][1][2], 2.0) + .12
        lo, hi = (-.56, -.34, -.03), (.56, .34, top)
    body = fk.build_mesh(S, f'SKR_{sex}_body', lo, hi, h, 400000, {'skin': M['skin']}, uv_scale=.24, ao_dist=.05,
                         mottle=.25, bruise=('#8f86a8', .22, 5.0), veins=('#7a7aa8', .18, 7.0), seed=4)
    objs = [body]
    if not o['bare']:
        A = chitin.Armour(S, M, seed=11 if sex == 'male' else 13)
        A.rank = o.get('rank')                       # (--rank=heavy: the heavy ranks' set)
        if o['part'] == 'head' and hasattr(layout_mod, 'head_parts'):
            layout_mod.head_parts(A, J)
        else:
            layout_mod.layout(A, J)
        log('armour pieces:', A.count)
        objs += list(A.join(f'SKR_{sex}_A').values())
    arm = fk.make_rig(J, anatomy.PARENT, anatomy.ORDER)
    for ob in objs:
        ob.parent = arm
        md = ob.modifiers.new('Armature', 'ARMATURE'); md.object = arm
    if o['pose']:
        import motion as Mo
        clip, fr = o['pose'].split(':')
        Mo.bake(arm, [clip], log=log)
        arm.animation_data.action = bpy.data.actions[clip]
        bpy.context.scene.frame_set(int(fr))
    sc = bpy.context.scene
    studio(sc)
    out = os.path.abspath(o['out'] or os.path.join(os.environ.get('TEMP', '.'), 'skr_lab'))   # (Blender reads a relative render path from the .blend's own place)
    os.makedirs(out, exist_ok=True)
    cam_d = bpy.data.cameras.new('cam'); cam = bpy.data.objects.new('cam', cam_d); sc.collection.objects.link(cam); sc.camera = cam
    if o.get('portraits'):
        portraits(o, sc, cam, cam_d, sex, out, hd)
        return
    Hh = Vector(hd)
    Hm = 2.2 if sex == 'male' else 2.05
    views = {
        'head': (Hh + Vector((0, -.01, .07)), Vector((-.85, -.55, .10)), 1.3, 120, (705, 750)),
        'headfront': (Hh + Vector((0, -.02, .06)), Vector((0, -1, .05)), 1.3, 120, (700, 750)),
        'headside': (Hh + Vector((0, .03, .07)), Vector((-1, 0, .05)), 1.4, 120, (750, 700)),
        'headtop': (Hh + Vector((0, .03, .07)), Vector((-.3, -.2, 1)), 1.4, 120, (750, 750)),
        'eye': (Hh + Vector((-.03, -.07, .07)), Vector((-1, -.55, .12)), .55, 120, (700, 600)),
        'torso': (Vector((0, 0, Hm * .68)), Vector((-.45, -1, .08)), 3.2, 85, (800, 900)),
        'legs': (Vector((0, 0, Hm * .27)), Vector((-.45, -1, .10)), 3.4, 85, (800, 900)),
        'armback': (Vector((-.33, .05, Hm * .58)), Vector((-.55, 1, .10)), 1.9, 85, (700, 900)),
        'headback': (Hh + Vector((0, .05, .05)), Vector((.15, 1, .25)), 1.5, 120, (700, 750)),
        'front': (Vector((0, 0, Hm * .5)), Vector((-.30, -1, .04)), 7.6, 85, (540, 1485)),
        'side': (Vector((0, 0, Hm * .5)), Vector((-1, -.05, .03)), 7.6, 85, (540, 1485)),
        'back': (Vector((0, 0, Hm * .66)), Vector((.05, 1, .12)), 4.2, 85, (600, 870)),
    }
    want = (o['views'] or ('head,headfront,headside' if o['part'] == 'head' else 'front,side,back')).split(',')
    if 'sheet' in want:
        # the owner's sheet's own view of this body, orthographic, at the sheet's scale: the floor at y 968 of 1024 px and
        # the male's head (2.03 m) at y 80, the body's middle at x 330 (male) or 640 (female) of the sheet's 1536;
        # rendered over nothing (film transparent) so it can be laid over the sheet (sheet_overlay.py)
        want.remove('sheet')
        yaw = math.radians(float(o.get('yaw') or 28))
        mpp = 2.03 / 888.0
        cx = 330 if sex == 'male' else 640
        cam_d.type = 'ORTHO'
        cam_d.ortho_scale = 1536 * mpp
        sc.render.resolution_x, sc.render.resolution_y = 1536, 1024
        sc.render.film_transparent = True
        d = Vector((-math.sin(yaw), -math.cos(yaw), 0))
        right = Vector((math.cos(yaw), -math.sin(yaw), 0))
        # the image's middle (768, 512) is the world point that many metres right of / above the body's foot point
        centre = Vector((0, 0, (968 - 512) * mpp)) + right * ((768 - cx) * mpp)
        cam.location = centre + d * 6
        cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
        sc.render.filepath = os.path.join(out, f'{sex}_sheet.png')
        bpy.ops.render.render(write_still=True)
        log('rendered the sheet view')
        sc.render.film_transparent = False
        cam_d.type = 'PERSP'
    for v in want:
        tgt, d, dist, lens, res = views[v]
        d = d.normalized()
        cam_d.lens = lens
        sc.render.resolution_x, sc.render.resolution_y = res
        cam.location = tgt + d * dist
        cam.rotation_euler = (tgt - cam.location).to_track_quat('-Z', 'Y').to_euler()
        sc.render.filepath = os.path.join(out, f'{sex}_{v}.png')
        bpy.ops.render.render(write_still=True)
        log('rendered', v)


if __name__ == '__main__':
    main()
