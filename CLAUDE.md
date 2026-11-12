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
- **Operations follow `docs/operation/ART_DIRECTION.md`** (the owner's art direction, 2026-11-10: "For our operation
  keep this as the rules please"). Read it before touching an operation level. In short: a once-great human city,
  destroyed, abandoned and taken over by an alien ecosystem; a playable strike, not a showcase. Buildings are COMPLETE
  buildings that were then damaged (finished walls, windows and frames, balconies, trim, rooftop plant, signage,
  doors, broken sections showing furnished interiors): never bare concrete skeletons, construction sites, grey boxes
  or stacked cubes; every district has its own architecture and its own lighting. Every detail has a reason (it tells
  what happened here); no random scatter. The alien vegetation is its own design language and grows the way plants
  grow (through windows and cracks, round pillars, roots into concrete, some buildings consumed, some barely
  touched). Real streets (lane markings, curbs, drains, potholes, wrecked vehicles), no huge flat surfaces, explorable
  interiors with floors, ceilings, furniture and light. Dark and cinematic but never too dark to see enemies. Audit
  first, plan, then work in its ten stages, testing after each; keep the route, encounters, collision and nav working;
  commit before each stage (the backup). Never call it AAA because it uses Nanite and Lumen.

## Asset pipeline
- `bash tools/blender/build_all.sh` builds the Blender sources Unreal's export reads into `assets/` (generated, not
  committed): textures (`textures.py`, `weapon_textures.py`, `wear_textures.py`, `horror_textures.py`,
  `nexus_textures.py`, `nexus_city_textures.py`, `ruins_textures.py`), the guns and optics (`weapons.py` + `gunkit.py`),
  the stalker (`aliens.py`, `fleshkit.py`), the Altered (`altered.py`), Nexus Prime (`nexus.py`, `nexus_city.py` kit),
  the city trees (`city_trees.py`), loot props (`loot_props.py`), the reliquary (`vanthos.py`), Meridian (`meridian.py`)
  and effect cards (`fx_kit.py`). Then `bash tools/blender/export_unreal.sh` builds the players and turns everything into
  `unreal/ShatteredOrbit/SourceArt` (FBX + textures + json), and `Content/Python/import_assets.py` imports it.
- `bl.py` helpers (materials, primitives, loft, export). Blender is Z-up, -Y forward; glTF is Y-up, +Z forward.
- Weapons (`weapons.py` on `gunparts.py` (the hard-surface kit: lofts through chamfered sections, turned parts, vented
  cages, stocks, magazines, muzzle devices, sights; direct meshes on `voidkit.py`, no booleans) + `gunkit.py`, textures
  `weapon_textures.py`; rebuilt 2026-11-12 toward the Requiem guns' standard, sheets `Saved/Screenshots/guns_*`): every
  archetype in `Data/game_data.json` has a
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
high ponytail with volume, the front drawn straight back into the tie (one direction, nothing across it); Unreal material `M_SOHair` for `hair`, `hair__cap`, `hair__brow`,
`hair__lash` (lashes have their own thick-strand texture and root at the lid's visible edge). Eyes: big rounded lid
openings (`eye_hu/eye_hl` in `headshape.head_geometry`), `fit.eye_sockets` closes the opening behind the lids (skin
walls round the eyeball; the lid margins are kept in the body's `eye_margins`), eyeballs `eye_white`/`eye_iris`/
`eye_pupil`; the body's vertex colour `Col` tints the lips and shades the lid crease and rims (Unreal multiplies it).
Head armour (`headgear.py`, the optional `head` slot, nothing worn by default): the Orion Vanguard Helmet, a full
sealed helmet over the head, face and neck (hides the hair and the head / neck skin: bald under it, the hair back when
it comes off): a base surface from signed distances on this body's measured head (cranium ellipsoid fit, face volume,
ribbed neck seal), plates cut from a relaxed smooth copy of it (`cut_plate`: base faces inside the plate's region, the
open edge slid onto the region's outline along the surface, lifted along the field normal, solidified without even
offset or clamp, chamfered). Clean and sleek, made to go with each outfit (no vents, discs or sensors; the shell's
front is set from this face's measured nose and chin, so no face pokes through): his tactical for the black coat (a
visor wrapped round the eyes, a mandible guard in two chamfered steps with a breather, a rail along each temple,
charcoal), hers ONE full, rounded face shield from the brow to the chin (white, for the jacket); both a peak over
the eyes like a hood's edge, swept jaw guards, three nape lames, a slim spine in the lining's blue, one line of
light. Plus the Orion Comms Headset (oval cups, band clear of
the hair, boom mic; the hair stays). Finish (`finish.py`, every piece but hair): the corner colour `Col` = paint scheme
x per-plate tone x grime / dust / ground dirt in RGB (the plate materials are a light neutral, the paint lives here:
his gunmetal + desert tan + signal-orange marking, hers off-white + lining blue; the helmets have their own,
`finish.HELMET`, and take the accent by whole plate: a zone painted across a plate ends ragged), edge wear in A (a rubbed band
diffused in from convex edges, chips only near edges, more on upper / front faces); Unreal `ARMOUR_WEAR` sets each
material's EdgeWear / Scratches / Grime / WearMetal / WearTiling with the shared wear mask.
Motion: each body has its own clip set in its own folder, nothing shared: `hero/male/motion.py` (masculine: wide
track, heel strike, shoulder drive, loose fists, a squared idle; idle variations neck stretch / scan / shoulder roll) and
`hero/female/motion.py` (feminine: crossover line, hip roll and sway, quick light steps, arms close, contrapposto
idle; variations weight shift / look back / neck stretch). Clips: Idle, Stroll (1.5 m/s: the slow walk), Walk (the
game's 4.4 m/s run), Run (8.6 m/s sprint), Jump (three poses: take-off at 0, the tuck at 0.22 s, the reach for the
ground at the end; the game reads it by the rise and the fall), Land, Vault / Mantle / Climb (1 s each, read by how far
through the move the body is), Crouch / CrouchWalk (2.7 m/s; authored down there, feet planted: the game bends
nothing at runtime), Slide, Death, Fidget1-3. Generated motion must never read as a machine (the owner:
"very robotic" on the first set, whose every joint ran on one sine): nothing peaks together (`gait.locomote` runs the
spine, chest, head, forearms and hands a lag behind the pelvis; keyed clips use `gait.Track.at(t, lags)`), no pure
sine (second harmonics, the swing foot recovers high and is drawn back before it lands: `retract`, `peak`), the two
sides are not copies (`asym`), elbows open behind and close in front, and a walk is a walk (double support, the body
highest over the planted leg), not a slowed run. A run is TALL, UPRIGHT and LONG-LEGGED (the owner: "crouched like a penguin" on
the set whose feet landed far ahead of the hips, 18 cm apart, knees out; then "still a bit too much knees bent ... more
upright ... more force"): the foot lands just ahead of the hip (`front` under a quarter: every cm of reach at the strike
pulls the hips down for the whole stance), the knee bends about 20-30 degrees at mid-stance and no more, the hips stay
within 2 cm of standing height (`drop` negative), the trunk is upright (`lean` 5 / 11, `chest_up`), the heel is carried
through the stance at a sprint (`stance`), the arms pump hard. Tune against numbers, not by eye: `reclip.py -- <sex>
--measure=Walk,Run` prints the hips' height, each knee's bend and each ankle per frame without baking. His gait is a
man's (the owner: "male run/walk seems too much like a women" on the narrow-track set): the feet under the hip joints
(`width` 7-8.5 cm, knees straight ahead: wide track + knees out is the waddle), the pelvis level and still (`hip_roll`
about 1, `sway` .002-.01), the shoulders doing the turning (`counter` 1.2+), elbows a little out, heavy half-closed
hands; hers stays on a line with the hips rolling. `ShatteredOrbit.Anim.RunsTall` measures the hips against standing
height and the feet's track in the game. Work on motion without rebuilding a body: `blender -b <saved build>
-P tools/blender/hero/reclip.py -- <sex> --frames=<dir> --clips=Walk,Run` (13 s: re-bakes and renders frames; look
at them), `--glb=SourceArt/Characters/src/hero_<sex>.glb` writes the game's source again, then `export_fbx.py ...
--per-item` and `SO_IMPORT_ONLY=player_clips` imports just the clips. `hero/gait.py` is the engine only (no style):
feet planned so a planted foot
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
The bodies' surface anatomy and skin (both the game's players and the naked base asset use the same body; the first,
smoother bodies were removed on 2026-11-09 at the owner's request). `build.py` gives the game's body its UVs and skin
maps (`basemesh_finish.game_skin`: `hero_<sex>_skin_BaseColor / _Normal / _ORM / _Subsurface`, `hero_<sex>_eye_BaseColor`
beside the other textures; the import makes the skin and eye instances from the GLB's materials, tint white).
Naked base characters (the production asset: `blender -b -P tools/blender/hero/basemesh.py -- male|female`, then
`basemesh_project.py` for both in one file; output `SourceArt/Characters/OrionBase`, generated, not committed).
Faces on the owner's direction: his broad and square (the jaw almost as wide as the cheekbones, the lower third
short), hers very round (`headshape.ROUND_HW`), big eyes, a small nose, full lips. `anatomy.py` =
signed relief on the body's distance field (muscle borders, tendons, knuckles, nails, face folds; `line` takes the
strongest segment per point, never the nearest one's fade: that jumps and cuts a line); `headshape.AFACE` = the face's
sections on soft-tissue profile norms (every column smooth: a zigzag between rows shows as a band); the lids are a
shell round the eyeball the lid margins are pinned on (`g["lid"]`); `ear_anatomy` (coarse for the base mesh, the fine
folds behind `self.fine`); `Body.hand_anatomy` (palm loft, webs, thumb mound). Smooth-min blends inflate where several
primitives nearly coincide (up to k/4): tune against numbers, not by eye. `basemesh_finish.py`: UV seams (back midline
of head and trunk, hidden side of each limb by shortest path, hands back / palm, soles), unwrap and pack, position /
normal / occlusion baked, `skinmaps.py` writes the skin's colour, roughness, normal and subsurface maps and the eye from
them (functions of the 3D position: nothing shows at a seam), collections `<Sex>_Base_Body/_Head/_Eyes/_Hair/_Skeleton`,
`Materials`, `Reference`, `Export` (LOD1-3), FBX per LOD, renders, a manifest json.

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
`art/reference/operation/first_operation_map.png` made linear, our own names, and (owner, 2026-11-10: "at least 4x
longer ... spawn at the very edge of the city and fight through ruined buildings / maybe a mall ... like a strike")
a long way in before it: 2.5 km south to north, 20 stages. Ashfall Verge (the landing pad, the dead highway, the toll
plaza) -> The Stacks (through the gatehouse block's rooms, the walled yard: clear, the archway, the alley) ->
Meridian Galleria (two storeys round an atrium, escalators, the rotunda under the fallen skylight: hold, then the
Warden at the service gate: a boss stage, a `bulwark` variant) -> Deepline (the stair down, the ticket hall, the
platform: destroy three `conduit` hearts, the tunnel with its collapse and the service corridor round it) -> The
Sluice (the drained canal, pump house, footbridges with the watch on them: clear, the spillway) -> the Causeway ->
the old Approach, Gate, Boulevard, Concord Ring (hold), High Terraces, Crown Bridge, the Crown (the Colossus). Named
elites (`VARIANTS`: Remnant Captain, Veilborn Seer, Pack Alpha) give the big fights a centre. One source for layout
and mission: `tools/operation/meridian_plan.py` (writes `Data/op_meridian.json`: stages, groups, barriers, map points,
`nav` boxes, `mapInfo`; `PITS` = holes in the ground, `ROUTE`); `tools/blender/meridian.py` (the old city, the ground,
the skyline) + `meridian_south.py` (the long way in: `wall` with doors / windows, `slab` grids with holes, `sloped`,
`escalator`) build it with `ruinkit.py` (ruined towers: slab cells, columns, cores, cladding, a damage field of broken
tops and blast holes, rebar, hanging slabs, rubble heaps; viaducts, invisible blockers and lids) into `MR_<zone>` +
`Data/op_meridian_art.json` (lights: void, fire, rim, beam, moon, lamp, bio); `make_operation_map.py` assembles the
level (a storm with a low sun under its edge). The overhaul to the final build (`docs/operation/MERIDIAN_OVERHAUL.md`:
audit, art direction per district, the ten stages and their status; the prototype is commit 607d56d): `citykit.py`
= complete buildings that were then ruined (a `tower()` call builds one when `rk.CITY` is set: `ZONE_STYLES` gives
each district its architecture: resi, mixed, office, civic, industrial, lab; the skyline is `far_building`),
`streetkit.py` + `meridian_story.py` = the streets and what was left in them (our own vehicles, the army's line,
each district's story), `alienflora.py` + `meridian_flora.py` = the alien plants and where they grow (from
`citykit.ANCHORS` and `rk.HEAPS`, denser toward the canal, the tunnel and the Crown). Buildings the growth has taken (`alienflora.consume`) are
picked from `citykit.BUILDINGS`. Moss lies ON what it grows on
(`alienflora.moss(..., zf=)`: cushions set to the surface's own height; a rubble mound hands out its height function in
`rk.HEAPS`): never a sheet or dome pushed through another mesh, never a flat polygon laid on the ground. `meridian_landmarks.py` = one landmark per district (control tower and gantry, the
three slabs with sky bridges, the Galleria's arch and vault, the station canopy, the annex with its cooling towers,
the downed gunship, the Assembly's dome). Zones run in the order
districts, landmarks, story, flora. Look at the geometry before importing: build with `--noexport --save=x.blend`, then
`blender -b x.blend -P tools/blender/meridian_preview.py -- <outdir>` (workbench views along the route).
**Why the operation exists** is written before it is built (`docs/story/WORLD.md` = the adopted story bible in our words,
`docs/story/MERIDIAN_FALL.md` = this operation's reason): the beam over Meridian is calling home the Keystones in Nexus
Prime's wall, the wall has nights left, nothing flies through the storm, a team walks in to cut the beam and bring the
capital's Keystone home; for the Altered the Crown is the root's voice and its wound. The plan carries what the game
says: `BRIEFING` (a line at a time as the operation begins), `INTEL` (who and what over the radio as each stage begins:
what the place means, never how to play it), `OUTCOME` (the end screen): `FSOStage::Intel`, `ASOOperation::Briefing`.
**Interiors** (`interiorkit.py`): a `Local` frame per shop / room; what a piece of furniture stops is ONE hidden box
(`solid`), everything drawn is detail; no whole glass where it can be shot at (collision is all-or-nothing: a creature
could not see through it); stocked shelves and bookcases are blocks with a window of `ru_goods` / `ru_books` on the
front, cloth picks one of the four bands of `ru_fabric` (explicit UVs: `Geo.add(..., uvs=)`); signs are bars of light,
never words. A bay a wave is put down in keeps its front open and its middle clear.
**The route's edge is made of things** (the owner: "don't just use invisible walls"): `citykit.building(front=)` /
`rk.tower(face=)` = a building walked into from the street and sealed behind (blind and whole for three storeys on
its other sides), `boundskit.py` = what closes every gap (`containers`, `twall`, `collapse`, `growth`, `palisade`; all
over 7.7 m, no ledge under that; `run` for a polyline). `MR_blockers` is only a net BEHIND them, laid last, tagged
`SONet`: `ASOCharacter::MoveBlockedBy` logs `Boundary net touched at ...` (every touch is a leak to close). Draw a
district's edge as a plan before importing: `SO_BOUNDS_DEBUG=x.json` on a `--noexport` build (status per district in
MERIDIAN_OVERHAUL.md). The ramp, the decks, the bridge and the Crown have NO unseen wall: a fall lands in the yard
under the terraces or on the ground round the Crown (closed in by walked-into towers and a ring of grown ribs), and
the ways back up are the ramp's low sides, the rubble under the north deck and two plates lying against the Crown's rim.
**What is drawn is not what collides** (the cause of "the enemy can shoot through walls / get stuck in walls and
rocks"): a Nanite mesh's collision is built from its simplified fallback (the Crown kept 3% of its triangles, even
the invisible walls lost half), so shots, creatures and the nav mesh went through what was drawn. Every zone now
exports `MR_<zone>_solid` beside itself (`ruinkit.collision_of`: the faces flagged to collide, exact; towers only up
to `COL_TOP` / `col_top` above their foot, nothing for ruins behind the invisible walls, rubble heaps through a
coarser stand-in `HEAP_COL_RES`), imported NOT Nanite, complex-as-simple, double-sided (`_collision_mesh`), placed
hidden; the drawn zone has no collision. Never give a Nanite mesh its own complex collision (Nexus Prime's kit still
does: to do). Do not name an object `*_col` (the FBX exporter takes that for UCX collision). The invisible walls
stand 9 m over what is walked on (an air jump + a clamber reach nearly 6), with lids over the estate and the mall.
Modular by rule (owner, 2026-11-10). **Species**: every creature is written ONCE: one class with everything it is
(body, clips, voice, gun, numbers, its own moves; the brain is the shared `ASOEnemyAIController`), one file per species
(`SOAI/Private/Species/SO<Name>.cpp`), named by `ASOEnemy::SpeciesId`. Nothing lists them: `USOSpeciesLibrary`
(`SOSpecies.h`) finds every class that names itself, and `Spawn(World, id, feet, yaw, options)` is the ONLY way a
level puts one into the world (operations, spawners, scripts): never write creature code, a class table or spawn rules
in an operation or a level. What a level may add is data: a variant (`FSOSpeciesVariant`: health / damage / speed / aim /
sight multipliers, another gun, another name), applied by `ASOEnemy::ApplyVariant`, the one place that knows how; an
operation's plan has `"enemies"` (a baseline for all) and `"variants"` (named dressings its waves spawn like a
species), and `USOSpeciesLibrary::OnSpawned` for a level's own extras. Tests `ShatteredOrbit.Species.*`.
**Areas**: one area at a time (`USOAreaSubsystem`, `Data/areas.json`: range, city, operations with the content folders
that are theirs alone). Nothing of another area is built or loaded: each level builds itself when it begins, an
operation loads its species then and holds them only while it runs, travel goes through `USOAreaSubsystem::Travel`,
and anything kept by hand (the sound cache) lets go on `OnReleaseContent` before the old level is torn down. Check
with the console: `SOCensus` (what is loaded by folder + anything of another area), `SOAreaTour quit [area ...]`
(visits every area and back, `Saved/area_tour.json`; run it with `-game -nullrhi -nosound -unattended`). A prop every
area uses lives in `/Game/Shared` (listed under `"shared"` in areas.json): `Shared/Operation` (the barrier panel, the
conduit, `M_SOEnergy`, `M_SOGlowPulse`, their own material instances) and `Shared/Map` (the beacon). Travel shows a
loading screen (`USOAreaSubsystem::TravelToLevel`, the engine's movie player: the area's name on a dark screen). Never keep
a bare pointer to a loaded asset across a timer or a level change (nothing holds it: it is collected). Test
`ShatteredOrbit.Area.OneAtATime`.
The loadout is worn: of the three equipped guns one is in the hands, the others each in a place of their own
(`ASOCharacter::RefreshHolsters`: long guns stand side by side on the back, one behind each shoulder, placed by their
BORE LINE inside the shoulders' width, never by their outline (a gun with fins was pushed out beside the body);
handguns at the hips; the gun in hand is stowed while mantling); pictures `SOCaptureSeries 1 12|13`. The waist never
twists far (`USOLocomotionAnimInstance::MaxWaistTwist`, 20 degrees): strafing or standing while the aim turns, the
pelvis takes half the turn up to that and the legs the rest about their own hip joints (a bare waist shows every degree).
Movement (`USOCharacterMovementComponent`, the owner's brief of 2026-11-09): instant run, built sprint, coyote time,
buffered jump, variable jump height (letting go cuts the rise: "jump held" = `SetWantsToMantle`), air jumps
(`MaxAirJumps`, 1 by default; they turn the carried speed toward the stick), strong air control, slide, and traversal
measured from the obstacle (`ESOTraversal`: low / medium vault over a thin obstacle met at speed, automatic at a sprint;
mantle onto a ledge; climb): one path checked for room, relative to what is climbed (moving platforms), speed kept.
Landing keeps the impact speed (heavy landings recover). Fall damage is ON (the owner, 2026-11-11: a fall costs, and
a jump in the air before the ground saves it): `FallDamageMinSpeed` 1650 cm/s (about 7 m: free below that, a 10 m deck
costs a third of a bar, 24 m kills), `FallDamagePerSpeed` .11; an air jump sets the vertical speed, so the landing after
it is only as hard as the little way down from there (`ShatteredOrbit.Movement.FallDamage`). So nothing unseen stops a
fall anywhere: what is under a deck is ground to land on, with a way back up.
A window is gone THROUGH (`ShatteredOrbit.Movement.ThroughAWindow`): the ledge's top is found by where the way ahead
opens above the hit (never by a probe dropped from above: that started inside a window's head) and a few centimetres
in (a building's wall is 30 cm, thinner than a body); a ledge nobody can stand on (a sill, a thin wall) is vaulted at
any speed with the jump held, folding as far as `VaultDiveTuck` when the head is low (openings from about 1.05 m).
`GetMovementState()` / `OnMovementStateChanged` / `OnMovementEvent` are the ONE place animation, sound, camera and
effects listen to: a new ability adds a custom mode, a state and its events there. `ASOCharacter::HandleMovementEvent`
plays the sounds (`move_*`, `footstep_<surface>_<n>` picked by `GetFloorSurface` from the floor's material names:
metal, dirt, grass, wood, water; plain `footstep_<n>` is concrete; `sfx_synth.py ... movement`, import with
`SO_IMPORT_ONLY=audio SO_AUDIO_ONLY=move_,footstep_metal,...`), dust and camera kicks. The body is driven by the
motion, never by a clock (`USOLocomotionAnimInstance`): standing, the feet stay planted while the aim turns
(`StandYaw`, a turn on the spot past `TurnInPlaceAngle`); in the air the jump clip is a pose picked by the rise and
the fall (`AirTuck`); in a traversal the hands go onto the measured edge by arm IK while it is in reach and the body
leans over it; cross-fades are eased. Tests `ShatteredOrbit.Movement.*`, `ShatteredOrbit.Anim.BodyFollowsMotion`;
pictures `SOCaptureSeries 1 14|15` (slow motion, files `SO_m_*`). The animation layers: Idle / Stroll / Walk / Run by
speed on one shared cycle phase, Jump by the rise and fall, Land by the impact, Vault / Mantle / Climb by progress,
crouched: the body's own Crouch / CrouchWalk on the same phase (`CrouchDrop` only sinks a body that has no crouch
clips; sinking the standing clips over runtime leg IK made the legs flip: the owner's "legs glitch everywhere and under
the floor"). The runtime leg IK's knee can only bend ahead of the hip-ankle line in the leg's own heading
(`KneeAhead`: an almost straight animated leg says nothing about the knee's side). Test `ShatteredOrbit.Anim.CrouchWalk`
(feet over the floor, knees up and ahead, hips level: still, forward, sideways, backward). The first-person arms
hang from the eye, not the capsule (`ASOCharacter::Tick`: crouched, the capsule's centre drops and the eye comes down
to it; left on the capsule the shoulders ended up above the camera and the arms came into view from overhead; test
`ShatteredOrbit.Anim.CrouchFirstPerson`). Braking out of a run plays the body's `Stop` clip (by how fast it was going);
a turn on the spot is stepped (`TurnLift`: the foot on the side of the turn comes off the ground first); on a vault,
mantle or climb the gun is put away in both views and the first-person hands go onto the edge too. Test
`ShatteredOrbit.Anim.StopsAndTurns`.
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
when flanked; stuck detection steps them back onto free nav, and one found standing in the world's geometry is put
back on free ground (`Rescue`; a blink or a rescue asks `ASOEnemy::FitsAt` first). It does not stand there (the
owner: "the ai is stupid"): hit in the open or with a gun levelled at it, it steps aside (`Sidestep`, then new cover);
badly hurt it falls back to cover further off and stays down longer (`bRetreating`); when the target goes out of
sight half the squad pushes to where it was, the flankers round its side (`Push`), the rest hold and follow; claws
come in round the sides (`SideBias`), everyone keeps its own distance (`RangeBias`). A hunter knows where the players
are but aims and fires only at what it sees; `HasLineOfFire` is the bullet's own trace, fat, and stops behind a mate.
A hit is news (`USOCombatStatics::OnCharacterHit`, `OnCharacterDied` -> `ASOEnemyAIController::OnHit`): the one hit
knows from any distance; a mate that is looking at it (`Notices`: in view, nothing between) or stands within
`MateFeelRadius` is warned, and each one that reacts is noticed in turn by the next (`EnterCombat` passes it on a beat
later), so a sniped sentry wakes its group and nobody beyond sight (the owner: "if one is sniped then rest don't do
anything"). Every armed creature fights from cover to cover, the Remnant too: far from the range it likes it takes
any cover nearer the target than it stands (`FindCover` bAdvance) and holds a few bursts before the next bound; it
does not fire while running between two covers unless the target is on top of it; with nowhere to hide it comes
round in an arc to a point at its range, never down the line of the gun (`ThinkAssault`).
Tests `ShatteredOrbit.AI.NoShotsThroughWalls`, `ShatteredOrbit.AI.AHitAlertsTheSquad`. Shots on an unaware creature hit harder (ambush). Voices
per creature from `sfx_synth.py` (`<set>_idle/query/alert/hurt/death_N`). Operation waves: the first of a stage is an
unaware garrison (`hunt: false`), later ones hunt. Spawns land on the nav mesh where the capsule fits; L_Meridian's nav
mesh is bounded to the walkable route per zone (one big volume ran out of tiles in the towers).
The base is alive: grown chitin barricades round every post (`ruinkit.alien_barricade`, real cover), hive growths with
egg pods (`hive_growth`, `pod`, texture `ru_hive`), the Choir's spires (`alien_spire`), cables of light; the violet glow
breathes (`M_SOGlowPulse`); `ASOAmbience` loops (`amb_alien_hum`, `amb_hive`, `amb_alien_chorus`) and drifting spores.
Player: flashlight (F / right stick; `ASOCharacter::SetFlashlight`: a torch on the gun: the beam leaves just ahead of
the muzzle and is turned onto what the crosshair is on, a hot spot and a soft spill; by the eye the gun stood in its own
beam), clamber (ledges 2.45-3.8 m: a hang and pull up,
`ClamberMaxHeight`), footsteps the creatures hear. Loot lands on the ground (traced on the world only) and drops in.
Tests `ShatteredOrbit.Altered.*`, `ShatteredOrbit.AI.*`; pictures `SOCaptureSeries 1 9` on L_Meridian (logs the nav path).
Reward sets: the owner's concept sheets in `art/reference/operation/`. The Void Requiem guns (plan ids `vr_*`, set
`void_requiem`, shader `requiem`, LootWeight 0) are built by `tools/blender/requiem_guns.py` on `voidkit.py` (direct
meshes, no booleans: `talon` swept blade plates with a gold bead / a line of light under them, `feathers` rows of
them, `plate` / `prism`, `lathe` turned parts, `crystal`, `vein`, the gold-ringed `core`, the plasma `chamber`);
materials `gun_body` (black by the shader), `gun_metal__void` (polished silver), `gun_metal`, `gun_dark`, `gun_trim`
and `gun_glow` / `gun_glow__dim` / `gun_glow__crystal` (Unreal tints every `gun_glow*` slot with the rarity colour).
Look at them with `requiem_sheet.py -- out.png gun_vr_rifle:s gun_vr_rifle:q ...` (the game's dressing, bloom).
Their reloads move real parts (`SOReload::GetStyle`: rifle = cell magazine + charging handle, sniper = magazine +
straight-pull bolt, SMG, pistol = slide, shotgun = pump + crystal shells, hand cannon = crane / cylinder / speedloader;
own sequences: `BeltSegments` (LMG feed cover `hatch` + belt box), `CoreSegments` (fusion: flank `hatch` + core
crystal `biomass`), `BreechSegments` (launcher: breech lid + warhead `mag`)); their sounds are `sfx_synth.py` VOID
(every shot over a struck bell tuned along D minor) and the `vr_<foley>` reload sounds `ASOWeapon::PlayEventSound`
picks for the set. Test `ShatteredOrbit.Loot.RequiemSet`. Still to model: the Void Sentinel armour (`void_sentinel`);
until it exists that part of the reward falls back to a legendary gun.

## Testing
Build: `Build.bat ShatteredOrbitEditor Win64 Development -Project=<uproject>`. Tests: `UnrealEditor-Cmd <uproject>
-ExecCmds="Automation RunTests ShatteredOrbit; Quit" -unattended -nullrhi` (results in `Saved/Logs/ShatteredOrbit.log`).
Pictures: `UnrealEditor <uproject> -game -RenderOffscreen -windowed -ResX=1600 -ResY=900 -ExecCmds="SOCaptureSeries 1 <set>"`
(`Saved/Screenshots/SO_*.png`; sets in `ASOPlayerController::SOCaptureSeries`).
