"""The Orion outfit's gloves, to the owner's sheet: fingerless black leather gloves (the fingers bare from the first
joint, the thumb from its middle), a rounded knuckle guard across the back of the hand, and a bracer round the wrist
with a lit blue panel on its back.
"""
import math

import bmesh
import bpy
import numpy as np
from mathutils import Vector

REGIONS = ("head", "neck", "chest", "midriff", "pelvis", "upperarm", "forearm", "hand", "thigh", "shin", "foot")
FINGERS = ("index", "middle", "ring", "pinky")


def bone_seg(arm, name):
    b = arm.data.bones[name]
    M = arm.matrix_world
    return M @ Vector(b.head_local), M @ Vector(b.tail_local)


def seg_dist(p, a, b):
    ab = b - a
    t = max(0.0, min(1.0, (p - a).dot(ab) / max(ab.length_squared, 1e-12)))
    return (p - (a + ab * t)).length, t


def glove(base, arm, sx, log=print):
    """the glove of one hand: the hand's own surface 2.6 mm out, the fingers cut at their first joint's middle"""
    from coat import keep_largest, bisect
    side = "L" if sx > 0 else "R"
    bm = bmesh.new()
    bm.from_mesh(base.data)
    bm.transform(base.matrix_world)
    hand = REGIONS.index("hand")
    fore = REGIONS.index("forearm")
    W = bone_seg(arm, f"hand.{side}")[0]
    keep = []
    for f in bm.faces:
        c = f.calc_center_median()
        if c.x * sx <= 0:
            continue
        if f.material_index == hand or (f.material_index == fore and (c - W).length < .05):
            keep.append(f)
    keepset = set(keep)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f not in keepset], context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    bm.normal_update()
    for v in bm.verts:
        v.co += v.normal * .0026
    bm.normal_update()
    # each finger cut across its first bone at 55 % (the thumb across its second at 45 %)
    cuts = [(f"{n}_01.{side}", .55) for n in FINGERS] + [(f"thumb_02.{side}", .45)]
    for bone, at in cuts:
        a, b = bone_seg(arm, bone)
        p0 = a + (b - a) * at
        n = (b - a).normalized()
        sel = [f for f in bm.faces if seg_dist(f.calc_center_median(), a, b + n * .06)[0] < .016]
        bisect(bm, sel, p0, n, clear=True)
    # the cuff a little up the forearm: a level cut across the arm
    fa = bone_seg(arm, f"forearm.{side}")
    ax = (fa[1] - fa[0]).normalized()
    bisect(bm, bm.faces[:], W - ax * .045, -ax, clear=True)
    keep_largest(bm)
    return bm


def bracer(arm, sx, base_bvh):
    """a short sleeve of armour round the wrist (6 cm), and the screen on its back"""
    side = "L" if sx > 0 else "R"
    fa = bone_seg(arm, f"forearm.{side}")
    W = bone_seg(arm, f"hand.{side}")[0]
    ax = (fa[1] - fa[0]).normalized()
    up = Vector((0, 0, 1))
    right = ax.cross(up).normalized()
    up = right.cross(ax).normalized()
    bm = bmesh.new()
    n = 32
    rings = []
    for k, (off, grow) in enumerate(((-.075, .000), (-.072, .003), (-.026, .003), (-.023, 0.0))):
        c = W + ax * off
        ring = []
        for i in range(n):
            a = 2 * math.pi * i / n
            d = (up * math.cos(a) + right * math.sin(a))
            hit = base_bvh.ray_cast(c + d * .12, -d, .2)[0]
            r = ((hit - c).length if hit is not None else .035) + .0065 + grow
            ring.append(bm.verts.new(c + d * r))
        rings.append(ring)
    for k in range(len(rings) - 1):
        for i in range(n):
            bm.faces.new((rings[k][i], rings[k][(i + 1) % n], rings[k + 1][(i + 1) % n], rings[k + 1][i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    # the screen on the back of the wrist
    import outfit_parts as OP
    top = W + ax * -.049
    hit = base_bvh.ray_cast(top + up * .12, -up, .2)[0]
    c = (hit if hit is not None else top + up * .03) + up * .012
    screen = bmesh.new()
    OP.plate(screen, [(-.016, -.020), (.016, -.020), (.016, .020), (-.016, .020)], OP.frame(c, up, ax),
             thick=.006, ridge=.0015, rings=1, wrap=.0, bevel=.0015)
    light = bmesh.new()
    OP.plate(light, [(-.011, -.015), (.011, -.015), (.011, .015), (-.011, .015)], OP.frame(c + up * .0012, up, ax),
             thick=.001, ridge=.0005, rings=1, wrap=.0, bevel=.0006)
    return bm, screen, light


def build(base, arm, T, log=print):
    from outfit_mat import to_object, face_out
    from mathutils.bvhtree import BVHTree
    b = bmesh.new()
    b.from_mesh(base.data)
    b.transform(base.matrix_world)
    bvh = BVHTree.FromBMesh(b)
    b.free()
    gloves, bracers, screens, lights = bmesh.new(), bmesh.new(), bmesh.new(), bmesh.new()

    def merge(src, dst):
        tmp = bpy.data.meshes.new("_tmp")
        src.to_mesh(tmp)
        dst.from_mesh(tmp)
        bpy.data.meshes.remove(tmp)
        src.free()
    for sx in (1, -1):
        merge(glove(base, arm, sx, log=log), gloves)
        br, sc, li = bracer(arm, sx, bvh)
        merge(br, bracers)
        merge(sc, screens)
        merge(li, lights)
    face_out(gloves, base)
    log(f"gloves: {len(gloves.faces)} faces, bracers, screens")
    g = to_object(gloves, "C_hands__orion", "orion_glove")
    s = g.modifiers.new("thick", 'SOLIDIFY')
    s.thickness, s.offset, s.use_rim = .0018, -1.0, True
    return [g, to_object(bracers, "hand_bracers", "orion_strap"), to_object(screens, "hand_screens", "orion_steel"),
            to_object(lights, "hand_lights", "orion_glow")]
