#pragma once

#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "SOAttributes.generated.h"

// A character's six attributes (Project Orion phase 4). They are points, 0 to the table's Max, that worn armour gives
// (USOInventoryComponent::GetAttributePoints) and that live in the attribute set, put there by one GameplayEffect
// (USOGameplayEffect_Gear), so anything else (a perk, an ability, a consumable) can add to the same numbers the
// same way. What a point is worth is data: Data/game_data.json "attributes" -> SO_IMPORT_ONLY=attributes ->
// /Game/Data/DA_Attributes. The names are ours (docs/orion/ARCHITECTURE.md section 5).

UENUM(BlueprintType)
enum class ESOAttribute : uint8
{
	/** Takes less of every damage. */
	Plating,
	/** The shield starts refilling sooner and refills faster. */
	Mending,
	/** Moves faster. */
	Stride,
	/** The grenade comes back sooner. */
	Ordnance,
	/** The melee comes back sooner. */
	Impact,
	/** The ultimate charges faster. */
	Focus,
	Count UMETA(Hidden)
};

/** Points in each attribute (what a piece gives, what a character has). */
USTRUCT(BlueprintType)
struct SOCOMBAT_API FSOAttributePoints
{
	GENERATED_BODY()

	int32 Points[static_cast<int32>(ESOAttribute::Count)] = {};

	int32 Get(ESOAttribute A) const { return Points[static_cast<int32>(A)]; }
	int32& At(ESOAttribute A) { return Points[static_cast<int32>(A)]; }
	int32 Total() const;
	FSOAttributePoints& operator+=(const FSOAttributePoints& Other);
	bool operator==(const FSOAttributePoints& Other) const;
};

/** What an attribute is worth. */
USTRUCT(BlueprintType)
struct SOCOMBAT_API FSOAttributeRule
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Attributes")
	ESOAttribute Attribute = ESOAttribute::Plating;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Attributes")
	FText Name;

	/** One line for the loadout screen. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Attributes")
	FText Effect;

	/** The scale it reaches at the table's Max points (1 at none, straight line between). Plating: on damage taken;
	 *  Mending: on the wait before the shield refills; Stride: on speed; Ordnance / Impact: on the grenade's /
	 *  melee's cooldown; Focus: on what charges the ultimate. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Attributes")
	float AtMax = 1.0f;

	/** A second scale for an attribute that moves two things (Mending: on how fast the shield refills). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Attributes")
	float AtMax2 = 1.0f;
};

/** The attributes' rules and how armour turns into points. */
UCLASS(BlueprintType)
class SOCOMBAT_API USOAttributeTable : public UPrimaryDataAsset
{
	GENERATED_BODY()

public:
	USOAttributeTable();

	/** Points at which a rule is at its full effect; more than this does nothing more. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Attributes")
	float Max = 100.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Attributes")
	TArray<FSOAttributeRule> Rules;

	// --- armour into points: a piece's points = its armour rating x PointsPerArmour x the rarity's scale x
	// (1 + its power x PerPower); Lean of them go to the attribute its slot leans to, the rest to two others the
	// copy rolled.
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Armour")
	float PointsPerArmour = 1.0f;

	/** By rarity, lowest first. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Armour")
	TArray<float> RarityScale;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Armour")
	float PerPower = 0.005f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Armour")
	float Lean = 0.55f;

	/** The attribute each armour slot leans to (a slot not named here leans to one the copy rolled). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Armour")
	TMap<FName, ESOAttribute> SlotLean;

	const FSOAttributeRule& Rule(ESOAttribute Attribute) const;

	/** What Points in an attribute scale its thing by (and its second thing). */
	float Scale(ESOAttribute Attribute, float Points) const;
	float Scale2(ESOAttribute Attribute, float Points) const;

	/** What one armour piece gives: the same for the same piece every time (Seed is the copy's own). */
	FSOAttributePoints ArmourPoints(FName Slot, int32 ArmourRating, int32 Rarity, int32 Power, uint32 Seed) const;

	/** The imported table (/Game/Data/DA_Attributes), or the class's own defaults if it was never imported. */
	static const USOAttributeTable& Get();
};
