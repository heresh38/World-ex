#!/bin/bash
# Rebuilds every texture and model with headless Blender. Usage: bash tools/blender/build_all.sh
set -e
cd "$(dirname "$0")/../.."
for s in textures refs characters players civilians weapon_textures weapons viewmodel vehicle_textures vehicles ship_textures ship_interior city props rural; do
  echo "== $s"
  blender --background --python tools/blender/$s.py 2>&1 | grep -E "^\[export|^\[ref|Error|Traceback|colliders" || true
done
# organic creatures: horror texture sets (hx_*), the Writhe infestation and the VANTHOS aliens (fleshkit.py SDF sculpting)
for s in horror_textures writhe aliens; do
  echo "== $s"
  blender --background --python tools/blender/$s.py 2>&1 | grep -E "^\[export|^\[texture|Error|Traceback" || true
done
