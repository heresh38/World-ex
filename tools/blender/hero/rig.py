"""Rigs a fitted hero base mesh for the game and writes the GLB that export_fbx.py turns into Unreal FBX.

The game's player contract (unreal/ShatteredOrbit: SOLocomotionAnimInstance, SOCharacter, import_assets.py):
  bones   root (not deforming) > hips > spine > chest > neck > head; chest > clavicle.X > upperarm.X > forearm.X >
          hand.X (the clavicle runs from the sternum to the shoulder joint and stays at rest in every clip: the game's
          arm IK turns it forward / up as the arm reaches, so the shoulder keeps its volume instead of caving in);
          hips > thigh.X > shin.X > foot.X; hand.X > <index|middle|ring|pinky|thumb>_01..03.X (Unreal: _L / _R)
          - the shared layout of characters.make_armature, here with the joints of our own skeleton (skeleton.py)
  clips   the body's own set from <sex>/motion.py (Idle, Walk, Run, Jump, Slide, Death, Fidget1-3), baked by gait.py;
          nothing is shared between the two bodies' motion. Written against arms hanging at the sides: every clip
          first lowers our A-pose arms
  mesh    B_body: one mesh, one material section per body region (skin__head, skin__neck, skin__chest,
          skin__midriff, skin__pelvis, skin__upperarm, skin__forearm, skin__hand, skin__thigh, skin__shin,
          skin__foot), so worn pieces can hide the regions they cover; the face_* shape keys become morph targets.
          B_eyes: both eyeballs (eye_white, eye_iris, eye_pupil), on the head bone
          B_brows: eyebrows and eyelashes as strand cards (hair__brow, hair__lash; hair.face_hair), on the head bone
  meta    the armature's `worldex` (wardrobe, defaults, regions) for wardrobe.json; no clothing yet
"""
import json
import math
import types
import numpy as np
import bpy
import bmesh
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


def add_clavicles(arm, T):
    """clavicle.X: from the sternoclavicular joint (beside the sternal notch, in front) to the shoulder joint; the
    upper arm hangs from it. No clip moves it (pose = rest), so the clips play exactly as before."""
    A = skeleton.arm(T)
    S = A["S"]
    sc = T["height"] / 1.84
    head = Vector((.024 * sc, S.y - .040 * sc, T["neck_base_z"] - .022 * sc))
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm.data.edit_bones
    for side, sx in (("L", 1), ("R", -1)):
        e = eb.new("clavicle." + side)
        e.head, e.tail = mx(head, sx), mx(S, sx)
        e.align_roll(Vector((0, 0, 1)))
        e.parent = eb["chest"]
        e.use_connect = False
        up = eb["upperarm." + side]
        up.use_connect = False
        up.parent = e
    bpy.ops.object.mode_set(mode='OBJECT')


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
    lip_tint(o, T)
    # the fit's part groups ("head", "neck", ...) would collide with bone names: drop them before skinning
    for g in list(o.vertex_groups):
        o.vertex_groups.remove(g)
    return reg


def lip_tint(o, T):
    """vertex colour (white = the skin as is): the lips a little rosier and darker round the mouth opening, so the
    mouth reads at a distance (Unreal's skin multiplies by it)"""
    from wardrobe import boundary_loops
    me = o.data
    P = np.array([v.co for v in me.vertices], np.float32)
    mouth = None
    for L in boundary_loops(o):
        c = P[L].mean(0)
        if abs(c[0]) < .01 and c[2] < T["eye_z"] - .03:
            mouth = P[L]
    col = np.ones((len(P), 4), np.float32)
    if mouth is not None:
        c = mouth.mean(0)
        hw = (mouth[:, 0].max() - mouth[:, 0].min()) / 2 + .002
        dx = (P[:, 0] - c[0]) / hw
        dz = P[:, 2] - c[2]
        dz = np.where(dz > 0, dz / (.0085 if T["sex"] == "male" else .0095), -dz / (.0105 if T["sex"] == "male" else .0115))
        r = np.sqrt(dx * dx + dz * dz)
        w = np.clip((1.15 - r) / .35, 0, 1) * (P[:, 1] < c[1] + .008)
        w = w * w * (3 - 2 * w)
        lip = np.array((.86, .62, .60) if T["sex"] == "male" else (.82, .52, .52), np.float32)
        col[:, :3] = 1 - w[:, None] * (1 - lip)
    # the eyelids drawn in shade: the upper lid's crease (an arc above the opening, higher on her), the lid rims and
    # a soft shadow in the inner corner
    if "eye_margins" in o.keys():
        import json
        for M in json.loads(o["eye_margins"]):
            M = np.array(M, np.float32)
            c = M.mean(0)
            hw = (M[:, 0].max() - M[:, 0].min()) / 2
            top = M[:, 2].max() - c[2]
            dx = (P[:, 0] - c[0]) / (hw * 1.08)
            front = P[:, 1] < c[1] + .004
            arc = c[2] + (top + (.0042 if T["sex"] == "male" else .0055)) * np.sqrt(np.clip(1 - dx * dx, 0, 1))
            crease = np.exp(-((P[:, 2] - arc) / .0012) ** 2) * (np.abs(dx) < 1.05) * front
            # distance to the lid margin: the rims
            d = np.min(np.linalg.norm(P[:, None, :] - M[None, ::2, :], axis=2), axis=1)
            rim = np.exp(-(d / .0016) ** 2) * front
            shade = np.clip(.30 * crease + .22 * rim, 0, .45)
            tone = np.array((.62, .46, .44), np.float32)          # a warm shadow, not grey
            col[:, :3] = col[:, :3] * (1 - shade[:, None] * (1 - tone))
    attr = me.color_attributes.get("Col") or me.color_attributes.new("Col", 'FLOAT_COLOR', 'POINT')
    attr.data.foreach_set("color", col.ravel())
    me.color_attributes.active_color = attr
    me.color_attributes.render_color_index = list(me.color_attributes).index(attr)


def dress_eyes(eyes, T):
    """eye_white / eye_iris (the cornea's front cap), joined into B_eyes"""
    white = skin_material("eye_white", (.86, .84, .80))
    iris = skin_material("eye_iris", (.20, .12, .06) if T["sex"] == "male" else (.22, .24, .12))   # brown / hazel
    pupil = skin_material("eye_pupil", (.008, .008, .008))
    for e in eyes:
        e.data.materials.clear()
        for m in (white, iris, pupil):
            e.data.materials.append(m)
        mw = e.matrix_world
        for p in e.data.polygons:
            n = (mw.to_3x3() @ p.normal).normalized()     # the pole looks forward: iris ~12 mm across, pupil ~4 mm
            p.material_index = 2 if n.y < -.985 else (1 if n.y < -.88 else 0)
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


def motion_clips(arm, T, sex):
    """(body, clips): the body's measurements and its own clips from tools/blender/hero/<sex>/motion.py"""
    import importlib.util
    import os
    import gait
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), sex, "motion.py")
    spec = importlib.util.spec_from_file_location(f"motion_{sex}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    body = gait.Body(arm, T, lower_arms(T))
    clips, _ = mod.clips(body)
    return body, clips


def animate(arm, T, sex, log=print):
    """bakes the body's own clips: tools/blender/hero/<sex>/motion.py (its style lives there and nowhere else) through
    the motion engine (gait.py: planted feet at the game's speeds, leg IK baked to FK)"""
    import gait
    body, clips = motion_clips(arm, T, sex)
    return gait.bake(arm, body, clips, log)


def heat_weights(o, arm, log=print):
    """heat (automatic) weights computed on a copy of the body without the eye-socket walls (fit.eye_sockets: closed
    surfaces tucked behind the lids make the heat solver fail for the whole mesh), then copied back: same vertices
    one to one, the socket walls and anything left without weights from their nearest weighted vertex"""
    from mathutils import kdtree
    n_sock = int(o.get("socket_verts", 0))
    tmp = o.copy()
    tmp.data = o.data.copy()
    bpy.context.scene.collection.objects.link(tmp)
    if tmp.data.shape_keys:
        tmp.shape_key_clear()
    bm = bmesh.new()
    bm.from_mesh(tmp.data)
    bm.verts.ensure_lookup_table()
    if n_sock:
        bmesh.ops.delete(bm, geom=bm.verts[len(bm.verts) - n_sock:], context='VERTS')
    # near-coincident vertices and sliver faces (lid corners, lip corners) stall the heat solver
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=.00015)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=.00005)
    bm.to_mesh(tmp.data)
    bm.free()
    bpy.ops.object.select_all(action='DESELECT')
    tmp.select_set(True)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.parent_set(type='ARMATURE_AUTO')
    names = [g.name for g in tmp.vertex_groups]
    W = [{names[g.group]: g.weight for g in v.groups if g.weight > 1e-4} for v in tmp.data.vertices]
    P = [v.co.copy() for v in tmp.data.vertices]
    bpy.data.objects.remove(tmp)
    for g in list(o.vertex_groups):
        o.vertex_groups.remove(g)
    groups = {nm: o.vertex_groups.new(name=nm) for nm in names}
    have = [i for i in range(len(W)) if W[i]]
    if not have:
        raise RuntimeError("heat weighting failed for the whole body")
    kd = kdtree.KDTree(len(have))
    for i in have:
        kd.insert(P[i], i)
    kd.balance()
    filled = 0
    for v in o.data.vertices:                             # (the copy's vertices moved: matched by position)
        _, i, dist = kd.find(v.co)
        filled += dist > 1e-6
        for nm, x in W[i].items():
            groups[nm].add([v.index], x, 'REPLACE')
    o.parent = arm
    mod = o.modifiers.new("Armature", 'ARMATURE')
    mod.object = arm
    log(f"rig: heat weights on {len(W)} vertices, {filled} filled from neighbours")


def rig(o, eyes, T, sex, log=print):
    import characters
    o.name = o.data.name = "B_body"
    section_body(o, T)
    b = types.SimpleNamespace(J=joints(T), s=T["height"] / 1.84)
    bpy.ops.object.select_all(action='DESELECT')
    arm = characters.make_armature(b, pole_angle=90)
    arm.name = "Armature"
    add_fingers(arm, T)
    add_clavicles(arm, T)
    for bn in arm.data.bones:
        if bn.name == "root" or bn.name.startswith(("ik_", "pole")):
            bn.use_deform = False
    # skin: automatic (heat) weights; the eyes ride the head
    heat_weights(o, arm, log)
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
    # clips: this body's own set (<sex>/motion.py), arms lowered from the A-pose first
    animate(arm, T, sex, log)
    for side in "LR":                                      # the shared armature's arm IK helpers (unused here)
        pb = arm.pose.bones["forearm." + side]
        if "IK" in pb.constraints:
            pb.constraints.remove(pb.constraints["IK"])
    arm["worldex"] = json.dumps({"wardrobe": {}, "defaults": {}, "regions": list(REGIONS)})
    # the rest pose stays the A-pose; frame 1 of Idle is what a static preview shows
    return arm


def write_glb(path):
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', export_animations=True, export_morph=True,
                              export_skins=True, export_yup=True, export_apply=False, use_selection=False,
                              export_extras=True,          # (the armature's `worldex` wardrobe metadata)
                              export_vertex_color='ACTIVE')   # (the body's lip tint)
