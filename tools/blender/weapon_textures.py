"""Bakes the weapon material sets with Cycles (seamless 4D-torus noise from textures.G, through textures.bake()).

Every set is <name>_c.jpg (colour), <name>_n.jpg (tangent normal) and, for PBR sets, <name>_m.jpg
(glTF metallic-roughness: G = roughness, B = metalness, stored linear). Grain and brushing run along U, which
weapons.py maps onto the gun's length (Blender -Y), so wood grain and machining marks follow the barrel.

Kinetic (real-material) sets: wpn_steel (blued steel), wpn_park (parkerized / anodized), wpn_poly (stippled polymer), wpn_odg (olive painted polymer),
wpn_wood (oiled walnut), wpn_knurl (diamond checkering). Energy line: wpn_paint (ceramic paint, white so the shader
colour multiplies it), wpn_metal (machined gunmetal). Horror line: bio_flesh, bio_bone, bio_sac.

Run: blender --background --python tools/blender/weapon_textures.py
"""
import bpy, math, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import bl
from textures import bake, G, setup   # noqa: F401

SIZE = 2048         # holds up at 4K in first person (was 512)


def aniso(g, fu, fv, detail=4, rough=.55, seed=0.0, kind='noise'):
    """Seamless noise with different feature counts along U and V (stretched streaks when fv >> fu)."""
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


def mr(g, rough, metal):
    """Pack roughness (G) and metalness (B) sockets/floats into a colour; pre-gamma so the JPG stores them linear."""
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
    """a + (b - a) * t for floats/sockets."""
    return g.math('ADD', g.math('MULTIPLY', t, b - a), a)


def bake_set(p, name, c, n, m=None, strength=.5):
    bake(p, name, c, n, strength=strength, size=SIZE)
    if m:
        out = bake(p, name + '_mtmp', m, size=SIZE)
        os.replace(out['c'], os.path.join(bl.TEXTURES, name + '_m.jpg'))
        print('[texture]', name + '_m.jpg')


def main():
    p = setup()
    sc = bpy.context.scene
    sc.view_settings.view_transform = 'Standard'   # colours bake to the hex values given (no filmic curve)

    # ------------------------------------------------ blued steel: brushed along U, worn grey patches, fine scratches
    def wear_steel(g):
        return g.math('GREATER_THAN', g.noise(5, 6, .62, 1), .64)

    def scratch(g, seed):
        return g.math('GREATER_THAN', aniso(g, 3, 70, 2, .5, seed), .71)

    def steel_c(g):
        brush = g.ramp(aniso(g, 2, 160, 3, .5, 2), [(.3, '#292d34'), (.7, '#30343c')])
        bare = g.ramp(g.noise(30, 4, .5, 3), [(.3, '#3f4349'), (.8, '#4d5158')])
        c = g.mix(brush, bare, wear_steel(g))
        return g.mix(c, (.25, .26, .28), scratch(g, 4))

    def steel_n(g):
        return g.math('ADD', g.math('MULTIPLY', aniso(g, 2, 200, 2, .5, 5), .4), g.math('MULTIPLY', scratch(g, 4), -.5))

    def steel_m(g):
        w = wear_steel(g)
        return mr(g, g.math('ADD', g.math('MULTIPLY', w, -.14), g.math('ADD', .24, g.math('ADD', g.math('MULTIPLY', aniso(g, 2, 160, 3, .5, 2), .26), g.math('MULTIPLY', scratch(g, 4), -.08)))),
                  g.math('ADD', .78, g.math('MULTIPLY', w, .2)))
    bake_set(p, 'wpn_steel', steel_c, steel_n, steel_m, .35)

    # ------------------------------------------------ parkerized / anodized: matte phosphate speckle, rubbed patches
    def park_c(g):
        base = g.ramp(g.noise(90, 2, .5, 7), [(.35, '#262829'), (.65, '#34373a')])
        rub = g.ramp(g.noise(4, 5, .6, 8), [(.62, (0, 0, 0)), (.8, (.2, .2, .2))])
        sep = g.n('ShaderNodeSeparateColor'); g.nt.links.new(rub, sep.inputs[0])
        return g.mix(base, (.27, .28, .29), sep.outputs[0])

    def park_m(g):
        return mr(g, g.math('ADD', .62, g.math('MULTIPLY', g.noise(60, 2, .5, 9), .14)), .45)
    bake_set(p, 'wpn_park', park_c, lambda g: g.noise(120, 2, .5, 10), park_m, .25)

    # ------------------------------------------------ polymer: stippled black-grey with faint mould swirl
    def poly_c(g):
        a = g.ramp(g.noise(6, 4, .5, 11), [(.3, '#17181a'), (.7, '#222326')])
        dots = g.math('LESS_THAN', g.voronoi(70, 12, 'F1', 'Distance'), .18)
        return g.mix(a, (.05, .05, .055), g.math('MULTIPLY', dots, .5))

    def poly_n(g):
        return g.math('SUBTRACT', 1.0, g.math('MULTIPLY', g.voronoi(70, 12, 'F1', 'Distance'), 1.6))

    def poly_m(g):
        return mr(g, g.math('ADD', .66, g.math('MULTIPLY', g.noise(8, 3, .5, 13), .14)), 0.0)
    bake_set(p, 'wpn_poly', poly_c, poly_n, poly_m, .16)     # a fine stipple: at .5 a frame looked hammered

    # ------------------------------------------------ olive-drab painted polymer (precision-rifle stocks), scuffed to black
    def odg_c(g):
        a = g.ramp(g.noise(6, 4, .5, 37), [(.3, '#3d4630'), (.7, '#4d573c')])
        scuff = g.math('GREATER_THAN', g.noise(5, 6, .62, 38), .68)
        return g.mix(a, (.1, .1, .1), g.math('MULTIPLY', scuff, .8))
    bake_set(p, 'wpn_odg', odg_c, poly_n, poly_m, .16)

    # ------------------------------------------------ walnut: grain streaks along U with figure, oil sheen, handling wear
    def grain(g):
        warp = aniso(g, 2, 9, 3, .5, 14)
        base = aniso(g, 3, 46, 3, .6, 15)
        return g.math('FRACT', g.math('MULTIPLY', g.math('ADD', base, g.math('MULTIPLY', warp, .6)), 7.0))

    def wood_c(g):
        gr = grain(g)
        c = g.ramp(gr, [(.0, '#2f1a0e'), (.45, '#5c3519'), (.7, '#7a4a25'), (1.0, '#3a2112')])
        pores = g.math('GREATER_THAN', aniso(g, 6, 260, 1, .5, 16), .66)
        c = g.mix(c, (.12, .06, .03), g.math('MULTIPLY', pores, .6))
        worn = g.math('GREATER_THAN', g.noise(4, 5, .6, 17), .66)
        return g.mix(c, (.55, .38, .22), g.math('MULTIPLY', worn, .45))

    def wood_n(g):
        return g.math('ADD', g.math('MULTIPLY', grain(g), .25), g.math('MULTIPLY', aniso(g, 6, 260, 1, .5, 16), .5))

    def wood_m(g):
        worn = g.math('GREATER_THAN', g.noise(4, 5, .6, 17), .66)
        return mr(g, g.math('ADD', .38, g.math('ADD', g.math('MULTIPLY', worn, .25), g.math('MULTIPLY', grain(g), .08))), 0.0)
    bake_set(p, 'wpn_wood', wood_c, wood_n, wood_m, .4)

    # ------------------------------------------------ diamond checkering (grips, knobs)
    def knurl_h(g):
        tc = g.uv(); sep = g.n('ShaderNodeSeparateXYZ'); g.nt.links.new(tc, sep.inputs[0])
        a = g.math('ABSOLUTE', g.math('SINE', g.math('MULTIPLY', g.math('ADD', sep.outputs[0], sep.outputs[1]), math.pi * 24)))
        b = g.math('ABSOLUTE', g.math('SINE', g.math('MULTIPLY', g.math('SUBTRACT', sep.outputs[0], sep.outputs[1]), math.pi * 24)))
        return g.math('MINIMUM', a, b)

    def knurl_c(g):
        return g.ramp(knurl_h(g), [(.0, '#0c0c0d'), (.6, '#1c1d1f'), (1.0, '#2a2b2e')])
    bake_set(p, 'wpn_knurl', knurl_c, knurl_h, None, .9)

    # ------------------------------------------------ energy line: ceramic paint (white base, multiplied by the shader)
    def paint_c(g):
        a = g.ramp(g.noise(40, 3, .5, 18), [(.3, '#e6e6e6'), (.7, '#f6f6f6')])
        chip = g.math('GREATER_THAN', g.noise(7, 7, .66, 19), .7)
        b = g.brick(.5, .25, offset=.5, mortar=.004, c1=(1, 1, 1), c2=(1, 1, 1))
        a = g.mix(a, (.8, .8, .8), b.outputs['Fac'])
        return g.mix(a, (.55, .56, .58), chip)

    def paint_n(g):
        b = g.brick(.5, .25, offset=.5, mortar=.004)
        return g.math('ADD', g.math('MULTIPLY', b.outputs['Fac'], -.6), g.math('MULTIPLY', g.math('GREATER_THAN', g.noise(7, 7, .66, 19), .7), -.3))

    def paint_m(g):
        chip = g.math('GREATER_THAN', g.noise(7, 7, .66, 19), .7)
        return mr(g, g.math('ADD', .34, g.math('MULTIPLY', chip, -.06)), g.math('MULTIPLY', chip, .9))
    bake_set(p, 'wpn_paint', paint_c, paint_n, paint_m, .4)

    # ------------------------------------------------ energy line: machined gunmetal with milling arcs
    def metal_c(g):
        brush = g.ramp(aniso(g, 2, 120, 3, .5, 20), [(.3, '#2f3339'), (.7, '#363a41')])
        edge = g.math('GREATER_THAN', g.noise(6, 6, .6, 21), .67)
        return g.mix(brush, (.4, .42, .45), edge)

    def metal_m(g):
        edge = g.math('GREATER_THAN', g.noise(6, 6, .6, 21), .67)
        return mr(g, g.math('ADD', .23, g.math('MULTIPLY', aniso(g, 2, 120, 3, .5, 20), .28)), g.math('ADD', .82, g.math('MULTIPLY', edge, .16)))
    bake_set(p, 'wpn_metal', metal_c, lambda g: g.math('MULTIPLY', aniso(g, 2, 160, 2, .5, 22), .5), metal_m, .3)

    # ------------------------------------------------ horror line: flesh with a vein network and pale pustules
    def veins(g, f, seed):
        f1 = g.voronoi(f, seed, 'F1', 'Distance'); f2 = g.voronoi(f, seed, 'F2', 'Distance')
        return g.math('LESS_THAN', g.math('SUBTRACT', f2, f1), .06)

    def flesh_c(g):
        a = g.ramp(g.noise(9, 6, .62, 23), [(.25, '#4a1420'), (.55, '#8a3442'), (.8, '#b0606a')])
        bruise = g.ramp(g.noise(3, 4, .55, 24), [(.45, (1, 1, 1)), (.75, (.55, .45, .7))])
        a = g.mix(a, bruise, 1.0, 'MULTIPLY')
        a = g.mix(a, (.18, .05, .2), g.math('MULTIPLY', veins(g, 6, 25), .85))
        a = g.mix(a, (.32, .1, .26), g.math('MULTIPLY', veins(g, 15, 26), .55))
        pus = g.math('LESS_THAN', g.voronoi(26, 27, 'F1', 'Distance'), .1)
        return g.mix(a, (.8, .74, .38), g.math('MULTIPLY', pus, .7))

    def flesh_n(g):
        wr = aniso(g, 5, 22, 4, .6, 28)
        return g.math('ADD', g.math('ADD', g.math('MULTIPLY', veins(g, 6, 25), .8), g.math('MULTIPLY', veins(g, 15, 26), .4)),
                      g.math('MULTIPLY', wr, .5))

    def flesh_m(g):
        return mr(g, g.math('ADD', .26, g.math('MULTIPLY', g.noise(10, 3, .5, 29), .3)), 0.0)
    bake_set(p, 'bio_flesh', flesh_c, flesh_n, flesh_m, .7)

    # ------------------------------------------------ horror line: bone / chitin with growth rings and grime
    def rings(g):
        return g.math('FRACT', g.math('MULTIPLY', g.math('ADD', aniso(g, 30, 2, 3, .5, 30), 0.0), 9.0))

    def bone_c(g):
        a = g.ramp(g.noise(8, 5, .6, 31), [(.3, '#a8987a'), (.7, '#e4d8bc')])
        r = g.ramp(rings(g), [(.0, '#ffffff'), (.8, '#ffffff'), (.95, '#8a7a5c')])
        a = g.mix(a, r, 1.0, 'MULTIPLY')
        grime = g.ramp(g.noise(14, 6, .65, 32), [(.55, (1, 1, 1)), (.8, (.45, .36, .24))])
        return g.mix(a, grime, 1.0, 'MULTIPLY')

    def bone_m(g):
        return mr(g, g.math('ADD', .4, g.math('MULTIPLY', g.noise(14, 6, .65, 32), .2)), 0.0)
    bake_set(p, 'bio_bone', bone_c, lambda g: g.math('ADD', rings(g), g.math('MULTIPLY', g.noise(20, 5, .6, 33), .6)), bone_m, .5)

    # ------------------------------------------------ horror line: translucent glowing sac membrane (colour doubles as emission)
    def sac_c(g):
        a = g.ramp(g.noise(5, 4, .6, 34), [(.3, '#6cd43a'), (.7, '#c8ff6a')])
        return g.mix(a, (.08, .16, .04), g.math('MULTIPLY', veins(g, 8, 35), .9))
    bake_set(p, 'bio_sac', sac_c, lambda g: g.math('ADD', veins(g, 8, 35), g.math('MULTIPLY', g.noise(12, 3, .5, 36), .3)), None, .6)


main()
