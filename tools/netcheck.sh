#!/bin/bash
# The two-player check: starts the game twice on this machine from the editor's binaries, a host (listen server) on
# the range and a guest that joins it, and prints what each side logged ("NetCheck host: ..." / "NetCheck guest:
# ...": ASOPlayerController::SOCaptureSeries sets 21 and 22). Nothing multiplayer is covered by the automation
# tests (they run one world); this is how it is looked at.
#   bash tools/netcheck.sh
# Do not run it while an editor, a build or the tests are running.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
UE="${UE_ROOT:-/c/Program Files/Epic Games/UE_5.8}/Engine/Binaries/Win64/UnrealEditor.exe"
PRJ="$(cygpath -m "$ROOT/unreal/ShatteredOrbit/ShatteredOrbit.uproject")"
LOGS="$ROOT/unreal/ShatteredOrbit/Saved/Logs"
COMMON="-game -RenderOffscreen -windowed -ResX=960 -ResY=540 -ForceRes -nosplash -nosound -unattended -NOSTEAM"
rm -f "$LOGS/netcheck_host.log" "$LOGS/netcheck_guest.log"

MSYS_NO_PATHCONV=1 "$UE" "$PRJ" "/Game/Maps/L_TestRange?listen" $COMMON -log=netcheck_host.log -SONetCheck=host >/dev/null 2>&1 &
HOST=$!
# the guest joins once the host is in play (its arrival screen has lifted)
for i in $(seq 1 90); do
  grep -a -q "Area: arrival done" "$LOGS/netcheck_host.log" 2>/dev/null && break
  sleep 1
done
MSYS_NO_PATHCONV=1 timeout 240 "$UE" "$PRJ" 127.0.0.1 $COMMON -log=netcheck_guest.log -SONetCheck=join >/dev/null 2>&1
echo "guest exit $?"
# the host quits by itself when its part is over; do not leave it behind
for i in $(seq 1 60); do kill -0 $HOST 2>/dev/null || break; sleep 1; done
kill $HOST 2>/dev/null

echo "== host"
grep -a -E "NetCheck|Join succeeded|Login request|Fatal|Assertion failed" "$LOGS/netcheck_host.log" | sed 's/^\[[^]]*\]\[[ 0-9]*\]//' | cut -c1-330
echo "== guest"
grep -a -E "NetCheck|Welcomed by server|Connection failed|Fatal|Assertion failed|Kit '" "$LOGS/netcheck_guest.log" | sed 's/^\[[^]]*\]\[[ 0-9]*\]//' | cut -c1-330
