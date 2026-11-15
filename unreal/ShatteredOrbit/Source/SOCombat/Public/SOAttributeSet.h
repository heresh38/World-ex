#pragma once

#include "CoreMinimal.h"
#include "AbilitySystemComponent.h"
#include "AttributeSet.h"
#include "SOAttributeSet.generated.h"

#define SO_ATTRIBUTE_ACCESSORS(ClassName, PropertyName) \
	GAMEPLAYATTRIBUTE_PROPERTY_GETTER(ClassName, PropertyName) \
	GAMEPLAYATTRIBUTE_VALUE_GETTER(PropertyName) \
	GAMEPLAYATTRIBUTE_VALUE_SETTER(PropertyName) \
	GAMEPLAYATTRIBUTE_VALUE_INITTER(PropertyName)

/**
 * A fighter's numbers: health and shield, the ultimate's charge, the scale on its movement speed.
 *
 * Damage is decided HERE and nowhere else. Whatever writes the IncomingDamage meta attribute (a round or a blow
 * through USOCombatStatics::ApplyDamage, a burn ticking, an ability's own effect) passes the same gate in
 * PostGameplayEffectExecute: nothing to the dead or the immune, the victim's own scaling (armour facing the shot,
 * ambush), no friendly fire, then the shield absorbs first and the rest comes off health. Replicated to everyone
 * (health bars, death).
 */
UCLASS()
class SOCOMBAT_API USOAttributeSet : public UAttributeSet
{
	GENERATED_BODY()

public:
	USOAttributeSet();

	UPROPERTY(BlueprintReadOnly, ReplicatedUsing = OnRep_Health, Category = "Attributes")
	FGameplayAttributeData Health;
	SO_ATTRIBUTE_ACCESSORS(USOAttributeSet, Health)

	UPROPERTY(BlueprintReadOnly, ReplicatedUsing = OnRep_MaxHealth, Category = "Attributes")
	FGameplayAttributeData MaxHealth;
	SO_ATTRIBUTE_ACCESSORS(USOAttributeSet, MaxHealth)

	UPROPERTY(BlueprintReadOnly, ReplicatedUsing = OnRep_Shield, Category = "Attributes")
	FGameplayAttributeData Shield;
	SO_ATTRIBUTE_ACCESSORS(USOAttributeSet, Shield)

	UPROPERTY(BlueprintReadOnly, ReplicatedUsing = OnRep_MaxShield, Category = "Attributes")
	FGameplayAttributeData MaxShield;
	SO_ATTRIBUTE_ACCESSORS(USOAttributeSet, MaxShield)

	/** The ultimate's charge, 0 to MaxUltimate. */
	UPROPERTY(BlueprintReadOnly, ReplicatedUsing = OnRep_Ultimate, Category = "Attributes")
	FGameplayAttributeData Ultimate;
	SO_ATTRIBUTE_ACCESSORS(USOAttributeSet, Ultimate)

	UPROPERTY(BlueprintReadOnly, ReplicatedUsing = OnRep_MaxUltimate, Category = "Attributes")
	FGameplayAttributeData MaxUltimate;
	SO_ATTRIBUTE_ACCESSORS(USOAttributeSet, MaxUltimate)

	/** Scale on the movement speed: 1 normally, under 1 while slowed. */
	UPROPERTY(BlueprintReadOnly, ReplicatedUsing = OnRep_MoveScale, Category = "Attributes")
	FGameplayAttributeData MoveScale;
	SO_ATTRIBUTE_ACCESSORS(USOAttributeSet, MoveScale)

	/** Scale on every damage taken, after the victim's own scaling: 1 normally, under 1 while guarded (and where
	 *  worn armour will count, phase 4). */
	UPROPERTY(BlueprintReadOnly, ReplicatedUsing = OnRep_DamageTaken, Category = "Attributes")
	FGameplayAttributeData DamageTaken;
	SO_ATTRIBUTE_ACCESSORS(USOAttributeSet, DamageTaken)

	// --- The six character attributes (SOAttributes.h): points, 0 and up, that worn gear gives. Only their owner
	// and the server need them. What a point is worth is USOAttributeTable's.
	UPROPERTY(BlueprintReadOnly, ReplicatedUsing = OnRep_Plating, Category = "Attributes")
	FGameplayAttributeData Plating;
	SO_ATTRIBUTE_ACCESSORS(USOAttributeSet, Plating)

	UPROPERTY(BlueprintReadOnly, ReplicatedUsing = OnRep_Mending, Category = "Attributes")
	FGameplayAttributeData Mending;
	SO_ATTRIBUTE_ACCESSORS(USOAttributeSet, Mending)

	UPROPERTY(BlueprintReadOnly, ReplicatedUsing = OnRep_Stride, Category = "Attributes")
	FGameplayAttributeData Stride;
	SO_ATTRIBUTE_ACCESSORS(USOAttributeSet, Stride)

	UPROPERTY(BlueprintReadOnly, ReplicatedUsing = OnRep_Ordnance, Category = "Attributes")
	FGameplayAttributeData Ordnance;
	SO_ATTRIBUTE_ACCESSORS(USOAttributeSet, Ordnance)

	UPROPERTY(BlueprintReadOnly, ReplicatedUsing = OnRep_Impact, Category = "Attributes")
	FGameplayAttributeData Impact;
	SO_ATTRIBUTE_ACCESSORS(USOAttributeSet, Impact)

	UPROPERTY(BlueprintReadOnly, ReplicatedUsing = OnRep_Focus, Category = "Attributes")
	FGameplayAttributeData Focus;
	SO_ATTRIBUTE_ACCESSORS(USOAttributeSet, Focus)

	/** Meta attribute: never replicated, consumed in PostGameplayEffectExecute. */
	UPROPERTY(BlueprintReadOnly, Category = "Attributes")
	FGameplayAttributeData IncomingDamage;
	SO_ATTRIBUTE_ACCESSORS(USOAttributeSet, IncomingDamage)

	/** The damage the last IncomingDamage really did after the gate (0 if it was refused); reading it clears it. */
	float TakeLastDamage() const;

	virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;
	virtual void PreAttributeChange(const FGameplayAttribute& Attribute, float& NewValue) override;
	virtual void PostGameplayEffectExecute(const FGameplayEffectModCallbackData& Data) override;

protected:
	UFUNCTION()
	void OnRep_Health(const FGameplayAttributeData& OldValue);
	UFUNCTION()
	void OnRep_MaxHealth(const FGameplayAttributeData& OldValue);
	UFUNCTION()
	void OnRep_Shield(const FGameplayAttributeData& OldValue);
	UFUNCTION()
	void OnRep_MaxShield(const FGameplayAttributeData& OldValue);
	UFUNCTION()
	void OnRep_Ultimate(const FGameplayAttributeData& OldValue);
	UFUNCTION()
	void OnRep_MaxUltimate(const FGameplayAttributeData& OldValue);
	UFUNCTION()
	void OnRep_MoveScale(const FGameplayAttributeData& OldValue);
	UFUNCTION()
	void OnRep_DamageTaken(const FGameplayAttributeData& OldValue);
	UFUNCTION()
	void OnRep_Plating(const FGameplayAttributeData& OldValue);
	UFUNCTION()
	void OnRep_Mending(const FGameplayAttributeData& OldValue);
	UFUNCTION()
	void OnRep_Stride(const FGameplayAttributeData& OldValue);
	UFUNCTION()
	void OnRep_Ordnance(const FGameplayAttributeData& OldValue);
	UFUNCTION()
	void OnRep_Impact(const FGameplayAttributeData& OldValue);
	UFUNCTION()
	void OnRep_Focus(const FGameplayAttributeData& OldValue);

private:
	void TakeDamage(const FGameplayEffectModCallbackData& Data);

	mutable float LastDamage = 0.0f;
};
