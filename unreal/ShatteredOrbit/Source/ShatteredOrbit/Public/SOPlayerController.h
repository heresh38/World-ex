#pragma once

#include "CoreMinimal.h"
#include "GameFramework/PlayerController.h"
#include "SOPlayerController.generated.h"

class UInputMappingContext;

/** Adds the default input mapping context (keyboard / mouse + gamepad) for the local player. */
UCLASS()
class SHATTEREDORBIT_API ASOPlayerController : public APlayerController
{
	GENERATED_BODY()

public:
	ASOPlayerController();

	UPROPERTY(EditDefaultsOnly, Category = "SO|Input")
	TSoftObjectPtr<UInputMappingContext> DefaultMappingContext;

	UPROPERTY(EditDefaultsOnly, Category = "SO|Input")
	int32 DefaultMappingPriority = 0;

	/** Adds DefaultMappingContext to the local player's Enhanced Input subsystem; false if it is missing. */
	bool AddDefaultMappingContext();

protected:
	virtual void BeginPlay() override;
};
