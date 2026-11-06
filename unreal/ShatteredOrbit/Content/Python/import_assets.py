"""Imports the Blender-built assets (unreal/ShatteredOrbit/SourceArt, written by tools/blender/export_unreal.sh).

Creates:
  /Game/Materials/M_SOStandard           master PBR material (glTF semantics: base x tint x vertex colour, MR map G=rough B=metal)
  /Game/Materials/T_White, T_WhiteMask, T_FlatNormal   our own 4x4 default textures
  /Game/Characters/PlayerMale/SK_PlayerMale (+ skeleton, physics asset, Anims/A_PlayerMale_<Clip>, MI_*)
  /Game/Characters/Stalker/SK_Stalker      (+ Anims/A_Stalker_<Clip>, hx_* flesh textures from assets/textures)
  /Game/Weapons/Rifle/SM_Rifle, SM_Rifle_mag, SM_Rifle_bolt, DA_Rifle (USOWeaponData with data.js stats)
  /Game/Weapons/Arms/SM_ArmLeft, SM_ArmRight

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

# The rifle, from src/game/data.js ARCHETYPES.rifle and weaponHandling (ADS in, sprint to fire).
RIFLE = dict(display_name="Assault Rifle", archetype="rifle", damage=19.0, rounds_per_minute=600.0, magazine_size=30,
             reserve_ammo=300, reload_time=2.3, range=40.0, spread=1.0, crit_multiplier=1.6, automatic=True,
             aim_zoom=1.35, muzzle_velocity=715.0, gravity_scale=1.0, kick=1.3, ads_time=0.24, sprint_to_fire_time=0.2)

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
    return {
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


def rifle(master):
    src = os.path.join(SOURCE, "Weapons", "Rifle")
    dest = "/Game/Weapons/Rifle"
    ensure_dir(dest)
    materials = load_json(os.path.join(src, "materials.json"))
    tex = import_textures_for(src, materials, dest + "/Textures")
    instances = {base_slot(k): make_instance(master, dest, base_slot(k), v, tex) for k, v in materials.items()}
    info = load_json(os.path.join(src, "gun_rifle.parts.json"))

    body = next(o for o in import_fbx(os.path.join(src, "gun_rifle.fbx"), dest, "SM_Rifle", False) if isinstance(o, unreal.StaticMesh))
    assign_materials(body, instances)
    parts = []
    for name, p in info["parts"].items():
        mesh = next(o for o in import_fbx(os.path.join(src, p["file"]), dest, f"SM_Rifle_{name}", False) if isinstance(o, unreal.StaticMesh))
        assign_materials(mesh, instances)
        part = unreal.SOWeaponPart()
        part.set_editor_property("name", name)
        part.set_editor_property("mesh", mesh)
        part.set_editor_property("rest_location", unreal.Vector(*p["loc"]))
        q = p["rot"]
        part.set_editor_property("rest_rotation", unreal.Quat(q[0], q[1], q[2], q[3]))
        parts.append(part)

    arms_src = os.path.join(SOURCE, "Weapons", "Arms")
    arms_dest = "/Game/Weapons/Arms"
    ensure_dir(arms_dest)
    arm_mats = load_json(os.path.join(arms_src, "materials.json"))
    arm_instances = {base_slot(k): make_instance(master, arms_dest, base_slot(k), v, {}) for k, v in arm_mats.items()}
    arms = {}
    for side, file in (("Left", "arm_L.fbx"), ("Right", "arm_R.fbx")):
        mesh = next(o for o in import_fbx(os.path.join(arms_src, file), arms_dest, f"SM_Arm{side}", False) if isinstance(o, unreal.StaticMesh))
        assign_materials(mesh, arm_instances)
        arms[side] = mesh

    path = f"{dest}/DA_Rifle"
    if eal.does_asset_exist(path):
        data = eal.load_asset(path)
    else:
        factory = unreal.DataAssetFactory()
        factory.set_editor_property("data_asset_class", unreal.SOWeaponData)
        data = tools.create_asset("DA_Rifle", dest, unreal.SOWeaponData, factory)
    for key, value in RIFLE.items():
        if key == "display_name":
            value = unreal.Text(value)
        data.set_editor_property(key, value)
    data.set_editor_property("weapon_class", unreal.SOWeaponClass.KINETIC)
    data.set_editor_property("body_mesh", body)
    data.set_editor_property("parts", parts)
    sockets = info["sockets"]
    data.set_editor_property("muzzle_location", unreal.Vector(*sockets["muzzle"]["loc"]))
    data.set_editor_property("sight_location", unreal.Vector(*sockets["sight"]["loc"]))
    data.set_editor_property("foregrip_location", unreal.Vector(*sockets["foregrip"]["loc"]))
    data.set_editor_property("arm_left_mesh", arms["Left"])
    data.set_editor_property("arm_right_mesh", arms["Right"])
    eal.save_loaded_asset(data, only_if_is_dirty=False)
    eal.save_directory(dest, only_if_is_dirty=False, recursive=True)
    eal.save_directory(arms_dest, only_if_is_dirty=False, recursive=True)
    log(f"DA_Rifle: {len(parts)} parts, muzzle {sockets['muzzle']['loc']}")


def main():
    if not os.path.isdir(SOURCE):
        raise RuntimeError(f"{SOURCE} is missing: run bash tools/blender/export_unreal.sh first")
    # The legacy FBX importer honours FbxImportUI (Interchange would ignore these options).
    unreal.SystemLibrary.execute_console_command(None, "Interchange.FeatureFlags.Import.FBX 0")
    defaults = default_textures()
    master = master_material(defaults)
    character(os.path.join(SOURCE, "Characters", "PlayerMale"), "/Game/Characters/PlayerMale", "SK_PlayerMale", "A_PlayerMale_",
              master, player_extra)
    character(os.path.join(SOURCE, "Characters", "Stalker"), "/Game/Characters/Stalker", "SK_Stalker", "A_Stalker_",
              master, stalker_extra, flesh=True)
    rifle(master)
    log("done")


main()
