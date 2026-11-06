#pragma once

#include "CoreMinimal.h"
#include "GameFramework/PlayerState.h"
#include "SOPlayerState.generated.h"

/** Replicated per-player state (score, name). The ability system lives on the pawn (ASOCombatCharacter) for now. */
UCLASS()
class SHATTEREDORBIT_API ASOPlayerState : public APlayerState
{
	GENERATED_BODY()

public:
	ASOPlayerState();
};
