"""The things in the world that explode (ASOExplosive: drums, gas bottles, a wreck's car body), their paint drawn
through the texture engine (pbr.py) to the owner's texture rules (docs/art/TEXTURE_RULES.md: 4K, every map, micro
detail, wear where wear goes, dirt where dirt collects, never plastic or clean).

  ex_paint   INDUSTRIAL ENAMEL on rolled steel, half a metre a tile, near white (the prop's own colour multiplies it):
             the enamel's orange peel, runs where it was sprayed thick, scratches through to the dark primer and the
             steel under it, dents, rust blooming in a few patches and running down from them, grime settled into
             every hollow and dust on what faces up
  ex_rust    the same steel where the paint is long gone (a drum's chimes, a wreck's sills and wheel arches): scale,
             pitting, streaks, a little old paint holding in the hollows

Run: blender --background --python tools/blender/explosive_maps.py [-- name name ...]     (PBR_SIZE=1024: a quick look)
"""
import os
import sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pbr import F32, Tile, above, hexc, mix, smooth                # noqa: E402
from world_maps import pits                                          # noqa: E402

TILE = .50
STEEL, PRIMER, RUST, RUST_DARK, GRIME = hexc('#8a8d93'), hexc('#3c3f43'), hexc('#7b4423'), hexc('#4a2a17'), hexc('#3a352e')


def blank(T, colour):
    return np.zeros((T.Z, T.Z, 3), F32) + hexc(colour)


def ex_paint():
    T = Tile("ex_paint", TILE)
    low = T.noise(.12, 3)
    peel = T.noise(.0016, 2)                                         # the enamel's orange peel
    roll = T.noise(.03, 3)                                           # the sheet's own waviness under it
    dents = T.dents(7, (.03, .07))                                   # (shallow and broad: small deep ones read as holes)
    # scratches: a few long hairlines through to the primer, fewer to the steel (handled, dragged, stacked)
    fine = T.lines(16, (.03, .16), (.00015, .0003), bend=.25, along=.3) * .7
    deep = T.lines(4, (.05, .2), (.0004, .0008), bend=.3, along=.3)
    # chips in a few places (where a drum is knocked: the asset's edges are its own business)
    where = above(T.noise(.09, 3), .32, .2)
    cf = T.noise(.004, 3) + .5 * T.noise(.0015, 2)
    chip = above(cf, .004, .03) * where
    primer = np.clip(chip + .6 * smooth(.25, .6, fine), 0, 1)
    bare = np.clip(above(cf, .0015, .03) * where + smooth(.4, .8, deep), 0, 1)
    # rust: blooms in a few patches, out of the chips, and runs down from them (V runs down the prop)
    bloom = above(T.noise(.06, 4), .22, .35) * np.clip(bare * 2.5 + .12 * pits(T, .0006, 1.4), 0, 1)
    runs = T.streaks(34, (.05, .30), (.0012, .004), (.3, .9))
    rust = np.clip(bloom + runs * above(T.noise(.08, 3), .45, .3) * .8, 0, 1)
    # paint runs where it was sprayed on thick: a few soft ridges hanging down
    drip = T.streaks(14, (.02, .08), (.002, .005), (.5, 1.0)) * above(T.noise(.1, 2), .5, .2)
    stain = above(T.noise(.05, 4), .35, .5) * .45
    alb = blank(T, '#e6e3dc') * (1 + .03 * low - .02 * peel)[..., None]
    alb = mix(alb, hexc('#b9b2a2'), stain)
    alb = mix(alb, PRIMER, primer)
    alb = mix(alb, STEEL, bare * (1 - .6 * rust))
    alb = mix(alb, RUST, rust * .85)
    alb = mix(alb, RUST_DARK, rust * smooth(.5, 1.0, bloom) * .6)
    rough = .38 + .05 * peel + .12 * stain + .20 * primer - .06 * bare + .32 * rust + .06 * (1 - low)
    metal = bare * (1 - rust)
    T.write(alb, [(roll, .0006), (-dents, .0010), (peel, .000025), (drip, .00020), (-fine, .00002), (-deep, .00006),
                  (-chip, .00006), (rust, .00005)],
            rough, metal, relief=3.0, cavity=.16, dust=(GRIME, .35))


def ex_rust():
    T = Tile("ex_rust", TILE)
    low = T.noise(.1, 3)
    scale = 1 - np.clip(T.cells(.006, warp=.4)[0] / .7, 0, 1) ** 1.6  # rust scale lifting in flakes
    pit = pits(T, .006, 1.2)
    runs = T.streaks(40, (.06, .35), (.001, .004), (.3, 1.0))
    paint = above(T.noise(.03, 3), .78, .1) * (1 - smooth(.3, .9, scale))   # old paint holding in a few hollows
    alb = blank(T, '#6e3b1f') * (1 + .18 * low)[..., None]
    alb = mix(alb, RUST_DARK, np.clip(.6 * pit + .4 * (1 - scale), 0, 1))
    alb = mix(alb, hexc('#9a5a2c'), runs * .6)
    alb = mix(alb, hexc('#bdb6a8'), paint * .7)
    rough = .74 + .1 * low + .1 * pit - .2 * paint
    T.write(alb, [(scale, .0004), (-pit, .0005), (low, .0006), (runs, .00005)], rough, .08, relief=3.0, cavity=.35, dust=(GRIME, .4))


SETS = {"ex_paint": ex_paint, "ex_rust": ex_rust}

if __name__ == "__main__":
    want = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    for name, fn in SETS.items():
        if not want or name in want:
            fn()
