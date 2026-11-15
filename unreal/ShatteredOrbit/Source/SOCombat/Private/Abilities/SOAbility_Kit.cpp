#include "Abilities/SOAbility_Kit.h"

#include "Engine/World.h"
#include "EngineUtils.h"
#include "TimerManager.h"
#include "SOCombatCharacter.h"
#include "SOCombatStatics.h"
#include "SOCombatTypes.h"
#include "SOCue.h"
#include "SOFxSubsystem.h"
#include "SOProjectileSubsystem.h"
#include "SOSound.h"

namespace
{
	const FLinearColor ChargeFire(1.0f, 0.6f, 0.25f);
}

// --- the thrown charge --------------------------------------------------------------------------

void USOAbility_Grenade::Throw(const ASOCombatCharacter* User, const FSOAbilityGrant& Grant, FVector& OutStart, FVector& OutVelocity)
{
	const FVector Dir = User->GetAimDirection();
	OutStart = User->GetAimOrigin() + Dir * 60.0f - FVector(0.0f, 0.0f, 12.0f);
	OutVelocity = Dir * Grant.Force + FVector(0.0f, 0.0f, Grant.Force * 0.18f);
}

void USOAbility_Grenade::Perform(ASOCombatCharacter* User, const FSOAbilityGrant& Grant, bool bServer)
{
	USOProjectileSubsystem* Rounds = bServer && User->GetWorld() ? User->GetWorld()->GetSubsystem<USOProjectileSubsystem>() : nullptr;
	if (!Rounds)
	{
		return;
	}
	FSOProjectile Charge;
	Throw(User, Grant, Charge.Origin, Charge.Velocity);
	Charge.Position = Charge.Origin;
	Charge.Gravity = 980.0f;
	Charge.Damage = Grant.Damage * User->GetAbilityDamageScale();
	Charge.CritMultiplier = 1.0f;
	Charge.FalloffStart = 1000000.0f; // a charge is as strong at the end of its throw as at the start
	Charge.Life = 8.0f;
	Charge.Instigator = User;
	Charge.Splash = Grant.Radius;
	if (Grant.Duration > 0.0f && Grant.Magnitude > 0.0f)
	{
		const FGameplayTag Named = USOCombatStatics::StatusTag(Grant.Status);
		Charge.Status = Named.IsValid() ? Named : SOTags::Status_Slow; // (a charge slows unless its grant says otherwise)
		Charge.StatusDuration = Grant.Duration;
		Charge.StatusMagnitude = Grant.Magnitude;
	}
	Rounds->Fire(Charge);
}

void USOAbility_Grenade::Show(ASOCombatCharacter* User, const FSOAbilityGrant& Grant) const
{
	UWorld* World = User->GetWorld();
	USOFxSubsystem* Fx = World ? World->GetSubsystem<USOFxSubsystem>() : nullptr;
	if (!Fx)
	{
		return;
	}
	// the path the server's charge takes, walked here so every machine draws the same flight and burst
	FVector P, V;
	Throw(User, Grant, P, V);
	const FVector Start = P, Velocity = V;
	FCollisionQueryParams Params(SCENE_QUERY_STAT(SOChargeArc), false, User);
	FHitResult Hit;
	bool bHit = false;
	float Flight = 0.0f;
	FVector End = P;
	const float Step = 0.02f;
	for (float T = 0.0f; T < 8.0f; T += Step)
	{
		const FVector Next = P + V * Step + FVector(0.0f, 0.0f, -0.5f * 980.0f * Step * Step);
		V.Z -= 980.0f * Step;
		if (World->LineTraceSingleByChannel(Hit, P, Next, SO_TRACE_BULLET, Params))
		{
			bHit = true;
			End = Hit.ImpactPoint;
			Flight = T + Step * (Hit.Distance / FMath::Max(FVector::Dist(P, Next), 1.0f));
			break;
		}
		P = Next;
		End = P;
		Flight = T;
	}
	Fx->Trail(Start, Velocity, 980.0f, Flight, USOFxSubsystem::ETrail::Rocket, ChargeFire);
	if (!bHit)
	{
		return;
	}
	Fx->Blast(End, Hit.ImpactNormal, Grant.Radius * 0.6f, USOFxSubsystem::EBlast::Fire, ChargeFire, Flight);
	Fx->Shockwave(End + FVector(Hit.ImpactNormal) * 8.0f, Grant.Radius, User->GetAbilityColor(), Flight); // how far it reaches, drawn
	FTimerHandle Boom;
	World->GetTimerManager().SetTimer(Boom, FTimerDelegate::CreateWeakLambda(User, [User, End]()
	{
		USOSoundLibrary::PlayAt(User, TEXT("ability_charge_burst"), End, 1.0f, 0.05f, ESOSoundRange::Far);
	}), FMath::Max(Flight, 0.01f), false);
}

// --- braced --------------------------------------------------------------------------------------

void USOAbility_Guard::Perform(ASOCombatCharacter* User, const FSOAbilityGrant& Grant, bool bServer)
{
	if (bServer)
	{
		USOCombatStatics::ApplyStatus(User, User, SOTags::Status_Guard, Grant.Duration, Grant.Magnitude);
	}
}

void USOAbility_Guard::Show(ASOCombatCharacter* User, const FSOAbilityGrant& Grant) const
{
	if (USOFxSubsystem* Fx = User->GetWorld() ? User->GetWorld()->GetSubsystem<USOFxSubsystem>() : nullptr)
	{
		// a ring of rising light round the body: its own player sees it come up all round the view
		const FVector Feet = User->GetActorLocation() - FVector(0.0f, 0.0f, User->GetSimpleCollisionHalfHeight());
		Fx->Ward(Feet, User->GetSimpleCollisionHalfHeight() * 2.0f, User->GetAbilityColor());
	}
}

// --- the blow into the ground --------------------------------------------------------------------

void USOAbility_Slam::Show(ASOCombatCharacter* User, const FSOAbilityGrant& Grant) const
{
	if (USOFxSubsystem* Fx = User->GetWorld() ? User->GetWorld()->GetSubsystem<USOFxSubsystem>() : nullptr)
	{
		const FVector Feet = User->GetActorLocation() - FVector(0.0f, 0.0f, User->GetSimpleCollisionHalfHeight());
		Fx->Shockwave(Feet, Grant.Range, User->GetAbilityColor());
	}
}

// --- a creature's rules for these ------------------------------------------------------------------

bool USOAbility_Grenade::WantsUse(const ASOCombatCharacter* User, const AActor* Target, const FSOAbilityGrant& Grant, bool bSeesTarget) const
{
	// a target it can see, too far for a blow and inside the throw
	const float Dist = Target ? FVector::Dist2D(User->GetActorLocation(), Target->GetActorLocation()) : 0.0f;
	return Target && bSeesTarget && Dist > 800.0f && Dist < Grant.Force * 1.1f;
}

bool USOAbility_Guard::WantsUse(const ASOCombatCharacter* User, const AActor* Target, const FSOAbilityGrant& Grant, bool bSeesTarget) const
{
	return Target && bSeesTarget && User->GetHealth() < User->GetMaxHealth() * 0.5f; // hurt, and still in the fight
}

// --- the pulse ---------------------------------------------------------------------------------------

bool USOAbility_Pulse::WantsUse(const ASOCombatCharacter* User, const AActor* Target, const FSOAbilityGrant& Grant, bool bSeesTarget) const
{
	return Target && bSeesTarget && FVector::Dist2D(User->GetActorLocation(), Target->GetActorLocation()) < Grant.Radius * 0.8f;
}

void USOAbility_Pulse::Perform(ASOCombatCharacter* User, const FSOAbilityGrant& Grant, bool bServer)
{
	UWorld* World = User->GetWorld();
	if (!bServer || !World)
	{
		return;
	}
	const FGameplayTag Status = USOCombatStatics::StatusTag(Grant.Status);
	const FVector Centre = User->GetActorLocation();
	FCollisionQueryParams Params(SCENE_QUERY_STAT(SOPulse), false, User);
	for (TActorIterator<ASOCombatCharacter> It(World); It; ++It) // one use, not a tick
	{
		ASOCombatCharacter* Other = *It;
		if (Other == User || Other->IsDead() || !USOCombatStatics::AreHostile(User, Other))
		{
			continue;
		}
		const FVector To = Other->GetActorLocation() - Centre;
		if (To.Size2D() > Grant.Radius || FMath::Abs(To.Z) > 300.0f
			|| World->LineTraceTestByObjectType(Centre, Other->GetActorLocation(), FCollisionObjectQueryParams(ECC_WorldStatic), Params))
		{
			continue;
		}
		if (Grant.Damage > 0.0f)
		{
			USOCombatStatics::ApplyDamage(User, Other, Grant.Damage * User->GetAbilityDamageScale(), false);
		}
		if (Status.IsValid() && Grant.Duration > 0.0f && !Other->IsDead())
		{
			USOCombatStatics::ApplyStatus(User, Other, Status, Grant.Duration, Grant.Magnitude);
		}
	}
}

void USOAbility_Pulse::Telegraph(ASOCombatCharacter* User, const FSOAbilityGrant& Grant) const
{
	if (USOFxSubsystem* Fx = User->GetWorld() ? User->GetWorld()->GetSubsystem<USOFxSubsystem>() : nullptr)
	{
		const FVector Feet = User->GetActorLocation() - FVector(0.0f, 0.0f, User->GetSimpleCollisionHalfHeight());
		Fx->Ward(Feet, User->GetSimpleCollisionHalfHeight() * 2.0f, User->GetAbilityColor()); // gathering: the warning
		Fx->Warn(Feet, Grant.Radius, 180.0f, 0.0f, Grant.WindUp, User->GetAbilityColor(), User); // and how far it will reach
	}
}

void USOAbility_Pulse::Show(ASOCombatCharacter* User, const FSOAbilityGrant& Grant) const
{
	if (USOFxSubsystem* Fx = User->GetWorld() ? User->GetWorld()->GetSubsystem<USOFxSubsystem>() : nullptr)
	{
		const FVector Feet = User->GetActorLocation() - FVector(0.0f, 0.0f, User->GetSimpleCollisionHalfHeight());
		Fx->Shockwave(Feet, Grant.Radius, User->GetAbilityColor()); // as far as it reaches
	}
}

// --- the sweep ---------------------------------------------------------------------------------------

FVector USOAbility_Sweep::Knock(const ASOCombatCharacter* User, const ASOCombatCharacter* Other, const FSOAbilityGrant& Grant) const
{
	// across the front, the way the arm goes (from the user's right to its left), and a little away
	const FVector Forward = Heading(User);
	const FVector Right = FVector::CrossProduct(FVector::UpVector, Forward);
	return -Right * Grant.Force + Forward * Grant.Force * 0.33f + FVector(0.0f, 0.0f, Grant.Force * 0.42f);
}

// --- the marks that burst ------------------------------------------------------------------------------

namespace
{
	/** The ground under a point (the world's own geometry), or the point itself. */
	FVector GroundUnder(const UWorld* World, const FVector& At)
	{
		FHitResult Hit;
		const FCollisionQueryParams Params(SCENE_QUERY_STAT(SOEruption), false);
		return World->LineTraceSingleByObjectType(Hit, At + FVector(0.0f, 0.0f, 120.0f), At - FVector(0.0f, 0.0f, 700.0f), FCollisionObjectQueryParams(ECC_WorldStatic), Params)
			? FVector(Hit.ImpactPoint) : At;
	}
}

bool USOAbility_Eruption::WantsUse(const ASOCombatCharacter* User, const AActor* Target, const FSOAbilityGrant& Grant, bool bSeesTarget) const
{
	return Target && FVector::Dist(User->GetActorLocation(), Target->GetActorLocation()) < Grant.Range; // (seen or not: it comes up under them)
}

void USOAbility_Eruption::Telegraph(ASOCombatCharacter* User, const FSOAbilityGrant& Grant) const
{
	if (USOFxSubsystem* Fx = User->GetWorld() ? User->GetWorld()->GetSubsystem<USOFxSubsystem>() : nullptr)
	{
		const FVector Feet = User->GetActorLocation() - FVector(0.0f, 0.0f, User->GetSimpleCollisionHalfHeight());
		Fx->Ward(Feet, User->GetSimpleCollisionHalfHeight() * 2.0f, User->GetAbilityColor()); // it is calling something up
	}
}

TArray<FVector> USOAbility_Eruption::Marks(const ASOCombatCharacter* User, const FSOAbilityGrant& Grant)
{
	TArray<FVector> Out;
	const UWorld* World = User->GetWorld();
	for (TActorIterator<ASOCombatCharacter> It(World); It; ++It) // one use, not a tick
	{
		const ASOCombatCharacter* Other = *It;
		if (Other != User && !Other->IsDead() && USOCombatStatics::AreHostile(User, Other)
			&& FVector::Dist(Other->GetActorLocation(), User->GetActorLocation()) < Grant.Range)
		{
			Out.Add(GroundUnder(World, Other->GetActorLocation() - FVector(0.0f, 0.0f, Other->GetSimpleCollisionHalfHeight())));
		}
	}
	// and more round them: the way out is not simply a step to the side
	const int32 Under = Out.Num();
	for (int32 i = 0; Under > 0 && i < FMath::RoundToInt(Grant.Magnitude); ++i)
	{
		const float A = FMath::FRandRange(0.0f, UE_TWO_PI);
		const FVector Off = FVector(FMath::Cos(A), FMath::Sin(A), 0.0f) * Grant.Radius * FMath::FRandRange(1.6f, 2.8f);
		Out.Add(GroundUnder(World, Out[i % Under] + Off + FVector(0.0f, 0.0f, 60.0f)));
	}
	return Out;
}

void USOAbility_Eruption::Perform(ASOCombatCharacter* User, const FSOAbilityGrant& Grant, bool bServer)
{
	UWorld* World = User->GetWorld();
	if (!bServer || !World)
	{
		return;
	}
	const TArray<FVector> Spots = Marks(User, Grant);
	if (Spots.Num() == 0)
	{
		return;
	}
	const float Fuse = FMath::Max(Grant.Duration, 0.3f);
	for (const FVector& Spot : Spots)
	{
		USOCue::Warn(User, Spot, Grant.Radius, 180.0f, 0.0f, Fuse, User->GetAbilityColor());
	}
	// they burst together when the fuse is up (not this ability's own timer: it is over, the marks are not)
	const float Damage = Grant.Damage * User->GetAbilityDamageScale(), Radius = Grant.Radius, Force = Grant.Force;
	FTimerHandle Timer;
	World->GetTimerManager().SetTimer(Timer, FTimerDelegate::CreateWeakLambda(User, [User, Spots, Damage, Radius, Force]()
	{
		Burst(User, Spots, Damage, Radius, Force);
	}), Fuse, false);
}

void USOAbility_Eruption::Burst(ASOCombatCharacter* User, const TArray<FVector>& Spots, float Damage, float Radius, float Force)
{
	UWorld* World = User ? User->GetWorld() : nullptr;
	if (!World || User->IsDead())
	{
		return; // whoever called them up is gone: they come to nothing
	}
	TSet<const ASOCombatCharacter*> Caught; // two marks that overlap are still one burst to whoever stands in both
	for (const FVector& Spot : Spots)
	{
		USOCue::Blast(User, Spot, FVector::UpVector, Radius * 0.8f, USOFxSubsystem::EBlast::Zap, User->GetAbilityColor());
		USOCue::Sound(User, TEXT("boss_mark_burst"), Spot, 0.85f, 0.1f, ESOSoundRange::Mid);
		for (TActorIterator<ASOCombatCharacter> It(World); It; ++It)
		{
			ASOCombatCharacter* Other = *It;
			if (Other == User || Other->IsDead() || Caught.Contains(Other) || !USOCombatStatics::AreHostile(User, Other))
			{
				continue;
			}
			const FVector To = Other->GetActorLocation() - FVector(0.0f, 0.0f, Other->GetSimpleCollisionHalfHeight()) - Spot;
			if (To.Size2D() > Radius || FMath::Abs(To.Z) > 260.0f)
			{
				continue;
			}
			Caught.Add(Other);
			if (USOCombatStatics::ApplyDamage(User, Other, Damage, false) > 0.0f && !Other->IsDead() && Force > 0.0f)
			{
				Other->LaunchCharacter(To.GetSafeNormal2D() * Force * 0.4f + FVector(0.0f, 0.0f, Force), true, true);
			}
		}
	}
}
