#include "SOPlayerController.h"
#include "SOCombatTypes.h"
#include "SOEnemy.h"
#include "SOSpecies.h"
#include "SOAreaSubsystem.h"

#include "SOLocomotionAnimInstance.h"

#include "EnhancedInputSubsystems.h"
#include "Engine/LocalPlayer.h"
#include "InputMappingContext.h"
#include "EngineUtils.h"
#include "Camera/CameraActor.h"
#include "Camera/CameraComponent.h"
#include "SOCharacter.h"
#include "SOGunRigComponent.h"
#include "SOViewmodelComponent.h"
#include "SOEnemy.h"
#include "SOAltered.h"
#include "NavigationSystem.h"
#include "NavigationPath.h"
#include "Components/CapsuleComponent.h"
#include "SOOperation.h"
#include "SOOperationBarrier.h"
#include "SOEnemyAIController.h"
#include "SOLog.h"
#include "SOWeapon.h"
#include "SOInventoryComponent.h"
#include "SOLootActors.h"
#include "SOLootLibrary.h"
#include "SOFxSubsystem.h"
#include "SOWeaponData.h"
#include "SOHUD.h"
#include "SOTimeOfDaySubsystem.h"
#include "SOWeather.h"
#include "SOCombatStatics.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "SOInventoryWidget.h"
#include "TimerManager.h"
#include "UnrealClient.h"
#include "Kismet/KismetSystemLibrary.h"
#include "Engine/GameViewportClient.h"
#include "RHI.h"
#include "UnrealEngine.h"
#include "Engine/StaticMeshActor.h"
#include "Framework/Application/SlateApplication.h"
#include "Engine/CollisionProfile.h"
#include "Kismet/GameplayStatics.h"
#include "SOCharacterMovementComponent.h"

ASOPlayerController::ASOPlayerController()
{
	DefaultMappingContext = TSoftObjectPtr<UInputMappingContext>(FSoftObjectPath(TEXT("/Game/Input/IMC_Default.IMC_Default")));
}

void ASOPlayerController::BeginPlay()
{
	Super::BeginPlay();
	if (IsLocalController())
	{
		AddDefaultMappingContext();
		SetInputMode(FInputModeGameOnly());
		SetShowMouseCursor(false);
		// Leaving the window (the Windows key, alt-tab) and coming back: no key stays held, and the game takes the
		// mouse again by itself instead of waiting for a click.
		if (FSlateApplication::IsInitialized())
		{
			ActivationHandle = FSlateApplication::Get().OnApplicationActivationStateChanged().AddUObject(this, &ASOPlayerController::OnWindowActivation);
		}
		DevBegin(); // (developer tools: nothing in a shipping build)
	}
}

void ASOPlayerController::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	if (ActivationHandle.IsValid() && FSlateApplication::IsInitialized())
	{
		FSlateApplication::Get().OnApplicationActivationStateChanged().Remove(ActivationHandle);
	}
	Super::EndPlay(EndPlayReason);
}

void ASOPlayerController::OnWindowActivation(bool bActive)
{
	FlushPressedKeys();
	if (bActive && !bShowMouseCursor)
	{
		SetInputMode(FInputModeGameOnly());
		FSlateApplication::Get().SetAllUserFocusToGameViewport();
	}
}

bool ASOPlayerController::AddDefaultMappingContext()
{
	UInputMappingContext* Context = DefaultMappingContext.LoadSynchronous();
	if (!Context)
	{
		UE_LOG(LogShatteredOrbit, Warning, TEXT("SOPlayerController: %s is missing; run Content/Python/setup_input.py"), *DefaultMappingContext.ToString());
		return false;
	}
	const ULocalPlayer* LocalPlayer = GetLocalPlayer();
	UEnhancedInputLocalPlayerSubsystem* Subsystem = LocalPlayer ? LocalPlayer->GetSubsystem<UEnhancedInputLocalPlayerSubsystem>() : nullptr;
	if (!Subsystem)
	{
		return false;
	}
	Subsystem->AddMappingContext(Context, DefaultMappingPriority);
	return true;
}

void ASOPlayerController::PlayerTick(float DeltaTime)
{
	Super::PlayerTick(DeltaTime);
	DevTick(DeltaTime); // the developer tools' share of the tick (nothing in a shipping build)
}
