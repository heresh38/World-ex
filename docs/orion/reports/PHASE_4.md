# Phase 4 report: loot and progression (in progress)

Started 2026-11-13, straight after phase 3. Format from `MASTER_BRIEF.md`, "Development reporting". The brief
(part 6) asks for a deep equipment system: rarity, weapon loot, perks, unique guns, armour with stats and attributes,
inventory, upgrades and crafting, progression. Phase 4 started from guns that were **Full** and armour, economy and
progression that were **Prototype**: armour was worn and owned but its numbers changed nothing, credits and alloy
could not be spent, and a level only scaled credit rewards.

**This report covers the first part of the phase: armour that counts, the six attributes, levels and upgrades.**
The rest of the phase is listed under Remaining. Nothing here has been played.

## Where each item stands

| The brief asks for | Status | What exists |
|---|---|---|
| Rarity (6.1) | **Full** (unchanged) | Five tiers as data. The top tier still carries a borrowed name on screen; it waits for the owner's ruling (`ARCHITECTURE.md` section 5). |
| Weapon loot (6.2) | **Full** | As before (rolls, rarity, power, a uid per copy, one name per gun). New: a copy's power can be raised (below), which is its "upgrade state". |
| Perks (6.3) | **Full** for this first set | What a perk does is its numbers in the data (`"perks"`); the code reads the numbers and never asks a perk its name. The owner allowed new perks on 2026-11-13: there are now **25** (the nine from before and sixteen new). New, for any gun: Spoils (a kill puts a fifth of the magazine back), Second Skin (a kill starts the shield refilling), Hot Hands (a reload just after a kill is 40% faster), Cold Bore (the first shot after two quiet seconds hits 25% harder and flies true), Last Third (the bottom third of the magazine hits 15% harder), Point Shooter (half the spread from the hip), Light Feed, Heavy Barrel, Long Count (kills stack +4% eight times), Slide Feed (a slide fills the magazine). Kinetic only: Soft Nose (more to flesh, less to shields), Tracer Core (precision hits burn), Match Grade (no loss with distance), Baffled Muzzle (heard a third as far). Energy only: Overcharged Cell (+30% to shields). Living only: Clinging Acid (slows what it hits). A class's perks only roll on that class. Three of the new ones are data alone. Names are our own; **two of the old names (Overflow, Rampage) are also perk names in another looter and wait for the owner's word**. One fix on the way: a burst on a precision hit now counts a boss's weak point. |
| Unique guns (6.4) | **Planned** | |
| Armour stats (6.5) | **Full** | Every armour piece gives points in the six attributes: a budget from its armour rating, its rarity and its power; a little over half goes to the attribute its slot leans to (head: Focus, chest: Mending, rig and coat: Plating, hands: Impact, legs: Ordnance, feet: Stride) and the rest to two others that copy rolled. The same copy always gives the same. Rarity and power, which were stored and did nothing, now count. |
| Character attributes (6.5) | **Full** | Six, with names of our own: **Plating** (less of every damage taken: -25% at the most), **Mending** (the shield starts refilling sooner, x0.6 the wait, and refills faster, x1.6), **Stride** (speed, +8%), **Ordnance** and **Impact** (the grenade's and the melee's cooldown, x0.65), **Focus** (everything that charges the ultimate, x1.4). They are points from 0 to 100 that live in the attribute set, put there by one effect, so a perk or an ability can add to the same numbers later. What a point is worth is data. |
| Armour perks, set bonuses, cosmetics | **Planned** | The slots are the seven real clothing slots the bodies have, not the brief's five. |
| Upgrades (6.7) | **Full** | A gun or an armour piece can be raised two power at a time for credits and alloy (more for a rarer piece and the higher it already is). A raised gun hits harder; a raised armour piece gives more points. It is paid in full or not done. |
| Crafting, perk changes, resource conversion (6.7) | **Planned** | |
| Progression (6.8) | **Part** | The experience curve, the last level (40) and the gear cap are data. Level and power are kept apart and meet in one rule: **a level sets how far gear can be upgraded** (20 + 3 per level). Not built: ability, crafting and collection progression. |
| Inventory (6.6) | **Part** (unchanged) | Lock, dismantle, overflow dismantling. Not built: favourites, sorting and filters of the player's own, search, saved loadouts, a locker apart from the carried inventory, configurable capacities. |
| One way to pay | **Part** | `USOInventoryComponent::Spend` takes both currencies or neither. Adding things still goes through the existing separate functions. |
| The loot code in its own module (`SOLoot`) | **Planned** | |

## What was inspected
The attribute set and the damage gate, the shield's refill, the movement speed, cooldowns and the ultimate's charge,
the inventory component (armour, rating, power, currencies, level), the wardrobe data, how the body follows the
inventory's outfit, the loadout screen, the profile store's migration.

## What was implemented
- **`SOAttributes.h`**: the six attributes, their rules (`USOAttributeTable`, data `"attributes"`), and how an armour
  piece turns into points (`ArmourPoints`).
- **The attribute set** has the six as real attributes (owner-only replication); `USOGameplayEffect_Gear` carries
  what is worn; `ASOCombatCharacter::SetGearAttributes` swaps it when the outfit changes
  (`ASOCharacter::OutfitFromInventory`).
- **Where each one bites**: Plating in the damage gate beside the guard's scale; Mending in the shield's refill;
  Stride in `GetMoveScale` (so the same place a slow and haste already go through); Ordnance and Impact in
  `GetAbilityCooldownScale(Slot)` (a creature's is still the difficulty's and its boss phase's); Focus where the
  kit charges the ultimate.
- **`SOProgression.h`**: `USOProgressionTable` (data `"progression"`): experience per level, the last level, the
  gear cap, what an upgrade costs. `USOInventoryComponent::Spend / GetPowerCap / GetUpgrade / Upgrade /
  ServerUpgrade`.
- **Perks as data**: `FSOPerkInfo` carries what a perk does; `USOLootLibrary::PerkEffects` adds up a copy's perks;
  `FSOWeaponStats::Perks` is what the gun reads at runtime. `SO_IMPORT_ONLY=perks` rewrites only the perks of the
  loot tables (no gun is re-imported).
- **The loadout screen**: the six attributes under the top figures, what a piece gives (against the piece worn in
  its slot) in its details, and a button to raise the selected piece with what it will cost, or why it cannot.
- **Saves**: version 3 (a piece carries its own roll; one without takes it from its uid, so old saves need no
  change).

## Files created
`SOCombat/Public/SOAttributes.h`, `SOProgression.h` and their `.cpp`,
`ShatteredOrbit/Private/Tests/SOProgressionTests.cpp`, `Content/Data/DA_Attributes`, `DA_Progression`, this report.

## Files modified
SOCombat: `SOAttributeSet`, `SOCombatTypes.h`, `SOCombatModule.cpp`, `SOGameplayEffects`, `SOCombatCharacter`,
`SOAbilitySystemComponent.cpp`, `Abilities/SOGameplayAbility.cpp`, `SOInventoryComponent`, `SOWardrobe.h`,
`SOProfileStore.cpp`. SOAI: `SOEnemy`. SOCharacter: `SOCharacter.cpp`. SOUI: `SOInventoryWidget`. Tests:
`SOAbilityTests.cpp`, `SOBossTests.cpp`. `Data/game_data.json`, `Content/Python/import_assets.py`,
`ShatteredOrbit/Private/SOPlayerControllerDev.cpp` (the two-player check says what each side knows of the guest's
attributes).

## Compilation
The editor target builds clean. Not built: Shipping, a package.

## Tests
104 of 104 automation tests pass (97 from before the phase, 7 new: the last two are the new perks and worn-per-body). One older test (`Ability.VanguardKit`) assumed an unarmoured body and now expects the plating of what its player wears.

New, in `SOProgressionTests.cpp`: `Attributes.RulesAndArmourPoints` (a rule is 1 at nothing, its own scale at the
most and no more beyond; a piece's points add up to its budget, most of them where its slot leans, the same every
time, different for another copy, more for a better rarity or more power), `Attributes.GearChangesTheBody` (each
attribute alone at the most: a blow of 40 takes 30; speed x1.08; the grenade back in x0.65 of the time and the melee
not; the shield refilling before a bare body's would; the ultimate charging faster; all gone when the gear comes
off), `Attributes.WornArmourFeedsTheBody` (a player with an inventory takes a body: the body has exactly what the
worn pieces give; the coat off and on; a worn piece raised), `Progression.UpgradesAndLevels` (the price is the
table's and is paid in full; short of either currency nothing is taken or changed; it stops at the level's cap; a
level moves the cap; levels stop at the last; a raised gun hits harder, a raised armour piece gives more). In `SOLootTests.cpp`: `Loot.PerksAreData` (every perk's numbers in the tables are the data's and every perk does something; a copy with two perks has both effects; a perk made in the test out of data alone, which no code knows by name, doubles the magazine, halves the spread and adds its share of health on a kill to another perk's).

Two players (`bash tools/netcheck.sh`): the guest's own machine knows its six attributes and they match what the
server put on its body (plating 34, mending 19, stride 13, ordnance 18, impact 14, focus 7 for a new profile).

Pictures: `SOCaptureSeries 1 19` (the loadout screen with the attributes row and a piece's "GIVES").

## Fixed on the owner's report (2026-11-13)
- **Her chest was missing from the side with the jacket off.** Her crop top hides the body's chest (so no skin can
  poke through cloth), but its armholes were cut by a plane through the shoulder that was left to cut everything
  beyond it: the whole side of the chest went with it. The armhole is now the body's own border between chest and
  arm (`shirt.armhole`), a clean loop a few millimetres out along the arm, and the top covers everything it hides.
  Looked at in Blender from five sides with the hidden regions really hidden (`tools/blender/hero/repiece.py --look`,
  a new script that rebuilds one piece on a saved build and shows the body as the game does), then in the game
  (`SOCaptureSeries 1 24`, files `SO_f*`). His shirt without his coat and her top under her jacket were looked at
  the same way: whole. Only her top was re-imported (`SO_IMPORT_ONLY=player_pieces SO_PLAYER_PIECES=female:top:orion`).
- **What is worn is each body's own.** A helmet put on her was on him after the switch, and taking it off him took
  it off her: a piece both bodies can wear is owned once and had one "worn" flag. Each piece now remembers which
  bodies have it on (`FSOArmorInstance::WornBy`); a body puts on what IT had on when it was left, its wardrobe's
  defaults the first time. Saves are version 4. Test `Wardrobe.WornPerBody` is the owner's own sequence.

## Known bugs and limits
- **The baseline moved.** A new character's starting outfit gives about 35 Plating, 9 to 22 in the others, so every
  player now takes about 9% less damage and is 1% faster than before this phase. All the numbers are first guesses.
- Which two other attributes a copy gives depends on its uid, and there is one copy of each armour piece (a second
  drop raises the first), so there is nothing to chase yet: a re-roll (the `Roll` field is there for it) or
  several copies of a piece is a design decision for the owner.
- An upgrade bought while a gun is in the hands re-equips it.
- The upgrade button has not been clicked by anyone; its key is U (left shoulder on a pad).
- Attributes show on the loadout screen only; the HUD does not show them.
- Creatures have no attributes (all zero), by design.

## Remaining in phase 4
- More perks from `docs/design/PERK_IDEAS.md` (rounds that pass through a target, the charge-up and heat perks, the squad perks, each gun's signature); perk columns per archetype; armour perks; set bonuses.
- Inventory: favourites, sorting, filters, search, saved loadouts, a locker, capacities as data.
- Crafting and materials; unique guns with their own mechanics.
- The loot code in its own module; one transaction function for everything a player owns.
- The owner's play-through and ruling on the numbers.
