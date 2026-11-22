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
    # (a pale warm grey, the sheet's plates: at #59564f, a tenth of the light reflected, the plates read black in the
    # game's daylight; a steel's own reflectance is far higher)
    base = hexc('#a39e94')
    alb = base * (.90 + .12 * var[..., None]) * (.97 + .03 * flow[..., None]) * (1 - .05 * hammer[..., None])
    alb = mix(alb, hexc('#8a8072'), heat * .45)
    alb = mix(alb, hexc('#bab8b2'), ground * .35)
    alb = mix(alb, hexc('#d8d4cc'), scr * .40)
    alb = mix(alb, hexc('#5c564c'), pits * .55)
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



# ---------------------------------------------------------------------------- the Sarketh guns' own materials
# (the owner, 2026-11-15, on the Veyr guns: "the textures you applied to the gun are too flat, make better steel/
# polimer/ exotic textures"). Each a set of its own (the human guns keep the wpn_* sets), with real relief at two or
# three scales, colour and roughness that vary, and something of their making in each: the pale alloy shows its
# crystal grains, the titanium the colours heat leaves, the polymer their moulded hex.
def _xy(T):
    a = (np.arange(T.Z, dtype=np.float32) + .5) * T.texel
    return a[None, :] * np.ones((T.Z, 1), np.float32), a[:, None] * np.ones((1, T.Z), np.float32)


def alloy():
    """skr_alloy, the pale armour: a crystalline alloy whose grains (a few millimetres) each take the light their own
    way (a brushed direction, a tone, a roughness of their own), hammered in broad blows, scratched where it was
    handled, pitted in clusters"""
    T = Tile('skr_alloy', .25)
    d1, d2, gid = T.cells(.0055, warp=.0012, warp_feature=.02)
    edge = 1 - smooth(0.0, .05, d2 - d1)                                           # the grain boundaries
    bx, by = T.brushed(.012, axis=1), T.brushed(.012, axis=0)
    dirn = gid > .5
    brush = np.where(dirn, bx, by)                                                 # each grain brushed its own way
    hammer = T.dents(380, (.004, .011))
    var = T.noise(.05, 3)
    scr = T.lines(220, (.004, .035), (.00018, .00045), bend=.35, along=.55) * smooth(-.1, .4, T.noise(.07, 2))
    pits = T.dents(320, (.0003, .0008)) * smooth(.15, .5, T.noise(.04, 3))
    heat = smooth(.3, .7, T.noise(.04, 4))
    base = hexc('#67645d')
    alb = base * (.86 + .10 * var[..., None] + .10 * (gid[..., None] - .5)) * (.97 + .03 * brush[..., None])
    alb = mix(alb, hexc('#4d463b'), heat * .30)
    alb = mix(alb, hexc('#4a4741'), edge * .12)
    alb = mix(alb, hexc('#c2beb5'), scr * .45)
    alb = mix(alb, hexc('#2f2a24'), pits * .6)
    rough = .22 + .12 * gid + .05 * var + .10 * heat + .03 * edge + .18 * pits - .08 * scr + .02 * brush
    metal = .72 + .16 * gid - .10 * heat + .1 * scr
    T.write(alb, [(-hammer, .00022), ((gid - .5), .000012), (-edge, .000008), (brush, .000006), (-scr, .00006), (-pits, .00022),
                  (var, .00025), (T.grain(1), .00001)], rough, metal, legacy_normal_jpg=True, legacy_mask_jpg=True, relief=1.4, cavity=.4)


def lacquer():
    """skr_lacquer, the shell (the owner, 2026-11-15: "the guns are brown, they should be orange"): an orange lacquer (yellow enough that the game's tone mapping leaves it orange, not red): grown in thin overlapping layers whose edges stand up and catch the light, a bronze
    depth in their crowns, fine pores, satin where hands have been and gloss elsewhere, scuffed through to a paler
    layer in patches"""
    T = Tile('skr_lacquer', .25)
    var = T.noise(.05, 3)
    d1, d2, cid = T.cells(.012, warp=.004, warp_feature=.04)
    rim = 1 - smooth(0.0, .09, d2 - d1)
    dome = np.clip(1 - d1 * 1.05, 0, 1) ** .7
    lap = smooth(.0, .35, d1) * (1 - rim)                                          # each layer laps under the next
    pores = T.dents(2600, (.00012, .00030))
    satin = smooth(.2, .55, T.noise(.06, 3))
    scuff = T.lines(160, (.004, .028), (.0003, .0008), bend=.4) * smooth(.1, .45, T.noise(.08, 2))
    alb = hexc('#e27c1c') * (.86 + .14 * var[..., None]) * (.95 + .10 * cid[..., None])
    alb = mix(alb, hexc('#f7a848'), dome * .34)                                    # brighter on the crowns
    alb = mix(alb, hexc('#8a3c0a'), rim * .26)
    alb = mix(alb, hexc('#e8b27a'), scuff * .45)
    alb = mix(alb, hexc('#3a1404'), pores * .4)
    rough = .14 + .05 * var + .20 * satin + .16 * scuff + .10 * rim + .18 * pores
    T.write(alb, [(dome, .00045), (lap, .00012), (-rim, .00020), (-pores, .00004), (-scuff, .00006), (var, .00025), (T.grain(1), .00001)],
            rough, .18, legacy_normal_jpg=True, legacy_mask_jpg=True, relief=1.4, cavity=.35)


def steel():
    """skr_steel, bolts, pins and vanes: machined steel, brushed along, fine tool marks across, oil darkening in patches,
    bright where it was wiped"""
    T = Tile('skr_steel', .25)
    x, y = _xy(T)
    brush = T.brushed(.02, axis=1)
    tool = .5 + .5 * np.sin(2 * np.pi * (y + T.noise(.03, 2) * .0006) / .00045)     # the cutter's passes, 0.45 mm
    oil = smooth(.2, .65, T.noise(.035, 4))
    wipe = smooth(.35, .75, T.noise(.05, 3))
    scr = T.lines(260, (.003, .025), (.00012, .0003), bend=.25, along=.7)
    alb = hexc('#8b8d8f') * (.92 + .05 * brush[..., None] + .03 * tool[..., None])
    alb = mix(alb, hexc('#4c4b48'), oil * .45)
    alb = mix(alb, hexc('#b4b6b8'), wipe * .2 + scr * .5)
    rough = .26 + .10 * oil - .08 * wipe + .04 * brush - .06 * scr
    T.write(alb, [(brush, .000012), (tool, .000006), (-scr, .00004), (T.noise(.05, 3), .00008), (T.grain(1), .000006)], rough, .95, legacy_normal_jpg=True, legacy_mask_jpg=True, relief=1.3,
            cavity=.3)


def mirror():
    """skr_mirror, a blade's steel (the owner, 2026-11-15: "a combination of stainless steel, extremely shiny"): stainless
    polished to a mirror, the faintest swirl of the last polish, a few hairline scratches, a breath of colour from the
    alloy; almost no roughness anywhere"""
    T = Tile('skr_mirror', .25)
    swirl = T.noise(.004, 3)
    hair = T.lines(90, (.004, .03), (.00008, .00018), bend=.3, along=.5)
    var = T.noise(.07, 3)
    alb = hexc('#d4d7dc') * (.97 + .03 * var[..., None])
    alb = mix(alb, hexc('#e6e8eb'), hair * .35)
    def norm(a):
        return (a - a.min()) / (np.ptp(a) + 1e-6)
    smudge = smooth(.45, .85, norm(T.noise(.03, 3)))                              # wiped, handled: a faint haze in patches
    rough = .04 + .035 * norm(swirl) + .08 * hair + .08 * smudge + .01 * norm(var)
    T.write(alb, [(swirl, .000002), (-hair, .000012), (T.grain(1), .000001)], rough, 1.0, legacy_normal_jpg=True, legacy_mask_jpg=True, relief=1.0,
            cavity=.1)


def carbon():
    """skr_carbon, Ember Oath II's shell (the owner, 2026-11-15, on the lacquer: "looks more like a tile floor so make it
    more like a sleek carbon fibre"): a 2/2 twill of 3 mm tows dyed the set's orange, each tow rounded across its width
    and drawn in its fibres along it, the tows running one way catching the light more than the others, all under a
    deep glossy clear coat (a faint haze where it was handled, a few hairlines in the coat)"""
    T = Tile('skr_carbon', .25)
    x, y = _xy(T)
    w = .003
    i = np.floor(x / w); j = np.floor(y / w)
    over = ((i - j) % 4) < 2                                                       # the twill: over two, under two, stepping
    across = np.where(over, y / w - j, x / w - i)                                  # across the tow
    prof = np.sin(np.pi * np.clip(across, 0, 1)).astype(np.float32)
    along = np.where(over, x, y)
    fib = .5 + .5 * np.sin(2 * np.pi * (np.where(over, y, x) / .00011) + T.noise(.002, 2) * 4)   # the fibres in a tow

    def norm(a):
        return (a - a.min()) / (np.ptp(a) + 1e-6)
    var = norm(T.noise(.05, 3))
    haze = smooth(.5, .85, norm(T.noise(.03, 3)))
    hair = T.lines(60, (.004, .03), (.00008, .00018), bend=.3, along=.5)
    shade = np.where(over, 1.0, .84).astype(np.float32)                           # (a shimmer of the weave, not a basket)
    k = shade * (.88 + .12 * prof) * (.95 + .05 * fib) * (.95 + .05 * var)
    alb = hexc('#d06a1a') * k[..., None]
    alb = mix(alb, hexc('#5a2a08'), (1 - prof) ** 10 * .30)                       # a fine dark line between the tows
    rough = .07 + .03 * (1 - prof) + .06 * haze + .07 * hair + .02 * var
    T.write(alb, [(prof, .00002), (fib, .0000015), (-hair, .000004)], rough, 0.0, legacy_normal_jpg=True, legacy_mask_jpg=True, relief=1.0,
            cavity=.15)


def iron():
    """skr_iron, the chassis and mounts: forged iron, hammered, pitted in clusters with rust in the pits, mill scale
    left in dark bluish patches, rubbed bright on what stands up"""
    T = Tile('skr_iron', .25)
    hammer = T.dents(520, (.005, .014))
    small = T.dents(900, (.0012, .003))
    cluster = smooth(.05, .45, T.noise(.04, 3))
    pits = T.dents(900, (.0003, .0010)) * cluster
    scale = smooth(.25, .6, T.noise(.03, 4))
    var = T.noise(.06, 3)
    alb = hexc('#2e2b28') * (.85 + .15 * var[..., None])
    alb = mix(alb, hexc('#20232a'), scale * .55)                                   # mill scale
    alb = mix(alb, hexc('#5a3018'), pits * .75)                                    # rust in the pits
    alb = mix(alb, hexc('#4a4744'), smooth(.4, .9, hammer) * .25)
    rough = .52 + .12 * var + .12 * pits - .10 * scale + .06 * small
    metal = .78 - .45 * pits + .05 * scale
    T.write(alb, [(-hammer, .00035), (-small, .00010), (-pits, .00030), (var, .00030), (T.grain(1), .00002)], rough, metal, legacy_normal_jpg=True, legacy_mask_jpg=True, relief=1.5,
            cavity=.45)


def titanium():
    """skr_titanium, cages, rings and the muzzle: brushed titanium blued by the heat it carries: bands of straw,
    bronze, violet and blue where it ran hot, plain grey where it stayed cool"""
    T = Tile('skr_titanium', .25)
    brush = T.brushed(.025, axis=1)
    h = np.clip(.5 + .5 * T.noise(.06, 3), 0, 1)                                    # how hot each place ran
    stops = [(0.0, '#9a9792'), (.45, '#9a9792'), (.58, '#c4a463'), (.68, '#9a6a3c'), (.78, '#6a3f72'), (.88, '#3f5a92'), (1.0, '#5e7fa8')]
    alb = np.zeros((T.Z, T.Z, 3), np.float32)
    for (a, ca), (b, cb) in zip(stops[:-1], stops[1:]):
        t = np.clip((h - a) / max(b - a, 1e-6), 0, 1)[..., None]
        band = ((h >= a) & (h <= b))[..., None]
        alb = np.where(band, hexc(ca) * (1 - t) + hexc(cb) * t, alb)
    alb = alb * (.93 + .07 * brush[..., None])
    scr = T.lines(160, (.003, .02), (.00012, .0003), bend=.2, along=.75)
    alb = mix(alb, hexc('#c8c6c2'), scr * .5)
    rough = .18 + .06 * brush + .08 * (1 - h) - .05 * scr
    T.write(alb, [(brush, .00001), (-scr, .00004), (T.noise(.05, 3), .00006), (T.grain(1), .000006)], rough, .95, legacy_normal_jpg=True, legacy_mask_jpg=True, relief=1.3, cavity=.25)


def poly():
    """skr_poly, grip, guard, cell and fore panel: a dark warm polymer, bead-blasted to a fine stipple, moulded with
    their hex in shallow relief, scuffed pale along edges it rubbed"""
    T = Tile('skr_poly', .25)
    d1, d2, hid = T.cells(.0042, warp=.0004)
    ridge = 1 - smooth(0.0, .14, d2 - d1)                                          # the moulded hex
    stip = T.noise(.0007, 2)
    var = T.noise(.05, 3)
    scuff = T.lines(140, (.003, .02), (.0003, .0009), bend=.5) * smooth(.15, .5, T.noise(.07, 2))
    alb = hexc('#1f1c19') * (.88 + .10 * var[..., None] + .04 * hid[..., None])
    alb = mix(alb, hexc('#2c2823'), ridge * .35)
    alb = mix(alb, hexc('#4b4640'), scuff * .5)
    rough = .62 + .06 * var - .10 * ridge - .14 * scuff + .05 * stip
    T.write(alb, [(ridge, .00010), (stip, .000025), (-scuff, .00004), (var, .00015), (T.grain(1), .000008)], rough, 0.0, legacy_normal_jpg=True, legacy_mask_jpg=True, relief=1.4, cavity=.35)


def rubber():
    """skr_rubber, the grip's panels and the pad: a deep diamond knurl (2.4 mm), its peaks worn paler and smoother"""
    T = Tile('skr_rubber', .25)
    x, y = _xy(T)
    p = .0024
    k = np.abs(np.sin(np.pi * (x + y) / p)) * np.abs(np.sin(np.pi * (x - y) / p))
    k = k ** .6
    wear = smooth(.1, .6, T.noise(.04, 3)) * k
    var = T.noise(.05, 3)
    alb = hexc('#161412') * (.9 + .08 * var[..., None])
    alb = mix(alb, hexc('#2e2a26'), wear * .6)
    rough = .82 - .18 * wear + .04 * var
    T.write(alb, [(k, .00045), (T.noise(.0008, 2), .00002), (T.grain(1), .000008)], rough, 0.0, legacy_normal_jpg=True, legacy_mask_jpg=True, relief=1.4, cavity=.5)


if __name__ == '__main__':
    want = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else ['skin', 'armour', 'dark']
    for w in want:
        globals()[w]()
