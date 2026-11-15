#pragma once

#include "CoreMinimal.h"
#include "GameplayEffect.h"
#include "SOGameplayEffects.generated.h"

// The game's effects other than damage (USOGameplayEffect_Damage, SOCombatStatics.h). Each is one small C++ class whose
// numbers arrive with the application (SetByCaller.*), so nothing here holds a design value: those live in the data.
// Everything that changes health, shield, speed or the ultimate's charge goes through one of these, so an ability,
// a perk or a piece of armour can find it, block it or scale it in one place.

/** Health back at once: SetByCaller.Magnitude (USOCombatStatics::Heal). */
UCLASS()
class SOCOMBAT_API USOGameplayEffect_Heal : public UGameplayEffect
{
	GENERATED_BODY()

public:
	USOGameplayEffect_Heal();
};

/** Shield back at once: SetByCaller.Magnitude (a kit's passive rule, ASOCombatCharacter::AddShield). */
UCLASS()
class SOCOMBAT_API USOGameplayEffect_Shield : public UGameplayEffect
{
	GENERATED_BODY()

public:
	USOGameplayEffect_Shield();
};

/** The shield refilling: SetByCaller.Magnitude every Period until it is taken off (USOAbilitySystemComponent). */
UCLASS()
class SOCOMBAT_API USOGameplayEffect_ShieldRegen : public UGameplayEffect
{
	GENERATED_BODY()

public:
	USOGameplayEffect_ShieldRegen();

	static constexpr float TickPeriod = 0.1f;
};

/** A condition that only marks its victim for SetByCaller.Duration (the tag rides on the application): stagger. */
UCLASS()
class SOCOMBAT_API USOGameplayEffect_Status : public UGameplayEffect
{
	GENERATED_BODY()

public:
	USOGameplayEffect_Status();
};

/** Acid, fire, parasites: SetByCaller.Damage into IncomingDamage every half second for SetByCaller.Duration. */
UCLASS()
class SOCOMBAT_API USOGameplayEffect_Burn : public UGameplayEffect
{
	GENERATED_BODY()

public:
	USOGameplayEffect_Burn();

	static constexpr float TickPeriod = 0.5f;
};

/** Slowed: the move scale times SetByCaller.Magnitude for SetByCaller.Duration. */
UCLASS()
class SOCOMBAT_API USOGameplayEffect_Slow : public UGameplayEffect
{
	GENERATED_BODY()

public:
	USOGameplayEffect_Slow();
};

/** Guarded: all damage taken times SetByCaller.Magnitude for SetByCaller.Duration. */
UCLASS()
class SOCOMBAT_API USOGameplayEffect_Guard : public UGameplayEffect
{
	GENERATED_BODY()

public:
	USOGameplayEffect_Guard();
};

/** An ability slot recharging for SetByCaller.Duration (the slot's cooldown tag rides on the application). */
UCLASS()
class SOCOMBAT_API USOGameplayEffect_Cooldown : public UGameplayEffect
{
	GENERATED_BODY()

public:
	USOGameplayEffect_Cooldown();
};

/** What worn gear gives: points in each of the six attributes (SetByCaller.Gear.*), for as long as it is on
 *  (ASOCombatCharacter::SetGearAttributes takes the old one off and puts the new one on). */
UCLASS()
class SOCOMBAT_API USOGameplayEffect_Gear : public UGameplayEffect
{
	GENERATED_BODY()

public:
	USOGameplayEffect_Gear();
};

/** The ultimate's charge up or down at once: SetByCaller.Magnitude (negative to spend it). */
UCLASS()
class SOCOMBAT_API USOGameplayEffect_Ultimate : public UGameplayEffect
{
	GENERATED_BODY()

public:
	USOGameplayEffect_Ultimate();
};
