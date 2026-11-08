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
    name = re.sub(r"[._]\d{3}$", "", str(name))
    if name == "skin__head":
        return "skin_face"                                    # the face has its own skin maps (tools/blender/skin.py)
    return "skin" if name.startswith("skin__") else name     # per-region body sections share the skin material


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


WEAR_HLSL = {
    "color": """
float edge = saturate((1.0 - A) * EdgeWear * (0.45 + W.b * 1.1));
float g = W.g * Grime;
float s = W.r * Scratches;
float3 c = C * lerp(float3(1.0, 1.0, 1.0), float3(0.5, 0.46, 0.4), g);
float3 bare = lerp(float3(0.6, 0.6, 0.58), saturate(C * 1.7 + 0.1), 1.0 - WearMetal);
return lerp(c, bare, saturate(edge + s * 0.5));
""",
    "metal": """
float edge = saturate((1.0 - A) * EdgeWear * (0.45 + W.b * 1.1));
return lerp(M, max(M, WearMetal), edge);
""",
    "rough": """
float edge = saturate((1.0 - A) * EdgeWear * (0.45 + W.b * 1.1));
return saturate(lerp(R + W.g * Grime * 0.3, 0.3, saturate(edge * 0.8 + W.r * Scratches * 0.45)));
""",
}

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
    mel.connect_material_property(base, "A", unreal.MaterialProperty.MP_OPACITY_MASK)

    mr = tex_param("MRTex", S.SAMPLERTYPE_MASKS, defaults["mask"], -900, 340)
    metal = mul(mr, "B", scalar("Metallic", 0.0, -900, 560), "", -650, 360)
    rough = mul(mr, "G", scalar("Roughness", 0.5, -900, 640), "", -650, 480)

    # Wear (guns): edges rubbed bare where the vertex colour alpha says (1 - edge wear), scratches and grime from the
    # shared wear mask (R scratches, G grime, B chip breakup). Every amount is 0 by default: no effect elsewhere.
    uv = mel.create_material_expression(mat, unreal.MaterialExpressionTextureCoordinate, -1300, 1500)
    tiling = scalar("WearTiling", 3.0, -1300, 1600)
    uvs = mul(uv, "", tiling, "", -1150, 1520)
    wear = tex_param("WearTex", S.SAMPLERTYPE_MASKS, defaults["mask"], -1000, 1500)
    mel.connect_material_expressions(uvs, "", wear, "UVs")
    amounts = {n: scalar(n, 0.0, -1000, 1700 + i * 80) for i, n in enumerate(("EdgeWear", "Scratches", "Grime", "WearMetal"))}

    def wear_node(kind, inputs, out_type, y):
        node = mel.create_material_expression(mat, unreal.MaterialExpressionCustom, -250, y)
        node.set_editor_property("code", WEAR_HLSL[kind])
        node.set_editor_property("output_type", out_type)
        ins = []
        for name in list(inputs) + ["A", "W", "EdgeWear", "Scratches", "Grime", "WearMetal"]:
            ci = unreal.CustomInput()
            ci.set_editor_property("input_name", name)
            ins.append(ci)
        node.set_editor_property("inputs", ins)
        for name, (src, pin) in inputs.items():
            mel.connect_material_expressions(src, pin, node, name)
        mel.connect_material_expressions(vcol, "A", node, "A")
        mel.connect_material_expressions(wear, "RGB", node, "W")
        for n, e in amounts.items():
            mel.connect_material_expressions(e, "", node, n)
        return node
    F = unreal.CustomMaterialOutputType
    worn_colour = wear_node("color", {"C": (colour, "")}, F.CMOT_FLOAT3, -200)
    worn_metal = wear_node("metal", {"M": (metal, "")}, F.CMOT_FLOAT1, 360)
    worn_rough = wear_node("rough", {"R": (rough, "")}, F.CMOT_FLOAT1, 480)
    mel.connect_material_property(worn_colour, "", unreal.MaterialProperty.MP_BASE_COLOR)
    mel.connect_material_property(worn_metal, "", unreal.MaterialProperty.MP_METALLIC)
    mel.connect_material_property(worn_rough, "", unreal.MaterialProperty.MP_ROUGHNESS)

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


# Slots that use another parent than M_SOStandard (key -> material), filled in main().
PARENT_FOR = {}


def hair_material(defaults):
    """/Game/Materials/M_SOHair: the hair cards (hair.py). Unreal's Hair shading model with the strand tangent along
    the card (the atlas strands run down V), dithered alpha (temporal AA blends the strand edges instead of a hard cut)
    and the atlas brightness kept under the dark tint so single strands stay visible. Same parameter names as the
    master (BaseColorTex, BaseColorTint, Roughness)."""
    path = "/Game/Materials/M_SOHair"
    if eal.does_asset_exist(path):
        mat = eal.load_asset(path)
        mel.delete_all_material_expressions(mat)
    else:
        mat = tools.create_asset("M_SOHair", "/Game/Materials", unreal.Material, unreal.MaterialFactoryNew())
    for prop, value in (("used_with_skeletal_mesh", True), ("used_with_morph_targets", True), ("two_sided", True),
                        ("blend_mode", unreal.BlendMode.BLEND_MASKED), ("opacity_mask_clip_value", 0.3333),
                        ("shading_model", unreal.MaterialShadingModel.MSM_HAIR)):
        mat.set_editor_property(prop, value)
    E = lambda cls, x, y: mel.create_material_expression(mat, cls, x, y)
    tex = E(unreal.MaterialExpressionTextureSampleParameter2D, -900, -200)
    tex.set_editor_property("parameter_name", "BaseColorTex")
    tex.set_editor_property("texture", defaults["white"])
    tint = E(unreal.MaterialExpressionVectorParameter, -900, 40)
    tint.set_editor_property("parameter_name", "BaseColorTint")
    tint.set_editor_property("default_value", unreal.LinearColor(0.035, 0.024, 0.018, 1))
    code = E(unreal.MaterialExpressionCustom, -500, -100)
    code.set_editor_property("code", "float l = saturate((C.r - 0.55) / 0.45); return T * lerp(0.45, 1.9, l * l);")
    code.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT3)
    ins = []
    for n in ("C", "T"):
        ci = unreal.CustomInput(); ci.set_editor_property("input_name", n); ins.append(ci)
    code.set_editor_property("inputs", ins)
    mel.connect_material_expressions(tex, "RGB", code, "C")
    mel.connect_material_expressions(tint, "", code, "T")
    mel.connect_material_property(code, "", unreal.MaterialProperty.MP_BASE_COLOR)

    def scalar(name, value, y):
        e = E(unreal.MaterialExpressionScalarParameter, -500, y)
        e.set_editor_property("parameter_name", name)
        e.set_editor_property("default_value", value)
        return e
    mel.connect_material_property(scalar("Scatter", 0.35, 120), "", unreal.MaterialProperty.MP_METALLIC)     # Hair: Scatter
    mel.connect_material_property(scalar("Specular", 0.3, 200), "", unreal.MaterialProperty.MP_SPECULAR)
    mel.connect_material_property(scalar("Roughness", 0.5, 280), "", unreal.MaterialProperty.MP_ROUGHNESS)
    tangent = E(unreal.MaterialExpressionConstant3Vector, -500, 440)
    tangent.set_editor_property("constant", unreal.LinearColor(0, 1, 0, 0))
    mel.connect_material_property(tangent, "", unreal.MaterialProperty.MP_NORMAL)                            # Hair: Tangent
    fn = unreal.load_asset("/Engine/Functions/Engine_MaterialFunctions02/Utility/DitherTemporalAA")
    ok = False
    if fn:
        dither = E(unreal.MaterialExpressionMaterialFunctionCall, -500, 560)
        dither.set_editor_property("material_function", fn)
        ok = mel.connect_material_expressions(tex, "A", dither, "Alpha Threshold")
        if ok:
            mel.connect_material_property(dither, "", unreal.MaterialProperty.MP_OPACITY_MASK)
    if not ok:
        mel.connect_material_property(tex, "A", unreal.MaterialProperty.MP_OPACITY_MASK)
        log("hair: DitherTemporalAA unavailable, plain alpha")
    mel.recompile_material(mat)
    eal.save_loaded_asset(mat, only_if_is_dirty=False)
    log("hair material ready")
    return mat


def make_instance(master, dest, name, m, tex, extra=None):
    """m: one materials.json entry; tex: {relative file or hx name: texture asset}."""
    master = PARENT_FOR.get(name, master)
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


HAIR_TONE = (0.035, 0.024, 0.018)     # dark brown (the concept pair); the game may recolour it later


def player_extra(key, m):
    if key in ("skin", "skin_face"):
        return {"tint": list(SKIN_TONE)}
    if key in ("hair", "hair__cap", "brow"):
        return {"tint": list(HAIR_TONE)}
    return None


# ---------------------------------------------------------------- modular players (wardrobe pieces)

ARMOR_SLOT = {"head": 10, "top": 4, "vest": 20, "outer": 14, "dress": 4, "hands": 6, "legs": 10, "feet": 6}
HEAVY = re.compile(r"plate|armou?r|guard|helmet|vest|harness|pauldron|greave|gauntlet|tactical|carrier|kevlar|combat", re.I)
ICONS = os.path.join(SOURCE, "Icons")


def import_ui_texture(file_path, dest, name):
    tex = import_texture(file_path, dest, name, "color")
    tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_EDITOR_ICON)
    tex.set_editor_property("lod_group", unreal.TextureGroup.TEXTUREGROUP_UI)
    tex.set_editor_property("mip_gen_settings", unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS)
    tex.set_editor_property("never_stream", True)
    return tex


def import_piece(fbx, dest, name, skeleton):
    """A wardrobe piece: skeletal mesh on an existing skeleton, no clips, no physics."""
    ui = unreal.FbxImportUI()
    ui.set_editor_property("import_mesh", True)
    ui.set_editor_property("import_textures", False)
    ui.set_editor_property("import_materials", False)
    ui.set_editor_property("import_as_skeletal", True)
    ui.set_editor_property("automated_import_should_detect_type", False)
    ui.set_editor_property("mesh_type_to_import", unreal.FBXImportType.FBXIT_SKELETAL_MESH)
    ui.set_editor_property("skeleton", skeleton)
    ui.set_editor_property("import_animations", False)
    ui.set_editor_property("create_physics_asset", False)
    sk = ui.get_editor_property("skeletal_mesh_import_data")
    sk.set_editor_property("convert_scene_unit", False)
    sk.set_editor_property("import_morph_targets", False)
    sk.set_editor_property("normal_import_method", unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS_AND_TANGENTS)
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", fbx)
    task.set_editor_property("destination_path", dest)
    task.set_editor_property("destination_name", name)
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("save", False)
    task.set_editor_property("options", ui)
    tools.import_asset_tasks([task])
    for p in task.get_editor_property("imported_object_paths"):
        a = unreal.load_asset(p)
        if isinstance(a, unreal.SkeletalMesh):
            return a
    raise RuntimeError(f"wardrobe piece import failed: {fbx}")


def player_wardrobe(sex, master):
    """export_fbx.py --per-item output of player_<sex>.glb (body + every piece, and their first-person cuts) ->
    SK_Player<Sex> (body, clips, physics), SK_Player<Sex>Arms, Wardrobe/SK_<Sex>_<slot>_<item>,
    Arms/SK_<Sex>Arms_<slot>_<item>, Icons/T_Icon_<slot>_<item> and DA_Wardrobe (USOWardrobeData)."""
    Sex = sex.capitalize()
    src = os.path.join(SOURCE, "Characters", f"Player{Sex}")
    arms_src = os.path.join(SOURCE, "Characters", f"Player{Sex}Arms")
    dest = f"/Game/Characters/Player{Sex}"
    if not os.path.isdir(src):
        log(f"Player{Sex}: skipped ({src} missing, run export_unreal.sh)")
        return None
    manifest = load_json(os.path.join(src, "export_fbx.json"))
    if not manifest.get("per_item"):
        log(f"Player{Sex}: {src} is not a --per-item export, skipped")
        return None
    materials = load_json(os.path.join(src, "materials.json"))
    meta = load_json(os.path.join(src, "wardrobe.json"))
    # start clean: a re-import over an older mesh keeps its material slots (the per-region skin sections would fold
    # into them) and the pieces must bind to the new skeleton
    if eal.does_directory_exist(dest):
        eal.delete_directory(dest)
    ensure_dir(dest)
    used = {base_slot(n) for a in manifest["assets"] for n in a["materials"]}
    tex = import_textures_for(src, materials, dest + "/Textures", used)
    instances = {}
    for key in used:
        m = materials.get(key) or (materials.get("skin") if key == "skin_face" else None) or {}
        instances[key] = make_instance(master, dest, key, m, tex, player_extra(key, m))

    # the body: skeleton, physics and clips
    body_entry = next(a for a in manifest["assets"] if a["name"] == "Body")
    objs = import_fbx(os.path.join(src, body_entry["file"]), dest, f"SK_Player{Sex}", True)
    body = next(o for o in objs if isinstance(o, unreal.SkeletalMesh))
    assign_materials(body, instances)
    skeleton = body.get_editor_property("skeleton")
    ensure_dir(dest + "/Anims")
    actions = sorted(body_entry.get("actions", []), key=len, reverse=True)
    for path in eal.list_assets(dest, recursive=False, include_folder=False):
        obj = eal.load_asset(path)
        if not isinstance(obj, unreal.AnimSequence):
            continue
        clip = next((a for a in actions if obj.get_name().endswith(a)), None)
        if not clip:
            continue
        target = f"{dest}/Anims/A_Player{Sex}_{clip}"
        if eal.does_asset_exist(target):
            eal.delete_asset(target)
        if eal.rename_asset(path, target):
            fix_clip_units(eal.load_asset(target))

    # every piece, and the first-person cuts
    ensure_dir(dest + "/Wardrobe"); ensure_dir(dest + "/Arms"); ensure_dir(dest + "/Icons")
    pieces = {}
    for a in manifest["assets"]:
        if a["name"] == "Body":
            continue
        mesh = import_piece(os.path.join(src, a["file"]), dest + "/Wardrobe", f"SK_{Sex}_{a['slot']}_{a['item']}", skeleton)
        assign_materials(mesh, instances)
        pieces[(a["slot"], a["item"])] = {"mesh": mesh}
    arms_body = None
    if os.path.isdir(arms_src):
        arms_manifest = load_json(os.path.join(arms_src, "export_fbx.json"))
        for a in arms_manifest["assets"]:
            if a["name"] == "Body":
                arms_body = import_piece(os.path.join(arms_src, a["file"]), dest, f"SK_Player{Sex}Arms", skeleton)
                assign_materials(arms_body, instances)
            elif (a["slot"], a["item"]) in pieces:
                mesh = import_piece(os.path.join(arms_src, a["file"]), dest + "/Arms", f"SK_{Sex}Arms_{a['slot']}_{a['item']}", skeleton)
                assign_materials(mesh, instances)
                pieces[(a["slot"], a["item"])]["arms"] = mesh

    # the data asset
    path = f"{dest}/DA_Wardrobe"
    if eal.does_asset_exist(path):
        data = eal.load_asset(path)
    else:
        factory = unreal.DataAssetFactory()
        factory.set_editor_property("data_asset_class", unreal.SOWardrobeData)
        data = tools.create_asset("DA_Wardrobe", dest, unreal.SOWardrobeData, factory)
    items = []
    wardrobe = meta.get("wardrobe", {})
    for (slot, item), got in sorted(pieces.items()):
        info = wardrobe.get(slot, {}).get(item, {})
        label = info.get("label", item)
        armour = slot in ARMOR_SLOT and not info.get("locked")
        w = unreal.SOWardrobeItem()
        w.set_editor_property("slot", slot)
        w.set_editor_property("item", item)
        w.set_editor_property("label", unreal.Text(label))
        w.set_editor_property("hide", [unreal.Name(r) for r in info.get("hide", [])])
        w.set_editor_property("covered_by", [unreal.Name(r) for r in info.get("coveredBy", [])])
        w.set_editor_property("replaces", [unreal.Name(r) for r in info.get("replaces", [])])
        w.set_editor_property("locked", bool(info.get("locked")))
        w.set_editor_property("hide_hair", bool(info.get("hideHair")))
        w.set_editor_property("armour", armour)
        heavy = bool(HEAVY.search(item + " " + label))
        w.set_editor_property("armor", int(round(ARMOR_SLOT.get(slot, 0) * (1.7 if heavy else 1.0))) if armour else 0)
        w.set_editor_property("mesh", got["mesh"])
        if "arms" in got:
            w.set_editor_property("arms_mesh", got["arms"])
        icon = os.path.join(ICONS, "armour", f"icon_{sex}_{slot}_{item}.png")
        if armour and os.path.exists(icon):
            w.set_editor_property("icon", import_ui_texture(icon, dest + "/Icons", f"T_Icon_{slot}_{item}"))
        items.append(w)
    data.set_editor_property("body", sex)
    data.set_editor_property("body_mesh", body)
    if arms_body:
        data.set_editor_property("arms_mesh", arms_body)
    data.set_editor_property("clip_path_prefix", f"{dest}/Anims/A_Player{Sex}_")
    data.set_editor_property("items", items)
    data.set_editor_property("defaults", {unreal.Name(k): unreal.Name(v) for k, v in meta.get("defaults", {}).items()})
    eal.save_loaded_asset(data, only_if_is_dirty=False)
    eal.save_directory(dest, only_if_is_dirty=False, recursive=True)
    log(f"Player{Sex}: body + {len(pieces)} pieces ({sum(1 for p in pieces.values() if 'arms' in p)} first-person cuts)")
    return data


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


# Gun wear per material (edge wear, scratches, grime, bare metal under the finish): nothing looks factory-new.
GUN_WEAR = {
    "gun_steel": (.9, .3, .4, 1), "gun_parkerized": (.85, .32, .45, 1), "gun_dark": (.8, .3, .45, 1), "gun_metal": (.85, .3, .4, 1),
    "gun_trim": (.7, .25, .3, 1), "gun_body": (.75, .28, .45, 1), "gun_paint": (.75, .28, .45, 1), "gun_brass": (.5, .2, .35, 1),
    "gun_polymer": (.55, .22, .5, 0), "gun_odg": (.55, .22, .5, 0), "gun_grip": (.35, .1, .55, 0), "gun_wood": (.5, .2, .4, 0),
    "gun_sightpaint": (.3, .1, .3, 0),
}
_WEAR_TEX = {}


def wear_texture():
    if "mask" not in _WEAR_TEX:
        f = os.path.join(REPO_TEXTURES, "wear_mask_c.jpg")
        _WEAR_TEX["mask"] = import_texture(f, WEAPON_TEX, "T_wear_mask", "mask") if os.path.exists(f) else None
    return _WEAR_TEX["mask"]


def gun_instances(master, src, dest, materials, clear):
    tex = shared_textures(src, materials)
    out = {}
    worn = wear_texture()
    for k, v in materials.items():
        key = base_slot(k)
        m = dict(v)
        extra = None
        if key == "gun_lens":
            # optic glass: see straight through (the browser draws it at 14 % opacity)
            m["alphaMode"] = "MASK"
            extra = {"baseColorTex": "__clear"}
            tex = dict(tex, __clear=clear)
        mi = make_instance(master, dest, key, m, tex, extra)
        amounts = next((a for name, a in GUN_WEAR.items() if key == name or key.startswith(name + "__")), None)
        if amounts and worn:
            mel.set_material_instance_texture_parameter_value(mi, "WearTex", worn)
            for name, value in zip(("EdgeWear", "Scratches", "Grime", "WearMetal"), amounts):
                mel.set_material_instance_scalar_parameter_value(mi, name, float(value))
            mel.update_material_instance(mi)
            eal.save_loaded_asset(mi, only_if_is_dirty=False)
        out[key] = mi
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
    values = dict(display_name=unreal.Text(a["name"]), title=unreal.Text(a.get("title", a["name"])), archetype=arch, slot=int(a["slot"]), loot_weight=float(a.get("weight", 1.0)),
                  weapon_class=cls, sound_prefix=arch, damage=float(a["dmg"]), rounds_per_minute=float(a["rpm"]),
                  magazine_size=int(a["mag"]), reserve_ammo=int(a["reserve"]), reload_time=float(a["reload"]),
                  range=float(a["range"]), spread=float(a["spread"]), crit_multiplier=float(a["crit"]),
                  automatic=bool(a.get("auto")), burst=int(a.get("burst", 0)), burst_rpm=float(a.get("burstRpm", 0.0)),
                  pellets=int(a.get("pellets", 1)), projectile=kind, splash=float(a.get("splash", 0.0)), dot=float(a.get("dot", 0.0)),
                  swarm=int(a.get("swarm", 0)), aim_zoom=float(a["zoom"]), muzzle_velocity=float(velocity),
                  gravity_scale=float(a.get("grav", 0.0)) if kind == unreal.SOProjectileKind.ROUND else (float(a.get("gooGrav", 0.35)) if kind in (
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
    icon = os.path.join(ICONS, "guns", f"icon_{a['model']}.png")
    if os.path.exists(icon):
        data.set_editor_property("icon", import_ui_texture(icon, dest, f"T_Icon_{folder}"))
    if arch == "rifle":
        arms = rifle_arms(master)
        data.set_editor_property("arm_left_mesh", arms["Left"] if arms else None)
        data.set_editor_property("arm_right_mesh", arms["Right"] if arms else None)
    eal.save_loaded_asset(data, only_if_is_dirty=False)
    eal.save_directory(dest, only_if_is_dirty=False, recursive=True)
    log(f"DA_{folder}: {arch}, {len(parts)} parts, sockets {sorted(sockets)}")
    return data


def rifle_arms(master):
    arms_src = os.path.join(SOURCE, "Weapons", "Arms")
    arms_dest = "/Game/Weapons/Arms"
    if not os.path.isdir(arms_src):                # the old static first-person arms are gone (players rebuilt)
        return None
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


def nexus(master):
    """tools/blender/nexus.py (via export_fbx.py) -> /Game/Environments/Nexus/SM_NX_*: the city hub kit, with
    complex-as-simple collision so every surface can be walked on."""
    src = os.path.join(SOURCE, "Nexus")
    dest = "/Game/Environments/Nexus"
    if not os.path.isdir(src):
        log("Nexus: skipped (SourceArt/Nexus missing, run export_unreal.sh)")
        return
    ensure_dir(dest)
    manifest = load_json(os.path.join(src, "export_fbx.json"))
    materials = load_json(os.path.join(src, "materials.json"))
    used = {base_slot(n) for a in manifest["assets"] for n in a["materials"]}
    tex = import_textures_for(src, materials, dest + "/Textures", used)
    instances = {key: make_instance(master, dest, key, materials.get(key) or {}, tex) for key in used}
    for a in manifest["assets"]:
        name = os.path.splitext(a["file"])[0]
        mesh = import_static(src, a["file"], dest, f"SM_{name}", instances)
        body = mesh.get_editor_property("body_setup")
        if body:
            body.set_editor_property("collision_trace_flag", unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
        eal.save_loaded_asset(mesh, only_if_is_dirty=False)
    eal.save_directory(dest, only_if_is_dirty=False, recursive=True)
    log(f"Nexus: {len(manifest['assets'])} pieces")


# ---------------------------------------------------------------- Nexus Prime, the big city (tools/blender/nexus_city.py)

GROUND_UV_HLSL = """
float s = 1.0 / (T * 100.0);
float3 n = normalize(N);
if (abs(n.z) > 0.6) { return WP.xy * s; }
float2 t = normalize(float2(-n.y, n.x) + 1e-5);
return float2(dot(WP.xy, t), -WP.z) * s;
"""
GROUND_N_HLSL = """
float3 n = normalize(N);
if (abs(n.z) > 0.6) { return normalize(float3(Nt.x * K, -Nt.y * K, max(Nt.z, 0.2))); }
return n;
"""
FACADE_UV_HLSL = """
float along = lerp(D, W, U1.x);
return float2(U0.x * along / Bay, -(1.0 - U0.y) * H / Floor);
"""
FACADE_LIT_HLSL = """
float along = lerp(D, W, U1.x);
float2 c = floor(float2(U0.x * along / Bay, (1.0 - U0.y) * H / Floor));
float h = frac(sin(dot(c + float2(Seed * 17.13 + U1.x * 31.0, Seed * 3.71), float2(12.9898, 78.233))) * 43758.5453);
float lit = step(h, Lit);
float3 col = lerp(float3(1.0, 0.70, 0.40), float3(0.55, 0.80, 1.0), step(0.72, frac(h * 13.7)));
return col * lit * M * Glow * Night * (1.0 - Boarded);
"""
FACADE_COLOR_HLSL = """
float along = lerp(D, W, U1.x);
float um = U0.x * along;
float zm = (1.0 - U0.y) * H;
float3 c = C * T;
// grime: streaks down the walls under the openings, dirt splashed up from the street, all scaled by wear
float colm = floor(um / (Bay * 0.5));
float s = frac(sin(colm * 12.9898 + Seed * 3.1) * 43758.5453);
float streak = saturate(s * 1.6 - 0.5) * (0.55 + 0.45 * frac(-zm / Floor));
float ground = saturate(1.0 - (zm + Z0) / 3.0);
float g = saturate(Wear * (streak * 0.55 + ground * 0.5 + 0.15));
c *= lerp(1.0, 0.5, g);
// repairs: patches of fresher render where the wall was fixed
float2 cell = floor(float2(um / (Bay * 2.0), zm / (Floor * 2.0)));
float r = frac(sin(dot(cell + Seed, float2(27.17, 91.31))) * 15731.743);
c *= (r < Wear * 0.22) ? float3(1.15, 1.12, 1.06) : float3(1.0, 1.0, 1.0);
// abandoned: plywood over the glass
float3 ply = float3(0.30, 0.22, 0.13) * (0.8 + 0.4 * frac(sin(floor(zm * 3.0) * 7.1 + colm) * 913.7));
return lerp(c, ply, M * Boarded);
"""


def _material(path, setup):
    folder, name = path.rsplit("/", 1)
    if eal.does_asset_exist(path):
        mat = eal.load_asset(path)
        mel.delete_all_material_expressions(mat)
    else:
        mat = tools.create_asset(name, folder, unreal.Material, unreal.MaterialFactoryNew())
    for prop, value in setup.items():
        mat.set_editor_property(prop, value)
    return mat


def _custom(mat, code, inputs, out_type, x, y):
    node = mel.create_material_expression(mat, unreal.MaterialExpressionCustom, x, y)
    node.set_editor_property("code", code)
    node.set_editor_property("output_type", out_type)
    ins = []
    for n in inputs:
        ci = unreal.CustomInput()
        ci.set_editor_property("input_name", n)
        ins.append(ci)
    node.set_editor_property("inputs", ins)
    return node


def _param(mat, cls, name, value, x, y):
    e = mel.create_material_expression(mat, cls, x, y)
    e.set_editor_property("parameter_name", name)
    if cls is unreal.MaterialExpressionScalarParameter:
        e.set_editor_property("default_value", value)
    elif cls is unreal.MaterialExpressionVectorParameter:
        e.set_editor_property("default_value", unreal.LinearColor(*value))
    else:
        e.set_editor_property("texture", value[0])
        e.set_editor_property("sampler_type", value[1])
    return e


WET_COLOR_HLSL = """
float flat = saturate((N.z - 0.7) * 3.3);
float puddle = saturate((sin(WP.x * 0.0021) * sin(WP.y * 0.0017) + sin(WP.x * 0.0007 + 1.3) * 0.6 - 0.75 + W * 0.9) * 3.0);
float wet = W * flat;
return C * lerp(1.0, 0.55, wet) * lerp(1.0, 0.8, puddle * wet);
"""
WET_ROUGH_HLSL = """
float flat = saturate((N.z - 0.7) * 3.3);
float puddle = saturate((sin(WP.x * 0.0021) * sin(WP.y * 0.0017) + sin(WP.x * 0.0007 + 1.3) * 0.6 - 0.75 + W * 0.9) * 3.0);
float wet = W * flat;
return lerp(lerp(R, 0.22, wet), 0.04, puddle * wet);
"""
# foliage: the tree bends with the wind more the higher above its base, leaves flutter (cm, world)
FOLIAGE_WPO_HLSL = """
float h = max(LP.z, 0.0) / 100.0;
float ws = max(WS, 0.1);
float2 dir = float2(WX, WY) / ws;
float bend = pow(h / 10.0, 1.6) * (0.35 + 0.65 * min(ws, 14.0) / 10.0);
float sway = 0.5 + 0.5 * sin(T * (0.8 + 0.3 * R) + R * 6.28) + G * 0.7;
float3 off = float3(dir * bend * sway * 22.0, -bend * bend * 2.0);
float fl = sin(T * 7.3 + dot(WP.xy, float2(0.05, 0.07)) + R * 9.0) * min(ws, 12.0) * 0.22 * saturate(h / 3.0);
return off + float3(fl, fl * 0.7, fl * 0.5);
"""


def weather_params():
    """/Game/Environments/MPC_SOWeather: what USOWeatherSubsystem drives every 0.2 s (wind in m/s, gust, wetness,
    rain); read by M_SOGround (wet streets) and M_SOFoliage (trees in the wind). Kept when it exists so the
    materials' references stay valid."""
    ensure_dir("/Game/Environments")
    path = "/Game/Environments/MPC_SOWeather"
    if eal.does_asset_exist(path):
        mpc = eal.load_asset(path)
    else:
        mpc = tools.create_asset("MPC_SOWeather", "/Game/Environments", unreal.MaterialParameterCollection, unreal.MaterialParameterCollectionFactoryNew())
    have = {str(p.get_editor_property("parameter_name")) for p in mpc.get_editor_property("scalar_parameters")}
    want = (("WindX", 2.0), ("WindY", 1.0), ("Wind", 3.0), ("Gust", 0.0), ("Wetness", 0.0), ("Rain", 0.0))
    if not all(n in have for n, _ in want):
        params = list(mpc.get_editor_property("scalar_parameters"))
        for n, v in want:
            if n not in have:
                sp = unreal.CollectionScalarParameter()
                sp.set_editor_property("parameter_name", n)
                sp.set_editor_property("default_value", v)
                params.append(sp)
        mpc.set_editor_property("scalar_parameters", params)
    eal.save_loaded_asset(mpc, only_if_is_dirty=False)
    return mpc


def _weather(mat, mpc, name, x, y):
    e = mel.create_material_expression(mat, unreal.MaterialExpressionCollectionParameter, x, y)
    e.set_editor_property("collection", mpc)
    e.set_editor_property("parameter_name", name)
    return e


def foliage_material(defaults, mpc):
    """/Game/Environments/NexusCity/M_SOFoliage: the city's trees and shrubs (city_trees.py): bark and leaf cards
    (alpha mask), the same parameters as the master (BaseColorTex, BaseColorTint, NormalTex, Roughness), swaying on
    MPC_SOWeather's wind by the height above the trunk base, leaves fluttering, a per-tree phase."""
    mat = _material("/Game/Environments/NexusCity/M_SOFoliage", {"used_with_instanced_static_meshes": True, "two_sided": True,
                                                                "blend_mode": unreal.BlendMode.BLEND_MASKED})
    S = unreal.MaterialSamplerType
    col = _param(mat, unreal.MaterialExpressionTextureSampleParameter2D, "BaseColorTex", (defaults["white"], S.SAMPLERTYPE_COLOR), -800, -200)
    tint = _param(mat, unreal.MaterialExpressionVectorParameter, "BaseColorTint", (1, 1, 1, 1), -800, -420)
    c = mel.create_material_expression(mat, unreal.MaterialExpressionMultiply, -450, -250)
    mel.connect_material_expressions(col, "RGB", c, "A")
    mel.connect_material_expressions(tint, "", c, "B")
    mel.connect_material_property(c, "", unreal.MaterialProperty.MP_BASE_COLOR)
    mel.connect_material_property(col, "A", unreal.MaterialProperty.MP_OPACITY_MASK)
    nrm = _param(mat, unreal.MaterialExpressionTextureSampleParameter2D, "NormalTex", (defaults["normal"], S.SAMPLERTYPE_NORMAL), -800, 100)
    mel.connect_material_property(nrm, "RGB", unreal.MaterialProperty.MP_NORMAL)
    mel.connect_material_property(_param(mat, unreal.MaterialExpressionScalarParameter, "Roughness", .7, -800, 380), "", unreal.MaterialProperty.MP_ROUGHNESS)
    wpo = _custom(mat, FOLIAGE_WPO_HLSL, ("LP", "WP", "WX", "WY", "WS", "G", "T", "R"), unreal.CustomMaterialOutputType.CMOT_FLOAT3, -450, 500)
    lp = mel.create_material_expression(mat, unreal.MaterialExpressionLocalPosition, -800, 500)
    wp = mel.create_material_expression(mat, unreal.MaterialExpressionWorldPosition, -800, 580)
    tm = mel.create_material_expression(mat, unreal.MaterialExpressionTime, -800, 660)
    rnd = mel.create_material_expression(mat, unreal.MaterialExpressionPerInstanceRandom, -800, 740)
    for n, e in (("LP", lp), ("WP", wp), ("T", tm), ("R", rnd)):
        mel.connect_material_expressions(e, "", wpo, n)
    for i, (n, pn) in enumerate((("WX", "WindX"), ("WY", "WindY"), ("WS", "Wind"), ("G", "Gust"))):
        mel.connect_material_expressions(_weather(mat, mpc, pn, -800, 820 + i * 70), "", wpo, n)
    mel.connect_material_property(wpo, "", unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET)
    mel.recompile_material(mat)
    eal.save_loaded_asset(mat, only_if_is_dirty=False)
    return mat


def ground_material(defaults):
    """/Game/Environments/NexusCity/M_SOGround: city ground, roofs, wall, land. The textures are projected in world
    metres (TilingM = metres per tile): from above on flat faces, along the face on walls; normal map in world space."""
    mat = _material("/Game/Environments/NexusCity/M_SOGround", {"tangent_space_normal": False, "used_with_instanced_static_meshes": True})
    S = unreal.MaterialSamplerType
    wp = mel.create_material_expression(mat, unreal.MaterialExpressionWorldPosition, -1400, 0)
    vn = mel.create_material_expression(mat, unreal.MaterialExpressionVertexNormalWS, -1400, 120)
    tiling = _param(mat, unreal.MaterialExpressionScalarParameter, "TilingM", 8.0, -1400, 240)
    uv = _custom(mat, GROUND_UV_HLSL, ("WP", "N", "T"), unreal.CustomMaterialOutputType.CMOT_FLOAT2, -1100, 60)
    mel.connect_material_expressions(wp, "", uv, "WP")
    mel.connect_material_expressions(vn, "", uv, "N")
    mel.connect_material_expressions(tiling, "", uv, "T")
    col = _param(mat, unreal.MaterialExpressionTextureSampleParameter2D, "ColorTex", (defaults["white"], S.SAMPLERTYPE_COLOR), -800, -200)
    nrm = _param(mat, unreal.MaterialExpressionTextureSampleParameter2D, "NormalTex", (defaults["normal"], S.SAMPLERTYPE_NORMAL), -800, 100)
    msk = _param(mat, unreal.MaterialExpressionTextureSampleParameter2D, "MaskTex", (defaults["mask"], S.SAMPLERTYPE_MASKS), -800, 400)
    for t in (col, nrm, msk):
        mel.connect_material_expressions(uv, "", t, "UVs")
    tint = _param(mat, unreal.MaterialExpressionVectorParameter, "Tint", (1, 1, 1, 1), -800, -400)
    c = mel.create_material_expression(mat, unreal.MaterialExpressionMultiply, -450, -250)
    mel.connect_material_expressions(col, "RGB", c, "A")
    mel.connect_material_expressions(tint, "", c, "B")
    # wet when it rains (MPC_SOWeather.Wetness): darker, glossier, puddles on the flat
    mpc = weather_params()
    wet = _weather(mat, mpc, "Wetness", -800, 900)
    wc = _custom(mat, WET_COLOR_HLSL, ("C", "N", "WP", "W"), unreal.CustomMaterialOutputType.CMOT_FLOAT3, -250, -250)
    wr = _custom(mat, WET_ROUGH_HLSL, ("R", "N", "WP", "W"), unreal.CustomMaterialOutputType.CMOT_FLOAT1, -250, 450)
    for node in (wc, wr):
        mel.connect_material_expressions(vn, "", node, "N")
        mel.connect_material_expressions(wp, "", node, "WP")
        mel.connect_material_expressions(wet, "", node, "W")
    mel.connect_material_expressions(c, "", wc, "C")
    mel.connect_material_expressions(msk, "G", wr, "R")
    mel.connect_material_property(wc, "", unreal.MaterialProperty.MP_BASE_COLOR)
    mel.connect_material_property(wr, "", unreal.MaterialProperty.MP_ROUGHNESS)
    strength = _param(mat, unreal.MaterialExpressionScalarParameter, "NormalStrength", 1.0, -800, 650)
    n = _custom(mat, GROUND_N_HLSL, ("Nt", "N", "K"), unreal.CustomMaterialOutputType.CMOT_FLOAT3, -450, 100)
    mel.connect_material_expressions(nrm, "RGB", n, "Nt")
    mel.connect_material_expressions(vn, "", n, "N")
    mel.connect_material_expressions(strength, "", n, "K")
    mel.connect_material_property(n, "", unreal.MaterialProperty.MP_NORMAL)
    mel.connect_material_property(msk, "B", unreal.MaterialProperty.MP_METALLIC)
    mel.recompile_material(mat)
    eal.save_loaded_asset(mat, only_if_is_dirty=False)
    return mat


def facade_material(defaults):
    """/Game/Environments/NexusCity/M_SOFacade: building walls. UV0 (unit-footprint facade coordinates) and UV1.x
    (1: the face runs along the width) become metres with the instance's custom data (0 width, 1 depth, 2 height in
    m, 3 seed, 4 wear, 5 boarded, 6 lit share, 7 base height above the street), so bays (Bay m) and floors (Floor m) keep their size on every lot.
    Wear streaks the walls down from the openings, splashes dirt up from the street and leaves patches of repair;
    boarded puts plywood over the glass (abandoned buildings). The mask's R marks glass: a hash per window, building
    and face lights the lit share of the rooms, scaled by Night (set by ASONexusCity)."""
    mat = _material("/Game/Environments/NexusCity/M_SOFacade", {"used_with_instanced_static_meshes": True})
    S = unreal.MaterialSamplerType
    u0 = mel.create_material_expression(mat, unreal.MaterialExpressionTextureCoordinate, -1500, -100)
    u1 = mel.create_material_expression(mat, unreal.MaterialExpressionTextureCoordinate, -1500, 0)
    u1.set_editor_property("coordinate_index", 1)
    cd = {}
    for i, (n, default) in enumerate((("W", 20.0), ("D", 20.0), ("H", 60.0), ("Seed", 0.0), ("Wear", 0.2), ("Boarded", 0.0), ("Lit", 0.25), ("Z0", 0.0))):
        e = mel.create_material_expression(mat, unreal.MaterialExpressionPerInstanceCustomData, -1500, 120 + i * 90)
        e.set_editor_property("data_index", i)
        e.set_editor_property("const_default_value", default)
        cd[n] = e
    bay = _param(mat, unreal.MaterialExpressionScalarParameter, "Bay", 3.6, -1500, 500)
    floor = _param(mat, unreal.MaterialExpressionScalarParameter, "Floor", 3.6, -1500, 580)
    uv = _custom(mat, FACADE_UV_HLSL, ("U0", "U1", "W", "D", "H", "Bay", "Floor"), unreal.CustomMaterialOutputType.CMOT_FLOAT2, -1150, 0)
    for n, e in (("U0", u0), ("U1", u1), ("Bay", bay), ("Floor", floor)):
        mel.connect_material_expressions(e, "", uv, n)
    for n in ("W", "D", "H"):
        mel.connect_material_expressions(cd[n], "", uv, n)
    col = _param(mat, unreal.MaterialExpressionTextureSampleParameter2D, "ColorTex", (defaults["white"], S.SAMPLERTYPE_COLOR), -850, -250)
    nrm = _param(mat, unreal.MaterialExpressionTextureSampleParameter2D, "NormalTex", (defaults["normal"], S.SAMPLERTYPE_NORMAL), -850, 50)
    msk = _param(mat, unreal.MaterialExpressionTextureSampleParameter2D, "MaskTex", (defaults["mask"], S.SAMPLERTYPE_MASKS), -850, 350)
    for t in (col, nrm, msk):
        mel.connect_material_expressions(uv, "", t, "UVs")
    tint = _param(mat, unreal.MaterialExpressionVectorParameter, "Tint", (1, 1, 1, 1), -850, -450)
    z0 = cd["Z0"]                                                                          # height of this part's base
    c = _custom(mat, FACADE_COLOR_HLSL, ("C", "T", "M", "U0", "U1", "W", "D", "H", "Seed", "Wear", "Boarded", "Bay", "Floor", "Z0"),
                unreal.CustomMaterialOutputType.CMOT_FLOAT3, -500, -300)
    for n, e, pin in (("C", col, "RGB"), ("T", tint, ""), ("M", msk, "R"), ("U0", u0, ""), ("U1", u1, ""), ("Bay", bay, ""), ("Floor", floor, ""), ("Z0", z0, "")):
        mel.connect_material_expressions(e, pin, c, n)
    for n in ("W", "D", "H", "Seed", "Wear", "Boarded"):
        mel.connect_material_expressions(cd[n], "", c, n)
    mel.connect_material_property(c, "", unreal.MaterialProperty.MP_BASE_COLOR)
    mel.connect_material_property(nrm, "RGB", unreal.MaterialProperty.MP_NORMAL)
    mel.connect_material_property(msk, "G", unreal.MaterialProperty.MP_ROUGHNESS)
    mel.connect_material_property(msk, "B", unreal.MaterialProperty.MP_METALLIC)
    lit = _custom(mat, FACADE_LIT_HLSL, ("U0", "U1", "W", "D", "H", "Seed", "Bay", "Floor", "M", "Lit", "Glow", "Night", "Boarded"),
                  unreal.CustomMaterialOutputType.CMOT_FLOAT3, -500, 300)
    for n, e in (("U0", u0), ("U1", u1), ("Bay", bay), ("Floor", floor)):
        mel.connect_material_expressions(e, "", lit, n)
    for n in ("W", "D", "H", "Seed", "Lit", "Boarded"):
        mel.connect_material_expressions(cd[n], "", lit, n)
    mel.connect_material_expressions(msk, "R", lit, "M")
    for i, (n, v) in enumerate((("Glow", 1.4), ("Night", 0.0))):
        mel.connect_material_expressions(_param(mat, unreal.MaterialExpressionScalarParameter, n, v, -850, 650 + i * 80), "", lit, n)
    mel.connect_material_property(lit, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    mel.recompile_material(mat)
    eal.save_loaded_asset(mat, only_if_is_dirty=False)
    return mat


def car_paint_material():
    """/Game/Environments/NexusCity/M_SOCarPaint: the city's parked cars, each painted by its instance's custom data
    (0..2 = linear RGB)."""
    mat = _material("/Game/Environments/NexusCity/M_SOCarPaint", {"used_with_instanced_static_meshes": True})
    rgb = []
    for i, d in enumerate((.5, .5, .5)):
        e = mel.create_material_expression(mat, unreal.MaterialExpressionPerInstanceCustomData, -700, i * 90)
        e.set_editor_property("data_index", i)
        e.set_editor_property("const_default_value", d)
        rgb.append(e)
    ap = mel.create_material_expression(mat, unreal.MaterialExpressionAppendVector, -450, 40)
    mel.connect_material_expressions(rgb[0], "", ap, "A")
    mel.connect_material_expressions(rgb[1], "", ap, "B")
    ap2 = mel.create_material_expression(mat, unreal.MaterialExpressionAppendVector, -250, 60)
    mel.connect_material_expressions(ap, "", ap2, "A")
    mel.connect_material_expressions(rgb[2], "", ap2, "B")
    mel.connect_material_property(ap2, "", unreal.MaterialProperty.MP_BASE_COLOR)
    mel.connect_material_property(_param(mat, unreal.MaterialExpressionScalarParameter, "Metallic", .55, -450, 300), "", unreal.MaterialProperty.MP_METALLIC)
    mel.connect_material_property(_param(mat, unreal.MaterialExpressionScalarParameter, "Roughness", .32, -450, 380), "", unreal.MaterialProperty.MP_ROUGHNESS)
    mel.recompile_material(mat)
    eal.save_loaded_asset(mat, only_if_is_dirty=False)
    return mat


def vehicles_trees_street(master, dest):
    """The city's trees / shrubs (tools/blender/city_trees.py, on M_SOFoliage: they sway in the weather's wind) and,
    once the traffic stage brings them, its vehicles (Vehicles/; paint cv_paint per instance on M_SOCarPaint, glass
    opaque for Nanite)."""
    paint = car_paint_material()
    foliage = foliage_material(default_textures(), weather_params())
    used = set()
    binf = os.path.join(PROJECT, "Data", "nexus_instances.bin")
    if os.path.exists(binf):                                 # only what nexus_dress.py places
        with open(binf, "rb") as f:
            f.read(4)
            n = int.from_bytes(f.read(4), "little")
            used = {m["name"] for m in json.loads(f.read(n).decode())["meshes"]}
    count = 0
    for sub in ("Vehicles", "Trees"):
        src = os.path.join(SOURCE, "NexusCity", sub)
        if not os.path.isdir(src):
            log(f"NexusCity: {sub} skipped")
            continue
        folder = f"{dest}/{sub}"
        ensure_dir(folder)
        manifest = load_json(os.path.join(src, "export_fbx.json"))
        materials = load_json(os.path.join(src, "materials.json"))
        tex = import_textures_for(src, materials, folder + "/Textures")
        inst = {}
        for key, m in materials.items():
            k = base_slot(key)
            if k == "cv_paint":
                inst[k] = paint
                continue
            m = dict(m)
            if k == "cv_glass":
                m.update(alphaMode="OPAQUE")
            inst[k] = make_instance(foliage if sub == "Trees" else master, folder, k, m, tex)
        for a in manifest["assets"]:
            name = os.path.splitext(a["file"])[0]
            if used and name not in used:
                continue
            if eal.does_asset_exist(f"{folder}/SM_{name}"):
                eal.delete_asset(f"{folder}/SM_{name}")
            mesh = import_static(src, a["file"], folder, f"SM_{name}", inst)
            _nanite(mesh, sub != "Trees")
            count += 1
    return count


def _city_instance(parent, dest, name, params, textures):
    path = f"{dest}/MI_{name}"
    mi = eal.load_asset(path) if eal.does_asset_exist(path) else tools.create_asset(
        f"MI_{name}", dest, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    mel.set_material_instance_parent(mi, parent)
    for k, v in params.items():
        mel.set_material_instance_scalar_parameter_value(mi, k, float(v))
    for k, t in textures.items():
        if t:
            mel.set_material_instance_texture_parameter_value(mi, k, t)
    mel.update_material_instance(mi)
    eal.save_loaded_asset(mi, only_if_is_dirty=False)
    return mi


def _nanite(mesh, collide):
    ns = mesh.get_editor_property("nanite_settings")
    ns.set_editor_property("enabled", True)
    mesh.set_editor_property("nanite_settings", ns)
    if collide:
        body = mesh.get_editor_property("body_setup")
        if body:
            body.set_editor_property("collision_trace_flag", unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
    eal.save_loaded_asset(mesh, only_if_is_dirty=False)


def nexus_city(master, defaults):
    """tools/blender/nexus_city.py (kit + tiles, through export_fbx.py) -> /Game/Environments/NexusCity: SM_NCB_*
    buildings, SM_NCK_* street pieces, Tiles/SM_NCT_* plan tiles and SM_NCL_land; ASONexusCity places them from
    Data/nexus_plan.json + Data/nexus_city.json. Everything is Nanite with complex-as-simple collision."""
    dest = "/Game/Environments/NexusCity"
    city = load_json(os.path.join(PROJECT, "Data", "nexus_city.json"))
    kit_src, tile_src = os.path.join(SOURCE, "NexusCity", "Kit"), os.path.join(SOURCE, "NexusCity", "Tiles")
    if not os.path.isdir(kit_src) or not os.path.isdir(tile_src):
        log("NexusCity: skipped (run tools/blender/export_unreal.sh)")
        return
    ensure_dir(dest)
    ensure_dir(dest + "/Textures")
    ensure_dir(dest + "/Tiles")
    ground, facade = ground_material(defaults), facade_material(defaults)

    def tex(stem, kind):
        f = os.path.join(REPO_TEXTURES, stem)
        if not os.path.exists(f):
            return None
        return import_texture(f, dest + "/Textures", "T_" + os.path.splitext(stem)[0], kind)

    inst = {}
    for name, tiling in city["ground"].items():
        src = "nx_rock" if name == "nc_rock" else name
        inst[name] = _city_instance(ground, dest, name, {"TilingM": tiling}, {
            "ColorTex": tex(src + "_c.jpg", "color"), "NormalTex": tex(src + "_n.png", "normal") or tex(src + "_n.jpg", "normal"),
            "MaskTex": tex(src + "_m.png", "mask")})
    for name, (bay, floor) in city["facade"].items():
        inst[name] = _city_instance(facade, dest, name, {"Bay": bay, "Floor": floor}, {
            "ColorTex": tex(name + "_c.jpg", "color"), "NormalTex": tex(name + "_n.png", "normal"), "MaskTex": tex(name + "_m.png", "mask")})
    count = vehicles_trees_street(master, dest)
    for src, folder in ((kit_src, dest), (tile_src, dest + "/Tiles")):
        manifest = load_json(os.path.join(src, "export_fbx.json"))
        materials = load_json(os.path.join(src, "materials.json"))
        for key, m in materials.items():
            k = base_slot(key)
            if k not in inst:
                plain = dict(m, baseColorTex=None, normalTex=None, mrTex=None)
                inst[k] = make_instance(master, dest, k, plain, {})
        for a in manifest["assets"]:
            name = os.path.splitext(a["file"])[0]
            # a fresh import: re-importing over an existing mesh keeps its old material slots (tiles change content)
            if eal.does_asset_exist(f"{folder}/SM_{name}"):
                eal.delete_asset(f"{folder}/SM_{name}")
            mesh = import_static(src, a["file"], folder, f"SM_{name}", inst)
            _nanite(mesh, True)
            count += 1
    eal.save_directory(dest, only_if_is_dirty=False, recursive=True)
    log(f"NexusCity: {count} meshes")


def ui_materials():
    """/Game/UI/M_UI_Stage: the loadout screen's live character picture. The scene capture stores inverse opacity in
    alpha (1 where it drew nothing), so the material shows the colour with opacity = 1 - alpha."""
    ensure_dir("/Game/UI")
    path = "/Game/UI/M_UI_Stage"
    if eal.does_asset_exist(path):
        mat = eal.load_asset(path)
        mel.delete_all_material_expressions(mat)
    else:
        mat = tools.create_asset("M_UI_Stage", "/Game/UI", unreal.Material, unreal.MaterialFactoryNew())
    mat.set_editor_property("material_domain", unreal.MaterialDomain.MD_UI)
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
    tex = mel.create_material_expression(mat, unreal.MaterialExpressionTextureSampleParameter2D, -500, 0)
    tex.set_editor_property("parameter_name", "Stage")
    tex.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_COLOR)
    inv = mel.create_material_expression(mat, unreal.MaterialExpressionOneMinus, -200, 150)
    mel.connect_material_expressions(tex, "A", inv, "")
    mel.connect_material_property(tex, "RGB", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    mel.connect_material_property(inv, "", unreal.MaterialProperty.MP_OPACITY)
    mel.recompile_material(mat)
    eal.save_loaded_asset(mat, only_if_is_dirty=False)
    log("UI materials ready")


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
    hair = hair_material(defaults)
    PARENT_FOR.update({"hair": hair, "hair__cap": hair})
    # SO_IMPORT_ONLY=arms,weapons,... re-imports just those steps (default: everything).
    only = {s.strip() for s in os.environ.get("SO_IMPORT_ONLY", "").split(",") if s.strip()}
    want = lambda step: not only or step in only
    if want("player"):
        for sex in ("male", "female"):
            player_wardrobe(sex, master)
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
    if want("ui"):
        ui_materials()
    if want("nexus"):
        nexus(master)
    if want("nexuscity"):
        nexus_city(master, defaults)
    log("done")


main()
