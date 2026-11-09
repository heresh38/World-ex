"""Loot pickups for the Unreal game: assets/models/loot_props.glb with
  PR_core   a loot core (floats and turns in the game, its glow tinted by the rarity): a faceted energy crystal held in a
            steel cage of two rings with glow channels, four curved ribs and an emitter cap above and below. Origin at
            its centre.
  PR_ammo   an ammo case (sits on the ground): a rugged bevelled polymer case with a lid seam, side ribs, a carry handle,
            latches and a glowing window on the rounds. Origin at the bottom centre.
Material names are an API: `core_glow` (the game tints it by rarity), `ammo_glow`, `loot_metal`, `loot_dark`,
`ammo_case`. Edge wear goes into the `_wear` attribute (export_fbx.py writes it into the vertex colour alpha).
    blender --background --python tools/blender/loot_props.py
"""
import math
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))
import bpy
import bmesh
from mathutils import Vector, Matrix
import bl
import gunkit

M = {}


def mats():
    M["glow"] = bl.mat("core_glow", "#ffffff", rough=.25, emit="#ffffff", strength=6.0)
    M["ammo_glow"] = bl.mat("ammo_glow", "#ffd58a", rough=.3, emit="#ffc860", strength=4.0)
    M["metal"] = bl.mat("loot_metal", "#62666d", metal=.85, rough=.32)
    M["dark"] = bl.mat("loot_dark", "#1b1d21", metal=.2, rough=.55)
    M["case"] = bl.mat("ammo_case", "#3b4336", metal=.0, rough=.62)


def tube(name, pts, r, m, sides=12, cap=True):
    """a round section swept along points"""
    bm = bmesh.new()
    rings = []
    for i, p in enumerate(pts):
        t = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        a = t.cross(Vector((0, 0, 1)) if abs(t.z) < .9 else Vector((1, 0, 0))).normalized()
        b = t.cross(a).normalized()
        rings.append([bm.verts.new(p + (a * math.cos(2 * math.pi * k / sides) + b * math.sin(2 * math.pi * k / sides)) * r)
                      for k in range(sides)])
    for r0, r1 in zip(rings, rings[1:]):
        for k in range(sides):
            bm.faces.new((r0[k], r0[(k + 1) % sides], r1[(k + 1) % sides], r1[k]))
    if cap:
        bm.faces.new(rings[0][::-1])
        bm.faces.new(rings[-1])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    o.data.materials.append(m)
    for p in o.data.polygons:
        p.use_smooth = True
    return o


def ring_pts(R, z, n=64):
    return [Vector((R * math.cos(2 * math.pi * k / n), R * math.sin(2 * math.pi * k / n), z)) for k in range(n + 1)]


def crystal():
    """a faceted gem: two staggered rings of six between two long points"""
    top, bot = Vector((0, 0, .112)), Vector((0, 0, -.112))
    ra = [Vector((.046 * math.cos(math.pi / 3 * k), .046 * math.sin(math.pi / 3 * k), .022)) for k in range(6)]
    rb = [Vector((.046 * math.cos(math.pi / 3 * k + math.pi / 6), .046 * math.sin(math.pi / 3 * k + math.pi / 6), -.022)) for k in range(6)]
    verts = [top, bot] + ra + rb
    faces = []
    for k in range(6):
        faces.append((0, 2 + k, 2 + (k + 1) % 6))
        faces.append((1, 8 + (k + 1) % 6, 8 + k))
        faces.append((2 + k, 8 + k, 2 + (k + 1) % 6))
        faces.append((2 + (k + 1) % 6, 8 + k, 8 + (k + 1) % 6))
    o = bl.mesh_from("crystal", verts, faces, M["glow"])
    md = o.modifiers.new("bv", 'BEVEL')
    md.width = .0018
    md.segments = 2
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.modifier_apply(modifier=md.name)
    return o


def core():
    parts = [crystal()]
    R = .088
    for z in (.078, -.078):
        parts.append(tube("ring", ring_pts(R, z), .0085, M["metal"], sides=14))
        parts.append(tube("ringglow", ring_pts(R - .0062, z), .0032, M["glow"], sides=8))
    for k in range(4):                                         # the ribs bow out between the rings
        a = math.pi / 2 * k + math.pi / 4
        d = Vector((math.cos(a), math.sin(a), 0))
        pts = [d * (R + .010 * math.sin(math.pi * t)) + Vector((0, 0, .078 - .156 * t)) for t in [i / 16 for i in range(17)]]
        parts.append(tube("rib", pts, .0062, M["metal"], sides=10))
        for z in (.078, -.078):                                # a clamp where each rib meets a ring
            c = d * R + Vector((0, 0, z))
            parts.append(bl.box("clamp", (.020, .020, .026), c, M["dark"], bevel=.004, rot=(0, 0, a)))
    for s in (1, -1):                                          # emitter caps above and below the crystal
        parts.append(bl.cyl("cap", .030, .016, (0, 0, s * .130), M["metal"], verts=24, r2=.018 if s > 0 else None, bevel=.003))
        parts.append(bl.cyl("emitter", .012, .010, (0, 0, s * .118), M["glow"], verts=20))
        for k in range(4):                                     # spokes from the cap to the ring
            a = math.pi / 2 * k
            d = Vector((math.cos(a), math.sin(a), 0))
            parts.append(tube("spoke", [d * .024 + Vector((0, 0, s * .128)), d * (R - .004) + Vector((0, 0, s * .080))], .0042, M["metal"], sides=8))
    o = bl.join(parts, "PR_core_mesh")
    gunkit.wear_attr(o)
    root = bl.empty("PR_core")
    o.parent = root
    return root


def ammo():
    W, D, H = .300, .180, .130
    parts = [bl.box("case", (W, D, H), (0, 0, H / 2), M["case"], bevel=.012, segs=3)]
    parts.append(bl.box("seam", (W + .004, D + .004, .012), (0, 0, H * .74), M["dark"], bevel=.004, segs=2))
    for sy, xs in ((1, (-.080, 0.0, .080)), (-1, (-.124, .124))):   # ribs down the long sides (the front's clear of the window)
        for x in xs:
            parts.append(bl.box("rib", (.016, .010, H * .62), (x, sy * (D / 2 + .003), H * .40), M["case"], bevel=.004, segs=2))
    for sx in (1, -1):                                         # latches on the front
        parts.append(bl.box("latch", (.034, .012, .040), (sx * .095, -(D / 2 + .005), H * .74), M["metal"], bevel=.004, segs=2))
        parts.append(bl.box("latchbar", (.026, .006, .010), (sx * .095, -(D / 2 + .012), H * .74 + .010), M["dark"], bevel=.002))
    # the carry handle with its mounts
    pts = [Vector((-.075 + .150 * t, 0, H + .014 + .030 * math.sin(math.pi * t))) for t in [i / 20 for i in range(21)]]
    parts.append(tube("handle", pts, .0075, M["metal"], sides=12))
    for sx in (1, -1):
        parts.append(bl.box("mount", (.026, .030, .016), (sx * .075, 0, H + .006), M["dark"], bevel=.005, segs=2))
    # the window on the rounds (front), in a frame
    parts.append(bl.box("window", (.150, .006, .032), (0, -(D / 2 + .001), H * .38), M["ammo_glow"], bevel=.002))
    parts.append(bl.box("frame", (.166, .006, .006), (0, -(D / 2 + .004), H * .38 + .019), M["metal"], bevel=.002))
    parts.append(bl.box("frame", (.166, .006, .006), (0, -(D / 2 + .004), H * .38 - .019), M["metal"], bevel=.002))
    o = bl.join(parts, "PR_ammo_mesh")
    gunkit.wear_attr(o)
    root = bl.empty("PR_ammo")
    o.parent = root
    return root


def main():
    bl.reset()
    mats()
    core()
    ammo().location.x = .5 if "--apart" in sys.argv else 0.0     # (--apart: side by side, for previews)
    bl.export("loot_props.glb")


main()
