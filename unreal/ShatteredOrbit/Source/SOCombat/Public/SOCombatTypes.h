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

/** The part of a body a blow landed on (what shows the hit, and how much it unsteadies). */
UENUM(BlueprintType)
enum class ESOHitRegion : uint8
{
	Torso,
	Head,
	ArmLeft,
	ArmRight,
	LegLeft,
	LegRight
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
	// numbers an effect is applied with
	SOCOMBAT_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(SetByCaller_Damage);
	SOCOMBAT_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(SetByCaller_Crit);
	SOCOMBAT_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(SetByCaller_Duration);
	SOCOMBAT_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(SetByCaller_Magnitude);
	// what worn gear gives in each attribute (USOGameplayEffect_Gear)
	SOCOMBAT_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(SetByCaller_Gear_Plating);
	SOCOMBAT_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(SetByCaller_Gear_Mending);
	SOCOMBAT_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(SetByCaller_Gear_Stride);
	SOCOMBAT_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(SetByCaller_Gear_Ordnance);
	SOCOMBAT_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(SetByCaller_Gear_Impact);
	SOCOMBAT_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(SetByCaller_Gear_Focus);
	// what a character is doing (USOAbilitySystemComponent::SetState)
	SOCOMBAT_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(State_Dead);
	SOCOMBAT_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(State_Aiming);
	SOCOMBAT_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(State_Sprinting);
	SOCOMBAT_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(State_Traversing);
	// conditions put on a character (USOCombatStatics::ApplyStatus)
	SOCOMBAT_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Status_Burn);
	SOCOMBAT_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Status_Slow);
	SOCOMBAT_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Status_Stagger);
	SOCOMBAT_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Status_Guard);
	SOCOMBAT_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Status_Jam);
	SOCOMBAT_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Status_Haste);
	SOCOMBAT_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Status_Suppressed);
	// an ability slot recharging (USOGameplayAbility)
	SOCOMBAT_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Cooldown_Grenade);
	SOCOMBAT_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Cooldown_Melee);
	SOCOMBAT_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Cooldown_Class);
	SOCOMBAT_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Cooldown_Movement);
	SOCOMBAT_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(Cooldown_Ultimate);
}
