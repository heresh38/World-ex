# The textures against the owner's rules

The rules: `TEXTURE_RULES.md` (every texture) and `GUN_TEXTURE_RULES.md` (guns). This file says, set by set, what
meets them and what does not yet. Keep it honest: a set is "drawn" only when it was made through the texture engine
(`tools/blender/pbr.py`) at 4096 px with the full map list and its material's own detail in it.

State on 2026-11-14.

## What "meets the rules" means here, and what it cannot mean

Every texture is made by our own scripts (a hard rule): no photographs, no scans, nothing third-party. A drawn set
has real relief, wear, dirt and variation, and its maps agree with each other because they come from one height
field. It is NOT a photo-scanned surface, and it will not pass for one beside the best scanned libraries: say so
rather than call a set photoreal. Where a set still looks drawn, the cure is more of its material's own structure
in the painter, not a filter.

Three things a tiling map cannot do, whatever its quality, and where they are done instead:
- hold up closer than its texels: the material's **detail layer** (`detail_maps.py`, half a millimetre a texel);
- not read as a repeat from across a square: the material's **macro variation** (laid at a scale that is not a
  whole number of tiles);
- know WHERE on an object it is (a gun's grip, a wall's foot): the object's own vertex colours / places, in the
  material.

## The engine and the materials

| piece | state |
|---|---|
| `pbr.py` (albedo, normal, AO + roughness + metallic, height, emissive; everything in metres) | done |
| master material `M_SOStandard`: AO from the mask's red, parallax from the height map, detail normal, macro variation | done; each is off until an instance asks |
| `M_SOGround` (Nexus Prime's ground): detail normal, AO from the mask's red | done; no parallax or macro variation there yet |
| `M_SOFacade` (Nexus Prime's walls): detail normal | done; no AO (its mask's red is the window glass), parallax or macro variation |
| in-game size: colour and normal 4096, mask 2048, height 1024 | done for the world's engine sets |

## Drawn through the engine at 4096 px, full map list

| sets | where | notes |
|---|---|---|
| `nx_stone` `nx_paving` `nx_panel` `nx_trim` `nx_window` `nx_rock` | Nexus Prime's kit (the spire, the wall, the gates, the halls) | these descended from the browser build; `nx_window` has its own emissive map now |
| `panel` `concrete` | the reliquary | from the browser build; only `panel` is in the game |
| `nc_asphalt` `nc_pavers` `nc_plaza` `nc_kerb` `nc_lot` `nc_grass` `nc_roof` `nc_dirt` `nc_wall` | Nexus Prime's streets, pavements, plaza, kerbs, yards, lawns, roofs, bare ground, the city wall | redrawn (`city_maps.py`); a lived-in city: worn and stained, not broken |
| `ru_concrete` `ru_fracture` `ru_asphalt` `ru_stone` `ru_metal` `ru_panel` `ru_rubble` `ru_ceramic` `ru_sandstone` `ru_corrugate` `ru_box_red/green/ochre` `ru_tile` `ru_plaster` `ru_brass` | Meridian Fall | redrawn; the old painters do not hold above 1024 px |
| `wpn_paint` `wpn_metal` `wpn_steel` `wpn_park` `wpn_poly` `wpn_odg` `wpn_wood` `wpn_knurl` | every gun | 22 cm a tile: a twentieth of a millimetre a texel |
| `wpn_anod` `wpn_brushed` `wpn_titanium` `wpn_carbon` `wpn_rubber` | no gun yet | drawn; a gun wears one when its parts are given it (a rebuild of that gun) |
| `det_stone` `det_concrete` `det_metal` `det_asphalt` `det_soil` `det_plaster`, `macro` | every engine set's material; Nexus Prime's ground and facades (detail only) | 1024 px, half a metre a tile |

## Not redrawn (old painters, old sizes): do NOT meet the rules

| sets | made by | size | what is wrong |
|---|---|---|---|
| `ncf_*` (Nexus Prime's facades: every building's walls and windows), `np_*` (its props), `nc_tunnel` `nc_rail` `nc_steel` `nc_rock` | `nexus_city_textures.py` | 512 / 1024 | a nearly flat normal, no AO or height; the facades have the detail layer only. The facades are the biggest gap left in the city: a bay's window layout and its glass mask are part of the map, so each must be redrawn with its layout kept |
| `ru_banner` `ru_hive` `ru_composite` `ru_far_a/b` `ru_bark` `ru_leaf` `ru_moss` `ru_fungus` `ru_wood` `ru_fabric` `ru_ceiling` `ru_shutter` `ru_carpet` `ru_goods` `ru_books` | `ruins_textures.py` | 1024 | as they were (they go through the engine for AO and height the next time they are built, at 1024) |
| `tread` `asphalt` `rock` `sand` `ice` `moss` `hazard` `facade` `ribbon` `carbon` | `textures.py` (Cycles, 512 px, from the browser build) | 512 | not in the game (nothing imports them); delete with `textures.py` or redraw when something needs one |
| `bio_flesh` `bio_bone` `bio_sac` (the living guns), `hx_*` (creatures) | `weapon_textures.py`, `horror_textures.py` (Cycles) | 2048 / 1024 | baked noise; no AO or height |
| the players' cloth, leather, rubber; the plate (`polymer`) | `hero/fabric.py` | 1024 | the plate was redrawn in two scales but is 1024 px with no AO or height; the cloths are weaves at 1024. The Orion male's outfit passes its palette as LINEAR colours (`make(..., linear=True)`, encoded to sRGB as written); the older sets store the colour given as sRGB bytes (a linear value given that way comes out up to ten times darker) |
| the players' skin, eyes, hair | `hero/skinmaps.py`, `hero/hair.py` | 4096 written, 2048 held | not looked at against these rules |
| the Sarketh's armour and cloth | `hero/sarketh_surface.py` | 1024 / 2048 | approved by the owner as a look; not on the engine, no AO or height; not in the game |
| the wear masks, effect cards, UI | | | not surfaces in the rules' sense; not looked at |

## Guns against the gun rules

Met: the full map list; the eight materials the guns wear, each with its own roughness, micro scratches, wear,
oxidation; the five further materials drawn.

NOT met, and why it is not a texture job alone:
- **Wear by place** (grip, magazine well, charging handle, heat colour at the barrel, holster side): a tiling map
  does not know where on the gun it is. Needs each gun's places given to its material.
- **Markings** (serial numbers, safety markings, a maker's mark): need marking decals placed on each gun.
- **Built detail** (fasteners, pins, screws, panel breaks, service panels, vents, weld lines, mould seams; nothing
  over 10 cm empty): is modelling in `gunparts.py` / `weapons.py`, gun by gun.
- **The seven materials on one gun**: the parts must be given them in `weapons.py`.
- **The 5 cm inspection test**: not tried.

All four are a rebuild of every gun.

**Started on the reference rifle** (`gun_rifle`, 2026-11-14; `bakekit.py`, `gunpaint.py`): it has its own unique UV
set and baked maps, wear placed by use (edges, grip, fore end, comb, controls, the bolt's track, the magazine well,
heat at the muzzle and the gas block, dirt in the hollows), and its markings (maker, model, serial number, the
maker's mark, selector letters, calibre, proof marks, welds, the grip's mould seam). Reviewed in the game (capture
set 29); its report, with its cost and what is not met, is `ASSET_AUDIT.md` section 10. Still open on it: the
seven materials on one gun (it has blued steel, parkerized steel, walnut, olive and black polymer, rubber, brass),
built detail beyond what the model has, a high-poly model to bake a normal map from, the inspection test at 5 cm,
the owner's verdict. No other gun has any of this.

**The guns' tiling sets after the rifle's review (2026-11-14):** `wpn_steel`, `wpn_park`, `wpn_poly`, `wpn_odg`
carry little random rubbing now and their pits in a few patches (WHERE a finish is rubbed is an asset's own maps'
work; on a gun with none, the game's per-copy wear layer's); parkerizing is a phosphate coat, not a metal, and its
crystals are fine. Every gun wears these, so every kinetic gun's finish is a little darker and cleaner than it was.
