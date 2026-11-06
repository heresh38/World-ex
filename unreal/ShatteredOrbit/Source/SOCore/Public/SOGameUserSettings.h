#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameUserSettings.h"
#include "SOGameUserSettings.generated.h"

/** Anti-aliasing choice; the values match r.AntiAliasingMethod. */
UENUM(BlueprintType)
enum class ESOAntiAliasing : uint8
{
	None = 0 UMETA(DisplayName = "Off"),
	FXAA = 1 UMETA(DisplayName = "FXAA"),
	TAA = 2 UMETA(DisplayName = "TAA"),
	TSR = 4 UMETA(DisplayName = "TSR")
};

/**
 * Player settings (GameUserSettings.ini). Engine scalability groups stay in the base class;
 * this adds the look / aim settings and the renderer feature toggles that the graphics menu exposes.
 * ApplyGraphics() pushes the renderer toggles into console variables with game-override priority
 * (above DefaultEngine.ini and scalability, below the console and the command line).
 */
UCLASS(config = GameUserSettings, configdonotcheckdefaults, BlueprintType)
class SOCORE_API USOGameUserSettings : public UGameUserSettings
{
	GENERATED_BODY()

public:
	USOGameUserSettings();

	/** The active settings object (GEngine->GetGameUserSettings()), or nullptr before the engine exists. */
	UFUNCTION(BlueprintCallable, Category = "Settings")
	static USOGameUserSettings* Get();

	// --- Look ---
	/** Mouse multiplier on top of the base degrees per count. */
	UPROPERTY(config, EditAnywhere, BlueprintReadWrite, Category = "Look", meta = (ClampMin = "0.05", ClampMax = "10"))
	float MouseSensitivity = 1.0f;

	/** Extra multiplier while aiming down sights (on top of zoom matching). */
	UPROPERTY(config, EditAnywhere, BlueprintReadWrite, Category = "Look", meta = (ClampMin = "0.05", ClampMax = "4"))
	float AimSensitivityMultiplier = 1.0f;

	UPROPERTY(config, EditAnywhere, BlueprintReadWrite, Category = "Look", meta = (ClampMin = "0.05", ClampMax = "10"))
	float GamepadSensitivity = 1.0f;

	/** Gamepad response curve exponent (1 = linear, 2 = classic, 3 = precise). */
	UPROPERTY(config, EditAnywhere, BlueprintReadWrite, Category = "Look", meta = (ClampMin = "1", ClampMax = "4"))
	float GamepadResponseExponent = 2.0f;

	/** 0..1; the smoothing time constant is AimSmoothing * 0.06 s (0 = raw input). */
	UPROPERTY(config, EditAnywhere, BlueprintReadWrite, Category = "Look", meta = (ClampMin = "0", ClampMax = "1"))
	float AimSmoothing = 0.3f;

	UPROPERTY(config, EditAnywhere, BlueprintReadWrite, Category = "Look")
	bool bInvertPitch = false;

	/** Horizontal field of view in degrees. */
	UPROPERTY(config, EditAnywhere, BlueprintReadWrite, Category = "Look", meta = (ClampMin = "70", ClampMax = "120"))
	float FieldOfView = 90.0f;

	// --- Graphics ---
	UPROPERTY(config, EditAnywhere, BlueprintReadWrite, Category = "Graphics")
	bool bLumen = true;

	UPROPERTY(config, EditAnywhere, BlueprintReadWrite, Category = "Graphics")
	bool bVirtualShadowMaps = true;

	UPROPERTY(config, EditAnywhere, BlueprintReadWrite, Category = "Graphics")
	ESOAntiAliasing AntiAliasing = ESOAntiAliasing::TSR;

	/** Render resolution in percent of the output (TSR upscales). */
	UPROPERTY(config, EditAnywhere, BlueprintReadWrite, Category = "Graphics", meta = (ClampMin = "25", ClampMax = "200"))
	float ScreenPercentage = 100.0f;

	UPROPERTY(config, EditAnywhere, BlueprintReadWrite, Category = "Graphics")
	bool bMotionBlur = false;

	/** Pushes Lumen / VSM / AA / screen percentage / motion blur into their console variables. */
	UFUNCTION(BlueprintCallable, Category = "Settings")
	void ApplyGraphics();

	/** Look settings changed (sensitivity, FOV, ...); listeners such as the look component re-read them. */
	DECLARE_MULTICAST_DELEGATE(FOnLookSettingsChanged);
	FOnLookSettingsChanged OnLookSettingsChanged;

	UFUNCTION(BlueprintCallable, Category = "Settings")
	void NotifyLookSettingsChanged() { OnLookSettingsChanged.Broadcast(); }

	//~ UGameUserSettings
	virtual void ApplyNonResolutionSettings() override;
	virtual void SetToDefaults() override;
};
