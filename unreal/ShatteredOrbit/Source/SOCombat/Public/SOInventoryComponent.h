#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "GameFramework/SaveGame.h"
#include "SOLootTypes.h"
#include "SOWardrobe.h"
#include "SOInventoryComponent.generated.h"

/** What a player owns, on disk (state.js save: inventory, equipped, credits, alloy, xp, level). */
UCLASS()
class SOCOMBAT_API USOSaveGame : public USaveGame
{
	GENERATED_BODY()

public:
	UPROPERTY(SaveGame)
	int32 Version = 1;

	UPROPERTY(SaveGame)
	TArray<FSOWeaponInstance> Items;

	UPROPERTY(SaveGame)
	TArray<FString> Equipped;

	UPROPERTY(SaveGame)
	int32 ActiveSlot = 0;

	UPROPERTY(SaveGame)
	int32 Credits = 500;

	UPROPERTY(SaveGame)
	int32 Alloy = 20;

	UPROPERTY(SaveGame)
	int32 Xp = 0;

	UPROPERTY(SaveGame)
	int32 Level = 1;

	/** Version 2: armour pieces and the body. */
	UPROPERTY(SaveGame)
	TArray<FSOArmorInstance> Armor;

	UPROPERTY(SaveGame)
	FName Body = TEXT("male");
};

DECLARE_MULTICAST_DELEGATE(FSOOnInventoryChanged);
DECLARE_MULTICAST_DELEGATE_TwoParams(FSOOnLootFeed, const FString& /*Text*/, const FLinearColor& /*Color*/);

/**
 * The player's vault and loadout (lives on the player state, so it survives death): every owned copy, three equipped
 * slots (Primary / Special / Heavy) and the one in hand, credits / alloy / xp. Server-authoritative and replicated;
 * the owning client asks through the Server* RPCs (inventory screen). The listen-server / standalone host saves to
 * the "ShatteredOrbit" save slot on every change. Rules from state.js / main.js: every new copy wears a NEW tag,
 * an empty slot equips a new drop of its slot, the vault holds 200 (past it the weakest plain spare is dismantled).
 */
UCLASS(ClassGroup = (ShatteredOrbit), meta = (BlueprintSpawnableComponent))
class SOCOMBAT_API USOInventoryComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	USOInventoryComponent();

	static constexpr int32 NumSlots = 3;
	static const TCHAR* SaveSlot;

	// --- Read ---
	const TArray<FSOWeaponInstance>& GetItems() const { return Items; }
	const FSOWeaponInstance* Find(const FString& Uid) const;
	/** The copy equipped in a slot (null if empty). */
	const FSOWeaponInstance* GetEquipped(int32 Slot) const;
	bool IsEquipped(const FString& Uid) const { return Equipped.Contains(Uid); }
	int32 GetActiveSlot() const { return ActiveSlot; }
	int32 GetCredits() const { return Credits; }
	int32 GetAlloy() const { return Alloy; }
	int32 GetXp() const { return Xp; }
	int32 GetLevel() const { return Level; }
	/** main.js power(): average power of the equipped copies. */
	int32 GetPower() const;

	// --- Armour (wardrobe pieces of the body; see USOWardrobeData) ---
	const TArray<FSOArmorInstance>& GetArmor() const { return Armor; }
	const FSOArmorInstance* FindArmor(const FString& Uid) const;
	/** The armour piece worn in a slot (head, top, vest, outer, hands, legs, feet), null if none. */
	const FSOArmorInstance* GetEquippedArmor(FName Slot) const;
	/** Total armour rating of what is worn. */
	int32 GetArmorRating() const;
	FName GetBody() const { return Body; }
	/** Body + every slot: the wardrobe's defaults (hair, underwear) with the worn armour on top. */
	FSOOutfit GetOutfit() const;

	/** Wears (or, if it is worn, takes off) an armour piece (server). */
	bool EquipArmor(const FString& Uid);
	/** Switches the body (male / female): the pieces that body has are owned for it too (server). */
	bool SetBody(FName NewBody);
	/** Server: an earned armour piece (an operation's reward); a piece already owned is raised to the better rarity /
	 *  power instead of a second copy. */
	FSOArmorInstance AddArmorPiece(FName Slot, FName Item, int32 Rarity, int32 Power, bool bAnnounce = true);
	/** Owns one of every armour piece of the body's wardrobe (missing ones only) and wears its defaults. */
	void GrantWardrobe(bool bWearDefaults);
	/** Drops armour that no longer exists in either body's wardrobe (old saves) and puts the body's default on
	 *  every required slot that has nothing worn, and on any slot whose worn piece was dropped (an old coat is
	 *  replaced by the new one, not left empty). */
	void Dress();

	/** Takes a save's armour: grants the wardrobe (wearing its defaults when the save had none) and dresses. */
	void RestoreArmor(const TArray<FSOArmorInstance>& Saved);

	// --- Server ---
	/** Adds a copy (unique uid, NEW tag); equips it if its slot is empty; keeps the vault under the cap. */
	FSOWeaponInstance AddWeapon(FSOWeaponInstance Weapon, bool bAnnounce = true);
	bool Equip(const FString& Uid);
	bool SelectSlot(int32 Slot);
	bool SetKeep(const FString& Uid, bool bKeep);
	/** Breaks a copy down for alloy (never an equipped or locked one). Returns the alloy gained (0 = refused). */
	int32 Dismantle(const FString& Uid);
	void MarkSeen(const FString& Uid);
	void MarkAllSeen();
	/** The weapon in hand reports its ammo before it is put away (and Autoloader starts counting). */
	void StoreAmmo(const FString& Uid, int32 Mag, int32 Reserve);
	/** Autoloader: a stowed copy refills its magazine once its reload time has passed. */
	FSOWeaponInstance PrepareForEquip(const FString& Uid);
	/** combat.js ammo pickup: the equipped weapons' reserves grow (25 %, heavies 15 %, capped at 1.5x). */
	void AddAmmoPickup();
	void AddCredits(int32 Amount);
	void AddXp(int32 Amount);
	void AddAlloy(int32 Amount);

	/** A brand-new profile: the browser build's starters plus the one-time armoury (every kinetic and horror gun). */
	void NewProfile();
	bool LoadProfile();
	void SaveProfile() const;
	/** Saving to disk (on for the host's own inventory; tests switch it off). */
	bool bPersist = true;

	// --- Client -> server (inventory screen) ---
	UFUNCTION(Server, Reliable)
	void ServerEquip(const FString& Uid);

	UFUNCTION(Server, Reliable)
	void ServerSelectSlot(int32 Slot);

	UFUNCTION(Server, Reliable)
	void ServerSetKeep(const FString& Uid, bool bKeep);

	UFUNCTION(Server, Reliable)
	void ServerDismantle(const FString& Uid);

	UFUNCTION(Server, Reliable)
	void ServerMarkSeen(const FString& Uid);

	UFUNCTION(Server, Reliable)
	void ServerEquipArmor(const FString& Uid);

	UFUNCTION(Server, Reliable)
	void ServerSetBody(FName NewBody);

	/** Anything changed (all machines). */
	FSOOnInventoryChanged OnChanged;
	/** A line for the loot feed (pickups, dismantles) on the machine that owns the inventory. */
	FSOOnLootFeed OnFeed;
	/** The equipped copy in the active slot changed: the pawn re-equips (server). */
	FSOOnInventoryChanged OnLoadoutChanged;
	/** The worn armour or the body changed: the pawn re-dresses (server). */
	FSOOnInventoryChanged OnOutfitChanged;

	//~ UActorComponent
	virtual void BeginPlay() override;
	virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;

protected:
	UFUNCTION()
	void OnRep_Inventory();

	UFUNCTION(Client, Reliable)
	void ClientFeed(const FString& Text, FLinearColor Color);

	void Changed(bool bLoadout, bool bOutfit = false);
	void Feed(const FString& Text, const FLinearColor& Color);
	FString UniqueUid(FString Uid) const;
	int32 SlotOf(const FSOWeaponInstance& Weapon) const;

	UPROPERTY(ReplicatedUsing = OnRep_Inventory)
	TArray<FSOWeaponInstance> Items;

	UPROPERTY(ReplicatedUsing = OnRep_Inventory)
	TArray<FString> Equipped;

	UPROPERTY(ReplicatedUsing = OnRep_Inventory)
	int32 ActiveSlot = 0;

	UPROPERTY(ReplicatedUsing = OnRep_Inventory)
	int32 Credits = 0;

	UPROPERTY(ReplicatedUsing = OnRep_Inventory)
	int32 Alloy = 0;

	UPROPERTY(ReplicatedUsing = OnRep_Inventory)
	int32 Xp = 0;

	UPROPERTY(ReplicatedUsing = OnRep_Inventory)
	int32 Level = 1;

	UPROPERTY(ReplicatedUsing = OnRep_Inventory)
	TArray<FSOArmorInstance> Armor;

	UPROPERTY(ReplicatedUsing = OnRep_Inventory)
	FName Body = TEXT("male");

	TMap<FString, double> StowedAt;
	FRandomStream Rng;
};
