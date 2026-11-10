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

// The armed stalker.
ASOArmedStalker::ASOArmedStalker(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	SpeciesId = TEXT("stalker");
	DisplayName = NSLOCTEXT("SO", "StalkerArmed", "Stalker");
	VoicePrefix = TEXT("stalker");
	WeaponArchetype = TEXT("auto");
	WeaponDamageScale = 0.3f;
	AimError = 60.0f;
	PreferredRange = 1500.0f;
	bUsesCover = true;
	BloodColor = FLinearColor(0.32f, 0.1f, 0.55f);
}
