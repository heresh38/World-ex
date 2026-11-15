"""Nexus Prime's ground, drawn anew through the texture engine (pbr.py) at 4096 px to the owner's texture rules
(docs/art/TEXTURE_RULES.md): the streets, pavements, plaza, kerbs, yards, lawns, roofs, bare ground and the city
wall. Same names, tile sizes, layouts and colours as nexus_city_textures.py made them with (M_SOGround lays them in
world metres by those: a paver is still 50 cm, a plaza slab 2 x 1 m with its line of light), so nothing is built
again. Run AFTER that script (it still makes the facades and the props' sets, which are not redrawn).

This is a city people live in, not a ruin: worn, stained and patched, not broken.

  nc_asphalt  the road: stones in tar, polished paler where wheels run, oil, a sealed joint down the middle, a few
              cracks, a darker patch of repair
  nc_pavers   pavement, 50 cm concrete pavers: each its own tone and lift, chipped corners, gum, sand in the joints
  nc_plaza    slate slabs 2 x 1 m, running bond, a thin inlay of light metal: grained, worn paths, stains
  nc_kerb     kerbs and viaducts: fine cast concrete, bug holes, hair cracks, the black a tyre leaves
  nc_lot      yards: poured bays 3 m square, a broom finish, joints, tyre marks, oil
  nc_grass    lawn seen from above: blades in tufts, dry patches, soil between
  nc_roof     flat roofs: lapped membrane sheets under gravel, where water stood, two drains
  nc_dirt     bare ground: grit, stones, weeds coming up
  nc_wall     the city wall: big dark cast panels with tie holes, rain runs

Colours: nexus_city_textures.py saved its hex colours as LINEAR values (the files are darker than the hex reads);
`lin()` keeps that, so the city is as bright as it was.

Run: blender --background --python tools/blender/city_maps.py [-- name ...]     (PBR_SIZE=1024 for a quick look)
"""
import math
import os
import sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bl                                                           # noqa: E402
from pbr import F32, Tile, above, mix, smooth                      # noqa: E402
from world_maps import panel_uv, pits                               # noqa: E402


def lin(h):
    return np.array(bl.hexrgb(h), F32)


def blank(T, colour):
    return np.zeros((T.Z, T.Z, 3), F32) + lin(colour)


def nc_asphalt():
    T = Tile("nc_asphalt", 8.0)
    Z = T.Z
    ad, _, aid = T.cells(.009, warp=.002)
    stone = smooth(.60, .28, ad)
    big = T.noise(2.5, 3)
    wheel = above(T.noise(2.2, 2), .45, .6)                       # where wheels run: polished, paler
    oil = above(T.noise(.6, 4), .05, .2)
    x = (np.arange(Z, dtype=F32)[None, :] + .5) / Z * 2 - 1
    seam = smooth(.012, .004, np.abs(x + T.noise(2.0, 3) * .02)) * np.ones((Z, 1), F32)      # the sealed joint down the middle
    crack = T.cracks(1.8, share=.14, width=.0025)
    patch = above(T.noise(2.6, 2), .07, .02)
    alb = blank(T, '#44474b') * (1 + .14 * big + .10 * (aid - .5) * stone)[..., None]
    alb = mix(alb, lin('#6a6d72'), stone * smooth(.55, 1.0, aid) * (.35 + .4 * wheel))
    alb = mix(alb, lin('#2a2c2f'), (1 - stone) * .45)
    alb = mix(alb, lin('#2e3033'), patch * .5)
    alb = mix(alb, lin('#17181a'), np.clip(seam + crack, 0, 1) * .9)
    alb = mix(alb, lin('#1b1c1e'), oil * .6)
    rough = .82 - .10 * stone - .12 * wheel - .30 * oil - .12 * seam - .06 * patch
    T.write(alb, [(stone * (1 - .5 * wheel) * (1 - .6 * patch), .0028), (big, .008), (-crack, .006), (seam, .0015), (T.grain(1), .0003)],
            rough, 0.0, relief=1.5, dust=(lin('#5d5a54'), .3))


def nc_pavers():
    T = Tile("nc_pavers", 4.0)
    J, edge, ra, rb = T.grid(8, 8, joint=.007, wander=.002)
    agg = smooth(.55, .2, T.cells(.006)[0])
    big = T.noise(1.2, 3)
    chip = smooth(.030, .004, edge) * above(T.noise(.06, 3), .30, .25)
    crack = T.cracks(.7, share=.10, width=.0014)
    gum = np.clip(T.dents(70, (.008, .016)) * 3 - 1.6, 0, 1)       # gum trodden flat
    stain = above(T.noise(.5, 4), .10, .25)
    by_joint = smooth(.05, .0, edge)
    alb = blank(T, '#7c7e81') * (1 + .16 * (ra - .5) + .07 * big + .04 * T.grain(1))[..., None]
    alb = mix(alb, lin('#9c9ea0'), agg * .25)
    alb = mix(alb, lin('#a7a8a8'), chip * .5)
    alb = mix(alb, lin('#1e1f20'), np.clip(gum * .9 + crack * .85, 0, 1))
    alb = mix(alb, lin('#47484a'), np.clip(stain * .5 + by_joint * .4, 0, 1))
    alb = mix(alb, lin('#4a443a'), J * .9)                         # sand in the joints
    rough = .72 + .18 * J + .08 * by_joint - .25 * gum + .06 * stain
    T.write(alb, [(-J, .006), (rb - .5, .004), (agg, .0003), (-chip, .004), (-crack, .002), (gum, .0008), (T.grain(1), .00015),
                  (T.noise(.5, 3), .0015)], rough, 0.0, relief=1.8, dust=(lin('#6c6a65'), .4))


def nc_plaza():
    T = Tile("nc_plaza", 8.0)
    Z = T.Z
    J, edge, ra, rb = T.grid(4, 8, stagger=.5, joint=.006, wander=.002)
    _, _, cid = T.cells(.0045)
    big = T.noise(2.5, 3)
    path = above(T.noise(1.6, 3), .42, .35)
    crack = T.cracks(2.0, share=.08, width=.0016)
    stain = above(T.noise(.5, 4), .06, .2)
    by_joint = smooth(.06, .0, edge)
    y = (np.arange(Z, dtype=F32)[:, None] + .5) / Z * T.m
    inlay = smooth(.016, .013, np.abs(y - T.m / 2)) * np.ones((1, Z), F32)       # the line of light metal: 3 cm wide
    scr = T.lines(700, (.05, .7), (.0004, .0010))
    alb = blank(T, '#4a4e58') * (1 + .20 * (ra - .5) + .07 * big)[..., None]
    alb = mix(alb, lin('#6f7582'), smooth(.78, .95, cid) * .6)
    alb = mix(alb, lin('#2a2d33'), smooth(.22, .05, cid) * .6)
    alb = mix(alb, lin('#585d68'), path * .30)
    alb = mix(alb, lin('#1f2125'), np.clip(stain * .6 + by_joint * .4 + J * .9, 0, 1) * (1 - inlay))
    alb = mix(alb, lin('#131417'), crack * .85 * (1 - inlay))
    alb = mix(alb, lin('#7fb8c8') * (1 + .15 * T.brushed(.4))[..., None], inlay)
    rough = (.52 - .22 * path + .22 * J + .14 * by_joint + .10 * scr + .12 * stain) * (1 - inlay) + inlay * (.34 + .1 * scr)
    T.write(alb, [(-J * (1 - inlay), .007), (ra - .5, .003), (cid - .5, .00022), (-crack, .003), (-scr, .0002), (inlay, .0006),
                  (T.noise(.8, 3), .0015)], rough, inlay * .7, relief=2.0, dust=(lin('#5f5c55'), .35))


def nc_kerb():
    T = Tile("nc_kerb", 2.0)
    sand = T.grain(1)
    agg = smooth(.55, .15, T.cells(.010)[0])
    big, mott = T.noise(.9, 4), T.noise(.2, 4)
    bug = (pits(T, .0010, 2.0) + pits(T, .0003, 4.0)) * (.15 + .85 * above(T.noise(.5, 3), .4, .5))
    hair = T.cracks(.6, share=.15, width=.0007)
    tyre = T.streaks(26, (.2, .9), (.02, .06), (.3, 1.0))         # the black a tyre leaves
    wear = above(T.noise(.4, 4), .30, .3)
    alb = blank(T, '#858583') * (1 + .08 * big + .06 * mott + .035 * sand)[..., None]
    alb = mix(alb, lin('#a2a29f'), agg * wear * .4)
    alb = mix(alb, lin('#4c4c4a'), np.clip(bug, 0, 1) * .8)
    alb = mix(alb, lin('#2e2e2d'), hair * .85)
    alb = mix(alb, lin('#1d1d1e'), tyre * .55)
    rough = .82 - .08 * wear + .05 * sand - .12 * tyre
    T.write(alb, [(sand, .00016), (agg * wear, .0004), (mott, .0010), (big, .002), (-np.clip(bug, 0, 1), .003), (-hair, .0015)], rough, 0.0,
            dust=(lin('#74726c'), .35))


def nc_lot():
    T = Tile("nc_lot", 9.0)
    J, edge, ra, rb = T.grid(3, 3, joint=.012, wander=.004)
    broom = T.brushed(.6)                                          # a broom finish, drawn across each bay
    sand = T.grain(1)
    big = T.noise(2.5, 4)
    crack = T.cracks(2.2, share=.16, width=.0025)
    oil = above(T.noise(.7, 4), .06, .2)
    tyre = above(T.noise(3.0, 2), .30, .5) * (.5 + .5 * np.clip(T.brushed(1.5) * 2 + .5, 0, 1))
    alb = blank(T, '#6a6c6e') * (1 + .12 * (ra - .5) + .08 * big + .05 * broom + .03 * sand)[..., None]
    alb = mix(alb, lin('#2e2f31'), tyre * .35)
    alb = mix(alb, lin('#1c1d1e'), np.clip(oil * .6 + crack * .9 + J * .85, 0, 1))
    rough = .80 + .05 * broom - .28 * oil - .08 * tyre + .1 * J
    T.write(alb, [(-J, .010), (broom, .0006), (sand, .0002), (big, .006), (-crack, .005), (rb - .5, .003)], rough, 0.0,
            relief=1.6, dust=(lin('#66635d'), .4))


def nc_grass():
    T = Tile("nc_grass", 4.0)
    td, _, tid = T.cells(.07, warp=.02)                           # tufts
    tuft = smooth(.75, .15, td)
    blades = T.lines(26000, (.02, .06), (.0012, .0026), bend=.5)
    fine = T.lines(26000, (.012, .035), (.0008, .0016), bend=.5)
    big = T.noise(1.5, 3)
    dry = above(T.noise(1.0, 3), .22, .4)
    soil = (1 - np.clip(blades + fine, 0, 1)) * (1 - tuft * .7)
    grit = T.grain(1)
    alb = mix(blank(T, '#2a4a1e'), lin('#47702d'), np.clip(.35 + .5 * blades + .3 * fine + .25 * (tid - .5), 0, 1))
    alb = alb * (1 + .12 * big)[..., None]
    alb = mix(alb, lin('#7c7440'), dry * (.3 + .4 * blades))
    alb = mix(alb, lin('#3a3024') * (1 + .2 * grit)[..., None], np.clip(soil, 0, 1) * .75)
    rough = .86 + .08 * soil - .12 * blades
    T.write(alb, [(blades, .012), (fine, .006), (tuft, .015), (big, .02), (grit * soil, .002)], rough, 0.0, relief=1.2, cavity=.45)


def nc_roof():
    T = Tile("nc_roof", 8.0)
    Z = T.Z
    J, edge, ra, rb = T.grid(4, 2, joint=.020)                    # membrane sheets, lapped
    lap = smooth(.10, .02, edge) * (1 - J)
    gd, _, gid = T.cells(.014, warp=.003)
    gravel = smooth(.55, .22, gd)
    big = T.noise(2.5, 3)
    pond = above(T.noise(2.2, 2), .22, .3)                        # where water stood
    rim = smooth(.3, .5, pond) * smooth(.9, .6, pond)
    yy, xx = np.mgrid[0:Z, 0:Z].astype(F32) / Z * T.m
    drain = np.zeros((Z, Z), F32)
    for cx, cy in ((2.0, 2.0), (6.0, 6.0)):
        drain = np.maximum(drain, np.clip(1 - np.hypot(xx - cx, yy - cy) / .11, 0, 1))
    grate = drain * (.5 + .5 * np.sin(xx / .012 * 2 * math.pi))
    alb = blank(T, '#5f6266') * (1 + .10 * (ra - .5) + .07 * big)[..., None]
    alb = mix(alb, lin('#8a8c8e') * (1 + .5 * (gid - .5))[..., None], gravel * .6)
    alb = mix(alb, lin('#3b3d40'), np.clip(pond * .35 + J * .6, 0, 1))
    alb = mix(alb, lin('#7d7868'), rim * .4)                       # the line the water left
    alb = mix(alb, lin('#151617'), drain * .85)
    rough = .86 - .14 * pond + .06 * gravel - .1 * drain
    T.write(alb, [(gravel, .009), (lap, .004), (-J, .003), (big, .010), (-pond, .006), (-drain, .030), (grate, .008)], rough,
            drain * .6, relief=1.4, dust=(lin('#6b6862'), .4))


def nc_dirt():
    T = Tile("nc_dirt", 6.0)
    sd, _, sid = T.cells(.05, warp=.012)
    stone = smooth(.42, .16, sd) * (sid > .55)
    pd, _, _ = T.cells(.012, warp=.003)
    peb = smooth(.5, .2, pd)
    grit = T.grain(1)
    big, mid = T.noise(2.0, 4), T.noise(.25, 4)
    wf = T.noise(.9, 3)
    weeds = above(wf, .20, .3)
    blades = T.lines(9000, (.02, .07), (.0012, .0028), bend=.5) * weeds
    alb = blank(T, '#5c5144') * (1 + .14 * big + .08 * mid + .05 * grit)[..., None]
    alb = mix(alb, lin('#8a8478') * (1 + .4 * (sid - .5))[..., None], stone * .7)
    alb = mix(alb, lin('#6e6253'), peb * (1 - stone) * .3)
    alb = mix(alb, lin('#3d4a26'), np.clip(blades * .9 + weeds * .15, 0, 1))
    rough = .92 - .06 * stone - .10 * blades
    T.write(alb, [(stone, .018), (peb, .004), (mid, .010), (big, .03), (grit, .0006), (blades, .010)], rough, 0.0, relief=1.3,
            dust=(lin('#6a6052'), .35))


def nc_wall():
    T = Tile("nc_wall", 12.0)
    J, edge, ra, rb = T.grid(2, 3, joint=.025)
    pu, pv, W, H = panel_uv(T, 2, 3, 0.0)
    tie = np.zeros((T.Z, T.Z), F32)                                # tie holes at the quarter points of every panel
    for hx in (.25, .75):
        for hy in (.25, .75):
            tie = np.maximum(tie, np.clip(1 - np.hypot(pu - hx * W, pv - hy * H) / .05, 0, 1) ** .5)
    sand = T.grain(1)
    big, mott = T.noise(3.0, 4), T.noise(.5, 4)
    bug = (pits(T, .0008, 2.0) + pits(T, .0002, 4.0)) * (.15 + .85 * above(T.noise(1.2, 3), .4, .5))
    hair = T.cracks(2.2, share=.14, width=.0020)
    rain = T.streaks(90, (1.0, 5.0), (.03, .22), (.25, 1.0))
    alb = blank(T, '#4d525a') * (1 + .16 * (ra - .5) + .08 * big + .06 * mott + .03 * sand)[..., None]
    alb = mix(alb, lin('#2a2c30'), np.clip(bug + tie * .8, 0, 1) * .8)
    alb = mix(alb, lin('#1c1d20'), np.clip(hair + J * .9, 0, 1))
    alb = mix(alb, lin('#30333a'), rain * .40)
    alb = mix(alb, lin('#6f747c'), smooth(.4, .9, rain) * rb * .12)      # here and there what the rain left is pale
    rough = .76 + .05 * sand + .06 * rain + .12 * J
    T.write(alb, [(-J, .020), (-tie, .030), (sand, .0003), (mott, .003), (big, .008), (-np.clip(bug, 0, 1), .006), (-hair, .004),
                  (ra - .5, .008)], rough, 0.0, relief=1.6, dust=(lin('#55565a'), .3))


SETS = dict(nc_asphalt=nc_asphalt, nc_pavers=nc_pavers, nc_plaza=nc_plaza, nc_kerb=nc_kerb, nc_lot=nc_lot, nc_grass=nc_grass, nc_roof=nc_roof,
            nc_dirt=nc_dirt, nc_wall=nc_wall)

if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    for n_ in (argv or SETS):
        SETS[n_]()
