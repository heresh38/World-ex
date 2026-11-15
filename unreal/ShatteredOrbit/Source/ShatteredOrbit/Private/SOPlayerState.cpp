#include "SOPlayerState.h"
#include "SOInventoryComponent.h"
#include "SOKitComponent.h"

ASOPlayerState::ASOPlayerState()
{
	SetNetUpdateFrequency(60.0f);
	Inventory = CreateDefaultSubobject<USOInventoryComponent>(TEXT("Inventory"));
	Kit = CreateDefaultSubobject<USOKitComponent>(TEXT("Kit"));
}
