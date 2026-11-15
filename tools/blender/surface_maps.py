"""The guns' material sets, drawn through the texture engine (pbr.py) to the owner's rules: every texture
(docs/art/TEXTURE_RULES.md) and guns in particular (docs/art/GUN_TEXTURE_RULES.md: the full map list, metal with micro
scratches / directional wear / oxidation / roughness variation, grips of rubber with wear and hand oils, coatings that
chip and fade, seven materials each with its own roughness).

4096 px, one repeat every 22 cm of gun (gunkit.uv_project; U runs along the gun): a twentieth of a millimetre a
texel. Each set: <name>_c.jpg, _n.png, _m.png (R ambient occlusion, G roughness, B metallic), _h.png (and _n.jpg /
_m.jpg beside them: the names the guns' own Blender materials read). `SO_IMPORT_ONLY=guntextures` brings them in.

  what the guns wear now (the names their materials know, so no gun is built again):
    wpn_paint    CERAMIC COATING over forged metal (the light guns' shells; near white, the gun's colour multiplies
                 it): the hammer's dishes under the coat, chips and gouges down to steel, rust in the chips, stains
    wpn_metal    forged iron (the light guns' frames): hammer blows, pits, casting grain, bright scratches, rust
    wpn_steel    blued steel: brushed, the tool's passes still faintly in it, the blue rubbed through, pits
    wpn_park     parkerized: phosphate crystals, rubbed smooth and lighter where it is handled, oil
    wpn_poly     glass-filled POLYMER: a sand stipple, the mould's flow, scuffs that go grey, cuts that whiten
    wpn_odg      the same painted olive, scuffed through to the black under it
    wpn_wood     oiled walnut: growth rings and figure along the stock, knots the grain runs round, pores, dents
    wpn_knurl    cut checkering: diamonds, their points worn flat where the hand grips, dirt in the grooves, hand oil
  the rest of the seven materials the gun rules name (drawn here; a gun wears one when its parts are given it in
  weapons.py: that is a rebuild of the gun):
    wpn_anod     ANODIZED aluminium: bead-blasted matte, the dye gone a shade purple-brown with age, bright silver
                 where it is cut through
    wpn_brushed  BRUSHED STEEL: drawn out one way, handled, freckled
    wpn_titanium TITANIUM: turned (the lathe's fine lines), warm grey, straw and blue where it has been hot
    wpn_carbon   CARBON FIBRE: a 2 x 2 twill of tows under resin, the fibres' sheen changing tow by tow
    wpn_rubber   RUBBER grip: moulded pips, compressed and shiny where it is held, hand oil, dirt between the pips

Run: blender --background --python tools/blender/surface_maps.py [-- name name ...]     (PBR_SIZE=1024: a quick look)
(after weapon_textures.py, which still bakes the living guns' sets: build_all.sh runs both in that order)
"""
import math
import os
import sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pbr import F32, Tile, above, hexc, mix, smooth                # noqa: E402
from world_maps import pits                                          # noqa: E402

TILE = .22
STEEL, RUST = hexc('#8f9299'), hexc('#7a4526')


def marks(T, fine=130, deep=8):
    """what handling leaves on any gun: hairlines (most along the gun), a few gouges. A repeat is 22 cm of gun and the
    game lays its own scratches and chips over every copy, so FEW (the first try was a rink)."""
    f = T.lines(fine, (.006, .056), (.00007, .00011), bend=.12, along=.7) * .8
    d = T.lines(deep, (.010, .041), (.00017, .00030), bend=.2, along=.5)
    return f, d


def out(T, alb, height, rough, metal, relief=4.0, cavity=.22):
    T.write(alb, height, rough, metal, relief=relief, cavity=cavity, legacy_normal_jpg=True, legacy_mask_jpg=True)


def blank(T, colour):
    return np.zeros((T.Z, T.Z, 3), F32) + hexc(colour)


def wpn_paint():
    T = Tile("wpn_paint", TILE)
    fine, deep = marks(T)
    low = T.noise(.07, 3)
    dish = 1 - np.clip(T.cells(.011)[0] / .62, 0, 1) ** 2         # forged under the coat
    peel = T.noise(.0012, 2)
    cf = T.noise(.0037, 3) + .45 * T.noise(.0013, 2)
    # (a tile carries FEW chips, in a few places: where a coat chips is its edges, and that is an asset's own maps'
    # work; chips peppered evenly over a shell read as speckled paint)
    where = above(T.noise(.05, 3), .30, .2)
    chip = above(cf, .0035, .03) * where
    rustc = above(cf, .0011, .03) * where
    stain = above(T.noise(.044, 4), .32, .5) * .5
    ding = T.dents(46, (.0004, .0011))
    expose = np.clip(chip + .95 * smooth(.25, .6, deep) + .8 * smooth(.55, .8, ding), 0, 1)
    alb = blank(T, '#ededed') * (1 + .035 * low - .045 * fine)[..., None]
    alb = mix(alb, hexc('#bdb7ab'), stain)
    alb = mix(alb, hexc('#7d8087'), expose)
    alb = mix(alb, RUST, rustc * .7)
    rough = .34 + .06 * peel + .14 * stain + .14 * fine + .08 * expose + .25 * rustc
    out(T, alb, [(-dish, .00010), (low, .00008), (-ding, .00016), (peel, .000010), (-chip, .000060), (-deep, .000050), (-fine, .000010)],
        rough, expose * (1 - .7 * rustc))


def wpn_metal():
    T = Tile("wpn_metal", TILE)
    fine, deep = marks(T)
    low = T.noise(.07, 3)
    dish = 1 - np.clip(T.cells(.010)[0] / .62, 0, 1) ** 2
    dish2 = 1 - np.clip(T.cells(.0042)[0] / .62, 0, 1) ** 2
    grain = T.noise(.0007, 2)
    pit = pits(T, .0008, 1.0) * above(T.noise(.035, 3), .30, .12)       # (in a few patches: evenly spread they read as pepper)
    rmask = np.clip(above(T.noise(.031, 4), .40, .5) * (.2 + .8 * smooth(.35, .85, dish)) * .5 + pit * .55, 0, 1)
    alb = blank(T, '#3a3d45') * (1 + .12 * low + .07 * grain + .10 * (1 - dish))[..., None]
    alb = mix(alb, STEEL, np.clip(.7 * fine + deep, 0, 1) * .8)
    alb = mix(alb, RUST, rmask)
    rough = .58 + .10 * grain - .10 * (1 - dish) - .24 * fine - .26 * deep + .30 * rmask
    # (the hammer's dishes are SHALLOW: at .16 mm deep the frame of a gun in the hands read as pebbled, like mail)
    out(T, alb, [(-dish, .000055), (-dish2, .000014), (low, .00008), (grain, .000008), (-pit, .00008), (-fine, .000012), (-deep, .000060)],
        rough, 1 - .78 * rmask)


def machined(T, step=.0004):
    """the tool's passes: fine parallel lines along the gun, `step` apart, not quite even"""
    v = (np.arange(T.Z, dtype=F32)[:, None] + .5) / T.Z
    n = round(T.m / step)
    return (np.abs(((v * n + T.noise(.03, 2) * .35) % 1.0) - .5) * 2).astype(F32) * np.ones((1, T.Z), F32)


def wpn_steel():
    T = Tile("wpn_steel", TILE)
    fine, deep = marks(T)
    low = T.noise(.07, 3)
    br, br2 = T.brushed(.055), T.brushed(.007)
    tool = machined(T)
    # (WHERE a finish is rubbed through is an asset's own maps' work, by place: a tile carries only the blue lying
    # a little thinner here and there, ragged along the brushing, and its pits in a few patches, never as pepper)
    worn = above(T.noise(.055, 5) + .55 * br + .25 * T.noise(.004, 2), .16, .10)
    pit = pits(T, .0005, 1.0) * above(T.noise(.035, 3), .28, .12)
    smear = above(T.noise(.012, 3), .25, .4)                      # prints: oil in the roughness
    alb = blank(T, '#2b2f37') * (1 + .16 * br + .08 * br2 + .06 * low)[..., None]
    alb = mix(alb, hexc('#33303a'), smooth(.45, .8, T.noise(.09, 2)) * .22)           # the blue is never one colour: plum where the bath ran hot
    alb = mix(alb, hexc('#4c5059') * (1 + .12 * br)[..., None], worn * .45)
    alb = mix(alb, hexc('#a3a6ad'), np.clip(.75 * fine + deep, 0, 1) * .85)
    alb = mix(alb, RUST, pit * .8)
    rough = .34 + .16 * br + .06 * br2 - .12 * worn - .12 * fine - .14 * deep + .3 * pit - .08 * smear + .04 * tool
    out(T, alb, [(low, .00006), (br, .000012), (br2, .000006), (tool, .000005), (-pit, .00008), (-fine, .000012), (-deep, .000060)],
        rough, .86 + .12 * worn - .5 * pit)


def wpn_park():
    T = Tile("wpn_park", TILE)
    fine, deep = marks(T)
    low = T.noise(.07, 3)
    cry, cry2 = T.noise(.0005, 1), T.grain(0)                     # the phosphate's crystals
    streak = T.brushed(.03)
    rub = above(T.noise(.055, 5) + .5 * streak + .3 * cry, .14, .10)          # handled: smoother, lighter; no soft edge
    oil = above(T.noise(.037, 4) + .4 * streak + .25 * cry, .14, .12)
    cut = np.clip(.6 * fine + deep, 0, 1)
    alb = blank(T, '#2f3235') * (1 + .16 * cry + .08 * cry2 + .05 * low)[..., None]
    alb = mix(alb, hexc('#494c50'), rub * .38)
    alb = mix(alb, hexc('#1c1e20'), oil * .35)
    alb = mix(alb, hexc('#8a8d92'), cut * .8)
    rough = .70 + .12 * cry - .20 * rub - .16 * oil - .14 * fine - .2 * deep
    # (a phosphate coat is a layer of crystals, not a metal: metal shows only where it is rubbed thin or cut; and
    # the crystals are FINE: at .014 mm of relief the cover read as stucco)
    out(T, alb, [(low, .00006), (cry * (1 - .6 * rub), .000005), (cry2 * (1 - .6 * rub), .000003), (-fine, .000012), (-deep, .000060)],
        rough, .08 + .30 * rub + .85 * cut)


def polymer(name, base, scuffed, cut_to, k_scuff, k_cut):
    T = Tile(name, TILE)
    fine, deep = marks(T)
    low = T.noise(.07, 3)
    sand, sand2 = T.grain(0), T.noise(.0006, 1)
    flow = T.brushed(.11)                                         # the mould's flow, faint
    scuff = above(T.noise(.044, 5) + .5 * T.brushed(.014) + .3 * sand2, .14, .10) * .7
    cut = np.clip(.7 * fine + deep, 0, 1)
    seam = T.dents(30, (.0003, .0009))                            # sink marks and nicks
    alb = blank(T, base) * (1 + .10 * sand + .06 * flow + .05 * low)[..., None]
    alb = mix(alb, hexc(scuffed), scuff * k_scuff)
    alb = mix(alb, hexc(cut_to), cut * k_cut)
    rough = .68 + .08 * sand - .16 * scuff + .06 * cut
    out(T, alb, [(low, .00005), (sand * (1 - .7 * scuff), .000010), (sand2 * (1 - .7 * scuff), .000012), (-fine, .000012), (-deep, .000060),
                 (-seam, .00008)], rough, 0.0)


def wpn_poly():
    polymer("wpn_poly", '#1b1c1f', '#35373b', '#5c5f63', .55, .7)     # scuffed grey; a cut whitens


def wpn_odg():
    polymer("wpn_odg", '#465034', '#1c1d1c', '#141514', .75, .85)     # the paint scuffed through to the black under it


def wpn_wood():
    T = Tile("wpn_wood", TILE)
    Z = T.Z
    y = (np.arange(Z, dtype=F32)[:, None] + .5) / Z * np.ones((1, Z), F32)
    x = (np.arange(Z, dtype=F32)[None, :] + .5) / Z * np.ones((Z, 1), F32)
    phase = 9 * y + 1.1 * (T.noise(.07, 4) * .9 + .25 * T.brushed(.11))
    knot = np.zeros((Z, Z), F32)
    for kx, ky, R in ((.27, .34, .016), (.71, .78, .010)):         # knots: the grain runs round them
        dx, dy = (x - kx + .5) % 1.0 - .5, (y - ky + .5) % 1.0 - .5
        r = np.hypot(dx, dy) * T.m
        phase = phase + 1.6 * np.exp(-(r / (R * 2.2)) ** 2) * np.tanh(dy * T.m / R)
        knot = np.maximum(knot, smooth(R, R * .55, r) * (.75 + .25 * np.sin(r / .0011 * 2 * math.pi)))
    ring = np.sin(2 * math.pi * phase)
    late = smooth(.55, .95, ring)                                 # the dark late wood: a narrow line
    fig = T.brushed(.028)                                         # figure: the fibres' own streaks
    pores = T.lines(2600, (.0015, .0075), (.00007, .00012), along=1.0, spread=.03)
    ding = T.dents(60, (.0005, .0017))
    hand = above(T.noise(.044, 5), .38, .5)                       # where hands have had it: lighter, smoother
    fine, deep = marks(T, 60, 6)
    alb = blank(T, '#6b3f1f') * (1 + .16 * fig + .10 * T.noise(.07, 3))[..., None]
    alb = mix(alb, hexc('#3a2010'), late * .8)
    alb = mix(alb, hexc('#22110a'), pores * .7)
    alb = mix(alb, hexc('#2a1509'), knot * .85)
    alb = mix(alb, hexc('#96673a'), hand * .45)
    alb = mix(alb, hexc('#2a170c'), smooth(.3, .8, ding) * .5)
    alb = mix(alb, hexc('#b08a5c'), np.clip(fine * .5 + deep, 0, 1) * .5)     # a scratch through the oil: pale wood
    rough = .44 + .10 * fig + .12 * pores + .10 * late - .12 * hand + .12 * ding + .10 * knot
    out(T, alb, [(T.noise(.07, 3), .00006), (-ding, .00020), (fig, .000008), (-late, .000015), (-pores, .000030), (-deep, .000050),
                 (knot, .000030)], rough, 0.0)


def wpn_knurl():
    T = Tile("wpn_knurl", TILE)
    yy, xx = np.mgrid[0:T.Z, 0:T.Z].astype(F32) / T.Z
    n = 64                                                        # diamonds 3.4 mm across
    h = np.minimum(np.abs(np.sin((xx + yy) * math.pi * n)), np.abs(np.sin((xx - yy) * math.pi * n)))
    worn = above(T.noise(.045, 5), .45, .5)                       # points worn flat where the hand grips
    h = np.minimum(h, 1 - .55 * worn)
    dirt = smooth(.35, .05, h) * (.5 + .5 * np.clip(T.noise(.025, 4) + .5, 0, 1))
    oil = above(T.noise(.03, 3), .35, .5)                         # hand oil: a sheen on the flats
    alb = mix(blank(T, '#0d0d0e'), hexc('#2c2d30'), smooth(.1, .9, h))
    alb = mix(alb, hexc('#3d3e42'), worn * smooth(.5, .7, h) * .6)
    alb = mix(alb, hexc('#2a231b'), dirt * .5)
    alb = alb * (1 + .05 * T.grain(0))[..., None]
    rough = .72 - .22 * worn * smooth(.5, .7, h) - .14 * oil + .12 * dirt
    out(T, alb, [(h, .00045), (T.grain(0), .000006)], rough, 0.0, relief=2.0, cavity=.35)


def wpn_anod():
    T = Tile("wpn_anod", TILE)
    fine, deep = marks(T)
    low = T.noise(.07, 3)
    bead = T.grain(0)                                             # bead-blasted before the dye
    bead2 = T.noise(.0004, 1)
    fade = above(T.noise(.06, 4), .35, .6)                        # the dye gone a shade purple-brown with age
    rub = above(T.noise(.04, 5), .25, .5)
    tool = machined(T, .0005)
    cut = np.clip(.75 * fine + deep, 0, 1)
    alb = blank(T, '#24262b') * (1 + .07 * bead + .05 * low)[..., None]
    alb = mix(alb, hexc('#33282c'), fade * .5)
    alb = mix(alb, hexc('#3a3d44'), rub * .5)
    alb = mix(alb, hexc('#c2c5cb'), cut * .9)                     # through the anodizing: bright aluminium
    rough = .52 + .08 * bead - .16 * rub - .2 * cut + .03 * tool
    out(T, alb, [(low, .00005), (bead, .000008), (bead2, .000008), (tool, .000004), (-fine, .000010), (-deep, .000050)], rough,
        .9 + .1 * cut)


def wpn_brushed():
    T = Tile("wpn_brushed", TILE)
    fine, deep = marks(T)
    low = T.noise(.07, 3)
    br, br2 = T.brushed(.08), T.brushed(.012)
    smear = above(T.noise(.012, 3), .28, .4)
    freck = pits(T, .0020, 1.0) * above(T.noise(.05, 3), .5, .5)
    alb = blank(T, '#8e9096') * (1 + .12 * br + .07 * br2 + .04 * low)[..., None]
    alb = mix(alb, hexc('#d0d2d6'), np.clip(.6 * fine + deep, 0, 1) * .7)
    alb = mix(alb, hexc('#5c4a38'), freck * .7)
    rough = .28 + .14 * br + .08 * br2 - .10 * fine + .14 * smear + .35 * freck
    out(T, alb, [(low, .00005), (br, .000014), (br2, .000007), (-fine, .000012), (-deep, .000060), (-freck, .00004)], rough,
        np.clip(1 - .8 * freck, 0, 1))


def wpn_titanium():
    T = Tile("wpn_titanium", TILE)
    fine, deep = marks(T)
    low = T.noise(.07, 3)
    lathe = machined(T, .00025)                                   # turned: the lathe's fine lines
    heat = above(T.noise(.09, 3), .30, .8)                        # where it has been hot: straw, then blue
    hot = above(T.noise(.09, 3) + .3 * T.noise(.03, 2), .10, .5)
    smear = above(T.noise(.012, 3), .25, .4)
    alb = blank(T, '#77726b') * (1 + .06 * lathe + .05 * low)[..., None]
    alb = mix(alb, hexc('#8f7a52'), heat * .45)
    alb = mix(alb, hexc('#4e5f86'), hot * .55)
    alb = mix(alb, hexc('#c4c0b8'), np.clip(.6 * fine + deep, 0, 1) * .7)
    rough = .36 + .08 * lathe - .10 * fine + .12 * smear + .05 * heat
    out(T, alb, [(low, .00005), (lathe, .000007), (-fine, .000012), (-deep, .000055)], rough, 1.0)


def wpn_carbon():
    T = Tile("wpn_carbon", TILE)
    Z = T.Z
    n = 110                                                       # tows 2 mm wide
    yy, xx = np.mgrid[0:Z, 0:Z].astype(F32) / Z * n
    ix, iy = np.floor(xx).astype(np.int32), np.floor(yy).astype(np.int32)
    warp_up = ((ix + iy) % 4) < 2                                 # a 2 x 2 twill
    fx, fy = xx - ix, yy - iy
    across = np.where(warp_up, fx, fy)
    along = np.where(warp_up, fy, fx)
    tow = np.sin(across * math.pi) ** .6                          # a tow's round back
    fibre = T.brushed(.02, axis=0) * warp_up + T.brushed(.02, axis=1) * (1 - warp_up)
    sheen = np.where(warp_up, .62, .38) + .10 * np.sin(along * math.pi)
    fine, deep = marks(T)
    resin = T.noise(.05, 3)
    alb = blank(T, '#101113') * (.75 + sheen * .9 + .25 * fibre)[..., None]
    alb = mix(alb, hexc('#6c6f73'), np.clip(.5 * fine + deep, 0, 1) * .6)     # a scratch in the resin goes grey
    rough = .16 + .10 * (1 - tow) + .06 * resin + .22 * fine + .3 * deep
    out(T, alb, [(tow, .000035), (fibre, .000006), (resin, .00003), (-fine, .000010), (-deep, .000050)], rough, .15 * sheen, relief=3.0)


def wpn_rubber():
    T = Tile("wpn_rubber", TILE)
    Z = T.Z
    n = 150                                                       # pips 1.5 mm apart
    yy, xx = np.mgrid[0:Z, 0:Z].astype(F32) / Z * n
    fx, fy = xx - np.floor(xx) - .5, yy - np.floor(yy) - .5
    pip = np.clip(1 - np.hypot(fx, fy) / .36, 0, 1) ** .7
    held = above(T.noise(.05, 4), .45, .5)                        # compressed and shiny where it is held
    pip = pip * (1 - .6 * held)
    oil = above(T.noise(.03, 3), .35, .5)
    dirt = (1 - pip) * (.4 + .6 * np.clip(T.noise(.02, 4) + .5, 0, 1))
    tear = T.dents(26, (.0005, .0016))                            # nicks and compression damage
    alb = blank(T, '#151516') * (1 + .08 * T.grain(0) + .06 * T.noise(.07, 3))[..., None]
    alb = mix(alb, hexc('#2b2c2e'), held * .5)
    alb = mix(alb, hexc('#3a3127'), dirt * .35)
    alb = mix(alb, hexc('#0a0a0a'), smooth(.4, .8, tear) * .6)
    rough = .82 - .30 * held - .14 * oil + .08 * dirt
    out(T, alb, [(pip, .00022), (T.grain(0), .000008), (-tear, .00015), (T.noise(.07, 3), .00005)], rough, 0.0, relief=2.0, cavity=.35)


def wpn_gold():
    """the light guns' gold at a fastening and a lip (the Sarketh's: a hard gilt over their iron): polished in one
    direction, fine, rubbed duller where it is touched, the iron showing in a nick; never a flat yellow"""
    T = Tile("wpn_gold", TILE)
    fine, deep = marks(T, 80, 4)
    low = T.noise(.07, 3)
    pol, pol2 = T.brushed(.06), T.brushed(.008)
    dull = above(T.noise(.035, 4) + .3 * pol, .22, .2)
    nick = np.clip(.5 * fine + deep, 0, 1)
    alb = blank(T, '#c79a45') * (1 + .08 * pol + .04 * pol2 + .05 * low)[..., None]
    alb = mix(alb, hexc('#9a7434'), dull * .45)
    alb = mix(alb, hexc('#4a4c52'), nick * .6)
    rough = .22 + .08 * pol + .04 * pol2 + .16 * dull + .10 * nick
    out(T, alb, [(low, .00004), (pol, .000005), (pol2, .000003), (-fine, .000010), (-deep, .000045)], rough, 1.0)


def wpn_brass():
    """cartridge brass (rounds, cases, feed lips' followers): drawn, so its lines run along the case; it tarnishes
    where fingers left it and never all over; a few green specks. (A flat gold value failed the gate: unfinished.)"""
    T = Tile("wpn_brass", TILE)
    fine, deep = marks(T, 90, 4)
    low = T.noise(.07, 3)
    draw, draw2 = T.brushed(.09), T.brushed(.012)
    tarn = above(T.noise(.03, 4) + .3 * T.noise(.003, 2), .30, .25)
    spot = pits(T, .0004, 1.5) * above(T.noise(.04, 3), .30, .15)
    alb = blank(T, '#b8893a') * (1 + .10 * draw + .05 * draw2 + .05 * low)[..., None]
    alb = mix(alb, hexc('#7d5a2a'), tarn * .55)
    alb = mix(alb, hexc('#e2c079'), np.clip(.7 * fine + deep, 0, 1) * .7)
    alb = mix(alb, hexc('#4f6b4e'), spot * .6)
    rough = .26 + .10 * draw + .04 * draw2 + .22 * tarn - .08 * fine - .10 * deep + .3 * spot
    out(T, alb, [(low, .00004), (draw, .000006), (draw2, .000004), (-fine, .000010), (-deep, .000045), (-spot, .00003)],
        rough, 1.0 - .5 * spot)


SETS = dict(wpn_paint=wpn_paint, wpn_metal=wpn_metal, wpn_steel=wpn_steel, wpn_park=wpn_park, wpn_poly=wpn_poly, wpn_odg=wpn_odg, wpn_brass=wpn_brass, wpn_gold=wpn_gold,
            wpn_wood=wpn_wood, wpn_knurl=wpn_knurl, wpn_anod=wpn_anod, wpn_brushed=wpn_brushed, wpn_titanium=wpn_titanium,
            wpn_carbon=wpn_carbon, wpn_rubber=wpn_rubber)
ALL = tuple(SETS)

if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    for n_ in (argv or ALL):
        SETS[n_]()
