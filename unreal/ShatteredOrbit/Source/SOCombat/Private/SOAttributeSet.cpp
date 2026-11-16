#include "SOAttributeSet.h"

#include "GameplayEffectExtension.h"
#include "Net/UnrealNetwork.h"
#include "SOAbilitySystemComponent.h"
#include "SOAttributes.h"
#include "SOCombatCharacter.h"
#include "SOCombatStatics.h"
#include "SOCombatTypes.h"

USOAttributeSet::USOAttributeSet()
{
	InitHealth(100.0f);
	InitMaxHealth(100.0f);
	InitShield(0.0f);
	InitMaxShield(0.0f);
	InitUltimate(0.0f);
	InitMaxUltimate(100.0f);
	InitMoveScale(1.0f);
	InitDamageTaken(1.0f);
	InitPlating(0.0f);
	InitMending(0.0f);
	InitStride(0.0f);
	InitOrdnance(0.0f);
	InitImpact(0.0f);
	InitFocus(0.0f);
	InitIncomingDamage(0.0f);
}

void USOAttributeSet::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
	Super::GetLifetimeReplicatedProps(OutLifetimeProps);
	DOREPLIFETIME_CONDITION_NOTIFY(USOAttributeSet, Health, COND_None, REPNOTIFY_Always);
	DOREPLIFETIME_CONDITION_NOTIFY(USOAttributeSet, MaxHealth, COND_None, REPNOTIFY_Always);
	DOREPLIFETIME_CONDITION_NOTIFY(USOAttributeSet, Shield, COND_None, REPNOTIFY_Always);
	DOREPLIFETIME_CONDITION_NOTIFY(USOAttributeSet, MaxShield, COND_None, REPNOTIFY_Always);
	DOREPLIFETIME_CONDITION_NOTIFY(USOAttributeSet, Ultimate, COND_None, REPNOTIFY_Always);
	DOREPLIFETIME_CONDITION_NOTIFY(USOAttributeSet, MaxUltimate, COND_None, REPNOTIFY_Always);
	DOREPLIFETIME_CONDITION_NOTIFY(USOAttributeSet, MoveScale, COND_None, REPNOTIFY_Always);
	DOREPLIFETIME_CONDITION_NOTIFY(USOAttributeSet, DamageTaken, COND_None, REPNOTIFY_Always);
	DOREPLIFETIME_CONDITION_NOTIFY(USOAttributeSet, Plating, COND_OwnerOnly, REPNOTIFY_Always);
	DOREPLIFETIME_CONDITION_NOTIFY(USOAttributeSet, Mending, COND_OwnerOnly, REPNOTIFY_Always);
	DOREPLIFETIME_CONDITION_NOTIFY(USOAttributeSet, Stride, COND_OwnerOnly, REPNOTIFY_Always);
	DOREPLIFETIME_CONDITION_NOTIFY(USOAttributeSet, Ordnance, COND_OwnerOnly, REPNOTIFY_Always);
	DOREPLIFETIME_CONDITION_NOTIFY(USOAttributeSet, Impact, COND_OwnerOnly, REPNOTIFY_Always);
	DOREPLIFETIME_CONDITION_NOTIFY(USOAttributeSet, Focus, COND_OwnerOnly, REPNOTIFY_Always);
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
	else if (Attribute == GetUltimateAttribute())
	{
		NewValue = FMath::Clamp(NewValue, 0.0f, GetMaxUltimate());
	}
	else if (Attribute == GetMoveScaleAttribute())
	{
		NewValue = FMath::Clamp(NewValue, 0.05f, 3.0f);
	}
	else if (Attribute == GetDamageTakenAttribute())
	{
		NewValue = FMath::Clamp(NewValue, 0.05f, 4.0f);
	}
}

float USOAttributeSet::TakeLastDamage() const
{
	const float Amount = LastDamage;
	LastDamage = 0.0f;
	return Amount;
}

void USOAttributeSet::PostGameplayEffectExecute(const FGameplayEffectModCallbackData& Data)
{
	Super::PostGameplayEffectExecute(Data);

	const FGameplayAttribute& Attribute = Data.EvaluatedData.Attribute;
	if (Attribute == GetIncomingDamageAttribute())
	{
		TakeDamage(Data);
	}
	// an effect that adds to a value's base (a heal, the shield refilling, the ultimate charging) stops at its limits
	else if (Attribute == GetHealthAttribute())
	{
		SetHealth(FMath::Clamp(GetHealth(), 0.0f, GetMaxHealth()));
	}
	else if (Attribute == GetShieldAttribute())
	{
		SetShield(FMath::Clamp(GetShield(), 0.0f, GetMaxShield()));
	}
	else if (Attribute == GetUltimateAttribute())
	{
		SetUltimate(FMath::Clamp(GetUltimate(), 0.0f, GetMaxUltimate()));
	}
}

void USOAttributeSet::TakeDamage(const FGameplayEffectModCallbackData& Data)
{
	float Amount = GetIncomingDamage();
	SetIncomingDamage(0.0f);
	LastDamage = 0.0f;
	if (Amount <= 0.0f || GetHealth() <= 0.0f)
	{
		return;
	}
	USOAbilitySystemComponent* ASC = Cast<USOAbilitySystemComponent>(GetOwningAbilitySystemComponent());
	ASOCombatCharacter* Victim = ASC ? Cast<ASOCombatCharacter>(ASC->GetAvatarActor()) : nullptr;
	AActor* Source = Data.EffectSpec.GetContext().GetOriginalInstigator();
	const bool bCrit = Data.EffectSpec.GetSetByCallerMagnitude(SOTags::SetByCaller_Crit, false, 0.0f) > 0.5f;

	// the gate every source of damage passes
	if (Victim)
	{
		if (Victim->IsDead() || Victim->IsImmune() || Victim->IsDisplayOnly())
		{
			return;
		}
		// (its own scaling, then what it is under: a guard; then what it wears: plating)
		Amount = Victim->ScaleIncomingDamage(Amount, Source, bCrit) * GetDamageTaken() * USOAttributeTable::Get().Scale(ESOAttribute::Plating, GetPlating());
		if (Amount <= 0.0f)
		{
			return;
		}
	}
	if (Source && Victim && Source != Victim && !USOCombatStatics::AreHostile(Source, Victim))
	{
		return;
	}

	// The shield takes it first, the rest comes off health.
	const float Absorbed = FMath::Min(GetShield(), Amount);
	SetShield(GetShield() - Absorbed);
	const float NewHealth = FMath::Max(0.0f, GetHealth() - (Amount - Absorbed));
	SetHealth(NewHealth);
	LastDamage = Amount;

	if (ASC)
	{
		ASC->NotifyDamaged(Amount, Source, bCrit, NewHealth);
	}
	if (Victim && Source && Source != Victim)
	{
		Victim->OnTookDamage(Source, Amount, bCrit);
		USOCombatStatics::OnCharacterHit().Broadcast(Victim, Source, Amount, Victim->GetWorld());
		if (ASOCombatCharacter* Dealer = Cast<ASOCombatCharacter>(Source))
		{
			Dealer->OnDealtDamage(Amount, NewHealth <= 0.0f, Victim);
		}
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

void USOAttributeSet::OnRep_Ultimate(const FGameplayAttributeData& OldValue)
{
	GAMEPLAYATTRIBUTE_REPNOTIFY(USOAttributeSet, Ultimate, OldValue);
}

void USOAttributeSet::OnRep_MaxUltimate(const FGameplayAttributeData& OldValue)
{
	GAMEPLAYATTRIBUTE_REPNOTIFY(USOAttributeSet, MaxUltimate, OldValue);
}

void USOAttributeSet::OnRep_MoveScale(const FGameplayAttributeData& OldValue)
{
	GAMEPLAYATTRIBUTE_REPNOTIFY(USOAttributeSet, MoveScale, OldValue);
}

void USOAttributeSet::OnRep_DamageTaken(const FGameplayAttributeData& OldValue)
{
	GAMEPLAYATTRIBUTE_REPNOTIFY(USOAttributeSet, DamageTaken, OldValue);
}

void USOAttributeSet::OnRep_Plating(const FGameplayAttributeData& OldValue)
{
	GAMEPLAYATTRIBUTE_REPNOTIFY(USOAttributeSet, Plating, OldValue);
}

void USOAttributeSet::OnRep_Mending(const FGameplayAttributeData& OldValue)
{
	GAMEPLAYATTRIBUTE_REPNOTIFY(USOAttributeSet, Mending, OldValue);
}

void USOAttributeSet::OnRep_Stride(const FGameplayAttributeData& OldValue)
{
	GAMEPLAYATTRIBUTE_REPNOTIFY(USOAttributeSet, Stride, OldValue);
}

void USOAttributeSet::OnRep_Ordnance(const FGameplayAttributeData& OldValue)
{
	GAMEPLAYATTRIBUTE_REPNOTIFY(USOAttributeSet, Ordnance, OldValue);
}

void USOAttributeSet::OnRep_Impact(const FGameplayAttributeData& OldValue)
{
	GAMEPLAYATTRIBUTE_REPNOTIFY(USOAttributeSet, Impact, OldValue);
}

void USOAttributeSet::OnRep_Focus(const FGameplayAttributeData& OldValue)
{
	GAMEPLAYATTRIBUTE_REPNOTIFY(USOAttributeSet, Focus, OldValue);
}
