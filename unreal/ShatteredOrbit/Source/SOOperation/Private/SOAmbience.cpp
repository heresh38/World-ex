#include "SOAmbience.h"

#include "Components/AudioComponent.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "Sound/SoundAttenuation.h"
#include "Sound/SoundWave.h"
#include "SOFxSubsystem.h"

ASOAmbience::ASOAmbience()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.TickInterval = 0.1f;
	SetRootComponent(CreateDefaultSubobject<USceneComponent>(TEXT("Root")));
}

void ASOAmbience::BeginPlay()
{
	Super::BeginPlay();
	if (Sound.IsNone() || GetNetMode() == NM_DedicatedServer)
	{
		return;
	}
	const FString Path = FString::Printf(TEXT("/Game/Audio/S_%s.S_%s"), *Sound.ToString(), *Sound.ToString());
	USoundWave* Wave = TSoftObjectPtr<USoundWave>(FSoftObjectPath(Path)).LoadSynchronous();
	if (!Wave)
	{
		return;
	}
	Wave->bLooping = true;
	FSoundAttenuationSettings Att;
	Att.bAttenuate = true;
	Att.bSpatialize = Radius < 10000.0f; // the far chorus is all round, not from one point
	Att.AttenuationShape = EAttenuationShape::Sphere;
	Att.AttenuationShapeExtents = FVector(Radius * 0.15f);
	Att.FalloffDistance = Radius * 0.85f;
	Att.DistanceAlgorithm = EAttenuationDistanceModel::NaturalSound;
	Loop = NewObject<UAudioComponent>(this);
	Loop->SetupAttachment(GetRootComponent());
	Loop->SetSound(Wave);
	Loop->SetVolumeMultiplier(Volume);
	Loop->bAutoActivate = false;
	Loop->bOverrideAttenuation = true;
	Loop->AttenuationOverrides = Att;
	Loop->RegisterComponent();
	Loop->Play(FMath::FRandRange(0.0f, 8.0f)); // each loop starts at its own point so neighbours never phase
}

void ASOAmbience::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (!bSpores || GetNetMode() == NM_DedicatedServer)
	{
		return;
	}
	const APlayerController* PC = GetWorld()->GetFirstPlayerController();
	const APawn* Viewer = PC ? PC->GetPawn() : nullptr;
	if (!Viewer || FVector::DistSquared(Viewer->GetActorLocation(), GetActorLocation()) > FMath::Square(4500.0f))
	{
		return;
	}
	SporeTimer -= DeltaSeconds;
	if (SporeTimer > 0.0f)
	{
		return;
	}
	SporeTimer = FMath::FRandRange(0.15f, 0.4f);
	if (USOFxSubsystem* Fx = GetWorld()->GetSubsystem<USOFxSubsystem>())
	{
		FSOFxParticle P;
		P.Kind = ESOFxKind::Glow;
		P.Position = GetActorLocation() + FVector(FMath::FRandRange(-350.0f, 350.0f), FMath::FRandRange(-350.0f, 350.0f), FMath::FRandRange(-40.0f, 60.0f));
		P.Velocity = FVector(FMath::FRandRange(-12.0f, 12.0f), FMath::FRandRange(-12.0f, 12.0f), FMath::FRandRange(18.0f, 45.0f));
		P.Life = FMath::FRandRange(4.0f, 7.0f);
		P.Size0 = FMath::FRandRange(2.5f, 5.0f);
		P.Size1 = 1.0f;
		P.Intensity0 = 3.5f;
		P.Intensity1 = 0.0f;
		P.Color = FLinearColor(0.62f, 0.38f, 1.0f);
		Fx->Spawn(P);
	}
}
