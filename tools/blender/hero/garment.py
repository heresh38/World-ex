"""Garment construction for the hero outfits (wardrobe.py): the operations a pattern cutter and a gear maker would do,
as mesh operations on shells grown from the body.

  cut()          a clean straight edge: everything beyond a plane goes (hems, cuffs, the open front), so edges follow
                 true lines instead of the body's quad grid
  seam()         a sewn seam: an edge loop along a plane pressed in a little (the groove), returned as an ordered
                 chain so stitching can follow it
  finish()       real cloth thickness with a rounded edge (solidify + a bevel on the rim)
  trim_strip()   a ribbon laid just over a surface along a chain of points, UV'd along its length: stitching,
                 zip tape, piping, edge binding (masked trim textures)
  strap()        webbing routed over the body between points, with thickness
  buckle(), d_ring(), snap(), rivet(), zip_pull()   hardware
Every part comes back as a bmesh or an object with its material; wardrobe.py joins them per piece.
"""
import math
import bmesh
import bpy
import numpy as np
from mathutils import Vector, Matrix


# ------------------------------------------------------------------------------------------------ cutting

def cut(bm, co, no, only=None):
    """removes everything on the +no side of the plane through co (only: a predicate on face centres, to cut just
    part of the garment, e.g. the front)"""
    if only:
        faces = [f for f in bm.faces if only(f.calc_center_median())]
        geom = list({v for f in faces for v in f.verts}) + list({e for f in faces for e in f.edges}) + faces
    else:
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    bmesh.ops.bisect_plane(bm, geom=geom, plane_co=Vector(co), plane_no=Vector(no).normalized(), clear_outer=True)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')


def remove(bm, test):
    """deletes the faces whose centre passes test (after a cut has made their border clean)"""
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if test(f.calc_center_median())], context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')


def seam(bm, co, no, depth=.0010, only=None):
    """an edge loop along the plane, pressed in by depth: the seam's groove. Returns its ordered vertex chains
    (positions, normals) for stitching."""
    faces = [f for f in bm.faces if (only(f.calc_center_median()) if only else True)]
    geom = list({v for f in faces for v in f.verts}) + list({e for f in faces for e in f.edges}) + faces
    r = bmesh.ops.bisect_plane(bm, geom=geom, plane_co=Vector(co), plane_no=Vector(no).normalized())
    cut_edges = [g for g in r["geom_cut"] if isinstance(g, bmesh.types.BMEdge)]
    bm.normal_update()
    verts = {v for e in cut_edges for v in e.verts}
    for v in verts:
        v.co -= v.normal * depth
    return chains(cut_edges)


def chains(edges):
    """orders a set of edges into vertex chains -> [[(co, normal), ...], ...]"""
    adj = {}
    for e in edges:
        a, b = e.verts
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    seen, out = set(), []
    starts = [v for v, n in adj.items() if len(n) == 1] + list(adj)
    for s in starts:
        if s in seen:
            continue
        chain, cur, prev = [s], s, None
        seen.add(s)
        while True:
            nxt = [w for w in adj[cur] if w is not prev and w not in seen]
            if not nxt:
                break
            prev, cur = cur, nxt[0]
            seen.add(cur)
            chain.append(cur)
        if len(chain) > 2:
            out.append([(v.co.copy(), v.normal.copy()) for v in chain])
    return out


def boundary_chains(bm, test=None):
    """the open edges (hems, the front opening) as ordered chains; test(edge midpoint) filters them"""
    edges = [e for e in bm.edges if e.is_boundary and (test((e.verts[0].co + e.verts[1].co) / 2) if test else True)]
    bm.normal_update()
    return chains(edges)


def finish(o, thickness, bevel=None):
    """cloth thickness with a rounded edge: solidify (rim) then bevel the rim's sharp edges"""
    m = o.modifiers.new("solid", 'SOLIDIFY')
    m.thickness = thickness
    m.offset = -1.0
    m.use_rim = True
    m.use_even_offset = False
    m.thickness_clamp = .5
    b = o.modifiers.new("edge", 'BEVEL')
    b.width = bevel if bevel is not None else thickness * .45
    b.segments = 2
    b.limit_method = 'ANGLE'
    b.angle_limit = math.radians(50)
    b.harden_normals = False
    bpy.context.view_layer.objects.active = o
    for md in (m, b):
        bpy.ops.object.modifier_apply(modifier=md.name)


# ------------------------------------------------------------------------------------------------ strips

def resample(points, step):
    """even spacing along a chain of (co, normal)"""
    if len(points) < 2:
        return points
    out = [points[0]]
    acc = 0.0
    for (a, na), (b, nb) in zip(points, points[1:]):
        seg = (b - a).length
        if seg < 1e-9:
            continue
        t = step - acc
        while t <= seg:
            k = t / seg
            out.append((a.lerp(b, k), na.lerp(nb, k).normalized()))
            t += step
        acc = seg - (t - step)
    if (out[-1][0] - points[-1][0]).length > step * .3:
        out.append(points[-1])
    return out


def smooth_chain(points, it=2):
    P = [p for p, n in points]
    N = [n for p, n in points]
    for _ in range(it):
        P = [P[0]] + [(P[i - 1] + P[i] * 2 + P[i + 1]) / 4 for i in range(1, len(P) - 1)] + [P[-1]]
    return list(zip(P, N))


def trim_strip(points, width, mat, offset=0.0, lift=.0005, tile=.03, step=.004, name="trim"):
    """a ribbon over the surface along points [(co, normal)]: across = normal x tangent; offset shifts it sideways
    (stitching beside a seam); UV u across (0..1), v along (metres / tile)"""
    pts = smooth_chain(resample(points, step), 1)
    if len(pts) < 2:
        return None
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    rows, vs = [], 0.0
    for i, (p, n) in enumerate(pts):
        t = (pts[min(i + 1, len(pts) - 1)][0] - pts[max(i - 1, 0)][0])
        if t.length < 1e-9:
            t = Vector((0, 0, 1))
        t.normalize()
        side = n.cross(t).normalized()
        c = p + n * lift + side * offset
        if i:
            vs += (p - pts[i - 1][0]).length / tile
        rows.append((bm.verts.new(c - side * width / 2), bm.verts.new(c + side * width / 2), vs))
    for (a0, b0, v0), (a1, b1, v1) in zip(rows, rows[1:]):
        f = bm.faces.new((a0, b0, b1, a1))
        for loop, (u, v) in zip(f.loops, ((0, v0), (1, v0), (1, v1), (0, v1))):
            loop[uv].uv = (u, v)
    return obj(bm, name, mat)


def strap(info, path, width, thick, mat, lift=.006, step=.008, name="strap"):
    """webbing routed over the body through the world points `path` (each projected to the skin and lifted)"""
    raw = []
    for a, b in zip(path, path[1:]):
        n = max(2, int((Vector(b) - Vector(a)).length / step))
        for k in range(n):
            p = Vector(a).lerp(Vector(b), k / n)
            loc, nrm, _, _ = info.bvh.find_nearest(p)
            raw.append((loc + nrm * lift, nrm))
    loc, nrm, _, _ = info.bvh.find_nearest(Vector(path[-1]))
    raw.append((loc + nrm * lift, nrm))
    pts = smooth_chain(raw, 3)
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    rings, vs = [], 0.0
    for i, (p, n) in enumerate(pts):
        t = (pts[min(i + 1, len(pts) - 1)][0] - pts[max(i - 1, 0)][0]).normalized()
        side = n.cross(t).normalized()
        if i:
            vs += (p - pts[i - 1][0]).length / .05
        ring = [bm.verts.new(p + side * sx * width / 2 + n * nz * thick / 2) for sx, nz in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        rings.append((ring, vs))
    for (r0, v0), (r1, v1) in zip(rings, rings[1:]):
        for k in range(4):
            f = bm.faces.new((r0[k], r0[(k + 1) % 4], r1[(k + 1) % 4], r1[k]))
            for loop, (u, v) in zip(f.loops, ((k / 4, v0), ((k + 1) / 4, v0), ((k + 1) / 4, v1), (k / 4, v1))):
                loop[uv].uv = (u, v)
    for r, _ in (rings[0], rings[-1]):
        bm.faces.new(r if r is rings[0][0] else r[::-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return obj(bm, name, mat), pts


# ------------------------------------------------------------------------------------------------ hardware

def frame_at(p, n, up=Vector((0, 0, 1))):
    """rows: side, up, normal"""
    n = Vector(n).normalized()
    side = Vector(up).cross(n)
    if side.length < 1e-6:
        side = Vector((1, 0, 0))
    side.normalize()
    u = n.cross(side).normalized()
    return Matrix((side, u, n)).transposed()


def rounded_box(size, R, at, mat, bevel=.003, segs=3, name="part"):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
    bmesh.ops.bevel(bm, geom=list(bm.edges), offset=min(bevel, min(size) * .45), segments=segs, affect='EDGES', profile=.5)
    for v in bm.verts:
        v.co = R @ v.co + Vector(at)
    return obj(bm, name, mat)


def buckle(p, n, width, mat, up=Vector((0, 0, 1)), name="buckle"):
    """a side-release / ladder buckle: a rounded frame with a centre bar, lying on the strap"""
    R = frame_at(p, n, up)
    parts = []
    w, h, t = width + .008, width * .9, .004
    for (cx, cy, sx, sy) in ((0, h / 2, w, .005), (0, -h / 2, w, .005), (w / 2, 0, .005, h), (-w / 2, 0, .005, h), (0, 0, w, .004)):
        parts.append(rounded_box((sx, sy, t), R, Vector(p) + R @ Vector((cx, cy, t)), mat, bevel=.0015, segs=2, name=name))
    return parts


def d_ring(p, n, size, mat, up=Vector((0, 0, 1)), name="dring"):
    R = frame_at(p, n, up)
    bm = bmesh.new()
    seg, rr, r = 16, size / 2, .0018
    rings = []
    for i in range(seg + 1):
        a = math.pi * i / seg
        c = Vector((math.cos(a) * rr, math.sin(a) * rr + .002, .004))
        tng = Vector((-math.sin(a), math.cos(a), 0))
        nn = Vector((math.cos(a), math.sin(a), 0))
        ring = []
        for k in range(6):
            b = 2 * math.pi * k / 6
            q = c + nn * math.cos(b) * r + Vector((0, 0, 1)) * math.sin(b) * r
            ring.append(bm.verts.new(R @ q + Vector(p)))
        rings.append(ring)
    for r0, r1 in zip(rings, rings[1:]):
        for k in range(6):
            bm.faces.new((r0[k], r0[(k + 1) % 6], r1[(k + 1) % 6], r1[k]))
    o = obj(bm, name, mat)
    bar = rounded_box((size + .004, .004, .004), R, Vector(p) + R @ Vector((0, .002, .004)), mat, bevel=.0015, segs=2)
    return [o, bar]


def snap(p, n, radius, mat, name="snap"):
    """a press stud: a domed disc"""
    R = frame_at(p, n)
    bm = bmesh.new()
    seg = 12
    rim = [bm.verts.new(R @ Vector((math.cos(2 * math.pi * k / seg) * radius, math.sin(2 * math.pi * k / seg) * radius, 0)) + Vector(p)) for k in range(seg)]
    mid = [bm.verts.new(R @ Vector((math.cos(2 * math.pi * k / seg) * radius * .7, math.sin(2 * math.pi * k / seg) * radius * .7, radius * .45)) + Vector(p)) for k in range(seg)]
    top = bm.verts.new(R @ Vector((0, 0, radius * .6)) + Vector(p))
    for k in range(seg):
        bm.faces.new((rim[k], rim[(k + 1) % seg], mid[(k + 1) % seg], mid[k]))
        bm.faces.new((mid[k], mid[(k + 1) % seg], top))
    return obj(bm, name, mat)


def rivet(p, n, mat):
    return snap(p, n, .0035, mat, name="rivet")


def zip_pull(p, n, mat, down=Vector((0, 0, -1))):
    R = frame_at(p, n, -Vector(down))
    a = rounded_box((.010, .012, .004), R, Vector(p) + R @ Vector((0, 0, .003)), mat, bevel=.0015, segs=2, name="zipslider")
    b = rounded_box((.007, .022, .0025), R, Vector(p) + R @ Vector((0, -.016, .005)), mat, bevel=.001, segs=2, name="zippull")
    return [a, b]


# ------------------------------------------------------------------------------------------------ objects

def obj(bm, name, mat):
    from wardrobe import material
    me = bpy.data.meshes.new(name)
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    me.materials.append(material(mat))
    for p in me.polygons:
        p.use_smooth = True
        p.material_index = 0
    return o
