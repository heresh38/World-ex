#pragma once

#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "Templates/SubclassOf.h"
#include "SOSpecies.generated.h"

class ASOEnemy;
class FJsonObject;

/**
 * Species: every kind of creature is written ONCE, as one class with everything it is (body, clips, voice, gun, numbers,
 * its own moves; the brain is the shared ASOEnemyAIController), and names itself with ASOEnemy::SpeciesId. Nothing
 * else lists them: the registry finds every class that has an id. A level never writes creature code: it asks for a
 * species by id (an operation's plan, a spawner, a script) and gets the same creature everywhere.
 *
 * What a level MAY do is dress a species up for itself with a variant: a few numbers on top of the species' own (more
 * health, harder hits, another gun, another name). A variant changes no behaviour; it goes through ASOEnemy::ApplyVariant,
 * the one place that knows how.
 */
USTRUCT(BlueprintType)
struct SOAI_API FSOSpeciesVariant
{
	GENERATED_BODY()

	/** The name the level uses for it ("remnant_ashen"). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Species")
	FName Id;

	/** The species it is made from. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Species")
	FName Species;

	/** Shown to the player (empty: the species' own name). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Species")
	FText DisplayName;

	/** Multipliers on the species' own numbers. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Species")
	float Health = 1.0f;

	/** Everything it deals: its rounds, its claws, its special moves. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Species")
	float Damage = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Species")
	float Speed = 1.0f;

	/** Below 1 it shoots straighter. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Species")
	float AimError = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Species")
	float Sight = 1.0f;

	/** Another gun (an archetype of Data/game_data.json; None: its own). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Species")
	FName Weapon;

	/** Another kit of abilities (Data/game_data.json "kits"; None: its own, if it has one). This is how a level
	 *  makes a role out of a species without writing a creature: a Remnant with the commander's kit rallies its
	 *  squad, a Veilborn with the disruptor's jams. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Species")
	FName Kit;

	/** On how long it holds the trigger and how long it waits between bursts, and on the range it likes. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Species")
	float Burst = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Species")
	float BurstPause = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Species")
	float Range = 1.0f;

	/** A suppressor (ASOEnemy::bSuppressor) / one that looks for high ground (bLikesHigh): roles made of data. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Species")
	bool bSuppressor = false;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Species")
	bool bLikesHigh = false;

	/** A boss table (Data/game_data.json "bosses"; None: its own, if it has one): this species fighting in phases,
	 *  with whatever shield and weak points the table gives it. How a level makes a boss without writing one. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Species")
	FName Boss;

	/** This on top of Base (a level's baseline under a variant): numbers multiply, names and guns override. */
	FSOSpeciesVariant Over(const FSOSpeciesVariant& Base) const;

	/** Reads the numbers of a plan's json object ({"species": "remnant", "name": "...", "health": 1.5, "damage": ..,
	 *  "speed": .., "aim": .., "sight": .., "weapon": "shotgun", "kit": "commander", "boss": "warden", "burst": 3, "burstPause": 0.6,
	 *  "range": 1.5, "suppressor": true, "high": true}). */
	static FSOSpeciesVariant FromJson(FName Id, const TSharedPtr<FJsonObject>& Object);
};

/** How one creature is put into the world. */
struct SOAI_API FSOSpawnOptions
{
	/** Knows where the players are and never gives up (reinforcements); false: stands its post unaware. */
	bool bHunter = false;

	/** The level's dressing (null: the species as written). */
	const FSOSpeciesVariant* Variant = nullptr;

	/** Which of a group this is: later ones step out round the point (a golden-angle spiral) so a crowd never stacks. */
	int32 Index = 0;

	/** Lands on the nav mesh near the point (a floor it can walk from), when the level has one. */
	bool bOnNav = true;

	/** Refuses a spot where its capsule does not fit (false: nudged out of what it touches, always spawns). */
	bool bNeedsRoom = true;
};

/**
 * Numbers by reflection: every number (float, int), switch (bool) and range (FVector2D, as two keys <name>Min /
 * <name>Max) that Base, or a class below it, lets an editor set on Object. A key is the property's name with a small
 * first letter and no "b" ("runSpeed", "usesCover"). So a number added to a species or to the brain is data the day
 * it is declared, with no table code to write.
 */
struct SOAI_API FSONumbers
{
	static bool Key(const FProperty* Property, const UClass* Base, FString& OutKey);
	static void Get(const UObject* Object, const UClass* Base, TMap<FName, float>& Out);
	/** Returns how many of Numbers it set. */
	static int32 Apply(UObject* Object, const UClass* Base, const TMap<FName, float>& Numbers);
};

/** One species' numbers (see USOSpeciesTable). */
USTRUCT(BlueprintType)
struct SOAI_API FSOSpeciesNumbers
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Species")
	FName Species;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Species")
	TMap<FName, float> Numbers;
};

/**
 * Every species' numbers as data: health, shield, speeds, sight, the range it likes, aim error, bursts, its blow, how
 * it takes a hit, its switches (uses cover, hunts in a pack, ...), and its brain's senses (view angles, how near is
 * noticed at once, how long it keeps looking, how far an alarm carries: ASOEnemyAIController takes those from the
 * same entry when it takes the creature over). Source: Data/species.json ->
 * /Game/Data/DA_Species (SO_IMPORT_ONLY=species). A creature takes its numbers from here as it is made
 * (ASOEnemy::PostActorCreated), before a level's variant scales them; what the class's constructor says is only
 * what a species gets that the file does not name. A key is the property's name with a small first letter and no
 * "b" ("runSpeed", "usesCover"; a switch is 0 or 1; a range is two keys, "burstTimeMin" / "burstTimeMax"); "health"
 * and "shield" are what it starts with. The import writes a species the file lacks into it from its class.
 * Not here: a species' body, clips, voice, capsule and its own moves (its class).
 */
UCLASS(BlueprintType)
class SOAI_API USOSpeciesTable : public UPrimaryDataAsset
{
	GENERATED_BODY()

public:
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Species")
	TArray<FSOSpeciesNumbers> Species;

	const TMap<FName, float>* Find(FName Id) const;

	static const USOSpeciesTable& Get();
};

DECLARE_MULTICAST_DELEGATE_OneParam(FSOOnEnemySpawned, ASOEnemy* /*Enemy*/);

UCLASS()
class SOAI_API USOSpeciesLibrary : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/** The class of a species (null: no such species). */
	static TSubclassOf<ASOEnemy> Find(FName Species);

	/** Every species there is, sorted. */
	UFUNCTION(BlueprintPure, Category = "SO|Species")
	static TArray<FName> GetSpecies();

	/** A species' numbers as its CLASS and its brain's class have them (the keys of USOSpeciesTable): what the
	 *  import writes into Data/species.json for a species the file does not have yet. */
	UFUNCTION(BlueprintCallable, Category = "SO|Species")
	static TMap<FName, float> GetClassNumbers(FName Species);

	/**
	 * Server: one creature of a species with its feet at (or near) Feet, facing Yaw: the same way for every level.
	 * Null when there is no such species or no free floor near the point.
	 */
	static ASOEnemy* Spawn(UWorld* World, FName Species, const FVector& Feet, float Yaw, const FSOSpawnOptions& Options = FSOSpawnOptions());

	/** Loads what a species needs to appear (body, clips, gun) and returns it, so a level can hold it while it runs:
	 *  no hitch when the first one spawns, and it all goes when the level does. */
	static void Preload(FName Species, const FSOSpeciesVariant* Variant, TArray<UObject*>& OutHeld);

	/** After every spawn through Spawn (server): a level's own extras hook in here. */
	static FSOOnEnemySpawned& OnSpawned();
};
