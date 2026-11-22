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

// The Bulwark.
ASOBulwark::ASOBulwark(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	SpeciesId = TEXT("bulwark");
	// (a Warden: the heavy Sarketh, a shield on its forearm, a little bigger in its powered armour; the old husk is gone)
	SOAltered::Configure(this, TEXT("SarkethHeavy"), 40.0f, 104.0f, 1.08f);
	VoicePrefix = TEXT("bulwark");
	WeaponArchetype = TEXT("shotgun");
	WeaponDamageScale = 0.2f;
	AimError = 70.0f;
	PreferredRange = 650.0f;
	bUsesCover = false;
	BurstTime = FVector2D(0.1f, 0.2f);
	BurstPause = FVector2D(0.9f, 1.4f);
	DisplayName = NSLOCTEXT("SO", "Bulwark", "Warden");
	StartMaxHealth = 620.0f;
	WalkSpeed = 150.0f;
	RunSpeed = 300.0f;
	MeleeDamage = 32.0f;
	MeleeRange = 230.0f;
	MeleeCooldown = 1.7f;
	MeleeWindup = 0.55f;
	LungeSpeed = 260.0f;
	ActionClips = { TEXT("Slam") };
	KitId = TEXT("bulwark");
	FlinchScale = 0.45f; // (a heavy body: a hit barely moves it)
}

float ASOBulwark::ScaleIncomingDamage(float Amount, const AActor* Source, bool bCrit) const
{
	if (!Source)
	{
		return Amount;
	}
	const bool bFront = PlateFaces(Source->GetActorLocation());
	const float Through = bFront ? Amount * FMath::Min(bCrit ? FrontDamageScale * 2.0f : FrontDamageScale, 1.0f) : Amount;
	AbsorbedByArmour = Amount - Through;                          // (what the plate took: it still shakes the arm behind it)
	return Super::ScaleIncomingDamage(Through, Source, bCrit);
}

bool ASOBulwark::PlateFaces(const FVector& From) const
{
	// A gunner's plate comes down to steady the gun: while it holds the trigger it is open from the front too. And a
	// Bulwark that reels has dropped its guard: that is what hammering the plate is for.
	const FVector To = (From - GetActorLocation()).GetSafeNormal2D();
	return FVector::DotProduct(GetActorForwardVector().GetSafeNormal2D(), To) > 0.4f && !(bSuppressor && IsFiring()) && !HasStatus(SOTags::Status_Stagger);
}

bool ASOBulwark::ThinkCombat(ASOEnemyAIController* AI, ASOCombatCharacter* Target)
{
	if (IsAbilityActive(ESOAbilitySlot::Class))
	{
		return true; // winding up: it stands and commits
	}
	const FSOAbilityGrant* Slam = GetAbilitySet() ? GetAbilitySet()->Find(ESOAbilitySlot::Class) : nullptr;
	int32 Charges = 0, MaxCharges = 0;
	float Left = 0.0f, Cooldown = 0.0f;
	if (Slam && !IsAttacking() && DistanceTo(Target) < Slam->Range * 0.75f
		&& GetAbilityState(ESOAbilitySlot::Class, Charges, MaxCharges, Left, Cooldown) && Charges > 0)
	{
		SOAltered::FaceToward(this, Target->GetActorLocation(), 0.0f, 0.0f);
		if (ActivateSlot(ESOAbilitySlot::Class))
		{
			AI->StopMovement();
			return true;
		}
	}
	return false;
}

void ASOBulwark::OnAbilityWindUp(ESOAbilitySlot Slot)
{
	Super::OnAbilityWindUp(Slot);
	if (Slot == ESOAbilitySlot::Class)
	{
		PlayAction(TEXT("Slam"), 1.0f); // the arm going up is the warning
	}
}

void ASOBulwark::OnAbilityUsed(ESOAbilitySlot Slot)
{
	Super::OnAbilityUsed(Slot);
	if (HasAuthority() && Slot == ESOAbilitySlot::Class)
	{
		USOCombatStatics::ReportNoise(this, GetActorLocation(), this, 2500.0f); // every creature in earshot knows
	}
}
