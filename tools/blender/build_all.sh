#!/bin/bash
# Rebuilds every texture and model with headless Blender. Usage: bash tools/blender/build_all.sh
set -e
cd "$(dirname "$0")/../.."
for s in textures refs characters players civilians weapons viewmodel vehicles ship_interior city props rural; do
  echo "== $s"
  blender --background --python tools/blender/$s.py 2>&1 | grep -E "^\[export|^\[ref|Error|Traceback|colliders" || true
done
