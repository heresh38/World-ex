#include "SOInventoryComponent.h"
#include "SOMelee.h"
#include "SOProgression.h"

#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/PlayerState.h"
#include "Kismet/GameplayStatics.h"
#include "Net/UnrealNetwork.h"
#include "SOCombatTypes.h"
#include "SOLootLibrary.h"
#include "SOCombatCharacter.h"
#include "SOJournal.h"
#include "SOProfileStore.h"
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
	DOREPLIFETIME(USOInventoryComponent, Blades);
	DOREPLIFETIME(USOInventoryComponent, MeleeSlot);
	DOREPLIFETIME(USOInventoryComponent, FaceKeys);
	DOREPLIFETIME(USOInventoryComponent, FaceValues);
	DOREPLIFETIME_CONDITION(USOInventoryComponent, Goods, COND_OwnerOnly);
	DOREPLIFETIME(USOInventoryComponent, SkinTone);
	DOREPLIFETIME(USOInventoryComponent, HairTone);
	DOREPLIFETIME(USOInventoryComponent, HairStyle);
	DOREPLIFETIME(USOInventoryComponent, Beard);
	DOREPLIFETIME_CONDITION(USOInventoryComponent, bCharacterMade, COND_OwnerOnly);
	DOREPLIFETIME_CONDITION(USOInventoryComponent, Learned, COND_OwnerOnly);
	DOREPLIFETIME_CONDITION(USOInventoryComponent, JournalRead, COND_OwnerOnly);
	DOREPLIFETIME_CONDITION(USOInventoryComponent, Tallies, COND_OwnerOnly);
	DOREPLIFETIME(USOInventoryComponent, Equipped);
	DOREPLIFETIME(USOInventoryComponent, ActiveSlot);
	// what a player has in the bank is theirs to see (the copies themselves go to everyone: the guns on a player's
	// back are drawn from them on every machine)
	DOREPLIFETIME_CONDITION(USOInventoryComponent, Credits, COND_OwnerOnly);
	DOREPLIFETIME_CONDITION(USOInventoryComponent, Alloy, COND_OwnerOnly);
	DOREPLIFETIME_CONDITION(USOInventoryComponent, Xp, COND_OwnerOnly);
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

FSOAttributePoints USOInventoryComponent::GetArmorPoints(const FSOArmorInstance& Piece) const
{
	const USOWardrobeData* Wardrobe = USOWardrobeData::Get(Body);
	const FSOWardrobeItem* Item = Wardrobe ? Wardrobe->Find(Piece.Slot, Piece.Item) : nullptr;
	return Item ? USOAttributeTable::Get().ArmourPoints(Piece.Slot, Item->Armor, Piece.Rarity, Piece.Power, Piece.GetSeed()) : FSOAttributePoints();
}

FSOAttributePoints USOInventoryComponent::GetAttributePoints() const
{
	FSOAttributePoints Sum;
	for (const FName Slot : USOWardrobeData::ArmourSlots())
	{
		if (const FSOArmorInstance* A = GetEquippedArmor(Slot))
		{
			Sum += GetArmorPoints(*A);
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
	// the hairstyle chosen, where this body's wardrobe has it (the other body's choice leaves this one's default)
	const USOWardrobeData* Wardrobe = USOWardrobeData::Get(Body);
	if (!HairStyle.IsNone() && Wardrobe && Wardrobe->Find(TEXT("hair"), HairStyle))
	{
		Outfit.Set(TEXT("hair"), HairStyle);
	}
	Outfit.FaceKeys = FaceKeys;
	Outfit.FaceValues = FaceValues;
	Outfit.SkinTone = SkinTone;
	Outfit.HairTone = HairTone;
	Outfit.Beard = Beard;
	return Outfit;
}

void USOInventoryComponent::SetSkinTone(const FLinearColor& Tone)
{
	const FLinearColor Clamped(FMath::Clamp(Tone.R, 0.0f, 1.2f), FMath::Clamp(Tone.G, 0.0f, 1.2f), FMath::Clamp(Tone.B, 0.0f, 1.2f), Tone.A > 0.0f ? 1.0f : 0.0f);
	if (!Clamped.Equals(SkinTone, 1e-4f))
	{
		SkinTone = Clamped;
		Changed(false, true);
	}
}

void USOInventoryComponent::SetHairTone(const FLinearColor& Tone)
{
	const FLinearColor Clamped(FMath::Clamp(Tone.R, 0.0f, 1.0f), FMath::Clamp(Tone.G, 0.0f, 1.0f), FMath::Clamp(Tone.B, 0.0f, 1.0f), Tone.A > 0.0f ? 1.0f : 0.0f);
	if (!Clamped.Equals(HairTone, 1e-4f))
	{
		HairTone = Clamped;
		Changed(false, true);
	}
}

void USOInventoryComponent::SetHairStyle(FName Style)
{
	if (Style != HairStyle)
	{
		HairStyle = Style;
		Changed(false, true);
	}
}

void USOInventoryComponent::SetBeard(FName Style)
{
	const FName Clean = Style == TEXT("none") ? NAME_None : Style;
	if (Clean != Beard)
	{
		Beard = Clean;
		Changed(false, true);
	}
}

void USOInventoryComponent::ServerSetHairStyle_Implementation(FName Style)
{
	SetHairStyle(Style);
}

void USOInventoryComponent::ServerSetBeard_Implementation(FName Style)
{
	SetBeard(Style);
}

void USOInventoryComponent::ServerSetSkinTone_Implementation(FLinearColor Tone)
{
	SetSkinTone(Tone);
}

void USOInventoryComponent::ServerSetHairTone_Implementation(FLinearColor Tone)
{
	SetHairTone(Tone);
}

void USOInventoryComponent::SetLook(const TArray<FName>& Keys, const TArray<float>& Values, const FLinearColor& Skin, const FLinearColor& Hair)
{
	FaceKeys.Reset();
	FaceValues.Reset();
	for (int32 i = 0; i < FMath::Min(Keys.Num(), Values.Num()); ++i)
	{
		const float V = FMath::Clamp(Values[i], -1.0f, 1.0f);
		if (!Keys[i].IsNone() && !FMath::IsNearlyZero(V, 1e-3f) && !FaceKeys.Contains(Keys[i]))
		{
			FaceKeys.Add(Keys[i]);
			FaceValues.Add(V);
		}
	}
	SkinTone = FLinearColor(FMath::Clamp(Skin.R, 0.0f, 1.2f), FMath::Clamp(Skin.G, 0.0f, 1.2f), FMath::Clamp(Skin.B, 0.0f, 1.2f), Skin.A > 0.0f ? 1.0f : 0.0f);
	HairTone = FLinearColor(FMath::Clamp(Hair.R, 0.0f, 1.0f), FMath::Clamp(Hair.G, 0.0f, 1.0f), FMath::Clamp(Hair.B, 0.0f, 1.0f), Hair.A > 0.0f ? 1.0f : 0.0f);
	Changed(false, true);
}

void USOInventoryComponent::ServerSetLook_Implementation(const TArray<FName>& Keys, const TArray<float>& Values, FLinearColor Skin, FLinearColor Hair)
{
	SetLook(Keys, Values, Skin, Hair);
}

void USOInventoryComponent::SetCharacterMade()
{
	if (!bCharacterMade)
	{
		bCharacterMade = true;
		Changed(false, false);
	}
}

void USOInventoryComponent::ServerSetCharacterMade_Implementation()
{
	SetCharacterMade();
}

void USOInventoryComponent::SetFace(FName Key, float Value)
{
	if (Key.IsNone())
	{
		return;
	}
	Value = FMath::Clamp(Value, -1.0f, 1.0f);
	const int32 i = FaceKeys.IndexOfByKey(Key);
	if (FMath::IsNearlyZero(Value, 1e-3f))
	{
		if (i == INDEX_NONE)
		{
			return;
		}
		FaceKeys.RemoveAt(i);
		FaceValues.RemoveAt(i);
	}
	else if (i == INDEX_NONE)
	{
		FaceKeys.Add(Key);
		FaceValues.Add(Value);
	}
	else if (FMath::IsNearlyEqual(FaceValues[i], Value, 1e-4f))
	{
		return;
	}
	else
	{
		FaceValues[i] = Value;
	}
	Changed(false, true);
}

float USOInventoryComponent::GetFace(FName Key) const
{
	const int32 i = FaceKeys.IndexOfByKey(Key);
	return i != INDEX_NONE && FaceValues.IsValidIndex(i) ? FaceValues[i] : 0.0f;
}

void USOInventoryComponent::ServerSetFace_Implementation(FName Key, float Value)
{
	SetFace(Key, Value);
}

bool USOInventoryComponent::EquipArmor(const FString& Uid)
{
	FSOArmorInstance* Piece = Armor.FindByPredicate([&Uid](const FSOArmorInstance& A) { return A.Uid == Uid; });
	if (!Piece)
	{
		return false;
	}
	if (Piece->bEquipped && !USOWardrobeData::IsOptionalSlot(Piece->Slot))
	{
		return false; // a required slot is never emptied: wearing another piece swaps it instead
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
	// What is worn is each body's own: remember what this one has on, then put on what the other had on when it
	// was left (a helmet put on one body is not on the other).
	bool bDressedBefore = false;
	for (FSOArmorInstance& A : Armor)
	{
		if (A.bEquipped)
		{
			A.WornBy.AddUnique(Body);
		}
		else
		{
			A.WornBy.Remove(Body);
		}
		bDressedBefore |= A.WornBy.Contains(NewBody);
	}
	Body = NewBody;
	GrantWardrobe(false);
	const USOWardrobeData* Wardrobe = USOWardrobeData::Get(Body);
	for (FSOArmorInstance& A : Armor)
	{
		// (the first time in this body: its wardrobe's own defaults)
		A.bEquipped = bDressedBefore ? A.WornBy.Contains(Body) : (Wardrobe && Wardrobe->Find(A.Slot, A.Item) && Wardrobe->Defaults.FindRef(A.Slot) == A.Item);
	}
	Dress(); // (a piece this body cannot wear comes off; every required slot that is empty gets its default)
	Changed(false, true);
	return true;
}

void USOInventoryComponent::RestoreArmor(const TArray<FSOArmorInstance>& Saved)
{
	Armor = Saved;
	GrantWardrobe(Armor.Num() == 0); // version 1 saves had no armour: the wardrobe, wearing its defaults
	Dress();                         // older outfits are gone; every required slot is worn
}

void USOInventoryComponent::Dress()
{
	const USOWardrobeData* Male = USOWardrobeData::Get(TEXT("male"));
	const USOWardrobeData* Female = USOWardrobeData::Get(TEXT("female"));
	TSet<FName> Replaced; // slots whose worn piece was an old one: the new default goes on, optional slots included
	if (Male || Female)
	{
		// pieces that exist in neither body's wardrobe any more (an older outfit) are gone from the game
		Armor.RemoveAll([&](const FSOArmorInstance& A)
		{
			const bool bGone = !(Male && Male->Find(A.Slot, A.Item)) && !(Female && Female->Find(A.Slot, A.Item));
			if (bGone && A.bEquipped)
			{
				Replaced.Add(A.Slot);
			}
			return bGone;
		});
	}
	const USOWardrobeData* Wardrobe = USOWardrobeData::Get(Body);
	if (!Wardrobe)
	{
		return;
	}
	for (const FName Slot : USOWardrobeData::ArmourSlots())
	{
		const bool bOptional = USOWardrobeData::IsOptionalSlot(Slot);
		if ((bOptional && !Replaced.Contains(Slot)) || GetEquippedArmor(Slot))
		{
			continue;
		}
		const FName Want = Wardrobe->Defaults.FindRef(Slot);
		FSOArmorInstance* Pick = Armor.FindByPredicate([&](const FSOArmorInstance& X) { return X.Slot == Slot && X.Item == Want; });
		if (!Pick && !bOptional) // no default for this slot: any piece this body can wear
		{
			Pick = Armor.FindByPredicate([&](const FSOArmorInstance& X) { return X.Slot == Slot && Wardrobe->Find(X.Slot, X.Item); });
		}
		if (Pick)
		{
			for (FSOArmorInstance& A : Armor)
			{
				if (A.Slot == Slot)
				{
					A.bEquipped = false;
				}
			}
			Pick->bEquipped = true;
		}
	}
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
		if (!Item.bArmour || !Item.Set.IsNone() || Armor.ContainsByPredicate([&](const FSOArmorInstance& A) { return A.Slot == Item.Slot && A.Item == Item.Item; }))
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

FSOArmorInstance USOInventoryComponent::AddArmorPiece(FName Slot, FName Item, int32 InRarity, int32 InPower, bool bAnnounce)
{
	FSOArmorInstance* Have = Armor.FindByPredicate([&](const FSOArmorInstance& A) { return A.Slot == Slot && A.Item == Item; });
	if (Have)
	{
		// one copy of a piece: a second drop raises it
		Have->Rarity = FMath::Max(Have->Rarity, InRarity);
		Have->Power = FMath::Max(Have->Power, InPower);
		Have->bNew = true;
	}
	else
	{
		FSOArmorInstance A;
		A.Uid = FString::Printf(TEXT("ar_%s_%s_%08x"), *Slot.ToString(), *Item.ToString(), Rng.RandHelper(0x7fffffff));
		A.Slot = Slot;
		A.Item = Item;
		A.Rarity = InRarity;
		A.Power = InPower;
		A.bNew = true;
		Have = &Armor.Add_GetRef(A);
	}
	const FSOArmorInstance Out = *Have;
	if (bAnnounce)
	{
		const USOWardrobeData* Wardrobe = USOWardrobeData::Get(Body);
		const FSOWardrobeItem* Info = Wardrobe ? Wardrobe->Find(Slot, Item) : nullptr;
		const USOLootTables* Tables = USOLootLibrary::GetTables();
		Feed(FString::Printf(TEXT("%s  ·  %s  ·  %d"), Info ? *Info->Label.ToString() : *Item.ToString(), *USOWardrobeData::SlotLabel(Slot).ToString(), Out.Power),
			Tables ? Tables->GetRarity(Out.Rarity).Color : FLinearColor::White);
	}
	Changed(false, Out.bEquipped); // (a worn piece raised: what it gives the body changed)
	return Out;
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
		// the HUD's NEW ITEM card (the gun's own picture, its name, its class line, in its rarity's light)
		FSOFeedItem Item;
		Item.Name = Weapon.Name;
		Item.Archetype = Weapon.Archetype;
		Item.Rarity = Weapon.Rarity;
		Item.Power = Weapon.Power;
		FeedItem(Item);
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
	// the journal: what is known of its maker
	if (const USOWeaponData* Data = Tables ? Tables->LoadArchetype(Weapon.Archetype) : nullptr; Data && !Data->Origin.IsNone())
	{
		Learn(SOJournal::OriginKey(Data->Origin));
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
	const TArray<FSOGoodsCost> Parts = USOLootLibrary::DismantleGoods(*W);
	Items.RemoveAll([&Uid](const FSOWeaponInstance& X) { return X.Uid == Uid; });
	Alloy += Gained;
	Feed(FString::Printf(TEXT("%s dismantled  ·  +%d alloy"), *Name, Gained), FLinearColor(0.6f, 0.63f, 0.66f));
	for (const FSOGoodsCost& Part : Parts)
	{
		AddGoods(Part.Item, Part.Count);
	}
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
	if (W->Mag >= 0 && W->Reserve > 0 && USOLootLibrary::PerkEffects(*W).bAutoload)
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
	Reward(ESORewardKind::Credits, Amount);
	Changed(false);
}

void USOInventoryComponent::AddAlloy(int32 Amount)
{
	Alloy += Amount;
	Reward(ESORewardKind::Alloy, Amount);
	Changed(false);
}

void USOInventoryComponent::AddXp(int32 Amount)
{
	const USOProgressionTable& Rules = USOProgressionTable::Get();
	Xp += FMath::Max(Amount, 0);
	Reward(ESORewardKind::Xp, Amount);
	while (Level < Rules.MaxLevel && Xp >= Rules.XpForLevel(Level))
	{
		Xp -= Rules.XpForLevel(Level);
		++Level;
		Feed(FString::Printf(TEXT("Level %d  ·  gear can now be raised to %d"), Level, Rules.PowerCap(Level)), FLinearColor(1.0f, 0.85f, 0.3f));
		OnLevelUp.Broadcast(Level);
		const APlayerState* PS = Cast<APlayerState>(GetOwner());
		const APlayerController* PC = PS ? PS->GetPlayerController() : nullptr;
		if (PC && !PC->IsLocalController())
		{
			ClientLevelUp(Level);
		}
	}
	if (Level >= Rules.MaxLevel)
	{
		Xp = FMath::Min(Xp, Rules.XpForLevel(Level)); // (nothing more to earn: it does not pile up unseen)
	}
	Changed(false);
}

bool USOInventoryComponent::Spend(int32 InCredits, int32 InAlloy)
{
	if (InCredits < 0 || InAlloy < 0 || Credits < InCredits || Alloy < InAlloy)
	{
		return false;
	}
	Credits -= InCredits;
	Alloy -= InAlloy;
	return true;
}

int32 USOInventoryComponent::GetPowerCap() const
{
	return USOProgressionTable::Get().PowerCap(Level);
}

bool USOInventoryComponent::GetUpgrade(const FString& Uid, int32& OutPower, int32& OutCredits, int32& OutAlloy) const
{
	const USOProgressionTable& Rules = USOProgressionTable::Get();
	const FSOWeaponInstance* W = Find(Uid);
	const FSOArmorInstance* A = W ? nullptr : FindArmor(Uid);
	if (!W && !A)
	{
		return false;
	}
	const int32 Power = W ? W->Power : A->Power;
	OutPower = FMath::Min(Power + FMath::Max(Rules.UpgradeStep, 1), GetPowerCap());
	Rules.UpgradeCost(W ? W->Rarity : A->Rarity, Power, OutCredits, OutAlloy);
	return OutPower > Power;
}

void USOInventoryComponent::GetUpgradeGoods(const FString& Uid, TArray<FSOGoodsCost>& Out) const
{
	Out.Reset();
	const USOProgressionTable& Rules = USOProgressionTable::Get();
	if (const FSOWeaponInstance* W = Find(Uid))
	{
		const USOLootTables* Tables = USOLootLibrary::GetTables();
		const USOWeaponData* Data = Tables ? Tables->LoadArchetype(W->Archetype) : nullptr;
		Rules.UpgradeGoods(USOLootLibrary::ClassId(Data ? Data->WeaponClass : ESOWeaponClass::Kinetic), W->Rarity, Out);
	}
	else if (const FSOArmorInstance* A = FindArmor(Uid))
	{
		Rules.UpgradeGoods(NAME_None, A->Rarity, Out);
	}
}

bool USOInventoryComponent::Upgrade(const FString& Uid)
{
	int32 NewPower = 0, CostCredits = 0, CostAlloy = 0;
	TArray<FSOGoodsCost> Takes;
	GetUpgradeGoods(Uid, Takes);
	if (!GetUpgrade(Uid, NewPower, CostCredits, CostAlloy) || !HasGoods(Takes) || !Spend(CostCredits, CostAlloy))
	{
		return false;
	}
	TakeGoods(Takes);                                        // (held: checked above)
	if (FSOWeaponInstance* W = const_cast<FSOWeaponInstance*>(Find(Uid)))
	{
		W->Power = NewPower;
		Feed(FString::Printf(TEXT("%s raised to %d"), *W->Name, NewPower), FLinearColor(0.95f, 0.72f, 0.32f));
		Changed(IsEquipped(Uid) && Equipped.IsValidIndex(ActiveSlot) && Equipped[ActiveSlot] == Uid); // (the gun in hand takes its new numbers)
	}
	else if (FSOArmorInstance* A = Armor.FindByPredicate([&Uid](const FSOArmorInstance& X) { return X.Uid == Uid; }))
	{
		A->Power = NewPower;
		const USOWardrobeData* Wardrobe = USOWardrobeData::Get(Body);
		const FSOWardrobeItem* Info = Wardrobe ? Wardrobe->Find(A->Slot, A->Item) : nullptr;
		Feed(FString::Printf(TEXT("%s raised to %d"), Info ? *Info->Label.ToString() : *A->Item.ToString(), NewPower), FLinearColor(0.95f, 0.72f, 0.32f));
		Changed(false, A->bEquipped); // (worn: what it gives the body grew)
	}
	return true;
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
	FaceKeys.Reset();
	FaceValues.Reset();
	SkinTone = HairTone = FLinearColor(0.0f, 0.0f, 0.0f, 0.0f);
	HairStyle = Beard = NAME_None;
	bCharacterMade = false;                                     // (a new player: the builder opens at the first start)
	Learned.Reset();
	JournalRead.Reset();
	Tallies.Reset();
	StarterGoods(Goods);
	GrantWardrobe(true);
	Dress();
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
	LearnOwnedOrigins();
	Changed(true, true);
}

bool USOInventoryComponent::LoadProfile()
{
	// the profile store is the one place that knows where a profile is kept
	const UGameInstance* Game = GetWorld() ? GetWorld()->GetGameInstance() : nullptr;
	USOProfileStore* Store = Game ? Game->GetSubsystem<USOProfileStore>() : nullptr;
	USOSaveGame* Save = Store ? Store->Load(SaveSlot) : nullptr;
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
	RestoreArmor(Save->Armor);
	Blades = Save->Blades;
	MeleeSlot = Blades.Contains(Save->MeleeSlot) ? Save->MeleeSlot : NAME_None;
	Goods.Reset();
	for (const FSOGoodsStack& Stack : Save->Goods)
	{
		// (items that no longer exist are dropped; none past its stack)
		const FSOGoodsInfo* Info = Tables ? Tables->FindGoods(Stack.Id) : nullptr;
		if (Stack.Count > 0 && (Info || !Tables) && !Goods.ContainsByPredicate([&Stack](const FSOGoodsStack& G) { return G.Id == Stack.Id; }))
		{
			FSOGoodsStack& Kept = Goods.Add_GetRef(Stack);
			Kept.Count = Info ? FMath::Min(Stack.Count, FMath::Max(1, Info->Stack)) : Stack.Count;
		}
	}
	SkinTone = Save->SkinTone;
	HairTone = Save->HairTone;
	HairStyle = Save->HairStyle;
	Beard = Save->Beard;
	bCharacterMade = Save->bCharacterMade;
	Learned = Save->Learned;
	JournalRead = Save->JournalRead;
	Tallies = Save->Tallies;
	LearnOwnedOrigins();
	FaceKeys.Reset();
	FaceValues.Reset();
	for (int32 i = 0; i < FMath::Min(Save->FaceKeys.Num(), Save->FaceValues.Num()); ++i)
	{
		FaceKeys.Add(Save->FaceKeys[i]);
		FaceValues.Add(FMath::Clamp(Save->FaceValues[i], -1.0f, 1.0f));
	}
	FString Worn;
	for (const FSOArmorInstance& A : Armor)
	{
		Worn += FString::Printf(TEXT(" %s=%s%s"), *A.Slot.ToString(), *A.Item.ToString(), A.bEquipped ? TEXT("*") : TEXT(""));
	}
	UE_LOG(LogSOCombat, Log, TEXT("Profile loaded: %s body, %d saved armour pieces -> %d (* worn):%s"), *Body.ToString(), Save->Armor.Num(), Armor.Num(), *Worn);
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

void USOInventoryComponent::ServerSetMeleeSlot_Implementation(FName Style)
{
	// a blade this player owns, or None: the fists
	const FName Want = Style == TEXT("fists") ? NAME_None : Style;
	if ((!Want.IsNone() && !Blades.Contains(Want)) || Want == MeleeSlot)
	{
		return;
	}
	MeleeSlot = Want;
	Changed(true);
}

void USOInventoryComponent::AddBlade(FName Style)
{
	if (Style.IsNone() || Blades.Contains(Style))
	{
		return;
	}
	Blades.Add(Style);
	if (MeleeSlot.IsNone())
	{
		MeleeSlot = Style;                                   // (the first blade goes in the empty melee slot)
	}
	const USOMeleeTable* Table = USOMeleeTable::Get();
	const FSOMeleeStyle* Info = Table ? Table->Find(Style) : nullptr;
	Feed(FString::Printf(TEXT("+ %s (hand to hand: key 4)"), Info && !Info->Name.IsEmpty() ? *Info->Name.ToString() : *Style.ToString()),
		FLinearColor(1.0f, 0.7f, 0.3f));
	Changed(false);
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
	Save->Armor = Armor;
	Save->Body = Body;
	Save->Blades = Blades;
	Save->MeleeSlot = MeleeSlot;
	Save->FaceKeys = FaceKeys;
	Save->FaceValues = FaceValues;
	Save->Goods = Goods;
	Save->SkinTone = SkinTone;
	Save->HairTone = HairTone;
	Save->HairStyle = HairStyle;
	Save->Beard = Beard;
	Save->bCharacterMade = bCharacterMade;
	Save->Learned = Learned;
	Save->JournalRead = JournalRead;
	Save->Tallies = Tallies;
	const UGameInstance* Game = GetWorld() ? GetWorld()->GetGameInstance() : nullptr;
	if (USOProfileStore* Store = Game ? Game->GetSubsystem<USOProfileStore>() : nullptr)
	{
		Store->Commit(SaveSlot, Save); // off the game thread, never a half-written file
	}
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

// --- Collected items ----------------------------------------------------------------------------------

int32 USOInventoryComponent::CountOf(FName Id) const
{
	const FSOGoodsStack* Stack = Goods.FindByPredicate([Id](const FSOGoodsStack& G) { return G.Id == Id; });
	return Stack ? Stack->Count : 0;
}

bool USOInventoryComponent::HasGoods(const TArray<FSOGoodsCost>& Costs) const
{
	for (const FSOGoodsCost& Cost : Costs)
	{
		// (one item named twice is counted together)
		int32 Want = 0;
		for (const FSOGoodsCost& Each : Costs)
		{
			Want += Each.Item == Cost.Item ? FMath::Max(Each.Count, 0) : 0;
		}
		if (CountOf(Cost.Item) < Want)
		{
			return false;
		}
	}
	return true;
}

int32 USOInventoryComponent::AddGoods(FName Id, int32 Count, bool bAnnounce)
{
	const USOLootTables* Tables = USOLootLibrary::GetTables();
	const FSOGoodsInfo* Info = Tables ? Tables->FindGoods(Id) : nullptr;
	if (!Info || Count <= 0)
	{
		return 0;
	}
	FSOGoodsStack* Stack = Goods.FindByPredicate([Id](const FSOGoodsStack& G) { return G.Id == Id; });
	if (!Stack)
	{
		Stack = &Goods.AddDefaulted_GetRef();
		Stack->Id = Id;
	}
	const int32 Room = FMath::Max(0, FMath::Max(1, Info->Stack) - Stack->Count);
	const int32 Added = FMath::Min(Count, Room);
	if (Added <= 0)
	{
		return 0;                                            // (full: what came in is lost)
	}
	Stack->Count += Added;
	Stack->bNew = true;
	if (bAnnounce)
	{
		const FLinearColor Color = Tables->GetRarity(Info->Rarity).Color;
		Feed(Added > 1 || Info->Stack > 1 ? FString::Printf(TEXT("+%d  %s"), Added, *Info->Name.ToString()) : FString::Printf(TEXT("+  %s"), *Info->Name.ToString()),
			FLinearColor(Color.R, Color.G, Color.B, 1.0f));
	}
	Changed(false);
	return Added;
}

bool USOInventoryComponent::TakeGoods(const TArray<FSOGoodsCost>& Costs)
{
	if (!HasGoods(Costs))
	{
		return false;
	}
	for (const FSOGoodsCost& Cost : Costs)
	{
		if (FSOGoodsStack* Stack = Goods.FindByPredicate([&Cost](const FSOGoodsStack& G) { return G.Id == Cost.Item; }))
		{
			Stack->Count -= FMath::Max(Cost.Count, 0);
		}
	}
	Goods.RemoveAll([](const FSOGoodsStack& G) { return G.Count <= 0; });
	Changed(false);
	return true;
}

namespace
{
	ASOCombatCharacter* BodyOf(const USOInventoryComponent* Inventory)
	{
		const APlayerState* PS = Inventory ? Cast<APlayerState>(Inventory->GetOwner()) : nullptr;
		return PS ? Cast<ASOCombatCharacter>(PS->GetPawn()) : nullptr;
	}
}

bool USOInventoryComponent::CanUseGoods(FName Id) const
{
	const USOLootTables* Tables = USOLootLibrary::GetTables();
	const FSOGoodsInfo* Info = Tables ? Tables->FindGoods(Id) : nullptr;
	const ASOCombatCharacter* User = BodyOf(this);
	if (!Info || Info->Kind != ESOGoodsKind::Consumable || CountOf(Id) <= 0 || !User || User->IsDead())
	{
		return false;
	}
	// it does something: what it gives is short somewhere
	return (Info->Heal > 0.0f && User->GetHealth() < User->GetMaxHealth() - 0.5f)
		|| (Info->Shield > 0.0f && User->GetShield() < User->GetMaxShield() - 0.5f)
		|| (Info->Ultimate > 0.0f && User->GetUltimate() < User->GetMaxUltimate() - 0.01f);
}

bool USOInventoryComponent::UseGoods(FName Id)
{
	if (!CanUseGoods(Id))
	{
		return false;
	}
	const FSOGoodsInfo* Info = USOLootLibrary::GetTables()->FindGoods(Id);
	ASOCombatCharacter* User = BodyOf(this);
	if (Info->Heal > 0.0f)
	{
		User->Heal(User->GetMaxHealth() * Info->Heal);
	}
	if (Info->Shield > 0.0f)
	{
		User->AddShield(User->GetMaxShield() * Info->Shield);
	}
	if (Info->Ultimate > 0.0f)
	{
		User->AddUltimate(User->GetMaxUltimate() * Info->Ultimate);
	}
	TakeGoods({ { Id, 1 } });
	Feed(FString::Printf(TEXT("%s used"), *Info->Name.ToString()), FLinearColor(0.42f, 0.95f, 0.55f));
	return true;
}

void USOInventoryComponent::MarkGoodsSeen(FName Id)
{
	if (FSOGoodsStack* Stack = Goods.FindByPredicate([Id](const FSOGoodsStack& G) { return G.Id == Id; }); Stack && Stack->bNew)
	{
		Stack->bNew = false;
		Changed(false);
	}
}

void USOInventoryComponent::StarterGoods(TArray<FSOGoodsStack>& Out)
{
	Out.Reset();
	const USOLootTables* Tables = USOLootLibrary::GetTables();
	if (!Tables)
	{
		return;
	}
	// in the goods' own order, so the starting stock reads like the inventory
	for (const FSOGoodsInfo& Info : Tables->Goods)
	{
		if (const int32* Count = Tables->StarterGoods.Find(Info.Id); Count && *Count > 0)
		{
			Out.Add({ Info.Id, FMath::Min(*Count, FMath::Max(1, Info.Stack)), false });
		}
	}
}

// --- The journal -----------------------------------------------------------------------------------------

void USOInventoryComponent::Learn(FName Key)
{
	if (Key.IsNone() || Key == SOJournal::StartKey() || Learned.Contains(Key))
	{
		return;
	}
	Learned.Add(Key);
	// a line in the feed for each entry it shows (an operation's own come with its banner and its radio)
	for (const FSOJournalEntry* E : FSOJournalData::Get().UnlockedBy(Key))
	{
		if (E->Section != TEXT("operations"))
		{
			Feed(FString::Printf(TEXT("JOURNAL  ·  %s"), *E->Title), FLinearColor(0.55f, 0.85f, 1.0f));
		}
	}
	Changed(false);
}

bool USOInventoryComponent::HasLearned(FName Key) const
{
	return Key == SOJournal::StartKey() || Learned.Contains(Key);
}

bool USOInventoryComponent::IsJournalOpen(FName EntryId) const
{
	const FSOJournalEntry* E = FSOJournalData::Get().Find(EntryId);
	return E && HasLearned(E->Unlock);
}

bool USOInventoryComponent::IsJournalNew(FName EntryId) const
{
	return IsJournalOpen(EntryId) && !JournalRead.Contains(EntryId);
}

bool USOInventoryComponent::HasJournalNew() const
{
	for (const FSOJournalEntry& E : FSOJournalData::Get().Entries)
	{
		if (HasLearned(E.Unlock) && !JournalRead.Contains(E.Id))
		{
			return true;
		}
	}
	return false;
}

void USOInventoryComponent::MarkJournalRead(FName EntryId)
{
	if (IsJournalNew(EntryId))
	{
		JournalRead.Add(EntryId);
		Changed(false);
	}
}

void USOInventoryComponent::Tally(FName Key, int32 Add)
{
	if (Key.IsNone() || Add == 0)
	{
		return;
	}
	FSOTally* T = Tallies.FindByPredicate([Key](const FSOTally& Each) { return Each.Key == Key; });
	if (!T)
	{
		T = &Tallies.AddDefaulted_GetRef();
		T->Key = Key;
	}
	T->Count = FMath::Max(0, T->Count + Add);
	Changed(false);
}

int32 USOInventoryComponent::GetTally(FName Key) const
{
	const FSOTally* T = Tallies.FindByPredicate([Key](const FSOTally& Each) { return Each.Key == Key; });
	return T ? T->Count : 0;
}

void USOInventoryComponent::LearnOwnedOrigins()
{
	const USOLootTables* Tables = USOLootLibrary::GetTables();
	for (const FSOWeaponInstance& W : Items)
	{
		if (const USOWeaponData* Data = Tables ? Tables->LoadArchetype(W.Archetype) : nullptr; Data && !Data->Origin.IsNone())
		{
			Learned.AddUnique(SOJournal::OriginKey(Data->Origin));
		}
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

void USOInventoryComponent::Reward(ESORewardKind Kind, int32 Amount)
{
	if (Amount <= 0)
	{
		return;
	}
	OnReward.Broadcast(Kind, Amount);
	const APlayerState* PS = Cast<APlayerState>(GetOwner());
	const APlayerController* PC = PS ? PS->GetPlayerController() : nullptr;
	if (PC && !PC->IsLocalController())
	{
		ClientReward(static_cast<uint8>(Kind), Amount);
	}
}

void USOInventoryComponent::ClientReward_Implementation(uint8 Kind, int32 Amount)
{
	OnReward.Broadcast(static_cast<ESORewardKind>(Kind), Amount);
}

void USOInventoryComponent::ClientLevelUp_Implementation(int32 NewLevel)
{
	OnLevelUp.Broadcast(NewLevel);
}

void USOInventoryComponent::FeedItem(const FSOFeedItem& Item)
{
	OnFeedItem.Broadcast(Item);
	const APlayerState* PS = Cast<APlayerState>(GetOwner());
	const APlayerController* PC = PS ? PS->GetPlayerController() : nullptr;
	if (PC && !PC->IsLocalController())
	{
		ClientFeedItem(Item);
	}
}

void USOInventoryComponent::ClientFeedItem_Implementation(const FSOFeedItem& Item)
{
	OnFeedItem.Broadcast(Item);
}

void USOInventoryComponent::OnRep_Inventory()
{
	OnChanged.Broadcast();
}

// --- RPCs ------------------------------------------------------------------------------------------

// What a joined player asks for. Each call only ever touches that player's own copies (a uid is looked up in their
// own list, a slot is checked against its range), so the one thing to refuse here is a string no uid could be.
namespace
{
	bool PlausibleUid(const FString& Uid) { return Uid.Len() > 0 && Uid.Len() <= 64; }
}
void USOInventoryComponent::ServerEquip_Implementation(const FString& Uid) { if (PlausibleUid(Uid)) { Equip(Uid); } }
void USOInventoryComponent::ServerSelectSlot_Implementation(int32 Slot) { SelectSlot(Slot); }
void USOInventoryComponent::ServerUseGoods_Implementation(FName Id) { UseGoods(Id); }
void USOInventoryComponent::ServerMarkGoodsSeen_Implementation(FName Id) { MarkGoodsSeen(Id); }
void USOInventoryComponent::ServerMarkJournalRead_Implementation(FName EntryId) { MarkJournalRead(EntryId); }
void USOInventoryComponent::ServerSetKeep_Implementation(const FString& Uid, bool bKeep) { if (PlausibleUid(Uid)) { SetKeep(Uid, bKeep); } }
void USOInventoryComponent::ServerDismantle_Implementation(const FString& Uid) { if (PlausibleUid(Uid)) { Dismantle(Uid); } }
void USOInventoryComponent::ServerMarkSeen_Implementation(const FString& Uid) { if (PlausibleUid(Uid)) { MarkSeen(Uid); } }
void USOInventoryComponent::ServerEquipArmor_Implementation(const FString& Uid) { if (PlausibleUid(Uid)) { EquipArmor(Uid); } }
void USOInventoryComponent::ServerUpgrade_Implementation(const FString& Uid) { if (PlausibleUid(Uid)) { Upgrade(Uid); } }
void USOInventoryComponent::ServerSetBody_Implementation(FName NewBody) { SetBody(NewBody); }
