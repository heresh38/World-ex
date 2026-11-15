# Project Orion: roadmap, risks and the first milestone

Phase 0 of `MASTER_BRIEF.md`, written 2026-11-12. The phases are the brief's (Part 31), in the brief's order; what
changes is where each one starts, because the project is not empty. Status words: **Full**, **Part**, **Prototype**,
**None**. Nothing below is done unless it says so; each phase gets its own report when it ends.

## 1. Where each phase starts

| Phase | The brief asks for | Starts from | Main work left |
|---|---|---|---|
| 0 Audit and architecture | Audit, architecture, standards, roadmap | **Full** with these documents | Refresh the two stale docs (README, migration plan). |
| 1 Core gameplay foundation | Player integration, enemy framework, health and damage, ability framework, combat data, multiplayer-ready interfaces | Player, enemies, health and damage **Full**; abilities **None**; interfaces **Part** | The ability framework and one complete kit; the multiplayer gaps; the packaging and profile-store boundaries. Detailed in section 4. |
| 2 Enemy AI and encounters | Perception, navigation, combat behaviour, archetypes, squads, elites, director | Brain **Full**; roster **Part** (all 8 roles as variants and kits, none with a body of its own); against the owner's AI brief of 2026-11-13 (`AI_BRIEF.md`) see `reports/AI.md`: more than half exists; the director, patrols, a squad object and all role art are missing | Swarm behaviour, a commander, a disruptor, an elite hunter; difficulty table; target switching; distance throttling; squad object; director split from the operation. |
| 3 Boss framework | Architecture, weak points, shields, patterns, phases, arena, one complete boss | Framework **Full**, the Colossus on it **Part** (2026-11-12, `reports/PHASE_3.md`) | Collision bodies that follow the drawn body; Colossus clips for reeling, a phase beginning and the call; arena hazards; the owner's play-through. A second boss only after that (a new creature in Blender first). |
| 4 Loot and progression | Items, rolls, perks, armour, rarity, inventory, equipment, crafting, progression, reward tables | Guns **Full**; armour stats, attributes, upgrades, level curve **Full** (2026-11-13, `reports/PHASE_4.md`); the rest **Planned** | `SOLoot` split; armour that counts; attributes; perks as data (the design in `docs/design/PERK_IDEAS.md`); sinks for both currencies; upgrades; locker management; unique guns with their own mechanics. |
| 5 Missions and activities | Mission framework, objectives, operations, extraction, rewards, events, replay | Operation **Part** | Objectives as classes; extraction; failure, wipe, reset; downed and revive; mission subsystem; optional objectives and difficulty variants; the level builder freed of Meridian's names. |
| 6 First complete environment | One polished biome fit for a full operation | Meridian Fall **Part**: built end to end, 20 stages; never played or judged by the owner | The owner's play-through and what it finds; the open items in `docs/operation/MERIDIAN_OVERHAUL.md`; an extraction site. |
| 7 City and narrative | The city, districts, vendors, NPCs, dialogue, factions, campaign | City shell **Part**; story bible **Part**; people **None** | Interactables, dialogue data, vendors, the people themselves (models, clips), district purposes, campaign structure. |
| 8 UI and presentation | HUD, inventory, menus, map, quests, social, audio, animation, effects | HUD, loadout, map **Part**; menus and settings **None** | Main and pause menus, settings that save, event-driven HUD, scaling and accessibility, music, mix, occlusion, the Niagara question. |
| 9 Vehicles and interactivity | Vehicles, interaction, destruction, events, weather | Weather **Part**; the rest **None** | All of it. Weather needs one shared seed per server. |
| 10 Multiplayer and backend | Dedicated servers, squads, sessions, matchmaking, persistence, security | Server-authoritative design **Part**; online **None** | Engine from source, sessions, profile service, reconnection, lag compensation, tests under latency and loss. |
| 11 Content expansion | More of everything | n/a | After the loop is proven. |
| 12 Polish and release | Optimisation, QA, accessibility, migration, anti-cheat, Steam, packaging | **None** | All of it; packaging is proven early (section 3) so this phase holds no surprise. |

The brief's order holds. Two items are pulled forward into phase 1 because leaving them would force rework of
everything built in between: a **packaged-build smoke test** and the **profile store interface**.

---

## 2. Technical risks

Ordered by how much they could cost.

| # | Risk | Evidence | What limits it |
|---|---|---|---|
| 1 | **Scope.** The brief describes years of work for a large studio. | 33 parts; the project has one operation and no abilities after its first weeks. | The brief's own rule: one complete loop before breadth. Every phase ends playable; phase 11 does not start until the loop in section 3 is played and judged. |
| 2 | **Nothing has been judged by playing.** Every check so far is an automation test, a measurement or a still. | 74 tests, no play notes. | The owner plays at each phase's end; a system is not "Full" in a report until then. |
| 3 | **The art pipeline's ceiling.** Every model comes from scripts. That keeps the game ours and reproducible; it also makes "AAA" surfaces slow to reach (faces, creatures, cloth). | Six passes on the guns; the README's own note on the faces. | Decide per asset class how far scripts go; the owner rules on rule 2 of `ARCHITECTURE.md` section 5. |
| 4 | **Never packaged.** | One map cooked; loose data files; no shipping guards; no packaging script. | Phase 1 smoke test: a packaged development build that reaches the range, the city and the operation. |
| 5 | **Multiplayer is designed for but unproven.** | No networked test; aim not on the server; server-only sounds and effects; unvalidated calls; guests lose their profile. | Phase 1 closes the known gaps; every new system gets a two-player check; latency and loss tests in phase 10. |
| 6 | **The dedicated server needs an engine built from source.** | `ShatteredOrbitServer.Target.cs`'s own comment; the installed engine ships no server binaries. | A listen server carries development; the source build is a phase 10 task of its own (disk, hours). |
| 7 | **The graphics-card hang entering Meridian.** | One crash log: device hung in Nanite shadow culling 3 s after arrival, in the editor. Not reproduced. | The arrival screen is a mitigation, not a fix. Keep the log; test on the owner's machine in a packaged build, where it matters. |
| 8 | **Performance is unmeasured on a mid-range PC.** | Only this machine's numbers (RTX 4070 Ti class). | Scalability levels exist; measure in the packaged build at 1080p / 1440p / 4K before any claim. |
| 9 | **Loading everything on arrival.** | `USOAreaSubsystem::AssetsFor` takes all of `/Game` but other areas' folders. | Per-area asset lists before a fourth area exists. |
| 10 | **Per-frame costs that grow with content.** | HUD and pickups scan every character; interact scans every actor; no distance throttling of creatures; cover search is 48 × N. | Registries and throttling in phases 1 and 2; profile first, as the brief says. |
| 11 | **Saves can be lost or duplicated.** | Synchronous write on every change, no temporary file, version never read. | The profile store in phase 1; transactions in phase 4. |
| 12 | **Large classes slow every change.** | `SOCharacter.cpp` 1,942 lines; the controller; the loadout widget. | Cut each when its phase touches it, with the tests as the net. |
| 13 | **Borrowed words reach the screen.** | The brief's attribute and activity names. | `ARCHITECTURE.md` section 5; nothing borrowed is shown until ruled. |

---

## 3. Recommended first milestone

**"One kit, one loop, one package."** The smallest thing that proves the brief's foundation end to end, built on
what exists and breaking none of it:

1. A player picks **one archetype** and has its grenade, melee, class ability and ultimate, each with its clip,
   sound, effect, cooldown and HUD readout, working for a host and a joined player.
2. That player runs **Meridian Fall** with them: the creatures take and survive the abilities through the one
   damage path, the Warden and the Colossus fights hold up.
3. The same build **starts from a packaged folder**, not the editor.

Why this and not more: it exercises every interface the later phases hang from (abilities on the combat core, status
effects, tags, input, HUD events, replication, data to asset, packaging) with the least new content. The other two
archetypes, new creatures and the boss framework then add to a proven base instead of to an assumption.

It is phase 1 of the brief plus the two items pulled forward. Extraction, the loop's last third, is phase 5.

---

## 4. Phase 1, prepared

Work items in order. Each ends with the build clean and the full test run passing before the next begins.

| # | Item | What is made | Done when |
|---|---|---|---|
| 1.1 | **Packaged smoke test** | All three maps in `MapsToCook`; `Data/` read through data assets or staged; a `tools/package.sh` | A packaged development build starts, shows the range, travels to the city and the operation. Findings listed, not necessarily all fixed. |
| 1.2 | **`SODev` module** | Screenshot series, benchmark, tour, census, cheats moved out of the controller and the area subsystem | Shipping configuration compiles without them; the capture sets still run in development. |
| 1.3 | **Gameplay tags** | Native tag tables `State.*`, `Ability.*`, `Cooldown.*`, `Status.*`, `Damage.*`, `Event.*`; `State.Dead` and the movement states set through them | A test reads each state tag on a living, sprinting, aiming and dead character. |
| 1.4 | **One path for health** | Heal, shield regeneration and scripted kills as GameplayEffects | Existing `Combat.*` tests pass; new test: a heal and a regen tick appear as effects. |
| 1.5 | **Status effects** | `Status.Burn` (moved from the projectile subsystem), `Status.Slow`, `Status.Stagger` as replicated effects with a HUD and a creature readout | Acid still burns exactly as before (same numbers); slow and stagger tested on player and creature. |
| 1.6 | **Ability base** | `USOGameplayAbility`, cooldown and charge effects, `USOAbilitySet`, grant on possess, kept state on the player state | Tests: activate, cooldown, charges, blocked while dead / traversing, survives respawn where it should. |
| 1.7 | **Data** | `"abilities"` and `"kits"` in `Data/game_data.json`; import to `DA_AbilitySet_<Kit>` | A number changed in the json changes the ability after re-import; no number in C++. |
| 1.8 | **Input** | `IA_Grenade`, `IA_Melee`, `IA_ClassAbility`, `IA_Ultimate` in `setup_input.py`, keyboard and gamepad | `Content.InputAssets` covers them. |
| 1.9 | **Body clips** | Throw, strike, cast and ultimate clips for both bodies (`hero/<sex>/motion.py`), first-person arms included | Frames looked at before import; `Anim.*` tests pass. |
| 1.10 | **The first kit, complete** | Four abilities for one archetype with model parts, sounds (`sfx_synth.py`) and effects | Each: used on creatures in a test; seen in stills; then played. |
| 1.11 | **HUD** | Cooldowns, charges and the ultimate meter, driven by events; the per-frame character scan replaced by a registry | No world scan in `DrawHUD`. |
| 1.12 | **Multiplayer gaps** | Aim state on the server; validation on all 15 client calls; only the host (later the squad leader) may travel; inventory to owner only; shot feedback predicted for the shooter; hit markers, creature voices and boss effects reach joined players | A two-player check list run in the editor, written into the report; spread on the sights measured on a joined player. |
| 1.13 | **Profile store** | `ISOProfileStore` and the local implementation (asynchronous, versioned, temporary file then rename); the inventory stops saving itself | Kill the game during a save: the old file is intact. A version-1 file loads. |
| 1.14 | **Creatures on the same framework** | The Veilborn's bolt and the Bulwark's slam as abilities | `Altered.*` tests pass unchanged. |
| 1.15 | **Report** | `docs/orion/reports/PHASE_1.md`; README and `CLAUDE.md` updated | The owner has played it. |

**Which kit first.** Recommended: the frontline one (the brief's Vanguard). Its abilities reuse the most existing
code (a thrown charge on the projectile subsystem, a strike on `DamageAround`, a barrier on the operation's barrier
material, a slam like the Bulwark's), so the framework is tested by the abilities rather than by new technology.
The brief asks that a class be more than a loadout, so the kit also gets a passive rule of its own, to be designed
with the kit, not here.

**Open choices that do not block starting** (a default is taken; each can be changed in one place):
- The ruling on borrowed words and on the asset rule (`ARCHITECTURE.md` section 5). Default: our own words; own
  scripts only.
- The archetypes' final names. Default: the brief's three as working names in code and data, not on screen.
- Whether cooldowns carry over a death. Default: they reset; the ultimate's charge carries.

**What phase 2 needs from phase 1.** The ability base (creature abilities), the status effects (disruptor), the
registry of characters (throttling, squads), and the two-player check list as a habit.
