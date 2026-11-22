"""The Sarketh's motion (the owner's design: "agile movement", digitigrade legs, a soldier's species): the clips a
creature plays in the game (ASOEnemy::LoadContent: Idle, Walk, Run, Attack, Death; a species' ActionClips), on the
skeleton of tools/blender/skr/anatomy.py, baked by bake() with the feet ON the ground.

A Sarketh stands and moves upright and coiled: its legs never straighten (the knee forward, the hock back, the weight
on the ball of the foot and the toes), the trunk is carried a little forward over the hips, the head level and still
while the body moves under it (a hunter's head), the steps quick and light. Nothing peaks together and nothing runs
on one sine (the player's rule for motion that does not read as a machine): every bone lags the hips a little, the
two sides are not copies.

Every clip is f(p) -> {bone: [(axis, degrees)]} in the armature's rest frame (fleshkit / characters.wq), each bone
relative to its parent as posed; the hips' height is found by bake(): the lowest toe of the foot that bears the
weight is put on the ground at every frame (a planted foot does not sink or float whatever the leg's angles are).

Clips (seconds, loop):
  Idle    3.2  loop   coiled, breathing, the weight shifting, the head scanning; claws loose
  Walk    1.0  loop   ~2 m/s: quick light steps on the toes, the trunk turning against the hips
  Run     0.62 loop   ~5.5 m/s: long reaching strides, the trunk low and forward, the arms pumping
  Attack  0.9         a claw strike with the right hand: the trunk winds, the arm whips across and down
  Death   1.5         the legs fold, the body falls back and to its side
  Cast    0.8         the right arm drawn back and thrust out (a bolt thrown)
  Blink   0.36        a crouch and a spring to the side
  Slam    1.3         both fists raised overhead and brought down into the ground in front (lands at .82 s)
  Sweep   1.2         the right arm drawn back across the body and swept round wide (lands at .78 s)
  Barrage 1.0         set, the right arm raised and thrust out as the volley goes (at .55 s)
  Shield  1.2         the forearms brought up crossed before the chest, the body set behind them
  Brace   0.8         the feet set wide, the weight forward and down behind the gun (a heavy gunner opening fire)
(the last five are the heavy ranks': their times are the kits' clipLead, Data/game_data.json "kits")
"""
import math

import bpy
from mathutils import Matrix, Quaternion, Vector

X, Y, Z = (1, 0, 0), (0, 1, 0), (0, 0, 1)
TAU = 2 * math.pi
FPS = 30
S, C = math.sin, math.cos


def smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def bell(p, at, w):
    """a smooth bump (0..1) centred on `at`, `w` wide (wraps)"""
    d = (p - at + .5) % 1.0 - .5
    return math.exp(-(d / w) ** 2)


def ramp(p, a, b):
    return smooth((p - a) / max(b - a, 1e-6))


def leg_cycle(phi, swing_at=.62, reach=20.0, push=16.0, lift=42.0, soft=12.0):
    """one leg's angles at its own phase phi (0..1): the foot lands at 0, bears the weight until swing_at, then swings
    forward. Returns (thigh, knee, hock, toes) in degrees about X (thigh: - forward; knee: + bends; hock: - lifts the
    heel; toes: kept flat on the ground through the stance, hanging through the swing)."""
    phi %= 1.0
    if phi < swing_at:
        t = phi / swing_at
        thigh = -reach + (reach + push) * t                 # forward at the landing, back at the push-off
        knee = soft + 6 * S(math.pi * t)                     # the weight taken and given back
        hock = -6 - 14 * smooth((t - .55) / .45)             # the heel rises into the push-off
        stance = True
    else:
        t = (phi - swing_at) / (1 - swing_at)
        thigh = push - (reach + push) * (.5 - .5 * C(math.pi * t))
        knee = soft + lift * S(math.pi * t) ** 1.3            # folded through the swing (the foot clears the ground)
        hock = -20 + 26 * smooth(t)                          # the foot reaches forward to land
        stance = False
    return thigh, knee, hock, stance


def flat_toes(thigh, knee, hock):
    """the toes' angle that keeps them level with the ground while the rest of the leg turns over them"""
    return -(thigh + knee + hock)


def idle(p):
    b = S(TAU * p)                                           # breath
    w = S(TAU * p + .7)                                      # the weight drifting side to side, behind the breath
    scan = 9 * S(TAU * p * 1 + 1.9) + 4 * S(TAU * p * 2 + .3)
    d = {
        'hips': [(Y, 1.5 * w), (Z, 2 * w)],
        'spine': [(X, 9 + 1.2 * b), (Y, -1.2 * w)],
        'chest': [(X, 6 + 1.6 * b), (Z, -2 * w)],
        'neck': [(X, -6 - .8 * b)],
        'head': [(X, -5), (Z, scan)],
        # (the sheet: the arms held off the body, the claws clear of the thighs)
        'upperarm.L': [(X, -8 + 2 * b), (Y, -9)], 'forearm.L': [(X, -26)], 'hand.L': [(X, -10), (Z, 6)],
        'upperarm.R': [(X, -6 + 2 * b), (Y, 9)], 'forearm.R': [(X, -30)], 'hand.R': [(X, -8), (Z, -8)],
    }
    for s, side in (('L', 1), ('R', -1)):
        lean = 2 * w * side                                  # the leg that takes the weight bends a little more
        thigh, knee, hock = -5 - lean, 11 + 2 * lean, -6
        # (the sheet's stance: the feet well apart, each leg out about six degrees, the foot turned back level)
        d[f'thigh.{s}'] = [(X, thigh), (Y, -6 * side)]
        d[f'shin.{s}'] = [(X, knee)]
        d[f'foot.{s}'] = [(X, hock), (Y, 6 * side)]
        d[f'toes.{s}'] = [(X, flat_toes(thigh, knee, hock))]
    return d, 'both'


def gait(p, run):
    ph = TAU * p
    sw = (.60, 18, 14, 28, 9) if not run else (.42, 34, 22, 68, 16)
    swing_at, reach, push, lift, soft = sw
    d = {}
    planted = []
    for s, off, side in (('L', 0.0, 1), ('R', .5, -1)):
        phi = (p + off) % 1.0
        thigh, knee, hock, stance = leg_cycle(phi, swing_at, reach, push, lift, soft)
        thigh *= 1.0 if side == 1 else .96                   # the two sides are not copies
        toes = flat_toes(thigh, knee, hock) if stance else 18 * S(math.pi * (phi - swing_at) / (1 - swing_at))
        d[f'thigh.{s}'] = [(X, thigh), (Y, -2.5 * side)]
        d[f'shin.{s}'] = [(X, knee)]
        d[f'foot.{s}'] = [(X, hock)]
        d[f'toes.{s}'] = [(X, toes)]
        if stance:
            planted.append(s)
    lean = 11 if not run else 22
    twist = (7 if not run else 11) * S(ph + .25)            # the trunk turns against the hips, a beat behind
    d['hips'] = [(Z, -(4 if not run else 6) * S(ph)), (Y, (2 if not run else 3) * S(ph + .5))]
    d['spine'] = [(X, lean * .45 + 1.5 * S(2 * ph + .4)), (Z, twist * .5)]
    d['chest'] = [(X, lean * .35), (Z, twist * .7)]
    d['neck'] = [(X, -lean * .45), (Z, -twist * .6)]
    d['head'] = [(X, -lean * .3 + 1.0 * S(2 * ph + 1.0)), (Z, -twist * .5)]      # the head stays on the line
    arm = 16 if not run else 34
    for s, side in (('L', 1), ('R', -1)):
        a = arm * S(ph + (math.pi if side == 1 else 0) + .3)                   # against the leg of its own side
        d[f'upperarm.{s}'] = [(X, -6 + a), (Y, -4 * side)]
        d[f'forearm.{s}'] = [(X, -(28 if not run else 64) - .35 * max(0.0, -a))]
        d[f'hand.{s}'] = [(X, -10)]
    return d, planted or ['L', 'R']


def walk(p):
    return gait(p, False)


def run(p):
    return gait(p, True)


def stance_legs(d, crouch=0.0, wide=0.0):
    for s, side in (('L', 1), ('R', -1)):
        thigh, knee, hock = -5 - 24 * crouch, 11 + 48 * crouch, -6 - 12 * crouch
        d[f'thigh.{s}'] = [(X, thigh), (Y, -(3 + wide) * side)]
        d[f'shin.{s}'] = [(X, knee)]
        d[f'foot.{s}'] = [(X, hock)]
        d[f'toes.{s}'] = [(X, flat_toes(thigh, knee, hock))]
    return d


def attack(p):
    wind = ramp(p, 0.0, .34) * (1 - ramp(p, .34, .46))
    strike = ramp(p, .34, .5) * (1 - ramp(p, .62, 1.0))
    back = 1 - ramp(p, .62, 1.0)
    d = {
        'spine': [(X, 8 + 6 * strike), (Z, 22 * wind - 26 * strike)],
        'chest': [(X, 6 + 4 * strike), (Z, 18 * wind - 24 * strike)],
        'neck': [(X, -8), (Z, -10 * wind + 12 * strike)],
        'head': [(X, -4), (Z, -12 * wind + 14 * strike)],
        'upperarm.R': [(X, -20 + 70 * wind - 95 * strike), (Y, 10 + 40 * wind - 30 * strike), (Z, 10 * wind)],
        'forearm.R': [(X, -60 * wind - 15 * strike - 30 * (1 - back))],
        'hand.R': [(X, -10 - 30 * strike)],
        'upperarm.L': [(X, -30 - 10 * strike), (Y, -14)], 'forearm.L': [(X, -55)], 'hand.L': [(X, -10)],
        'hips': [(Z, 8 * wind - 10 * strike)],
    }
    stance_legs(d, crouch=.35 * wind + .55 * strike, wide=4)
    return d, 'both'


def death(p):
    fold = ramp(p, 0.0, .45)
    fall = ramp(p, .25, .8)
    lie = ramp(p, .6, 1.0)
    d = {
        'hips': [(X, -78 * fall), (Y, 12 * fall)],
        'spine': [(X, -12 * fold + 10 * lie), (Z, 8 * fall)],
        'chest': [(X, -10 * fold + 6 * lie)],
        'neck': [(X, -20 * fold + 18 * lie)],
        'head': [(X, -16 * fold + 20 * lie), (Z, 25 * lie)],
        'upperarm.L': [(X, 30 * fold), (Y, -40 * fall)], 'forearm.L': [(X, -30 + 20 * lie)],
        'upperarm.R': [(X, 40 * fold), (Y, 55 * fall)], 'forearm.R': [(X, -40 + 30 * lie)],
    }
    for s, side in (('L', 1), ('R', -1)):
        thigh = -14 - 50 * fold + 30 * lie * (1 if side == 1 else .6)
        knee = 30 + 70 * fold - 30 * lie
        hock = -14 - 20 * fold
        d[f'thigh.{s}'] = [(X, thigh), (Y, -6 * side * fall)]
        d[f'shin.{s}'] = [(X, knee)]
        d[f'foot.{s}'] = [(X, hock)]
        d[f'toes.{s}'] = [(X, 10 * lie)]
    return d, 'all'


def cast(p):
    draw = ramp(p, 0.0, .4) * (1 - ramp(p, .4, .5))
    throw = ramp(p, .4, .55) * (1 - ramp(p, .7, 1.0))
    d = {
        'spine': [(X, 8 + 5 * throw), (Z, 16 * draw - 20 * throw)],
        'chest': [(X, 6), (Z, 14 * draw - 16 * throw)],
        'neck': [(X, -8), (Z, -8 * draw + 10 * throw)],
        'head': [(X, -4), (Z, -8 * draw + 10 * throw)],
        'upperarm.R': [(X, -10 + 40 * draw - 90 * throw), (Y, 20 * draw + 6 * throw)],
        'forearm.R': [(X, -80 * draw - 5 * throw)],
        'hand.R': [(X, -30 * draw + 10 * throw)],
        'upperarm.L': [(X, -40 - 20 * draw), (Y, -12)], 'forearm.L': [(X, -50)],
    }
    stance_legs(d, crouch=.3 * draw + .4 * throw, wide=5)
    return d, 'both'


def blink(p):
    dip = ramp(p, 0.0, .35) * (1 - ramp(p, .35, .7))
    spring = ramp(p, .35, .6) * (1 - ramp(p, .75, 1.0))
    d = {
        'hips': [(Y, 18 * spring)],
        'spine': [(X, 14 + 10 * dip), (Y, -10 * spring)],
        'chest': [(X, 8 + 6 * dip)],
        'neck': [(X, -14 * dip)], 'head': [(X, -8 * dip)],
        'upperarm.L': [(X, -20), (Y, -30 * spring)], 'forearm.L': [(X, -50)],
        'upperarm.R': [(X, -20), (Y, 20 * spring)], 'forearm.R': [(X, -50)],
    }
    stance_legs(d, crouch=.9 * dip + .2 * spring, wide=6 + 10 * spring)
    return d, 'both'


def slam(p):
    up = ramp(p, 0.0, .50) * (1 - ramp(p, .52, .63))
    down = ramp(p, .52, .63) * (1 - ramp(p, .82, 1.0))
    d = {
        'spine': [(X, 6 - 16 * up + 30 * down)],
        'chest': [(X, 4 - 10 * up + 16 * down)],
        'neck': [(X, -6 + 8 * up - 14 * down)], 'head': [(X, -4 + 4 * up - 8 * down)],
        'upperarm.L': [(X, -20 - 140 * up - 34 * down), (Y, -12 + 8 * up)], 'forearm.L': [(X, -40 + 22 * up - 8 * down)],
        'upperarm.R': [(X, -20 - 140 * up - 34 * down), (Y, 12 - 8 * up)], 'forearm.R': [(X, -40 + 22 * up - 8 * down)],
        'hand.L': [(X, -20)], 'hand.R': [(X, -20)],
    }
    stance_legs(d, crouch=.15 * up + .85 * down, wide=8)
    return d, 'both'


def sweep(p):
    wind = ramp(p, 0.0, .55) * (1 - ramp(p, .55, .66))
    swing = ramp(p, .55, .70) * (1 - ramp(p, .84, 1.0))
    d = {
        'hips': [(Z, 14 * wind - 18 * swing)],
        'spine': [(X, 8), (Z, 26 * wind - 34 * swing)],
        'chest': [(X, 6), (Z, 22 * wind - 30 * swing)],
        'neck': [(X, -8), (Z, -16 * wind + 20 * swing)], 'head': [(X, -4), (Z, -12 * wind + 16 * swing)],
        'upperarm.R': [(X, -60 - 10 * swing), (Y, 20 + 34 * wind - 12 * swing)], 'forearm.R': [(X, -20 - 24 * wind)],
        'upperarm.L': [(X, -40), (Y, -20)], 'forearm.L': [(X, -60)],
    }
    stance_legs(d, crouch=.3 * wind + .5 * swing, wide=10)
    return d, 'both'


def barrage(p):
    set_ = ramp(p, 0.0, .40) * (1 - ramp(p, .82, 1.0))
    fire = ramp(p, .45, .58) * (1 - ramp(p, .75, 1.0))
    d = {
        'spine': [(X, 6 - 6 * set_ + 4 * fire)],
        'chest': [(X, 4 - 8 * set_ + 6 * fire)],
        'neck': [(X, -6 + 6 * set_)], 'head': [(X, -4 + 4 * set_)],
        'upperarm.R': [(X, -20 - 80 * set_ - 10 * fire), (Y, 10)], 'forearm.R': [(X, -30 + 20 * set_ - 16 * fire)],
        'upperarm.L': [(X, -20 - 50 * set_), (Y, -10)], 'forearm.L': [(X, -50 + 10 * set_)],
    }
    stance_legs(d, crouch=.35 * set_ + .2 * fire, wide=10)
    return d, 'both'


def shield(p):
    up = ramp(p, 0.0, .35)
    d = {
        'spine': [(X, 10 + 10 * up)], 'chest': [(X, 6 + 6 * up)],
        'neck': [(X, -8 - 8 * up)], 'head': [(X, -6 - 4 * up)],
        'upperarm.L': [(X, -20 - 50 * up), (Y, -10 + 30 * up)], 'forearm.L': [(X, -40 - 70 * up)],
        'upperarm.R': [(X, -20 - 50 * up), (Y, 10 - 30 * up)], 'forearm.R': [(X, -40 - 70 * up)],
    }
    stance_legs(d, crouch=.5 * up, wide=10)
    return d, 'both'


def brace(p):
    set_ = ramp(p, 0.0, .45)
    d = {
        'hips': [(X, 4 * set_)],
        'spine': [(X, 10 + 8 * set_)], 'chest': [(X, 6 + 4 * set_)],
        'neck': [(X, -8 - 6 * set_)], 'head': [(X, -6 - 4 * set_)],
        'upperarm.L': [(X, -30 - 10 * set_), (Y, -14)], 'forearm.L': [(X, -55)],
        'upperarm.R': [(X, -20), (Y, 14)], 'forearm.R': [(X, -40)],
    }
    stance_legs(d, crouch=.45 * set_, wide=8 + 8 * set_)
    return d, 'both'


CLIPS = {
    'Idle': (3.2, True, idle), 'Walk': (1.0, True, walk), 'Run': (.62, True, run), 'Attack': (.9, False, attack),
    'Death': (1.5, False, death), 'Cast': (.8, False, cast), 'Blink': (.36, False, blink),
    'Slam': (1.3, False, slam), 'Sweep': (1.2, False, sweep), 'Barrage': (1.0, False, barrage), 'Shield': (1.2, False, shield),
    'Brace': (.8, False, brace),
}


def _q(arm, bone, rots):
    q = Quaternion()
    for ax, deg in rots:
        q = Quaternion(Vector(ax), math.radians(deg)) @ q
    rr = arm.data.bones[bone].matrix_local.to_quaternion()
    return rr.inverted() @ q @ rr


def _toe_floor(arm, which):
    """the lowest point of the feet that bear the weight (world z): the toes' tips and the balls; 'all': of the whole
    body (a body lying down rests on whatever is lowest)"""
    mw = arm.matrix_world
    if which == 'all':
        return min(min((mw @ pb.head).z, (mw @ pb.tail).z) for pb in arm.pose.bones if pb.name != 'root') - .05
    zs = []
    for s in ('L', 'R'):
        if which in ('both', 'lowest') or (isinstance(which, list) and s in which):
            for b in (f'toes.{s}', f'foot.{s}'):
                pb = arm.pose.bones.get(b)
                if pb:
                    zs.append((mw @ pb.tail).z)
    return min(zs) if zs else 0.0


def bake(arm, names=None, log=print):
    """bakes the clips into actions named for the game (fake users kept), every bone keyed, the hips' height found so
    the weight-bearing foot stands on the ground at every frame"""
    arm.animation_data_create()
    hips = arm.pose.bones['hips']
    rr = arm.data.bones['hips'].matrix_local.to_quaternion()
    made = []
    for name, (dur, loop, f) in CLIPS.items():
        if names and name not in names:
            continue
        act = bpy.data.actions.new(name)
        act.use_fake_user = True
        arm.animation_data.action = act
        nfr = max(2, round(dur * FPS))
        for i in range(nfr + 1):
            p = i / nfr
            rots, feet = f(p % 1.0 if loop else p)
            for pb in arm.pose.bones:
                pb.rotation_mode = 'QUATERNION'
                pb.rotation_quaternion = _q(arm, pb.name, rots.get(pb.name, [])) if pb.name != 'root' else Quaternion()
                pb.location = (0, 0, 0)
            bpy.context.view_layer.update()
            # the hips lowered (or raised) so the foot that bears the weight is on the ground
            low = _toe_floor(arm, feet)
            hips.location = rr.inverted() @ Vector((0, 0, -low + .004))
            bpy.context.view_layer.update()
            fr = 1 + i
            for pb in arm.pose.bones:
                pb.keyframe_insert('rotation_quaternion', frame=fr)
            hips.keyframe_insert('location', frame=fr)
        made.append(f'{name} {dur:.2f}s')
    arm.animation_data.action = bpy.data.actions.get('Idle')
    log('motion: ' + ', '.join(made))
    return made
