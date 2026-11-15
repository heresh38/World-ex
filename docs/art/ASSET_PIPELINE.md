# Project Orion: the art-production specification (the owner, 2026-11-14)

The owner's message, word for word. It is PERMANENT: every asset made for the game from here on is made to it.
How it sits beside the project's hard rules, and where the two differ, is at the end (`How it is applied here`).
Its first task (the audit, the standards, the checklist, one reference asset) is `ASSET_AUDIT.md`.

---

permanent Project Orion art-production specification

PROJECT ORION — MASTER AAA 3D ASSET QUALITY AND PRODUCTION PIPELINE

ROLE

Act as a senior AAA 3D artist, technical artist, character artist, environment artist, hard-surface modeller, material artist, texture artist and Unreal Engine 5 technical artist.

Your responsibility is to establish and implement a professional 3D asset production pipeline for Project Orion.

The objective is to create exceptionally detailed, realistic, visually impressive, commercially usable 3D assets suitable for a modern AAA-quality sci-fi looter shooter.

Every asset must look professionally manufactured, sculpted, textured, lit and integrated.

Do not settle for basic models with generic materials, flat colours, simplistic geometry or low-quality AI-generated textures.

A model that technically works is not necessarily a finished asset.

Visual quality is a primary requirement.

⸻

1. OVERALL VISUAL QUALITY STANDARD

Every asset must meet a consistent production-quality standard.

Prioritise:

* Realistic proportions.
* Convincing silhouettes.
* High-quality geometry.
* Clean topology.
* Accurate surface materials.
* High-resolution textures where justified.
* Detailed normal maps.
* Realistic roughness variation.
* Proper metallic response.
* Micro-surface detail.
* Believable manufacturing details.
* Subtle imperfections.
* Realistic reflections.
* Appropriate surface wear.
* Correct physical scale.
* High-quality shading.
* Professional presentation.

Assets must look convincing from multiple camera distances and lighting conditions.

Do not rely on excessive glowing effects, strong colour grading or dramatic lighting to disguise poor geometry or materials.

The model must look good even under neutral lighting.

Avoid the appearance of:

* Plastic-looking metal.
* Flat, lifeless textures.
* Perfectly sharp edges.
* Repetitive procedural details.
* Generic AI-generated geometry.
* Blurry texture maps.
* Unrealistic material reflections.
* Empty surfaces.
* Excessively clean manufactured objects.
* Random decorative details without purpose.

Every detail should have a visual, structural, functional or narrative reason to exist.

⸻

2. SOFTWARE AND PRODUCTION WORKFLOW

Use the following production tools where appropriate.

Blender

Primary software for:

* 3D modelling.
* Hard-surface modelling.
* Organic modelling.
* Sculpting.
* Retopology.
* UV unwrapping.
* Geometry Nodes.
* Modifiers.
* Rigging.
* Basic animation.
* Collision preparation.
* Asset export.

Preserve editable .blend source files.

Substance 3D Painter

Use for:

* PBR texturing.
* Material layering.
* Scratches.
* Edge wear.
* Dirt.
* Dust.
* Rust.
* Paint damage.
* Surface imperfections.
* Labels.
* Decals.
* Material variation.

ZBrush (where available)

Use for:

* Detailed creature sculpting.
* Character anatomy.
* Organic surfaces.
* High-poly sculpting.
* Complex armour.
* Fine sculptural details.

Do not require paid software when Blender can produce the required result.

Unreal Engine 5

Use for:

* Final material implementation.
* Material instances.
* Lighting.
* Rendering.
* Collision.
* Physics.
* Animation.
* Niagara effects.
* Nanite where appropriate.
* LODs.
* Texture streaming.
* Final quality inspection.

⸻

3. GEOMETRY AND MODELLING STANDARDS

Geometry must be intentionally designed.

Do not create finished assets from disconnected primitives or simplistic shapes unless the design specifically calls for them.

Every model must have:

* Correct proportions.
* Believable thickness.
* Proper structural construction.
* Clean intersections.
* Correct surface transitions.
* Appropriate edge treatment.
* Consistent scale.
* Appropriate geometry density.
* Correct normals.
* No accidental holes.
* No unintended overlapping geometry.
* No visible shading artifacts.

Hard-surface modelling

For weapons, armour, vehicles, machinery and architecture:

* Use appropriate bevels.
* Create believable panel gaps.
* Include structural seams.
* Use realistic component thickness.
* Model mechanical connections.
* Create properly fitted components.
* Avoid floating decorative elements.
* Use clean Boolean workflows where appropriate.
* Use weighted normals where suitable.
* Avoid razor-sharp edges on manufactured objects.

Manufactured metal objects should have appropriate edge rounding so that lighting produces convincing highlights.

Organic modelling

For characters, creatures and bosses:

* Prioritise believable anatomy.
* Create natural transitions between body parts.
* Avoid arbitrary surface noise.
* Ensure deformation-friendly topology.
* Build believable joints.
* Create detailed facial structures where applicable.
* Use sculpted forms rather than relying entirely on textures.
* Ensure the silhouette remains recognisable from a distance.

⸻

4. HIGH-POLY AND GAME-READY MODEL WORKFLOW

For assets that benefit from high-poly baking, use a high-poly and low-poly workflow.

High-poly version

Create detailed geometry for:

* Bevels.
* Engravings.
* Mechanical details.
* Sculpted surfaces.
* Fine shape transitions.
* Small manufactured details.

Game-ready version

Create an optimised version with:

* Clean topology.
* Appropriate polygon density.
* Correct UVs.
* Correct normals.
* Suitable collision.
* Appropriate LODs where needed.

Bake appropriate details from the high-poly model onto the game-ready model.

Support:

* Normal maps.
* Ambient occlusion.
* Curvature.
* Position maps.
* Thickness maps where appropriate.

Do not use unnecessary high-poly geometry when a normal map can produce the same visual result more efficiently.

Use Nanite selectively for suitable static geometry. Do not assume every asset should use Nanite.

Characters, deforming objects and specialised meshes still require appropriate topology and optimisation.

⸻

5. PROFESSIONAL PBR TEXTURING

All major assets must use a physically based material workflow.

Support the following texture maps where appropriate:

1. Base Color / Albedo.
2. Roughness.
3. Metallic.
4. Normal.
5. Ambient Occlusion.
6. Height or Displacement.
7. Opacity.
8. Emissive.

Each map must serve its intended purpose.

Base Color

Use realistic material colours.

Avoid unrealistic colour variation or excessive painted detail.

Roughness

Roughness must vary according to the actual material.

Examples:

* Polished metal.
* Brushed steel.
* Painted metal.
* Rubber.
* Glass.
* Ceramic.
* Fabric.
* Organic surfaces.

Do not assign one generic roughness value to an entire complex object.

Metallic

Metallic values must accurately distinguish metallic and non-metallic materials.

Do not make plastic, rubber or painted surfaces metallic simply to create stronger reflections.

Normal maps

Use normal maps to create detailed surface definition without unnecessary geometry.

Inspect for:

* Incorrect green-channel orientation.
* Baking artifacts.
* Seams.
* Inconsistent tangent space.
* Incorrect shading.

Texture resolution

Use sensible texture budgets.

Initial targets:

* Hero characters: 2K–4K.
* Hero weapons: 2K–4K.
* Bosses: 2K–4K.
* Standard enemies: 2K.
* Armour: 2K–4K.
* Major environment assets: 2K–4K where justified.
* Small props: 1K–2K.
* Distant objects: 512–1K where appropriate.

Use texture streaming, shared materials and texture atlases where appropriate.

Do not use 4K or 8K textures without a visual or technical justification.

⸻

6. SURFACE REALISM AND MICRODETAIL

This section is extremely important.

A professional model must not look like a perfect computer-generated object.

Create controlled surface variation.

Depending on the material, include:

* Fine scratches.
* Edge wear.
* Fingerprints.
* Dust.
* Dirt accumulation.
* Paint chipping.
* Subtle dents.
* Manufacturing marks.
* Engraved markings.
* Surface roughness variation.
* Small imperfections.
* Fabric weave.
* Leather grain.
* Concrete pores.
* Metal brushing.
* Organic skin detail.

Use wear logically.

For example:

* Exposed edges should show appropriate wear.
* Recesses can accumulate dirt.
* Frequently handled areas may show fingerprints.
* Metal joints may show mechanical abrasion.
* Footwear should show ground contact wear.
* Buildings should show environmental damage consistent with their age and location.

Do not apply random scratches uniformly across every surface.

Wear must tell a believable story.

⸻

7. ASSET-SPECIFIC PRODUCTION REQUIREMENTS

Different asset categories need different standards.

A. Player characters

Create:

* Realistic anatomy.
* High-quality faces.
* Detailed eyes.
* Realistic skin materials.
* Hair and facial hair.
* Clothing.
* Layered armour.
* Believable fabric.
* Mechanical armour components.
* Proper joints.
* Animation-ready topology.
* Rigging.
* Skin weights.
* Facial animation support where needed.

Male and female characters must have properly designed proportions and compatible equipment systems.

Armour must fit the character rather than appearing to float over the body.

B. Weapons

Weapons must look like functional manufactured objects.

Include:

* Receiver.
* Barrel.
* Muzzle.
* Magazine.
* Grip.
* Stock.
* Sights.
* Rails.
* Screws.
* Mechanical joints.
* Heat vents.
* Energy components where appropriate.
* Engravings.
* Labels.
* Surface wear.

Separate moving components when necessary.

Prepare weapons for:

* First-person presentation.
* Third-person presentation.
* Reload animations.
* Firing animations.
* Inspection animations.
* Attachment systems.

Create believable mechanical construction, even for futuristic energy weapons.

C. Enemies and creatures

Create:

* Distinct silhouettes.
* Believable anatomy.
* Detailed skin or exoskeleton.
* Appropriate material variation.
* Unique faces and heads.
* Claws, teeth or other anatomical features.
* Detailed joints.
* Animation-ready topology.
* Custom rigs.
* Attack and movement animations.

Creatures must not look like recoloured copies of one another.

D. Bosses

Bosses must have exceptional visual quality.

Include:

* Large-scale anatomical design.
* Complex silhouettes.
* Unique armour.
* Distinctive weak points.
* Detailed organic and mechanical materials.
* Custom animations.
* Attack-specific geometry.
* Damage states.
* Phase-specific visual changes.

A boss must be visually memorable even before the player engages it.

E. Buildings and environments

Create believable architecture.

Include:

* Structural support.
* Windows.
* Doors.
* Roofs.
* Interiors.
* Staircases.
* Machinery.
* Pipes.
* Electrical components.
* Signs.
* Furniture.
* Structural damage.
* Environmental debris.
* Vegetation.
* Weathering.

Do not produce unfinished-looking building shells as final assets.

Build modular architecture that can be reused intelligently.

F. Vehicles

Include:

* Proper body construction.
* Mechanical components.
* Wheels or propulsion systems.
* Suspension where applicable.
* Cockpits.
* Seats.
* Interior details.
* Functional access points.
* Damage states.
* Realistic materials.

⸻

8. UV UNWRAPPING AND TEXTURE QUALITY CONTROL

Every textured asset must have properly prepared UVs.

Check:

* Stretching.
* Overlapping.
* Texture distortion.
* Wasted UV space.
* Texel density.
* Seam placement.
* Normal map compatibility.

Use consistent texel density across assets of similar importance.

Use UV layouts appropriate to the asset.

Where mirrored or overlapping UVs are used, ensure that they do not interfere with unique markings, damage, decals or baked lighting information.

⸻

9. MATERIAL CREATION IN UNREAL ENGINE 5

Create reusable material systems.

Do not create hundreds of unnecessary duplicate materials.

Build reusable material families for:

* Painted metal.
* Bare metal.
* Brushed steel.
* Rubber.
* Glass.
* Plastic.
* Ceramic.
* Fabric.
* Leather.
* Concrete.
* Stone.
* Wood.
* Organic skin.
* Alien exoskeleton.
* Energy surfaces.

Support material instances for easy variation.

Create configurable parameters for:

* Base colour.
* Roughness.
* Metallic.
* Normal intensity.
* Emissive intensity.
* Surface wear.
* Dirt.
* Damage.
* Tint.
* Opacity.

Use physically plausible values.

Do not overuse emissive lighting.

Energy components should appear bright without destroying the visibility of nearby geometry.

⸻

10. LIGHTING AND FINAL PRESENTATION

Every asset must be evaluated under multiple lighting conditions.

Test:

1. Neutral studio lighting.
2. Bright daylight.
3. Dark indoor lighting.
4. Coloured artificial lighting.
5. Low-light combat conditions.
6. Close-up inspection lighting.

Check:

* Reflections.
* Roughness.
* Material separation.
* Silhouette.
* Surface detail.
* Normal maps.
* Shadow behaviour.
* Visual readability.

Do not rely on cinematic lighting alone to make an asset look impressive.

The model must remain visually convincing under ordinary gameplay lighting.

⸻

11. BLENDER TO UNREAL EXPORT PIPELINE

Create a consistent export pipeline.

Preserve:

* Editable Blender source.
* Texture source files.
* High-poly source where applicable.
* Low-poly game model.
* UV layouts.
* Material information.
* Rigging information.
* Animation source.

Use appropriate FBX or other supported interchange formats.

Ensure:

* Correct units.
* Correct scale.
* Correct orientation.
* Correct naming.
* Correct pivots.
* Correct smoothing.
* Correct normals.
* Correct material assignments.
* Correct skeletal hierarchy.
* Correct animation export.

Verify every asset inside Unreal Engine after import.

Never assume an asset will look identical in Blender and Unreal.

⸻

12. OPTIMISATION AND PERFORMANCE

Visual quality must be balanced with real-time performance.

Use:

* Appropriate polygon budgets.
* LODs.
* Nanite where suitable.
* Texture streaming.
* Material reuse.
* Efficient collision.
* Instancing.
* Efficient shader complexity.
* Proper shadow settings.
* Appropriate skeletal mesh complexity.

Avoid:

* Unnecessary material slots.
* Excessive transparent materials.
* Excessive draw calls.
* Excessive overdraw.
* Unnecessary high-resolution textures.
* Unoptimised skeletal meshes.
* Unnecessary geometry hidden inside other geometry.

Profile assets in Unreal Engine.

Do not guess performance.

⸻

13. AI-GENERATED ASSET QUALITY CONTROL

AI-generated 3D models may be used as starting points.

However, they must pass professional quality checks before entering the game.

Inspect:

* Mesh integrity.
* Geometry.
* Topology.
* UVs.
* Texture resolution.
* Material assignments.
* Scale.
* Normals.
* Collision.
* Rigging.
* Animation compatibility.
* Commercial licensing.

Repair or rebuild assets when necessary.

Never accept a visually attractive preview as proof that the exported model is game-ready.

Preserve source files and document any AI-generated assets and their licensing conditions.

⸻

14. AUTOMATED QUALITY-CONTROL CHECKLIST

Create an asset review checklist.

Every important asset must pass these categories:

Geometry

* Correct shape.
* Clean topology.
* No broken geometry.
* Correct normals.
* Proper edge treatment.

Textures

* Correct resolution.
* Proper UVs.
* No major stretching.
* No unwanted seams.
* High-quality normal maps.
* Appropriate roughness.

Materials

* Correct physical response.
* Realistic reflections.
* Proper material separation.
* No excessive plastic appearance.
* Correct emissive behaviour.

Presentation

* Looks good in neutral lighting.
* Looks good in gameplay lighting.
* Correct scale.
* Good silhouette.
* No obvious visual defects.

Technical

* Correct export.
* Correct collision.
* Appropriate LOD or Nanite configuration.
* Acceptable memory usage.
* Acceptable rendering cost.
* Correct animation compatibility.

Classify every asset as:

* Concept.
* Blockout.
* Work in progress.
* Technically complete.
* Art-approved.
* Game-ready.
* Shipping-approved.

Do not call a model AAA quality simply because it has a high polygon count or 4K textures.

⸻

15. ASSET PRODUCTION ORGANISATION

Establish a clean asset library.

Suggested structure:

ProjectOrion/
Assets/
Characters/
Player/
NPCs/
Enemies/
Bosses/
Weapons/
AssaultRifles/
SMGs/
Shotguns/
Snipers/
EnergyWeapons/
HeavyWeapons/
Armour/
Vehicles/
Environment/
Buildings/
Interiors/
Industrial/
AlienStructures/
Props/
Materials/
Textures/
VFX/
Animations/
Audio/
SourceFiles/
Blender/
Substance/
Sculpting/

Use consistent naming conventions.

Keep source assets separate from exported game assets.

Do not overwrite original source files without backups.

⸻

16. IMPLEMENTATION AND FIRST TASK

Do not attempt to remodel the entire game at once.

First inspect the existing Project Orion project and determine its current asset-production capabilities.

Then:

1. Audit the existing asset folder.
2. Identify low-quality or placeholder assets.
3. Identify missing asset categories.
4. Inspect existing Blender and Unreal import workflows.
5. Establish naming conventions.
6. Establish texture standards.
7. Establish material standards.
8. Establish an export pipeline.
9. Create an asset quality checklist.
10. Identify the first assets that should be upgraded.

Then create one complete reference-quality asset.

Recommended first asset: a Project Orion assault rifle.

It must include:

* High-quality modelling.
* Detailed mechanical construction.
* Clean topology.
* Proper UVs.
* PBR textures.
* Realistic roughness.
* Metallic materials.
* Normal details.
* Surface wear.
* Correct scale.
* Proper Unreal Engine materials.
* First-person and third-person compatibility where appropriate.

Use this weapon as the benchmark for future asset production.

Once approved, use the same pipeline for characters, armour, enemies, bosses, vehicles and environments.

⸻

FINAL QUALITY REQUIREMENT

Project Orion must not look like a collection of basic 3D models assembled inside a game engine.

It must look like a professionally produced game with a consistent art direction and carefully developed assets.

Every weapon should look manufactured.

Every character should look believable.

Every creature should have a convincing anatomy and material design.

Every building should look architecturally complete.

Every environment should feel physically present.

Every surface should respond convincingly to light.

Prioritise quality, consistency, detail and technical correctness.

The goal is not merely to create more assets.

The goal is to create fewer, exceptionally good assets first, establish a repeatable professional production pipeline, and then scale that quality across the entire game.

---

## How it is applied here

### The owner's ruling on tools (2026-11-14, word for word)

> Approve: Substance Painter, ZBrush, Blender and AI-assisted starting models.
> Improve: Require a consistent, repeatable asset pipeline with AAA-quality results.
> Keep strict: No unverified AI assets, poor topology, unfinished textures or unoptimised models in the final game.

This settles the first two rows of the table below, and replaces the hard rule "every 3D model and texture is made
in Blender by our own scripts" (CLAUDE.md):

- **Allowed to make an asset with:** Blender (scripts or by hand), Substance Painter, ZBrush, and an AI-assisted
  model as a STARTING point. Nothing else was approved: bought or downloaded third-party models and textures are
  still not brought in, and Epic's sample characters are still only measured side by side.
- **One pipeline whatever the tool:** every asset, however it was started, ends the same way: a game-ready model on
  the project's naming, unique UVs at the standard texel density, the full PBR set, the import through
  `import_assets.py`, a review in the game, a report with its cost, a status. A tool is a way into the pipeline,
  never a way round it.
- **Nothing reaches the game unverified:** the gate is `tools/blender/asset_check.py` (ASSET_AUDIT.md section 11).
  An asset that fails it, or that has not been run through it, stays below "Technically complete". An AI-assisted
  start is recorded in the asset's report (what made it, what was kept of it) and is retopologised, re-UV'd and
  textured in the pipeline like anything else: its raw mesh and its raw textures never ship.
- Read here, not said by the owner (ask if it matters): "AI-assisted starting models" covers MODELS; AI-made
  textures are not approved as final textures (the specification's own section 1 warns against them).
- A fact, not a rule: neither Substance Painter nor ZBrush is installed on this machine and neither can be driven
  without a person at it, so what is built from here is still built by Blender scripts; when the owner or an
  artist brings a sculpt, a painted set or an AI start, it enters at the bake / import step and meets the same gate.

The specification stands beside the project's hard rules (CLAUDE.md) and the two texture rule lists
(`TEXTURE_RULES.md`, `GUN_TEXTURE_RULES.md`). Where it and a hard rule differ, the stricter one holds until the
owner rules (the same convention as the master brief: `docs/orion/ARCHITECTURE.md`).

| the specification | the hard rule or the fact | what is done until the owner rules |
|---|---|---|
| section 2: Substance 3D Painter for texturing, ZBrush for sculpting, "where appropriate" (RULED 2026-11-14: both approved; the rest of this row is how it stands until someone uses them) | "Every 3D model and texture is made in Blender by our own scripts"; and neither program can be driven from here (they are interactive, licensed tools) | Blender and our own scripts do both jobs: the layering a painter does (materials by part, wear from baked curvature / occlusion / position, dirt, decals) is done by `tools/blender` scripts on baked maps. The spec itself says not to require paid software when Blender can produce the result |
| section 13: AI-generated models "may be used as starting points" | "Never add third-party models/textures" | RULED 2026-11-14: approved as starting points, verified through the gate, recorded in the asset's report; none has been used so far |
| section 15: a `ProjectOrion/Assets/...` folder tree | the game is `unreal/ShatteredOrbit` with `/Game/Characters`, `/Game/Weapons`, `/Game/Environments`, ... (asset folders and names are an API to the code and the import) | the tree is read as CATEGORIES mapped onto the existing folders (`ASSET_AUDIT.md`), never a second tree; sources stay in `tools/blender` (scripts) and saved `.blend` builds |
| section 5: 2K-4K by importance, "do not use 4K or 8K textures without a visual or technical justification" | `TEXTURE_RULES.md`: "hyper realistic 4k" | sources are written at 4096; what the GAME holds follows this section's budgets (set per texture at import) |
| section 4: a high-poly and a game-ready model, details baked | so far the guns and armour are one model with tiling maps | this is the pipeline change the reference rifle establishes: unique UVs, baked normal / occlusion / curvature / position, layered wear from them |
| section 16: do not remodel the whole game at once; one reference asset first | | the audit, then ONE assault rifle to the full standard, shown to the owner; nothing else is rebuilt before it is approved |
