# Project Orion: the owner's master brief

The owner's message of 2026-11-12, word for word ("Project Orion" is the owner's code name for this game).
It is the standing brief for the whole project. Where it and `CLAUDE.md`'s hard rules differ, see
`ARCHITECTURE.md` ("Where the brief and the standing rules differ"). Do not edit the text below.

---

PROJECT ORION — ULTIMATE MASTER AAA GAME DEVELOPMENT PROMPT

Complete Game Architecture, Gameplay Systems, World, Content, Multiplayer and Commercial Production

You are acting as the combined development team behind a commercial AAA sci-fi looter shooter.

Your expertise includes:

* Senior Unreal Engine 5 C++ engineering.
* AAA gameplay programming.
* Technical art and rendering.
* AI and combat engineering.
* Multiplayer and networking architecture.
* Procedural world generation.
* Character and creature development.
* Animation engineering.
* Game systems and progression design.
* UI/UX engineering.
* Level design.
* Audio and visual effects.
* Backend infrastructure.
* Performance engineering.
* Production management and QA.

Your responsibility is to help develop Project Orion into a complete, technically sound, commercially viable online sci-fi looter shooter.

This is not a small prototype or a simple demonstration. The architecture must be designed to support a substantial commercial game that can grow through future updates, new content, activities, equipment, enemies and expansions.

Use Unreal Engine 5.

Use C++ for important gameplay, networking, performance and foundational systems. Use Blueprints for visual scripting, configuration, prototyping and designer-facing functionality. Use Unreal Engine’s existing systems where appropriate instead of unnecessarily reinventing them.

Blender is the primary external modelling and asset-creation tool where custom modelling is required.

⸻

PART 1 — PROJECT IDENTITY AND CREATIVE DIRECTION

1.1 The world

Project Orion is a dark sci-fi looter shooter set on a transformed Earth.

Human civilisation has collapsed or radically changed following an extraordinary planetary catastrophe.

Humanity survives inside enormous fortified cities protected by colossal defensive walls.

Beyond these protected settlements lies a dangerous world containing:

* Ruined human civilisation.
* Abandoned industrial complexes.
* Destroyed cities.
* Overgrown settlements.
* Alien structures.
* Hostile biological ecosystems.
* Mysterious underground facilities.
* Ancient technology.
* Unexplored territories.
* Dangerous hostile creatures.

The player is an independent hunter and explorer who ventures outside the protected civilisation.

The central gameplay fantasy is exploration, discovery, combat, survival, equipment acquisition and gradually uncovering the truth about the transformed Earth.

1.2 Creative identity

The game should have a distinctive visual and narrative identity.

Visual direction:

* Dark and mysterious.
* Advanced science fiction.
* Industrial and alien architecture.
* Beautiful but dangerous environments.
* Large-scale structures.
* Strong environmental storytelling.
* Cinematic lighting.
* Detailed materials and believable construction.
* A mixture of human technology and alien influence.

Do not directly copy existing games, their characters, weapons, maps, factions, stories, interfaces or proprietary designs.

Use other AAA games only as quality references for responsiveness, production value, readability and overall experience.

All Project Orion content must have its own identity.

1.3 Commercial target

The game is intended for commercial release on Steam.

Design systems with future expansion in mind.

Avoid unnecessary complexity that would make development impossible for a small development team.

Prioritise a polished, complete playable experience over an enormous collection of unfinished features.

⸻

PART 2 — EXISTING PROJECT AUDIT AND INTEGRATION

Before changing anything, inspect the complete existing Project Orion Unreal Engine project.

The player movement and gunplay systems have already been developed or specified in previous development stages.

Treat them as existing systems that must be preserved and integrated.

Do not unnecessarily rewrite them.

2.1 Audit

Inspect:

* Project structure.
* C++ source.
* Blueprints.
* Character architecture.
* Movement implementation.
* Weapon implementation.
* Damage and health systems.
* Existing animations.
* Existing assets.
* Existing UI.
* Networking implementation.
* Input configuration.
* Build configuration.
* Plugins and dependencies.

Identify:

* What works.
* What is partially implemented.
* What is missing.
* What is duplicated.
* What needs refactoring.
* What may create compatibility problems.

2.2 Integration rules

Create a unified technical architecture.

All systems must share compatible interfaces.

Examples:

* Weapons must communicate with enemy health and damage systems.
* Enemy AI must use the existing combat architecture.
* Bosses must use the same damage and weak-point framework.
* Loot must integrate with enemy and boss rewards.
* Inventory must communicate with equipment and character stats.
* Abilities must integrate with movement and combat.
* Missions must communicate with encounters, objectives and rewards.
* HUD elements must display actual gameplay data.
* Multiplayer must synchronise important gameplay states.

Do not create duplicate health, damage, ammunition, inventory, progression or player-stat systems.

Preserve working code unless a specific improvement is justified.

⸻

PART 3 — PLAYER ABILITIES AND CHARACTER CLASSES

Build a complete player ability framework.

The existing movement and gunplay systems must remain the foundation.

Add a modular ability architecture that can support different character archetypes.

3.1 Ability categories

Support:

* Grenade abilities.
* Melee abilities.
* Class abilities.
* Movement abilities.
* Defensive abilities.
* Offensive abilities.
* Support abilities.
* Ultimate abilities.

Every ability should support:

* Activation conditions.
* Cooldowns.
* Charges.
* Resource costs where applicable.
* Damage or healing.
* Range.
* Area of effect.
* Animation.
* Sound.
* Visual effects.
* Gameplay tags.
* Multiplayer replication.

3.2 Character archetypes

Create three initial archetypes as design foundations.

Vanguard

Aggressive frontline combat specialist.

Focus:

* Heavy offensive abilities.
* Defensive protection.
* Close-range combat.
* Area damage.
* Crowd control.

Phantom

Mobile hunter and precision specialist.

Focus:

* Mobility.
* Stealth or concealment.
* Precision damage.
* Evasion.
* Tactical positioning.

Engineer

Technology and battlefield-control specialist.

Focus:

* Deployable devices.
* Turrets.
* Shields.
* Energy manipulation.
* Support abilities.
* Battlefield control.

These are initial concepts. Develop an original class identity and avoid making classes simply different weapon loadouts.

3.3 Ability progression

Implement:

* Ability upgrades.
* Unlockable abilities.
* Configurable ability variants.
* Synergies between abilities and equipment.
* Saved ability configurations.
* Cooldown balancing.
* Ability-specific visual effects.

Abilities must be useful in both solo and cooperative gameplay.

⸻

PART 4 — ENEMY AI AND COMBAT BEHAVIOUR

Create a complete enemy AI framework capable of supporting many different alien species and hostile factions.

Suggested architecture:

* AProjectOrionEnemyBase
* UProjectOrionEnemyAIController
* UEnemyCombatComponent
* UEnemyPerceptionComponent
* UEnemyHealthComponent
* UEnemyMovementComponent
* UEnemyAbilityComponent
* UEnemySquadComponent
* UEnemyDifficultyComponent
* UEnemyDataAsset

Use Behavior Trees, State Trees, EQS and Unreal navigation systems where appropriate.

4.1 Perception

Enemies must detect players using:

* Vision.
* Hearing.
* Line of sight.
* Distance.
* Environmental disturbances.
* Gunfire.
* Explosions.
* Player movement.

Implement states:

* Unaware.
* Suspicious.
* Investigating.
* Alerted.
* Engaged.
* Searching.
* Returning to patrol.

Enemies must remember the last known player position.

Do not give enemies unfair awareness of players through walls.

4.2 Tactical combat

Enemies must support:

* Cover.
* Flanking.
* Suppression.
* Retreat.
* Repositioning.
* Squad coordination.
* Aggressive advancement.
* Defensive positioning.
* Target prioritisation.
* Special abilities.
* Reinforcement calls.

Do not make all enemies behave identically.

4.3 Initial enemy roster

Build these archetypes:

1. Swarmer — fast close-range biological attacker.
2. Grunt — standard ranged infantry.
3. Assault Unit — aggressive close-range fighter.
4. Heavy Gunner — armoured suppression unit.
5. Sniper — long-range precision attacker.
6. Commander — coordinates nearby enemies.
7. Disruptor — specialises in disabling player systems.
8. Elite Hunter — advanced tactical opponent.

Every enemy needs:

* Unique silhouette.
* Distinctive animation.
* Different combat behaviour.
* Appropriate sound design.
* Unique attack patterns.
* Meaningful combat weaknesses.

4.4 Enemy difficulty

Difficulty must improve enemy decision-making and encounter pressure rather than simply multiplying health and damage.

Support configurable:

* Reaction time.
* Accuracy.
* Aggression.
* Coordination.
* Tactical intelligence.
* Ability usage.
* Target selection.

⸻

PART 5 — ELITE ENEMIES AND BOSS ENCOUNTERS

Build a reusable boss architecture.

Suggested components:

* AProjectOrionBossBase
* UBossCombatComponent
* UBossPhaseComponent
* UBossAttackComponent
* UBossWeakPointComponent
* UBossShieldComponent
* UBossEncounterComponent
* UBossRewardComponent

5.1 Boss phases

Support multiple configurable combat phases.

A boss can change:

* Attacks.
* Movement.
* Weak points.
* Armour.
* Defensive behaviour.
* Arena hazards.
* Summoned enemies.
* Combat intensity.

Starting example:

* Phase 1: 100–65% health.
* Phase 2: 65–30% health.
* Phase 3: 30–0% health.

5.2 Boss attacks

Support:

* Melee.
* Ground slams.
* Sweeping attacks.
* Projectiles.
* Homing projectiles.
* Energy beams.
* Charge attacks.
* Area explosions.
* Summoning.
* Environmental hazards.

Every dangerous attack needs a readable telegraph.

Initial telegraph targets:

* Fast attacks: 0.5–0.8 seconds.
* Standard attacks: 0.9–1.4 seconds.
* Heavy attacks: 1.5–2.2 seconds.
* Arena-wide attacks: 2–3 seconds.

Tune based on actual player movement and difficulty.

5.3 Boss concepts

Develop original versions of these signature concepts:

* The Hollow Titan: colossal biomechanical alien with a vulnerable energy core.
* The Veil Stalker: extremely fast hunter that uses concealment.
* The Iron Regent: mechanised commander with multiple defensive systems.
* The Rootmother: enormous biological organism integrated into an underground environment.

Each boss must have:

* Unique visual design.
* Custom animations.
* Distinct attack patterns.
* Weak-point mechanics.
* Multiple phases.
* An arena designed around its mechanics.
* Distinctive audio and VFX.
* Exclusive rewards.

Build one complete boss before expanding the roster.

⸻

PART 6 — LOOT, INVENTORY AND PLAYER PROGRESSION

This is a core pillar of Project Orion.

Create a deep, replayable equipment system.

Suggested architecture:

* UProjectOrionItemDefinition
* UProjectOrionItemInstance
* UProjectOrionLootGenerator
* UProjectOrionInventoryComponent
* UProjectOrionEquipmentComponent
* UProjectOrionStatComponent
* UProjectOrionPerkComponent
* UProjectOrionProgressionComponent
* UProjectOrionLootTable
* UProjectOrionRewardComponent

6.1 Rarity

Create:

* Common.
* Uncommon.
* Rare.
* Legendary.
* Exotic.

Rarity must affect the type and potential quality of equipment without making every higher-rarity item automatically superior in every situation.

6.2 Weapon loot

Support:

* Assault rifles.
* SMGs.
* Pulse rifles.
* Scout rifles.
* Battle rifles.
* Shotguns.
* Snipers.
* Marksman rifles.
* LMGs.
* Rocket launchers.
* Grenade launchers.
* Plasma weapons.
* Energy weapons.
* Beam weapons.
* Fusion and charge weapons.

Weapons must have:

* Base statistics.
* Randomised valid stat rolls.
* Perks.
* Rarity.
* Power level.
* Upgrade state.
* Unique item ID.

Preserve weapon archetype identity.

6.3 Perks

Support modular perks affecting:

* Damage.
* Precision.
* Reloading.
* Handling.
* Stability.
* Elemental effects.
* Ammunition.
* Enemy interactions.
* Special abilities.

Perks must produce real gameplay effects.

6.4 Exotic weapons

Create unique weapons with distinctive mechanics.

Examples:

* Starbreaker: charged armour-piercing energy shots.
* Black Meridian: precision-based target marking.
* Hollow Signal: builds and releases stored energy.
* Grave Engine: delayed explosive projectiles.

These are starting concepts. Develop original mechanics, visual designs and identities.

6.5 Armour

Equipment slots:

* Helmet.
* Chest.
* Gloves.
* Legs.
* Class item.

Support:

* Armour stats.
* Rarity.
* Perks.
* Upgrades.
* Cosmetic variations.
* Modular male and female character fitting.
* Armour set bonuses.

Character attributes:

* Resilience.
* Recovery.
* Mobility.
* Discipline.
* Strength.
* Intelligence.

Use configurable stat ranges and formulas.

6.6 Inventory and vault

Implement:

* Inventory.
* Equipment.
* Item locking.
* Favourites.
* Dismantling.
* Sorting.
* Filtering.
* Search.
* Comparison.
* Item inspection.
* Persistent storage.
* Vault transfers.
* Overflow reward handling.

Initial development configuration:

* 100 general inventory slots.
* 50 material/consumable slots where stacking applies.
* 5 saved equipment loadouts.

All capacities must be configurable.

6.7 Crafting and upgrades

Support:

* Weapon upgrades.
* Armour upgrades.
* Crafting.
* Material costs.
* Currency costs.
* Perk modification where designed.
* Cosmetic crafting.
* Resource conversion.

6.8 Player progression

Separate:

* Character level.
* Equipment power.
* Ability progression.
* Crafting progression.
* Collection progression.

Build a configurable XP curve and meaningful reward structure.

Do not introduce unnecessary grinding or dozens of meaningless currencies.

⸻

PART 7 — MISSIONS, OPERATIONS AND ACTIVITIES

Create a complete mission framework that connects the world, enemies, bosses, loot and player progression.

Suggested architecture:

* UProjectOrionMissionSubsystem
* UProjectOrionMissionDefinition
* UProjectOrionObjectiveComponent
* UProjectOrionEncounterDirector
* UProjectOrionExtractionComponent
* UProjectOrionRewardComponent

7.1 Mission types

Support:

Exploration

Players explore the transformed Earth, discover landmarks, investigate abandoned structures and find resources.

Operations

Players enter dangerous areas, fight through enemy forces, complete objectives, defeat a boss and extract.

Strikes

Structured cooperative combat missions with multiple encounters and a major boss.

Raids

Longer, challenging cooperative activities with unique mechanics, coordination and exclusive rewards.

Dungeons

Smaller multi-stage activities combining exploration, combat, environmental puzzles and bosses.

Public events

World encounters that allow nearby players to participate.

Faction missions

Activities related to the different factions in the world.

Bounties and contracts

Short optional objectives that reward players for completing specific tasks.

7.2 Operation loop

Build the primary Project Orion operation loop:

1. Player selects an operation.
2. Fireteam enters the environment.
3. Players explore the area.
4. Enemy encounters begin.
5. Players complete mission objectives.
6. Additional encounters and elites appear.
7. Players confront the boss.
8. Boss is defeated.
9. Players activate extraction.
10. Extraction sequence begins.
11. Players defend the extraction area.
12. Successful extraction awards rewards.
13. Players return to the main city.

Support failure conditions, player death, revives, encounter resets and reward eligibility.

7.3 Mission objectives

Create reusable objectives:

* Eliminate targets.
* Defend a location.
* Collect resources.
* Activate devices.
* Disable machinery.
* Destroy enemy structures.
* Rescue survivors.
* Investigate anomalies.
* Survive waves.
* Defeat an elite.
* Defeat a boss.
* Extract.

Use configurable objective definitions.

7.4 Mission replayability

Support:

* Difficulty variants.
* Randomised encounter compositions.
* Optional objectives.
* Hidden areas.
* Bonus rewards.
* Activity-specific loot.
* Weekly challenges.

Do not make procedural variation destroy mission quality or narrative coherence.

⸻

PART 8 — PROCEDURAL WORLD GENERATION AND ENVIRONMENTS

The transformed Earth is one of Project Orion’s defining features.

Build a scalable procedural world-generation framework.

Use Unreal Engine 5 PCG, World Partition, Data Layers, landscape systems and custom C++ generation where appropriate.

Do not attempt to generate every environment using random assets without design rules.

The goal is controlled procedural generation that produces believable, varied, high-quality environments.

8.1 World generation architecture

Support:

* Terrain generation.
* Biome generation.
* Road networks.
* Rivers and water.
* Settlements.
* Ruined cities.
* Industrial facilities.
* Underground structures.
* Alien structures.
* Points of interest.
* Enemy encounter placement.
* Resource placement.
* Exploration landmarks.

Use deterministic seeds where required so that world layouts can be reproduced.

8.2 Initial biomes

Create a framework supporting:

1. Overgrown urban ruins.
2. Destroyed industrial cities.
3. Frozen wastelands.
4. Desertified regions.
5. Dense alien forests.
6. Toxic wetlands.
7. Mountainous regions.
8. Underground alien environments.
9. Abandoned human research facilities.
10. Contaminated coastal regions.

Each biome must have unique:

* Terrain.
* Vegetation.
* Architecture.
* Weather.
* Lighting.
* Audio ambience.
* Enemy populations.
* Resources.
* Landmarks.
* Environmental hazards.

8.3 Environmental quality

Buildings must look complete and believable.

Do not use bare building shells, unfinished construction-like structures or repetitive procedural blocks as final content.

Environments must include appropriate:

* Windows.
* Doors.
* Roofs.
* Interiors.
* Structural details.
* Pipes.
* Machinery.
* Signs.
* Debris.
* Vegetation.
* Damage.
* Weathering.
* Environmental storytelling.

Create a modular asset library that procedural generation can assemble intelligently.

8.4 Exploration

Support:

* Hidden locations.
* Discoverable landmarks.
* Abandoned facilities.
* Underground routes.
* Secret rooms.
* Rare resource deposits.
* Environmental mysteries.
* Collectibles.
* Dynamic exploration events.

8.5 Streaming and scale

Use World Partition and appropriate level streaming.

Support:

* Large environments.
* Streaming cells.
* Distance-based detail.
* Nanite where suitable.
* HLOD.
* Asset instancing.
* Memory budgeting.

Do not attempt to load the entire world into memory simultaneously.

⸻

PART 9 — MAIN CITY AND SOCIAL HUB

Create the main fortified human settlement.

It should be a visually impressive, believable city protected by enormous defensive walls.

The city is the player’s central home and progression location.

9.1 City districts

Design distinct districts:

* Central command.
* Residential sector.
* Market district.
* Armoury.
* Engineering district.
* Medical facilities.
* Hangars.
* Industrial district.
* Mission operations centre.
* Social gathering areas.
* Outer defensive wall.

Each district must have a visual and gameplay purpose.

9.2 Vendors and NPCs

Create NPC systems supporting:

* Dialogue.
* Quest assignment.
* Vendor inventories.
* Item purchases.
* Crafting services.
* Equipment upgrades.
* Faction interactions.
* World information.
* Mission briefings.

NPCs should have believable animations, schedules where appropriate and meaningful interactions.

9.3 Social hub

Support:

* Other player characters.
* Fireteam gathering.
* Social interaction.
* Emotes.
* Vendors.
* Mission selection.
* Character inspection.
* Public activity access.

Do not simulate other players with fake online entities in production.

⸻

PART 10 — UI, HUD AND MENUS

Create a complete, professional AAA interface.

Use UMG, CommonUI where appropriate, C++ data management and a clean separation between presentation and gameplay data.

10.1 Visual identity

Create an original interface using:

* Dark metallic backgrounds.
* Restrained cyan and pale-blue highlights.
* White typography.
* Controlled amber warning accents.
* Fine technical borders.
* Subtle gradients.
* Clean typography.
* Consistent iconography.
* Smooth transitions.

Avoid generic default Unreal widgets.

10.2 Combat HUD

Display:

* Health.
* Shields.
* Ammunition.
* Weapon information.
* Ability cooldowns.
* Ultimate charge.
* Crosshair.
* Hit confirmation.
* Critical hits.
* Enemy damage.
* Objectives.
* Teammate status.
* Incoming damage.
* Boss health.
* Interaction prompts.

10.3 Menus

Build:

* Main menu.
* Inventory.
* Equipment.
* Character.
* Map.
* Quests.
* Missions.
* Social.
* Collections.
* Crafting.
* Vendors.
* Settings.

10.4 Inventory interface

Support:

* Item grids.
* Item inspection.
* Stat comparison.
* Drag and drop.
* Locking.
* Favourites.
* Dismantling.
* Sorting.
* Filtering.
* Search.

10.5 Settings and accessibility

Include:

* Graphics.
* Audio.
* Controls.
* Sensitivity.
* FOV.
* HUD scaling.
* Text scaling.
* Colourblind support.
* Subtitle options.
* Screen shake.
* Motion effect controls.

All settings must persist.

⸻

PART 11 — ANIMATION, VFX AND AUDIO

Create a unified presentation framework.

All systems should have appropriate visual and audio feedback.

11.1 Character animation

Support:

* Locomotion.
* Weapon handling.
* Reloading.
* Aiming.
* Jumping.
* Sliding.
* Melee.
* Ability use.
* Interactions.
* Revives.
* Emotes.
* Death.
* Equipment presentation.

Preserve and integrate the existing player movement and weapon animation work.

11.2 Enemy animation

Support:

* Creature locomotion.
* Combat.
* Attack telegraphs.
* Hit reactions.
* Stagger.
* Death.
* Weak-point exposure.
* Armour destruction.
* Special abilities.

11.3 Visual effects

Use Niagara for:

* Muzzle flashes.
* Weapon projectiles.
* Energy impacts.
* Explosions.
* Elemental damage.
* Shields.
* Healing.
* Abilities.
* Enemy attacks.
* Boss transitions.
* Environmental effects.
* Weather.
* Extraction sequences.

Create scalable VFX settings.

Avoid excessive effects that obscure gameplay.

11.4 Audio

Create systems for:

* Weapons.
* Reloads.
* Footsteps.
* Movement.
* Enemy voices.
* Creature sounds.
* Boss attacks.
* Explosions.
* Environmental ambience.
* Weather.
* UI.
* Dialogue.
* Music.

Support spatial audio, occlusion and environmental reverb where appropriate.

⸻

PART 12 — VEHICLES AND TRANSPORTATION

Create an extensible vehicle framework.

Initial vehicle categories:

* Ground transport.
* Armoured combat vehicles.
* Lightweight exploration vehicles.
* Futuristic bikes.
* Special mission vehicles.

Support:

* Vehicle physics.
* Acceleration.
* Braking.
* Steering.
* Suspension.
* Damage.
* Health.
* Weapons where appropriate.
* Entering and exiting.
* Passenger seats.
* Multiplayer replication.
* Vehicle-specific animations.

Vehicles must have believable handling and fit the world.

Do not create vehicles merely for decoration if they are intended to be playable.

⸻

PART 13 — DESTRUCTIBLE ENVIRONMENTS AND WORLD INTERACTIVITY

Build a controlled environmental interaction system.

Support where appropriate:

* Destructible barriers.
* Breakable containers.
* Explosive objects.
* Damaged machinery.
* Environmental hazards.
* Interactive consoles.
* Doors and gates.
* Power systems.
* Moving machinery.
* Physics-based props.
* Damageable environmental components.

Destruction must be purposeful and performant.

Use Unreal’s Chaos systems selectively.

Do not make every environmental object physically simulated.

⸻

PART 14 — DYNAMIC WORLD EVENTS AND WEATHER

Create a world-event framework.

Support:

* Enemy invasions.
* Patrol encounters.
* Distress signals.
* Resource discoveries.
* Rare elite appearances.
* Environmental anomalies.
* Public defence events.
* Dynamic extraction events.
* Faction encounters.

Events should be driven by configurable systems and actual world state.

14.1 Weather

Support:

* Rain.
* Heavy storms.
* Snow.
* Sandstorms.
* Fog.
* Wind.
* Lightning.
* Environmental contamination.

Weather should affect presentation and, where deliberately designed, gameplay.

Do not introduce unfair visibility or combat disadvantages without communicating them.

⸻

PART 15 — STORY, LORE AND FACTIONS

Create a complete original narrative framework.

Do not simply create random quests disconnected from the world.

15.1 Narrative foundation

Develop:

* The catastrophe that transformed Earth.
* The origin of the alien presence.
* Humanity’s survival.
* The history of the fortified cities.
* The origin of the player character’s role.
* The major mysteries of the world.
* The long-term campaign narrative.

The story should unfold through:

* Campaign missions.
* NPC dialogue.
* Environmental storytelling.
* Discoverable records.
* Abandoned facilities.
* Faction conflicts.
* Boss encounters.
* Exploration.

15.2 Factions

Create several distinct factions with:

* Beliefs.
* History.
* Leadership.
* Technology.
* Visual identity.
* Weapons.
* Armour.
* Territory.
* Relationships with other factions.
* Unique activities.
* Rewards.

Include human factions and hostile alien groups.

Do not make every faction morally identical.

15.3 Dialogue and narrative systems

Support:

* Dialogue trees.
* Quest conversations.
* Mission briefings.
* Cinematic sequences.
* Subtitles.
* Voice-over integration.
* Dialogue choices where appropriate.

The narrative architecture should support future campaigns and expansions.

⸻

PART 16 — MULTIPLAYER AND ONLINE INFRASTRUCTURE

Project Orion is intended to support a shared online experience.

Build networking architecture early enough that gameplay systems do not need to be completely rewritten later.

Use Unreal networking and replication appropriately.

Design around dedicated servers for authoritative online gameplay.

16.1 Core multiplayer

Support:

* Multiplayer character replication.
* Player movement synchronisation.
* Weapon firing.
* Damage validation.
* Enemy AI authority.
* Boss encounters.
* Loot ownership.
* Mission progression.
* Revives.
* Team objectives.

16.2 Fireteams

Support:

* Party creation.
* Invitations.
* Joining.
* Leaving.
* Party leader.
* Ready status.
* Fireteam privacy.
* Activity selection.

16.3 Matchmaking

Support:

* Activity matchmaking.
* Player-count requirements.
* Region selection where appropriate.
* Connection quality.
* Reconnection.
* Session management.

16.4 Persistent online data

Design for persistent:

* Characters.
* Inventory.
* Equipment.
* Currencies.
* Progression.
* Missions.
* Unlocks.
* Achievements.
* Collections.

Do not assume local SaveGame files provide secure commercial persistence.

Create a backend integration boundary that can connect to a suitable account and persistence service.

16.5 Network performance

Implement:

* Server-authoritative combat.
* Client prediction where appropriate.
* Lag compensation where appropriate.
* Efficient replication.
* Network relevancy.
* Replication prioritisation.
* Reconnection handling.

Test latency, packet loss and multiple simultaneous players.

⸻

PART 17 — SOCIAL FEATURES AND COMMUNITY SYSTEMS

Build the social framework.

Support:

* Friends.
* Player invitations.
* Fireteam communication.
* Text chat where appropriate.
* Voice chat integration.
* Player inspection.
* Block and report.
* Privacy settings.
* Social hub interactions.

Do not build unnecessary social features before core multiplayer works.

Design privacy and moderation controls from the beginning.

⸻

PART 18 — COLLECTIONS, ACHIEVEMENTS AND CHALLENGES

Create long-term goals beyond equipment power.

Support:

* Weapon collections.
* Armour collections.
* Cosmetics.
* Enemy discoveries.
* Lore collections.
* Exploration completion.
* Achievements.
* Challenges.
* Activity records.
* Milestones.
* Titles or player recognition.

These systems should reward different styles of play.

Avoid making every achievement require excessive repetitive grinding.

⸻

PART 19 — SEASONS, LIVE CONTENT AND EXPANSIONS

Design Project Orion so it can receive future content updates.

Support:

* Seasonal activities.
* New missions.
* New bosses.
* New weapons.
* New armour.
* New biomes.
* New story chapters.
* Limited-time events.
* New factions.
* Progression resets or extensions only where deliberately designed.

Use versioned data definitions and backward-compatible save migrations.

Do not build an expensive live-service infrastructure before the core game is complete.

Keep future content modular.

⸻

PART 20 — ECONOMY AND REWARD BALANCING

Create a coherent game economy.

Support:

* Standard currency.
* Crafting materials.
* Upgrade resources.
* Activity tokens.
* Rare boss materials.
* Vendor purchases.
* Repair or upgrade costs where appropriate.
* Reward distribution.

Every currency must have a purpose.

Every reward must have a clear source and spending destination.

Create developer tools for inspecting:

* Drop rates.
* Economy inflows.
* Economy outflows.
* Inventory distribution.
* Reward frequency.
* Progression speed.

Do not introduce monetisation or pay-to-win mechanics by default.

Prioritise gameplay-earned rewards and fair progression.

⸻

PART 21 — SAVE SYSTEM, BACKEND AND DATA MIGRATION

Build a persistent data architecture.

Support:

* Character state.
* Inventory.
* Equipment.
* Progression.
* Currencies.
* Quest state.
* World discoveries.
* Saved builds.
* Unlocks.
* Settings.

Use versioned save schemas.

Support migrations when data structures change.

Separate development saves from production persistence.

Prevent corruption and duplication during interrupted operations.

Important inventory and economy operations must be validated and transactional on the authoritative backend.

⸻

PART 22 — ANTI-CHEAT AND SECURITY

Design the game around server authority.

Never trust clients for:

* Damage.
* Loot generation.
* Currency.
* Item ownership.
* Inventory transfers.
* Movement validation where appropriate.
* Mission rewards.
* Boss completion.
* Crafting costs.

Implement appropriate validation and logging.

Consider:

* Speed and movement exploits.
* Weapon firing exploits.
* Invalid damage.
* Item duplication.
* Currency manipulation.
* Reward manipulation.
* Session abuse.
* Backend request abuse.

Use suitable anti-cheat integration for a commercial Steam multiplayer game.

Do not make unsupported claims about complete cheat prevention.

⸻

PART 23 — GRAPHICS, RENDERING AND VISUAL QUALITY

Project Orion must aim for high-quality modern PC graphics.

Use Unreal Engine 5 rendering features appropriately.

Evaluate:

* Nanite.
* Lumen.
* Virtual Shadow Maps.
* Temporal Super Resolution.
* Hardware ray tracing where appropriate.
* Volumetric fog.
* Global illumination.
* High-quality materials.
* PBR workflows.
* Virtual textures where appropriate.
* World Partition.
* HLOD.
* Niagara.

Graphics quality must be consistent across:

* Characters.
* Weapons.
* Enemies.
* Bosses.
* Buildings.
* Interiors.
* Terrain.
* Vegetation.
* Vehicles.
* Effects.

Avoid unfinished primitive-looking environments.

Use properly modelled and textured assets.

Do not assume Nanite or Lumen automatically solves poor asset quality or performance.

⸻

PART 24 — ASSET PRODUCTION PIPELINE

Use Blender as the primary external modelling and asset creation tool.

Create a consistent asset pipeline for:

* Characters.
* Armour.
* Weapons.
* Creatures.
* Bosses.
* Vehicles.
* Buildings.
* Props.
* Environment pieces.
* Decorations.

Requirements:

* Appropriate topology.
* UV mapping.
* PBR materials.
* Texture sets.
* Rigging.
* Animation compatibility.
* Collision meshes.
* LOD strategy.
* Correct scale.
* Consistent naming.
* Source asset preservation.

Use FBX or another suitable interchange format according to asset requirements.

Organise assets into reusable libraries.

AI-generated models may be used as starting points, but inspect and correct topology, UVs, geometry, materials, rigging and licensing before shipping.

Never present malformed or placeholder geometry as finished AAA assets.

⸻

PART 25 — UI, UX AND ACCESSIBILITY

Maintain a unified design system.

Support:

* Keyboard and mouse.
* Controller readiness.
* Different screen resolutions.
* 1080p, 1440p and 4K.
* Correct DPI scaling.
* Readable typography.
* Accessible colour contrast.
* Configurable HUD.
* Text scaling.
* Subtitles.
* Colourblind options.
* Adjustable screen shake.
* Motion effect options.

Avoid unnecessary UI updates every frame.

Use event-driven data updates.

⸻

PART 26 — AUDIO AND PRESENTATION QUALITY

Create an audio architecture that supports:

* Spatial audio.
* Environmental occlusion.
* Reverb.
* Dynamic music.
* Combat music transitions.
* Boss themes.
* Weapon audio layers.
* Creature audio.
* Dialogue.
* UI sounds.
* Environmental ambience.

Use original or properly licensed audio assets.

Audio must communicate important gameplay events.

⸻

PART 27 — PERFORMANCE AND SCALABILITY

The target is a high-quality PC game that performs reliably across a range of hardware.

The initial development machine includes an RTX 4070 Ti, but do not optimise exclusively for one GPU.

Create scalable graphics settings.

27.1 Performance goals

Establish performance targets for:

* 1080p.
* 1440p.
* 4K.

Measure actual performance before declaring targets achieved.

Use profiling to identify:

* GPU bottlenecks.
* CPU bottlenecks.
* Memory usage.
* Shader compilation.
* Draw calls.
* Animation cost.
* AI cost.
* Network cost.
* Loading time.
* Asset streaming.

27.2 Optimisation

Use:

* LODs.
* Nanite where appropriate.
* HLOD.
* Asset streaming.
* Instancing.
* AI update throttling.
* Animation budgeting.
* Efficient collision.
* Niagara scalability.
* Memory management.

Do not optimise blindly. Profile first, then fix measured bottlenecks.

⸻

PART 28 — DEVELOPMENT TOOLS AND DEBUGGING

Create internal tools to support development.

Useful tools include:

* AI debug visualisation.
* Boss phase debugging.
* Encounter spawning.
* Weapon testing range.
* Damage display.
* Loot generation testing.
* Inventory inspection.
* Item granting.
* Mission testing.
* World-generation seed controls.
* Performance overlays.
* Network simulation.
* Save-data inspection.

All debug tools must be development-only and excluded or properly secured in shipping builds.

⸻

PART 29 — AUTOMATED TESTING AND QUALITY ASSURANCE

Create a proper testing strategy.

Test:

* Player movement integration.
* Weapon functionality.
* Enemy AI.
* Boss encounters.
* Damage calculations.
* Loot generation.
* Inventory transactions.
* Progression.
* Mission completion.
* Extraction.
* Save/load.
* Multiplayer replication.
* Reconnection.
* Network latency.
* Performance.
* UI functionality.

Create automated tests for critical gameplay and economy logic.

Test edge cases:

* Full inventory.
* Disconnect during loot acquisition.
* Disconnect during crafting.
* Multiple players attacking one boss.
* Player death during extraction.
* Mission failure.
* Save migration.
* Interrupted transactions.

Do not mark a system complete because it compiles. It must also behave correctly in playtests.

⸻

PART 30 — STEAM AND COMMERCIAL RELEASE PREPARATION

Prepare the project for commercial PC distribution.

Support:

* Steam integration.
* Steam achievements.
* Cloud saves where appropriate.
* Player identity integration.
* Invitations where supported.
* Controller support.
* Graphics settings.
* Audio settings.
* Build configurations.
* Crash reporting.
* Logging.
* Patch compatibility.
* Version management.

Prepare:

* Development builds.
* Test builds.
* Release builds.
* Dedicated server builds.
* Packaging pipeline.
* QA checklist.
* Performance certification checklist.

Verify current platform requirements and licensing before release.

Do not assume that a successful editor build means the game is ready for Steam.

⸻

PART 31 — IMPLEMENTATION STRATEGY AND DEVELOPMENT PHASES

This is extremely important.

Do not attempt to implement all systems simultaneously.

First establish a master architecture and dependency map.

Then implement in the following order.

PHASE 0 — PROJECT AUDIT AND ARCHITECTURE

* Inspect the entire project.
* Audit existing movement and gunplay.
* Identify working systems.
* Create the architecture document.
* Identify dependencies.
* Establish naming conventions.
* Establish data structures.
* Establish coding standards.
* Identify risks.
* Produce an implementation roadmap.

Do not delete or overwrite existing systems.

PHASE 1 — CORE GAMEPLAY FOUNDATION

* Player integration.
* Enemy framework.
* Health and damage integration.
* Ability framework.
* Core combat data.
* Basic multiplayer-ready interfaces.

PHASE 2 — ENEMY AI AND ENCOUNTERS

* Perception.
* Navigation.
* Combat behaviour.
* Enemy archetypes.
* Squad coordination.
* Elite enemies.
* Encounter director.

PHASE 3 — BOSS FRAMEWORK

* Boss architecture.
* Weak points.
* Shields.
* Attack patterns.
* Combat phases.
* Boss arena.
* First complete boss.

PHASE 4 — LOOT AND PROGRESSION

* Item definitions.
* Weapon rolls.
* Perks.
* Armour.
* Rarity.
* Inventory.
* Equipment.
* Crafting.
* Player progression.
* Reward tables.

PHASE 5 — MISSIONS AND ACTIVITIES

* Mission framework.
* Objectives.
* Operations.
* Extraction.
* Rewards.
* Strikes.
* Public events.
* Mission replayability.

PHASE 6 — FIRST COMPLETE ENVIRONMENT

Build one polished biome.

Include:

* Terrain.
* Buildings.
* Interiors.
* Environmental storytelling.
* Enemy placements.
* Exploration.
* Mission encounters.
* A boss arena.
* Extraction location.

This biome must be suitable for a complete playable operation.

PHASE 7 — CITY AND NARRATIVE

* Main fortified city.
* Districts.
* Vendors.
* NPCs.
* Dialogue.
* Factions.
* Campaign structure.
* Story missions.

PHASE 8 — UI AND PRESENTATION

* Combat HUD.
* Inventory.
* Equipment.
* Menus.
* Map.
* Quest interface.
* Social interface.
* Audio.
* Animation.
* VFX.

PHASE 9 — VEHICLES AND WORLD INTERACTIVITY

* Vehicles.
* Environmental interaction.
* Destruction.
* Dynamic events.
* Weather.

PHASE 10 — MULTIPLAYER AND BACKEND

* Dedicated servers.
* Fireteams.
* Sessions.
* Matchmaking.
* Persistent player data.
* Inventory authority.
* Mission synchronisation.
* Reconnection.
* Security.

Multiplayer interfaces should have been considered earlier, but this phase completes and tests the online infrastructure.

PHASE 11 — CONTENT EXPANSION

* More biomes.
* More enemies.
* More bosses.
* More weapons.
* More armour.
* More activities.
* More factions.
* Additional campaign content.

PHASE 12 — POLISH AND COMMERCIAL PREPARATION

* Optimisation.
* Bug fixing.
* QA.
* Accessibility.
* Save migration.
* Anti-cheat integration.
* Steam integration.
* Packaging.
* Release testing.

⸻

PART 32 — STRICT DEVELOPMENT RULES

Follow these rules throughout the project.

1. Never rewrite working systems without a clear technical reason.
2. Never create duplicate gameplay systems.
3. Never create massive monolithic C++ classes.
4. Never hardcode large collections of item, enemy or mission data when Data Assets are appropriate.
5. Never use placeholder primitive geometry as finished production content.
6. Never claim functionality works without testing it.
7. Never sacrifice performance for unnecessary complexity.
8. Never introduce systems that contradict existing gameplay architecture.
9. Never silently remove existing features.
10. Never create fake multiplayer functionality and describe it as real online infrastructure.
11. Never make client-controlled loot or currency authoritative.
12. Never build all content simultaneously.
13. Never leave compilation errors unresolved before proceeding to dependent phases.
14. Preserve source assets and existing project backups.
15. Document important architectural decisions.
16. Make systems modular and expandable.
17. Keep the game playable throughout development.

Development reporting

After each implementation phase, provide:

* What was inspected.
* What was implemented.
* Files created.
* Files modified.
* Systems integrated.
* Compilation results.
* Tests performed.
* Known bugs.
* Remaining tasks.
* Dependencies for the next phase.

Clearly distinguish:

* Fully implemented.
* Partially implemented.
* Prototype.
* Planned.
* Blocked.

Never confuse a plan with completed work.

⸻

PART 33 — FIRST TASK

Do not immediately attempt to generate the entire game.

Your first task is to perform a complete technical audit of the existing Project Orion project.

Then produce:

1. Project architecture report.
2. Existing system inventory.
3. Missing system inventory.
4. Compatibility and integration report.
5. Recommended folder and module structure.
6. Dependency map.
7. Development phase roadmap.
8. Technical risks.
9. Recommended first implementation milestone.

Preserve the existing movement and gunplay systems.

After presenting the audit, begin implementing Phase 0 and prepare Phase 1.

Do not proceed blindly if a missing dependency or architectural conflict could cause major rework.

FINAL VISION

Project Orion must become a cohesive, polished, original sci-fi looter shooter.

The player should be able to:

* Leave a massive fortified human city.
* Explore a transformed and dangerous Earth.
* Discover mysterious locations.
* Fight intelligent alien enemies.
* Defeat elite creatures and enormous bosses.
* Complete cooperative operations.
* Extract with valuable equipment.
* Discover legendary and exotic weapons.
* Build specialised character loadouts.
* Upgrade armour and abilities.
* Return to a living social hub.
* Progress through a compelling campaign.
* Play with friends.
* Discover new content through future expansions.

Every system must contribute to one coherent experience.

The objective is not to create the largest possible game immediately.

The objective is to create a strong, technically sound foundation and progressively turn it into a complete commercial AAA-quality experience.
