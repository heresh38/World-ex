#include "SOGameMode.h"

#include "SOCharacter.h"
#include "SOPlayerController.h"
#include "SOPlayerState.h"

ASOGameMode::ASOGameMode()
{
	DefaultPawnClass = ASOCharacter::StaticClass();
	PlayerControllerClass = ASOPlayerController::StaticClass();
	PlayerStateClass = ASOPlayerState::StaticClass();
}
