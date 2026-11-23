"""The Orion outfit's legs, to the owner's sheet: loose black cargo trousers tucked and bunched into chunky combat
boots. Grown from the suited body (outfit.suited_base) and measured against the sheet (outfit.extents): the trousers
stand a couple of centimetres off the leg, more over the thigh's cargo cut, gathered in folds above the boots; the
boots' uppers stand 1-3 cm off the foot with a high, round toe box, on a lugged sole whose underside is the floor (the
foot stands inside it).
"""
import math

import bmesh
import numpy as np
from mathutils import Vector
from mathutils import noise as mnoise

REGIONS = ("head", "neck", "chest", "midriff", "pelvis", "upperarm", "forearm", "hand", "thigh", "shin", "foot")
R = {n: i for i, n in enumerate(REGIONS)}


def shell(base, regions, z0, z1):
    """the suited body's faces of these regions between two heights, as a bmesh in world space"""
    from coat import keep_largest, strip_shape_layers
    bm = bmesh.new()
    bm.from_mesh(base.data)
    bm.transform(base.matrix_world)
    strip_shape_layers(bm)
    keep = {R[r] for r in regions}
    drop = [f for f in bm.faces if f.material_index not in keep or not (z0 - .03 < f.calc_center_median().z < z1 + .03)]
    bmesh.ops.delete(bm, geom=drop, context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    bm.normal_update()
    return bm


def cut_level(bm, z, keep_above):
    """a clean level cut: what is below (keep_above) or above it goes"""
    from coat import bisect, keep_largest
    bisect(bm, bm.faces[:], (0, 0, z), (0, 0, -1) if keep_above else (0, 0, 1), clear=True)
    bm.normal_update()


# ------------------------------------------------------------------------------------------------ the trousers

def trousers(base, T, log=print):
    from coat import keep_largest
    top, bottom = T["trouser_top"], T["boot_top"] - .035
    bm = shell(base, ("midriff", "pelvis", "thigh", "shin"), bottom, top)
    # (the legs' muscles out of the cloth first: the trousers are displaced from a smoothed copy of the leg)
    from outfit_mat import taubin, hold_out
    taubin(bm, iters=25)
    K = Vector(T["knee"])
    seed = Vector((1.3, 7.7, 2.2))
    moves = []
    for v in bm.verts:
        p, n = v.co.copy(), v.normal.copy()
        z = p.z
        # the cut: snug at the waistband, loose over the seat and the thigh (the cargo cut), easing in to the knee,
        # loose again over the shin where it gathers above the boot
        e = .008 + .016 * smoothstep(top, top - .14, z) - .004 * smoothstep(K.z + .12, K.z, z) * smoothstep(K.z - .12, K.z, z)
        e += .006 * smoothstep(T["boot_top"] + .16, T["boot_top"] + .05, z)
        # (behind the knee and in the front of the hip the cloth spans the hollows: a little more there)
        e += .003 * max(0.0, n.y) * smoothstep(K.z + .10, K.z, z) * smoothstep(K.z - .10, K.z, z)
        # the folds: stacked rings above the boot, soft diagonal drag lines from the crotch, the knee's creases
        dz = z - T["boot_top"]
        stack = .0024 * math.sin(2 * math.pi * dz / .021 + 3.0 * mnoise.noise(p * 11 + seed)) * math.exp(-max(0.0, dz - .01) / .045) if dz > -.04 else 0.0
        knee = .0025 * math.sin(2 * math.pi * (z - K.z) / .03 + mnoise.noise(p * 7 + seed)) * math.exp(-((z - K.z) / .07) ** 2) * max(0.0, n.y + .3)
        drag = .002 * mnoise.noise(Vector((p.x * 9, p.y * 3, p.z * 4)) + seed)
        moves.append(p + n * (e + stack + knee + drag))
    for v, q in zip(bm.verts, moves):
        v.co = q
    bm.normal_update()
    hold_out(bm, base, .006)
    cut_level(bm, top, keep_above=False)
    cut_level(bm, bottom, keep_above=True)
    keep_largest(bm)
    log(f"trousers: {len(bm.faces)} faces, {top:.2f} to {bottom:.2f}")
    return bm


# ------------------------------------------------------------------------------------------------ the boots

def boots(base, T, log=print):
    """the uppers: the foot and the ankle's shell carried out to a chunky boot (a round toe box, a padded collar at the
    top), cut at the boot's top; the soles: the upper's footprint extruded down to the floor, lugged"""
    from coat import keep_largest
    top = T["boot_top"]
    bm = shell(base, ("shin", "foot"), -.01, top)
    A = Vector(T["ankle"])
    moves = []
    for v in bm.verts:
        p, n = v.co.copy(), v.normal.copy()
        sx = 1 if p.x > 0 else -1
        fwd = -(p.y - A.y)                                   # how far ahead of the ankle
        toe = smoothstep(.06, .17, fwd)                      # the forefoot and the toe box
        e = .012 + .010 * toe + .006 * max(0.0, n.z) * toe   # (the toe box stands up and out)
        e += .004 * smoothstep(top - .05, top, p.z)          # (the padded collar)
        e += .006 * max(0.0, -n.y) * smoothstep(A.z + .03, A.z + .09, p.z) * (1 - smoothstep(top - .06, top, p.z))  # tongue
        moves.append(p + n * e)
    for v, q in zip(bm.verts, moves):
        v.co = q
    bm.normal_update()
    cut_level(bm, top, keep_above=False)
    keep_largest_per_side(bm)
    # the sole: whatever of the upper lies under 2.6 cm becomes the outsole's wall down to the floor
    sole_top = .026
    for v in bm.verts:
        if v.co.z < sole_top:
            k = 1 - v.co.z / sole_top
            v.co.z = max(0.0, v.co.z - .012 * k)
    bm.normal_update()
    log(f"boots: uppers {len(bm.faces)} faces, top {top:.2f}")
    return bm


def keep_largest_per_side(bm):
    """keep the largest connected piece on either side (the two boots)"""
    import collections
    seen, parts = set(), []
    for f in bm.faces:
        if f in seen:
            continue
        stack, part = [f], []
        seen.add(f)
        while stack:
            g = stack.pop()
            part.append(g)
            for e in g.edges:
                for h in e.link_faces:
                    if h not in seen:
                        seen.add(h)
                        stack.append(h)
        parts.append(part)
    best = {}
    for p in parts:
        side = 1 if sum(f.calc_center_median().x for f in p) > 0 else -1
        if side not in best or len(p) > len(best[side]):
            best[side] = p
    keep = {f for p in best.values() for f in p}
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f not in keep], context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')


def smoothstep(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def build(base, T, log=print):
    from outfit_mat import to_object, material, face_out
    tb = trousers(base, T, log=log)
    face_out(tb, base)
    t = to_object(tb, "C_legs__orion", "orion_cloth")
    sol = t.modifiers.new("thick", 'SOLIDIFY')
    sol.thickness, sol.offset, sol.use_rim = .003, -1.0, True
    import outfit_boots                                     # (the boots: built on their own last)
    return [t] + outfit_boots.build(base, T, log=log)
