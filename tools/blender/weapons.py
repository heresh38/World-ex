"""Weapons v2: detailed first-person guns with working sights.

Frame: origin = pistol grip (right hand), barrel along Blender -Y (-> +Z in three.js).
Empties: muzzle, foregrip, sight (the eye point: looking from it along -Y passes through the sight's centre),
and optional 'scope' marks scoped weapons (the HUD draws a reticle when aiming).
Materials (names are an API): gun_body (shader colour/pattern), gun_metal, gun_trim, gun_glow (rarity colour),
gun_grip, gun_lens, gun_dot (red-dot / sight inserts).
"""
import bpy, math, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import bl
from mathutils import Vector

R90 = math.pi / 2


def mats():
    return dict(body=bl.mat('gun_body', '#e8e2d4', 0.05, .32, image='gunpaint_c.jpg'),
                metal=bl.mat('gun_metal', '#2a2e34', .85, .34, normal='panel_n.jpg', image='carbon_c.jpg', uv_scale=2),
                dark=bl.mat('gun_dark', '#15171a', .5, .55),
                trim=bl.mat('gun_trim', '#c79a45', 1.0, .25),
                glow=bl.mat('gun_glow', '#1ad8ff', 0, .4, emit='#1ad8ff', strength=7),
                grip=bl.mat('gun_grip', '#202224', 0, .6, image='carbon_c.jpg', normal='carbon_n.jpg', uv_scale=4),
                lens=bl.mat('gun_lens', '#1a3a48', .6, .04, emit='#06141c', strength=1.0),
                dot=bl.mat('gun_dot', '#ff2a2a', 0, .3, emit='#ff2a2a', strength=10),
                green=bl.mat('gun_tritium', '#46ff7a', 0, .3, emit='#46ff7a', strength=8))


def B(name, size, loc, m, bevel=.004, rot=(0, 0, 0)):
    return bl.box(name, size, loc, m, bevel=bevel, rot=rot)


def barrel(name, r, length, y0, z, m, verts=16, x=0.0):
    return bl.cyl(name, r, length, (x, y0 - length / 2, z), m, verts, rot=(R90, 0, 0))


def rail(M, y0, y1, z, w=.026):
    """Picatinny-style rail: base strip + teeth."""
    L = y0 - y1
    P = [B('railbase', (w, L, .008), (0, (y0 + y1) / 2, z), M['dark'], .002)]
    n = int(L / .012)
    for i in range(n):
        P.append(B('tooth', (w + .004, .006, .006), (0, y0 - .006 - i * .012, z + .007), M['dark'], 0))
    return P


def vents(M, y0, y1, z, x, n=5, h=.02):
    step = (y0 - y1) / n
    return [B('vent', (.004, step * .55, h), (x, y0 - step * (i + .5), z), M['dark'], 0) for i in range(n)]


def grip(M, y=0.0, z=0.0, ang=.28, h=.12):
    P = [B('grip', (.034, .052, h), (0, y + .02, z - h / 2 + .012), M['grip'], .01, rot=(ang, 0, 0)),
         B('gripcap', (.036, .056, .012), (0, y + .02 + math.sin(ang) * h * .5, z - h + .012), M['dark'], .004, rot=(ang, 0, 0)),
         B('trigguard', (.01, .075, .008), (0, y - .035, z - .045), M['dark'], .002),
         B('guardfront', (.01, .008, .03), (0, y - .072, z - .03), M['dark'], .002),
         B('trigger', (.006, .006, .022), (0, y - .03, z - .028), M['trim'], .001, rot=(.3, 0, 0))]
    for i in range(4):
        P.append(B('gripline', (.036, .004, .004), (0, y + .02 + i * .008, z - .02 - i * .022), M['dark'], 0, rot=(ang, 0, 0)))
    return P


def iron_rear(M, y, z):
    """Rear aperture (ring with ears). Its centre is at (0, y, z)."""
    return [bl.torus('rear_ring', .009, .0028, (0, y, z), M['dark'], rot=(R90, 0, 0), maj=16, mn=6),
            B('rear_base', (.03, .016, .016), (0, y, z - .016), M['dark'], .003),
            B('rear_earL', (.006, .014, .03), (.016, y, z - .004), M['dark'], .002),
            B('rear_earR', (.006, .014, .03), (-.016, y, z - .004), M['dark'], .002)]


def iron_front(M, y, z, ears=True, tritium=True):
    """Front post: its tip is at (0, y, z) so it sits in the middle of the rear aperture."""
    P = [B('post', (.004, .004, .02), (0, y, z - .01), M['dark'], .0008),
         B('front_base', (.024, .014, .012), (0, y, z - .026), M['dark'], .003)]
    if tritium:
        P.append(bl.sphere('postdot', .0025, (0, y + .002, z - .002), M['green'], 8, 6))
    if ears:
        for s in (1, -1):
            P.append(B('front_ear', (.004, .01, .028), (s * .013, y, z - .012), M['dark'], .0015, rot=(0, s * .15, 0)))
    return P


def red_dot(M, y, z):
    """Holographic sight; the dot floats on the sight line at (0, y - .03, z)."""
    P = [B('rd_base', (.034, .05, .012), (0, y, z - .025), M['dark'], .004),
         B('rd_hoodL', (.005, .05, .04), (.019, y, z - .002), M['dark'], .002),
         B('rd_hoodR', (.005, .05, .04), (-.019, y, z - .002), M['dark'], .002),
         B('rd_top', (.043, .05, .005), (0, y, z + .019), M['dark'], .002),
         B('rd_glass', (.033, .002, .034), (0, y - .02, z), M['lens'], 0),
         bl.sphere('rd_dot', .0016, (0, y - .03, z), M['dot'], 8, 6),
         B('rd_knob', (.01, .012, .012), (.026, y + .01, z - .01), M['dark'], .003)]
    return P


def scope_tube(M, y, z, L=.16, r=.022, objective=.03):
    """Rifle scope; centred on the sight line at height z."""
    P = [barrel('scope_tube', r, L * .6, y - L * .2, z, M['metal'], 20),
         bl.cyl('scope_obj', objective, L * .3, (0, y - L * .65, z), M['metal'], 24, rot=(R90, 0, 0), r2=r),
         bl.cyl('scope_bell', objective, L * .12, (0, y - L * .86, z), M['dark'], 24, rot=(R90, 0, 0)),
         bl.cyl('scope_eye', r * 1.15, L * .14, (0, y + L * .17, z), M['dark'], 20, rot=(R90, 0, 0)),
         bl.cyl('lens_f', objective * .86, .003, (0, y - L * .925, z), M['lens'], 24, rot=(R90, 0, 0)),
         bl.cyl('lens_r', r * .95, .003, (0, y + L * .245, z), M['lens'], 20, rot=(R90, 0, 0)),
         bl.cyl('turret_top', .009, .016, (0, y - L * .25, z + r + .008), M['trim'], 12),
         bl.cyl('turret_side', .009, .016, (r + .008, y - L * .25, z), M['dark'], 12, rot=(0, R90, 0))]
    for yy in (y - L * .05, y - L * .45):
        P.append(B('ring', (.008, .012, r * 2.4), (0, yy, z - r * .3), M['dark'], .002))
        P.append(B('ringbase', (.03, .014, .012), (0, yy, z - r - .008), M['dark'], .003))
    return P


def finish(name, parts, muzzle, fore, sight, scoped=False):
    for o in parts:
        bl.apply_all(o)
    # metal/dark get a box UV so the carbon/panel detail shows; body keeps per-part box UVs for the pattern
    g = bl.join(parts, name)
    bl.uv_box(g, .25)
    bl.empty('muzzle', muzzle, g); bl.empty('foregrip', fore, g); bl.empty('sight', sight, g)
    if scoped:
        bl.empty('scope', sight, g)
    bl.export(name + '.glb')


# -------------------------------------------------------------- the arsenal
def auto_rifle():
    bl.reset(); M = mats(); P = []
    P += grip(M)
    P += [B('upper', (.052, .34, .05), (0, -.06, .072), M['body'], .01),
          B('lower', (.048, .2, .05), (0, -.02, .028), M['body'], .01),
          B('chamfer', (.056, .3, .012), (0, -.07, .045), M['metal'], .003),
          B('ejport', (.002, .06, .02), (-.027, -.0, .07), M['dark'], 0),
          B('chargeh', (.02, .02, .01), (0, .1, .1), M['dark'], .003),
          B('handguard', (.06, .24, .06), (0, -.34, .062), M['metal'], .012),
          B('hg_glow', (.002, .16, .014), (.031, -.34, .068), M['glow'], 0),
          B('hg_glow2', (.002, .16, .014), (-.031, -.34, .068), M['glow'], 0),
          B('mag', (.034, .07, .15), (0, -.12, -.045), M['metal'], .008, rot=(-.18, 0, 0)),
          B('magbase', (.04, .076, .014), (0, -.107, -.12), M['dark'], .004, rot=(-.18, 0, 0)),
          B('stock', (.042, .22, .07), (0, .2, .05), M['body'], .015),
          B('stockpad', (.046, .03, .085), (0, .315, .045), M['dark'], .006),
          B('cheek', (.044, .1, .02), (0, .17, .092), M['metal'], .005),
          B('trimband', (.062, .016, .066), (0, -.22, .062), M['trim'], .003)]
    P += vents(M, -.25, -.43, .06, .0305, 6) + vents(M, -.25, -.43, .06, -.0305, 6)
    P += [barrel('barrel', .012, .16, -.46, .072, M['dark']), barrel('comp', .02, .06, -.6, .072, M['metal'], 12),
          B('compslot', (.042, .012, .006), (0, -.62, .072), M['dark'], 0)]
    P += rail(M, .06, -.44, .098)
    sz = .135
    P += red_dot(M, -.02, sz)
    finish('gun_auto', P, (0, -.66, .072), (0, -.32, .02), (0, .1, sz))


def pulse_rifle():
    bl.reset(); M = mats(); P = []
    P += grip(M)
    P += [B('body', (.062, .4, .1), (0, -.06, .06), M['body'], .025),
          B('glowpanel', (.002, .22, .05), (.032, -.08, .06), M['glow'], 0),
          B('glowpanel2', (.002, .22, .05), (-.032, -.08, .06), M['glow'], 0),
          B('topcut', (.066, .16, .02), (0, -.16, .114), M['metal'], .004),
          barrel('barrel', .015, .12, -.26, .06, M['dark']), barrel('emitter', .026, .05, -.36, .06, M['trim'], 18),
          barrel('emitter2', .02, .02, -.41, .06, M['glow'], 18),
          B('stock', (.05, .17, .08), (0, .21, .05), M['metal'], .02),
          B('cell', (.04, .07, .09), (0, -.12, -.03), M['glow'], .01),
          B('cellcage', (.044, .074, .02), (0, -.12, -.075), M['dark'], .004)]
    P += rail(M, .12, -.06, .112)
    sz = .14
    P += iron_rear(M, .1, sz) + iron_front(M, -.24, sz)
    finish('gun_pulse', P, (0, -.43, .06), (0, -.24, .01), (0, .14, sz))


def scout_rifle():
    bl.reset(); M = mats(); P = []
    P += grip(M)
    P += [B('receiver', (.05, .42, .07), (0, -.08, .055), M['body'], .016),
          B('stock', (.036, .28, .05), (0, .23, .04), M['body'], .012, rot=(-.08, 0, 0)),
          B('cheek', (.04, .12, .03), (0, .2, .075), M['metal'], .008),
          B('butt', (.04, .03, .1), (0, .36, .02), M['dark'], .006),
          barrel('barrel', .012, .4, -.3, .055, M['dark']), barrel('brake', .02, .06, -.68, .055, M['trim'], 12),
          B('mag', (.03, .08, .08), (0, -.1, -.015), M['metal'], .008),
          B('glow', (.002, .3, .01), (.026, -.1, .05), M['glow'], 0), B('glow2', (.002, .3, .01), (-.026, -.1, .05), M['glow'], 0),
          B('bolt', (.05, .012, .012), (-.035, .02, .07), M['trim'], .003)]
    P += rail(M, .08, -.16, .092)
    sz = .13
    P += scope_tube(M, -.02, sz, .17, .019, .026)
    finish('gun_scout', P, (0, -.74, .055), (0, -.32, .0), (0, .1, sz), scoped=True)


def hand_cannon():
    bl.reset(); M = mats(); P = []
    P += grip(M, ang=.38, h=.12)
    P += [B('frame', (.04, .2, .06), (0, -.07, .045), M['body'], .012),
          bl.cyl('cylinder', .038, .075, (0, -.04, .058), M['metal'], 6, rot=(R90, 0, 0), bevel=.004)]
    for i in range(6):
        a = i * math.pi / 3 + .52
        P.append(bl.cyl('flute', .007, .078, (math.cos(a) * .036, -.04, .058 + math.sin(a) * .036), M['dark'], 6, rot=(R90, 0, 0)))
    P += [barrel('barrel', .017, .22, -.08, .07, M['metal']),
          B('shroud', (.04, .22, .03), (0, -.19, .082), M['body'], .008),
          B('shroudglow', (.002, .16, .01), (.021, -.19, .082), M['glow'], 0),
          B('ejector', (.008, .2, .008), (0, -.19, .05), M['dark'], .002),
          B('hammer', (.012, .03, .03), (0, .045, .088), M['trim'], .004)]
    sz = .112
    P += [B('rear_notchL', (.008, .012, .016), (.009, .03, sz - .004), M['dark'], .002),
          B('rear_notchR', (.008, .012, .016), (-.009, .03, sz - .004), M['dark'], .002),
          bl.sphere('rear_dotL', .0022, (.009, .023, sz), M['green'], 6, 4), bl.sphere('rear_dotR', .0022, (-.009, .023, sz), M['green'], 6, 4)]
    P += iron_front(M, -.28, sz, ears=False)
    finish('gun_handcannon', P, (0, -.31, .07), (0, -.02, -.02), (0, .1, sz))


def shotgun():
    bl.reset(); M = mats(); P = []
    P += grip(M)
    P += [B('receiver', (.062, .27, .09), (0, -.05, .052), M['body'], .016),
          B('stock', (.05, .24, .08), (0, .21, .04), M['metal'], .02),
          B('butt', (.054, .03, .1), (0, .335, .035), M['dark'], .008)]
    for x in (-.017, .017):
        P.append(barrel('barrel', .016, .38, -.16, .072, M['metal'], x=x))
    P += [B('pump', (.072, .15, .052), (0, -.35, .03), M['body'], .015)]
    for i in range(5):
        P.append(B('pumprib', (.076, .01, .056), (0, -.29 - i * .03, .03), M['dark'], .002))
    P += [B('shells', (.07, .1, .02), (0, -.06, .1), M['trim'], .005),
          B('glow', (.002, .18, .015), (.032, -.05, .05), M['glow'], 0), B('glow2', (.002, .18, .015), (-.032, -.05, .05), M['glow'], 0),
          B('vrib', (.008, .36, .006), (0, -.36, .092), M['dark'], .001)]
    sz = .1
    P += [B('ghost_base', (.03, .014, .014), (0, .05, sz - .016), M['dark'], .003),
          bl.torus('ghost', .008, .0025, (0, .05, sz), M['dark'], rot=(R90, 0, 0), maj=14, mn=5),
          bl.sphere('bead', .004, (0, -.54, sz), M['green'], 8, 6), B('beadpost', (.004, .006, .008), (0, -.54, sz - .007), M['dark'], 0)]
    finish('gun_shotgun', P, (0, -.56, .072), (0, -.35, -.005), (0, .14, sz))


def sniper():
    bl.reset(); M = mats(); P = []
    P += grip(M)
    P += [B('receiver', (.052, .38, .08), (0, -.04, .05), M['metal'], .012),
          B('chassis', (.06, .3, .05), (0, -.29, .03), M['body'], .012),
          B('chassisglow', (.002, .2, .012), (.031, -.29, .03), M['glow'], 0),
          B('stock', (.046, .32, .06), (0, .27, .04), M['body'], .015),
          B('stockhole', (.05, .12, .02), (0, .26, .025), M['dark'], 0),
          B('cheek', (.044, .12, .03), (0, .22, .085), M['metal'], .008),
          B('butt', (.05, .03, .11), (0, .43, .03), M['dark'], .008),
          barrel('barrel', .015, .58, -.4, .055, M['dark']), barrel('suppressor', .026, .16, -.9, .055, M['metal'], 18),
          B('bolt', (.06, .015, .015), (-.035, .03, .075), M['trim'], .004), bl.sphere('boltknob', .012, (-.068, .03, .075), M['dark'], 10, 6),
          B('mag', (.036, .08, .07), (0, -.08, -.01), M['dark'], .006)]
    for s in (1, -1):
        P.append(B('bipod', (.01, .01, .12), (s * .026, -.58, -.03), M['dark'], .002, rot=(0, s * .2, 0)))
    P += rail(M, .14, -.2, .095)
    sz = .14
    P += scope_tube(M, .02, sz, .3, .024, .034)
    finish('gun_sniper', P, (0, -1.0, .055), (0, -.3, .0), (0, .2, sz), scoped=True)


def rocket():
    bl.reset(); M = mats(); P = []
    P += grip(M)
    P += [barrel('tube', .075, .92, .3, .13, M['body'], 24),
          barrel('bandF', .085, .06, -.48, .13, M['metal'], 24), barrel('bandB', .085, .06, .3, .13, M['metal'], 24),
          barrel('nozzle', .066, .06, .36, .13, M['dark'], 24), barrel('nozzleglow', .05, .01, .39, .13, M['glow'], 24),
          B('grip2', (.03, .05, .1), (0, -.28, .0), M['grip'], .008),
          B('glowring', (.003, .5, .02), (.075, -.15, .13), M['glow'], 0), B('glowring2', (.003, .5, .02), (-.075, -.15, .13), M['glow'], 0),
          B('hazard', (.16, .08, .16), (0, -.36, .13), M['trim'], .02)]
    sz = .23
    P += [B('sightarm', (.012, .03, .03), (0, .0, .21), M['dark'], .003)]
    P += red_dot(M, -.02, sz)
    finish('gun_rocket', P, (0, -.64, .13), (0, -.28, -.02), (0, .1, sz))


def make_paint():
    """Base paint texture for gun_body: subtle machined panels (the shader colour multiplies it)."""
    import numpy as np
    S = 256
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32) / S
    rng = np.random.default_rng(3)
    shade = .93 + .05 * rng.random((S, S))
    shade -= .12 * ((np.abs((xx * 4) % 1 - .5) > .485) | (np.abs((yy * 2) % 1 - .5) > .49))
    img = np.ones((S, S, 4), np.float32); img[..., :3] = np.clip(shade, 0, 1)[..., None]
    im = bpy.data.images.new('gunpaint_c', S, S); im.pixels = img[::-1].ravel()
    sc = bpy.context.scene; sc.render.image_settings.file_format = 'JPEG'; sc.render.image_settings.quality = 90
    im.save_render(os.path.join(bl.TEXTURES, 'gunpaint_c.jpg'))


bl.reset()
make_paint()
for f in (auto_rifle, hand_cannon, scout_rifle, shotgun, sniper, rocket, pulse_rifle):
    f()
