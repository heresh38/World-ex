#include "SOInventoryComponent.h"

#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/PlayerState.h"
#include "Kismet/GameplayStatics.h"
#include "Net/UnrealNetwork.h"
#include "SOCombatTypes.h"
#include "SOLootLibrary.h"
#include "SOWeaponData.h"

const TCHAR* USOInventoryComponent::SaveSlot = TEXT("ShatteredOrbit");

USOInventoryComponent::USOInventoryComponent()
{
	SetIsReplicatedByDefault(true);
	Rng.GenerateNewSeed();
}

void USOInventoryComponent::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
	Super::GetLifetimeReplicatedProps(OutLifetimeProps);
	DOREPLIFETIME(USOInventoryComponent, Items);
	DOREPLIFETIME(USOInventoryComponent, Equipped);
	DOREPLIFETIME(USOInventoryComponent, ActiveSlot);
	DOREPLIFETIME(USOInventoryComponent, Credits);
	DOREPLIFETIME(USOInventoryComponent, Alloy);
	DOREPLIFETIME(USOInventoryComponent, Xp);
	DOREPLIFETIME(USOInventoryComponent, Level);
	DOREPLIFETIME(USOInventoryComponent, Armor);
	DOREPLIFETIME(USOInventoryComponent, Body);
}

void USOInventoryComponent::BeginPlay()
{
	Super::BeginPlay();
	Equipped.SetNum(NumSlots);
	if (GetOwner() && GetOwner()->HasAuthority() && Items.Num() == 0)
	{
		// The host's own profile comes from disk; everyone else starts fresh (a profile service comes later).
		const APlayerState* PS = Cast<APlayerState>(GetOwner());
		const APlayerController* PC = PS ? PS->GetPlayerController() : nullptr;
		const bool bLocal = PC && PC->IsLocalController(); // no controller (tests, bots): never touch the save
		if (!(bPersist && bLocal && LoadProfile()))
		{
			NewProfile();
		}
	}
}

// --- Read ------------------------------------------------------------------------------------------

const FSOWeaponInstance* USOInventoryComponent::Find(const FString& Uid) const
{
	return Uid.IsEmpty() ? nullptr : Items.FindByPredicate([&Uid](const FSOWeaponInstance& W) { return W.Uid == Uid; });
}

const FSOArmorInstance* USOInventoryComponent::FindArmor(const FString& Uid) const
{
	return Uid.IsEmpty() ? nullptr : Armor.FindByPredicate([&Uid](const FSOArmorInstance& A) { return A.Uid == Uid; });
}

const FSOArmorInstance* USOInventoryComponent::GetEquippedArmor(FName Slot) const
{
	const USOWardrobeData* Wardrobe = USOWardrobeData::Get(Body);
	return Armor.FindByPredicate([&](const FSOArmorInstance& A) { return A.bEquipped && A.Slot == Slot && (!Wardrobe || Wardrobe->Find(A.Slot, A.Item)); });
}

int32 USOInventoryComponent::GetArmorRating() const
{
	const USOWardrobeData* Wardrobe = USOWardrobeData::Get(Body);
	int32 Sum = 0;
	for (const FName Slot : USOWardrobeData::ArmourSlots())
	{
		if (const FSOArmorInstance* A = GetEquippedArmor(Slot))
		{
			const FSOWardrobeItem* Item = Wardrobe ? Wardrobe->Find(A->Slot, A->Item) : nullptr;
			Sum += Item ? Item->Armor : 0;
		}
	}
	return Sum;
}

FSOOutfit USOInventoryComponent::GetOutfit() const
{
	FSOOutfit Outfit;
	Outfit.Body = Body;
	if (const USOWardrobeData* Wardrobe = USOWardrobeData::Get(Body))
	{
		for (const TPair<FName, FName>& D : Wardrobe->Defaults)
		{
			const bool bArmourSlot = USOWardrobeData::ArmourSlots().Contains(D.Key);
			Outfit.Set(D.Key, bArmourSlot ? FName(TEXT("none")) : D.Value); // armour slots: only what is worn
		}
	}
	for (const FName Slot : USOWardrobeData::ArmourSlots())
	{
		const FSOArmorInstance* A = GetEquippedArmor(Slot);
		Outfit.Set(Slot, A ? A->Item : FName(TEXT("none")));
	}
	return Outfit;
}

bool USOInventoryComponent::EquipArmor(const FString& Uid)
{
	FSOArmorInstance* Piece = Armor.FindByPredicate([&Uid](const FSOArmorInstance& A) { return A.Uid == Uid; });
	if (!Piece)
	{
		return false;
	}
	const bool bWear = !Piece->bEquipped;
	for (FSOArmorInstance& A : Armor)
	{
		if (A.Slot == Piece->Slot)
		{
			A.bEquipped = false;
		}
	}
	Piece->bEquipped = bWear;
	Piece->bNew = false;
	Changed(false, true);
	return true;
}

bool USOInventoryComponent::SetBody(FName NewBody)
{
	if (NewBody == Body || !USOWardrobeData::Get(NewBody))
	{
		return false;
	}
	Body = NewBody;
	GrantWardrobe(false);
	// keep wearing what the new body has; anything else falls back to its default
	if (const USOWardrobeData* Wardrobe = USOWardrobeData::Get(Body))
	{
		for (const FName Slot : USOWardrobeData::ArmourSlots())
		{
			if (!GetEquippedArmor(Slot))
			{
				const FName Want = Wardrobe->Defaults.FindRef(Slot);
				if (FSOArmorInstance* A = Armor.FindByPredicate([&](const FSOArmorInstance& X) { return X.Slot == Slot && X.Item == Want; }))
				{
					A->bEquipped = true;
				}
			}
		}
	}
	Changed(false, true);
	return true;
}

void USOInventoryComponent::GrantWardrobe(bool bWearDefaults)
{
	const USOWardrobeData* Wardrobe = USOWardrobeData::Get(Body);
	if (!Wardrobe)
	{
		return;
	}
	for (const FSOWardrobeItem& Item : Wardrobe->Items)
	{
		if (!Item.bArmour || Armor.ContainsByPredicate([&](const FSOArmorInstance& A) { return A.Slot == Item.Slot && A.Item == Item.Item; }))
		{
			continue;
		}
		FSOArmorInstance A;
		A.Uid = FString::Printf(TEXT("ar_%s_%s_%08x"), *Item.Slot.ToString(), *Item.Item.ToString(), Rng.RandHelper(0x7fffffff));
		A.Slot = Item.Slot;
		A.Item = Item.Item;
		A.Rarity = Item.Item == TEXT("orion") ? 3 : 2;
		A.Power = 10;
		A.bEquipped = bWearDefaults && Wardrobe->Defaults.FindRef(Item.Slot) == Item.Item;
		Armor.Add(A);
	}
}

const FSOWeaponInstance* USOInventoryComponent::GetEquipped(int32 Slot) const
{
	return Equipped.IsValidIndex(Slot) ? Find(Equipped[Slot]) : nullptr;
}

int32 USOInventoryComponent::GetPower() const
{
	int32 Sum = 0, Count = 0;
	for (int32 Slot = 0; Slot < NumSlots; ++Slot)
	{
		if (const FSOWeaponInstance* W = GetEquipped(Slot))
		{
			Sum += W->Power;
			++Count;
		}
	}
	return Count > 0 ? FMath::RoundToInt(static_cast<float>(Sum) / Count) : 0;
}

int32 USOInventoryComponent::SlotOf(const FSOWeaponInstance& Weapon) const
{
	const USOLootTables* Tables = USOLootLibrary::GetTables();
	const USOWeaponData* Data = Tables ? Tables->LoadArchetype(Weapon.Archetype) : nullptr;
	return Data ? FMath::Clamp(Data->Slot, 0, NumSlots - 1) : 0;
}

// --- Server ----------------------------------------------------------------------------------------

FString USOInventoryComponent::UniqueUid(FString Uid) const
{
	while (Uid.IsEmpty() || Find(Uid))
	{
		Uid = USOLootLibrary::NewUid(const_cast<FRandomStream&>(Rng));
	}
	return Uid;
}

FSOWeaponInstance USOInventoryComponent::AddWeapon(FSOWeaponInstance Weapon, bool bAnnounce)
{
	Weapon.Uid = UniqueUid(Weapon.Uid);
	Weapon.bNew = true;
	Items.Add(Weapon);
	const USOLootTables* Tables = USOLootLibrary::GetTables();
	if (bAnnounce)
	{
		const USOWeaponData* Data = Tables ? Tables->LoadArchetype(Weapon.Archetype) : nullptr;
		Feed(FString::Printf(TEXT("%s  ·  %s  ·  %d"), *Weapon.Name, Data ? *Data->DisplayName.ToString() : *Weapon.Archetype.ToString(), Weapon.Power),
			Tables ? Tables->GetRarity(Weapon.Rarity).Color : FLinearColor::White);
	}
	// keep the vault bounded: only a plain old spare is broken down, and the player is told
	if (Items.Num() > USOLootLibrary::VaultCap)
	{
		const FSOWeaponInstance* Spare = nullptr;
		for (const FSOWeaponInstance& W : Items)
		{
			if (IsEquipped(W.Uid) || W.bKeep || W.bNew)
			{
				continue;
			}
			if (!Spare || W.Rarity < Spare->Rarity || (W.Rarity == Spare->Rarity && W.Power < Spare->Power))
			{
				Spare = &W;
			}
		}
		if (Spare)
		{
			const FString Name = Spare->Name;
			const int32 Gained = USOLootLibrary::DismantleAlloy(*Spare);
			Alloy += Gained;
			Items.RemoveAll([Uid = Spare->Uid](const FSOWeaponInstance& W) { return W.Uid == Uid; });
			Feed(FString::Printf(TEXT("Vault full  ·  %s dismantled (+%d alloy)"), *Name, Gained), FLinearColor(0.6f, 0.63f, 0.66f));
		}
	}
	// empty slot? equip it straight away
	const int32 Slot = SlotOf(Weapon);
	bool bLoadout = false;
	if (Equipped.IsValidIndex(Slot) && !Find(Equipped[Slot]))
	{
		Equipped[Slot] = Weapon.Uid;
		bLoadout = Slot == ActiveSlot;
	}
	Changed(bLoadout);
	return Weapon;
}

bool USOInventoryComponent::Equip(const FString& Uid)
{
	const FSOWeaponInstance* W = Find(Uid);
	if (!W)
	{
		return false;
	}
	const int32 Slot = SlotOf(*W);
	if (Equipped[Slot] == Uid)
	{
		return true;
	}
	Equipped[Slot] = Uid;
	Changed(Slot == ActiveSlot);
	return true;
}

bool USOInventoryComponent::SelectSlot(int32 Slot)
{
	if (!Equipped.IsValidIndex(Slot) || Slot == ActiveSlot || !GetEquipped(Slot))
	{
		return false;
	}
	ActiveSlot = Slot;
	Changed(true);
	return true;
}

bool USOInventoryComponent::SetKeep(const FString& Uid, bool bKeep)
{
	FSOWeaponInstance* W = const_cast<FSOWeaponInstance*>(Find(Uid));
	if (!W || W->bKeep == bKeep)
	{
		return false;
	}
	W->bKeep = bKeep;
	Changed(false);
	return true;
}

int32 USOInventoryComponent::Dismantle(const FString& Uid)
{
	const FSOWeaponInstance* W = Find(Uid);
	if (!W || IsEquipped(Uid) || W->bKeep)
	{
		return 0;
	}
	const int32 Gained = USOLootLibrary::DismantleAlloy(*W);
	const FString Name = W->Name;
	Items.RemoveAll([&Uid](const FSOWeaponInstance& X) { return X.Uid == Uid; });
	Alloy += Gained;
	Feed(FString::Printf(TEXT("%s dismantled  ·  +%d alloy"), *Name, Gained), FLinearColor(0.6f, 0.63f, 0.66f));
	Changed(false);
	return Gained;
}

void USOInventoryComponent::MarkSeen(const FString& Uid)
{
	if (FSOWeaponInstance* W = const_cast<FSOWeaponInstance*>(Find(Uid)); W && W->bNew)
	{
		W->bNew = false;
		Changed(false);
	}
}

void USOInventoryComponent::MarkAllSeen()
{
	bool bAny = false;
	for (FSOWeaponInstance& W : Items)
	{
		bAny |= W.bNew;
		W.bNew = false;
	}
	if (bAny)
	{
		Changed(false);
	}
}

void USOInventoryComponent::StoreAmmo(const FString& Uid, int32 Mag, int32 Reserve)
{
	if (FSOWeaponInstance* W = const_cast<FSOWeaponInstance*>(Find(Uid)))
	{
		W->Mag = Mag;
		W->Reserve = Reserve;
		if (const UWorld* World = GetWorld())
		{
			StowedAt.Add(Uid, World->GetTimeSeconds());
		}
	}
}

FSOWeaponInstance USOInventoryComponent::PrepareForEquip(const FString& Uid)
{
	FSOWeaponInstance* W = const_cast<FSOWeaponInstance*>(Find(Uid));
	if (!W)
	{
		return FSOWeaponInstance();
	}
	// Autoloader: stowed weapons reload themselves
	if (W->HasPerk(TEXT("autoload")) && W->Mag >= 0 && W->Reserve > 0)
	{
		const double* Since = StowedAt.Find(Uid);
		const FSOWeaponStats S = USOLootLibrary::ComputeStats(*W);
		if (Since && GetWorld() && GetWorld()->GetTimeSeconds() - *Since >= S.Reload)
		{
			const int32 Take = FMath::Min(S.Mag - W->Mag, W->Reserve);
			W->Mag += Take;
			W->Reserve -= Take;
		}
	}
	return *W;
}

void USOInventoryComponent::AddAmmoPickup()
{
	const USOLootTables* Tables = USOLootLibrary::GetTables();
	for (int32 Slot = 0; Slot < NumSlots; ++Slot)
	{
		FSOWeaponInstance* W = const_cast<FSOWeaponInstance*>(GetEquipped(Slot));
		const USOWeaponData* Data = W && Tables ? Tables->LoadArchetype(W->Archetype) : nullptr;
		if (!Data)
		{
			continue;
		}
		const int32 Current = W->Reserve >= 0 ? W->Reserve : Data->ReserveAmmo;
		W->Reserve = FMath::Min(FMath::RoundToInt(Data->ReserveAmmo * 1.5f), Current + FMath::CeilToInt(Data->ReserveAmmo * (Data->Slot == 2 ? 0.15f : 0.25f)));
	}
	Feed(TEXT("Ammo synthesised"), FLinearColor::White);
	Changed(false);
}

void USOInventoryComponent::AddCredits(int32 Amount)
{
	Credits += Amount;
	Changed(false);
}

void USOInventoryComponent::AddAlloy(int32 Amount)
{
	Alloy += Amount;
	Changed(false);
}

void USOInventoryComponent::AddXp(int32 Amount)
{
	Xp += Amount;
	while (Xp >= 600 + Level * 250) // state.js xpForLevel
	{
		Xp -= 600 + Level * 250;
		++Level;
		Feed(FString::Printf(TEXT("Level %d"), Level), FLinearColor(1.0f, 0.85f, 0.3f));
	}
	Changed(false);
}

void USOInventoryComponent::NewProfile()
{
	Items.Reset();
	Equipped.Init(FString(), NumSlots);
	ActiveSlot = 0;
	Credits = 500;
	Alloy = 20;
	Xp = 0;
	Level = 1;
	Armor.Reset();
	Body = TEXT("male");
	GrantWardrobe(true);
	// state.js newSave: the three starters (names as the browser build gives them)...
	struct FStarter { const TCHAR* Arch; int32 Rarity; const TCHAR* Name; };
	const FStarter Starters[] = { { TEXT("auto"), 1, TEXT("") }, { TEXT("handcannon"), 1, TEXT("") }, { TEXT("rocket"), 0, TEXT("") } };
	for (const FStarter& S : Starters)
	{
		FSOWeaponInstance W = USOLootLibrary::MakeWeapon(S.Arch, S.Rarity, 10, Rng); // the gun's own name
		W.bNew = false;
		W.Uid = UniqueUid(W.Uid);
		Items.Add(W);
		Equipped[SlotOf(W)] = W.Uid;
	}
	// ...and grantArmory: every kinetic and horror archetype, locked so it is never dismantled by accident.
	if (const USOLootTables* Tables = USOLootLibrary::GetTables())
	{
		for (const FSOArchetypeEntry& Entry : Tables->Archetypes)
		{
			const USOWeaponData* Data = Entry.Data.LoadSynchronous();
			if (!Data || Data->WeaponClass == ESOWeaponClass::Energy)
			{
				continue;
			}
			FSOWeaponInstance W = USOLootLibrary::MakeWeapon(Entry.Id, Data->WeaponClass == ESOWeaponClass::Horror ? 2 : 1, 10, Rng);
			W.bKeep = true;
			W.Uid = UniqueUid(W.Uid);
			W.Source = TEXT("Armoury");
			Items.Add(W);
			if (Entry.Id == TEXT("rifle"))
			{
				Equipped[0] = W.Uid; // the assault rifle is the primary in hand (its sights and hold are the reference)
			}
		}
	}
	Changed(true, true);
}

bool USOInventoryComponent::LoadProfile()
{
	USOSaveGame* Save = Cast<USOSaveGame>(UGameplayStatics::LoadGameFromSlot(SaveSlot, 0));
	if (!Save || Save->Items.Num() == 0)
	{
		return false;
	}
	const USOLootTables* Tables = USOLootLibrary::GetTables();
	Items.Reset();
	for (const FSOWeaponInstance& W : Save->Items)
	{
		if (!Tables || Tables->LoadArchetype(W.Archetype)) // archetypes that no longer exist are dropped
		{
			FSOWeaponInstance& Kept = Items.Add_GetRef(W);
			FRandomStream Unused(0);
			Kept.Name = USOLootLibrary::WeaponName(W.Archetype, W.Rarity, Unused); // older saves rolled a name per copy
		}
	}
	Equipped = Save->Equipped;
	Equipped.SetNum(NumSlots);
	ActiveSlot = FMath::Clamp(Save->ActiveSlot, 0, NumSlots - 1);
	Credits = Save->Credits;
	Alloy = Save->Alloy;
	Xp = Save->Xp;
	Level = FMath::Max(1, Save->Level);
	Body = USOWardrobeData::Get(Save->Body) ? Save->Body : FName(TEXT("male"));
	Armor = Save->Armor;
	GrantWardrobe(Armor.Num() == 0); // version 1 saves had no armour: the wardrobe, wearing its defaults
	if (!GetEquipped(ActiveSlot))
	{
		for (int32 Slot = 0; Slot < NumSlots; ++Slot)
		{
			if (GetEquipped(Slot))
			{
				ActiveSlot = Slot;
				break;
			}
		}
	}
	Changed(true, true);
	return true;
}

void USOInventoryComponent::SaveProfile() const
{
	if (!bPersist)
	{
		return;
	}
	USOSaveGame* Save = Cast<USOSaveGame>(UGameplayStatics::CreateSaveGameObject(USOSaveGame::StaticClass()));
	Save->Items = Items;
	Save->Equipped = Equipped;
	Save->ActiveSlot = ActiveSlot;
	Save->Credits = Credits;
	Save->Alloy = Alloy;
	Save->Xp = Xp;
	Save->Level = Level;
	Save->Version = 2;
	Save->Armor = Armor;
	Save->Body = Body;
	UGameplayStatics::SaveGameToSlot(Save, SaveSlot, 0);
}

void USOInventoryComponent::Changed(bool bLoadout, bool bOutfit)
{
	if (GetOwner() && GetOwner()->HasAuthority())
	{
		const APlayerState* PS = Cast<APlayerState>(GetOwner());
		const APlayerController* PC = PS ? PS->GetPlayerController() : nullptr;
		if (PC && PC->IsLocalController())
		{
			SaveProfile();
		}
	}
	OnChanged.Broadcast();
	if (bLoadout)
	{
		OnLoadoutChanged.Broadcast();
	}
	if (bOutfit)
	{
		OnOutfitChanged.Broadcast();
	}
}

void USOInventoryComponent::Feed(const FString& Text, const FLinearColor& Color)
{
	OnFeed.Broadcast(Text, Color);
	const APlayerState* PS = Cast<APlayerState>(GetOwner());
	const APlayerController* PC = PS ? PS->GetPlayerController() : nullptr;
	if (PC && !PC->IsLocalController())
	{
		ClientFeed(Text, Color);
	}
}

void USOInventoryComponent::ClientFeed_Implementation(const FString& Text, FLinearColor Color)
{
	OnFeed.Broadcast(Text, Color);
}

void USOInventoryComponent::OnRep_Inventory()
{
	OnChanged.Broadcast();
}

// --- RPCs ------------------------------------------------------------------------------------------

void USOInventoryComponent::ServerEquip_Implementation(const FString& Uid) { Equip(Uid); }
void USOInventoryComponent::ServerSelectSlot_Implementation(int32 Slot) { SelectSlot(Slot); }
void USOInventoryComponent::ServerSetKeep_Implementation(const FString& Uid, bool bKeep) { SetKeep(Uid, bKeep); }
void USOInventoryComponent::ServerDismantle_Implementation(const FString& Uid) { Dismantle(Uid); }
void USOInventoryComponent::ServerMarkSeen_Implementation(const FString& Uid) { MarkSeen(Uid); }
void USOInventoryComponent::ServerEquipArmor_Implementation(const FString& Uid) { EquipArmor(Uid); }
void USOInventoryComponent::ServerSetBody_Implementation(FName NewBody) { SetBody(NewBody); }
