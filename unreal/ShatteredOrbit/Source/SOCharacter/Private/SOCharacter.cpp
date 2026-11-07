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
#include "SOLocomotionAnimInstance.h"
#include "SOLookComponent.h"
#include "SOViewmodelComponent.h"
#include "SOWeapon.h"
#include "SOWeaponData.h"
#include "SOSound.h"
#include "Animation/AnimSequenceBase.h"
#include "Engine/SkeletalMesh.h"
#include "Net/UnrealNetwork.h"

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
	Faction = ESOFaction::Player;
	StartMaxHealth = 100.0f;
	StartMaxShield = 50.0f;

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

	// The full body: hidden from the owner in first person but it still casts the player's shadow.
	USkeletalMeshComponent* Body = GetMesh();
	Body->SetRelativeLocation(FVector(0.0f, 0.0f, -Capsule->GetUnscaledCapsuleHalfHeight()));
	Body->SetRelativeRotation(FRotator(0.0f, -90.0f, 0.0f)); // Blender -Y forward -> UE +X
	Body->SetCastHiddenShadow(true);

	// First person: the same body again, owner-only, arms only (the anim instance collapses the rest).
	FirstPersonArms = CreateDefaultSubobject<USkeletalMeshComponent>(TEXT("FirstPersonArms"));
	FirstPersonArms->SetupAttachment(Capsule);
	FirstPersonArms->SetRelativeLocation(Body->GetRelativeLocation());
	FirstPersonArms->SetRelativeRotation(Body->GetRelativeRotation());
	FirstPersonArms->SetOnlyOwnerSee(true);
	FirstPersonArms->SetCastShadow(false);
	FirstPersonArms->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	FirstPersonArms->SetFirstPersonPrimitiveType(EFirstPersonPrimitiveType::FirstPerson);
	FirstPersonArms->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::OnlyTickPoseWhenRendered;

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

	// The holds are placed in world space every frame (from the aim, not the camera component, which only turns
	// when the view is computed at the end of the frame).
	Viewmodel = CreateDefaultSubobject<USOViewmodelComponent>(TEXT("Viewmodel"));
	Viewmodel->SetupAttachment(Capsule);
	ThirdPersonHold = CreateDefaultSubobject<USceneComponent>(TEXT("ThirdPersonHold"));
	ThirdPersonHold->SetupAttachment(Capsule);

	BodyMesh = TSoftObjectPtr<USkeletalMesh>(FSoftObjectPath(TEXT("/Game/Characters/PlayerMale/SK_PlayerMale.SK_PlayerMale")));
	ArmsMesh = TSoftObjectPtr<USkeletalMesh>(FSoftObjectPath(TEXT("/Game/Characters/PlayerMale/SK_PlayerMaleArms.SK_PlayerMaleArms")));
	DefaultWeapon = TSoftObjectPtr<USOWeaponData>(FSoftObjectPath(TEXT("/Game/Weapons/Rifle/DA_Rifle.DA_Rifle")));

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

void ASOCharacter::PostInitializeComponents()
{
	LoadContent();
	Super::PostInitializeComponents();
}

void ASOCharacter::LoadContent()
{
	LoadBody(GetMesh());
	LoadBody(FirstPersonArms);
}

void ASOCharacter::LoadBody(USkeletalMeshComponent* Body)
{
	if (!Body)
	{
		return;
	}
	const bool bArms = Body == FirstPersonArms;
	if (!Body->GetSkeletalMeshAsset())
	{
		USkeletalMesh* Loaded = bArms && !ArmsMesh.IsNull() ? ArmsMesh.LoadSynchronous() : nullptr;
		if (!Loaded && !BodyMesh.IsNull())
		{
			Loaded = BodyMesh.LoadSynchronous();
		}
		if (Loaded)
		{
			Body->SetSkeletalMesh(Loaded);
		}
	}
	if (bArms && GetMesh()->GetPhysicsAsset())
	{
		// Bounds from the body's physics shapes, so arms reaching forward are never culled (the arms mesh has none).
		Body->SetPhysicsAsset(GetMesh()->GetPhysicsAsset());
		Body->bComponentUseFixedSkelBounds = false;
	}
	if (Body->GetSkeletalMeshAsset() && !Body->GetAnimInstance())
	{
		Body->SetAnimInstanceClass(USOLocomotionAnimInstance::StaticClass());
	}
	if (USOLocomotionAnimInstance* Anim = Cast<USOLocomotionAnimInstance>(Body->GetAnimInstance()))
	{
		auto Clip = [this](const TCHAR* Name) -> UAnimSequenceBase*
		{
			const FString Asset = FPaths::GetBaseFilename(ClipPathPrefix) + Name;
			const FString Path = ClipPathPrefix + Name + TEXT(".") + Asset;
			return TSoftObjectPtr<UAnimSequenceBase>(FSoftObjectPath(Path)).LoadSynchronous();
		};
		Anim->Clips.Idle = Clip(TEXT("Idle"));
		Anim->Clips.Walk = Clip(TEXT("Walk"));
		Anim->Clips.Run = Clip(TEXT("Run"));
		Anim->Clips.Jump = Clip(TEXT("Jump"));
		Anim->Clips.Death = Clip(TEXT("Death"));
		Anim->Clips.Slide = Clip(TEXT("Slide"));
		Anim->Clips.WalkSpeed = 440.0f;
		Anim->Clips.RunSpeed = 860.0f;
	}
}

void ASOCharacter::BeginPlay()
{
	Super::BeginPlay();
	CurrentFov = GetHipFov();
	if (HasAuthority() && !Weapon && !DefaultWeapon.IsNull())
	{
		EquipWeapon(DefaultWeapon.LoadSynchronous());
	}
	ApplyViewMode();
}

FVector ASOCharacter::GetAimOrigin() const
{
	return FirstPersonCamera->GetComponentLocation();
}

USceneComponent* ASOCharacter::GetFirstPersonWeaponParent() const
{
	return Viewmodel;
}

bool ASOCharacter::CanFireWeapon() const
{
	if (bDead)
	{
		return false;
	}
	const USOCharacterMovementComponent* Move = GetSOMovement();
	if (Move && (Move->IsSprinting() || Move->IsMantling()))
	{
		return false;
	}
	const USOWeaponData* Data = Weapon ? Weapon->GetData() : nullptr;
	const float Ready = Data ? Data->SprintToFireTime : 0.2f;
	return GetWorld()->GetTimeSeconds() - LastSprintTime >= Ready;
}

FRotator ASOCharacter::GetAimRotation() const
{
	// The controller's own rotation (this frame's look input). GetBaseAimRotation() would return the camera's last
	// view, which already contains the recoil kick, is a frame late and follows any other view target.
	if (Controller)
	{
		return Controller->GetControlRotation();
	}
	return GetBaseAimRotation(); // others: replicated view pitch + actor yaw
}

FTransform ASOCharacter::GetEyeTransform(bool bWithRecoil) const
{
	FRotator Aim = GetAimRotation();
	Aim.Pitch = FRotator::NormalizeAxis(Aim.Pitch) + (bWithRecoil ? GetRecoilPitch() : 0.0f);
	Aim.Roll = 0.0f;
	return FTransform(Aim, FirstPersonCamera->GetComponentLocation());
}

FVector ASOCharacter::GetAimDirection() const
{
	// Rounds follow the kicked view (the kick recovers by itself).
	const FVector Forward = GetEyeTransform(true).GetRotation().GetForwardVector();
	if (ViewMode != ESOViewMode::ThirdPerson || !ThirdPersonCamera || bDead)
	{
		return Forward;
	}
	// Third person: the crosshair is the middle of the shoulder camera, which sits beside the head. Find what the
	// camera's centre ray hits and send the round from the eye to that point.
	UWorld* World = GetWorld();
	const FVector Origin = GetAimOrigin();
	const FVector Camera = ThirdPersonCamera->GetComponentLocation();
	const FVector Start = Camera + Forward * FMath::Max(0.0f, FVector::DotProduct(Origin - Camera, Forward)); // skip what is behind the character
	const FVector End = Start + Forward * 30000.0f;
	FCollisionQueryParams Params(SCENE_QUERY_STAT(SOThirdPersonAim), true, this);
	if (Weapon)
	{
		Params.AddIgnoredActor(Weapon);
	}
	FHitResult Hit;
	const FVector Target = World && World->LineTraceSingleByChannel(Hit, Start, End, SO_TRACE_BULLET, Params) ? FVector(Hit.ImpactPoint) : End;
	const FVector Dir = (Target - Origin).GetSafeNormal();
	return FVector::DotProduct(Dir, Forward) > 0.5f ? Dir : Forward;
}

float ASOCharacter::GetSpreadScale() const
{
	// weapons.js spreadDir: aiming x0.45, moving x1.35, airborne x1.6.
	float Scale = FMath::Lerp(1.0f, 0.45f, AimProgress);
	if (GetVelocity().Size2D() > 50.0f)
	{
		Scale *= 1.35f;
	}
	if (const USOCharacterMovementComponent* Move = GetSOMovement(); Move && Move->IsFalling())
	{
		Scale *= 1.6f;
	}
	return Scale;
}

void ASOCharacter::OnWeaponFired(float Kick)
{
	if (Viewmodel)
	{
		Viewmodel->Kick(Kick);
	}
	// weapons.js: recoil += 0.35 / spread * 0.3 + 0.15 per shot, capped at 1.5.
	const USOWeaponData* Data = Weapon ? Weapon->GetData() : nullptr;
	const float Spread = Data ? FMath::Max(Data->Spread, 0.1f) : 1.0f;
	RecoilKick = FMath::Min(1.5f, RecoilKick + (0.35f / Spread * 0.3f + 0.15f) * (Kick > 0.0f ? 1.0f : 0.0f));
}

FVector ASOCharacter::ViewmodelToWorld(const FVector& ViewmodelPoint) const
{
	// The viewmodel renders with FirstPersonFieldOfView; at the same depth a world point appears at the same screen
	// position when its lateral offsets are scaled by tan(worldFov / 2) / tan(viewmodelFov / 2).
	const FTransform Eye = GetEyeTransform(true); // what the camera shows (the component itself turns late)
	FVector Local = Eye.InverseTransformPosition(ViewmodelPoint);
	if (FirstPersonCamera->bEnableFirstPersonFieldOfView)
	{
		const float World = FMath::Tan(FMath::DegreesToRadians(FirstPersonCamera->FieldOfView) * 0.5f);
		const float View = FMath::Tan(FMath::DegreesToRadians(FirstPersonCamera->FirstPersonFieldOfView) * 0.5f);
		const float K = View > 1e-3f ? World / View : 1.0f;
		Local.Y *= K;
		Local.Z *= K;
	}
	return Eye.TransformPosition(Local);
}

bool ASOCharacter::IsFirstPersonView() const
{
	return ViewMode == ESOViewMode::FirstPerson && IsLocallyControlled() && IsPlayerControlled();
}

void ASOCharacter::UpdateFeedbackSounds(float DeltaSeconds)
{
	UWorld* World = GetWorld();
	if (!World || World->GetNetMode() == NM_DedicatedServer)
	{
		return;
	}
	const float Now = World->GetTimeSeconds();

	// Footsteps: one per stride on the ground (2D for yourself, positional for others).
	const USOCharacterMovementComponent* Move = GetSOMovement();
	const float Speed = GetVelocity().Size2D();
	if (Move && Move->MovementMode == MOVE_Walking && Speed > 120.0f && !bDead)
	{
		StepDistance += Speed * DeltaSeconds;
		const float Stride = Move->IsSprinting() ? 240.0f : (bIsCrouched ? 140.0f : 185.0f);
		if (StepDistance >= Stride)
		{
			StepDistance = 0.0f;
			const float Volume = bIsCrouched ? 0.22f : (Move->IsSprinting() ? 0.6f : 0.42f);
			const FName Step(*FString::Printf(TEXT("footstep_%d"), FMath::RandRange(1, 4)));
			USOSoundLibrary::PlayFor(this, Step, GetActorLocation() - FVector(0, 0, 85.0f), Volume, ESOSoundRange::Near, 0.08f);
		}
	}

	// Hurt / shield cues for the local player.
	if (IsLocallyControlled() && IsPlayerControlled())
	{
		const float Health = GetHealth();
		const float Shield = GetShield();
		if (LastHealthSeen >= 0.0f)
		{
			if (Health < LastHealthSeen - 0.5f && Now - LastHurtSound > 0.25f)
			{
				LastHurtSound = Now;
				USOSoundLibrary::Play2D(this, TEXT("player_hurt"), 0.8f, 0.06f);
			}
			if (LastShieldSeen > 0.0f && Shield <= 0.0f)
			{
				USOSoundLibrary::Play2D(this, TEXT("shield_break"), 0.7f, 0.02f);
			}
			const bool bRising = Shield > LastShieldSeen + 0.01f && Shield < GetMaxShield();
			if (bRising && !bShieldRecharging)
			{
				USOSoundLibrary::Play2D(this, TEXT("shield_recharge"), 0.45f, 0.0f);
			}
			bShieldRecharging = bRising || (bShieldRecharging && Shield < GetMaxShield() && Shield >= LastShieldSeen);
		}
		LastHealthSeen = Health;
		LastShieldSeen = Shield;
	}
}

void ASOCharacter::HandleDeath()
{
	Super::HandleDeath();
	bAiming = false;
	if (USOCharacterMovementComponent* Move = GetSOMovement())
	{
		Move->SetWantsToAim(false);
		Move->SetWantsToSprint(false);
	}
	// Watch the body fall from behind.
	SetViewMode(ESOViewMode::ThirdPerson);
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

	UpdateFeedbackSounds(DeltaSeconds);

	// Recoil recovers on its own; the camera shows it as an additive pitch.
	RecoilKick = FMath::Max(0.0f, RecoilKick - DeltaSeconds * RecoilRecovery);
	for (UCameraComponent* Camera : { FirstPersonCamera.Get(), ThirdPersonCamera.Get() })
	{
		Camera->ClearAdditiveOffset();
		if (RecoilKick > 0.0f)
		{
			Camera->AddAdditiveOffset(FTransform(FRotator(GetRecoilPitch(), 0.0f, 0.0f)), 0.0f);
		}
	}

	// Eye height eases across crouch / slide transitions.
	EyeOffset = FMath::FInterpTo(EyeOffset, GetTargetEyeOffset(), DeltaSeconds, EyeHeightInterpSpeed);
	FirstPersonCamera->SetRelativeLocation(FVector(0.0f, 0.0f, EyeOffset));

	// Aim down sights: progress at the weapon ADS rate, zoom by the weapon magnification.
	const USOWeaponData* WeaponData = Weapon ? Weapon->GetData() : nullptr;
	const float AdsTime = WeaponData ? WeaponData->AdsTime : 0.2f;
	AimProgress = FMath::FInterpConstantTo(AimProgress, bAiming ? 1.0f : 0.0f, DeltaSeconds, 1.0f / FMath::Max(AdsTime, 0.05f));
	const float Ads = AimProgress * AimProgress * (3.0f - 2.0f * AimProgress);
	const float HipFov = GetHipFov();
	const float Zoom = WeaponData ? WeaponData->AimZoom : 1.0f / AimFovScale;
	CurrentFov = HipFov / FMath::Lerp(1.0f, FMath::Max(Zoom, 1.0f), Ads);
	FirstPersonCamera->SetFieldOfView(CurrentFov);
	ThirdPersonCamera->SetFieldOfView(CurrentFov);
	Look->SetAim(bAiming, HipFov, CurrentFov);

	// A latched (tapped) sprint ends once you stop pushing forward; a latched crouch follows the movement state.
	if (USOCharacterMovementComponent* Move = GetSOMovement())
	{
		if (Move->IsSprinting())
		{
			LastSprintTime = GetWorld()->GetTimeSeconds();
			if (Weapon && Weapon->IsReloading())
			{
				Weapon->CancelReload(); // sprinting cancels a reload
			}
		}
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
	if (bDead)
	{
		return;
	}
	// Firing stops a sprint (the sprint-to-fire delay then applies).
	if (USOCharacterMovementComponent* Move = GetSOMovement(); Move && Move->WantsToSprint())
	{
		bSprintLatched = false;
		Move->SetWantsToSprint(false);
	}
	if (Weapon)
	{
		Weapon->StartFire();
	}
}

void ASOCharacter::HandleFireReleased()
{
	if (Weapon)
	{
		Weapon->StopFire();
	}
}

void ASOCharacter::HandleAimPressed()
{
	if (bDead)
	{
		return;
	}
	bAiming = true;
	if (USOCharacterMovementComponent* Move = GetSOMovement())
	{
		bSprintLatched = false;
		Move->SetWantsToSprint(false);
		Move->SetWantsToAim(true);
	}
}

void ASOCharacter::HandleAimReleased()
{
	bAiming = false;
	if (USOCharacterMovementComponent* Move = GetSOMovement())
	{
		Move->SetWantsToAim(false);
	}
}

void ASOCharacter::HandleReload()
{
	if (Weapon && !bDead)
	{
		Weapon->StartReload();
	}
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
	if (!HasAuthority() && IsLocallyControlled())
	{
		ServerSetViewMode(NewMode);
	}
}

void ASOCharacter::ServerSetViewMode_Implementation(ESOViewMode NewMode)
{
	ViewMode = NewMode;
	ApplyViewMode();
}

void ASOCharacter::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
	Super::GetLifetimeReplicatedProps(OutLifetimeProps);
	DOREPLIFETIME_CONDITION(ASOCharacter, ViewMode, COND_SkipOwner);
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
	if (Weapon)
	{
		Weapon->SetFirstPersonView(bFirst);
	}
}
