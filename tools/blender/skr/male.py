"""The male Sarketh's armour (metal plates he wears, by slot) and his claws, after the owner's sheet
(art/reference/sarketh/sarketh_design_sheet.png; on 2026-11-21 the owner: "make it exactly like the image"): a helmet of
dark lacquer with eyes of light and a crest of swept blades (head_parts); few, large, pointed plates that follow the
body's forms, the dark scaled body bare between them; big layered pauldrons; long plates down the outside of every limb,
spikes off the elbows, calves and hocks; small amber lights at the hips, the knees and the hocks.
Points are for the LEFT side (+X) and mirrored."""
import numpy as np

import anatomy

FINGERS = ('index', 'middle', 'ring', 'pinky')


def layout(A, J):
    # (the plates as numerous as the sheet's mosaic, the owner, 2026-11-22: "plates more numerous": a plate more round each
    # limb and a row more along it)
    """the whole set: the helmet and the neck (head_parts), then the body's armour slot by slot. The sheet's armour is a
    dense mosaic of POINTED shards, pale and dark, in rows down every limb (their points down the leg, toward the elbow
    on the forearm, lifting off at their ends), with big pieces over it: the chest's V, the layered pauldrons, the spine,
    the knees, the hips' plates, spikes off the elbows, calves, hocks and heels; the dark body bare on the belly and
    between the plates."""
    A.thick_k, A.tip_k, A.point_k = 1.5, 1.0, .85      # thick plates, their ends pointed and lifting (the sheet)
    A.angular, A.notch = .65, .15                      # straight-sided shards, a few with a second point
    j = lambda b, e=0: np.asarray(J[b][e], float)
    head_parts(A, J)

    A.slot = 'chest'
    # the chest: a broad plate over each side from the shoulder's front down to the foot of the breastbone, the two
    # meeting there in a V; a dark band along each collarbone; shards on the ribs' sides under the arm and at the waist
    ch = ('chest',)
    A.blade('pec', (.212, -.046, 1.712), (.028, -.124, 1.596), .100, 'chest', lift=.012, ridge=.009, thick=.010, peak=.38, base=.62,
            point=.9, only=ch)
    A.blade('pec_m', (.200, -.066, 1.652), (.036, -.126, 1.540), .088, 'chest', lift=.008, ridge=.008, thick=.009, peak=.38, base=.62,
            point=.9, mat='dark', only=ch)
    A.blade('pec_l', (.178, -.084, 1.592), (.050, -.120, 1.488), .074, 'chest', lift=.004, ridge=.007, thick=.009, peak=.38, base=.62,
            point=.9, only=ch)
    A.blade('collar', (.040, -.092, 1.740), (.205, -.028, 1.738), .040, 'chest', lift=.014, ridge=.005, thick=.007, peak=.4, mat='dark',
            only=ch)
    # a collar of shards rising round the back of the neck from the trapezius (the sheet: up to the jaw)
    for name, pts, w, mat in (('collar0', [(.050, -.010, 1.722), (.056, .000, 1.800), (.060, .014, 1.880)], .056, 'dark'),
                              ('collar1', [(.080, .018, 1.715), (.090, .030, 1.800), (.096, .046, 1.885)], .074, 'armour'),
                              ('collar2', [(.112, .030, 1.712), (.130, .042, 1.785), (.144, .058, 1.850)], .066, 'dark'),
                              ('collar3', [(.148, .036, 1.708), (.176, .048, 1.762), (.196, .064, 1.808)], .060, 'armour'),
                              ('collar4', [(.060, .062, 1.722), (.068, .078, 1.800), (.074, .096, 1.870)], .064, 'armour')):
        A.shard(name, pts, w, (1, -.35, 0), 'chest', thick=.011, base=.72, peak=.32, point=.95, lower=.6, notch=(.55, .28), mat=mat,
                edge=.22)
    A.blade('pec2', (.150, -.090, 1.560), (.070, -.112, 1.470), .056, 'chest', lift=.002, ridge=.006, thick=.008, peak=.38, base=.6,
            point=.9, mat='dark', only=ch)
    A.wrap('ribs', (.150, -.030, 1.600), (.150, .000, 1.360), 'chest', around=3, rows=3, span=(-75, 35), face=(1, -.4, 0), cover=1.05,
           tip=.008, dark=((1, 0), (2, 1)), accents=0, base=.35, peak=.32)
    A.wrap('flank', (.112, -.010, 1.400), (.110, .000, 1.250), 'spine', around=2, rows=2, span=(-80, 25), face=(1, -.4, 0), cover=1.05,
           tip=.008, dark=((0, 1),), accents=0, base=.35, peak=.32)
    A.stud('heart', (0, -.128, 1.600), .0050, 'chest', mirror=False, lift=.002)

    A.slot = 'shoulders'
    # the pauldron: big and rounded, three layers stepping out down the arm, its top edge rising to a point behind (the
    # sheet; the owner, 2026-11-15: rounded and layered)
    sh = j('upperarm.L')
    A.blade('pauldron', sh + (-.085, -.010, .105), sh + (.120, .010, -.125), .235, 'upperarm.L', lift=.012, ridge=.011, thick=.013,
            peak=.45, base=.78, point=.7, tip=.014, bend=(.034, 0, .014), angular=.15)
    A.blade('pauldron2', sh + (-.010, .005, .060), sh + (.140, .022, -.180), .190, 'upperarm.L', lift=.028, ridge=.009, thick=.012,
            peak=.45, base=.75, point=.7, tip=.018, mat='dark', angular=.15)
    A.blade('pauldron3', sh + (.045, .012, .005), sh + (.155, .030, -.230), .150, 'upperarm.L', lift=.044, ridge=.008, thick=.011,
            peak=.45, base=.75, point=.75, tip=.022, angular=.15)
    A.shard('pauldron_rise', [sh + (-.040, .040, .070), sh + (-.020, .060, .140), sh + (-.008, .085, .200)], .080, (1, -.6, .2),
            'upperarm.L', thick=.011, base=.75, peak=.35, point=.9, lower=.65, notch=(.5, .3), edge=.22)

    A.slot = 'back'
    # the back (the sheet's back view): a long plate down the spine from the nape with lights along it, a plate over each
    # shoulder blade, the lats bare; from the top of the back either side of the neck a tall spike rising
    A.blade('spine', (0, .104, 1.740), (0, .150, 1.430), .118, 'chest', lift=.006, ridge=.012, thick=.011, peak=.12, base=.85, point=1.2,
            mirror=False)
    A.blade('spine2', (0, .148, 1.460), (0, .118, 1.230), .056, 'spine', lift=.006, ridge=.008, thick=.009, peak=.25, base=.8, point=1.1,
            mirror=False, mat='dark')
    for k, z in enumerate((1.690, 1.630, 1.570, 1.510)):
        A.stud(f'spinelight{k}', (0, .140, z), .0042, 'chest', mirror=False, lift=.024)
    A.blade('scapula', (.070, .118, 1.690), (.170, .105, 1.520), .090, 'chest', lift=.004, ridge=.007, thick=.009, peak=.35, tip=.010,
            free=.85, mat='dark')
    A.blade('trap', (.050, .060, 1.740), (.150, .040, 1.700), .060, 'chest', lift=.006, tip=.020, free=.70, ridge=.007, thick=.010,
            peak=.35, base=.6)
    A.blade('trap2', (.080, .085, 1.715), (.180, .070, 1.660), .056, 'chest', lift=.010, tip=.022, free=.70, ridge=.006, thick=.009,
            peak=.35, base=.6, mat='dark')
    A.wrap('back', (.100, .040, 1.660), (.100, .045, 1.400), 'chest', around=3, rows=3, span=(-10, 85), face=(0, 1, 0), cover=1.0,
           tip=.010, dark=((0, 1), (2, 0)), lift=.0045)
    A.wrap('lowback', (.060, .060, 1.400), (.065, .060, 1.250), 'spine', around=2, rows=2, span=(5, 75), face=(0, 1, 0), cover=.95, tip=.008,
           dark=((0, 1),))
    A.shard('wing', [(.070, .070, 1.680), (.092, .088, 1.790), (.108, .104, 1.900), (.114, .112, 1.950)], .140, (1, .45, .1), 'chest',
            thick=.013, base=.75, peak=.38, point=.9, lower=.55, notch=(.45, .35), edge=.22)
    A.shard('wing2', [(.110, .060, 1.700), (.140, .078, 1.780), (.165, .095, 1.850)], .090, (1, .3, .2), 'chest', thick=.011, base=.7,
            peak=.32, point=.95, lower=.6, notch=(.55, .3), edge=.22, mat='dark')

    A.slot = 'arms'
    # the arms: plates down the outside of the upper arm under the pauldron, a spike off the elbow; the forearm's long
    # plates on its outside and back, overlapping, their points toward the elbow and lifting off it (the sheet)
    el, wr = j('forearm.L'), j('hand.L')
    ua, fa = ('upperarm.L',), ('forearm.L',)
    A.wrap('uarm', sh + (el - sh) * .26, el + (el - sh) * .05, 'upperarm.L', around=5, rows=3, span=(-190, 15), face=(0, -1, 0), cover=1.25,
           overlap=.45, tip=.006, dark_share=.3, accents=.6, base=.32, peak=.30)
    A.shard('elbow', [el + (.016, .040, .010), el + (.030, .070, .060), el + (.042, .095, .125)], .048, (1, -.2, 0), 'forearm.L',
            thick=.010, base=.7, peak=.3, point=.95, lower=.6, edge=.22)
    A.wrap('farm', el + (wr - el) * .06, wr + (wr - el) * .02, 'forearm.L', around=5, rows=3, span=(-210, 10), face=(0, -1, 0), cover=1.25,
           overlap=.45, tip=.007, dark_share=.3, accents=.6, base=.32, peak=.30, flip=True)

    A.slot = 'hands'
    # the hands: a plate over the back of the hand, plates over the first two joints of every finger, the last dark; long
    # curved claws (the creature's own)
    hn = j('hand.L', 1)
    A.blade('handback', wr + (.014, .002, -.010), hn + (.016, -.004, -.010), .058, 'hand.L', lift=.003, ridge=.006, peak=.4, thick=.007,
            base=.7, point=1.1)
    for f in FINGERS:
        for k in (1, 2, 3):
            a, b = j(f'{f}{k}.L'), j(f'{f}{k}.L', 1)
            A.blade(f'{f}{k}', a + (.008, 0, .003), b + (.008, 0, .000), (.019, .016, .013)[k - 1], f'{f}{k}.L', lift=.0018, ridge=.002,
                    thick=.004, peak=.5, base=.8, n=(8, 5), mat='dark' if k == 3 else 'armour')
        a, b = j(f'{f}3.L'), j(f'{f}3.L', 1)
        d = (b - a) / np.linalg.norm(b - a)
        A.slot = 'body'
        A.claw(f'{f}claw', b - d * .014, b + d * .050 + np.array([-.013, 0, -.004]), .0075, f'{f}3.L', up=(-1, 0, 0), hook=.5)
        A.slot = 'hands'
    a, b = j('thumb3.L'), j('thumb3.L', 1)
    d = (b - a) / np.linalg.norm(b - a)
    A.slot = 'body'
    A.claw('thumbclaw', b - d * .012, b + d * .040 + np.array([-.006, 0, 0]), .0075, 'thumb3.L', up=(-1, 0, 0), hook=.45)

    A.slot = 'belt'
    # the hips: a long plate hanging over each hip's side, its foot pointed and lifting, a dark one behind it; a dark V
    # over the groin; a light at each hip
    A.wrap('girdle', (0, .010, 1.270), (0, .010, 1.090), 'hips', around=7, rows=1, span=(-35, 200), face=(0, -1, 0), cover=.86, overlap=.2,
           tip=.010, dark=((0, 1), (0, 4)), reach=.40, mirror=False)
    A.wrap('girdle_r', (0, .010, 1.270), (0, .010, 1.090), 'hips', around=3, rows=1, span=(-200, -45), face=(0, -1, 0), cover=.86,
           overlap=.2, tip=.010, reach=.40, mirror=False)
    A.blade('tasset', (.128, -.040, 1.275), (.168, -.030, 1.070), .100, 'hips', lift=.016, tip=.018, free=.75, ridge=.008, thick=.010,
            peak=.35, base=.65)
    A.blade('tasset_b', (.130, .030, 1.265), (.160, .045, 1.080), .080, 'hips', lift=.012, tip=.014, free=.75, ridge=.006, peak=.35,
            mat='dark')
    A.blade('hipcrest', (.085, -.085, 1.265), (.125, -.065, 1.185), .050, 'hips', lift=.006, ridge=.005, peak=.4)
    A.blade('groin', (0, -.098, 1.190), (0, -.072, 1.035), .074, 'hips', lift=.005, ridge=.007, peak=.25, base=.8, point=1.1,
            mirror=False, mat='dark')
    A.stud('hiplight', (.150, -.060, 1.230), .0042, 'hips', mat='amber', lift=.034)

    A.slot = 'legs'
    # the legs: a long plate down the front of the thigh, a dark one outside it, a narrow one inside; a cupped plate on
    # the knee with a light; plates down the front of the shin; a spike off the calf and one off the hock (the sheet)
    hj, kn, hk, ba = j('thigh.L'), j('shin.L'), j('foot.L'), j('toes.L')
    th_, sn = ('thigh.L',), ('shin.L',)
    A.wrap('thigh', hj + (kn - hj) * .12, kn + (kn - hj) * .02, 'thigh.L', around=6, rows=4, span=(-170, 35), face=(0, -1, 0), cover=1.25,
           overlap=.45, tip=.006, ridge=.006, thick=.008, dark_share=.3, accents=.6, base=.32, peak=.30)
    A.blade('knee', kn + (.004, -.052, .100), kn + (.004, -.064, -.075), .094, 'shin.L', lift=.012, ridge=.010, thick=.012, peak=.40,
            base=.70, point=.8)
    A.stud('kneelight', kn + (.044, -.058, .010), .0045, 'shin.L', mat='amber', lift=.026)
    A.wrap('shin', kn + (hk - kn) * .16, hk + (hk - kn) * .02, 'shin.L', around=5, rows=4, span=(-160, 35), face=(0, -1, -.4), cover=1.25,
           overlap=.45, tip=.006, thick=.007, dark_share=.3, accents=.6, base=.32, peak=.30)
    A.shard('calf', [kn + (.010, .050, -.140), kn + (.016, .100, -.100), kn + (.020, .160, -.040)], .050, (1, 0, 0), 'shin.L',
            thick=.010, base=.7, peak=.3, point=.95, lower=.6, edge=.22)
    A.shard('hockspike', [hk + (.008, .020, .030), hk + (.012, .075, .060), hk + (.016, .125, .110)], .044, (1, 0, 0), 'foot.L',
            thick=.009, base=.7, peak=.3, point=.95, lower=.6, edge=.22)
    A.stud('hocklight', hk + (.034, -.004, .000), .0042, 'foot.L', mat='amber', lift=.004)

    A.slot = 'feet'
    # the long foot: plates down its front, a spike off its back; a plate over each toe, big claws
    ft = ('foot.L',)
    A.wrap('foot', hk + (ba - hk) * .10, ba + (ba - hk) * .10, 'foot.L', around=4, rows=2, span=(-140, 60), face=(0, -1, .3), cover=1.25,
           overlap=.45, tip=.006, thick=.007, dark_share=.25, accents=.5, base=.32, peak=.30)
    A.shard('heel', [ba + (.000, .045, .110), ba + (.004, .085, .150), ba + (.006, .120, .205)], .040, (1, 0, 0), 'foot.L', thick=.008,
            base=.7, peak=.3, point=.95, lower=.6, edge=.22)
    for dx, ln in ((-.026, .088), (0.0, .102), (.026, .086)):
        tip_ = ba + (dx * 1.6, -.030 - ln, -.034)
        root = ba + (dx, -.030, -.010)
        A.slot = 'feet'
        A.blade(f'toe{dx:+.3f}', root + (0, -.010, .018), tip_ + (0, .022, .018), .028, 'toes.L', lift=.002, ridge=.004, thick=.006, n=(10, 5))
        A.slot = 'body'
        A.claw(f'toeclaw{dx:+.3f}', tip_ + (0, .018, .006), tip_ + (dx * .4, -.068, -.032), .0150, 'toes.L', up=(0, 0, 1), hook=.55)
    A.slot = 'body'
    A.claw('dewclaw', ba + (-.040, .040, -.030), ba + (-.054, .086, -.050), .010, 'toes.L', up=(0, 0, 1), hook=.4)
    if getattr(A, 'rank', None) == 'heavy':
        heavy_parts(A, J)


def heavy_parts(A, J):
    """The heavy ranks (the Warden, the Bearer, the commander: the story's officers and heavy weapons in powered armour,
    a soldier inside; until the owner designs their suits): his set made heavier. A tall shield on the outside of the
    left forearm, lying close along it; a power unit on the back between the shoulder blades with two fins rising
    from it; a fourth, outer pauldron layer with a point; a plate down the breastbone."""
    j = lambda b, e=0: np.asarray(J[b][e], float)
    sh, el, wr = j('upperarm.L'), j('forearm.L'), j('hand.L')
    A.slot = 'shield'
    A.shard('shield', [el + (.060, .010, .120), (el + wr) * .5 + (.074, -.004, 0), wr + (.066, -.016, -.120)], .260, (1, -.30, 0),
            'forearm.L', thick=.016, base=.80, peak=.30, point=1.0, lower=.92, mat='armour', mirror=False, n=(30, 11), edge=.30)
    A.shard('shield_rim', [el + (.054, .014, .100), (el + wr) * .5 + (.066, -.002, 0), wr + (.058, -.014, -.100)], .300, (1, -.30, 0),
            'forearm.L', thick=.010, base=.80, peak=.30, point=1.0, lower=.92, mat='dark', mirror=False, n=(30, 11), edge=.30)
    A.stud('shieldlight', (el + wr) * .5 + (.090, -.010, .020), .0060, 'forearm.L', mirror=False, mat='amber', lift=.040)
    A.slot = 'back'
    A.blade('pack', (0, .150, 1.650), (0, .168, 1.400), .200, 'chest', lift=.030, ridge=.016, thick=.030, peak=.30, base=.85, point=.8,
            mirror=False, mat='dark', angular=.3)
    A.blade('pack_top', (0, .168, 1.660), (0, .190, 1.500), .150, 'chest', lift=.064, ridge=.012, thick=.016, peak=.30, base=.85, point=.9,
            mirror=False, angular=.3)
    A.shard('pack_fin', [(.050, .190, 1.560), (.070, .230, 1.660), (.082, .260, 1.760)], .070, (1, .2, 0), 'chest', thick=.012, base=.72,
            peak=.3, point=.95, lower=.6, edge=.22)
    A.slot = 'shoulders'
    A.blade('pauldron4', sh + (.060, .018, -.020), sh + (.170, .036, -.250), .170, 'upperarm.L', lift=.060, ridge=.009, thick=.012,
            peak=.45, base=.75, point=.75, tip=.024, mat='dark', angular=.15)
    A.shard('pauldron_hpt', [sh + (.040, .010, .040), sh + (.090, .020, .110), sh + (.130, .030, .170)], .070, (0, -1, .3), 'upperarm.L',
            thick=.011, base=.72, peak=.32, point=.95, lower=.6, edge=.22)
    A.slot = 'chest'
    A.blade('breast', (0, -.120, 1.700), (0, -.130, 1.500), .110, 'chest', lift=.016, ridge=.012, thick=.012, peak=.25, base=.85, point=1.0,
            mirror=False, angular=.4)


def head_parts(A, J):
    """The helmet (the sheet's "head detail"): a dark lacquered mask over the whole head, an eye of light either side,
    framed by pale plates (the face's front edge down to the chin, over each eye, along each cheek, under the jaw) with
    dark plates layered round the eyes, and a crest of free blades swept BACK off the brow and the crown, stacked and
    nearly parallel, pale and dark by turns, two dark horns rising at the top; plates down the back of the neck."""
    j = lambda b, e=0: np.asarray(J[b][e], float)
    hd, nk = j('head'), j('neck')
    S = anatomy.HEAD
    HF, lo, hi = anatomy.head_field(hd, S)
    off, th = .0035 * S, .0045 * S
    outer = lambda P: HF(P) - (off + th)                       # the mask's outer face: what the plates lie on

    def p(x, y, z):
        return hd + np.array([x, y, z], float) * S

    A.slot = 'helmet'
    # the eyes: almonds of light rising from behind the face's front edge back toward the temple (from the front they
    # slant up outward), inlaid in the mask (a slit through the shell closes when the helmet is reduced for the game)
    eyes = []
    for sg in (1, -1):
        e0, e1 = A.project([p(.034 * sg, -.092, .052), p(.047 * sg, -.050, .084)], fn=outer)
        eyes.append((e0, e1, sg))
    th0, nrm = p(0, -.040, -.022).astype(np.float32), np.array([0, .514, -.857], np.float32)
    keep = lambda P: (np.asarray(P, np.float32) - th0) @ nrm   # open under the jaw and at the nape
    A.shell('helmet', 'head', HF, lo - .01, hi + .01, off, th, keep, lambda c: 'dark', (), (), h=.0009, target=16000)
    A.slot = 'body'
    for e0, e1, sg in eyes:
        m_ = A.project([(e0 + e1) * .5 + np.array([0, 0, .002 * S])], fn=outer)[0]
        nn = A.normal([m_], fn=outer)[0]
        A.shard('eye' if sg > 0 else 'eye_R', [e0 + nn * .0003, m_ + nn * .0003, e1 + nn * .0003], .0105 * S, nn, 'head', thick=.0012,
                base=.10, peak=.42, point=1.0, lower=1.0, mat='glow', mirror=False, n=(14, 5), edge=.3)
    A.slot = 'helmet'
    # the frame: pale at the face's front edge, over the eye and along the cheek; the face's middle and the band round the
    # eye dark lacquer in layers (a pale stripe down the middle of the face read as a beak)
    A.blade('face', p(0, -.058, .140), p(0, -.126, -.043), .040 * S, 'head', lift=.0012, ridge=.006, thick=.007, peak=.20, base=.80,
            point=.85, mirror=False, mat='dark', field=outer)
    A.blade('faceedge', p(.026, -.050, .128), p(.014, -.118, -.032), .024 * S, 'head', lift=.0024, ridge=.004, thick=.007, peak=.30,
            base=.7, point=.9, field=outer)
    A.blade('brow', p(.018, -.050, .144), p(.062, .020, .116), .038 * S, 'head', lift=.0016, tip=.008, free=.82, ridge=.006, thick=.007,
            peak=.32, base=.75, field=outer)
    A.blade('temple', p(.050, -.040, .070), p(.064, .040, .090), .030 * S, 'head', lift=.0014, tip=.006, free=.85, ridge=.005, thick=.006,
            peak=.35, base=.7, mat='dark', field=outer)
    A.blade('cheek', p(.022, -.114, .002), p(.058, -.018, .040), .036 * S, 'head', lift=.0014, ridge=.006, thick=.007, peak=.45, base=.6,
            field=outer)
    A.blade('jaw', p(.010, -.106, -.040), p(.030, -.022, -.010), .024 * S, 'head', lift=.0014, ridge=.004, thick=.006, peak=.5, base=.6,
            field=outer)
    # the crest: blades swept back off the brow and the crown, stacked down the side of the head and nearly parallel (the
    # sheet: from the front they lie back behind the head; seen from the side a layered fin), pale and dark by turns
    # the crest (the owner, 2026-11-22: "crest more layered"): eight blades a side in three layers, thick and curved,
    # RISING up and back off the brow and the crown (the sheet: a crown of curved horns; laid back level they read as a
    # fan of knives), pale and dark by turns, the longest on top, the lowest down the back of the skull
    crest = [  # name, points (root first, inside the mask), width, the way its face looks, material, notch
        ('crest_a', [p(.014, -.050, .142), p(.030, .028, .192), p(.048, .108, .246), p(.058, .168, .292)], .056, (1, 0, .55), 'armour', (.62, .30)),
        ('crest_b', [p(.026, -.040, .130), p(.048, .048, .170), p(.070, .132, .214), p(.082, .188, .246)], .052, (1, 0, .48), 'dark', None),
        ('crest_c', [p(.038, -.030, .116), p(.062, .058, .146), p(.086, .148, .180), p(.098, .206, .200)], .054, (1, 0, .40), 'armour', (.58, .32)),
        ('crest_d', [p(.046, -.018, .100), p(.070, .062, .120), p(.092, .142, .138), p(.102, .192, .146)], .046, (1, 0, .34), 'dark', None),
        ('crest_e', [p(.050, .002, .086), p(.072, .080, .094), p(.090, .150, .100)], .042, (1, 0, .30), 'armour', (.55, .30)),
        ('crest_f', [p(.050, .030, .070), p(.066, .108, .064), p(.080, .170, .054)], .040, (1, 0, .25), 'dark', None),
        ('crest_g', [p(.044, .058, .052), p(.058, .128, .040), p(.066, .182, .026)], .036, (1, 0, .20), 'armour', None),
        ('crest_h', [p(.034, .084, .034), p(.044, .146, .016), p(.048, .190, .000)], .032, (1, 0, .15), 'dark', None),
    ]
    for name, pts, w, face, mat, notch in crest:
        A.shard(name, pts, w * S * 1.1, face, 'head', thick=.016 * S, base=.70, peak=.42, point=.8, lower=.70, notch=notch, mat=mat,
                edge=.22)
    for name, pts, w in (('horn', [p(.014, -.030, .148), p(.020, -.006, .214), p(.028, .048, .284)], .036),
                         ('horn2', [p(.022, .010, .150), p(.030, .048, .208), p(.036, .108, .256)], .032)):
        A.shard(name, pts, w * S * 1.1, (1, 0, 0), 'head', thick=.014 * S, base=.70, peak=.35, point=.85, lower=.60, mat='dark', edge=.22)
    # the face's second layer: a heavy brow plate over each eye, a second cheek plate under the first, a plate at the
    # temple behind the eye (the sheet's face is plates over plates, not one shell with stripes)
    A.blade('browplate', p(.022, -.074, .100), p(.060, -.018, .114), .030 * S, 'head', lift=.0030, tip=.006, free=.80, ridge=.006,
            thick=.009, peak=.35, base=.7, mat='dark', field=outer)
    A.blade('cheek2', p(.028, -.102, -.014), p(.060, -.032, .018), .030 * S, 'head', lift=.0026, ridge=.005, thick=.007, peak=.45,
            base=.6, field=outer)
    A.blade('temple2', p(.054, -.024, .052), p(.070, .046, .066), .028 * S, 'head', lift=.0024, tip=.006, free=.85, ridge=.005,
            thick=.006, peak=.35, base=.7, field=outer)

    A.slot = 'neck'
    A.wrap('neckring', nk + (0, .004, .030), nk + (hd - nk) * .80 + (0, .012, 0), 'neck', around=5, rows=2, span=(-150, 150), face=(0, 1, 0),
           cover=1.0, tip=.016, thick=.006, dark_arc=((-40, 40),), accents=.3)
    # down the back of the neck plates lying on it, their ends lifting toward the crest
    for k, (t0, t1, w) in enumerate(((.08, .48, .060), (.38, .78, .052), (.66, 1.02, .044))):
        a_, b_ = nk + (hd - nk) * t0, nk + (hd - nk) * t1
        A.blade(f'nape{k}', a_ + (0, .075, -.010), b_ + (0, .060, .010), w, 'neck', lift=.003, tip=.016, free=.70, ridge=.006,
                thick=.007, peak=.35, base=.6, mirror=False, mat='armour' if k != 1 else 'dark')
