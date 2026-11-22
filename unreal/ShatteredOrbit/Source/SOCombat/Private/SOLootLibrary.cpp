#include "SOLootLibrary.h"

#include "SOWeaponData.h"

namespace
{
	const TCHAR* TablesPath = TEXT("/Game/Data/DA_LootTables.DA_LootTables");

	const FSORarityInfo& FallbackRarity()
	{
		static const FSORarityInfo Common;
		return Common;
	}

	template <typename T>
	const T& Pick(const TArray<T>& List, FRandomStream& Rng)
	{
		return List[FMath::Clamp(FMath::FloorToInt(Rng.FRand() * List.Num()), 0, List.Num() - 1)];
	}
}

// --- Tables ----------------------------------------------------------------------------------------

const FSORarityInfo& USOLootTables::GetRarity(int32 Index) const
{
	return Rarities.IsValidIndex(Index) ? Rarities[Index] : FallbackRarity();
}

const FSOPerkInfo* USOLootTables::FindPerk(FName Id) const
{
	return Perks.FindByPredicate([Id](const FSOPerkInfo& P) { return P.Id == Id; });
}

const FSOSightInfo* USOLootTables::FindSight(FName Id) const
{
	return Sights.FindByPredicate([Id](const FSOSightInfo& S) { return S.Id == Id; });
}

const FSOGoodsInfo* USOLootTables::FindGoods(FName Id) const
{
	return Goods.FindByPredicate([Id](const FSOGoodsInfo& G) { return G.Id == Id; });
}

const FSOGunGroup* USOLootTables::FindFamily(FName Id) const
{
	return Families.FindByPredicate([Id](const FSOGunGroup& G) { return G.Id == Id; });
}

const FSOGunGroup* USOLootTables::FindOrigin(FName Id) const
{
	return Origins.FindByPredicate([Id](const FSOGunGroup& G) { return G.Id == Id; });
}

FName USOLootLibrary::ClassId(ESOWeaponClass Class)
{
	switch (Class)
	{
	case ESOWeaponClass::Energy: return TEXT("energy");
	case ESOWeaponClass::Horror: return TEXT("horror");
	default: return TEXT("kinetic");
	}
}

void USOLootLibrary::RollGoods(FName ListKey, FRandomStream& Rng, TArray<FSOGoodsCost>& Out)
{
	const USOLootTables* Tables = GetTables();
	const FSOGoodsDropList* List = Tables && !ListKey.IsNone() ? Tables->GoodsDrops.Find(ListKey) : nullptr;
	if (!List)
	{
		return;
	}
	for (const FSOGoodsDrop& Drop : List->Drops)
	{
		if (Drop.Item.IsNone() || Rng.FRand() >= Drop.Chance)
		{
			continue;
		}
		const int32 Count = Rng.RandRange(FMath::Max(1, Drop.Min), FMath::Max(Drop.Min, Drop.Max));
		if (FSOGoodsCost* Had = Out.FindByPredicate([&Drop](const FSOGoodsCost& C) { return C.Item == Drop.Item; }))
		{
			Had->Count += Count;                                 // (two lines of one item: one amount)
		}
		else
		{
			Out.Add({ Drop.Item, Count });
		}
	}
}

TArray<FSOGoodsCost> USOLootLibrary::DismantleGoods(const FSOWeaponInstance& Weapon)
{
	TArray<FSOGoodsCost> Out;
	const USOLootTables* Tables = GetTables();
	const USOWeaponData* Data = Tables ? Tables->LoadArchetype(Weapon.Archetype) : nullptr;
	if (!Data)
	{
		return Out;
	}
	auto ByRarity = [&Weapon](const TArray<int32>& Counts) { return Counts.Num() > 0 ? Counts[FMath::Clamp(Weapon.Rarity, 0, Counts.Num() - 1)] : 0; };
	if (const FName* Material = Tables->DismantleGoods.Find(ClassId(Data->WeaponClass)))
	{
		if (const int32 Count = ByRarity(Tables->DismantleCount); Count > 0 && !Material->IsNone())
		{
			Out.Add({ *Material, Count });
		}
	}
	if (const int32 Crystal = ByRarity(Tables->DismantleCrystal); Crystal > 0 && !Tables->DismantleCrystalItem.IsNone())
	{
		Out.Add({ Tables->DismantleCrystalItem, Crystal });
	}
	return Out;
}

USOWeaponData* USOLootTables::LoadArchetype(FName Id) const
{
	const FSOArchetypeEntry* Entry = Archetypes.FindByPredicate([Id](const FSOArchetypeEntry& E) { return E.Id == Id; });
	return Entry ? Entry->Data.LoadSynchronous() : nullptr;
}

USOLootTables* USOLootLibrary::GetTables()
{
	static TWeakObjectPtr<USOLootTables> Cached;
	if (!Cached.IsValid())
	{
		Cached = TSoftObjectPtr<USOLootTables>(FSoftObjectPath(TablesPath)).LoadSynchronous();
	}
	return Cached.Get();
}

// --- Rolls -----------------------------------------------------------------------------------------

FString USOLootLibrary::NewUid(FRandomStream& Rng)
{
	static int32 Counter = 0;
	return FString::Printf(TEXT("w%08x%04x%03d"), static_cast<uint32>(FDateTime::UtcNow().GetTicks() & 0xffffffff), ++Counter & 0xffff,
		FMath::FloorToInt(Rng.FRand() * 1000.0f));
}

int32 USOLootLibrary::RollRarity(FRandomStream& Rng, float Bonus)
{
	const float R = Rng.FRand() + Bonus;
	if (R > 0.985f) return 4;
	if (R > 0.9f) return 3;
	if (R > 0.68f) return 2;
	if (R > 0.38f) return 1;
	return 0;
}

FName USOLootLibrary::RandomArchetype(FRandomStream& Rng, int32 Slot)
{
	const USOLootTables* Tables = GetTables();
	if (!Tables)
	{
		return TEXT("rifle");
	}
	TArray<TPair<FName, float>> Pool;
	float Total = 0.0f;
	for (const FSOArchetypeEntry& Entry : Tables->Archetypes)
	{
		const USOWeaponData* Data = Entry.Data.LoadSynchronous();
		if (Data && Data->LootWeight > 0.0f && (Slot < 0 || Data->Slot == Slot))
		{
			Pool.Emplace(Entry.Id, Data->LootWeight);
			Total += Data->LootWeight;
		}
	}
	if (Pool.Num() == 0)
	{
		return TEXT("rifle");
	}
	float R = Rng.FRand() * Total;
	for (const TPair<FName, float>& P : Pool)
	{
		R -= P.Value;
		if (R <= 0.0f)
		{
			return P.Key;
		}
	}
	return Pool.Last().Key;
}

FString USOLootLibrary::WeaponName(FName Archetype, int32 Rarity, FRandomStream& Rng)
{
	const USOLootTables* Tables = GetTables();
	if (!Tables)
	{
		return Archetype.ToString();
	}
	// One name per gun, whatever the rarity or rolls: the copies differ by their rolls and perks.
	const USOWeaponData* Data = Tables->LoadArchetype(Archetype);
	if (Data && !Data->Title.IsEmpty())
	{
		return Data->Title.ToString();
	}
	if (const FString* Fixed = Tables->ExoticNames.Find(Archetype))
	{
		return *Fixed;
	}
	const ESOWeaponClass Class = Data ? Data->WeaponClass : ESOWeaponClass::Energy;
	if (Class == ESOWeaponClass::Kinetic && Tables->Maker.Num() > 0)
	{
		const FString* Code = Tables->ModelCode.Find(Archetype);
		const FString& Maker = Pick(Tables->Maker, Rng);
		return FString::Printf(TEXT("%s %s-%d"), *Maker, Code ? **Code : TEXT("M"), 10 + FMath::FloorToInt(Rng.FRand() * 89.0f));
	}
	if (Class == ESOWeaponClass::Horror && Tables->BioPrefix.Num() > 0 && Tables->BioNoun.Num() > 0)
	{
		const FString& A = Pick(Tables->BioPrefix, Rng);
		return A + TEXT(" ") + Pick(Tables->BioNoun, Rng);
	}
	if (Tables->Prefix.Num() > 0 && Tables->Noun.Num() > 0)
	{
		const FString& A = Pick(Tables->Prefix, Rng);
		return A + TEXT(" ") + Pick(Tables->Noun, Rng);
	}
	return Archetype.ToString();
}

FSOWeaponInstance USOLootLibrary::MakeWeapon(FName Archetype, int32 Rarity, int32 Power, FRandomStream& Rng)
{
	const USOLootTables* Tables = GetTables();
	FSOWeaponInstance W;
	W.Archetype = Archetype;
	W.Rarity = FMath::Clamp(Rarity, 0, 4);
	W.Power = FMath::Max(1, Power);
	if (const USOWeaponData* Data = Tables ? Tables->LoadArchetype(Archetype) : nullptr; Data && !Data->DefaultShader.IsNone())
	{
		W.Shader = Data->DefaultShader;
	}
	if (Tables)
	{
		// the perks this gun's class can roll (a perk that names no class is anyone's)
		const USOWeaponData* Kind = Tables->LoadArchetype(Archetype);
		const FName Class = !Kind ? NAME_None : (Kind->WeaponClass == ESOWeaponClass::Kinetic ? FName(TEXT("kinetic"))
			: (Kind->WeaponClass == ESOWeaponClass::Energy ? FName(TEXT("energy")) : FName(TEXT("horror"))));
		TArray<FSOPerkInfo> Pool;
		for (const FSOPerkInfo& Perk : Tables->Perks)
		{
			if (Perk.Classes.Num() == 0 || Perk.Classes.Contains(Class))
			{
				Pool.Add(Perk);
			}
		}
		const int32 Count = FMath::Min(Tables->GetRarity(W.Rarity).Perks, Pool.Num());
		while (W.Perks.Num() < Count)
		{
			const FName Perk = Pick(Pool, Rng).Id;
			if (!W.Perks.Contains(Perk))
			{
				W.Perks.Add(Perk);
			}
		}
	}
	W.Uid = NewUid(Rng);
	W.Name = WeaponName(Archetype, W.Rarity, Rng);
	if (const USOWeaponData* Data = Tables ? Tables->LoadArchetype(Archetype) : nullptr)
	{
		W.Sight = Data->DefaultSight;
	}
	// Rolls keep every copy close to the gun it is (a few percent either way); perks are what set copies apart.
	auto Roll = [&Rng]() { return 0.94f + Rng.FRand() * 0.12f; };
	W.Stats.Damage = 0.97f + Rng.FRand() * 0.06f;
	W.Stats.Rpm = 0.98f + Rng.FRand() * 0.04f;
	W.Stats.Stability = Roll();
	W.Stats.Range = Roll();
	W.Stats.Handling = Roll();
	return W;
}

FSOWeaponInstance USOLootLibrary::RollWeapon(int32 Power, const FSORollOptions& Options, FRandomStream& Rng)
{
	const FName Arch = Options.Archetype.IsNone() ? RandomArchetype(Rng, Options.Slot) : Options.Archetype;
	const int32 Rarity = Options.Rarity >= 0 ? Options.Rarity : RollRarity(Rng, Options.RarityBonus);
	FSOWeaponInstance W = MakeWeapon(Arch, Rarity, FMath::Max(1, Power), Rng);
	const USOLootTables* Tables = GetTables();
	if (const USOWeaponData* Data = Tables ? Tables->LoadArchetype(Arch) : nullptr; Data && Data->Sights.Num() > 0)
	{
		W.Sight = Pick(Data->Sights, Rng);
	}
	W.Source = Options.Source;
	return W;
}

void FSOPerkInfo::Add(const FSOPerkInfo& Other)
{
	Magazine *= Other.Magazine;
	Reload *= Other.Reload;
	Spread *= Other.Spread;
	Recoil *= Other.Recoil;
	Precision *= Other.Precision;
	FireRateShieldDown *= Other.FireRateShieldDown;
	KillDamage += Other.KillDamage;
	KillDamageStacks = FMath::Max(KillDamageStacks, Other.KillDamageStacks);
	KillDamageTime = FMath::Max(KillDamageTime, Other.KillDamageTime);
	KillHeal += Other.KillHeal;
	PrecisionSplash += Other.PrecisionSplash;
	PrecisionSplashRadius = FMath::Max(PrecisionSplashRadius, Other.PrecisionSplashRadius);
	bAutoload |= Other.bAutoload;
	KillMagazine += Other.KillMagazine;
	bKillShield |= Other.bKillShield;
	KillReload *= Other.KillReload;
	KillReloadTime = FMath::Max(KillReloadTime, Other.KillReloadTime);
	OpeningDamage *= Other.OpeningDamage;
	OpeningAfter = FMath::Max(OpeningAfter, Other.OpeningAfter);
	LowMagDamage *= Other.LowMagDamage;
	LowMagShare = FMath::Max(LowMagShare, Other.LowMagShare);
	HipSpread *= Other.HipSpread;
	ShieldDamage *= Other.ShieldDamage;
	HealthDamage *= Other.HealthDamage;
	HitSlow = FMath::Min(HitSlow, Other.HitSlow);
	HitSlowTime = FMath::Max(HitSlowTime, Other.HitSlowTime);
	PrecisionBurn += Other.PrecisionBurn;
	PrecisionBurnTime = FMath::Max(PrecisionBurnTime, Other.PrecisionBurnTime);
	bNoFalloff |= Other.bNoFalloff;
	Noise *= Other.Noise;
	bSlideReload |= Other.bSlideReload;
}

bool FSOPerkInfo::DoesAnything() const
{
	return Magazine != 1.0f || Reload != 1.0f || Spread != 1.0f || Recoil != 1.0f || Precision != 1.0f || FireRateShieldDown != 1.0f
		|| KillDamage > 0.0f || KillHeal > 0.0f || PrecisionSplash > 0.0f || bAutoload || KillMagazine > 0.0f || bKillShield
		|| KillReload != 1.0f || OpeningDamage != 1.0f || LowMagDamage != 1.0f || HipSpread != 1.0f || ShieldDamage != 1.0f
		|| HealthDamage != 1.0f || HitSlow != 1.0f || PrecisionBurn > 0.0f || bNoFalloff || Noise != 1.0f || bSlideReload;
}

FSOPerkInfo USOLootLibrary::PerkEffects(const FSOWeaponInstance& W)
{
	FSOPerkInfo All;
	if (const USOLootTables* Tables = GetTables())
	{
		for (const FName& Id : W.Perks)
		{
			if (const FSOPerkInfo* Perk = Tables->FindPerk(Id))
			{
				All.Add(*Perk);
			}
		}
	}
	return All;
}

FSOWeaponStats USOLootLibrary::ComputeStats(const FSOWeaponInstance& W)
{
	const USOLootTables* Tables = GetTables();
	return ComputeStatsFor(Tables ? Tables->LoadArchetype(W.Archetype) : nullptr, W);
}

FSOWeaponStats USOLootLibrary::ComputeStatsFor(const USOWeaponData* A, const FSOWeaponInstance& W)
{
	FSOWeaponStats S;
	if (!A)
	{
		return S;
	}
	const USOLootTables* Tables = GetTables();
	// Rarity brings more perks; its damage bonus is kept small (a fifth of data.js's rarity multiplier).
	const float Mult = 1.0f + ((Tables ? Tables->GetRarity(W.Rarity).Mult : 1.0f) - 1.0f) * 0.2f;
	const FSOWeaponRolls& R = W.Stats;
	S.Damage = A->Damage * Mult * R.Damage * (1.0f + W.Power / 200.0f);
	S.Rpm = A->RoundsPerMinute * R.Rpm;
	// what its perks do, as the data says (never by a perk's name)
	S.Perks = PerkEffects(W);
	S.Mag = FMath::RoundToInt(A->MagazineSize * S.Perks.Magazine);
	S.Reserve = A->ReserveAmmo;
	S.Reload = A->ReloadTime * S.Perks.Reload / (0.9f + R.Handling * 0.1f);
	S.Range = A->Range * R.Range;
	S.Spread = A->Spread * S.Perks.Spread / FMath::Max(R.Stability, 0.1f);
	S.Crit = A->CritMultiplier * S.Perks.Precision;
	S.Recoil = S.Perks.Recoil;
	S.Zoom = A->AimZoom;
	if (const FSOSightInfo* Sight = Tables ? Tables->FindSight(W.Sight) : nullptr; Sight && Sight->Zoom > 0.0f && W.Sight != TEXT("default"))
	{
		S.Zoom = Sight->Zoom;
	}
	return S;
}

int32 USOLootLibrary::RollQuality(const FSOWeaponInstance& W)
{
	auto Norm = [](float V, float Lo, float Span) { return FMath::Clamp((V - Lo) / Span, 0.0f, 1.0f); };
	const FSOWeaponRolls& R = W.Stats;
	const float Sum = Norm(R.Damage, 0.97f, 0.06f) + Norm(R.Rpm, 0.98f, 0.04f) + Norm(R.Stability, 0.94f, 0.12f) + Norm(R.Range, 0.94f, 0.12f)
		+ Norm(R.Handling, 0.94f, 0.12f);
	return FMath::RoundToInt(Sum / 5.0f * 100.0f);
}

int32 USOLootLibrary::RollKillDrop(int32 Level, bool bBrute, FRandomStream& Rng, float Chance)
{
	if (Rng.FRand() >= Chance)
	{
		return -1;
	}
	return RollRarity(Rng, Level * 0.006f + (bBrute ? 0.12f : 0.0f));
}

TArray<FSOWeaponInstance> USOLootLibrary::RollReliquary(int32 PlayerPower, FRandomStream& Rng, const FString& Source)
{
	TArray<FSOWeaponInstance> Out;
	const int32 Count = 2 + (Rng.FRand() < 0.5f ? 1 : 0);
	for (int32 k = 0; k < Count; ++k)
	{
		// pickWeighted({1: 22, 2: 40, 3: 29, 4: 9})
		float R = Rng.FRand() * 100.0f;
		int32 Rarity = 1;
		for (const TPair<int32, float>& Entry : { TPair<int32, float>(1, 22.0f), TPair<int32, float>(2, 40.0f), TPair<int32, float>(3, 29.0f), TPair<int32, float>(4, 9.0f) })
		{
			R -= Entry.Value;
			Rarity = Entry.Key;
			if (R <= 0.0f)
			{
				break;
			}
		}
		FSORollOptions Options;
		Options.Rarity = Rarity;
		Options.Source = Source;
		const int32 Power = PlayerPower + FMath::RoundToInt(Rng.FRand() * 7.0f - 1.0f) + (Rarity >= 3 ? 2 : 0);
		Out.Add(RollWeapon(Power, Options, Rng));
	}
	return Out;
}
