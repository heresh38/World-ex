"""Converts our GLBs into Unreal-ready FBX files.

    blender --background --python tools/blender/export_fbx.py -- in.glb out_dir [options]

Options:
  --single           the whole file as one FBX named after the GLB (default: one FBX per root object)
  --keep-location    keep each asset's GLB position (default: exported at the origin)
  --split-parts      guns: the reload parts (mag, bolt, charge, slide, pump, crane, cylinder, rounds, hatch, biomass)
                     become their own FBX files with the origin at their pivot; <asset>.parts.json gives their rest
                     transforms and the gun's empties (muzzle, sight, rail, foregrip, ...) in Unreal mesh space
  --only=a,b,c       keep only these mesh objects (e.g. one wardrobe loadout); armatures and empties are kept
  --arms-only        skinned meshes keep only what the arm bones (upperarm / forearm / hand) mostly carry: the
                     first-person arms cut from the very body (and outfit) everyone else sees

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
PARTS = ("mag", "bolt", "charge", "slide", "pump", "crane", "cylinder", "rounds", "hatch", "biomass")


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
        arm = {g.index for g in ob.vertex_groups if g.name in ARM_BONES}
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


def main():
    src, out_dir, flags, only = parse_args()
    single, keep_location, do_split = "--single" in flags, "--keep-location" in flags, "--split-parts" in flags
    os.makedirs(out_dir, exist_ok=True)
    materials, textures = export_materials(src, out_dir)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=src, merge_vertices=False)
    drop_helpers(only)
    if "--arms-only" in flags:
        keep_arms_only()
    skeletal_file = any(o.type == "ARMATURE" for o in bpy.context.scene.objects)
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
