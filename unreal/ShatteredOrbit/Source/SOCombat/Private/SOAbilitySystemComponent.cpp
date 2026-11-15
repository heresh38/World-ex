#include "SOAbilitySystemComponent.h"

#include "Engine/World.h"
#include "SOAttributeSet.h"
#include "SOAttributes.h"
#include "SOCombatCharacter.h"
#include "SOCombatTypes.h"
#include "SOGameplayEffects.h"

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

void USOAbilitySystemComponent::NoteUnderFire()
{
	LastDamageTime = GetWorld() ? GetWorld()->GetTimeSeconds() : LastDamageTime;
}

void USOAbilitySystemComponent::UpdateShieldRegen(float DeltaTime)
{
	if (!IsOwnerActorAuthoritative() || !GetWorld())
	{
		return;
	}
	const USOAttributeSet* Set = GetSet<USOAttributeSet>();
	// (mending: the wait is shorter and the refill faster)
	const USOAttributeTable& Rules = USOAttributeTable::Get();
	const float Mending = Set ? Set->GetMending() : 0.0f;
	const bool bRefill = Set && Set->GetHealth() > 0.0f && Set->GetShield() < Set->GetMaxShield()
		&& GetWorld()->GetTimeSeconds() - LastDamageTime >= ShieldRegenDelay * Rules.Scale(ESOAttribute::Mending, Mending);
	if (bRefill && !ShieldRegen.IsValid())
	{
		const FGameplayEffectSpecHandle Spec = MakeOutgoingSpec(USOGameplayEffect_ShieldRegen::StaticClass(), 1.0f, MakeEffectContext());
		if (Spec.IsValid())
		{
			Spec.Data->SetSetByCallerMagnitude(SOTags::SetByCaller_Magnitude, ShieldRegenRate * Rules.Scale2(ESOAttribute::Mending, Mending) * USOGameplayEffect_ShieldRegen::TickPeriod);
			ShieldRegen = ApplyGameplayEffectSpecToSelf(*Spec.Data);
		}
	}
	else if (!bRefill && ShieldRegen.IsValid())
	{
		RemoveActiveGameplayEffect(ShieldRegen);
		ShieldRegen.Invalidate();
	}
}

void USOAbilitySystemComponent::SetState(const FGameplayTag& Tag, bool bOn)
{
	if (HasMatchingGameplayTag(Tag) != bOn)
	{
		SetLooseGameplayTagCount(Tag, bOn ? 1 : 0);
	}
}
