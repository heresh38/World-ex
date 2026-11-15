"""THE FIRST BODIES OF MERIDIAN'S ENEMIES, BEING REPLACED (the story since 2026-11-14, docs/story/WORLD.md: one
humanoid species, the Sarketh, ranked by what they are issued; their new bodies are tools/blender/hero/sarketh.py).
What follows describes these first bodies as they were written.

The Altered: people and beasts the Stillfall changed, grown through with void crystal (the violet shards that crust
Meridian's ruins). Sculpted as signed-distance fields with fleshkit (ashen hide, cracked plates, crystal erupting
through the body, violet light in the cracks), soft-skinned to the shared 20-bone rig, vertex-coloured over the
shared hx_* texture sets.

  remnant    a husk: emaciated, hunched, a hanging jaw, glowing eye slits, shards through the skull and the shoulder
             blades, rags of the clothes it died in, long hooked fingers (fast, frail, comes in numbers)
  veilborn   tall and gaunt, a hood of hide round a crystal mask, an open chest caging a light, a veil of flesh strips
             from the shoulders, three long fingers that gather light (keeps its distance, hurls void bolts)
  bulwark    a hulk: a great slab of crystal-plated bone grown over the left forearm as a shield, a spiked club fist,
             a crystal ridge down the back, the head sunk between the shoulders (slow; the shield turns shots)
  bearer     the gun carrier: a broad husk plated like a strongpoint (a breastplate in three lames with light in the
             seams, a collar of plate round a small sunken head with one slit of light, a great pauldron over the gun
             arm), a drum of crystal-fused bone across its back that feeds the heavy gun it carries at the hip, the
             feed coming round under the arm to a port on its belt (slow; keeps a place under fire)
  colossus   the Hollow Colossus, the operation's boss (~2.6 m, a head over a soldier): stone-hard plates fused over the body with light in every
             crack, a hollow ribcage round a burning crystal heart (its weak point), a crown of shards, long arms and
             great clawed hands, crystal masses on the shoulders and back

Materials (names are an API): alt_skin, alt_flesh, alt_plate, alt_bone, alt_rag (hx_* sets), alt_crystal and
alt_glow (emissive). Clips: Idle, Walk, Run, Attack, Death; the veilborn adds Cast and Blink, the bulwark Slam, the
colossus Slam, Sweep, Barrage and Shield, the bearer Brace.

Run: blender --background --python tools/blender/altered.py [-- remnant veilborn bulwark colossus bearer]
"""
import math, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import bl, sdf
import fleshkit as fk
from fleshkit import X, Y, Z, S, TAU2, pulse, smooth, fbm, ridge
from writhe import human_joints, humanoid_clips, rand_dirs, teeth_ring

PI = math.pi
ASH = '#aaa59f'; ASH_D = '#7a7470'; HIDE = '#8a8482'; PLATE = '#3c3744'; PLATE_L = '#5a5662'; BONE = '#d6cfc2'
CAV = '#1c0a22'; RAG = '#4a4440'; CRYSTAL = '#9a5cff'; GLOW = '#c08cff'

KINDS = {'remnant': .98, 'veilborn': 1.18, 'bulwark': 1.5, 'colossus': 1.45, 'bearer': 1.3}


def mats():
    return dict(skin=fk.tmat('alt_skin', 'hx_skin', nstr=1.3), flesh=fk.tmat('alt_flesh', 'hx_flesh', nstr=1.2),
                plate=fk.tmat('alt_plate', 'hx_chitin', nstr=1.3), bone=fk.tmat('alt_bone', 'hx_bone'),
                rag=fk.tmat('alt_rag', 'hx_rag'), crystal=fk.glow_mat('alt_crystal', CRYSTAL, 6), glow=fk.glow_mat('alt_glow', GLOW, 4))


V = lambda *a: np.array(a, float)


def shard(sc, base, dirn, length, r, bone, k=.004):
    """a crystal spike growing out of the body"""
    d = np.asarray(dirn, float); d = d / np.linalg.norm(d)
    sc.cone(base - d * r * .6, base + d * length, r, r * .06, bone, 'crystal', CRYSTAL, k=k, amp=0)


def cluster(sc, rnd, base, up, n, length, r, bone):
    for i in range(n):
        d = np.asarray(up, float) + np.array([rnd.uniform(-.6, .6), rnd.uniform(-.6, .6), rnd.uniform(-.3, .3)])
        shard(sc, base + np.array([rnd.uniform(-1, 1), rnd.uniform(-1, 1), 0]) * r * .8, d, length * rnd.uniform(.55, 1.0), r * rnd.uniform(.6, 1.0), bone)


def glow_vein(sc, pts, r, bone):
    """a crack of violet light along the hide"""
    sc.chain([np.asarray(p, float) for p in pts], [r] * len(pts), bone, 'glow', GLOW, k=r * .5, amp=0)


def legs(sc, J, s, lk, hide=HIDE, toes=3, plate=False):
    for side, sx in (('L', 1), ('R', -1)):
        t0, t1 = J['thigh.' + side]; s0, s1 = J['shin.' + side]; q0, q1 = J['foot.' + side]
        sc.cone(t0 + V(0, 0, .03), t1, .075 * s * lk, .05 * s * lk, 'thigh.' + side, 'skin', ASH, k=.035 * s, amp=1.3)
        sc.ell((t0 + t1) / 2 + V(0, -.02, 0), V(.055, .05, .15) * s * lk, 'thigh.' + side, 'flesh', ASH_D, k=.03 * s, amp=1.2)
        sc.sph(t1 + V(0, -.015, 0), .045 * s * lk, 'shin.' + side, 'plate' if plate else 'skin', PLATE if plate else ASH, k=.02 * s, amp=.4)
        sc.cone(s0, s1, .045 * s * lk, .028 * s * lk, 'shin.' + side, 'skin', hide, k=.022 * s, amp=1.2)
        sc.cone(s0 + V(0, .02, -.03), s0 + V(0, .04 * s, -.2 * s), .04 * s * lk, .02 * s, 'shin.' + side, 'flesh', ASH_D, k=.025 * s, amp=1.2)
        if plate:
            fn = lambda P, s0=s0, s1=s1: sdf.round_cone(P, s0, s1, .062 * s * lk, .042 * s * lk)
            sc.shell(fn, np.minimum(s0, s1) - .3 * s, np.maximum(s0, s1) + .3 * s, .012 * s, 'shin.' + side, 'plate', PLATE,
                     keep=lambda P, s0=s0: (P[:, 1] - s0[1]) + .01 * s, holes=(6 / s, .7, 3), k=.006 * s, amp=.3)
        sc.ell(V(q0[0], -.055 * s, .042 * s), V(.042, .095, .034) * s * lk, 'foot.' + side, 'skin', hide, k=.02 * s)
        for c in range(toes):
            cc = c - (toes - 1) / 2
            b0 = V(q0[0] + cc * .026 * s * lk, -.125 * s, .038 * s)
            sc.chain([b0, b0 + V(cc * .01, -.055, -.02) * s, b0 + V(cc * .014, -.09, -.036) * s], [.011 * s * lk, .007 * s, .001],
                     'foot.' + side, 'bone', BONE, k=.005 * s, amp=0)


def hands(sc, J, s, k_, side, sx, fingers=4, length=1.0, fat=1.0):
    h0, h1 = J['hand.' + side]
    sc.ell((h0 + h1) / 2, V(.022, .038, .045) * s * k_ * fat, 'hand.' + side, 'skin', ASH, k=.018 * s)
    for c in range(fingers):
        y = (c - (fingers - 1) / 2) * .02 * s * k_ * fat
        b0 = V(h1[0], y, h1[2] + .015 * s)
        L = length
        sc.chain([b0, b0 + V(0, -.015, -.065) * s * L, b0 + V(sx * -.008, -.05, -.13) * s * L, b0 + V(sx * -.01, -.09, -.16) * s * L],
                 [.0105 * s * k_, .008 * s * k_, .0055 * s, .001], 'hand.' + side, 'skin', ASH, k=.005 * s, amp=.3)
        sc.cone(b0 + V(sx * -.01, -.05, -.13) * s * L, b0 + V(sx * -.01, -.12, -.17) * s * L, .0055 * s, .0008, 'hand.' + side, 'bone', BONE, k=.003, amp=0)


def arm(sc, J, s, k_, side, sx, mat='skin', col=ASH):
    a0, a1 = J['upperarm.' + side]; f0, f1 = J['forearm.' + side]
    sc.cone(a0, a1, .048 * s * k_, .036 * s * k_, 'upperarm.' + side, mat, col, k=.028 * s, amp=1.3)
    sc.ell(a0 + V(sx * .01, .01, -.06 * s), V(.038, .042, .1) * s * k_, 'upperarm.' + side, 'flesh', ASH_D, k=.028 * s, amp=1.2)
    sc.sph(f0, .038 * s * k_, 'forearm.' + side, 'skin', HIDE, k=.018 * s)
    sc.cone(f0, f1, .04 * s * k_, .03 * s * k_, 'forearm.' + side, mat, col, k=.022 * s, amp=1.3)


# ------------------------------------------------------------------ the creatures
def remnant(s):
    J = human_joints(s)
    sc = fk.Sculpt(11); rnd = sc.rnd
    sc.disp = lambda P: (fbm(P, 20 / s, 3, 1) - .5) * .008 * s + ridge(P, 6 / s, 2, 8) * .007 * s
    hz = J['hips'][0][2]; sz = J['spine'][0][2]; cz = J['chest'][0][2]; nz = J['neck'][0][2]; h2 = J['head'][0][2]
    # a starved frame: narrow pelvis, the belly sunk under the ribs, ribs and spine pressing through the hide
    sc.ell(V(0, .01, hz), V(.12, .085, .09) * s, 'hips', 'skin', ASH, k=.03 * s)
    sc.ell(V(0, .03, sz + .1 * s), V(.07, .05, .12) * s, 'spine', 'skin', ASH, k=.04 * s, amp=1.4)
    sc.cut_ell(V(0, -.05 * s, sz + .12 * s), V(.06, .03, .07) * s, 'spine', 'flesh', ASH_D, k=.03 * s)
    sc.ell(V(0, .01, cz + .1 * s), V(.13, .095, .13) * s, 'chest', 'skin', ASH, k=.05 * s)
    for sx in (1, -1):
        sc.cone(V(sx * .05, .01, cz + .17 * s), J['upperarm.' + ('L' if sx > 0 else 'R')][0], .045 * s, .045 * s, 'chest', 'skin', ASH, k=.035 * s)
        for i in range(5):                                       # ribs under the skin
            z = cz + (-.03 + i * .035) * s
            sc.chain([V(sx * .03, -.095 * s, z), V(sx * .11, -.07 * s, z - .01 * s), V(sx * .13, .0, z - .02 * s)],
                     [.008 * s, .008 * s, .006 * s], 'chest', 'skin', ASH, k=.01 * s, amp=.4)
    for i in range(8):                                           # the spine's knuckles
        z = hz + .08 * s + i * .045 * s
        sc.sph(V(0, .07 * s + (.03 * s if z > cz else 0), z), .018 * s, 'chest' if z > cz else 'spine', 'skin', ASH, k=.012 * s)
    # shards through the shoulder blades and the back
    for sx in (1, -1):
        b = V(sx * .07 * s, .09 * s, cz + .12 * s)
        shard(sc, b, (sx * .5, 1, .8), .26 * s, .03 * s, 'chest')
        shard(sc, b + V(sx * .02, 0, -.06) * s, (sx * .8, .8, .4), .16 * s, .022 * s, 'chest')
        glow_vein(sc, [b, b + V(-sx * .04, -.03, -.08) * s, b + V(-sx * .05, -.08, -.18) * s], .006 * s, 'chest')
    # rags: torn strips of the clothes it died in, hanging from a belt of cloth round the hips
    sc.chain([V(.13 * math.cos(a), .095 * math.sin(a), hz + .05 * s) for a in np.linspace(0, TAU2, 13)], [.016 * s] * 13, 'hips', 'rag', RAG, k=.006 * s, amp=.3)
    for i in range(9):
        a = i * TAU2 / 9 + .3
        top = V(.135 * math.cos(a) * s, .1 * math.sin(a) * s, hz + .04 * s)
        L = (.18 + .14 * ((i * 7) % 5) / 4) * s
        out = V(math.cos(a), math.sin(a), 0)
        sc.chain([top, top + out * .025 * s + V(0, 0, -L * .5), top + out * .035 * s + V(0, .01 * s, -L)], [.03 * s, .026 * s, .006 * s],
                 'hips', 'rag', RAG, k=.006 * s, writhe=(.1, .4), amp=.4)
    # neck and a gaunt skull, the jaw hanging open, eyes a violet slit, a shard through the skull
    sc.cone(V(0, .02, nz - .02), V(0, -.01 * s, nz + .11 * s), .035 * s, .032 * s, 'neck', 'skin', ASH, k=.025 * s, amp=1.4)
    sc.ell(V(0, -.005 * s, h2 + .1 * s), V(.068, .085, .09) * s, 'head', 'skin', ASH, k=.03 * s)
    sc.cut_ell(V(0, -.075 * s, h2 + .125 * s), V(.05, .02, .012) * s, 'head', 'glow', GLOW, k=.006 * s)
    for sx in (1, -1):
        sc.cut_ell(V(sx * .035 * s, -.07 * s, h2 + .08 * s), V(.022, .02, .03) * s, 'head', 'skin', ASH_D, k=.01 * s)
    sc.cut_ell(V(0, -.085 * s, h2 + .02 * s), V(.035, .04, .04) * s, 'head', 'flesh', CAV, k=.008 * s)
    teeth_ring(sc, V(0, -.085 * s, h2 + .02 * s), .03 * s, .035 * s, 10, 'head', (0, 1, 0), .018 * s, .004 * s)
    sc.ell(V(0, -.07 * s, h2 - .045 * s), V(.04, .035, .025) * s, 'head', 'bone', BONE, k=.012 * s)     # the hanging jaw
    shard(sc, V(.04 * s, .0, h2 + .15 * s), (.7, .3, .9), .2 * s, .028 * s, 'head')
    shard(sc, V(.05 * s, .02 * s, h2 + .11 * s), (1, .2, .3), .1 * s, .016 * s, 'head')
    glow_vein(sc, [V(.04, -.02, h2 + .15) * [s, s, 1], V(.0, -.06 * s, h2 + .13 * s), V(-.03 * s, -.07 * s, h2 + .06 * s)], .005 * s, 'head')
    for side, sx in (('L', 1), ('R', -1)):
        arm(sc, J, s, .95, side, sx)
        hands(sc, J, s, .95, side, sx, 4, 1.3)
        a0, a1 = J['upperarm.' + side]; f0, f1 = J['forearm.' + side]
        glow_vein(sc, [a0 + V(sx * .02, -.03, -.05), (a0 + a1) / 2 + V(sx * .03, -.035, 0), f0 + V(sx * .02, -.03, 0), (f0 + f1) / 2 + V(sx * .02, -.03, 0)], .005 * s, 'upperarm.' + side)
    shard(sc, (J['forearm.R'][0] + J['forearm.R'][1]) / 2 + V(-.03, .02, 0) * s, (-1, .3, .2), .12 * s, .02 * s, 'forearm.R')
    legs(sc, J, s, 1.0)
    return sc, J, dict(hunch=34, loll=24, both=True, drag=False, twitch=1.0, lean=42)


def veilborn(s):
    J = human_joints(s)
    # longer arms and fingers: stretch the forearm and hand chains
    for side in ('L', 'R'):
        f0, f1 = J['forearm.' + side]; h0, h1 = J['hand.' + side]
        ext = (f1 - f0) * .25
        J['forearm.' + side] = (f0, f1 + ext); J['hand.' + side] = (h0 + ext, h1 + ext * 1.3)
    sc = fk.Sculpt(23); rnd = sc.rnd
    sc.disp = lambda P: (fbm(P, 18 / s, 3, 2) - .5) * .006 * s + ridge(P, 5 / s, 3, 8) * .005 * s
    hz = J['hips'][0][2]; sz = J['spine'][0][2]; cz = J['chest'][0][2]; nz = J['neck'][0][2]; h2 = J['head'][0][2]
    sc.ell(V(0, .01, hz), V(.11, .08, .09) * s, 'hips', 'skin', HIDE, k=.03 * s)
    sc.ell(V(0, .02, sz + .1 * s), V(.06, .05, .13) * s, 'spine', 'skin', HIDE, k=.035 * s, amp=1.2)
    sc.ell(V(0, .01, cz + .1 * s), V(.12, .085, .14) * s, 'chest', 'skin', HIDE, k=.045 * s)
    for sx in (1, -1):
        sc.cone(V(sx * .05, .01, cz + .17 * s), J['upperarm.' + ('L' if sx > 0 else 'R')][0], .04 * s, .04 * s, 'chest', 'skin', HIDE, k=.03 * s)
    # the open chest: a cavity, a cage of crystal round a light
    sc.cut_ell(V(0, -.07 * s, cz + .09 * s), V(.065, .06, .09) * s, 'chest', 'flesh', CAV, k=.012 * s)
    sc.sph(V(0, -.045 * s, cz + .09 * s), .04 * s, 'chest', 'glow', GLOW, k=.01 * s, amp=0)
    for i in range(6):
        a = -1.2 + i * .48
        b = V(math.sin(a) * .06 * s, -.03 * s, cz + .02 * s)
        shard(sc, b, (math.sin(a) * .3, -1, 1.6), .17 * s, .011 * s, 'chest')
    # the veil: strips of hide falling from the shoulders and the hips, swaying
    for i in range(9):
        a = -1.9 + i * .475
        top = V(math.sin(a) * .15 * s, math.cos(a) * .1 * s, cz + .2 * s)
        bone = 'chest'
        pts = [top, top + V(math.sin(a) * .03, math.cos(a) * .05 + .03, -.3) * s, top + V(math.sin(a) * .05, math.cos(a) * .07 + .05, -.7) * s,
               top + V(math.sin(a) * .06, math.cos(a) * .08 + .06, -1.05 + .1 * (i % 3)) * s]
        sc.chain(pts, [.03 * s, .028 * s, .022 * s, .004 * s], bone, 'skin', ASH_D, k=.01 * s, writhe=(.15, .6), amp=.5)
    # hood of hide round a crystal mask
    sc.cone(V(0, .02, nz - .02), V(0, -.01 * s, nz + .12 * s), .038 * s, .034 * s, 'neck', 'skin', HIDE, k=.025 * s, amp=1.2)
    hood = lambda P: sdf.ellipsoid(P, V(0, .02 * s, h2 + .12 * s), V(.1, .12, .13) * s)
    sc.shell(hood, V(-.3, -.3, h2 - .1) * [s, s, 1], V(.3, .3, h2 + .4), .012 * s, 'head', 'skin', ASH_D,
             keep=lambda P: -(P[:, 1] + .05 * s) * 1.0, k=.006 * s, amp=.5)
    sc.ell(V(0, -.005 * s, h2 + .1 * s), V(.06, .075, .085) * s, 'head', 'skin', HIDE, k=.025 * s)
    sc.ell(V(0, -.068 * s, h2 + .1 * s), V(.05, .022, .07) * s, 'head', 'crystal', CRYSTAL, k=.006 * s, amp=0)
    for sx in (1, -1):
        sc.cut_ell(V(sx * .022 * s, -.088 * s, h2 + .115 * s), V(.012, .006, .006) * s, 'head', 'glow', '#ffffff', k=.002 * s)
    shard(sc, V(0, .04 * s, h2 + .2 * s), (0, .5, 1), .22 * s, .026 * s, 'head')
    shard(sc, V(.05 * s, .03 * s, h2 + .18 * s), (.6, .4, 1), .14 * s, .018 * s, 'head')
    shard(sc, V(-.05 * s, .03 * s, h2 + .18 * s), (-.6, .4, 1), .14 * s, .018 * s, 'head')
    for side, sx in (('L', 1), ('R', -1)):
        arm(sc, J, s, .78, side, sx, 'skin', HIDE)
        hands(sc, J, s, .9, side, sx, 3, 1.8)
        h0, h1 = J['hand.' + side]
        sc.sph((h0 + h1) / 2 + V(0, -.03 * s, 0), .018 * s, 'hand.' + side, 'glow', GLOW, k=.004 * s, amp=0)
        f0, f1 = J['forearm.' + side]
        glow_vein(sc, [f0 + V(0, -.03, 0) * s, (f0 + f1) / 2 + V(0, -.035, 0) * s, f1 + V(0, -.03, 0) * s], .005 * s, 'forearm.' + side)
    legs(sc, J, s, .8, toes=2)
    return sc, J, dict(hunch=6, loll=0, both=True, drag=False, twitch=.35, lean=18, height=1.2)


def bulwark(s):
    J = human_joints(s)
    sc = fk.Sculpt(37); rnd = sc.rnd
    sc.disp = lambda P: (fbm(P, 14 / s, 3, 3) - .5) * .01 * s + ridge(P, 4 / s, 4, 8) * .008 * s
    hz = J['hips'][0][2]; sz = J['spine'][0][2]; cz = J['chest'][0][2]; nz = J['neck'][0][2]; h2 = J['head'][0][2]
    W = 1.45
    sc.ell(V(0, .01, hz), V(.15, .1, .1) * s * [W * .9, 1, 1], 'hips', 'skin', HIDE, k=.035 * s)
    sc.ell(V(0, .02, sz + .1 * s), V(.11, .08, .12) * s * [W, 1, 1], 'spine', 'flesh', ASH_D, k=.05 * s, amp=1.4)
    sc.ell(V(0, .03, cz + .12 * s), V(.17, .13, .16) * s * [W, 1.15, 1], 'chest', 'skin', HIDE, k=.06 * s)
    # the hump: plates fused over the shoulders and back, a ridge of crystal down the spine
    hump = lambda P: sdf.ellipsoid(P, V(0, .09 * s, cz + .15 * s), V(.27, .19, .2) * s)
    sc.ell(V(0, .08 * s, cz + .14 * s), V(.24, .16, .18) * s, 'chest', 'flesh', ASH_D, k=.06 * s, amp=1.3)
    sc.shell(hump, V(-.5, -.2, cz - .2) * [s, s, 1], V(.5, .5, cz + .6), .03 * s, 'chest', 'plate', PLATE,
             keep=lambda P: -(P[:, 1] - .03 * s), holes=(4 / s, .7, 6), k=.016 * s, amp=.3)
    for i in range(6):
        z = cz + (.28 - i * .07) * s
        shard(sc, V(0, .2 * s - i * .012 * s, z), (0, .7, .7), (.22 - i * .02) * s, .04 * s, 'chest' if z > cz else 'spine')
    for c in rand_dirs(rnd, 7, (0, 1, .5), .8):
        p = sc.surface_point(V(0, .09 * s, cz + .15 * s), c, 1.2)
        sc.sph(p, .02 * s, 'chest', 'glow', GLOW, k=.006 * s, amp=0)
    for sx in (1, -1):
        sh = J['upperarm.' + ('L' if sx > 0 else 'R')][0]
        sc.cone(V(sx * .07, .02, cz + .18 * s), sh, .07 * s, .08 * s, 'chest', 'skin', HIDE, k=.05 * s)
    # the head sunk between the shoulders, a heavy brow plate, a glow under it, tusks of crystal
    sc.cone(V(0, .0, nz - .03), V(0, -.04 * s, nz + .08 * s), .065 * s, .055 * s, 'neck', 'flesh', ASH_D, k=.04 * s, amp=1.3)
    sc.ell(V(0, -.07 * s, h2 + .02 * s), V(.08, .085, .075) * s, 'head', 'skin', HIDE, k=.03 * s)
    sc.ell(V(0, -.1 * s, h2 + .07 * s), V(.085, .05, .035) * s, 'head', 'plate', PLATE, k=.015 * s, amp=.3)
    for sx in (1, -1):
        sc.cut_ell(V(sx * .035 * s, -.15 * s, h2 + .035 * s), V(.016, .01, .008) * s, 'head', 'glow', GLOW, k=.003 * s)
        shard(sc, V(sx * .045 * s, -.14 * s, h2 - .03 * s), (sx * .3, -.6, .9), .07 * s, .014 * s, 'head')
    sc.cut_ell(V(0, -.15 * s, h2 - .02 * s), V(.04, .03, .02) * s, 'head', 'flesh', CAV, k=.008 * s)
    teeth_ring(sc, V(0, -.15 * s, h2 - .02 * s), .035 * s, .02 * s, 10, 'head', (0, 1, 0), .02 * s, .006 * s)
    # left: the shield arm, a slab of crystal-plated bone over the forearm
    arm(sc, J, s, 1.55, 'L', 1, 'skin', HIDE)
    f0, f1 = J['forearm.L']
    mid = (f0 + f1) / 2 + V(.05, -.06, 0) * s
    # an oval plate, domed outward, grown over the forearm
    nrm = np.array([math.cos(.25), math.sin(.25), 0.0])

    e1 = np.array([-math.sin(.25), math.cos(.25), 0.0]); e2 = np.array([0.0, 0.0, 1.0])
    B, C, crown, th = .24 * s, .37 * s, .07 * s, .022 * s

    def slab(P, mid=mid, nrm=nrm):
        q = P - mid
        u, v, w = q @ nrm, q @ e1, q @ e2
        r2 = (v / B) ** 2 + (w / C) ** 2
        dome = crown * (1 - np.minimum(r2, 1.5))
        plate = np.abs(u - dome) - th * (1 - .4 * np.minimum(r2, 1))
        outline = (np.sqrt(r2) - 1) * min(B, C)
        return sdf.smax(plate, outline, .012 * s)
    sc.add(slab, mid - .6 * s, mid + .6 * s, 'forearm.L', 'plate', PLATE_L, k=.03 * s, amp=.4)
    for i in range(5):
        p = mid + V(.04, -.17 + i * .08, -.25 + (i % 2) * .5) * s
        shard(sc, p, (1, -.3, .2 * (i - 2)), .1 * s, .03 * s, 'forearm.L')
    glow_vein(sc, [mid + V(.04, -.12, .22) * s, mid + V(.045, 0, .05) * s, mid + V(.04, .1, -.2) * s], .008 * s, 'forearm.L')
    hands(sc, J, s, 1.5, 'L', 1, 3, .8, 1.3)
    # right: the club fist, bone spikes over the knuckles
    arm(sc, J, s, 1.6, 'R', -1, 'skin', HIDE)
    h0, h1 = J['hand.R']
    sc.ell((h0 + h1) / 2, V(.07, .075, .085) * s, 'hand.R', 'plate', PLATE, k=.03 * s, amp=.4)
    for c in rand_dirs(rnd, 6, (0, -1, -.6), .7):
        p = sc.surface_point((h0 + h1) / 2, c, .6)
        sc.cone(p, p + np.asarray(c) * .07 * s, .016 * s, .002 * s, 'hand.R', 'bone', BONE, k=.005 * s, amp=0)
    legs(sc, J, s, 1.45, toes=3, plate=True)
    return sc, J, dict(hunch=20, loll=0, both=True, drag=False, twitch=.25, lean=22, height=1.5)


def colossus(s):
    J = human_joints(s)
    for side in ('L', 'R'):                                      # longer arms, reaching to the knees
        f0, f1 = J['forearm.' + side]; h0, h1 = J['hand.' + side]
        ext = (f1 - f0) * .3
        J['forearm.' + side] = (f0, f1 + ext); J['hand.' + side] = (h0 + ext, h1 + ext)
    sc = fk.Sculpt(53); rnd = sc.rnd
    sc.disp = lambda P: (fbm(P, 10 / s, 3, 4) - .5) * .008 * s + ridge(P, 3 / s, 5, 7) * .009 * s
    hz = J['hips'][0][2]; sz = J['spine'][0][2]; cz = J['chest'][0][2]; nz = J['neck'][0][2]; h2 = J['head'][0][2]
    W = 1.35
    sc.ell(V(0, .01, hz), V(.15, .1, .1) * s * [W, 1, 1], 'hips', 'plate', PLATE, k=.03 * s, amp=.4)
    sc.ell(V(0, .02, sz + .1 * s), V(.1, .075, .12) * s * [W, 1, 1], 'spine', 'flesh', ASH_D, k=.04 * s, amp=1.2)
    # the hollow ribcage round the heart
    sc.ell(V(0, .04 * s, cz + .12 * s), V(.17, .12, .16) * s * [W, 1, 1], 'chest', 'plate', PLATE, k=.05 * s, amp=.4)
    sc.cut_ell(V(0, -.07 * s, cz + .1 * s), V(.1, .09, .12) * s, 'chest', 'flesh', CAV, k=.012 * s)
    heart = V(0, -.05 * s, cz + .1 * s)
    sc.ell(heart, V(.045, .04, .06) * s, 'chest', 'crystal', CRYSTAL, k=.004 * s, amp=0)
    for sx in (1, -1):
        for i in range(5):
            z = cz + (-.02 + i * .045) * s
            sc.chain([V(sx * .025, -.15 * s, z), V(sx * .12 * W, -.12 * s, z - .005 * s), V(sx * .17 * W, -.02 * s, z - .015 * s)],
                     [.014 * s, .013 * s, .012 * s], 'chest', 'bone', BONE, k=.008 * s, amp=.2)
    # stone plates over the shoulders and back with light in every crack, crystal masses
    back = lambda P: sdf.ellipsoid(P, V(0, .08 * s, cz + .14 * s), V(.25 * W, .16, .2) * s)
    sc.ell(V(0, .07 * s, cz + .13 * s), V(.22 * W, .13, .17) * s, 'chest', 'glow', GLOW, k=.04 * s, amp=0)
    sc.shell(back, V(-.6, -.3, cz - .3) * [s, s, 1], V(.6, .5, cz + .7), .028 * s, 'chest', 'plate', PLATE_L,
             keep=lambda P: -(P[:, 1] + .02 * s), holes=(5 / s, .78, 9), k=.01 * s, amp=.3)
    for sx in (1, -1):
        sh = J['upperarm.' + ('L' if sx > 0 else 'R')][0]
        sc.cone(V(sx * .07, .03, cz + .18 * s), sh, .075 * s, .085 * s, 'chest', 'plate', PLATE, k=.05 * s, amp=.4)
        cluster(sc, rnd, sh + V(sx * .02, .03, .07) * s, (sx * .6, .3, 1), 6, .3 * s, .05 * s, 'chest')
    cluster(sc, rnd, V(0, .2 * s, cz + .2 * s), (0, .9, .6), 7, .45 * s, .06 * s, 'chest')
    cluster(sc, rnd, V(0, .14 * s, sz + .1 * s), (0, 1, .1), 4, .25 * s, .04 * s, 'spine')
    # head: a heavy plated skull, two burning eyes, a crown of shards
    sc.cone(V(0, .02, nz - .02), V(0, -.02 * s, nz + .1 * s), .06 * s, .055 * s, 'neck', 'flesh', ASH_D, k=.04 * s, amp=1.2)
    sc.ell(V(0, -.02 * s, h2 + .09 * s), V(.085, .1, .1) * s, 'head', 'plate', PLATE, k=.03 * s, amp=.4)
    sc.cut_ell(V(0, -.11 * s, h2 + .05 * s), V(.05, .03, .03) * s, 'head', 'flesh', CAV, k=.01 * s)
    for sx in (1, -1):
        sc.cut_ell(V(sx * .038 * s, -.1 * s, h2 + .115 * s), V(.02, .012, .012) * s, 'head', 'glow', '#ffffff', k=.004 * s)
    for i in range(7):
        a = -1.25 + i * .42
        shard(sc, V(math.sin(a) * .07 * s, .01 * s + abs(math.sin(a)) * .02 * s, h2 + .17 * s), (math.sin(a) * .6, .25, 1),
              (.32 - abs(a) * .1) * s, .03 * s, 'head')
    for side, sx in (('L', 1), ('R', -1)):
        a0, a1 = J['upperarm.' + side]; f0, f1 = J['forearm.' + side]
        sc.cone(a0, a1, .07 * s, .055 * s, 'upperarm.' + side, 'flesh', ASH_D, k=.04 * s, amp=1.2)
        fa = lambda P, a0=a0, a1=a1: sdf.round_cone(P, a0, a1, .082 * s, .066 * s)
        sc.shell(fa, np.minimum(a0, a1) - .3 * s, np.maximum(a0, a1) + .3 * s, .018 * s, 'upperarm.' + side, 'plate', PLATE,
                 keep=lambda P, a0=a0, sx=sx: sx * (a0[0] - P[:, 0]) - .01 * s, holes=(6 / s, .74, 7), k=.008 * s, amp=.3)
        sc.sph(f0, .06 * s, 'forearm.' + side, 'plate', PLATE_L, k=.025 * s, amp=.4)
        sc.cone(f0, f1, .062 * s, .05 * s, 'forearm.' + side, 'flesh', ASH_D, k=.03 * s, amp=1.2)
        fb = lambda P, f0=f0, f1=f1: sdf.round_cone(P, f0, f1, .074 * s, .06 * s)
        sc.shell(fb, np.minimum(f0, f1) - .3 * s, np.maximum(f0, f1) + .3 * s, .016 * s, 'forearm.' + side, 'plate', PLATE,
                 keep=lambda P, f0=f0, sx=sx: sx * (f0[0] - P[:, 0]) - .012 * s, holes=(6 / s, .74, 8), k=.008 * s, amp=.3)
        glow_vein(sc, [f0 + V(sx * .02, -.05, 0) * s, (f0 + f1) / 2 + V(sx * .03, -.055, 0) * s, f1 + V(sx * .02, -.045, 0) * s], .008 * s, 'forearm.' + side)
        shard(sc, (f0 + f1) / 2 + V(sx * .06, .02, 0) * s, (sx, .4, .3), .16 * s, .028 * s, 'forearm.' + side)
        hands(sc, J, s, 1.5, side, sx, 4, 1.15, 1.2)
    legs(sc, J, s, 1.5, toes=3, plate=True)
    return sc, J, dict(hunch=12, loll=0, both=True, drag=False, twitch=.15, lean=14, height=1.45)


def bearer(s):
    J = human_joints(s)
    sc = fk.Sculpt(71); rnd = sc.rnd
    sc.disp = lambda P: (fbm(P, 14 / s, 3, 5) - .5) * .006 * s + ridge(P, 4 / s, 6, 8) * .005 * s
    hz = J['hips'][0][2]; sz = J['spine'][0][2]; cz = J['chest'][0][2]; nz = J['neck'][0][2]; h2 = J['head'][0][2]
    W = 1.3
    # the body under the plate: a thick trunk, square across the shoulders
    sc.ell(V(0, .01 * s, hz), V(.15 * W, .11, .11) * s, 'hips', 'skin', HIDE, k=.035 * s)
    sc.ell(V(0, .015 * s, sz + .1 * s), V(.125 * W, .095, .13) * s, 'spine', 'flesh', ASH_D, k=.05 * s, amp=1.2)
    sc.ell(V(0, .005 * s, hz - .05 * s), V(.1, .095, .06) * s, 'hips', 'skin', HIDE, k=.03 * s)
    sc.ell(V(0, .02 * s, cz + .11 * s), V(.175 * W, .13, .16) * s, 'chest', 'skin', HIDE, k=.06 * s)
    for sx in (1, -1):
        sh = J['upperarm.' + ('L' if sx > 0 else 'R')][0]
        sc.cone(V(sx * .08 * s, .02 * s, cz + .18 * s), sh, .075 * s, .08 * s, 'chest', 'skin', HIDE, k=.05 * s)
    # the breastplate: one shell round the chest, front and flanks, its lower edge a straight line; two seams across
    # it make three lames, with light in the seams
    cc = V(0, .02 * s, cz + .1 * s); cr = V(.19 * W, .145, .19) * s
    breast = lambda P: sdf.ellipsoid(P, cc, cr)
    sc.shell(breast, V(-.5 * s, -.4 * s, cz - .15 * s), V(.5 * s, .2 * s, cz + .4 * s), .02 * s, 'chest', 'plate', PLATE,
             keep=lambda P: np.maximum(P[:, 1] - .035 * s, np.maximum((cz - .045 * s) - P[:, 2], P[:, 2] - (cz + .245 * s))), k=.01 * s, amp=.25)
    for z in (cz + .045 * s, cz + .135 * s):
        sc.cut_ell(V(0, -.14 * s, z), V(.2 * W, .06, .0075) * s, 'chest', 'glow', GLOW, k=.004 * s)
    # the back plate, and the belly's two lames under the breastplate
    sc.shell(breast, V(-.5 * s, -.1 * s, cz - .15 * s), V(.5 * s, .4 * s, cz + .4 * s), .018 * s, 'chest', 'plate', PLATE_L,
             keep=lambda P: np.maximum(.06 * s - P[:, 1], np.maximum((cz - .02 * s) - P[:, 2], P[:, 2] - (cz + .23 * s))), k=.01 * s, amp=.25)
    bc = V(0, .015 * s, sz + .1 * s); br = V(.145 * W, .115, .16) * s
    belly = lambda P: sdf.ellipsoid(P, bc, br)
    for i, (z0, z1) in enumerate(((sz + .03 * s, sz + .105 * s), (sz + .115 * s, sz + .2 * s))):
        sc.shell(belly, V(-.5 * s, -.4 * s, sz - .1 * s), V(.5 * s, .1 * s, sz + .4 * s), .014 * s, 'spine', 'plate', PLATE_L if i else PLATE,
                 keep=lambda P, z0=z0, z1=z1: np.maximum(P[:, 1] + .01 * s, np.maximum(z0 - P[:, 2], P[:, 2] - z1)), k=.008 * s, amp=.25)
    # a belt, and the feed port on its right front: where the gun's feed comes home
    sc.chain([V(.152 * W * math.cos(a) * s, (.012 + .113 * math.sin(a)) * s, hz + .08 * s) for a in np.linspace(0, TAU2, 17)],
             [.02 * s] * 17, 'hips', 'rag', RAG, k=.006 * s, amp=.2)
    port = V(-.14 * s, -.095 * s, hz + .06 * s)
    sc.ell(port, V(.05, .04, .055) * s, 'hips', 'plate', PLATE_L, k=.012 * s, amp=.2)
    sc.cut_ell(port + V(0, -.04, .0) * s, V(.022, .014, .03) * s, 'hips', 'glow', GLOW, k=.004 * s)
    # tassets: a plate hanging from the belt over the front and outside of each thigh
    for side, sx in (('L', 1), ('R', -1)):
        t0, t1 = J['thigh.' + side]
        th = lambda P, t0=t0, t1=t1: sdf.round_cone(P, t0 + V(0, 0, .03 * s), t1, .119 * s, .08 * s)
        sc.shell(th, np.minimum(t0, t1) - .3 * s, np.maximum(t0, t1) + .3 * s, .011 * s, 'thigh.' + side, 'plate', PLATE,
                 keep=lambda P, t0=t0, sx=sx: np.maximum(np.maximum(P[:, 1] - .03 * s, sx * (t0[0] - .07 * s * sx - P[:, 0])),
                                                       np.maximum((t0[2] - .27 * s) - P[:, 2], P[:, 2] - (t0[2] - .03 * s))), k=.008 * s, amp=.25)
    # the collar: a ring of plate round the neck, high at the back and the sides, low in front of the face
    ring = []
    for a in np.linspace(0, TAU2, 17):
        back = .5 + .5 * math.sin(a)                             # 0 in front (-Y), 1 behind
        ring.append(V(.135 * math.cos(a) * s, (.03 + .12 * math.sin(a)) * s, nz + (.005 + .115 * back) * s))
    sc.chain(ring, [.036 * s] * 17, 'chest', 'plate', PLATE_L, k=.012 * s, amp=.2)
    # ... and a second, lower ring closes it down onto the shoulders (no gap under the first)
    sc.chain([V(.15 * math.cos(a) * s, (.035 + .13 * math.sin(a)) * s, nz + (-.03 + .05 * (.5 + .5 * math.sin(a))) * s) for a in np.linspace(0, TAU2, 17)],
             [.04 * s] * 17, 'chest', 'plate', PLATE, k=.014 * s, amp=.2)
    # the head: small, sunk into the collar; a skull plate over it with one slit of light
    sc.cone(V(0, .01 * s, nz - .03 * s), V(0, -.025 * s, nz + .07 * s), .06 * s, .052 * s, 'neck', 'flesh', ASH_D, k=.035 * s, amp=1.2)
    hc = V(0, -.06 * s, h2 - .012 * s)
    sc.ell(hc, V(.066, .09, .068) * s, 'head', 'skin', HIDE, k=.028 * s)
    helm = lambda P: sdf.ellipsoid(P, hc + V(0, .012, .008) * s, V(.076, .108, .078) * s)
    sc.shell(helm, hc - .25 * s, hc + .25 * s, .011 * s, 'head', 'plate', PLATE,
             keep=lambda P: (hc[2] - .022 * s) - P[:, 2], k=.006 * s, amp=.2)
    sc.ell(hc + V(0, -.075, .03) * s, V(.07, .04, .016) * s, 'head', 'plate', PLATE_L, k=.012 * s, amp=.2)        # the brow
    sc.cut_ell(hc + V(0, -.097, .004) * s, V(.048, .03, .0075) * s, 'head', 'glow', GLOW, k=.003 * s)
    # the arms: thick, a bracer on each forearm; a great pauldron over the gun arm, a smaller one on the other
    for side, sx in (('L', 1), ('R', -1)):
        arm(sc, J, s, 1.45, side, sx, 'skin', HIDE)
        a0, a1 = J['upperarm.' + side]; f0, f1 = J['forearm.' + side]
        fb = lambda P, f0=f0, f1=f1: sdf.round_cone(P, f0, f1, .066 * s, .05 * s)
        sc.shell(fb, np.minimum(f0, f1) - .3 * s, np.maximum(f0, f1) + .3 * s, .008 * s, 'forearm.' + side, 'plate', PLATE,
                 keep=lambda P, f0=f0, f1=f1, sx=sx: np.maximum(np.maximum(P[:, 2] - (f0[2] - .045 * s), (f1[2] + .035 * s) - P[:, 2]),
                                                              sx * (f0[0] + .012 * s * sx - P[:, 0])), k=.006 * s, amp=.25)
        big = 1.0 if sx < 0 else .72
        pc = a0 + V(sx * .035, .005, -.045) * s
        pr = V(.082, .13, .185) * s * big
        tilt = sx * .62                                          # the plate leans out from the neck over the arm
        ct, st_ = math.cos(tilt), math.sin(tilt)

        def pa(P, pc=pc, pr=pr, ct=ct, st_=st_):
            q = P - pc
            x = q[:, 0] * ct - q[:, 2] * st_; z = q[:, 0] * st_ + q[:, 2] * ct
            return sdf.ellipsoid(np.stack([x, q[:, 1], z], axis=1), np.zeros(3), pr)
        sc.shell(pa, pc - .35 * s, pc + .35 * s, .016 * s, 'upperarm.' + side, 'plate', PLATE_L if sx < 0 else PLATE,
                 keep=lambda P, pc=pc, sx=sx, big=big: np.maximum((pc[2] - .07 * s * big) - P[:, 2], sx * (pc[0] - .075 * s * sx - P[:, 0])), k=.01 * s, amp=.25)
        if sx < 0:                                               # a raised rim along the gun arm's plate: it turns blows from the neck
            sc.chain([pc + V(-.02, y, .13 + .03 * math.cos(y * 14)) * s for y in np.linspace(-.1, .1, 7)], [.017 * s] * 7, 'upperarm.R', 'plate', PLATE, k=.008 * s, amp=.2)
        hands(sc, J, s, 1.35, side, sx, 4, .72, 1.25)
    sr = J['upperarm.R'][0]
    glow_vein(sc, [sr + V(-.1, -.05, .05) * s, sr + V(-.125, 0, .02) * s, sr + V(-.1, .06, .05) * s], .006 * s, 'upperarm.R')
    # the drum: bone fused with crystal, lying across the back between the shoulder blades, light at both ends and in
    # its bands; the feed leaves its right end and comes round under the arm to the port on the belt
    dz = cz + .1 * s; dy = .215 * s; dl = .165 * s; dr = .1 * s
    sc.cone(V(-dl, dy, dz), V(dl, dy, dz), dr, dr, 'chest', 'plate', PLATE_L, k=.012 * s, amp=.25)
    for sx in (1, -1):
        sc.sph(V(sx * (dl + .055 * s), dy, dz), .062 * s, 'chest', 'glow', GLOW, k=.006 * s, amp=0)
        sc.cone(V(sx * .09 * s, .1 * s, dz - .02 * s), V(sx * .1 * s, dy - .03 * s, dz), .04 * s, .045 * s, 'chest', 'bone', BONE, k=.02 * s, amp=.3)
    for x in (-.1 * s, 0.0, .1 * s):
        sc.chain([V(x, dy + (dr + .004 * s) * math.sin(a), dz + (dr + .004 * s) * math.cos(a)) for a in np.linspace(0, TAU2, 13)],
                 [.014 * s] * 13, 'chest', 'bone', BONE, k=.005 * s, amp=.15)
    for i, x in enumerate((-.1, -.02, .07)):
        shard(sc, V(x * s, dy + .05 * s, dz + .07 * s), (x * 1.5, .7, 1), (.2 - .03 * i) * s, .032 * s, 'chest')
    feed = [V(-dl - .05 * s, dy, dz), V(-.275 * s, .15 * s, cz - .02 * s), V(-.265 * s, .03 * s, sz + .09 * s),
            V(-.225 * s, -.07 * s, hz + .13 * s), port + V(-.01, -.005, .05) * s]
    sc.chain(feed, [.03 * s, .028 * s, .026 * s, .025 * s, .024 * s], ['chest', 'chest', 'spine', 'hips', 'hips'], 'bone', BONE, k=.006 * s, amp=.3)
    legs(sc, J, s, 1.5, toes=2, plate=True)       # (thicker and the thighs fuse: the hide then stretches between them in a stride)
    return sc, J, dict(hunch=9, loll=0, both=True, drag=False, twitch=.12, lean=13, height=1.3)


# ------------------------------------------------------------------ extra clips
def extra_clips(kind, st):
    """the special moves (same pose language as writhe.humanoid_clips)"""
    hunch = st.get('hunch', 18)
    clips = {}
    if kind == 'veilborn':
        def cast(p):                                          # both hands gather light, then thrust it forward
            g = smooth(p / .45) * (1 - smooth((p - .45) / .1))
            t = smooth((p - .45) / .1) * (1 - smooth((p - .7) / .3))
            d = {'upperarm.L': [(Y, -20 - 20 * g), (X, -60 * g - 85 * t)], 'forearm.L': [(X, -70 * g - 5 * t)],
                 'upperarm.R': [(Y, 20 + 20 * g), (X, -60 * g - 85 * t)], 'forearm.R': [(X, -70 * g - 5 * t)],
                 'spine': [(X, hunch * .5 - 14 * g + 10 * t)], 'chest': [(X, -10 * g + 8 * t)], 'head': [(X, -10 * g + 6 * t)]}
            return d, fk.Vector((0, .04 * g - .08 * t, .03 * g)), None
        clips['Cast'] = (1.0, False, cast)

        def blink(p):                                        # folds in on itself (it vanishes and reappears in the game)
            f = math.sin(PI * p)
            d = {'spine': [(X, 40 * f)], 'chest': [(X, 30 * f)], 'head': [(X, 30 * f)],
                 'upperarm.L': [(Y, -60 * f), (X, -40 * f)], 'upperarm.R': [(Y, 60 * f), (X, -40 * f)],
                 'forearm.L': [(X, -90 * f)], 'forearm.R': [(X, -90 * f)], 'thigh.L': [(X, -40 * f)], 'thigh.R': [(X, -40 * f)],
                 'shin.L': [(X, 70 * f)], 'shin.R': [(X, 70 * f)]}
            return d, fk.Vector((0, 0, -.35 * f * st.get('height', 1))), None
        clips['Blink'] = (.6, False, blink)
    if kind in ('bulwark', 'colossus'):
        def slam(p):                                          # both fists up, then down into the ground
            a = smooth(p / .45) * (1 - smooth((p - .45) / .12))
            s_ = smooth((p - .45) / .12) * (1 - smooth((p - .7) / .3))
            d = {'upperarm.L': [(Y, -20), (X, -165 * a - 40 * s_)], 'forearm.L': [(X, -40 * a)],
                 'upperarm.R': [(Y, 20), (X, -165 * a - 40 * s_)], 'forearm.R': [(X, -40 * a)],
                 'spine': [(X, hunch * .5 - 20 * a + 45 * s_)], 'chest': [(X, -12 * a + 20 * s_)], 'head': [(X, -20 * a + 10 * s_)],
                 'thigh.L': [(X, -20 * s_ - 8 * a)], 'shin.L': [(X, 40 * s_)], 'thigh.R': [(X, -20 * s_ - 8 * a)], 'shin.R': [(X, 40 * s_)]}
            return d, fk.Vector((0, -.05 * s_, .04 * a - .2 * s_)) * st.get('height', 1) / 1.5, None
        clips['Slam'] = (1.6 if kind == 'colossus' else 1.3, False, slam)
    if kind == 'bearer':
        def brace(p):                                         # sets itself: the feet go wide, the weight drops behind the gun
            a = smooth(p / .35)
            j = math.sin(p * 60) * smooth((p - .45) / .1) * (1 - smooth((p - .8) / .2))   # the gun's shake coming up through it
            d = {'thigh.L': [(Y, -12 * a), (X, -22 * a)], 'shin.L': [(X, 34 * a)], 'foot.L': [(X, -12 * a)],
                 'thigh.R': [(Y, 12 * a), (X, -6 * a), (Z, -8 * a)], 'shin.R': [(X, 20 * a)], 'foot.R': [(X, -12 * a)],
                 'spine': [(X, hunch * .5 + 12 * a + .8 * j)], 'chest': [(X, 8 * a + .6 * j), (Z, -8 * a)], 'head': [(X, -14 * a), (Z, 8 * a)]}
            return d, fk.Vector((0, -.03 * a, -.085 * a * st.get('height', 1))), None
        clips['Brace'] = (1.4, False, brace)
    if kind == 'colossus':
        def sweep(p):                                         # the right arm swings round in a wide arc
            a = smooth(p / .4) * (1 - smooth((p - .4) / .25))
            s_ = smooth((p - .4) / .25) * (1 - smooth((p - .75) / .25))
            d = {'upperarm.R': [(Y, 40 + 40 * a - 10 * s_), (Z, 70 * a - 90 * s_), (X, -40 * a - 60 * s_)], 'forearm.R': [(X, -20 - 20 * a)],
                 'chest': [(Z, 35 * a - 45 * s_)], 'spine': [(X, hunch * .5), (Z, 20 * a - 25 * s_)], 'head': [(Z, -20 * a + 20 * s_)],
                 'upperarm.L': [(Y, -25), (X, -20)], 'thigh.L': [(X, -10 * s_)], 'thigh.R': [(X, 10 * s_)]}
            return d, fk.Vector((0, 0, 0)), None
        clips['Sweep'] = (1.5, False, sweep)

        def barrage(p):                                       # chest thrown open, arms wide: the heart flares and fires
            a = smooth(p / .3) * (1 - smooth((p - .8) / .2))
            j = .5 + .5 * math.sin(p * 40)
            d = {'upperarm.L': [(Y, -70 * a), (X, -30 * a)], 'upperarm.R': [(Y, 70 * a), (X, -30 * a)],
                 'forearm.L': [(X, -30 * a)], 'forearm.R': [(X, -30 * a)], 'spine': [(X, hunch * .5 - 25 * a)],
                 'chest': [(X, -18 * a + 2 * j * a)], 'head': [(X, -30 * a)]}
            return d, fk.Vector((0, 0, 0)), None
        clips['Barrage'] = (2.2, False, barrage)

        def shield(p):                                        # kneels into the beam, arms crossed over the heart
            a = smooth(p / .3)
            b = .5 + .5 * math.sin(p * TAU2 * 2)
            d = {'upperarm.L': [(Y, 30 * a), (X, -70 * a)], 'upperarm.R': [(Y, -30 * a), (X, -70 * a)],
                 'forearm.L': [(X, -110 * a), (Z, 30 * a)], 'forearm.R': [(X, -110 * a), (Z, -30 * a)],
                 'spine': [(X, hunch * .5 + 20 * a + 3 * b)], 'chest': [(X, 10 * a)], 'head': [(X, 25 * a)],
                 'thigh.L': [(X, -70 * a)], 'shin.L': [(X, 100 * a)], 'thigh.R': [(X, -20 * a)], 'shin.R': [(X, 90 * a)], 'foot.R': [(X, -40 * a)]}
            return d, fk.Vector((0, 0, -.12 * a * st.get('height', 1) / 1.0)), None
        clips['Shield'] = (3.0, True, shield)
    return clips


BUILD = dict(remnant=remnant, veilborn=veilborn, bulwark=bulwark, colossus=colossus, bearer=bearer)


def build(kind):
    bl.reset()
    s = KINDS[kind]
    sc, J, st = BUILD[kind](s)
    res = .0085
    target = {'remnant': 9000, 'veilborn': 11000, 'bulwark': 14000, 'colossus': 26000, 'bearer': 18000}[kind]
    o = fk.build_mesh(sc, 'Body_' + kind, np.array([-.75, -.7, -.03]) * s, np.array([.75, .7, 2.2]) * s, res * s, target, mats(),
                      uv_scale=.45 * s, ao_dist=.06 * s, seed=sum(map(ord, kind)) % 97, bruise=('#4a3a50', .35, 4.0), veins=('#2a1a34', .4, 5.0))
    arm_ = fk.make_rig(J)
    clips = humanoid_clips(st)
    clips.update(extra_clips(kind, st))
    fk.bake_clips(arm_, clips, 'hips', 1.0)
    fk.finish(o, arm_, 'altered_%s.glb' % kind)


if __name__ == '__main__':
    only = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    for k in KINDS:
        if not only or k in only:
            build(k)
