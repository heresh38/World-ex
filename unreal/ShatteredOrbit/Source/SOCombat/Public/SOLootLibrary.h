#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "SOLootTypes.h"
#include "SOLootLibrary.generated.h"

/** Options for RollWeapon (state.js rollWeapon). Unset values roll. */
USTRUCT(BlueprintType)
struct SOCOMBAT_API FSORollOptions
{
	GENERATED_BODY()

	/** Fixed archetype (None = any, weighted). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Loot")
	FName Archetype;

	/** Only this slot (-1 = any). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Loot")
	int32 Slot = -1;

	/** Fixed rarity (-1 = roll with RarityBonus). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Loot")
	int32 Rarity = -1;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Loot")
	float RarityBonus = 0.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Loot")
	FString Source;
};

/**
 * Loot rules, ported from the browser build's state.js / data.js / combat.js / operation.js:
 * rarity rolls, weighted archetypes, perks, stat rolls, names, the stats a copy fires with, enemy drops and the
 * VANTHOS reliquary reward pool. Every roll takes an FRandomStream so tests and replays are deterministic.
 */
UCLASS()
class SOCOMBAT_API USOLootLibrary : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/** /Game/Data/DA_LootTables (null until import_assets.py ran). */
	static USOLootTables* GetTables();

	static constexpr int32 VaultCap = 200;

	/** state.js rollRarity: Common 38 %, Uncommon 30 %, Rare 22 %, Legendary 8.5 %, Exotic 1.5 % (bonus shifts it up). */
	static int32 RollRarity(FRandomStream& Rng, float Bonus = 0.0f);

	/** Any archetype (or one of a slot), weighted by LootWeight. */
	static FName RandomArchetype(FRandomStream& Rng, int32 Slot = -1);

	/** state.js makeWeapon: rarity perks (no repeats), stat rolls, a name; the sight is the archetype's default. */
	static FSOWeaponInstance MakeWeapon(FName Archetype, int32 Rarity, int32 Power, FRandomStream& Rng);

	/** state.js rollWeapon: archetype, rarity, perks, stat rolls and a random compatible sight. */
	static FSOWeaponInstance RollWeapon(int32 Power, const FSORollOptions& Options, FRandomStream& Rng);

	/** data.js weaponName. */
	static FString WeaponName(FName Archetype, int32 Rarity, FRandomStream& Rng);

	/** state.js weaponStats (+ the mounted sight's zoom and the recoil perk). */
	UFUNCTION(BlueprintPure, Category = "SO|Loot")
	static FSOWeaponStats ComputeStats(const FSOWeaponInstance& Weapon);

	/** The same with the archetype's data already at hand. */
	static FSOWeaponStats ComputeStatsFor(const USOWeaponData* Archetype, const FSOWeaponInstance& Weapon);

	/** state.js rollQuality: how good the stat rolls are, 0..100. */
	UFUNCTION(BlueprintPure, Category = "SO|Loot")
	static int32 RollQuality(const FSOWeaponInstance& Weapon);

	/** Alloy for breaking a copy down (2 + 3 per rarity step). */
	UFUNCTION(BlueprintPure, Category = "SO|Loot")
	static int32 DismantleAlloy(const FSOWeaponInstance& Weapon) { return 2 + Weapon.Rarity * 3; }

	/** combat.js drop: enemy level -> a loot core of this rarity (-1 = no core). 15 % chance (brutes roll higher). */
	static int32 RollKillDrop(int32 Level, bool bBrute, FRandomStream& Rng, float Chance = 0.15f);

	/** operation.js rollRewards: 2-3 weapons, rarity Uncommon 22 / Rare 40 / Legendary 29 / Exotic 9, power around
	 *  the player's (+2 for legendary and up), any archetype. */
	static TArray<FSOWeaponInstance> RollReliquary(int32 PlayerPower, FRandomStream& Rng, const FString& Source = TEXT("Spire reliquary"));

	/** A fresh unique id. */
	static FString NewUid(FRandomStream& Rng);
};
