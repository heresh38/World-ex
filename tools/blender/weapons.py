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

Material names are an API (Unreal: USOGunRigComponent::Dress, import_assets.py GUN_WEAR):
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
import voidkit as V
import gunparts as G
from voidkit import prism, plate, lathe, lathe_x
from gunparts import lathe_z

RIGHT = -1      # the gun's right side is -X


def moving_part(name, parts, pivot, parent, parent_pivot=(0, 0, 0), organic=(), cyl_axis=None):
    """Join parts into their own object whose origin sits at `pivot` (gun frame), parented to `parent`.
    The game animates these by name for reloads (mag, bolt, charge, slide, pump, crane, cylinder, hatch, biomass)."""
    from mathutils import Matrix, Vector
    o = K.assemble(name, parts, organic, cyl_axis=cyl_axis)
    o.name = name
    o.data.transform(Matrix.Translation(-Vector(pivot)))
    o.location = Vector(pivot) - Vector(parent_pivot)
    o.parent = parent
    return o


def finish(name, parts, muzzle, fore, sight, optic=(), rail=None, scoped=False, organic=(), cyl_axis=None, keys=None,
           moving=(), loose=()):
    """moving: [(name, parts, pivot) or (name, parts, pivot, parent_name)] animated parts; loose: [(name, parts, pivot)]
    spare props the game hides and clones (x_shell, x_round, x_casing, x_speedloader...)."""
    # Iron sights become their own part ('irons') on guns that take rail optics, so a mounted optic can fold them
    # away (nothing of the gun crowds the optic's window).
    if rail:
        irons = [p for p in parts if p is not None and p.name.split('.')[0] in IRON_PARTS]
        if irons:
            parts = [p for p in parts if p not in irons]
            moving = list(moving) + [('irons', irons, (0, 0, 0))]
    g = K.assemble(name, parts, organic, cyl_axis=cyl_axis)
    made = {}
    for spec in moving:
        nm, pp, pv = spec[:3]
        par = made[spec[3]] if len(spec) > 3 else None
        o = moving_part(nm, pp, pv, par[0] if par else g, par[1] if par else (0, 0, 0), organic, cyl_axis)
        made[nm] = (o, pv)
    for nm, pp, pv in loose:
        moving_part(nm, pp, pv, g, (0, 0, 0), organic, cyl_axis)
    if optic:
        if all(p.name.split('.')[0] in IRON_PARTS for p in optic if p is not None):
            # flip-up / fixed irons standing in for an optic: they are the gun's irons (fold away under a rail optic)
            moving_part('irons', list(optic), (0, 0, 0), g, (0, 0, 0), organic, cyl_axis)
        else:
            o = K.assemble('OPTIC', list(optic)); o.parent = g
    bl.empty('muzzle', muzzle, g); bl.empty('foregrip', fore, g); bl.empty('sight', sight, g)
    if scoped:
        bl.empty('scope', sight, g)
    if rail:
        bl.empty('rail', rail, g)
    if keys:
        keys(g)
    scale_tree(g, GUN_SCALE.get(name, 1.0))
    K.export(name + '.glb')


# Real-world size: these guns were modelled ~1.1-1.2x too large overall (length, height and width alike). Overall
# lengths after the scale, against the real class: assault rifle 94 cm (AK 88, M16 100), carbine 85 (M4 84),
# auto rifle 95, scout 102, DMR 110 (M14 112), bolt-action 115 (105-117), anti-materiel sniper 129 (Barrett 145,
# AWM 120), pump 100 (870 18in 96), hand cannon 33 (6-10in magnum 27-37). Pistols (22-23 cm vs 19-21), revolver
# (27), SMGs (72-76 vs MP5 70), shotgun (89 vs M4 101), HMG (90), rocket launcher (98 vs RPG-7 95) are already right.
# The origin (top of the pistol grip) stays put; every part, pivot and socket scales about it.
# Part names (gunkit.iron_front / iron_rear and the hand-built posts) that make a gun's iron sights.
IRON_PARTS = {'post', 'postL', 'postR', 'postdot', 'front_base', 'front_ear', 'frontpost', 'rear_ring', 'rear_base',
              'rear_earL', 'rear_earR', 'rearblock', 'buis_base', 'fbuis_base', 'fbuis_arm'}

GUN_SCALE = {'gun_rifle': .82, 'gun_carbine': .9, 'gun_auto': .9, 'gun_scout': .92, 'gun_dmr': .9, 'gun_bolt': .85,
             'gun_sniper': .88, 'gun_pump': .86, 'gun_handcannon': .9}


def scale_tree(root, s):
    """Uniform scale of a gun about its origin, baked into the meshes and the children's offsets (no object scale
    left behind, so pivots, sockets and the reload parts' origins stay exact in every exporter)."""
    from mathutils import Matrix
    if abs(s - 1.0) < 1e-6:
        return
    done = set()

    def walk(o, is_root):
        if o.type == 'MESH' and o.data.name not in done:
            o.data.transform(Matrix.Scale(s, 4))
            done.add(o.data.name)
        if not is_root:
            o.location = o.location * s
        for c in o.children:
            walk(c, False)
    walk(root, True)


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
    """The energy line's built-in reflex sight: a clamp on the rail, a hooded window, the emitter behind it. The dot
    floats on the sight line at (0, y - .03, z)."""
    D = M['dark']; P = []
    P.append(prism('rd_base', [(y + .03, z - .034), (y + .03, z - .027), (y + .024, z - .021), (y - .03, z - .021), (y - .03, z - .034)], .034, D, .002))
    for s in (1, -1):                                                # the hood's cheeks, raked back
        P.append(prism('rd_cheek', [(y - .004, z - .022), (y + .006, z + .012), (y - .002, z + .022), (y - .03, z + .022), (y - .03, z - .022)], .0045, D, .0012, x=s * .0195))
    P.append(prism('rd_brow', [(y + .0, z + .0185), (y - .003, z + .0245), (y - .03, z + .0245), (y - .03, z + .0185)], .0435, D, .0012))
    P.append(prism('rd_glass', [(y - .0215, z - .019), (y - .0195, z - .019), (y - .0195, z + .019), (y - .0215, z + .019)], .0345, M['lens'], .0003))
    P.append(lathe('rd_dot', [(y - .0296, 0), (y - .0296, .0015), (y - .0304, .0015), (y - .0304, 0)], M['dot'], z, 0, 10))
    P.append(prism('rd_emitter', [(y + .022, z - .021), (y + .022, z - .012), (y + .012, z - .012), (y + .008, z - .021)], .012, M['metal'], .001))
    P.append(lathe_x('rd_knob', [(0, .0062), (.006, .0062), (.0075, .005), (.0075, 0)], (.017, y + .012, z - .0275), M['metal'], 12, 1))
    G.hexbolts(P, [(y - .012, z - .0275)], .017, M['trim'], .0026)
    return P


def scope_tube(M, y, z, L=.16, r=.022, objective=.03):
    """The energy line's built-in telescope: a turned main tube with an objective bell and an eyepiece, capped turrets,
    two clamped rings on the rail."""
    P = []
    y0, y1 = y + L * .36, y - L * .64                                # eyepiece end, objective end
    ob = objective
    P.append(lathe('scope_tube', [(y0, r * 1.2), (y0 - .004, r * 1.26), (y0 - L * .1, r * 1.26), (y0 - L * .14, r * 1.02), (y0 - L * .2, r), (y1 + L * .3, r),
                                  (y1 + L * .2, ob * .96), (y1 + .006, ob), (y1, ob * .97), (y1, ob * .86), (y1 + .012, ob * .84), (y0 - .01, r * 1.02),
                                  (y0, r * 1.06)], M['metal'], z, 0, 36, closed=True))
    P.append(G.band('scope_eye', y0 + .002, L * .07, r * 1.34, M['grip'], z, 0, .004, 32))
    P.append(G.band('scope_power', y0 - L * .15, L * .05, r * 1.1, M['dark'], z, 0, .0035, 24, .0006))
    P.append(lathe('lens_f', [(y1 + .011, 0), (y1 + .011, ob * .85), (y1 + .013, ob * .85), (y1 + .013, 0)], M['lens'], z, 0, 32))
    P.append(lathe('lens_r', [(y0 - .009, 0), (y0 - .009, r * 1.03), (y0 - .011, r * 1.03), (y0 - .011, 0)], M['lens'], z, 0, 32))
    ty = y - L * .12
    P.append(G.lathe_z('turret_top', [(r - .001, 0), (r - .001, .0105), (r + .004, .0105), (r + .005, .012), (r + .013, .012), (r + .014, .0105), (r + .014, 0)],
                       (0, ty, z), M['dark'], 20))
    P.append(G.lathe_z('turret_cap', [(r + .014, 0), (r + .014, .0112), (r + .018, .0112), (r + .019, .0098), (r + .019, 0)], (0, ty, z), M['trim'], 20))
    for s, m in ((1, M['dark']), (-1, M['metal'])):
        P.append(lathe_x('turret_side', [(r - .001, .0098), (r + .011, .0098), (r + .012, .0085), (r + .012, 0)], (0, ty, z), m, 20, s))
    for yy in (y + L * .14, y - L * .34):
        P.append(G.band('scopering', yy + .007, .014, r + .0042, M['dark'], z, 0, .0046, 24, .001))
        P.append(prism('ringbase', [(yy + .009, z - r - .002), (yy + .009, z - r - .016), (yy - .009, z - r - .016), (yy - .009, z - r - .002)], .03, M['dark'], .0025))
        G.hexbolts(P, [(yy, z - r - .009)], .015, M['trim'], .0024)
    return P


def e_rail(M, y0, y1, z, w=.026):
    return K.rail(M, y0, y1, z, w, M['dark'])


def vents(M, y0, y1, z, x, n=5, h=.02):
    step = (y0 - y1) / n
    return [B('vent', (.004, step * .55, h), (x, y0 - step * (i + .5), z), M['dark'], .0012) for i in range(n)]


def auto_rifle():
    """Energy auto rifle: a ceramic shell over a graphite frame, the emitter stack in a six-bar cage, a cell magazine,
    a skeleton stock."""
    bl.reset(); M = K.energy_mats(); P = []
    zb = .062
    G.grip(P, M['dark'], M['grip'], M['metal'], ang=.28, h=.12, w=.034, z=.004)
    P += K.trigger_group(M, M['dark'], M['trim'], y=-.012, z=.012, L=.072, drop=.05)
    # the frame: lower receiver and the cell's well
    P.append(prism('lower', [(.1, .048), (.1, .02), (.06, .006), (-.055, .006), (-.06, -.012), (-.152, -.012), (-.16, .012), (-.215, .024), (-.215, .048)],
                   .046, M['dark'], .003))
    P.append(plate('well_lip', [(-.058, .0), (-.058, -.014), (-.154, -.014), (-.158, .0)], M['metal'], .021, .0252, .0012))
    # the shell: upper receiver, armour over both flanks, a line of light under it
    P.append(G.loft('upper', [(.15, .046, .098, .0255, (.008, .003)), (-.2, .046, .098, .0265, (.008, .003)), (-.242, .05, .096, .0235, (.008, .003))], M['body']))
    P.append(plate('shell_rear', [(.142, .058), (.142, .0905), (.005, .0905), (-.028, .076), (-.028, .058)], M['body'], .024, .0298, .0018))
    P.append(plate('shell_front', [(-.046, .058), (-.046, .0745), (-.068, .0905), (-.2, .0905), (-.228, .074), (-.228, .058)], M['metal'], .024, .0296, .0018))
    G.glowline(P, 'seam', [(.136, .0535), (-.222, .0535)], .0262, M['glow'], .0026)
    G.slots(P, 'vent', [(-.1 - i * .028, .082, .02, .0048, .55) for i in range(4)], .0296, M['dark'])
    G.hexbolts(P, [(.126, .066), (.02, .066), (-.212, .066)], .0298, M['trim'], .0028)
    G.hexbolts(P, [(.08, .034), (-.19, .034)], .023, M['metal'], .003)
    G.selector(P, .03, .03, .023, M['trim'], 1, ang=.35, L=.02)
    P += [prism('chargeh', [(.148, .099), (.148, .108), (.118, .108), (.112, .099)], .038, M['dark'], .002),
          prism('chargelatch', [(.142, .1), (.142, .1065), (.128, .1065), (.128, .1)], .046, M['trim'], .0012)]
    # the emitter stack in its cage, a fore panel for the off hand
    G.coil(P, 'emitter', -.244, -.458, zb, .0185, M, rings=7, lip_m=M['trim'])
    G.cage(P, 'cage', -.236, -.472, zb, .0325, M['metal'], t=.0045, bars=6, fill=.56, frames=((-.236, .014), (-.352, .007), (-.458, .014)),
           phase=math.pi / 2, frame_m=M['dark'])
    P.append(prism('forepanel', [(-.258, .0315), (-.45, .0315), (-.44, .017), (-.27, .017)], .042, M['body'], .003))
    G.slots(P, 'forecut', [(-.3 - i * .034, .0245, .022, .0045, 0) for i in range(4)], .021, M['dark'])
    # barrel and brake
    V.barrel('barrel', M, -.46, -.612, zb, .0115, P, m=M['dark'], rings=[(-.505, .0146, .012), (-.565, .0146, .012)])
    G.brake(P, 'brake', -.6, zb, .019, .076, M['metal'], M['dark'], 3)
    # the cell
    P += G.box_mag('mag', [(-.066, .01), (-.072, -.09), (-.088, -.15), (-.15, -.15), (-.142, -.09), (-.14, .01)], .034, M['metal'], floor_m=M['dark'],
                   floor=[(-.083, -.146), (-.155, -.146), (-.157, -.162), (-.086, -.162)],
                   window=[(-.094, -.022), (-.12, -.022), (-.126, -.1), (-.1, -.1)], window_m=M['glow'],
                   ribs=[[(-.078, -.004), (-.134, -.004), (-.1345, -.012), (-.0785, -.012)], [(-.089, -.112), (-.141, -.112), (-.143, -.12), (-.091, -.12)]])
    # stock
    G.stock_fixed(P, M['body'], M['metal'], M['grip'], .15, .098, L=.222, drop=.132, w=.04, zb=.022, bolt_m=M['trim'], dark_m=M['dark'])
    P += K.sling_loop(.33, -.026, M['dark']) + K.sling_loop(-.455, .022, M['dark'])
    P += e_rail(M, .1, -.44, .098)
    sz = .135
    finish('gun_auto', P, (0, -.68, .062), (0, -.32, .02), (0, .1, sz), optic=red_dot(M, -.02, sz), rail=(0, -.02, .1075))


def pulse_rifle():
    """Pulse rifle: a short wedge of a carbine: three capacitors behind a window in each flank, a twin-rail emitter, a
    faceted cell ahead of the grip, folding irons."""
    bl.reset(); M = K.energy_mats(); P = []
    zb = .06
    G.grip(P, M['dark'], M['grip'], M['metal'], ang=.28, h=.12, w=.034, z=.004)
    P += K.trigger_group(M, M['dark'], M['trim'], y=-.012, z=.012, L=.072, drop=.05)
    P.append(G.loft('body', [(.14, .016, .1, .03, (.012, .005)), (-.2, .012, .1, .031, (.012, .005)), (-.262, .03, .092, .024, (.01, .004))], M['body']))
    P.append(prism('keel', [(.11, .02), (.07, .006), (-.06, .006), (-.07, .0), (-.17, .0), (-.2, .014)], .05, M['dark'], .003))
    # the capacitor bay: a dark window in each flank, three lit capacitors lying in it
    P.append(plate('bay', [(.03, .034), (.03, .078), (-.17, .078), (-.19, .06), (-.19, .034)], M['dark'], .028, .0316, .001))
    for i in range(3):
        y = .012 - i * .066
        for s in (1, -1):
            P.append(G.tube_('capacitor', y, y - .05, .0085, M['metal'], .056, s * .0315, n=14, ch=.001))
            P.append(G.band('capacitor_glow', y - .023, .004, .0089, M['glow'], .056, s * .0315, .003, 14, .0002))
            for q in (0.0, .044):
                P.append(G.band('cap_end', y - q, .006, .0098, M['metal'], .056, s * .0315, .0098, 14, .0006))
    P.append(plate('bay_frame', [(.04, .028), (.04, .084), (.03, .084), (.03, .034), (-.19, .034), (-.19, .028)], M['metal'], .029, .0336, .0012))
    P.append(plate('shell_top', [(.13, .084), (.13, .094), (-.19, .094), (-.2, .084)], M['body'], .029, .0326, .0012))
    P.append(plate('shell_nose', [(-.198, .03), (-.198, .086), (-.25, .086), (-.258, .07), (-.258, .034), (-.25, .03)], M['metal'], .024, .0312, .0016))
    P.append(plate('rear_panel', [(.128, .034), (.128, .08), (.052, .08), (.052, .034)], M['metal'], .029, .0322, .0016))
    G.slots(P, 'rear_vent', [(.112 - i * .017, .057, .03, .0045, math.pi / 2 - .3) for i in range(3)], .0322, M['dark'])
    G.seamline(P, [(.046, .022), (.046, .096)], .0306, M['dark'])
    G.hexbolts(P, [(.134, .026), (-.185, .09), (-.245, .058)], .0318, M['trim'], .0028)
    # twin-rail emitter
    G.coil(P, 'emitter', -.262, -.37, zb, .0165, M, rings=4, lip_m=M['trim'])
    for a in (math.pi / 2, -math.pi / 2):
        P.append(G.bar('emit_rail', -.262, -.418, .019, .026, a - .42, a + .42, M['metal'], zb, 0, 3))
    P.append(G.band('emit_muzzle', -.398, .03, .0275, M['dark'], zb, 0, .0085, 24, .0012))
    P.append(G.band('emit_lip', -.4265, .0035, .0245, M['trim'], zb, 0, .0055, 24, .0006))
    G.cell(P, 'cell', (0, -.12, .004), .026, .085, M, n=8)
    # a short skeleton stock
    G.stock_folding(P, M['metal'], M['dark'], M['grip'], .14, .098, L=.165, drop=.115, w=.042, bolt_m=M['trim'])
    P += e_rail(M, .12, -.06, .1)
    sz = .14
    optic = []
    G.iron_rear(optic, .1, sz, M['dark'], base_z=.1095)
    G.iron_front(optic, -.24, sz, M['dark'], dot_m=M['green'], base_z=.094, w=.022)
    finish('gun_pulse', P, (0, -.43, .06), (0, -.24, .01), (0, .14, sz), optic=optic, rail=(0, .03, .1095))


def scout_rifle():
    """Scout rifle: a slim receiver, a long barrel between two guide rails with three accelerator rings, a straight bolt,
    a skeleton stock with a cheek rest, its own telescope."""
    bl.reset(); M = K.energy_mats(); P = []
    zb = .055
    G.grip(P, M['dark'], M['grip'], M['metal'], ang=.28, h=.12, w=.034, z=.004)
    P += K.trigger_group(M, M['dark'], M['trim'], y=-.012, z=.012, L=.072, drop=.05)
    P.append(G.loft('receiver', [(.13, .022, .09, .025, (.008, .004)), (-.25, .022, .09, .025, (.008, .004)), (-.305, .03, .08, .02, (.007, .004))], M['body']))
    P.append(prism('lower', [(.1, .024), (.06, .008), (-.05, .008), (-.055, .0), (-.145, .0), (-.15, .012), (-.22, .024)], .042, M['dark'], .003))
    P.append(plate('side_plate', [(.12, .046), (.12, .084), (-.02, .084), (-.04, .066), (-.24, .066), (-.24, .046)], M['metal'], .0235, .0282, .0016))
    G.glowline(P, 'seam', [(-.045, .074), (-.24, .074)], .0256, M['glow'], .0026)
    G.port(P, .03, -.035, .062, .078, .0282, M['dark'], M['metal'], side=-1)
    P += [rod('bolt', (RIGHT * .024, .012, .07), (RIGHT * .056, .024, .058), .0045, M['trim']),
          lathe_x('boltknob', [(0, .004), (.004, .009), (.013, .009), (.017, .004), (.017, 0)], (RIGHT * .056, .024, .058), M['dark'], 14, -1)]
    G.hexbolts(P, [(.1, .056), (-.22, .056)], .0282, M['trim'], .0026)
    G.seamline(P, [(.06, .046), (.06, .084)], .0282, M['dark'])
    G.seamline(P, [(-.26, .028), (-.26, .086), (-.3, .078)], .0252, M['dark'])
    # the barrel: slim, between an upper and a lower guide rail, three accelerator rings
    V.barrel('barrel', M, -.3, -.69, zb, .0105, P, m=M['dark'])
    for a in (math.pi / 2, -math.pi / 2):
        P.append(G.bar('guide', -.3, -.64, .0135, .019, a - .3, a + .3, M['metal'], zb, 0, 2))
    for i, y in enumerate((-.37, -.47, -.57)):
        P.append(G.band('accel', y, .018, .0225, M['dark'], zb, 0, .0095, 24, .0012))
        P.append(G.band('accel_glow', y - .007, .004, .0232, M['glow'], zb, 0, .003, 24, .0003))
    G.brake(P, 'brake', -.675, zb, .018, .068, M['trim'], M['dark'], 3)
    P += G.box_mag('mag', [(-.06, .02), (-.066, -.06), (-.14, -.06), (-.136, .02)], .03, M['metal'], floor_m=M['dark'],
                   floor=[(-.064, -.056), (-.142, -.056), (-.143, -.068), (-.066, -.068)], window=[(-.085, -.005), (-.115, -.005), (-.118, -.045), (-.088, -.045)],
                   window_m=M['glow'])
    G.stock_thumbhole(P, M['body'], M['grip'], .13, .088, .222, .14, .036, G.gp(.28, 0, .004)(.028, .118), cheek_m=M['metal'], bolt_m=M['trim'])
    P += e_rail(M, .08, -.16, .09)
    P += K.sling_loop(.3, -.046, M['dark']) + K.sling_loop(-.3, .02, M['dark'])
    sz = .13
    finish('gun_scout', P, (0, -.74, .055), (0, -.32, .0), (0, .1, sz), optic=scope_tube(M, -.02, sz, .17, .019, .026), scoped=True,
           rail=(0, -.04, .0995))


def hand_cannon():
    """Hand cannon (the hero handgun): a round recoil shield and a humped frame round a six-cell cylinder (banded at
    the rear, fluted ahead of it), a heavy two-tone shroud over the barrel with a ported muzzle block, an ejector
    housing under it, a spur hammer, a rounded guard, a knurled grip with a butt cap and a lanyard ring."""
    bl.reset(); M = K.energy_mats(); P = []
    zc, zb = .058, .07
    BD, MT, DK, TR, GL = M['body'], M['metal'], M['dark'], M['trim'], M['glow']
    g = G.hand_grip(P, M['grip'], .38, .12, .034, z=.004)
    P.append(prism('gripcap', [g(-.023, .118), g(.029, .114), g(.031, .126), g(-.021, .129)], .036, TR, .0015))
    c = g(.004, .133)
    P.append(K.ring('lanyard', .0055, .0014, (0, c[0], c[1]), MT, axis='x', maj=20, mn=8))
    c = g(.002, .034)
    for s in (1, -1):
        P.append(lathe_x('medallion', [(0, .0062), (.0012, .0062), (.002, .005), (.002, 0)], (s * .0168, c[0], c[1]), TR, 18, s))
    G.guard(P, DK, [(-.076, .016), (-.078, -.008), (-.068, -.026), (-.05, -.0335), (-.026, -.0335), (-.01, -.029)], .014, .0062)
    G.trigger(P, TR, -.03, .014, L=.034, w=.0075)
    # the frame: a round shield behind the cylinder, the hump that carries the hammer, the top strap, the standing breech
    P.append(G.disc('recoil_shield', .014, .004, .0415, BD, zc, n=48, ch=.0025))
    P.append(G.rprism('frame_rear', G.chaikin([(.006, .016), (.006, .103), (.03, .103), (.044, .096), (.05, .08), (.066, .064), (.065, .055), (.054, .05),
                                               (.05, .03), (.044, .014)], 1, sharp=(0, 1, 9)), .034, BD, .005))
    P.append(plate('frame_inlay', [(.018, .03), (.018, .084), (.034, .084), (.044, .07), (.044, .04), (.038, .03)], MT, .0165, .0188, .0014))
    P.append(G.loft('frame_top', [(.012, .1005, .11, .015, (.0045, .0008)), (-.1, .1005, .11, .015, (.0045, .0008))], BD))
    P.append(prism('frame_low', [(.006, .008), (.006, .018), (-.084, .018), (-.084, .012), (-.03, .008)], .03, BD, .002))
    P.append(G.rprism('frame_front', [(-.082, .012), (-.082, .11), (-.1, .11), (-.1, .03), (-.092, .012)], .04, BD, .004))
    P.append(plate('crane', [(-.06, .012), (-.06, .024), (-.084, .024), (-.09, .016), (-.084, .012)], MT, .014, .0172, .001, sym=False, side=1))
    P.append(lathe_x('crane_pin', [(0, .0042), (.0016, .0042), (.0022, .003), (.0022, 0)], (.0172, -.078, .018), TR, 14, 1))
    P.append(plate('latch', [(.04, .074), (.04, .062), (.022, .06), (.02, .072)], DK, .017, .0212, .001, sym=False, side=1))
    G.serrations(P, 'latch_grip', .037, 4, .004, .063, .072, .0212, MT, t=.0016, sym=False, side=1)
    G.hexbolts(P, [(.03, .022), (-.091, .09), (-.091, .03)], .0202, TR, .0026)
    # the cylinder: a banded rear with the stop notches, six lands ahead of it (the flutes are the gaps), the cells
    P.append(lathe('cylinder', [(-.002, 0), (-.002, .032), (-.004, .0335), (-.076, .0335), (-.078, .032), (-.078, 0)], MT, zc, 0, 36))
    P.append(G.band('cyl_band', -.003, .027, .0386, MT, zc, 0, .0056, 48, .001))
    for k in range(6):
        a = k * math.pi / 3
        P.append(G.bar('cyl_land', -.03, -.077, .033, .0386, a - .37, a + .37, MT, zc, 0, 4))
        P.append(G.bar('cyl_notch', -.012, -.021, .0382, .039, a + .5 - .055, a + .5 + .055, DK, zc, 0, 1))
        b = a + math.pi / 6
        P.append(lathe('cell_face', [(-.0012, 0), (-.0012, .0048), (-.0022, .0048), (-.0022, 0)], GL, zc + math.sin(b) * .0235, math.cos(b) * .0235, 10))
        P.append(G.band('cell_rim', -.0008, .0018, .0064, DK, zc + math.sin(b) * .0235, math.cos(b) * .0235, .0018, 12, .0003))
    P.append(G.band('cyl_ring', -.0295, .003, .0392, TR, zc, 0, .003, 48, .0005))
    P.append(G.tube_('cylaxis', .008, -.086, .007, DK, zc, n=14))
    # the barrel under its shroud: ceramic over a steel lower flat, a ported muzzle block, the ejector housing
    V.barrel('barrel', M, -.09, -.306, zb, .0135, P, m=MT, bore=.0075)
    P.append(G.loft('shroud', [(-.098, .05, .11, .02, (.008, .004)), (-.262, .05, .11, .02, (.008, .004)), (-.27, .052, .1085, .019, (.008, .004))], BD))
    P.append(plate('shroud_flat', [(-.104, .0525), (-.104, .0705), (-.246, .0705), (-.258, .062), (-.258, .0525)], MT, .0195, .0222, .0014))
    G.glowline(P, 'seam', [(-.11, .074), (-.243, .074)], .0202, GL, .0022)
    G.slots(P, 'shroud_vent', [(-.132 - i * .03, .0905, .02, .0048, .5) for i in range(4)], .02, DK)
    P.append(G.loft('muzzleblock', [(-.268, .0515, .109, .0188, (.0075, .004)), (-.29, .0515, .109, .0188, (.0075, .004)), (-.3, .056, .105, .0162, (.006, .004))], MT))
    G.slots(P, 'comp', [(-.276 - i * .009, .092, .014, .0036, math.pi / 2 - .35) for i in range(2)], .0188, DK)
    P.append(G.band('crown', -.3005, .005, .0162, TR, zb, 0, .0042, 28, .0006))
    P.append(prism('rib', [(.008, .11), (.008, .1114), (-.292, .1114), (-.296, .11)], .0105, DK, .0006))
    P.append(G.rprism('ejshroud', [(-.1, .034), (-.1, .052), (-.236, .052), (-.246, .046), (-.246, .039), (-.24, .034)], .017, DK, .005))
    P.append(lathe('ejrod_tip', [(-.244, 0), (-.244, .0046), (-.252, .0046), (-.254, .0034), (-.254, 0)], TR, .043, 0, 14))
    G.hexbolts(P, [(-.118, .044), (-.222, .044)], .0085, MT, .0022)
    # the hammer: a curved spur with a chequered pad
    P.append(G.rprism('hammer', G.ribbon(G.smooth([(.03, .078), (.04, .097), (.054, .11), (.07, .1165)], 2), [.015, .013, .0105, .008]), .013, MT, .0018, 2))
    P.append(prism('hammer_pad', [(.056, .1125), (.071, .1195), (.073, .1165), (.059, .1095)], .0145, TR, .0008))
    sz = .112
    P.append(prism('rear_block', [(.038, .1095), (.038, sz - .004), (.02, sz - .004), (.016, .1095)], .024, DK, .001))
    for s, nm in ((1, 'rear_notchL'), (-1, 'rear_notchR')):
        P.append(prism(nm, [(.037, sz - .006), (.037, sz + .003), (.027, sz + .003), (.025, sz - .006)], .0075, DK, .001, x=s * .0085))
        P.append(lathe('rear_dot', [(.0372, 0), (.0372, .0018), (.0368, .0018), (.0368, 0)], M['green'], sz - .0015, s * .0085, 8))
    P.append(prism('front_base', [(-.262, .1105), (-.268, .1145), (-.29, .1145), (-.294, .1105)], .011, DK, .0008))
    P.append(prism('post', [(-.272, .114), (-.277, sz + .0045), (-.2835, sz + .0045), (-.286, .114)], .0036, DK, .0005))
    P.append(lathe('postdot', [(-.2768, 0), (-.2768, .0014), (-.2772, .0014), (-.2772, 0)], M['green'], sz + .0026, 0, 8))
    finish('gun_handcannon', P, (0, -.31, .07), (0, -.02, -.02), (0, .1, sz))


def shotgun():
    """Shotgun: two bored emitter barrels side by side under a vented rib, a ribbed pump, a receiver with a rack of
    charge cartridges on top, a solid stock."""
    bl.reset(); M = K.energy_mats(); P = []
    zb = .072
    G.grip(P, M['dark'], M['grip'], M['metal'], ang=.28, h=.12, w=.034, z=.004)
    P += K.trigger_group(M, M['dark'], M['trim'], y=-.012, z=.012, L=.072, drop=.05)
    P.append(G.loft('receiver', [(.09, .01, .097, .031, (.01, .005)), (-.15, .01, .097, .031, (.01, .005)), (-.195, .03, .094, .034, (.008, .005))], M['body']))
    P.append(plate('side_plate', [(.08, .03), (.08, .086), (-.04, .086), (-.06, .07), (-.175, .07), (-.175, .03)], M['metal'], .0295, .0346, .0018))
    G.glowline(P, 'seam', [(-.065, .078), (-.175, .078)], .0318, M['glow'], .0026)
    G.port(P, -.02, -.1, .042, .064, .0346, M['dark'], M['trim'], side=-1)
    G.hexbolts(P, [(.065, .04), (-.16, .04)], .0346, M['trim'], .003)
    for i in range(4):                                               # the rack of charge cartridges along the top
        P.append(G.tube_('cartridge', -.02 - i * .03, -.044 - i * .03, .0085, M['trim'], .105, n=12, ch=.0015))
        P.append(G.band('cartridge_glow', -.03 - i * .03, .004, .0089, M['glow'], .105, 0, .002, 12, .0002))
    P.append(prism('rack', [(-.01, .097), (-.01, .1), (-.15, .1), (-.15, .097)], .03, M['dark'], .001))
    # barrels, rib, the tube under them, the pump
    for x in (-.0175, .0175):
        P.append(G.tube_('barrel', -.16, -.548, .0162, M['metal'], zb, x, bore=.0115, n=24))
        P.append(G.band('muzzle_ring', -.53, .012, .0175, M['trim'], zb, x, .003, 24, .0006))
    P.append(prism('yoke', [(-.19, .05), (-.19, .094), (-.215, .094), (-.215, .05)], .074, M['dark'], .003))
    P.append(prism('vrib', [(-.2, .0885), (-.2, .095), (-.545, .095), (-.545, .0885)], .01, M['dark'], .001))
    for i in range(8):
        P.append(prism('ribpost', [(-.24 - i * .04, .084), (-.24 - i * .04, .0885), (-.25 - i * .04, .0885), (-.25 - i * .04, .084)], .007, M['dark'], .0005))
    P.append(G.tube_('magtube', -.19, -.5, .0125, M['dark'], .04, n=20))
    P.append(G.band('tubecap', -.488, .016, .0142, M['metal'], .04, 0, .0142, 20, .0015))
    P.append(G.rloft('pump', [(-.27, .012, .058, .037, 4.0), (-.3, .008, .06, .039, 4.0), (-.4, .008, .06, .039, 4.0), (-.432, .012, .058, .036, 4.0)], M['body'], n=20))
    for i in range(5):
        P.append(plate('pumprib', [(-.292 - i * .028, .014), (-.292 - i * .028, .054), (-.3 - i * .028, .054), (-.3 - i * .028, .014)], M['dark'], .037, .0412, .0008))
    # stock
    P.append(G.rprism('stock', [(.09, .094), (.2, .09), (.32, .08), (.33, .07), (.33, -.03), (.3, -.042), (.17, .0), (.09, .018)], .05, M['metal'], .012))
    P.append(plate('stock_inlay', [(.12, .034), (.12, .08), (.29, .07), (.3, -.02), (.19, .012)], M['body'], .024, .0262, .002))
    P.append(G.rprism('butt', [(.33, .074), (.346, .07), (.346, -.036), (.33, -.04)], .054, M['grip'], .005))
    sz = .1
    P.append(prism('ghost_base', [(.058, sz - .022), (.058, sz - .009), (.042, sz - .009), (.042, sz - .022)], .03, M['dark'], .002))
    P.append(lathe('ghost', [(.053, .0056), (.053, .0105), (.047, .0105), (.047, .0056)], M['dark'], sz, 0, 20, closed=True))
    P.append(prism('beadpost', [(-.537, .095), (-.537, sz - .003), (-.543, sz - .003), (-.543, .095)], .004, M['dark'], .0006))
    P.append(lathe('bead', [(-.536, 0), (-.536, .0036), (-.544, .0036), (-.544, 0)], M['green'], sz, 0, 10))
    finish('gun_shotgun', P, (0, -.56, .072), (0, -.35, -.005), (0, .14, sz))


def sniper():
    """Sniper rifle: a steel action in a ceramic chassis, an accelerator stack that runs out into a long fluted barrel
    and a heavy focusing brake, a bipod, a skeleton stock, a long telescope."""
    bl.reset(); M = K.energy_mats(); P = []
    zb = .055
    G.grip(P, M['dark'], M['grip'], M['metal'], ang=.28, h=.12, w=.034, z=.004)
    P += K.trigger_group(M, M['dark'], M['trim'], y=-.012, z=.012, L=.072, drop=.05)
    P.append(G.loft('receiver', [(.15, .014, .09, .026, (.008, .004)), (-.2, .014, .09, .026, (.008, .004)), (-.235, .02, .086, .023, (.008, .004))], M['metal']))
    P.append(prism('chassis', [(-.17, .006), (-.17, .05), (-.44, .05), (-.455, .04), (-.455, .012), (-.44, .006)], .06, M['body'], .004))
    G.slots(P, 'chassis_cut', [(-.225 - i * .05, .028, .03, .01, 0) for i in range(5)], .03, M['dark'])
    G.glowline(P, 'chassis_seam', [(-.185, .044), (-.44, .044)], .0302, M['glow'], .0024)
    P.append(plate('action_plate', [(.14, .03), (.14, .084), (.04, .084), (.02, .07), (-.15, .07), (-.17, .052), (-.17, .03)], M['body'], .0245, .0296, .0018))
    G.port(P, .0, -.07, .06, .08, .0296, M['dark'], M['trim'], side=-1)
    P += [rod('bolt', (RIGHT * .024, .03, .075), (RIGHT * .06, .04, .062), .005, M['trim']),
          lathe_x('boltknob', [(0, .005), (.005, .0115), (.017, .0115), (.022, .005), (.022, 0)], (RIGHT * .06, .04, .062), M['dark'], 16, -1)]
    G.hexbolts(P, [(.12, .05), (-.15, .046), (-.3, .016), (-.42, .016)], .0298, M['trim'], .003)
    G.seamline(P, [(.08, .03), (.08, .084)], .0296, M['dark'])
    G.seamline(P, [(-.31, .008), (-.31, .049)], .0302, M['dark'])
    # barrel: accelerator stack, then a long fluted tube, then the brake
    G.coil(P, 'accel', -.235, -.47, zb, .0205, M, rings=6, lip_m=M['trim'])
    for a in (math.pi / 2,):
        P.append(G.bar('accel_top', -.235, -.47, .022, .028, a - .5, a + .5, M['metal'], zb, 0, 3))
    V.barrel('barrel', M, -.47, -.875, zb, .0135, P, m=M['dark'], rings=[(-.49, .0185, .02), (-.84, .0165, .016)])
    for k in range(6):                                               # flutes: six raised lands between them
        a = math.pi / 6 + k * math.pi / 3
        P.append(G.bar('land', -.515, -.82, .013, .0152, a - .2, a + .2, M['metal'], zb, 0, 1))
    P.append(lathe('focus', [(-.86, 0), (-.86, .021), (-.875, .027), (-.99, .027), (-1.005, .031), (-1.028, .031), (-1.03, .029), (-1.03, .014),
                             (-.99, .014), (-.99, 0)], M['metal'], zb, 0, 28))
    for i in range(3):
        P.append(prism('focus_port', G.capsule(-.9 - i * .032, zb, .016, .03, math.pi / 2), .056, M['dark'], .0004))
    P.append(G.band('focus_glow', -.992, .005, .0315, M['glow'], zb, 0, .003, 28, .0004))
    P.append(G.band('focus_lip', -1.024, .004, .0322, M['trim'], zb, 0, .004, 28, .0005))
    # bipod
    P.append(prism('bipodclamp', [(-.535, .008), (-.535, .03), (-.565, .03), (-.565, .008)], .052, M['dark'], .003))
    for s in (1, -1):
        P.append(rod('bipod', (s * .022, -.55, .02), (s * .046, -.526, -.1), .0052, M['dark']))
        P.append(rod('bipod_ext', (s * .046, -.526, -.1), (s * .05, -.522, -.118), .0038, M['metal']))
        P.append(lathe_x('bipodfoot', [(-.008, .009), (.008, .009), (.008, 0)], (s * .05, -.522, -.122), M['grip'], 10, 1))
    P += G.box_mag('mag', [(-.05, .012), (-.052, -.06), (-.122, -.06), (-.12, .012)], .036, M['dark'], floor_m=M['metal'],
                   floor=[(-.05, -.056), (-.124, -.056), (-.125, -.068), (-.052, -.068)], window=[(-.07, -.008), (-.1, -.008), (-.1, -.044), (-.07, -.044)],
                   window_m=M['glow'])
    G.stock_adjustable(P, M['body'], M['dark'], M['grip'], .15, .09, .28, .135, .044, .016, bolt_m=M['trim'])
    P.append(lathe_z('monopod', [(-.05, 0), (-.05, .009), (-.046, .009), (-.044, .0055), (0, .0055), (0, 0)], (0, .392, -.01), M['dark'], 12))
    P += e_rail(M, .14, -.2, .09)
    sz = .14
    finish('gun_sniper', P, (0, -1.03, .055), (0, -.3, .0), (0, .2, sz), optic=scope_tube(M, .02, sz, .3, .024, .034), scoped=True,
           rail=(0, -.03, .0995))


def rocket():
    """Rocket launcher: a launch tube between a flared muzzle bell and a lit venturi, armour saddles along it, a sight
    rail on an arm, a grip frame and a fore grip under it, a shoulder rest."""
    bl.reset(); M = K.energy_mats(); P = []
    zc = .13
    G.grip(P, M['dark'], M['grip'], M['metal'], ang=.28, h=.12, w=.034, z=.004)
    P += K.trigger_group(M, M['dark'], M['trim'], y=-.012, z=.012, L=.072, drop=.05)
    P.append(lathe('tube', [(.3, .058), (.3, .074), (.296, .076), (-.56, .076), (-.58, .084), (-.622, .09), (-.626, .087), (-.626, .07), (-.58, .064), (-.56, .06)],
                   M['body'], zc, 0, 40, closed=True))
    P.append(lathe('tube_bore', [(.31, .0585), (-.6, .0605), (-.6, .058), (.31, .056)], M['dark'], zc, 0, 32, closed=True))
    for y, L, m in ((.3, .05, M['metal']), (-.42, .05, M['metal']), (-.1, .02, M['dark']), (.1, .02, M['dark'])):
        P.append(G.band('band', y, L, .084, m, zc, 0, .009, 40, .002))
    P.append(G.band('bell_lip', -.616, .008, .0925, M['trim'], zc, 0, .004, 40, .0008))
    P.append(lathe('nozzle', [(.3, .07), (.33, .066), (.372, .084), (.376, .081), (.376, .072), (.34, .054), (.3, .056)], M['dark'], zc, 0, 36, closed=True))
    P.append(G.band('nozzle_glow', .338, .008, .0585, M['glow'], zc, 0, .004, 32, .0004))
    for s in (1, -1):                                                # armour saddles and their lines of light
        a = 0.0 if s > 0 else math.pi
        P.append(G.bar('saddle', .05, -.38, .0765, .0835, a - .5, a + .5, M['body'], zc, 0, 4))
        P.append(G.bar('saddle_glow', -.06, -.3, .0835, .0845, a - .028, a + .028, M['glow'], zc, 0, 1))
    P.append(G.band('hazard', -.33, .06, .0855, M['trim'], zc, 0, .003, 40, .001))
    for k in range(6):
        a = k * math.pi / 3 + math.pi / 6
        P.append(lathe('band_bolt', [(-.44, 0), (-.44, .0034), (-.45, .0034), (-.45, 0)], M['trim'], zc + math.sin(a) * .0865, math.cos(a) * .0865, 6))
    # the grip frame, fore grip, shoulder rest
    P.append(prism('mount', [(.07, .056), (.07, .012), (.03, .004), (-.06, .004), (-.07, .012), (-.24, .03), (-.24, .056)], .04, M['dark'], .004))
    P.append(G.rprism('grip2', [(-.258, .058), (-.262, -.012), (-.27, -.058), (-.308, -.062), (-.3, .058)], .032, M['grip'], .009))
    P.append(prism('rest', [(.18, .058), (.18, .03), (.28, .01), (.3, .014), (.3, .058)], .05, M['metal'], .005))
    P.append(G.rprism('rest_pad', [(.2, .034), (.282, .012), (.286, .002), (.204, .024)], .054, M['grip'], .004))
    G.hexbolts(P, [(.05, .03), (-.2, .04)], .02, M['trim'], .003)
    # sight arm and rail
    sz = .23
    P.append(prism('sightarm', [(.05, .2), (.05, .208), (-.09, .208), (-.09, .2), (-.03, .2), (-.02, .192), (.02, .192), (.03, .2)], .016, M['dark'], .003))
    P += K.rail(M, .06, -.1, .205, .022, M['dark'])
    finish('gun_rocket', P, (0, -.64, .13), (0, -.28, -.02), (0, .1, sz), optic=red_dot(M, -.02, sz + .015), rail=(0, -.02, .2145))


def smg():
    """Submachine gun: a short chamfered upper, the emitter in a perforated shroud ending in a suppressor, a straight
    cell, a hand stop, a twin-rod stock."""
    bl.reset(); M = K.energy_mats(); P = []
    zb = .066
    G.grip(P, M['dark'], M['grip'], M['metal'], ang=.22, h=.11, w=.034, z=.004)
    P += K.trigger_group(M, M['dark'], M['trim'], y=-.012, z=.012, L=.072, drop=.05)
    P.append(G.loft('upper', [(.07, .044, .097, .025, (.008, .003)), (-.16, .044, .097, .025, (.008, .003)), (-.195, .048, .094, .0225, (.007, .003))], M['body']))
    P.append(prism('lower', [(.05, .046), (.05, .01), (-.062, .01), (-.066, -.008), (-.13, -.008), (-.134, .012), (-.17, .02), (-.17, .046)], .046, M['dark'], .003))
    P.append(plate('side_plate', [(.062, .054), (.062, .09), (-.05, .09), (-.066, .076), (-.155, .076), (-.155, .054)], M['metal'], .0235, .0288, .0016))
    G.glowline(P, 'seam', [(.058, .0495), (-.158, .0495)], .0256, M['glow'], .0024)
    G.slots(P, 'vent', [(-.085 - i * .024, .084, .016, .0042, .6) for i in range(3)], .0288, M['dark'])
    G.hexbolts(P, [(.05, .066), (-.145, .066)], .0288, M['trim'], .0026)
    G.selector(P, .02, .03, .023, M['trim'], 1, ang=.3, L=.018)
    P.append(prism('cocking', [(.04, .0975), (.04, .106), (.012, .106), (.006, .0975)], .034, M['trim'], .0015))
    # shroud, emitter, suppressor
    G.coil(P, 'emitter', -.196, -.302, zb, .0165, M, rings=4)
    G.cage(P, 'shroud', -.19, -.305, zb, .0285, M['metal'], t=.004, bars=8, fill=.58, frames=((-.19, .012), (-.295, .012)), phase=math.pi / 2, frame_m=M['dark'])
    V.barrel('barrel', M, -.3, -.37, zb, .0105, P, m=M['dark'])
    G.can(P, 'can', -.36, zb, .0195, .118, M['metal'], M['trim'], bands=2)
    # the cell and the hand stop
    P += G.box_mag('mag', [(-.072, .02), (-.078, -.15), (-.126, -.15), (-.122, .02)], .03, M['dark'], floor_m=M['metal'],
                   floor=[(-.075, -.146), (-.129, -.146), (-.13, -.16), (-.077, -.16)], window=[(-.092, -.02), (-.108, -.02), (-.112, -.13), (-.096, -.13)],
                   window_m=M['glow'])
    P.append(G.rprism('vgrip', [(-.23, .038), (-.236, -.048), (-.268, -.054), (-.266, .038)], .028, M['grip'], .008))
    P.append(prism('vgrip_cap', [(-.234, -.046), (-.27, -.052), (-.271, -.06), (-.236, -.055)], .03, M['dark'], .0015))
    # stock: two rods and a pad
    for x, z in ((.016, .085), (-.016, .085)):
        P.append(G.tube_('stockbar', .27, .07, .0055, M['dark'], z, x, n=12))
    P.append(G.tube_('stockbar', .27, .05, .0055, M['dark'], .03, 0, n=12))
    P.append(prism('stock_yoke', [(.262, .096), (.276, .096), (.276, .018), (.262, .018)], .046, M['metal'], .003))
    P.append(G.rprism('stockpad', [(.276, .1), (.292, .096), (.292, .014), (.276, .01)], .044, M['grip'], .005))
    P += e_rail(M, .06, -.28, .097, .022)
    sz = .135
    finish('gun_smg', P, (0, -.48, .066), (0, -.25, -.03), (0, .08, sz), optic=red_dot(M, -.04, sz), rail=(0, -.04, .1065))


def sidearm():
    """Sidearm: a steel frame with a tang over the hand and a rounded guard, a ceramic slide shell in stepped flats
    (a dark rail, a steel panel, cut serrations, a port), a crowned emitter nose, one line of light, three-dot sights,
    a flush base plate."""
    bl.reset(); M = K.energy_mats(); P = []
    BD, MT, DK, TR, GL = M['body'], M['metal'], M['dark'], M['trim'], M['glow']
    zb = .07
    g = G.hand_grip(P, DK, .3, .11, .034, z=.004)
    P.append(plate('grip_panel', [g(-.015, .032), g(.017, .028), g(.019, .06), g(.016, .096), g(-.013, .099), g(-.017, .062)], M['grip'], .011, .0179, .0012))
    P.append(G.rprism('grip_base', [g(.0282, .1085), g(-.0202, .1125), g(-.0206, .1215), g(.0288, .1175)], .034, MT, .004))
    G.guard(P, DK, [(-.076, .018), (-.078, -.008), (-.068, -.026), (-.05, -.0335), (-.026, -.0335), (-.012, -.029)], .014, .006)
    G.trigger(P, TR, -.03, .014, L=.033, w=.007)
    P.append(G.rprism('frame', G.chaikin([(.034, .047), (.054, .0462), (.053, .041), (.042, .033), (.0355, .016), (.033, .004), (-.026, .006), (-.03, .016),
                                          (-.1, .016), (-.108, .024), (-.165, .024), (-.165, .047)], 1, sharp=(0, 5, 6, 7, 8, 9, 10, 11)), .032, MT, .0035))
    # the slide shell: the body, a dark rail along its foot, a steel panel, the serrations, the port
    P.append(G.loft('slide', [(.038, .05, .088, .0175, (.007, .002)), (-.14, .05, .088, .0175, (.007, .002)), (-.164, .053, .0855, .0152, (.006, .002)),
                              (-.172, .057, .0825, .0132, (.005, .002))], BD))
    P.append(plate('slide_rail', [(.036, .0505), (.036, .0575), (-.16, .0575), (-.166, .054), (-.166, .0505)], DK, .0165, .0192, .001))
    P.append(plate('slide_panel', [(.006, .0615), (.006, .0785), (-.066, .0785), (-.08, .0695), (-.15, .0695), (-.154, .0615)], MT, .0165, .0196, .0014))
    G.glowline(P, 'seam', [(-.086, .075), (-.15, .075)], .0178, GL, .0022)
    G.serrations(P, 'serration', .033, 6, .0042, .0605, .0805, .0177, DK, rake=.0045)
    G.port(P, -.012, -.05, .0645, .0755, .0196, DK, TR, side=-1)
    P.append(prism('toprib', [(.018, .088), (.018, .0902), (-.146, .0902), (-.154, .088)], .0105, DK, .0006))
    P.append(prism('readout', [(.0385, .056), (.0402, .083), (.036, .083), (.036, .056)], .024, DK, .0008))
    P.append(prism('charge_bar', [(.0407, .066), (.0411, .072), (.04, .072), (.04, .066)], .012, GL, .0003))
    # the emitter nose: a crowned bore in a stepped collar
    G.muzzle(P, 'nose', -.166, -.2, zb, .0145, DK, .0062)
    P.append(G.band('nose_step', -.17, .01, .0158, MT, zb, 0, .003, 24, .0008))
    P.append(G.band('nose_lip', -.1955, .003, .0152, TR, zb, 0, .003, 24, .0004))
    # controls on the left, the accessory rail under the dust cover
    P.append(plate('slidestop', [(-.024, .047), (-.07, .045), (-.076, .04), (-.034, .041)], DK, .015, .0184, .0008, sym=False, side=1))
    P.append(lathe_x('stop_pin', [(0, .0034), (.0014, .0034), (.002, .0024), (.002, 0)], (.0184, -.07, .0428), TR, 12, 1))
    G.selector(P, .024, .038, .016, TR, 1, ang=.25, L=.017, r=.0045)
    P.append(lathe_x('cellrelease', [(0, .0044), (.003, .0044), (.0036, .0034), (.0036, 0)], (.016, -.017, .012), DK, 14, 1))
    P.append(prism('railbox', [(-.108, .024), (-.108, .012), (-.16, .012), (-.164, .024)], .028, DK, .002))
    G.slots(P, 'railcut', [(-.122 - i * .014, .0175, .006, .008, 0) for i in range(3)], .014, MT)
    G.hexbolts(P, [(-.09, .034)], .016, TR, .0024)
    sz = .1
    P.append(prism('rear_blade', [(.036, .0895), (.036, sz - .004), (.022, sz - .004), (.018, .0895)], .026, DK, .001))
    for s, nm in ((1, 'rearL'), (-1, 'rearR')):
        P.append(prism(nm, [(.035, sz - .006), (.035, sz + .003), (.025, sz + .003), (.023, sz - .006)], .0075, DK, .001, x=s * .0088))
        P.append(lathe('rdot', [(.0352, 0), (.0352, .0018), (.0348, .0018), (.0348, 0)], M['green'], sz - .002, s * .0088, 8))
    P.append(prism('front_base', [(-.132, .0895), (-.138, .0935), (-.156, .0935), (-.16, .0895)], .011, DK, .0008))
    P.append(prism('post', [(-.142, .093), (-.146, sz + .003), (-.152, sz + .003), (-.154, .093)], .0036, DK, .0005))
    P.append(lathe('postdot', [(-.1458, 0), (-.1458, .0014), (-.1462, .0014), (-.1462, 0)], M['green'], sz + .0012, 0, 8))
    finish('gun_sidearm', P, (0, -.2, .07), (0, -.02, -.02), (0, .09, sz), rail=(0, -.06, .088))


def heavy_mg():
    """Heavy machine gun: six barrels on a spindle in two clamp rings, a finned drive motor, an armoured housing with
    a charge drum hung under it, a carry handle, a stub stock."""
    bl.reset(); M = K.energy_mats(); P = []
    zb = .07
    G.grip(P, M['dark'], M['grip'], M['metal'], ang=.2, h=.12, w=.034, z=.004)
    P += K.trigger_group(M, M['dark'], M['trim'], y=-.012, z=.012, L=.072, drop=.05)
    P.append(G.loft('housing', [(.1, .004, .12, .05, (.016, .008)), (-.2, .004, .12, .05, (.016, .008)), (-.245, .016, .112, .044, (.014, .008))], M['body']))
    P.append(plate('armour', [(.09, .03), (.09, .104), (-.03, .104), (-.06, .08), (-.19, .08), (-.22, .056), (-.22, .03)], M['metal'], .0485, .0546, .0022))
    G.glowline(P, 'seam', [(-.065, .092), (-.2, .092)], .0508, M['glow'], .003)
    G.slots(P, 'vent', [(-.09 - i * .03, .104, .022, .0055, .55) for i in range(4)], .0508, M['dark'])
    G.port(P, -.02, -.1, .05, .074, .0546, M['dark'], M['trim'], side=-1)
    G.hexbolts(P, [(.075, .045), (.075, .09), (-.205, .045)], .0546, M['trim'], .0034)
    # motor, spindle, barrels, clamp rings, muzzle plate
    P.append(lathe('motor', [(-.24, 0), (-.24, .05), (-.31, .05), (-.318, .043), (-.318, 0)], M['metal'], zb, 0, 32))
    for i in range(5):
        P.append(G.band('motor_fin', -.25 - i * .013, .005, .054, M['dark'], zb, 0, .006, 32, .0006))
    P.append(G.tube_('spindle', -.31, -.6, .011, M['metal'], zb, n=16))
    for k in range(6):
        a = k * math.pi / 3
        x, z = math.cos(a) * .03, zb + math.sin(a) * .03
        P.append(G.tube_('rbarrel', -.3, -.655, .0108, M['dark'], z, x, bore=.0058, n=14))
        P.append(G.band('rmuzzle', -.64, .012, .0122, M['metal'], z, x, .0028, 14, .0005))
    for y, r, m in ((-.4, .047, M['dark']), (-.54, .05, M['metal'])):
        P.append(G.band('clamp', y, .022, r, m, zb, 0, r - .039, 32, .0015))
        for k in range(6):
            a = k * math.pi / 3 + math.pi / 6
            P.append(G.bar('spoke', y - .004, y - .018, .012, r - .006, a - .1, a + .1, m, zb, 0, 1))
    P.append(G.band('clamp_glow', -.553, .004, .0508, M['glow'], zb, 0, .003, 32, .0004))
    # the drum under the housing
    for s in (1, -1):
        P.append(lathe_x('drum', [(0, .09), (.03, .09), (.036, .084), (.036, .062), (.04, .058), (.04, 0)], (0, -.06, -.07), M['metal'], 40, s))
        P.append(lathe_x('drumcap', [(.04, .056), (.044, .052), (.044, .02), (.047, .016), (.047, 0)], (0, -.06, -.07), M['trim'], 24, s))
        for k in range(8):
            a = k * math.pi / 4
            G.hexbolts(P, [(-.06 + math.cos(a) * .073, -.07 + math.sin(a) * .073)], .036, M['dark'], .0034, sym=False, side=s)
    P.append(lathe_x('drumglow', [(-.0018, .0912), (.0018, .0912), (.0018, .088), (-.0018, .088)], (0, -.06, -.07), M['glow'], 40, 1, closed=True))
    P.append(lathe_x('drumband', [(-.008, .0905), (.008, .0905), (.008, .086), (-.008, .086)], (0, -.06, -.07), M['dark'], 40, 1, closed=True))
    P.append(prism('drum_hanger', [(-.02, .01), (-.02, -.0), (-.1, -.0), (-.1, .01)], .06, M['dark'], .003))
    # carry handle, stock, fore grip
    P += [prism('carry', [(-.02, .162), (-.02, .178), (-.22, .178), (-.22, .162)], .018, M['dark'], .004),
          prism('carryL', [(-.02, .12), (-.02, .17), (-.036, .17), (-.044, .12)], .018, M['dark'], .003),
          prism('carryF', [(-.196, .12), (-.204, .17), (-.22, .17), (-.22, .12)], .018, M['dark'], .003)]
    P.append(G.rprism('carry_wrap', [(-.07, .159), (-.07, .181), (-.17, .181), (-.17, .159)], .024, M['grip'], .006))
    G.stock_stub(P, M['body'], M['dark'], M['grip'], .1, .062, L=.14, r=.024, w=.064, h=.11)
    P.append(G.rprism('fgrip', [(-.28, .004), (-.286, -.068), (-.322, -.074), (-.32, .004)], .032, M['grip'], .009))
    P.append(prism('fgrip_cap', [(-.284, -.066), (-.324, -.072), (-.325, -.08), (-.286, -.075)], .034, M['dark'], .0015))
    sz = .21
    P += K.rail(M, .08, -.06, .17, .022, M['dark'])
    P.append(prism('rail_riser', [(.08, .12), (.08, .17), (.06, .17), (.05, .12)], .02, M['dark'], .003))
    finish('gun_hmg', P, (0, -.66, .07), (0, -.3, -.04), (0, .1, sz), optic=red_dot(M, .0, sz), rail=(0, .01, .1795))


def energy_rifle():
    """Energy rifle (the exotic): a reactor bulb with cooling rings behind an open cradle of four tines; a bare core
    of light runs through shrinking focus rings to the emitter."""
    bl.reset(); M = K.energy_mats(); P = []
    zc = .07
    G.grip(P, M['dark'], M['grip'], M['metal'], ang=.25, h=.12, w=.034, z=.004)
    P += K.trigger_group(M, M['dark'], M['trim'], y=-.012, z=.012, L=.072, drop=.05)
    P.append(lathe('reactor', [(.13, 0), (.13, .036), (.11, .052), (.06, .06), (-.02, .058), (-.07, .046), (-.085, .034), (-.085, 0)], M['body'], zc, 0, 36))
    for i in range(4):
        P.append(G.band('cooling', .1 - i * .026, .01, .062 - i * .0006, M['metal'], zc, 0, .008, 36, .001))
    P.append(G.band('reactor_glow', -.06, .006, .052, M['glow'], zc, 0, .004, 36, .0004))
    G.coil(P, 'core', -.08, -.37, zc, .0145, M, rings=9, core=.0105, ring_m=M['metal'])
    for k in range(4):                                               # the cradle: four tines, drawn in toward the emitter
        a = math.pi / 4 + k * math.pi / 2
        for i, (y0, y1, r0, r1) in enumerate(((-.07, -.19, .05, .058), (-.185, -.3, .04, .047), (-.295, -.385, .03, .036))):
            P.append(G.bar('tine', y0, y1, r0, r1, a - .2, a + .2, M['body'] if i != 1 else M['metal'], zc, 0, 2, taper=.8))
    for i, (y, r) in enumerate(((-.12, .045), (-.19, .039), (-.26, .033), (-.33, .027))):
        P.append(G.band('focus', y, .012, r, M['trim'] if i % 2 else M['dark'], zc, 0, r - .0155, 32, .0012))
    P.append(lathe('emitter', [(-.36, .013), (-.36, .03), (-.385, .03), (-.41, .021), (-.412, .019), (-.412, .013)], M['metal'], zc, 0, 28, closed=True))
    P.append(G.band('emit_glow', -.405, .004, .0135, M['glow'], zc, 0, .0135, 20, 0))
    # the spine: a fin over the reactor carrying the sight rail
    P.append(prism('fin', [(.09, .124), (.09, .14), (-.08, .14), (-.3, .112), (-.3, .104), (-.08, .124)], .008, M['body'], .002))
    P.append(prism('sightrail', [(.05, .12), (.05, .14), (-.05, .14), (-.05, .12)], .022, M['dark'], .003))
    G.stock_frame(P, M['metal'], M['grip'], .12, .1, L=.17, drop=.1, w=.044, zb=.024, comb=.03, bolt_m=M['trim'])
    P.append(prism('saddle', [(.08, .024), (.04, .006), (-.07, .006), (-.09, .024)], .05, M['dark'], .004))
    G.cell(P, 'cell', (0, -.06, .016), .026, .05, M, n=8)
    P.append(G.rprism('fgrip', [(-.2, .03), (-.206, -.04), (-.238, -.046), (-.236, .03)], .03, M['grip'], .008))
    sz = .165
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
    """Assault rifle (our own pattern): a milled steel receiver under a flat, fluted cover with an aperture sight at
    its rear; a walnut forend with a finger groove under a pierced steel heat shield; the gas block carries the hooded
    front sight at the forend's nose, the bare barrel runs on to a pronged flash hider; a straight, forward-raked
    magazine with pressed ribs; a walnut stock with a steel butt plate and a lightening slot."""
    bl.reset(); M = K.kinetic_mats(); S, PK, W, PO, RB, OD = M['steel'], M['park'], M['wood'], M['poly'], M['rubber'], M['odg']
    zb = .06; P = []
    P.append(prism('receiver', [(.165, .03), (.165, .084), (-.215, .084), (-.215, .026), (-.166, .026), (-.166, .006), (-.078, .006), (-.078, .026), (.02, .026),
                                (.02, .03)], .044, S, .0022))
    P.append(G.loft('topcover', [(.168, .084, .106, .0205, (.006, .0005)), (-.2, .084, .106, .0205, (.006, .0005)), (-.215, .084, .1, .0195, (.005, .0005))], PK))
    G.slots(P, 'cover_flute', [(-.01, .0945, .27, .0042, 0)], .0205, RB)
    P.append(prism('cover_latch', [(.176, .088), (.176, .1), (.166, .102), (.166, .088)], .016, S, .0015))
    P.append(plate('side_step', [(.152, .036), (.152, .078), (.04, .078), (.024, .064), (-.2, .064), (-.2, .036)], S, .021, .0242, .0012))
    P.append(plate('magwell_flare', [(-.08, .004), (-.08, .024), (-.164, .024), (-.168, .004)], S, .021, .0246, .001))
    G.seamline(P, [(.02, .036), (.02, .078)], .0242, RB)
    G.hexbolts(P, [(-.205, .032), (-.205, .076), (-.186, .032), (.156, .04), (.156, .078), (-.06, .032)], .0222, S, .0024, n=14)
    G.cross_pins(P, [(.1, .046), (.064, .046), (-.034, .046)], .044, S, .0024)
    G.selector(P, .046, .052, .0242, S, 1, ang=.55, L=.024, r=.006)
    # the bolt carrier seen in its slot on the right, the charging handle
    P.append(plate('boltslot', [(.01, .066), (.01, .08), (-.132, .08), (-.132, .066)], RB, .0195, .0246, .0006, sym=False, side=-1))
    BOLT = [plate('carrier', [(.005, .0675), (.005, .0785), (-.127, .0785), (-.127, .0675)], PK, .012, .0238, .0012, sym=False, side=-1),
            rod('charging', (RIGHT * .02, -.128, .074), (RIGHT * .046, -.128, .074), .0048, S),
            lathe_x('chknob', [(0, .0048), (.003, .0072), (.011, .0072), (.013, .0048), (.013, 0)], (RIGHT * .043, -.128, .074), S, 12, -1)]
    # sights: an aperture at the cover's rear, a hooded post on the gas block
    G.iron_rear(P, .09, .1195, S, base_z=.106, w=.03)
    P.append(prism('gasblock', [(-.434, .044), (-.434, .106), (-.468, .106), (-.478, .09), (-.478, .044)], .03, S, .003))
    G.hexbolts(P, [(-.456, .052)], .015, S, .0026, sym=False, side=1, n=14)
    G.iron_front(P, -.455, .1195, S, base_z=.104, w=.024)
    # the forend: walnut below with a finger groove, a pierced steel shield over the gas tube, steel ferrules
    P.append(G.sloft('hg_lower', [(-.262, .03, .078, .027, 4.5), (-.3, .026, .08, .0295, 4.5), (-.38, .026, .08, .0295, 4.5), (-.43, .034, .078, .026, 4.5)], W, n=20, sub=3))
    G.slots(P, 'hg_groove', [(-.345, .052, .12, .0065, 0)], .0293, RB, lift=.0008)
    P.append(G.loft('hg_upper', [(-.264, .08, .1075, .019, (.008, .0005)), (-.43, .08, .1075, .019, (.008, .0005))], PK))
    G.slots(P, 'hg_vent', [(-.284 - i * .0225, .0935, .012, .011, 0) for i in range(6)], .019, RB)
    P += [prism('ferrule_r', [(-.256, .024), (-.256, .088), (-.268, .088), (-.268, .024)], .06, S, .002),
          prism('ferrule_f', [(-.424, .03), (-.424, .084), (-.436, .084), (-.436, .03)], .056, S, .002),
          G.tube_('gastube', -.262, -.44, .0085, S, .093, n=16)]
    # barrel and its pronged hider
    V.barrel('barrel', M, -.215, -.64, zb, .0095, P, m=S, rings=[(-.53, .0115, .012)])
    G.hider(P, 'hider', -.63, zb, .0128, .06, S, 4, bore=.0056)
    P.append(G.band('hider_nut', -.632, .008, .0138, PK, zb, 0, .003, 6, .0006))
    # grip, guard, trigger, magazine catch
    G.grip(P, OD, RB, None, ang=.32, h=.115, w=.031, z=.024, swell=.005)
    G.guard(P, PO, [(-.082, .02), (-.083, -.006), (-.074, -.018), (-.058, -.0225), (-.03, -.0225), (-.014, -.018)], .012, .005)
    G.trigger(P, S, -.046, .024, L=.03)
    P.append(prism('magcatch', [(-.066, .016), (-.066, -.004), (-.078, -.008), (-.08, .016)], .012, S, .002))
    # the magazine: straight, raked forward, pressed ribs, a polymer floor
    mp = [(-.085, .02), (-.119, -.125), (-.185, -.125), (-.149, .02)]
    MAG = G.box_mag('magbody', mp, .03, S, floor_m=PO,
                    floor=[(-.116, -.121), (-.188, -.121), (-.192, -.136), (-.12, -.136)],
                    ribs=[[(-.094 - k * .0078, -.012 - k * .033), (-.142 - k * .0078, -.012 - k * .033), (-.1435 - k * .0078, -.019 - k * .033),
                           (-.0955 - k * .0078, -.019 - k * .033)] for k in range(3)])
    MAG.append(plate('magspine', [(-.112, -.004), (-.122, -.004), (-.151, -.118), (-.141, -.118)], S, .014, .0162, .0005))
    # the stock: walnut, a straight comb, a lightening slot, a steel butt plate
    P.append(G.sloft('stock', [(.163, .03, .086, .02, 4.5), (.2, .024, .085, .019, 3.2), (.3, .0, .081, .0195, 3.0), (.41, -.046, .075, .021, 3.2),
                               (.445, -.06, .071, .021, 3.6)], W, n=24, sub=4))
    G.slots(P, 'stock_slot', [(.335, .022, .09, .016, -.3)], .0188, RB, lift=.0012)
    P.append(G.rloft('buttplate', [(.444, -.061, .072, .0215, 3.6), (.452, -.06, .071, .0212, 3.6), (.455, -.056, .067, .0195, 3.2)], S, n=24))
    P.append(prism('tang', [(.24, .084), (.24, .0885), (.165, .0885), (.165, .084)], .026, S, .002))
    P.append(prism('tang_low', [(.2, .022), (.2, .028), (.165, .03), (.165, .024)], .024, S, .0015))
    P += K.sling_loop(.36, -.034, S) + K.sling_loop(-.43, .024, S, x=.03)
    P += K.rail(M, -.278, -.392, .1075, .02, PK)
    sz = .1195
    finish('gun_rifle', P, (0, -.69, zb), (0, -.345, .012), (0, .06, sz), rail=(0, -.335, .117),
           moving=[('mag', MAG, (0, -.149, .02)), ('bolt', BOLT, (RIGHT * .049, -.128, .074))])


def carbine():
    """Carbine: a flat-top upper on a slab-sided lower, an eight-bar free-float handguard, a collapsing stock, a
    pronged flash hider, folding irons."""
    bl.reset(); M = K.kinetic_mats(); S, PK, PO, RB = M['steel'], M['park'], M['poly'], M['rubber']
    zb = .066; P = []
    P.append(prism('lower', [(.1, .046), (.1, .022), (.074, .014), (.03, .014), (.03, .018), (-.04, .018), (-.046, -.006), (-.05, -.03), (-.124, -.036),
                             (-.128, -.004), (-.138, .02), (-.138, .046)], .034, PK, .002))
    P.append(plate('well_flare', [(-.05, -.014), (-.052, -.034), (-.125, -.04), (-.128, -.018)], PK, .016, .0196, .001))
    P.append(G.loft('upper', [(.1, .046, .09, .0165, (.005, .001)), (-.136, .046, .09, .0165, (.005, .001))], PK))
    P.append(plate('upper_cheek', [(.092, .052), (.092, .084), (.01, .084), (-.006, .074), (-.128, .074), (-.128, .052)], PK, .015, .0182, .0012))
    G.port(P, -.004, -.056, .06, .0765, .0182, M['rubber'], None, side=-1, door_m=PK)
    BOLT = [plate('boltface', [(-.006, .0615), (-.006, .075), (-.054, .075), (-.054, .0615)], S, .008, .0172, .0008, sym=False, side=-1)]
    P += [prism('deflector', [(.05, .062), (.03, .078), (.022, .078), (.026, .06)], .008, PK, .001, x=RIGHT * .019),
          lathe_x('fwdassist', [(0, .0075), (.008, .0075), (.0095, .006), (.0095, 0)], (RIGHT * .0165, .075, .07), PK, 16, -1)]
    CHARGE = [prism('chandle', [(.128, .0815), (.128, .0905), (.1, .0905), (.096, .0815)], .03, PK, .0015),
              prism('chlatch', [(.124, .083), (.124, .089), (.108, .089), (.108, .083)], .04, S, .001)]
    # the stock on its tube
    G.stock_tube(P, PK, PO, RB, S, .1, .065, L=.25, r=.0155, w=.036)
    P += K.sling_loop(.31, .05, S, x=.02)
    # grip, trigger, controls
    G.grip(P, PO, RB, None, ang=.33, h=.11, w=.03, z=.016, swell=.004)
    P += K.trigger_group(M, PK, S, y=-.005, z=.016, L=.058, drop=.046)
    G.cross_pins(P, [(.08, .035), (-.118, .035)], .034, S, .0026)
    G.selector(P, .05, .032, .017, S, 1, ang=.4, L=.02)
    P += [lathe_x('magrelease', [(0, .0046), (.003, .0046), (.0038, .0036), (.0038, 0)], (RIGHT * .017, -.045, .032), S, 14, -1),
          plate('boltcatch', [(-.03, .046), (-.03, .034), (-.05, .034), (-.05, .046)], S, .016, .0195, .0008, sym=False, side=1)]
    G.hexbolts(P, [(.06, .068), (-.1, .062)], .0182, S, .0024)
    # the handguard: eight bars on three frames, a rail down the top
    G.cage(P, 'handguard', -.136, -.432, zb, .029, PK, t=.004, bars=8, fill=.6, frames=((-.134, .018), (-.276, .008), (-.42, .012)), phase=math.pi / 2)
    P.append(lathe('barrelnut', [(-.128, 0), (-.128, .022), (-.142, .022), (-.142, 0)], S, zb, 0, 12, sharp=20))
    P += K.rail(M, .1, -.43, .09, .022, PK)
    # barrel, gas block and tube, flash hider
    V.barrel('barrel', M, -.13, -.535, zb, .0085, P, m=S, rings=[(-.36, .0125, .024), (-.5, .0105, .014)])
    P.append(G.tube_('gastube', -.14, -.36, .003, S, zb + .017, n=10))
    G.hider(P, 'flashhider', -.53, zb, .0112, .056, S, 4)
    # magazine
    MAG = G.box_mag('magbody', [(-.058, .012), (-.06, -.08), (-.074, -.17), (-.088, -.205), (-.152, -.198), (-.136, -.162), (-.122, -.08), (-.118, .012)],
                    .022, PK, floor_m=PO, floor=[(-.085, -.2), (-.156, -.193), (-.158, -.206), (-.088, -.214)],
                    ribs=[[(-.07, -.01), (-.078, -.01), (-.094, -.185), (-.086, -.185)], [(-.092, -.01), (-.1, -.01), (-.12, -.185), (-.112, -.185)],
                          [(-.108, -.01), (-.114, -.01), (-.14, -.18), (-.134, -.18)]])
    MAG.append(G.tube_('magtop', -.064, -.09, .0042, M['brass'], .015, n=12))
    sz = .1335
    optic = []
    G.iron_rear(optic, .07, sz, PK, base_z=.0995)
    G.iron_front(optic, -.41, sz, PK, base_z=.0995)
    finish('gun_carbine', P, (0, -.585, zb), (0, -.3, .028), (0, .1, sz), optic=optic, rail=(0, -.02, .0995),
           moving=[('mag', MAG, (0, -.088, .012)), ('charge', CHARGE, (0, .112, .086)), ('bolt', BOLT, (RIGHT * .01, -.03, .068))])


def bolt_rifle():
    """Bolt-action precision rifle: a round steel action bedded in a moulded stock (a deep forend with the barrel
    floating in its channel, a thumbhole butt with an adjustable cheek piece and a spaced pad), bottom metal with a
    detachable box, a heavy fluted barrel with a three-port brake, a folded bipod."""
    bl.reset(); M = K.kinetic_mats(); S, PK, OD, RB = M['steel'], M['park'], M['odg'], M['rubber']
    zb = .077; P = []
    # the stock: forend and action bed in one, the butt, the limb that closes the thumbhole
    P.append(G.sloft('forend', [(-.53, .04, .066, .019, 4.0), (-.5, .032, .0715, .0245, 4.5), (-.32, .028, .0725, .0275, 4.5), (-.16, .022, .0725, .0285, 4.5),
                                (-.05, .018, .066, .0285, 4.5), (.06, .018, .062, .027, 4.5), (.13, .026, .062, .0245, 4.0)], OD, n=24, sub=4))
    P.append(prism('channel', [(-.142, .069), (-.142, .0742), (-.526, .0742), (-.526, .069)], .034, RB, .0005))
    G.slots(P, 'forendslot', [(-.24 - i * .06, .05, .036, .009, 0) for i in range(5)], .0283, PK, lift=.0008)
    P.append(G.sloft('butt', [(.11, .03, .064, .024, 4.0), (.16, .03, .086, .0225, 3.4), (.22, .028, .098, .022, 3.2), (.34, -.02, .099, .0225, 3.2),
                              (.44, -.078, .098, .0235, 3.6), (.472, -.094, .094, .0235, 4.0)], OD, n=24, sub=4))
    P.append(G.rprism('limb', [(.044, -.076), (.07, -.074), (.42, -.07), (.456, -.086), (.45, -.1), (.07, -.094), (.044, -.092)], .03, OD, .008))
    P.append(G.rprism('cheek', [(.2, .1), (.212, .115), (.39, .115), (.4, .1)], .042, RB, .007))
    for yy in (.24, .36):
        P.append(lathe_z('cheekpost', [(-.016, 0), (-.016, .004), (0, .004), (0, 0)], (0, yy, .102), S, 10))
    P.append(lathe_x('cheekknob', [(0, .0105), (.007, .0105), (.009, .0085), (.009, 0)], (.0215, .3, .07), PK, 16, 1))
    P.append(G.rloft('buttspacer', [(.4715, -.095, .095, .0242, 4.0), (.4765, -.095, .095, .0242, 4.0)], S, n=24))
    P.append(G.rloft('buttpad', [(.4765, -.094, .094, .0245, 4.0), (.49, -.09, .09, .024, 4.0), (.494, -.084, .084, .022, 3.5)], RB, n=24))
    P.append(lathe_z('monopod', [(-.04, 0), (-.04, .009), (-.034, .009), (-.032, .006), (0, .006), (0, 0)], (0, .41, -.096), PK, 12))
    G.hexbolts(P, [(-.06, .042), (.09, .042), (-.2, .042)], .0284, S, .003)
    # the action: receiver, port, lug, rail; the bolt with its shroud, bent handle and knob
    P.append(lathe('receiver', [(.13, 0), (.13, .019), (.126, .021), (-.136, .021), (-.14, .019), (-.14, 0)], S, zb, 0, 28))
    P.append(plate('port', [(.03, zb - .002), (.03, zb + .014), (-.04, zb + .014), (-.04, zb - .002)], RB, .0165, .0214, .0008, sym=False, side=-1))
    P.append(prism('recoillug', [(-.124, .04), (-.124, .07), (-.136, .07), (-.136, .04)], .03, S, .002))
    P.append(plate('boltstop', [(.085, zb - .004), (.085, zb + .006), (.06, zb + .006), (.056, zb - .004)], S, .0195, .0232, .0008, sym=False, side=1))
    BOLT = [G.tube_('bolt', .05, -.05, .0125, PK, zb, n=16), G.tube_('shroud', .16, .125, .016, S, zb, n=20),
            G.band('shroudring', .13, .005, .0172, S, zb, 0, .003, 20, .0006),
            lathe('cockpiece', [(.172, 0), (.172, .006), (.16, .009), (.16, 0)], PK, zb, 0, 12),
            rod('boltroot', (RIGHT * .01, .112, zb + .002), (RIGHT * .03, .114, zb - .006), .0062, S),
            rod('boltarm', (RIGHT * .03, .114, zb - .006), (RIGHT * .058, .12, zb - .03), .0048, S),
            lathe_x('boltknob', [(0, .0045), (.004, .0098), (.012, .012), (.019, .0105), (.023, .0055), (.023, 0)], (RIGHT * .054, .1205, zb - .0305), PK, 16, -1)]
    P += K.rail(M, .12, -.13, .097, .022, PK)
    # the barrel: heavy, six lands, the brake
    V.barrel('barrel', M, -.14, -.78, zb, .0148, P, m=S, rings=[(-.165, .0185, .03)])
    for k in range(6):
        a = math.pi / 6 + k * math.pi / 3
        P.append(G.bar('land', -.2, -.72, .0142, .017, a - .22, a + .22, S, zb, 0, 1))
    G.brake(P, 'brake', -.775, zb, .021, .09, S, RB, 3, bore=.008)
    P.append(G.band('brakering', -.778, .006, .0222, PK, zb, 0, .003, 24, .0006))
    # bottom metal: the guard, the trigger, the box and its release
    P.append(prism('bottommetal', [(.0, .0125), (.0, .0205), (-.2, .0205), (-.21, .0165), (-.2, .0125)], .037, S, .0015))
    G.guard(P, S, [(-.08, .016), (-.081, -.008), (-.072, -.022), (-.056, -.028), (-.024, -.028), (-.008, -.022)], .012, .0052)
    G.trigger(P, S, -.04, .02, L=.03)
    P += G.box_mag('mag', [(-.086, .02), (-.086, -.035), (-.094, -.045), (-.152, -.045), (-.158, -.035), (-.158, .02)], .033, M['poly'], floor_m=PK,
                   floor=[(-.09, -.042), (-.154, -.042), (-.155, -.05), (-.091, -.05)],
                   ribs=[[(-.1, .008), (-.106, .008), (-.106, -.036), (-.1, -.036)], [(-.132, .008), (-.138, .008), (-.138, -.036), (-.132, -.036)]])
    P.append(prism('magrel', [(-.074, .006), (-.074, -.006), (-.086, -.006), (-.086, .006)], .012, S, .002))
    P.append(prism('bipodclamp', [(-.485, .014), (-.485, .034), (-.515, .034), (-.515, .014)], .044, PK, .003))
    for s in (1, -1):
        P += [G.tube_('bipodleg', -.49, -.69, .0055, PK, .012, s * .014, n=10), G.tube_('bipodext', -.68, -.74, .0042, S, .012, s * .014, n=10),
              lathe('bipodfoot', [(-.737, 0), (-.737, .008), (-.752, .008), (-.752, 0)], RB, .012, s * .014, 10)]
    # the grip
    G.grip(P, OD, RB, PK, ang=.2, h=.118, w=.034, z=.022, swell=.005)
    P += K.sling_loop(.3, -.104, S) + K.sling_loop(-.5, .02, S, x=.03)
    ROUND = [lathe('rd_case', [(.03, 0), (.03, .0058), (.028, .0062), (-.02, .0062), (-.032, .0042), (-.032, 0)], M['brass'], .3, 0, 12),
             lathe('rd_nose', [(-.032, 0), (-.032, .0042), (-.044, .003), (-.05, .0012), (-.05, 0)], M['steel'], .3, 0, 12)]
    finish('gun_bolt', P, (0, -.865, zb), (0, -.36, .02), (0, .2, .14), rail=(0, -.005, .1065),
           moving=[('bolt', BOLT, (0, .05, zb))], loose=[('x_round', ROUND, (0, 0, .3))])


def service_pistol():
    """Service pistol: a polymer frame with a tang, an undercut and a rounded guard, a railed dust cover; a steel
    slide in stepped flats with cut serrations front and rear, an ejection port over the barrel hood, an extractor; a
    crowned barrel and guide rod; a slide stop, take-down lever and magazine release; three-dot sights; a magazine
    with a toe on its base plate."""
    bl.reset(); M = K.kinetic_mats(); S, PK, PO, PA, RB = M['steel'], M['park'], M['poly'], M['paint'], M['rubber']
    P = []
    g = G.hand_grip(P, PO, .3, .1, .03, z=.022, ext=.01)
    P.append(plate('grip_panel', [g(-.015, .03), g(.017, .026), g(.019, .058), g(.016, .1), g(-.013, .103), g(-.017, .06)], RB, .01, .0158, .001))
    P.append(G.rprism('frame', G.chaikin([(.036, .05), (.056, .0492), (.055, .044), (.044, .037), (.0375, .03), (.036, .018), (-.022, .018), (-.028, .022),
                                          (-.1, .022), (-.106, .03), (-.158, .03), (-.16, .05)], 1, sharp=(0, 5, 6, 7, 8, 9, 10, 11)), .03, PO, .0035))
    G.slots(P, 'railcut', [(-.116 - i * .013, .032, .005, .006, 0) for i in range(3)], .015, PK)
    G.guard(P, PO, [(-.086, .026), (-.088, .002), (-.078, -.012), (-.06, -.018), (-.03, -.018), (-.012, -.013)], .0135, .0058)
    G.trigger(P, PK, -.044, .024, L=.03)
    SLIDE = [G.loft('slide', [(.04, .048, .079, .0142, (.0055, .001)), (-.146, .048, .079, .0142, (.0055, .001)), (-.16, .05, .0765, .0128, (.005, .001))], S),
             plate('slide_rail', [(.039, .0485), (.039, .0575), (-.152, .0575), (-.158, .053), (-.158, .0485)], S, .0135, .0153, .0008),
             plate('slide_flat', [(.039, .0595), (.039, .073), (-.104, .073), (-.118, .0595)], S, .0135, .0152, .0009)]
    G.serrations(SLIDE, 'serration', .034, 7, .0042, .0605, .072, .0152, PK, rake=.003)
    G.serrations(SLIDE, 'serration', -.072, 4, .0042, .0605, .072, .0152, PK, rake=.003)
    SLIDE.append(plate('ejport', [(-.01, .0635), (-.01, .0775), (-.05, .0775), (-.05, .0635)], RB, .011, .0156, .0004, sym=False, side=-1))
    SLIDE.append(prism('ejport_top', [(-.012, .0786), (-.012, .0793), (-.048, .0793), (-.048, .0786)], .012, RB, .0003, x=RIGHT * .004))
    SLIDE.append(plate('extractor', [(-.002, .066), (-.002, .0705), (-.03, .0705), (-.034, .068), (-.03, .066)], PK, .0146, .0164, .0005, sym=False, side=-1))
    P += [prism('hood', [(-.014, .065), (-.014, .0785), (-.046, .0785), (-.046, .065)], .016, PK, .001, x=RIGHT * .003),
          G.tube_('guiderod', -.15, -.1605, .0042, PK, .0545, n=12),
          plate('slidestop', [(-.004, .0475), (-.05, .0465), (-.064, .0405), (-.058, .0385), (-.046, .0425), (-.008, .0425)], S, .0148, .0172, .0006, sym=False, side=1),
          plate('takedown', [(-.079, .045), (-.079, .039), (-.092, .039), (-.092, .045)], S, .0148, .0172, .0006, sym=False, side=1),
          lathe_x('magrelease', [(0, .0044), (.003, .0044), (.0036, .0034), (.0036, 0)], (.015, -.012, .017), PK, 12, 1)]
    G.muzzle(P, 'crown', -.14, -.163, .062, .0068, PK, .0045, dark_m=RB)
    G.serrations(P, 'stop_grip', -.006, 4, .003, .0432, .0468, .0172, PK, t=.0012, sym=False, side=1)
    G.cross_pins(P, [(-.016, .04), (.02, .04)], .03, S, .0024)
    sz = .0835
    SLIDE.append(prism('rear_base', [(.037, .079), (.037, .0815), (.024, .0815), (.02, .079)], .026, S, .001))
    for s, nm in ((1, 'rearL'), (-1, 'rearR')):
        SLIDE.append(prism(nm, [(.0365, sz - .0045), (.0365, sz + .002), (.027, sz + .002), (.025, sz - .0045)], .0085, S, .0008, x=s * .0078))
        SLIDE.append(lathe('rdot', [(.0367, 0), (.0367, .0017), (.0363, .0017), (.0363, 0)], PA, sz - .0015, s * .0078, 8))
    SLIDE.append(prism('frontpost', [(-.138, .079), (-.142, sz + .002), (-.149, sz + .002), (-.153, .079)], .0036, S, .0006))
    SLIDE.append(lathe('fdot', [(-.1418, 0), (-.1418, .0016), (-.1422, .0016), (-.1422, 0)], PA, sz, 0, 8))
    # the magazine: steel body inside the grip, a polymer base with a toe, the top round
    MAG = [prism('magbody', [g(-.0105, .01), g(.0185, .01), g(.0185, .116), g(-.0105, .118)], .021, S, .0015),
           G.rprism('magbase', [g(-.0202, .1145), g(.0282, .1105), g(.029, .121), g(-.0245, .1265)], .03, PO, .0035)]
    t = g(-.002, .012)
    MAG.append(G.tube_('magtop', t[0] + .012, t[0] - .012, .0045, M['brass'], t[1], n=10))
    top = g(.004, .01)
    finish('gun_pistol', P, (0, -.165, .062), (0, -.02, -.035), (0, .07, sz), rail=(0, -.05, .078),
           moving=[('mag', MAG, (0, top[0], top[1])), ('slide', SLIDE, (0, -.06, .062))])


def pump_shotgun():
    """Pump shotgun: a steel receiver with its ejection port and the loading port and lifter underneath; a barrel
    under a vent rib over the magazine tube, a barrel band and a knurled magazine cap; a walnut fore-end with ribs
    all round on two action bars; a walnut stock with a slim wrist, a falling comb, a pistol grip and a spaced pad;
    a saddle of shells."""
    bl.reset(); M = K.kinetic_mats(); S, PK, W, RB, BR = M['steel'], M['park'], M['wood'], M['rubber'], M['brass']
    shell = bl.mat('gun_shell', '#8c1a1a', 0, .55)
    zb = .08; P = []
    P.append(G.loft('receiver', [(.09, .03, .1, .021, (.007, .003)), (-.15, .03, .1, .021, (.007, .003)), (-.172, .034, .096, .0185, (.006, .003))], PK))
    P.append(plate('receiver_flat', [(.082, .038), (.082, .09), (-.146, .09), (-.152, .084), (-.152, .038)], PK, .0195, .0222, .0012))
    G.seamline(P, [(.034, .038), (.034, .09)], .0222, RB)
    G.port(P, -.012, -.088, .061, .088, .0222, RB, S, side=-1)
    P.append(prism('loadport', [(-.028, .0285), (-.028, .0315), (-.112, .0315), (-.112, .0285)], .03, RB, .0006))
    P.append(prism('lifter', [(-.036, .0272), (-.036, .0296), (-.1, .0296), (-.106, .0272)], .022, S, .0005))
    P.append(prism('topgroove', [(.085, .1), (.085, .102), (-.145, .102), (-.145, .1)], .012, S, .0006))
    P.append(G.tube_('barrel', -.16, -.72, .0115, S, zb, bore=.0095, n=24))
    P.append(G.band('muzzle_ring', -.708, .012, .0125, S, zb, 0, .003, 24, .0008))
    P.append(prism('ventrib', [(-.165, .0945), (-.165, .0975), (-.715, .0975), (-.715, .0945)], .008, S, .0006))
    for i in range(10):
        P.append(prism('ribpost', [(-.188 - i * .05, .0895), (-.188 - i * .05, .0945), (-.193 - i * .05, .0945), (-.193 - i * .05, .0895)], .004, S, .0004))
    P.append(G.tube_('magtube', -.16, -.66, .0125, S, .046, n=20))
    P.append(lathe('magcap', [(-.655, 0), (-.655, .0145), (-.684, .0145), (-.69, .011), (-.69, 0)], S, .046, 0, 20))
    for i in range(3):
        P.append(G.band('capring', -.66 - i * .007, .003, .0153, PK, .046, 0, .002, 20, .0004))
    # the barrel band: a ring on the barrel, a ring on the tube, the web and its screw
    P.append(G.band('band_barrel', -.6, .018, .0146, S, zb, 0, .0032, 24, .001))
    P.append(G.band('band_tube', -.6, .018, .0156, S, .046, 0, .0032, 24, .001))
    P.append(prism('band_web', [(-.6, .058), (-.6, .069), (-.618, .069), (-.618, .058)], .013, S, .001))
    P.append(lathe_x('band_screw', [(0, .003), (.0015, .003), (.0022, .002), (.0022, 0)], (.0065, -.609, .0635), PK, 12, 1))
    # the fore-end on its bars: a swelled walnut sleeve, ribs that run all round it
    PUMP = [G.sloft('forend', [(-.268, .03, .064, .024, 3.5), (-.285, .022, .068, .029, 4.0), (-.36, .02, .068, .03, 4.0), (-.44, .022, .068, .029, 4.0),
                               (-.456, .03, .064, .024, 3.5)], W, n=20, sub=3)]
    for i in range(9):
        y = -.297 - i * .0165
        PUMP.append(G.rloft('forend_rib', [(y, .0188, .0692, .0312, 4.0), (y - .0075, .0188, .0692, .0312, 4.0)], W, n=20))
    for s in (1, -1):
        PUMP.append(prism('actionbar', [(-.14, .047), (-.14, .053), (-.27, .053), (-.27, .047)], .003, S, .0006, x=s * .0165))
    # the stock: wrist, comb, butt; the pistol grip under the receiver's tail; spacer and pad
    P.append(G.sloft('stock', [(.084, .032, .099, .0205, 5.0), (.12, .03, .097, .0185, 3.2), (.19, .02, .093, .0185, 2.7), (.3, -.018, .082, .0195, 2.7),
                               (.4, -.054, .07, .0205, 3.0), (.432, -.064, .064, .0205, 3.6)], W, n=24, sub=4))
    P.append(G.rprism('stock_grip', G.chaikin([(.03, .034), (.004, -.03), (.012, -.088), (.04, -.1), (.07, -.09), (.098, -.02), (.128, .032), (.09, .045)], 2,
                                              sharp=(0, 7)), .037, W, .012, 4))
    P.append(plate('grip_checker', [(.024, -.038), (.06, -.042), (.052, -.08), (.03, -.082)], PK, .0145, .0189, .001))
    P.append(prism('gripcap', [(.013, -.0885), (.041, -.1005), (.069, -.0905), (.068, -.0965), (.041, -.1065), (.011, -.0945)], .03, S, .0015))
    P.append(G.rloft('buttspacer', [(.4315, -.065, .065, .0212, 3.6), (.4355, -.065, .065, .0212, 3.6)], S, n=24))
    P.append(G.rloft('buttpad', [(.4355, -.064, .064, .0215, 3.6), (.447, -.062, .062, .0212, 3.6), (.451, -.057, .057, .0195, 3.2)], RB, n=24))
    G.guard(P, PK, [(-.094, .032), (-.096, .004), (-.086, -.012), (-.066, -.019), (-.02, -.019), (-.004, -.012)], .012, .0052)
    G.trigger(P, S, -.04, .03, L=.032)
    for s in (1, -1):
        P.append(lathe_x('crossbolt', [(0, .0042), (.002, .0042), (.0028, .003), (.0028, 0)], (s * .0222, .052, .05), S, 12, s))
    P += [lathe_z('safety', [(0, 0), (0, .0045), (.004, .0045), (.005, .0035), (.005, 0)], (0, .07, .1), S, 12),
          plate('slidelever', [(-.066, .028), (-.066, .02), (-.084, .02), (-.084, .028)], S, .005, .0075, .0006, sym=False, side=1)]
    G.hexbolts(P, [(-.12, .044), (.06, .05)], .0222, S, .0028, n=14)
    P += K.sling_loop(.37, -.052, S) + K.sling_loop(-.64, .028, S)
    # the saddle of four shells on the left
    P.append(plate('saddle', [(-.01, .044), (-.01, .09), (-.11, .09), (-.11, .044)], M['poly'], .0222, .0262, .0012, sym=False, side=1))
    for i in range(4):
        y = -.03 - i * .02
        P += [lathe_z('shell', [(0, 0), (0, .0092), (.044, .0092), (.046, .0086), (.046, 0)], (.035, y, .048), shell, 14),
              lathe_z('shellbase', [(-.012, 0), (-.012, .0098), (0, .0098), (0, 0)], (.035, y, .048), BR, 14)]
    sz = .1
    P += [lathe('bead', [(-.708, 0), (-.708, .0028), (-.713, .0028), (-.713, 0)], BR, .0992, 0, 10),
          lathe('midbead', [(-.428, 0), (-.428, .0018), (-.432, .0018), (-.432, 0)], M['paint'], .0984, 0, 8)]
    SHELL = [lathe('sh_hull', [(.02, 0), (.02, .0092), (-.03, .0092), (-.032, .0086), (-.032, 0)], shell, .3, 0, 14),
             lathe('sh_base', [(.032, 0), (.032, .0098), (.02, .0098), (.02, 0)], BR, .3, 0, 14)]
    finish('gun_pump', P, (0, -.72, zb), (0, -.36, .012), (0, .1, sz), rail=None,
           moving=[('pump', PUMP, (0, -.36, .046))], loose=[('x_shell', SHELL, (0, 0, .3))])


def compact_smg():
    """Compact SMG: a steel upper on a polymer lower, a slotted handguard, a charging tube with a forward handle along
    the top left, a side-folding wire stock, a straight magazine, a stubby fore grip."""
    bl.reset(); M = K.kinetic_mats(); S, PK, PO, RB = M['steel'], M['park'], M['poly'], M['rubber']
    zb = .068; P = []
    P.append(G.loft('upper', [(.075, .05, .092, .018, (.005, .001)), (-.17, .05, .092, .018, (.005, .001))], S))
    P.append(plate('upper_cheek', [(.066, .056), (.066, .086), (.0, .086), (-.016, .074), (-.162, .074), (-.162, .056)], S, .0165, .0198, .0012))
    P.append(prism('lower', [(.075, .05), (.075, .026), (.03, .022), (-.04, .022), (-.042, -.012), (-.096, -.014), (-.098, .022), (-.17, .026), (-.17, .05)],
                   .034, PO, .003))
    P.append(plate('well_flare', [(-.042, -.002), (-.043, -.016), (-.097, -.018), (-.098, -.004)], PO, .016, .0196, .001))
    G.port(P, -.016, -.064, .061, .08, .0198, M['rubber'], None, side=-1)
    BOLT = [plate('boltface', [(-.018, .0625), (-.018, .0785), (-.062, .0785), (-.062, .0625)], PK, .008, .0188, .0008, sym=False, side=-1)]
    P.append(G.loft('handguard', [(-.17, .03, .092, .021, (.007, .006)), (-.3, .03, .092, .021, (.007, .006)), (-.328, .038, .088, .018, (.006, .005))], PO))
    G.slots(P, 'hg_slot', [(-.2 - i * .03, .074, .02, .006, 0) for i in range(4)] + [(-.2 - i * .03, .046, .02, .006, 0) for i in range(4)], .021, PK)
    V.barrel('barrel', M, -.32, -.37, zb, .0085, P, m=S)
    G.brake(P, 'brake', -.36, zb, .0125, .052, S, M['rubber'], 3, bore=.005)
    P.append(G.tube_('chtube', -.15, -.32, .0075, S, .102, n=14))
    P.append(G.band('chtube_cap', -.314, .008, .0088, PK, .102, 0, .0088, 14, .001))
    CHARGE = [prism('chhandle', [(-.264, .096), (-.264, .108), (-.276, .108), (-.276, .096)], .008, S, .001, x=.015),
              prism('chstem', [(-.267, .099), (-.267, .105), (-.273, .105), (-.273, .099)], .014, S, .001, x=.007)]
    P += K.rail(M, .07, -.16, .092, .02, PK)
    # the folding stock: a hinge block, three rods, a pad
    P.append(prism('hinge', [(.076, .042), (.076, .09), (.1, .09), (.1, .042)], .03, PK, .003))
    for x, z in ((.013, .085), (-.013, .085)):
        P.append(G.tube_('stockrod', .3, .1, .0045, S, z, x, n=10))
    P.append(G.tube_('stockrod', .29, .1, .0045, S, .035, 0, n=10))
    P.append(prism('stock_yoke', [(.286, .096), (.298, .096), (.298, .024), (.286, .024)], .04, PK, .002))
    P.append(G.rprism('buttpad', [(.298, .1), (.316, .096), (.316, .02), (.298, .016)], .042, RB, .005))
    G.grip(P, PO, RB, None, ang=.25, h=.108, w=.03, z=.022, swell=.004)
    P += K.trigger_group(M, PO, S, y=-.0, z=.022, L=.042, drop=.044)
    MAG = G.box_mag('magbody', [(-.047, .018), (-.049, -.17), (-.091, -.17), (-.089, .018)], .024, PO, floor_m=PO,
                    floor=[(-.045, -.166), (-.094, -.166), (-.095, -.178), (-.046, -.178)],
                    ribs=[[(-.052, -.03 - k * .035), (-.086, -.03 - k * .035), (-.0862, -.036 - k * .035), (-.0522, -.036 - k * .035)] for k in range(4)])
    MAG.append(G.tube_('magtop', -.052, -.074, .0036, M['brass'], .021, n=10))
    P.append(lathe_z('vgrip', [(-.07, 0), (-.07, .013), (-.062, .015), (-.02, .0145), (-.004, .012), (0, .012), (0, 0)], (0, -.255, .03), RB, 16))
    P.append(lathe_z('vgripcap', [(-.078, 0), (-.078, .014), (-.07, .0165), (-.068, .0165), (-.068, 0)], (0, -.255, .03), PO, 16))
    G.cross_pins(P, [(.05, .035), (-.15, .035)], .034, S, .002)
    G.selector(P, .04, .036, .017, S, 1, ang=.4, L=.018)
    G.hexbolts(P, [(.06, .068), (-.15, .066)], .0198, S, .0022)
    finish('gun_ksmg', P, (0, -.415, zb), (0, -.255, -.02), (0, .08, .125), rail=(0, -.04, .1015),
           moving=[('mag', MAG, (0, -.069, .018)), ('charge', CHARGE, (.013, -.27, .102)), ('bolt', BOLT, (RIGHT * .01, -.04, .07))])


def battle_rifle():
    """Battle rifle: a one-piece walnut stock with a pressed grip panel, a steel receiver with an operating rod down
    its right side, a gas cylinder under the barrel, a pronged flash hider, aperture sights."""
    bl.reset(); M = K.kinetic_mats(); S, PK, W, BR = M['steel'], M['park'], M['wood'], M['brass']
    zb = .072; P = []
    P.append(G.rprism('stock', G.chaikin([(-.46, .034), (-.46, .07), (-.12, .07), (-.12, .06), (.1, .06), (.14, .08), (.3, .076), (.45, .066), (.462, .058), (.462, -.088),
                                         (.445, -.094), (.27, -.05), (.12, -.062), (.085, -.11), (.035, -.118), (.004, -.068), (-.004, .0), (-.01, .03),
                                         (-.055, .03), (-.055, .02), (-.135, .02), (-.135, .03), (-.3, .026)], 2, sharp=(0, 1, 2, 3, 4, 8, 9, 17, 18, 19, 20, 21)),
                      .044, W, .011))
    P.append(plate('grip_panel', [(.022, -.06), (.062, -.064), (.058, -.104), (.036, -.108)], PK, .019, .0228, .0012))
    P.append(plate('fore_panel', [(-.18, .036), (-.18, .062), (-.42, .062), (-.42, .036)], W, .0195, .0232, .002))
    P.append(G.loft('receiver', [(.11, .058, .1, .018, (.005, .001)), (-.15, .058, .1, .018, (.005, .001))], S))
    P.append(plate('receiver_rail', [(.1, .064), (.1, .072), (-.14, .072), (-.14, .064)], S, .0165, .0196, .0008))
    G.port(P, .005, -.066, .076, .094, .0182, M['rubber'], None, side=-1)
    BOLT = [plate('boltface', [(.004, .0775), (.004, .0925), (-.064, .0925), (-.064, .0775)], PK, .008, .0172, .0008, sym=False, side=-1),
            plate('oprod', [(-.04, .066), (-.04, .078), (-.34, .078), (-.34, .066)], S, .018, .024, .0012, sym=False, side=-1),
            prism('ophandle', [(-.033, .074), (-.033, .086), (-.047, .086), (-.047, .074)], .018, S, .002, x=RIGHT * .03)]
    P.append(G.loft('hg_upper', [(-.15, .072, .096, .016, (.007, .0005)), (-.36, .072, .096, .016, (.007, .0005))], W))
    G.slots(P, 'hg_vent', [(-.2 - i * .04, .084, .024, .005, 0) for i in range(4)], .016, PK)
    P += [G.tube_('gascyl', -.3, -.46, .0105, S, .045, n=16),
          lathe('gasplug', [(-.46, 0), (-.46, .0118), (-.47, .0118), (-.474, .008), (-.474, 0)], S, .045, 0, 6, sharp=20),
          prism('frontband', [(-.355, .03), (-.355, .09), (-.37, .09), (-.37, .03)], .046, S, .002)]
    V.barrel('barrel', M, -.15, -.695, zb, .0105, P, m=S, rings=[(-.462, .0128, .014)])
    G.hider(P, 'flashhider', -.69, zb, .0122, .064, S, 5)
    P.append(prism('fsb', [(-.667, zb + .006), (-.667, zb + .035), (-.683, zb + .035), (-.683, zb + .006)], .014, S, .002))
    G.iron_front(P, -.675, .125, S, base_z=zb + .03, w=.022)
    P += K.trigger_group(M, S, S, y=-.006, z=.03, L=.06, drop=.05)
    MAG = G.box_mag('magbody', [(-.058, .03), (-.062, -.12), (-.132, -.13), (-.132, .03)], .028, S, floor_m=S,
                    floor=[(-.059, -.117), (-.135, -.127), (-.136, -.137), (-.06, -.127)],
                    ribs=[[(-.066, -.01 - k * .035), (-.126, -.01 - k * .035), (-.1262, -.016 - k * .035), (-.0662, -.016 - k * .035)] for k in range(3)])
    MAG.append(G.tube_('magtop', -.065, -.095, .0046, BR, .033, n=10))
    P.append(prism('buttplate', [(.461, .066), (.472, .066), (.474, -.09), (.461, -.09)], .046, S, .003))
    G.hexbolts(P, [(.2, .02), (.466, .03)], .0222, S, .003, n=14)
    P += K.sling_loop(.38, -.07, S) + K.sling_loop(-.4, .03, S)
    G.iron_rear(P, .085, .125, S, base_z=.1)
    P += K.rail(M, .095, -.12, .1, .022, PK)
    finish('gun_dmr', P, (0, -.755, zb), (0, -.32, .022), (0, .11, .125), rail=(0, -.01, .1095),
           moving=[('mag', MAG, (0, -.095, .03)), ('bolt', BOLT, (RIGHT * .03, -.04, .08))])


def revolver():
    """Revolver: a round recoil shield and a humped frame under a grooved top strap, a six-shot cylinder (a band with
    the stop notches, flutes ahead of it) on a swing-out crane, a barrel with a rounded ejector shroud and a vent rib,
    a spur hammer with a chequered pad, a rounded guard, a walnut grip with brass medallions, an orange front blade."""
    bl.reset(); M = K.kinetic_mats(); S, PK, W, BR, OR = M['steel'], M['park'], M['wood'], M['brass'], M['orange']
    zc = .062; zb = zc + .013; P = []
    rc = .0135                                                       # the chambers' circle
    P.append(G.disc('recoilshield', .038, .0285, .0246, S, zc, n=40, ch=.002))
    P.append(G.rprism('frame_rear', G.chaikin([(.03, .018), (.03, .099), (.04, .099), (.048, .093), (.053, .078), (.062, .06), (.061, .052), (.054, .046),
                                               (.056, .03), (.05, .018)], 1, sharp=(0, 1, 9)), .022, S, .004))
    P.append(G.loft('topstrap', [(.04, .089, .1, .011, (.003, .0005)), (-.062, .089, .1, .011, (.003, .0005))], S))
    P.append(prism('topgroove', [(.018, .0998), (.018, .1004), (-.056, .1004), (-.056, .0998)], .004, PK, .0002))
    P.append(prism('frame_low', [(.03, .016), (.03, .0355), (-.036, .0355), (-.04, .03), (-.02, .02), (.0, .016)], .028, S, .002))
    P.append(G.rprism('frame_front', [(-.034, .03), (-.034, .09), (-.062, .09), (-.062, .04), (-.04, .03)], .034, S, .005))
    CYL = [lathe('cylinder', [(.0265, 0), (.0265, .0195), (.0245, .0205), (-.0295, .0205), (-.0315, .0195), (-.0315, 0)], S, zc, 0, 36),
           G.band('cyl_band', .0255, .021, .0223, S, zc, 0, .0022, 36, .0007),
           lathe('ratchet', [(.031, 0), (.031, .008), (.0265, .008), (.0265, 0)], S, zc, 0, 6, sharp=20)]
    ROUNDS = []
    for i in range(6):
        a = i * math.pi / 3 + math.pi / 6
        x, z = math.cos(a) * rc, zc + math.sin(a) * rc
        CYL.append(G.bar('cyl_land', .0045, -.0285, .0202, .0223, a - .35, a + .35, S, zc, 0, 3))
        CYL.append(G.bar('cyl_notch', .019, .012, .022, .0227, a + .5 - .06, a + .5 + .06, M['rubber'], zc, 0, 1))
        CYL.append(lathe('chamber', [(-.0316, 0), (-.0316, .0052), (-.0312, .0052), (-.0312, 0)], M['rubber'], z, x, 10))
        ROUNDS += [lathe('rim', [(.0284, 0), (.0284, .0062), (.0266, .0062), (.0266, 0)], BR, z, x, 12),
                   lathe('primer', [(.0288, 0), (.0288, .0021), (.0284, .0021), (.0284, 0)], M['steel'], z, x, 8)]
    hx, hz = .004, zc - .025
    CRANE = [G.tube_('ejrod', -.031, -.061, .0034, S, zc, n=10), lathe('ejknob', [(-.058, 0), (-.058, .0044), (-.064, .0044), (-.065, .0036), (-.065, 0)], S, zc, 0, 12),
             prism('yoke', [(-.031, zc - .026), (-.031, zc + .002), (-.037, zc + .002), (-.037, zc - .026)], .008, S, .001, x=.002),
             G.tube_('yokepin', .0, -.05, .0036, S, hz, hx, n=8)]
    LOADER = [lathe('sl_body', [(.016, 0), (.016, .019), (.004, .019), (.004, 0)], S, 0, 0, 24),
              lathe('sl_knob', [(.03, 0), (.03, .007), (.028, .008), (.016, .008), (.016, 0)], S, 0, 0, 12),
              G.band('sl_grip', .012, .004, .0198, PK, 0, 0, .002, 24, .0004)]
    for i in range(6):
        a = i * math.pi / 3 + math.pi / 6
        x, z = math.cos(a) * rc, math.sin(a) * rc
        LOADER += [lathe('sl_case', [(.004, 0), (.004, .0054), (-.026, .0054), (-.026, 0)], BR, z, x, 10),
                   lathe('sl_nose', [(-.026, 0), (-.026, .0046), (-.032, .0036), (-.034, .0018), (-.034, 0)], M['steel'], z, x, 10)]
    CASING = [lathe('cs_case', [(.0155, .0045), (.0155, .0062), (.014, .0062), (.014, .0054), (-.015, .0054), (-.015, .0045)], BR, .2, 0, 12, closed=True)]
    # barrel, the ejector shroud under it, the vent rib
    V.barrel('barrel', M, -.06, -.182, zb, .0088, P, m=S, bore=.0048)
    P.append(G.rprism('underlug', [(-.06, .05), (-.06, .068), (-.176, .068), (-.181, .062), (-.176, .053), (-.12, .047), (-.075, .048)], .019, S, .006))
    P.append(prism('ventrib', [(-.06, .0885), (-.06, .094), (-.178, .094), (-.181, .0885)], .0085, S, .001))
    for i in range(6):
        P.append(prism('ribpost', [(-.066 - i * .02, .0835), (-.066 - i * .02, .0885), (-.072 - i * .02, .0885), (-.072 - i * .02, .0835)], .006, S, .0004))
    # hammer, latch, screws
    P.append(G.rprism('hammer', G.ribbon(G.smooth([(.036, .072), (.042, .09), (.05, .1015), (.061, .1065)], 2), [.012, .0105, .0085, .0065]), .009, S, .0014, 2))
    P.append(prism('hammer_pad', [(.05, .1035), (.062, .1092), (.0635, .1066), (.052, .101)], .011, PK, .0007))
    P.append(plate('latch', [(.05, .081), (.05, .07), (.036, .068), (.033, .079)], S, .009, .0138, .0008, sym=False, side=1))
    G.serrations(P, 'latch_grip', .0475, 4, .0034, .0705, .0795, .0138, PK, t=.0013, sym=False, side=1)
    G.hexbolts(P, [(.004, .026), (-.03, .033)], .014, S, .0024, sym=False, side=-1, n=14)
    G.guard(P, S, [(-.05, .024), (-.052, .0), (-.044, -.014), (-.03, -.021), (-.004, -.021), (.014, -.015)], .012, .0056)
    G.trigger(P, S, -.012, .022, L=.03)
    # the walnut grip on the committed grip's lines, its medallions and screw
    g = G.hand_grip(P, W, .42, .105, .036, y=.024, z=.02, r=.0115, round_butt=True)
    c = g(.002, .03)
    for s in (1, -1):
        P.append(lathe_x('medallion', [(0, .0058), (.0012, .0058), (.0018, .0046), (.0018, 0)], (s * .0178, c[0], c[1]), BR, 16, s))
    c = g(.0, .078)
    P.append(lathe_x('gripscrew', [(0, .003), (.001, .003), (.0016, .002), (.0016, 0)], (-.0178, c[0], c[1]), S, 12, -1))
    sz = .102
    P += [prism('rearblock', [(.04, .0995), (.04, .104), (.022, .104), (.018, .0995)], .017, S, .001)]
    for s, nm in ((1, 'rearL'), (-1, 'rearR')):
        P.append(prism(nm, [(.03, sz - .0055), (.03, sz + .0015), (.023, sz + .0015), (.023, sz - .0055)], .005, S, .0006, x=s * .0055))
    P += [prism('frontramp', [(-.15, .094), (-.158, .098), (-.176, .098), (-.18, .094)], .0085, S, .0006),
          prism('frontblade', [(-.16, .0975), (-.163, sz), (-.172, sz), (-.176, .0975)], .0035, S, .0006),
          prism('fiber', [(-.165, sz - .0035), (-.165, sz - .0005), (-.171, sz - .0005), (-.171, sz - .0035)], .0037, OR, .0004)]
    finish('gun_revolver', P, (0, -.185, zb), (0, -.02, -.035), (0, .07, sz),
           moving=[('crane', CRANE, (hx, -.0025, hz)), ('cylinder', CYL, (0, -.0025, zc), 'crane'),
                   ('rounds', ROUNDS, (0, -.0025, zc), 'cylinder')],
           loose=[('x_speedloader', LOADER, (0, 0, 0)), ('x_casing', CASING, (0, 0, .2))])


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


def _bio_ribs(P, stations, zc, r=.0062, a0=.55, a1=2.3):
    """Rib bones over both flanks: at each station (y, half width, half height) an arc from beside the spine round to
    the belly, swept a little back as it drops. Give the body's own radius: the ribs lie half in the skin."""
    d = np.full(len(P), 1e3, np.float32)
    for y, rx, rz in stations:
        for s in (1, -1):
            pts = [(s * rx * math.sin(a), y + .02 * (a - a0), zc + rz * math.cos(a)) for a in np.linspace(a0, a1, 7)]
            for i, (p, q) in enumerate(zip(pts, pts[1:])):
                d = np.minimum(d, sdf.round_cone(P, p, q, r * (1 - .09 * i), r * (1 - .09 * (i + 1))))
    return d


def _bio_scales(P, stations, w=.024, L=.036, t=.0075, tilt=.26):
    """Overlapping plates of bone down the back: each (y, z) a scale lying forward over the next."""
    d = np.full(len(P), 1e3, np.float32)
    R = sdf.rot((1, 0, 0), tilt)
    for y, z in stations:
        d = np.minimum(d, sdf.ellipsoid(P, (0, y, z), (w, L, t), R))
    return d


def _bio_spur(P, a, b, c, r0=.015, r1=.004):
    """A hooked spur of bone behind the grip (the shoulder rests in its crook): from a through b to its point c."""
    a, b, c = (np.asarray(v, np.float32) for v in (a, b, c))
    d = sdf.smin(sdf.round_cone(P, a, b, r0, r0 * .66), sdf.round_cone(P, b, c, r0 * .66, r1), r0 * .5)
    up = b + np.array([0, r0 * 1.6, r0 * 2.6], np.float32)                 # the upper prong: the crook the shoulder sits in
    return sdf.smin(d, sdf.round_cone(P, b, up, r0 * .6, r1), r0 * .4)


def load_mat(tex, emit):
    """The loadable biomass (slime ball / bile bladder / larva egg): wet, glistening, lit from inside."""
    return K.tmat('bio_load', tex, coat=1.0, rough=.12, emit=emit, strength=1.6, emit_tex=True)


def hatch_sdf(c, r, cut_x, seed, th=.0032):
    """Lid over a socket on the gun's left flank: a lumpy shell patch of ellipsoid (c, r) outside the plane x = cut_x."""
    def f(P):
        e = sdf.ellipsoid(P, c, r)
        d = np.abs(e) - th
        d = sdf.smax(d, cut_x - P[:, 0], .003)
        return d + K.lumps(P, seed, 150, .0012)
    return f


def bio_spitter():
    """Spitter: a ribbed, breathing tube of muscle that hawks acid globs from a toothed maw."""
    bl.reset(); M = K.bio_mats()
    zb = .07; Ry = _ax_y()
    mouth = (0, -.565, zb)

    def rb(y):
        return float(np.interp(-y, [-.24, -.05, .36, .52], [.042, .062, .038, .052]))

    def body(P):
        d = sdf.round_cone(P, (0, .24, .045), (0, .05, .075), .042, .062)
        d = sdf.smin(d, sdf.round_cone(P, (0, .05, .075), (0, -.36, .072), .062, .038), .04)
        d = sdf.smin(d, sdf.round_cone(P, (0, -.36, .072), (0, -.53, zb), .038, .052), .05)
        d = sdf.smin(d, sdf.round_cone(P, (0, .005, .035), (0, .036, -.105), .023, .019), .03)        # grip
        d = sdf.smin(d, sdf.round_cone(P, (0, -.28, .045), (0, -.295, -.05), .027, .018), .035)      # foregrip growth
        d = sdf.smin(d, sdf.ellipsoid(P, (0, -.03, .02), (.03, .03, .025)), .02)                     # trigger knot
        for i, y in enumerate(np.linspace(-.06, -.44, 8)):
            d = sdf.smin(d, sdf.torus(P, (0, y, .073 - .003 * i), rb(y) - .003, .0075, Ry), .012)
        for s in (1, -1):                                                                          # tendons along the flanks
            d = sdf.smin(d, sdf.capsule(P, (s * .052, .04, .08), (s * .04, -.34, .062), .0045), .006)
            d = sdf.smin(d, sdf.capsule(P, (s * .045, .12, .05), (s * .038, -.2, .035), .0035), .005)
        for k in range(4):                                                                         # four lips round the maw
            a = k * math.pi / 2 + math.pi / 4
            d = sdf.smin(d, sdf.ellipsoid(P, (math.cos(a) * .03, -.55, zb + math.sin(a) * .024), (.022, .03, .018)), .012)
        d = d + K.lumps(P, 3, 120, .0011) + K.lumps(P, 4, 40, .002)
        d = sdf.smax(d, -sdf.ellipsoid(P, (0, -.575, zb), (.032, .055, .026)), .012)               # the maw
        d = sdf.smax(d, -sdf.sphere(P, (.038, -.25, .074), .024), .006)                               # feeding socket
        return d
    lo, hi = (-.1, -.62, -.14), (.1, .3, .16)
    P = [K.sdf_part('flesh', body, lo, hi, .0024, M['flesh'], 14000)]

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
        top = lambda y: float(np.interp(-y, [-.24, -.05, .36], [.087, .137, .11]))
        d = np.minimum(d, _bio_scales(P, [(y, top(y) + .003) for y in np.linspace(.21, -.34, 11) if abs(y - .08) > .03]))
        d = np.minimum(d, _bio_ribs(P, [(y, rb(y) + .002, rb(y) + .002) for y in np.linspace(.0, -.33, 7)], .073))
        d = np.minimum(d, _bio_spur(P, (0, .22, .05), (0, .335, .05), (0, .36, -.045), .021, .005))
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
    P.append(K.sdf_part('bone', bone, (-.1, -.6, -.07), (.1, .4, .17), .0016, M['bone'], 9000))
    P.append(K.sdf_part('maw', lambda P: sdf.ellipsoid(P, (0, -.548, zb), (.026, .03, .021)) + K.lumps(P, 6, 200, .001),
                        (-.04, -.6, .03), (.04, -.5, .11), .0018, M['maw'], 700))
    HATCH = [K.sdf_part('hatch', hatch_sdf((.03, -.25, .074), (.03, .034, .03), .044, 15), (.03, -.3, .03), (.075, -.2, .115), .0014, M['flesh'], 1400)]
    LOAD = [K.sdf_part('biomass', lambda P: sdf.sphere(P, (.036, -.25, .074), .019) + K.lumps(P, 16, 260, .0012) + K.lumps(P, 17, 90, .0016),
                       (.01, -.28, .05), (.06, -.22, .1), .0012, load_mat('bio_sac', '#ffffff'), 1200)]
    finish('gun_bio_spitter', P, (0, -.6, zb), (0, -.295, -.02), (0, .13, .155), organic=('bio_flesh', 'bio_maw', 'bio_glow', 'bio_load'),
           cyl_axis=(0, .07), keys=_bio_keys(mouth, .045),
           moving=[('hatch', HATCH, (.046, -.25, .1)), ('biomass', LOAD, (.036, -.25, .074))])


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
        d = d + K.lumps(P, 7, 110, .0012) + K.lumps(P, 8, 35, .0024)
        d = sdf.smax(d, -sdf.ellipsoid(P, (0, -.46, zb), (.055, .06, .026)), .014)                 # wide horizontal maw
        d = sdf.smax(d, -sdf.ellipsoid(P, (0, -.17, -.015), (.038, .085, .04)), .01)               # window onto the stomach sac
        d = sdf.smax(d, -sdf.ellipsoid(P, (.044, -.112, .078), (.022, .032, .02)), .006)            # feeding slit
        return d
    P = [K.sdf_part('flesh', body, (-.1, -.53, -.11), (.1, .26, .15), .0024, M['flesh'], 14000)]

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
        top = lambda y: float(np.interp(-y, [-.2, -.02, .33], [.09, .138, .127]))
        d = np.minimum(d, _bio_scales(P, [(y, top(y) + .004) for y in np.linspace(.17, -.31, 10) if abs(y - .07) > .03], .027))
        d = np.minimum(d, _bio_ribs(P, [(y, .06, .06) for y in np.linspace(.03, -.3, 6)], .078, .0062, .55, 1.75))
        d = np.minimum(d, _bio_spur(P, (0, .18, .055), (0, .295, .055), (0, .32, -.04), .021, .005))
        for s in (1, -1):
            d = np.minimum(d, sdf.round_cone(P, (s * .065, -.38, .09), (s * .1, -.33, .13), .009, .0015))
        return d
    P.append(K.sdf_part('bone', bone, (-.12, -.5, -.07), (.12, .36, .17), .0016, M['bone'], 9000))
    P.append(K.sdf_part('maw', lambda P: sdf.ellipsoid(P, (0, -.43, zb), (.048, .04, .02)) + K.lumps(P, 10, 200, .001),
                        (-.06, -.48, .04), (.06, -.38, .11), .0018, M['maw'], 700))
    HATCH = [K.sdf_part('hatch', hatch_sdf((.03, -.112, .078), (.032, .04, .03), .046, 18), (.03, -.16, .04), (.075, -.06, .115), .0014, M['flesh'], 1400)]
    LOAD = [K.sdf_part('biomass', lambda P: sdf.ellipsoid(P, (.042, -.112, .078), (.016, .027, .015)) + K.lumps(P, 19, 240, .0012) + K.lumps(P, 20, 80, .0018),
                       (.015, -.15, .05), (.07, -.075, .1), .0012, load_mat('bio_sac', '#ffffff'), 1200)]
    finish('gun_bio_bile', P, (0, -.49, zb), (0, -.2, -.06), (0, .12, .16), organic=('bio_flesh', 'bio_maw', 'bio_glow', 'bio_load'),
           cyl_axis=(0, .07), keys=_bio_keys((0, -.465, zb), .06),
           moving=[('hatch', HATCH, (.048, -.112, .052)), ('biomass', LOAD, (.042, -.112, .078))])


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
        d = d + K.lumps(P, 11, 90, .0014) + K.lumps(P, 12, 30, .003)
        d = sdf.smax(d, -sdf.sphere(P, (0, -.67, zb), .045), .015)                                 # orifice
        d = sdf.smax(d, -sdf.ellipsoid(P, (0, -.15, .18), (.03, .042, .028)), .006)                  # womb socket under the lid plate
        return d
    P = [K.sdf_part('flesh', body, (-.13, -.72, -.14), (.13, .37, .21), .0027, M['flesh'], 15000)]

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
            if i == 2:
                continue                                                                        # the lid plate is the 'hatch'
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
        rr = lambda y: float(np.interp(-y, [-.05, .5], [.083, .064]))
        d = np.minimum(d, _bio_ribs(P, [(y, rr(y), rr(y)) for y in np.linspace(-.08, -.5, 8)], zb, .0068, 1.95, 2.95))   # belly ribs under the eggs
        d = np.minimum(d, _bio_spur(P, (0, .28, .075), (0, .405, .075), (0, .43, -.04), .025, .006))
        return d
    P.append(K.sdf_part('bone', bone, (-.13, -.76, -.07), (.13, .48, .25), .002, M['bone'], 11000))
    P.append(K.sdf_part('maw', lambda P: sdf.sphere(P, (0, -.64, zb), .038) + K.lumps(P, 14, 200, .0015),
                        (-.05, -.69, .06), (.05, -.59, .16), .002, M['maw'], 700))
    def lid(P):
        shell = sdf.ellipsoid(P, (0, -.15, zb + .02), (.09, .085, .09))
        inner = sdf.ellipsoid(P, (0, -.14, zb + .005), (.085, .09, .085))
        plate = sdf.smax(shell, -inner, .004)
        return sdf.smax(plate, -(P[:, 2] - (zb + .045)), .006) + K.lumps(P, 21, 140, .0008)
    HATCH = [K.sdf_part('hatch', lid, (-.1, -.25, .14), (.1, -.05, .23), .0018, M['bone'], 2000)]

    def egg(P):
        d = sdf.ellipsoid(P, (0, -.15, .176), (.02, .029, .02))
        for k in range(5):                                                                      # raised veins
            a = k * 1.25
            d = sdf.smin(d, sdf.capsule(P, (math.cos(a) * .019, -.172, .176 + math.sin(a) * .019), (math.cos(a + .5) * .017, -.128, .176 + math.sin(a + .5) * .017), .0016), .003)
        return d + K.lumps(P, 22, 220, .001)
    LOAD = [K.sdf_part('biomass', egg, (-.03, -.19, .15), (.03, -.11, .2), .0011, load_mat('bio_flesh', '#ffffff'), 1500)]
    finish('gun_bio_brood', P, (0, -.7, zb), (0, -.31, -.04), (0, .07, .225), organic=('bio_flesh', 'bio_maw', 'bio_glow', 'bio_load'),
           cyl_axis=(0, .1), keys=_bio_keys((0, -.66, zb), .06),
           moving=[('hatch', HATCH, (0, -.232, .16)), ('biomass', LOAD, (0, -.15, .176))])


# ================================================================== sight attachments (gun_attach.glb)
def attachments():
    """Each ATT_<id> node: origin = top of the rail, optic axis along -Y. Children <node>_sight (eye point) and,
    for magnified optics, <node>_scope. The game mounts the node on a gun's 'rail' empty.

    Smooth machined finishes (no texture: a coarse one makes parts this small look lumpy): gun_optic anodised black,
    gun_steel for the hardware, gun_rubber, gun_lens (coated glass), gun_brass for one index ring, gun_sightpaint for
    the click marks, gun_dot for a reticle or an illumination mark."""
    bl.reset()
    AL = bl.mat('gun_optic', '#16181c', .85, .4)
    S = bl.mat('gun_steel', '#34373d', 1.0, .3)
    RB = bl.mat('gun_rubber', '#0b0b0c', 0.0, .78)
    L = bl.mat('gun_lens', '#3a2478', .75, .02, emit='#0a0524', strength=1.0)
    D = bl.mat('gun_dot', '#ff2a2a', 0, .3, emit='#ff2a2a', strength=10)
    BR = bl.mat('gun_brass', '#b8893a', 1.0, .3)
    WH = bl.mat('gun_sightpaint', '#f2efe6', 0, .45)
    TAU = 2 * math.pi

    def mount(P, y, w=.026):
        """a rail clamp: the saddle, the jaw on the right, its cross bolt and nut"""
        P.append(prism('clamp', [(y + .011, 0), (y + .011, .008), (y + .008, .0105), (y - .008, .0105), (y - .011, .008), (y - .011, 0)], w, AL, .0015))
        P.append(prism('clampjaw', [(y + .009, -.004), (y + .009, .006), (y - .009, .006), (y - .009, -.004)], .004, AL, .001, x=-(w / 2 + .001)))
        P.append(lathe_x('clampnut', [(0, .0052), (.005, .0052), (.006, .0042), (.006, 0)], (-(w / 2 + .003), y, .002), S, 6, -1))
        P.append(lathe_x('clampbolt', [(0, .003), (.0018, .003), (.0022, .002), (.0022, 0)], (w / 2, y, .002), S, 10, 1))

    def knurl(P, name, y, Ln, r, m, z, n=28, t=.0034, proud=.0007):
        """a knurled ring: a band with n raised bars"""
        P.append(G.band(name, y, Ln, r, m, z, 0, t, n, .0006))
        w = TAU / n * .27
        for k in range(n):
            a = TAU * k / n
            P.append(G.bar(name + '_k', y - .0009, y - Ln + .0009, r - .0003, r + proud, a - w, a + w, m, z, 0, 1))

    def ticks(P, c, axis, rr, d0, d1, n, m, wd=.05, t=.0004):
        """click marks round a drum: n thin bars on the radius rr round the upright (axis 'z') or the cross axis
        ('x+' / 'x-' = which way the drum stands), from d0 to d1 along it"""
        for k in range(n):
            a = TAU * k / n
            Vv = []
            for d in (d0, d1):
                for rad in (rr - t, rr + t):
                    for aa in (a - wd, a + wd):
                        u, v = rad * math.cos(aa), rad * math.sin(aa)
                        if axis == 'z':
                            Vv.append((c[0] + u, c[1] + v, c[2] + d))
                        else:
                            Vv.append((c[0] + (d if axis == 'x+' else -d), c[1] + u, c[2] + v))
            F = [(0, 1, 3, 2), (4, 5, 7, 6), (0, 1, 5, 4), (2, 3, 7, 6), (0, 2, 6, 4), (1, 3, 7, 5)]
            P.append(V.mk('tick', Vv, F, m, 30))

    def slotted(P, name, c, r, side, m=None):
        """a slotted adjustment screw standing out of a flank"""
        P.append(lathe_x(name, [(0, r), (.0014, r), (.002, r * .8), (.002, 0)], c, m or S, 14, side))
        P.append(plate(name + '_slot', [(c[1] + r * .8, c[2] - .0004), (c[1] + r * .8, c[2] + .0004), (c[1] - r * .8, c[2] + .0004), (c[1] - r * .8, c[2] - .0004)], RB,
                       abs(c[0]) + .0015, abs(c[0]) + .0022, .0001, sym=False, side=side))

    def done(name, parts, eye, scope=False):
        g = K.assemble(name, parts)
        bl.empty(name + '_sight', eye, g)
        if scope:
            bl.empty(name + '_scope', eye, g)

    # ---- open reflex: a machined base, the window in a hooped frame with a hood and side ears, the emitter's housing
    h = .022
    P = []
    mount(P, 0, .028)
    P.append(prism('rx_base', [(.027, .0095), (.027, .0135), (.023, .0165), (-.024, .0165), (-.027, .0135), (-.027, .0095)], .033, AL, .002))
    P.append(prism('rx_housing', [(.026, .0165), (.026, .0238), (.013, .0238), (.006, .0165)], .027, AL, .0016))
    P.append(lathe('rx_emitter', [(.0098, 0), (.0098, .0028), (.0086, .0028), (.0086, 0)], L, .0198, 0, 12))
    P.append(G.band('rx_emitter_rim', .0102, .0022, .0036, S, .0198, 0, .001, 12, .0003))
    for s in (1, -1):
        P.append(prism('rx_post', [(-.0085, .016), (-.0125, .037), (-.0195, .037), (-.0215, .016)], .0042, AL, .001, x=s * .0148))
        P.append(prism('rx_ear', [(.008, .0165), (-.0085, .0165), (-.0122, .0355), (-.0088, .0355)], .0026, AL, .0008, x=s * .0156))
    P.append(prism('rx_hood', [(-.0102, .0348), (-.0112, .0392), (-.0245, .0392), (-.0238, .0348)], .0338, AL, .0012))
    P.append(prism('rx_sill', [(-.0085, .0162), (-.0085, .0182), (-.0215, .0182), (-.0215, .0162)], .0338, AL, .0008))
    P.append(prism('rx_glass', [(-.0138, .018), (-.0166, .0348), (-.0176, .0348), (-.0148, .018)], .0256, L, .0002))
    P.append(lathe('rx_dot', [(-.0238, 0), (-.0238, .0012), (-.0244, .0012), (-.0244, 0)], D, h, 0, 8))
    P.append(lathe_x('rx_battery', [(0, .0062), (.0028, .0062), (.0036, .0052), (.0036, 0)], (-.0135, .0175, .0198), S, 20, -1))
    P.append(plate('rx_battery_slot', [(.0215, .0194), (.0215, .0202), (.0135, .0202), (.0135, .0194)], RB, .0166, .0173, .0001, sym=False, side=-1))
    slotted(P, 'rx_windage', (.0135, .0185, .0198), .0028, 1)
    P.append(G.lathe_z('rx_elevation', [(0, 0), (0, .0028), (.0012, .0028), (.0018, .0022), (.0018, 0)], (0, .0195, .0238), S, 14))
    P.append(prism('rx_elev_slot', [(.0218, .0256), (.0218, .0259), (.0172, .0259), (.0172, .0256)], .0008, RB, .0001))
    for i, y in enumerate((.004, -.006)):
        P.append(plate('rx_btn', [(y + .004, .0105), (y + .004, .0148), (y - .004, .0148), (y - .004, .0105)], RB, .0165, .0178, .0006, sym=False, side=1))
    G.hexbolts(P, [(.019, .0128), (-.019, .0128)], .0165, S, .0017, sym=False, side=-1)
    done('ATT_reflex', P, (0, .15, h))

    # ---- holographic: a long clamped base, the housing, a hooded window between pierced ears, the battery across the
    # back, buttons at the rear, adjustment screws on the right
    h = .036
    P = []
    mount(P, .028); mount(P, -.028)
    P.append(prism('hg_foot', [(.05, .0095), (.05, .0138), (-.05, .0138), (-.05, .0095)], .03, AL, .0015))
    P.append(plate('hg_lever', [(.04, .0015), (.04, .0075), (-.006, .0068), (-.012, .004), (-.006, .0015)], S, .0155, .0185, .0008, sym=False, side=1))
    P.append(lathe_x('hg_lever_hub', [(0, .0046), (.0022, .0046), (.003, .0034), (.003, 0)], (.0185, .034, .0045), S, 14, 1))
    P.append(G.loft('hg_body', [(.048, .0138, .0232, .0212, (.0035, .001)), (-.046, .0138, .0232, .0212, (.0035, .001)), (-.05, .0138, .0215, .0195, (.003, .001))], AL))
    for s in (1, -1):
        P.append(prism('hg_wall', [(.034, .0225), (.037, .049), (.029, .0575), (-.04, .0575), (-.0475, .049), (-.0475, .0225)], .0045, AL, .0014, x=s * .0198))
        P.append(plate('hg_ear_cut', G.capsule(-.006, .0395, .05, .014, 0), RB, .0212, .0224, .0006, sym=False, side=s))
        P.append(plate('hg_ear_rim', [(.03, .0245), (.03, .0295), (-.042, .0295), (-.042, .0245)], AL, .0205, .0236, .001, sym=False, side=s))
    P.append(prism('hg_roof', [(.0325, .054), (.0285, .0596), (-.0405, .0596), (-.0465, .054)], .0445, AL, .002))
    for x in (-.011, .011):
        P.append(prism('hg_roof_rib', [(.024, .0594), (.022, .0612), (-.034, .0612), (-.037, .0594)], .0055, AL, .0006, x=x))
    P.append(prism('hg_glass', [(-.042, .0238), (-.042, .0536), (-.043, .0536), (-.043, .0238)], .0356, L, .0002))
    P.append(prism('hg_glass2', [(.0302, .0238), (.0302, .0536), (.0292, .0536), (.0292, .0238)], .0356, L, .0002))
    P.append(prism('hg_engine', [(.028, .0232), (.028, .0285), (.006, .0285), (.0, .0232)], .03, AL, .001))
    P.append(lathe('hg_reticle', [(-.0412, .0032), (-.0412, .004), (-.0416, .004), (-.0416, .0032)], D, h, 0, 20, closed=True))
    P.append(lathe('hg_dot', [(-.0412, 0), (-.0412, .0009), (-.0416, .0009), (-.0416, 0)], D, h, 0, 8))
    P.append(lathe_x('hg_battery', [(-.0245, .0078), (-.0225, .0088), (.0225, .0088), (.0245, .0078), (.0245, 0)], (0, .0485, .0205), AL, 20, 1))
    P.append(lathe_x('hg_batcap', [(.0245, .0084), (.0262, .0092), (.0305, .0092), (.0318, .0078), (.0318, 0)], (0, .0485, .0205), S, 18, 1))
    P.append(plate('hg_batslot', [(.0535, .0201), (.0535, .0209), (.0435, .0209), (.0435, .0201)], RB, .0316, .0323, .0001, sym=False, side=1))
    for x in (-.009, .009):
        P.append(prism('hg_btn', [(.0585, .0165), (.0585, .0225), (.0566, .0225), (.0566, .0165)], .0105, RB, .0008, x=x))
    P.append(prism('hg_btn_plate', [(.0572, .0145), (.0572, .0245), (.048, .0245), (.048, .0145)], .034, AL, .001))
    slotted(P, 'hg_windage', (-.0212, .012, .0185), .003, -1)
    slotted(P, 'hg_elevation', (-.0212, -.004, .0185), .003, -1)
    G.hexbolts(P, [(.022, .051), (-.036, .051)], .0221, S, .0019)
    done('ATT_holo', P, (0, .2, h))

    def scope(name, Lo, r, obj, h, relief, zoom, shade=0.0, tall=.0):
        """Lo sets the eyepiece and objective stations (and with relief the eye point): r the main tube, obj the bell"""
        P = []
        y0, y1 = Lo * .47, -Lo * .6                                   # the eyepiece's rear, the objective's front
        e = r * 1.3
        ry = (.03, -.03) if zoom > 2 else (.024, -.024)
        # the base on the rail and its two rings: a pedestal, the ring, the split's ears with two bolts each
        P.append(prism('mountbar', [(ry[0] + .015, .0095), (ry[0] + .015, .0135), (ry[0] + .011, .0156), (ry[1] - .011, .0156), (ry[1] - .015, .0135),
                                    (ry[1] - .015, .0095)], .024, AL, .0015))
        G.slots(P, 'mountcut', [(0, .0125, (ry[0] - ry[1]) * .55, .0034, 0)], .012, RB)
        for yy in ry:
            mount(P, yy)
            P.append(prism('ringpost', [(yy + .0085, .0145), (yy + .0085, h - r * .3), (yy - .0085, h - r * .3), (yy - .0085, .0145)], .017, AL, .0018))
            P.append(G.band('ring', yy + .0085, .017, r + .0046, AL, h, 0, .005, 32, .001))
            for s in (1, -1):
                P.append(prism('ringear', [(yy + .0085, h - .0036), (yy + .0085, h + .0036), (yy - .0085, h + .0036), (yy - .0085, h - .0036)], .0062, AL, .001,
                               x=s * (r + .0064)))
                P.append(prism('ringsplit', [(yy + .0087, h - .0004), (yy + .0087, h + .0004), (yy - .0087, h + .0004), (yy - .0087, h - .0004)], .0066, RB, .0001,
                               x=s * (r + .0064)))
                for q in (.0045, -.0045):
                    P.append(G.lathe_z('ringbolt', [(.0034, 0), (.0034, .0021), (.0052, .0021), (.0056, .0015), (.0056, 0)], (s * (r + .0068), yy + q, h), S, 6))
        # the body, turned in one piece: eyepiece, main tube, the turret saddle, the bell; hollow, the lenses set back
        P.append(lathe('tube', [(y0, e * .9), (y0 - .003, e), (y0 - Lo * .09, e), (y0 - Lo * .135, r * 1.07), (y0 - Lo * .2, r),
                                (.0165, r), (.0145, r + .003), (-.0145, r + .003), (-.0165, r),
                                (y1 + Lo * .3, r), (y1 + Lo * .17, obj), (y1 + .003, obj), (y1, obj - .0012),
                                (y1, obj - .0038), (y1 + .018, obj - .0042), (y1 + Lo * .3, r - .003), (y0 - Lo * .2, r - .003), (y0 - .014, e - .004),
                                (y0, e - .004)], AL, h, 0, 40, closed=True))
        P.append(lathe('lens_f', [(y1 + .016, 0), (y1 + .016, obj - .004), (y1 + .0175, obj - .004), (y1 + .0175, 0)], L, h, 0, 32))
        P.append(lathe('lens_r', [(y0 - .011, 0), (y0 - .011, e - .0038), (y0 - .0125, e - .0038), (y0 - .0125, 0)], L, h, 0, 32))
        P.append(G.band('lens_ring', y1 + .0155, .0016, obj - .0036, S, h, 0, .0016, 32, .0003))
        P.append(G.band('accent', y1 + Lo * .17 - .002, .002, obj + .0005, BR, h, 0, .0022, 40, .0003))
        knurl(P, 'bell_grip', y1 + .012, .008, obj + .0008, AL, h, 36, .003)
        if shade:
            P.append(G.tube_('hood', y1 + .003, y1 - shade, obj + .0012, AL, h, 0, bore=obj - .0012, n=40, ch=.0008))
            P.append(G.band('hood_lip', y1 - shade + .004, .004, obj + .002, AL, h, 0, .0022, 40, .0006))
        # eyepiece: the rubber cup, the knurled diopter ring; the power ring with its fin
        P.append(G.band('eyecup', y0 + .007, .013, e + .0022, RB, h, 0, .0048, 36, .002))
        knurl(P, 'diopter', y0 - .008, Lo * .04 + .004, e + .0012, AL, h, 30, .0032)
        P.append(prism('diopter_mark', [(y0 - Lo * .1 + .0015, h + e - .0002), (y0 - Lo * .1 + .0015, h + e + .0004), (y0 - Lo * .1 - .003, h + e + .0004),
                                        (y0 - Lo * .1 - .003, h + e - .0002)], .0012, WH, .0001))
        if zoom > 2:
            knurl(P, 'power', y0 - Lo * .15, Lo * .045, r * 1.07 + .0026, AL, h, 26, .0034)
            P.append(prism('powerfin', [(y0 - Lo * .156, h + r * 1.07 + .002), (y0 - Lo * .16, h + r * 1.07 + .0085), (y0 - Lo * .178, h + r * 1.07 + .0085),
                                        (y0 - Lo * .186, h + r * 1.07 + .002)], .0045, AL, .0009))
        # turrets on the saddle: capped drums with click marks (elevation on top, windage on the right); the 2x keeps low caps
        ht = (.0085 if zoom <= 2 else .0165) + tall
        rt = .0105 if zoom <= 2 else .0118
        top = [(r + .002, 0), (r + .002, rt + .0012), (r + .0058, rt + .0012), (r + .0058, rt - .0004), (r + .0058 + ht * .45, rt - .0004),
               (r + .0058 + ht * .45, rt), (r + .005 + ht, rt), (r + .0062 + ht, rt - .0012), (r + .0062 + ht, 0)]
        P.append(G.lathe_z('turret_e', top, (0, 0, h), AL, 24))
        P.append(lathe_x('turret_w', top, (0, 0, h), AL, 24, -1))
        ticks(P, (0, 0, h), 'z', rt + .0013, r + .0026, r + .0052, 24, WH)
        ticks(P, (0, 0, h), 'x-', rt + .0013, r + .0026, r + .0052, 24, WH)
        if zoom > 2:
            for k in range(20):                                       # the caps' grip: raised bars round their top half
                a = TAU * k / 20
                d0, d1 = r + .0062 + ht * .5, r + .0046 + ht
                Vv = []
                for d in (d0, d1):
                    for rad in (rt - .0002, rt + .0007):
                        for aa in (a - .07, a + .07):
                            Vv.append((rad * math.cos(aa), rad * math.sin(aa), h + d))
                F = [(0, 1, 3, 2), (4, 5, 7, 6), (0, 1, 5, 4), (2, 3, 7, 6), (0, 2, 6, 4), (1, 3, 7, 5)]
                P.append(V.mk('capgrip', Vv, F, AL, 30))
                P.append(V.mk('capgrip', [(-(z - h), y, h + x) for x, y, z in Vv], F, AL, 30))
            # the parallax / illumination drum on the left, its index lit
            par = [(r + .002, 0), (r + .002, .0108), (r + .0125, .0108), (r + .0135, .0096), (r + .0135, 0)]
            P.append(lathe_x('parallax', par, (0, 0, h), AL, 24, 1))
            ticks(P, (0, 0, h), 'x+', .011, r + .0035, r + .0095, 18, WH, .035)
            P.append(lathe_x('parallax_mark', [(r + .0135, .0024), (r + .0141, .0024), (r + .0141, 0)], (0, 0, h), D, 12, 1))
        P.append(prism('index', [(.0162, h + r + .0008), (.0162, h + r + .0034), (.0152, h + r + .0034), (.0152, h + r + .0008)], .0014, WH, .0001))
        done(name, P, (0, Lo * .47 + relief, h), True)

    scope('ATT_x2', .15, .0162, .0205, .032, .05, 2)
    scope('ATT_x4', .24, .015, .0225, .036, .06, 4, shade=.022)
    scope('ATT_x8', .34, .016, .0295, .042, .07, 8, shade=.055, tall=.004)
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
