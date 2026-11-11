"""Ruin-building toolkit for the operation levels (meridian.py): geometry accumulated in plan coordinates (metres: E, N,
up) per material, then built as Blender meshes with world-scale UVs.

  Geo                 vertex / face / material lists for one output mesh (a level chunk)
  box, prism, cyl, annulus, tube, path_deck, wall_path      hard-surface primitives (outward winding, flat or smooth)
  heap                a rubble mound (signed distances: a noisy mound with concrete chunks, Surface Nets)
  tower               a ruined tower: column grid, floor slabs on a cell grid, spandrels or cladding, mullions and the
                      odd pane of glass; a damage field (a ragged broken top plus blast holes) removes cells, columns and
                      facade, broken slab edges get fractured sides and rebar, a few slabs hang from their last edge,
                      rubble heaps round the base
  crystal_cluster     the Altered's void crystal growth (faceted shards, emissive)
  build               Geo -> Blender object (plan (E, N) -> Blender (N, -E): Unreal X = N, Y = E)

Materials (names are an API for the Unreal import): ru_concrete, ru_fracture, ru_asphalt, ru_stone, ru_metal, ru_panel,
ru_rubble, ru_banner (textured, ruins_textures.py), ru_glass, ru_glow, ru_beam, ru_block (invisible blockers).
"""
import bpy, math, os, random, sys
import numpy as np
from mathutils import Vector, Matrix, noise
sys.path.insert(0, os.path.dirname(__file__))
import bl
import sdf
from ruins_textures import TILE

TAU = 2 * math.pi
TEXTURED = ("ru_concrete", "ru_fracture", "ru_asphalt", "ru_stone", "ru_metal", "ru_panel", "ru_rubble", "ru_banner", "ru_hive",
            "ru_ceramic", "ru_composite", "ru_sandstone", "ru_corrugate", "ru_tile", "ru_plaster", "ru_brass", "ru_far_a", "ru_far_b",
            "ru_bark", "ru_leaf", "ru_moss", "ru_fungus")
# The zone being built (meridian.py sets it) and every rubble heap that collides, by zone: the plants grow over them.
ZONE = None
HEAPS = []
# What a tower() call builds: None = the old bare frame (the prototype); dict(styles=(...)) = a complete building of
# the district's architecture (citykit.building), dict(far=True) = a block of the far skyline. meridian.py sets it
# per zone.
CITY = None
_MATS = {}


# ------------------------------------------------------------------ materials
def _img(f, colour):
    im = bpy.data.images.load(os.path.join(bl.TEXTURES, f), check_existing=True)
    if not colour:
        im.colorspace_settings.name = 'Non-Color'
    return im


def material(name):
    if name in _MATS:
        return _MATS[name]
    if name in TEXTURED:
        m = bpy.data.materials.new(name)
        nt = m.node_tree
        b = nt.nodes['Principled BSDF']
        c = nt.nodes.new('ShaderNodeTexImage'); c.image = _img(name + '_c.jpg', True)
        nt.links.new(c.outputs['Color'], b.inputs['Base Color'])
        n = nt.nodes.new('ShaderNodeTexImage'); n.image = _img(name + '_n.png', False)
        nm = nt.nodes.new('ShaderNodeNormalMap')
        nt.links.new(n.outputs['Color'], nm.inputs['Color']); nt.links.new(nm.outputs['Normal'], b.inputs['Normal'])
        r = nt.nodes.new('ShaderNodeTexImage'); r.image = _img(name + '_m.png', False)
        sp = nt.nodes.new('ShaderNodeSeparateColor')
        nt.links.new(r.outputs['Color'], sp.inputs['Color'])
        nt.links.new(sp.outputs['Green'], b.inputs['Roughness'])
        nt.links.new(sp.outputs['Blue'], b.inputs['Metallic'])
    elif name == "ru_glass":
        m = bl.mat(name, '#0d1317', .7, .07)
    elif name == "ru_petal":
        m = bl.mat(name, '#8a3fd0', 0.0, .5, emit='#b04cff', strength=.5)
    elif name == "ru_paint":
        m = bl.mat(name, '#b9b6a8', 0.0, .7)
    elif name == "ru_block_dark":
        m = bl.mat(name, '#0b0c0d', .1, .75)
    elif name == "ru_sack":
        m = bl.mat(name, '#7a6c50', 0.0, .95)
    elif name == "ru_car_red":
        m = bl.mat(name, '#5f2019', .35, .45)
    elif name == "ru_car_blue":
        m = bl.mat(name, '#2f4a5e', .35, .45)
    elif name == "ru_car_white":
        m = bl.mat(name, '#a9a8a0', .3, .5)
    elif name == "ru_car_green":
        m = bl.mat(name, '#2b3a26', .25, .6)
    elif name == "ru_bio":
        m = bl.mat(name, '#3dffd0', 0.0, .35, emit='#3dffd0', strength=7.0)
    elif name == "ru_holo_cyan":
        m = bl.mat(name, '#35e0ff', 0.0, .4, emit='#35e0ff', strength=6.0)
    elif name == "ru_holo_magenta":
        m = bl.mat(name, '#ff3fb4', 0.0, .4, emit='#ff3fb4', strength=6.0)
    elif name == "ru_sign_amber":
        m = bl.mat(name, '#ffb040', 0.0, .4, emit='#ffb040', strength=5.0)
    elif name == "ru_glow":
        m = bl.mat(name, '#7b3cff', 0.0, .35, emit='#9a5cff', strength=9.0)
    elif name == "ru_beam":
        m = bl.mat(name, '#d9c2ff', 0.0, .3, emit='#c9a6ff', strength=30.0)
    elif name == "ru_block":
        m = bl.mat(name, '#ff00ff', 0.0, 1.0)
    else:
        raise KeyError(name)
    # one-sided, except the banner cloth and the glow (the barrier sheet is seen from both sides)
    m.use_backface_culling = name not in ("ru_banner", "ru_glow")
    _MATS[name] = m
    return m


# ------------------------------------------------------------------ geometry accumulator
# A tower's floors collide up to this far above its foot (m): nobody gets higher, and the collision mesh is a
# fraction of the size. meridian.py raises it where a deck runs beside the towers.
COL_TOP = 16.0
HEAP_COL_RES = .5


class Geo:
    """C: does each face collide? The game does not collide with what it draws (a Nanite mesh's collision is built
    from its simplified fallback: walls that stop nothing, rocks you walk into). collision_of() gives the faces that
    collide as their own mesh, exact, and that is what the level blocks with."""

    def __init__(self, name):
        self.name = name
        self.V, self.F, self.M, self.S, self.C, self.R = [], [], [], [], [], []
        self.UV = {}
        self.col = True                                          # for the faces added from here on: do they collide,
        self.vis = True                                          # are they drawn (False: a coarser stand-in to collide with)

    def add(self, verts, faces, mat, smooth=False, uvs=None):
        o = len(self.V)
        self.V.extend((float(v[0]), float(v[1]), float(v[2])) for v in verts)
        mats = mat if isinstance(mat, (list, tuple)) else None
        for k, f in enumerate(faces):
            if uvs is not None:
                self.UV[len(self.F)] = uvs[k]
            self.F.append([i + o for i in f])
            self.M.append(mats[k] if mats else mat)
            self.S.append(smooth)
            self.C.append(self.col)
            self.R.append(self.vis)

    def __len__(self):
        return len(self.F)


def collision_of(geo):
    """the faces of geo that collide, as a Geo named <name>_solid (same materials: surfaces are told by their names)"""
    c = Geo(geo.name + "_solid")
    remap = {}
    for f, m, k in zip(geo.F, geo.M, geo.C):
        if not k:
            continue
        nf = []
        for i in f:
            if i not in remap:
                remap[i] = len(c.V)
                c.V.append(geo.V[i])
            nf.append(remap[i])
        c.F.append(nf); c.M.append(m); c.S.append(False); c.C.append(True); c.R.append(True)
    return c


def drawn_of(geo):
    """geo without its collision-only faces (the same object when it has none)"""
    if all(geo.R):
        return geo
    d = Geo(geo.name)
    remap = {}
    for fi, (f, m, sm, r) in enumerate(zip(geo.F, geo.M, geo.S, geo.R)):
        if not r:
            continue
        nf = []
        for i in f:
            if i not in remap:
                remap[i] = len(d.V)
                d.V.append(geo.V[i])
            nf.append(remap[i])
        if fi in geo.UV:
            d.UV[len(d.F)] = geo.UV[fi]
        d.F.append(nf); d.M.append(m); d.S.append(sm); d.C.append(True); d.R.append(True)
    return d


def build(geo, collection=None):
    """Geo -> Blender mesh object named geo.name at the origin (plan (E, N, z) -> Blender (N, -E, z))."""
    geo = drawn_of(geo)
    if not geo.F:
        return None
    V = np.asarray(geo.V, np.float64)
    BV = np.stack([V[:, 1], -V[:, 0], V[:, 2]], 1)
    me = bpy.data.meshes.new(geo.name)
    me.from_pydata(BV.tolist(), [], geo.F)
    names = sorted(set(geo.M))
    for n in names:
        me.materials.append(material(n))
    idx = {n: i for i, n in enumerate(names)}
    me.polygons.foreach_set('material_index', [idx[m] for m in geo.M])
    me.polygons.foreach_set('use_smooth', geo.S)
    # world-scale box UVs: each face projected along its dominant axis, one texture tile per TILE metres
    uv = me.uv_layers.new(name='UVMap')
    nl = len(me.loops)
    lv = np.empty(nl, np.int32); me.loops.foreach_get('vertex_index', lv)
    np_ = len(me.polygons)
    ls = np.empty(np_, np.int32); me.polygons.foreach_get('loop_start', ls)
    lt = np.empty(np_, np.int32); me.polygons.foreach_get('loop_total', lt)
    nrm = np.empty(np_ * 3, np.float32); me.polygons.foreach_get('normal', nrm); nrm = nrm.reshape(-1, 3)
    poly_of_loop = np.repeat(np.arange(np_), lt)
    p = BV[lv]
    n = nrm[poly_of_loop]
    ax = np.abs(n).argmax(1)
    tile = np.array([TILE.get(m, 2.0) for m in geo.M], np.float64)[poly_of_loop]
    u = np.where(ax == 2, p[:, 0], np.where(ax == 0, p[:, 1] * np.sign(n[:, 0] + 1e-9), p[:, 0] * -np.sign(n[:, 1] + 1e-9)))
    v = np.where(ax == 2, p[:, 1], p[:, 2])
    UV = np.stack([u / tile, v / tile], 1)
    for fi, fuv in geo.UV.items():
        s = ls[fi]
        UV[s:s + len(fuv)] = fuv
    uv.data.foreach_set('uv', UV.astype(np.float32).ravel())
    me.validate(clean_customdata=False)
    me.update()
    o = bpy.data.objects.new(geo.name, me)
    (collection or bpy.context.scene.collection).objects.link(o)
    return o


# ------------------------------------------------------------------ primitives (plan coordinates)
def _rz(yaw):
    c, s = math.cos(yaw), math.sin(yaw)
    return lambda x, y: (c * x - s * y, s * x + c * y)


def box(g, mat, c, h, yaw=0.0, R=None, top_mat=None, offsets=None, smooth=False):
    """A box centred at c with half sizes h, turned yaw about up (or by the 3x3 R). offsets: per-corner extra offsets
    (8 vectors, local) for broken / sheared shapes. top_mat: a different material on the top face."""
    pts = [(-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1), (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)]
    R = R or Matrix.Rotation(yaw, 3, 'Z')
    cv = Vector(c)
    vs = []
    for i, (sx, sy, sz) in enumerate(pts):
        p = Vector((sx * h[0], sy * h[1], sz * h[2]))
        if offsets:
            p += Vector(offsets[i])
        vs.append(R @ p + cv)
    faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    mats = [mat, top_mat or mat, mat, mat, mat, mat]
    g.add(vs, faces, mats, smooth)


def prism(g, mat, poly, z0, z1, side=None, top=True, bottom=True, smooth=False):
    """Extrudes a CCW polygon [(x, y)] from z0 to z1 (top: n-gon)."""
    n = len(poly)
    vs = [(x, y, z0) for x, y in poly] + [(x, y, z1) for x, y in poly]
    faces, mats = [], []
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, n + j, n + i)); mats.append(side or mat)
    if top:
        faces.append(tuple(range(n, 2 * n))); mats.append(mat)
    if bottom:
        faces.append(tuple(range(n))[::-1]); mats.append(mat)
    g.add(vs, faces, mats, smooth)


def circle(c, r, n, a0=0.0, a1=TAU):
    full = abs(a1 - a0 - TAU) < 1e-6
    m = n if full else n + 1
    return [(c[0] + r * math.cos(a0 + (a1 - a0) * i / n), c[1] + r * math.sin(a0 + (a1 - a0) * i / n)) for i in range(m)]


def cyl(g, mat, c, r, z0, z1, n=24, r1=None, cap_mat=None, smooth=True):
    """Upright cylinder (or cone with r1 at the top), smooth sides, flat caps."""
    r1 = r if r1 is None else r1
    b = circle(c, r, n); t = circle(c, r1, n)
    vs = [(x, y, z0) for x, y in b] + [(x, y, z1) for x, y in t]
    side = [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    g.add(vs, side, mat, smooth)
    g.add([(x, y, z1) for x, y in t], [tuple(range(n))], cap_mat or mat)
    g.add([(x, y, z0) for x, y in b], [tuple(range(n))[::-1]], cap_mat or mat)


def annulus(g, mat, c, r0, r1, z0, z1, n=64, a0=0.0, a1=TAU, side_mat=None, inner=True, outer=True):
    """A ring slab (or an arc of one) between radii r0 < r1, from z0 to z1."""
    full = abs(a1 - a0 - TAU) < 1e-6
    m = n if full else n + 1
    ring = lambda r, z: [(c[0] + r * math.cos(a0 + (a1 - a0) * i / n), c[1] + r * math.sin(a0 + (a1 - a0) * i / n), z) for i in range(m)]
    I0, I1, O0, O1 = ring(r0, z0), ring(r0, z1), ring(r1, z0), ring(r1, z1)
    vs = I0 + I1 + O0 + O1
    a, b, cc, d = 0, m, 2 * m, 3 * m
    faces, mats = [], []
    steps = n if full else n
    for i in range(steps):
        j = (i + 1) % m
        faces.append((b + i, d + i, d + j, b + j)); mats.append(mat)                # top
        faces.append((a + i, a + j, cc + j, cc + i)); mats.append(mat)              # bottom
        if outer:
            faces.append((cc + i, cc + j, d + j, d + i)); mats.append(side_mat or mat)
        if inner:
            faces.append((a + j, a + i, b + i, b + j)); mats.append(side_mat or mat)
    if not full:
        faces.append((a, cc, d, b)); mats.append(side_mat or mat)
        faces.append((a + m - 1, b + m - 1, d + m - 1, cc + m - 1)); mats.append(side_mat or mat)
    g.add(vs, faces, mats)


def tube(g, mat, pts, r, sides=6, cap=True, smooth=True, r_end=None):
    """A round section swept along points (rebar, rails, cables)."""
    pts = [Vector(p) for p in pts]
    rings = []
    r_end = r if r_end is None else r_end
    for i, p in enumerate(pts):
        t = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        a = t.cross(Vector((0, 0, 1)) if abs(t.z) < .9 else Vector((1, 0, 0))).normalized()
        b = t.cross(a).normalized()
        rr = r + (r_end - r) * i / max(len(pts) - 1, 1)
        rings.append([p + (a * math.cos(TAU * k / sides) + b * math.sin(TAU * k / sides)) * rr for k in range(sides)])
    vs = [v for ring in rings for v in ring]
    faces = []
    for i in range(len(rings) - 1):
        for k in range(sides):
            k1 = (k + 1) % sides
            faces.append((i * sides + k, i * sides + k1, (i + 1) * sides + k1, (i + 1) * sides + k))
    g.add(vs, faces, mat, smooth)
    if cap:
        last = (len(rings) - 1) * sides
        g.add(vs[:sides], [tuple(range(sides))[::-1]], mat)
        g.add(vs[last:], [tuple(range(sides))], mat)


def offset_path(pts, d):
    """offsets a 2D polyline sideways by d (left positive) with mitred corners"""
    out = []
    for i, p in enumerate(pts):
        prev = pts[i - 1] if i > 0 else None
        nxt = pts[i + 1] if i < len(pts) - 1 else None
        ns = []
        for a, b in ((prev, p), (p, nxt)):
            if a is None or b is None:
                continue
            dx, dy = b[0] - a[0], b[1] - a[1]
            L = math.hypot(dx, dy) or 1.0
            ns.append((-dy / L, dx / L))
        nx = sum(n[0] for n in ns); ny = sum(n[1] for n in ns)
        L = math.hypot(nx, ny) or 1.0
        nx, ny = nx / L, ny / L
        cosh = ns[0][0] * nx + ns[0][1] * ny
        k = d / max(cosh, .3)
        out.append((p[0] + nx * k, p[1] + ny * k) + tuple(p[2:]))
    return out


def path_deck(g, mat, side_mat, pts, width, thick, end_mat=None):
    """A deck (road slab) along a 3D centre line [(x, y, z)] with mitred corners; top at z."""
    L = offset_path(pts, width / 2); Rr = offset_path(pts, -width / 2)
    n = len(pts)
    vs = [(p[0], p[1], p[2]) for p in L] + [(p[0], p[1], p[2]) for p in Rr] + \
         [(p[0], p[1], p[2] - thick) for p in L] + [(p[0], p[1], p[2] - thick) for p in Rr]
    lt, rt, lb, rb = 0, n, 2 * n, 3 * n
    faces, mats = [], []
    for i in range(n - 1):
        faces.append((rt + i, rt + i + 1, lt + i + 1, lt + i)); mats.append(mat)          # top
        faces.append((rb + i, lb + i, lb + i + 1, rb + i + 1)); mats.append(side_mat)     # bottom
        faces.append((lt + i, lt + i + 1, lb + i + 1, lb + i)); mats.append(side_mat)     # left side
        faces.append((rt + i + 1, rt + i, rb + i, rb + i + 1)); mats.append(side_mat)     # right side
    faces.append((lt, lb, rb, rt)); mats.append(end_mat or side_mat)
    faces.append((lt + n - 1, rt + n - 1, rb + n - 1, lb + n - 1)); mats.append(end_mat or side_mat)
    g.add(vs, faces, mats)


def wall_path(g, mat, pts, thick, height, top_mat=None, skip=None, rnd=None, broken=0.0):
    """A wall along a polyline [(x, y, z)] (z = its foot), split into ~2 m segments; skip(i, t) drops segments,
    `broken` (0..1) knocks bites out of its top."""
    rnd = rnd or random.Random(1)
    for i in range(len(pts) - 1):
        a, b = Vector(pts[i]), Vector(pts[i + 1])
        d = b - a
        L = d.xy.length
        n = max(1, int(L / 2.0))
        yaw = math.atan2(d.y, d.x)
        for k in range(n):
            t0, t1 = k / n, (k + 1) / n
            if skip and skip(i, (t0 + t1) / 2):
                continue
            p = a + d * ((t0 + t1) / 2)
            hh = height * (1.0 - broken * rnd.random() * (rnd.random() < .35))
            box(g, mat, (p.x, p.y, p.z + hh / 2), (L / n / 2 + .01, thick / 2, hh / 2), yaw, top_mat=top_mat)


# ------------------------------------------------------------------ rubble
def heap(g, c, r, h, seed, chunks=14, res=.22, ry=None):
    """A rubble mound at c (x, y, z foot), radius r (ry: the other radius), height h, with concrete chunks."""
    rnd = random.Random(seed)
    ry = ry or r
    cx, cy, cz = c
    ch = []
    for _ in range(chunks):
        a = rnd.random() * TAU; d = rnd.random() ** .7 * .75
        px, py = cx + math.cos(a) * r * d, cy + math.sin(a) * ry * d
        rise = h * (1 - d * d) * rnd.uniform(.6, 1.05)
        half = np.array([rnd.uniform(.4, 1.5), rnd.uniform(.3, 1.0), rnd.uniform(.12, .4)]) * min(1.0, h / 1.5 + .3)
        R = sdf.rot((rnd.random(), rnd.random(), rnd.random()), rnd.uniform(0, math.pi))
        ch.append(((px, py, cz + rise), half, R))
    ph = rnd.random() * 100

    def fn(Pt):
        q = (Pt - np.array([cx, cy, cz], np.float32)) / np.array([r, ry, h], np.float32)
        d = (np.sqrt(q[:, 0] ** 2 + q[:, 1] ** 2 + (q[:, 2]) ** 2) - 1.0) * min(r, ry, h * 1.5)
        d += .26 * np.sin(Pt[:, 0] * 1.3 + ph) * np.sin(Pt[:, 1] * 1.7 - ph) + .07 * np.sin(Pt[:, 0] * 3.7 + Pt[:, 1] * 2.9 + ph * 2)             + .025 * np.sin(Pt[:, 0] * 9.1 - Pt[:, 2] * 7.3 + ph) * np.sin(Pt[:, 1] * 8.7 + ph * 3)
        for cc, half, R in ch:
            d = sdf.smin(d, sdf.round_box(Pt, cc, half, .04, R), .06)
        return np.maximum(d, -(Pt[:, 2] - cz + .25))
    lo = (cx - r - 2, cy - ry - 2, cz - .4)
    hi = (cx + r + 2, cy + ry + 2, cz + h + 2)
    V, Q = sdf.mesh(fn, lo, hi, res, project_iters=1)
    if len(Q) == 0:
        return
    def top(X, Y, fn=fn, z0=cz - .2, z1=cz + h + 1.6):
        """the mound's surface under each point (x, y): the highest place the field is solid"""
        X = np.asarray(X, np.float32); Y = np.asarray(Y, np.float32)
        Z = np.full(len(X), z0, np.float32)
        found = np.zeros(len(X), bool)
        n = 28
        for k in range(n):                                           # down from above in steps, then halved
            z = z1 - (z1 - z0) * k / (n - 1)
            d = fn(np.stack([X, Y, np.full(len(X), z, np.float32)], 1))
            hit = (d < 0) & ~found
            Z[hit] = z
            found |= hit
        lo, hi = Z.copy(), Z + (z1 - z0) / (n - 1)
        for _ in range(7):
            mid = (lo + hi) * .5
            inside = fn(np.stack([X, Y, mid], 1)) < 0
            lo = np.where(inside, mid, lo); hi = np.where(inside, hi, mid)
        return np.where(found, (lo + hi) * .5, cz).tolist()
    if g.col and ZONE:
        HEAPS.append((ZONE, (cx, cy, cz), max(r, ry), top))
    # drawn fine, collided with coarse: a mound's collision at the drawn resolution is most of a zone's collision mesh
    # for a few centimetres nobody feels on rubble
    was = g.col
    coarse = was and HEAP_COL_RES > res * 1.2
    g.col = was and not coarse
    # one material over the whole mound (two, split face by face on the slope, drew a sawtooth across it)
    g.add(V.tolist(), Q.tolist(), "ru_rubble", smooth=True)
    if coarse:
        V2, Q2 = sdf.mesh(fn, lo, hi, HEAP_COL_RES, project_iters=1)
        if len(Q2):
            g.col, g.vis = True, False
            g.add(V2.tolist(), Q2.tolist(), "ru_rubble")
    # What a mound is made of: the broken pieces lying in and on it (drawn only: none stands a hand above the fill).
    # Small lumps everywhere, blocks, and a few floor slabs lying on the slope with the fall of it.
    g.col, g.vis = False, True
    pieces = []
    for _ in range(min(300, int(14 + 5.0 * r * ry))):
        a = rnd.random() * TAU; d = math.sqrt(rnd.random()) * .97
        kind = rnd.random()
        if kind < .1:
            hx, hy, hz = rnd.uniform(.7, 1.5), rnd.uniform(.5, 1.0), rnd.uniform(.07, .12)          # a slab
        elif kind < .45:
            sz = rnd.uniform(.25, .55)
            hx, hy, hz = sz, sz * rnd.uniform(.5, .9), sz * rnd.uniform(.3, .6)                   # a block
        else:
            sz = rnd.uniform(.08, .22)
            hx, hy, hz = sz, sz * rnd.uniform(.6, 1.0), sz * rnd.uniform(.4, .8)                  # a lump
        pieces.append((cx + math.cos(a) * r * d, cy + math.sin(a) * ry * d, hx, hy, hz, a, kind))
    Zs = top([p[0] for p in pieces], [p[1] for p in pieces])
    e = .35
    Zx = top([p[0] + e for p in pieces], [p[1] for p in pieces])
    Zy = top([p[0] for p in pieces], [p[1] + e for p in pieces])
    for (x, y, hx, hy, hz, a, kind), z, zx, zy in zip(pieces, Zs, Zx, Zy):
        sx, sy = max(-1.0, min(1.0, (zx - z) / e)), max(-1.0, min(1.0, (zy - z) / e))          # the slope it lies on
        Rm = (Matrix.Rotation(math.atan(sy) + rnd.uniform(-.25, .25), 3, 'X') @ Matrix.Rotation(-math.atan(sx) + rnd.uniform(-.25, .25), 3, 'Y')
              @ Matrix.Rotation(rnd.uniform(0, TAU), 3, 'Z'))
        off = [(rnd.uniform(-.28, .28) * hx, rnd.uniform(-.28, .28) * hy, rnd.uniform(-.3, .3) * hz) for _ in range(8)]
        box(g, "ru_fracture" if kind > .1 and rnd.random() < .7 else "ru_concrete", (x, y, z + hz * rnd.uniform(-.1, .35)), (hx, hy, hz), R=Rm, offsets=off)
    g.col, g.vis = was, True


def chunks(g, c, r, count, seed, size=(.18, .7), z=0.0):
    """loose concrete chunks scattered round c"""
    rnd = random.Random(seed)
    for _ in range(count):
        a = rnd.random() * TAU; d = r * math.sqrt(rnd.random())
        s = rnd.uniform(*size)
        hx, hy, hz = s * rnd.uniform(.6, 1.0), s * rnd.uniform(.4, .8), s * rnd.uniform(.2, .45)
        R = Matrix.Rotation(rnd.uniform(0, TAU), 3, 'Z') @ Matrix.Rotation(rnd.uniform(-.4, .4), 3, 'X')
        off = [(rnd.uniform(-.25, .25) * hx, rnd.uniform(-.25, .25) * hy, rnd.uniform(-.3, .3) * hz) for _ in range(8)]
        box(g, "ru_fracture", (c[0] + math.cos(a) * d, c[1] + math.sin(a) * d, z + hz * .55), (hx, hy, hz), R=R, offsets=off)


# ------------------------------------------------------------------ void crystals
def crystal_cluster(g, c, size, seed, up=(0, 0, 1)):
    """a cluster of faceted shards growing from c (the Altered's void growth)"""
    rnd = random.Random(seed)
    upv = Vector(up).normalized()
    for k in range(rnd.randint(4, 7)):
        L = size * rnd.uniform(.5, 1.0) * (1.3 if k == 0 else 1.0)
        r = L * rnd.uniform(.10, .16)
        axis = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), 0))
        axis = axis.normalized() if axis.length > 1e-3 else Vector((1, 0, 0))
        tilt = Matrix.Rotation(rnd.uniform(.0, .6) if k else .08, 3, axis)
        d = (tilt @ upv).normalized()
        a = d.cross(Vector((1, 0, 0)) if abs(d.x) < .9 else Vector((0, 1, 0))).normalized(); b = d.cross(a)
        base = Vector(c) + a * rnd.uniform(-.3, .3) * size * .4 + b * rnd.uniform(-.3, .3) * size * .4 - d * .1
        n = 6
        ring0 = [base + (a * math.cos(TAU * i / n) + b * math.sin(TAU * i / n)) * r for i in range(n)]
        ring1 = [base + d * L * .72 + (a * math.cos(TAU * i / n + .3) + b * math.sin(TAU * i / n + .3)) * r * .82 for i in range(n)]
        tip = base + d * L
        vs = ring0 + ring1 + [tip]
        faces = [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)] + [(n + i, n + (i + 1) % n, 2 * n) for i in range(n)]
        faces.append(tuple(range(n))[::-1])
        g.add(vs, faces, "ru_glow")


# ------------------------------------------------------------------ banners
def banner(g, top_c, width, length, yaw, seed, sway=.25):
    """a tattered cloth banner hanging from top_c (x, y, z), facing along yaw + 90 deg; UVs 0..1 across, 0..1 down"""
    rnd = random.Random(seed)
    nx, ny = 6, 14
    T = _rz(yaw)
    vs, uvs_v = [], []
    cut = [length * (1 - .18 * (.5 + .5 * math.sin(i * 2.1 + seed)) * rnd.random()) for i in range(nx + 1)]
    for j in range(ny + 1):
        for i in range(nx + 1):
            u = i / nx; v = j / ny
            x = (u - .5) * width
            z = -v * cut[i]
            bulge = sway * math.sin(v * math.pi * .9) * (.6 + .4 * math.sin(u * 3.0 + seed)) + .05 * math.sin(u * 9 + v * 5)
            dx, dy = T(x, bulge)
            vs.append((top_c[0] + dx, top_c[1] + dy, top_c[2] + z))
            uvs_v.append((u, 1 - v * cut[i] / length))
    faces, uvs = [], []
    for j in range(ny):
        for i in range(nx):
            if j > ny * .55 and rnd.random() < .08 * (j / ny):
                continue                                         # holes torn in the lower cloth
            a = j * (nx + 1) + i
            f = (a, a + 1, a + 1 + nx + 1, a + nx + 1)
            faces.append(f); uvs.append([uvs_v[q] for q in f])
    g.add(vs, faces, "ru_banner", True, uvs)
    # the pole it hangs from
    p0 = T(-width / 2 - .3, 0); p1 = T(width / 2 + .3, 0)
    tube(g, "ru_metal", [(top_c[0] + p0[0], top_c[1] + p0[1], top_c[2] + .05), (top_c[0] + p1[0], top_c[1] + p1[1], top_c[2] + .05)], .06, 8)


# ------------------------------------------------------------------ the Altered's base: growth, pods, spires, barricades, cables
def hive_growth(g, gd, c, r, seed, wall=None, res=.13):
    """a growth spreading over the ground from c (x, y, z): thick roots branching out, swollen nodes, a skin of membrane
    near the middle, glowing veins along the roots, egg pods. wall: (nx, ny) the outward normal of a wall behind it the
    roots climb. The mass and pods are solid (g); the veins are detail (gd)."""
    rnd = random.Random(seed)
    cx, cy, cz = c
    caps = []
    for b in range(rnd.randint(6, 9)):
        a = rnd.uniform(0, TAU)
        L = r * rnd.uniform(.55, 1.0)
        pts = [Vector((cx, cy, cz))]
        for k in range(1, 6):
            a += rnd.uniform(-.35, .35)
            pts.append(pts[-1] + Vector((math.cos(a), math.sin(a), 0)) * L / 5)
        rad = [.5 * (1 - k / 6) ** .8 + .08 for k in range(6)]
        caps.append((pts, rad))
        if rnd.random() < .5:                                     # a side branch
            j = rnd.randint(1, 3)
            a2 = a + rnd.choice((-1, 1)) * rnd.uniform(.6, 1.2)
            q = [pts[j]] + [pts[j] + Vector((math.cos(a2), math.sin(a2), 0)) * L * .12 * k for k in range(1, 4)]
            caps.append((q, [rad[j] * .8 * (1 - k / 4) + .04 for k in range(4)]))
    if wall:                                                     # roots climbing the wall behind
        wn = Vector((wall[0], wall[1], 0)).normalized()
        side = Vector((-wn.y, wn.x, 0))
        for k in range(rnd.randint(3, 5)):
            base = Vector((cx, cy, cz)) - wn * r * .35 + side * rnd.uniform(-r * .5, r * .5)
            h = rnd.uniform(2.5, 6.0)
            pts = [base + side * math.sin(t * 2 + k) * .4 + Vector((0, 0, h * t)) - wn * .1 for t in (0, .2, .4, .6, .8, 1.0)]
            caps.append((pts, [.42, .36, .3, .22, .14, .06]))
    nodes = [(Vector((cx, cy, cz)) + Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), 0)) * r * .4, rnd.uniform(.6, 1.15)) for _ in range(5)]
    P = [(np.array([tuple(p) for p in pts], np.float32), np.array(rad, np.float32)) for pts, rad in caps]
    ph = rnd.random() * 10

    def fn(X):
        d = np.full(len(X), 1e9, np.float32)
        for pts, rad in P:
            for i in range(len(pts) - 1):
                d = sdf.smin(d, sdf.round_cone(X, pts[i], pts[i + 1], rad[i], rad[i + 1]), .12)
        for nc, nr in nodes:
            d = sdf.smin(d, sdf.ellipsoid(X, tuple(nc), (nr, nr, nr * .8)), .25)
        # a membrane skin round the heart, sagging between the roots
        skin = sdf.ellipsoid(X, (cx, cy, cz), (r * .5, r * .5, .5))
        d = sdf.smin(d, skin, .25)
        d += .05 * np.sin(X[:, 0] * 5 + ph) * np.sin(X[:, 1] * 4.3 - ph) + .02 * np.sin(X[:, 2] * 11 + X[:, 0] * 3)
        return np.maximum(d, -(X[:, 2] - cz + .08))
    lo = (cx - r - 1.5, cy - r - 1.5, cz - .2)
    hi = (cx + r + 1.5, cy + r + 1.5, cz + (7.0 if wall else 2.2))
    V, Q = sdf.mesh(fn, lo, hi, res, project_iters=1)
    if len(Q):
        g.add(V.tolist(), Q.tolist(), "ru_hive", smooth=True)
    # veins of light along the roots, pods
    for pts, rad in caps[:6]:
        tube(gd, "ru_glow", [tuple(Vector(tuple(p)) + Vector((0, 0, float(rr) * .92))) for p, rr in zip(pts, rad)][:4], .045, 5)
    for k in range(rnd.randint(3, 6)):
        a = rnd.uniform(0, TAU); dd = r * rnd.uniform(.25, .7)
        pc = (cx + math.cos(a) * dd, cy + math.sin(a) * dd, cz)
        pod(g, gd, pc, rnd.uniform(.55, .95), seed * 31 + k)


def pod(g, gd, c, s, seed):
    """an egg pod: a ribbed leathery sac with a light inside, on a stalk"""
    rnd = random.Random(seed)
    n, m = 14, 10
    tilt = Matrix.Rotation(rnd.uniform(-.25, .25), 3, 'X') @ Matrix.Rotation(rnd.uniform(-.25, .25), 3, 'Y')
    base = Vector(c)
    vs = []
    for j in range(m + 1):
        v = j / m
        z = s * 1.5 * v
        rad = s * .55 * math.sin(math.pi * min(1.0, v * 1.08)) ** .8 + .02
        for i in range(n):
            a = TAU * i / n
            rib = 1 + .07 * math.cos(a * 7)
            vs.append(tuple(base + tilt @ Vector((math.cos(a) * rad * rib, math.sin(a) * rad * rib, z))))
    faces = [(j * n + i, j * n + (i + 1) % n, (j + 1) * n + (i + 1) % n, (j + 1) * n + i) for j in range(m) for i in range(n)]
    g.add(vs, faces, "ru_hive", smooth=True)
    g.add([vs[m * n + i] for i in range(n)], [tuple(range(n))], "ru_hive")
    crystal_cluster(gd, tuple(base + tilt @ Vector((0, 0, s * .5))), s * .7, seed + 1)


def alien_spire(g, gd, c, h, seed):
    """a spire of the Choir: a twisted spiked obelisk of dark plate on a hive foot, a crown of shards, two broken rings
    of light hanging round it, shards floating"""
    rnd = random.Random(seed)
    cx, cy, cz = c
    n = 6
    rings = []
    for k in range(13):
        t = k / 12
        rad = (1.4 * (1 - t) ** 1.3 + .12) * (1 + .15 * math.sin(t * 9 + seed))
        tw = t * 1.6 + seed
        rings.append([(cx + math.cos(TAU * i / n + tw) * rad, cy + math.sin(TAU * i / n + tw) * rad, cz + h * t) for i in range(n)])
    vs = [p for ring in rings for p in ring]
    faces = [(k * n + i, k * n + (i + 1) % n, (k + 1) * n + (i + 1) % n, (k + 1) * n + i) for k in range(len(rings) - 1) for i in range(n)]
    g.add(vs, faces, "ru_metal")
    g.add(rings[-1], [tuple(range(n))], "ru_metal")
    for k in range(1, 12, 2):                                    # glowing seams up the spire
        ring = rings[k]
        tube(gd, "ru_glow", [(p[0] + (p[0] - cx) * .04, p[1] + (p[1] - cy) * .04, p[2]) for p in ring + ring[:1]], .03, 4)
    for k in range(5):                                           # spikes down the flanks
        t = rnd.uniform(.15, .7)
        a = rnd.uniform(0, TAU)
        rad = 1.4 * (1 - t) ** 1.3 + .12
        b = Vector((cx + math.cos(a) * rad * .9, cy + math.sin(a) * rad * .9, cz + h * t))
        tube(g, "ru_metal", [tuple(b), tuple(b + Vector((math.cos(a), math.sin(a), .5)) * h * .12)], .16, 5, r_end=.01)
    crystal_cluster(gd, (cx, cy, cz + h * .97), h * .18, seed + 5)
    for k, (z, R) in enumerate(((.55, 2.6), (.78, 1.9))):        # hanging rings of light, broken
        a0 = rnd.uniform(0, TAU)
        arc = [(cx + math.cos(a0 + a) * R, cy + math.sin(a0 + a) * R, cz + h * z + .3 * math.sin(a * 2)) for a in [i * TAU * .8 / 30 for i in range(31)]]
        tube(gd, "ru_metal", arc, .09, 6)
        tube(gd, "ru_glow", [(p[0], p[1], p[2] + .1) for p in arc], .035, 4)
    for k in range(6):                                           # shards drifting round it
        a = rnd.uniform(0, TAU); R = rnd.uniform(2.2, 3.4)
        crystal_cluster(gd, (cx + math.cos(a) * R, cy + math.sin(a) * R, cz + h * rnd.uniform(.3, .8)), rnd.uniform(.4, .8), seed * 7 + k)
    hive_growth(g, gd, (cx, cy, cz), 2.6, seed + 9, res=.15)


def alien_barricade(g, c, yaw, seed, w=3.4, h=1.35):
    """a curved barricade of grown chitin: a crescent wall (cover at chest height, bowed toward the enemy), ribbed,
    spiked along its top"""
    rnd = random.Random(seed)
    T = _rz(yaw)
    cx, cy, cz = c
    n, m = 14, 6
    R = w * .9                                                   # bowed: the middle stands proud
    vs = []
    for j in range(m + 1):
        v = j / m
        for side in (0, 1):
            for i in range(n + 1):
                u = i / n - .5
                bow = (1 - (u * 2) ** 2) * .35
                thick = .28 * (1 - .45 * v) * (1 - .3 * abs(u * 2))
                y = bow + (thick if side else -thick) + .05 * math.sin(v * 7 + i)
                z = h * v * (1 - .25 * (u * 2) ** 2) + (.08 * math.sin(i * 1.7 + seed) if j == m else 0)
                dx, dy = T(u * w, y)
                vs.append((cx + dx, cy + dy, cz + z))
    row = n + 1
    lay = lambda j, s, i: (j * 2 + s) * row + i
    faces = []
    for j in range(m):
        for i in range(n):
            faces.append((lay(j, 0, i), lay(j, 0, i + 1), lay(j + 1, 0, i + 1), lay(j + 1, 0, i)))      # front
            faces.append((lay(j, 1, i + 1), lay(j, 1, i), lay(j + 1, 1, i), lay(j + 1, 1, i + 1)))      # back
    for i in range(n):
        faces.append((lay(m, 0, i), lay(m, 0, i + 1), lay(m, 1, i + 1), lay(m, 1, i)))                  # top
    for j in range(m):
        faces.append((lay(j, 1, 0), lay(j, 0, 0), lay(j + 1, 0, 0), lay(j + 1, 1, 0)))                  # ends
        faces.append((lay(j, 0, n), lay(j, 1, n), lay(j + 1, 1, n), lay(j + 1, 0, n)))
    g.add(vs, faces, "ru_hive", smooth=True)
    for i in range(1, n, 2):                                     # spikes along the top
        p = Vector(vs[lay(m, 0, i)]) * .5 + Vector(vs[lay(m, 1, i)]) * .5
        tube(g, "ru_hive", [tuple(p - Vector((0, 0, .1))), tuple(p + Vector((0, 0, rnd.uniform(.25, .5))))], .07, 5, r_end=.005)


def cable(gd, a, b, sag, seed=0):
    """a cable slung between two points, a line of light along it"""
    a, b = Vector(a), Vector(b)
    pts = [a.lerp(b, t) - Vector((0, 0, sag * 4 * t * (1 - t))) for t in [i / 24 for i in range(25)]]
    tube(gd, "ru_metal", [tuple(p) for p in pts], .07, 6)
    tube(gd, "ru_glow", [tuple(p + Vector((0, 0, -.06))) for p in pts[2:-2]], .025, 4)


# ------------------------------------------------------------------ the ruined tower
def tower(g, gd, c, w, d, floors, yaw=0.0, seed=0, style="panel", top=(.45, 1.0), holes=2, rebar=True,
          base_z=0.0, heaps=True, detail=True, cell_target=3.0, intact_below=0, col_top=None, heap_res=.4):
    """A ruined tower centred at c (x, y), width w along its local x, depth d along local y, turned by yaw (radians).
    g gets the structure (collides), gd the fine detail (rebar, glass, mullions). col_top: how far above its foot it
    collides (None = COL_TOP; 0 = not at all: a ruin behind the route's invisible walls)."""
    if CITY:
        import citykit
        if CITY.get("far"):
            H = sum(4.5 if k == 0 else 3.6 for k in range(floors))
            citykit.far_building(g, c, w, d, H, yaw, seed)
            return H
        r0 = random.Random(seed * 101 + 7)
        style = CITY["styles"][seed % len(CITY["styles"])]
        # some stand almost whole, others are half gone: the district's damage, spread
        dmg = min(.92, max(.06, (1.0 - top[0]) * r0.uniform(.25, 1.25)))
        lod = 1 if (not detail or col_top == 0) else 0
        return citykit.building(g, gd, c, w, d, floors, yaw, seed, style, dmg, base_z, heaps, lod, col_top, intact_below)
    rnd = random.Random(seed)
    T = _rz(yaw)
    first_face = len(g.F)

    def W(x, y, z):
        dx, dy = T(x, y)
        return (c[0] + dx, c[1] + dy, base_z + z)
    levels = [0.0]
    for k in range(floors):
        levels.append(levels[-1] + (4.5 if k == 0 else 3.6))
    H = levels[-1]
    nbx, nby = max(1, round(w / 6.0)), max(1, round(d / 6.0))
    sub_x = max(1, round(w / nbx / cell_target)); sub_y = max(1, round(d / nby / cell_target))
    ncx, ncy = nbx * sub_x, nby * sub_y
    xs = [-w / 2 + w * i / ncx for i in range(ncx + 1)]
    ys = [-d / 2 + d * j / ncy for j in range(ncy + 1)]
    lo, hi = top
    sx, sy = rnd.uniform(-1, 1), rnd.uniform(-1, 1)
    ph = Vector((rnd.uniform(0, 50), rnd.uniform(0, 50), 0))

    wedge = (rnd.choice((-1, 1)) * w / 2, rnd.choice((-1, 1)) * d / 2, rnd.uniform(.25, .6))

    def top_h(x, y):
        nv = noise.noise(Vector((x * .06, y * .06, 0)) + ph) * .7 + noise.noise(Vector((x * .19, y * .19, 3)) + ph) * .3
        t = lo + (hi - lo) * (.5 + .5 * nv)
        h = H * t + (sx * x / max(w, 1) + sy * y / max(d, 1)) * H * .35 * (hi - lo)
        dw = math.hypot((x - wedge[0]) / max(w, 1), (y - wedge[1]) / max(d, 1))     # a corner fell away
        return min(h, H * (wedge[2] + dw * 1.4))
    blasts = []
    for _ in range(holes):
        side = rnd.randrange(4)
        u = rnd.uniform(-.4, .4)
        hx, hy = [(u * w, -d / 2), (w / 2, u * d), (u * w, d / 2), (-w / 2, u * d)][side]
        blasts.append((Vector((hx, hy, rnd.uniform(.2, .75) * H * hi)), rnd.uniform(4.0, 8.5)))

    def gone(x, y, z):
        if z <= levels[intact_below] + .01:
            return False
        if z > top_h(x, y):
            return True
        p = Vector((x, y, z))
        for bc, br in blasts:
            if (p - bc).length < br * (.8 + .35 * noise.noise(p * .35 + ph)):
                return True
        return False

    def jit(i, j, k, s=1.0):
        h = (i * 73856093 ^ j * 19349663 ^ k * 83492791 ^ seed * 2654435761) & 0xffffffff
        a = (h & 0xffff) / 65535.0; b = ((h >> 16) & 0xffff) / 65535.0
        return ((a - .5) * .9 * s, (b - .5) * .9 * s, ((a + b) % 1 - .5) * .14 * s)

    # cells per level (1..floors): does the slab exist?
    exists = {}
    for k in range(1, floors + 1):
        for i in range(ncx):
            for j in range(ncy):
                cxm, cym = (xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2
                exists[(k, i, j)] = not gone(cxm, cym, levels[k] - .2)
    # a slab cell with nothing under it for two floors falls (no floating floors)
    for k in range(2, floors + 1):
        for i in range(ncx):
            for j in range(ncy):
                if exists[(k, i, j)] and not exists.get((k - 1, i, j), True) and not exists.get((k - 2, i, j), True):
                    neighbours = sum(exists.get((k, i + a, j + b), False) for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1)))
                    if neighbours < 2:
                        exists[(k, i, j)] = False

    thick = .34
    rebars = 0
    for k in range(1, floors + 1):
        z = levels[k]
        verts = {}

        def vid(i, j, layer, k=k, z=z):
            key = (i, j, layer)
            if key not in verts:
                adj = [exists.get((k, i + a, j + b)) for a, b in ((0, 0), (-1, 0), (0, -1), (-1, -1))]
                adj = [e for e in adj if e is not None]
                broken = any(not e for e in adj)
                jx, jy, jz = jit(i, j, k) if broken else (0, 0, 0)
                if broken and (i in (0, ncx) or j in (0, ncy)):
                    jx, jy = (0 if i in (0, ncx) else jx), (0 if j in (0, ncy) else jy)
                zz = z + jz if layer == 0 else z - thick + jz * .5
                f = 1.0 if layer == 0 else .85
                verts[key] = W(xs[i] + jx * f, ys[j] + jy * f, zz)
            return verts[key]
        vs, faces, mats = [], [], []

        def face(keys, mat):
            o = len(vs)
            for kk in keys:
                vs.append(vid(*kk))
            faces.append(tuple(range(o, o + len(keys)))); mats.append(mat)
        for i in range(ncx):
            for j in range(ncy):
                if not exists[(k, i, j)]:
                    continue
                face([(i, j, 0), (i + 1, j, 0), (i + 1, j + 1, 0), (i, j + 1, 0)], "ru_concrete")
                face([(i, j, 1), (i, j + 1, 1), (i + 1, j + 1, 1), (i + 1, j, 1)], "ru_concrete")
                # edges: (neighbour offset, the edge's two grid corners in CCW order seen from outside)
                for (a, b), e0, e1 in (((0, -1), (i, j), (i + 1, j)), ((1, 0), (i + 1, j), (i + 1, j + 1)),
                                       ((0, 1), (i + 1, j + 1), (i, j + 1)), ((-1, 0), (i, j + 1), (i, j))):
                    nb = exists.get((k, i + a, j + b))
                    if nb:
                        continue
                    perimeter = nb is None
                    face([(e0[0], e0[1], 1), (e1[0], e1[1], 1), (e1[0], e1[1], 0), (e0[0], e0[1], 0)],
                         "ru_concrete" if perimeter else "ru_fracture")
                    if not perimeter and rebar and detail and rebars < 260 and rnd.random() < .55:
                        p0, p1 = Vector(vid(e0[0], e0[1], 0)), Vector(vid(e1[0], e1[1], 0))
                        out = Vector(W(*((xs[i] + xs[i + 1]) / 2 + a, (ys[j] + ys[j + 1]) / 2 + b, 0))) - Vector(W((xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2, 0))
                        out.z = 0; out.normalize()
                        for _ in range(rnd.randint(1, 3)):
                            t = rnd.uniform(.1, .9)
                            s = p0.lerp(p1, t) + Vector((0, 0, -thick * rnd.uniform(.25, .7)))
                            L = rnd.uniform(.35, 1.5)
                            droop = rnd.uniform(.05, .6) * L
                            side = (p1 - p0).normalized() * rnd.uniform(-.15, .15)
                            tube(gd, "ru_metal", [s - out * .1, s + out * L * .5 + side * .5 - Vector((0, 0, droop * .3)),
                                                  s + out * L + side - Vector((0, 0, droop))], .014, 5, cap=False)
                            rebars += 1
        g.add(vs, faces, mats)
        if detail:
            for i in range(ncx):
                for j in range(ncy):
                    if exists[(k, i, j)] and rnd.random() < .22 and any(exists.get((k, i + a, j + b)) is False for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                        p = W((xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2, 0)
                        chunks(gd, p, 1.2, rnd.randint(2, 4), seed * 131 + k * 17 + i * 5 + j, size=(.15, .45), z=base_z + z)

        # hanging slabs: a missing cell inside the building hangs from an edge it shared with a standing one
        for i in range(ncx):
            for j in range(ncy):
                if exists[(k, i, j)] or rnd.random() > .05:
                    continue
                for a, b in ((0, -1), (1, 0), (0, 1), (-1, 0)):
                    if exists.get((k, i + a, j + b)):
                        cw, cd = xs[i + 1] - xs[i], ys[j + 1] - ys[j]
                        hx, hy = (xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2
                        ex, ey = hx + a * cw / 2, hy + b * cd / 2           # the hinge edge's middle
                        ang = rnd.uniform(.5, 1.1)
                        Rl = Matrix.Rotation(-ang, 3, Vector((-b, a, 0)))
                        Rw = Matrix.Rotation(yaw, 3, 'Z') @ Rl
                        half = (cw / 2 * .95, cd / 2 * .95, thick / 2)
                        lc = Vector((-a * cw / 2, -b * cd / 2, -thick / 2))
                        pc = Matrix.Rotation(yaw, 3, 'Z') @ (Rl @ lc + Vector((ex, ey, 0)))
                        box(g, "ru_concrete", (c[0] + pc.x, c[1] + pc.y, base_z + z + pc.z), half, R=Rw, top_mat="ru_concrete")
                        break

    # columns: a grid at the bays; a column stands where its storey is not gone, broken off under the break
    for bi in range(nbx + 1):
        for bj in range(nby + 1):
            x, y = xs[bi * sub_x], ys[bj * sub_y]
            edge = bi in (0, nbx) or bj in (0, nby)
            s = .42 if edge else .36
            for k in range(floors):
                z0, z1 = levels[k], levels[k + 1]
                if gone(x, y, (z0 + z1) / 2):
                    if gone(x, y, z0 + .8) or k == 0:
                        break
                    # a stub up to the break
                    zt = z0 + rnd.uniform(.8, (z1 - z0) * .7)
                    off = [(0, 0, 0)] * 4 + [(0, 0, rnd.uniform(-.35, .2)) for _ in range(4)]
                    box(g, "ru_concrete", W(x, y, (z0 + zt) / 2), (s, s, (zt - z0) / 2), yaw, top_mat="ru_fracture", offsets=off)
                    break
                box(g, "ru_concrete", W(x, y, (z0 + z1) / 2 - .17), (s, s, (z1 - z0) / 2 - .17), yaw)

    # facade: spandrels / cladding along the perimeter cells, mullions and glass in the openings
    clad = "ru_panel" if style == "panel" else "ru_concrete"
    sides = [((i, 0), (0, -1)) for i in range(ncx)] + [((ncx - 1, j), (1, 0)) for j in range(ncy)] + \
            [((i, ncy - 1), (0, 1)) for i in range(ncx)] + [((0, j), (-1, 0)) for j in range(ncy)]
    for (i, j), (a, b) in sides:
        if a == 0:
            x0, x1 = xs[i], xs[i + 1]; yv = ys[0] - .16 if b < 0 else ys[ncy] + .16
            mid = ((x0 + x1) / 2, yv); L = (x1 - x0) / 2; ang = 0.0
        else:
            y0, y1 = ys[j], ys[j + 1]; xv = xs[0] - .16 if a < 0 else xs[ncx] + .16
            mid = (xv, (y0 + y1) / 2); L = (y1 - y0) / 2; ang = math.pi / 2
        for k in range(1, floors + 1):
            if not exists[(k, i, j)]:
                continue
            z = levels[k]
            shrink = rnd.uniform(0, .5) if (not exists.get((k, i + (1 if a == 0 else 0), j + (1 if a != 0 else 0)), True) or
                                           not exists.get((k, i - (1 if a == 0 else 0), j - (1 if a != 0 else 0)), True)) else 0
            band = 1.15 if style == "panel" else .95
            box(g, clad, W(mid[0], mid[1], z - band / 2 + .32), (L - shrink, .16, band / 2), yaw + ang)
            below = levels[k - 1] + (.32 if k > 1 else 0)
            if detail and (k == 1 or exists.get((k - 1, i, j))):
                zc = (below + z - band + .32) / 2; hz = (z - band + .32 - below) / 2
                r = rnd.random()
                if r < .14:
                    box(gd, "ru_glass", W(mid[0] - b * 0 * .05 + (0 if a == 0 else -a * .06), mid[1] + (-b * .06 if a == 0 else 0), zc),
                        (L - .05, .02, hz - .02), yaw + ang)
                if r < .7:
                    box(gd, "ru_metal", W(mid[0], mid[1], zc), (.05, .09, hz), yaw + ang)
                if style == "concrete" and k == 1 and rnd.random() < .3:
                    box(g, "ru_metal", W(mid[0], mid[1], below + hz * 1.5), (L - .1, .05, hz * .5), yaw + ang)   # half-down shutter
    # the core: stair and lift walls in the middle, standing a little higher than the floors round it
    cw2, cd2 = min(w * .14, 4.0), min(d * .17, 4.5)
    core_top = min(H, top_h(0, 0) + rnd.uniform(1.0, 5.0))
    for k in range(floors):
        z0, z1 = levels[k], min(levels[k + 1], core_top)
        if z1 - z0 < .6:
            break
        hz = (z1 - z0) / 2
        broken = z1 < levels[k + 1]
        for (px, py, hx, hy) in ((0, -cd2, cw2, .15), (0, cd2, cw2, .15), (-cw2, 0, .15, cd2), (cw2, 0, .15, cd2)):
            if py < 0 and k % 1 == 0:      # a doorway in the front wall: two piers and a lintel
                box(g, "ru_concrete", W(px - cw2 * .62, py, z0 + hz), (cw2 * .38, hy, hz), yaw, top_mat="ru_fracture" if broken else None)
                box(g, "ru_concrete", W(px + cw2 * .62, py, z0 + hz), (cw2 * .38, hy, hz), yaw, top_mat="ru_fracture" if broken else None)
                if z1 - z0 > 2.6:
                    box(g, "ru_concrete", W(px, py, (z0 + 2.4 + z1) / 2), (cw2 * .25, hy, (z1 - z0 - 2.4) / 2), yaw)
                continue
            off = [(0, 0, 0)] * 4 + [(0, 0, rnd.uniform(-.5, 0) if broken else 0) for _ in range(4)]
            box(g, "ru_concrete", W(px, py, z0 + hz), (hx, hy, hz), yaw, top_mat="ru_fracture" if broken else None, offsets=off)

    # brutalist fins at the columns
    if style == "concrete":
        for bi in range(nbx + 1):
            for bj in (0, nby):
                x, y = xs[bi * sub_x], ys[bj * sub_y]
                zt = min(H, top_h(x, y)) - rnd.uniform(0, 2)
                if zt > 2:
                    box(g, "ru_concrete", W(x, y + (-.55 if bj == 0 else .55), zt / 2), (.22, .4, zt / 2), yaw, top_mat="ru_fracture")
    # rubble round the foot where the building came down
    if heaps:
        for _ in range(rnd.randint(1, 3)):
            side = rnd.randrange(4)
            u = rnd.uniform(-.45, .45)
            hx, hy = [(u * w, -d / 2 - 1.5), (w / 2 + 1.5, u * d), (u * w, d / 2 + 1.5), (-w / 2 - 1.5, u * d)][side]
            p = W(hx, hy, 0)
            heap(g, (p[0], p[1], base_z), rnd.uniform(3, 6), rnd.uniform(1.2, 3.2), seed * 7 + side + _, chunks=6, res=heap_res)
    # what stands higher than anyone gets does not collide
    limit = COL_TOP if col_top is None else col_top
    for fi in range(first_face, len(g.F)):
        if g.C[fi] and (limit <= 0 or min(g.V[i][2] for i in g.F[fi]) - base_z > limit):
            g.C[fi] = False
    return H
