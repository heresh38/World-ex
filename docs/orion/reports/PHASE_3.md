# Phase 3 report: the boss framework

Started 2026-11-12, straight after phase 2 (the owner: "continue and don't wait for me just keep working"). Format
from `MASTER_BRIEF.md`, "Development reporting". The brief (part 5): a reusable boss architecture, phases, attacks
with readable warnings, weak points, shields, and "build one complete boss before expanding the roster". Phase 3
started from one boss, the Hollow Colossus, whose whole fight was written into its own class.

**What is true now:** a boss is no longer a kind of creature. It is any species (or a level's variant of one) that
names a table, and the table is data. The Colossus fights by its table and its attacks are abilities from kits;
the Galleria's Warden became a two-phase boss with two lines of data and no code. Nothing here has been played.

## Where each item stands

| The brief asks for | Status | What exists |
|---|---|---|
| Boss architecture (its "BossBase" and components) | **Full**, as one part instead of eight | `USOBossComponent` + `USOBossData` (`SOAI/SOBoss.h`). The brief's list maps like this: base = `ASOEnemy` with a `BossId`; combat and attacks = the shared ability framework (a phase names a kit); phases, weak points and shield = the component and its table; encounter = `ASOOperation`'s boss stage (adds keyed to the boss's health, checkpoint); reward = the operation's reward sets. No second damage path, no second ability system. |
| Combat phases | **Full** | A table of phases by share of health. A phase can change the kit (attacks), cooldowns, speed, the damage taken (armour), the pause between moves, and begin behind a shield. Phases come one at a time, so a blow that crosses two thresholds still meets each shield, and never while the boss reels: the opening the players earned is theirs to the end. Summoned enemies stay where they were (the operation's waves keyed to the boss's health). Arena hazards: only the bursting marks (below). |
| Shields | **Full** | A phase that begins with `shield` makes the boss immune until the conduits that feed it are destroyed (on the level's sockets, or a ring round it); then it reels for the phase's `stagger` seconds and takes half again as much. This is the Colossus's old shield, now any boss's. |
| Weak points | **Full** | A ball round a point on a bone. A round whose line passes through it on the way in is a precision hit worth the point's scale on top of the gun's own (the Colossus's heart: x1.6, only from in front). Enough damage on it within one phase breaks it: the boss reels and the point is shut until the next phase. Each open point carries a light, brighter while the boss reels. Precision is now the victim's call for everything that can be shot (`PrecisionAt`). |
| Attacks with a readable warning | **Full** for the five built | Every boss attack is an ability with a wind-up; the body goes into its clip as the wind-up begins (the clip is drawn out so the blow in it falls on the end), a sound of its own plays, and an attack that lands on the ground draws where: a ring or a cone that fills from the middle to the rim. Built: slam (ring), sweep (cone, throws sideways), barrage (a volley that lasts), marks that burst under the players (rings on a fuse; whoever steps out is not hurt), and the Sundering (the third phase's heavy slam). Wind-ups follow the brief's targets: standard 0.9 to 1.4 s (sweep 0.9, slam 1.15), heavy 1.5 to 2.2 s (Sundering 1.9, the marks' fuse 1.7 and 1.5). **Not built** from the brief's list: energy beams, charge attacks, summoning as an attack. |
| A warning on the ground | **Full** | `USOFxSubsystem::Warn`: a decal, so it lies on rubble and steps, drawn only on faces that look up, under a body that still turns if asked. A strike with a wind-up of 0.4 s or more draws its own reach, so the Bulwark's slam, the hunter's lunge and the disruptor's pulse have it too. Places the server chose reach every machine. |
| Boss arena | **Part** (unchanged) | The Crown already has the conduits' sockets. Nothing about the arena was redesigned round the new attacks, and it has no hazards of its own. |
| First complete boss | **Part** | The Colossus: its own body, its own four clips, three phases with three kits, a weak point that is modelled on the body (the crystal in the hollow chest), a shield, nine sounds of its own, exclusive rewards (the operation's sets; the armour of them is not modelled). What keeps it from Full: it has no clip for reeling (it stands still), none for calling up the marks (it reuses the barrage's) and none for a phase beginning; nobody has fought it. |
| A second boss | **Planned** | The roadmap said "then one new boss built complete". The brief says the opposite order ("one complete boss before expanding the roster"), and a new boss is first of all a new creature in Blender. Not started. |
| HUD | **Full** | The bar across the top shows a notch where each phase begins, the phase's name, why nothing hurts it, or that it reels. It now also comes up for a boss met outside an operation. |

## What was inspected
`ASOColossus` (its shield, stagger, three attacks and their timing), the ability base and every ability class, how a
creature uses its kit, how a round's hit is scored, the effects subsystem and its decals, the cue relay, the HUD's
boss bar, the operation's boss stage, the Colossus's model in `altered.py` (where its heart is).

## What was implemented
- **The table and what runs it** (`SOBoss.h/.cpp`): phases, weak points, shield, reeling. The component exists on
  every machine and is not replicated; the three things the others need travel on the creature (`BossId`,
  `BossPhase`, `BossWeakBroken`, beside its immunity, which already did).
- **Abilities**: an ability can last (`ChannelTime`); a grant can say where in the creature's clip the blow lands
  (`clipLead`) and name a sound for the wind-up (`windUpSound`); new classes `USOAbility_Sweep`, `USOAbility_Eruption`
  (SOCombat) and `USOAbility_Barrage` (SOAI). A creature's blow now goes where its body faces, where the warning is
  drawn, not along its aim.
- **The Colossus** lost its own attack code (about 170 lines): it decides when to move and how it closes, and uses
  any ability of its kit that would land, with a pause from its phase between two. It turns slowly while it winds
  up, so a cone can be stepped round.
- **Data**: `Data/game_data.json` `"bosses"` (colossus, warden) and four kits (`colossus`, `colossus_choir`,
  `colossus_root`, `warden_fury`); the importer's `bosses` step and the material `M_SOWarn`.
- **Sounds** (our synth, `sfx_synth.py ... boss`): two wind-ups, the slam, the sweep, the volley charging, the
  call, a mark bursting, a phase beginning, something in it breaking.
- **A reeling boss resists nothing it does to itself**: `ApplyStatus` only asks what a creature resists when
  someone else applies it.
- Bodies and guns no longer take decals (the warning painted the player violet).

## Files created
`SOAI/Public/SOBoss.h`, `SOAI/Private/SOBoss.cpp`, `ShatteredOrbit/Private/Tests/SOBossTests.cpp`,
`Content/Data/DA_Boss_Colossus`, `DA_Boss_Warden`, `Content/Abilities/DA_Kit_Colossus`, `_Colossus_choir`,
`_Colossus_root`, `_Warden_fury`, `Content/FX/M_SOWarn`, nine `boss_*` sounds, this report.

## Files modified
SOCombat: `SOFxSubsystem`, `SOCue`, `SOCombatCharacter`, `SOCombatStatics`, `SOProjectileSubsystem`,
`SOGunRigComponent`, `Abilities/SOAbilitySet.h`, `SOGameplayAbility`, `SOAbility_Strike`, `SOAbility_Kit`.
SOAI: `SOEnemy`, `SOAltered.h`, `Species/SOColossus.cpp`, `SOAbility_Bolt`, `SOSpecies`. SOCharacter:
`SOCharacter.cpp`. SOUI: `SOHUD`, `SOUI.Build.cs` (it now links the creature module, which it already included).
ShatteredOrbit: `SOPlayerControllerDev.cpp` (capture set 23, the two-player check's boss part).
`Content/Python/import_assets.py`, `Data/game_data.json`, `Data/op_meridian.json`, `tools/operation/meridian_plan.py`
(the Warden names its table), `tools/audio/sfx_synth.py`.

## Systems integrated
Damage still goes through the one gate (a phase's armour and the reeling bonus are scales in
`ScaleIncomingDamage`). Conditions: reeling is `Status.Stagger`, so the brain stops and abilities are blocked by the
rules that were already there. Difficulty: a level's cooldown scale multiplies the phase's. Variants: a plan's
`"boss"` key. Areas: the tables live in `/Game/Data`, shared.

## Compilation
The editor target builds clean. Not built: Shipping, a package (by the owner's rule, not until the last phase).

## Tests
97 of 97 automation tests pass on the final build, with the boss's sounds, the wind-up sound and the refitted bodies in (90 from before, 6 boss tests, 1 that measures the bodies).

New, `ShatteredOrbit.Boss.*`: `PhasesByHealth` (three phases, each phase's kit, one blow across two thresholds
still meets each shield, the next phase waits while it reels, a reeling boss takes half again, its conduits die
with it), `WeakPoint` (a shot at the heart from the front is the heart, from behind it is plate, a shot at the
legs is nothing; a real round does its damage x the gun's precision x the heart's; broken, it reels and the heart
is shut; whole again in the next phase), `AttacksWarnFirst` (the slam's reach is on the ground from the first
moment, nothing lands during the warning, then the kit's damage; the sweep lands in front, throws sideways and
touches nothing behind), `BarrageLasts`, `MarksBurstWhereDrawn` (stays: hurt; leaves: not; the boss dies first:
they come to nothing), `AVariantCanBeABoss` (a Bulwark given the table `warden`).

Two players (`bash tools/netcheck.sh`, now with a boss): the guest saw the boss and its table (3 phases); the slam's warning on its own ground and then the slam's damage (150 to 110); the new kit; four marks on its ground and the burst's damage; the phase change and the shield (immune, 60%). The first run of the check had put the boss behind a wall before the guest was watching; the check was corrected and this is its second run.

Pictures: `SOCaptureSeries 1 23` (files `SO_b0` to `SO_b9`): the slam's ring, the sweep's cone, the marks filling
and bursting, the volley, the shield with the bar's text, reeling with the heart lit.

## Known bugs and limits
- **The Colossus's collision was not its body: fixed on 2026-11-13.** Measured by a new test
  (`ShatteredOrbit.Altered.BodiesFollowTheBody`: every creature shot at from four sides on a grid, each hit compared
  with the nearest point of the drawn surface): the Colossus's collision stood on average 167 cm off its surface (worst
  267 cm), every shot of the grid counted, and a shot at its head landed on its spine. The cause was a physics asset
  left from an earlier, much bigger model: a re-import never rebuilds it. The import now refits the bodies of every
  skeletal mesh it brings in, one convex hull per bone (`import_assets.fit_bodies`, through a new editor-only module,
  `SOEditor`, because the editor's Python cannot set the fitting options; `SO_IMPORT_ONLY=bodies` refits what is
  already imported). After: Colossus 3.6 cm on average (worst 18.5), stalker 3.5 (was 8.2), Remnant 1.9 (7.2),
  Veilborn 2.5 (10.6), Bulwark 3.2 (9.4); both players were refitted too. **A side effect to judge in play:** the
  old capsules were fat, so near misses counted; every creature and the players are now thinner targets (on the
  grid a quarter to a third fewer shots land).
- The Colossus stands still while it reels, when a phase begins and when it calls the marks up (no clips of its
  own for these): the light, the sound and the bar say it, the body does not.
- The marks ignore walls between the boss and the player (by design: they come up from under), and extra marks
  can fall where nobody can stand.
- The pause between a boss's moves and every number in the tables are first guesses.
- Nine new sounds were built and imported; none has been listened to by the owner.
- A boss's phase is not saved: a wipe and a return starts the fight again (the operation respawns the boss).
- The Warden has a second phase and no weak point; its shield arm is still the Bulwark's front plate.

## Remaining
- The owner's play-through of the Crown.
- Colossus clips: reeling, a phase beginning, the call. Arena hazards at the Crown.
- From the brief's attack list: a beam, a charge, summoning as an attack.
- A second boss (a new creature in Blender first).

## Dependencies for phase 4
In place for loot and progression: every kill goes through one gate with the killer known, an operation's boss and
reward sets, variants and tables as data, the profile store with versions. Phase 4 needs: the loot code split out
(`SOLoot`), armour that counts in the gate (`DamageTaken` is ready for it), attributes, perks as data, sinks for the
two currencies.
