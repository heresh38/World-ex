#include "SOGameInstance.h"

#include "SOGameUserSettings.h"
#include "SOLog.h"

void USOGameInstance::Init()
{
	Super::Init();
	if (USOGameUserSettings* Settings = USOGameUserSettings::Get())
	{
		Settings->ApplyGraphics();
	}
	else
	{
		UE_LOG(LogShatteredOrbit, Warning, TEXT("GameUserSettingsClassName is not SOGameUserSettings (check DefaultEngine.ini)"));
	}
}
