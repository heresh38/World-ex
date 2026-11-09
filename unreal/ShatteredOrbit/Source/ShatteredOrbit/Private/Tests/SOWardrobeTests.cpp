// The modular player: the body wears one skeletal mesh per slot (following its pose), covered skin is hidden, the
// first-person arms wear the arm pieces, armour lives in the inventory and the body can be switched.

#include "SOTestWorld.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "SOInventoryComponent.h"
#include "SOWardrobe.h"

namespace
{
	/** The bodies are back (hero base meshes) but their clothing comes later: the outfit checks wait for it. */
	bool ClothingMissing(FAutomationTestBase& Test)
	{
		const USOWardrobeData* Male = USOWardrobeData::Get(TEXT("male"));
		if (Male && Male->Items.Num() > 0)
		{
			return false;
		}
		Test.AddWarning(TEXT("no clothing imported yet (the bodies are new; pieces come later): outfit checks skipped"));
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
		TestNotNull(*FString::Printf(TEXT("%s first-person arms"), *W->Body.ToString()), W->ArmsMesh.LoadSynchronous());
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
	if (ClothingMissing(*this))
	{
		// what can be checked without clothing: the player spawns as the male body and switches to the female one
		SOTest::FTestWorld World;
		World.AddBox(FVector(-2000, -2000, -100), FVector(2000, 2000, 0));
		ASOCharacter* Player = World.SpawnCharacter(FVector::ZeroVector);
		if (!TestNotNull(TEXT("player"), Player))
		{
			return false;
		}
		World.Run(0.2f);
		TestTrue(TEXT("male body"), Player->GetMesh()->GetSkeletalMeshAsset() == Male->BodyMesh.LoadSynchronous());
		FSOOutfit Outfit = Player->GetOutfit();
		Outfit.Body = TEXT("female");
		Player->SetOutfit(Outfit);
		World.Run(0.1f);
		TestTrue(TEXT("female body"), Player->GetMesh()->GetSkeletalMeshAsset() == Female->BodyMesh.LoadSynchronous());
		TestTrue(TEXT("female arms"), Player->GetFirstPersonArms()->GetSkeletalMeshAsset() == Female->ArmsMesh.LoadSynchronous());
		return true;
	}
	for (const USOWardrobeData* W : { Male, Female })
	{
		for (const FName Slot : { FName(TEXT("top")), FName(TEXT("outer")), FName(TEXT("hands")), FName(TEXT("legs")), FName(TEXT("feet")) })
		{
			const FSOWardrobeItem* Orion = W->Find(Slot, TEXT("orion"));
			if (TestNotNull(*FString::Printf(TEXT("%s orion %s"), *W->Body.ToString(), *Slot.ToString()), Orion))
			{
				TestNotNull(TEXT("piece mesh"), Orion->Mesh.LoadSynchronous());
				TestTrue(TEXT("piece is armour with a rating"), Orion->bArmour && Orion->Armor > 0);
				TestNotNull(TEXT("piece icon"), Orion->Icon.LoadSynchronous());
				TestEqual(TEXT("the orion set is worn by default"), W->Defaults.FindRef(Slot), FName(TEXT("orion")));
			}
		}
		const FSOWardrobeItem* Armoured = W->Find(TEXT("hands"), TEXT("orion_armoured"));
		if (TestNotNull(*FString::Printf(TEXT("%s armoured gloves (fingers covered)"), *W->Body.ToString()), Armoured))
		{
			TestTrue(TEXT("armoured gloves hide the bare hands"), Armoured->Hide.Contains(TEXT("hand")));
			TestTrue(TEXT("armoured gloves are armour"), Armoured->bArmour && Armoured->Armor > 0 && !Armoured->ArmsMesh.IsNull());
		}
		const FSOWardrobeItem* Gloves = W->Find(TEXT("hands"), TEXT("orion"));
		TestTrue(TEXT("gloves have a first-person cut"), Gloves && !Gloves->ArmsMesh.IsNull());
		const FSOWardrobeItem* Boots = W->Find(TEXT("feet"), TEXT("orion"));
		TestTrue(TEXT("boots have no first-person cut"), Boots && Boots->ArmsMesh.IsNull());
	}

	SOTest::FTestWorld World;
	World.AddBox(FVector(-2000, -2000, -100), FVector(2000, 2000, 0));
	ASOCharacter* Player = World.SpawnCharacter(FVector::ZeroVector);
	if (!TestNotNull(TEXT("player"), Player))
	{
		return false;
	}
	World.Run(0.2f);
	// dressed in the defaults
	for (const FName Slot : { FName(TEXT("hair")), FName(TEXT("top")), FName(TEXT("outer")), FName(TEXT("hands")), FName(TEXT("legs")), FName(TEXT("feet")) })
	{
		USkeletalMeshComponent* Piece = Player->GetWornPiece(Slot, false);
		if (TestNotNull(*FString::Printf(TEXT("worn %s"), *Slot.ToString()), Piece))
		{
			TestTrue(TEXT("piece follows the body's pose"), Piece->LeaderPoseComponent.Get() == Player->GetMesh());
			TestTrue(TEXT("piece shares the skeleton"), Piece->GetSkeletalMeshAsset() &&
				Piece->GetSkeletalMeshAsset()->GetSkeleton() == Player->GetMesh()->GetSkeletalMeshAsset()->GetSkeleton());
		}
	}
	TestNotNull(TEXT("first-person gloves"), Player->GetWornPiece(TEXT("hands"), true));
	TestNull(TEXT("no first-person boots"), Player->GetWornPiece(TEXT("feet"), true));
	TestTrue(TEXT("the jacket hides the chest skin"), Player->GetHiddenRegions().Contains(TEXT("chest")));
	TestTrue(TEXT("boots hide the feet"), Player->GetHiddenRegions().Contains(TEXT("foot")));
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
	{
		FString Slots;
		for (const FSkeletalMaterial& M : Player->GetMesh()->GetSkeletalMeshAsset()->GetMaterials())
		{
			Slots += M.MaterialSlotName.ToString() + TEXT(" ");
		}
		AddInfo(FString::Printf(TEXT("male body slots: %s"), *Slots));
	}
	TestEqual(TEXT("head skin shows"), SectionShown(TEXT("skin__head")), 1);
	TestEqual(TEXT("chest skin hidden"), SectionShown(TEXT("skin__chest")), 0);

	// a different outfit: taking the coat off removes its piece; the female body swaps the meshes and the clips
	FSOOutfit Outfit = Player->GetOutfit();
	Outfit.Set(TEXT("outer"), TEXT("none"));
	Player->SetOutfit(Outfit);
	TestNull(TEXT("coat off"), Player->GetWornPiece(TEXT("outer"), false));
	Outfit.Body = TEXT("female");
	for (const TPair<FName, FName>& D : Female->Defaults)
	{
		Outfit.Set(D.Key, D.Value);
	}
	Player->SetOutfit(Outfit);
	World.Run(0.1f);
	TestTrue(TEXT("female body"), Player->GetMesh()->GetSkeletalMeshAsset() == Female->BodyMesh.LoadSynchronous());
	TestTrue(TEXT("female arms"), Player->GetFirstPersonArms()->GetSkeletalMeshAsset() == Female->ArmsMesh.LoadSynchronous());
	TestNotNull(TEXT("female jacket"), Player->GetWornPiece(TEXT("outer"), false));
	TestFalse(TEXT("the cropped top leaves the midriff"), Player->GetHiddenRegions().Contains(TEXT("midriff")));
	TestEqual(TEXT("female head skin shows"), SectionShown(TEXT("skin__head")), 1);
	TestEqual(TEXT("female midriff shows"), SectionShown(TEXT("skin__midriff")), 1);
	// and back: the male head must show again (section visibility must not leak between bodies)
	Outfit.Body = TEXT("male");
	for (const TPair<FName, FName>& D : Male->Defaults)
	{
		Outfit.Set(D.Key, D.Value);
	}
	Player->SetOutfit(Outfit);
	World.Run(0.1f);
	TestEqual(TEXT("male head skin shows after the female body"), SectionShown(TEXT("skin__head")), 1);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOArmorInventoryTest, "ShatteredOrbit.Wardrobe.ArmorInventory", SOTest::Flags)
bool FSOArmorInventoryTest::RunTest(const FString& Parameters)
{
	if (SOTest::PlayerBodyMissing(*this) || ClothingMissing(*this))
	{
		return true;
	}
	USOInventoryComponent* Inventory = NewObject<USOInventoryComponent>();
	Inventory->bPersist = false;
	Inventory->NewProfile();
	TestTrue(TEXT("a new profile owns armour (the Orion set: top, vest, coat, two gloves, trousers, boots)"),
		Inventory->GetArmor().Num() >= 7);
	const FSOArmorInstance* Coat = Inventory->GetEquippedArmor(TEXT("outer"));
	if (!TestNotNull(TEXT("the coat is worn"), Coat))
	{
		return false;
	}
	TestEqual(TEXT("the orion coat"), Coat->Item, FName(TEXT("orion")));
	const int32 Rating = Inventory->GetArmorRating();
	TestTrue(TEXT("armour rating"), Rating > 0);
	FSOOutfit Outfit = Inventory->GetOutfit();
	TestEqual(TEXT("outfit wears the coat"), Outfit.Get(TEXT("outer")), FName(TEXT("orion")));
	TestNotEqual(TEXT("outfit keeps the hair"), Outfit.Get(TEXT("hair")), FName(TEXT("none")));
	// wearing the other gloves swaps them; a required slot can't be emptied (no undressing)
	const FSOArmorInstance* Other = Inventory->GetArmor().FindByPredicate([](const FSOArmorInstance& A) { return A.Slot == TEXT("hands") && A.Item != TEXT("orion"); });
	if (TestNotNull(TEXT("the armoured gloves are owned"), Other))
	{
		const FString Uid = Other->Uid;
		Inventory->EquipArmor(Uid);
		TestEqual(TEXT("one pair of gloves at a time"), Inventory->GetEquippedArmor(TEXT("hands"))->Uid, Uid);
		TestFalse(TEXT("the worn gloves can't be taken off"), Inventory->EquipArmor(Uid));
		TestNotNull(TEXT("still wearing gloves"), Inventory->GetEquippedArmor(TEXT("hands")));
	}
	// the outer layer is optional: it comes off
	if (const FSOArmorInstance* Worn = Inventory->GetEquippedArmor(TEXT("outer")))
	{
		const FString Uid = Worn->Uid;
		TestTrue(TEXT("the coat comes off"), Inventory->EquipArmor(Uid));
		TestEqual(TEXT("outfit without a coat"), Inventory->GetOutfit().Get(TEXT("outer")), FName(TEXT("none")));
		Inventory->EquipArmor(Uid);
	}
	// an old save: the previous outfit's pieces (worn) are gone and the new ones go on, the coat included
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
		const FSOOutfit Fresh = Loaded->GetOutfit();
		for (const FName Slot : USOWardrobeData::ArmourSlots())
		{
			const FName Default = USOWardrobeData::Get(TEXT("male"))->Defaults.FindRef(Slot);
			if (!Default.IsNone() && Slot != TEXT("head"))
			{
				TestEqual(FString::Printf(TEXT("old save spawns in the new %s"), *Slot.ToString()), Fresh.Get(Slot), Default);
			}
		}
	}
	// the female body: her pieces are owned too and her defaults fill the slots
	TestTrue(TEXT("switch body"), Inventory->SetBody(TEXT("female")));
	TestEqual(TEXT("female"), Inventory->GetBody(), FName(TEXT("female")));
	const FSOArmorInstance* Top = Inventory->GetEquippedArmor(TEXT("top"));
	TestTrue(TEXT("female top worn"), Top && USOWardrobeData::Get(TEXT("female"))->Find(Top->Slot, Top->Item) != nullptr);
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
