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
- Reload parts (`weapons.py finish(moving=, loose=)`: own objects with their origin at the pivot, children of the gun root;
  node names are an API): `mag` (all kinetic mag guns; pivot at the mag top, the rifle's at its front lip for rock-in),
  `bolt` (carrier/bolt face/op rod; bolt-action: on the bore axis, rotates + slides), `charge` (carbine T-handle, compact SMG
  cocking handle), `slide` (pistol), `pump` (forend), `crane` > `cylinder` > `rounds` (revolver), `hatch` + `biomass`
  (horror: flank flap about Z for spitter/bile, top lid plate about X for brood; material `bio_load`, tinted per gun in
  `styleMesh`). Loose props `x_shell`, `x_round`, `x_casing`, `x_speedloader` are hidden (`Weapons.dress`) and cloned.
- Reload system (`src/game/reload.js`, owned by `Weapons.rl`): keyframed segments (gun pose, off hand resolved against
  moving parts, part offsets, events) sampled each frame; `GunRig` poses the viewmodel gun and the avatar gun the same way
  (third person: `Avatar.reachL` two-bone IK). Mag guns: tactical = `S.reload`, empty adds the chambering segment (rifle
  overhand rack, carbine T-handle, DMR op rod, SMG slap, pistol slingshot); per-gun out/in styles (rock, drop-free, hook,
  firm push + tap). Revolver: crane out, eject brass, speedloader, flick shut. Pump/bolt: per shell / per round segments
  (ammo +1 each, firing interrupts via `rl.interrupt()`), pump racks if empty. Horror: hatch pops, husk slops out, new
  biomass, glow pulse. Ammo arrives on the `seat`/`grant` events. `Drops` = pooled physical drops (max 14, ~22 s).
  Cancelled by weapon swap, sprint, vehicle, death (`Weapons.cancelReload`). Post-shot: pump/bolt cycle, slide/carrier
  blowback, pistol slide locks back on empty. Sounds: `audio.reloadSfx(kind)`, `audio.dropSfx`. Test: `tools/test/reload.js`.
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
  camera distance (`LOD_NEAR`: ~250 m + 0.75 m per metre of height for buildings, skywalks 170, track 130, platform 210,
  times the quality draw factor, x0.85 on touch); across the last 30 % the two tiers cross-fade with the shared
  screen-door dither (`src/core/lodfade.js`, LOD tiers use faded copies of the dt materials); furniture is
  chunk-instanced. Test: `tools/test/downtown.js` (`PERF_ONLY=1` for draw-call numbers).
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
  street), water, exposure, bloom. The PMREM probe is rebuilt only when the sun moved ~5 degrees or night changed (at most every 12 s; ~2 per real minute).
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
`POOLS` = planting sets per area; `addLive/removeLive` for streamed worlds). LOD (`LOD` in flora.js, scaled by the
quality draw factor, x0.9 on touch, and by tree height): hero -> mid at ~78 m, mid -> impostor at ~290 m, bushes fade
out by ~330 m, rocks (one tier) by ~430 m. Tiers never swap in one frame: each hand-over cross-fades over the last 30 %
with a screen-door dither computed per frame in the vertex shader from the per-instance `aFade` (s, e, born) attribute
(`src/core/lodfade.js`: complementary dither so the pair never shows holes or double cover; the CPU re-buckets every
4 m). Streamed instances (`addLive(..., appear)`, planet chunks, planet scatter `Pool`s and terrain chunks) dither in
over 1.6 s and out on removal. Never give a material that uses `fadeShader` to a mesh without `aFade` (an unbound
attribute reads a stale generic value): use `fadeMaterial()` copies. `flora.forceTier` draws one tier everywhere (tests).
`World.warmTextures()` (end of each world build) uploads every scene texture behind the loading screen and sets
anisotropic filtering (`assets.aniso`: 8, 4 on touch). Pop-in test: `tools/test/popin.js` (A/B frames across every
LOD change while walking toward trees, a rock, towers and a streamed jungle; images in `test-out/popin/`). Earth plants by area (parks cherry ring +
oak/maple, quays willow/ash, suburbs maple/birch + hedges, villages, lone field trees, woods by altitude up to the
`SNOW_LINE` of the Meridian Peaks massif in `layout.js`); trunks collide via `kitColliders`. `planet.js` streams
snowy conifers (glacier), jungle canopy and savanna trees (mesa) per chunk. Test: `tools/test/trees.js`.

## Player, UI and sky
- Movement (`player.js`, constants exported as `MOVE`; tuned for a fast modern military shooter): walk 4.8 m/s, sprint
  7.0 (forward only; firing or aiming stops it), tactical sprint 8.6 on a double-tap of Shift (touch: double-tap the
  sprint button; 3.2 s, then a 4.5 s cooldown; the gun is carried high and away), ADS move 2.78 (58 % of walk, blended by
  the ADS progress), crouch 2.7. Ground acceleration is a fixed-rate approach to the wanted velocity: 55 m/s² to start
  (walk speed in ~0.09 s), 70 m/s² to stop or reverse, 24 m/s² to build from walk to sprint; air control 6 m/s² with no
  drag (momentum kept). Jump 6.1 m/s at gravity 19 (~1.0 m), coyote 0.12 s, buffer 0.15 s, landing dip (camera + gun).
  Slide (C while sprinting > 6 m/s): +2.4 m/s (cap 11), up to 0.9 s, friction 1.35/s (~5 m), jump cancels it keeping the
  momentum, 1.0 s cooldown so slides cannot chain. Per weapon class (`data.js weaponHandling(arch)`: [ADS-in s,
  sprint-to-fire s]): pistols .13/.14, SMGs .17-.18/.15-.16, rifles .22-.24/.19-.2, shotguns .22/.2, DMR .3/.23,
  heavy/sniper .38-.42/.25-.26; tactical sprint adds .08 to the sprint-out. `Player.readyT` counts the sprint-to-fire
  delay (weapons.js holds the trigger and buffers a click), `Player.adsK` the ADS progress (FOV zoom, eased; viewmodel
  blend; bob x0.08 and sway x0.2 when fully aimed), `runK`/`tacK` drive the viewmodel's sprint poses. C = crouch (touch:
  crouch button), automatic mantling onto ledges 0.5–2.45 m (`findLedge`), sitting (`Player.sit`, `World.addSeat`;
  layouts may export `seats`).
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

## VANTHOS (dead city)
A ruined circular city, years after its people (`src/worlds/vanthos/`). `world.js` builds it: overcast hazy dusk (linear fog
16-520 m; the Spire's materials see a thinner fog so it looms from anywhere; its core beats slow and red), drifting ash
(Points VFX), `ground.js` (textured streets as merged ribbons with worn lane paint, kerb gutters, drifts and grass; raised
block slabs with a broken sidewalk band and an overgrown lot; terrain splat), `ruins.js` (instanced ruin designs with
hero/far tiers cross-faded by `core/lodfade.js`; colliders, rubble `mound`s folded into `map.height`, `spots` inside /
perch / tree / glow), trees from `trees.glb` via `meridian/flora.js` (`GROW` pools), weeds, rare sputtering dead lamps, and
`ambience.js` (soundscape kinds `ruinwind`, `creak`, `drip`, `skitter`, `groan`, `distant`, `dread` in `core/soundscape.js`;
music kind `dread`). `styleKit` darkens the old `vanthos.glb` kit (no lit windows, no neon; facade/ribbon get the ruin
textures). Kit: `tools/blender/ruins.py` -> `vanthos_ruins.glb` (`VR_*`: towers a-c, mid a-c, low a-b, hall, stub, mounds,
debris, slabs, burnt/rusted cars, bus, signs, toppled lamp, barricade, remains, weeds; `_lod` for standing ruins; vertex
colour grime/moss/soot; extras `vr`), textures `tools/blender/vanthos_textures.py` (`vr_*`: asphalt, pavers, dirt, grass,
moss, conc, brick, frame, slab, rubble, rust, burnt, signs, ivy/weeds cut-outs). Districts (`districts.js`) fill lots with
standing ruins / rubble / foundations / wild scrub and place **residents** (`ctx.resident(types, x, z, n, beh)`; behaviours
`sleep` (lies in its Death pose and gets up when you are close or loud), `feed`, `perch`, `patrol`, `roam` (packs share a
route), `wander`). Sites stream in at 230 m (queued, 3 spawns per frame) and out at 340 m; `EnemyManager` freezes idle
creatures past ~250 m and thinks/moves them 4x less often past ~95 m; `world.onGunshot` -> `enemies.noise()`. No living
humans: the raiders are gone (hosts wear them; the military zone keeps only its automated turrets). Test: `tools/test/ruins.js`
(`PERF_ONLY=1` for the fixed-viewpoint numbers; screenshots in `test-out/ruins/`).

## Operation (VANTHOS)
`src/worlds/vanthos/operation.js` (`Operation`, owned by `VanthosWorld.op`) plays VANTHOS as a linear, replayable mission,
"Operation Heartline": landing zone → relay mast (Outskirts, hold the uplink vs raiders) → Flight Nine shuttle (Commercial,
stalker ambush, pull the recorder) → Brood Road (Crown ring, three Writhe waves + amalgam, open the gas main) → Spire lift
(crater, hold vs mixed factions, then ride; the lift is unpowered until then) → the Spire Warden on the foundation. Each stage
has a resident **garrison** (`G()` in `build()`, sites with `o.op/keep`, streamed with the city and forced in by `arrive()`,
which records `S.arrival`); scripted reinforcement `wave()`s after the interaction are smaller (enemies flagged `e.op`).
Ambient residents stay along the route; only those inside an arena get `st.off`. Radio lines are HUD subtitles (`hud.radio(who, text)`, queued),
terminal logs use `hud.lore()`. Boss: `Enemy.hpFloor/onFloor` (50 % and 20 %), `immune` (hits return `{immune}` → HUD
"IMMUNE"), `stunT`/`vuln` stagger; shield conduits are `Conduit` combat targets (not enemies; floating bars via
`world.barTargets()`), boss bar `hud.bossBar()`. Reliquary loot = `rollWeapon()` (state.js: any archetype, weighted rarity,
perks, stat rolls, random compatible sight); every copy has its own uid, `isNew` (NEW tag until picked), `keep` (Lock button).
`VAULT_CAP` 200: only plain old spares are dismantled, with a feed message. Save: `save.vanthos.runs/best/logs`; each visit
restarts the run, a metro trip resumes the stage (`g.opResume`), deaths revive at the stage checkpoint. Props `VX_conduit`,
`VX_relay`, `VX_terminal`, `VX_reliquary` (`vanthos.py`; materials `conduit_glow`, `relay_glow`, `terminal_screen`,
`reliquary_glow`). Test: `tools/test/operation.js` (screenshots in `test-out/operation/`).

## Shellbreak (team mode)
The Wayfarer's combat simulation: two squads of ghost-shells, first to the score limit (25/50/75 eliminations) or ahead
when the clock (5/10/15 min) runs out; 3v3 / 4v4 / 6v6 (player + 5 allies vs 6, never more than 11 bots on touch);
opposition Recruit / Regular / Veteran. Entry: Briefing table > Simulation tab (settings + service record), destination
`arena` (hidden in `DESTINATIONS`, kind `sim`: no orbit change, not a charted world); pause > Leave simulation and the
results screen return to the ship. Files: `src/worlds/arena/world.js` (`ArenaWorld`: map, dusk sky/fog/grade, chimney
smoke, loadout flyover, main.js hooks `parity` (no armour resist, full mobility), `onPlayerDeath`, `holdPause`, `hideTouch`,
`scoreKey` (Tab hold / I toggle), `hideDamageNumbers`, `blips()` for the minimap), `match.js` (`Match`: combatants, spawns
scored away from enemy sight lines + 2 s protection (broken by firing), respawn 3.5 s bots / 4.5 s player, eliminations
+100 (+25 precision), assists (>= 40 damage) +50, streaks, feed, end + rewards: XP, credits and `rollWeapon` -> `addWeapon`,
record in `save.arena` via `state.js arenaRecord` incl. `cfg`), `nav.js` (`NavGraph`: CSR A*, nearest, cover map),
`src/game/bots.js` (`Bot`, `BotManager`), `src/ui/arena.js` (score bar + clock, feed, eliminated / assist confirm, ally name
tags, death card (L = change loadout), scoreboard, loadout and end screens). Every shell is 100 health + 50 shield, all
hits x1.4 (`MODE_DMG`), the player's damage is normalised to power 25 (parity). Friendly fire is off (ally bots use combat
side `player`, which the player's rounds skip; bot rounds only test the other squad).
Bots: player bodies (`player_<sex>.glb`, the other sex is fetched by the world) in tactical kit, team colour on
`armor_primary__*` and the tinted cloth slots, hidden pieces removed, face morphs stripped (geometry shared per source),
standard hair material. Roles (rifleman, cqb, marksman, support, sidearm) pick guns from `ROLES` and a preferred range
(`PREF`). Brain (10 Hz near / in a fight, 5.5 Hz < 60 m, 3.3 Hz beyond): perception cone + LOS raycasts, shared squad intel
(sightings, which also ping the minimap), gunfire heard within 60-85 m, awareness of hits from behind; goals = lane push
(`lanes`), intel, flanks via other lanes / alleys, marksman perches, wingmen near the player; fight = strafe, close or open
range, cover points facing the threat (crouch-peek behind waist cover), reload in cover. Aim: reaction 220-380 ms
(Regular), an error that decays with `aimTau`, tracking lag from the target's angular speed, lead + drop compensation,
per-shot jitter growing with distance, burst control on automatics. Shooting uses the gun's real stats (dmg, rpm, burst,
pellets, spread, falloff, crit, vel/grav, goo splash + acid). Movement: A* + string pulling, moveCapsule, mantle / drop
edges (climb lerp), separation, a stuck watchdog (hop, repath, new goal, nudge onto the graph; counted in `stats.stuck`).
Animation only in view (every frame < 55 m, 20 Hz further, 2 Hz out of view), procedural crouch bends.
Map: `tools/blender/arena.py` -> `assets/models/arena_brennick.glb` (ARENA merged per material, ARENA_glass, ARENA_far)
+ `.json` (colliders, nav graph: 1 m cells on every level with walk/drop/mantle edges incl. 2-cell ledges, cover, lanes,
perches, spawns per squad (A at -z), light anchors, chimney `smoke`, sun/sky); textures `tools/blender/arena_textures.py`
(`ar_*`, numpy painted). Brennick Works is mirrored across z = 0: west rail cut (box car to climb into, flatcar, hopper,
1.2 m platform under a 60 m canopy sightline, walk-through shed on the alley), mid casting hall (furnaces, two mezzanines +
bridge, four stairs, crate stacks to mantle up, windows over both lanes), east yard + two-storey gatehouse (outside stair,
balcony), 2.4 m containers (roofs mantle-able), a walk-through container on the alley. The script audits spawn-to-spawn
sight lines (must be 0) and keeps only the nav part reachable both ways from a spawn. The district outside (no collisions)
is procedural Blender geometry: sawtooth and gabled halls, office blocks with lit window grids and rooftop kit, banded
chimneys with warning lamps, silos, a blast furnace with stoves, lattice gantry cranes, a conveyor, pylons with cables,
a water tower and the city's towers on the horizon. Test: `tools/test/arena.js` (movement numbers on the ship, then a full
simulated match; `SKIP_MOVE`, `SKIP_MATCH`, `MATCH_MIN`, `DIFF`, `TOUCH`; screenshots in `test-out/arena/`).

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

## Unreal port
`unreal/ShatteredOrbit` (UE 5.8, C++ modules ShatteredOrbit/SOCore/SOCharacter/SOCombat/SOAI/SOWorld/SOUI) is the
staged port described in `docs/unreal/MIGRATION_PLAN.md`; build, content scripts, tests and gaps are in its README.
Blender GLB -> FBX: `tools/blender/export_fbx.py` (`export_unreal.sh` for the project's set; effect cards from
`fx_kit.py`). Sounds for it: `tools/audio/sfx_synth.py` (numpy + scipy, our own synthesis). Do not change `src/` for it.

## Testing
`node tools/test/e2e.js` (Playwright, global install: `NODE_PATH=$(npm root -g)`), screenshots in `test-out/`.
Software rendering is slow (~5–20 fps); the test drives the game through `window.__game`.
