#pragma once

#include "CoreMinimal.h"
#include "Abilities/GameplayAbility.h"
#include "Abilities/SOAbilitySet.h"
#include "SOGameplayAbility.generated.h"

class ASOCombatCharacter;

/**
 * Base of every ability in the game, a player's or a creature's. An ability is given to a character with a slot and
 * the kit it came from (ASOCombatCharacter::GrantAbilitySet); its numbers are that kit's FSOAbilityGrant, never
 * values in the class.
 *
 * Cooldown and charges: every use puts one cooldown effect (USOGameplayEffect_Cooldown, tagged with the slot's
 * Cooldown.* tag) on the user for the grant's Cooldown; the ability can be used while fewer of those are running than
 * the grant has Charges, so each charge comes back on its own clock. Cost: the grant's UltimateCost off the ultimate's
 * charge. Blocked while dead, staggered or in a traversal. A player's use is predicted on their own machine and
 * confirmed by the server; a creature's runs on the server.
 *
 * A subclass writes Perform(): what happens. Gameplay (damage, conditions, spawning) only when bServer; what the
 * player sees and hears goes through ASOCombatCharacter::ShowAbility so every machine gets it.
 */
UCLASS(Abstract)
class SOCOMBAT_API USOGameplayAbility : public UGameplayAbility
{
	GENERATED_BODY()

public:
	USOGameplayAbility();

	static FGameplayTag CooldownTag(ESOAbilitySlot Slot);

	/** What a use looks and sounds like, on every machine once (ASOCombatCharacter::OnAbilityUsed calls it on the
	 *  class's default object: no state, only User and the grant). */
	virtual void Show(ASOCombatCharacter* User, const FSOAbilityGrant& Grant) const {}

	/** A creature's rule for it: would User use this now on Target? (ASOEnemy::UseKit asks every ability of its kit
	 *  each time its brain thinks; the first that says yes is used.) A player's abilities are never asked. */
	virtual bool WantsUse(const ASOCombatCharacter* User, const AActor* Target, const FSOAbilityGrant& Grant, bool bSeesTarget) const { return false; }

	/** What its wind-up looks and sounds like (the grant's WindUp), on every machine once. */
	virtual void Telegraph(ASOCombatCharacter* User, const FSOAbilityGrant& Grant) const {}

	/** Seconds it stays in use after it was performed (a volley, something held): meanwhile the slot counts as
	 *  active (a creature stands and turns with its target, nothing else of its kit starts). 0 = over at once. */
	virtual float ChannelTime(const FSOAbilityGrant& Grant) const { return 0.0f; }

	//~ UGameplayAbility
	virtual bool CheckCooldown(const FGameplayAbilitySpecHandle Handle, const FGameplayAbilityActorInfo* ActorInfo, FGameplayTagContainer* OptionalRelevantTags = nullptr) const override;
	virtual void ApplyCooldown(const FGameplayAbilitySpecHandle Handle, const FGameplayAbilityActorInfo* ActorInfo, const FGameplayAbilityActivationInfo ActivationInfo) const override;
	virtual bool CheckCost(const FGameplayAbilitySpecHandle Handle, const FGameplayAbilityActorInfo* ActorInfo, FGameplayTagContainer* OptionalRelevantTags = nullptr) const override;
	virtual void ApplyCost(const FGameplayAbilitySpecHandle Handle, const FGameplayAbilityActorInfo* ActorInfo, const FGameplayAbilityActivationInfo ActivationInfo) const override;
	virtual void ActivateAbility(const FGameplayAbilitySpecHandle Handle, const FGameplayAbilityActorInfo* ActorInfo, const FGameplayAbilityActivationInfo ActivationInfo, const FGameplayEventData* TriggerEventData) override;
	virtual void EndAbility(const FGameplayAbilitySpecHandle Handle, const FGameplayAbilityActorInfo* ActorInfo, const FGameplayAbilityActivationInfo ActivationInfo, bool bReplicateEndAbility, bool bWasCancelled) override;

protected:
	/** What the ability does, once it has been paid for. */
	virtual void Perform(ASOCombatCharacter* User, const FSOAbilityGrant& Grant, bool bServer) {}

	/** The grant this ability was given with (null if it was given without a kit). */
	const FSOAbilityGrant* GrantFor(const FGameplayAbilitySpecHandle Handle, const FGameplayAbilityActorInfo* ActorInfo) const;

private:
	/** The wind-up is over: do it, unless the user was stopped meanwhile. */
	void Release();

	/** Performed: true if it now lasts a while (ChannelTime) and ends itself. */
	bool Hold(const FSOAbilityGrant& Grant);
	void Finish();

	FTimerHandle WindUpTimer;
};
