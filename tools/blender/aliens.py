"""VANTHOS alien species on the shared 20-bone rig: stalker, hulk, mutant, swimmer, elite.

Sculpted as signed-distance fields with fleshkit (wet glistening flesh between chitin plates, exposed ribs and sinew,
pustules, tendrils, deliberate asymmetry), soft-skinned to the rig, vertex-coloured over the shared hx_* texture sets.
  stalker  lean eyeless predator: split mandible jaw, exposed flank ribs, spine quills, long hooked claws
  hulk     armoured brute: a cracked carapace hump with glowing vents, one oversized plated forearm, a sunken head
  mutant   the lab's failed subject: tumour mass swallowing one side, exposed glowing brain, acid veins, stitched tubes
  swimmer  drowned hunter: slick finned body, gill slits, a wide needle-toothed jaw, webbed claws, a dorsal sail
  elite    tall and regal: a crown of bone, a cluster of eyes, an open ribcage around a glowing heart, a bone blade arm
Materials (names are an API): alien_skin (wet flesh), alien_hide, alien_plate, alien_bone, alien_sac, alien_glow (pulses
in the game), alien_acid. Clips: Idle, Walk, Run, Attack, Death.

Run: blender --background --python tools/blender/aliens.py [-- stalker hulk ...]
"""
import math, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import bl, sdf
import fleshkit as fk
from fleshkit import fbm, ridge
from writhe import human_joints, humanoid_clips, spikes, rand_dirs, teeth_ring

KINDS = {
    #          scale  hide       flesh      plate      glow       acid
    'stalker': (1.05, '#5a4a66', '#8a3a5a', '#3a3046', '#b46cff', '#7dffb0'),
    'hulk': (1.5, '#6a5a50', '#9a4a30', '#4a3c34', '#ff7a2a', '#ffd27a'),
    'mutant': (1.0, '#9aa08a', '#a05040', '#4e5444', '#7dffb0', '#b6ff4a'),
    'swimmer': (.98, '#3a6a72', '#7a3a4a', '#1e3e44', '#3ae6ff', '#7dffb0'),
    'elite': (1.32, '#4a3a56', '#8a2a4a', '#2a2032', '#ff3fb4', '#b46cff'),
}
BONE = '#e0d2b4'


def mats(kind):
    _, hide, flesh, plate, glow, acid = KINDS[kind]
    return dict(skin=fk.tmat('alien_skin', 'hx_flesh', nstr=1.3), hide=fk.tmat('alien_hide', 'hx_skin', nstr=1.2),
                plate=fk.tmat('alien_plate', 'hx_chitin', nstr=1.3), bone=fk.tmat('alien_bone', 'hx_bone'),
                sac=fk.tmat('alien_sac', 'hx_sac'), glow=fk.glow_mat('alien_glow', glow, 3), acid=fk.glow_mat('alien_acid', acid, 2.5))


def blobs(sc, rnd, centre, dirs, rr, bone, mat, col, k=.5, out=.25):
    for d in dirs:
        p = sc.surface_point(centre, d, 1.2)
        r = rr[0] + (rr[1] - rr[0]) * rnd.random()
        sc.sph(p + np.asarray(d) * r * out, r, bone, mat, col, k=r * k, amp=.3)


def build_kind(kind):
    s, HIDE, FLESH, PLATE, GLOW, ACID = KINDS[kind]
    J = human_joints(s)
    sc = fk.Sculpt(sum(map(ord, kind))); rnd = sc.rnd

    def disp(P):
        return (fbm(P, 16 / s, 3, 1) - .5) * .009 * s + ridge(P, 5 / s, 2, 8) * .006 * s
    sc.disp = disp
    hz = J['hips'][0][2]; sz = J['spine'][0][2]; cz = J['chest'][0][2]; nz = J['neck'][0][2]; h2 = J['head'][0][2]
    wide = {'hulk': 1.55, 'elite': 1.15}.get(kind, 1.0)
    V = lambda *a: np.array(a, float)
    # ---------------- torso: pelvis, a pinched waist of sinew, ribcage, shoulder mass
    sc.ell(V(0, .01, hz), V(.13, .09, .1) * s * wide, 'hips', 'hide', HIDE, k=.03 * s)
    sc.ell(V(0, .02, sz + .1 * s), V(.085, .065, .12) * s * wide, 'spine', 'skin', FLESH, k=.04 * s, amp=1.6)
    for sx in (1, -1):                                                           # obliques: sinew cords over the waist
        sc.cone(V(sx * .07, -.03, hz + .06 * s) * [1, 1, 1], V(sx * .1 * wide, -.06, cz + .05 * s), .022 * s, .018 * s, 'spine', 'skin', FLESH, k=.02 * s, amp=1.5)
    sc.ell(V(0, .01, cz + .1 * s), V(.15, .11, .14) * s * np.array([wide, min(wide, 1.25), 1]), 'chest', 'hide', HIDE, k=.05 * s)
    for sx in (1, -1):
        sh = J['upperarm.' + ('L' if sx > 0 else 'R')][0]
        sc.cone(V(sx * .05, .01, cz + .17 * s), sh, .055 * s * wide, .06 * s * wide, 'chest', 'hide', HIDE, k=.04 * s)
    # exposed ribs over the flanks (skin peeled back), cut cavity behind them
    if kind in ('stalker', 'elite', 'mutant', 'swimmer'):
        side = (1, -1) if kind in ('stalker', 'elite') else (-1,)
        for sx in side:
            c = V(sx * .11 * wide, -.04, cz + .06 * s)
            sc.cut_ell(c, V(.06, .08, .1) * s, 'chest', 'skin', '#3a0c14', k=.015 * s)
            for i in range(4):
                z = cz + (-.02 + i * .04) * s
                sc.chain([V(sx * .05, -.1 * s, z), V(sx * .13 * wide, -.07 * s, z - .01 * s), V(sx * .15 * wide, .02 * s, z - .02 * s), V(sx * .1, .09 * s, z)],
                         [.009 * s, .009 * s, .008 * s, .006 * s], 'chest', 'bone', BONE, k=.006 * s, amp=.2)
    if kind == 'elite':
        # an open sternum around a glowing heart
        sc.cut_ell(V(0, -.11 * s, cz + .1 * s), V(.07, .06, .1) * s, 'chest', 'skin', '#3a0c14', k=.012 * s)
        sc.sph(V(0, -.08 * s, cz + .1 * s), .045 * s, 'chest', 'glow', GLOW, k=.01 * s, amp=0)
        for sx in (1, -1):
            for i in range(3):
                z = cz + (.03 + i * .045) * s
                sc.chain([V(sx * .02, -.13 * s, z), V(sx * .06 * s, -.16 * s, z + .01 * s), V(sx * .1 * s, -.14 * s, z)], [.009 * s, .007 * s, .004 * s],
                         'chest', 'bone', BONE, k=.005 * s, amp=.1)
    # carapace / dorsal plates
    if kind == 'hulk':
        hump = lambda P: sdf.ellipsoid(P, V(0, .1 * s, cz + .12 * s), V(.27, .2, .22) * s)
        sc.ell(V(0, .08 * s, cz + .12 * s), V(.24, .17, .2) * s, 'chest', 'skin', FLESH, k=.05 * s, amp=1.5)
        sc.shell(hump, V(-.4, -.2, cz - .2) * [s, s, 1], V(.4, .45, cz + .5), .028 * s, 'chest', 'plate', PLATE,
                 keep=lambda P: -(P[:, 1] - .02 * s), holes=(4 / s, .72, 3), k=.015 * s, amp=.3)
        for c in rand_dirs(rnd, 8, (0, 1, .4), .7):                       # glowing vents through the cracks
            p = sc.surface_point(V(0, .08 * s, cz + .12 * s), c, 1.0)
            sc.sph(p, .03 * s, 'chest', 'glow', GLOW, k=.01 * s, amp=0)
        spikes(sc, rnd, V(0, .1 * s, cz + .14 * s), [(0, .6, 1), (.4, .7, .7), (-.4, .7, .7), (.2, 1, .2), (-.2, 1, .2)], .2 * s, .035 * s, 'chest',
               mat='plate', col=PLATE, k=.015 * s)
    else:
        back = lambda P: sdf.ellipsoid(P, V(0, .02 * s, cz + .1 * s), V(.165 * wide, .125, .15) * s)
        sc.shell(back, V(-.3, -.2, cz - .1) * [s, s, 1], V(.3, .3, cz + .4), .012 * s, 'chest', 'plate', PLATE,
                 keep=lambda P: np.maximum(.03 * s - P[:, 1], np.abs(P[:, 0]) - .12 * s * wide), holes=(7 / s, .7, 4), k=.008 * s, amp=.3)
        if kind in ('stalker', 'elite'):
            for i in range(6):                                                 # spine quills
                z = cz + (.22 - i * .075) * s
                sc.chain([V(0, .1 * s, z), V(0, .2 * s, z + .04 * s), V(0, .3 * s, z + .1 * s)], [.016 * s, .01 * s, .002 * s],
                         'chest' if z > cz else 'spine', 'bone', BONE, k=.008 * s, amp=.1)
    if kind == 'swimmer':
        sail = lambda P: np.maximum(np.abs(P[:, 0]) - .006 * s, sdf.ellipsoid(P, V(0, .14 * s, cz + .02 * s), V(.04, .14, .3) * s))
        sc.add(sail, V(-.05, -.05, cz - .35), V(.05, .35, cz + .35), 'chest', 'sac', '#7ab8b8', k=.02 * s, amp=.2)
        for i in range(5):
            z = cz + (-.22 + i * .1) * s
            sc.chain([V(0, .08 * s, z), V(0, .26 * s, z + .05 * s)], [.006 * s, .003 * s], 'chest', 'bone', BONE, k=.004 * s, amp=0)
    if kind == 'mutant':
        # a tumour mass swallowing the left side, acid veins, surgical tubing
        for c, r in [((.12, -.02, cz + .02), .12), ((.16, .04, cz - .1), .1), ((.09, -.08, sz + .08), .08), ((.2, -.02, cz + .14), .07)]:
            sc.sph(V(*c) * [s, s, 1], r * s, 'chest' if c[2] > cz - .05 else 'spine', 'sac', '#c8b888', k=.04 * s, amp=2.5)
        for c in rand_dirs(rnd, 10, (1, -.4, 0), .8):
            p = sc.surface_point(V(.13, -.02, cz), c, 1.0)
            sc.sph(p, (.015 + .015 * rnd.random()) * s, 'chest', 'acid', ACID, k=.01 * s, amp=0)
        for sx, z0 in ((-1, cz + .05), (-1, sz)):
            sc.chain([V(sx * .1, .12, z0), V(sx * .16, .16, z0 - .15), V(sx * .12, .12, z0 - .35), V(sx * .06, .1, hz)],
                     [.011 * s] * 4, 'spine', 'plate', '#3a3e44', k=.004 * s, amp=0)
    # ---------------- neck + head
    sc.cone(V(0, .02, nz - .02), V(0, -.01 * s, nz + .12 * s), .05 * s * min(wide, 1.3), .045 * s, 'neck', 'skin', FLESH, k=.03 * s, amp=1.5)
    if kind == 'hulk':
        sc.ell(V(0, -.06 * s, h2 + .04 * s), V(.1, .11, .09) * s, 'head', 'plate', PLATE, k=.03 * s, amp=.4)
        sc.cut_ell(V(0, -.17 * s, h2 + .0), V(.06, .04, .035) * s, 'head', 'skin', '#3a0c14', k=.01 * s)
        teeth_ring(sc, V(0, -.165 * s, h2), .055 * s, .03 * s, 10, 'head', (0, 1, 0), .025 * s, .007 * s)
        for sx in (1, -1):
            sc.sph(V(sx * .045, -.15, h2 + .06) * [s, s, 1], .014 * s, 'head', 'glow', GLOW, k=.003, amp=0)
    elif kind == 'swimmer':
        sc.ell(V(0, -.04 * s, h2 + .08 * s), V(.09, .13, .075) * s, 'head', 'hide', HIDE, k=.03 * s)
        sc.cut_ell(V(0, -.13 * s, h2 + .04 * s), V(.075, .07, .028) * s, 'head', 'skin', '#3a0c14', k=.008 * s)
        teeth_ring(sc, V(0, -.13 * s, h2 + .04 * s), .07 * s, .022 * s, 16, 'head', (0, 1, 0), .03 * s, .005 * s)
        for sx in (1, -1):
            sc.sph(V(sx * .07, -.09, h2 + .1) * [s, s, 1], .018 * s, 'head', 'glow', GLOW, k=.004 * s, amp=0)
            for i in range(3):                                                 # gill slits
                sc.cut_ell(V(sx * .045 * s, -.0, nz + (.02 + i * .03) * s), V(.012, .03, .005) * s, 'neck', 'glow', GLOW, k=.003 * s)
            sc.chain([V(sx * .06, .02, h2 + .1) * [s, s, 1], V(sx * .12, .12, h2 + .12) * [s, s, 1], V(sx * .14, .2, h2 + .05) * [s, s, 1]],
                     [.008 * s, .005 * s, .001], 'head', 'sac', '#7ab8b8', k=.006 * s, writhe=(.2, 1))
    else:
        # elongated eyeless skull sweeping back, a split mandible jaw, teeth
        L = {'elite': 1.15}.get(kind, 1.0)
        sc.ell(V(0, -.01 * s, h2 + .1 * s), V(.075, .1, .085) * s, 'head', 'hide', HIDE, k=.03 * s)
        sc.cone(V(0, .03 * s, h2 + .12 * s), V(0, .26 * s * L, h2 + .2 * s * L), .07 * s, .02 * s, 'head', 'plate', PLATE, k=.03 * s, amp=.4)
        sc.cut_ell(V(0, -.1 * s, h2 + .04 * s), V(.04, .05, .035) * s, 'head', 'skin', '#3a0c14', k=.008 * s)
        teeth_ring(sc, V(0, -.1 * s, h2 + .045 * s), .036 * s, .03 * s, 12, 'head', (0, 1, 0), .025 * s, .005 * s)
        for sx in (1, -1):
            sc.chain([V(sx * .045, -.06, h2 + .05) * [s, s, 1], V(sx * .07, -.13, h2 + .0) * [s, s, 1], V(sx * .04, -.18, h2 - .06) * [s, s, 1]],
                     [.016 * s, .011 * s, .003 * s], 'head', 'bone', BONE, k=.008 * s, amp=.1)
        if kind == 'elite':
            for i, (ex, ez) in enumerate(((.03, .14), (-.03, .14), (.055, .11), (-.055, .11), (0, .17))):
                sc.sph(V(ex * s, -.075 * s, h2 + ez * s), .011 * s, 'head', 'glow', GLOW, k=.003 * s, amp=0)
            for i in range(7):
                a = -1.2 + i * .4
                sc.chain([V(math.sin(a) * .06 * s, .02 * s, h2 + .16 * s), V(math.sin(a) * .13 * s, .06 * s, h2 + .3 * s), V(math.sin(a) * .17 * s, .1 * s, h2 + (.42 - abs(a) * .06) * s)],
                         [.016 * s, .01 * s, .002 * s], 'head', 'bone', BONE, k=.008 * s, amp=.1)
        if kind == 'mutant':
            sc.cut_ell(V(.03 * s, .0, h2 + .17 * s), V(.06, .07, .04) * s, 'head', 'skin', '#3a0c14', k=.01 * s)
            for c in rand_dirs(rnd, 6, (0, 0, 1), .5):
                sc.sph(V(.03 * s, .0, h2 + .14 * s) + c * .03 * s, .03 * s, 'head', 'acid', ACID, k=.015 * s, amp=0)
        if kind == 'stalker':
            for sx in (1, -1):
                sc.cut_ell(V(sx * .035 * s, -.08 * s, h2 + .12 * s), V(.016, .012, .008) * s, 'head', 'glow', GLOW, k=.003 * s)
    # ---------------- arms
    for side, sx in (('L', 1), ('R', -1)):
        a0, a1 = J['upperarm.' + side]; f0, f1 = J['forearm.' + side]; h0, h1 = J['hand.' + side]
        big = (kind == 'hulk' and side == 'L') or (kind == 'mutant' and side == 'L')
        k_ = {'hulk': 1.5, 'elite': 1.1}.get(kind, .9) * (1.35 if big else 1)
        sc.cone(a0, a1, .05 * s * k_, .04 * s * k_, 'upperarm.' + side, 'skin', FLESH, k=.03 * s, amp=1.4)
        sc.ell(a0 + V(sx * .01, .01, -.06 * s), V(.04, .045, .1) * s * k_, 'upperarm.' + side, 'hide', HIDE, k=.03 * s)
        sc.sph(f0, .042 * s * k_, 'forearm.' + side, 'hide', HIDE, k=.02 * s)
        sc.cone(f0, f1, .045 * s * k_ * (1.3 if big else 1), .036 * s * k_, 'forearm.' + side, 'skin', FLESH, k=.025 * s, amp=1.4)
        if kind in ('hulk', 'elite') or big:
            fa = lambda P, f0=f0, f1=f1, kk=k_: sdf.round_cone(P, f0, f1, .062 * s * kk * (1.25 if big else 1), .05 * s * kk)
            sc.shell(fa, np.minimum(f0, f1) - .25, np.maximum(f0, f1) + .25, .014 * s, 'forearm.' + side, 'plate', PLATE,
                     keep=lambda P, f0=f0, sx=sx: sx * (f0[0] - P[:, 0]) - .005, k=.008 * s, amp=.3)
        if big and kind == 'mutant':
            blobs(sc, rnd, (f0 + f1) / 2, rand_dirs(rnd, 6, (sx, -.3, 0), .8), (.03 * s, .05 * s), 'forearm.' + side, 'sac', '#c8b888', k=.6)
        if kind == 'swimmer':
            fin = lambda P, f0=f0, f1=f1: np.maximum(np.abs(P[:, 0] - (f0[0] + f1[0]) / 2) - .005 * s, sdf.ellipsoid(P, (f0 + f1) / 2 + V(0, .07 * s, .02), V(.03, .07, .16) * s))
            sc.add(fin, np.minimum(f0, f1) - .2, np.maximum(f0, f1) + .2, 'forearm.' + side, 'sac', '#7ab8b8', k=.015 * s, amp=.2)
        sc.ell((h0 + h1) / 2, V(.022, .04, .045) * s * k_, 'hand.' + side, 'hide', HIDE, k=.02 * s)
        if kind == 'elite' and side == 'R':
            sc.chain([h0 + V(0, -.02, -.02), h1 + V(0, -.05, -.15) * s, h1 + V(0, -.1, -.45) * s], [.03 * s, .022 * s, .002], 'hand.R', 'bone', BONE, k=.01 * s, amp=.1)
        else:
            n = 3 if kind != 'swimmer' else 4
            for c in range(n):
                y = (c - (n - 1) / 2) * .022 * s * k_
                L = {'stalker': 1.5, 'swimmer': 1.2, 'hulk': .9}.get(kind, 1.1)
                b0 = V(h1[0], y, h1[2] + .02 * s)
                sc.chain([b0, b0 + V(0, -.02, -.07) * s * L, b0 + V(sx * -.01, -.06, -.14) * s * L, b0 + V(sx * -.01, -.11, -.17) * s * L],
                         [.012 * s * k_, .009 * s * k_, .006 * s, .001], 'hand.' + side, 'skin' if c else 'hide', FLESH if c else HIDE, k=.006 * s, amp=.3)
                sc.cone(b0 + V(sx * -.01, -.06, -.14) * s * L, b0 + V(sx * -.01, -.14, -.18) * s * L, .006 * s, .0008, 'hand.' + side, 'bone', BONE, k=.003, amp=0)
            if kind == 'swimmer':
                web = lambda P, h1=h1: np.maximum(np.abs(P[:, 0] - h1[0]) - .004 * s, sdf.ellipsoid(P, h1 + V(0, -.02, -.07) * s, V(.03, .05, .08) * s))
                sc.add(web, h1 - .2, h1 + .2, 'hand.' + side, 'sac', '#7ab8b8', k=.01 * s, amp=0)
    # ---------------- legs: back-swept, a heel spur, clawed toes
    for side, sx in (('L', 1), ('R', -1)):
        t0, t1 = J['thigh.' + side]; s0, s1 = J['shin.' + side]; q0, q1 = J['foot.' + side]
        lk = {'hulk': 1.4, 'elite': 1.1}.get(kind, .95)
        sc.cone(t0 + V(0, 0, .03), t1, .08 * s * lk, .055 * s * lk, 'thigh.' + side, 'skin', FLESH, k=.035 * s, amp=1.4)
        sc.ell((t0 + t1) / 2 + V(0, -.03, 0), V(.06, .05, .16) * s * lk, 'thigh.' + side, 'hide', HIDE, k=.035 * s)
        sc.sph(t1 + V(0, -.02, 0), .05 * s * lk, 'shin.' + side, 'plate', PLATE, k=.02 * s, amp=.3)
        sc.cone(s0, s1, .05 * s * lk, .03 * s * lk, 'shin.' + side, 'hide', HIDE, k=.025 * s)
        sc.cone(s0 + V(0, .02, -.04), s0 + V(0, .05 * s, -.22 * s), .045 * s * lk, .02 * s, 'shin.' + side, 'skin', FLESH, k=.03 * s, amp=1.4)
        sc.chain([s0 + (s1 - s0) * .55 + V(0, .02, 0), s0 + (s1 - s0) * .6 + V(0, .1 * s, .03 * s), s0 + (s1 - s0) * .62 + V(0, .16 * s, .07 * s)],
                 [.02 * s, .012 * s, .002], 'shin.' + side, 'bone', BONE, k=.008 * s, amp=.1)
        sc.ell(V(q0[0], -.06 * s, .045 * s), V(.045, .1, .035) * s * lk, 'foot.' + side, 'hide', HIDE, k=.02 * s)
        for c in (-1, 0, 1):
            b0 = V(q0[0] + c * .028 * s, -.13 * s, .04 * s)
            sc.chain([b0, b0 + V(c * .01, -.06, -.02) * s, b0 + V(c * .015, -.1, -.04) * s], [.012 * s * lk, .008 * s, .001], 'foot.' + side, 'bone', BONE, k=.006 * s, amp=0)
    # ---------------- pustules, tendrils
    for c in rand_dirs(rnd, {'mutant': 6, 'hulk': 8}.get(kind, 7), (0, .6, .5), 1.0):
        p = sc.surface_point(V(0, .02, cz + .08 * s), c, 1.2)
        r = (.012 + .02 * rnd.random()) * s
        g = rnd.random() < .45
        sc.sph(p + c * r * .75, r, 'chest', 'glow' if g else 'sac', GLOW if g else '#d8c8a0', k=r * .3, amp=0)
    if kind in ('stalker', 'mutant', 'elite'):
        for c in rand_dirs(rnd, 3, (0, .6, -1), .4):
            st = sc.surface_point(V(0, .02, sz + .05 * s), c, 1.0)
            sc.chain([st, st + V(0, .06, -.1) * s, st + V(.03, .1, -.25) * s, st + V(-.02, .14, -.4) * s], [.016 * s, .011 * s, .006 * s, .001],
                     'spine', 'skin', FLESH, k=.01 * s, writhe=(.3, 1))
    return sc, J


def build(kind):
    bl.reset()
    s = KINDS[kind][0]
    sc, J = build_kind(kind)
    o = fk.build_mesh(sc, 'Body_' + kind, np.array([-.62, -.62, -.03]) * s, np.array([.62, .55, 2.0]) * s, .0085 * s, 9000, mats(kind),
                      uv_scale=.45 * s, ao_dist=.06 * s, seed=sum(map(ord, kind)) % 97, bruise=('#5a3a5a', .4, 4.0), veins=('#3a1a3a', .45, 5.0))
    arm = fk.make_rig(J)
    st = {'stalker': dict(hunch=30, loll=0, both=True, drag=False, twitch=.5, lean=38),
          'hulk': dict(hunch=22, loll=0, both=True, drag=False, twitch=.3, lean=24, height=1.5),
          'mutant': dict(hunch=14, loll=22, drag=True, twitch=1.0, lean=26),
          'swimmer': dict(hunch=26, loll=0, both=True, drag=False, twitch=.5, lean=34),
          'elite': dict(hunch=8, loll=0, both=True, drag=False, twitch=.3, lean=26, height=1.3)}[kind]
    fk.bake_clips(arm, humanoid_clips(st), 'hips', 1.0)
    fk.finish(o, arm, 'alien_%s.glb' % kind)


if __name__ == '__main__':
    only = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    for k in KINDS:
        if not only or k in only:
            build(k)
