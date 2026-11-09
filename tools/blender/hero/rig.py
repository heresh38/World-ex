"""Rigs a fitted hero base mesh for the game and writes the GLB that export_fbx.py turns into Unreal FBX.

The game's player contract (unreal/ShatteredOrbit: SOLocomotionAnimInstance, SOCharacter, import_assets.py):
  bones   root (not deforming) > hips > spine > chest > neck > head; chest > upperarm.X > forearm.X > hand.X;
          hips > thigh.X > shin.X > foot.X; hand.X > <index|middle|ring|pinky|thumb>_01..03.X (Unreal: _L / _R)
          - the shared layout of characters.make_armature, here with the joints of our own skeleton (skeleton.py)
  clips   characters.animate's player set (Idle, Walk, Run, Jump, IdleRelaxed, WalkRelaxed, RunRelaxed, Sit, Death,
          Slide; gendered gait). Those poses assume arms hanging at the sides, so every clip first lowers our A-pose
          arms to the sides
  mesh    B_body: one mesh, one material section per body region (skin__head, skin__neck, skin__chest,
          skin__midriff, skin__pelvis, skin__upperarm, skin__forearm, skin__hand, skin__thigh, skin__shin,
          skin__foot), so worn pieces can hide the regions they cover; the face_* shape keys become morph targets.
          B_eyes: both eyeballs (eye_white, eye_iris), on the head bone
          B_brows: eyebrows and eyelashes as strand cards (hair__brow, hair__lash; hair.face_hair), on the head bone
  meta    the armature's `worldex` (wardrobe, defaults, regions) for wardrobe.json; no clothing yet
"""
import json
import math
import types
import numpy as np
import bpy
from mathutils import Vector
import skeleton

REGIONS = ("head", "neck", "chest", "midriff", "pelvis", "upperarm", "forearm", "hand", "thigh", "shin", "foot")
SKIN = {"head": (.80, .62, .52), "default": (.78, .60, .50)}
FINGER_NAME = {"index": "index", "middle": "middle", "ring": "ring", "little": "pinky"}


def mx(v, sx):
    return Vector((v.x * sx, v.y, v.z))


def joints(T):
    """the armature's joints (characters.make_armature's names), both sides"""
    A, L, F = skeleton.arm(T), skeleton.leg(T), skeleton.foot(T)
    Hd = skeleton.hand(T)
    y = .012
    hz = L["H"].z + .035
    J = {"hips": (Vector((0, y, hz)), Vector((0, y, T["waist"]["z"]))),
         "spine": (Vector((0, y, T["waist"]["z"])), Vector((0, y, T["chest"]["z"]))),
         "chest": (Vector((0, y, T["chest"]["z"])), Vector((0, y + .015, T["neck_base_z"]))),
         "neck": (Vector((0, y + .015, T["neck_base_z"])), Vector((0, .006, T["chin_z"] + .03))),
         "head": (Vector((0, .006, T["chin_z"] + .03)), Vector((0, .006, T["height"])))}
    for side, sx in (("L", 1), ("R", -1)):
        J["upperarm." + side] = (mx(A["S"], sx), mx(A["E"], sx))
        J["forearm." + side] = (mx(A["E"], sx), mx(A["W"], sx))
        J["hand." + side] = (mx(A["W"], sx), mx(Hd["knuckle"], sx))
        J["thigh." + side] = (mx(L["H"], sx), mx(L["K"], sx))
        J["shin." + side] = (mx(L["K"], sx), mx(L["A"], sx))
        J["foot." + side] = (mx(F["ankle"], sx), mx(F["ball"], sx))
    return J


def add_fingers(arm, T):
    Hd = skeleton.hand(T)
    dor = Hd["arm"]["dorsal"]
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm.data.edit_bones
    chains = [(FINGER_NAME[f], ch["joints"]) for f, ch in Hd["fingers"].items()] + [("thumb", Hd["thumb"]["joints"])]
    for side, sx in (("L", 1), ("R", -1)):
        for name, Jn in chains:
            parent = eb["hand." + side]
            for k in range(3):
                e = eb.new(f"{name}_0{k + 1}.{side}")
                e.head, e.tail = mx(Jn[k], sx), mx(Jn[k + 1], sx)
                e.align_roll(mx(dor, sx))
                e.parent = parent
                e.use_connect = k > 0
                parent = e
    bpy.ops.object.mode_set(mode='OBJECT')


def regions_of(o, T):
    """region per vertex from the fit's part groups (vertex groups) and the joints"""
    me = o.data
    names = [g.name for g in o.vertex_groups]
    W = np.zeros((len(me.vertices), max(1, len(names))), np.float32)
    for v in me.vertices:
        for g in v.groups:
            W[v.index, g.group] = g.weight
    part = np.array([names[i] for i in W.argmax(1)])
    P = np.array([v.co for v in me.vertices], np.float32)
    A, L = skeleton.arm(T), skeleton.leg(T)
    reg = np.empty(len(P), object)
    reg[:] = "chest"
    reg[part == "head"] = "head"
    reg[part == "neck"] = "neck"
    t = part == "torso"
    z = P[:, 2]
    reg[t & (z < T["underbust"]["z"] - .02)] = "midriff"
    reg[t & (z < T["hips"]["z"] + .05)] = "pelvis"
    for nm in ("hand",):
        reg[part == nm] = "hand"
    reg[(part == "foot") | (part == "toe")] = "foot"
    arm = part == "arm"
    S, E = np.array(A["S"]), np.array(A["E"])
    ax = (E - S) / np.linalg.norm(E - S)
    Pa = P.copy(); Pa[:, 0] = np.abs(Pa[:, 0])
    along = (Pa - E) @ ax
    reg[arm & (along < 0)] = "upperarm"
    reg[arm & (along >= 0)] = "forearm"
    leg = part == "leg"
    reg[leg & (z >= L["K"].z)] = "thigh"
    reg[leg & (z < L["K"].z)] = "shin"
    return reg


def skin_material(name, col):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*col, 1)
        bsdf.inputs["Roughness"].default_value = .55
    m.diffuse_color = (*col, 1)
    return m


def section_body(o, T):
    """one material slot per region (skin__<region>), every face in its region's slot"""
    reg = regions_of(o, T)
    me = o.data
    me.materials.clear()
    for r in REGIONS:
        me.materials.append(skin_material("skin__" + r, SKIN.get(r, SKIN["default"])))
    idx = {r: i for i, r in enumerate(REGIONS)}
    for p in me.polygons:
        rs = [reg[v] for v in p.vertices]
        best = max(set(rs), key=rs.count)
        p.material_index = idx[best]
    # the fit's part groups ("head", "neck", ...) would collide with bone names: drop them before skinning
    for g in list(o.vertex_groups):
        o.vertex_groups.remove(g)
    return reg


def dress_eyes(eyes, T):
    """eye_white / eye_iris (the cornea's front cap), joined into B_eyes"""
    white = skin_material("eye_white", (.92, .91, .88))
    iris = skin_material("eye_iris", (.30, .38, .45))
    for e in eyes:
        e.data.materials.clear()
        e.data.materials.append(white)
        e.data.materials.append(iris)
        mw = e.matrix_world
        c = mw.translation
        for p in e.data.polygons:
            n = (mw.to_3x3() @ p.normal).normalized()
            p.material_index = 1 if n.y < -.80 else 0
    bpy.ops.object.select_all(action='DESELECT')
    for e in eyes:
        e.select_set(True)
    bpy.context.view_layer.objects.active = eyes[0]
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.ops.object.join()
    o = bpy.context.view_layer.objects.active
    o.name = o.data.name = "B_eyes"
    return o


def lower_arms(T):
    """the rotation (degrees, about +Y) that brings our A-pose upper arm down to the clip set's arms-at-the-sides rest"""
    a = skeleton.arm(T)["a"]
    return math.degrees(math.atan2(-a.z, a.x)) - 84.0      # the shared rig's arms hang ~84 degrees below horizontal


def patch_clips(deg):
    """wraps characters.pose_fn so every clip first lowers the A-pose arms (IK clips solve from targets anyway)"""
    import characters
    base = characters.pose_fn

    def pose_fn(clip, style=None):
        f = base(clip, style)

        def g(p):
            d, ik, loc = f(p)
            d = dict(d)
            for side, sx in (("L", 1), ("R", -1)):
                k = "upperarm." + side
                d[k] = [((0, 1, 0), sx * -deg)] + list(d.get(k, []))
            return d, ik, loc
        return g
    characters.pose_fn = pose_fn
    return base


def rig(o, eyes, T, sex, log=print):
    import characters
    o.name = o.data.name = "B_body"
    section_body(o, T)
    b = types.SimpleNamespace(J=joints(T), s=T["height"] / 1.84)
    bpy.ops.object.select_all(action='DESELECT')
    arm = characters.make_armature(b, pole_angle=90)
    arm.name = "Armature"
    add_fingers(arm, T)
    for bn in arm.data.bones:
        if bn.name == "root" or bn.name.startswith(("ik_", "pole")):
            bn.use_deform = False
    # skin: automatic (heat) weights on the body; the eyes ride the head
    bpy.ops.object.select_all(action='DESELECT')
    o.select_set(True)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.parent_set(type='ARMATURE_AUTO')
    unweighted = sum(1 for v in o.data.vertices if not any(g.weight > 1e-4 for g in v.groups))
    log(f"rig: {len(arm.data.bones)} bones, {unweighted} body vertices without weights")
    eo = dress_eyes(eyes, T)
    vg = eo.vertex_groups.new(name="head")
    vg.add(list(range(len(eo.data.vertices))), 1.0, 'REPLACE')
    eo.parent = arm
    mod = eo.modifiers.new("Armature", 'ARMATURE')
    mod.object = arm
    import hair
    hair.face_hair(o, eo, arm, T, log=log)                 # B_brows: eyebrows and eyelashes (strand cards)
    # clips (the player set, gendered gait), arms lowered from the A-pose first
    deg = lower_arms(T)
    base = patch_clips(deg)
    try:
        characters.animate(arm, b.s, style=sex, clips=characters.PLAYER_CLIPS)
    finally:
        characters.pose_fn = base
    log(f"rig: clips {', '.join(a.name for a in bpy.data.actions)} (arms lowered {deg:.0f} degrees)")
    arm["worldex"] = json.dumps({"wardrobe": {}, "defaults": {}, "regions": list(REGIONS)})
    # the rest pose stays the A-pose; frame 1 of Idle is what a static preview shows
    return arm


def write_glb(path):
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', export_animations=True, export_morph=True,
                              export_skins=True, export_yup=True, export_apply=False, use_selection=False,
                              export_extras=True)          # (the armature's `worldex` wardrobe metadata)
