# Player proportions: references and decisions

The players (`anatomy.py`, `players.py`) are checked against Epic's engine references and adult anthropometry.
The Epic meshes are **measured only**. They are exported to a scratch folder, never imported into our project, and
never shipped:

- Manny / Quinn (`Templates/TemplateResources/High/Characters/Content/Mannequins`)
- the MetaHuman template head and archetype body (`Engine/Plugins/MetaHuman/...`: `SM_MH_Head`, `SKM_Face`, `SKM_Body`)

## Body

Fractions of standing height H. Real values are means from Drillis–Contini.

| | ours (male / female) | Manny | real |
|---|---|---|---|
| hip joint | .519 / .519 | .518 | .53 |
| knee | .283 / .282 | .278 | .285 |
| shoulder joint | .822 / .820 | .795 | .818 |
| upper arm | .183 | .154 | .186 |
| forearm | .142 | .151 | .146 |
| hand (wrist to fingertip) | .109 / .111 | (bones only) | .108 |
| head (crown to chin) | H/7.7 / H/7.4 | – | H/7.6–7.8 |

- **Heights:** male 1.82 m, female 1.64 m.
- **Hand scale:** `HAND_SCALE` (anatomy) is shared with the finger rig (`export_fbx.finger_chains`).
- **Fingers:** checked against real phalanx tables and against Manny / MetaHuman:
  - each finger runs proximal : middle : distal ≈ 1 : .6 : .45;
  - index ≈ .9 × middle, ring ≈ .94, little ≈ .75.

## Head

The head is compared side by side with the MetaHuman head: true scale, eye lines aligned, orthographic front and
profile.

1. **Skull above the brow.** `CRANIUM` is MetaHuman's measured mid-line outline and width, with the ears excluded. It
   is anchored at the eyelid surface and given in our design units. This fixed three faults of the first build:
   - a receding forehead, with the eyes bulging ahead of it (now about 1.7 cm behind the brow);
   - a crown leaning back like a cone (the vertex is now above the ears);
   - a skull about 3 cm short front to back.
2. **Widths.** The face is ×1.11 at the cheekbones and ×1.04 at the jaw, giving cheekbones about 14 cm (male). The
   eyes keep their real spacing: pupils 64 / 62 mm apart, eyeballs 24 mm. A narrow face had made them look too far
   apart.
3. **Lower face.** The nose, lips, muzzle and chin sit at MetaHuman's depth relative to the eyelids: the nose tip
   about 4 cm ahead, the chin about 1.6 cm ahead.
4. **Nose.** One lofted form (`Head.NOSE`), not stacked primitives:
   - root about 1 cm above the eye line;
   - root to base about 5.5 cm (male);
   - tip about 2 cm proud of the face;
   - dorsum 11–14 mm wide;
   - alae 35 mm wide (female 31);
   - about 130° at the root and about 100° under the nose.
5. **Mouth.** About 52 mm wide (male), 48 mm (female).
6. **Ears.** They run from brow level to the nose base:
   - centre about 1.2 cm under the eye line;
   - ear canal about 8 cm behind the eye (MetaHuman's ear joint);
   - on the side of the widened skull.
7. **Jaw and eyes.**
   - Lower jaw: pupil to chin about 11 cm.
   - Eye openings: about 10–11 mm high (they were slits).

## How we check

`Unreal side-by-side`: Epic's head and ours go into one scene of a scratch project (never ours), with the same clay,
light and 30° lens, eye lines aligned. Eight views plus a cyan/orange overlay (cyan Epic, orange ours: a colour fringe
is a mismatch). Scripts: `tools/reference/`. In game, `SOCaptureSeries 1 3` shoots both bodies from
the same eight angles, as worn and bald.

## Body build (`tools/reference/body_measure.py`, `body_views.py`, `body_sheet.py`)

Ours against Manny (male), Quinn and MetaHuman's archetype body (both female), at true scale on a 10 cm grid. Front,
side and back views, with overlays. The MetaHuman body is a female form, so the male is compared with Manny.

- **Male (strong, 1.82 m):**
  - shoulder joints 1.2 cm further out;
  - chest about 26 cm deep, about 104 cm round (it was 22 / 89);
  - waist kept at about 80, for a V-taper;
  - fuller glutes, thighs, calves (about 39 round) and upper arms.
- **Female (slim, 1.64 m):**
  - waist about 63 cm, hips about 88–90;
  - slimmer arms and legs.
- **Female face (cute):**
  - slightly larger eyes with brighter openings;
  - a smaller, shorter, slightly upturned nose;
  - fuller lips on a smaller mouth;
  - a small round chin, softer jaw and higher cheeks.

## Skin and hair

- **Face:** `skin.py` gives the head cylindrical UVs and bakes three maps from its 3D surface:
  - colour: lips, warm cheeks, nose and ears, under-eye tone, lash line, and the male beard shadow with stubble;
  - normal: pores, lip lines, forehead lines and crow's feet;
  - roughness.

  They go on the `skin_face` material (Unreal slot `skin__head`).
- **Body:** a tiling 8 cm detail set (`skin_detail_*`) on box-projected UVs, with pores and the fine cross-hatched
  creases of body skin.
- **Brows:** a 1024 × 256 strand atlas per style with about 600 crisp, tapered hairs.
- **Hair:** a 2048 atlas with strands about 0.05–0.1 mm wide, 1.8× more cards per style, and narrower cards.

## Morph targets

The face presets are shape keys with default weight 0. `players.py` sets them to 0, because Blender 5 creates new
keys at 1. `export_fbx.py` also zeroes them on import, so the Unreal base mesh is always the rest face.

## Guns

Overall lengths after `weapons.GUN_SCALE`, in cm. Real comparisons are in brackets.

| Group | Guns |
|---|---|
| Rifles | assault rifle 94 (AK 88), carbine 85 (M4 84), auto rifle 95, scout 102, DMR 110 (M14 112), bolt-action 115 (105–117), sniper 129 (AWM 120, Barrett 145) |
| Shotguns | pump 100 (870 18-inch 96), shotgun 89 |
| Handguns | pistols 22–23 (Glock 17 19–20), revolver 27, hand cannon 33 |
| SMGs | 72–76 (MP5 70) |
| Heavy | HMG 90, rocket launcher 98 (RPG-7 95) |

Optics:

- the reflex is about 46 × 30 × 37 mm with a 24 × 20 mm window;
- the holographic is about 95 × 46 mm with a 32 × 24 mm window;
- their eye points put the window at about a quarter of the view when aiming.
