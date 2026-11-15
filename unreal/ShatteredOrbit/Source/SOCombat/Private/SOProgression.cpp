#include "SOProgression.h"

void USOProgressionTable::UpgradeCost(int32 Rarity, int32 Power, int32& OutCredits, int32& OutAlloy) const
{
	const float ByRarity = UpgradeRarityCost.Num() > 0 ? UpgradeRarityCost[FMath::Clamp(Rarity, 0, UpgradeRarityCost.Num() - 1)] : 1.0f;
	OutCredits = FMath::Max(1, FMath::RoundToInt((UpgradeCredits + FMath::Max(Power, 0) * UpgradeCreditsPerPower) * ByRarity));
	OutAlloy = FMath::Max(1, FMath::RoundToInt((UpgradeAlloy + FMath::Max(Power, 0) * UpgradeAlloyPerPower) * ByRarity));
}

const USOProgressionTable& USOProgressionTable::Get()
{
	static TWeakObjectPtr<const USOProgressionTable> Loaded;
	if (!Loaded.IsValid())
	{
		// (kept for good: a small table read on every reward)
		if (USOProgressionTable* Table = Cast<USOProgressionTable>(FSoftObjectPath(TEXT("/Game/Data/DA_Progression.DA_Progression")).TryLoad()))
		{
			Table->AddToRoot();
			Loaded = Table;
		}
	}
	return Loaded.IsValid() ? *Loaded : *GetDefault<USOProgressionTable>();
}
