#pragma once

#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "SOAbilitySet.generated.h"

class USOGameplayAbility;

/** Where an ability sits on a character: one of each at most. The slot is also the ability's input and cooldown. */
UENUM(BlueprintType)
enum class ESOAbilitySlot : uint8
{
	Grenade,
	Melee,
	Class,
	Movement,
	Ultimate,
	Count UMETA(Hidden)
};

/**
 * One ability in a kit: what it is and its numbers (Data/game_data.json "kits" is their source). The ability class
 * decides what each number means (a strike: Damage, Range, Angle, Duration = stagger; a grenade: Damage, Radius, ...).
 */
USTRUCT(BlueprintType)
struct SOCOMBAT_API FSOAbilityGrant
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Ability")
	ESOAbilitySlot Slot = ESOAbilitySlot::Melee;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Ability")
	TSubclassOf<USOGameplayAbility> Ability;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Ability")
	FText DisplayName;

	/** Seconds until a spent charge is back. 0 = no cooldown. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Ability")
	float Cooldown = 8.0f;

	/** Uses that can be held at once; each comes back Cooldown seconds after it was spent. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Ability")
	int32 Charges = 1;

	/** Seconds between the use and its effect: the warning whoever it is aimed at gets (0 = at once). Staggering or
	 *  killing the user in that time stops it. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Ability")
	float WindUp = 0.0f;

	/** Ultimate charge it needs and spends (0 = none). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Ability")
	float UltimateCost = 0.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Ability")
	float Damage = 0.0f;

	/** cm */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Ability")
	float Range = 0.0f;

	/** cm */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Ability")
	float Radius = 0.0f;

	/** Half angle of a cone, degrees. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Ability")
	float Angle = 0.0f;

	/** Seconds (of the condition it leaves, of the thing it places). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Ability")
	float Duration = 0.0f;

	/** cm/s (a knock, a throw). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Ability")
	float Force = 0.0f;

	/** A scale (the speed a slow leaves, the share of damage a guard lets through). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Ability")
	float Magnitude = 0.0f;

	/** The condition it leaves, by name (slow, burn, stagger, jam, haste, guard: USOCombatStatics::StatusTag), with
	 *  Duration and Magnitude; none = the ability's own. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Ability")
	FName Status;

	/** The body's clip for it, by name in the user's own clip set (a player's "Throw", "Strike", "Brace", "Slam":
	 *  tools/blender/hero/<sex>/motion.py; none = the body does not move). It starts with the wind-up if there is
	 *  one, so the wind-up is the time into the clip at which the blow lands. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Ability")
	FName Clip;

	/** A creature's clip: the time into it at which the blow lands (0 = the wind-up itself). The clip is played
	 *  slower or faster so that moment falls on the end of the wind-up: a heavy attack is the same motion, drawn out. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Ability")
	float ClipLead = 0.0f;

	/** Sound played where it is used (USOSoundLibrary name; none = silent). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Ability")
	FName Sound;

	/** Sound played as its wind-up begins (none = silent): what is coming is heard before it is seen. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Ability")
	FName WindUpSound;
};

/**
 * A kit: the abilities a character has, by slot, and how its ultimate charges. Players get theirs from the kit they
 * chose (USOKitComponent); a creature can be given one the same way (ASOCombatCharacter::GrantAbilitySet).
 * Written by Content/Python/import_assets.py as /Game/Abilities/DA_Kit_<Id>.
 */
UCLASS(BlueprintType)
class SOCOMBAT_API USOAbilitySet : public UPrimaryDataAsset
{
	GENERATED_BODY()

public:
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Kit")
	FName KitId;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Kit")
	FText DisplayName;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Kit")
	TArray<FSOAbilityGrant> Abilities;

	/** Ultimate charge (of 100) gained per second alive, per point of damage dealt, per kill. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Kit")
	float UltimatePerSecond = 0.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Kit")
	float UltimatePerDamage = 0.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Kit")
	float UltimatePerKill = 0.0f;

	// --- The kit's passive rule: what makes it more than four buttons. One rule per kit, always on. ---
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Kit")
	FText PassiveName;

	/** A kill within CloseRange (cm) gives CloseKillShield points of shield back at once (0 = the kit has no such
	 *  rule). The frontline kit's: it is paid for standing where the fight is. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Kit")
	float CloseRange = 0.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Kit")
	float CloseKillShield = 0.0f;

	const FSOAbilityGrant* Find(ESOAbilitySlot Slot) const;

	/** The kit's asset by id ("vanguard" -> /Game/Abilities/DA_Kit_Vanguard), loaded; null if it was never imported. */
	static USOAbilitySet* Load(FName KitId);
};
