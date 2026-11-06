#include "SOTimeOfDaySubsystem.h"

#include "Engine/DirectionalLight.h"
#include "Engine/World.h"
#include "EngineUtils.h"

void USOTimeOfDaySubsystem::OnWorldBeginPlay(UWorld& InWorld)
{
	Super::OnWorldBeginPlay(InWorld);
	for (TActorIterator<ADirectionalLight> It(&InWorld); It; ++It)
	{
		if (It->ActorHasTag(TEXT("Sun")))
		{
			Sun = *It;
			break;
		}
	}
	UpdateSun();
}

bool USOTimeOfDaySubsystem::DoesSupportWorldType(const EWorldType::Type WorldType) const
{
	return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

TStatId USOTimeOfDaySubsystem::GetStatId() const
{
	RETURN_QUICK_DECLARE_CYCLE_STAT(USOTimeOfDaySubsystem, STATGROUP_Tickables);
}

void USOTimeOfDaySubsystem::SetHour(float NewHour)
{
	Hour = FMath::Fmod(FMath::Fmod(NewHour, 24.0f) + 24.0f, 24.0f);
	UpdateSun();
}

void USOTimeOfDaySubsystem::Tick(float DeltaTime)
{
	if (bPaused || DayLengthMinutes <= 0.0f)
	{
		return;
	}
	SetHour(Hour + DeltaTime * 24.0f / (DayLengthMinutes * 60.0f));
}

float USOTimeOfDaySubsystem::GetDaylight() const
{
	return FMath::SmoothStep(-0.08f, 0.12f, static_cast<float>(GetSunDirection().Z));
}

FVector USOTimeOfDaySubsystem::GetSunDirection() const
{
	// Arc from east (sunrise) through south (noon) to west (sunset); below the horizon at night.
	const float Noon = 0.5f * (SunriseHour + SunsetHour);
	const float HalfDay = FMath::Max(0.5f * (SunsetHour - SunriseHour), 0.1f);
	const float T = FMath::Clamp((Hour - Noon) / HalfDay, -2.0f, 2.0f); // -1 sunrise, 0 noon, +1 sunset
	const float Azimuth = FMath::DegreesToRadians(180.0f + 90.0f * T); // from north toward east: 90 east, 180 south, 270 west
	const float Elevation = FMath::DegreesToRadians(NoonElevation) * FMath::Cos(T * UE_HALF_PI);
	const float CosE = FMath::Cos(Elevation);
	return FVector(CosE * FMath::Cos(Azimuth), CosE * FMath::Sin(Azimuth), FMath::Sin(Elevation)).GetSafeNormal();
}

void USOTimeOfDaySubsystem::UpdateSun()
{
	if (ADirectionalLight* Light = Sun.Get())
	{
		// A directional light shines along its forward vector, i.e. away from the sun.
		Light->SetActorRotation((-GetSunDirection()).Rotation());
	}
}
