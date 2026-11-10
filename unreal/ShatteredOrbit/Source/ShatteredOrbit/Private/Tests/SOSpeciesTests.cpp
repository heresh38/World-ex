// Species and areas: every creature is one class asked for by id and is the same wherever it is spawned; a level only
// dresses it with a variant; one area at a time is kept in memory.

#include "SOTestWorld.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "Engine/GameInstance.h"
#include "EngineUtils.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Misc/Paths.h"
#include "SOAltered.h"
#include "SOAreaSubsystem.h"
#include "SOEnemy.h"
#include "SOEnemyAIController.h"
#include "SOEnemySpawner.h"
#include "SOOperation.h"
#include "SOSound.h"
#include "SOSpecies.h"
#include "SOWeapon.h"

namespace SOTest
{
	/** Two operations that share a species: the first as written, the second with a baseline and a variant. */
	const TCHAR* PlainPlan = TEXT(R"({
		"name": "First", "tagline": "",
		"groups": {"a": {"yaw": 0, "points": [[1500, -200, 0], [1500, 200, 0]]}},
		"stages": [{"id": "clear", "title": "A", "objective": "Clear", "kind": "clear", "waves": [{"spawn": [["remnant", 2, "a"]]}]}]
	})");

	const TCHAR* DressedPlan = TEXT(R"({
		"name": "Second", "tagline": "",
		"enemies": {"health": 1.5},
		"variants": {
			"remnant_ashen": {"species": "remnant", "name": "Ashen Remnant", "health": 2.0, "damage": 1.5, "speed": 1.2, "weapon": "shotgun"},
			"nonsense": {"species": "no_such_creature"}
		},
		"groups": {"a": {"yaw": 0, "points": [[1500, -200, 0], [1500, 200, 0]]}},
		"stages": [{"id": "clear", "title": "B", "objective": "Clear", "kind": "clear",
			"waves": [{"spawn": [["remnant", 1, "a"], ["remnant_ashen", 1, "a"]]}]}]
	})");

	ASOOperation* StartOperation(FTestWorld& W, const TCHAR* Plan)
	{
		W.AddBox(FVector(-1000, -2000, -100), FVector(5000, 2000, 0));
		ASOOperation* Op = W.World->SpawnActor<ASOOperation>();
		Op->StartDelay = -1.0f;
		Op->LoadPlan(Plan);
		Op->Begin();
		W.Run(0.4f);
		return Op;
	}

	TArray<ASOEnemy*> Creatures(UWorld* World)
	{
		TArray<ASOEnemy*> Out;
		for (TActorIterator<ASOEnemy> It(World); It; ++It)
		{
			Out.Add(*It);
		}
		return Out;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOSpeciesRegistryTest, "ShatteredOrbit.Species.Registry", SOTest::Flags)
bool FSOSpeciesRegistryTest::RunTest(const FString& Parameters)
{
	// Every creature names itself; nothing else lists them. Asked for by id, it is its own class with its own brain.
	const TArray<FName> Ids = USOSpeciesLibrary::GetSpecies();
	const TMap<FName, UClass*> Expect = {
		{ TEXT("stalker_feral"), ASOEnemy::StaticClass() }, { TEXT("stalker"), ASOArmedStalker::StaticClass() },
		{ TEXT("remnant"), ASORemnant::StaticClass() }, { TEXT("veilborn"), ASOVeilborn::StaticClass() },
		{ TEXT("bulwark"), ASOBulwark::StaticClass() }, { TEXT("colossus"), ASOColossus::StaticClass() },
		{ TEXT("conduit"), ASOConduit::StaticClass() } };
	for (const TPair<FName, UClass*>& E : Expect)
	{
		TestTrue(FString::Printf(TEXT("species %s is %s"), *E.Key.ToString(), *E.Value->GetName()), USOSpeciesLibrary::Find(E.Key) == E.Value);
	}
	TestEqual(TEXT("and there are no others unaccounted for"), Ids.Num(), Expect.Num());
	TestNull(TEXT("an unknown id is no species"), USOSpeciesLibrary::Find(TEXT("no_such_creature")).Get());

	SOTest::FTestWorld W;
	W.AddBox(FVector(-4000, -4000, -100), FVector(4000, 4000, 0));
	int32 Heard = 0;
	const FDelegateHandle Handle = USOSpeciesLibrary::OnSpawned().AddLambda([&Heard](ASOEnemy*) { ++Heard; });
	int32 N = 0;
	for (const FName& Id : Ids)
	{
		if (Id == TEXT("conduit") || Id == TEXT("colossus"))
		{
			continue;                                               // (their own tests; they need their content and room)
		}
		ASOEnemy* E = USOSpeciesLibrary::Spawn(W.World, Id, FVector(600.0f * N - 900.0f, 800.0f, 0.0f), 180.0f);
		++N;
		if (TestNotNull(FString::Printf(TEXT("%s spawns"), *Id.ToString()), E))
		{
			TestTrue(FString::Printf(TEXT("%s is its species' class"), *Id.ToString()), E->GetClass() == Expect.FindRef(Id) && E->SpeciesId == Id);
			TestNotNull(FString::Printf(TEXT("%s has the shared brain"), *Id.ToString()), Cast<ASOEnemyAIController>(E->GetController()));
			TestTrue(FString::Printf(TEXT("%s is the species as written"), *Id.ToString()), E->GetVariantId().IsNone() && E->GetDamageScale() == 1.0f);
		}
	}
	USOSpeciesLibrary::OnSpawned().Remove(Handle);
	TestEqual(TEXT("a level's hook hears every spawn"), Heard, N);
	TestNull(TEXT("an unknown species does not spawn"), USOSpeciesLibrary::Spawn(W.World, TEXT("no_such_creature"), FVector::ZeroVector, 0.0f));

	// a spawner asks by species too
	ASOEnemySpawner* Spawner = W.World->SpawnActor<ASOEnemySpawner>(FVector(-2000, -1500, 0), FRotator::ZeroRotator);
	Spawner->Species = TEXT("remnant");
	ASOEnemy* FromSpawner = Spawner->SpawnEnemy();
	TestTrue(TEXT("the spawner's creature is the same species class"), FromSpawner && FromSpawner->GetClass() == ASORemnant::StaticClass());
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOSpeciesVariantTest, "ShatteredOrbit.Species.SameEverywhere", SOTest::Flags)
bool FSOSpeciesVariantTest::RunTest(const FString& Parameters)
{
	// Two operations use the same species. In the first it is as written; the second dresses it (a baseline for all
	// its creatures and a named variant). The creature's class, brain and moves are the same in both; only the numbers
	// the variant names differ, and the species itself is never changed by it.
	const ASORemnant* Written = GetDefault<ASORemnant>();
	const float Health = Written->StartMaxHealth, Run = Written->RunSpeed, Scale = Written->WeaponDamageScale, Melee = Written->MeleeDamage;

	SOTest::FTestWorld First;
	ASOOperation* OpA = SOTest::StartOperation(First, SOTest::PlainPlan);
	TArray<ASOEnemy*> A = SOTest::Creatures(First.World);
	if (!TestEqual(TEXT("the first operation's wave"), A.Num(), 2))
	{
		return false;
	}
	for (const ASOEnemy* E : A)
	{
		TestTrue(TEXT("first: a remnant as written"), E->GetClass() == ASORemnant::StaticClass() && E->GetVariantId().IsNone());
		TestEqual(TEXT("first: its own health"), E->GetMaxHealth(), Health);
		TestEqual(TEXT("first: its own gun"), E->WeaponArchetype, Written->WeaponArchetype);
	}

	SOTest::FTestWorld Second;
	ASOOperation* OpB = SOTest::StartOperation(Second, SOTest::DressedPlan);
	TestEqual(TEXT("the unknown species' variant was refused"), OpB->Variants.Num(), 1);
	TArray<ASOEnemy*> B = SOTest::Creatures(Second.World);
	if (!TestEqual(TEXT("the second operation's wave"), B.Num(), 2))
	{
		return false;
	}
	const ASOEnemy* Plain = nullptr;
	const ASOEnemy* Ashen = nullptr;
	for (const ASOEnemy* E : B)
	{
		(E->GetVariantId() == TEXT("remnant_ashen") ? Ashen : Plain) = E;
	}
	if (!TestNotNull(TEXT("second: the plain remnant"), Plain) || !TestNotNull(TEXT("second: the dressed remnant"), Ashen))
	{
		return false;
	}
	// the same creature
	TestTrue(TEXT("both are the species' class"), Plain->GetClass() == ASORemnant::StaticClass() && Ashen->GetClass() == ASORemnant::StaticClass());
	TestTrue(TEXT("both have the species' brain"), Plain->GetController() && Ashen->GetController() && Plain->GetController()->GetClass() == A[0]->GetController()->GetClass()
		&& Ashen->GetController()->GetClass() == A[0]->GetController()->GetClass());
	TestTrue(TEXT("the same voice, cover use and range"), Ashen->VoicePrefix == Written->VoicePrefix && Ashen->bUsesCover == Written->bUsesCover && Ashen->PreferredRange == Written->PreferredRange);
	// the operation's baseline on the plain one
	TestEqual(TEXT("baseline: health x 1.5"), Plain->GetMaxHealth(), Health * 1.5f);
	TestEqual(TEXT("baseline: its own gun"), Plain->WeaponArchetype, Written->WeaponArchetype);
	TestEqual(TEXT("baseline: its own name"), Plain->DisplayName.ToString(), Written->DisplayName.ToString());
	// the variant over the baseline
	TestEqual(TEXT("variant: health x 2 x 1.5"), Ashen->GetMaxHealth(), Health * 3.0f);
	TestEqual(TEXT("variant: full health"), Ashen->GetHealth(), Health * 3.0f);
	TestEqual(TEXT("variant: rounds x 1.5"), Ashen->WeaponDamageScale, Scale * 1.5f);
	TestEqual(TEXT("variant: claws x 1.5"), Ashen->MeleeDamage, Melee * 1.5f);
	TestEqual(TEXT("variant: special moves x 1.5"), Ashen->GetDamageScale(), 1.5f);
	TestEqual(TEXT("variant: run speed x 1.2"), Ashen->RunSpeed, Run * 1.2f);
	TestEqual(TEXT("variant: its name"), Ashen->DisplayName.ToString(), FString(TEXT("Ashen Remnant")));
	TestEqual(TEXT("variant: its gun"), Ashen->WeaponArchetype, FName(TEXT("shotgun")));
	if (const ASOWeapon* Gun = Ashen->GetWeapon())
	{
		TestEqual(TEXT("variant: armed with that gun"), Gun->GetInstance().Archetype, FName(TEXT("shotgun")));
	}
	else
	{
		AddError(TEXT("variant: it is unarmed"));
	}
	// the species is untouched
	TestTrue(TEXT("the species' own numbers did not change"), Written->StartMaxHealth == Health && Written->RunSpeed == Run && Written->WeaponDamageScale == Scale
		&& Written->WeaponArchetype != TEXT("shotgun"));
	TestEqual(TEXT("the first operation's remnants are still as written"), A[0]->GetMaxHealth(), Health);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOAreaRegistryTest, "ShatteredOrbit.Area.OneAtATime", SOTest::Flags)
bool FSOAreaRegistryTest::RunTest(const FString& Parameters)
{
	// The areas (Data/areas.json): each has a level that exists and the content folders that are its alone; leaving an
	// area lets go of what the game keeps by hand.
	UGameInstance* Instance = NewObject<UGameInstance>(GEngine);
	USOAreaSubsystem* Areas = NewObject<USOAreaSubsystem>(Instance);
	Areas->Reload();
	if (!TestTrue(TEXT("the range, the city and an operation are listed"), Areas->Find(TEXT("range")) && Areas->Find(TEXT("nexus")) && Areas->Find(TEXT("meridian"))))
	{
		return false;
	}
	TSet<FString> Owned;
	for (const FSOArea& A : Areas->GetAreas())
	{
		TestTrue(FString::Printf(TEXT("%s: its level exists (%s)"), *A.Id.ToString(), *A.Level), FPackageName::DoesPackageExist(A.Level));
		TestTrue(FString::Printf(TEXT("%s: found again by its level"), *A.Id.ToString()), Areas->FindByLevel(A.Level) == &A && Areas->FindByLevel(A.Level + TEXT(".") + FPackageName::GetShortName(A.Level)) == &A);
		if (!A.Plan.IsEmpty())
		{
			TestTrue(FString::Printf(TEXT("%s: its plan exists (%s)"), *A.Id.ToString(), *A.Plan), FPaths::FileExists(FPaths::ProjectDir() / A.Plan));
		}
		for (const FString& Folder : A.Content)
		{
			bool bAlready = false;
			Owned.Add(Folder, &bAlready);
			TestFalse(FString::Printf(TEXT("%s: %s belongs to one area only"), *A.Id.ToString(), *Folder), bAlready);
		}
	}
	TestNull(TEXT("a level that is no area is refused"), Areas->FindByLevel(TEXT("/Game/Maps/L_Nowhere")));
	TestTrue(TEXT("the range owns no content of its own"), Areas->Find(TEXT("range"))->Content.Num() == 0);

	// sounds are kept once played, but only for the area: leaving it lets them all go
	USOSoundLibrary::Find(TEXT("ui_open"));
	if (USOSoundLibrary::NumHeld() == 0)
	{
		AddWarning(TEXT("no sounds imported: the cache release was not checked"));
	}
	else
	{
		USOAreaSubsystem::OnReleaseContent().Broadcast();
		TestEqual(TEXT("leaving an area: the sound cache holds nothing"), USOSoundLibrary::NumHeld(), 0);
	}
	return true;
}

#endif
