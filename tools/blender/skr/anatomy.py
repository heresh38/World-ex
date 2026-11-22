"""The Sarketh's bodies (the owner's design sheet, art/reference/sarketh/sarketh_design_sheet.png, 2026-11-15):
2.0-2.3 m tall, 70-90 kg (very lean: long limbs, a narrow waist, sinew over bone), digitigrade legs (the heel high off
the ground, a long foot bone down to four clawed toes), four long clawed fingers and a thumb, a narrow wedge of a head
pointing forward and down under a crest of swept blades. Under the chitin: dark, scaled, segmented muscle.

Male and female are SEPARATE bodies (their own joints, their own sculpt); this module only holds the tools both use.
Units are metres; Blender's frame: Z up, -Y forward, the body's left is +X.

joints(sex) -> {bone: (head, tail)}; sculpt(sex) -> fleshkit.Sculpt of the under-body (material 'skin', bones per
primitive). The armour (chitin plates, claws, crest) is laid on it by chitin.py.
"""
import math
import os
import sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import sdf          # noqa: E402
import fleshkit as fk   # noqa: E402

# corner colours MULTIPLY the skin's own map (skr_skin holds the navy-violet): these are relative tones
SKIN = '#d6d2e0'
SINEW = '#bdb8cc'
DEEP = '#9a96ac'


def lerp(a, b, t):
    a = np.asarray(a, float); b = np.asarray(b, float)
    return a + (b - a) * t


def mx(p):
    return (-p[0], p[1], p[2])


# --------------------------------------------------------------------------------------------- the two skeletons
FINGERS = ('index', 'middle', 'ring', 'pinky')


def _hand(J, s, wrist, knuckle_c, along, spread, lengths, curl, thumb):
    """Four fingers from knuckles spread across the hand's width (index forward), three bones each, closing a little
    toward the palm (-X on the left hand); the thumb from the inner heel of the hand."""
    sg = 1 if s == 'L' else -1
    for i, f in enumerate(FINGERS):
        off = (i - 1.5) * spread
        k = np.asarray(knuckle_c, float) + np.array([0, off, .004 * abs(i - 1.5)])
        d = np.asarray(along, float) + np.array([0, off * 1.6, 0]); d /= np.linalg.norm(d)
        p = k
        for j, L in enumerate(lengths[i]):
            ang = curl * (j + 1) * .5
            dj = d * math.cos(ang) + np.array([-sg, 0, 0]) * math.sin(ang)
            q = p + dj * L
            J[f'{f}{j + 1}.{s}'] = (tuple(p), tuple(q))
            p = q
    p = np.asarray(thumb[0], float)
    for j, q in enumerate(thumb[1:]):
        q = np.asarray(q, float)
        J[f'thumb{j + 1}.{s}'] = (tuple(p), tuple(q))
        p = q


def joints(sex):
    m = sex == 'male'
    J = {}
    if m:
        hip, sp, ch, nk, hd, top = (0, .010, 1.160), (0, .015, 1.290), (0, .020, 1.460), (0, .030, 1.722), (0, -.075, 1.890), (0, -.150, 2.005)
        J['hips'] = (hip, sp); J['spine'] = (sp, ch); J['chest'] = (ch, (0, .025, 1.720)); J['neck'] = (nk, hd); J['head'] = (hd, top)
        side = dict(sh=(.225, .028, 1.690), el=(.312, .048, 1.385), wr=(.382, .004, 1.085), hand=(.400, -.010, .995),
                    hipj=(.105, .010, 1.140), kn=(.120, -.078, .712), hock=(.115, .086, .272), ball=(.115, -.028, .046),
                    toe=(.115, -.165, .012))
    else:
        hip, sp, ch, nk, hd, top = (0, .012, 1.090), (0, .016, 1.210), (0, .020, 1.370), (0, .028, 1.615), (0, -.068, 1.774), (0, -.136, 1.880)
        J['hips'] = (hip, sp); J['spine'] = (sp, ch); J['chest'] = (ch, (0, .024, 1.612)); J['neck'] = (nk, hd); J['head'] = (hd, top)
        side = dict(sh=(.192, .026, 1.585), el=(.270, .046, 1.300), wr=(.336, .006, 1.020), hand=(.352, -.006, .938),
                    hipj=(.112, .012, 1.068), kn=(.118, -.072, .665), hock=(.110, .080, .252), ball=(.110, -.026, .043),
                    toe=(.110, -.152, .011))
    for s in 'LR':
        f = (lambda p: p) if s == 'L' else mx
        g = {k: f(v) for k, v in side.items()}
        J[f'upperarm.{s}'] = (g['sh'], g['el'])
        J[f'forearm.{s}'] = (g['el'], g['wr'])
        J[f'hand.{s}'] = (g['wr'], g['hand'])
        J[f'thigh.{s}'] = (g['hipj'], g['kn'])
        J[f'shin.{s}'] = (g['kn'], g['hock'])
        J[f'foot.{s}'] = (g['hock'], g['ball'])
        J[f'toes.{s}'] = (g['ball'], g['toe'])
        sg = 1 if s == 'L' else -1
        hx, hy, hz = g['hand']
        sc = 1.0 if m else .9
        lengths = [[.062 * sc, .048 * sc, .040 * sc], [.068 * sc, .052 * sc, .042 * sc], [.064 * sc, .049 * sc, .040 * sc], [.054 * sc, .042 * sc, .035 * sc]]
        _hand(J, s, g['wr'], (hx + .004 * sg, hy, hz - .012), (0.05 * sg, -.10, -1), .0155 * sc, lengths, .32,
              [(hx - .010 * sg, hy - .028, hz + .052), (hx - .006 * sg, hy - .052, hz + .018), (hx - .010 * sg, hy - .066, hz - .016), (hx - .016 * sg, hy - .074, hz - .044)])
    return J


PARENT = {'hips': 'root', 'spine': 'hips', 'chest': 'spine', 'neck': 'chest', 'head': 'neck'}
for _s in 'LR':
    PARENT.update({f'upperarm.{_s}': 'chest', f'forearm.{_s}': f'upperarm.{_s}', f'hand.{_s}': f'forearm.{_s}',
                   f'thigh.{_s}': 'hips', f'shin.{_s}': f'thigh.{_s}', f'foot.{_s}': f'shin.{_s}', f'toes.{_s}': f'foot.{_s}'})
    for _f in FINGERS + ('thumb',):
        PARENT[f'{_f}1.{_s}'] = f'hand.{_s}'
        PARENT[f'{_f}2.{_s}'] = f'{_f}1.{_s}'
        PARENT[f'{_f}3.{_s}'] = f'{_f}2.{_s}'
ORDER = ['hips', 'spine', 'chest', 'neck', 'head'] + [f'{n}.{s}' for s in 'LR' for n in
                                                     ('upperarm', 'forearm', 'hand', 'thigh', 'shin', 'foot', 'toes')] + \
        [f'{f}{j}.{s}' for s in 'LR' for f in FINGERS + ('thumb',) for j in (1, 2, 3)]


# --------------------------------------------------------------------------------------------- the under-body
class Body:
    """The sculpt with side-aware helpers: every limb primitive is made for both sides at once."""

    def __init__(self, sex, J):
        self.sex, self.J = sex, J
        self.S = fk.Sculpt(seed=3 if sex == 'male' else 5)

    def j(self, b, end=0):
        return np.asarray(self.J[b][end], float)

    def pt(self, b, t, off=(0, 0, 0), s='L'):
        p = lerp(self.J[f'{b}.{s}'][0], self.J[f'{b}.{s}'][1], t) if '.' not in b else lerp(self.J[b][0], self.J[b][1], t)
        o = np.asarray(off, float)
        if s == 'R':
            o = o * np.array([-1, 1, 1])
        return p + o

    def both(self, fn):
        for s in 'LR':
            fn(s, 1 if s == 'L' else -1)

    def cone(self, a, b, r1, r2, bone, col=SKIN, k=.02, mat='skin', **kw):
        return self.S.cone(a, b, r1, r2, bone, mat, col, k, **kw)

    def ell(self, c, r, bone, col=SKIN, k=.02, R=None, mat='skin', **kw):
        return self.S.ell(c, r, bone, mat, col, k, R=R, **kw)


HEAD = 1.12            # the male's head (helmet and all) to the build he had (the sheet's helmet is big beside the shoulders)


def head_field(hd, s=1.0):
    """The head (the owner's sheet, "head detail"): a cranium behind and above, and a long face running forward and down
    from the brow to a pointed chin, keeled down its front, the jaw under it running back to the throat. ONE shape, used
    by the sculpt (the head under the helmet) and by the helmet (a shell laid over it). s: the head's scale.
    Returns (field, lo, hi)."""
    hd = np.asarray(hd, float)

    def p(x, y, z):
        return hd + np.array([x, y, z], float) * s
    face = sdf.Loft(p(0, -.034, .142), p(0, -.120, -.046), {
        't': [0, .16, .36, .56, .76, .90, 1.0],
        'rv_pos': list(np.array([.044, .049, .047, .040, .029, .017, .005]) * s),      # half its width
        'rw_pos': list(np.array([.015, .019, .021, .020, .016, .010, .004]) * s),      # in front of its line: the keel
        'rw_neg': list(np.array([.058, .064, .061, .052, .037, .021, .006]) * s),      # behind it
        'n': [1.75, 1.55, 1.45, 1.45, 1.5, 1.7, 2.0],
        'nb': [2.2, 2.2, 2.2, 2.1, 2.0, 2.0, 2.0]}, v_axis=(1, 0, 0), cap=.6)
    a = math.radians(16)                                     # the cranium tilted, its back end up
    Rc = np.array([[1, 0, 0], [0, math.cos(a), math.sin(a)], [0, -math.sin(a), math.cos(a)]])
    cc, cr = p(0, .022, .090), np.array([.054, .066, .060]) * s
    ja, jb = p(0, -.104, -.040), p(0, -.004, .004)

    def f(P):
        P = np.asarray(P, np.float32)
        d = face(P)
        d = sdf.smin(d, sdf.ellipsoid(P, cc, cr, Rc), .028 * s)
        d = sdf.smin(d, sdf.round_cone(P, ja, jb, .010 * s, .028 * s), .022 * s)
        return d
    return f, hd + np.array([-.075, -.150, -.070]) * s, hd + np.array([.075, .115, .175]) * s


def _R(yaw=0.0, pitch=0.0, roll=0.0):
    """rows = local axes; rotations in degrees about Z, X, Y"""
    R = sdf.rot((0, 0, 1), math.radians(yaw)) @ sdf.rot((1, 0, 0), math.radians(pitch)) @ sdf.rot((0, 1, 0), math.radians(roll))
    return R.T


def sculpt(sex):
    J = joints(sex)
    B = Body(sex, J)
    m = sex == 'male'
    w = 1.10 if m else .90         # breadth of the frame (his: the sheet's broad, muscled chest)
    lim = 1.30 if m else .86       # limb thickness (the sheet: his heavy, muscled arms and thighs; hers slender)

    # ---- trunk
    ch = B.j('chest')
    B.ell(ch + (0, .005, .118), (.150 * w, .112, .150), 'chest', k=.05)                               # ribcage (high: the trunk a V)
    if m:
        for s, sg in (('L', 1), ('R', -1)):
            B.ell(ch + (.072 * sg, -.068, .150), (.082, .046, .066), 'chest', k=.035, R=_R(yaw=-12 * sg))  # pectorals
    else:
        for s, sg in (('L', 1), ('R', -1)):
            B.ell(ch + (.070 * sg, -.070, .110), (.060, .058, .062), 'chest', k=.03)                      # breasts
            B.ell(ch + (.060 * sg, -.050, .150), (.066, .036, .050), 'chest', k=.035)
    for s, sg in (('L', 1), ('R', -1)):
        if m:
            B.cone(ch + (.112 * sg * w, .056, .190), B.j('spine') + (.062 * sg, .046, .050), .062 * w, .026, 'chest', k=.045)   # lats: broad under the arm, to the waist
        else:
            B.cone(ch + (.088 * sg, .048, .170), B.j('spine') + (.046 * sg, .040, .070), .040, .018, 'chest', k=.04)         # hers: slight (the sheet's narrow waist)
        B.ell(ch + (.060 * sg, .088, .190), (.070 * w, .040, .060), 'chest', k=.04)                      # shoulder blades
        tr = 1.0 if m else .78
        B.cone(ch + (.024 * sg, .046, .310 * tr + .02 * (1 - tr)), B.pt('upperarm', 0, (-.03, .01, .024), s), .056 * lim * tr, .040 * lim * tr, 'chest',
               k=.045)                                                                                    # trapezius, up the neck (hers low and slight)
        B.cone(ch + (.020 * sg, -.050, .262), B.pt('upperarm', 0, (-.025, -.04, .005), s), .020, .024, 'chest', k=.02)           # collarbone
    sp = B.j('spine')
    waist = .080 * w if m else .064
    B.S.chain([ch + (0, -.005, .02), sp + (0, -.004, .06), sp + (0, .000, -.04)], [.110 * w, waist, .098 * (1.0 if m else 1.12)], 'spine', 'skin', SKIN, k=.04)
    for row in range(3):                                                                                      # the segmented belly
        for sg in (1, -1):
            B.ell(sp + (.032 * sg, -.072 + row * .003, .085 - row * .058), (.034, .020, .026), 'spine', col=SINEW, k=.018)
    for sg in (1, -1):
        if m:
            B.ell(sp + (.060 * sg * w, -.010, .010), (.032, .052, .085), 'spine', k=.035)               # obliques
        else:
            B.ell(sp + (.040 * sg, -.008, .014), (.024, .044, .075), 'spine', k=.03)                     # hers: the waist pinched
        B.ell(sp + (.032 * sg, .080, .060), (.030, .024, .120), 'spine', col=SINEW, k=.03)              # the spine's ropes
    hp = B.j('hips')
    pel = (.108, .080, .078) if m else (.150, .096, .090)
    B.ell(hp + (0, .012, -.008), pel, 'hips', k=.05)
    for sg in (1, -1):
        B.ell(hp + (.064 * sg * (1 if m else 1.08), .068, -.040), (.040, .032, .050) if m else (.050, .042, .060), 'hips', k=.04)  # glutes
    B.ell(hp + (0, -.058, -.080), (.042, .030, .055), 'hips', col=DEEP, k=.03)

    # ---- neck and head
    hd = B.j('head')
    nk = B.j('neck')
    hs = HEAD * (1.0 if m else .92)
    # the neck: long and slim, carried forward, into the back of the head from below
    B.S.chain([nk + (0, .012, -.012), lerp(nk, hd, .45) + (0, .010, 0), hd + (0, .032 * hs, .026 * hs)],
              [.064 * w, .044 * hs, .038 * hs] if m else [.060 * w, .034 * hs, .030 * hs], 'neck', 'skin', SKIN, k=.03)
    for sg in (1, -1):
        B.cone(hd + (.030 * sg * hs, -.020 * hs, .002), nk + (.050 * sg, -.046, .000), .012, .018, 'neck', col=SINEW, k=.018)   # the neck's cords
        B.cone(hd + (.024 * sg * hs, .040 * hs, .036 * hs), nk + (.060 * sg, .050, -.010), .013, .022, 'neck', col=SINEW, k=.02)
    hf, hlo, hhi = head_field(hd, hs)
    B.S.add(hf, hlo, hhi, 'head', 'skin', SKIN, k=.03)                                      # the head (head_field)

    # ---- arms
    def arm(s, sg):
        sh, el, wr = B.j(f'upperarm.{s}'), B.j(f'forearm.{s}'), B.j(f'hand.{s}')
        dl = 1.0 if m else .86
        B.ell(sh + (.012 * sg, -.004, -.018), (.064 * lim * dl, .068 * lim * dl, .080 * lim * dl), f'upperarm.{s}', k=.04)   # deltoid
        B.cone(sh, el, .052 * lim, .038 * lim, f'upperarm.{s}', k=.03)
        B.ell(lerp(sh, el, .48) + (-.004 * sg, -.030, 0), (.036 * lim, .036 * lim, .090), f'upperarm.{s}', k=.03)    # biceps
        B.ell(lerp(sh, el, .42) + (.006 * sg, .036, 0), (.040 * lim, .040 * lim, .100), f'upperarm.{s}', col=SINEW, k=.03)   # triceps
        B.S.sph(el + (0, .010, 0), .036 * lim, f'forearm.{s}', 'skin', SKIN, .02)
        B.cone(el, wr, .042 * lim, .024 * lim, f'forearm.{s}', k=.03)
        B.ell(lerp(el, wr, .28) + (.010 * sg, -.006, 0), (.040 * lim, .038 * lim, .085), f'forearm.{s}', k=.03)   # forearm muscle
        B.ell(lerp(el, wr, .55) + (-.006 * sg, .010, 0), (.026 * lim, .030 * lim, .090), f'forearm.{s}', col=SINEW, k=.025)
        # the hand: a long narrow palm (thin across X), knuckles, four fingers and a thumb; the claws are chitin.py's
        hb = B.j(f'hand.{s}', 0); he = B.j(f'hand.{s}', 1)
        B.ell(lerp(hb, he, .55) + (.002 * sg, -.004, -.006), (.024 * lim, .044 * lim, .058), f'hand.{s}', k=.02)
        for f in FINGERS:
            r0 = .0128 * lim if f != 'pinky' else .0110 * lim
            for jn in (1, 2, 3):
                a_, b_ = B.j(f'{f}{jn}.{s}'), B.j(f'{f}{jn}.{s}', 1)
                B.cone(a_, b_, r0 * (1 - .14 * (jn - 1)), r0 * (1 - .14 * jn), f'{f}{jn}.{s}', k=.006)
            B.S.sph(B.j(f'{f}1.{s}'), r0 * 1.15, f'{f}1.{s}', 'skin', SKIN, .008)
        for jn in (1, 2, 3):
            a_, b_ = B.j(f'thumb{jn}.{s}'), B.j(f'thumb{jn}.{s}', 1)
            B.cone(a_, b_, .0135 * lim * (1 - .12 * (jn - 1)), .0135 * lim * (1 - .12 * jn), f'thumb{jn}.{s}', k=.008)
    B.both(arm)

    # ---- digitigrade legs
    def leg(s, sg):
        hj, kn, hk, bl_, toe = B.j(f'thigh.{s}'), B.j(f'shin.{s}'), B.j(f'foot.{s}'), B.j(f'toes.{s}'), B.j(f'toes.{s}', 1)
        B.cone(hj + (0, .004, .02), kn, .076 * lim, .050 * lim, f'thigh.{s}', k=.04)
        if not m:
            B.ell(lerp(hj, kn, .22) + (.026 * sg, .004, 0), (.056, .060, .120), f'thigh.{s}', k=.05)   # her hip's curve into the thigh
        B.ell(lerp(hj, kn, .42) + (.006 * sg, -.032, 0), (.058 * lim, .052 * lim, .150), f'thigh.{s}', k=.04, R=_R(pitch=-8))   # quadriceps
        B.ell(lerp(hj, kn, .40) + (.004 * sg, .040, 0), (.050 * lim, .048 * lim, .140), f'thigh.{s}', col=SINEW, k=.04)       # hamstrings
        B.ell(lerp(hj, kn, .30) + (-.040 * sg, -.004, 0), (.038 * lim, .048 * lim, .120), f'thigh.{s}', k=.04)               # adductors
        B.S.sph(kn, .044 * lim, f'shin.{s}', 'skin', SKIN, .02)
        B.cone(kn, hk, .046 * lim, .030 * lim, f'shin.{s}', k=.025)
        B.ell(lerp(kn, hk, .30) + (0, .036, .004), (.040 * lim, .046 * lim, .110), f'shin.{s}', col=SINEW, k=.03, R=_R(pitch=20))   # calf
        B.S.sph(hk, .032 * lim, f'foot.{s}', 'skin', SKIN, .015)
        B.cone(hk, bl_, .031 * lim, .028 * lim, f'foot.{s}', k=.018)
        B.cone(hk + (0, .016, .01), lerp(hk, bl_, .6) + (0, .012, 0), .012, .010, f'foot.{s}', col=SINEW, k=.012)   # the long tendon
        # four toes: three forward and spread, one inside pointing back (the claws are chitin.py's)
        B.ell(bl_ + (0, -.020, -.006), (.040 * lim, .040 * lim, .026), f'toes.{s}', k=.02)
        for dx, ln in ((-.026, .088), (0.0, .102), (.026, .086)):
            a_ = bl_ + (dx * sg, -.030, -.010)
            b_ = bl_ + (dx * 1.6 * sg, -.030 - ln, -.034)
            B.cone(a_, lerp(a_, b_, .55) + (0, 0, .010), .016 * lim, .013 * lim, f'toes.{s}', k=.012)
            B.cone(lerp(a_, b_, .55) + (0, 0, .010), b_, .013 * lim, .010 * lim, f'toes.{s}', k=.008)
        B.cone(bl_ + (-.022 * sg, .006, -.004), bl_ + (-.040 * sg, .040, -.030), .013 * lim, .010 * lim, f'toes.{s}', k=.01)
    B.both(leg)

    # the surface: muscle striation and fine knots (the scales are in the skin's map, not the mesh)
    def disp(P):
        return (fk.fbm(P, 38, 2, 7) - .5) * .0016 + fk.ridge(P, 22, 9, 8) * .0010
    B.S.disp = disp
    return J, B.S
