"""Imports the Blender-built assets (unreal/ShatteredOrbit/SourceArt, written by tools/blender/export_unreal.sh).

Creates:
  /Game/Materials/M_SOStandard           master PBR material (glTF semantics: base x tint x vertex colour, MR map G=rough B=metal)
  /Game/Materials/T_White, T_WhiteMask, T_FlatNormal   our own 4x4 default textures
  /Game/Characters/PlayerMale/SK_PlayerMale (+ skeleton, physics asset, Anims/A_PlayerMale_<Clip>, MI_*)
  /Game/Characters/Stalker/SK_Stalker      (+ Anims/A_Stalker_<Clip>, hx_* flesh textures from assets/textures)
  /Game/Weapons/Rifle/SM_Rifle, SM_Rifle_mag, SM_Rifle_bolt, DA_Rifle (USOWeaponData with data.js stats)
  /Game/Weapons/Arms/SM_ArmLeft, SM_ArmRight
  /Game/FX/SM_FX_Quad, SM_FX_Streak, SM_FX_Star, M_SOFx (+ MI_FxGlow/Streak/Flash/Smoke), M_SOBulletHole
  /Game/Audio/S_* (tools/audio/sfx_synth.py)

Headless:
    UnrealEditor-Cmd.exe <path>/ShatteredOrbit.uproject -run=pythonscript -script="<path>/Content/Python/import_assets.py" -unattended -nullrhi
"""

import json
import os
import re
import struct
import zlib

import unreal

PROJECT = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
SOURCE = os.path.join(PROJECT, "SourceArt")
REPO_TEXTURES = os.path.normpath(os.path.join(PROJECT, "..", "..", "assets", "textures"))

tools = unreal.AssetToolsHelpers.get_asset_tools()
eal = unreal.EditorAssetLibrary
mel = unreal.MaterialEditingLibrary

# Weapon numbers come from Data/game_data.json (node tools/unreal/export_game_data.mjs, from src/game/data.js).

# Creature flesh: the GLBs ship without images; enemies.js applies these hx_* sets by material name.
FLESH = {"alien_skin": "hx_flesh", "alien_hide": "hx_skin", "alien_plate": "hx_chitin", "alien_bone": "hx_bone", "alien_sac": "hx_sac"}

SKIN_TONE = (0.55, 0.32, 0.22)


def log(msg):
    unreal.log("[import_assets] " + msg)


def ensure_dir(path):
    if not eal.does_directory_exist(path):
        eal.make_directory(path)


def base_slot(name):
    return re.sub(r"[._]\d{3}$", "", str(name))


# ---------------------------------------------------------------- default textures (ours)

def write_png(path, rgba, size=4):
    raw = b"".join(b"\x00" + bytes(rgba) * size for _ in range(size))

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)) \
        + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(png)


def import_texture(file_path, dest, name, kind):
    """kind: color | mask | normal."""
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", file_path)
    task.set_editor_property("destination_path", dest)
    task.set_editor_property("destination_name", name)
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("save", False)
    tools.import_asset_tasks([task])
    tex = unreal.load_asset(f"{dest}/{name}")
    if tex is None:
        raise RuntimeError(f"texture import failed: {file_path}")
    if kind == "normal":
        tex.set_editor_property("srgb", False)
        tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_NORMALMAP)
        tex.set_editor_property("flip_green_channel", True)  # glTF normal maps are OpenGL (+Y), Unreal is DirectX
    elif kind == "mask":
        tex.set_editor_property("srgb", False)
        tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_MASKS)
    eal.save_loaded_asset(tex, only_if_is_dirty=False)
    return tex


def default_textures():
    ensure_dir("/Game/Materials")
    folder = os.path.join(SOURCE, "_Defaults")
    write_png(os.path.join(folder, "T_White.png"), (255, 255, 255, 255))
    write_png(os.path.join(folder, "T_WhiteMask.png"), (255, 255, 255, 255))
    write_png(os.path.join(folder, "T_FlatNormal.png"), (128, 128, 255, 255))
    write_png(os.path.join(folder, "T_Clear.png"), (255, 255, 255, 0))
    return {
        "clear": import_texture(os.path.join(folder, "T_Clear.png"), "/Game/Materials", "T_Clear", "color"),
        "white": import_texture(os.path.join(folder, "T_White.png"), "/Game/Materials", "T_White", "color"),
        "mask": import_texture(os.path.join(folder, "T_WhiteMask.png"), "/Game/Materials", "T_WhiteMask", "mask"),
        "normal": import_texture(os.path.join(folder, "T_FlatNormal.png"), "/Game/Materials", "T_FlatNormal", "normal"),
    }


# ---------------------------------------------------------------- master material

def master_material(defaults):
    path = "/Game/Materials/M_SOStandard"
    if eal.does_asset_exist(path):
        mat = eal.load_asset(path)
        mel.delete_all_material_expressions(mat)
    else:
        mat = tools.create_asset("M_SOStandard", "/Game/Materials", unreal.Material, unreal.MaterialFactoryNew())
    mat.set_editor_property("used_with_skeletal_mesh", True)
    mat.set_editor_property("used_with_morph_targets", True)

    def tex_param(name, sampler, tex, x, y):
        e = mel.create_material_expression(mat, unreal.MaterialExpressionTextureSampleParameter2D, x, y)
        e.set_editor_property("parameter_name", name)
        e.set_editor_property("texture", tex)
        e.set_editor_property("sampler_type", sampler)
        return e

    def scalar(name, value, x, y):
        e = mel.create_material_expression(mat, unreal.MaterialExpressionScalarParameter, x, y)
        e.set_editor_property("parameter_name", name)
        e.set_editor_property("default_value", value)
        return e

    def vector(name, value, x, y):
        e = mel.create_material_expression(mat, unreal.MaterialExpressionVectorParameter, x, y)
        e.set_editor_property("parameter_name", name)
        e.set_editor_property("default_value", unreal.LinearColor(*value))
        return e

    def mul(a, a_out, b, b_out, x, y):
        e = mel.create_material_expression(mat, unreal.MaterialExpressionMultiply, x, y)
        mel.connect_material_expressions(a, a_out, e, "A")
        mel.connect_material_expressions(b, b_out, e, "B")
        return e

    S = unreal.MaterialSamplerType
    base = tex_param("BaseColorTex", S.SAMPLERTYPE_COLOR, defaults["white"], -900, -300)
    tint = vector("BaseColorTint", (1, 1, 1, 1), -900, -80)
    vcol = mel.create_material_expression(mat, unreal.MaterialExpressionVertexColor, -900, 60)
    vamt = scalar("VertexColorAmount", 0.0, -900, 200)
    vlerp = mel.create_material_expression(mat, unreal.MaterialExpressionLinearInterpolate, -650, 80)
    vlerp.set_editor_property("const_a", 1.0)
    mel.connect_material_expressions(vcol, "", vlerp, "B")
    mel.connect_material_expressions(vamt, "", vlerp, "Alpha")
    tinted = mul(base, "RGB", tint, "", -650, -250)
    colour = mul(tinted, "", vlerp, "", -400, -200)
    mel.connect_material_property(colour, "", unreal.MaterialProperty.MP_BASE_COLOR)
    mel.connect_material_property(base, "A", unreal.MaterialProperty.MP_OPACITY_MASK)

    mr = tex_param("MRTex", S.SAMPLERTYPE_MASKS, defaults["mask"], -900, 340)
    metal = mul(mr, "B", scalar("Metallic", 0.0, -900, 560), "", -650, 360)
    rough = mul(mr, "G", scalar("Roughness", 0.5, -900, 640), "", -650, 480)
    mel.connect_material_property(metal, "", unreal.MaterialProperty.MP_METALLIC)
    mel.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)

    normal = tex_param("NormalTex", S.SAMPLERTYPE_NORMAL, defaults["normal"], -900, 760)
    mel.connect_material_property(normal, "RGB", unreal.MaterialProperty.MP_NORMAL)

    emis = tex_param("EmissiveTex", S.SAMPLERTYPE_COLOR, defaults["white"], -900, 1000)
    ecol = vector("EmissiveColor", (0, 0, 0, 1), -900, 1220)
    estr = scalar("EmissiveStrength", 1.0, -900, 1360)
    e1 = mul(emis, "RGB", ecol, "", -650, 1060)
    e2 = mul(e1, "", estr, "", -400, 1100)
    mel.connect_material_property(e2, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)

    mel.recompile_material(mat)
    eal.save_loaded_asset(mat, only_if_is_dirty=False)
    log("master material ready")
    return mat


def make_instance(master, dest, name, m, tex, extra=None):
    """m: one materials.json entry; tex: {relative file or hx name: texture asset}."""
    path = f"{dest}/MI_{name}"
    if eal.does_asset_exist(path):
        mi = eal.load_asset(path)
    else:
        mi = tools.create_asset(f"MI_{name}", dest, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    mel.set_material_instance_parent(mi, master)
    extra = extra or {}
    base = extra.get("tint") or m.get("baseColor", [1, 1, 1, 1])
    mel.set_material_instance_vector_parameter_value(mi, "BaseColorTint", unreal.LinearColor(base[0], base[1], base[2], 1.0))
    mel.set_material_instance_scalar_parameter_value(mi, "Metallic", float(extra.get("metallic", m.get("metallic", 1.0))))
    mel.set_material_instance_scalar_parameter_value(mi, "Roughness", float(extra.get("roughness", m.get("roughness", 1.0))))
    mel.set_material_instance_scalar_parameter_value(mi, "VertexColorAmount", 1.0 if m.get("vertexColor") else 0.0)
    em = m.get("emissive", [0, 0, 0])
    mel.set_material_instance_vector_parameter_value(mi, "EmissiveColor", unreal.LinearColor(em[0], em[1], em[2], 1.0))
    mel.set_material_instance_scalar_parameter_value(mi, "EmissiveStrength", float(m.get("emissiveStrength", 1.0)) * (4.0 if any(em) else 1.0))
    for param, key in (("BaseColorTex", "baseColorTex"), ("MRTex", "mrTex"), ("NormalTex", "normalTex"), ("EmissiveTex", "emissiveTex")):
        file = extra.get(key) or m.get(key)
        if file and file in tex:
            mel.set_material_instance_texture_parameter_value(mi, param, tex[file])

    overrides = mi.get_editor_property("base_property_overrides")
    if m.get("alphaMode") in ("MASK", "BLEND"):
        overrides.set_editor_property("override_blend_mode", True)
        overrides.set_editor_property("blend_mode", unreal.BlendMode.BLEND_MASKED)
        overrides.set_editor_property("override_opacity_mask_clip_value", True)
        overrides.set_editor_property("opacity_mask_clip_value", float(m.get("alphaCutoff", 0.5)) if m.get("alphaMode") == "MASK" else 0.35)
    if m.get("doubleSided") or m.get("alphaMode") == "BLEND":
        overrides.set_editor_property("override_two_sided", True)
        overrides.set_editor_property("two_sided", True)
    mi.set_editor_property("base_property_overrides", overrides)
    mel.update_material_instance(mi)
    eal.save_loaded_asset(mi, only_if_is_dirty=False)
    return mi


# ---------------------------------------------------------------- FBX

def import_fbx(fbx, dest, name, skeletal):
    ui = unreal.FbxImportUI()
    ui.set_editor_property("import_mesh", True)
    ui.set_editor_property("import_textures", False)
    ui.set_editor_property("import_materials", False)
    ui.set_editor_property("import_as_skeletal", skeletal)
    ui.set_editor_property("automated_import_should_detect_type", False)
    ui.set_editor_property("mesh_type_to_import", unreal.FBXImportType.FBXIT_SKELETAL_MESH if skeletal else unreal.FBXImportType.FBXIT_STATIC_MESH)
    if skeletal:
        ui.set_editor_property("import_animations", True)
        ui.set_editor_property("create_physics_asset", True)
        sk = ui.get_editor_property("skeletal_mesh_import_data")
        sk.set_editor_property("import_morph_targets", True)
        # Skeletal FBX are written in cm by export_fbx.py (Unreal converts skinned vertices but not the bind pose).
        sk.set_editor_property("convert_scene_unit", False)
        sk.set_editor_property("normal_import_method", unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS_AND_TANGENTS)
        anim = ui.get_editor_property("anim_sequence_import_data")
        anim.set_editor_property("animation_length", unreal.FBXAnimationLengthImportType.FBXALIT_EXPORTED_TIME)
        anim.set_editor_property("import_bone_tracks", True)
        anim.set_editor_property("convert_scene_unit", False)
    else:
        sm = ui.get_editor_property("static_mesh_import_data")
        sm.set_editor_property("combine_meshes", True)
        sm.set_editor_property("convert_scene_unit", True)  # FBX metres (UnitScaleFactor 100) -> cm
        sm.set_editor_property("auto_generate_collision", False)
        sm.set_editor_property("normal_import_method", unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS_AND_TANGENTS)
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", fbx)
    task.set_editor_property("destination_path", dest)
    task.set_editor_property("destination_name", name)
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("save", False)
    task.set_editor_property("options", ui)
    tools.import_asset_tasks([task])
    paths = list(task.get_editor_property("imported_object_paths"))
    if not paths:
        raise RuntimeError(f"FBX import failed: {fbx}")
    return [unreal.load_asset(p) for p in paths]


def assign_materials(mesh, instances):
    missing = []
    if isinstance(mesh, unreal.SkeletalMesh):
        mats = list(mesh.get_editor_property("materials"))
        for slot in mats:
            mi = instances.get(base_slot(slot.get_editor_property("material_slot_name")))
            if mi:
                slot.set_editor_property("material_interface", mi)
            else:
                missing.append(str(slot.get_editor_property("material_slot_name")))
        mesh.set_editor_property("materials", mats)
    else:
        for i, slot in enumerate(mesh.get_editor_property("static_materials")):
            mi = instances.get(base_slot(slot.get_editor_property("material_slot_name")))
            if mi:
                mesh.set_material(i, mi)
            else:
                missing.append(str(slot.get_editor_property("material_slot_name")))
    if missing:
        log(f"  {mesh.get_name()}: no material for slots {missing}")
    eal.save_loaded_asset(mesh, only_if_is_dirty=False)


def import_textures_for(src_dir, materials, dest, used=None):
    tex = {}
    for key, m in materials.items():
        if used is not None and base_slot(key) not in used:
            continue
        for key, kind in (("baseColorTex", "color"), ("emissiveTex", "color"), ("mrTex", "mask"), ("normalTex", "normal")):
            f = m.get(key)
            if f and f not in tex:
                tex[f] = import_texture(os.path.join(src_dir, f), dest, "T_" + os.path.splitext(os.path.basename(f))[0], kind)
    return tex


def fix_clip_units(anim):
    """The legacy importer converts the mesh to cm but leaves Blender clips' bone translations in metres:
    scale every translation key by 100 (only while they are still metre-sized)."""
    lib = unreal.AnimationLibrary
    names = list(lib.get_animation_track_names(anim))
    biggest = max((lib.get_bone_pose_for_frame(anim, b, 0, False).translation.length() for b in names), default=0.0)
    if biggest <= 0.0 or biggest > 5.0:
        return False
    frames = lib.get_num_frames(anim)
    controller = anim.get_editor_property("controller")
    for bone in names:
        pos, rot, scl = [], [], []
        for f in range(frames + 1):
            t = lib.get_bone_pose_for_frame(anim, bone, f, False)
            p = t.translation
            pos.append(unreal.Vector(p.x * 100.0, p.y * 100.0, p.z * 100.0))
            rot.append(t.rotation)
            scl.append(t.scale3d)
        controller.set_bone_track_keys(bone, pos, rot, scl, False)
    return True


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def character(src, dest, mesh_name, clip_prefix, master, extra_for=None, flesh=False):
    manifest = load_json(os.path.join(src, "export_fbx.json"))
    materials = load_json(os.path.join(src, "materials.json"))
    asset = manifest["assets"][0]
    ensure_dir(dest)
    used = {base_slot(n) for n in asset["materials"]}
    tex = import_textures_for(src, materials, dest + "/Textures", used) if any(
        m.get(k) for m in materials.values() for k in ("baseColorTex", "mrTex", "normalTex", "emissiveTex")) else {}
    if flesh:
        for set_name in sorted(set(FLESH.values())):
            for suffix, kind in (("_c", "color"), ("_m", "mask"), ("_n", "normal")):
                f = os.path.join(REPO_TEXTURES, set_name + suffix + ".jpg")
                tex[set_name + suffix] = import_texture(f, dest + "/Textures", "T_" + set_name + suffix, kind)
    instances = {}
    for name in asset["materials"]:
        key = base_slot(name)
        m = materials.get(key) or materials.get(name) or {}
        extra = extra_for(key, m) if extra_for else None
        instances[key] = make_instance(master, dest, key, m, tex, extra)

    objs = import_fbx(os.path.join(src, asset["file"]), dest, mesh_name, True)
    mesh = next(o for o in objs if isinstance(o, unreal.SkeletalMesh))
    assign_materials(mesh, instances)

    # Clips: <mesh>_Anim_<take> -> Anims/<clip_prefix><Clip>
    ensure_dir(dest + "/Anims")
    actions = sorted(asset.get("actions", []), key=len, reverse=True)
    renamed = []
    for path in eal.list_assets(dest, recursive=False, include_folder=False):
        obj = eal.load_asset(path)
        if not isinstance(obj, unreal.AnimSequence):
            continue
        name = obj.get_name()
        clip = next((a for a in actions if name.endswith(a)), None)
        if not clip:
            continue
        target = f"{dest}/Anims/{clip_prefix}{clip}"
        if eal.does_asset_exist(target):
            eal.delete_asset(target)
        if eal.rename_asset(path, target):
            renamed.append(clip)
            fix_clip_units(eal.load_asset(target))
    for path in eal.list_assets(dest + "/Anims", recursive=False, include_folder=False):
        eal.save_asset(path, only_if_is_dirty=False)
    eal.save_directory(dest, only_if_is_dirty=False, recursive=True)
    log(f"{mesh_name}: {len(instances)} materials, clips {sorted(renamed)}")
    return mesh


def player_arms(master):
    """First-person arms: the body's own sleeves / gloves / shoulder plates (export_fbx.py --arms-only) on the body's
    skeleton, so the same clips and arm IK drive them and the hands match what everyone else sees."""
    src = os.path.join(SOURCE, "Characters", "PlayerMaleArms")
    dest = "/Game/Characters/PlayerMale"
    body = eal.load_asset(dest + "/SK_PlayerMale")
    if not body or not os.path.isdir(src):
        log("SK_PlayerMaleArms: skipped (needs SK_PlayerMale and SourceArt/Characters/PlayerMaleArms)")
        return None
    manifest = load_json(os.path.join(src, "export_fbx.json"))
    materials = load_json(os.path.join(src, "materials.json"))
    asset = manifest["assets"][0]
    used = {base_slot(n) for n in asset["materials"]}
    tex = import_textures_for(src, materials, dest + "/Textures", used)
    instances = {}
    for name in asset["materials"]:
        key = base_slot(name)
        m = materials.get(key) or materials.get(name) or {}
        instances[key] = make_instance(master, dest, key, m, tex, player_extra(key, m))

    ui = unreal.FbxImportUI()
    ui.set_editor_property("import_mesh", True)
    ui.set_editor_property("import_textures", False)
    ui.set_editor_property("import_materials", False)
    ui.set_editor_property("import_as_skeletal", True)
    ui.set_editor_property("automated_import_should_detect_type", False)
    ui.set_editor_property("mesh_type_to_import", unreal.FBXImportType.FBXIT_SKELETAL_MESH)
    ui.set_editor_property("skeleton", body.get_editor_property("skeleton"))
    ui.set_editor_property("import_animations", False)
    ui.set_editor_property("create_physics_asset", False)
    sk = ui.get_editor_property("skeletal_mesh_import_data")
    sk.set_editor_property("convert_scene_unit", False)
    sk.set_editor_property("normal_import_method", unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS_AND_TANGENTS)
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", os.path.join(src, asset["file"]))
    task.set_editor_property("destination_path", dest)
    task.set_editor_property("destination_name", "SK_PlayerMaleArms")
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("save", False)
    task.set_editor_property("options", ui)
    tools.import_asset_tasks([task])
    mesh = next((unreal.load_asset(p) for p in task.get_editor_property("imported_object_paths")
                 if isinstance(unreal.load_asset(p), unreal.SkeletalMesh)), None)
    if not mesh:
        raise RuntimeError("SK_PlayerMaleArms import failed")
    assign_materials(mesh, instances)
    eal.save_directory(dest, only_if_is_dirty=False, recursive=False)
    log(f"SK_PlayerMaleArms: {len(instances)} materials on the body skeleton")
    return mesh


def stalker_extra(key, m):
    if key in FLESH:
        s = FLESH[key]
        return {"tint": [0.82 * 0.8, 0.8 * 0.8, 0.78 * 0.8], "baseColorTex": s + "_c", "mrTex": s + "_m", "normalTex": s + "_n",
                "metallic": 1.0, "roughness": 1.0}
    return None


def player_extra(key, m):
    if key == "skin":
        return {"tint": list(SKIN_TONE)}
    return None


# ---------------------------------------------------------------- weapons + loot (stage 5)

GAME_DATA = os.path.normpath(os.path.join(PROJECT, "Data", "game_data.json"))
WEAPON_TEX = "/Game/Weapons/Textures"
_TEX_DONE = {}


def weapon_dir(model):
    """gun_bio_spitter -> BioSpitter (SourceArt/Weapons/<dir>, /Game/Weapons/<dir>)."""
    return "".join(p.capitalize() for p in model[len("gun_"):].split("_"))


def hex_color(h, default=(1.0, 0.78, 0.45)):
    if not h or not h.startswith("#"):
        return unreal.LinearColor(*default, 1.0)
    r, g, b = (int(h[i:i + 2], 16) / 255.0 for i in (1, 3, 5))
    srgb = lambda c: c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return unreal.LinearColor(srgb(r), srgb(g), srgb(b), 1.0)


def shared_textures(src, materials):
    """Weapon textures share file names across guns (wpn_steel_c.jpg ...): import each once into /Game/Weapons/Textures."""
    ensure_dir(WEAPON_TEX)
    out = {}
    for m in materials.values():
        for key, kind in (("baseColorTex", "color"), ("emissiveTex", "color"), ("mrTex", "mask"), ("normalTex", "normal")):
            f = m.get(key)
            if not f:
                continue
            base = os.path.splitext(os.path.basename(f))[0]
            if base not in _TEX_DONE:
                _TEX_DONE[base] = import_texture(os.path.join(src, f), WEAPON_TEX, "T_" + base, kind)
            out[f] = _TEX_DONE[base]
    return out


def gun_instances(master, src, dest, materials, clear):
    tex = shared_textures(src, materials)
    out = {}
    for k, v in materials.items():
        key = base_slot(k)
        m = dict(v)
        extra = None
        if key == "gun_lens":
            # optic glass: see straight through (the browser draws it at 14 % opacity)
            m["alphaMode"] = "MASK"
            extra = {"baseColorTex": "__clear"}
            tex = dict(tex, __clear=clear)
        out[key] = make_instance(master, dest, key, m, tex, extra)
    return out


def import_static(src, file, dest, name, instances):
    mesh = next(o for o in import_fbx(os.path.join(src, file), dest, name, False) if isinstance(o, unreal.StaticMesh))
    assign_materials(mesh, instances)
    return mesh


def projectile_kind(a):
    if a.get("goo"):
        return {"spit": unreal.SOProjectileKind.SPIT, "bile": unreal.SOProjectileKind.BILE, "brood": unreal.SOProjectileKind.BROOD}[a["goo"]]
    if a.get("projectile"):
        return unreal.SOProjectileKind.ROCKET
    return unreal.SOProjectileKind.ROUND if a["cls"] == "kinetic" else unreal.SOProjectileKind.BOLT


def weapon(master, arch, a, clear):
    folder = weapon_dir(a["model"])
    src = os.path.join(SOURCE, "Weapons", folder)
    dest = f"/Game/Weapons/{folder}"
    if not os.path.isdir(src):
        log(f"DA_{folder}: skipped ({src} missing, run export_unreal.sh)")
        return None
    ensure_dir(dest)
    materials = load_json(os.path.join(src, "materials.json"))
    instances = gun_instances(master, src, dest, materials, clear)
    info = load_json(os.path.join(src, a["model"] + ".parts.json"))
    body = import_static(src, a["model"] + ".fbx", dest, f"SM_{folder}", instances)
    parts = []
    for name, p in info["parts"].items():
        mesh = import_static(src, p["file"], dest, f"SM_{folder}_{name}", instances)
        part = unreal.SOWeaponPart()
        part.set_editor_property("name", name)
        part.set_editor_property("mesh", mesh)
        part.set_editor_property("rest_location", unreal.Vector(*p["loc"]))
        q = p["rot"]
        part.set_editor_property("rest_rotation", unreal.Quat(q[0], q[1], q[2], q[3]))
        part.set_editor_property("parent", p.get("parent") or "")
        parts.append(part)

    path = f"{dest}/DA_{folder}"
    if eal.does_asset_exist(path):
        data = eal.load_asset(path)
    else:
        factory = unreal.DataAssetFactory()
        factory.set_editor_property("data_asset_class", unreal.SOWeaponData)
        data = tools.create_asset(f"DA_{folder}", dest, unreal.SOWeaponData, factory)
    cls = {"kinetic": unreal.SOWeaponClass.KINETIC, "energy": unreal.SOWeaponClass.ENERGY, "horror": unreal.SOWeaponClass.HORROR}[a["cls"]]
    kind = projectile_kind(a)
    velocity = a.get("vel") or (60.0 if kind == unreal.SOProjectileKind.ROCKET else 500.0)
    tracer = a.get("tracer") or {"kinetic": "#ffc873", "energy": "#7fe8ff", "horror": "#9cff4a"}[a["cls"]]
    values = dict(display_name=unreal.Text(a["name"]), archetype=arch, slot=int(a["slot"]), loot_weight=float(a.get("weight", 1.0)),
                  weapon_class=cls, sound_prefix=arch, damage=float(a["dmg"]), rounds_per_minute=float(a["rpm"]),
                  magazine_size=int(a["mag"]), reserve_ammo=int(a["reserve"]), reload_time=float(a["reload"]),
                  range=float(a["range"]), spread=float(a["spread"]), crit_multiplier=float(a["crit"]),
                  automatic=bool(a.get("auto")), burst=int(a.get("burst", 0)), burst_rpm=float(a.get("burstRpm", 0.0)),
                  pellets=int(a.get("pellets", 1)), projectile=kind, splash=float(a.get("splash", 0.0)), dot=float(a.get("dot", 0.0)),
                  swarm=int(a.get("swarm", 0)), aim_zoom=float(a["zoom"]), muzzle_velocity=float(velocity),
                  gravity_scale=float(a.get("grav", 0.0)) if kind == unreal.SOProjectileKind.ROUND else (0.35 if kind in (
                      unreal.SOProjectileKind.SPIT, unreal.SOProjectileKind.BILE, unreal.SOProjectileKind.BROOD) else 0.0),
                  kick=float(a.get("kick", 1.0)), ads_time=float(a["adsTime"]), sprint_to_fire_time=float(a["sprintOut"]),
                  tracer_color=hex_color(tracer), body_mesh=body, parts=parts,
                  sights=[unreal.Name(s) for s in a["sights"]], default_sight=a["defaultSight"])
    for key, value in values.items():
        data.set_editor_property(key, value)
    sockets = info["sockets"]
    for key, prop in (("muzzle", "muzzle_location"), ("sight", "sight_location"), ("foregrip", "foregrip_location")):
        if key in sockets:
            data.set_editor_property(prop, unreal.Vector(*sockets[key]["loc"]))
    data.set_editor_property("has_rail", "rail" in sockets)
    data.set_editor_property("built_in_scope", "scope" in sockets)
    if "rail" in sockets:
        data.set_editor_property("rail_location", unreal.Vector(*sockets["rail"]["loc"]))
    if arch == "rifle":
        arms = rifle_arms(master)
        data.set_editor_property("arm_left_mesh", arms["Left"])
        data.set_editor_property("arm_right_mesh", arms["Right"])
    eal.save_loaded_asset(data, only_if_is_dirty=False)
    eal.save_directory(dest, only_if_is_dirty=False, recursive=True)
    log(f"DA_{folder}: {arch}, {len(parts)} parts, sockets {sorted(sockets)}")
    return data


def rifle_arms(master):
    arms_src = os.path.join(SOURCE, "Weapons", "Arms")
    arms_dest = "/Game/Weapons/Arms"
    ensure_dir(arms_dest)
    arm_mats = load_json(os.path.join(arms_src, "materials.json"))
    arm_instances = {base_slot(k): make_instance(master, arms_dest, base_slot(k), v, {}) for k, v in arm_mats.items()}
    arms = {}
    for side, file in (("Left", "arm_L.fbx"), ("Right", "arm_R.fbx")):
        arms[side] = import_static(arms_src, file, arms_dest, f"SM_Arm{side}", arm_instances)
    eal.save_directory(arms_dest, only_if_is_dirty=False, recursive=True)
    return arms


def optics(master, clear):
    """gun_attach.glb: ATT_<id> optics with their eye points (relative to the rail)."""
    src = os.path.join(SOURCE, "Weapons", "Attach")
    dest = "/Game/Weapons/Attach"
    ensure_dir(dest)
    materials = load_json(os.path.join(src, "materials.json"))
    instances = gun_instances(master, src, dest, materials, clear)
    out = {}
    for sight_id in ("reflex", "holo", "x2", "x4", "x8"):
        name = f"ATT_{sight_id}"
        if not os.path.exists(os.path.join(src, name + ".fbx")):
            continue
        mesh = import_static(src, name + ".fbx", dest, f"SM_{name}", instances)
        sockets = load_json(os.path.join(src, name + ".parts.json"))["sockets"]
        eye = sockets.get(f"{name}_sight", {"loc": [0, 0, 0]})["loc"]
        out[sight_id] = (mesh, eye)
    eal.save_directory(dest, only_if_is_dirty=False, recursive=True)
    return out


def loot_props(master):
    out = {}
    for folder, files in (("Loot", ("PR_core", "PR_ammo")), ("Reliquary", ("VX_reliquary",))):
        src = os.path.join(SOURCE, "Props", folder)
        dest = f"/Game/Props/{folder}"
        if not os.path.isdir(src):
            continue
        ensure_dir(dest)
        materials = load_json(os.path.join(src, "materials.json"))
        manifest = load_json(os.path.join(src, "export_fbx.json"))
        used = {base_slot(n) for a in manifest["assets"] if a["file"][:-4] in files for n in a["materials"]}
        tex = import_textures_for(src, materials, dest + "/Textures", used)
        instances = {k: make_instance(master, dest, k, m, tex) for k, m in ((base_slot(k), m) for k, m in materials.items()) if k in used}
        for f in files:
            out[f] = import_static(src, f + ".fbx", dest, f"SM_{f}", instances)
        eal.save_directory(dest, only_if_is_dirty=False, recursive=True)
    log(f"loot props: {sorted(out)}")
    return out


def loot_tables(datas, sight_meshes):
    game = load_json(GAME_DATA)
    ensure_dir("/Game/Data")
    path = "/Game/Data/DA_LootTables"
    if eal.does_asset_exist(path):
        tables = eal.load_asset(path)
    else:
        factory = unreal.DataAssetFactory()
        factory.set_editor_property("data_asset_class", unreal.SOLootTables)
        tables = tools.create_asset("DA_LootTables", "/Game/Data", unreal.SOLootTables, factory)
    rarities = []
    for r in game["rarity"]:
        info = unreal.SORarityInfo()
        info.set_editor_property("id", r["id"])
        info.set_editor_property("name", unreal.Text(r["name"]))
        info.set_editor_property("color", hex_color(r["color"]))
        info.set_editor_property("mult", float(r["mult"]))
        info.set_editor_property("perks", int(r["perks"]))
        rarities.append(info)
    perks = []
    for pid, p in game["perks"].items():
        info = unreal.SOPerkInfo()
        info.set_editor_property("id", pid)
        info.set_editor_property("name", unreal.Text(p["name"]))
        info.set_editor_property("description", unreal.Text(p["desc"]))
        perks.append(info)
    sights = []
    for sid, s in game["sights"].items():
        info = unreal.SOSightInfo()
        info.set_editor_property("id", sid)
        info.set_editor_property("name", unreal.Text(s["name"]))
        info.set_editor_property("zoom", float(s.get("zoom", 0.0)))
        info.set_editor_property("scope", bool(s.get("scope", False)))
        if sid in sight_meshes:
            mesh, eye = sight_meshes[sid]
            info.set_editor_property("mesh", mesh)
            info.set_editor_property("eye_point", unreal.Vector(*eye))
        sights.append(info)
    shaders = []
    for s in game["shaders"]:
        info = unreal.SOShaderInfo()
        info.set_editor_property("id", s["id"])
        info.set_editor_property("name", unreal.Text(s["name"]))
        info.set_editor_property("body", hex_color(s["body"]))
        shaders.append(info)
    entries = []
    for arch, data in datas.items():
        e = unreal.SOArchetypeEntry()
        e.set_editor_property("id", arch)
        e.set_editor_property("data", data)
        entries.append(e)
    n = game["names"]
    values = dict(rarities=rarities, perks=perks, sights=sights, shaders=shaders, archetypes=entries,
                  slot_names=[unreal.Text(s) for s in game["slots"]], prefix=n["prefix"], noun=n["noun"], maker=n["maker"],
                  model_code={unreal.Name(k): v for k, v in n["modelCode"].items()}, bio_prefix=n["bioPrefix"], bio_noun=n["bioNoun"],
                  exotic_names={unreal.Name(k): v for k, v in n["exotic"].items()})
    for key, value in values.items():
        tables.set_editor_property(key, value)
    eal.save_loaded_asset(tables, only_if_is_dirty=False)
    log(f"DA_LootTables: {len(rarities)} rarities, {len(perks)} perks, {len(sights)} sights, {len(entries)} archetypes")
    return tables


def weapons(master, defaults):
    game = load_json(GAME_DATA)
    sight_meshes = optics(master, defaults["clear"])
    datas = {}
    for arch, a in game["archetypes"].items():
        data = weapon(master, arch, a, defaults["clear"])
        if data:
            datas[arch] = data
    loot_tables(datas, sight_meshes)
    loot_props(master)


# ---------------------------------------------------------------- effects + audio (stage 4)

FX_SHAPE_HLSL = """
float2 d = UV - 0.5;
float dotS = saturate(1.0 - length(d) * 2.0);
dotS = dotS * dotS * (3.0 - 2.0 * dotS);
float across = saturate(1.0 - abs(d.y) * 2.0);
across *= across;
float head = UV.x * saturate((1.0 - UV.x) * 6.0);
float root = saturate(1.0 - UV.x) * saturate(UV.x * 8.0 + 0.25);
float s = Mode < 0.5 ? dotS : (Mode < 1.5 ? across * head : across * root);
return pow(s, Softness);
"""

DECAL_HLSL = """
float r = length(UV - 0.5) * 2.0;
float hole = 1.0 - smoothstep(0.12, 0.2, r);
float burn = (1.0 - smoothstep(0.2, 0.95, r)) * 0.55;
return saturate(hole + burn);
"""


def fx_master():
    """Unlit effect material: colour + intensity from per-instance custom data (0..3), shape from UVs (Mode param:
    0 soft dot, 1 streak bright at the head (U=1), 2 streak bright at the root). Additive by default; instances
    switch to translucent for smoke and blood."""
    path = "/Game/FX/M_SOFx"
    ensure_dir("/Game/FX")
    if eal.does_asset_exist(path):
        mat = eal.load_asset(path)
        mel.delete_all_material_expressions(mat)
    else:
        mat = tools.create_asset("M_SOFx", "/Game/FX", unreal.Material, unreal.MaterialFactoryNew())
    mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_ADDITIVE)
    mat.set_editor_property("two_sided", True)
    mat.set_editor_property("used_with_instanced_static_meshes", True)

    def custom_data(index, default, x, y):
        e = mel.create_material_expression(mat, unreal.MaterialExpressionPerInstanceCustomData, x, y)
        e.set_editor_property("data_index", index)
        e.set_editor_property("const_default_value", default)
        return e

    def scalar(name, value, x, y):
        e = mel.create_material_expression(mat, unreal.MaterialExpressionScalarParameter, x, y)
        e.set_editor_property("parameter_name", name)
        e.set_editor_property("default_value", value)
        return e

    r, g, b, i = (custom_data(k, 1.0, -900, -200 + k * 110) for k in range(4))
    rgb = mel.create_material_expression(mat, unreal.MaterialExpressionAppendVector, -650, -150)
    rg = mel.create_material_expression(mat, unreal.MaterialExpressionAppendVector, -760, -180)
    mel.connect_material_expressions(r, "", rg, "A")
    mel.connect_material_expressions(g, "", rg, "B")
    mel.connect_material_expressions(rg, "", rgb, "A")
    mel.connect_material_expressions(b, "", rgb, "B")

    uv = mel.create_material_expression(mat, unreal.MaterialExpressionTextureCoordinate, -900, 300)
    shape = mel.create_material_expression(mat, unreal.MaterialExpressionCustom, -650, 300)
    shape.set_editor_property("code", FX_SHAPE_HLSL)
    shape.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT1)
    inputs = []
    for name in ("UV", "Mode", "Softness"):
        ci = unreal.CustomInput()
        ci.set_editor_property("input_name", name)
        inputs.append(ci)
    shape.set_editor_property("inputs", inputs)
    mel.connect_material_expressions(uv, "", shape, "UV")
    mel.connect_material_expressions(scalar("Mode", 0.0, -900, 420), "", shape, "Mode")
    mel.connect_material_expressions(scalar("Softness", 1.0, -900, 500), "", shape, "Softness")

    amount = mel.create_material_expression(mat, unreal.MaterialExpressionMultiply, -400, 150)
    mel.connect_material_expressions(shape, "", amount, "A")
    mel.connect_material_expressions(i, "", amount, "B")
    emissive = mel.create_material_expression(mat, unreal.MaterialExpressionMultiply, -200, -50)
    mel.connect_material_expressions(rgb, "", emissive, "A")
    mel.connect_material_expressions(amount, "", emissive, "B")
    mel.connect_material_property(emissive, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    opacity = mel.create_material_expression(mat, unreal.MaterialExpressionSaturate, -200, 150)
    mel.connect_material_expressions(amount, "", opacity, "")
    mel.connect_material_property(opacity, "", unreal.MaterialProperty.MP_OPACITY)
    mel.recompile_material(mat)
    eal.save_loaded_asset(mat, only_if_is_dirty=False)

    def instance(name, mode, softness, translucent):
        ipath = f"/Game/FX/{name}"
        mi = eal.load_asset(ipath) if eal.does_asset_exist(ipath) else tools.create_asset(
            name, "/Game/FX", unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
        mel.set_material_instance_parent(mi, mat)
        mel.set_material_instance_scalar_parameter_value(mi, "Mode", mode)
        mel.set_material_instance_scalar_parameter_value(mi, "Softness", softness)
        if translucent:
            o = mi.get_editor_property("base_property_overrides")
            o.set_editor_property("override_blend_mode", True)
            o.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
            mi.set_editor_property("base_property_overrides", o)
        mel.update_material_instance(mi)
        eal.save_loaded_asset(mi, only_if_is_dirty=False)

    instance("MI_FxGlow", 0.0, 1.5, False)
    instance("MI_FxStreak", 1.0, 1.0, False)
    instance("MI_FxFlash", 2.0, 0.8, False)
    instance("MI_FxSmoke", 0.0, 1.2, True)
    log("effect materials ready")


def decal_material():
    path = "/Game/FX/M_SOBulletHole"
    if eal.does_asset_exist(path):
        mat = eal.load_asset(path)
        mel.delete_all_material_expressions(mat)
    else:
        mat = tools.create_asset("M_SOBulletHole", "/Game/FX", unreal.Material, unreal.MaterialFactoryNew())
    mat.set_editor_property("material_domain", unreal.MaterialDomain.MD_DEFERRED_DECAL)
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
    uv = mel.create_material_expression(mat, unreal.MaterialExpressionTextureCoordinate, -700, 0)
    shape = mel.create_material_expression(mat, unreal.MaterialExpressionCustom, -450, 0)
    shape.set_editor_property("code", DECAL_HLSL)
    shape.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT1)
    ci = unreal.CustomInput()
    ci.set_editor_property("input_name", "UV")
    shape.set_editor_property("inputs", [ci])
    mel.connect_material_expressions(uv, "", shape, "UV")
    colour = mel.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, -450, -150)
    colour.set_editor_property("constant", unreal.LinearColor(0.02, 0.018, 0.016, 1.0))
    rough = mel.create_material_expression(mat, unreal.MaterialExpressionConstant, -450, 150)
    rough.set_editor_property("r", 0.95)
    mel.connect_material_property(colour, "", unreal.MaterialProperty.MP_BASE_COLOR)
    mel.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
    mel.connect_material_property(shape, "", unreal.MaterialProperty.MP_OPACITY)
    mel.recompile_material(mat)
    eal.save_loaded_asset(mat, only_if_is_dirty=False)


def fx_meshes():
    src = os.path.join(SOURCE, "FX")
    for name in ("FX_Quad", "FX_Streak", "FX_Star"):
        mesh = next(o for o in import_fbx(os.path.join(src, name + ".fbx"), "/Game/FX", "SM_" + name, False) if isinstance(o, unreal.StaticMesh))
        eal.save_loaded_asset(mesh, only_if_is_dirty=False)
    log("effect meshes ready")


def audio():
    src = os.path.join(SOURCE, "Audio")
    ensure_dir("/Game/Audio")
    count = 0
    for f in sorted(os.listdir(src)):
        if not f.endswith(".wav"):
            continue
        name = "S_" + os.path.splitext(f)[0]
        task = unreal.AssetImportTask()
        task.set_editor_property("filename", os.path.join(src, f))
        task.set_editor_property("destination_path", "/Game/Audio")
        task.set_editor_property("destination_name", name)
        task.set_editor_property("automated", True)
        task.set_editor_property("replace_existing", True)
        task.set_editor_property("save", True)
        tools.import_asset_tasks([task])
        count += 1
    log(f"{count} sounds imported")


def main():
    if not os.path.isdir(SOURCE):
        raise RuntimeError(f"{SOURCE} is missing: run bash tools/blender/export_unreal.sh first")
    # The legacy FBX importer honours FbxImportUI (Interchange would ignore these options).
    unreal.SystemLibrary.execute_console_command(None, "Interchange.FeatureFlags.Import.FBX 0")
    defaults = default_textures()
    master = master_material(defaults)
    # SO_IMPORT_ONLY=arms,weapons,... re-imports just those steps (default: everything).
    only = {s.strip() for s in os.environ.get("SO_IMPORT_ONLY", "").split(",") if s.strip()}
    want = lambda step: not only or step in only
    if want("player"):
        character(os.path.join(SOURCE, "Characters", "PlayerMale"), "/Game/Characters/PlayerMale", "SK_PlayerMale", "A_PlayerMale_",
                  master, player_extra)
    if want("player") or want("arms"):
        player_arms(master)
    if want("stalker"):
        character(os.path.join(SOURCE, "Characters", "Stalker"), "/Game/Characters/Stalker", "SK_Stalker", "A_Stalker_",
                  master, stalker_extra, flesh=True)
    if want("weapons") or want("rifle"):
        weapons(master, defaults)
    if want("fx"):
        fx_master()
        decal_material()
        fx_meshes()
    if want("audio"):
        audio()
    log("done")


main()
