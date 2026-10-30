"""First-person arms (viewmodel), authored in gun space: origin = pistol grip, barrel along Blender -Y.

Nodes: arm_R (right hand on the grip, origin at the grip) and arm_L (origin at the left palm; the game moves
it onto each gun's 'foregrip' empty). Material names match the characters so the wardrobe colours apply.
"""
import bpy, math, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import bl
from mathutils import Vector


def seg(name, p0, p1, r0, r1, m, verts=12):
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    bpy.ops.mesh.primitive_cone_add(vertices=verts, radius1=r0, radius2=r1, depth=d.length, location=(p0 + p1) / 2)
    o = bpy.context.object
    o.rotation_mode = 'QUATERNION'; o.rotation_quaternion = d.to_track_quat('Z', 'Y')
    o = bl._finish(o, m, name)
    bl.autosmooth(o, 40)
    return o


def arm(name, hand, wrist, elbow, mats, side):
    root = bl.empty(name, (0, 0, 0))
    P, S, U, G = mats['armor_primary'], mats['armor_secondary'], mats['undersuit'], mats['glow']
    parts = [
        seg('forearm', wrist, elbow, .036, .046, U),
        seg('gauntlet', Vector(wrist) + (Vector(elbow) - Vector(wrist)) * .08, Vector(wrist) + (Vector(elbow) - Vector(wrist)) * .75, .046, .054, S),
        seg('cuff', Vector(wrist) + (Vector(elbow) - Vector(wrist)) * .02, Vector(wrist) + (Vector(elbow) - Vector(wrist)) * .12, .05, .05, P),
        bl.box('palm', (.055, .075, .06), hand, U, bevel=.012),
        bl.box('knuckles', (.06, .03, .045), Vector(hand) + Vector((0, -.04, .005)), S, bevel=.01),
        bl.box('thumb', (.018, .05, .02), Vector(hand) + Vector((side * .03, -.02, .02)), U, bevel=.006),
    ]
    mid = (Vector(wrist) + Vector(elbow)) / 2
    parts.append(bl.box('plate', (.05, .12, .02), mid + Vector((0, 0, .05)), P, bevel=.008))
    parts.append(bl.box('strip', (.008, .1, .006), mid + Vector((0, 0, .062)), G))
    for o in parts:
        bl.apply_all(o)
    g = bl.join(parts, name + '_mesh')
    g.parent = root
    return root


def main():
    bl.reset()
    mats = {
        'armor_primary': bl.mat('armor_primary', '#e8e2d4', .1, .35),
        'armor_secondary': bl.mat('armor_secondary', '#3a3f47', .75, .38),
        'undersuit': bl.mat('undersuit', '#22262c', 0, .75),
        'glow': bl.mat('glow', '#1ad8ff', 0, .4, emit='#1ad8ff', strength=5),
    }
    # right hand wraps the grip; forearm runs back toward the camera and out to the right (-X)
    arm('arm_R', (0, .015, -.045), (-.01, .06, -.09), (-.13, .36, -.24), mats, -1)
    # left arm authored with the palm at the origin; elbow back toward the camera, out to the left (+X)
    arm('arm_L', (0, 0, -.01), (.02, .05, -.05), (.17, .36, -.2), mats, 1)
    bl.export('viewmodel_arms.glb')


main()
