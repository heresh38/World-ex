"""Weapons: auto rifle, hand cannon, scout rifle, shotgun, sniper, rocket launcher, sidearm-style pulse rifle.

Frame: origin = pistol grip (right hand), barrel along Blender -Y (-> +Z in three.js).
Empties: muzzle, foregrip, sight (eye line for ADS). Materials: gun_body, gun_metal, gun_trim, gun_glow
(the game tints gun_glow by rarity and gun_body by the equipped shader).
"""
import bpy, math, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import bl
from mathutils import Vector

R90 = math.pi / 2


def mats():
    return dict(body=bl.mat('gun_body', '#e8e2d4', 0.05, .32),
                metal=bl.mat('gun_metal', '#30343b', .9, .3),
                trim=bl.mat('gun_trim', '#c79a45', 1.0, .25),
                glow=bl.mat('gun_glow', '#1ad8ff', 0, .4, emit='#1ad8ff', strength=7),
                grip=bl.mat('gun_grip', '#202224', 0, .6, image='carbon_c.jpg', normal='carbon_n.jpg', uv_scale=4),
                lens=bl.mat('gun_lens', '#3a8fb0', .5, .05, emit='#0b3550', strength=1.5))


def barrel(name, r, length, y0, z, m, verts=14):
    """cylinder along -Y starting at y0."""
    return bl.cyl(name, r, length, (0, y0 - length / 2, z), m, verts, rot=(R90, 0, 0))


def grip(M, y=0.0, z=0.0, ang=.25, h=.11):
    return [bl.box('grip', (.032, .05, h), (0, y + .02, z - h / 2 + .01), M['grip'], bevel=.008, rot=(ang, 0, 0)),
            bl.box('trigguard', (.012, .07, .012), (0, y - .035, z - .04), M['metal'])]


def scope(M, y, z, L=.12, r=.022):
    return [barrel('scope', r, L, y, z, M['metal']),
            bl.cyl('lens_f', r * .85, .004, (0, y - L - .002, z), M['lens'], 14, rot=(R90, 0, 0)),
            bl.box('scopemount', (.02, L * .5, .02), (0, y - L / 2, z - r - .008), M['metal'])]


def finish(name, parts, muzzle, fore, sight):
    for o in parts:
        bl.apply_all(o)
    g = bl.join(parts, name)
    bl.empty('muzzle', muzzle, g); bl.empty('foregrip', fore, g); bl.empty('sight', sight, g)
    bl.export(name + '.glb')


def auto_rifle():
    bl.reset(); M = mats(); P = []
    P += grip(M)
    P.append(bl.box('receiver', (.05, .34, .085), (0, -.06, .05), M['body'], bevel=.012))
    P.append(bl.box('rail', (.03, .3, .015), (0, -.07, .1), M['metal']))
    P.append(bl.box('stock', (.04, .2, .07), (0, .2, .04), M['body'], bevel=.015))
    P.append(bl.box('stockpad', (.045, .03, .085), (0, .31, .035), M['metal'], bevel=.008))
    P.append(bl.box('handguard', (.056, .2, .07), (0, -.3, .045), M['metal'], bevel=.01))
    P.append(barrel('barrel', .014, .2, -.4, .055, M['metal']))
    P.append(barrel('flash', .022, .05, -.58, .055, M['trim']))
    P.append(bl.box('mag', (.035, .06, .14), (0, -.12, -.04), M['metal'], bevel=.008, rot=(-.15, 0, 0)))
    P.append(bl.box('glowL', (.004, .22, .012), (.029, -.08, .06), M['glow']))
    P.append(bl.box('glowR', (.004, .22, .012), (-.029, -.08, .06), M['glow']))
    P.append(bl.box('trimband', (.058, .02, .075), (0, -.2, .05), M['trim'], bevel=.005))
    P += scope(M, -.0, .13, .11, .02)
    finish('gun_auto', P, (0, -.62, .055), (0, -.3, .0), (0, -.02, .13))


def hand_cannon():
    bl.reset(); M = mats(); P = []
    P += grip(M, ang=.35, h=.12)
    P.append(bl.box('frame', (.04, .2, .06), (0, -.07, .045), M['body'], bevel=.012))
    P.append(bl.cyl('cylinder', .04, .07, (0, -.04, .055), M['metal'], 8, rot=(R90, 0, 0)))
    for i in range(6):
        a = i * math.pi / 3
        P.append(bl.cyl('chamber', .009, .072, (math.cos(a) * .026, -.04, .055 + math.sin(a) * .026), M['trim'], 8, rot=(R90, 0, 0)))
    P.append(barrel('barrel', .018, .2, -.08, .065, M['metal']))
    P.append(bl.box('rib', (.022, .2, .014), (0, -.18, .088), M['body'], bevel=.004))
    P.append(bl.box('hammer', (.012, .03, .03), (0, .04, .085), M['trim']))
    P.append(bl.box('glow', (.004, .15, .01), (.02, -.17, .065), M['glow']))
    P.append(bl.box('sightpost', (.006, .01, .02), (0, -.26, .1), M['glow']))
    finish('gun_handcannon', P, (0, -.29, .065), (0, -.02, -.02), (0, .02, .1))


def scout_rifle():
    bl.reset(); M = mats(); P = []
    P += grip(M)
    P.append(bl.box('receiver', (.048, .4, .075), (0, -.08, .05), M['body'], bevel=.014))
    P.append(bl.box('stock', (.035, .26, .05), (0, .22, .03), M['body'], bevel=.012, rot=(-.08, 0, 0)))
    P.append(bl.box('cheek', (.04, .12, .03), (0, .2, .07), M['metal'], bevel=.008))
    P.append(barrel('barrel', .013, .38, -.3, .05, M['metal']))
    P.append(barrel('muzbrake', .02, .06, -.66, .05, M['trim']))
    P.append(bl.box('mag', (.03, .08, .08), (0, -.1, -.02), M['metal'], bevel=.008))
    P += scope(M, .02, .13, .2, .026)
    P.append(bl.box('glow', (.004, .3, .01), (.026, -.1, .045), M['glow']))
    P.append(bl.box('glow2', (.004, .3, .01), (-.026, -.1, .045), M['glow']))
    finish('gun_scout', P, (0, -.72, .05), (0, -.32, .0), (0, .0, .13))


def shotgun():
    bl.reset(); M = mats(); P = []
    P += grip(M)
    P.append(bl.box('receiver', (.06, .26, .09), (0, -.05, .05), M['body'], bevel=.016))
    P.append(bl.box('stock', (.05, .24, .08), (0, .2, .035), M['metal'], bevel=.02))
    for x in (-.017, .017):
        P.append(barrel('barrel', .016, .36, -.16, .07, M['metal']))
        P[-1].location.x = x
    P.append(bl.box('pump', (.07, .14, .05), (0, -.34, .025), M['body'], bevel=.015))
    for i in range(4):
        P.append(bl.box('pumprib', (.074, .012, .054), (0, -.29 - i * .03, .025), M['trim']))
    P.append(bl.box('shells', (.07, .1, .02), (0, -.06, .1), M['trim'], bevel=.005))
    P.append(bl.box('glow', (.004, .18, .015), (.031, -.05, .05), M['glow']))
    P.append(bl.box('glow2', (.004, .18, .015), (-.031, -.05, .05), M['glow']))
    finish('gun_shotgun', P, (0, -.53, .07), (0, -.34, -.01), (0, -.02, .12))


def sniper():
    bl.reset(); M = mats(); P = []
    P += grip(M)
    P.append(bl.box('receiver', (.05, .36, .08), (0, -.04, .05), M['metal'], bevel=.012))
    P.append(bl.box('chassis', (.058, .28, .05), (0, -.27, .03), M['body'], bevel=.012))
    P.append(bl.box('stock', (.045, .3, .06), (0, .26, .04), M['body'], bevel=.015))
    P.append(bl.box('stockhole', (.05, .12, .02), (0, .26, .02), M['metal']))
    P.append(barrel('barrel', .015, .55, -.38, .055, M['metal']))
    P.append(barrel('suppressor', .026, .14, -.86, .055, M['metal']))
    P.append(bl.box('bolt', (.06, .015, .015), (-.035, .02, .07), M['trim']))
    P += scope(M, .07, .14, .28, .03)
    P.append(bl.box('bipodL', (.01, .01, .1), (.025, -.55, -.02), M['metal']))
    P.append(bl.box('bipodR', (.01, .01, .1), (-.025, -.55, -.02), M['metal']))
    P.append(bl.box('glow', (.004, .26, .012), (.03, -.27, .03), M['glow']))
    finish('gun_sniper', P, (0, -1.0, .055), (0, -.3, .0), (0, .05, .14))


def rocket():
    bl.reset(); M = mats(); P = []
    P += grip(M, y=0.0)
    P.append(barrel('tube', .075, .9, .3, .12, M['body'], 18))
    P.append(barrel('tubebandF', .085, .05, -.48, .12, M['metal'], 18))
    P.append(barrel('tubebandB', .085, .05, .3, .12, M['metal'], 18))
    P.append(barrel('nozzle', .06, .06, .36, .12, M['trim'], 18))
    P.append(bl.box('grip2', (.03, .05, .1), (0, -.28, .0), M['grip'], bevel=.008))
    P.append(bl.box('sightbox', (.04, .1, .05), (.08, -.05, .17), M['metal'], bevel=.01))
    P.append(bl.box('glowring', (.004, .5, .02), (.074, -.15, .12), M['glow']))
    P.append(bl.box('glowring2', (.004, .5, .02), (-.074, -.15, .12), M['glow']))
    P.append(bl.box('hazard', (.155, .08, .155), (0, -.36, .12), M['trim'], bevel=.02))
    finish('gun_rocket', P, (0, -.62, .12), (0, -.28, -.02), (.08, -.0, .2))


def pulse_rifle():
    bl.reset(); M = mats(); P = []
    P += grip(M)
    P.append(bl.box('body', (.06, .38, .1), (0, -.06, .05), M['body'], bevel=.025))
    P.append(bl.box('topcut', (.064, .14, .03), (0, -.14, .1), M['metal']))
    P.append(barrel('barrel', .016, .14, -.25, .05, M['metal']))
    P.append(barrel('emitter', .026, .05, -.36, .05, M['trim']))
    P.append(bl.box('stock', (.05, .16, .08), (0, .2, .04), M['metal'], bevel=.02))
    P.append(bl.box('cell', (.04, .07, .09), (0, -.12, -.04), M['glow'], bevel=.01))
    P.append(bl.box('glow', (.066, .02, .02), (0, -.02, .09), M['glow']))
    P += scope(M, .0, .135, .09, .018)
    finish('gun_pulse', P, (0, -.42, .05), (0, -.24, .0), (0, -.0, .135))


for f in (auto_rifle, hand_cannon, scout_rifle, shotgun, sniper, rocket, pulse_rifle):
    f()
