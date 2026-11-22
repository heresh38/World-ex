#pragma once

#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "SOLootTypes.generated.h"

class USOWeaponData;
class UStaticMesh;

/** data.js RARITY: Common .. Exotic. */
USTRUCT(BlueprintType)
struct SOCOMBAT_API FSORarityInfo
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Loot")
	FName Id;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Loot")
	FText Name;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Loot")
	FLinearColor Color = FLinearColor::White;

	/** Damage multiplier. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Loot")
	float Mult = 1.0f;

	/** Perks rolled on a copy of this rarity. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Loot")
	int32 Perks = 0;
};

USTRUCT(BlueprintType)
struct SOCOMBAT_API FSOPerkInfo
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Loot")
	FName Id;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Loot")
	FText Name;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Loot")
	FText Description;

	// --- What it does: numbers from Data/game_data.json "perks" (a perk has only those it uses; the rest stay at
	// "nothing"). The code reads these and never asks a perk its name, so a perk that recombines them is data alone;
	// a perk that needs something new adds a number here and the one place that reads it.

	/** Scales on the gun's own numbers (1 = unchanged). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Loot|Effect")
	float Magazine = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Loot|Effect")
	float Reload = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Loot|Effect")
	float Spread = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Loot|Effect")
	float Recoil = 1.0f;

	/** On the precision multiplier. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Loot|Effect")
	float Precision = 1.0f;

	/** On the rate of fire while its holder's shield is down. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Loot|Effect")
	float FireRateShieldDown = 1.0f;

	/** A kill adds this share of damage, up to KillDamageStacks times, for KillDamageTime seconds (0 = none). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Loot|Effect")
	float KillDamage = 0.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Loot|Effect")
	int32 KillDamageStacks = 0;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Loot|Effect")
	float KillDamageTime = 0.0f;

	/** A kill gives this share of the holder's health back (0 = none). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Loot|Effect")
	float KillHeal = 0.0f;

	/** A precision hit bursts for this share of the gun's damage within PrecisionSplashRadius cm (0 = none). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Loot|Effect")
	float PrecisionSplash = 0.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Loot|Effect")
	float PrecisionSplashRadius = 0.0f;

	/** Put away, it reloads itself once its reload time has passed. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Loot|Effect")
	bool bAutoload = false;

	/** A kill puts this share of the magazine back from the reserve (0 = none). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Loot|Effect")
	float KillMagazine = 0.0f;

	/** A kill starts the holder's shield refilling at once. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Loot|Effect")
	bool bKillShield = false;

	/** A reload begun within KillReloadTime seconds of a kill takes this share of its time (1 = unchanged). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Loot|Effect")
	float KillReload = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Loot|Effect")
	float KillReloadTime = 0.0f;

	/** The first shot after OpeningAfter seconds without firing: on its damage, and it flies true (1 = none). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Loot|Effect")
	float OpeningDamage = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Loot|Effect")
	float OpeningAfter = 0.0f;

	/** On the damage of the rounds in the last LowMagShare of the magazine (1 = none). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Loot|Effect")
	float LowMagDamage = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Loot|Effect")
	float LowMagShare = 0.0f;

	/** On the spread when fired from the hip. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Loot|Effect")
	float HipSpread = 1.0f;

	/** On the damage to a target whose shield is up / whose shield is down. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Loot|Effect")
	float ShieldDamage = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Loot|Effect")
	float HealthDamage = 1.0f;

	/** What it hits is slowed to this share of its speed for HitSlowTime seconds (1 = none). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Loot|Effect")
	float HitSlow = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Loot|Effect")
	float HitSlowTime = 0.0f;

	/** A precision hit sets the target burning for this share of the gun's damage over PrecisionBurnTime seconds. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Loot|Effect")
	float PrecisionBurn = 0.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Loot|Effect")
	float PrecisionBurnTime = 0.0f;

	/** Its rounds lose nothing with distance. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Loot|Effect")
	bool bNoFalloff = false;

	/** On how far its shots are heard. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Loot|Effect")
	float Noise = 1.0f;

	/** Sliding fills the magazine from the reserve. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Loot|Effect")
	bool bSlideReload = false;

	/** The classes of gun that can roll it (kinetic, energy, horror; none named = any). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Loot")
	TArray<FName> Classes;

	/** It changes something (a perk with every number at "nothing" is a mistake in the data). */
	bool DoesAnything() const;

	/** This and Other together: scales multiply, shares add, the larger count / time / radius, either's switch. */
	void Add(const FSOPerkInfo& Other);
};

/** data.js SIGHTS: the gun's own sights or an optic from gun_attach.glb on the rail. */
USTRUCT(BlueprintType)
struct SOCOMBAT_API FSOSightInfo
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Loot")
	FName Id;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Loot")
	FText Name;

	/** Magnification (0 = the archetype's own zoom). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Loot")
	float Zoom = 0.0f;

	/** Magnified glass: once fully aimed the scope picture replaces the gun. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Loot")
	bool bScope = false;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Loot")
	TSoftObjectPtr<UStaticMesh> Mesh;

	/** The eye point of the optic relative to the rail (mesh space, cm). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Loot")
	FVector EyePoint = FVector::ZeroVector;
};

USTRUCT(BlueprintType)
struct SOCOMBAT_API FSOShaderInfo
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Loot")
	FName Id;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Loot")
	FText Name;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Loot")
	FLinearColor Body = FLinearColor::White;
};

USTRUCT(BlueprintType)
struct SOCOMBAT_API FSOArchetypeEntry
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Loot")
	FName Id;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Loot")
	TSoftObjectPtr<USOWeaponData> Data;
};

/** What kind of thing a collected item is: the inventory's categories. */
UENUM(BlueprintType)
enum class ESOGoodsKind : uint8
{
	/** Raises gear (USOProgressionTable: what a raise takes beside credits and alloy). */
	Material,
	/** Used from the inventory: health, shield or the ultimate's charge back at once. */
	Consumable,
	/** What an operation was for. */
	Key,
	/** A trophy: one of each, kept. */
	Relic,
};

/** A collected item that is not a gun or a piece of armour (Data/game_data.json "goods" -> DA_LootTables): its words,
 *  its picture, how many are carried at most, and what using one does. */
USTRUCT(BlueprintType)
struct SOCOMBAT_API FSOGoodsInfo
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Goods")
	FName Id;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Goods")
	FText Name;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Goods")
	ESOGoodsKind Kind = ESOGoodsKind::Material;

	/** Its rarity (the loot tables' Rarities): its colour on the screen. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Goods")
	int32 Rarity = 0;

	/** The most carried: what comes in past it is lost. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Goods")
	int32 Stack = 9999;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Goods")
	FText Lore;

	/** What it is for, in a line. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Goods")
	FText Use;

	/** Where it comes from, in a line. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Goods")
	FText Source;

	/** The armoury's picture of it (tools/blender/goods.py + icons.py goods). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Goods")
	TSoftObjectPtr<UTexture2D> Icon;

	/** A consumable: the share of its user's full health, shield and ultimate given back at once. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Goods")
	float Heal = 0.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Goods")
	float Shield = 0.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Goods")
	float Ultimate = 0.0f;
};

/** How many of one collected item a player holds. */
USTRUCT(BlueprintType)
struct SOCOMBAT_API FSOGoodsStack
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, SaveGame, Category = "Goods")
	FName Id;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, SaveGame, Category = "Goods")
	int32 Count = 0;

	/** Wears a NEW tag until it is looked at in the inventory. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, SaveGame, Category = "Goods")
	bool bNew = false;
};

/** One line of a drop list: the item, the chance, and Min..Max of it. */
USTRUCT(BlueprintType)
struct SOCOMBAT_API FSOGoodsDrop
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Goods")
	FName Item;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Goods")
	float Chance = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Goods")
	int32 Min = 1;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Goods")
	int32 Max = 1;
};

USTRUCT(BlueprintType)
struct SOCOMBAT_API FSOGoodsDropList
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Goods")
	TArray<FSOGoodsDrop> Drops;
};

/** So many of one collected item (what a raise takes, what a dismantle or a drop gives). */
USTRUCT(BlueprintType)
struct SOCOMBAT_API FSOGoodsCost
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Goods")
	FName Item;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Goods")
	int32 Count = 0;
};

/** A name the armoury sorts guns by: a family (what kind of gun, in its slot) or an origin (who made it). */
USTRUCT(BlueprintType)
struct SOCOMBAT_API FSOGunGroup
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Armoury")
	FName Id;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Armoury")
	FText Name;

	/** A family's slot (0 primary .. 2 heavy); an origin's -1. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Armoury")
	int32 Slot = -1;

	/** An origin's line. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Armoury")
	FText Text;
};

/**
 * Everything loot rolls from (data.js RARITY, PERKS, SIGHTS, SHADERS, the name pools and every archetype).
 * /Game/Data/DA_LootTables, written by Content/Python/import_assets.py from Data/game_data.json.
 */
UCLASS(BlueprintType)
class SOCOMBAT_API USOLootTables : public UPrimaryDataAsset
{
	GENERATED_BODY()

public:
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Loot")
	TArray<FSORarityInfo> Rarities;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Loot")
	TArray<FSOPerkInfo> Perks;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Loot")
	TArray<FSOSightInfo> Sights;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Loot")
	TArray<FSOShaderInfo> Shaders;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Loot")
	TArray<FSOArchetypeEntry> Archetypes;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Loot")
	TArray<FText> SlotNames;

	// Names (data.js weaponName): energy guns "<prefix> <noun>", kinetic "<maker> <code>-NN", horror "<bio prefix> <bio noun>",
	// exotics by archetype.
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Names")
	TArray<FString> Prefix;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Names")
	TArray<FString> Noun;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Names")
	TArray<FString> Maker;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Names")
	TMap<FName, FString> ModelCode;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Names")
	TArray<FString> BioPrefix;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Names")
	TArray<FString> BioNoun;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Names")
	TMap<FName, FString> ExoticNames;

	// --- the armoury's lists: families (what kind of gun) and origins (who made it), in the order shown ---
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Armoury")
	TArray<FSOGunGroup> Families;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Armoury")
	TArray<FSOGunGroup> Origins;

	// --- collected items (Data/game_data.json "goods", "goodsDrops", "dismantleGoods", "starterGoods") ---
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Goods")
	TArray<FSOGoodsInfo> Goods;

	/** "kill" (every creature), "elite" and "boss" (on top of it), "reliquary"; and by a creature's own key (its
	 *  variant, or its boss) what only it carries. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Goods")
	TMap<FName, FSOGoodsDropList> GoodsDrops;

	/** What dismantling a gun gives beside alloy: its class's material (by class id: energy, kinetic, horror), so
	 *  many by rarity; and so many of DismantleCrystalItem by rarity. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Goods")
	TMap<FName, FName> DismantleGoods;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Goods")
	TArray<int32> DismantleCount;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Goods")
	FName DismantleCrystalItem;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Goods")
	TArray<int32> DismantleCrystal;

	/** What a new profile (and one saved before collected items: version 8) starts with. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Goods")
	TMap<FName, int32> StarterGoods;

	const FSORarityInfo& GetRarity(int32 Index) const;
	const FSOPerkInfo* FindPerk(FName Id) const;
	const FSOSightInfo* FindSight(FName Id) const;
	USOWeaponData* LoadArchetype(FName Id) const;
	const FSOGoodsInfo* FindGoods(FName Id) const;
	const FSOGunGroup* FindFamily(FName Id) const;
	const FSOGunGroup* FindOrigin(FName Id) const;
};

/** state.js stat rolls: dmg / stability / range / handling 0.9..1.1, rpm 0.95..1.05. */
USTRUCT(BlueprintType)
struct SOCOMBAT_API FSOWeaponRolls
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, SaveGame, Category = "Loot")
	float Damage = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, SaveGame, Category = "Loot")
	float Rpm = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, SaveGame, Category = "Loot")
	float Stability = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, SaveGame, Category = "Loot")
	float Range = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, SaveGame, Category = "Loot")
	float Handling = 1.0f;
};

/** One owned copy of a weapon (state.js makeWeapon): every drop is its own gun. */
USTRUCT(BlueprintType)
struct SOCOMBAT_API FSOWeaponInstance
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, SaveGame, Category = "Loot")
	FString Uid;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, SaveGame, Category = "Loot")
	FName Archetype;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, SaveGame, Category = "Loot")
	int32 Rarity = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, SaveGame, Category = "Loot")
	int32 Power = 10;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, SaveGame, Category = "Loot")
	TArray<FName> Perks;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, SaveGame, Category = "Loot")
	FString Name;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, SaveGame, Category = "Loot")
	FName Shader = TEXT("bone");

	UPROPERTY(EditAnywhere, BlueprintReadWrite, SaveGame, Category = "Loot")
	FName Sight = TEXT("default");

	UPROPERTY(EditAnywhere, BlueprintReadWrite, SaveGame, Category = "Loot")
	FSOWeaponRolls Stats;

	/** Locked: never dismantled automatically or by accident. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, SaveGame, Category = "Loot")
	bool bKeep = false;

	/** Wears a NEW tag until it is looked at in the inventory. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, SaveGame, Category = "Loot")
	bool bNew = false;

	/** Where it came from (e.g. "Spire reliquary"). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, SaveGame, Category = "Loot")
	FString Source;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, SaveGame, Category = "Loot")
	int32 Mag = -1;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, SaveGame, Category = "Loot")
	int32 Reserve = -1;

	bool IsValid() const { return !Uid.IsEmpty() && !Archetype.IsNone(); }
	bool HasPerk(FName Perk) const { return Perks.Contains(Perk); }
};

/** The numbers a copy actually fires with (state.js weaponStats + the mounted sight's zoom). */
USTRUCT(BlueprintType)
struct SOCOMBAT_API FSOWeaponStats
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Loot")
	float Damage = 0.0f;

	UPROPERTY(BlueprintReadOnly, Category = "Loot")
	float Rpm = 0.0f;

	UPROPERTY(BlueprintReadOnly, Category = "Loot")
	int32 Mag = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Loot")
	int32 Reserve = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Loot")
	float Reload = 0.0f;

	/** m */
	UPROPERTY(BlueprintReadOnly, Category = "Loot")
	float Range = 0.0f;

	/** degrees */
	UPROPERTY(BlueprintReadOnly, Category = "Loot")
	float Spread = 0.0f;

	UPROPERTY(BlueprintReadOnly, Category = "Loot")
	float Crit = 1.0f;

	UPROPERTY(BlueprintReadOnly, Category = "Loot")
	float Zoom = 1.0f;

	/** Recoil multiplier (Gyro Stock). */
	UPROPERTY(BlueprintReadOnly, Category = "Loot")
	float Recoil = 1.0f;
	/** Everything the copy's perks do, taken together (USOLootLibrary::PerkEffects): what the gun reads at runtime. */
	FSOPerkInfo Perks;
};
