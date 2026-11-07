"""Bakes the shared wear mask the Unreal guns layer over their own material sets (so no gun looks factory-new):

  wear_mask.jpg   R = fine scratches (thin random strokes in several directions, denser in patches)
                  G = grime (soft blotches, heavier in a few places, where hands and dirt collect)
                  B = chip breakup (cell-shaped chips that break up the edge wear into flakes)

1024 px, seamless, linear values (the master material reads it as a mask). The guns' convex edges come from their
own `_wear` vertex attribute (gunkit.wear_attr), exported by export_fbx.py into the vertex colour alpha.

Run: blender --background --python tools/blender/wear_textures.py
"""
import bpy, math, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import bl
from textures import setup, bake

SIZE = 1024


def main():
    p = setup()
    bpy.context.scene.view_settings.view_transform = 'Standard'

    def streaks(g, fu, fv, seed, thr):
        """Thin bright strokes: noise stretched along one axis, thresholded."""
        tc = g.n('ShaderNodeTexCoord')
        sep = g.n('ShaderNodeSeparateXYZ'); g.nt.links.new(tc.outputs['UV'], sep.inputs[0])
        out = []
        for comp, f in ((sep.outputs[0], fu), (sep.outputs[1], fv)):
            R = f / (2 * math.pi)
            ang = g.math('MULTIPLY', comp, 2 * math.pi)
            out.append(g.math('MULTIPLY', g.math('COSINE', ang), R))
            out.append(g.math('MULTIPLY', g.math('SINE', ang), R))
        cmb = g.n('ShaderNodeCombineXYZ')
        for i in range(3):
            g.nt.links.new(out[i], cmb.inputs[i])
        w = g.math('ADD', out[3], seed * 13.7)
        nd = g.n('ShaderNodeTexNoise', noise_dimensions='4D')
        g.nt.links.new(cmb.outputs[0], nd.inputs['Vector']); g.nt.links.new(w, nd.inputs['W'])
        nd.inputs['Scale'].default_value = 1.0; nd.inputs['Detail'].default_value = 2; nd.inputs['Roughness'].default_value = .5
        return g.math('GREATER_THAN', nd.outputs['Fac'], thr)

    def mask_c(g):
        # scratches: three stroke directions, gathered in patches
        s = g.math('MAXIMUM', streaks(g, 6, 220, 1, .64), streaks(g, 220, 6, 2, .65))
        s = g.math('MAXIMUM', s, g.math('MAXIMUM', streaks(g, 3, 120, 7, .62), streaks(g, 140, 140, 3, .72)))
        patch = g.math('GREATER_THAN', g.noise(3, 4, .6, 4), .45)
        s = g.math('MULTIPLY', s, g.math('ADD', .25, g.math('MULTIPLY', patch, .75)))
        # grime: soft blotches
        grime = g.ramp(g.noise(5, 6, .62, 5), [(.48, (0, 0, 0)), (.8, (1, 1, 1))])
        gsep = g.n('ShaderNodeSeparateColor'); g.nt.links.new(grime, gsep.inputs[0])
        # chips: voronoi cells, some on
        chips = g.math('GREATER_THAN', g.voronoi(40, 6, 'F1', 'Distance'), .32)
        cmb = g.n('ShaderNodeCombineColor')
        g.nt.links.new(s, cmb.inputs[0]); g.nt.links.new(gsep.outputs[0], cmb.inputs[1]); g.nt.links.new(chips, cmb.inputs[2])
        return cmb.outputs[0]
    bake(p, 'wear_mask', mask_c, None, size=SIZE)


main()
