# Phase 2 report: enemy AI and encounters

Started 2026-11-12, straight after phase 1's work items (the owner: "continue and don't wait for me just keep
working"). Format from `MASTER_BRIEF.md`, "Development reporting". Phase 2 started from a brain that was already
**Full** (senses, cover, flanking, squad alerts) and a roster covering five of the brief's eight roles.

## Where each item stands

| Item | Status | What exists |
|---|---|---|
| Difficulty that changes decisions | **Full** | Four levels (recruit, standard, veteran, lethal) as data. A level scales how fast creatures notice, react and settle their aim, their aim error, burst length and pause, how soon they push, how long they hold cover, how many flank, and how often they use their own moves; health and damage move a little (lethal: x1.2 / x1.25). An operation's plan names its level. |
| Target switching | **Full** | In a fight a creature reconsiders its target every second or so: someone it can see who is clearly nearer than the one it has (or whom it has lost sight of), or whoever just hurt it. |
| Throttling by distance | **Full** | Out of a fight, a creature more than 60 m from every player thinks half as often, more than 120 m a fifth as often. |
| Creature moves as abilities | **Full** (done in phase 1) | The Bulwark's slam and the Veilborn's bolt, with wind-ups, from data. |
| Squad as an object | **Planned** (moved) | Coordination still runs on shared events and loops over the creatures, which is fine at the numbers an operation spawns. Worth doing when public events need groups that outlive one encounter (phase 5). |
| Encounter director split from the operation | **Planned** (moved) | Wave logic is still inside `ASOOperation`. It moves out when a second kind of activity needs it (phase 5), not before: a refactor with nothing to show today. |
| Scaling by player count | **Full** | An operation's waves are written for one player; each further player adds half of every group (two players: half as many again); a lone elite or boss stays alone. A plan can change the share. Not seen with two players in an operation. |
| Roles from data: commander, disruptor, elite hunter, pack leader | **Part** | A role is a kit of abilities put on a species by a level's variant; the creature uses it by rule (each ability says when it would be used). Commander: rallies its side (haste), and the squad is staggered when it dies. Disruptor: a pulse with a one-second warning that jams a player's abilities for five. Hunter: a lunge and a thrown charge. Alpha: the pack's howl. In Meridian Fall the three named elites carry them and a Stalker Hunter was added to the Concord Ring. **They still wear their species' bodies**: a silhouette, clips and a voice of their own for each is Blender work not started, so the brief's "unique silhouette" is not met. |
| Swarm behaviour | **Full** | The clawed stalkers are a pack: none goes in alone. Each holds off on a ring round the target, moving round it, until three are in place (or the target comes to one, or it is hurt, or seven seconds pass); when one goes, all go. The Pack Alpha's howl then speeds them. |

## Tests
90 of 90 automation tests pass. New in this phase: `AI.DifficultyLevels` (a level that is not in the table is
refused, a creature put down at the harder level has the level's share of health, its move comes back in the
level's share of the time), `Ability.PulseJams` (nothing during the wind-up, the one in reach is jammed and cannot
use an ability, the one out of reach is untouched, it passes; a harm is not put on one's own side nor a boon on
the other), `AI.CommanderRalliesAndFalls` (a Remnant given the commander's kit by a variant rallies its squad by
itself, and they are staggered when it dies), `AI.ThePackGoesInTogether` (four stalkers strung out along a line: when
the first blow lands at least three are round the target, and the first to arrive waited), and
`Operation.MorePlayersMoreOfThem`. The behaviour scales of the difficulty levels (notice, reaction,
aim, patience, flank share) are wired but not measured by a test. Nothing here has been played, and the roles
have not been seen in the operation itself.

## Known limits
- Changing the level does not change creatures already in the world (their health was given at spawn).
- No level has been played: the numbers are first guesses.
- The hunter's thrown charge and the disruptor's pulse have no body clip on the creature (the wind-up shows as
  light only); the commander's call uses its alert voice.
- One plan change: a Stalker Hunter replaces one of the two armed stalkers in the Concord Ring's second wave.

## Remaining
- Bodies, clips and voices of their own for the four roles (Blender): the brief's unique silhouettes.
- The owner's play-through of all of it; the difficulty levels' numbers are first guesses.
- Moved to phase 5: the squad as an object, the encounter director split out of the operation.

## Dependencies for phase 3
In place: abilities with wind-ups, targets and rules (a boss's attack set), conditions, kits on variants, cues for
every machine, the difficulty scale on creature moves. Phase 3 needs: a phase table by health, weak points by
bone, a warning on the ground for area attacks, and the Colossus moved onto them.
