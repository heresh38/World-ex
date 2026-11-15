#pragma once

#include "CoreMinimal.h"
#include "Abilities/SOGameplayAbility.h"
#include "SOAbility_Strike.generated.h"

/**
 * A blow at arm's length: everything hostile in front of the user within the grant's Range and inside its cone
 * (Angle, half angle) and with nothing solid between takes Damage, is knocked back by Force and staggered for
 * Duration. The grant's numbers: Damage, Range, Angle, Force, Duration. With a wind-up long enough to read, its
 * reach is drawn on the ground under the user while it winds up (a ring, or the cone it will land in), and the blow
 * of anything but a player goes where its body faces: where the warning is.
 */
UCLASS()
class SOCOMBAT_API USOAbility_Strike : public USOGameplayAbility
{
	GENERATED_BODY()

public:
	virtual void Show(ASOCombatCharacter* User, const FSOAbilityGrant& Grant) const override;
	virtual void Telegraph(ASOCombatCharacter* User, const FSOAbilityGrant& Grant) const override;
	virtual bool WantsUse(const ASOCombatCharacter* User, const AActor* Target, const FSOAbilityGrant& Grant, bool bSeesTarget) const override;

	/** A wind-up at least this long draws its reach on the ground (a shorter one is over before it could be read). */
	static constexpr float WarnFrom = 0.4f;

	/** The way the blow goes: a player's along the aim, anything else's where its body faces. */
	static FVector Heading(const ASOCombatCharacter* User);

protected:
	virtual void Perform(ASOCombatCharacter* User, const FSOAbilityGrant& Grant, bool bServer) override;

	/** How it throws what it lands on (cm/s). */
	virtual FVector Knock(const ASOCombatCharacter* User, const ASOCombatCharacter* Other, const FSOAbilityGrant& Grant) const;
};
