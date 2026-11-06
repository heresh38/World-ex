#pragma once

#include "CoreMinimal.h"
#include "Components/SceneComponent.h"
#include "SOGunRigComponent.generated.h"

class UStaticMesh;
class UStaticMeshComponent;
class USOWeaponData;
struct FSOReloadPose;

/**
 * A posable gun: body + reload parts (+ spare mag, + the first-person arms) built from a USOWeaponData.
 * The component's +X is the barrel. Children live under GunSpace, which turns the imported mesh space (gun along +Y)
 * onto +X. ApplyPose() moves the parts and the left hand like reload.js GunRig.apply().
 */
UCLASS(ClassGroup = (ShatteredOrbit))
class SOCOMBAT_API USOGunRigComponent : public USceneComponent
{
	GENERATED_BODY()

public:
	USOGunRigComponent();

	/** Creates the mesh components. First person: owner-only, first-person rendering, no shadows, with arms. */
	void Build(const USOWeaponData* Data, bool bInFirstPerson);

	void ApplyPose(const FSOReloadPose& Pose);

	/** World-space muzzle position. */
	FVector GetMuzzleLocation() const;

	/** Hand anchor in mesh space (cm): fore, mag, spare, magbase, bolt, pouch. */
	FVector ResolveAnchor(FName Anchor) const;

	UStaticMeshComponent* GetPart(FName Name) const;
	UStaticMeshComponent* GetSpare() const { return Spare; }
	UStaticMeshComponent* GetArmLeft() const { return ArmLeft; }
	USceneComponent* GetGunSpace() const { return GunSpace; }
	bool IsBuilt() const { return bBuilt; }

	/** glTF gun space (m, x right / y up / z barrel) -> imported mesh space (cm, gun along +Y). */
	static FVector GltfToMesh(float X, float Y, float Z) { return FVector(X * 100.0f, Z * 100.0f, Y * 100.0f); }
	/** glTF Euler XYZ (rad) -> mesh space rotation. */
	static FQuat GltfEulerToMesh(float RX, float RY, float RZ);

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
	TObjectPtr<UStaticMeshComponent> ArmLeft;

	UPROPERTY(Transient)
	TObjectPtr<UStaticMeshComponent> ArmRight;

	TMap<FName, FTransform> Rest;
	FVector Foregrip = FVector::ZeroVector;
	FVector Muzzle = FVector::ZeroVector;
	bool bFirstPerson = false;
	bool bBuilt = false;
};
