"""Weapons v3: high-detail first-person guns in three classes, plus mountable sight attachments.

  energy  - the glowing sci-fi line (auto, pulse, scout, hand cannon, shotgun, sniper, rocket, SMG, sidearm, rotary HMG,
            exotic energy rifle). gun_body takes the shader colour, gun_glow the rarity colour.
  kinetic - real-material firearms, never tinted: assault rifle (stamped receiver, walnut, curved magazine), carbine
            (flat-top, free-float handguard, collapsible stock), bolt-action precision rifle (thumbhole stock, fluted
            barrel), service pistol, pump shotgun, compact SMG, battle rifle, revolver.
  horror  - living biomass guns grown as signed-distance fields: spitter rifle, bile cannon, brood launcher. They carry
            shape keys 'pulse' (sacs swell, flesh breathes) and 'gape' (the maw opens) that the game animates.

Frame: origin = pistol grip (right hand), barrel along Blender -Y (-> +Z in three.js), Z up, right side = -X.
Empties: muzzle, foregrip (left hand), sight (the eye point: looking from it along -Y passes through the sight),
optional 'scope' (magnified optic: the HUD scope view takes over when aiming), optional 'rail' (top of the optic rail
where gun_attach.glb sights mount). A gun's built-in sight that a mounted optic replaces is a child node 'OPTIC'.
Every gun mesh carries the `_wear` vertex attribute (gunkit.wear_attr).

Material names are an API (src/game/weapons.js styleMesh):
  energy: gun_body, gun_metal, gun_dark, gun_trim, gun_glow, gun_grip, gun_lens, gun_dot, gun_tritium
  kinetic: gun_steel, gun_parkerized, gun_polymer, gun_polymer_od, gun_wood, gun_rubber, gun_brass, gun_sightpaint,
           gun_sightorange, gun_shell, gun_lens, gun_dot, gun_optic
  horror: bio_flesh, bio_bone, bio_glow, bio_maw

Run: blender --background --python tools/blender/weapons.py [-- name ...]   (no names = everything)
"""
import bpy, math, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import bl
import sdf
import gunkit as K
from gunkit import B, ext, tube, cbox, ccyl, cylx, cylz, ball, ring, rod, R90

RIGHT = -1      # the gun's right side is -X


def finish(name, parts, muzzle, fore, sight, optic=(), rail=None, scoped=False, organic=(), cyl_axis=None, keys=None):
    g = K.assemble(name, parts, organic, cyl_axis=cyl_axis)
    if optic:
        o = K.assemble('OPTIC', list(optic)); o.parent = g
    bl.empty('muzzle', muzzle, g); bl.empty('foregrip', fore, g); bl.empty('sight', sight, g)
    if scoped:
        bl.empty('scope', sight, g)
    if rail:
        bl.empty('rail', rail, g)
    if keys:
        keys(g)
    K.export(name + '.glb')


def mirror_pair(fn):
    """fn(side) -> parts, called for both sides."""
    return fn(1) + fn(-1)


# ================================================================== energy line (upgraded)
def e_grip(M, y=0.0, z=0.0, ang=.28, h=.12):
    P = [K.grip_profile('grip', M['grip'], ang=ang, h=h, w=.034, y=y, z=z + .004)]
    P += K.trigger_group(M, M['dark'], M['trim'], y=y - .012, z=z + .012, L=.072, drop=.05)
    return P


def e_screws(M, pts, xw):
    P = []
    for y, z in pts:
        P += K.screw(xw / 2, y, z, M['trim'], .0028, 1, M['dark']) + K.screw(-xw / 2, y, z, M['trim'], .0028, -1, M['dark'])
    return P


def red_dot(M, y, z):
    """Built-in holo sight; the dot floats on the sight line at (0, y - .03, z)."""
    return [B('rd_base', (.034, .05, .012), (0, y, z - .025), M['dark'], .004),
            B('rd_hoodL', (.005, .05, .04), (.019, y, z - .002), M['dark'], .002),
            B('rd_hoodR', (.005, .05, .04), (-.019, y, z - .002), M['dark'], .002),
            B('rd_top', (.043, .05, .005), (0, y, z + .019), M['dark'], .002),
            B('rd_glass', (.033, .002, .034), (0, y - .02, z), M['lens'], 0),
            ball('rd_dot', .0016, (0, y - .03, z), M['dot'], seg=10, rings=6),
            cylx('rd_knob', .006, .012, (.027, y + .01, z - .01), M['dark'], 20),
            B('rd_clamp', (.03, .018, .012), (0, y + .012, z - .035), M['dark'], .002)]


def scope_tube(M, y, z, L=.16, r=.022, objective=.03):
    P = [tube('scope_tube', r, L * .6, y - L * .2 + L * .3, z, M['metal'], 40),
         tube('scope_obj', r, L * .3, y - L * .5, z, M['metal'], 40, r2=objective),
         tube('scope_bell', objective, L * .12, y - L * .8, z, M['dark'], 40),
         tube('scope_eye', r * 1.18, L * .14, y + L * .24, z, M['dark'], 40),
         tube('lens_f', objective * .86, .003, y - L * .92, z, M['lens'], 40, bevel=0),
         tube('lens_r', r * .95, .003, y + L * .245, z, M['lens'], 32, bevel=0),
         cylz('turret_top', .009, .016, (0, y - L * .25, z + r + .008), M['trim'], 24),
         cylx('turret_side', .009, .016, (r + .008, y - L * .25, z), M['dark'], 24),
         ring('eyering', r * 1.18, .0025, (0, y + L * .17 - .002, z), M['trim'], maj=40, mn=8)]
    for yy in (y - L * .05, y - L * .45):
        P.append(ring('scopering', r + .003, .0035, (0, yy, z), M['dark'], maj=40, mn=8))
        P.append(B('ringbase', (.03, .014, .016), (0, yy, z - r - .008), M['dark'], .003))
    return P


def e_rail(M, y0, y1, z, w=.026):
    return K.rail(M, y0, y1, z, w, M['dark'])


def vents(M, y0, y1, z, x, n=5, h=.02):
    step = (y0 - y1) / n
    return [B('vent', (.004, step * .55, h), (x, y0 - step * (i + .5), z), M['dark'], .0012) for i in range(n)]


def auto_rifle():
    bl.reset(); M = K.energy_mats(); P = []
    P += e_grip(M)
    P += [ext('upper', [(.14, .048), (.14, .098), (-.2, .098), (-.23, .088), (-.23, .048)], .052, M['body'], .006,
              cuts=[cbox((.012, .06, .022), (RIGHT * .026, -.0, .072))]),
          ext('lower', [(.08, .05), (.08, .012), (.02, .006), (-.06, .006), (-.06, -.006), (-.15, -.006), (-.15, .05)], .048, M['body'], .006),
          B('boltface', (.04, .05, .016), (RIGHT * .012, .0, .072), M['metal'], .002),
          B('chamfer', (.056, .3, .012), (0, -.07, .045), M['metal'], .003),
          B('chargeh', (.034, .02, .012), (0, .13, .1), M['dark'], .003), B('chargelatch', (.012, .012, .01), (.016, .126, .1), M['trim'], .002),
          ext('handguard', [(-.22, .03), (-.22, .094), (-.46, .094), (-.47, .084), (-.47, .04), (-.46, .03)], .06, M['metal'], .01,
              cuts=[cbox((.08, .022, .012), (0, -.26 - i * .045, .062)) for i in range(5)]),
          B('hg_inner', (.05, .24, .05), (0, -.34, .062), M['dark'], .004),
          B('hg_glow', (.002, .16, .012), (.031, -.34, .078), M['glow'], 0), B('hg_glow2', (.002, .16, .012), (-.031, -.34, .078), M['glow'], 0),
          ext('mag', [(-.07, .01), (-.075, -.09), (-.09, -.15), (-.15, -.15), (-.14, -.09), (-.135, .01)], .034, M['metal'], .005),
          B('magbase', (.04, .07, .014), (0, -.12, -.152), M['dark'], .004),
          B('magwin', (.002, .03, .06), (.0175, -.11, -.06), M['glow'], 0),
          ext('stock', [(.14, .1), (.36, .085), (.37, .07), (.37, -.02), (.34, -.03), (.2, .02), (.14, .04)], .042, M['body'], .012,
              cuts=[cbox((.06, .1, .03), (0, .26, .03))]),
          ext('stockpad', [(.37, .088), (.385, .088), (.385, -.035), (.37, -.035)], .046, M['grip'], .006),
          B('cheek', (.044, .1, .02), (0, .2, .094), M['metal'], .005),
          B('trimband', (.064, .016, .068), (0, -.22, .062), M['trim'], .003)]
    P += K.pins(.049, [(.06, .025), (-.12, .025), (.1, .07)], M['trim'])
    P += e_screws(M, [(-.3, .045), (-.42, .045), (.25, .06)], .06)
    P += [tube('barrel', .012, .16, -.46, .062, M['dark'], 32)] + K.brake(-.6, .062, .019, .07, M['metal'], 3)
    P += K.sling_loop(.33, -.02, M['dark']) + K.sling_loop(-.45, .025, M['dark'])
    P += e_rail(M, .1, -.44, .098)
    sz = .135
    finish('gun_auto', P, (0, -.68, .062), (0, -.32, .02), (0, .1, sz), optic=red_dot(M, -.02, sz), rail=(0, -.02, .1075))


def pulse_rifle():
    bl.reset(); M = K.energy_mats(); P = []
    P += e_grip(M)
    P += [ext('body', [(.14, .01), (.14, .1), (-.22, .1), (-.26, .08), (-.26, .01)], .062, M['body'], .02,
              cuts=[cbox((.012, .06, .02), (RIGHT * .031, -.02, .075))]),
          B('glowpanel', (.002, .22, .05), (.032, -.08, .055), M['glow'], 0),
          B('glowpanel2', (.002, .22, .05), (-.032, -.08, .055), M['glow'], 0),
          B('topcut', (.066, .16, .02), (0, -.16, .104), M['metal'], .004),
          tube('barrel', .015, .12, -.26, .06, M['dark'], 32), tube('emitter', .026, .05, -.36, .06, M['trim'], 40, hollow=.016),
          tube('emitter2', .02, .02, -.4, .06, M['glow'], 32), ring('emitring', .024, .003, (0, -.375, .06), M['dark'], maj=40),
          ext('stock', [(.14, .09), (.3, .085), (.31, .07), (.31, -.01), (.14, .02)], .05, M['metal'], .015),
          B('cell', (.04, .07, .09), (0, -.12, -.035), M['glow'], .01),
          B('cellcage', (.044, .074, .02), (0, -.12, -.082), M['dark'], .004)]
    for i in range(3):
        P.append(B('cellbar', (.046, .006, .09), (0, -.095 - i * .025, -.035), M['dark'], .001))
    P += e_screws(M, [(-.2, .04), (.1, .06), (-.02, .03)], .062)
    P += e_rail(M, .12, -.06, .1)
    sz = .14
    finish('gun_pulse', P, (0, -.43, .06), (0, -.24, .01), (0, .14, sz), optic=K.iron_rear(M, .1, sz, M['dark']) + K.iron_front(M, -.24, sz, dot=M['green']),
           rail=(0, .03, .1095))


def scout_rifle():
    bl.reset(); M = K.energy_mats(); P = []
    P += e_grip(M)
    P += [ext('receiver', [(.13, .02), (.13, .09), (-.29, .09), (-.3, .075), (-.3, .02)], .05, M['body'], .014,
              cuts=[cbox((.012, .06, .018), (RIGHT * .025, -.0, .07))]),
          ext('stock', [(.13, .08), (.34, .07), (.35, .055), (.35, -.04), (.33, -.05), (.18, -.0), (.13, .02)], .036, M['body'], .01,
              cuts=[cbox((.06, .09, .035), (0, .25, .02))]),
          B('cheek', (.04, .12, .03), (0, .2, .075), M['metal'], .008),
          ext('butt', [(.35, .06), (.365, .06), (.365, -.05), (.35, -.05)], .04, M['grip'], .005),
          tube('barrel', .012, .4, -.3, .055, M['dark'], 32)] + K.brake(-.68, .055, .019, .065, M['trim'], 3)
    P += [ext('mag', [(-.06, .02), (-.065, -.06), (-.14, -.06), (-.135, .02)], .03, M['metal'], .005),
          B('glow', (.002, .3, .01), (.026, -.1, .05), M['glow'], 0), B('glow2', (.002, .3, .01), (-.026, -.1, .05), M['glow'], 0),
          rod('bolt', (RIGHT * .02, .02, .07), (RIGHT * .055, .03, .06), .0045, M['trim']), ball('boltknob', .009, (RIGHT * .058, .032, .059), M['dark'])]
    P += e_screws(M, [(-.22, .04), (.08, .04)], .05)
    P += e_rail(M, .08, -.16, .09)
    P += K.sling_loop(.3, -.04, M['dark'])
    sz = .13
    finish('gun_scout', P, (0, -.74, .055), (0, -.32, .0), (0, .1, sz), optic=scope_tube(M, -.02, sz, .17, .019, .026), scoped=True,
           rail=(0, -.04, .0995))


def hand_cannon():
    bl.reset(); M = K.energy_mats(); P = []
    P += e_grip(M, ang=.38, h=.12)
    P += [ext('frame', [(.04, .015), (.045, .085), (.02, .098), (-.17, .098), (-.17, .02), (-.03, .015)], .04, M['body'], .008,
              cuts=[cbox((.06, .085, .062), (0, -.04, .058))])]
    cyl_cuts = [ccyl(.007, .09, (math.cos(i * math.pi / 3 + .52) * .038, -.04, .058 + math.sin(i * math.pi / 3 + .52) * .038), (R90, 0, 0), 16) for i in range(6)]
    P += [tube('cylinder', .038, .075, -.0025, .058, M['metal'], 48, cuts=cyl_cuts, bevel=.003),
          tube('cylaxis', .008, .09, .005, .058, M['dark'], 20)]
    P += [tube('barrel', .017, .2, -.08, .07, M['metal'], 40, hollow=.008),
          ext('shroud', [(-.08, .06), (-.08, .098), (-.29, .098), (-.3, .088), (-.3, .066), (-.08, .06)], .04, M['body'], .008,
              cuts=[cbox((.05, .016, .008), (0, -.12 - i * .04, .098)) for i in range(4)]),
          B('shroudglow', (.002, .16, .01), (.021, -.19, .082), M['glow'], 0),
          tube('ejector', .005, .19, -.085, .05, M['dark'], 16),
          ext('hammer', [(.03, .085), (.06, .11), (.07, .106), (.05, .082), (.04, .07)], .012, M['trim'], .002)]
    P += e_screws(M, [(.0, .03), (-.15, .08)], .04)
    sz = .112
    P += [B('rear_notchL', (.008, .012, .016), (.009, .03, sz - .004), M['dark'], .002),
          B('rear_notchR', (.008, .012, .016), (-.009, .03, sz - .004), M['dark'], .002),
          ball('rear_dotL', .0022, (.009, .023, sz), M['green'], seg=10, rings=6), ball('rear_dotR', .0022, (-.009, .023, sz), M['green'], seg=10, rings=6)]
    P += K.iron_front(M, -.28, sz, ears=False, dot=M['green'])
    finish('gun_handcannon', P, (0, -.31, .07), (0, -.02, -.02), (0, .1, sz))


def shotgun():
    bl.reset(); M = K.energy_mats(); P = []
    P += e_grip(M)
    P += [ext('receiver', [(.09, .008), (.09, .097), (-.18, .097), (-.19, .08), (-.19, .008)], .062, M['body'], .014,
              cuts=[cbox((.012, .08, .03), (RIGHT * .031, -.05, .07))]),
          ext('stock', [(.09, .09), (.32, .08), (.33, .065), (.33, -.03), (.3, -.04), (.16, .0), (.09, .02)], .05, M['metal'], .016),
          ext('butt', [(.33, .07), (.345, .07), (.345, -.04), (.33, -.04)], .054, M['grip'], .006)]
    for x in (-.017, .017):
        P.append(tube('barrel', .016, .38, -.16, .072, M['metal'], 40, x=x, hollow=.011))
    P += [ext('pump', [(-.27, .005), (-.27, .055), (-.43, .055), (-.43, .005)], .072, M['body'], .016,
              cuts=[cbox((.09, .006, .012), (0, -.3 - i * .03, .005)) for i in range(5)])]
    for i in range(5):
        P.append(B('pumprib', (.076, .008, .052), (0, -.29 - i * .03, .03), M['dark'], .002))
    P += [B('shells', (.07, .1, .02), (0, -.06, .105), M['trim'], .005),
          B('glow', (.002, .18, .015), (.032, -.05, .05), M['glow'], 0), B('glow2', (.002, .18, .015), (-.032, -.05, .05), M['glow'], 0),
          B('vrib', (.008, .36, .006), (0, -.36, .092), M['dark'], .001)]
    P += e_screws(M, [(-.1, .03), (.04, .07)], .062)
    sz = .1
    P += [B('ghost_base', (.03, .014, .014), (0, .05, sz - .016), M['dark'], .003),
          ring('ghost', .008, .0025, (0, .05, sz), M['dark'], maj=28, mn=8),
          ball('bead', .004, (0, -.54, sz), M['green'], seg=12, rings=8), B('beadpost', (.004, .006, .008), (0, -.54, sz - .007), M['dark'], 0)]
    finish('gun_shotgun', P, (0, -.56, .072), (0, -.35, -.005), (0, .14, sz))


def sniper():
    bl.reset(); M = K.energy_mats(); P = []
    P += e_grip(M)
    P += [ext('receiver', [(.15, .01), (.15, .09), (-.23, .09), (-.23, .01)], .052, M['metal'], .012,
              cuts=[cbox((.012, .07, .02), (RIGHT * .026, -.0, .07))]),
          ext('chassis', [(-.18, .005), (-.18, .055), (-.44, .055), (-.45, .045), (-.45, .005)], .06, M['body'], .012,
              cuts=[cbox((.08, .03, .012), (0, -.24 - i * .05, .03)) for i in range(4)]),
          B('chassisglow', (.002, .2, .012), (.031, -.29, .03), M['glow'], 0),
          ext('stock', [(.15, .08), (.42, .07), (.43, .06), (.43, -.03), (.3, -.03), (.2, .0), (.15, .01)], .046, M['body'], .015,
              cuts=[cbox((.06, .12, .025), (0, .29, .02))]),
          B('cheek', (.044, .12, .03), (0, .22, .085), M['metal'], .008),
          ext('butt', [(.43, .07), (.445, .07), (.445, -.04), (.43, -.04)], .05, M['grip'], .008),
          tube('barrel', .015, .58, -.4, .055, M['dark'], 40), tube('suppressor', .026, .16, -.86, .055, M['metal'], 48),
          ring('supring', .027, .003, (0, -.9, .055), M['trim'], maj=48), ring('supring2', .027, .003, (0, -.98, .055), M['trim'], maj=48),
          rod('bolt', (RIGHT * .02, .03, .075), (RIGHT * .06, .04, .065), .005, M['trim']), ball('boltknob', .012, (RIGHT * .068, .042, .062), M['dark']),
          ext('mag', [(-.05, .01), (-.05, -.06), (-.12, -.06), (-.12, .01)], .036, M['dark'], .005)]
    for s in (1, -1):
        P.append(rod('bipod', (s * .02, -.55, .02), (s * .04, -.53, -.1), .005, M['dark']))
        P.append(ball('bipodfoot', .008, (s * .04, -.53, -.1), M['grip']))
    P.append(B('bipodclamp', (.05, .03, .02), (0, -.55, .02), M['dark'], .003))
    P += e_screws(M, [(-.3, .03), (-.4, .03), (.05, .03)], .06)
    P += e_rail(M, .14, -.2, .09)
    sz = .14
    finish('gun_sniper', P, (0, -1.03, .055), (0, -.3, .0), (0, .2, sz), optic=scope_tube(M, .02, sz, .3, .024, .034), scoped=True,
           rail=(0, -.03, .0995))


def rocket():
    bl.reset(); M = K.energy_mats(); P = []
    P += e_grip(M)
    P += [tube('tube', .075, .92, .3, .13, M['body'], 48, hollow=.06),
          tube('bandF', .085, .06, -.45, .13, M['metal'], 48), tube('bandB', .085, .06, .33, .13, M['metal'], 48),
          tube('nozzle', .07, .06, .36, .13, M['dark'], 48, r2=.08, hollow=.055), tube('nozzleglow', .05, .01, .33, .13, M['glow'], 40),
          ext('grip2', [(-.26, .06), (-.26, -.01), (-.27, -.06), (-.31, -.06), (-.3, .06)], .03, M['grip'], .008),
          B('glowring', (.003, .5, .02), (.076, -.15, .13), M['glow'], 0), B('glowring2', (.003, .5, .02), (-.076, -.15, .13), M['glow'], 0),
          B('hazard', (.16, .08, .16), (0, -.36, .13), M['trim'], .02), B('mount', (.04, .3, .03), (0, -.08, .06), M['dark'], .004)]
    for i in range(6):
        a = i * math.pi / 3
        P.append(K.screw(math.cos(a) * .0865, -.45, .13 + math.sin(a) * .0865, M['trim'], .003, 1)[0])
    sz = .23
    P += [B('sightarm', (.012, .03, .05), (0, .0, .21), M['dark'], .003)]
    P += K.rail(M, .06, -.1, .205, .022, M['dark'])
    finish('gun_rocket', P, (0, -.64, .13), (0, -.28, -.02), (0, .1, sz), optic=red_dot(M, -.02, sz + .015), rail=(0, -.02, .2145))


def smg():
    bl.reset(); M = K.energy_mats(); P = []
    P += e_grip(M, ang=.22, h=.11)
    P += [ext('upper', [(.07, .044), (.07, .097), (-.19, .097), (-.19, .044)], .05, M['body'], .01,
              cuts=[cbox((.012, .05, .02), (RIGHT * .025, -.04, .072))]),
          ext('lower', [(.05, .05), (.05, .008), (-.11, .008), (-.11, .05)], .046, M['metal'], .008),
          ext('shroud', [(-.18, .04), (-.18, .092), (-.3, .092), (-.3, .04)], .056, M['metal'], .01,
              cuts=[cbox((.07, .016, .01), (0, -.2 - i * .025, .066)) for i in range(4)]),
          B('seam', (.002, .2, .01), (.026, -.08, .072), M['glow'], 0), B('seam2', (.002, .2, .01), (-.026, -.08, .072), M['glow'], 0),
          ext('mag', [(-.075, .02), (-.08, -.15), (-.125, -.15), (-.12, .02)], .03, M['dark'], .005),
          B('magglow', (.032, .01, .1), (0, -.08, -.05), M['glow'], 0),
          ext('vgrip', [(-.23, .04), (-.235, -.05), (-.27, -.055), (-.265, .04)], .026, M['grip'], .008),
          tube('stockbar', .006, .2, .27, .085, M['dark'], 16, x=.016), tube('stockbar2', .006, .2, .27, .03, M['dark'], 16, x=-.016),
          ext('stockpad', [(.26, .1), (.29, .1), (.29, .0), (.26, .0)], .04, M['grip'], .006),
          tube('barrel', .011, .06, -.3, .066, M['dark'], 32), tube('can', .019, .11, -.36, .066, M['metal'], 40),
          ring('canring', .0195, .002, (0, -.4, .066), M['trim'], maj=40),
          B('cocking', (.03, .012, .012), (0, .02, .1), M['trim'], .003)]
    P += e_screws(M, [(-.25, .05), (-.05, .03)], .056)
    P += e_rail(M, .06, -.28, .097, .022)
    sz = .135
    finish('gun_smg', P, (0, -.48, .066), (0, -.25, -.03), (0, .08, sz), optic=red_dot(M, -.04, sz), rail=(0, -.04, .1065))


def sidearm():
    bl.reset(); M = K.energy_mats(); P = []
    P += e_grip(M, ang=.3, h=.11)
    P += [ext('frame', [(.03, .045), (.03, .015), (-.16, .015), (-.16, .045)], .032, M['metal'], .006),
          ext('slide', [(.035, .052), (.035, .088), (-.165, .088), (-.17, .08), (-.17, .052)], .036, M['body'], .007,
              cuts=[cbox((.004, .0025, .03), (s * .018, .03 - i * .006, .07)) for i in range(5) for s in (1, -1)] +
                   [cbox((.02, .035, .02), (RIGHT * .009, -.04, .09))]),
          B('glow', (.002, .12, .008), (.0185, -.1, .068), M['glow'], 0), B('glow2', (.002, .12, .008), (-.0185, -.1, .068), M['glow'], 0),
          B('readout', (.02, .014, .012), (0, .035, .05), M['glow'], .002),
          tube('barrel', .009, .012, -.16, .07, M['dark'], 32, hollow=.005),
          B('railbox', (.028, .05, .014), (0, -.13, .01), M['dark'], .004)]
    P += e_screws(M, [(-.04, .03)], .032)
    sz = .1
    P += [B('rearL', (.008, .01, .014), (.008, .025, sz - .004), M['dark'], .002), B('rearR', (.008, .01, .014), (-.008, .025, sz - .004), M['dark'], .002),
          ball('rdotL', .002, (.008, .019, sz), M['green'], seg=10, rings=6), ball('rdotR', .002, (-.008, .019, sz), M['green'], seg=10, rings=6)]
    P += K.iron_front(M, -.155, sz, ears=False, dot=M['green'])
    finish('gun_sidearm', P, (0, -.2, .07), (0, -.02, -.02), (0, .09, sz), rail=(0, -.06, .088))


def heavy_mg():
    bl.reset(); M = K.energy_mats(); P = []
    P += e_grip(M, ang=.2, h=.12)
    P += [ext('housing', [(.1, .0), (.1, .12), (-.22, .12), (-.24, .1), (-.24, .0)], .1, M['body'], .02,
              cuts=[cbox((.014, .08, .03), (RIGHT * .05, -.06, .08))]),
          B('housingglow', (.002, .2, .02), (.051, -.08, .07), M['glow'], 0), B('housingglow2', (.002, .2, .02), (-.051, -.08, .07), M['glow'], 0),
          tube('motor', .05, .08, -.24, .07, M['metal'], 48),
          tube('frontring', .056, .03, -.52, .07, M['metal'], 48, hollow=.045), tube('midring', .05, .02, -.38, .07, M['dark'], 48, hollow=.04)]
    for i in range(6):
        a = i * math.pi / 3
        P.append(tube('rbarrel', .011, .36, -.28, .07 + math.sin(a) * .03, M['dark'], 20, x=math.cos(a) * .03, hollow=.006))
    P += [tube('spindle', .012, .3, -.26, .07, M['metal'], 24),
          cylx('drum', .09, .07, (.0, -.06, -.07), M['metal'], 64, .003), cylx('drumcap', .06, .074, (.0, -.06, -.07), M['trim'], 48),
          cylx('drumglow', .092, .01, (.0, -.06, -.07), M['glow'], 64),
          B('carry', (.016, .2, .016), (0, -.12, .17), M['dark'], .004), B('carryL', (.016, .016, .05), (0, -.03, .145), M['dark'], .003),
          B('carryF', (.016, .016, .05), (0, -.21, .145), M['dark'], .003),
          ext('stock', [(.1, .1), (.24, .095), (.24, .0), (.1, .02)], .06, M['metal'], .015),
          ext('butt', [(.24, .1), (.255, .1), (.255, -.005), (.24, -.005)], .064, M['grip'], .008),
          ext('fgrip', [(-.28, .0), (-.285, -.07), (-.325, -.075), (-.32, .0)], .03, M['grip'], .008)]
    for i in range(8):
        a = i * math.pi / 4
        P.append(K.screw(.035, -.06 + math.cos(a) * .075, -.07 + math.sin(a) * .075, M['dark'], .003, 1)[0])
    P += e_screws(M, [(-.15, .03), (.05, .03)], .1)
    sz = .21
    P += K.rail(M, .08, -.06, .17, .022, M['dark'])
    finish('gun_hmg', P, (0, -.66, .07), (0, -.3, -.04), (0, .1, sz), optic=red_dot(M, .0, sz), rail=(0, .01, .1795))


def energy_rifle():
    bl.reset(); M = K.energy_mats(); P = []
    P += e_grip(M, ang=.25, h=.12)
    P += [tube('shellrear', .06, .2, .12, .07, M['body'], 48, r2=.045),
          tube('shellfront', .045, .26, -.08, .07, M['body'], 48, r2=.028),
          tube('core', .02, .38, .19, .07, M['glow'], 24)]
    for i, (y, r) in enumerate(((-.06, .07), (-.14, .062), (-.22, .054), (-.3, .046))):
        P.append(ring('ring', r, .007, (0, y, .07), M['trim'] if i % 2 else M['metal'], maj=48, mn=10))
        for k in range(4):
            a = k * math.pi / 2 + .4
            P.append(B('ringstrut', (.006, .006, r - .03), (math.cos(a) * (r + .02) / 2, y, .07 + math.sin(a) * (r + .02) / 2), M['dark'], .001, rot=(0, -a + R90, 0)))
    P += [tube('emitter', .03, .04, -.36, .07, M['metal'], 40, r2=.02, hollow=.012),
          tube('emitglow', .014, .02, -.39, .07, M['glow'], 24),
          ext('fin', [(.05, .1), (.05, .12), (-.3, .14), (-.3, .1)], .006, M['body'], .002),
          ext('stock', [(.12, .09), (.28, .08), (.29, .07), (.29, .0), (.12, .02)], .044, M['metal'], .015),
          ext('butt', [(.29, .08), (.305, .08), (.305, -.002), (.29, -.002)], .048, M['grip'], .008),
          B('cell', (.05, .06, .05), (0, -.06, -.01), M['glow'], .01),
          ext('fgrip', [(-.2, .03), (-.205, -.04), (-.24, -.045), (-.235, .03)], .03, M['grip'], .008)]
    sz = .165
    P += [B('sightrail', (.02, .1, .02), (0, .0, .13), M['dark'], .004)]
    finish('gun_energy', P, (0, -.42, .07), (0, -.22, -.03), (0, .09, sz), optic=red_dot(M, -.01, sz), rail=(0, -.01, .14))


# ================================================================== kinetic line
def curved_mag(name, y_rear, z_top, R, depth, theta, w, m, ribs=2, rib_m=None):
    """Curved box magazine (curves forward as it drops). Returns body + ribs + floorplate."""
    cy, cz = y_rear - R, z_top
    n = 14
    rear = [(cy + R * math.cos(t), cz - R * math.sin(t)) for t in np.linspace(0, theta, n)]
    front = [(cy + (R - depth) * math.cos(t), cz - (R - depth) * math.sin(t)) for t in np.linspace(theta, 0, n)]
    P = [ext(name, rear + front, w, m, .0025)]
    for k in range(ribs):
        r0 = R - depth * (.3 + .4 * k / max(1, ribs - 1)) + .003; r1 = r0 - .006
        a = [(cy + r0 * math.cos(t), cz - r0 * math.sin(t)) for t in np.linspace(.06, theta - .04, 10)]
        b = [(cy + r1 * math.cos(t), cz - r1 * math.sin(t)) for t in np.linspace(theta - .04, .06, 10)]
        P.append(ext('magrib', a + b, w + .003, rib_m or m, .0012, 2))
    t = theta; ca, sa = math.cos(t), math.sin(t)
    mid = (cy + (R - depth / 2) * ca, cz - (R - depth / 2) * sa)
    P.append(B('floorplate', (w + .006, depth + .012, .01), (0, mid[0] + sa * .003, mid[1] - ca * .003), rib_m or m, .003, rot=(-t, 0, 0)))
    return P


def assault_rifle():
    """Stamped-receiver assault rifle: walnut furniture, slant brake, curved magazine, side-swing safety."""
    bl.reset(); M = K.kinetic_mats(); S, PK, W, PO, BR = M['steel'], M['park'], M['wood'], M['poly'], M['brass']
    zb = .06; P = []
    rc = [(.165, .028), (.165, .084), (-.215, .084), (-.215, .024), (-.165, .024), (-.165, .002), (-.08, .002), (-.08, .024), (.02, .024), (.02, .028)]
    P.append(ext('receiver', rc, .046, S, .0018, cuts=[cbox((.012, .11, .02), (RIGHT * .023, -.07, .07)), cbox((.02, .004, .02), (RIGHT * .023, -.135, .062))]))
    # stamped magazine dimples, trunnion rivets, pins
    for s in (1, -1):
        P.append(B('dimple', (.002, .045, .012), (s * .0232, -.12, .012), S, .001))
        for y, z in ((-.2, .035), (-.2, .07), (-.185, .035), (.15, .04), (.15, .07), (-.06, .036)):
            P.append(K.rivet(s * .023, y, z, S, .0026, s))
    P += K.pins(.047, [(.1, .04), (.06, .04), (-.03, .04)], S, .0024)
    # bolt carrier seen through the ejection slot + charging handle
    P += [B('carrier', (.02, .14, .018), (RIGHT * .012, -.06, .072), PK, .002),
          rod('charging', (RIGHT * .02, -.125, .074), (RIGHT * .047, -.128, .074), .0045, S), ball('chknob', .0065, (RIGHT * .049, -.128, .074), S)]
    # dust cover with stamped ribs and its release button
    P.append(ext('dustcover', [(.17, .084), (.172, .094), (.156, .112), (-.172, .112), (-.19, .102), (-.196, .084)], .044, S, .006, 4))
    for y in (.11, .075, .04):
        P.append(B('dcrib', (.0455, .006, .014), (0, y, .104), S, .002))
    P.append(cylz('dcbutton', .005, .012, (0, .172, .09), S, 20))
    # side safety lever (right side) with its finger tab
    P += [ext('selector', [(.155, .074), (.158, .08), (-.035, .077), (-.04, .07), (.0, .068)], .0025, S, .0008, 2, x=RIGHT * .0245),
          B('seltab', (.004, .012, .016), (RIGHT * .026, -.032, .064), S, .001)]
    # rear sight block, tangent leaf and notch
    P += [ext('rsblock', [(-.195, .084), (-.195, .1), (-.212, .113), (-.265, .113), (-.265, .084)], .03, S, .002),
          B('leaf', (.022, .07, .004), (0, -.238, .117), S, .001, rot=(.04, 0, 0)), B('slider', (.028, .012, .008), (0, -.232, .119), S, .0015),
          B('notchL', (.006, .006, .009), (.006, -.268, .1185), S, .0008), B('notchR', (.006, .006, .009), (-.006, -.268, .1185), S, .0008)]
    # walnut handguards with steel retainers, gas tube
    P += [ext('hg_lower', [(-.265, .028), (-.265, .078), (-.42, .078), (-.432, .068), (-.432, .036), (-.42, .026)], .058, W, .012, 4),
          ext('hg_upper', [(-.268, .084), (-.268, .1), (-.276, .108), (-.392, .108), (-.4, .1), (-.4, .084)], .04, W, .01, 4),
          ext('retainerR', [(-.258, .022), (-.258, .086), (-.27, .086), (-.27, .022)], .062, S, .002),
          ext('retainerF', [(-.428, .026), (-.428, .08), (-.44, .08), (-.44, .026)], .06, S, .002),
          tube('gastube', .0105, .05, -.395, .096, S, 32),
          ext('gasblock', [(-.44, .045), (-.44, .108), (-.458, .108), (-.475, .094), (-.475, .045)], .03, S, .003)]
    P += K.screw(.03, -.435, .05, S, .0028, 1)
    # barrel, front sight base with hooded post, slant brake, cleaning rod, bayonet lug
    P += [tube('barrel', .0095, .44, -.215, zb, S, 32),
          ext('fsb', [(-.588, .042), (-.588, .075), (-.597, .102), (-.618, .102), (-.626, .075), (-.626, .042)], .026, S, .002),
          B('postL', (.003, .01, .03), (.011, -.607, .108), S, .001), B('postR', (.003, .01, .03), (-.011, -.607, .108), S, .001),
          B('post', (.0035, .004, .018), (0, -.607, .111), S, .0006),
          tube('brake', .0135, .048, -.64, zb, S, 40, hollow=.0055, cuts=[cbox((.04, .03, .03), (0, -.69, zb + .02), rot=(.5, 0, 0)),
                                                                         cbox((.006, .006, .03), (0, -.655, zb + .012))]),
          tube('crush', .0115, .012, -.628, zb, S, 32),
          tube('cleanrod', .0032, .36, -.265, .04, S, 16), ball('rodtip', .0045, (0, -.626, .04), S),
          B('baylug', (.01, .018, .012), (0, -.6, .03), S, .002)]
    # pistol grip, trigger group, magazine catch
    P.append(K.grip_profile('grip', PO, ang=.32, h=.115, w=.031, z=.024, swell=.005))
    P += K.trigger_group(M, S, S, y=-.04, z=.024, L=.056, drop=.048)
    P += [B('magcatch', (.012, .012, .018), (0, -.083, .006), S, .002)]
    P += curved_mag('mag', -.085, .02, .36, .064, .6, .03, PO, 2)
    # walnut stock with steel butt plate, tang, sling swivel
    P += [ext('stock', [(.165, .084), (.21, .08), (.43, .068), (.445, .06), (.445, -.075), (.43, -.078), (.3, -.03), (.22, .002), (.165, .03)], .042, W, .011, 4),
          ext('buttplate', [(.444, .062), (.456, .058), (.456, -.076), (.444, -.08)], .044, S, .003),
          B('tang', (.03, .07, .006), (0, .2, .084), S, .002),
          B('trapdoor', (.0015, .03, .02), (.0218, .43, .0), S, .0006)]
    P += K.screw(0, .448, .03, S, .003, 1) + K.sling_loop(.36, -.05, S) + K.sling_loop(-.42, .02, S, x=.031)
    # optic rail on the dust cover (modern side-rail style mount moved on top)
    P += K.rail(M, .12, -.1, .112, .022, PK)
    sz = .1195
    finish('gun_rifle', P, (0, -.69, zb), (0, -.345, .012), (0, -.19, sz), rail=(0, .01, .1215))


def carbine():
    """Flat-top carbine: anodized receivers, free-float slotted handguard, collapsible stock, flip-up irons."""
    bl.reset(); M = K.kinetic_mats(); S, PK, PO, RB = M['steel'], M['park'], M['poly'], M['rubber']
    zb = .066; P = []
    P.append(ext('lower', [(.1, .046), (.1, .024), (.07, .016), (.03, .016), (.03, .02), (-.05, .02), (-.05, -.022), (-.118, -.028),
                           (-.122, .0), (-.132, .02), (-.132, .046)], .034, PK, .002,
                 cuts=[cbox((.026, .06, .06), (0, -.085, .0))]))
    P.append(ext('magwell', [(-.046, -.006), (-.046, -.03), (-.124, -.032), (-.124, -.006)], .038, PK, .002, cuts=[cbox((.026, .07, .05), (0, -.085, -.02))]))
    P.append(ext('upper', [(.1, .046), (.1, .09), (-.134, .09), (-.134, .046)], .033, PK, .002,
                 cuts=[cbox((.01, .05, .016), (RIGHT * .017, -.03, .068))]))
    P += [B('boltface', (.02, .05, .014), (RIGHT * .01, -.03, .068), S, .002),
          B('portdoor', (.0015, .052, .018), (RIGHT * .0182, -.03, .053), PK, .0005),
          tube('fwdassist', .0075, .036, .09, .074, PK, 24, x=RIGHT * .02), cylz('fabtn', .0085, .006, (RIGHT * .02, .093, .074), PK, 24),
          B('deflector', (.008, .016, .02), (RIGHT * .019, .045, .066), PK, .003),
          B('chandle', (.026, .028, .008), (0, .112, .086), PK, .002), B('chlatch', (.012, .012, .008), (.018, .106, .086), PK, .002)]
    # buffer tube, castle nut, collapsible stock and butt pad
    P += [tube('buffer', .0155, .2, .3, .065, PK, 32), tube('castlenut', .019, .012, .112, .065, S, 12),
          ext('stock', [(.2, .086), (.33, .086), (.345, .08), (.35, .04), (.35, -.03), (.335, -.042), (.3, -.012), (.24, .035), (.2, .046)], .036, PO, .006,
              cuts=[cbox((.04, .05, .02), (0, .27, .0))]),
          ext('buttpad', [(.35, .086), (.362, .086), (.364, -.042), (.35, -.042)], .04, RB, .004),
          B('adjlever', (.012, .04, .008), (0, .26, .043), PK, .002)]
    P += K.sling_loop(.31, .05, S, x=.02)
    # grip, trigger, controls, pins
    P.append(K.grip_profile('grip', PO, ang=.33, h=.11, w=.03, z=.016, swell=.004))
    P += K.trigger_group(M, PK, S, y=-.005, z=.016, L=.058, drop=.046)
    P += K.pins(.035, [(.08, .035), (-.115, .035)], S, .0025)
    P += [cylx('selector', .006, .004, (.0185, .05, .032), S, 20), B('selarm', (.003, .022, .006), (.021, .044, .034), S, .001, rot=(.4, 0, 0)),
          cylx('magrelease', .0045, .006, (RIGHT * .018, -.045, .032), S, 20),
          B('boltcatch', (.003, .02, .01), (.0175, -.04, .04), S, .001)]
    # free-float handguard with M-LOK style slots, barrel nut, top rail
    slots = []
    for i in range(5):
        y = -.17 - i * .05
        slots += [cbox((.08, .032, .007), (0, y, .055)), cbox((.007, .032, .08), (0, y, .04))]
    P += [tube('handguard', .029, .3, -.132, .066, PK, 8, hollow=.023, cuts=slots, bevel=.003),
          tube('barrelnut', .022, .014, -.13, .066, S, 32)]
    P += K.rail(M, .1, -.43, .09, .022, PK)
    # barrel, gas block, flash hider
    P += [tube('barrel', .0085, .1, -.43, zb, S, 32), tube('gasblock', .012, .02, -.36, zb, S, 24)]
    P += K.birdcage(-.53, zb, .011, .05, S, 6) + [tube('barrel_in', .0085, .3, -.13, zb, S, 24)]
    # magazine
    P += [ext('mag', [(-.058, .012), (-.06, -.08), (-.074, -.17), (-.088, -.205), (-.152, -.198), (-.136, -.162), (-.122, -.08), (-.118, .012)], .022, PK, .002),
          B('magfloor', (.026, .068, .01), (0, -.121, -.205), PO, .003, rot=(-.08, 0, 0))]
    for k in range(3):
        P.append(B('magrib', (.0235, .004, .17), (0, -.075 - k * .022, -.08), PK, .001, rot=(-.12, 0, 0)))
    sz = .1335
    optic = [B('buis_base', (.022, .03, .012), (0, .07, .1055), PK, .002)] + K.iron_rear(M, .07, sz, PK) + \
            [B('fbuis_base', (.022, .03, .012), (0, -.41, .1055), PK, .002), B('fbuis_arm', (.008, .012, .022), (0, -.41, .12), PK, .002)] + \
            K.iron_front(M, -.41, sz, ears=True, m=PK)
    finish('gun_carbine', P, (0, -.585, zb), (0, -.3, .028), (0, .1, sz), optic=optic, rail=(0, -.02, .0995))


def bolt_rifle():
    """Big-bore bolt-action precision rifle: thumbhole stock, fluted heavy barrel, large brake, folded bipod."""
    bl.reset(); M = K.kinetic_mats(); S, PK, OD, RB = M['steel'], M['park'], M['odg'], M['rubber']
    zb = .077; P = []
    hole = [ccyl(.028, .1, (0, .095, .018), (0, R90, 0), 32), ccyl(.028, .1, (0, .14, .018), (0, R90, 0), 32), cbox((.1, .045, .056), (0, .1175, .018))]
    P.append(ext('stock', [(-.53, .03), (-.53, .07), (-.12, .072), (-.12, .058), (.11, .058), (.14, .078), (.2, .1), (.455, .1), (.47, .09),
                           (.475, -.095), (.455, -.105), (.32, -.105), (.19, -.058), (.105, -.03), (.06, -.123), (.0, -.128),
                           (-.024, -.02), (-.035, .02), (-.08, .02), (-.08, .0), (-.16, .0), (-.16, .02), (-.2, .028)], .052, OD, .012, 4, cuts=hole))
    for y in (-.25, -.31, -.37, -.43):
        P.append(B('forendslot', (.0535, .03, .008), (0, y, .04), PK, .003))
    # action: round receiver with ejection port, bolt with shroud and handle, rail
    P += [tube('receiver', .021, .27, .13, zb, S, 48, cuts=[cbox((.02, .07, .02), (RIGHT * .02, -.0, zb + .008))]),
          tube('bolt', .0125, .1, .05, zb, PK, 32), tube('shroud', .016, .035, .16, zb, S, 32),
          ring('shroudring', .016, .0025, (0, .126, zb), S, maj=40),
          rod('boltarm', (RIGHT * .012, .11, zb + .002), (RIGHT * .06, .118, zb - .028), .0045, S),
          ball('boltknob', .0115, (RIGHT * .064, .12, zb - .032), PK, scale=(1, 1, 1.1)),
          B('recoillug', (.03, .012, .03), (0, -.13, .055), S, .002)]
    P += K.screw(0, -.06, .058, S, .003, 1) + K.screw(0, .1, .058, S, .003, 1)
    P += K.rail(M, .12, -.13, .097, .022, PK)
    # fluted heavy barrel and big brake
    fl = []
    for k in range(6):
        a = k * math.pi / 3 + math.pi / 6
        fl.append(cbox((.006, .36, .006), (math.cos(a) * .0165, -.45, zb + math.sin(a) * .0165), rot=(0, -a, 0)))
    P += [tube('barrel', .017, .64, -.14, zb, S, 48, r2=.0135, cuts=fl), tube('brake', .021, .085, -.775, zb, S, 48, hollow=.008,
          cuts=[cbox((.06, .012, .028), (0, -.79 - i * .022, zb)) for i in range(3)] + [cbox((.012, .05, .03), (0, -.815, zb + .02))]),
          ring('brakering', .021, .0025, (0, -.778, zb), S, maj=48)]
    # bottom metal: trigger guard, magazine, release
    P += K.trigger_group(M, S, S, y=-.034, z=.02, L=.06, drop=.048)
    P += [ext('mag', [(-.085, .02), (-.085, -.035), (-.093, -.045), (-.152, -.045), (-.158, -.035), (-.158, .02)], .034, M['poly'], .003),
          B('magrel', (.012, .01, .012), (0, -.08, .0), S, .002)]
    # folded bipod, cheek riser knob, butt pad, monopod, sling studs
    P += [B('bipodclamp', (.044, .03, .02), (0, -.5, .02), PK, .003)]
    for s in (1, -1):
        P += [tube('bipodleg', .0055, .2, -.49, .008, PK, 20, x=s * .013), tube('bipodext', .0042, .06, -.68, .008, S, 20, x=s * .013),
              ball('bipodfoot', .008, (s * .013, -.745, .008), RB)]
    P += [cylx('cheekknob', .011, .014, (.032, .3, .075), PK, 24), B('cheekgap', (.054, .2, .003), (0, .32, .086), PK, .001),
          ext('buttpad', [(.475, .096), (.49, .096), (.492, -.1), (.475, -.106)], .054, RB, .004),
          cylz('monopod', .006, .05, (0, .42, -.12), PK, 20), ball('monofoot', .009, (0, .42, -.146), RB)]
    P += K.sling_loop(.4, -.11, S) + K.sling_loop(-.5, .015, S)
    finish('gun_bolt', P, (0, -.865, zb), (0, -.36, .02), (0, .2, .14), rail=(0, -.005, .1065))


def service_pistol():
    """Polymer-frame service pistol: serrated steel slide, accessory rail, three-dot sights."""
    bl.reset(); M = K.kinetic_mats(); S, PK, PO, PA = M['steel'], M['park'], M['poly'], M['paint']
    P = []
    P.append(ext('frame', [(.032, .05), (.032, .03), (.0, .022), (-.1, .022), (-.1, .03), (-.155, .03), (-.155, .05)], .03, PO, .003,
                 cuts=[cbox((.04, .004, .004), (0, -.11 - i * .012, .03)) for i in range(3)]))
    P.append(K.grip_profile('grip', PO, ang=.3, h=.1, w=.03, z=.022, swell=.004))
    P += K.trigger_group(M, PO, PK, y=-.032, z=.022, L=.06, drop=.044)
    slide_cuts = [cbox((.004, .0024, .026), (s * .0155, .032 - i * .0055, .066), rot=(.18, 0, 0)) for i in range(7) for s in (1, -1)]
    slide_cuts += [cbox((.004, .0024, .02), (s * .0155, -.12 - i * .0055, .068), rot=(.18, 0, 0)) for i in range(4) for s in (1, -1)]
    slide_cuts += [cbox((.016, .034, .02), (RIGHT * .008, -.03, .082))]
    P.append(ext('slide', [(.04, .048), (.04, .074), (.034, .078), (-.148, .078), (-.158, .07), (-.158, .048)], .029, S, .0025, cuts=slide_cuts))
    P += [B('hood', (.018, .032, .014), (RIGHT * .002, -.03, .072), PK, .002),
          tube('crown', .0068, .006, -.153, .062, PK, 32, hollow=.0045), tube('guiderod', .004, .008, -.152, .044, PK, 20),
          ext('slidestop', [(-.005, .048), (-.058, .046), (-.064, .039), (-.01, .041)], .0026, S, .0006, 2, x=.0158),
          cylx('stoppin', .003, .033, (0, -.01, .042), S, 16), B('takedown', (.003, .012, .006), (.0155, -.085, .042), S, .001),
          cylx('magrelease', .004, .006, (.015, -.006, .016), PO, 20), B('extractor', (.0015, .03, .004), (RIGHT * .0148, -.02, .068), PK, .0005)]
    # sights: notch rear with two white dots, post front with one
    sz = .0835
    P += [B('rear_base', (.026, .01, .006), (0, .028, .081), S, .001),
          B('rearL', (.0085, .009, .008), (.0078, .028, sz - .002), S, .0008), B('rearR', (.0085, .009, .008), (-.0078, .028, sz - .002), S, .0008),
          cylx('rdotL', .0016, .001, (.0078, .0235, sz - .001), PA, 12) if False else ball('rdotL', .0017, (.0078, .0234, sz - .0015), PA, scale=(1, .4, 1), seg=12, rings=8),
          ball('rdotR', .0017, (-.0078, .0234, sz - .0015), PA, scale=(1, .4, 1), seg=12, rings=8),
          B('frontpost', (.0035, .006, .0075), (0, -.146, sz - .0035), S, .0008),
          ball('fdot', .0016, (0, -.1425, sz - .0012), PA, scale=(1, .4, 1), seg=12, rings=8),
          B('magbase', (.033, .046, .009), (0, .037, -.084), PO, .003, rot=(.3, 0, 0))]
    finish('gun_pistol', P, (0, -.165, .062), (0, -.02, -.035), (0, .07, sz), rail=(0, -.05, .078))


def pump_shotgun():
    """Pump-action shotgun: walnut stock and ribbed forend, vent rib with bead, side saddle with shells."""
    bl.reset(); M = K.kinetic_mats(); S, PK, W, RB, BR = M['steel'], M['park'], M['wood'], M['rubber'], M['brass']
    shell = bl.mat('gun_shell', '#8c1a1a', 0, .55)
    zb = .08; P = []
    P.append(ext('receiver', [(.09, .03), (.09, .1), (-.16, .1), (-.168, .09), (-.168, .03)], .042, PK, .003,
                 cuts=[cbox((.01, .075, .03), (RIGHT * .021, -.05, .075)), cbox((.03, .08, .012), (0, -.07, .03))]))
    P += [B('topgroove', (.012, .23, .003), (0, -.03, .1), S, .0008),
          tube('barrel', .0115, .56, -.16, zb, S, 48, hollow=.0095), B('ventrib', (.008, .55, .003), (0, -.44, .0955), S, .0008),
          tube('magtube', .0125, .5, -.16, .046, S, 40), tube('magcap', .0145, .035, -.655, .046, S, 40),
          ring('capring', .0145, .0015, (0, -.665, .046), S, maj=40), ring('capring2', .0145, .0015, (0, -.675, .046), S, maj=40),
          ext('clamp', [(-.6, .035), (-.6, .092), (-.618, .092), (-.618, .035)], .03, S, .003)]
    for i in range(10):
        P.append(B('ribpost', (.004, .005, .006), (0, -.19 - i * .05, .092), S, .0006))
    grooves = [cbox((.07, .0045, .01), (0, -.29 - i * .018, .028)) for i in range(9)] + [cbox((.0045, .0045, .04), (s * .028, -.29 - i * .018, .052)) for i in range(9) for s in (1, -1)]
    P += [ext('forend', [(-.27, .026), (-.27, .066), (-.455, .066), (-.455, .026)], .054, W, .016, 4, cuts=grooves)]
    for s in (1, -1):
        P.append(B('actionbar', (.003, .13, .006), (s * .0165, -.205, .05), S, .0008))
    P += [ext('stock', [(.09, .098), (.2, .088), (.42, .072), (.43, .064), (.43, -.088), (.415, -.094), (.24, -.06), (.1, -.065),
                        (.065, -.105), (.025, -.11), (.0, -.06), (.0, .0), (.03, .03), (.09, .03)], .04, W, .011, 4),
          ext('buttpad', [(.43, .066), (.445, .066), (.447, -.09), (.43, -.09)], .044, RB, .004),
          B('gripcap', (.034, .04, .006), (0, .045, -.11), PK, .002, rot=(-.15, 0, 0))]
    P += K.trigger_group(M, PK, S, y=-.03, z=.03, L=.07, drop=.05)
    P += [cylz('safety', .0045, .008, (0, .07, .101), S, 20), B('slidelever', (.003, .016, .008), (.006, -.075, .024), S, .001)]
    P += K.screw(.0212, -.12, .04, S, .0028, 1) + K.screw(-.0212, -.12, .04, S, .0028, -1)
    P += K.sling_loop(.37, -.08, S) + K.sling_loop(-.64, .03, S)
    # side saddle with four shells (left side)
    P.append(B('saddle', (.004, .08, .045), (.023, -.06, .066), M['poly'], .002))
    for i in range(4):
        y = -.03 - i * .02
        P += [cylz('shell', .0092, .045, (.034, y, .07), shell, 24), cylz('shellbase', .0098, .012, (.034, y, .043), BR, 24)]
    sz = .1
    P += [ball('bead', .0028, (0, -.71, .0985), BR, seg=14, rings=10), ball('midbead', .0018, (0, -.43, .0975), M['paint'], seg=10, rings=6)]
    finish('gun_pump', P, (0, -.72, zb), (0, -.36, .012), (0, .07, sz), rail=None)


def compact_smg():
    """Compact SMG: steel upper, polymer lower and vented handguard, side-folding wire stock, straight magazine."""
    bl.reset(); M = K.kinetic_mats(); S, PK, PO, RB = M['steel'], M['park'], M['poly'], M['rubber']
    zb = .068; P = []
    P += [ext('upper', [(.075, .05), (.075, .092), (-.17, .092), (-.17, .05)], .036, S, .003, cuts=[cbox((.01, .045, .018), (RIGHT * .018, -.04, .07))]),
          B('boltface', (.02, .045, .014), (RIGHT * .01, -.04, .07), PK, .002),
          ext('lower', [(.075, .05), (.075, .026), (.03, .022), (-.04, .022), (-.04, -.01), (-.095, -.012), (-.095, .022), (-.17, .026), (-.17, .05)], .034, PO, .003),
          ext('handguard', [(-.17, .028), (-.17, .092), (-.315, .092), (-.325, .08), (-.325, .036), (-.315, .028)], .042, PO, .008,
              cuts=[cbox((.06, .02, .008), (0, -.2 - i * .03, .062)) for i in range(4)]),
          tube('barrel', .0085, .04, -.325, zb, S, 32)] + K.brake(-.36, zb, .0125, .05, S, 3)
    P += [tube('chtube', .0075, .17, -.15, .102, S, 24, x=.0), B('chhandle', (.004, .012, .012), (.013, -.27, .102), S, .001)]
    P += K.rail(M, .07, -.16, .092, .02, PK)
    P += [B('hinge', (.03, .025, .05), (0, .088, .066), PK, .003),
          tube('stockrod', .0045, .2, .3, .085, S, 20, x=.013), tube('stockrod2', .0045, .2, .3, .085, S, 20, x=-.013),
          tube('stockrod3', .0045, .19, .29, .035, S, 20),
          ext('buttpad', [(.29, .1), (.315, .1), (.315, .02), (.29, .02)], .042, RB, .005)]
    P.append(K.grip_profile('grip', PO, ang=.25, h=.108, w=.03, z=.022, swell=.004))
    P += K.trigger_group(M, PO, S, y=-.0, z=.022, L=.042, drop=.044)
    P += [ext('mag', [(-.047, .018), (-.049, -.17), (-.091, -.17), (-.089, .018)], .024, PO, .003),
          B('magfloor', (.028, .048, .01), (0, -.07, -.172), PO, .003)]
    for k in range(4):
        P.append(B('magrib', (.0255, .036, .004), (0, -.07, -.03 - k * .035), PO, .0012))
    P += [cylz('vgrip', .014, .07, (0, -.255, -.008), RB, 32), cylz('vgripcap', .016, .008, (0, -.255, -.045), PO, 32)]
    P += K.pins(.035, [(.05, .035), (-.15, .035)], S, .002) + [cylx('selector', .0055, .004, (.018, .04, .036), S, 20)]
    finish('gun_ksmg', P, (0, -.415, zb), (0, -.255, -.02), (0, .08, .125), rail=(0, -.04, .1015))


def battle_rifle():
    """Battle rifle (designated marksman): walnut one-piece stock, steel receiver and op-rod, long box magazine."""
    bl.reset(); M = K.kinetic_mats(); S, PK, W, BR = M['steel'], M['park'], M['wood'], M['brass']
    zb = .072; P = []
    P.append(ext('stock', [(-.46, .03), (-.46, .07), (-.12, .07), (-.12, .06), (.1, .06), (.13, .078), (.45, .072), (.462, .064), (.462, -.088),
                           (.445, -.094), (.25, -.052), (.11, -.068), (.07, -.112), (.03, -.118), (.0, -.065), (-.005, .0), (-.01, .03),
                           (-.055, .03), (-.055, .02), (-.135, .02), (-.135, .03)], .044, W, .011, 4))
    P += [ext('receiver', [(.11, .058), (.11, .1), (-.15, .1), (-.15, .058)], .036, S, .002,
              cuts=[cbox((.01, .07, .02), (RIGHT * .018, -.03, .085))]),
          B('boltface', (.02, .07, .016), (RIGHT * .01, -.03, .085), PK, .002),
          B('oprod', (.006, .3, .012), (RIGHT * .021, -.19, .072), S, .002), B('ophandle', (.018, .014, .012), (RIGHT * .03, -.04, .08), S, .002),
          ext('hg_upper', [(-.15, .072), (-.15, .094), (-.36, .094), (-.36, .072)], .032, W, .008, 4),
          tube('gascyl', .0105, .1, -.36, .045, S, 32), ext('frontband', [(-.355, .03), (-.355, .09), (-.37, .09), (-.37, .03)], .046, S, .002),
          tube('barrel', .0105, .54, -.15, zb, S, 32)]
    P += K.birdcage(-.69, zb, .012, .06, S, 6)
    P += [B('fsb', (.014, .016, .03), (0, -.675, zb + .02), S, .002)] + K.iron_front(M, -.675, .125, ears=True, m=S)
    P += K.trigger_group(M, S, S, y=-.006, z=.03, L=.06, drop=.05)
    P += [ext('mag', [(-.058, .03), (-.062, -.12), (-.132, -.13), (-.132, .03)], .028, S, .002),
          B('magfloor', (.032, .076, .008), (0, -.097, -.13), S, .002, rot=(-.07, 0, 0))]
    for k in range(3):
        P.append(B('magrib', (.0295, .06, .004), (0, -.096, -.01 - k * .035), S, .0012))
    P += [ext('buttplate', [(.461, .066), (.472, .066), (.474, -.09), (.461, -.09)], .046, S, .003),
          B('trapdoor', (.0015, .03, .02), (.0228, .43, .0), S, .0006)]
    P += K.screw(.022, .2, .02, S, .003, 1) + K.screw(-.022, .2, .02, S, .003, -1) + K.sling_loop(.38, -.07, S) + K.sling_loop(-.4, .03, S)
    P += K.iron_rear(M, .085, .125, S)
    P += K.rail(M, .095, -.12, .1, .022, PK)
    finish('gun_dmr', P, (0, -.755, zb), (0, -.32, .022), (0, .11, .125), rail=(0, -.01, .1095))


def revolver():
    """Double-action revolver: fluted six-shot cylinder, vent-rib barrel with full underlug, walnut grips, spur hammer."""
    bl.reset(); M = K.kinetic_mats(); S, PK, W, BR, OR = M['steel'], M['park'], M['wood'], M['brass'], M['orange']
    zc = .062; zb = zc + .013; P = []
    P.append(ext('frame', [(.042, .032), (.046, .088), (.028, .1), (-.036, .1), (-.04, .092), (-.062, .092), (-.062, .04), (-.04, .03),
                           (-.02, .02), (.0, .016), (.036, .016)], .036, S, .003,
                 cuts=[cbox((.05, .064, .052), (0, -.0045, zc))]))
    cut = []
    for i in range(6):
        a = i * math.pi / 3 + math.pi / 6
        cut.append(ccyl(.0055, .045, (math.cos(a) * .0215, -.004, zc + math.sin(a) * .0215), (R90, 0, 0), 16))
        b = i * math.pi / 3 + math.pi / 2
        cut.append(ccyl(.0045, .01, (math.cos(b) * .013, -.034, zc + math.sin(b) * .013), (R90, 0, 0), 16))
    P += [tube('cylinder', .0215, .058, .0265, zc, S, 64, cuts=cut, bevel=.002), tube('ratchet', .008, .006, .031, zc, S, 6)]
    P += [tube('barrel', .0085, .12, -.06, zb, S, 40, hollow=.0048),
          ext('underlug', [(-.06, .052), (-.06, .088), (-.178, .088), (-.178, .056), (-.12, .046), (-.075, .048)], .02, S, .003),
          ext('ventrib', [(-.06, .088), (-.06, .094), (-.178, .094), (-.178, .088)], .008, S, .001,
              cuts=[cbox((.02, .01, .004), (0, -.08 - i * .02, .093)) for i in range(5)]),
          tube('ejrod', .0034, .01, -.17, .046, S, 16),
          ext('hammer', [(.03, .086), (.05, .108), (.066, .112), (.068, .104), (.05, .086), (.044, .07)], .008, S, .0012, 2),
          B('latch', (.004, .014, .008), (.019, .034, .075), S, .001)]
    P += K.trigger_group(M, S, S, y=-.008, z=.02, L=.05, drop=.045)
    P.append(K.grip_profile('grip', W, ang=.42, h=.105, w=.036, y=.024, z=.02, swell=.004))
    for s in (1, -1):
        P.append(ring('medallion', .0055, .0012, (s * .018, .047, -.035), BR, axis='x', maj=24, mn=6))
    P += K.screw(.018, .0, .04, S, .0028, 1) + K.screw(.018, -.04, .085, S, .0026, 1) + K.screw(.018, .03, .05, S, .0026, 1)
    sz = .102
    P += [B('rearblock', (.016, .016, .006), (0, .03, .101), S, .001),
          B('rearL', (.005, .006, .007), (.0055, .025, sz - .002), S, .0006), B('rearR', (.005, .006, .007), (-.0055, .025, sz - .002), S, .0006),
          ext('frontblade', [(-.16, .094), (-.163, sz), (-.172, sz), (-.176, .094)], .0035, S, .0006, 2),
          B('fiber', (.0037, .006, .003), (0, -.168, sz - .002), OR, .0004)]
    finish('gun_revolver', P, (0, -.185, zb), (0, -.02, -.035), (0, .07, sz))


# ================================================================== horror line (living biomass)
def _ax_y():
    return np.array([[1, 0, 0], [0, 0, 1], [0, 1, 0]], np.float32)   # torus axis along Y


def _bio_keys(mouth, rmouth=.05):
    mouth = np.asarray(mouth, np.float32)

    def pulse(co, no, mats):
        wave = .5 + .5 * np.sin(co[:, 1] * 38.0 + co[:, 0] * 25.0)
        amt = np.where(mats == 'bio_glow', .0055 + .002 * wave, np.where(mats == 'bio_flesh', .0018 * wave, np.where(mats == 'bio_maw', .002, 0.0)))
        return no * amt[:, None]

    def gape(co, no, mats):
        d = co - mouth
        dist = np.linalg.norm(d, axis=1)
        f = 1 - sdf.smoothstep(rmouth * .6, rmouth * 1.8, dist)
        rad = d.copy(); rad[:, 1] = 0
        off = rad * .45 * f[:, None]
        off[:, 1] = -.012 * f
        return off

    def keys(g):
        K.shape_key(g, 'pulse', pulse)
        K.shape_key(g, 'gape', gape)
    return keys


def bio_spitter():
    """Spitter: a ribbed, breathing tube of muscle that hawks acid globs from a toothed maw."""
    bl.reset(); M = K.bio_mats()
    zb = .07; Ry = _ax_y()
    mouth = (0, -.565, zb)

    def rb(y):
        return float(np.interp(-y, [-.24, -.05, .36, .52], [.042, .06, .042, .05]))

    def body(P):
        d = sdf.round_cone(P, (0, .24, .045), (0, .05, .075), .042, .06)
        d = sdf.smin(d, sdf.round_cone(P, (0, .05, .075), (0, -.36, .072), .06, .042), .04)
        d = sdf.smin(d, sdf.round_cone(P, (0, -.36, .072), (0, -.53, zb), .042, .05), .05)
        d = sdf.smin(d, sdf.round_cone(P, (0, .005, .035), (0, .036, -.105), .023, .019), .03)        # grip
        d = sdf.smin(d, sdf.round_cone(P, (0, -.28, .045), (0, -.295, -.05), .027, .018), .035)      # foregrip growth
        d = sdf.smin(d, sdf.ellipsoid(P, (0, -.03, .02), (.03, .03, .025)), .02)                     # trigger knot
        for i, y in enumerate(np.linspace(-.06, -.44, 8)):
            d = sdf.smin(d, sdf.torus(P, (0, y, .073 - .003 * i), rb(y) - .003, .0075, Ry), .012)
        for s in (1, -1):                                                                          # tendons along the flanks
            d = sdf.smin(d, sdf.capsule(P, (s * .052, .04, .08), (s * .04, -.34, .062), .0045), .006)
            d = sdf.smin(d, sdf.capsule(P, (s * .045, .12, .05), (s * .038, -.2, .035), .0035), .005)
        d = d + K.lumps(P, 3, 120, .0025) + K.lumps(P, 4, 40, .003)
        d = sdf.smax(d, -sdf.ellipsoid(P, (0, -.575, zb), (.032, .055, .026)), .012)               # the maw
        return d
    lo, hi = (-.1, -.62, -.14), (.1, .3, .16)
    P = [K.sdf_part('flesh', body, lo, hi, .0026, M['flesh'], 8000)]

    def sacs(P):
        d = sdf.ellipsoid(P, (.042, -.12, .1), (.022, .036, .02))
        d = np.minimum(d, sdf.ellipsoid(P, (-.042, -.13, .098), (.02, .03, .019)))
        d = np.minimum(d, sdf.ellipsoid(P, (0, .1, .118), (.026, .045, .022)))
        d = np.minimum(d, sdf.ellipsoid(P, (.03, -.33, .095), (.016, .022, .015)))
        d = np.minimum(d, sdf.ellipsoid(P, (-.024, .17, .085), (.016, .02, .016)))
        return d + K.lumps(P, 5, 160, .0015)
    P.append(K.sdf_part('sacs', sacs, (-.08, -.37, .05), (.08, .24, .15), .0018, M['glow'], 2500))

    def bone(P):
        d = sdf.round_cone(P, (0, -.42, .1), (0, -.36, .16), .012, .002)                       # horn
        for i, y in enumerate(np.linspace(.0, -.3, 6)):                                         # spine plates
            d = np.minimum(d, sdf.ellipsoid(P, (0, y, .128 - .008 * i), (.014, .02, .008), sdf.rot((1, 0, 0), .35)))
        d = np.minimum(d, sdf.torus(P, (0, .08, .155), .0085, .0026, Ry))                       # rear aperture
        d = np.minimum(d, sdf.round_cone(P, (0, .08, .128), (0, .08, .146), .006, .003))
        d = np.minimum(d, sdf.round_cone(P, (0, -.385, .1), (0, -.385, .155), .007, .0018))     # front spike sight
        for k in range(10):                                                                     # teeth around the maw
            a = k / 10 * 2 * math.pi
            rim = np.array([math.cos(a) * .036, -.548, zb + math.sin(a) * .027])
            tip = np.array([math.cos(a) * .014, -.585, zb + math.sin(a) * .01])
            d = np.minimum(d, sdf.round_cone(P, rim, tip, .0055, .0008))
        for s in (1, -1):                                                                       # side spurs
            d = np.minimum(d, sdf.round_cone(P, (s * .05, -.2, .07), (s * .085, -.15, .1), .008, .0015))
            d = np.minimum(d, sdf.round_cone(P, (s * .055, .06, .08), (s * .09, .11, .11), .008, .0015))
        return d
    P.append(K.sdf_part('bone', bone, (-.1, -.6, .03), (.1, .2, .17), .0015, M['bone'], 3500))
    P.append(K.sdf_part('maw', lambda P: sdf.ellipsoid(P, (0, -.548, zb), (.026, .03, .021)) + K.lumps(P, 6, 200, .001),
                        (-.04, -.6, .03), (.04, -.5, .11), .0018, M['maw'], 700))
    finish('gun_bio_spitter', P, (0, -.6, zb), (0, -.295, -.02), (0, .13, .155), organic=('bio_flesh', 'bio_maw', 'bio_glow'),
           cyl_axis=(0, .07), keys=_bio_keys(mouth, .045))


def bio_bile():
    """Bile cannon: a swollen, glowing stomach slung under a short gullet that retches a spray of caustic bile."""
    bl.reset(); M = K.bio_mats()
    zb = .075; Ry = _ax_y()

    def body(P):
        d = sdf.round_cone(P, (0, .2, .05), (0, .02, .08), .04, .058)
        d = sdf.smin(d, sdf.round_cone(P, (0, .02, .08), (0, -.33, zb), .058, .05), .04)
        d = sdf.smin(d, sdf.ellipsoid(P, (0, -.4, zb), (.07, .06, .052)), .04)                     # wide head
        d = sdf.smin(d, sdf.round_cone(P, (0, .005, .035), (0, .036, -.105), .023, .019), .03)
        d = sdf.smin(d, sdf.ellipsoid(P, (0, -.17, .005), (.05, .1, .052)), .03)                   # stomach wall
        for s in (1, -1):                                                                          # gullet tubes
            d = sdf.smin(d, sdf.capsule(P, (s * .042, -.08, .0), (s * .05, -.36, .05), .009), .012)
        for i, y in enumerate(np.linspace(.0, -.3, 5)):
            d = sdf.smin(d, sdf.torus(P, (0, y, .078), .056, .007, Ry), .012)
        d = d + K.lumps(P, 7, 110, .0028) + K.lumps(P, 8, 35, .004)
        d = sdf.smax(d, -sdf.ellipsoid(P, (0, -.46, zb), (.055, .06, .026)), .014)                 # wide horizontal maw
        d = sdf.smax(d, -sdf.ellipsoid(P, (0, -.17, -.015), (.038, .085, .04)), .01)               # window onto the stomach sac
        return d
    P = [K.sdf_part('flesh', body, (-.1, -.53, -.11), (.1, .26, .15), .0026, M['flesh'], 8000)]

    def sac(P):
        d = sdf.ellipsoid(P, (0, -.17, -.012), (.042, .088, .043))
        d = np.minimum(d, sdf.ellipsoid(P, (.035, .06, .11), (.014, .02, .014)))
        d = np.minimum(d, sdf.ellipsoid(P, (-.03, -.25, .12), (.016, .024, .015)))
        return d + K.lumps(P, 9, 140, .002)
    P.append(K.sdf_part('sac', sac, (-.07, -.29, -.07), (.07, .1, .14), .002, M['glow'], 2500))

    def bone(P):
        d = sdf.torus(P, (0, .07, .16), .009, .0026, Ry)
        d = np.minimum(d, sdf.round_cone(P, (0, .07, .13), (0, .07, .151), .006, .003))
        d = np.minimum(d, sdf.round_cone(P, (0, -.36, .12), (0, -.36, .16), .007, .0018))
        for k in range(8):                                                                      # upper and lower fangs
            x = -.04 + k * .0115
            d = np.minimum(d, sdf.round_cone(P, (x, -.43, zb + .026), (x * .8, -.475, zb + .004), .005, .0008))
            d = np.minimum(d, sdf.round_cone(P, (x, -.43, zb - .026), (x * .8, -.47, zb - .004), .0045, .0008))
        for i, y in enumerate(np.linspace(.12, -.3, 7)):                                        # dorsal ridge
            d = np.minimum(d, sdf.round_cone(P, (0, y, .125 - .004 * i), (0, y + .03, .145 - .004 * i), .009, .002))
        for s in (1, -1):
            d = np.minimum(d, sdf.round_cone(P, (s * .065, -.38, .09), (s * .1, -.33, .13), .009, .0015))
        return d
    P.append(K.sdf_part('bone', bone, (-.12, -.5, .03), (.12, .2, .17), .0015, M['bone'], 3500))
    P.append(K.sdf_part('maw', lambda P: sdf.ellipsoid(P, (0, -.43, zb), (.048, .04, .02)) + K.lumps(P, 10, 200, .001),
                        (-.06, -.48, .04), (.06, -.38, .11), .0018, M['maw'], 700))
    finish('gun_bio_bile', P, (0, -.49, zb), (0, -.2, -.06), (0, .12, .16), organic=('bio_flesh', 'bio_maw', 'bio_glow'),
           cyl_axis=(0, .07), keys=_bio_keys((0, -.465, zb), .06))


def bio_brood():
    """Brood launcher: a carapace-armoured womb with a cluster of egg sacs; spore pods leave a petalled orifice."""
    bl.reset(); M = K.bio_mats()
    zb = .11; Ry = _ax_y()

    def body(P):
        d = sdf.round_cone(P, (0, .3, .07), (0, .05, .11), .05, .08)
        d = sdf.smin(d, sdf.round_cone(P, (0, .05, .11), (0, -.5, zb), .08, .06), .05)
        d = sdf.smin(d, sdf.ellipsoid(P, (0, -.6, zb), (.075, .07, .07)), .05)
        d = sdf.smin(d, sdf.round_cone(P, (0, .005, .05), (0, .036, -.105), .024, .02), .035)
        d = sdf.smin(d, sdf.round_cone(P, (0, -.3, .06), (0, -.31, -.04), .03, .02), .04)
        for i, y in enumerate(np.linspace(-.05, -.52, 9)):
            d = sdf.smin(d, sdf.torus(P, (0, y, zb), .077 - .002 * i, .008, Ry), .014)
        for s in (1, -1):
            d = sdf.smin(d, sdf.capsule(P, (s * .07, .1, .1), (s * .06, -.5, .1), .006), .008)
        d = d + K.lumps(P, 11, 90, .003) + K.lumps(P, 12, 30, .005)
        d = sdf.smax(d, -sdf.sphere(P, (0, -.67, zb), .045), .015)                                 # orifice
        return d
    P = [K.sdf_part('flesh', body, (-.13, -.72, -.14), (.13, .37, .21), .003, M['flesh'], 9000)]

    def eggs(P):
        d = np.full(len(P), 1e3, np.float32)
        rng = np.random.default_rng(4)
        for s in (1, -1):
            for k in range(5):
                c = (s * (.075 + rng.random() * .012), -.08 - k * .07 + rng.random() * .02, .08 + rng.random() * .05)
                d = np.minimum(d, sdf.ellipsoid(P, c, (.026, .03, .026)))
        return d + K.lumps(P, 13, 170, .0015)
    P.append(K.sdf_part('eggs', eggs, (-.13, -.42, .02), (.13, .0, .17), .0018, M['glow'], 3500))

    def bone(P):
        d = np.full(len(P), 1e3, np.float32)
        for i, y in enumerate(np.linspace(.15, -.45, 5)):                                       # carapace plates
            shell = sdf.ellipsoid(P, (0, y, zb + .02), (.09, .085, .09))
            inner = sdf.ellipsoid(P, (0, y + .01, zb + .005), (.085, .09, .085))
            plate = sdf.smax(shell, -inner, .004)
            plate = sdf.smax(plate, -(P[:, 2] - (zb + .045)), .006)
            d = np.minimum(d, plate)
        for k in range(4):                                                                      # petals around the orifice
            a = k * math.pi / 2 + math.pi / 4
            base = np.array([math.cos(a) * .055, -.64, zb + math.sin(a) * .055])
            tip = np.array([math.cos(a) * .075, -.72, zb + math.sin(a) * .075])
            d = np.minimum(d, sdf.round_cone(P, base, tip, .012, .002))
        d = np.minimum(d, sdf.torus(P, (0, .02, .225), .01, .003, Ry))
        d = np.minimum(d, sdf.round_cone(P, (0, .02, .19), (0, .02, .215), .007, .0035))
        d = np.minimum(d, sdf.round_cone(P, (0, -.5, .17), (0, -.5, .225), .008, .002))
        return d
    P.append(K.sdf_part('bone', bone, (-.12, -.76, .03), (.12, .27, .25), .0022, M['bone'], 4500))
    P.append(K.sdf_part('maw', lambda P: sdf.sphere(P, (0, -.64, zb), .038) + K.lumps(P, 14, 200, .0015),
                        (-.05, -.69, .06), (.05, -.59, .16), .002, M['maw'], 700))
    finish('gun_bio_brood', P, (0, -.7, zb), (0, -.31, -.04), (0, .07, .225), organic=('bio_flesh', 'bio_maw', 'bio_glow'),
           cyl_axis=(0, .1), keys=_bio_keys((0, -.66, zb), .06))


# ================================================================== sight attachments (gun_attach.glb)
def attachments():
    """Each ATT_<id> node: origin = top of the rail, optic axis along -Y. Children <node>_sight (eye point) and,
    for magnified optics, <node>_scope. The game mounts the node on a gun's 'rail' empty."""
    bl.reset()
    M = K.kinetic_mats()
    AL = K.tmat('gun_optic', 'wpn_park')
    L, D, RB = M['lens'], M['dot'], M['rubber']

    def mount(y, w=.026):
        return [B('clamp', (w, .02, .009), (0, y, .0045), AL, .0015), cylx('clampknob', .006, .008, (-w / 2 - .004, y, .004), AL, 20)]

    def done(name, parts, eye, scope=False):
        g = K.assemble(name, parts)
        bl.empty(name + '_sight', eye, g)
        if scope:
            bl.empty(name + '_scope', eye, g)

    # open reflex: low base, angled window, emitter
    h = .022
    done('ATT_reflex', mount(0) + [B('rx_base', (.028, .046, .008), (0, 0, .011), AL, .002),
                                   ext('rx_hood', [(.016, .012), (.012, .037), (-.016, .037), (-.016, .012)], .03, AL, .002,
                                       cuts=[cbox((.024, .1, .02), (0, 0, .025))]),
                                   B('rx_glass', (.024, .0015, .02), (0, -.014, h), L, 0, rot=(.12, 0, 0)),
                                   ball('rx_dot', .0012, (0, -.024, h), D, seg=10, rings=6),
                                   cylz('rx_emitter', .003, .004, (0, .008, .016), AL, 12),
                                   B('rx_btn', (.004, .008, .004), (.016, .004, .014), RB, .001)], (0, .1, h))
    # holographic: boxy hood, big window, battery cap, buttons
    h = .03
    done('ATT_holo', mount(.02) + mount(-.02) + [B('hg_base', (.034, .07, .012), (0, 0, .013), AL, .003),
                                                ext('hg_hood', [(.03, .018), (.03, .048), (-.036, .048), (-.036, .018)], .04, AL, .003,
                                                    cuts=[cbox((.03, .1, .024), (0, 0, .032))]),
                                                B('hg_glass', (.03, .0015, .022), (0, -.03, h), L, 0), B('hg_glass2', (.03, .0015, .022), (0, .024, h), L, 0),
                                                ring('hg_reticle', .0035, .0004, (0, -.04, h), D, maj=24, mn=4),
                                                ball('hg_dot', .0009, (0, -.04, h), D, seg=8, rings=6),
                                                cylx('hg_battery', .007, .016, (.026, .01, .016), AL, 24),
                                                B('hg_btn', (.006, .01, .004), (0, .03, .02), RB, .001), B('hg_btn2', (.006, .01, .004), (0, .042, .02), RB, .001)],
         (0, .12, h))

    def scope(name, L_, r, obj, h, eye_relief, turrets=True, shade=0.0):
        P = mount(.035) + mount(-.035)
        for yy in (.035, -.035):
            P += [B('ringbase', (.022, .016, h - r), (0, yy, (h - r) / 2 + .004), AL, .002),
                  ring('ring', r + .0025, .003, (0, yy, h), AL, maj=48, mn=8)]
        P += [tube('tube', r, L_ * .55, L_ * .22, h, AL, 48),
              tube('eyebell', r * 1.25, L_ * .2, L_ * .42, h, AL, 48, r2=r),
              tube('eyecup', r * 1.3, L_ * .05, L_ * .47, h, RB, 48, hollow=r * 1.05),
              tube('objbell', r, L_ * .25, -L_ * .33, h, AL, 48, r2=obj),
              tube('objective', obj, L_ * .1, -L_ * .58, h, AL, 48, hollow=obj * .86),
              tube('lens_f', obj * .87, .002, -L_ * .6, h, L, 48, bevel=0), tube('lens_r', r * 1.06, .002, L_ * .44, h, L, 48, bevel=0),
              ring('power', r * 1.26, .003, (0, L_ * .3, h), RB, maj=48, mn=8)]
        if shade:
            P.append(tube('sunshade', obj * 1.02, shade, -L_ * .68, h, AL, 48, hollow=obj * .94))
        if turrets:
            P += [cylz('turret_e', .011, .016, (0, -.01, h + r + .008), AL, 32), cylz('cap_e', .0118, .006, (0, -.01, h + r + .018), RB, 32),
                  cylx('turret_w', .011, .016, (-(r + .008), -.01, h), AL, 32), cylx('cap_w', .0118, .006, (-(r + .018), -.01, h), RB, 32),
                  cylx('parallax', .009, .012, (r + .006, -.01, h), AL, 32)]
        done(name, P, (0, L_ * .47 + eye_relief, h), True)

    scope('ATT_x2', .15, .0145, .019, .032, .05, turrets=False)
    scope('ATT_x4', .24, .015, .022, .036, .06)
    scope('ATT_x8', .34, .016, .028, .042, .07, shade=.05)
    bl.export('gun_attach.glb', export_attributes=True)


GUNS = dict(auto=auto_rifle, pulse=pulse_rifle, scout=scout_rifle, handcannon=hand_cannon, shotgun=shotgun, sniper=sniper,
            rocket=rocket, smg=smg, sidearm=sidearm, hmg=heavy_mg, energy=energy_rifle,
            rifle=assault_rifle, carbine=carbine, bolt=bolt_rifle, pistol=service_pistol, pump=pump_shotgun, ksmg=compact_smg,
            dmr=battle_rifle, revolver=revolver,
            spitter=bio_spitter, bile=bio_bile, brood=bio_brood, attach=attachments)

if __name__ == '__main__':
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    args = [a for a in args if a]
    for k in (args or list(GUNS)):
        GUNS[k]()
