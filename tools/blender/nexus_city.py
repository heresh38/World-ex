"""Nexus Prime, the big city (8.3 x 5.3 km inside its wall), built from the plan tools/city/nexus_plan.py writes
(unreal/ShatteredOrbit/Data/nexus_plan.json). Two outputs:

  --kit    assets/models/nexus_city_kit.glb: the building designs and street pieces the Unreal city builder
           (ASONexusCity) instances on the plan's lots, roads and rail:
             NCB_<shape>_<style>   a building on a unit footprint (x, y -0.5..0.5, z 0..1), scaled per lot to its
                                   width (x), depth (y) and height (z). UV0 = facade coordinates in unit space
                                   (u along the face, v up), UV1.x = 1 where u runs along x (scaled by the width),
                                   0 where it runs along y (scaled by the depth): M_SOFacade turns them into metres
                                   with the instance's custom data (width, depth, height, seed), so every bay and
                                   floor keeps its real size whatever the lot. Roofs use the world-aligned nc_roof.
             NCK_lamp, NCK_station, NCK_roof_ac, NCK_roof_tank, NCK_roof_mast   real size; "along" pieces run
                                   along +x, the lamp's arm reaches along -y (toward the road).
  --tiles  unreal/ShatteredOrbit/SourceArt/NexusCity/nexus_city_tiles.glb (regenerated, not committed): the plan
           itself as 1 km tiles NCT_<i>_<j> (asphalt inside the wall, raised blocks with kerbs, landmark grounds,
           lane paint with crossings and stop lines, the rail and metro viaducts on piers, the city wall with its
           towers, gates and rail portals) and NCL_land (the country outside the wall rising to mountains).
           Writes unreal/ShatteredOrbit/Data/nexus_city.json (tiles and where they go, the designs per district
           kind, roof areas, lane layout per road class for traffic, stations, facade and ground tilings).

Coordinates: the plan is metres (E, N), Spire at the origin. Blender gets (N, -E): Unreal imports Blender (x, y) as
(x, -y), so it sees X = N, Y = E (cm), the plan's own convention. The tiles keep world coordinates (origin 0), so
the city builder places every tile at the origin. Kit pieces: Blender x (the width / "along" axis) = Unreal local X,
Blender y = Unreal local -Y. Ground materials (nc_*) are world-aligned in Unreal, so the
tiles' UVs only serve Blender previews.

Run: blender --background --python tools/blender/nexus_city.py -- [--kit] [--tiles]
"""
import bpy, bmesh, math, os, sys, json, random
from collections import defaultdict
from mathutils import Vector, geometry, noise
sys.path.insert(0, os.path.dirname(__file__))
import bl
from nexus_city_textures import GROUND, FACADE

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
PLAN = os.path.join(ROOT, 'unreal', 'ShatteredOrbit', 'Data', 'nexus_plan.json')
CITY = os.path.join(ROOT, 'unreal', 'ShatteredOrbit', 'Data', 'nexus_city.json')
TILES_OUT = os.path.join(ROOT, 'unreal', 'ShatteredOrbit', 'SourceArt', 'NexusCity', 'src')
TILE = 1000.0
KERB = .15
WALL_H = 38.0

# lanes per road class (each direction): count, lane width, half median; for the paint and later for traffic
LANES = {"highway": dict(n=4, w=3.7, med=.35), "ring": dict(n=3, w=3.6, med=.35), "primary": dict(n=2, w=3.5, med=.35),
         "secondary": dict(n=1, w=3.6, med=.1), "access": dict(n=1, w=3.3, med=.1)}


def log(*a):
    print('[nexus_city]', *a)


def B(p):
    """plan (E, N) -> Blender (x, y) = (N, -E): the FBX import reads Blender (x, y) as Unreal (x, -y), so Unreal
    gets X = N, Y = E (the plan's convention)"""
    return (p[1], -p[0])


# ------------------------------------------------------------------ materials (names are an API for the import)
def materials():
    M = {}
    for name in GROUND:
        M[name] = bl.mat(name, '#ffffff', 0, .8, image=name + '_c.jpg', normal=name + '_n.png')
    for name in FACADE:
        M[name] = bl.mat(name, '#ffffff', 0, .6, image=name + '_c.jpg', normal=name + '_n.png')
    M['nc_rock'] = bl.mat('nc_rock', '#ffffff', 0, .9, image='nx_rock_c.jpg', normal='nx_rock_n.jpg')
    M['nc_paint_white'] = bl.mat('nc_paint_white', '#d8d8d2', 0, .55)
    M['nc_paint_yellow'] = bl.mat('nc_paint_yellow', '#d9a521', 0, .55)
    M['nc_steel'] = bl.mat('nc_steel', '#3d424a', .8, .38)
    M['nc_rail'] = bl.mat('nc_rail', '#6f7378', 1.0, .3)
    M['nc_tunnel'] = bl.mat('nc_tunnel', '#040506', 0, 1.0)
    M['nc_glow_cyan'] = bl.mat('nc_glow_cyan', '#2fd8ff', 0, .4, emit='#2fd8ff', strength=8)
    M['nc_glow_violet'] = bl.mat('nc_glow_violet', '#9b5cff', 0, .4, emit='#9b5cff', strength=8)
    M['nc_glow_warm'] = bl.mat('nc_glow_warm', '#ffc27a', 0, .4, emit='#ffc27a', strength=6)
    return M


# ------------------------------------------------------------------ mesh accumulator
class Acc:
    """Faces with their own corners (no shared vertices across faces; merged at the end), a material per face,
    UV0 per corner and optionally UV1 per corner."""

    def __init__(self):
        self.v, self.f, self.m, self.uv, self.uv1 = [], [], [], [], []

    def face(self, pts, mat, uv=None, uv1=None, want=None):
        pts = [tuple(p) for p in pts]
        if want is not None:
            n = (Vector(pts[1]) - Vector(pts[0])).cross(Vector(pts[2]) - Vector(pts[0]))
            if n.length > 1e-12 and n.dot(Vector(want)) < 0:
                pts = pts[::-1]
                uv = uv[::-1] if uv else uv
                uv1 = uv1[::-1] if uv1 else uv1
        i = len(self.v)
        self.v.extend(pts)
        self.f.append(tuple(range(i, i + len(pts))))
        self.m.append(mat)
        self.uv.append(uv or [(p[0] / 8, p[1] / 8) for p in pts])
        self.uv1.append(uv1 or [(0, 0)] * len(pts))

    def object(self, name, M, loc=(0, 0, 0), smooth=False, two_uv=False):
        mats = sorted(set(self.m))
        me = bpy.data.meshes.new(name)
        lx, ly, lz = loc
        me.from_pydata([(x - lx, y - ly, z - lz) for x, y, z in self.v], [], self.f)
        for k in mats:
            me.materials.append(M[k])
        idx = {k: i for i, k in enumerate(mats)}
        me.polygons.foreach_set('material_index', [idx[k] for k in self.m])
        uvl = me.uv_layers.new(name='UVMap')
        flat = [c for face in self.uv for c in face]
        uvl.data.foreach_set('uv', [x for c in flat for x in c])
        if two_uv:
            uv2 = me.uv_layers.new(name='UVFacade')
            flat = [c for face in self.uv1 for c in face]
            uv2.data.foreach_set('uv', [x for c in flat for x in c])
        me.update()
        bm = bmesh.new(); bm.from_mesh(me)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=.0005)
        bm.to_mesh(me); bm.free()
        for p in me.polygons:
            p.use_smooth = smooth
        o = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(o)
        o.location = loc
        return o


def area2(pts):
    return .5 * sum(pts[i - 1][0] * pts[i][1] - pts[i][0] * pts[i - 1][1] for i in range(len(pts)))


def clean(pts):
    out = []
    for p in pts:
        if not out or (abs(p[0] - out[-1][0]) > .01 or abs(p[1] - out[-1][1]) > .01):
            out.append((p[0], p[1]))
    if len(out) > 2 and abs(out[0][0] - out[-1][0]) < .01 and abs(out[0][1] - out[-1][1]) < .01:
        out.pop()
    return out


def ccw(pts):
    return pts if area2(pts) > 0 else pts[::-1]


def top(acc, pts, z, mat, scale=8.0):
    """A flat polygon facing up (any simple polygon, triangulated)."""
    pts = ccw(clean(pts))
    if len(pts) < 3:
        return
    tris = geometry.tessellate_polygon([[Vector((x, y, 0)) for x, y in pts]])
    for t in tris:
        tri = [(pts[i][0], pts[i][1], z) for i in t]
        acc.face(tri, mat, [(p[0] / scale, p[1] / scale) for p in tri], want=(0, 0, 1))


def sides(acc, pts, z0, z1, mat, scale=2.0, outward=True):
    pts = ccw(clean(pts))
    s = 0.0
    for i in range(len(pts)):
        a, b = pts[i], pts[(i + 1) % len(pts)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy)
        if L < 1e-4:
            continue
        want = (dy / L, -dx / L, 0) if outward else (-dy / L, dx / L, 0)
        acc.face([(a[0], a[1], z0), (b[0], b[1], z0), (b[0], b[1], z1), (a[0], a[1], z1)], mat,
                 [(s / scale, z0 / scale), ((s + L) / scale, z0 / scale), ((s + L) / scale, z1 / scale), (s / scale, z1 / scale)], want=want)
        s += L


def pip(pt, poly):
    x, y = pt; inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]; x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1 + 1e-12) + x1:
            inside = not inside
    return inside


def ellipse(c, r, n=96):
    return [(c[0] + r[0] * math.cos(2 * math.pi * i / n), c[1] + r[1] * math.sin(2 * math.pi * i / n)) for i in range(n)]


def clip_convex(poly, clipper):
    """Sutherland-Hodgman: poly clipped by a convex CCW clipper."""
    out = poly
    for i in range(len(clipper)):
        a, b = clipper[i], clipper[(i + 1) % len(clipper)]
        inp, out = out, []
        if not inp:
            break
        side = lambda p: (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
        for j in range(len(inp)):
            p, q = inp[j - 1], inp[j]
            sp, sq = side(p), side(q)
            if sq >= 0:
                if sp < 0:
                    t = sp / (sp - sq); out.append((p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t))
                out.append(q)
            elif sp >= 0:
                t = sp / (sp - sq); out.append((p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t))
    return out


# ------------------------------------------------------------------ polylines
def cum(pts):
    s = [0.0]
    for i in range(1, len(pts)):
        s.append(s[-1] + math.dist(pts[i - 1], pts[i]))
    return s


def at(pts, S, d):
    """point and unit direction at arc length d"""
    d = max(0.0, min(S[-1], d))
    for i in range(1, len(pts)):
        if S[i] >= d or i == len(pts) - 1:
            L = S[i] - S[i - 1] or 1e-9
            t = (d - S[i - 1]) / L
            a, b = pts[i - 1], pts[i]
            return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t), ((b[0] - a[0]) / L, (b[1] - a[1]) / L)


def sub(pts, S, d0, d1):
    out = [at(pts, S, d0)[0]]
    for i in range(1, len(pts) - 1):
        if d0 < S[i] < d1:
            out.append(pts[i])
    out.append(at(pts, S, d1)[0])
    return out


def offset_line(pts, o):
    """the polyline moved sideways by o (left of the direction positive), mitred"""
    n = len(pts); out = []
    for i in range(n):
        ds = []
        if i > 0:
            ds.append((pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]))
        if i < n - 1:
            ds.append((pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]))
        nx = ny = 0.0
        for dx, dy in ds:
            L = math.hypot(dx, dy) or 1e-9
            nx += -dy / L; ny += dx / L
        L = math.hypot(nx, ny) or 1e-9
        nx, ny = nx / L, ny / L
        k = 1.0
        if len(ds) == 2:
            dx, dy = ds[0]; L0 = math.hypot(dx, dy) or 1e-9
            k = 1.0 / max(.5, nx * -dy / L0 + ny * dx / L0)
        out.append((pts[i][0] + nx * o * k, pts[i][1] + ny * o * k))
    return out


def strip(acc, pts, o, hw, z, mat):
    a = offset_line(pts, o - hw); b = offset_line(pts, o + hw)
    for i in range(len(pts) - 1):
        acc.face([(a[i][0], a[i][1], z), (a[i + 1][0], a[i + 1][1], z), (b[i + 1][0], b[i + 1][1], z), (b[i][0], b[i][1], z)], mat, want=(0, 0, 1))


# ------------------------------------------------------------------ building kit
class Kit:
    """A unit-footprint building: facade faces get UV0 (u along the face + .5, v = z) and UV1.x (1: u along x)."""

    def __init__(self, style):
        self.a = Acc(); self.style = 'ncf_' + style

    def quad(self, pts, mat=None, want=None):
        mat = mat or self.style
        n = (Vector(pts[1]) - Vector(pts[0])).cross(Vector(pts[2]) - Vector(pts[0]))
        if want is not None and n.dot(Vector(want)) < 0:
            pts = pts[::-1]; n = -n
        if n.length < 1e-12:
            return
        n.normalize()
        if abs(n.z) > .72 or mat.startswith('nc_'):
            self.a.face(pts, 'nc_roof' if mat.startswith('ncf_') else mat, [(p[0] + .5, p[1] + .5) for p in pts], [(1, 1)] * len(pts))
            return
        along_x = abs(n.y) >= abs(n.x)
        uv = [((p[0] if along_x else p[1]) + .5, p[2]) for p in pts]
        self.a.face(pts, mat, uv, [(1.0 if along_x else 0.0, 0)] * len(pts))

    def prism(self, ring, z0, z1, mat=None, top=True, ring_top=None, roof=None):
        """vertical (or battered, with ring_top) walls round a CCW footprint ring, a flat top"""
        ring = ccw(ring); rt = ccw(ring_top) if ring_top else ring
        cx = sum(p[0] for p in ring) / len(ring); cy = sum(p[1] for p in ring) / len(ring)
        for i in range(len(ring)):
            a, b = ring[i], ring[(i + 1) % len(ring)]
            at_, bt = rt[i], rt[(i + 1) % len(rt)]
            out = ((a[0] + b[0]) / 2 - cx, (a[1] + b[1]) / 2 - cy, 0)
            self.quad([(a[0], a[1], z0), (b[0], b[1], z0), (bt[0], bt[1], z1), (at_[0], at_[1], z1)], mat, want=out)
        if top:
            tris = geometry.tessellate_polygon([[Vector((x, y, 0)) for x, y in rt]])
            for t in tris:
                self.quad([(rt[i][0], rt[i][1], z1) for i in t], roof or 'nc_roof', want=(0, 0, 1))

    def box(self, x0, x1, y0, y1, z0, z1, mat=None, top=True, roof=None):
        self.prism([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], z0, z1, mat, top, roof=roof)

    def band(self, x0, x1, y0, y1, z, h=.006, out=.006, mat='nc_glow_cyan'):
        """a lit ring round a tier just under z (sides only: the roof stays roof)"""
        self.box(x0 - out, x1 + out, y0 - out, y1 + out, z - h, z, mat, top=False)

    def oct(self, r, ch):
        return [(-r + ch, -r), (r - ch, -r), (r, -r + ch), (r, r - ch), (r - ch, r), (-r + ch, r), (-r, r - ch), (-r, -r + ch)]

    def vault(self, axis, z0, rise, mat='nc_steel', segs=12, ends=True):
        """a barrel roof over the whole footprint, its axis along x or y, the gable ends as facade"""
        for i in range(segs):
            a0 = math.pi * i / segs; a1 = math.pi * (i + 1) / segs
            p = lambda a, s: ((s, .5 * math.cos(a), z0 + rise * math.sin(a)) if axis == 'x' else (.5 * math.cos(a), s, z0 + rise * math.sin(a)))
            q = [p(a0, -.5), p(a0, .5), p(a1, .5), p(a1, -.5)]
            mid = p((a0 + a1) / 2, 0)
            self.quad(q, mat, want=(mid[0], mid[1], mid[2] - z0) if axis == 'y' else (0, mid[1], mid[2] - z0))
        if ends:
            for s in (-.5, .5):
                ring = [((s, .5 * math.cos(math.pi * i / segs), z0 + rise * math.sin(math.pi * i / segs)) if axis == 'x' else
                         (.5 * math.cos(math.pi * i / segs), s, z0 + rise * math.sin(math.pi * i / segs))) for i in range(segs + 1)]
                c = (s, 0, z0) if axis == 'x' else (0, s, z0)
                for i in range(segs):
                    self.quad([c, ring[i], ring[i + 1]], want=(s, 0, 0) if axis == 'x' else (0, s, 0))


def design(shape, style):
    k = Kit(style)
    roof = None
    if shape == 'tower':
        tiers = [(0, .14, 0), (.14, .82, .07), (.82, .94, .17), (.94, 1.0, .29)]
        for z0, z1, ins in tiers:
            r = .5 - ins
            k.box(-r, r, -r, r, z0, z1)
            k.band(-r, r, -r, r, z1, .004, .004)
        roof = [-.21, .21, -.21, .21, 1.0]
    elif shape == 'slab':
        k.box(-.5, .5, -.5, .5, 0, .97)
        k.box(-.5, .5, -.5, .5, .97, 1.0, 'nc_steel', roof='nc_roof')
        for sx in (-1, 1):
            for sy in (-1, 1):
                x, y = sx * .5, sy * .5
                k.box(x - .012, x + .012, y - .012, y + .012, .02, .995, 'nc_glow_cyan', roof='nc_glow_cyan')
        roof = [-.45, .45, -.45, .45, 1.0]
    elif shape == 'chamfer':
        k.prism(k.oct(.5, .17), 0, .9)
        k.prism(k.oct(.36, .12), .9, 1.0)
        k.prism(k.oct(.505, .17), .898, .905, 'nc_glow_cyan', top=False)
        roof = [-.25, .25, -.25, .25, 1.0]
    elif shape == 'podium_tower':
        k.box(-.5, .5, -.5, .5, 0, .2)
        k.band(-.5, .5, -.5, .5, .2, .005, .004)
        k.box(-.44, .16, -.36, .36, .2, 1.0)
        k.band(-.44, .16, -.36, .36, 1.0, .006, .004, 'nc_glow_violet')
        roof = [.22, .46, -.4, .4, .2]
    elif shape == 'stepped':
        k.box(-.5, .5, -.5, .5, 0, .45)
        k.box(-.5, .5, -.5, .2, .45, .75)
        k.box(-.5, .5, -.5, -.12, .75, 1.0)
        for y1, z in ((.5, .45), (.2, .75), (-.12, 1.0)):
            k.band(-.5, .5, -.5, y1, z, .005, .003, 'nc_glow_warm')
        roof = [-.45, .45, .25, .45, .45]
    elif shape == 'courtyard':
        k.box(-.5, .5, .18, .5, 0, 1.0)
        k.box(-.5, -.18, -.5, .18, 0, 1.0)
        k.box(.18, .5, -.5, .18, 0, 1.0)
        k.band(-.5, .5, .18, .5, 1.0, .005, .003)
        roof = [-.45, .45, .25, .45, 1.0]
    elif shape == 'hall':
        k.box(-.5, .5, -.5, .5, 0, .55, top=False)
        k.vault('x', .55, .45)
        k.box(-.5, .5, -.51, -.49, .2, .22, 'nc_glow_warm', roof='nc_glow_warm')
    elif shape == 'market':
        k.box(-.5, .5, -.5, .5, 0, .85)
        for sy in (-1, 1):
            y = sy * .5
            k.box(-.48, .48, y - (.0 if sy > 0 else .07), y + (.07 if sy > 0 else 0), .3, .32, 'nc_steel', roof='nc_steel')
            k.box(-.48, .48, y + sy * .07 - .004, y + sy * .07 + .004, .3, .32, 'nc_glow_warm', roof='nc_glow_warm')
        k.band(-.5, .5, -.5, .5, .85, .006, .004, 'nc_glow_violet')
        roof = [-.42, .42, -.42, .42, .85]
    elif shape == 'shed':
        k.box(-.5, .5, -.5, .5, 0, .6, top=False)
        n = 4
        for i in range(n):
            x0 = -.5 + i / n; x1 = x0 + 1 / n
            # glazed vertical face at x0 facing -x, the slope down to x1
            k.quad([(x0, -.5, .6), (x0, .5, .6), (x0, .5, .9), (x0, -.5, .9)], 'ncf_glass', want=(-1, 0, 0))
            k.quad([(x0, -.5, .9), (x0, .5, .9), (x1, .5, .6), (x1, -.5, .6)], 'nc_steel', want=(.3, 0, 1))
            for sy in (-.5, .5):
                k.quad([(x0, sy, .6), (x1, sy, .6), (x0, sy, .9)], want=(0, sy, 0))
    elif shape == 'tanks':
        k.box(-.5, .5, -.5, .5, 0, .06, 'nc_kerb', roof='nc_lot')
        k.box(-.5, -.1, -.5, .5, .06, .45)
        for cx, cy in ((.22, -.25), (.22, .25)):
            ring = [(cx + .2 * math.cos(2 * math.pi * i / 16), cy + .2 * math.sin(2 * math.pi * i / 16)) for i in range(16)]
            k.prism(ring, .06, .9, 'nc_steel', roof='nc_steel')
            k.prism([(cx + .205 * math.cos(2 * math.pi * i / 16), cy + .205 * math.sin(2 * math.pi * i / 16)) for i in range(16)], .7, .72, 'nc_glow_warm', top=False)
        roof = [-.45, -.15, -.45, .45, .45]
    elif shape == 'bunker':
        k.prism([(-.5, -.5), (.5, -.5), (.5, .5), (-.5, .5)], 0, .75, ring_top=[(-.38, -.38), (.38, -.38), (.38, .38), (-.38, .38)])
        k.box(-.18, .18, -.24, .24, .75, 1.0)
        k.band(-.18, .18, -.24, .24, 1.0, .01, .005, 'nc_glow_cyan')
        roof = [-.34, -.22, -.34, .34, .75]
    elif shape == 'hangar':
        k.box(-.5, .5, -.5, .5, 0, .35, top=False)
        k.vault('y', .35, .65, 'nc_steel')
        k.box(-.36, .36, -.505, -.495, .0, .3, 'nc_glow_cyan', roof='nc_glow_cyan')
    elif shape == 'ruin':
        rnd = random.Random(hash(style) & 0xffff)
        k.box(-.5, .5, -.5, .5, 0, .5)
        for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            h = rnd.uniform(.62, 1.0)
            k.box(sx * .5 - (.3 if sx > 0 else 0), sx * .5 + (.3 if sx < 0 else 0), sy * .5 - (.3 if sy > 0 else 0), sy * .5 + (.3 if sy < 0 else 0), .5, h)
        k.box(-.2, .2, -.5, -.3, .5, .7)
    elif shape == 'domelab':
        k.box(-.5, .5, -.5, .5, 0, .5)
        k.band(-.5, .5, -.5, .5, .5, .006, .004)
        rings = 8; segs = 24
        pt = lambda i, j: (.42 * math.cos(math.pi / 2 * i / rings) * math.cos(2 * math.pi * j / segs),
                           .42 * math.cos(math.pi / 2 * i / rings) * math.sin(2 * math.pi * j / segs),
                           .5 + .5 * math.sin(math.pi / 2 * i / rings))
        for i in range(rings):
            for j in range(segs):
                q = [pt(i, j), pt(i, j + 1), pt(i + 1, j + 1), pt(i + 1, j)]
                mid = pt(i + .5, j + .5)
                k.quad(q, 'ncf_glass', want=(mid[0], mid[1], mid[2] - .5))
    return k.a, roof


SHAPES_TALL = {'tower', 'chamfer', 'podium_tower', 'slab'}
KIND_DESIGNS = {
    "spire": [("tower", "glass"), ("slab", "glass"), ("chamfer", "glass"), ("tower", "panel"), ("podium_tower", "glass"), ("chamfer", "panel")],
    "mixed": [("tower", "office"), ("slab", "office"), ("podium_tower", "glass"), ("courtyard", "office"), ("chamfer", "panel"), ("stepped", "office")],
    "research": [("domelab", "panel"), ("slab", "panel"), ("chamfer", "glass"), ("courtyard", "panel"), ("podium_tower", "panel")],
    "market": [("market", "stone"), ("courtyard", "stone"), ("stepped", "stone"), ("hall", "stone"), ("slab", "stone")],
    "arena": [("slab", "panel"), ("podium_tower", "panel"), ("hall", "panel"), ("market", "panel")],
    "military": [("bunker", "military"), ("slab", "military"), ("hangar", "military"), ("courtyard", "military")],
    "housing": [("stepped", "housing"), ("slab", "housing"), ("courtyard", "housing"), ("tower", "housing")],
    "industrial": [("shed", "industrial"), ("tanks", "industrial"), ("hall", "industrial"), ("slab", "industrial")],
    "dockyard": [("hangar", "industrial"), ("shed", "industrial"), ("tanks", "industrial"), ("hall", "panel")],
    "ruins": [("ruin", "stone"), ("ruin", "office"), ("ruin", "housing"), ("bunker", "stone")],
}
HEIGHTS = {"hall": (8, 30), "market": (8, 26), "shed": (8, 24), "tanks": (10, 30), "hangar": (14, 40), "bunker": (8, 36),
           "domelab": (14, 60), "ruin": (6, 60), "stepped": (12, 120), "courtyard": (10, 110)}


def street_kit(M):
    out = []
    # street lamp: post, arm toward -y (the road), lit head
    k = Kit('panel')
    ring = lambda r, n=8: [(r * math.cos(2 * math.pi * i / n), r * math.sin(2 * math.pi * i / n)) for i in range(n)]
    k.prism(ring(.22), 0, .5, 'nc_steel', roof='nc_steel')
    k.prism(ring(.11), .5, 9.0, 'nc_steel', roof='nc_steel')
    k.box(-.08, .08, -2.6, 0, 8.85, 9.0, 'nc_steel', roof='nc_steel')
    k.box(-.2, .2, -2.9, -2.1, 8.7, 8.85, 'nc_steel', roof='nc_steel')
    k.box(-.17, .17, -2.85, -2.15, 8.66, 8.7, 'nc_glow_warm', roof='nc_glow_warm')
    k.box(-.12, .12, -.13, .13, 3.0, 3.6, 'nc_glow_cyan', roof='nc_glow_cyan')
    out.append(k.a.object('NCK_lamp', M, two_uv=True))
    # station: platforms both sides of the 11 m deck (deck top = origin), canopy, lift towers to the ground
    k = Kit('glass')
    L = 70.0
    for s in (-1, 1):
        k.box(-L, L, s * 5.6 if s > 0 else -9.8, 9.8 if s > 0 else -5.6, -1.6, 1.05, 'nc_kerb', roof='nc_plaza')
        y = s * 5.75
        k.box(-L, L, y - .2, y + .2, 1.05, 1.07, 'nc_paint_yellow', roof='nc_paint_yellow')
        for i in range(11):
            x = -L + 7 + i * 12.6
            k.box(x - .25, x + .25, s * 9.3 - .25, s * 9.3 + .25, 1.05, 7.4, 'nc_steel', roof='nc_steel')
        k.box(-60, -52, s * 9.8 if s > 0 else -14.5, 14.5 if s > 0 else -9.8, -17, 8.5)
        k.band(-60, -52, s * 9.8 if s > 0 else -14.5, 14.5 if s > 0 else -9.8, 8.5, .3, .05)
    k.box(-L - 1, L + 1, -10.4, 10.4, 7.4, 8.0, 'nc_steel', roof='nc_roof')
    for s in (-1, 1):
        k.box(-L - 1, L + 1, s * 10.4 - .06, s * 10.4 + .06, 7.45, 7.6, 'nc_glow_cyan', roof='nc_glow_cyan')
    out.append(k.a.object('NCK_station', M, two_uv=True))
    # roof clutter (real size)
    k = Kit('panel')
    k.box(-1.6, 1.6, -1.1, 1.1, 0, 1.5, 'nc_steel', roof='nc_steel')
    k.prism(ring(.8, 16), 1.5, 1.7, 'nc_rail', roof='nc_tunnel')
    out.append(k.a.object('NCK_roof_ac', M, two_uv=True))
    k = Kit('panel')
    for sx in (-1, 1):
        for sy in (-1, 1):
            k.box(sx * 1.2 - .1, sx * 1.2 + .1, sy * 1.2 - .1, sy * 1.2 + .1, 0, 2.2, 'nc_steel', roof='nc_steel')
    k.prism(ring(1.8, 16), 2.2, 5.6, 'nc_steel', roof='nc_steel')
    k.prism(ring(1.82, 16), 4.9, 5.0, 'nc_glow_warm', top=False)
    out.append(k.a.object('NCK_roof_tank', M, two_uv=True))
    k = Kit('panel')
    k.prism(ring(.18, 6), 0, 14, 'nc_steel', roof='nc_steel')
    k.prism(ring(.3, 6), 14, 14.6, 'nc_glow_cyan', roof='nc_glow_cyan')
    for z in (5, 9):
        k.box(-1.2, 1.2, -.05, .05, z, z + .1, 'nc_steel', roof='nc_steel')
    out.append(k.a.object('NCK_roof_mast', M, two_uv=True))
    return out


def build_kit(M):
    designs = {}
    for kind, lst in KIND_DESIGNS.items():
        for shape, style in lst:
            name = f"NCB_{shape}_{style}"
            if name in designs:
                continue
            acc, roof = design(shape, style)
            acc.object(name, M, two_uv=True)
            lo, hi = HEIGHTS.get(shape, (20, 400))
            designs[name] = dict(shape=shape, style=style, tall=shape in SHAPES_TALL, min_h=lo, max_h=hi, roof=roof)
    street_kit(M)
    bl.export('nexus_city_kit.glb')
    return designs


# ------------------------------------------------------------------ tiles
class Tiles:
    def __init__(self, x0, y0):
        self.x0, self.y0 = x0, y0
        self.acc = defaultdict(Acc)

    def key(self, x, y):
        return (int((x - self.x0) // TILE), int((y - self.y0) // TILE))

    def at(self, pts):
        x = sum(p[0] for p in pts) / len(pts); y = sum(p[1] for p in pts) / len(pts)
        return self.acc[self.key(x, y)]

    def centre(self, k):
        return (self.x0 + (k[0] + .5) * TILE, self.y0 + (k[1] + .5) * TILE)


def build_tiles(M, plan):
    wall = ccw([B(p) for p in plan["wall"]])
    xs = [p[0] for p in wall]; ys = [p[1] for p in wall]
    T = Tiles(math.floor(min(xs) / TILE) * TILE, math.floor(min(ys) / TILE) * TILE)
    stats = defaultdict(int)

    # ground: asphalt everywhere inside the wall, in 100 m cells
    for gx in range(int(min(xs) // 100) - 1, int(max(xs) // 100) + 2):
        for gy in range(int(min(ys) // 100) - 1, int(max(ys) // 100) + 2):
            cell = [(gx * 100, gy * 100), (gx * 100 + 100, gy * 100), (gx * 100 + 100, gy * 100 + 100), (gx * 100, gy * 100 + 100)]
            c = clip_convex(cell, wall)
            if len(c) >= 3 and abs(area2(c)) > 1:
                top(T.at(c), c, 0.0, 'nc_asphalt')
    # blocks: raised slabs with kerbs; yards in the working districts, plaza stone round the Spire
    yard = {"industrial", "dockyard", "military"}
    for blk in plan["blocks"]:
        pts = clean([B(p) for p in blk["poly"]])
        if len(pts) < 3:
            continue
        kind = plan["districts"].get(blk["district"], {}).get("kind", "mixed")
        mat = 'nc_lot' if kind in yard else 'nc_plaza' if kind == 'spire' else 'nc_pavers'
        a = T.at(pts)
        top(a, pts, KERB, mat)
        sides(a, pts, -.05, KERB, 'nc_kerb')
        stats['blocks'] += 1
    # landmark grounds
    lm_mat = {"dock_ring": 'nc_lot', "arena": 'nc_plaza', "park": 'nc_grass', "plaza": 'nc_plaza', "dome": 'nc_plaza'}
    for name, L in plan["landmarks"].items():
        e = ellipse(B(L["centre"]), (L["radius"][1], L["radius"][0]), 128)
        a = T.at(e)
        top(a, e, KERB + .02, lm_mat[L["kind"]])
        sides(a, e, -.05, KERB + .02, 'nc_kerb')
        if L["kind"] in ("plaza", "arena", "dome"):         # a lit ring inlaid round the plazas
            ring_o = ellipse(B(L["centre"]), (L["radius"][1] - 6, L["radius"][0] - 6), 128)
            ring_i = ellipse(B(L["centre"]), (L["radius"][1] - 6.6, L["radius"][0] - 6.6), 128)
            for i in range(128):
                j = (i + 1) % 128
                a.face([(*ring_i[i], KERB + .03), (*ring_i[j], KERB + .03), (*ring_o[j], KERB + .03), (*ring_o[i], KERB + .03)], 'nc_glow_cyan', want=(0, 0, 1))

    # ---------------- lane paint
    roads = plan["roads"]
    nodes = [B(p) for p in roads["nodes"]]
    deg = defaultdict(int); wmax = defaultdict(float)
    for e in roads["edges"]:
        for n in (e["a"], e["b"]):
            deg[n] += 1; wmax[n] = max(wmax[n], e["w"])
    radius = {n: (wmax[n] / 2 + 1.0 if deg[n] >= 3 else 0.0) for n in deg}
    Z = .012
    for e in roads["edges"]:
        pts = clean([B(p) for p in e["pts"]])
        if len(pts) < 2:
            continue
        S = cum(pts); L = S[-1]
        cls = e["cls"]; w = e["w"]; lane = LANES[cls]
        ra, rb = radius.get(e["a"], 0), radius.get(e["b"], 0)
        cross = cls != "highway"
        s0 = ra + (6.0 if ra and cross else 1.0 if ra else 0)
        s1 = L - (rb + (6.0 if rb and cross else 1.0 if rb else 0))
        if s1 - s0 < 4:
            continue
        def paint(o, hw, mat, dashed=False, a=s0, b=s1):
            if dashed:
                d = a
                while d < b - 1:
                    seg = sub(pts, S, d, min(b, d + 3.0))
                    strip(T.at(seg), seg, o, hw, Z, mat)
                    d += 9.0
            else:
                d = a
                while d < b - .5:                       # chunks so long roads spread over the tiles
                    seg = sub(pts, S, d, min(b, d + 120.0))
                    strip(T.at(seg), seg, o, hw, Z, mat)
                    d += 120.0
        n, lw, med = lane["n"], lane["w"], lane["med"]
        if med > .2:                                    # double yellow
            for s in (-1, 1):
                paint(s * (med - .1), .06, 'nc_paint_yellow')
                paint(s * (med + .1), .06, 'nc_paint_yellow')
        else:
            paint(0, .07, 'nc_paint_yellow' if cls == "secondary" else 'nc_paint_white', dashed=True)
        for s in (-1, 1):
            for k in range(1, n):
                paint(s * (med + k * lw), .07, 'nc_paint_white', dashed=True)
            paint(s * min(w / 2 - .9, med + n * lw), .08, 'nc_paint_white')
        stats['paint_edges'] += 1
        # crossings and stop lines at junction ends
        if cross:
            for end, r in ((0, ra), (1, rb)):
                if not r:
                    continue
                d = r + .6 if end == 0 else L - r - .6
                p, t = at(pts, S, d)
                nx, ny = -t[1], t[0]
                a = T.at([p])
                # zebra: bars along the road, 4 m long, across the full width
                sgn = 1 if end == 0 else -1
                o = -w / 2 + 1.2
                while o < w / 2 - 1.0:
                    c0 = (p[0] + nx * o, p[1] + ny * o)
                    q = [(c0[0] - nx * .3, c0[1] - ny * .3), (c0[0] + nx * .3, c0[1] + ny * .3)]
                    quad = [(q[0][0], q[0][1], Z), (q[1][0], q[1][1], Z),
                            (q[1][0] + t[0] * 4 * sgn, q[1][1] + t[1] * 4 * sgn, Z), (q[0][0] + t[0] * 4 * sgn, q[0][1] + t[1] * 4 * sgn, Z)]
                    a.face(quad, 'nc_paint_white', want=(0, 0, 1))
                    o += 1.25
                # stop line across the incoming half (traffic keeps right: incoming lanes are right of a->b at b)
                d2 = d + 4.8 * sgn
                p2, _ = at(pts, S, d2)
                side = 1 if end == 0 else -1
                o0, o1 = (med, min(w / 2 - .9, med + n * lw))
                q0 = (p2[0] + nx * o0 * side, p2[1] + ny * o0 * side); q1 = (p2[0] + nx * o1 * side, p2[1] + ny * o1 * side)
                a.face([(q0[0], q0[1], Z), (q1[0], q1[1], Z), (q1[0] + t[0] * .5, q1[1] + t[1] * .5, Z), (q0[0] + t[0] * .5, q0[1] + t[1] * .5, Z)],
                       'nc_paint_white', want=(0, 0, 1))

    # ---------------- viaducts: rail (9 m) and metro loop (16 m)
    blocks_b = [clean([B(p) for p in b["poly"]]) for b in plan["blocks"]]
    grid = defaultdict(list)
    for i, pb in enumerate(blocks_b):
        bx = [p[0] for p in pb]; by = [p[1] for p in pb]
        for gx in range(int(min(bx) // 100), int(max(bx) // 100) + 1):
            for gy in range(int(min(by) // 100), int(max(by) // 100) + 1):
                grid[(gx, gy)].append(i)
    lms = [ellipse(B(L["centre"]), (L["radius"][1], L["radius"][0]), 64) for L in plan["landmarks"].values()]

    def solid(p):
        """a pier may stand here: on a block or a landmark ground, not in a road"""
        for i in grid.get((int(p[0] // 100), int(p[1] // 100)), ()):
            if pip(p, blocks_b[i]):
                return True
        return any(pip(p, e) for e in lms)

    def wall_dist(p):
        best = 1e9
        for i in range(len(wall)):
            a, b = wall[i], wall[(i + 1) % len(wall)]
            dx, dy = b[0] - a[0], b[1] - a[1]
            t = max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy)))
            best = min(best, math.dist(p, (a[0] + dx * t, a[1] + dy * t)))
        return best

    portals, stations = [], []
    DECK = [(-5.5, 0), (5.5, 0), (5.5, -.6), (3.4, -1.8), (-3.4, -1.8), (-5.5, -.6)]   # (lateral, z) CCW seen from ahead

    def viaduct(line, H, closed):
        pts = [B(p) for p in line]
        if closed:
            pts = pts + [pts[0]]
        # resample every <= 30 m, keep only the part inside the wall (portals where it is cut)
        S = cum(pts); n = max(2, int(S[-1] / 30) + 1)
        dense = [at(pts, S, S[-1] * i / (n - 1))[0] for i in range(n)]
        runs, cur = [], []
        for p in dense:
            ok = pip(p, wall) and wall_dist(p) > 2.0
            if ok:
                cur.append(p)
            elif cur:
                runs.append(cur); cur = []
        if cur:
            runs.append(cur)
        for run in runs:
            if len(run) < 2:
                continue
            # stretch the cut ends to the wall face and mark a portal there
            for end in (0, -1):
                p = run[end]; q = run[1] if end == 0 else run[-2]
                d = (p[0] - q[0], p[1] - q[1]); L = math.hypot(*d) or 1; d = (d[0] / L, d[1] / L)
                if not closed and wall_dist(p) < 40:
                    k = 0.0
                    while k < 60 and wall_dist((p[0] + d[0] * k, p[1] + d[1] * k)) > .4 and pip((p[0] + d[0] * k, p[1] + d[1] * k), wall):
                        k += .5
                    e = (p[0] + d[0] * k, p[1] + d[1] * k)
                    run[end] = e
                    portals.append(dict(pos=e, dir=d, h=H))
            deck(run, H, closed and len(runs) == 1)

    def deck(run, H, closed):
        segs = len(run) - 1
        for i in range(segs):
            a, b = run[i], run[i + 1]
            dx, dy = b[0] - a[0], b[1] - a[1]; L = math.hypot(dx, dy) or 1
            # miter directions at both ends from the neighbours
            def side(j):
                ds = []
                if j > 0 or closed:
                    pj = run[j - 1] if j > 0 else run[-2]
                    ds.append((run[j][0] - pj[0], run[j][1] - pj[1]))
                if j < len(run) - 1 or closed:
                    nj = run[j + 1] if j < len(run) - 1 else run[1]
                    ds.append((nj[0] - run[j][0], nj[1] - run[j][1]))
                nx = ny = 0.0
                for ex, ey in ds:
                    l = math.hypot(ex, ey) or 1; nx += -ey / l; ny += ex / l
                l = math.hypot(nx, ny) or 1
                return nx / l, ny / l
            na, nb = side(i), side(i + 1)
            acc = T.at([a, b])
            prof_a = [(a[0] + na[0] * l, a[1] + na[1] * l, H + z) for l, z in DECK]
            prof_b = [(b[0] + nb[0] * l, b[1] + nb[1] * l, H + z) for l, z in DECK]
            for k in range(len(DECK)):
                k2 = (k + 1) % len(DECK)
                l0, z0 = DECK[k]; l1, z1 = DECK[k2]
                out = ((l0 + l1) / 2, (z0 + z1) / 2 + .8)          # away from the profile's centre (convex)
                want = (-dy / L * out[0], dx / L * out[0], out[1])
                mat = 'nc_lot' if k == 0 else 'nc_kerb'
                acc.face([prof_a[k], prof_b[k], prof_b[k2], prof_a[k2]], mat, want=want)
            for l0, l1, z0, z1, mat in ((-5.5, -5.2, 0, 1.0, 'nc_kerb'), (5.2, 5.5, 0, 1.0, 'nc_kerb'),
                                        (-5.52, -5.5, -.62, -.5, 'nc_glow_cyan'), (5.5, 5.52, -.62, -.5, 'nc_glow_cyan'),
                                        (-3.05, -2.95, 0, .18, 'nc_rail'), (-1.55, -1.45, 0, .18, 'nc_rail'),
                                        (1.45, 1.55, 0, .18, 'nc_rail'), (2.95, 3.05, 0, .18, 'nc_rail')):
                box_along(acc, a, b, na, nb, l0, l1, H + z0, H + z1, mat)
            if not closed and i in (0, segs - 1):           # end caps
                end = 0 if i == 0 else 1
                p, nn = (a, na) if end == 0 else (b, nb)
                ring = [(p[0] + nn[0] * l, p[1] + nn[1] * l, H + z) for l, z in DECK]
                tris = geometry.tessellate_polygon([[Vector((l, z, 0)) for l, z in DECK]])
                want = (-dx / L, -dy / L, 0) if end == 0 else (dx / L, dy / L, 0)
                for t in tris:
                    acc.face([ring[j] for j in t], 'nc_kerb', want=want)
        # piers on solid ground every ~30 m (none in a road)
        for i, p in enumerate(run):
            if i % 1 or not solid(p):
                continue
            j = min(i, len(run) - 2)
            dx, dy = run[j + 1][0] - run[j][0], run[j + 1][1] - run[j][1]; L = math.hypot(dx, dy) or 1
            t = (dx / L, dy / L); nrm = (-t[1], t[0])
            acc = T.at([p])
            q = lambda u, v: (p[0] + t[0] * u + nrm[0] * v, p[1] + t[1] * u + nrm[1] * v)
            ring = [q(-1.1, -1.5), q(1.1, -1.5), q(1.1, 1.5), q(-1.1, 1.5)]
            sides(acc, ring, -.2, H - 3.4, 'nc_kerb')
            cap_lo = ring; cap_hi = [q(-1.1, -4.2), q(1.1, -4.2), q(1.1, 4.2), q(-1.1, 4.2)]
            for k in range(4):
                a0, a1 = cap_lo[k], cap_lo[(k + 1) % 4]; b0, b1 = cap_hi[k], cap_hi[(k + 1) % 4]
                mid = ((a0[0] + a1[0]) / 2 - p[0], (a0[1] + a1[1]) / 2 - p[1], .3)
                acc.face([(a0[0], a0[1], H - 3.4), (a1[0], a1[1], H - 3.4), (b1[0], b1[1], H - 1.8), (b0[0], b0[1], H - 1.8)], 'nc_kerb', want=mid)
            stats['piers'] += 1

    def box_along(acc, a, b, na, nb, l0, l1, z0, z1, mat):
        A0 = (a[0] + na[0] * l0, a[1] + na[1] * l0); A1 = (a[0] + na[0] * l1, a[1] + na[1] * l1)
        B0 = (b[0] + nb[0] * l0, b[1] + nb[1] * l0); B1 = (b[0] + nb[0] * l1, b[1] + nb[1] * l1)
        acc.face([(*A0, z1), (*B0, z1), (*B1, z1), (*A1, z1)], mat, want=(0, 0, 1))
        acc.face([(*A0, z0), (*B0, z0), (*B0, z1), (*A0, z1)], mat, want=(-na[0], -na[1], 0))
        acc.face([(*A1, z0), (*B1, z0), (*B1, z1), (*A1, z1)], mat, want=(na[0], na[1], 0))

    rail_h = plan["rail"]["height"]; metro_h = plan["metro"]["height"]
    for name, line in plan["rail"]["lines"].items():
        viaduct(line, rail_h, False)
    viaduct(plan["metro"]["loop"], metro_h, True)
    # stations (rail) and hubs (metro): where the station prop goes, along the line
    def line_dir(line, p, closed):
        pts = [B(q) for q in line] + ([B(line[0])] if closed else [])
        best = None
        for i in range(len(pts) - 1):
            a, b = pts[i], pts[i + 1]
            dx, dy = b[0] - a[0], b[1] - a[1]; L2 = dx * dx + dy * dy or 1
            t = max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
            c = (a[0] + dx * t, a[1] + dy * t); d = math.dist(c, p)
            if best is None or d < best[0]:
                L = math.sqrt(L2); best = (d, c, (dx / L, dy / L))
        return best
    for sname, sp in plan["rail"]["stations"].items():
        b = min((line_dir(l, B(sp), False) for l in plan["rail"]["lines"].values()), key=lambda r: r[0])
        if pip(b[1], wall) and wall_dist(b[1]) > 80:
            stations.append(dict(name=sname, pos=b[1], dir=b[2], h=rail_h, line="rail"))
    for i, hp in enumerate(plan["metro"]["hubs"]):
        b = line_dir(plan["metro"]["loop"], B(hp), True)
        stations.append(dict(name=f"Metro {i + 1}", pos=b[1], dir=b[2], h=metro_h, line="metro"))

    # ---------------- the city wall: battered outer face, walkway, parapets, lit band; towers; gates; rail portals
    cx = sum(p[0] for p in wall) / len(wall); cy = sum(p[1] for p in wall) / len(wall)
    PROF = [(0, 0), (14, 0), (10, WALL_H), (9.2, WALL_H), (9.2, WALL_H - 1.4), (.8, WALL_H - 1.4), (.8, WALL_H - .4), (0, WALL_H - .4)]
    PMAT = ['-', 'nc_wall', 'nc_wall', 'nc_wall', 'nc_plaza', 'nc_wall', 'nc_wall', 'nc_wall']
    gates = []
    for gname, gp in plan["gates"].items():
        g = B(gp); best = None
        for i in range(len(wall)):
            a, b = wall[i], wall[(i + 1) % len(wall)]
            dx, dy = b[0] - a[0], b[1] - a[1]
            t = max(0, min(1, ((g[0] - a[0]) * dx + (g[1] - a[1]) * dy) / (dx * dx + dy * dy)))
            c = (a[0] + dx * t, a[1] + dy * t)
            if best is None or math.dist(c, g) < best[0]:
                best = (math.dist(c, g), i, t * math.hypot(dx, dy), c)
        gates.append(dict(name=gname, edge=best[1], s=best[2], pos=best[3]))
    for i in range(len(wall)):
        a, b = wall[i], wall[(i + 1) % len(wall)]
        dx, dy = b[0] - a[0], b[1] - a[1]; L = math.hypot(dx, dy); t = (dx / L, dy / L)
        out = (t[1], -t[0])                                  # right of a CCW edge = outside
        cuts = sorted([(g["s"] - 42, g["s"] + 42) for g in gates if g["edge"] == i])
        spans, s = [], 18.0
        for c0, c1 in cuts:
            spans.append((s, c0)); s = c1
        spans.append((s, L - 18.0))
        for s0, s1 in spans:
            n = max(1, int((s1 - s0) / 250) + 1)
            for k in range(n):
                u0 = s0 + (s1 - s0) * k / n; u1 = s0 + (s1 - s0) * (k + 1) / n
                p0 = (a[0] + t[0] * u0, a[1] + t[1] * u0); p1 = (a[0] + t[0] * u1, a[1] + t[1] * u1)
                acc = T.at([p0, p1])
                for j in range(1, len(PROF)):
                    (d0, z0), (d1, z1) = PROF[j], PROF[(j + 1) % len(PROF)]
                    o2 = ((z1 - z0), -(d1 - d0))
                    want = (out[0] * o2[0], out[1] * o2[0], o2[1])
                    q = lambda p, d, z: (p[0] + out[0] * d, p[1] + out[1] * d, z)
                    acc.face([q(p0, d0, z0), q(p1, d0, z0), q(p1, d1, z1), q(p0, d1, z1)], PMAT[j], want=want)
                # lit band along the inner face and on the outer parapet
                for d, z0, z1 in ((-.06, 29.4, 30.0), (9.9, WALL_H - .2, WALL_H)):
                    q = lambda p, z: (p[0] + out[0] * d, p[1] + out[1] * d, z)
                    acc.face([q(p0, z0), q(p1, z0), q(p1, z1), q(p0, z1)], 'nc_glow_cyan', want=(-out[0], -out[1], 0) if d < 0 else (out[0], out[1], .3))
    # towers at the corners
    for i, p in enumerate(wall):
        acc = T.at([p])
        c = (p[0] + (p[0] - cx) / math.dist(p, (cx, cy)) * 5, p[1] + (p[1] - cy) / math.dist(p, (cx, cy)) * 5)
        ring = [(c[0] + 19 * math.cos(math.pi / 8 + 2 * math.pi * k / 8), c[1] + 19 * math.sin(math.pi / 8 + 2 * math.pi * k / 8)) for k in range(8)]
        sides(acc, ring, -.2, 54, 'nc_wall', scale=12)
        top(acc, ring, 54, 'nc_plaza')
        band = [(c[0] + 19.3 * math.cos(math.pi / 8 + 2 * math.pi * k / 8), c[1] + 19.3 * math.sin(math.pi / 8 + 2 * math.pi * k / 8)) for k in range(8)]
        sides(acc, band, 48, 49.2, 'nc_glow_cyan')
        top(acc, band, 49.2, 'nc_glow_cyan')
        crown = [(c[0] + 8 * math.cos(math.pi / 8 + 2 * math.pi * k / 8), c[1] + 8 * math.sin(math.pi / 8 + 2 * math.pi * k / 8)) for k in range(8)]
        sides(acc, crown, 54, 62, 'nc_wall', scale=12)
        top(acc, crown, 62, 'nc_glow_violet')
    # gates: two pylons, a lintel, closed blast doors with a lit seam
    gate_out = []
    for g in gates:
        a, b = wall[g["edge"]], wall[(g["edge"] + 1) % len(wall)]
        dx, dy = b[0] - a[0], b[1] - a[1]; L = math.hypot(dx, dy); t = (dx / L, dy / L); out = (t[1], -t[0])
        p = g["pos"]; acc = T.at([p])
        q = lambda u, d: (p[0] + t[0] * u + out[0] * d, p[1] + t[1] * u + out[1] * d)
        def gbox(u0, u1, d0, d1, z0, z1, mat, topmat=None):
            ring = [q(u0, d0), q(u1, d0), q(u1, d1), q(u0, d1)]
            sides(acc, ring, z0, z1, mat, scale=12)
            top(acc, ring, z1, topmat or mat)
        for s in (-1, 1):
            gbox(s * 40, s * 56, -4, 18, -.2, 66, 'nc_wall', 'nc_plaza')
            gbox(s * 47.5 if s > 0 else -48.5, s * 48.5 if s > 0 else -47.5, -4.3, -4.0, 8, 62, 'nc_glow_cyan')
        gbox(-40, 40, -3, 17, 46, 56, 'nc_wall', 'nc_plaza')
        gbox(-40, 40, -3.3, -3.0, 50, 51, 'nc_glow_violet')
        gbox(-40, -.3, 6, 8, -.1, 46, 'nc_steel')
        gbox(.3, 40, 6, 8, -.1, 46, 'nc_steel')
        gbox(-.3, .3, 5.8, 8.2, -.1, 46, 'nc_glow_cyan')
        for z in (12, 24, 36):
            gbox(-39.5, 39.5, 5.8, 6.0, z, z + .25, 'nc_glow_cyan')
        gate_out.append(dict(name=g["name"], pos=p, out=out))
    # rail portals: a dark mouth with a lit frame on the inner wall face
    for pt in portals:
        p, d, H = pt["pos"], pt["dir"], pt["h"]
        acc = T.at([p]); nrm = (-d[1], d[0])
        q = lambda v, k=0.0: (p[0] + nrm[0] * v - d[0] * k, p[1] + nrm[1] * v - d[1] * k)
        face = lambda v0, v1, z0, z1, k, mat: acc.face([(*q(v0, k), z0), (*q(v1, k), z0), (*q(v1, k), z1), (*q(v0, k), z1)], mat, want=(-d[0], -d[1], 0))
        face(-6.5, 6.5, H - 1.8, H + 6.5, .1, 'nc_tunnel')
        face(-7.3, 7.3, H + 6.5, H + 7.2, .15, 'nc_glow_cyan')
        for s in (-1, 1):
            face(s * 6.5 if s > 0 else -7.3, s * 7.3 if s > 0 else -6.5, H - 1.8, H + 6.5, .15, 'nc_glow_cyan')

    # ---------------- land outside the wall: rolling ground, then mountains
    rnd = random.Random(11)
    per = sum(math.dist(wall[i], wall[(i + 1) % len(wall)]) for i in range(len(wall)))
    NU = 900
    Sw = cum(wall + [wall[0]])
    base_pts, norms = [], []
    for k in range(NU):
        d = per * k / NU
        p, tdir = at(wall + [wall[0]], Sw, d)
        base_pts.append(p)
    for k in range(NU):                                     # smoothed outward normals
        nx = ny = 0.0
        for j in range(-6, 7):
            a = base_pts[(k + j - 1) % NU]; b = base_pts[(k + j + 1) % NU]
            dx, dy = b[0] - a[0], b[1] - a[1]; l = math.hypot(dx, dy) or 1
            nx += dy / l; ny += -dx / l
        l = math.hypot(nx, ny) or 1
        norms.append((nx / l, ny / l))
    OFFS = [10, 16, 60, 140, 260, 420, 620, 860, 1150, 1500, 1900, 2350, 2850, 3400, 4000, 4700, 5500]

    def height(p, d):
        n = noise.fractal(Vector((p[0] / 1400, p[1] / 1400, .37)), .55, 2.1, 5)
        ridge = 1 - abs(noise.noise(Vector((p[0] / 2600, p[1] / 2600, 1.7))))
        if d < 100:
            return -.3 + d * .004
        k = min(1.0, (d - 100) / 2400) ** 1.6
        fall = 1.0 if d < 4200 else max(.35, 1 - (d - 4200) / 2600)
        return .3 + k * (520 + 520 * n + 380 * ridge) * fall + 6 * n

    rings = []
    for d in OFFS:
        rings.append([(base_pts[k][0] + norms[k][0] * d, base_pts[k][1] + norms[k][1] * d) for k in range(NU)])
    land = Acc()
    hz = [[height(p, d) for p in r] for r, d in zip(rings, OFFS)]
    for j in range(len(OFFS) - 1):
        mat = 'nc_lot' if OFFS[j] < 60 else 'nc_grass' if OFFS[j] < 420 else 'nc_rock'
        for k in range(NU):
            k2 = (k + 1) % NU
            pts = [(*rings[j][k], hz[j][k]), (*rings[j][k2], hz[j][k2]), (*rings[j + 1][k2], hz[j + 1][k2]), (*rings[j + 1][k], hz[j + 1][k])]
            land.face(pts, mat, [(p[0] / 40, p[1] / 40) for p in pts], want=(0, 0, 1))

    # ---------------- objects and manifest
    tiles = []
    for k, acc in sorted(T.acc.items()):
        c = T.centre(k)
        name = f"NCT_{k[0]}_{k[1]}"
        acc.object(name, M)
        tiles.append(dict(name=name, centre=[round(-c[1], 2), round(c[0], 2)]))
    land.object('NCL_land', M, smooth=True)
    os.makedirs(TILES_OUT, exist_ok=True)
    path = os.path.join(TILES_OUT, 'nexus_city_tiles.glb')
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', export_apply=True, export_yup=True, export_extras=True,
                              export_image_format='AUTO', export_animations=False, export_lights=False, export_cameras=False)
    log(f"tiles {len(tiles)} -> {path} ({os.path.getsize(path) / 1e6:.1f} MB)", dict(stats))
    P = lambda p: [round(-p[1], 2), round(p[0], 2)]           # Blender (x, y) -> plan (E, N)
    D = lambda d: [round(-d[1], 4), round(d[0], 4)]
    return dict(tiles=tiles, land="NCL_land",
                stations=[dict(name=s["name"], pos=P(s["pos"]), dir=D(s["dir"]), h=s["h"], line=s["line"]) for s in stations],
                portals=[dict(pos=P(p["pos"]), dir=D(p["dir"]), h=p["h"]) for p in portals],
                gates=[dict(name=g["name"], pos=P(g["pos"]), out=D(g["out"])) for g in gate_out])


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    do_kit = '--kit' in argv or not argv
    do_tiles = '--tiles' in argv or not argv
    plan = json.load(open(PLAN))
    city = json.load(open(CITY)) if os.path.exists(CITY) else {}
    if do_kit:
        bl.reset(); M = materials()
        city["designs"] = build_kit(M)
        city["kinds"] = {k: [f"NCB_{s}_{t}" for s, t in v] for k, v in KIND_DESIGNS.items()}
        city["props"] = dict(lamp="NCK_lamp", station="NCK_station", roof=["NCK_roof_ac", "NCK_roof_tank", "NCK_roof_mast"])
    if do_tiles:
        bl.reset(); M = materials()
        city.update(build_tiles(M, plan))
    city.update(version=1, tile=TILE, kerb=KERB, wall_height=WALL_H, lanes=LANES,
                facade={k: list(v) for k, v in FACADE.items()}, ground=GROUND | {"nc_rock": 40.0})
    json.dump(city, open(CITY, 'w'), indent=1)
    log("wrote", CITY)


main()
