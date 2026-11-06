#!/usr/bin/env bash
# Exports the GLBs the Unreal project uses into unreal/ShatteredOrbit/SourceArt (FBX + textures + json; not committed,
# regenerate with this script), then Content/Python/import_assets.py imports them into /Game.
#   bash tools/blender/export_unreal.sh            (BLENDER=<path to blender> to override)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BLENDER="${BLENDER:-blender}"
if ! command -v "$BLENDER" >/dev/null 2>&1; then
  for c in "/c/Program Files/Blender Foundation/Blender 5.2/blender.exe" "/c/Program Files/Blender Foundation/Blender 4.2/blender.exe"; do
    [ -x "$c" ] && BLENDER="$c" && break
  done
fi
OUT="$ROOT/unreal/ShatteredOrbit/SourceArt"
M="$ROOT/assets/models"
run() { "$BLENDER" --background --python "$ROOT/tools/blender/export_fbx.py" -- "$@" 2>&1 | grep -E "^\[export_fbx\]|Error|Traceback" || true; }

# Player: male body with the default tactical loadout (players.py defaults; hidden body regions dropped)
run "$M/player_male.glb" "$OUT/Characters/PlayerMale" --single \
  "--only=B_head,B_eyes,B_brows,B_lashes,C_hair__sidepart,C_top__undersuit,C_vest__vanguard,C_hands__gloves,C_legs__armoured,C_feet__combat"
# Enemy: the VANTHOS stalker (fleshkit, 5 clips)
run "$M/alien_stalker.glb" "$OUT/Characters/Stalker" --single
# Weapon: the kinetic assault rifle with its reload parts, and the first-person arms
run "$M/gun_rifle.glb" "$OUT/Weapons/Rifle" --split-parts
run "$M/viewmodel_arms.glb" "$OUT/Weapons/Arms"
echo "SourceArt written to $OUT"
