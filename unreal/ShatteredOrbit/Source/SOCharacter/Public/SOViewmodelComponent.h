#pragma once

#include "CoreMinimal.h"
#include "Components/SceneComponent.h"
#include "SOViewmodelComponent.generated.h"

class ASOCharacter;

/**
 * The first-person holder (port of the browser build's viewmodel.js): sits on the first-person camera and places
 * the weapon's first-person rig at the hip or with the sight on the camera axis (ADS), plus sway from look input,
 * bob from movement, recoil kick, the sprint pose, the raise on equip and the reload timeline's gun offsets.
 * Camera space: +X forward, +Y right, +Z up (cm).
 */
UCLASS(ClassGroup = (ShatteredOrbit))
class SOCHARACTER_API USOViewmodelComponent : public USceneComponent
{
	GENERATED_BODY()

public:
	USOViewmodelComponent();

	/** Hip position of the gun origin (grip) in camera space. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Viewmodel")
	FVector HipOffset = FVector(44.0f, 17.0f, -20.0f);

	/** ADS: the sight sits this far in front of the eye. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Viewmodel")
	float AdsSightDistance = 18.0f;

	/** ADS: the eye sits this far above the sight mount so the line of sight clears the receiver (iron sights). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Viewmodel")
	float AdsEyeLift = 2.5f;

	void Kick(float Strength);
	void Raise() { Lower = 1.0f; }

	/** Eased ADS amount 0..1 the holder currently uses. */
	float GetAds() const { return Ads; }

	virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

private:
	float Ads = 0.0f;
	float KickBack = 0.0f;   // m
	float KickPitch = 0.0f;  // rad
	float SwayX = 0.0f;
	float SwayY = 0.0f;
	float BobT = 0.0f;
	float Lower = 1.0f;
	float RunK = 0.0f;
};
