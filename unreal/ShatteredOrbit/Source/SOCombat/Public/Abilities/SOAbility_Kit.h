#pragma once

#include "CoreMinimal.h"
#include "Abilities/SOAbility_Strike.h"
#include "Abilities/SOGameplayAbility.h"
#include "SOAbility_Kit.generated.h"

// The abilities kits are built from, beside the strike (SOAbility_Strike.h). Each reads its numbers from its grant.

/**
 * A thrown charge: lobbed along the aim (Force cm/s, a little upward), it bursts on what it hits. Damage to what it
 * strikes and, falling off, to everything hostile within Radius; those caught are slowed to Magnitude of their
 * speed for Duration. It hurts its thrower too.
 */
UCLASS()
class SOCOMBAT_API USOAbility_Grenade : public USOGameplayAbility
{
	GENERATED_BODY()

public:
	virtual void Show(ASOCombatCharacter* User, const FSOAbilityGrant& Grant) const override;
	virtual bool WantsUse(const ASOCombatCharacter* User, const AActor* Target, const FSOAbilityGrant& Grant, bool bSeesTarget) const override;

protected:
	virtual void Perform(ASOCombatCharacter* User, const FSOAbilityGrant& Grant, bool bServer) override;

	/** Where it leaves the hand and how fast. */
	static void Throw(const ASOCombatCharacter* User, const FSOAbilityGrant& Grant, FVector& OutStart, FVector& OutVelocity);
};

/**
 * Braced: for Duration the user takes Magnitude of all damage (0.5 = half) and cannot be staggered
 * (the Status.Guard condition).
 */
UCLASS()
class SOCOMBAT_API USOAbility_Guard : public USOGameplayAbility
{
	GENERATED_BODY()

public:
	virtual void Show(ASOCombatCharacter* User, const FSOAbilityGrant& Grant) const override;
	virtual bool WantsUse(const ASOCombatCharacter* User, const AActor* Target, const FSOAbilityGrant& Grant, bool bSeesTarget) const override;

protected:
	virtual void Perform(ASOCombatCharacter* User, const FSOAbilityGrant& Grant, bool bServer) override;
};

/**
 * A blow into the ground: the strike's rules all round the user (give it Angle 180 and the reach as Range), shown
 * as a burst on the ground.
 */
UCLASS()
class SOCOMBAT_API USOAbility_Slam : public USOAbility_Strike
{
	GENERATED_BODY()

public:
	virtual void Show(ASOCombatCharacter* User, const FSOAbilityGrant& Grant) const override;
};

/**
 * An arm swung across the front: the strike's rules in a wide cone, and what it lands on is thrown sideways, the
 * way the arm was going, not straight back.
 */
UCLASS()
class SOCOMBAT_API USOAbility_Sweep : public USOAbility_Strike
{
	GENERATED_BODY()

protected:
	virtual FVector Knock(const ASOCombatCharacter* User, const ASOCombatCharacter* Other, const FSOAbilityGrant& Grant) const override;
};

/**
 * The ground breaking open under those it is meant for. After the wind-up (the cast), a mark is drawn under every
 * hostile within Range and Magnitude more round them: a ring Radius wide that fills for Duration seconds and then
 * bursts, for Damage to whoever still stands in it, thrown up by Force. The marks are where the server put them on
 * every machine, and what is drawn is what bursts: stepping out of the ring is enough. If the user dies before they
 * burst, they do not.
 */
UCLASS()
class SOCOMBAT_API USOAbility_Eruption : public USOGameplayAbility
{
	GENERATED_BODY()

public:
	virtual void Telegraph(ASOCombatCharacter* User, const FSOAbilityGrant& Grant) const override;
	virtual bool WantsUse(const ASOCombatCharacter* User, const AActor* Target, const FSOAbilityGrant& Grant, bool bSeesTarget) const override;

	/** Server: where the marks of one use go (under each hostile in Range, and the extra ones). */
	static TArray<FVector> Marks(const ASOCombatCharacter* User, const FSOAbilityGrant& Grant);

	/** Server: the marks burst. */
	static void Burst(ASOCombatCharacter* User, const TArray<FVector>& Marks, float Damage, float Radius, float Force);

protected:
	virtual void Perform(ASOCombatCharacter* User, const FSOAbilityGrant& Grant, bool bServer) override;
};

/**
 * A pulse from the body: after the wind-up, everything hostile within Radius with nothing solid between takes
 * Damage (if any) and the grant's condition (Status, Duration, Magnitude). A disruptor's jam is one: caught in it,
 * a player's abilities are out for its duration. The warning is light rising round the user through the wind-up.
 */
UCLASS()
class SOCOMBAT_API USOAbility_Pulse : public USOGameplayAbility
{
	GENERATED_BODY()

public:
	virtual void Show(ASOCombatCharacter* User, const FSOAbilityGrant& Grant) const override;
	virtual void Telegraph(ASOCombatCharacter* User, const FSOAbilityGrant& Grant) const override;
	virtual bool WantsUse(const ASOCombatCharacter* User, const AActor* Target, const FSOAbilityGrant& Grant, bool bSeesTarget) const override;

protected:
	virtual void Perform(ASOCombatCharacter* User, const FSOAbilityGrant& Grant, bool bServer) override;
};
