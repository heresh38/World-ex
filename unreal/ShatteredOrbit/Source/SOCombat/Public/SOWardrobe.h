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

	/** Helmets hide the hair (bald under a sealed helmet; the hair is back when it comes off). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Wardrobe")
	bool bHideHair = false;

	/** A piece of armour (lootable, shown in the inventory); hair and underwear are not. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Wardrobe")
	bool bArmour = true;

	/** Armour rating (data.js armorStats: ARMOR_SLOT, x1.7 for heavy pieces). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Wardrobe")
	int32 Armor = 0;

	/** A reward set's piece (void_sentinel): earned (an operation's reward), never handed out with the wardrobe. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Wardrobe")
	FName Set;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Wardrobe")
	TSoftObjectPtr<USkeletalMesh> Mesh;

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

	/** The one body: seen by everyone and from its own eyes (first person: its head hidden from that camera alone). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Wardrobe")
	TSoftObjectPtr<USkeletalMesh> BodyMesh;

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
	/** Slots that may be left empty: every armour slot (the undersuit, the "suit" slot, is always worn under the armour
	 *  and is never armour: a player is never undressed). */
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

	/** Worn by the body the player is in now. */
	UPROPERTY(SaveGame, BlueprintReadOnly, Category = "Armor")
	bool bEquipped = false;

	/** The bodies that have it on (male, female): what is worn is each body's own. A piece both bodies can wear is
	 *  owned once, but putting it on one does not put it on the other. The entry for the body the player is in is
	 *  brought up to date when they leave it (USOInventoryComponent::SetBody); until then bEquipped is the truth. */
	UPROPERTY(SaveGame, BlueprintReadOnly, Category = "Armor")
	TArray<FName> WornBy;

	UPROPERTY(SaveGame, BlueprintReadOnly, Category = "Armor")
	bool bNew = false;

	/** The copy's own roll: which attributes it gives beside its slot's (0: from its uid). A later re-roll changes
	 *  only this. */
	UPROPERTY(SaveGame, BlueprintReadOnly, Category = "Armor")
	int32 Roll = 0;

	/** The seed its attribute points come from (USOAttributeTable::ArmourPoints). */
	uint32 GetSeed() const { return Roll != 0 ? static_cast<uint32>(Roll) : GetTypeHash(Uid); }
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

	/** The face's sliders (the body's morph targets face_<key>, each -1..1; a key not set is the base face): the
	 *  character builder's (the owner, 2026-11-16: "the face will be heavily customizable in game"). */
	UPROPERTY(BlueprintReadOnly, Category = "Outfit")
	TArray<FName> FaceKeys;

	UPROPERTY(BlueprintReadOnly, Category = "Outfit")
	TArray<float> FaceValues;

	/** The skin's and the hair's tones (the character builder's: linear tints over the body's own maps, the brows
	 *  following the hair); alpha 0 = as the body was imported. */
	UPROPERTY(BlueprintReadOnly, Category = "Outfit")
	FLinearColor SkinTone = FLinearColor(0.0f, 0.0f, 0.0f, 0.0f);

	UPROPERTY(BlueprintReadOnly, Category = "Outfit")
	FLinearColor HairTone = FLinearColor(0.0f, 0.0f, 0.0f, 0.0f);

	/** The beard drawn on the face (the character builder's: none = clean-shaven, the base face; stubble, short, full:
	 *  the face's beard map's channels, M_SOSkin's BeardMask). The hairstyle is the hair slot's item. */
	UPROPERTY(BlueprintReadOnly, Category = "Outfit")
	FName Beard;

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
	bool operator==(const FSOOutfit& O) const
	{
		return Body == O.Body && Slots == O.Slots && Items == O.Items && FaceKeys == O.FaceKeys && FaceValues == O.FaceValues
			&& SkinTone.Equals(O.SkinTone, 1e-4f) && HairTone.Equals(O.HairTone, 1e-4f) && Beard == O.Beard;
	}
};
