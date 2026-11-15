# Project Orion: technical audit

Date 2026-11-12, at commit `9b3313e` (branch `claude/chat-session-qx6qg2`). The brief this answers is
`MASTER_BRIEF.md` (Part 33, "First task"). The plan that follows from it is in `ARCHITECTURE.md` and `ROADMAP.md`.

**How it was done.** Every C++ module, every `Build.cs` / `Target.cs`, the `.uproject`, `Config/*.ini`, `Data/*.json`,
the import and level-building scripts and the existing docs were read (four read-only passes by area, plus my own
inventory). No code was changed and nothing was built or run for this audit. The last full test run was at this
commit: 74 of 74 automation tests passing.

**What this audit cannot say.** Binary assets (`.uasset`) were not opened, so statements about data assets come from
the C++ and the json that produces them. Nobody has played the current build; every "works" below means "the code is
there and its automation test passes", not "it feels right". Nothing multiplayer has an automated test.

Status words used throughout, as the brief asks: **Full** (implemented and tested), **Part** (works but with named
gaps), **Prototype** (a first version that will be replaced), **None** (not in the project), **Blocked**.

---

## 1. The short answer

The project is a real game core, not a prototype: 8 C++ modules, about 31,500 lines, 74 automation tests, three
levels, 31 guns, 7 creature classes, one 20-stage operation, and a Blender pipeline of 75 scripts (35,000 lines) that
makes every model and texture.

| Area | State |
|---|---|
| Movement, gunplay, reloads, the gun in the hands | **Full**. The strongest part of the project. Network-predicted movement. |
| Health, shields, damage | **Full**. One damage path for players and creatures, on Unreal's Gameplay Ability System. |
| Enemy brain and the six creature kinds | **Full**. Hand-written, tested: senses, cover, flanking, squad alerts. |
| Operation (mission) framework | **Part**. Stages, waves, checkpoints, boss, rewards. No failure, no extraction. |
| Guns as loot | **Full**. Rolls, rarity, nine perks with real effects, drops, chests, set rewards. |
| Player abilities and classes | **None**. No grenade, melee, class ability, ultimate, or archetype. |
| Armour as gear | **Prototype**. Worn and owned, but its numbers change nothing. |
| Economy | **Prototype**. Two currencies are earned and can be spent on nothing. |
| Menus and settings | **None**. No main menu, pause menu or settings screen. |
| Online (sessions, accounts, saved profiles for guests) | **None**. Two players can only join through the editor. |
| A packaged build | **None**. The game has only ever run from the editor's binaries. |

Three findings would cause rework if left until the brief's last phases. They are cheap now:

1. **The game cannot be packaged as it stands.** Only the test range is listed to be cooked, and the game reads
   `Data/*.json` and a 12.7 MB instance file straight from the project folder, which a packaged build does not have.
2. **Aiming is not known to the server.** `bAiming` lives only on the player's own machine, so for a joined player
   the server computes hip-fire spread even when they are on the sights.
3. **The arrival screen loads almost everything in `/Game`.** It is right for three areas and wrong for thirty.

---

## 2. Architecture report

### Modules (`unreal/ShatteredOrbit/Source`)

| Module | Lines | What it is | Depends on (ours) |
|---|---|---|---|
| `SOCore` | 1,083 | Log, user settings, `USOAreaSubsystem` (areas, travel, arrival screen) | none |
| `SOWorld` | 1,930 | Nexus Prime's runtime builder, weather, time of day, map info and points | SOCore |
| `SOCombat` | 7,993 | Ability system and attributes, weapons, projectiles, reloads, gun rig, effects, sound, loot, inventory, wardrobe data | SOCore |
| `SOCharacter` | 6,395 | The player: character, movement component, look, view model, animation instance | SOCore, SOCombat |
| `SOAI` | 3,680 | `ASOEnemy`, the brain, the species, the species library | SOCore, SOCombat, SOCharacter |
| `SOOperation` | 1,402 | `ASOOperation`, barriers, ambience | SOCore, SOCombat, SOCharacter, SOAI, SOWorld |
| `SOUI` | 2,904 | Canvas HUD, loadout screen, map screen | all of the above but SOAI |
| `ShatteredOrbit` | 6,145 | Game mode, controller, player state, game instance, all automation tests | all |

The layering is clean: no circular dependency and no include that reaches upward. Two small flaws: `SOUI` includes
an `SOAI` header without declaring the dependency (it builds only through `SOOperation`), and `SOOperation` declares
`SOCharacter` without using it.

### Engine features in use
Enabled plugins: EnhancedInput, GameplayAbilities, CommonUI, StateTree, GameplayStateTree, PythonScriptPlugin,
EditorScriptingUtilities. Of these, **StateTree is enabled and used nowhere**, and **CommonUI is used only by a stub**
(`USOActivatableWidget`). Not present: Niagara, any OnlineSubsystem, Steam, PCG, Chaos destruction, Chaos vehicles,
World Partition, level streaming, HLOD, MetaSounds.

Rendering (`Config/DefaultEngine.ini`): DX12 / SM6, Nanite, software Lumen, virtual shadow maps, TSR, virtual
textures; `DefaultScalability.ini` drops Lumen and virtual shadow maps on the two lowest levels.

### Framework classes
- `ASOGameMode` (`AGameModeBase`): default classes, respawn after 4 s at the operation's checkpoint.
- No custom game state. `ASOPlayerState` holds the inventory. `USOGameInstance` applies graphics settings.
- `ASOPlayerController`: about 100 lines of game code and about 1,400 lines of developer screenshot script.
- Subsystems: `USOAreaSubsystem` (game instance); `USOProjectileSubsystem`, `USOFxSubsystem`, `USOLootSubsystem`,
  `USOWeatherSubsystem`, `USOTimeOfDaySubsystem` (world).

### How data flows
`Data/game_data.json` (guns, rarity, perks, sights, names) and the Blender output are turned into Unreal data assets
by `Content/Python/import_assets.py`; gameplay reads the data assets. Three things bypass that and read loose files
at runtime from the project folder: `areas.json` (`SOAreaSubsystem.cpp:459`), the operation plan
(`SOOperation.cpp:232`) and Nexus Prime's plan and instance file (`SONexusCity.cpp:27,345`).

### The one damage path
`USOCombatStatics::ApplyDamage` (server only) → immunity → the target's own scaling (`ScaleIncomingDamage`) →
faction check → one GameplayEffect into `IncomingDamage` → shield first, then health (`USOAttributeSet`) → death.
Every source of damage in the game goes through it: rounds, splash, acid, pools, falls, claws, slams, bolts.

### Who decides what (replication)
Server decides and replicates: movement (predicted on the client), firing, damage, death, ammo, reload grants,
inventory, loot, enemy brains, operation state. 55 replicated properties and remote calls across 12 files. There is
no client-side prediction of firing, no lag compensation, no validation on any of the 15 client-to-server calls.

### Levels
All three maps are single classic levels made by editor Python scripts. `L_Nexus` is one actor that builds the city
at runtime from a plan (about half a million instances). `L_Meridian` is zone meshes placed at the origin with
hidden exact collision beside them.

---

## 3. Existing system inventory

By the brief's parts. File references are under `unreal/ShatteredOrbit/Source`.

| Brief part | System | Status | Where | Notes |
|---|---|---|---|---|
| 2 | Player movement | **Full** | `SOCharacter/.../SOCharacterMovementComponent` | Sprint, slide, air jump, coyote time, vault / mantle / climb, fall damage. Saved moves and compressed flags. 16 tests. |
| 2 | Gunplay | **Full** | `SOCombat/.../SOWeapon`, `SOProjectileSubsystem`, `SOReload` | Simulated rounds with drop, auto / semi / burst, pellets, ADS, recoil, keyframed reloads moving real parts. |
| 2 | Gun in the hands | **Full** | `SOGunRigComponent`, `SOViewmodelComponent`, `SOLocomotionAnimInstance` | Arm IK onto grips in both views, sights on the eye line (tested for every gun and sight). |
| 2 | Health / shields / damage | **Full** | `SOCombatStatics`, `SOAttributeSet`, `SOAbilitySystemComponent` | Shared by players and creatures. Precision hits by bone, distance falloff. |
| 2 | Death and respawn | **Full** | `SOCombatCharacter`, `SOGameMode` | No downed state, no revive. |
| 2 | Input | **Full** | `Content/Input`, `setup_input.py` | Enhanced Input, 19 actions, gamepad mapped. No rebinding. |
| 3 | Ability system base | **Part** | `SOAbilitySystemComponent`, `SOAttributeSet` | The engine's ability system is wired for health and damage only. No ability class exists. |
| 4 | Enemy base and species | **Full** | `SOAI/.../SOEnemy`, `Species/*`, `SOSpecies` | One class per species, found by `USOSpeciesLibrary`; variants as data. |
| 4 | Perception | **Full** | `SOEnemyAIController` | Sight cone and peripheral band, awareness that fills, hearing, hit events, last known position, search. |
| 4 | Tactics | **Full** | `SOEnemyAIController` | Cover scoring, peek and duck, flankers, retreat when hurt, sidestep, squad alert, pushes. |
| 4 | Roster | **Part** | `SOAltered.h` | Feral stalker, armed stalker, Remnant, Veilborn, Bulwark, conduit, Colossus. See section 4 for the brief's eight roles. |
| 5 | Boss | **Part** | `Species/SOColossus.cpp` | Shield phases at 2/3 and 1/3, conduits, slam / sweep / barrage, stagger. Written into one class. |
| 6 | Weapon loot | **Full** | `SOLootLibrary`, `SOLootTypes`, `SOLootActors` | Five rarities, stat rolls, perks, sights, drops, chest, set rewards. 6 tests. |
| 6 | Perks | **Part** | `SOWeapon.cpp`, `SOLootLibrary.cpp` | Nine perks, all with real effects, each a hard-coded name check. |
| 6 | Inventory | **Part** | `SOInventoryComponent` | On the player state, replicated, server RPCs. One list of 200; lock, dismantle, auto-dismantle of overflow. |
| 6 | Armour | **Prototype** | `SOWardrobe.h`, `SOInventoryComponent` | Seven slots, worn and earned. Rarity, power and rating are stored and affect nothing. |
| 6 | Progression | **Prototype** | `SOInventoryComponent` | Level and XP rise; level only scales credit rewards. Power = average of equipped guns. |
| 7 | Operation | **Part** | `SOOperation/.../SOOperation` | Travel / clear / hold / boss stages, waves, spawn groups, checkpoints, barriers, briefing, intel, end screen, rewards. |
| 8 | World building | **Part** | `tools/blender/meridian*.py`, `citykit.py`, `SONexusCity` | Offline, deterministic, rule-driven (not random). No engine PCG, no streaming. |
| 9 | City | **Part** | `L_Nexus`, `SONexusCity` | Built and dressed; empty of people, vendors and services. |
| 10 | HUD | **Part** | `SOUI/.../SOHUD` | Canvas-drawn: crosshair, hit markers, health, ammo, feed, minimap, objective, boss bar, briefing, end screen. Polls every frame. |
| 10 | Loadout screen | **Full** | `SOInventoryWidget` | Redesigned 2026-11-12; first pass, no tabs. |
| 10 | Map screen | **Full** | `SOMapWidget` | Points, quick travel, area travel. |
| 11 | Player animation | **Full** | `tools/blender/hero/*/motion.py`, `SOLocomotionAnimInstance` | Own clip set per body. No melee, throw, cast, revive or emote clips. |
| 11 | Effects | **Part** | `SOFxSubsystem` | Our own instanced-card particle system (1,500 particles), decals, flash lights. Not Niagara. |
| 11 / 26 | Audio | **Part** | `SOSound`, `tools/audio/sfx_synth.py` | 262 synthesised sounds, three attenuation presets. No music, occlusion, reverb, mix or volume settings. |
| 14 | Weather | **Part** | `SOWorld/.../SOWeather` | Seven states, wind, rain, fog, lightning, ambience. Each machine rolls its own. |
| 16 | Listen-server play | **Part** | across modules | Server-authoritative design. Never tested by automation; joining only through the editor. |
| 21 | Saving | **Prototype** | `USOSaveGame` | One local file, the host's only. Written synchronously on every inventory change. Version written, never read. |
| 21 | Settings storage | **Part** | `SOCore/.../SOGameUserSettings` | Look, FOV and graphics fields exist and apply. Nothing saves or edits them in game. |
| 24 | Asset pipeline | **Full** | `tools/blender`, `export_fbx.py`, `import_assets.py` | Every model and texture from our own scripts; sources kept; names are an API. |
| 28 | Developer tools | **Part** | `SOPlayerController`, `SOAreaSubsystem` | Screenshot series, benchmark, census, area tour. None compiled out of a shipping build. |
| 29 | Automated tests | **Full** | `ShatteredOrbit/Private/Tests` | 74 tests: movement 16, animation 8, AI 7, loot 6, hold and aim 8, and more. All single-machine. |

---

## 4. Missing system inventory

**Part 3, abilities and classes.** Everything: grenade, melee, class ability, ultimate, cooldowns, charges, the three
archetypes, upgrades, saved configurations. The input set has no ability actions.

**Part 4, enemies.** Against the brief's eight roles:

| Brief role | What we have | Gap |
|---|---|---|
| Swarmer | Feral stalker (claws, lunge) | It is a lone hunter, not a pack animal; no swarm behaviour. |
| Grunt | Armed stalker | Covered. |
| Assault unit | Remnant | Covered. |
| Heavy gunner | Bulwark (shield, shotgun, slam) | No suppression behaviour; the HMG is only on the boss. |
| Sniper | Veilborn (scout rifle, blink, void bolt) | Close; no long-range telegraphed shot. |
| Commander | Named elites exist only as stat variants | No creature that directs others. |
| Disruptor | none | New. |
| Elite hunter | none | New. |

Also missing: any difficulty setting, scaling by player count, switching target once in combat, throttling of distant
creatures, an encounter director outside the operation actor.

**Part 5, bosses.** A reusable framework (phases, weak points on the body, attack sets as data); warnings before
attacks beyond the animation itself (no sound cue, no ground marker); the four named bosses. The Warden is a Bulwark
with bigger numbers.

**Part 6, loot and progression.** Armour stats, perks and set bonuses; character attributes; upgrades, crafting,
infusion; any way to spend credits or alloy; materials and consumables as items; favourites, user sorting, filters,
search; saved loadouts; a separate overflow store; exotic guns with their own mechanics; changing a gun's sight or
finish from the screen (both are stored, neither can be changed).

**Part 7, missions.** Extraction; failure, squad wipe and encounter reset; revives; objective kinds beyond the four
(collect, activate, destroy as a real kind, rescue, investigate); optional objectives; difficulty variants; a mission
subsystem that lists activities; bounties, public events, weekly goals. A second operation would need more than a
new plan file: the level builder script names Meridian's files.

**Part 8, world.** Engine PCG, World Partition, streaming, HLOD; biomes other than the ruined city; open exploration
(hidden places, resources, collectibles).

**Part 9, city life.** NPCs, vendors, dialogue, quest givers, services, other players in the hub. (People and
vehicles were kept out of Nexus Prime on the owner's earlier instruction; the brief places them in phases 7 and 9.)

**Part 10, interface.** Main menu, pause menu, settings screen, quests, collections, crafting, vendor and social
screens; drag and drop; HUD and text scaling, colour-blind options, subtitles options.

**Parts 12 to 14.** Vehicles; destruction; doors and consoles (the only interactable is the reward chest); world
events. Weather exists.

**Part 15, story.** The world bible exists (`docs/story/WORLD.md`, four human factions, the Altered) and the
operation has a written reason. Missing: dialogue system, records to find, campaign structure, cinematics.

**Parts 16, 17, 22, online.** Sessions, invitations, matchmaking, accounts, a profile service, reconnection, lag
compensation, validation of client calls, anti-cheat, friends, chat, voice, block and report. A dedicated server
target file exists but needs an engine built from source; none has been built.

**Parts 18 to 20.** Collections, achievements, challenges, seasons, vendors, economy tools.

**Part 21, saving.** Guests' profiles (a joined player always starts fresh and loses everything on travel); schema
migration; safe writes; settings that persist from in-game.

**Part 27, performance.** No measurement on a mid-range PC. The area tour records frame rate on this machine only.

**Part 30, release.** No packaged build of any kind, no packaging script, no Steam, no crash reporting.

---

## 5. Compatibility and integration report

### What already satisfies the brief's integration rules
- One health and damage system for players, creatures and bosses. Enemy guns are the player's `ASOWeapon`.
- Loot, drops, chests and operation rewards all write into one inventory component.
- The HUD shows real gameplay data (no mock values).
- Creatures are added in one file each and spawned through one function.
- Animation, sound, camera and effects listen to one movement-event source.

### Duplicates and loose ends to remove (none need a rewrite)
| What | Where | Why it matters |
|---|---|---|
| Ammo is stored twice (the gun actor and the owned copy) and reconciled by hand | `SOWeapon`, `SOInventoryComponent`, `SOLootActors.cpp:193` | A place for duplication bugs once crafting and vendors touch ammo. |
| Health is written outside the damage effect by `Heal` and shield regeneration; two creatures are killed by calling `Die` directly | `SOCombatCharacter.cpp:232`, `SOAbilitySystemComponent.cpp:28`, `SOOperation.cpp:516`, `SOColossus.cpp:366` | Abilities that heal, shield or prevent death need one path. |
| Burn, pools and swarms are private arrays in the projectile subsystem, unreplicated | `SOProjectileSubsystem` | Ability and perk effects (slow, stun, mark) need a shared, replicated status system. |
| Perks are name checks spread over three files | `SOWeapon.cpp`, `SOLootLibrary.cpp`, `SOInventoryComponent.cpp` | Fine for nine; the perk design in `docs/design/PERK_IDEAS.md` needs them as data. |
| Two lists of areas | `SOMap.cpp:93` (hard-coded) and `Data/areas.json` | The names already differ. |
| Hurt detection three times; spawn offsets applied twice | `SOEnemy.cpp`, `SOEnemyAIController.cpp`, `SOOperation.cpp:588`, `SOSpecies.cpp:134` | Harmless today; confusing when tuning. |
| Rarity colour lookups and weighted picks re-written in several places | loot, HUD, inventory, operation | Small. |
| Unused: StateTree plugins, `USOActivatableWidget`, a GameplayCue path to a folder that does not exist, the save `Version`, `MarkAllSeen`, the `bBrute` drop bonus, the finish table | various | Remove or use. |
| README and migration plan out of date (35 tests, missing module, stale gaps) | `unreal/ShatteredOrbit/README.md`, `docs/unreal/MIGRATION_PLAN.md` | They mislead a new reader. |

### What will conflict with the brief's later phases unless handled early
1. **Packaging**: one map in `MapsToCook`; loose `Data/` files; developer commands with no shipping guard.
2. **Aim state not on the server** (`SOCharacter.h:467`). The movement component already sends an aim flag; the
   character ignores it.
3. **Shot effects for the shooter arrive by an unreliable broadcast** from the server: no recoil or flash on a lost
   packet, and a delay at any latency.
4. **Hit markers exist only on the host.**
5. **Sounds and effects played on the server only** never reach joined players: creature voices, the boss's slam,
   sweep and shield, blink, bolt impacts.
6. **Any joined player can move the whole server** to another area; the operation's start does not wait for joined
   players who are still loading.
7. **Inventory replicates to everyone** rather than to its owner; every change saves the file synchronously.
8. **Arrival preloads nearly all of `/Game`**; **loot rolls load every gun's data synchronously on each call**.
9. **Per-frame world scans**: the HUD iterates every character each frame; the interact check scans every actor;
   pickups scan every character each tick; creatures are never throttled by distance.
10. **The ability system component lives on the pawn**, so anything an ability should keep across a respawn
    (charge, cooldowns) is lost with the body.
11. **Large classes**: `SOCharacter.cpp` (1,942 lines, about thirteen jobs), `SOInventoryWidget.cpp` (1,457),
    `SOLocomotionAnimInstance.cpp` (1,385), the controller's screenshot script (1,385).
12. **The operation plan is read from disk by every machine** and is not replicated.

### The brief's suggested classes against what exists
The brief's names are suggestions ("Suggested architecture"); its own rules forbid duplicate systems and rewriting
what works. So each maps onto an existing class, or onto a planned one that keeps the project's `SO` prefix.

| Brief's suggestion | In this project | Status |
|---|---|---|
| `AProjectOrionEnemyBase` | `ASOEnemy` | exists |
| `UProjectOrionEnemyAIController` | `ASOEnemyAIController` | exists |
| `UEnemyHealthComponent` | `USOAbilitySystemComponent` + `USOAttributeSet` (shared with the player) | exists; do not add |
| `UEnemyMovementComponent` | the engine's character movement | exists; do not add |
| `UEnemyPerceptionComponent`, `UEnemyCombatComponent` | inside the controller and `ASOEnemy` | split out in phase 2 |
| `UEnemyAbilityComponent` | the shared ability framework | phase 1 |
| `UEnemySquadComponent` | static delegates today | `USOSquad`, phase 2 |
| `UEnemyDifficultyComponent`, `UEnemyDataAsset` | `FSOSpeciesVariant` (data) | difficulty table, phase 2 |
| `AProjectOrionBossBase` and boss components | `ASOEnemy` with a `BossId` + `USOBossComponent` / `USOBossData` (phases, weak points, shield); attacks are kits; encounter and reward are the operation's | done in phase 3 (`reports/PHASE_3.md`) |
| `UProjectOrionItemDefinition` / `ItemInstance` | `USOWeaponData`, `FSOWardrobeItem` / `FSOWeaponInstance`, `FSOArmorInstance` | exist; common base in phase 4 |
| `UProjectOrionLootGenerator`, `LootTable` | `USOLootLibrary`, `USOLootTables` | exist |
| `UProjectOrionInventoryComponent`, `EquipmentComponent` | `USOInventoryComponent` | exists |
| `UProjectOrionStatComponent` | `USOAttributeSet` | extend in phase 4 |
| `UProjectOrionPerkComponent` | name checks | perks as data, phase 4 |
| `UProjectOrionProgressionComponent` | level and XP inside the inventory | split out in phase 4 |
| `UProjectOrionRewardComponent` | `ASOOperation::GrantReward`, `ASOReliquary` | exist |
| `UProjectOrionMissionSubsystem`, `MissionDefinition` | `ASOOperation` + plan json | subsystem in phase 5 |
| `UProjectOrionObjectiveComponent` | the four stage kinds | objective classes, phase 5 |
| `UProjectOrionEncounterDirector` | wave logic inside `ASOOperation` | split out in phase 2 |
| `UProjectOrionExtractionComponent` | none | phase 5 |
