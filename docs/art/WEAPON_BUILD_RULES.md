# Weapon build rules

The owner's rules for how EVERY weapon is built (2026-11-15, given on the Sarketh assault rifle and then, in the owner's
words, "keep/save those rules we have for building all weapons so they have the correct things required"). They stand
beside `GUN_TEXTURE_RULES.md` (how a gun's surface is painted), `TEXTURE_RULES.md` and `ASSET_PIPELINE.md`; where two
rules differ, the stricter one holds until the owner rules. Every weapon, human or alien, any class.

## The owner's words

First message, word for word:

> gun looks good but too flat, here are some things you can add to fix it, ralistic engineering. Layered mechanical
> components, ergonomic grip, trigger guard, removable power cell, cooling vents, maintenance panels, recessed muzzle,
> sensors, targeting optics, visible fasteners, overlapping armor plates, varied materials, realistic proportions,
> believable manufacturing, functional design language, depth and thickness, not flat, not blocky, detailed from every
> angle, game-ready hero asset.

Second message, word for word:

> The weapon currently looks like a single flat blob/panel. Break up all large flat surfaces into multiple overlapping
> components. Add a separate upper receiver, lower receiver, ergonomic grip, trigger guard, magazine or power cell
> housing, barrel shroud, cooling vents, maintenance hatches, access panels, fasteners, bolts, seams, recessed sections,
> bevels, panel gaps, rails, sensor modules, and attachment points.
>
> Create a hierarchy of detail:
> - large primary forms
> - medium mechanical assemblies
> - small technical details
>
> Increase thickness and dimensionality throughout the weapon. Introduce depth changes, cutouts, negative space,
> recessed grooves, layered armor plates, exposed internal mechanisms, and believable manufacturing logic.
>
> Every component should have a purpose:
> power source, heat dissipation, maintenance access, aiming system, structural support, and ammunition or energy feed
> system.
>
> Use AAA game art quality similar to Destiny 2, Halo Infinite, Titanfall, Call of Duty, and Mass Effect weapon design.
> Realistic proportions, functional engineering, hard-surface industrial design, highly detailed but readable.
>
> Avoid:
> flat panels,
> single-piece blob shapes,
> featureless surfaces,
> unbroken rectangles,
> toy-like proportions,
> random greebles with no function.
>
> The weapon should look manufactured, assembled from many distinct parts, and believable from every angle.

Third message (2026-11-15, on the first assembled Sarketh rifle): "now add to the gun body, it's too simple to be an
alien gun". An alien species' weapon must look like THEIR making, not a human rifle with alien colours (see
"An alien weapon" below).

The games named are a quality target only: nothing (names, shapes, parts) is taken from them.

## What every weapon must have (the checklist)

A weapon is not shown to the owner, and not past Work in progress (`ASSET_AUDIT.md`), until each line is met or its
absence is explained by what the weapon is (a blade has no muzzle; a grenade no grip).

**Primary forms** (the silhouette; readable at a distance)
- Real proportions: a rifle about a metre long, a receiver about 9-12 cm deep and 5-7 cm wide; a handgun about
  20-25 cm. Measured against the hands (`ShatteredOrbit.Hold.*`), never scaled up from a drawing.
- Depth and thickness everywhere: every section changes along the gun (swell, waist, taper); nothing is an extrusion
  of a side outline; it reads from the top, the front, below and behind as well as from the side.
- Separate upper receiver and lower receiver, a barrel shroud / handguard, a stock (or brace), a grip.

**Medium assemblies** (each has a purpose, named in the builder's comment)
- Power source / ammunition: a removable power cell or magazine (its own part, `mag`, the reload takes it out) in a
  housing or well; how it feeds the gun is visible (a feed line, a contact, a port).
- Heat dissipation: cooling vents, louvres, fins or an open cage where the heat is made (the emitter, the chamber).
- Maintenance access: at least one hatch or access panel, held by visible fasteners.
- Aiming system: a rail and a sight or targeting optic; sensor modules (rangefinder, illuminator) where the gun's
  role wants them.
- Structural support: a chassis the shells are fastened to; bands, collars, trunnions where loads meet.
- Control: ergonomic grip, trigger guard, trigger, selector, the cell / magazine catch, charging handle where it has one.
- Attachment points: rail, sling points front and rear.
- Recessed muzzle (or the class's own crown / emitter face set back inside its shroud).
- Exposed internal mechanism somewhere it makes sense (a coil through a cage, a bolt through a port).

**Small technical details**
- Fasteners and bolts where parts are joined (not scattered): screws round a hatch, studs at a plate's ends.
- Seams and panel gaps between parts; recessed grooves; bevels on every edge; cut-outs and negative space.
- Overlapping armour plates over the chassis, each standing proud with a chamfered edge.
- Varied materials: at least the body, a second metal or plate, a dark chassis, rubber at the hands, glass, light,
  fittings (the gate's limit is 8 materials).

**Never**
- Flat panels, unbroken rectangles, featureless surfaces, a single-piece blob, a side outline extruded into a slab.
- Toy-like proportions.
- Random greebles: every part answers one of the purposes above.

## An alien weapon

A species' weapon is that species' making (its materials, its way of joining, its light), and still obeys every line
above: an alien gun is engineered too. It must not read as a human rifle wearing alien colours: its body carries the
species' own forms (for the Sarketh: grown, layered chitin and pale forged plates swept back, ribbed carapace bands,
energy conduits running between the parts, crystal / light set into the structure; see `docs/story/WORLD.md` and the
species' design sheet).

## Sights and scopes

The owner, 2026-11-15, word for word: "ensure that the scopes have a unique look and feel, not just the normal red
dot, it should function the same but look must be blended in with the gun to ensure it belong on it". A sight works
exactly as the game's sights do (the same eye line, the dot or reticle on the sight's axis, a window as wide, an
optic's glass centred on the axis: `ShatteredOrbit.Aim.EverySightOnTheEyeLine`), but its look is the gun's own: its
materials, its shapes, its maker's language, sitting on the gun's own mount (an alien gun never carries a human rail or
a human red dot). The Sarketh's: `sarketh_guns.skr_sight` (the lozenge window of their emblem in a dark lacquer frame
with a gold rim, the pale brow swept back over it, a crystal throwing an amber lozenge reticle, forged iron base held by
pale claws on their toothed mount). A magnified scope for a gun is made the same way, by that gun's maker.

## One palette a set

The owner, 2026-11-15, word for word: "all guns in the set need to have the same color pallet and shoot the same
color, this is our rule going forward, so for example this must apply to current gun sets too like light guns that
seem to be shooting different colors". Every gun of a set (or, with no set, of its class's family: light, kinetic,
horror) has the set's materials and colours, fires the set's colour (rounds, bolts, slugs, trails, flashes, rockets)
and carries the set's light: `Data/game_data.json` "palettes", read by the import for every gun; nothing per gun.

## The budget

The owner, 2026-11-15, word for word: "the weapons are one the the most important part of the game and the center
focus of the player so the must look amazing, raise limit to 200k so we can get triple a 4k looking guns". A gun in
the hands may have up to 200,000 triangles (`asset_check.CLASSES["weapon"]`, `ASSET_AUDIT.md` section 11) and 12
materials, its own maps at 4096 px. Each part wears the 4K set of what it is made of (the owner, 2026-11-15: "apply a
4k metal/steel/iron/polymer/etc textures where needed as some parts look too bland and not realistic"): machined steel
for bolts and pins (`wpn_steel`), forged iron for a chassis (`wpn_metal`), titanium for cages and turned parts
(`wpn_titanium`), polymer for grips, guards and housings (`wpn_poly`), rubber where hands and shoulder go
(`wpn_knurl`), brass, gold, glass; never one surface for everything. The detail goes where it is seen: the hands' view, the muzzle, the receiver's
flanks and top. Because a gun is drawn many times (the two stowed on each player, every enemy's), a gun others hold or
that is far away will need a lighter copy made from the same model (levels of detail): to be added to the pipeline
before guns are given to the enemies in numbers.

## How it is checked

- Built with the hard-surface kit (`tools/blender/gunparts.py`: `Body` chassis + `shell` / `slats` / `light` /
  `collar` / `studs`, `loft` / `sloft`, `box_mag`, `grip`, `guard`, `cage`, `coil`, `louvre`, `hexbolts`, rails and
  sights in `weapons.py`), never a traced or extruded outline as the finished body.
- Looked at from every side before it is shown: side, three-quarter, top, front, below, behind, and close on the
  muzzle (`tools/blender/skr/gunsheet.py`, `VIEWS=side,quarter,top,front,under,back3q,muzzle`).
- Passes the gate (`tools/blender/asset_check.py --class=weapon`) and the texture rules.
