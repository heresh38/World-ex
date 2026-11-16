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
from voidkit import talon, plate, prism, lathe, lathe_x, crystal, studs  # noqa: E402
from weapons import finish, GUN_SCALE, UNWRAP_TRIES  # noqa: E402

GUN_SCALE.update({'gun_skr_rifle': 1.0, 'gun_skr_sniper': 1.0, 'gun_skr_cannon': 1.0, 'gun_skr_pistol': 1.0, 'gun_skr_blade': 1.0,
                  'gun_skr_grenade': 1.0, 'gun_skr_striker': .9})
UNWRAP_TRIES['gun_skr_striker'] = ((30.0, 'MINIMUM_STRETCH'), (30.0, 'ANGLE_BASED'), (24.0, 'ANGLE_BASED'))


def mats(under='skr_skin', shell='skr_dark', armour='skr_armour'):
    M = K.energy_mats()
    M['shell'] = fk.tmat('gun_body__skr', shell, rough=.24, nstr=.8)
    M['bone'] = fk.tmat('gun_metal__skr', armour, rough=.32, metal=.62)
    M['under'] = fk.tmat('gun_dark__skr', under, rough=.45)
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


# ------------------------------------------------------------------ parts: real geometry on the sheet's layout
# (the owner, 2026-11-15: "the layout is good but the material looks horrible ... now apply real geometry, real mesh to
# it"). The layout stays: the block cut to the outline with its windows is the receiver, the stock and the grip. On it,
# modelled parts where the sheet has them: the barrel as a real bundle (stacked slats, a core tube, amber light in the
# gaps between them) set where the sheet's barrel is and as tall; every pale region a CUT plate (its outline pulled to a
# few straight edges, chamfered, standing off the face), not a painted patch; the lights set in.
def parts(name):
    import json
    from voidkit import plate as vplate
    bl.reset(); M = mats(); P = []
    S = json.load(open(os.path.join(TRACE, name + '.json')))
    Tz = np.load(os.path.join(TRACE, name + '.npz'))
    mask = Tz['mask']
    spec = TRACED[name]
    W, H = S['size']
    px = S['px']
    gu, gv = spec['grip'][0] * W, spec['grip'][1] * H
    half = spec['width'] * .5
    yz = lambda c, r: ((c - gu) * px, (gv - r) * px)
    cols = np.nonzero(mask.any(0))[0]
    c_front, c_back = int(cols.min()), int(cols.max())
    c_split = int(c_front + (c_back - c_front) * spec.get('barrel', .42))
    y_front, y_back = yz(c_front, 0)[0], yz(c_back, 0)[0]
    y_split = yz(c_split, 0)[0]
    rule = dict(spec, receiver=(spec.get('barrel', .42) + .04, .76))

    def width_at(y, z):
        t = np.clip((y - y_front) / max(y_back - y_front, 1e-6), 0, 1)
        return np.where(t < rule['receiver'][0], .48, np.where(t <= rule['receiver'][1], 1.0, 1.0 - .22 * (t - rule['receiver'][1]) / .24)) * \
            np.where(z < -.02, .85, 1.0)
    # 1. the block in two layers (the owner, 2026-11-15, on the first textured look: "very plain and not very alive"): a
    # thinner rim all round the outline (the loops of the stock and grip are only this: blades of shell) and, inside it,
    # the full body, so every edge of the gun is a step with two highlights and not one soft roll
    RIM, CORE = .64, 1.08                                  # the rim, the body, and the core standing 3.6 mm proud of it
    inside = Tz['inside'].astype(np.float32)

    def tier_at(y, z):
        d = _bilinear(inside, gu + np.asarray(y) / px, gv - np.asarray(z) / px)
        return np.where(d > 8.5, CORE, np.where(d > 3.5, 1.0, RIM))
    body = []
    for i, p in enumerate(S['outline']):
        body.append(_curve_solid(f'rim{i}', [p['ext']] + p['holes'], half * RIM, min(.004, half * RIM * .3), M['shell'], 0.0, px, gu, gv, res=3))
    for i, p in enumerate(S['tier1']):
        if len(p['ext']) >= 3:
            body.append(_curve_solid(f'block{i}', [p['ext']] + p['holes'], half, min(.005, half * .3), M['shell'], 0.0, px, gu, gv, res=3))
    for i, p in enumerate(S['tier2']):
        if len(p['ext']) >= 3:
            body.append(_curve_solid(f'core{i}', [p['ext']] + p['holes'], half * CORE, .0016, M['shell'], 0.0, px, gu, gv, res=2))
    for o in body:
        V = fk.verts(o)
        V[:, 0] = V[:, 0] * width_at(V[:, 1], V[:, 2])
        fk.set_verts(o, V)
    P += body

    def face_at(y, z):
        return half * float(width_at(np.array(y), np.array(z))) * float(tier_at(y, z))
    cls = Tz['cls']

    def clear(pts, margin=.002):
        """the polygon pts (metres) lies on the full body and on no pale plate: tested on the trace itself, at points
        across it and round it a margin out"""
        Q = np.asarray(pts, np.float64)
        lo, hi = Q.min(0) - margin, Q.max(0) + margin
        ys, zs = np.meshgrid(np.linspace(lo[0], hi[0], 12), np.linspace(lo[1], hi[1], 7))
        u = np.clip(np.round(gu + ys / px).astype(int), 0, W - 1)
        v = np.clip(np.round(gv - zs / px).astype(int), 0, H - 1)
        d = inside[v, u]                                   # all of it on one layer: the core, or the body round it
        return bool(((d > 10.5).all() or ((d > 4.5) & (d < 7.0)).all()) and not (cls[v, u] == 2).any())

    def rect(y, z, L, h, ang):
        ca, sa = math.cos(ang), math.sin(ang)
        return [(y + ca * a - sa * b, z + sa * a + ca * b) for a, b in ((-L / 2, -h / 2), (L / 2, -h / 2), (L / 2, h / 2), (-L / 2, h / 2))]

    def slit(nm, y, z, L, ang, face, mat):
        """a light set INTO the shell: a dark recessed frame and the bar of light in it"""
        P.append(vplate(nm + '_frame', rect(y, z, L + .005, .0068, ang), M['under'], face - .002, face + .0011, .0006))
        P.append(vplate(nm, rect(y, z, L, .0026, ang), mat, face - .001, face + .0015, .0004))
    # the lights: the sheet's spots of light become slits along the gun's sweep, where the body shows (not under a plate)
    lit = 0
    for key, mat in (('white', M['white']), ('amber', M['amber'])):
        cand = []
        for p in S[key]:
            q = np.array([yz(c, r) for c, r in p['ext']])
            if len(q) < 3 or q[:, 0].mean() < y_split:
                continue                                   # (the barrel's lights are the bundle's own)
            cand.append((abs(float(np.dot(q[:, 0], np.roll(q[:, 1], 1)) - np.dot(q[:, 1], np.roll(q[:, 0], 1)))) * .5, q))
        cand.sort(key=lambda t: -t[0])
        taken = []
        for a, q in cand:
            y, z = q.mean(0)
            if any(math.hypot(y - ty, z - tz) < .018 for ty, tz in taken) or len(taken) >= 5:
                continue
            d = q - q.mean(0)
            w_, v_ = np.linalg.eigh(d.T @ d)
            ax = v_[:, 1]
            ang = float(np.clip(math.atan2(ax[1] * np.sign(ax[0] or 1), abs(ax[0])), -.6, .6))
            L = float(np.clip(np.ptp(d @ ax) * 1.6, .012, .030))
            if not clear(rect(y, z, L + .005, .0068, ang)):
                continue
            taken.append((y, z))
            slit(f'{key}slit{len(taken)}', y, z, L, ang, face_at(y, z), mat)
            lit += 1
    # a vent in the receiver's flank: slanted fins in a recessed frame, amber light behind them (the sheet's glowing slits
    # in the middle of the gun), placed where the body is clear of plates, nearest the middle of the receiver
    used = []

    def find(L, h, ang, target, ys, zs):
        """the clear place for an L x h piece at angle ang nearest target (y, z), apart from what is already placed"""
        best = None
        for yv in np.linspace(*ys, 24):
            for zv in np.linspace(*zs, 24):
                if any(abs(yv - uy) < (L + ul) / 2 + .008 and abs(zv - uz) < (h + uh) / 2 + .008 for uy, uz, ul, uh in used):
                    continue
                if clear(rect(yv, zv, L, h, ang)):
                    dd = math.hypot(yv - target[0], (zv - target[1]) * 1.5)
                    if best is None or dd < best[0]:
                        best = (dd, float(yv), float(zv))
        if best:
            used.append((best[1], best[2], L * abs(math.cos(ang)) + h, h + L * abs(math.sin(ang))))
            return best[1:]
        return None
    # a vent in the receiver's flank: slanted fins in a recessed frame, amber light behind them and between them (the
    # sheet's glowing slits in the middle of the gun)
    got = find(.054, .020, 0, (y_split + .08, .01), (y_split + .03, y_split + .20), (-.04, .06))
    if got:
        yv, zv = got
        f = face_at(yv, zv)
        P.append(vplate('vent_frame', rect(yv, zv, .054, .020, 0), M['under'], f - .003, f + .0008, .0008))
        P.append(vplate('vent_glow', rect(yv, zv, .044, .012, 0), M['amber'], f - .002, f + .0014, .0003))
        for k in range(6):
            yk = yv - .020 + k * .008
            fin = [(yk - .0018, zv - .0072), (yk + .0008, zv - .0072), (yk + .0026, zv + .0072), (yk + .0000, zv + .0072)]
            P.append(vplate(f'vent_fin{k}', fin, M['shell'], f - .002, f + .0034, .0005))
        print(f'[skr] vent at y {yv:.3f} z {zv:.3f}', flush=True)
    # rows of light along the sweep: three short slits, rising toward the back as the plates do
    for r_, (target, ys, zs) in enumerate((((y_split + .16, .045), (y_split + .06, y_back - .10), (.0, .09)),
                                          ((y_split + .02, .03), (y_split - .01, y_split + .12), (-.01, .07)),
                                          ((y_back - .14, .02), (y_split + .14, y_back - .05), (-.03, .07)))):
        ang = .24
        got = find(.040, .0075, ang, target, ys, zs)
        if not got:
            continue
        y, z = got
        for k in (-1, 0, 1):
            slit(f'row{r_}_{k}', y + k * .0135 * math.cos(ang), z + k * .0135 * math.sin(ang), .0085, ang,
                 face_at(y, z), M['white'] if r_ != 1 else M['amber'])
        lit += 3
    print(f'[skr] {lit} slits of light', flush=True)
    # 2. the barrel: a bundle as tall as the sheet's barrel, from the receiver to the muzzle
    top, bot = [], []
    for c in range(c_front, c_split):
        r = np.nonzero(mask[:, c])[0]
        if len(r):
            top.append(r.min()); bot.append(r.max())
    z_mid = (gv - (np.median(top) + np.median(bot)) * .5) * px
    h_bar = (np.median(bot) - np.median(top)) * px * .92
    bundle(P, M, y_split + .02, y_front + .01, z_mid, h_bar, spec['width'] * .62, nose=min(.09, (y_split - y_front) * .2), n_dash=6)
    # the core's end glows in the muzzle
    P.append(lathe('bore', [(y_front + .008, 0), (y_front + .008, h_bar * .11), (y_front + .0115, h_bar * .11), (y_front + .0115, 0)],
                   M['amber'], z_mid, n=12))
    # 3. the cut plates, standing off the face where they lie (over the barrel: off the bundle's flank), each in two
    # tiers: the plate, and on it a narrower plate inset from its edge (the sheet's metal is layered, never a flat sheet),
    # fastened by two studs at its ends
    for i, p in enumerate(S['plates']):
        pts = [yz(c, r) for c, r in p['ext']]
        if len(pts) < 3:
            continue
        yc = float(np.mean([q[0] for q in pts])); zc = float(np.mean([q[1] for q in pts]))
        if yc < y_split:
            face, base = spec['width'] * .31, spec['width'] * .31
        else:
            face = max(face_at(y, z) for y, z in pts + [(yc, zc)])
            base = half * RIM * min(float(width_at(np.array(y), np.array(z))) for y, z in pts)
        P.append(vplate(f'plate{i}', pts, M['bone'], base - .0015, face + .0032, .0016))
        ring = [yz(c, r) for c, r in p.get('up', [])]
        if len(ring) < 3:
            continue
        top = face + .0032
        P.append(vplate(f'plate{i}_up', ring, M['bone'], top - .001, top + .0022, .0011))
        R = np.array(ring); c0 = R.mean(0)
        D = np.linalg.norm(R[:, None] - R[None], axis=2)
        a, b = np.unravel_index(int(D.argmax()), D.shape)
        if D[a, b] > .03:
            studs(M, [tuple(R[a] + (c0 - R[a]) * .18), tuple(R[b] + (c0 - R[b]) * .18)], top + .0022, P, r=.0017)
    rows = [r for p in S['outline'] for c, r in p['ext'] if c < c_front + 4]
    mz = (gv - sum(rows) / len(rows)) * px
    muzzle = (0, y_front, mz)
    fore = (0, (y_front + y_split) * .5, z_mid - h_bar * .5)
    sight = (0, -.05, (gv - spec['sight_z'] * H) * px)
    if name not in ('skr_blade', 'skr_grenade'):
        trigger(P, M)
    import bmesh as _bm
    tris = sum(sum(len(f.vertices) - 2 for f in o.data.polygons) for o in P if o is not None and o.type == 'MESH')
    print('[skr] parts triangles', tris, flush=True)
    if tris > 56000:
        r = 56000 / tris
        for o in P:
            if o is None or o.type != 'MESH':
                continue
            bpy.context.view_layer.objects.active = o
            md = o.modifiers.new('fit', 'DECIMATE'); md.ratio = r
            bpy.ops.object.modifier_apply(modifier=md.name)
            bm = _bm.new(); bm.from_mesh(o.data); _bm.ops.recalc_face_normals(bm, faces=bm.faces); bm.to_mesh(o.data); bm.free()
    import bakekit
    bakekit.clean([o for o in P if o is not None], least=2e-11)
    finish('gun_' + name, P, muzzle, fore, sight, scoped=name == 'skr_sniper')


# ------------------------------------------------------------------ the Sarketh's own sight
# (the owner, 2026-11-15: "ensure that the scopes have a unique look and feel, not just the normal red dot, it should
# function the same but look must be blended in with the gun to ensure it belong on it"). It works as the energy line's
# reflex sight does (weapons.red_dot): the same eye line z, the dot on it just ahead of the window, a window as wide, the
# base on the mount at z - .034. Its look is theirs: the window is the LOZENGE of their emblem (a diamond, its frame in
# dark lacquer with a gold rim), the pale hood over it the emblem's brow, the reticle a small amber lozenge thrown by a
# crystal at the foot of the frame, the base forged iron held on the mount by pale claws, a steel windage screw.
def skr_sight(M, y, z):
    SH, PL, UN, TR, GL = M['shell'], M['bone'], M['under'], M['trim'], M['white']
    P = []
    yw = y - .02                                                      # the window's plane
    zr = z - .034                                                     # the mount's top
    ri = .0195                                                        # the window's half height (the crystal reaches up to it)
    P.append(prism('sk_base', [(y + .028, zr), (y + .028, zr + .0062), (y + .020, zr + .0105), (yw - .006, zr + .0105), (yw - .014, zr + .0060),
                               (yw - .014, zr)], .022, UN, .0016))
    for sg in (1, -1):                                                # the claws over the mount's sides
        P.append(plate('sk_claw', [(y + .024, zr - .0045), (y + .024, zr + .0085), (y + .008, zr + .0100), (yw - .004, zr + .0085), (yw - .012, zr - .0010),
                                   (y + .004, zr - .0070)], PL, .0108, .0136, .0008, sym=False, side=sg))
    # the frame: a lozenge (wider than tall, the emblem's) ring 12 mm deep, the gold rim at its mouth, the pale brow
    # lying on its two upper edges and swept back over it
    from voidkit import mk

    def loz(w, h):
        return [(w, 0.0), (0.0, h), (-w, 0.0), (0.0, -h)]

    def ring(nm_, outer, inner, y0, y1, m):
        n = len(outer)
        V = [(x, y0, z + q) for x, q in outer] + [(x, y1, z + q) for x, q in outer] + [(x, y1, z + q) for x, q in inner] + [(x, y0, z + q) for x, q in inner]
        F = []
        for L in range(4):
            for k in range(n):
                j = (k + 1) % n
                F.append((L * n + k, L * n + j, ((L + 1) % 4) * n + j, ((L + 1) % 4) * n + k))
        return mk(nm_, V, F, m, 30)

    def slab(nm_, poly, y0, y1, m):
        n = len(poly)
        y0 = y0 if isinstance(y0, (list, tuple)) else [y0] * n          # (a depth per point: a swept part)
        y1 = y1 if isinstance(y1, (list, tuple)) else [y1] * n
        V = [(x, y0[k], z + q) for k, (x, q) in enumerate(poly)] + [(x, y1[k], z + q) for k, (x, q) in enumerate(poly)]
        F = [(k, (k + 1) % n, n + (k + 1) % n, n + k) for k in range(n)] + [tuple(range(n))[::-1], tuple(range(n, 2 * n))]
        return mk(nm_, V, F, m, 30)
    wo, ho, wi, hi = .0340, .0250, .0285, .0195
    P.append(ring('sk_frame', loz(wo, ho), loz(wi, hi), yw + .004, yw - .008, SH))
    P.append(ring('sk_rim', loz(wo + .0012, ho + .0010), loz(wi + .0006, hi + .0005), yw - .0080, yw - .0104, TR))
    k_ = ho / wo                                                      # the brow: a V on the upper edges, thickest at the top
    for sg in (1, -1):                                                # the brow: one arm on each upper edge, swept back
        arm = [(0.0, ho + .0042), (sg * (wo + .0030), -.0006), (sg * (wo - .0004), -.0006), (0.0, ho + .0012)]
        rear = [yw + .020, yw + .003, yw + .003, yw + .020]                # deep at the peak, shallow at the sides
        front = [yw - .011, yw - .006, yw - .006, yw - .011]
        if sg < 0:
            arm, rear, front = arm[::-1], rear[::-1], front[::-1]
        P.append(slab('sk_brow', arm, rear, front, PL))
    P.append(slab('sk_brow_ridge', [(0.0, ho + .0070), (.0050, ho + .0036), (0.0, ho + .0030), (-.0050, ho + .0036)],
                  [yw + .026, yw + .010, yw + .010, yw + .010], [yw - .008, yw - .004, yw - .004, yw - .004], PL))
    P.append(slab('sk_glass', loz(wi + .0004, hi + .0004), yw - .0012, yw - .0022, M['lens']))
    P.append(slab('sk_dot', loz(.0019, .0013), y - .0296, y - .0302, M['dot']))                                               # on the eye line
    P.append(crystal('sk_emitter', (0, y + .010, zr + .0105), (0, yw + .003, z - ri + .002), .0026, GL, n=6, flat=.8))
    P.append(lathe('sk_emitter_seat', [(y + .006, 0), (y + .006, .0042), (y + .012, .0042), (y + .012, 0)], TR, zr + .0112, n=8))
    P.append(lathe_x('sk_knob', [(0, .0034), (.0026, .0034), (.0034, .0026), (.0034, 0)], (-.011, y + .014, zr + .0060), M['metal'], 6, -1))
    return P


# ------------------------------------------------------------------ assembled: the rifle as a made thing
# (the owner, 2026-11-15, on the layered cut-out: "too flat ... realistic engineering, layered mechanical components,
# ergonomic grip, trigger guard, removable power cell, cooling vents, maintenance panels, recessed muzzle, sensors,
# targeting optics, visible fasteners, overlapping armor plates, varied materials, realistic proportions ... detailed from
# every angle"; and: "a separate upper receiver, lower receiver ... every component should have a purpose"). The
# sheet is drawn 34 cm tall and 9 cm thick: the gun is built at a rifle's size instead (a receiver 11 cm deep and 6.6
# wide, a metre long) out of the energy line's hard-surface kit, keeping the sheet's language: dark lacquer under pale
# swept armour, the long barrel with amber light between its slats, a crest swept back, an open looped stock.
#   upper receiver   dark lacquer shells over the chassis, a pale cheek plate and spine, the crest's blades either
#                    side of the sight line, a maintenance hatch held by four bolts, the rail and the sight on it
#   lower receiver   the shell below the panel gap (the light in the gap is the cell's feed line), the cell well with
#                    its pale guard plate, the grip, guard and trigger, the selector, the cell catch
#   power cell       the removable cell (the part `mag`): pale casing, ribs, a floor plate, a window onto its charge
#   emitter          the coil stack in an open cage (heat goes straight out between the bars), under it the fore panel
#   shroud           the barrel's slats: dark shells above and below, amber light between them, a pale strake on top,
#                    louvres at its root; the muzzle recessed inside the shroud's mouth with prongs over and under it
#   sensors          a rangefinder pod on the left of the shroud, an illuminator on the right
#   stock            an open stock (comb, cheek rest, lower limb, butt, ribbed pad), an access panel on its flank
def skr_scope(M, y, z, L=.235):
    """The Sarketh's magnified scope (the sniper's, built in: these guns carry only their own sight): a main tube of
    lozenge section (their emblem's) in dark lacquer under a pale swept brow, titanium rings at its ends, the
    objective in a titanium bell with an amber rim, clear glass at both ends, a rubber eyecup, lozenge turrets with
    amber caps, two rings clamped on their toothed mount. The parts are the optic; `scope` names the magnified view."""
    SH, PL, UN, TR, AM = M['shell'], M['bone'], M['under'], M['trim'], M['amber']
    TI = fk.tmat('gun_metal__ti', 'skr_titanium')
    P = []
    y0, y1 = y + L * .42, y - L * .58                                   # the eyepiece's end, the objective's end
    r, ob = .0165, .0245
    P.append(lathe('scope', [(y0 - .030, r * .80), (y0 - .030, r * 1.42), (y1 + .050, r * 1.42), (y1 + .050, r * .80)], SH, z, n=4, closed=True))
    P += talon('scope_brow', [(y1 + .055, z + r * 1.30), (y + .02, z + r * 1.52), (y0 - .034, z + r * 1.36)], [.006, .012, .004], PL, x=0, t=.010,
               two=True, sym=False)
    P.append(lathe('scope_bell', [(y1 + .052, r * 1.05), (y1 + .052, r * 1.30), (y1 + .020, ob), (y1 + .002, ob), (y1, ob * .94), (y1, ob * .82),
                                  (y1 + .014, ob * .80), (y1 + .050, r * 1.05)], TI, z, n=32, closed=True))
    P.append(lathe('scope_rim', [(y1 - .0004, ob * .82), (y1 - .0004, ob * .95), (y1 - .0018, ob * .95), (y1 - .0018, ob * .82)], AM, z, n=32, closed=True))
    P.append(lathe('scope_lens_f', [(y1 + .012, 0), (y1 + .012, ob * .80), (y1 + .014, ob * .80), (y1 + .014, 0)], M['lens'], z, n=32))
    P.append(lathe('scope_eye', [(y0 - .032, r * .95), (y0 - .032, r * 1.25), (y0 - .004, r * 1.32), (y0 - .004, r * .95)], TI, z, n=32, closed=True))
    P.append(lathe('scope_cup', [(y0 - .005, r * .98), (y0 - .005, r * 1.36), (y0 + .010, r * 1.44), (y0 + .012, r * 1.36), (y0 + .012, r * 1.05)],
                   M['grip'], z, n=32, closed=True))
    P.append(lathe('scope_lens_r', [(y0 - .010, 0), (y0 - .010, r * 1.0), (y0 - .012, r * 1.0), (y0 - .012, 0)], M['lens'], z, n=24))
    ty = y - L * .06
    P.append(G_lathe_z('scope_turret', [(-.002, .0072), (.0095, .0072), (.0110, .0060), (.0110, .0001)], (0, ty, z + r * 1.30), UN, 4))
    P.append(G_lathe_z('scope_turret_cap', [(.0108, .0050), (.0128, .0042), (.0128, .0001)], (0, ty, z + r * 1.30), AM, 4))
    for sg in (1, -1):
        P.append(lathe_x('scope_knob', [(0, .0068), (.0085, .0068), (.0098, .0052), (.0098, 0)], (sg * r * 1.40, ty, z), UN, 4, sg))
        P.append(lathe_x('scope_knob_cap', [(.0096, .0040), (.0110, .0040), (.0112, .0030), (.0112, 0)], (sg * r * 1.40, ty, z), AM, 4, sg))
    zr = z - .034                                                        # the mount's top
    for yy in (y + L * .20, y - L * .30):
        P.append(lathe('scope_ring', [(yy + .007, r * 1.40), (yy + .007, r * 1.62), (yy - .007, r * 1.62), (yy - .007, r * 1.40)], SH, z, n=4, closed=True))
        P.append(prism('scope_ringbase', [(yy + .009, zr), (yy + .009, z - r * 1.5), (yy - .009, z - r * 1.5), (yy - .009, zr)], .022, UN, .0020))
        P.append(lathe_x('scope_clamp', [(0, .0034), (.0026, .0034), (.0034, .0026), (.0034, 0)], (.011, yy, zr + .006), TR, 6, 1))
    return P


def G_lathe_z(name, prof, c, m, n):
    import gunparts as G
    return G.lathe_z(name, prof, c, m, n)


# the set's long guns as Ember Oath's build with its barrel changed (the owner, 2026-11-15: "make all the other guns in
# this set too"): drawn out or cut short ahead of the receiver (`stretch`), made fatter round the bore (`radial`),
# with the magnified scope or the set's lozenge sight
VARIANTS = {'skr_sniper': dict(stretch=1.93, radial=1.0, scope=True),
            'skr_cannon': dict(stretch=.85, radial=1.6, scope=False),
            'skr_shotgun': dict(stretch=.55, radial=(1.55, 1.05), scope=False)}       # (wide and flat: a spread's mouth)


def skr_handgun(name='skr_pistol', big=False):
    """The set's handguns (the pistol and, `big`, the hand cannon: the brief's Condensed Slugs), on the light sidearm's
    proven layout so the hands fit them alike: a polymer grip with rubber panels, the guard and the trigger, a dark
    lacquer frame, an iron slide in two layers with pale strakes and their amber light in the seam, a cell in the grip
    (the part `mag`), a titanium emitter with an amber face, a crest blade swept back over the rear, a keel under the
    nose, pale blade sights with amber lozenge dots; their materials and colours."""
    import gunparts as G
    bl.reset(); M = mats(under='skr_iron', shell='skr_lacquer', armour='skr_alloy'); P = []
    ST = fk.tmat('gun_steel', 'skr_steel')
    TI = fk.tmat('gun_metal__ti', 'skr_titanium')
    PO = fk.tmat('gun_polymer', 'skr_poly')
    CELL = bl.mat('gun_glow__cell', '#ffb257', 0, .35, emit='#ffb257', strength=5)
    M.update(body=M['shell'], dark=PO, metal=ST, glow=CELL, white=CELL, dot=M['amber'],
             grip=fk.tmat('gun_grip', 'skr_rubber', metal=0, rough=.7),
             lens=bl.mat('gun_lens__skr', '#e8eef2', 0, .02, alpha=.05))
    SH, PL, UN, TR, GL, AM = M['shell'], M['bone'], M['under'], M['trim'], M['white'], M['amber']

    def AF(f):
        return math.copysign(math.asin(min(abs(f), 1.0) ** 2.5), f)
    k = 1.22 if big else 1.0                                            # the hand cannon: longer, taller, heavier
    zb = .07 * (1.06 if big else 1.0)
    g = G.hand_grip(P, PO, .3, .11, .034, z=.004)
    P.append(plate('grip_panel', [g(-.015, .032), g(.017, .028), g(.019, .06), g(.016, .096), g(-.013, .099), g(-.017, .062)], M['grip'], .011, .0179, .0012))
    P.append(G.rprism('grip_base', [g(.0282, .1085), g(-.0202, .1125), g(-.0206, .1215), g(.0288, .1175)], .034, PL, .004))
    G.guard(P, PO, [(-.076, .018), (-.078, -.008), (-.068, -.026), (-.05, -.0335), (-.026, -.0335), (-.012, -.029)], .014, .006)
    G.trigger(P, TR, -.03, .014, L=.033, w=.007)
    MAG = G.box_mag('mag', [g(-.011, .040), g(.012, .038), g(.014, .108), g(-.012, .110)], .024, PO, floor_m=PL,
                    floor=[g(-.015, .107), g(.017, .105), g(.018, .113), g(-.015, .115)], rib_m=PL)
    F = lambda y: y * k                                                 # (lengths ahead of the grip scale with the gun)
    FR = G.Body([(.057, .039, .0468, .0078, 3.0), (.046, .03, .047, .0136, 4.5), (.034, .012, .047, .0158, 5.0), (.0, .006, .047, .016, 5.0),
                 (F(-.026), .008, .047, .016, 5.0), (F(-.033), .016, .047, .016, 5.0), (F(-.098), .016, .047, .016, 5.5),
                 (F(-.107), .012, .047, .016, 5.5), (F(-.158), .012, .047, .0158, 5.5), (F(-.166), .016, .047, .015, 4.5)])
    FR.skin(P, SH, 'frame', step=.005, n=32)
    FR.shell(P, 'frame_panel', PL, .02, F(-.095), FR.af(-.3), FR.af(.6), t=.0009, ch=.001)
    top = .088 * (1.08 if big else 1.0)
    hw = .0175 * (1.12 if big else 1.0)
    SL = G.Body([(.038, .045, top, hw * .94, 5.0), (.02, .045, top, hw * .98, 5.0), (F(-.01), .045, top, hw, 5.0), (F(-.07), .045, top, hw, 5.0),
                 (F(-.13), .045, top, hw * .98, 5.0), (F(-.15), .046, top - .0005, hw * .94, 4.8), (F(-.164), .048, top - .0025, hw * .87, 4.4),
                 (F(-.172), .052, top - .0055, hw * .75, 4.0)])                 # (down onto the frame: no gap between them)
    SL.chassis(P, UN, name='slide', step=.006)
    SL.shell(P, 'slide_spine', PL, .036, F(-.168), 1.05, math.pi - 1.05, t=.0006, mirror=False)
    SL.slats(P, 'serration', SH, .035, .003, -.8, .8, 7, share=.6, t=.0022)
    SL.shell(P, 'slide_upper', SH, -.002, F(-.158), AF(.16), .82, t=.0022)
    SL.shell(P, 'slide_lower', PL, -.002, F(-.162), -.85, -AF(.12), t=.0020)
    SL.light(P, 'seam', GL, -.006, F(-.156), -AF(.03), AF(.07))
    SL.studs(P, TR, [(-.012, .5), (F(-.148), .5), (F(-.08), -.5)], r=.0016, d=.0024)
    for kk in range(3):                                                 # their three dashes on the slide
        y_ = F(-.060) - kk * .010
        xs_, _, zs_ = SL.pt(y_, AF(.62), .0030)
        P.append(plate('slide_mark', [(y_, zs_ - .0014), (y_ - .0068, zs_ - .0008), (y_ - .0068, zs_ + .0012), (y_, zs_ + .0006)], GL,
                       xs_ - .0012, xs_ + .0006, .0002))
    # the emitter: a titanium nose round an amber face, vanes in its mouth
    nose0, nose1 = F(-.166), F(-.2)
    G.muzzle(P, 'nose', nose0, nose1, zb, .0145 * (1.2 if big else 1.0), TI, .0062 * (1.25 if big else 1.0))
    P.append(G.band('nose_lip', nose1 + .0045, .003, .0152 * (1.2 if big else 1.0), TR, zb, 0, .003, 24, .0004))
    P.append(lathe('nose_glow', [(nose1 + .012, 0), (nose1 + .012, .0055 * (1.25 if big else 1.0)), (nose1 + .0128, .005), (nose1 + .0128, 0)], AM, zb, n=16))
    # the set's forms: a crest blade swept back over the rear, a keel under the nose, the blades along the slide
    crest_top = top + (.016 if big else .012)
    P += talon('crest', [(F(-.100), top - .002), (F(-.040), top + .004), (.010, crest_top + .002), (.040, crest_top + .006)], [.005, .012, .010, 0], PL,
               x=hw * .70, t=.0050)
    P += talon('keel', [(nose1 + .006, zb - .016), (F(-.150), zb - .024), (F(-.110), zb - .030)], [.004, .008, 0], PL, x=0, t=.006, two=True, sym=False)
    # the set's great pale blades swept back across the slide's flanks (as on Ember Oath), a beavertail over the hand,
    # their light seen through the rear serrations
    for nm_, spine, wid in (('sweep', [(F(-.165), top - .022), (F(-.110), top - .012), (F(-.050), top - .006), (.000, top - .004), (.030, top + .002)],
                             [.004, .012, .014, .010, 0]),
                            ('sweep_lo', [(F(-.160), .053), (F(-.100), .056), (F(-.040), .058)], [.003, .007, 0])):
        C_, u_ = G.spl(spine, 16)
        Wd = np.interp(np.linspace(0, 1, len(C_)), u_, np.asarray(wid, float))
        T_ = np.gradient(C_, axis=0); T_ /= np.linalg.norm(T_, axis=1)[:, None] + 1e-12
        Nn = np.stack([T_[:, 1], -T_[:, 0]], 1)
        poly = [tuple(q) for q in C_] + [tuple(q) for q in (C_ + Nn * Wd[:, None])[::-1][1:-1]]
        P.append(plate(nm_, poly, PL, hw - .0005, hw + .0040, .0012))
    P.append(G.rprism('beavertail', [(.030, .040), (.058, .043), (.066, .036), (.050, .030), (.032, .032)], .026, PL, .004))
    SL.light(P, 'serration_light', AM, .033, .005, -.6, .6)
    # controls
    G.selector(P, .024, .038, .016, TR, 1, ang=.25, L=.017, r=.0045)
    P.append(lathe_x('cellrelease', [(0, .0044), (.003, .0044), (.0036, .0034), (.0036, 0)], (.016, -.017, .012), PO, 14, 1))
    G.hexbolts(P, [(F(-.09), .034)], .016, ST, .0024)
    # the sights: pale blades either side of the eye line, an amber lozenge on each, a pale post with one in front
    sz = top + .012
    P.append(prism('rear_base', [(.036, top + .0005), (.036, sz - .004), (.022, sz - .004), (.018, top + .0005)], .026, UN, .001))
    for sgn in (1, -1):
        P.append(prism('rear_ear', [(.035, sz - .006), (.035, sz + .003), (.025, sz + .004), (.021, sz - .006)], .0065, PL, .001, x=sgn * .0088))
        P.append(lathe_x('rear_dot', [(0, .0016), (.0006, .0016), (.0008, 0)], (sgn * .0088, .0352, sz - .002), AM, 4, 1))
    P.append(prism('front_base', [(F(-.132), top + .0005), (F(-.138), top + .0045), (F(-.156), top + .0045), (F(-.16), top + .0005)], .011, UN, .0008))
    P.append(prism('post', [(F(-.142), top + .004), (F(-.146), sz + .003), (F(-.152), sz + .003), (F(-.154), top + .004)], .0036, PL, .0005))
    P.append(lathe('post_dot', [(F(-.1458), 0), (F(-.1458), .0014), (F(-.1462), .0014), (F(-.1462), 0)], AM, sz + .0012, 0, 4))
    finish('gun_' + name, P, (0, nose1, zb), (0, -.02, -.02), (0, .09, sz), moving=[('mag', MAG, (0, g(0, .040)[0], g(0, .040)[1]))])


def assembled_rifle(name='skr_rifle', sniper=False):
    if sniper is True:
        sniper = 'skr_sniper'
    import gunparts as G
    from weapons import e_hand, e_small
    bl.reset(); M = mats(under='skr_iron', shell='skr_lacquer', armour='skr_alloy'); P = []   # (their guns' own sets: skr/textures.py)
    # what each part is made of, every one a 4K set of its own (the owner, 2026-11-15: "apply a 4k metal/steel/iron/
    # polymer/etc textures where needed as some parts look too bland"): the dark lacquered shells (skr_dark), the pale
    # forged armour (skr_armour), the chassis, mount and emitter face in forged iron (wpn_metal), bolts, pins and the
    # muzzle's vanes in machined steel (wpn_steel), the emitter's cage, rings and the muzzle's mouth in titanium
    # (wpn_titanium), the grip, guard, cell and fore panel in polymer (wpn_poly), rubber where the hands and shoulder
    # go (wpn_knurl), their gold at fastenings (wpn_gold), glass, two lights
    ST = fk.tmat('gun_steel', 'skr_steel')
    TI = fk.tmat('gun_metal__ti', 'skr_titanium')
    PO = fk.tmat('gun_polymer', 'skr_poly')
    # the colours (the owner: "i like the orange more then this purple/blue ... the orange/gold on the scope"; their brief:
    # cells pale amber): no violet or cyan on their guns: the lacquer a warm graphite, every light pale amber or amber,
    # the glass smoked amber, gold where a band or a rim is
    CELL = bl.mat('gun_glow__cell', '#ffb257', 0, .35, emit='#ffb257', strength=5)   # (paler and brighter read as white)
    M.update(body=M['shell'], dark=PO, metal=ST, glow=CELL, white=CELL, dot=M['amber'],
             grip=fk.tmat('gun_grip', 'skr_rubber', metal=0, rough=.7),
             lens=bl.mat('gun_lens__skr', '#e8eef2', 0, .02, alpha=.05))
    SH, PL, UN, TR, GL, AM = M['shell'], M['bone'], M['under'], M['trim'], M['white'], M['amber']

    def AF(f):
        return math.copysign(math.asin(min(abs(f), 1.0) ** 2.5), f)
    zb = .058
    # ---- the receiver: one chassis, the upper and lower receivers as shells on it with a gap between them
    R = G.Body([(.150, .028, .100, .021, 4.0), (.115, .014, .106, .026, 4.6), (.070, .004, .110, .029, 5.0), (.025, .002, .108, .028, 5.0),
                (-.030, -.004, .104, .031, 5.0), (-.085, -.010, .102, .033, 5.0), (-.145, -.010, .100, .033, 5.0), (-.195, .006, .098, .030, 4.6),
                (-.232, .022, .094, .027, 4.0), (-.256, .032, .088, .024, 3.6)])
    R.chassis(P, UN)
    R.shell(P, 'upper', SH, .146, -.198, AF(.12), 1.22)
    R.shell(P, 'upper_top', PL, .146, -.248, 1.22, math.pi - 1.22, t=.0012, mirror=False)
    R.shell(P, 'lower', SH, .128, -.198, -1.25, -AF(.12))
    R.shell(P, 'lower_chin', SH, -.206, -.250, -.95, -AF(.12))
    R.light(P, 'feed_line', GL, .124, -.196, -AF(.05), AF(.05))
    R.shell(P, 'cheek_plate', PL, .118, .004, AF(.22), 1.0, d=.0026, t=.003)           # the armour over the upper receiver
    R.shell(P, 'strake', PL, -.03, -.190, AF(.30), .95, d=.0026, t=.003)
    R.shell(P, 'well_guard', PL, -.060, -.166, -1.05, -AF(.18), d=.0026, t=.0034)
    R.shell(P, 'hatch', SH, .088, .030, AF(.30), .82, d=.0056, t=.0016, ch=.001, side=1)  # the maintenance hatch (left)
    hp = [R.pt(y, a, .0074) for y, a in ((.083, AF(.36)), (.035, AF(.36)), (.083, .76), (.035, .76))]
    for q in hp:
        G.hexbolts(P, [(q[1], q[2])], q[0], ST, .0021, sym=False, side=1)
    R.slats(P, 'vent', SH, -.203, -.250, -.75, .85, 4)                                 # the receiver's nose: heat out
    R.light(P, 'vent_light', AM, -.205, -.248, -AF(.08), AF(.08))
    R.studs(P, TR, [(.132, .55), (.112, -.5), (-.004, .6), (-.184, .62), (-.03, -.72), (-.18, -.5), (.004, -.5)])
    e_small(P, M, R, sel=(.03, .034), pins=((.09, .03), (-.05, .02)), catch=(-.054, .010), charge=(.150, .1005), loops=((-.330, .021),))
    # ---- grip, guard, trigger
    e_hand(P, M)
    # ---- the crest: pale blades either side of the sight line, swept back (the sheet's), clear of the eye
    def blade(nm_, spine, wid, x, up, centre=False):
        """the sheet's swept armour as SOLID plates (6 mm, chamfered, a raised second tier along its middle): the side
        outline is the spine and the width hung off it, up or down"""
        C, u = G.spl(spine, 18)
        Wd = np.interp(np.linspace(0, 1, len(C)), u, np.asarray(wid, float))
        T = np.gradient(C, axis=0); T /= np.linalg.norm(T, axis=1)[:, None] + 1e-12
        Nn = np.stack([-T[:, 1], T[:, 0]], 1) * (1 if up else -1)
        out = C + Nn * Wd[:, None]
        poly = [tuple(q) for q in C] + [tuple(q) for q in out[::-1][1:-1]]
        x0, x1 = (-.0035, .0035) if centre else (x - .003, x + .003)
        P.append(plate(nm_, poly, PL, x0, x1, .0015, sym=not centre))
        k = int(len(C) * .8)
        lo, hi = C[1:k] + Nn[1:k] * (Wd[1:k, None] * .22), C[1:k] + Nn[1:k] * (Wd[1:k, None] * .62)
        if k > 3 and Wd[1:k].min() > .004:
            tier = [tuple(q) for q in lo] + [tuple(q) for q in hi[::-1]]
            t0, t1 = (-.0045, .0045) if centre else (x1 - .0006, x1 + .0020)
            P.append(plate(nm_ + '_tier', tier, PL, t0, t1, .0009, sym=not centre))
    # (the crest stays 2 cm under the eye line behind the sight: aimed in, blades at the eye's height either side of it
    # were two walls filling the view, the owner's "first person is broken")
    for nm_, spine, wid, x, up in (('crest', [(-.050, .098), (.010, .104), (.060, .110), (.100, .112), (.130, .108)], [.008, .014, .014, .008, 0], .026, True),
                                   ('crest_fore', [(-.250, .088), (-.17, .098), (-.075, .104)], [.004, .010, 0], .024, True),
                                   # the sheet's great pale blades, swept back across the receiver's flanks from the shroud's root
                                   ('sweep', [(-.262, .068), (-.200, .082), (-.120, .095), (-.040, .103), (.030, .110), (.078, .122)],
                                    [.004, .018, .024, .022, .014, 0], .0405, False),
                                   ('flank_blade', [(-.214, .042), (-.160, .026), (-.110, .012), (-.080, .002)], [.004, .014, .010, 0], .0392, False),
                                   ('stock_blade', [(.158, .056), (.240, .036), (.320, .010), (.362, -.016)], [.004, .010, .010, 0], .0170, False),
                                   ('comb_hook', [(.205, .102), (.280, .108), (.340, .118), (.372, .136)], [.004, .014, .014, 0], .0205, True)):
        blade(nm_, spine, wid, x, up)
    blade('keel', [(-.640, zb - .026), (-.560, zb - .034), (-.470, zb - .040), (-.430, zb - .034)], [.006, .014, .012, 0], 0, False, centre=True)
    # ---- the power cell
    MAG = G.box_mag('mag', [(-.066, .01), (-.078, -.09), (-.100, -.146), (-.160, -.140), (-.150, -.085), (-.140, .01)], .034, PO, floor_m=PL,
                    floor=[(-.096, -.142), (-.164, -.136), (-.168, -.152), (-.100, -.158)], rib_m=PL,
                    window=[(-.094, -.022), (-.12, -.022), (-.132, -.098), (-.106, -.098)], window_m=GL,
                    ribs=[[(-.077, -.004), (-.135, -.004), (-.1365, -.012), (-.0775, -.012)], [(-.094, -.110), (-.150, -.106), (-.153, -.114), (-.096, -.118)]])
    # ---- the emitter in its cage, the fore panel under it
    G.coil(P, 'emitter', -.250, -.405, zb, .0185, M, rings=6, ring_m=TI, lip_m=TR)
    G.cage(P, 'cage', -.244, -.410, zb, .0325, TI, t=.0045, bars=6, fill=.52, frames=((-.244, .014), (-.330, .007), (-.400, .012)),
           phase=math.pi / 2, frame_m=SH)
    # (the fore panel is what the support hand closes on: tall and wide enough that the fingers stop on its flanks below
    # the cage's lower bars and its front ring, full width to under the shroud; lower, narrower and tapering before the
    # ring, the index's tip curled over its edge into the cage in first person)
    P.append(G.sloft('forepanel', [(-.256, .010, .036, .024, 3.6), (-.30, .006, .041, .0305, 4.0), (-.396, .006, .041, .0305, 4.0), (-.416, .012, .037, .025, 3.6)], PO, 18, 3))
    G.slots(P, 'forecut', [(-.296 - i * .026, .0235, .021, .0045, 0) for i in range(3)], .0308, UN)
    # ---- the shroud: slats above and below, the light between them in dashes, a pale strake, the recessed muzzle
    S = G.Body([(-.398, zb - .030, zb + .034, .026, 4.4), (-.42, zb - .032, zb + .036, .028, 5.0), (-.50, zb - .030, zb + .034, .027, 5.0),
                (-.58, zb - .027, zb + .031, .025, 5.0), (-.635, zb - .024, zb + .028, .023, 4.6)])
    S.chassis(P, UN, name='shroud_core')
    S.shell(P, 'slat_up', SH, -.402, -.632, AF(.16), math.pi - AF(.16))
    S.shell(P, 'slat_lo', SH, -.402, -.628, -math.pi + AF(.16), -AF(.16))
    S.shell(P, 'shroud_strake', PL, -.420, -.600, 1.05, math.pi - 1.05, d=.0026, t=.0028, mirror=False)
    S.shell(P, 'shroud_cheek', PL, -.430, -.520, AF(.3), .9, d=.0026, t=.0028)
    for k in range(6):
        ya = -.410 - k * .036
        S.light(P, 'shroud_dash', AM, ya, ya - .024, -AF(.06), AF(.06))
    S.studs(P, TR, [(-.425, .5), (-.515, .5), (-.43, -.5), (-.60, -.5)])
    S.collar(P, 'shroud_band', SH, -.402, .010, .0025)
    P.append(lathe('muzzle_mouth', [(-.628, .0215), (-.628, .0255), (-.662, .0235), (-.664, .0215), (-.664, .0165), (-.660, .0158), (-.640, .0158),
                                    (-.640, .0215)], TI, zb, n=24, closed=True))
    P.append(lathe('emitter_face', [(-.636, 0), (-.636, .0156), (-.641, .0156), (-.641, 0)], UN, zb, n=24))
    P.append(lathe('emitter_glow', [(-.6405, 0), (-.6405, .0105), (-.6425, .0092), (-.6425, 0)], AM, zb, n=20))
    for k in range(6):                                                             # the emitter's vanes in the mouth
        a = k * math.pi / 3
        P.append(B(f'mouth_vane{k}', (.0018, .010, .004), (math.cos(a) * .0135, -.645, zb + math.sin(a) * .0135), ST, .0005))
    P += talon('prong_up', [(-.600, zb + .033), (-.650, zb + .030), (-.700, zb + .018)], [.012, .009, 0], PL, x=0, t=.008, two=True, sym=False)
    P += talon('prong_lo', [(-.600, zb - .029), (-.648, zb - .027), (-.684, zb - .019)], [.010, .007, 0], PL, x=0, t=.007, two=True, sym=False)
    # ---- sensors: a rangefinder pod on the left of the shroud, an illuminator on the right
    for sg, lit in ((1, AM), (-1, GL)):
        xs = sg * .0335
        P.append(prism('sensor_pod', [(-.520, zb - .004), (-.522, zb + .012), (-.566, zb + .013), (-.574, zb + .006), (-.570, zb - .006)], .011, SH, .0018, x=xs))
        P.append(lathe('sensor_lens', [(-.5705, 0), (-.5705, .0042), (-.5745, .0040), (-.5745, 0)], M['lens'], zb + .004, x=xs, n=16))
        P.append(lathe('sensor_ring', [(-.569, .0040), (-.569, .0055), (-.5755, .0055), (-.5755, .0040)], TI, zb + .004, x=xs, n=16, closed=True))
        P.append(B('sensor_led', (.0012, .006, .0018), (xs + sg * .0058, -.540, zb + .009), lit, .0004))
        G.hexbolts(P, [(-.530, zb - .001)], abs(xs) + .0056, ST, .0016, sym=False, side=sg)
    # ---- rail and sight, the stock with its access panel, sling points
    # ---- what makes it THEIR gun (the owner, 2026-11-15: "too simple to be an alien gun"): the Sarketh's own forms on
    # the engineering. Overlapping carapace scales down the lower receiver (grown in layers, like their armour), the
    # energy conduits from the cell to the emitter (a glowing core seen between the segments of its sheath), a
    # capacitor crystal on each flank set in a dark bed and held by pale claws, their dashes of light on the shroud
    # (the helm's three dashes), carapace bands where the receiver meets the stock and the shroud
    for i in range(4):                                                             # scales: each laps over the one behind
        ya = .118 - i * .024
        R.shell(P, 'scale', SH if i % 2 == 0 else PL, ya, ya - .030, -1.02, -AF(.22), d=.0026 + i * .0007, t=.0028)
    for y_, L_, m_ in ((.146, .010, TR), (.128, .006, PL)):
        R.collar(P, 'carapace_band', m_, y_, L_, .0034)
    S.collar(P, 'shroud_carapace', TR, -.414, .006, .0040)
    S.collar(P, 'shroud_carapace', SH, -.424, .005, .0032)
    for sg in (1, -1):                                                             # the conduits, both flanks
        path = [(sg * .0352, -.148, .006), (sg * .0372, -.186, .014), (sg * .0345, -.222, .030), (sg * .0275, -.250, .046)]
        P.append(G.cable('conduit_core', path, .0021, GL, 10, 28))
        C_, _ = G.spl(path, 9)
        for k in range(0, 8, 2):                                                   # the sheath in segments, the light between
            seg = [tuple(C_[k]), tuple((C_[k] + C_[k + 1]) / 2), tuple(C_[k + 1])]
            P.append(G.cable('conduit_sheath', seg, .0034, SH, 12, 6))
            P.append(G.cable('conduit_clamp', [tuple(C_[k]), tuple(C_[k] + (C_[k + 1] - C_[k]) * .12)], .0040, TR, 12, 3))
    for sg in (1, -1):                                                             # the capacitor crystals
        x0, y0_, z0 = R.pt(-.013, .52, .0026)
        P.append(G.rloft('crystal_bed', [(.001, z0 - .0075, z0 + .0075, .0025, 3.0, 1.0, sg * (x0 + .0008)),
                                                  (-.013, z0 - .0085, z0 + .0085, .0032, 3.0, 1.0, sg * (x0 + .0012)),
                                                  (-.029, z0 - .0070, z0 + .0070, .0025, 3.0, 1.0, sg * (x0 + .0008))], UN, 14))
        P.append(crystal('capacitor', (sg * (x0 + .0030), -.030, z0 - .0015), (sg * (x0 + .0030), .004, z0 + .0018), .0050, GL, n=6, flat=.55))
        for yc, zc, dz in ((-.024, z0 + .0085, -.006), (-.003, z0 + .0085, -.006), (-.014, z0 - .0090, .006)):
            P += talon('crystal_claw', [(yc, zc), (yc - .002, zc + dz * .5), (yc - .004, zc + dz)], [.0035, .0028, 0], PL, x=x0 + .0042,
                       t=.0016, sym=False, side=sg)
    for k in range(3):                                                             # their three dashes on the shroud
        y_ = -.452 - k * .011
        xs_, _, zs_ = S.pt(y_, AF(.62), .0030)
        P.append(plate('shroud_mark', [(y_, zs_ - .0016 + k * .0012), (y_ - .0075, zs_ - .0010 + k * .0012),
                                       (y_ - .0075, zs_ + .0012 + k * .0012), (y_, zs_ + .0006 + k * .0012)], GL, xs_ - .0012, xs_ + .0006, .0002))
    # the sight's mount is theirs: a spine of teeth swept back (a human gun's toothed rail does not belong on it)
    teeth = []
    for i in range(13):
        ya = .058 - i * .0198
        teeth += [(ya, .1075), (ya - .003, .1130), (ya - .0125, .1130), (ya - .0150, .1075)]
    P.append(prism('mount_spine', [(.062, .1020)] + [(.062, .1075)] + teeth + [(-.204, .1075), (-.204, .1020)], .022, UN, .0012))
    P.append(prism('mount_rib', [(.064, .1015), (.064, .1060), (-.206, .1060), (-.206, .1015)], .026, TR, .0010))
    sz = .147
    G.stock_soft(P, SH, PL, M['grip'], .150, .106, .232, .13, .040, .030, mode='open', cheek=True, bolt_m=ST)
    P.append(plate('stock_panel', [(.205, .085), (.262, .080), (.258, .058), (.208, .062)], PL, .0185, .0222, .0009, sym=True))
    G.hexbolts(P, [(.211, .079), (.254, .075), (.252, .063), (.213, .066)], .0222, ST, .0016)
    P += K.sling_loop(.330, .000, SH)
    if os.environ.get('SKR_TRIS'):                                      # where the triangles go, part by part
        import collections
        c = collections.Counter()
        for o in P:
            if o is not None and o.type == 'MESH':
                c[o.name.split('.')[0].rstrip('0123456789_')] += sum(len(f.vertices) - 2 for f in o.data.polygons)
        for k_, v_ in c.most_common(30):
            print('[skr] tris', k_, v_, flush=True)
    if sniper:
        # the set's other long guns (VARIANTS): everything ahead of the receiver drawn out or cut short (the shroud and
        # its dashes, the muzzle, the prongs, the keel, the sensors) and made fatter round the bore; a small part is
        # moved with it, never stretched (a stud stays round)
        v = VARIANTS[sniper]
        stretch, radial, y_at = v['stretch'], v['radial'], -.400
        rx, rz = (radial if not isinstance(radial, tuple) else radial[0]), (radial if not isinstance(radial, tuple) else radial[1])
        from mathutils import Matrix
        for o in P:                                                    # (a part placed by its object, not its points: baked in)
            if o is not None and o.type == 'MESH' and o.matrix_world != Matrix.Identity(4):
                o.data.transform(o.matrix_world)
                o.matrix_world = Matrix.Identity(4)
        for o in P:
            if o is None or o.type != 'MESH':
                continue
            V = fk.verts(o)
            if len(V) == 0 or V[:, 1].min() > y_at:
                continue
            small = np.ptp(V[:, 1]) < .02 and np.ptp(V[:, 0]) < .02 and np.ptp(V[:, 2]) < .02
            if small:
                c = V.mean(0)
                if c[1] < y_at:
                    V += np.array([c[0] * (rx - 1), (y_at + (c[1] - y_at) * stretch) - c[1], (c[2] - zb) * (rz - 1)])
            else:
                ahead = V[:, 1] < y_at
                V[:, 1] = np.where(ahead, y_at + (V[:, 1] - y_at) * stretch, V[:, 1])
                V[:, 0] = np.where(ahead, V[:, 0] * rx, V[:, 0])
                V[:, 2] = np.where(ahead, zb + (V[:, 2] - zb) * rz, V[:, 2])
            fk.set_verts(o, V)
        muzzle_y = y_at + (-.700 - y_at) * stretch
        if os.environ.get('SKR_STRAYS'):
            for o in P:
                if o is not None and o.type == 'MESH' and len(o.data.vertices):
                    V = fk.verts(o)
                    if V[:, 1].min() < muzzle_y - .015:
                        print('[skr] stray', o.name, np.round(V.min(0), 3), np.round(V.max(0), 3), flush=True)
        if v['scope']:
            finish('gun_' + name, P, (0, muzzle_y, zb), (0, -.33, .02), (0, .14, sz), optic=skr_scope(M, -.04, sz), scoped=True,
                   moving=[('mag', MAG, (0, -.103, .01))])
        else:
            finish('gun_' + name, P, (0, muzzle_y, zb), (0, -.33, .02), (0, .1, sz), optic=skr_sight(M, -.02, sz), rail=(0, -.02, .113),
                   moving=[('mag', MAG, (0, -.103, .01))])
        return
    finish('gun_' + name, P, (0, -.700, zb), (0, -.33, .02), (0, .1, sz), optic=skr_sight(M, -.02, sz), rail=(0, -.02, .113),
           moving=[('mag', MAG, (0, -.103, .01))])


# ------------------------------------------------------------------ layered: the sheet's shape, as a made gun
# (the owner, 2026-11-15, on the layered cut-out of the sheet's rifle: "this gun is great but can you make a new one with
# the old shape that functions the same as this ... just less flat and more detail"). The traced outline, built as six
# stacked layers of shell (tools/reference/trace_layers.py: the outline inset 0 .. 10.5 px), thin at the edge and full
# only in the middle, so the gun rounds like a carapace in crisp, bevelled steps (never smoothed: that was the smudge);
# the pale plates in two tiers with studs; and on it every working part the Veyr Rifle has (WEAPON_BUILD_RULES.md):
# a rubber grip, the trigger in the sheet's guard window, the removable cell, the barrel bundle with its amber light,
# a recessed emitter with vanes, sensor pods, a vent, slits of light, a maintenance hatch with steel bolts, energy
# conduits from the cell to the barrel, the selector, sling points. The sight sits on the crest's peak like a carry
# handle's (the crest is taller than any sight in front of it could look over), and the gun is built at 0.9 so the eye
# stays a rifle's height over the grip. Materials and colours: the Veyr Rifle's.
def _inpoly(poly, Q):
    """which points Q (n, 2) lie inside the polygon (ray casting)"""
    P = np.asarray(poly, float)
    x, y = Q[:, 0][:, None], Q[:, 1][:, None]
    x0, y0 = P[:, 0][None, :], P[:, 1][None, :]
    x1, y1 = np.roll(P[:, 0], -1)[None, :], np.roll(P[:, 1], -1)[None, :]
    cross = ((y0 > y) != (y1 > y)) & (x < (x1 - x0) * (y - y0) / np.where(y1 - y0 == 0, 1e-12, y1 - y0) + x0)
    return cross.sum(1) % 2 == 1


def layered(model='gun_skr_striker', trace='skr_rifle'):
    import json
    import gunparts as G
    bl.reset(); M = mats(under='skr_iron', shell='skr_lacquer', armour='skr_alloy'); P = []   # (their guns' own sets: skr/textures.py)
    ST = fk.tmat('gun_steel', 'skr_steel')
    TI = fk.tmat('gun_metal__ti', 'skr_titanium')
    PO = fk.tmat('gun_polymer', 'skr_poly')
    CELL = bl.mat('gun_glow__cell', '#ffb257', 0, .35, emit='#ffb257', strength=5)
    M.update(body=M['shell'], dark=PO, metal=ST, glow=CELL, white=CELL, dot=M['amber'],
             grip=fk.tmat('gun_grip', 'skr_rubber', metal=0, rough=.7),
             lens=bl.mat('gun_lens__skr', '#e8eef2', 0, .02, alpha=.05))
    SH, PL, UN, TR, GL, AM = M['shell'], M['bone'], M['under'], M['trim'], M['white'], M['amber']
    S = json.load(open(os.path.join(TRACE, trace + '.json')))
    Tz = np.load(os.path.join(TRACE, trace + '.npz'))
    mask, cls = Tz['mask'], Tz['cls']
    inside = Tz['inside'].astype(np.float32)
    spec = TRACED[trace]
    W, H = S['size']
    px = S['px']
    # the grip's top is the origin (weapons.py's frame): on the sheet it lies 1 cm behind and 6.6 cm under the point the
    # trace was measured from (the trigger at the top of the guard window, the hand round the column behind it)
    gu, gv = spec['grip'][0] * W + .010 / px, spec['grip'][1] * H + .066 / px
    yz = lambda c, r: ((c - gu) * px, (gv - r) * px)
    half = .030                                                        # 6 cm through the middle
    WID = [.42, .58, .71, .82, .92, 1.0]                               # each layer's share of it, edge to middle
    depths = [L['depth'] for L in S['layers']]
    cols = np.nonzero(mask.any(0))[0]
    c_front, c_back = int(cols.min()), int(cols.max())
    c_split = int(c_front + (c_back - c_front) * .42)
    y_front, y_back = yz(c_front, 0)[0], yz(c_back, 0)[0]
    y_split = yz(c_split, 0)[0]

    def width_at(y, z):
        t = np.clip((y - y_front) / max(y_back - y_front, 1e-6), 0, 1)
        return np.where(t < .46, .48, np.where(t <= .76, 1.0, 1.0 - .22 * (t - .76) / .24)) * np.where(z < .0, .85, 1.0)

    def layer_of(y, z):
        d = float(_bilinear(inside, np.array(gu + y / px), np.array(gv - z / px)))
        return int(sum(d > t for t in depths[1:]))

    def face_at(y, z):
        return half * float(width_at(np.array(y), np.array(z))) * WID[layer_of(y, z)]

    def top_at(y):
        c = int(round(gu + y / px))
        r = np.nonzero(mask[:, min(max(c, 0), W - 1)])[0]
        return (gv - r.min()) * px if len(r) else 0.0
    # 1. the shell in six layers
    body = []
    for k, (L, w) in enumerate(zip(S['layers'], WID)):
        for i, p in enumerate(L['polys']):
            if len(p['ext']) >= 3:
                body.append(_curve_solid(f'shell{k}_{i}', [p['ext']] + p['holes'], half * w, min(.0024, half * w * .3), SH, 0.0, px, gu, gv, res=2))
    for o in body:
        V = fk.verts(o)
        V[:, 0] = V[:, 0] * width_at(V[:, 1], V[:, 2])
        fk.set_verts(o, V)
    P += body
    # 2. the barrel: the bundle as tall as the sheet's barrel, its emitter recessed in the slats' mouth
    top, bot = [], []
    for c in range(c_front, c_split):
        r = np.nonzero(mask[:, c])[0]
        if len(r):
            top.append(r.min()); bot.append(r.max())
    z_mid = (gv - (np.median(top) + np.median(bot)) * .5) * px
    h_bar = (np.median(bot) - np.median(top)) * px * .92
    yb0, yb1 = y_split + .02, y_front + .01
    bundle(P, M, yb0, yb1, z_mid, h_bar, .046, nose=min(.09, (y_split - y_front) * .2), n_dash=6)
    P.append(lathe('bore', [(yb1 - .002, 0), (yb1 - .002, h_bar * .12), (yb1 + .0015, h_bar * .12), (yb1 + .0015, 0)], AM, z_mid, n=12))
    for k in range(6):
        a = k * math.pi / 3
        P.append(B(f'mouth_vane{k}', (.0016, .010, .0035), (math.cos(a) * h_bar * .15, yb1 - .004, z_mid + math.sin(a) * h_bar * .15), ST, .0004))
    for sg, lit in ((1, AM), (-1, GL)):                                # rangefinder left, illuminator right
        xs = sg * .0275
        yp = yb1 + .07
        P.append(prism('sensor_pod', [(yp + .040, z_mid - .006), (yp + .038, z_mid + .010), (yp - .004, z_mid + .011), (yp - .010, z_mid + .004),
                                      (yp - .006, z_mid - .007)], .010, SH, .0016, x=xs))
        P.append(lathe('sensor_lens', [(yp - .0095, 0), (yp - .0095, .0038), (yp - .0130, .0036), (yp - .0130, 0)], M['lens'], z_mid + .003, x=xs, n=16))
        P.append(lathe('sensor_ring', [(yp - .008, .0036), (yp - .008, .0050), (yp - .0138, .0050), (yp - .0138, .0036)], TI, z_mid + .003, x=xs, n=16,
                       closed=True))
        P.append(B('sensor_led', (.0012, .006, .0018), (xs + sg * .0053, yp + .018, z_mid + .008), lit, .0004))
    # 3. the pale plates, two tiers, studs at their ends; standing on the highest layer under them
    for i, p in enumerate(S['plates']):
        pts = [yz(c, r) for c, r in p['ext']]
        if len(pts) < 3:
            continue
        yc = float(np.mean([q[0] for q in pts])); zc = float(np.mean([q[1] for q in pts]))
        if yc < y_split:
            face, base = .046 * .5 + .0005, .046 * .5 - .002
        else:
            Q = np.array(pts)
            lo, hi = Q.min(0), Q.max(0)
            gy, gz = np.meshgrid(np.linspace(lo[0], hi[0], 9), np.linspace(lo[1], hi[1], 7))
            G2 = np.stack([gy.ravel(), gz.ravel()], 1)
            G2 = np.concatenate([G2[_inpoly(Q, G2)], Q, [[yc, zc]]])
            face = max(face_at(y, z) for y, z in G2)
            base = half * WID[0] * min(float(width_at(np.array(y), np.array(z))) for y, z in pts) - .0015
        P.append(plate(f'plate{i}', pts, PL, base, face + .0030, .0015))
        ring = [yz(c, r) for c, r in p.get('up', [])]
        if len(ring) < 3:
            continue
        tp = face + .0030
        P.append(plate(f'plate{i}_up', ring, PL, tp - .001, tp + .0020, .0010))
        R2 = np.array(ring); c0 = R2.mean(0)
        D = np.linalg.norm(R2[:, None] - R2[None], axis=2)
        a, b = np.unravel_index(int(D.argmax()), D.shape)
        if D[a, b] > .03:
            studs(M, [tuple(R2[a] + (c0 - R2[a]) * .18), tuple(R2[b] + (c0 - R2[b]) * .18)], tp + .0020, P, r=.0016)

    # 4. lights, a vent and a hatch where the shell is clear (one layer under them, no plate)
    def rect(y, z, L, h, ang):
        ca, sa = math.cos(ang), math.sin(ang)
        return [(y + ca * a_ - sa * b_, z + sa * a_ + ca * b_) for a_, b_ in ((-L / 2, -h / 2), (L / 2, -h / 2), (L / 2, h / 2), (-L / 2, h / 2))]

    def clear(pts, margin=.002, least=3):
        Q = np.asarray(pts, np.float64)
        lo, hi = Q.min(0) - margin, Q.max(0) + margin
        ys, zs = np.meshgrid(np.linspace(lo[0], hi[0], 12), np.linspace(lo[1], hi[1], 7))
        u = np.clip(np.round(gu + ys / px).astype(int), 0, W - 1)
        v = np.clip(np.round(gv - zs / px).astype(int), 0, H - 1)
        d = inside[v, u]
        k = sum((d > t).astype(int) for t in depths[1:])
        return bool((k == k.flat[0]).all() and k.flat[0] >= least and not (cls[v, u] == 2).any())
    used = []

    def find(L, h, ang, target, ys, zs, least=3):
        best = None
        for yv in np.linspace(*ys, 26):
            for zv in np.linspace(*zs, 26):
                if any(abs(yv - uy) < (L + ul) / 2 + .008 and abs(zv - uz) < (h + uh) / 2 + .008 for uy, uz, ul, uh in used):
                    continue
                if clear(rect(yv, zv, L, h, ang), least=least):
                    dd = math.hypot(yv - target[0], (zv - target[1]) * 1.5)
                    if best is None or dd < best[0]:
                        best = (dd, float(yv), float(zv))
        if best:
            used.append((best[1], best[2], L * abs(math.cos(ang)) + h, h + L * abs(math.sin(ang))))
            return best[1:]
        return None

    def slit(nm, y, z, L, ang, face, mat):
        P.append(plate(nm + '_frame', rect(y, z, L + .005, .0068, ang), UN, face - .002, face + .0011, .0006))
        P.append(plate(nm, rect(y, z, L, .0026, ang), mat, face - .001, face + .0015, .0004))
    got = find(.054, .020, 0, (y_split + .08, .06), (y_split + .03, y_split + .22), (-.02, .16))
    if got:
        yv, zv = got
        f = face_at(yv, zv)
        P.append(plate('vent_frame', rect(yv, zv, .054, .020, 0), UN, f - .003, f + .0008, .0008))
        P.append(plate('vent_glow', rect(yv, zv, .044, .012, 0), AM, f - .002, f + .0014, .0003))
        for k in range(6):
            yk = yv - .020 + k * .008
            P.append(plate(f'vent_fin{k}', [(yk - .0018, zv - .0072), (yk + .0008, zv - .0072), (yk + .0026, zv + .0072), (yk + .0000, zv + .0072)], SH,
                           f - .002, f + .0034, .0005))
    got = find(.050, .026, 0, (y_split + .26, .08), (y_split + .10, y_back - .06), (.0, .18))
    if got:                                                            # the maintenance hatch, four steel bolts
        yh, zh = got
        f = face_at(yh, zh)
        P.append(plate('hatch', rect(yh, zh, .050, .026, 0), SH, f - .002, f + .0026, .0010))
        G.hexbolts(P, [(yh + sy * .020, zh + sz_ * .009) for sy in (1, -1) for sz_ in (1, -1)], f + .0026, ST, .0018)
    for r_, target in enumerate(((y_split + .18, .14), (y_split + .05, .10), (y_back - .12, .10))):
        got = find(.040, .0075, .24, target, (y_split + .02, y_back - .04), (-.02, .2))
        if got:
            y, z = got
            for k in (-1, 0, 1):
                slit(f'row{r_}_{k}', y + k * .0135 * math.cos(.24), z + k * .0135 * math.sin(.24), .0085, .24, face_at(y, z), GL if r_ != 1 else AM)
    # 5. the hand's parts: rubber on the grip, the trigger in the guard window, the selector, the cell and its well
    for i, p in enumerate(S.get('grip_panel', [])):
        pts = [yz(c, r) for c, r in p['ext']]
        if len(pts) >= 3:
            yc = float(np.mean([q[0] for q in pts])); zc = float(np.mean([q[1] for q in pts]))
            f = max(face_at(y, z) for y, z in pts + [(yc, zc)])
            P.append(plate(f'grip_panel{i}', pts, M['grip'], f - .002, f + .0024, .0010))
    trigger(P, M, y=-.024, z=.016)
    # a real pistol grip out of the sheet's grip column (the column ends 7 cm under the receiver, where it joins the
    # guard's loop: too short for a hand, which hung in the air behind it): a polymer core with rubber panels, raked
    # as every grip the hand is fitted to
    G.grip(P, PO, M['grip'], ST, ang=.28, h=.118, w=.032, z=.004)
    G.selector(P, .010, .030, face_at(.010, .030) + .002, TR, 1, ang=.35, L=.02)
    MAG = G.box_mag('mag', [(-.120, .006), (-.126, -.060), (-.140, -.098), (-.188, -.094), (-.180, -.055), (-.172, .006)], .030, PO, floor_m=PL,
                    floor=[(-.137, -.094), (-.191, -.090), (-.193, -.104), (-.140, -.108)], rib_m=PL,
                    window=[(-.136, -.010), (-.158, -.010), (-.166, -.074), (-.144, -.074)], window_m=GL,
                    ribs=[[(-.124, -.004), (-.170, -.004), (-.171, -.011), (-.125, -.011)], [(-.135, -.082), (-.181, -.080), (-.183, -.087), (-.137, -.089)]])
    # 6. the conduits: the cell's light to the barrel, on both flanks (a glowing core between the segments of its sheath)
    for sg in (1, -1):
        path = []
        for y, z in ((-.150, .012), (-.190, .030), (y_split + .06, z_mid - .006), (y_split + .015, z_mid - .004)):
            path.append((sg * (face_at(y, z) + .0035 if y > y_split + .03 else .025), y, z))
        P.append(G.cable('conduit_core', path, .0020, GL, 10, 28))
        C_, _ = G.spl(path, 9)
        for k in range(0, 8, 2):
            seg = [tuple(C_[k]), tuple((C_[k] + C_[k + 1]) / 2), tuple(C_[k + 1])]
            P.append(G.cable('conduit_sheath', seg, .0032, SH, 12, 6))
            P.append(G.cable('conduit_clamp', [tuple(C_[k]), tuple(C_[k] + (C_[k + 1] - C_[k]) * .12)], .0038, TR, 12, 3))
    # 7. the sight IS the crest (the owner, 2026-11-15: "this whole top section, delete it and make it the golden scope
    # we have in this shape so it looks amazing, make scoping bigger than red dot by 2x in screen size it takes"): the
    # crest above its base is cut away (plates, spine and all) and in its place stands a hollow sight in the crest's own
    # side profile, hook and all: its walls polished gold, piped in gold along the outline, its roof and back clear
    # glass. The eye looks in at the back and out through the roof at the front: a window 6.6 cm wide and up to 4.8
    # tall (twice a red dot's), the reticle an amber lozenge on the eye line near the front, a line of their light along
    # the floor. Aimed it zooms as a red dot does (the data's zoom), not a scope's picture; no rail: nothing else mounts.
    from voidkit import mk
    z_base = .207                                                      # the crest's base on the receiver
    WW = .066                                                          # the window's width (a red dot's is 3 cm)
    ys = np.arange(-.15, .08, .002)
    tops = np.array([top_at(y) for y in ys])
    tops = np.convolve(np.pad(tops, 4, mode='edge'), np.ones(9) / 9, mode='valid')     # (the sheet's pixel steps smoothed out)
    up = tops > z_base + .003
    k0 = int(np.argmax(up & (ys > -.13)))
    k1 = k0
    while k1 + 1 < len(ys) and up[k1 + 1]:
        k1 += 1
    y_f0, y_b0 = float(ys[k0]), float(ys[k1])
    keep = list(range(k0, k1 + 1, 3)) + ([k1] if (k1 - k0) % 3 else [])
    outline = [(y_f0 - .002, z_base)] + [(float(ys[i]), float(tops[i])) for i in keep] + [(y_b0 + .002, z_base)]
    sz = z_base + .022                                                 # the eye line

    def carve(cutter):
        V0 = fk.verts(cutter)
        clo, chi = V0.min(0) - .001, V0.max(0) + .001
        for o in [o for o in P if o is not None and o.type == 'MESH']:
            V = fk.verts(o)
            if len(V) == 0 or (V.max(0) < clo).any() or (V.min(0) > chi).any():
                continue
            bpy.context.view_layer.objects.active = o
            md = o.modifiers.new('carve', 'BOOLEAN'); md.operation = 'DIFFERENCE'; md.object = cutter; md.solver = 'EXACT'
            bpy.ops.object.modifier_apply(modifier=md.name)
        bpy.data.objects.remove(cutter, do_unlink=True)
    # the crest goes: everything above its base between its front and its hook's back
    carve(plate('crest_cut', [(y_f0 - .004, z_base), (y_b0 + .004, z_base), (y_b0 + .004, z_base + .2), (y_f0 - .004, z_base + .2)], SH, -.1, .1, .0,
                sym=False))
    SC = []
    # (then, the owner: "it should be a scope similar to the one you made but it should be entirety out of glass but a
    # thin edge in the guns colors"): every face of it glass (gun_glass: M_SOGlass in the game, clear face on, its edges
    # catching the light), its outline and the rib over the back a thin line of their pale alloy
    GLS = bl.mat('gun_glass__skr', '#f2f5f7', 0, .03, alpha=.12)        # (clear: the owner, "see through not brown or any color")
    _b = GLS.node_tree.nodes.get('Principled BSDF')                    # (the previews draw it as glass too)
    if _b and 'Transmission Weight' in _b.inputs:
        _b.inputs['Transmission Weight'].default_value = 1.0
        _b.inputs['Roughness'].default_value = .03
    SC.append(plate('sight_wall', outline, GLS, WW / 2, WW / 2 + .0016, .0004))
    # the roof and back: clear glass round the profile from wall to wall
    n = len(outline)
    V = [(-WW / 2, y, z) for y, z in outline] + [(WW / 2, y, z) for y, z in outline]
    F = [(i, i + 1, n + i + 1, n + i) for i in range(n - 1)]
    SC.append(mk('sight_glass', V, F, M['lens'], 30))                                  # (the lens the aim is checked by)
    O2 = np.array(outline)
    Tg = np.gradient(O2, axis=0); Tg /= np.linalg.norm(Tg, axis=1)[:, None] + 1e-12
    Out = O2 + np.stack([-Tg[:, 1], Tg[:, 0]], 1) * .0006                              # (just outside it: the glass seen)
    V2 = [(-WW / 2, y, z) for y, z in Out] + [(WW / 2, y, z) for y, z in Out]
    SC.append(mk('sight_shell', V2, F, GLS, 30))
    # gold piping along the outline on both walls, and across the roof at the back and where the roof meets the eye line
    for sg in (1, -1):
        pts = [(sg * (WW / 2 + .0012), y, z) for y, z in outline]
        SC.append(G.cable('sight_piping', pts + [pts[0]], .0012, PL, 8, 140))
    for yy in (y_b0 - .003, ):
        zz = float(np.interp(yy, [q[0] for q in outline], [q[1] for q in outline]))
        SC.append(G.cable('sight_rib', [(-WW / 2, yy, zz), (0.0, yy, zz + .0015), (WW / 2, yy, zz)], .0012, PL, 8, 12))
    # the floor: their dark lacquer, a line of their light down its middle; the reticle; the crystal that throws it
    SC.append(plate('sight_floor', [(y_f0 + .004, z_base - .0015), (y_b0 - .002, z_base - .0015), (y_b0 - .002, z_base + .0012), (y_f0 + .004, z_base + .0012)],
                    SH, -WW / 2, WW / 2, .0004, sym=False))
    SC.append(B('sight_floorlight', (.0025, (y_b0 - y_f0) * .7, .0012), (0, (y_f0 + y_b0) * .5 + .01, z_base + .0016), GL, .0004))
    y_cross = float(np.interp(sz + .010, tops[k0:k0 + (k1 - k0) // 2 + 1], ys[k0:k0 + (k1 - k0) // 2 + 1]))     # the roof at the eye line
    dot = [(.0028, 0.0), (0.0, .0020), (-.0028, 0.0), (0.0, -.0020)]
    Vd = [(x, y_cross + .006, sz + q) for x, q in dot] + [(x, y_cross + .0066, sz + q) for x, q in dot]
    Fd = [(i, (i + 1) % 4, 4 + (i + 1) % 4, 4 + i) for i in range(4)] + [(3, 2, 1, 0), (4, 5, 6, 7)]
    SC.append(mk('sight_dot', Vd, Fd, M['dot'], 30))
    SC.append(crystal('sight_emitter', (0, y_b0 - .012, z_base + .0012), (0, y_b0 - .024, z_base + .008), .0026, GL, n=6, flat=.8))
    print(f'[skr] the golden crest sight: y {y_f0:.3f} .. {y_b0:.3f}, base {z_base:.3f}, eye line {sz:.3f}, roof meets it at {y_cross:.3f}', flush=True)
    # 8. sling points
    P += K.sling_loop(yb1 + .16, z_mid - h_bar * .5 - .004, SH)
    P += K.sling_loop(y_back - .05, (gv - np.nonzero(mask[:, min(int(gu + (y_back - .05) / px), W - 1)])[0].max()) * px - .004, SH)
    import bakekit
    bakekit.clean([o for o in P if o is not None], least=2e-11)
    finish(model, P, (0, yb1 - .03, z_mid), (0, (yb0 + yb1) * .5 + .06, z_mid - h_bar * .5), (0, y_b0 + .10, sz), optic=SC,
           moving=[('mag', MAG, (0, -.154, .006))])

GUNS = {k: (lambda k=k: parts(k)) for k in TRACED}
GUNS['skr_rifle'] = assembled_rifle
GUNS['skr_sniper'] = lambda: assembled_rifle('skr_sniper', sniper=True)
GUNS['skr_cannon'] = lambda: assembled_rifle('skr_cannon', sniper='skr_cannon')
GUNS['skr_shotgun'] = lambda: assembled_rifle('skr_shotgun', sniper='skr_shotgun')
GUNS['skr_pistol'] = lambda: skr_handgun('skr_pistol')
GUNS['skr_handcannon'] = lambda: skr_handgun('skr_handcannon', big=True)
GUNS['skr_striker'] = layered


if __name__ == '__main__':
    args = [a for a in (sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []) if a]
    for k in (args or list(GUNS)):
        GUNS[k]()
