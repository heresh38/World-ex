"""Nexus Prime: the main city hub (the owner's city art: a circular walled city round the Spire, ring districts,
an elevated ring road, the arena, the orbital dockyard, the outer gates; dark slate and gunmetal, cyan light lines,
violet crystal glow, lit windows; mountains all round).

Every piece is its own root (origin = where it stands, +X = outward / its front), so the Unreal level script places
and repeats them (Content/Python/make_nexus_map.py):

  NX_spire, NX_spire_ring_low, NX_spire_ring_high   the central hub tower (~190 m) and its two turning rings
  NX_plaza                                          the ring plaza it stands on (48 m)
  NX_wall, NX_gate                                  a 15-degree segment of the city wall (r 206-212 m) and the gates
  NX_road                                           a 20-degree segment of the elevated ring road (r 120-130 m)
  NX_tower_a, NX_tower_b, NX_block_c                district buildings (stone, gunmetal, lit window grids)
  NX_hall_d, NX_dome_e, NX_factory_f                market hall, research dome with dish, industrial works
  NX_arena, NX_pad                                  the arena bowl, a dockyard landing pad
  NX_beacon                                         a fast-travel beacon (obelisk + floating crystal)
  NX_crystal_a/b/c, NX_lamp                         violet crystal clusters, street lamp
  NX_ground, NX_land                                the city floor (r 206 m) and the land round it up to the mountains

Materials (names are an API for the Unreal import): nx_stone, nx_panel, nx_trim, nx_window (lit, emissive map),
nx_paving, nx_rock, nx_glow_cyan, nx_glow_violet, nx_glow_warm, nx_crystal. Textures: nexus_textures.py.

Run: blender --background --python tools/blender/nexus.py   -> assets/models/nexus.glb
"""
import bpy, bmesh, math, os, sys, random
from mathutils import Vector, Matrix
sys.path.insert(0, os.path.dirname(__file__))
import bl

TAU = 2 * math.pi


# ------------------------------------------------------------------ materials
def textured(name, tex, col='#ffffff', metal=0.0, rough=.6):
    return bl.mat(name, col, metal, rough, image=tex + '_c.jpg', normal=tex + '_n.jpg')


def window_mat():
    """Facade glass: the window grid is both the colour and the emissive map (lit rooms glow)."""
    m = bl.mat('nx_window', '#ffffff', .3, .18, image='nx_window_c.jpg', normal='nx_window_n.jpg')
    nt = m.node_tree
    b = nt.nodes['Principled BSDF']
    img = next(n for n in nt.nodes if n.type == 'TEX_IMAGE' and n.image and n.image.name.startswith('nx_window_c'))
    nt.links.new(img.outputs['Color'], b.inputs['Emission Color'])
    b.inputs['Emission Strength'].default_value = 2.5
    return m


def mats():
    return {
        'stone': textured('nx_stone', 'nx_stone', '#ffffff', 0, .8),
        'panel': textured('nx_panel', 'nx_panel', '#ffffff', .7, .45),
        'trim': textured('nx_trim', 'nx_trim', '#ffffff', 1.0, .3),
        'window': window_mat(),
        'paving': textured('nx_paving', 'nx_paving', '#ffffff', 0, .75),
        'rock': textured('nx_rock', 'nx_rock', '#ffffff', 0, .9),
        'cyan': bl.mat('nx_glow_cyan', '#2fd8ff', 0, .4, emit='#2fd8ff', strength=8),
        'violet': bl.mat('nx_glow_violet', '#9b5cff', 0, .4, emit='#9b5cff', strength=8),
        'warm': bl.mat('nx_glow_warm', '#ffc27a', 0, .4, emit='#ffc27a', strength=6),
        'crystal': bl.mat('nx_crystal', '#6a2ee0', .1, .12, emit='#8f4dff', strength=3),
    }


ORDER = ['stone', 'panel', 'trim', 'window', 'paving', 'rock', 'cyan', 'violet', 'warm', 'crystal']


# ------------------------------------------------------------------ bmesh building blocks
class Kit:
    """Collects geometry for one piece; every face carries a material slot from ORDER."""

    def __init__(self):
        self.bm = bmesh.new()

    def face(self, vs, mat):
        f = self.bm.faces.new(vs)
        f.material_index = ORDER.index(mat)
        return f

    def lathe(self, prof, segs, mat, a0=0.0, a1=TAU, rot=0.0, z=0.0, at=(0, 0)):
        """Revolve (r, z) points about Z. segs=8 gives octagons; rot turns the whole thing."""
        closed = abs((a1 - a0) - TAU) < 1e-6
        n = segs if closed else segs + 1
        rings = []
        for r, zz in prof:
            ring = []
            for i in range(n):
                a = a0 + (a1 - a0) * i / segs + rot
                ring.append(self.bm.verts.new((at[0] + r * math.cos(a), at[1] + r * math.sin(a), zz + z)))
            rings.append(ring)
        for k in range(len(rings) - 1):
            A, B = rings[k], rings[k + 1]
            for i in range(segs):
                j = (i + 1) % n if closed else i + 1
                vs = [A[i], A[j], B[j], B[i]]
                if len({v.index for v in vs}) < 4 and False:
                    continue
                try:
                    self.face(vs, mat)
                except ValueError:
                    pass
        return rings

    def block(self, c, size, mat, rotz=0.0, sides=None, top=None):
        """Box: c = centre (x, y, z), size = (sx, sy, sz); sides / top override the material of the walls / top."""
        hx, hy, hz = size[0] / 2, size[1] / 2, size[2] / 2
        R = Matrix.Rotation(rotz, 3, 'Z')
        pts = [Vector(c) + R @ Vector((sx * hx, sy * hy, sz * hz)) for sz in (-1, 1) for sy in (-1, 1) for sx in (-1, 1)]
        v = [self.bm.verts.new(p) for p in pts]
        walls = sides or mat
        self.face([v[0], v[2], v[3], v[1]], mat)                    # bottom
        self.face([v[4], v[5], v[7], v[6]], top or mat)             # top
        self.face([v[0], v[1], v[5], v[4]], walls)
        self.face([v[1], v[3], v[7], v[5]], walls)
        self.face([v[3], v[2], v[6], v[7]], walls)
        self.face([v[2], v[0], v[4], v[6]], walls)

    def prism(self, poly, z0, z1, mat, rotz=0.0, at=(0, 0, 0), plane='xy', top=None):
        """Extrude a 2D polygon (counter-clockwise). plane 'xy': footprint, extruded up; 'xz': side profile in the
        X-Z plane extruded along Y from z0 to z1."""
        R = Matrix.Rotation(rotz, 3, 'Z')
        base, cap = [], []
        for x, y in poly:
            if plane == 'xy':
                p0, p1 = Vector((x, y, z0)), Vector((x, y, z1))
            else:
                p0, p1 = Vector((x, z0, y)), Vector((x, z1, y))
            base.append(self.bm.verts.new(R @ p0 + Vector(at)))
            cap.append(self.bm.verts.new(R @ p1 + Vector(at)))
        n = len(poly)
        self.face(base[::-1] if plane == 'xy' else base, mat)
        self.face(cap if plane == 'xy' else cap[::-1], top or mat)
        for i in range(n):
            j = (i + 1) % n
            vs = [base[i], base[j], cap[j], cap[i]]
            self.face(vs if plane == 'xy' else vs[::-1], mat)

    def arc(self, R0, R1, z0, z1, a0, a1, segs, mat, inner=None, top=None):
        """Annular sector solid (curved wall / ring / deck)."""
        rings = []
        for r, z in ((R0, z0), (R1, z0), (R1, z1), (R0, z1)):
            rings.append([self.bm.verts.new((r * math.cos(a0 + (a1 - a0) * i / segs), r * math.sin(a0 + (a1 - a0) * i / segs), z))
                          for i in range(segs + 1)])
        full = abs((a1 - a0) - TAU) < 1e-6
        mats_ = [mat, mat, top or mat, inner or mat]   # bottom, outer, top, inner
        for k in range(4):
            A, B = rings[k], rings[(k + 1) % 4]
            for i in range(segs):
                self.face([A[i], A[i + 1], B[i + 1], B[i]], mats_[k])
        if not full:
            self.face([rings[k][0] for k in range(4)][::-1], mat)
            self.face([rings[k][segs] for k in range(4)], mat)

    def done(self, name, ms, uv=4.0):
        me = bpy.data.meshes.new(name)
        bmesh.ops.remove_doubles(self.bm, verts=self.bm.verts, dist=1e-4)
        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces)
        self.bm.to_mesh(me)
        self.bm.free()
        o = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(o)
        for k in ORDER:
            me.materials.append(ms[k])
        # drop unused slots so every piece only carries its own materials
        used = {p.material_index for p in me.polygons}
        remap = {}
        keep = [i for i in range(len(ORDER)) if i in used]
        for new, old in enumerate(keep):
            remap[old] = new
        idx = [remap[p.material_index] for p in me.polygons]
        for i in reversed(range(len(ORDER))):
            if i not in used:
                me.materials.pop(index=i)
        me.polygons.foreach_set('material_index', idx)
        me.update()
        bl.uv_box(o, uv)
        for p in me.polygons:
            p.use_smooth = False
        return o


# ------------------------------------------------------------------ pieces
def spire(ms):
    k = Kit()
    prof = [(22, 0), (22, 6), (19, 8), (19, 30), (16, 33), (16, 60), (13, 63), (13, 95), (10, 98), (10, 125), (7, 128), (7, 150), (3.2, 160)]
    rot = math.pi / 8
    k.lathe(prof, 8, 'stone', rot=rot)
    k.lathe([(0, 0), (22, 0)], 8, 'stone', rot=rot)                       # floor cap
    # trim bands at every setback, lit strips up the octagon's corners, a glowing seam per tier
    tiers = [(8, 30, 19), (33, 60, 16), (63, 95, 13), (98, 125, 10), (128, 150, 7)]
    for z0, z1, r in tiers:
        k.lathe([(r + .5, z1 - 1.2), (r + .5, z1), (r - .2, z1 + .4)], 8, 'panel', rot=rot)
        for i in range(8):
            a = rot + i * TAU / 8
            k.block((math.cos(a) * (r + .05), math.sin(a) * (r + .05), (z0 + z1) / 2), (.7, .7, (z1 - z0) - 2.5), 'cyan', rotz=a)
    # four great buttress fins (side profile in the X-Z plane, 3 m thick), with a lit edge
    fin = [(15, 0), (31, 0), (30, 5), (24, 30), (17, 62), (13, 92), (12, 92), (12, 0)]
    for i in range(4):
        a = i * TAU / 4
        k.prism(fin, -1.5, 1.5, 'stone', rotz=a, plane='xz')
        k.prism([(30.2, 5), (31.2, 0), (31.3, .4), (30.6, 5.4), (24.5, 30.4), (17.4, 62.4), (17, 62)], -.4, .4, 'cyan', rotz=a, plane='xz')
    # crown: spikes round the top tier and the needle
    for i in range(8):
        a = rot + i * TAU / 8
        k.prism([(-.8, -.8), (.8, -.8), (.8, .8), (-.8, .8)], 150, 157, 'trim', rotz=a, at=(math.cos(a) * 6.6, math.sin(a) * 6.6, 0))
        k.lathe([(0, 157), (.8, 157), (0, 163)], 4, 'trim', at=(math.cos(a) * 6.6, math.sin(a) * 6.6))
    k.lathe([(3.2, 160), (1.2, 182), (.2, 194), (0, 195)], 8, 'trim', rot=rot)
    k.lathe([(1.5, 170), (1.7, 171), (1.5, 172)], 8, 'cyan', rot=rot)
    out = [k.done('NX_spire', ms, uv=6)]
    # the two turning rings with their spokes
    for name, R, z, w in (('NX_spire_ring_low', 40, 70, 2.6), ('NX_spire_ring_high', 28, 118, 2.0)):
        k = Kit()
        k.arc(R - w, R, z, z + w, 0, TAU, 72, 'panel', inner='trim')
        k.arc(R - w - .25, R - w, z + w * .3, z + w * .7, 0, TAU, 72, 'cyan')
        k.arc(R, R + .2, z + w * .45, z + w * .55, 0, TAU, 72, 'violet')
        core = 13 if z < 100 else 10
        for i in range(4):
            a = i * TAU / 4 + math.pi / 4
            L = (R - w) - core
            mid = core + L / 2
            k.block((math.cos(a) * mid, math.sin(a) * mid, z + w / 2), (L, 1.2, 1.2), 'panel', rotz=a)
        out.append(k.done(name, ms, uv=4))
    return out


def plaza(ms):
    k = Kit()
    k.lathe([(0, .6), (30, .6), (30, .35), (34, .35), (34, .1), (48, .1), (48, -.4)], 96, 'paving')
    k.arc(29.6, 30.0, .6, .63, 0, TAU, 96, 'cyan')
    k.arc(47.4, 47.7, .1, .13, 0, TAU, 96, 'violet')
    for i in range(12):                                                    # lit bollards round the edge
        a = i * TAU / 12
        k.lathe([(.35, .1), (.35, 1.0), (.25, 1.1), (0, 1.1)], 8, 'panel', at=(math.cos(a) * 46, math.sin(a) * 46))
        k.lathe([(.36, .75), (.36, .9)], 8, 'cyan', at=(math.cos(a) * 46, math.sin(a) * 46))
    return k.done('NX_plaza', ms, uv=6)


def wall(ms):
    """A 15-degree arc of the city wall, centred on +X."""
    k = Kit()
    a0, a1 = -math.radians(7.5), math.radians(7.5)
    k.arc(206, 212, 0, 16, a0, a1, 6, 'stone', inner='stone', top='paving')
    k.arc(205.85, 206, 11.6, 12.2, a0, a1, 6, 'cyan')                      # light line on the city side
    for i in range(6):                                                     # merlons on the outer edge
        a = a0 + (a1 - a0) * (i + .5) / 6
        k.block((math.cos(a) * 211.4, math.sin(a) * 211.4, 17.2), (1.2, 4.0, 2.4), 'stone', rotz=a)
    for a in (a0 + .01, a1 - .01):                                         # buttresses outside
        k.prism([(212, 0), (219, 0), (212, 15)], -1.6, 1.6, 'stone', rotz=a, plane='xz')
    k.block((211.2, 0, 8.0), (.4, 6.0, 9.0), 'panel', rotz=0)               # a hull plate in the middle
    return k.done('NX_wall', ms, uv=6)


def gate(ms):
    k = Kit()
    for y in (-14, 14):
        k.lathe([(7.5, 0), (7.5, 30), (6, 31), (6, 34), (0, 38)], 8, 'stone', at=(209, y), rot=math.pi / 8)
        k.lathe([(7.6, 24), (7.6, 25)], 8, 'cyan', at=(209, y), rot=math.pi / 8)
    k.block((209, 0, 22), (8, 21, 6), 'stone')                              # the arch beam
    k.block((205, 0, 22), (.3, 18, 1.0), 'cyan')
    k.prism([(-4, 0), (4, 0), (0, 7)], 204.6, 204.9, 'violet', plane='xz', rotz=math.pi / 2)  # the emblem
    k.block((209, 0, .1), (10, 21, .2), 'paving')
    return k.done('NX_gate', ms, uv=6)


def road(ms):
    """A 20-degree arc of the elevated ring road, centred on +X."""
    k = Kit()
    a0, a1 = -math.radians(10), math.radians(10)
    k.arc(120, 130, 9, 10, a0, a1, 8, 'panel', top='paving')
    for R in (120, 129.7):
        k.arc(R, R + .3, 10, 11.1, a0, a1, 8, 'trim')
        k.arc(R + .05, R + .25, 10.95, 11.05, a0, a1, 8, 'cyan')
    for a in (-math.radians(5), math.radians(5)):
        k.block((math.cos(a) * 125, math.sin(a) * 125, 4.5), (2.6, 2.6, 9), 'stone', rotz=a)
        k.block((math.cos(a) * 125, math.sin(a) * 125, 8.6), (5.0, 3.4, .8), 'panel', rotz=a)
    return k.done('NX_road', ms, uv=4)


def tower(ms, name, tiers, seed, spike=0.0, glow='cyan'):
    """Stacked setback blocks: lit window facades, stone corner piers, a gunmetal band at every setback."""
    rnd = random.Random(seed)
    k = Kit()
    z = 0.0
    for w, d, h in tiers:
        k.block((0, 0, z + h / 2), (w, d, h), 'stone', sides='window', top='panel')
        for sx in (-1, 1):
            for sy in (-1, 1):
                k.block((sx * w / 2, sy * d / 2, z + h / 2), (1.6, 1.6, h + .2), 'stone')
        k.block((0, 0, z + h - .4), (w + .8, d + .8, .8), 'panel')
        k.block((w / 2 + .82, 0, z + h - .4), (.06, d * .7, .2), glow)       # a light line on the front band
        z += h
    if spike:
        k.lathe([(1.2, z), (.6, z + spike), (0, z + spike + 1)], 4, 'trim')
        k.block((0, 0, z + spike + 1.2), (.5, .5, .5), 'warm')
    else:
        k.block((rnd.uniform(-2, 2), rnd.uniform(-2, 2), z + 1.5), (4, 3, 3), 'panel')
    k.block((tiers[0][0] / 2 + .05, 0, 2.2), (.2, tiers[0][1] * .4, 4.2), 'panel')   # the door
    return k.done(name, ms, uv=8)


def hall(ms):
    k = Kit()
    k.block((0, 0, 5), (30, 20, 10), 'stone', sides='window', top='panel')
    k.lathe([(9, 10), (9, 11), (8, 14), (5.5, 17.5), (2, 19.2), (0, 19.5)], 24, 'panel', at=(0, 0))
    k.lathe([(9.05, 10.6), (9.05, 11.0)], 24, 'violet')
    for x, c in ((-9, 'violet'), (0, 'cyan'), (9, 'warm')):                 # market awnings and lit signs
        k.prism([(0, 4), (4, 4), (4, 4.3), (0, 5.2)], x - 4, x + 4, 'panel', plane='xz', rotz=0, at=(15, 0, 0))
        k.block((15.3, x, 7.4), (.2, 6, 1.2), c, rotz=0)
    return k.done('NX_hall_d', ms, uv=8)


def dome(ms):
    k = Kit()
    k.lathe([(16, 0), (16, 4), (15, 9), (12, 14), (7, 17.5), (0, 18.6)], 32, 'panel')
    k.lathe([(16.1, 3.4), (16.1, 4.0)], 32, 'cyan')
    k.lathe([(1, 18), (1, 30)], 8, 'trim')
    # the dish on its mast
    k.lathe([(0, 30.5), (2.5, 30.7), (5, 31.6), (6.5, 32.6), (6.4, 32.8), (4.9, 31.85), (2.4, 30.95), (0, 30.75)], 24, 'trim')
    k.block((0, 0, 34), (.4, .4, 2.5), 'violet')
    return k.done('NX_dome_e', ms, uv=6)


def factory(ms):
    k = Kit()
    k.block((0, 0, 6), (30, 24, 12), 'panel', sides='stone', top='panel')
    for x, y in ((-8, -6), (0, -6), (8, -6)):
        k.lathe([(2.2, 12), (2.0, 34), (2.4, 35), (2.4, 36), (1.6, 36)], 12, 'stone', at=(x, y))
        k.lathe([(2.42, 32), (2.42, 33)], 12, 'warm', at=(x, y))
    for y in (-10, 10):
        k.block((0, y, 13), (28, 1.4, 1.4), 'trim')
    k.block((15.1, 0, 5), (.2, 10, 8), 'panel')
    k.block((15.2, 0, 9.4), (.1, 10, .3), 'warm')
    return k.done('NX_factory_f', ms, uv=8)


def arena(ms):
    k = Kit()
    prof = [(64, 0), (64, 20), (62, 22), (58, 22), (56, 20), (36, 5), (32, 1.5), (0, 1.5)]
    k.lathe(prof, 64, 'stone')
    k.arc(62, 62.3, 20.6, 21.2, 0, TAU, 64, 'violet')
    k.arc(31.7, 32, 1.5, 1.8, 0, TAU, 64, 'cyan')
    for i in range(16):                                                     # outer arches as lit recesses
        a = i * TAU / 16
        k.block((math.cos(a) * 64.05, math.sin(a) * 64.05, 7), (.2, 6, 10), 'window', rotz=a)
    return k.done('NX_arena', ms, uv=8)


def pad(ms):
    k = Kit()
    k.lathe([(0, 1.2), (20, 1.2), (22, .8), (22, 0)], 48, 'panel')
    k.arc(18.3, 18.8, 1.2, 1.25, 0, TAU, 48, 'cyan')
    k.arc(6, 6.4, 1.2, 1.25, 0, TAU, 48, 'warm')
    for i in range(4):
        a = i * TAU / 4 + math.pi / 4
        k.lathe([(.3, 1.2), (.3, 3.5), (0, 3.6)], 6, 'panel', at=(math.cos(a) * 21, math.sin(a) * 21))
        k.lathe([(.32, 3.0), (.32, 3.4)], 6, 'warm', at=(math.cos(a) * 21, math.sin(a) * 21))
    return k.done('NX_pad', ms, uv=6)


def beacon(ms):
    k = Kit()
    k.lathe([(1.8, 0), (1.8, .5), (1.2, .8), (.8, 5.5), (.5, 6.2), (0, 6.4)], 8, 'stone', rot=math.pi / 8)
    k.lathe([(.82, 2), (.82, 4.6)], 8, 'cyan', rot=math.pi / 8)
    k.lathe([(0, 7.4), (.9, 8.6), (0, 10.4)], 4, 'cyan')                  # the floating crystal
    return k.done('NX_beacon', ms, uv=2)


def crystal(ms, name, seed, n):
    rnd = random.Random(seed)
    k = Kit()
    for i in range(n):
        r = rnd.uniform(.25, .7); h = rnd.uniform(1.0, 3.2) * (1.6 if i == 0 else 1)
        ox, oy = (0, 0) if i == 0 else (rnd.uniform(-1.2, 1.2), rnd.uniform(-1.2, 1.2))
        rings = k.lathe([(0, -.3), (r, -.3), (r, h), (0, h + r * 1.8)], 6, 'crystal', rot=rnd.uniform(0, 1))
        tilt = Matrix.Rotation(rnd.uniform(-.45, .45), 3, 'X') @ Matrix.Rotation(rnd.uniform(-.45, .45), 3, 'Y')
        for ring in rings:
            for v in ring:
                v.co = tilt @ v.co + Vector((ox, oy, 0))
    return k.done(name, ms, uv=1.5)


def lamp(ms):
    k = Kit()
    k.lathe([(.35, 0), (.35, .4), (.15, .6), (.12, 7), (0, 7.1)], 8, 'panel')
    k.block((.9, 0, 6.9), (1.8, .25, .25), 'panel')
    k.block((1.7, 0, 6.65), (.7, .5, .2), 'warm')
    return k.done('NX_lamp', ms, uv=2)


def ground(ms):
    k = Kit()
    k.lathe([(0, 0), (206, 0)], 96, 'paving')
    return k.done('NX_ground', ms, uv=8)


def land(ms):
    """The land outside the wall: a moat drop, rolling ground, then mountains rising to ~380 m round the horizon."""
    rnd = random.Random(7)
    k = Kit()
    segs = 128
    radii = [212, 230, 260, 320, 400, 520, 680, 860, 1050, 1250, 1450, 1650]
    phase = [rnd.uniform(0, TAU) for _ in range(6)]

    def height(r, a):
        if r <= 230:
            return -4.0 if r > 214 else 0.0
        t = min(1.0, max(0.0, (r - 260) / 1200))
        ridge = sum(math.sin(a * f + phase[i]) * (1.0 / f ** .6) for i, f in enumerate((3, 5, 8, 13, 21, 34)))
        base = 2 + t * t * 300 + t * (ridge * 60 + 40)
        return base + (rnd.uniform(-1, 1) * 6 * t)
    rows = []
    for r in radii:
        rows.append([k.bm.verts.new((r * math.cos(a), r * math.sin(a), height(r, a))) for a in (i * TAU / segs for i in range(segs))])
    for j in range(len(rows) - 1):
        for i in range(segs):
            i1 = (i + 1) % segs
            k.face([rows[j][i], rows[j][i1], rows[j + 1][i1], rows[j + 1][i]], 'rock')
    return k.done('NX_land', ms, uv=24)


def main():
    bl.reset()
    ms = mats()
    pieces = []
    pieces += spire(ms)
    pieces += [plaza(ms), wall(ms), gate(ms), road(ms)]
    pieces += [tower(ms, 'NX_tower_a', [(18, 18, 30), (14, 14, 22), (10, 10, 16)], 1, spike=10),
               tower(ms, 'NX_tower_b', [(26, 16, 20), (22, 13, 18)], 2, glow='violet'),
               tower(ms, 'NX_block_c', [(40, 14, 14)], 3, glow='warm')]
    pieces += [hall(ms), dome(ms), factory(ms), arena(ms), pad(ms), beacon(ms), lamp(ms)]
    pieces += [crystal(ms, 'NX_crystal_a', 11, 7), crystal(ms, 'NX_crystal_b', 12, 4), crystal(ms, 'NX_crystal_c', 13, 11)]
    pieces += [ground(ms), land(ms)]
    tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in pieces)
    print('[nexus] %d pieces, %d triangles' % (len(pieces), tris))
    bl.export('nexus.glb')


if __name__ == '__main__':
    main()
