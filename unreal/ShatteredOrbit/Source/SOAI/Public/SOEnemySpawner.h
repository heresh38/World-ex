#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "SOEnemySpawner.generated.h"

class ASOCombatCharacter;
class ASOEnemy;
class UArrowComponent;

/** Keeps one creature alive here: spawns it on begin play (server) and again RespawnDelay after it dies. */
UCLASS()
class SOAI_API ASOEnemySpawner : public AActor
{
	GENERATED_BODY()

public:
	ASOEnemySpawner();

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Spawner")
	TSubclassOf<ASOEnemy> EnemyClass;

	/** The species it spawns (USOSpeciesLibrary); set, it wins over EnemyClass. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Spawner")
	FName Species;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Spawner", meta = (Units = "s"))
	float RespawnDelay = 8.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Spawner")
	bool bSpawnOnBeginPlay = true;

	UFUNCTION(BlueprintCallable, Category = "SO|Spawner")
	ASOEnemy* SpawnEnemy();

	ASOEnemy* GetCurrent() const { return Current.Get(); }
	int32 GetSpawnCount() const { return SpawnCount; }

	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

private:
	void OnCharacterDied(ASOCombatCharacter* Victim, AActor* Killer, UWorld* World);

	UPROPERTY(VisibleAnywhere, Category = "SO|Spawner")
	TObjectPtr<UArrowComponent> Arrow;

	TWeakObjectPtr<ASOEnemy> Current;
	int32 SpawnCount = 0;
	FTimerHandle RespawnTimer;
	FDelegateHandle DiedHandle;
};
