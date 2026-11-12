"""Gun parts kit (used by weapons.py): the human guns' own shapes, built as direct meshes like the Void Requiem set
(voidkit.py: no booleans, every edge chamfered or rounded on purpose).

Bodies
  loft        a hard body through octagonal sections along the gun (receivers that taper, slides, shrouds)
  rloft       the same through soft sections (stocks, forends, anything a hand closes round)
  rprism      a side profile extruded across the gun with ROUNDED flanks (wood, moulded polymer)
  prism / plate (voidkit)   chamfered extrusion / raised flank panel
Turned parts
  lathe / lathe_x (voidkit), lathe_z (knobs and turrets standing up), tube_ (a chamfered tube, bored or solid),
  band (a ring round the bore), bar (a length of a ring: cage bars, prongs, fins)
Details
  slots (dark recessed slots on a flank), capsule (their outline), hexbolts, cable, fins, glowline
Assemblies
  grip, stock_frame, stock_tube, cage, brake, hider, can (suppressor), port (ejection port), selector, coil (an energy
  gun's emitter stack), cell (its power cell), box_mag, arc_profile

Frame as gunkit: origin = top of the pistol grip, barrel along -Y, Z up, the gun's right side is -X.
"""
import math, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import bl
import gunkit as K
import voidkit as V
from voidkit import mk, prism, plate, lathe, lathe_x, poly_offset, spl

TAU = 2 * math.pi


# ------------------------------------------------------------------ bodies
def _oct(hw, z0, z1, ch, x=0.0):
    ct, cb = ch if isinstance(ch, (tuple, list)) else (ch, ch)
    ct = min(ct, hw * .95, (z1 - z0) * .48); cb = min(cb, hw * .95, (z1 - z0) * .48)
    return [(x + hw, z0 + cb), (x + hw, z1 - ct), (x + hw - ct, z1), (x - hw + ct, z1), (x - hw, z1 - ct), (x - hw, z0 + cb),
            (x - hw + cb, z0), (x + hw - cb, z0)]


def _skin(name, rings, m, sharp, caps=True):
    n = len(rings[0][1])
    Vv = [(x, y, z) for y, ring in rings for x, z in ring]
    F = []
    for i in range(len(rings) - 1):
        for j in range(n):
            k = (j + 1) % n
            F.append((i * n + j, i * n + k, (i + 1) * n + k, (i + 1) * n + j))
    if caps:
        F += [tuple(range(n)), tuple(range((len(rings) - 1) * n, len(rings) * n))]
    return mk(name, Vv, F, m, sharp)


def loft(name, secs, m, sharp=30, caps=True):
    """A hard body: sections (y, z0, z1, half width, chamfer[, x]) from the rear forward; chamfer may be (top, bottom)."""
    return _skin(name, [(s[0], _oct(s[3], s[1], s[2], s[4], s[5] if len(s) > 5 else 0.0)) for s in secs], m, sharp, caps)


def _soft(hw, z0, z1, p, tw, n, x=0.0):
    out = []
    for k in range(n):
        a = TAU * k / n
        c, s = math.cos(a), math.sin(a)
        ex = 2.0 / p
        zr = math.copysign(abs(s) ** ex, s)
        xx = math.copysign(abs(c) ** ex, c) * hw * (1 + (tw - 1) * (zr + 1) / 2)
        out.append((x + xx, (z0 + z1) / 2 + (z1 - z0) / 2 * zr))
    return out


def rloft(name, secs, m, n=20, sharp=50, caps=True):
    """A soft body: sections (y, z0, z1, half width[, p, top width scale, x]); p = 2 an ellipse, 4+ a soft box."""
    return _skin(name, [(s[0], _soft(s[3], s[1], s[2], s[4] if len(s) > 4 else 3.5, s[5] if len(s) > 5 else 1.0, n,
                                     s[6] if len(s) > 6 else 0.0)) for s in secs], m, sharp, caps)


def rprism(name, pts, w, m, r=.006, segs=3, x=0.0, sharp=60):
    """A side profile [(y, z)] extruded across the gun, its flanks rounded over (radius r)."""
    r = min(r, w * .48)
    n = len(pts)
    lay = []
    for k in range(segs + 1):
        a = math.pi / 2 * k / segs
        lay.append((w / 2 - r + r * math.sin(a), r * (1 - math.cos(a))))
    lay = lay[::-1]                                                  # from the outer face (most inset) in to the flank
    rows = [(x - xo, poly_offset(pts, d) if d > 1e-6 else list(pts)) for xo, d in lay] + \
           [(x + xo, poly_offset(pts, d) if d > 1e-6 else list(pts)) for xo, d in lay[::-1]]
    Vv = [(xx, y, z) for xx, pp in rows for y, z in pp]
    F = []
    for i in range(len(rows) - 1):
        for j in range(n):
            k = (j + 1) % n
            F.append((i * n + j, i * n + k, (i + 1) * n + k, (i + 1) * n + j))
    F += [tuple(range(n)), tuple(range((len(rows) - 1) * n, len(rows) * n))]
    return mk(name, Vv, F, m, sharp)


# ------------------------------------------------------------------ turned parts
def lathe_z(name, prof, c, m, n=24, sharp=32, phase=0.0):
    """Profile [(dz, r)] turned round the upright through c = (x, y, z)."""
    Vv, F = V._lathe(prof, n, lambda a, r, th: (c[0] + r * math.cos(th + phase), c[1] + r * math.sin(th + phase), c[2] + a), False)
    return mk(name, Vv, F, m, sharp)


def tube_(name, y0, y1, r, m, z, x=0.0, bore=0.0, n=32, ch=.0012, r1=None):
    """A tube along the bore from y0 (rear) to y1 (front), ends chamfered; bored out when bore > 0; r1 = front radius."""
    r1 = r if r1 is None else r1
    c0, c1 = min(ch, r * .3), min(ch, r1 * .3)
    if bore:
        prof = [(y0, bore), (y0, r - c0), (y0 - c0, r), (y1 + c1, r1), (y1, r1 - c1), (y1, bore)]
        return lathe(name, prof, m, z, x, n, closed=True)
    return lathe(name, [(y0, 0), (y0, r - c0), (y0 - c0, r), (y1 + c1, r1), (y1, r1 - c1), (y1, 0)], m, z, x, n)


def band(name, y, L, r, m, z, x=0.0, t=.003, n=32, ch=.001):
    """A ring round the bore: from y forward L, outer radius r, t thick."""
    return tube_(name, y, y - L, r, m, z, x, bore=r - t, n=n, ch=ch)


def bar(name, y0, y1, r0, r1, a0, a1, m, z, x=0.0, n=2, taper=1.0):
    """A length of a ring: between radii r0 < r1 and angles a0 < a1 (radians from +X toward +Z) round the bore, from
    y0 forward to y1. taper < 1 narrows it toward the front (a prong)."""
    Vv = []
    for y, k in ((y0, 1.0), (y1, taper)):
        am, ah = (a0 + a1) / 2, (a1 - a0) / 2 * k
        for r in (r0, r1):
            for i in range(n + 1):
                a = am - ah + 2 * ah * i / n
                Vv.append((x + r * math.cos(a), y, z + r * math.sin(a)))
    m1 = n + 1
    F = []
    for e in (0, 1):
        o = e * 2 * m1
        for i in range(n):
            F.append((o + i, o + i + 1, o + m1 + i + 1, o + m1 + i))          # the end
    for i in range(n):
        F.append((i, i + 1, 2 * m1 + i + 1, 2 * m1 + i))                      # inner
        F.append((m1 + i, m1 + i + 1, 3 * m1 + i + 1, 3 * m1 + i))            # outer
    for i in (0, n):
        F.append((i, m1 + i, 3 * m1 + i, 2 * m1 + i))                          # the two sides
    return mk(name, Vv, F, m, 28)


def cage(P, name, y0, y1, z, r, m, t=.0045, bars=8, fill=.6, frames=(), phase=None, frame_m=None, x=0.0, skip=()):
    """A slotted handguard round the barrel from y0 forward to y1: `bars` long bars (each `fill` of its share of the
    ring: the gaps between them are the vents), with ring frames (y, length) holding them. skip = bar indices left out."""
    phase = math.pi / bars if phase is None else phase
    w = TAU / bars * fill / 2
    for k in range(bars):
        if k in skip:
            continue
        a = phase + TAU * k / bars
        P.append(bar(name, y0, y1, r - t, r, a - w, a + w, m, z, x, 2))
    for fy, fl in frames:
        P.append(band(name + '_frame', fy, fl, r + .0008, frame_m or m, z, x, t + .0016, bars * 4))


# ------------------------------------------------------------------ details
def capsule(y, z, L, h, ang=0.0, n=5):
    """Outline of a slot centred at (y, z): L long, h high, turned by ang."""
    pts = []
    r = h / 2
    for i in range(n + 1):
        a = -math.pi / 2 + math.pi * i / n
        pts.append((-(L / 2 - r) - r * math.cos(a), r * math.sin(a)))
    for i in range(n + 1):
        a = math.pi / 2 - math.pi * i / n
        pts.append(((L / 2 - r) + r * math.cos(a), r * math.sin(a)))
    ca, sa = math.cos(ang), math.sin(ang)
    return [(y + px * ca - pz * sa, z + px * sa + pz * ca) for px, pz in pts]


def slots(P, name, items, x, m, lift=.0005, sym=True, side=1):
    """Dark recessed slots on a flank at x: items are (y, z, L, h[, ang]) or ready outlines."""
    for it in items:
        pts = it if isinstance(it[0], (tuple, list)) else capsule(*it)
        P.append(plate(name, pts, m, x - .0012, x + lift, .0004, sym=sym, side=side))


def hexbolts(P, pts, x, m, r=.003, sym=True, n=6, side=1):
    """Socket-head bolts on a flank: a hexagon (n = 6) or a round head (n = 16) with its recess."""
    for y, z in pts:
        for s in ((1, -1) if sym else (side,)):
            P.append(lathe_x('bolt', [(-.001, r), (.0016, r), (.0021, r * .82), (.0021, r * .5), (.0011, r * .46), (.0011, 0)], (s * x, y, z), m, n, s, phase=.5))


def cross_pins(P, pts, w, m, r=.0024):
    for y, z in pts:
        P.append(K.cylx('pin', r, w + .0016, (0, y, z), m, 14, .0004))


def fins(P, name, y0, y1, z0, z1, x, m, n=6, t=.0022, lift=.004, sym=True, rake=0.0):
    """Cooling fins standing off a flank: n thin plates between y0 and y1."""
    step = (y0 - y1) / n
    for i in range(n):
        y = y0 - step * (i + .5)
        pts = [(y + t / 2 + rake, z1), (y - t / 2 + rake, z1), (y - t / 2, z0), (y + t / 2, z0)]
        P.append(plate(name, pts, m, x - .001, x + lift, .0005, sym=sym))


def glowline(P, name, pts, x, m, h=.004, lift=.0006, sym=True):
    """A line of light let into a flank along the side-view points pts [(y, z)] (h high)."""
    top = [(y, z + h / 2) for y, z in pts]
    bot = [(y, z - h / 2) for y, z in pts][::-1]
    P.append(plate(name, top + bot, m, x - .001, x + lift, .0003, sym=sym))


def cable(name, pts, r, m, n=8, samples=20):
    """A hose or cable through 3D points."""
    C, _ = spl(pts, samples)
    Vv = []
    up = np.array([0.0, 0.0, 1.0])
    for i in range(len(C)):
        t = C[min(i + 1, len(C) - 1)] - C[max(i - 1, 0)]
        t = t / (np.linalg.norm(t) + 1e-12)
        a = np.cross(t, up)
        if np.linalg.norm(a) < 1e-4:
            a = np.cross(t, np.array([1.0, 0.0, 0.0]))
        a /= np.linalg.norm(a)
        b = np.cross(t, a)
        for k in range(n):
            th = TAU * k / n
            Vv.append(tuple(C[i] + (a * math.cos(th) + b * math.sin(th)) * r))
    F = []
    for i in range(len(C) - 1):
        for k in range(n):
            j = (k + 1) % n
            F.append((i * n + k, i * n + j, (i + 1) * n + j, (i + 1) * n + k))
    F += [tuple(range(n)), tuple(range((len(C) - 1) * n, len(C) * n))]
    return mk(name, Vv, F, m, 50)


# ------------------------------------------------------------------ assemblies
def gp(ang, y, z):
    """Point on a raked grip: a along its front-back (+ = rear), b down it."""
    ca, sa = math.cos(ang), math.sin(ang)
    return lambda a, b: (y + a * ca + b * sa, z - b * ca + a * sa)


def grip(P, m, panel_m=None, cap_m=None, ang=.3, h=.115, w=.032, y=0.0, z=0.0, swell=.005, strap_m=None):
    """The pistol grip: a raked, swelled core; a textured panel let into each side; a base cap; a back strap."""
    P.append(K.grip_profile('grip', m, ang=ang, h=h, w=w, y=y, z=z, swell=swell))
    g = gp(ang, y, z)
    if panel_m:
        P.append(plate('grip_panel', [g(-.014, .024), g(.016, .02), g(.021, h * .5), g(.015, h * .84), g(-.011, h * .88), g(-.019, h * .5)], panel_m,
                       w / 2 - .004, w / 2 + .0012, .0014))
    if cap_m:
        P.append(prism('gripcap', [g(-.023, h - .002), g(.029, h - .006), g(.031, h + .006), g(-.021, h + .009)], w + .002, cap_m, .0015))
    if strap_m:
        P.append(prism('backstrap', [g(.026, .012), g(.0315, .016), g(.0335, h * .5), g(.0295, h * .9), g(.026, h * .9), g(.0295, h * .5)], w * .5, strap_m, .001))


def stock_frame(P, m, pad_m, y0, zt, L=.25, drop=.125, w=.036, zb=.02, ch=.004, comb=.034, cheek_m=None, bolt_m=None):
    """A skeleton stock: a comb beam, a lower strut and a butt block with a real opening between them, a recoil pad."""
    y1 = y0 + L
    P.append(prism('stock_comb', [(y0, zt), (y1 - .03, zt - .01), (y1 - .03, zt - .01 - comb), (y0 + .05, zt - comb + .004), (y0, zt - comb - .004)], w, m, ch))
    P.append(prism('stock_strut', [(y0, zb + .03), (y0 + .03, zb + .032), (y1 - .03, zt - drop + .034), (y1 - .03, zt - drop + .004), (y0 + .04, zb), (y0, zb)],
                   w * .8, m, ch * .8))
    P.append(prism('stock_butt', [(y1 - .034, zt - .008), (y1, zt - .014), (y1, zt - drop), (y1 - .034, zt - drop + .002)], w + .003, m, ch))
    P.append(rprism('stock_pad', [(y1, zt - .01), (y1 + .014, zt - .014), (y1 + .015, zt - drop + .006), (y1, zt - drop)], w + .006, pad_m, .004))
    if cheek_m:
        P.append(prism('stock_cheek', [(y0 + .03, zt + .001), (y0 + .04, zt + .012), (y1 - .07, zt + .006), (y1 - .06, zt - .006)], w + .004, cheek_m, .004))
    if bolt_m:
        hexbolts(P, [(y0 + .02, zt - comb * .5), (y1 - .018, zt - drop * .5)], (w + .003) / 2, bolt_m, .003)


def stock_tube(P, tube_m, body_m, pad_m, metal_m, y0, z, L=.24, r=.0155, w=.036, pos=.0):
    """A collapsing stock on a buffer tube: the tube and its castle nut, the sliding body with its latch, a pad."""
    P.append(tube_('buffer', y0, y0 + L - .03, r, tube_m, z, n=24))
    P.append(lathe('castlenut', [(y0 + .016, 0), (y0 + .016, r + .0045), (y0 + .002, r + .0045), (y0 + .002, 0)], metal_m, z, 0, 12, sharp=20))
    a = y0 + .09 + pos; b = y0 + L
    P.append(rprism('stock_body', [(a, z + r + .006), (b - .014, z + r + .006), (b, z + r - .002), (b, z - .11), (b - .016, z - .118), (b - .05, z - .086),
                                  (b - .095, z - .03), (a, z - r - .006)], w, body_m, .008, 4))
    slots(P, 'stock_cut', [[(b - .06, z - .04), (b - .028, z - .04), (b - .028, z - .092), (b - .04, z - .084)]], w / 2, tube_m)
    ribbed_pad(P, pad_m, b, z + r, z - .118, w + .004, 6, .014)
    P.append(prism('stock_latch', [(a + .02, z - r - .006), (a + .07, z - r - .006), (a + .062, z - r - .016), (a + .026, z - r - .014)], .012, metal_m, .001))


def box_mag(name, pts, w, m, floor_m=None, ribs=(), rib_m=None, ch=.002, floor=None, window=None, window_m=None):
    """A box magazine from its side profile: the body, pressed ribs (each an outline), a floor plate (outline), and a
    witness window."""
    parts = [prism(name, pts, w, m, ch)]
    for rp in ribs:
        parts.append(plate('magrib', rp, rib_m or m, w / 2 - .001, w / 2 + .0012, .0005))
    if floor:
        parts.append(prism('magfloor', floor, w + .005, floor_m or m, .0018))
    if window:
        cy = sum(p[0] for p in window) / len(window); cz = sum(p[1] for p in window) / len(window)
        parts.append(plate('magwindow', window, floor_m or m, w / 2 - .001, w / 2 + .0005, .0006))
        parts.append(plate('magwindow_slit', [(cy + (p[0] - cy) * .2, cz + (p[1] - cz) * .82) for p in window], window_m, w / 2 - .001, w / 2 + .0009, .0002))
    return parts


def arc_profile(y_rear, z_top, R, depth, theta, n=12):
    """Side profile of a curved magazine (it curves forward as it drops): rear arc down, front arc back up."""
    cy, cz = y_rear - R, z_top
    rear = [(cy + R * math.cos(t), cz - R * math.sin(t)) for t in np.linspace(0, theta, n)]
    front = [(cy + (R - depth) * math.cos(t), cz - (R - depth) * math.sin(t)) for t in np.linspace(theta, 0, n)]
    return rear + front


def arc_floor(y_rear, z_top, R, depth, theta, t=.01, over=.004):
    """The floor plate across the end of a curved magazine (arc_profile with the same numbers)."""
    cy, cz = y_rear - R, z_top
    u = (math.cos(theta), -math.sin(theta)); tn = (-math.sin(theta), -math.cos(theta))
    A = (cy + (R + over) * u[0], cz + (R + over) * u[1]); B = (cy + (R - depth - over) * u[0], cz + (R - depth - over) * u[1])
    return [(A[0] - tn[0] * .002, A[1] - tn[1] * .002), (B[0] - tn[0] * .002, B[1] - tn[1] * .002), (B[0] + tn[0] * t, B[1] + tn[1] * t), (A[0] + tn[0] * t, A[1] + tn[1] * t)]


def chaikin(pts, it=2, sharp=()):
    """Round the corners of a closed side profile (corner cutting); indices in `sharp` keep their corner."""
    P = [tuple(p) for p in pts]
    keep = set(sharp)
    for _ in range(it):
        out = []; nk = set()
        n = len(P)
        for i in range(n):
            a, b = P[i], P[(i + 1) % n]
            if i in keep:
                nk.add(len(out)); out.append(a)
            else:
                out.append((a[0] * .75 + b[0] * .25, a[1] * .75 + b[1] * .25))
            if (i + 1) % n not in keep:
                out.append((a[0] * .25 + b[0] * .75, a[1] * .25 + b[1] * .75))
        P, keep = out, nk
    return P


def arc_strip(y_rear, z_top, R, r0, r1, t0, t1, n=8):
    """A strip between radii r0 > r1 of the same arc (a rib pressed along a curved magazine)."""
    cy, cz = y_rear - R, z_top
    a = [(cy + r0 * math.cos(t), cz - r0 * math.sin(t)) for t in np.linspace(t0, t1, n)]
    b = [(cy + r1 * math.cos(t), cz - r1 * math.sin(t)) for t in np.linspace(t1, t0, n)]
    return a + b


def brake(P, name, y, z, r, L, m, dark_m, ports=3, bore=None, x=0.0):
    """A muzzle brake from y forward L: a stepped turned body, a crowned bore, side ports cut through it."""
    bore = bore or r * .45
    P.append(lathe(name, [(y, 0), (y, r * .78), (y - L * .1, r * .78), (y - L * .14, r), (y - L + .002, r), (y - L, r - .002), (y - L, bore),
                          (y - L + .02, bore), (y - L + .02, 0)], m, z, x, 24))
    for i in range(ports):
        py = y - L * (.3 + .56 * i / max(ports - 1, 1))
        P.append(prism(name + '_port', capsule(py, z, L * .11, r * .95, math.pi / 2), 2 * r + .0012, dark_m, .0003, x=x))


def hider(P, name, y, z, r, L, m, prongs=4, bore=None, x=0.0):
    """An open-pronged flash hider."""
    bore = bore or r * .5
    P.append(tube_(name, y, y - L * .34, r, m, z, x, bore=bore, n=24))
    w = TAU / prongs * .32
    for k in range(prongs):
        a = math.pi / prongs + TAU * k / prongs
        P.append(bar(name + '_prong', y - L * .32, y - L, bore, r, a - w, a + w, m, z, x, 2, taper=.7))


def can(P, name, y, z, r, L, m, band_m, bore=None, x=0.0, bands=2):
    """A sound suppressor: a long turned tube with stepped ends and knurled bands."""
    bore = bore or r * .3
    P.append(lathe(name, [(y, 0), (y, r * .7), (y - .006, r * .7), (y - .012, r), (y - L + .008, r), (y - L + .002, r * .86), (y - L, r * .8), (y - L, bore),
                          (y - L + .02, bore), (y - L + .02, 0)], m, z, x, 32))
    for i in range(bands):
        P.append(band(name + '_band', y - .02 - i * .012, .008, r + .0012, band_m, z, x, .003, 24, .0006))


def port(P, y0, y1, z0, z1, x, dark_m, bolt_m, side=-1, door_m=None):
    """An ejection port on one flank (side = -1: the gun's right): the opening, the bolt seen in it, a dust door
    hanging open under it."""
    pts = [(y0, z0), (y0, z1), (y1 + .004, z1), (y1, z1 - .004), (y1, z0)]
    P.append(plate('port', pts, dark_m, x - .002, x + .0004, .0005, sym=False, side=side))
    if bolt_m is not None:
        P.append(plate('port_bolt', poly_offset(pts, .0035), bolt_m, x - .003, x - .0002, .0008, sym=False, side=side))
    if door_m:
        P.append(plate('port_door', [(y0, z0 - .001), (y1, z0 - .001), (y1 + .002, z0 - (z1 - z0) * .8), (y0 - .002, z0 - (z1 - z0) * .8)], door_m,
                       x - .0005, x + .0022, .0006, sym=False, side=side))


def selector(P, y, z, x, m, side=1, ang=.5, L=.02, r=.0055):
    """A selector / safety lever on a flank: its hub and a lever lying at ang."""
    P.append(lathe_x('selector', [(-.001, r), (.0024, r), (.003, r * .7), (.003, 0)], (side * x, y, z), m, 16, side))
    ca, sa = math.cos(ang), math.sin(ang)
    lev = [(y + r * .5 * sa, z - r * .5 * ca), (y - L * ca + .002 * sa, z - L * sa - .002 * ca), (y - L * ca - .002 * sa, z - L * sa + .002 * ca), (y - r * .5 * sa, z + r * .5 * ca)]
    P.append(plate('selector_arm', lev, m, x + .0015, x + .0042, .0006, sym=False, side=side))


def coil(P, name, y0, y1, z, r, M, rings=6, x=0.0, core=None, ring_m=None, lip_m=None):
    """An energy gun's emitter stack between y0 (rear) and y1: a tube of dim light, turned rings along it."""
    core = core if core is not None else r * .62
    P.append(tube_(name + '_core', y0, y1, core, M['glow'], z, x, n=20, ch=0))
    L = y0 - y1
    step = L / rings
    for i in range(rings):
        y = y0 - step * (i + .22)
        P.append(lathe(name + '_ring', [(y, core - .0006), (y, r - .001), (y - .001, r), (y - step * .8 + .001, r), (y - step * .8, r - .001),
                                        (y - step * .8, core - .0006)], ring_m or M['dark'], z, x, 28, closed=True))
        P.append(band(name + '_fin', y - step * .36, step * .08, r + .0016, ring_m or M['dark'], z, x, .003, 28, .0005))
        if lip_m is not None and i % 2 == 0:
            P.append(band(name + '_lip', y - step * .8, .0016, r + .0008, lip_m, z, x, .0022, 28, .0004))


def cell(P, name, c, r, h, M, n=6, glow=True):
    """A power cell standing under the gun: a faceted can with a lit waist and a dark foot (c = the middle of its top)."""
    x, y, z = c
    P.append(lathe_z(name, [(-h, 0), (-h, r * .86), (-h + .004, r), (-h * .62, r), (-h * .6, r * .9), (-h * .34, r * .9), (-h * .32, r), (-.004, r),
                            (0, r * .86), (0, 0)], (x, y, z), M['metal'], n, 24, phase=math.pi / n))
    if glow:
        P.append(lathe_z(name + '_glow', [(-h * .51, 0), (-h * .51, r * .915), (-h * .43, r * .915), (-h * .43, 0)], (x, y, z), M['glow'], n, 24, phase=math.pi / n))
        for q in (.6, .43):
            P.append(lathe_z(name + '_louvre', [(-h * q, 0), (-h * q, r * .93), (-h * (q - .09), r * .93), (-h * (q - .09), 0)], (x, y, z), M['dark'], n, 24, phase=math.pi / n))
    P.append(lathe_z(name + '_foot', [(-h - .006, 0), (-h - .006, r * .7), (-h - .002, r * .92), (-h, r * .92), (-h, 0)], (x, y, z), M['dark'], n, 24, phase=math.pi / n))


def iron_rear(P, y, z, m, dot_m=None, base_z=None, w=.03, r=.0085, wall=.0013):
    """An open rear sight (the names are the irons' API: finish() folds them under a rail optic): a large, thin ghost
    ring on a slim stem over a low, narrow base. Nothing stands beside the ring: the target area stays clear."""
    bz = z - .03 if base_z is None else base_z
    P.append(prism('rear_base', [(y + .012, bz), (y + .012, bz + .004), (y + .006, bz + .006), (y - .006, bz + .006), (y - .012, bz + .004), (y - .012, bz)],
                   min(w, .018), m, .0012))
    P.append(lathe('rear_ring', [(y + .002, r), (y + .002, r + wall), (y - .002, r + wall), (y - .002, r)], m, z, 0, 48, closed=True))
    if z - r - .0004 > bz + .005:
        P.append(prism('rear_base', [(y + .002, bz + .005), (y + .002, z - r - .0004), (y - .002, z - r - .0004), (y - .002, bz + .005)], .003, m, .0005))


def iron_front(P, y, z, m, dot_m=None, base_z=None, w=.024):
    """A thin front post with its tip at (0, y, z) between two thin wings (open above)."""
    bz = z - .032 if base_z is None else base_z
    P.append(prism('front_base', [(y + .01, bz), (y + .01, bz + .004), (y + .005, bz + .006), (y - .005, bz + .006), (y - .01, bz + .004), (y - .01, bz)],
                   min(w, .018), m, .0012))
    for s in (1, -1):
        P.append(prism('front_ear', [(y + .006, bz + .004), (y + .003, z + .004), (y - .003, z + .004), (y - .006, bz + .004)], .0016, m, .0005, x=s * (w / 2 - .001)))
    P.append(prism('post', [(y + .0016, bz + .005), (y + .0012, z), (y - .0012, z), (y - .0016, bz + .005)], .0024, m, .0004))
    if dot_m is not None:
        P.append(lathe('postdot', [(y + .0017, 0), (y + .0017, .001), (y + .0013, .001), (y + .0013, 0)], dot_m, z - .002, 0, 8))


# ------------------------------------------------------------------ second pass: strips, guards, triggers, windows
def smooth(pts, it=2):
    """Corner cutting on an OPEN line [(y, z)]: the ends stay where they are."""
    P = [tuple(p) for p in pts]
    for _ in range(it):
        out = [P[0]]
        for a, b in zip(P, P[1:]):
            out.append((a[0] * .75 + b[0] * .25, a[1] * .75 + b[1] * .25))
            out.append((a[0] * .25 + b[0] * .75, a[1] * .25 + b[1] * .75))
        out.append(P[-1])
        P = out
    return P


def ribbon(pts, t):
    """The outline of a strip along an open centreline [(y, z)]: t thick (one number, or [start, end], or one per
    point)."""
    n = len(pts)
    if not isinstance(t, (list, tuple)):
        ts = [t] * n
    elif len(t) == n:
        ts = list(t)
    else:
        ts = [float(np.interp(i / (n - 1), np.linspace(0, 1, len(t)), t)) for i in range(n)]
    A, Bk = [], []
    for i, (y, z) in enumerate(pts):
        a = pts[max(i - 1, 0)]; b = pts[min(i + 1, n - 1)]
        dy, dz = b[0] - a[0], b[1] - a[1]
        l = math.hypot(dy, dz) or 1.0
        ny, nz = -dz / l, dy / l
        h = ts[i] / 2
        A.append((y + ny * h, z + nz * h)); Bk.append((y - ny * h, z - nz * h))
    return A + Bk[::-1]


def guard(P, m, pts, w=.012, t=.0045, r=.0017, name='trigguard', it=2):
    """A trigger guard with section: a rounded strip (t thick, w across) bent along the centreline pts."""
    P.append(rprism(name, ribbon(smooth(pts, it), t), w, m, min(r, t * .4), 2))


def trigger(P, m, y, z, L=.03, w=.0065, name='trigger', sweep=.004):
    """A curved trigger blade hanging from (y, z): thick at the pivot, its toe swept forward."""
    pts = smooth([(y + .004, z + .005), (y - .0005, z - L * .3), (y - sweep, z - L * .72), (y - sweep + .0035, z - L)], 2)
    P.append(rprism(name, ribbon(pts, [.0058, .0046, .0036, .003]), w, m, .0013, 2))


def serrations(P, name, y, n, pitch, z0, z1, x, m, rake=0.0, t=.002, sym=True, side=1, lift=.0004):
    """Grasping grooves cut in a flank: n dark slots from y forward, each raked by `rake` over its height."""
    for i in range(n):
        yy = y - i * pitch
        P.append(plate(name, [(yy + rake, z1), (yy - t + rake, z1), (yy - t, z0), (yy, z0)], m, x - .0012, x + lift, .0003, sym=sym, side=side))


def louvre(P, name, y0, y1, z0, z1, x, M, n=4, share=.28, sym=True, side=1, upright=False, lift=.0005, rake=0.0, glow=None, frame_m=None):
    """A louvred window in a flank (y0 rear > y1 front, z0 < z1): a dark recess, the light behind it seen only through
    n slits (`share` of the opening)."""
    pts = [(y0, z0), (y0 + rake, z1), (y1 + rake, z1), (y1, z0)]
    P.append(plate(name, pts, frame_m or M['dark'], x - .0015, x + lift, .0008, sym=sym, side=side))
    g = glow or M['glow']
    if upright:
        step = (y0 - y1 - .006) / n
        for i in range(n):
            a = y0 - .003 - step * (i + .5); h = step * share / 2
            P.append(plate(name + '_slit', [(a + h, z0 + .003), (a + h + rake * .8, z1 - .003), (a - h + rake * .8, z1 - .003), (a - h, z0 + .003)], g,
                           x, x + lift + .0003, .0002, sym=sym, side=side))
    else:
        step = (z1 - z0 - .006) / n
        for i in range(n):
            c = z0 + .003 + step * (i + .5); h = step * share / 2
            k = rake * (c - z0) / max(z1 - z0, 1e-6)
            P.append(plate(name + '_slit', [(y0 - .003 + k, c - h), (y0 - .003 + k, c + h), (y1 + .003 + k, c + h), (y1 + .003 + k, c - h)], g,
                           x, x + lift + .0003, .0002, sym=sym, side=side))


def disc(name, y0, y1, r, m, z, x=0.0, n=40, ch=.0015):
    """A turned disc round the bore axis (a recoil shield, a flange)."""
    return lathe(name, [(y0, 0), (y0, r - ch), (y0 - ch, r), (y1 + ch, r), (y1, r - ch), (y1, 0)], m, z, x, n)


def muzzle(P, name, y0, y1, z, r, m, bore, x=0.0, n=28, dark_m=None):
    """A crowned muzzle: the barrel's end from y0 to its face y1, the crown recessed round a real bore."""
    P.append(lathe(name, [(y0, 0), (y0, r), (y1 + .0012, r), (y1, r - .0012), (y1, bore + .0022), (y1 + .0025, bore + .0008), (y1 + .0025, bore),
                          (y1 + .03, bore), (y1 + .03, 0)], m, z, x, n))
    if dark_m is not None:
        P.append(lathe(name + '_bore', [(y1 + .012, 0), (y1 + .012, bore - .0003), (y1 + .0125, bore - .0003), (y1 + .0125, 0)], dark_m, z, x, 12))


def hand_grip(P, m, ang, h, w, y=0.0, z=0.0, r=.0105, name='grip', top=-.004, ext=0.0, swell=.0045, round_butt=False):
    """A handgun's grip on the lines the firing hand is fitted to (the game measures the backstrap 4 cm under the top
    of the grip, the side 1.8 cm ahead of it, and closes the fingers round the front strap): the back strap, the front
    strap, the width and the length of gunkit.grip_profile with the same numbers, the flanks rounded as much, nothing
    flaring inside that length. ext lengthens it; returns the grip's own coordinates (a + = rear, b down)."""
    g = gp(ang, y, z)
    hb = h + ext
    pts = [g(.03, top), g(.032, .02), g(.0265, h * .5), g(.028, hb), g(-.02, hb + .004), g(-.026, hb * .72), g(-.022 - swell, h * .5), g(-.0265, .034),
           g(-.024, top)]
    P.append(rprism(name, chaikin(pts, 2 if round_butt else 1, sharp=(0, 8) if round_butt else (0, 3, 4, 8)), w, m, min(r, w * .32), 4))
    return g


def sloft(name, secs, m, n=20, sub=5, sharp=50, caps=True):
    """rloft through sections smoothed along the gun: (y, z0, z1, half width[, p, top scale, x]) are stations, a curve
    is drawn through them (walnut and moulded stocks: a wrist, a comb, a swell, none of it faceted)."""
    A = np.array([[s[0], s[1], s[2], s[3], s[4] if len(s) > 4 else 3.5, s[5] if len(s) > 5 else 1.0, s[6] if len(s) > 6 else 0.0] for s in secs], float)
    C, _ = spl(A, (len(secs) - 1) * sub + 1)
    return rloft(name, [(c[0], min(c[1], c[2] - .002), c[2], max(c[3], .002), max(c[4], 2.0), c[5], c[6]) for c in C], m, n, sharp, caps)


def seamline(P, pts, x, m, t=.0011, sym=True, side=1, name='panel_line'):
    """A panel break: a fine dark line drawn into a flank along the side-view points."""
    P.append(plate(name, ribbon(pts, t), m, x - .0006, x + .0003, .0001, sym=sym, side=side))


def stock_fixed(P, m, m2, pad_m, y0, zt, L=.22, drop=.13, w=.04, zb=.022, bolt_m=None, dark_m=None):
    """A fixed solid stock: a wedge from the receiver to a tall butt, a second-tone panel let into each side with a
    lightening slot through it, a spacer and a butt plate."""
    y1 = y0 + L
    pts = [(y0, zt), (y1 - .014, zt - .012), (y1, zt - .024), (y1, zt - drop), (y1 - .03, zt - drop - .002), (y0 + .07, zb - .004), (y0, zb + .006)]
    P.append(prism('stock', pts, w, m, .004))
    P.append(plate('stock_panel', poly_offset(pts, .011), m2, w / 2 - .001, w / 2 + .0022, .002))
    slots(P, 'stock_slot', [(y0 + L * .64, zt - drop * .46, L * .32, .015, -.3)], w / 2 + .0022, dark_m or pad_m)
    P.append(prism('stock_spacer', [(y1, zt - .022), (y1 + .004, zt - .023), (y1 + .004, zt - drop + .001), (y1, zt - drop)], w + .002, m2, .001))
    P.append(rprism('stock_pad', [(y1 + .004, zt - .022), (y1 + .018, zt - .027), (y1 + .019, zt - drop + .007), (y1 + .004, zt - drop + .001)], w + .005, pad_m, .004))
    if bolt_m:
        hexbolts(P, [(y0 + .022, zt - .02), (y1 - .02, zt - drop + .022)], w / 2 + .0022, bolt_m, .003)


def stock_thumbhole(P, m, pad_m, y0, zt, L, drop, w, grip_pt, cheek_m=None, bolt_m=None):
    """A thumbhole stock: the comb, a tall butt, and a lower limb that runs forward to the foot of the pistol grip, so
    the hand goes through the stock."""
    y1 = y0 + L; gy, gz = grip_pt; zl = zt - drop
    P.append(rprism('stock_comb', [(y0, zt), (y1 - .02, zt - .008), (y1 - .02, zt - .052), (y0 + .1, zt - .046), (y0 + .03, zt - .036), (y0, zt - .04)], w, m, .006))
    P.append(rprism('stock_butt', [(y1 - .052, zt - .006), (y1, zt - .014), (y1, zl), (y1 - .04, zl - .004), (y1 - .074, zl + .034), (y1 - .052, zt - .05)], w + .002, m, .006))
    P.append(rprism('stock_limb', [(gy - .006, gz + .014), (gy + .03, gz + .016), (y1 - .066, zl + .03), (y1 - .042, zl - .002), (gy + .03, gz - .006), (gy - .008, gz - .004)],
                    w * .8, m, .005))
    P.append(rprism('stock_pad', [(y1, zt - .012), (y1 + .014, zt - .016), (y1 + .015, zl + .006), (y1, zl)], w + .006, pad_m, .004))
    if cheek_m:
        P.append(rprism('stock_cheek', [(y0 + .04, zt + .001), (y0 + .05, zt + .013), (y1 - .07, zt + .007), (y1 - .06, zt - .006)], w + .004, cheek_m, .005))
    if bolt_m:
        hexbolts(P, [(y0 + .02, zt - .02), (y1 - .024, zt - drop * .45)], (w + .002) / 2, bolt_m, .003)


def stock_adjustable(P, m, m2, pad_m, y0, zt, L, drop, w, zb, bolt_m=None):
    """A chassis stock: a knuckle on the receiver, a square spine, a cheek riser on two posts with its clamp knob, the
    butt carried on two rods (length of pull) with a hook under it, a butt pad."""
    y1 = y0 + L; hw = bolt_m or m2
    P.append(prism('stock_knuckle', [(y0, zt), (y0 + .03, zt), (y0 + .042, zt - .014), (y0 + .042, zb + .014), (y0 + .022, zb), (y0, zb)], w, m, .004))
    P.append(prism('stock_spine', [(y0 + .03, zt - .006), (y1 - .08, zt - .012), (y1 - .08, zt - .042), (y0 + .03, zt - .05)], w * .6, m2, .004))
    slots(P, 'spine_cut', [(y0 + .08 + i * .034, zt - .028, .022, .007, 0) for i in range(max(int((L - .16) / .034), 1))], w * .3, pad_m)
    P.append(rprism('stock_cheek', [(y0 + .06, zt + .012), (y0 + .072, zt + .027), (y1 - .1, zt + .023), (y1 - .09, zt + .008)], w * .86, m, .006))
    for yy in (y0 + .085, y1 - .115):
        P.append(lathe_z('cheekpost', [(-.03, 0), (-.03, .0042), (0, .0042), (0, 0)], (0, yy, zt + .014), hw, 10))
    P.append(lathe_x('cheekknob', [(0, .009), (.006, .009), (.008, .007), (.008, 0)], (w * .3, (y0 + y1) / 2 - .02, zt - .026), hw, 14, 1))
    for zz in (zt - .019, zt - .035):
        P.append(tube_('lop_rod', y1 - .02, y1 - .09, .0046, hw, zz, n=10))
    P.append(prism('stock_butt', [(y1 - .03, zt + .004), (y1, zt - .002), (y1, zt - drop), (y1 - .022, zt - drop - .004), (y1 - .052, zt - drop + .034),
                                  (y1 - .04, zt - drop + .046), (y1 - .03, zt - .058)], w, m, .004))
    P.append(rprism('stock_pad', [(y1, zt), (y1 + .014, zt - .004), (y1 + .015, zt - drop + .006), (y1, zt - drop)], w + .006, pad_m, .004))
    if bolt_m:
        hexbolts(P, [(y0 + .018, zt - .022), (y1 - .016, zt - .03), (y1 - .016, zt - drop + .03)], w / 2, bolt_m, .003)


def stock_folding(P, m, m2, pad_m, y0, zt, L, drop, w, bolt_m=None):
    """A side-folding stock: a hinge knuckle on the receiver with its pin, one tube back to a hooked butt, a thin
    brace under it."""
    y1 = y0 + L
    P.append(prism('stock_hinge', [(y0, zt), (y0 + .024, zt), (y0 + .032, zt - .01), (y0 + .032, zt - .05), (y0 + .022, zt - .06), (y0, zt - .06)], w * .9, m, .004))
    P.append(lathe_z('hinge_pin', [(-.066, 0), (-.066, .006), (.004, .006), (.006, .0046), (.006, 0)], (w * .28, y0 + .02, zt), bolt_m or m2, 12))
    P.append(tube_('stock_tube', y1 - .014, y0 + .028, .0105, m2, zt - .02, n=20))
    P.append(band('stock_collar', y0 + .05, .014, .013, m, zt - .02, 0, .003, 20, .001))
    P.append(K.rod('stock_brace', (0, y0 + .03, zt - .05), (0, y1 - .03, zt - drop + .036), .0048, m2))
    P.append(prism('stock_butt', [(y1 - .022, zt), (y1, zt - .004), (y1, zt - drop), (y1 - .036, zt - drop - .004), (y1 - .03, zt - drop + .026),
                                  (y1 - .02, zt - drop + .036)], w * .9, m, .004))
    P.append(rprism('stock_pad', [(y1, zt - .002), (y1 + .013, zt - .006), (y1 + .014, zt - drop + .006), (y1, zt - drop)], w * .9 + .005, pad_m, .004))


def stock_stub(P, m, m2, pad_m, y0, z, L=.13, r=.02, w=.06, h=.11):
    """A short buffer stock: a fat recoil tube with rings, a broad shoulder plate and pad."""
    y1 = y0 + L
    P.append(tube_('buffer', y1 - .02, y0, r, m2, z, n=28))
    for i in range(3):
        P.append(band('buffer_ring', y0 + .036 + i * .024, .008, r + .0035, m, z, 0, .0045, 28, .001))
    P.append(prism('stock_plate', [(y1 - .026, z + h * .46), (y1 - .008, z + h * .42), (y1 - .008, z - h * .56), (y1 - .026, z - h * .6)], w, m, .004))
    P.append(rprism('stock_pad', [(y1 - .008, z + h * .42), (y1 + .008, z + h * .37), (y1 + .009, z - h * .51), (y1 - .008, z - h * .56)], w + .004, pad_m, .005))


def dress(P, M, x, fin=None, line=None, bolts=None, name='dress'):
    """Layer a flank at x: a heat sink of real fins on a bolted base plate (fin = (y0, y1, z0, z1)); a pair of power /
    coolant lines along the side-view points `line` held by clamps; a row of inset fasteners (`bolts`)."""
    if fin:
        y0, y1, z0, z1 = fin
        P.append(plate(name + '_sink', [(y0 + .004, z0 - .003), (y0 + .004, z1 + .003), (y1 - .004, z1 + .003), (y1 - .004, z0 - .003)], M['dark'], x - .001, x + .0012,
                       .0008))
        fins(P, name + '_fin', y0, y1, z0, z1, x + .0012, M['metal'], n=max(int((y0 - y1) / .0075), 3), t=.0017, lift=.0042)
        hexbolts(P, [(y0 + .0015, z1 + .0006), (y1 - .0015, z0 - .0006)], x + .0012, M['trim'], .0013)
    if line:
        for k, dz in enumerate((0.0, -.0052)):
            for s in (1, -1):
                P.append(cable(name + '_line', [(s * (x + .0022), y, z + dz) for y, z in line], .0019 - k * .0004, M['dark'] if k == 0 else M['metal'], 8,
                               max(len(line) * 6, 12)))
        for t in (.1, .5, .9):
            f = t * (len(line) - 1); i = min(int(f), len(line) - 2); u = f - i
            yy = line[i][0] + (line[i + 1][0] - line[i][0]) * u; zz = line[i][1] + (line[i + 1][1] - line[i][1]) * u
            P.append(plate(name + '_clamp', [(yy + .003, zz + .0032), (yy + .003, zz - .0085), (yy - .003, zz - .0085), (yy - .003, zz + .0032)], M['metal'], x - .0005,
                           x + .0046, .0006))
    if bolts:
        hexbolts(P, bolts, x, M['trim'], .0016)


class Body:
    """A receiver in two layers, lofted through soft sections that CHANGE along the gun (a swell at the chamber, a
    waist over the grip, a taper into the stock and the handguard): a dark chassis, and armour shells standing proud
    of it with chamfered edges. The chassis and the light inside show in the gaps between the shells.

    secs = [(y, z0, z1, half width[, p])] from the rear forward (p: 2 an ellipse, 4-5 a rounded octagon); a curve is
    drawn through them. A point on the body is (y, a, d): a = the angle round the section (0 the left flank's middle,
    pi/2 the top, -pi/2 the belly), d = how far off the surface."""

    def __init__(self, secs):
        A = np.array([[s[0], s[1], s[2], s[3], s[4] if len(s) > 4 else 4.0] for s in secs], float)
        C, _ = spl(A, max(len(secs) * 10, 80))
        C = C[np.argsort(C[:, 0])]
        self.Y = C[:, 0]; self.C = C; self.y0 = float(A[0, 0]); self.y1 = float(A[-1, 0])

    def sec(self, y):
        return [float(np.interp(y, self.Y, self.C[:, k])) for k in (1, 2, 3, 4)]

    def pt(self, y, a, d=0.0):
        z0, z1, hw, p = self.sec(y)
        c, s = math.cos(a), math.sin(a); ex = 2.0 / max(p, 2.0)
        return (math.copysign(abs(c) ** ex, c) * (hw + d), y, (z0 + z1) / 2 + math.copysign(abs(s) ** ex, s) * ((z1 - z0) / 2 + d))

    def chassis(self, P, m, inset=.0026, step=.008, n=36, name='chassis'):
        ys = list(np.arange(self.y0, self.y1, -step)) + [self.y1]
        secs = []
        for y in ys:
            z0, z1, hw, p = self.sec(y)
            secs.append((y, z0 + inset, z1 - inset, max(hw - inset, .003), p))
        P.append(rloft(name, secs, m, n))

    def shell(self, P, name, m, ya, yb, a0, a1, t=.0026, d=0.0, mirror=True, ch=.0016, base=-.0028, ny=None, na=None):
        """An armour shell over the patch ya > yb, a0 < a1: t proud of the surface, its edges chamfered, a skirt down to
        the chassis all round (mirror = the same on the right flank)."""
        ny = ny or max(int((ya - yb) / .007), 2); na = na or max(int((a1 - a0) / .13), 2)
        ys = [ya, ya - ch] + [ya - ch + (yb - ya + 2 * ch) * i / ny for i in range(1, ny)] + [yb + ch, yb]
        ca = min(ch / .03, (a1 - a0) * .2)
        an = [a0, a0 + ca] + [a0 + ca + (a1 - a0 - 2 * ca) * j / na for j in range(1, na)] + [a1 - ca, a1]
        R, Cn = len(ys), len(an)
        loop = [(0, j) for j in range(Cn)] + [(i, Cn - 1) for i in range(1, R)] + [(R - 1, j) for j in range(Cn - 2, -1, -1)] + [(i, 0) for i in range(R - 2, 0, -1)]
        for sg in ((1, -1) if mirror else (1,)):
            Vv = []; F = []
            for i, y in enumerate(ys):
                for j, a in enumerate(an):
                    x, yy, z = self.pt(y, a, d + (t * .42 if (i in (0, R - 1) or j in (0, Cn - 1)) else t))
                    Vv.append((sg * x, yy, z))
            for i in range(R - 1):
                for j in range(Cn - 1):
                    F.append((i * Cn + j, i * Cn + j + 1, (i + 1) * Cn + j + 1, (i + 1) * Cn + j))
            k0 = len(Vv)
            for i, j in loop:
                x, yy, z = self.pt(ys[i], an[j], d + base)
                Vv.append((sg * x, yy, z))
            n = len(loop)
            for q in range(n):
                F.append((loop[q][0] * Cn + loop[q][1], loop[(q + 1) % n][0] * Cn + loop[(q + 1) % n][1], k0 + (q + 1) % n, k0 + q))
            P.append(mk(name, Vv, F, m, 40))

    def slats(self, P, name, m, ya, yb, a0, a1, n, share=.55, **kw):
        """A row of louvres: n narrow shells from ya forward to yb, the gaps between them open onto the chassis."""
        pitch = (ya - yb) / n
        for i in range(n):
            self.shell(P, name, m, ya - i * pitch, ya - i * pitch - pitch * share, a0, a1, ch=.001, **kw)

    def light(self, P, name, m, ya, yb, a0, a1, mirror=True):
        """Light lying ON the chassis (seen in a gap between shells, never on the outside)."""
        self.shell(P, name, m, ya, yb, a0, a1, t=.0007, d=-.0024, mirror=mirror, ch=.0005, base=-.0006)

    def collar(self, P, name, m, y, L, d=.003, n=40):
        """A raised band all round the body from y forward L."""
        secs = []
        for yy, dd in ((y, d * .35), (y - .0016, d), (y - L + .0016, d), (y - L, d * .35)):
            z0, z1, hw, p = self.sec(yy)
            secs.append((yy, z0 - dd, z1 + dd, hw + dd, p))
        P.append(rloft(name, secs, m, n))

    def studs(self, P, m, pts, r=.0022, d=.0026, n=6):
        """Inset fasteners at (y, a) on both flanks, their heads at the shells' height."""
        for y, a in pts:
            x, yy, z = self.pt(y, a, d - .0006)
            for sg in (1, -1):
                P.append(lathe_x('stud', [(-.001, r), (.0012, r), (.0016, r * .8), (.0016, r * .5), (.0008, r * .46), (.0008, 0)], (sg * x, yy, z), m, n, sg, phase=.5))


def ribbed_pad(P, m, y, z_top, z_bot, w, n=6, t=.014, name='stock_pad'):
    """A ribbed butt pad from y rearward: n rounded ribs with grooves between them."""
    h = (z_top - z_bot) / n
    for i in range(n):
        a = z_top - i * h; b = a - h * .82
        P.append(rprism(name, [(y, a), (y + t, a - .0015), (y + t, b + .0015), (y, b)], w, m, .0045, 3))
    P.append(prism(name + '_core', [(y - .001, z_top - .003), (y + t * .6, z_top - .004), (y + t * .6, z_bot + .004), (y - .001, z_bot + .003)], w - .008, m, .002))


def stock_soft(P, m, m2, pad_m, y0, zt, L, drop, w, zb, mode='open', grip_pt=None, cheek=True, bolt_m=None, fall=0.0, top0=None):
    """A shaped stock (never a plate): an oval comb that swells to the butt, a cheek rest lying on it, a lower limb (to
    the receiver: 'open'; to the foot of the pistol grip: 'thumb'), an upright rounded butt, a spacer and a ribbed
    pad. The openings between the limbs are real."""
    y1 = y0 + L; zl = zt - drop; hw = w / 2
    t0 = zt if top0 is None else top0                                # the comb leaves the receiver at its height and drops under the sight line
    P.append(sloft('stock_comb', [(y0 - .006, t0 - .046, t0, hw, 4.4), (y0 + L * .16, zt - .04, zt - .001, hw * .84, 3.0), (y0 + L * .55, zt - .042 - fall * .5, zt - .007 - fall * .5, hw * .88, 2.7),
                                  (y1 - .014, zt - .054 - fall, zt - .014 - fall, hw * 1.02, 3.2)], m, 22, 5))
    if cheek:
        P.append(sloft('stock_cheek', [(y0 + L * .2, zt - .008, zt + .006, hw * .7, 2.5), (y0 + L * .42, zt - .008, zt + .0125, hw * .93, 2.6),
                                       (y0 + L * .7, zt - .012, zt + .0105, hw * .93, 2.6), (y0 + L * .86, zt - .016, zt + .001, hw * .76, 2.5)], m2, 18, 5))
    if mode == 'thumb':
        gy, gz = grip_pt
        P.append(sloft('stock_limb', [(gy - .008, gz - .004, gz + .016, hw * .62, 3.0), (gy + .03, gz - .004, gz + .016, hw * .66, 2.8),
                                      (y1 - L * .4, (gz + zl) / 2 - .002, (gz + zl) / 2 + .02, hw * .64, 2.6), (y1 - .03, zl - .002, zl + .03, hw * .9, 3.0)], m, 18, 5))
    else:
        P.append(sloft('stock_limb', [(y0 - .006, zb, zb + .03, hw * .8, 3.6), (y0 + L * .25, zb - (zb - zl) * .2, zb - (zb - zl) * .2 + .024, hw * .62, 2.6),
                                      (y1 - L * .35, zl + (zb - zl) * .32, zl + (zb - zl) * .32 + .022, hw * .64, 2.6), (y1 - .03, zl - .002, zl + .03, hw * .9, 3.0)], m, 18, 5))
    P.append(rprism('stock_butt', chaikin([(y1 - .034, zt - .01 - fall), (y1, zt - .016 - fall), (y1, zl), (y1 - .036, zl - .004), (y1 - .05, zl + .03), (y1 - .034, zl + .05),
                                           (y1 - .028, zt - .056 - fall)], 1, sharp=(1, 2)), w + .002, m, .008, 4))
    P.append(prism('stock_spacer', [(y1, zt - .015 - fall), (y1 + .004, zt - .016 - fall), (y1 + .004, zl + .001), (y1, zl)], w + .003, m2, .001))
    ribbed_pad(P, pad_m, y1 + .004, zt - .016 - fall, zl + .001, w + .004)
    if bolt_m:
        hexbolts(P, [(y1 - .018, zt - .03 - fall), (y1 - .02, zl + .02)], (w + .002) / 2, bolt_m, .0026)


def stock_body(P, M, y0, zt, L, drop, w, zb, name='stock'):
    """A solid stock in the receiver's own two layers: a dark core waisted at the wrist, pale shells on its flanks
    with a chamfered lightening cut between them, a comb shell with a cheek swell, spacer and ribbed pad."""
    y1 = y0 + L; zl = zt - drop; hw = w / 2
    S = Body([(y0 - .006, zb, zt, hw, 4.4), (y0 + L * .14, zb - .002, zt - .002, hw * .78, 3.4), (y0 + L * .34, zb - (zb - zl) * .3, zt - .004, hw * .8, 3.2),
              (y0 + L * .6, zb - (zb - zl) * .62, zt - .008, hw * .9, 3.2), (y0 + L * .86, zl + .008, zt - .013, hw, 3.4), (y1, zl, zt - .016, hw, 3.8)])
    S.chassis(P, M['dark'], name=name + '_core')
    S.shell(P, name + '_comb', M['body'], y0 + L * .12, y1 - .006, .95, math.pi - .95, t=.003, mirror=False)
    S.shell(P, name + '_shell', M['body'], y0 + L * .1, y0 + L * .5, -.75, .7)
    S.shell(P, name + '_shell', M['body'], y0 + L * .56, y1 - .006, -.95, .7)
    S.shell(P, name + '_keel', M['metal'], y0 + L * .2, y1 - .01, -math.pi + 1.05, -1.05, t=.0022, mirror=False)
    S.studs(P, M['trim'], [(y0 + L * .16, 0.0), (y1 - .02, .3), (y1 - .02, -.6)])
    P.append(prism('stock_spacer', [(y1, zt - .017), (y1 + .004, zt - .018), (y1 + .004, zl + .001), (y1, zl)], w + .003, M['metal'], .001))
    ribbed_pad(P, M['grip'], y1 + .004, zt - .018, zl + .001, w + .004)
    return S


def hoop(name, y, z, w, h, r, t, depth, m, x=0.0, n=6):
    """A window frame standing across the gun: a rounded rectangle w x h (inside) centred at (x, z), corner radius r,
    its members t thick and `depth` deep, from y forward."""
    def loop(d):
        pts = []
        hw, hh, rr = w / 2 + d, h / 2 + d, r + d
        for cx, cz, a0 in ((hw - rr, hh - rr, 0), (-(hw - rr), hh - rr, math.pi / 2), (-(hw - rr), -(hh - rr), math.pi), (hw - rr, -(hh - rr), 1.5 * math.pi)):
            for i in range(n + 1):
                a = a0 + math.pi / 2 * i / n
                pts.append((x + cx + rr * math.cos(a), z + cz + rr * math.sin(a)))
        return pts
    inner, outer = loop(0.0), loop(t)
    N = len(inner)
    Vv = [(px, y, pz) for px, pz in inner] + [(px, y, pz) for px, pz in outer] + [(px, y - depth, pz) for px, pz in inner] + [(px, y - depth, pz) for px, pz in outer]
    F = []
    for i in range(N):
        j = (i + 1) % N
        F += [(i, j, N + j, N + i), (2 * N + i, 2 * N + j, 3 * N + j, 3 * N + i), (i, j, 2 * N + j, 2 * N + i), (N + i, N + j, 3 * N + j, 3 * N + i)]
    return mk(name, Vv, F, m, 40)


def checker(P, name, quad, x, m, nu=16, nv=9, h=.0008, sym=True, side=1):
    """Cut checkering as geometry: nu x nv small pyramids over the flank quad [(y, z) x 4] (a -> b along the first
    edge, d -> c along the opposite one) at x, on a thin closed backing."""
    a, b, c, d = quad

    def pt(u, v):
        return (a[0] * (1 - u) * (1 - v) + b[0] * u * (1 - v) + c[0] * u * v + d[0] * (1 - u) * v,
                a[1] * (1 - u) * (1 - v) + b[1] * u * (1 - v) + c[1] * u * v + d[1] * (1 - u) * v)
    for sg in ((1, -1) if sym else (side,)):
        Vv = []; F = []
        for i in range(nu):
            for j in range(nv):
                k = len(Vv)
                for u, v in ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)):
                    y, z = pt(u / nu, v / nv); Vv.append((sg * x, y, z))
                y, z = pt((i + .5) / nu, (j + .5) / nv); Vv.append((sg * (x + h), y, z))
                F += [(k, k + 1, k + 4), (k + 1, k + 2, k + 4), (k + 2, k + 3, k + 4), (k + 3, k, k + 4)]
        rim = [(i / nu, 0) for i in range(nu)] + [(1, j / nv) for j in range(nv)] + [(1 - i / nu, 1) for i in range(nu)] + [(0, 1 - j / nv) for j in range(nv)]
        k0 = len(Vv); n = len(rim)
        for u, v in rim:
            y, z = pt(u, v); Vv.append((sg * x, y, z))
        for u, v in rim:
            y, z = pt(u, v); Vv.append((sg * (x - .0012), y, z))
        for q in range(n):
            F.append((k0 + q, k0 + (q + 1) % n, k0 + n + (q + 1) % n, k0 + n + q))
        F.append(tuple(range(k0 + n, k0 + 2 * n)))
        P.append(mk(name, Vv, F, m, 30))


def stamp(P, name, items, x, m, lift=.0009, sym=True, side=1):
    """Pressed strengthening ribs on a sheet-steel flank: raised capsules (y, z, L, h[, ang]) in the flank's own metal."""
    for it in items:
        P.append(plate(name, capsule(*it), m, x - .0005, x + lift, lift * .75, sym=sym, side=side))


def rivets(P, pts, x, m, r=.0022, sym=True, side=1):
    """Domed rivet heads on a flank."""
    for y, z in pts:
        for s in ((1, -1) if sym else (side,)):
            P.append(lathe_x('rivet', [(-.0005, r), (.0004, r), (.0009, r * .82), (.0013, r * .5), (.0015, 0)], (s * x, y, z), m, 12, s))


def barrel_stepped(P, name, steps, z, m, bore, x=0.0, n=48):
    """A turned barrel in steps: steps = [(y, r), ...] from the breech forward, each radius holding to the next
    station; the last station is the muzzle's face. Shoulders are chamfered, the crown is recessed round a real bore."""
    prof = [(steps[0][0], 0), (steps[0][0], steps[0][1])]
    for (y, r), (y2, r2) in zip(steps, steps[1:-1]):
        c = min(.0014, abs(r - r2) * .9)
        prof += [(y2 + c, r), (y2 - c, r2)]
    ye, rl = steps[-1][0], steps[-2][1]
    prof += [(ye + .0012, rl), (ye, rl - .0012), (ye, bore + .002), (ye + .002, bore + .0006), (ye + .002, bore), (ye + .03, bore), (ye + .03, 0)]
    P.append(lathe(name, prof, m, z, x, n))


def dust_cover(P, y0, y1, z, x, m, h=.0165, side=-1, rib_m=None):
    """A port's dust cover hanging open under it: the hinge rod along the port's lower edge, the leaf with a pressed
    rib and its latch nub."""
    P.append(tube_('cover_hinge', y0, y1, .0019, m, z, side * (x + .0012), n=10))
    P.append(plate('cover_leaf', [(y0 - .002, z - .001), (y0 - .002, z - h), (y1 + .002, z - h), (y1 + .002, z - .001)], m, x, x + .0016, .0007, sym=False, side=side))
    P.append(plate('cover_rib', capsule((y0 + y1) / 2, z - h * .55, (y0 - y1) * .7, h * .32), rib_m or m, x + .0012, x + .0026, .0007, sym=False, side=side))
    P.append(lathe_x('cover_latch', [(0, .0022), (.0012, .0022), (.0018, .0012), (.0018, 0)], (side * (x + .0016), (y0 + y1) / 2, z - h + .003), m, 10, side))


def feed_lips(MAG, y_rear, y_front, z, w, m, brass, rake=0.0):
    """The top of a box magazine: two feed lips bent over the top round, the follower's edge behind it."""
    for s in (1, -1):
        MAG.append(prism('feed_lip', [(y_rear - .004, z - .004), (y_rear - .004, z + .0045), (y_front + .012, z + .0045 + rake), (y_front + .008, z - .004 + rake)], .0022, m, .0006,
                         x=s * (w * .5 - .0022)))
        MAG.append(prism('feed_lip_roll', [(y_rear - .008, z + .0035), (y_rear - .008, z + .0052), (y_front + .016, z + .0052 + rake), (y_front + .016, z + .0035 + rake)], .0052, m, .0005,
                         x=s * (w * .5 - .0042)))
    MAG.append(tube_('top_round', y_rear - .006, y_front + .004, min(w * .26, .0052), brass, z + .0012 + rake * .5, n=16))
    MAG.append(prism('follower', [(y_rear - .002, z - .006), (y_rear - .002, z - .001), (y_rear - .012, z - .001), (y_rear - .012, z - .006)], w * .6, m, .0006))


def swivel(P, y, z, m, x=0.0, down=True):
    """A sling swivel: a stud screwed into the wood, the loop hanging from it."""
    s = -1 if down else 1
    P.append(lathe_z('swivel_stud', [(0, 0), (0, .0042), (s * .003, .0042), (s * .005, .0026), (s * .009, .0026), (s * .009, 0)] if s > 0 else
                     [(-.009, 0), (-.009, .0026), (-.005, .0026), (-.003, .0042), (0, .0042), (0, 0)], (x, y, z), m, 12))
    P += K.sling_loop(y, z + s * .014, m, x=x, r=.0085)


def gas_block(P, y, L, zb, zt, m, r=.0135, pin_m=None):
    """A gas block clamped on the barrel from y forward L: the collar round the barrel, the port tower up to the gas
    tube at height zt, the tube's stub and plug, a cross pin."""
    P.append(band('gasblock', y, L, r, m, zb, 0, r - .006, 32, .0012))
    P.append(prism('gas_tower', [(y - .002, zb + r * .5), (y - .002, zt + .006), (y - L + .004, zt + .006), (y - L + .002, zb + r * .5)], r * 1.1, m, .0015))
    P.append(tube_('gas_stub', y + .004, y - L - .006, .0062, m, zt, n=20))
    P.append(lathe('gas_plug', [(y - L - .006, 0), (y - L - .006, .0052), (y - L - .012, .0052), (y - L - .014, .0036), (y - L - .014, 0)], pin_m or m, zt, 0, 6, sharp=20))
    P.append(K.cylx('gas_pin', .0022, r * 2 + .003, (0, y - L * .5, zb - r * .45), pin_m or m, 12, .0004))
