"""Builds /Game/Maps/L_Nexus: Nexus Prime, the big city (8.3 x 5.3 km inside its wall).

The city itself is one ASONexusCity actor (Source/SOWorld/Public/SONexusCity.h) that builds the plan tiles, the
buildings on every lot, lamps, stations and landmarks from Data/nexus_plan.json + Data/nexus_city.json (nothing of it
is saved into the level). This script adds the sky, sun (tagged "Sun" for USOTimeOfDaySubsystem), sky light, a long
haze for the distance, post process, the area map (ASOMapInfo covering the wall) with its places (gates, districts,
the Spire, the metro hubs; each on the nearest road so arrivals land in the street), the shuttle back to the
Proving Range and the player start on the Spire plaza, facing the Spire.

Headless:
    UnrealEditor-Cmd.exe <path>/ShatteredOrbit.uproject -run=pythonscript -script="<path>/Content/Python/make_nexus_map.py" -unattended -nullrhi
"""
import json
import math
import os

import unreal

MAP = "/Game/Maps/L_Nexus"
PROJECT = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
eal = unreal.EditorAssetLibrary


def log(msg):
    unreal.log("[make_nexus_map] " + msg)


def world(e, n, z=0.0):
    """plan metres (E, N) -> world cm (X = N, Y = E)"""
    return (n * 100.0, e * 100.0, z * 100.0)


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
    plan = json.load(open(os.path.join(PROJECT, "Data", "nexus_plan.json")))
    city = json.load(open(os.path.join(PROJECT, "Data", "nexus_city.json")))
    nodes = plan["roads"]["nodes"]
    kerb = city["kerb"]

    def on_road(p):
        """the road node nearest to plan point p (E, N)"""
        return min(nodes, key=lambda q: (q[0] - p[0]) ** 2 + (q[1] - p[1]) ** 2)

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

    spawn(unreal.SONexusCity, (0, 0, 0), label="NexusCity", folder="City")

    # sky and light: afternoon sun, a long haze so the far districts and the mountains fade
    sun = spawn(unreal.DirectionalLight, (0, 0, 2000), (-34, 140, 0), "Sun", "Lighting")
    sc = sun.get_component_by_class(unreal.DirectionalLightComponent)
    sc.set_mobility(unreal.ComponentMobility.MOVABLE)
    sc.set_editor_property("intensity", 9.0)
    sc.set_editor_property("atmosphere_sun_light", True)
    sun.set_editor_property("tags", ["Sun"])
    spawn(unreal.SkyAtmosphere, label="SkyAtmosphere", folder="Lighting")
    spawn(unreal.VolumetricCloud, label="VolumetricCloud", folder="Lighting")
    sky = spawn(unreal.SkyLight, (0, 0, 3000), label="SkyLight", folder="Lighting")
    skc = sky.get_component_by_class(unreal.SkyLightComponent)
    skc.set_mobility(unreal.ComponentMobility.MOVABLE)
    skc.set_editor_property("real_time_capture", True)
    fog = spawn(unreal.ExponentialHeightFog, (0, 0, -200), label="HeightFog", folder="Lighting")
    fc = fog.get_component_by_class(unreal.ExponentialHeightFogComponent)
    fc.set_editor_property("fog_density", 0.004)
    fc.set_editor_property("fog_height_falloff", 0.06)
    fc.set_editor_property("start_distance", 3000.0)
    fc.set_editor_property("enable_volumetric_fog", True)
    ppv = spawn(unreal.PostProcessVolume, label="PostProcess", folder="Lighting")
    ppv.set_editor_property("unbound", True)
    pps = ppv.get_editor_property("settings")
    for key, value in (("bloom_intensity", 0.6), ("bloom_threshold", 1.0), ("vignette_intensity", 0.3),
                       ("film_grain_intensity", 0.05), ("ambient_occlusion_intensity", 0.6),
                       ("auto_exposure_bias", 0.2), ("scene_fringe_intensity", 0.12)):
        pps.set_editor_property("override_" + key, True)
        pps.set_editor_property(key, value)
    ppv.set_editor_property("settings", pps)

    # where the player starts: the south side of the Spire plaza, facing north to the Spire
    start = (0.0, -230.0)
    spawn(unreal.PlayerStart, world(*start, kerb + 1.0), (0, 0, 0), "PlayerStart", "Gameplay")

    # the area map: the square round the wall
    wall = plan["wall"]
    e0, e1 = min(p[0] for p in wall), max(p[0] for p in wall)
    n0, n1 = min(p[1] for p in wall), max(p[1] for p in wall)
    info = spawn(unreal.SOMapInfo, world((e0 + e1) / 2, (n0 + n1) / 2), label="MapInfo", folder="Map")
    info.set_editor_property("area_name", unreal.Text("Nexus Prime"))
    info.set_editor_property("half_size", max(e1 - e0, n1 - n0) * 50.0 + 15000.0)

    beacon = unreal.load_asset("/Game/Environments/Nexus/SM_NX_beacon")
    K = unreal.SOMapPointKind
    places = [("The Spire", "The city's heart", K.FAST_TRAVEL, (0.0, -260.0), None),
              ("Shuttle to the Proving Range", "Back to the range", K.AREA_TRAVEL, (60.0, -300.0), "/Game/Maps/L_TestRange"),
              ("Operation: Meridian Fall", "The first operation", K.AREA_TRAVEL, (-60.0, -300.0), "/Game/Maps/L_Meridian")]
    for name, gp in plan["gates"].items():
        places.append((f"{dict(N='North', S='South', W='West', E='East')[name]} Gate", "The city wall", K.LANDMARK, on_road((gp[0] * .96, gp[1] * .96)), None))
    for key, d in plan["districts"].items():
        if key == "spire":
            continue
        loc = plan["key_locations"].get(d["label"])
        if loc is None:
            xs = [p[0] for p in d["poly"]]; ys = [p[1] for p in d["poly"]]
            loc = (sum(xs) / len(xs), sum(ys) / len(ys))
        places.append((d["label"], "District", K.FAST_TRAVEL, on_road(loc), None))
    for i, h in enumerate(plan["metro"]["hubs"]):
        places.append((f"Metro Hub {i + 1}", "Metro loop", K.FAST_TRAVEL, on_road(h), None))
    for label, sub, kind, p, level in places:
        # face the point toward the Spire so arrivals look into the city
        yaw = math.degrees(math.atan2(-p[0], -p[1])) if (p[0] or p[1]) else 0.0
        mp = spawn(unreal.SOMapPoint, world(p[0], p[1], kerb), (0, yaw, 0), f"Map_{label}", "Map")
        mp.set_editor_property("label", unreal.Text(label))
        mp.set_editor_property("subtitle", unreal.Text(sub))
        mp.set_editor_property("kind", kind)
        mp.set_editor_property("fast_travel", kind != K.LANDMARK)
        if level:
            mp.set_editor_property("travel_level", level)
        if beacon and kind != K.LANDMARK:
            mp.get_editor_property("beacon").set_static_mesh(beacon)

    w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    w.get_world_settings().set_editor_property("default_game_mode", unreal.SOGameMode)
    if not level_subsystem.save_current_level():
        raise RuntimeError("could not save " + MAP)
    log(f"saved {MAP} ({len(places)} map points)")


main()
