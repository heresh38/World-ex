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
run "$M/player_male.glb" "$OUT/Characters/PlayerMale" --single --finger-rig=male \
  "--only=B_head,B_eyes,B_brows,B_lashes,C_hair__sidepart,C_top__undersuit,C_vest__vanguard,C_hands__gloves,C_legs__armoured,C_feet__combat"
# First-person arms: the same body and outfit, cut to what the arm bones carry (same skeleton, so the same IK)
run "$M/player_male.glb" "$OUT/Characters/PlayerMaleArms" --single --finger-rig=male --arms-only   "--only=C_top__undersuit,C_vest__vanguard,C_hands__gloves"
# Enemy: the VANTHOS stalker (fleshkit, 5 clips)
run "$M/alien_stalker.glb" "$OUT/Characters/Stalker" --single
# Weapons: every archetype's gun (data.js ARCHETYPES model) with its reload parts, and the optics for the rail
for f in "$M"/gun_*.glb; do
  stem="$(basename "$f" .glb)"
  case "$stem" in gun_attach|gun_void_rifle) continue ;; esac
  dir="$(echo "$stem" | sed -E 's/^gun_//; s/(^|_)([a-z])/\U\2/g')"          # gun_bio_spitter -> BioSpitter
  run "$f" "$OUT/Weapons/$dir" --split-parts
done
run "$M/gun_attach.glb" "$OUT/Weapons/Attach" --split-parts
run "$M/viewmodel_arms.glb" "$OUT/Weapons/Arms"
# Loot: the loot core and ammo pickups, and the VANTHOS reliquary (its lid is a child part)
run "$M/props_world.glb" "$OUT/Props/Loot" "--only=PR_core_mesh,PR_ammo_mesh"
run "$M/vanthos.glb" "$OUT/Props/Reliquary" "--only=VX_reliquary_mesh,reliquary_lid_mesh"
# Effect cards (tracers, sparks, smoke, muzzle flash) from tools/blender/fx_kit.py
[ -f "$M/fx_kit.glb" ] || "$BLENDER" --background --python "$ROOT/tools/blender/fx_kit.py" >/dev/null 2>&1
run "$M/fx_kit.glb" "$OUT/FX"
# Sound effects (tools/audio/sfx_synth.py; needs numpy + scipy)
python "$ROOT/tools/audio/sfx_synth.py" "$OUT/Audio" | tail -1
echo "SourceArt written to $OUT"
