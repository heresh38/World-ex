"""The Writhe: a parasitic infestation that wears the dead. Four creatures, sculpted with fleshkit (SDF -> skinned GLB).

  writhe_mite     Mite      a bulbous veined sac on six spindly legs with a hooked feeding mouth and feelers; swarms,
                            leaps, bursts when shot and burrows into fresh corpses (own small rig).
  writhe_host     Host      a dead trooper the parasite has reanimated: chest burst open with splayed ribs and a writhing
                            tentacle, the left forearm swallowed by a spiked growth-club with whip tendrils, deflated
                            limbs, torn armour and rags, the skull split by growth, jaw hanging (shared 20-bone rig).
  writhe_bladder  Bladder   a host whose torso has swollen into a waddling gas-bag of brood; the head is sunk into the
                            sac, withered arms dangle, tendrils drag behind (shared rig, sac bones pulse).
  writhe_amalgam  Amalgam   several hosts fused into one armour-plated mass: bone spikes, extra heads, many mouths,
                            a club arm and a talon arm (shared rig, scaled up).

Materials (names are an API, the game animates writhe_glow and wriggles `_writhe` vertices): writhe_skin, writhe_flesh,
writhe_sac, writhe_bone, writhe_plate, writhe_rag, writhe_glow.
Clips: Idle, Walk, Run, Attack, Death (+ Aim for the host, Jump for the mite).

Run: blender --background --python tools/blender/writhe.py [-- mite host bladder amalgam]
"""
import bpy, math, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import bl, sdf, characters
import fleshkit as fk
from fleshkit import X, Y, Z, S, TAU2, pulse, smooth, fbm, ridge

PI = math.pi

# palette (sRGB hex, multiplied by the light texture maps)
SKIN = '#b8b4a0'; SKIN_B = '#ac9c90'; GROWTH = '#c48a48'; GROWTH_D = '#8a5a2c'; FLESH = '#9a3030'; CAV = '#3a0c0e'
BONE = '#e2d6b8'; RAG_D = '#6a6e76'; RAG_R = '#8a3a34'; RAG_O = '#767a64'; SAC = '#ead8b4'; GLOW = '#b4f03c'


def mats():
    return dict(skin=fk.tmat('writhe_skin', 'hx_skin', nstr=1.2), flesh=fk.tmat('writhe_flesh', 'hx_flesh', nstr=1.2),
                sac=fk.tmat('writhe_sac', 'hx_sac', nstr=1.0), bone=fk.tmat('writhe_bone', 'hx_bone'),
                plate=fk.tmat('writhe_plate', 'hx_chitin', nstr=1.2), rag=fk.tmat('writhe_rag', 'hx_rag'),
                glow=fk.glow_mat('writhe_glow', GLOW, 3.5))


def human_joints(s=1.0):
    b = characters.Body('trooper')
    return {k: (np.array(a) * s, np.array(t) * s) for k, (a, t) in b.J.items()}


def spikes(sc, rnd, centre, dirs, length, r, bone, mat='bone', col=BONE, k=.012, curve=.3):
    """Bone spikes erupting from the surface around `centre` along the given directions."""
    for d in dirs:
        d = np.asarray(d, float); d /= np.linalg.norm(d)
        p = sc.surface_point(centre, d, 1.2)
        L = length * (.7 + .6 * rnd.random())
        bend = np.array([0, 0, 1.0]) * curve * L
        sc.chain([p - d * r * 1.5, p + d * L * .55 + bend * .3, p + d * L + bend], [r, r * .55, r * .08], bone, mat, col, k=k, amp=.2)


def pustules(sc, rnd, centre, dirs, rr, bone, glow_frac=.3):
    for d in dirs:
        d = np.asarray(d, float); d /= np.linalg.norm(d)
        p = sc.surface_point(centre, d, 1.2)
        r = rr[0] + (rr[1] - rr[0]) * rnd.random()
        g = rnd.random() < glow_frac
        sc.sph(p + d * r * .55, r, bone, 'glow' if g else 'sac', GLOW if g else SAC, k=r * .35, amp=.15)


def rand_dirs(rnd, n, bias, spread=1.0):
    out = []
    for _ in range(n):
        v = np.array([rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 1)]) * spread + np.asarray(bias, float)
        out.append(v / np.linalg.norm(v))
    return out


def teeth_ring(sc, c, rx, rz, n, bone, inward, length=.025, r=.006, R=None):
    """A ring of teeth around a mouth opening (in the plane facing `inward`'s opposite)."""
    c = np.asarray(c, float); fw = -np.asarray(inward, float); fw /= np.linalg.norm(fw)
    up = np.array([0, 0, 1.0]); side = np.cross(up, fw)
    if np.linalg.norm(side) < .1:
        side = np.array([1.0, 0, 0])
    side /= np.linalg.norm(side); up = np.cross(fw, side)
    for i in range(n):
        a = i / n * TAU2
        p = c + side * math.cos(a) * rx + up * math.sin(a) * rz
        tip = p - (side * math.cos(a) * rx + up * math.sin(a) * rz) * .55 - fw * length * .3
        sc.cone(p, tip, r, r * .15, bone, 'bone', BONE, k=.003, amp=.0)


# ================================================================== HOST
def host_sculpt():
    J = human_joints(1.0)
    sc = fk.Sculpt(11); rnd = sc.rnd

    def disp(P):
        return (fbm(P, 20, 3, 1) - .5) * .008 + ridge(P, 6, 2, 8) * .005
    sc.disp = disp
    # ---- torso: sunken belly, ribcage, wasted shoulders
    sc.ell((0, .0, 1.0), (.14, .095, .1), 'hips', 'skin', SKIN, k=.03)
    sc.ell((0, .015, 1.17), (.1, .072, .12), 'spine', 'skin', SKIN_B, k=.045)
    sc.ell((0, .005, 1.37), (.155, .105, .13), 'chest', 'skin', SKIN, k=.04)
    for sx in (1, -1):
        sc.cone((sx * .05, .015, 1.47), (sx * .215, .0, 1.45), .052, .045, 'chest', 'skin', SKIN, k=.035)
        sc.cone((sx * .1, .06, 1.42), (sx * .04, .07, 1.2), .03, .02, 'chest', 'skin', SKIN, k=.04)   # shoulder blades
    # ---- the burst chest: cavity, splayed ribs, parasite mass, tentacles
    sc.cut_ell((.01, -.1, 1.34), (.085, .1, .12), 'chest', 'flesh', CAV, k=.02)
    for sx in (1, -1):
        for i in range(4):
            z = 1.26 + i * .043
            fl = .012 * i
            sc.chain([(sx * .045, -.075, z), (sx * (.085 + fl), -.15, z + .015), (sx * (.1 + fl), -.21 - .01 * (i % 2), z - .025)],
                     [.011, .008, .004], 'chest', 'bone', BONE, k=.006, amp=.15)
    for c, r in [((0.0, -.06, 1.33), .062), ((.035, -.085, 1.4), .045), ((-.035, -.075, 1.29), .042), ((.0, -.09, 1.24), .035),
                 ((-.03, -.1, 1.39), .03)]:
        sc.sph(c, r, 'chest', 'flesh', GROWTH_D, k=.03, amp=2.5)
    sc.chain([(0, -.08, 1.36), (.02, -.2, 1.43), (-.06, -.32, 1.5), (-.03, -.44, 1.47), (.06, -.52, 1.38), (.1, -.54, 1.27)],
             [.044, .034, .024, .015, .008, .003], 'chest', 'flesh', GROWTH, k=.02, writhe=(.15, 1.0), amp=1.5, cols=(GROWTH_D, GROWTH))
    sc.chain([(.03, -.09, 1.3), (.07, -.2, 1.2), (.05, -.24, 1.06), (.1, -.22, .94)], [.024, .016, .009, .003], 'chest', 'flesh',
             GROWTH, k=.015, writhe=(.15, 1.0))
    sc.chain([(-.04, -.1, 1.41), (-.12, -.17, 1.5), (-.17, -.13, 1.6), (-.13, -.07, 1.67)], [.02, .014, .008, .003], 'chest', 'flesh',
             GROWTH, k=.015, writhe=(.15, .9))
    # ---- neck, lolling head with a hanging jaw, split skull
    sc.cone((0, .015, 1.47), (0, .03, 1.63), .043, .036, 'neck', 'skin', SKIN, k=.03)
    for sx in (1, -1):
        sc.cone((sx * .032, -.02, 1.5), (sx * .016, -.045, 1.62), .011, .008, 'neck', 'flesh', FLESH, k=.012)
    sc.ell((0, -.005, 1.725), (.074, .09, .1), 'head', 'skin', SKIN, k=.02)
    sc.ell((0, -.06, 1.67), (.05, .045, .055), 'head', 'skin', SKIN, k=.025)
    sc.ell((0, -.088, 1.69), (.012, .02, .025), 'head', 'skin', SKIN, k=.01)                          # nose ridge
    sc.cut_ell((0, -.1, 1.635), (.036, .045, .032), 'head', 'flesh', CAV, k=.008)                    # gaping mouth
    sc.ell((0, -.06, 1.585), (.044, .05, .017), 'head', 'skin', SKIN, k=.012, R=sdf.rot((1, 0, 0), -.5))   # dropped jaw
    teeth_ring(sc, (0, -.1, 1.635), .03, .022, 9, 'head', (0, 1, 0), .02, .005)
    for sx, deep in ((1, .02), (-1, .014)):
        sc.cut_ell((sx * .03, -.09, 1.715), (.019, .016, .014), 'head', 'flesh', CAV, k=.006)
    sc.sph((.03, -.082, 1.713), .011, 'head', 'glow', GLOW, k=.002, amp=0)                            # one milky glowing eye
    for c, r in [((-.045, .015, 1.8), .052), ((-.075, -.025, 1.765), .032), ((-.02, .06, 1.78), .035), ((-.06, -.06, 1.73), .022)]:
        sc.sph(c, r, 'head', 'sac', GROWTH, k=.025, amp=2.5)
    sc.chain([(-.04, .07, 1.76), (-.06, .12, 1.66), (-.04, .1, 1.55), (-.07, .09, 1.45)], [.018, .012, .008, .003], 'head', 'flesh',
             GROWTH, k=.012, writhe=(.2, .9))
    helmet = lambda P: sdf.ellipsoid(P, (0, .0, 1.735), (.097, .112, .114))
    sc.shell(helmet, (-.12, -.13, 1.6), (.12, .13, 1.86), .006, 'head', 'rag', RAG_D,
             keep=lambda P: np.maximum(-(P[:, 0] - .02 + (fbm(P, 18, 2, 3) - .5) * .07), 1.76 - P[:, 2] + (fbm(P, 15, 2, 4) - .5) * .05),
             k=.003, amp=0)
    # ---- left arm: forearm swallowed by a spiked growth club with whip tendrils
    a0, a1 = J['upperarm.L']; f0, f1 = J['forearm.L']; h0, h1 = J['hand.L']
    sc.cone(a0, a1, .047, .04, 'upperarm.L', 'skin', SKIN, k=.03)
    sc.sph(f0, .044, 'forearm.L', 'skin', SKIN, k=.02)
    sc.cone(f0, f0 + (f1 - f0) * .5, .04, .07, 'forearm.L', 'flesh', GROWTH_D, k=.04, amp=2)
    sc.ell(f0 + (f1 - f0) * .62 + np.array([.012, 0, 0]), (.085, .08, .15), 'forearm.L', 'flesh', GROWTH, k=.05, amp=2.5)
    sc.ell(f1 + np.array([.01, -.005, -.07]), (.1, .09, .12), 'hand.L', 'flesh', GROWTH, k=.05, amp=2.5)
    for c in rand_dirs(rnd, 7, (0, 0, 0)):
        p = f1 + np.array([.01, 0, -.02]) + c * np.array([.08, .075, .12])
        sc.sph(p, .025 + .02 * rnd.random(), 'hand.L', 'flesh', GROWTH_D, k=.03, amp=2)
    club_c = f1 + np.array([.01, 0, -.05])
    spikes(sc, rnd, club_c, [(1, -.3, .2), (.6, -.8, -.1), (.9, .4, -.3), (.2, -.9, -.6), (.7, .1, .7), (-.2, -.5, -.9), (.4, .8, .1)],
           .11, .018, 'hand.L', k=.01)
    spikes(sc, rnd, f0 + (f1 - f0) * .6, [(1, -.4, 0), (.5, .7, .3)], .08, .014, 'forearm.L', k=.008)
    for i, (ox, oy) in enumerate(((.02, -.03), (-.03, .02), (.04, .04))):
        st = f1 + np.array([ox, oy, -.17])
        sc.chain([st, st + (.03, -.05, -.12), st + (-.02, -.02, -.26), st + (.05, .03, -.36 - .05 * i)], [.016, .011, .007, .002],
                 'hand.L', 'flesh', GROWTH, k=.012, writhe=(.3, 1.0))
    # ---- right arm: wasted, clawed fingers, a torn pauldron
    a0, a1 = J['upperarm.R']; f0, f1 = J['forearm.R']; h0, h1 = J['hand.R']
    sc.cone(a0, a1, .04, .031, 'upperarm.R', 'skin', SKIN, k=.03)
    sc.sph(a1, .034, 'forearm.R', 'skin', SKIN, k=.015)
    sc.cone(f0, f1, .03, .024, 'forearm.R', 'skin', SKIN, k=.02)
    sc.ell((h0 + h1) / 2 + np.array([0, 0, .01]), (.018, .038, .045), 'hand.R', 'skin', SKIN, k=.015)
    for i in range(4):
        y = -.024 + i * .016
        b0 = np.array([h1[0], y, h1[2] + .015])
        sc.chain([b0, b0 + (.004, -.012, -.04), b0 + (.012, -.03, -.065)], [.008, .007, .004], 'hand.R', 'skin', SKIN, k=.006)
    sc.chain([np.array([h0[0], -.03, h0[2] - .03]), np.array([h0[0] + .02, -.05, h0[2] - .07])], [.009, .005], 'hand.R', 'skin', SKIN, k=.006)
    pad = lambda P: sdf.ellipsoid(P, a0 + np.array([-.01, 0, -.005]), (.072, .08, .058))
    sc.shell(pad, a0 - .12, a0 + .12, .006, 'upperarm.R', 'rag', RAG_D,
             keep=lambda P: (1.425 - P[:, 2]) + (fbm(P, 16, 2, 4) - .5) * .05, k=.003, amp=0)
    # ---- legs: wasted thighs, a boot on one foot, the other bare and clawed
    for side, sx in (('L', 1), ('R', -1)):
        t0, t1 = J['thigh.' + side]; s0, s1 = J['shin.' + side]; q0, q1 = J['foot.' + side]
        sc.cone(t0 + np.array([0, 0, .03]), t1, .07, .046, 'thigh.' + side, 'skin', SKIN, k=.035)
        sc.sph(t1 + np.array([0, -.012, 0]), .045, 'shin.' + side, 'skin', SKIN, k=.02)
        sc.cone(s0, s1, .043, .03, 'shin.' + side, 'skin', SKIN, k=.02)
        sc.cone(s0 + np.array([0, .02, -.05]), s0 + np.array([0, .03, -.25]), .035, .02, 'shin.' + side, 'skin', SKIN, k=.03)   # calf
        if side == 'L':
            q = np.array([q0[0], -.045, .055])
            sc.add(lambda P, q=q: sdf.round_box(P, q, (.046, .11, .048), .034), q - .14, q + .14, 'foot.L', 'rag', RAG_D, k=.012, amp=0)
            sc.add(lambda P, q=q: sdf.round_box(P, q - np.array([0, 0, .04]), (.05, .118, .012), .008), q - .15, q + .15, 'foot.L',
                   'rag', '#3a3a3c', k=.004, amp=0)
            sc.cone(s1 + np.array([0, .005, -.02]), s1 + np.array([0, .005, .1]), .05, .046, 'shin.L', 'rag', RAG_D, k=.01, amp=0)
        else:
            sc.cone(q0, np.array([q0[0], -.09, .028]), .033, .026, 'foot.R', 'skin', SKIN, k=.02)
            for i in range(4):
                xx = q0[0] + (i - 1.5) * .017
                sc.chain([(xx, -.09, .028), (xx - .004, -.14, .02), (xx - .006, -.17, .004)], [.011, .008, .003], 'foot.R', 'skin', SKIN, k=.006)
    # ---- rags: torn trousers, the back of the armour vest
    pel = lambda P: sdf.ellipsoid(P, (0, 0, 1.0), (.15, .104, .11))
    sc.shell(pel, (-.2, -.15, .86), (.2, .15, 1.13), .007, 'hips', 'rag', RAG_O,
             keep=lambda P: np.maximum(.9 - P[:, 2], P[:, 2] - 1.07), holes=(14, .66, 6), k=.004, amp=0)
    for side in 'LR':
        t0, t1 = J['thigh.' + side]
        thf = lambda P, t0=t0, t1=t1: sdf.round_cone(P, t0 + np.array([0, 0, .03]), t1, .078, .054)
        sc.shell(thf, np.minimum(t0, t1) - .12, np.maximum(t0, t1) + .12, .006, 'thigh.' + side, 'rag', RAG_O,
                 keep=lambda P: (.66 + (fbm(P, 9, 2, 7) - .5) * .18) - P[:, 2], holes=(13, .6, 8), k=.004, amp=0)
    vest = lambda P: sdf.ellipsoid(P, (0, .005, 1.37), (.175, .127, .15))
    sc.shell(vest, (-.22, -.15, 1.2), (.22, .16, 1.55), .009, 'chest', 'rag', RAG_D,
             keep=lambda P: np.maximum(np.maximum(np.maximum(-.01 - P[:, 1] + (fbm(P, 12, 2, 9) - .5) * .12, 1.25 - P[:, 2]), P[:, 2] - 1.46),
                                       np.abs(P[:, 0]) - .13 + (fbm(P, 10, 2, 5) - .5) * .06),
             holes=(16, .7, 10), k=.004, amp=0)
    # ---- pustules over the back and shoulders
    pustules(sc, rnd, (0, .0, 1.38), rand_dirs(rnd, 14, (0, 1.2, .5), .9), (.012, .03), 'chest')
    pustules(sc, rnd, (0, .0, 1.15), rand_dirs(rnd, 5, (0, 1.2, -.2), .8), (.012, .022), 'spine')
    return sc, J


def humanoid_clips(st):
    """Lurching, twitching motion for the reanimated (host / amalgam / bladder) and the aliens; st tunes it."""
    hunch, loll = st.get('hunch', 18), st.get('loll', 26)
    heavyL, both = st.get('clubL', True), st.get('both', False)
    drag = st.get('drag', True)
    tw = st.get('twitch', 1.0)

    def idle(p, aim=False):
        b = S(TAU2 * p)
        t1, t2, t3 = pulse(p, .18, .025) * tw, pulse(p, .52, .03) * tw, pulse(p, .8, .02) * tw
        d = {'spine': [(X, hunch * .5 + 2 * b)], 'chest': [(X, hunch * .45 + 1.5 * b), (Z, 9 * t2 * S(p * 90))],
             'neck': [(X, 8)], 'head': [(Y, loll + 4 * b), (X, 12), (Z, 30 * t1), (Y, -20 * t3)],
             'upperarm.L': [(Y, -8), (X, -6 - 22 * t2)], 'forearm.L': [(X, -10)],
             'upperarm.R': [(Y, 7), (X, -8 - 18 * t3)], 'forearm.R': [(X, -24)], 'hand.R': [(X, -12)],
             'thigh.L': [(X, -14), (Y, -4)], 'shin.L': [(X, 24)], 'foot.L': [(X, -10)],
             'thigh.R': [(X, -6), (Y, 6), (Z, -14 if drag else 0)], 'shin.R': [(X, 14)], 'foot.R': [(X, -8)]}
        if both:
            d['upperarm.R'] = [(Y, 8), (X, -6 - 22 * t3)]; d['forearm.R'] = [(X, -10)]; d['hand.R'] = []
        if aim:
            d['upperarm.R'] = [(X, -80 + 3 * b + 8 * t3), (Z, 6)]; d['forearm.R'] = [(X, -6)]; d['hand.R'] = []
            d['spine'] = [(X, hunch * .25 + 2 * b)]; d['chest'] = [(X, hunch * .2), (Z, -6)]
        scl = None
        if st.get('breathe'):
            k = 1 + st['breathe'] * b
            scl = {'spine': (k, 1, k), 'chest': (k, 1, k)}
        return d, fk.Vector((0, 0, -.03 - .006 * b)), scl

    def walk(p):
        ph = TAU2 * p
        swL = 22 * S(ph); swR = (11 if drag else 22) * S(ph + PI)
        dip = max(0.0, S(ph + PI)) ** 2 if drag else .5 * max(0.0, S(2 * ph)) ** 2
        d = {'thigh.L': [(X, -swL - 10)], 'shin.L': [(X, 10 + 42 * max(0, S(ph + 1.2)))], 'foot.L': [(X, -10)],
             'thigh.R': [(X, -swR - 6), (Z, -15 if drag else 0), (Y, 6 if drag else 0)],
             'shin.R': [(X, 12 + (12 if drag else 42) * max(0, S(ph + PI + 1.2)))], 'foot.R': [(X, -6), (Y, 10 if drag else 0)],
             'hips': [(Z, 8 * S(ph)), (Y, 6 * S(ph))],
             'spine': [(X, hunch * .6 + 6 * dip), (Y, -9 * dip)], 'chest': [(X, hunch * .4), (Z, -7 * S(ph))],
             'head': [(Y, loll + 12 * dip), (X, 12 - 10 * dip), (Z, 14 * S(ph * 2 + .5))],
             'upperarm.L': [(Y, -8), (X, -15 * S(ph - .6))], 'forearm.L': [(X, -10 - 10 * max(0, S(ph - .9)))],
             'upperarm.R': [(Y, 7), (X, 20 * S(ph - .6 + PI))], 'forearm.R': [(X, -30)]}
        if both:
            d['upperarm.R'] = [(Y, 8), (X, 15 * S(ph - .6 + PI))]; d['forearm.R'] = [(X, -10)]
        return d, fk.Vector((0, 0, -.04 - .05 * dip)), None

    def run(p):
        ph = TAU2 * p
        aL, aR = 40, 40 * (.8 if drag else 1)
        d = {'thigh.L': [(X, -aL * S(ph) - 12)], 'shin.L': [(X, 14 + 78 * max(0, S(ph + 1.2)))], 'foot.L': [(X, -10)],
             'thigh.R': [(X, -aR * S(ph + PI) - 12), (Z, -8 if drag else 0)], 'shin.R': [(X, 14 + 70 * max(0, S(ph + PI + 1.2)))],
             'foot.R': [(X, -10)], 'hips': [(Z, 10 * S(ph)), (X, 10)],
             'spine': [(X, st.get('lean', 28)), (Z, -8 * S(ph))], 'chest': [(X, 12), (Z, 10 * S(ph))],
             'head': [(X, -22), (Y, loll * .4), (Z, 16 * S(ph * 2))],
             'upperarm.L': [(Y, -28), (X, 40 * S(ph + PI))], 'forearm.L': [(X, -30)],
             'upperarm.R': [(Y, 30), (X, 55 * S(ph))], 'forearm.R': [(X, -60 - 20 * S(ph))]}
        if both:
            d['upperarm.R'] = [(Y, 28), (X, 40 * S(ph))]; d['forearm.R'] = [(X, -30)]
        return d, fk.Vector((0, 0, .045 * math.cos(2 * ph) - .09)), None

    def attack(p):
        a = smooth(p / .38) * (1 - smooth((p - .38) / .14))
        s = smooth((p - .38) / .14) * (1 - smooth((p - .62) / .38))
        d = {'upperarm.L': [(Y, -10 - 22 * a), (X, -150 * a - 62 * s)], 'forearm.L': [(X, -50 * a - 12 * s)],
             'spine': [(X, hunch * .5 - 12 * a + 34 * s), (Z, 24 * a - 20 * s)], 'chest': [(X, -8 * a + 16 * s), (Z, 14 * a - 16 * s)],
             'neck': [(X, -10 * a)], 'head': [(Y, loll * (1 - a)), (X, -28 * a + 12 * s)],
             'thigh.L': [(X, -12 - 34 * s)], 'shin.L': [(X, 18 + 38 * s)], 'thigh.R': [(X, 22 * s - 4)], 'shin.R': [(X, 12 + 22 * s)],
             'upperarm.R': [(Y, 10), (X, 30 * s - 10 * a)], 'forearm.R': [(X, -30)]}
        if both:
            d['upperarm.R'] = [(Y, 10 + 22 * a), (X, -150 * a - 62 * s)]; d['forearm.R'] = [(X, -50 * a - 12 * s)]
        return d, fk.Vector((0, -.16 * s, -.04 - .09 * s)), None

    def death(p):
        e = smooth(p * 1.4)
        d = {'hips': [(X, 75 * e)], 'spine': [(X, 20 * e)], 'chest': [(X, 15 * e)], 'head': [(Y, loll + 20 * e), (X, 30 * e)],
             'thigh.L': [(X, -60 * e)], 'shin.L': [(X, 100 * e)], 'thigh.R': [(X, -30 * e)], 'shin.R': [(X, 70 * e)],
             'upperarm.L': [(Y, -30 * e), (X, -40 * e)], 'upperarm.R': [(Y, 35 * e), (X, -20 * e)]}
        return d, fk.Vector((0, -.35 * e, -.8 * e * st.get('height', 1.0))), None

    clips = {'Idle': (2.6, True, idle), 'Walk': (1.35, True, walk), 'Run': (.78, True, run), 'Attack': (.9, False, attack),
             'Death': (1.3, False, death)}
    if st.get('aim'):
        clips['Aim'] = (2.0, True, lambda p: idle(p, True))
    if st.get('swell'):
        def swell(p):
            k = 1 + .26 * smooth(p / .9) + .03 * S(p * 70) * smooth(p / .4)
            d = {'upperarm.L': [(Y, -30 * k), (X, -40 * S(p * 40))], 'upperarm.R': [(Y, 30 * k), (X, 40 * S(p * 37))],
                 'head': [(X, -40 * smooth(p / .3)), (Z, 15 * S(p * 50))], 'spine': [(X, -6)],
                 'thigh.L': [(X, -10), (Y, -8)], 'thigh.R': [(X, -10), (Y, 8)], 'shin.L': [(X, 20)], 'shin.R': [(X, 20)]}
            return d, fk.Vector((0, 0, -.04 + .03 * S(p * 60))), {'spine': (k, k, k), 'chest': (k, k, k * .97)}
        clips['Attack'] = (1.0, False, swell)
    if st.get('breathe'):
        for k in ('Walk', 'Run', 'Death') + (() if st.get('swell') else ('Attack',)):
            dur, lp, f = clips[k]
            clips[k] = (dur, lp, (lambda f: lambda p: (f(p)[0], f(p)[1], {}))(f))
    return clips


def host():
    bl.reset()
    sc, J = host_sculpt()
    o = fk.build_mesh(sc, 'Body_host', (-.48, -.72, -.02), (.48, .38, 1.96), .0085, 9500, mats(), seed=3)
    arm = fk.make_rig(J)
    fk.bake_clips(arm, humanoid_clips(dict(hunch=18, loll=26, aim=True)), 'hips')
    fk.finish(o, arm, 'writhe_host.glb')


# ================================================================== AMALGAM
def amalgam():
    bl.reset()
    s = 1.42
    J = human_joints(s)
    # broader frame: shoulders and hips pushed out, arms longer and lower
    for side, sx in (('L', 1), ('R', -1)):
        for k in ('upperarm', 'forearm', 'hand'):
            a, t = J[k + '.' + side]
            J[k + '.' + side] = (a + np.array([sx * .14, 0, -.06]), t + np.array([sx * .16, 0, -.06]))
        for k in ('thigh', 'shin', 'foot'):
            a, t = J[k + '.' + side]
            J[k + '.' + side] = (a + np.array([sx * .07, 0, 0]), t + np.array([sx * .09, 0, 0]))
    sc = fk.Sculpt(23); rnd = sc.rnd

    def disp(P):
        return (fbm(P, 12, 3, 4) - .5) * .016 + ridge(P, 4, 5, 8) * .008
    sc.disp = disp
    hz = J['hips'][0][2]; sz = J['spine'][0][2]; cz = J['chest'][0][2]; nz = J['neck'][0][2]; h2 = J['head'][0][2]
    # ---- the fused mass: a huge hunched torso
    sc.ell((0, .02, hz + .02), (.26, .19, .17), 'hips', 'skin', SKIN, k=.06, amp=1.4)
    sc.ell((0, .04, sz + .16), (.26, .2, .22), 'spine', 'flesh', GROWTH_D, k=.08, amp=2)
    sc.ell((0, .05, cz + .12), (.42, .3, .28), 'chest', 'skin', SKIN, k=.08, amp=1.4)
    sc.ell((0, .14, cz + .26), (.34, .26, .2), 'chest', 'flesh', GROWTH_D, k=.08, amp=2)                    # hump
    for sx in (1, -1):
        sh = J['upperarm.' + ('L' if sx > 0 else 'R')][0]
        sc.ell(sh + np.array([-sx * .04, .02, .04]), (.19, .17, .16), 'chest', 'skin', SKIN, k=.07, amp=1.4)
    # second and third bodies fused in: a head and shoulder bulging from the left flank, a torso on the back
    sc.ell((.3, -.08, sz + .12), (.09, .08, .1), 'spine', 'skin', SKIN_B, k=.05)
    sc.ell((.36, -.13, sz + .22), (.065, .075, .085), 'spine', 'skin', SKIN, k=.04)                       # buried head
    sc.cut_ell((.37, -.2, sz + .2), (.025, .03, .03), 'spine', 'flesh', CAV, k=.008)
    for sx in (1, -1):
        sc.cut_ell((.36 + sx * .025, -.19, sz + .25), (.013, .012, .011), 'spine', 'flesh', CAV, k=.004)
    sc.sph((.385, -.19, sz + .25), .009, 'spine', 'glow', GLOW, k=.002, amp=0)
    sc.chain([(.33, -.1, sz + .05), (.42, -.14, sz - .1), (.44, -.18, sz - .3), (.46, -.2, sz - .42)], [.04, .03, .025, .02],
             'spine', 'skin', SKIN, k=.03, writhe=(.0, .5))                                                   # a dangling extra arm
    sc.ell((-.12, .26, cz + .05), (.13, .09, .15), 'chest', 'skin', SKIN_B, k=.06)
    sc.ell((-.14, .32, cz + .2), (.07, .08, .085), 'chest', 'skin', SKIN, k=.04)                          # face on the back
    sc.cut_ell((-.14, .39, cz + .18), (.03, .025, .035), 'chest', 'flesh', CAV, k=.008)
    # ---- many mouths: lipped holes ringed with teeth across the belly and chest
    for c, r, inw in [((0, -.27, cz + .02), (.075, .05, .05), (0, 1, 0)), ((.17, -.24, sz + .2), (.045, .04, .04), (-.3, 1, 0)),
                      ((-.2, -.22, cz + .16), (.045, .04, .045), (.4, 1, 0)), ((-.08, -.2, sz + .04), (.04, .035, .035), (0, 1, .2)),
                      ((.23, -.2, cz + .2), (.035, .035, .04), (-.5, 1, 0))]:
        c = np.array(c, float)
        sc.ell(c - np.asarray(inw) * .01, (r[0] * 1.35, .04, r[2] * 1.35), 'chest' if c[2] > cz - .02 else 'spine', 'flesh', FLESH, k=.03, amp=1.5)
        sc.cut_ell(c - np.array([0, .03, 0]), r, 'chest' if c[2] > cz - .02 else 'spine', 'flesh', CAV, k=.012)
        teeth_ring(sc, c - np.array([0, .012, 0]), r[0] * .95, r[2] * .95, 11, 'chest' if c[2] > cz - .02 else 'spine', inw, .03, .007)
    # ---- the main head, sunk low between the shoulders: split jaw, cluster of glowing eyes
    sc.cone((0, -.02, nz - .05), (0, -.08, nz + .1), .11, .09, 'neck', 'skin', SKIN, k=.06)
    sc.ell((0, -.13, h2 + .02), (.1, .11, .1), 'head', 'skin', SKIN, k=.04)
    sc.cut_ell((0, -.23, h2 - .02), (.06, .06, .05), 'head', 'flesh', CAV, k=.01)
    for sx in (1, -1):
        sc.chain([(sx * .05, -.2, h2 - .06), (sx * .09, -.26, h2 - .12), (sx * .08, -.3, h2 - .2)], [.025, .018, .006], 'head', 'bone', BONE, k=.008)
    teeth_ring(sc, (0, -.235, h2 - .02), .05, .04, 10, 'head', (0, 1, 0), .03, .007)
    for i, (ex, ez) in enumerate(((.05, .06), (-.05, .065), (.075, .02), (-.08, .03), (0, .09), (.03, .1))):
        sc.sph((ex, -.215 + abs(ex) * .5, h2 + ez), .014 + .006 * (i < 2), 'head', 'glow', GLOW, k=.004, amp=0)
    # ---- armour plates (chitin) over shoulders, back and the club arm
    for sx in (1, -1):
        sh = J['upperarm.' + ('L' if sx > 0 else 'R')][0]
        pl = lambda P, sh=sh, sx=sx: sdf.ellipsoid(P, sh + np.array([-sx * .02, .02, .1]), (.22, .2, .14))
        sc.shell(pl, sh - .3, sh + .3, .022, 'chest', 'plate', '#6e665a',
                 keep=lambda P, sh=sh: (sh[2] + .06 + (fbm(P, 7, 2, 12) - .5) * .06) - P[:, 2], k=.012, amp=.3)
    back = lambda P: sdf.ellipsoid(P, (0, .14, cz + .22), (.38, .3, .24))
    sc.shell(back, (-.45, -.2, cz - .1), (.45, .5, cz + .5), .025, 'chest', 'plate', '#5e564c',
             keep=lambda P: np.maximum(.16 - P[:, 1], .0), holes=(5, .7, 13), k=.015, amp=.3)
    # ---- bone spikes along the spine ridge and shoulders
    spikes(sc, rnd, (0, .1, cz + .2), [(0, .4, 1), (.3, .6, .8), (-.3, .6, .8), (0, .9, .5), (.5, .8, .3), (-.5, .8, .3), (.15, 1, -.1),
                                       (-.15, 1, -.1)], .3, .045, 'chest', k=.02, curve=.25)
    spikes(sc, rnd, (0, .1, sz + .1), [(0, 1, .3), (.3, 1, 0), (-.3, 1, 0)], .2, .035, 'spine', k=.02)
    for sx in (1, -1):
        sh = J['upperarm.' + ('L' if sx > 0 else 'R')][0]
        spikes(sc, rnd, sh, [(sx, 0, 1), (sx * .6, .5, 1), (sx, -.3, .6)], .24, .04, 'chest', k=.02)
    # ---- left arm: the club (fused forearms), right arm: talons
    a0, a1 = J['upperarm.L']; f0, f1 = J['forearm.L']; h0, h1 = J['hand.L']
    sc.cone(a0, a1, .12, .1, 'upperarm.L', 'skin', SKIN, k=.06, amp=1.4)
    sc.sph(f0, .1, 'forearm.L', 'skin', SKIN, k=.04)
    sc.cone(f0, f1, .1, .17, 'forearm.L', 'flesh', GROWTH_D, k=.06, amp=2)
    sc.ell(f1 + np.array([.02, 0, -.08]), (.2, .19, .22), 'hand.L', 'flesh', GROWTH, k=.08, amp=2.2)
    cl = lambda P: sdf.ellipsoid(P, f1 + np.array([.03, 0, -.06]), (.215, .205, .24))
    sc.shell(cl, f1 - .35, f1 + .35, .022, 'hand.L', 'plate', '#6e665a', holes=(6, .66, 14),
             keep=lambda P: -(P[:, 0] - f1[0] + .02), k=.012, amp=.3)
    spikes(sc, rnd, f1 + np.array([.02, 0, -.08]), rand_dirs(rnd, 9, (.6, 0, -.3), .8), .2, .035, 'hand.L', k=.015)
    a0, a1 = J['upperarm.R']; f0, f1 = J['forearm.R']; h0, h1 = J['hand.R']
    sc.cone(a0, a1, .11, .09, 'upperarm.R', 'skin', SKIN, k=.06, amp=1.4)
    sc.sph(f0, .09, 'forearm.R', 'skin', SKIN, k=.04)
    sc.cone(f0, f1, .085, .075, 'forearm.R', 'skin', SKIN_B, k=.05, amp=1.4)
    fa = lambda P: sdf.round_cone(P, f0, f1, .1, .09)
    sc.shell(fa, np.minimum(f0, f1) - .15, np.maximum(f0, f1) + .15, .016, 'forearm.R', 'plate', '#6e665a',
             keep=lambda P: P[:, 0] - f0[0] + .02, k=.01, amp=.3)
    sc.ell((h0 + h1) / 2, (.06, .09, .08), 'hand.R', 'skin', SKIN, k=.03)
    for i in range(3):
        y = -.05 + i * .05
        b0 = np.array([h1[0] - .01, y, h1[2] + .02])
        sc.chain([b0, b0 + (-.02, -.04, -.12), b0 + (-.01, -.12, -.28), b0 + (.02, -.2, -.36)], [.03, .022, .012, .002], 'hand.R', 'bone',
                 BONE, k=.012, amp=.2)
    # ---- legs: thick, plated shins, splayed clawed feet
    for side, sx in (('L', 1), ('R', -1)):
        t0, t1 = J['thigh.' + side]; s0, s1 = J['shin.' + side]; q0, q1 = J['foot.' + side]
        sc.cone(t0 + np.array([0, 0, .06]), t1, .16, .11, 'thigh.' + side, 'skin', SKIN, k=.06, amp=1.4)
        sc.sph(t1, .1, 'shin.' + side, 'skin', SKIN, k=.03)
        sc.cone(s0, s1, .1, .075, 'shin.' + side, 'skin', SKIN_B, k=.04, amp=1.4)
        sh_ = lambda P, s0=s0, s1=s1: sdf.round_cone(P, s0, s1, .118, .09)
        sc.shell(sh_, np.minimum(s0, s1) - .15, np.maximum(s0, s1) + .15, .016, 'shin.' + side, 'plate', '#6e665a',
                 keep=lambda P, s0=s0: P[:, 1] - s0[1] + .01, k=.01, amp=.3)
        sc.ell((q0[0], -.08, .07), (.1, .16, .07), 'foot.' + side, 'skin', SKIN, k=.04)
        for i in range(3):
            xx = q0[0] + (i - 1) * .06
            sc.chain([(xx, -.18, .06), (xx + (i - 1) * .02, -.28, .04), (xx + (i - 1) * .03, -.33, .005)], [.03, .02, .004], 'foot.' + side,
                     'bone', BONE, k=.01, amp=.2)
    pustules(sc, rnd, (0, .05, cz + .1), rand_dirs(rnd, 18, (0, .3, .2), 1.0), (.02, .045), 'chest', .4)
    for c in rand_dirs(rnd, 4, (0, .2, -1), .5):
        st = sc.surface_point((0, .05, sz), c, 1.0)
        sc.chain([st, st + (0, .08, -.15), st + (.04, .14, -.35), st + (-.03, .2, -.5)], [.03, .02, .012, .003], 'spine', 'flesh', GROWTH,
                 k=.015, writhe=(.3, 1))
    o = fk.build_mesh(sc, 'Body_amalgam', (-1.0, -.85, -.02), (1.0, .85, 2.95), .014, 12000, mats(), uv_scale=.6, ao_dist=.1, seed=9)
    arm = fk.make_rig(J)
    fk.bake_clips(arm, humanoid_clips(dict(hunch=26, loll=0, both=True, drag=False, twitch=.7, lean=22, height=1.4)), 'hips', 1.0)
    fk.finish(o, arm, 'writhe_amalgam.glb')


# ================================================================== BLADDER
def bladder_joints():
    J = {'hips': ((0, 0, .62), (0, 0, .74)), 'spine': ((0, 0, .74), (0, 0, 1.02)), 'chest': ((0, 0, 1.02), (0, 0, 1.36)),
         'neck': ((0, 0, 1.36), (0, -.4, 1.5)), 'head': ((0, -.4, 1.5), (0, -.47, 1.66))}
    for side, sx in (('L', 1), ('R', -1)):
        sp = (sx * .42, -.12, 1.2); el = (sx * .46, -.14, .96); wr = (sx * .47, -.16, .76)
        J['upperarm.' + side] = (sp, el); J['forearm.' + side] = (el, wr); J['hand.' + side] = (wr, (sx * .47, -.17, .68))
        hj = (sx * .2, 0, .64); kn = (sx * .27, -.05, .34); an = (sx * .27, .0, .07)
        J['thigh.' + side] = (hj, kn); J['shin.' + side] = (kn, an); J['foot.' + side] = (an, (sx * .27, -.17, .02))
    return {k: (np.array(a, float), np.array(t, float)) for k, (a, t) in J.items()}


def bladder():
    bl.reset()
    J = bladder_joints()
    sc = fk.Sculpt(31); rnd = sc.rnd

    def disp(P):
        return (fbm(P, 9, 3, 7) - .5) * .02 + ridge(P, 3.5, 8, 10) * .012
    sc.disp = disp
    # ---- the sac: lobed, veined, glossy; lower lobe on the spine, upper on the chest
    sc.ell((0, .03, .98), (.44, .4, .36), 'spine', 'sac', '#f2dcb4', k=.1, amp=1.2)
    sc.ell((0, .06, 1.24), (.4, .37, .3), 'chest', 'sac', '#f0d6b8', k=.1, amp=1.2)
    for c, r, b in [((.25, .12, 1.1), .2, 'chest'), ((-.22, .18, .9), .22, 'spine'), ((.1, .3, 1.28), .18, 'chest'),
                    ((-.18, -.2, 1.05), .17, 'spine'), ((.2, -.18, .86), .16, 'spine'), ((-.08, .25, 1.42), .14, 'chest')]:
        sc.sph(c, r, b, 'sac', '#f4dcb0' if rnd.random() < .5 else '#eab8a4', k=.08, amp=1.2)
    sc.ell((0, .0, .74), (.24, .2, .14), 'hips', 'flesh', FLESH, k=.08, amp=2)                             # raw underbelly
    # glowing brood showing through the membrane
    pustules(sc, rnd, (0, .05, 1.08), rand_dirs(rnd, 26, (0, .3, .2), 1.0), (.02, .045), 'chest', .45)
    pustules(sc, rnd, (0, .05, .9), rand_dirs(rnd, 12, (0, .2, -.3), 1.0), (.02, .04), 'spine', .4)
    # ---- the original host's head and shoulders sunk into the front of the sac
    sc.ell((0, -.33, 1.36), (.17, .1, .1), 'chest', 'skin', SKIN, k=.06)                               # shoulders
    for sx in (1, -1):
        sc.ell((sx * .07, -.4, 1.3), (.05, .03, .06), 'chest', 'skin', SKIN_B, k=.03)                  # sunken pectorals
    sc.cone((0, -.36, 1.4), (0, -.41, 1.52), .05, .043, 'neck', 'skin', SKIN, k=.035)
    sc.ell((0, -.44, 1.58), (.072, .085, .092), 'head', 'skin', SKIN, k=.03, R=sdf.rot((1, 0, 0), .35))
    sc.ell((0, -.5, 1.53), (.045, .04, .05), 'head', 'skin', SKIN, k=.025)
    sc.cut_ell((0, -.54, 1.52), (.032, .035, .045), 'head', 'flesh', CAV, k=.008)
    teeth_ring(sc, (0, -.535, 1.52), .028, .04, 8, 'head', (0, 1, 0), .02, .005)
    for sx in (1, -1):
        sc.cut_ell((sx * .03, -.51, 1.6), (.017, .015, .013), 'head', 'flesh', CAV, k=.005)
    sc.sph((-.03, -.502, 1.6), .01, 'head', 'glow', GLOW, k=.002, amp=0)
    sc.sph((.035, -.4, 1.66), .045, 'head', 'sac', GROWTH, k=.03, amp=2)
    sc.chain([(.03, -.38, 1.66), (.06, -.3, 1.6), (.04, -.2, 1.55)], [.02, .014, .006], 'head', 'flesh', GROWTH, k=.015, amp=1.5)
    # ---- withered arms dangling from the sides
    for side, sx in (('L', 1), ('R', -1)):
        a0, a1 = J['upperarm.' + side]; f0, f1 = J['forearm.' + side]; h0, h1 = J['hand.' + side]
        sc.cone(a0 - np.array([sx * .08, 0, 0]), a1, .045, .032, 'upperarm.' + side, 'skin', SKIN, k=.04)
        sc.cone(f0, f1, .03, .022, 'forearm.' + side, 'skin', SKIN, k=.015)
        sc.ell((h0 + h1) / 2, (.016, .03, .04), 'hand.' + side, 'skin', SKIN, k=.012)
        for i in range(3):
            b0 = h1 + np.array([0, -.015 + i * .015, .01])
            sc.chain([b0, b0 + (0, -.01, -.05), b0 + (0, -.03, -.08)], [.007, .005, .002], 'hand.' + side, 'skin', SKIN, k=.004)
    # ---- stubby bowed legs
    for side, sx in (('L', 1), ('R', -1)):
        t0, t1 = J['thigh.' + side]; s0, s1 = J['shin.' + side]; q0, q1 = J['foot.' + side]
        sc.cone(t0 + np.array([-sx * .05, 0, .08]), t1, .12, .075, 'thigh.' + side, 'skin', SKIN_B, k=.06, amp=1.6)
        sc.sph((t0 + t1) / 2 + np.array([sx * .07, -.05, 0]), .05, 'thigh.' + side, 'flesh', FLESH, k=.04, amp=2)
        sc.sph(t1, .07, 'shin.' + side, 'skin', SKIN, k=.03)
        sc.cone(s0, s1, .07, .05, 'shin.' + side, 'skin', SKIN, k=.03)
        sc.ell((q0[0], -.06, .05), (.07, .13, .05), 'foot.' + side, 'skin', SKIN, k=.03)
        for i in range(3):
            xx = q0[0] + (i - 1) * .035
            sc.chain([(xx, -.15, .045), (xx, -.21, .02), (xx, -.23, .003)], [.016, .011, .003], 'foot.' + side, 'bone', BONE, k=.006, amp=.2)
    # ---- tendrils dragging behind and below
    for i, c in enumerate(rand_dirs(rnd, 6, (0, .5, -1), .5)):
        st = sc.surface_point((0, .05, .9), c, 1.2)
        sc.chain([st, st + (0, .1, -.15), st + (.05 * (i % 3 - 1), .25, -.35), st + (-.04, .4, -.5 - st[2] * .2)], [.035, .025, .015, .004],
                 'spine', 'flesh', GROWTH, k=.02, writhe=(.2, 1))
    o = fk.build_mesh(sc, 'Body_bladder', (-.75, -.7, -.02), (.75, .95, 1.8), .011, 8000, mats(), uv_scale=.5, ao_dist=.09, seed=13,
                      bruise=('#c06a70', .5, 3.0), mottle=.3)
    arm = fk.make_rig(J)
    fk.bake_clips(arm, humanoid_clips(dict(hunch=4, loll=10, drag=False, both=True, twitch=.6, lean=8, breathe=.05, height=.7, swell=True)), 'hips')
    fk.finish(o, arm, 'writhe_bladder.glb')


# ================================================================== MITE (own rig)
NLEG = 6
LEG_ANG = [math.radians(a) for a in (-50, -90, -130, 50, 90, 130)]   # around the body, 0 = +X; front is -Y


def mite_joints():
    J = {'body': ((0, 0, .1), (0, 0, .3)), 'sac': ((0, .02, .3), (0, .02, .5))}
    P = {'body': 'root', 'sac': 'body'}
    for i, a in enumerate(LEG_ANG):
        d = np.array([math.cos(a), math.sin(a) * .9, 0])
        hip = np.array([0, 0, .2]) + d * .13
        knee = hip + d * .17 + np.array([0, 0, .2])
        foot = hip + d * .36 + np.array([0, 0, -.2])
        J['leg%d.a' % i] = (hip, knee); J['leg%d.b' % i] = (knee, foot)
        P['leg%d.a' % i] = 'body'; P['leg%d.b' % i] = 'leg%d.a' % i
    for i, sx in enumerate((1, -1)):
        J['feel%d' % i] = ((sx * .05, -.2, .2), (sx * .1, -.38, .16)); P['feel%d' % i] = 'body'
    J = {k: (np.array(a, float), np.array(t, float)) for k, (a, t) in J.items()}
    order = ['body', 'sac'] + ['leg%d.%s' % (i, s) for i in range(NLEG) for s in 'ab'] + ['feel0', 'feel1']
    return J, P, order


def mite():
    bl.reset()
    J, PAR, ORDER = mite_joints()
    sc = fk.Sculpt(41); rnd = sc.rnd

    def disp(P):
        return (fbm(P, 30, 2, 2) - .5) * .006 + ridge(P, 11, 3, 10) * .006
    sc.disp = disp
    # bulbous sac: main bulb + lobes, veined membrane
    sc.ell((0, .03, .3), (.17, .21, .15), 'sac', 'sac', SAC, k=.05, amp=1.2)
    for c, r in [((.1, .1, .36), .1), ((-.09, .12, .34), .11), ((.0, .16, .26), .09), ((.06, -.06, .38), .07), ((-.07, -.02, .4), .07)]:
        sc.sph(c, r, 'sac', 'sac', '#e2cc94' if rnd.random() < .5 else '#cfae7a', k=.05, amp=1.2)
    pustules(sc, rnd, (0, .04, .32), rand_dirs(rnd, 9, (0, .2, .5), 1.0), (.012, .028), 'sac', .5)
    # fleshy underside / head where the legs root
    sc.ell((0, -.06, .22), (.13, .15, .08), 'body', 'flesh', FLESH, k=.05, amp=2)
    sc.ell((0, -.17, .24), (.075, .07, .065), 'body', 'flesh', FLESH, k=.04, amp=2)
    sc.cut_ell((0, -.235, .24), (.035, .04, .03), 'body', 'flesh', CAV, k=.008)                          # feeding mouth
    teeth_ring(sc, (0, -.232, .24), .034, .026, 9, 'body', (0, 1, 0), .02, .005)
    for i, sx in enumerate((1, -1)):
        a, t = J['feel%d' % i]
        sc.chain([a, (a + t) / 2 + np.array([sx * .03, 0, .04]), t, t + np.array([-sx * .02, -.06, -.06])], [.012, .008, .005, .001],
                 'feel%d' % i, 'flesh', GROWTH, k=.008, writhe=(.2, 1))
    sc.chain([(0, -.2, .2), (.01, -.3, .14), (-.02, -.36, .08), (.0, -.4, .03)], [.012, .008, .005, .001], 'body', 'flesh', GROWTH,
             k=.008, writhe=(.3, 1))
    # legs: spindly, knobbed knees, hooked bone tips
    for i in range(NLEG):
        a, k_ = J['leg%d.a' % i]; _, f = J['leg%d.b' % i]
        sc.cone(a, k_, .02, .013, 'leg%d.a' % i, 'flesh', FLESH, k=.012, amp=.6)
        sc.sph(k_, .016, 'leg%d.b' % i, 'flesh', GROWTH_D, k=.008, amp=.5)
        mid = k_ + (f - k_) * .7
        sc.cone(k_, mid, .012, .008, 'leg%d.b' % i, 'flesh', FLESH, k=.006, amp=.4)
        sc.cone(mid, f, .008, .002, 'leg%d.b' % i, 'bone', BONE, k=.004, amp=0)
    o = fk.build_mesh(sc, 'Body_mite', (-.5, -.5, -.03), (.5, .48, .58), .0055, 2600, mats(), uv_scale=.3, ao_dist=.04, mottle=.2, seed=17,
                      bruise=('#c06a70', .45, 5.0))
    arm = fk.make_rig(J, PAR, ORDER)
    legdir = [np.array([math.cos(a), math.sin(a) * .9, 0]) for a in LEG_ANG]
    lift_ax = [tuple(np.cross(d, (0, 0, 1)) / np.linalg.norm(np.cross(d, (0, 0, 1)))) for d in legdir]
    groupA = {0, 2, 4}

    def legs_pose(d, i, swing, lift, knee):
        d['leg%d.a' % i] = [(Z, swing), (lift_ax[i], lift)]
        d['leg%d.b' % i] = [(lift_ax[i], knee)]

    def idle(p):
        b = S(TAU2 * p)
        d = {'feel0': [(X, 15 * S(TAU2 * p * 2)), (Z, 10 * b)], 'feel1': [(X, 15 * S(TAU2 * p * 2 + 1)), (Z, -10 * b)]}
        for i in range(NLEG):
            legs_pose(d, i, 3 * S(TAU2 * p + i), 4 * pulse(p, i / NLEG, .05), 0)
        k = 1 + .06 * b
        return d, fk.Vector((0, 0, -.01 * b)), {'sac': (k, k, 1 + .1 * b)}

    def run(p):
        d = {'feel0': [(X, -25), (Z, 12 * S(TAU2 * p * 2))], 'feel1': [(X, -25), (Z, -12 * S(TAU2 * p * 2))], 'body': [(Z, 6 * S(TAU2 * p))]}
        for i in range(NLEG):
            ph = TAU2 * p + (0 if i in groupA else PI)
            fwd = 1 if legdir[i][0] > 0 else -1
            legs_pose(d, i, 28 * S(ph) * fwd, 22 * max(0, math.cos(ph)), -12 * max(0, math.cos(ph)))
        k = 1 + .05 * S(TAU2 * p * 2)
        return d, fk.Vector((0, 0, .02 * abs(math.cos(TAU2 * p)))), {'sac': (k, k, 2 - k)}

    def jump(p):
        e = smooth(p / .25); f_ = smooth((p - .25) / .3)
        d = {'body': [(X, -25 * f_ + 10 * e * (1 - f_))], 'feel0': [(X, -40 * f_)], 'feel1': [(X, -40 * f_)]}
        for i in range(NLEG):
            front = legdir[i][1] < -.3
            legs_pose(d, i, 0, -20 * e * (1 - f_) + (40 if front else -30) * f_, 30 * f_)
        return d, fk.Vector((0, 0, -.06 * e * (1 - f_))), {'sac': (1 + .1 * f_, 1 + .1 * f_, 1 - .08 * f_)}

    def death(p):
        e = smooth(p * 1.5)
        d = {'body': [(Y, 40 * e)]}
        for i in range(NLEG):
            legs_pose(d, i, 0, 50 * e, 70 * e)
        return d, fk.Vector((0, 0, -.12 * e)), {'sac': (1 - .3 * e, 1 - .3 * e, 1 - .45 * e)}

    fk.bake_clips(arm, {'Idle': (1.4, True, idle), 'Run': (.32, True, run), 'Walk': (.5, True, run), 'Jump': (.6, False, jump),
                        'Attack': (.6, False, jump), 'Death': (.7, False, death)}, 'body')
    fk.finish(o, arm, 'writhe_mite.glb')


KINDS = {'mite': mite, 'host': host, 'bladder': bladder, 'amalgam': amalgam}

if __name__ == '__main__':
    only = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    for k, fn in KINDS.items():
        if not only or k in only:
            fn()
