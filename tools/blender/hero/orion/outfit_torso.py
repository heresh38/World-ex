"""The Orion outfit under and over the coat, to the owner's sheet: the armoured vest (black, its chest and belly in
rounded plates, an X of straps across the chest), the neck gaiter (black knit, gathered from the collar's base up to
the jaw) and the belt worn over the coat (wide black webbing, a square buckle with a blue light, boxy pouches round the
hips, a blue light at either hip).
"""
import math

import bmesh
import numpy as np
from mathutils import Vector, Matrix
from mathutils import noise as mnoise

REGIONS = ("head", "neck", "chest", "midriff", "pelvis", "upperarm", "forearm", "hand", "thigh", "shin", "foot")
R = {n: i for i, n in enumerate(REGIONS)}


def smoothstep(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


# ------------------------------------------------------------------------------------------------ the vest

def vest(base, T, log=print):
    """the armoured vest: the trunk from the collar's ring to under the belt, a centimetre over the suit; its plates
    (rounded cells over the chest and the belly, as the sheet draws them) carried out on it"""
    from outfit_legs import shell, cut_level
    from outfit_coat import neck_ring, cut_ring
    from coat import keep_largest
    bm = shell(base, ("neck", "chest", "midriff", "pelvis"), T["trouser_top"] - .03, 1.62)
    for v in bm.verts:
        v.co += v.normal * .008
    bm.normal_update()
    cut_level(bm, T["trouser_top"] - .02, keep_above=True)
    cy, rx, ry = T["collar_y"], T["collar_rx"] + .006, T["collar_ry"] + .008
    cut_ring(bm, neck_ring(cy, rx, ry), T["neck_base_z"] - .045, cy, rx, ry)
    # the armholes: what reaches out past the shoulder joint goes (the coat's sleeves cover the arm's root)
    S = Vector(T["shoulder_joint"])
    from coat import bisect, faces_where
    for sx in (1, -1):
        bisect(bm, faces_where(bm, lambda f, sx=sx: f.calc_center_median().x * sx > S.x - .03), (sx * (S.x - .01), 0, 0), (sx, 0, 0), clear=True)
    keep_largest(bm)
    # the plates: rounded cells over the front, raised in rows (the sheet's belly in six, the chest in two), a seam
    # between each, the middle a channel
    rows = [(1.31, 1.40, .095), (1.205, 1.285, .080), (1.135, 1.195, .072), (1.075, 1.130, .068)]
    for v in bm.verts:
        p, n = v.co, v.normal
        if p.y > T["collar_y"] - .02 or n.y > -.25:
            continue
        lift = 0.0
        for z0, z1, w in rows:
            if z0 <= p.z <= z1:
                inz = min(p.z - z0, z1 - p.z) / ((z1 - z0) / 2)
                inx = 1 - abs(abs(p.x) - w / 2 - .006) / (w / 2 + .006)
                if abs(p.x) > .006:
                    lift = max(lift, .0055 * smoothstep(0, .35, inz) * smoothstep(0, .25, inx))
        v.co += n * lift
    bm.normal_update()
    log(f"vest: {len(bm.faces)} faces")
    return bm


# ------------------------------------------------------------------------------------------------ the gaiter

def gaiter(T, log=print):
    """the neck gaiter: a knit tube over the suit's collar from the collar's base to the jaw, gathered in soft rings"""
    cy, rx, ry = T["collar_y"], T["collar_rx"] + .010, T["collar_ry"] + .012
    z0, z1 = T["neck_base_z"] - .012, T["chin_z"] + .012
    bm = bmesh.new()
    n_u, n_v = 64, 26
    seed = Vector((3.3, .4, 1.9))
    rings = []
    for j in range(n_v + 1):
        s = j / n_v
        z = z0 + (z1 - z0) * s
        ring = []
        for i in range(n_u):
            a = 2 * math.pi * i / n_u
            out = Vector((math.sin(a), -math.cos(a), 0))
            front = max(0.0, math.cos(a))
            # gathered: the knit pushed down into rings, deeper at the front under the chin; it flares a little at its
            # foot over the collar's base, and is drawn up under the jaw at the front
            gather = .0045 * (math.sin(2 * math.pi * s * 4.5 + 1.5 * mnoise.noise(Vector((a * 2, s * 3, .2)) + seed)) + .6) * (.5 + .5 * front)
            flare = .010 * (1 - s) ** 3
            r = 1.0 + gather / max(rx, ry) + flare / max(rx, ry)
            zz = z + .010 * front * s * s - .006 * (1 - front) * s
            ring.append(bm.verts.new(Vector((math.sin(a) * rx * r, cy - math.cos(a) * ry * r, zz))))
        rings.append(ring)
    for j in range(n_v):
        for i in range(n_u):
            a0, a1 = rings[j][i], rings[j][(i + 1) % n_u]
            b0, b1 = rings[j + 1][i], rings[j + 1][(i + 1) % n_u]
            bm.faces.new((a0, a1, b1, b0))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    log(f"gaiter: {len(bm.faces)} faces")
    return bm


# ------------------------------------------------------------------------------------------------ the belt

def box(bm, centre, size, frame, bevel=.004):
    """a bevelled box in a frame (right, up, out)"""
    r_, u_, o_ = frame
    sx, sy, sz = size
    res = bmesh.ops.create_cube(bm, size=1.0)
    vs = res["verts"]
    M = Matrix(((r_.x * sx, u_.x * sy, o_.x * sz), (r_.y * sx, u_.y * sy, o_.y * sz), (r_.z * sx, u_.z * sy, o_.z * sz)))
    for v in vs:
        v.co = centre + M @ v.co
    bmesh.ops.bevel(bm, geom=list({e for v in vs for e in v.link_edges}), offset=bevel, segments=2, affect='EDGES', profile=.5)
    return vs


def belt(coat_obj, T, log=print):
    """the belt over the coat: a band of webbing following the coat's surface at the waist, the buckle, the pouches,
    the lights at the hips"""
    from mathutils.bvhtree import BVHTree
    import bpy
    dg = bpy.context.evaluated_depsgraph_get()
    e = coat_obj.evaluated_get(dg)
    me = e.to_mesh()
    cbm = bmesh.new()
    cbm.from_mesh(me)
    cbm.transform(coat_obj.matrix_world)
    e.to_mesh_clear()
    bvh = BVHTree.FromBMesh(cbm)
    cbm.free()
    zc, wb = T["belt_z"], .052
    yc = T["belt_yc"]
    bm = bmesh.new()
    n = 96
    rings = []
    for k in range(3):
        z = zc - wb / 2 + wb * k / 2
        ring = []
        for i in range(n):
            a = 2 * math.pi * i / n
            d = Vector((math.sin(a), -math.cos(a), 0))
            c = Vector((0, yc, z))
            hit = bvh.ray_cast(c + d * .6, -d, .7)[0]
            r = ((hit - c).length if hit is not None else .2) + .005
            ring.append(bm.verts.new(c + d * r))
        rings.append(ring)
    for k in range(2):
        for i in range(n):
            bm.faces.new((rings[k][i], rings[k][(i + 1) % n], rings[k + 1][(i + 1) % n], rings[k + 1][i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    band = bm
    # the buckle at the front, the pouches round the hips (the sheet: two each side in front, two behind)
    parts = bmesh.new()
    front_r = rings[1][0].co.length if False else (rings[1][0].co - Vector((0, yc, zc))).length
    up = Vector((0, 0, 1))

    def frame_at(a):
        d = Vector((math.sin(a), -math.cos(a), 0))
        return Vector((math.cos(a), math.sin(a), 0)), up, d

    def at(a, out=0.0):
        i = int(round(a / (2 * math.pi) * n)) % n
        d = Vector((math.sin(a), -math.cos(a), 0))
        return rings[1][i].co + d * out

    buckle = at(0.0, .008)
    box(parts, buckle, (.060, .050, .012), frame_at(0.0), bevel=.003)
    for a_deg, w, h, dpt in ((38, .062, .090, .040), (62, .055, .085, .038), (118, .060, .088, .042), (148, .055, .080, .036)):
        for sx in (1, -1):
            a = math.radians(a_deg) * sx
            c = at(a, dpt / 2 + .004) - Vector((0, 0, .012))
            box(parts, c, (w, h, dpt), frame_at(a), bevel=.006)
    lights = bmesh.new()
    for sx in (1, -1):
        a = math.radians(90) * sx
        box(lights, at(a, .010), (.022, .034, .010), frame_at(a), bevel=.004)
    box(lights, buckle + Vector((0, -.007, 0)), (.034, .026, .004), frame_at(0.0), bevel=.002)
    log("belt: band, buckle, 8 pouches, 3 lights")
    return band, parts, lights


def build(base, T, coat_obj, log=print):
    from outfit_mat import to_object, face_out
    vb = vest(base, T, log=log)
    face_out(vb, base)
    out = [to_object(vb, "C_vest__orion", "orion_vest"),
           to_object(gaiter(T, log=log), "C_top__orion", "orion_black")]
    if coat_obj is not None:
        band, parts, lights = belt(coat_obj, T, log=log)
        out += [to_object(band, "belt_band", "orion_strap"), to_object(parts, "belt_pouches", "orion_strap"),
                to_object(lights, "belt_lights", "orion_glow")]
    for o in out:
        if o.name.startswith("C_vest") or o.name.startswith("belt_band"):
            s = o.modifiers.new("thick", 'SOLIDIFY')
            s.thickness, s.offset, s.use_rim = .003, -1.0, True
    return out
