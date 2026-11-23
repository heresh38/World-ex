// The character builder (the owner, 2026-11-16: "the face will be heavily customizable in game when the player first
// starts"): its sliders are the bodies' own morph targets, its default tones are the bodies' own, the look is kept on
// the profile and on the outfit, a look alone never dresses the body again, and a new player meets the builder once.

#include "SOTestWorld.h"

#if WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR

#include "Engine/SkeletalMesh.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "SOCreator.h"
#include "SOCharacter.h"
#include "SOInventoryComponent.h"
#include "SOProfileStore.h"
#include "SOWardrobe.h"

namespace
{
	USOInventoryComponent* FreshInventory()
	{
		USOInventoryComponent* Inv = NewObject<USOInventoryComponent>();
		Inv->bPersist = false;
		Inv->NewProfile();
		return Inv;
	}

	bool HasKey(const USkeletalMesh* Mesh, FName Key)
	{
		return Mesh && Mesh->FindMorphTarget(FName(*(TEXT("face_") + Key.ToString()))) != nullptr;
	}

	/** The body's material instance by its imported name (MI_skin, MI_hair ...), under any dynamic instance. */
	UMaterialInterface* Source(UMaterialInterface* M)
	{
		const UMaterialInstanceDynamic* MID = Cast<UMaterialInstanceDynamic>(M);
		return MID && MID->Parent ? MID->Parent.Get() : M;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOCreatorKeysTest, "ShatteredOrbit.Creator.EveryKeyIsOnABody", SOTest::Flags)
bool FSOCreatorKeysTest::RunTest(const FString& Parameters)
{
	// every slider the builder offers moves a morph target of one of the bodies, the male body has all of its own (the
	// Orion head's 22: tools/blender/hero/orion/headcage.FACE_DELTA), and the first tone of each list is what the body
	// wears with nothing chosen (the import's tint: import_assets.SKIN_DAYLIGHT, HAIR_TONE)
	if (SOTest::PlayerBodyMissing(*this))
	{
		return true;
	}
	const FSOCreatorData& Data = FSOCreatorData::Get();
	TestTrue(TEXT("the builder's groups are data"), Data.Groups.Num() >= 8);
	TestTrue(TEXT("skin tones are data"), Data.SkinTones.Num() >= 6);
	TestTrue(TEXT("hair colours are data"), Data.HairColours.Num() >= 6);
	const USOWardrobeData* Male = USOWardrobeData::Get(TEXT("male"));
	const USOWardrobeData* Female = USOWardrobeData::Get(TEXT("female"));
	const USkeletalMesh* MaleMesh = Male ? Male->BodyMesh.LoadSynchronous() : nullptr;
	const USkeletalMesh* FemaleMesh = Female ? Female->BodyMesh.LoadSynchronous() : nullptr;
	if (!TestNotNull(TEXT("the male body"), MaleMesh))
	{
		return false;
	}
	for (const FName Key : Data.AllKeys())
	{
		TestTrue(FString::Printf(TEXT("the slider %s moves a body"), *Key.ToString()), HasKey(MaleMesh, Key) || HasKey(FemaleMesh, Key));
	}
	static const TCHAR* Orion[] = { TEXT("jaw"), TEXT("chin"), TEXT("cheekbones"), TEXT("cheeks"), TEXT("cheek_hollow"), TEXT("temples"), TEXT("brow"),
		TEXT("forehead"), TEXT("nose_width"), TEXT("nose_length"), TEXT("nose_tip"), TEXT("nasolabial"), TEXT("mouth_width"), TEXT("lips"), TEXT("eye_open"),
		TEXT("eye_size"), TEXT("crease"), TEXT("hood"), TEXT("tear_trough"), TEXT("eye_bags"), TEXT("ear_size"), TEXT("ear_out") };
	const TArray<FName> Offered = Data.AllKeys();
	for (const TCHAR* Key : Orion)
	{
		TestTrue(FString::Printf(TEXT("the male body has face_%s"), Key), HasKey(MaleMesh, Key));
		TestTrue(FString::Printf(TEXT("the builder offers %s"), Key), Offered.Contains(FName(Key)));
	}
	// the defaults are the bodies' own
	for (int32 i = 0; i < MaleMesh->GetMaterials().Num(); ++i)
	{
		UMaterialInterface* M = MaleMesh->GetMaterials()[i].MaterialInterface;
		const FString Name = M ? M->GetName() : FString();
		FLinearColor Tint;
		if (Name == TEXT("MI_skin") && M->GetVectorParameterValue(TEXT("BaseColorTint"), Tint))
		{
			TestTrue(FString::Printf(TEXT("the first skin tone is the body's own (%s against %s)"), *Data.SkinTones[0].Tint.ToString(), *Tint.ToString()),
				Data.SkinTones[0].Tint.Equals(FLinearColor(Tint.R, Tint.G, Tint.B, 1.0f), 0.01f));
		}
		if (Name == TEXT("MI_hair") && M->GetVectorParameterValue(TEXT("BaseColorTint"), Tint))
		{
			TestTrue(FString::Printf(TEXT("the first hair colour is the body's own (%s against %s)"), *Data.HairColours[0].Tint.ToString(), *Tint.ToString()),
				Data.HairColours[0].Tint.Equals(FLinearColor(Tint.R, Tint.G, Tint.B, 1.0f), 0.005f));
		}
	}
	// the hair is laid over a face's skin only where its map has a hair mask (the male's own face map): the female's
	// head wears the body's map, whose mask is white, and with HairAmount 1 her whole face took the brows' colour
	if (FemaleMesh)
	{
		for (const FSkeletalMaterial& Slot : FemaleMesh->GetMaterials())
		{
			float Hair = 0.0f;
			if (Slot.MaterialInterface && Slot.MaterialInterface->GetScalarParameterValue(TEXT("HairAmount"), Hair))
			{
				TestTrue(FString::Printf(TEXT("her %s takes no hair colour over its skin"), *Slot.MaterialSlotName.ToString()), Hair < 0.01f);
			}
		}
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOCreatorKeptTest, "ShatteredOrbit.Creator.TheLookIsKept", SOTest::Flags)
bool FSOCreatorKeptTest::RunTest(const FString& Parameters)
{
	// the face's sliders and both tones are the inventory's (the profile's), on the outfit the body wears; the whole
	// look set at once replaces them; a new player has not met the builder, a profile from before it has
	USOInventoryComponent* Inv = FreshInventory();
	TestFalse(TEXT("a new player has not made a character"), Inv->IsCharacterMade());
	Inv->SetFace(TEXT("jaw"), 0.6f);
	Inv->SetFace(TEXT("nose_tip"), -2.0f);
	Inv->SetSkinTone(FLinearColor(0.5f, 0.4f, 0.3f, 1.0f));
	Inv->SetHairTone(FLinearColor(0.2f, 0.1f, 0.05f, 1.0f));
	FSOOutfit Outfit = Inv->GetOutfit();
	TestEqual(TEXT("two sliders on the outfit"), Outfit.FaceKeys.Num(), 2);
	TestEqual(TEXT("a slider is kept"), Inv->GetFace(TEXT("jaw")), 0.6f);
	TestEqual(TEXT("a slider is held to -1..1"), Inv->GetFace(TEXT("nose_tip")), -1.0f);
	TestTrue(TEXT("the skin's tone is on the outfit"), Outfit.SkinTone.Equals(FLinearColor(0.5f, 0.4f, 0.3f, 1.0f)));
	TestTrue(TEXT("the hair's tone is on the outfit"), Outfit.HairTone.Equals(FLinearColor(0.2f, 0.1f, 0.05f, 1.0f)));
	FSOOutfit Other = Outfit;
	Other.SkinTone = FLinearColor(0.0f, 0.0f, 0.0f, 0.0f);
	TestFalse(TEXT("two outfits that differ in a tone are not the same"), Other == Outfit);
	Inv->SetFace(TEXT("jaw"), 0.0f);
	TestEqual(TEXT("a slider at the middle is gone"), Inv->GetOutfit().FaceKeys.Num(), 1);
	Inv->SetLook({ TEXT("lips"), TEXT("chin"), TEXT("lips") }, { 0.3f, 0.0f, 0.9f }, FLinearColor(0.0f, 0.0f, 0.0f, 0.0f), Inv->GetHairTone());
	Outfit = Inv->GetOutfit();
	TestEqual(TEXT("the whole look replaces the face (one key once, none at the middle)"), Outfit.FaceKeys.Num(), 1);
	TestEqual(TEXT("its value"), Inv->GetFace(TEXT("lips")), 0.3f);
	TestEqual(TEXT("the skin back to the body's own"), Outfit.SkinTone.A, 0.0f);
	TestEqual(TEXT("the hair kept"), Outfit.HairTone.A, 1.0f);
	Inv->SetCharacterMade();
	TestTrue(TEXT("met once"), Inv->IsCharacterMade());

	USOSaveGame* Old = NewObject<USOSaveGame>();
	Old->Version = 8;
	TestTrue(TEXT("migrated"), USOProfileStore::Migrate(Old));
	TestTrue(TEXT("a player from before the builder has made a character"), Old->bCharacterMade);
	TestEqual(TEXT("with the body's own tones"), Old->SkinTone.A, 0.0f);
	USOSaveGame* Current = NewObject<USOSaveGame>();
	Current->Version = USOSaveGame::CurrentVersion;
	TestTrue(TEXT("a current one"), USOProfileStore::Migrate(Current));
	TestFalse(TEXT("keeps its own word"), Current->bCharacterMade);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOCreatorBodyTest, "ShatteredOrbit.Creator.TheBodyWearsTheLook", SOTest::Flags)
bool FSOCreatorBodyTest::RunTest(const FString& Parameters)
{
	// the body takes a look on its morph targets and its skin's and hair's materials; a look alone never dresses the
	// body again (the builder's sliders move as they are dragged); a tone taken off puts the material back
	if (SOTest::PlayerBodyMissing(*this))
	{
		return true;
	}
	SOTest::FTestWorld W;
	W.AddBox(FVector(-500, -500, -20), FVector(500, 500, 0));
	ASOCharacter* Body = W.SpawnCharacter(FVector::ZeroVector);
	if (!TestNotNull(TEXT("a body"), Body))
	{
		return false;
	}
	USOInventoryComponent* Inv = FreshInventory();
	Body->SetOutfit(Inv->GetOutfit());
	W.Run(0.1f);
	const USkeletalMeshComponent* Suit = Body->GetWornPiece(TEXT("suit"));
	TestNotNull(TEXT("the undersuit is worn"), Suit);
	FSOOutfit Look = Inv->GetOutfit();
	Look.FaceKeys = { TEXT("jaw"), TEXT("ear_out") };
	Look.FaceValues = { 0.7f, -0.4f };
	Look.SkinTone = FLinearColor(0.44f, 0.31f, 0.23f, 1.0f);
	Look.HairTone = FLinearColor(0.18f, 0.12f, 0.065f, 1.0f);
	Body->SetOutfit(Look);
	TestTrue(TEXT("a look alone dresses nothing again"), Body->GetWornPiece(TEXT("suit")) == Suit);
	TestEqual(TEXT("the jaw's morph"), Body->GetMesh()->GetMorphTarget(TEXT("face_jaw")), 0.7f);
	TestEqual(TEXT("the ears' morph"), Body->GetMesh()->GetMorphTarget(TEXT("face_ear_out")), -0.4f);
	bool bSkin = false, bHair = false, bBrows = false;
	USkeletalMeshComponent* Mesh = Body->GetMesh();
	for (int32 i = 0; i < Mesh->GetNumMaterials(); ++i)
	{
		UMaterialInterface* M = Mesh->GetMaterial(i);
		const FString Name = Source(M) ? Source(M)->GetName() : FString();
		FLinearColor Tint;
		if (Name.StartsWith(TEXT("MI_skin")) && M->GetVectorParameterValue(TEXT("BaseColorTint"), Tint))
		{
			bSkin |= Tint.Equals(FLinearColor(0.44f, 0.31f, 0.23f, 1.0f), 1e-3f);
		}
		if (Name == TEXT("MI_skin_face") && M->GetVectorParameterValue(TEXT("HairColor"), Tint))
		{
			bBrows |= Tint.Equals(FLinearColor(0.18f * 1.6f, 0.12f * 1.6f, 0.065f * 1.6f, 1.0f), 1e-3f);
		}
		if (Name == TEXT("MI_hair") && M->GetVectorParameterValue(TEXT("BaseColorTint"), Tint))
		{
			bHair |= Tint.Equals(FLinearColor(0.18f, 0.12f, 0.065f, 1.0f), 1e-3f);
		}
	}
	// (the hair is a piece of the hair slot where the body has hairstyles to choose from)
	if (const USkeletalMeshComponent* Hair = Body->GetWornPiece(TEXT("hair")))
	{
		for (int32 i = 0; i < Hair->GetNumMaterials(); ++i)
		{
			UMaterialInterface* M = Hair->GetMaterial(i);
			FLinearColor Tint;
			if (Source(M) && Source(M)->GetName() == TEXT("MI_hair") && M->GetVectorParameterValue(TEXT("BaseColorTint"), Tint))
			{
				bHair |= Tint.Equals(FLinearColor(0.18f, 0.12f, 0.065f, 1.0f), 1e-3f);
			}
		}
	}
	TestTrue(TEXT("the skin takes its tone"), bSkin);
	TestTrue(TEXT("the brows follow the hair"), bBrows);
	TestTrue(TEXT("the hair takes its colour"), bHair);
	// back to the body's own
	Look.SkinTone = FLinearColor(0.0f, 0.0f, 0.0f, 0.0f);
	Body->SetOutfit(Look);
	for (int32 i = 0; i < Mesh->GetNumMaterials(); ++i)
	{
		UMaterialInterface* M = Mesh->GetMaterial(i);
		UMaterialInterface* From = Source(M);
		FLinearColor Now, Own;
		if (From && From->GetName() == TEXT("MI_skin") && M->GetVectorParameterValue(TEXT("BaseColorTint"), Now) && From->GetVectorParameterValue(TEXT("BaseColorTint"), Own))
		{
			TestTrue(TEXT("the skin back to its own tone"), Now.Equals(Own, 1e-3f));
		}
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOCreatorHairTest, "ShatteredOrbit.Creator.HairAndBeard", SOTest::Flags)
bool FSOCreatorHairTest::RunTest(const FString& Parameters)
{
	// the builder's hairstyles are the body's hair slot
	// and its beards a channel of the face's beard map; both are kept, both reach the body, the other body keeps its
	// own hair
	if (SOTest::PlayerBodyMissing(*this))
	{
		return true;
	}
	const USOWardrobeData* Male = USOWardrobeData::Get(TEXT("male"));
	if (!TestNotNull(TEXT("his wardrobe"), Male) || !Male->Find(TEXT("hair"), TEXT("crop")))
	{
		AddWarning(TEXT("the male's hairstyles are not imported yet"));
		return true;
	}
	TestTrue(TEXT("a slicked back style to choose"), Male->Find(TEXT("hair"), TEXT("slick")) != nullptr);
	TestEqual(TEXT("he starts with the swept style"), Male->Defaults.FindRef(TEXT("hair")), FName(TEXT("swept")));
	const FSOCreatorData& Data = FSOCreatorData::Get();
	TestTrue(TEXT("beards are data"), Data.Beards.Num() >= 4 && Data.BeardBodies.Contains(TEXT("male")));
	TestEqual(TEXT("the first beard is none"), Data.Beards.Num() > 0 ? Data.Beards[0].Id : NAME_None, FName(TEXT("none")));

	USOInventoryComponent* Inv = FreshInventory();
	TestEqual(TEXT("a new player: the default hair"), Inv->GetOutfit().Get(TEXT("hair")), FName(TEXT("swept")));
	TestTrue(TEXT("and clean-shaven"), Inv->GetOutfit().Beard.IsNone());
	Inv->SetHairStyle(TEXT("crop"));
	Inv->SetBeard(TEXT("short"));
	FSOOutfit Outfit = Inv->GetOutfit();
	TestEqual(TEXT("the crop on the outfit"), Outfit.Get(TEXT("hair")), FName(TEXT("crop")));
	TestEqual(TEXT("the beard on the outfit"), Outfit.Beard, FName(TEXT("short")));
	Inv->SetBeard(TEXT("none"));
	TestTrue(TEXT("none is clean-shaven"), Inv->GetBeard().IsNone());
	Inv->SetBeard(TEXT("full"));
	USOSaveGame* Old = NewObject<USOSaveGame>();
	Old->Version = 11;
	TestTrue(TEXT("a profile from before migrates"), USOProfileStore::Migrate(Old));
	TestTrue(TEXT("with the default hair and no beard"), Old->HairStyle.IsNone() && Old->Beard.IsNone());

	SOTest::FTestWorld W;
	W.AddBox(FVector(-500, -500, -20), FVector(500, 500, 0));
	ASOCharacter* Body = W.SpawnCharacter(FVector::ZeroVector);
	if (!TestNotNull(TEXT("a body"), Body))
	{
		return false;
	}
	Body->SetOutfit(Inv->GetOutfit());
	W.Run(0.1f);
	const USkeletalMeshComponent* Hair = Body->GetWornPiece(TEXT("hair"));
	TestTrue(TEXT("the crop is worn"), Hair && Hair->GetSkeletalMeshAsset() && Hair->GetSkeletalMeshAsset()->GetName().Contains(TEXT("hair_crop")));
	FLinearColor Mask = FLinearColor::Black;
	bool bFace = false;
	for (int32 i = 0; i < Body->GetMesh()->GetNumMaterials(); ++i)
	{
		UMaterialInterface* M = Body->GetMesh()->GetMaterial(i);
		if (Source(M) && Source(M)->GetName() == TEXT("MI_skin_face") && M->GetVectorParameterValue(TEXT("BeardMask"), Mask))
		{
			bFace = true;
			break;
		}
	}
	TestTrue(TEXT("the face takes the full beard (its map's blue)"), bFace && Mask.Equals(ASOCharacter::BeardMask(TEXT("full")), 1e-3f) && Mask.B > 0.5f);
	Inv->SetHairStyle(TEXT("slick"));
	Body->SetOutfit(Inv->GetOutfit());
	W.Run(0.1f);
	const USkeletalMeshComponent* Slick = Body->GetWornPiece(TEXT("hair"));
	TestTrue(TEXT("the style changes what is worn"), Slick && Slick->GetSkeletalMeshAsset() && Slick->GetSkeletalMeshAsset()->GetName().Contains(TEXT("hair_slick")));
	// the face's sliders reach the hair (its roots ride the forehead)
	Inv->SetHairStyle(TEXT("swept"));
	FSOOutfit Look = Inv->GetOutfit();
	Look.FaceKeys = { TEXT("forehead") };
	Look.FaceValues = { 0.8f };
	Body->SetOutfit(Look);
	W.Run(0.1f);
	if (const USkeletalMeshComponent* Swept = Body->GetWornPiece(TEXT("hair")))
	{
		if (Swept->GetSkeletalMeshAsset() && Swept->GetSkeletalMeshAsset()->FindMorphTarget(TEXT("face_forehead")))
		{
			TestEqual(TEXT("the hair rides the forehead's slider"), Swept->GetMorphTarget(TEXT("face_forehead")), 0.8f);
		}
	}
	return true;
}

#endif
