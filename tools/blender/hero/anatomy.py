"""Surface anatomy for the hero bodies: the relief the lofts and blended ellipsoids of shape.py cannot hold (smooth
minimum rounds every border away). A signed offset in metres, positive = outward, subtracted from the body's signed
distance so the fitted mesh, its normals and everything built on the body follow it.

Built from two things only, placed from the same targets and joints as the body:
  bump   an ellipsoidal swell (a muscle belly, a bone under the skin) or, negative, a hollow
  line   a ridge (tendon, crest) or, negative, a furrow (the border between two muscles) along a polyline

Torso features on the front and the back are laid out in the coronal plane (x, z) and masked to their side; limb
features are placed in 3D along the limb's own axes. Evaluated on (|x|, y, z): everything is modelled once, on the
left. `k` scales the muscular definition (his full, hers a trained but soft fraction); bony landmarks and the folds
every body has (spine, navel, collar bones, knees, ankles, knuckles) are kept on both.
"""
import numpy as np
from mathutils import Vector

F32 = np.float32
GAIN_MALE, GAIN_FEMALE = 1.7, .8          # how deep the relief is cut: an athlete, lean enough to read


def V(v):
    return np.asarray(tuple(v), F32)


def sstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def bump(P, c, r, amp, R=None):
    q = P - V(c)
    if R is not None:
        q = q @ np.asarray(R, F32).T
    q = q / np.asarray(r, F32)
    return amp * np.exp(-(q * q).sum(1))


def seg_dist(P, a, b):
    a, b = np.asarray(a, F32), np.asarray(b, F32)
    ab = b - a
    t = np.clip(((P - a) @ ab) / max(float(ab @ ab), 1e-12), 0, 1)
    return np.linalg.norm(P - (a + t[:, None] * ab), axis=1), t


def line(P, pts, width, amp, fade=0.0):
    """ridge (+) / furrow (-) along a polyline; fade = the fraction of each end over which it runs out. The strongest
    segment's value is taken per point (each segment's own falloff x its own fade: continuous everywhere; picking the
    fade of the nearest segment jumps where two segments are equally near and cuts a line into the surface)"""
    n = len(pts) - 1
    out = None
    for i in range(n):
        d, t = seg_dist(P, pts[i], pts[i + 1])
        w = np.exp(-(d / width) ** 2)
        if fade > 0:
            s = (i + t) / n
            w = w * sstep(0, fade, s) * sstep(1, 1 - fade, s)
        out = w if out is None else np.maximum(out, w)
    return amp * out


def xz(P):
    return P[:, [0, 2]]


def torso(B, P):
    T, m = B.T, B.m
    k = 1.0 if m else .38
    C, U, W, H = T["chest"]["z"], T["underbust"]["z"], T["waist"]["z"], T["hips"]["z"]
    nb, sh, cr = T["neck_base_z"], T["shoulder_z"], T["crotch_z"]
    s = T["biacromial"] / .41
    y = P[:, 1]
    front = sstep(.01, -.045, y)
    back = sstep(-.01, .045, y)
    Q = xz(P)
    o = np.zeros(len(P), F32)
    # ---- front
    o += line(Q, [(0, nb - .04), (0, U + .03)], .011, -.0042 * (1 if m else .55), .15) * front              # sternum
    o += bump(P, (0, -T["neck_d"] * .40, nb - .014), (.014, .014, .012), -.0045)                            # jugular notch
    o += bump(P, (.075 * s, -.018, nb + .004), (.034, .022, .012), -.0035)                                  # hollow over the collar bone
    if m:
        o += bump(Q, (.088, C + .028), (.066, .050), .0045) * front                                         # pectoral
        o += line(Q, [(.03, C - .042), (.066, C - .05), (.112, C - .036), (.152, C + .012)], .011, -.0052, .22) * front
        o += line(Q, [(.128, sh - .045), (.15, C + .035)], .010, -.003, .2) * front                         # deltopectoral groove
    # the belly wall: the midline, the borders of the rectus, its tendinous bands, the navel
    o += line(Q, [(0, U + .02), (0, W - .028)], .009, -.0034 * (1 if m else .6), .12) * front
    o += line(Q, [(0, W - .05), (0, H - .015)], .010, -.0014 * k, .2) * front
    o += bump(P[:, [0, 2]], (0, W - .04), (.007, .009), -.0075) * front                                      # navel
    semi = [(U * 0 + .060 * (1 if m else .9), U + .012), (.064 * (1 if m else .9), W + .0), (.048, H + .025)]
    o += line(Q, semi, .011, -.003 * k, .12) * front
    for zi in (U - .016, W + .068, W + .004):
        o += line(Q, [(.004, zi), (.052, zi - .004)], .008, -.0027 * k, .1) * front
    for zi in (U + .022, (U - .016 + W + .068) / 2, (W + .068 + W + .004) / 2, W - .03):
        o += bump(Q, (.031, zi), (.022, .026), .0022 * k) * front
    if m:
        for i, zi in enumerate((U + .034, U + .004, U - .026)):                                             # serratus
            o += bump(P, (T["underbust"]["w"] * .47 - i * .004, -.045 - i * .006, zi), (.016, .02, .013), .0026)
    # the groove of the groin from the hip bone to the pubis; the hip bone itself
    o += line(Q, [(.122 * (1 if m else .98), H + .07), (.084, H + .018), (.036, cr + .05)], .012, -.003 * (1 if m else .35), .12) * front
    o += bump(P, (H * 0 + T["hips"]["w"] * .36, -T["hips"]["d"] * .30, H + .085), (.018, .018, .022), .002)
    # ---- back
    o += line(Q, [(0, nb - .025), (0, C), (0, W), (0, H + .045)], .013, -.0052 * (1 if m else .75), .08) * back   # the spine's furrow
    o += line(Q, [(.031, W - .05), (.033, U + .01)], .016, .003 * k, .2) * back                             # erector spinae
    o += line(Q, [(.052 * s, sh - .06), (.058 * s, C + .012)], .012, -.0026 * k, .2) * back                 # the scapula's inner border
    o += bump(Q, (.084 * s, C + .004), (.022, .020), .003 * k) * back                                       # its lower angle
    o += bump(Q, (.118 * s, C + .062), (.034, .028), .003 * k) * back                                       # infraspinatus / teres
    if m:
        o += line(Q, [(.152, C - .02), (.122, W + .04)], .020, .0028, .25) * back                           # the lat's outer edge
        o += line(Q, [(.02, nb - .05), (.085, sh - .03)], .018, .0022, .25) * back                          # upper trapezius
    o += bump(Q, (.034, H + .066), (.010, .010), -.003) * back                                              # sacral dimples
    o += line(Q, [(0, H + .03), (0, cr + .012)], .011, -.012, .1) * back                                    # between the glutes
    o += line(Q, [(.024, cr - .038), (.07, cr - .034), (.116, cr - .016)], .012, -.004, .15) * back         # the gluteal fold
    o += bump(P, (T["hips"]["w"] * .475, .028, H - .022), (.02, .04, .042), -.0036 * (1 if m else .1))      # the hollow of the hip
    return o


def arm(B, P):
    T, A, m = B.T, B.arm, B.m
    k = 1.0 if m else .36
    a, dor = A["a"], A["dorsal"]
    fwd = (A["thumb"] - a * A["thumb"].dot(a)).normalized()
    S, E, Wr = A["S"], A["E"], A["W"]
    ur, fr = T["upper_arm_r"], T["forearm_r"]
    R = B.arm_rows                                             # rows: along, dorsal, a x dorsal
    L = T["upper_arm"]
    o = np.zeros(len(P), F32)
    # the deltoid's point a third of the way down, between biceps and triceps
    tip = S + a * (L * .47) + dor * ur * .92
    o += line(P, [V(S + a * .055 + fwd * ur * 1.0), V(tip)], .012, -.0032 * k, .15)
    o += line(P, [V(S + a * .06 - fwd * ur * 1.0 + dor * ur * .2), V(tip)], .012, -.0028 * k, .15)
    o += bump(P, S + a * (L * .22) + dor * ur * 1.0, (.07, .03, .05), .003 * k, R)
    # biceps, the furrows down both its sides, the two heads of the triceps and its flat tendon
    o += bump(P, S + a * (L * .56) + fwd * ur * .86, (.062, .030, .030), .0052 * k, R)
    o += line(P, [V(S + a * (L * .42) + dor * ur * .96 + fwd * ur * .2), V(E - a * .035 + dor * ur * .72 + fwd * ur * .25)], .010, -.0024 * k, .15)
    o += line(P, [V(S + a * (L * .34) - dor * ur * .9 + fwd * ur * .2), V(E - a * .04 - dor * ur * .7 + fwd * ur * .15)], .011, -.0026 * k, .15)
    o += bump(P, S + a * (L * .42) - fwd * ur * .62 + dor * ur * .52, (.05, .026, .026), .0042 * k, R)
    o += bump(P, S + a * (L * .46) - fwd * ur * .84 - dor * ur * .3, (.06, .026, .026), .0034 * k, R)
    o += bump(P, S + a * (L * .82) - fwd * ur * .78, (.045, .022, .022), -.003 * k, R)
    # the elbow: the hollow in front, the point of the ulna and the two condyles behind
    o += bump(P, E + fwd * ur * .66, (.022, .02, .02), -.003 * (1 if m else .6), R)
    o += bump(P, E - fwd * ur * .58 + dor * ur * .42, (.012, .01, .01), .002)
    o += bump(P, E - fwd * ur * .58 - dor * ur * .42, (.012, .01, .01), .002)
    # forearm: brachioradialis over the thumb side, the flexors' mass inside, the extensors on top, the ulna's edge
    FL = T["forearm"]
    o += bump(P, E + a * (FL * .2) + fwd * fr * .72 + dor * fr * .5, (.062, .02, .02), .0042 * k, R)
    o += bump(P, E + a * (FL * .26) - dor * fr * .84 + fwd * fr * .1, (.07, .022, .024), .0034 * k, R)
    o += bump(P, E + a * (FL * .3) + dor * fr * .9 - fwd * fr * .3, (.07, .02, .022), .003 * k, R)
    o += line(P, [V(E + a * (FL * .3) - fwd * fr * .86), V(Wr - a * .02 - fwd * T["wrist"]["w"] * .46)], .008, .0016 * (1 if m else .7), .2)
    o += line(P, [V(E + a * (FL * .45) + dor * fr * .55 + fwd * fr * .1), V(Wr - a * .03 + dor * fr * .3)], .009, -.0018 * k, .2)
    # wrist: the head of the ulna, the two tendons on the palm side
    wd = T["wrist"]
    o += bump(P, Wr - a * .012 - fwd * wd["w"] * .42 + dor * wd["d"] * .42, (.009, .008, .008), .0028)
    for off in (.1, -.12):
        o += line(P, [V(Wr - a * .06 - dor * wd["d"] * .5 + fwd * wd["w"] * off), V(Wr - a * .004 - dor * wd["d"] * .5 + fwd * wd["w"] * off)],
                  .0042, .0012 * (1 if m else .7), .25)
    return o


def hand(B, P):
    T, Hd, m = B.T, B.hand, B.m
    A = Hd["arm"]
    a, dor, th = A["a"], A["dorsal"], A["thumb"]
    o = np.zeros(len(P), F32)
    kk = 1.0 if m else .7
    for f, ch in Hd["fingers"].items():
        J = [Vector(j) for j in ch["joints"]]
        w = ch["width"] / 2
        d0 = (J[1] - J[0]).normalized()
        # the knuckle (the joint lies behind the web, in the hand's back), a tendon back to the wrist; the two finger
        # joints: a low knot on top, a crease underneath
        kn = J[0] - a * (.015 * Hd["scale"]) + dor * (T["palm"]["t"] * .40)
        o += bump(P, kn, (w * 1.15, w * .8, w * 1.0), .0024 * kk)
        o += line(P, [V(A["W"] + a * .02 + dor * T["palm"]["t"] * .5 + (J[0] - A["W"] - a * (J[0] - A["W"]).dot(a)) * .35), V(kn)],
                  .0036, .0006 * kk, .25)
        for i in (1, 2):
            o += bump(P, J[i] + dor * w * .82, (w * .8, w * .55, w * .9), .0006 * kk)
            o += bump(P, J[i] - dor * w * .8, (w * .30, w * .5, w * .75), -.0008)
            di = (J[i + 1] - J[i]).normalized()
            o += bump(P, J[i] + di * ((J[i + 1] - J[i]).length * .5) - dor * w * .8, (w * 1.0, w * .5, w * .8), .0005)     # the pad of each phalanx
        # the nail: a flat bed sunk into the fingertip's back, its free edge and side walls standing
        dn = (J[3] - J[2]).normalized()
        c = J[2] + dn * ((J[3] - J[2]).length * .58) + dor * w * .78
        side = dn.cross(dor).normalized()
        Rn = np.array([dn, dor, side], F32)
        o += bump(P, c, (w * .62, w * .32, w * .62), -.0011, Rn)
        o += bump(P, c - dn * w * .62, (w * .16, w * .3, w * .7), .0007, Rn)                 # the cuticle's fold
    tc = Hd["thumb"]
    J = [Vector(j) for j in tc["joints"]]
    w = tc["width"] / 2
    dn = (J[3] - J[2]).normalized()
    up = (dor - dn * dor.dot(dn)).normalized()
    for i in (1, 2):
        o += bump(P, J[i] + up * w * .8, (w * .8, w * .6, w * .9), .0006 * kk)
    return o


def leg(B, P):
    T, L, m = B.T, B.leg, B.m
    k = 1.0 if m else .4
    Hj, K, An = L["H"], L["K"], L["A"]
    th, ca = T["thigh"], T["calf"]
    lerp = lambda a, b, t: a + (b - a) * t
    o = np.zeros(len(P), F32)
    X = lambda x, y, z: Vector((x, y, z))
    # thigh: rectus femoris down the front, the outer sweep of vastus lateralis and the band along it, the long
    # furrow of sartorius from the hip bone to the inside of the knee
    o += bump(P, lerp(Hj, K, .45) + X(.004, -th["d"] * .43, 0), (.032, .03, .13), .0036 * k)
    o += bump(P, lerp(Hj, K, .56) + X(th["w"] * .41, -.02, 0), (.03, .05, .12), .0036 * k)
    o += line(P, [V(Hj + X(th["w"] * .5, .012, -.09)), V(K + X(.046, .004, .07))], .012, -.002 * k, .15)
    o += line(P, [V(Hj + X(.03, -th["d"] * .40, .0)), V(lerp(Hj, K, .5) + X(-.04, -th["d"] * .30, 0)), V(K + X(-.044, -.012, .09))], .012, -.0026 * k, .12)
    o += bump(P, lerp(Hj, K, .4) + X(-th["w"] * .30, .0, 0), (.03, .05, .11), .0026 * k)                 # adductors
    o += line(P, [V(lerp(Hj, K, .25) + X(.0, th["d"] * .46, 0)), V(lerp(Hj, K, .8) + X(.004, th["d"] * .36, 0))], .011, -.0022 * k, .2)   # between the hamstrings
    # knee: the cap, the tendon down to the shin bone, the hollows either side of it; behind: two tendons, a hollow
    o += bump(P, K + X(0, -.05, .014), (.02, .011, .024), .003)
    o += line(P, [V(K + X(0, -.05, -.012)), V(K + X(.002, -.046, -.058))], .009, .003, .15)
    for sx in (.034, -.032):
        o += bump(P, K + X(sx, -.036, -.002), (.012, .012, .02), -.003)
    for sx in (.03, -.03):
        o += line(P, [V(K + X(sx, .034, .055)), V(K + X(sx * 1.1, .03, -.012))], .009, .0028 * (1 if m else .7), .15)
    o += bump(P, K + X(0, .04, .012), (.018, .014, .03), -.0036)
    # calf: the two heads of gastrocnemius (the inner lower and fuller), the furrow between them, the heel cord with
    # a hollow either side, the shin's crest and the muscle beside it
    o += bump(P, lerp(K, An, .27) + X(-.024, .048, 0), (.026, .028, .075), .0046 * (1 if m else .6))
    o += bump(P, lerp(K, An, .23) + X(.022, .05, 0), (.024, .026, .065), .0038 * (1 if m else .6))
    o += line(P, [V(lerp(K, An, .1) + X(0, .058, 0)), V(lerp(K, An, .42) + X(0, .052, 0))], .008, -.0024 * k, .15)
    o += line(P, [V(lerp(K, An, .72) + X(0, .036, 0)), V(An + X(0, .04, .018))], .008, .0036, .2)
    for sx in (.02, -.02):
        o += bump(P, An + X(sx, .022, .036), (.011, .013, .03), -.0036)
    o += line(P, [V(K + X(-.004, -.04, -.075)), V(An + X(-.004, -.028, .05))], .008, .0022, .15)
    o += bump(P, lerp(K, An, .3) + X(.02, -.03, 0), (.016, .016, .085), .0028 * k)
    return o


def foot(B, P):
    F = B.foot
    o = np.zeros(len(P), F32)
    X = lambda x, y, z: Vector((x, y, z))
    for t in F["toes"]:
        r = t["width"] / 2
        tip = t["base"] + t["dir"] * t["len"]
        c = tip - t["dir"] * r * 1.0 + X(0, 0, r * 1.55 - tip.z)
        side = t["dir"].cross(Vector((0, 0, 1))).normalized()
        Rn = np.array([t["dir"], Vector((0, 0, 1)), side], F32)
        o += bump(P, c, (r * .6, r * .3, r * .62), -.001, Rn)                       # the nail
        o += bump(P, t["base"] + t["dir"] * (t["len"] * .35) + X(0, 0, r * 1.5), (r * .7, r * .6, r * .5), .001)   # the toe's knuckle
    # the tendons fanning to the toes over the instep
    an = F["ankle"]
    for t in F["toes"][:4]:
        o += line(P, [V(an + X(0, -.03, -.012)), V(t["base"] + X(0, .02, .03))], .005, .0011, .3)
    return o


def head(B, P):
    """the face and neck: lips with their bow and pillows, the philtrum, the fold from the nose's wing past the mouth,
    the wing's crease, the lid crease and the hollow under the eye, the hollows of the cheek and temple (his), the
    shadow under the jaw's border"""
    from headshape import Y0
    T, m = B.T, B.m
    g = B.head_geometry()
    hs, X = g["hs"], g["X"]
    f = 1.0 if m else .15                                       # how hard the face is cut (hers: soft and round)
    yr = (P[:, 1] - Y0) / hs
    front = sstep(-.018, -.045, yr)
    Q = xz(P)
    q = lambda x, z: (X(x, 0, z).x, X(x, 0, z).z)               # a point of the front view
    o = np.zeros(len(P), F32)
    st = g["stomion"]; mw = g["mouth_w"] / hs
    zs = .050
    # mouth: the parting, the corners, the upper lip's bow (a tubercle and two wings), the lower lip's two pillows,
    # the fold under it, the philtrum between two columns
    full = 1.0 if m else 1.5
    o += line(Q, [q(0, zs), q(mw * .5, zs - .0004)], .0019 * hs, -.0020, 0) * front
    o += bump(Q, q(mw * .5 + .0025, zs - .0006), (.0042 * hs, .0042 * hs), -.0022) * front
    o += bump(Q, q(0, zs + .0038), (.0050 * hs, .0026 * hs), .0012 * full) * front
    o += bump(Q, q(.0105, zs + .0046), (.0070 * hs, .0028 * hs), .0011 * full) * front
    o += bump(Q, q(.0085, zs - .0052), (.0085 * hs, .0034 * hs), .0016 * full) * front
    o += line(Q, [q(0, zs - .0135), q(.013, zs - .0125)], .0060 * hs, -.0005 * (1 if m else .8), 0) * front
    o += line(Q, [q(0, zs + .0075), q(0, .0695)], .0030 * hs, -.0014, .15) * front
    o += line(Q, [q(.0046, zs + .0078), q(.0040, .0695)], .0016 * hs, .0007, .15) * front
    # nose: the planes either side of the bridge, the crease round the wing, the fold running down from it
    o += bump(Q, q(.0125, .106), (.0055 * hs, .013 * hs), -.0011) * front
    nk = (1.08 if m else .74)
    sub = g["subnasale"]
    o += line(P, [V(sub + Vector((.0125 * nk, .0030, .0128))), V(sub + Vector((.0195 * nk, .0075, .0090))), V(sub + Vector((.0200 * nk, .0100, .0015)))],
              .0026, -.0014, .1)
    o += line(Q, [q(.0185 * nk + .002, .0775), q(.0265, .064), q(.0290, .054)], .0060 * hs, -.0006 * f, .3) * front   # (it ends by the mouth's corner: carried on down it is an old man's line)
    # (the lids are left to the lid shell in headshape: a furrow cut this close to the pinned lid margin folds it)
    ex = g["eye_c"].x / hs
    ez = (g["eye_c"].z - g["chin"]) / hs
    ez = ez if m else g["zf"](ez)                                # (q() maps heights through her shorter lower face)
    eq = lambda dx, dz: (g["eye_c"].x + dx * hs, g["eye_c"].z + dz * hs)
    # the planes of the face: the hollow under the cheekbone, the temple, the shadow under the jaw's border
    o += bump(P, X(.050, -.052, .078), (.012 * hs, .018 * hs, .016 * hs), -.0007 * f)
    o += bump(P, X(.060, -.046, .142), (.010 * hs, .022 * hs, .020 * hs), -.0018 * f)
    go = g["gonion"]
    o += line(P, [V(go + Vector((-.008, .0, -.014))), V(X(.030, -.040, .004)), V(X(.010, -.062, -.004))], .013, -.0007 * (1 if m else .6), .25)
    if m:
        o += line(Q, [q(0, .006), q(0, .021)], .0032 * hs, -.0007, .2) * front               # the chin's faint cleft
    # the hollow above the breastbone between the neck's two cords
    nb = T["neck_base_z"]
    o += bump(P, Vector((0, -T["neck_d"] * .40, nb + .018)), (.014, .014, .022), -.0022)
    return o


def relief(B, P):
    """the whole body's relief at P (already mirrored to the left)"""
    gain = GAIN_MALE if B.m else GAIN_FEMALE
    return (torso(B, P) + arm(B, P) + leg(B, P)) * gain + hand(B, P) + foot(B, P) + head(B, P)
