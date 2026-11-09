#pragma once

#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "SOWardrobe.generated.h"

class USkeletalMesh;
class UTexture2D;

/**
 * One wearable piece of a player body (wardrobe.py C_<slot>__<item>, imported as its own skeletal mesh on the body's
 * skeleton) with the meta the game needs: the body regions it hides, locked underwear rules, its icon and armour.
 */
USTRUCT(BlueprintType)
struct SOCOMBAT_API FSOWardrobeItem
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Wardrobe")
	FName Slot;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Wardrobe")
	FName Item;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Wardrobe")
	FText Label;

	/** Body regions this piece covers (skin__<region> sections are hidden while it is worn). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Wardrobe")
	TArray<FName> Hide;

	/** Locked underwear: hidden while any of these slots is worn. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Wardrobe")
	TArray<FName> CoveredBy;

	/** Slots this piece replaces (a dress hides top and legs). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Wardrobe")
	TArray<FName> Replaces;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Wardrobe")
	bool bLocked = false;

	/** Helmets hide the hair. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Wardrobe")
	bool bHideHair = false;

	/** A piece of armour (lootable, shown in the inventory); hair and underwear are not. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Wardrobe")
	bool bArmour = true;

	/** Armour rating (data.js armorStats: ARMOR_SLOT, x1.7 for heavy pieces). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Wardrobe")
	int32 Armor = 0;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Wardrobe")
	TSoftObjectPtr<USkeletalMesh> Mesh;

	/** First-person cut (only what the arm bones carry); unset for pieces that never reach the arms. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Wardrobe")
	TSoftObjectPtr<USkeletalMesh> ArmsMesh;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Wardrobe")
	TSoftObjectPtr<UTexture2D> Icon;
};

/** A player body and everything it can wear (Content/Python/import_assets.py: DA_Wardrobe in each body's folder). */
UCLASS(BlueprintType)
class SOCOMBAT_API USOWardrobeData : public UPrimaryDataAsset
{
	GENERATED_BODY()

public:
	/** male | female */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Wardrobe")
	FName Body;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Wardrobe")
	TSoftObjectPtr<USkeletalMesh> BodyMesh;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Wardrobe")
	TSoftObjectPtr<USkeletalMesh> ArmsMesh;

	/** /Game/Characters/Player<Sex>/Anims/A_Player<Sex>_ */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Wardrobe")
	FString ClipPathPrefix;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Wardrobe")
	TArray<FSOWardrobeItem> Items;

	/** slot -> item worn by default ("none" = nothing). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Wardrobe")
	TMap<FName, FName> Defaults;

	const FSOWardrobeItem* Find(FName Slot, FName Item) const;

	/** The wardrobe of a body (male / female), loaded on demand. */
	static USOWardrobeData* Get(FName Body);

	/** Armour slots in inventory order: head, top, vest, outer, hands, legs, feet. */
	static const TArray<FName>& ArmourSlots();
	/** Slots that may be left empty (head gear, the outer layer); every other armour slot always has a piece on,
	 *  so a player can swap pieces but never be undressed. */
	static bool IsOptionalSlot(FName Slot);

	/** Head, Chest, Rig, Coat, Hands, Legs, Feet. */
	static FText SlotLabel(FName Slot);
};

/** One owned armour piece (a wardrobe item of a body), saved with the profile. */
USTRUCT(BlueprintType)
struct SOCOMBAT_API FSOArmorInstance
{
	GENERATED_BODY()

	UPROPERTY(SaveGame, BlueprintReadOnly, Category = "Armor")
	FString Uid;

	UPROPERTY(SaveGame, BlueprintReadOnly, Category = "Armor")
	FName Slot;

	UPROPERTY(SaveGame, BlueprintReadOnly, Category = "Armor")
	FName Item;

	UPROPERTY(SaveGame, BlueprintReadOnly, Category = "Armor")
	int32 Rarity = 2;

	UPROPERTY(SaveGame, BlueprintReadOnly, Category = "Armor")
	int32 Power = 10;

	UPROPERTY(SaveGame, BlueprintReadOnly, Category = "Armor")
	bool bEquipped = false;

	UPROPERTY(SaveGame, BlueprintReadOnly, Category = "Armor")
	bool bNew = false;
};

/** What a character wears, replicated: the body and one item per slot. */
USTRUCT(BlueprintType)
struct SOCOMBAT_API FSOOutfit
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Outfit")
	FName Body = TEXT("male");

	UPROPERTY(BlueprintReadOnly, Category = "Outfit")
	TArray<FName> Slots;

	UPROPERTY(BlueprintReadOnly, Category = "Outfit")
	TArray<FName> Items;

	FName Get(FName Slot) const
	{
		const int32 i = Slots.IndexOfByKey(Slot);
		return i != INDEX_NONE && Items.IsValidIndex(i) ? Items[i] : FName(TEXT("none"));
	}
	void Set(FName Slot, FName Item)
	{
		const int32 i = Slots.IndexOfByKey(Slot);
		if (i == INDEX_NONE)
		{
			Slots.Add(Slot);
			Items.Add(Item);
		}
		else
		{
			Items[i] = Item;
		}
	}
	bool operator==(const FSOOutfit& O) const { return Body == O.Body && Slots == O.Slots && Items == O.Items; }
};
