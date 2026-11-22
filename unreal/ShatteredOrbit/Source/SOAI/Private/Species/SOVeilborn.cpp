#include "SOAltered.h"
#include "SOCue.h"

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
	SOAltered::Configure(this, TEXT("SarkethFemale"), 34.0f, 98.0f);   // (a Sarketh, a Speaker: the owner's design)
	VoicePrefix = TEXT("veilborn");
	// the Speaker's colours: verdigris plates, a green-black lacquer, teal lights (the signals officer)
	PlateTint = FLinearColor(0.70f, 1.10f, 0.96f);
	LacquerTint = FLinearColor(0.80f, 1.32f, 1.14f);
	LightTint = FLinearColor(0.30f, 1.00f, 0.75f);
	WeaponArchetype = TEXT("scout");
	WeaponDamageScale = 0.4f;
	AimError = 40.0f;
	PreferredRange = 2200.0f;
	BurstTime = FVector2D(0.2f, 0.5f);
	BurstPause = FVector2D(1.0f, 2.0f);
	KitId = TEXT("veilborn");
	DisplayName = NSLOCTEXT("SO", "Veilborn", "Speaker");
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
				USOCue::Blast(this, Here, FVector::UpVector, 120.0f, USOFxSubsystem::EBlast::Zap, SOAltered::VoidColor);
				USOCue::Blast(this, To, FVector::UpVector, 120.0f, USOFxSubsystem::EBlast::Zap, SOAltered::VoidColor, 0.05f);
			}
			USOCue::Sound(this, TEXT("bolt_impact"), To, 1.0f, 0.1f, ESOSoundRange::Mid);
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
	const bool bCasting = IsAbilityActive(ESOAbilitySlot::Grenade);
	if (T >= NextBlink && !bCasting && (Dist < MinRange || HealthAtBlink - Health > 45.0f))
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
	if (bCasting)
	{
		SetWantsFire(false);
		return true; // mid-cast: stands
	}
	// now and then, with a clear line, a void bolt instead of the rifle (the kit says what it is; this says when)
	int32 Charges = 0, MaxCharges = 0;
	float Left = 0.0f, Cooldown = 0.0f;
	if (T >= NextCast && HasLineOfFire(Target) && Dist < PreferredRange * 1.5f
		&& GetAbilityState(ESOAbilitySlot::Grenade, Charges, MaxCharges, Left, Cooldown) && Charges > 0)
	{
		SetAbilityTarget(Target);
		if (ActivateSlot(ESOAbilitySlot::Grenade))
		{
			AI->StopMovement();
			SetWantsFire(false);
			NextCast = T + FMath::FRandRange(0.0f, 0.35f) * Cooldown; // not on the dot every time
			return true;
		}
	}
	return Super::ThinkCombat(AI, Target); // whatever else its kit holds, by rule; otherwise it fights like the rest: cover, peek, rifle
}

void ASOVeilborn::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (IsDead())
	{
		return;
	}
	if (AActor* T = GetAbilityTarget(); T && IsAbilityActive(ESOAbilitySlot::Grenade))
	{
		SOAltered::FaceToward(this, T->GetActorLocation(), DeltaSeconds, 10.0f); // it turns with its target through the cast
	}
}

void ASOVeilborn::OnAbilityWindUp(ESOAbilitySlot Slot)
{
	Super::OnAbilityWindUp(Slot);
	if (Slot == ESOAbilitySlot::Grenade)
	{
		PlayAction(TEXT("Cast"), 1.0f); // the hands coming together is the warning
	}
}

void ASOVeilborn::OnAbilityUsed(ESOAbilitySlot Slot)
{
	Super::OnAbilityUsed(Slot);
	if (HasAuthority() && Slot == ESOAbilitySlot::Grenade)
	{
		++BoltsFired;
	}
}

