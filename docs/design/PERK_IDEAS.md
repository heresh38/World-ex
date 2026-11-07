# Weapon perks — ideas for later

Status: **ideas only.** Nothing here is built yet; the owner wants the perk system made once much more of the world
exists. Today's nine perks (`data.js PERKS`) stay as they are until then.

## The rule this follows

- **Every gun has exactly one name.** All copies of *Old Winter* are called *Old Winter*.
- **Stats barely move between copies.** Rolls stay within a few percent: damage ±3 %, fire rate ±2 %, handling,
  stability and range ±6 %. Rarity adds more perks and only a small damage bonus.
- **Perks are what make a copy special.** Two *Old Winters* can play completely differently because of their perks.
  Chasing the right perks is the reason to keep looting the same gun.

## How a copy is put together (proposal)

Each copy rolls one perk from each **column**. Each archetype has its own pool per column, so a sniper never rolls a
spray perk.

| Column | What it changes | How many choices | Notes |
|---|---|---|---|
| **Barrel / emitter / maw** | range, stability, handling, recoil direction | 1 (2 on Legendary+) | small, "stat" perks; the class decides the flavour (barrels, energy emitters, living maws) |
| **Feed** (magazine / cell / sac) | magazine, reload, ammo behaviour | 1 (2 on Legendary+) | |
| **Trait I** | how you play it | 1 (2 on Exotic) | the perks that change the gun |
| **Trait II** | how you play it | 1 (2 on Exotic) | never the same as Trait I |
| **Origin** | the maker's signature (Ostrel, Talvik, Vasko, Coldwater, ... / the Writhe / the Spire) | fixed per gun | ties guns from one maker together; set bonuses later |

Rarity decides how many columns are filled: Common has two, Uncommon three, Rare four, and Legendary and Exotic all
five plus the extra choices. A **Masterwork** pass (alloy) could later raise one roll to its best value. The
Gunsmith could later let you swap a barrel or feed perk; traits stay as rolled.

## Barrel / emitter / maw (small, stat perks)

- **Fluted Barrel / Tuned Emitter / Lean Maw**: faster handling and ADS, a little less stability.
- **Heavy Barrel / Dense Emitter / Thick Maw**: more stability and range, slower handling.
- **Ported / Vented**: recoil pushes straight up instead of sideways.
- **Long Throat**: more range, slower to aim.
- **Compensated Muzzle**: less muzzle flash and a smaller tracer, so you are harder to see.

## Feed (magazine, cell, sac)

- **Extended Feed**: magazine +30 %, reload a little slower.
- **Light Feed**: reload 20 % faster, magazine −10 %.
- **Ricochet Rounds** (kinetic): rounds bounce once off hard surfaces.
- **Hollow Points** (kinetic): more damage to flesh, less to shields.
- **Overcharged Cell** (energy): more damage to shields, more heat.
- **Acidic Sac** (living): the poison pool lasts 2 s longer.
- **Seeding Sac** (living): every fifth shot is a brood round.

## Trait perks (the ones that change the gun)

### Reload and magazine
- **Topped Off**: a kill refills 20 % of the magazine from reserve.
- **Spent Casing**: the last third of the magazine deals +15 % damage.
- **Tactical Reflex**: reloading right after a kill is 40 % faster.
- **Echo Chamber**: precision hits put a round back in the magazine (once per second).
- **Breach Load**: the first shot after a reload hits much harder, and a kill with it refunds that round.

### Kills and streaks
- **Bloodwake**: kills give a short stacking damage bonus (the current Rampage, made deeper).
- **Execution Line**: a kill with a precision hit makes the next shot pierce one more target.
- **Chain Fire**: kills while airborne or sliding refill the magazine.
- **Grim Tally**: the gun gets stronger with every kill this life (it shows a counter) and resets when you die.
- **Last Rites**: a kill starts your shield recharging at once.

### Precision
- **Steady Hand**: holding aim on a target narrows the spread over 0.6 s.
- **Glass Edge**: precision kills make the target burst into shards (small area damage).
- **Opening Shot**: the first shot after 2 s without firing has extra range, accuracy and damage.
- **Hunter's Mark**: a precision hit tags the target for your squad (minimap, +5 % damage for 4 s).

### Movement
- **Slide Loader**: sliding reloads the magazine.
- **Momentum**: moving fast (sprint or tactical sprint) charges a few overcharged rounds.
- **Hip-Fire Grip**: much better hip-fire accuracy and handling.
- **Featherfall**: aiming in the air slows your fall (good for the launchers).

### Status effects (one family per class, so classes feel different)
- **Kinetic: Bleed / Shatter.** Hits make wounds that tick; shattering ends them early for a burst.
- **Energy: Overheat / Arc.** Sustained fire heats the target, and an arc jumps between targets that are close
  together.
- **Living: Corrosion / Infestation.** Acid stacks soften armour; infested targets spawn a mite when they die.
- **Void** (Spire, rare): hits drain a little of the target's shield into yours.

### Living guns only (they are alive, after all)
- **Hungry**: the gun "eats" kills; after five, the next shot is a huge lob. It gets restless (sways) if it goes
  unfed for a while.
- **Symbiote**: heals you slowly while it is fed, and costs health when the magazine runs dry.
- **Mutation**: the gun changes its projectile kind (spit → bile → brood) as it levels up within a mission.
- **Brood Mother**: the swarm it leaves fights for you briefly.

### Energy guns only
- **Heat Sink**: no magazine; the gun vents heat instead (fire until hot, then a timed vent; a good vent is quick).
- **Capacitor**: holding the trigger charges a heavier shot.
- **Prism**: bolts split into three when they hit a shield.

### Kinetic guns only
- **Match Grade**: no damage falloff inside 1.5x the gun's range.
- **Subsonic**: firing does not alert enemies further than 25 m away.
- **Armour Piercer**: rounds pass through the first target.

### Squad
- **Rally Round**: reloading near an ally reloads their gun a little too.
- **Shared Spoils**: kills drop a small ammo brick for allies.
- **Beacon**: a kill puts out a pulse that briefly shows nearby enemies.

## Exotic signatures

Each archetype's exotic copy (its one name stays the same) gets a **signature** trait on top of its rolls, unique to
that gun:

- **Old Winter** (rifle): rounds slow the target; three hits freeze them for a moment.
- **Porch Light** (pump): the last shell lights the area and blinds the enemies near it.
- **Six Mercies** (revolver): six precision hits in a row make the next reload instant and the cylinder explosive.
- **The Gravid Bloom** (brood): the burst becomes a nest that keeps launching mites for 8 s.
- **Starfall Engine** (rocket): the rocket splits into a cluster that rains down after it lands.
- **Pale Horizon** (sniper): scoped, you see enemies through walls for a moment after a kill.

## Armour perks (later, with armour sets)

- **Set bonuses** for wearing 2 or 4 pieces of one set. For example, Orion: a faster tactical sprint and a cyan
  outline on tagged enemies.
- **Slot perks**:
  - head: a better radar or a faster scope-in;
  - arms: faster reloads for one class;
  - chest: more stability or a faster shield;
  - legs: a better slide or sprint;
  - feet: quieter footsteps or a bigger jump;
  - coat: a class ability.
- **Weapon-class affinity**: armour that boosts one class (kinetic, energy or living) so builds form round a class.

## Design notes

- **Clear effects:** every perk has an icon, one sentence of text, and a visible or audible effect when it triggers
  (the current Rampage indicator is the model).
- **No useless rolls:** each pool should hold perks that matter for that archetype.
- **Two traits that work together are the jackpot**, e.g. Slide Loader + Momentum, or Topped Off + Spent Casing.
- **Balance hooks:**
  - per-archetype multipliers so one perk can be strong on a pistol and modest on an LMG;
  - an internal cooldown on every proc;
  - a cap on stacking.
- **Do not let stats creep:** perks change *how* a gun plays more than *how much* damage it does.
