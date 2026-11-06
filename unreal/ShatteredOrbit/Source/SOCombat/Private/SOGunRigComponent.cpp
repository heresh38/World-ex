#include "SOGunRigComponent.h"

#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "SOReload.h"
#include "SOWeaponData.h"

namespace
{
	const FName NMag(TEXT("mag"));
	const FName NSpare(TEXT("spare"));
	const FName NBolt(TEXT("bolt"));
	const FName NFore(TEXT("fore"));
	const FName NPouch(TEXT("pouch"));
	const FName NMagBase(TEXT("magbase"));
}

USOGunRigComponent::USOGunRigComponent()
{
	PrimaryComponentTick.bCanEverTick = false;
}

FQuat USOGunRigComponent::GltfEulerToMesh(float RX, float RY, float RZ)
{
	// three.js Euler 'XYZ': q = qx * qy * qz (right-handed, glTF axes). The axis swap (y <-> z) is a mirror,
	// so the quaternion maps (w, x, y, z) -> (w, -x, -z, -y).
	const FQuat Q = FQuat(FVector(1, 0, 0), RX) * FQuat(FVector(0, 1, 0), RY) * FQuat(FVector(0, 0, 1), RZ);
	return FQuat(-Q.X, -Q.Z, -Q.Y, Q.W);
}

UStaticMeshComponent* USOGunRigComponent::MakeMesh(FName Name, UStaticMesh* Mesh)
{
	AActor* Owner = GetOwner();
	UStaticMeshComponent* Comp = NewObject<UStaticMeshComponent>(Owner, MakeUniqueObjectName(Owner, UStaticMeshComponent::StaticClass(), Name));
	Comp->SetupAttachment(GunSpace);
	Comp->SetStaticMesh(Mesh);
	Comp->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Comp->SetGenerateOverlapEvents(false);
	Comp->SetMobility(EComponentMobility::Movable);
	if (bFirstPerson)
	{
		Comp->SetOnlyOwnerSee(true);
		Comp->SetCastShadow(false);
		Comp->SetFirstPersonPrimitiveType(EFirstPersonPrimitiveType::FirstPerson);
	}
	else
	{
		Comp->SetCastShadow(true);
	}
	Comp->RegisterComponent();
	return Comp;
}

void USOGunRigComponent::Build(const USOWeaponData* Data, bool bInFirstPerson)
{
	if (bBuilt || !Data || !GetOwner())
	{
		return;
	}
	bBuilt = true;
	bFirstPerson = bInFirstPerson;

	GunSpace = NewObject<USceneComponent>(GetOwner(), MakeUniqueObjectName(GetOwner(), USceneComponent::StaticClass(), TEXT("GunSpace")));
	GunSpace->SetupAttachment(this);
	GunSpace->SetRelativeRotation(FRotator(0.0f, -90.0f, 0.0f)); // mesh +Y (barrel) -> rig +X
	GunSpace->RegisterComponent();

	Body = MakeMesh(TEXT("Body"), Data->BodyMesh.LoadSynchronous());
	for (const FSOWeaponPart& Part : Data->Parts)
	{
		UStaticMeshComponent* Comp = MakeMesh(Part.Name, Part.Mesh.LoadSynchronous());
		Comp->ComponentTags.Add(Part.Name);
		Comp->SetRelativeLocationAndRotation(Part.RestLocation, Part.RestRotation);
		Rest.Add(Part.Name, FTransform(Part.RestRotation, Part.RestLocation));
		PartComponents.Add(Comp);
		if (Part.Name == NMag)
		{
			Spare = MakeMesh(TEXT("SpareMag"), Part.Mesh.LoadSynchronous());
			Spare->SetRelativeLocationAndRotation(Part.RestLocation, Part.RestRotation);
			Spare->SetVisibility(false);
		}
	}
	Foregrip = Data->ForegripLocation;
	Muzzle = Data->MuzzleLocation;

	if (bFirstPerson)
	{
		ArmRight = MakeMesh(TEXT("ArmRight"), Data->ArmRightMesh.LoadSynchronous());
		ArmLeft = MakeMesh(TEXT("ArmLeft"), Data->ArmLeftMesh.LoadSynchronous());
		ArmLeft->SetRelativeLocation(Foregrip);
	}
}

UStaticMeshComponent* USOGunRigComponent::GetPart(FName Name) const
{
	for (UStaticMeshComponent* Comp : PartComponents)
	{
		if (Comp && Comp->ComponentHasTag(Name))
		{
			return Comp;
		}
	}
	return nullptr;
}

FVector USOGunRigComponent::GetMuzzleLocation() const
{
	return GunSpace ? GunSpace->GetComponentTransform().TransformPosition(Muzzle) : GetComponentLocation();
}

void USOGunRigComponent::SetOwnerNoSeeAll(bool bNoSee)
{
	TArray<USceneComponent*> Children;
	if (GunSpace)
	{
		GunSpace->GetChildrenComponents(true, Children);
	}
	for (USceneComponent* Child : Children)
	{
		if (UPrimitiveComponent* Prim = Cast<UPrimitiveComponent>(Child))
		{
			Prim->SetOwnerNoSee(bNoSee);
		}
	}
}

FVector USOGunRigComponent::ResolveAnchor(FName Anchor) const
{
	auto MagPoint = [](const UStaticMeshComponent* Comp, float Up) -> FVector
	{
		if (!Comp)
		{
			return FVector::ZeroVector;
		}
		FVector Local(0.0f, 0.0f, -10.0f + Up);
		if (const UStaticMesh* Mesh = Comp->GetStaticMesh())
		{
			const FBox Box = Mesh->GetBoundingBox();
			Local = FVector(Box.GetCenter().X, Box.GetCenter().Y, Box.Min.Z + Up);
		}
		return Comp->GetRelativeTransform().TransformPosition(Local);
	};

	if (Anchor == NFore)
	{
		return Foregrip;
	}
	if (Anchor == NPouch)
	{
		return GltfToMesh(0.1f, -0.42f, -0.22f);
	}
	if (Anchor == NMag)
	{
		return MagPoint(GetPart(NMag), 3.5f);
	}
	if (Anchor == NMagBase)
	{
		return MagPoint(GetPart(NMag), 0.0f);
	}
	if (Anchor == NSpare)
	{
		return MagPoint(Spare, 3.5f);
	}
	if (Anchor == NBolt)
	{
		const UStaticMeshComponent* Bolt = GetPart(NBolt);
		return Bolt ? Bolt->GetRelativeLocation() : Foregrip;
	}
	return Foregrip;
}

void USOGunRigComponent::ApplyPose(const FSOReloadPose& Pose)
{
	if (!bBuilt)
	{
		return;
	}
	if (UStaticMeshComponent* Mag = GetPart(NMag))
	{
		const FTransform& R = Rest.FindRef(NMag);
		Mag->SetRelativeLocationAndRotation(R.GetLocation() + GltfToMesh(Pose.Mag[0], Pose.Mag[1], Pose.Mag[2]),
			R.GetRotation() * GltfEulerToMesh(Pose.Mag[3], Pose.Mag[4], Pose.Mag[5]));
		Mag->SetVisibility(Pose.bMagVisible);
		if (Spare)
		{
			Spare->SetVisibility(Pose.bSpareVisible);
			if (Pose.bSpareVisible)
			{
				Spare->SetRelativeLocationAndRotation(R.GetLocation() + GltfToMesh(Pose.Spare[0], Pose.Spare[1], Pose.Spare[2]),
					R.GetRotation() * GltfEulerToMesh(Pose.Spare[3], Pose.Spare[4], Pose.Spare[5]));
			}
		}
	}
	if (UStaticMeshComponent* Bolt = GetPart(NBolt))
	{
		const FTransform& R = Rest.FindRef(NBolt);
		Bolt->SetRelativeLocation(R.GetLocation() + GltfToMesh(0.0f, 0.0f, -Pose.Bolt));
	}
	if (ArmLeft)
	{
		if (Pose.bHand)
		{
			const FVector A = ResolveAnchor(Pose.HandAnchorA) + GltfToMesh(Pose.HandA[0], Pose.HandA[1], Pose.HandA[2]);
			const FVector B = ResolveAnchor(Pose.HandAnchorB) + GltfToMesh(Pose.HandB[0], Pose.HandB[1], Pose.HandB[2]);
			const float F = Pose.HandAlpha;
			ArmLeft->SetRelativeLocationAndRotation(FMath::Lerp(A, B, F), GltfEulerToMesh(
				FMath::Lerp(Pose.HandA[3], Pose.HandB[3], F), FMath::Lerp(Pose.HandA[4], Pose.HandB[4], F), FMath::Lerp(Pose.HandA[5], Pose.HandB[5], F)));
		}
		else
		{
			ArmLeft->SetRelativeLocationAndRotation(Foregrip, FQuat::Identity);
		}
	}
}
