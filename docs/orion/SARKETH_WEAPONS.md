# The Sarketh's weapons: what they fire

The owner's brief of 2026-11-15, word for word (the Sarketh's guns are the `skr_*` set, `tools/blender/sarketh_guns.py`;
how a weapon is built: `docs/art/WEAPON_BUILD_RULES.md`). What is in the game and what is not is at the end: keep it
honest.

> Here's the info on the guns projectiles                                               Amber-charged kinetic
> projectiles. Not ordinary bullets, not lasers, and not generic plasma beams.
>
> 1. Their ammunition: Veyr Slugs
> The Sarketh manufacture artificial crystalline ammunition containing extremely compressed energy.
> When fired:
> A solid projectile is accelerated using electromagnetic propulsion.
> An amber energy field surrounds the projectile.
> It leaves a short golden-orange trail.
> On impact, the outer energy shell ruptures, producing a sharp thermal explosion.
> The remaining projectile penetrates the target.
>
>
> Assault rifles — Veyr Slugs
> Fast, small amber projectiles. Moderate impact with excellent sustained fire.
> Snipers — Penetrator Rounds
> Extremely concentrated projectiles with a bright white-hot center. Piercing damage.
> Heavy weapons — Breach Charges
> Large, slow-moving projectiles that detonate on impact.
> Shotguns — Shard Bursts
> Multiple small crystalline projectiles released in a wide spread.
> Hand cannons — Condensed Slugs
> Slow, powerful shots with substantial recoil and impact.
>
>
> Element Colour
> Projectile core White-hot
> Energy shell Amber
> Projectile trail Golden orange
> Impact sparks White and gold
> Explosion Orange with dark smoke
> Weapon energy cells Pale amber
>
> Give them a unique gameplay mechanic
> Thermal accumulation.
> The more continuously a Sarketh weapon fires, the hotter its internal crystal becomes.
> Low heat: Normal firing.
> Medium heat: Brighter projectiles.
> High heat: Increased projectile velocity.
> Maximum heat: Weapon automatically vents.
> This gives the Sarketh a recognizable combat identity.
> My final recommendation: Make Sarketh weapons feel like advanced electromagnetic weapons firing superheated
> crystalline ammunition. Their guns should feel heavy, precise and technologically sophisticated.
> That way, when players see an amber projectile flying across the battlefield, they'll immediately recognize it as
> Sarketh technology.

## What it means for the game

- A Sarketh round is a SOLID projectile (it flies, drops a little, can be led and dodged), wrapped in an amber field,
  with a short golden-orange trail behind it: never a hitscan line, a beam, or the light guns' plasma bolt.
- Drawn: a white-hot core, an amber shell round it, the golden-orange trail; on a hit the shell ruptures (a sharp
  orange flash with dark smoke, white and gold sparks) and the slug goes on into what it hit.
- The five rounds, by the gun's class: Veyr Slug (assault rifle: fast, small, steady), Penetrator (sniper: a white-hot
  centre, pierces through bodies), Breach Charge (heavy: large, slow, bursts with splash), Shard Burst (shotgun: a wide
  spread of small crystals), Condensed Slug (hand cannon: slow, heavy, hard recoil and impact).
- Thermal accumulation: each gun's crystal heats with every shot and cools when it rests. Low: normal. Medium: the
  rounds burn brighter. High: they fly faster. Maximum: the gun vents by itself (it cannot fire until it has vented).
- Their guns' cells and the light in them are pale amber; amber is how a player knows Sarketh fire at a glance.

## In the game (2026-11-15)

- **The round**: `ESOProjectileKind::Slug` (game_data.json `"round": "slug"`). A real projectile on the projectile
  subsystem (it flies, a little drop: `grav`), drawn by `USOFxSubsystem::SlugRound` (white-hot core, amber field, a
  short golden-orange trail, gold sparks shed as it heats), `SlugImpact` (the shell's rupture: a hard orange flash and
  crack, white and gold sparks, dark smoke, a glowing mark; into a body the flash and sparks only; with `splash` the whole
  burst, for a Breach Charge) and `SlugFlash` (the rails' hard white-gold flash, no flame or smoke). Sounds
  `<gun>_shot_fp|world` and `slug_impact` (`tools/audio/sfx_synth.py`, `SARKETH`, `skr_core`).
- **Penetration**: `"pierce"` (bodies passed after the first) and `"pierceKeep"` (the share of damage kept through each)
  -> `FSOProjectile::Pierce / PierceKeep`: the server's round goes on through a body (never a wall, never a plate that
  turns the blow) and is drawn going on out the far side.
- **Thermal accumulation**: `"heat": {perShot, cool, delay, vent, speed}` -> `USOWeaponData::HeatPerShot / HeatCool /
  HeatCoolDelay / VentTime / HeatSpeed`; `ASOWeapon::GetHeat / IsVenting / HeatSpeedScale / HeatBright` (medium 0.4:
  brighter rounds, high 0.7: faster up to `speed`, full: a forced vent with the light guns' vent effect and sound, no
  fire until it ends). The HUD draws the heat under the ammo count, amber turning white-hot, and says VENTING.
- **Their light keeps its colour**: a gun's `gun_glow__cell` and `gun_glow__amber` slots are not tinted by rarity
  (`USOGunRigComponent::Dress`).
- **Guns**: the assault rifle only, `skr_rifle` (Veyr Rifle: Veyr Slugs, pierce 1, a vent after about 23 shots held),
  loot weight 0 until the owner approves it; reload style `cell`. To try it: the Proving Range's **Sarketh cache**
  (`L_TestRange`, beside the Void Requiem cache: set `sarketh`, one Legendary copy of each of their guns, rearms in 10 s). The Penetrator, Breach Charge, Shard Burst and
  Condensed Slug wait for their guns (the sniper, the heavy cannon, a shotgun, a hand cannon): each is the same round
  with its own numbers (`pierce`, `splash`, `pellets`, `roundSize`, `vel`, `kick`).
- **Test**: `ShatteredOrbit.Weapon.SarkethSlugs` (a slug passes the body in front into the one behind with less, a round
  without pierce stops; the rifle fires slugs, never plasma; it heats, cools at rest, vents at full heat and holds its
  fire meanwhile, then fires again).
