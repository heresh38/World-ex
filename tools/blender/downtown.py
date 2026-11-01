"""New Meridian downtown kit: every downtown building design, its low-detail LOD, and the street kit.

Writes
  downtown.glb         buildings: root DT_<name> (hero) + DT_<name>_lod (low detail) for each design in DESIGNS
  downtown_street.glb  skywalks, transit platform / track / catenary / tram, tower crane (mast + slewing jib), street
                       furniture (kiosk, shelter, planter, cafe set, bollards, signals, bins, banners, string lights,
                       sculpture, bike rack)
Each root carries extras.dt (JSON): w / d / h (metres, three space: w along x, d along z), kind, era and AABB colliders
`col` [[x0, y0, z0, x1, y1, z1], ...] in three space relative to the root (fronts face three +z, i.e. Blender -Y).
Meshes are built directly from vertex lists (no operators) so the script stays quick. Facade UVs: u = metres along the
wall / tile width with whole bays centred on each wall, v = metres above the facade base / tile height, so the painted
floors of downtown_textures.py line up with the geometry (TILE gives each set's tile size and bay width).
Material names are an API for earth.js / meridian/downtown.js: dt_* facades get their window glow from the red channel of
their _m map, glass names get env reflections, dt_lattice*/dt_net* are cut-outs, dt_glow* are emissive.
Usage: blender --background --python tools/blender/downtown.py [-- --fast]   (--fast skips re-painting the textures)
       DT_PREVIEW=<dir> also writes one GLB per design for preview.py.
"""
import bpy, math, os, sys, json
from mathutils import Vector, Matrix
sys.path.insert(0, os.path.dirname(__file__))
import bl

FAST = '--fast' in sys.argv
TEX = bl.TEXTURES
TAU = math.tau

# facade tile sets: (tile width m, tile height m, bay width m)
TILE = {
    'curtain': (12.0, 16.0, 1.5), 'ribbon': (12.0, 15.2, 1.5), 'precast': (12.0, 15.2, 3.0), 'punched': (13.6, 12.8, 3.4),
    'brick': (14.4, 16.8, 3.6), 'stone': (16.0, 9.2, 4.0), 'derelict': (14.4, 16.0, 3.6), 'shop': (40.0, 5.0, 5.0),
}


# ---------------------------------------------------------------- materials
def tmat(name, tex, tint='#ffffff', rough=.8, metal=0.0, normal=True, aux=True, alpha=None):
    """Textured material: colour map x tint, optional normal map and aux map (G roughness, B metalness)."""
    if name in bl._MATS:
        return bl._MATS[name]
    m = bpy.data.materials.new(name)
    nt = m.node_tree; b = nt.nodes.get('Principled BSDF')
    b.inputs['Roughness'].default_value = rough; b.inputs['Metallic'].default_value = metal
    ext = '.png' if alpha else '_c.jpg'
    tn = nt.nodes.new('ShaderNodeTexImage'); tn.image = bpy.data.images.load(os.path.join(TEX, tex + ext), check_existing=True)
    mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'; mix.blend_type = 'MULTIPLY'
    mix.inputs['Factor'].default_value = 1.0; mix.inputs[7].default_value = (*bl.hexrgb(tint), 1)
    nt.links.new(tn.outputs['Color'], mix.inputs[6]); nt.links.new(mix.outputs[2], b.inputs['Base Color'])
    if normal and os.path.exists(os.path.join(TEX, tex + '_n.jpg')):
        nn = nt.nodes.new('ShaderNodeTexImage'); nn.image = bpy.data.images.load(os.path.join(TEX, tex + '_n.jpg'), check_existing=True)
        nn.image.colorspace_settings.name = 'Non-Color'
        nm = nt.nodes.new('ShaderNodeNormalMap'); nt.links.new(nn.outputs['Color'], nm.inputs['Color']); nt.links.new(nm.outputs['Normal'], b.inputs['Normal'])
    if aux and os.path.exists(os.path.join(TEX, tex + '_m.jpg')):
        an = nt.nodes.new('ShaderNodeTexImage'); an.image = bpy.data.images.load(os.path.join(TEX, tex + '_m.jpg'), check_existing=True)
        an.image.colorspace_settings.name = 'Non-Color'
        sp = nt.nodes.new('ShaderNodeSeparateColor'); nt.links.new(an.outputs['Color'], sp.inputs[0])
        nt.links.new(sp.outputs[1], b.inputs['Roughness']); nt.links.new(sp.outputs[2], b.inputs['Metallic'])
    if alpha:
        nt.links.new(tn.outputs['Alpha'], b.inputs['Alpha'])
        try:
            m.surface_render_method = 'BLENDED'
        except Exception:
            pass
    bl._MATS[name] = m
    return m


def mats():
    M = dict(
        glass_blue=tmat('dt_glass_blue', 'dt_curtain', '#b4cdf0', .06, .85),
        glass_teal=tmat('dt_glass_teal', 'dt_curtain', '#a6e0d4', .06, .85),
        glass_silver=tmat('dt_glass_silver', 'dt_curtain', '#f2f4f8', .06, .85),
        glass_dark=tmat('dt_glass_dark', 'dt_curtain', '#8a94a6', .06, .85),
        glass_bronze=tmat('dt_glass_bronze', 'dt_curtain', '#e8b080', .06, .85),
        glass_green=tmat('dt_glass_green', 'dt_curtain', '#b8e8b0', .06, .85),
        ribbon=tmat('dt_ribbon', 'dt_ribbon'),
        precast=tmat('dt_precast', 'dt_precast'),
        precast_warm=tmat('dt_precast_warm', 'dt_precast', '#f4dcc0'),
        punched=tmat('dt_punched', 'dt_punched'),
        punched_warm=tmat('dt_punched_warm', 'dt_punched', '#f6dcbc'),
        punched_grey=tmat('dt_punched_grey', 'dt_punched', '#b4bcc6'),
        brick=tmat('dt_brick', 'dt_brick'),
        brick_dark=tmat('dt_brick_dark', 'dt_brick', '#9a8478'),
        brick_buff=tmat('dt_brick_buff', 'dt_brick', '#ffe0a0'),
        stone=tmat('dt_stone', 'dt_stone'),
        limestone=tmat('dt_limestone', 'dt_stone', '#e4e2e6'),
        derelict=tmat('dt_derelict', 'dt_derelict'),
        shop=tmat('dt_shop', 'dt_shop'),
        trim=tmat('dt_trim', 'concrete', '#e2dccf', .8, 0, aux=False),
        trim_dark=tmat('dt_trim_dark', 'concrete', '#5c5e63', .7, 0, aux=False),
        sandtrim=tmat('dt_sandtrim', 'concrete', '#e8cf9e', .85, 0, aux=False),
        granite=tmat('dt_granite', 'dt_pavers', '#9a9690', .45, 0, aux=False),
        pavers=tmat('dt_pavers', 'dt_pavers', '#d8d2c8', .8, 0, aux=False),
        roof=tmat('dt_roof', 'dt_roof', '#ffffff', .9, 0, aux=False),
        rawconc=tmat('dt_rawconc', 'dt_rawconc', '#ffffff', .85, 0, aux=False),
        hoarding=tmat('dt_hoarding', 'dt_hoarding', '#ffffff', .85, 0, aux=False),
        awning_r=tmat('dt_awning_red', 'dt_awning', '#b8302a', .9, 0, normal=False, aux=False),
        awning_g=tmat('dt_awning_green', 'dt_awning', '#2f6a48', .9, 0, normal=False, aux=False),
        awning_b=tmat('dt_awning_navy', 'dt_awning', '#2a3a62', .9, 0, normal=False, aux=False),
        lattice=tmat('dt_lattice', 'dt_lattice', '#f2b51c', .5, .3, normal=False, aux=False, alpha=True),
        lattice_g=tmat('dt_lattice_galv', 'dt_lattice', '#a8acb0', .45, .7, normal=False, aux=False, alpha=True),
        net=tmat('dt_net_green', 'dt_net', '#3a7a52', .9, 0, normal=False, aux=False, alpha=True),
        net_o=tmat('dt_net_orange', 'dt_net', '#e8742a', .9, 0, normal=False, aux=False, alpha=True),
        metal=bl.mat('dt_metal_dark', '#2a2d32', .8, .4),
        metal_l=bl.mat('dt_metal_light', '#b8bec6', .9, .28),
        bronze=bl.mat('dt_bronze', '#6a4a2a', .9, .35),
        copper=bl.mat('dt_copper', '#4f8a78', .6, .45),
        mech=bl.mat('dt_mech', '#8c9094', .5, .5),
        white=bl.mat('dt_white', '#e8e6e0', .2, .45),
        yellow=bl.mat('dt_yellow', '#e8a81c', .3, .45),
        red=bl.mat('dt_red', '#a8261e', .3, .45),
        blue=bl.mat('dt_blue', '#2a5aa8', .3, .45),
        wood=bl.mat('dt_wood', '#7a5a3e', 0, .7),
        rust=bl.mat('dt_rust', '#6a3a22', .5, .8),
        steel=bl.mat('dt_steel', '#8a9099', .9, .3),
        rubber=bl.mat('dt_rubber', '#161618', 0, .9),
        plant=bl.mat('dt_plant', '#3f6e34', 0, .85),
        plant2=bl.mat('dt_plant_light', '#6a9a3a', 0, .85),
        flowers=bl.mat('dt_flowers', '#d84a6a', 0, .7),
        soil=bl.mat('dt_soil', '#3a2a1e', 0, .95),
        water=bl.mat('dt_water', '#2a6a88', .2, .05),
        glass=bl.mat('dt_glass_clear', '#9fc6d8', 0.0, .05, alpha=.28),
        glass_rail=bl.mat('dt_glass_rail', '#a8d0dc', 0.0, .05, alpha=.35),
        tinted=bl.mat('dt_glass_tinted', '#0e1418', .7, .08),
        glow=bl.mat('dt_glow_warm', '#ffd9a0', 0, .3, emit='#ffd29a', strength=5),
        glow_c=bl.mat('dt_glow_cyan', '#40e0ff', 0, .3, emit='#40e0ff', strength=6),
        glow_r=bl.mat('dt_glow_red', '#ff3326', 0, .3, emit='#ff3326', strength=8),
        glow_g=bl.mat('dt_glow_green', '#3aff7a', 0, .3, emit='#3aff7a', strength=6),
        glow_w=bl.mat('dt_glow_white', '#fff4e0', 0, .3, emit='#fff1dc', strength=4),
        glow_m=bl.mat('dt_glow_magenta', '#ff4fb0', 0, .3, emit='#ff4fb0', strength=5),
        tram=bl.mat('dt_tram_body', '#eceae4', .3, .35),
        tram_red=bl.mat('dt_tram_red', '#b0242a', .3, .35),
        car_a=bl.mat('dt_carpaint_a', '#a3121f', .6, .3), car_b=bl.mat('dt_carpaint_b', '#2a4f7a', .6, .3),
        car_c=bl.mat('dt_carpaint_c', '#d8d6d0', .6, .3), car_d=bl.mat('dt_carpaint_d', '#1c1f24', .6, .3),
    )
    return M


# Plain (untextured) materials are merged per mesh into three vertex-coloured ones so every design costs fewer draw calls:
# dt_plain (dielectric), dt_plain_metal (metals) and dt_plain_glow (emissive; the runtime multiplies the glow by the colour).
PLAIN_METAL = {'dt_metal_dark', 'dt_metal_light', 'dt_bronze', 'dt_copper', 'dt_mech', 'dt_steel'}
PLAIN_GLOW = {'dt_glow_warm', 'dt_glow_cyan', 'dt_glow_red', 'dt_glow_green', 'dt_glow_white', 'dt_glow_magenta'}
PLAIN = {'dt_white', 'dt_yellow', 'dt_red', 'dt_blue', 'dt_wood', 'dt_rust', 'dt_rubber', 'dt_plant', 'dt_plant_light', 'dt_flowers',
         'dt_soil', 'dt_water', 'dt_tram_body', 'dt_tram_red', 'dt_carpaint_a', 'dt_carpaint_b', 'dt_carpaint_c', 'dt_carpaint_d'}


def vcmat(name, metal, rough, emit=0.0):
    if name in bl._MATS:
        return bl._MATS[name]
    m = bpy.data.materials.new(name); nt = m.node_tree; b = nt.nodes.get('Principled BSDF')
    ca = nt.nodes.new('ShaderNodeVertexColor'); ca.layer_name = 'Col'
    nt.links.new(ca.outputs['Color'], b.inputs['Base Color'])
    b.inputs['Metallic'].default_value = metal; b.inputs['Roughness'].default_value = rough
    if emit:
        b.inputs['Emission Color'].default_value = (1, 1, 1, 1); b.inputs['Emission Strength'].default_value = emit
    bl._MATS[name] = m
    return m


def merged(m):
    """(material to use, vertex colour) for a plain material, else (m, None)"""
    n = m.name
    if n in PLAIN or n in PLAIN_METAL or n in PLAIN_GLOW:
        b = m.node_tree.nodes.get('Principled BSDF')
        col = tuple(b.inputs['Emission Color' if n in PLAIN_GLOW else 'Base Color'].default_value)[:3]
        tgt = vcmat('dt_plain_glow', 0, .3, 5) if n in PLAIN_GLOW else vcmat('dt_plain_metal', .85, .35) if n in PLAIN_METAL else vcmat('dt_plain', 0, .62)
        return tgt, col
    return m, None


# ---------------------------------------------------------------- mesh builder
class MB:
    """Accumulates faces (per-corner UVs, material, smooth flag) and AABB colliders; build() makes one mesh object."""

    def __init__(self):
        self.V, self.F, self.UV, self.M, self.S, self.mats, self.cols, self.extra = [], [], [], [], [], [], [], []

    def mi(self, m):
        if m not in self.mats:
            self.mats.append(m)
        return self.mats.index(m)

    def vert(self, p):
        self.V.append(tuple(p)); return len(self.V) - 1

    def face(self, pts, uvs, m, smooth=False):
        i0 = len(self.V); self.V += [tuple(p) for p in pts]
        self.F.append(tuple(range(i0, i0 + len(pts)))); self.UV.append(list(uvs)); self.M.append(self.mi(m)); self.S.append(smooth)

    def face_i(self, idx, uvs, m, smooth=True):
        self.F.append(tuple(idx)); self.UV.append(list(uvs)); self.M.append(self.mi(m)); self.S.append(smooth)

    def col(self, x0, y0, z0, x1, y1, z1):
        """collider in Blender coords -> stored in three space"""
        self.cols.append([round(min(x0, x1), 2), round(min(z0, z1), 2), round(-max(y0, y1), 2),
                          round(max(x0, x1), 2), round(max(z0, z1), 2), round(-min(y0, y1), 2)])

    def build(self, name):
        me = bpy.data.meshes.new(name)
        me.from_pydata(self.V, [], self.F)
        lay = me.uv_layers.new(name='UVMap')
        remap = [merged(m) for m in self.mats]
        final = []
        for m, _ in remap:
            if m not in final:
                final.append(m)
        vc = me.color_attributes.new('Col', 'BYTE_COLOR', 'CORNER') if any(c for _, c in remap) else None
        for p, uvs, mi, sm in zip(me.polygons, self.UV, self.M, self.S):
            m, c = remap[mi]
            p.material_index = final.index(m); p.use_smooth = sm
            for li, uv in zip(p.loop_indices, uvs):
                lay.data[li].uv = uv
                if vc is not None:
                    vc.data[li].color = (*(c or (1, 1, 1)), 1)
        for m in final:
            me.materials.append(m)
        me.validate(); me.update()
        o = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(o)
        if self.extra:
            o = bl.join([o] + self.extra, name)
        return o


def wall_uv(s0, s1, L, z0, z1, mode):
    """UVs for a wall quad covering [s0, s1] of a wall of length L between heights z0..z1."""
    if mode is None:          # world scale for trims (4 m tile)
        return [(s0 / 4, z0 / 4), (s1 / 4, z0 / 4), (s1 / 4, z1 / 4), (s0 / 4, z1 / 4)]
    tw, th, bay, zb = mode
    n = max(1, math.floor(L / bay + .01)); off = (L - n * bay) / 2
    u0, u1 = (s0 - off) / tw, (s1 - off) / tw
    return [(u0, (z0 - zb) / th), (u1, (z0 - zb) / th), (u1, (z1 - zb) / th), (u0, (z1 - zb) / th)]


def F(key, zb=0.0, scale=1.0):
    """facade UV mode for tile set key, base height zb (optionally stretched)"""
    tw, th, bay = TILE[key]
    return (tw * scale, th * scale, bay * scale, zb)


def prism(mb, poly, z0, z1, m, mode=None, top=None, smooth=False, bottom=False, walls=True, roof_tile=8.0):
    """Extrude a CCW polygon (list of (x, y)) from z0 to z1. smooth=True shares vertices around the ring (curved walls,
    continuous u). top: material for the cap (None = open)."""
    n = len(poly)
    if walls and z1 > z0:
        if smooth:
            ring = poly + [poly[0]]
            per = [0.0]
            for i in range(n):
                per.append(per[-1] + math.dist(ring[i], ring[i + 1]))
            lo = [mb.vert((x, y, z0)) for x, y in ring]; hi = [mb.vert((x, y, z1)) for x, y in ring]
            for i in range(n):
                uv = wall_uv(per[i], per[i + 1], 1e9, z0, z1, None if mode is None else (mode[0], mode[1], 1e9, mode[3]))
                if mode is None:
                    uv = [(per[i] / 4, z0 / 4), (per[i + 1] / 4, z0 / 4), (per[i + 1] / 4, z1 / 4), (per[i] / 4, z1 / 4)]
                else:
                    tw, th, _, zb = mode
                    uv = [(per[i] / tw, (z0 - zb) / th), (per[i + 1] / tw, (z0 - zb) / th), (per[i + 1] / tw, (z1 - zb) / th), (per[i] / tw, (z1 - zb) / th)]
                mb.face_i((lo[i], lo[i + 1], hi[i + 1], hi[i]), uv, m, True)
        else:
            for i in range(n):
                a, b = poly[i], poly[(i + 1) % n]
                L = math.dist(a, b)
                if L < 1e-4:
                    continue
                mb.face([(a[0], a[1], z0), (b[0], b[1], z0), (b[0], b[1], z1), (a[0], a[1], z1)], wall_uv(0, L, L, z0, z1, mode), m)
    if top is not None:
        if not walls:
            z1 += .04          # roof caps sit a hair above coplanar trim tops (no z-fighting)
        mb.face([(x, y, z1) for x, y in poly], [(x / roof_tile, y / roof_tile) for x, y in poly], top)
    if bottom:
        mb.face([(x, y, z0) for x, y in reversed(poly)], [(x / roof_tile, y / roof_tile) for x, y in reversed(poly)], bottom if not isinstance(bottom, bool) else top or m)


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def chamfer(w, d, c, cx=0.0, cy=0.0):
    x, y = w / 2, d / 2
    return [(cx - x + c, cy - y), (cx + x - c, cy - y), (cx + x, cy - y + c), (cx + x, cy + y - c), (cx + x - c, cy + y), (cx - x + c, cy + y), (cx - x, cy + y - c), (cx - x, cy - y + c)]


def notched(w, d, c, cx=0.0, cy=0.0):
    """rectangle with re-entrant (notched) corners"""
    x, y = w / 2, d / 2
    return [(cx - x + c, cy - y), (cx + x - c, cy - y), (cx + x - c, cy - y + c), (cx + x, cy - y + c), (cx + x, cy + y - c), (cx + x - c, cy + y - c),
            (cx + x - c, cy + y), (cx - x + c, cy + y), (cx - x + c, cy + y - c), (cx - x, cy + y - c), (cx - x, cy - y + c), (cx - x + c, cy - y + c)]


def circle(r, n, cx=0.0, cy=0.0, a0=0.0):
    return [(cx + math.cos(a0 + i / n * TAU) * r, cy + math.sin(a0 + i / n * TAU) * r) for i in range(n)]


def box(mb, x0, y0, z0, x1, y1, z1, m, mode=None, top=True, bottom=False, col=False):
    prism(mb, rect(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)), min(z0, z1), max(z0, z1), m, mode, top=m if top is True else (top or None), bottom=bottom)
    if col:
        mb.col(x0, y0, z0, x1, y1, z1)


def boxc(mb, cx, cy, z0, w, d, h, m, **kw):
    box(mb, cx - w / 2, cy - d / 2, z0, cx + w / 2, cy + d / 2, z0 + h, m, **kw)


def cyl(mb, cx, cy, z0, r, h, m, n=16, top=True, mode=None, r2=None, bottom=False):
    if r2 is None:
        prism(mb, circle(r, n, cx, cy), z0, z0 + h, m, mode, top=(m if top is True else top) if top else None, smooth=True, bottom=bottom)
        return
    lo = [mb.vert((cx + math.cos(i / n * TAU) * r, cy + math.sin(i / n * TAU) * r, z0)) for i in range(n + 1)]
    hi = [mb.vert((cx + math.cos(i / n * TAU) * r2, cy + math.sin(i / n * TAU) * r2, z0 + h)) for i in range(n + 1)]
    for i in range(n):
        mb.face_i((lo[i], lo[i + 1], hi[i + 1], hi[i]), [(i / n * 4, 0), ((i + 1) / n * 4, 0), ((i + 1) / n * 4, h / 4), (i / n * 4, h / 4)], m, True)
    if top and r2 > 1e-3:
        mb.face([(cx + math.cos(i / n * TAU) * r2, cy + math.sin(i / n * TAU) * r2, z0 + h) for i in range(n)], [(0, 0)] * n, m if top is True else top)


def obox(mb, p0, p1, w, h, m, up=(0, 0, 1)):
    """box of cross-section w x h from p0 to p1"""
    p0, p1 = Vector(p0), Vector(p1); ax = p1 - p0; L = ax.length
    if L < 1e-5:
        return
    ax.normalize(); u = Vector(up)
    if abs(ax.dot(u)) > .95:
        u = Vector((1, 0, 0)) if abs(ax.x) < .9 else Vector((0, 1, 0))
    s = ax.cross(u).normalized() * (w / 2); t = s.cross(ax).normalized() * (h / 2)
    c = [p0 - s - t, p0 + s - t, p0 + s + t, p0 - s + t]; d = [q + ax * L for q in c]
    for i in range(4):
        a, b = c[i], c[(i + 1) % 4]
        mb.face([a, b, d[(i + 1) % 4], d[i]], [(0, 0), (w / 4, 0), (w / 4, L / 4), (0, L / 4)], m)
    mb.face(list(reversed(c)), [(0, 0)] * 4, m); mb.face(d, [(0, 0)] * 4, m)


def blob(mb, cx, cy, cz, rx, ry, rz, m, seg=8, rings=5):
    """low-poly smooth ellipsoid (shrubs, tree crowns, bulbs)"""
    top = mb.vert((cx, cy, cz + rz)); bot = mb.vert((cx, cy, cz - rz))
    R = []
    for j in range(1, rings):
        a = math.pi * j / rings
        R.append([mb.vert((cx + math.sin(a) * math.cos(i / seg * TAU) * rx, cy + math.sin(a) * math.sin(i / seg * TAU) * ry, cz + math.cos(a) * rz)) for i in range(seg)])
    uv = [(0, 0)] * 4
    for i in range(seg):
        mb.face_i((top, R[0][i], R[0][(i + 1) % seg]), uv[:3], m)
        mb.face_i((bot, R[-1][(i + 1) % seg], R[-1][i]), uv[:3], m)
        for j in range(len(R) - 1):
            mb.face_i((R[j][i], R[j + 1][i], R[j + 1][(i + 1) % seg], R[j][(i + 1) % seg]), uv, m)


def lattice_box(mb, p0, p1, w, m, bay=2.0, chords=None):
    """open truss of square section w from p0 to p1: four faces with the cut-out lattice texture (u along length), plus
    solid corner chords (material `chords`) so the silhouette survives at a distance where the cut-out mips thin away."""
    p0, p1 = Vector(p0), Vector(p1); ax = p1 - p0; L = ax.length; ax.normalize()
    u = Vector((0, 0, 1)) if abs(ax.z) < .9 else Vector((1, 0, 0))
    s = ax.cross(u).normalized() * (w / 2); t = s.cross(ax).normalized() * (w / 2)
    c = [p0 - s - t, p0 + s - t, p0 + s + t, p0 - s + t]; d = [q + ax * L for q in c]
    if chords is not None:
        for q in c:
            obox(mb, q, q + ax * L, w * .09, w * .09, chords)
    k = L / bay
    for i in range(4):
        a, b = c[i], c[(i + 1) % 4]
        mb.face([a, b, d[(i + 1) % 4], d[i]], [(0, 0), (1, 0), (1, k), (0, k)], m)


def text_mesh(body, size, loc, m, rot=(math.pi / 2, 0, 0), extrude=.05, align='CENTER'):
    cu = bpy.data.curves.new('t', 'FONT'); cu.body = body; cu.size = size; cu.extrude = extrude; cu.align_x = align
    cu.align_y = 'CENTER'
    o = bpy.data.objects.new('t', cu); bpy.context.scene.collection.objects.link(o)
    o.location = loc; o.rotation_euler = rot
    bpy.context.view_layer.objects.active = o; o.select_set(True)
    bpy.ops.object.convert(target='MESH'); o = bpy.context.object; o.select_set(False)
    o.data.materials.clear(); o.data.materials.append(m)
    bl.apply_all(o)
    if not o.data.uv_layers:
        o.data.uv_layers.new(name='UVMap')
    return o


# ---------------------------------------------------------------- shared building parts
def rooftop(mb, x0, y0, x1, y1, z, M, rg, style='modern', lo=False):
    """Roof clutter so roofs are not flat and empty: plant screens, HVAC, cooling towers, water tanks, antennas."""
    w, d = x1 - x0, y1 - y0
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    if lo:
        if style != 'none':
            boxc(mb, cx + w * .1, cy + d * .05, z, w * .4, d * .4, 3.2, M['mech'])
        return
    if style in ('modern', 'office'):
        sw, sd = w * rg.uniform(.35, .5), d * rg.uniform(.35, .5)
        sx, sy = cx + rg.uniform(-.15, .15) * w, cy + rg.uniform(-.15, .15) * d
        boxc(mb, sx, sy, z, sw, sd, 4.2, M['mech'])                                    # louvred plant screen
        for k in range(int(sw // 2.2)):
            boxc(mb, sx - sw / 2 + 1.1 + k * 2.2, sy - sd / 2 - .06, z + .3, .12, .12, 3.6, M['metal'])
        for k in range(3 + rg.randint(0, 3)):
            hx, hy = x0 + rg.uniform(.15, .85) * w, y0 + rg.uniform(.15, .85) * d
            if abs(hx - sx) < sw / 2 + 2 and abs(hy - sy) < sd / 2 + 2:
                continue
            boxc(mb, hx, hy, z, rg.uniform(2, 3.5), rg.uniform(1.5, 2.5), rg.uniform(1.2, 2), M['mech'])
        if style == 'office':
            for k in range(2):
                cyl(mb, sx + sw / 2 - 2.5 - k * 4.4, sy + sd / 2 + 2.6, z, 1.9, 3.2, M['mech'], 12)
                cyl(mb, sx + sw / 2 - 2.5 - k * 4.4, sy + sd / 2 + 2.6, z + 3.2, 1.6, .5, M['metal'], 12)
        ax, ay = x0 + w * .82, y0 + d * .8
        boxc(mb, ax, ay, z, .25, .25, rg.uniform(6, 12), M['steel'], top=True)
    elif style == 'old':
        tx, ty = x0 + w * rg.uniform(.25, .75), y0 + d * rg.uniform(.55, .8)
        for dx in (-1.3, 1.3):
            for dy in (-1.3, 1.3):
                boxc(mb, tx + dx, ty + dy, z, .22, .22, 3.2, M['metal'])
        boxc(mb, tx, ty, z + 3.0, 3.6, 3.6, .25, M['wood'])
        cyl(mb, tx, ty, z + 3.25, 1.9, 3.4, M['wood'], 14, top=False)
        cyl(mb, tx, ty, z + 6.65, 2.05, 1.2, M['metal'], 14, r2=.2)
        for k in range(2):
            hx = x0 + w * (.2 + .5 * k); boxc(mb, hx, y0 + d * .3, z, 1.4, .9, 2.4, M['brick'] if 'brick' in M else M['trim'])
        boxc(mb, cx, y0 + d * .25, z, 2.4, 2.4, 2.4, M['trim_dark'])                    # stair hatch
        boxc(mb, x0 + w * .7, y0 + d * .3, z, 2.6, 2.0, .8, M['glass_dark'])             # skylight
    elif style == 'resi':
        boxc(mb, cx, cy, z, w * .3, d * .45, 3.6, M['trim'])                            # lift / stair overrun
        for k in range(4):
            boxc(mb, x0 + w * (.15 + k * .22), y0 + d * .2, z, 1.2, .8, 1.0, M['mech'])
        boxc(mb, x0 + w * .85, y0 + d * .75, z, .18, .18, 5, M['steel'])


def parapet(mb, poly, z, h, t, m, top_m=None):
    """thin wall around a roof edge (outer face only + cap), keeps the roof line crisp"""
    prism(mb, poly, z, z + h, m, None, top=None)
    n = len(poly)
    # inner face, inset by t (approximate for convex polygons)
    cx = sum(p[0] for p in poly) / n; cy = sum(p[1] for p in poly) / n
    inner = []
    for x, y in poly:
        dx, dy = x - cx, y - cy; L = math.hypot(dx, dy) or 1
        k = max(0, 1 - t * 1.41 / L)
        inner.append((cx + dx * k, cy + dy * k))
    prism(mb, list(reversed(inner)), z, z + h, m, None)
    for i in range(n):
        a, b, c, d = poly[i], poly[(i + 1) % n], inner[(i + 1) % n], inner[i]
        mb.face([(a[0], a[1], z + h), (b[0], b[1], z + h), (c[0], c[1], z + h), (d[0], d[1], z + h)], [(0, 0), (1, 0), (1, .1), (0, .1)], top_m or m)


def awning(mb, x0, x1, y, z, depth, m, frame_m):
    """sloped fabric awning on the -Y face from x0..x1 at height z"""
    mb.face([(x0, y - depth, z - .9), (x1, y - depth, z - .9), (x1, y, z), (x0, y, z)], [(0, 0), ((x1 - x0) / 2, 0), ((x1 - x0) / 2, 1), (0, 1)], m)
    mb.face([(x0, y, z), (x1, y, z), (x1, y - depth, z - .9), (x0, y - depth, z - .9)], [(0, 1), ((x1 - x0) / 2, 1), ((x1 - x0) / 2, 0), (0, 0)], m)
    box(mb, x0, y - depth - .02, z - 1.25, x1, y - depth + .02, z - .9, m)                  # valance
    for x in (x0, x1):
        obox(mb, (x, y, z - .1), (x, y - depth, z - 1.0), .05, .05, frame_m)


def fire_escape(mb, x, y0, y1, z0, z1, fh, M, side=1):
    """steel fire escape on a wall at x (facing +x when side=1): landings per floor, stair flights, rails"""
    for k in range(int((z1 - z0) / fh) + 1):
        z = z0 + k * fh
        if z > z1:
            break
        box(mb, x, y0, z, x + side * 1.3, y1, z + .1, M['metal'], top=True)
        box(mb, x + side * 1.25, y0, z + .1, x + side * 1.3, y1, z + 1.05, M['metal'], top=True)
        if k:
            obox(mb, (x + side * .65, y0 + .4, z - fh + .1), (x + side * .65, y1 - .4, z), .7, .08, M['metal'])


def shopfront_band(mb, poly, M, h=5.0, faces='all', back='stone'):
    """ground floor: shopfront texture on the chosen faces, a plain material elsewhere"""
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        L = math.dist(a, b)
        front = faces == 'all' or i in faces
        m = M['shop'] if front else M[back]
        mode = F('shop') if front else (F(back) if back in TILE else None)
        mb.face([(a[0], a[1], 0), (b[0], b[1], 0), (b[0], b[1], h), (a[0], a[1], h)], wall_uv(0, L, L, 0, h, mode), m)


def cornice(mb, poly, z, M, m=None, proud=.45, dentils=False):
    m = m or M['trim']
    n = len(poly)
    def grow(k):
        cx = sum(p[0] for p in poly) / n; cy = sum(p[1] for p in poly) / n
        out = []
        for i in range(n):
            # offset each vertex along the bisector of its two edge normals
            ax, ay = poly[i - 1]; bx, by = poly[i]; cx2, cy2 = poly[(i + 1) % n]
            e1 = Vector((bx - ax, by - ay)).normalized(); e2 = Vector((cx2 - bx, cy2 - by)).normalized()
            n1 = Vector((e1.y, -e1.x)); n2 = Vector((e2.y, -e2.x)); nb = (n1 + n2).normalized()
            s = k / max(.3, nb.dot(n1))
            out.append((bx + nb.x * s, by + nb.y * s))
        return out
    prism(mb, grow(proud * .4), z, z + .35, m, top=m, bottom=True)
    prism(mb, grow(proud), z + .35, z + .8, m, top=m, bottom=True)
    if dentils:
        g = grow(proud * .7)
        for i in range(n):
            a, b = Vector(g[i]), Vector(g[(i + 1) % n]); L = (b - a).length; e = (b - a).normalized()
            for k in range(int(L / .7)):
                p = a + e * (k * .7 + .35)
                boxc(mb, p.x, p.y, z + .12, .22, .22, .2, m, top=False)


# ---------------------------------------------------------------- historic low-rise
def hist_sandstone(mb, M, lo, rg):
    """Three-storey rusticated sandstone commercial block: shopfronts, pilasters, arched upper windows, dentil cornice,
    raised name panel with a date stone."""
    w, d, gh = 20.0, 18.0, 5.0
    top = gh + 9.2
    P = rect(-w / 2, -d / 2, w / 2, d / 2)
    if lo:
        prism(mb, P, 0, gh, M['shop'], F('shop')); prism(mb, P, gh, top + 1.6, M['stone'], F('stone', gh), top=M['roof'])
        return dict(w=w, d=d, h=top + 2.6)
    shopfront_band(mb, P, M, gh, faces=[0], back='stone')
    prism(mb, P, gh, top, M['stone'], F('stone', gh))
    box(mb, -w / 2 - .15, -d / 2 - .15, 0, w / 2 + .15, -d / 2 + .3, .45, M['sandtrim'])                    # plinth
    box(mb, -w / 2 - .2, -d / 2 - .2, gh - .25, w / 2 + .2, d / 2 + .2, gh + .2, M['sandtrim'])            # fascia over the shops
    for k in range(6):
        x = -w / 2 + k * 4.0
        boxc(mb, x, -d / 2 - .12, gh + .2, .7, .3, top - gh - .2, M['sandtrim'], top=False)                # pilasters
        boxc(mb, x, -d / 2 - .1, 0, .6, .25, gh - .25, M['metal'], top=False)                             # shop piers
    cornice(mb, P, top, M, M['sandtrim'], .55, dentils=True)
    parapet(mb, rect(-w / 2, -d / 2, w / 2, d / 2), top + .8, 1.0, .3, M['stone'], M['sandtrim'])
    box(mb, -4.5, -d / 2 - .1, top + .8, 4.5, -d / 2 + .4, top + 2.8, M['sandtrim'])                      # name panel
    box(mb, -2.2, -d / 2 - .16, top + 1.3, 2.2, -d / 2 - .1, top + 2.3, M['stone'], top=False)
    mb.extra.append(text_mesh('1911', .7, (0, -d / 2 - .2, top + 1.8), M['trim_dark'], extrude=.04))
    for x0, x1, am in ((-w / 2 + .6, -.6, M['awning_g']), (.6, w / 2 - .6, M['awning_g'])):
        awning(mb, x0, x1, -d / 2 - .15, gh - .45, 1.6, am, M['metal'])
    prism(mb, P, top + .8, top + .8, None, top=M['roof'], walls=False)
    rooftop(mb, -w / 2 + 1, -d / 2 + 1, w / 2 - 1, d / 2 - 1, top + .8, M, rg, 'old')
    mb.col(-w / 2, -d / 2, 0, w / 2, d / 2, top + 1.8)
    return dict(w=w, d=d, h=top + 2.8)


def hist_brick(mb, M, lo, rg, mat='brick', name='BAKERY'):
    """Four-storey red brick commercial building: shopfronts with awnings, bracketed metal cornice, a lit blade sign
    and a steel fire escape on the side wall."""
    w, d, gh, fh = 14.4, 18.0, 5.0, 4.2
    top = gh + 3 * fh
    P = rect(-w / 2, -d / 2, w / 2, d / 2)
    if lo:
        prism(mb, P, 0, gh, M['shop'], F('shop')); prism(mb, P, gh, top + 1.2, M[mat], F('brick', gh), top=M['roof'])
        return dict(w=w, d=d, h=top + 1.2)
    shopfront_band(mb, P, M, gh, faces=[0], back=mat)
    prism(mb, P, gh, top, M[mat], F('brick', gh))
    box(mb, -w / 2 - .1, -d / 2 - .25, gh - .3, w / 2 + .1, -d / 2, gh + .15, M['trim_dark'])
    for x in (-w / 2, w / 2):
        boxc(mb, x, -d / 2 - .05, 0, .8, .4, top, M['sandtrim'], top=False)                             # corner quoins strip
    # bracketed cornice
    box(mb, -w / 2 - .8, -d / 2 - .8, top, w / 2 + .8, d / 2 + .8, top + .6, M['metal'])
    box(mb, -w / 2 - .5, -d / 2 - .5, top - .35, w / 2 + .5, d / 2 + .5, top, M['metal'])
    for k in range(9):
        x = -w / 2 + .4 + k * (w - .8) / 8
        boxc(mb, x, -d / 2 - .45, top - .9, .2, .6, .9, M['metal'], top=False)
    parapet(mb, P, top + .6, .6, .25, M[mat], M['sandtrim'])
    awning(mb, -w / 2 + .5, w / 2 - .5, -d / 2 - .25, gh - .5, 1.8, M['awning_r'] if mat == 'brick' else M['awning_b'], M['metal'])
    # blade sign (lit)
    box(mb, w / 2 - 1.0, -d / 2 - 1.9, gh + 1.0, w / 2 - .8, -d / 2 - .3, gh + 6.0, M['metal'])
    box(mb, w / 2 - 1.05, -d / 2 - 1.8, gh + 1.2, w / 2 - .75, -d / 2 - .4, gh + 5.8, M['glow_m'] if mat == 'brick' else M['glow_c'])
    fire_escape(mb, w / 2, -d / 2 + 3, d / 2 - 3, gh + 1.0, top - 1, fh, M, 1)
    prism(mb, P, top + .6, top + .6, None, top=M['roof'], walls=False)
    rooftop(mb, -w / 2 + 1, -d / 2 + 1, w / 2 - 1, d / 2 - 1, top + .6, M, rg, 'old')
    mb.col(-w / 2, -d / 2, 0, w / 2, d / 2, top + 1.2)
    return dict(w=w, d=d, h=top + 1.2)


def hist_bank(mb, M, lo, rg):
    """Classical stone bank hall: granite steps, a recessed portico of four columns, entablature and pediment."""
    w, d, h = 24.0, 22.0, 14.0
    P = rect(-w / 2, -d / 2, w / 2, d / 2)
    if lo:
        prism(mb, P, 0, h, M['limestone'], F('stone', 1.2), top=M['roof'])
        mb.face([(-w / 2, -d / 2, h), (w / 2, -d / 2, h), (0, -d / 2, h + 3.4)], [(0, 0), (1, 0), (.5, .3)], M['sandtrim'])
        return dict(w=w, d=d, h=h + 3.6)
    pd = 3.0                                                  # portico depth
    body = [(-w / 2, -d / 2), (-6.5, -d / 2), (-6.5, -d / 2 + pd), (6.5, -d / 2 + pd), (6.5, -d / 2), (w / 2, -d / 2), (w / 2, d / 2), (-w / 2, d / 2)]
    box(mb, -w / 2 - .3, -d / 2 - .3, 0, w / 2 + .3, d / 2 + .3, 1.2, M['granite'])
    prism(mb, body, 1.2, h, M['limestone'], F('stone', 1.2))
    for k in range(4):                                        # steps
        box(mb, -7.5 + k * .1, -d / 2 - 2.2 + k * .55, 0, 7.5 - k * .1, -d / 2, .3 * (k + 1), M['granite'])
    for k in range(4):
        x = -4.8 + k * 3.2
        cyl(mb, x, -d / 2 + .9, 1.2, .62, 9.8, M['sandtrim'], 16, r2=.52)
        boxc(mb, x, -d / 2 + .9, 1.2, 1.5, 1.5, .5, M['sandtrim'])
        boxc(mb, x, -d / 2 + .9, 10.6, 1.5, 1.5, .4, M['sandtrim'])
    box(mb, -7.0, -d / 2 + pd - .1, 1.2, 7.0, -d / 2 + pd, 8.5, M['shop'], mode=(14, 7.3, 1.75, 1.2), top=False)
    box(mb, -1.4, -d / 2 + pd - .2, 1.2, 1.4, -d / 2 + pd - .1, 5.0, M['bronze'], top=False)                  # doors
    box(mb, -w / 2 - .4, -d / 2 - .4, h - 1.6, w / 2 + .4, d / 2 + .4, h, M['sandtrim'])                      # entablature
    cornice(mb, P, h, M, M['sandtrim'], .6, dentils=True)
    # pediment and a pitched copper roof running back to a rear gable
    z = h + .8
    for yg, flip in ((-d / 2 - .4, False), (d / 2 + .4, True)):
        tri = [(-7.6, yg, z), (7.6, yg, z), (0, yg, z + 3.4)]
        mb.face(tri[::-1] if flip else tri, [(0, 0), (4, 0), (2, 1)], M['sandtrim'])
        mb.face((tri if flip else tri[::-1]), [(0, 0), (4, 0), (2, 1)], M['sandtrim'])
    for sx in (-1, 1):
        q = [(0, -d / 2 - .6, z + 3.5), (sx * 7.9, -d / 2 - .6, z - .1), (sx * 7.9, d / 2 + .6, z - .1), (0, d / 2 + .6, z + 3.5)]
        mb.face(q if sx < 0 else q[::-1], [(0, 0), (2, 0), (2, 6), (0, 6)], M['copper'])
    box(mb, -7.6, -d / 2 - .4, h, 7.6, d / 2 + .4, z, M['sandtrim'], top=False)
    mb.extra.append(text_mesh('MERCHANTS', .75, (0, -d / 2 - .45, h - .8), M['trim_dark'], extrude=.04))
    prism(mb, P, h + .8, h + .8, None, top=M['roof'], walls=False)
    boxc(mb, 9, 6, h, 1.4, 1.0, 6.5, M['sandtrim'])
    boxc(mb, -9, 6, h, 1.4, 1.0, 6.5, M['sandtrim'])
    mb.col(-w / 2, -d / 2, 0, w / 2, d / 2, h + 1)
    mb.col(-7.5, -d / 2 - 2.2, 0, 7.5, -d / 2, .3)
    return dict(w=w, d=d, h=h + 4.2)


def hist_terracotta(mb, M, lo, rg):
    """Five-storey buff brick and terracotta block: corner quoins, oriel bay windows, a stepped curved gable parapet."""
    w, d, gh, fh = 18.0, 20.0, 5.0, 4.2
    top = gh + 4 * fh
    P = rect(-w / 2, -d / 2, w / 2, d / 2)
    if lo:
        prism(mb, P, 0, gh, M['shop'], F('shop')); prism(mb, P, gh, top + 1, M['brick_buff'], F('brick', gh), top=M['roof'])
        return dict(w=w, d=d, h=top + 4)
    shopfront_band(mb, P, M, gh, faces=[0, 1], back='brick_buff')
    prism(mb, P, gh, top, M['brick_buff'], F('brick', gh))
    for x in (-w / 2, w / 2):
        for k in range(int((top - gh) / .9)):
            z = gh + k * .9
            boxc(mb, x, -d / 2, z, 1.0 if k % 2 else .7, 1.0 if k % 2 else .7, .45, M['sandtrim'], top=False)
    box(mb, -w / 2 - .2, -d / 2 - .3, gh - .3, w / 2 + .2, d / 2 + .2, gh + .2, M['sandtrim'])
    # two oriel bay windows (floors 2-4)
    for cx in (-4.5, 4.5):
        poly = [(cx - 1.9, -d / 2), (cx + 1.9, -d / 2), (cx + 1.3, -d / 2 - .9), (cx - 1.3, -d / 2 - .9)][::-1]
        poly = [(cx - 1.9, -d / 2), (cx - 1.3, -d / 2 - .9), (cx + 1.3, -d / 2 - .9), (cx + 1.9, -d / 2)]
        poly = poly[::-1]
        prism(mb, [(x, y) for x, y in reversed(poly)], gh + fh, top - fh * .3, M['brick_buff'], (3.6, 16.8, 1.2, gh), top=M['sandtrim'], bottom=M['sandtrim'])
    cornice(mb, P, top, M, M['sandtrim'], .5)
    # stepped, curved central gable
    zt = top + .8
    parapet(mb, P, zt, .9, .3, M['brick_buff'], M['sandtrim'])
    prof = [(-5, 0), (-4, 1.4), (-2.6, 2.2), (-1.2, 2.9), (0, 3.4), (1.2, 2.9), (2.6, 2.2), (4, 1.4), (5, 0)]
    for (xa, za), (xb, zb) in zip(prof, prof[1:]):
        mb.face([(xa, -d / 2, zt + .9), (xb, -d / 2, zt + .9), (xb, -d / 2, zt + .9 + zb), (xa, -d / 2, zt + .9 + za)], [(xa / 4, 0), (xb / 4, 0), (xb / 4, zb / 4), (xa / 4, za / 4)], M['brick_buff'])
        mb.face([(xb, -d / 2 + .4, zt + .9), (xa, -d / 2 + .4, zt + .9), (xa, -d / 2 + .4, zt + .9 + za), (xb, -d / 2 + .4, zt + .9 + zb)], [(0, 0)] * 4, M['brick_buff'])
        obox(mb, (xa, -d / 2 + .2, zt + .95 + za), (xb, -d / 2 + .2, zt + .95 + zb), .6, .14, M['sandtrim'])
    cyl(mb, 0, -d / 2 + .2, zt + 1.6, .55, .2, M['sandtrim'], 12, top=True)
    boxc(mb, 0, -d / 2 + .2, zt + 4.3, .09, .09, 5, M['steel'])                                             # flag pole
    mb.face([(0, -d / 2 + .2, zt + 9.2), (1.9, -d / 2 + .2, zt + 8.5), (1.9, -d / 2 + .2, zt + 7.5), (0, -d / 2 + .2, zt + 8.2)], [(0, 0)] * 4, M['red'])
    mb.face([(0, -d / 2 + .2, zt + 8.2), (1.9, -d / 2 + .2, zt + 7.5), (1.9, -d / 2 + .2, zt + 8.5), (0, -d / 2 + .2, zt + 9.2)], [(0, 0)] * 4, M['red'])
    for x0, x1 in ((-w / 2 + .5, -.4), (.4, w / 2 - .5)):
        awning(mb, x0, x1, -d / 2 - .3, gh - .5, 1.5, M['awning_b'], M['metal'])
    prism(mb, P, zt, zt, None, top=M['roof'], walls=False)
    rooftop(mb, -w / 2 + 1, -d / 2 + 2, w / 2 - 1, d / 2 - 1, zt, M, rg, 'old')
    mb.col(-w / 2, -d / 2, 0, w / 2, d / 2, top + 1.7)
    return dict(w=w, d=d, h=top + 4.6)


def derelict(mb, M, lo, rg):
    """Abandoned five-storey walk-up: boarded and broken windows, grime and rust, a broken cornice, a stripped awning
    frame, a rusted water tank and a faded sign board."""
    w, d, fh = 18.0, 18.0, 4.0
    top = 5 * fh
    P = rect(-w / 2, -d / 2, w / 2, d / 2)
    if lo:
        prism(mb, P, 0, top + 1, M['derelict'], F('derelict'), top=M['roof'])
        return dict(w=w, d=d, h=top + 1)
    prism(mb, P, 0, top, M['derelict'], F('derelict'))
    box(mb, -w / 2 - .1, -d / 2 - .15, 3.6, w / 2 + .1, -d / 2, 4.3, M['rust'])
    # broken cornice: some segments missing
    for k in range(9):
        if k in (2, 3, 6):
            continue
        x0 = -w / 2 - .5 + k * (w + 1) / 9
        box(mb, x0, -d / 2 - .6, top, x0 + (w + 1) / 9 - .05, -d / 2 + .3, top + .55, M['trim_dark'])
    box(mb, -w / 2 - .4, -d / 2 + .3, top, -w / 2 + .3, d / 2 + .4, top + .55, M['trim_dark'])
    box(mb, w / 2 - .3, -d / 2 + .3, top, w / 2 + .4, d / 2 + .4, top + .55, M['trim_dark'])
    parapet(mb, P, top, .9, .3, M['derelict'], M['trim_dark'])
    # stripped awning frame, sagging
    for x in (-w / 2 + 1, -2, 2, w / 2 - 1):
        obox(mb, (x, -d / 2, 4.0), (x + rg.uniform(-.2, .2), -d / 2 - 1.6, 3.2 - rg.uniform(0, .4)), .06, .06, M['rust'])
    obox(mb, (-w / 2 + 1, -d / 2 - 1.6, 3.1), (w / 2 - 1, -d / 2 - 1.5, 2.8), .06, .06, M['rust'])
    # faded sign board, hanging crooked
    obox(mb, (-6, -d / 2 - .2, 7.2), (5, -d / 2 - .2, 6.4), 1.6, .1, M['wood'], up=(0, 1, 0))
    fire_escape(mb, -w / 2, -d / 2 + 4, d / 2 - 4, 4.5, top - 2, fh, M, -1)
    prism(mb, P, top, top, None, top=M['roof'], walls=False)
    tx, ty = 3, 3
    for dx in (-1.2, 1.2):
        for dy in (-1.2, 1.2):
            boxc(mb, tx + dx, ty + dy, top, .2, .2, 3.0, M['rust'])
    cyl(mb, tx, ty, top + 3.0, 1.8, 3.0, M['rust'], 12, top=False)
    cyl(mb, tx, ty, top + 6.0, 1.9, .9, M['rust'], 12, r2=.3)
    obox(mb, (-5, -4, top), (-5.6, -4.3, top + 4.5), .2, .2, M['steel'])                                     # bent antenna
    mb.col(-w / 2, -d / 2, 0, w / 2, d / 2, top + .9)
    return dict(w=w, d=d, h=top + .9)


# ---------------------------------------------------------------- 1970s / 80s towers
def slab70(mb, M, lo, rg):
    """1970s office slab: bronze ribbon glazing between concrete bands, blank precast end walls, a recessed colonnade
    lobby and a louvred plant penthouse."""
    w, d, lh, fl = 42.0, 21.0, 6.0, 15
    top = lh + fl * 3.8
    P = rect(-w / 2, -d / 2, w / 2, d / 2)
    if lo:
        prism(mb, P, 0, top, M['ribbon'], F('ribbon', lh), top=M['roof'])
        boxc(mb, 0, 0, top, w * .5, d * .6, 5, M['precast'])
        return dict(w=w, d=d, h=top + 5)
    box(mb, -w / 2 + 2.2, -d / 2 + 2.2, 0, w / 2 - 2.2, d / 2 - 2.2, lh, M['glass_bronze'], mode=F('curtain'), top=False)
    box(mb, -w / 2, -d / 2, lh - .9, w / 2, d / 2, lh, M['trim'], top=False, bottom=True)
    for k in range(8):
        x = -w / 2 + .6 + k * (w - 1.2) / 7
        for y in (-d / 2 + .6, d / 2 - .6):
            boxc(mb, x, y, 0, 1.0, 1.0, lh - .9, M['trim'], top=False)
    # long faces ribbon glazing, end faces blank precast with a slot
    for (a, b) in ((P[0], P[1]), (P[2], P[3])):
        L = math.dist(a, b)
        mb.face([(a[0], a[1], lh), (b[0], b[1], lh), (b[0], b[1], top), (a[0], a[1], top)], wall_uv(0, L, L, lh, top, F('ribbon', lh)), M['ribbon'])
    for (a, b) in ((P[1], P[2]), (P[3], P[0])):
        L = math.dist(a, b)
        mb.face([(a[0], a[1], lh), (b[0], b[1], lh), (b[0], b[1], top), (a[0], a[1], top)], wall_uv(0, L, L, lh, top, None), M['trim'])
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2; sx = 1 if a[0] > 0 else -1
        box(mb, mx - .05 * sx, my - 1, lh + 2, mx + .08 * sx, my + 1, top - 2, M['glass_bronze'], top=False)
    for sx in (-1, 1):
        box(mb, sx * w / 2 - .4, -d / 2 - .4, lh, sx * w / 2 + .4, d / 2 + .4, top + .6, M['trim'])      # end fins
    box(mb, -w / 2, -d / 2, top, w / 2, d / 2, top + 1.2, M['trim'])
    prism(mb, P, top + 1.2, top + 1.2, None, top=M['roof'], walls=False)
    boxc(mb, 0, 0, top + 1.2, w * .45, d * .55, 5, M['precast'], mode=F('precast', top + 1.2))
    rooftop(mb, -w / 2 + 1, -d / 2 + 1, w / 2 - 1, d / 2 - 1, top + 1.2, M, rg, 'office')
    mb.col(-w / 2, -d / 2, 0, w / 2, d / 2, top + 6)
    return dict(w=w, d=d, h=top + 6)


def setback(mb, M, lo, rg):
    """1980s bronze-glass setback tower: three chamfered tiers with terraces on a granite podium, a pyramidal crown."""
    tiers = [(36.0, 8.0, 46.0, 5.0), (30.0, 46.0, 84.0, 4.5), (23.0, 84.0, 112.0, 4.0)]
    pw = 42.0
    if lo:
        box(mb, -pw / 2, -pw / 2, 0, pw / 2, pw / 2, 8, M['granite'])
        for s, z0, z1, c in tiers:
            prism(mb, chamfer(s, s, c), z0, z1, M['glass_bronze'], F('curtain', z0), top=M['roof'])
        prism(mb, chamfer(23, 23, 4), 112, 113, M['metal'])
        _pyramid(mb, 0, 0, 113, 18, 12, M['bronze'])
        return dict(w=pw, d=pw, h=125)
    box(mb, -pw / 2, -pw / 2, 1.0, pw / 2, pw / 2, 8, M['granite'], top=M['roof'])
    box(mb, -pw / 2 + 4, -pw / 2 - .01, 0, pw / 2 - 4, -pw / 2 + 3, 7, M['glass_bronze'], mode=F('curtain'), top=False)
    box(mb, -pw / 2, -pw / 2, 0, -pw / 2 + 4, pw / 2, 1.0, M['granite'], top=False)
    box(mb, pw / 2 - 4, -pw / 2, 0, pw / 2, pw / 2, 1.0, M['granite'], top=False)
    box(mb, -pw / 2 + 4, -pw / 2 + 3, 0, pw / 2 - 4, pw / 2, 1.0, M['granite'], top=False)
    box(mb, -pw / 2 + 3, -pw / 2 - 4, 6.2, pw / 2 - 3, -pw / 2, 6.8, M['bronze'], bottom=True)          # entrance canopy
    for s, z0, z1, c in tiers:
        poly = chamfer(s, s, c)
        prism(mb, poly, z0, z1, M['glass_bronze'], F('curtain', z0))
        for z in range(int(z0) + 12, int(z1), 12):                                                         # spandrel bands
            prism(mb, chamfer(s + .3, s + .3, c), z - .5, z + .5, M['bronze'], top=None)
        parapet(mb, chamfer(s + .2, s + .2, c), z1, 1.1, .3, M['bronze'])
        prism(mb, poly, z1, z1, None, top=M['roof'], walls=False)
    for s, z0, z1, c in tiers[:2]:
        for k in range(4):
            a = k * math.pi / 2
            for t in (-.3, .3):
                x, y = math.cos(a) * s * .42 + math.sin(a) * t * s, math.sin(a) * s * .42 - math.cos(a) * t * s
                boxc(mb, x, y, z1, 1.6, 1.6, .8, M['trim'])
                blob(mb, x, y, z1 + 1.5, .9, .9, .9, M['plant'])
    prism(mb, chamfer(23, 23, 4), 112, 113.5, M['metal'])
    _pyramid(mb, 0, 0, 113.5, 18, 12, M['bronze'])
    boxc(mb, 0, 0, 125, .3, .3, 10, M['steel'])
    blob(mb, 0, 0, 135.2, .35, .35, .35, M['glow_r'], 6, 4)
    mb.col(-pw / 2, -pw / 2, 0, pw / 2, pw / 2, 8)
    for s, z0, z1, c in tiers:
        mb.col(-s / 2, -s / 2, z0, s / 2, s / 2, z1 + 1)
    return dict(w=pw, d=pw, h=136)


def _pyramid(mb, cx, cy, z, s, h, m):
    p = chamfer(s, s, s * .17, cx, cy); apex = (cx, cy, z + h)
    for i in range(len(p)):
        a, b = p[i], p[(i + 1) % len(p)]
        mb.face([(a[0], a[1], z), (b[0], b[1], z), apex], [(0, 0), (1, 0), (.5, 1)], m)


def ribbed(mb, M, lo, rg, warm=False):
    """Ribbed precast tower: deep vertical ribs at the corners and between bays, a two-storey glazed lobby behind the
    columns, a recessed crown band."""
    s, lh, fl = 30.0, 8.0, 22
    top = lh + fl * 3.8
    mat = M['precast_warm' if warm else 'precast']
    P = rect(-s / 2, -s / 2, s / 2, s / 2)
    if lo:
        prism(mb, P, 0, top + 4, mat, F('precast', lh), top=M['roof'])
        return dict(w=s + 2, d=s + 2, h=top + 9)
    box(mb, -s / 2 + 2, -s / 2 + 2, 0, s / 2 - 2, s / 2 - 2, lh, M['glass_dark'], mode=F('curtain'), top=False)
    box(mb, -s / 2, -s / 2, lh - .8, s / 2, s / 2, lh, M['trim'], top=False, bottom=True)
    prism(mb, P, lh, top, mat, F('precast', lh))
    for k in range(6):
        t = -s / 2 + k * 6.0
        for (x, y, w_, d_) in ((t, -s / 2 - .5, .9, 1.0), (t, s / 2 + .5, .9, 1.0), (-s / 2 - .5, t, 1.0, .9), (s / 2 + .5, t, 1.0, .9)):
            boxc(mb, x, y, 0, w_, d_, top + 2.5, M['trim'], top=True)
    prism(mb, rect(-s / 2 + 1, -s / 2 + 1, s / 2 - 1, s / 2 - 1), top, top + 3.5, M['glass_dark'], F('curtain', top))
    box(mb, -s / 2 - 1, -s / 2 - 1, top + 3.5, s / 2 + 1, s / 2 + 1, top + 5, M['trim'])
    prism(mb, P, top + 5, top + 5, None, top=M['roof'], walls=False)
    rooftop(mb, -s / 2 + 2, -s / 2 + 2, s / 2 - 2, s / 2 - 2, top + 5, M, rg, 'office')
    mb.col(-s / 2 - 1, -s / 2 - 1, 0, s / 2 + 1, s / 2 + 1, top + 5)
    return dict(w=s + 2, d=s + 2, h=top + 10)


# ---------------------------------------------------------------- modern towers
def glass_tower(mb, M, lo, rg):
    """Blue curtain-wall tower with notched corners and slim vertical fins on a stone and glass podium, an open glass
    crown screen with a lit band."""
    s, ph, top = 33.0, 14.0, 150.0
    pw, pd = 44.0, 40.0
    if lo:
        box(mb, -pw / 2, -pd / 2, 0, pw / 2, pd / 2, ph, M['glass_teal'], mode=F('curtain'))
        prism(mb, notched(s, s, 3), ph, top + 6, M['glass_blue'], F('curtain', ph), top=M['roof'])
        return dict(w=pw, d=pd, h=top + 6)
    box(mb, -pw / 2, -pd / 2, 0, pw / 2, pd / 2, ph, M['granite'], top=M['roof'])
    box(mb, -pw / 2 + 6, -pd / 2 - .02, 0, pw / 2 - 6, -pd / 2 + .3, ph - 2, M['glass_teal'], mode=F('curtain'), top=False)
    box(mb, -pw / 2 - .02, -pd / 2 + 6, 0, -pw / 2 + .3, pd / 2 - 6, 6, M['glass_teal'], mode=F('curtain'), top=False)
    box(mb, -pw / 2 + 4, -pd / 2 - 5, ph - 3.6, pw / 2 - 4, -pd / 2, ph - 3.0, M['metal_l'], bottom=True)      # canopy
    box(mb, -pw / 2 + 4.2, -pd / 2 - 4.8, ph - 3.65, pw / 2 - 4.2, -pd / 2 - .2, ph - 3.6, M['glow_w'], top=False, bottom=True)
    poly = notched(s, s, 3)
    prism(mb, poly, ph, top, M['glass_blue'], F('curtain', ph))
    for i in range(0, len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        L = math.dist(a, b)
        if L < 10:
            continue
        e = ((b[0] - a[0]) / L, (b[1] - a[1]) / L); nrm = (e[1], -e[0])
        for k in range(1, int(L / 6)):
            t = k * L / int(L / 6)
            x, y = a[0] + e[0] * t + nrm[0] * .3, a[1] + e[1] * t + nrm[1] * .3
            boxc(mb, x, y, ph, .35 + abs(nrm[0]) * .35, .35 + abs(nrm[1]) * .35, top - ph + 6, M['metal_l'])
    prism(mb, notched(s - .4, s - .4, 3), top, top + 6, M['glass_silver'], F('curtain', top))
    prism(mb, list(reversed(notched(s - 1.2, s - 1.2, 3))), top, top + 6, M['glass_dark'], F('curtain', top))
    prism(mb, notched(s + .2, s + .2, 3), top - 1.2, top - .6, M['glow_c'])
    prism(mb, notched(s - 1.2, s - 1.2, 3), top, top, None, top=M['roof'], walls=False)
    rooftop(mb, -s / 2 + 4, -s / 2 + 4, s / 2 - 4, s / 2 - 4, top, M, rg, 'modern')
    rooftop(mb, -pw / 2 + 2, pd / 2 - 8, -s / 2 - 1, pd / 2 - 2, ph, M, rg, 'modern')
    mb.col(-pw / 2, -pd / 2, 0, pw / 2, pd / 2, ph)
    mb.col(-s / 2, -s / 2, ph, s / 2, s / 2, top + 6)
    return dict(w=pw, d=pd, h=top + 6)


def crescent(mb, M, lo, rg):
    """Crescent headquarters: a curved silver-glass slab that bows to the north and opens to a plaza on the south, a
    diagrid on its concave face, a curved roofline and a full-height glass atrium at its foot."""
    Ro, Ri, a, yc, H = 60.0, 37.0, math.radians(34), -46.0, 206.0
    n = 18
    ang = [-a + 2 * a * i / n for i in range(n + 1)]
    hz = lambda t: H - 22 * (t / a) ** 2
    O = [(math.sin(t) * Ro, yc + math.cos(t) * Ro) for t in ang]
    I = [(math.sin(t) * Ri, yc + math.cos(t) * Ri) for t in ang]
    mat = M['glass_silver']
    tw, th = TILE['curtain'][:2]
    def surface(pts, flip, zf, m):
        per = [0.0]
        for i in range(n):
            per.append(per[-1] + math.dist(pts[i], pts[i + 1]))
        for i in range(n):
            a0, b0 = pts[i], pts[i + 1]; za, zb = zf(ang[i]), zf(ang[i + 1])
            q = [(a0[0], a0[1], 0), (b0[0], b0[1], 0), (b0[0], b0[1], zb), (a0[0], a0[1], za)]
            uv = [(per[i] / tw, 0), (per[i + 1] / tw, 0), (per[i + 1] / tw, zb / th), (per[i] / tw, za / th)]
            if flip:
                q = q[::-1]; uv = uv[::-1]
            mb.face(q, uv, m, smooth=False)
        return per
    # outer (north, convex) face winds clockwise in plan seen from above -> flip; inner (south) face natural
    surface(O, False, hz, mat)
    surface(I, True, hz, mat)
    for k, sgn in ((0, -1), (n, 1)):
        a0, b0 = I[k], O[k]; z = hz(ang[k]); L = math.dist(a0, b0)
        q = [(a0[0], a0[1], 0), (b0[0], b0[1], 0), (b0[0], b0[1], z), (a0[0], a0[1], z)]
        uv = wall_uv(0, L, L, 0, z, F('curtain'))
        if sgn > 0:
            q = q[::-1]; uv = uv[::-1]
        mb.face(q, uv, mat)
    for i in range(n):
        za, zb = hz(ang[i]), hz(ang[i + 1])
        mb.face([(I[i][0], I[i][1], za), (I[i + 1][0], I[i + 1][1], zb), (O[i + 1][0], O[i + 1][1], zb), (O[i][0], O[i][1], za)][::-1],
                [(0, 0), (1, 0), (1, 1), (0, 1)], M['roof'])
    if lo:
        mb.col(-36, -14, 0, 36, 14, H)
        return dict(w=72, d=30, h=H)
    # roof crown fins and parapet edge
    for i in range(n + 1):
        z = hz(ang[i])
        obox(mb, (O[i][0], O[i][1], z - 2), (O[i][0], O[i][1], z + 3.5), .5, .5, M['metal_l'])
    for P_, d_ in ((O, .5), (I, -.5)):
        for i in range(n):
            obox(mb, (P_[i][0], P_[i][1], hz(ang[i]) + .6), (P_[i + 1][0], P_[i + 1][1], hz(ang[i + 1]) + .6), .4, 1.2, M['metal_l'])
    # diagrid on the concave (south) face: members between nodes every 3 arc segments / 24 m
    rows = int(H / 24)
    off = .9
    Io = [(math.sin(t) * (Ri - off), yc + math.cos(t) * (Ri - off)) for t in ang]
    for r in range(rows):
        z0, z1 = r * 24, (r + 1) * 24
        for i in range(0, n, 3):
            j = min(n, i + 3)
            if hz(ang[i]) < z1 or hz(ang[j]) < z1:
                continue
            obox(mb, (Io[i][0], Io[i][1], z0), (Io[j][0], Io[j][1], z1), .7, .7, M['metal_l'])
            obox(mb, (Io[j][0], Io[j][1], z0), (Io[i][0], Io[i][1], z1), .7, .7, M['metal_l'])
        prism_band = [(Io[i][0], Io[i][1]) for i in range(n + 1)]
        for i in range(n):
            if hz(ang[i]) > z1 and hz(ang[i + 1]) > z1:
                obox(mb, (Io[i][0], Io[i][1], z1), (Io[i + 1][0], Io[i + 1][1], z1), .5, .5, M['metal_l'])
    # atrium base on the concave face: a glass box with a lit soffit
    Ia = [(math.sin(t) * (Ri - 7), yc + math.cos(t) * (Ri - 7)) for t in ang[4:n - 3]]
    for i in range(len(Ia) - 1):
        a0, b0 = Ia[i], Ia[i + 1]
        mb.face([(b0[0], b0[1], 0), (a0[0], a0[1], 0), (a0[0], a0[1], 22), (b0[0], b0[1], 22)], wall_uv(0, 10, 10, 0, 22, F('curtain')), M['glass_teal'])
    edge = [(math.sin(t) * (Ri - .2), yc + math.cos(t) * (Ri - .2)) for t in ang[4:n - 3]]
    for i in range(len(Ia) - 1):
        mb.face([(Ia[i][0], Ia[i][1], 22), (Ia[i + 1][0], Ia[i + 1][1], 22), (edge[i + 1][0], edge[i + 1][1], 22), (edge[i][0], edge[i][1], 22)], [(0, 0)] * 4, M['metal_l'])
        mb.face([(edge[i][0], edge[i][1], 21.8), (edge[i + 1][0], edge[i + 1][1], 21.8), (Ia[i + 1][0], Ia[i + 1][1], 21.8), (Ia[i][0], Ia[i][1], 21.8)], [(0, 0)] * 4, M['glow_w'])
    for t in (ang[4], ang[n - 3]):
        a0 = (math.sin(t) * (Ri - 7), yc + math.cos(t) * (Ri - 7)); b0 = (math.sin(t) * Ri, yc + math.cos(t) * Ri)
        mb.face([(a0[0], a0[1], 0), (b0[0], b0[1], 0), (b0[0], b0[1], 22), (a0[0], a0[1], 22)], [(0, 0), (1, 0), (1, 1), (0, 1)], M['glass_teal'])
        mb.face([(b0[0], b0[1], 0), (a0[0], a0[1], 0), (a0[0], a0[1], 22), (b0[0], b0[1], 22)], [(0, 0), (1, 0), (1, 1), (0, 1)], M['glass_teal'])
    for i in range(0, n - 1, 3):
        mb.col(min(O[i][0], O[i + 3 if i + 3 <= n else n][0], I[i][0], I[min(n, i + 3)][0]), min(I[i][1], I[min(n, i + 3)][1]) - 1, 0,
               max(O[i][0], O[min(n, i + 3)][0], I[i][0], I[min(n, i + 3)][0]), max(O[i][1], O[min(n, i + 3)][1]), H - 20)
    return dict(w=72, d=30, h=H + 3)


def twist(mb, M, lo, rg):
    """Twisting tower: a chamfered square plan turning 1.15 degrees per floor (46 degrees over 40 floors) on a glazed
    base, open crown fins at the top."""
    s, c, fl, fh, base = 30.0, 4.0, 40, 4.0, 8.0
    poly = chamfer(s, s, c)
    nseg = 1 if lo else 1
    step = 4 if lo else 1
    tw, th = TILE['curtain'][:2]
    rings = []
    for k in range(0, fl + 1, step):
        r = math.radians(1.15 * k)
        rings.append((base + k * fh, [(x * math.cos(r) - y * math.sin(r), x * math.sin(r) + y * math.cos(r)) for x, y in poly]))
    n = len(poly)
    for (z0, A), (z1, B) in zip(rings, rings[1:]):
        for i in range(n):
            a0, b0, a1, b1 = A[i], A[(i + 1) % n], B[i], B[(i + 1) % n]
            L = math.dist(a0, b0)
            off = (L - math.floor(L / 1.5) * 1.5) / 2
            mb.face([(a0[0], a0[1], z0), (b0[0], b0[1], z0), (b1[0], b1[1], z1)], [(-off / tw, (z0 - base) / th), ((L - off) / tw, (z0 - base) / th), ((L - off) / tw, (z1 - base) / th)], M['glass_teal'])
            mb.face([(a0[0], a0[1], z0), (b1[0], b1[1], z1), (a1[0], a1[1], z1)], [(-off / tw, (z0 - base) / th), ((L - off) / tw, (z1 - base) / th), (-off / tw, (z1 - base) / th)], M['glass_teal'])
        if not lo and int((z1 - base) / fh) % 5 == 0:
            r = math.radians(1.15 * (z1 - base) / fh)
            band = [(x * math.cos(r) - y * math.sin(r), x * math.sin(r) + y * math.cos(r)) for x, y in chamfer(s + .5, s + .5, c + .2)]
            prism(mb, band, z1 - .4, z1 + .2, M['metal_l'], top=None, bottom=True)
    ztop, T = rings[-1]
    mb.face([(x, y, ztop) for x, y in T], [(0, 0)] * n, M['roof'])
    # base: chamfered glazed lobby
    prism(mb, chamfer(s + 6, s + 6, c + 2), 0, base, M['glass_teal'], F('curtain'), top=M['roof'])
    box(mb, -(s + 8) / 2, -(s + 8) / 2 - 4, base - .8, (s + 8) / 2, -(s + 8) / 2 + 2, base - .2, M['metal_l'], bottom=True)
    if lo:
        mb.col(-(s + 6) / 2, -(s + 6) / 2, 0, (s + 6) / 2, (s + 6) / 2, ztop)
        return dict(w=s + 8, d=s + 8, h=ztop + 14)
    # crown: fins rising from the edges, lit at the tips
    r = math.radians(1.15 * fl)
    for i in range(n):
        a0, b0 = T[i], T[(i + 1) % n]
        for t in (.2, .5, .8):
            x, y = a0[0] + (b0[0] - a0[0]) * t, a0[1] + (b0[1] - a0[1]) * t
            hh = 14 - abs(t - .5) * 10
            obox(mb, (x, y, ztop - 1), (x * .96, y * .96, ztop + hh), .5, 1.6, M['metal_l'])
            blob(mb, x * .96, y * .96, ztop + hh, .3, .3, .3, M['glow_w'], 6, 4)
    rooftop(mb, -10, -10, 10, 10, ztop, M, rg, 'modern')
    mb.col(-(s + 6) / 2, -(s + 6) / 2, 0, (s + 6) / 2, (s + 6) / 2, base)
    mb.col(-s / 2 - 2, -s / 2 - 2, base, s / 2 + 2, s / 2 + 2, ztop)
    return dict(w=s + 8, d=s + 8, h=ztop + 14)


def crown_tower(mb, M, lo, rg):
    """Dark glass tower with light metal pilasters every 3 m and a three-tier lantern crown outlined in warm light,
    topped by a spire."""
    s, top = 30.0, 140.0
    P = rect(-s / 2, -s / 2, s / 2, s / 2)
    tiers = [(26.0, top, top + 6), (21.0, top + 6, top + 11), (15.0, top + 11, top + 15)]
    if lo:
        prism(mb, P, 0, top, M['glass_dark'], F('curtain'), top=M['roof'])
        for w_, z0, z1 in tiers:
            prism(mb, rect(-w_ / 2, -w_ / 2, w_ / 2, w_ / 2), z0, z1, M['glass_silver'], F('curtain', z0), top=M['roof'])
        return dict(w=s + 4, d=s + 4, h=top + 34)
    prism(mb, P, 10, top, M['glass_dark'], F('curtain', 10))
    box(mb, -s / 2 + 2.5, -s / 2 + 2.5, 0, s / 2 - 2.5, s / 2 - 2.5, 10, M['glass_teal'], mode=F('curtain'), top=False)
    box(mb, -s / 2, -s / 2, 9, s / 2, s / 2, 10, M['granite'], top=False, bottom=True)
    for k in range(11):
        t = -s / 2 + k * 3.0
        for (x, y, w_, d_) in ((t, -s / 2 - .25, .4, .5), (t, s / 2 + .25, .4, .5), (-s / 2 - .25, t, .5, .4), (s / 2 + .25, t, .5, .4)):
            boxc(mb, x, y, 0 if k in (0, 10) else 10, w_, d_, top - (0 if k in (0, 10) else 10) + 1, M['metal_l'], top=True)
    box(mb, -s / 2 - .4, -s / 2 - .4, top, s / 2 + .4, s / 2 + .4, top + .8, M['metal_l'])
    for w_, z0, z1 in tiers:
        prism(mb, rect(-w_ / 2, -w_ / 2, w_ / 2, w_ / 2), z0 + .8, z1, M['glass_silver'], F('curtain', z0))
        prism(mb, rect(-w_ / 2 - .3, -w_ / 2 - .3, w_ / 2 + .3, w_ / 2 + .3), z1, z1 + .35, M['glow'], top=M['metal_l'])
        for sx in (-1, 1):
            for sy in (-1, 1):
                boxc(mb, sx * w_ / 2, sy * w_ / 2, z0 + .8, .35, .35, z1 - z0 - .4, M['glow'])
    cyl(mb, 0, 0, top + 15.35, 1.2, 4, M['metal_l'], 12, r2=.4)
    cyl(mb, 0, 0, top + 19.3, .4, 14, M['steel'], 8, r2=.08)
    blob(mb, 0, 0, top + 33.4, .3, .3, .3, M['glow_r'], 6, 4)
    mb.col(-s / 2, -s / 2, 0, s / 2, s / 2, top + 15)
    return dict(w=s + 1, d=s + 1, h=top + 34)


def midglass(mb, M, lo, rg):
    """Modern mid-rise office in green glass: stepped terraces on one side planted with shrubs, timber soffits."""
    w, d = 40.0, 28.0
    steps = [(0, 40.0, 0, 34.0), (1, 32.0, 34.0, 44.0), (2, 24.0, 44.0, 54.0)]
    if lo:
        for k, ww, z0, z1 in steps:
            prism(mb, rect(-w / 2, -d / 2, -w / 2 + ww, d / 2), z0, z1, M['glass_green'], F('curtain', z0), top=M['roof'])
        return dict(w=w, d=d, h=58)
    box(mb, -w / 2 + 1.5, -d / 2 + 1.5, 0, w / 2 - 1.5, d / 2 - 1.5, 5, M['glass_teal'], mode=F('curtain'), top=False)
    for k, ww, z0, z1 in steps:
        zz = 5 if k == 0 else z0
        P = rect(-w / 2, -d / 2, -w / 2 + ww, d / 2)
        prism(mb, P, zz, z1, M['glass_green'], F('curtain', z0))
        box(mb, -w / 2 - .3, -d / 2 - .3, z1 - .4, -w / 2 + ww + .3, d / 2 + .3, z1 + .5, M['wood'] if k else M['trim'], top=False, bottom=True)
        prism(mb, P, z1 + .5, z1 + .5, None, top=M['roof'], walls=False)
        if k < 2:   # terrace planting on the step
            for j in range(4):
                x = -w / 2 + steps[k + 1][1] + 2 + rg.uniform(0, ww - steps[k + 1][1] - 4)
                y = -d / 2 + 2 + j * (d - 4) / 3
                boxc(mb, x, y, z1 + .5, 2.2, 1.4, .7, M['trim'])
                blob(mb, x, y, z1 + 1.6, 1.2, .8, .8, M['plant'] if j % 2 else M['plant2'])
            box(mb, -w / 2 + steps[k + 1][1], -d / 2, z1 + .5, -w / 2 + ww, -d / 2 + .05, z1 + 1.6, M['glass_rail'], top=False)
    rooftop(mb, -w / 2 + 2, -d / 2 + 2, -w / 2 + 22, d / 2 - 2, 54.5, M, rg, 'modern')
    mb.col(-w / 2, -d / 2, 0, w / 2, d / 2, 34.5)
    mb.col(-w / 2, -d / 2, 34.5, -w / 2 + 32, d / 2, 44.5)
    mb.col(-w / 2, -d / 2, 44.5, -w / 2 + 24, d / 2, 54.5)
    return dict(w=w, d=d, h=58)


# ---------------------------------------------------------------- residential, hotel, parkade
def residential(mb, M, lo, rg):
    """Apartment tower over ground-floor shops: punched windows, cantilevered balconies with glass rails on the long
    faces, a lift overrun and plant on the roof."""
    w, d, gh, fl, fh = 30.6, 20.4, 5.0, 15, 3.2
    top = gh + fl * fh
    P = rect(-w / 2, -d / 2, w / 2, d / 2)
    if lo:
        prism(mb, P, 0, gh, M['shop'], F('shop')); prism(mb, P, gh, top, M['punched_warm'], F('punched', gh), top=M['roof'])
        return dict(w=w, d=d + 3, h=top + 4)
    shopfront_band(mb, P, M, gh, faces=[0, 2], back='trim')
    prism(mb, P, gh, top, M['punched_warm'], F('punched', gh))
    box(mb, -w / 2 - .3, -d / 2 - .3, gh - .3, w / 2 + .3, d / 2 + .3, gh + .3, M['trim'], bottom=True)
    for f in range(1, fl):
        z = gh + f * fh
        for k in range(9):
            if (k + f) % 2:
                continue
            x = -w / 2 + 3.4 * k + 1.7
            for sy in (-1, 1):
                y0 = sy * d / 2
                box(mb, x - 1.6, y0, z - .05, x + 1.6, y0 + sy * 1.5, z + .2, M['trim'], bottom=True)
                box(mb, x - 1.6, y0 + sy * 1.45, z + .2, x + 1.6, y0 + sy * 1.5, z + 1.15, M['glass_rail'], top=False)
                box(mb, x - 1.6, y0 + sy * 1.42, z + 1.15, x + 1.6, y0 + sy * 1.53, z + 1.22, M['metal'])
    box(mb, -w / 2 - .3, -d / 2 - .3, top, w / 2 + .3, d / 2 + .3, top + 1, M['trim'])
    prism(mb, P, top + 1, top + 1, None, top=M['roof'], walls=False)
    rooftop(mb, -w / 2 + 1, -d / 2 + 1, w / 2 - 1, d / 2 - 1, top + 1, M, rg, 'resi')
    for x0, x1 in ((-w / 2 + .5, -1), (1, w / 2 - .5)):
        awning(mb, x0, x1, -d / 2 - .3, gh - .5, 1.6, M['awning_g'], M['metal'])
    mb.col(-w / 2, -d / 2, 0, w / 2, d / 2, top + 1)
    return dict(w=w, d=d + 3, h=top + 5)


def hotel(mb, M, lo, rg):
    """Hotel slab on a two-storey podium: porte-cochere canopy with a lit soffit, a vertical lit blade sign, a crown band."""
    w, d, ph, fl, fh = 37.4, 20.4, 10.0, 19, 3.2
    top = ph + fl * fh
    P = rect(-w / 2, -d / 2, w / 2, d / 2)
    if lo:
        box(mb, -w / 2 - 2, -d / 2 - 2, 0, w / 2 + 2, d / 2 + 2, ph, M['limestone'], mode=F('stone'))
        prism(mb, P, ph, top + 3, M['punched_grey'], F('punched', ph), top=M['roof'])
        return dict(w=w + 4, d=d + 10, h=top + 6)
    pd = rect(-w / 2 - 2, -d / 2 - 2, w / 2 + 2, d / 2 + 2)
    prism(mb, pd, 5, ph, M['limestone'], F('stone', 5), top=M['roof'])
    prism(mb, pd, 0, 5, M['shop'], F('shop'))
    prism(mb, P, ph, top, M['punched_grey'], F('punched', ph))
    for sx in (-1, 1):
        box(mb, sx * w / 2 - .6, -d / 2 - .6, ph, sx * w / 2 + .6, d / 2 + .6, top + 3, M['trim'])
    box(mb, -w / 2 - .6, -d / 2 - .6, top, w / 2 + .6, d / 2 + .6, top + 3, M['trim'])
    box(mb, -w / 2 - .7, -d / 2 - .7, top + 1, w / 2 + .7, -d / 2 - .55, top + 1.6, M['glow'], top=False)
    # porte-cochere
    box(mb, -9, -d / 2 - 10, 5.2, 9, -d / 2 - 2, 6.0, M['metal'], bottom=True)
    box(mb, -8.8, -d / 2 - 9.8, 5.15, 8.8, -d / 2 - 2.2, 5.2, M['glow_w'], top=False, bottom=True)
    for x in (-8, 8):
        cyl(mb, x, -d / 2 - 9, 0, .3, 5.2, M['metal_l'], 10)
    # blade sign on the corner
    box(mb, w / 2 + .6, -d / 2 + 1, ph + 4, w / 2 + 3.0, -d / 2 + 1.6, ph + 22, M['metal'])
    for k, ch in enumerate('HOTEL'):
        for side in (1, -1):
            o = text_mesh(ch, 2.2, (w / 2 + 1.8, -d / 2 + 1.3 + side * .33, ph + 19.2 - k * 3.4), M['glow'], rot=(math.pi / 2, 0, 0 if side < 0 else math.pi), extrude=.06)
            mb.extra.append(o)
    rooftop(mb, -w / 2 + 2, -d / 2 + 2, w / 2 - 2, d / 2 - 2, top, M, rg, 'resi')
    prism(mb, P, top, top, None, top=M['roof'], walls=False)
    mb.col(-w / 2 - 2, -d / 2 - 2, 0, w / 2 + 2, d / 2 + 2, ph)
    mb.col(-w / 2, -d / 2, ph, w / 2, d / 2, top + 3)
    mb.col(-8.4, -d / 2 - 9.4, 0, -7.6, -d / 2 - 8.6, 5.2); mb.col(7.6, -d / 2 - 9.4, 0, 8.4, -d / 2 - 8.6, 5.2)
    return dict(w=w + 4, d=d + 20, h=top + 3)


def _car(mb, x, y, z, yaw, m, M):
    c, s = math.cos(yaw), math.sin(yaw)
    R = lambda px, py: (x + px * c - py * s, y + px * s + py * c)
    def q(x0, y0, x1, y1, z0, z1, mm):
        poly = [R(x0, y0), R(x1, y0), R(x1, y1), R(x0, y1)]
        prism(mb, poly, z + z0, z + z1, mm, top=mm)
    q(-.9, -2.2, .9, 2.2, .25, .95, m)
    q(-.8, -1.1, .8, 1.0, .95, 1.45, M['tinted'])


def parkade(mb, M, lo, rg):
    """Five-level open-deck parking garage: thin slabs on a column grid, spandrel upstands, an internal ramp, parked cars,
    lit deck soffits, a glazed stair tower and a lit P sign."""
    w, d, lv, lh = 40.0, 30.0, 5, 3.1
    top = lv * lh
    P = rect(-w / 2, -d / 2, w / 2, d / 2)
    if lo:
        for k in range(lv + 1):
            z = k * lh
            box(mb, -w / 2, -d / 2, z, w / 2, d / 2, z + (1.1 if k else .3), M['rawconc'])
        box(mb, -w / 2 + .5, -d / 2 + .5, 0, w / 2 - .5, d / 2 - .5, top, M['tinted'], top=False)
        return dict(w=w, d=d, h=top + 1.1)
    for k in range(lv + 1):
        z = k * lh
        if k:
            box(mb, -w / 2, -d / 2, z - .3, w / 2, d / 2, z, M['rawconc'], bottom=True, top=False)
            box(mb, -w / 2 + .5, -d / 2 + .5, z - .32, w / 2 - .5, d / 2 - .5, z - .3, M['tinted'], top=False, bottom=False)
        prism(mb, P, z, z, None, top=M['roof'] if k == lv else M['rawconc'], walls=False)
        prism(mb, P, z, z + 1.1, M['rawconc'], None, top=M['rawconc'])                                           # upstand
        if k < lv:
            for y in (-d / 2 + 5.5, d / 2 - 5.5):                                                              # lit strips
                box(mb, -w / 2 + 2, y - .15, z + lh - .42, w / 2 - 2, y + .15, z + lh - .32, M['glow_w'], top=False, bottom=True)
    for i in range(6):
        for j in range(4):
            x, y = -w / 2 + .4 + i * (w - .8) / 5, -d / 2 + .4 + j * (d - .8) / 3
            boxc(mb, x, y, 0, .6, .6, top, M['rawconc'], top=False)
    # ramp in the middle bay
    for k in range(lv):
        z0, z1 = k * lh, (k + 1) * lh
        x0, x1 = (-w / 2 + 6, w / 2 - 6) if k % 2 == 0 else (w / 2 - 6, -w / 2 + 6)
        mb.face([(x0, -3, z0 + .02), (x1, -3, z1 - .02), (x1, 3, z1 - .02), (x0, 3, z0 + .02)][:: 1 if k % 2 == 0 else -1], [(0, 0), (8, 0), (8, 1.5), (0, 1.5)], M['rawconc'])
    cars = [M['car_a'], M['car_b'], M['car_c'], M['car_d'], M['car_c'], M['white']]
    for k in range(lv + 1):
        for i in range(8):
            if rg.rand() < .35:
                continue
            x = -w / 2 + 3 + i * 4.9
            for y in (-d / 2 + 3.2, d / 2 - 3.2):
                if rg.rand() < .4:
                    continue
                _car(mb, x, y, k * lh, math.pi / 2 * 0 + (0 if y < 0 else math.pi), cars[rg.randint(len(cars))], M)
    # stair tower
    box(mb, w / 2 - 1, -d / 2 + 2, 0, w / 2 + 4.5, -d / 2 + 8, top + 3.2, M['rawconc'], top=M['roof'])
    box(mb, w / 2 + 4.52, -d / 2 + 3, 1, w / 2 + 4.6, -d / 2 + 7, top + 2, M['glass_dark'], mode=F('curtain'), top=False)
    boxc(mb, w / 2 + 1.75, -d / 2 + 1.9, top - 2, 2.6, .3, 2.6, M['blue'])
    mb.extra.append(text_mesh('P', 2.2, (w / 2 + 1.75, -d / 2 + 1.72, top - .7), M['glow_w'], extrude=.05))
    for x in (-w / 2 + 6, 0, w / 2 - 8):
        boxc(mb, x, 0, top, .2, .2, 6, M['metal'])
        boxc(mb, x, 0, top + 6, .9, .3, .2, M['glow_w'])
    mb.col(-w / 2, -d / 2, 0, w / 2 + 4.6, d / 2, top + 1.1)
    return dict(w=w + 9.2, d=d, h=top + 3.2)


# ---------------------------------------------------------------- landmarks
def obs_tower(mb, M, lo, rg):
    """Observation tower: a granite and glass base hall, a tapering concrete shaft with glazed lift slots, a flared pod
    with the glass viewing band and a lit ring, beacon and mast."""
    zb, zp = 10.0, 160.0
    n = 12 if lo else 24
    if lo:
        box(mb, -16, -16, 0, 16, 16, zb, M['granite'])
        cyl(mb, 0, 0, zb, 8, zp - zb, M['rawconc'], n, r2=6, top=False)
        cyl(mb, 0, 0, zp, 6.5, 5, M['metal_l'], n, r2=14)
        cyl(mb, 0, 0, zp + 5, 14, 7, M['glass_dark'], n, top=False)
        cyl(mb, 0, 0, zp + 12, 14.5, 4, M['metal_l'], n, r2=8)
        cyl(mb, 0, 0, zp + 16, .5, 18, M['steel'], 6, r2=.1)
        mb.col(-16, -16, 0, 16, 16, zb); mb.col(-8, -8, zb, 8, 8, zp + 16)
        return dict(w=32, d=32, h=zp + 34)
    box(mb, -16, -16, 1, 16, 16, zb, M['granite'], top=M['roof'])
    box(mb, -16, -16.02, 0, 16, 16.02, 1, M['granite'], top=False)
    for (a, b) in ((-12, 12),):
        box(mb, a, -16.05, 1, b, -15.9, zb - 1.5, M['glass_teal'], mode=F('curtain', 1), top=False)
        box(mb, -16.05, a, 1, -15.9, b, zb - 1.5, M['glass_teal'], mode=F('curtain', 1), top=False)
        box(mb, 15.9, a, 1, 16.05, b, zb - 1.5, M['glass_teal'], mode=F('curtain', 1), top=False)
    box(mb, -14, -20, zb - 1.6, 14, -16, zb - 1.0, M['metal_l'], bottom=True)
    # shaft with vertical lift slots
    rings = 6
    for k in range(rings):
        z0 = zb + (zp - zb) * k / rings; z1 = zb + (zp - zb) * (k + 1) / rings
        r0 = 8 - 2 * k / rings; r1 = 8 - 2 * (k + 1) / rings
        cyl(mb, 0, 0, z0, r0, z1 - z0, M['rawconc'], n, r2=r1, top=False)
    for a in (0, math.pi):
        for k in range(rings):
            z0 = zb + (zp - zb) * k / rings; z1 = zb + (zp - zb) * (k + 1) / rings
            r0 = 8 - 2 * k / rings + .08; r1 = 8 - 2 * (k + 1) / rings + .08
            c, s = math.cos(a), math.sin(a)
            mb.face([(c * r0 - s * 1.2, s * r0 + c * 1.2, z0), (c * r0 + s * 1.2, s * r0 - c * 1.2, z0), (c * r1 + s * 1.2, s * r1 - c * 1.2, z1), (c * r1 - s * 1.2, s * r1 + c * 1.2, z1)][::-1 if a else 1],
                    [(0, 0), (1, 0), (1, (z1 - z0) / 8), (0, (z1 - z0) / 8)], M['glass_dark'])
    # pod
    cyl(mb, 0, 0, zp - 4, 6.2, 4, M['rawconc'], n, r2=7.5, top=False)
    cyl(mb, 0, 0, zp, 7.5, 5, M['metal_l'], n, r2=14, top=False)
    cyl(mb, 0, 0, zp + 5, 14.2, .5, M['metal_l'], n)
    cyl(mb, 0, 0, zp + 5.5, 14, 6.5, M['glass_dark'], n, top=False, mode=(TILE['curtain'][0], TILE['curtain'][1], 1.5, zp + 5.5))
    cyl(mb, 0, 0, zp + 12, 14.6, .6, M['glow'], n, top=False)
    cyl(mb, 0, 0, zp + 12.6, 14.6, 1.8, M['metal_l'], n, top=False)
    cyl(mb, 0, 0, zp + 14.4, 14.6, 3.2, M['metal_l'], n, r2=8)
    cyl(mb, 0, 0, zp + 17.6, 8, 1.2, M['metal'], n, r2=4)
    cyl(mb, 0, 0, zp + 18.8, 1.4, 3, M['glow_r'], 10, r2=1.0)
    cyl(mb, 0, 0, zp + 21.8, .5, 16, M['steel'], 8, r2=.12)
    blob(mb, 0, 0, zp + 38, .3, .3, .3, M['glow_r'], 6, 4)
    mb.col(-16, -16, 0, 16, 16, zb)
    mb.col(-8, -8, zb, 8, 8, zp + 20)
    return dict(w=32, d=36, h=zp + 38)


# ---------------------------------------------------------------- construction sites
def site_fence(mb, M, hw, hd, gate=8.0, lo=False):
    """2.4 m painted plywood hoarding around the site with a gate gap in the front (-Y) side."""
    h = 2.4
    segs = [((-hw, -hd), (-gate / 2, -hd)), ((gate / 2, -hd), (hw, -hd)), ((hw, -hd), (hw, hd)), ((hw, hd), (-hw, hd)), ((-hw, hd), (-hw, -hd))]
    for (ax, ay), (bx, by) in segs:
        L = math.hypot(bx - ax, by - ay)
        nx, ny = (by - ay) / L * .06, -(bx - ax) / L * .06
        mb.face([(ax, ay, 0), (bx, by, 0), (bx, by, h), (ax, ay, h)], [(0, 0), (L / 8, 0), (L / 8, 1), (0, 1)], M['hoarding'])
        mb.face([(bx - nx * 2, by - ny * 2, 0), (ax - nx * 2, ay - ny * 2, 0), (ax - nx * 2, ay - ny * 2, h), (bx - nx * 2, by - ny * 2, h)], [(0, 0), (L / 4, 0), (L / 4, .6), (0, .6)], M['wood'])
        mb.face([(ax, ay, h), (bx, by, h), (bx - nx * 2, by - ny * 2, h), (ax - nx * 2, ay - ny * 2, h)], [(0, 0)] * 4, M['wood'])
        if not lo:
            for k in range(int(L / 4) + 1):
                t = k * 4 / L if L else 0
                boxc(mb, ax + (bx - ax) * t - nx * 3, ay + (by - ay) * t - ny * 3, 0, .15, .15, h + .1, M['wood'])
    for (ax, ay), (bx, by) in segs:
        mb.col(min(ax, bx) - .1, min(ay, by) - .1, 0, max(ax, bx) + .1, max(ay, by) + .1, h)


def trailer(mb, M, x, y, z, yaw=0.0):
    c, s = math.cos(yaw), math.sin(yaw)
    poly = [(x + px * c - py * s, y + px * s + py * c) for px, py in rect(-6, -1.25, 6, 1.25)]
    prism(mb, poly, z + .3, z + 2.9, M['white'], top=M['metal'])
    for k in (-3.5, 0, 3.5):
        px, py = x + k * c + 1.27 * s, y + k * s - 1.27 * c
        mb.face([(px - .6 * c, py - .6 * s, z + 1.4), (px + .6 * c, py + .6 * s, z + 1.4), (px + .6 * c, py + .6 * s, z + 2.3), (px - .6 * c, py - .6 * s, z + 2.3)], [(0, 0)] * 4, M['tinted'])
    for k in (-5, 5):
        boxc(mb, x + k * c, y + k * s, z, .4, .4, .3, M['metal'])


def construction(mb, M, lo, rg):
    """Tower under construction: concrete core ahead of the slabs, bare floor plates on a column grid with rebar
    starters, curtain wall installed on the lower floors, orange climbing screens wrapping the working floors, safety
    netting, a materials hoist, site trailers and stacked materials, all behind a painted hoarding."""
    s, fh, nfl = 32.0, 4.0, 16
    hw = 23.0
    clad = {0: 7, 1: 4, 2: 5, 3: 6}
    if lo:
        box(mb, -5, -6, 0, 5, 6, 84, M['rawconc'])
        box(mb, -s / 2, -s / 2, 0, s / 2, s / 2, 7 * fh, M['glass_blue'], mode=F('curtain'))
        for f in range(7, nfl + 1):
            box(mb, -s / 2, -s / 2, f * fh - .35, s / 2, s / 2, f * fh, M['rawconc'])
        box(mb, -s / 2 - .5, -s / 2 - .5, (nfl - 3) * fh, s / 2 + .5, s / 2 + .5, nfl * fh + 2, M['net_o'], top=False)
        site_fence(mb, M, hw, hw, lo=True)
        return dict(w=hw * 2, d=hw * 2, h=86)
    site_fence(mb, M, hw, hw)
    box(mb, -5, -6, 0, 5, 6, 84, M['rawconc'])
    for z in range(4, 84, 4):                                                               # core openings
        box(mb, -2, -6.05, z + .5, 2, -6.0, z + 3.2, M['metal'], top=False)
    for f in range(1, nfl + 1):
        z = f * fh
        box(mb, -s / 2, -s / 2, z - .35, s / 2, s / 2, z, M['rawconc'], bottom=True)
    for i in range(5):
        for j in range(5):
            x, y = -s / 2 + 1 + i * (s - 2) / 4, -s / 2 + 1 + j * (s - 2) / 4
            if abs(x) < 6 and abs(y) < 7:
                continue
            boxc(mb, x, y, 0, .7, .7, nfl * fh, M['rawconc'], top=False)
            for k in range(4):
                boxc(mb, x - .2 + (k % 2) * .4, y - .2 + (k // 2) * .4, nfl * fh, .05, .05, 1.4, M['rust'], top=False)
    P = rect(-s / 2, -s / 2, s / 2, s / 2)
    for i in range(4):
        a, b = P[i], P[(i + 1) % 4]
        L = math.dist(a, b); zc = clad[i] * fh - .35
        mb.face([(a[0], a[1], 0), (b[0], b[1], 0), (b[0], b[1], zc), (a[0], a[1], zc)], wall_uv(0, L, L, 0, zc, F('curtain')), M['glass_blue'])
        # partly installed panels on the next floor
        for k in range(int(L / 1.5)):
            if rg.rand() < .45:
                t0, t1 = k * 1.5 / L, (k + 1) * 1.5 / L
                p0 = (a[0] + (b[0] - a[0]) * t0, a[1] + (b[1] - a[1]) * t0); p1 = (a[0] + (b[0] - a[0]) * t1, a[1] + (b[1] - a[1]) * t1)
                mb.face([(p0[0], p0[1], zc), (p1[0], p1[1], zc), (p1[0], p1[1], zc + fh), (p0[0], p0[1], zc + fh)], wall_uv(k * 1.5, (k + 1) * 1.5, L, zc, zc + fh, F('curtain')), M['glass_blue'])
        # edge protection rails on the open floors
        for f in range(clad[i] + 1, nfl - 2):
            z = f * fh
            mb.face([(a[0], a[1], z), (b[0], b[1], z), (b[0], b[1], z + 1.1), (a[0], a[1], z + 1.1)], [(0, 0), (L / 2, 0), (L / 2, .5), (0, .5)], M['net'])
    # climbing screens (orange) on the top three floors
    zs = (nfl - 3) * fh
    prism(mb, rect(-s / 2 - .6, -s / 2 - .6, s / 2 + .6, s / 2 + .6), zs, nfl * fh + 2.2, M['net_o'], None)
    prism(mb, list(reversed(rect(-s / 2 - .55, -s / 2 - .55, s / 2 + .55, s / 2 + .55))), zs, nfl * fh + 2.2, M['net_o'], None)
    box(mb, -s / 2 - .7, -s / 2 - .7, zs - .3, s / 2 + .7, s / 2 + .7, zs, M['yellow'], top=False, bottom=True)
    # formwork and stacked material on the top deck
    box(mb, -s / 2 + 2, -s / 2 + 2, nfl * fh, -2, -s / 2 + 12, nfl * fh + .6, M['wood'])
    for k in range(3):
        box(mb, 7, 2 + k * 2.5, nfl * fh, 13, 3.6 + k * 2.5, nfl * fh + .5, M['rust'])
    # materials hoist on the east face
    lattice_box(mb, (s / 2 + 1.5, -6, 0), (s / 2 + 1.5, -6, nfl * fh + 6), 1.4, M['lattice_g'], 1.4)
    boxc(mb, s / 2 + 3.4, -6, 26, 2.6, 2.4, 2.6, M['yellow'])
    # site: trailers stacked two high, rebar bundles, pallets, portable toilets
    trailer(mb, M, -hw + 7.5, hw - 3.5, 0); trailer(mb, M, -hw + 7.5, hw - 3.5, 2.95)
    box(mb, -hw + 1.5, hw - 5.2, 2.8, -hw + 13.5, hw - 4.9, 3.0, M['metal'])
    for k in range(3):
        box(mb, hw - 9, -hw + 3 + k * 1.4, 0, hw - 1.5, -hw + 3.8 + k * 1.4, .45, M['rust'])
        box(mb, -hw + 2 + k * 2.2, -hw + 2, 0, -hw + 3.8 + k * 2.2, -hw + 3.2, 1.0 + .3 * k, M['wood'])
    for k in range(3):
        boxc(mb, hw - 2 - k * 1.4, hw - 2, 0, 1.2, 1.2, 2.3, M['blue'])
    mb.col(-s / 2 - .7, -s / 2 - .7, 0, s / 2 + .7, s / 2 + .7, nfl * fh)
    mb.col(-5, -6, 0, 5, 6, 84)
    mb.col(-hw + 1.5, hw - 4.8, 0, -hw + 13.5, hw - 2.2, 5.9)
    return dict(w=hw * 2, d=hw * 2, h=86, crane=[s / 2 + 5.5, 0, s / 2 + 3.5], fence=hw)


def construction_b(mb, M, lo, rg):
    """Early-stage site: podium slabs and columns up to level three, the core climbing ahead, scaffolding and green
    netting on the street side, rebar starters, a concrete pump boom folded on its truck."""
    s, fh = 34.0, 4.5
    hw = 22.0
    if lo:
        box(mb, -4.5, -5, 0, 4.5, 5, 26, M['rawconc'])
        for f in range(1, 4):
            box(mb, -s / 2, -s / 2, f * fh - .4, s / 2, s / 2, f * fh, M['rawconc'])
        box(mb, -s / 2 - 1.6, -s / 2 - 1.6, 0, s / 2 + 1.6, -s / 2 - 1.5, 3 * fh + 2, M['net'], top=False)
        site_fence(mb, M, hw, hw, lo=True)
        return dict(w=hw * 2, d=hw * 2, h=28)
    site_fence(mb, M, hw, hw)
    box(mb, -4.5, -5, 0, 4.5, 5, 26, M['rawconc'])
    for k in range(5):
        boxc(mb, -4 + k * 2, -4.6, 26, .05, .05, 1.6, M['rust'], top=False)
    for f in range(1, 4):
        z = f * fh
        box(mb, -s / 2, -s / 2, z - .4, s / 2 if f < 3 else 4, s / 2, z, M['rawconc'], bottom=True)
    for i in range(5):
        for j in range(5):
            x, y = -s / 2 + 1 + i * (s - 2) / 4, -s / 2 + 1 + j * (s - 2) / 4
            if abs(x) < 6 and abs(y) < 6:
                continue
            hgt = 3 * fh if x < 5 else 2 * fh
            boxc(mb, x, y, 0, .7, .7, hgt, M['rawconc'], top=False)
            for k in range(4):
                boxc(mb, x - .2 + (k % 2) * .4, y - .2 + (k // 2) * .4, hgt, .05, .05, 1.2, M['rust'], top=False)
    # scaffold on the front (-Y) face: lattice frames + plank decks + netting
    y = -s / 2 - 1.5
    for k in range(13):
        x = -s / 2 + k * (s / 12)
        boxc(mb, x, y, 0, .06, .06, 3 * fh + 2, M['steel'], top=False)
        boxc(mb, x, y + 1.2, 0, .06, .06, 3 * fh + 2, M['steel'], top=False)
    for z in range(2, int(3 * fh + 2), 2):
        box(mb, -s / 2, y - .05, z, s / 2, y + 1.25, z + .06, M['wood'], bottom=True)
    box(mb, -s / 2, y - .12, 0, s / 2, y - .1, 3 * fh + 2, M['net'], top=False)
    mb.face([(s / 2, y - .1, 0), (-s / 2, y - .1, 0), (-s / 2, y - .1, 3 * fh + 2), (s / 2, y - .1, 3 * fh + 2)], [(0, 0), (s / 2, 0), (s / 2, 7), (0, 7)], M['net'])
    # concrete pump truck
    tx, ty = 10, hw - 6
    box(mb, tx - 5, ty - 1.2, .5, tx + 4, ty + 1.2, 2.6, M['white'])
    box(mb, tx + 4, ty - 1.2, .5, tx + 6.5, ty + 1.2, 3.2, M['yellow'])
    box(mb, tx + 4.6, ty - 1.25, 2.0, tx + 6.4, ty + 1.25, 3.0, M['tinted'], top=False)
    for k in (-3.5, -1.8, 2.5, 5.2):
        for sy in (-1, 1):
            cyl_y = ty + sy * 1.1
            boxc(mb, tx + k, cyl_y, 0, .9, .4, .9, M['rubber'])
    for k in range(3):
        obox(mb, (tx - 4, ty, 2.8 + k * .5), (tx + 3.5, ty, 2.9 + k * .5), .5, .4, M['yellow'])
    for k in range(2):
        box(mb, -hw + 2 + k * 2.2, -hw + 2, 0, -hw + 3.8 + k * 2.2, -hw + 3.2, 1.2, M['wood'])
    trailer(mb, M, -hw + 7.5, hw - 3.5, 0)
    mb.col(-s / 2, -s / 2 - 1.6, 0, s / 2, s / 2, 3 * fh)
    mb.col(-4.5, -5, 0, 4.5, 5, 26)
    mb.col(tx - 5, ty - 1.3, 0, tx + 6.5, ty + 1.3, 3.2)
    return dict(w=hw * 2, d=hw * 2, h=28, crane=[-s / 2 + 3, 0, s / 2 + 3], fence=hw)


# ---------------------------------------------------------------- registry
DESIGNS = [
    # name, builder, kind, era, kwargs
    ('DT_hist_sandstone', hist_sandstone, 'historic', 'old', {}),
    ('DT_hist_brick', hist_brick, 'historic', 'old', {}),
    ('DT_hist_brick_dark', hist_brick, 'historic', 'old', {'mat': 'brick_dark'}),
    ('DT_hist_bank', hist_bank, 'historic', 'old', {}),
    ('DT_hist_terracotta', hist_terracotta, 'historic', 'old', {}),
    ('DT_derelict', derelict, 'historic', 'abandoned', {}),
    ('DT_slab70', slab70, 'tower', '1970s', {}),
    ('DT_setback', setback, 'tower', '1980s', {}),
    ('DT_ribbed', ribbed, 'tower', '1970s', {}),
    ('DT_ribbed_warm', ribbed, 'tower', '1980s', {'warm': True}),
    ('DT_glass_tower', glass_tower, 'tower', 'new', {}),
    ('DT_crescent', crescent, 'tower', 'new', {}),
    ('DT_twist', twist, 'tower', 'new', {}),
    ('DT_crown', crown_tower, 'tower', 'new', {}),
    ('DT_midglass', midglass, 'mid', 'new', {}),
    ('DT_residential', residential, 'mid', 'new', {}),
    ('DT_hotel', hotel, 'mid', '1980s', {}),
    ('DT_parkade', parkade, 'mid', '1970s', {}),
    ('DT_obs_tower', obs_tower, 'landmark', '1960s', {}),
    ('DT_construction', construction, 'site', 'construction', {}),
    ('DT_construction_b', construction_b, 'site', 'construction', {}),
]


def make_root(name, mb, x, meta):
    r = bl.empty(name, (x, 0, 0))
    o = mb.build(name + '_mesh'); o.parent = r
    o.location = (0, 0, 0)
    r['dt'] = json.dumps(meta)
    return r


def build_designs():
    bl.reset()
    M = mats()
    import random
    roots = []
    x = 0.0
    for name, fn, kind, era, kw in DESIGNS:
        rg = _R(hash(name) % 9973)
        hi = MB(); meta = fn(hi, M, False, rg, **kw)
        lo = MB(); fn(lo, M, True, _R(hash(name) % 9973), **kw)
        meta.update(kind=kind, era=era, col=hi.cols)
        x += 120
        rh = make_root(name, hi, x, meta)
        rl = make_root(name + '_lod', lo, x, dict(lod=True))
        rl.location.y = 120
        roots.append((rh, rl))
        print('[design] %-22s hi %6d tris  lo %5d tris  %s' % (name, _tris(rh), _tris(rl), json.dumps({k: meta[k] for k in ('w', 'd', 'h')})))
    return roots


class _R:
    """numpy-free deterministic rng with the calls the builders use"""
    def __init__(self, seed):
        import random
        self.r = random.Random(seed)

    def uniform(self, a, b):
        return self.r.uniform(a, b)

    def rand(self):
        return self.r.random()

    def randint(self, a, b=None):
        return self.r.randrange(a, b) if b is not None else self.r.randrange(a)


def _tris(root):
    t = 0
    for o in root.children:
        if o.type == 'MESH':
            t += sum(len(p.vertices) - 2 for p in o.data.polygons)
    return t


# ---------------------------------------------------------------- street kit
def skywalk(mb, M, L, lo=False):
    """Enclosed glass skywalk along X, length L, floor at 4.8 m (bottom of the structure), 4 m wide."""
    z0, z1, w = 4.8, 8.4, 4.0
    box(mb, -L / 2, -w / 2, z0, L / 2, w / 2, z0 + .5, M['trim'], top=M['pavers'], bottom=True)
    box(mb, -L / 2, -w / 2 - .1, z1 - .4, L / 2, w / 2 + .1, z1, M['metal'], bottom=True)
    if lo:
        box(mb, -L / 2, -w / 2, z0 + .5, L / 2, w / 2, z1 - .4, M['tinted'], top=False)
        return
    for sy in (-1, 1):
        mb.face([(-L / 2, sy * w / 2, z0 + .5), (L / 2, sy * w / 2, z0 + .5), (L / 2, sy * w / 2, z1 - .4), (-L / 2, sy * w / 2, z1 - .4)][::-sy], [(0, 0)] * 4, M['glass'])
        for k in range(int(L / 2) + 1):
            x = -L / 2 + k * L / int(L / 2)
            boxc(mb, x, sy * w / 2, z0 + .5, .12, .14, z1 - z0 - .9, M['metal'], top=False)
        box(mb, -L / 2, sy * w / 2 - .08, z0 + .5, L / 2, sy * w / 2 + .08, z0 + .62, M['metal'])
    box(mb, -L / 2, -.3, z1 - .45, L / 2, .3, z1 - .4, M['glow_w'], top=False, bottom=True)
    box(mb, -L / 2, -w / 2 - .05, z0 - .08, L / 2, -w / 2 + .1, z0, M['glow'], top=False, bottom=True)
    box(mb, -L / 2, w / 2 - .1, z0 - .08, L / 2, w / 2 + .05, z0, M['glow'], top=False, bottom=True)


def platform(mb, M, lo=False):
    """Light-rail platform along X: 44 m x 4.2 m, 0.35 m high, tactile edge, a curved canopy on posts, glass shelters,
    ticket machines, benches, a lit route totem."""
    L, w = 44.0, 4.2
    box(mb, -L / 2, -w / 2, 0, L / 2, w / 2, .35, M['trim'], top=M['pavers'])
    box(mb, -L / 2, -w / 2, .35, L / 2, -w / 2 + .5, .36, M['yellow'], top=True)
    box(mb, -L / 2, w / 2 - .5, .35, L / 2, w / 2, .36, M['yellow'], top=True)
    cl = 30.0
    if lo:
        box(mb, -cl / 2, -w / 2 - .2, 3.6, cl / 2, w / 2 + .2, 3.9, M['metal_l'])
        return
    for k in range(6):
        x = -cl / 2 + 1 + k * (cl - 2) / 5
        cyl(mb, x, 0, .35, .12, 3.3, M['metal_l'], 8)
    sec = [(-w / 2 - .4, 3.55), (-w / 4, 3.85), (0, 3.95), (w / 4, 3.85), (w / 2 + .4, 3.55)]
    for (ya, za), (yb, zb) in zip(sec, sec[1:]):
        mb.face([(-cl / 2, ya, za), (cl / 2, ya, za), (cl / 2, yb, zb), (-cl / 2, yb, zb)][::-1], [(0, 0), (cl / 4, 0), (cl / 4, 1), (0, 1)], M['metal_l'])
        mb.face([(-cl / 2, ya, za - .08), (cl / 2, ya, za - .08), (cl / 2, yb, zb - .08), (-cl / 2, yb, zb - .08)], [(0, 0)] * 4, M['glass'])
    box(mb, -cl / 2, -.2, 3.3, cl / 2, .2, 3.4, M['glow_w'], top=False, bottom=True)
    for x in (-8, 6):
        box(mb, x - 2, .4, .35, x + 2, .45, 2.6, M['glass'], top=False)
        box(mb, x - 2.05, .3, 2.6, x + 2.05, 1.6, 2.7, M['metal'])
        box(mb, x - 1.8, .5, .35, x + 1.8, 1.0, .8, M['wood'])
        box(mb, x - 2.05, .4, .35, x - 1.95, 1.5, 2.6, M['glass'], top=False)
        box(mb, x + 1.95, .4, .35, x + 2.05, 1.5, 2.6, M['glass'], top=False)
    for x in (-14, 13):
        boxc(mb, x, .9, .35, .8, .6, 1.7, M['blue'])
        boxc(mb, x, .58, 1.2, .55, .05, .5, M['glow_c'], top=False)
    boxc(mb, 18, 0, .35, .5, .5, 3.2, M['metal'])
    boxc(mb, 18, 0, 2.6, .7, .55, .9, M['glow_c'])


def track(mb, M, L=20.0, lo=False):
    """Double light-rail track embedded in a paved bed along X (gauge 1.435 m, track centres +-2.2 m)."""
    w = 10.0
    mb.face([(-L / 2, -w / 2, .02), (L / 2, -w / 2, .02), (L / 2, w / 2, .02), (-L / 2, w / 2, .02)], [(-L / 12, -w / 12), (L / 12, -w / 12), (L / 12, w / 12), (-L / 12, w / 12)], M['granite'])
    if lo:
        return
    for yc in (-2.2, 2.2):
        mb.face([(-L / 2, yc - 1.25, .03), (L / 2, yc - 1.25, .03), (L / 2, yc + 1.25, .03), (-L / 2, yc + 1.25, .03)], [(-L / 4, 0), (L / 4, 0), (L / 4, .6), (-L / 4, .6)], M['rawconc'])
        for g in (-.72, .72):
            box(mb, -L / 2, yc + g - .04, .03, L / 2, yc + g + .04, .09, M['steel'], top=True)
    for sy in (-1, 1):
        box(mb, -L / 2, sy * w / 2 - .15 * (sy > 0), 0, L / 2, sy * w / 2 + .15 * (sy < 0), .15, M['trim'])


def catenary(mb, M, L=20.0):
    """Centre pole with two arms and the two contact wires for one 20 m span along X."""
    cyl(mb, 0, 0, 0, .14, 7.2, M['metal'], 8)
    for sy in (-1, 1):
        obox(mb, (0, 0, 6.6), (0, sy * 2.6, 6.4), .08, .08, M['metal'])
        obox(mb, (0, 0, 7.1), (0, sy * 2.6, 6.45), .05, .05, M['metal'])
        box(mb, -L / 2, sy * 2.2 - .015, 5.8, L / 2, sy * 2.2 + .015, 5.84, M['metal'], top=True, bottom=True)
        box(mb, -L / 2, sy * 2.2 - .015, 6.3, L / 2, sy * 2.2 + .015, 6.33, M['metal'], top=True, bottom=True)
        obox(mb, (0, sy * 2.2, 5.84), (0, sy * 2.2, 6.4), .03, .03, M['metal'])


def tram(mb, M, lo=False):
    """Two-section light-rail vehicle along X (36 m), white with a red band, window strip, doors, cab noses, roof gear,
    pantograph, headlights."""
    seg = 17.6
    def section(x0, x1, nose_a, nose_b):
        ys = 1.32
        prof = [(-ys, .45), (ys, .45), (ys + .05, 1.1), (ys, 3.0), (ys - .25, 3.45), (-ys + .25, 3.45), (-ys, 3.0), (-ys - .05, 1.1)]
        def ring(x, sc=1.0, zsc=1.0):
            return [(x, y * sc, .45 + (z - .45) * zsc) for y, z in prof]
        xs = [x0, x1]
        rings = [ring(x0 + (1.6 if nose_a else 0), 1, 1), ring(x1 - (1.6 if nose_b else 0), 1, 1)]
        if nose_a:
            rings.insert(0, ring(x0, .78, .9))
        if nose_b:
            rings.append(ring(x1, .78, .9))
        for A, B in zip(rings, rings[1:]):
            for i in range(len(prof)):
                a0, a1, b0, b1 = A[i], A[(i + 1) % len(prof)], B[i], B[(i + 1) % len(prof)]
                zc = (a0[2] + a1[2]) / 2
                m = M['tram'] if zc < 1.0 or zc > 3.1 else M['tram']
                mb.face([a0, b0, b1, a1], [(0, 0), (1, 0), (1, 1), (0, 1)], m, smooth=False)
        for R_, flip in ((rings[0], True), (rings[-1], False)):
            mb.face(R_ if flip else R_[::-1], [(0, 0)] * len(R_), M['tram'])
        xa, xb = x0 + (1.6 if nose_a else .3), x1 - (1.6 if nose_b else .3)
        for sy in (-1, 1):
            y = sy * 1.37
            box(mb, xa, y - .02, 1.75, xb, y + .02, 2.85, M['tinted'], top=False)                    # window band
            box(mb, xa, y - .03, 1.1, xb, y + .03, 1.45, M['tram_red'], top=False)
            for dx in (.3, .7):
                dxp = xa + (xb - xa) * dx
                box(mb, dxp - .65, y - .035, .55, dxp + .65, y + .035, 2.95, M['tinted'], top=False)
                box(mb, dxp - .7, y - .03, .5, dxp - .6, y + .03, 3.0, M['yellow'], top=False)
                box(mb, dxp + .6, y - .03, .5, dxp + .7, y + .03, 3.0, M['yellow'], top=False)
            box(mb, xa, y - .05, .25, xb, y + .05, .5, M['metal'], top=False)
        for nose, xn, sgn in ((nose_a, x0, -1), (nose_b, x1, 1)):
            if not nose:
                continue
            box(mb, xn - sgn * .05, -.95, 1.9, xn + sgn * .02, .95, 2.95, M['tinted'], top=False)
            for sy in (-1, 1):
                boxc(mb, xn + sgn * .02, sy * .75, 1.0, .1, .35, .2, M['glow_w'])
            boxc(mb, xn + sgn * .02, 0, 2.95, .1, 1.0, .25, M['glow'])
        boxc(mb, (x0 + x1) / 2, 0, 3.45, 5, 1.6, .5, M['mech'])
        for xb_ in (x0 + 3.5, x1 - 3.5):
            for sy in (-1, 1):
                for k in (-.9, .9):
                    cyl(mb, xb_ + k, sy * .72, .38, .38, .12, M['metal'], 10)
    section(-seg - .5, -.5, True, False)
    section(.5, seg + .5, False, True)
    box(mb, -.55, -1.25, .5, .55, 1.25, 3.3, M['rubber'])
    if not lo:
        obox(mb, (-1.2, 0, 3.95), (.2, 0, 5.3), .06, .06, M['metal'])
        obox(mb, (.2, 0, 5.3), (-1.0, 0, 5.85), .06, .06, M['metal'])
        box(mb, -1.6, -.8, 5.8, -.4, .8, 5.9, M['metal'])


def crane_mast(mb, M, H):
    """Tower crane mast: lattice section 2 m square on a concrete base, climbing frame near the top."""
    box(mb, -2.5, -2.5, 0, 2.5, 2.5, 1.2, M['rawconc'])
    lattice_box(mb, (0, 0, 1.2), (0, 0, H), 2.0, M['lattice'], 2.0, M['yellow'])
    box(mb, -1.4, -1.4, H - 6, 1.4, 1.4, H - 5.4, M['yellow'], bottom=True)
    box(mb, -1.1, -1.1, H - .4, 1.1, 1.1, H, M['yellow'], bottom=True)


def crane_jib(mb, M):
    """Slewing part of the tower crane (origin on the mast top): turntable, cab, 52 m jib, 16 m counter-jib with
    counterweights, apex with pendant ties, trolley and hook block, red lights on the tips."""
    cyl(mb, 0, 0, 0, 1.4, 1.2, M['yellow'], 16)
    box(mb, -1.2, 1.1, .4, 1.2, 3.4, 3.0, M['yellow'])
    box(mb, -1.0, 3.38, 1.0, 1.0, 3.45, 2.7, M['tinted'], top=False)
    J = 52.0
    lattice_box(mb, (1, 0, 2.0), (J, 0, 2.0), 1.6, M['lattice'], 1.6, M['yellow'])
    box(mb, J - .3, -.8, 1.2, J + .3, .8, 2.8, M['yellow'])
    lattice_box(mb, (-1, 0, 2.0), (-16, 0, 2.0), 1.8, M['lattice'], 1.8, M['yellow'])
    for k in range(4):
        box(mb, -15.5 + k * 1.3, -1.1, -.6, -14.3 + k * 1.3, 1.1, 2.6, M['rawconc'])
    box(mb, -10, -.9, 2.8, -3, .9, 3.0, M['metal'])
    lattice_box(mb, (0, 0, 1.2), (0, 0, 9.5), 1.6, M['lattice'], 1.6, M['yellow'])
    for p in ((J * .62, 0, 2.8), (-12, 0, 2.8)):
        obox(mb, (0, 0, 9.4), p, .06, .06, M['metal'])
    box(mb, 30, -.7, .9, 32.4, .7, 1.25, M['metal'])
    boxc(mb, 31.2, 0, -21.5, .04, .04, 22.4, M['metal'], top=False)
    boxc(mb, 31.2, 0, -22.5, .6, .45, 1.0, M['yellow'])
    for p in ((J + .1, 0, 2.9), (-16, 0, 2.9), (0, 0, 9.6)):
        blob(mb, *p, .25, .25, .25, M['glow_r'], 6, 4)


def kiosk(mb, M):
    box(mb, -1.6, -1.0, 0, 1.6, 1.0, 2.6, M['metal'])
    box(mb, -1.5, -1.02, 1.0, 1.5, -1.0, 2.2, M['tinted'], top=False)
    box(mb, -1.7, -1.6, 2.6, 1.7, 1.1, 2.9, M['awning_r'])
    box(mb, -1.5, -1.5, .95, 1.5, -1.0, 1.05, M['wood'])
    box(mb, -1.4, -1.03, 2.25, 1.4, -1.01, 2.55, M['glow_w'], top=False)
    mb.col(-1.6, -1.6, 0, 1.6, 1.0, 2.9)


def shelter(mb, M):
    box(mb, -2.2, -.05, 0, 2.2, .05, 2.4, M['glass'], top=False)
    for x in (-2.2, 2.2):
        box(mb, x - .05, -.05, 0, x + .05, 1.4, 2.4, M['glass'], top=False)
        boxc(mb, x, -.05, 0, .1, .1, 2.5, M['metal'])
    box(mb, -2.3, -.2, 2.5, 2.3, 1.6, 2.62, M['metal'], bottom=True)
    box(mb, 1.6, -.04, .3, 2.15, .04, 2.3, M['glow_w'], top=False)
    box(mb, -1.6, .2, .4, 1.2, .6, .5, M['wood'])
    mb.col(-2.3, -.2, 0, 2.3, 1.5, 2.6)


def planter(mb, M):
    box(mb, -1.3, -.6, 0, 1.3, .6, .6, M['trim'], top=False)
    box(mb, -1.2, -.5, .5, 1.2, .5, .55, M['soil'])
    for k, x in enumerate((-.7, 0, .7)):
        blob(mb, x, 0, .9, .55, .45, .45, M['plant'] if k != 1 else M['plant2'], 7, 4)
    for x in (-.35, .35):
        blob(mb, x, -.25, .75, .2, .15, .15, M['flowers'], 6, 3)
    mb.col(-1.3, -.6, 0, 1.3, .6, .7)


def cafe(mb, M):
    cyl(mb, 0, 0, 0, .05, 2.4, M['metal'], 6)
    cyl(mb, 0, 0, 2.1, 1.6, .55, M['awning_g'], 10, r2=.08)
    cyl(mb, 0, 0, 0, .3, .05, M['metal'], 8)
    cyl(mb, 0, 0, .72, .38, .04, M['metal_l'], 12)
    for sx in (-1, 1):
        box(mb, sx * .75 - .2, -.2, .44, sx * .75 + .2, .2, .48, M['metal'])
        box(mb, sx * .95 - .02 * sx - .02, -.2, .48, sx * .95 + .02, .2, .9, M['metal'])
        for k in ((-.15, -.15), (.15, .15), (-.15, .15), (.15, -.15)):
            boxc(mb, sx * .75 + k[0], k[1], 0, .03, .03, .44, M['metal'], top=False)
    mb.col(-1, -.4, 0, 1, .4, .9)


def bollards(mb, M):
    for k in range(5):
        cyl(mb, -4 + k * 2, 0, 0, .14, .95, M['metal'], 8)
        cyl(mb, -4 + k * 2, 0, .8, .145, .05, M['glow'], 8, top=False)


def signal(mb, M):
    """traffic signal: pole, mast arm over the road (+X), three heads"""
    cyl(mb, 0, 0, 0, .13, 6.2, M['metal'], 8)
    obox(mb, (0, 0, 5.9), (6.5, 0, 5.9), .12, .12, M['metal'])
    for x, lit in ((3.2, 'glow_g'), (6.0, 'glow_g'), (0.3, 'glow_r')):
        z = 5.1 if x > 1 else 2.6
        boxc(mb, x, -.2 if x > 1 else -.25, z, .38, .3, 1.05, M['metal'])
        for k, mm in enumerate(('glow_r', 'yellow', 'glow_g')):
            on = mm == (lit if x > 1 else 'glow_r')
            boxc(mb, x, -.36 if x > 1 else -.41, z + .78 - k * .3, .2, .03, .2, M[mm] if on and mm != 'yellow' else M['rubber'], top=False)
    boxc(mb, .2, -.15, 1.1, .2, .2, .3, M['yellow'])


def bin_(mb, M):
    cyl(mb, 0, 0, 0, .3, .95, M['metal'], 10)
    cyl(mb, 0, 0, .95, .33, .08, M['metal_l'], 10)


def hydrant(mb, M):
    cyl(mb, 0, 0, 0, .14, .62, M['red'], 8)
    cyl(mb, 0, 0, .62, .16, .12, M['red'], 8, r2=.06)
    obox(mb, (-.2, 0, .42), (.2, 0, .42), .1, .1, M['red'])


def banner(mb, M):
    """lamp pole with two hanging fabric banners"""
    cyl(mb, 0, 0, 0, .1, 6.2, M['metal'], 8)
    obox(mb, (0, 0, 6.1), (.9, 0, 5.9), .08, .08, M['metal'])
    boxc(mb, .9, 0, 5.4, .5, .3, .5, M['glow_w'])
    for sy, m in ((-1, 'awning_r'), (1, 'awning_b')):
        box(mb, -.02 + sy * .0, -.02, 3.0, .02, .02, 3.05, M['metal'])
        mb.face([(0, sy * .08, 2.9), (0, sy * .08 + sy * .8, 2.9), (0, sy * .08 + sy * .8, 4.6), (0, sy * .08, 4.6)][::sy], [(0, 0), (.25, 0), (.25, 1), (0, 1)], M[m])
        mb.face([(0, sy * .08, 2.9), (0, sy * .08, 4.6), (0, sy * .08 + sy * .8, 4.6), (0, sy * .08 + sy * .8, 2.9)][::sy], [(0, 0), (0, 1), (.25, 1), (.25, 0)], M[m])


def stringlights(mb, M, W=14.0):
    """a sagging wire of glowing bulbs across the pedestrian avenue (along Y), hung at 6 m"""
    n = 22
    pts = []
    for k in range(n + 1):
        t = k / n; y = -W / 2 + W * t; z = 6.2 - 1.2 * (1 - (2 * t - 1) ** 2)
        pts.append((0, y, z))
    for a, b in zip(pts, pts[1:]):
        obox(mb, a, b, .02, .02, M['metal'])
    for k, p in enumerate(pts[1:-1]):
        blob(mb, p[0], p[1], p[2] - .12, .09, .09, .11, M['glow'], 5, 3)


def sculpture(mb, M):
    """abstract plaza sculpture: three tilted steel rings on a granite plinth"""
    box(mb, -2.2, -2.2, 0, 2.2, 2.2, .6, M['granite'])
    for k in range(3):
        a = k * TAU / 3
        R_ = 2.6 - k * .45; n = 20
        tilt = .5 + k * .25
        pts = []
        for i in range(n + 1):
            t = i / n * TAU
            x, z = math.cos(t) * R_, math.sin(t) * R_
            y = 0
            x2, y2 = x * math.cos(a), x * math.sin(a)
            z2 = z * math.cos(tilt) + 3.6
            pts.append((x2 - math.sin(a) * z * math.sin(tilt) * .3, y2 + math.cos(a) * z * math.sin(tilt) * .3, z2))
        for p, q in zip(pts, pts[1:]):
            obox(mb, p, q, .22, .22, M['metal_l'] if k != 1 else M['copper'])
    mb.col(-2.2, -2.2, 0, 2.2, 2.2, 7)


def bikerack(mb, M):
    for k in range(5):
        x = -2 + k
        obox(mb, (x, -.3, 0), (x, -.3, .8), .05, .05, M['steel'])
        obox(mb, (x, .3, 0), (x, .3, .8), .05, .05, M['steel'])
        obox(mb, (x, -.3, .8), (x, .3, .8), .05, .05, M['steel'])


STREET = [
    ('DT_skywalk_28', lambda mb, M: skywalk(mb, M, 28.0), lambda mb, M: skywalk(mb, M, 28.0, True)),
    ('DT_skywalk_18', lambda mb, M: skywalk(mb, M, 18.0), lambda mb, M: skywalk(mb, M, 18.0, True)),
    ('DT_skywalk_10', lambda mb, M: skywalk(mb, M, 10.0), lambda mb, M: skywalk(mb, M, 10.0, True)),
    ('DT_platform', platform, lambda mb, M: platform(mb, M, True)),
    ('DT_track', track, lambda mb, M: track(mb, M, lo=True)),
    ('DT_catenary', catenary, None),
    ('DT_tram', tram, lambda mb, M: tram(mb, M, True)),
    ('DT_crane_mast_a', lambda mb, M: crane_mast(mb, M, 96.0), None),
    ('DT_crane_mast_b', lambda mb, M: crane_mast(mb, M, 48.0), None),
    ('DT_crane_jib', crane_jib, None),
    ('DT_kiosk', kiosk, None), ('DT_shelter', shelter, None), ('DT_planter', planter, None), ('DT_cafe', cafe, None),
    ('DT_bollards', bollards, None), ('DT_signal', signal, None), ('DT_bin', bin_, None), ('DT_hydrant', hydrant, None),
    ('DT_banner', banner, None), ('DT_stringlights', stringlights, None), ('DT_sculpture', sculpture, None),
    ('DT_bikerack', bikerack, None),
]


def build_street():
    bl.reset()
    M = mats()
    x = 0.0
    for name, fn, lofn in STREET:
        mb = MB(); fn(mb, M)
        x += 60
        r = make_root(name, mb, x, dict(col=mb.cols))
        if lofn:
            lo = MB(); lofn(lo, M)
            rl = make_root(name + '_lod', lo, x, dict(lod=True)); rl.location.y = 60
        print('[street] %-18s %6d tris' % (name, _tris(r)))


def preview_dump(prefix):
    """DT_PREVIEW=<dir>: one GLB per root (hero and lod) for tools/blender/preview.py contact sheets."""
    d = os.environ.get('DT_PREVIEW')
    if not d:
        return
    os.makedirs(d, exist_ok=True)
    for r in [o for o in bpy.context.scene.objects if o.parent is None and o.name.startswith('DT_')]:
        bpy.ops.object.select_all(action='DESELECT')
        for o in [r] + list(r.children_recursive):
            o.select_set(True)
        bpy.ops.export_scene.gltf(filepath=os.path.join(d, r.name + '.glb'), export_format='GLB', use_selection=True,
                                  export_apply=True, export_yup=True, export_extras=True)


def main():
    if not FAST or not os.path.exists(os.path.join(TEX, 'dt_curtain_c.jpg')):
        import downtown_textures
        downtown_textures.main()
    build_designs()
    preview_dump('b')
    p = bl.export('downtown.glb'); bl.quantize_glb(p)
    build_street()
    preview_dump('s')
    p = bl.export('downtown_street.glb'); bl.quantize_glb(p)


main()
