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

## The edge of the route: things, not unseen walls (the owner, 2026-11-11)

"allow the player to enter any buildings he can see the door ... use the buildings walls as the barrier ... rubble or
maybe something else collapsed blocking the other side ... don't just use invisible walls."

How it is built: a row of buildings beside the route IS the edge (`citykit.building(front=...)`, `rk.tower(face=...)`):
each has a street door (and shop windows) into a ground floor with a floor, what stood in its rooms and a fall of
rubble against its back wall; its other three sides are blind and whole for three storeys, no balcony below the
fourth, nothing lower than 7 m to climb to. Every gap between two of them is closed by something that was put or
fell there (`tools/blender/boundskit.py`, all over 7.7 m: a double jump and a clamber reach about six): freight boxes
stacked three and four high, the quarantine's and the army's wall sections with wire, floors that slid into an
alley and stand on edge, a palisade the Altered grew, a steel palisade that is seen through. What is left of the
unseen walls is a NET behind those things (`MR_blockers`, laid last): a player who touches it has found a way out,
and the game logs where (`Boundary net touched at E .. N ..`). Check a district's edge on a plan without the game:
`SO_BOUNDS_DEBUG=<file.json> blender -b -P tools/blender/meridian.py -- --noexport --zones=<zones>,blockers`.

| District | Edge now | Still an unseen wall where a player walks |
|---|---|---|
| Ashfall Verge | both rows walked into (26 buildings), freight boxes between them, across the road out behind the pad and on the ring road's deck | none known |
| The Stacks | the street's rows and quarantine wall, the gatehouse's forecourt walled, the yard's two blocks walked into (six doors), a row of ground-floor rooms behind the alley's walls | none known |
| Galleria | its own walls; forecourt and loading yard flanks 8.4 m; the station's head wall over the stair | none known |
| Deepline | underground: its own walls | none |
| The Sluice | the banks are walked now: rows walked into, grown palisades and collapses between, the annex walked into, a steel palisade round the cooling plant's yard, the portal house and the dam's gate house at the ends | none known |
| Causeway | the rows walked into, the army's wall and collapses between, the wall across the step where its rows meet the Approach's; the stage's energy wall now stands across the Causeway past the spillway's apron (at the ramp's foot it was walked round along the bank) | none known |
| Approach | rows walked into, the army's wall between them up to the city wall; freight boxes on the viaduct's deck | none known |
| Meridian Gate | the city wall; the court's flanks walked into, collapses between | none known |
| Boulevard | the lots' towers walked into, every alley closed by a collapse or a grown palisade | none known |
| Concord Ring | its thirteen towers walked into from the plaza, the breaches between them grown shut (north and west) or fallen in, grown palisades from the two by the ramp to its side walls | none on the ground |
| Ramp, High Terraces, Crown Bridge, the Crown | no unseen wall over any balustrade (the owner: a fall costs what it costs, and a jump before the ground saves it). A fall lands in the yard under the terraces (closed in by eight towers walked into from it, what fell or grew between them, and the backs of the ring's towers) or on the ground round the Crown (a ring of grown ribs, open south to the yard). Ways back up: the ramp's low side walls, the rubble under the north deck, two plates of the broken ring lying against the Crown's rim | none known |

Not checked by anyone playing. Upper storeys: a lid at about 9 m still stops a climber over the estate, the alley, the
mall and its yards.

## Stages and status

| Stage | What | Status |
|---|---|---|
| 1 | Audit | done (above) |
| 2 | Art direction, architectural language | done (above); texture sets `ru_ceramic`, `ru_composite`, `ru_sandstone`, `ru_corrugate`, `ru_tile`, `ru_plaster`, `ru_brass`, `ru_far_a/b` |
| 3 | Buildings and landmarks | first pass in: `tools/blender/citykit.py` (complete buildings, then damaged; six styles chosen per district in `meridian.ZONE_STYLES`; furnished rooms behind breaches; roof plant; a textured skyline) replaces every bare frame; the gatehouse, mall and station are re-clad (ceramic, composite, tile, plaster, bronze). Second pass: a landmark per district (`meridian_landmarks.py`): the Verge's control tower and the sign gantry over the jam, the Stacks' three housing slabs tied by sky bridges, the Galleria's entrance arch, pylon and atrium vault, Deepline's stair canopy and ring sign, the research annex with its silo, pipe bridge and two cooling towers on the Sluice's west bank, the gunship down across the Causeway, the Assembly's dome over the Ring. The skyline's low blocks are textured facades. To do: the wall's bunkers, more facade variety inside a style, signage, landmarks seen from further down the route |
| 4 | Destruction, debris, abandoned human infrastructure | first pass in: `streetkit.py` + `meridian_story.py` (the evacuation jam and the bus at the Verge, quarantine at the Stacks, the shelter's cots in the Galleria, bedding and the stranded train in Deepline, the annex's containment tanks at the Sluice, the army's emplacements, carriers and floodlights on the Causeway and Approach, the Boulevard stopped mid-afternoon). To do: the downed gunship, the Ring and Terraces, bigger collapses Second pass: a rubble mound is one material with its broken pieces lying in and on it (lumps, blocks, floor slabs laid to the slope; the two materials split face by face drew a sawtooth), the road's flat polygon potholes are washes of grit with no edge, the cooling plant's yard on the Sluice's east bank |
| 5 | The alien vegetation ecosystem | first pass in: `alienflora.py` + `meridian_flora.py` (climbers up the buildings from recorded anchors, growth over the rubble, hanging strands, roots, trees through the rotunda and the yard's fountain, fungus and lanterns in the tunnel, pads and wall growth in the canal; denser toward its sources; textures `ru_bark`, `ru_leaf`, `ru_moss`, `ru_fungus`, light `ru_bio`). Second pass: buildings consumed where the growth is densest (`alienflora.consume`: trunks up the corners, curtains off the roof edge, moss over the walls; up to 16, from `citykit.BUILDINGS`), moss sheets on walls and ground, flowers (`ru_petal`), creepers strung across the streets, trees through the paving (alley, boulevard, verge, causeway), a grove in the canal bed, more in the Galleria. Moss is colonies of small cushions lying on the surface under them (a mound gives its own height: `rk.HEAPS[..][3]`), lanterns are smooth drops, flowers are hanging bells with separate petals. To do: still thinner than the brief in the Verge and the Stacks; no wind; leaves are flat cards |
| 6 | Streets, interiors, small props | streets: lane lines, curbs, pavements, drains, manholes, washes of grit, signals, signs, shelters, bollards (in). Interiors, second pass: `tools/blender/interiorkit.py`. The Galleria's 100 shops each have a front (glazed with its doors parked open, shutter down, shutter stuck, shutter forced), a name in bars of light, a suspended ceiling with fallen tiles and the duct over it, and a fit-out by trade (clothing, market, cafe, electronics, books, pharmacy, shops the shelter spread into, stripped ones); the bays the hold's waves come out of are always open and clear (a shuttered one used to be able to trap its wave); ducts, trays, the sprinkler main and strip lights hang under both gallery slabs; directories and bins on the concourse. Seven new texture sets (wood, cloth, ceiling tile, shutter, carpet, stocked shelves, book spines). Every building on the route's edge now has a ground floor to walk into (below). To do: ceilings and doors in the gatehouse rooms, the ticket hall and the pump house; shop interiors are lit only by a lamp in one of four; the enterable buildings' rooms are sparsely furnished |
| 7 | Lighting, fog, materials, atmosphere | first pass in: a low sun under the storm's edge (long shafts between the towers), brighter sky fill and exposure, plant light (`bio`), lamps, moonlight shafts. To do: per-district grading, light shafts tuned by eye in the editor, puddles and wet reflections |
| 8 | Mission route and boss arena | not started (the route is unchanged and still passes its checks) |
| 9 | Gameplay, navigation, collision, multiplayer test | re-run after every stage: `SOCaptureSeries 1 9` on L_Meridian (13 nav legs, 250 spawns), the automation suite. Not played by a person; multiplayer not tested |
| 10 | Performance profile, visual consistency | not started (Meridian's loaded size and frame rate are not yet measured after the overhaul) |

How to see it before importing: `blender -b <saved build> -P tools/blender/meridian_preview.py -- <outdir> [shot ...]`.
