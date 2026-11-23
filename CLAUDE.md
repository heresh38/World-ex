# WORLD EX — notes for Claude Code

The game is the Unreal project `unreal/ShatteredOrbit` (UE 5.8, C++). The old browser build (Three.js) was deleted on
2026-11-08 at the owner's request: never use, rebuild or reference anything from it. Every asset comes from our own
asset pipeline (`tools/blender`: so far all of it Blender scripts; the tools the owner approved on 2026-11-14 are the
first hard rule below) and every number from the Unreal project's own data.

**"Project Orion"** is the owner's code name for this game. Its standing brief is `docs/orion/MASTER_BRIEF.md` (the
owner's message of 2026-11-12, word for word: 33 parts, 13 phases). Read with it: `docs/orion/AUDIT.md` (what exists
and what is missing, by the brief's parts), `ARCHITECTURE.md` (module structure, dependency map, standards, the
decisions, and where the brief and the hard rules below differ: the stricter rule holds until the owner rules),
`ROADMAP.md` (where each phase starts, risks, the first milestone, phase 1 as work items) and a report per phase in
`docs/orion/reports`. The code keeps its `SO` prefix: the brief's `ProjectOrion...` class names are roles mapped onto
existing classes, never second systems.

## Hard rules from the owner
- **What an asset may be made with** (the owner's ruling, 2026-11-14, word for word: "Approve: Substance Painter,
  ZBrush, Blender and AI-assisted starting models. Improve: Require a consistent, repeatable asset pipeline with
  AAA-quality results. Keep strict: No unverified AI assets, poor topology, unfinished textures or unoptimised
  models in the final game."). It replaced "every 3D model and texture is made in Blender by our own scripts".
  So: Blender (our scripts in `tools/blender/*.py`, run with `blender --background --python <script>`, or by hand),
  Substance Painter, ZBrush, and an AI-assisted model as a STARTING point only. Whatever the tool, ONE pipeline and
  ONE gate: nothing is in the game that has not passed `tools/blender/asset_check.py` and been reviewed in the game
  (`docs/art/ASSET_PIPELINE.md`, "The owner's ruling on tools"; `ASSET_AUDIT.md` section 11). Still never: bought
  or downloaded third-party models / textures; Epic's sample characters may only be measured side by side
  (tools/reference), never imported, fitted or copied. Neither Substance nor ZBrush is installed here: what is
  built from this machine is still built by the Blender scripts.
- No names, terms or text from other games.
- AAA quality everywhere: nothing blocky or half-done, no lumps / ledges / bulges on any model (check silhouettes).
- Premium presentation at 60 fps on a mid-range PC.
- **Every texture follows `docs/art/TEXTURE_RULES.md`** (the owner, 2026-11-14, word for word there: "the rules i just
  posted ... should be for all textures to ensure our world is truly alive"): 4K, sharp up close, no seams or visible
  repetition; every set has albedo, normal, roughness, metallic, ambient occlusion and height (emissive where it
  applies); micro detail, imperfections, dirt where dirt collects, edge wear, scratches, dust, weathering, colour and age
  variation; never plastic, flat-roughness or clean. Made by our own pipeline (the tools the owner approved, the first rule above). Nothing of the old browser
  build's textures stays: what descends from it is replaced. `docs/art/TEXTURE_STATE.md` says which sets meet it.
- **Guns follow `docs/art/GUN_TEXTURE_RULES.md` as well** (the owner, 2026-11-14: "this rule is for gun textures so
  remember these too and apply it"): every weapon looks manufactured (machining marks, seams, fasteners, serial
  numbers, safety markings, a maker's mark: all ours), its wear tells how it was used (grip, magazine well, charging
  handle, heat colour at the barrel, dust in recesses), seven materials each with its own roughness, NO flat panels,
  no surface over 10 cm visually empty, and it holds up turned within 5 cm of the camera. The games named there are
  a quality target only.
- **Every weapon is BUILT to `docs/art/WEAPON_BUILD_RULES.md`** (the owner, 2026-11-15, word for word there: "keep/save
  those rules we have for building all weapons so they have the correct things required"): real proportions, depth from
  every angle, assembled from many parts in a hierarchy (primary forms, mechanical assemblies, technical details), each
  with a purpose: separate upper / lower receiver, ergonomic grip, trigger guard, removable power cell or magazine in
  its housing, barrel shroud, cooling vents, maintenance hatches / access panels, recessed muzzle, rail, sight and sensor
  modules, attachment points, overlapping armour plates, fasteners, seams, panel gaps, varied materials, an exposed
  mechanism. Never flat panels, a blob, an extruded outline or random greebles. An alien gun is its species' own
  making, not a human rifle in alien colours. Budget: up to 200,000 triangles a gun (the owner raised it from 60k on
  2026-11-15: "the weapons are ... the center focus of the player so the must look amazing"); guns others hold will
  need lighter LOD copies.
- **One colour palette a set** (the owner, 2026-11-15: "all guns in the set need to have the same color pallet and shoot
  the same color, this is our rule going forward"): every gun of a set (its `"set"`; a gun of no set: its class's
  family, light / kinetic / horror) fires the same colour and carries the same light. `Data/game_data.json`
  `"palettes"` holds them (tracer, glow); no archetype has a colour of its own (`import_assets.palette_of`,
  `USOWeaponData::GlowColor` over the rarity's tint; rockets burn their set's colour). Test
  `ShatteredOrbit.Loot.OneColourASet`. A new set gets its palette before its first gun.
- **Every asset is made to `docs/art/ASSET_PIPELINE.md`** (the owner's PERMANENT art-production specification,
  2026-11-14, word for word there, 16 sections): fewer, exceptionally good assets first and a repeatable pipeline, then
  scale; never remodel the whole game at once. A model that works is not a finished asset: real proportions and
  construction, bevelled edges, a high-poly and a game-ready model with the details BAKED (normal, occlusion,
  curvature, position) where it pays, proper unique UVs at a consistent texel density, full PBR, wear placed where
  use puts it (never uniform random scratches), judged under NEUTRAL light as well as gameplay light, checked inside
  Unreal, performance profiled. Every asset has a status (Concept / Blockout / Work in progress / Technically complete
  / Art-approved / Game-ready / Shipping-approved): `docs/art/ASSET_AUDIT.md`. The owner RULED on the tools it
  names (Substance Painter, ZBrush, AI-assisted starting models: approved, see the first rule above); where it and
  another rule still differ, the stricter rule holds until the owner rules; the table is at the end of the
  specification.
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
- **The whole world follows `docs/art/WORLD_ART_DIRECTION.md`** (the owner's master art direction for atmosphere,
  lighting and world identity, 2026-11-16, word for word there: "Please remember and save this and consult it to
  ensure our world is triple a and fits with the story"). Read it before any level, sky, light, weather,
  post-process, colour grade, environment or faction work. In short: hopeful military science fiction; the world is
  beautiful even where it is dangerous; darkness is intentional, never the default (no grey or brown monotony, no
  permanent fog, no oppressive darkness, no bleak grade); lighting realistic, cinematic AND readable (enemies,
  objects, weapon effects; species recognisable at a distance); every planet its own biome, palette and light;
  Earth's protected settlements inside great walls are safe, advanced and alive, and outside them the invasion's
  ruins keep colour and beauty; every species has its own architecture, materials, technology, palette and ships
  (not every faction violet); the fractured empire shows in the world (species fighting each other, captured
  installations under another insignia, wrecks of the fleet); weather comes and goes and never stands in for
  detail; places look designed, never assembled from repeats. Its notes (ours) say how it sits with the story
  (`docs/story/WORLD.md`) and the operations' rules; the games it names are a quality target only.

## Asset pipeline
- `bash tools/blender/build_all.sh` builds the Blender sources Unreal's export reads into `assets/` (generated, not
  committed): textures (`textures.py`, `weapon_textures.py`, `surface_maps.py`, `wear_textures.py`, `horror_textures.py`,
  `nexus_textures.py`, `world_maps.py`, `detail_maps.py`, `nexus_city_textures.py`, `city_maps.py`, `ruins_textures.py`,
  `ruins_maps.py`: the `*_maps.py` are the texture engine's sets and overwrite the older scripts' of the same
  names), the guns and optics (`weapons.py` + `gunkit.py`),
  the stalker (`aliens.py`, `fleshkit.py`), Nexus Prime (`nexus.py`, `nexus_city.py` kit),
  the city trees (`city_trees.py`), loot props (`loot_props.py`), the reliquary (`vanthos.py`), Meridian (`meridian.py`)
  and effect cards (`fx_kit.py`). Then `bash tools/blender/export_unreal.sh` builds the players and turns everything into
  `unreal/ShatteredOrbit/SourceArt` (FBX + textures + json), and `Content/Python/import_assets.py` imports it.
- `bl.py` helpers (materials, primitives, loft, export). Blender is Z-up, -Y forward; glTF is Y-up, +Z forward.
- Weapons (`weapons.py` on `gunparts.py` (the hard-surface kit: lofts through chamfered sections, turned parts, vented
  cages, stocks, magazines, muzzle devices, sights; direct meshes on `voidkit.py`, no booleans) + `gunkit.py`, textures
  `weapon_textures.py`; rebuilt 2026-11-12 toward the Requiem guns' standard, sheets `Saved/Screenshots/guns_*`): every
  archetype in `Data/game_data.json` has a
  class: `energy`, `kinetic` (real projectiles with muzzle velocity and drop) and `horror` (living biomass). Sights
  (`gun_attach.glb`: reflex, holo, 2x/4x/8x and the compact 4x `prism`; the importer takes every sight the data's
  `sights` table names) mount per copy; magnified optics use the object name `scope` + `gun_lens`. What a gun may
  carry follows its kind (the owner, 2026-11-12: "a sniper scope on a shotgun makes no sense"): rifles default /
  reflex / holo / 4x, scout and battle rifles 4x / prism / 8x, sniper 4x / 8x, handguns, SMGs, shotguns and launchers
  irons / reflex / holo, the heavy machine guns up to 2x, living guns their own; a copy with a sight its gun may not
  carry gets the gun's own (`ASOWeapon::SetInstance`). `ShatteredOrbit.Aim.EverySightOnTheEyeLine` holds every gun
  with every allowed sight to it: the sight's point on the eye's axis as each round leaves, an optic's glass centred
  on it, windows wide enough to look through. Rounds leave along the eye's axis, so on the sights the gun turns about
  its SIGHT (`USOViewmodelComponent`: `SightPivot`), aimed spread is x0.25, a long gun's irons sit 9 cm ahead of the eye (further back the eye is over the stock and its comb fills the
  picture; a handgun's 24, `AdsHandgunSightDistance`)
  (`AdsSightDistance`), an optic on a handgun 12 cm (`AdsHandgunOpticDistance`). A rotary gun's barrel cluster is the
  part `spin` (origin on its axis): `ASOWeapon::Tick` turns it while firing. Tracers and flashes take the gun's own
  colour (`tracer` in the data: kinetic warm, light guns cyan / blue / gold, living green and violet; a bolt of light
  is longer with a head), the flash is five torn blades (`FX_Star`, shader mode 3), nothing is drawn through a scope.
  **The Sarketh's guns fire crystalline SLUGS** (the owner's brief, `docs/orion/SARKETH_WEAPONS.md`, word for word
  there): `ESOProjectileKind::Slug`, an amber-charged solid round (`USOFxSubsystem::SlugRound / SlugImpact /
  SlugFlash`) that goes on through bodies (`pierce`), and thermal accumulation on the gun (`"heat"`: brighter, then
  faster, then a forced vent; the HUD's heat gauge). Never the light guns' plasma look on them. Test
  `ShatteredOrbit.Weapon.SarkethSlugs`. A gun's glass may carry a maker's name (`gun_lens__skr`): the import makes every
  `gun_lens*` slot see-through (named otherwise it was a solid pane over the sight). A part MADE of glass is `gun_glass*`
  (`M_SOGlass`: translucent, clear face on, its edges catching light; the Veyr Striker's crest sight). Try them: the
  range's Sarketh cache (`skr_rifle`, `skr_striker`). A gun whose flat faces unwrap badly gets its own unwrap
  (`weapons.UNWRAP_TRIES`).
  **The light guns fire plasma, not bullets** (the owner, 2026-11-14: "more alien ... alien energy or plasma ... instead
  of a kinetic bullet the human weapons use"; they are the Sarketh's own technology): a gun whose projectile is
  `ESOProjectileKind::Bolt` draws `USOFxSubsystem::PlasmaFlash` (a bloom of its light, no flame or smoke),
  `PlasmaBolt` (a white-hot core in a corona of the gun's colour at the FRONT of a short tail, and the air along
  its path glowing a length at a time behind it for a tenth of a second: a streak's position is its front, the tail
  grows out behind it; the whole shot is drawn in the SHOOTER's frame: bolt, trail and glowing air carry the
  shooter's velocity and the bolt is aimed to land where the round hits: fixed in the world, a player firing on the
  move left every trail hanging beside the barrel, the owner's "bullets don't come out of the barrel"; capture set
  33) and `PlasmaImpact` (a flare, drops thrown out along the surface, vapour, a glow that cools; no
  bullet hole; a pattern of pellets lights the place once); the bolt's size follows the gun's damage. A bolt is SEEN
  to fly: the energy archetypes' `vel` in `Data/game_data.json` is 170-380 m/s (the sniper's lance 900) against a
  bullet's 700+, so a light gun is led at range and creatures lead a moving target with it (`ASOEnemy::ShotLead`,
  `GetAimDirection`). `SO_IMPORT_ONLY=gunnumbers` re-reads the guns' numbers without touching a mesh. Test
  `ShatteredOrbit.Weapon.LightGunsFirePlasma`; pictures `SOCaptureSeries 1 28` (files `SO_p*`). The light guns'
  MODELS are not changed by this.
  **Textures are DRAWN through one engine, `tools/blender/pbr.py`** (the owner's texture rules, see the hard rules;
  the state of every set is `docs/art/TEXTURE_STATE.md`: keep it honest). A `Tile(name, metres)` knows how many
  metres it covers; every feature is given its real size and the height is kept in METRES, and from that one height
  come the normal (the true slope x `relief`), the ambient occlusion (how far a point lies under its surroundings, at
  five radii) and the height map, so the maps agree. It writes `<name>_c.jpg` (albedo), `_n.png` (OpenGL normal),
  `_m.png` (R AMBIENT OCCLUSION, G roughness, B metallic), `_h.png` (height), `_e.jpg` (emissive, where given) at
  4096 px, and each set's tile and depth into `assets/textures/pbr_sets.json`. Its tools: `noise`, `cells` (nearest /
  second nearest / an id: stones, dishes), `cracks` (along warped cell borders, in patches), `grid` (courses of blocks:
  joints, distance to the edge, an id per block), `lines`, `dents`, `brushed`, `streaks` (what runs DOWN a wall),
  `blur`. The sets: `world_maps.py` (Nexus Prime's kit `nx_*`, the reliquary's `panel` / `concrete`: these descended
  from the browser build), `city_maps.py` (Nexus Prime's ground `nc_*`), `ruins_maps.py` (Meridian's sixteen main
  surfaces), `surface_maps.py` (the guns' thirteen `wpn_*`, 22 cm a tile: `wpn_paint` the light guns' ceramic coat,
  `wpn_metal` their forged iron, `wpn_steel`, `wpn_park`, `wpn_poly` / `wpn_odg`, `wpn_wood`, `wpn_knurl`, and
  `wpn_anod` / `wpn_brushed` / `wpn_titanium` / `wpn_carbon` / `wpn_rubber`, which no gun wears until its parts are
  given them in weapons.py), `detail_maps.py` (`det_*`: half a metre a tile, only what is too fine for a tile's own
  map; `macro`: a field with no small shapes). They keep the OLD sets' names, layouts and colours, so nothing that
  uses them is built again; each runs after the script it replaces (`build_all.sh`). Lessons: the old painters do NOT
  hold above 1024 px (their cracks are a noise's contour lines and become wandering loops; nothing in them is finer
  than a thousandth of a tile): a set is redrawn, never upscaled. Nexus Prime's old sets saved their hex colours as
  LINEAR values (`city_maps.lin`), Meridian's through the sRGB curve (hex as read). A map carries FEW scratches and
  shallow relief on a gun (22 cm of gun, and the game lays its own wear on every copy: the first tries were a rink,
  then stucco, then mail). Streaks and holes go in patches and in tens, not hundreds (a wall of even runs reads as
  a pattern). **In the game** (`import_assets.py`): the master `M_SOStandard` takes ambient occlusion from the
  mask's red (`AOAmount`), parallax from the height map (`HeightTex`, `Parallax` = depth / tile), a detail normal
  (`DetailTex` at `DetailScale` repeats a tile, `DetailStrength`, `DetailCavity`) and a macro variation at a scale
  that is not a whole number of tiles (`MacroTex`, `MacroScale`, `MacroAmount`); every one is OFF by default, so a
  material that does not ask is as it was (an old mask's red is not occlusion). `M_SOGround` takes the detail normal
  and the occlusion, `M_SOFacade` the detail normal. `SO_IMPORT_ONLY=worldmaps` imports every engine set the game
  already shows, with all its maps beside it, and tells each instance on it what to use (`PBR_FINISH`: its detail
  kind and amounts; the game holds colour and normal at 4096, the mask at 2048, the height at 1024);
  `SO_IMPORT_ONLY=guntextures` does the guns'. The players' armour plate is fabric.py's `polymer` (1024 px, two
  scales, not on the engine yet): `hero/remap.py -- polymer` writes a kind's maps again for both bodies without
  building one, `SO_IMPORT_ONLY=player_textures` brings them in.
  **An asset's OWN maps** (the art-production specification's baked workflow; the reference asset is the assault
  rifle, `docs/art/ASSET_AUDIT.md` section 10). A tiling set says what a surface is made of; it cannot know WHERE on
  the object it is. `bakekit.py`: `unwrap(objs)` gives the object and its moving parts a second UV set `UV1` (unique,
  one texel density, packed together; UV 0 keeps the tiling sets), `bake(objs, size)` bakes through Cycles (OptiX)
  from a joined copy: ambient occlusion (short reach), every texel's world position and normal, its material, what
  is covered; `curvature()` gets how the surface turns from those. `gunpaint.py` paints a gun's maps from them by
  its spec (`SPECS[<model>]`: its places in the gun's frame): `<gun>_u_m1` (R occlusion, G EDGE WEAR where the
  surface turns outward and is exposed, B DIRT in hollows and inside corners, soot at the muzzle), `_u_m2` (R
  HANDLING: grip, fore end, comb, controls; G HEAT at the muzzle and gas block; B PAINT in markings), `_u_m3`
  (relief, .5 none: engraved below, raised above). Marks are placed in SPACE (`Marks.text` = Blender's own text
  object filled as a mask, `stamp`, `bead` = a weld, a spec's `seams` = a mould line), so they fall on whatever
  faces that way there; on the left flank text reads toward +Y (the stock), on the right toward -Y. Noise is taken
  in space (`noise3`), so nothing shows at an island's edge. The rifle's: the maker ("NEXUS PRIME ARSENAL"), the
  model, a serial number, the broken-ring mark, S / F / A at the selector, the calibre and proof marks, welds at
  both trunnions, the grip's mould seam. `weapons.own_maps(name)` runs it in `finish()` for every gun with a spec
  (`SO_GUN_NO_BAKE=1` skips, `SO_GUN_BAKE_SIZE`). In the game: `M_SOStandard` reads `UniqueTex1/2/3` on UV 1 when
  `UniqueAmount` is 1 (the wear shader's edge, dirt, handling polish, heat colour and paint; occlusion; the relief
  bent into the normal from the surface's own derivatives, `BUMP_HLSL`, `UniqueBump` cm to the unit: no tangent
  frame on UV 1 is needed); `gun_instances` imports `T_<gun>_u_*` and sets them on every material of that gun;
  static meshes are imported WITHOUT generated lightmap UVs (they would overwrite UV 1). One gun again:
  `weapons.py -- rifle`, `export_fbx.py -- assets/models/gun_rifle.glb SourceArt/Weapons/Rifle --split-parts`,
  `SO_IMPORT_ONLY=weapons,guntextures SO_WEAPONS_ONLY=rifle`. A gun's GLB carries no tiling set (2026-11-22: the
  rifle's was 141 MB, 139 of them the 4096 px sets every gun shares, and export_fbx.py wrote them out again per gun:
  2.9 GB of copies): `bl.unembed_images` (`gunkit.export`, the sights, the explosives) names every image that is one
  of the engine's own files in `assets/textures` by a relative uri, byte for byte the same (the rifle's GLB is 2 MB);
  Blender's glTF importer reads the uri back, and `export_fbx.py` writes the file where it lies into materials.json
  (`../../../../../assets/textures/wpn_steel_c.jpg`; nothing copied; `import_texture` normalises the path). Look at ONE gun in the game:
  `SOCaptureSeries 1 29 -SOGuns=<archetype>` (the gun alone from each flank, three quarters, close on the receiver,
  the markings, the muzzle (aimed at the gun's own muzzle, `USOGunRigComponent::GetMuzzleLocation`): files `SO_r_<gun>_*`). **The high-poly** (`bakekit.bake_highpoly_normals`, every gun with own maps: the rifle and all
  eleven light guns; `SO_GUN_HIGHPOLY=none` skips it, a list bakes only those): the game model with its hard edges rounded (0.7 mm bevel, three steps, weighted normals), its normals baked
  in OBJECT space onto UV 1 (`<gun>_u_n`, imported BC7 linear as `T_<gun>_u_n`); `M_SOStandard` decodes it (Blender
  X left, Y back, Z up -> mesh X, -Y, Z), takes it to world space and turns the surface normal (tiling and detail on
  it) from the game model's own normal onto it (`UniqueNormalTex`, `UniqueNormalAmount`). The rifle's report (cost, met, not met) is `ASSET_AUDIT.md`
  section 10. Lessons of its review: a gun with own maps takes NO wear from the vertex colours (soft blobs) and
  little shared grime; an own map's edge wear is CUT against the shared mask's chips (`WEAR_EDGE`: the map says how
  much, the chips where exactly: crisp at any distance); nothing is rubbed on a flat without a cause (a patch read
  as a stain, a stroke as a soft block); a rubbed edge is a line at the corner, not a band a chamfer wide (white
  paint); the tiling sets carry LITTLE random rubbing and few pits (where a finish is rubbed is the own maps' work),
  and parkerizing is a phosphate coat, not a metal. **A static mesh imported again keeps the slot names of its
  first import**: `assign_materials` names and fills slots by `imported_material_slot_name` (filled by the old
  names, the rifle's olive grip wore the stock's walnut); `SO_IMPORT_ONLY=gunslots` puts every gun mesh's slots
  right without importing anything.
  **The gate** (the owner's ruling, the first hard rule): `blender --background --python tools/blender/asset_check.py
  -- <model.glb> --class=weapon|player|boss|enemy|vehicle|prop|building [--json=x.json]` measures the game-ready
  model whatever made it (triangles and materials against the class's budget in `asset_check.CLASSES`, degenerate /
  loose / wrongly wound faces, slivers, UV 1 overlap, texel density on what is seen, stretch, atlas use, every
  material with colour + normal + roughness maps and a roughness that has a range, the own maps); exit code 1 on a
  failure; an asset that fails or was not run stays below Technically complete (`ASSET_AUDIT.md` section 11). Run
  it BEFORE showing an asset. What it taught the pipeline: `bakekit.clean` (cuts every face into triangles the
  better way and deletes what has no area: an exporter's cut of a face with corners in a line makes zero-area
  triangles), `bakekit.unwrap` lays each projected island out again with the least stretch, `unwrap(shrink=.25)`
  cuts off and shrinks islands nobody can see (off by default: it pays for skin under clothes, not for shells laid
  on shells), the kinetic guns' brass is a set (`wpn_brass`).
  **The rifle is APPROVED as the benchmark** (the owner, 2026-11-14) and the pipeline goes gun by gun, the light
  guns first. A gun needs no hand-written spec: `weapons.finish` hands the painter what the builder already says
  (scale, muzzle, fore end, each moving part's pivot) and `gunpaint.auto_spec` makes the spec from it (grip
  materials are handled; the off hand lies round the fore point; a moving part's pivot is a rubbed track; heat at
  the muzzle, and what is not metal soots instead of bluing; a COAT, `gun_body` / `gun_paint`, chips a millimetre
  in from its rims where a blue only rubs at the corner). Which guns: `gunpaint.spec_for` (the rifle's own spec,
  every gun in `gunpaint.LIGHT`, and `SO_GUN_OWN=all` or a list for the rest). **Markings are placed where there
  is room**: `gunpaint.clear_patch(maps, side, w, h)` finds a clear, flat, open place on the baked flank (never a
  guessed coordinate: a mark over a vent is worse than none). **The light guns are marked the Sarketh's way**
  (they are the Sarketh's make): their emblem (`sarketh_mark`: the brow's chevron, the lozenge with the vent's
  slit, three dashes either side, as on their cloth) and a line of their writing (`sarketh_glyphs`: stems with
  ticks and points; it says nothing in any tongue), cut BIG into a pale shell (a stroke under a texel of the map
  is a smudge; on their dark iron grime in a cut is lost). No human letters on a light gun. Their gold is a set
  (`wpn_gold`). One gun through everything: build, `asset_check.py`, `export_fbx.py --split-parts`,
  `SO_IMPORT_ONLY=weapons,guntextures SO_WEAPONS_ONLY=<arch>[,<arch>]`, `SOCaptureSeries 1 29 -SOGuns=<arch>`.
  A gun seen for the first time has its textures built as it is drawn: the review waits six seconds for them
  (pictures taken at once showed the own maps at a low mip). A relief map's empty space is .5, never black
  (`gunpaint._fill(rest=)`: black is a pit at an island's far side in the small mips).
  **The texture streamer must be TOLD how a material reads a texture** (`import_assets.sampled` ->
  `USOEditorLibrary::SetTextureSampling(material, texture, UV set, repeats)`): the engine works that out only in
  an editor build step the import never runs, and otherwise takes every texture to lie once across UV 0. A gun's
  own maps lie on UV 1 across the whole gun, so they were held several mips too small: the Sarketh's marks were
  a smudge with a sharp 4096 map on the disk (it looked like a texture problem and was not: check the map itself
  before redrawing it). The own maps `_u_m1` and `_u_m3` are held at 4096, `_u_m2` at 2048. `bakekit.unwrap_fit`
  unwraps again with smaller islands (66, 50, 38 degrees) while more than 8 % of the surface is stretched (turned
  forms: a launcher's tube, a barrel cluster). The gate lets lights, glass and sight paint be one flat value
  (`--flat-ok`: gun_glow, gun_lens, gun_dot, gun_tritium, gun_sightpaint, gun_sightorange).
  Every copy is worn its own way (`USOGunRigComponent::Dress`: edge wear, scratches, grime and the mask's tiling from
  the copy's uid). Pictures: `SOCaptureSeries 1 18` (first person: hip, aimed, firing, every sight; files `SO_v_*`;
  run captures with `-ForceRes`).
  The kinetic guns and the handguns were rebuilt body by body on 2026-11-12 (the owner: "Yes, rebuild them"; the
  earlier passes had only added parts to flat extrusions): each receiver, cover, handguard, stock, grip and magazine
  is its own loft through changing sections (`gunparts.Body.skin` / `shell` / `checker`, `Limb` for grips,
  `ring_frame` and `drum` for the revolvers), no side face flat for more than 5 cm, each gun its own kind of body
  (stamped rifle, two-piece alloy carbine, walnut-stocked battle rifle, turned bolt action in a chassis, round-topped
  pump, tube-receiver SMG). Both shotguns aim through a raised ghost ring and front post (their `sight` is the
  ring's centre): a bead on the receiver's top put the stock in the middle of the aimed view.
  Reload parts are own objects with their origin at the pivot (node names are an API): `mag`, `bolt`, `charge`,
  `slide`, `pump`, `crane` > `cylinder` > `rounds`, `hatch` + `biomass`; loose props `x_shell`, `x_round`,
  `x_casing`, `x_speedloader`. **The light guns reload their own way** (the owner, 2026-11-15: "a different reload
  than the kinetic guns ... a part of the gun opens up and draws energy in from the air, some venting on overheating,
  maybe a battery replacement"; before, their cell was welded to the body and the hand only cupped it flat:
  "relaxed on his palm when he should be gripping it"), by `SOReload::GetStyle`: **cell** (auto, smg, pulse,
  energy: the cell is the part `mag`; the hand grips it, its lock pops with a hiss, it is drawn out and dropped, a
  fresh one is pushed home and turned to lock, the gun charges up), **vent** (hmg, sniper, scout) and **intake**
  (shotgun, rocket, handcannon, sidearm): a flap on the LEFT flank (the side the player sees) is the part `hatch`
  (`weapons.flap`: the shell stays on the right flank, the left one is hinged on its top edge, turned about the bore
  line): vent = the hand throws it open, the heat is purged in a burst and the gun shudders, slapped shut; intake =
  it opens by itself (the hands stay on the gun) and the gun draws energy in from the air, motes streaming into the
  opening. Pictures `SOCaptureSeries 1 34 -SOGuns=<arch>,...` (files `SO_lr_<gun>_first|side|close_<n>`). Effects: reload events
  `fx` (Arg = vent / intake / cellpop / charge, Count = thousandths of the segment, ms once scaled) ->
  `ASOWeapon::PlayReloadFx` -> `USOFxSubsystem::ReloadVent / ReloadIntake / ReloadCellPop / ReloadCharge` (in the
  view that shows the gun, HELD to the gun: every particle carries an `FSOFxAnchor` (the gun, a point in its rig
  frame, where that point was last frame) and `Tick` moves it by however far the point moved, through
  `ASOWeapon::RigPointToWorld` (the viewmodel's space for the first-person gun); spawned with the holder's
  velocity of the moment, the cloud hung in the air where the reload began when the player turned, stopped or the
  gun swayed: the owner, 2026-11-20. `SOCaptureSeries 1 34 -SOReloadTurn` turns 30 degrees between the moments to
  show it). **Overheat**: a light gun that fired a long burst (half
  its cell, 8 to 40 bolts) vents a little by itself as the trigger is let go (`HeatShots`). Sounds `sfx_synth.py`
  `cell_pop cell_lock light_charge flap_open flap_close light_vent light_vent_small light_intake`. Test
  `ShatteredOrbit.Loot.LightGunsReloadTheirOwnWay`. Gun wear: the `_wear` attribute (convex edges) goes into the vertex colour alpha.
- Material **names are an API** (`gun_body`, `gun_glow`, `orion_*`, `skin__<region>`, `hair*`, `nx_*`, `nc_*`, ...).
- Weapon / loot numbers: `unreal/ShatteredOrbit/Data/game_data.json` is their source (edit it, re-import).
- Check models with `tools/blender/preview.py -- out.png model.glb:Action:frame:view ...` (Cycles contact sheet).
- Creatures: `fleshkit.py` (tagged SDF primitives -> Surface Nets -> skinned GLB, baked FK clips) with the `hx_*` sets
  from `horror_textures.py`; the stalker is the only one in the game so far (`/Game/Characters/Stalker`).

## Characters
**The male player is the Orion body** (`tools/blender/hero/orion`; in the game since 2026-11-17, the owner: "put the
player in the game and delete the old male model"; nothing of the old male's rig, skin maps, head or clothing is
used). `lab.py -- out.png --levels=2 --detail --gamehead --facekeys --save=x.blend` builds it: the cage (`body.py`)
tags each face's game region (`body.face_regions`, `REGIONS`: a band between two parts goes to the hand / foot, so the
forearm ends on the wrist's ring), the game head (`headcage.py`: a ring cage laid on the sculpt `head.py`; the ears'
windows are capped through the cage's solve and cut out after the subdivision, each ear a ring grid on the sculpt's own
ear, `ear.py`: cut where the ear's field takes over, laid flat by a harmonic map, rings down equal-length spokes), the
face's 22 sliders as morph targets `face_<key>` (`headcage.FACE_SLIDERS`; a slider that moves a FORM is a warp of the
sculpt's space, `head.WARPS`: jaw, chin, cheekbones, cheeks, temples, forehead, eye bags, tear trough, hood; the nose's
two warp the nose's own field, `headbase._nose_warp`; the eyes' rims are pinned on the sculpt's own opening for every
slider, `headcage.rim_points`, so eye_open / eye_size move the opening itself; the lids' bands are laid BY CONSTRUCTION,
`headcage.place_lids` / `front_lids`: the four rings out from each rim (`lid_rings`) on the lid's front by rays from in
front, its front edge, the margin straight back to the globe; laid by nearest points they found the lid's own inside
and folded back along every lower lid; the nose tip's patch stays inside its window's rings, or it overlapped the band
above and the skin folded across the nose, a dark line each side). The flank under each arm follows the
sheet's line (the owner circled a bulge there: `ARMPIT_OUT`, `FLANK_ZONES`). The arm is an adult man's
(`UPPER_ARM` .332 since 2026-11-21 (the humerus at its norm, 0.18 x stature; .312 before), `FOREARM` .272: the sheet's canon left it 4 cm short and in third person the support hand could not
reach a long gun's fore end; the arm's sections are written for the design arm and stretched, `body.arm_s`). **The
arm's volume is its own table** (`body.ARM_VOL`, cm at real stations along the arm; the owner, 2026-11-20: "the arms
seem extremely unrealistic compared to rest of body"): the first two rings keep the sheet's deltoid, then the upper arm
HOLDS its girth through the biceps' and triceps' bellies (12 cm from 14 to 20 cm out: the sheet's plateau) and tapers
to a notch just above the elbow, the forearm SWELLS below the elbow (the extensors' ridge and the flexors: 9.6 x 11
cm at 36 cm, wider than the elbow's 9 x 9.5, as the sheet's) and runs out to a wrist 4.6 x 6.4; before, a hand-written
forearm table was 30 % thin and fell straight from the elbow, so the arm was a stick with a ball of a deltoid at its root.
**A hero's build** (the owner, 2026-11-21, "the players arms seem very skinny compared to the rest of the body"): the
finished arm measured against the norms (`scratchpad` script `measure_body.py`'s stations: a 184 cm man) was ON them
(upper arm 40 cm round, forearm 30, thigh 59, chest 104, waist 80) and still read thin beside the chest and shoulders,
so `ARM_VOL` is a heroic build's (upper arm and forearm 10 % rounder, 43 and 33 cm; the deltoid 5 %, the wrist 6 %),
the stations following the longer humerus; the rest of the body stays on the norms (every other station within a
few percent). `body.arm_mod` carries only the masses that are not round (biceps, triceps, the brachialis on the OUTSIDE under the
deltoid's point, the olecranon, the extensors' ridge rising ABOVE the elbow: begun below it there was a hollow at the
elbow's outer front); the forms on them are `anatomy.py`'s, whose arm muscles sit at SHOW .36-.44 (at .26-.32 they drew
nothing, and the brachialis had no entry: it ran at the .20 default on the inside, under the biceps). The anatomy's relief
takes about 1.9 mm off every surface (`GROOVE`) and puts the bellies 3-7 mm back: the cage's table is written for what
comes OUT (measure with `hero/orion/armsec.py`: vertical extent, depth, top and bottom of the arm every 2 cm). `game.py` (in Blender on the saved build: stages normals, uv,
skin, eyes, lashes, rig, suit, clips, export; `--stages=` picks some, `--save=` saves the build BEFORE the export splits
it, and a build saved after its export can still run `clips,export`; NEVER `rig` again on a saved build: it adds a
second armature modifier to the eyes, hair and lashes and a second suit object beside the old one, and the
export took the old suit with a dangling modifier, its sleeves in a T-pose in the game (2026-11-21); a change to
the skinning is run from the LAB build, every stage) makes it the game's: the head's normals from the
sculpt's field; UVs on hidden seams in two maps (`skin_face`: the head and ears, 0.13 mm a texel; `skin`: the rest, the
hands at 1.7x); the skin maps (`orion_male_skin_<face|body>_BaseColor / _Normal / _ORM`, R occlusion G roughness, B the
brows) baked through the head lab's own skin shader FROM THE GAME MESH (from the sculpt, rays met the wrong side of the
nose and missed under the jaw); the BROWS drawn hair by hair into the face's map (`brow_mask`: each of `groom.brows`'
strands carried onto the mesh and drawn as a tapered line, the ORM's B = how much of a texel is hair; `M_SOSkin` puts
`HairColor` over the skin by it, `HairAmount` 1 on the face, so the creator colours them with the hair: cards of six
hairs read as shingles and a hairbrush; the export material wires EVERY channel of the packed map the glTF way, R
through the exporter's `glTF Material Output` group's Occlusion, B to Metallic, or the exporter writes a map of its
own with R and B white: the game's skin had no occlusion, and with the brows in B the whole face took their colour;
check `SourceArt/Characters/PlayerMale/Textures/*_ORM.png` after an export); the lashes (`B_lashes`, `hair__lash`: cards of three or four of
`groom.lashes`, each a ribbon along its lid); the eyes (the sculpt's eyeballs, the front half unwrapped,
`orion_male_eye_BaseColor`); the rig (the shared player
skeleton, its joints from this body's own construction: `body.arm_axis`, the hand's `joints_of`, the foot's toes, the
knee 1.2 cm ahead of the hip-ankle line (behind it, the game's leg IK bent it backward in a sideways crouch-walk);
heat weights solved on a closed voxel copy, the eyes' openings filled, then copied face by face; then the SKULL
and the face weighted whole to the head bone, `game.rigid_skull`, blended in over 5 cm from 2 cm under the skull's
base joint: the heat weights spread the neck's share up the face, and when the head pitched 80 degrees with the
aim the sockets lagged behind the eyeballs, which are whole on the head, and the eyes stood out of the face: the
owner, 2026-11-21, "the players eyes seem to be popping out of his head"; check with `SOCaptureSeries 1 40`'s
`SO_hp_<pitch>_face` pictures, the face close from below looking down and from above looking up; and from UNDER
THE CHIN forward: the chin and jaw sit below the skull's joint and left in the neck's blend they lagged the head and
the face stretched looking up or down, the owner's "the face distorts", 2026-11-21: `rigid_skull(o, z, y)` drops its
line 11 cm toward the front; then the chest's FRONT onto the chest bone, `game.chest_over_clavicle`: the heat weights
gave each clavicle 85-91 % of the upper chest beside the sternum, and with the arms down in the idle the clavicles' turn
folded that band against the neck's, a ledge across the chest from shoulder to shoulder under the suit and a dip on
top of each shoulder; the clavicle keeps the shoulder's top and the chest's side; with it the pectoral's clavicular
head has soft edges, `anatomy.py` `pec_clav` edge 1.6: laid with the sternal head's hard edge its TOP edge was a 5-6 mm
step along the clavicle; measure with the scratch `chest_profile.py` and look at the idle with `suit_look.py`); the undersuit
(`C_suit__orion`, slot `suit`, ALWAYS worn and never armour: the owner, 2026-11-17, "the undersuit is on at all times
and armor goes on top of that"; the body's own mesh offset and cut a hair past the wrists' and ankles' rings, its maps
baked from the lab's detailed suit and collar, `orion_male_suit_*`, its weights copied in the REST pose); the clips
(`hero/male/motion.py`, the approved style, baked by `gait.py` on this skeleton: `gait.Body` takes the body's own foot
points; the knee's IK pole angle is SEARCHED to a tenth of a degree with the leg bent, `gait._calibrate_pole`: tried at
-90 / 0 / 90 / 180 it was 14 degrees out on this skeleton and every clip bowed the knees 18 degrees out, the owner's
"the leg looks bend"; a standing pose raises its hips to a set knee bend, `gait.Body.stand_tall`, the idle 3 degrees:
feet brought in under the body with the hips left at the rest height bent the knees 20; measure with the scratch
checks of the knee plane and the stance, idle knees 22 cm apart, ankles 26); the export (`B_<region>`, `B_eyes`,
`B_lashes`, the suit, `worldex` meta). `export_unreal.sh` runs both into
`SourceArt/Characters/src/orion_male.glb` (delete it to rebuild). **The Orion outfit** built to the owner's sheets on 2026-11-22 was DELETED the same day at their word ("delete the new
player clothing you just made, i don't like it, we will keep the undersuit for now"; a new armour design of theirs
comes; the scripts are in the git history, `tools/blender/hero/orion/outfit*.py`). What it taught stays: `game.py`'s
export writes a worn piece's corner colour `Col` (`export_vertex_color='ACTIVE'`, the body's own colour attributes
dropped first: they would have multiplied the skin), and Unreal's FBX import stores a vertex colour unconverted (byte =
255 x value); `fabric.make(..., linear=True, force=True)` takes a linear colour (its 8-bit maps store sRGB bytes: a
linear .12 grey came out .013) and writes a file again; a cloth takes no scratches from the shared wear mask (white
rain on dark twill); a garment carried out from the suited body is smoothed (Taubin) and held a cloth's ease out, or
the abs and the arm's muscles show through it; a plate spanning the collar and the arm is skinned like the body (rigid
on one bone it stands up like a horn as the arm comes down from the T-pose); a boot over a hidden foot keeps a boot's
shape. The outfit pictures stay: `SOCaptureSeries 1 45` (one exposure for every shot, `-SOOutfitEV=`, 2.2 the range's
daylight; turned to the sun, the views from behind with the back to it; nothing carried, `ASOCharacter::SetEmptyHanded`;
no HUD). In the game every armour slot may be empty
(`USOWardrobeData::IsOptionalSlot`); the skin is `M_SOSkin` (subsurface profile `SP_SOSkin`, `import_assets.skin_material`);
the face rides the outfit (`FSOOutfit::FaceKeys / FaceValues`, kept by the inventory, saves version 7) onto the body's
morph targets (`ASOCharacter::ApplyFace`); console `SOFace <key> <value>` (dev). **The character builder** (the
armoury's CHARACTER tab, 2026-11-21; the owner, 2026-11-16: "the face will be heavily customizable in game when the
player first starts"): `Data/creator.json` (read at runtime, `FSOCreatorData`; `tools/package.sh` stages it) names the
groups (body and skin, hair, brow, eyes, nose, cheeks, mouth, jaw, ears), every slider (a key of the body's
`face_<key>` morph targets, -1..1; a slider shows only on a body that has its morph: the two bodies' faces were built
apart) and the tones offered (linear tints over the body's own maps; the FIRST of each list is the body's own, the
import's `SKIN_DAYLIGHT` / `HAIR_TONE`, which alpha 0 on the outfit means: `ShatteredOrbit.Creator.EveryKeyIsOnABody`
holds them equal). The outfit carries `SkinTone` / `HairTone` (kept by the inventory, saves version 9;
`USOInventoryComponent::SetLook` sets the whole look in one change); `ASOCharacter::ApplyFace` lays them as dynamic
instances on every `MI_skin*` (BaseColorTint, and the Scatter down to a quarter with the tone's depth: the pale skin's
warm scatter made a deep tone glow orange; the brows on `MI_skin_face`'s HairColor at 1.6x the hair) and `MI_hair*`
but the lashes, of the body, the first-person arms and every worn piece (a body or piece that changes mesh drops its
overrides first); a change of the look alone never dresses the body again (`SetOutfit` -> `SetLook`). The tab: the
groups down the left with how many of their sliders are moved, a RANDOM FACE and a RESET ALL (each asked twice), the
group's sliders (`USOCreatorSlider`: dragged, the stand-in follows as it moves and the value is kept when it is let go;
the wheel nudges, a double click puts it back; W / S choose, left / right move by 5, R resets the group) or its tones
(`ESOArmouryControl::Swatch`, the body as `Choice`), and the stand-in close on the face (`USOCharacterPreview::
SetFraming`: 0 the whole body, .5 head and shoulders, 1 the face; the body alone drawn, no gun; turned to show the
group, the ears from the side: `TurnTo`; a portrait's light close up, softer and gentler, its rims ABOVE the head: level
with it they shone through the jaw's edge in the skin's scatter; the picture's sides fade, `M_UI_Stage` Edge). A NEW profile opens the builder by itself at the first start
(`USOInventoryComponent::IsCharacterMade`, false only for a new profile; a save from before version 9 counts as
made; `ASOHUD::DrawHUD`, never in a test, a capture series, the two-player check or an unattended run), and closing the
armoury after it ends the first start. The hair is laid over a face's skin (`HairAmount` 1) ONLY where the face has maps
of its own whose mask's B is the hair (the new male's `skin_face`): the female's head wears the body's map, whose B is
white, and with it her whole face took the brows' colour (`import_assets.player_extra`; the test holds her at 0).
Pictures: set 19's `SO_u10*_creator_*` (her body: `u10j` / `u10k`); tests `ShatteredOrbit.Creator.*`. **Hairstyles and
beards** (the builder's hair group, 2026-11-22; the base face is clean-shaven, the owner, 2026-11-16): a hairstyle is an
item of the wardrobe's HAIR slot (never empty; a sealed helmet hides it), so the male's hair is no longer part of his
body: `game.py --stages=hair` grows every style of `groom.STYLES` (swept, crop, slick: one groom, the top cut and
combed another way, the fade the same; the crop's cards from strands of 9 mm, `cards_min`) as `C_hair__<style>` on
the head bone, and writes the slot into the armature's `worldex` (the import also makes a meshless item of a non-armour
entry with no piece, which the game wears as nothing: a buzz cut was one, dropped because the scalp's short hair drawn
on the face does not read in the game, the head looked shaved, though the map carries it: open); the face's sliders are set on every worn piece too
(`ASOCharacter::ApplyFace`: the hair's roots ride the forehead). A beard is DRAWN, hair by hair, as the brows are:
`--stages=beard` (`beard_maps`, `groom.beard(..., scale=)`) writes `orion_male_skin_face_Beard.png` beside the face's
maps (BC7: three masks, one a channel), R a stubble, G a short boxed beard, B a full trimmed one, each its hairs over a
floor of how densely they grow (`beard_floor`, `BEARD_FLOOR`: hairs alone, thinner than a pixel at a few metres, came
out a faint olive cast); `M_SOSkin` adds `dot(BeardTex, BeardMask)` to the brows' mask under the hair's colour and
turns the subsurface scattering OFF under all hair drawn on the skin (Scatter x (1 - hair): the scattered light washed
the brows out entirely and made a beard olive; with it off the brows show for the first time), and
`ASOCharacter::BeardMask` picks the channel from the outfit's `Beard`. `--stages=masks` writes the face map's hair
channel again (brows and scalp) without baking the skin. The
inventory keeps `HairStyle` and `Beard` (saves version 12; `ServerSetHairStyle` / `ServerSetBeard`); `GetOutfit` puts
the style in the hair slot where the body's wardrobe has it; `Data/creator.json` `"beards"` names the beards and the
bodies whose faces carry them (the male). The tab's hair group: STYLE (the body's hair items, its default first), BEARD,
then the colour. Pictures `SOCaptureSeries 1 46` (files `SO_hb_<style>_<beard>_<yaw>`); test
`ShatteredOrbit.Creator.HairAndBeard`. A gun carried low (a sprint, the
armoury's stand-in: `USOLocomotionAnimInstance::bCarried`) keeps the third-person firing elbow by the side (the arm IK's
swing toward the straightest wrist is held to 0.55 rad there: it stood out level with the shoulder, the owner's "arm
seems very bend out"). `vr_sniper`'s third-person support hand lands 5 cm behind where the first-person arms hold it (the body's
reach clamp), and there it met the fang's blade and the keel's fins: its hand rest now runs back under the receiver's
front and the fang and the keel start ahead of it (requiem_guns.py, 2026-11-22; `TheGunIsSolid` passes on every gun).
The old male builder (`hero/build.py -- male`) is no longer exported: it stays only as the Sarketh's and the Void
Sentinel's base until they move to this body.
**The passes of 2026-11-20** (the owner: "do 10 more passes ... ensure it is not just as good but better ... the body
suit is still too flat"; judged against `art/reference/player/orion_tpose_bodysuit.png`): the BASE face is the
portrait's (`headbase.BASE`: what each slider's key reads when nothing is set; a slider's morph is built from it,
`headcage.FACE_DELTA` its range), the chin's rows wider and squarer (`headbase.MEASURES`); the body is CUT, not
bulky (`anatomy.Muscle.SHOW` up, and `Anatomy.lines`: the separations and the bony ridges DRAWN as valleys a finger
wide along polylines snapped onto the skin itself, deltopectoral, linea semilunaris, the groin, the iliac crest,
the lat's border, the arm's and the thigh's heads, the calf, the shin: written to a centimetre, a line a centimetre
under the skin drew nothing); the suit carries its relief IN THE GAME MESH (`game.make_suit`: each vertex takes the
fine suit's relief at the nearest point; in the normal map alone nothing stood in the silhouette), its fine mesh is
smooth-subdivided (`CATMULL_CLARK`: a SIMPLE cut kept the body's facets and the baked normals carried them as
bands across every plate), the muscles' panels are OFF (`suit.MUSCLE_PANELS`: the sheet's suit is cut in angular
plates and the body shows through), the knee's pad a hexagon, the thigh's plate wide at the hip, a plate down the
shin, cuffs at the wrists and ankles, a stitched channel inside every rim, real ribs in the flex zones, charcoal
base and grey plates at the sheet's contrast, matte woven; the hair (`hair_cards.py`, stage `hair`, a piece of the hair slot per style `C_hair__<style>` (once `B_hair` on the body),
material `hair`): the groom's strands rooted on the game head's own surface (`head_surface`: its vertices alone
gave 5000 roots), the long ones grouped into locks and drawn as cards in two layers (each lock's own line, and the
same lock pressed onto the scalp from the atlas's dense columns), the scalp's short hair drawn into the face map's
hair mask with the brows (`scalp_mask`: the fade is short hair on skin, a floor of hair under the top's cards).
Look at a build close up under a studio light with `hero/orion/bodylook.py` (views per part, `--suit` keeps the
suit) and at the head beside the portrait with `headlab.py --views=portrait,eye,mouth`; the skin's maps and the
game's hair shading are judged IN THE GAME (capture set 37, files `SO_fc_*`: the head from the front, both three
quarters, the side, the eye). Lessons of that: a stage run again on a saved build leaves the old material
datablocks, so the new ones come out `eye.001` / `hair.002` (`game.fresh_material` removes them first, and the
importer looks a material up by its base name: looked up by `eye` it found no maps, a white eye and opaque hair
cards); the game draws a hair card's alpha MASKED (cut at a third), so the atlas needs gaps between its strands
(`hair_atlas(per=(10, 16), coarse=.85)`: a dense column made every card an opaque tile, however it looked in Cycles);
a card's width is in HEAD CM (`build_cards(width=1.0)`; written in metres they were hairlines); `M_SOStandard` has a
`Specular` parameter now (0.5, the engine's default; the undersuit's instance .3: woven fabric, not satin) and the
suit's baked roughness is .86 on the base; `M_SOSkin`'s Scatter is .65 and `SP_SOSkin` has a 0.75 cm radius with warm
scattering colours (the engine's defaults made the face wax in daylight), the caruncle's flush is .5, the skin's base
tone a shade deeper than the lab's first (it read pale under the game's sky), and the import lays a warm tint over the
skin's own maps in daylight (`import_assets.SKIN_DAYLIGHT`, the character builder's first skin tone). The hair's top
stands higher and fuller (`groom.py`: `lift0` .55-.77 at the front, `reach` 1.5-3 cm off the crown: at 1-1.75 it lay
flat against the sheet's swept top) and the fade is drawn SMOOTH and READS (`hair_cards.scalp_mask`: the floor under
the top's cards laid over the head's own triangles, `raster_max`: discs at its vertices showed as a grid of dots
however they were blurred; every short hair a stroke anti-aliased with its nearest texel at full tone: shared out
evenly they drew at half and the sides read as bare skin; and under them a shade of how densely they grow, taken
from the strokes themselves, up to a third: a floor laid by position took the ears too).

The old player bodies, heads, clothing, hair, first-person arms and the scripts that built them (players.py, anatomy.py,
face.py, wardrobe.py, hair.py, skin.py, the old civilians / NPC kits) were deleted on 2026-11-07: the players are
being rebuilt from zero as two separate professional base meshes (male, female): clean quad topology with edge
loops at the eyes, mouth, nose, ears and every joint, real anatomy and proportions (Epic's Manny / MetaHuman may be
measured side by side, never imported), and face customisation (eyes, ears, mouth shape and colour, eye colour and
shape, noses, hair and hair colour, beard or none: the owner, 2026-11-16, "the face will be heavily customizable in
game when the player first starts"; so the head is a neutral base of parameters and the hair, beard and brows are
separate, optional pieces; the base model is CLEAN-SHAVEN, the beard an option of the character builder). Clothing and armour come back later, fitted to the new bodies. Until the new
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
`FSOFingerPose`, `USOLocomotionAnimInstance`). **The hands are FITTED to each gun's own shape** as it is picked up
(`USOLocomotionAnimInstance::FitGrip`, shape queries on the gun's meshes; the owner, 2026-11-15: "hands keep glitching
or bending or wrapping in or they're in the gun ... the gun needs to be a solid object"): the firing hand seated on the
grip's backstrap, the support hand slid along the fore end to where the whole hand has room, a vertical fore grip (a
POST: found by its narrow sections, hanging free) wrapped like a handle with the KNUCKLES at its front (palm level with
its middle, the fingers closed on the air ahead of a thin post), every finger closed joint by joint until it touches,
fingers posed from the REST pose (not on top of the clip's curl). Each THUMB is placed on the gun's surface: of its free
poses (swung, drawn in, partly closed, with a margin), the one whose tip comes nearest its place: the firing thumb round
the back of the grip onto its far side, the support thumb forward along the left of the fore end (taken as the first
free way and closed toward the palm, they stood out under the grip and curled up over the handguard into the sights).
The TRIGGER finger lies on the trigger: the trigger is found on the gun's shape by how THIN it is (probes across the
gun from the grip forward at three heights: the grip is wide, the gap in front of it empty, the blade under a
centimetre with the gap behind it; probes dropped from above read grip, blade and guard as one) and the finger is
posed with its pad on the blade's front face, its first two bones clear, bent as a finger bends (the middle joint
more than the tip), and LIFTED in the palm's plane where the trigger stands higher than the knuckles of the hand round
its grip (`FSOFingerPose::IndexLift`, up to 24 degrees; it is in the hold files as `indexLift`); a trigger finger that
still starts in the gun has the whole firing hand seated 0.75 or 1.5 cm higher, then lower (`FitGripDrop`: the heavy
machine gun's guard ran along the straight finger and its drum stood ahead of it). A fingertip runs on from its last joint the way that bone turns, rest bend included, in the fit
and in `MeasureHold` alike (carried straight on from the middle bone, a bent tip measured as pointing into the gun).
A gun may bring its own hold instead (`Data/holds/<archetype>.json`, `FSOGunHold`: both wrists, hand directions and
every finger; read as the rig is built, nothing fitted; none written yet). Measured by `MeasureHold` (wrist bend, reach,
finger bones in the gun, the palm's gap at its middle and 2.5 cm on); tests `ShatteredOrbit.Hold.*` (`TheGunIsSolid`,
`FittedGrip`; `SOTest::HoldNotYet` lists the guns that still fail, as warnings: only vr_lmg now (its post is out of
reach and the blade plates down its underside's sides meet the palm where the arm does reach: a model change). A
post is wrapped with the hand running along its side (angled 30 % into it, the palm's bones crossed it), and only
where the arm reaches it: the arm's rule slides a support hand back along the gun past 93 % of its reach, off the post
with the fingers still curled for it, so a hand round a post may reach to 98.5 % (`bSupportOnPost`) and the fit takes
a post up to 93 % of the arm (the shoulder is an estimate) and no further. The post is looked for round the fore
point (up to 9 cm behind it and 12 ahead), at a lower height if not at the usual one (`PostUp`), its front and back
probed from 9 cm off and then nearer (a probe begun inside the heavy machine gun's drum read its post 11 cm long), and
a probe that misses is tried again a hair to either side (laid along a mesh edge it slips between two faces: the
ksmg's post was found by one view and not the other on that alone). Elsewhere the support hand is kept within 90 % of
the first-person arm's reach and 87 % of the body's (the body's shoulder is known to five centimetres: at 90 the arm's
own rule slid the hand back off where it was fitted, the Requiem sniper's palm into its fins). Measuring the slide the
arm really needs and fitting again from it was tried and dropped: it fires while the gun is still coming up into the
hands, and moved every rifle's support hand 20 cm back. A gun's own shape can make a grip impossible: the heavy machine gun's drum
reached behind its grip and the Requiem LMG's belt box stood where the fingers wrap; both were moved forward in the
model (weapons.py `heavy_mg`, requiem_guns.py `vr_lmg`)); close-ups `SOCaptureSeries 1 30 -SOGuns=<arch>` (files `SO_k_<gun>_*`).
A CREATURE's head is held on its aim whatever its clip twitches (`bHeadFree` false: the old reset to the rest facing);
a player's body and the armoury's stand-in carry the clip's own head motion under the aim (`bHeadFree`).
**The hands are on the gun in the SAME frame** (the owner, 2026-11-16: "the player hand keeps moving and feels like the
player is not properly gripping the guns"): the engine calls an anim proxy's `PreUpdate` BEFORE `NativeUpdateAnimation`,
so everything the instance worked out (the hand targets, the aim, the blends) reached the pose a frame late and the
hands trailed the gun: about 4 cm and 4 degrees at every shot, a centimetre and a half per frame of a third-person turn,
most of a centimetre walking. `FSOLocomotionProxy::CopyFrom` now runs at the END of `NativeUpdateAnimation` (a scope
guard): never copy an instance's per-frame state in `PreUpdate`. `SOCaptureSeries 1 36 -SOGuns=<arch>` measures it:
every frame, each hand's bone in the gun's own frame as RENDERED (the gun as the frame ends, the bones at the start of
the next: a body's new pose is swapped in only as the frame goes to the renderer), through idle, walk, strafe, turn,
sprint, aim, aim on the move and turning, and firing, both views; `HOLDDRIFT` lines (spread / largest step cm, turn
deg, the elbow's bend) and the fit's report `HOLDFIT`. Held: under 0.05 cm everywhere. **The snug grip** (data
`"snugGrip"` -> `USOWeaponData::bSnugGrip` -> `USOGunRigComponent::IsSnugGrip`; the rifle only until the owner has
judged it: "start with just the ak rifle then after feedback from me we can do the rest"): the fingers brought
together toward the middle finger's line before they close (`FSOFingerPose::Together`, 0.85, `FingersTogether`, in the
fit and the pose alike: a resting hand fans its fingers, and they touched the handguard with their tips), the support
thumb's place at its root's height and close to the side (it stood up beside the handguard from the eye, its tip by
the front sight), and the first-person firing shoulder of a long gun pushed back and out from its hand rather than
down (on the sights the wrist bent 72 degrees, now 64).
**The Sarketh's guns never reload** (the owner, 2026-11-16: "remove loading and keep venting so after we stop shooting
and the counter rests to 0 or after venting we slowly add bullets from reserve to magazine"): a gun with `"refill"`
(seconds for a full load: `USOWeaponData::RefillTime`) condenses its rounds (`ASOWeapon::Condenses`, `IsCondensing`):
the trigger at rest and the crystal cold (or a vent ended), the server moves rounds from the reserve into it at that
rate; the reload key and an empty trigger vent it (`StartVent`, as long as the heat in it asks); the HUD says
CONDENSING. Test `ShatteredOrbit.Weapon.SarkethGunsCondense`. Their models have NO magazine: under a long gun's
receiver a condenser (a faceted amber crystal in pale claws and a forged collar: the rounds condense in it), and every
grip is their own (`sarketh_guns.skr_long_grip`, the handguns' own: dark forged iron on the hand's lines, a pale plate
with a rim of light, a crystal pommel in two claws; no polymer, rubber or base cap: "the new guns handle all look the
human ones"). **Ashen Gate** (`skr_cannon`) is a launcher of its own (`sarketh_guns.skr_launcher`: a wide receiver, a
revolving condenser drum in the open, a fat finned housing, a 5 cm bore; the owner: "more bulky like a grenade
launcher").
**Ember Oath II** (`skr_rifle_v2`, the owner, 2026-11-15: "add it to the game as a variant of the rifle ... so both
exist"): Ember Oath's build and numbers in the blade's mirror-polished stainless on its plates, blades and fittings
(`sarketh_guns._rifle_v2` -> `SKR_FINISH=mirror`; material `gun_steel__mirror`, set `skr/textures.py mirror` =
`skr_mirror`: roughness .05 to .14, the gate needs a map not a value; gunpaint keeps it nearly clean of grime). Its
own shot sounds are the rifle's (`SARKETH["skr_rifle_v2"]`). **The hand cannon** (`skr_handcannon`) was rebuilt on the
owner's word ("design it more like a sci fi" heavy magnum): a full-length slab slide over a fixed barrel, a flat
muzzle face, a grooved rib, an exposed hammer, a hatch with studs, vents, the light in thin seams; its guard keeps
the pistol's line (a squared or hooked guard put the off hand's index finger inside it).
**Every set looks through its own glass** (the owner, 2026-11-15: "the zoomed in screen should be unique to the weapon
set like instead of a black screen it should be unique with the guns theme and the crosshair too"): `ASOHUD::DrawScope`
and the hip crosshair take a theme from the gun (`SOSightTheme::Of`: its `set`, else its class's family): the window's
shape, what stands round it (the set's own body, darker toward the screen's edge, never plain black), its rim, the
glass tinted at its edge, the reticle and the crosshair, all in the palette's glow. Sarketh: a lozenge window in dark
orange lacquer with a gold rim, their emblem in gold round it, an amber lozenge reticle under the brow's chevron
with three dashes either side and the slug's drop as falling chevrons (brighter as the gun heats), a crosshair of four
diagonal ticks. Requiem: a hexagon in violet, three lines closing in. Light guns: a ring of lit segments, a broken
ring and a ruler in cyan. Living guns: a breathing membrane, claws and drops in green. Human guns: the black ring and
red point as before. Pictures: `SOCaptureSeries 1 18 -SOGuns=skr_sniper,sniper,vr_sniper,bolt` (the aimed views).
**Hand to hand** (the owner, 2026-11-15: "mele is when we put away all our guns on our back so we hold nothing but our
fists ... if we have a blade then blade strikes (light and hard strike for everything in mele)"): key 4 (`IA_Fists`;
the mouse wheel and the pad's d-pad reach it past the last gun, a gun's key leaves it) puts every gun on the back
(`ASOCharacter::SetFists`, replicated; `bHeldStowed`); fire is the light chain (each press after the last blow's
`recover` and within the style's `chainGrace` goes on to the next), aim the heavy blow. A style (`fists`, a blade's
archetype id) is data: `Data/game_data.json` "melee" -> `SO_IMPORT_ONLY=melee` -> `/Game/Data/DA_Melee`
(`USOMeleeTable`: guard clip, light blows, heavy blow; each blow's clip, `hit` time into it, `recover`, damage, range
and cone from the eye, force, stagger, the step in, sounds). The server lands it (`USOMeleeLibrary::Land`: the other
side within reach in the cone, not through the world's geometry, through the damage gate); a joined player sees their
own blow at once (`MeleePredicted`). The body: `USOLocomotionAnimInstance::SetMeleeGuard` / `PlayMeleeBlow`, a layer on
the UPPER body (the spine and under it) over the legs' gait, the whole body when standing, the trunk pitched with the
aim; the first-person arms play the same. Clips per body (`hero/<sex>/motion.py`): `FistGuard`, `Jab`, `Cross`, `Hook`,
`Haymaker`, `BladeGuard`, `SlashA`, `SlashB`, `Thrust`, `Cleave` (a hook's upper arm is out at 80 and turned in -80,
or the forearm stands up). Sounds `sfx_synth.py ... melee`. **The Veyr Edge** (`skr_blade`, the owner, 2026-11-15:
approved): `sarketh_guns.veyr_edge` (mirror-polished stainless, a ground edge, a glass window with a filament of light,
a machined handle), exported like a gun to `SourceArt/Weapons/SkrBlade`; the style's `"mesh"` is imported with the gun
pipeline's materials by `SO_IMPORT_ONLY=melee`. A blade is OWNED (`USOInventoryComponent::Blades`, saved: version 5,
replicated); a set cache gives every style of its set (`FSOMeleeStyle::SetId`, `ASOReliquary`). Key 4 goes from the
gun to the first blade owned (or the fists), from a blade to the fists, from the fists back to the gun
(`ASOCharacter::HandleFists`, `SetMeleeStyle`, checked on the server). The blade lies in the right fist of the body and
of the first-person arms from the hand's own bones (`ASOCharacter::BladeInHand`: the handle across the palm, the blade
out of the thumb's side, the edge toward the knuckles). A gun put away stays away whichever view comes up. **Melee like a fighter's** (the owner, 2026-11-16: "make mele combat on par" with
fighting games; our own moves): the stance picks the move (`ASOCharacter::NextMeleeBlow`, `SOMeleeMove`): light, light,
heavy = the finisher (a launcher); light at a sprint = the rush; light crouched = the sweep; heavy crouched = the riser
(a launcher); heavy in the air = the slam (a ring, `Shock`); a body in the air takes 1.2x (a juggle). A blow lands with a
hit-stop (`HitStop`: both bodies' `CustomTimeDilation` for an instant, every machine through `MulticastMeleeImpact`),
sparks, the camera's punch and the HUD's HITS count. The reload key held is the guard (`SetBlocking`: from the front
`BlockScale` gets through, the `Brace` clip held at `BlockHold`); raised within `ParryWindow` of a blow it is a parry
(nothing through, the attacker reels, the next blow within `CounterTime` does `CounterScale`; the HUD's PARRY). All of
it is data per style ("finisher", "rush", "sweep", "riser", "air", "block"). Clips `Uppercut`, `Rising`, `Sweep` (the
sweep plants the swept foot far out with the leg's IK). The loadout has a MELEE slot (`USOInventoryComponent::
MeleeSlot`, saves version 6): a blade owned or, empty, the fists; key 4 brings up what is in it and puts it away.
Tests `ShatteredOrbit.Melee.*`; pictures
`SOCaptureSeries 1 35` (files `SO_me_fp_*`, `SO_me_side_*`).
**Where the gun sits in first person** (`USOViewmodelComponent`; the owner, 2026-11-15: "the guns cover too much of the
screen ... shouldn't be at the center of the screen, better to be on the right ... on running we lower the gun for
rifles ... smaller guns like smg/pistol/revolver/handcannon we take it up"): at rest in the lower right (`HipOffset`,
`HandgunHipOffset`); on a sprint each gun is carried as its data says (`"carry"` in `Data/game_data.json` ->
`USOWeaponData::SprintCarry`, `SO_IMPORT_ONLY=gunnumbers`): `low` (long guns: the low ready, canted, muzzle in and down,
still in the corner of the view; `SprintLow*`), `short` (SMGs: up part of the way, `SprintShort*`; higher, the support
arm crossed the view), `high` (handguns: up by the face, muzzle to the sky, `SprintHigh*`). A gun's length does not
tell (the heavy machine gun is shorter than the SMG). Pictures `SOCaptureSeries 1 32 -SOGuns=<arch>,<arch>` (files
`SO_vm_<gun>_hip` / `_sprint`). **Third person**: the shoulder camera stays over the RIGHT shoulder (`HipSocketOffset`
Y +55): the owner tried it over the left one on 2026-11-15 and asked for it back. Maps: every level has an `ASOMapInfo` + `ASOMapPoint`s (mini-map, map
screen, quick travel). Nexus Prime (the big city, `L_Nexus`): plan `tools/city/nexus_plan.py` -> `Data/nexus_plan.json`,
kit + baked tiles `tools/blender/nexus_city.py`, built at runtime by `ASONexusCity`. Inventory icons:
`tools/blender/icons.py` (the armoury's pictures, below). Sounds: `tools/audio/sfx_synth.py` (numpy + scipy, our own synthesis).
Combat core and abilities (Project Orion phase 1, begun 2026-11-12; plan and state in `docs/orion/ROADMAP.md` and
`docs/orion/reports/PHASE_1.md`). **Damage is decided in one place, `USOAttributeSet::TakeDamage`**: whatever writes
the `IncomingDamage` attribute (a round or a blow through `USOCombatStatics::ApplyDamage`, a burn ticking, an
ability's effect) passes the same gate (the dead, the immune, the victim's `ScaleIncomingDamage`, friendly fire, then
shield before health); `ApplyDamage` returns what the gate let through. Nothing else lowers health. Healing, the
shield's refill, the ultimate's charge, conditions and cooldowns are small C++ GameplayEffects (`SOGameplayEffects.h`)
whose numbers arrive with the application (`SetByCaller.*`): never `SetNumericAttributeBase` on health or shield.
**Conditions**: `USOCombatStatics::ApplyStatus(Source, Target, Status.*, Duration, Magnitude)`: `Status.Burn` (the
total over the duration in half-second ticks; the acid guns use it), `Status.Slow` (scale on the speed: the attribute
`MoveScale`, read by `USOCharacterMovementComponent::GetMaxSpeed` and `ASOEnemy::SetRunning`), `Status.Stagger` (a
creature's brain stops and holds fire; abilities are blocked); a boss resists (`ResistsStatus`). **State tags**
`State.Dead / Aiming / Sprinting / Traversing` (`USOAbilitySystemComponent::SetState`, set by the server and by the
player's own machine each from its own simulation). **Abilities**: `USOGameplayAbility` (`SOCombat/Abilities`) is the
base for players and creatures; a character is given a kit (`USOAbilitySet`: abilities by slot `ESOAbilitySlot`
(grenade, melee, class, movement, ultimate) with their numbers) by `ASOCombatCharacter::GrantAbilitySet`, uses one with
`ActivateSlot`, and the HUD reads `GetAbilityState`. An ability's numbers are its grant's, never values in the class.
Every use puts one cooldown effect tagged `Cooldown.<Slot>` on the user; the ability can be used while fewer are
running than the grant has charges (each charge comes back on its own clock); `UltimateCost` comes off the `Ultimate`
attribute, which the kit charges per second, per point of damage dealt and per kill. What a use looks and sounds
like goes through `ASOCombatCharacter::ShowAbility` -> `OnAbilityUsed` (every machine, once), which calls the ability
class's `Show(User, Grant)` (no state: it runs on the class's default object). The abilities so far: `USOAbility_Strike`
(a blow in a cone: damage, knock, stagger), `USOAbility_Grenade` (a thrown charge on the projectile subsystem: bursts on
what it hits, splash, slows; a round can now leave a condition: `FSOProjectile::Status`), `USOAbility_Guard`
(`Status.Guard`: the attribute `DamageTaken` scales all damage in the gate, and no stagger meanwhile; worn armour will
feed the same attribute), `USOAbility_Slam` (the strike all round, shown as a burst). The first kit, Vanguard (a
working name), has all four. What they look and sound like: their own sounds (`sfx_synth.py ... abilities`:
`ability_throw / _charge_burst / _strike / _brace / _slam`, named in the kit's data as each grant's `sound`; import
with `SO_IMPORT_ONLY=audio SO_AUDIO_ONLY=ability_`), effects of their own in `USOFxSubsystem` (`Shockwave`: a ring
racing out along the ground, used by the slam and under the charge's burst; `Sweep`: an arc across the strike's
cone; `Ward`: lines of light rising round a body, the brace), and for the player who used it the gun dropping away
and coming back with a pitch of the view. **Each body has its own clips for the four** (`hero/<sex>/motion.py`:
`Throw`, `Strike`, `Brace`, `Slam`; a grant names its clip in `Clip`, data `"clip"`): the clip starts with the
wind-up, so the wind-up in the data is the time into the clip at which the blow lands (throw 0.2 s, strike 0.16,
slam 0.34); it is the whole body with its feet planted, so it plays only when the player is standing or nearly
(`ASOCharacter::BeginAbilityShow`: on the move the legs keep their gait and no clip plays: there is no upper-body
layer yet), and while it plays the gun is put away as on a traversal (`bHeldStowed`) and cannot fire. Look at clips
before importing: `reclip.py ... --frames=<dir> --clips=Throw,Strike,Brace,Slam` then
`scratchpad/sheet.py` (a contact sheet per clip); import with `SO_IMPORT_ONLY=player_clips`. In these clips a
positive `turn` of the upper arm opens it OUTWARD on both bodies (the brace needs -70).
The HUD shows conditions: a frame of light and a tag while braced, tags for burning / slowed / staggered, a pip per
condition under a hurt creature's health bar. Pictures: `SOCaptureSeries 1 20` (files `SO_w1` to `SO_w6`). An ability may have a **wind-up** (the grant's
`WindUp`: paid for at once, shown winding up (`OnAbilityWindUp`, the class's `Telegraph`), done when the time is up
unless its user was staggered or killed meanwhile; `IsAbilityActive(Slot)` is true in between): the warning a target
gets. **A creature's own moves are abilities too**: `ASOEnemy::KitId` names its kit (given on the server as it enters
play), the species decides WHEN (`ThinkCombat` -> `ActivateSlot`), the kit says WHAT; its abilities' damage takes the
variant's scale (`GetAbilityDamageScale`) and its light the Altered's violet (`GetAbilityColor`). The Bulwark's ground
slam (kit `bulwark`, slot Class) and the Veilborn's void bolt (kit `veilborn`, slot Grenade, `USOAbility_Bolt` in SOAI:
it goes at the user's `SetAbilityTarget`) are done, and the Colossus's with the boss framework (below).
A kit also has ONE passive rule (`USOAbilitySet::PassiveName`, data `"passive"`): the Vanguard's Close Quarters gives
25 shield back at once for a kill within 12 m (`CloseRange` / `CloseKillShield`, `ASOCombatCharacter::OnDealtDamage`).
A joined player's own shots show as the trigger breaks (`ASOWeapon::PredictShot`: the same fire clock beside the
server's, effects only; the server's echo is skipped on that machine). On a pad the two shoulders are grenade and
melee, both together the ultimate (`ASOCharacter::HandlePadShoulder`: a shoulder alone waits `PadChordWindow`), D-pad
up the class ability. A strike's "not through a wall" check looks for the world's static geometry only (a visibility
trace was stopped by the player's own gun when the target was low and close).
**What the server triggers reaches everyone** through `USOCue::Sound` / `USOCue::Blast` (`SOCue.h`: alone it plays
here, on a server it goes to every machine through the world's relay, on a joined player's machine it does nothing
because the server's call arrives): creature code uses them, never `USOSoundLibrary::PlayAt` or `Fx->Blast` directly.
A hit is confirmed on the shooter's own machine (`ASOCombatCharacter::ConfirmHit` -> `OnHitConfirmed`, which the HUD's
hit marker listens to: rounds fly on the server only). **Saving** goes through `USOProfileStore` (a game-instance
subsystem, the one place that reads or writes a profile; an online service takes its place later): `Commit` serialises
at once and writes off the game thread, one write at a time, the latest wins, by way of `.tmp` with the file in
place kept as `.bak`; what is written is sealed (tag, length, checksum) because the engine's save reader ASSERTS on a
damaged file, so a file reaches it only when the seal checks out and otherwise the backup is used; saves from before
the seal still load; every load is migrated to `USOSaveGame::CurrentVersion` (raise it with every change to what is
saved and teach `USOProfileStore::Migrate` the step). Things a player can use add themselves to `USOInteractables`
(the search for the one in front of a player no longer walks every actor). Only the host may travel the server to another area (`ServerTravelToArea`). In a test, a
controller made by hand must be told it is local (`SetAsLocalPlayerController`), or the engine sends its ability use
to a client that is not there and reports success. Kits are data:
`Data/game_data.json` "kits" -> `SO_IMPORT_ONLY=kits` -> `/Game/Abilities/DA_Kit_<Id>`; the ability classes are
listed in `import_assets.ABILITY_CLASSES`. The player's kit lives on the player state (`USOKitComponent`: the kit's
id, and the ultimate's charge between one body and the next); the ability system stays on the body, so a new body's
cooldowns start over. Input: `IA_Grenade` (G / right shoulder), `IA_Melee` (V / left shoulder), `IA_ClassAbility` (Q),
`IA_Ultimate` (X); the last two have no pad button yet. Aiming is known to the server (`bAiming` from the movement's
aim flag, replicated to the others). Tests `ShatteredOrbit.Ability.*`, `ShatteredOrbit.Status.*`.
**Developer tools are not in a shipping build**: the screenshot series, the benchmark and the two-player check live in
`ShatteredOrbit/Private/SOPlayerControllerDev.cpp`, whose functions are empty bodies under `UE_BUILD_SHIPPING` (the
Exec declarations stay: the header tool knows nothing of build configurations), and the area console commands
(`SOAreas`, `SOTravel`, `SOCensus`, `SOAreaTour`) are compiled out the same way. New developer code goes there.
**Two players** are checked with `bash tools/netcheck.sh`: it starts a host (the range with `?listen`) and a guest
that joins it, both from the editor's binaries, and prints what each side logged (capture sets 21 and 22, started by
`-SONetCheck=host|join` because a machine that is still joining cannot be given a console command). The automation
tests run one world: anything about joined players is looked at this way.
**A packaged game** (`bash tools/package.sh`; the owner, 2026-11-12: do NOT package after every phase or change, it
wastes time: package at the final phase or when asked, and check work with the editor build, the tests and the
capture sets run from the editor): no code reads a loose file except through `SOData` (`SOCore`): in
development from the project's `Data/`, in a package from `Content/Staged/Data`, where the script copies what the
game reads at runtime. All of `/Game` is cooked (assets are found by name). The automation tests are editor-only
(`WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR`). In a `.cpp` the file's own header is included first (the package's
build checks it).
Operations (`SOOperation` module): `ASOOperation` runs a level as stages (travel / clear / hold / boss) with waves,
spawn groups, checkpoints (the game mode respawns there) and boss adds keyed to the boss's health, read from a plan json;
`ASOOperationBarrier` energy walls keep the route linear until their stage; finishing grants every player ONE random
piece of the reward sets (`AddArmorPiece` for armour: wardrobe items with a `Set` are earned, never handed out).
HUD: objective panel, stage banner, goal marker, boss bar, end screen. Tests `ShatteredOrbit.Operation.*`.
**The HUD** (`SOUI/SOHUD.*`, drawn on the canvas; rebuilt 2026-11-20 on the owner's two reference screens,
`art/reference/ui/hud_1.webp` / `hud_2.webp`: "i need a new hud, images one and 2 show what we need"; they are AI
pictures, the LAYOUT and the FEEL are the target, every word and glyph in them is theirs and never used: ours come
from `Data/game_data.json` and the code's own data). It is the armoury's look (night-blue glass, cyan lines, gold for
what matters) drawn as GEOMETRY: `SOHUDPaint.h` batches vertex-coloured triangles (`FPainter`: plates with cut
corners, hexagons, diamonds, rings, sweeps, glowing lines, a textured disc) and `FType` draws every string through Slate's font cache AT THE SIZE IT IS DRAWN (`FSlateFontInfo` on the canvas item,
the engine's runtime-cached Roboto as the item's font object: without one the canvas draws nothing, and an offline
font ignores the Slate info): a size is a face in pixels at scale 1 (Small 10, Medium 12, Large 20 bold), crisp at
any scale and resolution. Before, the engine's bitmap Roboto and its distance-field face were scaled as pictures
and the magazine's count was soft and pixelated (the owner, 2026-11-21: "the numbers are blurry"). No UI material is involved (a UI-domain material does not
draw on a canvas). **Round 2** (the owner, 2026-11-21: "the hud still looks flat, it needs more depth, more definition,
more volume, more reason and now the icons are too big and obstructing the player view"): every `Panel` casts a
shadow (`Shadow`: two soft steps down), its body is lit from above, a dark line runs a step inside its edge and a
line of light along its top (`Bevel`: the edges that run near level across the top); a `Bar` has a trough darker
at its floor, a fill lit from above with a gloss and a bright head; the cells, the diamonds and the minimap's bezel
take the same (`Shadow` + `Bevel`); the held gun's count stands in its own darker well with ROUNDS / RESERVE under
it, and the vitals' bars lie on a plate of their own. Everything is smaller and out of the middle: the minimap 84
px, the weapon panel 330 x 98 with 86 x 38 cards, the abilities' cells 22, the ultimate 30, the emblem 42, the bars
250 wide. **Round 3** (the owner, 2026-11-21: "the hud still looks too bland too indie ... a triple a hud worthy of our
world ... everything must be very crisp like 4k with no pixilation or blurry parts"): every shape is GLASS drawn by
one material, `/Game/UI/M_HUDGlass` (`import_assets.hud_glass`, `SO_IMPORT_ONLY=ui`): a SURFACE-domain, unlit,
translucent material (a UI-domain one does not draw on a canvas) whose whole picture is one Custom node working in
PIXELS as a signed distance (a plate with two or four cut corners, a hexagon point-up / flat-top, a diamond, a ring /
arc, a disc, a bar), so its edge is anti-aliased at any size and resolution, with its shadow, its body lit from above,
an INNER GLOW in a colour of its own (the kit's light in the emblem and a ready cell, the rarity's in the weapon panel
and a new item's card, a condition's in its cell, red for the boss, the elite and the downed screen, gold for the
objective, the ultimate and a level reached), a line of light along its top, dark at its foot, its edge, and for a bar
its fill (lit, with a bright head) in a trough, in segments (the shield in five, the ultimate's meter in ten).
`SOHudPaint::FGlass` draws them (`ASOHUD::MakeGlass(P, S)`: one dynamic instance per shape per frame from a pool,
`K2_DrawMaterial`; `FGlassStyle` the colours and amounts; without the material it falls back to the flat shapes).
`FType` has FACES (`EFace`: Light, Medium, Bold, Cond = the engine's BoldCondensed, Black): `Label` = tracked
condensed caps (every heading and key), `Number` = the light face (every count: the magazine, the vitals, the
heading, the power), names in Medium. The magazine's well has a tick for every round (up to 40), an ability cooling
down a ring filling round its cell, the ultimate's diamond fills from its foot, the compass sits on a tinted strip,
the mini-map on a dish with 36 ticks. Checked at 3840 x 2160 (`-ResX=3840 -ResY=2160 -ForceRes`): type, shapes and
ticks crisp; the mini-map's picture is the area's own capture (`ASOMapInfo`: a texel of about half a metre, 1024 to
2048 by the area's size). **Round 4** (the owner, 2026-11-21, their two reference screens again with a written
brief: "it should pretty much look exactly like the image"; "CRITICAL: fix all text, number and image overlapping ...
zero visible overlaps"): the HUD is the reference's: the mini-map a dark radar dish (72 px) with a thin lit cyan rim,
the few nearest markers and `N` alone above it; the compass a slim scale (no strip) with a gold diamond on its middle,
the goal and the places as marks on the line; the conditions square cells with the time as m:ss and no word; the
vitals with nothing behind the bars (the emblem a diamond with a cyan rim, SHIELD cyan and HEALTH a muted red with a
mark and a word above each and the number at its end, the level a gold badge under the emblem); the abilities three
hex cells a fifth bigger with a key badge under each, the cooling seconds in the cell and its ring round it, the
ultimate a gold diamond between two bars filling OUTWARD from it (`FGlass::Bar(..., FillAxis)`: 3 = from the right)
with its share or ULTIMATE READY under it and its key at the right; the weapon panel cut into REGIONS
(`SOHudPaint::FRegion`: the picture's column at the right under the power, the name's row, the kind's row, the
count's room, a heat row when the gun has heat), the name and the kind FITTED to their rows (`FType::Fit` /
`FitLabel`: shrunk, then cut with an ellipsis), the magazine and the reserve shrunk together until they fit, the three
cards each with its number in a column of its own. Damage numbers: plain white, on a shield cyan-blue, precise pale
gold, critical gold with CRIT; each is laid, the first time it is drawn, where the WHOLE of its rise is clear of the
others and of the screen the fixed elements and the creatures' plates hold (`ASOHUD::Reserve`: this frame's and
last frame's), and keeps that lane; the rewards each on their own side (xp right of the crosshair, credits and alloy
left) in lanes by birth. The glass is graphite (`FGlassStyle` defaults). **Every element is adjustable on its own**:
`FSOHudElementLayout` (offset in px at 1080 lines, scale, visible) per element on the HUD (`MinimapLayout` ...),
drawn through `DrawElement` (the canvas translated with it, `FCanvas::PushRelativeTransform`; its sizes scaled by its
own S); console `SOHudLayout <element> <dx> <dy> [scale]` / `reset`. **The layout audit** (`SOHudPaint::FHudAudit`;
console `SOHudAudit 1`, or `-SOHudAudit` on the command line; the capture series runs with it): every string,
picture and piece of glass notes its rectangle and element, and at the frame's end the pairs that may not overlap
are logged as `HUDOVERLAP` (text on text, text or a picture on a picture, a word on a bar, anything crossing a
panel's or a cell's edge; what a container holds whole is by design); a loot beam's word is not drawn where it would
lie on reserved screen or in the crosshair's band. Set 38 has `hud_24_long_name` (`ASOHUD::SetDebugWeapon`),
`hud_25_big_count`, `hud_26_many_numbers` (eight kinds at once with the rewards), `hud_27/28_slot_2/3`; it is run at
1920x1080, 2560x1440 and 3440x1440 (`Saved/Screenshots/hud1080|hud1440|hudwide`) to zero overlaps. **Round 5** (the owner's queued HUD ideas, 2026-11-22): the elements COME IN (`ASOHUD::ArriveAll`: from beyond their own edges a moment apart, an ease out with a small overshoot, as a new body is taken and as the armoury or the map closes; `Arrive`: a short way again when what one shows changes, the held gun's uid, the stage; an element whose turn has not come is not drawn, and one on its way is muted in the audit, `FHudAudit::bSuppress`); a RING round the crosshair points where a blow came from (`ASOCombatCharacter::OnDamagedFrom` on the player's own machine, `ClientDamagedFrom` to a joined one: back along the round's or the blow's own path where the hit scope knows it, else the one behind it; its own blast tells it nothing; shield blue or the body's red, wider the harder, fading in 1.6 s; `ASOHUD::HitRingAngle`); every FAMILY of the plain sets has its own reticle (`DrawCrosshair`'s default: a rifle's four ticks, a marksman's three and a point, a sniper's or a charge gun's point in a fine ring, an SMG's crossed ticks, a handgun's chevron, a shotgun's ring on its cone, a machine gun's brackets, a launcher's ring with its drop; the sets' own glass keeps theirs); the QUICK-USE key (`IA_QuickUse`: H, the pad's d-pad down, the map moved to the pad's Menu button; `ASOCharacter::QuickUse / NextQuickUse / GetQuickUse`: tapped, the chosen consumable is used if it would do something, held 0.35 s the next one held is chosen) with its slot under the weapon panel (the item's picture, how many, its key; cyan as it is used, red refused); RELOAD under the crosshair is drawn there, not in the weapon panel (`DrawEmptyWord`: it slid with the panel). Pictures `hud_29_hit_ring`, `hud_30/31_quick_use(_refused)`, `hud_32_arriving`, `hud_33_reticle_<gun>` in set 38; tests `ShatteredOrbit.Hud.*`. Layout: `FLayout` (scale = height / 1080; wider than 2200 units the corners keep to a 2200 frame
in the middle, the armoury's rule; checked at 2560 x 1080). Top left the round mini-map (`ASOMapInfo`'s picture cut to a
disc, north up, the look cone, map points, the operation's goal held at the rim, creatures this side knows of in red,
the area's name and the nearest map point or the stage under it); top centre the compass strip (N / E / S / W, the
goal's bearing in gold, map points) and, in an operation, the objective banner (the stage's objective, its count /
clock / distance / the boss's health, a gold bar); top right the conditions on the player as hexagons with their
timers (`ASOCombatCharacter::GetStatusTimeLeft`), the TRACKED panel (the stage before, this one, the next, from
`ASOOperation::Stages`), the NEW ITEM card (a gun that came in: `USOInventoryComponent::OnFeedItem` / `FSOFeedItem`,
with the armoury's icon, the rarity · class · kind line) and the feed; over a hurt or aimed-at creature its level
(the player's level x its variant's damage scale), name and bar; bottom left the kit's emblem (the broken orbit) with
SHIELD and HEALTH, the kit's name, the level and its xp; bottom centre the abilities as hexagons (G V Q), the cooldown
a sweep with the seconds, a gold pulse as one comes ready, the ultimate a diamond that fills, its meter and ULTIMATE
READY; bottom right the three weapon cards (icons), the held gun's panel (name, rarity · class · kind, magazine big,
reserve, power, its picture, the Sarketh heat gauge with VENTING / CONDENSING, the reload along its foot) and under
it the grenade's charges, the melee style and F. Feedback: damage numbers at the hit (`FSOHitReport` travels with
`ConfirmHit` from the projectile subsystem and a melee blow: white, on a shield blue, precise yellow, critical orange
with CRIT = a weak point worth more than the head or the precise shot that ended it; pellets of one shot add up), the
crosshair's four states (tight, open on the move, closed to a point aimed over the shoulder, red with brackets on a
hostile under the eye's line: `Locked`), loot beams by rarity over every core in view (the FX subsystem's streaks
are the world's part), the screen's edge (shield hit: hexagon cells in blue; the body hit: red; low health: a red
pulse; braced: the kit's light; an ability or the ultimate coming ready: gold). Kept as they were: every set's scope
glass, the boss bar (restyled under the banner), the melee counters, the operation's banners and end screen (gold,
not the species' violet), the AI debug view. Pictures `SOCaptureSeries 1 38` (`SOPlayerControllerHudDev.cpp`, files
`SO_hud_01..19_*`: idle, moving, aiming, locked, hits, the number kinds, shield hit, health hit, low health, the
ability cooling and ready, loot beams, new item, the ultimate's pulse and ready, conditions, flashlight, fists, third
person); run it in the range and on `/Game/Maps/L_Meridian` (the objective banner and tracked panel are only there),
from Git Bash with `MSYS_NO_PATHCONV=1` (it turns `/Game/...` into a Windows path).
**The loop's beats reach the screen** (the owner's game loop, `docs/orion/GAME_LOOP.md`: "every 15-30 seconds the
player should get: kill, loot, xp, level, objective update, explosion, ability ready, new enemy, damage numbers";
the gameplay pass of 2026-11-21). The inventory tells its owner's machine what came in (`USOInventoryComponent::
OnReward` from `AddXp` / `AddCredits` / `AddAlloy` through `Reward`, `OnLevelUp` from `AddXp`; a joined player's
come by `ClientReward` / `ClientLevelUp`, as the feed does) and the HUD draws them: a reward pops up by the crosshair
(`DrawRewards`: +xp in gold, credits in cyan, alloy dim; one kind within a moment adds up into one number with a bump;
the sound `reward_xp`), the level bar's fill is EASED toward the real one so a kill is seen to fill it, and a level
reached runs it to the end with a flare and starts it again; the level-up moment (`DrawLevelUp`: a line of gold
opening out from the middle under LEVEL N, what gear may now be raised to, gold at the screen's edge, the sound
`level_up`); a kill confirmed bursts a ring out of the marker and kills within 4 s of each other count up beside it
(`KillStreak`, "x3"); an ELITE (a creature a level's variant gave a name of its own: `ASOEnemy::IsElite`, replicated)
is announced the first time it is in view (`DrawEliteIntro`: a plate under the compass with its name and level, red
marks either side, the sound `elite_seen`; `Introduced` remembers which). Sounds `sfx_synth.py ... loop`, import
`SO_IMPORT_ONLY=audio SO_AUDIO_ONLY=reward_,level_up,elite_`. Pictures `hud_20_kill_paid`, `hud_21/22_level_up`,
`hud_23_elite_seen` in set 38; test `ShatteredOrbit.Loop.AKillPaysOnScreen`. Still to do of the owner's brief: the
rest of the effect system (`art/reference/effects/effects_guide.webp`: `docs/orion/reports/EFFECTS.md`); the armoury
and the inventory of collected items (`art/reference/ui/armoury_arsenal.webp`) are done (below).
**The effect system** (the owner's guide, `art/reference/effects/effects_guide.webp`: "our effects are dull and one
dimensional"; what of it exists is `docs/orion/reports/EFFECTS.md`, keep it honest; first pass 2026-11-21). Everything
is `USOFxSubsystem` (pooled CPU particles on instanced cards: glow, streak, star, smoke, and the hexagonal CELL
`MI_FxCell`, shape mode 4 of `M_SOFx`). What a round hits is read from the hit's own names (`USOFxSubsystem::SurfaceOf`:
physical material, material, component, actor: concrete / metal / dirt / grass / wood / water; the floor's footsteps
read the same rule, `ASOCharacter::GetFloorSurface`) and the impact takes its look and sound from it (`Impact(...,
Surface)`: metal sparks and ricochets `impact_metal`, concrete dust and chips `impact_hard`, dirt a clod `impact_dirt`,
wood splinters `impact_wood`, water a splash `impact_water`; bullet holes only where one stays). The muzzle flash is
shaped by the kind of gun (`EFlash` Rifle / Short / Long / Shotgun / Heavy / Launcher, from the archetype's name in
`ASOWeapon`). A kinetic gun throws its CASING from the ejection port found on its own bounds (`Casing`; a particle
with `FloorZ` / `Bounce` lands and comes to rest). A hit on a body shows its KIND on the shooter's machine
(`ASOCombatCharacter::ShowHitKind` from the hit's confirmation, `FSOHitReport::bShieldBroken` new): a shield's cells
lit round the point, thrown off when it breaks, a critical's flare with lines, a weak point's gold burst and ring
(`HitKind`). A fire blast throws debris that lands, embers, a column of smoke, scorches the ground, races its shock
out along it and leaves a `Burn` (tongues of flame = the torn-blade card standing up, embers, smoke, for 2-4 s); a
zap steps arcs out in jagged chains. Sounds `sfx_synth.py ... impacts`, import `SO_IMPORT_ONLY=fx,audio
SO_AUDIO_ONLY=impact_metal,impact_dirt,impact_wood,impact_water,shield_hit`. Pictures `SOCaptureSeries 1 41` (files
`SO_fx_*`: time nearly stopped for each still); tests `ShatteredOrbit.Fx.*`. **Pass 2** (the owner, 2026-11-21: "the explosion sometimes comes before the rocket even hits the ground and it's just
like spikes coming out of the ground instead of a large explosion with a large blast radius"): a `Blast(Fire)` is a
white-hot flash the size of the blast, a fireball rolling up and out to its radius (soft cards and torn tongues),
black smoke boiling after it, a ring of dust racing out along the ground, debris and embers to the edge, a column
of smoke for seconds, the scorch, the shock, and fire left burning; NOTHING of it before the round lands (a burn's
Age runs from -Delay and it emits only from 0: the fire had started under the rocket in flight); the fire is licks
(streak cards standing up, short-lived and many, orange going red, a glow at the root, an ember bed) not spikes; a
blast that lands knocks the local player's view (`USOFxSubsystem::OnBlast` at the moment it lands ->
`ASOCharacter::OnBlastNearby`: `BlastShakeRoll`, `BlastPunch`, out to five radii) and pulses fire at the screen's
edge. Lessons: a spark's streak is its speed x 0.025 s capped at 42 cm (at 60 they were rays); dust must be nearly
opaque and large to be seen at 2.5 m; a flame is a tongue, never a dot, and never a tall bright blade; a blast's
light scales with the root of its radius (squared, a rocket flooded the range); a capture that fires must EQUIP the
gun it means (the profile's held gun was a rocket launcher, and the HUD capture's burst at a creature seven metres
off killed the player).
**Pass 3** (2026-11-22, the rest of the guide; `docs/orion/reports/EFFECTS.md`): things in the world that explode
(`ASOExplosive`: fuel drum, gas bottle, Sarketh crystal cell, wrecked car; our models `tools/blender/explosives.py` +
`explosive_maps.py`, `SO_IMPORT_ONLY=explosives`, sounds `sfx_synth.py ... explosives`): hurt like a body through
`ApplyDamage` / `ApplySplash`, lit past half (a burning leak) and gone a moment later, a blast sets the next off, the
splash is the shooter's, a wreck is thrown up and burns; an operation's plan puts them down by its fights
(`"explosives"`, `ASOOperation::SpawnExplosives`: a level place on its group's ground clear of every spawn point,
seeded by the group's name), the range has its own (`make_test_map.py`). The top rarity, Sovereign, signs its shots
in gold (`ASOWeapon::IsSovereign`, `USOFxSubsystem::SovereignFlash / SovereignTrail / SovereignMark`). Rain lands
(`USOWeatherSubsystem`: crowns of beads and drops round the eye, none under a roof; a storm's sheets of rain). The
cost is measured (`SOFxStats`; a full pool gives way in O(1)). Tests `ShatteredOrbit.Fx.ExplosivesGoOff`,
`ExplosivesChain`, `SovereignSignature`; pictures `SOCaptureSeries 1 43` (range, files `SO_fx3_*`) and `44` (on
`/Game/Maps/L_Meridian`: its props and its storm).
**The armoury** (I / Tab: `USOInventoryWidget`, C++ only; rebuilt 2026-11-16 on the owner's word: "upgrade it ready
for a triple a game release on steam"; ORGANISED on 2026-11-21 on their reference screen
`art/reference/ui/armoury_arsenal.webp`, "how to better organize weapons and other things we need like an inventory to
hold items we collect": its layout and feel, every word and glyph ours). Along the top the banner (emblem, name, level
and its bar; credits, alloy, vault, power) with the TABS between: LOADOUT · ARSENAL · ARMOUR · INVENTORY (Q / E, the
triggers; a gold mark where something new waits; a row of their own under the banner when the screen is too narrow);
the body (MALE / FEMALE) and the drag's hint at the foot's left, what the keys do at its right. LOADOUT: the backdrop
(`M_UI_Backdrop`), the character large on a lit platform (`M_UI_Floor`) holding the gun low
(`ASOCharacter::SetDisplayCarry`); left the four weapon cards (each with the gun's own render in its rarity's light, the
words in a column of their own: nothing on the picture), right the seven armour cards, the six attributes beside the
stage; a hovered card opens its quick look beside it (`PeekSlot`). ARSENAL (a weapon slot or MELEE), ARMOUR (a slot),
INVENTORY (the collected items): left the view's name and line, the arsenal's four slot TILES (what is carried in
each; A / D, the bumpers), then the CATEGORIES with their counts (every family of the slot, then every ORIGIN: The
Institute, Nexus Prime, Sarketh, Void Requiem, Grown; the armour's seven slots; the kinds of item: materials,
consumables, keys, relics); in the middle a GRID of cards (`ESOTileStyle::Cell`: the marks, the picture, power and its
difference against the one carried, the name; a collected item its count) under a head with the category's name, the
SORT (power / rarity / newest / name, Z; collected items: their own order first), the GRID / LIST views (V) and the
count, PAGES (the wheel over the grid, [ / ], PgUp / PgDn; the choice turns them); the stand-in between the grid and
the panel holding, raising or wearing what is chosen; right the INSPECT panel: rarity · class · kind, the name, the
origin · family in gold, the line, the gun LARGE, power and how far a level lets it be raised, the STATS beside the
PERKS, the TRAIT in a plate of gold; DETAILS (F) for every number against the carried gun and the perks' spine; the
actions EQUIP (Enter) · DETAILS · LOCK (R) · DISMANTLE (X, twice: what it gives is shown) · RAISE (U) with what it
takes (credits, alloy, the materials, each red where short). Hold C (the pad's L3): the chosen gun against the one
carried in its slot, side by side over the grid. A collected item's panel: what it is, its line, its picture large,
how many are held of how many, what it is for (a material: how many of the guns and pieces owned take it), where it
comes from; a consumable is USED (Enter; only when it would do something). The pad: LT / RT the tabs, LB / RB the
slot, A equip / use, B back, X dismantle, Y raise, R3 details, Menu lock, L3 compare. Every control is a
`USOArmouryButton` (`ESOArmouryControl`: tab, slot tile, row, page, tool) and every button a `USOQuietButton` (never
focused: the screen keeps the focus). The layout follows the width (`UpdateLayout`): a 2200 frame in the middle of an
ultrawide; the grid three columns under 1500 units inside the frame, the panel 440-520 wide, the attribute column
gone under 1650. **The stand-in is a picture, never a body in play** (`ASOCombatCharacter::SetDisplayOnly`; test
`ShatteredOrbit.Combat.TheArmouryModelIsOnlyAPicture`); it TURNS WHOLE on its turntable (a drag, a flick, the right
stick) and its head carries the clip's own motion under the aim. Every card is `M_UI_Card`, every shape its own
material (`M_UI_StatBar`, `M_UI_Hex`, `M_UI_Glyph`: 0 emblem, 1 credits, 2 alloy, 3 vault, 4 power, 5-10 the
attributes, 11 fists, 12 lock, 13 blade; the panels `M_UI_Plate`), one Custom node each drawn from the UV derivatives
(`import_assets.ui_shape`, `SO_IMPORT_ONLY=ui`). **A UI material's colour is LINEAR** (a "dark" 0.03 is a mid grey:
glass is 0.003-0.02, the text greys 0.2-0.6). **Words that must stay in their box are cut with an ellipsis** (`Fit`:
the overflow policy AND clipping to its bounds: Slate draws the ellipsis only where the words are clipped; and a
button's slot pads its content 4 px a side unless told not to). The words are data (`Data/game_data.json`): every
archetype's `"lore"`, `"family"`, `"origin"`, `"traits"`, `"classNames"`, `"families"`, `"origins"`;
`import_assets.gun_words` puts them on `USOWeaponData` (`Lore / ClassName / TraitName / TraitText / Family / Origin`,
with the guns and `SO_IMPORT_ONLY=gunnumbers`). The pictures: `tools/blender/icons.py` renders each gun 1024 x 512
(`frame_persp`), each armour piece 512 x 512, and each collected item 512 x 512 (`goods`, from `tools/blender/goods.py`:
our own models in their maker's look, pictures only, never in the world); `SO_IMPORT_ONLY=icons` (guns, armour) and
`SO_IMPORT_ONLY=goods` (the items and their pictures, `/Game/UI/Goods/T_Goods_<id>`). **The layout audit** (as the
HUD's: `-SOHudAudit`, `USOInventoryWidget::SetAudit`): every word, picture, button and plate on the screen as drawn
(render transforms, a scroll's clip) against every other: `ARMOURYOVERLAP` (words or pictures that cross, anything
across a button's or a plate's edge; what a frame holds whole is by design), `ARMOURYCLIP` (words given less room than
they need and not cut with an ellipsis). Pictures `SOCaptureSeries 1 19` (files `SO_u1_loadout` .. `SO_u9d_materials`:
the loadout, the pad's highlight, quick looks, the primary slot by family, by origin, by rarity, as a list, the next
card, the details, the comparison, special, heavy, melee, head, the inventory and its consumables, relics, materials,
the player dying with the armoury open; the profile is not saved meanwhile and one of every item is handed out), run
at 1920 x 1080, 2560 x 1440 and 3440 x 1440 with `-SOHudAudit` to zero crossings.
**Collected items** (the goods: the owner's "an inventory to hold items we collect"; `Data/game_data.json` "goods" ->
`USOLootTables::Goods`, `SO_IMPORT_ONLY=goods`): fourteen in four kinds (`ESOGoodsKind`): MATERIALS (Amber Condensate,
Machined Parts, Brood Resin, Forged Plate, Void Crystal), CONSUMABLES (Field Stim, Shield Cell, Overcharge: a share of
full health / shield / ultimate back at once), a KEY (the Sarketh Command Core) and RELICS (one of each named creature
of Meridian Fall). The inventory holds them (`USOInventoryComponent::Goods`, `FSOGoodsStack`: replicated to its owner,
saved: version 8, a profile from before starts with `"starterGoods"`; `AddGoods` up to the item's stack, `TakeGoods`
all or nothing, `UseGoods` on its body, `ServerUseGoods`, `MarkGoodsSeen`); what comes in is a line in the feed. They
are PAID by the loop (`USOLootSubsystem::OnDied`, `USOLootLibrary::RollGoods`, data `"goodsDrops"`): every kill rolls
"kill", an elite "elite" on top, a boss "boss", and a creature its own key's list (`ASOCombatCharacter::GetLootKey`: a
variant's id, or its boss's: each named one of Meridian Fall carries its relic, the commander the core); the elite's, the boss's and the creature's own list go to EVERY player in the world, each their own roll (whoever landed the last round, the team fought it; the owner's queue, 2026-11-22; test `ShatteredOrbit.Goods.RelicsGoToEveryPlayer`), the "kill" roll, the credits and the xp to the killer; a cache rolls
"reliquary"; dismantling a gun gives its class's material by rarity and void crystal from Legendary on
(`"dismantleGoods"`, `USOLootLibrary::DismantleGoods`). And they are TAKEN by raising: a raise takes the piece's
material (its gun class's, armour's) by rarity and void crystal for Legendary and Sovereign (`"progression.upgrade.goods"`
-> `USOProgressionTable::UpgradeGoods`, `USOInventoryComponent::GetUpgradeGoods`; short of any of it, nothing is paid).
Tests `ShatteredOrbit.Goods.*`.
**The journal** (the armoury's JOURNAL tab, 2026-11-22; the owner's armoury reference: "a journal of what was learned"):
`Data/journal.json` (read at runtime, `FSOJournalData` in `SOJournal.h`; `tools/package.sh` stages it) has the sections
(the Sarketh, operations, the war, makers, the record) and the pages, each shown once its key is learned (`SOJournal`:
`met:<species>` = one was killed where the player was, EVERY player of the world learns it; `named:<variant>`;
`stage:<operation>:<stage>` = a stage began; `done:<operation>`; `origin:<origin>` = a gun of that maker came in; none =
from the start). An operation's pages are NOT written there: they are its plan's own words (the briefing with its first
stage, the radio's line as each stage begins with what the stage asked, the outcome), read from `Data/areas.json`'s
operations, so nothing is written twice. The inventory keeps what was learned, what was read and the tallies (kills by
species and in all, named ones, operations finished, deaths: `USOInventoryComponent::Learn / MarkJournalRead / Tally`;
replicated to the owner, saved: version 10); a page first learned is a line in the feed (an operation's own come with
its banner and radio, quietly), unread pages mark the tab gold. The view (`EView::Journal`, the armoury's list
machinery: sections as categories with learned / all, pages as rows, a page not learned a locked row with what would
teach it) has no stand-in: the reading pane takes its room, the rank's portrait beside the words (`T_Journal_<rank>`:
`skr/lab.py -- <sex> --part=full --pose=Idle:1 --portraits=<species,...>` renders each rank in its colours, the whole
body and the head and shoulders, `SO_IMPORT_ONLY=journal`); the record is drawn from the tallies. Pictures set 19's
`SO_u11*_journal_*`; tests `ShatteredOrbit.Journal.*`.
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
**The story** (`docs/story/WORLD.md`, the owner's own, adopted 2026-11-14; it replaced the first bible: no Stillfall,
Pale Network, Keystones or Quiet any more, and NO dates or lengths of time for the war). Humanity had spread through
its system; a many-species empire (the Vanthos Empire) came in from the edge and took it a world at a time; over
Earth the empire's ships turned on each other (the emperor was murdered: nobody on Earth knows) and most left. What
stayed holds ground by species, each wanting Sol for its own people and fighting the others for it; we reverse
engineer their technology (void crystal) and go out to take the system back. A place held by one species has ONLY
that species in it. Meridian's is **the Sarketh**: one humanoid people, all the same size under what they wear,
ranked by what they are issued (every one has a gun; higher command has more armour and bigger guns): Runners
(scouts: the `stalker_feral` role), Levies (foot soldiers: `remnant`), Veterans (`stalker`), Speakers (signals
officers: `veilborn`), Wardens and Bearers (officers and heavy weapons in powered armour: `bulwark`, `bearer`), the
commander in a walking war suit (the Colossus: `colossus`). The big ones are SUITS with a soldier inside, never
bigger creatures. Ids, classes and asset folders keep the first names (an API); what the player reads is each one's
`DisplayName` and the plan's variant names, which follow the story. **The Sarketh are the owner's OWN design**
(`art/reference/sarketh/sarketh_design_sheet.png`, 2026-11-15: "it's my art"): a tall, dark, digitigrade species
(2.0-2.3 m, a crested head with eye slits, claws) in MODULAR pale metal armour by slot, built by `tools/blender/skr`
(below: "The Sarketh in the game"). The old `tools/blender/hero/sarketh.py` set is built on the HUMAN male and is NOT
the Sarketh: the owner made it a human player armour set (2026-11-15); never bring it into the game as them (on
2026-11-21 it was taken for them and the owner corrected it: "that one is the human model"). The first bodies
(`altered.py`'s husks grown through with crystal) were DELETED on 2026-11-22 at the owner's word ("delete the old
models like these two in the picture for the sarketh": the Warden's and the Bearer's), every one of them, with the
script that made them: every rank is a Sarketh.
Other species are designed only when the owner asks for the place they hold (some humanoid, some nothing like us),
each with names of our own.
**The Sarketh in the game** (the owner's design; 2026-11-21, the owner: "work on getting the new sarketh models we
made"): `tools/blender/skr/game.py -- male|female <Folder>` builds the body, its armour by slot and the rig
(`build.py`, at 4.5 mm), joins them into one skinned creature within the enemy class's 40k triangles (the dark body
collapsed to 14k: the armour carries the silhouette; the armour's flat faces dissolved first, then collapsed evenly to
26k: held at their turning edges the collapse stalled at four times the budget, 500 shards are nearly all rim), its
hard edges split, bakes the Sarketh's own motion (`skr/motion.py`: Idle, Walk, Run, Attack, Death, Cast, Blink on the
digitigrade skeleton: the knee forward, the hock back, the weight on the toes; the trunk carried forward and the head
level and still; the hips found at every frame so the weight-bearing toes stand on the ground) and writes
`SourceArt/Characters/src/skr_<sex>.glb`; `export_fbx.py --single` into `SourceArt/Characters/Sarketh` (the male) and
`SarkethFemale`; `SO_IMPORT_ONLY=sarketh` imports them (`import_assets.SARKETH`, `skr_extra`: each material on its own
texture engine set from `assets/textures`, `SKR_SETS`: skin, armour, dark; the occlusion read; the pale plates at HALF
their set's metal: fully metal they mirrored the ground and read dark bronze in daylight, where the sheet's are a pale
satin grey; the armour set itself drawn pale, `skr/textures.py` armour `#a39e94`: at `#59564f` a steel plate read
black). Who wears which: the male the Levy (`ASORemnant`) and the Veteran (`ASOArmedStalker`), the female the Speaker
(`ASOVeilborn`) and the Runner (the feral stalker, `ASOEnemy`'s own body); their capsules as tall as they stand (the
male 36 x 104, the female 34 x 98). The heavy ranks wear the HEAVY Sarketh (`skr/game.py -- male SarkethHeavy
--rank=heavy`, `male.heavy_parts`: his set with a tall shield along the left forearm, a power unit on the back with
fins, a fourth pauldron layer, a plate down the breastbone), a little bigger in powered armour
(`SOAltered::Configure(..., Scale)`): the Warden (`ASOBulwark`) 1.08, the Bearer 1.06, the commander (`ASOColossus`)
1.32 (the sheet's "bigger boss version" until its war suit is designed). The heavy ranks' moves play the Sarketh's own
clips (`skr/motion.py`: Slam, Sweep, Barrage, Shield, Brace, timed to the kits' `clipLead`). **Every rank its own
colours** (the owner, 2026-11-22: "give the different types different colour set, not too wild but enough to
distinguish them"): tints a species' constructor sets (`ASOEnemy::PlateTint`, `LacquerTint`, `LightTint`), laid as
dynamic instances on the body's own Sarketh materials as it is set (`ASOEnemy::ApplyRankColours`: the plates and the
claws, the dark lacquer, the small lights' glow; the eyes stay the species' white): the Runner sand, the Levy as made
(grey), the Veteran steel-blue, the Speaker teal, the Warden ivory-gold, the Bearer bronze, the commander crimson; never
violet (another species'). The half-metal plates mirror the sky, so a tint of a tenth or two did not show: the hue
moves about a third (the lacquer more: it is most of the female). They hold the light guns, which are the Sarketh's own technology (the story).
Pictures `SOCaptureSeries 1 42` (files `SO_k*`: the seven ranks in a line on open floor the capture finds for itself,
then each close). Still to do: the Warden's, the Bearer's and the commander's own powered armour and war suit on
the owner's design (the heavy Sarketh stands in), levels of detail, baked own maps (the gate's own-maps check), voices of their own, the
female's and the male's sets told apart by rank (the armour is modular by slot: a rank is a set).
**Made to the sheet** (the owner, 2026-11-21: "work more on the sarketh model to make it exactly like the image I send";
`skr/lab.py -- male|female --part=head|full [--bare] [--pose=Idle:1] --views=sheet,head,headside,back,torso,legs,...`
builds a part in a minute; the view `sheet` is the sheet's OWN view of that body, orthographic at its scale (the floor
at y 968, the male's 2.03 m at y 80, the body at x 330 / 640 of the 1536), over nothing, to lay over the sheet or set
beside it): the head is ONE shape, `anatomy.head_field` (a cranium and a long face keeled down its front to a pointed
chin, the jaw back to the throat; `anatomy.HEAD` 1.12: the sheet's helmet is big beside the shoulders), the sculpt's
head and the helmet's base alike. The helmet (`male.head_parts`): a dark lacquer shell over it; the eyes almonds of
light INLAID on it (a slit cut through the shell closed when the helmet was reduced for the game); pale plates only at
the face's edges, over the eyes and along the cheeks (a pale stripe down the middle of the face read as a beak); a
crest of free blades (`chitin.shard`: a lens-section blade along a curve, its broad face toward a hint, `lower` for a
horn's straighter edge, `notch` for a second point), eight a side in three layers (the owner, 2026-11-22: "crest
more layered"), thick and RISING up and back off the brow and the crown (laid back level they read as a fan of knives),
the longest on top, the lowest down the back of the skull, pale and dark by turns, two taller dark horns over them;
over each eye a heavy dark brow plate, a second cheek plate and one at the temple. The body's armour is the sheet's dense mosaic of
ARROWHEAD shards (a narrow root under the plate before, `wrap(..., base=.32, peak=.30)`) in rows on the front and
outside of every limb, the inside bare (`span` round the front and outside, `dark_share` / `dark_arc` for the dark
ones; tiled all round, a limb read as plated trousers; square plates read as a checkerboard), lying close (tips that
flare read as a skirt); over them a chevron of plates down each side of the chest to the breastbone, the pauldron in
three ROUNDED layers with a point rising behind (`blade(..., angular=)`: a plate's own outline), a collar of shards
round the back of the neck, the spine's wide V with lights along it (`stud(..., lift=)` onto the plate), spikes off
the elbows, calves, hocks and heels, small amber lights at the hips, knees and hocks (`skr_glow_amber`), the claws the
plates' pale metal (`skr_claw` on the armour set). A plate reads carved, not cut paper: a ridge down it, walls
bevelled in (`_blade`'s underside at 80 % of its width), a darker body (corner tone .33-.41) and a bright worn rim.
The female is NOT his set made smaller (`female.SKIP`: his rows, his chest, his pauldron and collar): her own sparse
set of long flowing plates (`female.layout`: a rounded plate on each breast, a band over each collarbone, one rounded
pauldron with a point, a long plate from the hip down the outside of each thigh, a few down the arm and the shin) on
her own slender body (`lim` .86, slight lats, a pinched waist, the hip's curve into the thigh); her crest darker
(`female.DARK`). The neck is carried forward (about a third off upright), the trunk a V (a high ribcage, the lats
tapering to the waist), his limbs heavy (`lim` 1.30). The hide's scutes are three centimetres and satin, the dark
lacquer glossy (at a satin roughness a thin blade seen edge on read pale), the plate a neutral grey at a satin
roughness. The idle stands as the sheet does: the feet apart (each leg out six degrees, the foot turned back level),
the arms held off the body.
**The old Sarketh armour on the human body** (`tools/blender/hero/sarketh.py`, first look 2026-11-14; the owner's ruling
of 2026-11-15: a HUMAN player armour set now, NOT the Sarketh, never their bodies in the game): built with the player armour's plate tools (`void_sentinel.py`: `shell` / `suit` / `Base.plate`
/ `Base.light`, imported as a library with its material names pointed at this set's by `use_tools()`) on the saved
rigged male build, so a Sarketh has the player's skeleton and takes the body's clips: `blender -b <saved rigged male
build> -P tools/blender/hero/sarketh.py -- male --save=x.blend --frames=<dir> --clips=Idle,Run,Crouch --n=1` (45 s;
frames are plain workbench looks), pieces `C_<slot>__sarketh_veteran`. The look (second pass, on the owner's word
of 2026-11-14): nobody sees a Sarketh's skin (a sealed suit). **Their armour is made like their guns: the light
(energy) guns are the Sarketh's own technology**, so the armour has what those guns have (`weapons.py`, energy
class): pale shells (`sk_plate`) over a dark frame (`sk_plate_dark`, `sk_trim`), long flat panels with slanted ends
(`leaf()`), CYAN light in rows of short dashes and in one long thin line (`sk_glow`, `sk_visor`), ribbed vents with
the light behind them (the belly, the breastplate's slot), a little gold at a fastening (`sk_gold`); their red only
as cloth hanging from the belt before and behind (`sk_cloth`). The helm is FLAT-FACED and hard-edged (flat planes,
`helm_form`): no eyes, a recessed vent down the middle of the face with a column of dashes of light, a heavy dark
brow coming down to a point over it, cheeks meeting in a pointed chin, and a thin blade of a fin built as its own
mesh (cut from the helm's form it came out a fat ragged paddle). **Violet and the Void Requiem's look belong to
ANOTHER species** (the owner: "the void requiem we will use for another species"): never on the Sarketh. Lessons:
a face that is round either side of a seam reads as a backside (the owner's word for the first helm): flat planes;
a single coloured shoulder on pale plate is somebody else's trooper: rank is how much is worn; an outline for `poly()` must be CONVEX (cut a
notch out with `inter(poly(a), -poly(notch))`); a plate region defined by "stands off the skull" also takes the
face: bound it. **What it is made of** (`tools/blender/hero/sarketh_surface.py`, the owner 2026-11-14: "the red piece ... should be a
fabric not a block so it should move with the air and it should carry their emblem ... iron should look like iron not
plastic, with scratches and so on, so make it more alive"): metal maps of our own per material (`metal()`: `shell` =
the pale plates, enamel over forged metal with chips and gouges down to steel; `iron` = the dark frame, hammered, pitted,
rust in the hollows; `steel` = belt and cuffs, brushed; `brass`), relief laid in TWO scales (a hammer blow is a
centimetre wide, a scratch a hair: one strength for both gave chrome scales or nothing), one repeat every `TILE`
0.15 m (`fabric.world_uvs` on each finished piece); wear in the corner colour `Col` (`wear()`: RGB tone / grime / dust /
ground dirt, A = rubbed), and **edge wear lies on the chamfer's own faces** (narrow AND turning a corner on both long
sides): a band spread in from the rim's points covers the whole of a plate with few points. Rivet heads where plates
are fastened (`sarketh.studs`), brass studs round the belt. **The cloth** (slot `cloth`, `C_cloth__sarketh_veteran`:
the tabard and the tail) is ONE layer cut to a pattern, gathered into folds under the belt, with UVs that are its flat
cut in metres on a map of its own (`cloth_maps`: twill in their red, hem, a gold-thread border, lower edges frayed thread
by thread through the alpha, burnt holes, dirt) and **their emblem** (`emblem()`: the faceless helm seen from the
front: the brow's chevron and the lozenge in gold thread, the face as a blade with the vent's slit and three dashes
either side in pale thread). It is simulated (`simulate`: pinned at the belt by the group `pin`, colliding with leg and
hip solids that stand INSIDE the pinned line (pinned rows inside a collider wring the cloth into a rope), a breeze
standing, a headwind at a run); in the game it will be the engine's cloth on that section. `--look=dir` renders the
set lit (Cycles, OptiX when there is a card; `--quick` = workbench to tune the cloth; `--nobuild` on a saved build;
`SK_VIEWS=name,name` picks views). The owner approved the Veteran's third look on 2026-11-14 ("This looks great") and asked for
the other ranks. **A rank is the Veteran's set with less on, or more** (`sarketh.RANKS`, `--rank=runner | levy | veteran
| speaker | warden | bearer | colossus`, pieces `C_<slot>__sarketh_<rank>`): `skip` = the plates it is not issued
("piece:name", matched from the front; the plate tools are wrapped in `sarketh.Base`, which issues only those), `cloth`
= which cloths, `fin` = the helm's blade, and for POWERED armour `bulk` (metres the whole frame stands further off
the body: shells, the limbs' and trunk's radii the outlines scale with, the cloth and its collider), `thick` (every
plate heavier), `pauldron`, `pack` (`carried()`: a power unit, the Bearer's drum with its feed, a Speaker's mast);
a powered frame's boots are the same boot made as wide and long as its legs. Runner 104k triangles, Levy 117k,
Speaker 144k, Warden 151k, Bearer 150k, the commander's suit 163k (a first pass: the heaviest powered armour, not
yet a designed walking suit). A rank that wears ONE cloth still needs the collider's other side (mirrored about the
hips). Still to do before any can be an enemy: proportions of its
own, a triangle budget (the set is 142k: an enemy needs a fraction), baked curvature / occlusion maps on unique UVs
in place of the corner colours, a structure for the under-suit, its own clips and voice, a rifle in its hands, the
other ranks as less or more of this set.
**Why the operation exists** is written before it is built (`docs/story/MERIDIAN_FALL.md` = this operation's
reason): when the ring broke a station came down on Meridian and the Sarketh landing force came down after it; an
Institute team woke the station's deep-space array, and the Sarketh have lit it to call their own people to come
and take the system; nothing flies through the storm round the beam, so a team walks in to cut it, kill the
commander in his Colossus and bring out the Sarketh command core. The plan carries what the game
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
hidden; the drawn zone has no collision. Never give a Nanite mesh its own complex collision: a Nanite mesh that is
collided with (Nexus Prime's kit, tiles and vehicles, the operations' barrier and conduit) takes it from an EXACT twin
(`import_assets._nanite_solid`: the same FBX, not Nanite, the same slots in the same order, so a hit's ElementIndex
names the same material) set as its `ComplexCollisionMesh`, editor-only data: the cook bakes the twin's triangles into
the mesh's own collision; the twins live in `/Game/EditorOnly/Collision` (never cooked: `DirectoriesToNeverCook`;
never held by an area's arrival); `_nanite(mesh, True)` refuses. Test `ShatteredOrbit.World.NaniteCollidesExactly`. Do not name an object `*_col` (the FBX exporter takes that for UCX collision). The invisible walls
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
loading screen (`USOAreaSubsystem::TravelToLevel`, the engine's movie player: the area's name on a dark screen), and
the same screen stays up while the area ARRIVES (`BeginArrival` / `TickArrival`, the owner 2026-11-12: "a loading
screen that loads all assets then lets us play"; entering the operation froze and once the graphics card hung in
Nanite's shadow culling three seconds in): every asset the area can use is loaded and held (all of `/Game` but the
other areas' folders and the maps; let go on leaving), the garbage of the last place collected, the nav mesh built,
then the world drawn BEHIND the screen until shaders and textures are in; nothing of the new world is drawn before
its assets are in, players cannot move or fire, an operation's clock and captures wait (`IsArriving`). Never keep
a bare pointer to a loaded asset across a timer or a level change (nothing holds it: it is collected). Test
`ShatteredOrbit.Area.OneAtATime`.
**The third-person combat stance** (the owner, 2026-11-23, with a reference sheet: "a professional AAA third-person
shooter character with a confident, aggressive, disciplined military combat stance"; their picture of the wrong pose was
the outfit capture taken with the gun hidden, the hands still on its grips). What made the pose weak, found before
anything was changed: the gun's butt sat 4 cm under the shoulder joint in one state only (no relaxed, no ready); each
elbow was aimed nearly straight down (pole .45 out) and the support elbow capped low, so both tucked against the ribs;
the collarbones pulled forward up to 24 degrees on any forward reach and the trunk was bladed 12-24 degrees to the gun:
rounded shoulders; and the legs were the plain idle's: upright, the feet together. Now a profile per CLASS of gun
(`FSOStance`, `SOCharacter/Public/SOStance.h`; `Data/stances.json`, read at runtime and staged by `tools/package.sh`:
smg, rifle, lmg, sniper, shotgun, pistol, heavy, chosen by the gun's family): where the gun rides at the ready and on
the sights (the shoulder pocket's shift, a handgun's grip), the relaxed carry, each elbow's lean out and how far it may
swing, how much of the collarbones' pull is taken out (square shoulders), the trunk's turn and forward lean, the chin
down, the knees (the hips lower), the support foot forward and the feet wider standing. THREE STATES: relaxed (out of a
fight: the gun carried low across the body, the arms easy), ready (up and forward, the body in its stance) and on the
sights (the cheek on the stock); `ASOCharacter::GetCombatReady` (0 relaxed .. 1 ready) comes up on a shot, an aim, a
reload or a hit (`MarkCombat`) and goes back down `combatSeconds` after the last, eased (`raiseTime`, `lowerTime`;
replicated as `bCombatReady` for the other machines). Applied where it already lived: the gun's place in
`USOViewmodelComponent::ThirdPersonHoldTransform` (the relaxed blend beside the sprint carry and the reload), the body
in `USOLocomotionAnimInstance` (`FSOStanceInputs`: the stance's feet through the legs' two-bone IK in `ApplyBody`, the
hips' drop with it; the elbows, the collarbones and the chin in `ApplyHold`); players only (a creature keeps its own way
of holding), never the first-person arms. Lessons: holding the FIRING elbow out bends the wrist on a raked grip past a
hand's limit, so on the sights the firing elbow goes where its wrist runs straightest and the shoulders roll into the
gun (60-75 degrees from the forearm is a hand round a pistol grip: `Hold.TheGunIsSolid` allows 75 on every gun now); a
muzzle dipped at the ready costs the wrist as much. Pictures `SOCaptureSeries 1 47` (files `SO_st_<gun>_<relaxed|ready|
aim>_<view>`; `-SOGuns=`, `-SOStanceViews=20,90,180,270`, one exposure, no HUD); tests `ShatteredOrbit.Stance.*`.
The loadout is worn: of the three equipped guns one is in the hands, the others each in a place of their own
(`ASOCharacter::RefreshHolsters`: long guns stand side by side on the back, one behind each shoulder, placed by their
BORE LINE inside the shoulders' width, never by their outline (a gun with fins was pushed out beside the body);
handguns at the hips; the gun in hand is stowed while mantling); pictures `SOCaptureSeries 1 12|13`. The waist never
twists far (`USOLocomotionAnimInstance::MaxWaistTwist`, 20 degrees): strafing or standing while the aim turns, the
pelvis takes half the turn up to that and the legs the rest about their own hip joints (a bare waist shows every degree).
Movement (`USOCharacterMovementComponent`, the owner's brief of 2026-11-09, and their movement guide of 2026-11-20,
`art/reference/movement/movement_guide.webp`, read in `docs/orion/GAME_LOOP.md`: the run in 0.15 s and the stop in
0.10 (`MaxAcceleration` 3000, `BrakingDecelerationWalking` 4400; before, instant), a slide of 0.8-1.2 s, the view at
95 degrees (`USOGameUserSettings::FieldOfView`) widening to 105 at a sprint (`SprintFovBoost`) and leaning into it
(`SprintCameraPitch`), a 2.5 degree lean into a strafe (`StrafeCameraRoll`), a hard landing's wobble (`LandShakeRoll`:
a spring knocked by the impact), and **the dodge** (`ESOCustomMovementMode::Dodge`, `IA_Dodge` = Left Alt, no pad key
yet: a burst of `DodgeSpeed` along the stick or straight back for `DodgeTime` that eases into the run, `DodgeCooldown`;
the press is kept `DodgeBufferTime` when the feet cannot yet; its state `ESOMovementState::Dodge`, its event
`DodgeStarted` (Strength = its side), the view rolls into it, the gun trails it through the viewmodel's strafe
inertia; it travels in the saved move's `FLAG_Custom_3` with its elapsed, cooldown, buffer and direction saved per
move). Pictures `SOCaptureSeries 1 39` (files `SO_mv_*`: idle, sprint, slide, dodge, jump, landing, strafe from the
eye; the slide and the dodge from beside the body, the dodge slowed to a tenth: at the capture's frame rate a
0.22 s move is one frame). **Fluid, like water** (the owner, 2026-11-20, on the first pass: "very fluid, like
water, truly perfect triple a and not some sprite sheet"): nothing moves on a straight line and stops dead:
the gun's sprint carry, its trail behind a strafe or a dodge, its sway behind a turn, its slide and mantle
tucks are damped SPRINGS (`SOViewmodelComponent.cpp` `Spring`: a little overshoot, then settled; the
`FInterpConstantTo` they ran on was the machine's motion), so are the camera's roll and the eye's height across
crouch, slide and stand (`CameraRollVel`, `EyeVel`); standing still the gun and the view breathe (3.6 s); the
acceleration into the run is a curve (`GetMaxAcceleration`: quick first step, soft arrival) and the dodge's
speed falls on one; the body has its own dodge clips (`hero/male/motion.py` `dodge(dx, dy)`: `DodgeL / R / B /
F`, 0.32 s, the step out of the line in place, played whole over the gait while the burst runs and fading as
it plays out: `USOLocomotionAnimInstance` layer `Dodge`, `ActiveDodge` picked by the dodge's direction). **Looking steeply down in third person** (the owner, 2026-11-20: "the players hand splits and the gun moves weirdly"):
the trunk's share of the aim pitch stops at a lean (`USOLocomotionAnimInstance` hold pass, the stance pitch clamped
-46..+57 degrees: at 70 % of -80 the body folded 56 degrees at the waist and the gun from the shoulder pocket
pointed down along it, the support hand beyond the arm), and below -20 degrees the stock comes off the shoulder:
`USOViewmodelComponent::ThirdPersonHoldTransform` blends the hold's point from the pocket to low and ahead of
the chest (`Low`), the gun's middle hanging from it, both hands on it with the elbows bent; the support hand may
slide 30 cm back along the gun (14 left it floating). Pictures `SOCaptureSeries 1 40` (files `SO_hp_<pitch>_*`,
at rest and aiming, -89 to +75). **Pass 2 of the look-down** (the owner, 2026-11-21: "the third person gun placement is in the players
face ... the wrist should not be twisting like that"): the gun's OWN pitch in third person is held within
`ThirdPersonMaxDownPitch` 55 / `ThirdPersonMaxUpPitch` 65 degrees (pointed straight down from the chest the stock
stood up along the face; the shot still goes along the eye's axis), it hangs from `ThirdPersonLowHold` (22 ahead, 10
right, 27 under the chest point) canted `ThirdPersonLowCant` 20 degrees inward, and the trunk's share of the pitch
stops at -40 (the head does the looking). The firing wrist at the full look-down went from 120 degrees to about 60-80;
a hand round a raked pistol grip is 60-75 degrees from its forearm (`ShatteredOrbit.Hold.TheGunIsSolid` allows 75).
Where the stock, the grip, the trigger and the fore end are comes from each gun's own shape (the rig's bounds and
`FitGrip`), never from hand-written numbers per gun. **Pass 3** (2026-11-21): letting the sprint go eases down to the run over `SprintEaseTime` 0.35 s (it braked
to it in a tenth: a lurch); the pad's B is one action (`IA_PadCrouchDodge`, `ASOCharacter::HandlePadCrouchDodgePressed`:
tapped with the stick pushed at a walk or a run it is the dodge, at a sprint the slide, otherwise the crouch; every
face button is taken); the third-person boom is `SprintArmExtra` longer at a sprint (eased: the view opens as the
body stretches out). The capture's stepper runs ONE cue a frame (`CaptureStep`: the timer catches up by firing
several times in a slow frame, and an Act 0.05 s after a Snap moved the camera before the screenshot was drawn:
every picture showed the step after its own; set 40's face cameras are on the support side, where the gun is not).
Still the guide's: no grapple (the owner, 2026-11-21: "don't add grapple yet, we will do that much later"), the ground
slam is the melee's air slam. Built sprint, coyote time,
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
Enemies, the Altered (`SOAltered.h`; the name stays an API: their bodies are the Sarketh now), all armed with our guns (`ASOEnemy::WeaponArchetype`, held two-handed
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
owner: "the ai is stupid"): hit in the open, one that fights from cover makes for cover at a run, another steps aside
now and then (`Sidestep`); NEVER for a gun merely levelled at it (the owner, 2026-11-22: zoomed in, "they just move out
of the way fast ... shooting needs to be a bit more easier and more fun, fun the the most important thing here");
badly hurt it falls back to cover further off and stays down longer (`bRetreating`); when the target goes out of
sight the flankers and hunters move up in BOUNDS (`Push`: a stretch of the way, `BoundLength` 9 m, then a moment there
looking, never one run down the street), while the rest HOLD THEIR GROUND (`HoldsGround`, `HoldRadius` 18 m round
where it was put into the world, `Home`): they take cover there, wait (`Patience` 12 s), search no further than its
edge; claws come in round the sides (`SideBias`), everyone keeps its own distance (`RangeBias`). **The AI pass of
2026-11-22** (the owner: "if i shoot beside them they do nothing, they need to listen to sound, see bullets and react
... they get shot by the player then just ran straight to the player no matter how far ... like they are mindless
zombies ... going behind cover and holding an area ... must be modular ... their behavior should be the same"): a
round that passes or strikes within `USOProjectileSubsystem::ShotNoticeRadius` (6 m) of a body is SEEN AND HEARD
(`ASOCombatCharacter::NoteRoundNear` -> `ASOEnemy` -> `ASOEnemyAIController::OnShotNear`): it is in the fight, knows
from which way, and one caught in the open makes for cover (looking out from cover, it ducks); hit, heard or shot at
by someone it has not seen, it knows the way and roughly how far, NEVER the place (`Guess`: off by about a tenth of
the distance; it took the shooter's true place and ran there); a gunman JOGS from place to place (`ESOPace`,
`ASOEnemy::SetPace`, `JogShare`) and runs only for cover under fire or falling back (at a dead run all the time it
was a blur to shoot at), shoots wider on the move (it stops to shoot), looks out of cover two to three and a half
seconds at a time, and with no cover (or no nav mesh) it holds where it stands and fights from there: no gunman ever
steers straight at the target (`ChaseTarget`: claws only). The same brain in every level: the range's spawners and
an operation's garrisons hold ground, its hunting waves come on in bounds. A creature's line of fire is what its
round would meet, traced as the round is (complex, from its eye, AND eye to muzzle and muzzle to target: a barrel in
a wall's corner fired "through the wall"); an ability's start point (`GetCastOrigin`) stops short of anything between
the eye and the hands; a blow lands only with nothing of the world between and no floor between (`CanReach`). A
dropped gun blocks no one's sight. Tests `AI.ShotsNearbyAreNoticed`, `AI.HoldsGroundWhenShotFromAfar`,
`AI.AimingDoesNotMakeThemDodge`; the report is `docs/orion/reports/AI.md`. A hunter knows where the players
are but aims and fires only at what it sees; `HasLineOfFire` is the bullet's own trace, fat, and stops behind a mate.
A hit is news (`USOCombatStatics::OnCharacterHit`, `OnCharacterDied` -> `ASOEnemyAIController::OnHit`): the one hit
knows from any distance; a mate that is looking at it (`Notices`: in view, nothing between) or stands within
`MateFeelRadius` is warned, and each one that reacts is noticed in turn by the next (`EnterCombat` passes it on a beat
later), so a sniped sentry wakes its group and nobody beyond sight (the owner: "if one is sniped then rest don't do
anything"). Every armed creature fights from cover to cover, the Remnant too: far from the range it likes it takes
any cover nearer the target than it stands (`FindCover` bAdvance) and holds a few bursts before the next bound; it
does not fire while running between two covers unless the target is on top of it; with nowhere to hide it comes
round in an arc to a point at its range, never down the line of the gun (`ThinkAssault`).
Tests `ShatteredOrbit.AI.NoShotsThroughWalls`, `ShatteredOrbit.AI.AHitAlertsTheSquad`. **Difficulty** (Project Orion phase 2;
`SODifficulty.h`, `Data/game_data.json` "difficulty" -> `SO_IMPORT_ONLY=difficulty` -> `/Game/Data/DA_Difficulty`): a
level is a set of scales on what the creatures and the brain already have (1 = as written), and a harder one makes
them BETTER, never just tougher: `Notice` (how fast awareness fills), `Reaction` (passing an alarm on, settling the
aim), `AimError`, `Burst` / `BurstPause`, `Patience` (how soon it pushes), `CoverHold`, `FlankShare` (how many go
round the side), `AbilityCooldown` (their own moves), and a little `Health` / `Damage` (given at spawn by
`USOSpeciesLibrary::Spawn`). Levels: recruit, standard (the default), veteran, lethal. A world's level is
`USODifficultySubsystem::Get(World)`; an operation's plan names its own (`"difficulty"`). In a fight a creature
reconsiders its target every second or so (`ReconsiderTarget`: one it can see that is clearly nearer, or the one that
just hurt it; switching costs it its cover). A creature far from every player and not in a fight thinks less often
(`ThinkPace`: half as often past 60 m, a fifth past 120 m). Test `ShatteredOrbit.AI.DifficultyLevels`. **Roles are kits, not creatures** (phase 2): a level makes a role out of a
species by giving a variant a kit (`FSOSpeciesVariant::Kit`, plan key `"kit"`), and the creature uses it BY RULE:
each time its brain thinks, `ASOEnemy::UseKit` asks every ability of its kit `WantsUse(User, Target, Grant, bSees)`
and uses the first that says yes; while one winds up it stands, holds fire and turns with its target. A species
with moves of its own decides those itself and ends on `Super::ThinkCombat` (the Veilborn does). The role kits
(`Data/game_data.json` "kits"): `commander` (`USOAbility_Rally`: its own side within reach gets haste; when the
one that carries a rally dies, those round it are staggered: kill it first), `disruptor` (`USOAbility_Pulse` with
`"status": "jam"`: a player caught in it cannot use abilities for the duration; its wind-up is the warning),
`hunter` (a lunge and a thrown charge: the player's own abilities with wind-ups), `alpha` (the pack's howl). In
Meridian Fall the Remnant Captain, the Veilborn Seer and the Pack Alpha carry the first three and a Stalker Hunter
stands in the Concord Ring. A grant names the condition it leaves (`Status`: slow, burn, stagger, jam, haste, guard:
`USOCombatStatics::StatusTag`); guard and haste are boons (one's own side only), the rest harms (the other side
only). These roles still wear their species' bodies: none has a silhouette of its own yet. Tests
`ShatteredOrbit.Ability.PulseJams`, `ShatteredOrbit.AI.CommanderRalliesAndFalls`. **The pack**: a clawed creature with
others of its kind round the same target does not go in alone (`ASOEnemy::bPack`, `PackRing`): it holds off on a
ring round the target, moving round it (`HoldRing`), until three of the pack (or all of it) are in place, the
target comes to one of them, it is hurt, or seven seconds pass; when one goes, all go (`PackGoes`). Without a nav
mesh the hold steers straight at its spot every frame, as the chase does (the automation tests' worlds have none: a
path move there does nothing). **More players, more of them**: an operation's waves are written for one player, and
each further player adds `PerExtraPlayer` (0.5) of every group; a creature that stands alone in its wave stays alone
(`ASOOperation::ScaledCount`). Tests `ShatteredOrbit.AI.ThePackGoesInTogether`,
`ShatteredOrbit.Operation.MorePlayersMoreOfThem`.
**The owner's enemy AI brief** is `docs/orion/AI_BRIEF.md` (2026-11-13, word for word); what of it exists, what is
missing and what was tested is `docs/orion/reports/AI.md`: read it before adding to the enemies, and keep it honest.
The brain stays C++ (no Behavior Tree, State Tree or EQS). Added for it: **suppression** (`Status.Suppressed`: a
round passing within `NearMissRadius` 130 cm of a body of the other side pins it, `ASOCombatCharacter::NoteNearMiss`:
a pinned creature keeps its head down and aims worse, a pinned player's spread widens and the shield's refill waits;
the Bulwark, the Colossus and conduits are not pinned); **a suppressor** (a variant's `"suppressor"`: keeps the
place its target went to ground under fire, `ASOEnemy::SuppressAt`, and the squad pushes sooner meanwhile); a
variant's `burst` / `burstPause` / `range` / `high` (wants high ground); **the marksman's shot** (`USOAbility_Snipe`,
kit `marksman`: `USOFxSubsystem::AimLine` on the target for the wind-up, locked for the last `LockTime` 0.3 s, one
fast round at where the target was then; new cover every `Magnitude` shots); **hit reactions** (see "Every hit
counts" below); targets spread
between players (`ReconsiderTarget`: a crowd on one makes it less attractive); blasts, slides and hard landings are
heard; **reinforcements arrive unseen** (`ASOOperation::SpawnPointFor`: a hunting wave's creature takes the next
of its group's points that no player has in view, `SeenByAPlayer`; a garrison stands where the plan says); creature
animation is budgeted (update-rate optimisation; a body nobody sees does not animate, except on a server with
players joined, where rounds must land on it: in a test set `VisibilityBasedAnimTickOption` to always tick before
reading a creature's pose); **a pack that is cut down breaks off** (a second of its kind dead near it within 4 s:
out to its own side and away for about 3 s, then the ring again; `ScatterUntil`); **a target loading its gun is an
opening** (`TargetIsOpen`: seen within 1.5 s, not on the easiest level: one in cover comes out and fires at once, a
pack with two on its ring goes in). Who a creature aims at is the server's knowledge (`SetAbilityTarget` is not
replicated): anything drawn from it goes out as a cue (`USOCue::AimLine`, `USOCue::Tracer`), never from an
ability's `Telegraph` / `Show` on each machine. To the one it points at an aim line is seen end-on, almost a
dot: what they read is the glint at its source, which keeps its size in the local view at any distance and flares
when the line locks. **A species' numbers are data**: `Data/species.json` -> `SO_IMPORT_ONLY=species` ->
`/Game/Data/DA_Species` (`USOSpeciesTable`: a key is the property's name with a small first letter and no `b`,
a switch is 0 / 1, a range is `<name>Min` / `<name>Max`, `health` and `shield` are what it starts with); every
creature takes them as it is made (`ASOEnemy::PostActorCreated` -> `ApplyNumbers`), a variant scales them after;
tune a creature THERE, not in its constructor (the constructor's values only stand in for keys the file lacks; the
import writes a new species into the file from its class). Not in it: body, clips, voice, capsule, own moves (the
class) and the brain's senses. `SOAIDebug` (console, not in shipping) draws what every creature within 60 m is
thinking and what the brains cost (`ASOEnemyAIController::ThinksCounted`). In Meridian Fall: `veilborn_marksman` on
the Sluice's footbridges, the Bearer (below) on the Boulevard and in the Concord Ring. Tests `ShatteredOrbit.AI.NearMissesPin`,
`SuppressorKeepsItUnderFire`, `MarksmanAimsThenShoots`, `HitsKnockTheBody`, `TargetsSpreadAndBlastsAreHeard`,
`ThePackBreaksOffAndTakesAnOpening`, `ShatteredOrbit.Operation.ReinforcementsArriveUnseen`,
`ShatteredOrbit.Species.NumbersAreData`; pictures `SOCaptureSeries 1 25` (files `SO_a*`).
**Every hit counts** (the owner, 2026-11-13: "ai feels like bullet sponges ... no reaction ... continuously charge
into my bullets ... every shot should count"). A hit does three things beside its damage (`ASOEnemy::HitReact`, called
from `ASOCombatCharacter::OnTookDamage`, which the damage gate calls for every body; where the blow landed travels
with it: whoever knows holds an `FSOHitScope` round `ApplyDamage`, the reaction reads `USOCombatStatics::LastHit()`;
a round does). It CHECKS the creature (`HitSlow` of its speed for `HitSlowTime`, a leg hit longer: fire slows what
runs at it). It UNSTEADIES it: the damage as a share of full health fills a meter (`PoiseDamage`) that drains by
`PoiseRecover` a second; a precise hit counts `PrecisionPoise` times, a leg 1.25, and what armour turned still counts
by `ArmourPoise`. Past `Poise` it STUMBLES: `Status.Stagger` for `StumbleTime`, the blow it was winding up lost, its
fire stopped, knocked a metre back, then `StumbleRest` before it can stumble again (and the meter fills only half
meanwhile). And it SHOWS where it landed (`MulticastFlinch` -> `USOLocomotionAnimInstance::HitKick(ESOHitRegion)`:
the head thrown, a shoulder driven back turning the chest, a leg giving so the hips drop, the trunk knocked away;
reeling is bowed and sagging). All of these are numbers in `Data/species.json`. A boss (anything with a boss table)
and anything that resists stagger is not checked or stumbled. **The head's kick is the last thing done to the pose**
(`FSOLocomotionProxy::ApplyHit`): the gun-hold pass sets neck and head afresh, and anything put on them earlier is
lost. **Test the body, not the number**: a reaction can be in the anim instance's values and not on the bones (it
was); `ShatteredOrbit.AI.AHitShowsWhereItLands` measures the bones, and `SOCaptureSeries 1 26` (files `SO_h*`) shows
them from beside the creature. The brain: a clawed creature hit on its way in (not merely aimed at) leaps out of the line
(`ASOEnemy::Juke`, how often is the level's `Reaction`) and comes in from the other side; badly hurt before it
arrives it breaks off once (`bBrokeOff`); after a stumble an armed one looks for cover. **The Bulwark's plate**
(`PlateFaces`): what it turns sparks and rings instead of bleeding (`ASOCombatCharacter::TurnsBlow`, read where the
impact is shown), still fills the stumble meter, and the plate is down while it reels: hammering the plate opens it.
A test whose creature has a brain and a player-controlled target must expect it to move when aimed at (remove the
brain if the test is not about it). Tests `ShatteredOrbit.AI.FireBreaksACharge`, `AHitShowsWhereItLands`.
**The Bearer** (the heavy gunner's own species, 2026-11-13; `ASOBearer` in `Species/SOBearer.cpp`, voice set
`bearer`; its body the heavy Sarketh since 2026-11-22, the old husk deleted; what follows is how the husk was): a broad
plated husk (a breastplate in three
lames with light in the seams, a collar round a small sunken head, a swept pauldron over the gun arm, a drum of
crystal-fused bone across the back whose feed comes round to a port on the belt) that carries the heavy machine gun
LOW AT THE RIGHT HIP in both hands (`ASOEnemy::HoldsAtHip` -> `UpdateGunHold`: the rear grip beside the hip joint,
the barrel laid on the target from there). Slow, no cover, a suppressor; its plates turn half a blow from the front
(`FrontDamageScale`), part while it fires and are down while it reels; it sets itself (`Brace` clip) as it opens
fire. Meridian Fall's waves name it directly (the Boulevard, the Concord Ring); the `bulwark_gunner` variant is kept
for a level that wants one. Sculpt lessons: thighs thicker than `legs(..., 1.5)` fuse and the hide stretches between
them in a stride; a bracer or tasset is a shell a finger off the limb and only its outer side, never a drum round it
(it stood out at hip height like a shelf). Its body now: `skr/game.py -- male SarkethHeavy --rank=heavy`,
`export_fbx.py ... SourceArt/Characters/SarkethHeavy --single`, `SO_IMPORT_ONLY=sarketh SO_SARKETH_ONLY=SarkethHeavy`.
Test `ShatteredOrbit.Altered.TheBearer`; pictures `SOCaptureSeries 1 27` (files `SO_g*`).
**A boss is a species with a table** (Project Orion phase 3; `SOBoss.h`, `Data/game_data.json` "bosses" ->
`SO_IMPORT_ONLY=bosses` -> `/Game/Data/DA_Boss_<Id>`; report `docs/orion/reports/PHASE_3.md`): `ASOEnemy::BossId` (a
species' own, or a variant's `"boss"`: a level makes a boss of any species with data alone) makes a `USOBossComponent`
on every machine; the server runs it, and what the others need travels on the creature (`BossPhase`, `BossWeakBroken`,
its immunity): the component is not replicated. The table: phases by share of health (`from`), each with the kit it
fights with (`GrantAbilitySet` replaces the last), scales on its cooldowns / speed / the damage it takes, the pause
between its moves, and whether it begins behind a shield fed by conduits (actors tagged `SOConduit`, or a ring round
it; destroy them and it reels). Phases come one at a time and never while it reels (the opening is the players').
Reeling is `Status.Stagger` put on by itself (`USOBossComponent::Stagger`: what a creature resists is what OTHERS do
to it) and it takes the table's `staggerDamage` meanwhile. **Weak points**: a ball round a point on a bone; a round
whose LINE passes through it on the way in is a precision hit worth `scale` on top of the gun's own. Test the line, not
where the round met the body: a body is a convex hull, and the heart sits in a hollow behind it. `front` = only from in front; `breakDamage`
on it within one phase breaks it (the boss reels, the point is shut until the next phase); each open point carries a
light. Precision is the victim's call everywhere: `ASOCombatCharacter::PrecisionAt(Hit)` (head and neck by default).
**Every boss attack is an ability with a wind-up**; the species only decides when (`UseKit(AI, Target, true)`: any of
those that would land, the phase's pause between two) and turns slowly while it winds up. What that needed:
`ChannelTime` (an ability that lasts: the slot stays active), a grant's `ClipLead` (the time into the creature's clip
at which the blow lands: the clip is drawn out so that falls on the end of the wind-up; `ASOEnemy::OnAbilityWindUp`
plays it) and `WindUpSound`, `USOAbility_Sweep` (thrown sideways), `USOAbility_Barrage` (a volley from
`GetCastOrigin`), `USOAbility_Eruption` (marks under those it fights and more round them, a fuse, a burst; what is
drawn is what bursts; they die with their user). **A warning on the ground**: `USOFxSubsystem::Warn` (a decal,
`/Game/FX/M_SOWarn`, `SO_IMPORT_ONLY=warn`: a ring or a sector worked out from the world position, a fill running from
the middle to the rim, only on faces that look up; `Follow` keeps it under a body that still turns). A strike with a
wind-up of 0.4 s or more draws its reach itself (`USOAbility_Strike::Telegraph`), a creature's blow goes where its
body faces (`Heading`), and a place the server chose goes to every machine with `USOCue::Warn`. Wind-ups follow the
brief: standard 0.9-1.4 s, heavy 1.5-2.2. Bodies and guns take no decals. The Colossus is the first (table `colossus`:
The Sentinel Wakes / The Choir Answers / The Root Screams, kits `colossus`, `colossus_choir`, `colossus_root`, the
heart in its hollow chest; its sounds `sfx_synth.py ... boss`, import `SO_AUDIO_ONLY=boss_`), and the Galleria's
Warden is a Bulwark with the table `warden`. The HUD's bar (`ASOHUD::DrawBossBar`: a notch per phase, the phase's
name, REELING) is for the operation's boss or any hurt boss within 70 m. Tests `ShatteredOrbit.Boss.*`; pictures
`SOCaptureSeries 1 23` (files `SO_b*`); `tools/netcheck.sh` puts a boss beside the guest too.
**What a round lands on is the body that is drawn**: the import refits the physics bodies of every skeletal mesh it
brings in, one convex hull per bone (`import_assets.fit_bodies` -> `USOEditorLibrary::FitBodies` in the editor-only
module `SOEditor`; `SO_IMPORT_ONLY=bodies` refits what is already imported). The engine's automatic bodies are fat
capsules, and a re-import never rebuilds them: the Colossus kept the bodies of an earlier, much bigger model (167 cm
off its surface on average, no head). `ShatteredOrbit.Altered.BodiesFollowTheBody` measures every creature (within
20 cm of the drawn surface, a shot at the head lands on the head).
**Armour counts: the six attributes** (Project Orion phase 4; `SOAttributes.h`, report
`docs/orion/reports/PHASE_4.md`). Names of our own: Plating (all damage taken), Mending (the wait before the shield
refills, and how fast), Stride (speed), Ordnance / Impact (the grenade's / the melee's cooldown), Focus (what charges
the ultimate). They are points, 0 to the table's `max` (100), real attributes in `USOAttributeSet` (owner-only), put
there by ONE effect (`USOGameplayEffect_Gear`, `ASOCombatCharacter::SetGearAttributes`) whenever the outfit changes
(`ASOCharacter::OutfitFromInventory`), so a perk or an ability can add to the same numbers. What a point is worth is
data (`Data/game_data.json` "attributes" -> `SO_IMPORT_ONLY=attributes` -> `/Game/Data/DA_Attributes`,
`USOAttributeTable::Scale`): read in the damage gate (beside the guard's scale), the shield's refill, `GetMoveScale`
(where a slow already goes), `GetAbilityCooldownScale(Slot)` and where the kit charges the ultimate. An armour piece's
points (`USOAttributeTable::ArmourPoints`, `USOInventoryComponent::GetArmorPoints`) = its armour rating x
`pointsPerArmour` x the rarity's scale x (1 + power x `perPower`); `lean` of them go to the attribute its slot leans
to (head Focus, top Mending, vest and outer Plating, hands Impact, legs Ordnance, feet Stride), the rest to two others
from the copy's own seed (`FSOArmorInstance::Roll`, 0 = its uid): the same copy always gives the same. A body in a
test that has an inventory wears armour: expect `GetAttributeScale(Plating)` on damage. **Levels and upgrades**
(`SOProgression.h`, data "progression" -> `SO_IMPORT_ONLY=progression` -> `/Game/Data/DA_Progression`): level
(experience, the curve and the last level are data) and power (each piece's own) are kept apart and meet in one rule:
a level sets how far gear can be raised (`GetPowerCap`). `USOInventoryComponent::Upgrade` raises a gun or an armour
piece one step for credits and alloy (`GetUpgrade` says what it gives and costs; `Spend` takes both currencies or
neither: the one way anything is paid for). The loadout screen shows the attributes, what a piece gives, and the
upgrade's price (key U). Saves are version 3. Tests `ShatteredOrbit.Attributes.*`, `ShatteredOrbit.Progression.*`.
**What a perk does is data**: its numbers in `Data/game_data.json` "perks" (`magazine`, `reload`, `spread`, `recoil`,
`precision`, `fireRateShieldDown`, `killDamage` / `Stacks` / `Time`, `killHeal`, `precisionSplash` / `Radius`,
`autoload`, and the sixteen perks of 2026-11-13: `killMagazine`, `killShield`, `killReload` / `Time`, `openingDamage` / `After`,
`lowMagDamage` / `Share`, `hipSpread`, `shieldDamage`, `healthDamage`, `hitSlow` / `Time`, `precisionBurn` / `Time`,
`noFalloff`, `noise`, `slideReload`; `classes` = the gun classes that can roll it) -> `FSOPerkInfo`; `USOLootLibrary::PerkEffects` adds up a copy's perks into `FSOWeaponStats::Perks`, which
is all the gun reads. Never ask a perk its name in code (`HasPerk` is for the screen); a perk that needs something new
adds a number and the one place that reads it. `SO_IMPORT_ONLY=perks` rewrites only the perks of `DA_LootTables`. New
perks are allowed since 2026-11-13 (25 now), with names of our own. Tests `ShatteredOrbit.Loot.PerksAreData`,
`ShatteredOrbit.Loot.NewPerks`. **What is worn is each body's own** (`FSOArmorInstance::WornBy`,
`USOInventoryComponent::SetBody`; saves version 4; test `ShatteredOrbit.Wardrobe.WornPerBody`). **A piece must cover
everything it hides**: look with `blender -b <saved build> -P tools/blender/hero/repiece.py -- <sex> --look=<dir>
--without=outer,vest` (the body as the game shows it, hidden regions gone: a hole is the background colour);
`--pieces=top` rebuilds one piece on a saved build, `--glb` writes the game's source, then `export_fbx.py --per-item`
and `SO_IMPORT_ONLY=player_pieces SO_PLAYER_PIECES=<sex>:<slot>:<item>` imports just that piece. Her top's armhole
is the body's own chest / arm border (`shirt.armhole`). Pictures `SOCaptureSeries 1 24` (her base layer, files `SO_f*`).
Shots on an unaware creature hit harder (ambush). Voices
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
**Meridian Fall rewards the Sarketh's own guns** (the owner, 2026-11-14: "change the loot from meridian to these
guns"): one Legendary copy of one light gun (`meridian_plan.REWARDS`: every energy archetype, no armour; checked in
`ShatteredOrbit.Operation.PlanFile`). The Void Requiem guns and the Void Sentinel armour are another species'
technology now and no operation gives them (the set caches in the range still do).
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
