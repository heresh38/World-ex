# Phase 0 report: audit and architecture

2026-11-12, at commit `9b3313e`. Format from `MASTER_BRIEF.md`, "Development reporting".

**What was inspected.** All eight C++ modules (about 31,500 lines), every `Build.cs` and `Target.cs`, the
`.uproject`, `Config/*.ini`, `Data/*.json`, the import and level-building scripts under `Content/Python`, the tool
folders, the README and the existing docs. Not inspected: the inside of binary assets; anything by playing.

**What was implemented.** Documents only:
- `docs/orion/MASTER_BRIEF.md`: the owner's brief, word for word.
- `docs/orion/AUDIT.md`: architecture report, existing and missing system inventories, compatibility report.
- `docs/orion/ARCHITECTURE.md`: module and folder structure, dependency map, how the systems fit, standards, where
  the brief and the standing rules differ, twelve decisions.
- `docs/orion/ROADMAP.md`: where each phase starts, risks, the first milestone, phase 1 as fifteen work items.

**Files created.** The four above and this report. **Files modified.** `CLAUDE.md` (a pointer to this folder).
No source, config, data or asset file was touched; no existing system was changed or removed.

**Systems integrated.** None (no code).

**Compilation.** Not run: nothing compiled changed. **Tests.** Not run for this phase; the last full run, at this
same commit, passed 74 of 74.

**Known bugs and defects found by reading** (none fixed in this phase; each is placed in a phase in the roadmap):
- Aim state is not sent to the server: a joined player on the sights gets hip-fire spread.
- Sounds and effects triggered on the server only (creature voices, boss slam / sweep / shield, blink, bolt impacts)
  never reach joined players; hit markers show for the host only.
- Any joined player can send the whole server to another area. No client call is validated.
- A joined player always starts with a fresh profile and loses it on travel.
- The Colossus's sweep ignores a variant's damage scale (`SOColossus.cpp:332`); conduits always take the 2x ambush
  bonus because they have no brain to become alert (`SOEnemy.cpp:476`); the Veilborn's cast cooldown is 2.4 in the
  header and 9.0 in the constructor.
- Enemies left alive from an earlier stage are no longer tracked or counted by the operation.
- A boss that fails to spawn completes its stage at once.
- Two area lists with different names (`SOMap.cpp:93`, `Data/areas.json`).
- The game cannot be packaged as configured (one map cooked, loose data files).
- README and migration plan are out of date.

**Remaining in phase 0.** Refreshing the README and `docs/unreal/MIGRATION_PLAN.md` (stale test counts and gaps).
Two rulings from the owner, neither blocking: borrowed words, and the asset rule (`ARCHITECTURE.md` section 5).

**Dependencies for phase 1.** None missing. Phase 1 needs: Blender work for four ability clips per body and the
kit's props; the listen-server check in the editor with two players; a first packaged build. It does not need the
dedicated server, an online service or any new engine plugin.

**Status of this phase.** Audit, architecture, standards, risks and roadmap: **Full**. Everything described in
those documents as phase 1 to 12 work: **Planned**.
