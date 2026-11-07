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

// --- Hand grips ---------------------------------------------------------------------------------

FQuat FSOHandGrip::MakeBasis(const FVector& Along, const FVector& Thumb, bool bLeft)
{
	const FVector A = Along.GetSafeNormal();
	const FVector T = (Thumb - A * FVector::DotProduct(Thumb, A)).GetSafeNormal();
	// Always a proper rotation (Z = X x Y). The hands are mirror images, so the palm is +Z on the right hand and -Z on
	// the left one (see PalmNormal).
	return FQuat(FMatrix(A, T, FVector::CrossProduct(A, T), FVector::ZeroVector));
}

FVector FSOHandGrip::PalmNormal(const FQuat& Basis, bool bLeft)
{
	return bLeft ? -Basis.GetAxisZ() : Basis.GetAxisZ();
}

FSOHandGrip FSOHandGrip::AtPalm(const FVector& Contact, const FVector& Along, const FVector& Thumb, bool bLeft)
{
	// Palm centre ~5 cm from the wrist along the hand, the palm surface ~1.3 cm off the bone.
	FSOHandGrip Grip;
	Grip.Basis = MakeBasis(Along, Thumb, bLeft);
	Grip.Wrist = Contact - Grip.Basis.GetAxisX() * 5.0f - PalmNormal(Grip.Basis, bLeft) * 1.3f;
	return Grip;
}

namespace
{
	// Rig space: +X barrel, +Y right, +Z up (cm), origin at the top of the pistol grip.
	// Firing hand: palm on the right of the grip, fingers round its front, thumb on top.
	FSOHandGrip RifleGrip()
	{
		return FSOHandGrip::AtPalm(FVector(-2.2f, 1.6f, -4.5f), FVector(0.93f, 0.0f, -0.37f), FVector(0.37f, 0.0f, 0.93f), false);
	}

	// Support hand under the handguard: palm up, fingers wrapping the right side, thumb along the left pointing forward.
	FSOHandGrip SupportGrip(const FVector& Foregrip)
	{
		return FSOHandGrip::AtPalm(Foregrip + FVector(0.0f, 0.0f, 1.2f), FVector(0.3f, 0.95f, 0.0f), FVector(1.0f, 0.0f, 0.0f), true);
	}

	// Holding a magazine from its left side: palm right, fingers round the front, thumb up.
	FSOHandGrip MagGrip(const FVector& Point)
	{
		return FSOHandGrip::AtPalm(Point + FVector(0.0f, -2.0f, 0.0f), FVector(1.0f, 0.0f, -0.25f), FVector(0.0f, 0.0f, 1.0f), true);
	}

	// Seating slap from below: palm up under the floor plate.
	FSOHandGrip SlapGrip(const FVector& Point)
	{
		return FSOHandGrip::AtPalm(Point + FVector(0.0f, 0.0f, -0.8f), FVector(1.0f, 0.0f, 0.0f), FVector(0.0f, -1.0f, 0.0f), true);
	}

	// Overhand rack: palm down on the top right of the receiver, fingers hooked over the right side onto the
	// charging handle, so the hand rides the handle back and never enters the receiver.
	FSOHandGrip RackGrip(const FVector& Handle)
	{
		return FSOHandGrip::AtPalm(FVector(Handle.X, 1.0f, Handle.Z + 4.8f), FVector(0.0f, 0.8f, -0.6f), FVector(-1.0f, 0.0f, 0.0f), true);
	}
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
		Comp->SetCastHiddenShadow(true); // the gun's shadow stays while its owner looks through first person
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
	RightGrip = RifleGrip();
	LeftGrip = SupportGrip(MeshToRig(Foregrip));
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
		return Bolt ? Bolt->GetRelativeLocation() : Foregrip; // current (travelling) position of the handle
	}
	return Foregrip;
}

FSOHandGrip USOGunRigComponent::GripForAnchor(FName Anchor) const
{
	const FVector Point = MeshToRig(ResolveAnchor(Anchor));
	if (Anchor == NFore || Anchor.IsNone())
	{
		return SupportGrip(MeshToRig(Foregrip));
	}
	if (Anchor == NMagBase)
	{
		return SlapGrip(Point);
	}
	if (Anchor == NBolt)
	{
		return RackGrip(Point);
	}
	return MagGrip(Point); // mag, spare, pouch
}

bool USOGunRigComponent::GetHandTargets(FTransform& OutRight, FTransform& OutLeft) const
{
	if (!bBuilt)
	{
		return false;
	}
	const FTransform Rig = GetComponentTransform();
	OutRight = FTransform(RightGrip.Basis, RightGrip.Wrist) * Rig;
	OutLeft = FTransform(LeftGrip.Basis, LeftGrip.Wrist) * Rig;
	return true;
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
	// Off hand: from grip A to grip B. Offsets only matter for the pouch (the keys' other offsets were tuned for the
	// browser build's arm mesh); the hand's turn comes from the grips themselves.
	if (Pose.bHand)
	{
		auto Grip = [this](FName Anchor, const float* Offset)
		{
			FSOHandGrip G = GripForAnchor(Anchor);
			if (Anchor == NPouch)
			{
				G.Wrist += MeshToRig(GltfToMesh(Offset[0], Offset[1], Offset[2]));
			}
			return G;
		};
		const FSOHandGrip A = Grip(Pose.HandAnchorA, Pose.HandA);
		const FSOHandGrip B = Grip(Pose.HandAnchorB, Pose.HandB);
		LeftGrip.Wrist = FMath::Lerp(A.Wrist, B.Wrist, Pose.HandAlpha);
		LeftGrip.Basis = FQuat::Slerp(A.Basis, B.Basis, Pose.HandAlpha);
		if (Pose.HandAnchorA != Pose.HandAnchorB)
		{
			// Between two grips the hand arcs out past the gun's left side instead of cutting through it, and comes
			// down onto the charging handle from above (over the top edge of the receiver).
			const float Arc = FMath::Sin(PI * FMath::Clamp(Pose.HandAlpha, 0.0f, 1.0f));
			const bool bOverTop = Pose.HandAnchorA == NBolt || Pose.HandAnchorB == NBolt;
			LeftGrip.Wrist += FVector(0.0f, -8.0f, bOverTop ? 9.0f : 0.0f) * Arc;
		}
	}
	else
	{
		LeftGrip = SupportGrip(MeshToRig(Foregrip));
	}
}
