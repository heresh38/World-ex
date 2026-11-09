# WORLD EX — notes for Claude Code

The game is the Unreal project `unreal/ShatteredOrbit` (UE 5.8, C++). The old browser build (Three.js) was deleted on
2026-11-08 at the owner's request: never use, rebuild or reference anything from it. Every asset comes from our own
Blender scripts in `tools/blender` (the asset pipeline) and every number from the Unreal project's own data.

## Hard rules from the owner
- **Every 3D model and texture is made in Blender by our own scripts** (`tools/blender/*.py`, run with
  `blender --background --python <script>`). Never add third-party models/textures; Epic's sample characters may only be
  measured side by side (tools/reference), never imported, fitted or copied.
- No names, terms or text from other games.
- AAA quality everywhere: nothing blocky or half-done, no lumps / ledges / bulges on any model (check silhouettes).
- Premium presentation at 60 fps on a mid-range PC.

## Asset pipeline
- `bash tools/blender/build_all.sh` builds the Blender sources Unreal's export reads into `assets/` (generated, not
  committed): textures (`textures.py`, `weapon_textures.py`, `wear_textures.py`, `horror_textures.py`,
  `nexus_textures.py`, `nexus_city_textures.py`, `ruins_textures.py`), the guns and optics (`weapons.py` + `gunkit.py`),
  the stalker (`aliens.py`, `fleshkit.py`), the Altered (`altered.py`), Nexus Prime (`nexus.py`, `nexus_city.py` kit),
  the city trees (`city_trees.py`), loot props (`loot_props.py`), the reliquary (`vanthos.py`), Meridian (`meridian.py`)
  and effect cards (`fx_kit.py`). Then `bash tools/blender/export_unreal.sh` builds the players and turns everything into
  `unreal/ShatteredOrbit/SourceArt` (FBX + textures + json), and `Content/Python/import_assets.py` imports it.
- `bl.py` helpers (materials, primitives, loft, export). Blender is Z-up, -Y forward; glTF is Y-up, +Z forward.
- Weapons (`weapons.py` + `gunkit.py`, textures `weapon_textures.py`): every archetype in `Data/game_data.json` has a
  class: `energy`, `kinetic` (real projectiles with muzzle velocity and drop) and `horror` (living biomass). Sights
  (`gun_attach.glb`: reflex, holo, 2x/4x/8x) mount per copy; magnified optics use the object name `scope` + `gun_lens`.
  Reload parts are own objects with their origin at the pivot (node names are an API): `mag`, `bolt`, `charge`,
  `slide`, `pump`, `crane` > `cylinder` > `rounds`, `hatch` + `biomass`; loose props `x_shell`, `x_round`,
  `x_casing`, `x_speedloader`. Gun wear: the `_wear` attribute (convex edges) goes into the vertex colour alpha.
- Material **names are an API** (`gun_body`, `gun_glow`, `orion_*`, `skin__<region>`, `hair*`, `nx_*`, `nc_*`, ...).
- Weapon / loot numbers: `unreal/ShatteredOrbit/Data/game_data.json` is their source (edit it, re-import).
- Check models with `tools/blender/preview.py -- out.png model.glb:Action:frame:view ...` (Cycles contact sheet).
- Creatures: `fleshkit.py` (tagged SDF primitives -> Surface Nets -> skinned GLB, baked FK clips) with the `hx_*` sets
  from `horror_textures.py`; the stalker is the only one in the game so far (`/Game/Characters/Stalker`).

## Characters
The old player bodies, heads, clothing, hair, first-person arms and the scripts that built them (players.py, anatomy.py,
face.py, wardrobe.py, hair.py, skin.py, the old civilians / NPC kits) were deleted on 2026-11-07: the players are
being rebuilt from zero as two separate professional base meshes (male, female): clean quad topology with edge
loops at the eyes, mouth, nose, ears and every joint, real anatomy and proportions (Epic's Manny / MetaHuman may be
measured side by side, never imported), and face customisation (eyes, ears, mouth shape and colour, eye colour and
shape, noses, hair and hair colour). Clothing and armour come back later, fitted to the new bodies. Until the new
bodies are imported, tests that need the player body skip with a warning (SOTest::PlayerBodyMissing).
`characters.py` still makes the enemies.

New base meshes: `tools/blender/hero/` (`blender -b -P tools/blender/hero/build.py -- male|female [--save=x.blend]
[--sheet=x.png] [--cage] [--nofine] [--nokeys]`). `targets.py` (anthropometric targets), `skeleton.py` (joints,
finger / toe chains), `cage.py` + `head.py` (all-quad cage; only the left half is authored, `build.mirror_topology`
rebuilds the right as its exact mirror), `shape.py` + `headshape.py` (the anatomical target as a signed distance
field, the head from adult norms), `headfit.py` (lays the head cage on the face's landmarks: eye / mouth loops,
nose cap, neck opening), `fit.py` (Catmull-Clark x2, projection, tangential relaxation, the face customisation
shape keys `face_*` from `headshape.FACE_KEYS`). Output: ~38.6k quads, symmetric, open only at eyes and mouth,
plus two eyeball meshes. `--rig` / `--glb=x.glb` rig it (`rig.py`: our joints on the shared player skeleton incl.
fingers and clavicles (`clavicle.X` between the chest and the upper arm: the game's arm IK turns it forward / up as
the arm reaches, so the shoulder keeps its volume), heat weights, the body's own clips, `B_body` one `skin__<region>` slot per region,
`B_eyes`, `B_brows` = eyebrows + lashes as strand cards), then dress it unless `--naked` (`wardrobe.py`: the Orion
outfit per slot `C_<slot>__<item>` from the concept sheet, skinned by data transfer, metadata in the armature's
`worldex`). Every piece is cut and sewn, not a pushed-out body shell: `coat.py` (his long field coat / her cropped
white jacket: shell from the body eased + draped, then cut clean (waist, cuffs, neckline, open front), a skirt carried
down the hips' envelope with drape folds and a back vent, a stand collar, pressed seams with double stitching, thickness
with the blue lining inside) + `coat_details.py` (`Surface.on/toward/frame` lays parts on the cloth; `panel` (rounded
patch with lift, thickness, stitched border), `zip_line`, `tube`, studs, rings; zip halves, collar tab, folded hood,
pockets, patches, cuff straps, half belt), `shirt.py` (his knit combat shirt with ripstop raglan sleeves and a quarter zip
/ her sleeveless high-neck crop top), `trousers.py` (cargo / plated; tucked into the boots: tight inside the shaft and
bloused above it; seams, waistband, belt loops, knee plates, cargo pockets), `boots.py` (combat boots on their own last:
foot loft + a straight tapered shaft (widest section, straight heel-to-calf back: no bulb or ledge), Surface Nets
mesh, throat with a padded tongue, eyelets / speed hooks / laces, toe cap and heel counter overlays, an outsole traced
from the upper's footprint (flush, lug tread, midsole band)), `gloves.py` (fingerless / armoured: clean finger cuts,
suede palm, one knuckle guard, wrist strap, the wrist-tech housing), `belt.py` (belt with buckle and keepers; his
pouches, her drop-leg holster), `garment.py` (cuts, strips, straps, hardware). `fabric.py` writes our cloth textures
(twill, ripstop, knit, coated canvas, polymer, leather, rubber, braid, zip tape, stitch thread; colour / OpenGL normal
/ metal-rough, per sex in `SourceArt/Characters/src/tex/<sex>`) and `world_uvs` gives every shell world-scale UVs. Hidden regions cover
everything a piece covers (no skin through clothes in any pose). Rules: no lumps / ledges / bulbs on any surface
(check silhouettes front, back, sides, 3/4); surface rays only search near the part (a long ray finds the far side). `hair.py`: hair as strand cards
(own numpy atlas `hero_hair_strands.png`: clumps of separate strands with ragged roots and pointed tips; a cap with a
soft, strand-broken edge from `hero_hair_scalp.png`; hairline wisps on a density gradient), male short swept, female
high ponytail with volume and a side-swept fringe; Unreal material `M_SOHair` for `hair`, `hair__cap`, `hair__brow`,
`hair__lash` (lashes have their own thick-strand texture and root at the lid's visible edge). Eyes: big rounded lid
openings (`eye_hu/eye_hl` in `headshape.head_geometry`), `fit.eye_sockets` closes the opening behind the lids (skin
walls round the eyeball; the lid margins are kept in the body's `eye_margins`), eyeballs `eye_white`/`eye_iris`/
`eye_pupil`; the body's vertex colour `Col` tints the lips and shades the lid crease and rims (Unreal multiplies it).
Head armour (`headgear.py`, the optional `head` slot, nothing worn by default): the Orion Vanguard Helmet, a full
sealed helmet over the head, face and neck (hides the hair and the head / neck skin: bald under it, the hair back when
it comes off): a base surface from signed distances on this body's measured head (cranium ellipsoid fit, face volume,
ribbed neck seal), plates cut from a relaxed smooth copy of it (`cut_plate`: base faces inside the plate's region, the
open edge slid onto the region's outline along the surface, lifted along the field normal, solidified without even
offset or clamp, chamfered), the visor (a dark mirrored lens in a raised frame, centre seam, light line, temple
sensors), turned ear discs with light rings, faceplate vent slats; his steel-grey and square with a heavy crest and a
faceplate ridge, hers white, a V visor, a pointed chin plate. Plus the Orion Comms Headset (oval cups, band clear of
the hair, boom mic; the hair stays). Finish (`finish.py`, every piece but hair): the corner colour `Col` = paint scheme
x per-plate tone x grime / dust / ground dirt in RGB (the plate materials are a light neutral, the paint lives here:
his gunmetal + desert tan + signal-orange marking, hers off-white + lining blue), edge wear in A (a rubbed band
diffused in from convex edges, chips only near edges, more on upper / front faces); Unreal `ARMOUR_WEAR` sets each
material's EdgeWear / Scratches / Grime / WearMetal / WearTiling with the shared wear mask.
Motion: each body has its own clip set in its own folder, nothing shared: `hero/male/motion.py` (masculine: wide
track, heel strike, shoulder drive, loose fists, a squared idle; idle variations neck stretch / scan / shoulder roll) and
`hero/female/motion.py` (feminine: crossover line, hip roll and sway, quick light steps, arms close, contrapposto
idle; variations weight shift / look back / neck stretch). Clips: Idle, Walk (the game's 4.4 m/s jog), Run (8.6 m/s
sprint), Jump, Slide, Death, Fidget1-3. `hero/gait.py` is the engine only (no style): feet planned so a planted foot
moves back at exactly the clip's speed (rolling heel -> ball about real pivots: no sliding at Clips.WalkSpeed /
RunSpeed), leg IK + foot orientation baked to FK, the hips lowered (smoothed over the clip) wherever a leg would
over-reach, arm bends about the elbow hinge (`Body.elbow`), finger curls (`Pose.curl`). Unreal: walk and run share one
cycle phase (both start on the left foot); a Fidget layer plays an idle variation after 7-15 s standing still and not
aiming (`USOLocomotionAnimInstance::FidgetDelay`). Test: `ShatteredOrbit.Anim.OwnClipsPerBody`.
Male and female heads differ on purpose (his heavy brow ridge, square wide jaw, big chin, broad nose; her narrow face
tapering to a small chin, high round cheekbones, small nose, full lips, bigger eyes). Face keys `face_*` are created
at 0 (Blender 5 adds new keys at 1.0). Heat weights are solved on a cleaned copy of the body (`rig.heat_weights`).
The two bodies share no generated file: textures `SourceArt/Characters/src/tex/<sex>/hero_<sex>_*.png`, GLBs `SourceArt/Characters/src/hero_<sex>.glb`,
Unreal folders `/Game/Characters/Player<Sex>` (own skeleton, clips, materials, textures, wardrobe).
`export_unreal.sh` builds `SourceArt/Characters/src/hero_<sex>.glb` (delete it, and `SourceArt/Characters/src/tex/<sex>`, to rebuild) and
exports `--per-item` + `--arms-only`.

## Unreal project
`unreal/ShatteredOrbit` (UE 5.8, C++ modules ShatteredOrbit/SOCore/SOCharacter/SOCombat/SOAI/SOWorld/SOUI); plan in
`docs/unreal/MIGRATION_PLAN.md`; build, content scripts, tests and gaps in its README.
Blender GLB -> FBX: `tools/blender/export_fbx.py` (`--per-item` writes the player body (one `skin__<region>` section per
region) and every wardrobe piece as its own skeletal FBX; `--arms-only` cuts the first-person arms). The player is
modular (`USOWardrobeData` per body, one follower skeletal mesh per slot, armour owned / worn through the inventory),
both views hold the gun with arm IK onto the rig's grips and the fingers close by grip preset (`USOGunRigComponent`,
`FSOFingerPose`, `USOLocomotionAnimInstance`). Maps: every level has an `ASOMapInfo` + `ASOMapPoint`s (mini-map, map
screen, quick travel). Nexus Prime (the big city, `L_Nexus`): plan `tools/city/nexus_plan.py` -> `Data/nexus_plan.json`,
kit + baked tiles `tools/blender/nexus_city.py`, built at runtime by `ASONexusCity`. Inventory icons:
`tools/blender/icons.py`. Sounds: `tools/audio/sfx_synth.py` (numpy + scipy, our own synthesis).
Operations (`SOOperation` module): `ASOOperation` runs a level as stages (travel / clear / hold / boss) with waves,
spawn groups, checkpoints (the game mode respawns there) and boss adds keyed to the boss's health, read from a plan json;
`ASOOperationBarrier` energy walls keep the route linear until their stage; finishing grants every player ONE random
piece of the reward sets (`AddArmorPiece` for armour: wardrobe items with a `Set` are earned, never handed out).
HUD: objective panel, stage banner, goal marker, boss bar, end screen. Tests `ShatteredOrbit.Operation.*`.
The first operation, Meridian Fall (`/Game/Maps/L_Meridian`; travel from Nexus Prime): the owner's layout sheet
`art/reference/operation/first_operation_map.png` made smaller and linear, our own names. One source for layout and
mission: `tools/operation/meridian_plan.py` (writes `Data/op_meridian.json`); `tools/blender/meridian.py` builds the ruined
city from it with `ruinkit.py` (ruined towers: slab cells, columns, cores, cladding, a damage field of broken tops and
blast holes, rebar, hanging slabs, rubble heaps; wall + gate, viaducts, the Concord Ring, the High Terraces, the
Crown Bridge, the Crown with its beam, the far spire and broken orbital ring, invisible blockers) into `MR_<zone>`
chunks + `Data/op_meridian_art.json` (lights); `make_operation_map.py` assembles the level (storm night).
Enemies, the Altered (`altered.py` + `SOAltered.h`), all armed with our guns (`ASOEnemy::WeaponArchetype`, held two-handed
by the same arm IK as the player, one-handed by the Bulwark; rounds scaled by `WeaponDamageScale`, aim error shrinking as
they track): Remnant (SMG, pushes in), armed Stalker (auto rifle, cover), Veilborn (scout rifle from cover, the odd void
bolt, blinks), Bulwark (frontal shield, shotgun, ground slam), the Hollow Colossus (boss, ~2.6 m: heavy machine gun,
slam, sweep, barrage; shields at 2/3 and 1/3 until its three conduits die, then staggers). Every creature uses the
player's capsule (34 x 90; Bulwark 44 x 108, Colossus 50 x 128) and step rules.
Brain (`ASOEnemyAIController`): sight cone + peripheral band, awareness that fills over time (crouching slows it,
sprinting and a lit flashlight speed it; a light is seen from any side), hearing (gunshots, running feet), states
unaware / suspicious / combat / search; squad alerts; armed cover-users score nav points that hide them from the
target but have a peek or a line over the top (flankers swing wide, claims kept apart), peek-shoot-duck, move on
when flanked; stuck detection steps them back onto free nav. Shots on an unaware creature hit harder (ambush). Voices
per creature from `sfx_synth.py` (`<set>_idle/query/alert/hurt/death_N`). Operation waves: the first of a stage is an
unaware garrison (`hunt: false`), later ones hunt. Spawns land on the nav mesh where the capsule fits; L_Meridian's nav
mesh is bounded to the walkable route per zone (one big volume ran out of tiles in the towers).
The base is alive: grown chitin barricades round every post (`ruinkit.alien_barricade`, real cover), hive growths with
egg pods (`hive_growth`, `pod`, texture `ru_hive`), the Choir's spires (`alien_spire`), cables of light; the violet glow
breathes (`M_SOGlowPulse`); `ASOAmbience` loops (`amb_alien_hum`, `amb_hive`, `amb_alien_chorus`) and drifting spores.
Player: flashlight (F / right stick; `ASOCharacter::SetFlashlight`), clamber (ledges 2.45-3.8 m: a hang and pull up,
`ClamberMaxHeight`), footsteps the creatures hear. Loot lands on the ground (traced on the world only) and drops in.
Tests `ShatteredOrbit.Altered.*`, `ShatteredOrbit.AI.*`; pictures `SOCaptureSeries 1 9` on L_Meridian (logs the nav path).
Reward sets still to model: the owner's concept sheets in `art/reference/operation/` (Void Sentinel armour, Void
Requiem guns, plan ids `void_sentinel` / `vr_*`); until they exist the reward falls back to a legendary gun.

## Testing
Build: `Build.bat ShatteredOrbitEditor Win64 Development -Project=<uproject>`. Tests: `UnrealEditor-Cmd <uproject>
-ExecCmds="Automation RunTests ShatteredOrbit; Quit" -unattended -nullrhi` (results in `Saved/Logs/ShatteredOrbit.log`).
Pictures: `UnrealEditor <uproject> -game -RenderOffscreen -windowed -ResX=1600 -ResY=900 -ExecCmds="SOCaptureSeries 1 <set>"`
(`Saved/Screenshots/SO_*.png`; sets in `ASOPlayerController::SOCaptureSeries`).
