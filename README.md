# WORLD EX — Shattered Orbit

A sci-fi looter shooter in Unreal Engine 5.8 (`unreal/ShatteredOrbit`, C++). First person with a third-person view,
modular male and female player bodies with armour, rolled loot, and Nexus Prime, the big city.

Every 3D model and texture is made by our own Python scripts in headless Blender (`tools/blender/`), every sound by our
own synthesis (`tools/audio/sfx_synth.py`). No third-party assets.

- Build the Blender sources: `bash tools/blender/build_all.sh`
- Export them (and the players) for Unreal: `bash tools/blender/export_unreal.sh`
- Import, build, test and play: see `unreal/ShatteredOrbit/README.md`
- Plan: `docs/unreal/MIGRATION_PLAN.md`; concept art: `art/reference/`
