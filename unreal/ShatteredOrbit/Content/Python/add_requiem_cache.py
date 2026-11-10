"""Adds the Void Requiem cache to the existing /Game/Maps/L_TestRange without rebuilding the map (make_test_map.py
places the same actor when the range is rebuilt): a reliquary that hands out one Legendary copy of each of the first
operation's nine reward guns.

UnrealEditor-Cmd <uproject> -run=pythonscript -script=<this file> -unattended -nullrhi -nosplash
"""
import unreal

MAP = "/Game/Maps/L_TestRange"
LABEL = "VoidRequiemCache"


def main():
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    if not levels.load_level(MAP):
        raise RuntimeError("could not load " + MAP)
    for a in actors.get_all_level_actors():
        if a.get_actor_label() == LABEL:
            actors.destroy_actor(a)
    cache = actors.spawn_actor_from_class(unreal.SOReliquary, unreal.Vector(450, -300, 0), unreal.Rotator(roll=0, pitch=0, yaw=146))
    cache.set_actor_label(LABEL)
    cache.set_editor_property("reward_set", "void_requiem")
    cache.set_editor_property("source_name", "Void Requiem cache")
    cache.set_editor_property("rearm_time", 10.0)
    cache.set_folder_path("Gameplay")
    if not levels.save_current_level():
        raise RuntimeError("could not save " + MAP)
    unreal.log("[add_requiem_cache] cache placed in " + MAP)


main()
