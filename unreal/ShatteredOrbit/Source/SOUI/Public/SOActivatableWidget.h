#pragma once

#include "CoreMinimal.h"
#include "CommonActivatableWidget.h"
#include "SOActivatableWidget.generated.h"

/** Base for Shattered Orbit screens (CommonUI, gamepad-first). Real screens arrive with the HUD stage. */
UCLASS(Abstract, Blueprintable)
class SOUI_API USOActivatableWidget : public UCommonActivatableWidget
{
	GENERATED_BODY()
};
