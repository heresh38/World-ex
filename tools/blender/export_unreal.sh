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

# Players: the body (each skin region its own section) and every armour piece as its own skeletal mesh on one
# skeleton, with finger bones; then the first-person cut of the same (only what the arm bones carry). Pieces: the
# Orion set (the owner's concept pair, the default), the vanguard / circuit-coat sets and a few casual pieces.
BODY="B_head,B_eyes,B_brows,B_lashes,B_neck,B_chest,B_midriff,B_pelvis,B_upperarm,B_forearm,B_hand,B_thigh,B_shin,B_foot"
ORION="C_top__orion,C_outer__orion,C_hands__orion,C_hands__orion_armoured,C_legs__orion,C_feet__orion"
MALE="$BODY,$ORION,C_hair__swept,C_hair__textured,C_hair__sidepart,C_underbottom__base,C_top__undersuit,C_vest__vanguard,C_hands__gloves,C_legs__armoured,C_feet__combat,C_head__pioneer,C_outer__jacket,C_outer__hoodie,C_legs__cargo"
FEMALE="$BODY,$ORION,C_hair__ponytail,C_hair__bob,C_undertop__base,C_underbottom__base,C_top__ribbed,C_vest__harness,C_outer__circuit_coat,C_hands__gauntlets,C_legs__leggings,C_feet__tech,C_outer__jacket,C_legs__cargo"
for sex in male female; do
  Sex="$(echo "$sex" | sed -E 's/^(.)/\U\1/')"
  only="$MALE"; [ "$sex" = female ] && only="$FEMALE"
  run "$M/player_$sex.glb" "$OUT/Characters/Player$Sex" --per-item --finger-rig=$sex "--only=$only"
  run "$M/player_$sex.glb" "$OUT/Characters/Player${Sex}Arms" --per-item --finger-rig=$sex --arms-only "--only=$only"
done
# Inventory icons (guns and armour pieces) rendered from the same models
"$BLENDER" --background --python "$ROOT/tools/blender/icons.py" -- "$OUT/Icons" 2>&1 | grep -E "^\[icons\]|Error|Traceback" || true
# Nexus Prime, the city hub (nexus.py kit: one FBX per piece)
run "$M/nexus.glb" "$OUT/Nexus"
# Nexus Prime, the big city (nexus_city.py: the building / street kit, and the plan baked into 1 km tiles + the land)
[ -f "$OUT/NexusCity/src/nexus_city_tiles.glb" ] || "$BLENDER" --background --python "$ROOT/tools/blender/nexus_city.py" -- --tiles >/dev/null 2>&1
run "$M/nexus_city_kit.glb" "$OUT/NexusCity/Kit"
run "$OUT/NexusCity/src/nexus_city_tiles.glb" "$OUT/NexusCity/Tiles"
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
