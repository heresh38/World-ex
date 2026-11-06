"""Bakes the Void Requiem material sets (the VANTHOS boss reward guns, void_requiem.py) with Cycles, the same way
weapon_textures.py does (seamless 4D-torus noise through textures.bake()).

  vq_obsidian  glossy black gunmetal: faint violet fracture lines like volcanic glass, brushing along the gun, scratches
  vq_plate     matte black gunmetal for side plates and furniture: stippled, rubbed lighter where hands go
  vq_gold      weathered gold trim: brushed, engraved filigree grooves, tarnish in patches, bright scuffs
  vq_crystal   void crystal (colour doubles as emission): faceted cells from deep violet to lilac, glowing fractures
  vq_grip      black wrapped grip: diagonal cord wrap with a fine weave

<name>_c.jpg colour, <name>_n.jpg tangent normal, <name>_m.jpg (G roughness, B metalness, linear) for PBR sets.
U runs along the gun (gunkit.uv_project), so brushing and wrap follow the barrel.

Run: blender --background --python tools/blender/void_textures.py
"""
import bpy, math, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import bl
from textures import setup
from weapon_textures import aniso, mr, bake_set


def main():
    p = setup()
    bpy.context.scene.view_settings.view_transform = 'Standard'

    def fracture(g, f, seed, w=.022):
        """Thin cell borders (F2 - F1 small): cracks, engraving, crystal facets."""
        f1 = g.voronoi(f, seed, 'F1', 'Distance'); f2 = g.voronoi(f, seed, 'F2', 'Distance')
        return g.math('LESS_THAN', g.math('SUBTRACT', f2, f1), w)

    def scratches(g, seed, thr=.72):
        return g.math('GREATER_THAN', aniso(g, 3, 80, 2, .5, seed), thr)

    # ------------------------------------------------ obsidian gunmetal
    def obs_c(g):
        base = g.ramp(aniso(g, 2, 150, 3, .5, 101), [(.3, '#0b0a0f'), (.7, '#17141d')])
        cloud = g.ramp(g.noise(5, 5, .6, 102), [(.35, (1, 1, 1)), (.75, (1.25, 1.15, 1.45))])
        c = g.mix(base, cloud, 1.0, 'MULTIPLY')
        c = g.mix(c, (.12, .07, .2), g.math('MULTIPLY', fracture(g, 4, 103, .018), .55))
        c = g.mix(c, (.07, .045, .11), g.math('MULTIPLY', fracture(g, 11, 104, .03), .35))
        dust = g.math('GREATER_THAN', g.noise(4, 6, .62, 105), .66)
        c = g.mix(c, (.11, .105, .11), g.math('MULTIPLY', dust, .35))
        return g.mix(c, (.3, .29, .33), g.math('MULTIPLY', scratches(g, 106), .7))

    def obs_n(g):
        return g.math('ADD', g.math('ADD', g.math('MULTIPLY', aniso(g, 2, 200, 2, .5, 107), .25), g.math('MULTIPLY', fracture(g, 4, 103, .018), -.6)),
                      g.math('MULTIPLY', scratches(g, 106), -.45))

    def obs_m(g):
        dust = g.math('GREATER_THAN', g.noise(4, 6, .62, 105), .66)
        r = g.math('ADD', .2, g.math('MULTIPLY', aniso(g, 2, 90, 2, .5, 108), .08))
        r = g.math('ADD', r, g.math('ADD', g.math('MULTIPLY', scratches(g, 106), .22), g.math('MULTIPLY', dust, .18)))
        return mr(g, r, g.math('ADD', .86, g.math('MULTIPLY', scratches(g, 106), .12)))
    bake_set(p, 'vq_obsidian', obs_c, obs_n, obs_m, .35)

    # ------------------------------------------------ matte black plate
    def plate_c(g):
        a = g.ramp(g.noise(7, 4, .5, 111), [(.3, '#141418'), (.7, '#1e1d23')])
        dots = g.math('LESS_THAN', g.voronoi(90, 112, 'F1', 'Distance'), .2)
        a = g.mix(a, (.05, .05, .06), g.math('MULTIPLY', dots, .45))
        rub = g.math('GREATER_THAN', g.noise(4, 5, .6, 113), .64)
        a = g.mix(a, (.2, .19, .22), g.math('MULTIPLY', rub, .5))
        return g.mix(a, (.26, .25, .29), g.math('MULTIPLY', scratches(g, 114, .75), .55))

    def plate_n(g):
        return g.math('ADD', g.math('SUBTRACT', 1.0, g.math('MULTIPLY', g.voronoi(90, 112, 'F1', 'Distance'), 1.2)),
                      g.math('MULTIPLY', scratches(g, 114, .75), -.5))

    def plate_m(g):
        rub = g.math('GREATER_THAN', g.noise(4, 5, .6, 113), .64)
        return mr(g, g.math('ADD', .5, g.math('ADD', g.math('MULTIPLY', g.noise(30, 2, .5, 115), .1), g.math('MULTIPLY', rub, -.14))),
                  g.math('ADD', .66, g.math('MULTIPLY', rub, .2)))
    bake_set(p, 'vq_plate', plate_c, plate_n, plate_m, .4)

    # ------------------------------------------------ weathered gold trim
    def tarnish(g):
        return g.math('GREATER_THAN', g.noise(5, 6, .62, 121), .6)

    def gold_c(g):
        a = g.ramp(aniso(g, 2, 140, 3, .5, 122), [(.25, '#8c6422'), (.6, '#c2913a'), (.9, '#e3bb68')])
        a = g.mix(a, (.32, .2, .07), g.math('MULTIPLY', fracture(g, 7, 123, .03), .8))          # engraved filigree
        a = g.mix(a, (.42, .28, .1), g.math('MULTIPLY', fracture(g, 17, 124, .04), .45))
        a = g.mix(a, (.2, .14, .06), g.math('MULTIPLY', tarnish(g), .62))
        return g.mix(a, (.98, .86, .56), g.math('MULTIPLY', scratches(g, 125), .7))

    def gold_n(g):
        return g.math('ADD', g.math('ADD', g.math('MULTIPLY', fracture(g, 7, 123, .03), -.9), g.math('MULTIPLY', fracture(g, 17, 124, .04), -.4)),
                      g.math('MULTIPLY', aniso(g, 2, 180, 2, .5, 126), .25))

    def gold_m(g):
        t = tarnish(g)
        return mr(g, g.math('ADD', .26, g.math('ADD', g.math('MULTIPLY', t, .3), g.math('MULTIPLY', fracture(g, 7, 123, .03), .2))),
                  g.math('ADD', 1.0, g.math('MULTIPLY', t, -.35)))
    bake_set(p, 'vq_gold', gold_c, gold_n, gold_m, .45)

    # ------------------------------------------------ void crystal (emissive colour)
    def crys_c(g):
        cell = g.voronoi(5, 131, 'F1', 'Color')
        sep = g.n('ShaderNodeSeparateColor'); g.nt.links.new(cell, sep.inputs[0])
        a = g.ramp(sep.outputs[0], [(.0, '#2a0656'), (.5, '#6a22c8'), (1.0, '#b060ff')])
        a = g.mix(a, g.ramp(g.noise(6, 5, .6, 132), [(.3, (.7, .7, .8)), (.8, (1.3, 1.2, 1.4))]), 1.0, 'MULTIPLY')
        a = g.mix(a, (.96, .8, 1.0), g.math('MULTIPLY', fracture(g, 5, 131, .025), .9))
        return g.mix(a, (.85, .6, 1.0), g.math('MULTIPLY', fracture(g, 13, 133, .02), .5))

    def crys_n(g):
        return g.math('ADD', g.math('MULTIPLY', fracture(g, 5, 131, .025), -.8), g.math('MULTIPLY', g.voronoi(5, 131, 'F1', 'Distance'), .5))
    bake_set(p, 'vq_crystal', crys_c, crys_n, None, .5)

    # ------------------------------------------------ wrapped grip
    def wrap_h(g):
        tc = g.uv(); sep = g.n('ShaderNodeSeparateXYZ'); g.nt.links.new(tc, sep.inputs[0])
        band = g.math('ABSOLUTE', g.math('SINE', g.math('MULTIPLY', g.math('ADD', sep.outputs[0], g.math('MULTIPLY', sep.outputs[1], 2.0)), math.pi * 10)))
        weave = g.math('ABSOLUTE', g.math('SINE', g.math('MULTIPLY', g.math('SUBTRACT', sep.outputs[0], sep.outputs[1]), math.pi * 64)))
        return g.math('ADD', g.math('MULTIPLY', g.math('POWER', band, .35), .75), g.math('MULTIPLY', weave, .25))

    def wrap_c(g):
        a = g.ramp(wrap_h(g), [(.0, '#060508'), (.6, '#141217'), (1.0, '#221f27')])
        worn = g.math('GREATER_THAN', g.noise(5, 5, .6, 141), .66)
        return g.mix(a, (.16, .15, .18), g.math('MULTIPLY', worn, .4))

    def wrap_m(g):
        return mr(g, g.math('ADD', .62, g.math('MULTIPLY', wrap_h(g), .16)), 0.0)
    bake_set(p, 'vq_grip', wrap_c, wrap_h, wrap_m, .8)


main()
