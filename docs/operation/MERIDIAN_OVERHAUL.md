# Meridian Fall: from prototype to final build

The owner, 2026-11-10: "for the operation think of our current art as the prototype and what I said upgrade to final
build." The rules are `ART_DIRECTION.md`. The prototype is commit `607d56d` (the backup the rules ask for).
This file is Stage 1 (the audit), Stage 2 (the art direction per district) and the running status of the stages.

## Stage 1: audit of the prototype

What works and is kept: the route (2.5 km, 20 stages, `tools/operation/meridian_plan.py`), the encounters, the exact
collision meshes, the nav mesh (13 legs connect), the spawn audit (250 of 250), one area loaded at a time.

What reads as unfinished (the reason for the overhaul):

| Problem | Where | Cause |
|---|---|---|
| Buildings are bare frames: slabs, columns, a spandrel band, no walls or windows | every district (150+ towers) | `ruinkit.tower` built a skeleton |
| The skyline is the same frame, repeated | backdrop (220 towers + 800 grey boxes) | same |
| One grey concrete everywhere; no cladding, glass, trim, signage | everywhere | nine texture sets, all ruin surfaces |
| Hand-built interiors are concrete boxes | gatehouse, mall, station | walls and floors in `ru_concrete` / `ru_panel` / `ru_stone` |
| Districts differ in layout only, not in architecture | all | one tower style |
| Streets are flat sheets: no lane lines, curbs, drains, potholes, wrecks | verge, alley, causeway, approach, boulevard | one asphalt slab per street |
| The alien presence is purple chitin only; no plant life, nothing grows through anything | all | only `hive_growth`, `pod`, `alien_spire` |
| Props are few and generic (jersey barriers, hedgehogs, boxes) | all | no vehicle, furniture or infrastructure kit |
| Storytelling is thin: nothing says what happened in each place | all | no authored set pieces |
| One lighting mood (storm night); interiors lit by a few lamps | all | one directional light, per-zone point lights only |
| The mall's shops and the canal's banks are bare | galleria, sluice | first pass |

## Stage 2: art direction

One city, Meridian, the old capital: white ceramic and dark glass with bronze trim, long horizontal lines, rounded
civic stone at its centre. It fell in a day (the evacuation jammed, the army held the wall and lost), and for years
since an alien ecosystem has been growing through it from the canal and the tunnels outward.

Each district has its own architecture (`citykit.STYLES`, chosen per zone in `meridian.ZONE_STYLES`), its own story
and its own light:

| District | Architecture | What happened here | Light |
|---|---|---|---|
| Ashfall Verge | logistics sheds in corrugated sheet, transit offices, gantries, the toll plaza | the evacuation: a jam of abandoned cars, luggage, a shuttle that never left | open low sun through haze, long shadows |
| The Stacks | ceramic-clad housing: balconies, condensers, washing lines, a walled yard | quarantine: sealed doors, a barricaded lobby, lives left mid-day | warm emergency lamps inside, teal plant-light in the yard |
| Meridian Galleria | a composite-and-glass arcade, bronze rails, shop fronts and signs | the shelter that was overrun: queue barriers, cots, a tree through the rotunda | shafts through the fallen skylight, dying signs |
| Deepline | a tiled station, the stranded train, service corridors | where people hid, and where the nest took hold | dark; bioluminescence and red emergency light |
| The Sluice | waterworks and the research annex on the bank | where it began: burst containment tanks, growth pouring into the canal | mist, green-cyan glow, sun across the top |
| Causeway, Approach, Gate | the army's line: prefab barricades, emplacements, the wall | the last stand: wrecked carriers, spent positions, a downed gunship | fires and failing floodlights |
| Boulevard, Concord Ring | civic stone and glass towers, colonnades, the monument | the capital's heart, emptied | cold open sky, the beam's light on stone |
| High Terraces, the Crown | government terraces, sky gardens run wild, the platform | the hive's seat | the beam |

The alien ecosystem is its own design language (Stage 5): rope-thick vines that climb and wrap, roots that split
concrete, hanging curtains from the high floors, broad fleshy leaves, shelf fungus, glowing bulbs, moss; densest at
the canal and the tunnel (its source), thinning toward the Verge.

## Stages and status

| Stage | What | Status |
|---|---|---|
| 1 | Audit | done (above) |
| 2 | Art direction, architectural language | done (above); texture sets `ru_ceramic`, `ru_composite`, `ru_sandstone`, `ru_corrugate`, `ru_tile`, `ru_plaster`, `ru_brass`, `ru_far_a/b` |
| 3 | Buildings and landmarks | first pass in: `tools/blender/citykit.py` (complete buildings, then damaged; six styles chosen per district in `meridian.ZONE_STYLES`; furnished rooms behind breaches; roof plant; a textured skyline) replaces every bare frame; the gatehouse, mall and station are re-clad (ceramic, composite, tile, plaster, bronze). Second pass: a landmark per district (`meridian_landmarks.py`): the Verge's control tower and the sign gantry over the jam, the Stacks' three housing slabs tied by sky bridges, the Galleria's entrance arch, pylon and atrium vault, Deepline's stair canopy and ring sign, the research annex with its silo, pipe bridge and two cooling towers on the Sluice's west bank, the gunship down across the Causeway, the Assembly's dome over the Ring. The skyline's low blocks are textured facades. To do: the wall's bunkers, more facade variety inside a style, signage, landmarks seen from further down the route |
| 4 | Destruction, debris, abandoned human infrastructure | first pass in: `streetkit.py` + `meridian_story.py` (the evacuation jam and the bus at the Verge, quarantine at the Stacks, the shelter's cots in the Galleria, bedding and the stranded train in Deepline, the annex's containment tanks at the Sluice, the army's emplacements, carriers and floodlights on the Causeway and Approach, the Boulevard stopped mid-afternoon). To do: the downed gunship, the Ring and Terraces, bigger collapses Second pass: a rubble mound is one material with its broken pieces lying in and on it (lumps, blocks, floor slabs laid to the slope; the two materials split face by face drew a sawtooth), the road's flat polygon potholes are washes of grit with no edge, the cooling plant's yard on the Sluice's east bank |
| 5 | The alien vegetation ecosystem | first pass in: `alienflora.py` + `meridian_flora.py` (climbers up the buildings from recorded anchors, growth over the rubble, hanging strands, roots, trees through the rotunda and the yard's fountain, fungus and lanterns in the tunnel, pads and wall growth in the canal; denser toward its sources; textures `ru_bark`, `ru_leaf`, `ru_moss`, `ru_fungus`, light `ru_bio`). Second pass: buildings consumed where the growth is densest (`alienflora.consume`: trunks up the corners, curtains off the roof edge, moss over the walls; up to 16, from `citykit.BUILDINGS`), moss sheets on walls and ground, flowers (`ru_petal`), creepers strung across the streets, trees through the paving (alley, boulevard, verge, causeway), a grove in the canal bed, more in the Galleria. Moss is colonies of small cushions lying on the surface under them (a mound gives its own height: `rk.HEAPS[..][3]`), lanterns are smooth drops, flowers are hanging bells with separate petals. To do: still thinner than the brief in the Verge and the Stacks; no wind; leaves are flat cards |
| 6 | Streets, interiors, small props | streets: lane lines, curbs, pavements, drains, manholes, potholes, signals, signs, shelters, bollards (in). Interiors: finished materials (in); to do: ceilings services, doors, more furniture, the mall's shops |
| 7 | Lighting, fog, materials, atmosphere | first pass in: a low sun under the storm's edge (long shafts between the towers), brighter sky fill and exposure, plant light (`bio`), lamps, moonlight shafts. To do: per-district grading, light shafts tuned by eye in the editor, puddles and wet reflections |
| 8 | Mission route and boss arena | not started (the route is unchanged and still passes its checks) |
| 9 | Gameplay, navigation, collision, multiplayer test | re-run after every stage: `SOCaptureSeries 1 9` on L_Meridian (13 nav legs, 250 spawns), the automation suite. Not played by a person; multiplayer not tested |
| 10 | Performance profile, visual consistency | not started (Meridian's loaded size and frame rate are not yet measured after the overhaul) |

How to see it before importing: `blender -b <saved build> -P tools/blender/meridian_preview.py -- <outdir> [shot ...]`.
