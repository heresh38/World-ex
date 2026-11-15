#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "SOKitComponent.generated.h"

class ASOCombatCharacter;
class USOAbilitySet;

/**
 * The kit a player has chosen, kept on the player state so it outlives the body: which kit, and the ultimate's
 * charge between one body and the next. The ability system itself lives on the body (a new body is a clean one:
 * cooldowns start over), so on every possession the server gives the new body the kit's abilities again
 * (Apply) and hands back the charge that was remembered when the last body died (Remember).
 */
UCLASS(ClassGroup = (ShatteredOrbit), meta = (BlueprintSpawnableComponent))
class SOCOMBAT_API USOKitComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	USOKitComponent();

	/** The kit's id in Data/game_data.json "kits" (asset /Game/Abilities/DA_Kit_<Id>). */
	UPROPERTY(ReplicatedUsing = OnRep_Kit, EditAnywhere, BlueprintReadOnly, Category = "SO|Kit")
	FName KitId = TEXT("vanguard");

	/** Server: another kit; the body in play gets it at once. */
	void SetKit(FName NewKit, ASOCombatCharacter* Body);

	/** Server: gives Body the chosen kit's abilities and the remembered ultimate charge. */
	void Apply(ASOCombatCharacter* Body);

	/** Server: Body is gone: keep what should carry over to the next one. */
	void Remember(const ASOCombatCharacter* Body);

	USOAbilitySet* GetKit();

	virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;

private:
	UFUNCTION()
	void OnRep_Kit();

	UPROPERTY(Transient)
	TObjectPtr<USOAbilitySet> Kit;

	FName LoadedKit;
	float SavedUltimate = 0.0f;
};
