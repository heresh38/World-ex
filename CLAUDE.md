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
- Weapons (`weapons.py` + `gunkit.py`, textures `weapon_textures.py`): every archetype in `ARCHETYPES` (`data.js`) has a class
  `cls`: `energy` (the original sci-fi line incl. the Orion Arms guns), `kinetic` (rifle, carbine, dmr, ksmg, bolt, pistol,
  revolver, pump — real projectiles with muzzle velocity and bullet drop) and `horror` (living biomass: spitter, bile, brood).
  Sights (`gun_attach.glb`: reflex, holo, 2x/4x/8x) mount per weapon (`w.sight`, changed at the Gunsmith); magnified optics
  use the object name `scope` + `gun_lens`. Kinetic/horror guns use their own material names (`gun_steel`, `gun_wood`,
  `bio_flesh`, ...) so rarity/shader tints only touch `gun_glow`/`gun_body`.
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
skin, eyes, hairColor, brow, face presets, sliders, wear per slot and tints per slot. The underwear slots (`undertop`,
`underbottom`) are `locked` (never removable) and use `coveredBy` to hide under clothing, so the body is never shown naked. Material names are an API for runtime
tints: `skin`, `eye_iris`, `hair`, `brow`, `cloth_<slot>`, `armor_primary__<slot>`, `glow`. Run with `-- female|male --fast`
for quick checks; `sdfview.py` previews a field without Blender. `refs.py` cuts fabric swatches from `art/reference`
(owner's art, allowed). `civilians.py` builds the pedestrians with `npc_kit.py` (tinted by prefix skin/hair/shirt/pants/shoes).
`characters.py` still makes the enemies. The player rig uses the IK pole angle of 90 degrees, which keeps the elbows down
and the upper-arm twist small for skinned shoulders.

## Earth (free roam)
The city follows the owner's river-city art (`art/reference/city_river.jpg`). A river (`RIVER_Z`, `riverZ()` in
`layout.js`, carved below sea level) runs through block row -3 with a bridge (`BLD_bridge`) on every north-south street
and causeway bridges where highways cross it. Downtown has towers; the middle ring has green-roof kit (`BLD_8`–`BLD_13`
in `city.py`); the outer ring has suburbs (rural houses). There are parks with `BLD_fountain`, a central `BLD_rotunda`
plaza, and glowing cyan kerb strips.
`src/worlds/meridian/`: `layout.js` (heightmap, river, highways, lanes, villages/farms, districts), `population.js` (pedestrians),
`traffic.js` (lane cars, hijack), `wanted.js` (stars + security drones). Assets: `rural.py` (RU_* kit). No missions on Earth.
- Spaceport (`spaceport.py`, `SPACEPORT` in `layout.js`): a ship landing field south of the city (VTOL pads, terminal with the
  Quartermaster, control tower, hangars, fuel farm, container yard; no runways — ships land vertically). The player's ship lands
  on pad 1; `src/game/cinematic.js` plays the landing / take-off cutscenes (`g.cineTime` pins the clock for tests).
- Water (`src/game/water.js`, textures from `water_textures.py`): river, bay and Vanthos flood water. API `g.water`:
  `heightAt`, `depthAt`, `splash(pos, kind|size)`, `hitTest(from, to, kind)`; ripples, splashes, wading and swimming.
  `src/game/puffs.js` is the shared dust/spray sprite system.

## Player, UI and sky
- Movement (`player.js`): walk 4.4, sprint 8.6, coyote time + jump buffer, C = crouch (slide when sprinting), automatic
  mantling onto ledges 0.5–2.45 m (`findLedge`), sitting (`Player.sit`, `World.addSeat`; layouts may export `seats`).
- Inventory (I / Tab): `Menus.st_inventory` (weapons, armour, missions, overview) + `src/ui/inspect.js` (turning gun or an
  orbit shot of the player drawn by `Renderer.preview` into `.inv-stage`). Equipping only works aboard the ship.
- Armour: `armorStats` in `data.js` (worn pieces → armour rating, damage resisted, mobility), used by `Game.armor`.
- Minimap on every world (`hud.js updateMinimap`): worlds may provide `minimap`; otherwise frontier planets get a
  hill-shaded patch and interiors a wall plan from the colliders. Interactables, hostiles and `markers()` are drawn.
- Small street furniture gets colliders through `kitColliders` in `earth.js`.
- Orbit: `sky.js` `spaceSky` (sparse stars, faint galaxy band) and `orbitPlanet`; Earth uses maps baked by
  `tools/blender/planets.py` (`earth_day/clouds/night/ms.jpg`, registered in `planetMaps` at boot).

## Creatures
Organic enemies are sculpted with `fleshkit.py` (tagged SDF primitives → Surface Nets → skinned GLB: soft-min skin
weights per primitive bone, vertex colours with cavity darkening/bruising/veins, `_writhe` vertex attribute for tentacle
wriggle, baked FK clips Idle/Walk/Run/Attack/Death). `horror_textures.py` bakes the shared `hx_*` sets (flesh, skin,
chitin, bone, sac, rag); the GLBs ship without images and `enemies.js` (`fleshify`) applies the maps by material name
(`writhe_*`, `alien_*`) and adds the wriggle shader + glow pulse. `aliens.py` = VANTHOS species (stalker, hulk, mutant,
swimmer, elite); `writhe.py` = the Writhe, a parasite faction hostile to everyone: `mite` (swarms, leaps, bursts, burrows
into fresh human corpses which rise as hosts), `host` (lurching reanimated trooper, lunges, may fire a scavenged gun),
`bladder` (waddles in, swells and ruptures into mites), `amalgam` (fused brute, slam + bile). Placed in VANTHOS districts
(`nest()` in `districts.js`, hospital boss), metro `FAUNA`, and overrun outposts on frontier planets.
`FLESH_PREVIEW=<dir>` writes texture-embedded copies for `preview.py`. Test: `tools/test/horror.js` (WORLD=vanthos_metro default).

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
