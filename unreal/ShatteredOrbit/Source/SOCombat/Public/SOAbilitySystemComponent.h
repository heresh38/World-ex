#pragma once

#include "CoreMinimal.h"
#include "AbilitySystemComponent.h"
#include "SOAbilitySystemComponent.generated.h"

DECLARE_MULTICAST_DELEGATE_FourParams(FSOOnDamaged, float /*Amount*/, AActor* /*Instigator*/, bool /*bCrit*/, bool /*bKilled*/);

/** Ability system with damage notifications, shield regeneration (server side) and the character's state tags. */
UCLASS(ClassGroup = (ShatteredOrbit), meta = (BlueprintSpawnableComponent))
class SOCOMBAT_API USOAbilitySystemComponent : public UAbilitySystemComponent
{
	GENERATED_BODY()

public:
	USOAbilitySystemComponent();

	/** Shield starts refilling this long after the last hit. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Shield")
	float ShieldRegenDelay = 4.0f;

	/** Shield points per second once refilling. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Shield")
	float ShieldRegenRate = 25.0f;

	FSOOnDamaged OnDamaged;

	/** Called by USOAttributeSet after damage was applied (server). */
	void NotifyDamaged(float Amount, AActor* Instigator, bool bCrit, float NewHealth);

	float GetLastDamageTime() const { return LastDamageTime; }

	/** Server: the shield starts refilling now, without the wait since the last hit (a perk's kill). */
	void RefillShieldNow() { LastDamageTime = -1000.0f; }

	/** Server: under fire though not hit: the wait before the shield refills starts over. */
	void NoteUnderFire();

	/** Server: puts the refill effect (USOGameplayEffect_ShieldRegen) on once ShieldRegenDelay has passed since the
	 *  last hit and takes it off when the shield is full or hit again (called by the owning character every tick;
	 *  the ASC itself only ticks while it has gameplay tasks). */
	void UpdateShieldRegen(float DeltaTime);

	/** A State.* tag on or off (dead, aiming, sprinting, in a traversal). Set by the machine that knows: the server
	 *  and the player's own machine each from their own simulation, so abilities can be checked on both. */
	void SetState(const FGameplayTag& Tag, bool bOn);

private:
	float LastDamageTime = -1000.0f;
	FActiveGameplayEffectHandle ShieldRegen;
};
