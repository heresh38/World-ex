"""Rigged characters: player_female, player_male, enemy_trooper, enemy_brute, npc_vendor.

One shared 20-bone skeleton. Armour is built from bevelled segments, each rigidly skinned to one bone
(segmented sci-fi plate armour, so no visible skinning artefacts). Arm poses for the "armed" clips are
solved with IK chains toward grip targets parented to the chest, then baked to plain keyframes.

Clips: Idle, Walk, Run, Jump, IdleRelaxed, WalkRelaxed, RunRelaxed, Sit, Death (players also get gendered gaits + Slide).
Recolourable material slots (by name): armor_primary, armor_secondary, undersuit, trim, visor, glow.
"""
import bpy, math, os, sys
from mathutils import Vector, Quaternion, Matrix
sys.path.insert(0, os.path.dirname(__file__))
import bl

FPS = 30


def seg(name, p0, p1, r0, r1, m, verts=12, bevel=0.0, scale=(1, 1)):
    """Tapered cylinder from p0 to p1 (world rest coords)."""
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    bpy.ops.mesh.primitive_cone_add(vertices=verts, radius1=r0, radius2=r1, depth=d.length, location=(p0 + p1) / 2)
    o = bpy.context.object
    o.scale = (scale[0], scale[1], 1)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    o.rotation_mode = 'QUATERNION'
    o.rotation_quaternion = d.to_track_quat('Z', 'Y')
    o = bl._finish(o, m, name, bevel, 1)
    bl.autosmooth(o, 40)
    return o


class Body:
    def __init__(self, kind):
        self.kind = kind
        self.parts = []   # (obj, bone)
        female = kind == 'female'
        brute = kind == 'brute'
        s = 1.0 if not female else .955
        if brute:
            s = 1.22
        self.s = s
        sh = .205 if female else .235       # shoulder half width
        hp = .118 if female else .108       # hip joint half width
        if brute:
            sh = .27
        z = lambda v: v * s
        J = {}
        J['hips'] = (Vector((0, 0, z(1.0))), Vector((0, 0, z(1.1))))
        J['spine'] = (Vector((0, 0, z(1.1))), Vector((0, 0, z(1.3))))
        J['chest'] = (Vector((0, 0, z(1.3))), Vector((0, 0, z(1.5))))
        J['neck'] = (Vector((0, 0, z(1.5))), Vector((0, 0, z(1.6))))
        J['head'] = (Vector((0, 0, z(1.6))), Vector((0, 0, z(1.82))))
        for side, sx in (('L', 1), ('R', -1)):
            sp = Vector((sx * sh, 0, z(1.45)))
            el = Vector((sx * (sh + .035), .01, z(1.45) - .31 * s))
            wr = Vector((sx * (sh + .05), 0, el.z - .27 * s))
            J['upperarm.' + side] = (sp, el)
            J['forearm.' + side] = (el, wr)
            J['hand.' + side] = (wr, wr + Vector((sx * .01, 0, -.1 * s)))
            hj = Vector((sx * hp, 0, z(.98)))
            kn = Vector((sx * (hp + .005), -.01, z(.53)))
            an = Vector((sx * (hp + .01), .01, z(.09)))
            J['thigh.' + side] = (hj, kn)
            J['shin.' + side] = (kn, an)
            J['foot.' + side] = (an, Vector((an.x, -.16 * s, .02)))
        self.J = J

    def add(self, o, bone):
        self.parts.append((o, bone))
        return o


def build_mesh(b, mats):
    """Armour pieces for the given body; returns list of (obj, bone)."""
    J, s, k = b.J, b.s, b.kind
    P, S2, U, T, V, G = (mats[n] for n in ('armor_primary', 'armor_secondary', 'undersuit', 'trim', 'visor', 'glow'))
    female, robot = k == 'female', k in ('trooper', 'brute')
    add = b.add
    # ---------- torso
    hz = J['hips'][0].z
    add(seg('pelvis', (0, 0, hz - .1 * s), (0, 0, hz + .12 * s), .15 * s, .14 * s, U, 14, scale=(1.15 if female else 1.1, .8)), 'hips')
    add(bl.box('belt', (.34 * s, .23 * s, .06 * s), (0, 0, hz + .08 * s), S2, bevel=.012), 'hips')
    add(bl.box('buckle', (.08 * s, .03, .05 * s), (0, -.12 * s, hz + .08 * s), T, bevel=.008), 'hips')
    add(bl.box('codpiece', (.14 * s, .05, .14 * s), (0, -.1 * s, hz - .02 * s), S2, bevel=.02), 'hips')
    for sx in (1, -1):
        add(bl.box('tasset', (.1 * s, .14 * s, .16 * s), (sx * .15 * s, -.02, hz - .03 * s), P, bevel=.02,
                   rot=(0, sx * -.18, 0)), 'hips')
    sz = J['spine'][0].z
    add(seg('abdomen', (0, 0, sz - .02), (0, 0, sz + .21 * s), .13 * s if not female else .115 * s, .15 * s,
            U, 14, scale=(1.1, .78)), 'spine')
    for i in range(3):
        add(bl.box('abplate%d' % i, (.16 * s, .04, .05 * s), (0, -.11 * s, sz + (.03 + i * .06) * s), S2, bevel=.01), 'spine')
    cz = J['chest'][0].z
    if female:
        add(seg('torso', (0, 0, cz - .02), (0, 0, cz + .2 * s), .15 * s, .17 * s, U, 16, scale=(1.15, .8)), 'chest')
        for sx in (1, -1):
            add(bl.sphere('bust', .085 * s, (sx * .068 * s, -.1 * s, cz + .08 * s), P, 16, 10, scale=(1, .9, .82)), 'chest')
        add(bl.box('chestplate', (.24 * s, .06, .1 * s), (0, -.13 * s, cz + .16 * s), P, bevel=.025), 'chest')
    else:
        w = 1.35 if k == 'brute' else 1.2
        add(seg('torso', (0, 0, cz - .02), (0, 0, cz + .21 * s), .16 * s, .2 * s, U, 16, scale=(w, .78)), 'chest')
        add(bl.box('chestplate', (.36 * s, .1, .2 * s), (0, -.13 * s, cz + .1 * s), P, bevel=.035, rot=(.12, 0, 0)), 'chest')
        add(bl.box('pecline', (.3 * s, .02, .02), (0, -.185 * s, cz + .05 * s), T, bevel=.005), 'chest')
    add(bl.box('collar', (.3 * s, .22 * s, .05 * s), (0, 0, cz + .2 * s), S2, bevel=.02), 'chest')
    # backpack / thruster pack
    add(bl.box('pack', (.26 * s, .12 * s, .26 * s), (0, .16 * s, cz + .08 * s), S2, bevel=.03), 'chest')
    for sx in (1, -1):
        add(bl.cyl('thruster', .035 * s, .1 * s, (sx * .08 * s, .2 * s, cz - .06 * s), mats['armor_secondary'], 10), 'chest')
        add(bl.cyl('thrglow', .026 * s, .01, (sx * .08 * s, .2 * s, cz - .115 * s), G, 10), 'chest')
    add(bl.box('packstrip', (.02, .02, .2 * s), (0, .225 * s, cz + .08 * s), G), 'chest')
    if robot:
        add(bl.box('core', (.1 * s, .03, .1 * s), (0, -.2 * s, cz + .1 * s), G, bevel=.01), 'chest')
    # ---------- neck / head
    nz = J['neck'][0].z
    add(seg('neck', (0, 0, nz - .03), (0, 0, nz + .1 * s), .055 * s, .05 * s, U, 10), 'neck')
    hz2 = J['head'][0].z
    if robot:
        add(bl.box('rhead', (.2 * s, .22 * s, .2 * s), (0, -.01, hz2 + .1 * s), P, bevel=.04), 'head')
        add(bl.box('reye', (.16 * s, .03, .035 * s), (0, -.12 * s, hz2 + .12 * s), G, bevel=.008), 'head')
        add(bl.box('rjaw', (.14 * s, .08, .06 * s), (0, -.08 * s, hz2 + .02 * s), S2, bevel=.015), 'head')
        add(bl.box('rfin', (.03, .18 * s, .08 * s), (0, .02, hz2 + .22 * s), S2, bevel=.01), 'head')
    else:
        hr = .115 * s
        add(bl.sphere('helmet', hr, (0, 0, hz2 + .11 * s), P, 20, 14, scale=(.92, 1.0, 1.08 if female else 1.0)), 'head')
        add(bl.sphere('visor', hr * .93, (0, -.035 * s, hz2 + .115 * s), V, 20, 12,
                      scale=(.88, .82, .5 if female else .42)), 'head')
        add(bl.box('visorline', (.15 * s, .02, .012), (0, -.105 * s, hz2 + .115 * s), G), 'head')
        if female:
            add(bl.box('crest', (.025, .2 * s, .06 * s), (0, .0, hz2 + .23 * s), S2, bevel=.012), 'head')
            # ponytail cable bundle out of the back of the helmet
            add(seg('tail', (0, .1 * s, hz2 + .14 * s), (0, .2 * s, hz2 - .12 * s), .035 * s, .015 * s, S2, 8), 'head')
            add(bl.torus('tailring', .035 * s, .01, (0, .115 * s, hz2 + .1 * s), T, rot=(1.2, 0, 0)), 'head')
        else:
            add(bl.box('mandible', (.17 * s, .09, .07 * s), (0, -.07 * s, hz2 + .03 * s), S2, bevel=.02), 'head')
            for sx in (1, -1):
                add(bl.box('earpiece', (.03, .08 * s, .07 * s), (sx * .105 * s, 0, hz2 + .11 * s), T, bevel=.01), 'head')
            add(bl.box('antenna', (.012, .012, .12 * s), (.085 * s, .05, hz2 + .25 * s), T), 'head')
    # ---------- limbs
    for side, sx in (('L', 1), ('R', -1)):
        a0, a1 = J['upperarm.' + side]
        add(seg('uarm', a0, a1, .055 * s, .048 * s, U, 10), 'upperarm.' + side)
        pad_s = 1.25 if k == 'brute' else (0.85 if female else 1.0)
        add(bl.sphere('pauldron', .085 * s * pad_s, a0 + Vector((sx * .02, 0, .02)), P, 14, 8,
                      scale=(1.05, 1.1, .8)), 'upperarm.' + side)
        add(bl.box('pauldtrim', (.02, .15 * s * pad_s, .02), a0 + Vector((sx * .085 * s * pad_s, 0, -.01)), T), 'upperarm.' + side)
        f0, f1 = J['forearm.' + side]
        add(seg('farm', f0, f1, .046 * s, .04 * s, U, 10), 'forearm.' + side)
        add(seg('gauntlet', f0 + (f1 - f0) * .25, f1 + (f0 - f1) * .05, .058 * s, .052 * s, S2, 10, bevel=0), 'forearm.' + side)
        add(bl.box('gstrip', (.012, .015, .12 * s), (f0 + f1) / 2 + Vector((sx * .055 * s, -.01, -.02)), G), 'forearm.' + side)
        add(bl.sphere('elbow', .045 * s, f0, P, 10, 6), 'forearm.' + side)
        h0, h1 = J['hand.' + side]
        add(bl.box('palm', (.05 * s, .085 * s, .09 * s), (h0 + h1) / 2 + Vector((0, 0, .01)), U, bevel=.012), 'hand.' + side)
        add(bl.box('knuckle', (.055 * s, .06 * s, .035 * s), (h0 + h1) / 2 + Vector((0, -.015, .015)), S2, bevel=.008), 'hand.' + side)
        t0, t1 = J['thigh.' + side]
        tw = 1.12 if female else 1.0
        add(seg('thigh', t0, t1, .082 * s * tw, .06 * s, U, 12), 'thigh.' + side)
        add(bl.box('thighplate', (.1 * s, .05, .2 * s), (t0 + t1) / 2 + Vector((sx * .01, -.065 * s, .02)), P, bevel=.02), 'thigh.' + side)
        add(bl.box('thighside', (.03, .1 * s, .16 * s), (t0 + t1) / 2 + Vector((sx * .07 * s, 0, 0)), S2, bevel=.01), 'thigh.' + side)
        s0, s1 = J['shin.' + side]
        add(seg('shin', s0, s1, .058 * s, .048 * s, U, 10), 'shin.' + side)
        add(seg('greave', s0 + (s1 - s0) * .12, s1 + (s0 - s1) * .1, .066 * s, .06 * s, P, 12), 'shin.' + side)
        add(bl.box('kneepad', (.085 * s, .06, .1 * s), s0 + Vector((0, -.055 * s, -.01)), S2, bevel=.02), 'shin.' + side)
        add(bl.box('kneeglow', (.04, .01, .012), s0 + Vector((0, -.088 * s, -.01)), G), 'shin.' + side)
        q0, q1 = J['foot.' + side]
        add(bl.box('boot', (.1 * s, .24 * s, .09 * s), Vector((q0.x, -.05 * s, .045)), S2, bevel=.025), 'foot.' + side)
        add(bl.box('sole', (.105 * s, .25 * s, .025), Vector((q0.x, -.05 * s, .0125)), mats['sole']), 'foot.' + side)
        add(bl.box('toecap', (.09 * s, .06, .06 * s), Vector((q0.x, -.15 * s, .05)), P, bevel=.02), 'foot.' + side)


def make_armature(b, pole_angle=-90):
    ad = bpy.data.armatures.new('rig')
    arm = bpy.data.objects.new('Armature', ad)
    bpy.context.scene.collection.objects.link(arm)
    bpy.context.view_layer.objects.active = arm
    arm.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    eb = ad.edit_bones
    root = eb.new('root'); root.head = (0, 0, 0); root.tail = (0, .2, 0)
    parent = {'hips': 'root', 'spine': 'hips', 'chest': 'spine', 'neck': 'chest', 'head': 'neck'}
    for side in 'LR':
        parent.update({'upperarm.' + side: 'chest', 'forearm.' + side: 'upperarm.' + side,
                       'hand.' + side: 'forearm.' + side, 'thigh.' + side: 'hips',
                       'shin.' + side: 'thigh.' + side, 'foot.' + side: 'shin.' + side})
    order = ['hips', 'spine', 'chest', 'neck', 'head'] + [n + '.' + sd for sd in 'LR' for n in
                                                         ('upperarm', 'forearm', 'hand', 'thigh', 'shin', 'foot')]
    for n in order:
        e = eb.new(n); e.head, e.tail = b.J[n]; e.roll = 0
        e.parent = eb[parent[n]]
        e.use_connect = n in ('spine', 'chest', 'neck', 'head') or n.startswith(('forearm', 'hand', 'shin', 'foot'))
    # IK helper bones (targets/poles) parented to chest; not skinned
    s = b.s
    sh = b.J['upperarm.R'][0]
    hand_r = Vector((-.13 * s, -.24 * s, 1.22 * s))
    hand_l = Vector((-.055 * s, -.47 * s, 1.27 * s))
    for n, p, par in (('ik_hand.R', hand_r, 'chest'), ('ik_hand.L', hand_l, 'chest'),
                      ('pole.R', Vector((-.55 * s, .35, 1.0 * s)), 'chest'),
                      ('pole.L', Vector((.45 * s, .1, 1.0 * s)), 'chest')):
        e = eb.new(n); e.head = p; e.tail = p + Vector((0, 0, .08)); e.parent = eb[par]
    bpy.ops.object.mode_set(mode='POSE')
    for pb in arm.pose.bones:
        pb.rotation_mode = 'QUATERNION'
    for side in 'LR':
        c = arm.pose.bones['forearm.' + side].constraints.new('IK')
        c.name = 'IK'
        c.target = arm; c.subtarget = 'ik_hand.' + side
        c.pole_target = arm; c.pole_subtarget = 'pole.' + side
        c.pole_angle = math.radians(pole_angle)
        c.chain_count = 2
        c.influence = 0.0
    bpy.ops.object.mode_set(mode='OBJECT')
    arm.select_set(False)
    return arm


# ------------------------------------------------------------------ animation
def wq(arm, bone, rots):
    """rots: list of (axis, deg) in the armature rest frame, applied in order -> pose-bone local quaternion."""
    q = Quaternion()
    for ax, d in rots:
        q = Quaternion(Vector(ax), math.radians(d)) @ q
    rr = arm.data.bones[bone].matrix_local.to_quaternion()
    return rr.inverted() @ q @ rr


X, Y, Z = (1, 0, 0), (0, 1, 0), (0, 0, 1)


# Gait styles for the player bodies (None = the shared neutral gait used by enemies and NPC rigs).
#   stance: thigh abduction (+ wider, - narrower / cross-over), roll: pelvis roll, yaw: pelvis yaw, sway: lateral hip
#   shift (m), counter: chest counter-rotation, bob: vertical bob scale, impact: heel-strike dip, arm: arm swing scale,
#   abd: arm abduction, bend: elbow bend
STYLES = {
    None: dict(stance=0, roll=0, yaw=1.0, sway=0, counter=0, bob=1.0, impact=0, arm=1.0, abd=7, bend=12),
    'male': dict(stance=3.5, roll=1.5, yaw=1.1, sway=.006, counter=7, bob=1.3, impact=.008, arm=1.25, abd=12, bend=16),
    'female': dict(stance=-2.6, roll=5.5, yaw=1.45, sway=.016, counter=2.5, bob=.7, impact=0, arm=.8, abd=4, bend=20),
}


def pose_fn(clip, style=None):
    """Returns f(phase)->dict(bone -> rots or ('loc', vec)) plus IK influence."""
    S = math.sin
    T = 2 * math.pi
    G = STYLES[style]

    def legs(p, amp, knee, lift=0.0):
        d = {}
        for side, off, sx in (('L', 0, 1), ('R', math.pi, -1)):
            ph = T * p + off
            sw = amp * S(ph)                     # + = forward
            kb = knee * max(0.0, S(ph + 1.2)) + 6  # knee bends during forward swing
            d['thigh.' + side] = ([(Y, -sx * G['stance'])] if G['stance'] else []) + [(X, -sw - lift)]
            d['shin.' + side] = [(X, kb + lift * 1.6)]
            d['foot.' + side] = [(X, -(kb - sw) * .35)]
        return d

    def arms_relaxed(p, amp):
        d = {}
        amp = amp * G['arm']
        for side, off, sx in (('L', math.pi, 1), ('R', 0, -1)):
            sw = amp * S(T * p + off)
            d['upperarm.' + side] = [(Y, -sx * G['abd']), (X, -sw)]
            d['forearm.' + side] = [(X, -G['bend'] - max(0, sw) * .8)]
            d['hand.' + side] = [(X, -5), (Y, sx * 4 * S(T * p + off)) if style == 'female' else (X, 0)]
        return d

    def gait(d, p, loc, k):
        """Pelvis roll/yaw/sway and chest counter-rotation for a walk (k=1) or run (k~1.6)."""
        if style is None:
            return
        yaw = (5 * k) * G['yaw'] * S(T * p)
        roll = G['roll'] * math.cos(T * p) * (1 if k < 1.3 else .6)
        d['hips'] = [(Z, yaw), (Y, roll)] + ([(X, 8)] if k > 1.3 else [])
        d['spine'] = [(Z, -yaw * .7), (Y, -roll * .8), (X, 3 if k < 1.3 else 6)]
        loc.x = G['sway'] * S(T * p) * (1 if k < 1.3 else .5)
        if G['impact']:
            ph = (2 * p) % 1.0
            loc.z -= G['impact'] * k * math.exp(-((ph - .25) / .07) ** 2)

    def f(p):
        d = {}; ik = 1.0; loc = Vector((0, 0, 0)); ry = 0
        if clip in ('Idle', 'IdleRelaxed'):
            b = S(T * p)
            d['spine'] = [(X, 1.5 * b)]
            d['chest'] = [(X, 1.0 * b)]
            d['head'] = [(X, -1.5 * b), (Z, 4 * S(T * p * 1))]
            d.update({'thigh.L': [(Y, -3)], 'thigh.R': [(Y, 3)], 'shin.L': [(X, 4)], 'shin.R': [(X, 4)]})
            loc.z = -.008 * (1 + b) - .02
            if clip == 'IdleRelaxed':
                ik = 0.0; d.update(arms_relaxed(p, 1.5))
            else:
                d['chest'] = [(X, 4 + b), (Z, -14)]; d['spine'] = [(Z, -8)]; d['head'] = [(Z, 20), (X, -2)]
        elif clip in ('Walk', 'WalkRelaxed'):
            d.update(legs(p, 24 if style != 'female' else 22, 34))
            loc.z = .022 * G['bob'] * math.cos(2 * T * p) - .03
            d['hips'] = [(Z, 5 * S(T * p))]
            d['spine'] = [(Z, -4 * S(T * p)), (X, 3)]
            gait(d, p, loc, 1.0)
            cy = -G['counter'] * S(T * p)
            if clip == 'WalkRelaxed':
                ik = 0.0; d.update(arms_relaxed(p, 20))
                if G['counter']:
                    d['chest'] = [(Z, cy)]
            else:
                d['chest'] = [(X, 4), (Z, -12 + cy * .4)]; d['head'] = [(Z, 16 - cy * .4)]
        elif clip in ('Run', 'RunRelaxed'):
            d.update(legs(p, 42 if style != 'female' else 38, 78 if style != 'female' else 86))
            loc.z = .045 * G['bob'] * math.cos(2 * T * p) - .06
            d['hips'] = [(Z, 8 * S(T * p)), (X, 8)]
            d['spine'] = [(Z, -7 * S(T * p)), (X, 6)]
            gait(d, p, loc, 1.6)
            cy = -G['counter'] * 1.3 * S(T * p)
            if clip == 'RunRelaxed':
                ik = 0.0; d.update(arms_relaxed(p, 50))
                for side, sx in (('L', 1), ('R', -1)):
                    d['forearm.' + side] = [(X, -70 - (10 if style == 'male' else 0) - (8 if style == 'female' else 0))]
                    if style == 'female':      # arms closer to the body, forearms swing across a little
                        d['upperarm.' + side] = [(Y, -sx * 2)] + d['upperarm.' + side][1:] + [(Z, sx * 8)]
                if G['counter']:
                    d['chest'] = [(Z, cy), (X, 4)]
            else:
                d['chest'] = [(X, 6), (Z, -12 + cy * .4)]; d['head'] = [(X, -10), (Z, 14 - cy * .4)]
        elif clip == 'Jump':
            if style == 'male':      # powerful tuck, knees apart
                d.update({'thigh.L': [(Y, -6), (X, -58)], 'shin.L': [(X, 88)], 'thigh.R': [(Y, 6), (X, -8)], 'shin.R': [(X, 48)],
                          'foot.L': [(X, -12)], 'spine': [(X, 10)], 'chest': [(X, 6), (Z, -12)], 'head': [(X, -6)]})
                loc.z = -.04
            elif style == 'female':  # knees together, trailing leg tucked behind, toes pointed
                d.update({'thigh.L': [(Y, 3), (X, -46)], 'shin.L': [(X, 92)], 'thigh.R': [(Y, -3), (X, -6)], 'shin.R': [(X, 74)],
                          'foot.L': [(X, 22)], 'foot.R': [(X, 30)], 'hips': [(Z, -6)], 'spine': [(X, 3), (Z, 4)],
                          'chest': [(X, 2), (Z, -12)]})
                loc.z = -.01
            else:
                d.update({'thigh.L': [(X, -50)], 'shin.L': [(X, 75)], 'thigh.R': [(X, -10)], 'shin.R': [(X, 40)],
                          'foot.L': [(X, -15)], 'spine': [(X, 6)], 'chest': [(X, 4), (Z, -12)]})
                loc.z = -.02
        elif clip == 'Slide':
            # running slide: lead leg out in front, the other tucked under, torso leaning back, left hand trailing low
            v = S(T * p)
            d.update({'hips': [(X, -24), (Z, 6)], 'thigh.L': [(Y, -4), (X, -56)], 'shin.L': [(X, 8)], 'foot.L': [(X, -12)],
                      'thigh.R': [(Y, 6), (X, -34)], 'shin.R': [(X, 112)], 'foot.R': [(X, 20)],
                      'spine': [(X, -6), (Z, -4)], 'chest': [(X, -4), (Z, -6)], 'head': [(X, 22 + .8 * v), (Z, 6)]})
            ik = 0.0
            d['upperarm.L'] = [(Y, -38), (X, 28)]; d['forearm.L'] = [(X, -12)]; d['hand.L'] = [(Y, -10)]
            d['upperarm.R'] = [(X, -48), (Y, 22)]; d['forearm.R'] = [(X, -42)]; d['hand.R'] = [(X, -10)]
            loc.z = -.66 + .004 * v; loc.y = .02
        elif clip == 'Sit':
            d.update({'thigh.L': [(X, -88), (Y, -4)], 'thigh.R': [(X, -88), (Y, 4)], 'shin.L': [(X, 82)],
                      'shin.R': [(X, 82)], 'foot.L': [(X, -8)], 'foot.R': [(X, -8)], 'spine': [(X, -4)],
                      'head': [(X, 3 * S(T * p))]})
            loc.z = -.47 * 1.0
            ik = 0.0
            for side, sx in (('L', 1), ('R', -1)):
                d['upperarm.' + side] = [(X, -40), (Y, sx * 6)]
                d['forearm.' + side] = [(X, -55)]
        elif clip == 'Death':
            t = min(1.0, p * 1.6)
            e = t * t * (3 - 2 * t)
            d['hips'] = [(X, -80 * e)]
            loc.z = -.0 - .85 * e
            loc.y = .35 * e
            d.update({'thigh.L': [(X, -25 * e)], 'thigh.R': [(X, -5 * e)], 'shin.L': [(X, 30 * e)],
                      'shin.R': [(X, 10 * e)], 'head': [(X, -20 * e), (Z, 25 * e)]})
            ik = 0.0
            for side, sx in (('L', 1), ('R', -1)):
                d['upperarm.' + side] = [(Y, -sx * 55 * e), (X, -20 * e)]
                d['forearm.' + side] = [(X, -30 * e)]
        return d, ik, loc
    return f


CLIPS = {'Idle': 2.4, 'Walk': 1.05, 'Run': .68, 'Jump': .5, 'IdleRelaxed': 3.0, 'WalkRelaxed': 1.1,
         'RunRelaxed': .7, 'Sit': 4.0, 'Death': 1.2}
PLAYER_CLIPS = dict(CLIPS, Slide=.8)


def animate(arm, scale, style=None, clips=None):
    """style: None (neutral, shared by enemies/NPC rigs), 'male' or 'female' (player bodies, with the extra Slide clip)."""
    arm.animation_data_create()
    acts = []
    for clip, dur in (clips or CLIPS).items():
        act = bpy.data.actions.new(clip)
        act.use_fake_user = True
        arm.animation_data.action = act
        f = pose_fn(clip, style)
        nfr = max(2, round(dur * FPS))
        steps = 8 if clip not in ('Death',) else 12
        for i in range(steps + 1):
            p = i / steps
            fr = 1 + p * nfr
            d, ik, loc = f(p % 1.0 if clip != 'Death' else p)
            for pb in arm.pose.bones:
                if pb.name.startswith(('ik_', 'pole')):
                    continue
                if pb.name in d:
                    pb.rotation_quaternion = wq(arm, pb.name, d[pb.name])
                else:
                    pb.rotation_quaternion = Quaternion()
                pb.keyframe_insert('rotation_quaternion', frame=fr)
            hb = arm.pose.bones['hips']
            # hips bone local frame: Y along +Z world; location in bone space
            rr = arm.data.bones['hips'].matrix_local.to_quaternion()
            hb.location = rr.inverted() @ (loc * scale)
            hb.keyframe_insert('location', frame=fr)
            for side in 'LR':
                c = arm.pose.bones['forearm.' + side].constraints['IK']
                c.influence = ik
                c.keyframe_insert('influence', frame=fr)
        acts.append((act, nfr))
    # bake IK into plain FK keys for every clip, then drop the helpers' influence
    bpy.context.view_layer.objects.active = arm
    arm.select_set(True)
    bpy.ops.object.mode_set(mode='POSE')
    for act, nfr in acts:
        arm.animation_data.action = act
        bpy.ops.pose.select_all(action='SELECT')
        bpy.ops.nla.bake(frame_start=1, frame_end=nfr + 1, step=1, only_selected=False, visual_keying=True,
                         clear_constraints=False, use_current_action=True, bake_types={'POSE'})
        # remove constraint influence curves from the baked action (they are not exportable/needed)
    bpy.ops.object.mode_set(mode='OBJECT')
    for side in 'LR':
        pb = arm.pose.bones['forearm.' + side]
        pb.constraints.remove(pb.constraints['IK'])
    for act, nfr in acts:
        try:
            fcs = act.fcurves
        except AttributeError:
            fcs = None
        if fcs is not None:
            for fc in list(fcs):
                if 'constraints' in fc.data_path or 'ik_' in fc.data_path or 'pole' in fc.data_path:
                    fcs.remove(fc)
        else:  # layered actions (Blender 4.4+)
            for layer in act.layers:
                for strip in layer.strips:
                    for cb in strip.channelbags:
                        for fc in list(cb.fcurves):
                            if 'constraints' in fc.data_path or 'ik_' in fc.data_path or 'pole' in fc.data_path:
                                cb.fcurves.remove(fc)
    arm.animation_data.action = bpy.data.actions['Idle']
    return acts


def build(kind, fname, colors):
    bl.reset()
    pr = dict(colors)
    mats = {
        'armor_primary': bl.mat('armor_primary', pr['primary'], pr.get('pm', .1), pr.get('pr', .35)),
        'armor_secondary': bl.mat('armor_secondary', pr['secondary'], .75, .38),
        'undersuit': bl.mat('undersuit', pr['under'], 0.0, .75),
        'trim': bl.mat('trim', pr['trim'], 1.0, .25),
        'visor': bl.mat('visor', pr['visor'], .9, .06, emit=pr['visor_e'], strength=.6),
        'glow': bl.mat('glow', pr['glow'], 0, .4, emit=pr['glow'], strength=5),
        'sole': bl.mat('sole', '#141414', 0, .9),
    }
    b = Body(kind)
    build_mesh(b, mats)
    # rigid skin: every part gets a vertex group for its bone, then join
    objs = []
    for o, bone in b.parts:
        bl.apply_all(o)
        vg = o.vertex_groups.new(name=bone)
        vg.add(list(range(len(o.data.vertices))), 1.0, 'REPLACE')
        objs.append(o)
    body = bl.join(objs, 'Body_' + kind)
    arm = make_armature(b)
    body.parent = arm
    md = body.modifiers.new('Armature', 'ARMATURE'); md.object = arm
    animate(arm, b.s)
    # sanity: report wrist positions in the Idle pose (should be in front of the chest)
    bpy.context.scene.frame_set(1)
    arm.animation_data.action = bpy.data.actions['Idle']
    bpy.context.view_layer.update()
    for side in 'LR':
        pb = arm.pose.bones['hand.' + side]
        print('  %s hand.%s head (armed idle) = %s' % (kind, side, tuple(round(v, 2) for v in (arm.matrix_world @ pb.head))))
    bl.export(fname, animations=True)


SETS = {
    'female': ('player_female.glb', dict(primary='#e8e2d4', secondary='#3a3f47', under='#22262c', trim='#c79a45',
                                         visor='#10161c', visor_e='#1ad8ff', glow='#1ad8ff')),
    'male': ('player_male.glb', dict(primary='#e8e2d4', secondary='#3a3f47', under='#22262c', trim='#c79a45',
                                     visor='#10161c', visor_e='#ffae2f', glow='#ffae2f')),
    'trooper': ('enemy_trooper.glb', dict(primary='#2c2f36', secondary='#5d1c1c', under='#15161a', trim='#8a8f99',
                                          visor='#000000', visor_e='#ff3326', glow='#ff3326', pm=.6, pr=.4)),
    'brute': ('enemy_brute.glb', dict(primary='#3b2a22', secondary='#1d1f24', under='#121316', trim='#c79a45',
                                      visor='#000000', visor_e='#ff7a1a', glow='#ff7a1a', pm=.7, pr=.35)),
    'vendor': ('npc_vendor.glb', dict(primary='#2a4a6a', secondary='#c79a45', under='#1d2128', trim='#e8e2d4',
                                      visor='#0c1418', visor_e='#7dffb0', glow='#7dffb0')),
}

if __name__ == '__main__':
    only = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    for kind, (fname, cols) in SETS.items():
        if only and kind not in only:
            continue
        build('male' if kind == 'vendor' else kind, fname, cols)
