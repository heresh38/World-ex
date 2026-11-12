#pragma once

#include "CoreMinimal.h"
#include "Components/SceneComponent.h"
#include "SOGunRigComponent.generated.h"

class UStaticMesh;
class UStaticMeshComponent;
class USOWeaponData;
struct FSOReloadPose;
struct FSOWeaponInstance;

/**
 * Where a hand holds something, in rig space (+X barrel, +Y right, +Z up, cm): the wrist location and an anatomical
 * basis (X along the hand wrist -> fingers, Y towards the thumb, Z out of the palm). The character's arm IK reaches
 * the wrist and turns the hand bone onto the basis, so the same grips work for any body on the shared rig.
 */
struct SOCOMBAT_API FSOHandGrip
{
	FVector Wrist = FVector::ZeroVector;
	FQuat Basis = FQuat::Identity;

	/** Basis from the finger direction and the thumb side (a proper rotation; X along, Y thumb, Z = X x Y). */
	static FQuat MakeBasis(const FVector& Along, const FVector& Thumb, bool bLeft);
	/** Out of the palm: +Z of the basis on the right hand, -Z on the (mirrored) left hand. */
	static FVector PalmNormal(const FQuat& Basis, bool bLeft);
	/** A grip whose palm centre touches Contact (the wrist sits behind it along the hand, off the palm surface). */
	static FSOHandGrip AtPalm(const FVector& Contact, const FVector& Along, const FVector& Thumb, bool bLeft);
};

/**
 * How far each finger closes, degrees per joint (knuckle, middle, tip) for index, middle, ring, little finger and
 * thumb (base, middle, tip). The arm IK turns each finger about the axis that brings it towards the palm.
 */
struct SOCOMBAT_API FSOFingerPose
{
	float Curl[5][3] = { { 0, 0, 0 }, { 0, 0, 0 }, { 0, 0, 0 }, { 0, 0, 0 }, { 0, 0, 0 } };
	/** The thumb swung round the hand's long axis toward the palm's side, degrees: it lies on the far side of what
	 *  the fingers hold (a grip between thumb and fingers), instead of through it. */
	float ThumbSpread = 0.0f;

	static FSOFingerPose Make(const float Index[3], const float Middle[3], const float Ring[3], const float Pinky[3], const float Thumb[3]);
	/** Firing hand on a pistol grip: three fingers wrapped, the index finger on the trigger, the thumb over the top. */
	static FSOFingerPose Trigger();
	/** Round a handguard / forend / vertical grip. */
	static FSOFingerPose Wrap(float Amount = 1.0f);
	/** Holding something small between thumb and fingers (rounds, shells, a speedloader, a cell). */
	static FSOFingerPose Pinch();
	/** Open palm (slapping a magazine home, pushing a lid). */
	static FSOFingerPose Flat();
	/** Relaxed, half closed. */
	static FSOFingerPose Relaxed();
	static FSOFingerPose Lerp(const FSOFingerPose& A, const FSOFingerPose& B, float Alpha);
};

/**
 * A posable gun: body + reload parts (+ spare mag) built from a USOWeaponData.
 * The component's +X is the barrel. Children live under GunSpace, which turns the imported mesh space (gun along +Y)
 * onto +X. ApplyPose() moves the parts and the off hand's grip (reload choreography); GetHandTargets() tells the
 * holder's arm IK where both hands go.
 */
UCLASS(ClassGroup = (ShatteredOrbit))
class SOCOMBAT_API USOGunRigComponent : public USceneComponent
{
	GENERATED_BODY()

public:
	USOGunRigComponent();

	/** Creates the mesh components. First person: owner-only, first-person rendering, no shadows. */
	void Build(const USOWeaponData* Data, bool bInFirstPerson);

	/** The copy's looks: mounts its optic on the rail (hiding the built-in sight it replaces), paints the body in its
	 *  finish and the glow in its rarity colour (material names are an API: gun_body, gun_glow). */
	void Dress(const FSOWeaponInstance& Instance);

	/** Removes the gun: every mesh it made, then itself. (Destroying only this component would hand its meshes to
	 *  whatever it was attached to: they would stay there.) */
	void Dismantle();

	/** Shows or hides the whole gun; parts the pose or a mounted optic keep hidden stay hidden. */
	void SetShown(bool bInShown);

	void ApplyPose(const FSOReloadPose& Pose);
	/** The turn of a rotary gun's barrel cluster (the part named `spin`), radians about the bore. */
	void SetBarrelSpin(float Radians) { BarrelSpin = Radians; }

	/** World-space muzzle position. */
	FVector GetMuzzleLocation() const;

	/** Off-hand anchor in mesh space (cm) against the parts as currently posed: fore, mag, spare, magbase, bolt,
	 *  charge, slide, pump, cyl, ejector, loader, shell, round, hatch, biomass, pouch, free. */
	FVector ResolveAnchor(FName Anchor) const;

	UStaticMeshComponent* GetPart(FName Name) const;
	UStaticMeshComponent* GetSpare() const { return Spare; }

	/** World-space wrist targets with the hand bases as rotations (see FSOHandGrip). False until built. */
	bool GetHandTargets(FTransform& OutRight, FTransform& OutLeft) const;

	/** How both hands close right now (the off hand's follows what it is holding through the reload). */
	void GetFingerPoses(FSOFingerPose& OutRight, FSOFingerPose& OutLeft) const { OutRight = RightFingers; OutLeft = LeftFingers; }

	/** Finger pose for the off hand on an anchor (fore, mag, magbase, bolt, round, ...). */
	FSOFingerPose FingersForAnchor(FName Anchor) const;

	/** The gun body's bounds in rig space (+X barrel, +Y right, +Z up, cm). */
	FBox GetRigBounds() const;

	/** The whole gun as it is carried: the body with its parts (magazine, bolt, ...) and the mounted optic. */
	FBox GetWornBounds() const;

	/** Rig-space grips (tests / debugging). */
	const FSOHandGrip& GetRightGrip() const { return RightGrip; }
	const FSOHandGrip& GetLeftGrip() const { return LeftGrip; }
	/** Off-hand grip for an anchor (fore, mag, spare, magbase, bolt, pouch) against the current part poses. */
	FSOHandGrip GripForAnchor(FName Anchor) const;
	USceneComponent* GetGunSpace() const { return GunSpace; }
	bool IsBuilt() const { return bBuilt; }
	/** A handgun (short barrel, held out in both hands). */
	bool IsHandgun() const { return bHandgun; }

	/** A rail optic is mounted (the gun's irons fold away, aiming looks through the optic). */
	bool IsOpticMounted() const { return bOpticMounted; }
	/** The optic on the rail (null with factory sights). */
	const UStaticMeshComponent* GetOptic() const { return bOpticMounted ? Optic.Get() : nullptr; }

	/** The gun carries its own optic (the energy line's built-in red dots) and no rail optic replaces it. */
	bool HasBuiltInOptic() const;

	/** glTF gun space (m, x right / y up / z barrel) -> imported mesh space (cm, gun along +Y). */
	static FVector GltfToMesh(float X, float Y, float Z) { return FVector(X * 100.0f, Z * 100.0f, Y * 100.0f); }
	/** glTF Euler XYZ (rad) -> mesh space rotation. */
	static FQuat GltfEulerToMesh(float RX, float RY, float RZ);

	/** Imported mesh space (gun along +Y) -> rig space (gun along +X). */
	static FVector MeshToRig(const FVector& V) { return FVector(V.Y, -V.X, V.Z); }

	/** Applies owner visibility rules to every mesh (third person: hide from owner while in first person). */
	void SetOwnerNoSeeAll(bool bNoSee);

private:
	UStaticMeshComponent* MakeMesh(FName Name, UStaticMesh* Mesh);

	UPROPERTY(Transient)
	TObjectPtr<USceneComponent> GunSpace;

	UPROPERTY(Transient)
	TObjectPtr<UStaticMeshComponent> Body;

	UPROPERTY(Transient)
	TArray<TObjectPtr<UStaticMeshComponent>> PartComponents;

	UPROPERTY(Transient)
	TObjectPtr<UStaticMeshComponent> Spare;

	UPROPERTY(Transient)
	TObjectPtr<UStaticMeshComponent> Optic;

	TMap<FName, FTransform> Rest;      // relative to the parent part (or the gun)
	TMap<FName, FTransform> RootRest;  // relative to the gun
	FVector Foregrip = FVector::ZeroVector;
	FSOHandGrip RightGrip;
	FSOHandGrip LeftGrip;
	FSOFingerPose RightFingers;
	FSOFingerPose LeftFingers;
	FSOFingerPose CurFingers;
	/** Where the off hand was when the current reload segment began (anchor "cur"). */
	FSOHandGrip CurGrip;
	int32 LastSegment = -1;
	FName Archetype;
	bool bShown = true;
	bool bOpticMounted = false;
	float BarrelSpin = 0.0f;
	bool bHandgun = false;

	/** A part's current transform in mesh space (nested parts included). */
	FTransform PartInMesh(const UStaticMeshComponent* Comp) const;
	FVector Muzzle = FVector::ZeroVector;
	bool bFirstPerson = false;
	bool bBuilt = false;
};
