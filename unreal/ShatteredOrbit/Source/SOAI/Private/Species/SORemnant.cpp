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

// The Remnant.
ASORemnant::ASORemnant(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	SpeciesId = TEXT("remnant");
	SOAltered::Configure(this, TEXT("Remnant"), 34.0f, 90.0f);
	DisplayName = NSLOCTEXT("SO", "Remnant", "Remnant");
	VoicePrefix = TEXT("remnant");
	WeaponArchetype = TEXT("smg");
	WeaponDamageScale = 0.3f;
	AimError = 95.0f;
	PreferredRange = 800.0f;
	bUsesCover = false;
	BurstTime = FVector2D(0.4f, 0.9f);
	BurstPause = FVector2D(0.5f, 1.1f);
	StartMaxHealth = 80.0f;
	WalkSpeed = 230.0f;
	RunSpeed = 650.0f;
	MeleeDamage = 11.0f;
	MeleeRange = 160.0f;
	MeleeCooldown = 0.75f;
	MeleeWindup = 0.26f;
	LungeSpeed = 620.0f;
	CorpseLifeSpan = 5.0f;
}
