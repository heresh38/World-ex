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
Hair is grown by `hair.py` (scalp cap + alpha-tested strand cards on the `hair_strands.png` atlas; materials `hair` and
`hair__cap`, both tinted by hairColor). Player clips add Slide; Walk, Run, Jump and the Relaxed clips are gendered per GLB
(`characters.animate(style=)`), enemies keep the neutral set. `players.py` also writes `player_<sex>_npc.glb` (crowd version:
one body mesh, everyday wardrobe `NPC_KEEP`/`NPC_HAIR`, smaller atlas `hair_strands_s.png`) used by `population.js` with
`randomCharacter`. Wardrobe meta per item: `hide` (regions), `coveredBy` (locked underwear), `replaces` (a dress hides
top/legs), `cover` (bit in the per-vertex `_covermask`; `avatar.js` pulls masked skin 6 mm inwards while that garment is
worn). Garment weights are copied from the body under them, restricted to the parts they cover. Player exports go through
`bl.quantize_glb()` (8-bit normals/weights, 16-bit UVs; three reads it natively).

## Earth (free roam)
The city follows the owner's river-city art (`art/reference/city_river.jpg`). A river (`RIVER_Z`, `riverZ()` in
`layout.js`, carved below sea level) runs through block row -3 with a bridge (`BLD_bridge`) on every north-south street
and causeway bridges where highways cross it. Downtown has towers; the middle ring has green-roof kit (`BLD_8`–`BLD_13`
in `city.py`); the outer ring has suburbs (rural houses). There are parks with `BLD_fountain`, a central `BLD_rotunda`
plaza, and glowing cyan kerb strips.
`src/worlds/meridian/`: `layout.js` (heightmap, river, highways, lanes, villages/farms, districts), `population.js` (pedestrians),
`traffic.js` (lane cars, hijack), `wanted.js` (stars + security drones). Assets: `rural.py` (RU_* kit). No missions on Earth.

- Downtown (`src/worlds/meridian/downtown.js`, kit `tools/blender/downtown.py` + `downtown_textures.py`): blocks bx/bz -2..2
  (`isDowntown`, `HERITAGE`, `TRANSIT` in `layout.js`; Founders' Park, the rotunda plaza and the (2,-2) park stay). Layout
  adopted from a prairie river city's downtown (no real names anywhere): numbered-grid blocks split into many plots
  (`PLAN` rows filled by `fillRow`, hand-planned landmark blocks), a car-free heritage avenue mid-block in row -1 lined
  with sandstone/brick low-rises (towers behind and among them, cafe tables, string lights, banners, trees), a light-rail
  transit mall one block nearer the river (row -2: track bed, catenary, two stations, two shuttling trams with a
  `collision.dynamic` box), 1970s-80s concrete / bronze-glass towers beside new glass towers, a crescent tower over a plaza,
  an observation tower, parkades, two construction sites with slewing tower cranes, plazas and pocket plazas, enclosed
  skywalks at ~5 m between neighbouring buildings (auto-found, never over the transit mall), signals and zebra crossings.
  Heights peak in the middle ring and fall off outward. `downtown.glb` = 21 designs `DT_<name>` + `DT_<name>_lod`
  (extras `dt`: w/d/h, kind, era, `col` AABBs in three space, fronts face +z); `downtown_street.glb` = skywalks, platform,
  track, catenary, tram, crane mast/jib, street furniture. Facade sets `dt_*_c/_n/_m` (m: R = glass of every window
  .55..1, G rough, B metal; runtime reuses R as the night-window mask, see Day/night below); untextured colours are merged per mesh into vertex-coloured
  `dt_plain`, `dt_plain_metal`, `dt_plain_glow` (fewer draw calls; the glow takes the vertex colour). Buildings are instanced per design/material with hero/LOD buckets by
  camera distance; furniture is chunk-instanced. Test: `tools/test/downtown.js` (`PERF_ONLY=1` for draw-call numbers).
- Spaceport (`spaceport.py`, `SPACEPORT` in `layout.js`): a ship landing field south of the city (VTOL pads, terminal with the
  Quartermaster, control tower, hangars, fuel farm, container yard; no runways — ships land vertically). The player's ship lands
  on pad 1; `src/game/cinematic.js` plays the landing / take-off cutscenes (`g.cineTime` pins the clock for tests).
- Water (`src/game/water.js`, textures from `water_textures.py`): river, bay and Vanthos flood water. API `g.water`:
  `heightAt`, `depthAt`, `splash(pos, kind|size)`, `hitTest(from, to, kind)`; ripples, splashes, wading and swimming.
  `src/game/puffs.js` is the shared dust/spray sprite system.
- Day/night (`src/worlds/meridian/daynight.js`, driven by `g.clock`): sun arc (east 06:00, south noon, west 20:00), moon
  at night (the one shadow light switches sun <-> moon while both are dim), palette keyframes (dawn orange, white noon,
  the original golden hour at 18:36, red sunset, purple dusk, blue night) for light, hemi, fog, sky (`atmosphereSky`
  uniforms night/moonDir/cloudC/glowC; gndC/gndK darken the lower half of the reflection probe so glass reflects a dark
  street), water, exposure, bloom. The PMREM probe is rebuilt only when the sun moved ~3.5 degrees or night changed.
  `SKY` = shared uniforms (night, hour, litHome/litOffice/litShop fractions, win gain). Downtown facades: per window cell
  (UV x tile bays/floors, hashed with the instance position and wall facing) a time-slot hash decides lit rooms; desktop
  adds interior mapping (ray into a box room: furniture, rug, ceiling lamp, blinds; < 150 m, off on touch or with
  `window.__ROOMS = false`). The city kit gets `nightWindows()` (3 m world cells). Emissive kit materials are scaled by
  night (`registerGlows`: lamps off by day); every street lamp gets an additive ground pool + halo (2 draw calls).
  Awnings flutter, banners and string lights sway (downtown.js `sway`). `atmos.js`: falling leaves/petals from nearby
  trees (`Flora.near`), rooftop steam, chimney smoke (`world.houses`), fountain spray, moths at lamps. `ambience.js` +
  `src/core/soundscape.js`: positional procedural ambience (fountains, cafes + evening music, construction 7-17, trams
  with bell, highways, river, birds/crickets) on a pool of 6 voices (4 on touch), plus `audio.cityMix` for the city bed.
  Test: `tools/test/daynight.js` (screenshots in `test-out/daynight/`).
- Street life (`population.js`, `npcnav.js`, `fauna.js`): `NavGraph` = sidewalk rings (nodes every ~22 m), corner
  crossings (edge `cross` = road axis/centre; people wait at the kerb for a traffic gap), heritage-avenue and transit-mall
  walkways (platform nodes y 0.35), bridge footways, rings round plazas / park fountains / the rotunda, plus places
  (`pois`): seats (benches via `World.seatSpots`, cafe chairs from `downtown.furn.DT_cafe`, planter rims), kiosk queues,
  shop windows, doors (`work`/`home`/`shop`/`hotel`, downtown fronts + mid-ring and suburb street faces), platform spots,
  meeting points; each hangs off the graph by a straight `clear()` walk (cafe sets count as oriented table boxes). A* per
  goal. The crowd (`COUNT` 150, 60 on touch) lives around the player: size and goal mix follow `g.clock` (`DENSITY`,
  `MIX`: commute to work doors / off trams, lunch queues + cafes, evening heritage avenue, near-empty 0-5 h); people
  despawn through doors or by boarding trams and respawn out of view (doors, out-of-frustum nodes, tram arrivals);
  far ones (> 300 m) are recycled; a teleport reseeds (some already seated / chatting). States: walk, wait, idle, browse,
  queue, platform, meetwait, talk (groups of 2-3, also chance meetings head-on), settle/sit/rise, board, flee/return,
  dead; seated neighbours talk; talk gestures are additive head/arm bends (avatar `touched`). Throttling: think+move
  every frame < 50 m, every 3rd < 120 m, 8th < 220 m, 20th beyond; mixer only in view (rate 1/2/4 by distance); far
  bodies leave the scene graph. Rural loops (villages, farms, spaceport) keep the simple loop walkers.
  Fauna (`fauna.py` -> `fauna.glb`): `BIRD_pigeon`/`BIRD_sparrow` instanced, vertex shader folds/flaps wings (`_wing`)
  and pecks (`_head`) from per-instance `aBird`; flocks peck on plazas/lawns/the avenue, burst up to a rooftop when the
  player runs/drives close or a shot is fired (`Population.alarm` -> `Fauna.scare`), drift back; none at night. `CAT`
  (14-bone rig, clips Idle/Look/Sit/Walk/Run, materials `cat_coat`/`cat_light`/`cat_eye` tinted per cat) sits by alley
  mouths, slinks along the wall, bolts into the alley when approached. Test: `tools/test/life.js` (test-out/life/).

## Trees
`tools/blender/trees.py` grows every tree (`trees.glb`, roots `TR_*`; `-- oak birch --fast` builds only those into
`$TREE_OUT`, `$TREE_PREVIEW=<dir>` writes per-species GLBs for preview.py). Broadleaf crowns by space colonisation, conifers
by whorls/pads; leaf-cluster cards (`leaves_*`, alpha MASK, normals bent out of the crown, AO in COLOR_0), `bark_*`,
`snow` (up-facing branch/rock faces), `rock`. Each variant has `TR_x` (hero 3-6k tris), `TR_x_mid`, `TR_x_lod` (crossed
impostor cards from a Cycles-baked atlas); root extras `h`, `w`, `trunk`, `species`. Also bakes `snow_c/_n.jpg` (terrain).
Runtime: `src/worlds/meridian/flora.js` (`Flora`: instanced LOD buckets by camera distance, wind, mip alpha boost;
`POOLS` = planting sets per area; `addLive/removeLive` for streamed worlds). Earth plants by area (parks cherry ring +
oak/maple, quays willow/ash, suburbs maple/birch + hedges, villages, lone field trees, woods by altitude up to the
`SNOW_LINE` of the Meridian Peaks massif in `layout.js`); trunks collide via `kitColliders`. `planet.js` streams
snowy conifers (glacier), jungle canopy and savanna trees (mesa) per chunk. Test: `tools/test/trees.js`.

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
- Clock: `src/game/clock.js` (`g.clock`: hour, daylight(), between(), set(), paused; day length = `settings.dayMinutes`,
  default 40, Engineering > Graphics). The HUD shows the time under the place name on worlds with `daynight` (Earth).

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

## Operation (VANTHOS)
`src/worlds/vanthos/operation.js` (`Operation`, owned by `VanthosWorld.op`) plays VANTHOS as a linear, replayable mission,
"Operation Heartline": landing zone → relay mast (Outskirts, hold the uplink vs raiders) → Flight Nine shuttle (Commercial,
stalker ambush, pull the recorder) → Brood Road (Crown ring, three Writhe waves + amalgam, open the gas main) → Spire lift
(crater, hold vs mixed factions, then ride; the lift is unpowered until then) → the Spire Warden on the foundation. Stages are
scripted waves (`wave()`, enemies flagged `e.op`), not distance streaming; ambient `sites` near the route/arenas get
`st.off`, and the raider convoy waits until the run is done. Radio lines are HUD subtitles (`hud.radio(who, text)`, queued),
terminal logs use `hud.lore()`. Boss: `Enemy.hpFloor/onFloor` (50 % and 20 %), `immune` (hits return `{immune}` → HUD
"IMMUNE"), `stunT`/`vuln` stagger; shield conduits are `Conduit` combat targets (not enemies; floating bars via
`world.barTargets()`), boss bar `hud.bossBar()`. Reliquary loot = `rollWeapon()` (state.js: any archetype, weighted rarity,
perks, stat rolls, random compatible sight); every copy has its own uid, `isNew` (NEW tag until picked), `keep` (Lock button).
`VAULT_CAP` 200: only plain old spares are dismantled, with a feed message. Save: `save.vanthos.runs/best/logs`; each visit
restarts the run, a metro trip resumes the stage (`g.opResume`), deaths revive at the stage checkpoint. Props `VX_conduit`,
`VX_relay`, `VX_terminal`, `VX_reliquary` (`vanthos.py`; materials `conduit_glow`, `relay_glow`, `terminal_screen`,
`reliquary_glow`). Test: `tools/test/operation.js` (screenshots in `test-out/operation/`).

## Vehicles
`vehicle_textures.py` bakes `veh_*` maps (seat fabric/quilt, leather, dash, carpet, headliner, grille, speaker, disc, grip;
layout renders with text for tyre sidewall/tread, gauges, screen, number-plate atlas, lamps, badges, bullet-hole and
glass-crack decals). `vehicles.py` → `vehicles_modern.py` builds `cars.glb` with `CAR_hatch|sedan|suv|pickup|van|rover`
(each `hi_<k>` full interior + `lo_<k>` 7-material LOD, animated `steer_`, `needleS_/needleR_`, `wheel_<FL..>`/`spin_`,
`seat_`/`eye_` empties, `worldex` extra with dimensions) and `board_sport|board_utility.glb`; its legacy path still makes
the skyway hover cars and calls `jumpship.py`. Runtime `src/game/vehicles.js`: `Car` = four-ray spring/damper suspension
(gravity, landing, rolling over, buoyancy via `g.water`), OBB collisions with world boxes, other cars, the player
(push/knock/stand on roof), enemies and pedestrians (`pedContact`, run-over above ~6 m/s); cars are combat targets
(decals, smoke, fire, wreck). `Board` = hover board summoned with V (hovers over ground/water, carve, Space jump,
Shift boost); on frontier worlds V again drops the rover. `save.car.model` is `board_sport|board_utility` (state.js
migrates old `car_*`). `meridian/traffic.js` = fixed population (~120 lane cars with `civ_*` drivers in the Sit pose),
throttled far away, turns at crossings; shot drivers slump and the car rolls to a stop. Test: `tools/test/vehicles.js`
(`WORLD=ares` skips the Earth-only checks).

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
