#include "SOAltered.h"
#include "SOCue.h"

#include "SOAlteredCommon.h"
#include "SOBoss.h"
#include "SOCombatTypes.h"

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

// The Hollow Colossus and the conduits that feed its shield.
ASOConduit::ASOConduit(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	SpeciesId = TEXT("conduit");
	BodyMesh.Reset();
	ClipPathPrefix.Reset();
	DisplayName = NSLOCTEXT("SO", "Conduit", "Conduit");
	bDropsLoot = false;
	StartMaxHealth = 900.0f;
	CorpseLifeSpan = 2.5f;
	AIControllerClass = nullptr;
	AutoPossessAI = EAutoPossessAI::Disabled;
	GetCapsuleComponent()->InitCapsuleSize(140.0f, 300.0f);
	GetCharacterMovement()->GravityScale = 0.0f;
	Crystal = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Crystal"));
	Crystal->SetupAttachment(GetCapsuleComponent());
	Crystal->SetRelativeLocation(FVector(0, 0, -300.0f));
	Crystal->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Tether = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Tether"));
	Tether->SetupAttachment(GetCapsuleComponent());
	Tether->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Tether->SetCastShadow(false);
	Tether->SetUsingAbsoluteRotation(true);
	Tether->SetUsingAbsoluteScale(true);
	static ConstructorHelpers::FObjectFinderOptional<UStaticMesh> Cylinder(TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
	if (Cylinder.Succeeded())
	{
		Tether->SetStaticMesh(Cylinder.Get());
	}
	Light = CreateDefaultSubobject<UPointLightComponent>(TEXT("Light"));
	Light->SetupAttachment(GetCapsuleComponent());
	Light->SetRelativeLocation(FVector(0, 0, 120.0f));
	Light->SetLightColor(SOAltered::VoidColor);
	Light->SetIntensity(120.0f);
	Light->SetAttenuationRadius(1800.0f);
	Light->SetCastShadows(false);
}

void ASOConduit::BeginPlay()
{
	Super::BeginPlay();
	GetCharacterMovement()->DisableMovement();
	Crystal->SetStaticMesh(TSoftObjectPtr<UStaticMesh>(FSoftObjectPath(TEXT("/Game/Shared/Operation/SM_MRK_conduit.SM_MRK_conduit"))).LoadSynchronous());
	if (UMaterialInterface* M = TSoftObjectPtr<UMaterialInterface>(FSoftObjectPath(SOAltered::GlowMaterial)).LoadSynchronous())
	{
		Tether->SetMaterial(0, M);
	}
}

void ASOConduit::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	const float T = SOAltered::Now(this);
	Light->SetIntensity(IsDead() ? 0.0f : 110.0f + 40.0f * FMath::Sin(T * 5.3f));
	const AActor* A = Anchor.Get();
	Tether->SetVisibility(A != nullptr && !IsDead());
	if (!A || IsDead())
	{
		return;
	}
	// a thin beam from the crystal's top to the anchor
	const FVector From = GetActorLocation() + FVector(0, 0, 150.0f);
	FVector To = A->GetActorLocation() + FVector(0, 0, 150.0f);
	if (const ASOColossus* Giant = Cast<ASOColossus>(A))
	{
		To = Giant->GetActorLocation() + FVector(0, 0, Giant->GetCapsuleComponent()->GetScaledCapsuleHalfHeight() * 0.45f);
	}
	const FVector D = To - From;
	Tether->SetWorldLocation(From + D * 0.5f);
	Tether->SetWorldRotation(FRotationMatrix::MakeFromZ(D.GetSafeNormal()).Rotator());
	const float W = 0.08f + 0.02f * FMath::Sin(T * 13.0f);
	Tether->SetWorldScale3D(FVector(W, W, D.Size() / 100.0f));
}

void ASOConduit::HandleDeath()
{
	Super::HandleDeath();
	Crystal->SetVisibility(false);
	Tether->SetVisibility(false);
	if (USOFxSubsystem* Fx = GetWorld()->GetSubsystem<USOFxSubsystem>())
	{
		USOCue::Blast(this, GetActorLocation(), FVector::UpVector, 260.0f, USOFxSubsystem::EBlast::Zap, SOAltered::VoidColor);
	}
	USOCue::Sound(this, TEXT("rocket_explode"), GetActorLocation(), 1.0f, 0.1f, ESOSoundRange::Far);
}

ASOColossus::ASOColossus(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	SpeciesId = TEXT("colossus");
	SOAltered::Configure(this, TEXT("Colossus"), 50.0f, 128.0f);
	DisplayName = NSLOCTEXT("SO", "Colossus", "The Colossus");
	VoicePrefix = TEXT("colossus");
	WeaponArchetype = TEXT("hmg");
	WeaponDamageScale = 0.22f;
	AimError = 70.0f;
	PreferredRange = 1800.0f;
	bUsesCover = false;
	BurstTime = FVector2D(0.8f, 1.6f);
	BurstPause = FVector2D(0.8f, 1.6f);
	StartMaxHealth = 12000.0f;
	WalkSpeed = 170.0f;
	RunSpeed = 240.0f;
	MeleeDamage = 0.0f;
	MeleeRange = 0.0f;
	SightRange = 9000.0f;
	CorpseLifeSpan = 0.0f;
	ActionClips = { TEXT("Slam"), TEXT("Sweep"), TEXT("Barrage"), TEXT("Shield") };
	KitId = TEXT("colossus");  // what it fights with in its first phase
	BossId = TEXT("colossus"); // how the fight goes: phases, the shield between them, the heart
	FlinchScale = 0.2f;
	GetCharacterMovement()->MaxAcceleration = 600.0f;
	GetCharacterMovement()->RotationRate = FRotator(0.0f, 90.0f, 0.0f);
	GetCharacterMovement()->bOrientRotationToMovement = true;
}

bool ASOColossus::IsShielded() const
{
	return Boss && Boss->IsShielded();
}

bool ASOColossus::IsStaggered() const
{
	return HasStatus(SOTags::Status_Stagger);
}

const TArray<TWeakObjectPtr<ASOConduit>>& ASOColossus::GetConduits() const
{
	static const TArray<TWeakObjectPtr<ASOConduit>> None;
	return Boss ? Boss->GetConduits() : None;
}

void ASOColossus::StartShield()
{
	if (Boss)
	{
		Boss->StartShield();
	}
}

FVector ASOColossus::Heart() const
{
	return GetActorLocation() + GetActorForwardVector() * 110.0f + FVector(0, 0, GetCapsuleComponent()->GetScaledCapsuleHalfHeight() * 0.45f);
}

bool ASOColossus::ThinkCombat(ASOEnemyAIController* AI, ASOCombatCharacter* Target)
{
	const float T = SOAltered::Now(this);
	Foe = Target;
	AI->StopMovement();
	if (IsShielded())
	{
		// behind the shield it kneels into the beam and waits for its conduits
		bApproach = false;
		SetWantsFire(false);
		if (USOLocomotionAnimInstance* Anim = Cast<USOLocomotionAnimInstance>(GetMesh()->GetAnimInstance()); Anim && !Anim->IsPlayingAction())
		{
			PlayAction(TEXT("Shield"), 1.0f);
		}
		return true;
	}
	if (IsUsingAbility())
	{
		// in a move: it stands and commits (Tick turns it, slowly: a blow can be stepped round)
		bApproach = false;
		SetWantsFire(false);
		bInMove = true;
		return true;
	}
	if (bInMove)
	{
		// the move is over: a breath before the next (the phase says how long)
		bInMove = false;
		NextMove = T + (Boss ? Boss->NextMovePause() : 3.5f);
	}
	const float Dist = DistanceTo(Target);
	bApproach = Dist > 700.0f;
	SetWantsFire(Dist > 450.0f && HasLineOfFire(Target)); // the heavy gun between its moves
	if (T >= NextMove && UseKit(AI, Target, true))
	{
		bApproach = false;
		SetWantsFire(false);
		bInMove = true;
	}
	return true;
}

void ASOColossus::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (!HasAuthority() || IsDead())
	{
		return;
	}
	ASOCombatCharacter* Target = Foe.Get();
	if (!Target || IsShielded() || IsStaggered())
	{
		return;
	}
	if (IsUsingAbility())
	{
		SOAltered::FaceToward(this, Target->GetActorLocation(), DeltaSeconds, 1.4f);
	}
	else if (bApproach)
	{
		AddMovementInput((Target->GetActorLocation() - GetActorLocation()).GetSafeNormal2D(), 1.0f);
	}
}

void ASOColossus::HandleDeath()
{
	Super::HandleDeath(); // (its conduits go with it: USOBossComponent::OwnerDied)
	USOCue::Blast(this, Heart(), FVector::UpVector, 700.0f, USOFxSubsystem::EBlast::Zap, SOAltered::VoidColor);
}
