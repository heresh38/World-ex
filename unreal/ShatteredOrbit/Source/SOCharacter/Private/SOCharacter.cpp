#include "SOCharacter.h"

#include "Camera/CameraComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "EnhancedInputComponent.h"
#include "Engine/World.h"
#include "GameFramework/Controller.h"
#include "GameFramework/SpringArmComponent.h"
#include "InputAction.h"
#include "InputActionValue.h"
#include "SOCharacterMovementComponent.h"
#include "SOGameUserSettings.h"
#include "SOLog.h"
#include "SOLookComponent.h"

namespace SOInputPaths
{
	static const TCHAR* Move = TEXT("/Game/Input/IA_Move.IA_Move");
	static const TCHAR* Look = TEXT("/Game/Input/IA_Look.IA_Look");
	static const TCHAR* LookGamepad = TEXT("/Game/Input/IA_LookGamepad.IA_LookGamepad");
	static const TCHAR* Jump = TEXT("/Game/Input/IA_Jump.IA_Jump");
	static const TCHAR* Sprint = TEXT("/Game/Input/IA_Sprint.IA_Sprint");
	static const TCHAR* Crouch = TEXT("/Game/Input/IA_Crouch.IA_Crouch");
	static const TCHAR* ToggleView = TEXT("/Game/Input/IA_ToggleView.IA_ToggleView");
	static const TCHAR* Interact = TEXT("/Game/Input/IA_Interact.IA_Interact");
	static const TCHAR* Fire = TEXT("/Game/Input/IA_Fire.IA_Fire");
	static const TCHAR* Aim = TEXT("/Game/Input/IA_Aim.IA_Aim");
	static const TCHAR* Reload = TEXT("/Game/Input/IA_Reload.IA_Reload");
}

ASOCharacter::ASOCharacter(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer.SetDefaultSubobjectClass<USOCharacterMovementComponent>(ACharacter::CharacterMovementComponentName))
{
	PrimaryActorTick.bCanEverTick = true;

	UCapsuleComponent* Capsule = GetCapsuleComponent();
	Capsule->InitCapsuleSize(34.0f, 90.0f);

	// Shooter: the body yaws with the camera.
	bUseControllerRotationYaw = true;
	bUseControllerRotationPitch = false;
	bUseControllerRotationRoll = false;
	JumpMaxCount = 1;
	JumpMaxHoldTime = 0.0f;

	EyeOffset = StandingEyeHeight - Capsule->GetUnscaledCapsuleHalfHeight();
	BaseEyeHeight = EyeOffset;
	CrouchedEyeHeight = CrouchEyeHeight - 58.0f;

	FirstPersonCamera = CreateDefaultSubobject<UCameraComponent>(TEXT("FirstPersonCamera"));
	FirstPersonCamera->SetupAttachment(Capsule);
	FirstPersonCamera->SetRelativeLocation(FVector(0.0f, 0.0f, EyeOffset));
	FirstPersonCamera->bUsePawnControlRotation = true;
	FirstPersonCamera->SetFieldOfView(90.0f);
	FirstPersonCamera->bEnableFirstPersonFieldOfView = true;
	FirstPersonCamera->FirstPersonFieldOfView = ViewmodelFov;

	FirstPersonArms = CreateDefaultSubobject<USkeletalMeshComponent>(TEXT("FirstPersonArms"));
	FirstPersonArms->SetupAttachment(FirstPersonCamera);
	FirstPersonArms->SetOnlyOwnerSee(true);
	FirstPersonArms->SetCastShadow(false);
	FirstPersonArms->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	FirstPersonArms->SetFirstPersonPrimitiveType(EFirstPersonPrimitiveType::FirstPerson);
	FirstPersonArms->SetRelativeLocation(FVector(-4.0f, 0.0f, -160.0f));

	// The full body: hidden from the owner in first person but it still casts the player's shadow.
	USkeletalMeshComponent* Body = GetMesh();
	Body->SetRelativeLocation(FVector(0.0f, 0.0f, -Capsule->GetUnscaledCapsuleHalfHeight()));
	Body->SetRelativeRotation(FRotator(0.0f, -90.0f, 0.0f)); // Blender -Y forward -> UE +X
	Body->SetCastHiddenShadow(true);

	ThirdPersonBoom = CreateDefaultSubobject<USpringArmComponent>(TEXT("ThirdPersonBoom"));
	ThirdPersonBoom->SetupAttachment(Capsule);
	ThirdPersonBoom->SetRelativeLocation(FVector(0.0f, 0.0f, 55.0f));
	ThirdPersonBoom->TargetArmLength = 320.0f;
	ThirdPersonBoom->SocketOffset = FVector(0.0f, 55.0f, 15.0f);
	ThirdPersonBoom->bUsePawnControlRotation = true;
	ThirdPersonBoom->bDoCollisionTest = true;
	ThirdPersonBoom->ProbeSize = 14.0f;
	ThirdPersonBoom->ProbeChannel = ECC_Camera;
	ThirdPersonBoom->bEnableCameraLag = true;
	ThirdPersonBoom->CameraLagSpeed = 18.0f;

	ThirdPersonCamera = CreateDefaultSubobject<UCameraComponent>(TEXT("ThirdPersonCamera"));
	ThirdPersonCamera->SetupAttachment(ThirdPersonBoom, USpringArmComponent::SocketName);
	ThirdPersonCamera->bUsePawnControlRotation = false;
	ThirdPersonCamera->SetAutoActivate(false);

	Look = CreateDefaultSubobject<USOLookComponent>(TEXT("Look"));

	MoveAction = TSoftObjectPtr<UInputAction>(FSoftObjectPath(SOInputPaths::Move));
	LookAction = TSoftObjectPtr<UInputAction>(FSoftObjectPath(SOInputPaths::Look));
	LookGamepadAction = TSoftObjectPtr<UInputAction>(FSoftObjectPath(SOInputPaths::LookGamepad));
	JumpAction = TSoftObjectPtr<UInputAction>(FSoftObjectPath(SOInputPaths::Jump));
	SprintAction = TSoftObjectPtr<UInputAction>(FSoftObjectPath(SOInputPaths::Sprint));
	CrouchAction = TSoftObjectPtr<UInputAction>(FSoftObjectPath(SOInputPaths::Crouch));
	ToggleViewAction = TSoftObjectPtr<UInputAction>(FSoftObjectPath(SOInputPaths::ToggleView));
	InteractAction = TSoftObjectPtr<UInputAction>(FSoftObjectPath(SOInputPaths::Interact));
	FireAction = TSoftObjectPtr<UInputAction>(FSoftObjectPath(SOInputPaths::Fire));
	AimAction = TSoftObjectPtr<UInputAction>(FSoftObjectPath(SOInputPaths::Aim));
	ReloadAction = TSoftObjectPtr<UInputAction>(FSoftObjectPath(SOInputPaths::Reload));
}

USOCharacterMovementComponent* ASOCharacter::GetSOMovement() const
{
	return Cast<USOCharacterMovementComponent>(GetCharacterMovement());
}

void ASOCharacter::BeginPlay()
{
	Super::BeginPlay();
	CurrentFov = GetHipFov();
	ApplyViewMode();
}

float ASOCharacter::GetHipFov() const
{
	const USOGameUserSettings* Settings = USOGameUserSettings::Get();
	return Settings ? Settings->FieldOfView : 90.0f;
}

float ASOCharacter::GetTargetEyeOffset() const
{
	const UCapsuleComponent* Capsule = GetCapsuleComponent();
	const float HalfHeight = Capsule->GetUnscaledCapsuleHalfHeight();
	return (bIsCrouched ? CrouchEyeHeight : StandingEyeHeight) - HalfHeight;
}

void ASOCharacter::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	// Eye height eases across crouch / slide transitions.
	EyeOffset = FMath::FInterpTo(EyeOffset, GetTargetEyeOffset(), DeltaSeconds, EyeHeightInterpSpeed);
	FirstPersonCamera->SetRelativeLocation(FVector(0.0f, 0.0f, EyeOffset));

	// Aim zoom.
	const float HipFov = GetHipFov();
	const float TargetFov = bAiming ? HipFov * AimFovScale : HipFov;
	CurrentFov = FMath::FInterpTo(CurrentFov, TargetFov, DeltaSeconds, FovInterpSpeed);
	FirstPersonCamera->SetFieldOfView(CurrentFov);
	ThirdPersonCamera->SetFieldOfView(CurrentFov);
	Look->SetAim(bAiming, HipFov, CurrentFov);

	// A latched (tapped) sprint ends once you stop pushing forward; a latched crouch follows the movement state.
	if (USOCharacterMovementComponent* Move = GetSOMovement())
	{
		if (bSprintLatched)
		{
			const FVector Input = Move->GetCurrentAcceleration().GetSafeNormal2D();
			if (FVector::DotProduct(Input, GetActorForwardVector().GetSafeNormal2D()) < 0.5f || bIsCrouched)
			{
				bSprintLatched = false;
				Move->SetWantsToSprint(false);
			}
		}
		if (bCrouchLatched && !Move->bWantsToCrouch)
		{
			bCrouchLatched = false;
		}
	}
}

void ASOCharacter::SetupPlayerInputComponent(UInputComponent* PlayerInputComponent)
{
	Super::SetupPlayerInputComponent(PlayerInputComponent);

	UEnhancedInputComponent* Input = Cast<UEnhancedInputComponent>(PlayerInputComponent);
	if (!Input)
	{
		UE_LOG(LogShatteredOrbit, Error, TEXT("SOCharacter: the input component is not an UEnhancedInputComponent (check DefaultInput.ini)"));
		return;
	}

	int32 Missing = 0;
	auto Load = [&Missing](const TSoftObjectPtr<UInputAction>& Soft) -> UInputAction*
	{
		UInputAction* Action = Soft.LoadSynchronous();
		if (!Action)
		{
			++Missing;
			UE_LOG(LogShatteredOrbit, Warning, TEXT("SOCharacter: input action %s is missing"), *Soft.ToString());
		}
		return Action;
	};

	if (UInputAction* A = Load(MoveAction)) { Input->BindAction(A, ETriggerEvent::Triggered, this, &ASOCharacter::HandleMove); }
	if (UInputAction* A = Load(LookAction)) { Input->BindAction(A, ETriggerEvent::Triggered, this, &ASOCharacter::HandleLook); }
	if (UInputAction* A = Load(LookGamepadAction)) { Input->BindAction(A, ETriggerEvent::Triggered, this, &ASOCharacter::HandleLookGamepad); }
	if (UInputAction* A = Load(JumpAction))
	{
		Input->BindAction(A, ETriggerEvent::Started, this, &ASOCharacter::HandleJumpPressed);
		Input->BindAction(A, ETriggerEvent::Completed, this, &ASOCharacter::HandleJumpReleased);
	}
	if (UInputAction* A = Load(SprintAction))
	{
		Input->BindAction(A, ETriggerEvent::Started, this, &ASOCharacter::HandleSprintPressed);
		Input->BindAction(A, ETriggerEvent::Completed, this, &ASOCharacter::HandleSprintReleased);
	}
	if (UInputAction* A = Load(CrouchAction))
	{
		Input->BindAction(A, ETriggerEvent::Started, this, &ASOCharacter::HandleCrouchPressed);
		Input->BindAction(A, ETriggerEvent::Completed, this, &ASOCharacter::HandleCrouchReleased);
	}
	if (UInputAction* A = Load(ToggleViewAction)) { Input->BindAction(A, ETriggerEvent::Started, this, &ASOCharacter::HandleToggleView); }
	if (UInputAction* A = Load(InteractAction)) { Input->BindAction(A, ETriggerEvent::Started, this, &ASOCharacter::HandleInteract); }
	if (UInputAction* A = Load(FireAction))
	{
		Input->BindAction(A, ETriggerEvent::Started, this, &ASOCharacter::HandleFirePressed);
		Input->BindAction(A, ETriggerEvent::Completed, this, &ASOCharacter::HandleFireReleased);
	}
	if (UInputAction* A = Load(AimAction))
	{
		Input->BindAction(A, ETriggerEvent::Started, this, &ASOCharacter::HandleAimPressed);
		Input->BindAction(A, ETriggerEvent::Completed, this, &ASOCharacter::HandleAimReleased);
	}
	if (UInputAction* A = Load(ReloadAction)) { Input->BindAction(A, ETriggerEvent::Started, this, &ASOCharacter::HandleReload); }

	if (Missing > 0)
	{
		UE_LOG(LogShatteredOrbit, Warning, TEXT("SOCharacter: %d input actions missing; run Content/Python/setup_input.py"), Missing);
	}
}

// --- Input -------------------------------------------------------------------------------------

void ASOCharacter::HandleMove(const FInputActionValue& Value)
{
	const FVector2D Axis = Value.Get<FVector2D>();
	if (!Controller || Axis.IsNearlyZero())
	{
		return;
	}
	const FRotator Yaw(0.0f, Controller->GetControlRotation().Yaw, 0.0f);
	const FRotationMatrix Basis(Yaw);
	AddMovementInput(Basis.GetUnitAxis(EAxis::X), Axis.Y);
	AddMovementInput(Basis.GetUnitAxis(EAxis::Y), Axis.X);
}

void ASOCharacter::HandleLook(const FInputActionValue& Value)
{
	Look->AddMouseInput(Value.Get<FVector2D>());
}

void ASOCharacter::HandleLookGamepad(const FInputActionValue& Value)
{
	Look->AddGamepadInput(Value.Get<FVector2D>());
}

void ASOCharacter::HandleJumpPressed()
{
	if (USOCharacterMovementComponent* Move = GetSOMovement())
	{
		Move->SetWantsToMantle(true);
		BufferedJumpTime = CanJump() ? -1.0f : GetWorld()->GetTimeSeconds();
	}
	Jump();
}

void ASOCharacter::HandleJumpReleased()
{
	if (USOCharacterMovementComponent* Move = GetSOMovement())
	{
		Move->SetWantsToMantle(false);
	}
	StopJumping();
}

void ASOCharacter::HandleSprintPressed()
{
	USOCharacterMovementComponent* Move = GetSOMovement();
	if (!Move)
	{
		return;
	}
	if (bSprintLatched)
	{
		bSprintLatched = false;
		Move->SetWantsToSprint(false);
		return;
	}
	if (bIsCrouched && !Move->IsSliding())
	{
		bCrouchLatched = false;
		UnCrouch();
	}
	SprintPressTime = GetWorld()->GetTimeSeconds();
	Move->SetWantsToSprint(true);
}

void ASOCharacter::HandleSprintReleased()
{
	USOCharacterMovementComponent* Move = GetSOMovement();
	if (!Move || bSprintLatched)
	{
		return;
	}
	const float Held = GetWorld()->GetTimeSeconds() - SprintPressTime;
	if (Held < TapToToggleTime)
	{
		bSprintLatched = true; // tap: keep sprinting until forward input stops
	}
	else
	{
		Move->SetWantsToSprint(false);
	}
}

void ASOCharacter::HandleCrouchPressed()
{
	if (bCrouchLatched)
	{
		bCrouchLatched = false;
		UnCrouch();
		return;
	}
	CrouchPressTime = GetWorld()->GetTimeSeconds();
	Crouch();
}

void ASOCharacter::HandleCrouchReleased()
{
	if (bCrouchLatched)
	{
		return;
	}
	const float Held = GetWorld()->GetTimeSeconds() - CrouchPressTime;
	if (Held < TapToToggleTime)
	{
		bCrouchLatched = true; // tap: stay crouched
	}
	else
	{
		UnCrouch();
	}
}

void ASOCharacter::HandleToggleView()
{
	ToggleViewMode();
}

void ASOCharacter::HandleInteract()
{
	UE_LOG(LogShatteredOrbit, Log, TEXT("Interact"));
}

void ASOCharacter::HandleFirePressed()
{
	UE_LOG(LogShatteredOrbit, Log, TEXT("Fire pressed (combat arrives in stage 3)"));
}

void ASOCharacter::HandleFireReleased()
{
	UE_LOG(LogShatteredOrbit, Verbose, TEXT("Fire released"));
}

void ASOCharacter::HandleAimPressed()
{
	bAiming = true;
	UE_LOG(LogShatteredOrbit, Log, TEXT("Aim on"));
}

void ASOCharacter::HandleAimReleased()
{
	bAiming = false;
	UE_LOG(LogShatteredOrbit, Log, TEXT("Aim off"));
}

void ASOCharacter::HandleReload()
{
	UE_LOG(LogShatteredOrbit, Log, TEXT("Reload (combat arrives in stage 3)"));
}

// --- Movement hooks ----------------------------------------------------------------------------

void ASOCharacter::Landed(const FHitResult& Hit)
{
	Super::Landed(Hit);

	const USOCharacterMovementComponent* Move = GetSOMovement();
	if (BufferedJumpTime >= 0.0f && Move && GetWorld()->GetTimeSeconds() - BufferedJumpTime <= Move->JumpBufferTime)
	{
		Jump();
	}
	BufferedJumpTime = -1.0f;
}

void ASOCharacter::OnStartCrouch(float HalfHeightAdjust, float ScaledHalfHeightAdjust)
{
	Super::OnStartCrouch(HalfHeightAdjust, ScaledHalfHeightAdjust);
	// The capsule centre dropped; keep the eye where it was and let Tick ease it down.
	EyeOffset += ScaledHalfHeightAdjust;
	FirstPersonCamera->SetRelativeLocation(FVector(0.0f, 0.0f, EyeOffset));
}

void ASOCharacter::OnEndCrouch(float HalfHeightAdjust, float ScaledHalfHeightAdjust)
{
	Super::OnEndCrouch(HalfHeightAdjust, ScaledHalfHeightAdjust);
	EyeOffset -= ScaledHalfHeightAdjust;
	FirstPersonCamera->SetRelativeLocation(FVector(0.0f, 0.0f, EyeOffset));
}

bool ASOCharacter::CanJumpInternal_Implementation() const
{
	const USOCharacterMovementComponent* Move = GetSOMovement();
	if (bIsCrouched && Move && Move->IsSliding())
	{
		return JumpIsAllowedInternal(); // jump out of a slide
	}
	return Super::CanJumpInternal_Implementation();
}

bool ASOCharacter::CanJumpWhileFalling() const
{
	const USOCharacterMovementComponent* Move = GetSOMovement();
	return Move && Move->IsInCoyoteWindow();
}

// --- Camera ------------------------------------------------------------------------------------

void ASOCharacter::SetViewMode(ESOViewMode NewMode)
{
	ViewMode = NewMode;
	ApplyViewMode();
}

void ASOCharacter::ToggleViewMode()
{
	SetViewMode(ViewMode == ESOViewMode::FirstPerson ? ESOViewMode::ThirdPerson : ESOViewMode::FirstPerson);
}

void ASOCharacter::ApplyViewMode()
{
	const bool bFirst = ViewMode == ESOViewMode::FirstPerson;
	FirstPersonCamera->SetActive(bFirst);
	ThirdPersonCamera->SetActive(!bFirst);
	FirstPersonArms->SetVisibility(bFirst, true);
	GetMesh()->SetOwnerNoSee(bFirst);
}
