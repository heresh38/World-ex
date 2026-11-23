# Asset audit, standards and checklist (the specification's first task)

`ASSET_PIPELINE.md`, section 16: inspect the project, audit what is there, set the standards, write the checklist,
name the first assets to upgrade, then build ONE reference asset. This file is that, kept current. Written
2026-11-14 from the project as it stands (nothing here is from memory: the counts are the project's own).

Status words are the specification's: **Concept / Blockout / Work in progress / Technically complete /
Art-approved / Game-ready / Shipping-approved**. "Technically complete" = it works in the game and passes its
tests; "Art-approved" needs the owner's word; nothing in the game is Art-approved yet except where it says so.

## 1. What is in the project

| in the game (`unreal/ShatteredOrbit/Content`) | assets | size |
|---|---|---|
| `Characters` (PlayerMale, PlayerFemale; Remnant, Stalker, Veilborn, Bulwark, Bearer, Colossus) | 433 | 433 MB |
| `Weapons` (22 archetypes, 9 Void Requiem, 6 sights, shared textures) | 496 | 780 MB |
| `Environments` (Nexus: the kit; NexusCity: ground, facades, props, trees; Meridian) | 722 | 2053 MB |
| `Props` (Loot, Reliquary), `Shared` (operation kit, map beacon) | 42 | 185 MB |
| `Audio` 292, `FX` 10, `UI` 3, `Materials` 19, `Abilities` 12, `Data` 7, `Input` 26, `Maps` 3 | | |

Sources: 48 scripts in `tools/blender`, 35 in `tools/blender/hero`. **The scripts are the editable source** (an asset
is rebuilt from them, never hand-edited); a `.blend` of any build is written with `--save` and is scratch.

## 2. Status by category, and what keeps each from the next step

| category | status | what it lacks against the specification |
|---|---|---|
| **Player bodies** (male, female: anatomy, faces, eyes, hair, face keys) | Technically complete | the owner's verdict; no facial animation; skin 4K held at 2K, not judged under neutral light |
| **Player outfit and armour** (the Orion male: the undersuit only, his outfit built to the owner's sheet on 2026-11-22 deleted the same day at their word, a new design of theirs comes; the female's outfit, helmets and headset; Void Sentinel in Blender only) | Concept (the male's armour) / Technically complete (the female's) / Work in progress (Void Sentinel) | cloth maps are 1024 px weaves (the male's take linear colours now); plate 1024, no baked maps; patches, panels and edge wear in corner colours (coarse: a vertex apart) |
| **Guns** (22 + 9) | Technically complete | modelled part by part and animated, but textured with TILING sets only: no unique UVs, no baked occlusion / curvature, no markings, wear not placed by use. **The reference rifle changes this** |
| **Sights** (6) | Technically complete | as the guns |
| **Enemies** (the six first bodies) | Work in progress | they are the old story's bodies: to be replaced by the Sarketh |
| **The Sarketh** (7 ranks, Blender only) | Work in progress (the Veteran's look: owner said "This looks great") | 104k-163k triangles (an enemy needs a fraction), corner-colour wear, no game export, no clips or voice of its own; the commander's suit is not a designed war suit |
| **Boss** (the Colossus) | Work in progress | old body; no damage states, no phase-specific geometry |
| **Nexus Prime** | Work in progress | buildings are facades on blocks (the specification's "building shells"): no interiors, no structure; ground redrawn 2026-11-14, facades and props not |
| **Meridian Fall** | Work in progress | mid-overhaul (`docs/operation/MERIDIAN_OVERHAUL.md`); main surfaces redrawn 2026-11-14 |
| **Props** (loot, reliquary) | Technically complete | old maps except the reliquary's plate |
| **Vehicles** | Work in progress | only wrecks in Meridian (dressing); none usable; none in Nexus Prime by the owner's rule |
| **VFX** | Technically complete | CPU particle cards by design (no Niagara) |
| **NPCs** | none | by the owner's rule (no people in Nexus Prime until asked) |

**Missing categories**: usable vehicles, NPCs, facial animation, weapon inspection animations, boss damage states,
other species, LODs for skinned meshes (none are authored).

## 3. What the pipeline can and cannot do today

Can: build any asset from a script (`build_all.sh`), export GLB -> FBX (`export_fbx.py`), import by step
(`SO_IMPORT_ONLY=...`), draw material sets at 4096 px with the full map list (`pbr.py`), refit physics bodies, run
117 automation tests, take fixed picture sets in the game, check two players.

Cannot yet (each is something the specification asks for):
- **unique UVs and baked maps** (occlusion, curvature, position, normal from a high-poly): nothing is baked; every
  hard surface is box- or world-mapped with tiling sets;
- **a painter's layering** (materials by part, wear from the baked maps, markings): done nowhere;
- **a neutral studio-light review** inside the game (the picture sets use the levels' own light);
- **per-asset cost** (triangles, draw calls, texture memory, shader cost) measured and recorded;
- **LODs** for skinned meshes.

## 4. Naming (established; names are an API to the code and the import)

| what | convention |
|---|---|
| Unreal assets | `SM_` static mesh, `SK_` skeletal mesh, `A_<Body>_<Clip>` clip, `MI_<material>` instance, `M_SO<Family>` material, `T_<file>` texture, `DA_<Thing>` data, `L_<Area>` map |
| materials | by ROLE, shared across assets: `gun_body`, `gun_metal`, `gun_glow*`, `orion_*`, `skin__<region>`, `sk_*`, `nx_*`, `nc_*`, `ru_*` |
| wardrobe | `C_<slot>__<item>`; gun models `gun_<archetype>`; gun parts by job (`mag`, `bolt`, `charge`, `slide`, `pump`, ...) |
| tiling texture sets | `<set>_c` albedo, `_n` normal (OpenGL), `_m` (R occlusion, G roughness, B metallic), `_h` height, `_e` emissive |
| an asset's own baked set (new) | `<asset>_u_m1` (R occlusion, G edge wear, B dirt), `<asset>_u_m2` (R handling, G heat, B painted marks), `<asset>_u_n` (engraving, welds, seams) |

The specification's folder tree (section 15) is read as categories on these folders: `Characters/Player` =
`/Game/Characters/Player<Sex>`, `Enemies` / `Bosses` = `/Game/Characters/<Species>`, `Weapons/<class>` =
`/Game/Weapons/<Archetype>`, `Environment` = `/Game/Environments/<Area>`, `Props` = `/Game/Props`, `Materials` =
`/Game/Materials`, `SourceFiles/Blender` = `tools/blender`.

## 5. Texture standard

| asset | source | held in the game | maps |
|---|---|---|---|
| hero weapon (in the hands) | tiling sets 4096 at 22 cm a tile; own baked set 4096 | tiling 4096 / 2048 mask; own set: wear / dirt and relief 4096, handling / heat / paint 2048 | full list + the baked set |
| player body, armour | 4096 | 2048 (4096 for the face when judged close) | full list |
| boss | 4096 | 2048-4096 | full list |
| standard enemy | 2048 | 2048 | full list |
| world surface walked up to | 4096 | colour and normal 4096, mask 2048, height 1024 | full list + detail layer |
| small prop | 2048 | 1024-2048 | full list |
| far skyline | 1024 | 512-1024 | colour, normal, mask |

A set is never upscaled (the old painters do not hold above 1024 px): it is redrawn. 4096 is the SOURCE; what the
game holds is the specification's budget, set per texture at import.

## 6. Material standard

One family, one material, instances for variation (`import_assets.py` builds them; never duplicate a material):

| the specification's family | here |
|---|---|
| painted / bare / brushed metal, rubber, plastic, ceramic, fabric, leather, concrete, stone, wood | `M_SOStandard` + the tiling set of that material, an instance per use |
| glass | `M_SOStandard` instance (masked / low roughness); facade glass in `M_SOFacade` |
| organic skin | `M_SOStandard` with the skin maps (no subsurface profile yet) |
| hair | `M_SOHair` |
| alien exoskeleton | the creatures' `hx_*` instances (old); the Sarketh's sets (not in the game) |
| energy surfaces | `M_SOEnergy`, `M_SOGlowPulse` |
| ground, facades, foliage | `M_SOGround`, `M_SOFacade`, `M_SOFoliage` |

Parameters `M_SOStandard` has: tint, roughness and metallic scales, emissive colour and strength, vertex-colour
amount, wear (edge, scratches, grime, bare metal, tiling), occlusion amount, parallax, detail (texture, scale,
strength, cavity), macro variation. Missing against section 9: **normal intensity** and **damage**.

## 7. Export and import (established)

Blender (metres, Z up, -Y forward) -> GLB -> `export_fbx.py` (static FBX in metres; skinned FBX in cm) ->
`import_assets.py` (the legacy FBX importer, normals and tangents imported, no auto collision, materials by name,
bodies refitted). Pivots: a moving part's origin is its pivot. Every asset is looked at IN the game after import
(`SOCaptureSeries`). Added for the specification: UV channel 1 kept (lightmap UVs not generated over it), an asset
review set (`SOCaptureSeries 1 29 -SOGuns=<archetype>`: the gun alone, each flank, three quarters, close on the
receiver, the markings, the muzzle), the asset's cost written to its report. Still to add: a neutral-light scene
in the engine (the review stands in the range's daylight; the neutral-light pictures are Blender's).

**Found on the reference rifle (2026-11-14), fixed in the import:** a static mesh imported AGAIN kept the material
slot names of its FIRST import, and slots were filled by those names, so a slot whose material had changed since
got the old one (the rifle's olive polymer grip was drawn in walnut, the magazine's parkerized catch in polymer).
`assign_materials` now names and fills every slot by what the file calls it (`imported_material_slot_name`). Every
gun rebuilt since its first import can carry the same fault until it is imported again.

## 8. The checklist (section 14, as it is checked here)

An asset's report answers each line with a measurement or a picture, never "looks fine":

**Geometry** - real proportions against its real class (measured); every edge bevelled or chamfered (no razor
edges); no holes, no parts inside parts, no flipped normals (Blender `--check`); silhouette read from front, side,
back, 3/4.
**Textures** - resolution per section 5; unique UVs: no overlap, stretch under 10 %, one texel density (measured);
no seam across a visible face; normal map checked green-up; roughness is a MAP with range, never one value.
**Materials** - metal is metal and paint is not (metallic 0 or 1, in between only where one wears to the other);
each material on the asset has its own roughness; emissive does not wash out its neighbours.
**Presentation** - pictures under neutral studio light, daylight, dark interior, coloured light, and close up; scale
beside a player.
**Technical** - import clean; collision; triangles, material slots, texture memory written down; the tests pass;
the animation that uses it still works.

Then its status is raised one step at a time; **Art-approved is the owner's word only**.

## 9. First assets to upgrade, in order

1. **The reference asset: the assault rifle** (`rifle`, `gun_rifle`). It is already built part by part with real
   mechanical construction; what it lacks is everything in section 3's "cannot yet". It becomes the benchmark.
2. After the owner approves it: the other guns through the same pipeline, the light guns first.
3. The Sarketh Veteran cut to an enemy's budget with baked maps, then into the game.
4. One Nexus Prime building as the reference for architecture (structure, an interior, a facade that is drawn).
5. The players' armour through the baked pipeline.

## 10. The reference rifle: what "complete" means for it

Kept: the model's construction, scale (94 cm), parts and pivots (the reload animations use them).
Added, each a piece of the pipeline every later asset uses:
- a second UV set, unique, one texel density, packed across the gun and its moving parts;
- baked from the model: ambient occlusion, object-space position and normal; from those, curvature;
- the painter's pass on the baked maps: edge wear where edges are and hands and slings rub, dirt where it
  collects, handling polish on the grip and the fore end, scratches at the magazine well and the charging handle,
  heat colour at the muzzle and the gas block, dust in the recesses;
- what is made on it: the maker's mark, a serial number, the selector's markings, proof marks, a weld line at the
  trunnion, the mould seam on the grip (engraved or painted into the gun's own maps: all ours);
- materials told apart on one gun (blued steel, parkerized steel, walnut, polymer, rubber), each its own roughness;
- in the game: its instances read the gun's own maps on UV 1 over the tiling sets on UV 0;
- judged under neutral light in a review scene, in first person at arm's length and close up, and its cost
  written down.

Status of the rifle: **Art-approved** (the owner, 2026-11-14: "Approved", asked whether it is approved as the
benchmark for the other guns). It is the benchmark: every other gun is brought to it through the same pipeline
and the same gate, the light guns first. What its report lists as not met stays open on the pipeline (a high-poly
model and a baked normal map first).

### The rifle's report (2026-11-14)

Build: `weapons.py -- rifle` (builds, unwraps UV 1, bakes on the graphics card, paints), `export_fbx.py ...
--split-parts`, `SO_IMPORT_ONLY=weapons,guntextures SO_WEAPONS_ONLY=rifle`; review `SOCaptureSeries 1 29`
(files `SO_r_rifle_*`).

**The gate** (`asset_check.py --class=weapon`, section 11): **PASS, 0 failed, 1 warning.** Its first run FAILED on
three points, each fixed in the pipeline, not on the one asset: 45 triangles without area (born when faces with
corners in a line were cut into triangles: `bakekit.clean` cuts every face the better way and deletes what is
still without area), 11.3 % of the surface stretched over a quarter on UV 1 (islands are now laid out again with
the least stretch after the projection: 5.7 %), and the brass on one flat value (a `wpn_brass` set was drawn).
The warning that stands: 37 % of the atlas lies on faces under other parts (the model is shells laid on shells;
cutting off and shrinking hidden islands was tried: it reached 5 % of the faces and packed worse, so it is off).
Measured: texel density 1.05 between densest and thinnest, .215 mm a texel at 4096, overlap .1 %, 54 % of the
atlas used, slivers 1.4 %, no loose geometry, no faces wound wrong.

**Cost.** 46,804 triangles (body, magazine, bolt, iron sights), 12 draw calls. 7 materials (blued steel,
parkerized steel, walnut, olive polymer, black polymer, rubber, brass). Tiling sets it wears: six, shared with every kinetic gun (colour and
normal held at 4096, mask at 2048, height at 1024). Its own maps: `_u_m1` and `_u_m2` held at 2048, `_u_m3` at
4096; about 17 to 34 MB in video memory by the compression the engine picks (worked out, NOT measured in the
engine). Texel density of the own maps .214 mm at 4096. One draw call a material a part. Source GLB 126 MB (it
still embeds the 4096 px tiling maps: the exporter should stop).

**Met.**
- Unique UVs on UV 1, nothing overlapping, one texel density, body and moving parts in one atlas.
- Baked from the model: occlusion, position, normal, material; curvature from those.
- Wear by place, checked in the game: rubbed edges are a broken line at the corner (the own map says how much,
  the shared mask's fine chips say where exactly, so it is crisp at any distance), the magazine well and the bolt's
  track rubbed bright, heat colour at the muzzle and gas block, dirt in hollows and packed into the engravings,
  handling polish on grip, fore end and controls.
- What is made on it reads in the game at a hand's breadth: "NEXUS PRIME ARSENAL / RIFLE 7 MM MK IV", the
  broken-ring mark, the serial number, S / F / A filled with paint, the calibre and proof marks on the right, weld
  beads at both trunnions, the grip's mould seam.
- Each material its own roughness and metalness: blued steel a metal, parkerizing a phosphate coat (not a metal;
  metal only where it is rubbed or cut), walnut, polymer and rubber not metal.
- The gas block is a clamp ring with its lug and cross bolts, a gas cylinder with its plug, a web and the sight's
  saddle (it was one chamfered box).
- Import clean (0 materials failed), the reload parts and pivots as they were.

**Not met, or not yet checked.**
- **High-poly and baked normals: a first pass (2026-11-15).** `bakekit.bake_highpoly_normals` makes the high-poly
  from the game model (every edge sharper than 35 degrees rounded by a 0.7 mm bevel in three steps, normals weighted
  by face area so flats stay flat: 106k faces against the game model's 47k) and bakes its normals in object space
  onto UV 1 (`gun_rifle_u_n`); the master material turns the surface onto them (`UniqueNormalTex`, no tangent frame
  on UV 1 needed). In the game: rounded, lit edges, no facet bands on the turned parts, nothing inverted. Not yet: a
  high-poly SCULPTED beyond the game model (castings' draft and fillets, the stamped receiver's radii, wood grain
  relief): what is baked now is the rounding of the game model's own edges. Rolled out to all eleven light guns
  the same day (auto, pulse, scout, handcannon, shotgun, sniper, rocket, smg, sidearm, hmg, energy: each passes the
  gate, high-poly 47k to 95k faces against game models of 21k to 45k; `SO_r_<gun>_*` reviewed in the game).
- 37 % of the UV 1 atlas is spent on faces that lie under other parts (measured by the gate). It goes away
  only with a welded model (one skin, the panels cut into it), which is the high-poly / low-poly step below.
- Neutral-light pictures are Blender's; in the engine the review stands in the range's daylight only. Dark
  interior and coloured light: not taken.
- The model itself is the limit now: the receiver's flank is a pressed box with panels laid on it, the magazine's
  ribs and the stock are simple forms, the walnut's figure is coarse. The gun rules' "no surface over 10 cm
  visually empty" holds on the receiver and the handguard, not on the stock (28 cm of walnut with a cheek flat).
- (Was open, now met: the maker's line and the serial number read at 60 cm as well as at 24. They had been
  smeared by the stretch of the first unwrap, not by the masks' size.)
- First person at 5 cm: not taken (the review's closest is 24 cm).
- Performance not profiled in a scene.

**Lessons for the next asset** (in the order they cost time): a gun with its own maps takes no wear from the
vertex colours (soft blobs on big faces) and little from the shared grime; nothing is rubbed on a flat without a
cause (a patch reads as a stain, a stroke as a soft block: a mask at .4 mm a texel cannot draw a hairline);
tiling sets carry little random rubbing and few pits, in patches; a rubbed edge is a line at the corner, bare
all the way only where it is most exposed (a band a chamfer wide read as white paint); look at the grip's
colour in the GAME (a stale slot name had given it the stock's walnut).

## 11. The gate (the owner's ruling of 2026-11-14)

"Approve: Substance Painter, ZBrush, Blender and AI-assisted starting models. Improve: Require a consistent,
repeatable asset pipeline with AAA-quality results. Keep strict: No unverified AI assets, poor topology, unfinished
textures or unoptimised models in the final game."

**One pipeline, whatever made the asset.** Start (a Blender script, a hand model, a ZBrush sculpt, an AI-assisted
model) -> the game-ready model on the project's names -> UV 0 for the tiling sets, a unique UV 1 (`bakekit.unwrap`)
-> bake (`bakekit.bake`) -> the painter's pass (our scripts on the baked maps, or a Substance Painter set exported
to the same three own maps) -> **the gate** -> FBX -> `import_assets.py` -> the review in the game -> the report
(cost, met, not met) -> a status. A tool is a way into the pipeline, never a way round it.

**The gate is `tools/blender/asset_check.py`** (`blender --background --python tools/blender/asset_check.py --
<model.glb> --class=<class> [--json=report.json]`; exit code 1 on a failure). It measures the model as it goes to
the import. An asset that fails, or has not been run, stays below Technically complete.

| the ruling | what is measured | fails when |
|---|---|---|
| poor topology | degenerate triangles; loose vertices / edges; faces wound against their neighbours; edges on more than two faces; slivers | any degenerate or loose; over .2 % wound wrong; (warn) over 1 % on three faces, over 5 % slivers |
| poor topology (UVs) | UV 1 inside 0..1; overlap; texel density, densest over thinnest; stretch; atlas used; atlas on hidden faces | overlap over 1 %; density over 1.6; over 10 % of the surface stretched more than a quarter; (warn) under half the atlas used, over a quarter on hidden faces |
| unfinished textures | every material has colour, normal and roughness / metal maps; the roughness has a range; the asset's own baked maps exist | a material on one flat value; a flat roughness; an own map missing |
| unoptimised models | triangles and materials against the class's budget; draw calls; triangles nobody can see | over budget; (warn) over 15 % of triangles under a quarter of a square millimetre |
| unverified AI assets | nothing an AI made goes round the gate: it is a START, retopologised, unwrapped and textured in the pipeline; its raw mesh and raw textures never ship | the asset's report does not say what made the start and what was kept of it |

**Budgets** (the project's own, set here on 2026-11-14 because the specification gives none in numbers: the owner
may change them; change them here and in `asset_check.CLASSES` together):

| class | triangles | materials |
|---|---|---|
| a gun in the hands, with its moving parts | 200,000 (the owner, 2026-11-15: "the weapons are one the the most important part of the game and the center focus of the player so the must look amazing, raise limit to 200k"; it was 60,000) | 12 (2026-11-15: a part made of its own material, steel, iron, titanium, polymer, rubber, on the owner's "apply a 4k metal/steel/iron/polymer/etc textures where needed"; it was 8) |
| a player with everything worn | 120,000 | 24 |
| a boss | 150,000 | 12 |
| a standard enemy | 40,000 | 6 |
| a vehicle | 80,000 | 10 |
| a prop | 15,000 | 4 |
| a building (Nanite: its fallback and its materials) | 250,000 | 16 |

**What the gate cannot judge:** silhouette, proportion, whether the wear tells the truth, whether it looks made.
That is the review in the game and the owner's word (Art-approved).

**Where the tools stand on this machine:** Blender 5.2 is installed and scripted. Substance Painter and ZBrush are
not installed, and no AI model generator is connected: nothing has been made with them. When one is used, the
asset's report names it.

## 12. The pipeline gun by gun (after the rifle's approval, 2026-11-14)

The rifle was approved as the benchmark; the light guns (the Sarketh's make) went through the same pipeline and
the same gate next. None needed a hand-written spec (`gunpaint.auto_spec` from what each builder says); each has
its own UV 1, baked maps, wear by place and the Sarketh's emblem and a line of their writing cut where the baked
flank has a clear, flat place. Gate reports: `unreal/ShatteredOrbit/Saved/gate_gun_<name>.json` (generated).
Review pictures: `Saved/Screenshots/SO_r_<archetype>_*`, sheets `light_guns_pipeline_left.png` / `_close.png`.

| gun | gate | triangles | materials | a texel (4096) | stretched | atlas hidden | warnings |
|---|---|---|---|---|---|---|---|
| `gun_rifle` | PASS | 46,804 | 7 | 0.215 mm | 5.7 % | 37 % | 1 |
| `gun_auto` | PASS | 40,500 | 8 | 0.261 mm | 3.3 % | 34 % | 2 |
| `gun_pulse` | PASS | 26,278 | 7 | 0.216 mm | 1.7 % | 35 % | 1 |
| `gun_scout` | PASS | 34,848 | 7 | 0.244 mm | 8.8 % | 39 % | 1 |
| `gun_handcannon` | PASS | 27,228 | 7 | 0.193 mm | 1.0 % | 52 % | 2 |
| `gun_shotgun` | PASS | 20,830 | 7 | 0.266 mm | 9.5 % | 47 % | 1 |
| `gun_sniper` | PASS | 43,214 | 7 | 0.278 mm | 7.8 % | 42 % | 1 |
| `gun_smg` | PASS | 26,234 | 8 | 0.211 mm | 8.1 % | 35 % | 1 |
| `gun_sidearm` | PASS | 19,998 | 7 | 0.124 mm | 0.4 % | 37 % | 1 |
| `gun_energy` | PASS | 26,644 | 8 | 0.284 mm | 1.3 % | 44 % | 1 |
| `gun_hmg` | PASS | 35,696 | 8 | 0.367 mm | 0.4 % | 37 % | 2 |
| `gun_rocket` | PASS | 38,984 | 8 | 0.458 mm | 0.1 % | 38 % | 1 |

All twelve are imported and reviewed in the game; 117 of 117 tests pass after them.

What the gate caught on the way (each fixed in the pipeline): flat gold trim (a `wpn_gold` set), the heavy machine
gun and the launcher stretched or collapsed on UV 1 (flat rings have two rims: `bakekit.unwrap_fit` goes to the
angle-based layout), the hand cannon had no room for a mark and a line (it carries the emblem alone). What the
game showed that the gate cannot: marks that were a smudge because the texture streamer held the own maps
several mips too small (`USOEditorLibrary::SetTextureSampling`).

**Status of the eleven light guns: Technically complete** (the gate passes, reviewed in the game). NOT
Art-approved: that is the owner's word, and their models are unchanged, so what the rifle's report lists as not
met holds for them too, more so: big flat pale shells (the gun rules' "no flat panels", "nothing over 10 cm
empty"), no high-poly model or baked normal map, a third or more of each atlas under other parts. On the side
arm and the lance the mark fell on dark iron, where it is faint. Still to go through: the seven other kinetic
guns (`SO_GUN_OWN=all`; they need their makers' lines), the three living guns, the nine Void Requiem guns.
