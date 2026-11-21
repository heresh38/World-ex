# The effect system against the owner's guide

The owner's effects guide (2026-11-20, `art/reference/effects/effects_guide.webp`; an AI picture of theirs: its LIST and
its FEEL are the target, every word in it is the picture-maker's): "our effects are dull and one dimensional, we need a
much better effect system." Everything is drawn by `USOFxSubsystem` (`SOCombat`): pooled CPU particles on instanced
cards (glow, streak, star, smoke, and since 2026-11-21 the hexagonal cell), bullet-hole decals, short light flashes.
No Niagara: it runs headless and deterministic for the tests. First pass 2026-11-21.

Status per bullet of the guide: DONE / PART / TO DO.

## Weapon fire
- Assault rifle sharp and punchy, SMG fast and small, battle rifle controlled, sniper loud and long, shotgun massive
  and wide: DONE. `USOFxSubsystem::EFlash` (Rifle / Short / Long / Shotgun / Heavy / Launcher), picked from the
  archetype's name in `ASOWeapon` (`shotgun`, `sniper` / `scout` / `bolt`, `smg` / `sidearm` / `handcannon`,
  `hmg` / `lmg`, `rocket` / `launcher`): the blades' length and width, the core, the smoke, the light, burning
  powder thrown out, and a ring of pressure across the bore for the long guns, the shotguns and the launchers.
- Energy bright and otherworldly: DONE before (`PlasmaFlash`); the Sarketh's rail flash (`SlugFlash`).
- Exotic unique: TO DO (no exotic class yet).
- Shell ejection (ballistic): DONE. `Casing`: a brass bar and its glint out of the ejection port found on each gun's
  own bounds (ahead of the grip, right flank, high), carried with the shooter, landing on the floor under it and
  skittering to rest (`FSOFxParticle::FloorZ` / `Bounce`).
- Lights up the environment, sparks and smoke: DONE (light per flash, smoke per kind, sparks for the heavy kinds).

## Impact effects
- Bullet impact on metal (sparks and metal debris), concrete (dust and fragments): DONE. `ESurface` read from the hit's
  own names (`SurfaceOf`: physical material, material, component, actor; the floor's footsteps read the same rule),
  each with its own look and sound: metal (sparks, ricochets, a hot point, `impact_metal`), concrete (sparks off the
  aggregate, dust, chips, `impact_hard`), dirt and grass (a clod, crumbs, torn grass, `impact_dirt`), wood
  (splinters, `impact_wood`), water (drops, a ring, mist, `impact_water`). Bullet holes on concrete, metal, wood.
- Flesh (blood and hit reaction): DONE before (blood mist and drops; the body's flinch in `ASOEnemy::HitReact`).
- Energy impact: DONE before (`PlasmaImpact`).
- Critical hit (larger), shield hit (shield break effect), weak point (distinct): DONE. `HitKind` on the shooter's
  own machine from the hit's confirmation (`FSOHitReport`, now with `bShieldBroken`): a shield hit lights a lattice
  of hexagonal cells round the point (`shield_hit`); a shield broken throws the cells off the body with a flash
  (`shield_break`); a critical flares larger with lines out; a weak point bursts in gold with a ring opening on
  the surface.

## Explosions and destruction
- Grenade (powerful area damage), rocket (large and cinematic): DONE. `Blast(Fire)`: the fireball, debris thrown out
  and landing, embers, a column of smoke standing after it, the ground scorched (the decal, sized), the shock racing
  out along the ground, and fire left burning.
- Energy explosion (sci-fi): DONE. `Blast(Zap)`: arcs of light stepping out in jagged chains, a ring on the surface.
- Environmental explosion (reactive environment), vehicle explosion: TO DO (nothing in the world explodes yet).

## Ability effects
- Ours are the strike's sweep, the slam's and the charge's shockwave, the brace's ward, the warnings on the ground
  (DONE before). The guide's void / arc / solar / stasis / healing are other games' abilities: ours take their own
  look as each ability is designed.

## Projectiles and tracers
- Ballistic tracer, energy bolt, plasma, rocket trail: DONE before (`Tracer`, `PlasmaBolt`, `SlugRound`, `Trail`).
- Exotic projectile: TO DO (with the exotic class).

## Environmental
- Dust and debris (reactive to explosions): DONE (debris, dust, the column).
- Smoke lingering: DONE (the column lives 2.5-4 s; impacts leave dust).
- Fire spreads and persists: DONE. `Burn`: tongues of flame (the torn-blade card standing up), embers rising and
  falling, smoke, over a patch for its time (a grenade 2 s, a rocket 4 s), dying down in its last third.
- Sparks (metal and electrical): DONE (metal impacts, the zap's arcs).
- Weather: TO DO (a level's own: the Meridian storm exists as a sky, not as particles).

## Loot and pickup
- Beams per rarity, glow and pulse, visible from a distance: DONE before (the HUD's beams and the world's streaks).

## UI feedback
- Shield break, low health, ability ready, level up, mission complete: DONE before (the HUD's edge effects and
  banners; level up and the loop's beats 2026-11-21).

## Pictures and tests
`SOCaptureSeries 1 41` (files `SO_fx_01_impacts`, `01b_impacts_later`, `02_flashes`, `03_casings`,
`03b_casings_third`, `04_hit_kinds`, `05_grenade`, `06_rocket`, `07_fire_after`, `08_energy_burst`).
Tests `ShatteredOrbit.Fx.SurfaceOfAHit`, `ImpactsPerSurfaceAndHitKinds`, `CasingsLandOnTheFloor`.
Budget: the pool holds 1500 particles, oldest dropped first; a rocket's blast spends about 60, a burn about 20 a
second, a metal impact 30.

## Still to do (the owner's guide)
Exotic weapons and projectiles (with the class), environmental and vehicle explosions (with things that explode),
weather as particles, the particles' cost profiled at the busiest moment (a shotgun into a shield in a crowd).
