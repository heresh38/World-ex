// The armoury's organisation and the collected items (the owner's armoury reference, 2026-11-20: "how to better
// organize weapons and other things we need like an inventory to hold items we collect"): every gun's family and
// origin, the goods as data, holding them, raising with them, dismantling for them, what kills and caches pay, the
// consumables, and a save from before them.

#include "SOTestWorld.h"

#if WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR

#include "GameFramework/PlayerController.h"
#include "SOCombatStatics.h"
#include "SOEnemy.h"
#include "SOInventoryComponent.h"
#include "SOLootActors.h"
#include "SOLootLibrary.h"
#include "SOPlayerState.h"
#include "SOProfileStore.h"
#include "SOProgression.h"
#include "SOSpecies.h"
#include "SOWeaponData.h"

namespace
{
	USOInventoryComponent* FreshInventory()
	{
		USOInventoryComponent* Inv = NewObject<USOInventoryComponent>();
		Inv->bPersist = false;
		Inv->NewProfile();
		return Inv;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOGoodsTablesTest, "ShatteredOrbit.Goods.TheTablesAreData", SOTest::Flags)
bool FSOGoodsTablesTest::RunTest(const FString& Parameters)
{
	// every gun is in one family of its own slot and has an origin; every item a drop, a dismantle, a raise or the
	// starting stock names is one the tables know (SO_IMPORT_ONLY=goods,gunnumbers,progression)
	const USOLootTables* Tables = USOLootLibrary::GetTables();
	if (!TestNotNull(TEXT("the loot tables"), Tables))
	{
		return false;
	}
	TestTrue(TEXT("collected items are data"), Tables->Goods.Num() >= 10);
	TestTrue(TEXT("the families are data"), Tables->Families.Num() >= 8);
	TestTrue(TEXT("the origins are data"), Tables->Origins.Num() >= 4);
	int32 Guns = 0;
	for (const FSOArchetypeEntry& Entry : Tables->Archetypes)
	{
		const USOWeaponData* Data = Entry.Data.LoadSynchronous();
		if (!Data)
		{
			continue;
		}
		++Guns;
		const FSOGunGroup* Family = Tables->FindFamily(Data->Family);
		TestTrue(FString::Printf(TEXT("%s is in a family (%s)"), *Entry.Id.ToString(), *Data->Family.ToString()), Family != nullptr);
		TestTrue(FString::Printf(TEXT("%s's family is of its slot"), *Entry.Id.ToString()), Family && Family->Slot == Data->Slot);
		TestTrue(FString::Printf(TEXT("%s has an origin (%s)"), *Entry.Id.ToString(), *Data->Origin.ToString()), Tables->FindOrigin(Data->Origin) != nullptr);
	}
	TestTrue(TEXT("every gun was looked at"), Guns >= 30);
	for (const TPair<FName, FSOGoodsDropList>& List : Tables->GoodsDrops)
	{
		for (const FSOGoodsDrop& Drop : List.Value.Drops)
		{
			TestNotNull(FString::Printf(TEXT("the drop list %s names a known item (%s)"), *List.Key.ToString(), *Drop.Item.ToString()), Tables->FindGoods(Drop.Item));
		}
	}
	for (const TPair<FName, FName>& Each : Tables->DismantleGoods)
	{
		TestNotNull(FString::Printf(TEXT("dismantling a %s gun gives a known item"), *Each.Key.ToString()), Tables->FindGoods(Each.Value));
	}
	for (const TPair<FName, int32>& Each : Tables->StarterGoods)
	{
		TestNotNull(FString::Printf(TEXT("the starting stock's %s is a known item"), *Each.Key.ToString()), Tables->FindGoods(Each.Key));
	}
	const USOProgressionTable& Rules = USOProgressionTable::Get();
	for (const TPair<FName, FName>& Each : Rules.UpgradeGunGoods)
	{
		TestNotNull(FString::Printf(TEXT("raising a %s gun takes a known item"), *Each.Key.ToString()), Tables->FindGoods(Each.Value));
	}
	TestNotNull(TEXT("raising armour takes a known item"), Tables->FindGoods(Rules.UpgradeArmourGoods));
	TestNotNull(TEXT("raising Legendary gear takes a known item"), Tables->FindGoods(Rules.UpgradeRareGoods));
	for (const FSOGoodsInfo& Info : Tables->Goods)
	{
		TestFalse(FString::Printf(TEXT("%s has a name"), *Info.Id.ToString()), Info.Name.IsEmpty());
		TestFalse(FString::Printf(TEXT("%s has a line"), *Info.Id.ToString()), Info.Lore.IsEmpty());
		TestTrue(FString::Printf(TEXT("%s can be held"), *Info.Id.ToString()), Info.Stack >= 1);
		if (Info.Kind == ESOGoodsKind::Consumable)
		{
			TestTrue(FString::Printf(TEXT("the consumable %s does something"), *Info.Id.ToString()), Info.Heal + Info.Shield + Info.Ultimate > 0.0f);
		}
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOGoodsHoldTest, "ShatteredOrbit.Goods.HeldStackedAndTaken", SOTest::Flags)
bool FSOGoodsHoldTest::RunTest(const FString& Parameters)
{
	const USOLootTables* Tables = USOLootLibrary::GetTables();
	if (!TestNotNull(TEXT("the loot tables"), Tables))
	{
		return false;
	}
	USOInventoryComponent* Inv = FreshInventory();
	for (const TPair<FName, int32>& Each : Tables->StarterGoods)
	{
		TestEqual(FString::Printf(TEXT("a new profile starts with its %s"), *Each.Key.ToString()), Inv->CountOf(Each.Key), Each.Value);
	}
	const int32 Amber = Inv->CountOf(TEXT("amber"));
	TestEqual(TEXT("goods stack"), Inv->AddGoods(TEXT("amber"), 5, false), 5);
	TestEqual(TEXT("in one stack"), Inv->CountOf(TEXT("amber")), Amber + 5);
	const FSOGoodsInfo* Stim = Tables->FindGoods(TEXT("stim"));
	if (TestNotNull(TEXT("the field stim"), Stim))
	{
		const int32 Had = Inv->CountOf(TEXT("stim"));
		TestEqual(TEXT("no more is carried than its stack"), Inv->AddGoods(TEXT("stim"), 100, false), Stim->Stack - Had);
		TestEqual(TEXT("the stack is full"), Inv->CountOf(TEXT("stim")), Stim->Stack);
		TestEqual(TEXT("and takes no more"), Inv->AddGoods(TEXT("stim"), 1, false), 0);
	}
	TestEqual(TEXT("an unknown item is not taken"), Inv->AddGoods(TEXT("no_such_item"), 3, false), 0);
	TestTrue(TEXT("what is held is held"), Inv->HasGoods({ { TEXT("amber"), 3 } }));
	TestFalse(TEXT("one item named twice counts together"), Inv->HasGoods({ { TEXT("amber"), Amber + 3 }, { TEXT("amber"), 3 } }));
	const int32 Plate = Inv->CountOf(TEXT("plate"));
	TestFalse(TEXT("all or nothing: short of one, none is taken"), Inv->TakeGoods({ { TEXT("plate"), 1 }, { TEXT("void_crystal"), 1000 } }));
	TestEqual(TEXT("and nothing was"), Inv->CountOf(TEXT("plate")), Plate);
	TestTrue(TEXT("taken"), Inv->TakeGoods({ { TEXT("plate"), Plate } }));
	TestEqual(TEXT("a stack used up is gone"), Inv->CountOf(TEXT("plate")), 0);
	TestFalse(TEXT("and leaves nothing behind"), Inv->GetGoods().ContainsByPredicate([](const FSOGoodsStack& S) { return S.Id == TEXT("plate"); }));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOGoodsRaiseTest, "ShatteredOrbit.Goods.RaisingTakesMaterials", SOTest::Flags)
bool FSOGoodsRaiseTest::RunTest(const FString& Parameters)
{
	// a raise takes the piece's material beside credits and alloy, and void crystal from Legendary on; short of any of
	// it, nothing is taken and nothing changes
	const USOProgressionTable& Rules = USOProgressionTable::Get();
	USOInventoryComponent* Inv = FreshInventory();
	FRandomStream Rng(11);
	const FSOWeaponInstance Gun = Inv->AddWeapon(USOLootLibrary::MakeWeapon(TEXT("auto"), 3, 10, Rng), false);
	TArray<FSOGoodsCost> Takes;
	Inv->GetUpgradeGoods(Gun.Uid, Takes);
	TArray<FSOGoodsCost> Want;
	Rules.UpgradeGoods(TEXT("energy"), 3, Want);
	TestTrue(TEXT("a Legendary light gun takes its material and void crystal"), Takes.Num() == 2 && Takes.Num() == Want.Num());
	TestTrue(TEXT("the light guns' material"), Takes.ContainsByPredicate([&Rules](const FSOGoodsCost& C) { return C.Item == Rules.UpgradeGunGoods.FindRef(TEXT("energy")) && C.Count > 0; }));
	TestTrue(TEXT("and void crystal"), Takes.ContainsByPredicate([&Rules](const FSOGoodsCost& C) { return C.Item == Rules.UpgradeRareGoods && C.Count > 0; }));
	Inv->AddCredits(1000000);
	Inv->AddAlloy(100000);
	Inv->TakeGoods({ { Rules.UpgradeRareGoods, Inv->CountOf(Rules.UpgradeRareGoods) } });
	const int32 Credits = Inv->GetCredits(), Power = Inv->Find(Gun.Uid)->Power;
	TestFalse(TEXT("without void crystal a Legendary is not raised"), Inv->Upgrade(Gun.Uid));
	TestTrue(TEXT("and nothing was paid or changed"), Inv->GetCredits() == Credits && Inv->Find(Gun.Uid)->Power == Power);
	Inv->AddGoods(Rules.UpgradeRareGoods, 5, false);
	FName MaterialId;
	int32 TookMaterial = 0, TookCrystal = 0;
	for (const FSOGoodsCost& C : Takes)
	{
		if (C.Item == Rules.UpgradeRareGoods)
		{
			TookCrystal += C.Count;
		}
		else
		{
			MaterialId = C.Item;
			TookMaterial += C.Count;
		}
	}
	const int32 Material = Inv->CountOf(MaterialId), Crystal = Inv->CountOf(Rules.UpgradeRareGoods);
	TestTrue(TEXT("with it, it is"), Inv->Upgrade(Gun.Uid));
	TestEqual(TEXT("the material was taken"), Inv->CountOf(MaterialId), Material - TookMaterial);
	TestEqual(TEXT("and the crystal"), Inv->CountOf(Rules.UpgradeRareGoods), Crystal - TookCrystal);

	// a common gun takes no crystal; an armour piece takes armour's material
	const FSOWeaponInstance Plain = Inv->AddWeapon(USOLootLibrary::MakeWeapon(TEXT("rifle"), 0, 10, Rng), false);
	Inv->GetUpgradeGoods(Plain.Uid, Takes);
	TestTrue(TEXT("a Common ballistic gun takes only its own material"), Takes.Num() == 1 && Takes[0].Item == Rules.UpgradeGunGoods.FindRef(TEXT("kinetic")));
	if (Inv->GetArmor().Num() > 0)
	{
		Inv->GetUpgradeGoods(Inv->GetArmor()[0].Uid, Takes);
		TestTrue(TEXT("an armour piece takes armour's material"), Takes.ContainsByPredicate([&Rules](const FSOGoodsCost& C) { return C.Item == Rules.UpgradeArmourGoods; }));
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOGoodsDismantleTest, "ShatteredOrbit.Goods.DismantlingGivesMaterials", SOTest::Flags)
bool FSOGoodsDismantleTest::RunTest(const FString& Parameters)
{
	const USOLootTables* Tables = USOLootLibrary::GetTables();
	if (!TestNotNull(TEXT("the loot tables"), Tables))
	{
		return false;
	}
	USOInventoryComponent* Inv = FreshInventory();
	FRandomStream Rng(5);
	const FSOWeaponInstance Rare = Inv->AddWeapon(USOLootLibrary::MakeWeapon(TEXT("carbine"), 2, 10, Rng), false);
	const FName Parts = Tables->DismantleGoods.FindRef(TEXT("kinetic"));
	const int32 Had = Inv->CountOf(Parts);
	const int32 Alloy = Inv->GetAlloy();
	TestTrue(TEXT("dismantled"), Inv->Dismantle(Rare.Uid) > 0);
	TestTrue(TEXT("for alloy as before"), Inv->GetAlloy() > Alloy);
	TestEqual(TEXT("and its class's material by rarity"), Inv->CountOf(Parts), Had + Tables->DismantleCount[FMath::Min(2, Tables->DismantleCount.Num() - 1)]);
	const FSOWeaponInstance Legendary = Inv->AddWeapon(USOLootLibrary::MakeWeapon(TEXT("pulse"), 3, 10, Rng), false);
	const int32 Crystal = Inv->CountOf(Tables->DismantleCrystalItem);
	Inv->Dismantle(Legendary.Uid);
	TestTrue(TEXT("a Legendary gives void crystal too"), Inv->CountOf(Tables->DismantleCrystalItem) > Crystal);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOGoodsDropTest, "ShatteredOrbit.Goods.ElitesCarryTheirRelics", SOTest::Flags)
bool FSOGoodsDropTest::RunTest(const FString& Parameters)
{
	// a kill pays goods straight into the killer's inventory: an elite its list on top, and a named one its own relic
	SOTest::FTestWorld W;
	W.AddBox(FVector(-4000, -4000, -100), FVector(4000, 4000, 0));
	ASOCharacter* Player = W.SpawnCharacter(FVector(0, 0, 0));
	FActorSpawnParameters Params;
	Params.bDeferConstruction = true;
	ASOPlayerState* PS = W.World->SpawnActor<ASOPlayerState>(ASOPlayerState::StaticClass(), FTransform::Identity, Params);
	PS->GetInventory()->bPersist = false;
	PS->FinishSpawning(FTransform::Identity);
	Player->SetPlayerState(PS);
	USOInventoryComponent* Inv = PS->GetInventory();
	W.Run(0.2f);
	const USOLootTables* Tables = USOLootLibrary::GetTables();
	if (!TestNotNull(TEXT("inventory"), Inv) || !TestNotNull(TEXT("the loot tables"), Tables))
	{
		return false;
	}
	const FSOGoodsDropList* Named = Tables->GoodsDrops.Find(TEXT("remnant_captain"));
	if (!TestTrue(TEXT("the Levy Captain carries something of its own"), Named && Named->Drops.Num() > 0))
	{
		return false;
	}
	const FName Relic = Named->Drops[0].Item;
	FSOSpeciesVariant V;
	V.Id = TEXT("remnant_captain");
	V.DisplayName = FText::FromString(TEXT("Levy Captain"));
	FSOSpawnOptions Options;
	Options.bOnNav = false;
	Options.Variant = &V;
	ASOEnemy* E = USOSpeciesLibrary::Spawn(W.World, TEXT("remnant"), FVector(600, 0, 0), 180.0f, Options);
	if (!TestNotNull(TEXT("a remnant spawned (/Game/Characters/Remnant imported)"), E))
	{
		return false;
	}
	if (AController* Brain = E->GetController())
	{
		Brain->UnPossess();
		Brain->Destroy();
	}
	TestEqual(TEXT("its drops are its variant's"), E->GetLootKey(), FName(TEXT("remnant_captain")));
	TestEqual(TEXT("an elite"), E->GetLootTier(), 1);
	TArray<FString> Lines;
	Inv->OnFeed.AddLambda([&Lines](const FString& Text, const FLinearColor&) { Lines.Add(Text); });
	const int32 Crystal = Inv->CountOf(TEXT("void_crystal"));
	W.Run(0.1f);
	USOCombatStatics::ApplyDamage(Player, E, 100000.0f, false);
	W.Run(0.1f);
	TestTrue(TEXT("the creature died"), E->IsDead());
	TestEqual(TEXT("its relic is the killer's"), Inv->CountOf(Relic), 1);
	TestTrue(TEXT("an elite pays void crystal"), Inv->CountOf(TEXT("void_crystal")) > Crystal);
	const FSOGoodsInfo* RelicInfo = Tables->FindGoods(Relic);
	TestTrue(TEXT("and the feed says so"), RelicInfo && Lines.ContainsByPredicate([RelicInfo](const FString& L) { return L.Contains(RelicInfo->Name.ToString()); }));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOGoodsUseTest, "ShatteredOrbit.Goods.ConsumablesWork", SOTest::Flags)
bool FSOGoodsUseTest::RunTest(const FString& Parameters)
{
	SOTest::FTestWorld W;
	W.AddBox(FVector(-4000, -4000, -100), FVector(4000, 4000, 0));
	ASOCharacter* Player = W.SpawnCharacter(FVector(0, 0, 0));
	FActorSpawnParameters Params;
	Params.bDeferConstruction = true;
	ASOPlayerState* PS = W.World->SpawnActor<ASOPlayerState>(ASOPlayerState::StaticClass(), FTransform::Identity, Params);
	PS->GetInventory()->bPersist = false;
	PS->FinishSpawning(FTransform::Identity);
	Player->SetPlayerState(PS);
	USOInventoryComponent* Inv = PS->GetInventory();
	W.Run(0.2f);
	if (!TestNotNull(TEXT("inventory"), Inv))
	{
		return false;
	}
	Inv->AddGoods(TEXT("stim"), 2, false);
	Inv->AddGoods(TEXT("cell"), 2, false);
	TestFalse(TEXT("a stim does nothing at full health"), Inv->CanUseGoods(TEXT("stim")));
	TestFalse(TEXT("so it is not used up"), Inv->UseGoods(TEXT("stim")));
	TestFalse(TEXT("a material is not used"), Inv->CanUseGoods(TEXT("amber")));
	// hurt through the shield into the health
	USOCombatStatics::ApplyDamage(Player, Player, Player->GetShield() + Player->GetMaxHealth() * 0.5f, false);
	W.Run(0.1f);
	const float Hurt = Player->GetHealth();
	TestTrue(TEXT("the body is hurt"), Hurt < Player->GetMaxHealth() - 1.0f && !Player->IsDead());
	const int32 Stims = Inv->CountOf(TEXT("stim"));
	TestTrue(TEXT("now a stim helps"), Inv->CanUseGoods(TEXT("stim")));
	TestTrue(TEXT("used"), Inv->UseGoods(TEXT("stim")));
	W.Run(0.05f);
	TestTrue(TEXT("it gave health back"), Player->GetHealth() > Hurt + 1.0f);
	TestEqual(TEXT("one was used"), Inv->CountOf(TEXT("stim")), Stims - 1);
	TestTrue(TEXT("a shield cell helps while the shield is down"), Player->GetShield() >= Player->GetMaxShield() - 0.5f || Inv->CanUseGoods(TEXT("cell")));
	if (Player->GetShield() < Player->GetMaxShield() - 0.5f)
	{
		Inv->UseGoods(TEXT("cell"));
		W.Run(0.05f);
		TestTrue(TEXT("the shield is back"), Player->GetShield() >= Player->GetMaxShield() - 0.5f);
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOGoodsSaveTest, "ShatteredOrbit.Goods.AnOldSaveStartsWithTheStock", SOTest::Flags)
bool FSOGoodsSaveTest::RunTest(const FString& Parameters)
{
	// a profile saved before collected items (version 7) is migrated with the starting stock; a new one is current
	USOSaveGame* Old = NewObject<USOSaveGame>();
	Old->Version = 7;
	TestTrue(TEXT("migrated"), USOProfileStore::Migrate(Old));
	TestEqual(TEXT("to this build's version"), Old->Version, USOSaveGame::CurrentVersion);
	TArray<FSOGoodsStack> Stock;
	USOInventoryComponent::StarterGoods(Stock);
	TestTrue(TEXT("with the starting stock"), Stock.Num() > 0 && Old->Goods.Num() == Stock.Num());
	USOSaveGame* Current = NewObject<USOSaveGame>();
	Current->Version = USOSaveGame::CurrentVersion;
	TestTrue(TEXT("a current one"), USOProfileStore::Migrate(Current));
	TestEqual(TEXT("is left as it is"), Current->Goods.Num(), 0);
	return true;
}

#endif
