#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "SOGameMode.generated.h"

/** Default game mode: SOCharacter pawn, SOPlayerController, SOPlayerState. Server-authoritative from day one. */
UCLASS()
class SHATTEREDORBIT_API ASOGameMode : public AGameModeBase
{
	GENERATED_BODY()

public:
	ASOGameMode();
};
