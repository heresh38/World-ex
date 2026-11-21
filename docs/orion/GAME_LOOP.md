# The game loop (the owner's brief, 2026-11-20)

The owner's words, word for word, sent with five AI-made reference pictures of their own (kept in `art/reference`:
`ui/hud_1.webp`, `ui/hud_2.webp` (the HUD), `effects/effects_guide.webp`, `movement/movement_guide.webp`,
`ui/armoury_arsenal.webp`). Every word, name and glyph in those pictures is the picture-maker's, not ours: the layout,
the feel and the list of things are the target; the words come from our own data.

> THE WAYFARER GAME LOOP
>
> LAND IN ZONE
> ↓
> FIGHT ENEMIES
> ↓
> GET LOOT
> ↓
> COMPLETE EVENT
> ↓
> FIGHT ELITE
> ↓
> GET BETTER LOOT
> ↓
> UPGRADE BUILD
> ↓
> TRY HARDER CONTENT
> ↓
> REPEAT
>
> SECRET SAUCE
>
> The biggest thing I would do:
>
> Every 15-30 seconds the player should get:
>
> Kill
>
> Loot
>
> XP
>
> Level
>
> Objective update
>
> Explosion
>
> Ability ready
>
> New enemy
>
> Damage numbers

With it, the owner asked for (2026-11-20): "i need a new hud, images one and 2 show what we need. i have also included
an image for effects because ours effects are dull and one dimensional, we need a much better effect system. i have
also included an image for an updated movement system please study it and there is an image for how to better organize
weapons and other things we need like an inventory to hold items we collect. remember the rules triple a artist, triple
a gamplay/movement. when reloading the reload effect stays mid air on guns like the light weapons so if you reload and
move then the effect stays in the air where you initated the reload and not on the gun, please fix."

## What each picture asks for (ours to read, not to copy)

- **HUD** (two screens): minimap top left with the area's name; compass and objective banner with progress top
  centre; buff / status timers and a tracked-objectives panel top right; level, name and health bar over an enemy;
  shield and health with numbers bottom left on the kit's emblem; abilities with keys, cooldowns and the ultimate's
  meter bottom centre; the held gun's name, class, magazine / reserve, the three slots, grenade and melee counts bottom
  right; a loot card ("new item") on a drop; damage numbers (normal, shield, precision, critical); a crosshair with
  four states (idle, moving, aiming, enemy lock); loot beams by rarity; screen-edge effects (shield hit, low health,
  ability ready).
- **Effects**: weapon fire per class (assault rifle sharp, SMG fast, battle rifle controlled, sniper loud, shotgun
  massive, energy bright and otherworldly, exotic unique) and muzzle flashes per damage type that light the scene with
  sparks, smoke and shell ejection; impacts per surface (metal sparks, concrete dust, flesh, energy discharge) and per
  hit kind (critical larger, shield break, weak point distinct); explosions (grenade, rocket, energy, environmental,
  vehicle); ability effects (void distort and pull, arc electrify, solar burn, stasis freeze, healing restore);
  projectiles and tracers (ballistic, energy bolt, rocket, plasma, exotic); environmental (dust, smoke, fire, sparks,
  weather); loot and pickup beams per rarity, glowing and pulsing, visible from a distance; UI feedback (shield break,
  low health, ability ready, level up, mission complete). "Effects aren't just visuals. They are communication."
- **Movement**: idle (relaxed alert stance, breathing, weight shifts), walk (grounded, subtle bob, weapon sway),
  sprint (lowered weapon, camera leans forward, wider FOV, dynamic arm movement, quick acceleration), slide (keeps
  momentum, low camera, smooth into aim), jump (fast take-off, short hang, responsive air control, not floaty), mantle /
  climb (smooth, context sensitive, low and high ledges, keeps momentum), landing (camera compression, impact by
  height, subtle shake), strafe and turn (body lean, weapon inertia, precise); first person: idle stable, walk bob and
  sway, sprint lowered weapon with FOV up, slide low, jump tilts, landing dips, aim stable. Numbers on the sheet: walk
  FOV 95, sprint 103-108, bob 1-2 px walking and 2-4 sprinting, acceleration 0.15 s, deceleration 0.10 s, strafe lean
  3-5 degrees, a short hang, landing impact by height, a slide of 0.8-1.2 s. Extra moves: double jump, dodge, ground
  slam, grapple. The flow: sprint, slide, aim, shoot, jump, mantle.
- **Armoury / inventory**: tabs (loadout, arsenal, armour, inventory, character, journal) and currencies at the top; a
  category list on the left (every gun class with counts, then by maker); a grid of gun cards with power, sort and
  view modes, pages; the character large in the middle holding the chosen gun; the chosen gun's panel on the right
  (rarity, class, kind, name, its line, a big render, power raised up to a cap, stats as bars, perks, the intrinsic
  trait, equip / details / lock / dismantle); a quick compare. And an INVENTORY for the items collected (not guns:
  materials, consumables, keys, whatever the loop drops).
