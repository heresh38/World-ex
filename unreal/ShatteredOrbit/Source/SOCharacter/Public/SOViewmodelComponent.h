#pragma once

#include "CoreMinimal.h"
#include "Components/SceneComponent.h"
#include "SOViewmodelComponent.generated.h"

class ASOCharacter;

/**
 * Where the gun is held. Ticks before the body meshes animate (after movement and look), and places:
 *  - itself: the first-person hold, locked to the (recoil-kicked) eye so the sights line up with the crosshair;
 *    hip / aim-down-sights blend, sway from look, bob from movement, recoil kick, sprint pose, raise, reload offsets;
 *  - the character's third-person hold: the same pose seen from outside, kept in front of the body when looking
 *    down and raised to the cheek when aiming.
 * The weapon's rigs attach to these, and the bodies' arm IK (USOLocomotionAnimInstance) reaches for the rigs' grips.
 * Eye space: +X forward, +Y right, +Z up (cm).
 */
UCLASS(ClassGroup = (ShatteredOrbit))
class SOCHARACTER_API USOViewmodelComponent : public USceneComponent
{
	GENERATED_BODY()

public:
	USOViewmodelComponent();

	/** Hip position of the gun origin (top of the pistol grip) in eye space; within reach of both arms. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	FVector HipOffset = FVector(30.0f, 13.0f, -22.0f);

	/** ADS: the sight sits this far in front of the eye, on the line of sight. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	float AdsSightDistance = 30.0f;

	/** Third person: the character's eyes sit this far above the camera's eye height (cheek weld when aiming). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	float ThirdPersonEyeLift = 7.0f;

	/** Third person: when looking down the hip hold moves forward this far (cm at straight down) to stay clear of the body. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	float ThirdPersonDownReach = 26.0f;

	void Kick(float Strength);
	void Raise() { Lower = 1.0f; }

	/** Eased ADS amount 0..1 the hold currently uses. */
	float GetAds() const { return Ads; }

	/** Updates both holds now (also called by the tick). */
	void UpdateHold(float DeltaTime);

	virtual void BeginPlay() override;
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
