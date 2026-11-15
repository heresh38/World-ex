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
def trigger(P, M, y=-.014, z=.004):
    """a thin bone blade (the hand's fit finds a trigger by how thin it is)"""
    P += talon('trigger', [(y, z), (y - .006, z - .022), (y + .002, z - .040)], [.009, .008, 0], M['trim'], x=0, t=.0032, two=True, sym=False, n=8)


def housing_cuts(F, y0, y1, z, r, n, x=None):
    """notches round the housing and recessed slots for the lights"""
    x = r if x is None else x
    for k in range(n):
        y = y0 + (y1 - y0) * (k + .5) / n
        for s in (1, -1):
            F.cut((s * x, y, z), (.0055, .0028, r * .9), k=.002)
            F.cut((s * x, y - (y1 - y0) / n * .5, z), (.0045, .0115, .0042), k=.0015)


def skr_rifle():
    bl.reset(); M = mats(); P = []
    F = Frame()
    F.shell([(0, .060, .074), (0, -.020, .085), (0, -.140, .088), (0, -.262, .082)], [.024, .031, .030, .025])
    F.ell((0, -.100, .074), (.023, .150, .040))
    F.ell((0, -.040, .108), (.016, .090, .020), 'bone', k=.010)
    F.shell([(0, -.255, .080), (0, -.420, .078), (0, -.590, .078)], [.0235, .0222, .0210], k=.010)
    housing_cuts(F, -.30, -.58, .078, .0225, 5)
    F.bone([(0, -.582, .078), (0, -.632, .078)], [.0255, .0225], k=.006)
    F.cut((0, -.640, .078), (.0085, .030, .0085), k=.002)
    gun_frame(F, .040, -.26, .078, .030)
    P.append(F.mesh('frame', M, (-.05, -.68, -.15), (.05, .34, .17)))
    trigger(P, M)
    slots(P, M, -.315, -.563, .078, .0218, 5)
    P.append(lathe('bore', [(-.618, .0080), (-.618, 0)], M['white'], .078, n=12))
    for sd in (1, -1):
        P.append(B('slit', (.003, .074, .006), (sd * .0262, -.110, .084), M['white'], .0012, rot=(.06, 0, 0)))
        P.append(B('muzzleslot', (.003, .022, .0038), (sd * .0228, -.606, .086), M['amber'], .001))
        P.append(B('muzzleslot', (.003, .022, .0038), (sd * .0228, -.606, .070), M['amber'], .001))
    blade(P, 'prong', [(-.52, .102), (-.60, .110), (-.71, .098)], [.020, .015, 0], M, t=.007)
    blade(P, 'prong_low', [(-.54, .054), (-.61, .046), (-.69, .054)], [.015, .011, 0], M, t=.006)
    crown(P, M, -.55, -.12, .094, 5, .020, .030, x=.019)
    keel(P, M, -.54, -.25, .062, 3, .017, .024, x=.018)
    blade(P, 'fin', [(-.08, .118), (.01, .158), (.10, .205)], [.042, .030, 0], M, t=.008)
    blade(P, 'fin2', [(-.18, .116), (-.11, .140), (-.04, .170)], [.030, .022, 0], M, x=.014, t=.005, lean=.3)
    blade(P, 'flankblade', [(-.22, .072), (-.12, .066), (.00, .072), (.06, .060)], [.020, .028, .022, 0], M, x=.027, t=.005, bias=.3)
    blade(P, 'chin', [(-.16, .048), (-.10, .024), (-.04, .004)], [.020, .016, 0], M, x=.016, t=.004)
    blade(P, 'gripspur', [(.030, -.030), (.064, -.080), (.104, -.124)], [.020, .016, 0], M, t=.007)
    blade(P, 'buttspur', [(.272, .010), (.310, -.020), (.360, -.040)], [.020, .014, 0], M, t=.008)
    blade(P, 'buttspur2', [(.262, .095), (.300, .125), (.340, .160)], [.018, .012, 0], M, t=.007)
    for sd in (1, -1):
        P.append(B('stocklight', (.003, .060, .004), (sd * .0118, .150, .110), M['white'], .001))
    finish('gun_skr_rifle', P, (0, -.640, .078), (0, -.38, .052), (0, -.05, .14))


def skr_sniper():
    bl.reset(); M = mats(); P = []
    F = Frame()
    F.shell([(0, .060, .074), (0, -.020, .084), (0, -.160, .086), (0, -.300, .080)], [.023, .030, .029, .024])
    F.ell((0, -.120, .074), (.022, .170, .038))
    F.ell((0, -.050, .106), (.015, .100, .018), 'bone', k=.010)
    F.shell([(0, -.295, .078), (0, -.500, .077), (0, -.700, .077)], [.0205, .0195, .0185], k=.010)
    housing_cuts(F, -.33, -.68, .077, .0195, 6)
    F.shell([(0, -.690, .077), (0, -.800, .077)], [.0105, .0100], k=.006)
    F.bone([(0, -.790, .077), (0, -.838, .077)], [.0185, .0160], k=.006)
    F.cut((0, -.845, .077), (.0065, .030, .0065), k=.002)
    F.bone([(0, -.020, .108), (0, -.020, .140)], [.0080, .0070], k=.008)
    F.bone([(0, -.130, .106), (0, -.130, .140)], [.0080, .0070], k=.008)
    F.shell([(0, .020, .150), (0, -.190, .150)], [.0150, .0165], k=.006)
    gun_frame(F, .040, -.30, .077, .029, stock_len=.25)
    P.append(F.mesh('frame', M, (-.05, -.88, -.15), (.05, .36, .19), target=34000))
    trigger(P, M)
    slots(P, M, -.355, -.66, .077, .0190, 6, L=.024, h=.0040)
    P.append(lathe('bore', [(-.822, .006), (-.822, 0)], M['white'], .077, n=12))
    P.append(lathe('scopelens', [(-.188, .0150), (-.194, .0150), (-.194, 0)], M['lens'], .150, n=16))
    P.append(lathe('scopeglow', [(-.06, .0168), (-.09, .0168), (-.09, .0150), (-.06, .0150)], M['white'], .150, n=12))
    for sd in (1, -1):
        P.append(B('slit', (.003, .084, .0055), (sd * .0255, -.130, .082), M['white'], .0012, rot=(.05, 0, 0)))
    crown(P, M, -.66, -.12, .090, 6, .019, .028, x=.018)
    keel(P, M, -.64, -.29, .062, 3, .015, .022, x=.017)
    blade(P, 'bipodblade', [(-.36, .056), (-.47, .008), (-.59, -.064)], [.026, .020, 0], M, t=.008)
    blade(P, 'fin', [(-.07, .116), (.02, .150), (.11, .195)], [.038, .028, 0], M, t=.008)
    blade(P, 'flankblade', [(-.26, .072), (-.14, .066), (.00, .072), (.06, .060)], [.020, .028, .022, 0], M, x=.026, t=.005, bias=.3)
    blade(P, 'gripspur', [(.030, -.030), (.064, -.080), (.104, -.124)], [.020, .016, 0], M, t=.007)
    blade(P, 'buttspur', [(.292, .010), (.330, -.020), (.380, -.040)], [.020, .014, 0], M, t=.008)
    finish('gun_skr_sniper', P, (0, -.845, .077), (0, -.40, .050), (0, -.08, .150), scoped=True)


def skr_cannon():
    bl.reset(); M = mats(); P = []
    F = Frame()
    F.shell([(0, .060, .078), (0, -.020, .094), (0, -.150, .100), (0, -.285, .094)], [.028, .040, .042, .036])
    F.ell((0, -.110, .074), (.030, .160, .050))
    F.ell((0, -.060, .130), (.018, .110, .020), 'bone', k=.010)
    F.shell([(0, -.280, .090), (0, -.420, .088), (0, -.550, .088)], [.0420, .0405, .0395], k=.010)
    housing_cuts(F, -.31, -.54, .088, .0410, 4)
    F.bone([(0, -.548, .088), (0, -.630, .088)], [.0500, .0480], k=.008)
    F.cut((0, -.650, .088), (.030, .050, .030), k=.003)
    F.bone([(0, -.100, .140), (0, -.240, .140)], [.008, .008], k=.010)
    F.bone([(0, -.100, .120), (0, -.100, .140)], [.008, .008], k=.008)
    F.bone([(0, -.240, .120), (0, -.240, .140)], [.008, .008], k=.008)
    gun_frame(F, .040, -.28, .088, .040, stock_len=.20, top=.11, low=.035, grip_h=.120)
    P.append(F.mesh('frame', M, (-.07, -.68, -.16), (.07, .32, .19), target=34000))
    trigger(P, M)
    slots(P, M, -.325, -.525, .088, .0398, 4, L=.028, h=.006)
    P.append(lathe('core', [(-.606, .030), (-.606, 0)], M['white'], .088, n=18))
    P.append(lathe('coreamber', [(-.612, .0300), (-.618, .0300), (-.618, .0262), (-.612, .0262)], M['amber'], .088, n=18))
    for sd in (1, -1):
        P.append(B('chevron', (.003, .046, .007), (sd * .0405, -.160, .106), M['white'], .0012, rot=(.5, 0, 0)))
        P.append(B('chevron', (.003, .046, .007), (sd * .0405, -.160, .086), M['white'], .0012, rot=(-.5, 0, 0)))
    crown(P, M, -.50, -.12, .126, 5, .026, .034, x=.026, t=.007)
    keel(P, M, -.50, -.28, .050, 3, .022, .026, x=.026, t=.006)
    blade(P, 'fin', [(-.09, .138), (.00, .178), (.09, .222)], [.046, .032, 0], M, t=.009)
    blade(P, 'fin2', [(-.23, .136), (-.16, .160), (-.08, .190)], [.034, .026, 0], M, x=.020, t=.006, lean=.3)
    blade(P, 'flankblade', [(-.27, .066), (-.14, .060), (.00, .068), (.06, .058)], [.024, .034, .026, 0], M, x=.034, t=.006, bias=.3)
    blade(P, 'gripspur', [(.030, -.030), (.064, -.080), (.104, -.124)], [.020, .016, 0], M, t=.007)
    blade(P, 'buttspur', [(.252, .010), (.290, -.020), (.340, -.040)], [.022, .016, 0], M, t=.008)
    finish('gun_skr_cannon', P, (0, -.650, .088), (0, -.40, .046), (0, -.05, .17))


def skr_pistol():
    bl.reset(); M = mats(); P = []
    F = Frame()
    F.shell([(0, .048, .070), (0, -.020, .078), (0, -.120, .078), (0, -.168, .072)], [.020, .025, .024, .020])
    F.ell((0, -.060, .066), (.019, .090, .032))
    F.ell((0, -.020, .094), (.013, .060, .015), 'bone', k=.008)
    F.bone([(0, -.160, .072), (0, -.206, .072)], [.0175, .0150], k=.006)
    F.cut((0, -.212, .072), (.0055, .022, .0055), k=.002)
    housing_cuts(F, -.08, -.15, .074, .0230, 2)
    gun_frame(F, .030, -.17, .072, .024, stock=False, grip_h=.100)
    P.append(F.mesh('frame', M, (-.04, -.24, -.14), (.04, .14, .14), h=.0009, target=20000))
    trigger(P, M)
    P.append(lathe('bore', [(-.196, .0055), (-.196, 0)], M['white'], .072, n=12))
    for sd in (1, -1):
        P.append(B('slit', (.003, .052, .005), (sd * .0212, -.060, .078), M['white'], .0012, rot=(.07, 0, 0)))
    slots(P, M, -.095, -.140, .074, .0222, 2, L=.016, h=.0036)
    crown(P, M, -.17, .02, .090, 3, .016, .022, x=.015, t=.005)
    blade(P, 'prong', [(-.15, .096), (-.20, .100), (-.25, .092)], [.014, .010, 0], M, t=.006)
    blade(P, 'fin', [(-.02, .100), (.04, .126), (.09, .158)], [.030, .022, 0], M, t=.007)
    blade(P, 'tail', [(.040, .068), (.075, .058), (.115, .040)], [.020, .014, 0], M, t=.006)
    blade(P, 'gripspur', [(.026, -.026), (.056, -.070), (.090, -.110)], [.018, .014, 0], M, t=.006)
    finish('gun_skr_pistol', P, (0, -.212, .072), (0, -.03, .00), (0, -.03, .11))


def skr_blade():
    """the energy blade: a long hooked blade, dark, a line of light along its edge, spurs along its back; held by a
    bone grip (origin at the top of the grip, the blade running forward along -Y)"""
    bl.reset(); M = mats(); P = []
    F = Frame()
    F.bone([(0, .000, .010), (0, .004, -.050), (0, .008, -.120)], [.0165, .0160, .0150], k=.010)
    F.ell((0, .006, -.128), (.018, .022, .012), 'bone', k=.008)
    F.shell([(0, .040, .022), (0, -.030, .030), (0, -.075, .036)], [.016, .022, .018], k=.012)
    F.bone([(0, .020, .030), (0, .070, .055), (0, .100, .090)], [.010, .007, .004], k=.008)
    P.append(F.mesh('frame', M, (-.04, -.12, -.16), (.04, .14, .12), h=.0009, target=12000))
    spine = [(-.05, .030), (-.24, .052), (-.46, .048), (-.66, .010), (-.80, -.050)]
    P += talon('edge', spine, [.056, .066, .058, .036, 0], M['shell'], x=0, t=.007, two=True, sym=False, glow=M['white'], g=.0022, n=24)
    P += talon('edgebone', [(-.06, .050), (-.22, .078), (-.40, .074), (-.52, .058)], [.020, .024, .018, 0], M['bone'], x=0, t=.009, two=True,
               sym=False, n=16)
    for i, y in enumerate((-.14, -.26, -.38)):
        blade(P, f'backspur{i}', [(y, .074 - i * .002), (y + .03, .098), (y + .07, .112 - i * .006)], [.016, .012, 0], M, t=.006)
    for y in (-.10, -.20, -.30):
        for sd in (1, -1):
            P.append(B('edgeamber', (.003, .016, .004), (sd * .0074, y, .040), M['amber'], .001))
    finish('gun_skr_blade', P, (0, -.80, -.05), (0, .0, -.06), (0, -.05, .08))


def skr_grenade():
    """the grenade: a dark egg held in a three-fingered claw of bone, a diamond of light on its face"""
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


GUNS = dict(skr_rifle=skr_rifle, skr_sniper=skr_sniper, skr_cannon=skr_cannon, skr_pistol=skr_pistol, skr_blade=skr_blade, skr_grenade=skr_grenade)

if __name__ == '__main__':
    args = [a for a in (sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []) if a]
    for k in (args or list(GUNS)):
        GUNS[k]()
