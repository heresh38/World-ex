"""Bakes the material sets of the Orion outfits (wardrobe.py orion(); the owner's concept pair in
art/reference/orion_pair.jpg): tactical-futuristic black, gunmetal grey and white with cyan light.

  or_quilt    black tech fabric quilted in long diamonds (the male jacket, the female bodice)
  or_coat     storm-grey heavy canvas, worn paler at the edges (the long coat)
  or_lining   electric-blue satin lining (coat edges)
  or_twill    black cargo twill (trousers)
  or_stretch  black stretch fabric with a fine rib (leggings)
  or_plate    gunmetal-grey armour plate: brushed, panel seams, worn bright on the edges (knee / shin / shoulder plates)
  or_leather  black grained leather (gloves, straps, belts, boots)
  or_knit     black ribbed knit (the neck gaiter)
  or_white    off-white technical shell fabric with panel seams (the female cropped jacket)
  or_sole     black rubber with a lug tread (boot soles)

<name>_c.jpg colour and <name>_n.jpg tangent normal (seamless; garments are box-mapped by wardrobe.Kit.build).

Run: blender --background --python tools/blender/orion_textures.py
"""
import bpy, math, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import bl
from textures import setup, bake

SIZE = 1024


def main():
    p = setup()
    bpy.context.scene.view_settings.view_transform = 'Standard'

    def uvsep(g):
        sep = g.n('ShaderNodeSeparateXYZ'); g.nt.links.new(g.uv(), sep.inputs[0])
        return sep.outputs[0], sep.outputs[1]

    def band(g, a, freq, sharp=1.0):
        """|sin(pi * freq * a)| ** sharp: 0 on the seams, 1 between them (integer freq: seamless)."""
        s = g.math('ABSOLUTE', g.math('SINE', g.math('MULTIPLY', a, math.pi * freq)))
        return g.math('POWER', s, sharp) if sharp != 1.0 else s

    def weave(g, f=180):
        u, v = uvsep(g)
        return g.math('MULTIPLY', g.math('ADD', band(g, u, f), band(g, v, f)), .5)

    def wear(g, seed, thr=.62):
        """Soft patches: 0 below thr, fading to 1 over 0.12 of noise above it."""
        n = g.math('SUBTRACT', g.noise(5, 6, .62, seed), thr - .04)
        return g.math('MULTIPLY', g.math('MINIMUM', g.math('MAXIMUM', n, 0.0), .16), 1 / .16 * .7)

    # ------------------------------------------------ quilted black tech fabric
    def quilt_h(g):
        u, v = uvsep(g)
        a = band(g, g.math('ADD', u, g.math('MULTIPLY', v, .5)), 8, .45)
        b = band(g, g.math('SUBTRACT', u, g.math('MULTIPLY', v, .5)), 8, .45)
        cells = g.math('MINIMUM', a, b)
        return g.math('ADD', g.math('MULTIPLY', cells, .8), g.math('MULTIPLY', weave(g, 220), .12))

    def quilt_c(g):
        c = g.ramp(quilt_h(g), [(.0, '#07080a'), (.45, '#121419'), (1.0, '#1d2027')])
        sheen = g.ramp(g.noise(5, 4, .6, 11), [(.3, (1, 1, 1)), (.8, (1.25, 1.27, 1.35))])
        return g.mix(c, sheen, 1.0, 'MULTIPLY')
    bake(p, 'or_quilt', quilt_c, quilt_h, strength=.7, size=SIZE)

    # ------------------------------------------------ storm-grey canvas coat
    def coat_h(g):
        return g.math('ADD', g.math('MULTIPLY', weave(g, 260), .5), g.math('MULTIPLY', g.noise(30, 4, .6, 21), .35))

    def coat_c(g):
        c = g.ramp(g.noise(4, 5, .6, 22), [(.25, '#4c5057'), (.75, '#666b73')])
        c = g.mix(c, g.ramp(weave(g, 260), [(.0, (.82, .82, .84)), (1.0, (1.06, 1.06, 1.08))]), 1.0, 'MULTIPLY')
        c = g.mix(c, (.55, .57, .6), g.math('MULTIPLY', wear(g, 23, .64), .35))
        return g.mix(c, (.2, .21, .23), g.math('MULTIPLY', wear(g, 24, .7), .4))       # grime
    bake(p, 'or_coat', coat_c, coat_h, strength=.35, size=SIZE)

    # ------------------------------------------------ blue satin lining
    def lining_c(g):
        return g.ramp(g.noise(3, 3, .5, 31), [(.2, '#0f4f96'), (.8, '#2e8de8')])
    bake(p, 'or_lining', lining_c, lambda g: g.math('MULTIPLY', weave(g, 300), .3), strength=.2, size=512)

    # ------------------------------------------------ black cargo twill
    def twill_h(g):
        u, v = uvsep(g)
        return g.math('ADD', g.math('MULTIPLY', band(g, g.math('ADD', g.math('MULTIPLY', u, 2.0), v), 140), .6),
                      g.math('MULTIPLY', g.noise(20, 3, .6, 41), .3))

    def twill_c(g):
        c = g.ramp(twill_h(g), [(.0, '#0e0f12'), (1.0, '#1f2227')])
        c = g.mix(c, g.ramp(g.noise(3, 4, .6, 42), [(.3, (.9, .9, .9)), (.8, (1.2, 1.2, 1.22))]), 1.0, 'MULTIPLY')
        return g.mix(c, (.16, .16, .17), g.math('MULTIPLY', wear(g, 43, .66), .45))       # faded patches
    bake(p, 'or_twill', twill_c, twill_h, strength=.5, size=SIZE)

    # ------------------------------------------------ black stretch leggings
    def stretch_h(g):
        u, v = uvsep(g)
        return g.math('ADD', g.math('MULTIPLY', band(g, u, 220, .6), .55), g.math('MULTIPLY', g.noise(14, 3, .5, 51), .2))

    def stretch_c(g):
        c = g.ramp(stretch_h(g), [(.0, '#0b0c0e'), (1.0, '#1a1c21')])
        return g.mix(c, g.ramp(g.noise(4, 4, .6, 52), [(.3, (.95, .95, .95)), (.8, (1.25, 1.27, 1.32))]), 1.0, 'MULTIPLY')
    bake(p, 'or_stretch', stretch_c, stretch_h, strength=.35, size=SIZE)

    # ------------------------------------------------ gunmetal armour plate
    def seams(g):
        u, v = uvsep(g)
        a = g.math('LESS_THAN', band(g, u, 3), .035)
        b = g.math('LESS_THAN', band(g, g.math('ADD', v, g.math('MULTIPLY', u, .25)), 2), .03)
        return g.math('MAXIMUM', a, b)

    def scratches(g, seed):
        u, v = uvsep(g)
        return g.math('GREATER_THAN', g.noise(70, 2, .5, seed), .72)

    def plate_h(g):
        return g.math('ADD', g.math('MULTIPLY', seams(g), -.9), g.math('ADD', g.math('MULTIPLY', g.noise(140, 2, .5, 61), .1),
                                                                         g.math('MULTIPLY', scratches(g, 62), -.25)))

    def plate_c(g):
        c = g.ramp(g.noise(4, 5, .6, 63), [(.25, '#6b7179'), (.75, '#868c95')])
        c = g.mix(c, (.92, .94, .97), g.math('MULTIPLY', wear(g, 64, .67), .5))           # worn bright
        c = g.mix(c, (.2, .21, .23), g.math('MULTIPLY', seams(g), .85))
        return g.mix(c, (.95, .96, .98), g.math('MULTIPLY', scratches(g, 62), .5))
    bake(p, 'or_plate', plate_c, plate_h, strength=.5, size=SIZE)

    # ------------------------------------------------ black leather
    def leather_h(g):
        return g.math('ADD', g.math('MULTIPLY', g.voronoi(90, 71, 'F1', 'Distance'), .7), g.math('MULTIPLY', g.noise(25, 3, .6, 72), .3))

    def leather_c(g):
        c = g.ramp(leather_h(g), [(.0, '#0a0a0b'), (1.0, '#1c1c1f')])
        return g.mix(c, (.2, .2, .22), g.math('MULTIPLY', wear(g, 73, .66), .5))
    bake(p, 'or_leather', leather_c, leather_h, strength=.45, size=SIZE)

    # ------------------------------------------------ black knit
    def knit_h(g):
        u, v = uvsep(g)
        return g.math('MULTIPLY', band(g, u, 64, .5), g.math('ADD', .7, g.math('MULTIPLY', band(g, v, 128), .3)))

    def knit_c(g):
        return g.ramp(knit_h(g), [(.0, '#08090a'), (1.0, '#1d1f22')])
    bake(p, 'or_knit', knit_c, knit_h, strength=.8, size=512)

    # ------------------------------------------------ off-white technical shell
    def white_h(g):
        return g.math('ADD', g.math('MULTIPLY', seams(g), -.7), g.math('MULTIPLY', weave(g, 280), .25))

    def white_c(g):
        c = g.ramp(g.noise(4, 5, .6, 81), [(.25, '#c9ccd1'), (.75, '#e3e5e8')])
        c = g.mix(c, (.45, .47, .5), g.math('MULTIPLY', seams(g), .7))
        return g.mix(c, (.6, .6, .62), g.math('MULTIPLY', wear(g, 82, .66), .3))           # grime
    bake(p, 'or_white', white_c, white_h, strength=.4, size=SIZE)

    # ------------------------------------------------ rubber sole
    def sole_h(g):
        u, v = uvsep(g)
        return g.math('MULTIPLY', band(g, u, 24, .3), band(g, v, 12, .3))

    def sole_c(g):
        return g.ramp(sole_h(g), [(.0, '#060607'), (1.0, '#18191b')])
    bake(p, 'or_sole', sole_c, sole_h, strength=.9, size=512)


main()
