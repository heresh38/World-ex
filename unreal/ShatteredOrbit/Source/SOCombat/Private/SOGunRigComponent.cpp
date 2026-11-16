#include "SOGunRigComponent.h"

#include "Dom/JsonObject.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "SOData.h"

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
		// (the hand runs forward and only a little down: square to a raked grip, 22 degrees down, it left the wrist
		// that much more to make up from a forearm that comes up to the grip from below)
		return FSOHandGrip::AtPalm(FVector(-2.2f, 1.6f, -4.5f), FVector(0.975f, 0.0f, -0.22f), FVector(0.22f, 0.0f, 0.975f), false);
	}

	// Handguns: the support hand wraps the firing hand from the left (palm on the grip's left side, fingers round the
	// front below the trigger guard, thumb forward along the frame).
	FSOHandGrip HandgunSupportGrip()
	{
		// (the hand runs forward and round the front of the grip, hardly down: pointing down the grip as it did, the
		// wrist was bent over a right angle. The palm stands a finger's thickness off the grip: the firing hand's
		// fingertips lie under it.)
		return FSOHandGrip::AtPalm(FVector(-1.5f, -3.6f, -5.0f), FVector(0.72f, 0.62f, -0.3f), FVector(0.6f, 0.0f, 0.8f), true);
	}

	// Support hand on the handguard, a C grip: the palm on its lower LEFT, facing up and in; the fingers go under it and
	// up its right side; the thumb lies forward along its left side. The hand runs forward and to the right, so the
	// wrist carries on from a forearm that comes up to the gun from behind and below. (Laid flat under the gun with
	// the fingers straight across it, the wrist was turned through a right angle and the thumb had nowhere to go but
	// up over the top.)
	FSOHandGrip SupportGrip(const FVector& Foregrip)
	{
		// (palm normal (0, .45, .89): mostly up; the hand 35 degrees off the barrel and only a little down, so a
		// forearm rising to it from a low elbow bends the wrist back as little as an under grip allows)
		return FSOHandGrip::AtPalm(Foregrip + FVector(0.0f, -1.2f, 0.4f), FVector(0.82f, 0.51f, -0.26f), FVector(1.0f, 0.0f, 0.0f), true);
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

// --- A gun's own hold ----------------------------------------------------------------------------

bool FSOGunHold::bIgnoreFiles = false;

namespace
{
	const TCHAR* HoldFingers[5] = { TEXT("index"), TEXT("middle"), TEXT("ring"), TEXT("little"), TEXT("thumbCurl") };

	bool ReadVector(const TSharedPtr<FJsonObject>& Obj, const TCHAR* Key, FVector& Out)
	{
		const TArray<TSharedPtr<FJsonValue>>* A = nullptr;
		if (!Obj->TryGetArrayField(Key, A) || A->Num() != 3)
		{
			return false;
		}
		Out = FVector((*A)[0]->AsNumber(), (*A)[1]->AsNumber(), (*A)[2]->AsNumber());
		return true;
	}

	bool ReadHand(const TSharedPtr<FJsonObject>& Root, const TCHAR* Key, bool bLeft, FSOHandGrip& Grip, FSOFingerPose& Fingers)
	{
		const TSharedPtr<FJsonObject>* Hand = nullptr;
		FVector Wrist, Along, Thumb;
		if (!Root->TryGetObjectField(Key, Hand) || !ReadVector(*Hand, TEXT("wrist"), Wrist) || !ReadVector(*Hand, TEXT("along"), Along) || !ReadVector(*Hand, TEXT("thumb"), Thumb)
			|| Along.IsNearlyZero() || Thumb.IsNearlyZero())
		{
			return false;
		}
		Grip.Wrist = Wrist;
		Grip.Basis = FSOHandGrip::MakeBasis(Along, Thumb, bLeft);
		for (int32 F = 0; F < 5; ++F)
		{
			FVector Curl;
			if (!ReadVector(*Hand, HoldFingers[F], Curl))
			{
				return false;
			}
			Fingers.Curl[F][0] = static_cast<float>(Curl.X);
			Fingers.Curl[F][1] = static_cast<float>(Curl.Y);
			Fingers.Curl[F][2] = static_cast<float>(Curl.Z);
		}
		Fingers.ThumbSpread = static_cast<float>((*Hand)->GetNumberField(TEXT("thumbSpread")));
		Fingers.ThumbIn = static_cast<float>((*Hand)->GetNumberField(TEXT("thumbIn")));
		double Lift = 0.0;
		Fingers.IndexLift = (*Hand)->TryGetNumberField(TEXT("indexLift"), Lift) ? static_cast<float>(Lift) : 0.0f;
		double Together = 0.0;
		Fingers.Together = (*Hand)->TryGetNumberField(TEXT("together"), Together) ? static_cast<float>(Together) : 0.0f;
		return true;
	}

	FString WriteHand(const TCHAR* Key, const FSOHandGrip& Grip, const FSOFingerPose& Fingers)
	{
		const FVector A = Grip.Basis.GetAxisX(), T = Grip.Basis.GetAxisY();
		FString Out = FString::Printf(TEXT("  \"%s\": {\n    \"wrist\": [%.2f, %.2f, %.2f],\n    \"along\": [%.3f, %.3f, %.3f],\n    \"thumb\": [%.3f, %.3f, %.3f],\n"),
			Key, Grip.Wrist.X, Grip.Wrist.Y, Grip.Wrist.Z, A.X, A.Y, A.Z, T.X, T.Y, T.Z);
		for (int32 F = 0; F < 5; ++F)
		{
			Out += FString::Printf(TEXT("    \"%s\": [%.0f, %.0f, %.0f],\n"), HoldFingers[F], Fingers.Curl[F][0], Fingers.Curl[F][1], Fingers.Curl[F][2]);
		}
		Out += FString::Printf(TEXT("    \"thumbSpread\": %.0f,\n    \"thumbIn\": %.0f,\n    \"indexLift\": %.0f,\n    \"together\": %.2f\n  }"), Fingers.ThumbSpread, Fingers.ThumbIn, Fingers.IndexLift, Fingers.Together);
		return Out;
	}
}

bool FSOGunHold::Load(FName Archetype, FSOGunHold& Out)
{
	FString Text;
	TSharedPtr<FJsonObject> Root;
	if (bIgnoreFiles || Archetype.IsNone() || !SOData::LoadText(File(Archetype), Text) || !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Root) || !Root.IsValid())
	{
		return false;
	}
	FSOGunHold Read;
	if (!ReadHand(Root, TEXT("firing"), false, Read.Firing, Read.FiringFingers) || !ReadHand(Root, TEXT("support"), true, Read.Support, Read.SupportFingers))
	{
		UE_LOG(LogTemp, Warning, TEXT("%s: the hold's file does not hold a whole hold: the gun is fitted as it is picked up"), *File(Archetype));
		return false;
	}
	Out = Read;
	return true;
}

FString FSOGunHold::ToJson(FName Archetype, const FString& About) const
{
	return FString::Printf(TEXT("{\n  \"gun\": \"%s\",\n  \"about\": \"%s\",\n  \"frame\": \"cm in the gun's frame: +X along the barrel, +Y to the right, +Z up, from the top of the pistol grip. "
		"wrist: the wrist joint. along: the way the hand runs, wrist to knuckles. thumb: the hand's thumb side. "
		"A finger's three numbers: degrees closed at the knuckle, the middle joint and the tip. thumbSpread: the thumb swung round the hand toward the palm's side. thumbIn: drawn in toward the fingers.\",\n"
		"%s,\n%s\n}\n"),
		*Archetype.ToString(), *About.ReplaceCharWithEscapedChar(), *WriteHand(TEXT("firing"), Firing, FiringFingers), *WriteHand(TEXT("support"), Support, SupportFingers));
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
	P.ThumbSpread = FMath::Lerp(A.ThumbSpread, B.ThumbSpread, Alpha);
	P.ThumbIn = FMath::Lerp(A.ThumbIn, B.ThumbIn, Alpha);
	P.IndexLift = FMath::Lerp(A.IndexLift, B.IndexLift, Alpha);
	P.Together = FMath::Lerp(A.Together, B.Together, Alpha);
	return P;
}

USOGunRigComponent::USOGunRigComponent()
{
	PrimaryComponentTick.bCanEverTick = false;
}

FQuat USOGunRigComponent::GltfEulerToMesh(float RX, float RY, float RZ)
{
	// glTF Euler 'XYZ': q = qx * qy * qz (right-handed, glTF axes). The axis swap (y <-> z) is a mirror,
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
	Comp->bReceivesDecals = false;
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
	bSnugGrip = Data->bSnugGrip;
	RightGrip = RifleGrip();
	LeftGrip = bHandgun ? HandgunSupportGrip() : SupportGrip(MeshToRig(Foregrip));
	RightFingers = FSOFingerPose::Trigger();
	LeftFingers = FingersForAnchor(NFore);
	// the gun's own hold, when it brought one (Data/holds/<archetype>.json): the hands rest where it says
	bHasHold = FSOGunHold::Load(Archetype, Hold);
	if (bHasHold)
	{
		RightGrip = Hold.Firing;
		LeftGrip = Hold.Support;
		RightFingers = Hold.FiringFingers;
		LeftFingers = Hold.SupportFingers;
	}
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

void USOGunRigComponent::Dismantle()
{
	TArray<USceneComponent*> Made;
	GetChildrenComponents(true, Made);
	for (USceneComponent* Part : Made)
	{
		if (Part && Part->GetOwner() == GetOwner())
		{
			Part->DestroyComponent();
		}
	}
	Body = nullptr;
	Spare = nullptr;
	Optic = nullptr;
	GunSpace = nullptr;
	PartComponents.Reset();
	bBuilt = false;
	DestroyComponent();
}

FBox USOGunRigComponent::GetWornBounds() const
{
	FBox Out = GetRigBounds();
	auto Add = [this, &Out](const UStaticMeshComponent* Comp)
	{
		const UStaticMesh* Mesh = Comp ? Comp->GetStaticMesh() : nullptr;
		if (!Mesh || Comp == Body || Comp == Spare)
		{
			return;
		}
		const FTransform InMesh = PartInMesh(Comp);
		FVector Corners[8];
		Mesh->GetBoundingBox().GetVertices(Corners);
		for (const FVector& C : Corners)
		{
			Out += MeshToRig(InMesh.TransformPosition(C));
		}
	};
	for (const UStaticMeshComponent* Part : PartComponents)
	{
		Add(Part);
	}
	Add(Optic);
	return Out;
}

FSOFingerPose USOGunRigComponent::FingersForAnchor(FName Anchor) const
{
	if (bHasHold && (Anchor == NFore || Anchor.IsNone()))
	{
		return Hold.SupportFingers;                             // (where the support hand rests: the gun's own hold)
	}
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
	FLinearColor Glow = Tables ? Tables->GetRarity(Instance.Rarity).Color : FLinearColor(0.2f, 0.8f, 1.0f);
	if (Data && Data->GlowColor.A > 0.0f)
	{
		Glow = Data->GlowColor;   // the set's light, whatever the copy's rarity (one palette a set: game_data.json "palettes")
	}
	else if (Data && Data->SetId == TEXT("void_requiem"))
	{
		Glow = FLinearColor(0.3f, 0.06f, 1.0f);
	}
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
			const bool bLens = SlotName.StartsWith(TEXT("gun_lens"));
			UMaterialInstanceDynamic* MID = bLens ? nullptr : Mesh->CreateDynamicMaterialInstance(i);
			if (!MID)
			{
				continue;
			}
			if (!bGlow)
			{
				// No two copies are worn alike (the owner: "every gun that drops should have a slightly different wear in
				// the look so it's not just plastic looking"): how hard this copy was used comes from its own id (the same
				// copy always looks the same), and nothing is left factory-clean.
				FRandomStream Use(GetTypeHash(Instance.Uid) ^ GetTypeHash(Slots[i]));
				const float Used = Use.FRandRange(0.0f, 1.0f);                  // 0 = looked after, 1 = dragged through a war
				// (each layer: the least it may be, and how far this copy's use takes the material's own amount; a scratch
				// layer near 1 stripes the whole gun, so it stays the smallest)
				struct FLayer { const TCHAR* Name; float Least, Lo, Hi; };
				const FLayer Layers[] = { { TEXT("EdgeWear"), 0.3f, 0.65f, 1.3f }, { TEXT("Scratches"), 0.1f, 0.5f, 1.45f }, { TEXT("Grime"), 0.18f, 0.55f, 1.5f } };
				for (const FLayer& Layer : Layers)
				{
					const float Base = FMath::Max(MID->K2_GetScalarParameterValue(Layer.Name), Layer.Least);
					const float Own = FMath::Lerp(Layer.Lo, Layer.Hi, FMath::Clamp(Used + Use.FRandRange(-0.2f, 0.2f), 0.0f, 1.0f));
					MID->SetScalarParameterValue(Layer.Name, Base * Own);
				}
				// (the shared mask lands somewhere else on each copy)
				MID->SetScalarParameterValue(TEXT("WearTiling"), MID->K2_GetScalarParameterValue(TEXT("WearTiling")) * Use.FRandRange(0.82f, 1.24f));
			}
			if (!bGlow && !bBody)
			{
				continue;
			}
			if (bGlow)
			{
				// the Sarketh's light is theirs whatever the copy's rarity (docs/orion/SARKETH_WEAPONS.md: the cells pale
				// amber; amber is how a player knows their fire)
				FLinearColor SlotGlow = Glow;
				if (SlotName.EndsWith(TEXT("__cell")))
				{
					SlotGlow = FLinearColor(1.0f, 0.55f, 0.18f);
				}
				else if (SlotName.EndsWith(TEXT("__amber")))
				{
					SlotGlow = FLinearColor(1.0f, 0.42f, 0.08f);
				}
				MID->SetVectorParameterValue(TEXT("BaseColorTint"), SlotGlow);
				MID->SetVectorParameterValue(TEXT("EmissiveColor"), SlotGlow);
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
		return bHasHold ? Hold.Support : (bHandgun ? HandgunSupportGrip() : SupportGrip(MeshToRig(Foregrip)));
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
	// a rotary gun: the barrel cluster about the bore
	Place(TEXT("spin"), FVector::ZeroVector, GltfEulerToMesh(0.0f, 0.0f, BarrelSpin));
	if (UStaticMeshComponent* Rounds = GetPart(TEXT("rounds")))
	{
		Rounds->SetVisibility(bShown && Pose.bRounds);
	}
	// horror: the hatch (flank flap about the barrel, brood lid about X) and the biomass
	const bool bBrood = Archetype == TEXT("brood") || Archetype == TEXT("vr_lmg"); // a lid hinged across the gun
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
		LeftGrip = GripForAnchor(NFore);
		LeftFingers = FingersForAnchor(NFore);
	}
}
