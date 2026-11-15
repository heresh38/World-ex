#pragma once

#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "SOProgression.generated.h"

/**
 * How a character grows, as data (Project Orion phase 4; Data/game_data.json "progression" ->
 * SO_IMPORT_ONLY=progression -> /Game/Data/DA_Progression). Two things kept apart: the character's LEVEL (from
 * experience, never lost) and its gear's POWER (each piece's own, raised by finding better or by upgrading). They
 * meet in one rule: a level sets how far gear can be upgraded.
 */
UCLASS(BlueprintType)
class SOCOMBAT_API USOProgressionTable : public UPrimaryDataAsset
{
	GENERATED_BODY()

public:
	// --- level: the experience the next level takes = XpBase + level x XpPerLevel ---
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Level")
	int32 XpBase = 600;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Level")
	int32 XpPerLevel = 250;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Level")
	int32 MaxLevel = 40;

	// --- power: how far an upgrade may take a piece = PowerCapBase + level x PowerCapPerLevel ---
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Power")
	int32 PowerCapBase = 20;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Power")
	int32 PowerCapPerLevel = 3;

	// --- upgrades: one raises a piece's power by UpgradeStep and costs
	// (Credits + power x CreditsPerPower) x the rarity's cost, and (Alloy + power x AlloyPerPower) x the same ---
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Upgrade")
	int32 UpgradeStep = 2;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Upgrade")
	float UpgradeCredits = 120.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Upgrade")
	float UpgradeCreditsPerPower = 6.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Upgrade")
	float UpgradeAlloy = 3.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Upgrade")
	float UpgradeAlloyPerPower = 0.1f;

	/** By rarity, lowest first: a rarer piece costs more to raise. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Upgrade")
	TArray<float> UpgradeRarityCost = { 1.0f, 1.2f, 1.5f, 2.0f, 2.6f };

	int32 XpForLevel(int32 Level) const { return XpBase + Level * XpPerLevel; }
	int32 PowerCap(int32 Level) const { return PowerCapBase + FMath::Max(Level, 1) * PowerCapPerLevel; }

	/** What raising a piece of this rarity from this power costs. */
	void UpgradeCost(int32 Rarity, int32 Power, int32& OutCredits, int32& OutAlloy) const;

	/** The imported table (/Game/Data/DA_Progression), or the class's own defaults if it was never imported. */
	static const USOProgressionTable& Get();
};
