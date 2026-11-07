#include "SOPlayerState.h"
#include "SOInventoryComponent.h"

ASOPlayerState::ASOPlayerState()
{
	SetNetUpdateFrequency(60.0f);
	Inventory = CreateDefaultSubobject<USOInventoryComponent>(TEXT("Inventory"));
}
