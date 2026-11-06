#include "SOAbilitySystemComponent.h"

#include "Engine/World.h"
#include "SOAttributeSet.h"
#include "SOCombatCharacter.h"

USOAbilitySystemComponent::USOAbilitySystemComponent()
{
	PrimaryComponentTick.bCanEverTick = true;
	SetIsReplicatedByDefault(true);
	SetReplicationMode(EGameplayEffectReplicationMode::Mixed);
}

void USOAbilitySystemComponent::NotifyDamaged(float Amount, AActor* Instigator, bool bCrit, float NewHealth)
{
	LastDamageTime = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.0f;
	const bool bKilled = NewHealth <= 0.0f;
	OnDamaged.Broadcast(Amount, Instigator, bCrit, bKilled);
	if (bKilled)
	{
		if (ASOCombatCharacter* Character = Cast<ASOCombatCharacter>(GetAvatarActor()))
		{
			Character->Die(Instigator);
		}
	}
}

void USOAbilitySystemComponent::UpdateShieldRegen(float DeltaTime)
{
	if (!IsOwnerActorAuthoritative() || !GetWorld())
	{
		return;
	}
	const USOAttributeSet* Set = GetSet<USOAttributeSet>();
	if (!Set || Set->GetHealth() <= 0.0f || Set->GetShield() >= Set->GetMaxShield())
	{
		return;
	}
	if (GetWorld()->GetTimeSeconds() - LastDamageTime >= ShieldRegenDelay)
	{
		const float NewShield = FMath::Min(Set->GetMaxShield(), Set->GetShield() + ShieldRegenRate * DeltaTime);
		SetNumericAttributeBase(USOAttributeSet::GetShieldAttribute(), NewShield);
	}
}
