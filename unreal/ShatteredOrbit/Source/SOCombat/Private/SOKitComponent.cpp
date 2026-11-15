#include "SOKitComponent.h"

#include "Abilities/SOAbilitySet.h"
#include "Net/UnrealNetwork.h"
#include "SOCombatCharacter.h"
#include "SOCombatTypes.h"

USOKitComponent::USOKitComponent()
{
	PrimaryComponentTick.bCanEverTick = false;
	SetIsReplicatedByDefault(true);
}

void USOKitComponent::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
	Super::GetLifetimeReplicatedProps(OutLifetimeProps);
	DOREPLIFETIME(USOKitComponent, KitId);
}

USOAbilitySet* USOKitComponent::GetKit()
{
	if (LoadedKit != KitId)
	{
		// once per choice, at a possession: never in a tick
		LoadedKit = KitId;
		Kit = USOAbilitySet::Load(KitId);
		if (!Kit && !KitId.IsNone())
		{
			UE_LOG(LogSOCombat, Warning, TEXT("Kit '%s' has no asset (/Game/Abilities): run the import with SO_IMPORT_ONLY=kits"), *KitId.ToString());
		}
	}
	return Kit;
}

void USOKitComponent::SetKit(FName NewKit, ASOCombatCharacter* Body)
{
	if (!GetOwner() || !GetOwner()->HasAuthority() || NewKit == KitId)
	{
		return;
	}
	KitId = NewKit;
	SavedUltimate = 0.0f; // another kit's charge is not this one's
	if (Body && !Body->IsDead())
	{
		Body->AddUltimate(-Body->GetUltimate());
		Apply(Body);
	}
}

void USOKitComponent::Apply(ASOCombatCharacter* Body)
{
	if (!Body || !Body->HasAuthority())
	{
		return;
	}
	Body->GrantAbilitySet(GetKit());
	if (SavedUltimate > 0.0f)
	{
		Body->AddUltimate(SavedUltimate);
		SavedUltimate = 0.0f;
	}
}

void USOKitComponent::Remember(const ASOCombatCharacter* Body)
{
	if (Body && Body->HasAuthority())
	{
		SavedUltimate = Body->GetUltimate();
	}
}

void USOKitComponent::OnRep_Kit()
{
	GetKit();
}
