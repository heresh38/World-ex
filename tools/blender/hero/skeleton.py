"""Joint positions shared by the cage (cage.py) and the anatomical target (shape.py), so the fingers, toes and limbs of
the topology and of the shape sit exactly on one another. Left side only (+X); the right is its mirror.
"""
import math
from mathutils import Vector


def unit(v):
    v = Vector(v)
    return v.normalized() if v.length > 1e-9 else v


def arm(T):
    """shoulder, elbow, wrist, the arm axis a, the back of the hand (dorsal), the thumb side (forward, -Y-ish)"""
    drop, fwd = math.radians(T["arm_drop"]), math.radians(T["arm_fwd"])
    a = Vector((math.cos(drop) * math.cos(fwd), -math.sin(fwd) * math.cos(drop), -math.sin(drop))).normalized()
    dorsal = unit(Vector((0, 0, 1)) - a * a.z)
    thumb = unit(dorsal.cross(a) * -1.0)                 # forward for the left arm
    if thumb.y > 0:
        thumb = -thumb
    S = Vector(T["shoulder_joint"])
    E = S + a * T["upper_arm"]
    W = E + a * T["forearm"]
    return dict(S=S, E=E, W=W, a=a, dorsal=dorsal, thumb=thumb)


FINGERS = ("index", "middle", "ring", "little")
F_LEN = dict(index=.077, middle=.085, ring=.080, little=.063)      # knuckle to tip, for a 19.5 cm hand
F_WID = dict(index=.0185, middle=.0190, ring=.0178, little=.0158)
F_SPREAD = dict(index=-.10, middle=0.0, ring=.07, little=.14)       # toward the little finger (+) / thumb (-)
F_OFFSET = dict(index=.75, middle=.25, ring=-.25, little=-.75)     # across the knuckles, toward the thumb (+)


def hand(T):
    A = arm(T)
    a, d, th = A["a"], A["dorsal"], A["thumb"]
    P = T["palm"]
    sc = T["hand"] / .195
    knuckle = A["W"] + a * (P["l"] * .96)
    fingers = {}
    for f in FINGERS:
        base = knuckle + th * (F_OFFSET[f] * P["w"] / 2 * .95)
        dirn = unit(a - th * F_SPREAD[f] - d * .12)
        L = F_LEN[f] * sc
        # three phalanges (proximal .45, middle .30, distal .25 of the length), a gentle relaxed curl
        joints = [base]
        segs = (.45, .30, .25)
        p = base
        k = dirn
        for i, s in enumerate(segs):
            k = unit(k - d * (.10 + .06 * i))
            p = p + k * (L * s)
            joints.append(p)
        fingers[f] = dict(base=base, dir=dirn, len=L, width=F_WID[f] * sc, joints=joints)
    # thumb: from the radial side of the palm near the wrist
    tb = A["W"] + a * (P["l"] * .30) + th * (P["w"] / 2 * .95) - d * (P["t"] * .15)
    tdir = unit(a * .55 + th * .55 - d * .35)
    L = .068 * sc
    joints = [tb]
    p, k = tb, tdir
    for i, s in enumerate((.42, .32, .26)):
        k = unit(k - d * (.08 + .05 * i) + a * .05)
        p = p + k * (L * s)
        joints.append(p)
    thumb = dict(base=tb, dir=tdir, len=L, width=.0215 * sc, joints=joints)
    return dict(arm=A, knuckle=knuckle, fingers=fingers, thumb=thumb, scale=sc)


def leg(T):
    return dict(H=Vector(T["hip_joint"]), K=Vector(T["knee"]), A=Vector(T["ankle"]))


TOES = ("big", "second", "third", "fourth", "little")
T_LEN = (.042, .033, .029, .025, .020)
T_WID = (.029, .018, .017, .0155, .0145)
T_OFFSET = (.82, .38, .00, -.36, -.70)        # across the ball of the foot, from medial (+) to lateral (-)


def foot(T):
    L = leg(T)
    ank = L["A"]
    fl, fw = T["foot"]["l"], T["foot"]["w"]
    heel = Vector((ank.x, ank.y + T["heel_back"], .032))
    toe_y = ank.y - (fl - T["heel_back"])
    ball = Vector((ank.x + .008, toe_y + .065, .026))
    medial = Vector((-1, 0, 0))                     # toward x = 0 for the left foot
    s = fl / .27
    toes = []
    for i, n in enumerate(TOES):
        base = ball + medial * (T_OFFSET[i] * fw / 2 * .92) + Vector((0, -.006 - .004 * (2 - abs(i - 1.5)), 0))
        dirn = unit(Vector((-.06 * (i - 1.5) * .15, -1, 0)))
        toes.append(dict(name=n, base=base, dir=dirn, len=T_LEN[i] * s, width=T_WID[i] * fw / .102))
    return dict(ankle=ank, heel=heel, ball=ball, toe_y=toe_y, toes=toes, width=fw, length=fl)
