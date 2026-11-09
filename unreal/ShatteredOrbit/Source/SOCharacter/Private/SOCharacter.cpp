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
#include "GameFramework/PlayerState.h"
#include "SOInventoryComponent.h"
#include "SOLootActors.h"
#include "SOGunRigComponent.h"
#include "EngineUtils.h"
#include "Kismet/GameplayStatics.h"
#include "Components/CapsuleComponent.h"
#include "Rendering/SkeletalMeshRenderData.h"
#include "Rendering/SkeletalMeshLODRenderData.h"

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
	static const TCHAR* Weapon1 = TEXT("/Game/Input/IA_Weapon1.IA_Weapon1");
	static const TCHAR* Weapon2 = TEXT("/Game/Input/IA_Weapon2.IA_Weapon2");
	static const TCHAR* Weapon3 = TEXT("/Game/Input/IA_Weapon3.IA_Weapon3");
	static const TCHAR* NextWeapon = TEXT("/Game/Input/IA_NextWeapon.IA_NextWeapon");
	static const TCHAR* PrevWeapon = TEXT("/Game/Input/IA_PrevWeapon.IA_PrevWeapon");
	static const TCHAR* Inventory = TEXT("/Game/Input/IA_Inventory.IA_Inventory");
	static const TCHAR* Map = TEXT("/Game/Input/IA_Map.IA_Map");
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
	// Animated whenever first person is on (ticking is switched off in third person): "only when rendered" would leave
	// them stuck in the rest pose below the camera after a third-person spell, never rendered and so never animated.
	FirstPersonArms->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;

	ThirdPersonBoom = CreateDefaultSubobject<USpringArmComponent>(TEXT("ThirdPersonBoom"));
	ThirdPersonBoom->SetupAttachment(Capsule);
	ThirdPersonBoom->SetRelativeLocation(FVector(0.0f, 0.0f, 55.0f));
	ThirdPersonBoom->TargetArmLength = HipArmLength;
	ThirdPersonBoom->SocketOffset = HipSocketOffset;
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
	Weapon1Action = TSoftObjectPtr<UInputAction>(FSoftObjectPath(SOInputPaths::Weapon1));
	Weapon2Action = TSoftObjectPtr<UInputAction>(FSoftObjectPath(SOInputPaths::Weapon2));
	Weapon3Action = TSoftObjectPtr<UInputAction>(FSoftObjectPath(SOInputPaths::Weapon3));
	NextWeaponAction = TSoftObjectPtr<UInputAction>(FSoftObjectPath(SOInputPaths::NextWeapon));
	PrevWeaponAction = TSoftObjectPtr<UInputAction>(FSoftObjectPath(SOInputPaths::PrevWeapon));
	InventoryAction = TSoftObjectPtr<UInputAction>(FSoftObjectPath(SOInputPaths::Inventory));
	MapAction = TSoftObjectPtr<UInputAction>(FSoftObjectPath(SOInputPaths::Map));
}

USOCharacterMovementComponent* ASOCharacter::GetSOMovement() const
{
	return Cast<USOCharacterMovementComponent>(GetCharacterMovement());
}

void ASOCharacter::PostInitializeComponents()
{
	LoadContent();
	Super::PostInitializeComponents();
	if (Outfit.Slots.Num() == 0)
	{
		// dressed in the wardrobe's defaults until an inventory says otherwise
		if (const USOWardrobeData* Wardrobe = USOWardrobeData::Get(Outfit.Body))
		{
			for (const TPair<FName, FName>& D : Wardrobe->Defaults)
			{
				Outfit.Set(D.Key, D.Value);
			}
		}
	}
	ApplyOutfit();
}

// --- Outfit ------------------------------------------------------------------------------------

namespace
{
	/** Shows / hides the body's skin__<region> sections (export_fbx.py --per-item gives each region its own slot). */
	void ShowRegions(USkeletalMeshComponent* Body, const TSet<FName>& Hidden)
	{
		USkeletalMesh* Mesh = Body ? Body->GetSkeletalMeshAsset() : nullptr;
		const FSkeletalMeshRenderData* Render = Mesh ? Mesh->GetResourceForRendering() : nullptr;
		if (!Render)
		{
			return;
		}
		const TArray<FSkeletalMaterial>& Materials = Mesh->GetMaterials();
		for (int32 Lod = 0; Lod < Render->LODRenderData.Num(); ++Lod)
		{
			const TArray<FSkelMeshRenderSection>& Sections = Render->LODRenderData[Lod].RenderSections;
			const FSkeletalMeshLODInfo* Info = Mesh->GetLODInfo(Lod);
			for (int32 Section = 0; Section < Sections.Num(); ++Section)
			{
				int32 Material = Sections[Section].MaterialIndex;
				if (Info && Info->LODMaterialMap.IsValidIndex(Section) && Info->LODMaterialMap[Section] != INDEX_NONE)
				{
					Material = Info->LODMaterialMap[Section];
				}
				if (!Materials.IsValidIndex(Material))
				{
					continue;
				}
				const FString Slot = Materials[Material].MaterialSlotName.ToString();
				if (Slot.StartsWith(TEXT("skin__")))
				{
					Body->ShowMaterialSection(Material, Section, !Hidden.Contains(FName(*Slot.RightChop(6))), Lod);
				}
			}
		}
	}
}

void ASOCharacter::SetOutfit(const FSOOutfit& NewOutfit)
{
	if (NewOutfit == Outfit && AppliedBody == NewOutfit.Body && WornThirdPerson.Num() > 0)
	{
		return;
	}
	Outfit = NewOutfit;
	ApplyOutfit();
}

void ASOCharacter::OnRep_Outfit()
{
	ApplyOutfit();
}

void ASOCharacter::OutfitFromInventory()
{
	if (const USOInventoryComponent* Inventory = GetInventory(); Inventory && HasAuthority())
	{
		SetOutfit(Inventory->GetOutfit());
	}
}

USkeletalMeshComponent* ASOCharacter::GetWornPiece(FName Slot, bool bFirstPerson) const
{
	const TObjectPtr<USkeletalMeshComponent>* Found = (bFirstPerson ? WornFirstPerson : WornThirdPerson).Find(Slot);
	return Found ? Found->Get() : nullptr;
}

void ASOCharacter::ApplyOutfit()
{
	USOWardrobeData* Wardrobe = USOWardrobeData::Get(Outfit.Body);
	if (!Wardrobe)
	{
		return;
	}
	// another body: its meshes and clips (both views)
	if (AppliedBody != Outfit.Body)
	{
		AppliedBody = Outfit.Body;
		BodyMesh = Wardrobe->BodyMesh;
		ArmsMesh = Wardrobe->ArmsMesh;
		if (!Wardrobe->ClipPathPrefix.IsEmpty())
		{
			ClipPathPrefix = Wardrobe->ClipPathPrefix;
		}
		USkeletalMesh* Body = BodyMesh.LoadSynchronous();
		USkeletalMesh* Arms = ArmsMesh.LoadSynchronous();
		if (Body && GetMesh()->GetSkeletalMeshAsset() != Body)
		{
			GetMesh()->SetSkeletalMesh(Body);
			LoadBody(GetMesh());
		}
		if (Arms && FirstPersonArms->GetSkeletalMeshAsset() != Arms)
		{
			FirstPersonArms->SetSkeletalMesh(Arms);
			LoadBody(FirstPersonArms);
		}
	}

	// what shows: replaced slots and hair under a helmet go; locked underwear only while nothing covers it
	TMap<FName, const FSOWardrobeItem*> Worn;
	for (int32 i = 0; i < Outfit.Slots.Num(); ++i)
	{
		if (const FSOWardrobeItem* Item = Outfit.Items.IsValidIndex(i) ? Wardrobe->Find(Outfit.Slots[i], Outfit.Items[i]) : nullptr)
		{
			Worn.Add(Outfit.Slots[i], Item);
		}
	}
	TSet<FName> Gone;
	for (const TPair<FName, const FSOWardrobeItem*>& P : Worn)
	{
		Gone.Append(P.Value->Replaces);
		if (P.Value->bHideHair)
		{
			Gone.Add(TEXT("hair"));
		}
	}
	for (const TPair<FName, const FSOWardrobeItem*>& P : Worn)
	{
		for (const FName Cover : P.Value->CoveredBy)
		{
			if (P.Value->bLocked && Worn.Contains(Cover) && !Gone.Contains(Cover))
			{
				Gone.Add(P.Key);
			}
		}
	}
	HiddenRegions.Reset();
	for (const TPair<FName, const FSOWardrobeItem*>& P : Worn)
	{
		if (!Gone.Contains(P.Key))
		{
			HiddenRegions.Append(P.Value->Hide);
		}
	}

	auto Dress = [&](TMap<FName, TObjectPtr<USkeletalMeshComponent>>& Pieces, USkeletalMeshComponent* Leader, bool bFirstPerson)
	{
		TSet<FName> Keep;
		for (const TPair<FName, const FSOWardrobeItem*>& P : Worn)
		{
			USkeletalMesh* Mesh = Gone.Contains(P.Key) ? nullptr : (bFirstPerson ? P.Value->ArmsMesh : P.Value->Mesh).LoadSynchronous();
			if (!Mesh)
			{
				continue;
			}
			TObjectPtr<USkeletalMeshComponent>& Piece = Pieces.FindOrAdd(P.Key);
			if (!Piece)
			{
				const FName Name = MakeUniqueObjectName(this, USkeletalMeshComponent::StaticClass(),
					*FString::Printf(TEXT("%s_%s"), bFirstPerson ? TEXT("WornFP") : TEXT("Worn"), *P.Key.ToString()));
				Piece = NewObject<USkeletalMeshComponent>(this, Name);
				Piece->SetupAttachment(Leader);
				Piece->SetCollisionEnabled(ECollisionEnabled::NoCollision);
				Piece->SetGenerateOverlapEvents(false);
				Piece->bUseBoundsFromLeaderPoseComponent = true;
				if (bFirstPerson)
				{
					Piece->SetOnlyOwnerSee(true);
					Piece->SetCastShadow(false);
					Piece->SetFirstPersonPrimitiveType(EFirstPersonPrimitiveType::FirstPerson);
				}
				else
				{
					Piece->SetCastHiddenShadow(true);
				}
				Piece->RegisterComponent();
			}
			if (Piece->GetSkeletalMeshAsset() != Mesh)
			{
				Piece->SetSkeletalMesh(Mesh);
			}
			Piece->SetLeaderPoseComponent(Leader);
			Keep.Add(P.Key);
		}
		for (auto It = Pieces.CreateIterator(); It; ++It)
		{
			if (!Keep.Contains(It.Key()))
			{
				if (It.Value())
				{
					It.Value()->DestroyComponent();
				}
				It.RemoveCurrent();
			}
		}
	};
	Dress(WornThirdPerson, GetMesh(), false);
	Dress(WornFirstPerson, FirstPersonArms, true);
	ShowRegions(GetMesh(), HiddenRegions);
	ShowRegions(FirstPersonArms, HiddenRegions);
	ApplyViewMode();
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
	Aim.Roll = CameraRoll;   // slide / strafe tilt (the gun rolls with the view; the aim direction does not change)
	return FTransform(Aim, FirstPersonCamera->GetComponentLocation());
}

bool ASOCharacter::UsesShoulderCrosshair() const
{
	return ViewMode == ESOViewMode::ThirdPerson && ThirdPersonCamera && !bDead && !bScopeView;
}

FVector ASOCharacter::GetAimTarget() const
{
	const FTransform Eye = GetEyeTransform(true);
	const FVector Forward = Eye.GetRotation().GetForwardVector();
	const FVector Origin = Eye.GetLocation();
	if (!UsesShoulderCrosshair())
	{
		return Origin + Forward * 30000.0f;
	}
	// Third person: the crosshair is the middle of the shoulder camera, which sits beside the head: what the
	// camera's centre ray hits (starting level with the eye, so nothing behind the character counts).
	UWorld* World = GetWorld();
	const FVector Camera = ThirdPersonCamera->GetComponentLocation();
	const FVector Start = Camera + Forward * FMath::Max(0.0f, FVector::DotProduct(Origin - Camera, Forward));
	const FVector End = Start + Forward * 30000.0f;
	FCollisionQueryParams Params(SCENE_QUERY_STAT(SOThirdPersonAim), true, this);
	if (Weapon)
	{
		Params.AddIgnoredActor(Weapon);
	}
	FHitResult Hit;
	return World && World->LineTraceSingleByChannel(Hit, Start, End, SO_TRACE_BULLET, Params) ? FVector(Hit.ImpactPoint) : End;
}

FVector ASOCharacter::GetAimDirection() const
{
	// Rounds follow the kicked view (the kick recovers by itself); third person, from the eye to the crosshair's point.
	const FVector Forward = GetEyeTransform(true).GetRotation().GetForwardVector();
	if (!UsesShoulderCrosshair())
	{
		return Forward;
	}
	const FVector Dir = (GetAimTarget() - GetAimOrigin()).GetSafeNormal();
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
	const float Spread = Weapon ? FMath::Max(Weapon->GetStats().Spread, 0.1f) : 1.0f;
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
	StoreWeaponAmmo(); // the respawned body draws the same gun with the same rounds
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
	UpdateCameraFeel(DeltaSeconds);
	for (UCameraComponent* Camera : { FirstPersonCamera.Get(), ThirdPersonCamera.Get() })
	{
		Camera->ClearAdditiveOffset();
		const float Roll = Camera == FirstPersonCamera.Get() ? CameraRoll : 0.0f;
		if (RecoilKick > 0.0f || FMath::Abs(Roll) > 1e-3f)
		{
			Camera->AddAdditiveOffset(FTransform(FRotator(GetRecoilPitch(), 0.0f, Roll)), 0.0f);
		}
	}

	// Eye height eases across crouch / slide transitions; steps, landings and the head bob ride on top.
	EyeOffset = FMath::FInterpTo(EyeOffset, GetTargetEyeOffset(), DeltaSeconds, EyeHeightInterpSpeed);
	FirstPersonCamera->SetRelativeLocation(FVector(0.0f, 0.0f, EyeOffset) + FeelOffset);

	// Aim down sights: progress at the weapon ADS rate, zoom by the weapon magnification.
	const USOWeaponData* WeaponData = Weapon ? Weapon->GetData() : nullptr;
	const float AdsTime = WeaponData ? WeaponData->AdsTime : 0.2f;
	AimProgress = FMath::FInterpConstantTo(AimProgress, bAiming ? 1.0f : 0.0f, DeltaSeconds, 1.0f / FMath::Max(AdsTime, 0.05f));
	const float Ads = AimProgress * AimProgress * (3.0f - 2.0f * AimProgress);
	const float HipFov = GetHipFov();
	const float Zoom = WeaponData ? Weapon->GetStats().Zoom : 1.0f / AimFovScale;
	const float MoveFov = HipFov + FovBoost * (1.0f - Ads);     // sprint / slide widen the hip view only
	// The eye zooms by the full magnification; the shoulder camera only a little (it comes in closer instead), so a
	// scoped gun never zooms onto the character's back before the view cuts to the scope.
	const float EyeFov = MoveFov / FMath::Lerp(1.0f, FMath::Max(Zoom, 1.0f), Ads);
	const float ShoulderFov = MoveFov / FMath::Lerp(1.0f, FMath::Clamp(Zoom, 1.0f, ThirdPersonMaxZoom), Ads);
	FirstPersonCamera->SetFieldOfView(EyeFov);
	ThirdPersonCamera->SetFieldOfView(ShoulderFov);
	ThirdPersonBoom->TargetArmLength = FMath::Lerp(HipArmLength, AimArmLength, Ads);
	ThirdPersonBoom->SocketOffset = FMath::Lerp(HipSocketOffset, AimSocketOffset, Ads);

	// Magnified optics: fully aimed, the scope picture replaces the gun (viewmodel.js inScope); third person cuts to
	// the eye for it, like the shoulder shooters do.
	const bool bScope = IsLocallyControlled() && IsPlayerControlled() && !bDead && Weapon && Weapon->IsScoped()
		&& AimProgress > 0.82f && bAiming;
	if (bScope != bScopeView)
	{
		bScopeView = bScope;
		ApplyViewMode();
	}
	CurrentFov = UsesShoulderCrosshair() ? ShoulderFov : EyeFov;
	Look->SetAim(bAiming, MoveFov, CurrentFov);

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
	if (UInputAction* A = Load(Weapon1Action)) { Input->BindAction(A, ETriggerEvent::Started, this, &ASOCharacter::HandleWeapon1); }
	if (UInputAction* A = Load(Weapon2Action)) { Input->BindAction(A, ETriggerEvent::Started, this, &ASOCharacter::HandleWeapon2); }
	if (UInputAction* A = Load(Weapon3Action)) { Input->BindAction(A, ETriggerEvent::Started, this, &ASOCharacter::HandleWeapon3); }
	if (UInputAction* A = Load(NextWeaponAction)) { Input->BindAction(A, ETriggerEvent::Started, this, &ASOCharacter::HandleNextWeapon); }
	if (UInputAction* A = Load(PrevWeaponAction)) { Input->BindAction(A, ETriggerEvent::Started, this, &ASOCharacter::HandlePrevWeapon); }
	if (UInputAction* A = Load(InventoryAction)) { Input->BindAction(A, ETriggerEvent::Started, this, &ASOCharacter::HandleInventory); }
	if (UInputAction* A = Load(MapAction)) { Input->BindAction(A, ETriggerEvent::Started, this, &ASOCharacter::HandleMap); }

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
	if (AActor* Target = FindInteractable(); Target && !bDead)
	{
		ServerInteract(Target);
	}
}

AActor* ASOCharacter::FindInteractable() const
{
	const FTransform Eye = GetEyeTransform(false);
	AActor* Best = nullptr;
	float BestScore = 0.0f;
	for (TActorIterator<AActor> It(GetWorld()); It; ++It)
	{
		const ISOInteractable* Thing = Cast<ISOInteractable>(*It);
		if (!Thing)
		{
			continue;
		}
		const FVector To = It->GetActorLocation() + FVector(0, 0, 60.0f) - Eye.GetLocation();
		const float Distance = To.Size();
		const float Facing = FVector::DotProduct(To.GetSafeNormal(), Eye.GetRotation().GetForwardVector());
		if (Distance > Thing->GetInteractRange() || Facing < 0.35f)
		{
			continue;
		}
		const float Score = Facing / FMath::Max(Distance, 1.0f);
		if (Score > BestScore)
		{
			BestScore = Score;
			Best = *It;
		}
	}
	return Best;
}

void ASOCharacter::ServerInteract_Implementation(AActor* Target)
{
	ISOInteractable* Thing = Cast<ISOInteractable>(Target);
	if (!Thing || bDead || FVector::Dist(Target->GetActorLocation(), GetActorLocation()) > Thing->GetInteractRange() + 150.0f)
	{
		return;
	}
	if (Thing->CanInteract(this))
	{
		Thing->Interact(this);
	}
	else
	{
		USOSoundLibrary::PlayFor(this, TEXT("ui_deny"), GetActorLocation(), 0.6f, ESOSoundRange::Near);
	}
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

void ASOCharacter::HandleWeapon1() { SelectSlot(0); }
void ASOCharacter::HandleWeapon2() { SelectSlot(1); }
void ASOCharacter::HandleWeapon3() { SelectSlot(2); }
void ASOCharacter::HandleNextWeapon() { CycleSlot(1); }
void ASOCharacter::HandlePrevWeapon() { CycleSlot(-1); }

void ASOCharacter::HandleMap()
{
	if (ToggleMapScreen)
	{
		ToggleMapScreen();
	}
}

void ASOCharacter::FastTravel(AActor* Point)
{
	if (HasAuthority())
	{
		ServerFastTravel_Implementation(Point);
	}
	else
	{
		ServerFastTravel(Point);
	}
}

void ASOCharacter::ServerFastTravel_Implementation(AActor* Point)
{
	if (!Point || !Point->ActorHasTag(TEXT("SOFastTravel")) || bDead)
	{
		return;
	}
	// beside the point on its front, facing it (the map point's own arrival spot)
	const FVector Front = Point->GetActorForwardVector();
	const FVector At = Point->GetActorLocation() + Front * 400.0f + FVector(0.0f, 0.0f, GetCapsuleComponent()->GetScaledCapsuleHalfHeight() + 20.0f);
	const FRotator Facing = (-Front).Rotation();
	TeleportTo(At, FRotator(0.0f, Facing.Yaw, 0.0f), false, true);
	if (AController* C = GetController())
	{
		C->SetControlRotation(FRotator(0.0f, Facing.Yaw, 0.0f));
	}
	USOSoundLibrary::PlayFor(this, TEXT("reliquary_open"), At, 0.5f, ESOSoundRange::Near);
}

void ASOCharacter::TravelToArea(const FString& Level)
{
	if (HasAuthority())
	{
		ServerTravelToArea_Implementation(Level);
	}
	else
	{
		ServerTravelToArea(Level);
	}
}

void ASOCharacter::ServerTravelToArea_Implementation(const FString& Level)
{
	UWorld* World = GetWorld();
	if (!World || !Level.StartsWith(TEXT("/Game/Maps/")))
	{
		return;
	}
	StoreWeaponAmmo();
	if (World->GetNetMode() == NM_Standalone)
	{
		UGameplayStatics::OpenLevel(this, FName(*Level));
	}
	else
	{
		World->ServerTravel(Level + TEXT("?listen"));
	}
}

void ASOCharacter::HandleInventory()
{
	if (ToggleInventoryScreen)
	{
		ToggleInventoryScreen();
	}
}

USOInventoryComponent* ASOCharacter::GetInventory() const
{
	const APlayerState* PS = GetPlayerState();
	return PS ? PS->FindComponentByClass<USOInventoryComponent>() : nullptr;
}

void ASOCharacter::SelectSlot(int32 Slot)
{
	USOInventoryComponent* Inventory = GetInventory();
	if (!Inventory || bDead || Slot == Inventory->GetActiveSlot() || !Inventory->GetEquipped(Slot))
	{
		return;
	}
	Inventory->ServerSelectSlot(Slot);
}

void ASOCharacter::CycleSlot(int32 Step)
{
	const USOInventoryComponent* Inventory = GetInventory();
	if (!Inventory)
	{
		return;
	}
	for (int32 i = 1; i < USOInventoryComponent::NumSlots; ++i)
	{
		const int32 Slot = (Inventory->GetActiveSlot() + Step * i + USOInventoryComponent::NumSlots * 2) % USOInventoryComponent::NumSlots;
		if (Inventory->GetEquipped(Slot))
		{
			SelectSlot(Slot);
			return;
		}
	}
}

void ASOCharacter::StoreWeaponAmmo()
{
	USOInventoryComponent* Inventory = GetInventory();
	if (Inventory && Weapon && HasAuthority())
	{
		Inventory->StoreAmmo(Weapon->GetInstance().Uid, Weapon->GetMag(), Weapon->GetReserve());
	}
}

void ASOCharacter::EquipFromInventory()
{
	USOInventoryComponent* Inventory = GetInventory();
	if (!HasAuthority() || !Inventory || bDead)
	{
		return;
	}
	const FSOWeaponInstance* Wanted = Inventory->GetEquipped(Inventory->GetActiveSlot());
	if (!Wanted || (Weapon && Weapon->GetInstance().Uid == Wanted->Uid))
	{
		return;
	}
	const FString Uid = Wanted->Uid;
	StoreWeaponAmmo();
	EquipInstance(Inventory->PrepareForEquip(Uid));
}

void ASOCharacter::PossessedBy(AController* NewController)
{
	Super::PossessedBy(NewController);
	BindInventory();
}

void ASOCharacter::BindInventory()
{
	if (USOInventoryComponent* Inventory = GetInventory())
	{
		if (BoundInventory.IsValid())
		{
			BoundInventory->OnLoadoutChanged.Remove(LoadoutHandle);
		BoundInventory->OnOutfitChanged.Remove(OutfitHandle);
		}
		if (BoundInventory.IsValid())
		{
			BoundInventory->OnOutfitChanged.Remove(OutfitHandle);
		}
		BoundInventory = Inventory;
		LoadoutHandle = Inventory->OnLoadoutChanged.AddUObject(this, &ASOCharacter::EquipFromInventory);
		OutfitHandle = Inventory->OnOutfitChanged.AddUObject(this, &ASOCharacter::OutfitFromInventory);
		EquipFromInventory();
		OutfitFromInventory();
	}
}

void ASOCharacter::UnPossessed()
{
	StoreWeaponAmmo();
	if (BoundInventory.IsValid())
	{
		BoundInventory->OnLoadoutChanged.Remove(LoadoutHandle);
		BoundInventory->OnOutfitChanged.Remove(OutfitHandle);
	}
	BoundInventory = nullptr;
	Super::UnPossessed();
}

void ASOCharacter::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	if (BoundInventory.IsValid())
	{
		BoundInventory->OnLoadoutChanged.Remove(LoadoutHandle);
		BoundInventory->OnOutfitChanged.Remove(OutfitHandle);
	}
	Super::EndPlay(EndPlayReason);
}

void ASOCharacter::OnWeaponEquipped()
{
	ApplyViewMode();
	if (Viewmodel)
	{
		Viewmodel->Raise();
	}
	if (Weapon && IsLocallyControlled() && HasActorBegunPlay())
	{
		USOSoundLibrary::Play2D(this, TEXT("weapon_raise"), 0.7f, 0.04f);
	}
}

// --- Movement hooks ----------------------------------------------------------------------------

void ASOCharacter::Landed(const FHitResult& Hit)
{
	Super::Landed(Hit);
	// the view dips with the impact (the spring in UpdateCameraFeel brings it back)
	LandDipVel -= FMath::Clamp((-LastAirVz - 150.0f) * 0.16f, 0.0f, 190.0f);

	const USOCharacterMovementComponent* Move = GetSOMovement();
	if (BufferedJumpTime >= 0.0f && Move && GetWorld()->GetTimeSeconds() - BufferedJumpTime <= Move->JumpBufferTime)
	{
		Jump();
	}
	BufferedJumpTime = -1.0f;
}

void ASOCharacter::OnJumped_Implementation()
{
	Super::OnJumped_Implementation();
	LandDipVel -= 35.0f;   // a small push off the legs before the view rises
}

void ASOCharacter::UpdateCameraFeel(float DeltaSeconds)
{
	const float Dt = FMath::Max(DeltaSeconds, 1e-4f);
	const USOCharacterMovementComponent* Move = GetSOMovement();
	const bool bFeel = Move && IsLocallyControlled() && ViewMode == ESOViewMode::FirstPerson && !bDead;
	const double Z = GetActorLocation().Z;
	if (!bFeel)
	{
		FeelOffset = FVector::ZeroVector;
		StepSmooth = LandDip = LandDipVel = CameraRoll = FovBoost = BobAmp = 0.0f;
		LastFeelZ = Z;
		bHaveFeelZ = true;
		return;
	}
	const FVector Velocity = GetVelocity();
	const float Speed = Velocity.Size2D();
	const bool bGrounded = Move->IsMovingOnGround() && !Move->IsSliding();

	// 1. Steps: walking up or down stairs moves the capsule in jumps (MaxStepHeight); the view glides instead.
	//    A change bigger than any walkable slope explains (46 degrees) is a step.
	if (bHaveFeelZ && Move->MovementMode == MOVE_Walking)
	{
		const float Dz = static_cast<float>(Z - LastFeelZ);
		if (FMath::Abs(Dz) > 1.5f + Speed * Dt * 1.1f && FMath::Abs(Dz) < 60.0f)
		{
			StepSmooth = FMath::Clamp(StepSmooth - Dz, -60.0f, 60.0f);
		}
	}
	LastFeelZ = Z;
	bHaveFeelZ = true;
	StepSmooth = FMath::FInterpTo(StepSmooth, 0.0f, Dt, 11.0f);

	// 2. Landing: the view dips with the impact and springs back (stiff, slightly under-damped).
	if (Move->IsFalling())
	{
		LastAirVz = Velocity.Z;
	}
	const float Stiff = 190.0f, Damp = 2.0f * FMath::Sqrt(Stiff) * 0.72f;
	LandDipVel += (-Stiff * LandDip - Damp * LandDipVel) * Dt;
	LandDip = FMath::Clamp(LandDip + LandDipVel * Dt, -14.0f, 6.0f);

	// 3. Head bob in step with the footsteps (one dip per step, a sway per stride), never while aiming much.
	const float Stride = Move->IsSprinting() ? 240.0f : (bIsCrouched ? 140.0f : 185.0f);
	if (bGrounded)
	{
		BobPhase += Speed * Dt * PI / Stride;
	}
	const float Ads = AimProgress * AimProgress * (3.0f - 2.0f * AimProgress);
	const float WantAmp = bGrounded ? FMath::Min(Speed / 440.0f, 1.0f) * (Move->IsSprinting() ? 1.25f : 0.55f) * (1.0f - Ads * 0.85f) : 0.0f;
	BobAmp = FMath::FInterpTo(BobAmp, WantAmp * HeadBobScale, Dt, 6.0f);
	const float BobZ = -FMath::Abs(FMath::Sin(BobPhase)) * BobAmp + BobAmp * 0.5f;
	const float BobY = FMath::Sin(BobPhase * 0.5f) * BobAmp * 0.45f;

	// 4. Roll: into a slide, a touch toward a strafe, a whisper with the stride.
	const FVector Right = GetActorRightVector();
	const float Strafe = Move->IsMovingOnGround() ? FMath::Clamp(static_cast<float>(FVector::DotProduct(Velocity, Right)) / 440.0f, -1.0f, 1.0f) : 0.0f;
	const float WantRoll = (Move->IsSliding() ? -SlideCameraRoll : 0.0f) + Strafe * StrafeCameraRoll * (1.0f - Ads)
		+ FMath::Sin(BobPhase * 0.5f) * BobAmp * 0.25f;
	CameraRoll = FMath::FInterpTo(CameraRoll, WantRoll, Dt, 7.0f);

	// 5. Field of view widens with speed.
	const float WantFov = Move->IsSliding() ? SlideFovBoost : (Move->IsSprinting() ? SprintFovBoost * FMath::Clamp((Speed - 440.0f) / 420.0f, 0.0f, 1.0f) : 0.0f);
	FovBoost = FMath::FInterpTo(FovBoost, WantFov, Dt, 5.0f);

	FeelOffset = FVector(0.0f, BobY, StepSmooth + LandDip + BobZ);
}

void ASOCharacter::OnStartCrouch(float HalfHeightAdjust, float ScaledHalfHeightAdjust)
{
	Super::OnStartCrouch(HalfHeightAdjust, ScaledHalfHeightAdjust);
	LastFeelZ -= ScaledHalfHeightAdjust;   // the capsule centre moved, not the feet: no step
	// The capsule centre dropped; keep the eye where it was and let Tick ease it down.
	EyeOffset += ScaledHalfHeightAdjust;
	FirstPersonCamera->SetRelativeLocation(FVector(0.0f, 0.0f, EyeOffset));
}

void ASOCharacter::OnEndCrouch(float HalfHeightAdjust, float ScaledHalfHeightAdjust)
{
	Super::OnEndCrouch(HalfHeightAdjust, ScaledHalfHeightAdjust);
	LastFeelZ += ScaledHalfHeightAdjust;
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
	DOREPLIFETIME(ASOCharacter, Outfit);
}

void ASOCharacter::ToggleViewMode()
{
	SetViewMode(ViewMode == ESOViewMode::FirstPerson ? ESOViewMode::ThirdPerson : ESOViewMode::FirstPerson);
}

void ASOCharacter::ApplyViewMode()
{
	const bool bFirst = ViewMode == ESOViewMode::FirstPerson;
	const bool bEye = bFirst || bScopeView; // looking through a scope is always from the eye
	FirstPersonCamera->SetActive(bEye);
	ThirdPersonCamera->SetActive(!bEye);
	FirstPersonArms->SetVisibility(bFirst && !bScopeView, true);
	FirstPersonArms->SetComponentTickEnabled(bFirst);
	GetMesh()->SetOwnerNoSee(bEye);
	for (const TPair<FName, TObjectPtr<USkeletalMeshComponent>>& Piece : WornThirdPerson)
	{
		if (Piece.Value)
		{
			Piece.Value->SetOwnerNoSee(bEye);
		}
	}
	if (Weapon)
	{
		Weapon->SetFirstPersonView(bEye);
		if (Weapon->GetFirstPersonRig())
		{
			Weapon->GetFirstPersonRig()->SetShown(bFirst && !bScopeView);
		}
	}
}
