"""The Sarketh: the species that holds Meridian (docs/story/WORLD.md). One humanoid people, all the same size under
what they wear, ranked by what they are issued. This is the FIRST of them, a Veteran: the body sealed in a suit, in
full armour. Every other rank is this soldier with less on (a Levy, a Runner) or more (a Speaker's set, powered
armour), so the look is settled here and shown to the owner before any other rank is built.

Nobody sees a Sarketh's skin: Earth's air is not theirs, and a helm with no face on it is what a soldier of theirs
looks like to us.

THEIR ARMOUR IS MADE LIKE THEIR GUNS (the owner, 2026-11-14: the light guns are the Sarketh's own technology; the
violet of the Void Requiem set belongs to another species). So, as on the light guns (weapons.py, the energy
class): pale shells over a dark frame, cut in long flat panels with slanted ends; light that is CYAN and comes in
rows of short dashes and in one long thin line; ribbed vents with the light behind them; a little gold at a
fastening. The helm is flat-faced and hard-edged: no eyes, a recessed vent down the middle of the face with a
column of dashes of light in it, a heavy dark brow that comes down to a point over it, cheeks that meet in a
pointed chin, a thin blade of a fin running back over the skull. Their red is cloth only, hanging from the belt
before and behind.

What it must never be: round and soft in the face (the first helm bulged either side of a seam: the owner, "like a
giant butt"); white plate on black with one coloured shoulder (somebody else's trooper); violet.

Built with the plate tools of the player's own armour (void_sentinel.py: an under-suit pushed off the body, a base
surface draped smooth over it, every plate a piece of that base cut to an outline and given thickness and a
chamfered rim; plates are rigid, one bone each), on the same body and skeleton, so it takes the body's clips.

  head    C_head__sarketh_veteran    the helm
  vest    C_vest__sarketh_veteran    cuirass, gorget, belt, pauldrons, upper-arm plates
  hands   C_hands__sarketh_veteran   vambraces with a raised flange, gauntlets
  legs    C_legs__sarketh_veteran    tassets, cuisses, peaked knee cops, greaves
  feet    C_feet__sarketh_veteran    plated boots
  cloth   C_cloth__sarketh_veteran   the tabard and the tail: one layer of cloth with their emblem, simulated

What it is made of (sarketh_surface.py): forged iron, enamel over metal, blackened steel, brass, each with maps of
our own and wear in the corner colours; `--look=dir` renders it so (Cycles), the cloth hanging and moving.

Materials (names are an API): sk_suit, sk_plate (the pale shell), sk_plate_dark (the dark frame), sk_trim (darker
still: belt, cuffs), sk_gold, sk_glow and sk_visor (cyan light), sk_cloth (their red), sk_sole.

  blender -b <saved rigged male build> -P tools/blender/hero/sarketh.py -- male [--rank=runner|levy|veteran|speaker|warden|bearer|colossus]
          [--only=head,vest,...]
          [--save=out.blend] [--tex=dir] [--look=dir [--clips=Idle,Run] [--quick]] [--frames=dir [--n=2]]
  blender -b <a saved build of the set> -P tools/blender/hero/sarketh.py -- male --nobuild --look=dir [--quick]
"""
import math
import os
import sys
import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (HERE, os.path.dirname(HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import void_sentinel as vs                                     # the plate tools (its own set is never built here)
from void_sentinel import A, Cyl, Parts, Base, poly, inter, shell, suit, mirrored, boxed

F32 = np.float32
SET = "sarketh_veteran"
SUIT, PLATE, DARK, TRIM, GLOW, VISOR, CLOTH, SOLE, GOLD = ("sk_suit", "sk_plate", "sk_plate_dark", "sk_trim", "sk_glow", "sk_visor",
                                                          "sk_cloth", "sk_sole", "sk_gold")
# (colour, roughness, metallic) and what a quick look (workbench) shows
PALETTE = {
    SUIT: ((.018, .019, .024), .80, 0.0),
    PLATE: ((.70, .72, .79), .34, .15),
    DARK: ((.150, .158, .185), .50, 1.0),                      # (forged iron: a metal's colour is what it reflects)
    TRIM: ((.070, .075, .090), .40, 1.0),
    GLOW: ((.16, .82, 1.0), .30, 0.0),
    VISOR: ((.16, .82, 1.0), .10, .30),
    CLOTH: ((.20, .020, .024), .88, 0.0),
    SOLE: ((.010, .010, .010), .90, 0.0),
    GOLD: ((.80, .58, .22), .30, 1.0),
}
LOOK = {SUIT: (.040, .042, .050), PLATE: (.78, .80, .87), DARK: (.105, .115, .155), TRIM: (.060, .066, .085), GLOW: (.30, .90, 1.0),
        VISOR: (.30, .90, 1.0), CLOTH: (.40, .045, .05), SOLE: (.02, .02, .02), GOLD: (.84, .63, .28)}
SLOTS = ("head", "vest", "hands", "legs", "feet", "cloth")

# ---- the ranks (docs/story/WORLD.md): one people, all the same size under what they wear, ranked by what they are
# issued. Every rank is the Veteran's set with less on, or more: `skip` = the plates it is not issued ("piece:name",
# matched from the front), `cloth` = which cloths it wears, `fin` = the helm's blade (a mark of standing), and for
# those in POWERED armour `bulk` (metres the whole frame stands further off the body), `thick` (how much heavier
# every plate is), `pauldron` (how much bigger the shoulders), `pack` (what is carried on the back).
RANKS = {
    # the scouts: a sealed suit, a helm, a collar and one shoulder cap, a belly plate, the spine's lames, one plate on
    # the thigh, forearms, knees and shins; nothing that slows a run
    "runner": dict(fin=False, cloth=("tail",), skip=(
        "vest:breast", "vest:vent", "vest:rib", "vest:flank", "vest:blade_back", "vest:loin",
        "vest:rerebrace", "vest:pauldron_mid", "vest:pauldron_low", "vest:pauldron_l", "legs:tasset", "legs:seat", "legs:cuisse_rivets",
        "legs:cuisse_l", "legs:cuisse_step", "legs:ham", "legs:calf", "legs:greave_ridge", "hands:flange", "head:temple_l")),
    # the foot soldiers: a breastplate and one shoulder cap, thighs and shins; no flanks, no lames
    "levy": dict(fin=False, cloth=("tabard",), skip=(
        "vest:rib", "vest:flank", "vest:blade_back", "vest:loin", "vest:rerebrace", "vest:pauldron_mid", "vest:pauldron_low",
        "vest:pauldron_l", "legs:tasset", "legs:cuisse_out", "legs:ham", "legs:calf", "hands:flange")),
    "veteran": dict(),
    # the signals officers: the Veteran's set, a mast of their light on the back, longer cloth
    "speaker": dict(mast=True, long=.13),
    # officers in powered armour
    "warden": dict(bulk=.030, thick=1.7, pauldron=1.42, pack="power"),
    # heavy weapons in powered armour: the drum on the back that feeds the gun
    "bearer": dict(bulk=.034, thick=1.85, pauldron=1.5, pack="drum", fin=False, cloth=("tail",)),
    # the commander's walking war suit
    "colossus": dict(bulk=.060, thick=2.5, pauldron=1.9, pack="power", long=.10),
}
RANK = dict(RANKS["veteran"])
PIECE = ""


def rank(name):
    """which rank is built from here on (the set's name follows it: C_<slot>__sarketh_<rank>)"""
    global SET, RANK
    import sarketh_surface
    RANK = dict(RANKS[name])
    SET = sarketh_surface.SET = "sarketh_" + name


def skipped(name):
    key = f"{PIECE}:{name}"
    return any(key.startswith(s) for s in RANK.get("skip", ()))


class Base(vs.Base):
    """the plate tools, issuing only what this rank is issued, and heavier for those in powered armour"""

    def plate(self, name, region, lift, thick=.0045, mat=None, bevel=.0020, bind="auto", keep=None, level=None, step=None):
        if skipped(name):
            return None
        k = 1.0 if name.endswith("_step") else RANK.get("thick", 1.0)    # (a step comes back through here already scaled)
        return super().plate(name, region, lift * k, thick * k, mat or PLATE, bevel * min(k, 1.6), bind, keep, level, step)

    def light(self, name, pts, top, width=.0022, bind="auto", mirror=True, mat=None):
        if skipped(name):
            return None
        k = RANK.get("thick", 1.0)
        return super().light(name, pts, top * k, width * min(k, 1.5), bind, mirror, mat or GLOW)


def use_tools():
    """the plate tools read their material names from their own module: point them at this set's"""
    vs.SUIT, vs.PLATE, vs.DARK, vs.TRIM, vs.GLOW, vs.VISOR, vs.SOLE = SUIT, PLATE, DARK, TRIM, GLOW, VISOR, SOLE
    vs.TEXTURED = {}                                           # (UVs and maps are laid on each finished piece: sarketh_surface.finish)


def materials():
    import wardrobe
    for name, (col, rough, metal) in PALETTE.items():
        wardrobe.PALETTE.setdefault(name, (col, rough, metal))
        m = wardrobe.material(name)
        b = m.node_tree.nodes.get("Principled BSDF")
        if name in (GLOW, VISOR) and b is not None:
            b.inputs["Emission Color"].default_value = (*col, 1)
            b.inputs["Emission Strength"].default_value = 6.0 if name == GLOW else 3.0
        m.diffuse_color = (*LOOK[name], 1)


def leaf(u0, u1, t0, t1, point=.5, shoulder=.35):
    """a plate that ends in a point: square across the top (t0), its sides running down to `shoulder` of the way
    and then drawn in to a point at t1 (point: where across the plate the tip lies, 0..1)"""
    ts = t0 + (t1 - t0) * shoulder
    return [(u0, t0), (u1, t0), (u1, ts), (u0 + (u1 - u0) * point, t1), (u0, ts)]


def studs(base, name, pts, top, bind, r=.0040, mat=None, mirror=False):
    """rivet heads: a low chamfered head at each point, standing on a plate whose top is `top` above the base (what
    holds a plate on is seen: a plate with nothing fastening it reads as moulded)"""
    import wardrobe
    if skipped(name):
        return
    top, r = top * RANK.get("thick", 1.0), r * min(RANK.get("thick", 1.0), 1.5)
    bm = bmesh.new()
    for p_ in pts:
        loc, n = base.on(p_)
        M = Matrix.Translation(loc + n * (top + r * .20)) @ n.to_track_quat('Z', 'Y').to_matrix().to_4x4()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=r, radius2=r * .60, depth=r * .5, matrix=M)
    o = wardrobe.to_object(bm, "vs_" + name, mat or DARK)
    base.parts.add(o, bind)
    if mirror:
        for c in mirrored([o]):
            base.parts.add(c, bind)


# ------------------------------------------------------------------------------------------------ the cuirass

def vest(info, log=print):
    import wardrobe
    T = info.T
    C, U, Wt, Hp = T["chest"], T["underbust"], T["waist"], T["hips"]
    zc, zu, zw, zh, znb = C["z"], U["z"], Wt["z"], Hp["z"], T["neck_base_z"]
    bulk = RANK.get("bulk", 0.0)
    k = (C["w"] + 2 * bulk) / .355
    S, E, a_ = info.A["S"], info.A["E"], info.A["a"]
    dorsal, thumb = info.A["dorsal"], info.A["thumb"]

    def keep(c, r):
        if r in ("chest", "midriff"):
            return True
        if r in ("upperarm", "forearm"):
            return (Vector((abs(c.x), c.y, c.z)) - E).dot(a_) < .03
        if r == "pelvis":
            return c.z > zh + .005
        if r == "neck":
            return c.z < znb + .060
        return False
    sh = shell(info, keep, .0035 + bulk, cuts=[((0, 0, znb + .036), (0, 0, 1)), ((0, 0, zh + .030), (0, 0, -1)), (E - a_ * .004, a_, True)])
    parts = Parts()
    parts.add(suit(sh, "sk_suit_torso"), "soft")
    base = Base(info, sh, ease=.0015, drape=36, clear=.0058)
    tor = vs.torso_frame(info)
    half = math.pi * tor.R
    lim = C["w"] / 2 + .045 + bulk

    def front(P):
        u, z, r = tor(P)
        return u, np.where(r > lim, z + 10.0, z)

    def back(P):
        u, z, r = tor(P)
        return half - u, np.where(r > lim, z + 10.0, z)

    # ---- the front: ONE breastplate drawn down to a point over the belly, a dark blade down its middle
    zt = zc + .092
    tip = zu - .070
    breast = [(-.046 * k, zt), (-.156 * k, zt - .016), (-.176 * k, zc - .006), (-.150 * k, zu + .018), (-.070 * k, zu - .032), (0, tip),
              (.070 * k, zu - .032), (.150 * k, zu + .018), (.176 * k, zc - .006), (.156 * k, zt - .016), (.046 * k, zt)]
    vz0, vz1 = zu - .036, zt - .014                           # the vent: a slot through the breastplate, a dark plate low in it
    slot = [(-.016 * k, vz1 + .05), (.016 * k, vz1 + .05), (.016 * k, vz0), (-.016 * k, vz0)]
    base.plate("breast", lambda P: inter(poly(*front(P), breast), -poly(*front(P), slot)), .0070, .0052, PLATE, bind="chest", step=(.018, PLATE))
    base.plate("vent", lambda P: poly(*front(P), [(-.0135 * k, vz1 + .012), (.0135 * k, vz1 + .012), (.0135 * k, vz0 + .003), (-.0135 * k, vz0 + .003)]),
               .0026, .0030, DARK, .0012, bind="chest")
    neck = A((0, .02, 0))
    rn = T["neck_w"] / 2 + .034 + bulk * .7

    def rho(P):
        return np.sqrt(P[:, 0] ** 2 + (P[:, 1] - neck[1]) ** 2)
    Sn = A(S)

    def from_joint(P):
        Q = np.array(P, F32)
        Q[:, 0] = np.abs(Q[:, 0])
        return np.sqrt(((Q - Sn) ** 2).sum(1))
    base.plate("yoke", lambda P: inter(rn + .007 - rho(P), .074 - from_joint(P), zc + .099 - P[:, 2], .012 - np.abs(P[:, 0]),
                                       np.abs(P[:, 0]) - (S.x + .012)), .0080, .0050, DARK, bind="chest")
    # the gorget: two rings, the upper standing higher up the neck (the helm sits down into it)
    base.plate("gorget", lambda P: inter(rho(P) - rn, znb - .045 - P[:, 2]), .0095, .0055, PLATE, .0026, bind="chest")
    base.plate("throat", lambda P: inter(rho(P) - (rn - .012), znb - .006 - P[:, 2]), .0105, .0045, DARK, .0022, bind="chest")
    # ---- the belly: a ribbed vent like a light gun's handguard: a dark plate, pale ribs across it either side of
    # the middle, and one line of light down the gap between them
    z0, z1 = zh + .097, zu - .016
    wl = .080 * k
    base.plate("belly", lambda P: poly(*front(P), [(-wl, z1), (wl, z1), (wl * .90, z0 + .004), (-wl * .90, z0 + .004)]), .0056, .0030, DARK, .0014,
               bind="spine")
    nr_ = 7
    pitch = (z1 - z0 - .012) / nr_
    for i in range(nr_):
        top = z1 - .006 - pitch * i
        bot = top - pitch * .58
        w_ = wl * (.93 - .012 * i)
        base.plate(f"rib{i}", lambda P, top=top, bot=bot, w_=w_: poly(*front(P), [(.0085, top), (w_, top), (w_ - .008, bot), (.0085, bot)]),
                   .0056 + .0030 + .0003, .0034, PLATE, .0014, bind="spine")
    # the flanks: two long leaves each side, pointing down and back
    u0, u1 = .090 * k, half * .54
    fz0, fz1 = z0 - .004, zc - .070
    for i in range(2):
        a0 = u0 + (u1 - u0) * (.50 * i)
        a1 = u0 + (u1 - u0) * (.50 * (i + 1)) - .006
        base.plate(f"flank{i}", lambda P, a0=a0, a1=a1: poly(*front(P), leaf(a0, a1, fz1 + .012 * i, fz0 + .020 * i, .62, .45)),
                   .0060, .0042, DARK if i == 0 else PLATE, bind="spine")
    # ---- the back: a spine of lames with their points down, a long leaf over each shoulder blade, loin plates
    sp0, sp1, ns = z0, zc + .090, 4
    sst = (sp1 - sp0) / ns
    for i in range(ns):
        b0, t0 = sp0 + sst * i, sp0 + sst * (i + 1) - .006
        base.plate(f"spine{i}", lambda P, b0=b0, t0=t0: poly(*back(P), [(-.026, t0), (.026, t0), (.026, b0 + .016), (0, b0 - .004), (-.026, b0 + .016)]),
                   .0100, .0050, PLATE, bind="chest" if b0 > zu else "spine")
    base.plate("blade_back", lambda P: poly(*back(P), [(.036, zt), (.150 * k, zt - .010), (.168 * k, zc + .010), (.110 * k, zu - .010), (.036, zc - .050)]),
               .0070, .0050, PLATE, bind="chest", step=(.016, DARK))
    ub1 = half * .44 - .008
    base.plate("loin", lambda P: poly(*back(P), leaf(.036, ub1, zu - .030, z0 + .004, .30, .40)), .0060, .0042, DARK, bind="spine")
    # ---- the belt: a band of dark steel and a lozenge at the front (the tabard hangs from it: legs)
    base.plate("belt", lambda P: inter(zh + .036 - P[:, 2], P[:, 2] - (zh + .088)), .0130, .0060, TRIM, .0020, bind="hips")
    base.plate("boss", lambda P: poly(*front(P), [(0, zh + .112), (.034, zh + .062), (0, zh + .012), (-.034, zh + .062)]),
               .0200, .0050, GOLD, .0020, bind="hips")
    # ---- light, as on their guns: a column of short dashes in the breastplate's vent, one long line down the belly
    # between the ribs, dashes down the spine
    nd = 7
    for i in range(nd):
        z = vz1 - .004 - (vz1 - vz0 - .016) * i / (nd - 1)
        base.light(f"vent{i}", [tor.point(-.0085 * k, z), tor.point(.0085 * k, z)], .0026 + .0030, .0036, "chest", mirror=False, mat=GLOW)
    base.light("belly", [tor.point(0, z1 - .010), tor.point(0, z0 + .014)], .0056 + .0030, .0030, "spine", mirror=False, mat=GLOW)
    for i in (1, 2, 3):
        zl = sp0 + sst * (i + .55)
        base.light(f"spine_l{i}", [tor.point(half - .011, zl), tor.point(half + .011, zl)], .0100 + .0050, .0030,
                   "chest" if zl > zu else "spine", mirror=False, mat=GLOW)
    # ---- what fastens it: rivets round the breastplate's border, brass studs round the belt
    studs(base, "breast_rivets", [tor.point(sg * u_ * k, z_) for sg in (-1, 1) for u_, z_ in
                                  ((.060, zt - .010), (.140, zt - .024), (.163, zc - .004), (.139, zu + .022), (.066, zu - .020))],
          .0070 + .0052, "chest", .0038)
    studs(base, "belt_studs", [tor.point(sg * half * (i + .5) / 9, zh + .062) for sg in (-1, 1) for i in range(1, 9)],
          .0130 + .0060, "hips", .0046, GOLD)
    # ---- the upper-arm plate: a leaf pointing down the arm
    Ra = T["upper_arm_r"] + .010 + bulk
    arm = Cyl(S, E, dorsal, Ra, pos=thumb)
    La = arm.L
    base.plate("rerebrace", lambda P: poly(arm(P)[0], arm(P)[1], leaf(-Ra * 1.5, Ra * 1.5, .150, La - .036, .5, .55)),
               .0060, .0045, PLATE, bind="upperarm", step=(.014, DARK))
    parts += base.parts
    back = max(v.co.y for v in sh.verts if abs(v.co.z - zc) < .04 and abs(v.co.x) < .08)
    carried(parts, back, zc, zu, zh, k)
    base.free()
    sh.free()
    parts += pauldrons(info, log)
    log(f"sarketh: cuirass {len(parts)} parts")
    return wardrobe.join(parts, "C_vest__" + SET)


def carried(parts, back, zc, zu, zh, k):
    """what a rank carries on its back: the power unit of a suit of powered armour, the drum that feeds a heavy gun,
    a signals officer's mast"""
    import wardrobe
    I3 = Matrix.Identity(3)
    th = RANK.get("thick", 1.0)
    pack = RANK.get("pack")
    if pack == "power":
        d = .085 * th
        y = back + .012 * th + d / 2
        boxed(parts, "pack", (.250 * k, d, .300), I3, (0, y, zc + .010), DARK, bevel=.018, bind="chest")
        boxed(parts, "pack_top", (.170 * k, d * .8, .070), I3, (0, y - .006, zc + .190), PLATE, bevel=.014, bind="chest")
        for sg in (-1, 1):
            boxed(parts, "pack_cell", (.052, .056, .240), I3, (sg * .150 * k, y - .008, zc - .020), TRIM, bevel=.012, bind="chest")
            boxed(parts, "pack_cell_cap", (.058, .062, .030), I3, (sg * .150 * k, y - .008, zc + .112), GOLD, bevel=.008, bind="chest")
        for i in range(5):                                         # a ribbed vent down the unit, their light behind it
            boxed(parts, "pack_rib", (.150 * k, .010, .020), I3, (0, y + d / 2 + .002, zc - .090 + i * .042), PLATE, bevel=.004, bind="chest")
        boxed(parts, "pack_light", (.012, .006, .200), I3, (0, y + d / 2 + .0005, zc - .006), GLOW, bevel=.002, bind="chest")
    elif pack == "drum":
        r, w = .105 * th ** .5, .300 * k
        y = back + .010 * th + r
        z = zu + .050
        bm = bmesh.new()
        M = Matrix.Translation((0, y, z)) @ Matrix.Rotation(math.radians(90), 4, 'Y')
        bmesh.ops.create_cone(bm, cap_ends=True, segments=28, radius1=r, radius2=r, depth=w, matrix=M)
        bmesh.ops.bevel(bm, geom=[e for e in bm.edges if abs(abs(e.verts[0].co.x) - w / 2) < 1e-4 and abs(abs(e.verts[1].co.x) - w / 2) < 1e-4],
                        offset=.012, segments=2, affect='EDGES')
        parts.add(wardrobe.to_object(bm, "vs_drum", DARK), "chest")
        for sg in (-1, 1):
            bm = bmesh.new()
            M = Matrix.Translation((sg * (w / 2 + .008), y, z)) @ Matrix.Rotation(math.radians(90), 4, 'Y')
            bmesh.ops.create_cone(bm, cap_ends=True, segments=28, radius1=r * .80, radius2=r * .80, depth=.018, matrix=M)
            parts.add(wardrobe.to_object(bm, "vs_drum_cap", PLATE), "chest")
        boxed(parts, "drum_mount", (.170 * k, r * 1.5, .150), I3, (0, y - r * .55, z + .010), TRIM, bevel=.012, bind="chest")   # what holds it to the back
        boxed(parts, "drum_yoke", (.240 * k, .030, .050), I3, (0, y - r * .15, z + r + .012), PLATE, bevel=.008, bind="chest")
        for i in range(4):                                         # bands round it
            bm = bmesh.new()
            M = Matrix.Translation(((i - 1.5) * w * .24, y, z)) @ Matrix.Rotation(math.radians(90), 4, 'Y')
            bmesh.ops.create_cone(bm, cap_ends=False, segments=28, radius1=r + .004, radius2=r + .004, depth=.016, matrix=M)
            parts.add(wardrobe.to_object(bm, "vs_drum_band", TRIM), "chest")
        # the feed: from the drum's right end down and round to the right hip, where the gun is held
        boxed(parts, "feed_a", (.060, .050, .200), I3, (-(w / 2 + .010), y - .030, z - .120), TRIM, bevel=.010, bind="spine")
        boxed(parts, "feed_b", (.056, .150, .050), I3, (-(w / 2 + .012), y - .110, zh + .085), TRIM, bevel=.010, bind="hips")
        boxed(parts, "feed_port", (.070, .040, .064), I3, (-(w / 2 + .014), y - .200, zh + .085), GOLD, bevel=.008, bind="hips")
    if RANK.get("mast"):
        x, y = -.105 * k, back + .030
        boxed(parts, "mast_foot", (.060, .050, .110), I3, (x, y, zc + .060), DARK, bevel=.010, bind="chest")
        boxed(parts, "mast", (.014, .014, .460), I3, (x, y + .004, zc + .330), TRIM, bevel=.004, bind="chest")
        boxed(parts, "mast_head", (.030, .020, .060), I3, (x, y + .004, zc + .580), PLATE, bevel=.006, bind="chest")
        for i in range(4):
            boxed(parts, "mast_dash", (.050 - .008 * i, .006, .007), I3, (x, y + .004, zc + .300 + i * .060), GLOW, bevel=.002, bind="chest")


def pauldrons(info, log=print):
    """three leaves over each shoulder, laid like feathers: a cap, and two long lames under it each drawn to a point
    down the arm."""
    import sdf
    from boots import mesh_from
    from headgear import relax_on
    S, a_ = info.A["S"], info.A["a"]
    d_, f_ = info.A["dorsal"], info.A["thumb"]
    s = 1.16 * RANK.get("pauldron", 1.0)
    R = np.array((tuple(a_), tuple(d_), tuple(f_)), F32)       # rows: along the arm, up-and-out, forward
    c = A(S + a_ * (.052 * s) + d_ * .020)
    rad = A((.132 * s, .074 * s, .092 * s))

    def form(P):
        return sdf.ellipsoid(P, c, rad, R)
    lo, hi = c - .17 * s, c + .17 * s
    bm = mesh_from(form, lo, hi, .0040, "pauldron", PLATE)
    relax_on(bm, form, 12)
    base = Base(info, bm, field=form, own=True, reach=.0075, keep=.12)

    def loc(P):
        q = (P - c) @ R.T
        return q[:, 0], q[:, 1], q[:, 2]                      # t along the arm, w up-and-out, sd forward

    def lame(P, t0, t1, point=0.0, under=-.030):
        t, w, sd = loc(P)
        return inter(t0 - t, t - (t1 - point * np.abs(sd) / (.09 * s)), under - w)
    base.plate("pauldron_cap", lambda P: lame(P, -.24, .004 * s, .020 * s, -.004 * s), .0125, .0052, PLATE, .0026, bind="pauldron")
    base.plate("pauldron_mid", lambda P: lame(P, -.020 * s, .074 * s, .058 * s, -.008 * s), .0066, .0040, DARK, .0020, bind="pauldron")
    base.plate("pauldron_low", lambda P: lame(P, .040 * s, .132 * s, .086 * s, -.012 * s), .0012, .0036, PLATE, .0018, bind="pauldron")

    def strip(t, half_):
        return [Vector((c + R.T @ A((t, .0, sd))).tolist()) + d_ * .09 for sd in np.linspace(-half_, half_, 5)]
    base.light("pauldron_l", strip(.030 * s, .030 * s), .0066 + .0040, .0022, "pauldron", mirror=False, mat=GLOW)
    left = base.parts
    base.free()
    out = Parts(left)
    for c_ in mirrored(left):
        out.add(c_, "pauldron")
    return out


# ------------------------------------------------------------------------------------------------ the legs

def legs(info, log=print):
    import wardrobe
    import garment
    T = info.T
    Hp = T["hips"]
    zh, zcr = Hp["z"], T["crotch_z"]
    H, K, An = info.L["H"], info.L["K"], info.L["A"]
    boot_top = An.z + .145

    def keep(c, r):
        if r == "thigh":
            return True
        if r in ("shin", "foot"):
            return c.z > An.z + .02
        if r in ("pelvis", "midriff"):
            return c.z < zh + .10
        return False
    bulk = RANK.get("bulk", 0.0)
    sh = shell(info, keep, .0042 + bulk, cuts=[((0, 0, zh + .078), (0, 0, 1)), ((0, 0, An.z + .045), (0, 0, -1))])
    parts = Parts()
    parts.add(suit(sh, "sk_suit_legs"), "soft")
    base = Base(info, sh, ease=.0015, drape=24, clear=.0062)
    Rt = (T["thigh"]["w"] + T["thigh"]["d"]) / 4 + .006 + bulk
    Rs = (T["calf"]["w"] + T["calf"]["d"]) / 4 + .006 + bulk
    fwd = (0, -1, 0)
    th = Cyl(H, K, fwd, Rt, pos=(1, 0, 0))
    thb = Cyl(H, K, (0, 1, 0), Rt, pos=(1, 0, 0))
    sn = Cyl(K, An, fwd, Rs, pos=(1, 0, 0))
    snb = Cyl(K, An, (0, 1, 0), Rs, pos=(1, 0, 0))
    Lt, Ls = th.L, sn.L
    kq = Rt / .105

    def uv(f, P):
        u, t, _ = f(P)
        return u, t
    # ---- the hips: two long leaves hanging at each side from under the belt, a plate behind
    base.plate("tasset", lambda P: poly(*uv(th, P), leaf(.050 * kq, .200 * kq, -.080, .130, .40, .50)), .0105, .0048, PLATE, bind="soft",
               step=(.016, PLATE))
    base.plate("tasset_in", lambda P: poly(*uv(th, P), leaf(-.010 * kq, .078 * kq, -.060, .090, .55, .45)), .0060, .0042, DARK, bind="soft")
    base.plate("seat", lambda P: inter(poly(np.abs(P[:, 0]), P[:, 2], [(.016, zh + .034), (.128 * kq, zh + .034), (.140 * kq, zcr + .070), (.085 * kq, zcr + .030), (.016, zcr + .060)]),
                                       H.y + .02 - P[:, 1]), .0060, .0042, DARK, bind="hips")
    # ---- the thigh: one long cuisse drawn to a point over the knee, a dark plate outside, one behind
    c0, c1 = .150, Lt - .050
    base.plate("cuisse", lambda P: poly(*uv(th, P), leaf(-.072 * kq, .086 * kq, c0, c1, .45, .60)), .0090, .0052, PLATE, .0024, bind="thigh",
               step=(.015, DARK))
    base.plate("cuisse_out", lambda P: poly(*uv(th, P), leaf(.100 * kq, .192 * kq, c0 + .090, c1 - .050, .35, .55)), .0060, .0042, DARK, bind="thigh")
    base.plate("ham", lambda P: poly(*uv(thb, P), [(-.070 * kq, .120), (.070 * kq, .120), (.060 * kq, Lt - .110), (-.060 * kq, Lt - .110)]),
               .0050, .0040, DARK, bind="thigh")
    # ---- the knee: a cop with a peak standing up the thigh
    ks = Rs / .0705
    base.plate("knee", lambda P: poly(*uv(sn, P), [(-.050 * ks, -.036), (0, -.118), (.050 * ks, -.036), (.064 * ks, .004), (.046 * ks, .050), (-.046 * ks, .050), (-.064 * ks, .004)]),
               .0150, .0056, PLATE, .0028, bind="knee")
    # ---- the shin: a long greave, square under the knee and drawn to a point over the instep; a dark ridge; the calf
    g0, g1 = .070, Ls - (boot_top - An.z) - .012
    base.plate("greave", lambda P: poly(*uv(sn, P), leaf(-.062 * ks, .062 * ks, g0, g1, .5, .62)), .0085, .0052, PLATE, .0024, bind="shin")
    base.plate("greave_ridge", lambda P: poly(*uv(sn, P), [(-.011 * ks, g0 + .016), (.011 * ks, g0 + .016), (.006 * ks, g1 - .040), (-.006 * ks, g1 - .040)]),
               .0085 + .0052 + .0002, .0046, DARK, .0020, bind="shin")
    base.plate("calf", lambda P: poly(*uv(snb, P), leaf(-.058 * ks, .058 * ks, .070, g1 - .040, .5, .60)), .0055, .0042, DARK, bind="shin")
    studs(base, "cuisse_rivets", [th.point(-.063 * kq, c0 + .009, Rt + .01), th.point(.077 * kq, c0 + .009, Rt + .01)],
          .0090 + .0052, "thigh", .0036, mirror=True)
    studs(base, "knee_rivets", [sn.point(-.050 * ks, .012, Rs + .02), sn.point(.050 * ks, .012, Rs + .02)], .0150 + .0056, "knee", .0040, mirror=True)
    studs(base, "greave_rivets", [sn.point(-.049 * ks, g0 + .012, Rs + .02), sn.point(.049 * ks, g0 + .012, Rs + .02)],
          .0085 + .0052, "shin", .0036, mirror=True)
    base.light("cuisse_l", [th.point(0.0, c0 + .040, Rt + .01), th.point(0.0, c0 + .210, Rt + .01)], .0090 + .0052 + .0036, .0022, "thigh", mat=GLOW)
    base.light("greave_l", [sn.point(0.0, g0 + .034, Rs + .02), sn.point(0.0, g1 - .064, Rs + .02)], .0085 + .0052 + .0002 + .0046, .0022, "shin",
               mat=GLOW)
    parts += base.parts
    # (their red, the tabard and the tail, is a piece of its own: sarketh_surface.cloth_piece)
    base.free()
    sh.free()
    log(f"sarketh: legs {len(parts)} parts")
    return wardrobe.join(parts, "C_legs__" + SET)


# ------------------------------------------------------------------------------------------------ the gauntlets

def hands(info, log=print):
    import wardrobe
    import skeleton
    T = info.T
    Ar = info.A
    E, W, a_, d_, f_ = Ar["E"], Ar["W"], Ar["a"], Ar["dorsal"], Ar["thumb"]
    Hd = info.H
    pl, pw = T["palm"]["l"], T["palm"]["w"]

    def q(c):
        return Vector((abs(c.x), c.y, c.z))

    def keep_arm(c, r):
        t = (q(c) - E).dot(a_)
        return r in ("forearm", "upperarm", "hand") and -.05 < t < (W - E).dot(a_) + .03

    def keep_hand(c, r):
        return r in ("hand", "forearm") and (q(c) - W).dot(a_) > -.03
    arm_sh = shell(info, keep_arm, .0042 + RANK.get("bulk", 0.0) * .8, cuts=[(E - a_ * .026, -a_, True), (W + a_ * .012, a_, True)])
    hand_sh = shell(info, keep_hand, .0026, cuts=[(W - a_ * .010, -a_, True)])
    parts = Parts()
    parts.add(suit(arm_sh, "sk_suit_arm"), "soft")
    parts.add(suit(hand_sh, "sk_glove", .35), "soft")
    base = Base(info, arm_sh, ease=.0015, drape=20, clear=.0060)
    Rf = T["forearm_r"] + .008
    L = (W - E).length
    out = Cyl(E, W, d_, Rf, pos=f_)
    inn = Cyl(E, W, -d_, Rf, pos=f_)
    elb = Cyl(E, W, d_ * .45 - f_, Rf, pos=d_)

    def uv(f, P):
        u, t, _ = f(P)
        return u, t
    w = Rf * 1.36
    base.plate("couter", lambda P: poly(*uv(elb, P), [(-.026, .010), (0, .000), (.026, .010), (.022, .040), (0, .058), (-.022, .040)]),
               .0052, .0040, DARK, .0018, bind="forearm")
    # the vambrace: a long leaf drawn to a point at the wrist, and along its outer edge a raised flange (a soldier
    # of theirs turns a blow with the forearm)
    base.plate("vambrace", lambda P: poly(*uv(out, P), leaf(-w, w, .060, L - .020, .5, .62)), .0085, .0050, PLATE, .0024, bind="forearm")
    base.plate("flange", lambda P: poly(*uv(out, P), [(-w * .16, .070), (w * .16, .070), (w * .10, L - .070), (-w * .10, L - .070)]),
               .0085 + .0050 + .0002, .0085, DARK, .0030, bind="forearm")
    base.plate("vambrace_in", lambda P: poly(*uv(inn, P), [(-Rf * .95, .074), (Rf * .95, .074), (Rf * .72, L - .048), (-Rf * .72, L - .048)]),
               .0050, .0040, DARK, bind="forearm")
    for i in range(5):
        t = .092 + (L - .190) * i / 4
        base.light(f"flange_l{i}", [out.point(-w * .085, t, Rf + .02), out.point(w * .085, t, Rf + .02)], .0085 + .0050 + .0002 + .0085, .0034,
                   "forearm", mat=GLOW)
    base.plate("cuff", lambda P: inter(L - .026 - out(P)[1], out(P)[1] - (L + .006)), .0072, .0045, TRIM, .0016, bind="forearm")
    parts += base.parts
    base.free()
    hb = Base(info, hand_sh, ease=.0006, drape=0, clear=.003, refine=1, reach=.0075, level=2)
    Wn, an, dn, fn = A(W), A(a_), A(d_), A(f_)

    def hand(P):
        Q = np.array(P, F32)
        Q[:, 0] = np.abs(Q[:, 0])
        d = Q - Wn
        return d @ fn, d @ an, d @ dn

    def back(P, pts):
        u, v, wv = hand(P)
        return inter(poly(u, v, pts), .003 - wv)
    hb.plate("handback", lambda P: back(P, leaf(-pw * .46, pw * .46, .014, pl * 1.04, .5, .66)), .0036, .0032, PLATE, .0012, bind="hand")
    for name in skeleton.FINGERS:
        F = Hd["fingers"][name]
        J = F["joints"]
        rw = F["width"] / 2 + .0016
        for i in range(2):
            seg = Cyl(J[i], J[i + 1], d_, rw, pos=f_)
            Ls = seg.L

            def region(P, seg=seg, Ls=Ls, rw=rw):
                u, t, rho = seg(P)
                return inter(poly(u, t, [(-rw * .86, Ls * .16), (rw * .86, Ls * .16), (rw * .86, Ls * .88), (-rw * .86, Ls * .88)]), rho - (rw + .0045))
            bone = ("pinky" if name == "little" else name) + f"_0{i + 1}"
            hb.plate(f"{name}{i}", region, .0022, .0022, DARK, .0008, bind=bone, level=2)
    parts += hb.parts
    hb.free()
    arm_sh.free()
    hand_sh.free()
    log(f"sarketh: gauntlets {len(parts)} parts")
    return wardrobe.join(parts, "C_hands__" + SET)


# ------------------------------------------------------------------------------------------------ the boots

def feet(info, log=print):
    """plated boots on the body's own boot last (boots.py): the left one built, the right its mirror"""
    import wardrobe
    import boots
    from coat import bisect, keep_largest
    from headgear import relax_on
    shaft_h = .145
    M = boots.Measure(info, shaft_h)
    sole_top = .017
    last = boots.last_sdf(M, sole_top)
    M.last = last
    lo = (M.cx - .09, M.toe_y - .05, -.01)
    hi = (M.cx + .09, M.heel_y + .06, M.top + .04)
    bm = boots.mesh_from(last, lo, hi, .0030, "boot", SUIT)
    relax_on(bm, last, 8)
    bisect(bm, bm.faces[:], (0, 0, M.top), (0, 0, 1), clear=True)
    bisect(bm, bm.faces[:], (0, 0, sole_top - .002), (0, 0, -1), clear=True)
    keep_largest(bm)
    bm.normal_update()
    left = Parts()
    inner = wardrobe.to_object(bm.copy(), "sk_boot", SUIT)
    boots.decimate(inner, .05)
    left.add(inner, "soft")
    base = Base(info, bm, field=last, own=True, reach=.0075, keep=.12)
    y0, y1, ya, za, cx, top = M.toe_y, M.heel_y, M.ank.y, M.ank.z, M.cx, M.top
    SS = M.shin_slices()
    sx_, sy_ = SS[0][1], SS[0][2]
    fr = Cyl((sx_, sy_, 0), (sx_, sy_, 1), (0, -1, 0), .052, pos=(1, 0, 0), mirror=False)
    bk = Cyl((sx_, sy_, 0), (sx_, sy_, 1), (0, 1, 0), .052, pos=(1, 0, 0), mirror=False)
    x_, y_, z_ = (lambda P: P[:, 0]), (lambda P: P[:, 1]), (lambda P: P[:, 2])
    low = za + .004
    # the toe: two lames, each with its point toward the toe (the upper tucked under the shin plate)
    base.plate("toe", lambda P: inter(y_(P) - (y0 + .100) + .55 * np.abs(x_(P) - cx), sole_top + .003 - z_(P), z_(P) - low),
               .0036, .0050, PLATE, .0024, bind="foot", keep=.45)   # (its lower edge clear of the last's own cut: that one is ragged)
    base.plate("instep", lambda P: inter(y0 + .070 - .55 * np.abs(x_(P) - cx) + .050 - y_(P), y_(P) - (ya - .022), sole_top - .010 - z_(P), z_(P) - (za + .010)),
               .0060, .0042, DARK, .0016, bind="foot")
    base.plate("heelcup", lambda P: inter(y1 - .060 - y_(P), z_(P) - (za + .030)), .0045, .0048, DARK, .0018, bind="foot")
    base.plate("shaft_front", lambda P: poly(fr(P)[0], z_(P), [(-.050, top - .026), (.050, top - .026), (.046, za + .070), (0, za + .030), (-.046, za + .070)]),
               .0070, .0050, PLATE, .0020, bind="shin")
    base.plate("shaft_back", lambda P: poly(bk(P)[0], z_(P), [(-.046, za + .052), (.046, za + .052), (.042, top - .030), (-.042, top - .030)]),
               .0050, .0042, DARK, bind="shin")
    base.plate("bootcuff", lambda P: top - .022 - z_(P), .0085, .0050, TRIM, .0018, bind="shin")
    left += base.parts
    base.free()
    sole_fn = boots.outsole_sdf(M, sole_top, heel=0.0)
    sb = boots.mesh_from(sole_fn, (M.cx - .09, M.toe_y - .05, -.012), (M.cx + .09, M.heel_y + .05, sole_top + .01), .0018, "sole", SOLE)
    so = wardrobe.to_object(sb, "sk_sole", SOLE)
    boots.decimate(so, .05)
    left.add(so, "foot")
    out = Parts(left)
    for c_ in mirrored(left):
        out.append(c_)
    log(f"sarketh: boots {len(out)} parts")
    piece = wardrobe.join(out, "C_feet__" + SET)
    bulk = RANK.get("bulk", 0.0)
    if bulk:
        # a powered frame's boots: the same boot made as wide and as long as the legs that stand in it (about the
        # ankle's own axis, so it stays on the ground and under the shin)
        kx, ky = 1 + bulk / .058, 1 + bulk * 1.7 / .28
        for v in piece.data.vertices:
            c_ = cx if v.co.x >= 0 else -cx
            v.co.x = c_ + (v.co.x - c_) * kx
            v.co.y = ya + (v.co.y - ya) * ky
    return piece


# ------------------------------------------------------------------------------------------------ the helm

def helm_form(M):
    """the helm's own form: flat planes round the skull, meeting in hard edges. The face is two planes that are almost
    one (a shallow keel down the middle), standing a little forward at the brow; the cheeks turn back in two more;
    the jaw comes to a pointed chin; the crown is six-sided. Under it the neck seal. (The fin is a blade of its own,
    stood on the crown afterwards: cut from this form it came out a fat, ragged paddle.)"""
    import sdf
    c = np.array(M["c"], F32)
    r = M["r"]
    ez, cz, nz, nr, ny = M["ez"], M["cz"], M["nz"], M["neck_r"], M["neck_y"]
    g = .020
    W, D, H = float(r[0]) + g, float(r[1]) + g, float(r[2]) + g
    fr = M["front"]
    cy = float(c[1])
    nose_y = min(fr["nose"], fr["mouth"]) - .016                # clear of the nose's tip and the lips
    chin_y = fr["chin"] - .012
    planes = []

    def nrm(az, el):
        a, e = math.radians(az), math.radians(el)
        return np.array((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e)), F32)

    def add(az, el, scale=1.0, through=None):
        for s_ in ((1,) if az in (0, 180) else (1, -1)):
            n = nrm(az * s_, el)
            if through is None:
                d = float(math.sqrt((n[0] * W) ** 2 + (n[1] * D) ** 2 + (n[2] * H) ** 2)) * scale
            else:
                d = float(n @ (np.array((through[0] * s_, through[1], through[2]), F32) - c))
            planes.append((n, d))
    add(0, 90, .955)                                            # the crown: a flat top, six sides
    add(0, 52, .985)
    add(62, 50)
    add(122, 50)
    add(180, 54)
    add(74, 22, .985)
    add(132, 24, .990)
    add(180, 26)
    add(14, -4, through=(0, nose_y, ez - .034))                 # the face: flat, leaning out toward the brow
    add(54, -3, through=(W * .60, nose_y + .030, ez - .030))    # the cheeks turn back
    add(90, 0, .985)
    add(144, 0)
    add(180, 0)
    add(24, -44, through=(0, chin_y, cz - .010))                # the jaw, to a pointed chin
    add(100, -26, through=(W * .86, cy, cz + .018))
    add(150, -30, through=(W * .6, cy + D * .78, cz + .004))
    add(180, -34, through=(0, cy + D * .9, cz + .006))
    k = .0035

    def skull(P):
        q = P - c
        d = None
        for n, dd in planes:
            e = q @ n - dd
            d = e if d is None else sdf.smax(d, e, k)
        return d

    def form(P):
        d = sdf.smax(skull(P), (cz - .036) - P[:, 2], k)
        neck = sdf.round_cone(P, np.array((0, ny, cz - .002), F32), np.array((0, ny + .006, nz - .032), F32), nr + .016, nr + .030)
        return np.minimum(d, neck)
    back_y = cy + D + .01
    top_z = float(c[2]) + H + .01
    return form, dict(W=W, D=D, H=H, c=c, back_y=back_y, top_z=top_z, front_y=min(nose_y, chin_y) - .02, skull=skull)


def head(info, log=print):
    """the helm: no eyes. Down the middle of a flat face a recessed vent with a column of dashes of light in it (as in
    a light gun's cage); a pale cheek plate each side of it, the two meeting under it in a pointed chin; a heavy dark
    brow across the top of the face that comes down to a point over the vent; the fin plated from the brow to its
    tip; dark plates over the temples and the back of the skull; a jaw plate each side; three lames at the nape."""
    import wardrobe
    import headgear
    from boots import mesh_from, decimate
    M = headgear.head_measures(info)
    form, G = helm_form(M)
    c, ez, cz, nz = G["c"], M["ez"], M["cz"], M["nz"]
    W, D, H = G["W"], G["D"], G["H"]
    skull = G["skull"]
    cy = float(c[1])
    lo = (-W - .05, G["front_y"] - .04, nz - .06)
    hi = (W + .05, G["back_y"] + .05, G["top_z"] + .05)
    parts = Parts()
    bm = mesh_from(form, lo, hi, .0030, "helm", SUIT)
    under = wardrobe.to_object(bm.copy(), "sk_helm_base", SUIT)
    decimate(under, .05)
    parts.add(under, "head")
    base = Base(info, bm, field=form, own=True, reach=.0075, keep=.34)   # (kept finer than a body plate: these are small and seen close)
    R_ = (W + D) / 2
    rad = math.radians

    def U(P):
        return np.arctan2(np.abs(P[:, 0]), -(P[:, 1] - cy)) * R_

    def Z(P):
        return P[:, 2]

    def X(P):
        return np.abs(P[:, 0])

    def fore(P):
        return P[:, 1] - cy                                       # negative on the front half
    zb = ez + .030                                                # the brow line
    wk = .0105                                                    # half the fin's strip over the crown
    vw = .0165                                                    # half the vent

    def brow_low(P):                                              # the brow's lower edge: down to a point over the vent
        return zb - .026 * np.maximum(1.0 - U(P) / (rad(30) * R_), 0.0)
    # the vent: a dark plate set low in the middle of the face, from under the brow to the chin
    base.plate("vent", lambda P: inter(X(P) - vw, Z(P) - (zb + .004), (cz - .014) - Z(P), fore(P)), .0006, .0026, DARK, .0010, bind="head", keep=.5)
    # the cheeks: one pale plate each side of the vent, flat, the two drawn down to meet in a pointed chin
    base.plate("cheek", lambda P: inter(vw + .0030 - X(P), Z(P) - (brow_low(P) - .004), (cz - .036) + 1.05 * np.maximum(X(P) - .012, 0) - Z(P), U(P) - rad(60) * R_,
                                        fore(P)), .0052, .0054, PLATE, .0030, bind="head")
    # the brow: heavy, dark, standing off the face
    base.plate("brow", lambda P: inter(brow_low(P) - Z(P), Z(P) - (zb + .030), U(P) - rad(72) * R_, fore(P)), .0088, .0060, DARK, .0030, bind="head")
    # the crown: one plate over the whole top of the skull (the fin stands on its middle)
    base.plate("crown", lambda P: (zb + .034) - Z(P), .0030, .0046, PLATE, .0022, bind="head")
    base.plate("temple", lambda P: poly(U(P), Z(P), [(rad(64) * R_, zb - .050), (rad(118) * R_, zb - .040), (rad(118) * R_, zb + .028), (rad(76) * R_, zb + .028)]),
               .0058, .0046, DARK, .0022, bind="head")
    base.plate("jaw", lambda P: poly(U(P), Z(P), [(rad(64) * R_, zb - .056), (rad(112) * R_, zb - .046), (rad(108) * R_, cz - .018), (rad(66) * R_, cz - .034)]),
               .0050, .0048, PLATE, .0026, bind="head")
    base.plate("back", lambda P: inter(rad(122) * R_ - U(P), (cz + .056) - Z(P), Z(P) - (zb + .028)), .0030, .0046, DARK, .0020, bind="head")
    for k_, (z0, z1) in enumerate(((cz + .014, cz + .050), (cz - .018, cz + .018), (cz - .046, cz - .014))):
        base.plate(f"nape{k_}", lambda P, z0=z0, z1=z1: inter(z0 - Z(P), Z(P) - z1, rad(112) * R_ - U(P)), .0040 + .0042 * k_, .0046,
                   PLATE if k_ != 1 else DARK, .0022, bind="head")
    # light: the column of dashes in the vent, a dash at each temple
    nd = 8
    za, zz = zb - .034, cz + .002
    for i in range(nd):
        z = za + (zz - za) * i / (nd - 1)
        base.light(f"grille{i}", [Vector((-vw * .62, cy - D - .08, z)), Vector((vw * .62, cy - D - .08, z))], .0006 + .0026, .0038, "head",
                   mirror=False, mat=VISOR)

    def at(a, z):
        return Vector((math.sin(a) * (R_ + .03), cy - math.cos(a) * (R_ + .03), z))
    base.light("temple_l", [at(rad(84), zb - .012), at(rad(108), zb - .008)], .0058 + .0046, .0024, "head", mat=GLOW)
    parts += base.parts
    base.free()
    # the fin: a thin blade on the crown's middle line, rising from behind the brow and swept back past the skull;
    # a line of light along each side of it
    zt = float(c[2]) + H * .955 + .0076                            # the crown plate's top
    y0, y1 = cy - D * .62, cy + D * 1.60
    prof = [(y0, zt - .012), (y0 + .022, zt + .020), (cy - D * .05, zt + .044), (cy + D * .70, zt + .050), (y1 - .045, zt + .034), (y1, zt + .006),
            (y1 - .060, zt - .018), (cy + D * .55, zt - .085), (cy - D * .30, zt - .040)]
    for name, mat, hw, pts in (("sk_fin", PLATE, .0052, prof),
                               ("sk_fin_light", GLOW, .0058, [(cy - D * .30, zt + .017), (y1 - .085, zt + .020), (y1 - .100, zt + .0145), (cy - D * .30, zt + .0115)])):
        if not RANK.get("fin", True):                              # (the blade is a mark of standing)
            break
        fb = bmesh.new()
        left = [fb.verts.new((-hw, y, z)) for y, z in pts]
        right = [fb.verts.new((hw, y, z)) for y, z in pts]
        fb.faces.new(left)
        fb.faces.new(right[::-1])
        n_ = len(pts)
        for i in range(n_):
            j = (i + 1) % n_
            fb.faces.new((left[j], left[i], right[i], right[j]))
        bmesh.ops.recalc_face_normals(fb, faces=fb.faces[:])
        if mat == PLATE:
            bmesh.ops.bevel(fb, geom=[e for e in fb.edges], offset=.0016, segments=1, affect='EDGES')
        o = wardrobe.to_object(fb, name, mat)
        parts.add(o, "head")
    log(f"sarketh: helm {len(parts)} parts")
    return wardrobe.join(parts, "C_head__" + SET)


def cloth(info, log=print):
    import sarketh_surface
    return sarketh_surface.cloth_piece(info, log, RANK.get("cloth"), RANK.get("long", 0.0), RANK.get("bulk", 0.0))


BUILDERS = {"head": head, "vest": vest, "hands": hands, "legs": legs, "feet": feet, "cloth": cloth}


def build(info, log=print, only=None):
    global PIECE
    use_tools()
    materials()
    out = []
    for slot in SLOTS:
        if only is None or slot in only:
            PIECE = slot
            out.append(BUILDERS[slot](info, log))
    return [o for o in out if o is not None]


def main():
    import targets
    import wardrobe
    argv = sys.argv[sys.argv.index("--") + 1:]
    sex = argv[0]
    flags = {a.split("=")[0]: (a.split("=", 1)[1] if "=" in a else True) for a in argv[1:]}
    T = targets.SEXES[sex]

    def log(*a):
        print("[sarketh]", *a, flush=True)
    arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    body = bpy.data.objects["B_body"]
    arm.animation_data_create()
    arm.animation_data.action = None
    for pb in arm.pose.bones:
        pb.rotation_mode = 'QUATERNION'
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.location = (0, 0, 0)
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()
    only = flags["--only"].split(",") if isinstance(flags.get("--only"), str) else None
    rank(flags["--rank"] if isinstance(flags.get("--rank"), str) else "veteran")
    log(f"rank: {SET}")
    if flags.get("--nobuild"):                                 # a saved build of the set: only look at it
        import sarketh_surface as surface
        clips = flags["--clips"].split(",") if isinstance(flags.get("--clips"), str) else ["Idle", "Run"]
        surface.look(arm, flags["--look"], T, lambda o: o.name.endswith("__" + SET), clips, log, quick=bool(flags.get("--quick")))
        return
    for o in list(bpy.data.objects):
        if o.name.endswith("__" + SET) and (only is None or o.name.split("__")[0][2:] in only):
            bpy.data.objects.remove(o)
    info = wardrobe.BodyInfo(body, T)
    pieces = build(info, log, only)
    info.free()
    import sarketh_surface as surface
    for p in pieces:
        if p.name.startswith("C_cloth__"):
            surface.hang(p, arm)
            log(f"{p.name}: {vs.tris(p)} triangles")
            continue
        wardrobe.skin_like_body(p, body, arm)
        if p.name.startswith("C_head__"):
            for g in list(p.vertex_groups):
                p.vertex_groups.remove(g)
            p.vertex_groups.new(name="head").add(list(range(len(p.data.vertices))), 1.0, 'REPLACE')
        vs.after_skin(p, arm)
        log(f"{p.name}: {vs.tris(p)} triangles, materials {[s.material.name for s in p.material_slots]}")
    log(f"the set: {sum(vs.tris(o) for o in bpy.data.objects if o.name.endswith('__' + SET))} triangles")
    import tempfile
    made = [o for o in bpy.data.objects if o.name.endswith("__" + SET)]
    surface.finish(made, flags["--tex"] if isinstance(flags.get("--tex"), str) else os.path.join(tempfile.gettempdir(), "sarketh_tex"), log)
    arm.animation_data.action = bpy.data.actions.get("Idle")
    if isinstance(flags.get("--save"), str):
        bpy.ops.wm.save_as_mainfile(filepath=flags["--save"])
        log(f"saved {flags['--save']}")
    if isinstance(flags.get("--frames"), str):
        clips = flags["--clips"].split(",") if isinstance(flags.get("--clips"), str) else []
        vs.frames(arm, flags["--frames"], clips, int(flags.get("--n", 2)), T, lambda o: o.name.endswith("__" + SET))
    if isinstance(flags.get("--look"), str):
        clips = flags["--clips"].split(",") if isinstance(flags.get("--clips"), str) else ["Idle", "Run"]
        surface.look(arm, flags["--look"], T, lambda o: o.name.endswith("__" + SET), clips, log, quick=bool(flags.get("--quick")))


if __name__ == "__main__":
    main()
