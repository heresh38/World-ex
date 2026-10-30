#!/bin/bash
# Rebuilds every texture and model with headless Blender. Usage: bash tools/blender/build_all.sh
set -e
cd "$(dirname "$0")/../.."
for s in textures characters weapons viewmodel vehicles ship_interior city; do
  echo "== $s"
  blender --background --python tools/blender/$s.py 2>&1 | grep -E "^\[|Error|Traceback|colliders" || true
done
