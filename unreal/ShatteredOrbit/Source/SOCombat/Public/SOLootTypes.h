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

	const FSORarityInfo& GetRarity(int32 Index) const;
	const FSOPerkInfo* FindPerk(FName Id) const;
	const FSOSightInfo* FindSight(FName Id) const;
	USOWeaponData* LoadArchetype(FName Id) const;
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
};
