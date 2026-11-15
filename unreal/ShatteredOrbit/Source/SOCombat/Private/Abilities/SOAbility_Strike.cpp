#include "Abilities/SOAbility_Strike.h"

#include "Engine/World.h"
#include "EngineUtils.h"
#include "SOCombatCharacter.h"
#include "SOCombatStatics.h"
#include "SOCombatTypes.h"
#include "SOFxSubsystem.h"

void USOAbility_Strike::Show(ASOCombatCharacter* User, const FSOAbilityGrant& Grant) const
{
	if (USOFxSubsystem* Fx = User->GetWorld() ? User->GetWorld()->GetSubsystem<USOFxSubsystem>() : nullptr)
	{
		Fx->Sweep(User->GetAimOrigin(), User->GetAimDirection(), Grant.Range, Grant.Angle, User->GetAbilityColor());
	}
}

FVector USOAbility_Strike::Heading(const ASOCombatCharacter* User)
{
	FVector Forward = User->IsPlayerControlled() ? User->GetAimDirection() : User->GetActorForwardVector();
	Forward.Z = 0.0f;
	return Forward.GetSafeNormal(UE_SMALL_NUMBER, User->GetActorForwardVector());
}

void USOAbility_Strike::Telegraph(ASOCombatCharacter* User, const FSOAbilityGrant& Grant) const
{
	USOFxSubsystem* Fx = User->GetWorld() ? User->GetWorld()->GetSubsystem<USOFxSubsystem>() : nullptr;
	if (Fx && Grant.WindUp >= WarnFrom)
	{
		// what is drawn is what it hits: the reach from its middle, the cone it lands in, under its feet as it turns
		const FVector Feet = User->GetActorLocation() - FVector(0.0f, 0.0f, User->GetSimpleCollisionHalfHeight());
		Fx->Warn(Feet, Grant.Range + 35.0f, Grant.Angle, Heading(User).Rotation().Yaw, Grant.WindUp, User->GetAbilityColor(), User);
	}
}

bool USOAbility_Strike::WantsUse(const ASOCombatCharacter* User, const AActor* Target, const FSOAbilityGrant& Grant, bool bSeesTarget) const
{
	// in reach (with room for the wind-up: the target will have moved a little) and, for a cone, in front
	if (!Target || !bSeesTarget)
	{
		return false;
	}
	const FVector To = Target->GetActorLocation() - User->GetActorLocation();
	return To.Size2D() < Grant.Range * 0.8f
		&& (Grant.Angle >= 179.0f || FVector::DotProduct(User->GetActorForwardVector().GetSafeNormal2D(), To.GetSafeNormal2D()) > FMath::Cos(FMath::DegreesToRadians(Grant.Angle * 0.7f)));
}

FVector USOAbility_Strike::Knock(const ASOCombatCharacter* User, const ASOCombatCharacter* Other, const FSOAbilityGrant& Grant) const
{
	const FVector Away = (Other->GetActorLocation() - User->GetActorLocation()).GetSafeNormal2D();
	return Away * Grant.Force + FVector(0.0f, 0.0f, Grant.Force * 0.35f);
}

void USOAbility_Strike::Perform(ASOCombatCharacter* User, const FSOAbilityGrant& Grant, bool bServer)
{
	UWorld* World = User->GetWorld();
	if (!bServer || !World)
	{
		return;
	}
	const FVector Origin = User->GetAimOrigin();
	const FVector Forward = Heading(User);
	const float MinDot = FMath::Cos(FMath::DegreesToRadians(FMath::Clamp(Grant.Angle, 1.0f, 180.0f)));

	FCollisionQueryParams Params(SCENE_QUERY_STAT(SOStrike), false, User);
	// one use, not a tick: walking the characters here costs nothing next to keeping a second list of them
	for (TActorIterator<ASOCombatCharacter> It(World); It; ++It)
	{
		ASOCombatCharacter* Other = *It;
		if (Other == User || Other->IsDead() || !USOCombatStatics::AreHostile(User, Other))
		{
			continue;
		}
		const FVector To = Other->GetActorLocation() - User->GetActorLocation();
		const float Reach = Grant.Range + Other->GetSimpleCollisionRadius();
		if (To.Size2D() > Reach || FMath::Abs(To.Z) > 220.0f || FVector::DotProduct(Forward, To.GetSafeNormal2D()) < MinDot)
		{
			continue;
		}
		// Not through a wall: the world's own geometry only. (A visibility trace was stopped by the user's own gun
		// when the target was low and close: a creature lunging in under the muzzle took no blow.)
		if (World->LineTraceTestByObjectType(Origin, Other->GetActorLocation(), FCollisionObjectQueryParams(ECC_WorldStatic), Params))
		{
			continue;
		}
		if (USOCombatStatics::ApplyDamage(User, Other, Grant.Damage * User->GetAbilityDamageScale(), false) <= 0.0f)
		{
			continue;
		}
		if (Other->IsDead())
		{
			continue;
		}
		if (Grant.Duration > 0.0f)
		{
			USOCombatStatics::ApplyStatus(User, Other, SOTags::Status_Stagger, Grant.Duration);
		}
		if (Grant.Force > 0.0f)
		{
			Other->LaunchCharacter(Knock(User, Other, Grant), true, true);
		}
	}
}
