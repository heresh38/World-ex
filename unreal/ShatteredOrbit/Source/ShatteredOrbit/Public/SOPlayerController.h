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

	/** Dev: screenshots of the hip / ADS / mid-reload / third-person views into Saved/Screenshots/SO_*.png, then
	 *  quits if bQuitWhenDone. Run headless-free: -game -RenderOffscreen -ExecCmds="SOCaptureSeries 1". */
	UFUNCTION(Exec)
	void SOCaptureSeries(int32 bQuitWhenDone = 0);

protected:
	virtual void BeginPlay() override;

private:
	void CaptureStep();
	int32 CaptureIndex = 0;
	bool bCaptureQuit = false;
	FTimerHandle CaptureTimer;
};
