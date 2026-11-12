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


def red_dot(M, y, z, heavy=False):
    """The energy line's built-in sight: a slim hooded emitter sight. A low clamped base, a stem, the window in a
    hoop with rounded corners whose members are 2 mm thick and 6 mm deep, a thin visor over it, a thin glass, the
    emitter low behind. The dot floats on the sight line at (0, y - .03, z). heavy = the heavy weapons' larger window
    with two thin braces."""
    D = M['dark']; P = []
    w, h = (.036, .027) if heavy else (.03, .023)
    yw = y - .02                                                     # the window's plane
    zr = z - .034                                                    # the rail's top
    P.append(prism('rd_base', [(y + .026, zr), (y + .026, zr + .0075), (y + .022, zr + .0098), (yw - .008, zr + .0098), (yw - .01, zr + .0075), (yw - .01, zr)],
                   w * .8, D, .0015))
    P.append(lathe_x('rd_clamp', [(0, .0048), (.004, .0048), (.005, .0038), (.005, 0)], (-(w * .4), y + .004, zr + .004), M['metal'], 6, -1))
    P.append(prism('rd_stem', [(yw + .004, zr + .009), (yw + .003, z - h / 2 - .001), (yw - .003, z - h / 2 - .001), (yw - .005, zr + .009)], w * .5, D, .001))
    P.append(G.hoop('rd_hoop', yw + .003, z, w, h, .004, .002, .006, D))
    P.append(prism('rd_visor', [(yw + .003, z + h / 2 + .0004), (yw + .003, z + h / 2 + .002), (yw - .013, z + h / 2 + .002), (yw - .011, z + h / 2 + .0004)], w * .86, D,
                   .0005))
    P.append(prism('rd_glass', [(yw - .0005, z - h / 2 + .0006), (yw - .0005, z + h / 2 - .0006), (yw - .0013, z + h / 2 - .0006), (yw - .0013, z - h / 2 + .0006)],
                   w - .001, M['lens'], .0002))
    P.append(lathe('rd_dot', [(y - .0296, 0), (y - .0296, .0013), (y - .0302, .0013), (y - .0302, 0)], M['dot'], z, 0, 12))
    P.append(prism('rd_emitter', [(y + .024, zr + .0098), (y + .024, zr + .0165), (y + .012, zr + .0165), (y + .007, zr + .0098)], w * .5, M['metal'], .001))
    P.append(lathe_x('rd_knob', [(0, .0034), (.0026, .0034), (.0034, .0026), (.0034, 0)], (w * .25, y + .016, zr + .013), M['trim'], 16, 1))
    if heavy:
        for s in (1, -1):
            P.append(prism('rd_brace', [(yw + .022, zr + .0098), (yw + .003, zr + .0098), (yw + .001, z + h * .3), (yw + .003, z + h * .3)], .002, D, .0006,
                           x=s * (w / 2 + .001)))
    G.hexbolts(P, [(y + .018, zr + .0045)], w * .4, M['trim'], .0018)
    return P


def scope_tube(M, y, z, L=.16, r=.022, objective=.03):
    """The energy line's built-in telescope: a turned main tube with an objective bell and an eyepiece, capped turrets,
    two clamped rings on the rail."""
    P = []
    y0, y1 = y + L * .36, y - L * .64                                # eyepiece end, objective end
    ob = objective
    P.append(lathe('scope_tube', [(y0, r * 1.2), (y0 - .004, r * 1.26), (y0 - L * .1, r * 1.26), (y0 - L * .14, r * 1.02), (y0 - L * .2, r), (y1 + L * .3, r),
                                  (y1 + L * .2, ob * .96), (y1 + .006, ob), (y1, ob * .97), (y1, ob * .86), (y1 + .012, ob * .84), (y0 - .01, r * 1.02),
                                  (y0, r * 1.06)], M['metal'], z, 0, 64, closed=True))
    P.append(G.band('scope_eye', y0 + .002, L * .05, r * 1.3, M['dark'], z, 0, .003, 64, .0012))
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


def e_hand(P, M, ang=.28, h=.12):
    """Every energy long gun's grip (the lines the firing hand is fitted to), a guard with section, a curved trigger."""
    G.grip(P, M['dark'], M['grip'], M['metal'], ang=ang, h=h, w=.034, z=.004)
    G.guard(P, M['dark'], [(-.076, .018), (-.078, -.008), (-.068, -.026), (-.05, -.0335), (-.026, -.0335), (-.012, -.029)], .013, .0052)
    G.trigger(P, M['trim'], -.03, .014, L=.033, w=.007)


def e_small(P, M, B, sel=(.03, .03), pins=((.085, .03), (-.045, .02)), catch=(-.052, .012), charge=None, loops=()):
    """The small real parts where a hand goes: selector, takedown pins, magazine catch, charging handle, sling loops."""
    xs = B.pt(sel[0], -.3, .0028)[0]
    G.selector(P, sel[0], sel[1], xs, M['trim'], 1, ang=.35, L=.02)
    for y, z in pins:
        w = 2 * B.pt(y, 0, .0034)[0]
        P.append(K.cylx('pin', .0032, w, (0, y, z), M['metal'], 16, .0006))
    if catch:
        xc = B.pt(catch[0], -.6, .0026)[0]
        P.append(plate('magcatch', [(catch[0] + .008, catch[1] + .007), (catch[0] + .008, catch[1] - .007), (catch[0] - .008, catch[1] - .009), (catch[0] - .01, catch[1] + .005)],
                       M['trim'], xc - .002, xc + .0022, .0008, sym=False, side=-1))
    if charge:
        y, z = charge
        P += [prism('chargeh', [(y, z), (y, z + .009), (y - .03, z + .009), (y - .036, z)], .036, M['dark'], .002),
              prism('chargelatch', [(y - .006, z + .001), (y - .006, z + .0075), (y - .02, z + .0075), (y - .02, z + .001)], .044, M['trim'], .0012)]
    for y, z in loops:
        P += K.sling_loop(y, z, M['dark'])


def AF(f):
    """The angle round a Body's section (p = 5) at the height fraction f of its flank (-1 belly edge .. 1 top edge)."""
    return math.copysign(math.asin(min(abs(f), 1.0) ** 2.5), f)


def k_grip(P, m, panel_m, ang, h, w, z, y=0.0, plug_m=None, n=28):
    """A pistol grip lofted down its own axis on the lines the firing hand is fitted to (the back strap, front strap,
    width and length of gunkit.grip_profile with the same numbers): a palm swell, finger grooves, checkering that
    follows the curve, a plug in its foot. Returns the Limb."""
    hw = w / 2
    secs = []
    for i in range(11):
        b = -.006 + (h + .01) * i / 10
        t = min(max(b / h, 0.0), 1.0)
        back = float(np.interp(b, [-.006, .02, h * .5, h], [.03, .032, .0265, .028]))
        front = -.0262 + .0011 * math.cos(t * 6 * math.pi) + (.002 if i == 0 else 0.0) + (.003 if i == 10 else 0.0)
        secs.append((b, front, back, hw * (.94 + .1 * math.sin(math.pi * t)), 2.8))
    GR = G.Limb(secs, ang, y, z)
    GR.skin(P, m, 'grip', step=.005, n=n)
    GR.checker(P, 'grip_checker', panel_m, h * .3, h * .86, -.8, .8, 14, 12, .0006, d=.0002)
    P.append(G.rprism('grip_plug', [GR.g(-.0195, h + .0025), GR.g(.027, h - .001), GR.g(.0275, h + .003), GR.g(-.019, h + .007)], w * .84, plug_m or m, .003))
    return GR


def SL_hood(SL, m):
    """The barrel's hood seen in a slide's ejection port (it belongs to the barrel: it stays when the slide moves)."""
    tmp = []
    SL.shell(tmp, 'hood', m, -.014, -.046, SL.af(.42), 1.22, t=.0007, ch=.0005, mirror=False, side=-1, base=-.001)
    return tmp[0]


def auto_rifle():
    """Energy auto rifle: a dark chassis swelling at the cell's well and waisted over the grip under pale armour
    shells (a cheek shell, an upper strake and a lower one with the line of light in the gap between them, a steel
    well guard, louvres at the nose over the emitter's root), the emitter stack in a six-bar cage, a cell magazine, a
    solid two-layer stock."""
    bl.reset(); M = K.energy_mats(); P = []
    BD, MT, DK, TR, GL = M['body'], M['metal'], M['dark'], M['trim'], M['glow']
    zb = .062
    e_hand(P, M)
    B = G.Body([(.152, .03, .096, .021, 4.0), (.11, .016, .098, .0245, 4.6), (.06, .008, .098, .0255, 5.0), (.02, .008, .098, .0232, 5.0), (-.03, .006, .098, .0255, 5.0),
                (-.08, .0, .098, .0282, 5.0), (-.14, .0, .098, .0286, 5.0), (-.19, .012, .098, .027, 4.6), (-.225, .028, .097, .0248, 4.0), (-.248, .04, .094, .022, 3.6)])
    B.chassis(P, DK)
    B.shell(P, 'spine', MT, .148, -.244, 1.05, math.pi - 1.05, t=.0004, mirror=False)
    B.shell(P, 'shell_cheek', BD, .146, .034, -.3, .8)
    B.shell(P, 'shell_tail', MT, .124, .034, -1.05, -.42, t=.0022)
    B.shell(P, 'shell_upper', BD, .02, -.196, AF(.09), .8)
    B.shell(P, 'shell_lower', BD, .02, -.05, -.9, -AF(.09))
    B.shell(P, 'shell_well', MT, -.062, -.162, -1.0, -AF(.09), t=.0034)
    B.shell(P, 'shell_chin', BD, -.172, -.196, -.9, -AF(.09))
    B.light(P, 'seam', GL, .016, -.19, -AF(.04), AF(.04))
    B.slats(P, 'vent', BD, -.203, -.246, -.75, .8, 4)
    B.light(P, 'vent_light', GL, -.205, -.244, -AF(.07), AF(.07))
    B.collar(P, 'tail_ring', MT, .154, .009, .002)
    B.studs(P, TR, [(.132, .5), (.046, .5), (.006, .62), (-.184, .62), (-.03, -.72), (-.074, -.5), (-.15, -.5)])
    e_small(P, M, B, charge=(.148, .0985), loops=((.33, -.03), (-.455, .022)))
    # the emitter stack in its cage, a fore panel for the off hand
    G.coil(P, 'emitter', -.244, -.458, zb, .0185, M, rings=7, lip_m=TR)
    G.cage(P, 'cage', -.236, -.472, zb, .0325, MT, t=.0045, bars=6, fill=.56, frames=((-.236, .014), (-.352, .007), (-.458, .014)), phase=math.pi / 2, frame_m=DK)
    P.append(G.sloft('forepanel', [(-.256, .014, .034, .02, 3.6), (-.3, .01, .034, .023, 4.0), (-.41, .01, .034, .023, 4.0), (-.452, .016, .034, .019, 3.6)], BD, 18, 3))
    G.slots(P, 'forecut', [(-.3 - i * .034, .0225, .022, .0045, 0) for i in range(4)], .0232, DK)
    V.barrel('barrel', M, -.46, -.612, zb, .0115, P, m=DK, rings=[(-.505, .0146, .012), (-.565, .0146, .012)])
    G.brake(P, 'brake', -.6, zb, .019, .076, MT, DK, 3)
    P.append(G.band('brake_nut', -.6, .01, .0165, TR, zb, 0, .004, 6, .0008))
    # the cell
    P += G.box_mag('mag', [(-.066, .01), (-.072, -.09), (-.088, -.15), (-.15, -.15), (-.142, -.09), (-.14, .01)], .034, MT, floor_m=DK,
                   floor=[(-.083, -.146), (-.155, -.146), (-.157, -.162), (-.086, -.162)],
                   window=[(-.094, -.022), (-.12, -.022), (-.126, -.1), (-.1, -.1)], window_m=GL,
                   ribs=[[(-.078, -.004), (-.134, -.004), (-.1345, -.012), (-.0785, -.012)], [(-.089, -.112), (-.141, -.112), (-.143, -.12), (-.091, -.12)]])
    G.stock_body(P, M, .15, .096, .222, .13, .04, .03)
    P += e_rail(M, .1, -.44, .098)
    sz = .135
    finish('gun_auto', P, (0, -.68, .062), (0, -.32, .02), (0, .1, sz), optic=red_dot(M, -.02, sz), rail=(0, -.02, .1075))


def pulse_rifle():
    """Pulse rifle: a short deep wedge. The chassis swells round the capacitor bay, whose light is seen through a row
    of louvres in each flank; a cheek shell, a steel belly guard and a nose cowl; a twin-rail emitter; a faceted cell
    ahead of the grip; a side-folding stock on a tube; folding irons."""
    bl.reset(); M = K.energy_mats(); P = []
    BD, MT, DK, TR, GL = M['body'], M['metal'], M['dark'], M['trim'], M['glow']
    zb = .06
    e_hand(P, M)
    B = G.Body([(.142, .03, .098, .022, 4.0), (.1, .018, .1, .028, 4.6), (.05, .012, .1, .03, 5.0), (.0, .012, .1, .0285, 5.0), (-.06, .008, .1, .031, 5.0),
                (-.12, .006, .1, .033, 5.0), (-.17, .012, .1, .032, 4.8), (-.21, .022, .098, .029, 4.2), (-.245, .032, .094, .0255, 3.8), (-.264, .04, .088, .022, 3.4)])
    B.chassis(P, DK)
    B.shell(P, 'spine', MT, .138, -.26, 1.05, math.pi - 1.05, t=.0004, mirror=False)
    B.shell(P, 'shell_cheek', BD, .136, .036, -.35, .82)
    B.shell(P, 'shell_brow', BD, .022, -.2, .52, .84)
    B.slats(P, 'bay_louvre', BD, .022, -.176, -.36, .44, 11, share=.6, t=.003)
    B.light(P, 'bay_light', GL, .018, -.172, -AF(.06), AF(.06))
    B.shell(P, 'shell_belly', MT, .022, -.19, -.98, -.46, t=.0022)
    B.shell(P, 'shell_cowl', BD, -.208, -.262, -.85, .84)
    B.collar(P, 'tail_ring', MT, .144, .009, .002)
    B.studs(P, TR, [(.122, .55), (.05, .55), (-.19, .68), (-.19, -.72), (.0, -.72)])
    e_small(P, M, B, catch=(-.085, .016), charge=(.136, .1005), loops=((-.2, .016),))
    # twin-rail emitter
    G.coil(P, 'emitter', -.262, -.37, zb, .0165, M, rings=4, lip_m=TR)
    for a in (math.pi / 2, -math.pi / 2):
        P.append(G.bar('emit_rail', -.262, -.418, .019, .026, a - .42, a + .42, MT, zb, 0, 4))
    for y in (-.3, -.345):
        P.append(G.band('emit_standoff', y, .006, .0272, DK, zb, 0, .009, 28, .001))
    P.append(G.band('emit_muzzle', -.398, .03, .0275, DK, zb, 0, .0085, 32, .0012))
    P.append(G.band('emit_lip', -.4265, .0035, .0245, TR, zb, 0, .0055, 32, .0006))
    G.cell(P, 'cell', (0, -.12, .004), .026, .085, M, n=8)
    P.append(prism('cell_latch', [(-.088, .004), (-.088, -.012), (-.096, -.016), (-.098, .004)], .02, TR, .0015))
    G.stock_folding(P, MT, DK, M['grip'], .14, .098, L=.165, drop=.115, w=.042, bolt_m=TR)
    P += e_rail(M, .12, -.06, .1)
    sz = .14
    optic = []
    G.iron_rear(optic, .1, sz, DK, base_z=.1095)
    G.iron_front(optic, -.24, sz, DK, dot_m=M['green'], base_z=.094, w=.022)
    finish('gun_pulse', P, (0, -.43, .06), (0, -.24, .01), (0, .14, sz), optic=optic, rail=(0, .03, .1095))


def scout_rifle():
    """Scout rifle: a long slim receiver (waisted over the grip, drawn out into the barrel) under a cheek shell, a
    long upper strake and a short lower one with the light between; a straight bolt; a slim barrel between two guide
    rails with three accelerator rings; a thumbhole stock; its own telescope."""
    bl.reset(); M = K.energy_mats(); P = []
    BD, MT, DK, TR, GL = M['body'], M['metal'], M['dark'], M['trim'], M['glow']
    zb = .055
    e_hand(P, M)
    B = G.Body([(.132, .03, .088, .019, 4.0), (.09, .016, .09, .0225, 4.6), (.04, .006, .09, .0235, 5.0), (.0, .004, .09, .0218, 5.0), (-.05, .0, .09, .024, 5.0),
                (-.1, .0, .09, .025, 5.0), (-.15, .004, .09, .0245, 5.0), (-.21, .016, .09, .0232, 4.6), (-.26, .026, .086, .021, 4.0), (-.308, .034, .078, .0175, 3.4)])
    B.chassis(P, DK)
    B.shell(P, 'spine', MT, .128, -.3, 1.05, math.pi - 1.05, t=.0004, mirror=False)
    B.shell(P, 'shell_cheek', BD, .126, .04, -.3, .8)
    B.shell(P, 'shell_strake', BD, .026, -.25, AF(.42), .8)
    B.shell(P, 'shell_lower', BD, .026, -.045, -.9, AF(.3))
    B.shell(P, 'shell_well', MT, -.056, -.146, -1.0, AF(.3), t=.0032)
    B.shell(P, 'shell_chin', BD, -.158, -.25, -.85, AF(.3))
    B.light(P, 'seam', GL, -.05, -.246, AF(.335), AF(.385))
    B.slats(P, 'vent', BD, -.258, -.306, -.7, .8, 4)
    B.light(P, 'vent_light', GL, -.26, -.304, -AF(.07), AF(.07))
    B.collar(P, 'tail_ring', MT, .134, .009, .002)
    B.studs(P, TR, [(.112, .5), (.05, .5), (-.24, .6), (-.03, -.72), (-.2, -.6)])
    e_small(P, M, B, catch=(-.05, .01), loops=((.3, -.046), (-.3, .02)))
    G.port(P, .03, -.035, .064, .08, B.pt(0, .5, .0028)[0], DK, MT, side=-1)
    P += [rod('bolt', (RIGHT * .022, .012, .072), (RIGHT * .054, .024, .06), .0045, TR),
          lathe_x('boltknob', [(0, .004), (.004, .009), (.013, .009), (.017, .004), (.017, 0)], (RIGHT * .054, .024, .06), DK, 20, -1)]
    # the barrel: slim, between an upper and a lower guide rail, three accelerator rings
    V.barrel('barrel', M, -.3, -.69, zb, .0105, P, m=DK)
    for a in (math.pi / 2, -math.pi / 2):
        P.append(G.bar('guide', -.3, -.64, .0135, .019, a - .3, a + .3, MT, zb, 0, 3))
    for y in (-.37, -.47, -.57):
        P.append(G.band('accel', y, .018, .0225, DK, zb, 0, .0095, 32, .0012))
        P.append(G.band('accel_glow', y - .007, .004, .0232, GL, zb, 0, .003, 32, .0003))
        for q in (.003, -.019):
            P.append(G.band('accel_insul', y + q, .003, .0205, MT, zb, 0, .006, 32, .0006))
    G.brake(P, 'brake', -.675, zb, .018, .068, TR, DK, 3)
    P += G.box_mag('mag', [(-.06, .02), (-.066, -.06), (-.14, -.06), (-.136, .02)], .03, MT, floor_m=DK,
                   floor=[(-.064, -.056), (-.142, -.056), (-.143, -.068), (-.066, -.068)], window=[(-.085, -.005), (-.115, -.005), (-.118, -.045), (-.088, -.045)],
                   window_m=GL)
    G.stock_soft(P, BD, MT, M['grip'], .13, .088, .222, .14, .036, .03, mode='thumb', grip_pt=G.gp(.28, 0, .004)(.028, .118), bolt_m=TR)
    P += e_rail(M, .08, -.16, .09)
    sz = .13
    finish('gun_scout', P, (0, -.74, .055), (0, -.32, .0), (0, .1, sz), optic=scope_tube(M, -.02, sz, .17, .019, .026), scoped=True,
           rail=(0, -.04, .0995))


def hand_cannon():
    """Hand cannon (the hero handgun), built in two layers like the long energy guns: a dark frame lofted round the
    drum's window with pale shells standing proud of it and light lying in the gaps; a recoil shield of two pale
    discs with a ring of light between; an energy cell drum (six cells clipped in milled cradles, each with a slit of
    light, the feed ports clustered round the axis in line with the emitter); a heavy shroud that is a cage of shells
    (the emitter's coil seen through its vents, a dark spine above it); a broad hammer in the frame's cut with a gold
    chequered spur, under the sight line; a guard undercut at the front strap; a grip on its lines with a flared butt."""
    bl.reset(); M = K.energy_mats(); P = []
    zc, zb = .058, .07
    BD, MT, DK, TR, GL = M['body'], M['metal'], M['dark'], M['trim'], M['glow']
    # ---- the grip on the committed lines, a flared butt below its length, a lanyard ring
    g = G.hand_grip(P, M['grip'], .38, .12, .034, z=.004)
    BT = G.Limb([(.113, -.0203, .0273, .0156, 3.2), (.1245, -.0205, .0283, .0166, 3.2), (.131, -.0245, .0318, .0196, 3.2), (.137, -.0262, .0332, .021, 3.4),
                 (.141, -.0252, .0322, .0198, 3.6)], .38, 0, .004)                 # the flare begins BELOW the length the hand is fitted to
    BT.skin(P, MT, 'butt', step=.0045, n=24)
    bb = []
    for b in (.1282, .13, .1318):
        s = BT.sec(b); bb.append((b, s[0] - .0009, s[1] + .0009, s[2] + .0009, s[3]))
    G.Limb(bb, .38, 0, .004).skin(P, TR, 'butt_band', step=.0018, n=24)
    c = g(.004, .1435)
    P.append(K.ring('lanyard', .0055, .0014, (0, c[0], c[1]), MT, axis='x', maj=20, mn=8))
    c = g(.002, .034)
    for s in (1, -1):
        P.append(lathe_x('medallion', [(0, .0062), (.0012, .0062), (.002, .005), (.002, 0)], (s * .0168, c[0], c[1]), TR, 18, s))
    G.checker(P, 'grip_checker', [g(-.008, .046), g(.012, .044), g(.012, .108), g(-.008, .11)], .017, M['grip'], 8, 19, .0005)
    # ---- the guard (undercut where it meets the front strap) and the trigger
    P.append(G.rprism('trigguard', G.ribbon(G.smooth([(-.074, .02), (-.078, -.006), (-.07, -.024), (-.054, -.0325), (-.034, -.0325), (-.022, -.029),
                                                      (-.0165, -.0215)], 2), [.0064, .0062, .006, .0056, .005, .0046]), .014, DK, .002, 2))
    G.trigger(P, TR, -.03, .014, L=.034, w=.0075)
    # ---- the frame: ONE dark loft round the drum's window (top strap, barrel boss, belly, the hump with its horn and
    # the cut the hammer sits in); stations = window edge -> outline, half widths
    P.append(G.ring_frame('frame', [
        (.006, .0985, .012, .1085, .0135), (-.03, .0985, -.03, .1085, .0135), (-.076, .0985, -.086, .1085, .0135),
        (-.082, .0985, -.0995, .108, .0145), (-.082, .0925, -.1, .098, .0155),
        (-.082, .058, -.1, .058, .016), (-.082, .0235, -.1, .024, .0155),
        (-.082, .0175, -.097, .012, .015), (-.076, .0175, -.088, .008, .015),
        (-.035, .0175, -.04, .006, .015), (.006, .0175, -.012, .0005, .015),
        (.012, .0175, .012, .0105, .015), (.012, .0235, .03, .019, .015),
        (.012, .034, .043, .035, .015, .015, .0128, .6),
        (.012, .048, .058, .05, .015, .015, .0125, .6),
        (.012, .058, .067, .059, .015, .015, .0125, .6),                       # the horn over the hand's web
        (.012, .068, .056, .07, .015, .015, .0125, .6),
        (.012, .082, .047, .083, .015, .015, .0125, .6),
        (.012, .0925, .0425, .097, .015, .015, .0128, .6),
        (.012, .0985, .04, .1075, .0138, .0138, .0132, .6)], DK, ro=.0022, coarse=True, segs=2))
    # the top strap's second layer: a steel spine, pale shells over the edges
    FT = G.Body([(.014, .1, .11, .013, 4.0), (.0, .1, .11, .015, 5.0), (-.04, .1, .11, .015, 5.0), (-.08, .1, .11, .015, 5.0), (-.1, .1, .11, .015, 5.0)])
    FT.chassis(P, DK, inset=.0016, step=.02, n=20, name='frame_top')
    FT.shell(P, 'top_spine', MT, .012, -.098, 1.0, math.pi - 1.0, t=.0004, mirror=False)
    for ya, yb in ((.01, -.04), (-.048, -.098)):
        FT.shell(P, 'top_shell', BD, ya, yb, -.9, .8, t=.0016, ch=.0012, base=-.0018, na=7)
    # pale shells on the frame's flanks, the dark frame and a line of light in the gaps between them
    P.append(plate('frame_shell', [(.019, .03), (.019, .09), (.034, .09), (.04, .078), (.047, .066), (.05, .056), (.043, .046), (.033, .034), (.027, .028)],
                   BD, .013, .0176, .0012))
    P.append(plate('frame_shell', [(-.004, .0148), (-.074, .0148), (-.074, .0105), (-.04, .0088), (-.012, .0048), (-.004, .0062)], BD, .013, .0176, .001))
    P.append(plate('frame_shell', [(-.0865, .03), (-.0865, .093), (-.0965, .093), (-.0965, .03)], BD, .013, .0176, .0012))
    P.append(plate('frame_light', [(-.008, .0158), (-.07, .0158), (-.07, .0168), (-.008, .0168)], GL, .014, .0154, .0002))
    P.append(plate('crane', [(-.079, .0135), (-.079, .0255), (-.0955, .0255), (-.0955, .018), (-.09, .0135)], MT, .013, .0172, .001, sym=False, side=1))
    P.append(lathe_x('crane_pin', [(0, .0036), (.0016, .0036), (.0022, .0026), (.0022, 0)], (.0172, -.087, .0195), TR, 14, 1))
    P.append(plate('latch', [(.039, .074), (.039, .063), (.024, .061), (.022, .072)], DK, .016, .0198, .001, sym=False, side=1))
    G.serrations(P, 'latch_grip', .0365, 4, .0036, .0635, .0725, .0198, MT, t=.0015, sym=False, side=1)
    G.hexbolts(P, [(-.0915, .086), (-.0915, .037), (.044, .06)], .0176, TR, .0024)
    # ---- the recoil shield: two pale discs on a dark core, a ring of light between them
    P.append(lathe('shield_core', [(.0145, 0), (.0145, .039), (.0035, .039), (.0035, 0)], DK, zc, 0, 48))
    P.append(G.disc('recoil_shield', .0148, .0106, .0415, BD, zc, n=48, ch=.0012))
    P.append(G.disc('recoil_shield', .0076, .0032, .0415, BD, zc, n=48, ch=.0012))
    P.append(G.band('shield_light', .0104, .0026, .0398, GL, zc, 0, .002, 48, .0002))
    # ---- the drum: six cells clipped in milled cradles (a slit of light along each), stop notches in the rear band,
    # the feed ports round the axis: the top one in line with the emitter
    P.append(G.drum('cylinder', -.002, -.078, .0345, BD, zc, n=96, fl_w=.0095, fl_d=.006, fl_end=-.014, fl_r=.006,
                    notch=(-.0045, -.0105, 7, 3, .0012), holes=(.012, .0048, .022, .0008), hub=.005, nh=16))
    P.append(G.band('cyl_ring', -.0118, .002, .0351, TR, zc, 0, .002, 48, .0004))
    for k in range(6):
        a = k * math.pi / 3
        cx, cz = math.cos(a) * .0327, zc + math.sin(a) * .0327
        P.append(lathe('cell', [(-.02, 0), (-.02, .003), (-.0215, .004), (-.0705, .004), (-.072, .003), (-.072, 0)], DK, cz, cx, 14))
        for y in (-.0225, -.0665):
            P.append(lathe('cell_cap', [(y, 0), (y, .0047), (y - .003, .0047), (y - .003, 0)], TR, cz, cx, 10))
        P.append(G.bar('cell_light', -.032, -.06, .0364, .0371, a - .024, a + .024, GL, zc, 0, 1))
        b = a + math.pi / 6
        P.append(lathe('cell_face', [(-.066, 0), (-.066, .0046), (-.065, .0046), (-.065, 0)], GL, zc + math.sin(b) * .012, math.cos(b) * .012, 12))
    P.append(G.tube_('cylaxis', .008, -.086, .0045, DK, zc, n=14))
    P.append(lathe('breech_hub', [(.0035, 0), (.0035, .024), (-.002, .024), (-.002, 0)], DK, zc, 0, 40))
    P.append(G.band('breech_light', .0018, .002, .0246, GL, zc, 0, .0015, 48, .0002))
    P.append(G.tube_('breech', -.0785, -.1, .011, MT, zb, n=24))
    # ---- the shroud: a cage of shells round the emitter (rear and front blocks, a pale top and cheeks, vents, posts,
    # a steel keel), a dark spine above the emitter with a line of light along it
    SH = G.Body([(-.098, .05, .11, .0195, 5.0), (-.12, .049, .11, .021, 5.0), (-.15, .049, .11, .0215, 5.0), (-.18, .049, .11, .021, 5.0), (-.21, .05, .11, .0205, 5.0),
                 (-.235, .05, .11, .0205, 5.0), (-.255, .051, .11, .02, 4.8), (-.265, .052, .1095, .0195, 4.6), (-.272, .053, .109, .019, 4.4)])
    af = SH.af
    for nm, ya, yb in (('shroud', -.098, -.121), ('shroud', -.249, -.272)):
        secs = []
        for y in np.linspace(ya, yb, 5):
            z0, z1, hw, p = SH.sec(y)
            secs.append((y, z0 + .0026, z1 - .0026, hw - .0026, p))
        P.append(G.rloft(nm, secs, DK, 24))
        SH.shell(P, 'shroud_block', BD, ya - .002, yb + .002, af(-.82), af(.4))
    SH.shell(P, 'shroud_top', BD, -.1, -.268, af(.5), math.pi - af(.5), t=.0026, d=-.002, mirror=False, base=-.002, closed=True, ny=10, na=12)
    for ya, yb in ((-.123, -.158), (-.214, -.247)):
        SH.shell(P, 'shroud_cheek', BD, ya, yb, af(-.1), af(.4), closed=True)
    SH.slats(P, 'shroud_louvre', BD, -.164, -.2085, af(-.1), af(.4), 5, share=.6, closed=True)
    for y in (-.1535, -.1845, -.2155):
        SH.shell(P, 'shroud_post', MT, y, y - .005, af(-.58), af(-.07), t=.002, closed=True)
    SH.shell(P, 'shroud_keel', MT, -.123, -.247, -math.pi - af(-.55), af(-.55), t=.0022, mirror=False, closed=True, ny=8, na=10)
    P.append(G.rloft('shroud_core', [(-.118, .087, .1066, .0165, 4.5), (-.185, .087, .1066, .0165, 4.5), (-.252, .087, .1066, .0165, 4.5)], DK, 28))
    P.append(prism('seam', [(-.125, .0929), (-.125, .0941), (-.245, .0941), (-.245, .0929)], .0338, GL, .0002))
    SH.studs(P, TR, [(-.1095, .2), (-.2605, .2), (-.1095, -.5), (-.2605, -.5)], r=.002)
    # the emitter inside the cage: a coil of steel rings on a core of light
    P.append(G.tube_('emitter_core', -.121, -.249, .0086, GL, zb, n=16, ch=0))
    step = .128 / 8
    for i in range(8):
        y = -.121 - step * (i + .08)
        P.append(lathe('emitter_ring', [(y, .008), (y, .0115), (y - .001, .0125), (y - step * .84 + .001, .0125), (y - step * .84, .0115), (y - step * .84, .008)],
                       MT, zb, 0, 14, closed=True))
        if i % 2 == 0:
            ym = y - step * .42
            P.append(lathe('emitter_lip', [(ym + .0012, .012), (ym + .0012, .0136), (ym - .0012, .0136), (ym - .0012, .012)], TR, zb, 0, 14, closed=True))
    # the muzzle block, ported, and a crowned bore
    P.append(G.loft('muzzleblock', [(-.268, .0515, .109, .0188, (.0075, .004)), (-.29, .0515, .109, .0188, (.0075, .004)), (-.3, .056, .105, .0162, (.006, .004))], MT))
    G.slots(P, 'comp', [(-.276 - i * .009, .092, .014, .0036, math.pi / 2 - .35) for i in range(2)], .0188, DK)
    P.append(G.band('crown', -.3005, .005, .0162, TR, zb, 0, .0042, 28, .0006))
    G.muzzle(P, 'barrel', -.296, -.306, zb, .0128, MT, .0075, dark_m=DK)
    P.append(prism('rib', [(.008, .11), (.008, .1114), (-.292, .1114), (-.296, .11)], .0105, DK, .0006))
    # the housing under the shroud, lofted to a nose, its rod's tip in gold
    P.append(G.sloft('underlug', [(-.098, .03, .054, .0095, 3.5), (-.16, .032, .054, .009, 3.5), (-.22, .034, .054, .0085, 3.2), (-.243, .038, .054, .007, 2.8),
                                  (-.252, .044, .054, .0045, 2.4)], MT, 16, 4))
    P.append(lathe('ejrod_tip', [(-.249, 0), (-.249, .0042), (-.2565, .0042), (-.2585, .003), (-.2585, 0)], TR, .0475, 0, 14))
    G.hexbolts(P, [(-.118, .043), (-.215, .043)], .0086, TR, .002)
    # ---- the hammer in the frame's cut (under the sight line): a broad sculpted body, a gold spur, cut checkering
    P.append(G.rprism('hammer', G.chaikin([(.034, .064), (.0375, .078), (.038, .098), (.041, .1045), (.048, .106), (.06, .1025), (.074, .0965), (.0745, .0935),
                                           (.064, .097), (.057, .0935), (.0555, .082), (.06, .072), (.052, .06)], 2, sharp=(6, 7)), .013, MT, .0022, 2))
    P.append(plate('hammer_slot', [(.0425, .08), (.0425, .098), (.05, .1), (.0505, .084), (.047, .078)], DK, .005, .0068, .0005))
    P.append(prism('hammer_spur', [(.0585, .1012), (.0592, .1035), (.0748, .0972), (.0744, .0946), (.064, .0985)], .017, TR, .0008))
    G.checker3(P, 'spur_checker', (-.0075, .06, .10328), (.0075, .06, .10328), (.0075, .074, .09762), (-.0075, .074, .09762), DK, 9, 9, .0006, .0008)
    P.append(K.cylx('hammer_pin', .003, .0306, (0, .0445, .07), TR, 14, .0005))
    # ---- the sights and the plate for an optic
    sz = .112
    P.append(prism('optic_plate', [(-.018, .11), (-.018, .1116), (-.072, .1116), (-.072, .11)], .026, DK, .0006))
    for yy in (-.026, -.064):
        for xx in (.009, -.009):
            P.append(lathe_z('plate_screw', [(0, 0), (0, .0018), (.0004, .0018), (.0004, 0)], (xx, yy, .1116), MT, 10))
    P.append(prism('rear_base', [(.038, .1075), (.038, sz - .004), (.02, sz - .004), (.016, .1085)], .024, DK, .001))
    for s, nm in ((1, 'rear_earL'), (-1, 'rear_earR')):
        P.append(prism(nm, [(.037, sz - .006), (.037, sz + .003), (.027, sz + .003), (.025, sz - .006)], .0075, DK, .001, x=s * .0085))
        P.append(lathe('postdot', [(.0372, 0), (.0372, .0018), (.0368, .0018), (.0368, 0)], M['green'], sz - .0015, s * .0085, 8))
    P.append(prism('front_base', [(-.262, .1105), (-.268, .1145), (-.29, .1145), (-.294, .1105)], .011, DK, .0008))
    P.append(prism('post', [(-.272, .114), (-.277, sz + .0045), (-.2835, sz + .0045), (-.286, .114)], .0036, DK, .0005))
    P.append(lathe('postdot', [(-.2768, 0), (-.2768, .0014), (-.2772, .0014), (-.2772, 0)], M['green'], sz + .0026, 0, 8))
    finish('gun_handcannon', P, (0, -.31, .07), (0, -.02, -.02), (0, .1, sz), rail=(0, -.045, .1116))


def shotgun():
    """Shotgun: a chassis that widens from the wrist to the twin-barrel yoke under a cheek shell, flank shells with
    the light between them and louvres over the charge rack's feed; two bored barrels under a vented rib, a ribbed
    pump, a rack of charge cartridges on top, a low optic rail, a shaped stock whose comb falls to the heel."""
    bl.reset(); M = K.energy_mats(); P = []
    BD, MT, DK, TR, GL = M['body'], M['metal'], M['dark'], M['trim'], M['glow']
    zb = .072
    e_hand(P, M)
    B = G.Body([(.094, .022, .094, .024, 4.0), (.06, .012, .097, .029, 4.6), (.02, .008, .097, .0305, 5.0), (-.03, .008, .097, .0295, 5.0), (-.08, .006, .097, .032, 5.0),
                (-.12, .008, .097, .0335, 5.0), (-.155, .014, .097, .035, 4.8), (-.18, .024, .096, .036, 4.4), (-.2, .034, .095, .0365, 4.2), (-.216, .04, .094, .036, 4.0)])
    B.chassis(P, DK)
    B.shell(P, 'spine', MT, .09, -.212, 1.05, math.pi - 1.05, t=.0004, mirror=False)
    B.shell(P, 'shell_cheek', BD, .088, .03, -.5, .8)
    B.shell(P, 'shell_upper', BD, .016, -.21, AF(.1), .8)
    B.shell(P, 'shell_lower', MT, .016, -.2, -.92, -AF(.1), t=.0022)
    B.light(P, 'seam', GL, .012, -.2, -AF(.04), AF(.04))
    B.studs(P, TR, [(.07, .5), (-.02, .6), (-.19, .6), (-.03, -.7), (-.17, -.7)])
    e_small(P, M, B, pins=((.06, .03), (-.1, .022)), catch=None, loops=((.3, -.03), (-.47, .03)))
    G.port(P, -.02, -.1, .046, .066, B.pt(-.06, 0, .0028)[0], DK, TR, side=-1)
    for i in range(4):                                               # the rack of charge cartridges along the top
        P.append(G.tube_('cartridge', -.02 - i * .03, -.044 - i * .03, .0085, TR, .105, n=20, ch=.0015))
        P.append(G.band('cartridge_glow', -.03 - i * .03, .004, .0089, GL, .105, 0, .002, 20, .0002))
    P.append(prism('rack', [(-.01, .097), (-.01, .1), (-.15, .1), (-.15, .097)], .03, DK, .001))
    for x in (-.0175, .0175):
        P.append(G.tube_('barrel', -.16, -.548, .0162, MT, zb, x, bore=.0115, n=32))
        P.append(G.band('muzzle_ring', -.53, .012, .0175, TR, zb, x, .003, 32, .0006))
    P.append(G.rprism('yoke', [(-.19, .05), (-.19, .094), (-.215, .094), (-.215, .05)], .074, DK, .008))
    P.append(prism('vrib', [(-.2, .0885), (-.2, .095), (-.545, .095), (-.545, .0885)], .01, DK, .001))
    for i in range(8):
        P.append(prism('ribpost', [(-.24 - i * .04, .084), (-.24 - i * .04, .0885), (-.25 - i * .04, .0885), (-.25 - i * .04, .084)], .007, DK, .0005))
    P.append(G.tube_('magtube', -.19, -.5, .0125, DK, .04, n=24))
    P.append(G.band('tubecap', -.488, .016, .0142, MT, .04, 0, .0142, 24, .0015))
    P.append(G.sloft('pump', [(-.268, .014, .056, .033, 3.6), (-.29, .008, .06, .039, 4.0), (-.35, .006, .06, .04, 4.0), (-.41, .008, .06, .039, 4.0),
                              (-.434, .014, .056, .033, 3.6)], BD, 24, 3))
    for i in range(6):
        y = -.296 - i * .021
        P.append(G.rloft('pumprib', [(y, .0055, .0615, .0412, 4.0), (y - .009, .0055, .0615, .0412, 4.0)], DK, n=24))
    G.stock_soft(P, BD, MT, M['grip'], .09, .066, .24, .102, .046, .024, mode='open', cheek=False, bolt_m=TR, fall=.012, top0=.094)
    # raised sights: a ghost ring on a stem at the receiver's rear, a post on a ramp at the muzzle (2.4 cm over the
    # cartridge rack, 4 cm over the receiver); the `sight` point is the ring's centre
    sz = .1375
    G.iron_rear(P, .07, sz, DK, base_z=.0965, w=.018)
    P.append(prism('front_base', [(-.492, .095), (-.524, .131), (-.542, .131), (-.547, .095)], .008, DK, .001))
    P.append(prism('post', [(-.529, .13), (-.531, sz), (-.537, sz), (-.539, .13)], .0026, DK, .0004))
    P.append(lathe('postdot', [(-.5288, 0), (-.5288, .0012), (-.5292, .0012), (-.5292, 0)], M['green'], sz - .0022, 0, 8))
    P += K.rail(M, .036, -.008, .0895, .022, DK)
    finish('gun_shotgun', P, (0, -.56, .072), (0, -.35, -.005), (0, .07, sz), rail=(0, .014, .099))   # (the sight point stays
    # out over the wrist: on the receiver the eye, 9 cm behind it, was level with the receiver's top and its rear face
    # filled the aimed view. To do: a raised rear sight and front post, as the rifles have.)


def sniper():
    """Sniper rifle: a heavy steel-shelled action on a dark chassis, and a separate deep forend cradle under the
    accelerator stack with louvred flanks; a long fluted barrel to a ported focusing brake; a bipod; an adjustable
    chassis stock with a monopod; a long telescope."""
    bl.reset(); M = K.energy_mats(); P = []
    BD, MT, DK, TR, GL = M['body'], M['metal'], M['dark'], M['trim'], M['glow']
    zb = .055
    e_hand(P, M)
    B = G.Body([(.152, .024, .088, .021, 4.0), (.11, .012, .09, .0255, 4.6), (.05, .006, .09, .027, 5.0), (.0, .004, .09, .0252, 5.0), (-.06, .0, .09, .0275, 5.0),
                (-.12, .0, .09, .0285, 5.0), (-.17, .004, .09, .028, 5.0), (-.205, .012, .09, .0265, 4.6), (-.225, .02, .088, .0245, 4.0), (-.24, .026, .084, .0225, 3.6)])
    B.chassis(P, DK)
    B.shell(P, 'spine', MT, .148, -.236, 1.05, math.pi - 1.05, t=.0004, mirror=False)
    B.shell(P, 'shell_cheek', MT, .146, .046, -.4, .8)
    B.shell(P, 'shell_action', BD, .03, -.2, AF(.1), .8, t=.003)
    B.shell(P, 'shell_lower', MT, .03, -.04, -.95, -AF(.1), t=.0022)
    B.shell(P, 'shell_well', BD, -.046, -.128, -1.0, -AF(.1), t=.0034)
    B.shell(P, 'shell_chin', MT, -.14, -.2, -.9, -AF(.1), t=.0022)
    B.light(P, 'seam', GL, -.05, -.196, -AF(.04), AF(.04))
    B.collar(P, 'tail_ring', DK, .154, .01, .0022)
    B.studs(P, TR, [(.126, .5), (.06, .5), (.01, .62), (-.186, .62), (-.02, -.7), (-.17, -.6)])
    e_small(P, M, B, catch=(-.04, .008), loops=((.36, -.04),))
    G.port(P, .0, -.07, .062, .08, B.pt(-.03, .5, .0032)[0], DK, TR, side=-1)
    P += [rod('bolt', (RIGHT * .024, .03, .075), (RIGHT * .06, .04, .062), .005, TR),
          lathe_x('boltknob', [(0, .005), (.005, .0115), (.017, .0115), (.022, .005), (.022, 0)], (RIGHT * .06, .04, .062), DK, 24, -1)]
    # the forend cradle under the accelerator
    F = G.Body([(-.176, .008, .05, .027, 4.4), (-.22, .004, .052, .0305, 5.0), (-.3, .004, .052, .031, 5.0), (-.38, .006, .05, .0305, 5.0), (-.43, .01, .048, .028, 4.6),
                (-.462, .016, .044, .023, 4.0)])
    F.chassis(P, DK, name='cradle')
    F.shell(P, 'cradle_shell', BD, -.19, -.25, -.9, .75)
    F.slats(P, 'cradle_louvre', BD, -.26, -.4, -.5, .75, 7, share=.62)
    F.light(P, 'cradle_light', GL, -.262, -.398, AF(.22), AF(.3))
    F.shell(P, 'cradle_keel', MT, -.26, -.4, -1.0, -.56, t=.0022)
    F.shell(P, 'cradle_nose', BD, -.41, -.458, -.9, .75)
    F.studs(P, TR, [(-.2, -.2), (-.445, -.2)])
    # barrel: accelerator stack, then a long fluted tube, then the brake
    G.coil(P, 'accel', -.235, -.47, zb, .0205, M, rings=6, lip_m=TR)
    P.append(G.bar('accel_top', -.235, -.47, .022, .028, math.pi / 2 - .5, math.pi / 2 + .5, MT, zb, 0, 4))
    V.barrel('barrel', M, -.47, -.875, zb, .0135, P, m=DK, rings=[(-.49, .0185, .02), (-.84, .0165, .016)])
    for k in range(6):
        a = math.pi / 6 + k * math.pi / 3
        P.append(G.bar('land', -.515, -.82, .013, .0152, a - .2, a + .2, MT, zb, 0, 2))
    P.append(lathe('focus', [(-.86, 0), (-.86, .021), (-.875, .027), (-.99, .027), (-1.005, .031), (-1.028, .031), (-1.03, .029), (-1.03, .014),
                             (-.99, .014), (-.99, 0)], MT, zb, 0, 40))
    for i in range(3):
        P.append(prism('focus_port', G.capsule(-.9 - i * .032, zb, .016, .03, math.pi / 2), .056, DK, .0004))
    P.append(G.band('focus_glow', -.992, .005, .0315, GL, zb, 0, .003, 40, .0004))
    P.append(G.band('focus_lip', -1.024, .004, .0322, TR, zb, 0, .004, 40, .0005))
    P.append(prism('bipodclamp', [(-.535, .008), (-.535, .03), (-.565, .03), (-.565, .008)], .052, DK, .003))
    for s in (1, -1):
        P.append(rod('bipod', (s * .022, -.55, .02), (s * .046, -.526, -.1), .0052, DK))
        P.append(rod('bipod_ext', (s * .046, -.526, -.1), (s * .05, -.522, -.118), .0038, MT))
        P.append(lathe_x('bipodfoot', [(-.008, .009), (.008, .009), (.008, 0)], (s * .05, -.522, -.122), M['grip'], 12, 1))
    P += G.box_mag('mag', [(-.05, .012), (-.052, -.06), (-.122, -.06), (-.12, .012)], .036, DK, floor_m=MT,
                   floor=[(-.05, -.056), (-.124, -.056), (-.125, -.068), (-.052, -.068)], window=[(-.07, -.008), (-.1, -.008), (-.1, -.044), (-.07, -.044)],
                   window_m=GL)
    G.stock_adjustable(P, BD, DK, M['grip'], .15, .09, .28, .135, .044, .016, bolt_m=TR)
    P.append(lathe_z('monopod', [(-.05, 0), (-.05, .009), (-.046, .009), (-.044, .0055), (0, .0055), (0, 0)], (0, .392, -.01), DK, 16))
    P += e_rail(M, .14, -.2, .09)
    sz = .14
    finish('gun_sniper', P, (0, -1.03, .055), (0, -.3, .0), (0, .2, sz), optic=scope_tube(M, .02, sz, .3, .024, .034), scoped=True,
           rail=(0, -.03, .0995))


def rocket():
    """Rocket launcher: a dark launch tube that swells at the breech and flares to the muzzle bell, under armour
    shells (a top spine, flank shells with the light in the gap, a belly shell, louvres at the venturi); conduits
    along its belly; a sight arm; a grip frame and fore grip; a padded shoulder cradle."""
    bl.reset(); M = K.energy_mats(); P = []
    BD, MT, DK, TR, GL = M['body'], M['metal'], M['dark'], M['trim'], M['glow']
    zc = .13
    e_hand(P, M)
    R = [(.3, .07), (.25, .077), (.16, .077), (.06, .074), (-.04, .075), (-.18, .076), (-.34, .076), (-.46, .078), (-.55, .081), (-.6, .088), (-.626, .092)]
    B = G.Body([(y, zc - r, zc + r, r, 2.0) for y, r in R])
    B.chassis(P, DK, n=48)
    P.append(lathe('tube_bore', [(.31, .0585), (-.63, .0705), (-.63, .068), (.31, .056)], DK, zc, 0, 40, closed=True))
    B.shell(P, 'shell_spine', BD, .25, -.54, 1.05, math.pi - 1.05, t=.003, mirror=False)
    B.shell(P, 'shell_breech', BD, .25, .07, -.75, .8, t=.003)
    B.shell(P, 'shell_upper', BD, .04, -.54, .12, .8, t=.003)
    B.shell(P, 'shell_lower', BD, .04, -.3, -.75, -.02, t=.003)
    B.shell(P, 'shell_chin', MT, -.32, -.54, -.75, -.02, t=.0024)
    B.light(P, 'seam', GL, -.02, -.3, .03, .07)
    B.slats(P, 'venturi_louvre', MT, .296, .258, -1.2, 1.2, 3, share=.6)
    B.shell(P, 'bell', MT, -.556, -.622, -1.45, 1.45, t=.0026)
    B.collar(P, 'band', MT, -.42, .03, .0042)
    B.collar(P, 'hazard', TR, -.33, .012, .0036)
    B.collar(P, 'bell_lip', TR, -.618, .008, .0032)
    B.studs(P, TR, [(.2, .4), (.1, .4), (-.5, .4), (-.5, -.4), (.2, -.4), (-.1, .4), (-.25, -.4)], r=.003, d=.0032)
    P.append(lathe('nozzle', [(.3, .07), (.33, .066), (.372, .084), (.376, .081), (.376, .072), (.34, .054), (.3, .056)], DK, zc, 0, 48, closed=True))
    P.append(G.band('nozzle_glow', .338, .008, .0585, GL, zc, 0, .004, 48, .0004))
    for s in (1, -1):
        P.append(G.cable('conduit', [(s * .062, .26, zc - .052), (s * .066, .0, zc - .049), (s * .062, -.4, zc - .052)], .0045, DK, 10, 24))
        P.append(G.cable('conduit2', [(s * .052, .26, zc - .061), (s * .056, .0, zc - .058), (s * .052, -.4, zc - .061)], .0028, MT, 8, 24))
    # the grip frame, fore grip, shoulder cradle
    P.append(G.sloft('mount', [(.074, .014, .058, .017, 4.0), (.03, .004, .058, .02, 4.4), (-.06, .004, .058, .02, 4.4), (-.16, .016, .058, .019, 4.2), (-.244, .03, .058, .016, 3.8)],
                     DK, 20, 4))
    P.append(G.rprism('grip2', [(-.258, .058), (-.262, -.012), (-.27, -.058), (-.308, -.062), (-.3, .058)], .032, M['grip'], .009))
    P.append(G.sloft('rest', [(.17, .034, .06, .024, 4.0), (.22, .018, .06, .028, 3.6), (.28, .008, .06, .03, 3.4), (.305, .012, .06, .026, 3.4)], MT, 20, 4))
    for i in range(4):
        y = .205 + i * .024
        P.append(G.rloft('rest_pad', [(y, .002 + (3 - i) * .006, .02 + (3 - i) * .006, .031, 3.0), (y + .018, .0 + (3 - i) * .006, .018 + (3 - i) * .006, .031, 3.0)], M['grip'], n=18))
    G.hexbolts(P, [(.05, .03), (-.2, .044)], .0195, TR, .003)
    sz = .23
    P.append(G.rprism('sightarm', [(.05, .2), (.05, .208), (-.09, .208), (-.09, .2), (-.03, .2), (-.02, .192), (.02, .192), (.03, .2)], .016, DK, .003))
    P += K.rail(M, .06, -.1, .205, .022, DK)
    finish('gun_rocket', P, (0, -.64, .13), (0, -.28, -.02), (0, .1, sz), optic=red_dot(M, -.02, sz + .015, heavy=True), rail=(0, -.02, .2145))


def smg():
    """Submachine gun: a compact chassis, waisted over the grip and drawn to a nose, under a cheek shell, an upper
    strake and a steel well guard with the light in the gap; the emitter in an eight-bar shroud ending in a
    suppressor; a straight cell; a hand stop; a twin-rod stock with a ribbed pad."""
    bl.reset(); M = K.energy_mats(); P = []
    BD, MT, DK, TR, GL = M['body'], M['metal'], M['dark'], M['trim'], M['glow']
    zb = .066
    e_hand(P, M, ang=.22, h=.11)
    B = G.Body([(.074, .03, .095, .02, 4.0), (.05, .014, .097, .024, 4.6), (.02, .01, .097, .0238, 5.0), (-.02, .008, .097, .0228, 5.0), (-.06, .006, .097, .0252, 5.0),
                (-.1, .004, .097, .0262, 5.0), (-.14, .01, .097, .0255, 4.8), (-.17, .022, .096, .024, 4.2), (-.19, .034, .094, .0225, 3.8), (-.2, .04, .092, .0215, 3.6)])
    B.chassis(P, DK)
    B.shell(P, 'spine', MT, .07, -.196, 1.05, math.pi - 1.05, t=.0004, mirror=False)
    B.shell(P, 'shell_cheek', BD, .068, .012, -.5, .8)
    B.shell(P, 'shell_strake', BD, .0, -.16, AF(.1), .8)
    B.shell(P, 'shell_lower', BD, .0, -.06, -.9, -AF(.1))
    B.shell(P, 'shell_well', MT, -.068, -.13, -1.0, -AF(.1), t=.0032)
    B.shell(P, 'shell_chin', BD, -.14, -.16, -.85, -AF(.1))
    B.light(P, 'seam', GL, -.004, -.156, -AF(.04), AF(.04))
    B.slats(P, 'vent', BD, -.166, -.2, -.7, .8, 3)
    B.light(P, 'vent_light', GL, -.168, -.198, -AF(.07), AF(.07))
    B.studs(P, TR, [(.05, .5), (-.02, .6), (-.15, .6), (-.03, -.7), (-.12, -.5)])
    e_small(P, M, B, sel=(.02, .03), pins=((.05, .028), (-.05, .02)), catch=(-.06, .012), charge=(.04, .0975), loops=((.06, .1),))
    # shroud, emitter, suppressor
    G.coil(P, 'emitter', -.196, -.302, zb, .0165, M, rings=4)
    G.cage(P, 'shroud', -.19, -.305, zb, .0285, MT, t=.004, bars=8, fill=.58, frames=((-.19, .012), (-.295, .012)), phase=math.pi / 2, frame_m=DK)
    V.barrel('barrel', M, -.3, -.37, zb, .0105, P, m=DK)
    G.can(P, 'can', -.36, zb, .0195, .118, MT, TR, bands=2)
    P += G.box_mag('mag', [(-.072, .02), (-.078, -.15), (-.126, -.15), (-.122, .02)], .03, DK, floor_m=MT,
                   floor=[(-.075, -.146), (-.129, -.146), (-.13, -.16), (-.077, -.16)], window=[(-.092, -.02), (-.108, -.02), (-.112, -.13), (-.096, -.13)],
                   window_m=GL)
    P.append(G.rprism('vgrip', [(-.23, .038), (-.236, -.048), (-.268, -.054), (-.266, .038)], .028, M['grip'], .008))
    P.append(prism('vgrip_cap', [(-.234, -.046), (-.27, -.052), (-.271, -.06), (-.236, -.055)], .03, DK, .0015))
    for x, z in ((.016, .085), (-.016, .085)):
        P.append(G.tube_('stockbar', .27, .07, .0055, DK, z, x, n=20))
    P.append(G.tube_('stockbar', .27, .05, .0055, DK, .03, 0, n=20))
    P.append(G.rprism('stock_yoke', [(.258, .098), (.276, .096), (.276, .018), (.258, .016)], .046, MT, .006))
    G.ribbed_pad(P, M['grip'], .276, .098, .014, .046, 5, .015)
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
    FR = G.Body([(.057, .039, .0468, .0078, 3.0), (.046, .03, .047, .0136, 4.5), (.034, .012, .047, .0158, 5.0), (.0, .006, .047, .016, 5.0), (-.026, .008, .047, .016, 5.0),
                 (-.033, .016, .047, .016, 5.0), (-.098, .016, .047, .016, 5.5), (-.107, .012, .047, .016, 5.5), (-.158, .012, .047, .0158, 5.5), (-.166, .016, .047, .015, 4.5)])
    FR.skin(P, MT, 'frame', step=.005, n=32)                           # the frame: ten sections, tang to dust cover
    FR.shell(P, 'frame_panel', MT, .02, -.095, FR.af(-.3), FR.af(.6), t=.0009, ch=.001)
    FR.slats(P, 'rail_tooth', DK, -.112, -.158, -1.48, -1.08, 4, share=.6, t=.002, base=-.001)
    # the slide shell: the body, a dark rail along its foot, a steel panel, the serrations, the port
    SL = G.Body([(.038, .05, .088, .0165, 5.0), (.02, .05, .088, .0172, 5.0), (-.01, .05, .088, .0175, 5.0), (-.04, .05, .088, .0175, 5.0), (-.07, .05, .088, .0175, 5.0),
                 (-.1, .05, .088, .0175, 5.0), (-.13, .05, .088, .0172, 5.0), (-.15, .051, .0875, .0165, 4.8), (-.164, .053, .0855, .0152, 4.4), (-.172, .057, .0825, .0132, 4.0)])
    SL.chassis(P, DK, name='slide', step=.006)                         # the slide in two layers: grasping louvres, shells, the light between them
    SL.shell(P, 'slide_spine', MT, .036, -.168, 1.05, math.pi - 1.05, t=.0004, mirror=False)
    SL.slats(P, 'serration', BD, .035, .003, -.8, .8, 7, share=.6, t=.0022)
    SL.shell(P, 'slide_upper', BD, -.002, -.158, AF(.16), .8, t=.0022)
    SL.shell(P, 'slide_lower', MT, -.002, -.162, -.85, -AF(.12), t=.0018)
    SL.light(P, 'seam', GL, -.006, -.156, -AF(.03), AF(.07))
    SL.studs(P, TR, [(-.012, .5), (-.148, .5)], r=.0016, d=.0022)
    G.port(P, -.012, -.05, .0665, .0775, SL.pt(-.03, .4, .0024)[0], DK, TR, side=-1)
    P.append(prism('toprib', [(.018, .088), (.018, .0902), (-.146, .0902), (-.154, .088)], .0105, DK, .0006))
    P.append(prism('optic_plate', [(-.036, .088), (-.036, .0906), (-.084, .0906), (-.084, .088)], .026, DK, .0006))
    for yy in (-.043, -.077):
        for xx in (.009, -.009):
            P.append(lathe_z('plate_screw', [(0, 0), (0, .0018), (.0004, .0018), (.0004, 0)], (xx, yy, .0906), MT, 10))
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
    G.hexbolts(P, [(-.09, .034)], .016, TR, .0024)
    sz = .1
    P.append(prism('rear_base', [(.036, .0895), (.036, sz - .004), (.022, sz - .004), (.018, .0895)], .026, DK, .001))
    for s, nm in ((1, 'rear_earL'), (-1, 'rear_earR')):
        P.append(prism(nm, [(.035, sz - .006), (.035, sz + .003), (.025, sz + .003), (.023, sz - .006)], .0075, DK, .001, x=s * .0088))
        P.append(lathe('postdot', [(.0352, 0), (.0352, .0018), (.0348, .0018), (.0348, 0)], M['green'], sz - .002, s * .0088, 8))
    P.append(prism('front_base', [(-.132, .0895), (-.138, .0935), (-.156, .0935), (-.16, .0895)], .011, DK, .0008))
    P.append(prism('post', [(-.142, .093), (-.146, sz + .003), (-.152, sz + .003), (-.154, .093)], .0036, DK, .0005))
    P.append(lathe('postdot', [(-.1458, 0), (-.1458, .0014), (-.1462, .0014), (-.1462, 0)], M['green'], sz + .0012, 0, 8))
    # ---- cut checkering on the grip, serrations along the top rib, a striker plate
    G.checker(P, 'grip_checker', [g(-.015, .032), g(.017, .028), g(.016, .096), g(-.013, .099)], .0179, M['grip'], 14, 24, .0005)
    for i in range(7):
        y = -.092 - i * .0068
        P.append(prism('top_serration', [(y, .0901), (y, .0907), (y - .003, .0907), (y - .003, .0901)], .0085, MT, .0002))
    P.append(G.rprism('striker_plate', [(.0402, .058), (.0412, .081), (.039, .081), (.039, .058)], .02, MT, .002))
    G.rivets(P, [(-.02, .034), (-.14, .034), (.02, .03)], .016, TR, .0016)
    finish('gun_sidearm', P, (0, -.2, .07), (0, -.02, -.02), (0, .09, sz), rail=(0, -.06, .088))


def heavy_mg():
    """Heavy machine gun: a deep armoured housing (dark chassis, pale shells, a steel feed cover on top, louvres over
    the feed's light) swelling to the drive motor; six barrels on a spindle in two clamp rings (the part `spin`); a
    charge drum hung under it; a tubular carry handle; a pintle socket; a stub stock on the recoil tube."""
    bl.reset(); M = K.energy_mats(); P = []
    BD, MT, DK, TR, GL = M['body'], M['metal'], M['dark'], M['trim'], M['glow']
    zb = .07
    e_hand(P, M, ang=.2)
    B = G.Body([(.104, .02, .112, .036, 4.0), (.07, .008, .12, .046, 4.6), (.02, .004, .122, .05, 5.0), (-.04, .004, .122, .0505, 5.0), (-.1, .004, .122, .052, 5.0),
                (-.15, .006, .12, .0515, 5.0), (-.19, .012, .118, .05, 4.4), (-.215, .016, .119, .05, 3.6), (-.232, .019, .12, .05, 2.8), (-.246, .02, .12, .05, 2.2)])
    B.chassis(P, DK, n=44)
    B.shell(P, 'feed_cover', MT, .09, -.2, .98, math.pi - .98, t=.003, mirror=False)
    B.shell(P, 'shell_cheek', BD, .098, .03, -.6, .82, t=.003)
    B.shell(P, 'shell_upper', BD, .018, -.2, AF(.5), .82, t=.003)
    B.slats(P, 'feed_louvre', BD, .018, -.19, AF(.12), AF(.42), 10, share=.62, t=.003)
    B.light(P, 'feed_light', GL, .014, -.186, AF(.24), AF(.3))
    B.shell(P, 'shell_lower', MT, .018, -.2, -.95, AF(.04), t=.0024)
    B.shell(P, 'shell_collar', BD, -.208, -.244, -1.3, 1.3, t=.003)
    B.studs(P, TR, [(.08, .55), (.08, -.4), (-.19, .7), (-.19, -.7), (-.226, .0), (-.09, -.7)], r=.003, d=.003)
    e_small(P, M, B, pins=((.07, .03), (-.15, .03)), catch=None, loops=((.09, .118),))
    G.port(P, -.02, -.1, .046, .066, B.pt(-.06, -.1, .0028)[0], DK, TR, side=-1)
    # motor, then the spinning cluster
    P.append(lathe('motor', [(-.24, 0), (-.24, .05), (-.31, .05), (-.318, .043), (-.318, 0)], MT, zb, 0, 48))
    for i in range(5):
        P.append(G.band('motor_fin', -.25 - i * .013, .005, .054, DK, zb, 0, .006, 48, .0006))
    SPIN = [G.tube_('spindle', -.31, -.6, .011, MT, zb, n=24)]
    for k in range(6):
        a = k * math.pi / 3 + math.pi / 2
        x, z = math.cos(a) * .03, zb + math.sin(a) * .03
        SPIN.append(G.tube_('rbarrel', -.3, -.655, .0108, DK, z, x, bore=.0058, n=24))
        SPIN.append(G.band('rmuzzle', -.64, .012, .0122, MT, z, x, .0028, 24, .0005))
        SPIN.append(G.band('rbreech', -.318, .02, .0128, MT, z, x, .003, 24, .0006))
    for y, r, m in ((-.4, .047, DK), (-.54, .05, MT)):
        SPIN.append(G.band('clamp', y, .022, r, m, zb, 0, r - .039, 48, .0015))
        for k in range(6):
            a = k * math.pi / 3
            SPIN.append(G.bar('spoke', y - .004, y - .018, .012, r - .006, a - .1, a + .1, m, zb, 0, 1))
    SPIN.append(G.band('clamp_glow', -.553, .004, .0508, GL, zb, 0, .003, 48, .0004))
    SPIN.append(lathe('spin_hub', [(-.6, 0), (-.6, .016), (-.612, .016), (-.62, .009), (-.62, 0)], TR, zb, 0, 24))
    # the drum under the housing
    for s in (1, -1):
        P.append(lathe_x('drum', [(0, .09), (.03, .09), (.036, .084), (.036, .062), (.04, .058), (.04, 0)], (0, -.06, -.07), MT, 56, s))
        P.append(lathe_x('drumcap', [(.04, .056), (.044, .052), (.044, .02), (.047, .016), (.047, 0)], (0, -.06, -.07), TR, 32, s))
        for k in range(8):
            a = k * math.pi / 4
            G.hexbolts(P, [(-.06 + math.cos(a) * .073, -.07 + math.sin(a) * .073)], .036, DK, .0034, sym=False, side=s)
    P.append(lathe_x('drumglow', [(-.0018, .0912), (.0018, .0912), (.0018, .088), (-.0018, .088)], (0, -.06, -.07), GL, 56, 1, closed=True))
    P.append(lathe_x('drumband', [(-.008, .0905), (.008, .0905), (.008, .086), (-.008, .086)], (0, -.06, -.07), DK, 56, 1, closed=True))
    P.append(prism('drum_hanger', [(-.02, .01), (-.02, -.0), (-.1, -.0), (-.1, .01)], .06, DK, .003))
    # a pintle socket ahead of the drum, the carry handle as a bent tube on two posts
    P.append(lathe_z('pintle', [(-.03, 0), (-.03, .016), (-.024, .02), (-.006, .02), (0, .026), (0, 0)], (0, -.19, .012), MT, 24))
    P.append(lathe_z('pintle_pin', [(-.04, 0), (-.04, .008), (-.03, .008), (-.03, 0)], (0, -.19, .012), TR, 12))
    P.append(G.cable('carry', [(0, -.02, .122), (0, -.03, .165), (0, -.07, .18), (0, -.17, .18), (0, -.21, .165), (0, -.22, .122)], .0085, DK, 14, 40))
    P.append(G.rloft('carry_wrap', [(-.075, .168, .192, .012, 2.4), (-.165, .168, .192, .012, 2.4)], M['grip'], n=20))
    G.stock_stub(P, BD, DK, M['grip'], .1, .062, L=.14, r=.024, w=.064, h=.11)
    P.append(G.rprism('fgrip', [(-.28, .004), (-.286, -.068), (-.322, -.074), (-.32, .004)], .032, M['grip'], .009))
    P.append(prism('fgrip_cap', [(-.284, -.066), (-.324, -.072), (-.325, -.08), (-.286, -.075)], .034, DK, .0015))
    sz = .21
    P += K.rail(M, .08, -.06, .17, .022, DK)
    P.append(prism('rail_riser', [(.08, .12), (.08, .17), (.06, .17), (.05, .12)], .02, DK, .003))
    P.append(prism('rail_riser2', [(-.04, .122), (-.04, .17), (-.06, .17), (-.066, .122)], .02, DK, .003))
    finish('gun_hmg', P, (0, -.66, zb + .03), (0, -.3, -.04), (0, .1, sz), optic=red_dot(M, .0, sz, heavy=True), rail=(0, .01, .1795),
           moving=[('spin', SPIN, (0, -.31, zb))])


def energy_rifle():
    """Energy rifle (the Light Lance): a round reactor whose dark core shows between six armour petals; the core of
    light runs sleeved through shrinking focus rings inside an open cradle of four tines to the emitter; a fin over
    the reactor carries the sight rail; a shaped open stock; a faceted cell and feed lines."""
    bl.reset(); M = K.energy_mats(); P = []
    BD, MT, DK, TR, GL = M['body'], M['metal'], M['dark'], M['trim'], M['glow']
    zc = .07
    e_hand(P, M, ang=.25)
    R = [(.132, .034), (.118, .046), (.095, .055), (.06, .06), (.02, .0605), (-.02, .058), (-.05, .052), (-.07, .045), (-.082, .038), (-.09, .032)]
    B = G.Body([(y, zc - r, zc + r, r, 2.0) for y, r in R])
    B.chassis(P, DK, n=48, name='reactor')
    for k in range(3):                                               # six petals: three a side, the core between them
        a = -1.05 + k * .78
        B.shell(P, 'petal', BD, .122, -.076, a, a + .62, t=.0034)
    B.shell(P, 'petal_top', MT, .1, -.07, math.pi / 2 - .16, math.pi / 2 + .16, t=.0024, mirror=False)
    for i in range(4):
        B.collar(P, 'cooling', MT, .1 - i * .026, .006, .0052)
    B.collar(P, 'reactor_glow', GL, -.056, .005, .0008)
    B.studs(P, TR, [(.09, .3), (-.04, .3), (.09, -.5), (-.04, -.5)], r=.0028, d=.0034)
    G.coil(P, 'core', -.08, -.37, zc, .0145, M, rings=9, core=.0105, ring_m=MT)
    for k in range(4):                                               # the cradle: four tines, drawn in toward the emitter
        a = math.pi / 4 + k * math.pi / 2
        for i, (y0, y1, r0, r1) in enumerate(((-.07, -.19, .05, .058), (-.185, -.3, .04, .047), (-.295, -.385, .03, .036))):
            P.append(G.bar('tine', y0, y1, r0, r1, a - .2, a + .2, BD if i != 1 else MT, zc, 0, 4, taper=.8))
    for i, (y, r) in enumerate(((-.12, .045), (-.19, .039), (-.26, .033), (-.33, .027))):
        P.append(G.band('focus', y, .012, r, TR if i % 2 else DK, zc, 0, r - .0155, 48, .0012))
        P.append(G.band('focus_insul', y + .004, .003, r - .003, MT, zc, 0, r - .0175, 48, .0006))
    P.append(lathe('emitter', [(-.36, .013), (-.36, .03), (-.385, .03), (-.41, .021), (-.412, .019), (-.412, .013)], MT, zc, 0, 48, closed=True))
    P.append(G.band('emit_glow', -.405, .004, .0135, GL, zc, 0, .0135, 24, 0))
    P.append(G.rprism('fin', [(.09, .124), (.09, .14), (-.08, .14), (-.3, .112), (-.3, .104), (-.08, .124)], .008, BD, .003))
    P.append(G.rprism('sightrail', [(.05, .12), (.05, .14), (-.05, .14), (-.05, .12)], .022, DK, .004))
    G.stock_soft(P, MT, BD, M['grip'], .12, .1, .17, .1, .044, .03, mode='open', bolt_m=TR)
    P.append(G.sloft('saddle', [(.084, .016, .03, .02, 4.0), (.04, .006, .03, .025, 4.4), (-.07, .006, .03, .025, 4.4), (-.094, .016, .03, .02, 4.0)], DK, 20, 4))
    G.cell(P, 'cell', (0, -.06, .016), .026, .05, M, n=8)
    for s in (1, -1):
        P.append(G.cable('feed', [(s * .014, -.05, zc - .058), (s * .016, -.18, zc - .052), (s * .012, -.33, zc - .034), (s * .008, -.372, zc - .028)], .003, DK, 8, 20))
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
    """Assault rifle (our own pattern), every body a loft. The receiver runs through thirteen sections: a tang that
    tapers into the stock, a rear trunnion swell, a pressed waist over the magazine well, a front trunnion that is
    thick and squared; raised trunnion blocks with rivets, a seat rail for the cover along each top edge, a pressed
    rib, the bolt's slot between two guide rails on the right. The top cover is its own arch with pressed ribs, a
    front tab under the trunnion's block and a rear catch. The magazine well and trigger housing are one shaped part
    with a flared mouth and a paddle catch; the guard is a steel strap. The handguard is walnut shells with real
    vents (the barrel and the gas tube show through), a ferrule and a retaining cap. The stock is walnut through ten
    sections (oval wrist, a comb that rolls over, heel and toe), a ribbed steel butt plate, a swivel. The grip is
    lofted down its own axis with a palm swell, finger grooves and cut checkering. A curved magazine with pressed
    ribs, a floor plate with its catch, feed lips and the top round."""
    bl.reset(); M = K.kinetic_mats(); S, PK, W, PO, RB, OD = M['steel'], M['park'], M['wood'], M['poly'], M['rubber'], M['odg']
    zb = .06; P = []
    pi = math.pi

    # ---------------------------------------------------------------- receiver: thirteen sections that change
    R = G.Body([(.194, .03, .06, .0125, 3.2), (.174, .033, .073, .0156, 4.0), (.152, .031, .084, .0195, 5.0), (.125, .028, .084, .0216, 6.0), (.095, .028, .084, .0222, 6.0), (.06, .028, .084, .0212, 6.0),
                (.02, .028, .084, .0206, 6.0), (-.02, .027, .084, .0204, 6.0), (-.06, .026, .084, .02, 6.0), (-.1, .026, .084, .02, 6.0), (-.14, .026, .084, .0206, 6.0),
                (-.168, .024, .084, .0222, 6.5), (-.192, .021, .084, .0238, 7.0), (-.216, .021, .084, .0242, 7.0)])
    R.skin(P, S, 'receiver', step=.008, n=36)
    R.shell(P, 'cover_rail', S, .15, -.2, .56, 1.0, t=.0016, ch=.001)                 # the rail the cover seats between
    R.shell(P, 'trunnion_r', S, .148, .1, -.66, .5, t=.0022)                           # rear trunnion block
    R.shell(P, 'trunnion_f', S, -.168, -.214, -.66, .5, t=.0026)                       # front trunnion block
    # the flank in three bands, each a real step: a raised belt along the lower half (in three lengths, a flute
    # between them), a recessed channel through the middle with a pressed rib in it, raised panels above on the left
    lo, hi = R.af(-.86), R.af(-.24)
    for ya, yb in ((.092, .03), (.02, -.07), (-.08, -.16)):
        R.shell(P, 'belt', S, ya, yb, lo, hi, t=.002, ch=.0014)
    R.shell(P, 'press_rib', S, .08, -.15, R.af(-.13), R.af(.03), t=.001, ch=.001, na=2)
    for ya, yb in ((.09, -.02), (-.032, -.155)):
        R.shell(P, 'side_panel', S, ya, yb, R.af(.2), R.af(.72), t=.0014, ch=.0012, mirror=False, side=1)
    R.shell(P, 'slot_rail', S, .018, -.14, .05, .088, t=.0014, ch=.001, mirror=False, side=-1)    # right: the bolt's slot
    R.shell(P, 'boltslot', RB, .012, -.134, .095, .5, t=.0003, ch=.0005, mirror=False, side=-1)
    for y, a in ((.136, -.45), (.136, .3), (.112, -.45), (.112, .3), (-.18, -.45), (-.18, .3), (-.204, -.45), (-.204, .3)):
        x = R.pt(y, a, .0024)
        G.rivets(P, [(y, x[2])], x[0], S, .0021)
    for y, z in ((.1, .046), (.064, .046), (-.034, .046)):                             # axis pins through the receiver
        P.append(K.cylx('pin', .0026, 2 * R.pt(y, 0, 0)[0] + .003, (0, y, z), S, 14, .0005))
    xs = R.pt(.046, -.03, .0002)[0]
    G.selector(P, .046, .052, xs, S, 1, ang=.55, L=.024, r=.006)
    for y, z in ((.07, .06), (.024, .046)):
        P.append(lathe_x('sel_stop', [(0, .0018), (.0016, .0018), (.002, .001), (.002, 0)], (xs, y, z), S, 10, 1))
    G.dust_cover(P, .008, -.13, .0668, .0204, PK, .016)
    BOLT = [plate('carrier', [(.005, .0685), (.005, .0778), (-.127, .0778), (-.127, .0685)], PK, .012, .0214, .0012, sym=False, side=-1),
            rod('charging', (RIGHT * .02, -.128, .074), (RIGHT * .046, -.128, .074), .0048, S),
            lathe_x('chknob', [(0, .0048), (.003, .0072), (.011, .0072), (.013, .0048), (.013, 0)], (RIGHT * .043, -.128, .074), S, 16, -1)]

    # ---------------------------------------------------------------- top cover: an arch with pressed ribs
    C = G.Body([(.166, .076, .092, .0185, 2.6), (.14, .076, .0955, .019, 2.6), (.11, .076, .099, .0192, 2.6), (.08, .076, .102, .0192, 2.6), (.055, .076, .1045, .0192, 2.6),
                (.03, .076, .106, .0192, 2.6), (-.04, .076, .106, .0192, 2.6), (-.12, .076, .106, .0192, 2.6), (-.185, .076, .106, .0192, 2.6), (-.2, .078, .104, .018, 2.6),
                (-.208, .08, .098, .014, 2.6)])
    C.skin(P, PK, 'topcover', step=.008, n=28)
    for y in (-.02, -.055, -.09, -.125, -.16):
        C.shell(P, 'cover_rib', PK, y, y - .008, -.3, pi + .3, t=.0014, mirror=False, ch=.001, base=-.0005, na=16)
    P.append(prism('cover_tab', [(-.198, .086), (-.198, .094), (-.222, .094), (-.222, .086)], .012, PK, .001))
    P.append(G.rprism('cover_block', [(-.205, .084), (-.205, .103), (-.219, .103), (-.226, .096), (-.226, .084)], .032, S, .003))
    P.append(G.rprism('cover_catch', [(.178, .078), (.178, .089), (.167, .091), (.167, .078)], .014, S, .003))
    P.append(lathe('catch_button', [(.181, 0), (.181, .0032), (.177, .0036), (.177, 0)], S, .083, 0, 12))

    # ---------------------------------------------------------------- magazine well and trigger housing
    Wl = G.Body([(.04, .02, .032, .0125, 4.0), (.01, .017, .032, .0155, 5.0), (-.03, .015, .032, .0165, 5.0), (-.06, .012, .032, .0175, 5.5), (-.076, .004, .032, .0196, 6.0),
                 (-.1, .0, .032, .0204, 6.0), (-.13, .0, .032, .0206, 6.0), (-.16, .001, .032, .0206, 6.0), (-.174, .006, .032, .0192, 5.0), (-.182, .014, .032, .017, 4.0)])
    Wl.skin(P, S, 'well', step=.008, n=32)
    Wl.shell(P, 'well_mouth', S, -.08, -.17, -1.5, -.72, t=.0024, base=-.002)           # the flared mouth
    Wl.shell(P, 'well_panel', S, -.09, -.162, -.45, .25, t=.001, ch=.0012)
    P.append(G.rprism('magcatch', [(-.062, .012), (-.058, -.012), (-.066, -.022), (-.078, -.02), (-.08, .012)], .014, S, .003))
    P.append(K.cylx('catch_pin', .002, .036, (0, -.07, .008), S, 10, .0004))
    G.guard(P, S, [(-.082, .02), (-.083, -.006), (-.074, -.018), (-.058, -.0225), (-.03, -.0225), (-.014, -.018)], .013, .0046, r=.0019)
    G.trigger(P, S, -.046, .024, L=.03)

    # ---------------------------------------------------------------- sights, barrel group (kept)
    G.iron_rear(P, .09, .1195, S, base_z=.1005, w=.03)
    P.append(G.rprism('gasblock', [(-.434, .044), (-.434, .106), (-.468, .106), (-.478, .09), (-.478, .044)], .03, S, .004))
    G.hexbolts(P, [(-.456, .052)], .015, S, .0026, sym=False, side=1, n=14)
    G.iron_front(P, -.455, .1195, S, base_z=.104, w=.024)
    P.append(G.tube_('gastube', -.218, -.44, .0085, S, .093, n=24))
    G.barrel_stepped(P, 'barrel', [(-.215, .0128), (-.262, .0108), (-.44, .0097), (-.56, .0088), (-.64, .0088)], zb, S, .0045)
    P.append(G.band('barrel_collar', -.524, .012, .0115, S, zb, 0, .003, 32, .001))
    G.hider(P, 'hider', -.63, zb, .0128, .06, S, 4, bore=.0056)
    P.append(G.band('hider_nut', -.632, .008, .0138, PK, zb, 0, .003, 6, .0006))

    # ---------------------------------------------------------------- handguard: walnut shells with real vents
    HG = G.Body([(-.262, .03, .1075, .0245, 3.0), (-.28, .027, .1075, .0275, 3.2), (-.305, .025, .1075, .0295, 3.4), (-.335, .024, .1075, .0305, 3.4),
                 (-.365, .024, .1075, .0302, 3.4), (-.39, .026, .1075, .0288, 3.2), (-.41, .029, .1075, .027, 3.2), (-.424, .032, .1075, .0252, 3.0),
                 (-.432, .034, .1075, .024, 3.0)])
    kw = dict(t=.003, d=-.003, base=-.0046, closed=True)
    HG.shell(P, 'hg_belly', W, -.27, -.422, -pi + .8, -.8, mirror=False, **kw)
    HG.shell(P, 'hg_lower', W, -.27, -.422, -.72, -.22, **kw)
    HG.slats(P, 'hg_vent_bar', W, -.272, -.42, -.16, .2, 8, share=.56, **kw)
    HG.shell(P, 'hg_upper', W, -.27, -.422, .26, .84, **kw)
    HG.slats(P, 'hg_top_bar', PK, -.272, -.42, .92, 1.2, 8, share=.56, **kw)
    HG.shell(P, 'hg_top', PK, -.27, -.422, 1.28, pi - 1.28, mirror=False, **kw)
    HG.checker(P, 'fore_checker', W, -.3, -.4, -.64, -.32, 28, 5, .0007, d=.0001)
    HG.collar(P, 'ferrule', S, -.256, .014, .0012)
    HG.collar(P, 'hg_cap', S, -.42, .014, .0012)
    P += K.rail(M, -.278, -.392, .1075, .02, PK)

    # ---------------------------------------------------------------- stock: walnut through ten sections
    # the wrist grows out of the tang with a palm swell, the comb rolls over and drops to the heel, a cheek flat on the left
    P.append(G.sloft('stock', [(.166, .034, .0765, .0165, 4.0, 1.0), (.185, .03, .073, .017, 3.2, .95), (.205, .022, .0715, .0178, 2.5, .9),
                               (.235, .012, .0705, .0166, 2.5, .85), (.27, .002, .0695, .0172, 2.6, .8), (.31, -.014, .0675, .0184, 2.8, .8),
                               (.35, -.03, .065, .0195, 2.9, .82), (.39, -.045, .061, .0205, 3.0, .86), (.42, -.056, .057, .021, 3.2, .9),
                               (.445, -.066, .052, .0212, 3.6, .95)], W, n=28, sub=4))
    P.append(G.sloft('cheek_flat', [(.262, .03, .062, .0042, 3.0, 1.0, .0152), (.3, .016, .0625, .0052, 3.0, 1.0, .0158), (.36, -.006, .0595, .0056, 3.0, 1.0, .0172),
                                    (.405, -.022, .055, .0046, 3.0, 1.0, .0184)], W, 14, 4))
    P.append(G.rloft('buttplate', [(.444, -.067, .053, .0215, 3.6), (.452, -.066, .052, .0212, 3.6), (.455, -.062, .048, .0195, 3.2)], S, n=32))
    for i in range(5):
        z = .038 - i * .022
        P.append(G.rloft('butt_rib', [(.4555, z - .006, z + .006, .0185, 3.0), (.4585, z - .004, z + .004, .016, 3.0)], S, n=16))
    for s_ in (1, -1):
        P.append(lathe_x('stock_bolt', [(0, .0055), (.0012, .0055), (.002, .004), (.002, 0)], (s_ * .0168, .205, .048), S, 16, s_))
    G.swivel(P, .36, -.0355, S)
    P += K.sling_loop(-.43, .024, S, x=.031)

    # ---------------------------------------------------------------- pistol grip: lofted down its own axis
    # (its back strap, front strap, width and length are the ones the firing hand is fitted to)
    GR = G.Limb([(-.006, -.024, .03, .0145, 3.0), (.01, -.0255, .0318, .0152, 2.8), (.025, -.0268, .0316, .0156, 2.7), (.04, -.0258, .0296, .016, 2.7),
                 (.055, -.0272, .0268, .0163, 2.7), (.07, -.026, .0262, .016, 2.7), (.085, -.0272, .0266, .0156, 2.7), (.1, -.0262, .0274, .0154, 2.8),
                 (.112, -.024, .028, .0152, 3.0), (.119, -.021, .0275, .0146, 3.2)], .32, 0.0, .024)
    GR.skin(P, OD, 'grip', step=.005, n=32)
    GR.checker(P, 'grip_checker', RB, .034, .098, -.8, .8, 15, 12, .0006, d=.0002)
    c = GR.pt(.016, .1, .0002)
    P.append(lathe_x('grip_screw', [(0, .0034), (.0012, .0034), (.0018, .0024), (.0018, 0)], c, S, 12, 1))
    P.append(G.rprism('grip_plug', [GR.g(-.02, .118), GR.g(.027, .1145), GR.g(.0275, .1185), GR.g(-.0195, .1225)], .026, PO, .003))

    # ---------------------------------------------------------------- magazine: curved, pressed ribs, floor plate, lips
    prof = G.arc_profile(-.085, .02, .5, .064, .29, 14)
    MAG = [G.rprism('magbody', prof, .03, S, .004, 3)]
    for dr in (.013, .032, .051):
        MAG.append(plate('magrib', G.arc_strip(-.085, .02, .5, .5 - dr + .0036, .5 - dr - .0036, .035, .27), S, .0142, .0172, .001))
    for t0 in (.09, .19):                                             # two pressed bands across it
        MAG.append(plate('magband', G.arc_strip(-.085, .02, .5, .497, .439, t0, t0 + .012, 3), S, .0142, .0166, .0006))
    MAG.append(prism('floorplate', G.arc_floor(-.085, .02, .5, .064, .29, .009), .034, S, .002))
    fl = G.arc_floor(-.085, .02, .5, .064, .29, .009)
    MAG.append(prism('floor_catch', [fl[3], (fl[3][0] + .006, fl[3][1] + .003), (fl[0][0] + .006, fl[0][1] + .012), (fl[0][0] + .001, fl[0][1] + .01)], .01, PK, .001))
    G.feed_lips(MAG, -.085, -.149, .02, .03, S, M['brass'])
    sz = .1195
    finish('gun_rifle', P, (0, -.69, zb), (0, -.345, .012), (0, .06, sz), rail=(0, -.335, .117),
           moving=[('mag', MAG, (0, -.149, .02)), ('bolt', BOLT, (RIGHT * .049, -.128, .074))])


def carbine():
    """Carbine (a modern alloy gun, our own pattern): an upper and a lower lofted as two halves that meet in a
    parting line; the magazine well forged as its own deep form with a fence and a flared mouth; a free-floating
    handguard tube of ten bars; a stepped barrel with its gas block and tube, a pronged hider; a collapsing stock on
    a buffer tube with a shaped cheek piece and a ribbed pad; a lofted grip; a curved magazine; folding irons."""
    bl.reset(); M = K.kinetic_mats(); S, PK, PO, RB = M['steel'], M['park'], M['poly'], M['rubber']
    zb = .066; P = []
    pi = math.pi
    # ---------------------------------------------------------------- upper half
    U = G.Body([(.102, .05, .088, .0145, 4.0), (.085, .047, .09, .016, 5.0), (.05, .046, .09, .0165, 5.5), (.01, .046, .09, .0165, 5.5), (-.02, .046, .09, .0172, 5.5),
                (-.06, .046, .09, .0172, 5.5), (-.09, .046, .09, .0165, 5.5), (-.115, .047, .09, .0165, 5.0), (-.13, .05, .09, .0172, 3.4), (-.139, .052, .088, .0178, 2.4)])
    U.skin(P, PK, 'upper', step=.007, n=36)
    U.shell(P, 'upper_cheek', PK, .09, .012, U.af(.1), U.af(.8), t=.0014, ch=.0012)
    U.shell(P, 'upper_boss', PK, -.07, -.124, U.af(-.2), U.af(.8), t=.0016, ch=.0012)
    U.shell(P, 'upper_strake', PK, .0, -.062, U.af(.1), U.af(.8), t=.0014, ch=.0012, mirror=False, side=1)
    xp = U.pt(-.03, .3, .0004)[0]
    G.port(P, -.004, -.056, .06, .0765, xp, RB, None, side=-1, door_m=PK)
    BOLT = [plate('boltface', [(-.006, .0615), (-.006, .075), (-.054, .075), (-.054, .0615)], S, .008, xp - .001, .0008, sym=False, side=-1)]
    P += [G.rprism('deflector', [(.05, .062), (.03, .078), (.022, .078), (.026, .06)], .008, PK, .002, x=RIGHT * .0185),
          lathe_x('fwdassist', [(0, .0075), (.008, .0075), (.0095, .006), (.0095, 0)], (RIGHT * .016, .075, .07), PK, 20, -1)]
    CHARGE = [prism('chandle', [(.128, .0815), (.128, .0905), (.1, .0905), (.096, .0815)], .03, PK, .0015),
              prism('chlatch', [(.124, .083), (.124, .089), (.108, .089), (.108, .083)], .04, S, .001)]
    # ---------------------------------------------------------------- lower half and the forged magazine well
    Lw = G.Body([(.102, .026, .049, .0145, 4.0), (.085, .017, .049, .016, 5.0), (.05, .014, .049, .0165, 5.5), (.02, .015, .049, .0165, 5.5), (-.01, .016, .049, .0165, 5.5),
                 (-.04, .017, .049, .0168, 5.5), (-.075, .018, .049, .0172, 5.5), (-.11, .018, .049, .0172, 5.5), (-.13, .02, .049, .017, 5.0), (-.142, .026, .049, .0162, 4.0)])
    Lw.skin(P, PK, 'lower', step=.007, n=36)
    Lw.shell(P, 'lower_step', PK, .092, -.034, Lw.af(-.7), Lw.af(.55), t=.0014, ch=.0012)
    Wl = G.Body([(-.042, -.002, .03, .0162, 5.0), (-.05, -.02, .03, .0178, 6.0), (-.066, -.03, .03, .0186, 6.0), (-.086, -.035, .03, .0188, 6.0), (-.106, -.038, .03, .0188, 6.0),
                 (-.122, -.038, .03, .0186, 6.0), (-.131, -.024, .03, .018, 5.0), (-.138, -.002, .03, .0166, 4.0)])
    Wl.skin(P, PK, 'well', step=.006, n=36)
    Wl.shell(P, 'well_mouth', PK, -.052, -.128, -1.5, -.7, t=.0022, base=-.002)
    Wl.shell(P, 'well_fence', PK, -.058, -.124, Wl.af(-.45), Wl.af(.1), t=.0013, ch=.0012)
    for y, z in ((.082, .034), (-.122, .034)):                         # pivot and takedown pins in their bosses
        x = Lw.pt(y, 0, .0002)[0]
        G.rivets(P, [(y, z)], x, PK, .0058)
        P.append(K.cylx('pin', .0026, 2 * x + .0034, (0, y, z), S, 14, .0005))
    xs = Lw.pt(.05, 0, .0016)[0]
    G.selector(P, .05, .032, xs, S, 1, ang=.4, L=.02)
    for y, z in ((.066, .04), (.036, .022)):
        P.append(lathe_x('sel_stop', [(0, .0016), (.0016, .0016), (.002, .0009), (.002, 0)], (xs, y, z), S, 10, 1))
    P += [lathe_x('magrelease', [(0, .0046), (.003, .0046), (.0038, .0036), (.0038, 0)], (RIGHT * (Wl.pt(-.05, .2, 0)[0] + .0002), -.049, .024), S, 16, -1),
          plate('boltcatch', [(-.03, .047), (-.03, .034), (-.05, .034), (-.05, .047)], S, .0162, .0196, .0008, sym=False, side=1)]
    G.guard(P, PK, [(-.05, .014), (-.052, -.01), (-.044, -.024), (-.03, -.03), (-.014, -.03), (-.006, -.026)], .012, .0046, r=.0018)
    G.trigger(P, S, -.024, .016, L=.03)
    k_grip(P, PO, RB, .33, .11, .03, .016)
    # ---------------------------------------------------------------- buffer tube and the collapsing stock
    P.append(G.tube_('buffer', .33, .1, .0155, PK, .065, n=36))
    P.append(lathe('castlenut', [(.116, 0), (.116, .02), (.102, .02), (.102, 0)], S, .065, 0, 12, sharp=20))
    P.append(G.rprism('endplate', [(.1, .04), (.1, .09), (.105, .09), (.105, .04)], .034, S, .003))
    for i in range(4):
        P.append(G.band('buffer_groove', .135 + i * .014, .003, .0162, S, .065, 0, .0022, 36, .0005))
    P.append(G.sloft('stock_body', [(.19, .044, .0865, .0185, 3.0, 1.0), (.215, .03, .0885, .019, 2.8, 1.12), (.25, .006, .0895, .0188, 2.8, 1.18), (.29, -.02, .089, .019, 3.0, 1.12),
                                    (.325, -.04, .0865, .0196, 3.2, 1.02), (.35, -.048, .082, .0196, 3.6, 1.0)], PO, 28, 4))
    G.slots(P, 'stock_cut', [(.3, .03, .04, .012, -.5)], .0188, RB, lift=.0006)
    P.append(G.rprism('stock_latch', [(.2, .04), (.25, .016), (.246, .01), (.2, .03)], .012, S, .003))
    G.ribbed_pad(P, RB, .35, .082, -.048, .04, 6, .014)
    P += K.sling_loop(.31, -.046, S)
    # ---------------------------------------------------------------- the free-floating handguard tube, barrel group
    G.cage(P, 'handguard', -.14, -.432, zb, .029, PK, t=.004, bars=10, fill=.7, frames=((-.14, .016), (-.236, .007), (-.33, .007), (-.42, .012)), phase=pi / 2)
    P.append(lathe('barrelnut', [(-.128, 0), (-.128, .0225), (-.146, .0225), (-.146, 0)], S, zb, 0, 12, sharp=20))
    for y in (-.148, -.24, -.334, -.426):
        G.hexbolts(P, [(y, zb - .012), (y, zb + .012)], .0298, S, .002)
    P += K.rail(M, .1, -.43, .09, .022, PK)
    G.barrel_stepped(P, 'barrel', [(-.13, .0118), (-.19, .0092), (-.372, .0085), (-.49, .0098), (-.51, .0085), (-.535, .0085)], zb, S, .004)
    G.gas_block(P, -.348, .024, zb, zb + .017, S, r=.0128)
    P.append(G.tube_('gastube', -.14, -.36, .003, S, zb + .017, n=12))
    G.hider(P, 'flashhider', -.53, zb, .0112, .056, S, 4)
    # ---------------------------------------------------------------- magazine
    MAG = [G.rprism('magbody', [(-.058, .012), (-.06, -.08), (-.074, -.17), (-.088, -.205), (-.152, -.198), (-.136, -.162), (-.122, -.08), (-.118, .012)], .022, PK, .003, 3)]
    for rp in ([(-.07, -.01), (-.078, -.01), (-.094, -.185), (-.086, -.185)], [(-.092, -.01), (-.1, -.01), (-.12, -.185), (-.112, -.185)],
               [(-.108, -.01), (-.114, -.01), (-.14, -.18), (-.134, -.18)]):
        MAG.append(plate('magrib', rp, PK, .0098, .0122, .0006))
    MAG.append(G.rprism('magfloor', [(-.085, -.2), (-.156, -.193), (-.158, -.206), (-.088, -.214)], .027, PO, .003))
    G.feed_lips(MAG, -.062, -.114, .012, .022, PK, M['brass'])
    sz = .1335
    optic = []
    G.iron_rear(optic, .07, sz, PK, base_z=.0995)
    G.iron_front(optic, -.41, sz, PK, base_z=.0995)
    finish('gun_carbine', P, (0, -.585, zb), (0, -.3, .028), (0, .1, sz), optic=optic, rail=(0, -.02, .0995),
           moving=[('mag', MAG, (0, -.088, .012)), ('charge', CHARGE, (0, .112, .086)), ('bolt', BOLT, (RIGHT * .01, -.03, .068))])


def bolt_rifle():
    """Bolt-action precision rifle: a round action (a turned receiver with its ring and bridge, the port between
    them, a bolt with a knurled knob, shroud and cocking piece) bedded in a chassis stock lofted from the action's
    tail to the forend's tip; the heavy fluted barrel floats over the forend with a visible gap; bottom metal with a
    detachable box; a thumbhole butt through ten sections with an adjustable cheek piece; a folded bipod."""
    bl.reset(); M = K.kinetic_mats(); S, PK, OD, RB = M['steel'], M['park'], M['odg'], M['rubber']
    zb = .077; P = []
    # ---------------------------------------------------------------- the chassis: twelve sections; the barrel floats
    CH = G.Body([(.14, .03, .06, .022, 4.0), (.1, .02, .062, .026, 4.5), (.04, .016, .062, .0275, 4.8), (-.03, .016, .064, .0285, 4.8), (-.1, .018, .064, .0285, 4.8),
                 (-.16, .022, .062, .0285, 4.8), (-.2, .026, .058, .028, 4.6), (-.3, .028, .057, .0272, 4.4), (-.4, .03, .056, .026, 4.4), (-.48, .032, .056, .0245, 4.2),
                 (-.515, .036, .055, .022, 4.0), (-.532, .042, .054, .018, 3.4)])
    CH.skin(P, OD, 'chassis', step=.008, n=36)
    CH.shell(P, 'bed_panel', OD, .09, -.15, CH.af(-.5, 0), CH.af(.6, 0), t=.0016, ch=.0014)
    for ya, yb in ((-.21, -.3), (-.312, -.402), (-.414, -.5)):
        CH.shell(P, 'fore_panel', OD, ya, yb, CH.af(-.55, -.3), CH.af(.55, -.3), t=.0016, ch=.0014)
    CH.checker(P, 'fore_checker', OD, -.23, -.48, CH.af(-.95, -.3), CH.af(-.68, -.3), 44, 4, .0006)
    for y in (-.06, .09, -.2):
        x = CH.pt(y, 0, .0018)
        G.rivets(P, [(y, x[2])], x[0], S, .003)
    for y in (-.05, .1):
        P.append(lathe_z('pillar_screw', [(-.003, 0), (-.003, .0045), (-.001, .0052), (0, .0052), (0, 0)], (0, y, CH.sec(y)[0] + .0005), S, 6))
    # ---------------------------------------------------------------- the action: ring, port, bridge; rail; bolt
    P.append(lathe('receiver', [(.13, 0), (.13, .0205), (.127, .022), (.062, .022), (.058, .0198), (-.083, .0198), (-.087, .0225), (-.137, .0225), (-.14, .0205), (-.14, 0)],
                   S, zb, 0, 44))
    P.append(plate('port', [(.03, zb - .002), (.03, zb + .014), (-.04, zb + .014), (-.04, zb - .002)], RB, .0165, .0202, .0008, sym=False, side=-1))
    P.append(G.rprism('recoillug', [(-.124, .04), (-.124, .07), (-.138, .07), (-.138, .04)], .03, S, .004))
    P.append(plate('boltstop', [(.085, zb - .004), (.085, zb + .006), (.06, zb + .006), (.056, zb - .004)], S, .0195, .0236, .0008, sym=False, side=1))
    P.append(lathe_x('safety', [(0, .0048), (.003, .0048), (.0038, .0036), (.0038, 0)], (RIGHT * .0205, .14, zb + .006), S, 16, -1))
    P.append(plate('safety_lever', [(.142, zb + .004), (.158, zb + .016), (.154, zb + .019), (.138, zb + .008)], S, .0236, .0262, .0007, sym=False, side=-1))
    kc = (RIGHT * .054, .1205, zb - .0305)
    BOLT = [G.tube_('bolt', .05, -.05, .0125, PK, zb, n=24), G.tube_('shroud', .16, .125, .016, S, zb, n=28),
            G.band('shroudring', .13, .005, .0172, S, zb, 0, .003, 28, .0006), G.band('bolt_collar', .121, .008, .0185, PK, zb, 0, .003, 28, .0008),
            lathe('cockpiece', [(.172, 0), (.172, .006), (.16, .009), (.16, 0)], PK, zb, 0, 16),
            rod('boltroot', (RIGHT * .01, .112, zb + .002), (RIGHT * .03, .114, zb - .006), .0062, S),
            rod('boltarm', (RIGHT * .03, .114, zb - .006), (RIGHT * .058, .12, zb - .03), .0048, S),
            lathe_x('boltknob', [(0, .0045), (.004, .0098), (.012, .012), (.019, .0105), (.023, .0055), (.023, 0)], kc, PK, 24, -1)]
    for dx in (.007, .011, .015):                                    # the knob's knurl: three raised rings
        BOLT.append(lathe_x('knob_knurl', [(dx, .0114), (dx, .0126), (dx + .002, .0126), (dx + .002, .0114)], kc, PK, 24, -1, closed=True))
    P += K.rail(M, .12, -.13, .097, .022, PK)
    # ---------------------------------------------------------------- the barrel: heavy, six lands, the brake
    V.barrel('barrel', M, -.14, -.78, zb, .0148, P, m=S, rings=[(-.165, .0185, .03)])
    for k in range(6):
        a = math.pi / 6 + k * math.pi / 3
        P.append(G.bar('land', -.2, -.72, .0142, .017, a - .22, a + .22, S, zb, 0, 2))
    G.brake(P, 'brake', -.775, zb, .021, .09, S, RB, 3, bore=.008)
    P.append(G.band('brakering', -.778, .006, .0222, PK, zb, 0, .003, 32, .0006))
    P.append(G.band('muzzle_thread', -.768, .008, .0162, PK, zb, 0, .0025, 32, .0006))
    # ---------------------------------------------------------------- bottom metal, guard, box, bipod
    P.append(G.rprism('bottommetal', [(.0, .0115), (.0, .0205), (-.2, .0205), (-.21, .0165), (-.2, .0115)], .037, S, .003))
    G.guard(P, S, [(-.08, .016), (-.081, -.008), (-.072, -.022), (-.056, -.028), (-.024, -.028), (-.008, -.022)], .012, .0048, r=.0018)
    G.trigger(P, S, -.04, .02, L=.03)
    P.append(G.rprism('mag', [(-.086, .02), (-.086, -.035), (-.094, -.045), (-.152, -.045), (-.158, -.035), (-.158, .02)], .033, M['poly'], .004, 3))
    for yy in (-.1, -.132):
        P.append(plate('magrib', [(yy, .008), (yy - .006, .008), (yy - .006, -.036), (yy, -.036)], M['poly'], .0155, .0177, .0006))
    P.append(G.rprism('magfloor', [(-.09, -.042), (-.154, -.042), (-.155, -.051), (-.091, -.051)], .037, PK, .003))
    P.append(G.rprism('magrel', [(-.074, .006), (-.074, -.008), (-.086, -.008), (-.086, .006)], .012, S, .003))
    P.append(G.rprism('bipodclamp', [(-.485, .014), (-.485, .034), (-.515, .034), (-.515, .014)], .044, PK, .005))
    for s in (1, -1):
        P += [G.tube_('bipodleg', -.49, -.69, .0055, PK, .012, s * .014, n=16), G.tube_('bipodext', -.68, -.74, .0042, S, .012, s * .014, n=12),
              lathe('bipodfoot', [(-.737, 0), (-.737, .008), (-.752, .008), (-.752, 0)], RB, .012, s * .014, 14)]
    # ---------------------------------------------------------------- grip and the thumbhole butt
    k_grip(P, OD, RB, .2, .118, .034, .022, plug_m=PK)
    P.append(G.sloft('butt', [(.11, .03, .062, .024, 4.0, 1.0), (.14, .03, .074, .0232, 3.6, 1.0), (.17, .03, .086, .0225, 3.4, .95), (.22, .028, .094, .022, 3.2, .9),
                              (.28, .006, .0945, .0222, 3.2, .88), (.34, -.02, .0945, .0225, 3.2, .88), (.39, -.05, .0945, .023, 3.4, .9),
                              (.44, -.078, .094, .0235, 3.6, .95), (.46, -.088, .092, .0235, 3.8, 1.0), (.472, -.094, .09, .0235, 4.0, 1.0)], OD, 28, 4))
    P.append(G.rprism('limb', [(.044, -.076), (.07, -.074), (.42, -.07), (.456, -.086), (.45, -.1), (.07, -.094), (.044, -.092)], .03, OD, .009, 4))
    P.append(G.rprism('cheek', [(.2, .09), (.212, .098), (.39, .098), (.4, .09)], .04, RB, .004))
    for yy in (.24, .36):
        P.append(lathe_z('cheekpost', [(-.016, 0), (-.016, .004), (0, .004), (0, 0)], (0, yy, .092), S, 12))
    P.append(lathe_x('cheekknob', [(0, .0105), (.007, .0105), (.009, .0085), (.009, 0)], (.0215, .3, .07), PK, 20, 1))
    P.append(G.rloft('buttspacer', [(.4715, -.095, .091, .0242, 4.0), (.4765, -.095, .091, .0242, 4.0)], S, n=28))
    G.ribbed_pad(P, RB, .4765, .09, -.094, .049, 7, .016)
    P.append(lathe_z('monopod', [(-.04, 0), (-.04, .009), (-.034, .009), (-.032, .006), (0, .006), (0, 0)], (0, .41, -.096), PK, 14))
    P += K.sling_loop(.3, -.104, S) + K.sling_loop(-.5, .02, S, x=.03)
    ROUND = [lathe('rd_case', [(.03, 0), (.03, .0058), (.028, .0062), (-.02, .0062), (-.032, .0042), (-.032, 0)], M['brass'], .3, 0, 12),
             lathe('rd_nose', [(-.032, 0), (-.032, .0042), (-.044, .003), (-.05, .0012), (-.05, 0)], M['steel'], .3, 0, 12)]
    finish('gun_bolt', P, (0, -.865, zb), (0, -.36, .02), (0, .2, .14), rail=(0, -.005, .1065),
           moving=[('bolt', BOLT, (0, .05, zb))], loose=[('x_round', ROUND, (0, 0, .3))])


def service_pistol():
    """Service pistol, slide and frame as lofts. The polymer frame runs through ten sections from the tang over the
    hand to the dust cover, whose rail is real teeth; an undercut guard with section. The steel slide (the part
    `slide`) through eight sections with grasping serrations front and rear cut below the surface, a flat along each
    flank, the ejection port wrapped over the top with the barrel's hood in it, an extractor, an optic plate, three-
    dot sights, a striker plate. A crowned barrel and guide rod; slide stop, take-down lever, thumb safety, magazine
    release; a checkered grip panel with its screws; a magazine with witness holes and a toe on its base."""
    bl.reset(); M = K.kinetic_mats(); S, PK, PO, PA, RB = M['steel'], M['park'], M['poly'], M['paint'], M['rubber']
    P = []
    g = G.hand_grip(P, PO, .3, .1, .03, z=.022, ext=.01)
    P.append(plate('grip_panel', [g(-.015, .03), g(.017, .026), g(.019, .058), g(.016, .1), g(-.013, .103), g(-.017, .06)], RB, .01, .0158, .001))
    G.checker(P, 'grip_checker', [g(-.014, .032), g(.016, .028), g(.015, .098), g(-.012, .101)], .016, RB, 14, 24, .0006)
    for b in (.03, .1):
        c = g(.018, b)
        G.rivets(P, [c], .0158, S, .0016)
    # ---------------------------------------------------------------- the frame: ten sections
    F = G.Body([(.057, .041, .0495, .0075, 3.0), (.046, .032, .05, .0128, 4.5), (.034, .02, .05, .0146, 5.0), (.0, .018, .05, .015, 5.0), (-.026, .019, .05, .015, 5.0),
                (-.032, .022, .05, .015, 5.0), (-.098, .022, .05, .015, 5.5), (-.106, .03, .05, .015, 5.5), (-.15, .03, .05, .0148, 5.5), (-.16, .032, .05, .014, 4.5)])
    F.skin(P, PO, 'frame', step=.005, n=32)
    F.shell(P, 'frame_panel', PO, .02, -.09, F.af(-.5), F.af(.45), t=.0009, ch=.001)
    F.slats(P, 'rail_tooth', PO, -.112, -.154, -1.48, -1.08, 4, share=.6, t=.002, base=-.001)
    G.guard(P, PO, [(-.086, .026), (-.088, .002), (-.078, -.012), (-.06, -.018), (-.03, -.018), (-.012, -.013)], .0135, .0058)
    G.trigger(P, PK, -.044, .024, L=.03)
    xf = F.pt(-.04, .1, .0002)[0]
    P += [plate('slidestop', [(-.004, .0475), (-.05, .0465), (-.064, .0405), (-.058, .0385), (-.046, .0425), (-.008, .0425)], S, xf - .0008, xf + .0022, .0006, sym=False, side=1),
          plate('takedown', [(-.079, .045), (-.079, .039), (-.092, .039), (-.092, .045)], S, xf - .0008, xf + .0022, .0006, sym=False, side=1),
          lathe_x('magrelease', [(0, .0044), (.003, .0044), (.0036, .0034), (.0036, 0)], (xf, -.012, .017), PK, 16, 1)]
    G.selector(P, .03, .041, xf, S, 1, ang=.3, L=.014, r=.0034)
    G.rivets(P, [(-.094, .04), (.02, .04), (-.016, .04)], xf, S, .0018)
    # ---------------------------------------------------------------- the slide: eight sections, serrations cut into it
    SLIDE = []
    SL = G.Body([(.041, .05, .0785, .0132, 4.5), (.036, .048, .079, .0142, 5.5), (.0, .048, .079, .0142, 5.5), (-.05, .048, .079, .0142, 5.5), (-.1, .048, .079, .0142, 5.5),
                 (-.14, .048, .079, .0142, 5.5), (-.152, .049, .078, .0136, 5.0), (-.16, .051, .076, .0125, 4.0)])
    cuts = []                                                          # grasping serrations: real grooves cut below the surface
    for y0_, y1_, k_ in ((.035, .006, 7), (-.102, -.13, 6)):
        pitch = (y0_ - y1_) / k_
        cuts += [(y0_ - (i + .3) * pitch, y0_ - (i + .75) * pitch, SL.af(-.5), SL.af(.86), .001) for i in range(k_)]
    SL.skin(SLIDE, S, 'slide', step=.005, n=48, cuts=cuts)
    SL.shell(SLIDE, 'slide_flat', S, .002, -.096, SL.af(-.55), SL.af(.3), t=.0009, ch=.001)
    SL.shell(SLIDE, 'ejport', RB, -.01, -.05, SL.af(.35), 1.3, t=.0003, ch=.0005, mirror=False, side=-1)
    SL.shell(SLIDE, 'extractor', PK, -.002, -.034, SL.af(.05), SL.af(.3), t=.0012, ch=.0006, mirror=False, side=-1)
    SLIDE.append(prism('optic_plate', [(-.028, .0786), (-.028, .0796), (-.072, .0796), (-.072, .0786)], .022, PK, .0004))
    for yy in (-.034, -.066):
        for xx in (.0075, -.0075):
            SLIDE.append(lathe_z('plate_screw', [(0, 0), (0, .0016), (.0003, .0016), (.0003, 0)], (xx, yy, .0796), S, 10))
    for i in range(22):
        y = .016 - i * .0068
        if -.076 < y < -.022:
            continue
        SLIDE.append(prism('top_serration', [(y, .0789), (y, .0795), (y - .003, .0795), (y - .003, .0789)], .011, PK, .0002))
    SLIDE.append(G.rprism('striker_plate', [(.0412, .053), (.0412, .074), (.0398, .074), (.0398, .053)], .02, PK, .002))
    SLIDE.append(lathe('striker', [(.0418, 0), (.0418, .0022), (.0408, .0022), (.0408, 0)], S, .066, 0, 12))
    P.append(SL_hood(SL, PK))
    P.append(G.tube_('guiderod', -.15, -.1605, .0042, PK, .0545, n=16))
    G.muzzle(P, 'crown', -.14, -.163, .062, .0068, PK, .0045, dark_m=RB)
    sz = .0835
    SLIDE.append(prism('rear_base', [(.037, .079), (.037, .0815), (.024, .0815), (.02, .079)], .026, S, .001))
    for s, nm in ((1, 'rearL'), (-1, 'rearR')):
        SLIDE.append(prism(nm, [(.0365, sz - .0045), (.0365, sz + .002), (.027, sz + .002), (.025, sz - .0045)], .0085, S, .0008, x=s * .0078))
        SLIDE.append(lathe('rdot', [(.0367, 0), (.0367, .0017), (.0363, .0017), (.0363, 0)], PA, sz - .0015, s * .0078, 8))
    SLIDE.append(prism('frontpost', [(-.138, .079), (-.142, sz + .002), (-.149, sz + .002), (-.153, .079)], .0036, S, .0006))
    SLIDE.append(lathe('fdot', [(-.1418, 0), (-.1418, .0016), (-.1422, .0016), (-.1422, 0)], PA, sz, 0, 8))
    # ---------------------------------------------------------------- the magazine
    MAG = [prism('magbody', [g(-.0105, .01), g(.0185, .01), g(.0185, .116), g(-.0105, .118)], .021, S, .0015),
           G.rprism('magbase', [g(-.0202, .1145), g(.0282, .1105), g(.029, .121), g(-.0245, .1265)], .03, PO, .0035)]
    t = g(-.002, .012)
    MAG.append(G.tube_('magtop', t[0] + .012, t[0] - .012, .0045, M['brass'], t[1], n=12))
    for k in range(5):
        c = g(.0186, .03 + k * .016)
        MAG.append(lathe('witness', [(c[0] + .0004, 0), (c[0] + .0004, .0016), (c[0] - .0002, .0016), (c[0] - .0002, 0)], RB, c[1], 0, 8))
    top = g(.004, .01)
    finish('gun_pistol', P, (0, -.165, .062), (0, -.02, -.035), (0, .07, sz), rail=(0, -.05, .078),
           moving=[('mag', MAG, (0, top[0], top[1])), ('slide', SLIDE, (0, -.06, .062))])


def pump_shotgun():
    """Pump shotgun: a round-topped steel receiver lofted through ten sections (the ejection port with the bolt in
    it, the loading port and lifter underneath, a milled flat low on each flank); a barrel under a vent rib over the
    magazine tube, a barrel band and a knurled cap; a corncob fore-end that wraps the tube; a walnut stock with real
    drop through ten sections, its pistol grip, a spacer and a pad; a saddle of shells. Raised sights: a ghost ring
    on a stem at the receiver's rear and a post on a ramp at the muzzle, 3.1 cm over the receiver."""
    bl.reset(); M = K.kinetic_mats(); S, PK, W, RB, BR = M['steel'], M['park'], M['wood'], M['rubber'], M['brass']
    shell = bl.mat('gun_shell', '#8c1a1a', 0, .55)
    zb = .08; P = []
    R = G.Body([(.092, .034, .096, .0185, 3.2), (.075, .03, .1, .0205, 3.4), (.04, .03, .1, .021, 3.6), (.0, .03, .1, .021, 3.6), (-.04, .03, .1, .0214, 3.6),
                (-.08, .03, .1, .0214, 3.6), (-.115, .03, .1, .021, 3.6), (-.145, .031, .1, .0205, 3.4), (-.162, .034, .098, .0195, 3.0), (-.172, .038, .094, .018, 2.6)])
    R.skin(P, PK, 'receiver', step=.007, n=36)
    R.shell(P, 'receiver_flat', PK, .078, -.14, R.af(-.72), R.af(-.05), t=.0014, ch=.0014)
    R.shell(P, 'receiver_brow', PK, .078, .0, R.af(.25), R.af(.75), t=.0012, ch=.0012, mirror=False, side=1)
    xr = R.pt(-.05, .25, .0004)[0]
    G.port(P, -.012, -.088, .061, .088, xr, RB, S, side=-1)
    P.append(prism('loadport', [(-.028, .0285), (-.028, .0315), (-.112, .0315), (-.112, .0285)], .028, RB, .0006))
    P.append(prism('lifter', [(-.036, .0272), (-.036, .0296), (-.1, .0296), (-.106, .0272)], .022, S, .0005))
    for y, z in ((.022, .045), (-.05, .045)):
        P.append(K.cylx('pin', .0026, 2 * R.pt(y, 0, 0)[0] + .003, (0, y, z), S, 14, .0005))
    for y, a in ((.07, .5), (-.138, .5)):
        x = R.pt(y, a, .0002)
        G.rivets(P, [(y, x[2])], x[0], S, .002)
    P.append(plate('shell_latch', [(-.03, .034), (-.03, .0385), (-.07, .0385), (-.074, .034)], S, .0195, .0226, .0007, sym=False, side=-1))
    # ---------------------------------------------------------------- barrel group
    P.append(G.tube_('barrel', -.16, -.72, .0115, S, zb, bore=.0095, n=32))
    P.append(G.band('muzzle_ring', -.708, .012, .0125, S, zb, 0, .003, 32, .0008))
    P.append(prism('ventrib', [(-.165, .0945), (-.165, .0975), (-.715, .0975), (-.715, .0945)], .008, S, .0006))
    for i in range(10):
        P.append(prism('ribpost', [(-.188 - i * .05, .0895), (-.188 - i * .05, .0945), (-.193 - i * .05, .0945), (-.193 - i * .05, .0895)], .004, S, .0004))
    P.append(G.tube_('magtube', -.16, -.66, .0125, S, .046, n=28))
    P.append(lathe('magcap', [(-.655, 0), (-.655, .0145), (-.684, .0145), (-.69, .011), (-.69, 0)], S, .046, 0, 28))
    for i in range(3):
        P.append(G.band('capring', -.66 - i * .007, .003, .0153, PK, .046, 0, .002, 28, .0004))
    P.append(G.band('band_barrel', -.6, .018, .0146, S, zb, 0, .0032, 28, .001))
    P.append(G.band('band_tube', -.6, .018, .0156, S, .046, 0, .0032, 28, .001))
    P.append(prism('band_web', [(-.6, .058), (-.6, .069), (-.618, .069), (-.618, .058)], .013, S, .001))
    P.append(lathe_x('band_screw', [(0, .003), (.0015, .003), (.0022, .002), (.0022, 0)], (.0065, -.609, .0635), PK, 12, 1))
    # ---------------------------------------------------------------- the corncob fore-end on its bars
    PUMP = [G.sloft('forend', [(-.268, .03, .064, .024, 3.5), (-.285, .022, .068, .029, 4.0), (-.36, .02, .068, .03, 4.0), (-.44, .022, .068, .029, 4.0),
                               (-.456, .03, .064, .024, 3.5)], W, n=24, sub=3)]
    for i in range(9):
        y = -.297 - i * .0165
        PUMP.append(G.rloft('forend_rib', [(y, .0188, .0692, .0312, 4.0), (y - .0075, .0188, .0692, .0312, 4.0)], W, n=24))
    for s in (1, -1):
        PUMP.append(prism('actionbar', [(-.14, .047), (-.14, .053), (-.27, .053), (-.27, .047)], .003, S, .0006, x=s * .0165))
    PUMP.append(G.band('forend_nut', -.458, .008, .0155, S, .046, 0, .003, 24, .0008))
    # ---------------------------------------------------------------- the stock: real drop, ten sections; grip, pad
    P.append(G.sloft('stock', [(.084, .032, .099, .0205, 4.6, 1.0), (.098, .03, .084, .0195, 3.8, 1.0), (.115, .028, .07, .0188, 3.2, .95), (.14, .024, .06, .0182, 2.8, .9),
                               (.18, .016, .056, .018, 2.6, .88), (.24, .0, .052, .0186, 2.6, .85), (.3, -.022, .047, .0195, 2.7, .85), (.36, -.044, .041, .0202, 2.9, .88),
                               (.41, -.06, .036, .0206, 3.2, .92), (.432, -.068, .032, .0206, 3.6, .95)], W, n=28, sub=4))
    P.append(G.rprism('stock_grip', G.chaikin([(.03, .034), (.004, -.03), (.012, -.088), (.04, -.1), (.07, -.09), (.098, -.02), (.128, .032), (.09, .045)], 2,
                                              sharp=(0, 7)), .037, W, .012, 4))
    G.checker(P, 'grip_checker', [(.026, -.04), (.058, -.044), (.051, -.078), (.031, -.08)], .0186, W, 10, 11, .0007)
    P.append(G.rprism('gripcap', [(.013, -.0885), (.041, -.1005), (.069, -.0905), (.068, -.0965), (.041, -.1065), (.011, -.0945)], .03, S, .003))
    P.append(G.rloft('buttspacer', [(.4315, -.069, .033, .0212, 3.6), (.4355, -.069, .033, .0212, 3.6)], S, n=28))
    G.ribbed_pad(P, RB, .4355, .032, -.068, .041, 5, .015)
    G.guard(P, PK, [(-.094, .032), (-.096, .004), (-.086, -.012), (-.066, -.019), (-.02, -.019), (-.004, -.012)], .012, .0048, r=.0018)
    G.trigger(P, S, -.04, .03, L=.032)
    xs = R.pt(.052, 0, .0004)[0]
    for s in (1, -1):
        P.append(lathe_x('crossbolt', [(0, .0042), (.002, .0042), (.0028, .003), (.0028, 0)], (s * xs, .052, .05), S, 12, s))
    P += [lathe_z('safety', [(0, 0), (0, .0045), (.004, .0045), (.005, .0035), (.005, 0)], (0, .078, .0985), S, 12),
          plate('slidelever', [(-.066, .028), (-.066, .02), (-.084, .02), (-.084, .028)], S, .005, .0075, .0006, sym=False, side=1)]
    G.swivel(P, .37, -.0465, S)
    P += K.sling_loop(-.64, .028, S)
    P.append(plate('saddle', [(-.01, .044), (-.01, .09), (-.11, .09), (-.11, .044)], M['poly'], .0205, .0262, .0012, sym=False, side=1))
    for i in range(4):
        y = -.03 - i * .02
        P += [lathe_z('shell', [(0, 0), (0, .0092), (.044, .0092), (.046, .0086), (.046, 0)], (.035, y, .048), shell, 16),
              lathe_z('shellbase', [(-.012, 0), (-.012, .0098), (0, .0098), (0, 0)], (.035, y, .048), BR, 16)]
    P += K.rail(M, .056, -.026, .0925, .02, PK)
    # ---------------------------------------------------------------- raised sights: a ghost ring and a post on a ramp
    sz = .131
    G.iron_rear(P, .075, sz, S, base_z=.0985, w=.018)
    P.append(prism('front_base', [(-.652, .0975), (-.688, .1245), (-.708, .1245), (-.714, .0975)], .008, S, .001))
    P.append(prism('post', [(-.693, .1235), (-.695, sz), (-.701, sz), (-.703, .1235)], .0026, S, .0004))
    P.append(lathe('postdot', [(-.6928, 0), (-.6928, .0012), (-.6932, .0012), (-.6932, 0)], BR, sz - .0022, 0, 8))
    SHELL = [lathe('sh_hull', [(.02, 0), (.02, .0092), (-.03, .0092), (-.032, .0086), (-.032, 0)], shell, .3, 0, 14),
             lathe('sh_base', [(.032, 0), (.032, .0098), (.02, .0098), (.02, 0)], BR, .3, 0, 14)]
    finish('gun_pump', P, (0, -.72, zb), (0, -.36, .012), (0, .075, sz), rail=(0, .015, .102),
           moving=[('pump', PUMP, (0, -.36, .046))], loose=[('x_shell', SHELL, (0, 0, .3))])


def compact_smg():
    """Compact SMG: a stamped tube receiver with pressed stiffening rings; the magazine housing welded under it (the
    weld's bead shows), a polymer trigger housing behind; a ventilated barrel shroud of eight bars over a ribbed hand
    panel; a charging tube with a forward handle along the top left; a stock of two rods that lies folded along the
    right side, its plate flat against the shroud, clear of the sight line; a straight magazine; a stubby fore grip."""
    bl.reset(); M = K.kinetic_mats(); S, PK, PO, RB = M['steel'], M['park'], M['poly'], M['rubber']
    zb = .068; P = []
    T = G.Body([(.078, .054, .088, .017, 2.2), (.07, .05, .092, .021, 2.2), (.03, .05, .092, .021, 2.2), (-.02, .05, .092, .021, 2.2), (-.07, .05, .092, .021, 2.2),
                (-.12, .05, .092, .021, 2.2), (-.16, .05, .092, .021, 2.2), (-.172, .052, .09, .019, 2.2)])
    T.skin(P, S, 'receiver', step=.007, n=40)
    for y in (.064, .0, -.108, -.156):
        T.collar(P, 'press_ring', S, y, .006, .0011)
    T.shell(P, 'weld_bead', S, -.036, -.104, -1.2, -1.04, t=.0013, ch=.0006)
    T.shell(P, 'side_press', S, .05, -.01, -.3, .35, t=.001, ch=.0012, mirror=False, side=1)
    xp = T.pt(-.04, .1, .0004)[0]
    G.port(P, -.016, -.064, .061, .08, xp, RB, None, side=-1)
    G.dust_cover(P, -.016, -.064, .0605, xp, S, .012)
    BOLT = [plate('boltface', [(-.018, .0625), (-.018, .0785), (-.062, .0785), (-.062, .0625)], PK, .008, xp - .001, .0008, sym=False, side=-1)]
    P.append(lathe('endcap', [(.092, 0), (.092, .014), (.088, .018), (.078, .019), (.078, 0)], S, .071, 0, 32))
    # ---------------------------------------------------------------- trigger housing (polymer) and the welded magazine housing (steel)
    Lw = G.Body([(.078, .03, .056, .0135, 4.0), (.06, .024, .056, .016, 5.0), (.02, .022, .056, .0168, 5.5), (-.02, .022, .056, .0168, 5.5), (-.04, .024, .056, .0165, 5.0)])
    Lw.skin(P, PO, 'lower', step=.007, n=32)
    Lw.shell(P, 'lower_panel', PO, .066, -.03, Lw.af(-.6), Lw.af(.3), t=.0012, ch=.0012)
    H = G.Body([(-.036, -.004, .056, .0158, 5.0), (-.046, -.014, .056, .0172, 6.0), (-.07, -.016, .056, .0176, 6.0), (-.094, -.016, .056, .0172, 6.0), (-.104, -.004, .056, .016, 5.0)])
    H.skin(P, S, 'mag_housing', step=.006, n=32)
    H.shell(P, 'well_mouth', S, -.044, -.098, -1.5, -.72, t=.002, base=-.002)
    H.shell(P, 'housing_press', S, -.05, -.092, H.af(-.4), H.af(.3), t=.001, ch=.001)
    xs = Lw.pt(.04, 0, .0014)[0]
    G.selector(P, .04, .036, xs, S, 1, ang=.4, L=.018)
    for y, z in ((.054, .044), (.026, .03)):
        P.append(lathe_x('sel_stop', [(0, .0016), (.0016, .0016), (.002, .0009), (.002, 0)], (xs, y, z), S, 10, 1))
    for y, z in ((.05, .035), (-.03, .035)):
        P.append(K.cylx('pin', .002, 2 * Lw.pt(y, 0, 0)[0] + .003, (0, y, z), S, 12, .0004))
    G.guard(P, PO, [(-.044, -.008), (-.043, -.022), (-.036, -.03), (-.022, -.032), (-.012, -.028)], .012, .0048, r=.0018)
    G.trigger(P, S, -.03, .022, L=.028)
    k_grip(P, PO, RB, .25, .108, .03, .022)
    # ---------------------------------------------------------------- shroud, hand panel, barrel, charging tube
    G.cage(P, 'handguard', -.168, -.328, zb, .0235, PK, t=.004, bars=8, fill=.6, frames=((-.168, .014), (-.246, .007), (-.316, .014)), phase=math.pi / 8)
    P.append(G.tube_('heatshield', -.17, -.324, .0135, RB, zb, n=24))
    P.append(G.sloft('hg_panel', [(-.176, .03, .05, .019, 4.0), (-.2, .024, .05, .0235, 4.4), (-.296, .024, .05, .0235, 4.4), (-.322, .03, .05, .019, 4.0)], PO, 24, 3))
    for i in range(5):
        y = -.206 - i * .02
        P.append(G.rloft('hg_panel_rib', [(y, .0228, .046, .0246, 4.4), (y - .008, .0228, .046, .0246, 4.4)], PO, n=24))
    G.barrel_stepped(P, 'barrel', [(-.172, .0105), (-.32, .0085), (-.37, .0085)], zb, S, .0045)
    G.brake(P, 'brake', -.36, zb, .0125, .052, S, RB, 3, bore=.005)
    P.append(G.tube_('chtube', -.15, -.32, .0075, S, .102, n=20))
    P.append(G.band('chtube_cap', -.314, .008, .0088, PK, .102, 0, .0088, 20, .001))
    CHARGE = [G.rprism('chhandle', [(-.264, .096), (-.264, .108), (-.276, .108), (-.276, .096)], .008, S, .002, x=.015),
              prism('chstem', [(-.267, .099), (-.267, .105), (-.273, .105), (-.273, .099)], .014, S, .001, x=.007)]
    P += K.rail(M, .07, -.16, .092, .02, PK)
    # ---------------------------------------------------------------- the stock, folded along the right side
    P.append(G.rprism('hinge', [(.078, .05), (.078, .09), (.1, .09), (.1, .05)], .03, PK, .006))
    P.append(lathe_z('hinge_pin', [(-.044, 0), (-.044, .0046), (.003, .0046), (.004, .0036), (.004, 0)], (RIGHT * .012, .09, .09), S, 12))
    for z, x in ((.09, .0285), (.036, .0235)):
        P.append(rod('stock_knuckle', (RIGHT * .01, .094, z), (RIGHT * x, .094, z), .0046, S))
        P.append(G.tube_('stockrod', .096, -.128, .0045, S, z, RIGHT * x, n=16))
    P.append(G.rprism('stock_plate', [(-.116, .026), (-.116, .1), (-.15, .1), (-.15, .026)], .007, PK, .003, x=RIGHT * .031))
    for i in range(4):
        z = .09 - i * .018
        P.append(G.rprism('plate_rib', [(-.119, z + .006), (-.119, z - .006), (-.147, z - .006), (-.147, z + .006)], .004, RB, .0015, x=RIGHT * .0362))
    # ---------------------------------------------------------------- magazine, fore grip
    MAG = [G.rprism('magbody', [(-.047, .018), (-.049, -.17), (-.091, -.17), (-.089, .018)], .024, PO, .003, 3)]
    for k in range(4):
        MAG.append(plate('magrib', [(-.052, -.03 - k * .035), (-.086, -.03 - k * .035), (-.0862, -.037 - k * .035), (-.0522, -.037 - k * .035)], PO, .011, .0132, .0006))
    MAG.append(G.rprism('magfloor', [(-.045, -.166), (-.094, -.166), (-.095, -.178), (-.046, -.178)], .028, PO, .003))
    G.feed_lips(MAG, -.05, -.086, .018, .024, S, M['brass'])
    P.append(lathe_z('vgrip', [(-.07, 0), (-.07, .013), (-.062, .015), (-.02, .0145), (-.004, .012), (0, .012), (0, 0)], (0, -.255, .03), RB, 20))
    P.append(lathe_z('vgripcap', [(-.078, 0), (-.078, .014), (-.07, .0165), (-.068, .0165), (-.068, 0)], (0, -.255, .03), PO, 20))
    finish('gun_ksmg', P, (0, -.415, zb), (0, -.255, -.02), (0, .08, .125), rail=(0, -.04, .1015),
           moving=[('mag', MAG, (0, -.069, .018)), ('charge', CHARGE, (.013, -.27, .102)), ('bolt', BOLT, (RIGHT * .01, -.04, .07))])


def battle_rifle():
    """Battle rifle (our own pattern): the walnut stock IS the body: one loft from the butt through the wrist and the
    action bed to a hand-filling forend, raised strakes on the forend with the finger groove between them, a
    pistol-grip wrist on the lines the hand is fitted to. A milled steel receiver sits in it (heel, bridge, rail
    step, the port and the operating rod on the right); a walnut upper handguard with real vents over the barrel; a
    gas cylinder under the barrel ahead of the forend's band; a ribbed box magazine; aperture sights."""
    bl.reset(); M = K.kinetic_mats(); S, PK, W, BR, RB = M['steel'], M['park'], M['wood'], M['brass'], M['rubber']
    zb = .072; P = []
    pi = math.pi
    # ---------------------------------------------------------------- the stock: sixteen sections, butt to forend tip
    ST = G.Body([(.462, -.074, .064, .0215, 3.6), (.43, -.066, .067, .0212, 3.2), (.36, -.044, .072, .02, 2.8), (.28, -.026, .0765, .0188, 2.7), (.2, -.028, .079, .0186, 2.8),
                 (.15, .006, .071, .0205, 3.4), (.1, .02, .062, .0215, 4.0), (.03, .026, .06, .022, 4.2), (-.05, .028, .06, .0222, 4.2), (-.12, .028, .064, .0222, 4.2),
                 (-.16, .026, .07, .0228, 4.0), (-.24, .022, .071, .0246, 3.6), (-.32, .022, .071, .025, 3.6), (-.37, .025, .07, .0238, 3.6), (-.4, .03, .069, .0215, 3.4),
                 (-.42, .037, .067, .017, 3.0)])
    ST.skin(P, W, 'stock', step=.008, n=32)
    ST.shell(P, 'fore_strake', W, -.175, -.385, ST.af(.05, -.3), ST.af(.7, -.3), t=.0018, ch=.0016)         # the finger groove lies between
    ST.shell(P, 'fore_belly', W, -.175, -.385, ST.af(-.9, -.3), ST.af(-.2, -.3), t=.0018, ch=.0016)          # these two strakes
    ST.checker(P, 'fore_checker', W, -.2, -.36, ST.af(-.82, -.3), ST.af(-.3, -.3), 36, 5, .0007, d=.0019)
    ST.shell(P, 'cheek', W, .4, .25, ST.af(.15, .3), ST.af(.8, .3), t=.002, ch=.002, mirror=False, side=1)
    P.append(G.rprism('stock_grip', G.chaikin([(-.01, .034), (-.004, .0), (.004, -.068), (.035, -.118), (.085, -.11), (.12, -.062), (.16, -.03), (.16, .05), (.0, .05)],
                                              2, sharp=(0, 6, 7, 8)), .043, W, .0125, 4))
    G.checker(P, 'grip_checker', [(.024, -.062), (.06, -.066), (.056, -.102), (.038, -.106)], .0216, W, 12, 12, .0007)
    P.append(G.rprism('grip_cap', [(.03, -.113), (.086, -.105), (.088, -.111), (.032, -.119)], .034, S, .003))
    P.append(G.rloft('buttplate', [(.461, -.075, .065, .022, 3.6), (.47, -.074, .064, .0218, 3.6), (.474, -.07, .06, .02, 3.2)], S, n=28))
    for i in range(6):
        z = .05 - i * .022
        P.append(G.rloft('butt_rib', [(.4735, z - .006, z + .006, .0185, 3.0), (.4765, z - .004, z + .004, .016, 3.0)], S, n=16))
    for y, z in ((.1, .036), (-.1, .04)):
        x = ST.pt(y, 0, .0002)[0]
        G.rivets(P, [(y, z)], x, S, .0034)
    G.swivel(P, .38, -.051, S)
    P += K.sling_loop(-.39, .02, S, x=.028)
    # ---------------------------------------------------------------- the receiver, milled steel, set in the wood
    R = G.Body([(.134, .064, .084, .013, 4.0), (.118, .06, .096, .0165, 5.0), (.095, .058, .1, .0178, 6.0), (.05, .058, .1, .018, 6.0), (.0, .058, .1, .018, 6.0),
                (-.05, .058, .1, .0183, 6.0), (-.1, .058, .1, .0183, 6.0), (-.135, .059, .1, .0186, 6.0), (-.15, .061, .098, .0182, 4.5), (-.158, .064, .094, .017, 3.0)])
    R.skin(P, S, 'receiver', step=.007, n=36)
    R.shell(P, 'receiver_rail', S, .1, -.14, R.af(-.75), R.af(-.3), t=.0016, ch=.0012)
    R.shell(P, 'bridge', S, .1, .04, R.af(.15), R.af(.82), t=.0018, ch=.0014)
    R.shell(P, 'ring', S, -.1, -.15, R.af(-.2), R.af(.82), t=.0018, ch=.0014)
    xr = R.pt(-.03, .3, .0004)[0]
    G.port(P, .005, -.066, .076, .094, xr, RB, None, side=-1)
    BOLT = [plate('boltface', [(.004, .0775), (.004, .0925), (-.064, .0925), (-.064, .0775)], PK, .008, xr - .001, .0008, sym=False, side=-1),
            plate('oprod', [(-.04, .066), (-.04, .078), (-.34, .078), (-.34, .066)], S, .018, .024, .0012, sym=False, side=-1),
            G.rprism('ophandle', [(-.033, .074), (-.033, .086), (-.047, .086), (-.047, .074)], .018, S, .003, x=RIGHT * .03)]
    P.append(plate('oprod_guide', [(-.15, .064), (-.15, .08), (-.17, .08), (-.17, .064)], S, .0182, .0256, .001, sym=False, side=-1))
    P.append(lathe_x('safety', [(0, .0046), (.003, .0046), (.0038, .0036), (.0038, 0)], (ST.pt(.012, 0, 0)[0], .012, .04), S, 14, 1))
    P.append(G.rprism('floorplate', [(-.05, .019), (-.05, .0245), (-.14, .0245), (-.14, .019)], .03, S, .002))
    G.guard(P, S, [(-.054, .028), (-.056, .004), (-.048, -.012), (-.034, -.02), (-.012, -.02), (-.002, -.016)], .012, .0046, r=.0018)
    G.trigger(P, S, -.022, .03, L=.032)
    # ---------------------------------------------------------------- upper handguard: walnut shells with real vents
    UH = G.Body([(-.152, .064, .098, .0165, 2.6), (-.2, .064, .099, .0172, 2.6), (-.26, .064, .099, .0172, 2.6), (-.32, .064, .0985, .0168, 2.6), (-.358, .064, .097, .016, 2.6)])
    kw = dict(t=.0028, d=-.0028, base=-.004, closed=True)
    UH.shell(P, 'hg_crown', W, -.158, -.354, 1.08, pi - 1.08, mirror=False, **kw)
    UH.slats(P, 'hg_vent_bar', W, -.166, -.348, .5, .98, 9, share=.56, **kw)
    UH.shell(P, 'hg_side', W, -.158, -.354, -.1, .42, **kw)
    UH.collar(P, 'hg_ferrule', S, -.15, .01, .001)
    # ---------------------------------------------------------------- barrel group
    G.barrel_stepped(P, 'barrel', [(-.15, .0135), (-.2, .0112), (-.37, .0105), (-.47, .0095), (-.695, .0095)], zb, S, .0048)
    P.append(G.band('gas_port_band', -.455, .014, .0128, S, zb, 0, .0035, 32, .001))
    P += [G.tube_('gascyl', -.36, -.5, .0105, S, .045, n=24),
          lathe('gasplug', [(-.5, 0), (-.5, .0118), (-.51, .0118), (-.514, .008), (-.514, 0)], S, .045, 0, 6, sharp=20),
          G.rprism('frontband', [(-.395, .03), (-.395, .09), (-.412, .09), (-.412, .03)], .05, S, .006),
          prism('gas_lug', [(-.45, .045), (-.45, .064), (-.47, .064), (-.47, .045)], .012, S, .002)]
    for i in range(3):
        P.append(G.band('gascyl_ring', -.43 - i * .025, .006, .0122, S, .045, 0, .003, 20, .0006))
    G.hider(P, 'flashhider', -.69, zb, .0122, .064, S, 5)
    P.append(G.rprism('fsb', [(-.667, zb + .006), (-.667, zb + .035), (-.683, zb + .035), (-.683, zb + .006)], .014, S, .003))
    G.iron_front(P, -.675, .125, S, base_z=zb + .03, w=.022)
    G.iron_rear(P, .085, .125, S, base_z=.1)
    P += K.rail(M, .095, -.12, .1, .022, PK)
    # ---------------------------------------------------------------- magazine
    MAG = [G.rprism('magbody', [(-.058, .03), (-.062, -.12), (-.132, -.13), (-.132, .03)], .028, S, .0035, 3)]
    for k in range(3):
        MAG.append(plate('magrib', [(-.066, -.01 - k * .035), (-.126, -.01 - k * .035), (-.1262, -.017 - k * .035), (-.0662, -.017 - k * .035)], S, .013, .0152, .0007))
    MAG.append(plate('magspine', [(-.092, .01), (-.1, .01), (-.102, -.112), (-.094, -.112)], S, .013, .0152, .0006))
    MAG.append(G.rprism('magfloor', [(-.057, -.116), (-.135, -.126), (-.136, -.137), (-.058, -.127)], .032, S, .003))
    G.feed_lips(MAG, -.062, -.128, .03, .028, S, BR)
    finish('gun_dmr', P, (0, -.755, zb), (0, -.32, .022), (0, .11, .125), rail=(0, -.01, .1095),
           moving=[('mag', MAG, (0, -.095, .03)), ('bolt', BOLT, (RIGHT * .03, -.04, .08))])


def revolver():
    """Revolver: ONE frame lofted round a real cylinder window (a top strap, the barrel boss, the belly, a round recoil
    shield with a loading cut on the right, the hump the hammer comes out of), a fluted cylinder with stop notches and
    bored chambers on a swing-out crane whose yoke fills the front of the window, the ejector rod lying in the open
    channel of a half lug under the barrel, a vent rib, a spur hammer with a chequered pad, a guard undercut at the
    front strap, walnut panels on a steel grip frame with medallions and an escutcheoned screw, an orange front blade."""
    bl.reset(); M = K.kinetic_mats(); S, PK, W, BR, OR = M['steel'], M['park'], M['wood'], M['brass'], M['orange']
    zc = .062; zb = zc + .013; P = []
    rc = .0135                                                       # the chambers' circle
    Rs = .0228                                                       # the recoil shield, round like the cylinder

    def sh(z):
        return max(math.sqrt(max(Rs * Rs - (z - zc) ** 2, 0.0)), .0112)
    # ---- the frame: stations round the window (window edge -> outline, half widths at the window / part way / outline)
    P.append(G.ring_frame('frame', [
        (.0225, .0868, .027, .1, .0105), (-.006, .0868, -.008, .1, .0105), (-.036, .0868, -.040, .1, .0107),      # top strap
        (-.042, .0868, -.0505, .0995, .011), (-.042, .0808, -.051, .09, .0118),
        (-.042, .064, -.0515, .064, .0126), (-.042, .0445, -.0505, .046, .0124),                                  # the barrel boss
        (-.042, .0385, -.046, .0335, .0122), (-.036, .0385, -.037, .0275, .0124),
        (-.012, .0385, -.016, .0195, .013), (.0225, .0385, .006, .013, .013),                                     # the belly
        (.0285, .0385, .022, .021, .013, .013, .0128, .4),
        (.0285, .0445, .04, .029, sh(.0445), .013, .0126, .45),
        (.0285, .054, .051, .0375, sh(.054), .0128, .0108, .5),                                                   # the recoil shield
        (.0285, .062, .057, .05, sh(.062), .0125, .0105, .5, .0168),
        (.0285, .072, .05, .0625, sh(.072), .0122, .0105, .55, .015),                                             # (its loading cut)
        (.0285, .0808, .0435, .078, sh(.0808), .0118, .0105, .5),
        (.0285, .0868, .041, .0965, .011, .011, .0105, .5)], S))
    P.append(prism('topgroove', [(.018, .0998), (.018, .1004), (-.046, .1004), (-.046, .0998)], .004, PK, .0002))
    # ---- the cylinder: flutes, stop notches, bored chambers; the ratchet behind it, the gas ring ahead
    CYL = [G.drum('cylinder', .0265, -.0315, .0218, S, zc, n=144, fl_w=.0066, fl_d=.003, fl_end=.004, fl_r=.008,
                  notch=(.021, .0135, 15, 3, .0009), holes=(rc, .0052, .029, .0006), hub=.0052),
           lathe('ratchet', [(.031, 0), (.031, .005), (.0265, .0062), (.0265, 0)], S, zc, 0, 24),
           G.tube_('gasring', -.0315, -.0338, .0048, S, zc, n=20, ch=.0005)]
    ROUNDS = []
    for i in range(6):
        a = i * math.pi / 3 + math.pi / 6
        x, z = math.cos(a) * rc, zc + math.sin(a) * rc
        CYL.append(G.bar('ratchet_tooth', .0308, .0265, .0048, .0088, a - .17, a + .17, S, zc, 0, 1, .7))
        ROUNDS += [lathe('rim', [(.0284, 0), (.0284, .0062), (.0266, .0062), (.0266, 0)], BR, z, x, 12),
                   lathe('primer', [(.0288, 0), (.0288, .0021), (.0284, .0021), (.0284, 0)], M['steel'], z, x, 8)]
    # ---- the crane: its yoke fills the front of the window, the ejector rod runs out under the barrel
    hx, hz = .004, zc - .025
    CRANE = [G.tube_('ejrod', -.031, -.0985, .0032, S, zc, n=14),
             lathe('ejknob', [(-.094, 0), (-.094, .0042), (-.1035, .0042), (-.1048, .0034), (-.1048, 0)], S, zc, 0, 16),
             lathe('ejknurl', [(-.0955, 0), (-.0955, .00465), (-.1022, .00465), (-.1022, 0)], PK, zc, 0, 12, sharp=20),
             G.rprism('yoke', [(-.0342, .0392), (-.0342, .0658), (-.0412, .0658), (-.0412, .0392)], .0236, S, .0022, 2),
             G.tube_('yokepin', .0, -.05, .0024, S, hz, hx, n=8)]
    LOADER = [lathe('sl_body', [(.016, 0), (.016, .019), (.004, .019), (.004, 0)], S, 0, 0, 24),
              lathe('sl_knob', [(.03, 0), (.03, .007), (.028, .008), (.016, .008), (.016, 0)], S, 0, 0, 12),
              G.band('sl_grip', .012, .004, .0198, PK, 0, 0, .002, 24, .0004)]
    for i in range(6):
        a = i * math.pi / 3 + math.pi / 6
        x, z = math.cos(a) * rc, math.sin(a) * rc
        LOADER += [lathe('sl_case', [(.004, 0), (.004, .0054), (-.026, .0054), (-.026, 0)], BR, z, x, 10),
                   lathe('sl_nose', [(-.026, 0), (-.026, .0046), (-.032, .0036), (-.034, .0018), (-.034, 0)], M['steel'], z, x, 10)]
    CASING = [lathe('cs_case', [(.0155, .0045), (.0155, .0062), (.014, .0062), (.014, .0054), (-.015, .0054), (-.015, .0045)], BR, .2, 0, 12, closed=True)]
    # ---- the barrel: the forcing cone in the window, a shoulder at the frame, a taper to a crowned muzzle
    P.append(lathe('barrel', [(-.033, 0), (-.033, .0066), (-.0345, .0078), (-.0512, .0078), (-.0512, .0099), (-.056, .0099), (-.0572, .0093),
                              (-.18, .0086), (-.1838, .0086), (-.1855, .0072), (-.1855, .0064), (-.1836, .0054), (-.1836, .0048),
                              (-.155, .0048), (-.155, 0)], S, zb, 0, 36))
    # the half lug under it: closed on the right, an open channel on the left the ejector rod lies in (and swings out of)
    zt, zl, hwl, rb = .0712, .0505, .0072, .006

    def lug(pocket, sx=1.0, sz_=1.0):
        pts = [(hwl, zt), (-hwl, zt)]
        pts += [(hwl * math.cos(math.pi + math.pi * k / 10), zl + rb + rb * math.sin(math.pi + math.pi * k / 10)) for k in range(11)]
        if pocket:
            pts += [(.0006, .0572)] + [(.0006 - .0048 * math.sin(math.pi * k / 8), zc - .0048 * math.cos(math.pi * k / 8)) for k in range(1, 8)] + [(.0006, .0668)]
        else:
            pts += [(hwl, .0572 + .0096 * k / 8) for k in range(9)]
        pts += [(hwl, .0668 + .0002)] if pocket else [(hwl, .0672)]
        return [(x * sx, zt - (zt - z) * sz_) for x, z in pts]
    P.append(G._skin('lug', [(-.0512, lug(True)), (-.1074, lug(True)), (-.1078, lug(False)), (-.119, lug(False)), (-.1255, lug(False, .93, .9)),
                             (-.1295, lug(False, .78, .7)), (-.132, lug(False, .5, .42))], S, 40))
    P.append(prism('ventrib', [(-.0512, .0885), (-.0512, .094), (-.178, .094), (-.181, .0885)], .0085, S, .001))
    for i in range(6):
        P.append(prism('ribpost', [(-.066 - i * .02, .0835), (-.066 - i * .02, .0885), (-.072 - i * .02, .0885), (-.072 - i * .02, .0835)], .006, S, .0004))
    for i in range(14):
        P.append(prism('ribline', [(-.058 - i * .0085, .0938), (-.058 - i * .0085, .0943), (-.062 - i * .0085, .0943), (-.062 - i * .0085, .0938)], .0062, PK, .0002))
    # ---- the hammer in the cut behind the top strap (under the sight line): a broad body, a spur with a chequered pad
    P.append(G.rprism('hammer', G.chaikin([(.04, .064), (.0405, .088), (.0425, .0945), (.047, .096), (.056, .0935), (.0665, .0885), (.067, .0862),
                                           (.058, .0885), (.0525, .0855), (.0515, .076), (.0545, .066), (.049, .057)], 2, sharp=(5, 6)), .009, S, .0016, 2))
    P.append(prism('hammer_spur', [(.0552, .0932), (.0558, .0952), (.0672, .0898), (.0668, .0876), (.059, .0905)], .0125, S, .0007))
    G.checker3(P, 'spur_checker', (-.0056, .0564, .09502), (.0056, .0564, .09502), (.0056, .0666, .0902), (-.0056, .0666, .0902), PK, 8, 8, .0005, .0008)
    P.append(K.cylx('hammer_pin', .0026, .0236, (0, .046, .066), PK, 12, .0004))
    # the cylinder latch on the left, behind the shield
    P.append(plate('latch', [(.0465, .0575), (.0465, .0495), (.0385, .0485), (.0375, .0565)], S, .009, .0138, .0008, sym=False, side=1))
    G.serrations(P, 'latch_grip', .0452, 3, .0026, .0505, .0558, .0138, PK, t=.0011, sym=False, side=1)
    # the side plate on the right with its screws
    P.append(plate('sideplate', [(.018, .0235), (.018, .0345), (-.03, .0345), (-.036, .0305), (-.014, .0225), (.0, .0195)], S, .011, .0137, .0006, sym=False, side=-1))
    G.hexbolts(P, [(.011, .0285), (-.027, .0315)], .0137, S, .0022, sym=False, side=-1, n=14)
    G.rivets(P, [(-.006, .0235)], .0137, PK, .0016, sym=False, side=-1)
    # ---- the guard: up into the frame at the front, undercut where it meets the front strap
    P.append(G.rprism('trigguard', G.ribbon(G.smooth([(-.041, .03), (-.0455, .012), (-.044, -.002), (-.037, -.0125), (-.026, -.017), (-.006, -.017),
                                                      (.0045, -.0135), (.0105, -.0065)], 2), [.0058, .0056, .0054, .005, .0046, .0042]), .012, S, .0018, 2))
    G.trigger(P, S, -.012, .022, L=.027)
    G.cross_pins(P, [(-.008, .0285), (-.024, .034), (.012, .031)], .0262, PK, .0016)
    # ---- the grip on the committed grip's lines: a steel frame (the straps), walnut panels rounding down to it
    g = G.gp(.42, .024, .02); h = .105
    outline = G.chaikin([g(.03, -.004), g(.032, .02), g(.0265, h * .5), g(.028, h), g(-.02, h + .004), g(-.026, h * .72), g(-.0265, h * .5),
                         g(-.0265, .034), g(-.024, -.004)], 2, sharp=(0, 8))
    P.append(G.rprism('grip_frame', outline, .0156, S, .0016, 2))
    P.append(G.rprism('grip', G.poly_offset(outline, .0007), .036, W, .0115, 4))
    c = g(.002, .03)
    for s in (1, -1):
        P.append(lathe_x('medallion', [(0, .0058), (.0012, .0058), (.0018, .0046), (.0018, 0)], (s * .0178, c[0], c[1]), BR, 16, s))
    c = g(.0, .074)
    for s in (1, -1):
        P.append(lathe_x('escutcheon', [(0, .0048), (.0009, .0048), (.0013, .004), (.0013, .0026), (.0006, .0024), (.0006, 0)], (s * .0178, c[0], c[1]), BR, 16, s))
        P.append(lathe_x('gripscrew', [(0, .0024), (.0011, .0024), (.0015, .0016), (.0015, 0)], (s * .0178, c[0], c[1]), S, 12, s))
    P.append(plate('screwslot', [(c[0] - .002, c[1] + .0004), (c[0] + .002, c[1] + .0004), (c[0] + .002, c[1] - .0004), (c[0] - .002, c[1] - .0004)],
                   PK, .019, .01945, .0001, sym=False, side=1))
    G.checker(P, 'grip_checker', [g(-.01, .04), g(.013, .038), g(.013, .066), g(-.01, .067)], .0181, W, 11, 13, .0006)
    G.checker(P, 'grip_checker', [g(-.01, .081), g(.013, .081), g(.012, .096), g(-.009, .097)], .0181, W, 11, 7, .0006)
    # ---- the sights: a square notch on the top strap, a plate for an optic ahead of it, a pinned blade
    sz = .102
    P += [prism('rearblock', [(.041, .097), (.041, .104), (.022, .104), (.017, .0985)], .017, S, .001)]
    P.append(prism('optic_plate', [(.008, .1), (.008, .1012), (-.046, .1012), (-.046, .1)], .019, PK, .0005))
    for yy in (.0, -.038):
        for xx in (.0062, -.0062):
            P.append(lathe_z('plate_screw', [(0, 0), (0, .0016), (.0004, .0016), (.0004, 0)], (xx, yy, .1012), S, 10))
    for s, nm in ((1, 'rear_earL'), (-1, 'rear_earR')):
        P.append(prism(nm, [(.03, sz - .0055), (.03, sz + .0015), (.023, sz + .0015), (.023, sz - .0055)], .005, S, .0006, x=s * .0055))
    P += [prism('front_base', [(-.15, .094), (-.158, .098), (-.176, .098), (-.18, .094)], .0085, S, .0006),
          prism('frontpost', [(-.16, .0975), (-.163, sz), (-.172, sz), (-.176, .0975)], .0035, S, .0006),
          prism('postdot', [(-.165, sz - .0035), (-.165, sz - .0005), (-.171, sz - .0005), (-.171, sz - .0035)], .0037, OR, .0004)]
    P.append(K.cylx('sight_pin', .001, .0092, (0, -.166, .0965), PK, 8, .0002))
    finish('gun_revolver', P, (0, -.185, zb), (0, -.02, -.035), (0, .07, sz), rail=(0, -.02, .1012),
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


def _bio_strands(P, rf, zf, y0, y1, n=9, r=.008, twist=.55):
    """Muscle bundles lying along the body, drawn forward to the maw: n strands round the section (rf(y) = the
    body's radius, zf(y) = its centre's height), each a chain of capsules sunk a third into the surface, turning a
    little as they run."""
    d = np.full(len(P), 1e3, np.float32)
    ys = np.linspace(y0, y1, 10)
    for i in range(n):
        a0 = 2 * math.pi * (i + .5) / n
        pts = []
        for j, y in enumerate(ys):
            a = a0 + twist * j / 9
            rr = rf(y) - r * .22
            pts.append((rr * math.cos(a), y, zf(y) + rr * math.sin(a)))
        for p, q in zip(pts, pts[1:]):
            d = np.minimum(d, sdf.capsule(P, p, q, r * (1.0 - .2 * (i % 2))))
    return d


def _bio_veins(P, rf, zf, y0, y1, n=4, r=.0018, lift=.0009, seed=3):
    """Veins of light under the skin: n wandering lines along the body with short branches, half sunk in the flesh."""
    rng = np.random.default_rng(seed)
    d = np.full(len(P), 1e3, np.float32)
    ys = np.linspace(y0, y1, 13)
    for i in range(n):
        a0 = 2 * math.pi * (i + rng.random() * .6) / n; ph = rng.random() * 6.28; w = .22 + rng.random() * .2

        def at(y, da=0.0):
            a = a0 + w * math.sin(y * 19.0 + ph) + da
            rr = rf(y) + lift
            return (rr * math.cos(a), y, zf(y) + rr * math.sin(a))
        for j in range(len(ys) - 1):
            d = np.minimum(d, sdf.capsule(P, at(ys[j]), at(ys[j + 1]), r))
            if j % 3 == 1:
                s = 1 if (i + j) % 2 else -1
                ym = ys[j] + (ys[j + 1] - ys[j]) * 1.6
                d = np.minimum(d, sdf.round_cone(P, at(ys[j]), at(ym, s * .42), r * .8, r * .35))
    return d


def _bio_bridges(P, rf, zf, spans, r=.0032, lift=.015):
    """Sinew bridges: cords that leave the body, stand off it with a gap under them and go back in. spans = (y from,
    y to, angle round the section); both flanks."""
    d = np.full(len(P), 1e3, np.float32)
    for ya, yb, ang in spans:
        for s in (1, -1):
            pts = []
            for t in np.linspace(0, 1, 9):
                y = ya + (yb - ya) * t
                rr = rf(y) - .003 + lift * math.sin(math.pi * t) ** .7
                pts.append((s * rr * math.cos(ang), y, zf(y) + rr * math.sin(ang)))
            for k, (p, q) in enumerate(zip(pts, pts[1:])):
                d = np.minimum(d, sdf.capsule(P, p, q, r * (1.25 if k in (0, 7) else 1.0)))
    return d


def _bio_wrap(P, a, b, r0, r1, turns=3.0, r=.0042, n=30):
    """Two tendons wound round the grip's bone from a down to b (r0, r1 = the helix's radius at each end)."""
    a = np.asarray(a, np.float32); b = np.asarray(b, np.float32)
    ax = (b - a) / np.linalg.norm(b - a)
    u = np.cross(ax, np.array([1, 0, 0], np.float32)); u /= np.linalg.norm(u); v = np.cross(ax, u)
    d = np.full(len(P), 1e3, np.float32)
    for ph in (0.0, math.pi):
        pts = []
        for t in np.linspace(0, 1, n):
            th = 2 * math.pi * turns * t + ph
            pts.append(a + (b - a) * t + (u * math.cos(th) + v * math.sin(th)) * (r0 + (r1 - r0) * t))
        for p, q in zip(pts, pts[1:]):
            d = np.minimum(d, sdf.capsule(P, p, q, r))
    return d


def _bio_pores(P, d, cell=.017, r=.0034):
    """Pores: small pits in the skin on a jittered lattice (about half of its cells)."""
    Q = P + np.stack([K.lumps(P, 41, 60, .004), K.lumps(P, 42, 60, .004), K.lumps(P, 43, 60, .004)], axis=1)
    idx = np.floor(Q / cell)
    c = (idx + .5) * cell
    on = (np.sin(idx @ np.array([12.9898, 78.233, 37.719], np.float32)) * 43758.5453) % 1.0 > .5
    dp = np.where(on, np.linalg.norm(Q - c, axis=1) - r, 1e3).astype(np.float32)
    return np.maximum(d, -dp)


def _bio_ribs(P, stations, zc, r=.0062, a0=.55, a1=2.3, stand=0.0):
    """Rib bones over both flanks: at each station (y, half width, half height) an arc from beside the spine round to
    the belly, swept a little back as it drops. Give the body's own radius: the ribs lie half in the skin."""
    d = np.full(len(P), 1e3, np.float32)
    for y, rx, rz in stations:
        for s in (1, -1):
            pts = []
            for k, a in enumerate(np.linspace(a0, a1, 7)):                # with `stand` the rib arches clear of the body: only its ends go in
                off = stand if 0 < k < 6 else -.004 * (stand > 0)
                pts.append((s * (rx + off) * math.sin(a), y + .02 * (a - a0), zc + (rz + off) * math.cos(a)))
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

    def zf(y):
        return float(np.interp(-y, [-.24, -.05, .36, .53], [.045, .075, .072, zb]))

    def body(P):
        d = sdf.round_cone(P, (0, .24, .045), (0, .05, .075), .042, .062)
        d = sdf.smin(d, sdf.round_cone(P, (0, .05, .075), (0, -.36, .072), .062, .038), .04)
        d = sdf.smin(d, sdf.round_cone(P, (0, -.36, .072), (0, -.53, zb), .038, .052), .05)
        d = sdf.smin(d, _bio_wrap(P, (0, .0, .04), (0, .036, -.105), .0195, .016), .006)               # tendons wound round the grip's bone
        d = sdf.smin(d, sdf.round_cone(P, (0, -.28, .045), (0, -.295, -.05), .027, .018), .035)      # foregrip growth
        d = sdf.smin(d, sdf.ellipsoid(P, (0, -.03, .02), (.03, .03, .025)), .02)                     # trigger knot
        d = sdf.smin(d, _bio_strands(P, rb, zf, .2, -.5, 9, .008), .004)                           # muscle drawn forward to the maw
        for s in (1, -1):                                                                          # tendons along the flanks
            d = sdf.smin(d, sdf.capsule(P, (s * .052, .04, .08), (s * .04, -.34, .062), .0045), .006)
            d = sdf.smin(d, sdf.capsule(P, (s * .045, .12, .05), (s * .038, -.2, .035), .0035), .005)
        for k in range(4):                                                                         # four lips round the maw
            a = k * math.pi / 2 + math.pi / 4
            d = sdf.smin(d, sdf.ellipsoid(P, (math.cos(a) * .03, -.55, zb + math.sin(a) * .024), (.022, .03, .018)), .012)
        d = _bio_pores(P, d + K.lumps(P, 3, 120, .0011) + K.lumps(P, 4, 40, .002))
        d = sdf.smax(d, -sdf.ellipsoid(P, (0, -.575, zb), (.032, .055, .026)), .012)               # the maw
        d = sdf.smax(d, -sdf.sphere(P, (.038, -.25, .074), .024), .006)                               # feeding socket
        return d
    lo, hi = (-.1, -.62, -.14), (.1, .3, .16)
    P = [K.sdf_part('flesh', body, lo, hi, .0024, M['flesh'], 19000)]

    def sacs(P):
        d = sdf.ellipsoid(P, (.042, -.12, .1), (.022, .036, .02))
        d = np.minimum(d, sdf.ellipsoid(P, (-.042, -.13, .098), (.02, .03, .019)))
        d = np.minimum(d, sdf.ellipsoid(P, (0, .1, .118), (.026, .045, .022)))
        d = np.minimum(d, sdf.ellipsoid(P, (.03, -.33, .095), (.016, .022, .015)))
        d = np.minimum(d, sdf.ellipsoid(P, (-.024, .17, .085), (.016, .02, .016)))
        return np.minimum(d + K.lumps(P, 5, 160, .0015), _bio_veins(P, rb, zf, .18, -.48, 4))
    P.append(K.sdf_part('sacs', sacs, (-.085, -.5, .0), (.085, .24, .16), .0016, M['glow'], 4000))

    def bone(P):
        d = sdf.round_cone(P, (0, -.42, .1), (0, -.36, .16), .012, .002)                       # horn
        top = lambda y: float(np.interp(-y, [-.24, -.05, .36], [.087, .137, .11]))
        d = np.minimum(d, _bio_scales(P, [(y, top(y) + .003) for y in np.linspace(.21, -.34, 11) if abs(y - .08) > .03]))
        d = np.minimum(d, _bio_ribs(P, [(y, rb(y), rb(y)) for y in np.linspace(.0, -.33, 7)], .073, stand=.011))
        d = np.minimum(d, _bio_spur(P, (0, .22, .05), (0, .335, .05), (0, .36, -.045), .021, .005))
        d = np.minimum(d, sdf.round_cone(P, (0, .004, .034), (0, .036, -.105), .0205, .017))    # the grip's bone
        d = np.minimum(d, sdf.ellipsoid(P, (0, .037, -.112), (.021, .023, .009)))               # its knuckle
        d = np.minimum(d, _bio_bridges(P, rb, zf, [(.17, .05, .55), (-.08, -.2, -.5), (-.3, -.43, .35)]))
        for s in (1, -1):                                                                       # mandibles hooked round the maw
            d = np.minimum(d, sdf.round_cone(P, (s * .044, -.49, zb - .004), (s * .06, -.565, zb - .006), .011, .007))
            d = np.minimum(d, sdf.round_cone(P, (s * .06, -.565, zb - .006), (s * .034, -.608, zb - .004), .007, .0016))
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
    P.append(K.sdf_part('bone', bone, (-.1, -.63, -.13), (.1, .4, .17), .0019, M['bone'], 12000))
    P.append(K.sdf_part('maw', lambda P: np.minimum(sdf.ellipsoid(P, (0, -.548, zb), (.026, .03, .021)), sdf.torus(P, (0, -.553, zb), .031, .0065, Ry)) + K.lumps(P, 6, 200, .001),
                        (-.045, -.6, .025), (.045, -.5, .115), .0018, M['maw'], 1500))
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

    def rf(y):
        return float(np.interp(-y, [-.2, -.02, .33], [.04, .058, .05]))

    def zf(y):
        return float(np.interp(-y, [-.2, -.02, .33], [.05, .08, zb]))

    def body(P):
        d = sdf.round_cone(P, (0, .2, .05), (0, .02, .08), .04, .058)
        d = sdf.smin(d, sdf.round_cone(P, (0, .02, .08), (0, -.33, zb), .058, .05), .04)
        d = sdf.smin(d, sdf.ellipsoid(P, (0, -.4, zb), (.07, .06, .052)), .04)                     # wide head
        d = sdf.smin(d, _bio_wrap(P, (0, .0, .04), (0, .036, -.105), .0195, .016), .006)
        d = sdf.smin(d, sdf.ellipsoid(P, (0, -.17, .005), (.05, .1, .052)), .03)                   # stomach wall
        for s in (1, -1):                                                                          # gullet tubes
            d = sdf.smin(d, sdf.capsule(P, (s * .042, -.08, .0), (s * .05, -.36, .05), .009), .012)
        d = sdf.smin(d, _bio_strands(P, rf, zf, .16, -.37, 9, .0065, .4), .004)
        d = _bio_pores(P, d + K.lumps(P, 7, 110, .0012) + K.lumps(P, 8, 35, .0024))
        d = sdf.smax(d, -sdf.ellipsoid(P, (0, -.46, zb), (.055, .06, .026)), .014)                 # wide horizontal maw
        d = sdf.smax(d, -sdf.ellipsoid(P, (0, -.17, -.015), (.038, .085, .04)), .01)               # window onto the stomach sac
        d = sdf.smax(d, -sdf.ellipsoid(P, (.044, -.112, .078), (.022, .032, .02)), .006)            # feeding slit
        return d
    P = [K.sdf_part('flesh', body, (-.1, -.53, -.13), (.1, .26, .15), .0024, M['flesh'], 19000)]

    def sac(P):
        d = sdf.ellipsoid(P, (0, -.17, -.012), (.042, .088, .043))
        d = np.minimum(d, sdf.ellipsoid(P, (.035, .06, .11), (.014, .02, .014)))
        d = np.minimum(d, sdf.ellipsoid(P, (-.03, -.25, .12), (.016, .024, .015)))
        return np.minimum(d + K.lumps(P, 9, 140, .002), _bio_veins(P, rf, zf, .15, -.34, 4, seed=7))
    P.append(K.sdf_part('sac', sac, (-.08, -.4, -.07), (.08, .2, .15), .0016, M['glow'], 4000))

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
        d = np.minimum(d, _bio_ribs(P, [(y, rf(y) + .002, rf(y) + .002) for y in np.linspace(.03, -.3, 6)], .078, .0062, .55, 1.75, stand=.011))
        d = np.minimum(d, _bio_spur(P, (0, .18, .055), (0, .295, .055), (0, .32, -.04), .021, .005))
        d = np.minimum(d, sdf.round_cone(P, (0, .004, .034), (0, .036, -.105), .0205, .017))
        d = np.minimum(d, sdf.ellipsoid(P, (0, .037, -.112), (.021, .023, .009)))
        d = np.minimum(d, _bio_bridges(P, rf, zf, [(.14, .03, .6), (-.2, -.33, .45)]))
        for s in (1, -1):                                                                       # the jaw: two bones under the lip, joined at the chin
            d = np.minimum(d, sdf.round_cone(P, (s * .066, -.39, zb - .03), (s * .05, -.468, zb - .036), .011, .0075))
        for s in (1, -1):                                                                       # ... meeting in a pointed chin
            d = np.minimum(d, sdf.round_cone(P, (s * .05, -.468, zb - .036), (0, -.5, zb - .04), .0075, .006))
        for s in (1, -1):
            d = np.minimum(d, sdf.round_cone(P, (s * .065, -.38, .09), (s * .1, -.33, .13), .009, .0015))
        return d
    P.append(K.sdf_part('bone', bone, (-.12, -.52, -.13), (.12, .36, .17), .0019, M['bone'], 12000))
    P.append(K.sdf_part('maw', lambda P: np.minimum(sdf.ellipsoid(P, (0, -.43, zb), (.048, .04, .02)), np.minimum(sdf.capsule(P, (-.04, -.436, zb + .024), (.04, -.436, zb + .024), .0058), sdf.capsule(P, (-.04, -.436, zb - .024), (.04, -.436, zb - .024), .0058))) + K.lumps(P, 10, 200, .001),
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

    def rf(y):
        return float(np.interp(-y, [-.3, -.05, .5], [.05, .08, .06]))

    def zf(y):
        return float(np.interp(-y, [-.3, -.05, .5], [.07, .11, zb]))

    def body(P):
        d = sdf.round_cone(P, (0, .3, .07), (0, .05, .11), .05, .08)
        d = sdf.smin(d, sdf.round_cone(P, (0, .05, .11), (0, -.5, zb), .08, .06), .05)
        d = sdf.smin(d, sdf.ellipsoid(P, (0, -.6, zb), (.075, .07, .07)), .05)
        d = sdf.smin(d, _bio_wrap(P, (0, .0, .055), (0, .036, -.105), .0205, .017, 3.4), .006)
        d = sdf.smin(d, sdf.round_cone(P, (0, -.3, .06), (0, -.31, -.04), .03, .02), .04)
        d = sdf.smin(d, _bio_strands(P, rf, zf, .26, -.56, 10, .009, .5), .005)
        for s in (1, -1):
            d = sdf.smin(d, sdf.capsule(P, (s * .07, .1, .1), (s * .06, -.5, .1), .006), .008)
        d = _bio_pores(P, d + K.lumps(P, 11, 90, .0014) + K.lumps(P, 12, 30, .003), .02, .004)
        d = sdf.smax(d, -sdf.sphere(P, (0, -.67, zb), .045), .015)                                 # orifice
        d = sdf.smax(d, -sdf.ellipsoid(P, (0, -.15, .18), (.03, .042, .028)), .006)                  # womb socket under the lid plate
        return d
    P = [K.sdf_part('flesh', body, (-.13, -.72, -.14), (.13, .37, .21), .0027, M['flesh'], 20000)]

    def eggs(P):
        d = np.full(len(P), 1e3, np.float32)
        rng = np.random.default_rng(4)
        for s in (1, -1):
            for k in range(5):
                c = (s * (.075 + rng.random() * .012), -.08 - k * .07 + rng.random() * .02, .08 + rng.random() * .05)
                d = np.minimum(d, sdf.ellipsoid(P, c, (.026, .03, .026)))
        return np.minimum(d + K.lumps(P, 13, 170, .0015), _bio_veins(P, rf, zf, .24, -.54, 5, .002, seed=11))
    P.append(K.sdf_part('eggs', eggs, (-.13, -.58, .0), (.13, .26, .2), .0018, M['glow'], 5000))

    def bone(P):
        d = np.full(len(P), 1e3, np.float32)
        for i, y in enumerate(np.linspace(.15, -.45, 5)):                                       # carapace plates
            if i == 2:
                continue                                                                        # the lid plate is the 'hatch'
            rz = .078 if i == 0 else .09                             # the rear plate lies low: 1.7 cm under the sight line behind the sight
            shell = sdf.ellipsoid(P, (0, y, zb + .02), (.09, .085, rz))
            inner = sdf.ellipsoid(P, (0, y + .01, zb + .005), (.085, .09, rz - .005))
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
        d = np.minimum(d, _bio_ribs(P, [(y, rr(y), rr(y)) for y in np.linspace(-.08, -.5, 8)], zb, .0068, 1.95, 2.95, stand=.012))   # belly ribs under the eggs
        d = np.minimum(d, _bio_spur(P, (0, .28, .075), (0, .405, .075), (0, .43, -.04), .025, .006))
        d = np.minimum(d, sdf.round_cone(P, (0, .004, .05), (0, .036, -.105), .0215, .018))
        d = np.minimum(d, sdf.ellipsoid(P, (0, .037, -.112), (.022, .024, .009)))
        d = np.minimum(d, _bio_bridges(P, rf, zf, [(.24, .1, .1), (-.2, -.36, -.75), (-.4, -.54, .2)], .0036, .017))
        return d
    P.append(K.sdf_part('bone', bone, (-.13, -.76, -.13), (.13, .48, .25), .0021, M['bone'], 13000))
    P.append(K.sdf_part('maw', lambda P: np.minimum(sdf.sphere(P, (0, -.64, zb), .038), sdf.torus(P, (0, -.648, zb), .05, .0085, Ry)) + K.lumps(P, 14, 200, .0015),
                        (-.064, -.69, .046), (.064, -.59, .174), .002, M['maw'], 1600))
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
    for magnified optics, <node>_scope. The game mounts the node on a gun's 'rail' empty and puts the eye AT the eye
    point, so every part is drawn for that view: reflex and holo are a thin frame round a large window (the housing
    about a sixth of the screen's width), the scopes are round to 64 segments with fine knurling and thin rims.

    Smooth machined finishes (no texture: a coarse one makes parts this small look lumpy): gun_optic anodised black,
    gun_steel for the hardware, gun_rubber, gun_lens (coated glass), gun_brass for one index ring, gun_sightpaint for
    the index marks, gun_dot for a reticle, an illumination mark or the prism sight's light collector."""
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
        P.append(lathe_x('clampbolt', [(0, .003), (.0018, .003), (.0022, .002), (.0022, 0)], (w / 2, y, .002), S, 16, 1))

    def boxes(name, quads, m):
        """many small boxes as ONE mesh (knurl teeth, tick marks): quads = lists of 8 corners"""
        Vv = []; F = []
        for q in quads:
            k = len(Vv); Vv += q
            F += [(k, k + 1, k + 3, k + 2), (k + 4, k + 5, k + 7, k + 6), (k, k + 1, k + 5, k + 4), (k + 2, k + 3, k + 7, k + 6), (k, k + 2, k + 6, k + 4),
                  (k + 1, k + 3, k + 7, k + 5)]
        return V.mk(name, Vv, F, m, 30, weld=False)

    def teeth(place, r0, r1, d0, d1, n, share=.5, twist=0.0):
        """n teeth between radii r0 < r1 round an axis, from d0 to d1 along it; place(d, u, v) puts a point"""
        out = []
        w = TAU / n * share / 2
        for k in range(n):
            a = TAU * k / n
            out.append([place(d, rad * math.cos(aa + (twist if d == d1 else 0)), rad * math.sin(aa + (twist if d == d1 else 0)))
                        for d in (d0, d1) for rad in (r0, r1) for aa in (a - w, a + w)])
        return out

    def knurl(P, name, y, Ln, r, m, z, n=72, t=.003, proud=.00045):
        """a finely knurled ring round the optic's axis: a band, n small teeth standing a little proud of it"""
        P.append(G.band(name, y, Ln, r, m, z, 0, t, 64, .0006))
        P.append(boxes(name + '_k', teeth(lambda d, u, v: (u, d, z + v), r - .0002, r + proud, y - .0008, y - Ln + .0008, n, .5, TAU / n * .5), m))

    def slotted(P, name, c, r, side, m=None):
        """a slotted adjustment screw standing out of a flank"""
        P.append(lathe_x(name, [(0, r), (.0014, r), (.002, r * .8), (.002, 0)], c, m or S, 20, side))
        P.append(plate(name + '_slot', [(c[1] + r * .8, c[2] - .0004), (c[1] + r * .8, c[2] + .0004), (c[1] - r * .8, c[2] + .0004), (c[1] - r * .8, c[2] - .0004)], RB,
                       abs(c[0]) + .0015, abs(c[0]) + .0022, .0001, sym=False, side=side))

    def done(name, parts, eye, scope=False):
        g = K.assemble(name, parts)
        bl.empty(name + '_sight', eye, g)
        if scope:
            bl.empty(name + '_scope', eye, g)

    # ---- open reflex: a low base, a LARGE window (32 x 22 mm) in a hoop 2.5 mm thick with a hood and side ears,
    # the emitter's housing low behind it
    h = .022
    P = []
    mount(P, 0, .028)
    P.append(prism('rx_base', [(.03, .0095), (.03, .0115), (.028, .0125), (-.024, .0125), (-.026, .0115), (-.026, .0095)], .039, AL, .0012))
    P.append(prism('rx_housing', [(.03, .0125), (.03, .0166), (.016, .0166), (.011, .0125)], .03, AL, .0012))
    P.append(lathe('rx_emitter', [(.0132, 0), (.0132, .0019), (.0124, .0019), (.0124, 0)], L, .0146, 0, 16))
    for s in (1, -1):
        P.append(prism('rx_post', [(-.012, .0125), (-.0152, .0372), (-.0188, .0372), (-.0188, .0125)], .0026, AL, .0008, x=s * .0173))
        P.append(prism('rx_ear', [(.012, .0125), (-.0118, .0125), (-.0148, .0352), (-.0128, .0352)], .0016, AL, .0005, x=s * .0189))
    P.append(prism('rx_hood', [(-.0118, .0346), (-.0128, .0372), (-.0248, .0372), (-.0242, .0346)], .0372, AL, .0008))
    P.append(prism('rx_sill', [(-.0118, .0118), (-.0118, .0128), (-.019, .0128), (-.019, .0118)], .0372, AL, .0004))
    P.append(prism('rx_glass', [(-.0146, .0128), (-.0166, .0346), (-.0174, .0346), (-.0154, .0128)], .032, L, .0002))
    P.append(lathe('rx_dot', [(-.0238, 0), (-.0238, .0011), (-.0243, .0011), (-.0243, 0)], D, h, 0, 12))
    P.append(lathe_x('rx_battery', [(0, .0034), (.0026, .0034), (.0034, .0026), (.0034, 0)], (-.015, .023, .0128), S, 24, -1))
    P.append(plate('rx_battery_slot', [(.0256, .0125), (.0256, .0131), (.0204, .0131), (.0204, .0125)], RB, .018, .0186, .0001, sym=False, side=-1))
    slotted(P, 'rx_windage', (.015, .023, .0132), .0024, 1)
    P.append(G.lathe_z('rx_elevation', [(0, 0), (0, .0026), (.001, .0026), (.0015, .002), (.0015, 0)], (0, .024, .0166), S, 20))
    P.append(prism('rx_elev_slot', [(.0262, .0181), (.0262, .0184), (.0218, .0184), (.0218, .0181)], .0007, RB, .0001))
    for y in (.006, -.004):
        P.append(plate('rx_btn', [(y + .004, .0098), (y + .004, .0122), (y - .004, .0122), (y - .004, .0098)], RB, .0195, .0206, .0005, sym=False, side=1))
    G.hexbolts(P, [(.022, .0108), (-.02, .0108)], .0195, S, .0012, sym=False, side=-1)
    done('ATT_reflex', P, (0, .15, h))

    # ---- holographic: a low housing on a clamped base, a LARGE window (48 x 34 mm) under a short hood: thin walls
    # swept back to the base as ears, the battery across the back, buttons behind it, screws on the right
    h = .036
    P = []
    mount(P, .028); mount(P, -.028)
    P.append(prism('hg_foot', [(.052, .0095), (.052, .0128), (-.05, .0128), (-.05, .0095)], .032, AL, .0012))
    P.append(plate('hg_lever', [(.04, .0015), (.04, .0075), (-.006, .0068), (-.012, .004), (-.006, .0015)], S, .0165, .0195, .0008, sym=False, side=1))
    P.append(G.loft('hg_body', [(.052, .0128, .0182, .027, (.0028, .0008)), (-.048, .0128, .0182, .027, (.0028, .0008))], AL))
    for s in (1, -1):
        P.append(prism('hg_wall', [(.012, .018), (-.012, .054), (-.048, .054), (-.048, .018)], .003, AL, .001, x=s * .0258))
        P.append(plate('hg_wall_rib', [(.0, .0205), (-.016, .046), (-.02, .046), (-.006, .0205)], AL, .0268, .0283, .0005, sym=False, side=s))
    P.append(prism('hg_roof', [(-.01, .0532), (-.0125, .0562), (-.05, .0562), (-.05, .0532)], .0546, AL, .001))
    P.append(prism('hg_visor', [(-.046, .0562), (-.046, .0572), (-.054, .0556), (-.054, .0536), (-.05, .0536)], .0546, AL, .0006))
    P.append(prism('hg_glass', [(-.04, .0185), (-.04, .0532), (-.0408, .0532), (-.0408, .0185)], .0486, L, .0002))
    P.append(lathe('hg_reticle', [(-.0392, .0036), (-.0392, .0043), (-.0396, .0043), (-.0396, .0036)], D, h, 0, 32, closed=True))
    P.append(lathe('hg_dot', [(-.0392, 0), (-.0392, .0008), (-.0396, .0008), (-.0396, 0)], D, h, 0, 12))
    P.append(lathe_x('hg_battery', [(-.027, .0052), (-.0255, .006), (.0255, .006), (.027, .0052), (.027, 0)], (0, .046, .0182), AL, 28, 1))
    P.append(lathe_x('hg_batcap', [(.027, .0056), (.0285, .0064), (.0325, .0064), (.0335, .0054), (.0335, 0)], (0, .046, .0182), S, 28, 1))
    for x in (-.01, .01):
        P.append(prism('hg_btn', [(.0535, .0138), (.0535, .0176), (.0518, .0176), (.0518, .0138)], .0105, RB, .0006, x=x))
    slotted(P, 'hg_windage', (-.027, .016, .0156), .0022, -1)
    slotted(P, 'hg_elevation', (-.027, .002, .0156), .0022, -1)
    G.hexbolts(P, [(-.03, .05), (-.044, .022)], .0273, S, .0014)
    done('ATT_holo', P, (0, .2, h))

    def glass(P, y0, y1, e, r, obj, Lo, h):
        """a turned optic body from the eyepiece's rear y0 to the objective's front y1 with its two lenses set back"""
        P.append(lathe('tube', [(y0, e - .0016), (y0 - .0012, e), (y0 - Lo * .09, e), (y0 - Lo * .135, r * 1.07), (y0 - Lo * .2, r),
                                (.0165, r), (.0145, r + .003), (-.0145, r + .003), (-.0165, r),
                                (y1 + Lo * .3, r), (y1 + Lo * .17, obj), (y1 + .003, obj), (y1, obj - .0012),
                                (y1, obj - .003), (y1 + .018, obj - .0034), (y1 + Lo * .3, r - .0026), (y0 - Lo * .2, r - .0026), (y0 - .012, e - .003),
                                (y0, e - .003)], AL, h, 0, 64, closed=True))
        P.append(lathe('lens_f', [(y1 + .016, 0), (y1 + .016, obj - .0032), (y1 + .0172, obj - .0032), (y1 + .0172, 0)], L, h, 0, 48))
        P.append(lathe('lens_r', [(y0 - .007, 0), (y0 - .007, e - .0028), (y0 - .0082, e - .0028), (y0 - .0082, 0)], L, h, 0, 48))
        P.append(G.band('lens_ring', y0 - .0058, .0012, e - .0026, S, h, 0, .0012, 48, .0002))

    def scope(name, Lo, r, obj, h, relief, zoom, shade=0.0, tall=.0):
        """Lo sets the eyepiece and objective stations (and with relief the eye point): r the main tube, obj the bell"""
        P = []
        y0, y1 = Lo * .47, -Lo * .6
        e = r * 1.3
        ry = (.03, -.03) if zoom > 2 else (.024, -.024)
        P.append(prism('mountbar', [(ry[0] + .015, .0095), (ry[0] + .015, .0135), (ry[0] + .011, .0156), (ry[1] - .011, .0156), (ry[1] - .015, .0135),
                                    (ry[1] - .015, .0095)], .024, AL, .0015))
        G.slots(P, 'mountcut', [(0, .0125, (ry[0] - ry[1]) * .55, .0034, 0)], .012, RB)
        for yy in ry:
            mount(P, yy)
            P.append(prism('ringpost', [(yy + .007, .0145), (yy + .007, h - r * .3), (yy - .007, h - r * .3), (yy - .007, .0145)], .015, AL, .0018))
            P.append(G.band('ring', yy + .007, .014, r + .0034, AL, h, 0, .0038, 64, .0008))
            for s in (1, -1):
                P.append(prism('ringear', [(yy + .007, h - .003), (yy + .007, h + .003), (yy - .007, h + .003), (yy - .007, h - .003)], .0054, AL, .0008, x=s * (r + .0052)))
                P.append(prism('ringsplit', [(yy + .0072, h - .0003), (yy + .0072, h + .0003), (yy - .0072, h + .0003), (yy - .0072, h - .0003)], .0058, RB, .0001,
                               x=s * (r + .0052)))
                for q in (.0036, -.0036):
                    P.append(G.lathe_z('ringbolt', [(.0028, 0), (.0028, .0018), (.0044, .0018), (.0048, .0013), (.0048, 0)], (s * (r + .0056), yy + q, h), S, 6))
        glass(P, y0, y1, e, r, obj, Lo, h)
        P.append(G.band('accent', y1 + Lo * .17 - .002, .002, obj + .0005, BR, h, 0, .0022, 64, .0003))
        knurl(P, 'bell_grip', y1 + .012, .007, obj + .0006, AL, h, 96, .0028)
        if shade:
            P.append(G.tube_('hood', y1 + .003, y1 - shade, obj + .001, AL, h, 0, bore=obj - .001, n=64, ch=.0006))
        # eyepiece: a thin rubber rim, the fine diopter ring; the power ring with its fin
        P.append(G.band('eyecup', y0 + .004, .008, e + .0012, RB, h, 0, .0028, 64, .0012))
        knurl(P, 'diopter', y0 - .008, Lo * .04 + .004, e + .001, AL, h, 96, .003)
        P.append(prism('diopter_mark', [(y0 - Lo * .1 + .0015, h + e - .0002), (y0 - Lo * .1 + .0015, h + e + .0003), (y0 - Lo * .1 - .003, h + e + .0003),
                                        (y0 - Lo * .1 - .003, h + e - .0002)], .001, WH, .0001))
        if zoom > 2:
            knurl(P, 'power', y0 - Lo * .15, Lo * .045, r * 1.07 + .0024, AL, h, 84, .0032)
            P.append(prism('powerfin', [(y0 - Lo * .156, h + r * 1.07 + .002), (y0 - Lo * .16, h + r * 1.07 + .0075), (y0 - Lo * .178, h + r * 1.07 + .0075),
                                        (y0 - Lo * .186, h + r * 1.07 + .002)], .004, AL, .0009))
        # turrets on the saddle: smooth capped drums, ticks engraved round the skirt, a fine grip round the cap's top
        ht = (.0075 if zoom <= 2 else .015) + tall
        rt = .0098 if zoom <= 2 else .011
        d1 = r + .0052
        top = [(r + .002, 0), (r + .002, rt + .001), (d1, rt + .001), (d1, rt - .0003), (d1 + ht * .45, rt - .0003), (d1 + ht * .45, rt), (d1 + ht - .001, rt),
               (d1 + ht, rt - .001), (d1 + ht, 0)]
        P.append(G.lathe_z('turret_e', top, (0, 0, h), AL, 56))
        P.append(lathe_x('turret_w', top, (0, 0, h), AL, 56, -1))
        zp = lambda d, u, v: (u, v, h + d)
        xp = lambda d, u, v: (-d, u, h + v)
        for nm, pl in (('e', zp), ('w', xp)):
            P.append(boxes('ticks_' + nm, teeth(pl, rt + .0008, rt + .00112, r + .0026, r + .0048, 48, .16), WH))
            if zoom > 2:
                P.append(boxes('capgrip_' + nm, teeth(pl, rt - .0002, rt + .0004, d1 + ht * .55, d1 + ht - .0014, 72, .5), AL))
        if zoom > 2:
            par = [(r + .002, 0), (r + .002, .0102), (r + .0115, .0102), (r + .0125, .0092), (r + .0125, 0)]
            P.append(lathe_x('parallax', par, (0, 0, h), AL, 56, 1))
            P.append(boxes('ticks_p', teeth(lambda d, u, v: (d, u, h + v), .0101, .01045, r + .0035, r + .009, 36, .14), WH))
            P.append(lathe_x('parallax_mark', [(r + .0125, .002), (r + .013, .002), (r + .013, 0)], (0, 0, h), D, 16, 1))
        P.append(prism('index', [(.0162, h + r + .0008), (.0162, h + r + .003), (.0154, h + r + .003), (.0154, h + r + .0008)], .0012, WH, .0001))
        done(name, P, (0, Lo * .47 + relief, h), True)

    scope('ATT_x2', .15, .0162, .0205, .032, .05, 2)
    scope('ATT_x4', .24, .015, .0225, .036, .06, 4, shade=.022)
    scope('ATT_x8', .34, .016, .0295, .042, .07, 8, shade=.055, tall=.004)

    # ---- prism sight (fixed 4x, our own): a short thick body cast with its base, a hooded objective, a light
    # collector strip along the roof, low capped adjusters, a fine diopter ring. Eye point 45 mm behind the eyepiece.
    h = .034
    P = []
    mount(P, .022); mount(P, -.022)
    P.append(prism('pr_base', [(.04, .0095), (.04, .014), (.034, .019), (-.034, .019), (-.04, .014), (-.04, .0095)], .03, AL, .002))
    G.slots(P, 'pr_basecut', [(0, .0142, .03, .0036, 0)], .015, RB)
    P.append(lathe('pr_body', [(.038, .0118), (.038, .0185), (-.03, .0185), (-.042, .0205), (-.042, .0165), (-.03, .0118)], AL, h, 0, 8, phase=math.pi / 8,
                   closed=True))
    for s in (1, -1):
        P.append(plate('pr_flank', [(.03, h - .008), (.03, h + .008), (-.022, h + .008), (-.026, h + .004), (-.026, h - .008)], AL, .017, .0192, .0012, sym=False, side=s))
    G.hexbolts(P, [(.024, h - .0045), (-.02, h - .0045)], .0192, S, .0014)
    P.append(lathe('pr_objective', [(-.04, .0185), (-.04, .0205), (-.06, .0205), (-.0612, .0195), (-.0612, .0172), (-.045, .0168), (-.045, .0185)], AL, h, 0, 64, closed=True))
    P.append(prism('pr_visor', [(-.058, h + .0196), (-.058, h + .0212), (-.074, h + .02), (-.074, h + .0188)], .03, AL, .0005))
    P.append(lathe('pr_lens_f', [(-.047, 0), (-.047, .0168), (-.0482, .0168), (-.0482, 0)], L, h, 0, 48))
    P.append(lathe('pr_eyepiece', [(.052, .0128), (.0532, .0142), (.04, .0142), (.037, .0155), (.037, .0118), (.052, .0118)], AL, h, 0, 64, closed=True))
    knurl(P, 'pr_diopter', .05, .009, .0152, AL, h, 84, .0026)
    P.append(G.band('pr_eyecup', .0585, .0065, .0152, RB, h, 0, .0026, 64, .001))
    P.append(lathe('pr_lens_r', [(.046, 0), (.046, .0118), (.0448, .0118), (.0448, 0)], L, h, 0, 48))
    # the light collector: a strip of fibre in a channel along the roof under a thin guard
    P.append(prism('pr_channel', [(.026, h + .0165), (.026, h + .0186), (-.03, h + .0186), (-.03, h + .0165)], .0105, RB, .0005))
    P.append(prism('pr_fibre', [(.024, h + .0182), (.024, h + .0204), (-.028, h + .0204), (-.028, h + .0182)], .0052, D, .0011))
    for y in (.02, -.004, -.026):
        P.append(prism('pr_fibre_clip', [(y + .0016, h + .018), (y + .0016, h + .0212), (y - .0016, h + .0212), (y - .0016, h + .018)], .0112, AL, .0006))
    # adjusters: two low caps on the right flank
    for y in (.012, -.008):
        P.append(lathe_x('pr_adjust', [(0, .0052), (.003, .0052), (.004, .0044), (.004, 0)], (-.0192, y, h + .0006), AL, 32, -1))
        P.append(plate('pr_adjust_slot', [(y + .0036, h + .0002), (y + .0036, h + .001), (y - .0036, h + .001), (y - .0036, h + .0002)], RB, .0231, .0236, .0001,
                       sym=False, side=-1))
    done('ATT_prism', P, (0, .0975, h), True)
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
