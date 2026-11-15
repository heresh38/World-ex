"""What the materials lay over a tile so it holds up closer than its texels and does not read as a repeat (the
owner's texture rules, docs/art/TEXTURE_RULES.md: "ultra-sharp detail at close viewing distances", "no repeated
patterns"). Through the texture engine (pbr.py), 1024 px:

  det_<kind>   a DETAIL set, half a metre a tile (half a millimetre a texel): only what is too fine for the tile's
               own map. The material adds its normal to the tile's (DetailTex / DetailScale / DetailStrength) and
               darkens what it buries a little (DetailCavity).
                 stone     grain, pits, the hair cracks of a weathered face
                 concrete  sand, small aggregate, pores
                 metal     the finish's own grain, pin pits, hair scratches every way
                 asphalt   stones in tar
                 soil      grit, pebbles
                 plaster   stipple and the trowel
  macro        a field with no small shapes at all, laid at a scale that is NOT a whole number of tiles
               (MacroScale): R = tone, G = roughness. It is what stops a tile reading as a tile from across a square.

Run: blender --background --python tools/blender/detail_maps.py [-- name ...]
"""
import os
import sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pbr import F32, Tile, above, hexc, smooth                     # noqa: E402
from world_maps import pits                                          # noqa: E402

GREY = hexc('#808080')


def flat(T):
    return np.zeros((T.Z, T.Z, 3), F32) + GREY


def det_stone():
    T = Tile("det_stone", .5, size=1024)
    d1, d2, cid = T.cells(.004)
    T.write(flat(T), [(T.grain(1), .00012), (cid - .5, .00020), (T.noise(.03, 3), .0005), (-pits(T, .004, 1.2), .0012),
                      (-T.cracks(.06, share=.35, width=.0005), .0010)], .7, 0.0, relief=2.0, cavity=0)


def det_concrete():
    T = Tile("det_concrete", .5, size=1024)
    d, _, _ = T.cells(.006)
    T.write(flat(T), [(T.grain(1), .00016), (smooth(.5, .1, d), .00035), (T.noise(.04, 3), .0005), (-pits(T, .006, 1.4), .0016),
                      (-T.cracks(.10, share=.2, width=.0005), .0008)], .8, 0.0, relief=2.0, cavity=0)


def det_metal():
    T = Tile("det_metal", .5, size=1024)
    T.write(flat(T), [(T.grain(1), .00003), (T.noise(.02, 3), .00008), (-pits(T, .003, 1.0), .00035),
                      (-T.lines(1400, (.01, .12), (.0002, .0005)), .00007), (-T.lines(40, (.03, .2), (.0006, .0012)), .0003)],
            .4, 1.0, relief=2.0, cavity=0)


def det_asphalt():
    T = Tile("det_asphalt", .5, size=1024)
    d, d2, cid = T.cells(.009, warp=.002)
    stone = smooth(.62, .30, d)
    T.write(flat(T), [(stone, .0022), (cid * stone, .0008), (T.grain(1), .00025), (-pits(T, .006, 1.5), .002)], .85, 0.0,
            relief=1.6, cavity=0)


def det_soil():
    T = Tile("det_soil", .5, size=1024)
    d, _, cid = T.cells(.02, warp=.004)
    peb = smooth(.45, .15, d) * (cid > .6)
    T.write(flat(T), [(T.noise(.05, 4), .003), (T.grain(1), .0006), (peb, .004), (T.noise(.012, 2), .0012)], .95, 0.0,
            relief=1.5, cavity=0)


def det_plaster():
    T = Tile("det_plaster", .5, size=1024)
    T.write(flat(T), [(T.grain(1), .00012), (T.noise(.008, 2), .0003), (T.brushed(.12), .00025), (-pits(T, .002, 1.2), .0008),
                      (-T.cracks(.12, share=.15, width=.0004), .0006)], .85, 0.0, relief=2.0, cavity=0)


def macro():
    T = Tile("macro", 1.0, size=1024)
    a = T.noise(.5, 3) * .6 + T.noise(.2, 2) * .25
    b = T.noise(.45, 3) * .6 + T.noise(.16, 2) * .25
    a = np.clip(.5 + a * .9, 0, 1)
    b = np.clip(.5 + b * .9, 0, 1)
    T._save("m", np.dstack([a, b, np.zeros_like(a)]), False)
    print("[pbr] macro", flush=True)


SETS = dict(det_stone=det_stone, det_concrete=det_concrete, det_metal=det_metal, det_asphalt=det_asphalt, det_soil=det_soil,
            det_plaster=det_plaster, macro=macro)

if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    for n_ in (argv or SETS):
        SETS[n_]()
