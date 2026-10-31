"""Bakes the organic material sets for the Writhe infestation and the VANTHOS alien species (Cycles, seamless).

Every set is hx_<name>_c.jpg (colour), _n.jpg (tangent normal) and _m.jpg (glTF metallic-roughness: G rough, B metal,
stored linear). Colours are kept light and only mildly tinted: the creature scripts put the macro colour (bruising,
growth tint, cavity darkening) in vertex colours, which three multiplies with these maps.

Sets: hx_flesh (striated wet muscle, vein web, pores), hx_skin (dead mottled skin with wrinkles and lesions),
hx_chitin (fused plates with seams and ridges), hx_bone (pitted bone with growth rings), hx_sac (glossy membrane
with a fine vein net), hx_rag (torn, soaked fabric weave).

Run: blender --background --python tools/blender/horror_textures.py
"""
import bpy, math, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import bl
from textures import bake, setup   # noqa: F401  (textures.G is the node-graph builder bake() hands us)

SIZE = 512


def aniso(g, fu, fv, detail=4, rough=.55, seed=0.0, kind='noise'):
    """Seamless noise with different feature counts along U and V (streaks / fibres when fv >> fu)."""
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
    w = g.math('ADD', out[3], seed * 17.31)
    if kind == 'voronoi':
        nd = g.n('ShaderNodeTexVoronoi', voronoi_dimensions='4D', feature='F1')
        g.nt.links.new(cmb.outputs[0], nd.inputs['Vector']); g.nt.links.new(w, nd.inputs['W'])
        nd.inputs['Scale'].default_value = 1.0
        return nd.outputs['Distance']
    nd = g.n('ShaderNodeTexNoise', noise_dimensions='4D')
    g.nt.links.new(cmb.outputs[0], nd.inputs['Vector']); g.nt.links.new(w, nd.inputs['W'])
    nd.inputs['Scale'].default_value = 1.0; nd.inputs['Detail'].default_value = detail
    nd.inputs['Roughness'].default_value = rough
    return nd.outputs['Fac']


def mr(g, rough, metal=0.0):
    """Roughness (G) and metalness (B) packed into a colour, pre-gamma so the JPG stores them linear."""
    def lin(v):
        return g.math('POWER', v, 2.2) if isinstance(v, bpy.types.NodeSocket) else v ** 2.2
    cmb = g.n('ShaderNodeCombineColor')
    for i, v in enumerate((1.0, rough, metal)):
        v = lin(v)
        if isinstance(v, bpy.types.NodeSocket):
            g.nt.links.new(v, cmb.inputs[i])
        else:
            cmb.inputs[i].default_value = v
    return cmb.outputs[0]


def lerp(g, a, b, t):
    return g.math('ADD', g.math('MULTIPLY', t, b - a), a)


def veins(g, f, seed, w=.06):
    """Thin connected web: where the two nearest voronoi features are nearly equidistant."""
    f1 = g.voronoi(f, seed, 'F1', 'Distance'); f2 = g.voronoi(f, seed, 'F2', 'Distance')
    d = g.math('SUBTRACT', f2, f1)
    return g.math('SUBTRACT', 1.0, g.math('MINIMUM', g.math('DIVIDE', d, w), 1.0))


def bake_set(p, name, c, n, m, strength=.5):
    bake(p, name, c, n, strength=strength, size=SIZE)
    out = bake(p, name + '_mtmp', m, size=SIZE)
    os.replace(out['c'], os.path.join(bl.TEXTURES, name + '_m.jpg'))
    print('[texture]', name + '_m.jpg')


def main():
    p = setup()

    # ------------------------------------------------ wet muscle: fibres, a vein web, pores and a few pale pustules
    def flesh_c(g):
        fib = aniso(g, 4, 46, 3, .55, 1)
        a = g.ramp(fib, [(.25, '#a8746c'), (.5, '#d8a89c'), (.75, '#f2d2c4')])
        blot = g.ramp(g.noise(4, 5, .6, 2), [(.35, (1, 1, 1)), (.7, (.72, .52, .58))])
        a = g.mix(a, blot, 1.0, 'MULTIPLY')
        a = g.mix(a, (.32, .06, .12), g.math('MULTIPLY', veins(g, 5, 3, .07), .8))
        a = g.mix(a, (.45, .12, .2), g.math('MULTIPLY', veins(g, 13, 4, .05), .5))
        pus = g.math('LESS_THAN', g.voronoi(22, 5, 'F1', 'Distance'), .09)
        return g.mix(a, (1.0, .92, .62), g.math('MULTIPLY', pus, .75))

    def flesh_n(g):
        fib = aniso(g, 4, 46, 3, .55, 1)
        pus = g.math('SUBTRACT', .12, g.math('MINIMUM', g.voronoi(22, 5, 'F1', 'Distance'), .12))
        return g.math('ADD', g.math('ADD', g.math('MULTIPLY', veins(g, 5, 3, .07), .9), g.math('MULTIPLY', veins(g, 13, 4, .05), .45)),
                      g.math('ADD', g.math('MULTIPLY', fib, .35), g.math('MULTIPLY', pus, 6.0)))

    def flesh_m(g):
        return mr(g, g.math('ADD', .16, g.math('MULTIPLY', g.noise(7, 3, .5, 6), .32)))
    bake_set(p, 'hx_flesh', flesh_c, flesh_n, flesh_m, .8)

    # ------------------------------------------------ dead host skin: mottling, wrinkles, lesions that weep
    def skin_c(g):
        a = g.ramp(g.noise(6, 7, .62, 7), [(.3, '#b7b0a2'), (.7, '#e2dccd')])
        mott = g.ramp(g.noise(2.5, 4, .55, 8), [(.4, (1, 1, 1)), (.75, (.78, .7, .76))])
        a = g.mix(a, mott, 1.0, 'MULTIPLY')
        a = g.mix(a, (.42, .3, .38), g.math('MULTIPLY', veins(g, 9, 9, .04), .45))
        les = g.math('LESS_THAN', g.voronoi(7, 10, 'F1', 'Distance'), .13)
        a = g.mix(a, (.55, .2, .18), g.math('MULTIPLY', les, .8))
        return g.mix(a, (.95, .82, .5), g.math('MULTIPLY', g.math('LESS_THAN', g.voronoi(7, 10, 'F1', 'Distance'), .05), .8))

    def skin_n(g):
        wr = aniso(g, 30, 3, 4, .6, 11)
        les = g.math('SUBTRACT', .14, g.math('MINIMUM', g.voronoi(7, 10, 'F1', 'Distance'), .14))
        return g.math('ADD', g.math('ADD', g.math('MULTIPLY', wr, .6), g.math('MULTIPLY', g.noise(60, 2, .5, 12), .25)),
                      g.math('MULTIPLY', les, -5.0))

    def skin_m(g):
        les = g.math('LESS_THAN', g.voronoi(7, 10, 'F1', 'Distance'), .14)
        return mr(g, g.math('SUBTRACT', g.math('ADD', .5, g.math('MULTIPLY', g.noise(5, 3, .5, 13), .2)), g.math('MULTIPLY', les, .35)))
    bake_set(p, 'hx_skin', skin_c, skin_n, skin_m, .6)

    # ------------------------------------------------ chitin: fused plates, dark seams, growth ridges, glossy
    def chit_c(g):
        cell = g.voronoi(6, 14, 'F1', 'Distance')
        a = g.ramp(cell, [(.0, '#e6e0d2'), (.45, '#b2a898'), (.62, '#6c6258')])
        a = g.mix(a, (.18, .14, .14), g.math('MULTIPLY', veins(g, 6, 14, .05), .95))
        rid = g.ramp(aniso(g, 2, 40, 2, .5, 15), [(.3, (1, 1, 1)), (.7, (.8, .78, .74))])
        return g.mix(a, rid, 1.0, 'MULTIPLY')

    def chit_n(g):
        cell = g.voronoi(6, 14, 'F1', 'Distance')
        return g.math('ADD', g.math('SUBTRACT', g.math('MULTIPLY', cell, -1.4), g.math('MULTIPLY', veins(g, 6, 14, .05), .9)),
                      g.math('MULTIPLY', aniso(g, 2, 40, 2, .5, 15), .25))

    def chit_m(g):
        return mr(g, g.math('ADD', .2, g.math('MULTIPLY', g.voronoi(6, 14, 'F1', 'Distance'), .35)))
    bake_set(p, 'hx_chitin', chit_c, chit_n, chit_m, .9)

    # ------------------------------------------------ bone: pitted, growth rings, grime in the pits
    def bone_c(g):
        a = g.ramp(g.noise(8, 5, .6, 16), [(.3, '#c8b898'), (.7, '#f0e6cc')])
        r = g.ramp(g.math('FRACT', g.math('MULTIPLY', aniso(g, 26, 2, 3, .5, 17), 8.0)), [(.0, (1, 1, 1)), (.8, (1, 1, 1)), (.95, (.62, .55, .42))])
        a = g.mix(a, r, 1.0, 'MULTIPLY')
        pits = g.math('LESS_THAN', g.voronoi(40, 18, 'F1', 'Distance'), .12)
        return g.mix(a, (.3, .2, .14), g.math('MULTIPLY', pits, .7))

    def bone_n(g):
        pits = g.math('SUBTRACT', g.math('MINIMUM', g.voronoi(40, 18, 'F1', 'Distance'), .15), .15)
        return g.math('ADD', g.math('MULTIPLY', pits, 4.0), g.math('MULTIPLY', g.noise(18, 5, .6, 19), .5))

    def bone_m(g):
        return mr(g, g.math('ADD', .42, g.math('MULTIPLY', g.noise(14, 4, .6, 20), .25)))
    bake_set(p, 'hx_bone', bone_c, bone_n, bone_m, .6)

    # ------------------------------------------------ membrane sac: glossy, a fine net of veins over mottled tissue
    def sac_c(g):
        a = g.ramp(g.noise(4, 4, .6, 21), [(.3, '#d8d0a8'), (.7, '#fbf6dc')])
        a = g.mix(a, (.42, .2, .14), g.math('MULTIPLY', veins(g, 4, 22, .045), .85))
        a = g.mix(a, (.6, .34, .22), g.math('MULTIPLY', veins(g, 11, 23, .04), .55))
        return g.mix(a, (.5, .55, .3), g.math('MULTIPLY', g.math('GREATER_THAN', g.noise(3, 3, .5, 24), .62), .4))

    def sac_n(g):
        return g.math('ADD', g.math('ADD', g.math('MULTIPLY', veins(g, 4, 22, .045), 1.0), g.math('MULTIPLY', veins(g, 11, 23, .04), .5)),
                      g.math('MULTIPLY', g.noise(30, 2, .5, 25), .15))

    def sac_m(g):
        return mr(g, g.math('ADD', .08, g.math('MULTIPLY', g.noise(6, 2, .5, 26), .18)))
    bake_set(p, 'hx_sac', sac_c, sac_n, sac_m, .7)

    # ------------------------------------------------ rags: soaked fabric weave with tears and stains
    def rag_c(g):
        tc = g.uv(); sep = g.n('ShaderNodeSeparateXYZ'); g.nt.links.new(tc, sep.inputs[0])
        wx = g.math('SINE', g.math('MULTIPLY', sep.outputs[0], 2 * math.pi * 96))
        wy = g.math('SINE', g.math('MULTIPLY', sep.outputs[1], 2 * math.pi * 96))
        weave = g.math('MULTIPLY', g.math('ADD', g.math('MULTIPLY', wx, wy), 1.0), .5)
        a = g.ramp(weave, [(.0, '#8a8a86'), (1.0, '#d4d2cc')])
        stain = g.ramp(g.noise(3, 6, .65, 27), [(.45, (1, 1, 1)), (.7, (.5, .32, .28))])
        return g.mix(a, stain, 1.0, 'MULTIPLY')

    def rag_n(g):
        tc = g.uv(); sep = g.n('ShaderNodeSeparateXYZ'); g.nt.links.new(tc, sep.inputs[0])
        wx = g.math('SINE', g.math('MULTIPLY', sep.outputs[0], 2 * math.pi * 96))
        wy = g.math('SINE', g.math('MULTIPLY', sep.outputs[1], 2 * math.pi * 96))
        return g.math('ADD', g.math('MULTIPLY', g.math('MULTIPLY', wx, wy), .3), g.math('MULTIPLY', g.noise(8, 5, .6, 28), .8))

    def rag_m(g):
        wet = g.math('GREATER_THAN', g.noise(3, 6, .65, 27), .6)
        return mr(g, g.math('SUBTRACT', .85, g.math('MULTIPLY', wet, .45)))
    bake_set(p, 'hx_rag', rag_c, rag_n, rag_m, .5)


if __name__ == '__main__':
    main()
