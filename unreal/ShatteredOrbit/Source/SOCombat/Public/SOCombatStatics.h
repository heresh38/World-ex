#pragma once

#include "CoreMinimal.h"
#include "GameplayEffect.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "SOCombatStatics.generated.h"

class ASOCombatCharacter;

/** Instant damage: SetByCaller.Damage into the IncomingDamage meta attribute. */
UCLASS()
class SOCOMBAT_API USOGameplayEffect_Damage : public UGameplayEffect
{
	GENERATED_BODY()

public:
	USOGameplayEffect_Damage();
};

DECLARE_MULTICAST_DELEGATE_ThreeParams(FSOOnCharacterDied, ASOCombatCharacter* /*Victim*/, AActor* /*Killer*/, UWorld* /*World*/);
DECLARE_MULTICAST_DELEGATE_FourParams(FSOOnNoise, UWorld* /*World*/, const FVector& /*Location*/, AActor* /*Instigator*/, float /*Radius*/);

UCLASS()
class SOCOMBAT_API USOCombatStatics : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/** Applies Amount damage from Source to Target through GAS (server only). Returns the damage applied (0 if refused). */
	UFUNCTION(BlueprintCallable, Category = "SO|Combat")
	static float ApplyDamage(AActor* Source, AActor* Target, float Amount, bool bCrit);

	/** Same factions never hurt each other; actors without a faction are fair game. */
	static bool AreHostile(const AActor* A, const AActor* B);

	/** Fired on the server when a combat character dies (game mode respawns, spawners refill, AI loses targets). */
	static FSOOnCharacterDied& OnCharacterDied();

	/** Loud events (gunshots); creatures within Radius hear them. */
	static FSOOnNoise& OnNoise();

	UFUNCTION(BlueprintCallable, Category = "SO|Combat", meta = (WorldContext = "WorldContext"))
	static void ReportNoise(const UObject* WorldContext, FVector Location, AActor* Instigator, float Radius);
};
