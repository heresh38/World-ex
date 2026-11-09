#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "SOWeather.generated.h"

class AActor;
class UAudioComponent;
class UInstancedStaticMeshComponent;
class UMaterialInstanceDynamic;
class UMaterialParameterCollection;
class USoundBase;

/** The sky over an area. */
UENUM(BlueprintType)
enum class ESOWeather : uint8
{
	Clear,
	Cloudy,
	Overcast,
	Rain,
	Storm,
	Fog,
	Windy,   // dry, gusty: dust and litter in the air
};

/** What a weather means for the world (blended between states). */
USTRUCT(BlueprintType)
struct SOWORLD_API FSOWeatherLook
{
	GENERATED_BODY()

	/** 0..1 cloud cover. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Weather") float Cloud = 0.2f;
	/** Multiplier on the level's height-fog density. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Weather") float Fog = 1.0f;
	/** 0..1 rain. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Weather") float Rain = 0.0f;
	/** Mean wind (m/s). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Weather") float Wind = 3.0f;
	/** 0..1 dust and litter in the air. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Weather") float Dust = 0.2f;
	/** 0..1 how gusty. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Weather") float Gusts = 0.3f;
};

/**
 * Weather and the air of a level: drifts between states (clear, cloudy, overcast, rain, storm, fog, windy) and blends
 * their look; a wandering, gusting wind; wetness that builds in rain and dries after. It drives the sky (volumetric
 * cloud coverage / density, height-fog density, sun and sky-light strength), the material parameter collection
 * /Game/Environments/MPC_SOWeather (WindX, WindY, Wind, Gust, Wetness, Rain: foliage sway, wet streets), lightning and
 * thunder in storms, wind / rain ambience, and the life in the air round the camera: dust motes in the light, leaves
 * and litter skittering on the wind, rain streaks, steam from vents and open manholes, smoke from exhaust stacks
 * (emitters published by ASONexusCity). Presentation only; every machine runs its own (the state is seeded, so a
 * server can later replicate SetWeather).
 */
UCLASS()
class SOWORLD_API USOWeatherSubsystem : public UTickableWorldSubsystem
{
	GENERATED_BODY()

public:
	/** Change the weather, blending over BlendSeconds. */
	UFUNCTION(BlueprintCallable, Category = "SO|Weather")
	void SetWeather(ESOWeather NewWeather, float BlendSeconds = 60.0f);

	UFUNCTION(BlueprintPure, Category = "SO|Weather")
	ESOWeather GetWeather() const { return Target; }

	/** Wind velocity (cm/s, horizontal), gusts included. */
	UFUNCTION(BlueprintPure, Category = "SO|Weather")
	FVector GetWind() const { return WindVelocity; }

	UFUNCTION(BlueprintPure, Category = "SO|Weather")
	float GetRain() const { return Look.Rain; }

	UFUNCTION(BlueprintPure, Category = "SO|Weather")
	float GetWetness() const { return Wetness; }

	/** Set the streets' wetness now (tests, pictures, a level that starts after rain). */
	UFUNCTION(BlueprintCallable, Category = "SO|Weather")
	void SetWetness(float NewWetness) { Wetness = FMath::Clamp(NewWetness, 0.0f, 1.0f); }

	UFUNCTION(BlueprintPure, Category = "SO|Weather")
	FSOWeatherLook GetLook() const { return Look; }

	/** Pick the next weather by itself every few minutes. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Weather")
	bool bAutomatic = true;

	/** Real minutes a weather lasts before the next one is chosen (random within). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Weather")
	FVector2D MinutesPerWeather = FVector2D(6.0f, 14.0f);

	static FSOWeatherLook LookOf(ESOWeather Weather);

	//~ UTickableWorldSubsystem
	virtual void OnWorldBeginPlay(UWorld& InWorld) override;
	virtual void Tick(float DeltaTime) override;
	virtual TStatId GetStatId() const override;
	virtual void Deinitialize() override;

protected:
	virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;

private:
	void ApplyEnvironment(float DeltaTime);
	void TickAir(float DeltaTime);
	bool EnsureHost();
	UInstancedStaticMeshComponent* MakeISM(const TCHAR* Mesh, const TCHAR* Material, bool bTranslucent, int32 CustomFloats);

	ESOWeather Target = ESOWeather::Cloudy;
	FSOWeatherLook From, To, Look;
	float Blend = 1.0f, BlendTime = 60.0f;
	float NextChange = 0.0f;
	float Time = 0.0f;
	float WindAngle = 0.6f;
	FVector WindVelocity = FVector::ZeroVector;
	float Gust = 0.0f;
	float Wetness = 0.0f;
	float EnvTimer = 0.0f;
	float LightningTimer = 8.0f, Flash = 0.0f;
	float GustSoundTimer = 6.0f;
	bool bCloudChecked = false;
	FRandomStream Random;

	// the level's own values (captured once)
	float BaseFog = -1.0f, BaseSun = -1.0f, BaseSky = -1.0f;

	TWeakObjectPtr<AActor> Host;
	TWeakObjectPtr<UInstancedStaticMeshComponent> Motes, RainStreaks, Steam, Smoke;
	TArray<TWeakObjectPtr<UInstancedStaticMeshComponent>> Litter;
	UPROPERTY(Transient) TObjectPtr<UMaterialParameterCollection> Params;
	UPROPERTY(Transient) TObjectPtr<UMaterialInstanceDynamic> CloudMID;
	UPROPERTY(Transient) TObjectPtr<UAudioComponent> WindLoop;
	UPROPERTY(Transient) TObjectPtr<UAudioComponent> RainLoop;

	struct FMote { FVector P; FVector V; float Phase; };
	struct FDrop { FVector P; };
	struct FBit { FVector P; FVector V; FRotator R; FRotator Spin; float Ground; int32 Kind; bool bAir; };
	struct FPuff { FVector P; FVector V; float Age; float Life; float Size0; float Size1; FLinearColor Color; float Alpha; };
	TArray<FMote> MoteState;
	TArray<FDrop> DropState;
	TArray<FBit> Bits;
	TArray<FPuff> SteamPuffs, SmokePuffs;
	float SteamTimer = 0.0f, SmokeTimer = 0.0f;
	FVector LastEye = FVector::ZeroVector;
};
