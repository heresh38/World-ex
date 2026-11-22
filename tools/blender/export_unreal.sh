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

# Players, built once into SourceArt/Characters/src (delete the GLB to rebuild), then the body (one skin__<region>
# section per region) and its first-person arms cut. The male is the new body (Project Orion, tools/blender/hero/orion:
# lab.py builds it with the game's head and the face's sliders, game.py gives it its UVs, its skin maps, its eyes, its
# rig and its clips); the female is still the first hero base mesh (tools/blender/hero/build.py, with its outfit).
mkdir -p "$OUT/Characters/src"
for sex in male female; do
  Sex="$(echo "${sex:0:1}" | tr a-z A-Z)${sex:1}"
  if [ "$sex" = male ]; then
    glb="$OUT/Characters/src/orion_male.glb"
    if [ ! -f "$glb" ]; then
      work="$OUT/Characters/src/orion_male"
      mkdir -p "$work"
      "$BLENDER" --background --python "$ROOT/tools/blender/hero/orion/lab.py" -- "$work/lab.png" --levels=2 --detail         --gamehead --facekeys "--save=$work/lab.blend" 2>&1 | grep -E "^\[orion\] (built|ears|head laid)|Error|Traceback" || true
      "$BLENDER" --background "$work/lab.blend" --python "$ROOT/tools/blender/hero/orion/game.py" -- "$work"         "--glb=$glb" 2>&1 | grep -E "^\[game\]|Error|Traceback" || true
    fi
  else
    glb="$OUT/Characters/src/hero_$sex.glb"
    [ -f "$glb" ] || "$BLENDER" --background --python "$ROOT/tools/blender/hero/build.py" -- "$sex" "--glb=$glb" 2>&1 | grep -E "^\[hero\]|Error|Traceback" || true
  fi
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
# The Sarketh, every rank (the owner's design, tools/blender/skr/game.py: built once into SourceArt/Characters/src,
# delete a GLB to rebuild it): the male (Levy, Veteran), the female (Runner, Speaker), the heavy (Warden, Bearer, the
# commander). The old Altered husks (altered.py) were deleted on 2026-11-22 at the owner's word.
for rank in "male Sarketh skr_male" "female SarkethFemale skr_female" "male SarkethHeavy skr_male_heavy --rank=heavy"; do
  set -- $rank
  glb="$OUT/Characters/src/$3.glb"
  [ -f "$glb" ] || "$BLENDER" --background --python "$ROOT/tools/blender/skr/game.py" -- "$1" "$2" ${4:-} 2>&1 | grep -E "^\[skr_game\]|Error|Traceback" || true
  run "$glb" "$OUT/Characters/$2" --single
done
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
# Meridian, the first operation (meridian.py: the zones, their detail, the backdrop, blockers, conduit and barrier)
[ -f "$M/meridian.glb" ] || "$BLENDER" --background --python "$ROOT/tools/blender/meridian.py" >/dev/null 2>&1
run "$M/meridian.glb" "$OUT/Meridian"
run "$M/vanthos.glb" "$OUT/Props/Reliquary" "--only=VX_reliquary_mesh,reliquary_lid_mesh"
# Effect cards (tracers, sparks, smoke, muzzle flash) from tools/blender/fx_kit.py
[ -f "$M/fx_kit.glb" ] || "$BLENDER" --background --python "$ROOT/tools/blender/fx_kit.py" >/dev/null 2>&1
run "$M/fx_kit.glb" "$OUT/FX"
# Sound effects (tools/audio/sfx_synth.py; needs numpy + scipy)
python "$ROOT/tools/audio/sfx_synth.py" "$OUT/Audio" | tail -1
echo "SourceArt written to $OUT"
