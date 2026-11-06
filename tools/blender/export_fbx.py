"""Converts our GLBs into Unreal-ready FBX files.

    blender --background --python tools/blender/export_fbx.py -- in.glb out_dir [--single] [--keep-location]

- One FBX per top-level asset (root object of the GLB) in out_dir, named after the root
  (--single writes the whole file as one FBX named after the GLB).
- Units: Blender metres with "FBX units scale", so Unreal imports 1 m = 100 cm without touching the import scale.
- Axes: Z up, -Y forward (Blender's native frame, written into the FBX axis system; Unreal converts on import).
- Skeletons: no leaf bones, deform bones only, every action baked (Unreal imports them as animation sequences).
- Collision: objects named UCX_* (or ending in _col / _collision) are kept, unparented next to their mesh and
  renamed UCX_<Mesh>_NN so Unreal picks them up as custom collision.
- LODs: X / X_mid / X_lod (also X_lod1, X_LOD2, ...) become one FBX LodGroup "X" with children X_LOD0, X_LOD1, X_LOD2.
- Textures embedded in the GLB are written next to the FBX in out_dir/Textures and referenced relatively.
- Assets are exported at the origin (their GLB position is ignored) unless --keep-location is given.
Writes out_dir/export_fbx.json listing every file.
"""
import json
import os
import re
import sys

import bpy
from mathutils import Matrix

LOD_RE = re.compile(r"^(?P<base>.+?)_(?:(?P<mid>mid)|(?:lod|LOD)(?P<n>\d*))$")
COL_RE = re.compile(r"^(UCX_.+|.+_(?:col|collision)(?:\.\d+)?)$", re.I)


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    flags = {a for a in argv if a.startswith("--")}
    pos = [a for a in argv if not a.startswith("--")]
    if len(pos) != 2:
        print(__doc__)
        raise SystemExit("usage: export_fbx.py -- in.glb out_dir [--single] [--keep-location]")
    return os.path.abspath(pos[0]), os.path.abspath(pos[1]), "--single" in flags, "--keep-location" in flags


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


def write_textures(out_dir):
    tex_dir = os.path.join(out_dir, "Textures")
    written = []
    for img in bpy.data.images:
        if img.source != "FILE" and not img.packed_file:
            continue
        if img.size[0] == 0:
            continue
        ext = ".jpg" if img.file_format == "JPEG" else ".png"
        if img.file_format not in ("JPEG", "PNG"):
            img.file_format = "PNG"
        os.makedirs(tex_dir, exist_ok=True)
        path = os.path.join(tex_dir, safe(os.path.splitext(img.name)[0]) + ext)
        img.filepath_raw = path
        try:
            img.save()
        except RuntimeError as e:  # image without pixel data
            print(f"[export_fbx] could not write {img.name}: {e}")
            continue
        if img.packed_file:
            img.unpack(method="REMOVE")
            img.filepath = path
        written.append(os.path.relpath(path, out_dir))
    return written


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
        path_mode="RELATIVE",
        embed_textures=False,
    )


def main():
    src, out_dir, single, keep_location = parse_args()
    os.makedirs(out_dir, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=src, merge_vertices=False)

    textures = write_textures(out_dir)
    roots = [ob for ob in bpy.context.scene.objects if ob.parent is None]
    ucx = prepare_collision(roots)
    roots = [ob for ob in bpy.context.scene.objects if ob.parent is None and not ob.name.startswith("UCX_")]

    if single:
        stem = safe(os.path.splitext(os.path.basename(src))[0])
        objects = list(bpy.context.scene.objects)
        groups = [(stem, objects, False)]
    else:
        groups = group_lods(roots)

    manifest = {"source": os.path.basename(src), "textures": textures, "assets": []}
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
        path = os.path.join(out_dir, name + ".fbx")
        export(path, objects + cols, skeletal)
        manifest["assets"].append({
            "file": os.path.basename(path),
            "kind": "skeletal" if skeletal else "static",
            "lods": sum(1 for o in objects if re.search(r"_LOD\d+$", o.name)) if is_lod else 1,
            "collision": [c.name for c in cols],
            "meshes": sum(1 for o in objects if o.type == "MESH"),
        })
        root.matrix_world = saved
        for c, m in zip(cols, saved_cols):
            c.matrix_world = m
        print(f"[export_fbx] {path} ({manifest['assets'][-1]['kind']}, lods {manifest['assets'][-1]['lods']}, ucx {len(cols)})")

    with open(os.path.join(out_dir, "export_fbx.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"[export_fbx] {len(manifest['assets'])} FBX file(s), {len(textures)} texture(s) -> {out_dir}")


main()
