#include "SOGunRigComponent.h"

#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "SOLootLibrary.h"
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

	// Handguns: the support hand wraps the firing hand from the left (palm on the grip's left side, fingers round the
	// front below the trigger guard, thumb forward along the frame).
	FSOHandGrip HandgunSupportGrip()
	{
		return FSOHandGrip::AtPalm(FVector(-1.5f, -2.4f, -5.5f), FVector(0.35f, 0.45f, -0.8f), FVector(0.9f, 0.0f, 0.4f), true);
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

// --- Finger poses --------------------------------------------------------------------------------

FSOFingerPose FSOFingerPose::Make(const float Index[3], const float Middle[3], const float Ring[3], const float Pinky[3], const float Thumb[3])
{
	FSOFingerPose P;
	const float* Rows[5] = { Index, Middle, Ring, Pinky, Thumb };
	for (int32 f = 0; f < 5; ++f)
	{
		for (int32 j = 0; j < 3; ++j)
		{
			P.Curl[f][j] = Rows[f][j];
		}
	}
	return P;
}

FSOFingerPose FSOFingerPose::Trigger()
{
	const float I[3] = { 28, 40, 22 }, M[3] = { 78, 82, 48 }, R[3] = { 82, 84, 50 }, P[3] = { 86, 84, 50 }, T[3] = { 30, 28, 22 };
	return Make(I, M, R, P, T);
}

FSOFingerPose FSOFingerPose::Wrap(float Amount)
{
	const float a = Amount;
	const float I[3] = { 50 * a, 58 * a, 34 * a }, M[3] = { 56 * a, 62 * a, 36 * a }, R[3] = { 62 * a, 66 * a, 38 * a }, P[3] = { 68 * a, 70 * a, 40 * a },
		T[3] = { 18 * a, 16 * a, 12 * a };
	return Make(I, M, R, P, T);
}

FSOFingerPose FSOFingerPose::Pinch()
{
	const float I[3] = { 42, 50, 28 }, M[3] = { 50, 58, 32 }, R[3] = { 70, 82, 44 }, P[3] = { 76, 86, 46 }, T[3] = { 34, 26, 18 };
	return Make(I, M, R, P, T);
}

FSOFingerPose FSOFingerPose::Flat()
{
	const float I[3] = { 6, 6, 4 }, M[3] = { 6, 6, 4 }, R[3] = { 8, 8, 4 }, P[3] = { 10, 8, 4 }, T[3] = { 0, 4, 4 };
	return Make(I, M, R, P, T);
}

FSOFingerPose FSOFingerPose::Relaxed()
{
	const float I[3] = { 18, 22, 14 }, M[3] = { 22, 26, 16 }, R[3] = { 26, 30, 18 }, P[3] = { 30, 32, 20 }, T[3] = { 10, 10, 8 };
	return Make(I, M, R, P, T);
}

FSOFingerPose FSOFingerPose::Lerp(const FSOFingerPose& A, const FSOFingerPose& B, float Alpha)
{
	FSOFingerPose P;
	for (int32 f = 0; f < 5; ++f)
	{
		for (int32 j = 0; j < 3; ++j)
		{
			P.Curl[f][j] = FMath::Lerp(A.Curl[f][j], B.Curl[f][j], Alpha);
		}
	}
	return P;
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
		const FTransform PartRest(Part.RestRotation, Part.RestLocation);
		// Nested parts (crane > cylinder > rounds) ride on their parent part; rest transforms are kept relative to it.
		UStaticMeshComponent* ParentComp = Part.Parent.IsNone() ? nullptr : GetPart(Part.Parent);
		RootRest.Add(Part.Name, PartRest);
		if (ParentComp)
		{
			Comp->AttachToComponent(ParentComp, FAttachmentTransformRules::KeepRelativeTransform);
			const FTransform Relative = PartRest.GetRelativeTransform(RootRest.FindRef(Part.Parent));
			Comp->SetRelativeTransform(Relative);
			Rest.Add(Part.Name, Relative);
		}
		else
		{
			Comp->SetRelativeLocationAndRotation(Part.RestLocation, Part.RestRotation);
			Rest.Add(Part.Name, PartRest);
		}
		if (Part.Name.ToString().StartsWith(TEXT("x_")))
		{
			Comp->SetVisibility(false); // loose reload props (shell, round, casing, speedloader) appear only in reloads
		}
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
	Archetype = Data->Archetype;
	bHandgun = Data->MuzzleLocation.Y < 35.0f; // short barrel, the support hand on the grip
	RightGrip = RifleGrip();
	LeftGrip = bHandgun ? HandgunSupportGrip() : SupportGrip(MeshToRig(Foregrip));
	RightFingers = FSOFingerPose::Trigger();
	LeftFingers = FingersForAnchor(NFore);
}

FBox USOGunRigComponent::GetRigBounds() const
{
	const UStaticMesh* Mesh = Body ? Body->GetStaticMesh() : nullptr;
	if (!Mesh)
	{
		return FBox(FVector(-20.0f, -3.0f, -12.0f), FVector(40.0f, 3.0f, 10.0f));
	}
	const FBox B = Mesh->GetBoundingBox();
	FBox Out(ForceInit);
	Out += MeshToRig(B.Min);
	Out += MeshToRig(B.Max);
	return Out;
}

FSOFingerPose USOGunRigComponent::FingersForAnchor(FName Anchor) const
{
	if (Anchor == NFore || Anchor.IsNone() || Anchor == TEXT("pump"))
	{
		// handguns: the support hand wraps the firing hand; long guns: round the handguard / forend
		return bHandgun ? FSOFingerPose::Wrap(1.15f) : FSOFingerPose::Wrap(Anchor == TEXT("pump") ? 1.1f : 1.0f);
	}
	if (Anchor == NMagBase || Anchor == TEXT("hatch"))
	{
		return FSOFingerPose::Flat();
	}
	if (Anchor == NBolt || Anchor == TEXT("charge") || Anchor == TEXT("slide"))
	{
		return FSOFingerPose::Wrap(1.2f); // hooked over the handle / gripping the slide serrations
	}
	if (Anchor == NMag || Anchor == NSpare || Anchor == TEXT("biomass"))
	{
		return FSOFingerPose::Wrap(0.85f);
	}
	if (Anchor == TEXT("round") || Anchor == TEXT("shell") || Anchor == TEXT("loader") || Anchor == TEXT("cyl") || Anchor == TEXT("ejector"))
	{
		return FSOFingerPose::Pinch();
	}
	return FSOFingerPose::Relaxed(); // pouch, free
}

void USOGunRigComponent::SetShown(bool bInShown)
{
	bShown = bInShown;
	SetVisibility(bShown, true);
	// parts the pose or the optic keep hidden stay hidden (SetVisibility above reaches every child)
	for (UStaticMeshComponent* Part : PartComponents)
	{
		if (!Part)
		{
			continue;
		}
		const FString Name = Part->ComponentTags.Num() > 0 ? Part->ComponentTags[0].ToString() : FString();
		if (Name.StartsWith(TEXT("x_")) || ((Name == TEXT("OPTIC") || Name == TEXT("irons")) && bOpticMounted))
		{
			Part->SetVisibility(false);
		}
	}
	if (Spare)
	{
		Spare->SetVisibility(false);
	}
}

void USOGunRigComponent::Dress(const FSOWeaponInstance& Instance)
{
	if (!bBuilt || !GunSpace)
	{
		return;
	}
	const USOLootTables* Tables = USOLootLibrary::GetTables();
	const USOWeaponData* Data = Tables ? Tables->LoadArchetype(Instance.Archetype) : nullptr;

	// Optic on the rail (data.js SIGHTS; gun_attach.glb ATT_<id>).
	if (Optic)
	{
		Optic->DestroyComponent();
		Optic = nullptr;
	}
	UStaticMeshComponent* BuiltIn = GetPart(TEXT("OPTIC"));
	const FSOSightInfo* Sight = Tables && Instance.Sight != TEXT("default") ? Tables->FindSight(Instance.Sight) : nullptr;
	if (Sight && Data && Data->bHasRail && !Sight->Mesh.IsNull())
	{
		Optic = MakeMesh(TEXT("Optic"), Sight->Mesh.LoadSynchronous());
		Optic->SetRelativeLocation(Data->RailLocation);
		bOpticMounted = true;
	}
	else
	{
		bOpticMounted = false;
	}
	if (BuiltIn)
	{
		BuiltIn->SetVisibility(bShown && !bOpticMounted);
	}
	// A mounted optic folds the iron sights away so nothing of the gun crowds its window.
	if (UStaticMeshComponent* Irons = GetPart(TEXT("irons")))
	{
		Irons->SetVisibility(bShown && !bOpticMounted);
	}

	// Finish and rarity glow by material name.
	FLinearColor BodyColor = FLinearColor::White;
	bool bPaint = false;
	if (Tables)
	{
		if (const FSOShaderInfo* Shader = Tables->Shaders.FindByPredicate([&](const FSOShaderInfo& S) { return S.Id == Instance.Shader; }))
		{
			BodyColor = Shader->Body;
			bPaint = Data && Data->WeaponClass == ESOWeaponClass::Energy; // kinetic / horror keep their own materials
		}
	}
	const FLinearColor Glow = Tables ? Tables->GetRarity(Instance.Rarity).Color : FLinearColor(0.2f, 0.8f, 1.0f);
	TArray<USceneComponent*> Children;
	GunSpace->GetChildrenComponents(true, Children);
	for (USceneComponent* Child : Children)
	{
		UStaticMeshComponent* Mesh = Cast<UStaticMeshComponent>(Child);
		if (!Mesh || !Mesh->GetStaticMesh())
		{
			continue;
		}
		const TArray<FName> Slots = Mesh->GetMaterialSlotNames();
		for (int32 i = 0; i < Slots.Num(); ++i)
		{
			const FString SlotName = Slots[i].ToString();
			const bool bGlow = SlotName.StartsWith(TEXT("gun_glow"));
			const bool bBody = bPaint && SlotName.StartsWith(TEXT("gun_body"));
			if (!bGlow && !bBody)
			{
				continue;
			}
			UMaterialInstanceDynamic* MID = Mesh->CreateDynamicMaterialInstance(i);
			if (!MID)
			{
				continue;
			}
			if (bGlow)
			{
				MID->SetVectorParameterValue(TEXT("BaseColorTint"), Glow);
				MID->SetVectorParameterValue(TEXT("EmissiveColor"), Glow);
			}
			else
			{
				MID->SetVectorParameterValue(TEXT("BaseColorTint"), BodyColor);
			}
		}
	}
}

bool USOGunRigComponent::HasBuiltInOptic() const
{
	return !bOpticMounted && GetPart(TEXT("OPTIC")) != nullptr;
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

FTransform USOGunRigComponent::PartInMesh(const UStaticMeshComponent* Comp) const
{
	if (!Comp || !GunSpace)
	{
		return FTransform::Identity;
	}
	return Comp->GetComponentTransform().GetRelativeTransform(GunSpace->GetComponentTransform());
}

FVector USOGunRigComponent::ResolveAnchor(FName Anchor) const
{
	auto MagPoint = [this](const UStaticMeshComponent* Comp, float Up) -> FVector
	{
		if (!Comp)
		{
			return FVector(0.0f, 9.0f, -5.0f + Up); // no magazine (energy cells): under the receiver ahead of the grip
		}
		FVector Local(0.0f, 0.0f, -10.0f + Up);
		if (const UStaticMesh* Mesh = Comp->GetStaticMesh())
		{
			const FBox Box = Mesh->GetBoundingBox();
			Local = FVector(Box.GetCenter().X, Box.GetCenter().Y, Box.Min.Z + Up);
		}
		return PartInMesh(Comp).TransformPosition(Local);
	};
	auto At = [this](FName Part, const FVector& Local) -> FVector
	{
		const UStaticMeshComponent* Comp = GetPart(Part);
		return Comp ? PartInMesh(Comp).TransformPosition(Local) : Foregrip;
	};
	auto Centre = [this](FName Part) -> FVector
	{
		const UStaticMeshComponent* Comp = GetPart(Part);
		if (!Comp)
		{
			return Foregrip;
		}
		const UStaticMesh* Mesh = Comp->GetStaticMesh();
		return PartInMesh(Comp).TransformPosition(Mesh ? Mesh->GetBoundingBox().GetCenter() : FVector::ZeroVector);
	};

	if (Anchor == NFore || Anchor.IsNone()) return Foregrip;
	if (Anchor == NPouch) return GltfToMesh(0.1f, -0.42f, -0.22f);
	if (Anchor == TEXT("free")) return FVector::ZeroVector;
	if (Anchor == NMag) return MagPoint(GetPart(NMag), 3.5f);
	if (Anchor == NMagBase) return MagPoint(GetPart(NMag), 0.0f);
	if (Anchor == NSpare) return MagPoint(Spare, 3.5f);
	if (Anchor == TEXT("loader")) return At(TEXT("x_speedloader"), GltfToMesh(0, 0, -0.03f));
	if (Anchor == TEXT("cyl")) return At(TEXT("cylinder"), GltfToMesh(0.012f, -0.01f, 0));
	if (Anchor == TEXT("ejector")) return At(TEXT("crane"), GltfToMesh(-0.004f, 0.025f, 0.06f));
	if (Anchor == TEXT("shell")) return At(TEXT("x_shell"), GltfToMesh(0, -0.016f, -0.05f));
	if (Anchor == TEXT("round")) return At(TEXT("x_round"), GltfToMesh(-0.008f, 0.004f, -0.02f));
	if (Anchor == NBolt)
	{
		const UStaticMeshComponent* Bolt = GetPart(NBolt);
		return Bolt ? PartInMesh(Bolt).GetLocation() : Foregrip; // the handle's pivot, travelling with it
	}
	if (Anchor == TEXT("charge") || Anchor == TEXT("slide"))
	{
		// the top of the part, where the palm goes
		const UStaticMeshComponent* Comp = GetPart(Anchor);
		if (const UStaticMesh* Mesh = Comp ? Comp->GetStaticMesh() : nullptr)
		{
			const FBox Box = Mesh->GetBoundingBox();
			return PartInMesh(Comp).TransformPosition(FVector(Box.GetCenter().X, Box.GetCenter().Y, Box.Max.Z));
		}
	}
	return Centre(Anchor); // pump, hatch, biomass, ...
}

FSOHandGrip USOGunRigComponent::GripForAnchor(FName Anchor) const
{
	const FVector Point = MeshToRig(ResolveAnchor(Anchor));
	if (Anchor == NFore || Anchor.IsNone())
	{
		return bHandgun ? HandgunSupportGrip() : SupportGrip(MeshToRig(Foregrip));
	}
	if (Anchor == TEXT("pump"))
	{
		return SupportGrip(Point - FVector(0.0f, 0.0f, 2.5f)); // palm under the forend
	}
	if (Anchor == NMagBase)
	{
		return SlapGrip(Point);
	}
	if (Anchor == NBolt)
	{
		return RackGrip(Point);
	}
	if (Anchor == TEXT("charge") || Anchor == TEXT("slide"))
	{
		return FSOHandGrip::AtPalm(Point + FVector(0.0f, 1.0f, 0.8f), FVector(0.0f, 0.8f, -0.6f), FVector(-1.0f, 0.0f, 0.0f), true);
	}
	return MagGrip(Point); // mag, spare, pouch, cyl, ejector, loader, shell, round, hatch, biomass, free
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
	auto Place = [this](FName Name, const FVector& Offset, const FQuat& Turn, bool bShow = true)
	{
		if (UStaticMeshComponent* Comp = GetPart(Name))
		{
			const FTransform& R = Rest.FindRef(Name);
			Comp->SetRelativeLocationAndRotation(R.GetLocation() + Offset, R.GetRotation() * Turn);
			Comp->SetVisibility(bShown && bShow);
		}
	};
	auto Six = [](const float* P) { return GltfToMesh(P[0], P[1], P[2]); };
	auto SixRot = [](const float* P) { return GltfEulerToMesh(P[3], P[4], P[5]); };

	// magazine (old) and spare
	if (UStaticMeshComponent* Mag = GetPart(NMag))
	{
		Place(NMag, Six(Pose.Mag), SixRot(Pose.Mag), Pose.bMagVisible);
		if (Spare)
		{
			Spare->SetVisibility(bShown && Pose.bSpareVisible);
			if (Pose.bSpareVisible)
			{
				const FTransform& R = Rest.FindRef(NMag);
				Spare->SetRelativeLocationAndRotation(R.GetLocation() + Six(Pose.Spare), R.GetRotation() * SixRot(Pose.Spare));
			}
		}
	}
	// sliding parts back along the bore; the bolt-action bolt also turns about it
	Place(NBolt, GltfToMesh(0.0f, 0.0f, -Pose.Bolt), GltfEulerToMesh(0.0f, 0.0f, Pose.BoltRot));
	Place(TEXT("charge"), GltfToMesh(0.0f, Pose.ChargeUp, -Pose.Charge), FQuat::Identity);
	Place(TEXT("slide"), GltfToMesh(0.0f, 0.0f, -Pose.Slide), FQuat::Identity);
	Place(TEXT("pump"), GltfToMesh(0.0f, 0.0f, -Pose.Pump), FQuat::Identity);
	// revolver: crane swings out, cylinder spins, rounds leave and return
	Place(TEXT("crane"), FVector::ZeroVector, GltfEulerToMesh(0.0f, 0.0f, Pose.Crane));
	Place(TEXT("cylinder"), FVector::ZeroVector, GltfEulerToMesh(0.0f, 0.0f, Pose.Spin));
	if (UStaticMeshComponent* Rounds = GetPart(TEXT("rounds")))
	{
		Rounds->SetVisibility(bShown && Pose.bRounds);
	}
	// horror: the hatch (flank flap about the barrel, brood lid about X) and the biomass
	const bool bBrood = Archetype == TEXT("brood");
	Place(TEXT("hatch"), FVector::ZeroVector, bBrood ? GltfEulerToMesh(Pose.Hatch, 0.0f, 0.0f) : GltfEulerToMesh(0.0f, 0.0f, Pose.Hatch));
	Place(TEXT("biomass"), Six(Pose.Bio), SixRot(Pose.Bio), Pose.bBio);
	// loose props held by the hand (absolute in gun space)
	if (UStaticMeshComponent* Loader = GetPart(TEXT("x_speedloader")))
	{
		Loader->SetVisibility(bShown && Pose.bLoader);
		if (Pose.bLoader)
		{
			Loader->SetRelativeLocationAndRotation(GltfToMesh(Pose.Loader[0], Pose.Loader[1], -0.0245f + Pose.Loader[2]), GltfEulerToMesh(0.0f, 0.0f, Pose.Loader[3]));
		}
	}
	for (const TPair<FName, const float*>& Prop : { TPair<FName, const float*>(TEXT("x_shell"), Pose.Shell), TPair<FName, const float*>(TEXT("x_round"), Pose.Round) })
	{
		if (UStaticMeshComponent* Comp = GetPart(Prop.Key))
		{
			const bool bShow = Prop.Key == TEXT("x_shell") ? Pose.bShell : Pose.bRound;
			Comp->SetVisibility(bShown && bShow);
			if (bShow)
			{
				Comp->SetRelativeLocationAndRotation(Six(Prop.Value), SixRot(Prop.Value));
			}
		}
	}

	// Off hand: from grip A to grip B ("cur" = where the hand was when the segment began). The keys' offsets move
	// the palm (they were authored for the browser build's palm pivot); the hand's turn comes from the grips.
	if (Pose.Segment != LastSegment)
	{
		LastSegment = Pose.Segment;
		CurGrip = LeftGrip;
		CurFingers = LeftFingers;
	}
	if (Pose.bHand)
	{
		auto Grip = [this](FName Anchor, const float* Offset)
		{
			if (Anchor == TEXT("cur"))
			{
				return CurGrip;
			}
			FSOHandGrip G = GripForAnchor(Anchor);
			if (Anchor != NBolt && Anchor != TEXT("charge") && Anchor != TEXT("slide"))
			{
				G.Wrist += MeshToRig(GltfToMesh(Offset[0], Offset[1], Offset[2]));
			}
			return G;
		};
		const FSOHandGrip A = Grip(Pose.HandAnchorA, Pose.HandA);
		const FSOHandGrip B = Grip(Pose.HandAnchorB, Pose.HandB);
		LeftGrip.Wrist = FMath::Lerp(A.Wrist, B.Wrist, Pose.HandAlpha);
		LeftGrip.Basis = FQuat::Slerp(A.Basis, B.Basis, Pose.HandAlpha);
		// the fingers open in flight and close on what the hand arrives at
		auto Fingers = [this](FName Anchor) { return Anchor == TEXT("cur") ? CurFingers : FingersForAnchor(Anchor); };
		const float Close = FMath::Clamp(Pose.HandAlpha, 0.0f, 1.0f);
		const FSOFingerPose Between = FSOFingerPose::Lerp(Fingers(Pose.HandAnchorA), Fingers(Pose.HandAnchorB), Close);
		const float Open = Pose.HandAnchorA != Pose.HandAnchorB ? FMath::Sin(PI * Close) * 0.6f : 0.0f;
		LeftFingers = FSOFingerPose::Lerp(Between, FSOFingerPose::Flat(), Open);
		if (Pose.HandAnchorA != Pose.HandAnchorB)
		{
			// Between two grips the hand arcs out past the gun's left side instead of cutting through it, and comes
			// down onto a charging handle / slide from above (over the top edge of the receiver).
			const float Arc = FMath::Sin(PI * FMath::Clamp(Pose.HandAlpha, 0.0f, 1.0f));
			auto Over = [](FName N) { return N == NBolt || N == TEXT("charge") || N == TEXT("slide"); };
			const bool bOverTop = Over(Pose.HandAnchorA) || Over(Pose.HandAnchorB);
			LeftGrip.Wrist += FVector(0.0f, -8.0f, bOverTop ? 9.0f : 0.0f) * Arc;
		}
	}
	else
	{
		LeftGrip = bHandgun ? HandgunSupportGrip() : SupportGrip(MeshToRig(Foregrip));
		LeftFingers = FingersForAnchor(NFore);
	}
}
