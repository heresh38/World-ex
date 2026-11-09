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

# Players: the hero base meshes (tools/blender/hero: rigged, the player clips, face_* morphs), built once into
# SourceArt/Characters/src (delete the GLB to rebuild), then the body (one skin__<region> section per region) and
# its first-person arms cut; the Orion outfit, hair (strand cards), brows and lashes come with it.
mkdir -p "$OUT/Characters/src"
for sex in male female; do
  Sex="$(echo "${sex:0:1}" | tr a-z A-Z)${sex:1}"
  glb="$OUT/Characters/src/hero_$sex.glb"
  [ -f "$glb" ] || "$BLENDER" --background --python "$ROOT/tools/blender/hero/build.py" -- "$sex" "--glb=$glb" 2>&1 | grep -E "^\[hero\]|Error|Traceback" || true
  run "$glb" "$OUT/Characters/Player$Sex" --per-item
  run "$glb" "$OUT/Characters/Player${Sex}Arms" --per-item --arms-only
done
# Inventory icons (guns and armour pieces) rendered from the same models
"$BLENDER" --background --python "$ROOT/tools/blender/icons.py" -- "$OUT/Icons" 2>&1 | grep -E "^\[icons\]|Error|Traceback" || true
# Nexus Prime, the city hub (nexus.py kit: one FBX per piece)
run "$M/nexus.glb" "$OUT/Nexus"
# Nexus Prime, the big city (nexus_city.py: the building / street kit, and the plan baked into 1 km tiles + the land)
[ -f "$OUT/NexusCity/src/nexus_city_tiles.glb" ] || "$BLENDER" --background --python "$ROOT/tools/blender/nexus_city.py" -- --tiles >/dev/null 2>&1
run "$M/nexus_city_kit.glb" "$OUT/NexusCity/Kit"
run "$OUT/NexusCity/src/nexus_city_tiles.glb" "$OUT/NexusCity/Tiles"
# ...its trees and shrubs (city_trees.py)
[ -f "$M/city_trees.glb" ] || "$BLENDER" --background --python "$ROOT/tools/blender/city_trees.py" >/dev/null 2>&1
run "$M/city_trees.glb" "$OUT/NexusCity/Trees"
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
# Loot: the loot core and ammo pickups, and the VANTHOS reliquary (its lid is a child part)
run "$M/loot_props.glb" "$OUT/Props/Loot"
run "$M/vanthos.glb" "$OUT/Props/Reliquary" "--only=VX_reliquary_mesh,reliquary_lid_mesh"
# Effect cards (tracers, sparks, smoke, muzzle flash) from tools/blender/fx_kit.py
[ -f "$M/fx_kit.glb" ] || "$BLENDER" --background --python "$ROOT/tools/blender/fx_kit.py" >/dev/null 2>&1
run "$M/fx_kit.glb" "$OUT/FX"
# Sound effects (tools/audio/sfx_synth.py; needs numpy + scipy)
python "$ROOT/tools/audio/sfx_synth.py" "$OUT/Audio" | tail -1
echo "SourceArt written to $OUT"
