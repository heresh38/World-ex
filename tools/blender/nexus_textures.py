"""Bakes the Nexus Prime kit's material sets (nexus.py), after the owner's city art: dark slate and gunmetal under
night blue, cyan light lines, violet crystal glow, lit windows.

  nx_stone    dark slate ashlar: big dressed blocks, chipped edges, rain streaks
  nx_panel    gunmetal hull panels: seams, rivet rows, scuffs
  nx_trim     brushed steel trim with a warm sheen
  nx_window   facade glass grid: dark panes, some lit warm / cyan (also the emissive map)
  nx_paving   plaza paving: large slabs in a running bond, worn paths
  nx_rock     mountain / cliff rock with strata

<name>_c.jpg colour and <name>_n.jpg tangent normal (seamless; the kit is box-mapped in world metres).

Run: blender --background --python tools/blender/nexus_textures.py
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
        s = g.math('ABSOLUTE', g.math('SINE', g.math('MULTIPLY', a, math.pi * freq)))
        return g.math('POWER', s, sharp) if sharp != 1.0 else s

    def soft(g, seed, thr, w=.14):
        n = g.math('SUBTRACT', g.noise(5, 6, .62, seed), thr)
        return g.math('MULTIPLY', g.math('MINIMUM', g.math('MAXIMUM', n, 0.0), w), 1 / w)

    def bricks(g, nx, ny, mortar, offset=.5):
        nd = g.brick(1 / nx, 1 / ny, offset, mortar, (1, 1, 1), (0, 0, 0), 0.0)
        return nd.outputs['Fac'], nd.outputs['Color']

    # ------------------------------------------------ slate ashlar
    def stone_h(g):
        fac, _ = bricks(g, 3, 6, .012)
        return g.math('ADD', g.math('MULTIPLY', g.math('SUBTRACT', 1.0, fac), .8), g.math('MULTIPLY', g.noise(24, 5, .62, 11), .25))

    def stone_c(g):
        fac, _ = bricks(g, 3, 6, .012)
        c = g.ramp(g.noise(6, 5, .6, 12), [(.25, '#23262d'), (.75, '#353943')])
        cell = g.ramp(g.voronoi(3, 13, 'F1', 'Color'), [(0.0, (.85, .86, .9)), (1.0, (1.12, 1.1, 1.08))])
        c = g.mix(c, cell, 1.0, 'MULTIPLY')
        c = g.mix(c, (.07, .075, .085), g.math('MULTIPLY', fac, .85))                              # mortar joints
        u, v = uvsep(g)
        streak = g.math('MULTIPLY', soft(g, 14, .55), g.math('GREATER_THAN', g.noise(2, 2, .5, 15), .5))
        c = g.mix(c, (.12, .13, .15), g.math('MULTIPLY', streak, .5))                               # rain streaks
        return g.mix(c, (.5, .52, .56), g.math('MULTIPLY', soft(g, 16, .7), .25))                  # weathered pale
    bake(p, 'nx_stone', stone_c, stone_h, strength=.6, size=SIZE)

    # ------------------------------------------------ gunmetal panels
    def panel_h(g):
        fac, _ = bricks(g, 2, 4, .006, 0.0)
        u, v = uvsep(g)
        rivets = g.math('LESS_THAN', g.voronoi(48, 21, 'F1', 'Distance'), .12)
        return g.math('ADD', g.math('MULTIPLY', g.math('SUBTRACT', 1.0, fac), .9), g.math('MULTIPLY', rivets, .25))

    def panel_c(g):
        fac, _ = bricks(g, 2, 4, .006, 0.0)
        c = g.ramp(g.noise(5, 5, .6, 22), [(.25, '#2b3038'), (.75, '#3d434d')])
        _, cell = bricks(g, 2, 4, .006, 0.0)
        c = g.mix(c, g.ramp(g.noise(3, 2, .5, 23), [(.3, (.9, .92, .95)), (.7, (1.08, 1.08, 1.1))]), 1.0, 'MULTIPLY')
        c = g.mix(c, (.06, .065, .075), g.math('MULTIPLY', fac, .9))
        return g.mix(c, (.55, .58, .62), g.math('MULTIPLY', soft(g, 24, .66), .35))                # scuffs
    bake(p, 'nx_panel', panel_c, panel_h, strength=.5, size=SIZE)

    # ------------------------------------------------ brushed trim
    def trim_c(g):
        u, v = uvsep(g)
        c = g.ramp(g.noise(2, 2, .5, 31), [(.3, '#6a6a68'), (.7, '#8c8a84')])
        return g.mix(c, (.52, .45, .32), g.math('MULTIPLY', soft(g, 32, .55), .4))                 # warm sheen
    bake(p, 'nx_trim', trim_c, lambda g: g.math('MULTIPLY', band(g, uvsep(g)[1], 300, .5), .3), strength=.25, size=512)

    # ------------------------------------------------ window grid (colour = emissive)
    def win_c(g):
        u, v = uvsep(g)
        frame = g.math('MAXIMUM', g.math('LESS_THAN', band(g, u, 6), .16), g.math('LESS_THAN', band(g, v, 8), .14))
        lit = g.voronoi(1, 41, 'F1', 'Color')
        cells = g.n('ShaderNodeTexBrick', offset=0.0, offset_frequency=2, squash=1.0)
        g.nt.links.new(g.uv(), cells.inputs['Vector'])
        cells.inputs['Scale'].default_value = 1.0
        cells.inputs['Brick Width'].default_value = 1 / 6; cells.inputs['Row Height'].default_value = 1 / 8
        cells.inputs['Mortar Size'].default_value = 0.0
        cells.inputs['Color1'].default_value = (0, 0, 0, 1); cells.inputs['Color2'].default_value = (1, 1, 1, 1)
        cells.inputs['Bias'].default_value = -.72          # most rooms dark
        on = g.n('ShaderNodeSeparateColor'); g.nt.links.new(cells.outputs['Color'], on.inputs[0])
        glass = g.mix((.015, .02, .03), (.85, .66, .45), on.outputs[0])
        return g.mix(glass, (.05, .055, .065), frame)
    bake(p, 'nx_window', win_c, lambda g: g.math('MAXIMUM', g.math('LESS_THAN', band(g, uvsep(g)[0], 6), .16),
                                                      g.math('LESS_THAN', band(g, uvsep(g)[1], 8), .14)), strength=.8, size=SIZE)

    # ------------------------------------------------ plaza paving
    def pave_h(g):
        fac, _ = bricks(g, 4, 8, .008)
        return g.math('ADD', g.math('MULTIPLY', g.math('SUBTRACT', 1.0, fac), .7), g.math('MULTIPLY', g.noise(30, 4, .6, 51), .2))

    def pave_c(g):
        fac, cell = bricks(g, 4, 8, .008)
        c = g.ramp(g.noise(5, 5, .6, 52), [(.25, '#3a3d44'), (.75, '#4c5058')])
        c = g.mix(c, g.ramp(g.voronoi(4, 53, 'F1', 'Color'), [(0, (.88, .88, .9)), (1, (1.1, 1.08, 1.05))]), 1.0, 'MULTIPLY')
        c = g.mix(c, (.1, .105, .115), g.math('MULTIPLY', fac, .8))
        return g.mix(c, (.6, .62, .64), g.math('MULTIPLY', soft(g, 54, .62), .3))                  # worn paths
    bake(p, 'nx_paving', pave_c, pave_h, strength=.5, size=SIZE)

    # ------------------------------------------------ rock
    def rock_h(g):
        u, v = uvsep(g)
        strata = band(g, g.math('ADD', v, g.math('MULTIPLY', g.noise(3, 3, .5, 61), .15)), 9, .6)
        return g.math('ADD', g.math('MULTIPLY', strata, .4), g.math('MULTIPLY', g.noise(12, 7, .65, 62), .6))

    def rock_c(g):
        c = g.ramp(rock_h(g), [(.2, '#25262b'), (.55, '#3f414a'), (.9, '#5e606a')])
        return g.mix(c, (.32, .27, .4), g.math('MULTIPLY', soft(g, 63, .6), .3))                   # violet mineral cast
    bake(p, 'nx_rock', rock_c, rock_h, strength=.8, size=SIZE)


main()
