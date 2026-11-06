#pragma once

#include "CoreMinimal.h"
#include "Engine/GameInstance.h"
#include "SOGameInstance.generated.h"

/** Lives for the whole session; applies the saved settings on start. */
UCLASS()
class SHATTEREDORBIT_API USOGameInstance : public UGameInstance
{
	GENERATED_BODY()

public:
	virtual void Init() override;
};
