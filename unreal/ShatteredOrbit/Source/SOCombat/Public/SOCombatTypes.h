#pragma once

#include "CoreMinimal.h"
#include "SOCombatTypes.generated.h"

/** Weapon classes from the browser build's archetypes (stage 3 builds the weapon data assets on them). */
UENUM(BlueprintType)
enum class ESOWeaponClass : uint8
{
	Energy,
	Kinetic,
	Horror
};
