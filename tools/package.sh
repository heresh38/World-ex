#!/bin/bash
# Packages the game for Windows into unreal/ShatteredOrbit/Saved/StagedBuilds/Windows.
#   bash tools/package.sh [Development|Shipping]
# Then run it:  unreal/ShatteredOrbit/Saved/StagedBuilds/Windows/ShatteredOrbit.exe
# Takes a long time the first time (every shader is compiled for the packaged game). Do not run it while an editor,
# a build or the tests are running.
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
UE="${UE_ROOT:-/c/Program Files/Epic Games/UE_5.8}/Engine"
PRJ_DIR="$ROOT/unreal/ShatteredOrbit"
CONFIG="${1:-Development}"

# The data files the game reads at runtime (SOData.h): a packaged game has no project folder, so they go in with
# the content. Everything else in Data/ is read by the editor scripts only.
STAGED="$PRJ_DIR/Content/Staged/Data"
rm -rf "$PRJ_DIR/Content/Staged"
mkdir -p "$STAGED"
cp "$PRJ_DIR/Data/areas.json" "$PRJ_DIR/Data/creator.json" "$PRJ_DIR/Data/journal.json" "$PRJ_DIR/Data/nexus_plan.json" "$PRJ_DIR/Data/nexus_city.json" \
   "$PRJ_DIR/Data/nexus_instances.bin" "$STAGED/"
for f in "$PRJ_DIR"/Data/op_*.json; do
  case "$f" in *_art.json) ;; *) cp "$f" "$STAGED/" ;; esac
done
echo "staged data: $(ls "$STAGED" | tr '\n' ' ')"

PRJ_WIN="$(cygpath -m "$PRJ_DIR/ShatteredOrbit.uproject")"
MSYS_NO_PATHCONV=1 "$UE/Build/BatchFiles/RunUAT.bat" BuildCookRun -project="$PRJ_WIN" -noP4 -platform=Win64 \
  -clientconfig="$CONFIG" -build -cook -stage -pak -iostore -prereqs -utf8output -unattended -nosplash
echo "packaged: $PRJ_DIR/Saved/StagedBuilds/Windows"
