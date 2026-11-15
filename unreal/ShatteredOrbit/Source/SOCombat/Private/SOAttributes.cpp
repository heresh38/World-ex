#include "SOAttributes.h"

int32 FSOAttributePoints::Total() const
{
	int32 Sum = 0;
	for (const int32 P : Points)
	{
		Sum += P;
	}
	return Sum;
}

FSOAttributePoints& FSOAttributePoints::operator+=(const FSOAttributePoints& Other)
{
	for (int32 i = 0; i < static_cast<int32>(ESOAttribute::Count); ++i)
	{
		Points[i] += Other.Points[i];
	}
	return *this;
}

bool FSOAttributePoints::operator==(const FSOAttributePoints& Other) const
{
	for (int32 i = 0; i < static_cast<int32>(ESOAttribute::Count); ++i)
	{
		if (Points[i] != Other.Points[i])
		{
			return false;
		}
	}
	return true;
}

USOAttributeTable::USOAttributeTable()
{
	// The defaults are the data's own numbers (Data/game_data.json "attributes"), so a build whose table was never
	// imported behaves the same.
	auto Add = [this](ESOAttribute A, const TCHAR* Name, const TCHAR* Effect, float AtMax, float AtMax2 = 1.0f)
	{
		FSOAttributeRule& R = Rules.AddDefaulted_GetRef();
		R.Attribute = A;
		R.Name = FText::FromString(Name);
		R.Effect = FText::FromString(Effect);
		R.AtMax = AtMax;
		R.AtMax2 = AtMax2;
	};
	Add(ESOAttribute::Plating, TEXT("Plating"), TEXT("Less of every damage taken"), 0.75f);
	Add(ESOAttribute::Mending, TEXT("Mending"), TEXT("The shield refills sooner and faster"), 0.6f, 1.6f);
	Add(ESOAttribute::Stride, TEXT("Stride"), TEXT("Moves faster"), 1.08f);
	Add(ESOAttribute::Ordnance, TEXT("Ordnance"), TEXT("The grenade comes back sooner"), 0.65f);
	Add(ESOAttribute::Impact, TEXT("Impact"), TEXT("The melee comes back sooner"), 0.65f);
	Add(ESOAttribute::Focus, TEXT("Focus"), TEXT("The ultimate charges faster"), 1.4f);
	RarityScale = { 1.0f, 1.15f, 1.3f, 1.5f, 1.7f };
	SlotLean = { { TEXT("head"), ESOAttribute::Focus }, { TEXT("top"), ESOAttribute::Mending }, { TEXT("vest"), ESOAttribute::Plating },
		{ TEXT("outer"), ESOAttribute::Plating }, { TEXT("hands"), ESOAttribute::Impact }, { TEXT("legs"), ESOAttribute::Ordnance },
		{ TEXT("feet"), ESOAttribute::Stride } };
}

const FSOAttributeRule& USOAttributeTable::Rule(ESOAttribute Attribute) const
{
	for (const FSOAttributeRule& R : Rules)
	{
		if (R.Attribute == Attribute)
		{
			return R;
		}
	}
	static const FSOAttributeRule None;
	return None;
}

float USOAttributeTable::Scale(ESOAttribute Attribute, float Points) const
{
	return FMath::Lerp(1.0f, Rule(Attribute).AtMax, FMath::Clamp(Points / FMath::Max(Max, 1.0f), 0.0f, 1.0f));
}

float USOAttributeTable::Scale2(ESOAttribute Attribute, float Points) const
{
	return FMath::Lerp(1.0f, Rule(Attribute).AtMax2, FMath::Clamp(Points / FMath::Max(Max, 1.0f), 0.0f, 1.0f));
}

FSOAttributePoints USOAttributeTable::ArmourPoints(FName Slot, int32 ArmourRating, int32 Rarity, int32 Power, uint32 Seed) const
{
	FSOAttributePoints Out;
	const int32 Count = static_cast<int32>(ESOAttribute::Count);
	const float ByRarity = RarityScale.Num() > 0 ? RarityScale[FMath::Clamp(Rarity, 0, RarityScale.Num() - 1)] : 1.0f;
	const int32 Budget = FMath::RoundToInt(FMath::Max(ArmourRating, 0) * PointsPerArmour * ByRarity * (1.0f + FMath::Max(Power, 0) * PerPower));
	if (Budget <= 0)
	{
		return Out;
	}
	// the copy's own roll: which two other attributes it gives, and how the rest is shared between them
	FRandomStream Rng(static_cast<int32>(Seed));
	const ESOAttribute* Named = SlotLean.Find(Slot);
	const int32 LeanTo = Named ? static_cast<int32>(*Named) : Rng.RandHelper(Count);
	int32 A = Rng.RandHelper(Count - 1);
	A += A >= LeanTo ? 1 : 0;
	int32 B = Rng.RandHelper(Count - 2);
	for (const int32 Taken : { FMath::Min(LeanTo, A), FMath::Max(LeanTo, A) })
	{
		B += B >= Taken ? 1 : 0;
	}
	const int32 ToLean = FMath::RoundToInt(Budget * FMath::Clamp(Lean, 0.0f, 1.0f));
	const int32 ToA = FMath::RoundToInt((Budget - ToLean) * Rng.FRandRange(0.35f, 0.65f));
	Out.Points[LeanTo] = ToLean;
	Out.Points[A] = ToA;
	Out.Points[B] = Budget - ToLean - ToA;
	return Out;
}

const USOAttributeTable& USOAttributeTable::Get()
{
	static TWeakObjectPtr<const USOAttributeTable> Loaded;
	if (!Loaded.IsValid())
	{
		// (kept for good: a table this small, read from the damage gate, is never worth loading twice)
		if (USOAttributeTable* Table = Cast<USOAttributeTable>(FSoftObjectPath(TEXT("/Game/Data/DA_Attributes.DA_Attributes")).TryLoad()))
		{
			Table->AddToRoot();
			Loaded = Table;
		}
	}
	return Loaded.IsValid() ? *Loaded : *GetDefault<USOAttributeTable>();
}
