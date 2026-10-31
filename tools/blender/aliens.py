"""VANTHOS alien species on the shared rig (all 9 clips): stalker, hulk, mutant, swimmer, elite.

Built like characters.py enemies: organic segments rigidly skinned to one bone each, so they animate cleanly.
Materials: alien_skin, alien_plate, alien_glow (pulses in the game), alien_acid.
Run: blender --background --python tools/blender/aliens.py [-- stalker hulk ...]
"""
import bpy, math, os, sys
from mathutils import Vector
sys.path.insert(0, os.path.dirname(__file__))
import bl, characters
from characters import seg

V = Vector
KINDS = {
    #          scale  skin       plate      glow       acid
    'stalker': (1.05, '#3a2a46', '#1c1624', '#b46cff', '#7dffb0'),
    'hulk': (1.5, '#4a3a34', '#2a2220', '#ff7a2a', '#ffd27a'),
    'mutant': (1.0, '#6a6f5a', '#2e3328', '#7dffb0', '#b6ff4a'),
    'swimmer': (.98, '#1f4a52', '#0e2a30', '#3ae6ff', '#7dffb0'),
    'elite': (1.32, '#2a1e34', '#14101a', '#ff3fb4', '#b46cff'),
}


def body(kind):
    s = KINDS[kind][0]
    b = characters.Body('trooper')
    for k, (a, t) in b.J.items():
        b.J[k] = (a * s, t * s)
    b.s = s
    return b


def mats(kind):
    _, skin, plate, glow, acid = KINDS[kind]
    return dict(skin=bl.mat('alien_skin', skin, .1, .45), plate=bl.mat('alien_plate', plate, .5, .35),
                glow=bl.mat('alien_glow', glow, 0, .3, emit=glow, strength=6), acid=bl.mat('alien_acid', acid, 0, .3, emit=acid, strength=4))


def build_parts(b, kind, M):
    J, s = b.J, b.s
    add = b.add
    sk, pl, gl, ac = M['skin'], M['plate'], M['glow'], M['acid']
    lean = kind in ('stalker', 'swimmer')
    hz = J['hips'][0].z; sz = J['spine'][0].z; cz = J['chest'][0].z; nz = J['neck'][0].z; h2 = J['head'][0].z
    wide = {'hulk': 1.6, 'elite': 1.25}.get(kind, 1.0)
    # torso: ribbed, narrow waist
    add(seg('pelvis', (0, 0, hz - .08 * s), (0, 0, hz + .1 * s), .12 * s * wide, .1 * s * wide, sk, 12, scale=(1.1, .8)), 'hips')
    add(seg('waist', (0, 0, sz - .02), (0, 0, sz + .2 * s), .09 * s * wide, .14 * s * wide, sk, 12, scale=(1.1, .75)), 'spine')
    for i in range(4):
        add(bl.torus('rib', .1 * s * wide, .015 * s, (0, 0, sz + .03 * s + i * .045 * s), pl, maj=16, mn=5), 'spine')
    add(seg('chest', (0, 0, cz - .02), (0, 0, cz + .22 * s), .16 * s * wide, .19 * s * wide, sk, 14, scale=(1.15, .8)), 'chest')
    cw = min(wide, 1.2)
    add(bl.sphere('carapace', .17 * s * cw, (0, .09 * s * cw, cz + .1 * s), pl, 14, 10, scale=(1.25, .75, 1.0)), 'chest')
    for i in range(5):                                  # spines down the back
        add(seg('spine', (0, .13 * s * cw, cz + .2 * s - i * .08 * s), (0, .26 * s * cw, cz + .25 * s - i * .08 * s), .03 * s, .003, pl, 6), 'chest')
    add(bl.sphere('heart', .05 * s, (0, -.15 * s * wide, cz + .1 * s), gl, 10, 8), 'chest')
    # neck + head: elongated skull sweeping back, glowing eye slits, mandibles
    add(seg('neck', (0, 0, nz - .02), (0, .03 * s, nz + .12 * s), .06 * s, .05 * s, sk, 10), 'neck')
    if kind == 'hulk':
        add(bl.sphere('head', .12 * s, (0, -.04 * s, h2 + .06 * s), pl, 14, 10, scale=(1.2, 1, .8)), 'head')
        add(bl.box('eyes', (.14 * s, .02, .02 * s), (0, -.15 * s, h2 + .08 * s), gl), 'head')
    else:
        add(bl.sphere('skull', .1 * s, (0, -.01 * s, h2 + .1 * s), sk, 16, 12, scale=(.8, 1, .95)), 'head')
        add(seg('crest', (0, .03 * s, h2 + .12 * s), (0, .3 * s, h2 + .18 * s), .08 * s, .01, pl, 10, scale=(.7, 1)), 'head')
        for sx in (1, -1):
            add(bl.box('eye', (.04 * s, .02, .012 * s), (sx * .04 * s, -.095 * s, h2 + .12 * s), gl, rot=(0, sx * .3, 0)), 'head')
            add(seg('mandible', (sx * .04 * s, -.07 * s, h2 + .04 * s), (sx * .02 * s, -.15 * s, h2 - .04 * s), .018 * s, .004, pl, 6), 'head')
        if kind == 'elite':
            for i in range(5):
                a = -1 + i * .5
                add(seg('crown', (math.sin(a) * .07 * s, .0, h2 + .18 * s), (math.sin(a) * .16 * s, .05 * s, h2 + .38 * s), .02 * s, .002, gl, 6), 'head')
    # arms: long, clawed
    for side, sx in (('L', 1), ('R', -1)):
        a0, a1 = J['upperarm.' + side]; f0, f1 = J['forearm.' + side]; h0, h1 = J['hand.' + side]
        big = kind == 'mutant' and side == 'R'
        arm_k = {'hulk': 1.5, 'elite': 1.15}.get(kind, 1.0) * (1.6 if big else 1)
        add(seg('uarm', a0, a1, .055 * s * arm_k, .045 * s * arm_k, sk, 10), 'upperarm.' + side)
        add(bl.sphere('shoulder', .08 * s * arm_k, a0 + V((sx * .02, 0, .02)), pl, 12, 8, scale=(1.1, 1.1, .8)), 'upperarm.' + side)
        add(seg('farm', f0, f1, .05 * s * arm_k * (1.3 if kind == 'hulk' else 1), .04 * s * arm_k, sk, 10), 'forearm.' + side)
        if kind == 'hulk':
            add(seg('fplate', f0 + (f1 - f0) * .1, f1, .085 * s * arm_k, .075 * s * arm_k, pl, 10), 'forearm.' + side)
        if kind == 'swimmer':
            add(bl.box('fin', (.01, .12 * s, .2 * s), (f0 + f1) / 2 + V((sx * .05 * s, .05 * s, 0)), gl, rot=(.3, 0, 0)), 'forearm.' + side)
        if big:
            add(bl.sphere('growth', .1 * s, (f0 + f1) / 2 + V((sx * .05 * s, 0, 0)), ac, 10, 8, scale=(1, 1, 1.4)), 'forearm.' + side)
        add(bl.box('palm', (.05 * s, .07 * s, .07 * s), (h0 + h1) / 2, sk, bevel=.01), 'hand.' + side)
        if kind == 'elite' and side == 'R':
            add(seg('blade', h0, h1 + (h1 - h0) * 4, .03 * s, .004, gl, 6, scale=(.4, 1)), 'hand.' + side)
        else:
            for c in range(3):
                off = V(((c - 1) * .02 * s, -.01 * s, 0))
                add(seg('claw', h1 + off, h1 + off + V((0, -.03 * s, -.12 * s * (1.4 if lean else 1))), .012 * s, .002, pl, 6), 'hand.' + side)
        # legs: digitigrade look (back-swept shins with a raised heel spur)
        t0, t1 = J['thigh.' + side]; s0, s1 = J['shin.' + side]; q0, q1 = J['foot.' + side]
        lk = {'hulk': 1.4, 'elite': 1.15}.get(kind, 1.0)
        add(seg('thigh', t0, t1, .08 * s * lk, .06 * s * lk, sk, 12), 'thigh.' + side)
        add(bl.sphere('knee', .06 * s * lk, t1 + V((0, -.03 * s, 0)), pl, 10, 8), 'shin.' + side)
        add(seg('shin', s0, s1, .055 * s * lk, .035 * s * lk, sk, 10), 'shin.' + side)
        add(seg('calfspur', s0 + (s1 - s0) * .5, s0 + (s1 - s0) * .5 + V((0, .12 * s, .05 * s)), .03 * s, .003, pl, 6), 'shin.' + side)
        add(seg('foot', q0, q1, .045 * s * lk, .03 * s * lk, sk, 8, scale=(1.3, 1)), 'foot.' + side)
        for c in (-1, 1):
            add(seg('toe', q1 + V((c * .025 * s, 0, 0)), q1 + V((c * .04 * s, -.08 * s, -.01)), .015 * s, .003, pl, 6), 'foot.' + side)
    if kind == 'swimmer':
        add(bl.box('dorsal', (.012, .3 * s, .25 * s), (0, .2 * s, cz + .1 * s), gl, rot=(-.4, 0, 0)), 'chest')
        for i in range(6):
            add(bl.sphere('spot', .015 * s, ((i % 2 - .5) * .14 * s, -.13 * s, sz + i * .05 * s), gl, 6, 4), 'spine')
    if kind == 'mutant':
        for i in range(5):
            add(seg('vein', (.05 * s, -.14 * s, sz + i * .06 * s), (-.06 * s, -.13 * s, sz + .04 * s + i * .06 * s), .008 * s, .008 * s, ac, 5), 'spine')
        add(seg('tube', (.08 * s, .1 * s, cz + .2 * s), (.14 * s, .05 * s, sz), .015 * s, .015 * s, pl, 6), 'chest')


def build(kind):
    bl.reset()
    b = body(kind)
    M = mats(kind)
    build_parts(b, kind, M)
    objs = []
    for o, bone in b.parts:
        bl.apply_all(o)
        vg = o.vertex_groups.new(name=bone)
        vg.add(list(range(len(o.data.vertices))), 1.0, 'REPLACE')
        objs.append(o)
    mesh = bl.join(objs, 'Body_' + kind)
    arm = characters.make_armature(b, pole_angle=90)
    mesh.parent = arm
    md = mesh.modifiers.new('Armature', 'ARMATURE'); md.object = arm
    characters.animate(arm, b.s)
    bl.export('alien_%s.glb' % kind, animations=True)


if __name__ == '__main__':
    only = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    for k in KINDS:
        if not only or k in only:
            build(k)
