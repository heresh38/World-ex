#include "SOAttributeSet.h"

#include "GameplayEffectExtension.h"
#include "Net/UnrealNetwork.h"
#include "SOAbilitySystemComponent.h"
#include "SOCombatTypes.h"

USOAttributeSet::USOAttributeSet()
{
	InitHealth(100.0f);
	InitMaxHealth(100.0f);
	InitShield(0.0f);
	InitMaxShield(0.0f);
	InitIncomingDamage(0.0f);
}

void USOAttributeSet::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
	Super::GetLifetimeReplicatedProps(OutLifetimeProps);
	DOREPLIFETIME_CONDITION_NOTIFY(USOAttributeSet, Health, COND_None, REPNOTIFY_Always);
	DOREPLIFETIME_CONDITION_NOTIFY(USOAttributeSet, MaxHealth, COND_None, REPNOTIFY_Always);
	DOREPLIFETIME_CONDITION_NOTIFY(USOAttributeSet, Shield, COND_None, REPNOTIFY_Always);
	DOREPLIFETIME_CONDITION_NOTIFY(USOAttributeSet, MaxShield, COND_None, REPNOTIFY_Always);
}

void USOAttributeSet::PreAttributeChange(const FGameplayAttribute& Attribute, float& NewValue)
{
	Super::PreAttributeChange(Attribute, NewValue);
	if (Attribute == GetHealthAttribute())
	{
		NewValue = FMath::Clamp(NewValue, 0.0f, GetMaxHealth());
	}
	else if (Attribute == GetShieldAttribute())
	{
		NewValue = FMath::Clamp(NewValue, 0.0f, GetMaxShield());
	}
}

void USOAttributeSet::PostGameplayEffectExecute(const FGameplayEffectModCallbackData& Data)
{
	Super::PostGameplayEffectExecute(Data);

	if (Data.EvaluatedData.Attribute != GetIncomingDamageAttribute())
	{
		return;
	}
	const float Amount = GetIncomingDamage();
	SetIncomingDamage(0.0f);
	if (Amount <= 0.0f || GetHealth() <= 0.0f)
	{
		return;
	}

	// The shield takes it first, the rest comes off health.
	const float Absorbed = FMath::Min(GetShield(), Amount);
	SetShield(GetShield() - Absorbed);
	const float NewHealth = FMath::Max(0.0f, GetHealth() - (Amount - Absorbed));
	SetHealth(NewHealth);

	const FGameplayEffectContextHandle& Context = Data.EffectSpec.GetContext();
	AActor* Instigator = Context.GetOriginalInstigator();
	const bool bCrit = Data.EffectSpec.GetSetByCallerMagnitude(SOTags::SetByCaller_Crit, false, 0.0f) > 0.5f;
	if (USOAbilitySystemComponent* ASC = Cast<USOAbilitySystemComponent>(GetOwningAbilitySystemComponent()))
	{
		ASC->NotifyDamaged(Amount, Instigator, bCrit, NewHealth);
	}
}

void USOAttributeSet::OnRep_Health(const FGameplayAttributeData& OldValue)
{
	GAMEPLAYATTRIBUTE_REPNOTIFY(USOAttributeSet, Health, OldValue);
}

void USOAttributeSet::OnRep_MaxHealth(const FGameplayAttributeData& OldValue)
{
	GAMEPLAYATTRIBUTE_REPNOTIFY(USOAttributeSet, MaxHealth, OldValue);
}

void USOAttributeSet::OnRep_Shield(const FGameplayAttributeData& OldValue)
{
	GAMEPLAYATTRIBUTE_REPNOTIFY(USOAttributeSet, Shield, OldValue);
}

void USOAttributeSet::OnRep_MaxShield(const FGameplayAttributeData& OldValue)
{
	GAMEPLAYATTRIBUTE_REPNOTIFY(USOAttributeSet, MaxShield, OldValue);
}
