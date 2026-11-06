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
 * Health and shield. Damage arrives through the IncomingDamage meta attribute (USOGameplayEffect_Damage):
 * the shield absorbs first, the rest comes off health. Replicated to everyone (health bars, death).
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

	/** Meta attribute: never replicated, consumed in PostGameplayEffectExecute. */
	UPROPERTY(BlueprintReadOnly, Category = "Attributes")
	FGameplayAttributeData IncomingDamage;
	SO_ATTRIBUTE_ACCESSORS(USOAttributeSet, IncomingDamage)

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
};
