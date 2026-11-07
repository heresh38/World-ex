"""Converts our GLBs into Unreal-ready FBX files.

    blender --background --python tools/blender/export_fbx.py -- in.glb out_dir [options]

Options:
  --single           the whole file as one FBX named after the GLB (default: one FBX per root object)
  --keep-location    keep each asset's GLB position (default: exported at the origin)
  --split-parts      guns: the reload parts (mag, bolt, charge, slide, pump, crane, cylinder, rounds, hatch, biomass), the
                     built-in sight a mounted optic replaces (OPTIC) and the loose reload props (x_*)
                     become their own FBX files with the origin at their pivot; <asset>.parts.json gives their rest
                     transforms and the gun's empties (muzzle, sight, rail, foregrip, ...) in Unreal mesh space
  --only=a,b,c       keep only these mesh objects (e.g. one wardrobe loadout); armatures and empties are kept
  --arms-only        skinned meshes keep only what the arm bones (upperarm / forearm / hand) mostly carry: the
                     first-person arms cut from the very body (and outfit) everyone else sees
  --per-item         players: the body (head, eyes, brows, lashes and every B_<region>, each region its own material slot
                     skin__<region> so the game can hide what clothing covers) as <stem>__Body.fbx with the clips, and
                     every wardrobe piece C_<slot>__<item> as its own <stem>__C_<slot>__<item>.fbx on the same skeleton
                     (no clips); wardrobe.json keeps the armature's `worldex` meta (labels, regions each piece hides,
                     defaults). With --arms-only: the first-person cut of each of them.
  --finger-rig=male|female
                     players: adds finger bones under hand.L / hand.R (index, middle, ring, pinky, thumb; three each,
                     <finger>_01..03.<side>) laid along the fingers anatomy.py sculpts, and moves the finger skin (body
                     and gloves) onto them, so the hands can close round a grip. The GLB (browser build) is unchanged.

- Units: static files stay in Blender metres with "FBX units scale" (import with "Convert Scene Unit"); files with an
  armature are rewritten in centimetres first (mesh, shape keys, rest bones, location keys; scene unit 1 cm) because
  Unreal converts skinned vertices but not the bind pose. export_fbx.json says which ("units": "m" | "cm").
- Axes: Z up, -Y forward (Blender's native frame, written into the FBX axis system). Unreal's importer flips Y, so a
  Blender point (x, y, z) m lands at (100x, -100y, 100z) cm in the imported mesh: models face +Y in Unreal.
- Skeletons: no leaf bones, deform bones only, every action baked (Unreal imports them as animation sequences);
  bone display shapes the glTF importer adds (Icosphere) are dropped.
- Collision: objects named UCX_* (or ending in _col / _collision) are kept, unparented next to their mesh and
  renamed UCX_<Mesh>_NN so Unreal picks them up as custom collision.
- LODs: X / X_mid / X_lod (also X_lod1, X_LOD2, ...) become one FBX LodGroup "X" with children X_LOD0, X_LOD1, X_LOD2.
- Materials: out_dir/materials.json lists every glTF material (factors, texture files, alpha mode, double sided,
  whether its meshes carry vertex colours); the images embedded in the GLB are written byte for byte to
  out_dir/Textures. The Unreal import script builds material instances from this (the FBX carries slot names only).
Writes out_dir/export_fbx.json listing every file.
"""
import json
import os
import re
import struct
import sys

import bpy
from mathutils import Matrix

LOD_RE = re.compile(r"^(?P<base>.+?)_(?:(?P<mid>mid)|(?:lod|LOD)(?P<n>\d*))$")
COL_RE = re.compile(r"^(UCX_.+|.+_(?:col|collision)(?:\.\d+)?)$", re.I)
PARTS = ("mag", "bolt", "charge", "slide", "pump", "crane", "cylinder", "rounds", "hatch", "biomass", "OPTIC")


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    flags = {a.split("=")[0]: (a.split("=", 1)[1] if "=" in a else True) for a in argv if a.startswith("--")}
    pos = [a for a in argv if not a.startswith("--")]
    if len(pos) != 2:
        print(__doc__)
        raise SystemExit("usage: export_fbx.py -- in.glb out_dir [--single] [--keep-location] [--split-parts] [--only=a,b]")
    only = set(flags["--only"].split(",")) if isinstance(flags.get("--only"), str) else None
    return os.path.abspath(pos[0]), os.path.abspath(pos[1]), flags, only


def safe(name):
    return re.sub(r"[^A-Za-z0-9_]+", "_", name).strip("_") or "Asset"


def descendants(ob):
    out = []
    for c in ob.children:
        out.append(c)
        out.extend(descendants(c))
    return out


def has_armature(ob):
    return ob.type == "ARMATURE" or any(d.type == "ARMATURE" for d in descendants(ob))


def ue_loc(v):
    """Blender metres -> Unreal mesh space centimetres (the importer flips Y)."""
    return [round(v[0] * 100.0, 4), round(-v[1] * 100.0, 4), round(v[2] * 100.0, 4)]


def ue_quat(q):
    """Blender quaternion -> Unreal mesh space [x, y, z, w] (mirror in Y: (w, x, y, z) -> (w, -x, y, -z))."""
    return [round(-q.x, 6), round(q.y, 6), round(-q.z, 6), round(q.w, 6)]


# ---------------------------------------------------------------- materials + images straight from the GLB

def read_glb(path):
    with open(path, "rb") as f:
        data = f.read()
    magic, _version, _length = struct.unpack_from("<4sII", data, 0)
    if magic != b"glTF":
        raise SystemExit(f"{path} is not a GLB")
    off, doc, binary = 12, None, b""
    while off < len(data):
        clen, ctype = struct.unpack_from("<I4s", data, off)
        chunk = data[off + 8: off + 8 + clen]
        if ctype == b"JSON":
            doc = json.loads(chunk.decode("utf-8"))
        elif ctype == b"BIN\x00":
            binary = chunk
        off += 8 + clen
    return doc, binary


def export_materials(src, out_dir):
    doc, binary = read_glb(src)
    images = doc.get("images", [])
    files = {}
    tex_dir = os.path.join(out_dir, "Textures")
    for i, img in enumerate(images):
        if "bufferView" not in img:
            continue
        bv = doc["bufferViews"][img["bufferView"]]
        raw = binary[bv.get("byteOffset", 0): bv.get("byteOffset", 0) + bv["byteLength"]]
        ext = ".jpg" if img.get("mimeType") == "image/jpeg" else ".png"
        name = safe(img.get("name") or f"image_{i}")
        os.makedirs(tex_dir, exist_ok=True)
        with open(os.path.join(tex_dir, name + ext), "wb") as f:
            f.write(raw)
        files[i] = f"Textures/{name}{ext}"

    def tex(info):
        if not info:
            return None
        t = doc["textures"][info["index"]]
        return files.get(t.get("source"))

    vc_materials = set()
    for mesh in doc.get("meshes", []):
        for prim in mesh.get("primitives", []):
            if "COLOR_0" in prim.get("attributes", {}) and "material" in prim:
                vc_materials.add(prim["material"])

    out = {}
    for i, m in enumerate(doc.get("materials", [])):
        pbr = m.get("pbrMetallicRoughness", {})
        ext = m.get("extensions", {})
        out[m.get("name", f"material_{i}")] = {
            "baseColor": pbr.get("baseColorFactor", [1, 1, 1, 1]),
            "baseColorTex": tex(pbr.get("baseColorTexture")),
            "metallic": pbr.get("metallicFactor", 1.0),
            "roughness": pbr.get("roughnessFactor", 1.0),
            "mrTex": tex(pbr.get("metallicRoughnessTexture")),
            "normalTex": tex(m.get("normalTexture")),
            "normalScale": (m.get("normalTexture") or {}).get("scale", 1.0),
            "emissive": m.get("emissiveFactor", [0, 0, 0]),
            "emissiveStrength": ext.get("KHR_materials_emissive_strength", {}).get("emissiveStrength", 1.0),
            "emissiveTex": tex(m.get("emissiveTexture")),
            "alphaMode": m.get("alphaMode", "OPAQUE"),
            "alphaCutoff": m.get("alphaCutoff", 0.5),
            "doubleSided": m.get("doubleSided", False),
            "vertexColor": i in vc_materials,
        }
    with open(os.path.join(out_dir, "materials.json"), "w") as f:
        json.dump(out, f, indent=2)
    return out, sorted(files.values())


# ---------------------------------------------------------------- scene preparation

def drop_helpers(only):
    """Removes bone display shapes and (with --only) every mesh not in the list."""
    shapes = set()
    for ob in bpy.context.scene.objects:
        if ob.type == "ARMATURE" and ob.pose:
            for pb in ob.pose.bones:
                if pb.custom_shape:
                    shapes.add(pb.custom_shape.name)
    for ob in list(bpy.context.scene.objects):
        is_shape = ob.name in shapes or (ob.type == "MESH" and ob.parent is None and not ob.data.materials and re.match(r"^Icosphere", ob.name))
        filtered = only is not None and ob.type == "MESH" and ob.name not in only
        if is_shape or filtered:
            bpy.data.objects.remove(ob, do_unlink=True)


ARM_BONES = tuple(f"{b}.{s}" for b in ("upperarm", "forearm", "hand") for s in "LR")


def keep_arms_only(threshold=0.5):
    """Deletes every vertex whose arm-bone weight is below threshold; meshes left empty are removed."""
    import bmesh
    for ob in list(bpy.context.scene.objects):
        if ob.type != "MESH" or not ob.vertex_groups:
            continue
        arm = {g.index for g in ob.vertex_groups if g.name in ARM_BONES or FINGER_RE.match(g.name)}
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        deform = bm.verts.layers.deform.active
        drop = [v for v in bm.verts if deform is None or sum(w for i, w in v[deform].items() if i in arm) < threshold]
        bmesh.ops.delete(bm, geom=drop, context="VERTS")
        left = len(bm.verts)
        bm.to_mesh(ob.data)
        bm.free()
        if left == 0:
            bpy.data.objects.remove(ob, do_unlink=True)
        else:
            print(f"[export_fbx] arms only: {ob.name} keeps {left} vertices")


# Finger layout of anatomy.Body.hand_sdf (left hand, hand-local frame: x wrist -> tip, y towards the thumb, z dorsal;
# metres before the hand scale): (knuckle x, y), phalanx lengths, radius, splay, extra curl.
FINGERS = (("index", (.093, .0245), (.046, .027, .021), .0087, .045, 0.0),
           ("middle", (.097, .0078), (.050, .031, .023), .0091, .005, .03),
           ("ring", (.093, -.009), (.047, .029, .022), .0086, -.035, .06),
           ("pinky", (.084, -.0245), (.037, .022, .019), .0075, -.08, .1))
THUMB = ((.014, .028, -.006), (.045, .051, -.017), (.071, .059, -.028), (.092, .059, -.037))
FINGER_RE = re.compile(r"^(index|middle|ring|pinky|thumb)_0[123]\.[LR]$")


def finger_chains(male):
    """{finger: (points (4, 3) in the hand frame, radius)}, the same geometry hand_sdf sculpts."""
    import numpy as np
    w = 1.04 if male else 1.0
    chains = {}
    for name, (kx, ky), segs, r, splay, extra in FINGERS:
        p = np.array([kx, ky, .0015])
        pts, ang = [p], 0.0
        for j, length in enumerate(segs):
            ang += (.16, .3, .2)[j] + extra
            dv = np.array([np.cos(ang), splay * (1 - .35 * j), -np.sin(ang)])
            p = p + dv / np.linalg.norm(dv) * length
            pts.append(p)
        chains[name] = (np.array(pts), r * w)
    chains["thumb"] = (np.array(THUMB, dtype=float), .0105 * w)
    return chains


def add_finger_rig(male):
    """Finger bones under each hand bone and the finger skin weighted onto them (see --finger-rig)."""
    import numpy as np
    arm = next((o for o in bpy.context.scene.objects if o.type == "ARMATURE"), None)
    if arm is None or "hand.L" not in arm.data.bones:
        print("[export_fbx] finger rig: no hand bones, skipped")
        return
    sc = 1.1 if male else 1.0
    chains = finger_chains(male)
    world = arm.matrix_world
    inv = world.inverted()
    frames = {}
    for side, sx in (("L", 1.0), ("R", -1.0)):
        b = arm.data.bones["hand." + side]
        wr = np.array(world @ b.head_local)
        tp = np.array(world @ b.tail_local)
        # hand_sdf works on the left hand; the right hand is its mirror image in x
        m = np.array([sx, 1.0, 1.0])
        ux = (tp - wr) * m
        ux /= np.linalg.norm(ux)
        uz = np.array([1.0, 0.0, 0.0]) - ux[0] * ux
        uz /= np.linalg.norm(uz)
        uy = np.cross(ux, uz)
        frames[side] = (wr, m, np.array([ux, uy, uz]))

    def to_world(side, q):
        wr, m, R = frames[side]
        return wr + (sc * (np.asarray(q) @ R)) * m

    # bones
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm.data.edit_bones
    from mathutils import Vector
    for side in "LR":
        _wr, m, R = frames[side]
        dorsal = Vector((R[2] * m).tolist())
        for name, (pts, _r) in chains.items():
            parent = eb["hand." + side]
            for k in range(3):
                bone = eb.new(f"{name}_0{k + 1}.{side}")
                bone.head = inv @ Vector(to_world(side, pts[k]).tolist())
                bone.tail = inv @ Vector(to_world(side, pts[k + 1]).tolist())
                bone.align_roll(inv.to_3x3() @ dorsal)
                bone.parent = parent
                bone.use_connect = False
                bone.use_deform = True
                parent = bone
    bpy.ops.object.mode_set(mode="OBJECT")

    # weights: every vertex the hand bone carries is split between the hand and the nearest finger's bones
    def smooth(a, b, x):
        t = np.clip((x - a) / max(b - a, 1e-9), 0.0, 1.0)
        return t * t * (3 - 2 * t)

    counts = {}
    for ob in bpy.context.scene.objects:
        if ob.type != "MESH" or not any(g.name.startswith("hand.") for g in ob.vertex_groups):
            continue
        mw = ob.matrix_world
        co = np.empty(len(ob.data.vertices) * 3)
        ob.data.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)
        co = (np.c_[co, np.ones(len(co))] @ np.array(mw).T)[:, :3]
        for side in "LR":
            hg = ob.vertex_groups.get("hand." + side)
            if hg is None:
                continue
            idx, wh = [], []
            for v in ob.data.vertices:
                for g in v.groups:
                    if g.group == hg.index and g.weight > 0.0:
                        idx.append(v.index)
                        wh.append(g.weight)
            if not idx:
                continue
            idx = np.array(idx)
            wh = np.array(wh)
            wr, m, R = frames[side]
            q = (((co[idx] * m) - wr * m) @ R.T) / sc       # hand-local frame of the (mirrored) left hand
            best = np.full(len(q), np.inf)
            pick = np.full(len(q), -1)
            along = np.zeros(len(q))
            names = list(chains)
            for c, name in enumerate(names):
                pts, r = chains[name]
                dist = np.full(len(q), np.inf)
                s = np.zeros(len(q))
                start = 0.0
                for k in range(3):
                    a, b = pts[k], pts[k + 1]
                    ab = b - a
                    L = np.linalg.norm(ab)
                    t = ((q - a) @ ab) / (L * L)
                    tc = np.clip(t, 0.0, 1.0)
                    d = np.linalg.norm(q - (a + np.outer(tc, ab)), axis=1)
                    sk = start + (t if k == 0 else tc) * L          # before the knuckle: negative
                    better = d < dist
                    dist = np.where(better, d, dist)
                    s = np.where(better, sk, s)
                    start += L
                surface = dist - r
                if name != "thumb":
                    surface = np.where(s < -.014, np.inf, surface)   # the palm stays on the hand
                better = surface < best
                best = np.where(better, surface, best)
                pick = np.where(better, c, pick)
                along = np.where(better, s, along)
            tol = .0075          # skin and glove lie up to this far outside the sculpted finger
            member = 1.0 - smooth(tol * .6, tol, best)
            share = {}
            for c, name in enumerate(names):
                sel = pick == c
                if not sel.any():
                    continue
                pts, _r = chains[name]
                L = np.linalg.norm(np.diff(pts, axis=0), axis=1)
                s = along[sel]
                if name == "thumb":
                    j0 = smooth(L[0] * .15, L[0] * .7, s)         # the metacarpal sits in the ball of the thumb
                    h0 = (.0, .0)
                else:
                    j0 = smooth(-.010, .008, s)
                j1 = smooth(L[0] - .005, L[0] + .005, s)
                j2 = smooth(L[0] + L[1] - .004, L[0] + L[1] + .004, s)
                parts = {f"{name}_01.{side}": j0 * (1 - j1), f"{name}_02.{side}": j1 * (1 - j2), f"{name}_03.{side}": j2}
                for bone, f in parts.items():
                    share.setdefault(bone, np.zeros(len(q)))[sel] = f
            total = sum(share.values()) if share else np.zeros(len(q))
            moved = member * np.clip(total, 0.0, 1.0)
            for bone, f in share.items():
                w = wh * member * f
                keep = w > .004
                if not keep.any():
                    continue
                g = ob.vertex_groups.get(bone) or ob.vertex_groups.new(name=bone)
                for vi, val in zip(idx[keep].tolist(), w[keep].tolist()):
                    g.add([vi], float(val), "REPLACE")
                counts[bone] = counts.get(bone, 0) + int(keep.sum())
            rest = wh * (1.0 - moved)
            for vi, val in zip(idx.tolist(), rest.tolist()):
                if val > .004:
                    hg.add([vi], float(val), "REPLACE")
                else:
                    hg.remove([vi])
    print(f"[export_fbx] finger rig: {len(chains) * 6} bones, weighted vertices "
          + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))


def action_fcurves(action):
    """F-curves of an action (Blender 4.4+ slotted actions; the legacy action.fcurves on older versions)."""
    if hasattr(action, "layers"):
        for layer in action.layers:
            for strip in layer.strips:
                for bag in getattr(strip, "channelbags", []):
                    yield from bag.fcurves
    elif hasattr(action, "fcurves"):
        yield from action.fcurves


def scene_to_centimetres():
    """Skeletal files: rewrite everything in centimetres (mesh data + shape keys, armature rest bones, object and
    bone-location animation) and set the scene unit to 1 cm, so the FBX is cm-native. Unreal's unit conversion
    scales the vertices but not the bind pose, which leaves skeletons in metres; native cm avoids any conversion."""
    k = 100.0
    scale = Matrix.Scale(k, 4)
    done = set()
    for ob in bpy.context.scene.objects:
        if ob.data is not None and ob.data.name not in done and ob.type in ("MESH", "ARMATURE"):
            done.add(ob.data.name)
            if ob.type == "MESH":
                ob.data.transform(scale, shape_keys=True)
            else:
                ob.data.transform(scale)
        ob.location = ob.location * k
        if ob.type == "EMPTY":
            ob.empty_display_size *= k
    for action in bpy.data.actions:
        for fc in action_fcurves(action):
            if fc.data_path.endswith("location"):
                for kp in fc.keyframe_points:
                    kp.co[1] *= k
                    kp.handle_left[1] *= k
                    kp.handle_right[1] *= k
                fc.update()
    us = bpy.context.scene.unit_settings
    us.system = "METRIC"
    us.scale_length = 0.01


def prepare_collision(roots):
    """Unparents collision meshes and names them UCX_<root>_NN; returns {root object: [ucx objects]}."""
    by_root = {}
    for root in roots:
        cols = [d for d in [root] + descendants(root) if d.type == "MESH" and COL_RE.match(d.name)]
        named = []
        for i, ob in enumerate(cols):
            mw = ob.matrix_world.copy()
            ob.parent = None
            ob.matrix_world = mw
            ob.name = f"UCX_{safe(root.name)}_{i:02d}"
            ob.data.materials.clear()
            named.append(ob)
        if named:
            by_root[root] = named
    return by_root


def group_lods(roots):
    """Returns a list of (name, [objects to export], is_lod_group)."""
    names = {r.name: r for r in roots}
    tiers = {}
    for r in roots:
        m = LOD_RE.match(r.name)
        if m and m.group("base") in names:
            level = 1 if m.group("mid") else (int(m.group("n")) if m.group("n") else 2)
            tiers.setdefault(m.group("base"), {})[level] = r
    for base in tiers:
        tiers[base][0] = names[base]

    members_of = {}  # base object -> sorted tier objects
    for base, levels in tiers.items():
        members_of[names[base]] = [levels[k] for k in sorted(levels)]
    in_group = {ob for tiers_list in members_of.values() for ob in tiers_list}

    groups = []
    for r in roots:
        if r in members_of:
            base = safe(r.name)
            empty = bpy.data.objects.new(f"LOD_{base}", None)
            bpy.context.scene.collection.objects.link(empty)
            empty["fbx_type"] = "LodGroup"
            empty.matrix_world = Matrix.Translation(r.matrix_world.translation)
            members = [empty]
            for lvl, ob in enumerate(members_of[r]):
                rot_scale = ob.matrix_world.to_3x3().to_4x4()
                ob.parent = empty
                ob.matrix_parent_inverse = Matrix.Identity(4)
                ob.matrix_basis = rot_scale
                ob.name = f"{base}_LOD{lvl}"
                members += [ob] + descendants(ob)
            groups.append((base, members, True))
        elif r not in in_group:
            groups.append((safe(r.name), [r] + descendants(r), False))
    return groups


def mesh_materials(objects):
    names = []
    for ob in objects:
        if ob.type == "MESH":
            for m in ob.data.materials:
                if m and m.name not in names:
                    names.append(m.name)
    return names


def export(path, objects, skeletal):
    bpy.ops.object.select_all(action="DESELECT")
    for ob in objects:
        ob.hide_set(False)
        ob.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.export_scene.fbx(
        filepath=path,
        use_selection=True,
        object_types={"EMPTY", "MESH", "ARMATURE", "OTHER"},
        use_custom_props=True,
        global_scale=1.0,
        apply_unit_scale=True,
        apply_scale_options="FBX_SCALE_UNITS",
        axis_forward="-Y",
        axis_up="Z",
        use_space_transform=True,
        bake_space_transform=False,
        use_mesh_modifiers=True,
        mesh_smooth_type="FACE",
        use_tspace=True,
        use_triangles=False,
        add_leaf_bones=False,
        primary_bone_axis="Y",
        secondary_bone_axis="X",
        use_armature_deform_only=True,
        armature_nodetype="NULL",
        bake_anim=skeletal,
        bake_anim_use_all_actions=skeletal,
        bake_anim_use_nla_strips=False,
        bake_anim_force_startend_keying=True,
        bake_anim_simplify_factor=0.0,
        path_mode="STRIP",
        embed_textures=False,
    )


def split_parts(name, root, out_dir):
    """Exports each reload part at its own pivot; returns the parts.json dict (Unreal mesh space, root = origin)."""
    info = {"parts": {}, "sockets": {}}
    inv = root.matrix_world.inverted()
    for ob in descendants(root):
        rel = inv @ ob.matrix_world
        loc, rot, _scale = rel.decompose()
        if ob.type == "EMPTY" and ob.name not in PARTS:
            info["sockets"][ob.name] = {"loc": ue_loc(loc), "rot": ue_quat(rot)}
    for part in PARTS + tuple(o.name for o in descendants(root) if o.name.startswith("x_")):
        ob = next((o for o in descendants(root) if o.name == part), None)
        if ob is None or ob.type != "MESH":
            continue
        rel = inv @ ob.matrix_world
        loc, rot, _scale = rel.decompose()
        parent = ob.parent.name if ob.parent is not root else ""
        saved_parent, saved = ob.parent, ob.matrix_world.copy()
        kids = [c for c in ob.children]
        kid_saved = [(c, c.matrix_world.copy()) for c in kids]
        ob.parent = None
        ob.matrix_world = Matrix.Identity(4)
        for c, m in kid_saved:  # nested parts (crane > cylinder) stay with their own files
            c.parent = None
            c.matrix_world = m
        fname = f"{name}__{safe(part)}.fbx"
        export(os.path.join(out_dir, fname), [ob], False)
        info["parts"][part] = {"file": fname, "loc": ue_loc(loc), "rot": ue_quat(rot), "parent": parent,
                               "materials": mesh_materials([ob])}
        ob.parent = saved_parent
        ob.matrix_world = saved
        for c, m in kid_saved:
            c.parent = ob
            c.matrix_world = m
        ob.hide_set(True)  # left out of the body export
    return info


def export_per_item(src, out_dir, textures, with_clips=True):
    """--per-item: the body and each wardrobe piece as their own skeletal FBX on one skeleton (see the docstring)."""
    arm = next(o for o in bpy.context.scene.objects if o.type == "ARMATURE")
    meta = json.loads(arm["worldex"]) if "worldex" in arm.keys() else {}
    with open(os.path.join(out_dir, "wardrobe.json"), "w") as f:
        json.dump({"wardrobe": meta.get("wardrobe", {}), "defaults": meta.get("defaults", {}), "regions": meta.get("regions", [])}, f, indent=1)
    stem = safe(os.path.splitext(os.path.basename(src))[0])
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    body = [o for o in meshes if o.name.split(".")[0].startswith("B_")]
    # one material slot per body region: the game hides the regions the worn pieces cover
    for o in body:
        region = o.name.split(".")[0][2:]
        for i, slot in enumerate(o.material_slots):
            if slot.material and slot.material.name.split(".")[0] == "skin":
                m = slot.material.copy()
                m.name = "skin__" + region
                o.material_slots[i].material = m
    groups = [("Body", body)] + [(o.name.split(".")[0], [o]) for o in meshes if o.name.split(".")[0].startswith("C_")]
    manifest = {"source": os.path.basename(src), "textures": textures, "materials": "materials.json", "units": "cm",
                "per_item": True, "assets": []}
    for name, objs in groups:
        if not objs:
            continue
        file = f"{stem}__{name}.fbx"
        clips = with_clips and name == "Body"
        export(os.path.join(out_dir, file), [arm] + objs, clips)
        entry = {"file": file, "kind": "skeletal", "name": name, "materials": mesh_materials(objs),
                 "actions": [a.name for a in bpy.data.actions] if clips else []}
        if name.startswith("C_"):
            slot, item = name[2:].split("__", 1)
            entry.update({"slot": slot, "item": item})
        manifest["assets"].append(entry)
        print(f"[export_fbx] {file} ({len(objs)} mesh{'es' if len(objs) > 1 else ''}{', clips' if clips else ''})")
    with open(os.path.join(out_dir, "export_fbx.json"), "w") as f:
        json.dump(manifest, f, indent=2)


def main():
    src, out_dir, flags, only = parse_args()
    single, keep_location, do_split = "--single" in flags, "--keep-location" in flags, "--split-parts" in flags
    os.makedirs(out_dir, exist_ok=True)
    materials, textures = export_materials(src, out_dir)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=src, merge_vertices=False)
    drop_helpers(only)
    if isinstance(flags.get("--finger-rig"), str):
        add_finger_rig(flags["--finger-rig"] != "female")
    if "--arms-only" in flags:
        keep_arms_only()
    skeletal_file = any(o.type == "ARMATURE" for o in bpy.context.scene.objects)
    if "--per-item" in flags:
        scene_to_centimetres()
        export_per_item(src, out_dir, textures, with_clips="--arms-only" not in flags)
        return
    if skeletal_file:
        scene_to_centimetres()

    roots = [ob for ob in bpy.context.scene.objects if ob.parent is None]
    ucx = prepare_collision(roots)
    roots = [ob for ob in bpy.context.scene.objects if ob.parent is None and not ob.name.startswith("UCX_")]

    if single:
        stem = safe(os.path.splitext(os.path.basename(src))[0])
        groups = [(stem, list(bpy.context.scene.objects), False)]
    else:
        groups = group_lods(roots)

    manifest = {"source": os.path.basename(src), "textures": textures, "materials": "materials.json",
                "units": "cm" if skeletal_file else "m", "assets": []}
    for name, objects, is_lod in groups:
        root = objects[0]
        cols = [] if single else [c for o in objects for c in ucx.get(o, [])]
        saved = root.matrix_world.copy()
        saved_cols = [c.matrix_world.copy() for c in cols]
        if not keep_location and not single:
            shift = Matrix.Translation(-saved.translation)
            root.matrix_world = shift @ saved
            for c in cols:
                c.matrix_world = shift @ c.matrix_world
        skeletal = any(has_armature(o) for o in objects)
        if name.lower().startswith("armature"):
            name = safe(os.path.splitext(os.path.basename(src))[0])
        entry = {"file": name + ".fbx", "kind": "skeletal" if skeletal else "static"}
        if do_split and not skeletal:
            entry["parts"] = f"{name}.parts.json"
            info = split_parts(name, root, out_dir)
            with open(os.path.join(out_dir, entry["parts"]), "w") as f:
                json.dump(info, f, indent=2)
        body = [o for o in objects if not o.hide_get()]
        export(os.path.join(out_dir, entry["file"]), body + cols, skeletal)
        entry.update({
            "lods": sum(1 for o in objects if re.search(r"_LOD\d+$", o.name)) if is_lod else 1,
            "collision": [c.name for c in cols],
            "meshes": sum(1 for o in body if o.type == "MESH"),
            "materials": mesh_materials(body),
            "actions": [a.name for a in bpy.data.actions] if skeletal else [],
        })
        manifest["assets"].append(entry)
        for o in objects:
            o.hide_set(False)
        root.matrix_world = saved
        for c, m in zip(cols, saved_cols):
            c.matrix_world = m
        print(f"[export_fbx] {entry['file']} ({entry['kind']}, lods {entry['lods']}, ucx {len(cols)}"
              f"{', parts ' + entry['parts'] if 'parts' in entry else ''})")

    with open(os.path.join(out_dir, "export_fbx.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"[export_fbx] {len(manifest['assets'])} FBX file(s), {len(textures)} texture(s), "
          f"{len(materials)} material(s) -> {out_dir}")


main()
