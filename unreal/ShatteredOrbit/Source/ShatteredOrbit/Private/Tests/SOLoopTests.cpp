// The owner's game loop (2026-11-20): every beat a player earns reaches the screen. What the HUD draws is judged in
// capture set 38 (hud_20 to hud_23); this checks the events it draws from: a kill pays xp and credits through the
// inventory and the inventory tells the screen, a level reached is announced, and a creature given a name of its own
// by a level's variant knows it is an elite.

#include "SOTestWorld.h"

#if WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR

#include "SOCombatStatics.h"
#include "SOEnemy.h"
#include "SOInventoryComponent.h"
#include "SOLootActors.h"
#include "SOPlayerState.h"
#include "SOProgression.h"
#include "SOSpecies.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOLoopKillPaysTest, "ShatteredOrbit.Loop.AKillPaysOnScreen", SOTest::Flags)
bool FSOLoopKillPaysTest::RunTest(const FString& Parameters)
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
	if (!TestNotNull(TEXT("inventory"), Inv) || !TestNotNull(TEXT("loot subsystem"), W.World->GetSubsystem<USOLootSubsystem>()))
	{
		return false;
	}

	int32 XpGot = 0, CreditsGot = 0, LevelReached = 0;
	Inv->OnReward.AddLambda([&](ESORewardKind Kind, int32 Amount)
	{
		XpGot += Kind == ESORewardKind::Xp ? Amount : 0;
		CreditsGot += Kind == ESORewardKind::Credits ? Amount : 0;
	});
	Inv->OnLevelUp.AddLambda([&](int32 Level) { LevelReached = Level; });

	// a creature of the other side, dressed by a level's variant with a name of its own, killed by the player: the
	// loot subsystem pays the killer's inventory and the inventory tells the screen what came in
	FSOSpeciesVariant V;
	V.Id = TEXT("captain");
	V.DisplayName = FText::FromString(TEXT("Remnant Captain"));
	FSOSpawnOptions Options;
	Options.bOnNav = false;
	Options.Variant = &V;
	ASOEnemy* E = USOSpeciesLibrary::Spawn(W.World, TEXT("remnant"), FVector(600, 0, 0), 180.0f, Options);
	if (!TestNotNull(TEXT("a remnant spawned (/Game/Characters/Remnant imported)"), E))
	{
		return false;
	}
	TestTrue(TEXT("a creature with a variant's name is an elite"), E->IsElite());
	if (AController* Brain = E->GetController())
	{
		Brain->UnPossess();
		Brain->Destroy();
	}
	W.Run(0.1f);
	const int32 XpBefore = Inv->GetXp(), CreditsBefore = Inv->GetCredits(), LevelBefore = Inv->GetLevel();
	USOCombatStatics::ApplyDamage(Player, E, 100000.0f, false);
	W.Run(0.1f);
	TestTrue(TEXT("the creature died"), E->IsDead());
	TestTrue(TEXT("the kill paid xp"), XpGot > 0);
	TestTrue(TEXT("the kill paid credits"), CreditsGot > 0);
	TestEqual(TEXT("what reached the screen is what the inventory got (credits)"), CreditsGot, Inv->GetCredits() - CreditsBefore);
	if (Inv->GetLevel() == LevelBefore)
	{
		TestEqual(TEXT("what reached the screen is what the inventory got (xp)"), XpGot, Inv->GetXp() - XpBefore);
	}

	// the level: enough xp for the next one is announced with the level reached
	const USOProgressionTable& Rules = USOProgressionTable::Get();
	const int32 Level = Inv->GetLevel();
	Inv->AddXp(Rules.XpForLevel(Level) - Inv->GetXp() + 1);
	TestEqual(TEXT("the level reached is announced"), LevelReached, Level + 1);
	TestEqual(TEXT("and it is the inventory's"), Inv->GetLevel(), Level + 1);

	// a creature as written is no elite
	ASOEnemy* Plain = USOSpeciesLibrary::Spawn(W.World, TEXT("remnant"), FVector(900, 0, 0), 180.0f, FSOSpawnOptions());
	TestTrue(TEXT("a creature as written is no elite"), Plain && !Plain->IsElite());
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
