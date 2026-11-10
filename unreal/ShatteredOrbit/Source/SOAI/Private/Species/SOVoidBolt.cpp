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

// The void bolt: the Altered's thrown shot.
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
	Light->SetLightColor(SOAltered::VoidColor);
	Light->SetIntensity(60.0f);
	Light->SetAttenuationRadius(600.0f);
	Light->SetCastShadows(false);
	InitialLifeSpan = 6.0f;
}

void ASOVoidBolt::BeginPlay()
{
	Super::BeginPlay();
	if (UMaterialInterface* M = TSoftObjectPtr<UMaterialInterface>(FSoftObjectPath(SOAltered::GlowMaterial)).LoadSynchronous())
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
		Fx->Blast(At, Normal, 70.0f, USOFxSubsystem::EBlast::Zap, SOAltered::VoidColor);
	}
	USOSoundLibrary::PlayAt(this, TEXT("bolt_impact"), At, 0.8f, 0.1f, ESOSoundRange::Mid);
	SetLifeSpan(0.05f);
	Core->SetVisibility(false);
}
