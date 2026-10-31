"""Bakes the planet maps seen from orbit (equirectangular, wraps seamlessly in longitude, no pole pinching):

  earth_day.jpg    4096x2048  surface albedo: oceans with shelves, continents, deserts, forests, tundra, ice caps
  earth_clouds.jpg 4096x2048  cloud cover (grey = density), swirling storm systems, latitude bands
  earth_night.jpg  2048x1024  city lights on the night side
  earth_ms.jpg     2048x1024  R = terrain height, G = ocean mask (sun glint), B = ice

Every texel is shaded from its 3D direction on the unit sphere, so the noise is continuous across the seam and the poles.
Usage: blender --background --python tools/blender/planets.py [-- --fast]
"""
import bpy, math, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import bl
from textures import G

FAST = '--fast' in sys.argv


def setup():
    bl.reset()
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.samples = 1
    sc.cycles.device = 'CPU'
    sc.render.bake.margin = 0
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, 0))
    return bpy.context.object


class Sphere(G):
    """Node builder with sphere-direction sampling."""

    def dir(self):
        if getattr(self, '_dir', None):
            return self._dir
        tc = self.n('ShaderNodeTexCoord')
        sep = self.n('ShaderNodeSeparateXYZ'); self.nt.links.new(tc.outputs['UV'], sep.inputs[0])
        lon = self.math('MULTIPLY', sep.outputs[0], 2 * math.pi)
        lat = self.math('MULTIPLY', self.math('SUBTRACT', sep.outputs[1], .5), math.pi)
        cl = self.math('COSINE', lat)
        cmb = self.n('ShaderNodeCombineXYZ')
        self.nt.links.new(self.math('MULTIPLY', cl, self.math('COSINE', lon)), cmb.inputs[0])
        self.nt.links.new(self.math('MULTIPLY', cl, self.math('SINE', lon)), cmb.inputs[1])
        self.nt.links.new(self.math('SINE', lat), cmb.inputs[2])
        self._dir = cmb.outputs[0]; self._lat = lat
        return self._dir

    def lat(self):
        self.dir(); return self._lat

    def alat(self):
        return self.math('ABSOLUTE', self.lat())

    def vadd(self, v, off):
        nd = self.n('ShaderNodeVectorMath', operation='ADD'); self.nt.links.new(v, nd.inputs[0])
        if isinstance(off, bpy.types.NodeSocket):
            self.nt.links.new(off, nd.inputs[1])
        else:
            nd.inputs[1].default_value = off
        return nd.outputs[0]

    def snoise(self, scale, detail=8, rough=.55, dist=0.0, seed=(0, 0, 0), lac=2.0, vec=None):
        nd = self.n('ShaderNodeTexNoise', noise_dimensions='3D')
        self.nt.links.new(self.vadd(vec or self.dir(), seed), nd.inputs['Vector'])
        nd.inputs['Scale'].default_value = scale; nd.inputs['Detail'].default_value = detail
        nd.inputs['Roughness'].default_value = rough; nd.inputs['Distortion'].default_value = dist
        nd.inputs['Lacunarity'].default_value = lac
        return nd

    def svoronoi(self, scale, seed=(0, 0, 0), out='Distance'):
        nd = self.n('ShaderNodeTexVoronoi', voronoi_dimensions='3D')
        self.nt.links.new(self.vadd(self.dir(), seed), nd.inputs['Vector'])
        nd.inputs['Scale'].default_value = scale
        return nd.outputs[out]

    def smooth(self, x, a, b):
        nd = self.n('ShaderNodeMapRange', interpolation_type='SMOOTHSTEP')
        self.nt.links.new(x, nd.inputs['Value'])
        nd.inputs['From Min'].default_value = a; nd.inputs['From Max'].default_value = b
        return nd.outputs['Result']

    def rgb(self, r, g, b):
        nd = self.n('ShaderNodeCombineColor')
        for i, v in enumerate((r, g, b)):
            if isinstance(v, bpy.types.NodeSocket):
                self.nt.links.new(v, nd.inputs[i])
            else:
                nd.inputs[i].default_value = v
        return nd.outputs[0]


# ------------------------------------------------------------------ the shared fields
def fields(g):
    """Continent shape, mountains, moisture, latitude terms; cached on the builder."""
    if getattr(g, 'F', None):
        return g.F
    warp = g.snoise(1.1, 4, .5, 0, (11, 3, 7)).outputs['Color']
    wv = g.n('ShaderNodeVectorMath', operation='SCALE'); g.nt.links.new(warp, wv.inputs[0]); wv.inputs['Scale'].default_value = .55
    v = g.vadd(g.dir(), wv.outputs[0])
    big = g.snoise(.9, 3, .5, 0, (2, 9, 4), vec=v).outputs['Fac']
    det = g.snoise(2.6, 14, .6, 0, (5, 1, 8), vec=v).outputs['Fac']
    cont = g.math('ADD', g.math('MULTIPLY', big, .62), g.math('MULTIPLY', det, .42))       # ~0.2..0.85
    land = g.smooth(cont, .555, .561)
    # ridged mountains following the continents' spines
    rn = g.snoise(5.5, 10, .55, 0, (8, 8, 2), vec=v).outputs['Fac']
    ridge = g.math('SUBTRACT', 1.0, g.math('ABSOLUTE', g.math('SUBTRACT', g.math('MULTIPLY', rn, 2.0), 1.0)))
    ridge = g.math('POWER', ridge, 3.0)
    inland = g.smooth(cont, .58, .68)
    mount = g.math('MULTIPLY', ridge, inland)
    height = g.math('ADD', g.math('MULTIPLY', g.smooth(cont, .555, .78), .55), g.math('MULTIPLY', mount, .45))
    # moisture: wet tropics, dry horse latitudes, wet mid latitudes, plus noise and rain shadow from mountains
    lat = g.lat()
    band = g.math('COSINE', g.math('MULTIPLY', lat, 6.0))
    mo = g.snoise(3.2, 8, .55, .4, (3, 3, 3)).outputs['Fac']
    moist = g.math('ADD', g.math('ADD', g.math('MULTIPLY', mo, 1.0), g.math('MULTIPLY', band, .22)), g.math('MULTIPLY', mount, -.25))
    alat = g.alat()
    jit = g.math('MULTIPLY', g.snoise(7, 6, .6, 0, (1, 5, 9)).outputs['Fac'], .22)
    ice = g.smooth(g.math('ADD', alat, jit), 1.36, 1.42)                       # ~72-76 degrees with a ragged edge
    cold = g.smooth(g.math('ADD', alat, jit), 1.05, 1.25)
    g.F = dict(cont=cont, land=land, mount=mount, height=height, moist=moist, ice=ice, cold=cold, alat=alat, v=v)
    return g.F


def day(g):
    F = fields(g)
    # ocean: abyss -> deep -> shelf -> coastal shallows
    ocean = g.ramp(F['cont'], [(.42, '#041634'), (.52, '#062654'), (.545, '#0b3a6a'), (.553, '#156379'), (.558, '#2a8f92')])
    fine = g.snoise(40, 6, .6, 0, (4, 4, 4)).outputs['Fac']
    # land biomes by moisture: desert -> savanna -> grassland -> forest -> rainforest
    m = g.math('ADD', F['moist'], g.math('MULTIPLY', fine, .12))
    biome = g.ramp(m, [(.38, '#c4a46c'), (.46, '#a78a55'), (.53, '#7d8344'), (.6, '#4f6b30'), (.68, '#2d4f22'), (.78, '#1d3b1a')])
    # dunes / rock streaks
    streak = g.ramp(g.snoise(22, 8, .65, .6, (6, 2, 1)).outputs['Fac'], [(.3, '#d8bf8a'), (.7, '#8a6a44')])
    desert = g.smooth(m, .48, .38)
    biome = g.mix(biome, streak, g.math('MULTIPLY', desert, .35))
    tundra = g.mix(biome, (.42, .4, .33), F['cold'])
    rock = g.mix(tundra, (.38, .33, .28), g.smooth(F['mount'], .15, .4))
    snow = g.mix(rock, (.92, .94, .96), g.smooth(g.math('ADD', F['mount'], g.math('MULTIPLY', F['cold'], .35)), .62, .8))
    land_c = g.mix(snow, g.mix(snow, (.0, .0, .0), .0), 0.0)
    col = g.mix(ocean, land_c, F['land'])
    # rivers/lakes speckle and fine texture
    col = g.mix(col, (.05, .12, .2), g.math('MULTIPLY', g.smooth(g.snoise(60, 4, .5, 0, (9, 1, 1)).outputs['Fac'], .72, .78), g.math('MULTIPLY', F['land'], .5)))
    col = g.mix(col, (.93, .96, 1.0), F['ice'])
    return col


def clouds(g):
    v = fields(g)['v']
    swirl = g.snoise(1.8, 3, .5, 1.1, (1, 1, 1)).outputs['Color']
    sv = g.n('ShaderNodeVectorMath', operation='SCALE'); g.nt.links.new(swirl, sv.inputs[0]); sv.inputs['Scale'].default_value = .35
    w = g.vadd(g.dir(), sv.outputs[0])
    a = g.snoise(3.5, 12, .62, 0, (7, 3, 5), vec=w).outputs['Fac']
    b = g.snoise(9, 8, .55, .1, (2, 7, 1), vec=w).outputs['Fac']
    c = g.math('ADD', g.math('MULTIPLY', a, .8), g.math('MULTIPLY', b, .28))
    lat = g.lat()
    # more cloud along the equatorial convergence and the storm tracks, less over the subtropics
    band = g.math('MULTIPLY', g.math('COSINE', g.math('MULTIPLY', lat, 6.0)), .07)
    c = g.math('ADD', c, band)
    cov = g.smooth(c, .55, .8)
    wisps = g.math('MULTIPLY', g.smooth(b, .55, .8), .35)
    d = g.math('MAXIMUM', cov, wisps)
    return g.rgb(d, d, d)


def night(g):
    F = fields(g)
    pop = g.smooth(g.snoise(4, 6, .6, 0, (5, 5, 1)).outputs['Fac'], .42, .62)
    habitable = g.math('MULTIPLY', g.math('MULTIPLY', F['land'], g.math('SUBTRACT', 1.0, F['cold'])), g.math('SUBTRACT', 1.0, g.smooth(F['mount'], .2, .4)))
    coast = g.smooth(F['cont'], .62, .56)                      # people live by the sea
    dens = g.math('MULTIPLY', habitable, g.math('ADD', g.math('MULTIPLY', pop, .8), g.math('MULTIPLY', coast, .5)))
    city = g.smooth(g.svoronoi(70, (3, 1, 2)), .2, .03)
    towns = g.smooth(g.svoronoi(220, (8, 2, 6)), .16, .0)
    lights = g.math('MULTIPLY', g.math('ADD', city, g.math('MULTIPLY', towns, .45)), dens)
    lights = g.math('MINIMUM', g.math('MULTIPLY', lights, 2.2), 1.0)
    return g.rgb(lights, g.math('MULTIPLY', lights, .72), g.math('MULTIPLY', lights, .38))


def maps(g):
    F = fields(g)
    return g.rgb(F['height'], g.math('SUBTRACT', 1.0, F['land']), F['ice'])


def bake(plane, name, fn, w, h):
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    for nd in list(nt.nodes):
        if nd.type != 'OUTPUT_MATERIAL':
            nt.nodes.remove(nd)
    outn = [nd for nd in nt.nodes if nd.type == 'OUTPUT_MATERIAL'][0]
    g = Sphere(nt)
    img = bpy.data.images.new(name, w, h)
    if name != 'earth_day':
        img.colorspace_settings.name = 'Non-Color'
    em = g.n('ShaderNodeEmission')
    nt.links.new(fn(g), em.inputs['Color'])
    nt.links.new(em.outputs[0], outn.inputs['Surface'])
    tn = nt.nodes.new('ShaderNodeTexImage'); tn.image = img; nt.nodes.active = tn
    plane.data.materials.clear(); plane.data.materials.append(m)
    bpy.ops.object.select_all(action='DESELECT'); plane.select_set(True)
    bpy.context.view_layer.objects.active = plane
    bpy.ops.object.bake(type='EMIT')
    path = os.path.join(bl.TEXTURES, name + '.jpg')
    sc = bpy.context.scene
    sc.render.image_settings.file_format = 'JPEG'; sc.render.image_settings.quality = 92
    img.save_render(path)
    print('[planet]', os.path.basename(path), w, 'x', h)


def main():
    p = setup()
    k = 4 if FAST else 1
    bake(p, 'earth_day', day, 4096 // k, 2048 // k)
    bake(p, 'earth_clouds', clouds, 4096 // k, 2048 // k)
    bake(p, 'earth_night', night, 2048 // k, 1024 // k)
    bake(p, 'earth_ms', maps, 2048 // k, 1024 // k)


main()
