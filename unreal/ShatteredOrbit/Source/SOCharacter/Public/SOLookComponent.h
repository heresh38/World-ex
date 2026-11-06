#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "SOLookComponent.generated.h"

/**
 * Turns raw look input into control rotation.
 * Mouse: counts * MouseDegreesPerCount * MouseSensitivity. Gamepad: response curve |v|^exp, then degrees per second.
 * While aiming the result is scaled by AimSensitivityMultiplier and, with zoom matching, by
 * tan(zoomedFov/2) / tan(hipFov/2) so the same mouse motion covers the same screen distance.
 * Optional smoothing: exponential, time constant AimSmoothing * 0.06 s, applied to the turn rate.
 */
UCLASS(ClassGroup = (ShatteredOrbit), meta = (BlueprintSpawnableComponent))
class SOCHARACTER_API USOLookComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	USOLookComponent();

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Look")
	float MouseDegreesPerCount = 0.07f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Look")
	float GamepadYawRate = 230.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Look")
	float GamepadPitchRate = 160.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Look")
	float MouseSensitivity = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Look")
	float AimSensitivityMultiplier = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Look")
	float GamepadSensitivity = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Look")
	float GamepadResponseExponent = 2.0f;

	/** 0..1 setting; time constant = AimSmoothing * SmoothingTimeScale. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Look")
	float AimSmoothing = 0.3f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Look")
	float SmoothingTimeScale = 0.06f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Look")
	bool bZoomMatchedAim = true;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Look")
	bool bInvertPitch = false;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Look")
	float MaxPitch = 88.0f;

	/** When false the component only computes; the owner applies ConsumeLookDelta() itself. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Look")
	bool bApplyToController = true;

	/** Raw mouse counts this frame (x right, y up). */
	void AddMouseInput(const FVector2D& Counts);

	/** Gamepad stick (-1..1, dead zone already applied). Held value, re-sent each frame by Enhanced Input. */
	void AddGamepadInput(const FVector2D& Stick);

	/** Aim state and the two field of view values used for zoom matching. */
	void SetAim(bool bInAiming, float InHipFov, float InAimFov);

	/** Copies the look settings from USOGameUserSettings. */
	UFUNCTION(BlueprintCallable, Category = "Look")
	void LoadFromSettings();

	/** Drops pending input and the smoothing state. */
	void ResetLook() { PendingMouseCounts = FVector2D::ZeroVector; PendingStick = FVector2D::ZeroVector; SmoothedRate = FVector2D::ZeroVector; }

	/** Computes this frame's yaw / pitch in degrees from the pending input and clears it. */
	FVector2D ConsumeLookDelta(float DeltaTime);

	float GetSmoothingTimeConstant() const { return FMath::Max(0.0f, AimSmoothing) * SmoothingTimeScale; }
	float GetCurrentSensitivityScale() const;

	/** tan(zoomFov/2) / tan(hipFov/2); both in degrees. */
	static float ZoomScale(float HipFovDeg, float ZoomFovDeg);

	/** Radial response curve: keeps direction, maps magnitude m to m^Exponent. */
	static FVector2D ApplyResponseCurve(const FVector2D& Stick, float Exponent);

	//~ UActorComponent
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
	virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

private:
	FVector2D PendingMouseCounts = FVector2D::ZeroVector;
	FVector2D PendingStick = FVector2D::ZeroVector;
	FVector2D SmoothedRate = FVector2D::ZeroVector;
	bool bAiming = false;
	float HipFov = 90.0f;
	float AimFov = 90.0f;
	FDelegateHandle SettingsHandle;
	TWeakObjectPtr<AActor> TickAfterController;
};
