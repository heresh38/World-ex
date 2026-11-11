#include "SOAltered.h"

#include "SOAlteredCommon.h"

#include "Components/CapsuleComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Materials/MaterialInterface.h"
#include "NavigationSystem.h"
#include "SOCombatCharacter.h"
#include "SOCombatStatics.h"
#include "SOEnemyAIController.h"
#include "SOFxSubsystem.h"
#include "SOLocomotionAnimInstance.h"
#include "UObject/ConstructorHelpers.h"
#include "SOSound.h"

// The Veilborn.
ASOVeilborn::ASOVeilborn(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	SpeciesId = TEXT("veilborn");
	SOAltered::Configure(this, TEXT("Veilborn"), 34.0f, 90.0f);
	VoicePrefix = TEXT("veilborn");
	WeaponArchetype = TEXT("scout");
	WeaponDamageScale = 0.4f;
	AimError = 40.0f;
	PreferredRange = 2200.0f;
	BurstTime = FVector2D(0.2f, 0.5f);
	BurstPause = FVector2D(1.0f, 2.0f);
	CastCooldown = 9.0f;
	DisplayName = NSLOCTEXT("SO", "Veilborn", "Veilborn");
	StartMaxHealth = 130.0f;
	WalkSpeed = 180.0f;
	RunSpeed = 420.0f;
	MeleeDamage = 14.0f;
	MeleeRange = 150.0f;
	SightRange = 5000.0f;
	ActionClips = { TEXT("Cast"), TEXT("Blink") };
}

bool ASOVeilborn::Blink(const FVector& Away)
{
	UWorld* World = GetWorld();
	const FVector Here = GetActorLocation();
	const float Side = FMath::RandBool() ? 1.0f : -1.0f;
	UNavigationSystemV1* Nav = FNavigationSystem::GetCurrent<UNavigationSystemV1>(World);
	for (int32 Try = 0; Try < 4; ++Try)
	{
		const FVector Dir = Away.GetSafeNormal2D().RotateAngleAxis(Side * (55.0f + 25.0f * Try) * (Try % 2 ? -1.0f : 1.0f), FVector::UpVector);
		FVector To = Here + Dir * FMath::FRandRange(700.0f, 1000.0f);
		FNavLocation OnNav;
		if (Nav && Nav->GetDefaultNavDataInstance(FNavigationSystem::DontCreate))
		{
			if (!Nav->ProjectPointToNavigation(To, OnNav, FVector(300.0f, 300.0f, 600.0f)))
			{
				continue;
			}
			To = OnNav.Location + FVector(0, 0, GetCapsuleComponent()->GetScaledCapsuleHalfHeight());
		}
		if (FitsAt(To) && TeleportTo(To, GetActorRotation(), false, true))      // never into a wall
		{
			if (USOFxSubsystem* Fx = World->GetSubsystem<USOFxSubsystem>())
			{
				Fx->Blast(Here, FVector::UpVector, 120.0f, USOFxSubsystem::EBlast::Zap, SOAltered::VoidColor);
				Fx->Blast(To, FVector::UpVector, 120.0f, USOFxSubsystem::EBlast::Zap, SOAltered::VoidColor, 0.05f);
			}
			USOSoundLibrary::PlayAt(this, TEXT("bolt_impact"), To, 1.0f, 0.1f, ESOSoundRange::Mid);
			PlayAction(TEXT("Blink"), 1.4f);
			++Blinks;
			return true;
		}
	}
	return false;
}

bool ASOVeilborn::ThinkCombat(ASOEnemyAIController* AI, ASOCombatCharacter* Target)
{
	const float T = SOAltered::Now(this);
	const float Dist = DistanceTo(Target);
	const float Health = GetHealth();
	if (HealthAtBlink < 0.0f)
	{
		HealthAtBlink = Health;
	}
	// pressed or hurt badly: blink aside
	if (T >= NextBlink && PendingCast < 0.0f && (Dist < MinRange || HealthAtBlink - Health > 45.0f))
	{
		NextBlink = T + BlinkCooldown;
		HealthAtBlink = Health;
		AI->StopMovement();
		if (Blink(GetActorLocation() - Target->GetActorLocation()))
		{
			NextCast = FMath::Max(NextCast, T + 0.6f);
			return true;
		}
	}
	if (PendingCast >= 0.0f)
	{
		SetWantsFire(false);
		return true; // mid-cast: stands
	}
	// now and then, with a clear line, a void bolt instead of the rifle
	if (T >= NextCast && HasLineOfFire(Target) && Dist < PreferredRange * 1.5f)
	{
		AI->StopMovement();
		SetWantsFire(false);
		CastTarget = Target;
		PlayAction(TEXT("Cast"), 1.0f);
		PendingCast = T + 0.55f;
		NextCast = T + CastCooldown * FMath::FRandRange(0.85f, 1.2f);
		return true;
	}
	return false; // otherwise it fights like the rest: cover, peek, rifle
}

void ASOVeilborn::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (IsDead())
	{
		return;
	}
	if (AActor* T = CastTarget.Get(); T && PendingCast >= 0.0f)
	{
		SOAltered::FaceToward(this, T->GetActorLocation(), DeltaSeconds, 10.0f);
	}
	if (HasAuthority() && PendingCast >= 0.0f && SOAltered::Now(this) >= PendingCast)
	{
		PendingCast = -1.0f;
		if (AActor* T = CastTarget.Get())
		{
			const FVector Hands = GetActorLocation() + GetActorForwardVector() * 70.0f + FVector(0, 0, 55.0f);
			SOAltered::FireBolt(this, Hands, T, BoltDamage, 2400.0f, 1.5f);
			++BoltsFired;
		}
	}
}
