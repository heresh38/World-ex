#pragma once

#include "CoreMinimal.h"
#include "GameplayEffect.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "SOCombatTypes.h"
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
DECLARE_MULTICAST_DELEGATE_FourParams(FSOOnCharacterHit, ASOCombatCharacter* /*Victim*/, AActor* /*Source*/, float /*Amount*/, UWorld* /*World*/);
DECLARE_MULTICAST_DELEGATE_FourParams(FSOOnNoise, UWorld* /*World*/, const FVector& /*Location*/, AActor* /*Instigator*/, float /*Radius*/);

/** Where a blow landed. Known only while the damage it belongs to is being applied (FSOHitScope). */
struct SOCOMBAT_API FSOHitInfo
{
	FName Bone;
	FVector Point = FVector::ZeroVector;
	/** The way the blow was travelling. */
	FVector Direction = FVector::ZeroVector;
	bool bPrecision = false;
	bool bKnown = false;

	ESOHitRegion Region() const { return RegionOf(Bone); }

	/** The region a bone belongs to (head / neck; upper arm, forearm, hand; thigh, shin, foot; the rest is trunk). */
	static ESOHitRegion RegionOf(FName Bone);
};

/** Whoever knows where a blow lands (a round) holds one of these round its ApplyDamage: what reacts to the damage
 *  (ASOCombatCharacter::OnTookDamage) can then ask USOCombatStatics::LastHit() where it was. */
struct SOCOMBAT_API FSOHitScope
{
	FSOHitScope(FName Bone, const FVector& Point, const FVector& Direction, bool bPrecision);
	~FSOHitScope();

private:
	FSOHitInfo Before;
};

UCLASS()
class SOCOMBAT_API USOCombatStatics : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/** Applies Amount damage from Source to Target through GAS (server only). Returns the damage applied (0 if refused):
	 *  the gate every damage passes is USOAttributeSet (the dead, the immune, the victim's scaling, friendly fire). */
	UFUNCTION(BlueprintCallable, Category = "SO|Combat")
	static float ApplyDamage(AActor* Source, AActor* Target, float Amount, bool bCrit);

	/**
	 * Puts a condition (a Status.* tag) on Target for Duration seconds (server only). Status.Burn: Magnitude is the
	 * total damage over the duration, in half-second ticks through the damage gate. Status.Slow: Magnitude is the
	 * scale on the movement speed (0.6 = 40 % slower). Status.Stagger: cannot act. Status.Guard: Magnitude is the
	 * share of all damage taken (0.5 = half), and no stagger meanwhile. Refused for the dead, for friends
	 * and for a target that resists it (ASOCombatCharacter::ResistsStatus). Two applications run side by side.
	 */
	static bool ApplyStatus(AActor* Source, AActor* Target, FGameplayTag Status, float Duration, float Magnitude = 0.0f);

	/** A condition's tag from its name in the data ("slow", "burn", "stagger", "jam", "haste", "guard"); an invalid
	 *  tag for anything else. Status.Jam: abilities cannot be used. Status.Haste: Magnitude is the scale on the
	 *  movement speed (1.25 = a quarter faster). Guard and haste are boons: given to one's own side only (and to
	 *  oneself); the others are harms: to the other side only. */
	static FGameplayTag StatusTag(FName Name);

	/** Same factions never hurt each other; actors without a faction are fair game. */
	static bool AreHostile(const AActor* A, const AActor* B);

	/** Fired on the server when a combat character dies (game mode respawns, spawners refill, AI loses targets). */
	static FSOOnCharacterDied& OnCharacterDied();

	/** Where the blow being applied right now landed (bKnown false: nobody said, e.g. a blast or a burn). */
	static const FSOHitInfo& LastHit();

	/** Fired on the server whenever a combat character takes damage from someone (whoever saw or felt it reacts). */
	static FSOOnCharacterHit& OnCharacterHit();

	/** Loud events (gunshots); creatures within Radius hear them. */
	static FSOOnNoise& OnNoise();

	UFUNCTION(BlueprintCallable, Category = "SO|Combat", meta = (WorldContext = "WorldContext"))
	static void ReportNoise(const UObject* WorldContext, FVector Location, AActor* Instigator, float Radius);
};
