"""The Sarketh's surfaces, drawn through the texture engine (pbr.py, the owner's texture rules):

  skr_skin    the dark under-layer: big scutes (2 cm) of a navy-violet near black, each domed and parted from the next
              by a dark crease, with fine scales (6 mm) inside them, a faint violet sheen on the crowns
  skr_chitin  the pale plates: a satin, taupe-grey shell with growth lines running ALONG each plate (its UVs run along
              it), pits, fine scratches, lighter where scratched; partly metallic (the sheet's plates shine like worn
              metal at their edges)
  skr_dark    the dark lacquered chitin of the face's mask: glossy, near black, a few scratches

blender -b -P tools/blender/skr/textures.py [-- skin chitin dark]    (PBR_SIZE=2048 for a quick set)
"""
import os
import sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import pbr  # noqa: E402
from pbr import Tile, hexc, mix, smooth  # noqa: E402


def skin():
    T = Tile('skr_skin', .24)
    d1, d2, rid = T.cells(.013, warp=.003, warp_feature=.04)
    crease = 1 - smooth(0.0, .16, d2 - d1)
    dome = np.clip(1 - d1 * .95, 0, 1) ** .6
    s1, s2, sid = T.cells(.0042, warp=.0009)
    crease_s = 1 - smooth(0.0, .22, s2 - s1)
    tone = .88 + .20 * rid[..., None] + .08 * sid[..., None]
    base = hexc('#121019')
    alb = base * tone
    alb = mix(alb, hexc('#221f36'), (dome * .40 * (.5 + .5 * T.noise(.05))).clip(0, 1))      # the crowns' sheen
    alb = mix(alb, hexc('#0a0910'), (crease * .85))
    alb = mix(alb, hexc('#0e0c15'), (crease_s * .35))
    rough = .62 - .08 * dome + .10 * crease + .04 * T.noise(.01)
    T.write(alb, [(dome, .0011), (-crease, .0009), (-crease_s, .00028), (T.noise(.004, 3), .00012), (T.grain(1), .00002)],
            rough, 0.0, relief=1.4, cavity=.35, legacy_normal_jpg=True, legacy_mask_jpg=True)


def armour():
    T = Tile('skr_armour', .25)
    Z = T.Z
    y = (np.arange(Z, dtype=np.float32)[:, None] + .5) * T.texel * np.ones((1, Z), np.float32)
    warp = T.noise(.04, 3) * .006
    bands = .5 + .5 * np.sin(2 * np.pi * (y + warp) / .0042)                    # growth lines along the plate
    bands2 = .5 + .5 * np.sin(2 * np.pi * (y + warp * 2.0) / .019)
    pits = T.dents(90, (.0005, .0012))
    scr = T.lines(140, (.006, .040), (.00025, .0006), bend=.3, along=.5)
    var = T.noise(.06, 3)
    base = hexc('#55534f')
    alb = base * (.92 + .10 * var[..., None]) * (.985 + .015 * bands2[..., None])
    alb = mix(alb, hexc('#4b4946'), (bands * .10))
    alb = mix(alb, hexc('#a29e98'), (scr * .28))
    alb = mix(alb, hexc('#4a443c'), (pits * .22))
    rough = .30 + .07 * var + .12 * pits - .06 * scr + .05 * bands
    metal = .62 + .15 * scr
    T.write(alb, [(bands, .00004), (bands2, .00012), (-pits, .00018), (-scr, .00006), (var, .00030), (T.grain(1), .000015)],
            rough, metal, relief=1.3, cavity=.30, legacy_normal_jpg=True, legacy_mask_jpg=True)


def dark():
    T = Tile('skr_dark', .25)
    var = T.noise(.05, 3)
    scr = T.lines(70, (.005, .030), (.00025, .0005), bend=.4)
    pits = T.dents(90, (.0005, .0012))
    alb = hexc('#191826') * (.9 + .12 * var[..., None])
    alb = mix(alb, hexc('#4a4760'), (scr * .5))
    rough = .22 + .05 * var + .14 * scr + .1 * pits
    T.write(alb, [(var, .0002), (-scr, .0001), (-pits, .0003), (T.grain(1), .00001)], rough, .15, relief=1.2, cavity=.25,
            legacy_normal_jpg=True, legacy_mask_jpg=True)


if __name__ == '__main__':
    want = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else ['skin', 'armour', 'dark']
    for w in want:
        globals()[w]()
