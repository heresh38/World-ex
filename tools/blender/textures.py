"""Bakes every tiling texture the game uses with Cycles (procedural node setups -> JPG).

Noise-based maps are made seamless by sampling 4D noise on a torus (u,v -> cos/sin pairs);
pattern-based maps (panels, windows, grates) use integer repeat counts so they wrap exactly.
Outputs assets/textures/<name>_c.jpg (colour), _n.jpg (tangent normal) and optional _e.jpg (emissive).
"""
import bpy, math, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import bl

SIZE = 512


def setup():
    bl.reset()
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.samples = 4
    sc.cycles.device = 'CPU'
    sc.render.bake.margin = 0
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, 0))
    return bpy.context.object


class G:
    """Tiny node-graph builder."""

    def __init__(self, nt):
        self.nt = nt; self.x = -1200

    def n(self, t, **inputs):
        nd = self.nt.nodes.new(t)
        nd.location = (self.x, 0); self.x += 120
        for k, v in inputs.items():
            if hasattr(nd, k) and not k[0].isupper():
                setattr(nd, k, v)
            else:
                self.set(nd, k, v)
        return nd

    def set(self, nd, k, v):
        sock = nd.inputs[k]
        if hasattr(v, 'is_output') or isinstance(v, bpy.types.NodeSocket):
            self.nt.links.new(v, sock)
        else:
            sock.default_value = v

    def math(self, op, a, b=0.0):
        nd = self.nt.nodes.new('ShaderNodeMath'); nd.operation = op
        for i, v in enumerate((a, b)):
            if isinstance(v, bpy.types.NodeSocket):
                self.nt.links.new(v, nd.inputs[i])
            else:
                nd.inputs[i].default_value = v
        return nd.outputs[0]

    def torus(self, freq, seed=0.0):
        """Returns (vector, w) sockets for seamless 4D sampling; freq = features per tile."""
        tc = self.n('ShaderNodeTexCoord')
        sep = self.n('ShaderNodeSeparateXYZ'); self.nt.links.new(tc.outputs['UV'], sep.inputs[0])
        R = freq / (2 * math.pi)
        out = []
        for comp in (sep.outputs[0], sep.outputs[1]):
            ang = self.math('MULTIPLY', comp, 2 * math.pi)
            out.append(self.math('MULTIPLY', self.math('COSINE', ang), R))
            out.append(self.math('MULTIPLY', self.math('SINE', ang), R))
        cmb = self.n('ShaderNodeCombineXYZ')
        self.nt.links.new(out[0], cmb.inputs[0]); self.nt.links.new(out[1], cmb.inputs[1])
        self.nt.links.new(out[2], cmb.inputs[2])
        w = self.math('ADD', out[3], seed * 17.31)
        return cmb.outputs[0], w

    def noise(self, freq, detail=4, rough=.55, seed=0.0):
        v, w = self.torus(freq, seed)
        nd = self.n('ShaderNodeTexNoise', noise_dimensions='4D')
        self.nt.links.new(v, nd.inputs['Vector']); self.nt.links.new(w, nd.inputs['W'])
        nd.inputs['Scale'].default_value = 1.0; nd.inputs['Detail'].default_value = detail
        nd.inputs['Roughness'].default_value = rough
        return nd.outputs['Fac']

    def voronoi(self, freq, seed=0.0, feature='F1', out='Distance'):
        v, w = self.torus(freq, seed)
        nd = self.n('ShaderNodeTexVoronoi', voronoi_dimensions='4D', feature=feature)
        self.nt.links.new(v, nd.inputs['Vector']); self.nt.links.new(w, nd.inputs['W'])
        nd.inputs['Scale'].default_value = 1.0
        return nd.outputs[out]

    def uv(self):
        return self.n('ShaderNodeTexCoord').outputs['UV']

    def brick(self, w, h, offset=0.0, mortar=.02, c1=(1, 1, 1), c2=(0, 0, 0), bias=0.0, squash=1.0):
        nd = self.n('ShaderNodeTexBrick', offset=offset, offset_frequency=2, squash=squash)
        self.nt.links.new(self.uv(), nd.inputs['Vector'])
        nd.inputs['Scale'].default_value = 1.0; nd.inputs['Brick Width'].default_value = w
        nd.inputs['Row Height'].default_value = h; nd.inputs['Mortar Size'].default_value = mortar
        nd.inputs['Mortar Smooth'].default_value = .1; nd.inputs['Bias'].default_value = bias
        nd.inputs['Color1'].default_value = (*c1, 1); nd.inputs['Color2'].default_value = (*c2, 1)
        nd.inputs['Mortar'].default_value = (0, 0, 0, 1)
        return nd

    def ramp(self, fac, stops, constant=False):
        nd = self.n('ShaderNodeValToRGB')
        if constant:
            nd.color_ramp.interpolation = 'CONSTANT'
        els = nd.color_ramp.elements
        while len(els) < len(stops):
            els.new(0.5)
        for e, (p, c) in zip(els, stops):
            e.position = p
            e.color = (*bl.hexrgb(c), 1) if isinstance(c, str) else (*c, 1)
        self.nt.links.new(fac, nd.inputs['Fac'])
        return nd.outputs['Color']

    def mix(self, a, b, f, blend='MIX'):
        nd = self.n('ShaderNodeMix', data_type='RGBA', blend_type=blend)
        for k, v in ((0, f), (6, a), (7, b)):
            if isinstance(v, bpy.types.NodeSocket):
                self.nt.links.new(v, nd.inputs[k])
            elif k == 0:
                nd.inputs[k].default_value = v
            else:
                nd.inputs[k].default_value = (*v, 1) if len(v) == 3 else v
        return nd.outputs[2]


def bake(plane, name, color_fn, height_fn=None, emit_fn=None, strength=1.0, size=SIZE):
    """color_fn(G)->color socket, height_fn(G)->float socket, emit_fn(G)->color socket."""
    out = {}
    for kind, fn in (('c', color_fn), ('n', height_fn), ('e', emit_fn)):
        if fn is None:
            continue
        m = bpy.data.materials.new('%s_%s' % (name, kind))
        nt = m.node_tree
        for nd in list(nt.nodes):
            if nd.type != 'OUTPUT_MATERIAL':
                nt.nodes.remove(nd)
        outn = [nd for nd in nt.nodes if nd.type == 'OUTPUT_MATERIAL'][0]
        g = G(nt)
        img = bpy.data.images.new('%s_%s' % (name, kind), size, size)
        if kind == 'n':
            img.colorspace_settings.name = 'Non-Color'
            bsdf = g.n('ShaderNodeBsdfPrincipled')
            bump = g.n('ShaderNodeBump'); bump.inputs['Strength'].default_value = strength
            bump.inputs['Distance'].default_value = .02
            nt.links.new(fn(g), bump.inputs['Height'])
            nt.links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
            nt.links.new(bsdf.outputs[0], outn.inputs['Surface'])
        else:
            em = g.n('ShaderNodeEmission')
            nt.links.new(fn(g), em.inputs['Color'])
            nt.links.new(em.outputs[0], outn.inputs['Surface'])
        tn = nt.nodes.new('ShaderNodeTexImage'); tn.image = img; nt.nodes.active = tn
        plane.data.materials.clear(); plane.data.materials.append(m)
        bpy.ops.object.select_all(action='DESELECT'); plane.select_set(True)
        bpy.context.view_layer.objects.active = plane
        if kind == 'n':
            bpy.ops.object.bake(type='NORMAL', normal_space='TANGENT')
        else:
            bpy.ops.object.bake(type='EMIT')
        path = os.path.join(bl.TEXTURES, '%s_%s.jpg' % (name, kind))
        sc = bpy.context.scene
        sc.render.image_settings.file_format = 'JPEG'; sc.render.image_settings.quality = 88
        img.save_render(path)
        out[kind] = path
        print('[texture]', os.path.basename(path))
    return out


def main():
    p = setup()
    # --- ship / industrial hull panels: plate grid with seams, rivets and grime
    def panel_h(g):
        b = g.brick(.5, .25, offset=.5, mortar=.008)
        n = g.noise(24, 3, .5, 1)
        return g.math('ADD', g.math('MULTIPLY', b.outputs['Fac'], -1.0), g.math('MULTIPLY', n, .08))

    def panel_c(g):
        b = g.brick(.5, .25, offset=.5, mortar=.008, c1=(.66, .67, .68), c2=(.58, .6, .62), bias=0)
        grime = g.ramp(g.noise(6, 6, .62, 2), [(.35, '#ffffff'), (.75, '#8a8478')])
        c = g.mix(b.outputs['Color'], grime, 1.0, 'MULTIPLY')
        return g.mix(c, (.12, .12, .13), b.outputs['Fac'])
    bake(p, 'panel', panel_c, panel_h, strength=.6)

    # --- floor: diamond-tread steel
    def tread_h(g):
        v = g.voronoi(40, 3, 'F1', 'Distance')
        return g.math('SUBTRACT', 1.0, g.math('MULTIPLY', v, 2.2))

    def tread_c(g):
        wear = g.ramp(g.noise(10, 6, .6, 4), [(.3, '#4a4d52'), (.7, '#7c7f84')])
        v = g.voronoi(40, 3, 'F1', 'Distance')
        return g.mix(wear, (.75, .76, .78), g.math('LESS_THAN', v, .25))
    bake(p, 'tread', tread_c, tread_h, strength=.8)

    # --- concrete
    def conc_c(g):
        a = g.ramp(g.noise(5, 8, .6, 5), [(.2, '#6c6a66'), (.8, '#a19d95')])
        spec = g.ramp(g.noise(60, 2, .5, 6), [(.45, '#ffffff'), (.6, '#d4d0c8')])
        return g.mix(a, spec, 1.0, 'MULTIPLY')
    bake(p, 'concrete', conc_c, lambda g: g.noise(30, 6, .6, 7), strength=.25)

    # --- asphalt
    def asph_c(g):
        a = g.ramp(g.noise(80, 3, .5, 8), [(.3, '#1a1b1d'), (.7, '#3a3b3e')])
        patch = g.ramp(g.noise(3, 4, .5, 9), [(.4, '#ffffff'), (.7, '#c9c9cc')])
        return g.mix(a, patch, 1.0, 'MULTIPLY')
    bake(p, 'asphalt', asph_c, lambda g: g.noise(90, 3, .5, 10), strength=.35)

    # --- rock (planet ground, tinted per planet in-engine)
    def rock_h(g):
        v = g.voronoi(7, 11, 'F2', 'Distance')
        return g.math('ADD', g.math('MULTIPLY', v, .6), g.math('MULTIPLY', g.noise(14, 8, .65, 12), .7))

    def rock_c(g):
        a = g.ramp(g.noise(9, 8, .65, 12), [(.25, '#5a5550'), (.75, '#a39a8e')])
        cr = g.ramp(g.voronoi(7, 11, 'F2', 'Distance'), [(.0, '#3a3633'), (.25, '#ffffff')])
        return g.mix(a, cr, 1.0, 'MULTIPLY')
    bake(p, 'rock', rock_c, rock_h, strength=1.0)

    # --- sand / regolith
    def sand_c(g):
        return g.ramp(g.noise(20, 6, .6, 13), [(.3, '#b9a789'), (.7, '#e2d3b4')])

    def sand_h(g):
        tc = g.uv(); sep = g.n('ShaderNodeSeparateXYZ'); g.nt.links.new(tc, sep.inputs[0])
        ripple = g.math('SINE', g.math('ADD', g.math('MULTIPLY', sep.outputs[1], 2 * math.pi * 12),
                                       g.math('MULTIPLY', g.noise(3, 2, .5, 14), 6)))
        return g.math('ADD', g.math('MULTIPLY', ripple, .3), g.noise(60, 2, .5, 15))
    bake(p, 'sand', sand_c, sand_h, strength=.5)

    # --- ice
    def ice_c(g):
        a = g.ramp(g.noise(6, 6, .6, 16), [(.3, '#9fc4d6'), (.8, '#e7f4fa')])
        cr = g.ramp(g.voronoi(9, 17, 'F2', 'Distance'), [(.0, '#6f9fb8'), (.12, '#ffffff')])
        return g.mix(a, cr, 1.0, 'MULTIPLY')
    bake(p, 'ice', ice_c, lambda g: g.voronoi(9, 17, 'F2', 'Distance'), strength=.4)

    # --- moss / alien turf
    def moss_c(g):
        a = g.ramp(g.noise(30, 8, .7, 18), [(.25, '#2f3d1d'), (.75, '#76874a')])
        return a
    bake(p, 'moss', moss_c, lambda g: g.noise(40, 8, .7, 18), strength=.6)

    # --- hazard stripes
    def haz_c(g):
        tc = g.uv(); sep = g.n('ShaderNodeSeparateXYZ'); g.nt.links.new(tc, sep.inputs[0])
        s = g.math('FRACT', g.math('MULTIPLY', g.math('ADD', sep.outputs[0], sep.outputs[1]), 4))
        stripe = g.math('GREATER_THAN', s, .5)
        base = g.mix((.9, .62, .05), (.05, .05, .05), stripe)
        dirt = g.ramp(g.noise(5, 6, .6, 19), [(.3, '#ffffff'), (.8, '#8f8a80')])
        return g.mix(base, dirt, 1.0, 'MULTIPLY')
    bake(p, 'hazard', haz_c)

    # --- building facade: 8 x 16 windows per tile, random lit windows (emissive)
    def fac_c(g):
        b = g.brick(.125, .0625, offset=0.0, mortar=.009, c1=(.08, .1, .13), c2=(.16, .2, .26))
        frame = g.ramp(g.noise(8, 4, .5, 20), [(.3, '#6e7177'), (.7, '#9a9da3')])
        return g.mix(b.outputs['Color'], frame, b.outputs['Fac'])

    def fac_h(g):
        b = g.brick(.125, .0625, offset=0.0, mortar=.009)
        return b.outputs['Fac']

    def fac_e(g):
        b = g.brick(.125, .0625, offset=0.0, mortar=.009, c1=(1, 1, 1), c2=(0, 0, 0))
        sep = g.n('ShaderNodeSeparateColor'); g.nt.links.new(b.outputs['Color'], sep.inputs[0])
        on = g.ramp(sep.outputs[0], [(0.0, '#000000'), (.62, '#000000'), (.63, '#ffd9a0'), (.85, '#a9d8ff')], constant=True)
        return g.mix(on, (0, 0, 0), b.outputs['Fac'])
    bake(p, 'facade', fac_c, fac_h, fac_e, strength=.8)

    # --- second facade style: horizontal ribbon glazing
    def rib_c(g):
        b = g.brick(1.0, .1, offset=0.0, mortar=.014, c1=(.1, .14, .17), c2=(.12, .16, .2))
        return g.mix(b.outputs['Color'], (.82, .8, .76), b.outputs['Fac'])

    def rib_e(g):
        b = g.brick(.0625, .1, offset=0.0, mortar=.014, c1=(1, 1, 1), c2=(0, 0, 0))
        sep = g.n('ShaderNodeSeparateColor'); g.nt.links.new(b.outputs['Color'], sep.inputs[0])
        on = g.ramp(sep.outputs[0], [(0.0, '#000000'), (.7, '#000000'), (.71, '#fff0d0')], constant=True)
        rows = g.brick(1.0, .1, offset=0.0, mortar=.014)
        return g.mix(on, (0, 0, 0), rows.outputs['Fac'])
    bake(p, 'ribbon', rib_c, lambda g: g.brick(1.0, .1, mortar=.014).outputs['Fac'], rib_e, strength=.5)

    # --- carbon weave (gun grips, car interiors)
    def carbon_c(g):
        b = g.brick(.0625, .0625, offset=.5, mortar=.004, c1=(.05, .05, .055), c2=(.11, .11, .12), bias=0)
        return b.outputs['Color']
    bake(p, 'carbon', carbon_c, lambda g: g.brick(.0625, .0625, offset=.5, mortar=.004).outputs['Fac'], strength=.3)


if __name__ == '__main__':   # ship_textures.py imports bake()/G from here
    main()
