#pragma once

#include "CoreMinimal.h"
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

	/** This on top of Base (a level's baseline under a variant): numbers multiply, names and guns override. */
	FSOSpeciesVariant Over(const FSOSpeciesVariant& Base) const;

	/** Reads the numbers of a plan's json object ({"species": "remnant", "name": "...", "health": 1.5, "damage": ..,
	 *  "speed": .., "aim": .., "sight": .., "weapon": "shotgun"}). */
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
