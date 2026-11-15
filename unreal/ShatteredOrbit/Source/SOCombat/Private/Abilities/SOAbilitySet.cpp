#include "Abilities/SOAbilitySet.h"

#include "Abilities/SOGameplayAbility.h"

const FSOAbilityGrant* USOAbilitySet::Find(ESOAbilitySlot Slot) const
{
	return Abilities.FindByPredicate([Slot](const FSOAbilityGrant& G) { return G.Slot == Slot; });
}

USOAbilitySet* USOAbilitySet::Load(FName KitId)
{
	if (KitId.IsNone())
	{
		return nullptr;
	}
	FString Name = KitId.ToString();
	Name[0] = FChar::ToUpper(Name[0]);
	const FString Path = FString::Printf(TEXT("/Game/Abilities/DA_Kit_%s.DA_Kit_%s"), *Name, *Name);
	return Cast<USOAbilitySet>(FSoftObjectPath(Path).TryLoad());
}
