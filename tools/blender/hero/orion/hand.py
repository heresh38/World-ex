"""The hand (Project Orion male): its own all-quad cage grafted onto the arm's wrist ring, 20 cm from the wrist to
the middle fingertip (the owner, 2026-11-16: "make the hands slightly larger"), palm down, thumb forward, relaxed.

Topology (cage, one hand):
  * the wrist ring (12, from the arm: dorsal 6 from the little-finger side to the thumb side, palmar 6 back) widens
    in one band to the palm's ring of 28 (dorsal 14, palmar 14): each of 8 wrist segments becomes three (a 1-to-3
    quad pattern, two vertices inside it), the sides stay one;
  * five palm rings of 28 to the knuckles; the thumb leaves through a window of 8 on the palm's thumb side (two
    rings long, from the back of the hand's edge round to the palm), each finger from three of the 13 segments
    across the knuckles (rings of 8: four on the back, four on the palm), the segment beyond the little finger
    stays the palm's own end, the web between two fingers is the edge they share;
  * each digit runs in rings of 8 through its joints to a 2 x 2 cap at the tip.
Every vertex is given a target: rings round the palm's section, round each finger's bones in their relaxed curl;
the cage is solved with the body's so its limit surface passes through them. Knuckles, pads, creases and nails are
laid over the subdivided hand (detail()).
"""
import math
import numpy as np

HAND_LEN = 0.200
# each finger: its knuckle along the hand from the wrist, across it (+ toward the thumb), its length from the
# knuckle to the tip, its width at the base, its spread (deg, + toward the thumb)
FINGERS = [("little", .089, -.0359, .076, .0200, -17.0),
           ("ring", .097, -.0132, .093, .0216, -10.6),
           ("middle", .101, .0102, .098, .0221, 0.0),
           ("index", .098, .0355, .089, .0225, 6.1)]
# (the owner's hand references, 2026-11-17, laid under ours at the same scale (the wrist's crease to the middle
# fingertip 20 cm) and measured: where each finger's root and tip are, its fan, its width along it (2.0-2.25 cm at
# the root, 1.8 near the tip: they keep their width to a broad rounded tip); the outline of ours drawn over theirs
# showed the knuckles crowded toward the middle, the fan too narrow, and fingers 1 cm too wide: the body's 4.9 mm
# of skin, now faded out over the hand (lab.py))
PHAL = (.46, .30, .24)                 # the phalanges' shares of a finger's length
CURL = (4.0, 8.0, 5.0)                 # the bend at the knuckle, the middle joint, the last (deg): open, as the references
PALM_X = [.024, .038, .051, .064, .077]          # the palm's rings along the hand (the knuckle ring follows them)
PALM_W = [.0335, .0395, .0435, .0455, .0465]     # its half width there
# the edge on the little finger's side, straight from the wrist to the little finger's root as the references' (ours
# came in at the wrist and bulged at the middle of the palm), and the thumb's side before the thumb flares it (m)
PALM_U = [-.0417, -.0442, -.0454, -.0462]
PALM_R = [.0321, .0378, .0416, .0435]
# the thumb's side: the references' thumb leaves from the wrist, its outer edge one line from the wrist's side to its
# tip (about 40 degrees out), the mound of the thenar under it: the last three columns of the first four rings go
# out to it (m across the hand, columns 13, 12 and the share of that carried by column 11)
THENAR = [(.059, .049, .25), (.063, .056, .35), (.060, .052, .30), (.053, .047, .20)]
WINDOW_RINGS = (1, 2, 3)          # the palm's rings the thumb leaves through
# the window itself is laid as a ring square to the thumb's own axis, round its metacarpal (the thenar): along it from
# its base, its half widths in the hand's plane and across it (m), each loop vertex's angle (deg: 0 outward, 90 the
# back). Laid along the palm's edge, the window's far end stood level with the thumb's first ring 41 degrees off it,
# and the skin between folded back on itself there (the pinch at the thumb's root)
WIN_ALONG, WIN_RW, WIN_RN, WIN_RD = .036, .013, .0115, .0150   # ... and up toward the back: the hand's back runs on
# down onto the thumb's (a top level with the thumb's left a dent between the two)
WIN_ANG = (45, 0, -45, -90, -135, 180, 135, 90)
# ... tilted: its side toward the index further up the thumb than its outer side (m either way), as the web's skin
# climbs the thumb's inner edge (square to the thumb, the web lay 1 cm under the references')
WIN_TILT = .008
THUMB_SOFT = (1.0, 1.0, .5)       # how loosely the cage holds the window, the ring after it, the palm round it
# the knuckle ring's columns under the fingers: the little finger takes columns 0-3 (its outer side runs on from the
# palm's edge: one column beyond it made a shelf there), the ring 4-7, the middle 7-10, the index 10-13; columns 3-4
# are the web between the little and the ring finger
KNUCKLE_Y = [(1.5, -.0359), (5.5, -.0132), (8.5, .0102), (11.5, .0355)]
FINGER_COL = (0, 4, 7, 10)
# the webs between the fingers (the knuckle ring's columns 3, 4, 7, 10): how much further out on the back and on the
# palm, how much lower on the back and higher on the palm (m), and how loosely the cage holds them (solve_cage's
# free: an exact fit pinched each web into a sharp V; the references' are a soft U)
WEB_COLS = (3, 4, 7, 10)
WEB = (.004, .010, .003, .004, .6)


def unit(v):
    v = np.asarray(v, float)
    return v / max(float(np.linalg.norm(v)), 1e-12)


def rot(v, axis, deg):
    """v turned about axis by deg (Rodrigues)"""
    a = unit(axis)
    t = math.radians(deg)
    return v * math.cos(t) + np.cross(a, v) * math.sin(t) + a * float(a @ v) * (1 - math.cos(t))


class Frame:
    """the hand's frame at the wrist joint: along it, across it toward the thumb, out of its back"""

    def __init__(self, W, a, up, sx):
        self.W, self.ax, self.az = np.asarray(W, float), unit(a), unit(up)
        self.ay = np.array([0.0, -1.0, 0.0])          # the thumb's side is forward on both hands
        self.sx = sx

    def p(self, x, y, z):
        return self.W + self.ax * x + self.ay * y + self.az * z


def column_y(i, wscale=1.0):
    """across the hand (m) of the knuckle ring's column i (0 = beyond the little finger .. 13 = the thumb's side)"""
    xs = [0.0] + [k for k, _ in KNUCKLE_Y] + [13.0]
    ys = [-.0461] + [v for _, v in KNUCKLE_Y] + [.0445]
    return float(np.interp(i, xs, ys)) * wscale


def palm_z(y, x, dorsal):
    """the back of the hand (dorsal) and the palm's face: the metacarpals' arch on the back, on the palm the thenar
    mound by the thumb, the hypothenar along the little finger's edge, the pads under the knuckles; near the wrist
    the section is still the wrist's oval (thicker), flattening over the palm's first rings"""
    yn = max(-1.0, min(1.0, y / .047))
    round_ = max(0.0, 1 - (x - .02) / .035)                       # 1 at the wrist end, 0 from the palm's middle
    if dorsal:
        return .0105 + .0030 * (1 - yn * yn) - .0015 * max(0.0, (x - .07) / .03) + .0060 * round_ * (1 - yn * yn)
    z = -.0135 - .0025 * (1 - yn * yn)
    # the thenar: under the thumb's metacarpal from the wrist, so the mound runs on into the thumb (behind it and
    # further in, a valley lay between them: a notch at the thumb's root)
    z -= .0085 * math.exp(-((y - .046) / .016) ** 2) * math.exp(-((x - .036) / .022) ** 2)      # thenar
    z -= .0045 * math.exp(-((y + .036) / .012) ** 2) * math.exp(-((x - .045) / .035) ** 2)      # hypothenar
    z -= .0030 * math.exp(-((x - .095) / .012) ** 2)                                             # the pads
    return z


def build_hand(C, wrist, frame, log=print):
    """adds one hand to the cage C on the arm's wrist ring (12 vertex indices, in the arm's ring order)"""
    F = frame
    sx = F.sx
    w = list(wrist)
    # the wrist ring: dorsal from the little finger's side to the thumb's j5..j10, the thumb's side j10-j11,
    # palmar back j11, j0..j4, the little finger's side j4-j5
    dors_w = [w[5], w[6], w[7], w[8], w[9], w[10]]
    palm_w = [w[11], w[0], w[1], w[2], w[3], w[4]]                    # thumb's side -> little finger's side

    def ring28(x, wv, last=False, k=0):
        D, P = [], []
        c0, c13 = column_y(0), column_y(13)
        for i in range(14):
            if last:
                y = column_y(i)
            else:                                                      # between this ring's own two edges
                f = lambda j: PALM_U[k] + (PALM_R[k] - PALM_U[k]) * (column_y(j) - c0) / (c13 - c0)
                y = f(i)
                t13, t12, s11 = THENAR[k]
                if i == 13:
                    y = t13
                elif i == 12:
                    y = t12
                elif i == 11:
                    y = y + s11 * (t12 - f(12))
            xx = x
            web = last and i in WEB_COLS
            if last:                                                   # the knuckle ring follows the knuckles' line
                xx = float(np.interp(y, [f[2] for f in FINGERS], [f[1] for f in FINGERS])) - .006
            edge = i in (0, 13)
            # the thumb's window sits a little lower on the side (round the thumb's own axis, under the palm's
            # middle plane)
            zd = palm_z(y, xx, True) - ((.009 if (i == 13 and k in WINDOW_RINGS and not last) else .006) if edge else 0)
            zp = palm_z(y, xx, False) + (.005 if edge else 0)
            if web:
                zd, zp = zd - WEB[2], zp + WEB[3]
            D.append(C.add(F.p(xx + (WEB[0] if web else 0), y, zd), "hand"))
            P.append(C.add(F.p(xx + (WEB[1] if web else 0), y, zp), "hand"))
            if web:
                C.soft[D[-1]] = C.soft[P[-1]] = WEB[4]
        return D, P

    rings = [ring28(x, wv, k == len(PALM_X) - 1, k) for k, (x, wv) in enumerate(zip(PALM_X, PALM_W))]
    # the first band: wrist (12) -> palm (28)
    D0, P0 = rings[0]

    def plain(a, b, c, d):
        C.quad(a, b, d, c)                                            # a-b below, c-d above (c over a)

    def triple(a, b, top):
        c, d, e, f = top
        pa, pb = C.V[a], C.V[b]
        m1 = C.add(.5 * (pa + (pb - pa) / 3) + .5 * C.V[d], "hand")
        m2 = C.add(.5 * (pa + (pb - pa) * 2 / 3) + .5 * C.V[e], "hand")
        C.quad(a, m1, d, c); C.quad(m1, m2, e, d); C.quad(m2, b, f, e); C.quad(a, b, m2, m1)

    # dorsal: the first wrist segment plain, the other four each to three
    plain(dors_w[0], dors_w[1], D0[0], D0[1])
    for k in range(1, 5):
        triple(dors_w[k], dors_w[k + 1], D0[3 * k - 2: 3 * k + 2])
    plain(dors_w[5], palm_w[0], D0[13], P0[13])                       # the thumb's side
    # palmar (thumb's side -> little finger's side): four to three, the last plain
    for k in range(4):
        triple(palm_w[k], palm_w[k + 1], P0[13 - 3 * k: 9 - 3 * k: -1])
    plain(palm_w[4], palm_w[5], P0[1], P0[0])
    plain(palm_w[5], dors_w[0], P0[0], D0[0])                         # the little finger's side
    # the palm's bands, the thumb's window cut from rings 0..2 on the thumb's side (segments D13-P13, P13-P12)
    ring_order = lambda R: R[0] + R[1][::-1]                           # D0..D13, P13..P0
    w0 = WINDOW_RINGS[0]
    window = {(w0, 13), (w0, 14), (w0 + 1, 13), (w0 + 1, 14)}         # (band, segment index in ring order)
    for b in range(len(rings) - 1):
        r0, r1 = ring_order(rings[b]), ring_order(rings[b + 1])
        n = len(r0)
        for j in range(n):
            if (b, j) in window:
                continue
            k = (j + 1) % n
            C.quad(r0[j], r0[k], r1[k], r1[j])
    # the window's loop (8), the vertex inside it goes
    R1, R2, R3 = rings[w0], rings[w0 + 1], rings[w0 + 2]
    loop = [R1[0][13], R1[1][13], R1[1][12], R2[1][12], R3[1][12], R3[1][13], R3[0][13], R2[0][13]]
    inner = R2[1][13]
    C.V[inner] = C.V[R2[0][13]]                                      # (left unused: removed below)
    tj0 = thumb_joints(F)
    u = unit(tj0[1] - tj0[0])
    ux, uy = float(u @ F.ax), float(u @ F.ay)
    w_out = unit(-uy * F.ax + ux * F.ay)                              # outward, in the hand's plane, square to it
    n_up = unit(F.az - u * float(F.az @ u))
    A = tj0[0] + u * WIN_ALONG
    for v, ang in zip(loop, WIN_ANG):
        t = math.radians(ang)
        C.V[v] = A - u * (WIN_TILT * math.cos(t)) + w_out * (WIN_RW * math.cos(t)) + n_up * ((WIN_RD if t > 0 else WIN_RN) * math.sin(t))
    C.dead = getattr(C, "dead", set()) | {inner}
    # the fingers from the knuckle ring, the end beyond the little finger the palm's own
    D5, P5 = rings[-1]
    C.quad(D5[3], D5[4], P5[4], P5[3])                               # the web between the little and the ring finger
    for f, (name, kx, ky, L, wd, spread) in enumerate(FINGERS):
        i = FINGER_COL[f]
        base = [D5[i], D5[i + 1], D5[i + 2], D5[i + 3], P5[i + 3], P5[i + 2], P5[i + 1], P5[i]]
        digit(C, F, base, joints_of(F, kx, ky, L, spread), wd, f"finger_{name}")
    # the thumb
    tj = thumb_joints(F)
    # the window, its ring and the palm round it are held loosely (an exact fit through the window drew a cuff
    # round the thumb's root): the surface rounds over them as the thenar runs into the thumb
    for v in loop:
        C.soft[v] = max(C.soft.get(v, 0.0), THUMB_SOFT[0])
    lset = set(loop)
    for f in C.F:
        if lset & set(f):
            for v in f:
                if v not in lset and C.part[v] == "hand":
                    C.soft[v] = max(C.soft.get(v, 0.0), THUMB_SOFT[2])
    digit(C, F, loop, tj, .0215, "thumb", thumb=True)
    log(f"hand: {'left' if sx > 0 else 'right'}")


def joints_of(F, kx, ky, L, spread):
    """a finger's knuckle, middle joint, last joint and tip in its relaxed curl"""
    # fanned toward the thumb by `spread`: about (along x toward the thumb), the same on both hands (about the
    # hand's up axis the left hand's fan ran backward and its fingers closed into one paddle)
    d = rot(F.ax, np.cross(F.ax, F.ay), spread)
    side = unit(np.cross(d, F.az))                                   # the bend's axis
    p = F.p(kx, ky, -.002)
    out = [p]
    for k, (share, bend) in enumerate(zip(PHAL, CURL)):
        d = rot(d, side, -bend)
        p = p + d * L * share
        out.append(p)
    return out


def thumb_joints(F):
    """the thumb's joints (its base in the wrist's side, its first joint, the last, the tip), measured on the
    references laid under ours: it leaves low by the wrist and opens about 40 degrees from the index, in the palm's
    plane and a little under it (it lay along the index, 1.5 cm in and 1 cm high: a tube out of the palm's side)"""
    c = F.p(.020, .040, -.010)
    mcp = F.p(.0525, .0685, -.016)
    ip = F.p(.0805, .0820, -.020)
    tip = F.p(.1010, .0895, -.0225)
    return [c, mcp, ip, tip]


def digit(C, F, base, J, wd, part, thumb=False):
    """rings of 8 from the base ring through the joints to a cap at the tip. Each ring's vertices keep the base
    ring's angles round the digit (no twist), easing to the digit's own oval past its first ring."""
    base = list(base)
    b_pts = np.array([C.V[v] for v in base])
    centre0 = b_pts.mean(0)
    seg = [(J[k], J[k + 1]) for k in range(len(J) - 1)]
    def frame_at(ax):
        upv = F.az if not thumb else (F.ay + .6 * F.az)
        up = unit(upv - ax * float(upv @ ax))
        sidev = F.ay if not thumb else (F.ay - F.az)
        side = unit(sidev - ax * float(sidev @ ax) - up * float(sidev @ up))
        return up, side

    axis0 = unit(J[1] - J[0])
    up0, side0 = frame_at(axis0)
    ang0 = np.unwrap([math.atan2(float((p - centre0) @ up0), float((p - centre0) @ side0)) for p in b_pts])
    step = math.copysign(math.pi / 4, ang0[1] - ang0[0])
    start = math.atan2(sum(math.sin(a - step * j) for j, a in enumerate(ang0)),
                       sum(math.cos(a - step * j) for j, a in enumerate(ang0)))
    canon = [start + step * j for j in range(8)]
    ang0 = [canon[j] + math.remainder(ang0[j] - canon[j], 2 * math.pi) for j in range(8)]
    # rings: (bone, share along it, width scale, ease to the oval)
    if thumb:
        # its mound at the root, the first bone narrower, the joint, then the wide flat pad
        # out of a broad mound (a narrow root made a neck: a sausage stuck on), the first bone, the joint, the wide
        # flat pad the references show
        plan = [(1, .22, 1.04, .7), (1, .62, .99, 1.0), (1, 1.0, .96, 1.0), (2, .5, .88, 1.0), (2, .88, .75, 1.0)]
    else:
        # the references' widths along the finger (at its root, the middle joint, the middle bone, the last joint,
        # the pad, by the tip): they hardly taper, to a broad rounded tip
        plan = [(0, .40, 1.0, .5), (0, 1.0, .96, 1.0), (1, .5, .90, 1.0), (1, 1.0, .87, 1.0), (2, .5, .83, 1.0),
                (2, .86, .73, 1.0)]
    # a finger's depth against its width falls toward the tip (the last bone is flat under its nail)
    depth = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0] if thumb else [1.0, .97, .95, .93, .90, .87]
    prev = base
    rings = [base]
    for (bone, share, ws, ease), dz in zip(plan, depth):
        a, b = seg[bone]
        c = a + (b - a) * share
        ax = unit(b - a)
        up, side = frame_at(ax)
        r = wd * ws / 2
        ring = []
        for j in range(8):
            t = ang0[j] * (1 - ease) + canon[j] * ease
            # the back of a digit is rounder, its pad fuller; a little wider than it is deep
            # flatter on the back, the pad fuller; a little square at the sides (round, a ring of 8 subdivides to
            # a sausage)
            ry, rz = r, r * (.76 if math.sin(t) > 0 else .90) * dz
            ct, st = math.cos(t), math.sin(t)
            sq = lambda v: math.copysign(abs(v) ** .85, v)
            p = c + side * (ry * sq(ct)) + up * (rz * sq(st))
            ring.append(C.add(p, part))
        rings.append(ring)
    if thumb:
        # the thumb out of the palm's side over two strips, not one: a ring halfway between the window's edge (on
        # the palm) and its first ring (round it), so the root flares out of the thenar (one strip pinched it to a
        # neck, or, wider, ballooned it into a knob)
        mid = [C.add(.5 * (C.V[a] + C.V[b]), part) for a, b in zip(rings[0], rings[1])]
        for v in mid:
            C.soft[v] = THUMB_SOFT[1]
        rings.insert(1, mid)
    for r0, r1 in zip(rings, rings[1:]):
        C.strip(r0, r1)
    tip_dir = unit(seg[-1][1] - seg[-1][0])
    C.cap(rings[-1], part, wd * .30, tip_dir)


TENDON = (.0004, .0006, .0008, .0008)       # the extensor tendons' ridge on the back (m): little, ring, middle, index
NAIL_W, THUMB_NAIL_W = .30, .0072            # a nail's half width: a share of its finger's, the thumb's (m)
# the veins on the back of the hand (cm in the hand's frame: along it from the wrist, across toward the thumb): the
# arch, the veins from the webs into it, its two ends running up the thumb's side and the little finger's side, one
# up the middle; how high they stand and how wide (m)
VEINS = [[(8.0, -3.7), (6.8, -2.0), (6.1, 0.2), (6.3, 2.2), (7.0, 3.7)],
         [(9.6, 2.3), (7.6, 2.4), (6.4, 2.1)], [(9.9, -0.1), (8.0, 0.0), (6.2, 0.3)], [(9.3, -2.6), (7.6, -2.5), (6.9, -2.2)],
         [(7.0, 3.7), (5.0, 3.6), (2.6, 3.1), (0.0, 2.6)], [(8.0, -3.7), (5.2, -3.7), (2.4, -3.2), (0.0, -2.8)],
         [(6.1, 0.2), (4.0, 0.6), (2.0, 0.9), (0.0, 1.1)]]
VEIN_H, VEIN_W = .0007, .0017


def detail(P, frames, log=None):
    """knuckles, the pads and creases, the nails' plates over the subdivided hands (metres along the normal)"""
    out = np.zeros(len(P), np.float32)
    for F in frames:
        rel = P - F.W
        x, y, z = rel @ F.ax, rel @ F.ay, rel @ F.az
        near = (x > -.01) & (x < .23) & (np.abs(y) < .11) & (np.abs(z) < .06)    # (the thumb's tip is 9 cm out)
        if not near.any():
            continue
        dors = near & (z > .003)
        for f_i, (name, kx, ky, L, wd, spread) in enumerate(FINGERS):
            J = joints_of(F, kx, ky, L, spread)
            # the back of the hand as the references': each metacarpal's head a knuckle a little behind the joint,
            # a soft valley between two, and the extensor tendon running from it toward the wrist's middle (the
            # index's and the middle finger's the clearest, the little finger's faint)
            k0 = J[0] - F.W
            kxx, kyy = float(k0 @ F.ax), float(k0 @ F.ay)
            ax_, ay_ = kxx - .007, kyy
            bx_, by_ = .016, kyy * .35
            sx_, sy_ = bx_ - ax_, by_ - ay_
            t = np.clip(((x - ax_) * sx_ + (y - ay_) * sy_) / (sx_ * sx_ + sy_ * sy_), 0, 1)
            dd = np.hypot(x - (ax_ + sx_ * t), y - (ay_ + sy_ * t))
            fade = np.clip(t / .12, 0, 1) * np.clip((1 - t) / .45, 0, 1)
            out += TENDON[f_i] * np.exp(-(dd / .0028) ** 2) * fade * dors
            if f_i + 1 < len(FINGERS):                                  # the valley toward the next knuckle
                k1 = joints_of(F, *FINGERS[f_i + 1][1:4], FINGERS[f_i + 1][5])[0] - F.W
                mx, my = .5 * (kxx + float(k1 @ F.ax)) - .010, .5 * (kyy + float(k1 @ F.ay))
                out -= .0007 * np.exp(-((x - mx) / .012) ** 2 - ((y - my) / .0045) ** 2) * dors
            # a relaxed, open hand shows its knuckles only a little (2.6 mm lumps read as swellings)
            for k, (jp, amp, rad) in enumerate(((J[0] - F.ax * .003, .0022, .0095), (J[1], .0012, .007),
                                                (J[2], .0007, .0055))):
                q = P - jp
                dn = q @ F.az
                rr = np.sqrt(((q - np.outer(dn, F.az)) ** 2).sum(1))
                out += amp * np.exp(-(rr / rad) ** 2) * (dn > 0) * near                   # knuckles on the back
                out -= .0007 * np.exp(-(rr / (rad * .5)) ** 2) * (dn < 0) * near           # creases on the palm
            out += nail(P, J[2], J[3], F.az, NAIL_W * wd, near)
        tj = thumb_joints(F)
        out += nail(P, tj[2], tj[3], F.ay + .6 * F.az, THUMB_NAIL_W, near)
        # the veins on the back of the hand (the references': the dorsal venous arch across the metacarpals, fed from
        # the webs, draining up the thumb's side and the little finger's side toward the wrist), low and soft
        dors = near & (z > .003)
        for line in VEINS:
            V_ = np.array(line, float) / 100
            best = np.full(len(P), 1e3); tt = np.zeros(len(P))
            seg_len = np.hypot(*np.diff(V_, axis=0).T)
            acc = np.r_[0, np.cumsum(seg_len)]
            for i in range(len(V_) - 1):
                (x0, y0), (x1, y1) = V_[i], V_[i + 1]
                sx_, sy_ = x1 - x0, y1 - y0
                ti = np.clip(((x - x0) * sx_ + (y - y0) * sy_) / (sx_ * sx_ + sy_ * sy_), 0, 1)
                di = np.hypot(x - (x0 + sx_ * ti), y - (y0 + sy_ * ti))
                m = di < best
                best = np.where(m, di, best); tt = np.where(m, (acc[i] + ti * seg_len[i]) / acc[-1], tt)
            ends = np.clip(tt / .12, 0, 1) * np.clip((1 - tt) / .12, 0, 1)
            wrist = np.clip((x - .004) / .02, 0, 1)                      # gone into the wrist
            out += VEIN_H * np.exp(-(best / VEIN_W) ** 2) * ends * wrist * dors
    return out


def nail(P, a, b, up_hint, hw, near):
    """a nail on the last bone from a (its joint) to b (its tip), as the references' sculpted fingers: a smooth plate
    two thirds of the bone long and about three quarters of the finger wide (the first one spanned the whole width),
    its root a curve (the cuticle, the corners further out), a groove all round it, the skin's folds standing just
    outside it along the sides and the root (none at the free edge)"""
    d = unit(b - a)
    L = float(np.linalg.norm(b - a))
    q = P - a
    t = (q @ d) / L
    up = unit(up_hint - d * float(up_hint @ d))
    side = unit(np.cross(d, up))
    u = (q @ side) / hw
    back = (q @ up > 0) & near & (t > -.2) & (t < 1.3)
    sd_side = (np.abs(u) - 1) * hw
    sd_root = (.30 + .08 * u * u - t) * L
    sd_tip = (t - 1.03) * L
    sd = np.maximum(np.maximum(sd_side, sd_root), sd_tip)          # signed distance to the nail's outline (m)
    plate = np.clip(-sd / .0009, 0, 1)
    plate = plate * plate * (3 - 2 * plate)
    groove = np.exp(-((sd - .0001) / .0006) ** 2)
    fold = np.exp(-((sd - .0014) / .0007) ** 2) * (sd > 0) * (sd_tip < np.maximum(sd_side, sd_root))
    # (a 1 mm mesh: the groove a hair narrower than an edge left the nail a faint line)
    return (.0007 * plate - .0006 * groove + .0003 * fold) * back


def smooth_root(P, edges, frames, iters=40, radius=.032):
    """the thumb's root on the subdivided skin, smoothed without shrinking it (Taubin: a step in, a step out),
    fading out within `radius` of the window's middle: what the window's ring leaves there (a soft cuff round the
    thumb, a dent on its back by the root) is rounded off as skin rounds over the thenar into the thumb"""
    P = np.asarray(P, np.float64).copy()
    n = len(P)
    e0, e1 = edges[:, 0], edges[:, 1]
    deg = np.maximum(np.bincount(e0, minlength=n) + np.bincount(e1, minlength=n), 1).astype(np.float64)
    wgt = np.zeros(n)
    for F in frames:
        tj = thumb_joints(F)
        u = unit(tj[1] - tj[0])
        A = tj[0] + u * WIN_ALONG
        d = np.linalg.norm(P - A, axis=1)
        t = np.clip(1 - d / radius, 0, 1)
        wgt = np.maximum(wgt, t * t * (3 - 2 * t))
    on = np.flatnonzero(wgt > 0)
    if not len(on):
        return P
    w = wgt[:, None]
    for _ in range(iters):
        for lam in (.5, -.53):
            acc = np.zeros_like(P)
            for c in range(3):
                acc[:, c] = (np.bincount(e0, weights=P[e1, c], minlength=n) +
                             np.bincount(e1, weights=P[e0, c], minlength=n))
            P += lam * w * (acc / deg[:, None] - P)
    return P
