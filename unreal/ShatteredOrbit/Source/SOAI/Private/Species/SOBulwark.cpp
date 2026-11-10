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

// The Bulwark.
ASOBulwark::ASOBulwark(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	SpeciesId = TEXT("bulwark");
	SOAltered::Configure(this, TEXT("Bulwark"), 44.0f, 108.0f);
	VoicePrefix = TEXT("bulwark");
	WeaponArchetype = TEXT("shotgun");
	WeaponDamageScale = 0.2f;
	AimError = 70.0f;
	PreferredRange = 650.0f;
	bUsesCover = false;
	BurstTime = FVector2D(0.1f, 0.2f);
	BurstPause = FVector2D(0.9f, 1.4f);
	DisplayName = NSLOCTEXT("SO", "Bulwark", "Bulwark");
	StartMaxHealth = 620.0f;
	WalkSpeed = 150.0f;
	RunSpeed = 300.0f;
	MeleeDamage = 32.0f;
	MeleeRange = 230.0f;
	MeleeCooldown = 1.7f;
	MeleeWindup = 0.55f;
	LungeSpeed = 260.0f;
	ActionClips = { TEXT("Slam") };
}

float ASOBulwark::ScaleIncomingDamage(float Amount, const AActor* Source, bool bCrit) const
{
	if (!Source)
	{
		return Amount;
	}
	const FVector To = (Source->GetActorLocation() - GetActorLocation()).GetSafeNormal2D();
	const bool bFront = FVector::DotProduct(GetActorForwardVector().GetSafeNormal2D(), To) > 0.4f;
	return Super::ScaleIncomingDamage(bFront ? Amount * (bCrit ? FrontDamageScale * 2.0f : FrontDamageScale) : Amount, Source, bCrit);
}

bool ASOBulwark::ThinkCombat(ASOEnemyAIController* AI, ASOCombatCharacter* Target)
{
	const float T = SOAltered::Now(this);
	if (PendingSlam >= 0.0f)
	{
		return true;
	}
	if (T >= NextSlam && !IsAttacking() && DistanceTo(Target) < SlamRadius * 0.75f)
	{
		AI->StopMovement();
		SOAltered::FaceToward(this, Target->GetActorLocation(), 0.0f, 0.0f);
		PlayAction(TEXT("Slam"), 1.0f);
		PendingSlam = T + 0.72f;
		NextSlam = T + SlamCooldown;
		return true;
	}
	return false;
}

void ASOBulwark::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (!HasAuthority() || IsDead() || PendingSlam < 0.0f || SOAltered::Now(this) < PendingSlam)
	{
		return;
	}
	PendingSlam = -1.0f;
	const FVector Impact = GetActorLocation() + GetActorForwardVector() * 140.0f - FVector(0, 0, GetCapsuleComponent()->GetScaledCapsuleHalfHeight() - 10.0f);
	DamageAround(Impact, SlamRadius, SlamDamage, 900.0f);
	if (USOFxSubsystem* Fx = GetWorld()->GetSubsystem<USOFxSubsystem>())
	{
		Fx->Blast(Impact, FVector::UpVector, SlamRadius * 0.6f, USOFxSubsystem::EBlast::Zap, SOAltered::VoidColor);
	}
	USOSoundLibrary::PlayAt(this, TEXT("rocket_explode"), Impact, 0.9f, 0.1f, ESOSoundRange::Far);
	USOCombatStatics::ReportNoise(this, Impact, this, 2500.0f);
}
