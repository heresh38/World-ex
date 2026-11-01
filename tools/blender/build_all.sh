#!/bin/bash
# Rebuilds every texture and model with headless Blender. Usage: bash tools/blender/build_all.sh
set -e
cd "$(dirname "$0")/../.."
for s in textures ship_textures refs characters players civilians weapon_textures weapons viewmodel vehicle_textures vehicles ship_interior city props rural; do
  echo "== $s"
  blender --background --python tools/blender/$s.py 2>&1 | grep -E "^\[export|^\[ref|Error|Traceback|colliders" || true
done
# organic creatures: horror texture sets (hx_*), the Writhe infestation, the VANTHOS aliens and Earth's birds and stray
# cats (fauna.glb) (fleshkit.py SDF sculpting)
for s in horror_textures writhe aliens fauna; do
  echo "== $s"
  blender --background --python tools/blender/$s.py 2>&1 | grep -E "^\[export|^\[texture|Error|Traceback" || true
done
# trees: space-colonised broadleaf + whorled conifers, leaf/bark textures, impostor atlas, snow_c/_n ground textures
echo "== trees"
blender --background --python tools/blender/trees.py 2>&1 | grep -E "^\[export|^\[texture|^\[tris|Error|Traceback" || true
# water (ocean-sim normal maps, foam, spray sprite) and the New Meridian Spaceport (bakes its sp_* textures first)
for s in water_textures spaceport; do
  echo "== $s"
  blender --background --python tools/blender/$s.py 2>&1 | grep -E "^\[export|^\[texture|^\[spaceport|Error|Traceback" || true
done
# downtown New Meridian: numpy-painted facade sets (dt_*), building designs + LODs and the street kit
echo "== downtown"
blender --background --python tools/blender/downtown.py 2>&1 | grep -E "^\[export|^\[texture|^\[design|Error|Traceback" || true
