# Phase 1 report: core gameplay foundation

Started 2026-11-12 on the owner's "Start phase 1". Format from `MASTER_BRIEF.md`, "Development reporting". The work
items are those of `ROADMAP.md` section 4. **Every item is built and tested by automation, by a real game start and
by a two-player run; none of it has been played by the owner**, which is the phase's last item. Two things were
moved out: the Colossus's attacks go onto the framework with the boss work (phase 3), and an upper-body animation
layer with the presentation work (phase 8).

## Where each item stands

| # | Item | Status | What exists |
|---|---|---|---|
| 1.1 | Packaged smoke test | **Full** | `tools/package.sh` builds a Windows package (1.6 GB) in about seven minutes. The packaged game starts, reaches the range, Nexus Prime and Meridian Fall, and comes back. Findings below. |
| 1.2 | Developer tools out of shipping | **Full** (by another route than planned) | Not a module: the screenshot series, the benchmark and the two-player check moved into one file, `SOPlayerControllerDev.cpp`, whose functions are empty bodies in a shipping build, and the area console commands are compiled out the same way. A separate module could not hold the controller's own Exec functions. The Shipping configuration itself has not been compiled (no packaging until the final phase). |
| 1.3 | Gameplay tags | **Full** | `State.Dead / Aiming / Sprinting / Traversing`, `Status.*`, `Cooldown.*`, `SetByCaller.*`. |
| 1.4 | One path for health | **Full** | The damage gate is `USOAttributeSet::TakeDamage`; healing and the shield's refill are effects. Scripted kills still call `Die()` (decision 14). |
| 1.5 | Status effects | **Full** | Burn (the acid guns use it), slow, stagger and guard work on players and creatures and replicate as tags. The HUD shows them: a frame of light and a tag while braced, tags for the others, a pip per condition under a hurt creature's health bar. Nothing is drawn on the creature's body itself. |
| 1.6 | Ability base | **Full** | `USOGameplayAbility`, `USOAbilitySet`, charges, cooldowns, ultimate cost and charge, `USOKitComponent` on the player state. |
| 1.7 | Data | **Full** | `"kits"` in `Data/game_data.json` -> `SO_IMPORT_ONLY=kits` -> `DA_Kit_Vanguard`. |
| 1.8 | Input | **Full** | Keyboard G, V, Q, X. Pad: right shoulder grenade, left shoulder melee, both together the ultimate (a shoulder alone waits 0.09 s for the other), D-pad up the class ability (the view toggle gave up that button). Not tried on a real pad. |
| 1.9 | Body clips | **Part** | Both bodies have their own Throw, Strike, Brace and Slam clips (looked at frame by frame in Blender, imported, seen in the game from outside). The clip is the whole body with planted feet, so it plays only when standing or nearly; on the move nothing plays (there is no upper-body layer). While it plays the gun is put away and cannot fire. First-person arms have no clips of their own: the gun drops away and comes back. |
| 1.10 | The first kit, complete | **Full** as a first pass | The Vanguard kit: Breach Charge (thrown, bursts, slows; 2 charges), Strike (cone, knock, stagger), Brace (half damage, no stagger, 6 s), Groundbreaker (the ultimate: a blow all round), and its passive rule Close Quarters (a kill within 12 m gives 25 shield back at once). Each ability has its own sound, effect, body clip and a wind-up matched to the clip (throw 0.2 s, strike 0.16, slam 0.34). Judged from stills and logs only: no sound has been listened to, no number has been tuned by playing. |
| 1.11 | HUD | **Part** | A cell per filled slot (ready / recharging, charges), the ultimate's line, conditions. The audit's worry about per-frame scans was half right: the HUD walks the combat characters (a few dozen, by class), which is fine; the search for something to interact with walked EVERY actor each frame and now reads a list (`USOInteractables`). Key letters are still fixed text. |
| 1.12 | Multiplayer gaps | **Full** for what was listed, on one machine | Run with two players (`bash tools/netcheck.sh`: a host and a guest as two processes). Seen working from the guest: the kit arrives, the creature the host spawned is seen, aiming reaches the server (spread x0.25), firing kills it and the guest gets its own hit markers, the guest's shots show at once and match the server's count, reloading, brace / strike / charge with cooldowns, charges, the braced tag and the ultimate's charge all correct on the guest's screen, creature voices arriving from the server. Also done: only the host can travel; credits, alloy and XP to their owner only. Open: the owned copies still go to everyone; nothing was run over a real network (no latency, no loss), with more than two players, or on a dedicated server. |
| 1.13 | Profile store | **Full** | `USOProfileStore`: the one place a profile is read or written. Writes off the game thread, one at a time, by way of a temporary file with the previous kept as a backup; sealed with a length and checksum; every load migrated to the current version. Found on the way: the engine's save reader asserts on a damaged file (it crashed the test run), so a file is only handed to it once the seal checks out. The existing save loaded and was rewritten through the store in a real game start. Still local only: a joined player's profile is not kept. |
| 1.14 | Creatures on the framework | **Full** for the two it named | Abilities can have a wind-up (the warning), stopped by a stagger or death, and a target. The Bulwark's ground slam (kit `bulwark`) and the Veilborn's void bolt (kit `veilborn`) are abilities: the species decides when, the data says what. One behaviour change: the slam now measures from the Bulwark itself with flat damage (before: from a point 1.4 m ahead, falling off to half at the edge). The Colossus's slam, sweep and barrage stay their own code until the boss framework (phase 3). |
| 1.15 | Report, and the owner has played it | **Part** | This report. The owner's play-through is the one thing phase 1 still needs. |

## What was inspected
The ability system, attribute set, damage statics, projectile subsystem's burn, the combat character, the player
character's input and aim, the movement component's speed, the creature's speed and brain, the HUD, the input and
import scripts, the packaging tool's staging rules and the engine's ability-system headers (5.8).

## What was implemented

**Packaging (1.1).** `SOData` (`SOCore`) is the one way the game reads a loose data file: from the project's `Data/`
in development, from `Content/Staged/Data` in a package (`tools/package.sh` copies the five files the game reads at
runtime there; the folder is ignored by git). All three maps are cooked, and all of `/Game` (the game finds guns,
sounds, wardrobe and species by name, so nothing references them). What the first packages found and what was done:
- The package's build is stricter than the editor's: a `.cpp` must include its own header first
  (`SOAlteredCommon.cpp`, fixed).
- The automation tests were compiled into the game and used an editor-only call; they are editor-only now.
- The barrier and Crown-beam material lacked a usage flag that the editor sets by itself and a package cannot
  (`M_SOEnergy`, fixed in the import and re-imported).
- Not fixed, found by the packaged run: the first launch has no save file (expected, but logged as a warning); the
  nav mesh is built from meshes of over 200,000 triangles (a warning the editor run also gives).

**The damage gate (1.4).** Before, `USOCombatStatics::ApplyDamage` held the rules (the dead, the immune, the
victim's own scaling, friendly fire) and the attribute set only subtracted. Now the rules are in the attribute set,
so anything that writes `IncomingDamage` passes them, and `ApplyDamage` returns what was let through. The same
change gives the kit its ultimate charge from damage dealt (`OnDealtDamage`).

**Conditions (1.5).** `USOCombatStatics::ApplyStatus`. Burn is a periodic effect (the totals are the old ones: the
old private list in the projectile subsystem is gone). Slow is the new `MoveScale` attribute. Stagger stops a
creature's brain and its trigger and blocks abilities. The Colossus and its conduits resist slow and stagger.

**Abilities (1.6 to 1.8, 1.10, 1.11).** See `CLAUDE.md` ("Combat core and abilities") for how it fits together.
The first ability is `USOAbility_Strike`: everything hostile in a cone in front, with nothing solid between, takes
the damage, is knocked back and staggered.

**Aim on the server (1.12).** `bAiming` is replicated to the other players, and the server takes a joined player's
aim from the aim flag their moves already carry, so the spread it rolls is the aimed one.

## Files created
- `tools/package.sh`
- `Source/SOCore`: `SOData.h/.cpp`
- `Source/SOCombat`: `SOGameplayEffects.h/.cpp`, `SOKitComponent.h/.cpp`, `Abilities/SOAbilitySet.h/.cpp`,
  `Abilities/SOGameplayAbility.h/.cpp`, `Abilities/SOAbility_Strike.h/.cpp`, `Abilities/SOAbility_Kit.h/.cpp`
  (the thrown charge, the brace, the slam)
- `Source/SOCombat`: `SOCue.h/.cpp` (sounds and effects for every machine), `SOProfileStore.h/.cpp` (saving)
- `Source/ShatteredOrbit/Private/Tests/SOAbilityTests.cpp`
- `tools/audio/sfx_synth.py`: five ability sounds; assets `/Game/Audio/S_ability_*`, `/Game/Abilities/DA_Kit_Bulwark`
- Assets: `/Game/Abilities/DA_Kit_Vanguard`, `/Game/Input/IA_Grenade`, `IA_Melee`, `IA_ClassAbility`, `IA_Ultimate`

## Files modified
- `Config/DefaultGame.ini`, `.gitignore` (project), `Data/game_data.json` ("kits")
- `Content/Python/import_assets.py` (`kits()`, the energy material's flag), `setup_input.py`
- `SOCombat`: `SOCombatTypes.h`, `SOCombatModule.cpp`, `SOAttributeSet.*`, `SOAbilitySystemComponent.*`,
  `SOCombatStatics.*`, `SOCombatCharacter.*`, `SOProjectileSubsystem.*`
- `SOCharacter`: `SOCharacter.*`, `SOCharacterMovementComponent.*`
- `SOAI`: `SOEnemy.*`, `SOEnemyAIController.cpp`, `SOAltered.h`, `Species/SOAlteredCommon.cpp`
- `SOOperation/SOOperation.cpp`, `SOWorld/SONexusCity.cpp`, `SOCore/SOAreaSubsystem.cpp` (data reads)
- `SOUI/SOHUD.cpp`; `ShatteredOrbit`: `SOPlayerState.*`, `SOPlayerController.cpp` (capture set 20), every test
  file's guard
- Re-saved by the import: `IMC_Default`, `M_SOEnergy`, `M_SOGlowPulse`, `MI_SOEnergy_Barrier`, `MI_ru_beam`,
  `MI_ru_glow`
- `CLAUDE.md`

## Systems integrated
Abilities use the existing ability system component, attribute set and damage statics; nothing was duplicated. The
acid guns' burn, the Siphon perk's heal and the shield's refill moved onto the new effects without changing their
numbers. The player's kit hangs off the existing player state beside the inventory. The HUD reads the same
character it already reads.

## Compilation
Editor target: builds clean. Game target (inside the package): builds clean.

## Tests
- **Automation: 85 of 85 pass** (the 74 from before, unchanged, and eleven new: `Ability.StateTags`,
  `Ability.StrikeCooldownAndCharges`, `Ability.UltimateChargesAndCosts`, `Ability.KitFromDataOnPossess`,
  `Ability.VanguardKit`, `Ability.KitPassiveRule`, `Status.BurnSlowStagger`, `Combat.HealAndRegenAreEffects`,
  `Profile.SafeWriteAndMigrate`, `Altered.BulwarkSlamIsAnAbility`, `Altered.BulwarkChoosesToSlam`).
- **Two players** (`tools/netcheck.sh`, three runs): see 1.12. The host's log and the guest's log agree line for
  line (10 shots shown on the guest, 10 fired on the server, 20 rounds left on both).
- **A real game start from the editor** (`SOCaptureSeries 1 20`): the existing save loaded, the kit was given, all
  four abilities were used, and the save was rewritten through the store with the previous file kept as `.bak`.
  Stills `SO_w1` to `SO_w10` (first person, then the clips from outside). This run caught a bug the tests had
  not: a creature lunging in low and close took no blow, because the strike's wall check was stopped by the
  player's own gun (fixed: it looks for the world's geometry only).
- **The packaged game, run by itself** (`ShatteredOrbit.exe -ExecCmds="SOAreaTour quit"`): range -> Nexus Prime
  (425,064 instances of 121 meshes, none missing) -> range -> Meridian Fall (the plan read: 20 stages, 37 spawn
  groups; stage 0 began) -> range; nothing of another area left loaded at any stop.
- **The ability in the packaged game** (`SOCaptureSeries 1 20`, a real controller and player state): the log reads
  `kit vanguard, creature spawned` and `strike used, creature 140 -> 0 of 140, dead 1, charges 0/1, back in 9.0 s,
  ultimate 7.7` (160 damage, doubled on an unaware creature), then `brace used (guarded 1), charge thrown` and
  `slam before the charge refused, with it used, charge left 0.0`. Pictures `Saved/Screenshots/SO_w1` to `SO_w6`
  show the HUD's four cells (G, V, Q, X) ready, spent and recharging. They also show how little the borrowed
  effects give: of the charge's burst only its smoke is in the still, and the slam is two thin streaks.
- **Not tested:** anything with two players; a gamepad; anything by hand. Capture set 20 also runs the default
  set's pictures after its own (harmless, a minute wasted).

## Known bugs and limits
- No ability has a body clip: seen from outside, the body does not move when one is used.
- The abilities' sounds were synthesised and imported but never listened to (the checks run without sound).
- The effects are a first pass tuned from stills: glows had to be turned down twice to stop them washing out.
- A thrown charge hurts its thrower inside its radius (as a rocket does). Deliberate, to be judged by playing.
- One test trap found and written down: a controller made by hand in a test is not "local" to the engine, so an
  ability use reported success without running (`SetAsLocalPlayerController`).
- Nothing shows a condition on a creature or on the player.
- The class ability and the ultimate cannot be used from a gamepad.
- The HUD's key letters are fixed text (wrong on a pad, wrong after any rebinding).
- Two-player behaviour of all of this is untested: predicted use, the cooldown on a joined player's machine, the
  other players seeing the use.
- A new body's cooldowns start over (decided, see decision 15), so dying resets a spent ability.
- Every defect listed in `PHASE_0.md` that is not named as fixed here is still there.

## Remaining
- The owner's play-through: every number in the kit is a first guess, and no sound has been listened to.
- Moved to phase 3: the Colossus's attacks as abilities with telegraphs.
- Moved to phase 8: an upper-body animation layer (an ability's clip on the move), first-person arm clips, the
  HUD's key letters following the real bindings.
- Not covered by any check: a real network (latency, loss), more than two players, a dedicated server, a real
  gamepad, the Shipping configuration.

## Dependencies for phase 2
All in place: the ability base with wind-ups and targets (creature moves), conditions (a disruptor), kits as data
for creatures, cues that reach every machine, the two-player check. Phase 2 needs new creature models and clips
from Blender for any new species.
