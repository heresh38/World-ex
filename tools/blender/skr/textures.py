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
    """forged plate (the owner, 2026-11-15: the first set's growth lines read as wood grain): hammered in broad shallow
    blows, drawn out along the plate a little (a faint flow, not stripes), oxidised in patches (warmer and darker where
    it was heated, cooler and brighter where it was ground), pitted in clusters, scratched in patches"""
    T = Tile('skr_armour', .25)
    var = T.noise(.06, 3)
    patch = T.noise(.035, 4)
    hammer = T.dents(420, (.0035, .010))                                          # broad, shallow blows
    flow = T.blur_px(T.brushed(.030, axis=1), 1.5)                                # drawn along the plate
    fine = T.brushed(.006, axis=1)
    cluster = smooth(.15, .45, T.noise(.05, 3))
    pits = T.dents(260, (.0003, .0009)) * cluster
    scr_zone = smooth(.0, .35, T.noise(.07, 2))
    scr = T.lines(180, (.004, .035), (.0002, .0005), bend=.35, along=.6) * scr_zone
    heat = smooth(.25, .6, patch)                                                 # oxidised
    ground = smooth(.30, .65, -patch)                                             # ground back bright
    base = hexc('#59564f')
    alb = base * (.90 + .12 * var[..., None]) * (.97 + .03 * flow[..., None]) * (1 - .05 * hammer[..., None])
    alb = mix(alb, hexc('#4c463d'), heat * .45)
    alb = mix(alb, hexc('#6c6b68'), ground * .35)
    alb = mix(alb, hexc('#b2aea6'), scr * .40)
    alb = mix(alb, hexc('#38332c'), pits * .55)
    rough = .30 + .06 * var + .10 * heat - .06 * ground + .16 * pits - .08 * scr + .03 * fine
    metal = .66 + .14 * scr + .08 * ground - .10 * heat
    T.write(alb, [(-hammer, .00022), (flow, .00003), (fine, .000008), (-pits, .00020), (-scr, .00006), (var, .00030),
                  (T.grain(1), .000012)], rough, metal, relief=1.3, cavity=.35, legacy_normal_jpg=True, legacy_mask_jpg=True)


def dark():
    """the dark lacquered shell: grown in thin overlapping layers (broad, low cells whose rims catch the light), a
    violet depth on their crowns, satin where it has been handled and gloss elsewhere, scuffs in patches, dust in the
    layers' seams"""
    T = Tile('skr_dark', .25)
    var = T.noise(.05, 3)
    d1, d2, cid = T.cells(.014, warp=.004, warp_feature=.04)
    rim = 1 - smooth(0.0, .10, d2 - d1)                                           # a layer's edge
    dome = np.clip(1 - d1 * 1.1, 0, 1) ** .8
    fine = T.noise(.0016, 2)
    satin = smooth(.2, .55, T.noise(.06, 3))
    scr_zone = smooth(.05, .40, T.noise(.08, 2))
    scr = T.lines(150, (.004, .030), (.0002, .0005), bend=.4) * scr_zone
    pits = T.dents(140, (.0004, .0010)) * smooth(.1, .5, T.noise(.04, 3))
    alb = hexc('#181624') * (.86 + .14 * var[..., None]) * (.97 + .05 * cid[..., None])
    alb = mix(alb, hexc('#2a2540'), dome * .18)
    alb = mix(alb, hexc('#0b0a12'), rim * .22)
    alb = mix(alb, hexc('#3a3734'), rim * smooth(.3, .7, T.noise(.02, 2)) * .20)  # dust in the seams
    alb = mix(alb, hexc('#3e3b4e'), scr * .35)
    rough = .16 + .05 * var + .18 * satin + .14 * scr + .12 * pits + .10 * rim + .02 * fine
    T.write(alb, [(dome, .00020), (-rim, .00012), (var, .0002), (fine, .000015), (-scr, .0001), (-pits, .0003),
                  (T.grain(1), .00001)], rough, .15, relief=1.2, cavity=.30, legacy_normal_jpg=True, legacy_mask_jpg=True)


def gun_dark():
    """the guns' dark lacquer (the owner, 2026-11-15, on the assault rifle: "i like the orange more then this purple/blue
    ... the orange/gold on the scope"): the shell's layered growth as dark(), in a warm graphite with a bronze depth on
    the crowns instead of the armour's violet, so the gold and the amber light are what read on it"""
    T = Tile('skr_gun_dark', .25)
    var = T.noise(.05, 3)
    d1, d2, cid = T.cells(.014, warp=.004, warp_feature=.04)
    rim = 1 - smooth(0.0, .10, d2 - d1)
    dome = np.clip(1 - d1 * 1.1, 0, 1) ** .8
    fine = T.noise(.0016, 2)
    satin = smooth(.2, .55, T.noise(.06, 3))
    scr_zone = smooth(.05, .40, T.noise(.08, 2))
    scr = T.lines(150, (.004, .030), (.0002, .0005), bend=.4) * scr_zone
    pits = T.dents(140, (.0004, .0010)) * smooth(.1, .5, T.noise(.04, 3))
    alb = hexc('#1c1916') * (.86 + .14 * var[..., None]) * (.97 + .05 * cid[..., None])
    alb = mix(alb, hexc('#33281c'), dome * .22)
    alb = mix(alb, hexc('#0c0a08'), rim * .22)
    alb = mix(alb, hexc('#3a3530'), rim * smooth(.3, .7, T.noise(.02, 2)) * .20)
    alb = mix(alb, hexc('#4a4238'), scr * .35)
    rough = .16 + .05 * var + .18 * satin + .14 * scr + .12 * pits + .10 * rim + .02 * fine
    T.write(alb, [(dome, .00020), (-rim, .00012), (var, .0002), (fine, .000015), (-scr, .0001), (-pits, .0003),
                  (T.grain(1), .00001)], rough, .15, relief=1.2, cavity=.30, legacy_normal_jpg=True, legacy_mask_jpg=True)


if __name__ == '__main__':
    want = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else ['skin', 'armour', 'dark']
    for w in want:
        globals()[w]()
