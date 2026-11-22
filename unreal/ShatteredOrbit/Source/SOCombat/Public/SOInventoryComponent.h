#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "GameFramework/SaveGame.h"
#include "SOAttributes.h"
#include "SOLootTypes.h"
#include "SOWardrobe.h"
#include "SOInventoryComponent.generated.h"

/** A count the journal keeps (SOJournal: kills of a species, operations finished, deaths). */
USTRUCT()
struct SOCOMBAT_API FSOTally
{
	GENERATED_BODY()

	UPROPERTY(SaveGame)
	FName Key;

	UPROPERTY(SaveGame)
	int32 Count = 0;
};

/** What a player owns, on disk (state.js save: inventory, equipped, credits, alloy, xp, level). */
UCLASS()
class SOCOMBAT_API USOSaveGame : public USaveGame
{
	GENERATED_BODY()

public:
	/** The version this build writes. Raise it with every change to what is saved, and teach
	 *  USOProfileStore::Migrate the step from the one before. */
	static constexpr int32 CurrentVersion = 10;

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

	/** Version 2: armour pieces and the body. Version 3: a piece carries its own roll (FSOArmorInstance::Roll).
	 *  Version 4: what is worn is kept per body (FSOArmorInstance::WornBy). */
	UPROPERTY(SaveGame)
	TArray<FSOArmorInstance> Armor;

	UPROPERTY(SaveGame)
	FName Body = TEXT("male");

	/** Version 5: the melee styles owned beyond the fists (blades: USOMeleeTable ids). */
	UPROPERTY(SaveGame)
	TArray<FName> Blades;

	/** Version 6: the melee slot (a blade owned, or None: the fists). */
	UPROPERTY(SaveGame)
	FName MeleeSlot;

	/** Version 7: the face's sliders (FSOOutfit::FaceKeys / FaceValues). */
	UPROPERTY(SaveGame)
	TArray<FName> FaceKeys;

	UPROPERTY(SaveGame)
	TArray<float> FaceValues;

	/** Version 8: collected items (materials, consumables, keys, relics). A save from before them starts with the
	 *  loot tables' StarterGoods (USOProfileStore::Migrate). */
	UPROPERTY(SaveGame)
	TArray<FSOGoodsStack> Goods;

	/** Version 9: the skin's and the hair's tones (the character builder; alpha 0 = the body's own). */
	UPROPERTY(SaveGame)
	FLinearColor SkinTone = FLinearColor(0.0f, 0.0f, 0.0f, 0.0f);

	UPROPERTY(SaveGame)
	FLinearColor HairTone = FLinearColor(0.0f, 0.0f, 0.0f, 0.0f);

	/** Version 9: the character builder was seen once (a new profile opens it at the first start; a profile from
	 *  before it counts as made). */
	UPROPERTY(SaveGame)
	bool bCharacterMade = false;

	/** Version 10: the journal: the keys learned (SOJournal), the entries read, the tallies. */
	UPROPERTY(SaveGame)
	TArray<FName> Learned;

	UPROPERTY(SaveGame)
	TArray<FName> JournalRead;

	UPROPERTY(SaveGame)
	TArray<FSOTally> Tallies;
};

DECLARE_MULTICAST_DELEGATE(FSOOnInventoryChanged);
DECLARE_MULTICAST_DELEGATE_TwoParams(FSOOnLootFeed, const FString& /*Text*/, const FLinearColor& /*Color*/);

/** A gun that just came in (the HUD's NEW ITEM card): its name, its archetype (for the icon and the class line),
 *  rarity and power. */
USTRUCT()
struct SOCOMBAT_API FSOFeedItem
{
	GENERATED_BODY()

	UPROPERTY()
	FString Name;

	UPROPERTY()
	FName Archetype;

	UPROPERTY()
	int32 Rarity = 0;

	UPROPERTY()
	int32 Power = 0;
};
DECLARE_MULTICAST_DELEGATE_OneParam(FSOOnFeedItem, const FSOFeedItem& /*Item*/);

/** What a kill, a pickup or a chest pays. The HUD shows each as it comes in (the owner's loop, 2026-11-20: "every
 *  15-30 seconds the player should get: kill, loot, xp, level ..."). */
enum class ESORewardKind : uint8
{
	Xp,
	Credits,
	Alloy,
};
DECLARE_MULTICAST_DELEGATE_TwoParams(FSOOnReward, ESORewardKind /*Kind*/, int32 /*Amount*/);
DECLARE_MULTICAST_DELEGATE_OneParam(FSOOnLevelUp, int32 /*Level*/);

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
	/** The attribute points one piece gives (its armour rating, rarity, power and its own roll: SOAttributes.h). */
	FSOAttributePoints GetArmorPoints(const FSOArmorInstance& Piece) const;
	/** What everything worn gives: the character's attributes (the body takes them: ASOCombatCharacter::SetGearAttributes). */
	FSOAttributePoints GetAttributePoints() const;
	FName GetBody() const { return Body; }
	/** Body + every slot: the wardrobe's defaults (hair, underwear) with the worn armour on top. */
	FSOOutfit GetOutfit() const;

	/** The face: one slider (a morph target face_<Key> of the body, clamped to -1..1; 0 removes it), server. */
	void SetFace(FName Key, float Value);
	float GetFace(FName Key) const;

	UFUNCTION(Server, Reliable)
	void ServerSetFace(FName Key, float Value);

	/** The skin's and the hair's tones (linear tints; alpha 0 = the body's own), server. */
	void SetSkinTone(const FLinearColor& Tone);
	void SetHairTone(const FLinearColor& Tone);
	const FLinearColor& GetSkinTone() const { return SkinTone; }
	const FLinearColor& GetHairTone() const { return HairTone; }

	UFUNCTION(Server, Reliable)
	void ServerSetSkinTone(FLinearColor Tone);

	UFUNCTION(Server, Reliable)
	void ServerSetHairTone(FLinearColor Tone);

	/** The whole look at once (the builder's reset, its reset of a group, its random face): the face's sliders
	 *  replaced by these, the tones set (alpha 0 = the body's own); one change, one save. Server. */
	void SetLook(const TArray<FName>& Keys, const TArray<float>& Values, const FLinearColor& Skin, const FLinearColor& Hair);

	UFUNCTION(Server, Reliable)
	void ServerSetLook(const TArray<FName>& Keys, const TArray<float>& Values, FLinearColor Skin, FLinearColor Hair);

	/** The character builder was seen (a new profile opens it once, at the first start). */
	bool IsCharacterMade() const { return bCharacterMade; }
	void SetCharacterMade();

	UFUNCTION(Server, Reliable)
	void ServerSetCharacterMade();

	/** Wears (or, if it is worn, takes off) an armour piece (server). */
	bool EquipArmor(const FString& Uid);
	/** Switches the body (male / female): the pieces that body has are owned for it too, and it wears what IT had
	 *  on when the player last left it (its wardrobe's defaults the first time), not what the other body wears (server). */
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

	/** Hand to hand: a blade (a USOMeleeTable style id) is owned once; the fists are always there. Server only. */
	void AddBlade(FName Style);
	bool HasBlade(FName Style) const { return Blades.Contains(Style); }
	const TArray<FName>& GetBlades() const { return Blades; }
	/** The loadout's melee slot (the owner, 2026-11-16: "in the inventory add a spot for mele and if non then it's your
	 *  fists"): the blade in it, or None for the fists. Key 4 brings up what is there. */
	FName GetMeleeSlot() const { return MeleeSlot; }
	UFUNCTION(Server, Reliable)
	void ServerSetMeleeSlot(FName Style);
	void AddXp(int32 Amount);
	void AddAlloy(int32 Amount);

	// --- Collected items (goods: USOLootTables::Goods) ---
	const TArray<FSOGoodsStack>& GetGoods() const { return Goods; }
	int32 CountOf(FName Id) const;
	/** Holds all of them. */
	bool HasGoods(const TArray<FSOGoodsCost>& Costs) const;
	/** Server: adds up to the item's stack (what is past it is lost); returns how many went in. bAnnounce: a line in
	 *  the feed. */
	int32 AddGoods(FName Id, int32 Count, bool bAnnounce = true);
	/** Server: takes all of them, or none (false). */
	bool TakeGoods(const TArray<FSOGoodsCost>& Costs);
	/** Would using one do anything for this player's body now (a consumable held, the body alive and short of what
	 *  it gives)? */
	bool CanUseGoods(FName Id) const;
	/** Server: uses one consumable on this player's body; false (nothing taken) when it could do nothing. */
	bool UseGoods(FName Id);
	void MarkGoodsSeen(FName Id);
	/** What raising a gun or a piece takes beside credits and alloy (empty when it cannot be raised). */
	void GetUpgradeGoods(const FString& Uid, TArray<FSOGoodsCost>& Out) const;
	/** What a new profile starts with (the loot tables' StarterGoods), into Out. */
	static void StarterGoods(TArray<FSOGoodsStack>& Out);

	// --- The journal (SOJournal.h; the armoury's JOURNAL tab) ---
	/** Server: a key learned (SOJournal::MetKey ...). The first time, every entry it shows is new, and a line in the
	 *  feed names each one that is not an operation's own (those come with the operation's banner and radio). */
	void Learn(FName Key);
	bool HasLearned(FName Key) const;
	/** Shown in the journal: learned (or shown from the start). */
	bool IsJournalOpen(FName EntryId) const;
	/** Shown and not yet read. */
	bool IsJournalNew(FName EntryId) const;
	/** Any entry shown and not yet read (the armoury's gold mark on the tab). */
	bool HasJournalNew() const;
	void MarkJournalRead(FName EntryId);
	/** Server: one more of something counted (SOJournal::KillTally ...). */
	void Tally(FName Key, int32 Add = 1);
	int32 GetTally(FName Key) const;
	const TArray<FSOTally>& GetTallies() const { return Tallies; }

	UFUNCTION(Server, Reliable)
	void ServerMarkJournalRead(FName EntryId);

	// --- Spending and upgrades (USOProgressionTable) ---
	/** Pays both or neither: false (and nothing taken) if either is short. The one way anything is paid for. */
	bool Spend(int32 InCredits, int32 InAlloy);
	/** How far this character's gear can be upgraded (its level decides). */
	int32 GetPowerCap() const;
	/** What upgrading a gun or an armour piece would give and cost. False if it is not owned or already at the cap. */
	bool GetUpgrade(const FString& Uid, int32& OutPower, int32& OutCredits, int32& OutAlloy) const;
	/** Server: raises the piece's power one step and takes the cost; false (nothing changed) if it cannot be done or
	 *  cannot be paid for. */
	bool Upgrade(const FString& Uid);

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
	void ServerUpgrade(const FString& Uid);

	UFUNCTION(Server, Reliable)
	void ServerSetBody(FName NewBody);

	UFUNCTION(Server, Reliable)
	void ServerUseGoods(FName Id);

	UFUNCTION(Server, Reliable)
	void ServerMarkGoodsSeen(FName Id);

	/** Anything changed (all machines). */
	FSOOnInventoryChanged OnChanged;
	/** A line for the loot feed (pickups, dismantles) on the machine that owns the inventory. */
	FSOOnLootFeed OnFeed;
	/** A gun that came in, with what the HUD's card shows (on the machine that owns the inventory). */
	FSOOnFeedItem OnFeedItem;
	/** Xp, credits or alloy that came in (on the machine that owns the inventory): the HUD's popups. */
	FSOOnReward OnReward;
	/** A level reached (on the machine that owns the inventory): the HUD's moment. */
	FSOOnLevelUp OnLevelUp;
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

	UFUNCTION(Client, Reliable)
	void ClientFeedItem(const FSOFeedItem& Item);

	UFUNCTION(Client, Reliable)
	void ClientReward(uint8 Kind, int32 Amount);

	UFUNCTION(Client, Reliable)
	void ClientLevelUp(int32 NewLevel);

	/** Tells the owning machine what came in (as Feed: here, and over the wire to a joined player). */
	void Reward(ESORewardKind Kind, int32 Amount);

	void Changed(bool bLoadout, bool bOutfit = false);
	void Feed(const FString& Text, const FLinearColor& Color);
	void FeedItem(const FSOFeedItem& Item);
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

	UPROPERTY(ReplicatedUsing = OnRep_Inventory)
	TArray<FName> Blades;

	UPROPERTY(ReplicatedUsing = OnRep_Inventory)
	FName MeleeSlot;

	UPROPERTY(ReplicatedUsing = OnRep_Inventory)
	TArray<FName> FaceKeys;

	UPROPERTY(ReplicatedUsing = OnRep_Inventory)
	TArray<float> FaceValues;

	UPROPERTY(ReplicatedUsing = OnRep_Inventory)
	TArray<FSOGoodsStack> Goods;

	UPROPERTY(ReplicatedUsing = OnRep_Inventory)
	FLinearColor SkinTone = FLinearColor(0.0f, 0.0f, 0.0f, 0.0f);

	UPROPERTY(ReplicatedUsing = OnRep_Inventory)
	FLinearColor HairTone = FLinearColor(0.0f, 0.0f, 0.0f, 0.0f);

	/** (true until a new profile is made: an inventory with no profile, a test's or a bot's, never opens the builder) */
	UPROPERTY(Replicated)
	bool bCharacterMade = true;

	/** The journal: the keys learned, the entries read, the tallies (to the owner only). */
	UPROPERTY(ReplicatedUsing = OnRep_Inventory)
	TArray<FName> Learned;

	UPROPERTY(ReplicatedUsing = OnRep_Inventory)
	TArray<FName> JournalRead;

	UPROPERTY(ReplicatedUsing = OnRep_Inventory)
	TArray<FSOTally> Tallies;

	/** Learns the makers of every gun owned without a word (a profile from before the journal, a new one). */
	void LearnOwnedOrigins();

	TMap<FString, double> StowedAt;
	FRandomStream Rng;
};
