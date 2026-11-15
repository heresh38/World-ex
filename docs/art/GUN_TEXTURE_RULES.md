# Gun texture rules (the owner, 2026-11-14)

The owner's words, word for word: "this rule is for gun textures so remember these too and apply it." They stand
beside `TEXTURE_RULES.md` (which is for every texture) and add what a weapon in particular must show.

## The rules

PBR MAPS REQUIRED
- Albedo
- Normal
- Roughness
- Metallic
- Ambient Occlusion
- Height
- Emissive (where applicable)

MANUFACTURING DETAIL
Every weapon must appear physically manufactured.

Include:
- CNC machining marks
- Mold seams
- Weld lines
- Fasteners
- Rivets
- Pins
- Screws
- Maintenance panels
- Engraved serial numbers
- Safety markings
- Manufacturer logos

REALISTIC METAL
Metal must contain:
- Micro scratches
- Directional wear
- Edge polishing
- Holster wear
- Handling marks
- Oxidation
- Burn marks near barrel
- Roughness variation

WEAPON GRIP MATERIALS
- Rubber texture
- Surface wear
- Hand oils
- Compression damage
- Dirt accumulation
- Grip pattern wear

PAINT AND COATINGS
- Surface chipping
- Worn edges
- Impact scratches
- Maintenance repair marks
- Faded paint
- Uneven weathering

SCI-FI WEAPON RULES

NO FLAT PANELS.

Every surface must contain:
- Panel breaks
- Service access points
- Mechanical layers
- Heat vents
- Cooling systems
- Attachment points
- Functional engineering details

No surface larger than 10cm should remain visually empty.

WEAR STORYTELLING

Weapon should reveal how it was used:

- Grip area heavily worn
- Magazine insertion scratches
- Charging handle wear
- Sight adjustment marks
- Barrel heat discoloration
- Dust accumulation in recesses

MATERIAL CONTRAST

Use:
- Anodized metal
- Brushed steel
- Titanium
- Carbon fiber
- Polymer
- Ceramic coating
- Rubber grips

Each material should have unique roughness values.

FIRST PERSON INSPECTION TEST

Player can rotate weapon within 5cm of camera.

When inspected:
- New details continue appearing.
- Surface information feels endless.
- No flat or empty areas visible.

QUALITY TARGET

Match or exceed:
- Destiny 2 Exotic weapons
- Call of Duty MW weapon blueprints
- Star Citizen weapon assets
- Escape From Tarkov weapon realism

Avoid:
- Plastic appearance
- Perfectly clean surfaces
- Flat roughness maps
- Generic sci-fi panels
- Empty geometry
- Uniform materials

## What this asks of our pipeline

The games named are a QUALITY target only: nothing of theirs is copied (hard rule: no names, terms or text from
other games; every model and texture from our own scripts). Markings, serial numbers and makers' logos are ours.

The rules fall into three kinds, and each has its own place in the pipeline:

1. **What a material is** (machining marks, micro scratches, oxidation, roughness variation, rubber, coatings, the
   seven materials each with its own roughness): the tiling material sets, written through `tools/blender/pbr.py`
   with the full map list (`tools/blender/surface_maps.py`).
2. **Where on THIS gun** (grip worn, scratches at the magazine well, the charging handle, heat colour at the
   barrel, dust in the recesses, holster wear on the high side): cannot live in a tiling map. It needs each gun's
   own places (muzzle, grip, magazine well, controls) given to the material, and the gun's own occlusion.
3. **What is built or marked** (fasteners, rivets, pins, screws, panel breaks, service panels, vents, weld lines,
   mould seams, serial numbers, safety markings, the maker's mark): geometry and marking decals on each gun
   (`gunparts.py`, `weapons.py`), with the rule that no surface over 10 cm stays empty.

The state of the guns against these rules is kept in `docs/art/TEXTURE_STATE.md`.
