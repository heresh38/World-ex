#include "SOOperation.h"

#include "Components/CapsuleComponent.h"
#include "Dom/JsonObject.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/GameStateBase.h"
#include "GameFramework/PlayerState.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Net/UnrealNetwork.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "SOCombatCharacter.h"
#include "SOCombatStatics.h"
#include "SOAltered.h"
#include "SOEnemy.h"
#include "SOEnemyAIController.h"
#include "SOInventoryComponent.h"
#include "SOLog.h"
#include "SOLootLibrary.h"
#include "SOLootTypes.h"
#include "SOSound.h"
#include "SOWardrobe.h"
#include "SOWeather.h"

namespace
{
	FVector Vec(const TArray<TSharedPtr<FJsonValue>>& A)
	{
		return FVector(A.Num() > 0 ? A[0]->AsNumber() : 0.0, A.Num() > 1 ? A[1]->AsNumber() : 0.0, A.Num() > 2 ? A[2]->AsNumber() : 0.0);
	}

	ESOStageKind KindOf(const FString& S)
	{
		if (S == TEXT("clear")) return ESOStageKind::Clear;
		if (S == TEXT("hold")) return ESOStageKind::Hold;
		if (S == TEXT("boss")) return ESOStageKind::Boss;
		return ESOStageKind::Travel;
	}
}

int32 FSOWave::Size() const
{
	int32 N = 0;
	for (const FSOWaveEntry& E : Entries)
	{
		N += FMath::Max(E.Count, 0);
	}
	return N;
}

ASOOperation::ASOOperation()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.TickInterval = 0.1f;
	bReplicates = true;
	bAlwaysRelevant = true;
	SetRootComponent(CreateDefaultSubobject<USceneComponent>(TEXT("Root")));
	EnemyClasses.Add(TEXT("stalker"), ASOEnemy::StaticClass());
	EnemyClasses.Add(TEXT("remnant"), ASORemnant::StaticClass());
	EnemyClasses.Add(TEXT("veilborn"), ASOVeilborn::StaticClass());
	EnemyClasses.Add(TEXT("bulwark"), ASOBulwark::StaticClass());
	EnemyClasses.Add(TEXT("colossus"), ASOColossus::StaticClass());
	Rng.Initialize(FMath::Rand());
}

ASOOperation* ASOOperation::Get(const UObject* WorldContext)
{
	UWorld* World = WorldContext ? WorldContext->GetWorld() : nullptr;
	if (!World)
	{
		return nullptr;
	}
	for (TActorIterator<ASOOperation> It(World); It; ++It)
	{
		return *It;
	}
	return nullptr;
}

bool ASOOperation::LoadPlan(const FString& JsonText)
{
	TSharedPtr<FJsonObject> Root;
	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(JsonText);
	if (!FJsonSerializer::Deserialize(Reader, Root) || !Root)
	{
		return false;
	}
	OperationName = FText::FromString(Root->GetStringField(TEXT("name")));
	Tagline = FText::FromString(Root->GetStringField(TEXT("tagline")));

	Groups.Reset();
	if (const TSharedPtr<FJsonObject>* G = nullptr; Root->TryGetObjectField(TEXT("groups"), G))
	{
		for (const TPair<FString, TSharedPtr<FJsonValue>>& Pair : (*G)->Values)
		{
			const TSharedPtr<FJsonObject> O = Pair.Value->AsObject();
			FSOSpawnGroup Group;
			Group.Yaw = O->GetNumberField(TEXT("yaw"));
			for (const TSharedPtr<FJsonValue>& P : O->GetArrayField(TEXT("points")))
			{
				Group.Points.Add(Vec(P->AsArray()));
			}
			Groups.Add(FName(Pair.Key), Group);
		}
	}

	Stages.Reset();
	for (const TSharedPtr<FJsonValue>& V : Root->GetArrayField(TEXT("stages")))
	{
		const TSharedPtr<FJsonObject> O = V->AsObject();
		FSOStage S;
		S.Id = FName(O->GetStringField(TEXT("id")));
		S.Title = FText::FromString(O->GetStringField(TEXT("title")));
		S.Objective = FText::FromString(O->GetStringField(TEXT("objective")));
		S.Kind = KindOf(O->GetStringField(TEXT("kind")));
		const TArray<TSharedPtr<FJsonValue>>* Arr = nullptr;
		if (O->TryGetArrayField(TEXT("goal"), Arr))
		{
			S.Goal = Vec(*Arr);
		}
		O->TryGetNumberField(TEXT("radius"), S.GoalRadius);
		O->TryGetNumberField(TEXT("hold"), S.HoldTime);
		FString BossKind;
		if (O->TryGetStringField(TEXT("boss"), BossKind))
		{
			S.Boss = FName(BossKind);
			S.BossGroup = FName(O->GetStringField(TEXT("bossGroup")));
		}
		if (O->TryGetArrayField(TEXT("checkpoint"), Arr) && Arr->Num() >= 4)
		{
			S.bCheckpoint = true;
			S.Checkpoint = FTransform(FRotator(0.0, (*Arr)[3]->AsNumber(), 0.0), Vec(*Arr));
		}
		if (O->TryGetArrayField(TEXT("waves"), Arr))
		{
			for (const TSharedPtr<FJsonValue>& WV : *Arr)
			{
				const TSharedPtr<FJsonObject> WO = WV->AsObject();
				FSOWave Wave;
				WO->TryGetNumberField(TEXT("delay"), Wave.Delay);
				WO->TryGetNumberField(TEXT("maxAlive"), Wave.MaxAlive);
				WO->TryGetNumberField(TEXT("bossHealth"), Wave.BossHealth);
				for (const TSharedPtr<FJsonValue>& EV : WO->GetArrayField(TEXT("spawn")))
				{
					const TArray<TSharedPtr<FJsonValue>>& E = EV->AsArray();
					if (E.Num() >= 3)
					{
						Wave.Entries.Add({ FName(E[0]->AsString()), static_cast<int32>(E[1]->AsNumber()), FName(E[2]->AsString()) });
					}
				}
				S.Waves.Add(Wave);
			}
		}
		Stages.Add(S);
	}

	Rewards.Reset();
	if (const TSharedPtr<FJsonObject>* R = nullptr; Root->TryGetObjectField(TEXT("rewards"), R))
	{
		(*R)->TryGetNumberField(TEXT("rarity"), RewardRarity);
		const TArray<TSharedPtr<FJsonValue>>* Arr = nullptr;
		if ((*R)->TryGetArrayField(TEXT("armor"), Arr))
		{
			for (const TSharedPtr<FJsonValue>& A : *Arr)
			{
				const TArray<TSharedPtr<FJsonValue>>& P = A->AsArray();
				FSOOperationRewardOption Opt;
				Opt.Slot = FName(P[0]->AsString());
				Opt.Item = FName(P[1]->AsString());
				Rewards.Add(Opt);
			}
		}
		if ((*R)->TryGetArrayField(TEXT("weapons"), Arr))
		{
			for (const TSharedPtr<FJsonValue>& A : *Arr)
			{
				FSOOperationRewardOption Opt;
				Opt.Archetype = FName(A->AsString());
				Rewards.Add(Opt);
			}
		}
	}
	return Stages.Num() > 0;
}

void ASOOperation::BeginPlay()
{
	Super::BeginPlay();
	if (!PlanFile.IsEmpty())
	{
		FString Text;
		if (FFileHelper::LoadFileToString(Text, *(FPaths::ProjectDir() / PlanFile)) && LoadPlan(Text))
		{
			UE_LOG(LogShatteredOrbit, Log, TEXT("Operation %s: %d stages, %d spawn groups, %d rewards"), *OperationName.ToString(), Stages.Num(), Groups.Num(), Rewards.Num());
		}
		else
		{
			UE_LOG(LogShatteredOrbit, Warning, TEXT("Operation: could not read the plan %s"), *PlanFile);
		}
	}
	if (USOWeatherSubsystem* Weather = bStorm ? GetWorld()->GetSubsystem<USOWeatherSubsystem>() : nullptr)
	{
		Weather->bAutomatic = false;
		Weather->SetWeather(ESOWeather::Storm, 0.0f);
		Weather->SetWetness(0.85f);
	}
	if (HasAuthority())
	{
		DiedHandle = USOCombatStatics::OnCharacterDied().AddUObject(this, &ASOOperation::OnCharacterDied);
		if (StartDelay >= 0.0f && Stages.Num() > 0)
		{
			AdvanceAt = GetWorld()->GetTimeSeconds() + StartDelay;
		}
	}
}

void ASOOperation::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	USOCombatStatics::OnCharacterDied().Remove(DiedHandle);
	Super::EndPlay(EndPlayReason);
}

void ASOOperation::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
	Super::GetLifetimeReplicatedProps(OutLifetimeProps);
	DOREPLIFETIME(ASOOperation, State);
	DOREPLIFETIME(ASOOperation, StageIndex);
	DOREPLIFETIME(ASOOperation, Kills);
	DOREPLIFETIME(ASOOperation, GoalCount);
	DOREPLIFETIME(ASOOperation, StageStart);
	DOREPLIFETIME(ASOOperation, Boss);
	DOREPLIFETIME(ASOOperation, Granted);
}

float ASOOperation::GetStageAge() const
{
	const UWorld* World = GetWorld();
	const AGameStateBase* GS = World ? World->GetGameState() : nullptr;
	const float Now = GS ? GS->GetServerWorldTimeSeconds() : (World ? World->GetTimeSeconds() : 0.0f);
	return Now - StageStart;
}

float ASOOperation::GetHoldLeft() const
{
	const FSOStage* S = GetStage();
	return S && S->Kind == ESOStageKind::Hold ? FMath::Max(0.0f, S->HoldTime - GetStageAge()) : 0.0f;
}

int32 ASOOperation::GetAlive() const
{
	int32 N = 0;
	for (const TWeakObjectPtr<ASOEnemy>& E : Alive)
	{
		N += E.IsValid() && !E->IsDead();
	}
	return N;
}

FString ASOOperation::GetObjectiveLine() const
{
	if (State == ESOOperationState::Complete)
	{
		return TEXT("Operation complete");
	}
	const FSOStage* S = GetStage();
	if (!S)
	{
		return TEXT("Stand by");
	}
	const FString Text = S->Objective.ToString();
	switch (S->Kind)
	{
	case ESOStageKind::Clear:
		return FString::Printf(TEXT("%s   %d / %d"), *Text, FMath::Min(Kills, GoalCount), GoalCount);
	case ESOStageKind::Hold:
	{
		const int32 Left = FMath::CeilToInt(GetHoldLeft());
		return FString::Printf(TEXT("%s   %d:%02d"), *Text, Left / 60, Left % 60);
	}
	default:
		return Text;
	}
}

bool ASOOperation::GetCheckpoint(FTransform& Out) const
{
	for (int32 i = FMath::Min(StageIndex, Stages.Num() - 1); i >= 0; --i)
	{
		if (Stages[i].bCheckpoint)
		{
			Out = Stages[i].Checkpoint;
			return true;
		}
	}
	return false;
}

TArray<ASOCombatCharacter*> ASOOperation::Players() const
{
	TArray<ASOCombatCharacter*> Out;
	for (TActorIterator<ASOCombatCharacter> It(GetWorld()); It; ++It)
	{
		if (It->Faction == ESOFaction::Player && !It->IsDead())
		{
			Out.Add(*It);
		}
	}
	return Out;
}

void ASOOperation::Begin()
{
	if (HasAuthority() && Stages.Num() > 0)
	{
		AdvanceAt = -1.0f;
		StartStage(0);
	}
}

void ASOOperation::AdvanceStage()
{
	if (!HasAuthority())
	{
		return;
	}
	AdvanceAt = -1.0f;
	if (StageIndex + 1 < Stages.Num())
	{
		StartStage(StageIndex + 1);
	}
	else
	{
		Complete();
	}
}

void ASOOperation::StartStage(int32 Index)
{
	const FSOStage& S = Stages[Index];
	StageIndex = Index;
	State = ESOOperationState::Active;
	StageStart = GetWorld()->GetTimeSeconds();
	Kills = 0;
	GoalCount = 0;
	NextWave = 0;
	LastWaveTime = StageStart;
	bHoldDone = false;
	Alive.Reset();
	Boss = nullptr;
	if (S.Kind == ESOStageKind::Clear)
	{
		for (const FSOWave& W : S.Waves)
		{
			GoalCount += W.Size();
		}
	}
	if (S.Kind == ESOStageKind::Boss && !S.Boss.IsNone())
	{
		Boss = SpawnEnemy(S.Boss, S.BossGroup, 0);
		GoalCount = 1;
	}
	UE_LOG(LogShatteredOrbit, Log, TEXT("Operation stage %d: %s (%s)"), Index, *S.Title.ToString(), *S.Objective.ToString());
	OnRep_Stage();
}

void ASOOperation::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (!HasAuthority())
	{
		return;
	}
	const float Now = GetWorld()->GetTimeSeconds();
	if (AdvanceAt >= 0.0f)
	{
		if (Now >= AdvanceAt)
		{
			AdvanceStage();
		}
		return;
	}
	if (State == ESOOperationState::Active)
	{
		TickStage();
	}
}

void ASOOperation::TickStage()
{
	const FSOStage& S = Stages[StageIndex];
	const float Now = GetWorld()->GetTimeSeconds();
	Alive.RemoveAll([](const TWeakObjectPtr<ASOEnemy>& E) { return !E.IsValid() || E->IsDead(); });

	// the next wave, when its turn comes
	const float BossHealth = Boss ? Boss->GetHealth() / FMath::Max(Boss->GetMaxHealth(), 1.0f) : 1.0f;
	if (S.Waves.IsValidIndex(NextWave))
	{
		const FSOWave& W = S.Waves[NextWave];
		const bool bReady = W.BossHealth >= 0.0f
			? (Boss && !Boss->IsDead() && BossHealth <= W.BossHealth)
			: (Now - LastWaveTime >= W.Delay && Alive.Num() <= W.MaxAlive);
		if (bReady)
		{
			SpawnWave(W);
			++NextWave;
			LastWaveTime = Now;
		}
	}
	else if (S.Kind == ESOStageKind::Hold && S.Waves.Num() > 0 && Now - StageStart < S.HoldTime)
	{
		// a hold never runs dry: the last wave comes again while the timer runs
		const FSOWave& W = S.Waves.Last();
		if (Now - LastWaveTime >= FMath::Max(W.Delay, 4.0f) && Alive.Num() <= W.MaxAlive)
		{
			SpawnWave(W);
			LastWaveTime = Now;
		}
	}

	bool bDone = false;
	switch (S.Kind)
	{
	case ESOStageKind::Travel:
		for (const ASOCombatCharacter* P : Players())
		{
			const FVector D = P->GetActorLocation() - S.Goal;
			bDone |= D.Size2D() <= S.GoalRadius && FMath::Abs(D.Z) < 800.0f;
		}
		break;
	case ESOStageKind::Clear:
		bDone = NextWave >= S.Waves.Num() && Alive.Num() == 0;
		break;
	case ESOStageKind::Hold:
		bDone = Now - StageStart >= S.HoldTime;
		break;
	case ESOStageKind::Boss:
		bDone = !Boss || Boss->IsDead();
		break;
	}
	if (bDone)
	{
		UE_LOG(LogShatteredOrbit, Log, TEXT("Operation stage %d done (%d kills)"), StageIndex, Kills);
		if (S.Kind == ESOStageKind::Boss)
		{
			// the boss's thralls fall with it
			const TArray<TWeakObjectPtr<ASOEnemy>> Thralls = MoveTemp(Alive); // their deaths edit Alive
			for (const TWeakObjectPtr<ASOEnemy>& E : Thralls)
			{
				if (E.IsValid() && !E->IsDead())
				{
					E->Die(nullptr);
				}
			}
			Alive.Reset();
		}
		AdvanceAt = Now + StageGap;
	}
}

void ASOOperation::SpawnWave(const FSOWave& Wave)
{
	for (const FSOWaveEntry& E : Wave.Entries)
	{
		for (int32 i = 0; i < E.Count; ++i)
		{
			if (ASOEnemy* Enemy = SpawnEnemy(E.Enemy, E.Group, i))
			{
				Alive.Add(Enemy);
			}
		}
	}
}

ASOEnemy* ASOOperation::SpawnEnemy(FName Kind, FName Group, int32 Index)
{
	const TSubclassOf<ASOEnemy>* Class = EnemyClasses.Find(Kind);
	const FSOSpawnGroup* G = Groups.Find(Group);
	if (!Class || !*Class || !G || G->Points.Num() == 0)
	{
		UE_LOG(LogShatteredOrbit, Warning, TEXT("Operation: no enemy '%s' or spawn group '%s'"), *Kind.ToString(), *Group.ToString());
		return nullptr;
	}
	const ASOEnemy* Cdo = Class->GetDefaultObject();
	const float Half = Cdo->GetCapsuleComponent()->GetScaledCapsuleHalfHeight();
	const float Radius = Cdo->GetCapsuleComponent()->GetScaledCapsuleRadius();
	// round the group's points; a second lap steps out so a crowd does not stack
	const int32 Lap = Index / G->Points.Num();
	const float A = Index * 2.39996f;
	const FVector Spread = Lap > 0 ? FVector(FMath::Cos(A), FMath::Sin(A), 0.0f) * Radius * 2.6f * Lap : FVector::ZeroVector;
	const FVector Point = G->Points[Index % G->Points.Num()] + Spread + FVector(0, 0, Half + 5.0f);
	FActorSpawnParameters Params;
	Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AdjustIfPossibleButAlwaysSpawn;
	ASOEnemy* Enemy = GetWorld()->SpawnActor<ASOEnemy>(*Class, Point, FRotator(0.0f, G->Yaw, 0.0f), Params);
	if (!Enemy)
	{
		return nullptr;
	}
	if (!Enemy->GetController())
	{
		Enemy->SpawnDefaultController();
	}
	if (ASOEnemyAIController* AI = Cast<ASOEnemyAIController>(Enemy->GetController()))
	{
		AI->bHunter = true; // an operation's enemies know where the players are
	}
	return Enemy;
}

void ASOOperation::OnCharacterDied(ASOCombatCharacter* Victim, AActor* Killer, UWorld* World)
{
	if (World != GetWorld() || !Victim)
	{
		return;
	}
	const int32 Before = Alive.Num();
	Alive.RemoveAll([Victim](const TWeakObjectPtr<ASOEnemy>& E) { return E.Get() == Victim; });
	if (Alive.Num() < Before || Victim == Boss)
	{
		++Kills;
	}
}

TArray<FSOOperationRewardOption> ASOOperation::AvailableRewards(const USOInventoryComponent* Inventory) const
{
	TArray<FSOOperationRewardOption> Out;
	const USOWardrobeData* Wardrobe = Inventory ? USOWardrobeData::Get(Inventory->GetBody()) : nullptr;
	const USOLootTables* Tables = USOLootLibrary::GetTables();
	for (const FSOOperationRewardOption& R : Rewards)
	{
		if (R.IsArmor() ? (Wardrobe && Wardrobe->Find(R.Slot, R.Item)) : (Tables && Tables->LoadArchetype(R.Archetype)))
		{
			Out.Add(R);
		}
	}
	return Out;
}

FString ASOOperation::GrantReward(APlayerState* Player, USOInventoryComponent* Inventory, FRandomStream& Stream)
{
	if (!Inventory)
	{
		return FString();
	}
	const TArray<FSOOperationRewardOption> Options = AvailableRewards(Inventory);
	FSOOperationReward Reward;
	Reward.Player = Player;
	Reward.Rarity = RewardRarity;
	const FString Source = OperationName.ToString();
	if (Options.Num() == 0)
	{
		// the sets are not in the game yet: a gun of the reward's rarity instead
		FSORollOptions Roll;
		Roll.Rarity = RewardRarity;
		Roll.Source = Source;
		const FSOWeaponInstance W = Inventory->AddWeapon(USOLootLibrary::RollWeapon(Inventory->GetPower() + 2, Roll, Stream));
		Reward.Label = W.Name;
	}
	else
	{
		// one random piece; the ones this player does not own yet are three times as likely
		TArray<float> Weights;
		float Total = 0.0f;
		for (const FSOOperationRewardOption& O : Options)
		{
			const bool bOwned = O.IsArmor()
				? Inventory->GetArmor().ContainsByPredicate([&](const FSOArmorInstance& A) { return A.Slot == O.Slot && A.Item == O.Item; })
				: Inventory->GetItems().ContainsByPredicate([&](const FSOWeaponInstance& W) { return W.Archetype == O.Archetype; });
			Weights.Add(bOwned ? 1.0f : 3.0f);
			Total += Weights.Last();
		}
		float Pick = Stream.FRandRange(0.0f, Total);
		int32 Chosen = Options.Num() - 1;
		for (int32 i = 0; i < Options.Num(); ++i)
		{
			Pick -= Weights[i];
			if (Pick <= 0.0f)
			{
				Chosen = i;
				break;
			}
		}
		const FSOOperationRewardOption& O = Options[Chosen];
		if (O.IsArmor())
		{
			const FSOArmorInstance A = Inventory->AddArmorPiece(O.Slot, O.Item, RewardRarity, Inventory->GetPower() + 2);
			const USOWardrobeData* Wardrobe = USOWardrobeData::Get(Inventory->GetBody());
			const FSOWardrobeItem* Item = Wardrobe ? Wardrobe->Find(A.Slot, A.Item) : nullptr;
			Reward.Label = Item ? Item->Label.ToString() : A.Item.ToString();
		}
		else
		{
			FSOWeaponInstance W = USOLootLibrary::MakeWeapon(O.Archetype, RewardRarity, Inventory->GetPower() + 2, Stream);
			W.Source = Source;
			W = Inventory->AddWeapon(W);
			Reward.Label = W.Name;
		}
	}
	Granted.Add(Reward);
	return Reward.Label;
}

void ASOOperation::Complete()
{
	State = ESOOperationState::Complete;
	StageStart = GetWorld()->GetTimeSeconds();
	for (FConstPlayerControllerIterator It = GetWorld()->GetPlayerControllerIterator(); It; ++It)
	{
		APlayerController* PC = It->Get();
		APlayerState* PS = PC ? PC->PlayerState : nullptr;
		USOInventoryComponent* Inventory = PS ? PS->FindComponentByClass<USOInventoryComponent>() : nullptr;
		if (!Inventory)
		{
			continue;
		}
		const FString Label = GrantReward(PS, Inventory, Rng);
		Inventory->AddCredits(1500 + Inventory->GetLevel() * 40);
		Inventory->AddAlloy(20 + Rng.RandRange(0, 10));
		Inventory->AddXp(4000);
		UE_LOG(LogShatteredOrbit, Log, TEXT("Operation complete: %s earned %s"), *PS->GetPlayerName(), *Label);
	}
	OnRep_Stage();
}

void ASOOperation::OnRep_Stage()
{
	if (HasActorBegunPlay())
	{
		USOSoundLibrary::Play2D(this, State == ESOOperationState::Complete ? TEXT("reliquary_open") : TEXT("ui_open"), 0.7f, 0.0f);
	}
	OnStageChanged.Broadcast(StageIndex, State);
}
