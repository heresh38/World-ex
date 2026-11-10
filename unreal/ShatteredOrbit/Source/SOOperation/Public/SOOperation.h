#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "SOSpecies.h"
#include "SOOperation.generated.h"

class APlayerState;
class ASOCombatCharacter;
class ASOEnemy;
class USOInventoryComponent;
class FJsonObject;

UENUM(BlueprintType)
enum class ESOStageKind : uint8
{
	/** Get a player to the goal. */
	Travel,
	/** Kill every enemy of every wave. */
	Clear,
	/** Survive until the timer runs out while the waves keep coming. */
	Hold,
	/** Kill the boss (its adds come with waves keyed to its health). */
	Boss
};

UENUM(BlueprintType)
enum class ESOOperationState : uint8
{
	Waiting,
	Active,
	Complete
};

/** Some enemies of one kind at one spawn group. */
USTRUCT(BlueprintType)
struct SOOPERATION_API FSOWaveEntry
{
	GENERATED_BODY()

	/** A species (USOSpeciesLibrary) or one of this operation's variants of one. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Operation")
	FName Enemy;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Operation")
	int32 Count = 1;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Operation")
	FName Group;
};

/**
 * One wave of a stage. It comes once the previous wave is out, Delay seconds have passed since then, and no more than
 * MaxAlive of the stage's enemies are still standing; a boss stage's waves can instead wait for the boss's health to
 * fall to BossHealth.
 */
USTRUCT(BlueprintType)
struct SOOPERATION_API FSOWave
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Operation")
	TArray<FSOWaveEntry> Entries;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Operation", meta = (Units = "s"))
	float Delay = 0.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Operation")
	int32 MaxAlive = 0;

	/** Hunters know where the players are (reinforcements); a garrison (false) stands its ground unaware until it
	 *  sees, hears or is hurt by someone, so it can be crept up on. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Operation")
	bool bHunt = true;

	/** Boss stages: comes when the boss's health fraction is at or below this (negative = not keyed to the boss). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Operation")
	float BossHealth = -1.0f;

	int32 Size() const;
};

USTRUCT(BlueprintType)
struct SOOPERATION_API FSOStage
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Operation")
	FName Id;

	/** The place ("Meridian Gate"), shown big when the stage begins. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Operation")
	FText Title;

	/** What to do ("Break the hold on the gate"). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Operation")
	FText Objective;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Operation")
	ESOStageKind Kind = ESOStageKind::Travel;

	/** Where the objective is (marker on screen; Travel: where to go). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Operation")
	FVector Goal = FVector::ZeroVector;

	/** Travel: how close counts as arrived (cm). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Operation")
	float GoalRadius = 800.0f;

	/** Hold: seconds to hold. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Operation", meta = (Units = "s"))
	float HoldTime = 0.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Operation")
	TArray<FSOWave> Waves;

	/** Boss: the boss's kind and spawn group. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Operation")
	FName Boss;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Operation")
	FName BossGroup;

	/** Where players come back once this stage has begun (unset = the previous stage's). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Operation")
	bool bCheckpoint = false;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Operation")
	FTransform Checkpoint;
};

/** One possible reward: an armour piece (Slot + Item of the wardrobe) or a gun (Archetype). */
USTRUCT(BlueprintType)
struct SOOPERATION_API FSOOperationRewardOption
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Operation")
	FName Slot;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Operation")
	FName Item;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Operation")
	FName Archetype;

	bool IsArmor() const { return !Slot.IsNone(); }
};

/** What a player got for finishing (replicated to everyone: the squad sees each other's drops). */
USTRUCT(BlueprintType)
struct SOOPERATION_API FSOOperationReward
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Operation")
	TObjectPtr<APlayerState> Player;

	UPROPERTY(BlueprintReadOnly, Category = "Operation")
	FString Label;

	UPROPERTY(BlueprintReadOnly, Category = "Operation")
	int32 Rarity = 3;
};

/** A spawn group: where a wave's enemies appear. */
USTRUCT()
struct SOOPERATION_API FSOSpawnGroup
{
	GENERATED_BODY()

	UPROPERTY()
	TArray<FVector> Points;

	/** Which way the enemies face when they appear (yaw, degrees). */
	UPROPERTY()
	float Yaw = 0.0f;
};

DECLARE_MULTICAST_DELEGATE_TwoParams(FSOOnStageChanged, int32 /*Stage*/, ESOOperationState /*State*/);

/**
 * An operation: a linear run through an area in stages (travel, clear, hold, boss), each with its waves and a
 * checkpoint where fallen players come back; finishing it grants every player one random piece of its reward sets
 * (an armour piece or a gun). One per level. The plan (stages, waves, spawn groups, rewards) is read from a json file
 * (PlanFile, written by tools/operation/<name>_plan.py), so the level's geometry and its mission share one source.
 * Server-authoritative; clients get the stage, progress, boss and rewards.
 *
 * It holds NO creature code: its waves name species (USOSpeciesLibrary: each written once, the same in every
 * operation) and spawn them through the library. What an operation may add for itself is data in its plan:
 * "enemies" (a baseline for all of them: {"health": 1.2, "damage": 1.1}) and "variants" (named dressings of a
 * species: {"remnant_ashen": {"species": "remnant", "name": "Ashen Remnant", "health": 1.6, "weapon": "shotgun"}};
 * waves then spawn "remnant_ashen" like any species). It loads the species it uses when the level starts and
 * holds them only while it runs.
 */
UCLASS()
class SOOPERATION_API ASOOperation : public AActor
{
	GENERATED_BODY()

public:
	ASOOperation();

	/** Relative to the project directory (Data/op_meridian.json). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Operation")
	FString PlanFile;

	/** Seconds after the level begins before the first stage starts. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Operation", meta = (Units = "s"))
	float StartDelay = 3.0f;

	/** Seconds between a stage being done and the next one starting. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Operation", meta = (Units = "s"))
	float StageGap = 2.5f;

	/** This operation's dressings of species, by the name its waves use. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Operation")
	TMap<FName, FSOSpeciesVariant> Variants;

	/** On every creature of this operation (under its variant, if it has one). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Operation")
	FSOSpeciesVariant Baseline;

	/** A wave's enemy name -> the species it is and what this operation puts on top (false: no such creature). */
	bool ResolveEnemy(FName Name, FName& OutSpecies, FSOSpeciesVariant& OutVariant) const;

	/** Every enemy name the plan's stages use. */
	TArray<FName> GetEnemyNames() const;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Operation")
	FText OperationName;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Operation")
	FText Tagline;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Operation")
	TArray<FSOStage> Stages;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Operation")
	TArray<FSOOperationRewardOption> Rewards;

	/** The sky while the operation runs (the weather stays put). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Operation")
	bool bStorm = true;

	/** The rarity a reward drops at (3 = Legendary). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Operation")
	int32 RewardRarity = 3;

	TMap<FName, FSOSpawnGroup> Groups;

	/** The level's operation (null if it has none). */
	static ASOOperation* Get(const UObject* WorldContext);

	/** Reads a plan from json text (all machines; replaces the stages, groups and rewards). */
	bool LoadPlan(const FString& JsonText);

	// --- State (replicated) ---
	ESOOperationState GetState() const { return State; }
	int32 GetStageIndex() const { return StageIndex; }
	const FSOStage* GetStage() const { return Stages.IsValidIndex(StageIndex) ? &Stages[StageIndex] : nullptr; }
	/** Seconds since the current stage began (client clock). */
	float GetStageAge() const;
	/** Clear: kills / enemies of the stage so far. Hold: seconds left. */
	int32 GetKills() const { return Kills; }
	int32 GetGoalCount() const { return GoalCount; }
	float GetHoldLeft() const;
	ASOEnemy* GetBoss() const { return Boss; }
	const TArray<FSOOperationReward>& GetRewards() const { return Granted; }
	/** The objective as one line ("Break the hold on the gate  12 / 20"). */
	FString GetObjectiveLine() const;
	/** Where fallen players come back (false = no checkpoint yet: the level's player start). */
	bool GetCheckpoint(FTransform& Out) const;
	int32 GetAlive() const;

	// --- Server ---
	/** Starts the first stage now. */
	void Begin();
	/** Ends the current stage and starts the next (or completes the operation). */
	void AdvanceStage();
	/** Grants Player one random reward (exposed for tests). Returns its label. */
	FString GrantReward(APlayerState* Player, USOInventoryComponent* Inventory, FRandomStream& Rng);
	/** The options a player can still use: pieces their body has in its wardrobe and guns that exist. */
	TArray<FSOOperationRewardOption> AvailableRewards(const USOInventoryComponent* Inventory) const;

	FSOOnStageChanged OnStageChanged;

	//~ AActor
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
	virtual void Tick(float DeltaSeconds) override;
	virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;

protected:
	void StartStage(int32 Index);
	void TickStage();
	void SpawnWave(const FSOWave& Wave);
	ASOEnemy* SpawnEnemy(FName Kind, FName Group, int32 Index, bool bHunt = true);
	void Complete();
	void OnCharacterDied(ASOCombatCharacter* Victim, AActor* Killer, UWorld* World);
	TArray<ASOCombatCharacter*> Players() const;

	UFUNCTION()
	void OnRep_Stage();

	UPROPERTY(ReplicatedUsing = OnRep_Stage)
	ESOOperationState State = ESOOperationState::Waiting;

	UPROPERTY(ReplicatedUsing = OnRep_Stage)
	int32 StageIndex = -1;

	UPROPERTY(Replicated)
	int32 Kills = 0;

	UPROPERTY(Replicated)
	int32 GoalCount = 0;

	/** Server time the current stage began / a hold ends. */
	UPROPERTY(Replicated)
	float StageStart = 0.0f;

	UPROPERTY(Replicated)
	TObjectPtr<ASOEnemy> Boss;

	UPROPERTY(Replicated)
	TArray<FSOOperationReward> Granted;

	/** What its species need to appear, held while the operation's level runs. */
	UPROPERTY(Transient)
	TArray<TObjectPtr<UObject>> HeldContent;

	/** Server: the stage's enemies still standing, its next wave, when the last wave came, the hold's loop. */
	TArray<TWeakObjectPtr<ASOEnemy>> Alive;
	int32 NextWave = 0;
	float LastWaveTime = 0.0f;
	float AdvanceAt = -1.0f;
	bool bHoldDone = false;
	FDelegateHandle DiedHandle;
	FRandomStream Rng;
};
