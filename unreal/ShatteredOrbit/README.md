# Shattered Orbit (Unreal Engine 5.8)

Stage 2 (foundation) of `docs/unreal/MIGRATION_PLAN.md`: project, modules, player movement and camera, input,
graphics settings, a generated test range and automation tests. The browser build in the repository root stays the
playable prototype until this project overtakes it.

## Requirements (once)

- Unreal Engine **5.8** from the Epic Games Launcher (`C:\Program Files\Epic Games\UE_5.8`).
- Visual Studio 2022 (Community or Build Tools) with the C++ toolset **MSVC 14.44.35211 or newer** and a Windows 10/11
  SDK (10.0.22621 or newer). UE 5.8 refuses MSVC 14.44.35210 and older. For command-line builds the Build Tools are
  enough: `winget install Microsoft.VisualStudio.2022.BuildTools` with the `VCTools` workload.
- Git LFS (`git lfs install`): `.uasset`, `.umap`, `.fbx` and `.wav` are stored in LFS (root `.gitattributes`).

Paths below assume the repository at `C:\Dev\World-ex` and the engine at `C:\Program Files\Epic Games\UE_5.8`.

## Build

From a terminal (Git Bash or PowerShell):

```bash
"/c/Program Files/Epic Games/UE_5.8/Engine/Build/BatchFiles/Build.bat" ShatteredOrbitEditor Win64 Development -Project="C:/Dev/World-ex/unreal/ShatteredOrbit/ShatteredOrbit.uproject" -WaitMutex
```

Visual Studio / Rider project files (optional):

```bash
"/c/Program Files/Epic Games/UE_5.8/Engine/Build/BatchFiles/Build.bat" -projectfiles -project="C:/Dev/World-ex/unreal/ShatteredOrbit/ShatteredOrbit.uproject" -game -engine
```

Or right-click `ShatteredOrbit.uproject` > Generate Visual Studio project files, open `ShatteredOrbit.sln` and build
`ShatteredOrbitEditor` / Development Editor / Win64. The `Server` target needs a source build of the engine.

## Generate the content (editor Python scripts)

The input assets and the test map are created by scripts in `Content/Python` (the generated `.uasset`/`.umap` files are
committed through LFS, so this is only needed after changing a script). Headless:

```bash
"/c/Program Files/Epic Games/UE_5.8/Engine/Binaries/Win64/UnrealEditor-Cmd.exe" "C:/Dev/World-ex/unreal/ShatteredOrbit/ShatteredOrbit.uproject" -run=pythonscript -script="C:/Dev/World-ex/unreal/ShatteredOrbit/Content/Python/setup_input.py" -unattended -nullrhi -nosplash
```

```bash
"/c/Program Files/Epic Games/UE_5.8/Engine/Binaries/Win64/UnrealEditor-Cmd.exe" "C:/Dev/World-ex/unreal/ShatteredOrbit/ShatteredOrbit.uproject" -run=pythonscript -script="C:/Dev/World-ex/unreal/ShatteredOrbit/Content/Python/make_test_map.py" -unattended -nullrhi -nosplash
```

In the editor: Tools > Execute Python Script.

- `setup_input.py` → `/Game/Input/IA_*` (Move, Look, LookGamepad, Jump, Sprint, Crouch, ToggleView, Interact, Fire,
  Aim, Reload) and `IMC_Default` (keyboard/mouse + gamepad).
- `make_test_map.py` → `/Game/Maps/L_TestRange` (floor with a 1 m checker, walls, mantle ledges at 60/120/200/240 cm
  plus a 300 cm wall, ramps at 15/30/50 degrees, crates, sky atmosphere, clouds, sun, sky light, height fog, post
  process, player start) and the grey-box material `/Game/Materials/Dev/M_Greybox`; sets it as the default map.
  The grey-box blocks are the engine unit cube with our own procedural material: test geometry only.

## Automation tests

```bash
"/c/Program Files/Epic Games/UE_5.8/Engine/Binaries/Win64/UnrealEditor-Cmd.exe" "C:/Dev/World-ex/unreal/ShatteredOrbit/ShatteredOrbit.uproject" -ExecCmds="Automation RunTests ShatteredOrbit; Quit" -unattended -nullrhi -nosplash -nosound -log -ReportExportPath="C:/Dev/World-ex/unreal/ShatteredOrbit/Saved/Automation"
```

Or in the editor: Tools > Session Frontend > Automation, filter `ShatteredOrbit`. Tests
(`Source/ShatteredOrbit/Private/Tests/SOAutomationTests.cpp`):

| Test | Checks |
|---|---|
| `Movement.Defaults` | tuning values, eye height 165 cm, camera boom collision |
| `Movement.Speeds` | simulated in a transient world: walk 440, sprint 860 (forward only), slide (boost, decay, end), crouch 270, jump apex ~98 cm |
| `Movement.CoyoteTime` | jump 0.05 s after leaving a ledge works, 0.3 s does not |
| `Movement.Mantle` | ledges 60/120/200/240 cm are mantled, a 300 cm wall is not |
| `Camera.ViewToggle` | first person default, T toggles the third-person camera, body visibility |
| `Look.Math` | zoom-matched scale, response curve, smoothing time constant |
| `Settings.ApplyGraphics` | Lumen / VSM / AA / screen percentage / motion blur console variables |
| `World.TimeOfDay` | sun east at 06:00, south at noon, west at 20:00, night |
| `Content.InputAssets` | the input actions and `IMC_Default` exist |
| `Content.TestRangeLoads` | the map loads with its lights, geometry and the SOGameMode override |

## What to try in the editor

Open `ShatteredOrbit.uproject` (L_TestRange opens), press Play.

- **Move / look:** WASD + mouse, or left / right stick. Space / A jumps.
- **Sprint:** hold Shift (or tap it to latch until you stop pushing forward); L3 on the gamepad.
- **Crouch / slide:** C or Ctrl (B on the gamepad); tap toggles, hold crouches while held. Crouch while sprinting
  slides (~5 m, jump out of it to keep the speed).
- **Mantle:** walk or jump at a ledge while holding jump: the orange blocks (60-240 cm) are climbable, the grey
  300 cm wall is not.
- **Coyote time / jump buffer:** jump just after running off a ledge, or press jump just before landing.
- **Camera:** T (D-pad up) toggles third person; RMB / LT zooms (aim) with zoom-matched sensitivity.
- **Fire / Reload / Interact** (LMB / R / E) only log to the Output Log for now (category `LogShatteredOrbit`).
- **Graphics settings:** console `r.DynamicGlobalIlluminationMethod`, or in a Blueprint / Python get
  `SOGameUserSettings`, change e.g. `bLumen`, `AntiAliasing`, `ScreenPercentage` and call `ApplyGraphics`.
- **Multiplayer check:** Play > Number of Players 2, Net Mode "Play As Listen Server": sprint, slide and mantle on the
  client should not rubber-band.

## Layout

| Module | Contents |
|---|---|
| `ShatteredOrbit` (primary) | `ASOGameMode`, `ASOPlayerController` (adds `IMC_Default`), `ASOPlayerState`, `USOGameInstance`, tests |
| `SOCore` | `LogShatteredOrbit`, `USOGameUserSettings` (look + graphics settings, `ApplyGraphics()`) |
| `SOCharacter` | `ASOCharacter`, `USOCharacterMovementComponent` (sprint, coyote, slide, mantle, saved moves), `USOLookComponent` |
| `SOCombat` | stub (`ESOWeaponClass`); GAS arrives in stage 3 |
| `SOWorld` | `USOTimeOfDaySubsystem` skeleton (rotates a directional light tagged `Sun`) |
| `SOUI` | stub (`USOActivatableWidget`, CommonUI) |

Assets come from Blender: `tools/blender/export_fbx.py -- in.glb out_dir` turns our GLBs into Unreal-ready FBX
(units, Z up, no leaf bones, UCX_ collision, LOD groups).
