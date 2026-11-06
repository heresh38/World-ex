#pragma once

#include "CoreMinimal.h"
#include "GameFramework/PlayerState.h"
#include "SOPlayerState.generated.h"

/** Replicated per-player state. The ability system component moves here in stage 3. */
UCLASS()
class SHATTEREDORBIT_API ASOPlayerState : public APlayerState
{
	GENERATED_BODY()

public:
	ASOPlayerState();
};
