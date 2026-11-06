#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "SOGameMode.generated.h"

class ASOCombatCharacter;

/**
 * Default game mode: SOCharacter pawn, SOPlayerController, SOPlayerState, SOHUD. Server-authoritative.
 * A dead player is redeployed at a player start after RespawnDelay; the old body stays a few seconds.
 */
UCLASS()
class SHATTEREDORBIT_API ASOGameMode : public AGameModeBase
{
	GENERATED_BODY()

public:
	ASOGameMode();

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Rules", meta = (Units = "s"))
	float RespawnDelay = 4.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Rules", meta = (Units = "s"))
	float BodyLifeSpan = 5.0f;

	virtual void StartPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

	/** Redeploys a dead player's controller now (also called by the respawn timer). */
	void RespawnPlayer(AController* Controller);

private:
	void OnCharacterDied(ASOCombatCharacter* Victim, AActor* Killer, UWorld* World);
	FDelegateHandle DiedHandle;
};
