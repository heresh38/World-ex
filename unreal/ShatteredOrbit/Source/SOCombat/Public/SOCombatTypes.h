#pragma once

#include "CoreMinimal.h"
#include "NativeGameplayTags.h"
#include "SOCombatTypes.generated.h"

SOCOMBAT_API DECLARE_LOG_CATEGORY_EXTERN(LogSOCombat, Log, All);

/** Weapon classes from the browser build's archetypes. */
UENUM(BlueprintType)
enum class ESOWeaponClass : uint8
{
	Energy,
	Kinetic,
	Horror
};

/** Who fights whom. Rounds and attacks never hurt the same faction. */
UENUM(BlueprintType)
enum class ESOFaction : uint8
{
	Player,
	Alien,
	Writhe,
	Neutral
};

namespace SOTags
{
	SOCOMBAT_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(SetByCaller_Damage);
	SOCOMBAT_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(SetByCaller_Crit);
	SOCOMBAT_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(State_Dead);
}
