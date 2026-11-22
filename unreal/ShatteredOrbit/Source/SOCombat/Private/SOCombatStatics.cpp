#include "SOCombatStatics.h"
#include "SOExplosive.h"

#include "AbilitySystemBlueprintLibrary.h"
#include "AbilitySystemComponent.h"
#include "AbilitySystemGlobals.h"
#include "Engine/World.h"
#include "SOAttributeSet.h"
#include "SOCombatCharacter.h"
#include "SOCombatTypes.h"
#include "SOGameplayEffects.h"

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
	// a thing in the world that explodes is hurt like a body, by its own health (it has no attributes)
	if (ASOExplosive* Explosive = Cast<ASOExplosive>(Target))
	{
		return Explosive->TakeHit(Source, Amount);
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
	const USOAttributeSet* Set = TargetASC->GetSet<USOAttributeSet>();
	if (Set)
	{
		Set->TakeLastDamage();
	}
	Maker->ApplyGameplayEffectSpecToTarget(*Spec.Data, TargetASC);
	// what the gate let through (USOAttributeSet::TakeDamage): scaled by the victim, 0 if it was refused
	return Set ? Set->TakeLastDamage() : 0.0f;
}

bool USOCombatStatics::ApplyStatus(AActor* Source, AActor* Target, FGameplayTag Status, float Duration, float Magnitude)
{
	if (!Target || !Target->HasAuthority() || Duration <= 0.0f || !Status.IsValid())
	{
		return false;
	}
	if (const ASOCombatCharacter* Victim = Cast<ASOCombatCharacter>(Target))
	{
		if (Victim->IsDead() || (Source != Target && Victim->ResistsStatus(Status)))
		{
			return false; // (what it resists is what others do to it: a boss still reels when its own shield breaks)
		}
		if (Status == SOTags::Status_Stagger && Victim->HasStatus(SOTags::Status_Guard))
		{
			return false; // braced: not knocked out of anything
		}
	}
	// a boon goes to one's own side, a harm to the other
	const bool bBoon = Status == SOTags::Status_Guard || Status == SOTags::Status_Haste;
	if (Source && Source != Target && AreHostile(Source, Target) == bBoon)
	{
		return false;
	}
	UAbilitySystemComponent* TargetASC = UAbilitySystemGlobals::GetAbilitySystemComponentFromActor(Target);
	if (!TargetASC)
	{
		return false;
	}
	UAbilitySystemComponent* SourceASC = Source ? UAbilitySystemGlobals::GetAbilitySystemComponentFromActor(Source) : nullptr;
	UAbilitySystemComponent* Maker = SourceASC ? SourceASC : TargetASC;

	TSubclassOf<UGameplayEffect> Class = USOGameplayEffect_Status::StaticClass();
	if (Status == SOTags::Status_Burn)
	{
		Class = USOGameplayEffect_Burn::StaticClass();
	}
	else if (Status == SOTags::Status_Slow || Status == SOTags::Status_Haste)
	{
		Class = USOGameplayEffect_Slow::StaticClass(); // (a scale on the movement speed, either way)
	}
	else if (Status == SOTags::Status_Guard)
	{
		Class = USOGameplayEffect_Guard::StaticClass();
	}
	FGameplayEffectContextHandle Context = Maker->MakeEffectContext();
	Context.AddInstigator(Source, Source);
	const FGameplayEffectSpecHandle Spec = Maker->MakeOutgoingSpec(Class, 1.0f, Context);
	if (!Spec.IsValid())
	{
		return false;
	}
	Spec.Data->DynamicGrantedTags.AddTag(Status);
	Spec.Data->SetSetByCallerMagnitude(SOTags::SetByCaller_Duration, Duration);
	if (Status == SOTags::Status_Burn)
	{
		if (Magnitude <= 0.0f)
		{
			return false;
		}
		Spec.Data->SetSetByCallerMagnitude(SOTags::SetByCaller_Damage, Magnitude / Duration * USOGameplayEffect_Burn::TickPeriod);
		Spec.Data->SetSetByCallerMagnitude(SOTags::SetByCaller_Crit, 0.0f);
	}
	else if (Status == SOTags::Status_Slow || Status == SOTags::Status_Guard)
	{
		Spec.Data->SetSetByCallerMagnitude(SOTags::SetByCaller_Magnitude, FMath::Clamp(Magnitude, 0.05f, 1.0f));
	}
	else if (Status == SOTags::Status_Haste)
	{
		Spec.Data->SetSetByCallerMagnitude(SOTags::SetByCaller_Magnitude, FMath::Clamp(Magnitude, 1.0f, 2.0f));
	}
	Maker->ApplyGameplayEffectSpecToTarget(*Spec.Data, TargetASC);
	return true;
}

FGameplayTag USOCombatStatics::StatusTag(FName Name)
{
	static const TMap<FName, FGameplayTag> Tags = {
		{ TEXT("burn"), SOTags::Status_Burn }, { TEXT("slow"), SOTags::Status_Slow }, { TEXT("stagger"), SOTags::Status_Stagger },
		{ TEXT("guard"), SOTags::Status_Guard }, { TEXT("jam"), SOTags::Status_Jam }, { TEXT("haste"), SOTags::Status_Haste },
		{ TEXT("suppressed"), SOTags::Status_Suppressed } };
	const FGameplayTag* Found = Tags.Find(Name);
	return Found ? *Found : FGameplayTag();
}

bool USOCombatStatics::AreHostile(const AActor* A, const AActor* B)
{
	const ASOCombatCharacter* CA = Cast<ASOCombatCharacter>(A);
	const ASOCombatCharacter* CB = Cast<ASOCombatCharacter>(B);
	if (!CA || !CB)
	{
		return true;
	}
	if (CA->IsDisplayOnly() || CB->IsDisplayOnly())
	{
		return false;                                          // (a body only to be looked at is nobody's enemy)
	}
	return CA->Faction != CB->Faction;
}

FSOOnCharacterDied& USOCombatStatics::OnCharacterDied()
{
	static FSOOnCharacterDied Delegate;
	return Delegate;
}

namespace
{
	FSOHitInfo GLastHit;
}

FSOHitScope::FSOHitScope(FName Bone, const FVector& Point, const FVector& Direction, bool bPrecision)
	: Before(GLastHit)
{
	GLastHit.Bone = Bone;
	GLastHit.Point = Point;
	GLastHit.Direction = Direction;
	GLastHit.bPrecision = bPrecision;
	GLastHit.bKnown = true;
}

FSOHitScope::~FSOHitScope()
{
	GLastHit = Before;
}

const FSOHitInfo& USOCombatStatics::LastHit()
{
	return GLastHit;
}

ESOHitRegion FSOHitInfo::RegionOf(FName Bone)
{
	const FString Name = Bone.ToString().ToLower();
	const bool bLeft = Name.EndsWith(TEXT("_l")) || Name.EndsWith(TEXT(".l"));
	if (Name.Contains(TEXT("head")) || Name.Contains(TEXT("neck")))
	{
		return ESOHitRegion::Head;
	}
	if (Name.Contains(TEXT("arm")) || Name.Contains(TEXT("hand")) || Name.Contains(TEXT("clavicle")))
	{
		return bLeft ? ESOHitRegion::ArmLeft : ESOHitRegion::ArmRight;
	}
	if (Name.Contains(TEXT("thigh")) || Name.Contains(TEXT("shin")) || Name.Contains(TEXT("foot")) || Name.Contains(TEXT("calf")))
	{
		return bLeft ? ESOHitRegion::LegLeft : ESOHitRegion::LegRight;
	}
	return ESOHitRegion::Torso;
}

FSOOnCharacterHit& USOCombatStatics::OnCharacterHit()
{
	static FSOOnCharacterHit Delegate;
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
