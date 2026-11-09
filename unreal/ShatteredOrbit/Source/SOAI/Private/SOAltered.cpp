#include "SOAltered.h"

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

namespace
{
	const FLinearColor VoidColor(0.62f, 0.36f, 1.0f);
	const TCHAR* GlowMaterial = TEXT("/Game/Environments/Meridian/MI_ru_glow.MI_ru_glow");

	/** Mesh, clips and capsule of one of the Altered (/Game/Characters/<Name>/SK_<Name>). */
	void Configure(ASOEnemy* E, const TCHAR* Name, float Radius, float HalfHeight)
	{
		E->BodyMesh = TSoftObjectPtr<USkeletalMesh>(FSoftObjectPath(FString::Printf(TEXT("/Game/Characters/%s/SK_%s.SK_%s"), Name, Name, Name)));
		E->ClipPathPrefix = FString::Printf(TEXT("/Game/Characters/%s/Anims/A_%s_"), Name, Name);
		E->GetCapsuleComponent()->InitCapsuleSize(Radius, HalfHeight);
		E->GetMesh()->SetRelativeLocation(FVector(0.0f, 0.0f, -HalfHeight));
		E->GetMesh()->SetRelativeScale3D(FVector(1.0f));
		E->BloodColor = FLinearColor(0.32f, 0.1f, 0.55f);
	}

	float Now(const UObject* O) { return O->GetWorld() ? O->GetWorld()->GetTimeSeconds() : 0.0f; }

	void FaceToward(AActor* Self, const FVector& Point, float DeltaSeconds, float Rate)
	{
		const FVector To = (Point - Self->GetActorLocation()).GetSafeNormal2D();
		if (!To.IsNearlyZero())
		{
			const FRotator Want = To.Rotation();
			Self->SetActorRotation(DeltaSeconds > 0.0f ? FMath::RInterpTo(Self->GetActorRotation(), Want, DeltaSeconds, Rate) : Want);
		}
	}

	void FireBolt(ASOEnemy* From, const FVector& Start, AActor* Target, float Damage, float Speed, float SpreadDeg)
	{
		UWorld* World = From->GetWorld();
		if (!World || !Target)
		{
			return;
		}
		const FVector Aim = Target->GetActorLocation() + FVector(0, 0, 40.0f) + Target->GetVelocity() * 0.25f;
		FVector Dir = (Aim - Start).GetSafeNormal();
		Dir = FMath::VRandCone(Dir, FMath::DegreesToRadians(SpreadDeg));
		FActorSpawnParameters Params;
		Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
		Params.Instigator = From;
		if (ASOVoidBolt* Bolt = World->SpawnActor<ASOVoidBolt>(ASOVoidBolt::StaticClass(), Start, Dir.Rotation(), Params))
		{
			Bolt->Launch(From, Dir, Target, Damage, Speed);
		}
		USOSoundLibrary::PlayAt(From, TEXT("energy_shot_world"), Start, 0.8f, 0.15f, ESOSoundRange::Mid);
	}
}

// ------------------------------------------------------------------ void bolt
ASOVoidBolt::ASOVoidBolt()
{
	PrimaryActorTick.bCanEverTick = true;
	bReplicates = true;
	SetReplicatingMovement(true);
	Core = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Core"));
	Core->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Core->SetCastShadow(false);
	Core->SetRelativeScale3D(FVector(0.32f));
	RootComponent = Core;
	static ConstructorHelpers::FObjectFinder<UStaticMesh> Sphere(TEXT("/Engine/BasicShapes/Sphere.Sphere"));
	if (Sphere.Succeeded())
	{
		Core->SetStaticMesh(Sphere.Object);
	}
	Light = CreateDefaultSubobject<UPointLightComponent>(TEXT("Light"));
	Light->SetupAttachment(Core);
	Light->SetLightColor(VoidColor);
	Light->SetIntensity(60.0f);
	Light->SetAttenuationRadius(600.0f);
	Light->SetCastShadows(false);
	InitialLifeSpan = 6.0f;
}

void ASOVoidBolt::BeginPlay()
{
	Super::BeginPlay();
	if (UMaterialInterface* M = TSoftObjectPtr<UMaterialInterface>(FSoftObjectPath(GlowMaterial)).LoadSynchronous())
	{
		Core->SetMaterial(0, M);
	}
}

void ASOVoidBolt::Launch(AActor* InShooter, const FVector& Direction, AActor* InTarget, float InDamage, float InSpeed)
{
	Shooter = InShooter;
	Target = InTarget;
	Damage = InDamage;
	Speed = InSpeed;
	Velocity = Direction.GetSafeNormal() * Speed;
}

void ASOVoidBolt::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	Age += DeltaSeconds;
	Light->SetIntensity(55.0f + 20.0f * FMath::Sin(Age * 31.0f));
	if (!HasAuthority() || bSpent)
	{
		return;
	}
	if (Age > Life)
	{
		Burst(GetActorLocation(), -Velocity.GetSafeNormal());
		return;
	}
	// a slow curve toward the target's chest
	if (const AActor* T = Target.Get())
	{
		const FVector Want = (T->GetActorLocation() + FVector(0, 0, 40.0f) - GetActorLocation()).GetSafeNormal();
		const FVector Dir = Velocity.GetSafeNormal();
		const float MaxTurn = FMath::DegreesToRadians(Turn) * DeltaSeconds;
		const float Angle = FMath::Acos(FMath::Clamp(FVector::DotProduct(Dir, Want), -1.0f, 1.0f));
		if (Angle > 1e-3f && Angle < UE_HALF_PI)
		{
			Velocity = FMath::Lerp(Dir, Want, FMath::Min(1.0f, MaxTurn / Angle)).GetSafeNormal() * Speed;
		}
	}
	const FVector From = GetActorLocation();
	const FVector To = From + Velocity * DeltaSeconds;
	FCollisionQueryParams Params(SCENE_QUERY_STAT(SOVoidBolt), false, this);
	if (AActor* S = Shooter.Get())
	{
		Params.AddIgnoredActor(S);
	}
	FHitResult Hit;
	// the rounds' channel: hits bodies and walls, passes the invisible route blockers
	while (GetWorld()->SweepSingleByChannel(Hit, From, To, FQuat::Identity, SO_TRACE_BULLET, FCollisionShape::MakeSphere(Radius), Params))
	{
		AActor* Other = Hit.GetActor();
		const ASOCombatCharacter* Body = Cast<ASOCombatCharacter>(Other);
		if (Body && Shooter.IsValid() && !USOCombatStatics::AreHostile(Shooter.Get(), Body))
		{
			Params.AddIgnoredActor(Other); // through its own kind
			continue;
		}
		if (Other)
		{
			USOCombatStatics::ApplyDamage(Shooter.Get(), Other, Damage, false);
		}
		Burst(Hit.ImpactPoint, Hit.ImpactNormal);
		return;
	}
	SetActorLocation(To);
}

void ASOVoidBolt::Burst(const FVector& At, const FVector& Normal)
{
	bSpent = true;
	if (USOFxSubsystem* Fx = GetWorld()->GetSubsystem<USOFxSubsystem>())
	{
		Fx->Blast(At, Normal, 70.0f, USOFxSubsystem::EBlast::Zap, VoidColor);
	}
	USOSoundLibrary::PlayAt(this, TEXT("bolt_impact"), At, 0.8f, 0.1f, ESOSoundRange::Mid);
	SetLifeSpan(0.05f);
	Core->SetVisibility(false);
}

// ------------------------------------------------------------------ remnant
ASORemnant::ASORemnant(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	Configure(this, TEXT("Remnant"), 34.0f, 88.0f);
	DisplayName = NSLOCTEXT("SO", "Remnant", "Remnant");
	StartMaxHealth = 70.0f;
	WalkSpeed = 230.0f;
	RunSpeed = 650.0f;
	MeleeDamage = 11.0f;
	MeleeRange = 160.0f;
	MeleeCooldown = 0.75f;
	MeleeWindup = 0.26f;
	LungeSpeed = 620.0f;
	CorpseLifeSpan = 5.0f;
}

// ------------------------------------------------------------------ veilborn
ASOVeilborn::ASOVeilborn(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	Configure(this, TEXT("Veilborn"), 36.0f, 106.0f);
	DisplayName = NSLOCTEXT("SO", "Veilborn", "Veilborn");
	StartMaxHealth = 130.0f;
	WalkSpeed = 180.0f;
	RunSpeed = 420.0f;
	MeleeDamage = 14.0f;
	MeleeRange = 150.0f;
	SightRange = 5000.0f;
	ActionClips = { TEXT("Cast"), TEXT("Blink") };
}

bool ASOVeilborn::Blink(const FVector& Away)
{
	UWorld* World = GetWorld();
	const FVector Here = GetActorLocation();
	const float Side = FMath::RandBool() ? 1.0f : -1.0f;
	UNavigationSystemV1* Nav = FNavigationSystem::GetCurrent<UNavigationSystemV1>(World);
	for (int32 Try = 0; Try < 4; ++Try)
	{
		const FVector Dir = Away.GetSafeNormal2D().RotateAngleAxis(Side * (55.0f + 25.0f * Try) * (Try % 2 ? -1.0f : 1.0f), FVector::UpVector);
		FVector To = Here + Dir * FMath::FRandRange(700.0f, 1000.0f);
		FNavLocation OnNav;
		if (Nav && Nav->GetDefaultNavDataInstance(FNavigationSystem::DontCreate))
		{
			if (!Nav->ProjectPointToNavigation(To, OnNav, FVector(300.0f, 300.0f, 600.0f)))
			{
				continue;
			}
			To = OnNav.Location + FVector(0, 0, GetCapsuleComponent()->GetScaledCapsuleHalfHeight());
		}
		if (TeleportTo(To, GetActorRotation(), false, true))
		{
			if (USOFxSubsystem* Fx = World->GetSubsystem<USOFxSubsystem>())
			{
				Fx->Blast(Here, FVector::UpVector, 120.0f, USOFxSubsystem::EBlast::Zap, VoidColor);
				Fx->Blast(To, FVector::UpVector, 120.0f, USOFxSubsystem::EBlast::Zap, VoidColor, 0.05f);
			}
			USOSoundLibrary::PlayAt(this, TEXT("bolt_impact"), To, 1.0f, 0.1f, ESOSoundRange::Mid);
			PlayAction(TEXT("Blink"), 1.4f);
			++Blinks;
			return true;
		}
	}
	return false;
}

bool ASOVeilborn::ThinkCombat(ASOEnemyAIController* AI, ASOCombatCharacter* Target)
{
	const float T = Now(this);
	const float Dist = DistanceTo(Target);
	const float Health = GetHealth();
	if (HealthAtBlink < 0.0f)
	{
		HealthAtBlink = Health;
	}
	// pressed or hurt badly: blink aside
	if (T >= NextBlink && PendingCast < 0.0f && (Dist < MinRange || HealthAtBlink - Health > 45.0f))
	{
		NextBlink = T + BlinkCooldown;
		HealthAtBlink = Health;
		AI->StopMovement();
		if (Blink(GetActorLocation() - Target->GetActorLocation()))
		{
			NextCast = FMath::Max(NextCast, T + 0.6f);
			return true;
		}
	}
	const bool bSee = AI->LineOfSightTo(Target);
	if (PendingCast >= 0.0f)
	{
		return true; // mid-cast: stand
	}
	if (Dist > PreferredRange + 500.0f || !bSee)
	{
		AI->Chase();
		return true;
	}
	AI->StopMovement();
	if (T >= NextCast)
	{
		CastTarget = Target;
		PlayAction(TEXT("Cast"), 1.0f);
		PendingCast = T + 0.55f;
		NextCast = T + CastCooldown * FMath::FRandRange(0.85f, 1.2f);
	}
	return true;
}

void ASOVeilborn::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (IsDead())
	{
		return;
	}
	if (AActor* T = CastTarget.Get(); T && PendingCast >= 0.0f)
	{
		FaceToward(this, T->GetActorLocation(), DeltaSeconds, 10.0f);
	}
	if (HasAuthority() && PendingCast >= 0.0f && Now(this) >= PendingCast)
	{
		PendingCast = -1.0f;
		if (AActor* T = CastTarget.Get())
		{
			const FVector Hands = GetActorLocation() + GetActorForwardVector() * 70.0f + FVector(0, 0, 55.0f);
			FireBolt(this, Hands, T, BoltDamage, 2400.0f, 1.5f);
			++BoltsFired;
		}
	}
}

// ------------------------------------------------------------------ bulwark
ASOBulwark::ASOBulwark(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	Configure(this, TEXT("Bulwark"), 62.0f, 125.0f);
	DisplayName = NSLOCTEXT("SO", "Bulwark", "Bulwark");
	StartMaxHealth = 620.0f;
	WalkSpeed = 150.0f;
	RunSpeed = 300.0f;
	MeleeDamage = 32.0f;
	MeleeRange = 230.0f;
	MeleeCooldown = 1.7f;
	MeleeWindup = 0.55f;
	LungeSpeed = 260.0f;
	ActionClips = { TEXT("Slam") };
}

float ASOBulwark::ScaleIncomingDamage(float Amount, const AActor* Source, bool bCrit) const
{
	if (!Source)
	{
		return Amount;
	}
	const FVector To = (Source->GetActorLocation() - GetActorLocation()).GetSafeNormal2D();
	const bool bFront = FVector::DotProduct(GetActorForwardVector().GetSafeNormal2D(), To) > 0.4f;
	return bFront ? Amount * (bCrit ? FrontDamageScale * 2.0f : FrontDamageScale) : Amount;
}

bool ASOBulwark::ThinkCombat(ASOEnemyAIController* AI, ASOCombatCharacter* Target)
{
	const float T = Now(this);
	if (PendingSlam >= 0.0f)
	{
		return true;
	}
	if (T >= NextSlam && !IsAttacking() && DistanceTo(Target) < SlamRadius * 0.75f)
	{
		AI->StopMovement();
		FaceToward(this, Target->GetActorLocation(), 0.0f, 0.0f);
		PlayAction(TEXT("Slam"), 1.0f);
		PendingSlam = T + 0.72f;
		NextSlam = T + SlamCooldown;
		return true;
	}
	return false;
}

void ASOBulwark::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (!HasAuthority() || IsDead() || PendingSlam < 0.0f || Now(this) < PendingSlam)
	{
		return;
	}
	PendingSlam = -1.0f;
	const FVector Impact = GetActorLocation() + GetActorForwardVector() * 140.0f - FVector(0, 0, GetCapsuleComponent()->GetScaledCapsuleHalfHeight() - 10.0f);
	DamageAround(Impact, SlamRadius, SlamDamage, 900.0f);
	if (USOFxSubsystem* Fx = GetWorld()->GetSubsystem<USOFxSubsystem>())
	{
		Fx->Blast(Impact, FVector::UpVector, SlamRadius * 0.6f, USOFxSubsystem::EBlast::Zap, VoidColor);
	}
	USOSoundLibrary::PlayAt(this, TEXT("rocket_explode"), Impact, 0.9f, 0.1f, ESOSoundRange::Far);
	USOCombatStatics::ReportNoise(this, Impact, this, 2500.0f);
}

// ------------------------------------------------------------------ conduit
ASOConduit::ASOConduit(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	BodyMesh.Reset();
	ClipPathPrefix.Reset();
	DisplayName = NSLOCTEXT("SO", "Conduit", "Conduit");
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
	Light->SetLightColor(VoidColor);
	Light->SetIntensity(120.0f);
	Light->SetAttenuationRadius(1800.0f);
	Light->SetCastShadows(false);
}

void ASOConduit::BeginPlay()
{
	Super::BeginPlay();
	GetCharacterMovement()->DisableMovement();
	Crystal->SetStaticMesh(TSoftObjectPtr<UStaticMesh>(FSoftObjectPath(TEXT("/Game/Environments/Meridian/SM_MRK_conduit.SM_MRK_conduit"))).LoadSynchronous());
	if (UMaterialInterface* M = TSoftObjectPtr<UMaterialInterface>(FSoftObjectPath(GlowMaterial)).LoadSynchronous())
	{
		Tether->SetMaterial(0, M);
	}
}

void ASOConduit::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	const float T = Now(this);
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
		Fx->Blast(GetActorLocation(), FVector::UpVector, 260.0f, USOFxSubsystem::EBlast::Zap, VoidColor);
	}
	USOSoundLibrary::PlayAt(this, TEXT("rocket_explode"), GetActorLocation(), 1.0f, 0.1f, ESOSoundRange::Far);
}

// ------------------------------------------------------------------ colossus
ASOColossus::ASOColossus(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	Configure(this, TEXT("Colossus"), 150.0f, 410.0f);
	DisplayName = NSLOCTEXT("SO", "Colossus", "The Hollow Colossus");
	StartMaxHealth = 18000.0f;
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
	return StaggerUntil > Now(this);
}

FVector ASOColossus::Heart() const
{
	return GetActorLocation() + GetActorForwardVector() * 110.0f + FVector(0, 0, GetCapsuleComponent()->GetScaledCapsuleHalfHeight() * 0.45f);
}

float ASOColossus::ScaleIncomingDamage(float Amount, const AActor* Source, bool bCrit) const
{
	return IsStaggered() ? Amount * 1.5f : Amount;
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
				Fx->Blast(S, FVector::UpVector, 220.0f, USOFxSubsystem::EBlast::Zap, VoidColor);
			}
		}
	}
	USOSoundLibrary::PlayAt(this, TEXT("reliquary_open"), GetActorLocation(), 1.0f, 0.0f, ESOSoundRange::Far);
}

void ASOColossus::Begin(EMove Move, FName Clip, float ImpactAfter, float Rate)
{
	const float T = Now(this);
	Pending = Move;
	ImpactAt = T + ImpactAfter / Rate;
	MoveEnd = T + FMath::Max(GetActionLength(Clip), ImpactAfter + 0.4f) / Rate;
	bApproach = false;
	PlayAction(Clip, Rate);
}

bool ASOColossus::ThinkCombat(ASOEnemyAIController* AI, ASOCombatCharacter* Target)
{
	const float T = Now(this);
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
				Fx->Blast(Heart(), GetActorForwardVector(), 400.0f, USOFxSubsystem::EBlast::Zap, VoidColor);
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
		return true;
	}
	const float Dist = DistanceTo(Target);
	bApproach = Dist > 900.0f;
	if (T < NextMove)
	{
		return true;
	}
	const FVector To = (Target->GetActorLocation() - GetActorLocation()).GetSafeNormal2D();
	const bool bFront = FVector::DotProduct(GetActorForwardVector().GetSafeNormal2D(), To) > 0.35f;
	if (Dist < 1100.0f)
	{
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
	else if (Dist < 4200.0f && AI->LineOfSightTo(Target))
	{
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
	const float T = Now(this);
	ASOCombatCharacter* Target = Foe.Get();
	if (Target && !bShielded && !IsStaggered())
	{
		if (bApproach)
		{
			AddMovementInput((Target->GetActorLocation() - GetActorLocation()).GetSafeNormal2D(), 1.0f);
		}
		else if (Pending != EMove::None || ShotsLeft > 0)
		{
			FaceToward(this, Target->GetActorLocation(), DeltaSeconds, Pending == EMove::Barrage ? 2.5f : 1.2f);
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
			const FVector Impact = Feet + GetActorForwardVector() * 450.0f;
			DamageAround(Impact, 950.0f, 45.0f, 1300.0f);
			if (Fx)
			{
				Fx->Blast(Impact, FVector::UpVector, 650.0f, USOFxSubsystem::EBlast::Zap, VoidColor);
				Fx->Blast(Impact, FVector::UpVector, 380.0f, USOFxSubsystem::EBlast::Fire, FLinearColor(0.5f, 0.45f, 0.5f), 0.08f);
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
				if (Other == this || Other->IsDead() || !USOCombatStatics::AreHostile(this, Other) || D.Size2D() > 1250.0f
					|| FVector::DotProduct(Fwd, D.GetSafeNormal2D()) < 0.0f || D.Z > 500.0f)
				{
					continue;
				}
				USOCombatStatics::ApplyDamage(this, Other, 40.0f, false);
				const FVector Side = FVector::CrossProduct(FVector::UpVector, Fwd);
				Other->LaunchCharacter(-Side * 1100.0f + Fwd * 400.0f + FVector(0, 0, 450.0f), true, true);
			}
			if (Fx)
			{
				Fx->Blast(GetActorLocation() + Fwd * 700.0f, Fwd, 300.0f, USOFxSubsystem::EBlast::Zap, VoidColor);
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
			FireBolt(this, Heart(), Target, 14.0f, 2200.0f, 6.0f);
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
		Fx->Blast(Heart(), FVector::UpVector, 700.0f, USOFxSubsystem::EBlast::Zap, VoidColor);
	}
}
