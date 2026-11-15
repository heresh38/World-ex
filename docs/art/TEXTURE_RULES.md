# Texture rules (the owner, 2026-11-14)

The owner's words, in order, word for word. They apply to EVERY texture in the game.

> okay so basically any texture such as brick/rock/grass/steel/etc anything that was imported from the browser build
> of the game should be replaced by you, i want hyper realistic 4k triple a textures.

> the rules i just posted with the info should be for all textures to ensure our world is truly alive

## The rules

TEXTURE QUALITY
- Ultra-sharp detail at close viewing distances.
- No blurry areas.
- No AI smearing.
- No visible seams.
- No stretching.
- No repeated patterns.

PBR WORKFLOW
Generate all required texture maps:
- Albedo/Base Color
- Normal
- Roughness
- Metallic
- Ambient Occlusion
- Height/Displacement
- Optional Emissive

REALISM RULES
- Every material must contain micro details.
- Surface imperfections are mandatory.
- Dirt accumulation in realistic locations.
- Edge wear.
- Small scratches.
- Dust buildup.
- Weathering.
- Natural color variation.
- Age variation.

MATERIAL EXAMPLES

CONCRETE
- Fine aggregate detail.
- Hairline cracks.
- Dirt in recesses.
- Water stains.
- Surface wear.
- Roughness variation.

METAL
- Machining marks.
- Tiny scratches.
- Fingerprint variation.
- Edge wear.
- Oxidation.
- Realistic reflections.

WOOD
- Accurate grain direction.
- Knots.
- Age variation.
- Surface scratches.
- Micro roughness.

STONE
- Real geological structure.
- Fractures.
- Mineral variation.
- Moss buildup.
- Surface erosion.

FABRIC
- Visible fibers.
- Weave patterns.
- Compression folds.
- Tension stretching.
- Fraying edges.

Avoid:
- Procedural-looking repetition
- Plastic materials
- Over-sharpening
- Cartoon appearance
- Flat roughness values
- Perfectly clean surfaces

## How they are met here

Every texture is still made by our own scripts (the hard rule in CLAUDE.md: nothing third-party, no photographs).
What the rules add to that:

- **One engine** (`tools/blender/pbr.py`) writes every set with the full map list: `<name>_c` (albedo), `_n` (OpenGL
  normal, relief in several scales), `_m` (R ambient occlusion, G roughness, B metallic), `_h` (height) and `_e`
  where a surface gives light.
- **4096 px** for what is walked up to; a second, finer **detail layer** in the material for what the eye gets
  closer to than a texel is wide.
- **Repetition is broken in the material**, not only in the map: a second, larger-scale variation over the tile.
- What each kind of material must show (concrete, metal, wood, stone, fabric) is the list above; a set that lacks
  one of them is not finished.

The state of the work against these rules, set by set, is kept in `docs/art/TEXTURE_STATE.md`.
