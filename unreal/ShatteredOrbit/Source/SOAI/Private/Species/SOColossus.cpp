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
	if (const ASOColossus* Boss = Cast<ASOColossus>(A))
	{
		To = Boss->GetActorLocation() + FVector(0, 0, Boss->GetCapsuleComponent()->GetScaledCapsuleHalfHeight() * 0.45f);
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
		Fx->Blast(GetActorLocation(), FVector::UpVector, 260.0f, USOFxSubsystem::EBlast::Zap, SOAltered::VoidColor);
	}
	USOSoundLibrary::PlayAt(this, TEXT("rocket_explode"), GetActorLocation(), 1.0f, 0.1f, ESOSoundRange::Far);
}

ASOColossus::ASOColossus(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	SpeciesId = TEXT("colossus");
	SOAltered::Configure(this, TEXT("Colossus"), 50.0f, 128.0f);
	DisplayName = NSLOCTEXT("SO", "Colossus", "The Hollow Colossus");
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
	ShieldAt = { 0.66f, 0.33f };
	ConduitClass = ASOConduit::StaticClass();
	GetCharacterMovement()->MaxAcceleration = 600.0f;
	GetCharacterMovement()->RotationRate = FRotator(0.0f, 90.0f, 0.0f);
	GetCharacterMovement()->bOrientRotationToMovement = true;
}

bool ASOColossus::IsStaggered() const
{
	return StaggerUntil > SOAltered::Now(this);
}

FVector ASOColossus::Heart() const
{
	return GetActorLocation() + GetActorForwardVector() * 110.0f + FVector(0, 0, GetCapsuleComponent()->GetScaledCapsuleHalfHeight() * 0.45f);
}

float ASOColossus::ScaleIncomingDamage(float Amount, const AActor* Source, bool bCrit) const
{
	return Super::ScaleIncomingDamage(IsStaggered() ? Amount * 1.5f : Amount, Source, bCrit);
}

void ASOColossus::StartShield()
{
	if (bShielded || !HasAuthority())
	{
		return;
	}
	bShielded = true;
	Pending = EMove::None;
	ShotsLeft = 0;
	bApproach = false;
	SetImmune(true, NSLOCTEXT("SO", "ColossusShield", "Shielded: destroy the conduits"));
	PlayAction(TEXT("Shield"), 1.0f);
	TArray<FVector> Sockets;
	for (TActorIterator<AActor> It(GetWorld()); It; ++It)
	{
		if (It->ActorHasTag(TEXT("SOConduit")))
		{
			Sockets.Add(It->GetActorLocation());
		}
	}
	if (Sockets.Num() == 0)
	{
		const FVector C = GetActorLocation() - FVector(0, 0, GetCapsuleComponent()->GetScaledCapsuleHalfHeight());
		for (int32 i = 0; i < 3; ++i)
		{
			const float A = UE_TWO_PI * i / 3.0f + 0.5f;
			Sockets.Add(C + FVector(FMath::Cos(A), FMath::Sin(A), 0.0f) * 2800.0f);
		}
	}
	Conduits.Reset();
	for (const FVector& S : Sockets)
	{
		FActorSpawnParameters Params;
		Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
		if (ASOConduit* C = GetWorld()->SpawnActor<ASOConduit>(ConduitClass ? *ConduitClass : ASOConduit::StaticClass(), S + FVector(0, 0, 300.0f), FRotator::ZeroRotator, Params))
		{
			C->Anchor = this;
			Conduits.Add(C);
			if (USOFxSubsystem* Fx = GetWorld()->GetSubsystem<USOFxSubsystem>())
			{
				Fx->Blast(S, FVector::UpVector, 220.0f, USOFxSubsystem::EBlast::Zap, SOAltered::VoidColor);
			}
		}
	}
	USOSoundLibrary::PlayAt(this, TEXT("reliquary_open"), GetActorLocation(), 1.0f, 0.0f, ESOSoundRange::Far);
}

void ASOColossus::Begin(EMove Move, FName Clip, float ImpactAfter, float Rate)
{
	const float T = SOAltered::Now(this);
	Pending = Move;
	ImpactAt = T + ImpactAfter / Rate;
	MoveEnd = T + FMath::Max(GetActionLength(Clip), ImpactAfter + 0.4f) / Rate;
	bApproach = false;
	PlayAction(Clip, Rate);
}

bool ASOColossus::ThinkCombat(ASOEnemyAIController* AI, ASOCombatCharacter* Target)
{
	const float T = SOAltered::Now(this);
	Foe = Target;
	AI->StopMovement();
	if (bShielded)
	{
		Conduits.RemoveAll([](const TWeakObjectPtr<ASOConduit>& C) { return !C.IsValid() || C->IsDead(); });
		if (Conduits.Num() == 0)
		{
			// the shield breaks: it reels, open to everything
			bShielded = false;
			SetImmune(false);
			StaggerUntil = T + StaggerTime;
			NextMove = StaggerUntil + 1.0f;
			USOSoundLibrary::PlayAt(this, TEXT("rocket_explode"), Heart(), 1.0f, 0.0f, ESOSoundRange::Far);
			if (USOFxSubsystem* Fx = GetWorld()->GetSubsystem<USOFxSubsystem>())
			{
				Fx->Blast(Heart(), GetActorForwardVector(), 400.0f, USOFxSubsystem::EBlast::Zap, SOAltered::VoidColor);
			}
		}
		else if (USOLocomotionAnimInstance* Anim = Cast<USOLocomotionAnimInstance>(GetMesh()->GetAnimInstance()); Anim && !Anim->IsPlayingAction())
		{
			PlayAction(TEXT("Shield"), 1.0f);
		}
		return true;
	}
	if (ShieldAt.IsValidIndex(NextShield) && GetHealth() <= GetMaxHealth() * ShieldAt[NextShield])
	{
		++NextShield;
		StartShield();
		return true;
	}
	if (IsStaggered() || Pending != EMove::None || ShotsLeft > 0)
	{
		bApproach = false;
		SetWantsFire(false);
		return true;
	}
	const float Dist = DistanceTo(Target);
	bApproach = Dist > 700.0f;
	SetWantsFire(Dist > 450.0f && HasLineOfFire(Target)); // the heavy gun between its moves
	if (T < NextMove)
	{
		return true;
	}
	const FVector To = (Target->GetActorLocation() - GetActorLocation()).GetSafeNormal2D();
	const bool bFront = FVector::DotProduct(GetActorForwardVector().GetSafeNormal2D(), To) > 0.35f;
	if (Dist < 450.0f)
	{
		SetWantsFire(false);
		if (bFront && FMath::FRand() < 0.55f)
		{
			Begin(EMove::Sweep, TEXT("Sweep"), 0.78f);
		}
		else
		{
			Begin(EMove::Slam, TEXT("Slam"), 0.82f);
		}
		NextMove = T + FMath::FRandRange(3.0f, 4.2f);
	}
	else if (Dist < 4200.0f && AI->LineOfSightTo(Target) && FMath::FRand() < 0.45f)
	{
		SetWantsFire(false);
		Begin(EMove::Barrage, TEXT("Barrage"), 0.55f);
		NextMove = T + FMath::FRandRange(4.0f, 5.5f);
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
	const float T = SOAltered::Now(this);
	ASOCombatCharacter* Target = Foe.Get();
	if (Target && !bShielded && !IsStaggered())
	{
		if (bApproach)
		{
			AddMovementInput((Target->GetActorLocation() - GetActorLocation()).GetSafeNormal2D(), 1.0f);
		}
		else if (Pending != EMove::None || ShotsLeft > 0)
		{
			SOAltered::FaceToward(this, Target->GetActorLocation(), DeltaSeconds, Pending == EMove::Barrage ? 2.5f : 1.2f);
		}
	}
	// a move lands
	if (Pending != EMove::None && T >= ImpactAt)
	{
		const EMove Move = Pending;
		Pending = EMove::None;
		const FVector Feet = GetActorLocation() - FVector(0, 0, GetCapsuleComponent()->GetScaledCapsuleHalfHeight() - 10.0f);
		USOFxSubsystem* Fx = GetWorld()->GetSubsystem<USOFxSubsystem>();
		if (Move == EMove::Slam)
		{
			const FVector Impact = Feet + GetActorForwardVector() * 160.0f;
			DamageAround(Impact, 520.0f, 40.0f, 1100.0f);
			if (Fx)
			{
				Fx->Blast(Impact, FVector::UpVector, 360.0f, USOFxSubsystem::EBlast::Zap, SOAltered::VoidColor);
				Fx->Blast(Impact, FVector::UpVector, 220.0f, USOFxSubsystem::EBlast::Fire, FLinearColor(0.5f, 0.45f, 0.5f), 0.08f);
			}
			USOSoundLibrary::PlayAt(this, TEXT("rocket_explode"), Impact, 1.0f, 0.05f, ESOSoundRange::Far);
		}
		else if (Move == EMove::Sweep)
		{
			// everything in a wide arc in front, thrown sideways
			const FVector Fwd = GetActorForwardVector().GetSafeNormal2D();
			for (TActorIterator<ASOCombatCharacter> It(GetWorld()); It; ++It)
			{
				ASOCombatCharacter* Other = *It;
				const FVector D = Other->GetActorLocation() - GetActorLocation();
				if (Other == this || Other->IsDead() || !USOCombatStatics::AreHostile(this, Other) || D.Size2D() > 480.0f
					|| FVector::DotProduct(Fwd, D.GetSafeNormal2D()) < 0.0f || D.Z > 500.0f)
				{
					continue;
				}
				USOCombatStatics::ApplyDamage(this, Other, 40.0f, false);
				const FVector Side = FVector::CrossProduct(FVector::UpVector, Fwd);
				Other->LaunchCharacter(-Side * 900.0f + Fwd * 300.0f + FVector(0, 0, 380.0f), true, true);
			}
			if (Fx)
			{
				Fx->Blast(GetActorLocation() + Fwd * 280.0f, Fwd, 200.0f, USOFxSubsystem::EBlast::Zap, SOAltered::VoidColor);
			}
			USOSoundLibrary::PlayAt(this, TEXT("stalker_attack"), GetActorLocation(), 1.0f, 0.0f, ESOSoundRange::Far);
		}
		else if (Move == EMove::Barrage)
		{
			ShotsLeft = 10;
			NextShot = T;
		}
	}
	if (ShotsLeft > 0 && T >= NextShot)
	{
		if (Target)
		{
			SOAltered::FireBolt(this, Heart(), Target, 14.0f, 2200.0f, 6.0f);
		}
		--ShotsLeft;
		NextShot = T + 0.14f;
	}
}

void ASOColossus::HandleDeath()
{
	Super::HandleDeath();
	for (const TWeakObjectPtr<ASOConduit>& C : Conduits)
	{
		if (C.IsValid() && !C->IsDead())
		{
			C->Die(nullptr);
		}
	}
	if (USOFxSubsystem* Fx = GetWorld()->GetSubsystem<USOFxSubsystem>())
	{
		Fx->Blast(Heart(), FVector::UpVector, 700.0f, USOFxSubsystem::EBlast::Zap, SOAltered::VoidColor);
	}
}
