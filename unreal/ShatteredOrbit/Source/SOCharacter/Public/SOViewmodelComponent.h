#pragma once

#include "CoreMinimal.h"
#include "Components/SceneComponent.h"
#include "SOViewmodelComponent.generated.h"

class ASOCharacter;

/**
 * Where the gun is held. Ticks before the body meshes animate (after movement and look), and places:
 *  - itself: the first-person hold, locked to the (recoil-kicked) eye so the sights line up with the crosshair;
 *    hip / aim-down-sights blend, sway from look, bob from movement, recoil kick, sprint pose, raise, reload offsets;
 *  - the character's third-person hold: the body's own (butt in the right shoulder pocket, bore on the crosshair's
 *    point; handguns out in both hands), shouldered higher when aiming, never through the head.
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
	FVector HipOffset = FVector(27.0f, 11.5f, -15.5f);          // (it sat 22 cm under the eye: too low, not enough of the gun showed)

	/** Handguns (short barrel, support hand on the grip) are held out at arm's length, higher and nearer the middle. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	FVector HandgunHipOffset = FVector(40.0f, 8.5f, -10.5f);

	/** First person, while reloading: the gun comes up (cm: X forward, Y right, Z up) ... */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	FVector ReloadLift = FVector(-4.0f, -6.0f, 8.0f);

	/** ... and cants toward the view (degrees: X roll, Y pitch nose up, Z yaw inward) so the mag well is in sight. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	FVector ReloadTilt = FVector(-24.0f, 10.0f, 10.0f);

	/** ADS: the sight sits this far in front of the eye, on the line of sight. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	float AdsSightDistance = 9.0f;                               // (long guns. At 30, then 19, the eye sat over the stock: the comb filled the
	                                                             // lower half of the picture and the rear sight was a pinhole. This close the
	                                                             // stock is under and behind the eye, out of the view, and the ring is wide.)

	/** The same for a handgun, held out at arm's length. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	float AdsHandgunSightDistance = 24.0f;

	/** ADS through a rail optic: its eye point (set per optic in gun_attach.glb so the window fills about a quarter of
	 *  the view) sits this far in front of the eye. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	float AdsOpticEyeDistance = 0.0f;

	/** The same for an optic on a handgun: held out at arm's length, its window is a small frame ahead of the eye
	 *  (at the eye it hid the whole pistol and half the view). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Viewmodel")
	float AdsHandgunOpticDistance = 12.0f;

	/** ADS through a gun's built-in optic: its sight point sits this far in front of the eye. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	float AdsBuiltInOpticDistance = 4.0f;

	/** Third person: the shoulder pocket (where the butt sits) from the right shoulder joint, actor axes at rest (cm:
	 *  X forward, Y right, Z up): in front of the joint, toward the chest, a little below it. Turns with the chest. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	FVector PocketFromShoulder = FVector(9.0f, -4.5f, -4.0f);

	/** Third person, aiming: the butt rides this much higher and nearer the cheek in the pocket (shoulder raised), so
	 *  the comb meets the cheek of the canted head. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	FVector PocketAimShift = FVector(1.5f, -2.5f, 7.0f);

	/** Third person: height of the butt's middle in rig space (cm above the top of the pistol grip). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	float ButtHeight = 1.5f;

	/** Third person, handguns: the grip from the shoulders' middle along the aim (cm: forward, right, up), hip / aimed. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	FVector HandgunHold = FVector(38.0f, 7.0f, -6.0f);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	FVector HandgunAimHold = FVector(44.0f, 5.0f, 2.0f);

	/** Third person: the gun points at the crosshair's point, but never at one nearer than this (cm). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	float ThirdPersonMinAimDistance = 400.0f;

	/** Third person, sprinting: the grip from the shoulders' middle (cm, actor axes: forward, right, up) and the gun's
	 *  turn (pitch, yaw, roll) against the facing: carried low across the chest, muzzle down and to the left. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	FVector CarryOffset = FVector(24.0f, 7.0f, -22.0f);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	FRotator CarryRot = FRotator(-30.0f, -42.0f, -18.0f);

	/** Handguns while sprinting: low by the chest, muzzle down. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	FVector HandgunCarryOffset = FVector(26.0f, 6.0f, -20.0f);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	FRotator HandgunCarryRot = FRotator(-40.0f, -10.0f, 0.0f);

	/** Third person, reloading: the gun down in front of the chest, muzzle a little up and in, canted toward the body. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	FVector ReloadOffset = FVector(30.0f, 8.0f, -14.0f);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	FRotator ReloadRot = FRotator(12.0f, -18.0f, -28.0f);

	/** Without a body pose yet: the pocket in actor space (cm). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	FVector DefaultPocket = FVector(1.0f, 12.0f, 48.5f);

	/** The shoulder pocket and the shoulders' middle (actor space, cm) from the body's last pose; false = defaults. */
	bool GetShoulderPoints(const ASOCharacter* Character, FVector& OutPocket, FVector& OutChest) const;

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
	float StrafeK = 0.0f;
	float AirK = 0.0f;
	float SlideK = 0.0f;
	float MantleK = 0.0f;
	float ReloadK = 0.0f;
	FVector HoldDir = FVector::ForwardVector;
	bool bHoldDirValid = false;

	FTransform ThirdPersonHoldTransform(const ASOCharacter* Character, bool bHandgun, float Dt);
};
