// Stage 5 automation tests: loot tables from data.js, rolls, stats, the reliquary pool, the inventory, pickups and
// every archetype firing and reloading.

#include "SOTestWorld.h"

#if WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR

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
#include "SOCombatStatics.h"
#include "SOCombatTypes.h"
#include "SOEnemy.h"

namespace SOTest
{
	ASOEnemy* SpawnStalker(FTestWorld& W, const FVector& Feet, const FRotator& Rotation);
}

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
		TestTrue(*FString::Printf(TEXT("%s: the gun built"), *Name), Gun->GetRig()->IsBuilt());
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
		// empty it and reload: full again, whatever the choreography (a gun that condenses never reloads: it fills
		// again by itself once it has cooled)
		if (Gun->Condenses())
		{
			Gun->SetAmmo(0, 200);
			Gun->StartReload();
			TestFalse(*FString::Printf(TEXT("%s: never reloads"), *Name), Gun->IsReloading());
			W.Run(Data->VentTime + Data->HeatCoolDelay + 1.0f / FMath::Max(Data->HeatCool, 0.1f) + Data->RefillTime + 0.5f);
			TestEqual(*FString::Printf(TEXT("%s: condensed full from the reserve"), *Name), Gun->GetMag(), Gun->GetStats().Mag);
			W.Run(1.5f);
			continue;
		}
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

// The light guns reload their own way, never as the kinetic guns change magazines (the owner, 2026-11-15: "a different
// reload than the kinetic guns ... a part of the gun opens up and draws energy in from the air, some venting on
// overheating, maybe a battery replacement"; before it, on the SMG, the cell never moved and the hand held it "relaxed on
// his palm"). Cell guns: the cell is a part, the hand GRIPS it, it comes out, a spare is turned home. Vent and intake
// guns: a flank flap is a part (thrown open by the hand to vent, opening by itself to draw), it opens and closes, the purge or the draw is shown for a while in between, and every
// light gun charges up as it closes.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOLootLightReloadTest, "ShatteredOrbit.Loot.LightGunsReloadTheirOwnWay", SOTest::Flags)
bool FSOLootLightReloadTest::RunTest(const FString& Parameters)
{
	const USOLootTables* Tables = USOLootLibrary::GetTables();
	if (!TestNotNull(TEXT("DA_LootTables (run import_assets.py)"), Tables))
	{
		return false;
	}
	const TPair<const TCHAR*, const TCHAR*> Guns[] = { { TEXT("auto"), TEXT("cell") }, { TEXT("smg"), TEXT("cell") }, { TEXT("pulse"), TEXT("cell") },
		{ TEXT("energy"), TEXT("cell") }, { TEXT("hmg"), TEXT("vent") }, { TEXT("sniper"), TEXT("vent") }, { TEXT("scout"), TEXT("vent") },
		{ TEXT("shotgun"), TEXT("intake") }, { TEXT("rocket"), TEXT("intake") }, { TEXT("handcannon"), TEXT("intake") }, { TEXT("sidearm"), TEXT("intake") } };
	for (const TPair<const TCHAR*, const TCHAR*>& Gun : Guns)
	{
		const TCHAR* Arch = Gun.Key;
		const FName Style(Gun.Value);
		const USOWeaponData* W = Tables->LoadArchetype(Arch);
		if (!TestNotNull(*FString::Printf(TEXT("%s data"), Arch), W))
		{
			continue;
		}
		TestEqual(*FString::Printf(TEXT("%s: reloads by %s"), Arch, Gun.Value), SOReload::GetStyle(Arch), Style);
		const FName Part = Style == TEXT("cell") ? FName(TEXT("mag")) : FName(TEXT("hatch"));
		const FSOWeaponPart* Found = W->Parts.FindByPredicate([Part](const FSOWeaponPart& P) { return P.Name == Part; });
		TestTrue(*FString::Printf(TEXT("%s: its %s is a part of its own"), Arch, *Part.ToString()), Found && !Found->Mesh.IsNull());
		int32 From = -1, To = -1;
		const TArray<FSOReloadSegment> Segs = SOReload::BuildReload(Arch, true, false, true, W->ReloadTime, 3, From, To);
		bool bGrips = false, bMoves = false, bSpare = false, bSeat = false, bCharge = false, bShown = false;
		for (const FSOReloadSegment& S : Segs)
		{
			if (const TArray<FSOKey>* Hand = S.Channels.Find(TEXT("hand")))
			{
				bGrips |= Hand->ContainsByPredicate([Part](const FSOKey& K) { return K.Anchor == Part; });
				bSpare |= Hand->ContainsByPredicate([](const FSOKey& K) { return K.Anchor == TEXT("spare"); });
			}
			bMoves |= S.Channels.Contains(Part);
			for (const FSOReloadEvent& E : S.Events)
			{
				bSeat |= E.Name == TEXT("seat");
				bCharge |= E.Name == TEXT("fx") && E.Arg == TEXT("charge");
				bShown |= E.Name == TEXT("fx") && (E.Arg == Style || (Style == TEXT("cell") && E.Arg == TEXT("cellpop"))) && E.Count > 50;
			}
		}
		if (Style != TEXT("intake"))   // (an intake's flap opens by itself: the hands stay on the gun)
		{
			TestTrue(*FString::Printf(TEXT("%s: the hand goes to its %s"), Arch, *Part.ToString()), bGrips);
		}
		TestTrue(*FString::Printf(TEXT("%s: its %s moves"), Arch, *Part.ToString()), bMoves);
		if (Style == TEXT("cell"))
		{
			TestTrue(*FString::Printf(TEXT("%s: a fresh cell is turned home"), Arch), bSpare);
		}
		TestTrue(*FString::Printf(TEXT("%s: the charge is restored"), Arch), bSeat);
		TestTrue(*FString::Printf(TEXT("%s: what it does is shown for a while"), Arch), bShown);
		TestTrue(*FString::Printf(TEXT("%s: it charges up as it closes"), Arch), bCharge);
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

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOPerksAreDataTest, "ShatteredOrbit.Loot.PerksAreData", SOTest::Flags)
bool FSOPerksAreDataTest::RunTest(const FString& Parameters)
{
	// What a perk does is its numbers in Data/game_data.json: the tables carry them, the gun reads them, and a perk
	// that only recombines them needs no code at all.
	USOLootTables* Tables = const_cast<USOLootTables*>(USOLootLibrary::GetTables());
	const TSharedPtr<FJsonObject> Data = SOTest::GameData();
	if (!TestNotNull(TEXT("DA_LootTables"), Tables) || !TestTrue(TEXT("Data/game_data.json"), Data.IsValid()))
	{
		return false;
	}
	TestFalse(TEXT("a perk with nothing in it does nothing"), FSOPerkInfo().DoesAnything());
	for (const TPair<FString, TSharedPtr<FJsonValue>>& Pair : Data->GetObjectField(TEXT("perks"))->Values)
	{
		const TSharedPtr<FJsonObject> J = Pair.Value->AsObject();
		const FSOPerkInfo* P = Tables->FindPerk(FName(Pair.Key));
		if (!TestNotNull(*FString::Printf(TEXT("perk %s"), *Pair.Key), P))
		{
			continue;
		}
		auto Same = [&](const TCHAR* Key, float Have, float IfAbsent)
		{
			double Want = IfAbsent;
			J->TryGetNumberField(Key, Want);
			TestEqual(*FString::Printf(TEXT("%s: %s is the data's (run the import with SO_IMPORT_ONLY=perks)"), *Pair.Key, Key), Have, static_cast<float>(Want), 0.0001f);
		};
		Same(TEXT("magazine"), P->Magazine, 1.0f);
		Same(TEXT("reload"), P->Reload, 1.0f);
		Same(TEXT("spread"), P->Spread, 1.0f);
		Same(TEXT("recoil"), P->Recoil, 1.0f);
		Same(TEXT("precision"), P->Precision, 1.0f);
		Same(TEXT("fireRateShieldDown"), P->FireRateShieldDown, 1.0f);
		Same(TEXT("killDamage"), P->KillDamage, 0.0f);
		Same(TEXT("killHeal"), P->KillHeal, 0.0f);
		Same(TEXT("precisionSplash"), P->PrecisionSplash, 0.0f);
		const bool bDoesSomething = P->DoesAnything();
		TestTrue(*FString::Printf(TEXT("%s does something"), *Pair.Key), bDoesSomething);
	}

	// a copy reads them
	const USOWeaponData* Rifle = Tables->LoadArchetype(TEXT("rifle"));
	if (!TestNotNull(TEXT("the rifle"), Rifle))
	{
		return false;
	}
	FRandomStream Rng(7);
	FSOWeaponInstance W = USOLootLibrary::MakeWeapon(TEXT("rifle"), 0, 10, Rng);
	W.Perks.Reset();
	const FSOWeaponStats Plain = USOLootLibrary::ComputeStatsFor(Rifle, W);
	W.Perks = { TEXT("overflow"), TEXT("quickdraw") };
	const FSOWeaponStats Two = USOLootLibrary::ComputeStatsFor(Rifle, W);
	const FSOPerkInfo* Overflow = Tables->FindPerk(TEXT("overflow"));
	const FSOPerkInfo* Quick = Tables->FindPerk(TEXT("quickdraw"));
	if (TestNotNull(TEXT("overflow"), Overflow) && TestNotNull(TEXT("quickdraw"), Quick))
	{
		TestEqual(TEXT("a bigger magazine by the data's number"), Two.Mag, FMath::RoundToInt(Plain.Mag * Overflow->Magazine));
		TestEqual(TEXT("and a faster reload by the other's, together"), Two.Reload, Plain.Reload * Quick->Reload, 0.0001f);
		TestEqual(TEXT("what neither touches is unchanged"), Two.Spread, Plain.Spread, 0.0001f);
	}

	// a perk that exists only as data: no code knows its name
	FSOPerkInfo Made;
	Made.Id = TEXT("test_data_only");
	Made.Magazine = 2.0f;
	Made.Spread = 0.5f;
	Made.KillHeal = 0.1f;
	Tables->Perks.Add(Made);
	W.Perks = { TEXT("test_data_only"), TEXT("vampire") };
	const FSOWeaponStats WithMade = USOLootLibrary::ComputeStatsFor(Rifle, W);
	const FSOPerkInfo* Siphon = Tables->FindPerk(TEXT("vampire"));
	TestEqual(TEXT("a perk made of data alone doubles the magazine"), WithMade.Mag, Plain.Mag * 2);
	TestEqual(TEXT("and halves the spread"), WithMade.Spread, Plain.Spread * 0.5f, 0.0001f);
	TestEqual(TEXT("and its share of health on a kill adds to another perk's"), WithMade.Perks.KillHeal, 0.1f + (Siphon ? Siphon->KillHeal : 0.0f), 0.0001f);
	Tables->Perks.RemoveAll([](const FSOPerkInfo& P) { return P.Id == TEXT("test_data_only"); });
	TestNull(TEXT("(taken out again)"), Tables->FindPerk(TEXT("test_data_only")));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSONewPerksTest, "ShatteredOrbit.Loot.NewPerks", SOTest::Flags)
bool FSONewPerksTest::RunTest(const FString& Parameters)
{
	// The perks added on 2026-11-13, through a real gun in a real world: each does what its line says, by its
	// numbers in the data.
	const USOLootTables* Tables = USOLootLibrary::GetTables();
	if (!TestNotNull(TEXT("loot tables"), Tables))
	{
		return false;
	}
	auto PerkOf = [&](const TCHAR* Id) { const FSOPerkInfo* P = Tables->FindPerk(Id); TestNotNull(*FString::Printf(TEXT("perk %s (run the import with SO_IMPORT_ONLY=perks)"), Id), P); return P ? *P : FSOPerkInfo(); };

	// a class's own perks stay with the class
	FRandomStream Rng(31);
	const TPair<const TCHAR*, const TCHAR*> Kinds[] = { { TEXT("rifle"), TEXT("kinetic") }, { TEXT("energy"), TEXT("energy") }, { TEXT("spitter"), TEXT("horror") } };
	for (const TPair<const TCHAR*, const TCHAR*>& Kind : Kinds)
	{
		int32 Wrong = 0, Own = 0;
		for (int32 i = 0; i < 300; ++i)
		{
			for (const FName& Id : USOLootLibrary::MakeWeapon(Kind.Key, 4, 10, Rng).Perks)
			{
				const FSOPerkInfo* P = Tables->FindPerk(Id);
				Wrong += P && P->Classes.Num() > 0 && !P->Classes.Contains(FName(Kind.Value));
				Own += P && P->Classes.Contains(FName(Kind.Value));
			}
		}
		TestEqual(*FString::Printf(TEXT("a %s gun never rolls another class's perk"), Kind.Value), Wrong, 0);
		TestTrue(*FString::Printf(TEXT("and a %s gun does roll its own class's (%d in 300 copies)"), Kind.Value, Own), Own > 0);
	}

	SOTest::FTestWorld W;
	W.AddBox(FVector(-4000, -4000, -100), FVector(4000, 4000, 0));
	W.AddBox(FVector(2500, -3000, 0), FVector(2600, 3000, 800)); // a wall every round ends on
	ASOCharacter* Player = W.SpawnCharacter(FVector(0, 0, 0));
	W.Run(0.3f);
	USOProjectileSubsystem* Rounds = W.World->GetSubsystem<USOProjectileSubsystem>();
	TArray<float> Fired;        // the damage each round that landed carried
	FGameplayTag LastStatus;
	const FDelegateHandle Handle = Rounds->OnHit.AddLambda([&](const FSOProjectile& Round, const FHitResult&, float)
	{
		Fired.Add(Round.Damage);
		LastStatus = Round.Status;
	});
	auto GunWith = [&](const TCHAR* Arch, std::initializer_list<FName> Perks)
	{
		FSOWeaponInstance Copy = USOLootLibrary::MakeWeapon(Arch, 0, 10, Rng);
		Copy.Perks = Perks;
		ASOWeapon* Gun = Player->EquipInstance(Copy);
		W.Run(0.4f);
		return Gun;
	};
	auto Shoot = [&](ASOWeapon* Gun)
	{
		Fired.Reset();
		Gun->StartFire();
		W.Step();
		Gun->StopFire();
		W.Run(0.4f);
		return Fired.Num() > 0 ? Fired[0] : -1.0f;
	};

	// Cold Bore: the first shot after a quiet spell, then the next
	{
		const FSOPerkInfo P = PerkOf(TEXT("cold_bore"));
		ASOWeapon* Gun = GunWith(TEXT("scout"), { TEXT("cold_bore") });
		if (TestNotNull(TEXT("scout rifle"), Gun))
		{
			W.Run(P.OpeningAfter + 0.3f);
			TestEqual(TEXT("cold bore: the first shot after the quiet hits harder"), Shoot(Gun), Gun->GetStats().Damage * P.OpeningDamage, 0.01f);
			TestEqual(TEXT("and the one straight after is an ordinary shot"), Shoot(Gun), Gun->GetStats().Damage, 0.01f);
		}
	}
	// Last Third: the rounds at the bottom of the magazine
	{
		const FSOPerkInfo P = PerkOf(TEXT("last_third"));
		ASOWeapon* Gun = GunWith(TEXT("scout"), { TEXT("last_third") });
		if (TestNotNull(TEXT("scout rifle"), Gun))
		{
			TestEqual(TEXT("last third: a full magazine's first round is ordinary"), Shoot(Gun), Gun->GetStats().Damage, 0.01f);
			Gun->SetAmmo(2, 50);
			TestEqual(TEXT("and a round from the bottom hits harder"), Shoot(Gun), Gun->GetStats().Damage * P.LowMagDamage, 0.01f);
		}
	}
	// Clinging Acid: the round carries the slow
	{
		const FSOPerkInfo P = PerkOf(TEXT("clinging_acid"));
		ASOWeapon* Gun = GunWith(TEXT("scout"), { TEXT("clinging_acid") });
		if (TestNotNull(TEXT("gun"), Gun))
		{
			Shoot(Gun);
			TestTrue(TEXT("clinging acid: what it hits is slowed"), LastStatus == SOTags::Status_Slow && P.HitSlow < 1.0f && P.HitSlowTime > 0.0f);
		}
	}
	// Match Grade, Slide Feed: straight from the gun
	{
		ASOWeapon* Gun = GunWith(TEXT("scout"), { TEXT("slide_feed"), TEXT("match_grade") });
		if (TestNotNull(TEXT("gun"), Gun))
		{
			TestTrue(TEXT("the gun knows it reloads on a slide and loses nothing with distance"), Gun->GetStats().Perks.bSlideReload && Gun->GetStats().Perks.bNoFalloff);
			Gun->SetAmmo(1, 40);
			const int32 In = Gun->RefillFromReserve();
			TestEqual(TEXT("slide feed: the magazine is filled"), Gun->GetMag(), Gun->GetStats().Mag);
			TestEqual(TEXT("from the reserve"), Gun->GetReserve(), 40 - In);
			Gun->SetAmmo(1, 2);
			Gun->RefillFromReserve();
			TestEqual(TEXT("and only with what the reserve has"), Gun->GetMag(), 3);
		}
	}
	// a kill: Spoils, Second Skin, Hot Hands
	{
		const FSOPerkInfo Spoils = PerkOf(TEXT("spoils")), Hot = PerkOf(TEXT("hot_hands"));
		ASOWeapon* Gun = GunWith(TEXT("scout"), { TEXT("spoils"), TEXT("second_skin"), TEXT("hot_hands") });
		ASOEnemy* Prey = SOTest::SpawnStalker(W, FVector(900, 0, 0), FRotator(0, 180, 0));
		if (TestNotNull(TEXT("gun"), Gun) && TestNotNull(TEXT("stalker"), Prey))
		{
			if (AController* Brain = Prey->GetController())
			{
				Brain->UnPossess();
				Brain->Destroy();
			}
			Prey->SetAlert(true);
			W.Run(0.3f);
			USOCombatStatics::ApplyDamage(Player, Prey, Prey->GetHealth() - 3.0f, false);
			const float FullShield = Player->GetShield();
			USOCombatStatics::ApplyDamage(nullptr, Player, 20.0f, false);
			Gun->SetAmmo(2, 100);
			Shoot(Gun);
			if (TestTrue(TEXT("the shot killed it"), Prey->IsDead()))
			{
				TestEqual(TEXT("spoils: a fifth of the magazine came back from the reserve"), Gun->GetMag(), 1 + FMath::RoundToInt(Gun->GetStats().Mag * Spoils.KillMagazine));
				W.Run(0.6f);
				TestTrue(TEXT("second skin: the shield is refilling without the wait"), Player->GetShield() > FullShield - 20.0f + 1.0f);
				Gun->SetAmmo(0, 100);
				Gun->StartReload();
				const float After = Gun->GetReloadDuration();
				Gun->CancelReload();
				W.Run(Hot.KillReloadTime + 1.0f);
				Gun->SetAmmo(0, 100);
				Gun->StartReload();
				const float Later = Gun->GetReloadDuration();
				AddInfo(FString::Printf(TEXT("reload: %.2f s just after a kill, %.2f s later"), After, Later));
				TestTrue(TEXT("hot hands: a reload just after a kill is faster by the data's share"), Later > 0.2f && FMath::IsNearlyEqual(After, Later * Hot.KillReload, Later * 0.08f));
			}
		}
	}
	// Soft Nose / Overcharged Cell, at the round: harder on flesh or on shields
	{
		const FSOPerkInfo Soft = PerkOf(TEXT("soft_nose")), Cell = PerkOf(TEXT("overcharged_cell"));
		TestTrue(TEXT("soft nose trades shields for flesh"), Soft.HealthDamage > 1.0f && Soft.ShieldDamage < 1.0f);
		TestTrue(TEXT("an overcharged cell is harder on shields"), Cell.ShieldDamage > 1.0f);
		ASOEnemy* Shooter = SOTest::SpawnStalker(W, FVector(-900, 600, 0), FRotator::ZeroRotator);
		if (AController* Brain = Shooter ? Shooter->GetController() : nullptr)
		{
			Brain->UnPossess(); // (it only lends its name to the rounds: left its brain, it would come and claw the player)
			Brain->Destroy();
		}
		W.Run(12.0f); // (the shield whole again)
		if (TestNotNull(TEXT("shooter"), Shooter) && TestTrue(TEXT("the shield is up"), Player->GetShield() > 10.0f))
		{
			auto Hit = [&](float Shield, float Health)
			{
				FSOProjectile Round;
				Round.Origin = Round.Position = Player->GetActorLocation() + FVector(-300, 0, 20);
				Round.Velocity = FVector(60000, 0, 0);
				Round.Gravity = 0.0f;
				Round.Damage = 10.0f;
				Round.CritMultiplier = 1.0f;
				Round.ShieldScale = Shield;
				Round.HealthScale = Health;
				Round.Instigator = Shooter;
				const float Before = Player->GetHealth() + Player->GetShield();
				Rounds->Fire(Round);
				W.Run(0.2f);
				return Before - (Player->GetHealth() + Player->GetShield());
			};
			const float Worn = Player->GetAttributeScale(ESOAttribute::Plating);
			TestEqual(TEXT("on a shield, the shield's scale"), Hit(Soft.ShieldDamage, Soft.HealthDamage), 10.0f * Soft.ShieldDamage * Worn, 0.05f);
			USOCombatStatics::ApplyDamage(Shooter, Player, Player->GetShield() + 1.0f, false);
			TestEqual(TEXT("with the shield down, the flesh's"), Hit(Soft.ShieldDamage, Soft.HealthDamage), 10.0f * Soft.HealthDamage * Worn, 0.05f);
		}
	}
	Rounds->OnHit.Remove(Handle);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOOneColourASetTest, "ShatteredOrbit.Loot.OneColourASet", SOTest::Flags)
bool FSOOneColourASetTest::RunTest(const FString& Parameters)
{
	// The owner, 2026-11-15: "all guns in the set need to have the same color pallet and shoot the same color". A set
	// (its SetId), or for a gun of no set its class's family (light, kinetic, horror): one colour fired, one light on it.
	const USOLootTables* Tables = USOLootLibrary::GetTables();
	if (!TestNotNull(TEXT("loot tables"), Tables))
	{
		return false;
	}
	TMap<FString, TPair<FLinearColor, FLinearColor>> Seen;
	TMap<FString, FString> First;
	for (const FSOArchetypeEntry& Entry : Tables->Archetypes)
	{
		const USOWeaponData* Data = Tables->LoadArchetype(Entry.Id);
		if (!Data)
		{
			continue;
		}
		const FString Family = !Data->SetId.IsNone() ? Data->SetId.ToString() : FString::Printf(TEXT("class %d"), static_cast<int32>(Data->WeaponClass));
		TestTrue(*FString::Printf(TEXT("%s has its set's light"), *Entry.Id.ToString()), Data->GlowColor.A > 0.0f);
		if (const TPair<FLinearColor, FLinearColor>* Was = Seen.Find(Family))
		{
			TestTrue(*FString::Printf(TEXT("%s fires the colour %s does (%s)"), *Entry.Id.ToString(), *First[Family], *Family), Was->Key.Equals(Data->TracerColor, 1e-3f));
			TestTrue(*FString::Printf(TEXT("%s has the light %s has (%s)"), *Entry.Id.ToString(), *First[Family], *Family), Was->Value.Equals(Data->GlowColor, 1e-3f));
		}
		else
		{
			Seen.Add(Family, TPair<FLinearColor, FLinearColor>(Data->TracerColor, Data->GlowColor));
			First.Add(Family, Entry.Id.ToString());
		}
	}
	TestTrue(TEXT("the sets were found"), Seen.Num() >= 4);
	return true;
}

// The Sarketh's guns never reload (the owner, 2026-11-16): the trigger at rest and the crystal cold (or vented), rounds
// condense from the reserve into it at the data's rate; the reload key and an empty trigger vent it.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOLootCondenseTest, "ShatteredOrbit.Weapon.SarkethGunsCondense", SOTest::Flags)
bool FSOLootCondenseTest::RunTest(const FString& Parameters)
{
	const USOLootTables* Tables = USOLootLibrary::GetTables();
	if (!TestNotNull(TEXT("DA_LootTables"), Tables))
	{
		return false;
	}
	int32 Sarketh = 0;
	for (const FSOArchetypeEntry& Entry : Tables->Archetypes)
	{
		const USOWeaponData* D = Tables->LoadArchetype(Entry.Id);
		if (D && D->SetId == TEXT("sarketh"))
		{
			++Sarketh;
			TestTrue(*FString::Printf(TEXT("%s condenses (\"refill\")"), *Entry.Id.ToString()), D->RefillTime > 0.0f && D->HeatPerShot > 0.0f);
		}
	}
	TestTrue(TEXT("the Sarketh set is there"), Sarketh >= 7);

	SOTest::FTestWorld W;
	W.AddBox(FVector(-3000, -3000, -100), FVector(3000, 3000, 0));
	ASOCharacter* Player = W.SpawnCharacter(FVector(0, 0, 0));
	FRandomStream Rng(5);
	ASOWeapon* Gun = Player->EquipInstance(USOLootLibrary::MakeWeapon(TEXT("skr_rifle"), 0, 10, Rng));
	if (!TestNotNull(TEXT("Ember Oath"), Gun))
	{
		return false;
	}
	W.Run(0.3f);
	const USOWeaponData* D = Gun->GetData();
	const int32 Full = Gun->GetStats().Mag;
	Gun->SetAmmo(Full, 100);
	Gun->StartFire();
	W.Run(0.6f);
	const int32 AfterBurst = Gun->GetMag();
	TestTrue(TEXT("firing spends rounds and heats the crystal"), AfterBurst < Full && Gun->GetHeat() > 0.0f);
	W.Run(0.3f);
	TestTrue(TEXT("nothing condenses while the trigger is held"), Gun->GetMag() <= AfterBurst);
	Gun->StopFire();
	W.Run(0.15f);
	TestEqual(TEXT("nothing condenses while the crystal is hot"), Gun->GetReserve(), 100);
	// the reload key vents it: no reload, the heat runs out, then the rounds come
	Gun->StartReload();
	TestFalse(TEXT("no reload"), Gun->IsReloading());
	TestTrue(TEXT("the key vents it"), Gun->IsVenting());
	for (int32 i = 0; i < 400 && Gun->IsVenting(); ++i)
	{
		W.Step();
	}
	TestEqual(TEXT("cold after the vent"), Gun->GetHeat(), 0.0f, 0.001f);
	Gun->SetAmmo(0, 100);                                   // (from empty: the refill's pace is measured)
	const int32 Before = Gun->GetMag();
	W.Run(D->RefillTime * 0.5f);
	const int32 Half = Gun->GetMag();
	TestTrue(FString::Printf(TEXT("rounds condense slowly (%d -> %d in half the refill time)"), Before, Half), Half > Before && Half < Full);
	TestEqual(TEXT("from the reserve"), Gun->GetReserve(), 100 - (Half - Before));
	W.Run(D->RefillTime);
	TestEqual(TEXT("full again"), Gun->GetMag(), Full);
	// empty, the trigger vents it, and it fills from what the reserve has
	Gun->SetAmmo(0, 5);
	Gun->StartFire();
	W.Step();
	Gun->StopFire();
	W.Run(D->VentTime + D->HeatCoolDelay + 1.0f / FMath::Max(D->HeatCool, 0.1f) + D->RefillTime + 0.5f);
	TestEqual(TEXT("only what the reserve had"), Gun->GetMag(), 5);
	TestEqual(TEXT("the reserve is spent"), Gun->GetReserve(), 0);
	return true;
}

#endif
