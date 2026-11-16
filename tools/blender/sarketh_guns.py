"""The Sarketh's weapons (the owner's design sheet, art/reference/sarketh/sarketh_design_sheet.png, "Sarketh weapons set",
2026-11-15): grown, not machined. A dark lacquered chitin shell (the barrel housings and the receiver), over it pale
chitin blades swept BACK along the top and under the barrel, an open bone frame for the grip and the stock (loops, not
solid blocks), white light in slits on the flanks and a row of amber slots along the barrel housing.

  gun_skr_rifle    assault rifle   "versatile and reliable": long housing, prongs over the muzzle, a looped stock
  gun_skr_sniper   sniper rifle    "precision at any range": a longer barrel, a short tube sight, a blade under the barrel
  gun_skr_cannon   heavy cannon    "maximum firepower": a broad housing round a fat barrel, a glowing bore
  gun_skr_pistol   pistol          "compact and efficient"
  gun_skr_blade    energy blade    "silent and lethal": a long hooked blade with a light along its edge, held by a grip
  gun_skr_grenade  grenade         "disruptive technology": a dark faceted egg in a chitin claw, a diamond of light

Frame: weapons.py's (origin at the top of the grip, barrel along -Y, Z up). Materials (names are an API, the energy line's
slots with this species' variants): gun_body__skr (the dark shell), gun_metal__skr (the pale blades and the frame),
gun_dark__skr (the scaled under-layer inside the frame), gun_glow (white; the game tints it with the rarity colour),
gun_glow__amber (the slots), gun_trim (the small fittings).

Run: blender --background --python tools/blender/sarketh_guns.py [-- skr_rifle ...]
"""
import math
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))
import bpy                      # noqa: E402
import bl                       # noqa: E402
import gunkit as K              # noqa: E402
import fleshkit as fk           # noqa: E402
from gunkit import B            # noqa: E402
from voidkit import talon, plate, prism, lathe, crystal, studs  # noqa: E402
from weapons import finish, GUN_SCALE  # noqa: E402

GUN_SCALE.update({'gun_skr_rifle': 1.0, 'gun_skr_sniper': 1.0, 'gun_skr_cannon': 1.0, 'gun_skr_pistol': 1.0, 'gun_skr_blade': 1.0,
                  'gun_skr_grenade': 1.0})


def mats():
    M = K.energy_mats()
    M['shell'] = fk.tmat('gun_body__skr', 'skr_dark', rough=.24, nstr=.8)
    M['bone'] = fk.tmat('gun_metal__skr', 'skr_armour', rough=.32, metal=.62)
    M['under'] = fk.tmat('gun_dark__skr', 'skr_skin', rough=.45)
    M['white'] = bl.mat('gun_glow', '#d6e6ff', 0, .35, emit='#d6e6ff', strength=9)
    M['amber'] = bl.mat('gun_glow__amber', '#ffb24a', 0, .35, emit='#ffb24a', strength=6)
    return M


def blade(P, name, spine, wid, M, x=0.0, t=.006, two=None, sym=True, **kw):
    """a pale blade: on both flanks at x, or one centre blade (x=0, ridged both faces)"""
    centre = x == 0.0
    P += talon(name, spine, wid, M['bone'], x=x, t=t, two=centre if two is None else two, sym=sym and not centre, **kw)


def slots(P, M, y0, y1, z, x, n, L=.020, h=.0045, mat='amber'):
    for i in range(n):
        y = y0 + (y1 - y0) * i / max(n - 1, 1)
        for s in (1, -1):
            P.append(B(f'slot{i}', (.004, L, h), (s * x, y, z), M[mat], .0012))


def housing(P, M, y0, y1, z, r, n=10, ribs=()):
    """the barrel's dark housing: a faceted tube with raised bands"""
    P.append(lathe('housing', [(y0, 0), (y0, r * .85), (y0 - .012, r), (y1 + .02, r * .96), (y1, r * .84), (y1, 0)], M['shell'], z, n=n,
                   phase=math.pi / n))
    for y in ribs:
        P.append(lathe('band', [(y + .006, 0), (y + .006, r * 1.06), (y, r * 1.1), (y - .006, r * 1.06), (y - .006, 0)], M['under'], z, n=n,
                       phase=math.pi / n))


def frame_grip(P, M, ang=.34, h=.12, w=.032):
    """the bone grip, its back swept into a spur, the trigger and an organic guard"""
    P.append(K.grip_profile('grip', M['bone'], ang=ang, h=h, w=w, y=0.0, z=.004))
    P += K.trigger_group(M, M['under'], M['trim'], y=-.012, z=.014, L=.072, drop=.05)
    blade(P, 'gripspur', [(.028, -.020), (.062, -.074), (.100, -.120)], [.020, .016, 0], M, t=.007)
    blade(P, 'gripfin', [(.010, .030), (.034, -.010), (.050, -.060)], [.010, .010, 0], M, x=w / 2 + .001, t=.003)


def looped_stock(P, M, y0=.05, L=.22, top=.10, low=.03):
    """an open stock: an upper and a lower bar of bone meeting at a butt plate, spurs off the butt"""
    y1 = y0 + L
    P.append(prism('stock_upper', [(y0, top - .012), (y0, top + .010), (y0 + L * .5, top + .016), (y1, top + .004), (y1 + .01, top - .016),
                                   (y1 - .004, top - .022), (y0 + L * .5, top - .006), (y0 + .02, top - .016)], .026, M['bone'], .004))
    P.append(prism('stock_lower', [(y0 + .01, low + .02), (y0 + L * .55, low - .03), (y1, low - .028), (y1 + .006, low - .010),
                                   (y0 + L * .55, low - .012), (y0 + .03, low + .034)], .022, M['bone'], .004))
    P.append(prism('stock_core', [(y0 + .02, top - .012), (y1 - .02, top - .016), (y1 - .02, low - .012), (y0 + L * .55, low - .008),
                                  (y0 + .03, low + .03)], .010, M['under'], .002))
    P.append(prism('butt', [(y1 - .012, top + .008), (y1 + .022, top - .002), (y1 + .028, low - .040), (y1 - .004, low - .036),
                            (y1 + .004, (top + low) / 2), (y1 - .010, top - .010)], .032, M['bone'], .004))
    blade(P, 'buttspur', [(y1 + .02, low - .03), (y1 + .06, low - .06), (y1 + .11, low - .08)], [.020, .014, 0], M, t=.008)
    blade(P, 'buttspur2', [(y1 + .01, top + .002), (y1 + .05, top + .03), (y1 + .09, top + .065)], [.016, .011, 0], M, t=.007)
    P.append(B('stocklight', (.0034, .05, .0042), (.0136, y0 + L * .5, top + .003), M['white'], .001))
    P.append(B('stocklight', (.0034, .05, .0042), (-.0136, y0 + L * .5, top + .003), M['white'], .001))


def crown(P, M, y_front, y_back, z, n, w0, rise, x=.021, t=.006):
    """blades along the top flanks, roots forward, swept back and up, each lying over the root of the one behind"""
    L = (y_back - y_front) / (n * .72)
    for i in range(n):
        ys = y_front + i * L * .72
        ww = w0 * (1 + .12 * i)
        blade(P, f'crown{i}', [(ys, z), (ys + L * .45, z + rise * .4 + .004 * i), (ys + L, z + rise + .008 * i)], [ww * .7, ww, 0], M, x=x - .0012 * i,
              t=t, lean=.25, bias=.35)
        # under each pale blade a dark one, longer and lower (the sheet's guns are layered dark and pale)
        P += talon(f'crown{i}d', [(ys - L * .12, z - .006), (ys + L * .40, z + rise * .25 - .004), (ys + L * 1.12, z + rise * .7)], [ww * .8, ww * .9, 0],
                   M['shell'], x=x + .002, t=t * .8, lean=.2, bias=.2)


def keel(P, M, y_front, y_back, z, n, w0, drop, x=.019, t=.005):
    L = (y_back - y_front) / (n * .72)
    for i in range(n):
        ys = y_front + i * L * .72
        blade(P, f'keel{i}', [(ys, z), (ys + L * .45, z - drop * .4), (ys + L, z - drop - .004 * i)], [w0 * .7, w0, 0], M, x=x, t=t, lean=-.2, bias=-.3)
        P += talon(f'keel{i}d', [(ys - L * .10, z + .005), (ys + L * .45, z - drop * .2 + .003), (ys + L * 1.1, z - drop * .7)], [w0 * .8, w0 * .9, 0],
                   M['shell'], x=x + .002, t=t * .8, lean=-.2, bias=-.2)


# ------------------------------------------------------------------ organic frames (sculpted, not extruded)
import numpy as np            # noqa: E402
import sdf                    # noqa: E402


class Frame:
    """A gun's grown body: tagged distance primitives (dark shell or pale bone) smooth-unioned into one surface, meshed
    with Surface Nets, every face given the material of what it grew from."""

    def __init__(self):
        self.S = fk.Sculpt(seed=2)

    def bone(self, pts, r, k=.010):
        return self._chain(pts, r, 'bone', k)

    def shell(self, pts, r, k=.012):
        return self._chain(pts, r, 'shell', k)

    def _chain(self, pts, r, mat, k):
        """a smooth tube: its own segments joined exactly (a soft join between segments of one tube swelled every joint
        into a bead), the whole tube joined softly to what was there before"""
        prims = self.S.chain(pts, r, None, mat, '#ffffff', .0015)
        if prims:
            prims[0].k = k
        return prims

    def ell(self, c, r, mat='shell', k=.012, R=None):
        return self.S.ell(c, r, None, mat, '#ffffff', k, R=R)

    def cut(self, c, r, k=.004, R=None):
        return self.S.cut_ell(c, r, None, None, '#ffffff', k, R=R)

    def mesh(self, name, M, lo, hi, h=.0011, target=30000):
        V, Q = sdf.mesh(lambda P: self.S.field(P, disp=False), lo, hi, h)
        o = fk.to_object(name, V, Q)
        fk.decimate_to(o, target)
        V = sdf.project(lambda P: self.S.field(P, disp=False), fk.verts(o), 2, max_step=h * .5)
        fk.set_verts(o, V)
        D = np.abs(self.S.distances(V.astype(np.float32)))
        owner = D.argmin(1)
        names = ['shell', 'bone']
        for nm in names:
            o.data.materials.append(M[nm])
        me = o.data
        vm = np.array([names.index(self.S.prims[i].mat) if self.S.prims[i].mat in names else 0 for i in owner])
        lt = np.empty(len(me.polygons), np.int32); me.polygons.foreach_get('loop_total', lt)
        vi = np.empty(len(me.loops), np.int32); me.loops.foreach_get('vertex_index', vi)
        ls = np.concatenate([[0], np.cumsum(lt)[:-1]])
        fm = np.array([np.bincount(vm[vi[a:a + n]]).argmax() for a, n in zip(ls, lt)], np.int32)
        me.polygons.foreach_set('material_index', fm)
        N = sdf.normals(lambda P: self.S.field(P, disp=False), V)
        me.normals_split_custom_set_from_vertices([tuple(v) for v in N])
        bl.uv_box(o, .22)
        return o


def gun_frame(F, y_back, y_front, z, r_body, stock=True, stock_len=.23, grip_h=.115, guard=True, top=.10, low=.03):
    """the shared organic frame: a raked bone grip grown out of the receiver's belly, the trigger guard as a loop of bone
    to the receiver's front, a stock of two bars of bone meeting at a butt, all smooth-unioned into the dark body"""
    g = lambda a, b: (0.0, .010 + a * .94 + b * .34, .010 - b * .94 + a * .34)      # along / down a grip raked back
    F.bone([g(0, -.03), g(.002, .03), g(.004, .07), g(.004, grip_h)], [.0175, .0172, .0168, .0160], k=.012)
    F.ell(g(.010, .05), (.0150, .0225, .055), 'bone', k=.010, R=sdf.rot((1, 0, 0), -.34).T)
    F.ell(g(.012, grip_h + .006), (.017, .026, .011), 'bone', k=.008)                        # the heel
    if guard:
        F.bone([g(-.016, .010), (0, -.040, -.050), (0, -.090, -.050), (0, -.125, -.018), (0, -.140, z - r_body * .7)], [.0065, .0060, .0062, .0068, .009],
               k=.007)
    if stock:
        y1 = y_back + stock_len
        F.bone([(0, y_back - .02, top - .004), (0, y_back + stock_len * .45, top + .010), (0, y1 - .02, top - .004), (0, y1 + .004, top - .030)],
               [.0130, .0112, .0118, .0150], k=.010)
        F.bone([g(.020, .020), (0, y_back + stock_len * .40, low - .030), (0, y1 - .02, low - .030), (0, y1 + .006, low - .006)],
               [.0130, .0108, .0112, .0150], k=.010)
        F.bone([(0, y1 + .004, top - .030), (0, y1 + .012, (top + low) / 2 - .02), (0, y1 + .006, low - .006)], [.0155, .0175, .0155], k=.008)
        F.ell((0, y1 + .012, (top + low) / 2 - .02), (.017, .012, .060), 'bone', k=.008)          # the butt pad


# ------------------------------------------------------------------ the guns
# The sheet's guns, read closely: the barrel is a BUNDLE of long dark slats stacked one over another, tapering to a
# pointed nose, amber light burning in the gaps between them; the receiver a dark glossy mass with oval windows
# through it; a few BIG pale blades curving back over it with hooked tips (not rows of small spikes); the grip, the
# guard and the stock open loops of pale metal.
def trigger(P, M, y=-.014, z=.004):
    """a thin blade (the hand's fit finds a trigger by how thin it is)"""
    P += talon('trigger', [(y, z), (y - .006, z - .022), (y + .002, z - .040)], [.009, .008, 0], M['trim'], x=0, t=.0032, two=True, sym=False, n=8)


def bundle(P, M, y0, y1, z, h, w, nose=.06, glow_gap=True, n_dash=6):
    """the barrel: an upper and a lower slat round a core tube, each a chamfered blade in the side view, the upper one
    running on to a pointed nose; dashes of amber light in the gaps between them"""
    gap = .0045
    up = [(y0, z + h * .5), (y1 + nose * .4, z + h * .5 - .004), (y1 - nose * .6, z + h * .18), (y1 + nose * .1, z + gap), (y0, z + gap + .002)]
    lo = [(y0, z - gap - .002), (y1 + nose * .2, z - gap), (y1 - nose * .1, z - h * .30), (y1 + nose * .5, z - h * .5 + .004), (y0, z - h * .5)]
    P.append(prism('slat_up', up, w, M['shell'], min(.004, w * .12)))
    P.append(prism('slat_lo', lo, w * .92, M['shell'], min(.004, w * .12)))
    P.append(lathe('core', [(y0, 0), (y0, h * .17), (y1 + .01, h * .17), (y1, h * .12), (y1, 0)], M['under'], z, n=10, phase=math.pi / 10))
    P.append(prism('rail_mid', [(y0, z + gap * .4), (y1 + nose * .3, z + gap * .4), (y1 + nose * .3, z - gap * .4), (y0, z - gap * .4)], w * .7,
                   M['shell'], .001))
    if glow_gap:
        for k in range(n_dash):
            ya = y0 + (y1 - y0) * (k + .15) / n_dash
            yb = y0 + (y1 - y0) * (k + .75) / n_dash
            for zz in (z + gap * .5 + .001, z - gap * .5 - .001):
                P.append(B(f'dash{k}', (w * .80, abs(yb - ya), .0028), (0, (ya + yb) / 2, zz), M['amber'], .0006))
    # a second, thinner slat over the first, stopping short of the nose; dark plates along each flank of the bundle with
    # a pale edge, so the barrel is layered side to side as well as top to bottom (the sheet's)
    top = z + h * .5
    P.append(prism('slat_top', [(y0 + .02, top - .002), (y0 + (y1 - y0) * .62, top + .002), (y0 + (y1 - y0) * .70, top - h * .10),
                                (y0 + .02, top - h * .12)], w * .62, M['shell'], .0025))
    L = y1 - y0
    for k, (t0, t1) in enumerate(((.05, .42), (.36, .78))):
        pts = [(y0 + L * t0, z + h * .30), (y0 + L * t1, z + h * .22), (y0 + L * (t1 + .05), z), (y0 + L * t1, z - h * .24),
               (y0 + L * t0, z - h * .30)]
        P.append(plate(f'cheek{k}', pts, M['shell'], w * .5 - .002, w * .5 + .0045, .0016))
        for q in range(3):                                   # amber slots along each side plate
            yq = y0 + L * (t0 + (t1 - t0) * (q + .5) / 3.3)
            for sd in (1, -1):
                P.append(B(f'cheekslot{k}{q}', (.003, abs(L) * (t1 - t0) * .16, .0036), (sd * (w * .5 + .0050), yq, z + h * .02), M['amber'], .0008))
        P += talon(f'cheekedge{k}', [(y0 + L * t0, z + h * .32), (y0 + L * (t0 + t1) * .5, z + h * .30), (y0 + L * (t1 + .06), z + h * .02)],
                   [.006, .008, 0], M['bone'], x=w * .5 + .0035, t=.003)
    for sd in (1, -1):
        P.append(B('muzzlelight', (.003, .010, .004), (sd * w * .36, y1 + .006, z + gap * .5), M['amber'], .001))
        P.append(B('muzzlelight', (.003, .010, .004), (sd * w * .36, y1 + .006, z - gap * .5), M['amber'], .001))


def receiver(F, y0, y1, z, rx, rz, windows=2):
    """the receiver: a dark glossy mass, swollen in the middle, its belly running down into the grip, oval windows
    cut through it side to side"""
    L = y0 - y1
    F.ell((0, (y0 + y1) / 2, z), (rx, L * .55, rz), 'shell', k=.012)
    F.ell((0, (y0 + y1) / 2 + L * .12, z + rz * .55), (rx * .72, L * .40, rz * .55), 'shell', k=.014)
    F.ell((0, y0 - L * .18, z - rz * .55), (rx * .85, L * .22, rz * .65), 'shell', k=.014)
    for k in range(windows):
        yc = y0 - L * (.30 + .40 * k / max(windows - 1, 1))
        F.cut((0, yc, z + rz * .05), (rx * 2.5, L * .085, rz * .32), k=.004)


def oval_stock(F, y0, L, top, low):
    """an open loop of pale metal: the stock's outline with an oval window through it, a butt at its end"""
    yc, zc = y0 + L * .55, (top + low) / 2
    F.ell((0, yc, zc), (.015, L * .55, (top - low) * .62), 'bone', k=.012)
    F.cut((0, yc + L * .02, zc), (.05, L * .40, (top - low) * .40), k=.004)
    F.ell((0, y0 + L * 1.05, zc - .01), (.017, .016, (top - low) * .78), 'bone', k=.010)


def grip_loop(F, z_body, guard=True, grip_h=.112):
    g = lambda a, b: (0.0, .010 + a * .94 + b * .34, .010 - b * .94 + a * .34)
    F.bone([g(0, -.03), g(.002, .03), g(.004, .07), g(.004, grip_h)], [.0175, .0172, .0168, .0160], k=.012)
    F.ell(g(.010, .05), (.0150, .0225, .055), 'bone', k=.010, R=sdf.rot((1, 0, 0), -.34).T)
    F.ell(g(.012, grip_h + .006), (.017, .026, .011), 'bone', k=.008)
    F.cut(g(.006, .055), (.05, .007, .024), k=.003)                                   # a slot through the grip's heel
    if guard:
        F.bone([g(-.016, .010), (0, -.040, -.052), (0, -.092, -.050), (0, -.126, -.016), (0, -.138, z_body - .02)], [.0068, .0062, .0064, .0070, .0095],
               k=.007)


def fins(P, M, y_front, y_back, top, s=1.0, n_side=2):
    """the big pale blades: one long and low over the front, a tall hooked one in the middle, one at the back; down each
    flank a blade curving along the receiver; a dark blade under each pale one"""
    L = y_back - y_front
    blade(P, 'finlow', [(y_front, top - .006 * s), (y_front + L * .30, top + .010 * s), (y_front + L * .52, top + .016 * s)],
          [.026 * s, .030 * s, 0], M, x=.012 * s, t=.006 * s, lean=.35, bias=.3)
    P += talon('finlow_d', [(y_front - L * .04, top - .012 * s), (y_front + L * .30, top + .002 * s), (y_front + L * .58, top + .006 * s)],
               [.024 * s, .028 * s, 0], M['shell'], x=.015 * s, t=.005 * s, lean=.3, bias=.2)
    blade(P, 'finhook', [(y_front + L * .40, top + .002 * s), (y_front + L * .58, top + .036 * s), (y_front + L * .74, top + .052 * s),
                         (y_front + L * .82, top + .044 * s)], [.040 * s, .034 * s, .018 * s, 0], M, t=.008 * s)
    blade(P, 'finrear', [(y_front + L * .70, top - .002 * s), (y_front + L * .88, top + .024 * s), (y_back + L * .08, top + .030 * s)],
          [.034 * s, .026 * s, 0], M, t=.007 * s)
    for k in range(n_side):
        a = y_front + L * (.10 + .45 * k)
        blade(P, f'flank{k}', [(a, top - .040 * s), (a + L * .18, top - .052 * s), (a + L * .36, top - .044 * s), (a + L * .46, top - .030 * s)],
              [.016 * s, .024 * s, .020 * s, 0], M, x=.030 * s, t=.005 * s, bias=.3)
        P += talon(f'flank{k}d', [(a - L * .03, top - .030 * s), (a + L * .18, top - .036 * s), (a + L * .40, top - .028 * s)],
                   [.014 * s, .018 * s, 0], M['shell'], x=.028 * s, t=.004 * s)


def skr_rifle():
    bl.reset(); M = mats(); P = []
    F = Frame()
    receiver(F, .05, -.26, .086, .036, .060, windows=3)
    grip_loop(F, .086)
    oval_stock(F, .040, .24, .124, .006)
    F.bone([(0, .040, .108), (0, .070, .110)], [.010, .010], k=.010)
    F.bone([(0, .040, .030), (0, .070, .020)], [.010, .010], k=.010)
    P.append(F.mesh('frame', M, (-.05, -.30, -.15), (.05, .34, .17)))
    trigger(P, M)
    bundle(P, M, -.20, -.62, .084, .084, .050, nose=.09)
    fins(P, M, -.32, .06, .140, s=1.35, n_side=2)
    blade(P, 'buttspur', [(.282, .012), (.315, -.012), (.350, -.026)], [.018, .012, 0], M, t=.007)
    for sd in (1, -1):
        P.append(B('slit', (.003, .060, .005), (sd * .0300, -.090, .090), M['white'], .0012, rot=(.10, 0, 0)))
        P.append(B('slit2', (.003, .032, .004), (sd * .0285, -.170, .070), M['white'], .0010, rot=(-.08, 0, 0)))
    finish('gun_skr_rifle', P, (0, -.71, .084), (0, -.36, .040), (0, -.05, .16))


def skr_sniper():
    bl.reset(); M = mats(); P = []
    F = Frame()
    receiver(F, .05, -.29, .084, .034, .056, windows=3)
    grip_loop(F, .084)
    oval_stock(F, .040, .27, .120, .004)
    F.bone([(0, .040, .106), (0, .070, .108)], [.010, .010], k=.010)
    F.bone([(0, .040, .026), (0, .070, .016)], [.010, .010], k=.010)
    F.bone([(0, -.020, .112), (0, -.020, .140)], [.0080, .0070], k=.008)
    F.bone([(0, -.150, .110), (0, -.150, .140)], [.0080, .0070], k=.008)
    F.shell([(0, .025, .150), (0, -.200, .150)], [.0150, .0165], k=.006)
    P.append(F.mesh('frame', M, (-.05, -.33, -.15), (.05, .37, .19), target=32000))
    trigger(P, M)
    bundle(P, M, -.22, -.84, .082, .070, .044, nose=.10, n_dash=8)
    fins(P, M, -.34, .06, .136, s=1.25)
    blade(P, 'bipodblade', [(-.40, .050), (-.50, .006), (-.60, -.060)], [.024, .018, 0], M, t=.008)
    P.append(lathe('scopelens', [(-.198, .0150), (-.204, .0150), (-.204, 0)], M['lens'], .150, n=16))
    P.append(lathe('scopeglow', [(-.07, .0168), (-.10, .0168), (-.10, .0150), (-.07, .0150)], M['white'], .150, n=12))
    for sd in (1, -1):
        P.append(B('slit', (.003, .070, .005), (sd * .0290, -.100, .090), M['white'], .0012, rot=(.10, 0, 0)))
    finish('gun_skr_sniper', P, (0, -.94, .082), (0, -.42, .044), (0, -.08, .150), scoped=True)


def skr_cannon():
    bl.reset(); M = mats(); P = []
    F = Frame()
    receiver(F, .05, -.27, .092, .046, .072, windows=3)
    grip_loop(F, .090, grip_h=.118)
    oval_stock(F, .040, .22, .126, .012)
    F.bone([(0, .040, .122), (0, .070, .124)], [.012, .012], k=.010)
    F.bone([(0, .040, .030), (0, .070, .020)], [.012, .012], k=.010)
    F.bone([(0, -.100, .148), (0, -.230, .148)], [.008, .008], k=.010)
    F.bone([(0, -.100, .130), (0, -.100, .148)], [.008, .008], k=.008)
    F.bone([(0, -.230, .130), (0, -.230, .148)], [.008, .008], k=.008)
    P.append(F.mesh('frame', M, (-.07, -.32, -.16), (.07, .32, .19), target=32000))
    trigger(P, M)
    bundle(P, M, -.22, -.58, .090, .110, .072, nose=.05, n_dash=5)
    P.append(lathe('mouth', [(-.555, 0), (-.555, .030), (-.570, .034), (-.640, .034), (-.648, .028), (-.648, .020), (-.62, .020), (-.62, 0)], M['bone'],
                   .088, n=12, phase=math.pi / 12))
    P.append(lathe('core', [(-.620, .020), (-.620, 0)], M['white'], .088, n=18))
    P.append(lathe('coreamber', [(-.628, .0205), (-.636, .0205), (-.636, .0170), (-.628, .0170)], M['amber'], .088, n=18))
    fins(P, M, -.30, .06, .162, s=1.5, n_side=2)
    blade(P, 'buttspur', [(.262, .014), (.300, -.012), (.340, -.028)], [.020, .014, 0], M, t=.008)
    for sd in (1, -1):
        P.append(B('chevron', (.003, .046, .007), (sd * .0410, -.110, .106), M['white'], .0012, rot=(.5, 0, 0)))
        P.append(B('chevron', (.003, .046, .007), (sd * .0410, -.110, .086), M['white'], .0012, rot=(-.5, 0, 0)))
    finish('gun_skr_cannon', P, (0, -.65, .088), (0, -.40, .046), (0, -.05, .17))


def skr_pistol():
    bl.reset(); M = mats(); P = []
    F = Frame()
    receiver(F, .045, -.15, .074, .027, .044, windows=2)
    grip_loop(F, .072, grip_h=.098)
    F.bone([(0, .040, .090), (0, .080, .070), (0, .100, .045)], [.008, .007, .006], k=.008)          # a tail of bone over the hand
    P.append(F.mesh('frame', M, (-.04, -.18, -.14), (.04, .14, .14), h=.0009, target=18000))
    trigger(P, M)
    bundle(P, M, -.11, -.25, .074, .056, .034, nose=.05, n_dash=2)
    fins(P, M, -.17, .05, .112, s=.85, n_side=1)
    for sd in (1, -1):
        P.append(B('slit', (.003, .040, .005), (sd * .0222, -.050, .080), M['white'], .0012, rot=(.08, 0, 0)))
    finish('gun_skr_pistol', P, (0, -.27, .072), (0, -.03, .00), (0, -.03, .11))


def skr_blade():
    """the energy blade: a long hooked blade of dark shell with a line of light along its edge, a pale back blade
    along its spine, a few hooked spurs; held by a pale grip (the blade running forward along -Y)"""
    bl.reset(); M = mats(); P = []
    F = Frame()
    F.bone([(0, .000, .010), (0, .004, -.050), (0, .008, -.120)], [.0165, .0160, .0150], k=.010)
    F.ell((0, .006, -.128), (.018, .022, .012), 'bone', k=.008)
    F.ell((0, -.020, .030), (.020, .060, .024), 'shell', k=.012)
    F.cut((0, -.030, .030), (.05, .018, .008), k=.003)
    F.bone([(0, .020, .030), (0, .070, .055), (0, .100, .090)], [.010, .007, .004], k=.008)
    P.append(F.mesh('frame', M, (-.04, -.12, -.16), (.04, .14, .12), h=.0009, target=12000))
    spine = [(-.05, .030), (-.24, .052), (-.46, .048), (-.66, .010), (-.80, -.050)]
    P += talon('edge', spine, [.056, .066, .058, .036, 0], M['shell'], x=0, t=.007, two=True, sym=False, glow=M['white'], g=.0022, n=24)
    P += talon('edgebone', [(-.06, .050), (-.22, .078), (-.40, .074), (-.56, .052)], [.022, .028, .020, 0], M['bone'], x=0, t=.009, two=True,
               sym=False, n=18)
    for i, y in enumerate((-.16, -.34)):
        blade(P, f'backspur{i}', [(y, .076), (y + .04, .100), (y + .09, .108)], [.020, .014, 0], M, t=.006)
    for y in (-.10, -.20, -.30, -.40):
        for sd in (1, -1):
            P.append(B('edgeamber', (.003, .022, .004), (sd * .0074, y, .040), M['amber'], .001))
    finish('gun_skr_blade', P, (0, -.80, -.05), (0, .0, -.06), (0, -.05, .08))


def skr_grenade():
    """the grenade: a dark faceted egg held in a three-fingered claw of pale metal, a diamond of light on its face"""
    bl.reset(); M = mats(); P = []
    F = Frame()
    F.ell((0, 0, 0), (.034, .034, .046), 'shell', k=.004)
    for k in range(9):
        a = 2 * np.pi * k / 9
        for zz in (-.022, .012):
            F.cut((.040 * np.cos(a), .040 * np.sin(a), zz), (.010, .010, .012), k=.003)
    for k in range(3):
        a = 2 * np.pi * k / 3 + .4
        c, s_ = np.cos(a), np.sin(a)
        pts = [(.000, .000, .052), (.022 * c, .022 * s_, .046), (.036 * c, .036 * s_, .020), (.040 * c, .040 * s_, -.012), (.030 * c, .030 * s_, -.040)]
        F.bone(pts, [.009, .008, .0075, .006, .003], k=.006)
    F.bone([(0, 0, .046), (0, 0, .064)], [.012, .008], k=.006)
    P.append(F.mesh('frame', M, (-.06, -.06, -.06), (.06, .06, .08), h=.0006, target=12000))
    P.append(crystal('diamond', (0, -.030, .002), (0, -.046, .002), .011, M['white'], n=4, k0=.5, k1=.5))
    P.append(B('pin', (.006, .012, .010), (0, 0, .070), M['trim'], .002))
    finish('gun_skr_grenade', P, (0, -.05, 0), (0, 0, 0), (0, -.05, .02))


# ------------------------------------------------------------------ the guns, traced off the owner's sheet
# (the owner, 2026-11-15: "make the guns an exact copy of the image cm by cm"). tools/reference/trace_sheet.py traces each
# weapon's side view off the sheet (2 mm a pixel): its outline with its see-through windows, and what every part is
# (dark plate, pale metal, amber or white light) and how the painter lit it. Here that side view is made solid: the
# outline is exact; the thickness across the gun (which the sheet does not show) is a pillow, thin where the part is thin
# and fuller in the body; the pale metal stands proud of the dark, the lights are set in, and the painted highlights (the
# ridges and edges the painter lit) are raised as real relief.
TRACE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'reference', 'sarketh_trace')
# per gun: the widest it is across (m), and where its grip is on the sheet as a share of its length and height (the
# origin of the gun's frame: the top of the grip), or None for a gun with no grip of that kind
TRACED = {
    'skr_rifle': dict(width=.090, k=.95, grip=(.700, .560), muzzle_z=.47, sight_z=.30),
    'skr_sniper': dict(width=.060, grip=(.720, .600), muzzle_z=.50, sight_z=.22),
    'skr_cannon': dict(width=.080, grip=(.700, .600), muzzle_z=.47, sight_z=.30),
    'skr_pistol': dict(width=.046, grip=(.700, .560), muzzle_z=.55, sight_z=.25),
    'skr_blade': dict(width=.026, grip=(.930, .600), muzzle_z=.70, sight_z=.30),
    'skr_grenade': dict(width=.080, grip=(.500, .500), muzzle_z=.50, sight_z=.30, round=True),
}


def _bilinear(A, u, v):
    """A sampled at fractional pixel (u = column, v = row), clamped"""
    H, W = A.shape
    u = np.clip(u, 0, W - 1.001); v = np.clip(v, 0, H - 1.001)
    i0 = np.floor(v).astype(np.int64); j0 = np.floor(u).astype(np.int64)
    fv = v - i0; fu = u - j0
    return (A[i0, j0] * (1 - fu) * (1 - fv) + A[i0, j0 + 1] * fu * (1 - fv) + A[i0 + 1, j0] * (1 - fu) * fv + A[i0 + 1, j0 + 1] * fu * fv)


def _blur2(A, r):
    """a box blur of r pixels each way, twice (near a gaussian), edges held"""
    for _ in range(2):
        for ax in (0, 1):
            P_ = np.pad(A, [(r, r) if a == ax else (0, 0) for a in (0, 1)], mode='edge')
            c = np.cumsum(P_, axis=ax, dtype=np.float64)
            c = np.concatenate([np.zeros_like(np.take(c, [0], axis=ax)), c], axis=ax)
            n = A.shape[ax]
            A = (np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=ax) - np.take(c, np.arange(0, n), axis=ax)) / (2 * r + 1)
    return A


def traced(name):
    bl.reset(); M = mats(); P = []
    T = np.load(os.path.join(TRACE, name + '.npz'))
    mask, cls, lum, px = T['mask'], T['cls'], T['lum'], float(T['px'])
    spec = TRACED[name]
    H, W = mask.shape
    gu, gv = spec['grip'][0] * W, spec['grip'][1] * H              # the grip's top on the sheet (pixels): the origin
    inside = T['inside'] * px
    outside = T['outside'] * px
    sd = np.where(mask, -inside, outside)                            # signed distance to the outline, metres
    wmax = spec['width'] * .5
    # the body rounds out with its height (a barrel is round, a blade thin), reaching its full width only in the thick core
    hw = wmax * np.clip(inside / .034, 0, 1) ** .50
    # every pale region a plate of its own, standing 4.5 mm proud of the dark with a chamfered edge (the sheet's layering)
    pale_in = T['pale_in'] * px
    hw = hw + .0045 * np.clip(pale_in / .0025, 0, 1) + np.where(cls >= 3, -.0012, 0) + (lum - .25).clip(-.15, .5) * .0018
    hw = np.maximum(_blur2(hw, 2), .0012)                             # (softened: a step in it was a stair on the surface)
    sd = _blur2(sd, 1)
    if spec.get('round'):                                             # the grenade is round: its width follows its height
        hw = np.maximum(hw, wmax * np.sqrt(np.clip(inside / (.5 * H * px), 0, 1)))

    def field(Pt):
        Pt = np.asarray(Pt, np.float64)
        u = gu + Pt[:, 1] / px                                        # +Y (back, toward the butt) is the image's right
        v = gv - Pt[:, 2] / px
        d2 = _bilinear(sd, u, v)
        out = (u < 0) | (u > W - 1) | (v < 0) | (v > H - 1)
        d2 = np.where(out, .02, d2)
        h = _bilinear(hw, u, v)
        return np.maximum(d2, np.abs(Pt[:, 0]) - h).astype(np.float32)
    lo = (-wmax - .008, -gu * px - .004, (gv - H) * px - .004)
    hi = (wmax + .008, (W - gu) * px + .004, gv * px + .004)
    V, Q = sdf.mesh(field, lo, hi, .0009 if name != 'skr_grenade' else .0005)
    o = fk.to_object('frame', V, Q)
    bpy.context.view_layer.objects.active = o
    md = o.modifiers.new('smooth', 'CORRECTIVE_SMOOTH')              # what is left of the grid smoothed away, the volume kept
    md.iterations = 6; md.factor = .5; md.smooth_type = 'SIMPLE'; md.use_only_smooth = True if hasattr(md, 'use_only_smooth') else False
    bpy.ops.object.modifier_apply(modifier=md.name)
    fk.decimate_to(o, 46000 if name not in ('skr_pistol', 'skr_grenade') else 26000)
    names = ['shell', 'bone', 'amber', 'white']
    for nm in names:
        o.data.materials.append(M[nm])
    me = o.data
    cen = np.array([p_.center[:] for p_ in me.polygons])
    u = gu + cen[:, 1] / px
    v = gv - cen[:, 2] / px
    c = cls[np.clip(np.round(v).astype(int), 0, H - 1), np.clip(np.round(u).astype(int), 0, W - 1)]
    me.polygons.foreach_set('material_index', np.array([{1: 0, 2: 1, 3: 2, 4: 3}.get(int(k), 0) for k in c], np.int32))
    bl.uv_box(o, .22)
    K.harden(o, 40)
    P.append(o)
    # sockets: the muzzle at the front end of the outline, the support hand under the fore end, the sight over the receiver
    cols = np.nonzero(mask.any(0))[0]
    front = cols.min()
    rows = np.nonzero(mask[:, front:front + 4].any(1))[0]
    mz = (gv - rows.mean()) * px
    muzzle = (0, (front - gu) * px, mz)
    fore = (0, (front - gu) * px * .55, mz - .03)
    sight = (0, -.05, (gv - spec['sight_z'] * H) * px)
    if name != 'skr_blade' and name != 'skr_grenade':
        trigger(P, M)
    finish('gun_' + name, P, muzzle, fore, sight, scoped=name == 'skr_sniper')


# ------------------------------------------------------------------ crisp: hard parts placed by the trace
# (the owner, 2026-11-15, on the traced blob: "blurry and seem smudged ... all parts can be seen properly"). Every shape
# the trace found is built as a part of its own with hard, bevelled edges: the body as three bevelled layers (the full
# outline, then two inner tiers stepping out toward its core, so it is layered in depth as the sheet's guns are), every
# pale region a plate of its own standing proud on the layer under it, every light set in its own part. The outline,
# the windows and where each plate and light sits are the sheet's; the depth is the tiers'.
def _curve_solid(name, rings, half, bevel, mat, x, px, gu, gv, res=1):
    """rings (pixel polygons: an outline, then its holes) as a bevelled extrusion `half` either side of world x"""
    from mathutils import Matrix
    cu = bpy.data.curves.new(name, 'CURVE')
    cu.dimensions = '2D'
    cu.fill_mode = 'BOTH'
    cu.extrude = max(half - bevel, .0002)
    cu.bevel_depth = bevel
    cu.bevel_resolution = res
    cu.offset = -bevel                                 # (the bevel does not grow the outline: the sheet's line stays)
    for ring in rings:
        if len(ring) < 3:
            continue
        sp = cu.splines.new('POLY')
        sp.points.add(len(ring) - 1)
        for i, (c, r) in enumerate(ring):
            sp.points[i].co = ((c - gu) * px, (gv - r) * px, 0, 1)
        sp.use_cyclic_u = True
    ob = bpy.data.objects.new(name, cu)
    bpy.context.scene.collection.objects.link(ob)
    ob.matrix_world = Matrix(((0, 0, 1, x), (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
    bpy.ops.object.select_all(action='DESELECT')
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.convert(target='MESH')
    ob = bpy.context.view_layer.objects.active
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    import bmesh as _bm
    bm = _bm.new(); bm.from_mesh(ob.data)                  # flat runs merged (a cap or a straight side is one face, not dozens)
    if half > .0015:                                       # (a light is small: merging its faces left points in a line)
        _bm.ops.dissolve_limit(bm, angle_limit=math.radians(2.0), verts=bm.verts, edges=bm.edges)
    _bm.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)  # the fill and the sides welded into one closed solid,
    _bm.ops.recalc_face_normals(bm, faces=bm.faces)       # then every face turned outward
    bm.to_mesh(ob.data); bm.free()
    ob.data.materials.clear()
    ob.data.materials.append(mat)
    K.harden(ob, 30)
    bl.uv_box(ob, .22)
    return ob


def crisp(name):
    import json
    bl.reset(); M = mats(); P = []
    S = json.load(open(os.path.join(TRACE, name + '.json')))
    spec = TRACED[name]
    W, H = S['size']
    px = S['px']
    gu, gv = spec['grip'][0] * W, spec['grip'][1] * H
    Wd = spec['width']
    half = {0: .23 * Wd, 1: .36 * Wd, 2: .50 * Wd}
    for tier, key in ((0, 'outline'), (1, 'tier1'), (2, 'tier2')):
        for i, p in enumerate(S[key]):
            P.append(_curve_solid(f'{key}{i}', [p['ext']] + p['holes'], half[tier], min(.0016, half[tier] * .25), M['shell'], 0.0, px, gu, gv))
    for i, p in enumerate(S['pale']):
        t = 2 if p['depth'] > 8.5 else (1 if p['depth'] > 3.5 else 0)
        for sd in (1, -1):
            P.append(_curve_solid(f'plate{i}{"" if sd > 0 else "_R"}', [p['ext']] + p['holes'], .0019, .0010, M['bone'],
                                  sd * (half[t] + .0013), px, gu, gv))
    for key, mat in (('amber', M['amber']), ('white', M['white'])):
        for i, p in enumerate(S[key]):
            for sd in (1, -1):
                P.append(_curve_solid(f'{key}{i}{"" if sd > 0 else "_R"}', [p['ext']], .0008, .0003, mat, sd * (half[1] + .0010), px, gu, gv))
    # within the weapon budget (asset_check: 60 000 triangles with its moving parts): every part thinned evenly if over
    tris = sum(sum(len(f.vertices) - 2 for f in o.data.polygons) for o in P)
    if tris > 54000:
        r = 54000 / tris
        for o in P:
            bpy.context.view_layer.objects.active = o
            md = o.modifiers.new('fit', 'DECIMATE'); md.ratio = r
            bpy.ops.object.modifier_apply(modifier=md.name)
            import bmesh as _bm
            bm = _bm.new(); bm.from_mesh(o.data)              # (thinning can turn a face: every face outward again)
            _bm.ops.recalc_face_normals(bm, faces=bm.faces)
            bm.to_mesh(o.data); bm.free()
    # sockets
    mask_cols = [c for p in S['outline'] for c, r in p['ext']]
    front = min(mask_cols)
    rows = [r for p in S['outline'] for c, r in p['ext'] if c < front + 4]
    mz = (gv - sum(rows) / len(rows)) * px
    muzzle = (0, (front - gu) * px, mz)
    fore = (0, (front - gu) * px * .55, mz - .03)
    sight = (0, -.05, (gv - spec['sight_z'] * H) * px)
    if name not in ('skr_blade', 'skr_grenade'):
        trigger(P, M)
    import bakekit
    bakekit.clean(P, least=2e-11)                          # last: no triangle without area reaches the gate (it allows none)
    finish('gun_' + name, P, muzzle, fore, sight, scoped=name == 'skr_sniper')


# ------------------------------------------------------------------ solid: every part with its own round volume
# (the owner, 2026-11-15, on the bevelled layers: "fill the empty areas, this is just a cut out"). At every point along the
# gun, each part the side view cuts through (a barrel, the receiver, a blade, a loop of the stock) is given a round cross
# section: an ellipse as tall as the part is there and, across, in proportion to that height (a barrel round, the
# receiver full, a blade thin), up to the gun's width. The pale plates are a shell lying ON that rounded surface, a few
# millimetres proud with a sharp edge where the sheet's plate ends; the lights are the sheet's, in their own material.
def solid(name):
    bl.reset(); M = mats(); P = []
    T = np.load(os.path.join(TRACE, name + '.npz'))
    mask, cls, px = T['mask'], T['cls'], float(T['px'])
    spec = TRACED[name]
    H, W = mask.shape
    gu, gv = spec['grip'][0] * W, spec['grip'][1] * H
    sd = np.where(mask, -T['inside'], T['outside']) * px                     # the side outline, metres
    psd = np.where(cls == 2, -T['pale_in'], T['pale_out']) * px              # the pale plates' outline, metres
    # per pixel: the vertical run of the part it lies in (its middle row, its half height)
    zc = np.zeros(mask.shape, np.float32); hh = np.zeros(mask.shape, np.float32)
    for j in range(W):
        col = mask[:, j].astype(np.int8)
        d = np.diff(np.concatenate([[0], col, [0]]))
        for a, b in zip(np.nonzero(d == 1)[0], np.nonzero(d == -1)[0]):
            zc[a:b, j] = (a + b - 1) * .5
            hh[a:b, j] = (b - a) * .5
    rows = np.arange(H, dtype=np.float32)[:, None]
    k = spec.get('round', False) and 1.0 or spec.get('k', .72)
    half_w = spec['width'] * .5
    across = np.sqrt(np.maximum(hh * hh - (rows - zc) ** 2, 0)) * px * k       # half the width at this point: an ellipse
    across = np.minimum(across, half_w)
    across = np.where(mask, np.maximum(_blur2(across, 1), .0016), 0)      # (neighbouring columns blended: no ribs)

    def at(A, u, v):
        return _bilinear(A, u, v)

    def body(Pt):
        u = gu + Pt[:, 1] / px
        v = gv - Pt[:, 2] / px
        out = (u < 0) | (u > W - 1) | (v < 0) | (v > H - 1)
        d2 = np.where(out, .02, at(sd, u, v))
        return np.maximum(d2, np.abs(Pt[:, 0]) - at(across, u, v)), u, v, out

    def field(Pt):
        Pt = np.asarray(Pt, np.float64)
        fb, u, v, out = body(Pt)
        pd = np.where(out, .02, at(psd, u, v))
        plate = np.maximum(np.abs(fb - .0018) - .0018, pd)                      # a shell 3.6 mm thick on the body, cut to the plate
        return np.minimum(fb, plate).astype(np.float32)
    lo = (-half_w - .008, -gu * px - .004, (gv - H) * px - .004)
    hi = (half_w + .008, (W - gu) * px + .004, gv * px + .004)
    h = .0009 if name != 'skr_grenade' else .0005
    V, Q = sdf.mesh(field, lo, hi, h)
    o = fk.to_object('frame', V, Q)
    print('[skr] surface nets:', len(o.data.polygons), 'quads', flush=True)
    # down to the budget in steps (in one step from millions the surface tore into shards), each step projected back onto
    # the true surface
    target = 52000 if name not in ('skr_pistol', 'skr_grenade') else 26000
    if os.environ.get('SKR_RAW'):
        target = 10 ** 9
    import bmesh as _bm
    bm = _bm.new(); bm.from_mesh(o.data)
    _bm.ops.remove_doubles(bm, verts=bm.verts, dist=h * .05)
    _bm.ops.triangulate(bm, faces=bm.faces)
    bm.to_mesh(o.data); bm.free()
    for _ in range(8):
        n = len(o.data.polygons)
        if n <= target * 1.02:
            break
        bpy.context.view_layer.objects.active = o
        md = o.modifiers.new('dec', 'DECIMATE'); md.ratio = max(target / n, .45); md.use_collapse_triangulate = True
        bpy.ops.object.modifier_apply(modifier=md.name)
    names = ['shell', 'bone', 'amber', 'white']
    for nm in names:
        o.data.materials.append(M[nm])
    me = o.data
    cen = np.array([p_.center[:] for p_ in me.polygons])
    fb, u, v, out = body(cen.astype(np.float64))
    c = cls[np.clip(np.round(v).astype(int), 0, H - 1), np.clip(np.round(u).astype(int), 0, W - 1)]
    on_plate = (fb > .0010) & (c == 2)
    idx = np.where(c == 3, 2, np.where(c == 4, 3, np.where(on_plate | (c == 2), 1, 0)))
    me.polygons.foreach_set('material_index', idx.astype(np.int32))
    bl.uv_box(o, .22)
    K.harden(o, 34)
    import bmesh as _bm
    bm = _bm.new(); bm.from_mesh(me)
    _bm.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    P.append(o)
    cols = np.nonzero(mask.any(0))[0]
    front = cols.min()
    rr = np.nonzero(mask[:, front:front + 4].any(1))[0]
    mz = (gv - rr.mean()) * px
    muzzle = (0, (front - gu) * px, mz)
    fore = (0, (front - gu) * px * .55, mz - .03)
    sight = (0, -.05, (gv - spec['sight_z'] * H) * px)
    if name not in ('skr_blade', 'skr_grenade'):
        trigger(P, M)
    import bakekit
    bakekit.clean(P, least=2e-11)
    finish('gun_' + name, P, muzzle, fore, sight, scoped=name == 'skr_sniper')


# ------------------------------------------------------------------ block: a solid block worked to the sheet's pattern
# (the owner, 2026-11-15: "use a solid block and modify it to this pattern now that we have the layout so it doesn't look
# like a smudge"). One block cut to the side outline (its windows cut through), its edges taken off in a broad rounded
# chamfer so it is a solid and not a cut-out, then narrowed where the gun is slimmer (the muzzle, the stock, the grip)
# and fullest at the receiver; each pale plate laid on its faces as a raised piece with a chamfered edge, the lights set
# in. Every edge is a modelled one: nothing is smoothed.
def _taper(spec, y, z, y_front, y_back):
    """the block's width as a share of the full width at (y, z): slimmer toward the muzzle and the stock, fullest
    over the receiver, a little slimmer down the grip"""
    t = np.clip((y - y_front) / max(y_back - y_front, 1e-6), 0, 1)               # 0 at the muzzle .. 1 at the butt
    rec = spec.get('receiver', (.45, .75))
    s = np.where(t < rec[0], .60 + .40 * (t / rec[0]) ** .8, np.where(t <= rec[1], 1.0, 1.0 - .22 * (t - rec[1]) / max(1 - rec[1], 1e-6)))
    return s * np.where(z < -.02, .85, 1.0)


def block(name):
    import json
    import bmesh as _bm
    bl.reset(); M = mats(); P = []
    S = json.load(open(os.path.join(TRACE, name + '.json')))
    spec = TRACED[name]
    W, H = S['size']
    px = S['px']
    gu, gv = spec['grip'][0] * W, spec['grip'][1] * H
    half = spec['width'] * .5
    bev = min(.0065, half * .35)
    # 1. the block: the outline (with its windows) as one solid, its edges chamfered round in four steps
    for i, p in enumerate(S['outline']):
        P.append(_curve_solid(f'block{i}', [p['ext']] + p['holes'], half, bev, M['shell'], 0.0, px, gu, gv, res=3))
    # 2. the plates on its faces, raised 2.4 mm with a chamfered edge; 3. the lights set in
    for i, p in enumerate(S['pale_face']):
        for sd in (1, -1):
            P.append(_curve_solid(f'plate{i}{"" if sd > 0 else "_R"}', [p['ext']] + p['holes'], .0016, .0009, M['bone'],
                                  sd * (half + .0008), px, gu, gv))
    for key, mat in (('amber', M['amber']), ('white', M['white'])):
        for i, p in enumerate(S[key]):
            for sd in (1, -1):
                P.append(_curve_solid(f'{key}{i}{"" if sd > 0 else "_R"}', [p['ext']], .0007, .0002, mat, sd * (half + .0006), px, gu, gv))
    # 4. the taper: every part narrowed by the same rule, so the plates stay on the faces
    y_front = (min(c for p in S['outline'] for c, r in p['ext']) - gu) * px
    y_back = (max(c for p in S['outline'] for c, r in p['ext']) - gu) * px
    for o in P:
        V = fk.verts(o)
        V[:, 0] = V[:, 0] * _taper(spec, V[:, 1], V[:, 2], y_front, y_back)
        fk.set_verts(o, V)
    # sockets
    rows = [r for p in S['outline'] for c, r in p['ext'] if c < (y_front / px + gu) + 4]
    mz = (gv - sum(rows) / len(rows)) * px
    muzzle = (0, y_front, mz)
    fore = (0, y_front * .55, mz - .03)
    sight = (0, -.05, (gv - spec['sight_z'] * H) * px)
    if name not in ('skr_blade', 'skr_grenade'):
        trigger(P, M)
    tris = sum(sum(len(f.vertices) - 2 for f in o.data.polygons) for o in P)
    print('[skr] block triangles', tris, flush=True)
    if tris > 56000:
        r = 56000 / tris
        for o in P:
            bpy.context.view_layer.objects.active = o
            md = o.modifiers.new('fit', 'DECIMATE'); md.ratio = r
            bpy.ops.object.modifier_apply(modifier=md.name)
            bm = _bm.new(); bm.from_mesh(o.data); _bm.ops.recalc_face_normals(bm, faces=bm.faces); bm.to_mesh(o.data); bm.free()
    import bakekit
    bakekit.clean(P, least=2e-11)
    finish('gun_' + name, P, muzzle, fore, sight, scoped=name == 'skr_sniper')


GUNS = {k: (lambda k=k: block(k)) for k in TRACED}


if __name__ == '__main__':
    args = [a for a in (sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []) if a]
    for k in (args or list(GUNS)):
        GUNS[k]()
