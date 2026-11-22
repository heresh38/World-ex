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
	DisplayName = NSLOCTEXT("SO", "StalkerArmed", "Veteran");
	// the Veteran's colours: gunmetal plates with a blue cast, a blue-black lacquer, ice-blue lights
	PlateTint = FLinearColor(0.68f, 0.84f, 1.18f);
	LacquerTint = FLinearColor(0.80f, 0.96f, 1.40f);
	LightTint = FLinearColor(0.40f, 0.85f, 1.00f);
	SOAltered::Configure(this, TEXT("Sarketh"), 36.0f, 104.0f);   // (a Sarketh: the owner's design, tools/blender/skr)
	VoicePrefix = TEXT("stalker");
	WeaponArchetype = TEXT("auto");
	WeaponDamageScale = 0.3f;
	AimError = 60.0f;
	PreferredRange = 1500.0f;
	bUsesCover = true;
	BloodColor = FLinearColor(0.32f, 0.1f, 0.55f);
}
