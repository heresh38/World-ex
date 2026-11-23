#pragma once

#include "CoreMinimal.h"
#include "Components/SceneComponent.h"
#include "SOViewmodelComponent.generated.h"

class ASOCharacter;
class USOGunRigComponent;
class USOWeaponData;

/**
 * Where the body holds its gun: ONE gun in ONE body's hands, the same in first person (the game: seen from the body's
 * own eyes) and in the third-person test view (the owner, 2026-11-23: one model, one camera). Ticks after movement and
 * look and before the body animates, and places the character's gun hold (the gun rides it; the body's arm IK reaches
 * for its grips):
 *  - the body's own hold by the gun's class (FSOStance): relaxed low across the body, at the ready on the shoulder,
 *    handguns out in both hands; the sprint's carry, the reload's, a steep look down;
 *  - on the sights, the sight on the line of the body's eyes (where the camera is in first person), the kick turning
 *    the gun about its sight;
 *  - the recoil's kick, the raise, the reload's own moves and the motion's inertia on top;
 *  - never into a wall (pulled back, then up), never out of the firing hand's reach (the owner's ULTIMATE rule: the
 *    hands are always on the gun).
 * Actor and eye space: +X forward, +Y right, +Z up (cm).
 */
UCLASS(ClassGroup = (ShatteredOrbit))
class SOCHARACTER_API USOViewmodelComponent : public USceneComponent
{
	GENERATED_BODY()

public:
	USOViewmodelComponent();

	/** On the sights of a long gun the gun stays shouldered (its butt in the pocket) and the camera alone comes to its
	 *  sight's line (the head keeps its own pose): this far ahead of the butt (cm along the gun: where a cheek on the
	 *  comb would put the eye). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	float CheekFromButt = 13.0f;

	/** ...but never nearer the sight than this (cm): irons (a rear sight nearer the eye is a blur), a gun's built-in
	 *  optic (its sight point), a rail optic (its sight point is its eye point, set per optic in gun_attach.glb). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	float IronsEyeRelief = 6.0f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	float BuiltInOpticEyeRelief = 4.0f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	float OpticEyeRelief = 0.0f;

	/** A handgun on the sights is held out in both hands, its sight on the eyes' line where the firing wrist is this
	 *  share of the arm from its shoulder (the arms nearly straight); without a body, this far ahead of the eyes (cm). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	float HandgunReach = 0.88f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	float AdsHandgunSightDistance = 30.0f;

	/** Without a gun's shape yet: a long gun's sight this far ahead of the eyes (cm). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	float AdsSightDistance = 16.0f;

	/** The shoulder pocket (where the butt sits) from the right shoulder joint, actor axes at rest (cm: X forward, Y
	 *  right, Z up): in front of the joint, toward the chest, a little below it. Turns with the chest. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	FVector PocketFromShoulder = FVector(9.0f, -4.5f, -4.0f);

	/** Height of the butt's middle in rig space (cm above the top of the pistol grip). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	float ButtHeight = 1.5f;

	/** The gun points at the crosshair's point, but never at one nearer than this (cm). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	float MinAimDistance = 400.0f;

	/** A long gun pointed steeply down: where its middle hangs from, in actor space off the chest point (ahead, right,
	 *  up); the gun's own pitch is held within these (degrees), and it cants inward this much at the full low hold. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	FVector LowHold = FVector(22.0f, 10.0f, -27.0f);
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	float MaxDownPitch = 48.0f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	float MaxUpPitch = 65.0f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	float LowCant = 28.0f;

	/** Sprinting, as the gun's data says (USOWeaponData::SprintCarry, the owner, 2026-11-15: "on running we lower the gun
	 *  for rifles ... smaller guns like smg/pistol/revolver/handcannon we take it up"): the grip from the shoulders'
	 *  middle (cm, actor axes: forward, right, up) and the gun's turn (pitch, yaw, roll) against the facing. Low (a long
	 *  gun): the low ready, across the chest, muzzle down and to the left. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	FVector CarryOffset = FVector(26.0f, 9.0f, -8.0f);          // (the front of it in the corner of the eyes' picture: 24
	                                                             // below the shoulders and 30 degrees down it was out of it;
	                                                             // at the shoulders' height the firing wrist bent 85)
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	FRotator CarryRot = FRotator(-18.0f, -32.0f, -10.0f);

	/** Short (an SMG): up part of the way, in front of the chest, muzzle up and in. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	FVector ShortCarryOffset = FVector(26.0f, 8.0f, -10.0f);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	FRotator ShortCarryRot = FRotator(32.0f, -18.0f, -12.0f);

	/** High (a handgun): up by the face in both hands, muzzle to the sky. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	FVector HandgunCarryOffset = FVector(22.0f, 9.0f, 6.0f);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	FRotator HandgunCarryRot = FRotator(72.0f, -8.0f, 0.0f);

	/** Reloading: the gun up in the workspace in front of the chest, where the eyes see the work (one body: the camera
	 *  is in its eyes; held at the belly, 14 cm lower, a first-person reload showed the muzzle alone at the foot of the
	 *  picture), muzzle a little up and in, canted toward the body. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	FVector ReloadOffset = FVector(40.0f, 6.0f, -2.0f);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	FRotator ReloadRot = FRotator(12.0f, -18.0f, -28.0f);

	/** Without a body pose yet: the pocket in actor space (cm). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	FVector DefaultPocket = FVector(1.0f, 12.0f, 48.5f);

	/** The firing hand's wrist is kept within this share of the arm's length from its shoulder (the gun comes in when it
	 *  would be further: the hand is always on its handle). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	float FiringReach = 0.95f;

	/** The support hand's place on the gun is kept within this share of its arm from its shoulder: the gun comes in
	 *  toward that shoulder (a long gun's butt no further back than this far in front of the firing shoulder joint, cm). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	float SupportReach = 0.87f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	float ButtAheadOfShoulder = 2.0f;

	/** The shoulder pocket and the shoulders' middle (actor space, cm) from the body's last pose; false = defaults. */
	bool GetShoulderPoints(const ASOCharacter* Character, FVector& OutPocket, FVector& OutChest) const;

	void Kick(float Strength);
	void Raise() { Lower = 1.0f; }

	/** Eased ADS amount 0..1 the hold currently uses. */
	float GetAds() const { return Ads; }

	/** How far a wall in front has pushed the gun back (cm, eased). */
	float GetWallPush() const { return WallK; }

	/** Places the gun hold now (also called by the tick). */
	void UpdateHold(float DeltaTime);

	virtual void BeginPlay() override;
	virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

private:
	float Ads = 0.0f;
	float KickBack = 0.0f;   // m
	float KickPitch = 0.0f;  // rad
	float Lower = 1.0f;
	float RunK = 0.0f;
	float RunV = 0.0f;       // (the carries and the trail are springs: a little overshoot, then settled)
	float StrafeK = 0.0f;
	float StrafeV = 0.0f;
	float SlideV = 0.0f, MantleV = 0.0f;
	float AirK = 0.0f;
	float SlideK = 0.0f;
	float MantleK = 0.0f;
	float ReloadK = 0.0f;
	float WallK = 0.0f, WallV = 0.0f;
	FVector HoldDir = FVector::ForwardVector;
	bool bHoldDirValid = false;

	/** Where the body holds the gun: the stance's place, the sprint's carry, the reload's, a steep look down. */
	FTransform HoldTransform(const ASOCharacter* Character, const USOWeaponData* Data, bool bHandgun, float Dt, float RunT);
	/** Pulled back from a wall in front (along itself, then the muzzle turned up past it), eased. */
	FTransform ClearOfWalls(const ASOCharacter* Character, const USOGunRigComponent* Rig, const FTransform& Hold, float Dt);
	/** Never further from the firing shoulder than the arm reaches, nor folded into it: the hand stays on its handle. */
	FTransform InFiringReach(const ASOCharacter* Character, const USOGunRigComponent* Rig, const FTransform& Hold) const;
	/** Never further from the support shoulder than that arm reaches with a bend left in it: the gun comes in toward it
	 *  (the support hand is on the gun too; slid back along the gun its fingers closed in it, or it left a handgun). */
	FTransform InSupportReach(const ASOCharacter* Character, const USOGunRigComponent* Rig, const FTransform& Hold) const;
	/** The support wrist's place on the gun (the rig's frame, the fitted hold), its shoulder and arm in the body's last pose. */
	bool SupportArm(const ASOCharacter* Character, const USOGunRigComponent* Rig, FVector& OutInGun, FVector& OutShoulder, float& OutArm) const;
	/** A handgun held out on the sights: how far ahead of the eye its sight is, from the reach of the arms. */
	float HandgunRelief(const ASOCharacter* Character, const USOGunRigComponent* Rig, const FVector& SightRig, const FTransform& Eye) const;
};
