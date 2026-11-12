"""Bakes the shared wear mask the Unreal guns layer over their own material sets (so no gun looks factory-new):

  wear_mask.jpg   R = fine scratches (thin strokes, most of them ALONG the gun: the way it is drawn, slung and
                      laid down; a few across and diagonal; denser in patches)
                  G = grime and dust (soft blotches, heavier in a few places, where hands and dirt collect, over
                      a fine dust speckle)
                  B = chip breakup (cell-shaped chips, two sizes, that break the edge wear into flakes of bare metal)
  wear_mask2.jpg  R = rubbed high spots (broad soft patches where hands, holsters and slings polish the finish)
                  G = oil sheen / roughness variation (long soft streaks along the gun over a fine mottle: multiply
                      the roughness by 1 - G * amount)
                  B = smudges (clusters of small soft prints: raise the roughness, darken a little)
  (wear_mask2 is new in the third pass: the master material does not read it yet.)

4096 px, seamless, linear values (the master material reads it as a mask). The guns' convex edges come from their
own `_wear` vertex attribute (gunkit.wear_attr), exported by export_fbx.py into the vertex colour alpha.

Run: blender --background --python tools/blender/wear_textures.py
"""
import bpy, math, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import bl
from textures import setup, bake

SIZE = 4096


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
        s = g.math('MAXIMUM', streaks(g, 6, 220, 1, .64), streaks(g, 220, 6, 2, .7))
        s = g.math('MAXIMUM', s, g.math('MAXIMUM', streaks(g, 3, 120, 7, .62), streaks(g, 140, 140, 3, .74)))
        s = g.math('MAXIMUM', s, g.math('MAXIMUM', streaks(g, 4, 420, 9, .66), streaks(g, 9, 640, 12, .69)))
        patch = g.math('GREATER_THAN', g.noise(3, 4, .6, 4), .45)
        s = g.math('MULTIPLY', s, g.math('ADD', .25, g.math('MULTIPLY', patch, .75)))
        # grime: soft blotches
        grime = g.ramp(g.noise(5, 6, .62, 5), [(.48, (0, 0, 0)), (.8, (1, 1, 1))])
        gsep = g.n('ShaderNodeSeparateColor'); g.nt.links.new(grime, gsep.inputs[0])
        dust = g.math('MULTIPLY', g.math('GREATER_THAN', g.noise(260, 2, .5, 21), .62), .35)
        gr = g.math('MAXIMUM', gsep.outputs[0], dust)
        # chips: voronoi cells of two sizes, some on
        chips = g.math('MAXIMUM', g.math('GREATER_THAN', g.voronoi(40, 6, 'F1', 'Distance'), .32),
                       g.math('GREATER_THAN', g.voronoi(130, 9, 'F1', 'Distance'), .36))
        cmb = g.n('ShaderNodeCombineColor')
        g.nt.links.new(s, cmb.inputs[0]); g.nt.links.new(gr, cmb.inputs[1]); g.nt.links.new(chips, cmb.inputs[2])
        return cmb.outputs[0]
    bake(p, 'wear_mask', mask_c, None, size=SIZE)

    def val(g, colour):
        sep = g.n('ShaderNodeSeparateColor'); g.nt.links.new(colour, sep.inputs[0])
        return sep.outputs[0]

    def soft(g, fu, fv, seed):
        """streaks without the threshold: a soft value stretched along one axis"""
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
        nd = g.n('ShaderNodeTexNoise', noise_dimensions='4D')
        g.nt.links.new(cmb.outputs[0], nd.inputs['Vector']); g.nt.links.new(g.math('ADD', out[3], seed * 13.7), nd.inputs['W'])
        nd.inputs['Scale'].default_value = 1.0; nd.inputs['Detail'].default_value = 3; nd.inputs['Roughness'].default_value = .55
        return nd.outputs['Fac']

    def mask2_c(g):
        rub = val(g, g.ramp(g.noise(2.5, 5, .6, 31), [(.5, (0, 0, 0)), (.74, (1, 1, 1))]))
        oil = g.math('ADD', g.math('MULTIPLY', val(g, g.ramp(soft(g, 2, 26, 33), [(.42, (0, 0, 0)), (.7, (1, 1, 1))])), .7),
                     g.math('MULTIPLY', g.noise(60, 3, .5, 34), .3))
        prints = g.math('LESS_THAN', g.voronoi(70, 35, 'F1', 'Distance'), .2)
        where = val(g, g.ramp(g.noise(4, 4, .6, 36), [(.56, (0, 0, 0)), (.7, (1, 1, 1))]))
        smudge = g.math('MULTIPLY', g.math('MULTIPLY', prints, where), g.math('ADD', .55, g.math('MULTIPLY', g.noise(180, 2, .5, 37), .45)))
        cmb = g.n('ShaderNodeCombineColor')
        g.nt.links.new(rub, cmb.inputs[0]); g.nt.links.new(oil, cmb.inputs[1]); g.nt.links.new(smudge, cmb.inputs[2])
        return cmb.outputs[0]
    bake(p, 'wear_mask2', mask2_c, None, size=SIZE)


main()
