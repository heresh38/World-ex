// Stage 5 automation tests: loot tables from data.js, rolls, stats, the reliquary pool, the inventory, pickups and
// every archetype firing and reloading.

#include "SOTestWorld.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "Components/StaticMeshComponent.h"
#include "Dom/JsonObject.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "SOGunRigComponent.h"
#include "SOInventoryComponent.h"
#include "SOLootActors.h"
#include "SOLootLibrary.h"
#include "SOPlayerState.h"
#include "SOProjectileSubsystem.h"
#include "SOReload.h"
#include "SOSound.h"
#include "SOWeapon.h"
#include "SOWeaponData.h"

namespace SOTest
{
	TSharedPtr<FJsonObject> GameData()
	{
		FString Text;
		const FString Path = FPaths::Combine(FPaths::ProjectDir(), TEXT("Data/game_data.json"));
		if (!FFileHelper::LoadFileToString(Text, *Path))
		{
			return nullptr;
		}
		TSharedPtr<FJsonObject> Root;
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Text);
		return FJsonSerializer::Deserialize(Reader, Root) ? Root : nullptr;
	}

	/** A player with a player state (inventory, not saved to disk). */
	ASOCharacter* SpawnLooter(FTestWorld& W, USOInventoryComponent*& OutInventory)
	{
		W.AddBox(FVector(-4000, -4000, -100), FVector(4000, 4000, 0));
		ASOCharacter* Player = W.SpawnCharacter(FVector(0, 0, 0));
		FActorSpawnParameters Params;
		Params.bDeferConstruction = true;
		ASOPlayerState* PS = W.World->SpawnActor<ASOPlayerState>(ASOPlayerState::StaticClass(), FTransform::Identity, Params);
		PS->GetInventory()->bPersist = false;
		PS->FinishSpawning(FTransform::Identity);
		Player->SetPlayerState(PS);
		OutInventory = PS->GetInventory();
		W.Run(0.2f);
		return Player;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOLootTablesTest, "ShatteredOrbit.Loot.TablesMatchDataJs", SOTest::Flags)
bool FSOLootTablesTest::RunTest(const FString& Parameters)
{
	const USOLootTables* Tables = USOLootLibrary::GetTables();
	const TSharedPtr<FJsonObject> Data = SOTest::GameData();
	if (!TestNotNull(TEXT("DA_LootTables (run import_assets.py)"), Tables) || !TestTrue(TEXT("Data/game_data.json (the weapon / loot data)"), Data.IsValid()))
	{
		return false;
	}
	const TSharedPtr<FJsonObject> Archetypes = Data->GetObjectField(TEXT("archetypes"));
	TestEqual(TEXT("every archetype has a data asset"), Tables->Archetypes.Num(), Archetypes->Values.Num());
	TestEqual(TEXT("rarities"), Tables->Rarities.Num(), 5);
	TestEqual(TEXT("perks"), Tables->Perks.Num(), Data->GetObjectField(TEXT("perks"))->Values.Num());
	for (const TPair<FString, TSharedPtr<FJsonValue>>& Pair : Archetypes->Values)
	{
		const TSharedPtr<FJsonObject> A = Pair.Value->AsObject();
		const USOWeaponData* W = Tables->LoadArchetype(FName(Pair.Key));
		if (!TestNotNull(*FString::Printf(TEXT("%s data"), *Pair.Key), W))
		{
			continue;
		}
		TestEqual(*FString::Printf(TEXT("%s damage"), *Pair.Key), W->Damage, (float)A->GetNumberField(TEXT("dmg")));
		TestEqual(*FString::Printf(TEXT("%s rpm"), *Pair.Key), W->RoundsPerMinute, (float)A->GetNumberField(TEXT("rpm")));
		TestEqual(*FString::Printf(TEXT("%s magazine"), *Pair.Key), W->MagazineSize, (int32)A->GetNumberField(TEXT("mag")));
		TestEqual(*FString::Printf(TEXT("%s slot"), *Pair.Key), W->Slot, (int32)A->GetNumberField(TEXT("slot")));
		double Pellets = 1.0;
		A->TryGetNumberField(TEXT("pellets"), Pellets);
		TestEqual(*FString::Printf(TEXT("%s pellets"), *Pair.Key), W->Pellets, (int32)Pellets);
		TestNotNull(*FString::Printf(TEXT("%s model"), *Pair.Key), W->BodyMesh.LoadSynchronous());
		TestTrue(*FString::Printf(TEXT("%s sights"), *Pair.Key), W->Sights.Num() > 0 && W->Sights.Contains(W->DefaultSight));
	}
	for (const FSOSightInfo& Sight : Tables->Sights)
	{
		TestTrue(*FString::Printf(TEXT("optic %s has a model"), *Sight.Id.ToString()), Sight.Id == TEXT("default") || !Sight.Mesh.IsNull());
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOLootRollsTest, "ShatteredOrbit.Loot.Rolls", SOTest::Flags)
bool FSOLootRollsTest::RunTest(const FString& Parameters)
{
	const USOLootTables* Tables = USOLootLibrary::GetTables();
	if (!TestNotNull(TEXT("loot tables"), Tables))
	{
		return false;
	}
	FRandomStream Rng(1234);
	int32 Counts[5] = { 0, 0, 0, 0, 0 };
	const int32 N = 40000;
	for (int32 i = 0; i < N; ++i)
	{
		++Counts[USOLootLibrary::RollRarity(Rng)];
	}
	const float Expected[5] = { 0.38f, 0.30f, 0.22f, 0.085f, 0.015f };
	for (int32 r = 0; r < 5; ++r)
	{
		TestEqual(*FString::Printf(TEXT("rarity %d share"), r), Counts[r] / float(N), Expected[r], 0.012f);
	}
	for (int32 i = 0; i < 300; ++i)
	{
		const FSOWeaponInstance W = USOLootLibrary::RollWeapon(30, FSORollOptions(), Rng);
		const USOWeaponData* Data = Tables->LoadArchetype(W.Archetype);
		if (!TestNotNull(TEXT("rolled archetype exists"), Data))
		{
			return false;
		}
		TestEqual(TEXT("perks by rarity"), W.Perks.Num(), Tables->GetRarity(W.Rarity).Perks);
		TestEqual(TEXT("no repeated perk"), TSet<FName>(W.Perks).Num(), W.Perks.Num());
		TestTrue(TEXT("stat rolls stay close to the gun"), W.Stats.Damage >= 0.97f && W.Stats.Damage <= 1.03f && W.Stats.Rpm >= 0.98f && W.Stats.Rpm <= 1.02f
			&& W.Stats.Range >= 0.94f && W.Stats.Range <= 1.06f);
		TestTrue(TEXT("a compatible sight"), Data->Sights.Contains(W.Sight));
		TestEqual(TEXT("every copy carries the gun's one name"), W.Name, Data->Title.ToString());
		TestFalse(TEXT("the gun has a name"), W.Name.IsEmpty());
	}
	// stats: rarity and power, perks
	FSOWeaponInstance W = USOLootLibrary::MakeWeapon(TEXT("rifle"), 3, 40, Rng);
	W.Stats = FSOWeaponRolls();
	W.Perks = { TEXT("overflow"), TEXT("quickdraw"), TEXT("steady") };
	const FSOWeaponStats S = USOLootLibrary::ComputeStats(W);
	TestEqual(TEXT("damage = base x small rarity bonus x (1 + power / 200)"), S.Damage, 19.0f * 1.04f * 1.2f, 0.01f);
	TestEqual(TEXT("Overflow: magazine +40 %"), S.Mag, 42);
	TestEqual(TEXT("Quickload: reload 35 % faster"), S.Reload, 2.3f * 0.65f, 0.01f);
	TestEqual(TEXT("Gyro Stock: spread -40 %"), S.Spread, 0.6f, 0.01f);
	TestEqual(TEXT("roll quality of average rolls"), USOLootLibrary::RollQuality(W), 50);
	// the reliquary pool
	for (int32 i = 0; i < 50; ++i)
	{
		const TArray<FSOWeaponInstance> Reward = USOLootLibrary::RollReliquary(30, Rng);
		TestTrue(TEXT("2-3 weapons"), Reward.Num() >= 2 && Reward.Num() <= 3);
		for (const FSOWeaponInstance& R : Reward)
		{
			TestTrue(TEXT("reliquary: uncommon or better"), R.Rarity >= 1);
			TestTrue(TEXT("reliquary: power around the player's"), R.Power >= 29 && R.Power <= 38);
			TestEqual(TEXT("source"), R.Source, FString(TEXT("Spire reliquary")));
		}
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOInventoryTest, "ShatteredOrbit.Loot.Inventory", SOTest::Flags)
bool FSOInventoryTest::RunTest(const FString& Parameters)
{
	SOTest::FTestWorld W;
	USOInventoryComponent* Inv = nullptr;
	ASOCharacter* Player = SOTest::SpawnLooter(W, Inv);
	if (!TestNotNull(TEXT("inventory"), Inv))
	{
		return false;
	}
	// a new profile: three starters + the armoury (every kinetic and horror archetype), the rifle in hand
	TestEqual(TEXT("starters + armoury"), Inv->GetItems().Num(), 3 + 11);
	const FSOWeaponInstance* Primary = Inv->GetEquipped(0);
	TestTrue(TEXT("the assault rifle is the primary"), Primary && Primary->Archetype == TEXT("rifle"));
	TestTrue(TEXT("special and heavy equipped"), Inv->GetEquipped(1) && Inv->GetEquipped(2));

	// possession equips the active slot's copy
	Player->BindInventory();
	W.Run(0.1f);
	TestTrue(TEXT("the character holds the equipped copy"), Player->GetWeapon() && Player->GetWeapon()->GetInstance().Uid == Primary->Uid);

	// switching slots swaps the gun and keeps each copy's ammo
	Player->GetWeapon()->SetAmmo(7, 100);
	Inv->SelectSlot(1);
	W.Run(0.1f);
	TestTrue(TEXT("special slot in hand"), Player->GetWeapon() && Player->GetWeapon()->GetInstance().Uid == Inv->GetEquipped(1)->Uid);
	Inv->SelectSlot(0);
	W.Run(0.1f);
	TestEqual(TEXT("the rifle comes back with its 7 rounds"), Player->GetWeapon() ? Player->GetWeapon()->GetMag() : -1, 7);

	// rules: equip, lock, dismantle
	FRandomStream Rng(7);
	FSOWeaponInstance Drop = USOLootLibrary::MakeWeapon(TEXT("carbine"), 2, 20, Rng);
	const FSOWeaponInstance Added = Inv->AddWeapon(Drop);
	TestTrue(TEXT("new drops wear a NEW tag"), Inv->Find(Added.Uid) && Inv->Find(Added.Uid)->bNew);
	TestEqual(TEXT("equipped copies cannot be dismantled"), Inv->Dismantle(Primary->Uid), 0);
	Inv->SetKeep(Added.Uid, true);
	TestEqual(TEXT("locked copies cannot be dismantled"), Inv->Dismantle(Added.Uid), 0);
	Inv->SetKeep(Added.Uid, false);
	const int32 Alloy = Inv->GetAlloy();
	TestEqual(TEXT("dismantle: 2 + 3 per rarity"), Inv->Dismantle(Added.Uid), 8);
	TestEqual(TEXT("alloy paid"), Inv->GetAlloy(), Alloy + 8);
	Inv->Equip(Inv->AddWeapon(USOLootLibrary::MakeWeapon(TEXT("dmr"), 1, 20, Rng)).Uid);
	W.Run(0.1f);
	TestTrue(TEXT("equipping into the active slot swaps the gun in hand"), Player->GetWeapon() && Player->GetWeapon()->GetData()->Archetype == TEXT("dmr"));

	// the vault cap breaks down the weakest plain spare
	Inv->MarkAllSeen();
	while (Inv->GetItems().Num() < USOLootLibrary::VaultCap)
	{
		FSOWeaponInstance Spare = USOLootLibrary::MakeWeapon(TEXT("pistol"), 1, 30, Rng);
		Inv->AddWeapon(Spare, false);
		Inv->MarkAllSeen();
	}
	FSOWeaponInstance Weakest = USOLootLibrary::MakeWeapon(TEXT("pistol"), 0, 1, Rng);
	const FString WeakUid = Inv->AddWeapon(Weakest, false).Uid;
	Inv->MarkAllSeen();
	Inv->AddWeapon(USOLootLibrary::MakeWeapon(TEXT("pistol"), 1, 30, Rng), false);
	TestEqual(TEXT("vault stays at the cap"), Inv->GetItems().Num(), USOLootLibrary::VaultCap);
	TestNull(TEXT("the weakest plain spare went"), Inv->Find(WeakUid));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOPickupTest, "ShatteredOrbit.Loot.PickupsAndReliquary", SOTest::Flags)
bool FSOPickupTest::RunTest(const FString& Parameters)
{
	SOTest::FTestWorld W;
	USOInventoryComponent* Inv = nullptr;
	ASOCharacter* Player = SOTest::SpawnLooter(W, Inv);
	USOLootSubsystem* Loot = W.World->GetSubsystem<USOLootSubsystem>();
	if (!TestNotNull(TEXT("inventory"), Inv) || !TestNotNull(TEXT("loot subsystem"), Loot))
	{
		return false;
	}
	Player->BindInventory();
	W.Run(0.1f);
	const int32 Before = Inv->GetItems().Num();
	ASOLootPickup* Core = Loot->SpawnPickup(FVector(600, 0, 0), ESOPickupKind::Core, 3, 20);
	TestNotNull(TEXT("core spawned"), Core);
	Core->Collect(Player, Inv);
	TestEqual(TEXT("a core becomes a weapon"), Inv->GetItems().Num(), Before + 1);
	TestEqual(TEXT("of its rarity"), Inv->GetItems().Last().Rarity, 3);

	ASOWeapon* Held = Player->GetWeapon();
	Held->SetAmmo(Held->GetMag(), 50);
	ASOLootPickup* Ammo = Loot->SpawnPickup(FVector(600, 0, 0), ESOPickupKind::Ammo, 0, 20);
	Ammo->Collect(Player, Inv);
	TestTrue(*FString::Printf(TEXT("ammo tops up the reserve (%d)"), Held->GetReserve()), Held->GetReserve() > 50);

	// walking over a pickup collects it
	ASOLootPickup* Walk = Loot->SpawnPickup(Player->GetActorLocation(), ESOPickupKind::Core, 1, 20);
	const int32 Count = Inv->GetItems().Num();
	W.Run(0.2f);
	TestEqual(TEXT("walked-over core collected"), Inv->GetItems().Num(), Count + 1);
	TestFalse(TEXT("and gone"), IsValid(Walk));

	// the reliquary: sealed -> 2-3 weapons + credits + xp -> open -> reseals
	ASOReliquary* Reliquary = W.World->SpawnActor<ASOReliquary>(FVector(200, 0, 0), FRotator::ZeroRotator);
	Reliquary->RearmTime = 0.5f;
	W.Run(0.1f);
	const int32 Items = Inv->GetItems().Num();
	const int32 Credits = Inv->GetCredits();
	TestTrue(TEXT("sealed reliquary can be opened"), Reliquary->CanInteract(Player));
	Reliquary->Interact(Player);
	TestTrue(TEXT("reliquary open"), Reliquary->IsOpen());
	TestTrue(TEXT("2-3 weapons granted"), Inv->GetItems().Num() - Items >= 2 && Inv->GetItems().Num() - Items <= 3);
	TestTrue(TEXT("credits granted"), Inv->GetCredits() >= Credits + 900);
	TestFalse(TEXT("cannot be emptied twice"), Reliquary->CanInteract(Player));
	W.Run(0.7f);
	TestFalse(TEXT("reseals on the range"), Reliquary->IsOpen());
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOEveryArchetypeTest, "ShatteredOrbit.Weapon.EveryArchetypeFiresAndReloads", SOTest::Flags)
bool FSOEveryArchetypeTest::RunTest(const FString& Parameters)
{
	const USOLootTables* Tables = USOLootLibrary::GetTables();
	if (!TestNotNull(TEXT("loot tables"), Tables))
	{
		return false;
	}
	SOTest::FTestWorld W;
	W.AddBox(FVector(-4000, -4000, -100), FVector(4000, 4000, 0));
	W.AddBox(FVector(2500, -3000, 0), FVector(2600, 3000, 800));
	ASOCharacter* Player = W.SpawnCharacter(FVector(0, 0, 0));
	W.Run(0.3f);
	USOProjectileSubsystem* Rounds = W.World->GetSubsystem<USOProjectileSubsystem>();
	FRandomStream Rng(99);
	for (const FSOArchetypeEntry& Entry : Tables->Archetypes)
	{
		const FString Name = Entry.Id.ToString();
		FSOWeaponInstance Copy = USOLootLibrary::MakeWeapon(Entry.Id, 0, 10, Rng);
		ASOWeapon* Gun = Player->EquipInstance(Copy);
		if (!TestNotNull(*FString::Printf(TEXT("%s equips"), *Name), Gun))
		{
			continue;
		}
		W.Run(0.3f);
		const USOWeaponData* Data = Gun->GetData();
		TestTrue(*FString::Printf(TEXT("%s: both rigs built"), *Name), Gun->GetFirstPersonRig()->IsBuilt() && Gun->GetThirdPersonRig()->IsBuilt());
		// one trigger pull: pellets / burst
		const int32 InFlight = Rounds->GetNumInFlight();
		const int32 Shots = Gun->GetShotsFired();
		Gun->StartFire();
		W.Step();
		Gun->StopFire();
		TestEqual(*FString::Printf(TEXT("%s: one shot"), *Name), Gun->GetShotsFired(), Shots + 1);
		TestTrue(*FString::Printf(TEXT("%s: %d projectiles per shot"), *Name, Data->Pellets), Rounds->GetNumInFlight() - InFlight >= FMath::Max(1, Data->Pellets));
		if (Data->Burst > 1)
		{
			W.Run(0.5f);
			TestEqual(*FString::Printf(TEXT("%s: a burst of %d"), *Name, Data->Burst), Gun->GetShotsFired(), Shots + Data->Burst);
		}
		// empty it and reload: full again, whatever the choreography
		Gun->SetAmmo(0, 200);
		Gun->StartReload();
		TestTrue(*FString::Printf(TEXT("%s: reloading"), *Name), Gun->IsReloading());
		W.Run(Gun->GetReloadDuration() + 0.2f);
		TestFalse(*FString::Printf(TEXT("%s: reload finished (%.2f s)"), *Name, Gun->GetReloadDuration()), Gun->IsReloading());
		TestEqual(*FString::Printf(TEXT("%s: magazine full"), *Name), Gun->GetMag(), Gun->GetStats().Mag);
		W.Run(1.5f); // let rounds, rockets and goo land
	}
	return true;
}

// The Void Requiem set (the first operation's reward guns): every gun carries the parts its reload moves, reloads with
// a sequence of its own length, tolls with its own shot and has the set's foley.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOLootRequiemSetTest, "ShatteredOrbit.Loot.RequiemSet", SOTest::Flags)
bool FSOLootRequiemSetTest::RunTest(const FString& Parameters)
{
	const USOLootTables* Tables = USOLootLibrary::GetTables();
	if (!TestNotNull(TEXT("DA_LootTables (run import_assets.py)"), Tables))
	{
		return false;
	}
	const TMap<FName, TArray<FName>> Guns = {
		{ TEXT("vr_rifle"), { TEXT("mag"), TEXT("charge"), TEXT("bolt") } }, { TEXT("vr_sniper"), { TEXT("mag"), TEXT("bolt") } },
		{ TEXT("vr_smg"), { TEXT("mag"), TEXT("charge"), TEXT("bolt") } }, { TEXT("vr_shotgun"), { TEXT("pump"), TEXT("x_shell") } },
		{ TEXT("vr_lmg"), { TEXT("hatch"), TEXT("mag"), TEXT("charge") } },
		{ TEXT("vr_handcannon"), { TEXT("crane"), TEXT("cylinder"), TEXT("rounds"), TEXT("x_speedloader") } },
		{ TEXT("vr_pistol"), { TEXT("mag"), TEXT("slide") } }, { TEXT("vr_fusion"), { TEXT("hatch"), TEXT("biomass") } },
		{ TEXT("vr_rocket"), { TEXT("hatch"), TEXT("mag") } } };
	for (const TPair<FName, TArray<FName>>& Gun : Guns)
	{
		const FString Name = Gun.Key.ToString();
		const USOWeaponData* W = Tables->LoadArchetype(Gun.Key);
		if (!TestNotNull(*FString::Printf(TEXT("%s data"), *Name), W))
		{
			continue;
		}
		TestEqual(*FString::Printf(TEXT("%s is in the set"), *Name), W->SetId, FName(TEXT("void_requiem")));
		TestTrue(*FString::Printf(TEXT("%s never drops as ordinary loot"), *Name), W->LootWeight <= 0.0f);
		TestTrue(*FString::Printf(TEXT("%s violet tracer"), *Name), W->TracerColor.B > W->TracerColor.G && W->TracerColor.R > W->TracerColor.G);
		for (const FName Part : Gun.Value)
		{
			const FSOWeaponPart* Found = W->Parts.FindByPredicate([Part](const FSOWeaponPart& P) { return P.Name == Part; });
			TestTrue(*FString::Printf(TEXT("%s has its %s"), *Name, *Part.ToString()), Found && !Found->Mesh.IsNull());
		}
		for (const TCHAR* View : { TEXT("fp"), TEXT("world") })
		{
			TestNotNull(*FString::Printf(TEXT("%s shot sound (%s)"), *Name, View), USOSoundLibrary::Find(FName(*FString::Printf(TEXT("%s_shot_%s"), *Name, View))));
		}
		// tactical and empty reloads: real sequences (hand keys, events), the tactical one as long as the data says
		for (const bool bEmpty : { false, true })
		{
			int32 From = -1, To = -1;
			const TArray<FSOReloadSegment> Segs = SOReload::BuildReload(Gun.Key, true, false, bEmpty, W->ReloadTime, 3, From, To);
			TestTrue(*FString::Printf(TEXT("%s reload sequence"), *Name), Segs.Num() > 0);
			bool bHand = false, bMoves = false, bFeeds = false;
			for (const FSOReloadSegment& S : Segs)
			{
				bHand |= S.Channels.Contains(TEXT("hand"));
				for (const TPair<FName, TArray<FSOKey>>& Channel : S.Channels)
				{
					bMoves |= Channel.Key != TEXT("hand") && Channel.Key != TEXT("gun");
				}
				for (const FSOReloadEvent& E : S.Events)
				{
					bFeeds |= E.Name == TEXT("seat") || E.Name == TEXT("grant");
				}
			}
			TestTrue(*FString::Printf(TEXT("%s reload moves the off hand"), *Name), bHand);
			TestTrue(*FString::Printf(TEXT("%s reload moves a part of the gun"), *Name), bMoves);
			TestTrue(*FString::Printf(TEXT("%s reload feeds the gun"), *Name), bFeeds);
			if (!bEmpty && From < 0)
			{
				const float Nominal = Segs.Num() > 1 ? Segs[0].Duration + Segs.Last().Duration : Segs[0].Duration;
				TestTrue(*FString::Printf(TEXT("%s tactical reload lasts its reload time"), *Name), FMath::IsNearlyEqual(Nominal, W->ReloadTime, 0.02f));
			}
		}
	}
	TestEqual(TEXT("the shotgun racks its pump after a shot"), SOReload::GetStyle(TEXT("vr_shotgun")), FName(TEXT("pump")));

	// the proving range's cache: one Legendary copy of each of the nine, no credits, and it reseals
	{
		SOTest::FTestWorld W;
		USOInventoryComponent* Inv = nullptr;
		ASOCharacter* Player = SOTest::SpawnLooter(W, Inv);
		ASOReliquary* Cache = W.World->SpawnActorDeferred<ASOReliquary>(ASOReliquary::StaticClass(), FTransform(FVector(200, 0, 0)));
		Cache->RewardSet = TEXT("void_requiem");
		Cache->SourceName = TEXT("Void Requiem cache");
		Cache->RearmTime = 0.5f;
		Cache->FinishSpawning(FTransform(FVector(200, 0, 0)));
		W.Run(0.1f);
		const int32 Items = Inv->GetItems().Num();
		const int32 Credits = Inv->GetCredits();
		Cache->Interact(Player);
		TestTrue(TEXT("cache open"), Cache->IsOpen());
		TestEqual(TEXT("the cache hands out all nine guns"), Inv->GetItems().Num() - Items, Guns.Num());
		TestEqual(TEXT("and no credits"), Inv->GetCredits(), Credits);
		TSet<FName> Got;
		for (const FSOWeaponInstance& Gun : Cache->GetLastRewards())
		{
			Got.Add(Gun.Archetype);
			TestEqual(*FString::Printf(TEXT("%s from the cache is Legendary"), *Gun.Archetype.ToString()), Gun.Rarity, 3);
			TestTrue(*FString::Printf(TEXT("%s from the cache is one of the set"), *Gun.Archetype.ToString()), Guns.Contains(Gun.Archetype));
		}
		TestEqual(TEXT("one copy of each"), Got.Num(), Guns.Num());
		W.Run(0.7f);
		TestFalse(TEXT("the cache reseals"), Cache->IsOpen());
	}
	for (const TCHAR* Foley : { TEXT("vr_mag_in"), TEXT("vr_mag_slap"), TEXT("vr_rack_back"), TEXT("vr_hatch_open"), TEXT("vr_hatch_close"), TEXT("vr_bio_in"),
		TEXT("vr_shell_in"), TEXT("vr_pump_back"), TEXT("vr_cyl_open"), TEXT("vr_speedload"), TEXT("vr_slide_back") })
	{
		TestNotNull(*FString::Printf(TEXT("foley %s"), Foley), USOSoundLibrary::Find(FName(Foley)));
	}
	return true;
}

#endif
