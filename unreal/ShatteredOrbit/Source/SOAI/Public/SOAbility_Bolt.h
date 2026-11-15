#pragma once

#include "CoreMinimal.h"
#include "Abilities/SOGameplayAbility.h"
#include "SOAbility_Bolt.generated.h"

/**
 * A creature's cast: a void bolt from the hands at the user's ability target (ASOCombatCharacter::SetAbilityTarget),
 * leading it a little; the bolt homes weakly and bursts on what it meets (ASOVoidBolt). The grant's numbers: Damage,
 * Force = the bolt's speed (cm/s), Angle = its scatter (degrees), WindUp = the cast, Cooldown.
 */
UCLASS()
class SOAI_API USOAbility_Bolt : public USOGameplayAbility
{
	GENERATED_BODY()

public:
	virtual bool WantsUse(const ASOCombatCharacter* User, const AActor* Target, const FSOAbilityGrant& Grant, bool bSeesTarget) const override;

protected:
	virtual void Perform(ASOCombatCharacter* User, const FSOAbilityGrant& Grant, bool bServer) override;
};

/**
 * A volley of void bolts: Magnitude of them over Duration seconds from where the user's casts leave it
 * (ASOEnemy::GetCastOrigin), each as the bolt above (Damage, Force = speed, Angle = scatter). It lasts as long as
 * the volley: meanwhile its user stands and turns with its target. Staggering or killing it stops the volley.
 */
UCLASS()
class SOAI_API USOAbility_Barrage : public USOGameplayAbility
{
	GENERATED_BODY()

public:
	virtual bool WantsUse(const ASOCombatCharacter* User, const AActor* Target, const FSOAbilityGrant& Grant, bool bSeesTarget) const override;
	virtual void Telegraph(ASOCombatCharacter* User, const FSOAbilityGrant& Grant) const override;
	virtual float ChannelTime(const FSOAbilityGrant& Grant) const override { return Grant.Duration; }
	virtual void EndAbility(const FGameplayAbilitySpecHandle Handle, const FGameplayAbilityActorInfo* ActorInfo, const FGameplayAbilityActivationInfo ActivationInfo, bool bReplicateEndAbility, bool bWasCancelled) override;

protected:
	virtual void Perform(ASOCombatCharacter* User, const FSOAbilityGrant& Grant, bool bServer) override;

private:
	void FireOne();

	FTimerHandle VolleyTimer;
	int32 BoltsLeft = 0;
	float BoltDamage = 0.0f, BoltSpeed = 0.0f, BoltScatter = 0.0f;
};

/**
 * A marksman's shot. For the wind-up a line of light runs from the user to its target and follows it; for the last
 * LockTime it holds still, and the shot goes down it: whoever moves in that last moment is missed, whoever stands is
 * hit hard. The grant's numbers: Damage; Range = how far it reaches; Radius = it is not used on a target closer than
 * this (up close a marksman is in trouble); Magnitude = after this many shots it gives up its place and finds another;
 * WindUp = the aim.
 */
UCLASS()
class SOAI_API USOAbility_Snipe : public USOGameplayAbility
{
	GENERATED_BODY()

public:
	/** The line stops following this long before the shot. */
	static constexpr float LockTime = 0.3f;

	virtual bool WantsUse(const ASOCombatCharacter* User, const AActor* Target, const FSOAbilityGrant& Grant, bool bSeesTarget) const override;
	virtual void Telegraph(ASOCombatCharacter* User, const FSOAbilityGrant& Grant) const override;
	virtual void Show(ASOCombatCharacter* User, const FSOAbilityGrant& Grant) const override;

	/** Where the shot goes: where the target was when the line locked. */
	static FVector AimPoint(const AActor* Target);

protected:
	virtual void Perform(ASOCombatCharacter* User, const FSOAbilityGrant& Grant, bool bServer) override;

private:
	int32 Shots = 0;
};

/**
 * A leader's call: after the wind-up, every one of its own side within Radius gets the grant's boon (Status: haste
 * by default, for Duration at Magnitude) and knows there is a fight on. A creature uses it when at least two of its
 * own are in reach. Whoever carries it is what holds the group together: when it dies, those within Radius are
 * staggered for a moment (ASOEnemy::HandleDeath).
 */
UCLASS()
class SOAI_API USOAbility_Rally : public USOGameplayAbility
{
	GENERATED_BODY()

public:
	virtual void Show(ASOCombatCharacter* User, const FSOAbilityGrant& Grant) const override;
	virtual void Telegraph(ASOCombatCharacter* User, const FSOAbilityGrant& Grant) const override;
	virtual bool WantsUse(const ASOCombatCharacter* User, const AActor* Target, const FSOAbilityGrant& Grant, bool bSeesTarget) const override;

protected:
	virtual void Perform(ASOCombatCharacter* User, const FSOAbilityGrant& Grant, bool bServer) override;
};
