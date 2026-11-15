#pragma once

#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "Subsystems/WorldSubsystem.h"
#include "SODifficulty.generated.h"

/**
 * One level of difficulty. A harder level makes the creatures BETTER, not just tougher: they notice sooner, react and
 * settle their aim faster, shoot straighter and longer, hold cover less and push sooner, flank in larger numbers and
 * use their own moves more often. Health and damage move too, a little. Every number is a scale on what the species
 * and the brain already have (1 = as written), so a level never has to know a species.
 * Source: Data/game_data.json "difficulty" -> /Game/Data/DA_Difficulty (SO_IMPORT_ONLY=difficulty).
 */
USTRUCT(BlueprintType)
struct SOAI_API FSODifficulty
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Difficulty")
	FName Id = TEXT("standard");

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Difficulty")
	FText Name;

	/** How fast a creature's awareness of someone it can see fills. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Difficulty")
	float Notice = 1.0f;

	/** The time it takes to react: to pass an alarm on, and to settle its aim on a target (under 1 = quicker). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Difficulty")
	float Reaction = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Difficulty")
	float AimError = 1.0f;

	/** How long a burst lasts, and the pause between bursts. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Difficulty")
	float Burst = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Difficulty")
	float BurstPause = 1.0f;

	/** How long it waits before pushing to where a target went out of sight (under 1 = sooner). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Difficulty")
	float Patience = 1.0f;

	/** How long it holds one piece of cover before moving to the next. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Difficulty")
	float CoverHold = 1.0f;

	/** The share of a group that goes round the side (0 to 1). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Difficulty")
	float FlankShare = 0.33f;

	/** The cooldown of the creatures' own moves (a slam, a bolt). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Difficulty")
	float AbilityCooldown = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Difficulty")
	float Health = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Difficulty")
	float Damage = 1.0f;
};

/** The game's difficulty levels. */
UCLASS(BlueprintType)
class SOAI_API USODifficultyTable : public UPrimaryDataAsset
{
	GENERATED_BODY()

public:
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Difficulty")
	TArray<FSODifficulty> Levels;

	/** The level an activity runs at when it names none. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Difficulty")
	FName Default = TEXT("standard");

	const FSODifficulty* Find(FName Id) const;
};

/**
 * The level this world runs at. An activity sets it as it begins (an operation's plan names it: "difficulty"); every
 * creature and its brain read it. Server side: brains only run there.
 */
UCLASS()
class SOAI_API USODifficultySubsystem : public UWorldSubsystem
{
	GENERATED_BODY()

public:
	/** The world's level (the table's default until one is set; "as written" if the table was never imported). */
	static const FSODifficulty& Get(const UObject* WorldContext);

	/** Sets the level by id; false (and nothing changes) if the table has no such level. Creatures already in the
	 *  world keep the health they were given; everything else follows at once. */
	bool SetLevel(FName Id);

	const FSODifficulty& GetLevel();

private:
	void Load();

	UPROPERTY(Transient)
	TObjectPtr<USODifficultyTable> Table;

	FSODifficulty Current;
	bool bLoaded = false;
};
