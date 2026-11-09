"""Void Requiem: the first operation's raid weapon set (the owner's concept sheet art/reference/operation/
void_requiem_weapons.png; our own models). Nine energy guns sharing one look: black bodies (the "requiem" shader),
angular silver plates, gold trim, a violet void core on both flanks (a gold ring round a glowing disc with a crystal
shard standing in it), crystalline fins swept back along the top and under the barrel, glowing seams.

  gun_vr_rifle       Last Rite          assault rifle: angular receiver, finned shroud, skeleton stock with a spur
  gun_vr_sniper      Vigil's End        sniper: long fluted barrel ending in a split crystal muzzle, long scope in gold rings
  gun_vr_smg         Threnody           submachine gun: compact, twin stacked barrels, folding spur stock
  gun_vr_shotgun     Toll of Ruin       shotgun: heavy, a flared crystal mouth, gold-banded pump grip
  gun_vr_lmg         Last Procession    light machine gun: box receiver, a drum with a lit window, vented shroud, carry handle
  gun_vr_handcannon  Final Verse        hand cannon: a cylinder of glowing chambers, a long bladed shroud
  gun_vr_pistol      Ashen Psalm        pistol: slim angular slide, the core in the frame, a spur at the muzzle
  gun_vr_fusion      Eulogy             fusion rifle: a wide body, a charge chamber, three prongs that cradle the shot
  gun_vr_rocket      Funeral Bell       rocket launcher: a banded tube ending in a crystal bell, a core on the shoulder

The frame, empties and material API are the energy line's (weapons.py): origin = top of the pistol grip, barrel along
Blender -Y, Z up, right side -X; gun_body (the shader colour), gun_metal, gun_dark, gun_trim (gold), gun_glow (the
rarity colour: violet for the set's Legendary drops), gun_grip, gun_lens.

Run: blender --background --python tools/blender/requiem_guns.py [-- vr_rifle ...]
"""
import math, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import bl
import gunkit as K
from gunkit import B, ext, tube, cbox, ccyl, cylx, cylz, ball, ring, rod, R90
from weapons import finish, e_grip, e_screws, e_rail, scope_tube, red_dot, RIGHT


# ------------------------------------------------------------------ the set's language
def core(M, y, z, r, w, P):
    """the void core on both flanks: a dark socket, a gold ring, a glowing disc, a crystal shard standing in it"""
    for s in (1, -1):
        x = s * (w / 2 + .002)
        P.append(cylx('core_socket', r * 1.12, .006, (x - s * .002, y, z), M['dark'], 32))
        P.append(ring('core_ring', r, r * .16, (x + s * .002, y, z), M['trim'], axis='x', maj=40, mn=10))
        P.append(cylx('core_disc', r * .78, .003, (x + s * .001, y, z), M['glow'], 32))
        P.append(rod('core_shard', (x + s * .004, y, z - r * .62), (x + s * .004, y, z + r * .62), r * .2, M['glow'], 6, r2=.0008))
        P.append(rod('core_shard2', (x + s * .004, y, z - r * .62), (x + s * .004, y, z - r * .1), r * .2, M['glow'], 6, r2=r * .05))


def fin(name, y, z, L, H, w, M, down=False, m=None):
    """a crystalline blade swept back along the gun (L long, rising H), thin, sharp"""
    s = -1 if down else 1
    pts = [(y, z), (y - L * .15, z + s * H * .35), (y + L * .55, z + s * H), (y + L, z + s * H * .25), (y + L * .9, z)]
    if down:
        pts = pts[::-1]
    return ext(name, pts, w, m or M['metal'], .0012, 2)


def seam(name, y0, y1, z, x, M):
    """a glowing seam on a flank"""
    return B(name, (.0018, abs(y1 - y0), .0045), (x, (y0 + y1) / 2, z), M['glow'], 0)


def gold_band(name, y, z, r, M, L=.012):
    return tube(name, r, L, y + L / 2, z, M['trim'], 40)


def plate(name, pts, w, M):
    """an angular silver armour plate standing proud of a flank"""
    return ext(name, pts, w, M['metal'], .0018, 2)


# ------------------------------------------------------------------ the nine
def vr_rifle():
    bl.reset(); M = K.energy_mats(); P = []
    P += e_grip(M)
    W = .054
    P += [ext('receiver', [(.15, .045), (.15, .088), (.1, .104), (-.18, .104), (-.24, .09), (-.25, .05), (-.05, .044)], W, M['body'], .006,
              cuts=[cbox((.012, .06, .02), (RIGHT * .027, -.02, .074))]),
          plate('plateL', [(.08, .06), (.06, .098), (-.16, .098), (-.2, .07), (-.14, .056)], W + .012, M),
          ext('shroud', [(-.24, .036), (-.24, .098), (-.36, .1), (-.5, .084), (-.52, .062), (-.5, .036)], .046, M['body'], .008,
              cuts=[cbox((.06, .024, .01), (0, -.3 - i * .05, .07)) for i in range(4)]),
          B('shroud_core', (.04, .24, .04), (0, -.38, .066), M['dark'], .004),
          seam('seamL', -.26, -.48, .078, .024, M), seam('seamR', -.26, -.48, .078, -.024, M),
          ext('mag', [(-.06, .044), (-.068, -.06), (-.09, -.13), (-.15, -.122), (-.13, -.06), (-.125, .044)], .032, M['metal'], .005),
          B('magglow', (.002, .035, .06), (.0165, -.1, -.03), M['glow'], 0),
          B('magfoot', (.038, .066, .012), (0, -.12, -.13), M['trim'], .003, rot=(-.2, 0, 0)),
          ext('stock', [(.15, .095), (.36, .09), (.4, .1), (.4, .066), (.37, -.02), (.34, -.03), (.22, .03), (.15, .045)], .036, M['body'], .01,
              cuts=[cbox((.06, .12, .04), (0, .27, .045))]),
          ext('stockpad', [(.4, .1), (.415, .1), (.415, -.03), (.4, -.03)], .042, M['grip'], .005),
          fin('stockspur', .32, .095, .1, .05, .006, M),
          fin('topfin', -.12, .104, .13, .03, .006, M),
          fin('shroudfin', -.52, .036, .12, .045, .006, M, down=True),
          gold_band('band1', -.24, .066, .03, M), gold_band('band2', -.5, .062, .026, M)]
    core(M, -.03, .074, .022, W, P)
    P += [tube('barrel', .011, .14, -.52, .062, M['dark'], 32), tube('muzzle', .017, .05, -.64, .062, M['metal'], 6),
          ring('muzzlering', .018, .003, (0, -.66, .062), M['trim'], maj=6, mn=6)]
    P += e_screws(M, [(-.3, .045), (.25, .07)], .056)
    P += e_rail(M, .1, -.16, .104)
    sz = .14
    finish('gun_vr_rifle', P, (0, -.69, .062), (0, -.34, .02), (0, .1, sz), optic=red_dot(M, -.02, sz), rail=(0, -.02, .1135))


def vr_sniper():
    bl.reset(); M = K.energy_mats(); P = []
    P += e_grip(M)
    W = .05
    P += [ext('receiver', [(.14, .03), (.14, .09), (-.3, .09), (-.33, .074), (-.33, .03)], W, M['body'], .012,
              cuts=[cbox((.012, .06, .018), (RIGHT * .025, -.02, .07))]),
          plate('plate', [(.06, .05), (.03, .084), (-.24, .084), (-.28, .06)], W + .012, M),
          ext('stock', [(.14, .08), (.38, .075), (.42, .09), (.42, .05), (.4, -.06), (.37, -.07), (.2, .0), (.14, .02)], .036, M['body'], .01,
              cuts=[cbox((.06, .1, .045), (0, .27, .02))]),
          ext('butt', [(.42, .09), (.435, .09), (.435, -.065), (.42, -.065)], .04, M['grip'], .005),
          fin('stockspur', .34, .08, .12, .06, .006, M), fin('underspur', .34, -.06, .1, .05, .006, M, down=True),
          tube('barrel', .013, .56, -.33, .056, M['dark'], 32, cuts=[cbox((.03, .02, .004), (0, -.42 - i * .06, .069)) for i in range(7)]),
          gold_band('band1', -.4, .056, .018, M), gold_band('band2', -.62, .056, .017, M),
          ext('mag', [(-.06, .03), (-.064, -.05), (-.13, -.05), (-.126, .03)], .03, M['metal'], .005)]
    for s in (1, -1):                                             # the split crystal muzzle
        P.append(rod('prong', (s * .012, -.88, .056), (s * .028, -.98, .056 + s * .006), .006, M['metal'], 6, r2=.0012))
        P.append(seam('seam', -.06, -.3, .05, s * .026, M))
    P.append(rod('muzzlecrystal', (0, -.88, .056), (0, -.96, .056), .008, M['glow'], 6, r2=.001))
    core(M, -.08, .06, .02, W, P)
    P += e_rail(M, .1, -.2, .09)
    P += K.sling_loop(.3, -.04, M['dark'])
    sz = .135
    sc = scope_tube(M, -.04, sz, .22, .02, .028)
    finish('gun_vr_sniper', P, (0, -.99, .056), (0, -.32, .0), (0, .12, sz), optic=sc + [ring('scopering', .023, .003, (0, -.0, sz), M['trim']),
                                                                                       ring('scopering2', .023, .003, (0, -.14, sz), M['trim'])],
           scoped=True, rail=(0, -.06, .0995))


def vr_smg():
    bl.reset(); M = K.energy_mats(); P = []
    P += e_grip(M, ang=.3)
    W = .05
    P += [ext('body', [(.1, .03), (.1, .1), (.06, .11), (-.2, .11), (-.24, .085), (-.24, .03)], W, M['body'], .008,
              cuts=[cbox((.012, .05, .018), (RIGHT * .025, -.03, .08))]),
          plate('plate', [(.02, .05), (0, .1), (-.18, .1), (-.2, .06)], W + .012, M),
          tube('barrelA', .009, .12, -.24, .08, M['dark'], 24), tube('barrelB', .009, .1, -.24, .052, M['dark'], 24),
          ext('muzzleblock', [(-.33, .04), (-.33, .094), (-.37, .094), (-.38, .04)], .03, M['metal'], .005),
          ext('mag', [(-.08, .03), (-.086, -.12), (-.13, -.12), (-.124, .03)], .028, M['metal'], .004),
          B('magglow', (.002, .025, .08), (.0145, -.105, -.04), M['glow'], 0),
          rod('stockarm', (.1, -.0, .085), (.24, -.0, .07), .006, M['dark']),
          rod('stockarm2', (.1, -.0, .045), (.24, -.0, .06), .006, M['dark']),
          ext('stockpad', [(.24, .095), (.255, .095), (.255, .02), (.24, .02)], .036, M['grip'], .004),
          fin('stockspur', .2, .095, .08, .04, .005, M), fin('topfin', -.1, .11, .1, .025, .005, M),
          fin('underfin', -.36, .04, .09, .04, .005, M, down=True),
          seam('seamL', -.02, -.2, .095, .026, M), seam('seamR', -.02, -.2, .095, -.026, M)]
    core(M, -.06, .07, .02, W, P)
    P += e_rail(M, .06, -.12, .11)
    sz = .15
    finish('gun_vr_smg', P, (0, -.39, .066), (0, -.2, .0), (0, .08, sz), optic=red_dot(M, -.04, sz), rail=(0, -.04, .1195))


def vr_shotgun():
    bl.reset(); M = K.energy_mats(); P = []
    P += e_grip(M)
    W = .062
    P += [ext('body', [(.14, .02), (.14, .1), (-.22, .1), (-.27, .08), (-.27, .02)], W, M['body'], .012),
          plate('plate', [(.06, .04), (.03, .094), (-.2, .094), (-.24, .06)], W + .014, M),
          tube('barrel', .02, .2, -.27, .066, M['dark'], 32),
          tube('pump', .026, .12, -.3, .05, M['grip'], 32),
          gold_band('pband1', -.3, .05, .028, M), gold_band('pband2', -.408, .05, .028, M),
          tube('mouth', .022, .07, -.47, .066, M['metal'], 6, r2=.04, hollow=.014),
          ring('mouthring', .04, .004, (0, -.54, .066), M['trim'], maj=6, mn=6),
          ext('stock', [(.14, .09), (.34, .08), (.35, .065), (.35, -.02), (.14, .02)], .052, M['body'], .014),
          ext('stockpad', [(.35, .085), (.365, .085), (.365, -.025), (.35, -.025)], .056, M['grip'], .005),
          fin('topfin', -.1, .1, .14, .035, .007, M), fin('stockspur', .28, .08, .08, .04, .006, M)]
    for i in range(5):                                            # crystal teeth in the mouth
        a = i * 2 * math.pi / 5
        P.append(rod('tooth', (math.cos(a) * .026, -.52, .066 + math.sin(a) * .026), (math.cos(a) * .018, -.56, .066 + math.sin(a) * .018), .004, M['glow'], 5, r2=.0006))
    core(M, -.08, .062, .026, W, P)
    P += e_rail(M, .08, -.12, .1)
    sz = .14
    finish('gun_vr_shotgun', P, (0, -.56, .066), (0, -.36, .02), (0, .1, sz), optic=K.iron_rear(M, .08, sz, M['dark']) + K.iron_front(M, -.24, sz, dot=M['green']),
           rail=(0, -.02, .1095))


def vr_lmg():
    bl.reset(); M = K.energy_mats(); P = []
    P += e_grip(M)
    W = .07
    P += [ext('receiver', [(.16, .02), (.16, .11), (.08, .124), (-.24, .124), (-.28, .1), (-.28, .02)], W, M['body'], .012,
              cuts=[cbox((.014, .07, .022), (RIGHT * .035, -.02, .08))]),
          plate('plate', [(.08, .04), (.06, .114), (-.2, .114), (-.24, .07), (-.18, .04)], W + .014, M),
          ext('shroud', [(-.28, .03), (-.28, .1), (-.56, .094), (-.58, .07), (-.56, .03)], .056, M['metal'], .008,
              cuts=[cbox((.07, .03, .014), (0, -.32 - i * .05, .08)) for i in range(5)]),
          B('shroud_core', (.046, .28, .05), (0, -.42, .064), M['dark'], .004),
          tube('barrel', .013, .12, -.58, .064, M['dark'], 32), tube('muzzle', .02, .05, -.68, .064, M['metal'], 8),
          rod('handle', (0, .04, .124), (0, -.14, .124), .006, M['dark']),
          ext('handlebar', [(.04, .13), (.04, .16), (-.14, .16), (-.14, .13)], .016, M['metal'], .004),
          tube('drum', .07, .07, .0, -.04, M['metal'], 40, cuts=[ccyl(.03, .1, (0, .03, -.04), (R90, 0, 0), 24)]),
          B('drumwin', (.074, .002, .05), (0, -.071, -.04), M['glow'], 0),
          ext('stock', [(.16, .1), (.38, .09), (.4, .075), (.4, -.03), (.16, .03)], .05, M['body'], .014),
          ext('stockpad', [(.4, .095), (.415, .095), (.415, -.035), (.4, -.035)], .054, M['grip'], .005),
          fin('topfin', -.1, .124, .14, .03, .007, M), fin('shroudfin', -.58, .03, .14, .05, .007, M, down=True),
          gold_band('band1', -.28, .064, .036, M), gold_band('band2', -.56, .064, .032, M),
          seam('seamL', -.3, -.54, .09, .029, M), seam('seamR', -.3, -.54, .09, -.029, M)]
    core(M, -.12, .08, .026, W, P)
    P += e_rail(M, .1, -.22, .124)
    sz = .16
    finish('gun_vr_lmg', P, (0, -.73, .064), (0, -.4, .02), (0, .1, sz), optic=red_dot(M, -.06, sz), rail=(0, -.06, .1335))


def vr_handcannon():
    bl.reset(); M = K.energy_mats(); P = []
    P += e_grip(M, ang=.38, h=.12)
    P += [ext('frame', [(.04, .015), (.045, .085), (.02, .1), (-.18, .1), (-.18, .02), (-.03, .015)], .042, M['body'], .008,
              cuts=[cbox((.062, .085, .064), (0, -.04, .058))])]
    cuts = [ccyl(.007, .09, (math.cos(i * math.pi / 3 + .52) * .038, -.04, .058 + math.sin(i * math.pi / 3 + .52) * .038), (R90, 0, 0), 16) for i in range(6)]
    P += [tube('cylinder', .039, .075, -.0025, .058, M['metal'], 48, cuts=cuts, bevel=.003),
          tube('cylglow', .03, .07, -.005, .058, M['glow'], 24)]
    for i in range(6):                                            # glowing chambers
        a = i * math.pi / 3 + .52
        P.append(tube('chamber', .0066, .072, -.004, .058 + math.sin(a) * .038, M['glow'], 12, x=math.cos(a) * .038))
    P += [tube('barrel', .017, .22, -.08, .072, M['metal'], 40, hollow=.008),
          ext('shroud', [(-.08, .062), (-.08, .1), (-.3, .1), (-.33, .09), (-.32, .066), (-.08, .062)], .042, M['body'], .008),
          plate('blade', [(-.1, .1), (-.12, .112), (-.3, .108), (-.34, .1)], .01, M),
          seam('seamL', -.1, -.3, .082, .022, M), seam('seamR', -.1, -.3, .082, -.022, M),
          ext('hammer', [(.03, .085), (.06, .115), (.08, .118), (.05, .082), (.04, .07)], .012, M['trim'], .002),
          fin('underfin', -.3, .062, .08, .03, .006, M, down=True)]
    P += e_screws(M, [(.0, .03), (-.16, .08)], .042)
    sz = .118
    P += [B('rear_notchL', (.008, .012, .016), (.009, .03, sz - .004), M['dark'], .002),
          B('rear_notchR', (.008, .012, .016), (-.009, .03, sz - .004), M['dark'], .002)]
    P += K.iron_front(M, -.3, sz, ears=False, dot=M['green'])
    finish('gun_vr_handcannon', P, (0, -.34, .072), (0, -.02, -.02), (0, .1, sz))


def vr_pistol():
    bl.reset(); M = K.energy_mats(); P = []
    P += e_grip(M, ang=.3, h=.11)
    P += [ext('frame', [(.04, .0), (.04, .05), (-.16, .05), (-.17, .03), (-.02, .0)], .03, M['body'], .006),
          ext('slide', [(.05, .05), (.05, .09), (.0, .096), (-.17, .094), (-.19, .07), (-.19, .05)], .034, M['metal'], .005,
              cuts=[cbox((.04, .006, .02), (0, .02 - i * .012, .08)) for i in range(4)]),
          B('slideglow', (.036, .1, .003), (0, -.08, .095), M['glow'], 0),
          fin('spur', -.19, .05, .06, .03, .005, M, down=True),
          ext('triggerguard_plate', [(-.02, .0), (-.05, -.02), (-.1, -.02), (-.12, .0)], .028, M['trim'], .003)]
    core(M, .0, -.03, .014, .036, P)
    sz = .108
    P += K.iron_rear(M, .03, sz, M['dark']) + K.iron_front(M, -.17, sz, dot=M['green'])
    finish('gun_vr_pistol', P, (0, -.2, .07), (0, -.02, -.02), (0, .1, sz), rail=(0, -.06, .096))


def vr_fusion():
    bl.reset(); M = K.energy_mats(); P = []
    P += e_grip(M)
    W = .07
    P += [ext('body', [(.14, .02), (.14, .1), (.06, .118), (-.22, .118), (-.28, .09), (-.28, .02)], W, M['body'], .012),
          plate('plate', [(.04, .04), (.02, .108), (-.2, .108), (-.24, .06)], W + .014, M),
          tube('chamber', .03, .16, -.24, .066, M['dark'], 32, hollow=.024),
          tube('chamberglow', .022, .15, -.245, .066, M['glow'], 24),
          gold_band('band1', -.25, .066, .034, M), gold_band('band2', -.39, .066, .034, M)]
    for i in range(3):                                            # three prongs cradle the shot
        a = math.pi / 2 + i * 2 * math.pi / 3
        x, zz = math.cos(a) * .04, .066 + math.sin(a) * .04
        P.append(rod('prong', (x, -.38, zz), (x * 1.3, -.52, .066 + (zz - .066) * 1.3), .009, M['metal'], 6, r2=.003))
        P.append(rod('prongtip', (x * 1.3, -.52, .066 + (zz - .066) * 1.3), (x * .7, -.58, .066 + (zz - .066) * .7), .004, M['glow'], 5, r2=.0008))
    P += [ext('stock', [(.14, .09), (.34, .085), (.36, .1), (.36, -.02), (.14, .02)], .05, M['body'], .014),
          ext('stockpad', [(.36, .1), (.375, .1), (.375, -.025), (.36, -.025)], .054, M['grip'], .005),
          fin('topfin', -.06, .118, .16, .035, .007, M), fin('stockspur', .28, .085, .08, .04, .006, M)]
    core(M, -.08, .07, .026, W, P)
    P += e_rail(M, .08, -.16, .118)
    sz = .155
    finish('gun_vr_fusion', P, (0, -.58, .066), (0, -.32, .02), (0, .1, sz), optic=red_dot(M, -.04, sz), rail=(0, -.04, .1275))


def vr_rocket():
    bl.reset(); M = K.energy_mats(); P = []
    P += e_grip(M, y=.0)
    P += [tube('tube', .055, .8, .34, .09, M['body'], 40, hollow=.045),
          tube('bell', .062, .08, -.46, .09, M['metal'], 8, r2=.085, hollow=.05),
          ring('bellring', .085, .005, (0, -.54, .09), M['trim'], maj=8, mn=6),
          gold_band('band1', -.1, .09, .058, M), gold_band('band2', -.32, .09, .058, M), gold_band('band3', .22, .09, .058, M),
          ext('shoulder', [(.1, .03), (.1, .06), (.28, .06), (.3, .04)], .07, M['grip'], .006),
          ext('frontgrip', [(-.2, .03), (-.2, .04), (-.26, .04), (-.27, -.05), (-.24, -.05)], .03, M['grip'], .004),
          fin('topfin', -.2, .145, .2, .05, .008, M), fin('topfin2', .1, .145, .14, .035, .008, M)]
    for i in range(6):                                            # crystal teeth round the bell
        a = i * math.pi / 3
        P.append(rod('tooth', (math.cos(a) * .07, -.53, .09 + math.sin(a) * .07), (math.cos(a) * .06, -.58, .09 + math.sin(a) * .06), .006, M['glow'], 5, r2=.0008))
    core(M, .06, .09, .03, .11, P)
    P += e_rail(M, .1, -.1, .145)
    sz = .18
    finish('gun_vr_rocket', P, (0, -.6, .09), (0, -.24, -.02), (0, .1, sz), optic=red_dot(M, -.02, sz), rail=(0, -.02, .1545))


GUNS = dict(vr_rifle=vr_rifle, vr_sniper=vr_sniper, vr_smg=vr_smg, vr_shotgun=vr_shotgun, vr_lmg=vr_lmg,
            vr_handcannon=vr_handcannon, vr_pistol=vr_pistol, vr_fusion=vr_fusion, vr_rocket=vr_rocket)

if __name__ == '__main__':
    args = [a for a in (sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []) if a]
    for k in (args or list(GUNS)):
        GUNS[k]()
