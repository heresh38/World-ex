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
TEXTURED = ("ru_concrete", "ru_fracture", "ru_asphalt", "ru_stone", "ru_metal", "ru_panel", "ru_rubble", "ru_banner")
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
class Geo:
    def __init__(self, name):
        self.name = name
        self.V, self.F, self.M, self.S = [], [], [], []
        self.UV = {}

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

    def __len__(self):
        return len(self.F)


def build(geo, collection=None):
    """Geo -> Blender mesh object named geo.name at the origin (plan (E, N, z) -> Blender (N, -E, z))."""
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
    # rubble on what faces up, broken concrete on the steep sides
    P0, P1, P2 = V[Q[:, 0]], V[Q[:, 1]], V[Q[:, 2]]
    nz = np.cross(P1 - P0, P2 - P0)
    nz = nz[:, 2] / (np.linalg.norm(nz, axis=1) + 1e-9)
    mats = ["ru_rubble" if z > .72 else "ru_fracture" for z in nz]
    g.add(V.tolist(), Q.tolist(), mats, smooth=True)


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


# ------------------------------------------------------------------ the ruined tower
def tower(g, gd, c, w, d, floors, yaw=0.0, seed=0, style="panel", top=(.45, 1.0), holes=2, rebar=True,
          base_z=0.0, heaps=True, detail=True, cell_target=3.0, intact_below=0):
    """A ruined tower centred at c (x, y), width w along its local x, depth d along local y, turned by yaw (radians).
    g gets the structure (collides), gd the fine detail (rebar, glass, mullions)."""
    rnd = random.Random(seed)
    T = _rz(yaw)

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
            heap(g, (p[0], p[1], base_z), rnd.uniform(3, 6), rnd.uniform(1.2, 3.2), seed * 7 + side + _, chunks=6)
    return H
