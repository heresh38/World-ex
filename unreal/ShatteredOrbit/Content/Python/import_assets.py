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
import glob
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

# Weapon and loot numbers come from Data/game_data.json: that file is their source (edit it, then re-import).

# Creature flesh: the GLBs ship without images; enemies.js applies these hx_* sets by material name.
FLESH = {"alien_skin": "hx_flesh", "alien_hide": "hx_skin", "alien_plate": "hx_chitin", "alien_bone": "hx_bone", "alien_sac": "hx_sac",
         # the Altered (altered.py)
         "alt_skin": "hx_skin", "alt_flesh": "hx_flesh", "alt_plate": "hx_chitin", "alt_bone": "hx_bone", "alt_rag": "hx_rag"}
ALTERED = ("Remnant", "Veilborn", "Bulwark", "Colossus", "Bearer")

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
    elif kind == "objnormal":
        # a high-poly's normals in the asset's own frame (bakekit.bake_highpoly_normals): linear, BC7, never flipped
        tex.set_editor_property("srgb", False)
        tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_BC7)
    if "_skin_" in name.lower():
        if "_skin_face_" in name.lower():
            # the face's maps are held at 4K (0.13 mm a texel): the brows are drawn into them hair by hair, a hair about
            # a texel wide; at 2K, packed as BC1 (4 x 4 texel blocks of two values each), every hair came out a chain of
            # millimetre blocks. Its packed map (R occlusion, G roughness, B the brows) is BC7: its channels kept apart
            if "_orm" in name.lower():
                tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_BC7)
        else:
            # the body's skin maps are written at 4K; the game holds them at 2K (video memory)
            tex.set_editor_property("max_texture_size", 2048)
    if "hair" in name.lower():
        # strand cards: smaller mips keep the strands' alpha coverage (plain averaging thins hair out with distance)
        try:
            tex.set_editor_property("do_scale_mips_for_alpha_coverage", True)
            tex.set_editor_property("alpha_coverage_thresholds", unreal.Vector4(0, 0, 0, 0.5))
        except Exception as e:  # (older engines)
            log(f"hair texture {name}: no alpha coverage mips ({e})")
    eal.save_loaded_asset(tex, only_if_is_dirty=False)
    return tex


def default_textures():
    ensure_dir("/Game/Materials")
    folder = os.path.join(SOURCE, "_Defaults")
    write_png(os.path.join(folder, "T_White.png"), (255, 255, 255, 255))
    write_png(os.path.join(folder, "T_WhiteMask.png"), (255, 255, 255, 255))
    write_png(os.path.join(folder, "T_FlatNormal.png"), (128, 128, 255, 255))
    write_png(os.path.join(folder, "T_Clear.png"), (255, 255, 255, 0))
    write_png(os.path.join(folder, "T_FlatObjNormal.png"), (128, 128, 255, 255))
    return {
        "clear": import_texture(os.path.join(folder, "T_Clear.png"), "/Game/Materials", "T_Clear", "color"),
        "white": import_texture(os.path.join(folder, "T_White.png"), "/Game/Materials", "T_White", "color"),
        "mask": import_texture(os.path.join(folder, "T_WhiteMask.png"), "/Game/Materials", "T_WhiteMask", "mask"),
        "normal": import_texture(os.path.join(folder, "T_FlatNormal.png"), "/Game/Materials", "T_FlatNormal", "normal"),
        "objnormal": import_texture(os.path.join(folder, "T_FlatObjNormal.png"), "/Game/Materials", "T_FlatObjNormal", "objnormal"),
    }


# ---------------------------------------------------------------- master material


# An asset's OWN maps (tools/blender/bakekit.py, gunpaint.py), read on UV 1 when UA (UniqueAmount) is 1:
# U1 = occlusion / edge wear / dirt, U2 = handling / heat / paint. With UA = 0 every line is what it was.
# (an own map's edge wear is CUT against the shared mask's chips: the map says how much, the chips where exactly, so
# the edge of a rubbed place is as fine as the chips at any distance, never the own map's texels)
WEAR_EDGE = ("saturate(max((1.0 - A) * (1.0 - UA) * EdgeWear * (0.45 + W.b * 1.1), "
             "saturate((U1.g * 1.5 + W.b - 1.0) * 3.0) * UA * saturate(0.4 + EdgeWear * 0.6)))")
WEAR_HLSL = {
    "color": """
float edge = """ + WEAR_EDGE + """;
float g = saturate(W.g * Grime * (1.0 - 0.6 * UA) + U1.b * UA * 0.8);
float s = W.r * Scratches * (1.0 - 0.7 * UA);
float3 c = C * lerp(float3(1.0, 1.0, 1.0), float3(0.5, 0.46, 0.4), g);
c *= lerp(1.0, 0.50, U1.b * UA);
float h = U2.g * UA * WearMetal;
float3 hc = lerp(float3(1.0, 1.0, 1.0), float3(0.80, 0.62, 0.40), saturate(h * 2.2));
hc = lerp(hc, float3(0.42, 0.48, 0.78), saturate(h * 2.2 - 1.1));
c *= hc;
float3 bare = lerp(float3(0.6, 0.6, 0.58), saturate(C * 1.7 + 0.1), 1.0 - WearMetal);
c = lerp(c, bare, saturate(edge + s * 0.5));
return lerp(c, float3(0.86, 0.85, 0.80), saturate((U2.b - 0.35) * 3.0) * UA);
""",
    "metal": """
float edge = """ + WEAR_EDGE + """;
return lerp(lerp(M, max(M, WearMetal), edge), 0.0, saturate((U2.b - 0.35) * 3.0) * UA);
""",
    "rough": """
float edge = """ + WEAR_EDGE + """;
float r = saturate(lerp(R + W.g * Grime * 0.3 + U1.b * UA * 0.18, 0.3, saturate(edge * 0.8 + W.r * Scratches * (1.0 - 0.7 * UA) * 0.45)));
r = lerp(r, r * 0.55, U2.r * UA);
return lerp(r, 0.5, saturate((U2.b - 0.35) * 3.0) * UA);
""",
}
# The relief of an asset's own height map (UV 1), bent into the normal without a tangent frame of its own (the
# surface's own derivatives): N the world normal, WP the world position, H the height, K centimetres to the unit.
# The high-poly's normal (an asset's own map UniqueNormalTex on UV 1, in the asset's frame, turned to world space): the
# surface normal so far N (tiling set + detail, world) is turned by the rotation that takes the game model's own
# normal V onto the high-poly's O, by UNA. The tiling detail rides on the rounded edges; with UNA = 0 nothing changes.
HIGHPOLY_HLSL = """
float3 v = normalize(V);
float3 h = normalize(lerp(v, normalize(O), UNA));
float3 ax = cross(v, h);
float s = length(ax);
if (s < 1e-5) return N;
ax /= s;
float c = dot(v, h);
return normalize(N * c + cross(ax, N) * s + ax * dot(ax, N) * (1.0 - c));
"""
# the map's colour to a normal in the mesh's own frame (Blender X left, Y back, Z up -> the imported mesh: X, -Y, Z)
OBJNORMAL_HLSL = """
float3 o = T * 2.0 - 1.0;
return float3(o.x, -o.y, o.z);
"""

BUMP_HLSL = """
float3 dpx = ddx(WP);
float3 dpy = ddy(WP);
float hx = ddx(H);
float hy = ddy(H);
float3 n = normalize(N);
float3 r1 = cross(dpy, n);
float3 r2 = cross(n, dpx);
float det = dot(dpx, r1);
float3 grad = sign(det) * (hx * r1 + hy * r2);
return normalize(abs(det) * n - K * grad);
"""

SURFACE_HLSL = {
    "color": """
float cav = saturate(length(D.xy) * 1.8 * S) * K;
return C * (1.0 - cav) * (1.0 + (M.r - 0.5) * 2.0 * A);
""",
    "rough": """
float cav = saturate(length(D.xy) * 1.8 * S) * K;
return saturate(R + cav * 0.12 + (M.g - 0.5) * 0.35 * A);
""",
    "normal": """
return normalize(float3(B.xy + D.xy * S, B.z));
""",
    "ao": """
return lerp(1.0, O, K) * lerp(1.0, U, UA);
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
    # What the owner's texture rules ask of every surface (docs/art/TEXTURE_RULES.md). Each is OFF until an instance
    # asks for it (the defaults leave a material exactly as it was): parallax from the set's height map (Parallax =
    # its depth over its tile), ambient occlusion from the mask's red (AOAmount), a detail normal for close up
    # (DetailTex at DetailScale repeats a tile, DetailStrength; DetailCavity darkens what it buries), and a macro
    # variation at a scale that is not a whole number of tiles (MacroTex R tone, G roughness; MacroAmount).
    uv0 = mel.create_material_expression(mat, unreal.MaterialExpressionTextureCoordinate, -1900, -300)
    height = tex_param("HeightTex", S.SAMPLERTYPE_MASKS, defaults["mask"], -1700, -520)
    bump = mel.create_material_expression(mat, unreal.MaterialExpressionBumpOffset, -1350, -420)
    bump.set_editor_property("reference_plane", 0.5)
    mel.connect_material_expressions(uv0, "", bump, "Coordinate")
    mel.connect_material_expressions(height, "R", bump, "Height")
    mel.connect_material_expressions(scalar("Parallax", 0.0, -1700, -300), "", bump, "HeightRatioInput")
    base = tex_param("BaseColorTex", S.SAMPLERTYPE_COLOR, defaults["white"], -900, -300)
    mel.connect_material_expressions(bump, "", base, "UVs")
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
    mel.connect_material_expressions(bump, "", mr, "UVs")
    metal = mul(mr, "B", scalar("Metallic", 0.0, -900, 560), "", -650, 360)
    rough = mul(mr, "G", scalar("Roughness", 0.5, -900, 640), "", -650, 480)
    # the specular level (0.5 the engine's default; a fabric's is lower: the undersuit sets .3, or it shone like satin)
    mel.connect_material_property(scalar("Specular", 0.5, -900, 700), "", unreal.MaterialProperty.MP_SPECULAR)

    # Wear (guns): edges rubbed bare where the vertex colour alpha says (1 - edge wear), scratches and grime from the
    # shared wear mask (R scratches, G grime, B chip breakup). Every amount is 0 by default: no effect elsewhere.
    uv = mel.create_material_expression(mat, unreal.MaterialExpressionTextureCoordinate, -1300, 1500)
    tiling = scalar("WearTiling", 3.0, -1300, 1600)
    uvs = mul(uv, "", tiling, "", -1150, 1520)
    wear = tex_param("WearTex", S.SAMPLERTYPE_MASKS, defaults["mask"], -1000, 1500)
    mel.connect_material_expressions(uvs, "", wear, "UVs")
    amounts = {n: scalar(n, 0.0, -1000, 1700 + i * 80) for i, n in enumerate(("EdgeWear", "Scratches", "Grime", "WearMetal"))}
    # an asset's own maps, on its second UV set
    uv1 = mel.create_material_expression(mat, unreal.MaterialExpressionTextureCoordinate, -1300, 3100)
    uv1.set_editor_property("coordinate_index", 1)
    own = []
    for i in range(3):
        t = tex_param(f"UniqueTex{i + 1}", S.SAMPLERTYPE_MASKS, defaults["mask"], -1000, 3100 + i * 230)
        mel.connect_material_expressions(uv1, "", t, "UVs")
        own.append(t)
    uamt = scalar("UniqueAmount", 0.0, -1000, 3800)
    hpn_tex = tex_param("UniqueNormalTex", S.SAMPLERTYPE_LINEAR_COLOR, defaults["objnormal"], -1000, 3950)
    mel.connect_material_expressions(uv1, "", hpn_tex, "UVs")
    hpn_amt = scalar("UniqueNormalAmount", 0.0, -1000, 4180)

    def wear_node(kind, inputs, out_type, y):
        node = mel.create_material_expression(mat, unreal.MaterialExpressionCustom, -250, y)
        node.set_editor_property("code", WEAR_HLSL[kind])
        node.set_editor_property("output_type", out_type)
        ins = []
        for name in list(inputs) + ["A", "W", "EdgeWear", "Scratches", "Grime", "WearMetal", "U1", "U2", "UA"]:
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
        mel.connect_material_expressions(own[0], "RGB", node, "U1")
        mel.connect_material_expressions(own[1], "RGB", node, "U2")
        mel.connect_material_expressions(uamt, "", node, "UA")
        return node
    F = unreal.CustomMaterialOutputType
    worn_colour = wear_node("color", {"C": (colour, "")}, F.CMOT_FLOAT3, -200)
    worn_metal = wear_node("metal", {"M": (metal, "")}, F.CMOT_FLOAT1, 360)
    worn_rough = wear_node("rough", {"R": (rough, "")}, F.CMOT_FLOAT1, 480)
    duv = mul(uv0, "", scalar("DetailScale", 8.0, -1900, 2300), "", -1650, 2300)
    detail = tex_param("DetailTex", S.SAMPLERTYPE_NORMAL, defaults["normal"], -1400, 2300)
    mel.connect_material_expressions(duv, "", detail, "UVs")
    dstr = scalar("DetailStrength", 0.0, -1400, 2520)
    dcav = scalar("DetailCavity", 0.0, -1400, 2600)
    muv = mul(uv0, "", scalar("MacroScale", 0.173, -1900, 2760), "", -1650, 2760)
    macro = tex_param("MacroTex", S.SAMPLERTYPE_MASKS, defaults["mask"], -1400, 2760)
    mel.connect_material_expressions(muv, "", macro, "UVs")
    mamt = scalar("MacroAmount", 0.0, -1400, 2980)

    def finish(code, inputs, out_type, y):
        node = _custom(mat, code, [n for n, _, _ in inputs], out_type, 150, y)
        for n, src, pin in inputs:
            mel.connect_material_expressions(src, pin, node, n)
        return node
    fc = finish(SURFACE_HLSL["color"], (("C", worn_colour, ""), ("D", detail, "RGB"), ("S", dstr, ""), ("K", dcav, ""), ("M", macro, "RGB"), ("A", mamt, "")),
                F.CMOT_FLOAT3, -200)
    fr = finish(SURFACE_HLSL["rough"], (("R", worn_rough, ""), ("D", detail, "RGB"), ("S", dstr, ""), ("K", dcav, ""), ("M", macro, "RGB"), ("A", mamt, "")),
                F.CMOT_FLOAT1, 480)
    mel.connect_material_property(fc, "", unreal.MaterialProperty.MP_BASE_COLOR)
    mel.connect_material_property(worn_metal, "", unreal.MaterialProperty.MP_METALLIC)
    mel.connect_material_property(fr, "", unreal.MaterialProperty.MP_ROUGHNESS)
    ao = finish(SURFACE_HLSL["ao"], (("O", mr, "R"), ("K", scalar("AOAmount", 0.0, -900, 720), ""), ("U", own[0], "R"), ("UA", uamt, "")),
                F.CMOT_FLOAT1, 620)
    mel.connect_material_property(ao, "", unreal.MaterialProperty.MP_AMBIENT_OCCLUSION)

    normal = tex_param("NormalTex", S.SAMPLERTYPE_NORMAL, defaults["normal"], -900, 760)
    mel.connect_material_expressions(bump, "", normal, "UVs")
    fn = finish(SURFACE_HLSL["normal"], (("B", normal, "RGB"), ("D", detail, "RGB"), ("S", dstr, "")), F.CMOT_FLOAT3, 760)
    final_normal = fn
    try:
        # the relief of the asset's own height map (engraving, a weld's bead): bent in world space, back to tangent
        # (named `relief`: `bump` is the parallax node above, which the emissive map's UVs are still to be given)
        to_world = mel.create_material_expression(mat, unreal.MaterialExpressionTransform, 380, 760)
        to_world.set_editor_property("transform_source_type", unreal.MaterialVectorCoordTransformSource.TRANSFORMSOURCE_TANGENT)
        to_world.set_editor_property("transform_type", unreal.MaterialVectorCoordTransform.TRANSFORM_WORLD)
        mel.connect_material_expressions(fn, "", to_world, "")
        # the high-poly's normal: decoded, its frame to world, the surface turned onto it
        hp_obj = _custom(mat, OBJNORMAL_HLSL, ("T",), F.CMOT_FLOAT3, 380, 1180)
        mel.connect_material_expressions(hpn_tex, "RGB", hp_obj, "T")
        hp_world = mel.create_material_expression(mat, unreal.MaterialExpressionTransform, 560, 1180)
        hp_world.set_editor_property("transform_source_type", unreal.MaterialVectorCoordTransformSource.TRANSFORMSOURCE_LOCAL)
        hp_world.set_editor_property("transform_type", unreal.MaterialVectorCoordTransform.TRANSFORM_WORLD)
        mel.connect_material_expressions(hp_obj, "", hp_world, "")
        vnormal = mel.create_material_expression(mat, unreal.MaterialExpressionVertexNormalWS, 560, 1320)
        turned = _custom(mat, HIGHPOLY_HLSL, ("N", "V", "O", "UNA"), F.CMOT_FLOAT3, 560, 760)
        mel.connect_material_expressions(to_world, "", turned, "N")
        mel.connect_material_expressions(vnormal, "", turned, "V")
        mel.connect_material_expressions(hp_world, "", turned, "O")
        mel.connect_material_expressions(hpn_amt, "", turned, "UNA")
        wpos = mel.create_material_expression(mat, unreal.MaterialExpressionWorldPosition, 380, 900)
        bump_k = mul(scalar("UniqueBump", 0.40, 380, 1040), "", uamt, "", 560, 1040)
        relief = _custom(mat, BUMP_HLSL, ("N", "WP", "H", "K"), F.CMOT_FLOAT3, 720, 800)
        mel.connect_material_expressions(turned, "", relief, "N")
        mel.connect_material_expressions(wpos, "", relief, "WP")
        mel.connect_material_expressions(own[2], "R", relief, "H")
        mel.connect_material_expressions(bump_k, "", relief, "K")
        to_tangent = mel.create_material_expression(mat, unreal.MaterialExpressionTransform, 960, 800)
        to_tangent.set_editor_property("transform_source_type", unreal.MaterialVectorCoordTransformSource.TRANSFORMSOURCE_WORLD)
        to_tangent.set_editor_property("transform_type", unreal.MaterialVectorCoordTransform.TRANSFORM_TANGENT)
        mel.connect_material_expressions(relief, "", to_tangent, "")
        final_normal = to_tangent
    except Exception as e:                                      # (the relief is lost, the material is not)
        log(f"master material: the own-map relief could not be built ({e})")
    mel.connect_material_property(final_normal, "", unreal.MaterialProperty.MP_NORMAL)

    emis = tex_param("EmissiveTex", S.SAMPLERTYPE_COLOR, defaults["white"], -900, 1000)
    mel.connect_material_expressions(bump, "", emis, "UVs")
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


def skin_material(defaults):
    """/Game/Materials/M_SOSkin: the players' skin (skin, skin_face and every skin__<region> section): Unreal's
    subsurface-profile shading (light carried under the skin: soft, red in the shadows' edges) with the profile
    SP_SOSkin, the same parameter names as the master (BaseColorTex x BaseColorTint, NormalTex, MRTex: R occlusion,
    G roughness x Roughness), a skin's specular (F0 .028 = .35), AOAmount (1) how much of the map's occlusion is used"""
    path = "/Game/Materials/M_SOSkin"
    if eal.does_asset_exist(path):
        mat = eal.load_asset(path)
        mel.delete_all_material_expressions(mat)
    else:
        mat = tools.create_asset("M_SOSkin", "/Game/Materials", unreal.Material, unreal.MaterialFactoryNew())
    sp_path = "/Game/Materials/SP_SOSkin"
    if eal.does_asset_exist(sp_path):
        sp = eal.load_asset(sp_path)
    else:
        sp = tools.create_asset("SP_SOSkin", "/Game/Materials", unreal.SubsurfaceProfile, unreal.SubsurfaceProfileFactory())
    try:
        # a skin's own scattering, not the engine's default wax: a shorter radius, warm where the light comes back out
        st = sp.get_editor_property("settings")
        st.set_editor_property("scatter_radius", 0.75)
        st.set_editor_property("subsurface_color", unreal.LinearColor(0.78, 0.55, 0.45, 1.0))
        st.set_editor_property("falloff_color", unreal.LinearColor(1.0, 0.42, 0.30, 1.0))
        sp.set_editor_property("settings", st)
    except Exception as e:
        log(f"SP_SOSkin: default settings kept ({e})")
    eal.save_loaded_asset(sp, only_if_is_dirty=False)
    for prop, value in (("used_with_skeletal_mesh", True), ("used_with_morph_targets", True),
                        ("shading_model", unreal.MaterialShadingModel.MSM_SUBSURFACE_PROFILE), ("subsurface_profile", sp)):
        mat.set_editor_property(prop, value)
    E = lambda cls, x, y: mel.create_material_expression(mat, cls, x, y)
    S = unreal.MaterialSamplerType

    def tex(name, sampler, t, y):
        e = E(unreal.MaterialExpressionTextureSampleParameter2D, -900, y)
        e.set_editor_property("parameter_name", name)
        e.set_editor_property("texture", t)
        e.set_editor_property("sampler_type", sampler)
        return e

    def scalar(name, value, y):
        e = E(unreal.MaterialExpressionScalarParameter, -900, y)
        e.set_editor_property("parameter_name", name)
        e.set_editor_property("default_value", value)
        return e

    def mul(a, ao, b, bo, y):
        e = E(unreal.MaterialExpressionMultiply, -500, y)
        mel.connect_material_expressions(a, ao, e, "A")
        mel.connect_material_expressions(b, bo, e, "B")
        return e
    base = tex("BaseColorTex", S.SAMPLERTYPE_COLOR, defaults["white"], -400)
    tint = E(unreal.MaterialExpressionVectorParameter, -900, -160)
    tint.set_editor_property("parameter_name", "BaseColorTint")
    tint.set_editor_property("default_value", unreal.LinearColor(1, 1, 1, 1))
    nrm = tex("NormalTex", S.SAMPLERTYPE_NORMAL, defaults["normal"], 0)
    mel.connect_material_property(nrm, "RGB", unreal.MaterialProperty.MP_NORMAL)
    mr = tex("MRTex", S.SAMPLERTYPE_MASKS, defaults["mask"], 300)
    # the hair drawn on the skin (the Orion male's brows, hair by hair: the mask's B is how much of a texel is hair,
    # game.py brow_mask): the hair's own colour over the skin and its own roughness, by HairAmount (0 in the master:
    # the import turns it on for a face whose map carries the hairs; the creator colours them with HairColor)
    hair = mul(mr, "B", scalar("HairAmount", 0.0, 1100), "", 1000)
    hair_col = E(unreal.MaterialExpressionVectorParameter, -900, 1200)
    hair_col.set_editor_property("parameter_name", "HairColor")
    hair_col.set_editor_property("default_value", unreal.LinearColor(*BROW_TONE, 1.0))
    colour = E(unreal.MaterialExpressionLinearInterpolate, -300, -300)
    mel.connect_material_expressions(mul(base, "RGB", tint, "", -300), "", colour, "A")
    mel.connect_material_expressions(hair_col, "", colour, "B")
    mel.connect_material_expressions(hair, "", colour, "Alpha")
    mel.connect_material_property(colour, "", unreal.MaterialProperty.MP_BASE_COLOR)
    rough = E(unreal.MaterialExpressionLinearInterpolate, -300, 400)
    mel.connect_material_expressions(mul(mr, "G", scalar("Roughness", 1.0, 520), "", 400), "", rough, "A")
    mel.connect_material_expressions(scalar("HairRoughness", .45, 1300), "", rough, "B")
    mel.connect_material_expressions(hair, "", rough, "Alpha")
    mel.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
    ao = E(unreal.MaterialExpressionLinearInterpolate, -500, 650)
    ao.set_editor_property("const_a", 1.0)
    mel.connect_material_expressions(mr, "R", ao, "B")
    mel.connect_material_expressions(scalar("AOAmount", 1.0, 700), "", ao, "Alpha")
    mel.connect_material_property(ao, "", unreal.MaterialProperty.MP_AMBIENT_OCCLUSION)
    mel.connect_material_property(scalar("Specular", .35, 820), "", unreal.MaterialProperty.MP_SPECULAR)
    mel.connect_material_property(scalar("Scatter", .65, 900), "", unreal.MaterialProperty.MP_OPACITY)   # (the profile's amount:
    # at 1 the face was wax in daylight)
    mel.recompile_material(mat)
    eal.save_loaded_asset(mat, only_if_is_dirty=False)
    return mat


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
    tint.set_editor_property("default_value", unreal.LinearColor(*HAIR_TONE, 1))
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
    mel.connect_material_property(scalar("Scatter", 0.2, 120), "", unreal.MaterialProperty.MP_METALLIC)      # Hair: Scatter
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
        # alpha x AlphaGain (clamped) into the dither: strands are thinner than a pixel at a distance, so the raw alpha
        # alone dithers the hair see-through
        gain = E(unreal.MaterialExpressionMultiply, -700, 600)
        mel.connect_material_expressions(tex, "A", gain, "A")
        mel.connect_material_expressions(scalar("AlphaGain", 1.8, 680), "", gain, "B")
        sat = E(unreal.MaterialExpressionSaturate, -600, 600)
        mel.connect_material_expressions(gain, "", sat, "")
        ok = mel.connect_material_expressions(sat, "", dither, "Alpha Threshold")
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
    if "hair" in extra:
        mel.set_material_instance_scalar_parameter_value(mi, "HairAmount", float(extra["hair"]))
    if "specular" in extra:
        mel.set_material_instance_scalar_parameter_value(mi, "Specular", float(extra["specular"]))
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
        sm.set_editor_property("generate_lightmap_u_vs", False)   # (UV 1 is an asset's own set: bakekit.py; lighting is dynamic)
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
    objs = [unreal.load_asset(p) for p in paths]
    if skeletal:
        for o in objs:
            if isinstance(o, unreal.SkeletalMesh):
                fit_bodies(o)
    return objs


# Bones shorter than this (cm) share their parent's body. Small enough that a head, a hand and a foot get their own.
BODY_MIN_BONE = 10.0


def fit_bodies(mesh):
    """The physics bodies of a skeletal mesh fitted to what is drawn: one convex hull per bone (the editor module's
    USOEditorLibrary::FitBodies). The engine's automatic bodies are a few fat capsules: on the Colossus they stood up
    to a metre and a half in front of its surface and its head had none, so shots that passed it counted as hits and
    a head shot never was one. A mesh without a physics asset (a wardrobe piece, the arms) is left alone."""
    pa = mesh.get_editor_property("physics_asset")
    if not pa:
        return 0
    n = unreal.SOEditorLibrary.fit_bodies(mesh, BODY_MIN_BONE, 1, 24)
    eal.save_loaded_asset(pa, only_if_is_dirty=False)
    log(f"{mesh.get_name()}: {n} bodies fitted per bone")
    return n


def bodies():
    """Refits the bodies of every creature and both players that are already imported (SO_IMPORT_ONLY=bodies)."""
    names = ["Stalker"] + list(ALTERED) + ["PlayerMale", "PlayerFemale"]
    for name in names:
        path = f"/Game/Characters/{name}/SK_{name}"
        if eal.does_asset_exist(path):
            fit_bodies(eal.load_asset(path))
        else:
            log(f"{path}: not imported, skipped")


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
        # A mesh imported AGAIN keeps the slot names of its first import; what the file calls each slot NOW is its
        # imported name. Filled by the old name, a slot whose material had changed got the old material (the rifle's
        # olive grip came out in walnut). Slot names are an API (the game looks for gun_glow, gun_body, gun_lens):
        # they are set to the imported ones.
        mats = list(mesh.get_editor_property("static_materials"))
        renamed = False
        for i, slot in enumerate(mats):
            name = str(slot.get_editor_property("imported_material_slot_name"))
            if name in ("", "None"):
                name = str(slot.get_editor_property("material_slot_name"))
            if str(slot.get_editor_property("material_slot_name")) != name:
                slot.set_editor_property("material_slot_name", name)
                renamed = True
            mi = instances.get(base_slot(name))
            if mi:
                slot.set_editor_property("material_interface", mi)
            else:
                missing.append(name)
        try:
            mesh.set_editor_property("static_materials", mats)
        except Exception as e:
            log(f"  {mesh.get_name()}: slots not renamed ({e})")
            for i, slot in enumerate(mats):
                mi = slot.get_editor_property("material_interface")
                if mi:
                    mesh.set_material(i, mi)
        if renamed:
            log(f"  {mesh.get_name()}: slots renamed to the file's own: {[str(s.get_editor_property('material_slot_name')) for s in mats]}")
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
    # clips the model no longer has (an older clip set) are deleted, so nothing stale is left to load
    for path in eal.list_assets(dest + "/Anims", recursive=False, include_folder=False):
        name = path.split(".")[-1]
        if name.startswith(clip_prefix) and name[len(clip_prefix):] not in actions:
            eal.delete_asset(path.split(".")[0])
            log(f"{mesh_name}: removed old clip {name}")
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


HAIR_TONE = (0.020, 0.014, 0.010)     # dark brown, near black (the concept pair); the game may recolour it later
BROW_TONE = (0.032, 0.022, 0.016)     # the brows drawn on the face's skin: a dark brown (M_SOSkin HairColor)


def player_extra(key, m):
    if key in ("skin", "skin_face"):
        # (the body's own skin maps carry the colour; the flat tone only for a body exported without them; the
        # face's map carries the brows' hairs in its mask's B: HairAmount 1 shows them)
        return {"tint": [1.0, 1.0, 1.0] if m.get("baseColorTex") else list(SKIN_TONE),
                "hair": 1.0 if key == "skin_face" else 0.0}
    if key in ("hair", "hair__cap", "hair__brow", "hair__lash", "brow"):
        return {"tint": list(HAIR_TONE)}
    if key == "orion_suit":
        return {"specular": 0.3}                       # a woven fabric, not satin
    return None


# ---------------------------------------------------------------- modular players (wardrobe pieces)

# Outfit wear per material: (EdgeWear, Scratches, Grime, WearMetal, WearTiling). Plates rub through to metal at the
# edges and carry scratches; cloth only takes grime; glow, visor, skin and hair none.
ARMOUR_WEAR = {
    "orion_plate": (1.0, .45, .35, 1.0, .35), "orion_plate_white": (1.0, .40, .40, 1.0, .35),
    "orion_steel": (.8, .50, .30, 1.0, .40),
    "orion_coat": (0.0, .10, .45, 0.0, .30), "orion_white": (0.0, .10, .50, 0.0, .30), "orion_cloth": (0.0, .08, .45, 0.0, .30),
    "orion_black": (0.0, .05, .40, 0.0, .30), "orion_strap": (0.0, .20, .45, 0.0, .30),
    "orion_leather": (0.0, .35, .50, 0.0, .30), "orion_sole": (0.0, .10, .60, 0.0, .30),
}
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


def make_lods(mesh, count=4):
    """the third-person body and pieces get an automatic LOD chain (Unreal's skeletal reduction: each LOD about half
    the triangles of the one before); the first-person cuts are always close and keep their one LOD"""
    try:
        sub = unreal.get_editor_subsystem(unreal.SkeletalMeshEditorSubsystem)
        sub.regenerate_lod(mesh, new_lod_count=count, regenerate_even_if_imported=True, generate_base_lod=False)
        lods = [sub.get_num_verts(mesh, i) for i in range(sub.get_lod_count(mesh))]
        log(f"{mesh.get_name()}: LOD vertices {lods}")
    except Exception as e:                       # (the reduction plugin missing: the mesh keeps LOD0 only)
        log(f"{mesh.get_name()}: no LODs ({e})")


def player_pieces(spec):
    """Only some wardrobe pieces again (SO_IMPORT_ONLY=player_pieces SO_PLAYER_PIECES=female:top:orion,...): each
    piece's FBX over the mesh that is there, on the body's skeleton, with the material instances that are there.
    For work on one garment (tools/blender/hero/repiece.py): nothing else of the player is touched."""
    for one in [s.strip() for s in spec.split(",") if s.strip()]:
        sex, slot, item = one.split(":")
        Sex = sex.capitalize()
        src = os.path.join(SOURCE, "Characters", f"Player{Sex}")
        dest = f"/Game/Characters/Player{Sex}"
        body = unreal.load_asset(f"{dest}/SK_Player{Sex}")
        if not body or not os.path.isdir(src):
            log(f"Player{Sex} {slot} {item}: skipped (import the player first)")
            continue
        manifest = load_json(os.path.join(src, "export_fbx.json"))
        entry = next((a for a in manifest["assets"] if a.get("slot") == slot and a.get("item") == item), None)
        if not entry:
            log(f"Player{Sex} {slot} {item}: not in the export, skipped")
            continue
        mesh = import_piece(os.path.join(src, entry["file"]), dest + "/Wardrobe", f"SK_{Sex}_{slot}_{item}", body.get_editor_property("skeleton"))
        instances = {}
        for path in eal.list_assets(dest, recursive=False, include_folder=False):
            name = path.split("/")[-1].split(".")[0]
            if name.startswith("MI_"):
                instances[name[3:]] = eal.load_asset(path)
        assign_materials(mesh, instances)
        make_lods(mesh)
        eal.save_loaded_asset(mesh, only_if_is_dirty=False)
        log(f"SK_{Sex}_{slot}_{item}: piece re-imported")


def player_clips(sex):
    """Only the body's clips again (SO_IMPORT_ONLY=player_clips): the takes of the body FBX onto the skeleton that is
    already there, as Anims/A_Player<Sex>_<Clip>. For work on motion (tools/blender/hero/reclip.py): nothing else of
    the player is touched."""
    Sex = sex.capitalize()
    src = os.path.join(SOURCE, "Characters", f"Player{Sex}")
    dest = f"/Game/Characters/Player{Sex}"
    body = unreal.load_asset(f"{dest}/SK_Player{Sex}")
    if not body or not os.path.isdir(src):
        log(f"Player{Sex} clips: skipped (import the player first)")
        return
    manifest = load_json(os.path.join(src, "export_fbx.json"))
    entry = next(a for a in manifest["assets"] if a["name"] == "Body")
    ui = unreal.FbxImportUI()
    ui.set_editor_property("import_mesh", False)
    ui.set_editor_property("import_textures", False)
    ui.set_editor_property("import_materials", False)
    ui.set_editor_property("import_as_skeletal", True)
    ui.set_editor_property("automated_import_should_detect_type", False)
    ui.set_editor_property("mesh_type_to_import", unreal.FBXImportType.FBXIT_ANIMATION)
    ui.set_editor_property("skeleton", body.get_editor_property("skeleton"))
    ui.set_editor_property("import_animations", True)
    anim = ui.get_editor_property("anim_sequence_import_data")
    anim.set_editor_property("animation_length", unreal.FBXAnimationLengthImportType.FBXALIT_EXPORTED_TIME)
    anim.set_editor_property("import_bone_tracks", True)
    anim.set_editor_property("convert_scene_unit", False)
    tmp = dest + "/ClipsIn"
    if eal.does_directory_exist(tmp):
        eal.delete_directory(tmp)
    ensure_dir(tmp)
    ensure_dir(dest + "/Anims")
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", os.path.join(src, entry["file"]))
    task.set_editor_property("destination_path", tmp)
    task.set_editor_property("destination_name", f"Clip{Sex}")
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("save", False)
    task.set_editor_property("options", ui)
    tools.import_asset_tasks([task])
    actions = sorted(entry.get("actions", []), key=len, reverse=True)
    done = []
    for path in eal.list_assets(tmp, recursive=False, include_folder=False):
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
            eal.save_asset(target, only_if_is_dirty=False)
            done.append(clip)
    eal.delete_directory(tmp)
    log(f"Player{Sex}: {len(done)} clips ({', '.join(sorted(done))})")


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
    # (by their base names: a build whose stages ran again on a saved file wrote `eye.001` and `hair.002`, and the
    # lookups by `eye` and `hair` found no maps: a white eye, opaque hair cards)
    materials = {re.sub(r"[._]\d{3}$", "", k): v for k, v in materials.items()}
    meta = load_json(os.path.join(src, "wardrobe.json"))
    # start clean: a re-import over an older mesh keeps its material slots (the per-region skin sections would fold
    # into them) and the pieces must bind to the new skeleton
    if eal.does_directory_exist(dest):
        eal.delete_directory(dest)
    ensure_dir(dest)
    used = {base_slot(n) for a in manifest["assets"] for n in a["materials"]}
    tex = import_textures_for(src, materials, dest + "/Textures", used)
    instances = {}
    worn = wear_texture()
    for key in used:
        m = materials.get(key) or (materials.get("skin") if key == "skin_face" else None) or {}
        if not m and key in ("skin", "skin_face"):
            # the body's sections are skin__<region> in the file: they all carry the same skin maps
            m = materials.get("skin__head" if key == "skin_face" else "skin__chest") or {}
        instances[key] = make_instance(master, dest, key, m, tex, player_extra(key, m))
        amounts = ARMOUR_WEAR.get(key)
        if amounts and worn:
            # the outfit's wear (hero/finish.py writes the per-vertex edge wear and the paint): how far the edges
            # rub bare, scratches and grime from the shared mask, at a scale that suits world-sized cloth UVs
            mi = instances[key]
            mel.set_material_instance_texture_parameter_value(mi, "WearTex", worn)
            for name, value in zip(("EdgeWear", "Scratches", "Grime", "WearMetal", "WearTiling"), amounts):
                mel.set_material_instance_scalar_parameter_value(mi, name, float(value))
            mel.update_material_instance(mi)
            eal.save_loaded_asset(mi, only_if_is_dirty=False)

    # the body: skeleton, physics and clips
    body_entry = next(a for a in manifest["assets"] if a["name"] == "Body")
    objs = import_fbx(os.path.join(src, body_entry["file"]), dest, f"SK_Player{Sex}", True)
    body = next(o for o in objs if isinstance(o, unreal.SkeletalMesh))
    assign_materials(body, instances)
    make_lods(body)
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
        make_lods(mesh)
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
    # the Sarketh's orange lacquer (the owner: "the guns are brown, they should be orange"): kept, chipped little, little
    # grime, no bare metal under it: the body's heavy wear turned it brown in the game
    "gun_body__skr": (.35, .12, .10, 0),
    # a blade's mirror-polished stainless: kept bright and clean (the owner: "extremely shiny")
    "gun_steel__mirror": (.12, .05, .04, 1),
    # Ember Oath II's carbon fibre under a clear coat: a little wear on its edges, little grime
    "gun_body__skrcarbon": (.2, .08, .06, 0),
    "gun_steel": (.9, .3, .4, 1), "gun_parkerized": (.85, .32, .45, 1), "gun_dark": (.8, .3, .45, 1), "gun_metal": (.85, .3, .4, 1),
    "gun_trim": (.7, .25, .3, 1), "gun_body": (.75, .28, .45, 1), "gun_paint": (.75, .28, .45, 1), "gun_brass": (.5, .2, .35, 1),
    "gun_polymer_od": (.55, .22, .5, 0), "gun_polymer": (.55, .22, .5, 0), "gun_rubber": (.3, .1, .5, 0), "gun_wood": (.5, .2, .4, 0),
    "gun_sightpaint": (.3, .1, .3, 0),
}
_WEAR_TEX = {}


def wear_texture():
    if "mask" not in _WEAR_TEX:
        f = os.path.join(REPO_TEXTURES, "wear_mask_c.jpg")
        _WEAR_TEX["mask"] = import_texture(f, WEAPON_TEX, "T_wear_mask", "mask") if os.path.exists(f) else None
    return _WEAR_TEX["mask"]


def sampled(material, texture, uv, scale):
    """tell the texture streamer how this material reads this texture: which UV set, how many repeats across it
    (USOEditorLibrary::SetTextureSampling: the engine builds this only in an editor step the import never runs)"""
    try:
        unreal.SOEditorLibrary.set_texture_sampling(material, texture, uv, scale)
    except Exception as e:
        log(f"  {material.get_name()}: the streamer was not told about {texture.get_name()} ({e})")


def gun_instances(master, src, dest, materials, clear, model=None):
    tex = shared_textures(src, materials)
    out = {}
    worn = wear_texture()
    # the gun's own maps (tools/blender/gunpaint.py), when it has them: wear / dirt (m1) and the relief (m3) held at
    # 4096, handling / heat / paint (m2) at 2048. (m1 at 2048 was a texel of half a millimetre: grime in a cut mark
    # is what makes the mark read, and at that size a Sarketh mark on a pale shell was a smudge.)
    own = {}
    for k, hold in (("m1", 4096), ("m2", 2048), ("m3", 4096)):
        f = os.path.join(REPO_TEXTURES, f"{model}_u_{k}.png") if model else ""
        if f and os.path.exists(f):
            own[k] = import_texture(f, dest, f"T_{model}_u_{k}", "mask")
            own[k].set_editor_property("max_texture_size", hold)
            eal.save_loaded_asset(own[k], only_if_is_dirty=False)
    hp_file = os.path.join(REPO_TEXTURES, f"{model}_u_n.png") if model else ""
    hp_normals = import_texture(hp_file, dest, f"T_{model}_u_n", "objnormal") if hp_file and os.path.exists(hp_file) else None
    for k, v in materials.items():
        key = base_slot(k)
        m = dict(v)
        extra = None
        if key.startswith("gun_glass"):
            # a part MADE of glass (the Sarketh's crest sight: the owner, "entirely out of glass but a thin edge in the
            # guns colors"): seen as glass, clear face on, catching light at its edges (M_SOGlass), not cut away as a
            # sight's lens is
            PARENT_FOR[key] = glass_master()
            m = {k_: v_ for k_, v_ in m.items() if k_ not in ("alphaMode", "alphaCutoff")}
        if key.startswith("gun_lens"):
            # optic glass: see straight through (the browser draws it at 14 % opacity); a maker's own glass too
            # (gun_lens__skr: named for its tint, it was drawn as a solid amber pane over the sight)
            m["alphaMode"] = "MASK"
            extra = {"baseColorTex": "__clear"}
            tex = dict(tex, __clear=clear)
        mi = make_instance(master, dest, key, m, tex, extra)
        if os.path.basename(m.get("mrTex") or "").startswith("wpn_"):       # (the engine's sets carry ambient occlusion in the mask's red)
            mel.set_material_instance_scalar_parameter_value(mi, "AOAmount", 1.0)
        if len(own) == 3 and not key.startswith("gun_lens") and not key.startswith("gun_glass") and key != "gun_dot":
            for i, k in enumerate(("m1", "m2", "m3")):
                mel.set_material_instance_texture_parameter_value(mi, f"UniqueTex{i + 1}", own[k])
                sampled(mi, own[k], 1, 1.0)                    # (on UV 1, once across the gun: the streamer must be told)
            mel.set_material_instance_scalar_parameter_value(mi, "UniqueAmount", 1.0)
            if hp_normals:
                mel.set_material_instance_texture_parameter_value(mi, "UniqueNormalTex", hp_normals)
                sampled(mi, hp_normals, 1, 1.0)
                mel.set_material_instance_scalar_parameter_value(mi, "UniqueNormalAmount", 1.0)
            mel.update_material_instance(mi)
            eal.save_loaded_asset(mi, only_if_is_dirty=False)
        amounts = GUN_WEAR.get(key) or next((a for name, a in GUN_WEAR.items() if key.startswith(name + "__")), None)   # (a variant's own first)
        if amounts and worn:
            mel.set_material_instance_texture_parameter_value(mi, "WearTex", worn)
            sampled(mi, worn, 0, 3.0)                          # (the shared mask repeats WearTiling times a tile)
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


def palette_of(a):
    """A gun's colours: its set's palette (game_data.json "palettes"), else its class family's (energy: light,
    kinetic, horror). The owner, 2026-11-15: every gun of a set has the same colour palette and fires the same colour."""
    pals = load_json(GAME_DATA)["palettes"]
    fam = a.get("set") or {"energy": "light", "kinetic": "kinetic", "horror": "horror"}[a["cls"]]
    return pals[fam]


def projectile_kind(a):
    if a.get("round") == "slug":                                  # the Sarketh's crystalline slugs (docs/orion/SARKETH_WEAPONS.md)
        return unreal.SOProjectileKind.SLUG
    if a.get("goo"):
        return {"spit": unreal.SOProjectileKind.SPIT, "bile": unreal.SOProjectileKind.BILE, "brood": unreal.SOProjectileKind.BROOD}[a["goo"]]
    if a.get("projectile"):
        return unreal.SOProjectileKind.ROCKET
    return unreal.SOProjectileKind.ROUND if a["cls"] == "kinetic" else unreal.SOProjectileKind.BOLT


def slug_values(a):
    """A Sarketh gun's slug and its crystal's heat (game_data.json: "pierce", "pierceKeep", "roundSize", "heat": {perShot,
    cool, delay, vent, speed}); every other gun has none."""
    h = a.get("heat") or {}
    return dict(pierce=int(a.get("pierce", 0)), pierce_keep=float(a.get("pierceKeep", 0.6)), round_size=float(a.get("roundSize", 0.0)),
                heat_per_shot=float(h.get("perShot", 0.0)), heat_cool=float(h.get("cool", 0.6)), heat_cool_delay=float(h.get("delay", 0.3)),
                vent_time=float(h.get("vent", 1.4)), heat_speed=float(h.get("speed", 1.3)), refill_time=float(a.get("refill", 0.0)))


def gun_words(a):
    """A gun's words in the armoury (game_data.json): its line ("lore"), its class's name ("classNames") and the trait its
    set or class carries ("traits": the armoury's gold node)."""
    game = load_json(GAME_DATA)
    trait = (game.get("traits") or {}).get(a.get("set") or a["cls"]) or {}
    return dict(lore=unreal.Text(a.get("lore", "")), class_name=unreal.Text((game.get("classNames") or {}).get(a["cls"], a["cls"].title())),
                trait_name=unreal.Text(trait.get("name", "")), trait_text=unreal.Text(trait.get("text", "")))


def weapon(master, arch, a, clear):
    folder = weapon_dir(a["model"])
    src = os.path.join(SOURCE, "Weapons", folder)
    dest = f"/Game/Weapons/{folder}"
    if not os.path.isdir(src):
        log(f"DA_{folder}: skipped ({src} missing, run export_unreal.sh)")
        return None
    ensure_dir(dest)
    materials = load_json(os.path.join(src, "materials.json"))
    instances = gun_instances(master, src, dest, materials, clear, a["model"])
    info = load_json(os.path.join(src, a["model"] + ".parts.json"))
    body = import_static(src, a["model"] + ".fbx", dest, f"SM_{folder}", instances)
    try:
        log(f"SM_{folder}: {unreal.EditorStaticMeshLibrary.get_num_uv_channels(body, 0)} UV sets")
    except Exception:
        pass
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
    tracer = palette_of(a)["tracer"]                             # (the set's colour: never a gun's own)
    values = dict(display_name=unreal.Text(a["name"]), title=unreal.Text(a.get("title", a["name"])), archetype=arch, slot=int(a["slot"]), loot_weight=float(a.get("weight", 1.0)), default_shader=a.get("shader", "None"), set_id=a.get("set", "None"),
                  weapon_class=cls, sound_prefix=arch, damage=float(a["dmg"]), rounds_per_minute=float(a["rpm"]),
                  magazine_size=int(a["mag"]), reserve_ammo=int(a["reserve"]), reload_time=float(a["reload"]),
                  range=float(a["range"]), spread=float(a["spread"]), crit_multiplier=float(a["crit"]),
                  automatic=bool(a.get("auto")), burst=int(a.get("burst", 0)), burst_rpm=float(a.get("burstRpm", 0.0)),
                  pellets=int(a.get("pellets", 1)), projectile=kind, splash=float(a.get("splash", 0.0)), dot=float(a.get("dot", 0.0)),
                  swarm=int(a.get("swarm", 0)), aim_zoom=float(a["zoom"]), muzzle_velocity=float(velocity),
                  gravity_scale=float(a.get("grav", 0.0)) if kind in (unreal.SOProjectileKind.ROUND, unreal.SOProjectileKind.SLUG) else (float(a.get("gooGrav", 0.35)) if kind in (
                      unreal.SOProjectileKind.SPIT, unreal.SOProjectileKind.BILE, unreal.SOProjectileKind.BROOD) else 0.0),
                  kick=float(a.get("kick", 1.0)), ads_time=float(a["adsTime"]), sprint_to_fire_time=float(a["sprintOut"]),
                  sprint_carry=a.get("carry", "None"), tracer_color=hex_color(tracer), glow_color=hex_color(palette_of(a)["glow"]), body_mesh=body, parts=parts,
                  sights=[unreal.Name(s) for s in a["sights"]], default_sight=a["defaultSight"], snug_grip=bool(a.get("snugGrip", False)),
                  **slug_values(a), **gun_words(a))
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
    for sight_id in [k for k in load_json(GAME_DATA)["sights"] if k != "default"]:
        name = f"ATT_{sight_id}"
        if not os.path.exists(os.path.join(src, name + ".fbx")):
            continue
        mesh = import_static(src, name + ".fbx", dest, f"SM_{name}", instances)
        sockets = load_json(os.path.join(src, name + ".parts.json"))["sockets"]
        eye = sockets.get(f"{name}_sight", {"loc": [0, 0, 0]})["loc"]
        out[sight_id] = (mesh, eye)
    eal.save_directory(dest, only_if_is_dirty=False, recursive=True)
    return out


LOOT_WEAR = {"loot_metal": (.8, .35, .35, 1.0), "loot_dark": (.6, .3, .4, 1.0), "ammo_case": (.7, .35, .45, 1.0)}


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
        worn = wear_texture()
        for k, mi in instances.items():                    # the pickups' wear (edge wear from loot_props.py's _wear)
            amounts = LOOT_WEAR.get(k)
            if amounts and worn:
                mel.set_material_instance_texture_parameter_value(mi, "WearTex", worn)
                for name, value in zip(("EdgeWear", "Scratches", "Grime", "WearMetal"), amounts):
                    mel.set_material_instance_scalar_parameter_value(mi, name, float(value))
                mel.update_material_instance(mi)
                eal.save_loaded_asset(mi, only_if_is_dirty=False)
        for f in files:
            out[f] = import_static(src, f + ".fbx", dest, f"SM_{f}", instances)
        eal.save_directory(dest, only_if_is_dirty=False, recursive=True)
    log(f"loot props: {sorted(out)}")
    return out


def perk_infos(game):
    """Data/game_data.json "perks" as FSOPerkInfo: its name, its line, and the numbers of what it does."""
    perks = []
    for pid, p in game["perks"].items():
        info = unreal.SOPerkInfo()
        info.set_editor_property("id", pid)
        info.set_editor_property("name", unreal.Text(p["name"]))
        info.set_editor_property("description", unreal.Text(p["desc"]))
        # what it does: its own numbers (a perk names only those it uses)
        for key, prop in (("magazine", "magazine"), ("reload", "reload"), ("spread", "spread"), ("recoil", "recoil"),
                          ("precision", "precision"), ("fireRateShieldDown", "fire_rate_shield_down"),
                          ("killDamage", "kill_damage"), ("killDamageTime", "kill_damage_time"), ("killHeal", "kill_heal"),
                          ("precisionSplash", "precision_splash"), ("precisionSplashRadius", "precision_splash_radius"),
                          ("killMagazine", "kill_magazine"), ("killReload", "kill_reload"), ("killReloadTime", "kill_reload_time"),
                          ("openingDamage", "opening_damage"), ("openingAfter", "opening_after"),
                          ("lowMagDamage", "low_mag_damage"), ("lowMagShare", "low_mag_share"), ("hipSpread", "hip_spread"),
                          ("shieldDamage", "shield_damage"), ("healthDamage", "health_damage"), ("hitSlow", "hit_slow"),
                          ("hitSlowTime", "hit_slow_time"), ("precisionBurn", "precision_burn"),
                          ("precisionBurnTime", "precision_burn_time"), ("noise", "noise")):
            if key in p:
                info.set_editor_property(prop, float(p[key]))
        for key, prop in (("killShield", "kill_shield"), ("noFalloff", "no_falloff"), ("slideReload", "slide_reload")):
            info.set_editor_property(prop, bool(p.get(key, False)))
        info.set_editor_property("classes", [unreal.Name(c) for c in p.get("classes", [])])
        if "killDamageStacks" in p:
            info.set_editor_property("kill_damage_stacks", int(p["killDamageStacks"]))
        info.set_editor_property("autoload", bool(p.get("autoload", False)))
        perks.append(info)
    return perks


def perks_only():
    """Only the perks of the loot tables again (SO_IMPORT_ONLY=perks): their numbers changed, no gun is re-imported."""
    path = "/Game/Data/DA_LootTables"
    if not eal.does_asset_exist(path):
        log("DA_LootTables: not imported yet (run the weapons step), skipped")
        return
    tables = eal.load_asset(path)
    game = load_json(GAME_DATA)
    perks = perk_infos(game)
    tables.set_editor_property("perks", perks)
    rarities = list(tables.get_editor_property("rarities"))
    for info, r in zip(rarities, game["rarity"]):                 # (their names and colours: the rest stays)
        info.set_editor_property("name", unreal.Text(r["name"]))
        info.set_editor_property("color", hex_color(r["color"]))
    tables.set_editor_property("rarities", rarities)
    eal.save_loaded_asset(tables, only_if_is_dirty=False)
    log(f"DA_LootTables: {len(perks)} perks and {len(rarities)} rarities rewritten")


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
    perks = perk_infos(game)
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


# What each engine set (tools/blender/pbr.py) is laid over with: (detail kind, its strength, how much it darkens what
# it buries, the macro variation's amount).
PBR_FINISH = {
    "nx_stone": ("stone", .8, .5, .10), "nx_paving": ("stone", .6, .4, .10), "nx_rock": ("stone", 1.0, .6, .12),
    "nx_panel": ("metal", .7, .3, .06), "nx_trim": ("metal", .6, .2, .05), "nx_window": (None, 0, 0, 0),
    "panel": ("metal", .7, .3, .06), "concrete": ("concrete", .9, .5, .10),
    "ru_concrete": ("concrete", .9, .5, .10), "ru_fracture": ("concrete", .7, .4, .06), "ru_asphalt": ("asphalt", .9, .5, .10),
    "ru_stone": ("stone", .7, .4, .10), "ru_sandstone": ("stone", .8, .5, .10), "ru_rubble": ("soil", .8, .4, .08),
    "ru_metal": ("metal", .7, .3, .06), "ru_panel": ("metal", .6, .3, .06), "ru_corrugate": ("metal", .6, .3, .06),
    "ru_box_red": ("metal", .6, .3, .06), "ru_box_green": ("metal", .6, .3, .06), "ru_box_ochre": ("metal", .6, .3, .06),
    "ru_brass": ("metal", .5, .2, .04), "ru_plaster": ("plaster", .9, .4, .08), "ru_ceramic": ("plaster", .25, .1, .06),
    "ru_tile": ("stone", .2, .1, .05),
}
# What the game holds of a set (the source is 4096 px throughout): colour and normal whole, the mask at 2048, the
# height at 1024 (parallax needs no more): about 40 MB a set in video memory instead of 85.
PBR_HOLD = {"m": 2048, "h": 1024}
# Nexus Prime's own ground and facade sets (their maps are not the engine's yet): which detail they take.
CITY_DETAIL = {"nc_asphalt": "asphalt", "nc_tunnel": "asphalt", "nc_pavers": "concrete", "nc_kerb": "concrete", "nc_lot": "concrete",
               "nc_roof": "concrete", "nc_wall": "concrete", "nc_plaza": "stone", "nc_rock": "stone", "nc_grass": "soil", "nc_dirt": "soil",
               "nc_steel": "metal", "nc_rail": "metal", "ncf_stone": "stone", "ncf_brick": "stone", "ncf_panel": "metal",
               "ncf_industrial": "metal", "ncf_military": "metal", "ncf_warehouse": "metal"}
DETAIL_TILE = 0.5      # metres a detail set covers (detail_maps.py)


def world_maps(defaults):
    """The texture engine's sets into the game (SO_IMPORT_ONLY=worldmaps): every set in assets/textures/pbr_sets.json
    whose colour map the game already has is imported again with ALL its maps (colour, normal, AO / roughness / metal,
    height, emissive) beside it, and every instance that shows it is told to use them: ambient occlusion, parallax at
    the set's true depth, the detail layer of its kind, the macro variation. No mesh is imported."""
    info = load_json(os.path.join(REPO_TEXTURES, "pbr_sets.json"))
    folder = "/Game/Materials/Detail"
    ensure_dir(folder)
    det = {}
    for f in sorted(os.listdir(REPO_TEXTURES)):
        if f.startswith("det_") and f.endswith("_n.png"):
            det[f[4:-6]] = import_texture(os.path.join(REPO_TEXTURES, f), folder, "T_" + f[:-4], "normal")
    macro = import_texture(os.path.join(REPO_TEXTURES, "macro_m.png"), folder, "T_macro", "mask")
    every = [str(a) for a in eal.list_assets("/Game", recursive=True, include_folder=False)]
    done = 0
    for name, i in sorted(info.items()):
        if name.startswith("det_") or name.startswith("wpn_") or name == "macro":       # (the guns' sets: SO_IMPORT_ONLY=guntextures)
            continue
        homes = sorted({a.rsplit("/", 1)[0] for a in every if a.endswith(f"/T_{name}_c.T_{name}_c")})
        for home in homes:
            tex = {}
            for kind, ext, how in (("c", "jpg", "color"), ("n", "png", "normal"), ("m", "png", "mask"), ("h", "png", "mask"), ("e", "jpg", "color")):
                f = os.path.join(REPO_TEXTURES, f"{name}_{kind}.{ext}")
                if os.path.exists(f):
                    tex[kind] = import_texture(f, home, f"T_{name}_{kind}", how)
                    if kind in PBR_HOLD:
                        tex[kind].set_editor_property("max_texture_size", PBR_HOLD[kind])
                        eal.save_loaded_asset(tex[kind], only_if_is_dirty=False)
            kind_, strength, cavity, amount = PBR_FINISH.get(name, (None, 0, 0, 0))
            parent = home.rsplit("/", 1)[0]
            for a in eal.list_assets(parent, recursive=False, include_folder=False):
                mi = eal.load_asset(str(a).split(".")[0])
                if not isinstance(mi, unreal.MaterialInstanceConstant):
                    continue
                shown = mel.get_material_instance_texture_parameter_value(mi, "BaseColorTex")
                if not shown or shown.get_path_name() != tex["c"].get_path_name():
                    continue
                for param, k in (("NormalTex", "n"), ("MRTex", "m"), ("HeightTex", "h")):
                    mel.set_material_instance_texture_parameter_value(mi, param, tex[k])
                if "e" in tex:
                    mel.set_material_instance_texture_parameter_value(mi, "EmissiveTex", tex["e"])
                for param, v in (("Roughness", 1.0), ("Metallic", 1.0), ("AOAmount", 1.0), ("Parallax", min(0.05, float(i["depth"]) / float(i["tile"]))),
                                 ("DetailScale", float(i["tile"]) / DETAIL_TILE), ("DetailStrength", strength if kind_ in det else 0.0),
                                 ("DetailCavity", cavity), ("MacroAmount", amount), ("MacroScale", 0.173)):
                    mel.set_material_instance_scalar_parameter_value(mi, param, float(v))
                if kind_ in det:
                    mel.set_material_instance_texture_parameter_value(mi, "DetailTex", det[kind_])
                mel.set_material_instance_texture_parameter_value(mi, "MacroTex", macro)
                mel.update_material_instance(mi)
                eal.save_loaded_asset(mi, only_if_is_dirty=False)
                done += 1
                log(f"world maps: {name} -> {mi.get_name()} ({home})")
    # Nexus Prime's ground and facades: their own materials, with the detail layer
    ground_material(defaults)
    facade_material(defaults)
    city = "/Game/Environments/NexusCity"
    n_city = 0
    for a in eal.list_assets(city, recursive=False, include_folder=False):
        mi = eal.load_asset(str(a).split(".")[0])
        key = mi.get_name()[3:] if isinstance(mi, unreal.MaterialInstanceConstant) else ""
        kind_ = CITY_DETAIL.get(key) or ("concrete" if key.startswith("ncf_") and key != "ncf_glass" else None)
        if kind_ not in det:
            continue
        mel.set_material_instance_texture_parameter_value(mi, "DetailTex", det[kind_])
        tiling = mel.get_material_instance_scalar_parameter_value(mi, "TilingM") if key.startswith("nc_") else 0.0
        mel.set_material_instance_scalar_parameter_value(mi, "DetailScale", (tiling or 3.6) / DETAIL_TILE)
        mel.set_material_instance_scalar_parameter_value(mi, "DetailStrength", 0.8)
        if key in info and key.startswith("nc_"):               # (an engine set: its mask's red is ambient occlusion)
            mel.set_material_instance_scalar_parameter_value(mi, "AOAmount", 1.0)
        mel.update_material_instance(mi)
        eal.save_loaded_asset(mi, only_if_is_dirty=False)
        n_city += 1
    log(f"world maps: {done} instances on the engine's sets, {n_city} city instances with a detail layer")


def gun_textures():
    """The guns' shared material sets again, straight from assets/textures (SO_IMPORT_ONLY=guntextures): the maps
    changed (tools/blender/surface_maps.py, through the texture engine), no gun's mesh or material did. Every gun
    reads the same T_wpn_* assets. A set's lossless .png is taken where there is one beside the .jpg; the height
    map comes in too, and every gun instance on a wpn_ set is told to take its ambient occlusion from the mask."""
    ensure_dir(WEAPON_TEX)
    info = load_json(os.path.join(REPO_TEXTURES, "pbr_sets.json")) if os.path.exists(os.path.join(REPO_TEXTURES, "pbr_sets.json")) else {}
    seen = {}
    for f in sorted(os.listdir(REPO_TEXTURES)):
        base, ext = os.path.splitext(f)
        if ext.lower() not in (".jpg", ".png") or not base.startswith("wpn_") or base[-2:] not in ("_c", "_n", "_m", "_h"):
            continue
        if ext.lower() == ".jpg" and os.path.exists(os.path.join(REPO_TEXTURES, base + ".png")):
            continue
        seen[base] = import_texture(os.path.join(REPO_TEXTURES, f), WEAPON_TEX, "T_" + base, {"_c": "color", "_n": "normal", "_m": "mask", "_h": "mask"}[base[-2:]])
    told = 0
    for a in eal.list_assets("/Game/Weapons", recursive=True, include_folder=False):
        path = str(a).split(".")[0]
        if "/MI_" not in path:
            continue
        mi = eal.load_asset(path)
        if not isinstance(mi, unreal.MaterialInstanceConstant):
            continue
        mr = mel.get_material_instance_texture_parameter_value(mi, "MRTex")
        name = mr.get_name()[2:-2] if mr and mr.get_name().startswith("T_wpn_") else ""
        if name not in info:
            continue
        mel.set_material_instance_scalar_parameter_value(mi, "AOAmount", 1.0)
        if name + "_h" in seen:
            mel.set_material_instance_texture_parameter_value(mi, "HeightTex", seen[name + "_h"])
        mel.update_material_instance(mi)
        eal.save_loaded_asset(mi, only_if_is_dirty=False)
        told += 1
    log(f"gun textures: {len(seen)} maps, {told} gun materials take their ambient occlusion from them")


def gun_slots():
    """Every gun mesh's material slots again, by what its file calls them (SO_IMPORT_ONLY=gunslots): a mesh imported
    more than once kept the slot names of its first import and was filled by those (assign_materials), so a part
    whose material had changed since wore the old one. Nothing is imported: each mesh takes the instances that lie
    in its own folder."""
    by_folder = {}
    meshes = []
    for a in eal.list_assets("/Game/Weapons", recursive=True, include_folder=False):
        path = str(a).split(".")[0]
        folder, name = path.rsplit("/", 1)
        if name.startswith("MI_"):
            by_folder.setdefault(folder, {})[name[3:]] = path
        elif name.startswith("SM_"):
            meshes.append((folder, path))
    changed = 0
    for folder, path in meshes:
        mesh = eal.load_asset(path)
        if not isinstance(mesh, unreal.StaticMesh):
            continue
        before = [(str(m.get_editor_property("material_slot_name")), m.get_editor_property("material_interface").get_name()
                   if m.get_editor_property("material_interface") else "") for m in mesh.get_editor_property("static_materials")]
        instances = {k: eal.load_asset(v) for k, v in by_folder.get(folder, {}).items()}
        assign_materials(mesh, instances)
        after = [(str(m.get_editor_property("material_slot_name")), m.get_editor_property("material_interface").get_name()
                  if m.get_editor_property("material_interface") else "") for m in mesh.get_editor_property("static_materials")]
        if before != after:
            changed += 1
            log(f"  {path}: {[b for b, c in zip(before, after) if b != c]} -> {[c for b, c in zip(before, after) if b != c]}")
    log(f"gun slots: {len(meshes)} meshes looked at, {changed} had a slot on the wrong material")


def player_textures():
    """The players' cloth and plate maps again, nothing else (SO_IMPORT_ONLY=player_textures): the maps changed
    (tools/blender/hero/fabric.py), no body or piece did. Skin, eye and hair maps are left as they are."""
    n = 0
    for sex in ("Male", "Female"):
        for folder in (f"Player{sex}", f"Player{sex}Arms"):
            src = os.path.join(SOURCE, "Characters", folder, "Textures")
            dest = f"/Game/Characters/{folder}/Textures"
            if not os.path.isdir(src):
                continue
            for f in sorted(os.listdir(src)):
                base, ext = os.path.splitext(f)
                if ext.lower() != ".png" or base[-2:] not in ("_c", "_n", "_m") or not eal.does_asset_exist(f"{dest}/T_{base}"):
                    continue
                import_texture(os.path.join(src, f), dest, "T_" + base, {"_c": "color", "_n": "normal", "_m": "mask"}[base[-2:]])
                n += 1
    log(f"player textures: {n} maps")


def gun_numbers():
    """Data/game_data.json archetypes -> the numbers of every gun's data asset that is already imported, nothing else
    (SO_IMPORT_ONLY=gunnumbers): the weapons step re-imports every mesh and material to change one figure."""
    game = load_json(GAME_DATA)
    n = 0
    for arch, a in game["archetypes"].items():
        if not isinstance(a, dict) or "model" not in a:
            continue
        folder = weapon_dir(a["model"])
        path = f"/Game/Weapons/{folder}/DA_{folder}"
        if not eal.does_asset_exist(path):
            continue
        data = eal.load_asset(path)
        if str(data.get_editor_property("archetype")) != arch:
            continue                                          # (another archetype shares this model: its own asset)
        kind = projectile_kind(a)
        velocity = a.get("vel") or (60.0 if kind == unreal.SOProjectileKind.ROCKET else 500.0)
        values = dict(damage=float(a["dmg"]), rounds_per_minute=float(a["rpm"]), magazine_size=int(a["mag"]), reserve_ammo=int(a["reserve"]),
                      reload_time=float(a["reload"]), range=float(a["range"]), spread=float(a["spread"]), crit_multiplier=float(a["crit"]),
                      muzzle_velocity=float(velocity), kick=float(a.get("kick", 1.0)), sprint_to_fire_time=float(a["sprintOut"]),
                      sprint_carry=a.get("carry", "None"), tracer_color=hex_color(palette_of(a)["tracer"]),
                      glow_color=hex_color(palette_of(a)["glow"]), snug_grip=bool(a.get("snugGrip", False)), **slug_values(a), **gun_words(a))
        for key, value in values.items():
            data.set_editor_property(key, value)
        eal.save_loaded_asset(data, only_if_is_dirty=False)
        n += 1
    log(f"gun numbers: {n} data assets")


def icons_only():
    """Every gun's and armour piece's armoury picture again, nothing else (SO_IMPORT_ONLY=icons; tools/blender/icons.py
    renders them into SourceArt/Icons/guns and /armour): each texture is replaced where it is, so whatever names it
    keeps it. The melee styles' pictures come with SO_IMPORT_ONLY=melee."""
    game = load_json(GAME_DATA)
    n = 0
    for arch, a in game["archetypes"].items():
        if not isinstance(a, dict) or "model" not in a:
            continue
        folder = weapon_dir(a["model"])
        path = f"/Game/Weapons/{folder}/DA_{folder}"
        icon = os.path.join(ICONS, "guns", f"icon_{a['model']}.png")
        if not eal.does_asset_exist(path) or not os.path.exists(icon):
            continue
        data = eal.load_asset(path)
        if str(data.get_editor_property("archetype")) != arch:
            continue                                          # (another archetype shares this model: its own asset)
        data.set_editor_property("icon", import_ui_texture(icon, f"/Game/Weapons/{folder}", f"T_Icon_{folder}"))
        eal.save_loaded_asset(data, only_if_is_dirty=False)
        n += 1
    log(f"icons: {n} guns")
    # the armour pieces' pictures (made with the bodies' wardrobes: T_Icon_<slot>_<item> under each body's Icons)
    pieces = 0
    for sex in ("male", "female"):
        dest = f"/Game/Characters/Player{sex.title()}/Icons"
        for icon in sorted(glob.glob(os.path.join(ICONS, "armour", f"icon_{sex}_*.png"))):
            slot_item = os.path.basename(icon)[len(f"icon_{sex}_"):-4]
            name = f"T_Icon_{slot_item}"
            if eal.does_asset_exist(f"{dest}/{name}"):
                import_ui_texture(icon, dest, name)
                pieces += 1
    log(f"icons: {pieces} armour pieces")


def register_archetypes(datas):
    """Puts (or replaces) these guns' entries in the loot tables' archetype list without touching anything else in it
    (SO_WEAPONS_ONLY: a new gun is known to the game, MakeWeapon / LoadArchetype find it)."""
    path = "/Game/Data/DA_LootTables"
    if not datas or not eal.does_asset_exist(path):
        return
    tables = eal.load_asset(path)
    entries = [e for e in list(tables.get_editor_property("archetypes")) if str(e.get_editor_property("id")) not in datas]
    for arch, data in datas.items():
        e = unreal.SOArchetypeEntry()
        e.set_editor_property("id", arch)
        e.set_editor_property("data", data)
        entries.append(e)
    tables.set_editor_property("archetypes", entries)
    eal.save_loaded_asset(tables, only_if_is_dirty=False)
    log(f"DA_LootTables: {', '.join(datas)} registered ({len(entries)} archetypes)")


def weapons(master, defaults):
    game = load_json(GAME_DATA)
    some = [s.strip() for s in os.environ.get("SO_WEAPONS_ONLY", "").split(",") if s.strip()]
    if some:                                                    # SO_WEAPONS_ONLY=rifle,auto: only those guns again
        datas = {}
        for arch in some:
            data = weapon(master, arch, game["archetypes"][arch], defaults["clear"])
            if data:
                datas[arch] = data
        register_archetypes(datas)                              # (a gun new to the game is put in the loot tables too)
        return
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
// 3: a tongue of flame from the muzzle (U = 0) to its tip (U = 1): widest a fifth of the way out, drawn to a point,
// torn along its length, a different tear on every card (Seed)
float w = saturate(UV.x * 8.0) * pow(saturate(1.0 - UV.x), 0.75);
float body = saturate(1.0 - abs(d.y) * 2.0 / max(w, 0.02));
float tear = 0.6 + 0.4 * sin(d.y * 37.0 + Seed * 40.0 + UV.x * 11.0) * sin(UV.x * (19.0 + Seed * 9.0) + Seed * 23.0);
float tongue = body * body * tear * saturate((1.0 - UV.x) * 2.5);
float s = Mode < 0.5 ? dotS : (Mode < 1.5 ? across * head : (Mode < 2.5 ? across * root : tongue));
return pow(s, Softness);
"""

DECAL_HLSL = """
float r = length(UV - 0.5) * 2.0;
float hole = 1.0 - smoothstep(0.12, 0.2, r);
float burn = (1.0 - smoothstep(0.2, 0.95, r)) * 0.55;
return saturate(hole + burn);
"""


WARN_HLSL = """
float2 d = (WorldPos.xy - Center.xy) / max(Center.w, 1.0);
float r = length(d);
float2 n = d / max(r, 0.0001);
float fill = Shape.w;
float sector = 1.0;
float side = 0.0;
if (Shape.z > -0.999)
{
    float ang = acos(clamp(dot(n, Shape.xy), -1.0, 1.0));
    float lim = acos(clamp(Shape.z, -1.0, 1.0));
    float w = 0.022 / max(r, 0.06);
    sector = 1.0 - smoothstep(lim - w * 0.4, lim, ang);
    side = smoothstep(lim - w * 2.2, lim - w * 1.2, ang) * sector * step(0.04, r);
}
float inside = 1.0 - smoothstep(0.985, 1.0, r);
float rim = smoothstep(0.925, 0.955, r) * inside;
float wash = 1.0 - smoothstep(fill - 0.03, fill, r);
float front = smoothstep(fill - 0.085, fill - 0.015, r) * (1.0 - smoothstep(fill - 0.015, fill + 0.005, r));
float hot = smoothstep(0.7, 1.0, fill);
float lines = saturate(rim + side);
float level = 1.0 - smoothstep(170.0, 250.0, abs(WorldPos.z - Center.z));
float3 nrm = normalize(cross(ddx(WorldPos), ddy(WorldPos)));
level *= smoothstep(0.45, 0.75, abs(nrm.z));
float a = inside * sector * level * saturate(0.16 + wash * 0.2 + lines * 0.85 + front * 0.7) * Color.a;
float glow = 0.35 + wash * (0.9 + hot * 1.6) + lines * 5.0 + front * (3.0 + hot * 3.0);
return float4(Color.rgb * glow, a);
"""


def warn_material():
    """/Game/FX/M_SOWarn: the warning an area attack draws on the ground (USOFxSubsystem::Warn): a ring or a sector
    with a fill that runs from the middle to the rim. A decal, so it lies on rubble and steps as well as on a flat
    floor (and only on what faces up: not up the side of a crate standing in it); the picture is worked out from the world position (Center = x, y, z, radius; Shape = cos / sin of the
    heading, cos of the half angle, fill 0..1; Color with the fade in its alpha), so the decal's own turn is nothing."""
    path = "/Game/FX/M_SOWarn"
    ensure_dir("/Game/FX")
    if eal.does_asset_exist(path):
        mat = eal.load_asset(path)
        mel.delete_all_material_expressions(mat)
    else:
        mat = tools.create_asset("M_SOWarn", "/Game/FX", unreal.Material, unreal.MaterialFactoryNew())
    mat.set_editor_property("material_domain", unreal.MaterialDomain.MD_DEFERRED_DECAL)
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
    shape = mel.create_material_expression(mat, unreal.MaterialExpressionCustom, -450, 0)
    shape.set_editor_property("code", WARN_HLSL)
    shape.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT4)
    vectors = {"Center": (0.0, 0.0, 0.0, 300.0), "Shape": (1.0, 0.0, -1.0, 0.5), "Color": (0.62, 0.3, 1.0, 1.0)}
    inputs = []
    for n in ["WorldPos"] + list(vectors):
        ci = unreal.CustomInput()
        ci.set_editor_property("input_name", n)
        inputs.append(ci)
    shape.set_editor_property("inputs", inputs)
    wp = mel.create_material_expression(mat, unreal.MaterialExpressionWorldPosition, -900, -150)
    mel.connect_material_expressions(wp, "", shape, "WorldPos")
    for k, (n, value) in enumerate(vectors.items()):
        v = mel.create_material_expression(mat, unreal.MaterialExpressionVectorParameter, -900, 60 + k * 200)
        v.set_editor_property("parameter_name", n)
        v.set_editor_property("default_value", unreal.LinearColor(*value))
        mel.connect_material_expressions(v, "RGBA", shape, n)
    rgb = mel.create_material_expression(mat, unreal.MaterialExpressionComponentMask, -150, -60)
    for ch, on in (("r", True), ("g", True), ("b", True), ("a", False)):
        rgb.set_editor_property(ch, on)
    alpha = mel.create_material_expression(mat, unreal.MaterialExpressionComponentMask, -150, 120)
    for ch, on in (("r", False), ("g", False), ("b", False), ("a", True)):
        alpha.set_editor_property(ch, on)
    mel.connect_material_expressions(shape, "", rgb, "")
    mel.connect_material_expressions(shape, "", alpha, "")
    dark = mel.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, -150, -240)
    dark.set_editor_property("constant", unreal.LinearColor(0.01, 0.006, 0.02, 1.0))
    mel.connect_material_property(dark, "", unreal.MaterialProperty.MP_BASE_COLOR)
    mel.connect_material_property(rgb, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    mel.connect_material_property(alpha, "", unreal.MaterialProperty.MP_OPACITY)
    mel.recompile_material(mat)
    eal.save_loaded_asset(mat, only_if_is_dirty=False)
    log("M_SOWarn")


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
    for name in ("UV", "Mode", "Softness", "Seed"):
        ci = unreal.CustomInput()
        ci.set_editor_property("input_name", name)
        inputs.append(ci)
    shape.set_editor_property("inputs", inputs)
    mel.connect_material_expressions(uv, "", shape, "UV")
    seed = mel.create_material_expression(mat, unreal.MaterialExpressionPerInstanceRandom, -900, 580)
    mel.connect_material_expressions(seed, "", shape, "Seed")
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
    instance("MI_FxFlash", 3.0, 0.9, False)
    instance("MI_FxSmoke", 0.0, 1.2, True)
    log("effect materials ready")


# What more than one area uses: never in an area's own folder.
SHARED = "/Game/Shared"
SHARED_NEXUS = ("NX_beacon",)


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
    # what every area shows (the map beacon) lives in /Game/Shared with its own materials and textures: an area's
    # folder is that area's alone (USOAreaSubsystem), and nothing else may load from it
    shared = SHARED + "/Map"
    common = [a for a in manifest["assets"] if os.path.splitext(a["file"])[0] in SHARED_NEXUS]
    common_used = {base_slot(n) for a in common for n in a["materials"]}
    ensure_dir(shared)
    common_tex = import_textures_for(src, materials, shared + "/Textures", common_used)
    common_instances = {key: make_instance(master, shared, key, materials.get(key) or {}, common_tex) for key in common_used}
    for a in manifest["assets"]:
        name = os.path.splitext(a["file"])[0]
        if a in common:
            mesh = import_static(src, a["file"], shared, f"SM_{name}", common_instances)
        else:
            mesh = import_static(src, a["file"], dest, f"SM_{name}", instances)
        body = mesh.get_editor_property("body_setup")
        if body:
            body.set_editor_property("collision_trace_flag", unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
        eal.save_loaded_asset(mesh, only_if_is_dirty=False)
    eal.save_directory(dest, only_if_is_dirty=False, recursive=True)
    eal.save_directory(shared, only_if_is_dirty=False, recursive=True)
    log(f"Nexus: {len(manifest['assets'])} pieces ({len(common)} shared)")


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
    mat = _material("/Game/Environments/NexusCity/M_SOFoliage", {"used_with_instanced_static_meshes": True, "used_with_nanite": True, "two_sided": True,
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
    mat = _material("/Game/Environments/NexusCity/M_SOGround", {"tangent_space_normal": False, "used_with_instanced_static_meshes": True, "used_with_nanite": True})
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
    # a detail normal for close up (a ground tile is 4 to 12 m: millimetres a texel); off until an instance asks
    duv = mel.create_material_expression(mat, unreal.MaterialExpressionMultiply, -1000, 1100)
    mel.connect_material_expressions(uv, "", duv, "A")
    mel.connect_material_expressions(_param(mat, unreal.MaterialExpressionScalarParameter, "DetailScale", 16.0, -1250, 1180), "", duv, "B")
    det = _param(mat, unreal.MaterialExpressionTextureSampleParameter2D, "DetailTex", (defaults["normal"], S.SAMPLERTYPE_NORMAL), -800, 1100)
    mel.connect_material_expressions(duv, "", det, "UVs")
    nb = _custom(mat, SURFACE_HLSL["normal"], ("B", "D", "S"), unreal.CustomMaterialOutputType.CMOT_FLOAT3, -620, 100)
    mel.connect_material_expressions(nrm, "RGB", nb, "B")
    mel.connect_material_expressions(det, "RGB", nb, "D")
    mel.connect_material_expressions(_param(mat, unreal.MaterialExpressionScalarParameter, "DetailStrength", 0.0, -800, 1330), "", nb, "S")
    n = _custom(mat, GROUND_N_HLSL, ("Nt", "N", "K"), unreal.CustomMaterialOutputType.CMOT_FLOAT3, -450, 100)
    mel.connect_material_expressions(nb, "", n, "Nt")
    mel.connect_material_expressions(vn, "", n, "N")
    mel.connect_material_expressions(strength, "", n, "K")
    mel.connect_material_property(n, "", unreal.MaterialProperty.MP_NORMAL)
    mel.connect_material_property(msk, "B", unreal.MaterialProperty.MP_METALLIC)
    # ambient occlusion from the mask's red, for the sets the texture engine drew (city_maps.py); off until asked
    ao = _custom(mat, SURFACE_HLSL["ao"], ("O", "K"), unreal.CustomMaterialOutputType.CMOT_FLOAT1, -450, 600)
    mel.connect_material_expressions(msk, "R", ao, "O")
    mel.connect_material_expressions(_param(mat, unreal.MaterialExpressionScalarParameter, "AOAmount", 0.0, -800, 1500), "", ao, "K")
    mel.connect_material_property(ao, "", unreal.MaterialProperty.MP_AMBIENT_OCCLUSION)
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
    mat = _material("/Game/Environments/NexusCity/M_SOFacade", {"used_with_instanced_static_meshes": True, "used_with_nanite": True})
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
    duv = mel.create_material_expression(mat, unreal.MaterialExpressionMultiply, -1000, 900)
    mel.connect_material_expressions(uv, "", duv, "A")
    mel.connect_material_expressions(_param(mat, unreal.MaterialExpressionScalarParameter, "DetailScale", 7.0, -1250, 980), "", duv, "B")
    det = _param(mat, unreal.MaterialExpressionTextureSampleParameter2D, "DetailTex", (defaults["normal"], S.SAMPLERTYPE_NORMAL), -850, 900)
    mel.connect_material_expressions(duv, "", det, "UVs")
    nb = _custom(mat, SURFACE_HLSL["normal"], ("B", "D", "S"), unreal.CustomMaterialOutputType.CMOT_FLOAT3, -500, 60)
    mel.connect_material_expressions(nrm, "RGB", nb, "B")
    mel.connect_material_expressions(det, "RGB", nb, "D")
    mel.connect_material_expressions(_param(mat, unreal.MaterialExpressionScalarParameter, "DetailStrength", 0.0, -850, 1130), "", nb, "S")
    mel.connect_material_property(nb, "", unreal.MaterialProperty.MP_NORMAL)
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
    mat = _material("/Game/Environments/NexusCity/M_SOCarPaint", {"used_with_instanced_static_meshes": True, "used_with_nanite": True})
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
    # the city instances its props: the master needs the instanced usage, or a game build draws them with the
    # engine's default checker material (usage flags cannot be added at runtime)
    if not (master.get_editor_property("used_with_instanced_static_meshes") and master.get_editor_property("used_with_nanite")):
        master.set_editor_property("used_with_instanced_static_meshes", True)
        master.set_editor_property("used_with_nanite", True)
        mel.recompile_material(master)
        eal.save_loaded_asset(master, only_if_is_dirty=False)

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


ENERGY_HLSL = """
// bands of light drifting up the surface, brighter toward its edges (UV), a slow breathing pulse
float band = 0.5 + 0.5 * sin(WP.z * 0.045 - T * 3.0) * sin(WP.z * 0.013 + T * 1.3);
float2 e = min(UV, 1.0 - UV);
float edge = saturate(1.0 - min(e.x, e.y) * 8.0);
float pulse = 0.85 + 0.15 * sin(T * 2.1);
return C * I * pulse * (0.35 + 0.45 * band + 0.6 * edge);
"""


GLOW_PULSE_HLSL = """
// the violet light of the Altered breathes: a slow swell, out of step from place to place
float ph = dot(WP, float3(0.0011, 0.0013, 0.0007));
return C * I * (0.55 + 0.45 * sin(T * 1.7 + ph * 6.2831) * sin(T * 0.53 + ph * 3.1));
"""


_GLASS = {}


def glass_master():
    """/Game/Weapons/M_SOGlass: a gun part made of glass. Translucent and two-sided: clear face on (OpacityFace),
    only its edges catching the light (Fresnel: OpacityEdge, a faint EdgeGlow), smooth and specular; no colour of its
    own (the owner: "the scope needs to be see through not brown or any color"): BaseColorTint is near white."""
    if "m" in _GLASS:
        return _GLASS["m"]
    ensure_dir("/Game/Weapons")
    props = {"blend_mode": unreal.BlendMode.BLEND_TRANSLUCENT, "two_sided": True}
    mode = getattr(unreal.TranslucencyLightingMode, "TLM_SURFACE", None)
    if mode is not None:
        props["translucency_lighting_mode"] = mode
    mat = _material("/Game/Weapons/M_SOGlass", props)
    tint = _param(mat, unreal.MaterialExpressionVectorParameter, "BaseColorTint", (0.95, 0.97, 1.0, 1.0), -900, 0)
    face = _param(mat, unreal.MaterialExpressionScalarParameter, "OpacityFace", 0.03, -900, 200)     # (clear: no colour of its own)
    edge = _param(mat, unreal.MaterialExpressionScalarParameter, "OpacityEdge", 0.35, -900, 300)
    glow = _param(mat, unreal.MaterialExpressionScalarParameter, "EdgeGlow", 0.15, -900, 420)
    fres = mel.create_material_expression(mat, unreal.MaterialExpressionFresnel, -900, 540)
    fres.set_editor_property("exponent", 3.0)
    lerp = mel.create_material_expression(mat, unreal.MaterialExpressionLinearInterpolate, -500, 240)
    mel.connect_material_expressions(face, "", lerp, "A")
    mel.connect_material_expressions(edge, "", lerp, "B")
    mel.connect_material_expressions(fres, "", lerp, "Alpha")
    mel.connect_material_property(lerp, "", unreal.MaterialProperty.MP_OPACITY)
    m1 = mel.create_material_expression(mat, unreal.MaterialExpressionMultiply, -500, 420)
    mel.connect_material_expressions(tint, "", m1, "A")
    mel.connect_material_expressions(fres, "", m1, "B")
    m2 = mel.create_material_expression(mat, unreal.MaterialExpressionMultiply, -300, 420)
    mel.connect_material_expressions(m1, "", m2, "A")
    mel.connect_material_expressions(glow, "", m2, "B")
    mel.connect_material_property(m2, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    mel.connect_material_property(tint, "", unreal.MaterialProperty.MP_BASE_COLOR)
    rough = mel.create_material_expression(mat, unreal.MaterialExpressionConstant, -500, 620)
    rough.set_editor_property("r", 0.04)
    mel.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
    mel.recompile_material(mat)
    eal.save_loaded_asset(mat, only_if_is_dirty=False)
    _GLASS["m"] = mat
    return mat


def energy_materials():
    """/Game/Environments/Meridian/M_SOEnergy: unlit additive light (the barriers, the crown's beam): Color x Intensity
    in drifting bands, brighter at the edges. MI_SOEnergy_Barrier for ASOOperationBarrier's panel; MI_ru_beam (the
    beam in the crown's detail) is re-parented onto it. Shared: every operation has barriers."""
    dest = SHARED + "/Operation"
    ensure_dir(dest)
    mat = _material(dest + "/M_SOEnergy", {"blend_mode": unreal.BlendMode.BLEND_ADDITIVE, "shading_model": unreal.MaterialShadingModel.MSM_UNLIT,
                                           "two_sided": True, "used_with_nanite": True})   # its meshes are Nanite: the editor sets the flag by itself, a package cannot
    wp = mel.create_material_expression(mat, unreal.MaterialExpressionWorldPosition, -800, 0)
    uv = mel.create_material_expression(mat, unreal.MaterialExpressionTextureCoordinate, -800, 120)
    t = mel.create_material_expression(mat, unreal.MaterialExpressionTime, -800, 240)
    col = _param(mat, unreal.MaterialExpressionVectorParameter, "Color", (0.55, 0.3, 1.0, 1.0), -800, 360)
    inten = _param(mat, unreal.MaterialExpressionScalarParameter, "Intensity", 3.0, -800, 480)
    node = _custom(mat, ENERGY_HLSL, ("WP", "UV", "T", "C", "I"), unreal.CustomMaterialOutputType.CMOT_FLOAT3, -400, 200)
    for src, pin in ((wp, "WP"), (uv, "UV"), (t, "T"), (col, "C"), (inten, "I")):
        mel.connect_material_expressions(src, "", node, pin)
    mel.connect_material_property(node, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    mel.recompile_material(mat)
    eal.save_loaded_asset(mat, only_if_is_dirty=False)

    def inst(path, color, intensity):
        if eal.does_asset_exist(path):
            mi = eal.load_asset(path)
        else:
            folder, name = path.rsplit("/", 1)
            mi = tools.create_asset(name, folder, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
        mel.set_material_instance_parent(mi, mat)
        mel.set_material_instance_vector_parameter_value(mi, "Color", unreal.LinearColor(*color))
        mel.set_material_instance_scalar_parameter_value(mi, "Intensity", intensity)
        mel.update_material_instance(mi)
        eal.save_loaded_asset(mi, only_if_is_dirty=False)
    inst(dest + "/MI_SOEnergy_Barrier", (0.5, 0.28, 1.0, 1.0), 1.6)
    # the glow on every growth, crystal and seam: opaque, lit, its light breathing
    glow = _material(dest + "/M_SOGlowPulse", {"used_with_nanite": True, "used_with_skeletal_mesh": True, "used_with_instanced_static_meshes": True})
    gwp = mel.create_material_expression(glow, unreal.MaterialExpressionWorldPosition, -800, 0)
    gt = mel.create_material_expression(glow, unreal.MaterialExpressionTime, -800, 120)
    gc = _param(glow, unreal.MaterialExpressionVectorParameter, "Color", (0.6, 0.36, 1.0, 1.0), -800, 240)
    gi = _param(glow, unreal.MaterialExpressionScalarParameter, "Intensity", 18.0, -800, 360)
    gn = _custom(glow, GLOW_PULSE_HLSL, ("WP", "T", "C", "I"), unreal.CustomMaterialOutputType.CMOT_FLOAT3, -400, 120)
    for src, pin in ((gwp, "WP"), (gt, "T"), (gc, "C"), (gi, "I")):
        mel.connect_material_expressions(src, "", gn, pin)
    mel.connect_material_property(gn, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    base = _param(glow, unreal.MaterialExpressionVectorParameter, "Base", (0.18, 0.06, 0.35, 1.0), -400, -120)
    mel.connect_material_property(base, "", unreal.MaterialProperty.MP_BASE_COLOR)
    rough = mel.create_material_expression(glow, unreal.MaterialExpressionConstant, -400, 350)
    rough.set_editor_property("r", 0.3)
    mel.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
    mel.recompile_material(glow)
    eal.save_loaded_asset(glow, only_if_is_dirty=False)
    meridian_dir = "/Game/Environments/Meridian"
    for folder in (dest, meridian_dir):                         # the shared kit's glow, and Meridian's own
        if eal.does_asset_exist(folder + "/MI_ru_glow"):
            mi = eal.load_asset(folder + "/MI_ru_glow")
            mel.set_material_instance_parent(mi, glow)
            mel.set_material_instance_vector_parameter_value(mi, "Color", unreal.LinearColor(0.6, 0.36, 1.0, 1.0))
            mel.set_material_instance_scalar_parameter_value(mi, "Intensity", 18.0)
            mel.update_material_instance(mi)
            eal.save_loaded_asset(mi, only_if_is_dirty=False)
    inst(meridian_dir + "/MI_ru_beam", (0.75, 0.6, 1.0, 1.0), 12.0)   # (the crown's beam, in Meridian's detail)
    log("energy materials ready")


def _collision_mesh(mesh):
    """A mesh that exists to be collided with, exactly as built: not Nanite (a Nanite mesh's collision is made from
    its simplified fallback: the Crown kept 3% of its triangles, and shots, creatures and the nav mesh went through
    what was drawn), every triangle solid from both sides."""
    ns = mesh.get_editor_property("nanite_settings")
    ns.set_editor_property("enabled", False)
    mesh.set_editor_property("nanite_settings", ns)
    body = mesh.get_editor_property("body_setup")
    if body:
        body.set_editor_property("collision_trace_flag", unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
        body.set_editor_property("double_sided_geometry", True)
    eal.save_loaded_asset(mesh, only_if_is_dirty=False)


def meridian(master):
    """tools/blender/meridian.py (through export_fbx.py) -> /Game/Environments/Meridian: SM_MR_<zone> (the structure,
    Nanite, drawn only), SM_MR_<zone>_solid (what of it collides: exact, not Nanite, hidden in the level),
    SM_MR_<zone>_detail and SM_MR_backdrop (drawn only), SM_MR_blockers (invisible walls), SM_MRK_conduit and
    SM_MRK_barrier (actor pieces)."""
    src = os.path.join(SOURCE, "Meridian")
    dest = "/Game/Environments/Meridian"
    if not os.path.isdir(src):
        log("Meridian: skipped (SourceArt/Meridian missing, run export_unreal.sh)")
        return
    ensure_dir(dest)
    if not master.get_editor_property("used_with_nanite"):
        master.set_editor_property("used_with_nanite", True)
        mel.recompile_material(master)
        eal.save_loaded_asset(master, only_if_is_dirty=False)
    manifest = load_json(os.path.join(src, "export_fbx.json"))
    materials = load_json(os.path.join(src, "materials.json"))
    used = {base_slot(n) for a in manifest["assets"] for n in a["materials"]}
    tex = import_textures_for(src, materials, dest + "/Textures", used)
    instances = {key: make_instance(master, dest, key, materials.get(key) or {}, tex) for key in used}
    # the kit every operation uses (the barrier panel, the conduit: the Altered carry it wherever they go) lives in
    # /Game/Shared/Operation with its own materials: this folder is Meridian's alone
    shared = SHARED + "/Operation"
    kit = [a for a in manifest["assets"] if a["file"].startswith("MRK_")]
    kit_used = {base_slot(n) for a in kit for n in a["materials"]} | {"ru_glow"}
    ensure_dir(shared)
    kit_tex = import_textures_for(src, materials, shared + "/Textures", kit_used)
    kit_instances = {key: make_instance(master, shared, key, materials.get(key) or {}, kit_tex) for key in kit_used}
    # SO_MERIDIAN_ONLY=deepline,galleria: only those zones again (the skyline alone takes ten minutes)
    some = {z.strip() for z in os.environ.get("SO_MERIDIAN_ONLY", "").split(",") if z.strip()}
    for a in manifest["assets"]:
        name = os.path.splitext(a["file"])[0]
        if some and not any(name in (f"MR_{z}", f"MR_{z}_solid", f"MR_{z}_detail") for z in some):
            continue
        if eal.does_asset_exist(f"{dest}/SM_{name}"):           # a fresh import: the zones change content
            eal.delete_asset(f"{dest}/SM_{name}")
        if a in kit:
            if eal.does_asset_exist(f"{shared}/SM_{name}"):
                eal.delete_asset(f"{shared}/SM_{name}")
            _nanite(import_static(src, a["file"], shared, f"SM_{name}", kit_instances), True)
            continue
        mesh = import_static(src, a["file"], dest, f"SM_{name}", instances)
        if name.endswith("_solid") or name == "MR_blockers":
            _collision_mesh(mesh)
        else:
            _nanite(mesh, False)
    energy_materials()
    for old in ("M_SOEnergy", "MI_SOEnergy_Barrier", "M_SOGlowPulse"):   # (they were here before they were shared)
        if eal.does_asset_exist(f"{dest}/{old}"):
            users = [r for r in eal.find_package_referencers_for_asset(f"{dest}/{old}", False) if not str(r).endswith("/" + old)]
            if users:
                log(f"Meridian: {old} is still used by {', '.join(str(u) for u in users[:4])}: left in place")
            else:
                eal.delete_asset(f"{dest}/{old}")
    eal.save_directory(shared, only_if_is_dirty=False, recursive=True)
    eal.save_directory(dest, only_if_is_dirty=False, recursive=True)
    log(f"Meridian: {len(manifest['assets'])} pieces")


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
    ui_shape("M_UI_Plate", UI_PLATE_HLSL, dict(Fill=(.035, .045, .07, .92), FillLow=(.02, .026, .045, .94), Edge=(1, 1, 1, .14),
                                              Accent=(0, 0, 0, 0), Shape=(12, 1, 0, 0), Look=(0, 0, 0, 0)))
    # the armoury (the loadout screen, 2026-11-16): the backdrop, the platform, the cards, the bars, the perks' nodes,
    # the small glyphs; every one drawn by its own code, sized from the UV derivatives (crisp at any resolution)
    ui_shape("M_UI_Backdrop", UI_BACKDROP_HLSL, dict(Deep=(.0012, .002, .0048, 1), Tint=(.0075, .019, .040, 1), Beam=(.35, .72, 1.0, 1),
                                                    Stage=(.5, .5, .87, .97)), time=True)
    ui_shape("M_UI_Floor", UI_FLOOR_HLSL, dict(Ring=(.30, .78, 1.0, 1), Pool=(.18, .5, .95, 1), Look=(.24, 0, 0, 1)), time=True)
    ui_shape("M_UI_Card", UI_CARD_HLSL, dict(Rarity=(.7, .45, 1.0, 1), State=(0, 0, 0, 0), Shape=(18, .68, .9, 7)))
    ui_shape("M_UI_StatBar", UI_STATBAR_HLSL, dict(Values=(.6, .6, 10, 0), Fill=(.82, .9, 1.0, .95), Good=(.42, .95, .55, 1),
                                                  Bad=(1.0, .40, .34, 1)))
    ui_shape("M_UI_Hex", UI_HEX_HLSL, dict(Color=(.25, .85, 1.0, 1), Glyph=(0, 1, 0, 0)))
    ui_shape("M_UI_Glyph", UI_GLYPH_HLSL, dict(Color=(.85, .92, 1.0, 1), Glyph=(0, 0, 0, 0)), time=True)
    log("UI materials ready")


# The screens' own shapes, drawn by the material (no textures): sizes come from the UV derivatives, so one material
# draws a panel of any size with the same corner cut and hairline in pixels.
UI_PLATE_HLSL = """
// A plate: a rectangle with its top-right and bottom-left corners cut (the game's panel shape), a hairline round
// it, a fill that deepens downwards, an accent bar (left and / or bottom), a wash of the accent rising from the
// bottom, fine hatching in the lower right corner, a line of light under the top edge.
// Shape = (cut px, edge px, left bar px, bottom bar px); Look = (wash, hatch, top light, -)
float2 px = float2(1.0 / max(abs(ddx(UV.x)) + abs(ddy(UV.x)), 1e-6), 1.0 / max(abs(ddx(UV.y)) + abs(ddy(UV.y)), 1e-6));
float2 p = UV * px;
float d = min(min(p.x, p.y), min(px.x - p.x, px.y - p.y));
d = min(d, ((px.x - p.x) + p.y - Shape.x) * 0.70711);
d = min(d, (p.x + (px.y - p.y) - Shape.x) * 0.70711);
float inside = saturate(d + 0.5);
float edge = saturate(Shape.y - d + 0.5) * step(0.01, Shape.y);
float3 c = lerp(Fill.rgb, FillLow.rgb, UV.y);
float a = lerp(Fill.a, FillLow.a, UV.y);
float wash = Look.x * pow(UV.y, 1.8);
c = lerp(c, Accent.rgb, wash * 0.5);
a = saturate(a + wash * 0.3);
float h = step(frac((p.x + p.y) / 7.0), 0.15) * Look.y * saturate((UV.x + UV.y - 1.05) * 1.8);
c += h * 0.05;
float bar = max(step(p.x, Shape.z) * step(0.01, Shape.z), step(px.y - p.y, Shape.w) * step(0.01, Shape.w));
c = lerp(c, Accent.rgb, bar * Accent.a);
a = lerp(a, 1.0, bar * Accent.a);
c += Look.z * Edge.rgb * saturate(1.0 - p.y / 22.0) * 0.1;
c = lerp(c, Edge.rgb, edge * Edge.a);
a = lerp(a, 1.0, edge * Edge.a);
return float4(c, a * inside);
"""

UI_BACKDROP_HLSL = """
// The armoury's backdrop: night blue lit from the stage, light falling onto it from above, the broken orbit faint and
// turning behind the character, motes drifting up through the light, a horizon of light where the floor is, the
// edges sunk in dark. Deep = the edges, Tint = the lit middle, Beam = the light, Stage = (centre x, y, horizon y, opacity)
float2 px = float2(1.0 / max(abs(ddx(UV.x)) + abs(ddy(UV.x)), 1e-6), 1.0 / max(abs(ddx(UV.y)) + abs(ddy(UV.y)), 1e-6));
float m = min(px.x, px.y);
float2 q = (UV - Stage.xy) * px / m;
float r = length(q * float2(0.82, 1.0));
float3 c = lerp(Tint.rgb, Deep.rgb, smoothstep(0.02, 1.05, r));
// the light from above, widening as it falls
float wdt = 0.018 + 0.07 * UV.y;
float beam = exp(-q.x * q.x / wdt) * (1.0 - UV.y * 0.55) * smoothstep(0.0, 0.25, UV.y + 0.05);
c += Beam.rgb * beam * 0.045;
// the broken orbit behind the character: arcs in pieces, each turning at its own pace, a ring of ticks
float2 o = q - float2(0.0, -0.06);
float ro = length(o);
float ao = atan2(o.y, o.x) / 6.2831853 + 0.5;
float aa = max(fwidth(ro), 1e-5);
float arcs = 0.0;
arcs += saturate(1.0 - abs(ro - 0.355) / (aa * 1.3)) * step(frac(ao * 3.0 + Time * 0.006), 0.70) * 0.55;
arcs += saturate(1.0 - abs(ro - 0.455) / (aa * 1.0)) * step(frac(ao * 5.0 - Time * 0.009 + 0.30), 0.46) * 0.38;
arcs += saturate(1.0 - abs(ro - 0.585) / (aa * 1.7)) * step(frac(ao * 2.0 + Time * 0.004 + 0.60), 0.64) * 0.30;
arcs += saturate(1.0 - abs(ro - 0.405) / (aa * 5.0)) * step(frac(ao * 150.0 + Time * 0.15), 0.10) * 0.22;
arcs += saturate(1.0 - abs(ro - 0.74) / (aa * 1.0)) * step(frac(ao * 7.0 + Time * 0.003 + 0.15), 0.30) * 0.18;
c += Beam.rgb * arcs * 0.12;
// motes drifting up through the light (two layers)
float mot = 0.0;
for (int k = 0; k < 2; k++)
{
    float sc = k == 0 ? 24.0 : 13.0;
    float2 g = UV * px / m * sc + float2(k * 7.31, Time * (0.05 + k * 0.035));
    float2 id = floor(g);
    float2 f = frac(g) - 0.5;
    float h = frac(sin(dot(id, float2(127.1, 311.7))) * 43758.5453);
    float h2 = frac(sin(dot(id, float2(269.5, 183.3))) * 43758.5453);
    float2 off = float2(h - 0.5, h2 - 0.5) * 0.7;
    float dd = length(f - off);
    float tw = 0.45 + 0.55 * sin(Time * (0.8 + h * 1.7) + h2 * 6.2831);
    mot += step(0.84, h) * exp(-dd * dd * (k == 0 ? 2600.0 : 1300.0)) * tw;
}
c += Beam.rgb * mot * 0.3 * (1.0 - 0.6 * smoothstep(0.25, 1.0, r));
// the horizon of light at the floor's height
float hz = exp(-pow((UV.y - Stage.z) * 20.0, 2.0)) * exp(-q.x * q.x * 1.4);
c += Beam.rgb * hz * 0.035;
// the edges sink into the dark
c *= 1.0 - 0.6 * smoothstep(0.45, 1.4, r);
return float4(c, Stage.w);
"""

UI_FLOOR_HLSL = """
// The platform the character stands on, seen from in front and a little above: rings of light in perspective (one in
// pieces turning, one of fine ticks), a pool of light, the dark of the feet's shadow; nearer the eye is brighter.
// Ring, Pool = colours; Look = (squash: the ellipse's height to its width, -, -, opacity)
float2 px = float2(1.0 / max(abs(ddx(UV.x)) + abs(ddy(UV.x)), 1e-6), 1.0 / max(abs(ddx(UV.y)) + abs(ddy(UV.y)), 1e-6));
float2 q = (UV - 0.5) * 2.0;
q.y *= px.y / px.x;
q.y /= max(Look.x, 0.05);
float r = length(q);
float ang = atan2(q.y, q.x) / 6.2831853 + 0.5;
float aa = max(fwidth(r), 1e-5);
float front = 0.55 + 0.45 * saturate(q.y * 0.9 + 0.5);
float ring1 = saturate(1.0 - abs(r - 0.30) / (aa * 1.5));
float ring2 = saturate(1.0 - abs(r - 0.46) / (aa * 2.2)) * step(frac(ang * 3.0 + Time * 0.02), 0.78);
float ring3 = saturate(1.0 - abs(r - 0.62) / (aa * 1.2)) * step(frac(ang * 5.0 - Time * 0.035), 0.55);
float ticks = saturate(1.0 - abs(r - 0.78) / (aa * 7.0)) * step(frac(ang * 120.0 + Time * 0.25), 0.18);
float ring5 = saturate(1.0 - abs(r - 0.95) / (aa * 1.0));
float rings = ring1 * 0.85 + ring2 * 0.7 + ring3 * 0.45 + ticks * 0.42 + ring5 * 0.28;
rings *= front * saturate(1.0 - (r - 0.86) / 0.2);
float pool = exp(-r * r * 6.0);
float glow = saturate(rings + pool * 0.42);
float3 c = Ring.rgb * rings + Pool.rgb * pool * 0.5;
float shadow = exp(-r * r / 0.010) * 0.7;
float a = saturate(glow + shadow * (1.0 - glow));
c = c / max(a, 1e-4) * glow;
return float4(c, a * Look.w);
"""

UI_CARD_HLSL = """
// An armoury card: two corners cut (top left, bottom right), the rarity's light rising in it from the lower right and
// glowing behind the item's picture, faint scan lines, a hairline in the rarity's colour (bright when hovered, doubled
// and pale cyan when chosen) with its light inside it, a rarity diamond in the cut corner, an accent along the foot.
// Rarity = colour; State = (hover, chosen, -, empty); Shape = (cut px, glow centre x, glow strength, diamond px)
float2 px = float2(1.0 / max(abs(ddx(UV.x)) + abs(ddy(UV.x)), 1e-6), 1.0 / max(abs(ddx(UV.y)) + abs(ddy(UV.y)), 1e-6));
float2 p = UV * px;
float cut = Shape.x;
float d = min(min(p.x, p.y), min(px.x - p.x, px.y - p.y));
d = min(d, (p.x + p.y - cut) * 0.70711);
d = min(d, ((px.x - p.x) + (px.y - p.y) - cut) * 0.70711);
float inside = saturate(d + 0.5);
float hover = State.x, chosen = State.y, empty = State.w;
float3 rar = Rarity.rgb;
float3 c = lerp(float3(0.0062, 0.0090, 0.0175), float3(0.0030, 0.0042, 0.0090), UV.y);
float a = 0.93;
float rise = saturate(UV.x * 0.5 + UV.y * 0.8 - 0.5);
c = lerp(c, rar * 0.11, rise * rise * (0.45 + 0.3 * hover) * (1.0 - empty));
float2 g = (UV - float2(Shape.y, 0.55)) / float2(0.34, 0.70);
c += rar * exp(-dot(g, g) * 2.0) * Shape.z * (0.075 + 0.05 * hover) * (1.0 - empty);
c += 0.0025 * step(frac(p.y / 3.0), 0.34);
float inner = exp(-max(d, 0.0) / 8.0) * (0.05 * hover + 0.09 * chosen);
float3 lit = lerp(rar, float3(0.45, 0.9, 1.0), chosen * 0.55);
c += lit * inner;
float w = 1.0 + chosen;
float edge = saturate(w - d + 0.5);
float ea = lerp(0.42, 1.0, saturate(max(hover, chosen))) * lerp(1.0, 0.45, empty);
c = lerp(c, lit, edge * ea);
a = lerp(a, 1.0, edge * ea);
float2 mk = p - float2(cut * 0.55 + 7.0, cut * 0.55 + 7.0);
float md = abs(mk.x) + abs(mk.y);
float dia = saturate(Shape.w - md + 0.5) - saturate(Shape.w * 0.42 - md + 0.5);
c = lerp(c, rar, dia * lerp(1.0, 0.35, empty));
float foot = step(px.y - p.y, 2.0) * saturate(1.0 - UV.x / 0.4) * (1.0 - empty);
c = lerp(c, rar, foot);
c += 0.012 * saturate(1.0 - p.y / 20.0) * (0.6 + hover);
return float4(c, a * inside);
"""

UI_STATBAR_HLSL = """
// A stat's bar: a faint track, the value in segments with a bright cap, and what it gains (Good) or loses (Bad) against
// the one equipped. Values = (value 0..1, the equipped one's 0..1, segments, -)
float2 px = float2(1.0 / max(abs(ddx(UV.x)) + abs(ddy(UV.x)), 1e-6), 1.0 / max(abs(ddx(UV.y)) + abs(ddy(UV.y)), 1e-6));
float v = saturate(Values.x), cmp = saturate(Values.y);
float segs = max(Values.z, 1.0);
float gap = step(frac(UV.x * segs), 1.0 - 2.0 * segs / px.x);
float3 c = float3(1.0, 1.0, 1.0);
float a = 0.09;
float lo = min(v, cmp), hi = max(v, cmp);
if (UV.x < lo) { c = Fill.rgb; a = Fill.a; }
else if (UV.x < hi) { c = v > cmp ? Good.rgb : Bad.rgb; a = v > cmp ? 1.0 : 0.6; }
a *= gap;
float cap = saturate(1.0 - abs(UV.x * px.x - v * px.x) / 1.5);
c = lerp(c, float3(1.0, 1.0, 1.0), cap * 0.6);
a = max(a, cap * 0.95);
return float4(c, a);
"""

UI_HEX_HLSL = """
// A perk's node: a hexagon (flat top) with a hairline, a soft glow round it and an inner ring, a dark heart, and a glyph
// of light in it. Color = colour; Glyph = (which glyph 0..7, how lit 0..1, -, -)
float2 px = float2(1.0 / max(abs(ddx(UV.x)) + abs(ddy(UV.x)), 1e-6), 1.0 / max(abs(ddx(UV.y)) + abs(ddy(UV.y)), 1e-6));
float2 q = (UV - 0.5) * 2.0;
float2 aq = abs(q);
float hd = max(aq.y, aq.x * 0.866025 + aq.y * 0.5) / 0.866025;
float unit = 2.0 / px.x;
float lit = lerp(0.55, 1.0, saturate(Glyph.y));
float inside = saturate((0.86 - hd) / unit + 0.5);
float outline = saturate(1.0 - abs(hd - 0.86) / (unit * 1.7));
float halo = exp(-max(hd - 0.86, 0.0) / 0.045) * (1.0 - inside) * 0.55;
float ring = saturate(1.0 - abs(hd - 0.66) / (unit * 1.1)) * 0.4;
float rr = length(q);
float lw = unit * 1.7;
int k = (int)(Glyph.x + 0.5);
float g = 0.0;
if (k == 0) { g = saturate(1.0 - abs(rr - 0.30) / lw) + saturate((0.10 - rr) / unit + 0.5); }
else if (k == 1) { g = saturate(1.0 - abs(aq.x + aq.y - 0.34) / lw) + saturate((0.08 - (aq.x + aq.y)) / unit + 0.5); }
else if (k == 2) { g = saturate((0.42 - (pow(aq.x, 0.55) + pow(aq.y, 0.55))) / (unit * 2.0) + 0.5); }
else if (k == 3) { g = saturate(1.0 - abs(rr - 0.22) / lw) + saturate(1.0 - aq.x / lw) * step(0.12, aq.y) * step(aq.y, 0.40) + saturate(1.0 - aq.y / lw) * step(0.12, aq.x) * step(aq.x, 0.40); }
else if (k == 4) { g = step(aq.y, 0.30) * max(saturate(1.0 - aq.x / (lw * 1.4)), saturate(1.0 - abs(aq.x - 0.19) / (lw * 1.4))); }
else if (k == 5) { float2 t = float2(aq.x, q.y + 0.06); float td = max(t.x * 0.866 + t.y * 0.5, -t.y); g = saturate(1.0 - abs(td - 0.20) / lw); }
else if (k == 6) { g = saturate(1.0 - abs(rr - 0.34) / lw) + saturate(1.0 - abs(rr - 0.18) / lw); }
else { float h2 = max(aq.y, aq.x * 0.866025 + aq.y * 0.5) / 0.866025; g = saturate((0.30 - h2) / unit + 0.5) - saturate((0.16 - h2) / unit + 0.5); }
g = saturate(g);
float3 c = float3(0.016, 0.022, 0.04) + Color.rgb * 0.10;
float a = inside * 0.94;
c = c * inside + Color.rgb * (outline + halo + ring * inside + g * inside) * lit;
a = saturate(a + outline + halo * 0.7);
return float4(c, a);
"""

UI_GLYPH_HLSL = """
// The armoury's small glyphs, drawn in light: 0 the emblem (the broken orbit round a diamond), 1 credits, 2 alloy, 3 the
// vault, 4 power, 5 plating, 6 mending, 7 stride, 8 ordnance, 9 impact, 10 focus, 11 the fists, 12 a lock, 13 a blade.
// Color = colour; Glyph = (which, -, -, -)
float2 px = float2(1.0 / max(abs(ddx(UV.x)) + abs(ddy(UV.x)), 1e-6), 1.0 / max(abs(ddx(UV.y)) + abs(ddy(UV.y)), 1e-6));
float2 q = (UV - 0.5) * 2.0;
float2 aq = abs(q);
float u = 2.0 / min(px.x, px.y);
float lw = u * 1.6;
float r = length(q);
float ang = atan2(q.y, q.x) / 6.2831853 + 0.5;
int k = (int)(Glyph.x + 0.5);
float g = 0.0;
if (k == 0)
{
    g = saturate(1.0 - abs(r - 0.78) / (lw * 1.3)) * step(frac(ang * 3.0 + Time * 0.02), 0.72);
    g += saturate((0.36 - (aq.x + aq.y)) / u + 0.5) - saturate((0.16 - (aq.x + aq.y)) / u + 0.5);
    float2 sat = q - float2(cos(Time * 0.6), sin(Time * 0.6)) * 0.78;
    g += saturate((0.09 - length(sat)) / u + 0.5);
}
else if (k == 1) { g = saturate(1.0 - abs(r - 0.70) / lw) + saturate(1.0 - abs(r - 0.46) / lw) + saturate(1.0 - aq.x / lw) * step(aq.y, 0.26); }
else if (k == 2) { float h = max(aq.y, aq.x * 0.866 + aq.y * 0.5) / 0.866; g = saturate(1.0 - abs(h - 0.78) / lw) + saturate((0.36 - h) / u + 0.5); }
else if (k == 3) { float b = max(aq.x, aq.y); g = saturate(1.0 - abs(b - 0.70) / lw) + (saturate(1.0 - aq.x / lw) + saturate(1.0 - aq.y / lw)) * step(b, 0.70); }
else if (k == 4) { float dm = aq.x + aq.y; g = saturate((0.85 - dm) / u + 0.5) - saturate((0.40 - dm) / u + 0.5); }
else if (k == 5) { float sh = max(aq.x * 0.9 + q.y * 0.45, -q.y * 0.8); g = saturate(1.0 - abs(sh - 0.62) / lw) + saturate((0.30 - max(aq.x * 0.9 + q.y * 0.45, -q.y * 0.8)) / u + 0.5); }
else if (k == 6) { g = saturate(1.0 - abs(r - 0.80) / lw) + (saturate(1.0 - aq.x / (lw * 1.6)) * step(aq.y, 0.48) + saturate(1.0 - aq.y / (lw * 1.6)) * step(aq.x, 0.48)); }
else if (k == 7) { float c1 = abs(aq.y * 0.9 - (q.x + 0.25)); float c2 = abs(aq.y * 0.9 - (q.x - 0.25)); g = (saturate(1.0 - c1 / (lw * 1.4)) + saturate(1.0 - c2 / (lw * 1.4))) * step(aq.y, 0.55) * step(abs(q.x), 0.75); }
else if (k == 8) { float2 b = q - float2(0.0, 0.12); g = saturate(1.0 - abs(length(b) - 0.55) / lw) + step(abs(q.x), 0.16) * step(-0.78, q.y) * step(q.y, -0.52); }
else if (k == 9) { g = saturate(1.0 - abs(frac(ang * 8.0) - 0.25) * 8.0) * step(0.30, r) * step(r, 0.85) + saturate((0.22 - r) / u + 0.5); }
else if (k == 10) { float lid = abs(aq.y - (0.55 - q.x * q.x * 0.55)); g = saturate(1.0 - lid / lw) * step(aq.x, 0.9) + saturate((0.20 - r) / u + 0.5); }
else if (k == 11)
{
    float kn = 1e3;
    for (int f = 0; f < 4; f++) { kn = min(kn, abs(length(q - float2(-0.45 + f * 0.30, -0.36)) - 0.15)); }
    float2 pb = abs(q - float2(0.0, 0.20)) - float2(0.56, 0.36);
    float palm = abs(length(max(pb, 0.0)) + min(max(pb.x, pb.y), 0.0) - 0.08);
    float2 ta = float2(-0.58, 0.10), tb = float2(0.10, 0.02);
    float th = saturate(dot(q - ta, tb - ta) / dot(tb - ta, tb - ta));
    float thumb = abs(length(q - ta - (tb - ta) * th) - 0.11);
    g = saturate(1.0 - kn / lw) + saturate(1.0 - palm / lw) * step(-0.18, q.y) + saturate(1.0 - thumb / lw);
}
else if (k == 12) { float body = max(aq.x - 0.48, abs(q.y - 0.25) - 0.38); g = saturate((-body) / u + 0.5) * (1.0 - saturate((0.10 - length(q - float2(0.0, 0.22))) / u + 0.5)); g += saturate(1.0 - abs(length(q - float2(0.0, -0.18)) - 0.30) / lw) * step(q.y, -0.13); }
else { float2 t = float2(q.x * 0.7071 + q.y * 0.7071, -q.x * 0.7071 + q.y * 0.7071); g = saturate((0.14 - (abs(t.y) + abs(t.x) * 0.16)) / u + 0.5) * step(abs(t.x), 0.88); }
g = saturate(g);
return float4(Color.rgb, g * Color.a);
"""


def ui_shape(name, code, vectors, time=False):
    """A UI material whose whole picture is one Custom node: vector parameters in, colour + opacity out."""
    path = "/Game/UI/" + name
    if eal.does_asset_exist(path):
        mat = eal.load_asset(path)
        mel.delete_all_material_expressions(mat)
    else:
        mat = tools.create_asset(name, "/Game/UI", unreal.Material, unreal.MaterialFactoryNew())
    mat.set_editor_property("material_domain", unreal.MaterialDomain.MD_UI)
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
    uv = mel.create_material_expression(mat, unreal.MaterialExpressionTextureCoordinate, -900, 0)
    shape = mel.create_material_expression(mat, unreal.MaterialExpressionCustom, -450, 0)
    shape.set_editor_property("code", code)
    shape.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT4)
    names = ["UV"] + list(vectors) + (["Time"] if time else [])
    inputs = []
    for n in names:
        ci = unreal.CustomInput()
        ci.set_editor_property("input_name", n)
        inputs.append(ci)
    shape.set_editor_property("inputs", inputs)
    mel.connect_material_expressions(uv, "", shape, "UV")
    for k, (n, value) in enumerate(vectors.items()):
        v = mel.create_material_expression(mat, unreal.MaterialExpressionVectorParameter, -900, 120 + k * 200)
        v.set_editor_property("parameter_name", n)
        v.set_editor_property("default_value", unreal.LinearColor(*value))
        mel.connect_material_expressions(v, "RGBA", shape, n)
    if time:
        t = mel.create_material_expression(mat, unreal.MaterialExpressionTime, -900, -150)
        mel.connect_material_expressions(t, "", shape, "Time")
    rgb = mel.create_material_expression(mat, unreal.MaterialExpressionComponentMask, -150, -60)
    for ch, on in (("r", True), ("g", True), ("b", True), ("a", False)):
        rgb.set_editor_property(ch, on)
    alpha = mel.create_material_expression(mat, unreal.MaterialExpressionComponentMask, -150, 120)
    for ch, on in (("r", False), ("g", False), ("b", False), ("a", True)):
        alpha.set_editor_property(ch, on)
    mel.connect_material_expressions(shape, "", rgb, "")
    mel.connect_material_expressions(shape, "", alpha, "")
    mel.connect_material_property(rgb, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    mel.connect_material_property(alpha, "", unreal.MaterialProperty.MP_OPACITY)
    mel.recompile_material(mat)
    eal.save_loaded_asset(mat, only_if_is_dirty=False)


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
    # SO_AUDIO_ONLY=move_,footstep_metal: only the sounds whose names start with one of these
    prefixes = [x.strip() for x in os.environ.get("SO_AUDIO_ONLY", "").split(",") if x.strip()]
    for f in sorted(os.listdir(src)):
        if not f.endswith(".wav") or (prefixes and not any(f.startswith(x) for x in prefixes)):
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


def difficulty():
    """Data/game_data.json "difficulty" -> /Game/Data/DA_Difficulty (USODifficultyTable): the levels and the default
    (SO_IMPORT_ONLY=difficulty). Every number is a scale on what the creatures already have."""
    game = load_json(GAME_DATA)
    d = game.get("difficulty")
    if not d:
        return
    ensure_dir("/Game/Data")
    path = "/Game/Data/DA_Difficulty"
    if eal.does_asset_exist(path):
        table = eal.load_asset(path)
    else:
        factory = unreal.DataAssetFactory()
        factory.set_editor_property("data_asset_class", unreal.SODifficultyTable)
        table = tools.create_asset("DA_Difficulty", "/Game/Data", unreal.SODifficultyTable, factory)
    levels = []
    for lid, l in d["levels"].items():
        lv = unreal.SODifficulty()
        lv.set_editor_property("id", lid)
        lv.set_editor_property("name", unreal.Text(l.get("name", lid)))
        for key, prop in (("notice", "notice"), ("reaction", "reaction"), ("aimError", "aim_error"), ("burst", "burst"),
                          ("burstPause", "burst_pause"), ("patience", "patience"), ("coverHold", "cover_hold"),
                          ("flankShare", "flank_share"), ("abilityCooldown", "ability_cooldown"), ("health", "health"),
                          ("damage", "damage")):
            if key in l:
                lv.set_editor_property(prop, float(l[key]))
        levels.append(lv)
    table.set_editor_property("levels", levels)
    table.set_editor_property("default", d.get("default", "standard"))
    eal.save_loaded_asset(table, only_if_is_dirty=False)
    log(f"DA_Difficulty: {len(levels)} levels, default {d.get('default', 'standard')}")


def melee(master=None, defaults=None):
    """Data/game_data.json "melee" -> /Game/Data/DA_Melee (USOMeleeTable): hand to hand, a style per way of fighting
    (the fists, a blade): its guard clip, its chain of light blows and its heavy blow (SO_IMPORT_ONLY=melee). A style
    with a "mesh" (a blade: tools/blender/sarketh_guns.py, exported like a gun to SourceArt/Weapons/<Dir>) has it
    imported the way a gun's body is (its materials, the set's maps, its own baked maps) and set on the style."""
    d = load_json(GAME_DATA).get("melee")
    if not d:
        return
    ensure_dir("/Game/Data")
    path = "/Game/Data/DA_Melee"
    if eal.does_asset_exist(path):
        table = eal.load_asset(path)
    else:
        factory = unreal.DataAssetFactory()
        factory.set_editor_property("data_asset_class", unreal.SOMeleeTable)
        table = tools.create_asset("DA_Melee", "/Game/Data", unreal.SOMeleeTable, factory)

    def blow(b):
        x = unreal.SOMeleeBlow()
        x.set_editor_property("clip", b["clip"])
        for key, prop in (("hit", "hit_time"), ("recover", "recover"), ("damage", "damage"), ("range", "range"), ("angle", "angle"),
                          ("force", "force"), ("stagger", "stagger"), ("lunge", "lunge"), ("launch", "launch"), ("hitStop", "hit_stop"),
                          ("shock", "shock")):
            if key in b:
                x.set_editor_property(prop, float(b[key]))
        x.set_editor_property("swing_sound", b.get("swing", "None"))
        x.set_editor_property("hit_sound", b.get("hitSound", "None"))
        return x

    styles = []
    for sid, st in d.items():
        if sid.startswith("_"):
            continue
        y = unreal.SOMeleeStyle()
        y.set_editor_property("id", sid)
        y.set_editor_property("name", unreal.Text(st.get("name", sid)))
        y.set_editor_property("guard", st["guard"])
        y.set_editor_property("light", [blow(b) for b in st["light"]])
        y.set_editor_property("heavy", blow(st["heavy"]))
        for key in ("finisher", "rush", "sweep", "riser", "air"):          # (the named moves: light, light, heavy; ...)
            if key in st:
                y.set_editor_property(key, blow(st[key]))
        g = st.get("block") or {}
        y.set_editor_property("block_clip", g.get("clip", "None"))
        for key, prop in (("hold", "block_hold"), ("scale", "block_scale"), ("parry", "parry_window"), ("parryStagger", "parry_stagger"),
                          ("counterTime", "counter_time"), ("counter", "counter_scale")):
            if key in g:
                y.set_editor_property(prop, float(g[key]))
        y.set_editor_property("chain_grace", float(st.get("chainGrace", 0.45)))
        y.set_editor_property("edge", bool(st.get("edge", False)))
        if st.get("edgeColor"):
            y.set_editor_property("edge_color", hex_color(st["edgeColor"]))
        y.set_editor_property("set_id", st.get("set", "None"))
        y.set_editor_property("lore", unreal.Text(st.get("lore", "")))
        if st.get("mesh") and master is not None:
            folder = weapon_dir(st["mesh"])
            src = os.path.join(SOURCE, "Weapons", folder)
            if os.path.isdir(src):
                dest = f"/Game/Weapons/{folder}"
                ensure_dir(dest)
                instances = gun_instances(master, src, dest, load_json(os.path.join(src, "materials.json")), defaults["clear"], st["mesh"])
                y.set_editor_property("mesh", import_static(src, st["mesh"] + ".fbx", dest, f"SM_{folder}", instances))
                icon = os.path.join(ICONS, "guns", f"icon_{st['mesh']}.png")
                if os.path.exists(icon):
                    y.set_editor_property("icon", import_ui_texture(icon, dest, f"T_Icon_{folder}"))
                log(f"SM_{folder}: the {sid} style's mesh")
            else:
                log(f"{sid}: its mesh {src} is missing (export it like a gun)")
        styles.append(y)
    table.set_editor_property("styles", styles)
    eal.save_loaded_asset(table, only_if_is_dirty=False)
    log(f"DA_Melee: {len(styles)} styles ({', '.join(str(x.get_editor_property('id')) for x in styles)})")


SPECIES_DATA = os.path.normpath(os.path.join(PROJECT, "Data", "species.json"))


def species():
    """Data/species.json -> /Game/Data/DA_Species (USOSpeciesTable): every species' numbers (SO_IMPORT_ONLY=species).
    A species the file does not have yet is written into it from its class first, so a new creature's numbers
    appear there to be tuned; after that the file is their source. Keys: see USOSpeciesTable."""
    data = load_json(SPECIES_DATA) if os.path.exists(SPECIES_DATA) else {}
    added = []
    for sid in unreal.SOSpeciesLibrary.get_species():
        sid = str(sid)
        numbers = {str(k): round(float(v), 4) for k, v in unreal.SOSpeciesLibrary.get_class_numbers(sid).items()}
        entry = data.setdefault(sid, {})
        new = sorted(k for k in numbers if k not in entry)   # (a whole new species, or a number its class has gained)
        for k in new:
            entry[k] = numbers[k]
        if new:
            added.append(f"{sid} (+{len(new)})")
        for k in sorted(entry):
            if k not in numbers:
                log(f"species.json: WARNING '{sid}' has no number '{k}' (misspelt, or gone from its class): it does nothing")
    if added:
        with open(SPECIES_DATA, "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, indent=2, sort_keys=True)
            f.write("\n")
        log(f"species.json: wrote from the classes: {', '.join(added)}")
    ensure_dir("/Game/Data")
    path = "/Game/Data/DA_Species"
    if eal.does_asset_exist(path):
        table = eal.load_asset(path)
    else:
        factory = unreal.DataAssetFactory()
        factory.set_editor_property("data_asset_class", unreal.SOSpeciesTable)
        table = tools.create_asset("DA_Species", "/Game/Data", unreal.SOSpeciesTable, factory)
    entries = []
    for sid in sorted(data):
        entry = unreal.SOSpeciesNumbers()
        entry.set_editor_property("species", sid)
        entry.set_editor_property("numbers", {unreal.Name(k): float(v) for k, v in data[sid].items()})
        entries.append(entry)
    table.set_editor_property("species", entries)
    eal.save_loaded_asset(table, only_if_is_dirty=False)
    log(f"DA_Species: {len(entries)} species")


def attributes():
    """Data/game_data.json "attributes" -> /Game/Data/DA_Attributes (USOAttributeTable): what a point of each of the
    six character attributes is worth, and how an armour piece turns into points (SO_IMPORT_ONLY=attributes)."""
    game = load_json(GAME_DATA)
    a = game.get("attributes")
    if not a:
        return
    ensure_dir("/Game/Data")
    path = "/Game/Data/DA_Attributes"
    if eal.does_asset_exist(path):
        table = eal.load_asset(path)
    else:
        factory = unreal.DataAssetFactory()
        factory.set_editor_property("data_asset_class", unreal.SOAttributeTable)
        table = tools.create_asset("DA_Attributes", "/Game/Data", unreal.SOAttributeTable, factory)
    which = {"plating": unreal.SOAttribute.PLATING, "mending": unreal.SOAttribute.MENDING, "stride": unreal.SOAttribute.STRIDE,
             "ordnance": unreal.SOAttribute.ORDNANCE, "impact": unreal.SOAttribute.IMPACT, "focus": unreal.SOAttribute.FOCUS}
    rules = []
    for key, r in a["rules"].items():
        rule = unreal.SOAttributeRule()
        rule.set_editor_property("attribute", which[key])
        rule.set_editor_property("name", unreal.Text(r.get("name", key)))
        rule.set_editor_property("effect", unreal.Text(r.get("effect", "")))
        rule.set_editor_property("at_max", float(r.get("atMax", 1.0)))
        rule.set_editor_property("at_max2", float(r.get("atMax2", 1.0)))
        rules.append(rule)
    armour = a.get("armour", {})
    table.set_editor_property("max", float(a.get("max", 100.0)))
    table.set_editor_property("rules", rules)
    table.set_editor_property("points_per_armour", float(armour.get("pointsPerArmour", 2.0)))
    table.set_editor_property("rarity_scale", [float(x) for x in armour.get("rarityScale", [1.0])])
    table.set_editor_property("per_power", float(armour.get("perPower", 0.005)))
    table.set_editor_property("lean", float(armour.get("lean", 0.55)))
    table.set_editor_property("slot_lean", {slot: which[v] for slot, v in armour.get("slotLean", {}).items()})
    eal.save_loaded_asset(table, only_if_is_dirty=False)
    log(f"DA_Attributes: {len(rules)} rules, max {a.get('max', 100)}")


def progression():
    """Data/game_data.json "progression" -> /Game/Data/DA_Progression (USOProgressionTable): the experience a level
    takes, how far a level lets gear be upgraded, and what an upgrade costs (SO_IMPORT_ONLY=progression)."""
    game = load_json(GAME_DATA)
    p = game.get("progression")
    if not p:
        return
    ensure_dir("/Game/Data")
    path = "/Game/Data/DA_Progression"
    if eal.does_asset_exist(path):
        table = eal.load_asset(path)
    else:
        factory = unreal.DataAssetFactory()
        factory.set_editor_property("data_asset_class", unreal.SOProgressionTable)
        table = tools.create_asset("DA_Progression", "/Game/Data", unreal.SOProgressionTable, factory)
    xp, cap, up = p.get("xp", {}), p.get("powerCap", {}), p.get("upgrade", {})
    table.set_editor_property("xp_base", int(xp.get("base", 600)))
    table.set_editor_property("xp_per_level", int(xp.get("perLevel", 250)))
    table.set_editor_property("max_level", int(xp.get("maxLevel", 40)))
    table.set_editor_property("power_cap_base", int(cap.get("base", 20)))
    table.set_editor_property("power_cap_per_level", int(cap.get("perLevel", 3)))
    table.set_editor_property("upgrade_step", int(up.get("step", 2)))
    table.set_editor_property("upgrade_credits", float(up.get("credits", 120)))
    table.set_editor_property("upgrade_credits_per_power", float(up.get("creditsPerPower", 6)))
    table.set_editor_property("upgrade_alloy", float(up.get("alloy", 3)))
    table.set_editor_property("upgrade_alloy_per_power", float(up.get("alloyPerPower", 0.1)))
    table.set_editor_property("upgrade_rarity_cost", [float(x) for x in up.get("rarityCost", [1.0])])
    eal.save_loaded_asset(table, only_if_is_dirty=False)
    log(f"DA_Progression: max level {xp.get('maxLevel', 40)}, upgrade step {up.get('step', 2)}")


def bosses():
    """Data/game_data.json "bosses" -> /Game/Data/DA_Boss_<Id> (USOBossData): a boss fight as data: its phases by
    health, the kit of each, the shield between them, its weak points (SO_IMPORT_ONLY=bosses)."""
    game = load_json(GAME_DATA)
    ensure_dir("/Game/Data")
    for boss_id, b in game.get("bosses", {}).items():
        if not isinstance(b, dict):
            continue  # (the note)
        name = "DA_Boss_" + boss_id[0].upper() + boss_id[1:]
        path = "/Game/Data/" + name
        if eal.does_asset_exist(path):
            table = eal.load_asset(path)
        else:
            factory = unreal.DataAssetFactory()
            factory.set_editor_property("data_asset_class", unreal.SOBossData)
            table = tools.create_asset(name, "/Game/Data", unreal.SOBossData, factory)
        phases = []
        for p in b.get("phases", []):
            ph = unreal.SOBossPhase()
            ph.set_editor_property("name", unreal.Text(p.get("name", "")))
            ph.set_editor_property("from_health", float(p.get("from", 1.0)))
            ph.set_editor_property("kit", p.get("kit", "None"))
            ph.set_editor_property("cooldown", float(p.get("cooldown", 1.0)))
            ph.set_editor_property("speed", float(p.get("speed", 1.0)))
            ph.set_editor_property("damage_taken", float(p.get("damageTaken", 1.0)))
            pause = p.get("movePause", [3.0, 4.5])
            ph.set_editor_property("move_pause", unreal.Vector2D(float(pause[0]), float(pause[1])))
            ph.set_editor_property("shield", bool(p.get("shield", False)))
            ph.set_editor_property("conduits", int(p.get("conduits", 3)))
            ph.set_editor_property("stagger", float(p.get("stagger", 5.0)))
            phases.append(ph)
        points = []
        for w in b.get("weakPoints", []):
            wp = unreal.SOWeakPoint()
            wp.set_editor_property("name", w.get("name", "None"))
            wp.set_editor_property("bone", w.get("bone", "None"))
            off = w.get("offset", [0, 0, 0])
            wp.set_editor_property("offset", unreal.Vector(float(off[0]), float(off[1]), float(off[2])))
            wp.set_editor_property("radius", float(w.get("radius", 40.0)))
            wp.set_editor_property("scale", float(w.get("scale", 1.5)))
            wp.set_editor_property("front", bool(w.get("front", False)))
            wp.set_editor_property("break_damage", float(w.get("breakDamage", 0.0)))
            wp.set_editor_property("break_stagger", float(w.get("breakStagger", 3.0)))
            points.append(wp)
        table.set_editor_property("boss_id", boss_id)
        table.set_editor_property("phases", phases)
        table.set_editor_property("weak_points", points)
        table.set_editor_property("stagger_damage", float(b.get("staggerDamage", 1.5)))
        table.set_editor_property("shield_text", unreal.Text(b.get("shieldText", "")))
        eal.save_loaded_asset(table, only_if_is_dirty=False)
        log(f"{name}: {len(phases)} phases, {len(points)} weak points")


ABILITY_CLASSES = {
    "strike": "/Script/SOCombat.SOAbility_Strike",
    "grenade": "/Script/SOCombat.SOAbility_Grenade",
    "guard": "/Script/SOCombat.SOAbility_Guard",
    "slam": "/Script/SOCombat.SOAbility_Slam",
    "bolt": "/Script/SOAI.SOAbility_Bolt",
    "pulse": "/Script/SOCombat.SOAbility_Pulse",
    "rally": "/Script/SOAI.SOAbility_Rally",
    "sweep": "/Script/SOCombat.SOAbility_Sweep",
    "eruption": "/Script/SOCombat.SOAbility_Eruption",
    "barrage": "/Script/SOAI.SOAbility_Barrage",
    "snipe": "/Script/SOAI.SOAbility_Snipe",
}


def kits():
    """Data/game_data.json "kits" -> /Game/Abilities/DA_Kit_<Id> (USOAbilitySet): a kit's abilities by slot and their
    numbers (SO_IMPORT_ONLY=kits). The ability classes are C++ (ABILITY_CLASSES); every number comes from the json."""
    game = load_json(GAME_DATA)
    ensure_dir("/Game/Abilities")
    slots = {"grenade": unreal.SOAbilitySlot.GRENADE, "melee": unreal.SOAbilitySlot.MELEE, "class": unreal.SOAbilitySlot.CLASS,
             "movement": unreal.SOAbilitySlot.MOVEMENT, "ultimate": unreal.SOAbilitySlot.ULTIMATE}
    for kit_id, k in game.get("kits", {}).items():
        name = "DA_Kit_" + kit_id[0].upper() + kit_id[1:]
        path = "/Game/Abilities/" + name
        if eal.does_asset_exist(path):
            kit = eal.load_asset(path)
        else:
            factory = unreal.DataAssetFactory()
            factory.set_editor_property("data_asset_class", unreal.SOAbilitySet)
            kit = tools.create_asset(name, "/Game/Abilities", unreal.SOAbilitySet, factory)
        grants = []
        for slot, a in k.get("abilities", {}).items():
            cls = unreal.load_class(None, ABILITY_CLASSES[a["ability"]])
            if cls is None:
                raise RuntimeError(f"kit {kit_id}: ability class for '{a['ability']}' not found")
            g = unreal.SOAbilityGrant()
            g.set_editor_property("slot", slots[slot])
            g.set_editor_property("ability", cls)
            g.set_editor_property("display_name", unreal.Text(a.get("name", "")))
            g.set_editor_property("cooldown", float(a.get("cooldown", 0.0)))
            g.set_editor_property("charges", int(a.get("charges", 1)))
            g.set_editor_property("ultimate_cost", float(a.get("ultimateCost", 0.0)))
            g.set_editor_property("wind_up", float(a.get("windUp", 0.0)))
            for key in ("damage", "range", "radius", "angle", "duration", "force", "magnitude"):
                g.set_editor_property(key, float(a.get(key, 0.0)))
            g.set_editor_property("sound", a.get("sound", "None"))
            g.set_editor_property("wind_up_sound", a.get("windUpSound", "None"))
            g.set_editor_property("clip", a.get("clip", "None"))
            g.set_editor_property("clip_lead", float(a.get("clipLead", 0.0)))
            g.set_editor_property("status", a.get("status", "None"))
            grants.append(g)
        kit.set_editor_property("kit_id", kit_id)
        kit.set_editor_property("display_name", unreal.Text(k.get("name", kit_id)))
        kit.set_editor_property("abilities", grants)
        kit.set_editor_property("ultimate_per_second", float(k.get("ultimatePerSecond", 0.0)))
        kit.set_editor_property("ultimate_per_damage", float(k.get("ultimatePerDamage", 0.0)))
        kit.set_editor_property("ultimate_per_kill", float(k.get("ultimatePerKill", 0.0)))
        passive = k.get("passive", {})
        kit.set_editor_property("passive_name", unreal.Text(passive.get("name", "")))
        kit.set_editor_property("close_range", float(passive.get("closeRange", 0.0)))
        kit.set_editor_property("close_kill_shield", float(passive.get("closeKillShield", 0.0)))
        eal.save_loaded_asset(kit, only_if_is_dirty=False)
        log(f"{name}: {len(grants)} abilities")


def main():
    if not os.path.isdir(SOURCE):
        raise RuntimeError(f"{SOURCE} is missing: run bash tools/blender/export_unreal.sh first")
    # The legacy FBX importer honours FbxImportUI (Interchange would ignore these options).
    unreal.SystemLibrary.execute_console_command(None, "Interchange.FeatureFlags.Import.FBX 0")
    defaults = default_textures()
    master = master_material(defaults)
    hair = hair_material(defaults)
    PARENT_FOR.update({k: hair for k in ("hair", "hair__cap", "hair__brow", "hair__lash")})   # head hair, brows, lashes
    # SO_IMPORT_ONLY=arms,weapons,... re-imports just those steps (default: everything).
    only = {s.strip() for s in os.environ.get("SO_IMPORT_ONLY", "").split(",") if s.strip()}
    want = lambda step: not only or step in only
    if want("player") or "player_skin" in only:
        skin = skin_material(defaults)
        PARENT_FOR.update({k: skin for k in ("skin", "skin_face")})                       # the players' skin
    if want("player"):
        for sex in ("male", "female"):
            player_wardrobe(sex, master)
    if "player_clips" in only:
        for sex in ("male", "female"):
            player_clips(sex)
    if "player_pieces" in only:
        player_pieces(os.environ.get("SO_PLAYER_PIECES", ""))
    if want("stalker"):
        character(os.path.join(SOURCE, "Characters", "Stalker"), "/Game/Characters/Stalker", "SK_Stalker", "A_Stalker_",
                  master, stalker_extra, flesh=True)
    if want("altered"):
        one = os.environ.get("SO_ALTERED_ONLY", "")   # (e.g. Bearer: just that one, the others are left as they are)
        for k in ALTERED:
            if os.path.isdir(os.path.join(SOURCE, "Characters", k)) and (not one or k in one.split(",")):
                character(os.path.join(SOURCE, "Characters", k), f"/Game/Characters/{k}", f"SK_{k}", f"A_{k}_", master, stalker_extra, flesh=True)
    if want("weapons") or want("rifle"):
        weapons(master, defaults)
    if "gunnumbers" in only:
        gun_numbers()
    if "icons" in only:
        icons_only()
    if "gunslots" in only:
        gun_slots()
    if "guntextures" in only:
        gun_textures()
    if "worldmaps" in only:
        world_maps(defaults)
    if "player_textures" in only:
        player_textures()
    if want("fx"):
        fx_master()
        decal_material()
        warn_material()
        fx_meshes()
    elif want("warn"):
        warn_material()
    if want("audio"):
        audio()
    if want("ui"):
        ui_materials()
    if want("kits"):
        kits()
    if want("difficulty"):
        difficulty()
    if want("melee"):
        melee(master, defaults)
    if want("species"):
        species()
    if want("bosses"):
        bosses()
    if want("attributes"):
        attributes()
    if want("progression"):
        progression()
    if "perks" in only:
        perks_only()
    if "bodies" in only:
        bodies()
    if want("nexus"):
        nexus(master)
    if want("nexuscity"):
        nexus_city(master, defaults)
    if want("meridian"):
        meridian(master)
    elif want("energy"):
        energy_materials()
    log("done")


main()
