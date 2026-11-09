"""Builds /Game/Maps/L_Meridian: Operation: Meridian Fall (the first operation).

Everything comes from the plan (tools/operation/meridian_plan.py -> Data/op_meridian.json) and the art
(tools/blender/meridian.py -> /Game/Environments/Meridian + Data/op_meridian_art.json):
  - the zones (SM_MR_<zone>: collide), their detail and the backdrop (no collision), the invisible blockers (hidden in
    game, block pawns only), all placed at the origin;
  - the operation (ASOOperation reading the plan), the barriers (ASOOperationBarrier), the player start at the entry;
  - a storm night: a cold low moon (not tagged "Sun": the clock does not move it), dark sky and clouds, dense purple-
    grey height fog with volumetrics, a dim sky light, the plan's lights (void crystals violet, fires amber, the
    crown's rim and beam), post process (exposure held down, bloom up, cool grade, vignette, grain);
  - the area map (ASOMapInfo + ASOMapPoint per plan map point, the shuttle back to Nexus Prime), the nav mesh bounds.

Headless:
    UnrealEditor-Cmd.exe <path>/ShatteredOrbit.uproject -run=pythonscript -script="<path>/Content/Python/make_operation_map.py" -unattended -nullrhi
"""
import json
import os

import unreal

MAP = "/Game/Maps/L_Meridian"
ENV = "/Game/Environments/Meridian"
PROJECT = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
eal = unreal.EditorAssetLibrary


def log(msg):
    unreal.log("[make_operation_map] " + msg)


def open_clean_level(level_subsystem, actor_subsystem):
    if not eal.does_directory_exist("/Game/Maps"):
        eal.make_directory("/Game/Maps")
    if eal.does_asset_exist(MAP):
        if not level_subsystem.load_level(MAP):
            raise RuntimeError("could not load " + MAP)
        keep = (unreal.WorldSettings.static_class(), unreal.Brush.static_class())
        actors = [a for a in actor_subsystem.get_all_level_actors() if a.get_class() not in keep]
        if actors:
            actor_subsystem.destroy_actors(actors)
        log(f"reusing {MAP} (cleared {len(actors)} actors)")
    elif not level_subsystem.new_level(MAP):
        raise RuntimeError("could not create " + MAP)


def main():
    plan = json.load(open(os.path.join(PROJECT, "Data", "op_meridian.json"), encoding="utf-8"))
    art_path = os.path.join(PROJECT, "Data", "op_meridian_art.json")
    art = json.load(open(art_path, encoding="utf-8")) if os.path.exists(art_path) else {"lights": []}
    level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    open_clean_level(level_subsystem, actor_subsystem)

    def spawn(cls, loc=(0, 0, 0), rot=(0, 0, 0), label=None, folder=None):
        pitch, yaw, roll = rot
        a = actor_subsystem.spawn_actor_from_class(cls, unreal.Vector(*loc), unreal.Rotator(roll=roll, pitch=pitch, yaw=yaw))
        if label:
            a.set_actor_label(label)
        if folder:
            a.set_folder_path(folder)
        return a

    # the city: every exported piece at the origin
    meshes = [a for a in eal.list_assets(ENV, recursive=False) if os.path.basename(a).split(".")[0].startswith("SM_MR_")]
    for path in sorted(meshes):
        name = os.path.basename(path).split(".")[0]
        mesh = eal.load_asset(path)
        a = spawn(unreal.StaticMeshActor, label=name[3:], folder="City")
        comp = a.static_mesh_component
        comp.set_static_mesh(mesh)
        comp.set_mobility(unreal.ComponentMobility.STATIC)
        if name.endswith("_detail") or name == "SM_MR_backdrop":
            comp.set_collision_profile_name("NoCollision")
            comp.set_editor_property("can_character_step_up_on", unreal.CanBeCharacterBase.ECB_NO)
            if name == "SM_MR_backdrop":
                comp.set_editor_property("cast_shadow", True)
        elif name == "SM_MR_blockers":
            # invisible walls: they stop players and creatures, never shots, sight or the camera
            a.set_actor_hidden_in_game(True)
            comp.set_cast_shadow(False)
            comp.set_collision_profile_name("BlockAllDynamic")
            comp.set_collision_response_to_all_channels(unreal.CollisionResponseType.ECR_IGNORE)
            comp.set_collision_response_to_channel(unreal.CollisionChannel.ECC_PAWN, unreal.CollisionResponseType.ECR_BLOCK)
            comp.set_editor_property("can_ever_affect_navigation", True)
    log(f"{len(meshes)} city pieces")

    # storm night
    moon = spawn(unreal.DirectionalLight, (0, 0, 3000), (-32, 205, 0), "Moon", "Lighting")
    mc = moon.get_component_by_class(unreal.DirectionalLightComponent)
    mc.set_mobility(unreal.ComponentMobility.MOVABLE)
    mc.set_editor_property("intensity", 2.4)
    mc.set_editor_property("light_color", unreal.Color(r=170, g=182, b=230, a=255))
    mc.set_editor_property("atmosphere_sun_light", True)
    mc.set_editor_property("dynamic_shadow_distance_movable_light", 25000.0)
    spawn(unreal.SkyAtmosphere, label="SkyAtmosphere", folder="Lighting")
    cloud = spawn(unreal.VolumetricCloud, label="VolumetricCloud", folder="Lighting")
    cc = cloud.get_component_by_class(unreal.VolumetricCloudComponent)
    cc.set_editor_property("layer_bottom_altitude", 1.2)
    cc.set_editor_property("layer_height", 6.0)
    sky = spawn(unreal.SkyLight, (0, 0, 3000), label="SkyLight", folder="Lighting")
    skc = sky.get_component_by_class(unreal.SkyLightComponent)
    skc.set_mobility(unreal.ComponentMobility.MOVABLE)
    skc.set_editor_property("real_time_capture", True)
    skc.set_editor_property("intensity", 1.0)
    fog = spawn(unreal.ExponentialHeightFog, (0, 0, -100), label="HeightFog", folder="Lighting")
    fc = fog.get_component_by_class(unreal.ExponentialHeightFogComponent)
    fc.set_editor_property("fog_density", 0.026)
    fc.set_editor_property("fog_height_falloff", 0.12)
    fc.set_editor_property("start_distance", 1500.0)
    fc.set_editor_property("fog_inscattering_luminance", unreal.LinearColor(0.06, 0.055, 0.09, 1.0))
    fc.set_editor_property("enable_volumetric_fog", True)
    fc.set_editor_property("volumetric_fog_scattering_distribution", 0.6)
    fc.set_editor_property("volumetric_fog_extinction_scale", 1.4)
    ppv = spawn(unreal.PostProcessVolume, label="PostProcess", folder="Lighting")
    ppv.set_editor_property("unbound", True)
    pps = ppv.get_editor_property("settings")
    for key, value in (("bloom_intensity", 1.1), ("bloom_threshold", 0.8), ("vignette_intensity", 0.45),
                       ("film_grain_intensity", 0.08), ("ambient_occlusion_intensity", 0.75),
                       ("auto_exposure_bias", -0.4), ("auto_exposure_min_brightness", 0.04), ("auto_exposure_max_brightness", 1.2),
                       ("scene_fringe_intensity", 0.2), ("color_saturation", unreal.Vector4(0.9, 0.9, 0.95, 1.0)),
                       ("color_gain_shadows", unreal.Vector4(0.92, 0.94, 1.08, 1.0)), ("white_temp", 6900.0)):
        try:
            pps.set_editor_property("override_" + key, True)
            pps.set_editor_property(key, value)
        except Exception as e:  # a renamed setting must not stop the map
            log(f"post process {key}: {e}")
    ppv.set_editor_property("settings", pps)

    # the plan's lights
    colours = {"void": (unreal.Color(r=160, g=95, b=255, a=255), 70.0), "fire": (unreal.Color(r=255, g=140, b=60, a=255), 55.0),
               "rim": (unreal.Color(r=170, g=110, b=255, a=255), 25.0), "beam": (unreal.Color(r=200, g=165, b=255, a=255), 120.0)}
    for i, L in enumerate(art["lights"]):
        col, intensity = colours.get(L["kind"], colours["void"])
        p = spawn(unreal.PointLight, tuple(L["at"]), label=f"Light_{L['kind']}_{i}", folder="Lighting/Points")
        pc = p.get_component_by_class(unreal.PointLightComponent)
        pc.set_mobility(unreal.ComponentMobility.MOVABLE)
        pc.set_editor_property("light_color", col)
        pc.set_editor_property("intensity", float(L.get("intensity") or intensity))
        pc.set_editor_property("attenuation_radius", float(L["radius"]))
        pc.set_editor_property("cast_shadows", L["kind"] == "beam")
        pc.set_editor_property("volumetric_scattering_intensity", {"void": 1.2, "fire": 1.0, "rim": 0.25, "beam": 0.0}.get(L["kind"], 1.0))
    log(f"{len(art['lights'])} lights")

    # the operation, its barriers, where players come in
    op = spawn(unreal.SOOperation, label="Operation", folder="Gameplay")
    op.set_editor_property("plan_file", "Data/op_meridian.json")
    for b in plan["barriers"]:
        c = b["c"]
        ba = spawn(unreal.SOOperationBarrier, (c[0], c[1], c[2] + b["height"] / 2.0), (0, b["yaw"], 0), f"Barrier_{b['id']}", "Gameplay")
        ba.set_editor_property("opens_at", b["opens"])
        ba.set_editor_property("width", float(b["width"]))
        ba.set_editor_property("height", float(b["height"]))
    for i, p in enumerate(plan["pylons"]):                       # where the Colossus's conduits rise
        tp = spawn(unreal.TargetPoint, (p[0], p[1], p[2] + 35.0), label=f"ConduitSocket_{i}", folder="Gameplay")
        tp.set_editor_property("tags", ["SOConduit"])
    first = plan["stages"][0]["checkpoint"]
    spawn(unreal.PlayerStart, (first[0], first[1], first[2]), (0, first[3], 0), "PlayerStart", "Gameplay")
    # the nav mesh only where the route is walked (plan metres: N0, N1, E0, E1, Z0, Z1): one box over the whole
    # route would take in every floor of every ruined tower and run out of tiles
    for i, (n0, n1, e0, e1, z0, z1) in enumerate((
            (-322, -196, -32, 32, -2, 9), (-200, -136, -37, 37, -2, 6), (-138, -38, -19, 19, -2, 9),
            (-46, 46, -46, 46, -3, 5), (-8, 8, 40, 80, -2, 13), (-10, 123, 72, 88, 7, 14), (106, 123, -10, 88, 7, 14),
            (118, 242, -42, 42, 7, 16))):
        nav = spawn(unreal.NavMeshBoundsVolume, ((n0 + n1) * 50.0, (e0 + e1) * 50.0, (z0 + z1) * 50.0), label=f"NavBounds_{i}", folder="Gameplay/Nav")
        nav.set_actor_scale3d(unreal.Vector((n1 - n0) / 2.0, (e1 - e0) / 2.0, (z1 - z0) / 2.0))   # the brush is 200 cm
    # the base breathing: loops (machinery, growth, the far chorus) and spores
    sounds = {"hum": "amb_alien_hum", "hive": "amb_hive", "chorus": "amb_alien_chorus"}
    for i, a in enumerate(art.get("ambience", [])):
        amb = spawn(unreal.SOAmbience, tuple(a["at"]), label=f"Ambience_{a['kind']}_{i}", folder="Ambience")
        amb.set_editor_property("sound", sounds[a["kind"]])
        amb.set_editor_property("volume", float(a["volume"]))
        amb.set_editor_property("radius", float(a["radius"]))
        amb.set_editor_property("spores", bool(a["spores"]))

    # the area map
    info = spawn(unreal.SOMapInfo, (-4000, 2500, 0), label="MapInfo", folder="Map")
    info.set_editor_property("area_name", unreal.Text("Meridian"))
    info.set_editor_property("half_size", 32000.0)
    beacon = unreal.load_asset("/Game/Environments/Nexus/SM_NX_beacon")
    K = unreal.SOMapPointKind
    kinds = {"FastTravel": K.FAST_TRAVEL, "Landmark": K.LANDMARK, "Mission": K.MISSION, "AreaTravel": K.AREA_TRAVEL}
    for m in plan["map"]:
        kind = kinds[m["kind"]]
        mp = spawn(unreal.SOMapPoint, tuple(m["at"]), (0, 0, 0), f"Map_{m['label']}", "Map")
        mp.set_editor_property("label", unreal.Text(m["label"]))
        mp.set_editor_property("subtitle", unreal.Text(m["subtitle"]))
        mp.set_editor_property("kind", kind)
        # quick travel only to the entry and back to the city: the route is walked, not skipped
        mp.set_editor_property("fast_travel", kind in (K.FAST_TRAVEL, K.AREA_TRAVEL))
        if kind == K.AREA_TRAVEL:
            mp.set_editor_property("travel_level", "/Game/Maps/L_Nexus")
        if beacon and kind == K.AREA_TRAVEL:
            mp.get_editor_property("beacon").set_static_mesh(beacon)

    w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    ws = w.get_world_settings()
    ws.set_editor_property("default_game_mode", unreal.SOGameMode)
    ws.set_editor_property("kill_z", -5000.0)
    if not level_subsystem.save_current_level():
        raise RuntimeError("could not save " + MAP)
    log(f"saved {MAP}")


main()
