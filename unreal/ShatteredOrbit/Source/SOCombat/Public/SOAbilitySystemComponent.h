#pragma once

#include "CoreMinimal.h"
#include "AbilitySystemComponent.h"
#include "SOAbilitySystemComponent.generated.h"

DECLARE_MULTICAST_DELEGATE_FourParams(FSOOnDamaged, float /*Amount*/, AActor* /*Instigator*/, bool /*bCrit*/, bool /*bKilled*/);

/** Ability system with damage notifications and shield regeneration (server side). */
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

	/** Server: refills the shield after ShieldRegenDelay (called by the owning character every tick; the ASC itself
	 *  only ticks while it has gameplay tasks). */
	void UpdateShieldRegen(float DeltaTime);

private:
	float LastDamageTime = -1000.0f;
};
