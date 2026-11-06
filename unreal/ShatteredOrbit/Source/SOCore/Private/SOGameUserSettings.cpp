#include "SOGameUserSettings.h"

#include "Engine/Engine.h"
#include "HAL/IConsoleManager.h"
#include "SOLog.h"

namespace
{
	// Game override priority: above the project settings (DefaultEngine.ini) and scalability, below the console
	// and the command line, so `r.X` typed in the console still wins for debugging.
	void SetCVarInt(const TCHAR* Name, int32 Value)
	{
		if (IConsoleVariable* CVar = IConsoleManager::Get().FindConsoleVariable(Name))
		{
			CVar->Set(Value, ECVF_SetByGameOverride);
		}
		else
		{
			UE_LOG(LogShatteredOrbit, Verbose, TEXT("Settings: console variable %s not found"), Name);
		}
	}

	void SetCVarFloat(const TCHAR* Name, float Value)
	{
		if (IConsoleVariable* CVar = IConsoleManager::Get().FindConsoleVariable(Name))
		{
			CVar->Set(Value, ECVF_SetByGameOverride);
		}
	}
}

USOGameUserSettings::USOGameUserSettings()
{
}

USOGameUserSettings* USOGameUserSettings::Get()
{
	return GEngine ? Cast<USOGameUserSettings>(GEngine->GetGameUserSettings()) : nullptr;
}

void USOGameUserSettings::ApplyGraphics()
{
	// Global illumination + reflections: 1 = Lumen; without Lumen fall back to no dynamic GI and screen space reflections.
	SetCVarInt(TEXT("r.DynamicGlobalIlluminationMethod"), bLumen ? 1 : 0);
	SetCVarInt(TEXT("r.ReflectionMethod"), bLumen ? 1 : 2);
	SetCVarInt(TEXT("r.Shadow.Virtual.Enable"), bVirtualShadowMaps ? 1 : 0);
	SetCVarInt(TEXT("r.AntiAliasingMethod"), static_cast<int32>(AntiAliasing));
	SetCVarFloat(TEXT("r.ScreenPercentage"), FMath::Clamp(ScreenPercentage, 25.0f, 200.0f));
	SetCVarInt(TEXT("r.MotionBlurQuality"), bMotionBlur ? 4 : 0);

	UE_LOG(LogShatteredOrbit, Log, TEXT("Graphics applied: Lumen=%d VSM=%d AA=%d SP=%.0f MotionBlur=%d"),
		bLumen, bVirtualShadowMaps, static_cast<int32>(AntiAliasing), ScreenPercentage, bMotionBlur);
}

void USOGameUserSettings::ApplyNonResolutionSettings()
{
	Super::ApplyNonResolutionSettings();
	ApplyGraphics();
	NotifyLookSettingsChanged();
}

void USOGameUserSettings::SetToDefaults()
{
	Super::SetToDefaults();
	const USOGameUserSettings* Defaults = GetDefault<USOGameUserSettings>();
	MouseSensitivity = Defaults->MouseSensitivity;
	AimSensitivityMultiplier = Defaults->AimSensitivityMultiplier;
	GamepadSensitivity = Defaults->GamepadSensitivity;
	GamepadResponseExponent = Defaults->GamepadResponseExponent;
	AimSmoothing = Defaults->AimSmoothing;
	bInvertPitch = Defaults->bInvertPitch;
	FieldOfView = Defaults->FieldOfView;
	bLumen = Defaults->bLumen;
	bVirtualShadowMaps = Defaults->bVirtualShadowMaps;
	AntiAliasing = Defaults->AntiAliasing;
	ScreenPercentage = Defaults->ScreenPercentage;
	bMotionBlur = Defaults->bMotionBlur;
}
