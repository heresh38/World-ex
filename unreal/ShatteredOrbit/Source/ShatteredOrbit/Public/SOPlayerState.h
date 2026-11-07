#pragma once

#include "CoreMinimal.h"
#include "GameFramework/PlayerState.h"
#include "SOPlayerState.generated.h"

class USOInventoryComponent;

/** Replicated per-player state (score, name) and the player's vault + loadout (USOInventoryComponent), which outlive
 *  the pawn. The ability system lives on the pawn (ASOCombatCharacter) for now. */
UCLASS()
class SHATTEREDORBIT_API ASOPlayerState : public APlayerState
{
	GENERATED_BODY()

public:
	ASOPlayerState();

	USOInventoryComponent* GetInventory() const { return Inventory; }

protected:
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "SO|Loot")
	TObjectPtr<USOInventoryComponent> Inventory;
};
