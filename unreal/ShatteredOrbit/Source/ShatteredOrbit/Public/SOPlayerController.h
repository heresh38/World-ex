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

	/** Dev: screenshots into Saved/Screenshots/SO_*.png (first person: hip, firing, sights, mag change, rack, looking
	 *  down; third person: behind, aiming, and side / front / rack views from a free camera), then quits if
	 *  bQuitWhenDone. Run: -game -RenderOffscreen -ExecCmds="SOCaptureSeries 1".
	 *  Set 1: the hold study instead (every gun: hip, aimed, mid-reload, third person from both sides; files h<NN>_*). */
	UFUNCTION(Exec)
	void SOCaptureSeries(int32 bQuitWhenDone = 0, int32 Set = 0);

	/** Dev: after a warm-up, measures frame / game / render / GPU times for Seconds and logs avg + 95th percentile.
	 *  e.g. -game -windowed -ResX=2560 -ResY=1440 -ExecCmds="SOBenchmark 15 1" */
	UFUNCTION(Exec)
	void SOBenchmark(float Seconds = 15.0f, int32 bQuitWhenDone = 0);

	/** Dev: one of the face's sliders (e.g. SOFace jaw 0.6; SOFace all 0 sets every one back), saved with the profile. */
	UFUNCTION(Exec)
	void SOFace(const FString& Key, float Value = 1.0f);

	/** Dev: what the effects cost now (particles alive, the most at once, the last and the worst frame's work on the
	 *  game thread, how many gave way for the cap) and the rain round the eye. SOFxStats 1 starts the peaks over. */
	UFUNCTION(Exec)
	void SOFxStats(int32 bReset = 0);

	virtual void PlayerTick(float DeltaTime) override;

protected:
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

	/** The game's window lost or regained the foreground. */
	void OnWindowActivation(bool bActive);
	FDelegateHandle ActivationHandle;

private:
	// Developer tools (SOPlayerControllerDev.cpp: empty bodies in a shipping build)
	void DevTick(float DeltaTime);
	/** Before the frame's input: a capture's turn of the view goes in where a mouse's does, so the body faces it in the
	 *  same frame (set after the input, the body faced the turn a frame late and the shoulder camera shook against it). */
	void DevPreTick(float DeltaTime);
	/** -SONetCheck=host|join on the command line starts the two-player check on this machine's own controller. */
	void DevBegin();
	void CaptureStep();
	/** Set 38, the HUD in play (SOPlayerControllerHudDev.cpp). */
	void CaptureHud();
	/** A capture cue runs Action once Delay seconds have passed since the previous cue and Ready (if any) is true. */
	struct FCaptureCue
	{
		float Delay = 0.5f;
		TFunction<bool()> Ready;
		TFunction<void()> Action;
	};
	TArray<FCaptureCue> CaptureCues;
	int32 CaptureIndex = 0;
	float CaptureWait = 0.0f;
	/** Forward move input the capture series holds down (fed in PlayerTick, where real input arrives, before the movement tick). */
	FVector2D CaptureMove = FVector2D::ZeroVector;   // x right, y forward
	/** How fast the capture series turns the view (degrees a second, + to the right). */
	float CaptureTurn = 0.0f;
	UPROPERTY(Transient)
	TObjectPtr<AActor> CaptureCamera;
	float BenchWarmup = -1.0f;
	float BenchLeft = 0.0f;
	bool bBenchQuit = false;
	TArray<float> BenchFrame, BenchGame, BenchRender, BenchGpu;
	void FinishBenchmark();
	bool bCaptureQuit = false;
	FTimerHandle CaptureTimer;
};
