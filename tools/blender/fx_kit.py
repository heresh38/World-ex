"""Effect cards for the Unreal build (assets/models/fx_kit.glb): the particle system draws these with procedural
materials (soft dots, streaks), so they are plain UV'd quads.

    blender --background --python tools/blender/fx_kit.py

FX_Quad   1 x 1 m card facing -Y (Blender), UVs 0..1      sparks, dust, smoke, blood puffs
FX_Streak 1 m long card along -Y, 1 m wide (scaled thin)  tracers, spark streaks (U runs tail -> head)
FX_Star   five blades about -Y at uneven turns              muzzle flash (the material shapes each to a torn point)
Blender -Y is the forward axis everywhere (Unreal +Y in mesh space, +X after the usual -90 degree yaw).
"""
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(__file__))
import bl  # noqa: E402


def card(name, verts, m):
    """verts: 4 corners in order (u0 v0, u1 v0, u1 v1, u0 v1)."""
    o = bl.mesh_from(name, verts, [(0, 1, 2, 3)], m)
    uv = o.data.uv_layers.new(name="UVMap")
    for loop, (u, v) in zip(o.data.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
        uv.data[loop.index].uv = (u, v)
    return o


def main():
    bl.reset()
    m = bl.mat("fx_card", "#ffffff", rough=1.0)
    h = 0.5
    # Quad facing -Y (normal -Y), centred on the origin.
    card("FX_Quad", [(-h, 0, -h), (h, 0, -h), (h, 0, h), (-h, 0, h)], m)
    # Streak: from the origin (tail, U=0) to 1 m along -Y (head, U=1), lying in the YZ plane.
    card("FX_Streak", [(0, 0, -h), (0, -1, -h), (0, -1, h), (0, 0, h)], m)
    # Star (the muzzle flash): five long blades about -Y at uneven turns, each from the origin (the muzzle, U=0) to its
    # tip (U=1). No card across the bore: two crossed cards and a square read as a cross and a diamond from in front.
    # The effect material shapes each blade to a point and tears it (FX_SHAPE_HLSL mode 3).
    import math
    parts = []
    for k, deg in enumerate((0.0, 31.0, 74.0, 108.0, 151.0)):
        a = math.radians(deg)
        c, sn = math.cos(a) * h, math.sin(a) * h
        L = (1.0, 0.82, 0.94, 0.7, 0.88)[k]
        parts.append(card("star_%d" % k, [(-c, 0, -sn), (-c, -L, -sn), (c, -L, sn), (c, 0, sn)], m))
    bl.join(parts, "FX_Star")
    bl.export("fx_kit.glb")


main()
