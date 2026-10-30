# WORLD EX — notes for Claude Code

Browser looter shooter on Three.js r186 (vendored in `lib/three`, no build step: native ES modules + import map in `index.html`).
Serve the repo root with any static server (`python3 -m http.server 8765`).

## Hard rules from the owner
- **Every 3D model and texture is made in Blender by our own scripts** (`tools/blender/*.py`, run with
  `blender --background --python <script>`). Never add third-party models/textures, and do not build visible
  meshes from three.js primitives (VFX like tracers/particles/light shafts are fine).
- No names, terms or text from other games.
- Premium presentation; keep 60 fps on a mid-range laptop (quality presets + dynamic resolution in `src/core/renderer.js`).

## Asset pipeline
- `bash tools/blender/build_all.sh` rebuilds everything into `assets/`. In this container Blender is the `bpy` pip
  module behind a `/usr/local/bin/blender` shim; a normal Blender install works the same way.
- `bl.py` helpers (materials, primitives, loft, export). Blender is Z-up, -Y forward → glTF/three is Y-up, +Z forward.
- Material **names are an API**: the game recolours by name (`armor_primary`, `armor_secondary`, `glow`, `visor`,
  `gun_body`, `gun_glow`, `car_paint`, `hover_glow`, `facade`, `ribbon`, `rock`, `core_glow`, `ammo_glow`, glass names).
- Bone names lose dots in three (`hand.R` → `handR`). Characters share one rig and 9 clips
  (Idle, Walk, Run, Jump, IdleRelaxed, WalkRelaxed, RunRelaxed, Sit, Death); arm poses are IK-solved then baked.
- `ship_interior.py` also writes `ship_interior.json`: AABB colliders, station points and light anchors (already in three space).
- Check models with `tools/blender/preview.py -- out.png model.glb:Action:frame:view ...` (Cycles contact sheet).

## Characters
Players are built by `players.py` (base body, regions `B_*`, eyes, brows, lashes, face morphs from `face.py`) and
`wardrobe.py` (hair and clothing as `C_<slot>__<item>`). The anatomy is signed-distance fields in `anatomy.py`,
meshed by `sdf.py` (Surface Nets + narrow band). Meta (wardrobe items with the regions they hide, defaults, morph groups)
lives in the armature's `worldex` extra. `Avatar.applyCharacter(save.character)` applies the look, using character v3:
skin, eyes, hairColor, brow, face presets, sliders, wear per slot and tints per slot. Material names are an API for runtime
tints: `skin`, `eye_iris`, `hair`, `brow`, `cloth_<slot>`, `armor_primary__<slot>`, `glow`. Run with `-- female|male --fast`
for quick checks; `sdfview.py` previews a field without Blender. `refs.py` cuts fabric swatches from `art/reference`
(owner's art, allowed). `civilians.py` builds the pedestrians with `npc_kit.py` (tinted by prefix skin/hair/shirt/pants/shoes).
`characters.py` still makes the enemies. The player rig uses the IK pole angle of 90 degrees, which keeps the elbows down
and the upper-arm twist small for skinned shoulders.

## Earth (free roam)
`src/worlds/meridian/`: `layout.js` (heightmap, highways, lanes, villages/farms, districts), `population.js` (pedestrians),
`traffic.js` (lane cars, hijack), `wanted.js` (stars + security drones). Assets: `rural.py` (RU_* kit). No missions on Earth.

## Camera
First person is the primary view (`settings.view = 'first'`), third person is a toggle (T) that may be removed later.
In first person the body moves to layer 1 (shadows only) and `src/game/viewmodel.js` draws the Blender arms + gun in a
second render pass with depth cleared. Touch controls live in `src/ui/touch.js` and feed the same `Input` state.

## Code map
- `src/main.js` Game: boot → title (live 3D) → loading (byte-level progress) → worlds; stations, progression, saving, loop.
- `src/core/` renderer (bloom/FXAA/governor), input (pointer lock), audio (all procedural WebAudio), assets, physics
  (AABB spatial hash + terrain height fn; capsule move with step-up; raycast used by bullets and the camera).
- `src/game/` player (controller + collision-aware 3rd-person camera), avatar (skinned wrapper, gun socket solved from the
  armed idle pose), weapons, combat (targets/bolts/pickups), enemies, vehicles, fx, data, state (save + loot rolls).
- `src/worlds/` `ship.js` hub (stations replace the old menu), `earth.js` city, `planet.js` endless chunk streaming, `sky.js`.
- `src/ui/` hud, menus (title/loading/pause/station panels), style.css.
- `legacy/` is the previous single-file engine (reference only).

## Testing
`node tools/test/e2e.js` (Playwright, global install: `NODE_PATH=$(npm root -g)`), screenshots in `test-out/`.
Software rendering is slow (~5–20 fps); the test drives the game through `window.__game`.
