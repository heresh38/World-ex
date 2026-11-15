// Phase 1 of Project Orion: state tags, the one path for health, conditions, and abilities with cooldowns, charges and
// an ultimate cost. All single-machine (the server's side): the two-player checks are done by hand.

#include "SOTestWorld.h"

#if WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR

#include "Abilities/SOAbilitySet.h"
#include "Abilities/SOAbility_Strike.h"
#include "Abilities/SOAbility_Kit.h"
#include "SOAbilitySystemComponent.h"
#include "SOAltered.h"
#include "SOCharacterMovementComponent.h"
#include "SOCombatStatics.h"
#include "SOCombatTypes.h"
#include "SOEnemy.h"
#include "SOOperation.h"
#include "SODifficulty.h"
#include "SOSpecies.h"
#include "HAL/FileManager.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "SOInventoryComponent.h"
#include "SOProfileStore.h"
#include "GameFramework/PlayerController.h"
#include "SOPlayerState.h"

namespace SOTest
{
	ASOEnemy* SpawnStalker(FTestWorld& W, const FVector& Feet, const FRotator& Rotation);

	USOAbilitySet* MakeKit(TFunctionRef<void(USOAbilitySet&)> Fill)
	{
		USOAbilitySet* Kit = NewObject<USOAbilitySet>(GetTransientPackage());
		Kit->KitId = TEXT("test");
		Fill(*Kit);
		return Kit;
	}

	FSOAbilityGrant Strike(ESOAbilitySlot Slot)
	{
		FSOAbilityGrant G;
		G.Slot = Slot;
		G.Ability = USOAbility_Strike::StaticClass();
		G.Cooldown = 2.0f;
		G.Charges = 1;
		G.Damage = 50.0f;
		G.Range = 250.0f;
		G.Angle = 60.0f;
		return G;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOStateTagsTest, "ShatteredOrbit.Ability.StateTags", SOTest::Flags)
bool FSOStateTagsTest::RunTest(const FString& Parameters)
{
	SOTest::FTestWorld W;
	W.AddBox(FVector(-2000, -2000, -100), FVector(2000, 2000, 0));
	ASOCharacter* Player = W.SpawnCharacter(FVector(0, 0, 0));
	W.Run(0.3f);
	TestFalse(TEXT("alive: no dead tag"), Player->HasStatus(SOTags::State_Dead));
	TestFalse(TEXT("not aiming"), Player->HasStatus(SOTags::State_Aiming));

	// The server learns a joined player's aim from the movement's flag (it arrives with every move), not from input.
	Player->GetSOMovement()->SetWantsToAim(true);
	W.Run(0.1f);
	TestTrue(TEXT("aim flag from the movement puts the character on the sights"), Player->IsAimingDownSights());
	TestTrue(TEXT("aiming tag"), Player->HasStatus(SOTags::State_Aiming));
	const float Aimed = Player->GetSpreadScale();
	Player->GetSOMovement()->SetWantsToAim(false);
	W.Run(0.6f);
	TestFalse(TEXT("aiming tag cleared"), Player->HasStatus(SOTags::State_Aiming));
	TestTrue(TEXT("the spread on the sights is tighter than at the hip"), Aimed < Player->GetSpreadScale());

	USOCombatStatics::ApplyDamage(nullptr, Player, 1000.0f, false);
	TestTrue(TEXT("dead tag"), Player->HasStatus(SOTags::State_Dead));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOHealEffectTest, "ShatteredOrbit.Combat.HealAndRegenAreEffects", SOTest::Flags)
bool FSOHealEffectTest::RunTest(const FString& Parameters)
{
	SOTest::FTestWorld W;
	W.AddBox(FVector(-2000, -2000, -100), FVector(2000, 2000, 0));
	ASOCharacter* Player = W.SpawnCharacter(FVector(0, 0, 0));
	W.Run(0.1f);
	TestEqual(TEXT("the damage that went in is what ApplyDamage returns"), USOCombatStatics::ApplyDamage(nullptr, Player, 80.0f, false), 80.0f);
	TestEqual(TEXT("health after 80 (50 on the shield)"), Player->GetHealth(), 70.0f);
	Player->Heal(20.0f);
	TestEqual(TEXT("healed 20"), Player->GetHealth(), 90.0f);
	Player->Heal(500.0f);
	TestEqual(TEXT("a heal stops at the maximum"), Player->GetHealth(), 100.0f);

	// the shield refills as an effect: none while the delay runs, one while it fills, none once it is full
	USOAbilitySystemComponent* ASC = Player->GetSOAbilitySystem();
	TestEqual(TEXT("no effect during the delay"), ASC->GetNumActiveGameplayEffects(), 0);
	W.Run(ASC->ShieldRegenDelay + 0.5f);
	TestEqual(TEXT("the refill is an active effect"), ASC->GetNumActiveGameplayEffects(), 1);
	TestTrue(TEXT("shield filling"), Player->GetShield() > 5.0f && Player->GetShield() < 50.0f);
	W.Run(3.0f);
	TestEqual(TEXT("shield full"), Player->GetShield(), 50.0f);
	TestEqual(TEXT("the refill is taken off when full"), ASC->GetNumActiveGameplayEffects(), 0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOStatusTest, "ShatteredOrbit.Status.BurnSlowStagger", SOTest::Flags)
bool FSOStatusTest::RunTest(const FString& Parameters)
{
	SOTest::FTestWorld W;
	W.AddBox(FVector(-4000, -4000, -100), FVector(4000, 4000, 0));
	ASOEnemy* Stalker = SOTest::SpawnStalker(W, FVector(0, 0, 0), FRotator::ZeroRotator);
	Stalker->SetAlert(true); // no ambush bonus: plain numbers
	W.Run(0.1f);
	const float Full = Stalker->GetHealth();

	// burn: the total over the duration, in half-second ticks, through the damage gate
	TestTrue(TEXT("burn applied"), USOCombatStatics::ApplyStatus(nullptr, Stalker, SOTags::Status_Burn, 3.0f, 60.0f));
	TestTrue(TEXT("burning"), Stalker->HasStatus(SOTags::Status_Burn));
	W.Run(1.1f);
	TestEqual(TEXT("two ticks in after a second"), Stalker->GetHealth(), Full - 20.0f, 0.5f);
	W.Run(2.4f);
	TestEqual(TEXT("the whole burn over its duration"), Stalker->GetHealth(), Full - 60.0f, 0.5f);
	TestFalse(TEXT("burn over"), Stalker->HasStatus(SOTags::Status_Burn));

	// slow: on a creature and on a player, gone when it ends
	Stalker->SetRunning(true);
	const float RunSpeed = Stalker->GetCharacterMovement()->MaxWalkSpeed;
	TestTrue(TEXT("slow applied"), USOCombatStatics::ApplyStatus(nullptr, Stalker, SOTags::Status_Slow, 1.0f, 0.5f));
	TestEqual(TEXT("creature at half speed"), Stalker->GetCharacterMovement()->MaxWalkSpeed, RunSpeed * 0.5f, 1.0f);
	W.Run(1.2f);
	Stalker->SetRunning(true); // its brain may have slowed it to a walk meanwhile
	TestEqual(TEXT("creature back to speed"), Stalker->GetCharacterMovement()->MaxWalkSpeed, RunSpeed, 1.0f);

	ASOCharacter* Player = W.SpawnCharacter(FVector(3000, 0, 0));
	W.Run(0.3f);
	const float Walk = Player->GetSOMovement()->GetMaxSpeed();
	USOCombatStatics::ApplyStatus(nullptr, Player, SOTags::Status_Slow, 1.0f, 0.6f);
	TestEqual(TEXT("player slowed"), Player->GetSOMovement()->GetMaxSpeed(), Walk * 0.6f, 1.0f);
	W.Run(1.2f);
	TestEqual(TEXT("player back to speed"), Player->GetSOMovement()->GetMaxSpeed(), Walk, 1.0f);

	// stagger: a marker for a while; the dead take no conditions; a boss resists
	TestTrue(TEXT("stagger applied"), USOCombatStatics::ApplyStatus(nullptr, Stalker, SOTags::Status_Stagger, 0.5f));
	TestTrue(TEXT("staggered"), Stalker->HasStatus(SOTags::Status_Stagger));
	W.Run(0.7f);
	TestFalse(TEXT("stagger over"), Stalker->HasStatus(SOTags::Status_Stagger));
	TestTrue(TEXT("the Colossus resists a stagger"), GetDefault<ASOColossus>()->ResistsStatus(SOTags::Status_Stagger));
	USOCombatStatics::ApplyDamage(nullptr, Stalker, 5000.0f, false);
	TestFalse(TEXT("no condition on the dead"), USOCombatStatics::ApplyStatus(nullptr, Stalker, SOTags::Status_Slow, 1.0f, 0.5f));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOAbilityStrikeTest, "ShatteredOrbit.Ability.StrikeCooldownAndCharges", SOTest::Flags)
bool FSOAbilityStrikeTest::RunTest(const FString& Parameters)
{
	SOTest::FTestWorld W;
	W.AddBox(FVector(-2000, -2000, -100), FVector(2000, 2000, 0));
	ASOCharacter* Player = W.SpawnCharacter(FVector(0, 0, 0));
	ASOEnemy* Stalker = SOTest::SpawnStalker(W, FVector(190, 0, 0), FRotator(0, 180, 0));
	ASOEnemy* Behind = SOTest::SpawnStalker(W, FVector(-190, 0, 0), FRotator::ZeroRotator);
	Stalker->SetAlert(true);
	Behind->SetAlert(true);
	W.Run(0.1f);
	const float Full = Stalker->GetHealth();

	TestFalse(TEXT("no kit: nothing in the slot"), Player->ActivateSlot(ESOAbilitySlot::Melee));
	USOAbilitySet* Kit = SOTest::MakeKit([](USOAbilitySet& K)
	{
		FSOAbilityGrant G = SOTest::Strike(ESOAbilitySlot::Melee);
		G.Charges = 2;
		G.Duration = 0.6f;
		K.Abilities.Add(G);
	});
	Player->GrantAbilitySet(Kit);

	int32 Charges = 0, Max = 0;
	float Left = 0.0f, Cooldown = 0.0f;
	TestTrue(TEXT("slot filled"), Player->GetAbilityState(ESOAbilitySlot::Melee, Charges, Max, Left, Cooldown));
	TestEqual(TEXT("both charges ready"), Charges, 2);
	TestFalse(TEXT("another slot is empty"), Player->GetAbilityState(ESOAbilitySlot::Grenade, Charges, Max, Left, Cooldown));

	TestTrue(TEXT("first strike"), Player->ActivateSlot(ESOAbilitySlot::Melee));
	TestEqual(TEXT("the one in front takes the blow"), Stalker->GetHealth(), Full - 50.0f, 0.5f);
	TestEqual(TEXT("the one behind does not"), Behind->GetHealth(), Behind->GetMaxHealth());
	TestTrue(TEXT("and is staggered"), Stalker->HasStatus(SOTags::Status_Stagger));
	Player->GetAbilityState(ESOAbilitySlot::Melee, Charges, Max, Left, Cooldown);
	TestEqual(TEXT("one charge left"), Charges, 1);
	TestTrue(TEXT("the spent one is on its way back"), Left > 1.5f && Left <= 2.0f);

	TestTrue(TEXT("second strike"), Player->ActivateSlot(ESOAbilitySlot::Melee));
	TestFalse(TEXT("no third: both charges spent"), Player->ActivateSlot(ESOAbilitySlot::Melee));
	Player->GetAbilityState(ESOAbilitySlot::Melee, Charges, Max, Left, Cooldown);
	TestEqual(TEXT("no charges"), Charges, 0);

	W.Run(2.2f);
	Player->GetAbilityState(ESOAbilitySlot::Melee, Charges, Max, Left, Cooldown);
	TestEqual(TEXT("both back after the cooldown"), Charges, 2);
	TestEqual(TEXT("nothing left to wait for"), Left, 0.0f);

	// blocked by state: in a stagger, and dead
	USOCombatStatics::ApplyStatus(nullptr, Player, SOTags::Status_Stagger, 0.5f);
	TestFalse(TEXT("not while staggered"), Player->ActivateSlot(ESOAbilitySlot::Melee));
	W.Run(0.7f);
	TestTrue(TEXT("again once it has passed"), Player->ActivateSlot(ESOAbilitySlot::Melee));
	USOCombatStatics::ApplyDamage(nullptr, Player, 1000.0f, false);
	TestFalse(TEXT("not while dead"), Player->ActivateSlot(ESOAbilitySlot::Melee));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOAbilityUltimateTest, "ShatteredOrbit.Ability.UltimateChargesAndCosts", SOTest::Flags)
bool FSOAbilityUltimateTest::RunTest(const FString& Parameters)
{
	SOTest::FTestWorld W;
	W.AddBox(FVector(-2000, -2000, -100), FVector(2000, 2000, 0));
	ASOCharacter* Player = W.SpawnCharacter(FVector(0, 0, 0));
	ASOEnemy* Stalker = SOTest::SpawnStalker(W, FVector(190, 0, 0), FRotator(0, 180, 0));
	Stalker->SetAlert(true);
	W.Run(0.1f);
	USOAbilitySet* Kit = SOTest::MakeKit([](USOAbilitySet& K)
	{
		FSOAbilityGrant Melee = SOTest::Strike(ESOAbilitySlot::Melee);
		Melee.Cooldown = 0.0f;
		K.Abilities.Add(Melee);
		FSOAbilityGrant Ultimate = SOTest::Strike(ESOAbilitySlot::Ultimate);
		Ultimate.Cooldown = 0.0f;
		Ultimate.UltimateCost = 100.0f;
		Ultimate.Damage = 10.0f;
		K.Abilities.Add(Ultimate);
		K.UltimatePerDamage = 1.0f;
		K.UltimatePerSecond = 10.0f;
	});
	Player->GrantAbilitySet(Kit);
	TestEqual(TEXT("starts empty"), Player->GetUltimate(), 0.0f);
	TestFalse(TEXT("no ultimate without the charge"), Player->ActivateSlot(ESOAbilitySlot::Ultimate));

	TestTrue(TEXT("a strike"), Player->ActivateSlot(ESOAbilitySlot::Melee));
	TestEqual(TEXT("damage dealt charges it (1 per point)"), Player->GetUltimate(), 50.0f, 0.5f);
	W.Run(2.0f);
	TestEqual(TEXT("and so does time (10 a second)"), Player->GetUltimate(), 70.0f, 2.0f);

	Player->AddUltimate(500.0f);
	TestEqual(TEXT("stops at the maximum"), Player->GetUltimate(), 100.0f);
	TestTrue(TEXT("the ultimate"), Player->ActivateSlot(ESOAbilitySlot::Ultimate));
	TestTrue(TEXT("spends the whole charge (less what its own blow earned)"), Player->GetUltimate() <= 10.5f);
	TestFalse(TEXT("not twice"), Player->ActivateSlot(ESOAbilitySlot::Ultimate));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOKitFromDataTest, "ShatteredOrbit.Ability.KitFromDataOnPossess", SOTest::Flags)
bool FSOKitFromDataTest::RunTest(const FString& Parameters)
{
	// the imported kit (Data/game_data.json "kits" -> /Game/Abilities/DA_Kit_Vanguard)
	USOAbilitySet* Vanguard = USOAbilitySet::Load(TEXT("vanguard"));
	if (!TestNotNull(TEXT("DA_Kit_Vanguard (run the import with SO_IMPORT_ONLY=kits)"), Vanguard))
	{
		return false;
	}
	const FSOAbilityGrant* Melee = Vanguard->Find(ESOAbilitySlot::Melee);
	if (!TestNotNull(TEXT("the kit has a melee"), Melee))
	{
		return false;
	}
	TestTrue(TEXT("its class is the strike"), Melee->Ability == USOAbility_Strike::StaticClass());
	TestTrue(TEXT("its numbers came from the data"), Melee->Damage > 0.0f && Melee->Range > 0.0f && Melee->Cooldown > 0.0f);

	// a player who takes a body gets the kit; the ultimate's charge goes with the player to the next body
	SOTest::FTestWorld W;
	W.AddBox(FVector(-2000, -2000, -100), FVector(2000, 2000, 0));
	APlayerController* PC = W.World->SpawnActor<APlayerController>();
	PC->SetAsLocalPlayerController(); // a controller made by hand has no local player: say so, or its abilities wait for a client
	ASOPlayerState* PS = W.World->SpawnActor<ASOPlayerState>();
	PC->PlayerState = PS;
	ASOCharacter* First = W.SpawnCharacter(FVector(0, 0, 0));
	PC->Possess(First);
	W.Run(0.2f);
	TestTrue(TEXT("the body has the player's kit"), First->GetAbilitySet() == Vanguard);
	int32 Charges = 0, Max = 0;
	float Left = 0.0f, Cooldown = 0.0f;
	TestTrue(TEXT("and its melee is ready"), First->GetAbilityState(ESOAbilitySlot::Melee, Charges, Max, Left, Cooldown) && Charges == Max);
	TestTrue(TEXT("a strike at nothing still spends the charge"), First->ActivateSlot(ESOAbilitySlot::Melee));
	First->GetAbilityState(ESOAbilitySlot::Melee, Charges, Max, Left, Cooldown);
	TestEqual(TEXT("the charge is spent"), Charges, Max - 1);
	First->AddUltimate(40.0f);
	USOCombatStatics::ApplyDamage(nullptr, First, 1000.0f, false);
	TestTrue(TEXT("dead"), First->IsDead());

	PC->UnPossess();
	ASOCharacter* Second = W.SpawnCharacter(FVector(400, 0, 0));
	PC->Possess(Second);
	W.Run(0.2f);
	TestTrue(TEXT("the next body has the kit too"), Second->GetAbilitySet() == Vanguard);
	TestTrue(TEXT("the charge carried over"), Second->GetUltimate() >= 39.5f);
	Second->GetAbilityState(ESOAbilitySlot::Melee, Charges, Max, Left, Cooldown);
	TestEqual(TEXT("a new body's cooldowns start over"), Charges, Max);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOVanguardKitTest, "ShatteredOrbit.Ability.VanguardKit", SOTest::Flags)
bool FSOVanguardKitTest::RunTest(const FString& Parameters)
{
	// The first kit as the data describes it, used by a player with a controller: the thrown charge, the brace, the slam.
	USOAbilitySet* Vanguard = USOAbilitySet::Load(TEXT("vanguard"));
	if (!TestNotNull(TEXT("DA_Kit_Vanguard"), Vanguard))
	{
		return false;
	}
	for (const ESOAbilitySlot Slot : { ESOAbilitySlot::Grenade, ESOAbilitySlot::Melee, ESOAbilitySlot::Class, ESOAbilitySlot::Ultimate })
	{
		const FSOAbilityGrant* Grant = Vanguard->Find(Slot);
		TestTrue(FString::Printf(TEXT("slot %d filled with a class"), static_cast<int32>(Slot)), Grant && Grant->Ability);
	}
	const FSOAbilityGrant* Charge = Vanguard->Find(ESOAbilitySlot::Grenade);
	const FSOAbilityGrant* Brace = Vanguard->Find(ESOAbilitySlot::Class);
	const FSOAbilityGrant* Slam = Vanguard->Find(ESOAbilitySlot::Ultimate);
	if (!Charge || !Brace || !Slam)
	{
		return false;
	}

	SOTest::FTestWorld W;
	W.AddBox(FVector(-6000, -6000, -100), FVector(6000, 6000, 0));
	APlayerController* PC = W.World->SpawnActor<APlayerController>();
	PC->SetAsLocalPlayerController(); // a controller made by hand has no local player: say so, or its abilities wait for a client
	PC->PlayerState = W.World->SpawnActor<ASOPlayerState>();
	ASOCharacter* Player = W.SpawnCharacter(FVector(0, 0, 0));
	PC->Possess(Player);
	PC->SetControlRotation(FRotator::ZeroRotator);
	W.Run(0.3f);

	// the thrown charge: lands where its arc says, hurts and slows what is near, leaves the far one alone
	const float Speed = Charge->Force;
	const float Up = Speed * 0.18f, Height = 150.0f;
	const float Flight = (Up + FMath::Sqrt(Up * Up + 2.0f * 980.0f * Height)) / 980.0f;
	const float Lands = Speed * Flight;
	ASOEnemy* Near = SOTest::SpawnStalker(W, FVector(Lands - 150.0f, 160.0f, 0), FRotator(0, 180, 0));
	ASOEnemy* Far = SOTest::SpawnStalker(W, FVector(Lands + Charge->Radius + 900.0f, 0, 0), FRotator(0, 180, 0));
	Near->SetAlert(true);
	Far->SetAlert(true);
	for (ASOEnemy* Still : { Near, Far })
	{
		// (this is about the charge, not about them: one with a brain leaps aside when a player's aim is on it)
		if (AController* Brain = Still->GetController())
		{
			Brain->UnPossess();
			Brain->Destroy();
		}
	}
	TestTrue(TEXT("charge thrown"), Player->ActivateSlot(ESOAbilitySlot::Grenade));
	int32 Charges = 0, Max = 0;
	float Left = 0.0f, Cooldown = 0.0f;
	Player->GetAbilityState(ESOAbilitySlot::Grenade, Charges, Max, Left, Cooldown);
	TestEqual(TEXT("one of its charges spent"), Charges, Max - 1);
	W.Run(Charge->WindUp + Flight + 0.4f); // it leaves the hand after the wind-up
	TestTrue(TEXT("the one near the burst is hurt"), Near->GetHealth() < Near->GetMaxHealth() - 20.0f);
	TestTrue(TEXT("and slowed"), Near->HasStatus(SOTags::Status_Slow));
	TestEqual(TEXT("the one well outside the radius is not"), Far->GetHealth(), Far->GetMaxHealth());

	// braced: a share of all damage, no stagger, then over
	TestTrue(TEXT("brace"), Player->ActivateSlot(ESOAbilitySlot::Class));
	TestTrue(TEXT("guarded"), Player->HasStatus(SOTags::Status_Guard));
	// (what the player wears counts too: its plating takes its own share first)
	const float Worn = Player->GetAttributeScale(ESOAttribute::Plating);
	TestEqual(TEXT("takes the guard's share of a hit"), USOCombatStatics::ApplyDamage(nullptr, Player, 40.0f, false), 40.0f * Brace->Magnitude * Worn, 0.1f);
	TestFalse(TEXT("cannot be staggered while braced"), USOCombatStatics::ApplyStatus(nullptr, Player, SOTags::Status_Stagger, 1.0f));
	W.Run(Brace->Duration + 0.3f);
	TestFalse(TEXT("the brace ends"), Player->HasStatus(SOTags::Status_Guard));
	TestEqual(TEXT("and hits are whole again"), USOCombatStatics::ApplyDamage(nullptr, Player, 10.0f, false), 10.0f * Worn, 0.001f);

	// the slam: needs the full charge, hits all round
	TestFalse(TEXT("no slam without the charge"), Player->ActivateSlot(ESOAbilitySlot::Ultimate));
	ASOEnemy* Behind = SOTest::SpawnStalker(W, FVector(-Slam->Range * 0.6f, 0, 0), FRotator::ZeroRotator);
	Behind->SetAlert(true);
	W.Run(0.1f);
	Player->AddUltimate(100.0f);
	TestTrue(TEXT("slam"), Player->ActivateSlot(ESOAbilitySlot::Ultimate));
	TestTrue(TEXT("the charge is paid for as the wind-up begins"), Player->GetUltimate() < 50.0f);
	W.Run(Slam->WindUp + 0.1f); // it lands after the wind-up
	TestTrue(TEXT("it reaches the one behind"), Behind->IsDead() || Behind->GetHealth() < Behind->GetMaxHealth() - 100.0f);
	TestTrue(TEXT("the charge is spent"), Player->GetUltimate() < 50.0f);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOProfileStoreTest, "ShatteredOrbit.Profile.SafeWriteAndMigrate", SOTest::Flags)
bool FSOProfileStoreTest::RunTest(const FString& Parameters)
{
	// The profile store's file handling, on a file of the test's own (never the player's save).
	const FString Path = FPaths::ProjectSavedDir() / TEXT("Tests") / TEXT("profile_store_test.sav");
	IFileManager& Files = IFileManager::Get();
	for (const TCHAR* Ext : { TEXT(""), TEXT(".bak"), TEXT(".tmp") })
	{
		Files.Delete(*(Path + Ext), false, true, true);
	}
	auto Bytes = [](int32 Version, int32 Credits)
	{
		USOSaveGame* Save = NewObject<USOSaveGame>();
		Save->Version = Version;
		Save->Credits = Credits;
		if (Version < 2)
		{
			Save->Body = TEXT("nobody"); // what an old file might hold where the body is now
		}
		TArray<uint8> Out;
		UGameplayStatics::SaveGameToMemory(Save, Out);
		return Out;
	};
	TestNull(TEXT("nothing saved yet"), USOProfileStore::LoadFile(Path));

	// a save from before the store (the engine's bare bytes, version 1) loads and is brought to the current version
	TestTrue(TEXT("first write"), USOProfileStore::WriteSafely(Path, Bytes(1, 777)));
	USOSaveGame* Old = USOProfileStore::LoadFile(Path);
	if (TestNotNull(TEXT("a bare version 1 file loads"), Old))
	{
		TestEqual(TEXT("migrated to the current version"), Old->Version, USOSaveGame::CurrentVersion);
		TestEqual(TEXT("what it held is kept"), Old->Credits, 777);
		TestEqual(TEXT("a version 1 file gets the default body"), Old->Body, FName(TEXT("male")));
	}

	// a second, sealed write keeps the one before as the backup, and leaves no temporary file
	const TArray<uint8> Sealed = USOProfileStore::Seal(Bytes(USOSaveGame::CurrentVersion, 888));
	TestTrue(TEXT("second write"), USOProfileStore::WriteSafely(Path, Sealed));
	TestTrue(TEXT("backup kept"), Files.FileExists(*(Path + TEXT(".bak"))));
	TestFalse(TEXT("no temporary file left"), Files.FileExists(*(Path + TEXT(".tmp"))));
	USOSaveGame* New = USOProfileStore::LoadFile(Path);
	TestTrue(TEXT("the latest is what loads"), New && New->Credits == 888);

	// a file that is not a save, and a sealed one cut short, both fall back to the backup (never to the engine's reader)
	FFileHelper::SaveStringToFile(TEXT("not a save"), *Path);
	USOSaveGame* Rescued = USOProfileStore::LoadFile(Path);
	TestTrue(TEXT("a file that is not a save falls back to the backup"), Rescued && Rescued->Credits == 777);
	TArray<uint8> Cut = Sealed;
	Cut.SetNum(Cut.Num() - 40);
	FFileHelper::SaveArrayToFile(Cut, *Path);
	Rescued = USOProfileStore::LoadFile(Path);
	TestTrue(TEXT("a file cut short falls back to the backup"), Rescued && Rescued->Credits == 777);
	TArray<uint8> Bent = Sealed;
	Bent[Bent.Num() / 2] ^= 0x5A;
	FFileHelper::SaveArrayToFile(Bent, *Path);
	Rescued = USOProfileStore::LoadFile(Path);
	TestTrue(TEXT("a file with a damaged byte falls back to the backup"), Rescued && Rescued->Credits == 777);

	// a file from a newer build is refused, not misread
	USOProfileStore::WriteSafely(Path, USOProfileStore::Seal(Bytes(USOSaveGame::CurrentVersion + 5, 999)));
	Files.Delete(*(Path + TEXT(".bak")), false, true, true);
	TestNull(TEXT("a newer build's file is not used"), USOProfileStore::LoadFile(Path));

	for (const TCHAR* Ext : { TEXT(""), TEXT(".bak"), TEXT(".tmp") })
	{
		Files.Delete(*(Path + Ext), false, true, true);
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOBulwarkSlamTest, "ShatteredOrbit.Altered.BulwarkSlamIsAnAbility", SOTest::Flags)
bool FSOBulwarkSlamTest::RunTest(const FString& Parameters)
{
	// A creature's own move on the same framework as a player's: the kit says what, a wind-up warns, a stagger stops it.
	SOTest::FTestWorld W;
	W.AddBox(FVector(-3000, -3000, -100), FVector(3000, 3000, 0));
	ASOCharacter* Player = W.SpawnCharacter(FVector(0, 0, 0));
	FActorSpawnParameters Params;
	Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	ASOBulwark* Bulwark = W.World->SpawnActor<ASOBulwark>(FVector(260, 0, 111), FRotator(0, 180, 0), Params);
	if (!TestNotNull(TEXT("bulwark"), Bulwark))
	{
		return false;
	}
	if (AController* Brain = Bulwark->GetController())
	{
		Brain->UnPossess(); // the test decides when it slams; its brain would fight the player meanwhile
		Brain->Destroy();
	}
	W.Run(0.2f);
	const FSOAbilityGrant* Slam = Bulwark->GetAbilitySet() ? Bulwark->GetAbilitySet()->Find(ESOAbilitySlot::Class) : nullptr;
	if (!TestNotNull(TEXT("the bulwark's kit has its slam (run the import with SO_IMPORT_ONLY=kits)"), Slam))
	{
		return false;
	}
	TestTrue(TEXT("the slam has a wind-up"), Slam->WindUp > 0.3f);

	const float Before = Player->GetShield() + Player->GetHealth();
	TestTrue(TEXT("slam begun"), Bulwark->ActivateSlot(ESOAbilitySlot::Class));
	TestTrue(TEXT("winding up"), Bulwark->IsAbilityActive(ESOAbilitySlot::Class));
	TestFalse(TEXT("not twice at once"), Bulwark->ActivateSlot(ESOAbilitySlot::Class));
	W.Run(Slam->WindUp * 0.5f);
	TestEqual(TEXT("nothing lands during the wind-up"), Player->GetShield() + Player->GetHealth(), Before);
	W.Run(Slam->WindUp * 0.5f + 0.1f);
	TestEqual(TEXT("then the blow lands for the kit's damage"), Player->GetShield() + Player->GetHealth(), Before - Slam->Damage, 0.5f);
	TestFalse(TEXT("and the move is over"), Bulwark->IsAbilityActive(ESOAbilitySlot::Class));
	TestFalse(TEXT("it has a cooldown"), Bulwark->ActivateSlot(ESOAbilitySlot::Class));

	// staggered in the wind-up: it does not land
	W.Run(Slam->Cooldown + 0.3f);
	const float Again = Player->GetShield() + Player->GetHealth();
	TestTrue(TEXT("second slam begun"), Bulwark->ActivateSlot(ESOAbilitySlot::Class));
	W.Run(0.1f);
	TestTrue(TEXT("staggered"), USOCombatStatics::ApplyStatus(nullptr, Bulwark, SOTags::Status_Stagger, 2.0f));
	W.Run(Slam->WindUp + 0.2f);
	TestTrue(TEXT("a stagger in the wind-up stops the blow"), Player->GetShield() + Player->GetHealth() >= Again);
	TestFalse(TEXT("the stopped move is over too"), Bulwark->IsAbilityActive(ESOAbilitySlot::Class));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOBulwarkBrainSlamTest, "ShatteredOrbit.Altered.BulwarkChoosesToSlam", SOTest::Flags)
bool FSOBulwarkBrainSlamTest::RunTest(const FString& Parameters)
{
	// With its own brain and a player in reach, the Bulwark uses the slam by itself, and the player feels it.
	SOTest::FTestWorld W;
	W.AddBox(FVector(-3000, -3000, -100), FVector(3000, 3000, 0));
	ASOCharacter* Player = W.SpawnCharacter(FVector(0, 0, 0));
	FSOSpawnOptions Options;
	Options.bHunter = true;
	Options.bOnNav = false;
	ASOEnemy* Bulwark = USOSpeciesLibrary::Spawn(W.World, TEXT("bulwark"), FVector(280, 0, 0), 180.0f, Options);
	if (!TestNotNull(TEXT("bulwark spawned"), Bulwark) || !TestNotNull(TEXT("with a brain"), Bulwark->GetController()))
	{
		return false;
	}
	int32 WindUpFrames = 0;
	W.Run(9.0f, [&]()
	{
		WindUpFrames += Bulwark->IsAbilityActive(ESOAbilitySlot::Class) ? 1 : 0;
		if (Player->GetHealth() < 60.0f)
		{
			Player->Heal(40.0f); // keep the target alive for the whole look
		}
	});
	const FSOAbilityGrant* Slam = Bulwark->GetAbilitySet() ? Bulwark->GetAbilitySet()->Find(ESOAbilitySlot::Class) : nullptr;
	TestNotNull(TEXT("it has the slam"), Slam);
	TestTrue(TEXT("it wound up a slam by itself"), WindUpFrames > 10);
	TestTrue(TEXT("and each wind-up lasted about the kit's time"), Slam && WindUpFrames < FMath::CeilToInt(3.0f * Slam->WindUp / SOTest::Dt));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOKitPassiveTest, "ShatteredOrbit.Ability.KitPassiveRule", SOTest::Flags)
bool FSOKitPassiveTest::RunTest(const FString& Parameters)
{
	// The frontline kit's passive rule: a kill at close range gives shield back at once; a far kill does not.
	SOTest::FTestWorld W;
	W.AddBox(FVector(-6000, -6000, -100), FVector(6000, 6000, 0));
	ASOCharacter* Player = W.SpawnCharacter(FVector(0, 0, 0));
	ASOEnemy* Close = SOTest::SpawnStalker(W, FVector(400, 0, 0), FRotator(0, 180, 0));
	ASOEnemy* Far = SOTest::SpawnStalker(W, FVector(3000, 0, 0), FRotator(0, 180, 0));
	W.Run(0.1f);
	USOAbilitySet* Kit = SOTest::MakeKit([](USOAbilitySet& K)
	{
		K.CloseRange = 1200.0f;
		K.CloseKillShield = 25.0f;
	});
	Player->GrantAbilitySet(Kit);
	USOCombatStatics::ApplyDamage(nullptr, Player, 50.0f, false);
	TestEqual(TEXT("shield knocked off"), Player->GetShield(), 0.0f);
	USOCombatStatics::ApplyDamage(Player, Far, 5000.0f, false);
	TestTrue(TEXT("the far one is dead"), Far->IsDead());
	TestEqual(TEXT("a far kill gives nothing"), Player->GetShield(), 0.0f);
	USOCombatStatics::ApplyDamage(Player, Close, 5000.0f, false);
	TestTrue(TEXT("the close one is dead"), Close->IsDead());
	TestEqual(TEXT("a close kill gives the kit's shield back at once"), Player->GetShield(), 25.0f);

	// and the imported kit carries its rule
	if (const USOAbilitySet* Vanguard = USOAbilitySet::Load(TEXT("vanguard")))
	{
		TestTrue(TEXT("the Vanguard's rule came with the data"), Vanguard->CloseKillShield > 0.0f && Vanguard->CloseRange > 0.0f && !Vanguard->PassiveName.IsEmpty());
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSODifficultyTest, "ShatteredOrbit.AI.DifficultyLevels", SOTest::Flags)
bool FSODifficultyTest::RunTest(const FString& Parameters)
{
	// A harder level is read by the creatures: better at the job (a move comes back sooner), a little tougher.
	SOTest::FTestWorld W;
	W.AddBox(FVector(-3000, -3000, -100), FVector(3000, 3000, 0));
	USODifficultySubsystem* Levels = W.World->GetSubsystem<USODifficultySubsystem>();
	if (!TestNotNull(TEXT("difficulty subsystem"), Levels))
	{
		return false;
	}
	TestEqual(TEXT("a world starts at the default level"), USODifficultySubsystem::Get(W.World).Id, FName(TEXT("standard")));
	TestFalse(TEXT("a level that is not in the table is refused"), Levels->SetLevel(TEXT("nonsense")));
	FSOSpawnOptions Options;
	Options.bOnNav = false;
	ASOEnemy* Plain = USOSpeciesLibrary::Spawn(W.World, TEXT("bulwark"), FVector(0, 0, 0), 0.0f, Options);
	if (!TestTrue(TEXT("the harder level exists (import with SO_IMPORT_ONLY=difficulty)"), Levels->SetLevel(TEXT("lethal"))) || !TestNotNull(TEXT("bulwark"), Plain))
	{
		return false;
	}
	const FSODifficulty& Lethal = USODifficultySubsystem::Get(W.World);
	TestTrue(TEXT("harder = notices sooner, reacts faster, shoots straighter, flanks more, uses its moves more"),
		Lethal.Notice > 1.0f && Lethal.Reaction < 1.0f && Lethal.AimError < 1.0f && Lethal.FlankShare > 0.33f && Lethal.AbilityCooldown < 1.0f);
	ASOEnemy* Hard = USOSpeciesLibrary::Spawn(W.World, TEXT("bulwark"), FVector(900, 0, 0), 0.0f, Options);
	if (!TestNotNull(TEXT("a bulwark put down at the harder level"), Hard))
	{
		return false;
	}
	W.Run(0.2f);
	TestEqual(TEXT("it has the level's share of health"), Hard->GetMaxHealth(), Plain->GetMaxHealth() * Lethal.Health, 1.0f);
	for (ASOEnemy* E : { Plain, Hard })
	{
		if (AController* Brain = E->GetController())
		{
			Brain->UnPossess();
			Brain->Destroy();
		}
	}
	const FSOAbilityGrant* Slam = Hard->GetAbilitySet() ? Hard->GetAbilitySet()->Find(ESOAbilitySlot::Class) : nullptr;
	if (TestNotNull(TEXT("its slam"), Slam) && TestTrue(TEXT("slam begun"), Hard->ActivateSlot(ESOAbilitySlot::Class)))
	{
		int32 Charges = 0, Max = 0;
		float Left = 0.0f, Cooldown = 0.0f;
		Hard->GetAbilityState(ESOAbilitySlot::Class, Charges, Max, Left, Cooldown);
		TestEqual(TEXT("its move comes back in the level's share of the time"), Left, Slam->Cooldown * Lethal.AbilityCooldown, 0.2f);
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOPulseJamsTest, "ShatteredOrbit.Ability.PulseJams", SOTest::Flags)
bool FSOPulseJamsTest::RunTest(const FString& Parameters)
{
	// A disruptor's pulse: caught in it, a player's abilities are out until it passes; outside its reach, nothing.
	SOTest::FTestWorld W;
	W.AddBox(FVector(-4000, -4000, -100), FVector(4000, 4000, 0));
	ASOCharacter* Player = W.SpawnCharacter(FVector(0, 0, 0));
	ASOCharacter* FarPlayer = W.SpawnCharacter(FVector(0, 2500, 0));
	ASOEnemy* Disruptor = SOTest::SpawnStalker(W, FVector(400, 0, 0), FRotator(0, 180, 0));
	if (AController* Brain = Disruptor->GetController())
	{
		Brain->UnPossess();
		Brain->Destroy();
	}
	W.Run(0.1f);
	Player->GrantAbilitySet(SOTest::MakeKit([](USOAbilitySet& K) { K.Abilities.Add(SOTest::Strike(ESOAbilitySlot::Melee)); }));
	Disruptor->GrantAbilitySet(SOTest::MakeKit([](USOAbilitySet& K)
	{
		FSOAbilityGrant G;
		G.Slot = ESOAbilitySlot::Class;
		G.Ability = USOAbility_Pulse::StaticClass();
		G.Cooldown = 5.0f;
		G.WindUp = 0.5f;
		G.Radius = 900.0f;
		G.Duration = 2.0f;
		G.Status = TEXT("jam");
		K.Abilities.Add(G);
	}));
	TestTrue(TEXT("pulse begun"), Disruptor->ActivateSlot(ESOAbilitySlot::Class));
	W.Run(0.3f);
	TestFalse(TEXT("nothing during the wind-up"), Player->HasStatus(SOTags::Status_Jam));
	W.Run(0.3f);
	TestTrue(TEXT("the one in reach is jammed"), Player->HasStatus(SOTags::Status_Jam));
	TestFalse(TEXT("the one out of reach is not"), FarPlayer->HasStatus(SOTags::Status_Jam));
	TestFalse(TEXT("jammed: no ability"), Player->ActivateSlot(ESOAbilitySlot::Melee));
	W.Run(2.1f);
	TestFalse(TEXT("it passes"), Player->HasStatus(SOTags::Status_Jam));
	TestTrue(TEXT("and the ability is back"), Player->ActivateSlot(ESOAbilitySlot::Melee));

	// a harm is not put on one's own side, a boon not on the other
	TestFalse(TEXT("no jam on a creature from a creature"), USOCombatStatics::ApplyStatus(Disruptor, Disruptor == nullptr ? nullptr : SOTest::SpawnStalker(W, FVector(900, 900, 0), FRotator::ZeroRotator), SOTags::Status_Jam, 1.0f));
	TestFalse(TEXT("no haste on a player from a creature"), USOCombatStatics::ApplyStatus(Disruptor, Player, SOTags::Status_Haste, 1.0f, 1.3f));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOCommanderTest, "ShatteredOrbit.AI.CommanderRalliesAndFalls", SOTest::Flags)
bool FSOCommanderTest::RunTest(const FString& Parameters)
{
	// A role from data: a Remnant given the commander's kit by a variant rallies its squad by itself (they move
	// faster), and when it dies those round it lose a moment.
	SOTest::FTestWorld W;
	W.AddBox(FVector(-6000, -6000, -100), FVector(6000, 6000, 0));
	ASOCharacter* Player = W.SpawnCharacter(FVector(0, 0, 0));
	FSOSpeciesVariant Captain;
	Captain.Id = TEXT("test_captain");
	Captain.Species = TEXT("remnant");
	Captain.Kit = TEXT("commander");
	FSOSpawnOptions Lead;
	Lead.bHunter = true;
	Lead.bOnNav = false;
	Lead.Variant = &Captain;
	FSOSpawnOptions Plain;
	Plain.bHunter = true;
	Plain.bOnNav = false;
	ASOEnemy* Commander = USOSpeciesLibrary::Spawn(W.World, TEXT("remnant"), FVector(1400, 0, 0), 180.0f, Lead);
	ASOEnemy* MateA = USOSpeciesLibrary::Spawn(W.World, TEXT("remnant"), FVector(1500, 300, 0), 180.0f, Plain);
	ASOEnemy* MateB = USOSpeciesLibrary::Spawn(W.World, TEXT("remnant"), FVector(1500, -300, 0), 180.0f, Plain);
	if (!TestNotNull(TEXT("commander"), Commander) || !TestNotNull(TEXT("mate"), MateA) || !TestNotNull(TEXT("mate"), MateB))
	{
		return false;
	}
	int32 Rallied = 0;
	W.Run(7.0f, [&]()
	{
		Rallied += (MateA->HasStatus(SOTags::Status_Haste) || MateB->HasStatus(SOTags::Status_Haste)) ? 1 : 0;
		if (Player->GetHealth() < 60.0f)
		{
			Player->Heal(40.0f);
		}
		for (ASOEnemy* E : { Commander, MateA, MateB })
		{
			if (!E->IsDead() && E->GetHealth() < E->GetMaxHealth())
			{
				E->Heal(1000.0f); // nobody falls before the look is over
			}
		}
	});
	TestNotNull(TEXT("the variant gave it the commander's kit"), Commander->GetAbilitySet());
	TestTrue(TEXT("it rallied its squad by itself"), Rallied > 10);
	TestFalse(TEXT("the plain ones have no kit"), MateA->GetAbilitySet() != nullptr);

	USOCombatStatics::ApplyDamage(Player, Commander, 100000.0f, false);
	TestTrue(TEXT("the commander is down"), Commander->IsDead());
	TestTrue(TEXT("and those round it lose a moment"), MateA->HasStatus(SOTags::Status_Stagger) || MateB->HasStatus(SOTags::Status_Stagger));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOWaveScalingTest, "ShatteredOrbit.Operation.MorePlayersMoreOfThem", SOTest::Flags)
bool FSOWaveScalingTest::RunTest(const FString& Parameters)
{
	// A wave is written for one player; each further player adds a share of every group; a lone elite stays alone.
	TestEqual(TEXT("one player: as written"), ASOOperation::ScaledCount(6, 1, 0.5f), 6);
	TestEqual(TEXT("two players: half as many again"), ASOOperation::ScaledCount(6, 2, 0.5f), 9);
	TestEqual(TEXT("three players: twice as many"), ASOOperation::ScaledCount(6, 3, 0.5f), 12);
	TestEqual(TEXT("a small group still grows"), ASOOperation::ScaledCount(2, 2, 0.5f), 3);
	TestEqual(TEXT("the one that stands alone stays alone"), ASOOperation::ScaledCount(1, 3, 0.5f), 1);
	TestEqual(TEXT("a plan can switch it off"), ASOOperation::ScaledCount(6, 3, 0.0f), 6);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOPackTest, "ShatteredOrbit.AI.ThePackGoesInTogether", SOTest::Flags)
bool FSOPackTest::RunTest(const FString& Parameters)
{
	// Four clawed stalkers that start strung out along a line: the first to arrive does not go in alone. When the
	// first blow lands, at least three of them are round the target.
	SOTest::FTestWorld W;
	W.AddBox(FVector(-8000, -8000, -100), FVector(8000, 8000, 0));
	ASOCharacter* Player = W.SpawnCharacter(FVector(0, 0, 0));
	FSOSpawnOptions Options;
	Options.bHunter = true;
	Options.bOnNav = false;
	TArray<ASOEnemy*> Pack;
	for (int32 i = 0; i < 4; ++i)
	{
		Pack.Add(USOSpeciesLibrary::Spawn(W.World, TEXT("stalker_feral"), FVector(1800.0f + i * 900.0f, (i % 2) * 300.0f, 0), 180.0f, Options));
	}
	if (!TestTrue(TEXT("pack spawned"), Pack.Num() == 4 && !Pack.Contains(nullptr)))
	{
		return false;
	}
	const float Full = Player->GetHealth() + Player->GetShield();
	int32 RoundAtFirstBlow = -1;
	float FirstBlowAt = -1.0f, FirstArrivedAt = -1.0f, Clock = 0.0f;
	W.Run(22.0f, [&]()
	{
		Clock += SOTest::Dt;
		int32 Round = 0;
		for (const ASOEnemy* E : Pack)
		{
			Round += FVector::Dist2D(E->GetActorLocation(), Player->GetActorLocation()) < 1400.0f ? 1 : 0;
		}
		if (FirstArrivedAt < 0.0f && Round >= 1)
		{
			FirstArrivedAt = Clock;
		}
		if (RoundAtFirstBlow < 0 && Player->GetHealth() + Player->GetShield() < Full - 0.5f)
		{
			RoundAtFirstBlow = Round;
			FirstBlowAt = Clock;
		}
		if (Player->GetHealth() < 60.0f)
		{
			Player->Heal(40.0f);
		}
	});
	TestTrue(TEXT("the pack did strike"), RoundAtFirstBlow >= 0);
	TestTrue(FString::Printf(TEXT("at the first blow at least three were round the target (there were %d)"), RoundAtFirstBlow), RoundAtFirstBlow >= 3);
	TestTrue(FString::Printf(TEXT("the first to arrive (%.1f s) waited for the others (first blow %.1f s)"), FirstArrivedAt, FirstBlowAt), FirstBlowAt > FirstArrivedAt + 1.0f);
	return true;
}

#endif
