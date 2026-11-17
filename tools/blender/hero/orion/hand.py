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
FINGERS = [("little", .097, -.031, .068, .0188, -10.0),
           ("ring", .105, -.011, .085, .0210, -3.5),
           ("middle", .109, .011, .091, .0222, 0.0),
           ("index", .106, .033, .083, .0216, 5.0)]
PHAL = (.46, .30, .24)                 # the phalanges' shares of a finger's length
CURL = (10.0, 18.0, 11.0)              # the relaxed bend at the knuckle, the middle joint, the last (deg)
PALM_X = [.015, .032, .050, .068, .086]          # the palm's rings along the hand (the knuckle ring follows them)
PALM_W = [.034, .040, .0435, .0455, .0465]       # its half width there
KNUCKLE_Y = [(2.5, -.031), (5.5, -.011), (8.5, .011), (11.5, .033)]   # the knuckle ring's columns under the fingers


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
    ys = [-.0485] + [v for _, v in KNUCKLE_Y] + [.0445]
    return float(np.interp(i, xs, ys)) * wscale


def palm_z(y, x, dorsal):
    """the back of the hand (dorsal) and the palm's face: the metacarpals' arch on the back, on the palm the thenar
    mound by the thumb, the hypothenar along the little finger's edge, the pads under the knuckles"""
    yn = y / .047
    if dorsal:
        return .0105 + .0030 * (1 - yn * yn) - .0015 * max(0.0, (x - .07) / .03)
    z = -.0135 - .0025 * (1 - yn * yn)
    z -= .0070 * math.exp(-((y - .030) / .014) ** 2) * math.exp(-((x - .030) / .022) ** 2)      # thenar
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

    def ring28(x, wv, last=False):
        D, P = [], []
        for i in range(14):
            y = column_y(i, wv / .0465)
            xx = x
            if last:                                                   # the knuckle ring follows the knuckles' line
                xx = float(np.interp(y, [f[2] for f in FINGERS], [f[1] for f in FINGERS])) - .006
            edge = i in (0, 13)
            zd = palm_z(y, xx, True) - (.006 if edge else 0)
            zp = palm_z(y, xx, False) + (.005 if edge else 0)
            D.append(C.add(F.p(xx, y, zd), "hand"))
            P.append(C.add(F.p(xx, y, zp), "hand"))
        return D, P

    rings = [ring28(x, wv, k == len(PALM_X) - 1) for k, (x, wv) in enumerate(zip(PALM_X, PALM_W))]
    # the first band: wrist (12) -> palm (28)
    D0, P0 = rings[0]

    def plain(a, b, c, d):
        C.quad(a, b, d, c)                                            # a-b below, c-d above (c over a)

    def triple(a, b, top):
        c, d, e, f = top
        pa, pb = C.V[a], C.V[b]
        m1 = C.add(pa + (C.V[d] - pa) * .45 + (pb - pa) * .12, "hand")
        m2 = C.add(pb + (C.V[e] - pb) * .45 + (pa - pb) * .12, "hand")
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
    # the palm's bands, the thumb's window cut from rings 1..3 on the thumb's side (segments D13-P13, P13-P12)
    ring_order = lambda R: R[0] + R[1][::-1]                           # D0..D13, P13..P0
    window = {(1, 13), (1, 14), (2, 13), (2, 14)}                     # (band, segment index in ring order)
    for b in range(len(rings) - 1):
        r0, r1 = ring_order(rings[b]), ring_order(rings[b + 1])
        n = len(r0)
        for j in range(n):
            if (b, j) in window:
                continue
            k = (j + 1) % n
            C.quad(r0[j], r0[k], r1[k], r1[j])
    # the window's loop (8), the vertex inside it goes
    R1, R2, R3 = rings[1], rings[2], rings[3]
    loop = [R1[0][13], R1[1][13], R1[1][12], R2[1][12], R3[1][12], R3[1][13], R3[0][13], R2[0][13]]
    inner = R2[1][13]
    C.V[inner] = C.V[R2[0][13]]                                      # (left unused: removed below)
    C.dead = getattr(C, "dead", set()) | {inner}
    # the fingers from the knuckle ring, the end beyond the little finger the palm's own
    D5, P5 = rings[-1]
    C.quad(D5[0], D5[1], P5[1], P5[0])
    for f, (name, kx, ky, L, wd, spread) in enumerate(FINGERS):
        i = 1 + 3 * f
        base = [D5[i], D5[i + 1], D5[i + 2], D5[i + 3], P5[i + 3], P5[i + 2], P5[i + 1], P5[i]]
        digit(C, F, base, joints_of(F, kx, ky, L, spread), wd, f"finger_{name}")
    # the thumb
    tj = thumb_joints(F)
    digit(C, F, loop, tj, .0245, "thumb", thumb=True)
    log(f"hand: {'left' if sx > 0 else 'right'}")


def joints_of(F, kx, ky, L, spread):
    """a finger's knuckle, middle joint, last joint and tip in its relaxed curl"""
    d = rot(F.ax, F.az, spread)
    side = unit(np.cross(d, F.az))                                   # the bend's axis
    p = F.p(kx, ky, -.002)
    out = [p]
    for k, (share, bend) in enumerate(zip(PHAL, CURL)):
        d = rot(d, side, -bend)
        p = p + d * L * share
        out.append(p)
    return out


def thumb_joints(F):
    c = F.p(.022, .030, -.012)                   # its metacarpal lies in the thenar mound, inside the palm
    mcp = F.p(.064, .052, -.024)
    dp = unit(F.ax * .86 + F.ay * .22 - F.az * .46)
    ip = mcp + dp * .031
    dd = unit(F.ax * .88 + F.ay * .10 - F.az * .46)
    tip = ip + dd * .027
    return [c, mcp, ip, tip]


def digit(C, F, base, J, wd, part, thumb=False):
    """rings of 8 from the base ring through the joints to a cap at the tip. Each ring's vertices keep the base
    ring's angles round the digit (no twist), easing to the digit's own oval past its first ring."""
    base = list(base)
    b_pts = np.array([C.V[v] for v in base])
    centre0 = b_pts.mean(0)
    seg = [(J[k], J[k + 1]) for k in range(len(J) - 1)]
    def frame_at(ax):
        upv = F.az if not thumb else (F.ay + F.az)
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
        plan = [(0, .78, 1.30, .5), (0, 1.0, 1.08, .9), (1, .35, 1.0, 1.0), (1, 1.0, .92, 1.0), (2, .5, .90, 1.0),
                (2, .86, .80, 1.0)]
    else:
        plan = [(0, .40, 1.0, .5), (0, 1.0, .94, 1.0), (1, .5, .90, 1.0), (1, 1.0, .85, 1.0), (2, .5, .81, 1.0),
                (2, .86, .74, 1.0)]
    prev = base
    rings = [base]
    for bone, share, ws, ease in plan:
        a, b = seg[bone]
        c = a + (b - a) * share
        ax = unit(b - a)
        up, side = frame_at(ax)
        r = wd * ws / 2
        ring = []
        for j in range(8):
            t = ang0[j] * (1 - ease) + canon[j] * ease
            # the back of a digit is rounder, its pad fuller; a little wider than it is deep
            ry, rz = r, r * (.86 if math.sin(t) > 0 else .92)
            p = c + side * (ry * math.cos(t)) + up * (rz * math.sin(t))
            ring.append(C.add(p, part))
        rings.append(ring)
    for r0, r1 in zip(rings, rings[1:]):
        C.strip(r0, r1)
    tip_dir = unit(seg[-1][1] - seg[-1][0])
    C.cap(rings[-1], part, wd * .30, tip_dir)


def detail(P, frames, log=None):
    """knuckles, the pads and creases, the nails' plates over the subdivided hands (metres along the normal)"""
    out = np.zeros(len(P), np.float32)
    for F in frames:
        rel = P - F.W
        x, y, z = rel @ F.ax, rel @ F.ay, rel @ F.az
        near = (x > -.01) & (x < .23) & (np.abs(y) < .08) & (np.abs(z) < .06)
        if not near.any():
            continue
        for name, kx, ky, L, wd, spread in FINGERS:
            J = joints_of(F, kx, ky, L, spread)
            for k, (jp, amp, rad) in enumerate(((J[0], .0026, .010), (J[1], .0018, .007), (J[2], .0010, .0055))):
                q = P - jp
                dn = q @ F.az
                rr = np.sqrt(((q - np.outer(dn, F.az)) ** 2).sum(1))
                out += amp * np.exp(-(rr / rad) ** 2) * (dn > 0) * near                   # knuckles on the back
                out -= .0007 * np.exp(-(rr / (rad * .5)) ** 2) * (dn < 0) * near           # creases on the palm
            # the nail: a low plate over the last bone's back half, a groove round it
            a, b = J[2], J[3]
            d = unit(b - a)
            q = P - a
            t = (q @ d) / float(np.linalg.norm(b - a))
            up = unit(F.az - d * float(F.az @ d))
            side = unit(np.cross(d, up))
            u = (q @ side) / (wd * .40)
            h = q @ up
            nail = (t > .42) & (t < 1.02) & (np.abs(u) < 1.0) & (h > 0) & near
            out += .0005 * nail
            rim = np.exp(-((np.abs(u) - 1.0) / .12) ** 2) * (t > .42) * (t < 1.0) * (h > 0) * near
            out -= .0004 * rim
    return out
