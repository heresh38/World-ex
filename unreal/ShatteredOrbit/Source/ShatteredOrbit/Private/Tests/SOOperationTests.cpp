// Operation tests: the plan file, the stage flow (travel, clear, hold, boss with health-keyed adds), checkpoints and
// the one-random-piece reward.

#include "SOTestWorld.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "EngineUtils.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "SOCombatStatics.h"
#include "SOEnemy.h"
#include "SOSpecies.h"
#include "SOEnemyAIController.h"
#include "SOInventoryComponent.h"
#include "SOOperation.h"
#include "SOPlayerState.h"

namespace SOTest
{
	const TCHAR* OperationPlan = TEXT(R"({
		"name": "Test Run", "tagline": "Four stages",
		"groups": {
			"a": {"yaw": 180, "points": [[3000, -300, 0], [3000, 300, 0]]},
			"boss": {"yaw": 180, "points": [[3500, 0, 0]]}
		},
		"stages": [
			{"id": "go", "title": "The Gate", "objective": "Reach the gate", "kind": "travel", "goal": [1500, 0, 0], "radius": 400,
			 "checkpoint": [1400, 0, 100, 0]},
			{"id": "clear", "title": "The Gate", "objective": "Clear the gate", "kind": "clear",
			 "waves": [{"spawn": [["stalker", 2, "a"]]}, {"delay": 0.5, "maxAlive": 0, "spawn": [["stalker", 1, "a"]]}]},
			{"id": "hold", "title": "The Plaza", "objective": "Hold the plaza", "kind": "hold", "hold": 3, "goal": [2000, 0, 0],
			 "checkpoint": [1900, 0, 100, 90]},
			{"id": "boss", "title": "The Crown", "objective": "Bring it down", "kind": "boss", "boss": "stalker", "bossGroup": "boss",
			 "waves": [{"bossHealth": 0.5, "spawn": [["stalker", 2, "a"]]}]}
		],
		"rewards": {"rarity": 3, "armor": [["head", "no_such_piece"]], "weapons": ["no_such_gun"]}
	})");

	TArray<ASOEnemy*> LiveEnemies(UWorld* World, const ASOEnemy* Except = nullptr)
	{
		TArray<ASOEnemy*> Out;
		for (TActorIterator<ASOEnemy> It(World); It; ++It)
		{
			if (!It->IsDead() && *It != Except)
			{
				Out.Add(*It);
			}
		}
		return Out;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOOperationPlanTest, "ShatteredOrbit.Operation.PlanFile", SOTest::Flags)
bool FSOOperationPlanTest::RunTest(const FString& Parameters)
{
	SOTest::FTestWorld W;
	ASOOperation* Op = W.World->SpawnActor<ASOOperation>();
	TestTrue(TEXT("inline plan reads"), Op->LoadPlan(SOTest::OperationPlan));
	TestEqual(TEXT("stages"), Op->Stages.Num(), 4);
	TestEqual(TEXT("spawn groups"), Op->Groups.Num(), 2);
	TestEqual(TEXT("rewards"), Op->Rewards.Num(), 2);
	TestEqual(TEXT("clear stage waves"), Op->Stages[1].Waves.Num(), 2);
	TestEqual(TEXT("hold time"), Op->Stages[2].HoldTime, 3.0f);
	TestEqual(TEXT("boss keyed wave"), Op->Stages[3].Waves[0].BossHealth, 0.5f);

	// the shipped operation's plan reads too, and every enemy it names has a class and every group exists
	FString Text;
	if (FFileHelper::LoadFileToString(Text, *(FPaths::ProjectDir() / TEXT("Data/op_meridian.json"))))
	{
		ASOOperation* Real = W.World->SpawnActor<ASOOperation>();
		if (TestTrue(TEXT("op_meridian.json reads"), Real->LoadPlan(Text)))
		{
			for (const FSOStage& S : Real->Stages)
			{
				for (const FSOWave& Wave : S.Waves)
				{
					for (const FSOWaveEntry& E : Wave.Entries)
					{
						TestTrue(*FString::Printf(TEXT("%s: enemy %s has a class"), *S.Id.ToString(), *E.Enemy.ToString()), USOSpeciesLibrary::Find(E.Enemy) != nullptr || Real->Variants.Contains(E.Enemy));
						TestTrue(*FString::Printf(TEXT("%s: group %s exists"), *S.Id.ToString(), *E.Group.ToString()), Real->Groups.Contains(E.Group));
					}
				}
				if (S.Kind == ESOStageKind::Boss)
				{
					TestTrue(TEXT("boss has a class"), USOSpeciesLibrary::Find(S.Boss) != nullptr || Real->Variants.Contains(S.Boss));
					TestTrue(TEXT("boss group exists"), Real->Groups.Contains(S.BossGroup));
				}
			}
		}
	}
	else
	{
		AddWarning(TEXT("Data/op_meridian.json not written yet"));
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOOperationFlowTest, "ShatteredOrbit.Operation.StagesToReward", SOTest::Flags)
bool FSOOperationFlowTest::RunTest(const FString& Parameters)
{
	SOTest::FTestWorld W;
	W.AddBox(FVector(-1000, -2000, -100), FVector(5000, 2000, 0));
	ASOCharacter* Player = W.SpawnCharacter(FVector(0, 0, 0));
	FActorSpawnParameters Params;
	Params.bDeferConstruction = true;
	ASOPlayerState* PS = W.World->SpawnActor<ASOPlayerState>(ASOPlayerState::StaticClass(), FTransform::Identity, Params);
	PS->GetInventory()->bPersist = false;
	PS->FinishSpawning(FTransform::Identity);
	Player->SetPlayerState(PS);

	ASOOperation* Op = W.World->SpawnActor<ASOOperation>();
	Op->StartDelay = -1.0f;
	Op->StageGap = 0.2f;
	Op->LoadPlan(SOTest::OperationPlan);
	FTransform Checkpoint;
	TestFalse(TEXT("no checkpoint before it starts"), Op->GetCheckpoint(Checkpoint));
	Op->Begin();
	W.Run(0.3f);

	// 1 travel: nothing happens until a player reaches the goal
	TestEqual(TEXT("stage 0"), Op->GetStageIndex(), 0);
	TestTrue(TEXT("travel checkpoint"), Op->GetCheckpoint(Checkpoint) && Checkpoint.GetLocation().X == 1400.0);
	Player->SetActorLocation(FVector(1450, 0, 92));
	W.Run(0.6f);
	TestEqual(TEXT("arrived: stage 1"), Op->GetStageIndex(), 1);

	// 2 clear: two come, then the third once they are down
	W.Run(0.3f);
	TestEqual(TEXT("goal counts every wave"), Op->GetGoalCount(), 3);
	TArray<ASOEnemy*> Live = SOTest::LiveEnemies(W.World);
	TestEqual(TEXT("first wave"), Live.Num(), 2);
	for (ASOEnemy* E : Live)
	{
		const ASOEnemyAIController* AI = Cast<ASOEnemyAIController>(E->GetController());
		TestTrue(TEXT("wave enemies hunt"), AI && AI->bHunter);
		E->Die(Player);
	}
	W.Run(1.0f);
	Live = SOTest::LiveEnemies(W.World);
	TestEqual(TEXT("second wave after the first is down"), Live.Num(), 1);
	TestEqual(TEXT("still clearing"), Op->GetStageIndex(), 1);
	TestTrue(TEXT("objective shows progress"), Op->GetObjectiveLine().Contains(TEXT("2 / 3")));
	for (ASOEnemy* E : Live)
	{
		E->Die(Player);
	}
	W.Run(0.6f);
	TestEqual(TEXT("cleared: stage 2"), Op->GetStageIndex(), 2);
	TestEqual(TEXT("kills"), Op->GetKills(), 0);

	// 3 hold: ends on the timer, the checkpoint moves up
	TestTrue(TEXT("hold checkpoint"), Op->GetCheckpoint(Checkpoint) && Checkpoint.GetLocation().X == 1900.0);
	W.Run(2.0f);
	TestEqual(TEXT("still holding"), Op->GetStageIndex(), 2);
	W.Run(1.5f);
	TestEqual(TEXT("held: stage 3"), Op->GetStageIndex(), 3);
	TestTrue(TEXT("checkpoint stays at the last one"), Op->GetCheckpoint(Checkpoint) && Checkpoint.GetLocation().X == 1900.0);

	// 4 boss: adds come when its health falls to half, fall with it
	W.Run(0.3f);
	ASOEnemy* Boss = Op->GetBoss();
	if (!TestNotNull(TEXT("boss spawned"), Boss))
	{
		return false;
	}
	const int32 Before = SOTest::LiveEnemies(W.World, Boss).Num();
	USOCombatStatics::ApplyDamage(Player, Boss, Boss->GetMaxHealth() * 0.3f, false);
	W.Run(0.3f);
	TestEqual(TEXT("no adds above half"), SOTest::LiveEnemies(W.World, Boss).Num(), Before);
	Boss->SetImmune(true, FText::FromString(TEXT("Shielded")));
	TestEqual(TEXT("immune boss takes nothing"), USOCombatStatics::ApplyDamage(Player, Boss, 10.0f, false), 0.0f);
	Boss->SetImmune(false);
	USOCombatStatics::ApplyDamage(Player, Boss, Boss->GetMaxHealth() * 0.3f, false);
	W.Run(0.3f);
	TestEqual(TEXT("adds at half health"), SOTest::LiveEnemies(W.World, Boss).Num(), Before + 2);
	Boss->Die(Player);
	W.Run(0.3f);
	TestEqual(TEXT("adds fall with the boss"), SOTest::LiveEnemies(W.World).Num(), 0);
	W.Run(0.5f);
	TestEqual(TEXT("complete"), Op->GetState(), ESOOperationState::Complete);

	// the reward: one piece (none of the test's options exist, so a gun of the reward rarity)
	USOInventoryComponent* Inv = PS->GetInventory();
	const int32 Guns = Inv->GetItems().Num();
	FRandomStream Rng(7);
	const FString Label = Op->GrantReward(PS, Inv, Rng);
	TestFalse(TEXT("reward has a name"), Label.IsEmpty());
	TestEqual(TEXT("one gun added"), Inv->GetItems().Num(), Guns + 1);
	TestEqual(TEXT("reward is legendary"), Inv->GetItems().Last().Rarity, 3);
	TestEqual(TEXT("reward recorded for the squad"), Op->GetRewards().Num(), 1);

	// an earned armour piece: one copy, raised by a second drop, never handed out with the wardrobe
	const FSOArmorInstance A = Inv->AddArmorPiece(TEXT("head"), TEXT("test_piece"), 3, 20, false);
	const FSOArmorInstance B = Inv->AddArmorPiece(TEXT("head"), TEXT("test_piece"), 4, 25, false);
	TestEqual(TEXT("same piece"), A.Uid, B.Uid);
	TestEqual(TEXT("raised rarity"), B.Rarity, 4);
	TestEqual(TEXT("raised power"), B.Power, 25);
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
