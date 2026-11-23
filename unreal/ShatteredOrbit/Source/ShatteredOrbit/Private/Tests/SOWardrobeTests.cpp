// The modular player: the body wears one skeletal mesh per slot (following its pose), covered skin is hidden, the
// first-person arms wear the arm pieces, armour lives in the inventory and the body can be switched.

#include "SOTestWorld.h"

#if WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR

#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "SOInventoryComponent.h"
#include "SOLocomotionAnimInstance.h"
#include "SOWardrobe.h"

namespace
{
	/** The male body (the Orion body, 2026-11-17) wears only the undersuit until his new armour is made (the owner:
	 *  "we will be either removing or updating all the user armor"): the checks that need his armour wait for it. */
	bool ClothingMissing(FAutomationTestBase& Test)
	{
		const USOWardrobeData* Male = USOWardrobeData::Get(TEXT("male"));
		if (Male && Male->Items.ContainsByPredicate([](const FSOWardrobeItem& I) { return I.bArmour; }))
		{
			return false;
		}
		Test.AddWarning(TEXT("no armour for the male body yet (only the undersuit; the armour is being remade): skipped"));
		return true;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOWardrobeDressesTest, "ShatteredOrbit.Wardrobe.Dresses", SOTest::Flags)
bool FSOWardrobeDressesTest::RunTest(const FString& Parameters)
{
	if (SOTest::PlayerBodyMissing(*this))
	{
		return true;
	}
	const USOWardrobeData* Male = USOWardrobeData::Get(TEXT("male"));
	const USOWardrobeData* Female = USOWardrobeData::Get(TEXT("female"));
	if (!TestNotNull(TEXT("male wardrobe (run export_unreal.sh + import_assets.py)"), Male) || !TestNotNull(TEXT("female wardrobe"), Female))
	{
		return false;
	}
	for (const USOWardrobeData* W : { Male, Female })
	{
		const USkeletalMesh* BodyMesh = W->BodyMesh.LoadSynchronous();
		TestNotNull(*FString::Printf(TEXT("%s body mesh"), *W->Body.ToString()), BodyMesh);
		if (BodyMesh)
		{
			// one skin section per region, so worn pieces can hide what they cover
			for (const TCHAR* Region : { TEXT("head"), TEXT("neck"), TEXT("chest"), TEXT("midriff"), TEXT("pelvis"), TEXT("upperarm"),
				TEXT("forearm"), TEXT("hand"), TEXT("thigh"), TEXT("shin"), TEXT("foot") })
			{
				const FName Slot(*FString::Printf(TEXT("skin__%s"), Region));
				TestTrue(*FString::Printf(TEXT("%s has the %s section"), *W->Body.ToString(), *Slot.ToString()),
					BodyMesh->GetMaterials().ContainsByPredicate([&](const FSkeletalMaterial& M) { return M.MaterialSlotName == Slot; }));
			}
		}
	}
	// the male (the Orion body): the undersuit, always worn, never armour (the owner, 2026-11-17: "the undersuit is on
	// at all times and armor goes on top of that"); it hides the skin it covers
	const FSOWardrobeItem* Suit = Male->Find(TEXT("suit"), TEXT("orion"));
	if (!TestNotNull(TEXT("male undersuit (slot suit, item orion)"), Suit))
	{
		return false;
	}
	TestNotNull(TEXT("undersuit mesh"), Suit->Mesh.LoadSynchronous());
	TestFalse(TEXT("the undersuit is not armour"), Suit->bArmour);
	TestFalse(TEXT("the undersuit's slot is not an armour slot"), USOWardrobeData::ArmourSlots().Contains(TEXT("suit")));
	TestEqual(TEXT("the undersuit is worn by default"), Male->Defaults.FindRef(TEXT("suit")), FName(TEXT("orion")));
	TestTrue(TEXT("the undersuit hides the chest"), Suit->Hide.Contains(TEXT("chest")));
	TestFalse(TEXT("the undersuit leaves the face"), Suit->Hide.Contains(TEXT("head")));

	SOTest::FTestWorld World;
	World.AddBox(FVector(-2000, -2000, -100), FVector(2000, 2000, 0));
	ASOCharacter* Player = World.SpawnCharacter(FVector::ZeroVector);
	if (!TestNotNull(TEXT("player"), Player))
	{
		return false;
	}
	World.Run(0.2f);
	TestTrue(TEXT("male body"), Player->GetMesh()->GetSkeletalMeshAsset() == Male->BodyMesh.LoadSynchronous());
	USkeletalMeshComponent* Worn = Player->GetWornPiece(TEXT("suit"));
	if (TestNotNull(TEXT("the undersuit is worn"), Worn))
	{
		TestTrue(TEXT("it follows the body's pose"), Worn->LeaderPoseComponent.Get() == Player->GetMesh());
		TestTrue(TEXT("it shares the skeleton"), Worn->GetSkeletalMeshAsset() &&
			Worn->GetSkeletalMeshAsset()->GetSkeleton() == Player->GetMesh()->GetSkeletalMeshAsset()->GetSkeleton());
	}
	TestTrue(TEXT("the undersuit hides the chest skin"), Player->GetHiddenRegions().Contains(TEXT("chest")));
	TestFalse(TEXT("the face shows"), Player->GetHiddenRegions().Contains(TEXT("head")));
	auto SectionShown = [&](const TCHAR* SlotName) -> int32
	{
		USkeletalMeshComponent* Body = Player->GetMesh();
		const TArray<FSkeletalMaterial>& Mats = Body->GetSkeletalMeshAsset()->GetMaterials();
		for (int32 i = 0; i < Mats.Num(); ++i)
		{
			if (Mats[i].MaterialSlotName == FName(SlotName))
			{
				return Body->IsMaterialSectionShown(i, 0) ? 1 : 0;
			}
		}
		return -1; // no such slot
	};
	TestEqual(TEXT("head skin shows"), SectionShown(TEXT("skin__head")), 1);
	TestEqual(TEXT("chest skin hidden"), SectionShown(TEXT("skin__chest")), 0);
	TestEqual(TEXT("hand skin shows"), SectionShown(TEXT("skin__hand")), 1);

	// the female body swaps the meshes and the clips, wears her outfit; back to the male, his head shows again
	// (section visibility must not leak between bodies) and the undersuit is back on
	FSOOutfit Outfit = Player->GetOutfit();
	Outfit.Body = TEXT("female");
	for (const TPair<FName, FName>& D : Female->Defaults)
	{
		Outfit.Set(D.Key, D.Value);
	}
	Player->SetOutfit(Outfit);
	World.Run(0.1f);
	TestTrue(TEXT("female body"), Player->GetMesh()->GetSkeletalMeshAsset() == Female->BodyMesh.LoadSynchronous());
	TestNull(TEXT("no male undersuit on the female body"), Player->GetWornPiece(TEXT("suit")));
	TestEqual(TEXT("female head skin shows"), SectionShown(TEXT("skin__head")), 1);
	Outfit.Body = TEXT("male");
	for (const TPair<FName, FName>& D : Male->Defaults)
	{
		Outfit.Set(D.Key, D.Value);
	}
	Player->SetOutfit(Outfit);
	World.Run(0.1f);
	TestEqual(TEXT("male head skin shows after the female body"), SectionShown(TEXT("skin__head")), 1);
	TestNotNull(TEXT("the undersuit is back on"), Player->GetWornPiece(TEXT("suit")));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOArmorInventoryTest, "ShatteredOrbit.Wardrobe.ArmorInventory", SOTest::Flags)
bool FSOArmorInventoryTest::RunTest(const FString& Parameters)
{
	if (SOTest::PlayerBodyMissing(*this))
	{
		return true;
	}
	// every armour slot may be empty (the owner, 2026-11-17: "the rest of the armor slots can be empty for now")
	for (const FName Slot : USOWardrobeData::ArmourSlots())
	{
		TestTrue(*FString::Printf(TEXT("%s may be empty"), *Slot.ToString()), USOWardrobeData::IsOptionalSlot(Slot));
	}
	USOInventoryComponent* Inventory = NewObject<USOInventoryComponent>();
	Inventory->bPersist = false;
	Inventory->NewProfile();
	FSOOutfit Outfit = Inventory->GetOutfit();
	TestEqual(TEXT("the male wears the undersuit"), Outfit.Get(TEXT("suit")), FName(TEXT("orion")));
	// an old save: the previous outfits' pieces (worn) are gone, nothing is forced into an emptied slot
	{
		TArray<FSOArmorInstance> Old;
		for (const TCHAR* Slot : { TEXT("top"), TEXT("outer"), TEXT("feet") })
		{
			FSOArmorInstance& A = Old.AddDefaulted_GetRef();
			A.Uid = FString::Printf(TEXT("old-%s"), Slot);
			A.Slot = Slot;
			A.Item = TEXT("old_outfit_piece");
			A.bEquipped = true;
		}
		USOInventoryComponent* Loaded = NewObject<USOInventoryComponent>();
		Loaded->bPersist = false;
		Loaded->NewProfile();
		Loaded->RestoreArmor(Old);
		TestFalse(TEXT("old pieces are deleted"), Loaded->GetArmor().ContainsByPredicate([](const FSOArmorInstance& A) { return A.Item == TEXT("old_outfit_piece"); }));
		TestEqual(TEXT("the undersuit stays on"), Loaded->GetOutfit().Get(TEXT("suit")), FName(TEXT("orion")));
	}
	// the female body: her pieces are owned and worn, and any of them comes off (every slot may be empty)
	TestTrue(TEXT("switch body"), Inventory->SetBody(TEXT("female")));
	TestEqual(TEXT("female"), Inventory->GetBody(), FName(TEXT("female")));
	const FSOArmorInstance* Top = Inventory->GetEquippedArmor(TEXT("top"));
	if (TestTrue(TEXT("female top worn"), Top && USOWardrobeData::Get(TEXT("female"))->Find(Top->Slot, Top->Item) != nullptr))
	{
		const FString Uid = Top->Uid;
		TestTrue(TEXT("the top comes off"), Inventory->EquipArmor(Uid));
		TestNull(TEXT("nothing worn on top"), Inventory->GetEquippedArmor(TEXT("top")));
		TestEqual(TEXT("outfit without a top"), Inventory->GetOutfit().Get(TEXT("top")), FName(TEXT("none")));
		TestTrue(TEXT("and goes back on"), Inventory->EquipArmor(Uid));
	}
	TestTrue(TEXT("armour rating with her pieces"), Inventory->GetArmorRating() > 0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOBodyClipsTest, "ShatteredOrbit.Anim.OwnClipsPerBody", SOTest::Flags)
bool FSOBodyClipsTest::RunTest(const FString& Parameters)
{
	if (SOTest::PlayerBodyMissing(*this))
	{
		return true;
	}
	SOTest::FTestWorld World;
	World.AddBox(FVector(-2000, -2000, -100), FVector(2000, 2000, 0));
	ASOCharacter* Player = World.SpawnCharacter(FVector::ZeroVector);
	if (!TestNotNull(TEXT("player"), Player))
	{
		return false;
	}
	Player->GetMesh()->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
	World.Run(0.2f);
	TMap<FName, TArray<const UAnimSequenceBase*>> Seen;
	for (const FName Body : { FName(TEXT("male")), FName(TEXT("female")) })
	{
		FSOOutfit Outfit = Player->GetOutfit();
		Outfit.Body = Body;
		Player->SetOutfit(Outfit);
		World.Run(0.1f);
		USOLocomotionAnimInstance* Anim = Cast<USOLocomotionAnimInstance>(Player->GetMesh()->GetAnimInstance());
		if (!TestNotNull(TEXT("locomotion anim"), Anim))
		{
			return false;
		}
		const FSOLocomotionClips& C = Anim->Clips;
		const FString Folder = Body == TEXT("male") ? TEXT("/Game/Characters/PlayerMale/") : TEXT("/Game/Characters/PlayerFemale/");
		TArray<const UAnimSequenceBase*>& Mine = Seen.Add(Body);
		for (const UAnimSequenceBase* Clip : { C.Idle.Get(), C.Walk.Get(), C.Run.Get(), C.Jump.Get(), C.Slide.Get(), C.Death.Get() })
		{
			if (TestNotNull(FString::Printf(TEXT("%s clip"), *Body.ToString()), Clip))
			{
				TestTrue(FString::Printf(TEXT("%s plays its own %s"), *Body.ToString(), *Clip->GetName()), Clip->GetPathName().StartsWith(Folder));
				Mine.Add(Clip);
			}
		}
		TestEqual(FString::Printf(TEXT("%s has three idle variations"), *Body.ToString()), C.Fidgets.Num(), 3);
		for (const UAnimSequenceBase* F : C.Fidgets)
		{
			TestTrue(TEXT("idle variation from its own folder"), F && F->GetPathName().StartsWith(Folder));
		}
		// an idle variation plays while standing, and moving ends it
		Anim->FidgetDelay = FVector2D(0.3f, 0.3f);
		Anim->ResetFidgetTimer();
		float Peak = 0.0f;
		World.Run(1.5f, [&]() { Peak = FMath::Max(Peak, Anim->Weights[7]); });
		TestTrue(FString::Printf(TEXT("%s: an idle variation plays (weight %.2f)"), *Body.ToString(), Peak), Peak > 0.9f);
	}
	for (const UAnimSequenceBase* Clip : Seen.FindRef(TEXT("male")))
	{
		TestFalse(TEXT("no clip is shared between the bodies"), Seen.FindRef(TEXT("female")).Contains(Clip));
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOHeadGearTest, "ShatteredOrbit.Wardrobe.HeadGear", SOTest::Flags)
bool FSOHeadGearTest::RunTest(const FString& Parameters)
{
	if (SOTest::PlayerBodyMissing(*this) || ClothingMissing(*this))
	{
		return true;
	}
	SOTest::FTestWorld World;
	World.AddBox(FVector(-2000, -2000, -100), FVector(2000, 2000, 0));
	ASOCharacter* Player = World.SpawnCharacter(FVector::ZeroVector);
	if (!TestNotNull(TEXT("player"), Player))
	{
		return false;
	}
	World.Run(0.2f);
	for (const FName Body : { FName(TEXT("male")), FName(TEXT("female")) })
	{
		const USOWardrobeData* W = USOWardrobeData::Get(Body);
		if (!TestNotNull(TEXT("wardrobe"), W))
		{
			continue;
		}
		const FSOWardrobeItem* Helmet = W->Find(TEXT("head"), TEXT("orion_helmet"));
		TestTrue(TEXT("nothing on the head by default"), W->Defaults.FindRef(TEXT("head")).IsNone());
		if (!Helmet)
		{
			// (the male's helmet and headset were deleted at the owner's word, 2026-11-22: his head gear comes back with his
			// armour, built to the owner's own image; until then only her head gear is checked)
			AddInfo(FString::Printf(TEXT("%s: no head gear yet"), *Body.ToString()));
			continue;
		}
		TestNotNull(FString::Printf(TEXT("%s owns a headset"), *Body.ToString()), W->Find(TEXT("head"), TEXT("orion_headset")));
		TestTrue(TEXT("the sealed helmet hides the hair"), Helmet->bHideHair);
		TestTrue(TEXT("and the head"), Helmet->Hide.Contains(TEXT("head")) && Helmet->Hide.Contains(TEXT("neck")));
		FSOOutfit Outfit = Player->GetOutfit();
		Outfit.Body = Body;
		Outfit.Set(TEXT("head"), TEXT("orion_helmet"));
		Player->SetOutfit(Outfit);
		World.Run(0.1f);
		TestNotNull(FString::Printf(TEXT("%s: helmet worn"), *Body.ToString()), Player->GetWornPiece(TEXT("head")));
		TestNull(FString::Printf(TEXT("%s: bald under the helmet"), *Body.ToString()), Player->GetWornPiece(TEXT("hair")));
		Outfit.Set(TEXT("head"), TEXT("orion_headset"));
		Player->SetOutfit(Outfit);
		World.Run(0.1f);
		TestNotNull(FString::Printf(TEXT("%s: the hair is back with the headset"), *Body.ToString()), Player->GetWornPiece(TEXT("hair")));
		Outfit.Set(TEXT("head"), TEXT("none"));
		Player->SetOutfit(Outfit);
		World.Run(0.1f);
		TestNull(TEXT("bare head"), Player->GetWornPiece(TEXT("head")));
		TestNotNull(TEXT("hair without the helmet"), Player->GetWornPiece(TEXT("hair")));
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOWornPerBodyTest, "ShatteredOrbit.Wardrobe.WornPerBody", SOTest::Flags)
bool FSOWornPerBodyTest::RunTest(const FString& Parameters)
{
	// What is worn is each body's own (the owner, 2026-11-13: a helmet put on her was on him after the switch, and
	// taking it off him took it off her).
	if (SOTest::PlayerBodyMissing(*this) || ClothingMissing(*this))
	{
		return true;
	}
	USOInventoryComponent* Inv = NewObject<USOInventoryComponent>();
	Inv->bPersist = false;
	Inv->NewProfile();
	auto Worn = [Inv](FName Slot) { const FSOArmorInstance* A = Inv->GetEquippedArmor(Slot); return A ? A->Item : FName(TEXT("none")); };
	auto Piece = [Inv](FName Slot, FName Item) { const FSOArmorInstance* A = Inv->GetArmor().FindByPredicate([&](const FSOArmorInstance& X) { return X.Slot == Slot && X.Item == Item; }); return A ? A->Uid : FString(); };
	TestEqual(TEXT("he starts bare-headed"), Worn(TEXT("head")), FName(TEXT("none")));
	TestEqual(TEXT("he starts in his coat"), Worn(TEXT("outer")), FName(TEXT("orion")));

	TestTrue(TEXT("to her"), Inv->SetBody(TEXT("female")));
	TestEqual(TEXT("the first time she wears her wardrobe's own: bare-headed"), Worn(TEXT("head")), FName(TEXT("none")));
	TestEqual(TEXT("and her jacket"), Worn(TEXT("outer")), FName(TEXT("orion")));
	const FString Helmet = Piece(TEXT("head"), TEXT("orion_helmet"));
	if (!TestFalse(TEXT("she owns the helmet"), Helmet.IsEmpty()))
	{
		return false;
	}
	TestTrue(TEXT("she puts the helmet on"), Inv->EquipArmor(Helmet));
	TestTrue(TEXT("and takes her jacket off"), Inv->EquipArmor(Piece(TEXT("outer"), TEXT("orion"))));
	TestEqual(TEXT("helmet on her"), Worn(TEXT("head")), FName(TEXT("orion_helmet")));

	TestTrue(TEXT("back to him"), Inv->SetBody(TEXT("male")));
	TestEqual(TEXT("her helmet is not on him"), Worn(TEXT("head")), FName(TEXT("none")));
	TestEqual(TEXT("and he still has his coat on"), Worn(TEXT("outer")), FName(TEXT("orion")));
	// (his head gear was deleted at the owner's word, 2026-11-22: a piece of his own that he takes off stands in, so a
	// switch is still seen to leave each body's pieces where they are)
	const FString Gloves = Piece(TEXT("hands"), TEXT("orion"));
	if (TestFalse(TEXT("he owns his gloves"), Gloves.IsEmpty()))
	{
		TestTrue(TEXT("he takes his gloves off"), Inv->EquipArmor(Gloves));
		TestEqual(TEXT("his gloves off"), Worn(TEXT("hands")), FName(TEXT("none")));
	}

	TestTrue(TEXT("to her again"), Inv->SetBody(TEXT("female")));
	TestEqual(TEXT("she still has her helmet on"), Worn(TEXT("head")), FName(TEXT("orion_helmet")));
	TestEqual(TEXT("and her jacket still off"), Worn(TEXT("outer")), FName(TEXT("none")));
	TestTrue(TEXT("she takes the helmet off"), Inv->EquipArmor(Helmet));

	TestTrue(TEXT("to him again"), Inv->SetBody(TEXT("male")));
	TestEqual(TEXT("his gloves are still off: her taking the helmet off did nothing to him"), Worn(TEXT("hands")), FName(TEXT("none")));
	TestEqual(TEXT("and he is still bare-headed"), Worn(TEXT("head")), FName(TEXT("none")));
	for (const FName Slot : { FName(TEXT("top")), FName(TEXT("legs")), FName(TEXT("feet")) })
	{
		TestTrue(*FString::Printf(TEXT("a required slot (%s) is never left empty by a switch"), *Slot.ToString()), Worn(Slot) != FName(TEXT("none")));
	}
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
