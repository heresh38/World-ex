#include "SOAbility_Bolt.h"
#include "SOCue.h"

#include "Engine/World.h"
#include "EngineUtils.h"
#include "TimerManager.h"
#include "SOCombatStatics.h"
#include "SOCombatTypes.h"
#include "SOEnemy.h"
#include "SOEnemyAIController.h"
#include "SOProjectileSubsystem.h"
#include "SOFxSubsystem.h"
#include "Species/SOAlteredCommon.h"

void USOAbility_Bolt::Perform(ASOCombatCharacter* User, const FSOAbilityGrant& Grant, bool bServer)
{
	ASOEnemy* Caster = Cast<ASOEnemy>(User);
	AActor* Target = User->GetAbilityTarget();
	if (!bServer || !Caster || !Target)
	{
		return;
	}
	SOAltered::FireBolt(Caster, Caster->GetCastOrigin(), Target, Grant.Damage, Grant.Force, Grant.Angle); // (it takes the variant's damage scale itself)
}

bool USOAbility_Bolt::WantsUse(const ASOCombatCharacter* User, const AActor* Target, const FSOAbilityGrant& Grant, bool bSeesTarget) const
{
	return Target && bSeesTarget && FVector::Dist(User->GetActorLocation(), Target->GetActorLocation()) < 3300.0f;
}

// --- the barrage -------------------------------------------------------------------------------------

bool USOAbility_Barrage::WantsUse(const ASOCombatCharacter* User, const AActor* Target, const FSOAbilityGrant& Grant, bool bSeesTarget) const
{
	// seen, too far for its arms, inside the bolts' reach
	const float Dist = Target ? FVector::Dist(User->GetActorLocation(), Target->GetActorLocation()) : 0.0f;
	return Target && bSeesTarget && Dist > 450.0f && Dist < (Grant.Range > 0.0f ? Grant.Range : 4200.0f);
}

void USOAbility_Barrage::Telegraph(ASOCombatCharacter* User, const FSOAbilityGrant& Grant) const
{
	const ASOEnemy* Caster = Cast<ASOEnemy>(User);
	USOFxSubsystem* Fx = User->GetWorld() ? User->GetWorld()->GetSubsystem<USOFxSubsystem>() : nullptr;
	if (Caster && Fx)
	{
		Fx->Blast(Caster->GetCastOrigin(), User->GetActorForwardVector(), 150.0f, USOFxSubsystem::EBlast::Zap, User->GetAbilityColor()); // light gathering where they will leave it
	}
}

void USOAbility_Barrage::Perform(ASOCombatCharacter* User, const FSOAbilityGrant& Grant, bool bServer)
{
	UWorld* World = User->GetWorld();
	if (!bServer || !World)
	{
		return;
	}
	BoltsLeft = FMath::Max(1, FMath::RoundToInt(Grant.Magnitude));
	BoltDamage = Grant.Damage;
	BoltSpeed = Grant.Force;
	BoltScatter = Grant.Angle;
	const float Gap = FMath::Max(Grant.Duration, 0.05f) / BoltsLeft;
	FireOne();
	if (BoltsLeft > 0)
	{
		World->GetTimerManager().SetTimer(VolleyTimer, FTimerDelegate::CreateUObject(this, &USOAbility_Barrage::FireOne), Gap, true);
	}
}

void USOAbility_Barrage::FireOne()
{
	ASOEnemy* Caster = Cast<ASOEnemy>(GetAvatarActorFromActorInfo());
	AActor* Target = Caster ? Caster->GetAbilityTarget() : nullptr;
	if (!Caster || Caster->IsDead() || Caster->HasStatus(SOTags::Status_Stagger) || !Target || BoltsLeft <= 0)
	{
		BoltsLeft = 0;
	}
	else
	{
		SOAltered::FireBolt(Caster, Caster->GetCastOrigin(), Target, BoltDamage, BoltSpeed, BoltScatter);
		--BoltsLeft;
	}
	if (BoltsLeft <= 0)
	{
		if (UWorld* World = GetWorld())
		{
			World->GetTimerManager().ClearTimer(VolleyTimer);
		}
	}
}

void USOAbility_Barrage::EndAbility(const FGameplayAbilitySpecHandle Handle, const FGameplayAbilityActorInfo* ActorInfo, const FGameplayAbilityActivationInfo ActivationInfo, bool bReplicateEndAbility, bool bWasCancelled)
{
	BoltsLeft = 0;
	if (UWorld* World = GetWorld())
	{
		World->GetTimerManager().ClearTimer(VolleyTimer);
	}
	Super::EndAbility(Handle, ActorInfo, ActivationInfo, bReplicateEndAbility, bWasCancelled);
}

// --- the marksman's shot ------------------------------------------------------------------------------

FVector USOAbility_Snipe::AimPoint(const AActor* Target)
{
	// (where it was when the line stopped following it: a target that kept moving is no longer there)
	return Target->GetActorLocation() + FVector(0.0f, 0.0f, 20.0f) - Target->GetVelocity() * LockTime;
}

bool USOAbility_Snipe::WantsUse(const ASOCombatCharacter* User, const AActor* Target, const FSOAbilityGrant& Grant, bool bSeesTarget) const
{
	const float Dist = Target ? FVector::Dist(User->GetActorLocation(), Target->GetActorLocation()) : 0.0f;
	return Target && bSeesTarget && Dist >= Grant.Radius && Dist <= (Grant.Range > 0.0f ? Grant.Range : 7000.0f);
}

void USOAbility_Snipe::Telegraph(ASOCombatCharacter* User, const FSOAbilityGrant& Grant) const
{
	// (who it aims at is known to the server alone: the line goes to every machine as a cue, not from here on each)
	const ASOEnemy* Shooter = Cast<ASOEnemy>(User);
	if (Shooter && User->GetAbilityTarget())
	{
		USOCue::AimLine(User, User, User->GetActorTransform().InverseTransformPositionNoScale(Shooter->GetCastOrigin()), User->GetAbilityTarget(), Grant.WindUp, LockTime,
			User->GetAbilityColor());
	}
}

void USOAbility_Snipe::Perform(ASOCombatCharacter* User, const FSOAbilityGrant& Grant, bool bServer)
{
	ASOEnemy* Shooter = Cast<ASOEnemy>(User);
	AActor* Target = User->GetAbilityTarget();
	USOProjectileSubsystem* Rounds = bServer && User->GetWorld() ? User->GetWorld()->GetSubsystem<USOProjectileSubsystem>() : nullptr;
	if (!Shooter || !Target || !Rounds)
	{
		return;
	}
	const FVector From = Shooter->GetCastOrigin();
	FSOProjectile Round;
	Round.Origin = Round.Position = From;
	Round.Velocity = (AimPoint(Target) - From).GetSafeNormal() * 90000.0f;
	Round.Gravity = 0.0f;
	Round.Damage = Grant.Damage * User->GetAbilityDamageScale();
	Round.CritMultiplier = 1.0f; // (its damage is its own: no head-shot lottery on a player)
	Round.FalloffStart = 1000000.0f;
	Round.MinDamageScale = 1.0f;
	Round.Life = 1.5f;
	Round.Instigator = User;
	Rounds->Fire(Round);
	USOCombatStatics::ReportNoise(User, From, User, 4500.0f);
	// what the shot looks like, on every machine (the target is the server's knowledge)
	const FVector Dir = Round.Velocity.GetSafeNormal();
	USOCue::Tracer(User, From, From + Dir * (Grant.Range > 0.0f ? Grant.Range : 7000.0f), 90000.0f, User->GetAbilityColor(), 3.4f, 900.0f, true);
	USOCue::Blast(User, From, Dir, 90.0f, USOFxSubsystem::EBlast::Zap, User->GetAbilityColor());
	// after a few shots from one place it moves: a marksman that stays is found
	const int32 Per = FMath::RoundToInt(Grant.Magnitude);
	if (Per > 0 && ++Shots % Per == 0)
	{
		if (ASOEnemyAIController* Brain = Cast<ASOEnemyAIController>(Shooter->GetController()))
		{
			Brain->Relocate();
		}
	}
}

void USOAbility_Snipe::Show(ASOCombatCharacter* User, const FSOAbilityGrant& Grant) const
{
	// (nothing here: the shot's tracer and flash are cued from Perform, where the target is known)
}

// --- the rally ---------------------------------------------------------------------------------------

namespace
{
	template <typename TFunc>
	int32 ForMates(const ASOCombatCharacter* User, float Radius, TFunc&& Do)
	{
		int32 Count = 0;
		for (TActorIterator<ASOEnemy> It(User->GetWorld()); It; ++It) // one use, not a tick
		{
			if (*It != User && !It->IsDead() && It->Faction == User->Faction && FVector::Dist(It->GetActorLocation(), User->GetActorLocation()) < Radius)
			{
				Do(*It);
				++Count;
			}
		}
		return Count;
	}
}

bool USOAbility_Rally::WantsUse(const ASOCombatCharacter* User, const AActor* Target, const FSOAbilityGrant& Grant, bool bSeesTarget) const
{
	return Target && ForMates(User, Grant.Radius, [](ASOEnemy*) {}) >= 2; // someone to call to
}

void USOAbility_Rally::Perform(ASOCombatCharacter* User, const FSOAbilityGrant& Grant, bool bServer)
{
	if (!bServer)
	{
		return;
	}
	const FGameplayTag Named = USOCombatStatics::StatusTag(Grant.Status);
	const FGameplayTag Boon = Named.IsValid() ? Named : SOTags::Status_Haste;
	ForMates(User, Grant.Radius, [&](ASOEnemy* Mate)
	{
		USOCombatStatics::ApplyStatus(User, Mate, Boon, Grant.Duration, Grant.Magnitude);
		Mate->SetAlert(true);
	});
}

void USOAbility_Rally::Telegraph(ASOCombatCharacter* User, const FSOAbilityGrant& Grant) const
{
	if (ASOEnemy* Leader = Cast<ASOEnemy>(User))
	{
		Leader->Voice(TEXT("alert"), 1.0f); // it is heard calling before it lands
	}
}

void USOAbility_Rally::Show(ASOCombatCharacter* User, const FSOAbilityGrant& Grant) const
{
	if (USOFxSubsystem* Fx = User->GetWorld() ? User->GetWorld()->GetSubsystem<USOFxSubsystem>() : nullptr)
	{
		const FVector Feet = User->GetActorLocation() - FVector(0.0f, 0.0f, User->GetSimpleCollisionHalfHeight());
		Fx->Shockwave(Feet, Grant.Radius * 0.5f, User->GetAbilityColor());
	}
}
