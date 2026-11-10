"""Builds /Game/Maps/L_TestRange: the movement test range for stage 2.

Floor with a 1 m checker, perimeter walls, mantle ledges at 60 / 120 / 200 / 240 cm (plus a 300 cm wall that must
NOT be mantled), ramps at 15 / 30 / 50 degrees (the last one is too steep to walk), cover crates, sky atmosphere,
volumetric clouds, sun (tagged "Sun" for USOTimeOfDaySubsystem), sky light, height fog, an unbound post process
volume and a player start. The world settings use SOGameMode and the map is the game / editor default map.

The grey-box blocks use the engine's unit cube with our own procedural checker material (M_Greybox, no textures);
they are test geometry only and will never ship in a real level (real art comes from tools/blender).

Headless:
    UnrealEditor-Cmd.exe <path>/ShatteredOrbit.uproject -run=pythonscript -script="<path>/Content/Python/make_test_map.py" -unattended -nullrhi
"""

import os
import re

import unreal

MAP = "/Game/Maps/L_TestRange"
MAT_DIR = "/Game/Materials/Dev"
CUBE = "/Engine/BasicShapes/Cube.Cube"
TAG = "SOTestGeometry"

CHECKER_HLSL = """
float3 p = floor((WP + 0.37) / 100.0);
float k = fmod(abs(p.x + p.y + p.z), 2.0);
return Tint * lerp(0.78, 1.0, k);
"""

TINTS = {
    "MI_Greybox_Floor": (0.32, 0.33, 0.35),
    "MI_Greybox_Wall": (0.52, 0.53, 0.55),
    "MI_Greybox_Ledge": (0.85, 0.42, 0.12),
    "MI_Greybox_Ramp": (0.16, 0.48, 0.62),
    "MI_Greybox_Crate": (0.55, 0.47, 0.32),
}


def log(msg):
    unreal.log("[make_test_map] " + msg)


asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
eal = unreal.EditorAssetLibrary
mel = unreal.MaterialEditingLibrary


def ensure_dir(path):
    if not eal.does_directory_exist(path):
        eal.make_directory(path)


def make_materials():
    ensure_dir(MAT_DIR)
    path = f"{MAT_DIR}/M_Greybox"
    if eal.does_asset_exist(path):
        mat = eal.load_asset(path)
        mel.delete_all_material_expressions(mat)
    else:
        mat = asset_tools.create_asset("M_Greybox", MAT_DIR, unreal.Material, unreal.MaterialFactoryNew())

    wp = mel.create_material_expression(mat, unreal.MaterialExpressionWorldPosition, -700, 0)
    tint = mel.create_material_expression(mat, unreal.MaterialExpressionVectorParameter, -700, 200)
    tint.set_editor_property("parameter_name", "Tint")
    tint.set_editor_property("default_value", unreal.LinearColor(0.5, 0.5, 0.5, 1.0))
    custom = mel.create_material_expression(mat, unreal.MaterialExpressionCustom, -400, 0)
    custom.set_editor_property("code", CHECKER_HLSL)
    custom.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT3)
    custom.set_editor_property("description", "Checker1m")
    in_wp = unreal.CustomInput()
    in_wp.set_editor_property("input_name", "WP")
    in_tint = unreal.CustomInput()
    in_tint.set_editor_property("input_name", "Tint")
    custom.set_editor_property("inputs", [in_wp, in_tint])
    mel.connect_material_expressions(wp, "", custom, "WP")
    mel.connect_material_expressions(tint, "", custom, "Tint")
    mel.connect_material_property(custom, "", unreal.MaterialProperty.MP_BASE_COLOR)
    rough = mel.create_material_expression(mat, unreal.MaterialExpressionConstant, -400, 250)
    rough.set_editor_property("r", 0.82)
    mel.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
    mel.recompile_material(mat)
    eal.save_loaded_asset(mat, only_if_is_dirty=False)

    instances = {}
    for name, rgb in TINTS.items():
        ipath = f"{MAT_DIR}/{name}"
        if eal.does_asset_exist(ipath):
            mi = eal.load_asset(ipath)
        else:
            mi = asset_tools.create_asset(name, MAT_DIR, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
        mel.set_material_instance_parent(mi, mat)
        mel.set_material_instance_vector_parameter_value(mi, "Tint", unreal.LinearColor(rgb[0], rgb[1], rgb[2], 1.0))
        mel.update_material_instance(mi)
        eal.save_loaded_asset(mi, only_if_is_dirty=False)
        instances[name] = mi
    log("greybox materials ready")
    return instances


def open_clean_level(level_subsystem, actor_subsystem):
    ensure_dir("/Game/Maps")
    if eal.does_asset_exist(MAP):
        if not level_subsystem.load_level(MAP):
            raise RuntimeError("could not load " + MAP)
        keep = (unreal.WorldSettings.static_class(), unreal.Brush.static_class())  # world settings + the builder brush
        actors = [a for a in actor_subsystem.get_all_level_actors() if a.get_class() not in keep]
        if actors:
            actor_subsystem.destroy_actors(actors)
        log(f"reusing {MAP} (cleared {len(actors)} actors)")
    else:
        if not level_subsystem.new_level(MAP):
            raise RuntimeError("could not create " + MAP)
        log(f"created {MAP}")


def main():
    level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    mats = make_materials()
    cube = unreal.load_asset(CUBE)
    open_clean_level(level_subsystem, actor_subsystem)

    def spawn(cls, loc=(0, 0, 0), rot=(0, 0, 0), label=None):
        pitch, yaw, roll = rot
        actor = actor_subsystem.spawn_actor_from_class(cls, unreal.Vector(*loc), unreal.Rotator(roll=roll, pitch=pitch, yaw=yaw))
        if label:
            actor.set_actor_label(label)
        return actor

    def block(label, center, size, mat, rot=(0, 0, 0)):
        """A grey-box block: size in cm (x, y, z), engine cube is 100 cm."""
        actor = spawn(unreal.StaticMeshActor, center, rot, label)
        comp = actor.static_mesh_component
        comp.set_static_mesh(cube)
        comp.set_material(0, mats[mat])
        actor.set_actor_scale3d(unreal.Vector(size[0] / 100.0, size[1] / 100.0, size[2] / 100.0))
        actor.set_editor_property("tags", [TAG])
        actor.set_folder_path("Geometry")
        return actor

    # Floor 80 x 80 m, top at z = 0; perimeter walls 4 m.
    block("Floor", (0, 0, -10), (8000, 8000, 20), "MI_Greybox_Floor")
    for label, c, s in (
        ("Wall_N", (4000, 0, 200), (40, 8040, 400)),
        ("Wall_S", (-4000, 0, 200), (40, 8040, 400)),
        ("Wall_E", (0, 4000, 200), (8040, 40, 400)),
        ("Wall_W", (0, -4000, 200), (8040, 40, 400)),
    ):
        block(label, c, s, "MI_Greybox_Wall")

    # Mantle ledges in front of the player start (front faces at x = 800).
    for i, h in enumerate((60, 120, 200, 240, 300)):
        y = -1000 + i * 500
        mat = "MI_Greybox_Wall" if h > 245 else "MI_Greybox_Ledge"
        block(f"Ledge_{h}cm", (900, y, h / 2.0), (200, 300, h), mat)

    # Ramps behind the start, rising toward -x: 15 and 30 degrees walkable, 50 too steep.
    import math
    length, width, thick = 800.0, 300.0, 30.0
    for i, angle in enumerate((15, 30, 50)):
        a = math.radians(angle)
        cx = -1400.0 - (length / 2.0) * math.cos(a)
        cz = (length / 2.0) * math.sin(a) - (thick / 2.0) * math.cos(a)
        block(f"Ramp_{angle}deg", (cx, -900 + i * 700, cz), (length, width, thick), "MI_Greybox_Ramp", rot=(angle, 180, 0))

    # Cover crates.
    for i, (x, y) in enumerate(((400, 900), (550, 1150), (300, 1300))):
        block(f"Crate_{i}", (x, y, 50), (100, 100, 100), "MI_Greybox_Crate")

    # Sky and light.
    sun = spawn(unreal.DirectionalLight, (0, 0, 800), (-38, 35, 0), "Sun")
    sun_comp = sun.get_component_by_class(unreal.DirectionalLightComponent)
    sun_comp.set_mobility(unreal.ComponentMobility.MOVABLE)
    sun_comp.set_editor_property("intensity", 9.0)
    sun_comp.set_editor_property("atmosphere_sun_light", True)
    sun.set_editor_property("tags", ["Sun"])
    spawn(unreal.SkyAtmosphere, (0, 0, 0), label="SkyAtmosphere")
    spawn(unreal.VolumetricCloud, (0, 0, 0), label="VolumetricCloud")
    sky = spawn(unreal.SkyLight, (0, 0, 600), label="SkyLight")
    sky_comp = sky.get_component_by_class(unreal.SkyLightComponent)
    sky_comp.set_mobility(unreal.ComponentMobility.MOVABLE)
    sky_comp.set_editor_property("real_time_capture", True)
    fog = spawn(unreal.ExponentialHeightFog, (0, 0, -100), label="HeightFog")
    fog_comp = fog.get_component_by_class(unreal.ExponentialHeightFogComponent)
    fog_comp.set_editor_property("fog_density", 0.012)
    fog_comp.set_editor_property("enable_volumetric_fog", True)
    ppv = spawn(unreal.PostProcessVolume, (0, 0, 0), label="PostProcess")
    ppv.set_editor_property("unbound", True)
    # Stage 4 look: restrained bloom so muzzle flashes and sparks glow, soft vignette, a little grain, firmer AO,
    # exposure biased slightly up for the bright test range.
    pps = ppv.get_editor_property("settings")
    for key, value in (("bloom_intensity", 0.6), ("bloom_threshold", 1.0), ("vignette_intensity", 0.35),
                       ("film_grain_intensity", 0.06), ("ambient_occlusion_intensity", 0.65),
                       ("auto_exposure_bias", 0.3), ("scene_fringe_intensity", 0.15)):
        pps.set_editor_property("override_" + key, True)
        pps.set_editor_property(key, value)
    ppv.set_editor_property("settings", pps)
    for a in (sun, sky, fog, ppv):
        a.set_folder_path("Lighting")

    spawn(unreal.PlayerStart, (0, 0, 100), (0, 0, 0), "PlayerStart")

    # Stage 3: nav mesh over the floor (generated at runtime, RuntimeGeneration=Dynamic) and three stalker spawners
    # out past the ledges, facing the start.
    nav = spawn(unreal.NavMeshBoundsVolume, (0, 0, 150), label="NavBounds")
    nav.set_actor_scale3d(unreal.Vector(40.0, 40.0, 4.0))  # default brush is 200 cm
    nav.set_folder_path("Gameplay")
    for i, (x, y) in enumerate(((2600, -700), (2900, 600), (3400, 0))):
        spawner = spawn(unreal.SOEnemySpawner, (x, y, 0), (0, 180, 0), f"StalkerSpawner_{i}")
        spawner.set_folder_path("Gameplay")

    # Stage 5: the VANTHOS reward pool to try on the range (it reseals after 30 s here).
    reliquary = spawn(unreal.SOReliquary, (950, -800, 0), (0, 140, 0), "Reliquary")
    reliquary.set_folder_path("Gameplay")

    # The Void Requiem cache: one Legendary copy of each of the first operation's nine reward guns, to try here.
    cache = spawn(unreal.SOReliquary, (450, -300, 0), (0, 146, 0), "VoidRequiemCache")
    cache.set_editor_property("reward_set", "void_requiem")
    cache.set_editor_property("source_name", "Void Requiem cache")
    cache.set_editor_property("rearm_time", 10.0)
    cache.set_folder_path("Gameplay")

    # Stage 6: the area map (mini-map, map screen) with its places and the way to Nexus Prime
    info = spawn(unreal.SOMapInfo, (0, 0, 0), (0, 0, 0), "MapInfo")
    info.set_editor_property("area_name", unreal.Text("Proving Range"))
    info.set_editor_property("half_size", 4300.0)
    info.set_folder_path("Map")
    beacon = unreal.load_asset("/Game/Environments/Nexus/SM_NX_beacon")
    for label, sub, kind, loc, yaw, level in (
            ("Firing Line", "Where you start", unreal.SOMapPointKind.FAST_TRAVEL, (-300, 0, 0), 0, ""),
            ("Reliquary", "The VANTHOS reward pool", unreal.SOMapPointKind.MISSION, (950, -1250, 0), 90, ""),
            ("Stalker Field", "Live targets", unreal.SOMapPointKind.LANDMARK, (3000, 0, 0), 180, ""),
            ("Shuttle to Nexus Prime", "The city hub", unreal.SOMapPointKind.AREA_TRAVEL, (-2600, 2400, 0), -90, "/Game/Maps/L_Nexus")):
        p = spawn(unreal.SOMapPoint, loc, (0, yaw, 0), f"Map_{label}")
        p.set_editor_property("label", unreal.Text(label))
        p.set_editor_property("subtitle", unreal.Text(sub))
        p.set_editor_property("kind", kind)
        p.set_editor_property("fast_travel", kind != unreal.SOMapPointKind.LANDMARK)
        p.set_editor_property("travel_level", level)
        if beacon and kind != unreal.SOMapPointKind.LANDMARK:
            p.get_editor_property("beacon").set_static_mesh(beacon)
        p.set_folder_path("Map")

    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    world.get_world_settings().set_editor_property("default_game_mode", unreal.SOGameMode)

    if not level_subsystem.save_current_level():
        raise RuntimeError("could not save " + MAP)
    log(f"saved {MAP}")
    set_default_map()


def set_default_map():
    """Makes L_TestRange the game and editor default map in Config/DefaultEngine.ini."""
    ini = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_config_dir()), "DefaultEngine.ini")
    text = open(ini, encoding="utf-8").read() if os.path.exists(ini) else ""
    value = f"{MAP}.{MAP.rsplit('/', 1)[1]}"
    section = "[/Script/EngineSettings.GameMapsSettings]"
    if section not in text:
        text = f"{section}\nGameDefaultMap={value}\nEditorStartupMap={value}\n\n" + text
    else:
        for key in ("GameDefaultMap", "EditorStartupMap"):
            if re.search(rf"^{key}=.*$", text, flags=re.M):
                text = re.sub(rf"^{key}=.*$", f"{key}={value}", text, flags=re.M)
            else:
                text = text.replace(section, f"{section}\n{key}={value}", 1)
    with open(ini, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    log("default map set in " + ini)


main()
