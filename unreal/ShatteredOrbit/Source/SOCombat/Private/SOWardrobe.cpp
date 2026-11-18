#include "SOWardrobe.h"

const FSOWardrobeItem* USOWardrobeData::Find(FName Slot, FName Item) const
{
	return Items.FindByPredicate([&](const FSOWardrobeItem& I) { return I.Slot == Slot && I.Item == Item; });
}

USOWardrobeData* USOWardrobeData::Get(FName Body)
{
	const bool bFemale = Body == TEXT("female");
	const TCHAR* Path = bFemale ? TEXT("/Game/Characters/PlayerFemale/DA_Wardrobe.DA_Wardrobe") : TEXT("/Game/Characters/PlayerMale/DA_Wardrobe.DA_Wardrobe");
	return TSoftObjectPtr<USOWardrobeData>(FSoftObjectPath(Path)).LoadSynchronous();
}

const TArray<FName>& USOWardrobeData::ArmourSlots()
{
	static const TArray<FName> Slots = { TEXT("head"), TEXT("top"), TEXT("vest"), TEXT("outer"), TEXT("hands"), TEXT("legs"), TEXT("feet") };
	return Slots;
}

bool USOWardrobeData::IsOptionalSlot(FName Slot)
{
	// every armour slot may be left empty: the undersuit (its own slot, "suit", never armour) is always worn and
	// can never come off, and armour goes on over it (the owner, 2026-11-17: "the undersuit is on at all times and
	// armor goes on top of that so the undersuit can't come off and the rest of the armor slots can be empty")
	return ArmourSlots().Contains(Slot);
}

FText USOWardrobeData::SlotLabel(FName Slot)
{
	static const TMap<FName, FText> Labels = {
		{ TEXT("head"), NSLOCTEXT("SO", "SlotHead", "Head") }, { TEXT("top"), NSLOCTEXT("SO", "SlotChest", "Chest") },
		{ TEXT("vest"), NSLOCTEXT("SO", "SlotRig", "Rig") }, { TEXT("outer"), NSLOCTEXT("SO", "SlotCoat", "Coat") },
		{ TEXT("hands"), NSLOCTEXT("SO", "SlotHands", "Hands") }, { TEXT("legs"), NSLOCTEXT("SO", "SlotLegs", "Legs") },
		{ TEXT("feet"), NSLOCTEXT("SO", "SlotFeet", "Feet") } };
	const FText* L = Labels.Find(Slot);
	return L ? *L : FText::FromName(Slot);
}
