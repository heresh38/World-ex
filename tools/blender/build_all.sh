#!/usr/bin/env bash
# Builds every Blender source the Unreal export reads into assets/ (generated, not committed):
#   bash tools/blender/build_all.sh          (BLENDER=<path to blender> to override)
# Then tools/blender/export_unreal.sh turns them (and the players, which it builds itself) into SourceArt/.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BLENDER="${BLENDER:-blender}"
if ! command -v "$BLENDER" >/dev/null 2>&1; then
  for c in "/c/Program Files/Blender Foundation/Blender 5.2/blender.exe" "/c/Program Files/Blender Foundation/Blender 4.2/blender.exe"; do
    [ -x "$c" ] && BLENDER="$c" && break
  done
fi
run() {
  local script="$1"; shift
  echo "== $script $*"
  "$BLENDER" --background --python "$ROOT/tools/blender/$script.py" -- "$@" 2>&1 | grep -E "^\[export|^\[texture|Error|Traceback" || true
}
# textures: the shared painted sets, the guns' sets, the wear mask, the creatures' flesh sets, Nexus Prime's sets
for s in textures weapon_textures wear_textures horror_textures nexus_textures nexus_city_textures; do
  run "$s"
done
run weapons                       # every gun (gun_<archetype>.glb, with its reload parts) and the optics (gun_attach.glb)
run aliens stalker                # the stalker (fleshkit SDF sculpt, skinned, 5 clips)
run nexus                         # Nexus Prime's hub kit
run nexus_city --kit              # the big city's building / street kit (the tiles are baked by export_unreal.sh)
run city_trees                    # the city's trees and shrubs
run loot_props                    # loot core and ammo case (loot_props.glb)
run vanthos                       # the reliquary (the reward chest; replaced when the operation's own kit is built)
run fx_kit                        # effect cards (tracers, sparks, smoke, muzzle flash)
echo "assets/ built"
