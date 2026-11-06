#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "SOTimeOfDaySubsystem.generated.h"

class ADirectionalLight;

/**
 * World clock skeleton (from the browser build's clock + day/night): hour 0..24, one day lasts DayLengthMinutes,
 * the sun rises in the east at 06:00, stands south at noon and sets in the west at 20:00.
 * A directional light tagged "Sun" is rotated to match. Palettes, moon and sky arrive in later stages.
 */
UCLASS()
class SOWORLD_API USOTimeOfDaySubsystem : public UTickableWorldSubsystem
{
	GENERATED_BODY()

public:
	UFUNCTION(BlueprintPure, Category = "SO|Time")
	float GetHour() const { return Hour; }

	UFUNCTION(BlueprintCallable, Category = "SO|Time")
	void SetHour(float NewHour);

	UFUNCTION(BlueprintCallable, Category = "SO|Time")
	void SetPaused(bool bInPaused) { bPaused = bInPaused; }

	UFUNCTION(BlueprintPure, Category = "SO|Time")
	bool IsPaused() const { return bPaused; }

	/** 0 at night, 1 in full day (smooth across dawn and dusk). */
	UFUNCTION(BlueprintPure, Category = "SO|Time")
	float GetDaylight() const;

	/** Unit vector toward the sun (UE space: +X north, +Y east, +Z up). */
	UFUNCTION(BlueprintPure, Category = "SO|Time")
	FVector GetSunDirection() const;

	/** Real minutes per in-game day. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Time")
	float DayLengthMinutes = 40.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Time")
	float SunriseHour = 6.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Time")
	float SunsetHour = 20.0f;

	/** Peak sun elevation at noon in degrees. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Time")
	float NoonElevation = 62.0f;

	//~ UTickableWorldSubsystem
	virtual void OnWorldBeginPlay(UWorld& InWorld) override;
	virtual void Tick(float DeltaTime) override;
	virtual TStatId GetStatId() const override;

protected:
	virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;

private:
	void UpdateSun();

	float Hour = 10.0f;
	bool bPaused = false;
	TWeakObjectPtr<ADirectionalLight> Sun;
};
