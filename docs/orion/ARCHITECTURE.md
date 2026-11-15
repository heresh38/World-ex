# Project Orion: architecture, standards and decisions

Phase 0 of `MASTER_BRIEF.md`. Written 2026-11-12 from the findings in `AUDIT.md`. This is the plan the later
phases build on; nothing in it is built unless it says "exists". Change it by adding a dated decision at the end,
not by quietly editing an old one.

## The rule above all the others
The brief says: never rewrite what works, never make a second system for a job that has one, keep the game playable.
So the target architecture is **the existing one, extended**. The project keeps its `SO` class prefix, its module
names and its file layout; the brief's `ProjectOrion...` class names are read as roles, and `AUDIT.md` section 5 maps
each one to the class that has or will have that role.

---

## 1. Module structure

### Today (kept as it is)
```
SOCore        log, settings, areas / travel / arrival
  SOWorld     city builder, weather, time of day, map
  SOCombat    abilities + attributes, weapons, projectiles, effects, sound, loot, inventory, wardrobe data
    SOCharacter   the player
      SOAI        creatures and their brain
        SOOperation   missions
          SOUI        HUD and screens
            ShatteredOrbit   game mode, controller, player state, tests
```
A module may include only what is above it in this list. `SOUI` must declare `SOAI` (it uses it today without).

### Additions, each made in the phase that needs it (not before)

| New module | Made in | What moves or goes in | Why not leave it where it is |
|---|---|---|---|
| `SODev` (not built for Shipping) | Phase 1 | `SOCaptureSeries`, `SOBenchmark`, census and tour commands, cheat commands, item granting | 1,400 lines of screenshot script sit in the player controller and would ship. |
| `SOLoot` | start of Phase 4 | From `SOCombat`: loot types and library, inventory, wardrobe data, loot actors, save; new: armour stats, perks as data, crafting, vendors' stock | `SOCombat` already holds eight jobs in 8,000 lines; phase 4 would double it. Needs class redirects for the data assets (`[CoreRedirects]`), which is routine. |
| `SOOnline` | Phase 10 | Sessions, squad (party), matchmaking, the profile service's client | Keeps every online SDK out of gameplay modules. |
| `SOWorldGen` | Phase 6 or 11, only if an open biome is built | Engine PCG graphs' C++ nodes, streaming set-up | Meridian does not need it. |

No new module for abilities: the framework belongs beside the ability system component it extends (`SOCombat`), and
the player's kits beside the player (`SOCharacter`). Creatures use the same framework from `SOAI`.

### Folders
- Source: `Source/<Module>/Public|Private`, one class per file pair, a sub-folder once a job has more than about
  five files (`SOCombat/Private/Abilities`, `SOAI/Private/Species`, `SOCharacter/Private/Kits`).
- Content: by kind, then by owner (`/Game/Characters/PlayerMale`, `/Game/Weapons/<Gun>`,
  `/Game/Environments/<Area>`); anything two areas use goes in `/Game/Shared`. New: `/Game/Abilities/<Kit>`,
  `/Game/UI`, `/Game/Data`.
- Data: `unreal/ShatteredOrbit/Data/*.json` is the source for numbers and text; the import turns it into data assets.
- Tools: `tools/blender` (models, textures), `tools/audio`, `tools/operation`, `tools/city`.
- Docs: `docs/orion` (this folder: brief, audit, architecture, roadmap, a report per phase), `docs/story`,
  `docs/operation`, `docs/design`.

---

## 2. Dependency map

What each system needs before it can be built. An arrow reads "needs".

```
Abilities (P1) ──► ability system on the combat character (exists)
                ├► status effects as GameplayEffects (P1)
                ├► new input actions (P1)
                └► new body clips: throw, strike, cast (Blender, P1)

Classes / kits (P1) ──► abilities
Enemy abilities, new roster (P2) ──► abilities, status effects
Difficulty (P2) ──► species variants (exist) + a difficulty table
Encounter director (P2) ──► wave logic split out of ASOOperation

Boss framework (P3) ──► enemy abilities with telegraphs (P2), weak points by bone (needs physics assets, exist)
First new boss (P3) ──► boss framework, a creature model (Blender), an arena

Armour stats, attributes (P4) ──► attribute set extended, SOLoot split
Perks as data (P4) ──► status effects (P1)
Crafting, upgrades, vendors' stock (P4) ──► currencies (exist), a transaction layer, profile store interface (P1)
Exotic guns (P4) ──► perks as data, abilities (for charged / marked shots)

Extraction, failure, revive (P5) ──► operation stage kinds as classes, downed state on the combat character
Mission subsystem (P5) ──► areas.json as the list of activities
Second operation (P5/P11) ──► level builder script freed of Meridian's names

City life (P7) ──► interactables beyond the chest, dialogue data, vendors' stock (P4)
Menus, settings (P8) ──► settings fields (exist), CommonUI activatable base (stub exists)

Online (P10) ──► everything server-authoritative already, profile store interface (P1), validated RPCs (P1),
                 a packaged build (P1 smoke test), an engine built from source for the dedicated server
Steam (P12) ──► SOOnline, packaged build
```

Two dependencies run against the brief's phase order and are pulled forward for that reason (see `ROADMAP.md`):
the **packaged-build smoke test** and the **profile store interface**.

---

## 3. How the main systems fit together

### Combat core (exists; the rule for everything new)
- One damage entry: `USOCombatStatics::ApplyDamage`. New sources (abilities, hazards, vehicles) call it; nothing
  else lowers health. Healing, shield regeneration and scripted kills move onto GameplayEffects in phase 1 so that
  "prevent death", "over-shield" and "heal over time" have one place to hook.
- One status system: a small set of GameplayEffects with tags (`Status.Burn`, `Status.Slow`, `Status.Stagger`,
  `Status.Marked`, ...). The projectile subsystem's private burn list becomes a client of it.
- Gameplay tags are the shared vocabulary: `State.*` (Dead, Downed, Aiming, Sprinting, Traversing, Reloading),
  `Ability.*`, `Cooldown.*`, `Status.*`, `Damage.*` (Kinetic, Light, Living, and elements when they are designed),
  `Event.*`. Declared natively in one file per module.

### Abilities (phase 1)
- `USOGameplayAbility : UGameplayAbility` in `SOCombat/Abilities`: activation rules by tag, cooldown as a
  GameplayEffect with a set-by-caller duration, charges, optional cost, one hook each for the body's clip, the
  sound and the effect, locally predicted for players and server-only for creatures.
- `USOAbilitySet` (data asset): slot (grenade, melee, class, movement, ultimate) → ability class + its numbers. A kit
  (archetype) is one ability set plus passive effects. Numbers come from `Data/game_data.json` ("abilities", "kits").
- The ability system component stays on the pawn (decision 3). What must survive a respawn (ultimate charge, the
  chosen kit) is kept by a component on the player state and given back on possess.
- Creatures use the same class: the Veilborn's bolt and the Bulwark's slam become abilities, which gives bosses
  their attack sets and telegraphs for free in phase 3.

### Creatures (exists; extended in phases 2 and 3)
- One class per species, found by `USOSpeciesLibrary`, spawned only through `Spawn`. Levels add data, never code.
- The brain stays C++ (decision 6). As the roster grows it is cut into parts along lines that already exist in the
  code: senses, cover, squad, movement recovery. A squad becomes an object (`USOSquad`) instead of loops over every
  creature.
- Difficulty is a table of the tunables that already exist (awareness fill rate, alert delay, aim ramp, aim error,
  burst length, flanker share, push delays, ability use), never a health multiplier alone.
- A boss is an `ASOEnemy` with three reusable parts: a phase table (by health), weak points (by bone), and an
  attack set (abilities with a wind-up, a sound cue and a ground marker). The operation's boss stage is the
  encounter; `GrantReward` is the reward. Built in phase 3 as one component and one data asset
  (`USOBossComponent`, `USOBossData`): a species names its table, or a level's variant does, so a level makes a boss
  of any species with data alone.

### Items and progression (exists for guns; extended in phase 4)
- Definition (data asset) + instance (struct with a uid) stays the model. Armour gets what guns have: rolls, perks,
  power that counts.
- Character attributes live in the attribute set and are fed by worn armour through GameplayEffects, so abilities,
  perks and armour all change the same numbers the same way.
- Every change to what a player owns goes through one transaction function on the server (add, remove, spend,
  craft, transfer) that either completes or does nothing, and that the profile store records.

### Missions (exists as the operation; extended in phase 5)
- `ASOOperation` stays the runner. Stage kinds become small classes (`USOObjective`) so that collect, activate,
  destroy, defend, extract and the rest are added without touching the runner.
- The plan stays one generated file per activity; at runtime it is read from a data asset, not from disk.
- `USOMissionSubsystem` (game instance) lists activities from `areas.json`, launches them through
  `USOAreaSubsystem::Travel`, and keeps what a squad needs between levels.

### Saving and online (prototype today; boundary in phase 1, service in phase 10)
- `ISOProfileStore` in `SOCore`: load profile, commit transaction, save settings. The first implementation is the
  current local file (made asynchronous, versioned, written to a temporary file and renamed). The online one comes
  later behind the same interface. Gameplay never calls `SaveGameToSlot` directly again.
- Server authority is already the design. Phase 1 adds validation to every client call and stops a guest moving the
  server.

### Interface
- The canvas HUD stays until phase 8 and gets its data by events, not by scanning the world each frame.
- Screens are C++ widgets on the game's own plate material; menus use CommonUI's activatable stack (the stub
  `USOActivatableWidget` becomes the base).

### Effects and sound
- `USOFxSubsystem` and `USOSoundLibrary` stay the only calls gameplay makes (decision 7). Both gain a "tell
  everyone" path so that what the server triggers is seen and heard by joined players.

---

## 4. Standards

**Naming.** Classes `ASO*`, `USO*`, `FSO*`, `ESO*`, `ISO*`. Assets `SM_`, `SK_`, `M_`, `MI_`, `T_`, `DA_`, `S_`,
`IA_`, `IMC_`, `L_`. Tests `ShatteredOrbit.<Area>.<WhatIsTrue>`. Material and node names that scripts read are an
API (see `CLAUDE.md`). No name, term or text from another game, in code, data or on screen.

**Code.**
- C++ for gameplay, networking and anything per-frame. Blueprints only as thin children for tuning; no logic in
  graphs (the project is built and tested headless).
- One job per class. A new class over about 800 lines is cut before it is merged; the four large existing files
  are cut when their phase touches them, not before.
- Numbers and text live in data (`Data/*.json` → data assets), never in a constructor, once more than one thing
  shares them.
- No synchronous asset load, world-wide actor scan or line trace per actor inside a tick. Keep a registry.
- Never keep a bare pointer to a loaded asset across a timer or a level change.
- Log to `LogShatteredOrbit`.
- Comments say why, not what.

**Networking.**
- The server decides damage, loot, currency, ownership, rewards, mission state. The client asks.
- Every client-to-server call is validated (range, ownership, rate, state) and safe to receive twice.
- A replicated property that drives anything visible has a rep-notify. Private data replicates to its owner only.
- Anything a player must see or hear is triggered on every machine (a multicast or a replicated state), never by a
  local call on the server.
- Every new system gets a two-player check before it is called done.

**Data and saves.** Every saved structure carries a version and a migration from the one before. Ids of items,
abilities, perks and species never change once shipped in a save.

**Assets.** Made in Blender by our own scripts; sources kept; real collision (`_solid`), never a Nanite mesh's own;
no placeholder shown as finished; check silhouettes; look at a render before importing.

**Testing and reporting.** A system is done when it compiles, its automation tests pass, it has been played, and
its report says so in those words. Each phase ends with a report in `docs/orion/reports/PHASE_<n>.md` in the brief's
format (inspected, implemented, files, integration, build result, tests, known bugs, remaining, next dependencies)
using the status words Full / Part / Prototype / Planned / Blocked. A plan is never reported as work.

---

## 5. Where the brief and the standing rules differ

`CLAUDE.md`'s hard rules are the owner's earlier, stricter word. Until the owner says otherwise the stricter rule
holds. These are the differences found; the first two need the owner's ruling, the rest are settled as shown.

| # | The brief | The standing rule | What is done until ruled |
|---|---|---|---|
| 1 | Uses terms that belong to one other game: the six attributes "Resilience, Recovery, Mobility, Discipline, Strength, Intelligence"; "Strikes", "Raids", "Fireteam", "Vault", "Exotic", "Class item", "Public events" | "No names, terms or text from other games" (and the brief's own 1.2) | They are read as roles. Proposed names of our own are listed below; nothing on screen uses the borrowed words. `Exotic` is already our fifth rarity's name and stays until ruled. |
| 2 | "AI-generated models may be used as starting points" | "Every 3D model and texture is made in Blender by our own scripts. Never add third-party models" | The standing rule holds: nothing generated or bought is imported. |
| 3 | Suggested class names `AProjectOrion...` | Do not duplicate or rewrite | Mapped to `SO` classes (`AUDIT.md` section 5). |
| 4 | "Use Niagara" | Effects are our own subsystem, because the project is built headless | Kept behind one interface; Niagara is evaluated in phase 8 (decision 7). |
| 5 | "Behavior Trees, State Trees, EQS where appropriate" | The brain is tested C++ | Kept (decision 6). |
| 6 | NPCs and vendors in the city, playable vehicles | "Keep people and vehicles out of Nexus Prime until asked" | The brief is the asking, for phases 7 and 9. Nothing before then. |
| 7 | Blueprints for designer-facing work | Everything is C++ and scripts | Data assets and json are the designer-facing layer. |
| 8 | Engine PCG and World Partition | Levels are built by our Blender and Python scripts | Meridian stays as it is; streaming only for an open biome (decision 10). |

**Proposed names (ours; every one can be changed in one place):**

| Role in the brief | Proposed | Note |
|---|---|---|
| Fireteam | Squad | Already the word in the code and the story. |
| Strike | Operation (a short one: Sortie) | The game's activity is already "Operation". |
| Raid | Siege | |
| Dungeon | Descent | |
| Public event | Flashpoint | |
| Bounties | Contracts | The brief offers this word itself. |
| Vault | Locker | The chest in the world is already "reliquary". |
| Class item | Mark | The archetype's own worn piece. |
| Resilience / Recovery / Mobility | Plating / Mending / Stride | Damage taken, recovery speed, movement. |
| Discipline / Strength / Intelligence | Ordnance / Impact / Focus | Grenade, melee and ultimate recharge. |

---

## 6. Decisions

1. **Keep the `SO` prefix, module names and existing classes** (2026-11-12). The brief forbids duplicates and
   needless rewrites; renaming 31,000 lines and every asset reference buys nothing a player sees.
2. **The engine's Gameplay Ability System is the ability framework.** It already carries health and damage, it
   replicates and predicts, and a second system would break the brief's "no duplicate" rule.
3. **The ability system component stays on the pawn for now.** 74 tests and every creature depend on it there.
   What must outlive a body is kept on the player state. Revisit if reconnection (phase 10) needs more.
4. **One damage path, one status system.** `ApplyDamage` stays the only way health goes down; healing,
   regeneration, scripted kills and burn move onto GameplayEffects in phase 1.
5. **Data is authored as json, shipped as data assets.** No gameplay code reads a loose file at runtime after
   phase 1 (packaging depends on it).
6. **The enemy brain stays hand-written C++** and is cut into parts as the roster grows. It works, it is tested,
   and a tree rewrite would cost weeks to arrive where it is. The unused StateTree plugins are switched off.
7. **Gameplay calls our effects and sound subsystems only.** What draws behind them (our cards today, Niagara if it
   proves better and can be authored by script) is a phase 8 question that touches no gameplay code.
8. **Server authority with a profile store behind an interface.** Local file now, service later; no gameplay code
   knows which.
9. **Developer tools live in a module that Shipping does not build.**
10. **Meridian Fall stays a single scripted level.** World Partition, HLOD and engine PCG are for a first open
    biome, if and when one is built.
11. **The asset rule stays as strict as it is** (own Blender scripts only) unless the owner lifts it.
12. **`SOLoot` is split from `SOCombat` at the start of phase 4**, with redirects, in one commit that changes no
    behaviour and is proven by the full test run.
13. **The damage gate is the attribute set** (2026-11-12, phase 1). The rules that were in
    `USOCombatStatics::ApplyDamage` (the dead, the immune, the victim's scaling, friendly fire) moved into
    `USOAttributeSet::TakeDamage`, so a periodic effect or an ability's own effect cannot go round them.
14. **`Die()` stays the one way to die**, called by the gate at zero health and by scripts that remove something
    (a boss's adds, its conduits). Making a scripted kill an effect would add a path, not remove one.
15. **Charges recharge each on its own clock; a new body's cooldowns start over; the ultimate's charge carries.**
    One cooldown effect per spent charge needs no counter to replicate. Revisit the reset on death when revives
    exist (phase 5): a downed player who is picked up keeps their body and so their cooldowns.
16. **Runtime data is staged with the package, read through `SOData`.** Decision 5's end state (data assets) is
    kept for the files that are small and structured (areas, an operation's plan); the city's 22 MB of plan and
    instances stay files.
17. **The automation tests are editor-only.** They build worlds by hand and call editor-only functions; the
    packaged game is checked by running it (`SOAreaTour`, the capture sets).
