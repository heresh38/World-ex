#include "SOCharacter.h"

#include "SOAreaSubsystem.h"
#include "SOCombatStatics.h"
#include "SOCue.h"
#include "Components/SpotLightComponent.h"

#include "Misc/PackageName.h"

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
#include "SOFxSubsystem.h"
#include "Materials/MaterialInterface.h"
#include "PhysicalMaterials/PhysicalMaterial.h"
#include "Animation/AnimSequenceBase.h"
#include "Engine/SkeletalMesh.h"
#include "Net/UnrealNetwork.h"
#include "GameFramework/PlayerState.h"
#include "SOInventoryComponent.h"
#include "SOLootActors.h"
#include "SOLootLibrary.h"
#include "SOGunRigComponent.h"
#include "SOMelee.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "TimerManager.h"
#include "EngineUtils.h"
#include "Kismet/GameplayStatics.h"
#include "Components/CapsuleComponent.h"
#include "GameFramework/PlayerState.h"
#include "SOAbilitySystemComponent.h"
#include "SOKitComponent.h"
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
	static const TCHAR* Dodge = TEXT("/Game/Input/IA_Dodge.IA_Dodge");
	static const TCHAR* PadCrouchDodge = TEXT("/Game/Input/IA_PadCrouchDodge.IA_PadCrouchDodge");
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
	static const TCHAR* Flashlight = TEXT("/Game/Input/IA_Flashlight.IA_Flashlight");
	static const TCHAR* Grenade = TEXT("/Game/Input/IA_Grenade.IA_Grenade");
	static const TCHAR* Melee = TEXT("/Game/Input/IA_Melee.IA_Melee");
	static const TCHAR* ClassAbility = TEXT("/Game/Input/IA_ClassAbility.IA_ClassAbility");
	static const TCHAR* Ultimate = TEXT("/Game/Input/IA_Ultimate.IA_Ultimate");
	static const TCHAR* Fists = TEXT("/Game/Input/IA_Fists.IA_Fists");
	static const TCHAR* PadShoulderRight = TEXT("/Game/Input/IA_PadShoulderRight.IA_PadShoulderRight");
	static const TCHAR* PadShoulderLeft = TEXT("/Game/Input/IA_PadShoulderLeft.IA_PadShoulderLeft");
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
	FirstPersonArms->bReceivesDecals = false;
	FirstPersonArms->SetupAttachment(Capsule);
	FirstPersonArms->SetRelativeLocation(Body->GetRelativeLocation());
	ArmsBaseX = Body->GetRelativeLocation().X;                 // (the arms' own place along the body: the fists add to it)
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
	FlashlightAction = TSoftObjectPtr<UInputAction>(FSoftObjectPath(SOInputPaths::Flashlight));
	GrenadeAction = TSoftObjectPtr<UInputAction>(FSoftObjectPath(SOInputPaths::Grenade));
	MeleeAction = TSoftObjectPtr<UInputAction>(FSoftObjectPath(SOInputPaths::Melee));
	ClassAbilityAction = TSoftObjectPtr<UInputAction>(FSoftObjectPath(SOInputPaths::ClassAbility));
	UltimateAction = TSoftObjectPtr<UInputAction>(FSoftObjectPath(SOInputPaths::Ultimate));
	FistsAction = TSoftObjectPtr<UInputAction>(FSoftObjectPath(SOInputPaths::Fists));
	PadShoulderRightAction = TSoftObjectPtr<UInputAction>(FSoftObjectPath(SOInputPaths::PadShoulderRight));
	PadShoulderLeftAction = TSoftObjectPtr<UInputAction>(FSoftObjectPath(SOInputPaths::PadShoulderLeft));
	Flashlight = CreateDefaultSubobject<USpotLightComponent>(TEXT("Flashlight"));
	Flashlight->SetupAttachment(GetCapsuleComponent());
	Flashlight->SetUsingAbsoluteLocation(true);
	Flashlight->SetUsingAbsoluteRotation(true);
	Flashlight->SetIntensityUnits(ELightUnits::Candelas);
	// A torch: a hot spot thrown a long way and a soft spill round it (it was a short wide cone hung by the eye, and
	// read as a bulb carried about).
	Flashlight->SetIntensity(5200.0f);
	Flashlight->SetAttenuationRadius(6500.0f);
	Flashlight->SetInnerConeAngle(7.0f);
	Flashlight->SetOuterConeAngle(23.0f);
	Flashlight->SetSourceRadius(1.5f);
	Flashlight->SetLightColor(FLinearColor(1.0f, 0.95f, 0.86f));
	Flashlight->SetCastShadows(true);
	Flashlight->SetVolumetricScatteringIntensity(0.3f);
	Flashlight->SetVisibility(false);
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
		SetGearAttributes(Inventory->GetAttributePoints()); // what is worn counts: the body's six attributes
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
		const FSOWardrobeItem* Item = Outfit.Items.IsValidIndex(i) ? Wardrobe->Find(Outfit.Slots[i], Outfit.Items[i]) : nullptr;
		if (!Item && !USOWardrobeData::ArmourSlots().Contains(Outfit.Slots[i]))
		{
			// a slot that is never empty (hair, underwear) naming the other body's item: this body's own default
			Item = Wardrobe->Find(Outfit.Slots[i], Wardrobe->Defaults.FindRef(Outfit.Slots[i]));
		}
		if (Item)
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
				Piece->bReceivesDecals = false;
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
	ApplyFace();
	ApplyViewMode();
}

void ASOCharacter::ApplyFace()
{
	// the face's sliders: each a morph target face_<key> of the body (tools/blender/hero/orion: headcage.FACE_SLIDERS)
	USkeletalMeshComponent* Body = GetMesh();
	if (!Body)
	{
		return;
	}
	Body->ClearMorphTargets();
	for (int32 i = 0; i < FMath::Min(Outfit.FaceKeys.Num(), Outfit.FaceValues.Num()); ++i)
	{
		Body->SetMorphTarget(FName(*(TEXT("face_") + Outfit.FaceKeys[i].ToString())), Outfit.FaceValues[i]);
	}
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
		// (this body's newer clips: older imports do without them)
		auto Own = [this, &Clip](const TCHAR* Name) -> UAnimSequenceBase*
		{
			const FString Path = ClipPathPrefix + Name + TEXT(".") + FPaths::GetBaseFilename(ClipPathPrefix) + Name;
			return FPackageName::DoesPackageExist(FSoftObjectPath(Path).GetLongPackageName()) ? Clip(Name) : nullptr;
		};
		Anim->Clips.Stroll = Own(TEXT("Stroll"));
		Anim->Clips.Land = Own(TEXT("Land"));
		Anim->Clips.Vault = Own(TEXT("Vault"));
		Anim->Clips.Mantle = Own(TEXT("Mantle"));
		Anim->Clips.Climb = Own(TEXT("Climb"));
		Anim->Clips.Crouch = Own(TEXT("Crouch"));
		Anim->Clips.CrouchWalk = Own(TEXT("CrouchWalk"));
		Anim->Clips.Stop = Own(TEXT("Stop"));
		Anim->Clips.DodgeL = Own(TEXT("DodgeL"));
		Anim->Clips.DodgeR = Own(TEXT("DodgeR"));
		Anim->Clips.DodgeB = Own(TEXT("DodgeB"));
		Anim->Clips.DodgeF = Own(TEXT("DodgeF"));
		Anim->Clips.StrollSpeed = 150.0f;
		Anim->Clips.CrouchSpeed = GetCharacterMovement() ? GetCharacterMovement()->MaxWalkSpeedCrouched : 270.0f;
		Anim->Clips.Fidgets.Reset();
		for (int32 i = 1; i <= 8; ++i)                       // this body's idle variations (Fidget1..n)
		{
			const FString Name = FString::Printf(TEXT("Fidget%d"), i);
			const FString Path = ClipPathPrefix + Name + TEXT(".") + FPaths::GetBaseFilename(ClipPathPrefix) + Name;
			if (!FPackageName::DoesPackageExist(FSoftObjectPath(Path).GetLongPackageName()))
			{
				break;
			}
			if (UAnimSequenceBase* F = Clip(*Name))
			{
				Anim->Clips.Fidgets.Add(F);
			}
		}
		Anim->Clips.WalkSpeed = 440.0f;
		Anim->Clips.RunSpeed = 860.0f;
		AbilityClips.Reset(); // another body, another clip set
	}
}

void ASOCharacter::BeginPlay()
{
	Super::BeginPlay();
	// the eye's height, the arms' place under it and the camera's roll are set in this actor's tick; the gun is laid on
	// the eye (the viewmodel) and the arms reach for it after that, in the same frame, never from the frame before
	if (Viewmodel)
	{
		Viewmodel->AddTickPrerequisiteActor(this);
	}
	CurrentFov = GetHipFov();
	if (USOCharacterMovementComponent* Move = GetSOMovement())
	{
		Move->OnMovementEvent.AddUObject(this, &ASOCharacter::HandleMovementEvent);
	}
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
	if (bHeldStowed)
	{
		return false; // the gun is put away (a traversal, an ability's clip)
	}
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
	// Aiming x0.25 (on the sights a gun shoots where its sight is: at x0.45 a machine gun's cone was a quarter of a
	// scope's picture), moving x1.35, airborne x1.6.
	float Scale = FMath::Lerp(1.0f, 0.25f, AimProgress);
	if (HasStatus(SOTags::Status_Suppressed))
	{
		Scale *= 1.3f; // (rounds passing close: the aim is not as steady)
	}
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
			USOSoundLibrary::PlayFor(this, SurfaceSound(GetFloorSurface(), TEXT("footstep"), 4), GetActorLocation() - FVector(0, 0, 85.0f), Volume, ESOSoundRange::Near, 0.08f);
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
	if (HasAuthority())
	{
		if (const APlayerState* PS = GetPlayerState())
		{
			if (USOKitComponent* Kit = PS->FindComponentByClass<USOKitComponent>())
			{
				Kit->Remember(this); // the ultimate's charge goes to the next body
			}
		}
	}
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

void ASOCharacter::RefreshHolsters()
{
	const USOInventoryComponent* Inventory = GetInventory();
	USkeletalMeshComponent* Body = GetMesh();
	const USkeletalMesh* Asset = Body ? Body->GetSkeletalMeshAsset() : nullptr;
	const int32 Num = USOInventoryComponent::NumSlots;
	HolsterRigs.SetNum(Num);
	HolsterUids.SetNum(Num);
	HolsterPlaces.SetNum(Num);
	const USOLootTables* Tables = USOLootLibrary::GetTables();
	auto Drop = [this](int32 Slot)
	{
		if (HolsterRigs[Slot])
		{
			HolsterRigs[Slot]->Dismantle();                          // (with its meshes: they would stay on the body otherwise)
			HolsterRigs[Slot] = nullptr;
		}
		HolsterUids[Slot].Reset();
		HolsterPlaces[Slot] = NAME_None;
	};

	// 1. Which guns are worn: every equipped gun that is not in the hands (all of them while the hands are busy).
	TArray<int32, TInlineAllocator<4>> Order;
	int32 Stowed = INDEX_NONE;
	for (int32 Slot = 0; Slot < Num; ++Slot)
	{
		const FSOWeaponInstance* Copy = Inventory && Asset && !bDead ? Inventory->GetEquipped(Slot) : nullptr;
		const bool bHeld = Copy && Weapon && Weapon->GetInstance().Uid == Copy->Uid;
		if (!Copy || (bHeld && !bHeldStowed))
		{
			Drop(Slot);
			continue;
		}
		if (!HolsterRigs[Slot] || HolsterUids[Slot] != Copy->Uid)
		{
			Drop(Slot);
			USOWeaponData* Data = Tables ? Tables->LoadArchetype(Copy->Archetype) : nullptr;
			if (!Data)
			{
				continue;
			}
			USOGunRigComponent* Rig = NewObject<USOGunRigComponent>(this);
			Rig->SetupAttachment(Body);
			Rig->RegisterComponent();
			Rig->Build(Data, false);
			Rig->Dress(*Copy);
			HolsterRigs[Slot] = Rig;
			HolsterUids[Slot] = Copy->Uid;
		}
		if (bHeld)
		{
			Stowed = Slot;                                           // takes its place last: the others keep theirs
		}
		else
		{
			Order.Add(Slot);
		}
	}
	if (Stowed != INDEX_NONE)
	{
		Order.Add(Stowed);
	}
	if (Order.Num() == 0)
	{
		return;
	}

	// 2. Where. Every worn gun has a place of its own, sized from the gun itself (its bounds), so two never share a
	//    spot or pass through each other: long guns stand on the back side by side, muzzles up, one behind each
	//    shoulder with its top to the spine (the primary's home is the right, the special's the left, the heavy takes
	//    the free one; a third, the gun put away for a climb, lies across them); handguns hang at the hips, the first
	//    on the right, muzzle down and the grip to the rear (a third behind the belt).
	//    Rest pose, component space: +X the body's left, +Y forward, +Z up.
	const FReferenceSkeleton& Ref = Asset->GetRefSkeleton();
	auto RefCS = [&Ref](FName Bone)
	{
		FTransform T = FTransform::Identity;
		for (int32 I = Ref.FindBoneIndex(Bone); I != INDEX_NONE; I = Ref.GetParentIndex(I))
		{
			T = T * Ref.GetRefBonePose()[I];
		}
		return T;
	};
	const float K = FMath::Max(static_cast<float>(RefCS(TEXT("head")).GetLocation().Z) / 165.0f, 0.5f);
	const FVector Chest = RefCS(TEXT("chest")).GetLocation();
	const FVector Hips = RefCS(TEXT("hips")).GetLocation();
	const bool bFemale = Inventory->GetBody() == TEXT("female");
	// the clothed body's surface from its joints (cm): behind the chest, behind the belt, beside the hip joint
	// (a coat or jacket over the back adds its cloth and folded hood)
	const float BackDepth = ((bFemale ? HolsterBackDepth.Y : HolsterBackDepth.X) + (GetWornPiece(TEXT("outer"), false) ? HolsterCoat : 0.0f)) * K;
	const float BeltDepth = (bFemale ? 10.5f : 12.0f) * K;
	const float HipSide = (bFemale ? HolsterHipSide.Y : HolsterHipSide.X) * K;
	const float SpineGap = 1.6f;                                   // a back gun's top keeps this far from the midline
	const float ShoulderX = FMath::Max(FMath::Abs(static_cast<float>(RefCS(TEXT("upperarm_L")).GetLocation().X)), 12.0f);

	bool bBackTaken[2] = { false, false };
	bool bHipTaken[2] = { false, false };
	float BackOuter = BackDepth;                                   // how far behind the chest the back guns reach
	for (const int32 Slot : Order)
	{
		USOGunRigComponent* Rig = HolsterRigs[Slot];
		if (!Rig)
		{
			continue;
		}
		const FBox Box = Rig->GetWornBounds();
		FVector Corners[8];
		Box.GetVertices(Corners);
		auto Turned = [&Corners](const FQuat& Q)
		{
			FBox Out(ForceInit);
			for (const FVector& C : Corners)
			{
				Out += Q.RotateVector(C);
			}
			return Out;
		};
		FName Bone, Place;
		FQuat Rot;
		FVector At;
		if (Rig->IsHandgun())
		{
			const int32 Side = !bHipTaken[0] ? 0 : (!bHipTaken[1] ? 1 : 2);
			if (Side < 2)
			{
				bHipTaken[Side] = true;
				const float Sign = Side == 0 ? -1.0f : 1.0f;           // -X is the body's right
				Bone = Side == 0 ? TEXT("thigh_R") : TEXT("thigh_L");
				Place = Side == 0 ? TEXT("hip_right") : TEXT("hip_left");
				Rot = FRotationMatrix::MakeFromXZ(FVector(0.0f, 0.10f, -0.995f), FVector(0.0f, 1.0f, 0.0f)).ToQuat();
				const FBox B = Turned(Rot);
				const FVector Joint = RefCS(Bone).GetLocation();
				// its inner side on the hip's surface, the top of the grip just under the hip joint
				At = FVector(Joint.X + Sign * HipSide - (Sign < 0.0f ? B.Max.X : B.Min.X), Joint.Y + 1.0f * K, Joint.Z - 3.0f * K);
			}
			else
			{
				Bone = TEXT("hips");
				Place = TEXT("belt_back");
				Rot = FRotationMatrix::MakeFromXZ(FVector(0.94f, 0.0f, -0.34f), FVector(0.34f, 0.0f, 0.94f)).ToQuat();
				const FBox B = Turned(Rot);
				At = FVector(-B.GetCenter().X, Hips.Y - BeltDepth - 1.0f - B.Max.Y, Hips.Z + 5.0f * K - B.GetCenter().Z);
			}
		}
		else
		{
			Bone = TEXT("chest");
			const int32 Home = Slot == 0 ? 0 : (Slot == 1 ? 1 : (bBackTaken[0] ? 1 : 0));
			const int32 Side = !bBackTaken[Home] ? Home : (!bBackTaken[1 - Home] ? 1 - Home : 2);
			if (Side < 2)
			{
				bBackTaken[Side] = true;
				const float Sign = Side == 0 ? -1.0f : 1.0f;
				Place = Side == 0 ? TEXT("back_right") : TEXT("back_left");
				// Flat on the back behind its shoulder, muzzle up and a little out, its top to the spine and the grip
				// outward. It is placed by its bore line (the rig's own origin), never by its outline: a gun with fins
				// or a tall sight would otherwise be pushed out past the shoulder. The line sits as far from the spine
				// as the gun's top needs, but always inside the shoulder's width.
				Rot = FRotationMatrix::MakeFromXZ(FVector(Sign * 0.10f, 0.0f, 0.995f), FVector(-Sign, 0.0f, 0.0f)).ToQuat();
				const FBox B = Turned(Rot);
				const float Line = FMath::Clamp(static_cast<float>(Box.Max.Z) + SpineGap, ShoulderX * 0.42f, ShoulderX * 0.62f);
				// (its side on the back: the flat of the receiver, not the tip of a fin)
				const float Thick = FMath::Min(static_cast<float>(Side == 0 ? -Box.Min.Y : Box.Max.Y), 6.5f);
				const float Middle = static_cast<float>(Chest.Z) + 1.0f * K;
				const float Low = FMath::Max(Middle - 0.5f * static_cast<float>(B.GetSize().Z), static_cast<float>(Hips.Z) - 6.0f * K);
				At = FVector(Sign * Line, Chest.Y - BackDepth - 1.0f - Thick - (Side == 1 ? 1.5f : 0.0f), Low - B.Min.Z);
				BackOuter = FMath::Max(BackOuter, BackDepth + 2.5f + 2.0f * Thick);
			}
			else
			{
				// both sides taken: slung across the two, outside them
				Place = TEXT("back_across");
				Rot = FRotationMatrix::MakeFromXZ(FVector(-0.56f, 0.0f, 0.83f), FVector(0.83f, 0.0f, 0.56f)).ToQuat();
				const FBox B = Turned(Rot);
				At = FVector(-B.GetCenter().X, Chest.Y - BackOuter - 1.0f - B.Max.Y, Chest.Z + 1.0f * K - B.GetCenter().Z);
			}
		}
		if (HolsterPlaces[Slot] != Place || Rig->GetAttachSocketName() != Bone)
		{
			const FTransform Desired(Rot, At);
			Rig->AttachToComponent(Body, FAttachmentTransformRules::KeepRelativeTransform, Bone);
			Rig->SetRelativeTransform(Desired.GetRelativeTransform(RefCS(Bone)));
			HolsterPlaces[Slot] = Place;
		}
		Rig->SetShown(true);
		Rig->SetOwnerNoSeeAll(Body->bOwnerNoSee);
	}
}

void ASOCharacter::Tick(float DeltaSeconds)
{
	TickFootstepNoise(DeltaSeconds);
	if (const USOCharacterMovementComponent* SOMove = GetSOMovement())
	{
		// a joined player's aim reaches the server with their moves; from here it goes on to everyone else
		if (HasAuthority() && !IsLocallyControlled())
		{
			bAiming = SOMove->WantsToAim() && !bDead;
		}
		if (AbilitySystem)
		{
			AbilitySystem->SetState(SOTags::State_Aiming, bAiming);
			AbilitySystem->SetState(SOTags::State_Sprinting, SOMove->IsSprinting());
			AbilitySystem->SetState(SOTags::State_Traversing, SOMove->IsMantling());
		}
	}
	// the hands are busy on a vault, a mantle or a climb: the gun in them goes to its holster and comes back after
	if (const USOCharacterMovementComponent* SOMove = GetSOMovement())
	{
		// (and while the body plays an ability's clip: a throw, a blow, a brace)
		const USOLocomotionAnimInstance* BodyAnim = GetMesh() ? Cast<USOLocomotionAnimInstance>(GetMesh()->GetAnimInstance()) : nullptr;
		const bool bStow = (SOMove->IsMantling() || (BodyAnim && BodyAnim->IsPlayingAction()) || bFists) && !bDead;
		if (bStow != bHeldStowed)
		{
			bHeldStowed = bStow;
			if (Weapon && Weapon->GetThirdPersonRig())
			{
				Weapon->GetThirdPersonRig()->SetShown(!bStow);
			}
			// (first person: the hands go onto the edge too, so the gun is out of them and comes back up after)
			if (Weapon && Weapon->GetFirstPersonRig())
			{
				Weapon->GetFirstPersonRig()->SetShown(!bStow);
			}
			if (!bStow && Viewmodel)
			{
				Viewmodel->Raise();
			}
			HolsterTimer = 0.0f;
		}
	}
	UpdateMeleeGuard();
	UpdateBlade();
	HolsterTimer -= DeltaSeconds;
	if (HolsterTimer <= 0.0f)
	{
		HolsterTimer = 0.2f;
		RefreshHolsters();
	}
	if (bFlashlightOn)
	{
		// The torch is on the gun: the beam leaves just ahead of the muzzle, so it lights what the gun points at and
		// never the gun or the hands holding it (by the eye, the gun stood in its own beam: white, with its shadow over
		// everything). It is turned onto what the aim is on, so the hot spot sits under the crosshair. No gun in the
		// hands (stowed on a ledge): from just ahead of the chest.
		const FRotator Aim = IsLocallyControlled() ? GetControlRotation() : GetBaseAimRotation();
		const bool bFirst = IsFirstPersonView();
		const FVector Eye = bFirst ? FirstPersonCamera->GetComponentLocation() : GetPawnViewLocation();
		const USOGunRigComponent* Rig = Weapon && !bHeldStowed ? (bFirst ? Weapon->GetFirstPersonRig() : Weapon->GetThirdPersonRig()) : nullptr;
		const FVector From = Rig ? Rig->GetMuzzleLocation() + Aim.RotateVector(FVector(8.0f, 0.0f, -4.0f))
			: (bFirst ? Eye + Aim.RotateVector(FVector(34.0f, 10.0f, -14.0f)) : GetActorLocation() + GetActorRotation().RotateVector(FVector(34.0f, -14.0f, 42.0f)));
		FVector On = Eye + Aim.Vector() * 3000.0f;
		FHitResult Hit;
		FCollisionQueryParams Params(SCENE_QUERY_STAT(SOTorch), false, this);
		if (GetWorld()->LineTraceSingleByChannel(Hit, Eye + Aim.Vector() * 60.0f, On, ECC_Visibility, Params))
		{
			On = Hit.ImpactPoint;
		}
		// (close to a wall the two lines cross steeply: never turn the beam more than a little off the aim)
		const FVector Dir = (On - From).GetSafeNormal();
		const FVector Blend = FVector::DotProduct(Dir, Aim.Vector()) > 0.94f ? Dir : Aim.Vector();
		Flashlight->SetWorldLocationAndRotation(From, Blend.Rotation());
	}
	Super::Tick(DeltaSeconds);

	UpdateFeedbackSounds(DeltaSeconds);

	// Recoil recovers on its own; the camera shows it as an additive pitch.
	RecoilKick = FMath::Max(0.0f, RecoilKick - DeltaSeconds * RecoilRecovery);
	AbilityKick = FMath::FInterpTo(AbilityKick, 0.0f, DeltaSeconds, 9.0f);
	UpdateCameraFeel(DeltaSeconds);
	for (UCameraComponent* Camera : { FirstPersonCamera.Get(), ThirdPersonCamera.Get() })
	{
		Camera->ClearAdditiveOffset();
		const bool bEyeCam = Camera == FirstPersonCamera.Get();
		const float Roll = bEyeCam ? CameraRoll + ShakeRoll : 0.0f;
		const float Pitch = GetRecoilPitch() + AbilityKick + (bEyeCam ? FeelPitch : 0.0f);
		if (FMath::Abs(Pitch) > 1e-3f || FMath::Abs(Roll) > 1e-3f)
		{
			Camera->AddAdditiveOffset(FTransform(FRotator(Pitch, 0.0f, Roll)), 0.0f);
		}
	}

	// Eye height eases across crouch / slide transitions (a damped spring: it drops into a slide and comes up out of
	// it with a settle, the owner's "fluid, like water"); steps, landings and the head bob ride on top.
	{
		const float Dt = FMath::Min(DeltaSeconds, 0.05f);
		const float Omega = EyeHeightInterpSpeed * 1.1f, Zeta = 0.86f;
		EyeVel += (Omega * Omega * (GetTargetEyeOffset() - EyeOffset) - 2.0f * Zeta * Omega * EyeVel) * Dt;
		EyeOffset += EyeVel * Dt;
	}
	FirstPersonCamera->SetRelativeLocation(FVector(0.0f, 0.0f, EyeOffset) + FeelOffset);
	// The first-person arms hang from the eye, not from the capsule. Crouched (or sliding) the capsule's centre drops
	// and the eye comes down to it: left on the capsule, the arms' shoulders ended up above the camera and the arms
	// reached down into the view from overhead. Their shoulders keep their place under the eye exactly as standing.
	// With the fists up the arms stand a little forward and lower (the guard is at the chin: from the eye the fists filled
	// the bottom corners of the view; a hand to hand view shows them ahead, under the line of sight).
	FistsView = FMath::FInterpTo(FistsView, bFists ? 1.0f : 0.0f, DeltaSeconds, 8.0f);
	const FVector ArmsAt = FirstPersonArms->GetRelativeLocation();
	const float ArmsX = ArmsBaseX;
	FirstPersonArms->SetRelativeLocation(FVector(ArmsX + FistsForward * FistsView, ArmsAt.Y, EyeOffset - StandingEyeHeight - FistsDrop * FistsView));

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
	{
		const USOCharacterMovementComponent* SOMove = GetSOMovement();
		const float Want = SOMove && SOMove->IsSprinting() ? FMath::Clamp((GetVelocity().Size2D() - 440.0f) / 420.0f, 0.0f, 1.0f) : 0.0f;
		SprintView = FMath::FInterpTo(SprintView, Want, DeltaSeconds, 4.0f);
	}
	ThirdPersonBoom->TargetArmLength = FMath::Lerp(HipArmLength, AimArmLength, Ads) + SprintArmExtra * SprintView * (1.0f - Ads);
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
	if (UInputAction* A = Load(PadCrouchDodgeAction))
	{
		Input->BindAction(A, ETriggerEvent::Started, this, &ASOCharacter::HandlePadCrouchDodgePressed);
		Input->BindAction(A, ETriggerEvent::Completed, this, &ASOCharacter::HandlePadCrouchDodgeReleased);
	}
	if (UInputAction* A = Load(DodgeAction)) { Input->BindAction(A, ETriggerEvent::Started, this, &ASOCharacter::HandleDodgePressed); }
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
	if (UInputAction* A = Load(ReloadAction))
	{
		Input->BindAction(A, ETriggerEvent::Started, this, &ASOCharacter::HandleReload);
		Input->BindAction(A, ETriggerEvent::Completed, this, &ASOCharacter::HandleReloadReleased);
	}
	if (UInputAction* A = Load(Weapon1Action)) { Input->BindAction(A, ETriggerEvent::Started, this, &ASOCharacter::HandleWeapon1); }
	if (UInputAction* A = Load(Weapon2Action)) { Input->BindAction(A, ETriggerEvent::Started, this, &ASOCharacter::HandleWeapon2); }
	if (UInputAction* A = Load(Weapon3Action)) { Input->BindAction(A, ETriggerEvent::Started, this, &ASOCharacter::HandleWeapon3); }
	if (UInputAction* A = Load(FistsAction)) { Input->BindAction(A, ETriggerEvent::Started, this, &ASOCharacter::HandleFists); }
	if (UInputAction* A = Load(NextWeaponAction)) { Input->BindAction(A, ETriggerEvent::Started, this, &ASOCharacter::HandleNextWeapon); }
	if (UInputAction* A = Load(PrevWeaponAction)) { Input->BindAction(A, ETriggerEvent::Started, this, &ASOCharacter::HandlePrevWeapon); }
	if (UInputAction* A = Load(InventoryAction)) { Input->BindAction(A, ETriggerEvent::Started, this, &ASOCharacter::HandleInventory); }
	if (UInputAction* A = Load(MapAction)) { Input->BindAction(A, ETriggerEvent::Started, this, &ASOCharacter::HandleMap); }
	if (UInputAction* A = Load(FlashlightAction)) { Input->BindAction(A, ETriggerEvent::Started, this, &ASOCharacter::HandleFlashlight); }
	if (UInputAction* A = Load(GrenadeAction)) { Input->BindAction(A, ETriggerEvent::Started, this, &ASOCharacter::HandleGrenade); }
	if (UInputAction* A = Load(MeleeAction)) { Input->BindAction(A, ETriggerEvent::Started, this, &ASOCharacter::HandleMelee); }
	if (UInputAction* A = Load(ClassAbilityAction)) { Input->BindAction(A, ETriggerEvent::Started, this, &ASOCharacter::HandleClassAbility); }
	if (UInputAction* A = Load(UltimateAction)) { Input->BindAction(A, ETriggerEvent::Started, this, &ASOCharacter::HandleUltimate); }
	if (UInputAction* A = Load(PadShoulderRightAction))
	{
		Input->BindAction(A, ETriggerEvent::Started, this, &ASOCharacter::HandlePadRightDown);
		Input->BindAction(A, ETriggerEvent::Completed, this, &ASOCharacter::HandlePadRightUp);
	}
	if (UInputAction* A = Load(PadShoulderLeftAction))
	{
		Input->BindAction(A, ETriggerEvent::Started, this, &ASOCharacter::HandlePadLeftDown);
		Input->BindAction(A, ETriggerEvent::Completed, this, &ASOCharacter::HandlePadLeftUp);
	}

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

void ASOCharacter::HandlePadCrouchDodgePressed()
{
	// the dodge when the stick is pushed at a walk or a run (not at a sprint: that is the slide, as before; not
	// crouched, in the air or already stepping out)
	const USOCharacterMovementComponent* Move = GetSOMovement();
	const bool bOnTheMove = Move && Move->IsMovingOnGround() && !Move->IsSprinting() && !Move->IsSliding() && !Move->IsDodging()
		&& !bIsCrouched && !bCrouchLatched && GetVelocity().Size2D() < Move->SlideEnterSpeed
		&& Move->GetCurrentAcceleration().SizeSquared() > FMath::Square(Move->GetMaxAcceleration() * 0.4f);
	bPadPressWasDodge = bOnTheMove && !bDead;
	if (bPadPressWasDodge)
	{
		HandleDodgePressed();
		return;
	}
	HandleCrouchPressed();
}

void ASOCharacter::HandlePadCrouchDodgeReleased()
{
	if (bPadPressWasDodge)
	{
		bPadPressWasDodge = false;
		return;
	}
	HandleCrouchReleased();
}

void ASOCharacter::HandleDodgePressed()
{
	if (USOCharacterMovementComponent* Move = GetSOMovement(); Move && !bDead)
	{
		Move->SetWantsToDodge(true);
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
	USOInteractables* Things = GetWorld() ? GetWorld()->GetSubsystem<USOInteractables>() : nullptr;
	if (!Things)
	{
		return nullptr;
	}
	for (const TWeakObjectPtr<AActor>& It : Things->Get())
	{
		const ISOInteractable* Thing = Cast<ISOInteractable>(It.Get());
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
			Best = It.Get();
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
	if (bFists)
	{
		MeleeStrike(false);
		return;
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

UAnimSequenceBase* ASOCharacter::GetAbilityClip(FName Name)
{
	if (Name.IsNone())
	{
		return nullptr;
	}
	if (const TObjectPtr<UAnimSequenceBase>* Known = AbilityClips.Find(Name))
	{
		return *Known;
	}
	// once per clip and body (the arrival has loaded the body's folder already): never in a tick
	const FString Path = ClipPathPrefix + Name.ToString() + TEXT(".") + FPaths::GetBaseFilename(ClipPathPrefix) + Name.ToString();
	UAnimSequenceBase* Clip = FPackageName::DoesPackageExist(FSoftObjectPath(Path).GetLongPackageName())
		? TSoftObjectPtr<UAnimSequenceBase>(FSoftObjectPath(Path)).LoadSynchronous() : nullptr;
	AbilityClips.Add(Name, Clip);
	return Clip;
}

void ASOCharacter::BeginAbilityShow(ESOAbilitySlot Slot)
{
	// its own player sees the hands go to it: the gun drops out of the way and comes back
	if (Viewmodel)
	{
		Viewmodel->Raise();
	}
	const FSOAbilityGrant* Grant = GetAbilitySet() ? GetAbilitySet()->Find(Slot) : nullptr;
	USOLocomotionAnimInstance* BodyAnim = GetMesh() ? Cast<USOLocomotionAnimInstance>(GetMesh()->GetAnimInstance()) : nullptr;
	if (!Grant || !BodyAnim || bDead)
	{
		return;
	}
	// The clip is the whole body with its feet planted: standing (or nearly) it plays; on the move the legs keep
	// their own gait and it is left out.
	if (GetVelocity().Size2D() < 200.0f && !GetCharacterMovement()->IsFalling())
	{
		if (UAnimSequenceBase* Clip = GetAbilityClip(Grant->Clip))
		{
			BodyAnim->PlayAction(Clip, 1.0f);
		}
	}
}

void ASOCharacter::OnAbilityWindUp(ESOAbilitySlot Slot)
{
	Super::OnAbilityWindUp(Slot);
	BeginAbilityShow(Slot);
}

void ASOCharacter::OnAbilityUsed(ESOAbilitySlot Slot)
{
	Super::OnAbilityUsed(Slot);
	const FSOAbilityGrant* Grant = GetAbilitySet() ? GetAbilitySet()->Find(Slot) : nullptr;
	if (!Grant || Grant->WindUp <= 0.0f)
	{
		BeginAbilityShow(Slot); // no wind-up: it shows as it happens
	}
	// the blow itself pitches the view
	if (IsLocallyControlled())
	{
		AbilityKick = Slot == ESOAbilitySlot::Ultimate ? -8.0f : (Slot == ESOAbilitySlot::Melee ? -3.5f : (Slot == ESOAbilitySlot::Grenade ? 1.5f : 0.0f));
	}
}

void ASOCharacter::HandlePadShoulder(bool bRight, bool bDown)
{
	// A pad has no buttons left for a fourth ability, so the two shoulders together are the ultimate. A shoulder
	// pressed alone therefore waits PadChordWindow for the other before it counts (the keyboard's keys do not wait).
	const int32 Side = bRight ? 1 : 0;
	bPadShoulderDown[Side] = bDown;
	UWorld* World = GetWorld();
	if (!bDown || !World)
	{
		return;
	}
	FTimerManager& Timers = World->GetTimerManager();
	if (bPadShoulderDown[1 - Side])
	{
		Timers.ClearTimer(PadChordTimer); // the first one's own ability is dropped: this is the pair
		ActivateSlot(ESOAbilitySlot::Ultimate);
		return;
	}
	const ESOAbilitySlot Alone = bRight ? ESOAbilitySlot::Grenade : ESOAbilitySlot::Melee;
	Timers.SetTimer(PadChordTimer, FTimerDelegate::CreateWeakLambda(this, [this, Alone]() { ActivateSlot(Alone); }), FMath::Max(PadChordWindow, 0.01f), false);
}

void ASOCharacter::HandleGrenade() { ActivateSlot(ESOAbilitySlot::Grenade); }
void ASOCharacter::HandleMelee() { ActivateSlot(ESOAbilitySlot::Melee); }
void ASOCharacter::HandleClassAbility() { ActivateSlot(ESOAbilitySlot::Class); }
void ASOCharacter::HandleUltimate() { ActivateSlot(ESOAbilitySlot::Ultimate); }

void ASOCharacter::HandleAimPressed()
{
	if (bDead)
	{
		return;
	}
	if (bFists)
	{
		MeleeStrike(true);
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
	if (bFists)
	{
		SetBlocking(true);                                   // (hand to hand: the reload key is the guard)
		return;
	}
	if (Weapon && !bDead)
	{
		Weapon->StartReload();
	}
}

void ASOCharacter::HandleReloadReleased()
{
	SetBlocking(false);
}

void ASOCharacter::HandleWeapon1() { SelectSlot(0); }
void ASOCharacter::HandleWeapon2() { SelectSlot(1); }
void ASOCharacter::HandleWeapon3() { SelectSlot(2); }
void ASOCharacter::HandleFists()
{
	// the gun <-> what is in the loadout's melee slot (a blade, or the fists when it is empty)
	if (bFists)
	{
		SetFists(false);
		return;
	}
	const USOInventoryComponent* Inventory = GetInventory();
	const FName Blade = Inventory ? Inventory->GetMeleeSlot() : NAME_None;
	SetMeleeStyle(Blade.IsNone() ? FName(TEXT("fists")) : Blade);
	SetFists(true);
}
void ASOCharacter::HandleNextWeapon() { CycleSlot(1); }
void ASOCharacter::HandlePrevWeapon() { CycleSlot(-1); }

void ASOCharacter::HandleFlashlight()
{
	SetFlashlight(!bFlashlightOn);
}

void ASOCharacter::SetFlashlight(bool bOn)
{
	if (!HasAuthority())
	{
		ServerSetFlashlight(bOn);
	}
	bFlashlightOn = bOn;
	OnRep_Flashlight();
}

void ASOCharacter::ServerSetFlashlight_Implementation(bool bOn)
{
	bFlashlightOn = bOn;
	OnRep_Flashlight();
}

void ASOCharacter::OnRep_Flashlight()
{
	Flashlight->SetVisibility(bFlashlightOn && !IsDead());
	USOSoundLibrary::PlayAt(this, bFlashlightOn ? TEXT("torch_on") : TEXT("torch_off"), GetActorLocation() + FVector(0, 0, 50.0f), 0.6f, 0.05f, ESOSoundRange::Near);
}

void ASOCharacter::TickFootstepNoise(float DeltaSeconds)
{
	const UCharacterMovementComponent* Move = GetCharacterMovement();
	const float Speed = GetVelocity().Size2D();
	if (!HasAuthority() || IsDead() || !Move->IsMovingOnGround() || bIsCrouched || Speed < 180.0f)
	{
		FootstepTimer = 0.0f;
		return;
	}
	FootstepTimer -= DeltaSeconds;
	if (FootstepTimer > 0.0f)
	{
		return;
	}
	const bool bRunning = Speed > 650.0f;
	FootstepTimer = bRunning ? 0.35f : 0.5f;
	USOCombatStatics::ReportNoise(this, GetActorLocation(), this, bRunning ? 1400.0f : 500.0f);
}

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
	// Travel takes everyone along, so it is the host's to start (later: the squad's leader). A joined player's
	// request arrives here on the server, where their controller is not a local one.
	if (const AController* Pilot = GetController(); !Pilot || !Pilot->IsLocalController())
	{
		UE_LOG(LogShatteredOrbit, Log, TEXT("Travel: only the host can take the squad to another area"));
		return;
	}
	StoreWeaponAmmo();
	// one area at a time: the subsystem lets go of this one before the next is built
	if (USOAreaSubsystem* Areas = USOAreaSubsystem::Get(this); !Areas || !Areas->TravelToLevel(Level))
	{
		UE_LOG(LogShatteredOrbit, Warning, TEXT("Travel: %s is not a listed area (Data/areas.json)"), *Level);
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
	if (!Inventory || bDead || !Inventory->GetEquipped(Slot))
	{
		return;
	}
	if (bFists)
	{
		SetFists(false);
	}
	if (Slot != Inventory->GetActiveSlot())
	{
		Inventory->ServerSelectSlot(Slot);
	}
}

void ASOCharacter::CycleSlot(int32 Step)
{
	const USOInventoryComponent* Inventory = GetInventory();
	if (!Inventory)
	{
		return;
	}
	// the hands are one more stop on the wheel, after the last gun and before the first
	const int32 Num = USOInventoryComponent::NumSlots;
	if (bFists)
	{
		for (int32 i = 0; i < Num; ++i)
		{
			const int32 Slot = Step > 0 ? i : Num - 1 - i;
			if (Inventory->GetEquipped(Slot))
			{
				SelectSlot(Slot);
				return;
			}
		}
		return;
	}
	for (int32 i = 1; i <= Num; ++i)
	{
		const int32 Raw = Inventory->GetActiveSlot() + Step * i;
		if (Raw >= Num || Raw < 0)
		{
			SetFists(true);
			return;
		}
		if (Inventory->GetEquipped(Raw))
		{
			SelectSlot(Raw);
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
	// the kit lives with the player, the abilities on the body: a new body is given them again (server)
	if (const APlayerState* PS = GetPlayerState())
	{
		if (USOKitComponent* Kit = PS->FindComponentByClass<USOKitComponent>())
		{
			Kit->Apply(this);
		}
	}
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
	RefreshHolsters();
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

void ASOCharacter::MoveBlockedBy(const FHitResult& Impact)
{
	Super::MoveBlockedBy(Impact);
	const AActor* Other = Impact.GetActor();
	const UWorld* World = GetWorld();
	if (Other && World && Other->ActorHasTag(TEXT("SONet")) && World->GetTimeSeconds() - LastNetReport > 4.0)
	{
		LastNetReport = World->GetTimeSeconds();
		const FVector P = GetActorLocation();
		UE_LOG(LogShatteredOrbit, Warning, TEXT("Boundary net touched at E %.1f N %.1f z %.1f m (a way out of the map: close it with something real)"),
			P.Y / 100.0f, P.X / 100.0f, P.Z / 100.0f);
	}
}

void ASOCharacter::Landed(const FHitResult& Hit)
{
	Super::Landed(Hit);
	// the view dips with the impact (the spring in UpdateCameraFeel brings it back)
	LandDipVel -= FMath::Clamp((-LastAirVz - 150.0f) * 0.16f, 0.0f, 190.0f);

	const USOCharacterMovementComponent* Move = GetSOMovement();
	// fall damage (off unless the movement component's FallDamageMinSpeed is set)
	if (const float Damage = Move ? Move->GetFallDamage(Move->GetLastLandSpeed()) : 0.0f; Damage > 0.0f && HasAuthority())
	{
		USOCombatStatics::ApplyDamage(this, this, Damage, false);
	}
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

FName ASOCharacter::GetFloorSurface() const
{
	// (one rule for the feet and the rounds: USOFxSubsystem::SurfaceOf reads the floor's own names)
	return USOFxSubsystem::SurfaceName(USOFxSubsystem::SurfaceOf(GetCharacterMovement()->CurrentFloor.HitResult));
}

FName ASOCharacter::SurfaceSound(FName Surface, const TCHAR* Kind, int32 Takes)
{
	const int32 Take = FMath::RandRange(1, FMath::Max(Takes, 1));
	if (Surface != TEXT("concrete") && !Surface.IsNone())
	{
		const FName Own(*FString::Printf(TEXT("%s_%s_%d"), Kind, *Surface.ToString(), Take));
		if (USOSoundLibrary::Find(Own))
		{
			return Own;
		}
	}
	return FName(*FString::Printf(TEXT("%s_%d"), Kind, Take));
}

void ASOCharacter::KickDust(float Strength, const FVector& Along)
{
	UWorld* World = GetWorld();
	USOFxSubsystem* Fx = World && World->GetNetMode() != NM_DedicatedServer ? World->GetSubsystem<USOFxSubsystem>() : nullptr;
	if (!Fx || Strength <= 0.0f)
	{
		return;
	}
	const FVector Feet = GetActorLocation() - FVector(0.0f, 0.0f, GetCapsuleComponent()->GetScaledCapsuleHalfHeight() - 4.0f);
	const int32 Puffs = FMath::Clamp(FMath::RoundToInt(3.0f + Strength * 5.0f), 3, 9);
	for (int32 i = 0; i < Puffs; ++i)
	{
		const float Angle = (i + FMath::FRand()) * 2.0f * PI / Puffs;
		const FVector Out(FMath::Cos(Angle), FMath::Sin(Angle), 0.0f);
		FSOFxParticle P;
		P.Kind = ESOFxKind::Smoke;
		P.Position = Feet + Out * 14.0f;
		P.Velocity = Out * (50.0f + 70.0f * Strength) + Along * 0.25f + FVector(0.0f, 0.0f, 18.0f + 22.0f * FMath::FRand());
		P.Drag = 3.2f;
		P.Life = 0.55f + 0.35f * FMath::FRand();
		P.Size0 = 12.0f + 6.0f * Strength;
		P.Size1 = 46.0f + 30.0f * Strength;
		P.Intensity0 = 0.16f + 0.10f * FMath::Min(Strength, 1.0f);
		P.Intensity1 = 0.0f;
		P.Color = FLinearColor(0.62f, 0.60f, 0.56f);
		Fx->Spawn(P);
	}
}

void ASOCharacter::HandleMovementEvent(ESOMovementEvent Event, float Strength)
{
	UWorld* World = GetWorld();
	if (!World || World->GetNetMode() == NM_DedicatedServer || bDead)
	{
		return;
	}
	const FVector Feet = GetActorLocation() - FVector(0.0f, 0.0f, 85.0f);
	const FVector Flat(GetVelocity().X, GetVelocity().Y, 0.0f);
	switch (Event)
	{
	case ESOMovementEvent::Jumped:
		USOSoundLibrary::PlayFor(this, TEXT("move_jump"), Feet, 0.45f, ESOSoundRange::Near, 0.06f);
		break;
	case ESOMovementEvent::AirJumped:
		USOSoundLibrary::PlayFor(this, TEXT("move_airjump"), Feet, 0.55f, ESOSoundRange::Near, 0.05f);
		LandDipVel -= 28.0f;                                     // a short push under the view
		KickDust(0.35f, -Flat);
		break;
	case ESOMovementEvent::Landed:
		if (HasAuthority() && Strength > 550.0f)
		{
			USOCombatStatics::ReportNoise(this, GetActorLocation(), this, FMath::Clamp(Strength * 1.1f, 600.0f, 1800.0f)); // (the harder the landing, the further it carries)
		}
	{
		// the sound of the surface, heavier with the fall; a hard one kicks up dust
		const float Hard = FMath::Clamp((Strength - 500.0f) / 1100.0f, 0.0f, 1.0f);
		if (Strength > 220.0f)
		{
			USOSoundLibrary::PlayFor(this, SurfaceSound(GetFloorSurface(), TEXT("footstep"), 4), Feet, 0.5f + 0.4f * Hard, ESOSoundRange::Near, 0.05f);
			USOSoundLibrary::PlayFor(this, Hard > 0.45f ? TEXT("move_land_hard") : TEXT("move_land_soft"), Feet, 0.35f + 0.5f * Hard, ESOSoundRange::Near, 0.05f);
		}
		if (Hard > 0.25f)
		{
			KickDust(Hard, Flat);
		}
		if (Hard > 0.2f)
		{
			ShakeRollVel += LandShakeRoll * 36.0f * Hard;        // a knock the view wobbles out of (UpdateCameraFeel)
		}
		StepDistance = 0.0f;
		break;
	}
	case ESOMovementEvent::DodgeStarted:
		USOSoundLibrary::PlayFor(this, TEXT("move_airjump"), Feet, 0.4f, ESOSoundRange::Near, 0.05f);
		LandDipVel -= 16.0f;                                     // the push off
		KickDust(0.4f, -Flat);
		break;
	case ESOMovementEvent::SlideStarted:
		if (HasAuthority())
		{
			USOCombatStatics::ReportNoise(this, GetActorLocation(), this, 1200.0f); // (a slide scrapes: creatures hear it)
		}
		if (ASOWeapon* Held = GetWeapon(); Held && HasAuthority() && Held->GetStats().Perks.bSlideReload)
		{
			Held->RefillFromReserve(); // (Slide Feed: going into a slide fills the magazine)
		}
		USOSoundLibrary::PlayFor(this, TEXT("move_slide"), Feet, 0.6f, ESOSoundRange::Near, 0.05f);
		KickDust(0.5f, Flat);
		break;
	case ESOMovementEvent::VaultStarted:
		USOSoundLibrary::PlayFor(this, TEXT("move_vault"), Feet + FVector(0, 0, 80.0f), 0.55f, ESOSoundRange::Near, 0.05f);
		break;
	case ESOMovementEvent::MantleStarted:
	case ESOMovementEvent::ClimbStarted:
		USOSoundLibrary::PlayFor(this, TEXT("move_mantle"), Feet + FVector(0, 0, 120.0f), 0.55f, ESOSoundRange::Near, 0.05f);
		break;
	case ESOMovementEvent::TraversalEnded:
		USOSoundLibrary::PlayFor(this, SurfaceSound(GetFloorSurface(), TEXT("footstep"), 4), Feet, 0.5f, ESOSoundRange::Near, 0.05f);
		LandDipVel -= 22.0f;                                     // the feet meet the ground again
		break;
	default:
		break;
	}
}

void ASOCharacter::UpdateCameraFeel(float DeltaSeconds)
{
	const float Dt = FMath::Max(DeltaSeconds, 1e-4f);
	const USOCharacterMovementComponent* Move = GetSOMovement();
	const bool bFeel = Move && IsLocallyControlled() && ViewMode == ESOViewMode::FirstPerson && !bDead;
	const double Z = GetActorLocation().Z;
	if (!bFeel)
	{
		// the shoulder camera: the capsule pops up and down steps, the view glides over them
		const bool bShoulder = Move && IsLocallyControlled() && ViewMode == ESOViewMode::ThirdPerson && !bDead;
		if (bShoulder && bHaveFeelZ && Move->MovementMode == MOVE_Walking)
		{
			const float Dz = static_cast<float>(Z - LastFeelZ);
			if (FMath::Abs(Dz) > 1.5f + static_cast<float>(GetVelocity().Size2D()) * Dt * 1.1f && FMath::Abs(Dz) < 60.0f)
			{
				StepSmooth = FMath::Clamp(StepSmooth - Dz, -60.0f, 60.0f);
			}
		}
		StepSmooth = bShoulder ? FMath::FInterpTo(StepSmooth, 0.0f, Dt, 11.0f) : 0.0f;
		ThirdPersonBoom->TargetOffset = FVector(0.0f, 0.0f, StepSmooth);
		FeelOffset = FVector::ZeroVector;
		LandDip = LandDipVel = CameraRoll = CameraRollVel = FovBoost = BobAmp = FeelPitch = ShakeRoll = ShakeRollVel = 0.0f;
		LastFeelZ = Z;
		bHaveFeelZ = true;
		return;
	}
	ThirdPersonBoom->TargetOffset = FVector::ZeroVector;
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

	// 4. Roll: into a slide, into a dodge, a lean toward a strafe (the guide's 3-5 degrees), a whisper with the stride;
	//    and a hard landing's wobble (a spring knocked by the impact, settling in a cycle or two).
	const FVector Right = GetActorRightVector();
	const float Strafe = Move->IsMovingOnGround() && !Move->IsDodging() ? FMath::Clamp(static_cast<float>(FVector::DotProduct(Velocity, Right)) / 440.0f, -1.0f, 1.0f) : 0.0f;
	const float VaultArc = Move->IsVaulting() ? FMath::Sin(Move->GetMantleAlpha() * PI) : 0.0f;
	const float DodgeSide = Move->IsDodging() ? static_cast<float>(FVector::DotProduct(Move->GetDodgeDir(), Right)) * FMath::Sin(Move->GetDodgeAlpha() * PI) : 0.0f;
	const float WantRoll = (Move->IsSliding() ? -SlideCameraRoll : 0.0f) + VaultArc * VaultCameraRoll + Strafe * StrafeCameraRoll * (1.0f - Ads)
		+ DodgeSide * DodgeCameraRoll + FMath::Sin(BobPhase * 0.5f) * BobAmp * 0.25f;
	{
		// a spring (at a straight exponential the lean stopped dead: a machine's motion)
		const float Omega = 9.0f, Zeta = 0.78f, SDt = FMath::Min(Dt, 0.05f);
		CameraRollVel += (Omega * Omega * (WantRoll - CameraRoll) - 2.0f * Zeta * Omega * CameraRollVel) * SDt;
		CameraRoll += CameraRollVel * SDt;
	}
	const float ShakeStiff = 520.0f, ShakeDamp = 2.0f * FMath::Sqrt(ShakeStiff) * 0.32f;
	ShakeRollVel += (-ShakeStiff * ShakeRoll - ShakeDamp * ShakeRollVel) * Dt;
	ShakeRoll = FMath::Clamp(ShakeRoll + ShakeRollVel * Dt, -4.0f, 4.0f);

	// 5. Field of view widens with speed (the guide: walk 95, sprint 103-108), and the view leans into a sprint.
	const float SprintK = Move->IsSprinting() ? FMath::Clamp((Speed - 440.0f) / 420.0f, 0.0f, 1.0f) : 0.0f;
	const float WantFov = Move->IsSliding() ? SlideFovBoost : Move->IsVaulting() ? SprintFovBoost : Move->IsDodging() ? DodgeFovBoost : SprintFovBoost * SprintK;
	FovBoost = FMath::FInterpTo(FovBoost, WantFov, Dt, 5.0f);
	FeelPitch = FMath::FInterpTo(FeelPitch, SprintCameraPitch * SprintK * (1.0f - Ads), Dt, 4.0f);

	// 6. Standing still the view breathes (the guide's idle: "subtle breathing, small weight shifts"): a few millimetres
	//    over 3.6 seconds, gone the moment the body moves.
	const float Still = FMath::Clamp(1.0f - Speed / 30.0f, 0.0f, 1.0f) * (bGrounded ? 1.0f : 0.0f) * (1.0f - Ads * 0.7f);
	const float BreathZ = 0.35f * Still * FMath::Sin(GetWorld()->GetTimeSeconds() * (2.0f * PI / 3.6f));
	FeelOffset = FVector(0.0f, BobY, StepSmooth + LandDip + BobZ + BreathZ);
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
	if (NewMode != ESOViewMode::FirstPerson && NewMode != ESOViewMode::ThirdPerson)
	{
		return; // a value no client of ours sends
	}
	ViewMode = NewMode;
	ApplyViewMode();
}

void ASOCharacter::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
	Super::GetLifetimeReplicatedProps(OutLifetimeProps);
	DOREPLIFETIME_CONDITION(ASOCharacter, ViewMode, COND_SkipOwner);
	DOREPLIFETIME(ASOCharacter, Outfit);
	DOREPLIFETIME(ASOCharacter, bFlashlightOn);
	DOREPLIFETIME(ASOCharacter, bFists);
	DOREPLIFETIME(ASOCharacter, MeleeStyle);
	DOREPLIFETIME(ASOCharacter, bBlocking);
	DOREPLIFETIME_CONDITION(ASOCharacter, bAiming, COND_SkipOwner);
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
		// (a gun put away, on a vault or in hand to hand, stays away whichever view comes up: switching views with the
		// fists up brought the gun back into the first-person view)
		if (Weapon->GetFirstPersonRig())
		{
			Weapon->GetFirstPersonRig()->SetShown(bFirst && !bScopeView && !bHeldStowed);
		}
		if (bHeldStowed && Weapon->GetThirdPersonRig())
		{
			Weapon->GetThirdPersonRig()->SetShown(false);
		}
	}
	for (USOGunRigComponent* Rig : HolsterRigs)
	{
		if (Rig)
		{
			Rig->SetOwnerNoSeeAll(bEye);
		}
	}
}


// --- hand to hand -------------------------------------------------------------------------------------------------------

const FSOMeleeStyle* ASOCharacter::GetMeleeStyle() const
{
	const USOMeleeTable* Table = USOMeleeTable::Get();
	const FSOMeleeStyle* Style = Table ? Table->Find(MeleeStyle) : nullptr;
	return Style ? Style : (Table ? Table->Find(TEXT("fists")) : nullptr);
}

const FSOMeleeBlow* ASOCharacter::MeleeBlowAt(int32 Index) const
{
	const FSOMeleeStyle* Style = GetMeleeStyle();
	return Style ? USOMeleeTable::Blow(*Style, Index) : nullptr;
}

void ASOCharacter::SetFists(bool bOn)
{
	if (bDead || bOn == bFists)
	{
		return;
	}
	if (bOn && Weapon)
	{
		Weapon->StopFire();
	}
	if (bOn)
	{
		HandleAimReleased();                                 // (out of the sights first: the aim key is the heavy blow now)
	}
	bFists = bOn;
	if (!bOn)
	{
		bBlocking = false;
	}
	OnRep_Fists();
	if (!HasAuthority())
	{
		ServerSetFists(bOn);
	}
}

void ASOCharacter::ServerSetFists_Implementation(bool bOn)
{
	SetFists(bOn);
}

void ASOCharacter::OnRep_Fists()
{
	MeleeLastIndex = -1;
	UpdateMeleeGuard();
	HolsterTimer = 0.0f;                                     // (the gun goes to the back on the next tick)
	USOSoundLibrary::PlayFor(this, bFists ? TEXT("melee_ready") : TEXT("ui_equip"), GetActorLocation(), 0.6f, ESOSoundRange::Near);
}

void ASOCharacter::UpdateMeleeGuard()
{
	const FSOMeleeStyle* Style = bFists && !bDead ? GetMeleeStyle() : nullptr;
	const bool bBlock = Style && bBlocking && !Style->BlockClip.IsNone();
	UAnimSequenceBase* Guard = Style ? GetAbilityClip(bBlock ? Style->BlockClip : Style->Guard) : nullptr;
	for (USkeletalMeshComponent* Skel : { GetMesh(), FirstPersonArms.Get() })
	{
		if (USOLocomotionAnimInstance* Anim = Skel ? Cast<USOLocomotionAnimInstance>(Skel->GetAnimInstance()) : nullptr)
		{
			Anim->SetMeleeGuard(Guard, bBlock ? Style->BlockHold : -1.0f);
		}
	}
}

int32 ASOCharacter::NextMeleeBlow(bool bHeavy) const
{
	const FSOMeleeStyle* Style = GetMeleeStyle();
	const UWorld* World = GetWorld();
	if (!Style || !World || Style->Light.Num() == 0 || bBlocking)
	{
		return -2;
	}
	const double Now = World->GetTimeSeconds();
	const FSOMeleeBlow* Last = MeleeLastStart < -50.0 ? nullptr : MeleeBlowAt(MeleeLastIndex);
	const double Free = Last ? MeleeLastStart + Last->Recover : -100.0;
	if (Now < Free - 0.06)                                  // (a press a hair early still counts: the machines' clocks differ)
	{
		return -2;
	}
	const bool bAir = GetCharacterMovement() && GetCharacterMovement()->IsFalling();
	const bool bLow = bIsCrouched;
	const USOCharacterMovementComponent* Move = GetSOMovement();
	const bool bRun = Move && Move->IsSprinting() && GetVelocity().Size2D() > 500.0f;
	const bool bInChain = Last && MeleeLastIndex >= 0 && MeleeLastIndex < 100 && Now <= Free + Style->ChainGrace;
	auto Has = [Style](int32 I) { return USOMeleeTable::Blow(*Style, I) != nullptr; };
	if (bHeavy)
	{
		// heavy: in the air the slam, crouched the riser, after two lights the finisher, else the heavy blow
		if (bAir && Has(SOMeleeMove::Air)) return SOMeleeMove::Air;
		if (bLow && Has(SOMeleeMove::Riser)) return SOMeleeMove::Riser;
		if (bInChain && MeleeLastIndex >= 1 && Has(SOMeleeMove::Finisher)) return SOMeleeMove::Finisher;
		return SOMeleeMove::Heavy;
	}
	// light: crouched the sweep, at a sprint the rush, else the chain
	if (!bAir && bLow && Has(SOMeleeMove::Sweep)) return SOMeleeMove::Sweep;
	if (!bAir && bRun && Has(SOMeleeMove::Rush)) return SOMeleeMove::Rush;
	return bInChain ? (MeleeLastIndex + 1) % Style->Light.Num() : 0;
}

bool ASOCharacter::MeleeBlowAllowed(int32 Index) const
{
	const UWorld* World = GetWorld();
	const FSOMeleeBlow* Last = MeleeLastStart < -50.0 ? nullptr : MeleeBlowAt(MeleeLastIndex);
	const double Free = Last ? MeleeLastStart + Last->Recover : -100.0;
	return bFists && !bDead && !bBlocking && World && MeleeBlowAt(Index) && World->GetTimeSeconds() >= Free - 0.12;
}

double ASOCharacter::GetComboAge() const
{
	return GetWorld() ? GetWorld()->GetTimeSeconds() - ComboLast : 100.0;
}

void ASOCharacter::MeleeStrike(bool bHeavy)
{
	if (!bFists || bDead || !IsLocallyControlled())
	{
		return;
	}
	const int32 Index = NextMeleeBlow(bHeavy);
	if (Index < -1)
	{
		return;
	}
	if (HasAuthority())
	{
		ServerMeleeBlow_Implementation(static_cast<int16>(Index));
		return;
	}
	// a joined player sees their own blow at once; the server lands it and its echo is skipped here
	BeginMeleeBlow(Index);
	ShowMeleeBlow(Index);
	MeleePredicted = GetWorld()->GetTimeSeconds();
	ServerMeleeBlow(static_cast<int16>(Index));
}

void ASOCharacter::BeginMeleeBlow(int32 Index)
{
	MeleeLastIndex = Index;
	MeleeLastStart = GetWorld()->GetTimeSeconds();
}

void ASOCharacter::ServerMeleeBlow_Implementation(int16 Index)
{
	if (!MeleeBlowAllowed(Index))
	{
		return;
	}
	const FSOMeleeBlow* Blow = MeleeBlowAt(Index);
	BeginMeleeBlow(Index);
	MulticastMeleeBlow(Index);
	// the blow lands when the clip says (after its wind-up), if the hands are still fighting then; a parry's counter
	// makes it harder
	TWeakObjectPtr<ASOCharacter> Self(this);
	const int32 At = Index;
	GetWorldTimerManager().SetTimer(MeleeHitTimer, FTimerDelegate::CreateLambda([Self, At]()
	{
		ASOCharacter* Me = Self.Get();
		const FSOMeleeBlow* B = Me ? Me->MeleeBlowAt(At) : nullptr;
		if (Me && B && Me->bFists && !Me->bDead)
		{
			const double Now = Me->GetWorld()->GetTimeSeconds();
			const FSOMeleeStyle* Style = Me->GetMeleeStyle();
			const float Scale = Now < Me->CounterUntil && Style ? Style->CounterScale : 1.0f;
			if (USOMeleeLibrary::Land(Me, *B, Scale, SOMeleeMove::Weight(At)) > 0)
			{
				Me->CounterUntil = -100.0;                   // (the counter is spent on the blow that lands)
			}
		}
	}), FMath::Max(Blow->HitTime, 0.01f), false);
}

void ASOCharacter::MulticastMeleeBlow_Implementation(int16 Index)
{
	if (!HasAuthority())
	{
		if (IsLocallyControlled() && GetWorld()->GetTimeSeconds() - MeleePredicted < 0.6)
		{
			return;                                          // (shown already, as it was pressed)
		}
		BeginMeleeBlow(Index);
	}
	ShowMeleeBlow(Index);
}

void ASOCharacter::ShowMeleeBlow(int32 Index)
{
	const FSOMeleeStyle* Style = GetMeleeStyle();
	const FSOMeleeBlow* Blow = MeleeBlowAt(Index);
	if (!Style || !Blow)
	{
		return;
	}
	if (UAnimSequenceBase* Clip = GetAbilityClip(Blow->Clip))
	{
		for (USkeletalMeshComponent* Skel : { GetMesh(), FirstPersonArms.Get() })
		{
			if (USOLocomotionAnimInstance* Anim = Skel ? Cast<USOLocomotionAnimInstance>(Skel->GetAnimInstance()) : nullptr)
			{
				Anim->PlayMeleeBlow(Clip, 1.0f);
			}
		}
	}
	if (!Blow->SwingSound.IsNone())
	{
		USOSoundLibrary::PlayFor(this, Blow->SwingSound, GetActorLocation(), Index < 0 || Index >= 100 ? 0.9f : 0.7f, ESOSoundRange::Near);
	}
	// the body moves with it (its own machine moves it: the movement is the owner's): the step in, the rush across the
	// ground, the slam straight down out of the air
	if (IsLocallyControlled())
	{
		UCharacterMovementComponent* Move = GetCharacterMovement();
		const FVector Ahead = GetAimDirection().GetSafeNormal2D();
		if (Index == SOMeleeMove::Air && Move->IsFalling())
		{
			Move->Velocity = Ahead * 300.0f + FVector(0.0f, 0.0f, -2200.0f);
		}
		else if (Blow->Lunge > 0.0f && !Move->IsFalling())
		{
			Move->Velocity += Ahead * Blow->Lunge;
		}
		AbilityKick = Index < 0 || Index >= 100 ? -4.0f : -1.5f;   // (the view takes the blow's weight)
	}
	TWeakObjectPtr<ASOCharacter> Self(this);
	const float Range = Blow->Range, Angle = Blow->Angle, Shock = Blow->Shock;
	const bool bEdge = Style->bEdge;
	const FLinearColor Color = Style->EdgeColor;
	GetWorldTimerManager().SetTimer(MeleeEdgeTimer, FTimerDelegate::CreateLambda([Self, Range, Angle, Shock, bEdge, Color]()
	{
		ASOCharacter* Me = Self.Get();
		USOFxSubsystem* Fx = Me && Me->GetWorld() ? Me->GetWorld()->GetSubsystem<USOFxSubsystem>() : nullptr;
		if (!Fx)
		{
			return;
		}
		if (Shock > 0.0f)
		{
			// a blow into the ground: the ring races out from the feet
			const FVector Feet = Me->GetActorLocation() - FVector(0.0f, 0.0f, Me->GetSimpleCollisionHalfHeight());
			Fx->Shockwave(Feet, Shock, bEdge ? Color : FLinearColor(1.0f, 0.85f, 0.6f));
		}
		else if (bEdge)
		{
			Fx->Sweep(Me->GetAimOrigin(), Me->GetAimDirection(), Range, Angle, Color);   // a blade's edge of light
		}
	}), FMath::Max(Blow->HitTime - 0.03f, 0.01f), false);
}

void ASOCharacter::OnMeleeHit(ASOCombatCharacter* Victim, const FVector& Point, float Weight, float HitStop)
{
	MulticastMeleeImpact(Victim, Point, Weight, HitStop);
}

void ASOCharacter::MulticastMeleeImpact_Implementation(ASOCombatCharacter* Victim, FVector_NetQuantize Point, float Weight, float HitStop)
{
	UWorld* World = GetWorld();
	if (!World)
	{
		return;
	}
	// the freeze: both bodies stop for an instant as the blow lands (each machine: this is how it is SHOWN; the
	// server's own freeze holds the attacker's next blow back by as much, which the recover times already allow for)
	if (HitStop > 0.0f)
	{
		TArray<TWeakObjectPtr<AActor>> Frozen;
		for (AActor* A : { static_cast<AActor*>(this), static_cast<AActor*>(Victim) })
		{
			if (A)
			{
				A->CustomTimeDilation = 0.04f;
				Frozen.Add(A);
			}
		}
		FTimerHandle Thaw;
		World->GetTimerManager().SetTimer(Thaw, FTimerDelegate::CreateLambda([Frozen]()
		{
			for (const TWeakObjectPtr<AActor>& A : Frozen)
			{
				if (A.IsValid())
				{
					A->CustomTimeDilation = 1.0f;
				}
			}
		}), HitStop, false);
	}
	// sparks where it landed: the blade's light, or the fist's flash and the flesh
	const FSOMeleeStyle* Style = GetMeleeStyle();
	if (USOFxSubsystem* Fx = World->GetSubsystem<USOFxSubsystem>())
	{
		const FVector Normal = Victim ? (GetActorLocation() - Victim->GetActorLocation()).GetSafeNormal2D() : -GetActorForwardVector();
		if (Style && Style->bEdge)
		{
			Fx->PlasmaImpact(Point, Normal, Style->EdgeColor, 0.5f * Weight, 0.0f, true);
		}
		else
		{
			Fx->Impact(Point, Normal, true, FLinearColor(0.35f, 0.04f, 0.03f), 0.0f, false);
			Fx->SlugImpact(Point, Normal, 0.35f * Weight);      // (the knuckles' spark of light off the suit's plate)
		}
	}
	// the one who struck: the camera takes it, the count goes on
	if (IsLocallyControlled())
	{
		AbilityKick = FMath::Min(AbilityKick, -1.5f - 1.5f * Weight);
		const double Now = World->GetTimeSeconds();
		ComboHits = Now - ComboLast < 1.6 ? ComboHits + 1 : 1;
		ComboLast = Now;
	}
}

void ASOCharacter::SetBlocking(bool bOn)
{
	bOn = bOn && bFists && !bDead;
	if (bOn == bBlocking)
	{
		return;
	}
	bBlocking = bOn;
	if (bOn && GetWorld())
	{
		BlockStart = GetWorld()->GetTimeSeconds();
	}
	UpdateMeleeGuard();
	if (!HasAuthority())
	{
		ServerSetBlocking(bOn);
	}
}

void ASOCharacter::ServerSetBlocking_Implementation(bool bOn)
{
	SetBlocking(bOn);
}

float ASOCharacter::ScaleIncomingDamage(float Amount, const AActor* Source, bool bCrit) const
{
	Amount = Super::ScaleIncomingDamage(Amount, Source, bCrit);
	const FSOMeleeStyle* Style = bBlocking ? GetMeleeStyle() : nullptr;
	const UWorld* World = GetWorld();
	if (!Style || !Source || !World)
	{
		return Amount;
	}
	// only what comes from in front of the guard
	const FVector To = (Source->GetActorLocation() - GetActorLocation()).GetSafeNormal2D();
	if (FVector::DotProduct(To, GetAimDirection().GetSafeNormal2D()) < FMath::Cos(FMath::DegreesToRadians(70.0f)))
	{
		return Amount;
	}
	const double Now = World->GetTimeSeconds();
	if (Now - BlockStart <= Style->ParryWindow)
	{
		// a parry: nothing gets through, the attacker reels, and this player's next blow is a counter
		ASOCharacter* Me = const_cast<ASOCharacter*>(this);
		Me->CounterUntil = Now + Style->CounterTime;
		if (HasAuthority())
		{
			if (ASOCombatCharacter* Attacker = Cast<ASOCombatCharacter>(const_cast<AActor*>(Source)))
			{
				USOCombatStatics::ApplyStatus(Me, Attacker, SOTags::Status_Stagger, Style->ParryStagger);
			}
			USOCue::Sound(this, TEXT("melee_parry"), GetActorLocation(), 1.0f, 0.03f);
			Me->MulticastMeleeImpact(nullptr, GetActorLocation() + To * 40.0f + FVector(0, 0, 40.0f), 2.0f, 0.12f);
		}
		Me->ParryShownAt = Now;
		return 0.0f;
	}
	return Amount * Style->BlockScale;
}

void ASOCharacter::SetMeleeStyle(FName Style)
{
	// the fists are always there; a blade only if this player owns it (the server checks)
	const USOInventoryComponent* Inventory = GetInventory();
	if (Style != TEXT("fists") && (!Inventory || !Inventory->HasBlade(Style)))
	{
		return;
	}
	if (Style == MeleeStyle)
	{
		return;
	}
	MeleeStyle = Style;
	OnRep_MeleeStyle();
	if (!HasAuthority())
	{
		ServerSetMeleeStyle(Style);
	}
}

void ASOCharacter::ServerSetMeleeStyle_Implementation(FName Style)
{
	SetMeleeStyle(Style);
}

void ASOCharacter::OnRep_MeleeStyle()
{
	MeleeLastIndex = -1;                                     // (a new style begins its own chain)
	UpdateMeleeGuard();
	UpdateBlade();
	if (bFists)
	{
		USOSoundLibrary::PlayFor(this, MeleeStyle == TEXT("fists") ? TEXT("melee_ready") : TEXT("blade_swing"), GetActorLocation(), 0.5f, ESOSoundRange::Near);
	}
}

bool ASOCharacter::BladeInHand(const USkeletalMeshComponent* Skel, FTransform& OutWorld)
{
	static const FName Hand(TEXT("hand_R")), Index(TEXT("index_01_R")), Middle(TEXT("middle_01_R")), Pinky(TEXT("pinky_01_R"));
	if (!Skel || Skel->GetBoneIndex(Hand) == INDEX_NONE || Skel->GetBoneIndex(Middle) == INDEX_NONE)
	{
		return false;
	}
	const FVector H = Skel->GetBoneLocation(Hand), M = Skel->GetBoneLocation(Middle);
	const FVector Along = (M - H).GetSafeNormal();                          // the wrist to the knuckles
	FVector Thumb = Skel->GetBoneLocation(Index) - Skel->GetBoneLocation(Pinky);   // the little finger to the index
	Thumb = (Thumb - Along * FVector::DotProduct(Thumb, Along)).GetSafeNormal();
	const FVector Palm = FVector::CrossProduct(Thumb, Along).GetSafeNormal(); // (right hand: out of the palm)
	// the blade's mesh: the blade along +Y, the edge along -Z, the handle's middle 6 cm behind its origin
	const FVector Y = Thumb, Z = -Along, X = FVector::CrossProduct(Y, Z);
	const FQuat Rot = FMatrix(X, Y, Z, FVector::ZeroVector).ToQuat();
	const FVector Grip = H + Along * FVector::Dist(H, M) * 0.55f + Palm * 2.6f;  // inside the closed fist
	OutWorld = FTransform(Rot, Grip - Rot.RotateVector(FVector(0.0f, -6.0f, 0.0f)));
	return true;
}

void ASOCharacter::UpdateBlade()
{
	const FSOMeleeStyle* Style = bFists && !bDead ? GetMeleeStyle() : nullptr;
	const bool bShow = Style && !Style->Mesh.IsNull() && Style->Id == MeleeStyle;
	if (bShow && BladeStyle != MeleeStyle)
	{
		// once per change of style, never every frame: the mesh is loaded with the area's assets already
		UStaticMesh* BladeMesh = Style->Mesh.LoadSynchronous();
		for (TObjectPtr<UStaticMeshComponent>* Slot : { &BladeTP, &BladeFP })
		{
			if (!*Slot)
			{
				UStaticMeshComponent* C = NewObject<UStaticMeshComponent>(this);
				C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
				C->SetCastShadow(Slot == &BladeTP);
				C->SetupAttachment(GetCapsuleComponent());
				C->RegisterComponent();
				if (Slot == &BladeFP)
				{
					C->SetOnlyOwnerSee(true);
					C->SetFirstPersonPrimitiveType(EFirstPersonPrimitiveType::FirstPerson);
				}
				*Slot = C;
			}
			(*Slot)->SetStaticMesh(BladeMesh);
		}
		BladeStyle = MeleeStyle;
	}
	if (!bShow)
	{
		BladeStyle = NAME_None;
	}
	for (const bool bFirst : { false, true })
	{
		UStaticMeshComponent* C = bFirst ? BladeFP.Get() : BladeTP.Get();
		const USkeletalMeshComponent* Holder = bFirst ? FirstPersonArms.Get() : GetMesh();
		if (!C)
		{
			continue;
		}
		FTransform At;
		const bool bOn = bShow && Holder && Holder->IsVisible() && BladeInHand(Holder, At);
		C->SetVisibility(bOn);
		if (bOn)
		{
			C->SetWorldTransform(At);
			if (!bFirst)
			{
				C->SetOwnerNoSee(GetMesh()->bOwnerNoSee);
			}
		}
	}
}
