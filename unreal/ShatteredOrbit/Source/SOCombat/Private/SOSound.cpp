#include "SOSound.h"

#include "Engine/World.h"
#include "GameFramework/Pawn.h"
#include "Kismet/GameplayStatics.h"
#include "Sound/SoundAttenuation.h"
#include "Sound/SoundBase.h"
#include "SOAreaSubsystem.h"
#include "UObject/StrongObjectPtr.h"

namespace
{
	TMap<FName, TStrongObjectPtr<USoundBase>>& Cache()
	{
		static TMap<FName, TStrongObjectPtr<USoundBase>> Sounds;
		// held only for the area being played: leaving it lets them all go (the next area loads what it plays)
		static const FDelegateHandle Release = USOAreaSubsystem::OnReleaseContent().AddLambda([]() { Sounds.Reset(); });
		return Sounds;
	}

	USoundAttenuation* Attenuation(ESOSoundRange Range)
	{
		static TStrongObjectPtr<USoundAttenuation> Presets[3];
		TStrongObjectPtr<USoundAttenuation>& Slot = Presets[static_cast<int32>(Range)];
		if (!Slot.IsValid())
		{
			USoundAttenuation* A = NewObject<USoundAttenuation>(GetTransientPackage());
			FSoundAttenuationSettings& S = A->Attenuation;
			S.bAttenuate = true;
			S.bSpatialize = true;
			S.AttenuationShape = EAttenuationShape::Sphere;
			S.DistanceAlgorithm = EAttenuationDistanceModel::NaturalSound;
			S.dBAttenuationAtMax = -60.0f;
			S.bAttenuateWithLPF = true;
			const float Inner[] = { 150.0f, 400.0f, 1500.0f };
			const float Falloff[] = { 2500.0f, 6000.0f, 15000.0f };
			S.AttenuationShapeExtents = FVector(Inner[static_cast<int32>(Range)], 0.0f, 0.0f);
			S.FalloffDistance = Falloff[static_cast<int32>(Range)];
			S.LPFRadiusMin = S.FalloffDistance * 0.15f;
			S.LPFRadiusMax = S.FalloffDistance;
			S.LPFFrequencyAtMin = 20000.0f;
			S.LPFFrequencyAtMax = 2500.0f;
			Slot.Reset(A);
		}
		return Slot.Get();
	}

	float Pitch(float Jitter)
	{
		return 1.0f + FMath::FRandRange(-Jitter, Jitter);
	}
}

USoundBase* USOSoundLibrary::Find(FName Name)
{
	if (TStrongObjectPtr<USoundBase>* Found = Cache().Find(Name))
	{
		return Found->Get();
	}
	const FString Asset = TEXT("S_") + Name.ToString();
	const FSoftObjectPath Path(FString::Printf(TEXT("/Game/Audio/%s.%s"), *Asset, *Asset));
	USoundBase* Sound = Cast<USoundBase>(Path.TryLoad());
	Cache().Add(Name, TStrongObjectPtr<USoundBase>(Sound));
	return Sound;
}

void USOSoundLibrary::ReleaseAll()
{
	Cache().Reset();
}

int32 USOSoundLibrary::NumHeld()
{
	int32 N = 0;
	for (const TPair<FName, TStrongObjectPtr<USoundBase>>& Pair : Cache())
	{
		N += Pair.Value.IsValid();
	}
	return N;
}

void USOSoundLibrary::PlayAt(const UObject* WorldContext, FName Name, FVector Location, float Volume, float PitchJitter, ESOSoundRange Range)
{
	UWorld* World = WorldContext ? WorldContext->GetWorld() : nullptr;
	if (!World || World->GetNetMode() == NM_DedicatedServer)
	{
		return;
	}
	if (USoundBase* Sound = Find(Name))
	{
		UGameplayStatics::PlaySoundAtLocation(World, Sound, Location, FRotator::ZeroRotator, Volume, Pitch(PitchJitter), 0.0f, Attenuation(Range));
	}
}

void USOSoundLibrary::Play2D(const UObject* WorldContext, FName Name, float Volume, float PitchJitter)
{
	UWorld* World = WorldContext ? WorldContext->GetWorld() : nullptr;
	if (!World || World->GetNetMode() == NM_DedicatedServer)
	{
		return;
	}
	if (USoundBase* Sound = Find(Name))
	{
		UGameplayStatics::PlaySound2D(World, Sound, Volume, Pitch(PitchJitter));
	}
}

void USOSoundLibrary::PlayFor(const AActor* Source, FName Name, FVector Location, float Volume, ESOSoundRange Range, float PitchJitter)
{
	const APawn* Pawn = Cast<APawn>(Source);
	if (!Pawn && Source)
	{
		Pawn = Cast<APawn>(Source->GetOwner());
	}
	if (Pawn && Pawn->IsLocallyControlled() && Pawn->IsPlayerControlled())
	{
		Play2D(Source, Name, Volume, PitchJitter);
	}
	else
	{
		PlayAt(Source, Name, Location, Volume, PitchJitter, Range);
	}
}
