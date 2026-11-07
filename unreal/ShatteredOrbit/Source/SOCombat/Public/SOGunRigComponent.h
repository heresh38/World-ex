#pragma once

#include "CoreMinimal.h"
#include "Components/SceneComponent.h"
#include "SOGunRigComponent.generated.h"

class UStaticMesh;
class UStaticMeshComponent;
class USOWeaponData;
struct FSOReloadPose;

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

	void ApplyPose(const FSOReloadPose& Pose);

	/** World-space muzzle position. */
	FVector GetMuzzleLocation() const;

	/** Hand anchor in mesh space (cm): fore, mag, spare, magbase, bolt, pouch. */
	FVector ResolveAnchor(FName Anchor) const;

	UStaticMeshComponent* GetPart(FName Name) const;
	UStaticMeshComponent* GetSpare() const { return Spare; }

	/** World-space wrist targets with the hand bases as rotations (see FSOHandGrip). False until built. */
	bool GetHandTargets(FTransform& OutRight, FTransform& OutLeft) const;

	/** Rig-space grips (tests / debugging). */
	const FSOHandGrip& GetRightGrip() const { return RightGrip; }
	const FSOHandGrip& GetLeftGrip() const { return LeftGrip; }
	/** Off-hand grip for an anchor (fore, mag, spare, magbase, bolt, pouch) against the current part poses. */
	FSOHandGrip GripForAnchor(FName Anchor) const;
	USceneComponent* GetGunSpace() const { return GunSpace; }
	bool IsBuilt() const { return bBuilt; }

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

	TMap<FName, FTransform> Rest;
	FVector Foregrip = FVector::ZeroVector;
	FSOHandGrip RightGrip;
	FSOHandGrip LeftGrip;
	FVector Muzzle = FVector::ZeroVector;
	bool bFirstPerson = false;
	bool bBuilt = false;
};
