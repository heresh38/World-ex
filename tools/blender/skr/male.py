"""The male Sarketh's armour (metal plates he wears, by slot) and his claws, after the owner's sheet (art/reference/sarketh/sarketh_design_sheet.png): most of the body
under overlapping plates with the dark scaled body showing in the gaps between them. A crest of blades lying back over
the skull and sweeping off behind it, a pale plate down the snout over a dark mask, a slit of light either side; heavy
layered pauldrons with spikes rising over the shoulders; a chest of broad plates meeting in a V; every limb ringed in
rows of plates pointing down it, lying close; plates across the knuckles, long curved claws;
the spine a row of plates with lights between them. Points are for the LEFT side (+X) and mirrored.

Angles in wrap(): 0 = the `face` direction; for a limb running DOWN with face (0, -1, 0) (forward), +90 is the inside
(-X) and -90 the outside (+X)."""
import numpy as np

FINGERS = ('index', 'middle', 'ring', 'pinky')


def layout(A, J):
    A.thick_k, A.tip_k = 2.4, .7            # thick armour plates lying on the body, edges barely lifted (not spiky: the owner)
    A.point_k = .55                         # blunt points: the plates end rounded, not in needles
    j = lambda b, e=0: np.asarray(J[b][e], float)
    hd, nk = j('head'), j('neck')

    # ---- the head (the owner's sheet, "head detail"): a tall, narrow face, its dark visor down to a pointed chin with a slit
    #      of light along each side, framed by pale guards; a brow plate over the crown; blades swept back off the crown and
    #      the temples. All of it is his HELMET; the eyes are his own.
    A.slot = 'body'
    A.slot = 'helmet'
    # the helmet (the sheet's head detail): FACETED, flat planes meeting in hard edges, not a rounded shell. A tall narrow
    # head: the top and the back swept back, a sloping brow, the face a V of two planes down to a pointed chin under a dark
    # visor, flat cheeks, the jaw cut back under it to the neck. Each plane sits about a centimetre outside the skull.
    planes = [((0, .45, 1), .172), ((0, .90, .50), .172), ((0, 1, -.30), .097), ((0, -.55, .85), .162),
              ((.62, -1, .05), .085), ((-.62, -1, .05), .085), ((.5, -.6, -.6), .080), ((-.5, -.6, -.6), .080),
              ((1, -.05, -.30), .057), ((-1, -.05, -.30), .057), ((1, .10, .90), .122), ((-1, .10, .90), .122),
              ((0, -.75, -1), .080), ((1, -.20, -1), .062), ((-1, -.20, -1), .062), ((0, .30, -1), .060),
              ((.6, 0, .8), .150), ((-.6, 0, .8), .150),                     # a pitched top: a ridge, not a lid
              ((.8, .6, 0), .095), ((-.8, .6, 0), .095),                     # the back narrowing behind
              ((.8, -1, .05), .080), ((-.8, -1, .05), .080)]                 # a sharper V to the face
    NP = np.array([np.asarray(n_, float) / np.linalg.norm(n_) for n_, _ in planes], np.float32)
    DP = np.array([d_ for _, d_ in planes], np.float32)

    def poly(P):
        q = np.asarray(P, np.float32) - hd.astype(np.float32)
        return (q @ NP.T - DP[None, :]).max(1)
    zc, zn, yn = hd[2] - .052, hd[2] + .045, hd[1] + .035

    def keep(P):
        return np.maximum(zc - P[:, 2], np.minimum(zn - P[:, 2], P[:, 1] - yn))

    def mat_of(c):
        q = c - hd
        return 'dark' if (q[1] < -.030 and -.040 < q[2] < .112 and abs(q[0]) < .046 and q[1] < -.035 - .4 * abs(q[0])) else 'armour'
    grooves = [(hd + (0, -.030, .134), (0, -.6, 1), .0024), (hd + (0, .062, .060), (0, 1, .3), .0022)]
    slits, eyes = [], []
    for sg in (1, -1):
        e0, e1 = hd + (.024 * sg, -.080, .052), hd + (.046 * sg, -.066, .090)
        slits.append((e0, e1, .0042))
        eyes.append((e0, e1, sg))
    A.shell('helmet', 'head', poly, hd + (-.090, -.200, -.090), hd + (.090, .160, .225), -.0055, .0055, keep, mat_of, grooves, slits,
            h=.0009, target=16000)
    A.slot = 'body'
    for e0, e1, sg in eyes:                                    # his eyes, burning in the slits
        nrm = np.array([.526 * sg, -.849, .042])
        A.claw('eye' if sg > 0 else 'eye_R', e0 - nrm * .0025, e1 - nrm * .0025, .0036, 'head', up=(0, 0, 1), hook=.0, flat=1.0, mirror=False,
               mat='glow', segs=8, ring=6)
    A.slot = 'helmet'
    A.blade('guard', hd + (.040, -.060, -.022), hd + (.062, -.010, .118), .026, 'head', lift=.002, ridge=.004, peak=.5, base=.6, field=poly,
            thick=.006)
    A.blade('temple', hd + (.058, -.030, .108), hd + (.082, .090, .090), .050, 'head', lift=.002, tip=.000, free=.72, peak=.5, point=.7,
            field=poly)
    for k in range(5):
        a_ = hd + (.010 + .012 * k, -.010 + .020 * k, .168 - .006 * k)
        b_ = hd + (.030 + .032 * k, .190 + .010 * k, .190 - .032 * k)          # fanned out and back
        A.blade(f'crest{k}', a_, b_, .088 - .006 * k, 'head', lift=.002 + .005 * k, tip=.000, free=.66, thick=.006, ridge=.007, peak=.40,
                point=1.3, bend=(0, 0, .016), mat='dark' if k in (1, 3) else 'armour', field=poly)
    A.blade('crown', hd + (.016, .000, .172), hd + (.042, .150, .246), .050, 'head', lift=.006, tip=.000, free=.55, thick=.006, ridge=.007,
            peak=.40, point=1.3, bend=(0, 0, .02), field=poly)
    A.blade('crestmid', hd + (0, -.010, .178), hd + (0, .170, .205), .084, 'head', lift=.004, tip=.000, free=.62, thick=.007, ridge=.008,
            peak=.40, point=1.2, bend=(0, 0, .020), mirror=False, field=poly)
    A.blade('occiput', hd + (.020, .092, .110), hd + (.040, .140, .010), .050, 'head', lift=.002, tip=.004, free=.6, mat='dark', field=poly)

    A.slot = 'neck'
    # ---- neck: rings of small plates, a ridge at the nape
    A.wrap('neck', nk + (0, .006, .150), nk + (0, .010, -.010), 'neck', around=7, rows=3, span=(-180, 180), face=(0, -1, 0), cover=1.0,
           tip=.005, thick=.005, n=(10, 6), dark=((0, 2), (1, 1), (1, 4), (2, 3), (2, 6)), mirror=False, flip=False)
    A.blade('nape', nk + (0, .055, .000), nk + (0, .080, .160), .040, 'neck', lift=.004, tip=.012, free=.75, mirror=False)

    A.slot = 'chest'
    # ---- chest and belly
    A.blade('pec', (.030, -.132, 1.680), (.190, -.074, 1.560), .120, 'chest', lift=.004, ridge=.006, thick=.008, peak=.4)
    A.blade('pec2', (.040, -.124, 1.585), (.150, -.092, 1.488), .086, 'chest', lift=.003, ridge=.004, peak=.4)
    A.blade('collar', (.020, -.104, 1.724), (.180, -.044, 1.712), .060, 'chest', lift=.007, ridge=.004, peak=.4, mat='dark')
    A.blade('sternum', (0, -.134, 1.708), (0, -.128, 1.480), .050, 'chest', lift=.005, ridge=.006, mirror=False, thick=.008)
    A.wrap('ribs', (.150, -.020, 1.560), (.150, .010, 1.330), 'chest', around=2, rows=3, span=(-70, 30), face=(1, -.4, 0), cover=.9,
           tip=.006, dark=((1, 0),))
    A.blade('oblique', (.090, -.088, 1.340), (.122, -.060, 1.240), .046, 'spine', lift=.003, tip=.004)
    for r_, z in enumerate((1.445, 1.390, 1.335, 1.280)):
        A.blade(f'belly{r_}', (.006, -.100, z), (.068, -.084, z - .030), .052, 'spine', mat='dark', lift=.002, ridge=.004, peak=.45, base=.8, tip=.002)
    A.wrap('flank', (.115, .000, 1.450), (.112, .010, 1.260), 'spine', around=2, rows=2, span=(-80, 30), face=(1, -.3, 0), cover=1.0, tip=.004,
           dark=((1, 1),))
    A.stud('heart', (0, -.146, 1.610), .0048, 'chest', mirror=False)
    A.stud('belly', (0, -.104, 1.350), .0036, 'spine', mirror=False)

    A.slot = 'shoulders'
    # ---- shoulders: a pauldron in three layers (rounded: no spikes, the owner 2026-11-15)
    A.blade('pauldron', (.170, .000, 1.785), (.340, .032, 1.565), .150, 'upperarm.L', lift=.008, ridge=.007, thick=.010, peak=.3, tip=.016,
            bend=(.022, 0, 0))
    A.blade('pauldron2', (.215, .020, 1.745), (.362, .052, 1.530), .118, 'upperarm.L', lift=.020, ridge=.006, thick=.009, peak=.3, tip=.022,
            mat='dark')
    A.blade('pauldron3', (.245, .030, 1.700), (.372, .060, 1.500), .086, 'upperarm.L', lift=.032, ridge=.005, thick=.008, peak=.3, tip=.026)
    A.slot = 'back'
    A.blade('scapula', (.060, .118, 1.690), (.185, .104, 1.505), .100, 'chest', lift=.004, ridge=.005, thick=.008)
    A.blade('scapula2', (.040, .120, 1.600), (.150, .110, 1.440), .070, 'chest', lift=.003, mat='dark')
    A.blade('lat', (.130, .086, 1.520), (.160, .060, 1.380), .052, 'chest', lift=.003)
    A.wrap('back', (.090, .040, 1.700), (.095, .045, 1.420), 'chest', around=3, rows=3, span=(-75, 75), face=(0, 1, 0), cover=1.04, tip=.006,
           dark=((0, 1), (2, 0)), lift=.0045)
    A.wrap('glute', (.070, .040, 1.200), (.085, .040, 1.040), 'hips', around=3, rows=2, span=(-80, 80), face=(0, 1, 0), cover=1.04, tip=.006,
           dark=((1, 1),))

    A.slot = 'arms'
    # ---- arms: the upper arm and the forearm ringed in plates pointing down
    sh, el, wr = j('upperarm.L'), j('forearm.L'), j('hand.L')
    A.wrap('uarm', sh + (el - sh) * .22, el + (el - sh) * .05, 'upperarm.L', around=5, rows=3, span=(-220, 45), face=(0, -1, 0), cover=1.06,
           tip=.008, dark=((0, 1), (0, 3), (1, 0), (1, 3), (2, 0), (2, 2)))
    A.wrap('farm', el + (wr - el) * .06, wr + (wr - el) * .02, 'forearm.L', around=5, rows=3, span=(-230, 55), face=(0, -1, 0), cover=1.06,
           tip=.008, dark=((0, 2), (1, 1), (1, 4), (2, 0), (2, 3)))
    A.blade('forearm', el + (.034, .006, -.030), wr + (.040, .030, .010), .060, 'forearm.L', lift=.010, ridge=.005, peak=.3, tip=.010)
    hn = j('hand.L', 1)
    A.slot = 'hands'
    A.blade('handback', wr + (.012, .000, -.006), hn + (.018, -.004, -.014), .056, 'hand.L', lift=.003, ridge=.004, peak=.45, thick=.006)
    for f in FINGERS:
        for k in (1, 2, 3):
            a, b = j(f'{f}{k}.L'), j(f'{f}{k}.L', 1)
            A.slot = 'hands'
        A.blade(f'{f}{k}', a + (.008, 0, .003), b + (.008, 0, .000), (.020, .017, .014)[k - 1], f'{f}{k}.L', lift=.0018, ridge=.002,
                    thick=.004, peak=.5, base=.8, n=(8, 5), mat='dark' if k == 3 else 'armour')
        a, b = j(f'{f}3.L'), j(f'{f}3.L', 1)
        d = (b - a) / np.linalg.norm(b - a)
        A.slot = 'body'
        A.claw(f'{f}claw', b - d * .014, b + d * .046 + np.array([-.012, 0, -.004]), .0072, f'{f}3.L', up=(-1, 0, 0), hook=.5)
    a, b = j('thumb3.L'), j('thumb3.L', 1)
    d = (b - a) / np.linalg.norm(b - a)
    A.slot = 'body'
    A.claw('thumbclaw', b - d * .012, b + d * .038 + np.array([-.006, 0, 0]), .0072, 'thumb3.L', up=(-1, 0, 0), hook=.45)

    A.slot = 'belt'
    # ---- hips: a girdle of plates, the loin's V
    A.wrap('girdle', (0, .010, 1.270), (0, .010, 1.080), 'hips', around=7, rows=1, span=(-35, 200), face=(0, -1, 0), cover=.86, overlap=.2,
           tip=.010, dark=((0, 1), (0, 4)), reach=.40, mirror=False)
    A.wrap('girdle_r', (0, .010, 1.270), (0, .010, 1.080), 'hips', around=3, rows=1, span=(-200, -45), face=(0, -1, 0), cover=.86, overlap=.2,
           tip=.010, reach=.40, mirror=False)
    A.blade('loin', (0, -.110, 1.210), (0, -.094, 1.020), .066, 'hips', lift=.006, ridge=.006, mirror=False, thick=.008)
    A.blade('hipflare', (.130, -.040, 1.260), (.190, -.012, 1.080), .080, 'hips', lift=.012, ridge=.005, tip=.012)

    A.slot = 'legs'
    # ---- legs
    hj, kn, hk, ba = j('thigh.L'), j('shin.L'), j('foot.L'), j('toes.L')
    A.wrap('thigh', hj + (kn - hj) * .10, kn + (kn - hj) * .02, 'thigh.L', around=6, rows=4, span=(-225, 85), face=(0, -1, 0), cover=1.06,
           tip=.008, ridge=.004, thick=.007, dark=((0, 2), (0, 4), (1, 0), (1, 3), (2, 1), (2, 3), (3, 0), (3, 5)))
    A.blade('thighout', hj + (.070, -.010, -.050), kn + (.050, -.010, .080), .080, 'thigh.L', lift=.014, ridge=.006, thick=.009, peak=.35, tip=.012)
    A.blade('knee', kn + (0, -.050, .070), kn + (0, -.056, -.092), .074, 'shin.L', lift=.006, ridge=.007, thick=.009)
    A.stud('kneelight', kn + (0, -.070, -.004), .0042, 'shin.L')
    A.wrap('shin', kn + (hk - kn) * .14, hk + (hk - kn) * .02, 'shin.L', around=5, rows=4, span=(-215, 85), face=(0, -1, -.4), cover=1.06,
           tip=.008, thick=.006, dark=((0, 1), (1, 2), (1, 4), (2, 0), (3, 2), (3, 4)))
    A.slot = 'feet'
    A.wrap('foot', hk + (ba - hk) * .08, ba + (ba - hk) * .10, 'foot.L', around=4, rows=2, span=(-170, 130), face=(0, -1, .3), cover=1.05,
           tip=.006, thick=.006, dark=((1, 1),))
    for dx, ln in ((-.026, .088), (0.0, .102), (.026, .086)):
        tip_ = ba + (dx * 1.6, -.030 - ln, -.034)
        root = ba + (dx, -.030, -.010)
        A.slot = 'feet'
        A.blade(f'toe{dx:+.3f}', root + (0, -.010, .018), tip_ + (0, .022, .018), .026, 'toes.L', lift=.002, ridge=.003, thick=.005, n=(10, 5))
        A.slot = 'body'
        A.claw(f'toeclaw{dx:+.3f}', tip_ + (0, .016, .006), tip_ + (dx * .4, -.058, -.030), .0125, 'toes.L', up=(0, 0, 1), hook=.55)
    A.slot = 'body'
    A.claw('dewclaw', ba + (-.040, .040, -.030), ba + (-.052, .080, -.050), .009, 'toes.L', up=(0, 0, 1), hook=.4)

    A.slot = 'back'
    # ---- the back: the spine's plates with lights between them, plates on the low back
    for k, z in enumerate((1.745, 1.672, 1.600, 1.528, 1.456, 1.384, 1.312, 1.240)):
        bone = 'chest' if z > 1.46 else 'spine'
        A.blade(f'spine{k}', (0, .150, z + .040), (0, .175, z - .050), .046 - .003 * k, bone, lift=.004, ridge=.006, tip=.003, free=1.0,
                mirror=False, thick=.008)
        A.stud(f'spinelight{k}', (0, .162, z - .052), .0036, bone, mirror=False)
    A.wrap('lowback', (.050, .060, 1.420), (.060, .060, 1.270), 'spine', around=2, rows=2, span=(-20, 60), face=(0, 1, 0), cover=.9, tip=.005,
           dark=((0, 1),))
