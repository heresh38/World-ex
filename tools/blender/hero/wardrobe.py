"""The Orion outfit (the owner's "Project Orion" concept sheet) for the hero bodies, one interchangeable piece per
wardrobe slot (Unreal: USOWardrobeData; slots head / top / vest / outer / hands / legs / feet, plus hair):

  top     male: long-sleeved black tactical shirt with a neck gaiter; female: black high-neck crop top (bare midriff)
  vest    the rig: utility belt with pouches and buckle; male: a cross strap, female: a right-thigh holster
  outer   male: long dark coat, open front, high collar with a hood down, blue lining; female: cropped white jacket,
          high collar, open front
  hands   fingerless gloves with a glowing wrist unit; orion_armoured: full gloves with knuckle plates
  legs    male: black cargo trousers with knee plates; female: fitted trousers with thigh / knee / shin plates
  feet    combat boots (hers with armour plates and a low heel)
  hair    male: short swept dark hair; female: high ponytail

Every piece is grown from the body's own surface (the faces of the regions it covers, pushed out to its thickness),
so it fits exactly and keeps clean quads; then thickness, hems, collars and skirts, and modelled parts (belts,
pouches, plates, straps, soles). Skin weights come from the body (nearest surface), so a piece follows every clip.
Objects are C_<slot>__<item>; their metadata (label, regions hidden) goes into the armature's `worldex`.
"""
import math
import os
import json
import bmesh
import bpy
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from mathutils import noise as mnoise
import skeleton

REGIONS = ("head", "neck", "chest", "midriff", "pelvis", "upperarm", "forearm", "hand", "thigh", "shin", "foot")

# colours (linear): the concept's palette: near-black cloth, charcoal coat, steel plates, white jacket, cyan glow
PALETTE = {
    "orion_black": ((.012, .012, .014), .85, 0.0),
    "orion_cloth": ((.020, .021, .024), .80, 0.0),
    "orion_coat": ((.055, .057, .062), .75, 0.0),
    "orion_lining": ((.010, .060, .220), .60, 0.0),
    "orion_stitch": ((.115, .115, .120), .70, 0.0),        # tonal thread, a shade lighter than the coat
    "orion_zip": ((.016, .016, .018), .75, 0.0),           # woven zip tape
    "orion_leather": ((.022, .020, .019), .55, 0.0),       # the boots' oiled leather
    "orion_midsole": ((.060, .060, .062), .80, 0.0),       # the sole's lighter rubber band
    "orion_lace": ((.012, .012, .013), .70, 0.0),          # braided boot lace
    "orion_plate": ((.160, .165, .175), .40, .6),
    "orion_steel": ((.050, .052, .056), .35, .8),
    "orion_strap": ((.015, .014, .013), .65, 0.0),
    "orion_white": ((.62, .63, .65), .65, 0.0),
    "orion_grey": ((.22, .23, .25), .60, 0.0),
    "orion_sole": ((.008, .008, .008), .90, 0.0),
    "orion_glow": ((.10, .55, 1.0), .30, 0.0),
    "hair": ((.035, .024, .018), .55, 0.0),
}


def material(name):
    m = bpy.data.materials.get(name)
    if m:
        return m
    col, rough, metal = PALETTE[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (*col, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if name.endswith("glow"):
        b.inputs["Emission Color"].default_value = (*col, 1)
        b.inputs["Emission Strength"].default_value = 4.0
    m.diffuse_color = (*col, 1)
    return m


# ------------------------------------------------------------------------------------------------ body access

class BodyInfo:
    def __init__(self, body, T):
        self.o, self.T = body, T
        self.m = T["sex"] == "male"
        me = body.data
        self.bm = bmesh.new()
        self.bm.from_mesh(me)
        self.bm.verts.ensure_lookup_table()
        self.bm.faces.ensure_lookup_table()
        self.bm.normal_update()
        self.face_region = [REGIONS[f.material_index] for f in self.bm.faces]
        self.bvh = BVHTree.FromBMesh(self.bm)
        self.A, self.L, self.F = skeleton.arm(T), skeleton.leg(T), skeleton.foot(T)
        self.H = skeleton.hand(T)

    def free(self):
        self.bm.free()


def from_faces(info, name, keep, offset, mat, fold=None, hem=.0018, wrinkle=.0010, drape=0):
    """a shell of the body faces where keep(face centre, region) is true, every vertex pushed out along its normal by
    offset(co, normal, region) + fold(co, region) (the garment's folds), plus fine wrinkle noise and a rolled hem
    (the rings next to every open edge pushed out a little more)"""
    bm = info.bm.copy()
    bm.faces.ensure_lookup_table()
    regs = info.face_region
    drop = [f for f, r in zip(bm.faces, regs) if not keep(f.calc_center_median(), r)]
    bmesh.ops.delete(bm, geom=drop, context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    bm.normal_update()
    # rings from the open edges (0 = on the hem)
    ring = {v: 0 for v in bm.verts if v.is_boundary}
    front = list(ring)
    for k in range(1, 4):
        nxt = []
        for v in front:
            for e in v.link_edges:
                w = e.other_vert(v)
                if w not in ring:
                    ring[w] = k
                    nxt.append(w)
        front = nxt
    seed = Vector((hash(name) % 97 * .37, 1.3, 2.1))
    region = {}
    base = []
    for v in bm.verts:
        loc, nrm, idx, _ = info.bvh.find_nearest(v.co)
        r = regs[idx] if idx is not None else "chest"
        region[v] = r
        base.append(v.co + v.normal * max(offset(v.co, v.normal, r), .0012))
    for v, c in zip(bm.verts, base):
        v.co = c
    if drape:                                              # the garment's own shape first (spanning the hollows) ...
        drape_out(bm, info, drape, min_off=.003)
    moved = []
    for v in bm.verts:                                     # ... then its folds, wrinkles and rolled hems on top
        r = region[v]
        d = 0.0
        if fold:
            d += fold(v.co, r)
        if wrinkle:
            d += wrinkle * mnoise.noise(v.co * 38.0 + seed) + wrinkle * .5 * mnoise.noise(v.co * 95.0 + seed)
        if hem and v in ring:
            d += hem * (1.0 - ring[v] / 3.5)
        moved.append(v.co + v.normal * d)
    for v, c in zip(bm.verts, moved):
        v.co = c
    bm.normal_update()
    o = to_object(bm, name, mat)
    return o


def drape_out(bm, info, iterations, min_off=.003):
    """cloth spans hollows instead of following every muscle: Laplacian smoothing that only lets a vertex move if it
    stays outside the body (at least min_off from the skin); hems stay where they are"""
    bm.verts.index_update()
    n = len(bm.verts)
    P = np.array([v.co for v in bm.verts])
    nb = [[e.other_vert(v).index for e in v.link_edges] for v in bm.verts]
    fixed = np.array([v.is_boundary for v in bm.verts])
    for it in range(iterations):
        M = np.array([P[ix].mean(0) if ix else P[i] for i, ix in enumerate(nb)])
        C = P + (M - P) * .5
        for i in range(n):
            if fixed[i]:
                continue
            loc, nrm, idx, dist = info.bvh.find_nearest(Vector(C[i]))
            if loc is None:
                continue
            out = Vector(C[i]) - loc
            if out.dot(nrm) < min_off:                     # too close or inside: back out along the body normal
                C[i] = np.array(loc + nrm * min_off)
        P = np.where(fixed[:, None], P, C)
    for v, p in zip(bm.verts, P):
        v.co = Vector(p)
    bm.normal_update()


class Folds:
    """cloth folds in each limb's own frame: compression rings inside the elbows and behind the knees, stacking at
    the cuffs, a bunch above the belt, the groin's diagonals, and the coat skirt's drape"""
    def __init__(self, info):
        self.i = info
        A, L = info.A, info.L
        self.S, self.E, self.W = A["S"], A["E"], A["W"]
        self.ua, self.fa = (self.E - self.S).normalized(), (self.W - self.E).normalized()
        self.front = A["thumb"].normalized()                        # the arm's anterior side (inside of the elbow)
        self.H, self.K, self.A = L["H"], L["K"], L["A"]

    @staticmethod
    def q(co):
        return Vector((abs(co.x), co.y, co.z))

    def rings(self, d, pitch, reach, amp):
        return amp * math.sin(2 * math.pi * d / pitch) * math.exp(-(d / reach) ** 2)

    def sleeve(self, co, r, amp=.0035, cuff=None):
        if r not in ("upperarm", "forearm", "hand"):
            return 0.0
        q = self.q(co)
        d = (q - self.E).dot(self.fa if r != "upperarm" else self.ua)
        # radial direction round the elbow: the inside (anterior) gathers the folds
        axis_p = self.E + self.ua * min(0.0, d) if r == "upperarm" else self.E + self.fa * max(0.0, d)
        rad = (q - axis_p)
        inside = max(0.0, rad.normalized().dot(self.front)) if rad.length > 1e-6 else 0.0
        f = self.rings(d, .024, .07, amp) * (.35 + .65 * inside)
        if cuff is not None:
            dc = (q - self.W).dot(self.fa) - cuff
            f += amp * .8 * math.sin(2 * math.pi * dc / .018) * math.exp(-(dc / .045) ** 2)
        return f

    def trouser(self, co, r, amp=.004, stack_z=None):
        if r not in ("thigh", "shin", "pelvis"):
            return 0.0
        q = self.q(co)
        f = 0.0
        d = q.z - self.K.z
        behind = max(0.0, (q.y - self.K.y) / .06)
        f += self.rings(d, .028, .07, amp) * (.3 + .7 * min(1.0, behind))
        if stack_z is not None:
            ds = q.z - stack_z
            f += amp * math.sin(2 * math.pi * ds / .022) * math.exp(-(ds / .06) ** 2)
        if r in ("pelvis", "thigh") and q.z > self.H.z - .12 and q.x < self.H.x + .02:
            g = (q.x * .9 + (q.z - self.H.z))                     # groin diagonals
            f += amp * .6 * math.sin(2 * math.pi * g / .03) * math.exp(-((q.z - self.H.z + .06) / .07) ** 2)
        return f

    def waist(self, co, z0, amp=.003):
        dz = co.z - z0
        return amp * math.sin(2 * math.pi * dz / .02 + 2.0 * mnoise.noise(Vector((co.x * 12, co.y * 12, 0)))) *             math.exp(-(max(0.0, dz) / .05) ** 2) * (1.0 if dz > -.005 else 0.0)


def to_object(bm, name, mat):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    me.materials.append(material(mat))
    for p in me.polygons:
        p.use_smooth = True
        p.material_index = 0                       # (shells copied from the body keep its region indices)
    return o


def solidify(o, t, offset=-1.0, rim=True):
    m = o.modifiers.new("solid", 'SOLIDIFY')
    m.thickness = t
    m.offset = offset
    m.use_rim = rim
    m.use_even_offset = False             # (even thickness overshoots into spikes on thin slivers at the cuffs)
    m.thickness_clamp = .5
    apply_mods(o)


def apply_mods(o):
    bpy.context.view_layer.objects.active = o
    for m in list(o.modifiers):
        if m.type != 'ARMATURE':
            bpy.ops.object.modifier_apply(modifier=m.name)


def boundary_loops(o):
    bm = bmesh.new()
    bm.from_mesh(o.data)
    edges = [e for e in bm.edges if e.is_boundary]
    seen, loops = set(), []
    for e in edges:
        if e.index in seen:
            continue
        loop, cur, prev = [e.verts[0].index], e.verts[1], e
        seen.add(e.index)
        while cur.index != loop[0] and len(loop) < 20000:
            loop.append(cur.index)
            nxt = next((x for x in cur.link_edges if x.is_boundary and x is not prev and x.index not in seen), None)
            if nxt is None:
                break
            seen.add(nxt.index)
            prev, cur = nxt, nxt.other_vert(cur)
        loops.append(loop)
    bm.free()
    return loops


def extrude_loop(o, pick, move, rings=1, mat=None):
    """extrudes the boundary loop chosen by pick(centre) `rings` times; move(co, k) gives each new ring's positions"""
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bm.verts.ensure_lookup_table()
    loops = boundary_loops(o)
    best = max(loops, key=lambda L: pick(sum((bm.verts[i].co for i in L), Vector()) / len(L)))
    edges = [e for e in bm.edges if e.is_boundary and e.verts[0].index in set(best) and e.verts[1].index in set(best)]
    for k in range(rings):
        r = bmesh.ops.extrude_edge_only(bm, edges=edges)
        nv = [g for g in r["geom"] if isinstance(g, bmesh.types.BMVert)]
        for v in nv:
            v.co = move(v.co, k)
        edges = [g for g in r["geom"] if isinstance(g, bmesh.types.BMEdge) and g.is_boundary]
    bm.to_mesh(o.data)
    bm.free()
    if mat:
        pass
    for p in o.data.polygons:
        p.use_smooth = True


def join(objs, name):
    objs = [o for o in objs if o]
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    if len(objs) > 1:
        bpy.ops.object.join()
    o = bpy.context.view_layer.objects.active
    o.name = o.data.name = name
    return o


# ------------------------------------------------------------------------------------------------ modelled parts

def box(name, size, at, mat, rot=None, bevel=.004):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
    if bevel:
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bevel, segments=2, affect='EDGES', profile=.5)
    R = rot or Matrix.Identity(3)
    for v in bm.verts:
        v.co = R @ v.co + Vector(at)
    return to_object(bm, name, mat)


def ring_band(info, name, z0, z1, push, mat, keep=None, segments=None):
    """a band of the body between heights z0 and z1 (optionally limited by keep), pushed out and given thickness"""
    def k(c, r):
        return z0 <= c.z <= z1 and (keep(c, r) if keep else True)
    o = from_faces(info, name, k, lambda co, n, r: push, mat)
    return o


def plate_on(info, name, centre, normal_hint, size, mat, lift=.006):
    """an armour plate laid on the body: a box oriented to the surface normal nearest centre"""
    loc, nrm, idx, _ = info.bvh.find_nearest(Vector(centre))
    n = nrm.normalized()
    up = Vector((0, 0, 1))
    side = up.cross(n).normalized()
    up2 = n.cross(side).normalized()
    R = Matrix((side, up2, n)).transposed()
    return box(name, size, loc + n * (lift + size[2] / 2), mat, R, bevel=.003)


# ------------------------------------------------------------------------------------------------ the pieces

def top(info):
    T, m = info.T, info.m
    if True:                                                # the base layer, cut and sewn (shirt.py)
        import shirt
        return join(shirt.build(info), "C_top__orion")
    ub, hz = T["underbust"]["z"], T["hips"]["z"]
    if m:
        def keep(c, r):
            if r in ("chest", "midriff", "upperarm", "forearm"):
                return True
            if r == "pelvis":
                return c.z > hz + .02
            if r == "neck":
                return c.z < T["chin_z"] - .015          # the gaiter: up the neck
            return False
        F_ = Folds(info)
        belt_top = hz + .085
        o = from_faces(info, "top", keep, lambda co, n, r: .0045 if r != "neck" else .007, "orion_black", drape=4,
                       fold=lambda co, r: F_.sleeve(co, r, .005, cuff=-.03) + (F_.waist(co, belt_top) if r in ("midriff", "pelvis") else 0.0))
    else:
        def keep(c, r):
            if r == "chest":
                return True
            if r == "midriff":
                return c.z > ub - .035
            if r == "neck":
                return c.z < T["chin_z"] - .03           # the high neck
            if r in ("upperarm",):
                return False
            return False
        o = from_faces(info, "top", keep, lambda co, n, r: .0035, "orion_black", wrinkle=.0007)
    solidify(o, .003)
    parts = [o]
    if m:
        # chest panels of the tactical shirt (the concept's armoured weave)
        C = T["chest"]
        for sx in (1, -1):
            parts.append(plate_on(info, "panel", (sx * .07, -.15, C["z"] + .02), None, (.085, .07, .006), "orion_cloth", lift=.006))
    return join(parts, "C_top__orion")


def legs(info):
    T, m = info.T, info.m
    if True:                                                # cut and sewn, tucked into the boots (trousers.py)
        import trousers
        return join(trousers.build(info), "C_legs__orion")
    wz = T["hips"]["z"] + (.06 if m else .075)
    ank = info.L["A"].z

    def keep(c, r):
        if r in ("thigh",):
            return True
        if r == "shin":
            return c.z > ank + .04
        if r in ("pelvis", "midriff"):
            return c.z < wz
        return False
    loose = .009 if m else .004
    F_ = Folds(info)
    stack = ank + (.11 if m else .16)
    o = from_faces(info, "legs", keep, lambda co, n, r: loose if r != "pelvis" else .006, "orion_cloth",
                   fold=lambda co, r: F_.trouser(co, r, .0065 if m else .003, stack_z=stack), drape=6 if m else 2)
    solidify(o, .003)
    parts = [o]
    K = info.L["K"]
    for sx in (1, -1):
        kx = K.x * sx
        parts.append(plate_on(info, "knee", (kx, K.y - .06, K.z + .01), None, (.075, .10, .014), "orion_plate", lift=loose + .004))
        if m:
            # cargo pocket on the outer thigh
            parts.append(plate_on(info, "pocket", (kx + sx * .06, 0.0, K.z + .25), None, (.075, .10, .025), "orion_cloth", lift=loose + .004))
        else:
            parts.append(plate_on(info, "thighplate", (kx + sx * .02, -.04, K.z + .22), None, (.07, .14, .010), "orion_plate", lift=loose + .003))
            parts.append(plate_on(info, "shinplate", (kx, K.y - .05, K.z - .18), None, (.055, .16, .010), "orion_plate", lift=loose + .003))
    return join(parts, "C_legs__orion")


def feet(info):
    T, m = info.T, info.m
    if True:                                                # combat boots on their own last (boots.py)
        import boots
        return join(boots.build(info), "C_feet__orion")
    ank = info.L["A"].z
    top_z = ank + (.11 if m else .16)

    F = info.F
    ball_y = F["ball"].y + .004

    def keep(c, r):                                       # the upper, behind the toes (the toe box closes it)
        return (r == "foot" and c.y > ball_y) or (r == "shin" and c.z <= top_z)
    o = from_faces(info, "boot", keep, lambda co, n, r: .010 if r == "shin" else .008, "orion_black")
    solidify(o, .004)
    parts = [o]
    for sx in (1, -1):
        parts.append(toe_box(info, sx))
    for sx in (1, -1):
        heel, ball = F["heel"], F["ball"]
        ln = F["length"] + .02
        cy = (heel.y + (ball.y - .07)) / 2
        cx = (F["ankle"].x + .004) * sx
        parts.append(sole(info, sx))
        if not m:
            parts.append(box("heel", (F["width"] * .7, .055, .035), (cx, heel.y - .01, .022), "orion_sole", bevel=.004))
            parts.append(plate_on(info, "bootplate", (cx, F["ankle"].y - .06, ank + .08), None, (.06, .08, .008), "orion_plate", lift=.012))
        else:
            parts.append(plate_on(info, "toecap", (cx, ball.y - .05, .05), None, (.07, .05, .008), "orion_steel", lift=.010))
    return join(parts, "C_feet__orion")


def hands(info, armoured=False):
    T = info.T
    if True:                                                # built on the hand (gloves.py)
        import gloves
        return join(gloves.build(info, armoured), "C_hands__orion_armoured" if armoured else "C_hands__orion")
    Hd = info.H
    A = info.A
    W, kn, a = A["W"], Hd["knuckle"], A["a"]
    phal = {f: ch["joints"] for f, ch in Hd["fingers"].items()}

    def keep(c, r):
        if r == "hand":
            if armoured:
                return True
            q = Vector((abs(c.x), c.y, c.z))
            # fingerless: the glove stops half way along the first phalanx
            return (q - kn).dot(a) < .012
        if r == "forearm":
            q = Vector((abs(c.x), c.y, c.z))
            return (q - W).dot(a) > -.07
        return False
    o = from_faces(info, "glove", keep, lambda co, n, r: .0025, "orion_black", wrinkle=.0006, hem=.0012)
    solidify(o, .002)
    parts = [o]
    dor = A["dorsal"]
    for sx in (1, -1):
        wx = Vector((W.x * sx, W.y, W.z)) - Vector((a.x * sx, a.y, a.z)) * .035
        parts.append(plate_on(info, "wristunit", wx + Vector((dor.x * sx, dor.y, dor.z)) * .02, None, (.035, .045, .012), "orion_steel", lift=.007))
        parts.append(plate_on(info, "wristglow", wx + Vector((dor.x * sx, dor.y, dor.z)) * .02, None, (.018, .010, .004), "orion_glow", lift=.020))
        if armoured:
            kc = Vector((kn.x * sx, kn.y, kn.z))
            parts.append(plate_on(info, "knuckles", kc + Vector((dor.x * sx, dor.y, dor.z)) * .01, None, (.065, .022, .010), "orion_plate", lift=.006))
    name = "C_hands__orion_armoured" if armoured else "C_hands__orion"
    return join(parts, name)


def vest(info):
    T, m = info.T, info.m
    if True:                                                # the belt rig (belt.py)
        import belt
        return join(belt.build(info), "C_vest__orion")
    hz = T["hips"]["z"]
    z0, z1 = hz + .045, hz + .085
    belt = ring_band(info, "belt", z0, z1, .016 if m else .010, "orion_strap", keep=lambda c, r: r in ("pelvis", "midriff"))
    solidify(belt, .006)
    parts = [belt]
    # buckle and pouches round the belt
    loc, nrm, _, _ = info.bvh.find_nearest(Vector((0, -.15, (z0 + z1) / 2)))
    parts.append(box("buckle", (.055, .012, .040), loc + nrm * .028, "orion_plate", bevel=.003))
    parts.append(box("buckleglow", (.030, .004, .010), loc + nrm * .036, "orion_glow", bevel=.0))
    for ang in (35, 70, 110, 145, -35, -70, -110):
        a = math.radians(ang)
        d = Vector((math.sin(a), -math.cos(a), 0))
        hit = info.bvh.ray_cast(Vector((0, .01, (z0 + z1) / 2)) + d * .4, -d)
        if hit[0] is None:
            continue
        p, n = hit[0], hit[1]
        side = Vector((0, 0, 1)).cross(n).normalized()
        R = Matrix((side, Vector((0, 0, 1)), n)).transposed()
        parts.append(box("pouch", (.05, .065, .03), p + n * (.032 if m else .026) + Vector((0, 0, -.012)), "orion_black", R, bevel=.005))
    if m:
        # a strap across the chest (left shoulder to right hip)
        C = T["chest"]
        pts = [Vector((.11, -.13, C["z"] + .10)), Vector((0, -.16, C["z"] - .02)), Vector((-.10, -.13, hz + .14))]
        for i in range(len(pts) - 1):
            p0, p1 = pts[i], pts[i + 1]
            mid = (p0 + p1) / 2
            loc, nrm, _, _ = info.bvh.find_nearest(mid)
            d = (p1 - p0)
            ln = d.length
            d.normalize()
            n = nrm.normalized()
            side = d.cross(n).normalized()
            R = Matrix((side, d, n)).transposed()
            parts.append(box("strap", (.035, ln + .02, .006), loc + n * .016, "orion_strap", R, bevel=.002))
    else:
        # a holster on the right thigh
        K, Hj = info.L["K"], info.L["H"]
        tz = (K.z + Hj.z) / 2 + .02
        band = ring_band(info, "thighband", tz - .015, tz + .015, .008, "orion_strap",
                         keep=lambda c, r: r == "thigh" and c.x < 0)
        solidify(band, .004)
        parts.append(band)
        hit = info.bvh.ray_cast(Vector((-.40, -.01, tz - .02)), Vector((1, 0, 0)))
        if hit[0] is not None:
            p, n = hit[0], hit[1]
            parts.append(box("holster", (.035, .07, .13), p + n * .030, "orion_black", bevel=.006))
    return join(parts, "C_vest__orion")


def skirt(info):
    """the long coat's skirt: lofted rings round both legs from the hips to below the knee, open at the front, the
    outside in the coat colour and the inside in the blue lining (two layers, a rim at the hem and the front edges)"""
    T = info.T
    hz = T["hips"]["z"]
    K = info.L["K"]
    z_top, z_bot = hz + .02, K.z - .08
    n_ring, n_seg = 16, 72
    gap = math.radians(26)                                 # the open front: +-26 degrees round the front centre
    bm = bmesh.new()
    rows_out, rows_in = [], []
    for i in range(n_ring + 1):
        t = i / n_ring
        z = z_top + (z_bot - z_top) * t
        # the body's half width / depth at the top, then flaring out
        rx = (T["hips"]["w"] / 2 + .030) * (1 + .22 * t)
        ry_f = (T["hips"]["d"] * .5 + .030) * (1 + .30 * t)
        ry_b = (T["hips"]["d"] * .55 + .040) * (1 + .40 * t)
        ro, ri = [], []
        for k in range(n_seg + 1):
            a = gap + (2 * math.pi - 2 * gap) * k / n_seg   # 0 = front centre, round by the left side
            ry = ry_f if math.cos(a) > 0 else ry_b
            # drape: soft vertical folds growing toward the hem, a little irregular
            fold = 1.0 + (.010 + .075 * t * t) * math.sin(9 * a + 1.7 * mnoise.noise(Vector((a * 1.3, t * 2.0, .5))))                 * (.55 + .45 * mnoise.noise(Vector((a * 2.1, 4.0, t))))
            x = math.sin(a) * rx * fold
            y = -math.cos(a) * ry * fold + .012
            ro.append(bm.verts.new((x, y, z)))
            inner = .006
            ri.append(bm.verts.new((x - math.sin(a) * inner, y + math.cos(a) * inner, z)))
        rows_out.append(ro)
        rows_in.append(ri)
    for i in range(n_ring):
        for k in range(n_seg):
            bm.faces.new((rows_out[i][k], rows_out[i + 1][k], rows_out[i + 1][k + 1], rows_out[i][k + 1]))
            f = bm.faces.new((rows_in[i][k], rows_in[i][k + 1], rows_in[i + 1][k + 1], rows_in[i + 1][k]))
            f.material_index = 1
    for k in range(n_seg):                                 # hem rim
        bm.faces.new((rows_out[n_ring][k], rows_in[n_ring][k], rows_in[n_ring][k + 1], rows_out[n_ring][k + 1]))
    for i in range(n_ring):                                # front edge rims
        bm.faces.new((rows_out[i][0], rows_out[i + 1][0], rows_in[i + 1][0], rows_in[i][0]))
        bm.faces.new((rows_out[i][n_seg], rows_in[i][n_seg], rows_in[i + 1][n_seg], rows_out[i + 1][n_seg]))
    bm.normal_update()
    o = to_object(bm, "skirt", "orion_coat")
    o.data.materials.append(material("orion_lining"))
    for p, f in zip(o.data.polygons, range(len(o.data.polygons))):
        pass
    # restore the lining indices (to_object reset them): inner faces point toward the axis
    for p in o.data.polygons:
        c = p.center
        radial = Vector((c.x, c.y - .012, 0))
        p.material_index = 1 if radial.length > 1e-6 and p.normal.dot(radial.normalized()) < -.5 else 0
    return o


def toe_box(info, sx):
    """the boot's front: lofted sections from just behind the ball of the foot to a rounded toe"""
    F = info.F
    y0, y1 = F["ball"].y + .035, F["toe_y"] - .006
    cx = (F["ankle"].x + .004) * sx
    n_ring, n_seg = 8, 16
    bm = bmesh.new()
    rows = []
    for i in range(n_ring + 1):
        t = i / n_ring
        y = y0 + (y1 - y0) * t
        hw = F["width"] * (.56 - .10 * t * t)
        h = .068 - .026 * t - .014 * t * t
        ring = []
        for k in range(n_seg):
            a = 2 * math.pi * k / n_seg
            c, s_ = math.cos(a), math.sin(a)
            x = cx + math.copysign(abs(c) ** .7, c) * hw
            z = .012 + (h / 2) * (1 + math.copysign(abs(s_) ** .8, s_))
            ring.append(bm.verts.new((x, y, max(.012, z))))
        rows.append(ring)
    for i in range(n_ring):
        for k in range(n_seg):
            bm.faces.new((rows[i][k], rows[i + 1][k], rows[i + 1][(k + 1) % n_seg], rows[i][(k + 1) % n_seg]))
    tip = bm.verts.new((cx, y1 - .012, .028))
    for k in range(n_seg):
        bm.faces.new((rows[-1][k], tip, rows[-1][(k + 1) % n_seg]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return to_object(bm, "toebox", "orion_black")


def sole(info, sx):
    """a boot sole under the foot: the foot's outline at the floor, thickened downward a little"""
    F = info.F
    heel, ball = F["heel"], F["ball"]
    toe_y = F["toe_y"] - .002
    w = F["width"] * .56
    pts = []
    for t in np.linspace(0, 1, 9):
        y = heel.y + .02 + (toe_y - heel.y - .02) * t
        hw = w * (.78 + .30 * math.sin(min(1, t * 1.25) * math.pi * .9))
        pts.append((y, hw * (1 - .55 * max(0, t - .85) / .15)))
    bm = bmesh.new()
    cx = F["ankle"].x * sx + .006 * sx
    top, bot = [], []
    for y, hw in pts:
        top.append((bm.verts.new((cx - hw, y, .014)), bm.verts.new((cx + hw, y, .014))))
        bot.append((bm.verts.new((cx - hw * .97, y, -.004)), bm.verts.new((cx + hw * .97, y, -.004))))
    for i in range(len(pts) - 1):
        bm.faces.new((top[i][0], top[i][1], top[i + 1][1], top[i + 1][0]))
        bm.faces.new((bot[i][0], bot[i + 1][0], bot[i + 1][1], bot[i][1]))
        bm.faces.new((top[i][0], top[i + 1][0], bot[i + 1][0], bot[i][0]))
        bm.faces.new((top[i][1], bot[i][1], bot[i + 1][1], top[i + 1][1]))
    bm.faces.new((top[0][0], bot[0][0], bot[0][1], top[0][1]))
    bm.faces.new((top[-1][0], top[-1][1], bot[-1][1], bot[-1][0]))
    bm.normal_update()
    return to_object(bm, "sole", "orion_sole")


def outer(info):
    T, m = info.T, info.m
    if True:                                                # his field coat / her cropped jacket (coat.py)
        import coat
        return join(coat.build(info), "C_outer__orion")
    ub = T["underbust"]["z"]
    hz = T["hips"]["z"]
    nb = T["neck_base_z"]
    W = info.A["W"]
    a = info.A["a"]
    front_gap = .055 if m else .045

    def keep(c, r):
        open_front = c.y < -.02 and abs(c.x) < front_gap and c.z < nb - .02
        if open_front:
            return False
        if r in ("upperarm",):
            return True
        if r == "forearm":
            q = Vector((abs(c.x), c.y, c.z))
            return (q - W).dot(a) < -.045
        if r == "chest":
            return True
        if r == "neck":
            return c.z < nb + .02
        if m:
            return r in ("midriff", "pelvis")
        return r == "midriff" and c.z > ub - .01
    push = (lambda co, n, r: .020 if r in ("midriff", "pelvis") else .014) if m else (lambda co, n, r: .011)
    F_ = Folds(info)
    o = from_faces(info, "coat", keep, push, "orion_coat" if m else "orion_white",
                   fold=lambda co, r: F_.sleeve(co, r, .009 if m else .006, cuff=-.06), wrinkle=.0016, drape=12 if m else 8)
    skirt_obj = skirt(info) if m else None
    # collar: the neckline carried up and out
    def pick_neck(c):
        return c.z

    def move_neck(co, k):
        cen = Vector((0, .02, co.z))
        d = Vector((co.x, co.y - .02, 0))
        return Vector((d.x * 1.10, d.y * 1.10 + .02, co.z + .028))
    extrude_loop(o, pick_neck, move_neck, rings=2 if m else 2)
    solidify(o, .005)
    parts = [o]
    if m:
        parts.append(skirt_obj)
        # hood down behind the collar
        hz2 = nb + .06
        parts.append(box("hood", (.20, .07, .09), (0, .11, hz2), "orion_coat", bevel=.025))
        # shoulder tabs with glow strips
        S = info.A["S"]
        for sx in (1, -1):
            parts.append(plate_on(info, "tab", (S.x * sx * .95, S.y - .01, S.z + .045), None, (.06, .05, .008), "orion_steel", lift=.022))
            parts.append(plate_on(info, "tabglow", (S.x * sx * .95, S.y - .01, S.z + .045), None, (.03, .008, .003), "orion_glow", lift=.032))
    else:
        S = info.A["S"]
        for sx in (1, -1):
            parts.append(plate_on(info, "tab", (S.x * sx * .95, S.y - .03, S.z + .03), None, (.05, .04, .006), "orion_grey", lift=.016))
            parts.append(plate_on(info, "tabglow", (S.x * sx * .95, S.y - .03, S.z + .03), None, (.02, .006, .003), "orion_glow", lift=.022))
    return join(parts, "C_outer__orion")


def skin_like_body(piece, body, arm):
    """weights from the body's nearest surface; armature modifier on the rig"""
    for g in list(piece.vertex_groups):
        piece.vertex_groups.remove(g)
    for g in body.vertex_groups:
        piece.vertex_groups.new(name=g.name)
    dt = piece.modifiers.new("dt", 'DATA_TRANSFER')
    dt.object = body
    dt.use_vert_data = True
    dt.data_types_verts = {'VGROUP_WEIGHTS'}
    dt.vert_mapping = 'POLYINTERP_NEAREST'
    dt.layers_vgroup_select_src = 'ALL'
    dt.layers_vgroup_select_dst = 'NAME'
    bpy.context.view_layer.objects.active = piece
    bpy.ops.object.modifier_apply(modifier=dt.name)
    piece.parent = arm
    mod = piece.modifiers.new("Armature", 'ARMATURE')
    mod.object = arm


def dress(body, arm, T, log=print):
    """builds every piece on the rigged body and records the wardrobe in the armature's worldex"""
    info = BodyInfo(body, T)
    m = info.m
    # body shape keys must be off while sampling (the basis is what the pieces fit)
    import hair as hair_mod
    tex_dir = hair_mod.tex_dir(T)
    pieces = [top(info), legs(info), feet(info), hands(info), hands(info, armoured=True), vest(info), outer(info),
              hair_mod.build(info, T, tex_dir, log=log)]
    info.free()
    import fabric
    fabric.apply(T, tex_dir)                                # the cloth textures (fabric.py), this body's own files
    for p in pieces:
        skin_like_body(p, body, arm)
        log(f"wardrobe: {p.name} {len(p.data.polygons)} faces")
    hair_item = "short" if m else "ponytail"
    wardrobe = {
        "top": {"orion": {"label": "Orion Tactical Shirt" if m else "Orion Crop Top",
                          "hide": ["chest", "midriff", "upperarm", "forearm"] if m else ["chest"]}},
        "vest": {"orion": {"label": "Orion Utility Rig", "hide": []}},
        "outer": {"orion": {"label": "Orion Field Coat" if m else "Orion Cropped Jacket",
                            # (every region it covers is hidden: no skin can show through it in any pose)
                            "hide": ["upperarm", "forearm", "chest", "midriff"] if m else ["upperarm", "forearm", "chest"]}},
        "hands": {"orion": {"label": "Orion Fingerless Gloves", "hide": []},
                  "orion_armoured": {"label": "Orion Armoured Gloves", "hide": ["hand"]}},
        "legs": {"orion": {"label": "Orion Cargo Trousers" if m else "Orion Plated Trousers", "hide": ["pelvis", "thigh", "shin"]}},
        "feet": {"orion": {"label": "Orion Combat Boots", "hide": ["foot"]}},
        "hair": {hair_item: {"label": "Short Swept" if m else "High Ponytail", "hide": []}},
    }
    defaults = {"top": "orion", "vest": "orion", "outer": "orion", "hands": "orion", "legs": "orion", "feet": "orion",
                "hair": hair_item}
    meta = json.loads(arm.get("worldex", "{}"))
    meta.update({"wardrobe": wardrobe, "defaults": defaults})
    arm["worldex"] = json.dumps(meta)
    return pieces
