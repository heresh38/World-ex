#!/bin/bash
# Rebuilds every texture and model with headless Blender. Usage: bash tools/blender/build_all.sh
set -e
cd "$(dirname "$0")/../.."
for s in textures ship_textures refs characters players civilians weapon_textures weapons viewmodel vehicle_textures vehicles ship_interior city props rural; do
  echo "== $s"
  blender --background --python tools/blender/$s.py 2>&1 | grep -E "^\[export|^\[ref|Error|Traceback|colliders" || true
done
# organic creatures: horror texture sets (hx_*), the Writhe infestation and the VANTHOS aliens (fleshkit.py SDF sculpting)
for s in horror_textures writhe aliens; do
  echo "== $s"
  blender --background --python tools/blender/$s.py 2>&1 | grep -E "^\[export|^\[texture|Error|Traceback" || true
done
# water (ocean-sim normal maps, foam, spray sprite) and the New Meridian spaceport (bakes its ap_* textures first)
for s in water_textures airport; do
  echo "== $s"
  blender --background --python tools/blender/$s.py 2>&1 | grep -E "^\[export|^\[texture|^\[airport|Error|Traceback" || true
done
