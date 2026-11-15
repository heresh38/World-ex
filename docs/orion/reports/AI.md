# The enemies against the owner's AI brief

The brief is `docs/orion/AI_BRIEF.md` (the owner, 2026-11-13). This is what of it exists in the game, what was added
on 2026-11-13 after the owner's "Close AI gaps", what is still missing, and what was tested. A line under "exists"
names its test; a line without a test says so. Nobody has played any of it: the tests run one world without a
picture, the two-player check and the pictures are noted where they were run.

How the brief's class names map onto the code (never second systems): the enemy base is `ASOEnemy`, one class per
species in `SOAI/Private/Species`; the brain is `ASOEnemyAIController` (perception, behaviour and squad logic live
there, in C++: there is no Behavior Tree, State Tree, EQS or Blueprint logic, and none is planned: the cover search
is our own query); health, shields and conditions are the ability system's attributes; abilities are kits
(`USOAbilitySet`); difficulty is `USODifficultySubsystem`; spawning is `USOSpeciesLibrary::Spawn` and an
operation's waves.

## Added on 2026-11-13

| What | Where | Test |
| --- | --- | --- |
| **Suppression, both ways.** A round that passes within 1.3 m of a body it was not fired by its own side pins it (`Status.Suppressed`, 1.6 s, refreshed): a pinned creature stays down in cover and its aim is 1.6 times worse; a pinned player's spread is 1.3 times wider, the shield's refill waits, and the HUD says UNDER FIRE. Conduits, the Bulwark and the Colossus are not pinned. | `USOProjectileSubsystem::NoteNearMisses`, `ASOCombatCharacter::NoteNearMiss` | `AI.NearMissesPin` |
| **A suppressor** (a variant's `"suppressor": true`): when its target goes to ground it keeps the place it last saw them under fire for up to ten seconds (bursts, the gun's own spread; never through a mate), and while it does the rest of its squad pushes sooner. | `ASOEnemy::SuppressAt`, `ASOEnemyAIController::ThinkCombat` | `AI.SuppressorKeepsItUnderFire` (42 rounds in 4 s against 0 from an ordinary one) |
| **The heavy gunner**: `bulwark_gunner`, a Bulwark with the heavy machine gun, long bursts, slow, a suppressor; while it fires its front plate does not cover it (the opening). In Meridian Fall: the Boulevard and the Concord Ring's last wave. | `tools/operation/meridian_plan.py` VARIANTS | none of its own (the parts above) |
| **The marksman**: `veilborn_marksman`, kit `marksman`: a line of light on its target for 1.4 s, the last 0.3 s locked, then one fast round at where the target was when it locked: standing still it lands (75), moving across it misses. Wants high ground (`"high": true` weights the cover search), moves to new cover every three shots. In Meridian Fall: two on the Sluice's footbridges. | `USOAbility_Snipe`, `USOFxSubsystem::AimLine` | `AI.MarksmanAimsThenShoots` |
| **A hit shows on the body**: the trunk is knocked away from where the blow came from, by its share of the creature's health and the creature's weight (`FlinchScale`: Bulwark 0.45, Colossus 0.2), at most once every 0.35 s for small hits; reeling (staggered) is a bowed, swaying pose on every machine. | `ASOEnemy::HitReact`, `USOLocomotionAnimInstance::Flinch` | `AI.HitsKnockTheBody` |
| **More is heard**: blasts (5000 cm), a slide (1200), a hard landing. | `ApplySplash`, `ASOCharacter` | `AI.TargetsSpreadAndBlastsAreHeard` |
| **Targets are spread**: with several players, each creature already on a target makes it less attractive to the next (never all on one unless that one is clearly the nearest). | `ASOEnemyAIController::ReconsiderTarget` | same (3 on the nearer player, 1 on the other) |
| **Reinforcements arrive unseen**: a hunting wave's creature takes the next of its group's points that no living player has in view (in front of them within 70 m with nothing solid between); a garrison stands where the plan says. | `ASOOperation::SpawnPointFor`, `SeenByAPlayer` | `Operation.ReinforcementsArriveUnseen` |
| **Animation is budgeted**: a creature far off or small on screen updates its pose every few frames (the engine's update-rate optimisation); one nobody sees here does not update, except on a server with players joined, where rounds must land on the body as the joined player sees it. | `ASOEnemy` constructor, `BeginPlay` | none |
| **An AI debug view**: console `SOAIDebug`: over every creature within 60 m its state, awareness, target, cover, role flags and its kit's readiness, a line to its cover and to where it last knew its target; at the top how many are alive and fighting, thinks per second and their cost in ms. Not in a shipping build. Brains run on the server, so a joined player sees nothing. | `ASOHUD::DrawAIDebug` | pictures, set 25 |
| **A pack that is cut down breaks off**: when a second of its kind dies near a clawed pack animal within four seconds of the last, it runs out to its own side and away for about three seconds, then the pack forms its ring again (at most every 14 s). | `ASOEnemyAIController::OnDied`, `ScatterUntil` | `AI.ThePackBreaksOffAndTakesAnOpening` |
| **A target loading its gun is an opening** (not on the easiest level, and only for one that saw the target within the last 1.5 s): one in cover comes out and fires at once (then not again for 6 s); a pack with two on its ring goes in without waiting for the rest. | `ASOEnemyAIController::TargetIsOpen` | same, for the pack; the cover case has no test (the test worlds have no nav mesh to find cover on) |
| **The marksman's line and shot reach joined players**: who a creature aims at is known to the server alone, so the line and the tracer go to every machine as cues. | `USOCue::AimLine`, `USOCue::Tracer` | the two-player check |
| **A species' numbers are data**: `Data/species.json` (a key per number: `health`, `runSpeed`, `sightRange`, `preferredRange`, `aimError`, `burstTimeMin` / `Max`, `usesCover`, the brain's `viewHalfAngle`, `searchTime`, ...) -> `/Game/Data/DA_Species`; a creature takes them as it is made, its brain as it takes it over, a level's variant scales them after; the import writes into the file whatever number a class has that the file lacks. | `USOSpeciesTable`, `FSONumbers`, `ASOEnemy::ApplyNumbers` | `Species.NumbersAreData` |
| **The aim line reads from the eyes of the one aimed at**: seen end-on a line is almost a dot, so the light at its source keeps its size in the local view at any distance and flares when the line locks. | `USOFxSubsystem` | picture `SO_a2_marksman_locked` (at 17 m; not looked at from further) |
| **Variants can change more**: `burst`, `burstPause`, `range`, `suppressor`, `high`. | `FSOSpeciesVariant` | through the above |

## The brief, section by section

**1. Architecture.** Exists: one base, one brain, a species per file found by name, kits, variants and difficulty as
data, bosses as tables, and now a species' numbers (health, shield, speeds, sight, the range it likes, aim error,
bursts, its blow, how it takes a hit, its switches, and its brain's senses: view angles, how near is noticed at
once, how long it keeps looking, how far an alarm carries) in `Data/species.json` -> `DA_Species`, taken by every
creature as it is made and by its brain as it takes the creature over (`Species.NumbersAreData`). The file holds
today exactly what the classes had: nothing has been retuned per species yet. Missing: a new creature is still a
new class for its body, clips, voice, capsule and its own moves; the brief's "aggression", "intelligence" and
"retreat threshold" per enemy exist only as the difficulty level's scales and fixed rules in the brain (falling
back at a third of its health is the same for all). The brief's separate components (combat, perception,
weapon, behaviour, squad) are parts of two classes, not components.

**2. Perception.** Exists: a sight cone with a peripheral band, line of sight, awareness that fills (slower
crouched, faster sprinting or with the torch on), hearing of gunfire, running feet, and now blasts, slides and
landings; a last known position that is searched, never the player's true place (`AI.NoShotsThroughWalls` and the
older perception tests). States: unaware, suspicious, combat, search. Missing: **no patrols**, so nothing to return
to; "investigating" and "alerted" are not states of their own; a quiet gun is no quieter (perk `baffled_muzzle`
scales the noise, nothing else); darkness does not hide the player.

**3. Combat behaviour.** Exists: cover scored by protection, a peek, distance, mates' claims, flank side and now
height; bounds from cover to cover; flankers (a share of the squad, by difficulty); sidestep when shot at in the
open; falling back when badly hurt; pushing a target that went out of sight; suppression (new); taking
the opening when the target loads its gun (new). Missing: **calling reinforcements, protecting a more valuable mate,
guarding an objective**; nothing reacts to a revive or to an ability being used; a flank is not given up when it turns out unsafe; retreat happens for low health only (not
for being outnumbered or a broken shield; a commander's death staggers those round it instead).

**4. Roles.** As variants and kits on existing bodies: grunt (Remnant), assault (Bulwark with the shotgun), heavy
gunner (new; since later on 2026-11-13 a species of its own with its own body and voice, the Bearer), sniper (new), commander, disruptor, elite hunter (phase 2), swarmer (the clawed Stalker pack: holds a
ring, goes in together). Missing: **none of the other roles has a body, clips or a voice of its own** (Blender
work owed: marksman, commander, disruptor, hunter, alpha); the swarmer breaks off when its pack is cut down and leaps out of the line when it is hit or aimed at
(new); the hunter does not learn a player's repeated tactics. The Bearer was built to the standard of the other Altered (sculpted from distance fields: plated, but
soft-edged), seen in the game from the front and the side only, and its hold was corrected once after its test
found the off hand 13 cm short of the fore grip.

**5. Movement and animation.** Exists: each species' own clips, walk / run by speed, turning eased, hit reactions
by body region and reeling as procedural poses (new: head, shoulders, legs, trunk), a stumble that knocks the
creature back, a leap out of the line of fire. Missing: **hit-reaction, stagger and knockdown clips** (the poses are
bone turns over whatever clip is playing: arms and hands do not react, nothing falls down), leaping onto things,
climbing, motion warping, strafe and backpedal clips for creatures.

**6. Damage and reactions.** Exists: one damage gate, shields, precision by the victim's own rule, weak points with
a light on them that break (bosses), conditions, suppression, and "every hit counts" (new, the owner's "bullet
sponges ... every shot should count"): a hit slows the creature, enough of them or a precise one make it stumble
(staggered, its blow lost, knocked back), the body shows the hit where it landed, and the Bulwark's plate sparks,
still fills the stumble meter and is down while it reels. Missing: reactions by damage type; armour pieces that
break off; weak points on anything but a boss; no hit reaction on bosses beyond their own reeling.

**7. Difficulty.** Exists: four levels as scales on what the brain does (notice, reaction, aim, bursts, patience,
cover, flank share, ability cooldowns, a little health and damage) (`AI.DifficultyLevels`). Not checked against the
brief's reaction-time ranges number by number.

**8. Squad.** Exists: alerts passed from mate to mate by sight, flank shares, cover claims, half push / half hold,
the pack's ring, a commander's rally, the squad pushing while a gunner suppresses (new). Missing: **no squad
object and no named roles handed out within a squad** (who pins, who flanks is each brain's own draw).

**9. Several players.** Exists: target choice by sight, distance and who hurt it, now spread between players; waves
grow per player. Everything is decided on the server. Missing: going for the isolated or the downed player on
purpose.

**10. Spawning and the director.** Exists: an operation's stages, waves, garrisons and hunters, boss adds by
health, reinforcements out of view (new). Missing: **a director that paces a fight by how the players are doing**,
patrols, encounters made at runtime, a boss's entrance.

**11. Performance.** Exists: brains think less often far from every player (`ThinkPace`), animation budgeted (new),
the think cost counted and shown (new). Missing: pooling, dormancy for whole groups, a measured budget for many
creatures (the benchmark has not been run with forty of them).

**12. Debugging and tests.** Exists: the debug view (new), the automation tests named above, the two-player check.
Missing: tests for ten creatures against a squad, mixed groups on a real nav mesh, and anything under latency.

## What was checked

- **Automation tests**: 112 of 112 pass (104 before this work; 8 new: the five in the table's first rows,
  `Operation.ReinforcementsArriveUnseen`, `AI.ThePackBreaksOffAndTakesAnOpening`, `Species.NumbersAreData`). They run
  one world with no picture and no nav mesh: nothing about cover, flanking or paths is checked by them beyond what
  the older tests did.
- **Two players** (`tools/netcheck.sh`, a host and a joined guest on this machine): the guest's machine draws the
  marksman's aim line and is told it is under fire when a round passes; the marksman's shot costs the guest what
  the kit says. The first run showed no aim line on the guest (its target was known to the server alone): fixed
  with a cue and run again. Not checked there: the flinch on a creature as the guest sees it, the gunner.
- **Pictures** (`SOCaptureSeries 1 25` in the range, with `SOAIDebug` on): the marksman's light at lock, the debug
  header and labels, the gunner behind a block marked SUPPRESSING with 22 rounds fired in three seconds. The first
  set had the creatures behind the range's blocks (my placement) and showed that from the target's own eyes the aim
  line was invisible: the light at its source was made to read.
- **Not checked at all**: the marksmen and gunners in Meridian Fall itself (placed in the plan, never seen there);
  how any of it feels to play; frame rate with many creatures; sound (the two marksman sounds were made and levelled
  by numbers, not listened to); a suppressor's fire against a player who actually moves between covers; the
  reload opening for a creature in cover; reinforcements out of view in a real wave (the rule is tested, an
  operation's wave using it was not watched).

### Every hit counts (added later on 2026-11-13, after the owner's "bullet sponges")

- **Tests**: 115 of 115. New: `AI.FireBreaksACharge` (a shot charger is checked, stumbles once, is knocked back and
  covers under 62% of the ground of one left alone; a head hit unsteadies twice as much; a boss is not stumbled; a
  blow being wound up is lost), `AI.AHitShowsWhereItLands` (the values AND the bones: head, chest and hips of an
  armed and of a clawed body), `AI.ThePlateGivesWay` (the Bulwark's plate turns a blow, what it turned still fills
  the meter, it reels within six blows and takes the next one whole).
- **What the first pictures caught**: the first version passed its tests and did nothing you could see for a head
  hit. The head's kick was applied before the gun-hold pass, which sets neck and head afresh, and one picture was
  taken in the same frame as its blow (saving the picture before had stalled a frame). The kick is now the last
  thing done to the pose, the test measures bones, and every reaction was made larger; the stumble's step back was
  a few centimetres and is now a knock of about 1.6 m for a stalker.
- **Pictures** (`SOCaptureSeries 1 26`, `Saved/Screenshots/SO_hit_reactions_sheet.png`): head thrown back, leg
  giving with the hips dropping, trunk knocked back, the stumble and the reeling pose, all clearly different from
  standing.
- **Two players**: the guest's own fire staggered the creature in front of it on the host (four rounds) and killed
  it; nothing broke. NOT checked: that the guest's machine draws the flinch (it goes out as an unreliable call to
  every machine, as the old one did).
- **Not checked**: any of it in motion by a person (stills only); how it feels with a real gun at real ranges; the
  leap aside (`Juke`) on a nav mesh and in a crowd; whether the stumble's knock back can push a creature off a
  ledge or into a wall in Meridian Fall; sound (a stumble plays the hurt voice louder, nothing new was made).
- **Still a sponge by design**: the Bulwark from the front takes a quarter of each blow until it reels (about two
  seconds of rifle fire on the plate, then about a second open); bosses do not react to single hits at all.

## What I would do next, in order

1. Blender: bodies, clips and voices for the roles (the gunner needs a two-handed hold or a body built for the
   gun), then hit-reaction and stagger clips to replace the procedural trunk.
2. A pacing director over an operation's waves (hold a wave back when the players are nearly down, bring it
   forward when they are untouched) and patrols for garrisons.
3. A squad object: who pins, who flanks and who holds is handed out once per group instead of drawn per brain.
4. Retune `Data/species.json` per species (today it is the classes' old numbers), with the brief's ranges for
   sight and hearing as the starting point, by playing.
