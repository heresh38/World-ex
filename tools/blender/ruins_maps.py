"""Meridian's surfaces a player walks up to, drawn anew through the texture engine (pbr.py) at 4096 px to the
owner's texture rules (docs/art/TEXTURE_RULES.md). Same names, layouts and colours as ruins_textures.py made them
with (meridian.py and citykit.py lay their UVs by those: a slab is still a metre, a cladding panel still 1.2 x 0.6),
so nothing is built again; that script's own painters do not hold above 1024 px (see the note there). Run AFTER it.

  ru_concrete   cast concrete, the form boards' eight courses: sand and aggregate, bug holes, tie holes, hairline
                and wider cracks, spalled patches down to the aggregate, soot, damp gone green, rain runs
  ru_fracture   a broken concrete face: the break's facets, aggregate standing out of it, dust in the hollows
  ru_asphalt    an old road: stones in tar, alligator cracking, potholes with broken lips, patches, ash and grit
  ru_stone      plaza slabs 1 x 1 m: grained, cracked, some lifted, a few gone to dirt, moss in the joints
  ru_metal      painted structural steel: orange peel, chipped to bare metal, rust that stands in scales and runs
  ru_panel      facade cladding 1 x 1.5 m: seams and fixings, sun-bleached, streaked, burnt and blistered
  ru_rubble     ground debris: ash, gravel, crumbs, chunks
  ru_ceramic    housing cladding 1.2 x 0.6 m: glazed, crazed, rain dirt, a few broken to the backing
  ru_sandstone  civic ashlar, running bond: bedding, tooling, pits, arrises worn round, soot under the courses
  ru_corrugate  corrugated sheet (and the freight boxes' three paints): faded, dented, rust at the laps and down
  ru_tile       indoor floor tiles 0.6 m, two tones: glazed, scratched, cracked, dirt in the joints, dust
  ru_plaster    painted plaster: roller stipple, peeling to the grey under it with curled edges, water stains
  ru_brass      bronze trim gone dull: brushed, handled, verdigris standing in crusts

Run: blender --background --python tools/blender/ruins_maps.py [-- name ...]     (PBR_SIZE=1024 for a quick look)
"""
import math
import os
import sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pbr import F32, Tile, above, hexc, mix, smooth                # noqa: E402
from world_maps import panel_uv, pits                               # noqa: E402


def blank(T, colour):
    return np.zeros((T.Z, T.Z, 3), F32) + hexc(colour)


def ru_concrete():
    T = Tile("ru_concrete", 2.5)
    Z = T.Z
    sand = T.grain(1)
    agg = smooth(.55, .15, T.cells(.012)[0])
    big, mott = T.noise(1.2, 4), T.noise(.25, 4)
    bug = (pits(T, .0010, 2.0) + pits(T, .0003, 4.0)) * (.15 + .85 * above(T.noise(.6, 3), .4, .5))
    hair = T.cracks(.7, share=.22, width=.0008)
    wide = T.cracks(1.6, share=.10, width=.0030)
    y = (np.arange(Z, dtype=F32)[:, None] + .5) / Z * 8
    seam = smooth(.97, 1.0, np.abs((y % 1.0) - .5) * 2) * np.ones((1, Z), F32)       # eight board courses
    wood = T.brushed(.5) * (1 - seam)
    pu, pv, W, H = panel_uv(T, 4, 8, .5)                          # a tie hole in each bay of each course
    tie = np.clip(1 - np.hypot(pu - W / 2, pv - H / 2) / .014, 0, 1) ** .5
    spall = above(T.noise(.35, 4), .07, .12)                      # the face knocked off: aggregate and a ragged lip
    soot = above(T.noise(.9, 3), .22, .5)
    damp = above(T.noise(.7, 3), .12, .3)
    rain = T.streaks(50, (.3, 2.0), (.015, .10), (.25, 1.0))
    alb = blank(T, '#87837b') * (1 + .08 * big + .06 * mott + .035 * sand + .03 * wood)[..., None]
    alb = mix(alb, hexc('#6a665f'), agg * spall * .8)
    alb = mix(alb, hexc('#a09a8e'), spall * (1 - agg) * .5)       # fresh broken concrete is paler
    alb = mix(alb, hexc('#4b4843'), np.clip(bug + tie, 0, 1) * .8)
    alb = mix(alb, hexc('#2e2c29'), np.clip(hair + wide, 0, 1) * .85)
    alb = mix(alb, hexc('#3a3835'), soot * .40)
    alb = mix(alb, hexc('#4a4f3c'), damp * .40)
    alb = mix(alb, hexc('#5f584a'), rain * .32)
    alb = mix(alb, hexc('#66635d'), seam * .5)
    rough = .86 + .05 * sand - .08 * damp + .06 * rain + .05 * spall
    T.write(alb, [(sand, .00018), (mott, .0012), (big, .003), (-np.clip(bug, 0, 1), .0035), (-tie, .012), (-hair, .0016), (-wide, .0060),
                  (seam, .0015), (wood, .00025), (-spall, .0080), (agg * spall, .0030)], rough, 0.0, dust=(hexc('#77736a'), .4))


def ru_fracture():
    T = Tile("ru_fracture", 1.5)
    d1, d2, cid = T.cells(.09, warp=.03)                          # the break's facets: each its own plane
    yy, xx = np.mgrid[0:T.Z, 0:T.Z].astype(F32) / T.Z
    facet = (cid - .5) + (xx * np.cos(cid * 40) + yy * np.sin(cid * 40)) * 1.2 * (cid - .5)
    edge = smooth(.10, .0, d2 - d1)
    ad, _, aid = T.cells(.018, warp=.004)
    stone = smooth(.52, .22, ad)                                  # aggregate standing out of the break
    peb = smooth(.5, .2, T.cells(.006)[0])
    fine = T.noise(.02, 3)
    alb = blank(T, '#928d83') * (1 + .10 * T.noise(.5, 3) + .07 * fine + .05 * T.grain(1) + .12 * (cid - .5))[..., None]
    alb = mix(alb, hexc('#6c675f'), stone * (.5 + .5 * aid) * .7)
    alb = mix(alb, hexc('#b3ad9f'), stone * smooth(.7, 1.0, aid) * .5)
    alb = mix(alb, hexc('#5e5a52'), peb * .25)
    alb = mix(alb, hexc('#3d3a36'), edge * .22)
    T.write(alb, [(facet, .020), (-edge, .003), (stone, .0045), (peb, .0012), (fine, .0015), (T.grain(1), .0003)], .94, 0.0,
            relief=1.3, dust=(hexc('#8a857b'), .55))


def ru_asphalt():
    T = Tile("ru_asphalt", 6.0)
    ad, _, aid = T.cells(.009, warp=.002)
    stone = smooth(.60, .28, ad)
    big = T.noise(2.0, 3)
    gator = T.cracks(.22, share=.30, width=.0030)                 # alligator cracking, in patches
    long_ = T.cracks(1.6, share=.25, width=.0060)
    pot = T.dents(7, (.12, .30))
    hole = smooth(.35, .6, pot + .25 * T.noise(.15, 3))           # potholes with broken lips
    lip = smooth(.2, .35, pot) * (1 - hole)
    patch = above(T.noise(1.8, 2), .10, .02)                      # a repair: newer, darker, smoother
    ash = above(T.noise(.9, 4), .22, .5)
    oil = above(T.noise(.5, 4), .05, .2)
    alb = blank(T, '#3d3f43') * (1 + .12 * big + .10 * (aid - .5) * stone)[..., None]
    alb = mix(alb, hexc('#5a5c60'), stone * smooth(.6, 1.0, aid) * .55)     # worn stones show paler
    alb = mix(alb, hexc('#232427'), (1 - stone) * .45)
    alb = mix(alb, hexc('#28292b'), patch * .55)
    alb = mix(alb, hexc('#101112'), np.clip(gator + long_, 0, 1) * .9)
    alb = mix(alb, hexc('#3a352c'), hole * .9)
    alb = mix(alb, hexc('#58544d'), ash * .40)
    alb = mix(alb, hexc('#161719'), oil * .6)
    rough = .82 - .10 * stone + .10 * ash - .30 * oil - .08 * patch + .1 * hole
    T.write(alb, [(stone * (1 - .6 * patch), .0030), (big, .010), (-gator, .0045), (-long_, .010), (-hole, .045), (lip, .008),
                  (T.grain(1), .0003), (hole * T.noise(.03, 3), .008)], rough, 0.0, relief=1.4, dust=(hexc('#5b574f'), .45))


def ru_stone():
    T = Tile("ru_stone", 4.0)
    J, edge, ra, rb = T.grid(4, 4, joint=.009, wander=.003)
    _, _, cid = T.cells(.004)
    big = T.noise(1.5, 3)
    gone = (ra < .06).astype(F32)                                 # a slab gone to dirt
    crack = T.cracks(1.1, share=.16, width=.0020) * (1 - gone)
    hole = pits(T, .0012, 1.3)
    stain = above(T.noise(.5, 4), .10, .25)
    moss = above(T.noise(.3, 4), .35, .4) * smooth(.05, .0, edge)
    by_joint = smooth(.08, .0, edge)
    dirt = np.clip(T.noise(.06, 4) * .5 + .5, 0, 1)
    alb = blank(T, '#73716b') * (1 + .22 * (rb - .5) + .08 * big)[..., None]
    alb = mix(alb, hexc('#9a978f'), smooth(.80, .96, cid) * .5)
    alb = mix(alb, hexc('#4d4b47'), smooth(.20, .04, cid) * .5)
    alb = mix(alb, hexc('#3c362e') * (1 + .5 * dirt)[..., None], np.clip(gone + J * .85, 0, 1))
    alb = mix(alb, hexc('#2a2823'), np.clip(crack + stain * .5 + by_joint * .35, 0, 1) * .8)
    alb = mix(alb, hexc('#3f4a2c'), moss * .7)
    rough = .76 + .16 * J + .14 * gone + .10 * by_joint + .08 * (cid - .5) + .12 * moss
    T.write(alb, [(-J, .010), (rb - .5, .010), (-gone, .018), (gone * dirt, .010), (cid - .5, .0003), (-crack, .004), (-hole, .002),
                  (T.noise(.6, 3), .002), (moss, .003)], rough, 0.0, relief=1.8, dust=(hexc('#625e55'), .5))


def ru_metal():
    T = Tile("ru_metal", 2.0)
    peel = T.noise(.004, 2)
    big = T.noise(.8, 3)
    scr = T.lines(900, (.02, .35), (.0003, .0009))
    deep = T.lines(40, (.06, .5), (.0010, .0022))
    cf = T.noise(.05, 4) + .5 * T.noise(.012, 3)
    chip = above(cf, .06, .04)
    rf = T.noise(.30, 4) + .4 * T.noise(.06, 3)
    rust = above(rf, .16, .12)
    halo = above(rf, .26, .2) * (1 - rust)                        # the stain round a bloom
    fd, _, fid = T.cells(.007, warp=.002)
    scale = smooth(.62, .25, fd) * rust                           # rust stands in scales
    runs = T.streaks(60, (.2, 1.4), (.006, .04), (.3, 1.0)) * above(rf, .5, .6)
    pit = pits(T, .0030, 1.2)
    bare = np.clip(chip + .6 * scr + deep, 0, 1) * (1 - rust)
    alb = blank(T, '#32363b') * (1 + .12 * big + .05 * peel)[..., None]
    alb = mix(alb, hexc('#787a7d'), bare * .85)
    alb = mix(alb, hexc('#5a3018'), np.clip(halo * .45 + runs * .5, 0, 1))
    alb = mix(alb, hexc('#522c18') * (1 + .5 * (fid - .5))[..., None], rust)
    alb = mix(alb, hexc('#8a4f24'), scale * smooth(.6, 1.0, fid) * .6)
    rough = .52 + .06 * peel - .20 * bare + .40 * rust + .12 * halo + .1 * runs
    metal = np.clip(.15 + .85 * bare - rust, 0, 1)
    T.write(alb, [(peel, .00004), (big, .0015), (-chip, .00018), (-scr, .00008), (-deep, .0004), (scale, .0012), (rust, .0005),
                  (-pit, .0006)], rough, metal, relief=2.2, dust=(hexc('#4a4640'), .3))


def ru_panel():
    T = Tile("ru_panel", 3.0)
    J, edge, ra, rb = T.grid(3, 2, joint=.010)
    pu, pv, W, H = panel_uv(T, 3, 2, 0.0)
    fix = np.zeros((T.Z, T.Z), F32)                                # a fixing near each corner and mid-edge
    for fx in (.06, W / 2, W - .06):
        for fy in (.06, H / 2, H - .06):
            if abs(fx - W / 2) < 1e-6 and abs(fy - H / 2) < 1e-6:
                continue
            fix = np.maximum(fix, np.clip(1 - np.hypot(pu - fx, pv - fy) / .011, 0, 1) ** .5)
    roll = smooth(0, .012, edge)
    brush = T.brushed(.4, axis=0)
    big = T.noise(1.2, 3)
    bleach = above(T.noise(1.0, 3), .35, .6)
    rain = T.streaks(70, (.3, 1.6), (.01, .07), (.25, 1.0))
    bf = T.noise(.7, 3)
    burn = above(bf, .10, .2)
    bd, _, _ = T.cells(.012, warp=.003)
    blister = smooth(.55, .2, bd) * above(bf, .16, .2)            # paint blistered round a burn
    scr = T.lines(600, (.03, .5), (.0003, .0010))
    alb = blank(T, '#484b51') * (1 + .16 * (ra - .5) + .07 * brush + .06 * big)[..., None]
    alb = mix(alb, hexc('#7b7d80'), bleach * .28)
    alb = mix(alb, hexc('#2a2c2f'), rain * .40)
    alb = mix(alb, hexc('#0e0e0f'), burn * .85)
    alb = mix(alb, hexc('#9a9da2'), np.clip(scr * .5 + fix * .6, 0, 1) * .6)
    alb = mix(alb, hexc('#121315'), J * .92)
    rough = .58 + .08 * brush + .12 * bleach + .28 * burn + .2 * J - .1 * scr
    metal = np.clip((1 - J) * .45 * (1 - burn) + .4 * scr, 0, 1)
    T.write(alb, [(roll, .004), (-J, .012), (fix, .005), (brush, .00005), (big, .003), (blister, .0015), (-scr, .0001),
                  (-T.dents(24, (.015, .06)), .004)], rough, metal, relief=1.8, dust=(hexc('#47443f'), .4))


def ru_rubble():
    T = Tile("ru_rubble", 4.0)
    cd, cd2, cid = T.cells(.16, warp=.05)
    chunk = smooth(.05, .22, cd2 - cd) * (cid > .5)               # chunks of concrete: angular, broken, half of the places empty
    bd, bd2, bid = T.cells(.45, warp=.12)
    chunk = np.maximum(chunk, smooth(.05, .16, bd2 - bd) * (bid > .78))       # and a few slabs of it
    gd, _, gid = T.cells(.035, warp=.008)
    gravel = smooth(.52, .22, gd)
    crumb = smooth(.5, .2, T.cells(.010)[0])
    big = T.noise(1.5, 4)
    ash = above(T.noise(.8, 4), .30, .5) * (1 - chunk)
    alb = blank(T, '#5b564e') * (1 + .12 * big + .05 * T.grain(1))[..., None]
    alb = mix(alb, hexc('#8f8a80') * (1 + .4 * (gid - .5))[..., None], gravel * .55)
    alb = mix(alb, hexc('#7d786f') * (1 + .3 * (cid - .5))[..., None], chunk * .8)
    alb = mix(alb, hexc('#6d675d'), crumb * (1 - gravel) * .3)
    alb = mix(alb, hexc('#3b3936'), ash * .55)
    T.write(alb, [(chunk, .060), (chunk * T.noise(.05, 3), .012), (gravel, .014), (crumb, .004), (big, .030), (T.grain(1), .0006)],
            .93, 0.0, relief=1.2, dust=(hexc('#6a655c'), .5))


def ru_ceramic():
    T = Tile("ru_ceramic", 2.4)
    J, edge, ra, rb = T.grid(2, 4, joint=.006)
    broken = (ra < .09).astype(F32)                               # a panel's face gone: the backing shows
    craze = T.cracks(.035, share=.30, width=.0004) * (1 - broken)      # the glaze crazed
    crack = T.cracks(.9, share=.10, width=.0014) * (1 - broken)
    big = T.noise(1.2, 3)
    rain = T.streaks(80, (.2, 1.4), (.01, .08), (.25, 1.0))
    stain = above(T.noise(.6, 3), .16, .3)
    wave = T.noise(.25, 2)                                        # a glazed face is never quite flat
    back = T.noise(.02, 3)
    alb = blank(T, '#c6bfb1') * (1 + .10 * (rb - .5) + .04 * big)[..., None]
    alb = mix(alb, hexc('#8d8676'), craze * .5)
    alb = mix(alb, hexc('#3d4a44'), stain * .45)
    alb = mix(alb, hexc('#857c6c'), rain * .35)
    alb = mix(alb, hexc('#6e675c') * (1 + .25 * back)[..., None], broken)
    alb = mix(alb, hexc('#2a2824'), np.clip(crack + J * .9, 0, 1))
    rough = .22 + .3 * stain + .25 * rain + .6 * broken + .3 * J + .2 * craze
    T.write(alb, [(-J, .008), (wave, .0006), (-craze, .00012), (-crack, .0015), (-broken, .005), (broken * back, .002), (rb - .5, .002)],
            rough, 0.0, relief=1.8, dust=(hexc('#847c6e'), .35))


def ru_sandstone():
    T = Tile("ru_sandstone", 3.0)
    J, edge, ra, rb = T.grid(3, 5, stagger=.5, joint=.008, wander=.003)
    worn = smooth(.0, .030, edge)                                 # arrises worn round
    bed = T.brushed(.5)                                           # the stone's bedding, lying along the course
    tool = T.lines(2600, (.03, .12), (.0008, .0016), along=1.0, spread=.25)       # the mason's tooling
    grain = T.grain(1)
    pit = pits(T, .0030, 1.6)
    big = T.noise(1.0, 3)
    _, pv, _, H = panel_uv(T, 3, 5, .5)
    soot = smooth(.14, .0, pv) * (.5 + .5 * above(T.noise(.5, 3), .5, .6))       # under each course's joint
    spall = above(T.noise(.3, 4), .05, .1)
    alb = blank(T, '#a6987f') * (1 + .22 * (ra - .5) + .07 * bed + .06 * big + .04 * grain)[..., None]
    alb = alb * (1 + (rb - .5)[..., None] * np.array((.06, .0, -.08), F32))
    alb = mix(alb, hexc('#c9bda3'), spall * .5)
    alb = mix(alb, hexc('#3a352d'), soot * .55)
    alb = mix(alb, hexc('#5c5345'), pit * .6)
    alb = mix(alb, hexc('#4a4439'), J * .85)
    rough = .86 + .08 * J - .05 * worn
    T.write(alb, [(worn, .006), (-J, .012), (bed, .0005), (-tool, .0007), (grain, .0002), (-pit, .0025), (-spall, .006), (ra - .5, .006),
                  (big, .003)], rough, 0.0, relief=1.8, dust=(hexc('#8d826e'), .4))


def corrugate(name="ru_corrugate", lo='#42505b', hi='#63727c'):
    T = Tile(name, 2.0)
    Z = T.Z
    x = (np.arange(Z, dtype=F32)[None, :] + .5) / Z
    wave = (.5 + .5 * np.cos(x * 26 * 2 * math.pi)) * np.ones((Z, 1), F32)       # twenty-six ribs across the tile
    y = (np.arange(Z, dtype=F32)[:, None] + .5) / Z
    lap = (smooth(.012, .0, np.abs(y - .5)) + smooth(.012, .0, np.minimum(y, 1 - y))) * np.ones((1, Z), F32)     # where sheets overlap
    big = T.noise(.8, 3)
    fade = above(T.noise(.9, 3), .40, .6)
    rf = T.noise(.35, 4) + .4 * T.noise(.07, 3) + 1.2 * lap
    rust = above(rf, .14, .12)
    runs = T.streaks(70, (.2, 1.4), (.008, .05), (.3, 1.0))
    fd, _, fid = T.cells(.006, warp=.002)
    scale = smooth(.6, .25, fd) * rust
    scr = T.lines(500, (.03, .4), (.0003, .0010))
    dent = T.dents(16, (.03, .10))
    alb = mix(blank(T, lo), hexc(hi), np.clip(.5 + .5 * big + .25 * (wave - .5), 0, 1))
    alb = mix(alb, hexc('#8d9498'), fade * .22)
    alb = mix(alb, hexc('#9da1a6'), scr * .5 * (1 - rust))
    alb = mix(alb, hexc('#5b3319'), runs * .40)
    alb = mix(alb, hexc('#4a2816') * (1 + .5 * (fid - .5))[..., None], rust)
    alb = mix(alb, hexc('#864a20'), scale * smooth(.6, 1.0, fid) * .6)
    rough = .50 + .12 * fade + .40 * rust + .1 * runs - .12 * scr
    T.write(alb, [(wave, .018), (-dent, .012), (lap, .0015), (scale, .0010), (-scr, .00008), (big, .002), (T.grain(1), .00003)],
            rough, np.clip(.3 * (1 - rust) + .5 * scr, 0, 1), relief=1.4, dust=(hexc('#4d4a44'), .35))


def ru_tile():
    T = Tile("ru_tile", 2.4)
    J, edge, ra, rb = T.grid(4, 4, joint=.004)
    Z = T.Z
    v = np.floor((np.arange(Z, dtype=F32)[:, None] + .5) / Z * 4)
    u = np.floor((np.arange(Z, dtype=F32)[None, :] + .5) / Z * 4)
    two = ((u + v) % 2).astype(F32)
    broken = (ra < .08).astype(F32)
    crack = T.cracks(.5, share=.5, width=.0010) * broken
    scr = T.lines(900, (.03, .5), (.0002, .0007))
    dust = above(T.noise(.5, 4), .40, .6)
    wave = T.noise(.2, 2)
    speck = T.grain(1)
    alb = mix(blank(T, '#77746f'), hexc('#a5a29a'), two) * (1 + .08 * (rb - .5) + .025 * speck)[..., None]
    alb = mix(alb, hexc('#7d7568'), dust * .45)
    alb = mix(alb, hexc('#cfccc4'), scr * .25)
    alb = mix(alb, hexc('#23211e'), np.clip(crack + J * .9, 0, 1))
    rough = .16 + .5 * dust + .5 * J + .3 * crack + .12 * scr
    T.write(alb, [(-J, .004), (wave, .0004), (-crack, .0012), (-scr, .00005), (rb - .5, .0010), (dust * T.grain(1), .00015)], rough, 0.0,
            relief=2.0, dust=(hexc('#7d7568'), .3))


def ru_plaster():
    T = Tile("ru_plaster", 3.0)
    stip = T.noise(.006, 2)                                       # the roller's stipple
    big = T.noise(1.2, 3)
    pf = T.noise(.6, 4) + .35 * T.noise(.12, 3)
    peel = above(pf, .22, .02)                                    # the paint gone: the grey under it
    curl = above(pf, .27, .02) * (1 - peel)                       # its edge, curled up
    water = above(T.noise(.9, 3), .16, .4)
    tide = smooth(.25, .5, water) * smooth(.8, .55, water)
    crack = T.cracks(.8, share=.22, width=.0009)
    under = T.noise(.03, 3)
    alb = blank(T, '#8c978f') * (1 + .07 * big + .03 * stip)[..., None]
    alb = mix(alb, hexc('#6b665d') * (1 + .12 * under)[..., None], peel)
    alb = mix(alb, hexc('#a3ada5'), curl * .5)
    alb = mix(alb, hexc('#5a4f36'), water * .32)
    alb = mix(alb, hexc('#4a3f2a'), tide * .35)                   # the line a wetting leaves as it dries
    alb = mix(alb, hexc('#33312d'), crack * .85)
    rough = .80 + .10 * peel - .08 * water + .04 * stip
    T.write(alb, [(stip * (1 - peel), .00025), (big, .002), (-peel, .0006), (curl, .0012), (under * peel, .0006), (-crack, .0015)],
            rough, 0.0, relief=2.2, dust=(hexc('#77756c'), .3))


def ru_brass():
    T = Tile("ru_brass", 1.5)
    br, br2 = T.brushed(.5), T.brushed(.08)
    big = T.noise(.6, 3)
    gf = T.noise(.25, 4) + .4 * T.noise(.05, 3)
    green = above(gf, .16, .1)
    crust = smooth(.6, .25, T.cells(.004, warp=.001)[0]) * green
    dull = above(T.noise(.4, 3), .45, .6)
    smear = above(T.noise(.06, 3), .25, .4)
    scr = T.lines(800, (.02, .3), (.0002, .0007), along=.7)
    alb = blank(T, '#7c5d33') * (1 + .16 * br + .08 * br2 + .08 * big)[..., None]
    alb = mix(alb, hexc('#5d4627'), dull * .5)
    alb = mix(alb, hexc('#c9a25a'), scr * .6 * (1 - green))
    alb = mix(alb, hexc('#3f6f62') * (1 + .3 * T.noise(.02, 3))[..., None], green)
    alb = mix(alb, hexc('#7fb09c'), crust * .5)
    rough = .34 + .12 * br + .18 * dull + .12 * smear + .5 * green - .1 * scr
    T.write(alb, [(br, .00006), (br2, .00003), (-scr, .00006), (crust, .0006), (green, .0003), (big, .0010)], rough,
            np.clip(1 - green, 0, 1), relief=2.4, dust=(hexc('#55503f'), .3))


SETS = dict(ru_concrete=ru_concrete, ru_fracture=ru_fracture, ru_asphalt=ru_asphalt, ru_stone=ru_stone, ru_metal=ru_metal, ru_panel=ru_panel,
            ru_rubble=ru_rubble, ru_ceramic=ru_ceramic, ru_sandstone=ru_sandstone, ru_corrugate=corrugate,
            ru_box_red=lambda: corrugate("ru_box_red", '#4f1f17', '#7a3526'), ru_box_green=lambda: corrugate("ru_box_green", '#24392e', '#3d5a47'),
            ru_box_ochre=lambda: corrugate("ru_box_ochre", '#6b5524', '#94793a'), ru_tile=ru_tile, ru_plaster=ru_plaster, ru_brass=ru_brass)

if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    for n_ in (argv or SETS):
        SETS[n_]()
