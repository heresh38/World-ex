#include "SOCombatStatics.h"

#include "AbilitySystemBlueprintLibrary.h"
#include "AbilitySystemComponent.h"
#include "AbilitySystemGlobals.h"
#include "Engine/World.h"
#include "SOAttributeSet.h"
#include "SOCombatCharacter.h"
#include "SOCombatTypes.h"

USOGameplayEffect_Damage::USOGameplayEffect_Damage()
{
	DurationPolicy = EGameplayEffectDurationType::Instant;

	FSetByCallerFloat SetByCaller;
	SetByCaller.DataTag = SOTags::SetByCaller_Damage;

	FGameplayModifierInfo Modifier;
	Modifier.Attribute = USOAttributeSet::GetIncomingDamageAttribute();
	Modifier.ModifierOp = EGameplayModOp::Additive;
	Modifier.ModifierMagnitude = FGameplayEffectModifierMagnitude(SetByCaller);
	Modifiers.Add(Modifier);
}

float USOCombatStatics::ApplyDamage(AActor* Source, AActor* Target, float Amount, bool bCrit)
{
	if (!Target || Amount <= 0.0f || !Target->HasAuthority())
	{
		return 0.0f;
	}
	if (const ASOCombatCharacter* Victim = Cast<ASOCombatCharacter>(Target); Victim && Victim->IsDead())
	{
		return 0.0f;
	}
	if (Source && Source != Target && !AreHostile(Source, Target))
	{
		return 0.0f;
	}
	UAbilitySystemComponent* TargetASC = UAbilitySystemGlobals::GetAbilitySystemComponentFromActor(Target);
	if (!TargetASC)
	{
		return 0.0f;
	}
	UAbilitySystemComponent* SourceASC = Source ? UAbilitySystemGlobals::GetAbilitySystemComponentFromActor(Source) : nullptr;
	UAbilitySystemComponent* Maker = SourceASC ? SourceASC : TargetASC;

	FGameplayEffectContextHandle Context = Maker->MakeEffectContext();
	Context.AddInstigator(Source, Source);
	const FGameplayEffectSpecHandle Spec = Maker->MakeOutgoingSpec(USOGameplayEffect_Damage::StaticClass(), 1.0f, Context);
	if (!Spec.IsValid())
	{
		return 0.0f;
	}
	Spec.Data->SetSetByCallerMagnitude(SOTags::SetByCaller_Damage, Amount);
	Spec.Data->SetSetByCallerMagnitude(SOTags::SetByCaller_Crit, bCrit ? 1.0f : 0.0f);
	Maker->ApplyGameplayEffectSpecToTarget(*Spec.Data, TargetASC);
	return Amount;
}

bool USOCombatStatics::AreHostile(const AActor* A, const AActor* B)
{
	const ASOCombatCharacter* CA = Cast<ASOCombatCharacter>(A);
	const ASOCombatCharacter* CB = Cast<ASOCombatCharacter>(B);
	if (!CA || !CB)
	{
		return true;
	}
	return CA->Faction != CB->Faction;
}

FSOOnCharacterDied& USOCombatStatics::OnCharacterDied()
{
	static FSOOnCharacterDied Delegate;
	return Delegate;
}

FSOOnNoise& USOCombatStatics::OnNoise()
{
	static FSOOnNoise Delegate;
	return Delegate;
}

void USOCombatStatics::ReportNoise(const UObject* WorldContext, FVector Location, AActor* Instigator, float Radius)
{
	UWorld* World = WorldContext ? WorldContext->GetWorld() : nullptr;
	if (World)
	{
		OnNoise().Broadcast(World, Location, Instigator, Radius);
	}
}
