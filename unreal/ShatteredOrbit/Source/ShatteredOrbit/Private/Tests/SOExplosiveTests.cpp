// Things in the world that explode (ASOExplosive; the owner's effects guide: "environmental explosion: reactive
// environment; vehicle explosion: massive and dramatic") and the top rarity's own signature ("exotic: unique and
// memorable"): a drum hurt past half burns and goes by itself, a blast sets the next one off, what it kills is the
// shooter's, a wreck takes far more and is thrown up; a Sovereign copy draws its gold.

#include "SOTestWorld.h"

#if WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR

#include "Engine/StaticMesh.h"
#include "SOCombatStatics.h"
#include "SOEnemy.h"
#include "SOExplosive.h"
#include "SOFxSubsystem.h"
#include "SOInventoryComponent.h"
#include "SOJournal.h"
#include "SOLootLibrary.h"
#include "SOPlayerState.h"
#include "SOSpecies.h"
#include "SOWeapon.h"

namespace
{
	ASOExplosive* PutDown(SOTest::FTestWorld& W, ESOExplosiveKind Kind, const FVector& At)
	{
		FActorSpawnParameters Params;
		Params.bDeferConstruction = true;
		Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
		ASOExplosive* E = W.World->SpawnActor<ASOExplosive>(ASOExplosive::StaticClass(), FTransform(At), Params);
		if (E)
		{
			E->SetKind(Kind);
			E->FinishSpawning(FTransform(At));
		}
		return E;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOExplosiveGoesOffTest, "ShatteredOrbit.Fx.ExplosivesGoOff", SOTest::Flags)
bool FSOExplosiveGoesOffTest::RunTest(const FString& Parameters)
{
	SOTest::FTestWorld W;
	W.AddBox(FVector(-4000, -4000, -100), FVector(4000, 4000, 0));
	for (const ESOExplosiveKind Kind : { ESOExplosiveKind::Drum, ESOExplosiveKind::Cylinder, ESOExplosiveKind::Cell, ESOExplosiveKind::Vehicle })
	{
		TestNotNull(*FString::Printf(TEXT("its mesh (%s: SO_IMPORT_ONLY=explosives)"), *ASOExplosive::MeshPath(Kind)), Cast<UStaticMesh>(FSoftObjectPath(ASOExplosive::MeshPath(Kind)).TryLoad()));
	}
	ASOCharacter* Player = W.SpawnCharacter(FVector(-600, 0, 0));
	FActorSpawnParameters PSParams;
	PSParams.bDeferConstruction = true;
	ASOPlayerState* PS = W.World->SpawnActor<ASOPlayerState>(ASOPlayerState::StaticClass(), FTransform::Identity, PSParams);
	PS->GetInventory()->bPersist = false;
	PS->FinishSpawning(FTransform::Identity);
	Player->SetPlayerState(PS);
	ASOExplosive* Drum = PutDown(W, ESOExplosiveKind::Drum, FVector(500, 0, 0));
	FSOSpawnOptions Options;
	Options.bOnNav = false;
	ASOEnemy* Levy = USOSpeciesLibrary::Spawn(W.World, TEXT("remnant"), FVector(640, 120, 0), 180.0f, Options);
	if (!TestNotNull(TEXT("a drum"), Drum) || !TestNotNull(TEXT("a Levy beside it"), Levy))
	{
		return false;
	}
	if (AController* Brain = Levy->GetController())
	{
		Brain->UnPossess();
		Brain->Destroy();
	}
	W.Run(0.2f);
	const int32 Before = ASOExplosive::NumDetonated;
	// a round that holes it: it burns, and goes by itself a moment later
	USOCombatStatics::ApplyDamage(Player, Drum, Drum->MaxHealth * 0.6f, false);
	TestTrue(TEXT("holed past half, it burns"), Drum->IsLit());
	TestFalse(TEXT("not gone yet"), Drum->IsSpent());
	W.Run(Drum->BurnFuse + 0.3f);
	TestTrue(TEXT("it went by itself"), Drum->IsSpent());
	TestEqual(TEXT("once"), ASOExplosive::NumDetonated, Before + 1);
	TestTrue(TEXT("the Levy beside it is dead"), Levy->IsDead());
	TestEqual(TEXT("and it is the shooter's kill"), PS->GetInventory()->GetTally(SOJournal::KillTally(TEXT("remnant"))), 1);
	TestEqual(TEXT("a spent drum takes nothing"), USOCombatStatics::ApplyDamage(Player, Drum, 50.0f, false), 0.0f);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOExplosiveChainTest, "ShatteredOrbit.Fx.ExplosivesChain", SOTest::Flags)
bool FSOExplosiveChainTest::RunTest(const FString& Parameters)
{
	// a row of drums a step apart: one shot through sets off the next, and that the next; a wreck takes a lot more
	SOTest::FTestWorld W;
	W.AddBox(FVector(-4000, -4000, -100), FVector(4000, 4000, 0));
	ASOCharacter* Player = W.SpawnCharacter(FVector(-900, 0, 0));
	TArray<ASOExplosive*> Row;
	for (int32 i = 0; i < 3; ++i)
	{
		Row.Add(PutDown(W, ESOExplosiveKind::Drum, FVector(400 + i * 120.0f, 0, 0)));
	}
	ASOExplosive* Car = PutDown(W, ESOExplosiveKind::Vehicle, FVector(400, 1600, 0));
	W.Run(0.2f);
	const int32 Before = ASOExplosive::NumDetonated;
	USOCombatStatics::ApplyDamage(Player, Row[0], 500.0f, false);
	W.Run(0.1f);
	TestTrue(TEXT("the one shot through went at once"), Row[0]->IsSpent());
	W.Run(1.2f);
	TestTrue(TEXT("the next went off by it"), Row[1]->IsSpent());
	TestTrue(TEXT("and the last by that"), Row[2]->IsSpent());
	TestEqual(TEXT("three blasts"), ASOExplosive::NumDetonated, Before + 3);
	TestFalse(TEXT("the wreck out of reach is whole"), Car->IsSpent());
	USOCombatStatics::ApplyDamage(Player, Car, 100.0f, false);
	TestFalse(TEXT("a wreck takes more than a drum"), Car->IsSpent() || Car->IsLit());
	const FVector Was = Car->GetActorLocation();
	USOCombatStatics::ApplyDamage(Player, Car, 1000.0f, false);
	W.Run(0.45f);
	TestTrue(TEXT("the wreck went"), Car->IsSpent());
	TestTrue(TEXT("and is thrown up by its blast"), Car->GetActorLocation().Z > Was.Z + 60.0f);
	W.Run(1.2f);
	TestTrue(TEXT("and comes down again"), FMath::Abs(Car->GetActorLocation().Z - Was.Z) < 5.0f);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOSovereignTest, "ShatteredOrbit.Fx.SovereignSignature", SOTest::Flags)
bool FSOSovereignTest::RunTest(const FString& Parameters)
{
	// the top rarity's copy fires in gold (its flash, its round's way, where it lands); a lower one does not
	SOTest::FTestWorld W;
	W.AddBox(FVector(-4000, -4000, -100), FVector(4000, 4000, 0));
	USOFxSubsystem* Fx = W.World->GetSubsystem<USOFxSubsystem>();
	if (!TestNotNull(TEXT("the effects"), Fx))
	{
		return false;
	}
	const int32 Before = Fx->GetNumParticles();
	Fx->SovereignFlash(FVector(0, 0, 100), FVector::ForwardVector, 1.0f, false, false);
	const int32 Flash = Fx->GetNumParticles() - Before;
	Fx->SovereignTrail(FVector(0, 0, 100), FVector(3000, 0, 100), 20000.0f);
	const int32 Trail = Fx->GetNumParticles() - Before - Flash;
	Fx->SovereignMark(FVector(3000, 0, 100), -FVector::ForwardVector, 0.15f);
	const int32 Mark = Fx->GetNumParticles() - Before - Flash - Trail;
	TestTrue(TEXT("a crown at the muzzle"), Flash >= 12);
	TestTrue(TEXT("a helix along the way and an orb on its head"), Trail >= 40);
	TestTrue(TEXT("a sigil where it lands"), Mark >= 12);
	// which copies: the top rarity's alone
	FRandomStream Rng(3);
	const USOLootTables* Tables = USOLootLibrary::GetTables();
	if (TestNotNull(TEXT("the loot tables"), Tables))
	{
		const int32 Top = Tables->Rarities.Num() - 1;
		ASOCharacter* Hero = W.SpawnCharacter(FVector(0, 0, 0));
		Hero->EquipInstance(USOLootLibrary::MakeWeapon(TEXT("rifle"), Top, 20, Rng));
		TestTrue(TEXT("a Sovereign rifle signs its shots"), Hero->GetWeapon() && Hero->GetWeapon()->IsSovereign());
		Hero->EquipInstance(USOLootLibrary::MakeWeapon(TEXT("rifle"), Top - 1, 20, Rng));
		TestFalse(TEXT("a Legendary one does not"), Hero->GetWeapon() && Hero->GetWeapon()->IsSovereign());
	}
	// the pool's cost is kept, and a full pool gives way without falling behind
	Fx->ResetStats();
	for (int32 i = 0; i < USOFxSubsystem::MaxParticles + 300; ++i)
	{
		FSOFxParticle P;
		P.Position = FVector(i, 0, 100);
		P.Life = 2.0f;
		Fx->Spawn(P);
	}
	TestEqual(TEXT("the pool holds its cap"), Fx->GetNumParticles(), USOFxSubsystem::MaxParticles);
	TestEqual(TEXT("and counts what gave way"), Fx->GetDropped(), 300 + FMath::Max(0, Before + Flash + Trail + Mark - 0));
	W.Run(0.1f);
	TestTrue(TEXT("its frame's work is measured"), Fx->GetLastTickMs() >= 0.0f && Fx->GetPeakParticles() >= USOFxSubsystem::MaxParticles);
	return true;
}

#endif
