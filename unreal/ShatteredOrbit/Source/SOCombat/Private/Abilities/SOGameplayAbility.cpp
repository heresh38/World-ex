#include "Abilities/SOGameplayAbility.h"

#include "AbilitySystemComponent.h"
#include "Engine/World.h"
#include "TimerManager.h"
#include "SOAttributeSet.h"
#include "SOCombatCharacter.h"
#include "SOCombatTypes.h"
#include "SOGameplayEffects.h"

USOGameplayAbility::USOGameplayAbility()
{
	InstancingPolicy = EGameplayAbilityInstancingPolicy::InstancedPerActor;
	NetExecutionPolicy = EGameplayAbilityNetExecutionPolicy::LocalPredicted;
	ActivationBlockedTags.AddTag(SOTags::State_Dead);
	ActivationBlockedTags.AddTag(SOTags::State_Traversing);
	ActivationBlockedTags.AddTag(SOTags::Status_Stagger);
	ActivationBlockedTags.AddTag(SOTags::Status_Jam);
}

FGameplayTag USOGameplayAbility::CooldownTag(ESOAbilitySlot Slot)
{
	switch (Slot)
	{
	case ESOAbilitySlot::Grenade: return SOTags::Cooldown_Grenade;
	case ESOAbilitySlot::Melee: return SOTags::Cooldown_Melee;
	case ESOAbilitySlot::Class: return SOTags::Cooldown_Class;
	case ESOAbilitySlot::Movement: return SOTags::Cooldown_Movement;
	case ESOAbilitySlot::Ultimate: return SOTags::Cooldown_Ultimate;
	default: return FGameplayTag();
	}
}

const FSOAbilityGrant* USOGameplayAbility::GrantFor(const FGameplayAbilitySpecHandle Handle, const FGameplayAbilityActorInfo* ActorInfo) const
{
	const UAbilitySystemComponent* ASC = ActorInfo ? ActorInfo->AbilitySystemComponent.Get() : nullptr;
	const FGameplayAbilitySpec* Spec = ASC ? ASC->FindAbilitySpecFromHandle(Handle) : nullptr;
	const USOAbilitySet* Set = Spec ? Cast<USOAbilitySet>(Spec->SourceObject.Get()) : nullptr;
	return Set && Spec->InputID >= 0 ? Set->Find(static_cast<ESOAbilitySlot>(Spec->InputID)) : nullptr;
}

bool USOGameplayAbility::CheckCooldown(const FGameplayAbilitySpecHandle Handle, const FGameplayAbilityActorInfo* ActorInfo, FGameplayTagContainer* OptionalRelevantTags) const
{
	const FSOAbilityGrant* Grant = GrantFor(Handle, ActorInfo);
	const UAbilitySystemComponent* ASC = ActorInfo ? ActorInfo->AbilitySystemComponent.Get() : nullptr;
	if (!Grant || !ASC)
	{
		return true;
	}
	const FGameplayTag Tag = CooldownTag(Grant->Slot);
	const int32 Recharging = ASC->GetActiveEffects(FGameplayEffectQuery::MakeQuery_MatchAnyOwningTags(FGameplayTagContainer(Tag))).Num();
	if (Recharging < FMath::Max(1, Grant->Charges))
	{
		return true;
	}
	if (OptionalRelevantTags)
	{
		OptionalRelevantTags->AddTag(Tag);
	}
	return false;
}

void USOGameplayAbility::ApplyCooldown(const FGameplayAbilitySpecHandle Handle, const FGameplayAbilityActorInfo* ActorInfo, const FGameplayAbilityActivationInfo ActivationInfo) const
{
	const FSOAbilityGrant* Grant = GrantFor(Handle, ActorInfo);
	if (!Grant || Grant->Cooldown <= 0.0f)
	{
		return;
	}
	const FGameplayEffectSpecHandle Spec = MakeOutgoingGameplayEffectSpec(Handle, ActorInfo, ActivationInfo, USOGameplayEffect_Cooldown::StaticClass(), 1.0f);
	if (Spec.IsValid())
	{
		Spec.Data->DynamicGrantedTags.AddTag(CooldownTag(Grant->Slot));
		const ASOCombatCharacter* User = ActorInfo ? Cast<ASOCombatCharacter>(ActorInfo->AvatarActor.Get()) : nullptr;
		Spec.Data->SetSetByCallerMagnitude(SOTags::SetByCaller_Duration, FMath::Max(0.05f, Grant->Cooldown * (User ? User->GetAbilityCooldownScale(Grant->Slot) : 1.0f)));
		ApplyGameplayEffectSpecToOwner(Handle, ActorInfo, ActivationInfo, Spec);
	}
}

bool USOGameplayAbility::CheckCost(const FGameplayAbilitySpecHandle Handle, const FGameplayAbilityActorInfo* ActorInfo, FGameplayTagContainer* OptionalRelevantTags) const
{
	const FSOAbilityGrant* Grant = GrantFor(Handle, ActorInfo);
	if (!Grant || Grant->UltimateCost <= 0.0f)
	{
		return true;
	}
	const UAbilitySystemComponent* ASC = ActorInfo ? ActorInfo->AbilitySystemComponent.Get() : nullptr;
	const USOAttributeSet* Set = ASC ? ASC->GetSet<USOAttributeSet>() : nullptr;
	return Set && Set->GetUltimate() + KINDA_SMALL_NUMBER >= Grant->UltimateCost;
}

void USOGameplayAbility::ApplyCost(const FGameplayAbilitySpecHandle Handle, const FGameplayAbilityActorInfo* ActorInfo, const FGameplayAbilityActivationInfo ActivationInfo) const
{
	const FSOAbilityGrant* Grant = GrantFor(Handle, ActorInfo);
	if (!Grant || Grant->UltimateCost <= 0.0f)
	{
		return;
	}
	const FGameplayEffectSpecHandle Spec = MakeOutgoingGameplayEffectSpec(Handle, ActorInfo, ActivationInfo, USOGameplayEffect_Ultimate::StaticClass(), 1.0f);
	if (Spec.IsValid())
	{
		Spec.Data->SetSetByCallerMagnitude(SOTags::SetByCaller_Magnitude, -Grant->UltimateCost);
		ApplyGameplayEffectSpecToOwner(Handle, ActorInfo, ActivationInfo, Spec);
	}
}

void USOGameplayAbility::ActivateAbility(const FGameplayAbilitySpecHandle Handle, const FGameplayAbilityActorInfo* ActorInfo, const FGameplayAbilityActivationInfo ActivationInfo, const FGameplayEventData* TriggerEventData)
{
	if (!CommitAbility(Handle, ActorInfo, ActivationInfo))
	{
		EndAbility(Handle, ActorInfo, ActivationInfo, true, true);
		return;
	}
	ASOCombatCharacter* User = ActorInfo ? Cast<ASOCombatCharacter>(ActorInfo->AvatarActor.Get()) : nullptr;
	const FSOAbilityGrant* Grant = GrantFor(Handle, ActorInfo);
	if (!User || !Grant)
	{
		EndAbility(Handle, ActorInfo, ActivationInfo, true, false);
		return;
	}
	if (Grant->WindUp > 0.0f && User->GetWorld())
	{
		// paid for and committed to: shown winding up now, done when the time is up (Release)
		User->ShowAbility(Grant->Slot, true);
		User->GetWorld()->GetTimerManager().SetTimer(WindUpTimer, FTimerDelegate::CreateUObject(this, &USOGameplayAbility::Release), Grant->WindUp, false);
		return;
	}
	Perform(User, *Grant, ActorInfo->IsNetAuthority());
	User->ShowAbility(Grant->Slot);
	if (!Hold(*Grant))
	{
		EndAbility(Handle, ActorInfo, ActivationInfo, true, false);
	}
}

bool USOGameplayAbility::Hold(const FSOAbilityGrant& Grant)
{
	const float Time = ChannelTime(Grant);
	UWorld* World = GetWorld();
	if (Time <= 0.0f || !World)
	{
		return false;
	}
	World->GetTimerManager().SetTimer(WindUpTimer, FTimerDelegate::CreateUObject(this, &USOGameplayAbility::Finish), Time, false);
	return true;
}

void USOGameplayAbility::Finish()
{
	EndAbility(GetCurrentAbilitySpecHandle(), GetCurrentActorInfo(), GetCurrentActivationInfo(), true, false);
}

void USOGameplayAbility::Release()
{
	const FGameplayAbilityActorInfo* Info = GetCurrentActorInfo();
	const FGameplayAbilitySpecHandle Handle = GetCurrentAbilitySpecHandle();
	ASOCombatCharacter* User = Info ? Cast<ASOCombatCharacter>(Info->AvatarActor.Get()) : nullptr;
	const FSOAbilityGrant* Grant = GrantFor(Handle, Info);
	const bool bStopped = !User || !Grant || User->IsDead() || User->HasStatus(SOTags::Status_Stagger);
	if (!bStopped)
	{
		Perform(User, *Grant, Info->IsNetAuthority());
		User->ShowAbility(Grant->Slot);
		if (Hold(*Grant))
		{
			return;
		}
	}
	EndAbility(Handle, Info, GetCurrentActivationInfo(), true, bStopped);
}

void USOGameplayAbility::EndAbility(const FGameplayAbilitySpecHandle Handle, const FGameplayAbilityActorInfo* ActorInfo, const FGameplayAbilityActivationInfo ActivationInfo, bool bReplicateEndAbility, bool bWasCancelled)
{
	if (WindUpTimer.IsValid())
	{
		if (UWorld* World = GetWorld())
		{
			World->GetTimerManager().ClearTimer(WindUpTimer);
		}
	}
	Super::EndAbility(Handle, ActorInfo, ActivationInfo, bReplicateEndAbility, bWasCancelled);
}
