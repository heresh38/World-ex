#include "SOGameplayEffects.h"

#include "SOAttributeSet.h"
#include "SOCombatTypes.h"

namespace
{
	FGameplayEffectModifierMagnitude ByCaller(const FGameplayTag& Tag)
	{
		FSetByCallerFloat SetByCaller;
		SetByCaller.DataTag = Tag;
		return FGameplayEffectModifierMagnitude(SetByCaller);
	}

	FGameplayModifierInfo SetBy(const FGameplayAttribute& Attribute, EGameplayModOp::Type Op, const FGameplayTag& Tag)
	{
		FGameplayModifierInfo Modifier;
		Modifier.Attribute = Attribute;
		Modifier.ModifierOp = Op;
		Modifier.ModifierMagnitude = ByCaller(Tag);
		return Modifier;
	}
}

USOGameplayEffect_Heal::USOGameplayEffect_Heal()
{
	DurationPolicy = EGameplayEffectDurationType::Instant;
	Modifiers.Add(SetBy(USOAttributeSet::GetHealthAttribute(), EGameplayModOp::AddBase, SOTags::SetByCaller_Magnitude));
}

USOGameplayEffect_Shield::USOGameplayEffect_Shield()
{
	DurationPolicy = EGameplayEffectDurationType::Instant;
	Modifiers.Add(SetBy(USOAttributeSet::GetShieldAttribute(), EGameplayModOp::AddBase, SOTags::SetByCaller_Magnitude));
}

USOGameplayEffect_ShieldRegen::USOGameplayEffect_ShieldRegen()
{
	DurationPolicy = EGameplayEffectDurationType::Infinite;
	Period.Value = TickPeriod;
	bExecutePeriodicEffectOnApplication = false;
	Modifiers.Add(SetBy(USOAttributeSet::GetShieldAttribute(), EGameplayModOp::AddBase, SOTags::SetByCaller_Magnitude));
}

USOGameplayEffect_Status::USOGameplayEffect_Status()
{
	DurationPolicy = EGameplayEffectDurationType::HasDuration;
	DurationMagnitude = ByCaller(SOTags::SetByCaller_Duration);
}

USOGameplayEffect_Burn::USOGameplayEffect_Burn()
{
	DurationPolicy = EGameplayEffectDurationType::HasDuration;
	DurationMagnitude = ByCaller(SOTags::SetByCaller_Duration);
	Period.Value = TickPeriod;
	bExecutePeriodicEffectOnApplication = false;
	Modifiers.Add(SetBy(USOAttributeSet::GetIncomingDamageAttribute(), EGameplayModOp::AddBase, SOTags::SetByCaller_Damage));
}

USOGameplayEffect_Slow::USOGameplayEffect_Slow()
{
	DurationPolicy = EGameplayEffectDurationType::HasDuration;
	DurationMagnitude = ByCaller(SOTags::SetByCaller_Duration);
	Modifiers.Add(SetBy(USOAttributeSet::GetMoveScaleAttribute(), EGameplayModOp::MultiplyCompound, SOTags::SetByCaller_Magnitude));
}

USOGameplayEffect_Guard::USOGameplayEffect_Guard()
{
	DurationPolicy = EGameplayEffectDurationType::HasDuration;
	DurationMagnitude = ByCaller(SOTags::SetByCaller_Duration);
	Modifiers.Add(SetBy(USOAttributeSet::GetDamageTakenAttribute(), EGameplayModOp::MultiplyCompound, SOTags::SetByCaller_Magnitude));
}

USOGameplayEffect_Gear::USOGameplayEffect_Gear()
{
	DurationPolicy = EGameplayEffectDurationType::Infinite;
	Modifiers.Add(SetBy(USOAttributeSet::GetPlatingAttribute(), EGameplayModOp::AddBase, SOTags::SetByCaller_Gear_Plating));
	Modifiers.Add(SetBy(USOAttributeSet::GetMendingAttribute(), EGameplayModOp::AddBase, SOTags::SetByCaller_Gear_Mending));
	Modifiers.Add(SetBy(USOAttributeSet::GetStrideAttribute(), EGameplayModOp::AddBase, SOTags::SetByCaller_Gear_Stride));
	Modifiers.Add(SetBy(USOAttributeSet::GetOrdnanceAttribute(), EGameplayModOp::AddBase, SOTags::SetByCaller_Gear_Ordnance));
	Modifiers.Add(SetBy(USOAttributeSet::GetImpactAttribute(), EGameplayModOp::AddBase, SOTags::SetByCaller_Gear_Impact));
	Modifiers.Add(SetBy(USOAttributeSet::GetFocusAttribute(), EGameplayModOp::AddBase, SOTags::SetByCaller_Gear_Focus));
}

USOGameplayEffect_Cooldown::USOGameplayEffect_Cooldown()
{
	DurationPolicy = EGameplayEffectDurationType::HasDuration;
	DurationMagnitude = ByCaller(SOTags::SetByCaller_Duration);
}

USOGameplayEffect_Ultimate::USOGameplayEffect_Ultimate()
{
	DurationPolicy = EGameplayEffectDurationType::Instant;
	Modifiers.Add(SetBy(USOAttributeSet::GetUltimateAttribute(), EGameplayModOp::AddBase, SOTags::SetByCaller_Magnitude));
}
