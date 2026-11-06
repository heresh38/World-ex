#include "SOWeaponData.h"

const FSOWeaponPart* USOWeaponData::FindPart(FName PartName) const
{
	return Parts.FindByPredicate([PartName](const FSOWeaponPart& Part) { return Part.Name == PartName; });
}
