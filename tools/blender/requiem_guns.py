"""Void Requiem: the first operation's raid weapon set (the owner's concept sheet art/reference/operation/
void_requiem_weapons.png; our own models). Nine energy guns in one language: a black frame (the "requiem" shader),
polished silver blade plates layered along it like feathers and swept out to points, gold beads on their edges, a
gold-ringed void core on both flanks with a crystal star standing in it, a plasma chamber burning through the shroud,
crystal blades at the muzzle, light leaking under every plate.

  gun_vr_rifle       Last Rite          assault rifle: cell magazine, charging handle, plasma shroud, crystal bayonets
  gun_vr_sniper      Vigil's End        sniper: a long lit barrel ending in a trident, straight-pull bolt, long scope
  gun_vr_smg         Threnody           submachine gun: twin stacked barrels, forward cell, wire stock
  gun_vr_shotgun     Toll of Ruin       shotgun: a jawed mouth, pump forend, crystal shells
  gun_vr_lmg         Last Procession    light machine gun: belt of crystal rounds from a box, feed cover, twin barrels
  gun_vr_handcannon  Final Verse        hand cannon: a crystal cylinder on a crane, long lit shroud
  gun_vr_pistol      Ashen Psalm        pistol: lit slide, cell in the grip
  gun_vr_fusion      Eulogy             fusion rifle: twin cores, jaws that cradle the shot, a core hatch
  gun_vr_rocket      Funeral Bell       rocket launcher: a gold-lipped bell, a breech hatch, a crystal warhead

Reload parts (node names are an API, origins at their pivots): mag, charge, bolt, slide, pump, crane > cylinder >
rounds, hatch, biomass (the fusion rifle's core crystal), loose x_shell / x_speedloader. Sockets: muzzle, foregrip,
sight, rail (+ scope on the sniper). Materials: gun_body (the shader colour), gun_metal__void (silver), gun_dark,
gun_trim (gold), gun_glow / gun_glow__dim / gun_glow__crystal (the rarity colour), gun_grip, gun_lens, gun_dot.

Run: blender --background --python tools/blender/requiem_guns.py [-- vr_rifle ...]
Look: blender --background --python tools/blender/requiem_sheet.py -- out.png gun_vr_rifle:s gun_vr_rifle:q ...
"""
import math, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import bl
import gunkit as K
import voidkit as V
from gunkit import B, ext, tube, cbox, ccyl, cylx, cylz, ball, ring, rod, R90
from voidkit import feathers, talon, plate, prism, lathe, lathe_x, crystal, vein, arc, core, chamber, barrel, studs, lights, round_
from weapons import finish, e_rail, RIGHT, GUN_SCALE

GUN_SCALE.update({'gun_vr_rifle': .9, 'gun_vr_sniper': .9, 'gun_vr_handcannon': .9})


# ------------------------------------------------------------------ shared assemblies
def gp(ang, y, z):
    """Point on a raked grip: a along its front-back (+ = rear), b down it."""
    ca, sa = math.cos(ang), math.sin(ang)
    return lambda a, b: (y + a * ca + b * sa, z - b * ca + a * sa)


def grip(M, P, ang=.28, h=.12, y=0.0, z=0.0, w=.034, guard=True, L=.072, heel=True):
    """The pistol grip: knurled core, a silver backstrap blade running down to a heel spur, a gold heel cap, front
    strap plate, the trigger and its guard."""
    P.append(K.grip_profile('grip', M['grip'], ang=ang, h=h, w=w, y=y, z=z + .004))
    g = gp(ang, y, z + .004)
    P += talon('backstrap', [g(.027, .012), g(.03, h * .45), g(.027, h * .9), g(.036, h + .03)], [.012, .015, .014, 0], M['silver'],
               x=w / 2 - .001, t=.0035, n=10, bias=-.3, trim=M['trim'], g=.0012)
    if heel:
        P.append(prism('heelcap', [g(-.024, h - .004), g(.028, h - .008), g(.033, h + .008), g(.0, h + .012), g(-.022, h + .007)], w + .003, M['trim'], .002))
    P.append(plate('grip_panel', [g(-.015, .022), g(.015, .018), g(.02, h * .5), g(.013, h * .84), g(-.011, h * .88), g(-.019, h * .5)], M['metal'],
                   w / 2 - .003, w / 2 + .0016, .0014))
    P += talon('grip_slash', [g(-.012, .03), g(.004, h * .45), g(.014, h * .82)], [.004, .008, 0], M['silver'], x=w / 2 + .0012, t=.002, n=8)
    studs(M, [g(.0, h * .2)], w / 2 + .0014, P, .002)
    P += talon('frontstrap', [g(-.026, .03), g(-.03, h * .5), g(-.024, h * .92)], [.008, .01, 0], M['silver'], x=w / 2 - .0015, t=.0025, n=8, bias=.3)
    if guard:
        P += K.trigger_group(M, M['dark'], M['trim'], y=y - .012, z=z + .012, L=L, drop=.05)


def sight(M, y, z):
    """The set's built-in reflex: a lens held between two forward-swept silver horns, a gold brow, the dot on the sight
    line. Low and open: nothing of it stands in the window."""
    horn = [(y + .03, z - .0205), (y + .014, z - .004), (y - .004, z + .019), (y - .042, z + .031), (y - .022, z + .008), (y - .03, z - .0205)]
    O = [prism('rd_base', [(y + .034, z - .031), (y + .03, z - .0205), (y - .03, z - .0205), (y - .036, z - .026), (y - .03, z - .031)], .034, M['dark'], .002),
         plate('rd_horn', horn, M['silver'], .0168, .0208, .0014),
         prism('rd_brow', [(y - .002, z + .0195), (y - .034, z + .0275), (y - .036, z + .0305), (y - .004, z + .0225)], .036, M['trim'], .0008),
         B('rd_glass', (.0336, .0016, .034), (0, y - .02, z + .002), M['lens'], 0),
         ball('rd_dot', .0016, (0, y - .03, z), M['dot'], seg=10, rings=6),
         lathe_x('rd_knob', [(0, .005), (.006, .005), (.007, .004), (.007, 0)], (.0208, y + .014, z - .013), M['trim'], 12)]
    lights(M, [(y + .004, z - .012)], .0208, O, .0016)
    return O


def stock(M, P, y0, zt, L=.25, w=.036, drop=.135, spur=True):
    """Skeleton stock from the receiver's rear face y0 (top at zt): a black frame (comb bar, butt, lower strut) under
    silver blade plates (a comb plate, a butt wing running down into a spur, a brace along the strut), a gold heel."""
    y1 = y0 + L; h = w / 2
    P.append(prism('stock_bar', [(y0 - .012, zt - .034), (y0 - .012, zt), (y0 + L * .5, zt + .004), (y1 - .012, zt + .006), (y1 - .012, zt - .04),
                                 (y0 + L * .6, zt - .03), (y0 + L * .22, zt - .038)], w, M['body'], .004))
    P.append(prism('stock_butt', [(y1 - .04, zt + .004), (y1, zt + .008), (y1 + .004, zt - drop * .5), (y1 - .004, zt - drop), (y1 - .03, zt - drop - .004),
                                  (y1 - .044, zt - drop * .5)], w + .004, M['body'], .004))
    P.append(prism('stock_pad', [(y1, zt + .008), (y1 + .013, zt + .002), (y1 + .015, zt - drop * .92), (y1 - .004, zt - drop)], w + .008, M['grip'], .003))
    P.append(prism('stock_strut', [(y0 - .012, zt - .05), (y0 - .012, zt - .07), (y1 - .04, zt - drop + .0), (y1 - .03, zt - drop + .026)], w * .55, M['body'], .003))
    P.append(plate('stock_plate', [(y0 + .004, zt - .03), (y0 + .004, zt - .003), (y0 + L * .5, zt + .001), (y1 - .05, zt + .002), (y1 - .07, zt - .026),
                                   (y0 + L * .5, zt - .02), (y0 + L * .22, zt - .033)], M['metal'], h - .003, h + .002, .002))
    P += talon('stock_comb', [(y0 - .0, zt - .008), (y0 + L * .45, zt + .002), (y1 + .002, zt + .02)], [.02, .03, 0], M['silver'], x=h + .0015,
               t=.006, lean=-.2, bias=-.4, trim=M['trim'], glow=M['glow'], g=.0015)
    P += talon('stock_wing', [(y1 - .075, zt - .012), (y1 - .028, zt - drop * .4), (y1 - .012, zt - drop * .86)], [.03, .044, 0], M['silver'], x=h + .003,
               t=.006, bias=.3, trim=M['trim'])
    P += talon('stock_brace', [(y1 - .05, zt - drop + .018), (y0 + L * .45, zt - drop * .58), (y0 - .006, zt - .06)], [.022, .018, 0], M['silver'], x=w * .275 + .001,
               t=.004, n=10, bias=.3, glow=M['glow'], g=.0013)
    if spur:
        P += talon('stock_spur', [(y1 - .022, zt - drop * .7), (y1 - .012, zt - drop - .01), (y1 + .014, zt - drop - .06)], [.03, .024, 0], M['silver'],
                   x=h + .001, t=.005, bias=-.25, trim=M['trim'])
    P.append(prism('stock_heel', [(y1 - .036, zt + .0055), (y1 + .001, zt + .0095), (y1 + .014, zt + .003), (y1 + .014, zt - .016), (y1 - .002, zt - .008)],
                   w + .01, M['trim'], .002))
    studs(M, [(y0 + .03, zt - .014), (y0 + L * .5, zt - .01)], h + .002, P)
    lights(M, [(y1 - .02, zt - drop * .22)], h + .004, P)


def bayonets(M, P, y, z, r, L=.09, up=.008, n=2):
    """Crystal blades standing off the muzzle (above and below the bore), held in silver claws."""
    for i, s in enumerate((1, -1)[:n]):
        zz = z + s * (r + .004)
        P += talon('bay_claw', [(y + .06, zz - s * .003), (y + .015, zz + s * .006), (y - .04, zz + s * .004)], [.014, .016, 0], M['silver'], x=0, t=.007,
                   two=True, sym=False, n=8, bias=.3 * s)
        P += talon('bay_blade', [(y + .01, zz + s * .008), (y - L * .5, zz + s * (.011 + up * .3)), (y - L, zz + s * (.008 + up))],
                   [.011, .014, 0], M['crystal'], x=0, t=.0036, two=True, sym=False, n=10, bias=.3 * s)
        P.append(vein('bay_arc', [(0, y + .0, zz + s * .008), (0, y - L * .5, zz + s * (.011 + up * .3)), (0, y - L * .93, zz + s * (.008 + up * .94))], M['glow'],
                      .0007, 11 + i, .0012, 3))


# ------------------------------------------------------------------ the nine
def vr_rifle():
    bl.reset(); M = V.mats(); P = []
    W = .05; h = W / 2
    grip(M, P)
    stock(M, P, .15, .094)
    # frame
    P.append(ext('receiver', [(.15, .03), (.15, .09), (.12, .104), (-.2, .104), (-.24, .09), (-.24, .046), (-.135, .046), (-.135, .0),
                              (-.055, .0), (-.055, .012), (.06, .012), (.1, .03)], W, M['body'], .004, 1,
                 cuts=[cbox((.014, .06, .018), (RIGHT * h, -.125, .08))]))
    P.append(prism('shroud_top', [(-.23, .08), (-.23, .1), (-.5, .095), (-.525, .086), (-.525, .08)], .04, M['body'], .004))
    P.append(prism('shroud_low', [(-.23, .028), (-.23, .053), (-.525, .051), (-.525, .04), (-.5, .03)], .042, M['body'], .004))
    P.append(prism('shroud_nose', [(-.495, .036), (-.495, .094), (-.52, .09), (-.535, .078), (-.535, .052), (-.52, .04)], .034, M['dark'], .004))
    P.append(prism('handrest', [(-.27, .026), (-.27, .032), (-.42, .032), (-.42, .026), (-.41, .0225), (-.28, .0225)], .038, M['grip'], .002))
    chamber(M, -.238, -.497, .066, .0108, P, ribs=6, seed=3)
    # barrel, muzzle, crystal bayonets
    barrel('barrel', M, -.52, -.668, .066, .0122, P, rings=[(-.565, .0155, .014), (-.59, .0155, .008), (-.607, .0155, .008)])
    P.append(lathe('muzzle', [(-.622, .0122), (-.626, .0185), (-.66, .0185), (-.668, .0165), (-.668, .0128), (-.63, .0128)], M['silver'], .066, n=8, phase=math.pi / 8))
    P.append(lathe('muzzle_lip', [(-.662, .0188), (-.666, .0196), (-.67, .0188), (-.67, .013), (-.662, .013)], M['trim'], .066, n=8, phase=math.pi / 8))
    P.append(lathe('muzzle_glow', [(-.64, .0062), (-.64, 0)], M['dim'], .066, n=12))
    bayonets(M, P, -.64, .066, .0185)
    # silver: the crown and keel rows of the shroud, the fangs, the receiver wings and dorsal spikes
    feathers('crown', M, P, -.165, -.6, .098, 3, .044, .0245, .0075, up=1, rise=.012)
    feathers('keel', M, P, -.19, -.565, .041, 3, .034, .0235, .006, up=-1, rise=.01)
    P += talon('fang', [(-.14, .034), (-.2, .004), (-.285, -.034)], [.04, .026, 0], M['silver'], x=.0235, t=.007, bias=.3, trim=M['trim'])
    P += talon('fang_low', [(-.15, .012), (-.19, -.008), (-.235, -.02)], [.014, .012, 0], M['silver'], x=.0215, t=.004, bias=.2)
    P += talon('wing', [(-.215, .09), (-.09, .099), (.05, .099), (.15, .116)], [.016, .028, 0.022, 0], M['silver'], x=h + .002, t=.006, lean=-.3, bias=-.4,
               trim=M['trim'], glow=M['glow'])
    P += talon('dorsal', [(-.2, .1), (-.15, .11), (-.085, .12)], [.026, .017, 0], M['silver'], x=h - .001, t=.0045, lean=-.2, bias=-.2)
    P += talon('dorsal2', [(-.275, .106), (-.225, .114), (-.165, .121)], [.022, .014, 0], M['silver'], x=.021, t=.004, bias=-.2)
    P += talon('dorsal3', [(-.35, .108), (-.31, .116), (-.26, .122)], [.018, .011, 0], M['silver'], x=.019, t=.0035, bias=-.2)
    # receiver armour round the core (the right flank leaves the bolt's port open)
    rear = [(.135, .04), (.14, .084), (.105, .0975), (.006, .0975), (.008, .086), (.014, .072), (.008, .058), (.003, .046), (.06, .026)]
    P.append(plate('armour_rear', rear, M['metal'], h - .003, h + .003, .0018))
    P += talon('ray_rear', [(.0, .074), (.07, .07), (.146, .058)], [.018, .03, 0], M['silver'], x=h + .003, t=.0055, bias=.3, trim=M['trim'])
    P += talon('ray_rear_low', [(.004, .052), (.045, .036), (.1, .027)], [.014, .017, 0], M['silver'], x=h + .0025, t=.004, bias=-.2)
    P += talon('ray_front', [(-.058, .058), (-.14, .057), (-.236, .062)], [.016, .022, 0], M['silver'], x=h + .003, t=.005, bias=-.3, trim=M['trim'])
    P += talon('ray_front_up', [(-.058, .088), (-.13, .091), (-.2, .089)], [.01, .014, 0], M['silver'], x=h + .003, t=.0035, bias=.3, sym=False)
    front = [(-.066, .0975), (-.19, .0975), (-.228, .088), (-.228, .05), (-.145, .05), (-.07, .05), (-.066, .06), (-.074, .072), (-.066, .086)]
    P.append(plate('armour_front', front, M['metal'], h - .003, h + .003, .0018, sym=False))
    P.append(plate('armour_front', [(-.066, .0975), (-.19, .0975), (-.228, .091), (-.16, .091), (-.09, .091), (-.066, .089)], M['metal'], h - .003, h + .003,
                   .0015, sym=False, side=-1))
    P.append(plate('armour_front', [(-.228, .069), (-.228, .05), (-.07, .05), (-.066, .06), (-.07, .069)], M['metal'], h - .003, h + .003, .0015, sym=False, side=-1))
    P.append(plate('magwell', [(-.052, .044), (-.138, .044), (-.141, -.004), (-.05, -.004)], M['metal'], h - .003, h + .0025, .002))
    core(M, -.03, .072, .0235, W + .004, P)
    P += arc('crack', [(-.068, .06), (-.1, .058), (-.135, .066), (-.16, .06)], h + .0032, M['glow'], .0007, 5, .003, sym=False)
    P += arc('crack', [(.03, .06), (.06, .05), (.1, .058)], h + .0032, M['glow'], .0006, 9, .003)
    studs(M, [(.12, .05), (.12, .086), (-.2, .058), (-.2, .09), (-.125, .01), (-.065, .01)], h + .003, P)
    lights(M, [(.085, .076), (-.11, .09)], h + .003, P)
    # reload parts
    MAG = [prism('magbody', [(-.062, .03), (-.066, -.05), (-.084, -.118), (-.136, -.108), (-.127, -.05), (-.123, .03)], .03, M['dark'], .003)]
    MAG += talon('magblade', [(-.094, -.0), (-.1, -.06), (-.124, -.142)], [.03, .03, 0], M['silver'], x=.0145, t=.0045, bias=-.3, trim=M['trim'], g=.0013)
    MAG += [prism('magfloor', [(-.08, -.114), (-.14, -.102), (-.146, -.112), (-.086, -.126)], .034, M['trim'], .002),
            B('magwindow', (.0312, .008, .05), (0, -.071, -.04), M['dim'], 0, rot=(-.12, 0, 0)),
            B('magrib', (.032, .012, .004), (0, -.07, -.022), M['dark'], .001), B('magrib', (.032, .012, .004), (0, -.073, -.058), M['dark'], .001)]
    CHARGE = [B('ch_body', (.028, .024, .008), (0, .128, .1075), M['dark'], .002),
              prism('ch_wings', [(.118, .104), (.118, .112), (.142, .115), (.15, .11), (.142, .104)], .044, M['silver'], .0015),
              B('ch_latch', (.01, .01, .006), (.017, .123, .1135), M['trim'], .0015)]
    BOLT = [B('boltbody', (.02, .056, .014), (RIGHT * .014, -.125, .08), M['silver'], .002),
            B('boltslit', (.004, .03, .0035), (RIGHT * .0242, -.125, .08), M['glow'], 0),
            lathe_x('bolthandle', [(0, .0045), (.012, .0045), (.014, .0065), (.02, .0065), (.022, .004), (.022, 0)], (RIGHT * .024, -.146, .08), M['trim'], 10, -1)]
    P += e_rail(M, .1, -.16, .104)
    sz = .14
    finish('gun_vr_rifle', P, (0, -.675, .066), (0, -.345, .02), (0, .1, sz), optic=sight(M, -.02, sz), rail=(0, -.02, .1135),
           moving=[('mag', MAG, (0, -.09, .02)), ('charge', CHARGE, (0, .128, .1075)), ('bolt', BOLT, (RIGHT * .014, -.125, .08))])
    stats('gun_vr_rifle')


def rays(M, P, y, z, r, h, back=.14, fwd=.2, left_only=()):
    """Blades sweeping away from the core along the receiver's flanks (fore and aft, high and low). left_only names
    the ones the right flank leaves out (where a port sits)."""
    def sym(n):
        return n not in left_only
    if back:
        P += talon('ray_rear', [(y + r * 1.25, z + .002), (y + back * .55, z - .002), (y + back, z - .014)], [r * .75, r * 1.25, 0], M['silver'], x=h + .003,
                   t=.0055, bias=.3, trim=M['trim'], sym=sym('rear'))
        P += talon('ray_rear_low', [(y + r * 1.3, z - r * .85), (y + back * .45, z - r * 1.5), (y + back * .75, z - r * 1.9)], [r * .6, r * .7, 0], M['silver'],
                   x=h + .0025, t=.004, bias=-.2, sym=sym('rear_low'))
    if fwd:
        P += talon('ray_front', [(y - r * 1.25, z - r * .6), (y - fwd * .55, z - r * .62), (y - fwd, z - r * .4)], [r * .7, r * .95, 0], M['silver'], x=h + .003,
                   t=.005, bias=-.3, trim=M['trim'], sym=sym('front'))
        P += talon('ray_front_up', [(y - r * 1.25, z + r * .7), (y - fwd * .5, z + r * .82), (y - fwd * .85, z + r * .74)], [r * .42, r * .6, 0], M['silver'],
                   x=h + .003, t=.0035, bias=.3, sym=sym('front_up'))


def shroud(M, P, y0, y1, z, r, w=.04, top=.1, low=.03, ribs=6, seed=3):
    """The barrel shroud from y0 (the receiver's face) to its nose y1: a top and a bottom rail in the frame colour, a dark
    nose block, and between the rails the plasma chamber burning round the bore axis (z, radius r)."""
    P.append(prism('shroud_top', [(y0, z + r + .004), (y0, top), (y1 + .03, top - .005), (y1, top - .014), (y1, z + r + .004)], w, M['body'], .004))
    P.append(prism('shroud_low', [(y0, low), (y0, z - r - .004), (y1, z - r - .006), (y1, low + .012), (y1 + .025, low + .002)], w + .002, M['body'], .004))
    P.append(prism('shroud_nose', [(y1 + .03, low + .006), (y1 + .03, top - .006), (y1 + .005, top - .011), (y1 - .01, z + r + .006), (y1 - .01, z - r - .006),
                                   (y1 + .005, low + .012)], w - .006, M['dark'], .004))
    chamber(M, y0 - .008, y1 + .028, z, r, P, ribs=ribs, seed=seed)


def muzzle_dev(M, P, y, z, r, L=.046, rb=None):
    """A faceted silver muzzle device ending at y (front face), a gold lip, light inside the bore."""
    rb = rb or r * .7
    f = math.pi / 8
    P.append(lathe('muzzle', [(y + L, rb), (y + L - .004, r), (y + .008, r), (y, r - .002), (y, rb + .0006), (y + L * .8, rb + .0006)], M['silver'], z, n=8, phase=f))
    P.append(lathe('muzzle_lip', [(y + .006, r + .0003), (y + .002, r + .0011), (y - .002, r + .0003), (y - .002, rb + .0008), (y + .006, rb + .0008)], M['trim'], z, n=8,
                   phase=f, closed=True))
    P.append(lathe('muzzle_glow', [(y + L * .6, rb * .5), (y + L * .6, 0)], M['dim'], z, n=12))


def gold_ring(name, M, y, z, r, P, L=.008, t=.002, x=0.0, n=24, m=None):
    P.append(lathe(name, [(y + L / 2, r - .0005), (y + L / 2, r + t * .6), (y + L / 4, r + t), (y - L / 4, r + t), (y - L / 2, r + t * .6), (y - L / 2, r - .0005)],
                   m or M['trim'], z, x, n, closed=True))


def cell_mag(M, front, rear, top, bottom, w=.03, rake=.004, fang=.03):
    """A void cell magazine between y = front and rear, from z = top down to bottom: dark body, a silver blade on each
    flank running out past the floor, a gold floor plate, a lit window up its back."""
    mid = (top + bottom) / 2
    Q = [prism('magbody', [(rear, top), (rear - rake, mid), (rear - rake * 3, bottom + .006), (front - rake * 2.2, bottom), (front - rake, mid), (front, top)],
               w, M['dark'], .003)]
    cy = (front + rear) / 2
    Q += talon('magblade', [(cy, top - .03), (cy - rake * 1.2, mid), (front - rake * 2 + .004, bottom - fang)], [(rear - front) * .5, (rear - front) * .52, 0],
               M['silver'], x=w / 2 - .0005, t=.0045, bias=-.3, trim=M['trim'], g=.0013)
    Q += [prism('magfloor', [(rear - rake * 3 + .004, bottom + .004), (front - rake * 2.2 - .006, bottom - .004), (front - rake * 2.2 - .01, bottom - .014),
                             (rear - rake * 3, bottom - .008)], w + .004, M['trim'], .002),
          B('magwindow', (w + .0012, .007, (top - bottom) * .36), (0, rear - rake - .008, mid + .004), M['dim'], 0),
          B('magrib', (w + .002, .011, .004), (0, rear - rake - .008, mid + (top - bottom) * .14), M['dark'], .001),
          B('magrib', (w + .002, .011, .004), (0, rear - rake - .008, mid - (top - bottom) * .12), M['dark'], .001)]
    return Q


def bolt_parts(M, y, z, h, L=.056, handle='knob'):
    """The bolt seen in the right flank's port, with its handle standing out of the gun."""
    Q = [B('boltbody', (.02, L, .014), (RIGHT * (h - .011), y, z), M['silver'], .002),
         B('boltslit', (.004, L * .55, .0035), (RIGHT * (h - .0008), y, z), M['glow'], 0)]
    if handle == 'knob':
        Q.append(lathe_x('bolthandle', [(0, .0045), (.012, .0045), (.014, .0065), (.02, .0065), (.022, .004), (.022, 0)], (RIGHT * (h - .001), y - L * .38, z),
                         M['trim'], 10, -1))
    elif handle == 'pull':                          # a long straight-pull handle, swept back, with a faceted knob
        a = (RIGHT * (h - .002), y - L * .3, z); b = (RIGHT * (h + .028), y - L * .18, z - .01)
        Q += [rod('bolthandle', a, b, .0042, M['trim'], 10), crystal('boltknob', b, (b[0] + RIGHT * .02, b[1] + .004, b[2] - .006), .0085, M['dark'], 6, .3, .7)]
    return Q


# ------------------------------------------------------------------ sniper
def scope(M, y, z, rail_z):
    """Vigil's End's long glass: a turned body, gold rings, a silver blade down each flank, turrets, two mounts."""
    r = .0165
    O = [lathe('scope_tube', [(y + .105, .019), (y + .105, .0215), (y + .07, .0215), (y + .06, r), (y - .02, r), (y - .028, .021), (y - .05, .021), (y - .058, r),
                              (y - .13, r), (y - .17, .027), (y - .225, .027), (y - .23, .0255), (y - .23, .023), (y - .17, .023), (y - .13, r - .003),
                              (y + .06, r - .003), (y + .07, .019)], M['dark'], z, n=32, closed=True),
         lathe('lens_r', [(y + .098, .0192), (y + .097, 0)], M['lens'], z, n=24), lathe('lens_f', [(y - .212, .0232), (y - .21, 0)], M['lens'], z, n=24),
         lathe('scope_iris', [(y - .2, .0232), (y - .2, .017), (y - .202, .017), (y - .202, .0232)], M['dim'], z, n=24, closed=True),
         K.cylz('turret_top', .0085, .013, (0, y - .039, z + .0265), M['trim'], 12), K.cylz('turret_cap', .0095, .004, (0, y - .039, z + .034), M['dark'], 12),
         lathe_x('turret_side', [(0, .0085), (.011, .0085), (.013, .007), (.013, 0)], (.02, y - .039, z), M['trim'], 12),
         lathe_x('turret_eye', [(.0132, .004), (.0138, 0)], (.02, y - .039, z), M['glow'], 10)]
    gold_ring('scope_ring', M, y + .072, z, .0215, O, .006, .0016)
    gold_ring('scope_ring', M, y - .132, z, r, O, .006, .0016)
    gold_ring('scope_ring', M, y - .226, z, .027, O, .005, .0014)
    O += talon('scope_blade', [(y + .05, z + .002), (y - .07, z + .006), (y - .215, z + .002)], [.012, .02, 0], M['silver'], x=.0215, t=.004, bias=.3,
               trim=M['trim'], glow=M['glow'], g=.0012)
    for yy in (y + .03, y - .095):
        O.append(prism('scope_mount', [(yy + .013, rail_z - .002), (yy + .009, z - r + .003), (yy - .009, z - r + .003), (yy - .013, rail_z - .002)], .024, M['dark'], .0015))
        gold_ring('scope_clamp', M, yy, z, r, O, .012, .0024, m=M['dark'])
    return O


def vr_sniper():
    bl.reset(); M = V.mats(); P = []
    W = .05; h = W / 2; zb = .062
    grip(M, P)
    stock(M, P, .15, .088, L=.29, drop=.15)
    P.append(ext('receiver', [(.15, .02), (.15, .084), (.12, .096), (-.3, .096), (-.34, .084), (-.34, .03), (-.135, .03), (-.135, .0), (-.055, .0), (-.055, .012),
                              (.06, .012), (.1, .02)], W, M['body'], .004, 1, cuts=[cbox((.014, .078, .018), (RIGHT * h, .04, .074))]))
    shroud(M, P, -.33, -.53, zb, .0095, .038, top=.094, low=.03, ribs=5)
    P.append(prism('handrest', [(-.36, .026), (-.36, .032), (-.5, .032), (-.5, .026), (-.49, .0225), (-.37, .0225)], .036, M['grip'], .002))
    # the long lit barrel and its trident
    barrel('barrel', M, -.53, -.93, zb, .0105, P, rings=[(-.6, .0128, .014), (-.7, .0128, .014), (-.8, .0128, .014)])
    for y in (-.575, -.675, -.775, -.875):
        gold_ring('band', M, y, zb, .0105, P, .006, .0016)
    for s in (1, -1):
        P.append(B('barrel_light', (.0014, .3, .0032), (s * .0106, -.74, zb), M['glow'], 0))
    muzzle_dev(M, P, -.936, zb, .016, .04, .0075)
    bayonets(M, P, -.915, zb, .016, L=.1, up=.004)
    P += talon('trident', [(-.865, zb), (-.94, zb + .003), (-1.0, zb)], [.014, .013, 0], M['silver'], x=.0125, t=.004, n=10, trim=M['trim'])
    # silver
    feathers('crown', M, P, -.2, -.67, .091, 3, .04, .0245, .007, up=1, rise=.008)
    feathers('keel', M, P, -.25, -.61, .038, 3, .032, .0225, .0055, up=-1, rise=.008)
    P += talon('fang', [(-.15, .03), (-.24, .0), (-.345, -.03)], [.04, .026, 0], M['silver'], x=.0235, t=.007, bias=.3, trim=M['trim'])
    P += talon('fang_strut', [(-.19, .0), (-.27, -.03), (-.33, -.032)], [.006, .007, 0], M['trim'], x=.0215, t=.003, n=10)
    P += talon('wing', [(-.3, .084), (-.1, .091), (.05, .091), (.15, .108)], [.014, .026, .02, 0], M['silver'], x=h + .002, t=.006, lean=-.3, bias=-.4,
               trim=M['trim'], glow=M['glow'])
    P += talon('dorsal', [(-.31, .094), (-.26, .104), (-.2, .117)], [.022, .014, 0], M['silver'], x=.021, t=.004, bias=-.2)
    P += talon('dorsal2', [(-.4, .098), (-.36, .108), (-.31, .118)], [.018, .011, 0], M['silver'], x=.0195, t=.0035, bias=-.2)
    P.append(plate('armour', [(.135, .03), (.14, .078), (.11, .0895), (-.29, .0895), (-.33, .08), (-.33, .036), (-.14, .036), (-.05, .02), (.06, .018)], M['metal'],
                   h - .003, h + .0025, .0018, sym=False))
    P.append(plate('armour', [(-.01, .03), (-.01, .0895), (-.29, .0895), (-.33, .08), (-.33, .036), (-.14, .036), (-.05, .02)], M['metal'],
                   h - .003, h + .0025, .0018, sym=False, side=-1))
    P.append(plate('magwell', [(-.052, .03), (-.138, .03), (-.141, -.004), (-.05, -.004)], M['metal'], h - .003, h + .003, .002))
    core(M, -.09, .064, .0225, W + .005, P)
    rays(M, P, -.09, .064, .0225, h, back=.2, fwd=.23, left_only=('rear',))
    P += arc('crack', [(-.13, .05), (-.18, .046), (-.24, .054), (-.3, .048)], h + .003, M['glow'], .0007, 5, .003)
    studs(M, [(.12, .04), (.12, .076), (-.31, .05), (-.31, .08), (-.125, .01), (-.065, .01)], h + .0025, P)
    lights(M, [(-.2, .082), (.09, .03)], h + .0025, P)
    MAG = cell_mag(M, -.128, -.062, .03, -.06, .032, .002, .028)
    BOLT = bolt_parts(M, .04, .074, h, .07, 'pull')
    P += e_rail(M, .1, -.2, .096)
    sz = .142
    finish('gun_vr_sniper', P, (0, -.945, zb), (0, -.43, .016), (0, .125, sz), optic=scope(M, .0, sz, .1055), scoped=True, rail=(0, -.06, .1055),
           moving=[('mag', MAG, (0, -.095, .02)), ('bolt', BOLT, (RIGHT * (h - .011), .04, .074))])
    stats('gun_vr_sniper')


# ------------------------------------------------------------------ submachine gun
def vr_smg():
    bl.reset(); M = V.mats(); P = []
    W = .048; h = W / 2; zc = .068
    grip(M, P, ang=.3, h=.11)
    stock(M, P, .1, .09, L=.2, w=.03, drop=.11)
    P.append(ext('receiver', [(.1, .03), (.1, .092), (.07, .106), (-.13, .106), (-.155, .096), (-.155, .028), (-.142, .028), (-.142, .004), (-.078, .004),
                              (-.078, .012), (.06, .012)], W, M['body'], .004, 1, cuts=[cbox((.014, .046, .016), (RIGHT * h, -.105, .086))]))
    shroud(M, P, -.145, -.3, zc, .0115, .04, top=.106, low=.026, ribs=4, seed=5)
    P.append(prism('muzzle_block', [(-.29, .03), (-.29, .104), (-.318, .1), (-.326, .09), (-.326, .04), (-.318, .032)], .032, M['dark'], .004))
    barrel('barrel', M, -.3, -.372, .087, .0098, P, rings=[(-.345, .012, .008)])
    barrel('barrel_low', M, -.3, -.352, .047, .0088, P)
    gold_ring('lip', M, -.368, .087, .0098, P, .006, .0015); gold_ring('lip', M, -.348, .047, .0088, P, .006, .0015)
    P.append(prism('handrest', [(-.17, .0235), (-.17, .029), (-.275, .029), (-.275, .0235), (-.265, .02), (-.18, .02)], .036, M['grip'], .002))
    feathers('crown', M, P, -.09, -.35, .1, 2, .042, .0235, .007, up=1, rise=.012)
    feathers('keel', M, P, -.16, -.34, .036, 2, .03, .0225, .0055, up=-1, rise=.01)
    P += talon('dorsal', [(-.14, .104), (-.08, .114), (-.0, .123)], [.028, .018, 0], M['silver'], x=h - .001, t=.005, lean=-.2, bias=-.2, trim=M['trim'])
    P += talon('dorsal2', [(-.21, .108), (-.165, .115), (-.11, .122)], [.02, .013, 0], M['silver'], x=.021, t=.004, bias=-.2)
    P += talon('fang', [(-.26, .028), (-.305, .008), (-.36, -.004)], [.022, .015, 0], M['silver'], x=.0215, t=.005, bias=.3, trim=M['trim'])
    P += talon('wing', [(-.14, .092), (-.04, .099), (.04, .099), (.1, .112)], [.012, .022, .018, 0], M['silver'], x=h + .002, t=.005, lean=-.3, bias=-.4,
               trim=M['trim'], glow=M['glow'])
    P.append(plate('armour', [(.09, .034), (.094, .088), (.068, .1), (-.128, .1), (-.15, .092), (-.15, .034), (-.07, .016), (.058, .016)], M['metal'], h - .003, h + .0025,
                   .0018, sym=False))
    P.append(plate('armour', [(.09, .034), (.094, .088), (.068, .1), (-.07, .1), (-.07, .076), (-.15, .076), (-.15, .034), (-.07, .016), (.058, .016)], M['metal'],
                   h - .003, h + .0025, .0018, sym=False, side=-1))
    P.append(plate('magwell', [(-.074, .03), (-.146, .03), (-.149, -.002), (-.072, -.002)], M['metal'], h - .003, h + .003, .002))
    core(M, -.03, .068, .021, W + .005, P)
    rays(M, P, -.03, .068, .021, h, back=.115, fwd=.11, left_only=('front_up',))
    studs(M, [(.08, .04), (.08, .084), (-.135, .04)], h + .0025, P)
    lights(M, [(.045, .09)], h + .0025, P)
    MAG = cell_mag(M, -.133, -.087, .02, -.125, .028, .0015, .03)
    CHARGE = [B('ch_stem', (.014, .009, .008), (.02, -.2, .1), M['dark'], .002),
              lathe_x('ch_knob', [(0, .005), (.012, .005), (.014, .0075), (.02, .0075), (.022, .005), (.022, 0)], (.025, -.2, .1), M['trim'], 10)]
    BOLT = bolt_parts(M, -.105, .086, h, .04, None)
    P += e_rail(M, .06, -.12, .106)
    sz = .142
    finish('gun_vr_smg', P, (0, -.378, .087), (0, -.222, .012), (0, .08, sz), optic=sight(M, -.04, sz), rail=(0, -.04, .1155),
           moving=[('mag', MAG, (0, -.108, .02)), ('charge', CHARGE, (.02, -.2, .1)), ('bolt', BOLT, (RIGHT * (h - .011), -.105, .086))])
    stats('gun_vr_smg')


# ------------------------------------------------------------------ shotgun
def vr_shotgun():
    bl.reset(); M = V.mats(); P = []
    W = .058; h = W / 2; zb = .076; zt = .046
    grip(M, P)
    stock(M, P, .14, .092, L=.21, w=.04, drop=.125)
    P.append(ext('receiver', [(.14, .02), (.14, .094), (.11, .104), (-.15, .104), (-.185, .094), (-.185, .022), (-.05, .022), (-.05, .012), (.06, .012), (.1, .02)],
                 W, M['body'], .004, 1, cuts=[cbox((.03, .09, .026), (0, -.105, .024))]))
    P.append(lathe('barrel', [(-.18, 0), (-.18, .02), (-.5, .02), (-.506, .018), (-.506, .0146), (-.46, .0146), (-.46, 0)], M['dark'], zb, n=32))
    P.append(lathe('magtube', [(-.18, 0), (-.18, .0125), (-.452, .0125), (-.458, .0105), (-.458, 0)], M['dark'], zt, n=24))
    gold_ring('tubecap', M, -.45, zt, .0125, P, .008, .002)
    P.append(prism('clamp', [(-.425, .034), (-.425, .096), (-.432, .1), (-.446, .1), (-.452, .096), (-.452, .034)], .03, M['silver'], .003))
    for y in (-.2, -.215, -.23):
        gold_ring('barrel_ring', M, y, zb, .02, P, .006, .0016, m=M['dark'])
    P.append(lathe('mouth_glow', [(-.47, .0144), (-.468, 0)], M['dim'], zb, n=16))
    for i in range(6):                               # crystal teeth round the bore
        a = i * math.pi / 3 + math.pi / 6
        P.append(crystal('tooth', (math.cos(a) * .0185, -.498, zb + math.sin(a) * .0185), (math.cos(a) * .011, -.548, zb + math.sin(a) * .011), .0048, M['crystal'], 5))
    # the jaws
    P += talon('jaw_up', [(-.41, .1), (-.5, .106), (-.59, .094)], [.022, .034, 0], M['silver'], x=.022, t=.007, lean=.3, bias=.3, trim=M['trim'], glow=M['glow'])
    P += talon('jaw_low', [(-.44, .05), (-.51, .044), (-.575, .056)], [.024, .03, 0], M['silver'], x=.0215, t=.006, lean=-.2, bias=-.3, trim=M['trim'])
    P += talon('jaw_crest', [(-.39, .098), (-.5, .109), (-.605, .1)], [.012, .016, 0], M['silver'], x=0, t=.009, two=True, sym=False, bias=.3)
    P += talon('jaw_chin', [(-.455, .034), (-.52, .028), (-.585, .042)], [.014, .016, 0], M['silver'], x=0, t=.01, two=True, sym=False, bias=-.3)
    feathers('crown', M, P, -.13, -.47, .097, 3, .046, .0285, .0075, up=1, rise=.012)
    P += talon('dorsal', [(-.16, .104), (-.1, .111), (-.03, .117)], [.028, .018, 0], M['silver'], x=h - .002, t=.005, lean=-.2, bias=-.2, trim=M['trim'])
    P += talon('wing', [(-.17, .09), (-.05, .098), (.05, .098), (.14, .112)], [.012, .024, .02, 0], M['silver'], x=h + .002, t=.006, lean=-.3, bias=-.4,
               trim=M['trim'], glow=M['glow'])
    P.append(plate('armour', [(.13, .026), (.134, .088), (.108, .098), (-.148, .098), (-.18, .09), (-.18, .028), (-.05, .028), (-.045, .016), (.058, .016)], M['metal'],
                   h - .003, h + .0025, .0018))
    core(M, -.06, .064, .027, W + .005, P)
    rays(M, P, -.06, .064, .027, h, back=.17, fwd=.115)
    P += arc('crack', [(.0, .05), (.04, .04), (.09, .046)], h + .003, M['glow'], .0007, 9, .003)
    studs(M, [(.12, .034), (.12, .08), (-.17, .036), (-.17, .084)], h + .0025, P)
    # pump forend on the tube
    PUMP = [prism('forend', [(-.25, .024), (-.25, .058), (-.262, .064), (-.385, .064), (-.4, .054), (-.4, .03), (-.39, .024)], .054, M['grip'], .006)]
    for i in range(5):
        PUMP.append(B('forend_rib', (.056, .007, .026), (0, -.275 - i * .025, .04), M['dark'], .0012))
    PUMP += talon('forend_blade', [(-.243, .052), (-.33, .046), (-.418, .052)], [.02, .026, 0], M['silver'], x=.0275, t=.005, bias=-.3, trim=M['trim'])
    PUMP += [prism('forend_cap', [(-.248, .022), (-.248, .06), (-.256, .066), (-.262, .066), (-.262, .022)], .058, M['trim'], .002)]
    SHELL = [lathe('sh_base', [(.032, 0), (.032, .0098), (.022, .0098), (.02, .0092), (.02, 0)], M['trim'], .3, n=14),
             crystal('sh_body', (0, .021, .3), (0, -.034, .3), .0092, M['crystal'], 6, .1, .55)]
    sz = .132
    P += K.iron_rear(M, .07, sz, M['dark']) + K.iron_front(M, -.3, sz, ears=False, dot=M['green'])
    finish('gun_vr_shotgun', P, (0, -.512, zb), (0, -.33, .014), (0, .1, sz),
           moving=[('pump', PUMP, (0, -.33, zt))], loose=[('x_shell', SHELL, (0, 0, .3))])
    stats('gun_vr_shotgun')


# ------------------------------------------------------------------ light machine gun
def vr_lmg():
    bl.reset(); M = V.mats(); P = []
    W = .066; h = W / 2; zb = .084
    grip(M, P)
    stock(M, P, .16, .098, L=.22, w=.04, drop=.13, spur=False)
    P.append(ext('receiver', [(.16, .02), (.16, .1), (.13, .118), (-.24, .118), (-.28, .104), (-.28, .03), (-.2, .03), (-.2, .012), (.06, .012), (.1, .02)],
                 W, M['body'], .004, 1))
    P.append(prism('shroud_top', [(-.27, .1), (-.27, .118), (-.54, .112), (-.56, .104), (-.56, .1)], .044, M['body'], .004))
    P.append(prism('shroud_low', [(-.27, .03), (-.27, .068), (-.56, .066), (-.572, .056), (-.572, .04), (-.55, .03)], .05, M['body'], .005))
    P.append(prism('shroud_nose', [(-.535, .034), (-.535, .114), (-.56, .108), (-.576, .097), (-.576, .05), (-.56, .038)], .036, M['dark'], .004))
    chamber(M, -.285, -.537, zb, .0115, P, ribs=6, seed=7)
    for i in range(6):
        P.append(B('vent', (.052, .016, .008), (0, -.31 - i * .04, .05), M['dark'], .002))
    barrel('barrel', M, -.56, -.71, zb, .013, P, rings=[(-.615, .016, .014), (-.645, .016, .008)])
    muzzle_dev(M, P, -.748, zb, .0195, .05, .0135)
    barrel('gastube', M, -.57, -.635, .05, .009, P)
    gold_ring('gaslip', M, -.631, .05, .009, P, .006, .0015)
    P.append(prism('handrest', [(-.33, .0245), (-.33, .031), (-.5, .031), (-.5, .0245), (-.49, .021), (-.34, .021)], .044, M['grip'], .002))
    P.append(prism('handle', [(-.3, .116), (-.312, .14), (-.42, .145), (-.444, .116), (-.428, .116), (-.412, .135), (-.322, .131), (-.316, .116)], .014, M['dark'], .002))
    P += talon('foresight', [(-.6, .095), (-.612, .114), (-.622, .136)], [.016, .011, 0], M['silver'], x=0, t=.004, two=True, sym=False)
    feathers('crown', M, P, -.262, -.615, .109, 3, .04, .0245, .007, up=1, rise=.01)
    feathers('keel', M, P, -.28, -.605, .041, 3, .034, .0275, .006, up=-1, rise=.01)
    P += talon('wing', [(-.26, .104), (-.1, .112), (.06, .112), (.16, .124)], [.012, .024, .02, 0], M['silver'], x=h + .002, t=.006, lean=-.3, bias=-.4,
               trim=M['trim'], glow=M['glow'])
    P += talon('fang', [(-.21, .03), (-.26, .006), (-.315, -.012)], [.03, .02, 0], M['silver'], x=h - .004, t=.006, bias=.3, trim=M['trim'])
    P.append(plate('armour', [(.15, .026), (.154, .094), (.128, .112), (-.238, .112), (-.274, .1), (-.274, .036), (-.2, .036), (-.196, .016), (.058, .016)], M['metal'],
                   h - .003, h + .0025, .002))
    P.append(B('feed', (.012, .07, .034), (h + .003, -.13, .096), M['dark'], .003))
    core(M, .03, .066, .026, W + .005, P)
    rays(M, P, .03, .066, .026, h, back=.12, fwd=.1)
    studs(M, [(.14, .034), (.14, .09), (-.26, .042), (-.26, .094), (-.19, .022)], h + .0025, P)
    lights(M, [(-.22, .1), (.1, .1)], h + .0025, P)
    # reload parts: the feed cover (hinged at its front), the belt box, the charging handle
    HATCH = [prism('cover', [(-.058, .118), (-.058, .127), (-.078, .134), (-.185, .134), (-.2, .127), (-.2, .118)], .058, M['body'], .003),
             B('cover_latch', (.02, .012, .008), (0, -.064, .1295), M['trim'], .002)]
    HATCH += talon('cover_blade', [(-.062, .127), (-.13, .136), (-.205, .128)], [.01, .014, 0], M['silver'], x=.029, t=.004, bias=.3, trim=M['trim'])
    MAG = [prism('box', [(-.065, .01), (-.065, -.1), (-.075, -.112), (-.185, -.112), (-.195, -.1), (-.195, .01)], .072, M['dark'], .004),
           B('box_window', (.0735, .05, .012), (0, -.13, -.03), M['dim'], 0),
           B('box_bar', (.075, .006, .016), (0, -.115, -.03), M['dark'], .001), B('box_bar', (.075, .006, .016), (0, -.145, -.03), M['dark'], .001),
           prism('box_lid', [(-.062, .012), (-.062, .002), (-.198, .002), (-.198, .012)], .076, M['trim'], .002),
           B('belt_link', (.004, .014, .098), (.0405, -.118, .046), M['dark'], .001)]
    MAG += talon('box_blade', [(-.07, -.012), (-.1, -.07), (-.172, -.128)], [.03, .036, 0], M['silver'], x=.0365, t=.005, bias=.3, trim=M['trim'])
    for i in range(6):
        MAG += round_('belt%d' % i, M, -.104, .05, .0062, .042, .004 + i * .0166)
    CHARGE = [B('ch_stem', (.012, .012, .008), (RIGHT * (h + .002), -.02, .092), M['dark'], .002),
              lathe_x('ch_knob', [(0, .005), (.012, .005), (.014, .0078), (.021, .0078), (.023, .005), (.023, 0)], (RIGHT * (h + .006), -.02, .092), M['trim'], 10, -1)]
    P += e_rail(M, .13, -.04, .118)
    sz = .154
    finish('gun_vr_lmg', P, (0, -.752, zb), (0, -.42, .014), (0, .14, sz), optic=sight(M, .03, sz), rail=(0, .03, .1275),
           moving=[('hatch', HATCH, (0, -.2, .118)), ('mag', MAG, (0, -.13, .008)), ('charge', CHARGE, (RIGHT * (h + .002), -.02, .092))])
    stats('gun_vr_lmg')


# ------------------------------------------------------------------ hand cannon
def vr_handcannon():
    bl.reset(); M = V.mats(); P = []
    zc = .062; zb = .0755; rc = .027; hx = .004; hz = zc - .031; py = -.0035
    grip(M, P, ang=.38, h=.12, L=.06)
    P.append(ext('frame', [(.085, .04), (.09, .08), (.07, .096), (.03, .108), (-.045, .108), (-.05, .1), (-.075, .1), (-.075, .036), (-.045, .026), (-.02, .016),
                           (.0, .012), (.04, .012), (.06, .03)], .04, M['body'], .003, 1, cuts=[cbox((.06, .066, .062), (0, py, zc))]))
    P += talon('hammer', [(.064, .09), (.09, .106), (.122, .126)], [.02, .013, 0], M['trim'], x=0, t=.0055, two=True, sym=False, bias=-.2)
    P += talon('strap', [(-.074, .1035), (-.01, .109), (.05, .104), (.1, .119)], [.008, .013, .012, 0], M['silver'], x=.0195, t=.0045, lean=-.2, bias=-.3,
               trim=M['trim'], glow=M['glow'], g=.0012)
    P += talon('cheek', [(.04, .09), (.066, .094), (.094, .084)], [.01, .014, 0], M['silver'], x=.0205, t=.004, bias=.3)
    P += talon('under', [(.05, .04), (.005, .022), (-.06, .024)], [.018, .015, 0], M['silver'], x=.0205, t=.0045, bias=-.3, trim=M['trim'])
    P += talon('tang', [(.07, .05), (.086, .036), (.094, .016)], [.016, .012, 0], M['silver'], x=.0195, t=.004, bias=.3)
    P.append(plate('lug_plate', [(-.05, .096), (-.072, .096), (-.072, .04), (-.046, .03), (-.04, .034), (-.046, .06)], M['metal'], .017, .0218, .0014))
    P += talon('guard_spur', [(-.04, .014), (-.07, .004), (-.105, .004)], [.012, .01, 0], M['silver'], x=.006, t=.004, two=True, sym=False)
    core(M, .06, .066, .018, .043, P, spikes=False)
    # cylinder: an open cage of silver bars round six crystal rounds
    CYL = [lathe('cyl_rear', [(.0265, 0), (.0265, rc - .0012), (.0245, rc), (.0205, rc), (.0205, 0)], M['silver'], zc, n=12),
           lathe('cyl_front', [(-.0275, 0), (-.0275, rc), (-.0315, rc), (-.0335, rc - .0012), (-.0335, 0)], M['silver'], zc, n=12),
           lathe('cyl_axle', [(.0205, .0075), (-.0275, .0075)], M['dark'], zc, n=10)]
    ROUNDS = []
    for i in range(6):
        a = i * math.pi / 3
        CYL.append(tube('cyl_bar', .0032, .05, .0215, zc + math.sin(a) * (rc - .0034), M['silver'], 8, x=math.cos(a) * (rc - .0034)))
        b = a + math.pi / 6
        ROUNDS += round_('rnd', M, .0262, .057, .0064, math.cos(b) * .0172, zc + math.sin(b) * .0172, tip=.98)
    gold_ring('cyl_band', M, .0225, zc, rc, CYL, .003, .0012, n=12); gold_ring('cyl_band', M, -.0295, zc, rc, CYL, .003, .0012, n=12)
    CRANE = [tube('ejrod', .0034, .034, -.0335, zc, M['silver'], 12),
             lathe('ejknob', [(-.0655, 0), (-.0655, .005), (-.072, .005), (-.074, .003), (-.074, 0)], M['trim'], zc, n=10),
             B('yoke', (.008, .006, .034), (.002, -.036, zc - .015), M['dark'], .001), tube('yokepin', .0036, .05, .0, hz, M['dark'], 12, x=hx)]
    LOADER = [lathe('sl_body', [(.016, 0), (.016, .0235), (.006, .0235), (.004, .022), (.004, 0)], M['dark'], 0, n=12),
              lathe('sl_knob', [(.03, 0), (.03, .008), (.016, .008), (.016, 0)], M['trim'], 0, n=10)]
    for i in range(6):
        b = i * math.pi / 3 + math.pi / 6
        LOADER += round_('sl_rnd', M, .004, .054, .0064, math.cos(b) * .0172, math.sin(b) * .0172, tip=.98)
    # the long lit shroud
    P.append(prism('shroud_top', [(-.075, .09), (-.075, .108), (-.27, .104), (-.3, .097), (-.3, .09)], .034, M['body'], .003))
    P.append(prism('shroud_low', [(-.075, .036), (-.075, .058), (-.3, .056), (-.312, .05), (-.29, .04)], .034, M['body'], .003))
    P.append(prism('shroud_nose', [(-.268, .042), (-.268, .104), (-.3, .098), (-.316, .089), (-.316, .06), (-.3, .048)], .03, M['dark'], .003))
    chamber(M, -.08, -.272, zb, .0105, P, ribs=4, seed=9)
    muzzle_dev(M, P, -.338, zb, .0165, .04, .0085)
    feathers('crown', M, P, -.078, -.35, .1, 2, .036, .019, .006, up=1, rise=.008)
    feathers('keel', M, P, -.085, -.325, .044, 2, .026, .0185, .005, up=-1, rise=.008)
    P += talon('fang', [(-.08, .038), (-.14, .016), (-.21, .008)], [.026, .018, 0], M['silver'], x=.019, t=.005, bias=.3, trim=M['trim'])
    P += talon('strap_blade', [(.03, .105), (-.01, .109), (-.055, .104)], [.008, .01, 0], M['silver'], x=.019, t=.003, bias=.3)
    studs(M, [(.03, .032), (-.062, .046), (-.062, .09)], .0205, P)
    sz = .128
    P += [B('rear_notchL', (.008, .012, .014), (.009, .06, sz - .004), M['dark'], .002), B('rear_notchR', (.008, .012, .014), (-.009, .06, sz - .004), M['dark'], .002),
          B('rear_bridge', (.03, .012, .012), (0, .06, sz - .017), M['dark'], .002)]
    P += K.iron_front(M, -.29, sz, ears=False, dot=M['green'])
    finish('gun_vr_handcannon', P, (0, -.342, zb), (0, -.02, -.02), (0, .13, sz),
           moving=[('crane', CRANE, (hx, py, hz)), ('cylinder', CYL, (0, py, zc), 'crane'), ('rounds', ROUNDS, (0, py, zc), 'cylinder')],
           loose=[('x_speedloader', LOADER, (0, 0, 0))])
    stats('gun_vr_handcannon')


# ------------------------------------------------------------------ pistol
def vr_pistol():
    bl.reset(); M = V.mats(); P = []
    zb = .066
    grip(M, P, ang=.3, h=.105, w=.03, z=.012, L=.062, heel=False)
    P.append(prism('frame', [(.036, .05), (.04, .03), (.0, .021), (-.09, .021), (-.12, .03), (-.172, .035), (-.19, .044), (-.187, .05)], .03, M['body'], .003))
    P.append(lathe('barrel', [(-.1, 0), (-.1, .0078), (-.201, .0078), (-.201, .0052), (-.17, .0052), (-.17, 0)], M['dark'], zb, n=16))
    P += talon('fang', [(-.1, .026), (-.16, .01), (-.225, .004)], [.018, .014, 0], M['silver'], x=.0145, t=.0045, bias=.3, trim=M['trim'])
    P.append(plate('frame_plate', [(.03, .047), (.03, .032), (-.0, .0255), (-.03, .0255), (-.044, .037), (-.03, .047)], M['metal'], .012, .0166, .0012))
    P += talon('dust_blade', [(-.085, .037), (-.14, .039), (-.2, .046)], [.016, .012, 0], M['silver'], x=.0148, t=.0035, bias=-.3, trim=M['trim'], g=.0011)
    P += talon('guard_spur', [(-.07, .014), (-.095, .002), (-.125, .0)], [.01, .008, 0], M['silver'], x=.0, t=.0035, two=True, sym=False)
    lights(M, [(-.14, .039)], .0166, P, .0018)
    core(M, -.06, .037, .0105, .0315, P, spikes=False)
    studs(M, [(.02, .036), (-.15, .038)], .0152, P, .0018)
    SLIDE = [prism('slide', [(.044, .052), (.05, .066), (.04, .084), (.02, .089), (-.15, .087), (-.19, .078), (-.2, .064), (-.192, .052)], .03, M['dark'], .003),
             B('slide_light', (.0308, .12, .0085), (0, -.08, .0585), M['dim'], 0),
             B('slide_hot', (.0314, .108, .0015), (0, -.08, .0585), M['glow'], 0),
             lathe('crown', [(-.192, .0106), (-.202, .0106), (-.205, .009), (-.205, .0082), (-.192, .0082)], M['silver'], zb, n=8, closed=True, phase=math.pi / 8)]
    for i in range(5):
        SLIDE.append(B('slide_rib', (.0322, .0045, .0115), (0, -.034 - i * .023, .0585), M['dark'], .0008))
    feathers('slide_crown', M, SLIDE, .04, -.225, .0775, 3, .03, .0172, .0055, up=1, rise=.006, bulge=.002, overlap=.5)
    SLIDE += talon('slide_spur', [(.03, .072), (.056, .084), (.086, .1)], [.02, .014, 0], M['trim'], x=0, t=.0055, two=True, sym=False, bias=-.2)
    for i, y in enumerate((-.03, -.08, -.125)):                          # a serrated spine along the top
        SLIDE += talon('slide_fin%d' % i, [(y, .087), (y + .016, .091), (y + .04, .095)], [.012, .008, 0], M['silver'], x=0, t=.004, two=True, sym=False)
    for s_ in (1, -1):
        SLIDE.append(vein('slide_arc', [(s_ * .0158, -.03, .058), (s_ * .0158, -.07, .061), (s_ * .0158, -.1, .0565), (s_ * .0158, -.135, .06)], M['glow'], .0006,
                          3 + s_, .0016, 3))
    sz = .1
    SLIDE += [B('rear_base', (.026, .01, .006), (0, .03, .09), M['dark'], .001),
              B('rearL', (.008, .009, .009), (.0078, .03, sz - .003), M['dark'], .0008), B('rearR', (.008, .009, .009), (-.0078, .03, sz - .003), M['dark'], .0008),
              B('frontpost', (.0035, .007, .012), (0, -.165, sz - .006), M['dark'], .0008),
              ball('postdot', .0017, (0, -.161, sz - .002), M['green'], scale=(1, .4, 1), seg=10, rings=6)]
    g = gp(.3, 0, .016)
    c = g(.004, .06)
    MAG = [B('magbody', (.02, .028, .098), (0, c[0], c[1]), M['dark'], .0015, rot=(.3, 0, 0)),
           prism('magbase', [g(-.024, .104), g(.03, .1), g(.036, .113), g(.0, .118), g(-.022, .113)], .034, M['trim'], .002),
           B('maglight', (.0205, .006, .03), (0, g(.019, .05)[0], g(.019, .05)[1]), M['dim'], 0, rot=(.3, 0, 0))]
    top = g(.004, .012)
    finish('gun_vr_pistol', P, (0, -.208, zb), (0, -.02, -.02), (0, .1, sz), rail=(0, -.06, .0875),
           moving=[('mag', MAG, (0, top[0], top[1])), ('slide', SLIDE, (0, -.06, zb))])
    stats('gun_vr_pistol')


# ------------------------------------------------------------------ fusion rifle
def vr_fusion():
    bl.reset(); M = V.mats(); P = []
    W = .06; h = W / 2; zc = .066
    grip(M, P)
    stock(M, P, .14, .09, L=.2, w=.034, drop=.12)
    P.append(ext('receiver', [(.14, .02), (.14, .096), (.1, .11), (-.15, .11), (-.2, .098), (-.2, .02), (-.1, .016), (-.055, .012), (.06, .012), (.1, .02)],
                 W, M['body'], .004, 1))
    P.append(prism('jaw_up', [(-.19, .088), (-.19, .108), (-.38, .104), (-.47, .095), (-.47, .088)], .046, M['body'], .004))
    P.append(prism('jaw_low', [(-.19, .022), (-.19, .044), (-.44, .04), (-.47, .034), (-.44, .024)], .046, M['body'], .004))
    P.append(prism('handrest', [(-.26, .0165), (-.26, .023), (-.4, .023), (-.4, .0165), (-.39, .013), (-.27, .013)], .04, M['grip'], .002))
    # emitter: the lance the jaws cradle
    P.append(lathe('emitter', [(-.372, 0), (-.372, .0125), (-.39, .0145), (-.42, .0145), (-.44, .0085), (-.462, .0085), (-.462, .0045), (-.44, .0045), (-.44, 0)],
                   M['dark'], zc, n=12))
    gold_ring('emitter_ring', M, -.405, zc, .0145, P, .01, .002, n=12)
    P.append(prism('emitter_strut', [(-.384, .042), (-.384, .09), (-.4, .09), (-.4, .042)], .012, M['dark'], .002))
    P.append(crystal('lance', (0, -.45, zc), (0, -.525, zc), .0075, M['glow'], 6, .2, .5))
    for i in range(3):
        a = i * 2 * math.pi / 3 + math.pi / 2
        P.append(crystal('lance_shard', (math.cos(a) * .016, -.455, zc + math.sin(a) * .016), (math.cos(a) * .011, -.5, zc + math.sin(a) * .011), .0035, M['crystal'], 5))
    # silver
    feathers('crown', M, P, -.12, -.53, .1, 3, .05, .0265, .008, up=1, rise=.014)
    feathers('keel', M, P, -.17, -.51, .031, 3, .036, .0255, .006, up=-1, rise=.012)
    P += talon('fang', [(-.09, .022), (-.17, -.008), (-.25, -.042)], [.046, .03, 0], M['silver'], x=h - .004, t=.007, bias=.3, trim=M['trim'])
    P += talon('dorsal', [(-.16, .106), (-.09, .117), (-.01, .127)], [.03, .02, 0], M['silver'], x=h - .002, t=.005, lean=-.2, bias=-.2, trim=M['trim'])
    P += talon('dorsal2', [(-.25, .11), (-.2, .119), (-.14, .127)], [.022, .014, 0], M['silver'], x=.024, t=.004, bias=-.2)
    P += talon('wing', [(-.02, .1), (.06, .103), (.14, .116)], [.016, .022, 0], M['silver'], x=h + .002, t=.005, lean=-.3, bias=-.4, trim=M['trim'], glow=M['glow'])
    P.append(plate('armour', [(.13, .026), (.134, .09), (.098, .104), (-.148, .104), (-.194, .094), (-.194, .026), (-.1, .021), (.058, .016)], M['metal'],
                   h - .003, h + .0025, .002))
    core(M, .0, .068, .026, W + .005, P, name='core')
    core(M, -.11, .066, .019, W + .005, P, spikes=False, name='core2')
    rays(M, P, .0, .068, .026, h, back=.13, fwd=0)
    P.append(B('core_bridge', (W + .012, .05, .008), (0, -.058, .067), M['trim'], .002))
    studs(M, [(.12, .034), (.12, .084), (-.18, .036), (-.18, .09)], h + .0025, P)
    # reload parts: the core crystal between the jaws and the flank hatch over it (hinged along its top edge)
    BIO = [crystal('cartridge', (0, -.205, zc), (0, -.365, zc), .0135, M['crystal'], 6, .1, .9, r1=.0135),
           lathe('cart_cap', [(-.2, 0), (-.2, .0155), (-.214, .0155), (-.217, .0135), (-.217, 0)], M['trim'], zc, n=6),
           lathe('cart_cap2', [(-.352, 0), (-.352, .0135), (-.355, .0155), (-.368, .0155), (-.368, 0)], M['trim'], zc, n=6),
           lathe('cart_line', [(-.21, 0), (-.215, .004), (-.355, .004), (-.36, 0)], M['glow'], zc, n=6)]
    for k in range(3):
        a = k * 2.1
        BIO.append(vein('cart_arc', [(math.cos(a + j * .7) * .0142, -.22 - j * .034, zc + math.sin(a + j * .7) * .0142) for j in range(5)], M['glow'], .0007, 20 + k, .003, 3))
    HATCH = [plate('hatch', [(-.2, .086), (-.2, .05), (-.215, .046), (-.35, .046), (-.366, .052), (-.366, .086)], M['silver'], .0235, .0275, .002, sym=False),
             plate('hatch_inlay', [(-.225, .078), (-.225, .058), (-.34, .058), (-.34, .078)], M['dark'], .0265, .0285, .001, sym=False),
             B('hatch_pull', (.006, .03, .006), (.029, -.283, .05), M['trim'], .0015)]
    HATCH += arc('hatch_crack', [(-.235, .07), (-.27, .064), (-.3, .072), (-.33, .066)], .0288, M['glow'], .0006, 4, .002, sym=False)
    P.append(plate('window_frame', [(-.2, .09), (-.2, .084), (-.366, .084), (-.366, .09)], M['trim'], .0235, .0265, .001, sym=False, side=-1))
    P.append(plate('window_frame', [(-.2, .052), (-.2, .046), (-.366, .046), (-.366, .052)], M['trim'], .0235, .0265, .001, sym=False, side=-1))
    P += e_rail(M, .1, -.12, .11)
    sz = .146
    finish('gun_vr_fusion', P, (0, -.5, zc), (0, -.33, .008), (0, .1, sz), optic=sight(M, -.02, sz), rail=(0, -.02, .1195),
           moving=[('hatch', HATCH, (.0255, -.283, .086)), ('biomass', BIO, (0, -.285, zc))])
    stats('gun_vr_fusion')


# ------------------------------------------------------------------ rocket launcher
def vr_rocket():
    bl.reset(); M = V.mats(); P = []
    zc = .105; R = .058; f12 = math.pi / 12
    grip(M, P)
    P.append(prism('saddle', [(.07, .012), (.09, .052), (-.11, .052), (-.11, .03), (-.062, .012)], .04, M['body'], .004))
    P.append(lathe('tube', [(.34, .049), (.34, R), (-.5, R), (-.5, .049)], M['body'], zc, n=40, closed=True))
    P.append(lathe('bell', [(-.455, R + .001), (-.5, .064), (-.56, .08), (-.578, .082), (-.578, .07), (-.52, .052), (-.455, .052)], M['silver'], zc, n=12, closed=True,
                   phase=f12))
    P.append(lathe('bell_lip', [(-.573, .0832), (-.58, .0852), (-.587, .0832), (-.587, .069), (-.573, .069)], M['trim'], zc, n=12, closed=True, phase=f12))
    P.append(lathe('mouth_glow', [(-.48, .05), (-.47, 0)], M['dim'], zc, n=24))
    for y, rr in ((-.505, .05), (-.53, .058)):
        P.append(lathe('mouth_rib', [(y + .004, rr + .004), (y + .004, rr - .004), (y - .004, rr - .004), (y - .004, rr + .004)], M['dark'], zc, n=24, closed=True))
    for i in range(6):
        a = i * math.pi / 3 + math.pi / 6
        P.append(crystal('tooth', (math.cos(a) * .076, -.57, zc + math.sin(a) * .076), (math.cos(a) * .064, -.625, zc + math.sin(a) * .064), .0065, M['crystal'], 5))
    P.append(lathe('nozzle', [(.33, R + .001), (.345, .064), (.385, .073), (.392, .071), (.392, .061), (.345, .05), (.33, .05)], M['silver'], zc, n=12, closed=True,
                   phase=f12))
    P.append(lathe('nozzle_lip', [(.388, .0745), (.394, .0762), (.4, .0745), (.4, .06), (.388, .06)], M['trim'], zc, n=12, closed=True, phase=f12))
    P.append(lathe('nozzle_glow', [(.345, .05), (.34, 0)], M['dim'], zc, n=24))
    for y in (-.4, -.09, .25):
        P.append(lathe('band', [(y + .013, R - .001), (y + .013, R + .0045), (y - .013, R + .0045), (y - .013, R - .001)], M['dark'], zc, n=40, closed=True))
        gold_ring('band_gold', M, y, zc, R + .0045, P, .005, .0014, n=40)
    P.append(lathe('tube_light', [(-.13, R - .001), (-.13, R + .0012), (-.36, R + .0012), (-.36, R - .001)], M['dim'], zc, n=40, closed=True))
    for i in range(7):
        y = -.15 - i * .032
        P.append(lathe('tube_rib', [(y + .004, R), (y + .004, R + .0035), (y - .004, R + .0035), (y - .004, R)], M['dark'], zc, n=40, closed=True))
    for k in range(4):
        a0 = .5 + k * 1.6
        P.append(vein('tube_arc', [(math.cos(a0 + j * .25) * (R + .002), -.14 - j * .05, zc + math.sin(a0 + j * .25) * (R + .002)) for j in range(5)], M['glow'],
                      .0008, 40 + k, .004, 3))
    P.append(prism('handrest', [(-.2, .041), (-.2, .049), (-.32, .049), (-.32, .041), (-.31, .037), (-.21, .037)], .05, M['grip'], .002))
    P.append(prism('shoulder', [(.19, .05), (.2, .022), (.31, .018), (.335, .05)], .06, M['grip'], .006))
    # silver
    feathers('crown', M, P, -.06, -.5, zc + .04, 3, .072, .051, .009, up=1, rise=.014, lean=-.35)
    feathers('keel', M, P, -.1, -.47, zc - .04, 3, .056, .05, .007, up=-1, rise=.012, lean=-.35)
    P += talon('dorsal', [(-.02, zc + .05), (.06, zc + .072), (.16, zc + .088)], [.036, .024, 0], M['silver'], x=.046, t=.006, lean=.3, bias=-.2, trim=M['trim'])
    P += talon('tail', [(.1, zc + .02), (.22, zc + .028), (.345, zc + .05)], [.03, .04, 0], M['silver'], x=.057, t=.006, lean=.3, bias=-.3, trim=M['trim'],
               glow=M['glow'])
    P += talon('tail_low', [(.12, zc - .03), (.24, zc - .034), (.35, zc - .05)], [.024, .03, 0], M['silver'], x=.054, t=.005, lean=-.3, bias=.3)
    P += talon('fang', [(-.1, .05), (-.15, .026), (-.2, .012)], [.03, .02, 0], M['silver'], x=.021, t=.005, bias=.3, trim=M['trim'])
    core(M, -.0, zc, .03, 2 * R + .003, P)
    # reload parts: the breech lid on top (hinged on the right) and the crystal warhead under it
    P.append(prism('breech', [(.05, .15), (.05, .168), (.06, .174), (.22, .174), (.235, .166), (.235, .15)], .084, M['body'], .004))
    HATCH = [prism('lid', [(.064, .174), (.064, .18), (.075, .184), (.21, .184), (.222, .18), (.222, .174)], .07, M['silver'], .003),
             B('lid_pull', (.008, .04, .008), (.034, .143, .181), M['trim'], .002),
             prism('lid_inlay', [(.09, .184), (.09, .1852), (.196, .1852), (.196, .184)], .03, M['dark'], .0004)]
    MAG = [lathe('wh_base', [(.205, 0), (.205, .03), (.195, .032), (.175, .032), (.17, .03), (.17, 0)], M['trim'], zc, n=12),
           crystal('wh_crystal', (0, .172, zc), (0, .07, zc), .03, M['crystal'], 6, .1, .6),
           lathe('wh_line', [(.172, 0), (.17, .006), (.1, .006), (.09, 0)], M['glow'], zc, n=6)]
    P += K.rail(M, .02, -.14, .163, .022, M['dark'])
    sz = .199
    finish('gun_vr_rocket', P, (0, -.59, zc), (0, -.26, .034), (0, .1, sz), optic=sight(M, -.06, sz), rail=(0, -.06, .1725),
           moving=[('hatch', HATCH, (RIGHT * .035, .143, .176)), ('mag', MAG, (0, .143, zc))])
    stats('gun_vr_rocket')


def stats(name):
    print('[requiem] %s: %d tris' % (name, bl.tri_count()))


GUNS = dict(vr_rifle=vr_rifle, vr_sniper=vr_sniper, vr_smg=vr_smg, vr_shotgun=vr_shotgun, vr_lmg=vr_lmg,
            vr_handcannon=vr_handcannon, vr_pistol=vr_pistol, vr_fusion=vr_fusion, vr_rocket=vr_rocket)

if __name__ == '__main__':
    args = [a for a in (sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []) if a]
    for k in (args or list(GUNS)):
        GUNS[k]()
