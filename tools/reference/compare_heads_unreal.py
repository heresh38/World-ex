"""Run in a SCRATCH Unreal project (MetaHumanSDK + MetaHuman plugins enabled), never in ours:
   UnrealEditor.exe Scratch.uproject -ExecutePythonScript=compare_heads_unreal.py   (env CMP_OUT, CMP_SRC)
 Epic's MetaHuman head and our two heads in one Unreal scene, the same clay material, light and
camera, eye lines aligned; eight views each (show-only capture) for side-by-side and overlay sheets."""
import unreal, math, os
OUT = os.environ["CMP_OUT"]
SRC = os.environ.get("CMP_SRC", "C:/Dev/World-ex/unreal/ShatteredOrbit/SourceArt/Characters")   # player_<sex>__Body.fbx folders
eal = unreal.EditorAssetLibrary
els = unreal.EditorLevelLibrary
tools = unreal.AssetToolsHelpers.get_asset_tools()
unreal.SystemLibrary.execute_console_command(None, "Interchange.FeatureFlags.Import.FBX 0")
unreal.EditorLevelLibrary.new_level("/Game/CmpRef")
world = unreal.EditorLevelLibrary.get_editor_world()


def import_static(fbx, name):
    ui = unreal.FbxImportUI()
    ui.set_editor_property("import_mesh", True); ui.set_editor_property("import_textures", False)
    ui.set_editor_property("import_materials", False); ui.set_editor_property("import_as_skeletal", False)
    ui.set_editor_property("automated_import_should_detect_type", False)
    ui.set_editor_property("mesh_type_to_import", unreal.FBXImportType.FBXIT_STATIC_MESH)
    sm = ui.get_editor_property("static_mesh_import_data")
    sm.set_editor_property("combine_meshes", True); sm.set_editor_property("convert_scene_unit", False)
    sm.set_editor_property("auto_generate_collision", False)
    t = unreal.AssetImportTask()
    t.set_editor_property("filename", fbx); t.set_editor_property("destination_path", "/Game/Ours")
    t.set_editor_property("destination_name", name); t.set_editor_property("automated", True)
    t.set_editor_property("replace_existing", True); t.set_editor_property("options", ui)
    tools.import_asset_tasks([t])
    return unreal.load_asset("/Game/Ours/" + name)


# clay for everything (shape only)
mel = unreal.MaterialEditingLibrary
if eal.does_asset_exist("/Game/M_Clay"):
    eal.delete_asset("/Game/M_Clay")
clay = tools.create_asset("M_Clay", "/Game", unreal.Material, unreal.MaterialFactoryNew())
c = mel.create_material_expression(clay, unreal.MaterialExpressionConstant3Vector, -300, 0); c.constant = unreal.LinearColor(.62, .6, .58, 1)
r = mel.create_material_expression(clay, unreal.MaterialExpressionConstant, -300, 200); r.r = .55
mel.connect_material_property(c, "", unreal.MaterialProperty.MP_BASE_COLOR)
mel.connect_material_property(r, "", unreal.MaterialProperty.MP_ROUGHNESS)
mel.recompile_material(clay)


def place(mesh, loc):
    a = els.spawn_actor_from_object(mesh, loc)
    comp = a.static_mesh_component
    for i in range(comp.get_num_materials()):
        comp.set_material(i, clay)
    return a


MH_EYE = unreal.Vector(0, 9.06, 160.42)   # MetaHuman template eye centre (cm, Unreal space)
mh = place(unreal.load_asset("/MetaHumanSDK/TemplateAssets/SM_MH_Head"), unreal.Vector(0, 0, 0))
heads = {"mh": mh}
for sex, eye in (("male", (0, 5.36, 171.25)), ("female", (0, 4.97, 153.94))):
    m = import_static(f"{SRC}/Player{sex.capitalize()}/player_{sex}__Body.fbx", f"SM_cmp_{sex}")
    b = m.get_bounding_box()
    unreal.log(f"CMP {sex} bounds {b.min} {b.max}")
    heads[sex] = place(m, unreal.Vector(MH_EYE.x - eye[0], MH_EYE.y - eye[1], MH_EYE.z - eye[2]))

sun = els.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(0, 0, 400), unreal.Rotator(0, -30, -69))
sun.light_component.set_intensity(6.0)
sky = els.spawn_actor_from_class(unreal.SkyLight, unreal.Vector(0, 0, 300)); sky.light_component.set_intensity(1.0)
els.spawn_actor_from_class(unreal.SkyAtmosphere, unreal.Vector(0, 0, 0))
pp = els.spawn_actor_from_class(unreal.PostProcessVolume, unreal.Vector(0, 0, 0)); pp.set_editor_property("unbound", True)
s = pp.settings
s.set_editor_property("override_auto_exposure_method", True); s.set_editor_property("auto_exposure_method", unreal.AutoExposureMethod.AEM_MANUAL)
s.set_editor_property("override_auto_exposure_bias", True); s.set_editor_property("auto_exposure_bias", 11.0)
pp.set_editor_property("settings", s)

rt = unreal.RenderingLibrary.create_render_target2d(world, 1024, 1024, unreal.TextureRenderTargetFormat.RTF_RGBA8)
cap = els.spawn_actor_from_class(unreal.SceneCapture2D, unreal.Vector(0, 0, 0))
cc = cap.capture_component2d
cc.set_editor_property("texture_target", rt)
cc.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
cc.set_editor_property("fov_angle", 30.0)
C = MH_EYE + unreal.Vector(0, -9.0, 4.0)          # head centre, a little above and behind the eyes
VIEWS = [("a_front", 0, 0), ("b_3q_left", 45, 0), ("c_profile_left", 90, 0), ("d_back_3q_left", 135, 0), ("e_back", 180, 0),
         ("f_3q_right", -45, 0), ("g_profile_right", -90, 0), ("h_above", 20, 40)]
home = {k: a.get_actor_location() for k, a in heads.items()}
for key, actor in heads.items():
    for k, a in heads.items():       # only this head in front of the camera
        a.set_actor_location(home[k] if k == key else home[k] + unreal.Vector(0, 0, -20000), False, False)
    for name, yaw, pitch in VIEWS:
        y, p = math.radians(yaw), math.radians(pitch)
        loc = C + unreal.Vector(math.sin(y) * math.cos(p) * 80.0, math.cos(y) * math.cos(p) * 80.0, math.sin(p) * 80.0)
        cap.set_actor_location_and_rotation(loc, unreal.MathLibrary.find_look_at_rotation(loc, C), False, False)
        cc.capture_scene()
        unreal.RenderingLibrary.export_render_target(world, rt, OUT, f"{key}_{name}.png")
    unreal.log(f"CMP captured {key}")
unreal.SystemLibrary.quit_editor()
