"""The male Sarketh's armour (metal plates he wears, by slot) and his claws, after the owner's sheet (art/reference/sarketh/sarketh_design_sheet.png): most of the body
under overlapping plates with the dark scaled body showing in the gaps between them. A crest of blades lying back over
the skull and sweeping off behind it, a pale plate down the snout over a dark mask, a slit of light either side; heavy
layered pauldrons with spikes rising over the shoulders; a chest of broad plates meeting in a V; every limb ringed in
rows of plates pointing down it, flaring at the elbows, knees and heels; plates across the knuckles, long curved claws;
the spine a row of plates with lights between them. Points are for the LEFT side (+X) and mirrored.

Angles in wrap(): 0 = the `face` direction; for a limb running DOWN with face (0, -1, 0) (forward), +90 is the inside
(-X) and -90 the outside (+X)."""
import numpy as np

FINGERS = ('index', 'middle', 'ring', 'pinky')


def layout(A, J):
    A.thick_k, A.tip_k = 1.7, 1.5           # thick armour plates, their lower edges standing a little off the body
    j = lambda b, e=0: np.asarray(J[b][e], float)
    hd, nk = j('head'), j('neck')

    # ---- the head (the owner's sheet, "head detail"): a tall, narrow face, its dark visor down to a pointed chin with a slit
    #      of light along each side, framed by pale guards; a brow plate over the crown; blades swept back off the crown and
    #      the temples. All of it is his HELMET; the eyes are his own.
    A.slot = 'body'
    A.light('eye', [hd + (.024, -.072, .056), hd + (.035, -.062, .075), hd + (.046, -.050, .094)], .0095, 'head', lift=.002)
    A.light('eyetail', [hd + (.040, -.042, .090), hd + (.046, -.024, .100)], .0026, 'head')
    A.slot = 'helmet'
    # the helmet's shell: the whole head enclosed 4 mm off it, panels parted by seams, the face behind a dark visor with the
    # eyes' slits cut through it (the light under it is his own)
    hs_fn = A.subfield({'head'})
    zc, zn, yn = hd[2] - .045, hd[2] + .050, hd[1] + .030

    def keep(P):
        return np.maximum(zc - P[:, 2], np.minimum(zn - P[:, 2], P[:, 1] - yn))

    def mat_of(c):
        return 'dark' if (c[1] < hd[1] - .015 and abs(c[0]) < .028 and c[2] < hd[2] + .115) else 'armour'
    grooves = [((+.027, 0, 0), (1, 0, 0), .0022), ((-.027, 0, 0), (1, 0, 0), .0022),
               (hd + (0, -.052, .116), (0, -.35, 1), .0024), (hd + (0, .040, .040), (0, 1, .25), .0022)]
    slits = []
    for sg in (1, -1):
        slits.append((hd + (.024 * sg, -.074, .056), hd + (.046 * sg, -.050, .094), .0045))
    A.shell('helmet', 'head', hs_fn, hd + (-.085, -.20, -.085), hd + (.085, .15, .225), .004, .0048, keep, mat_of, grooves, slits)
    A.blade('temple', hd + (.046, -.022, .092), hd + (.094, .120, .082), .052, 'head', lift=.014, tip=.002, free=.55, peak=.5, point=.7,
            only=('head',))
    for k in range(5):
        a_ = hd + (.010 + .012 * k, .000 + .020 * k, .152 - .006 * k)
        b_ = hd + (.032 + .026 * k, .200 + .020 * k, .196 - .030 * k)
        A.blade(f'crest{k}', a_, b_, .086 - .006 * k, 'head', lift=.014 + .006 * k, tip=.002, free=.50, thick=.008, ridge=.008, peak=.50,
                point=.7, bend=(0, 0, .018), mat='dark' if k in (1, 3) else 'armour', only=('head',))
    A.blade('crestmid', hd + (0, .010, .166), hd + (0, .235, .232), .090, 'head', lift=.018, tip=.002, free=.48, thick=.009, ridge=.009,
            peak=.50, point=.7, bend=(0, 0, .022), mirror=False, only=('head',))
    A.blade('occiput', hd + (.020, .082, .110), hd + (.040, .140, .000), .052, 'head', lift=.012, tip=.006, free=.55, mat='dark', only=('head',))

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
    # ---- arms: the upper arm and the forearm ringed in plates pointing down, a spike off the elbow
    sh, el, wr = j('upperarm.L'), j('forearm.L'), j('hand.L')
    A.wrap('uarm', sh + (el - sh) * .22, el + (el - sh) * .05, 'upperarm.L', around=5, rows=3, span=(-220, 45), face=(0, -1, 0), cover=1.06,
           tip=.008, dark=((0, 1), (1, 3), (2, 0)))
    A.blade('elbow', el + (-.004, .036, .040), el + (.012, .140, -.040), .044, 'forearm.L', lift=.005, tip=.012, free=.32, thick=.008)
    A.wrap('farm', el + (wr - el) * .06, wr + (wr - el) * .02, 'forearm.L', around=5, rows=3, span=(-230, 55), face=(0, -1, 0), cover=1.06,
           tip=.008, dark=((1, 1), (2, 3)))
    A.blade('forearm', el + (.034, .006, -.030), wr + (.040, .030, .010), .060, 'forearm.L', lift=.010, ridge=.005, peak=.3, tip=.010)
    A.blade('wristflare', el + (wr - el) * .70 + (.034, .040, 0), wr + (.056, .090, -.070), .036, 'forearm.L', lift=.010, tip=.010, free=.48)
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
           tip=.008, ridge=.004, thick=.007, dark=((0, 2), (1, 0), (2, 3), (3, 5)))
    A.blade('thighout', hj + (.070, -.010, -.050), kn + (.050, -.010, .080), .080, 'thigh.L', lift=.014, ridge=.006, thick=.009, peak=.35, tip=.012)
    A.blade('kneespike', kn + (.044, -.012, .086), kn + (.096, .000, .212), .036, 'thigh.L', lift=.008, tip=.010, free=.32, thick=.008)
    A.blade('knee', kn + (0, -.050, .070), kn + (0, -.056, -.092), .074, 'shin.L', lift=.006, ridge=.007, thick=.009)
    A.stud('kneelight', kn + (0, -.070, -.004), .0042, 'shin.L')
    A.wrap('shin', kn + (hk - kn) * .14, hk + (hk - kn) * .02, 'shin.L', around=5, rows=4, span=(-215, 85), face=(0, -1, -.4), cover=1.06,
           tip=.008, thick=.006, dark=((1, 2), (2, 0)))
    for k, t in enumerate((.20, .48)):
        p = kn + (hk - kn) * t
        A.blade(f'calfspike{k}', p + (0, .044, .012), p + (0, .150, -.040), .040 - .006 * k, 'shin.L', lift=.006, tip=.010, free=.40, thick=.008)
    A.slot = 'feet'
    A.blade('heel', hk + (0, .024, .046), hk + (0, .130, -.004), .032, 'foot.L', lift=.006, tip=.010, free=.35, thick=.007)
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
        A.blade(f'spine{k}', (0, .150, z + .040), (0, .175, z - .050), .046 - .003 * k, bone, lift=.004, ridge=.006, tip=.010, free=.75,
                mirror=False, thick=.008)
        A.stud(f'spinelight{k}', (0, .162, z - .052), .0036, bone, mirror=False)
    A.wrap('lowback', (.050, .060, 1.420), (.060, .060, 1.270), 'spine', around=2, rows=2, span=(-20, 60), face=(0, 1, 0), cover=.9, tip=.005,
           dark=((0, 1),))
