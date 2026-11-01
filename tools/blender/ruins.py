"""VANTHOS ruins: what is left of the city, long after its people (vanthos_ruins.glb, roots VR_*).

Designs (each VR_<name>, the standing ruins also VR_<name>_lod):
  towers     tower_a  concrete office tower sheared off diagonally, a corner collapsed, floor slabs and rebar exposed
             tower_b  stripped glass tower: top floors torn away, one face peeled open to its floor plates, leaning
             tower_c  slender residential tower snapped in half, a blast hole through its middle
  mid-rise   mid_a    long concrete apartment block, its east third fallen into the street
             mid_b    burnt-out brick corner building: roof and floors gone, a hollow shell you can walk into
             mid_c    concrete block with one whole facade fallen away (a dollhouse of dark rooms)
  low-rise   low_a    two-storey brick shop row, roof caved in, front half collapsed
             low_b    three-storey corner shell, two walls standing
             hall     a ruined market hall: brick arcades, rusted roof trusses, half the roof down, debris inside
             stub     the foundations of a building that came down: broken low walls and slab pieces
  rubble     mound_l, mound_m (rubble mounds you walk over; their surface is in the world height function),
             debris (a flat debris field), slabs (broken slabs leaning together)
  props      car_burnt, car_rust, bus_burnt, sign_fallen, lamp_down, barricade, remains, weeds_a, weeds_b
Extras `vr` (JSON) on each root: w / d / h (three space metres), `col` AABB colliders [x0,y0,z0,x1,y1,z1] in three space
relative to the root (fronts face three +z), `mound` [H, rx, rz, cx, cz] (a rubble surface: H * cos^2 falloff over an
ellipse, centred at cx/cz), `spots`: `inside` (sheltered ground-floor points for resident enemies), `perch` (high
standing points), `tree` (where something grows: rubble tops, roofs, the hall floor), `glow` (a rare dead lamp / emergency
glow that may flicker).
Materials (names are an API for src/worlds/vanthos/ruins.js): vr_conc / vr_brick / vr_frame facades, vr_slab raw concrete,
vr_slab_in (interior faces), vr_rubble, vr_rust, vr_burnt, vr_moss, vr_signs, vr_ivy and vr_weeds (alpha cut-outs). Every
mesh carries vertex colour (Col): grime and moss toward the ground, soot near broken edges, darker interiors.
No lit windows anywhere: the facade textures are blown out and dark.
Usage: blender --background --python tools/blender/ruins.py [-- --fast]   (--fast skips re-painting the textures)
       VR_PREVIEW=<dir> also writes one GLB per design for preview.py.
"""
import bpy, math, os, sys, json
from mathutils import Vector, Matrix
sys.path.insert(0, os.path.dirname(__file__))
import bl

FAST = '--fast' in sys.argv
TEX = bl.TEXTURES
TAU = math.tau
# facade tile sets: (tile width m, tile height m, bay width m, floor height m)
TILE = {'conc': (14.0, 14.0, 3.5, 3.5), 'brick': (14.4, 12.0, 3.6, 4.0), 'frame': (12.0, 16.0, 1.5, 4.0)}


# ---------------------------------------------------------------- materials
def tmat(name, tex, tint='#ffffff', rough=.85, metal=0.0, normal=True, aux=True, alpha=False, ext='_c.jpg'):
    """Textured material: colour map x tint (x vertex colour, exported as COLOR_0), optional normal / aux (G rough, B metal)."""
    if name in bl._MATS:
        return bl._MATS[name]
    m = bpy.data.materials.new(name)
    nt = m.node_tree; b = nt.nodes.get('Principled BSDF')
    b.inputs['Roughness'].default_value = rough; b.inputs['Metallic'].default_value = metal
    tn = nt.nodes.new('ShaderNodeTexImage'); tn.image = bpy.data.images.load(os.path.join(TEX, tex + ('.png' if alpha else ext)), check_existing=True)
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
            m.surface_render_method = 'DITHERED'
        except Exception:
            pass
        if hasattr(m, 'blend_method'):
            m.blend_method = 'CLIP'
    bl._MATS[name] = m
    return m


def mats():
    return dict(
        conc=tmat('vr_conc', 'vr_conc'), conc2=tmat('vr_conc_warm', 'vr_conc', '#e8d8c4'), conc3=tmat('vr_conc_grey', 'vr_conc', '#b8bcc0'),
        brick=tmat('vr_brick', 'vr_brick'), frame=tmat('vr_frame', 'vr_frame'),
        slab=tmat('vr_slab', 'vr_slab', aux=False), slab_in=tmat('vr_slab_in', 'vr_slab', '#8a8682', aux=False),
        rubble=tmat('vr_rubble', 'vr_rubble', aux=False), rust=tmat('vr_rust', 'vr_rust', rough=.8, metal=.4),
        burnt=tmat('vr_burnt', 'vr_burnt', rough=.85, metal=.4), moss=tmat('vr_moss', 'vr_moss', aux=False),
        signs=tmat('vr_signs', 'vr_signs', normal=False, aux=False),
        ivy=tmat('vr_ivy', 'vr_ivy', normal=False, aux=False, alpha=True), weeds=tmat('vr_weeds', 'vr_weeds', normal=False, aux=False, alpha=True),
        bone=bl.mat('vr_bone', '#a49c88', 0, .7), cloth=bl.mat('vr_cloth', '#3a3630', 0, .95), glass=bl.mat('vr_glass_dirty', '#2a3034', .6, .2),
        glow=bl.mat('vr_glow', '#ff3a20', 0, .4, emit='#ff3a20', strength=4),
    )


# ---------------------------------------------------------------- mesh builder (faces with per-corner UVs and colours)
class MB:
    def __init__(self, tone=1.0, seed=0):
        self.V, self.F, self.UV, self.M, self.C, self.mats, self.cols = [], [], [], [], [], [], []
        self.spots = {'inside': [], 'perch': [], 'tree': [], 'glow': []}
        self.tone = tone; self.seed = seed; self.xf = None
        self.sootz = None                    # f(x, y) -> height of the broken top there (soot below it)

    def mi(self, m):
        if m not in self.mats:
            self.mats.append(m)
        return self.mats.index(m)

    def shade(self, p, m):
        """vertex colour: grime + moss toward the ground, soot under broken tops, darker interiors, a building tone"""
        x, y, z = p
        k = self.tone * (.92 + .08 * math.sin(x * .37 + y * .21 + self.seed))
        g = min(1.0, max(0.0, z / 3.2))
        r, gg, b = k * (.62 + .38 * g), k * (.66 + .34 * g), k * (.5 + .5 * g)       # mossy, darker at the foot
        if self.sootz is not None:
            top = self.sootz(x, y)
            s = min(1.0, max(0.0, (z - (top - 5.0)) / 5.0))
            r *= 1 - .55 * s; gg *= 1 - .57 * s; b *= 1 - .58 * s
        n = m.name
        if n in ('vr_slab_in',):
            r *= .7; gg *= .7; b *= .72
        if n in ('vr_ivy', 'vr_weeds', 'vr_moss'):
            v = .8 + .2 * math.sin(x * 1.3 + y * .7 + z)
            r, gg, b = v, v, v * .95
        return (min(1, r), min(1, gg), min(1, b))

    def face(self, pts, uvs, m, cols=None):
        i0 = len(self.V); self.V += [tuple(p) for p in pts]
        self.F.append(tuple(range(i0, i0 + len(pts)))); self.UV.append(list(uvs)); self.M.append(self.mi(m))
        self.C.append(cols or [self.shade(p, m) for p in pts])

    def col(self, x0, y0, z0, x1, y1, z1):
        """collider in Blender coords -> three space"""
        self.cols.append([round(min(x0, x1), 2), round(min(z0, z1), 2), round(-max(y0, y1), 2),
                          round(max(x0, x1), 2), round(max(z0, z1), 2), round(-min(y0, y1), 2)])

    def spot(self, kind, x, y, z):
        self.spots[kind].append([round(x, 2), round(z, 2), round(-y, 2)])

    def transform(self, M4):
        self.V = [tuple(M4 @ Vector(v)) for v in self.V]

    def build(self, name):
        me = bpy.data.meshes.new(name)
        me.from_pydata(self.V, [], self.F)
        lay = me.uv_layers.new(name='UVMap')
        vc = me.color_attributes.new('Col', 'BYTE_COLOR', 'CORNER')
        for p, uvs, mi, cs in zip(me.polygons, self.UV, self.M, self.C):
            p.material_index = mi
            for li, uv, c in zip(p.loop_indices, uvs, cs):
                lay.data[li].uv = uv
                vc.data[li].color = (*c, 1)
        for m in self.mats:
            me.materials.append(m)
        me.validate(); me.update()
        o = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(o)
        return o


def quad_uv(a, b, h0, h1, tw, th):
    return [(a / tw, h0 / th), (b / tw, h0 / th), (b / tw, h1 / th), (a / tw, h1 / th)]


def box(mb, x0, y0, z0, x1, y1, z1, m, top=None, tile=4.0, bottom=True, col=False):
    x0, x1 = min(x0, x1), max(x0, x1); y0, y1 = min(y0, y1), max(y0, y1); z0, z1 = min(z0, z1), max(z0, z1)
    P = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    for i in range(4):
        a, b = P[i], P[(i + 1) % 4]
        L = math.dist(a, b); s0 = (a[0] + a[1])
        mb.face([(a[0], a[1], z0), (b[0], b[1], z0), (b[0], b[1], z1), (a[0], a[1], z1)], quad_uv(s0, s0 + L, z0, z1, tile, tile), m)
    mb.face([(x, y, z1) for x, y in P], [(x / tile, y / tile) for x, y in P], top or m)
    if bottom:
        mb.face([(x, y, z0) for x, y in reversed(P)], [(x / tile, y / tile) for x, y in reversed(P)], m)
    if col:
        mb.col(x0, y0, z0, x1, y1, z1)


def obox(mb, p0, p1, w, h, m, up=(0, 0, 1), tile=4.0):
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
        mb.face([a, b, d[(i + 1) % 4], d[i]], [(0, 0), (w / tile * 2, 0), (w / tile * 2, L / tile), (0, L / tile)], m)
    mb.face(list(reversed(c)), [(0, 0), (w / tile, 0), (w / tile, h / tile), (0, h / tile)], m)
    mb.face(d, [(0, 0), (w / tile, 0), (w / tile, h / tile), (0, h / tile)], m)


def chunk(mb, rg, cx, cy, cz, s, m, flat=.6):
    """an irregular lump of concrete (a box with jittered corners, rotated)"""
    R = Matrix.Rotation(rg.uniform(0, TAU), 4, 'Z') @ Matrix.Rotation(rg.uniform(-.5, .5), 4, 'X') @ Matrix.Rotation(rg.uniform(-.5, .5), 4, 'Y')
    hx, hy, hz = s * rg.uniform(.6, 1.1), s * rg.uniform(.5, 1.0), s * flat * rg.uniform(.5, 1.0)
    C = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            for sz in (-1, 1):
                v = Vector((sx * hx * rg.uniform(.7, 1.2), sy * hy * rg.uniform(.7, 1.2), sz * hz * rg.uniform(.7, 1.2)))
                C.append(R @ v + Vector((cx, cy, cz)))
    i = lambda sx, sy, sz: C[(sx > 0) * 4 + (sy > 0) * 2 + (sz > 0)]
    faces = [((-1, -1, -1), (1, -1, -1), (1, -1, 1), (-1, -1, 1)), ((1, -1, -1), (1, 1, -1), (1, 1, 1), (1, -1, 1)),
             ((1, 1, -1), (-1, 1, -1), (-1, 1, 1), (1, 1, 1)), ((-1, 1, -1), (-1, -1, -1), (-1, -1, 1), (-1, 1, 1)),
             ((-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)), ((-1, 1, -1), (1, 1, -1), (1, -1, -1), (-1, -1, -1))]
    for f in faces:
        pts = [i(*q) for q in f]
        mb.face(pts, [(p.x / 3 + p.z / 5, p.y / 3 + p.z / 4) for p in pts], m)


def rebar(mb, rg, p, d, n, M, L=(.6, 1.6)):
    """a few bent bars sticking out of a broken edge at p along direction d (droop down)"""
    for k in range(n):
        q = Vector(p) + Vector((rg.uniform(-.8, .8), rg.uniform(-.8, .8), rg.uniform(-.1, .1)))
        dv = Vector(d).normalized()
        a = q + dv * rg.uniform(*L) * .5 + Vector((0, 0, rg.uniform(-.25, .1)))
        b = a + dv * rg.uniform(*L) * .5 + Vector((rg.uniform(-.2, .2), rg.uniform(-.2, .2), -rg.uniform(.1, .7)))
        obox(mb, q, a, .035, .035, M['rust']); obox(mb, a, b, .035, .035, M['rust'])


def ivy(mb, rg, p, nrm, w, h, M, up=False):
    """a vine curtain on a wall: p = top centre (or bottom centre with up=True), nrm = wall outward normal (x, y)"""
    nx, ny = nrm
    tx, ty = -ny, nx
    o = .07
    x, y, z = p[0] + nx * o, p[1] + ny * o, p[2]
    z0, z1 = (z, z + h) if up else (z - h, z)
    a = (x - tx * w / 2, y - ty * w / 2); b = (x + tx * w / 2, y + ty * w / 2)
    if up:
        uv = [(0, 1), (1, 1), (1, 0), (0, 0)]
    else:
        uv = [(0, 0), (1, 0), (1, 1), (0, 1)]
    mb.face([(a[0], a[1], z0), (b[0], b[1], z0), (b[0], b[1], z1), (a[0], a[1], z1)], uv, M['ivy'])


def tuft(mb, rg, x, y, z, s, M, cell=0):
    """crossed weed cards (cell 0 grass, 1 broad weeds)"""
    u0, u1 = (0, .5) if cell == 0 else (.5, 1)
    a0 = rg.uniform(0, math.pi)
    for k in range(3):
        a = a0 + k * math.pi / 3
        dx, dy = math.cos(a) * s * .6, math.sin(a) * s * .6
        mb.face([(x - dx, y - dy, z), (x + dx, y + dy, z), (x + dx, y + dy, z + s), (x - dx, y - dy, z + s)], [(u0, 0), (u1, 0), (u1, 1), (u0, 1)], M['weeds'])


# ---------------------------------------------------------------- the parametric ruin
class Ruin:
    """A rectangular multi-storey ruin w x d (Blender x / y, front = -y), floors of fh metres, facade material `fac`.
    Damage: shear (a tilted cut plane with a jagged edge), corner blobs (collapsed corners), peel (a side whose facade has
    fallen away), holes (blast holes through a few floors). Walls are split into bay panels; missing panels show the
    floor plates, columns and dark interior faces behind them."""

    def __init__(self, M, rg, w, d, floors, fac='conc', facm=None, t=.3):
        self.M, self.rg, self.w, self.d, self.floors, self.fac = M, rg, w, d, floors, fac
        tw, th, bay, fh = TILE[fac]
        self.tw, self.th, self.bay, self.fh = tw, th, bay, fh
        self.facm = facm or M[fac]
        self.t = t
        self.nx = max(2, round(w / bay)); self.ny = max(2, round(d / bay))
        self.bx, self.by = w / self.nx, d / self.ny
        self.H = floors * fh
        self.shear = None; self.blobs = []; self.peel = set(); self.holes = []; self.front_open = .7
        self.jag = {}

    # damage queries ------------------------------------------------
    def cut(self, x, y):
        """height of the broken top above (x, y)"""
        top = self.H
        if self.shear:
            (dx, dy), z0, slope, amp = self.shear
            top = min(top, z0 + slope * (x * dx + y * dy))
        k = (round(x * 3.1), round(y * 3.1))
        if k not in self.jag:
            self.jag[k] = self.rg.uniform(-1, 1)
        return top + (self.jag[k] * self.shear[3] if self.shear else 0)

    def gone(self, x, y, z):
        if z > self.cut(x, y):
            return True
        for (cx, cy, cz, r, zs) in self.blobs:
            if math.hypot(x - cx, y - cy, (z - cz) * zs) < r:
                return True
        for (cx, cy, z0, z1, r) in self.holes:
            if z0 < z < z1 and math.hypot(x - cx, y - cy) < r:
                return True
        return False

    def sides(self):
        w, d = self.w / 2, self.d / 2
        # (start, end, outward normal, side id, bays)
        return [((-w, -d), (w, -d), (0, -1), 'S', self.nx), ((w, -d), (w, d), (1, 0), 'E', self.ny),
                ((w, d), (-w, d), (0, 1), 'N', self.nx), ((-w, d), (-w, -d), (-1, 0), 'W', self.ny)]

    # geometry ------------------------------------------------------
    def build(self, mb, lo=False):
        M, rg, fh, t = self.M, self.rg, self.fh, self.t
        mb.sootz = lambda x, y: self.cut(x, y)
        if lo:
            return self.build_lo(mb)
        # wall panels per side, floor and bay
        for (a, b, n, sid, nb) in self.sides():
            L = math.dist(a, b); ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
            bw = L / nb
            for f in range(self.floors):
                z0, z1 = f * fh, (f + 1) * fh
                for i in range(nb):
                    s0, s1 = i * bw, (i + 1) * bw
                    cx, cy = a[0] + ux * (s0 + s1) / 2 - n[0] * .5, a[1] + uy * (s0 + s1) / 2 - n[1] * .5
                    if sid in self.peel and f >= self.peel_from:
                        continue
                    if f == 0 and sid == 'S' and rg.random() < self.front_open:
                        continue                                       # shopfronts gone: the ground floor is open
                    if self.gone(cx, cy, (z0 + z1) / 2):
                        # partial panel under the broken top
                        top = self.cut(cx, cy)
                        if not (z0 < top < z1 and top - z0 > .9) or any(math.hypot(cx - bx, cy - by, ((z0 + top) / 2 - bz) * zs) < r for bx, by, bz, r, zs in self.blobs):
                            continue
                        zt0, zt1 = top + rg.uniform(-.6, .4), top + rg.uniform(-.6, .4)
                    else:
                        zt0 = zt1 = z1
                    self.panel(mb, a, (ux, uy), n, s0, s1, z0, zt0, zt1, sid, f, i, nb)
        # floor plates
        for f in range(1, self.floors + 1):
            self.plate(mb, f)
        # columns on a coarse grid
        for f in range(self.floors):
            z0 = f * fh
            for i in range(1, self.nx, 2):
                for j in range(1, self.ny, 2):
                    x = -self.w / 2 + i * self.bx; y = -self.d / 2 + j * self.by
                    if not self.gone(x, y, z0 + 1) and not self.gone(x, y, z0 + fh - .5):
                        box(mb, x - .3, y - .3, z0, x + .3, y + .3, z0 + fh - .3, M['slab_in'], bottom=False)
                        if f == 0:
                            mb.col(x - .3, y - .3, 0, x + .3, y + .3, fh)
        # ground floor interior: debris, the spots enemies hold
        for i in range(self.nx):
            for j in range(self.ny):
                x = -self.w / 2 + (i + .5) * self.bx; y = -self.d / 2 + (j + .5) * self.by
                if not self.gone(x, y, fh - .1) and i % 2 == 0 and j % 2 == 0 and 0 < i < self.nx - 1 and 0 < j < self.ny - 1:
                    mb.spot('inside', x, y, 0)
                if rg.random() < .25 and not self.gone(x, y, 1):
                    chunk(mb, rg, x + rg.uniform(-1, 1), y + rg.uniform(-1, 1), .2, rg.uniform(.3, .7), M['slab_in'])
        # ground-floor colliders: wall runs (doors and missing panels stay open), the rest of the body as one block above
        self.colliders(mb)

    def panel(self, mb, a, u, n, s0, s1, z0, zt0, zt1, sid, f, i, nb):
        M, t = self.M, self.t
        ux, uy = u
        p0 = (a[0] + ux * s0, a[1] + uy * s0); p1 = (a[0] + ux * s1, a[1] + uy * s1)
        tw, th = self.tw, self.th
        # outer face (facade UVs: s along the side, v from the ground)
        mb.face([(p0[0], p0[1], z0), (p1[0], p1[1], z0), (p1[0], p1[1], zt1), (p0[0], p0[1], zt0)],
                [(s0 / tw, z0 / th), (s1 / tw, z0 / th), (s1 / tw, zt1 / th), (s0 / tw, zt0 / th)], self.facm)
        # inner face
        q0 = (p0[0] - n[0] * t, p0[1] - n[1] * t); q1 = (p1[0] - n[0] * t, p1[1] - n[1] * t)
        mb.face([(q1[0], q1[1], z0), (q0[0], q0[1], z0), (q0[0], q0[1], zt0), (q1[0], q1[1], zt1)],
                [(s1 / 4, z0 / 4), (s0 / 4, z0 / 4), (s0 / 4, zt0 / 4), (s1 / 4, zt1 / 4)], M['slab_in'])
        # broken top edge, and the side edges (wall thickness) where the neighbour panel is missing
        mb.face([(p0[0], p0[1], zt0), (p1[0], p1[1], zt1), (q1[0], q1[1], zt1), (q0[0], q0[1], zt0)], [(0, 0), (1, 0), (1, .08), (0, .08)], M['slab'])
        for (p, q, zt, flip) in ((p0, q0, zt0, True), (p1, q1, zt1, False)):
            pts = [(p[0], p[1], z0), (q[0], q[1], z0), (q[0], q[1], zt), (p[0], p[1], zt)]
            mb.face(pts if not flip else [pts[1], pts[0], pts[3], pts[2]], [(0, z0 / 4), (.08, z0 / 4), (.08, zt / 4), (0, zt / 4)], M['slab'])
        if zt0 < (f + 1) * self.fh - .2 and self.rg.random() < .5:
            rebar(mb, self.rg, ((p0[0] + p1[0]) / 2 - n[0] * t / 2, (p0[1] + p1[1]) / 2 - n[1] * t / 2, (zt0 + zt1) / 2), (0, 0, 1), 2, M, (.4, 1.0))

    def plate(self, mb, f):
        M, rg, fh = self.M, self.rg, self.fh
        z = f * fh
        nx, ny, bx, by = self.nx, self.ny, self.bx, self.by
        have = {}
        for i in range(nx):
            for j in range(ny):
                x = -self.w / 2 + (i + .5) * bx; y = -self.d / 2 + (j + .5) * by
                have[(i, j)] = not self.gone(x, y, z - .2)
        for (i, j), ok in have.items():
            if not ok:
                continue
            x0 = -self.w / 2 + i * bx; y0 = -self.d / 2 + j * by; x1, y1 = x0 + bx, y0 + by
            x = (x0 + x1) / 2; y = (y0 + y1) / 2
            exposed = self.gone(x, y, z + 1.0) or f == self.floors
            P = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
            mb.face([(px, py, z) for px, py in P], [(px / 4, py / 4) for px, py in P], M['moss'] if exposed and rg.random() < .55 else M['slab'])
            mb.face([(px, py, z - .32) for px, py in reversed(P)], [(px / 4, py / 4) for px, py in reversed(P)], M['slab_in'])
            if exposed and rg.random() < .18:
                mb.spot('tree', x, y, z)
            if exposed and rg.random() < .3:
                tuft(mb, rg, x + rg.uniform(-1, 1), y + rg.uniform(-1, 1), z, rg.uniform(.6, 1.2), M, rg.random() < .3)
            if exposed and rg.random() < .2:
                chunk(mb, rg, x + rg.uniform(-1, 1), y + rg.uniform(-1, 1), z + .2, rg.uniform(.3, .8), M['rubble'])
            # broken edges toward missing cells (inside the footprint): edge face, rebar, sometimes a drooping piece
            for (di, dj, e) in ((1, 0, ((x1, y0), (x1, y1))), (-1, 0, ((x0, y1), (x0, y0))), (0, 1, ((x1, y1), (x0, y1))), (0, -1, ((x0, y0), (x1, y0)))):
                nb_ = (i + di, j + dj)
                if nb_ in have and not have[nb_]:
                    (ax, ay), (bx_, by_) = e
                    mb.face([(ax, ay, z - .32), (bx_, by_, z - .32), (bx_, by_, z), (ax, ay, z)], [(0, 0), (1, 0), (1, .08), (0, .08)], M['slab'])
                    mid = ((ax + bx_) / 2, (ay + by_) / 2, z - .15)
                    if rg.random() < .6:
                        rebar(mb, rg, mid, (di, dj, 0), 3, M)
                    if rg.random() < .25:
                        L = rg.uniform(1.2, 2.6); dn = rg.uniform(.5, 1.2)
                        obox(mb, (mid[0] + di * .2, mid[1] + dj * .2, z - .1), (mid[0] + di * L * .6, mid[1] + dj * L * .6, z - .1 - L * dn),
                             max(bx, by) * rg.uniform(.4, .8), .28, M['slab'], up=(di, dj, 0) if (di or dj) else (0, 0, 1))

    def build_lo(self, mb):
        """far LOD: each bay column is one quad (facade) up to the highest standing panel, an interior face behind it"""
        M, fh = self.M, self.fh
        for (a, b, n, sid, nb) in self.sides():
            L = math.dist(a, b); ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
            bw = L / nb
            for i in range(nb):
                s0, s1 = i * bw, (i + 1) * bw
                cx, cy = a[0] + ux * (s0 + s1) / 2 - n[0] * .5, a[1] + uy * (s0 + s1) / 2 - n[1] * .5
                top = 0
                for f in range(self.floors):
                    if sid in self.peel and f >= self.peel_from:
                        break
                    if self.gone(cx, cy, (f + .5) * fh):
                        c = self.cut(cx, cy)
                        if f * fh < c < (f + 1) * fh:
                            top = c
                        break
                    top = (f + 1) * fh
                if top < 1:
                    continue
                p0 = (a[0] + ux * s0, a[1] + uy * s0); p1 = (a[0] + ux * s1, a[1] + uy * s1)
                mb.face([(p0[0], p0[1], 0), (p1[0], p1[1], 0), (p1[0], p1[1], top), (p0[0], p0[1], top)],
                        [(s0 / self.tw, 0), (s1 / self.tw, 0), (s1 / self.tw, top / self.th), (s0 / self.tw, top / self.th)], self.facm)
                q0 = (p0[0] - n[0] * .3, p0[1] - n[1] * .3); q1 = (p1[0] - n[0] * .3, p1[1] - n[1] * .3)
                mb.face([(q1[0], q1[1], 0), (q0[0], q0[1], 0), (q0[0], q0[1], top), (q1[0], q1[1], top)], [(0, 0), (1, 0), (1, 1), (0, 1)], M['slab_in'])
        # the highest standing plate as one cap (aerial views)
        for f in range(self.floors, 0, -1):
            z = f * fh
            pts = [(x, y) for x in (-self.w / 2 + .3, self.w / 2 - .3) for y in (-self.d / 2 + .3, self.d / 2 - .3)]
            if not any(self.gone(x * .5, y * .5, z - .2) for x, y in pts):
                P = [(-self.w / 2, -self.d / 2), (self.w / 2, -self.d / 2), (self.w / 2, self.d / 2), (-self.w / 2, self.d / 2)]
                mb.face([(x, y, z) for x, y in P], [(x / 4, y / 4) for x, y in P], M['slab'])
                break

    def colliders(self, mb):
        fh, t = self.fh, self.t
        w, d = self.w / 2, self.d / 2
        # ground floor: one box per side (the open front is left open; enter through it)
        for (a, b, n, sid, nb) in self.sides():
            if sid == 'S' and self.front_open > .3:
                # two short returns at the corners
                mb.col(-w, -d, 0, -w + 1.2, -d + t, fh)
                mb.col(w - 1.2, -d, 0, w, -d + t, fh)
                continue
            x0, x1 = min(a[0], b[0]), max(a[0], b[0]); y0, y1 = min(a[1], b[1]), max(a[1], b[1])
            if n[0]:
                xx = a[0]
                mb.col(xx - t if n[0] > 0 else xx, y0, 0, xx if n[0] > 0 else xx + t, y1, fh)
            else:
                yy = a[1]
                mb.col(x0, yy - t if n[1] > 0 else yy, 0, x1, yy if n[1] > 0 else yy + t, fh)
        # the floors above as one block where the building still stands (a ceiling over the ground floor)
        top = min(self.H, max(self.cut(x, y) for x in (-w * .6, 0, w * .6) for y in (-d * .6, 0, d * .6)))
        if top > fh + 1:
            mb.col(-w, -d, fh - .35, w, d, top)


def make_root(name, mb, x, meta):
    r = bl.empty(name, (x, 0, 0))
    o = mb.build(name + '_mesh'); o.parent = r
    meta = dict(meta)
    meta.setdefault('col', mb.cols)
    meta.setdefault('spots', {k: v for k, v in mb.spots.items() if v})
    r['vr'] = json.dumps(meta)
    return r


def lean(mb, deg, pivot_y, axis='X'):
    M4 = Matrix.Translation((0, pivot_y, 0)) @ Matrix.Rotation(math.radians(deg), 4, axis) @ Matrix.Translation((0, -pivot_y, 0))
    mb.transform(M4)


# ---------------------------------------------------------------- designs
class R_:
    def __init__(self, seed):
        import random
        self.r = random.Random(seed)

    def uniform(self, a, b):
        return self.r.uniform(a, b)

    def random(self):
        return self.r.random()

    def randint(self, a, b):
        return self.r.randint(a, b)

    def choice(self, s):
        return self.r.choice(s)


def facade_ivy(mb, rg, R, n=4, M=None):
    """vines hanging from broken tops and creeping up from the street on random wall spots"""
    for k in range(n):
        side = R.sides()[rg.randint(0, 3)]
        (a, b, nrm, sid, nb) = side
        L = math.dist(a, b); s = rg.uniform(.15, .85) * L
        ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        x, y = a[0] + ux * s, a[1] + uy * s
        if sid in R.peel:
            continue
        top = min(R.cut(x - nrm[0], y - nrm[1]), R.H)
        if rg.random() < .5:
            h = rg.uniform(4, 10); z = min(top - .3, rg.uniform(4, top))
            if z - h < 0:
                h = z
            if h > 2:
                ivy(mb, rg, (x, y, z), nrm, rg.uniform(2, 3.5), h, M)
        else:
            ivy(mb, rg, (x, y, 0), nrm, rg.uniform(2.5, 4), min(top - .5, rg.uniform(3, 8)), M, up=True)


def base_rubble(mb, rg, M, cx, cy, r, n, z=0.0):
    for k in range(n):
        a = rg.uniform(0, TAU); dd = rg.uniform(0, r)
        chunk(mb, rg, cx + math.cos(a) * dd, cy + math.sin(a) * dd, z + rg.uniform(.1, .4), rg.uniform(.3, 1.1), M['rubble'] if k % 3 else M['slab'])


def mound_mesh(mb, rg, M, H, rx, ry, cx=0.0, cy=0.0, n=22, chunks=26, slabs=5, lo=False):
    """rubble mound: a heightfield H * cos^2 over an ellipse (the runtime walks the same smooth surface) with lumps on
    it that only rise above it, then chunks, broken slabs, beams and rebar"""
    def h(u, v):
        d = math.hypot(u, v)
        return H * math.cos(min(1, d) * math.pi / 2) ** 2 if d < 1 else 0.0
    nr, ns = (4, 10) if lo else (10, 26)
    ring = []
    for i in range(nr + 1):
        rho = i / nr * 1.03
        row = []
        for j in range(ns):
            a = j / ns * TAU + (i % 2) * .5 / ns * TAU
            u, v = math.cos(a) * rho, math.sin(a) * rho
            bump = 0 if lo or i in (0, nr) else abs(math.sin(i * 1.7 + j * 2.3) * math.cos(i * .9 - j * 1.4)) * .35 * (1 - rho)
            row.append((cx + u * rx, cy + v * ry, h(u, v) + bump - (.08 if i == nr else .03)))
        ring.append(row)
    top = (cx, cy, H)
    for j in range(ns):
        q = [top, ring[1][j], ring[1][(j + 1) % ns]]
        mb.face(q, [(p[0] / 4, p[1] / 4) for p in q], M['rubble'])
    for i in range(1, nr):
        for j in range(ns):
            q = [ring[i][j], ring[i + 1][j], ring[i + 1][(j + 1) % ns], ring[i][(j + 1) % ns]]
            mb.face(q, [(p[0] / 4, p[1] / 4) for p in q], M['rubble'])
    if lo:
        return
    for k in range(chunks):
        a = rg.uniform(0, TAU); dd = math.sqrt(rg.uniform(0, 1)) * .9
        u, v = math.cos(a) * dd, math.sin(a) * dd
        x, y = cx + u * rx, cy + v * ry
        s = rg.uniform(.4, 1.3) * (1.3 - dd * .6)
        chunk(mb, rg, x, y, h(u, v) + s * .2, s, M['slab'] if k % 3 == 0 else M['rubble'])
    for k in range(slabs):                                         # broken floor slabs sticking out at an angle
        a = rg.uniform(0, TAU); dd = rg.uniform(.1, .6)
        u, v = math.cos(a) * dd, math.sin(a) * dd
        x, y = cx + u * rx, cy + v * ry; z = h(u, v)
        L = rg.uniform(3, 6); b = rg.uniform(0, TAU); tilt = rg.uniform(.3, .9)
        p0 = (x, y, z - .6); p1 = (x + math.cos(b) * L * math.cos(tilt), y + math.sin(b) * L * math.cos(tilt), z - .6 + L * math.sin(tilt) * .7)
        obox(mb, p0, p1, rg.uniform(2, 3.5), .3, M['slab'], up=(math.cos(b + 1.57), math.sin(b + 1.57), 0))
        rebar(mb, rg, p1, (p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]), 3, M)
    for k in range(3):                                             # a rusted beam
        a = rg.uniform(0, TAU); dd = rg.uniform(.1, .7)
        x, y = cx + math.cos(a) * dd * rx, cy + math.sin(a) * dd * ry; z = h(math.cos(a) * dd, math.sin(a) * dd)
        b = rg.uniform(0, TAU); L = rg.uniform(4, 8)
        obox(mb, (x, y, z - .3), (x + math.cos(b) * L, y + math.sin(b) * L, z - .3 + rg.uniform(-1, 2.5)), .3, .45, M['rust'])
    for k in range(int(rx * ry / 18)):
        a = rg.uniform(0, TAU); dd = math.sqrt(rg.uniform(0, 1)) * .95
        u, v = math.cos(a) * dd, math.sin(a) * dd
        tuft(mb, rg, cx + u * rx, cy + v * ry, h(u, v) - .05, rg.uniform(.5, 1.1), M, rg.random() < .35)
    for k in range(int(1 + rx * ry / 90)):
        a = rg.uniform(0, TAU); dd = rg.uniform(.1, .55)
        mb.spot('tree', cx + math.cos(a) * dd * rx, cy + math.sin(a) * dd * ry, h(math.cos(a) * dd, math.sin(a) * dd) - .2)
    mb.spot('perch', cx, cy, H)


# --- towers
def tower_a(mb, M, lo, rg):
    """concrete office tower, 14 floors, sheared off on a slant, the north-east corner gone down to the 5th floor"""
    R = Ruin(M, rg, 24.5, 21, 14, 'conc')
    R.shear = ((.8, .6), 41.0, -.45, 1.2)
    R.blobs = [(12.5, 10.5, 30, 9.0, .45)]
    R.holes = [(-6, -10.5, 17, 24, 4.5)]
    R.build(mb, lo)
    if not lo:
        facade_ivy(mb, rg, R, 6, M)
        mound_mesh(mb, rg, M, 3.2, 9, 8, 15, 13, chunks=18, slabs=3)
        mb.spot('glow', -12.5 + 2, -10.5 - .2, 2.6)
    return dict(w=24.5, d=21, h=R.H, mound=[3.2, 9, 8, 15, -13], kind='tower')


def tower_b(mb, M, lo, rg):
    """stripped glass tower, 18 floors (4 m): its top torn off, the east face peeled to the floors, leaning a few degrees"""
    R = Ruin(M, rg, 22.5, 22.5, 18, 'frame', t=.25)
    R.shear = ((0, 1), 62.0, -.25, 2.4)
    R.peel = {'E'}; R.peel_from = 3
    R.blobs = [(-11, -11, 6, 5.0, .7)]
    R.build(mb, lo)
    if not lo:
        facade_ivy(mb, rg, R, 4, M)
        mound_mesh(mb, rg, M, 2.4, 6, 9, 16, 0, chunks=16, slabs=3)
    lean(mb, -3.5, 11.25)
    return dict(w=22.5, d=22.5, h=R.H, kind='tower', mound=[2.4, 6, 9, 16, 0])


def tower_c(mb, M, lo, rg):
    """slender residential tower snapped at the 11th floor, a blast hole through floors 5-7"""
    R = Ruin(M, rg, 17.5, 17.5, 20, 'conc', facm=M['conc2'])
    R.shear = ((1, 0), 39.0, .3, 2.0)
    R.holes = [(0, -8.75, 17, 25, 5.5), (8.75, 2, 18, 23, 4.0)]
    R.build(mb, lo)
    if not lo:
        facade_ivy(mb, rg, R, 6, M)
        # the upper half lies broken in the street behind it
        mound_mesh(mb, rg, M, 4.2, 10, 14, 0, 22, chunks=22, slabs=6)
    return dict(w=17.5, d=17.5, h=R.H, mound=[4.2, 10, 14, 0, -22], kind='tower')


# --- mid-rise
def mid_a(mb, M, lo, rg):
    """six-storey apartment slab 31.5 x 14, the east third fallen into the street"""
    R = Ruin(M, rg, 31.5, 14, 6, 'conc', facm=M['conc3'])
    R.blobs = [(17, 0, 0, 12.0, .55)]
    R.shear = ((-1, 0), 21.0, -.05, .9)
    R.build(mb, lo)
    if not lo:
        facade_ivy(mb, rg, R, 5, M)
        mound_mesh(mb, rg, M, 4.0, 9, 9, 15, -2, chunks=24, slabs=5)
        # balconies hanging from the south face
        for f in range(1, 5):
            for i in range(0, 6, 2):
                x = -14 + i * 3.5
                if R.gone(x, -7.5, f * 3.5):
                    continue
                if rg.random() < .25:
                    obox(mb, (x - 1.5, -7.3, f * 3.5), (x - 1.2, -8.6, f * 3.5 - 1.6), 2.6, .2, M['slab'], up=(1, 0, 0))
                else:
                    box(mb, x - 1.5, -8.6, f * 3.5 - .2, x + 1.5, -7, f * 3.5, M['slab'])
                    obox(mb, (x - 1.5, -8.55, f * 3.5 + 1), (x + 1.5, -8.55, f * 3.5 + .7 + rg.uniform(-.4, .1)), .05, .05, M['rust'])
    return dict(w=31.5, d=14, h=R.H, mound=[4.0, 9, 9, 15, 2], kind='mid')


def mid_b(mb, M, lo, rg):
    """burnt-out brick corner building, 5 x 4 m floors: roof and every floor gone, a hollow shell"""
    R = Ruin(M, rg, 18, 18, 5, 'brick')
    R.shear = ((.7, -.7), 18.5, -.25, 1.6)
    R.front_open = .5
    if lo:
        R.build(mb, True)
        return dict(w=18, d=18, h=R.H, kind='mid')
    mb.sootz = lambda x, y: R.cut(x, y)
    # walls only (no plates, no columns), windows on every floor; the inside is a debris heap with weeds
    for (a, b, n, sid, nb) in R.sides():
        L = math.dist(a, b); ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        bw = L / nb
        for f in range(R.floors):
            z0, z1 = f * R.fh, (f + 1) * R.fh
            for i in range(nb):
                s0, s1 = i * bw, (i + 1) * bw
                cx, cy = a[0] + ux * (s0 + s1) / 2, a[1] + uy * (s0 + s1) / 2
                if f == 0 and sid == 'S' and i in (1, 2):
                    continue                                   # the old shop door, blown wide
                top = R.cut(cx, cy)
                if top <= z0 + .9:
                    continue
                zt0 = zt1 = z1
                if top < z1:
                    zt0, zt1 = top + rg.uniform(-.6, .3), top + rg.uniform(-.6, .3)
                R.panel(mb, a, (ux, uy), n, s0, s1, z0, zt0, zt1, sid, f, i, nb)
    # joist pockets and a few charred beams still spanning
    for k in range(4):
        z = (k % 3 + 1) * 4 - .3
        y = rg.uniform(-7, 7)
        obox(mb, (-8.8, y, z), (8.8, y + rg.uniform(-1, 1), z - rg.uniform(0, 2.5)), .25, .3, M['burnt'])
    mound_mesh(mb, rg, M, 2.4, 7.5, 7.5, 0, 0, chunks=20, slabs=4)
    for k in range(3):
        mb.spot('inside', rg.uniform(-5, 5), rg.uniform(-5, 5), 0)
    facade_ivy(mb, rg, R, 4, M)
    R.colliders(mb)
    mb.cols = [c for c in mb.cols if c[4] - c[1] < 5]               # no ceiling block: it is open to the sky
    return dict(w=18, d=18, h=R.H, mound=[2.4, 7.5, 7.5, 0, 0], kind='mid')


def mid_c(mb, M, lo, rg):
    """seven-storey concrete block 24.5 x 17.5, its whole north face fallen away: a dollhouse of dark rooms"""
    R = Ruin(M, rg, 24.5, 17.5, 7, 'conc')
    R.peel = {'N'}; R.peel_from = 1
    R.shear = ((1, 0), 24.5, -.12, 1.0)
    R.blobs = [(-12, 8, 22, 6.0, .8)]
    R.build(mb, lo)
    if not lo:
        # partition walls inside, now visible from the north
        for f in range(1, 7):
            for x in (-7, 0, 7):
                if not R.gone(x, 5, f * 3.5 + 1.5) and rg.random() < .7:
                    box(mb, x - .1, 1, f * 3.5, x + .1, 8.6, f * 3.5 + 3.1, M['slab_in'], bottom=False)
        facade_ivy(mb, rg, R, 4, M)
        mound_mesh(mb, rg, M, 3.0, 13, 6, 0, 15, chunks=22, slabs=5)
    return dict(w=24.5, d=17.5, h=R.H, mound=[3.0, 13, 6, 0, -15], kind='mid')


# --- low-rise
def low_a(mb, M, lo, rg):
    """two-storey brick shop row 28.8 x 12, roof caved in, the front half of the east end down in the street"""
    R = Ruin(M, rg, 28.8, 12, 2, 'brick', facm=M['brick'])
    R.blobs = [(10, -6, 4, 6.5, .6)]
    R.front_open = .6
    R.build(mb, lo)
    if not lo:
        # the roof: rusted sheets on a few rafters, sagging into the gap
        for k in range(8):
            x = -13 + k * 3.6
            if R.gone(x, 0, 7.5):
                continue
            obox(mb, (x, -6, 8), (x + rg.uniform(-.3, .3), 6, 8 - rg.uniform(0, 1.5)), .15, .25, M['burnt'])
        facade_ivy(mb, rg, R, 4, M)
        mound_mesh(mb, rg, M, 2.2, 6, 5, 10, -9, chunks=14, slabs=2)
        for x in (-10, -3):
            mb.spot('glow', x, -6.1, 3.2) if rg.random() < .3 else None
    return dict(w=28.8, d=12, h=8, mound=[2.2, 6, 5, 10, 9], kind='low')


def low_b(mb, M, lo, rg):
    """a three-storey corner shell: two walls standing, a floor stub hanging between them"""
    R = Ruin(M, rg, 14, 14, 3, 'conc', facm=M['conc2'])
    R.shear = ((.7, .7), 9.5, -.3, 1.4)
    R.peel = {'N', 'E'}; R.peel_from = 0
    R.build(mb, lo)
    if not lo:
        facade_ivy(mb, rg, R, 3, M)
        mound_mesh(mb, rg, M, 2.6, 8, 8, 3, 3, chunks=18, slabs=4)
    return dict(w=14, d=14, h=10.5, mound=[2.6, 8, 8, 3, -3], kind='low')


def hall(mb, M, lo, rg):
    """ruined market hall 40 x 24 m: brick arcades, rusted roof trusses, half of the roof down inside"""
    W, D, H = 40.0, 24.0, 9.0
    if lo:
        R = Ruin(M, rg, W, D, 2, 'brick'); R.build_lo(mb)
        return dict(w=W, d=D, h=H, kind='hall')
    mb.sootz = lambda x, y: H + 2
    bay = 5.0
    for (a, b, nrm) in (((-W / 2, -D / 2), (W / 2, -D / 2), (0, -1)), ((W / 2, -D / 2), (W / 2, D / 2), (1, 0)),
                        ((W / 2, D / 2), (-W / 2, D / 2), (0, 1)), ((-W / 2, D / 2), (-W / 2, -D / 2), (-1, 0))):
        L = math.dist(a, b); ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        n = round(L / bay); bw = L / n
        for i in range(n):
            s0, s1 = i * bw, (i + 1) * bw
            p0 = (a[0] + ux * s0, a[1] + uy * s0); p1 = (a[0] + ux * s1, a[1] + uy * s1)
            broken = rg.random() < .2
            ztop = H - (rg.uniform(1.5, 4) if broken else 0)
            # pier + spandrel above an arch-like opening (square-headed, 3 m wide, 5 m tall)
            pw = (bw - 3.2) / 2
            for (q0, q1, z0, z1) in ((s0, s0 + pw, 0, ztop), (s1 - pw, s1, 0, ztop), (s0 + pw, s1 - pw, 5.2, ztop)):
                P0 = (a[0] + ux * q0, a[1] + uy * q0); P1 = (a[0] + ux * q1, a[1] + uy * q1)
                tz = ztop + (rg.uniform(-.8, 0) if broken else 0)
                R = Ruin.__new__(Ruin); R.M = M; R.rg = rg; R.t = .5; R.tw, R.th = TILE['brick'][:2]; R.facm = M['brick']; R.fh = 99
                Ruin.panel(R, mb, a, (ux, uy), nrm, q0, q1, z0, tz, tz + (rg.uniform(-.6, .3) if broken else 0), 'x', 0, 0, 1)
            # colliders: the piers (the openings stay passable, except a few bricked or blocked)
            for (q0, q1) in ((s0, s0 + pw), (s1 - pw, s1)):
                P0 = (a[0] + ux * q0 - nrm[0] * .5, a[1] + uy * q0 - nrm[1] * .5); P1 = (a[0] + ux * q1, a[1] + uy * q1)
                mb.col(min(P0[0], P1[0]), min(P0[1], P1[1]), 0, max(P0[0], P1[0]), max(P0[1], P1[1]), ztop)
            if rg.random() < .25:
                chunk(mb, rg, (p0[0] + p1[0]) / 2 - nrm[0] * 1.5, (p0[1] + p1[1]) / 2 - nrm[1] * 1.5, .4, 1.0, M['rubble'])
    # roof trusses across the short span; the east half of the roof has fallen in
    for k in range(9):
        x = -W / 2 + 2.5 + k * 4.4
        down = x > 4
        if down and rg.random() < .6:
            # a fallen truss, one end still on the wall
            obox(mb, (x, -D / 2 + .5, H - .5), (x + rg.uniform(-2, 2), D / 2 - 6, .4), .3, .5, M['rust'])
            continue
        for (y0, y1, z0, z1) in ((-D / 2, 0, H, H + 4.5), (0, D / 2, H + 4.5, H)):
            obox(mb, (x, y0, z0), (x, y1, z1), .25, .4, M['rust'])
        obox(mb, (x, -D / 2, H), (x, D / 2, H), .2, .3, M['rust'])
        for y in (-6, 6):
            obox(mb, (x, y, H), (x, y * .4, H + 4.5 * (1 - abs(y * .4) / 12)), .12, .12, M['rust'])
        if not down:
            # what is left of the roof sheeting: rusted panels with gaps (light comes through)
            for (y0, y1, z0, z1) in ((-D / 2, 0, H, H + 4.5), (0, D / 2, H + 4.5, H)):
                for s in range(3):
                    if rg.random() < .35:
                        continue
                    ya, yb = y0 + (y1 - y0) * s / 3, y0 + (y1 - y0) * (s + 1) / 3
                    za, zb = z0 + (z1 - z0) * s / 3 + .3, z0 + (z1 - z0) * (s + 1) / 3 + .3
                    pts = [(x - 2.2, ya, za), (x + 2.2, ya, za), (x + 2.2, yb, zb), (x - 2.2, yb, zb)]
                    mb.face(pts, [(0, 0), (1, 0), (1, 1), (0, 1)], M['rust'])
                    mb.face(list(reversed(pts)), [(0, 0), (1, 0), (1, 1), (0, 1)], M['rust'])
    # inside: the fallen roof heap, old market counters, debris, weeds; spots for residents and trees
    mound_mesh(mb, rg, M, 2.0, 9, 7, 11, 2, chunks=18, slabs=3)
    for k in range(6):
        x = -15 + k * 4.5
        if rg.random() < .7:
            box(mb, x - 1.6, -3.4, 0, x + 1.6, -2.4, 1.0, M['slab'], col=True)
            if rg.random() < .5:
                box(mb, x - 1.6, 2.4, 0, x + 1.6, 3.4, 1.0, M['slab'], col=True)
    for k in range(20):
        tuft(mb, rg, rg.uniform(-18, 18), rg.uniform(-10, 10), 0, rg.uniform(.5, 1.0), M, rg.random() < .4)
    for k in range(12):
        chunk(mb, rg, rg.uniform(-18, 18), rg.uniform(-10, 10), .2, rg.uniform(.3, .8), M['slab'] if k % 2 else M['rubble'])
    for (x, y) in ((-14, 6), (-8, -7), (-2, 7), (-12, -1), (2, -1)):
        mb.spot('inside', x, y, 0)
    for (x, y) in ((12, 2), (6, -6)):
        mb.spot('tree', x, y, 0)
    mb.spot('glow', -19.4, 0, 4.0)
    return dict(w=W, d=D, h=H + 4.5, mound=[2.0, 9, 7, 11, -2], kind='hall')


def stub(mb, M, lo, rg):
    """the foundations of a building that came down: broken low walls, slab pieces, a weed-grown floor"""
    W, D = 26.0, 20.0
    if lo:
        return dict(w=W, d=D, h=2, kind='stub')
    mb.sootz = None
    for (a, b, nrm) in (((-W / 2, -D / 2), (W / 2, -D / 2), (0, -1)), ((W / 2, -D / 2), (W / 2, D / 2), (1, 0)),
                        ((W / 2, D / 2), (-W / 2, D / 2), (0, 1)), ((-W / 2, D / 2), (-W / 2, -D / 2), (-1, 0))):
        L = math.dist(a, b); ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        s = 0.0
        while s < L - .5:
            seg = min(L - s, rg.uniform(2, 5))
            h = rg.uniform(0, 2.6) if rg.random() < .75 else 0
            if h > .4:
                R = Ruin.__new__(Ruin); R.M = M; R.rg = rg; R.t = .3; R.tw, R.th = TILE['conc'][:2]; R.facm = M['conc']; R.fh = 99
                Ruin.panel(R, mb, a, (ux, uy), nrm, s, s + seg, 0, h + rg.uniform(-.3, .3), h + rg.uniform(-.3, .3), 'x', 0, 0, 1)
                p0 = (a[0] + ux * s, a[1] + uy * s); p1 = (a[0] + ux * (s + seg), a[1] + uy * (s + seg))
                mb.col(min(p0[0], p1[0]) - .15, min(p0[1], p1[1]) - .15, 0, max(p0[0], p1[0]) + .15, max(p0[1], p1[1]) + .15, h - .2)
            s += seg
    P = [(-W / 2, -D / 2), (W / 2, -D / 2), (W / 2, D / 2), (-W / 2, D / 2)]
    mb.face([(x, y, .05) for x, y in P], [(x / 4, y / 4) for x, y in P], M['slab'])
    for k in range(5):
        x, y = rg.uniform(-9, 9), rg.uniform(-7, 7); b = rg.uniform(0, TAU); L = rg.uniform(3, 6)
        obox(mb, (x, y, 0), (x + math.cos(b) * L, y + math.sin(b) * L, rg.uniform(.3, 2.2)), rg.uniform(2, 3), .3, M['slab'], up=(math.cos(b + 1.57), math.sin(b + 1.57), 0))
    for k in range(30):
        tuft(mb, rg, rg.uniform(-12, 12), rg.uniform(-9, 9), .05, rg.uniform(.5, 1.2), M, rg.random() < .4)
    for k in range(10):
        chunk(mb, rg, rg.uniform(-11, 11), rg.uniform(-8, 8), .25, rg.uniform(.3, .9), M['rubble'])
    for k in range(3):
        mb.spot('tree', rg.uniform(-8, 8), rg.uniform(-6, 6), 0)
    mb.spot('inside', 0, 0, 0)
    return dict(w=W, d=D, h=2.6, kind='stub')


# --- rubble
def mound_l(mb, M, lo, rg):
    mound_mesh(mb, rg, M, 6.0, 19, 16, chunks=60, slabs=10, lo=lo)
    return dict(w=38, d=32, h=6, mound=[6.0, 19, 16, 0, 0], kind='rubble')


def mound_m(mb, M, lo, rg):
    mound_mesh(mb, rg, M, 3.4, 11, 9, chunks=30, slabs=5, lo=lo)
    return dict(w=22, d=18, h=3.4, mound=[3.4, 11, 9, 0, 0], kind='rubble')


def debris(mb, M, lo, rg):
    for k in range(30):
        a, d = rg.uniform(0, TAU), math.sqrt(rg.uniform(0, 1)) * 9
        chunk(mb, rg, math.cos(a) * d, math.sin(a) * d * .7, .15, rg.uniform(.2, .9), M['rubble'] if k % 3 else M['slab'], .45)
    for k in range(3):
        x, y, b = rg.uniform(-6, 6), rg.uniform(-4, 4), rg.uniform(0, TAU)
        obox(mb, (x, y, .1), (x + math.cos(b) * 4, y + math.sin(b) * 4, .3), .25, .35, M['rust'])
    for k in range(14):
        tuft(mb, rg, rg.uniform(-9, 9), rg.uniform(-6, 6), 0, rg.uniform(.5, 1.0), M, rg.random() < .4)
    return dict(w=18, d=13, h=1, kind='rubble')


def slabs(mb, M, lo, rg):
    """broken floor slabs leaning together: cover and a scramble up"""
    for (p0, p1, w) in (((-4, 0, 0), (1.5, .3, 3.2), 3.2), ((4, .5, 0), (-.5, .2, 3.4), 3.0), ((0, -3, 0), (.3, 1, 2.2), 4.0)):
        obox(mb, p0, p1, w, .35, M['slab'], up=(0, 1, 0))
        rebar(mb, rg, p1, (p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]), 4, M)
    base_rubble(mb, rg, M, 0, 0, 5, 18)
    mb.col(-3.2, -2, 0, 3.2, 2, 2.8)
    mb.spot('perch', 0, 0, 3.4)
    return dict(w=10, d=8, h=3.6, kind='rubble')


# ---------------------------------------------------------------- props
def car_shell(mb, M, rg, mat, L=4.4, W=1.8, Hh=1.45, rims=True, flat=0.0):
    """a sedan body from slices: sill, waist, glasshouse (no glass), roof dented"""
    hw = W / 2
    prof = [(-L / 2, .35, .75), (-L / 2 + .2, .3, .95), (-L / 2 + 1.0, .3, 1.0), (-.6, .3, Hh - .02), (.9, .3, Hh), (L / 2 - .9, .3, 1.02),
            (L / 2 - .1, .3, .9), (L / 2, .35, .7)]
    z0 = -flat
    # sides
    for s in (-1, 1):
        for k in range(len(prof) - 1):
            (y0, b0, t0), (y1, b1, t1) = prof[k], prof[k + 1]
            pts = [(s * hw, y0, b0 + z0), (s * hw, y1, b1 + z0), (s * hw, y1, min(t1, 1.0) + z0), (s * hw, y0, min(t0, 1.0) + z0)]
            mb.face(pts if s > 0 else [pts[1], pts[0], pts[3], pts[2]], [(p[1] / 2, p[2] / 2) for p in (pts if s > 0 else [pts[1], pts[0], pts[3], pts[2]])], mat)
    # hood, roof, boot (top surface), with a dent in the roof
    tops = [(-L / 2, .75), (-L / 2 + 1.0, 1.0), (-.6, Hh - .1 - rg.uniform(0, .2)), (.9, Hh - rg.uniform(0, .3)), (L / 2 - .9, 1.02), (L / 2, .7)]
    for k in range(len(tops) - 1):
        (y0, za), (y1, zb) = tops[k], tops[k + 1]
        w0 = hw * (.82 if 1 <= k <= 3 else 1); w1 = hw * (.82 if 1 <= k + 1 <= 3 else 1)
        pts = [(-w0, y0, za + z0), (w0, y0, za + z0), (w1, y1, zb + z0), (-w1, y1, zb + z0)]
        if k in (1, 2) and k == 2:
            pass
        mb.face(pts, [(p[0] / 2, p[1] / 2) for p in pts], mat)
    # pillars of the glasshouse (the glass is gone)
    for y in (-.6 + .05, .9 - .05, L / 2 - .95):
        for s in (-1, 1):
            obox(mb, (s * hw * .9, y, 1.0 + z0), (s * hw * .82, y + (.15 if y > 0 else -.1), Hh - .05 + z0), .08, .08, mat)
    # ends
    for (y, z) in ((-L / 2, .75), (L / 2, .7)):
        pts = [(-hw, y, .35 + z0), (hw, y, .35 + z0), (hw, y, z + z0), (-hw, y, z + z0)]
        mb.face(pts if y > 0 else list(reversed(pts)), [(0, 0), (1, 0), (1, .3), (0, .3)], mat)
    # wheels: bare rims or flat tyres
    for s in (-1, 1):
        for y in (-L / 2 + .8, L / 2 - .8):
            r = .3 if rims else .34
            for k in range(8):
                a0, a1 = k / 8 * TAU, (k + 1) / 8 * TAU
                pts = [(s * (hw - .05), y + math.cos(a0) * r, .34 - flat * .5 + math.sin(a0) * r), (s * (hw - .05), y + math.cos(a1) * r, .34 - flat * .5 + math.sin(a1) * r),
                       (s * (hw - .3), y + math.cos(a1) * r, .34 - flat * .5 + math.sin(a1) * r), (s * (hw - .3), y + math.cos(a0) * r, .34 - flat * .5 + math.sin(a0) * r)]
                mb.face(pts if s > 0 else list(reversed(pts)), [(0, 0), (1, 0), (1, 1), (0, 1)], M['rust'])
    # interior: burnt seat frames and darkness under the glasshouse
    mb.face([(-hw + .1, -L / 2 + 1, .5 + z0), (hw - .1, -L / 2 + 1, .5 + z0), (hw - .1, L / 2 - .9, .5 + z0), (-hw + .1, L / 2 - .9, .5 + z0)], [(0, 0), (1, 0), (1, 1), (0, 1)], M['burnt'])
    for y in (-.2, .9):
        obox(mb, (-.5, y, .55 + z0), (-.5, y + .1, 1.1 + z0), .45, .1, M['rust']); obox(mb, (.5, y, .55 + z0), (.5, y + .1, 1.1 + z0), .45, .1, M['rust'])


def car_burnt(mb, M, lo, rg):
    car_shell(mb, M, rg, M['burnt'], rims=True, flat=.18)
    for k in range(5):
        tuft(mb, rg, rg.uniform(-1.4, 1.4), rg.uniform(-2.6, 2.6), 0, rg.uniform(.4, .8), M, True)
    mb.col(-.9, -2.2, 0, .9, 2.2, 1.3)
    return dict(w=1.8, d=4.4, h=1.3, kind='prop')


def car_rust(mb, M, lo, rg):
    car_shell(mb, M, rg, M['rust'], rims=False, flat=.08)
    ivy(mb, rg, (.95, .4, 0), (1, 0), 2.2, 1.0, M, up=True)
    for k in range(8):
        tuft(mb, rg, rg.uniform(-1.6, 1.6), rg.uniform(-2.8, 2.8), 0, rg.uniform(.5, 1.0), M, rg.random() < .5)
    mb.col(-.9, -2.2, 0, .9, 2.2, 1.4)
    return dict(w=1.8, d=4.4, h=1.4, kind='prop')


def bus_burnt(mb, M, lo, rg):
    L, W, H = 11.5, 2.5, 3.0
    hw = W / 2
    for s in (-1, 1):
        # side: lower panel, window pillars (no glass), roof edge
        pts = [(s * hw, -L / 2, .4), (s * hw, L / 2, .4), (s * hw, L / 2, 1.3), (s * hw, -L / 2, 1.3)]
        mb.face(pts if s > 0 else [pts[1], pts[0], pts[3], pts[2]], [(p[1] / 2, p[2] / 2) for p in pts], M['burnt'])
        for k in range(9):
            y = -L / 2 + .3 + k * (L - .6) / 8
            obox(mb, (s * hw, y, 1.3), (s * hw, y, 2.85), .12, .12, M['burnt'])
        obox(mb, (s * hw, -L / 2, 2.9), (s * hw, L / 2, 2.9 - rg.uniform(0, .5)), .15, .2, M['burnt'])
    # roof (sagging, half burnt through)
    for k in range(6):
        if rg.random() < .3:
            continue
        y0, y1 = -L / 2 + k * L / 6, -L / 2 + (k + 1) * L / 6
        sag = .25 * math.sin(k / 5 * math.pi)
        pts = [(-hw, y0, 2.95 - sag), (hw, y0, 2.95 - sag), (hw, y1, 2.95 - sag), (-hw, y1, 2.95 - sag)]
        mb.face(pts, [(0, 0), (1, 0), (1, 1), (0, 1)], M['burnt']); mb.face(list(reversed(pts)), [(0, 0), (1, 0), (1, 1), (0, 1)], M['burnt'])
    for y in (-L / 2, L / 2):
        pts = [(-hw, y, .4), (hw, y, .4), (hw, y, 1.4), (-hw, y, 1.4)]
        mb.face(pts if y > 0 else list(reversed(pts)), [(0, 0), (1, 0), (1, .5), (0, .5)], M['burnt'])
    mb.face([(-hw, -L / 2, .45), (hw, -L / 2, .45), (hw, L / 2, .45), (-hw, L / 2, .45)], [(0, 0), (1, 0), (1, 4), (0, 4)], M['rust'])
    for k in range(6):
        y = -L / 2 + 1.5 + k * 1.6
        for s in (-1, 1):
            obox(mb, (s * .7, y, .5), (s * .7, y + .15, 1.4), .7, .12, M['rust'])
    for s in (-1, 1):
        for y in (-L / 2 + 1.8, L / 2 - 2.4):
            box(mb, s * hw - .1, y - .45, 0, s * hw + .05, y + .45, .5, M['rust'])
    for k in range(10):
        tuft(mb, rg, rg.uniform(-1.8, 1.8), rg.uniform(-6, 6), 0, rg.uniform(.5, 1.1), M, rg.random() < .4)
    mb.col(-hw, -L / 2, 0, hw, L / 2, 3.0)
    return dict(w=W, d=L, h=3, kind='prop')


def sign_fallen(row):
  def fn(mb, M, lo, rg):
    """a street sign on a bent post, the board half down in the weeds (vr_signs atlas row `row`, 0 at the top)"""
    obox(mb, (0, 0, 0), (0, .2, 1.8), .12, .12, M['rust'])
    obox(mb, (0, .2, 1.8), (.4, 2.6, 1.0), .12, .12, M['rust'])
    c = Vector((.6, 3.1, .55)); u = Vector((1, .15, 0)).normalized() * 1.5; v = Vector((0, -.35, 1)).normalized() * .38
    pts = [c - u - v, c + u - v, c + u + v, c - u + v]
    v0, v1 = 1 - (row + 1) / 4, 1 - row / 4
    mb.face(pts, [(0, v0), (1, v0), (1, v1), (0, v1)], M['signs'])
    mb.face([p - Vector((0, .04, 0)) for p in reversed(pts)], [(0, 0), (1, 0), (1, 1), (0, 1)], M['rust'])
    for k in range(6):
        tuft(mb, rg, rg.uniform(-1, 2), rg.uniform(0, 4), 0, rg.uniform(.4, .8), M)
    return dict(w=3, d=4, h=1.8, kind='prop')
  return fn


def lamp_down(mb, M, lo, rg):
    """a toppled street lamp lying across the kerb, its head smashed"""
    obox(mb, (0, 0, 0), (0, 0, .9), .22, .22, M['rust'])                                    # the stump
    obox(mb, (.2, .3, .12), (.4, 7.5, .2), .16, .16, M['rust'])                            # the fallen pole
    obox(mb, (.4, 7.5, .2), (1.5, 8.2, .35), .1, .1, M['rust'])
    box(mb, 1.2, 8.0, .05, 2.0, 8.6, .35, M['burnt'])
    return dict(w=2, d=9, h=.9, kind='prop')


def barricade(mb, M, lo, rg):
    """an old quarantine line: concrete barriers, a sagging rusted fence, a burnt-out tarp"""
    for k in range(5):
        x = -8 + k * 4 + rg.uniform(-.3, .3)
        a = rg.uniform(-.25, .25)
        c, s = math.cos(a), math.sin(a)
        pts = [(-1.8, -.35), (1.8, -.35), (1.8, .35), (-1.8, .35)]
        P = [(x + px * c - py * s, py * c + px * s) for px, py in pts]
        for i in range(4):
            a_, b_ = P[i], P[(i + 1) % 4]
            mb.face([(a_[0], a_[1], 0), (b_[0], b_[1], 0), (b_[0], b_[1], 1.0), (a_[0], a_[1], 1.0)], [(0, 0), (1, 0), (1, .3), (0, .3)], M['slab'])
        mb.face([(px, py, 1.0) for px, py in P], [(0, 0), (1, 0), (1, .2), (0, .2)], M['slab'])
        if rg.random() < .7:
            obox(mb, (x, .1, 1.0), (x + rg.uniform(-.3, .3), .1, 2.4 - rg.uniform(0, 1)), .06, .06, M['rust'])
    for k in range(5):
        obox(mb, (-10 + k * 4, .15, 2.3 - rg.uniform(0, .6)), (-6 + k * 4, .15, 2.3 - rg.uniform(0, .9)), .04, .04, M['rust'])
    mb.col(-10, -.5, 0, 10, .5, 1.0)
    for k in range(12):
        tuft(mb, rg, rg.uniform(-10, 10), rg.uniform(-1.5, 1.5), 0, rg.uniform(.4, .9), M, rg.random() < .3)
    return dict(w=20, d=1, h=2.4, kind='prop')


def remains(mb, M, lo, rg):
    """human remains, long bleached: a skull, ribs and long bones in torn cloth, half in the weeds (small and dim)"""
    def bone(p0, p1, r=.025):
        obox(mb, p0, p1, r * 2, r * 2, M['bone'], tile=.5)
    # skull: two stacked lumps
    chunk(mb, rg, .0, .0, .1, .1, M['bone'], .9)
    chunk(mb, rg, .03, .06, .07, .07, M['bone'], .9)
    for k in range(6):
        y = .25 + k * .05
        bone((-.12, y, .03), (.0, y + .02, .1), .012); bone((.12, y, .03), (.0, y + .02, .1), .012)
    bone((0, .2, .05), (0, .6, .05), .018)
    for (a, b) in (((.1, .62, .03), (.22, 1.05, .03)), ((-.1, .62, .03), (-.2, 1.04, .04)), ((.15, .25, .03), (.35, .5, .03)), ((-.15, .25, .03), (-.4, .35, .03))):
        bone(a, b)
    # cloth, torn and filthy
    pts = [(-.3, .15, .02), (.32, .2, .02), (.28, .7, .03), (-.25, .68, .02)]
    mb.face(pts, [(0, 0), (1, 0), (1, 1), (0, 1)], M['cloth'])
    for k in range(4):
        tuft(mb, rg, rg.uniform(-.5, .5), rg.uniform(0, 1), 0, rg.uniform(.3, .5), M)
    return dict(w=1, d=1.2, h=.2, kind='prop')


def weeds(cell):
    def fn(mb, M, lo, rg):
        for k in range(4):
            tuft(mb, rg, rg.uniform(-.4, .4), rg.uniform(-.4, .4), 0, rg.uniform(.6, 1.1), M, cell)
        return dict(w=1, d=1, h=1, kind='weeds')
    return fn


def glow_lamp(mb, M, lo, rg):
    """a dead emergency lamp: a cracked red cage on a bracket (the runtime flickers its vr_glow, rarely)"""
    box(mb, -.12, -.1, 0, .12, 0, .25, M['rust'])
    box(mb, -.09, -.18, .05, .09, -.1, .2, M['glow'])
    return dict(w=.3, d=.2, h=.25, kind='prop')


DESIGNS = [
    ('VR_tower_a', tower_a, True), ('VR_tower_b', tower_b, True), ('VR_tower_c', tower_c, True),
    ('VR_mid_a', mid_a, True), ('VR_mid_b', mid_b, True), ('VR_mid_c', mid_c, True),
    ('VR_low_a', low_a, True), ('VR_low_b', low_b, True), ('VR_hall', hall, True), ('VR_stub', stub, False),
    ('VR_mound_l', mound_l, True), ('VR_mound_m', mound_m, False), ('VR_debris', debris, False), ('VR_slabs', slabs, False),
    ('VR_car_burnt', car_burnt, False), ('VR_car_rust', car_rust, False), ('VR_bus_burnt', bus_burnt, False),
    ('VR_sign_a', sign_fallen(0), False), ('VR_sign_b', sign_fallen(2), False), ('VR_lamp_down', lamp_down, False), ('VR_barricade', barricade, False),
    ('VR_remains', remains, False), ('VR_weeds_a', weeds(0), False), ('VR_weeds_b', weeds(1), False), ('VR_glow_lamp', glow_lamp, False),
]


def _tris(root):
    t = 0
    for o in root.children:
        if o.type == 'MESH':
            t += sum(len(p.vertices) - 2 for p in o.data.polygons)
    return t


def build():
    bl.reset()
    M = mats()
    x = 0.0
    total = 0
    for k, (name, fn, has_lo) in enumerate(DESIGNS):
        seed = 1000 + k * 37
        mb = MB(1.0, seed); meta = fn(mb, M, False, R_(seed))
        x += 80
        r = make_root(name, mb, x, meta)
        t = _tris(r); total += t
        line = '[ruin] %-16s hero %6d tris' % (name, t)
        if has_lo:
            lo = MB(1.0, seed); fn(lo, M, True, R_(seed))
            rl = make_root(name + '_lod', lo, x, dict(lod=True, col=[], spots={}))
            rl.location.y = 80
            line += '   lod %5d tris' % _tris(rl)
        print(line, json.dumps({k2: meta[k2] for k2 in ('w', 'd', 'h')}), 'cols', len(mb.cols), 'spots', {k2: len(v) for k2, v in mb.spots.items() if v})
    print('[ruin] total hero tris', total)


def preview_dump():
    d = os.environ.get('VR_PREVIEW')
    if not d:
        return
    os.makedirs(d, exist_ok=True)
    for r in [o for o in bpy.context.scene.objects if o.parent is None and o.name.startswith('VR_')]:
        bpy.ops.object.select_all(action='DESELECT')
        for o in [r] + list(r.children_recursive):
            o.select_set(True)
        bpy.ops.export_scene.gltf(filepath=os.path.join(d, r.name + '.glb'), export_format='GLB', use_selection=True,
                                  export_apply=True, export_yup=True, export_extras=True, export_vertex_color='ACTIVE')


def main():
    if not FAST or not os.path.exists(os.path.join(TEX, 'vr_conc_c.jpg')):
        import vanthos_textures
        vanthos_textures.main()
    build()
    preview_dump()
    p = bl.export('vanthos_ruins.glb', export_vertex_color='ACTIVE')
    bl.quantize_glb(p)


main()
