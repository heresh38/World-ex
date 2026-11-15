# Project Orion: the owner's enemy AI brief

The owner's message of 2026-11-13, word for word. It is the standing brief for the enemies and how they fight.
What of it exists, what does not, and what was tested: `reports/AI.md`. Where it and `CLAUDE.md`'s hard rules
differ, the stricter rule holds (see `ARCHITECTURE.md`). Do not edit the text below.

---

PROJECT ORION — MASTER AAA ENEMY AI AND COMBAT BEHAVIOUR SYSTEM

Act as a senior AAA AI programmer, Unreal Engine 5 C++ gameplay engineer, combat designer, enemy behaviour architect, and technical AI designer.

Your task is to build a complete, modular, production-quality enemy AI framework for Project Orion.

Project Orion is a dark sci-fi looter shooter set on a transformed Earth. Humanity survives behind enormous fortified cities while hostile alien creatures and other dangerous forces occupy the outside world.

The enemies must make combat feel intelligent, unpredictable, atmospheric, and challenging.

Do not create enemies that simply run toward the player, stand still and shoot, or repeatedly execute basic attack animations.

Every enemy should have a recognisable combat role, decision-making logic, movement style, attack patterns, reactions, and personality.

Use Unreal Engine 5, C++ for core systems, and Behavior Trees, State Trees, EQS, Animation Blueprints, and Blueprints where appropriate.

First inspect the existing Project Orion project. Reuse the existing player, movement, weapon, damage, animation, and multiplayer systems. Do not create duplicate systems.

⸻

1. CORE ENEMY AI ARCHITECTURE

Create a reusable enemy framework that supports dozens of different enemy types.

Suggested architecture:

* AProjectOrionEnemyBase
* UProjectOrionEnemyAIController
* UEnemyCombatComponent
* UEnemyPerceptionComponent
* UEnemyHealthComponent
* UEnemyMovementComponent
* UEnemyWeaponComponent
* UEnemyAbilityComponent
* UEnemyBehaviorComponent
* UEnemySquadComponent
* UEnemyDifficultyComponent
* UEnemySpawnDirector
* UEnemyDataAsset

Use data-driven configuration so that new enemies can be created without rewriting the entire AI system.

Each enemy should support configurable:

* Health.
* Shields.
* Armour.
* Movement speed.
* Detection range.
* Hearing range.
* Attack range.
* Preferred combat distance.
* Accuracy.
* Reaction time.
* Aggression.
* Intelligence.
* Attack cooldown.
* Ability cooldown.
* Flanking preference.
* Retreat threshold.
* Combat role.
* Difficulty tier.

All important properties must be adjustable through Data Assets or appropriate Unreal configuration.

2. PERCEPTION AND PLAYER DETECTION

Build a sophisticated perception system.

Enemies must detect players using:

Vision

* Field of view: configurable, initially 100–120 degrees for standard humanoid enemies.
* Detection distance: configurable by enemy type, initially 2,000–3,500 cm.
* Line-of-sight checks.
* Occlusion from walls, terrain and environmental objects.
* Reduced visibility in darkness or environmental concealment where supported.
* Detection based on player movement and visibility.

Hearing

Enemies should investigate:

* Gunfire.
* Explosions.
* Sprinting.
* Sliding.
* Jumping and landing.
* Environmental disturbances.
* Nearby enemy death or distress signals.

Initial hearing radii:

* Footsteps: 700–1,200 cm.
* Sprinting: 1,500–2,000 cm.
* Suppressed or quiet weapons: 1,000–1,500 cm.
* Loud gunfire: 2,500–4,000 cm.
* Explosions: 4,000–6,000 cm.

Treat these as starting values, not universal constants.

Detection states

Implement:

1. Unaware.
2. Suspicious.
3. Investigating.
4. Alerted.
5. Engaged.
6. Searching.
7. Returning to patrol.

Enemies must remember the last known player location.

If the player disappears behind cover, enemies should investigate the last known position rather than instantly knowing the player’s new location.

Avoid unfair wallhacks.

3. INTELLIGENT COMBAT BEHAVIOUR

Implement tactical behaviour that changes according to enemy type, combat situation, squad composition and difficulty.

Enemies should be capable of:

* Advancing toward the player.
* Maintaining preferred engagement distance.
* Taking cover.
* Moving between cover positions.
* Flanking the player.
* Suppressing the player.
* Retreating when heavily damaged.
* Calling for reinforcements.
* Protecting higher-value enemies.
* Surrounding isolated players.
* Guarding objectives.
* Repositioning when line of sight is blocked.
* Investigating nearby threats.
* Interrupting the player when an opportunity exists.

Do not make every enemy perform every behaviour.

Give each enemy a tactical personality.

Cover system

Use EQS or an equivalent query system to identify cover positions.

Evaluate:

* Line-of-sight protection.
* Distance from the player.
* Distance from teammates.
* Exposure to multiple enemies.
* Flanking opportunities.
* Height advantage.
* Accessibility.
* Whether another enemy already occupies the position.

Enemies should move naturally between cover positions.

Do not allow enemies to repeatedly switch between two cover points.

Flanking

Implement coordinated flanking.

* One enemy may maintain pressure.
* Another attempts to move around the player’s position.
* A third may approach from another angle.
* Flanking routes must account for actual navigation and obstacles.
* Do not let every enemy flank simultaneously.
* Enemies should abandon flanking when the route becomes unsafe or impossible.

Suppression

Some enemies should use sustained fire to limit player movement.

Suppression should:

* Create pressure.
* Encourage repositioning.
* Coordinate with advancing enemies.
* Use weapon-specific firing patterns.
* Avoid unlimited firing or perfect accuracy.

Retreat

Enemies may retreat when:

* Critically injured.
* Outnumbered.
* Their squad leader dies.
* Their shield system collapses.
* Their position becomes dangerous.

Retreating enemies can reposition, call for help, recover shields or attempt to regroup.

4. ENEMY COMBAT ROLES

Create a modular enemy role system.

The first production roster should include at least these archetypes.

A. Swarmer

Small, fast alien creature.

Behaviour:

* Rushes the player.
* Uses unpredictable movement.
* Attempts to surround.
* Dodges some incoming fire.
* Attacks at close range.
* Retreats or scatters when its group is heavily damaged.

B. Grunt / Basic Infantry

Standard ranged enemy.

Behaviour:

* Maintains medium range.
* Fires controlled bursts.
* Uses basic cover.
* Moves between positions.
* Occasionally rushes when the player is vulnerable.

C. Assault Unit

Aggressive close-range fighter.

Behaviour:

* Advances aggressively.
* Uses shotguns or close-range energy weapons.
* Attempts to close distance.
* Uses short bursts of sprinting.
* Repositions when blocked.

D. Heavy Gunner

Large armoured enemy.

Behaviour:

* Suppresses player positions.
* Uses sustained fire.
* Has high health and armour.
* Moves slowly.
* Protects nearby weaker enemies.
* Has vulnerable areas exposed during certain attacks.

E. Sniper

Long-range specialist.

Behaviour:

* Maintains long engagement distance.
* Searches for elevated positions.
* Uses telegraphed aiming before firing.
* Repositions after several shots.
* Attempts to target exposed players.
* Becomes vulnerable when approached.

F. Commander / Support Unit

Tactical enemy that improves nearby allies.

Behaviour:

* Maintains a safe position.
* Coordinates squad members.
* Buffs allies.
* Calls reinforcements where appropriate.
* Prioritises survival.
* Changes squad behaviour when killed.

G. Disruptor

Specialist enemy.

Behaviour:

* Uses EMP, electrical or disruption attacks.
* Attempts to disable player abilities or shields.
* Uses repositioning to avoid direct confrontation.
* Has clearly telegraphed special attacks.

H. Elite Hunter

Advanced enemy designed to challenge experienced players.

Behaviour:

* Uses cover and flanking intelligently.
* Reacts to repeated player tactics.
* Uses abilities strategically.
* Prioritises isolated players.
* Has several combat patterns.
* Avoids repetitive predictable attacks.

Create each role as a configurable archetype, not a separate hardcoded AI implementation.

5. MOVEMENT AND ANIMATION

Enemy movement must look natural and match the quality of the player movement system.

Implement:

* Walking.
* Running.
* Sprinting.
* Strafing.
* Backpedalling.
* Dodging.
* Leaping.
* Climbing where supported.
* Cover movement.
* Attack movement.
* Hit reactions.
* Staggering.
* Knockback.
* Death animations.

Requirements:

* No sliding feet.
* No unnatural instant direction changes.
* No snapping between movement states.
* Smooth turning and acceleration.
* Correct movement animation blending.
* Animation-aware movement.
* Root motion only where appropriate.
* Motion Warping for attacks and interactions where appropriate.

Different enemy species must have their own locomotion and movement characteristics.

6. DAMAGE AND REACTION SYSTEM

Enemies must react meaningfully to player attacks.

Support:

* Headshots.
* Weak-point damage.
* Armour impacts.
* Shield impacts.
* Body hits.
* Limb hits.
* Explosions.
* Knockback.
* Stagger.
* Suppression.
* Death.

Create hit reactions based on:

* Damage amount.
* Damage type.
* Impact direction.
* Body region.
* Remaining health.
* Enemy size.
* Armour state.

Avoid interrupting every enemy animation with a hit reaction. Use reaction priorities and cooldowns.

Armour and shields

Support:

* Armour plates.
* Energy shields.
* Regenerating shields.
* Exposed weak points.
* Destructible armour components where appropriate.

A heavy enemy might have armour that absorbs damage until the player attacks a vulnerable component.

Weak points

Weak points must be visually identifiable.

Examples:

* Glowing biological organs.
* Exposed energy cores.
* Head or face regions.
* Exposed power cells.
* Mechanical joints.

Make weak-point damage configurable per enemy.

7. DIFFICULTY AND AI PERSONALITY

Create multiple difficulty levels.

Easy

* Slower reactions.
* Less aggressive positioning.
* Lower accuracy.
* Fewer coordinated actions.
* More predictable attack patterns.

Normal

* Standard reaction times.
* Basic tactical behaviour.
* Moderate accuracy.
* Occasional flanking.

Hard

* Faster tactical decisions.
* More frequent repositioning.
* Better squad coordination.
* More aggressive use of abilities.
* Better target selection.

Elite / Endgame

* Advanced tactical positioning.
* Stronger squad coordination.
* More intelligent ability usage.
* Better awareness of player vulnerability.
* More complex combat patterns.

Do not simply increase enemy health and damage to create difficulty.

Difficulty should primarily improve decision-making, coordination, pressure and encounter design.

Use initial reaction-time ranges:

* Easy: 0.8–1.2 seconds.
* Normal: 0.5–0.8 seconds.
* Hard: 0.3–0.5 seconds.
* Elite: 0.2–0.4 seconds.

Introduce variation so that enemies do not all react simultaneously.

Do not give enemies impossible reaction times or perfect aim.

8. SQUAD INTELLIGENCE

Create a squad coordination system.

Enemies should share appropriate information:

* Last known player location.
* Current target.
* Available cover.
* Squad status.
* Threat level.
* Nearby enemy casualties.
* Active flanking assignments.

Implement squad roles:

* Leader.
* Suppressor.
* Flanker.
* Defender.
* Assault.
* Support.

The system must prevent multiple enemies from selecting the same tactical position unnecessarily.

When the squad leader dies:

* Nearby enemies may become disorganised.
* Some may retreat.
* Others may become more aggressive.
* Behaviour depends on their archetype.

9. PLAYER TARGETING AND MULTIPLAYER

Support multiple players.

Enemies should:

* Detect multiple players.
* Select targets intelligently.
* Reassess targets when situations change.
* Avoid all focusing on one player constantly.
* Recognise downed or vulnerable players where appropriate.
* Respect encounter rules and mission objectives.

Target selection should consider:

* Distance.
* Visibility.
* Threat.
* Recent damage dealt.
* Player vulnerability.
* Squad assignments.
* Encounter-specific priorities.

All authoritative enemy decisions, damage and important combat state must be handled server-side in multiplayer.

Clients should receive appropriate replicated state and visual feedback.

Avoid replicating unnecessary AI calculations every frame.

10. SPAWNING AND ENCOUNTER DIRECTOR

Build an enemy spawn and encounter management system.

Support:

* Patrol groups.
* Ambushes.
* Reinforcements.
* Enemy waves.
* Elite encounters.
* Boss introduction sequences.
* Mission-specific enemy groups.
* Procedurally placed encounters.

Spawn enemies intelligently:

* Outside the player’s immediate view where appropriate.
* At valid navigation locations.
* Without spawning inside geometry.
* Without spawning directly on top of players.
* Within encounter boundaries.
* With performance and multiplayer authority in mind.

Use a configurable encounter director that can manage enemy composition, difficulty and pacing.

11. PERFORMANCE AND AI SCALABILITY

The system must support encounters containing many enemies.

Implement:

* AI update throttling.
* Distance-based perception updates.
* Reduced update frequency for distant enemies.
* Animation budgeting.
* Efficient EQS usage.
* Navigation optimisation.
* Object pooling where appropriate.
* Dormant AI states for distant enemies.
* LOD-based AI complexity.

Do not run expensive perception, pathfinding or decision queries every frame.

Make AI update frequency configurable.

Provide profiling tools showing:

* Active AI count.
* Perception update cost.
* Pathfinding cost.
* Behaviour decision cost.
* Animation cost.
* Server AI cost.

12. DEBUGGING AND TESTING

Create an AI debug mode.

Display:

* Current AI state.
* Current target.
* Detection status.
* Last known player position.
* Current tactical role.
* Selected cover point.
* Current path.
* Attack cooldowns.
* Squad assignments.
* Difficulty level.

Build test scenarios for:

* One enemy against one player.
* Five enemies against one player.
* Ten enemies against a fireteam.
* Mixed enemy archetypes.
* Enemies losing line of sight.
* Enemies reacting to gunfire.
* Enemies flanking.
* Squad leader death.
* Multiple simultaneous encounters.
* Network latency and server-authoritative combat.

13. IMPLEMENTATION ORDER

Implement in the following phases.

Phase 1: Core enemy framework, health, damage and perception.

Phase 2: Basic enemy behaviour and navigation.

Phase 3: Combat roles and enemy archetypes.

Phase 4: Cover, flanking, suppression and retreat.

Phase 5: Animation, hit reactions and weak points.

Phase 6: Squad intelligence and coordination.

Phase 7: Difficulty scaling and encounter director.

Phase 8: Multiplayer integration and server authority.

Phase 9: Performance optimisation and debugging.

After every phase:

* Compile the project.
* Fix errors.
* Test behaviour in a real playable environment.
* Check animation and navigation.
* Verify multiplayer authority where applicable.
* Document completed work and remaining issues.

Do not claim features are complete unless they have actually been implemented and tested.

FINAL QUALITY REQUIREMENT

The enemies must feel like believable, dangerous opponents rather than moving target dummies.

Every archetype must have a recognisable identity.

Combat should naturally produce moments where:

* Enemies surround the player.
* A heavy unit suppresses the fireteam.
* A sniper forces the player out of cover.
* Smaller creatures rush from unexpected directions.
* A commander coordinates an attack.
* Players must adapt their positioning and weapon choices.

Prioritise believable behaviour, readable attack telegraphs, fair difficulty, responsive combat and scalable performance.

Do not sacrifice game performance for unnecessary AI complexity.
