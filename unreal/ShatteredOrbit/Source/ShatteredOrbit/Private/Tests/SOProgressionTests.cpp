// Phase 4 of Project Orion: armour that counts. The six character attributes: what a point is worth, what a piece
// gives, how the body takes them from what is worn, and what each one changes. All single-machine (the server's side).

#include "SOTestWorld.h"

#if WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR

#include "Abilities/SOAbilitySet.h"
#include "GameFramework/PlayerController.h"
#include "SOAbilitySystemComponent.h"
#include "SOAttributes.h"
#include "SOCharacterMovementComponent.h"
#include "SOCombatStatics.h"
#include "SOInventoryComponent.h"
#include "SOLootLibrary.h"
#include "SOPlayerState.h"
#include "SOProgression.h"
#include "SOWardrobe.h"

namespace
{
	FSOAttributePoints Only(ESOAttribute A, int32 Points)
	{
		FSOAttributePoints P;
		P.At(A) = Points;
		return P;
	}

	float Life(const ASOCharacter* C)
	{
		return C->GetHealth() + C->GetShield();
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOAttributeRulesTest, "ShatteredOrbit.Attributes.RulesAndArmourPoints", SOTest::Flags)
bool FSOAttributeRulesTest::RunTest(const FString& Parameters)
{
	const USOAttributeTable& T = USOAttributeTable::Get();
	TestTrue(TEXT("the table is the imported one (SO_IMPORT_ONLY=attributes)"), &T != GetDefault<USOAttributeTable>());
	TestEqual(TEXT("six rules"), T.Rules.Num(), static_cast<int32>(ESOAttribute::Count));
	for (int32 i = 0; i < static_cast<int32>(ESOAttribute::Count); ++i)
	{
		const ESOAttribute A = static_cast<ESOAttribute>(i);
		TestFalse(TEXT("every attribute has a name of its own"), T.Rule(A).Name.IsEmpty());
		TestEqual(TEXT("no points: nothing changes"), T.Scale(A, 0.0f), 1.0f);
		TestEqual(TEXT("at the most it is the rule's own scale"), T.Scale(A, T.Max), T.Rule(A).AtMax);
		TestEqual(TEXT("more than the most does nothing more"), T.Scale(A, T.Max * 3.0f), T.Rule(A).AtMax);
		TestEqual(TEXT("half way is half way"), T.Scale(A, T.Max * 0.5f), (1.0f + T.Rule(A).AtMax) * 0.5f, 0.0001f);
	}
	TestTrue(TEXT("plating takes damage off, never adds"), T.Rule(ESOAttribute::Plating).AtMax < 1.0f && T.Rule(ESOAttribute::Plating).AtMax >= 0.5f);
	TestTrue(TEXT("stride is a little speed, not a lot"), T.Rule(ESOAttribute::Stride).AtMax > 1.0f && T.Rule(ESOAttribute::Stride).AtMax <= 1.15f);

	// a piece: its budget from its armour, rarity and power; most of it where its slot leans; the same every time
	const FSOAttributePoints Vest = T.ArmourPoints(TEXT("vest"), 20, 2, 10, 12345u);
	const int32 Budget = FMath::RoundToInt(20 * T.PointsPerArmour * T.RarityScale[2] * (1.0f + 10 * T.PerPower));
	TestEqual(TEXT("a piece's points add up to its budget"), Vest.Total(), Budget);
	TestEqual(TEXT("most of them where the slot leans (a vest: plating)"), Vest.Get(ESOAttribute::Plating), FMath::RoundToInt(Budget * T.Lean));
	int32 Given = 0;
	for (const int32 P : Vest.Points)
	{
		Given += P > 0;
	}
	TestEqual(TEXT("and the rest in two others"), Given, 3);
	TestTrue(TEXT("the same piece gives the same every time"), T.ArmourPoints(TEXT("vest"), 20, 2, 10, 12345u) == Vest);
	bool bDiffers = false;
	for (uint32 Seed = 1; Seed < 12 && !bDiffers; ++Seed)
	{
		bDiffers = !(T.ArmourPoints(TEXT("vest"), 20, 2, 10, Seed) == Vest);
	}
	TestTrue(TEXT("another copy rolls differently"), bDiffers);
	TestTrue(TEXT("a better rarity gives more"), T.ArmourPoints(TEXT("vest"), 20, 4, 10, 12345u).Total() > Vest.Total());
	TestTrue(TEXT("more power gives more"), T.ArmourPoints(TEXT("vest"), 20, 2, 60, 12345u).Total() > Vest.Total());
	TestEqual(TEXT("a piece with no armour gives nothing"), T.ArmourPoints(TEXT("vest"), 0, 4, 60, 12345u).Total(), 0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOAttributeBodyTest, "ShatteredOrbit.Attributes.GearChangesTheBody", SOTest::Flags)
bool FSOAttributeBodyTest::RunTest(const FString& Parameters)
{
	// Each attribute, alone, at the most: what it changes on a body and by how much (the table's own numbers), and
	// that it is gone when the gear comes off.
	const USOAttributeTable& T = USOAttributeTable::Get();
	const int32 Most = FMath::RoundToInt(T.Max);
	SOTest::FTestWorld W;
	W.AddBox(FVector(-3000, -3000, -100), FVector(3000, 3000, 0));
	ASOCharacter* P = W.SpawnCharacter(FVector(0, 0, 0));
	USOAbilitySet* Kit = USOAbilitySet::Load(TEXT("vanguard"));
	if (!TestNotNull(TEXT("player"), P) || !TestNotNull(TEXT("the vanguard kit (SO_IMPORT_ONLY=kits)"), Kit))
	{
		return false;
	}
	P->GrantAbilitySet(Kit);
	W.Run(0.5f);

	// plating
	float Before = Life(P);
	USOCombatStatics::ApplyDamage(nullptr, P, 40.0f, false);
	TestEqual(TEXT("bare: a blow of 40 takes 40"), Before - Life(P), 40.0f, 0.01f);
	P->SetGearAttributes(Only(ESOAttribute::Plating, Most));
	TestEqual(TEXT("the body has the points"), P->GetAttribute(ESOAttribute::Plating), static_cast<float>(Most));
	Before = Life(P);
	USOCombatStatics::ApplyDamage(nullptr, P, 40.0f, false);
	TestEqual(TEXT("full plating: the same blow takes the rule's share"), Before - Life(P), 40.0f * T.Rule(ESOAttribute::Plating).AtMax, 0.01f);
	P->SetGearAttributes(FSOAttributePoints());
	TestEqual(TEXT("off again: the points are gone"), P->GetAttribute(ESOAttribute::Plating), 0.0f);
	Before = Life(P);
	USOCombatStatics::ApplyDamage(nullptr, P, 10.0f, false);
	TestEqual(TEXT("and a blow is a whole blow again"), Before - Life(P), 10.0f, 0.01f);

	// stride
	const float Speed = P->GetCharacterMovement()->GetMaxSpeed();
	P->SetGearAttributes(Only(ESOAttribute::Stride, Most));
	TestEqual(TEXT("full stride: faster by the rule"), P->GetCharacterMovement()->GetMaxSpeed(), Speed * T.Rule(ESOAttribute::Stride).AtMax, 0.5f);
	P->SetGearAttributes(Only(ESOAttribute::Stride, Most / 2));
	TestEqual(TEXT("half: half of it"), P->GetCharacterMovement()->GetMaxSpeed(), Speed * (1.0f + T.Rule(ESOAttribute::Stride).AtMax) * 0.5f, 0.5f);

	// ordnance and impact: the grenade and the melee come back sooner, each by its own attribute
	const FSOAbilityGrant* Grenade = Kit->Find(ESOAbilitySlot::Grenade);
	const FSOAbilityGrant* Melee = Kit->Find(ESOAbilitySlot::Melee);
	if (TestNotNull(TEXT("grenade"), Grenade) && TestNotNull(TEXT("melee"), Melee))
	{
		P->SetGearAttributes(Only(ESOAttribute::Ordnance, Most));
		TestEqual(TEXT("ordnance is the grenade's"), P->GetAbilityCooldownScale(ESOAbilitySlot::Grenade), T.Rule(ESOAttribute::Ordnance).AtMax);
		TestEqual(TEXT("and not the melee's"), P->GetAbilityCooldownScale(ESOAbilitySlot::Melee), 1.0f);
		int32 Charges = 0, Max = 0;
		float Left = 0.0f, Cooldown = 0.0f;
		TestTrue(TEXT("a charge thrown"), P->ActivateSlot(ESOAbilitySlot::Grenade));
		W.Run(Grenade->WindUp + 0.3f);
		P->GetAbilityState(ESOAbilitySlot::Grenade, Charges, Max, Left, Cooldown);
		TestEqual(TEXT("it is back in the rule's share of the time"), Left, Grenade->Cooldown * T.Rule(ESOAttribute::Ordnance).AtMax - Grenade->WindUp - 0.3f, 0.35f);
		P->SetGearAttributes(Only(ESOAttribute::Impact, Most));
		TestEqual(TEXT("impact is the melee's"), P->GetAbilityCooldownScale(ESOAbilitySlot::Melee), T.Rule(ESOAttribute::Impact).AtMax);
		TestEqual(TEXT("and not the class ability's"), P->GetAbilityCooldownScale(ESOAbilitySlot::Class), 1.0f);
	}

	// mending: hurt, the shield starts back sooner
	P->SetGearAttributes(FSOAttributePoints());
	W.Run(12.0f); // (whole again)
	const float FullShield = P->GetShield();
	if (TestTrue(TEXT("the player has a shield"), FullShield > 20.0f))
	{
		const float Wait = P->GetSOAbilitySystem()->ShieldRegenDelay;
		USOCombatStatics::ApplyDamage(nullptr, P, 20.0f, false);
		W.Run(Wait * 0.8f);
		TestEqual(TEXT("bare: still waiting at four fifths of the wait"), P->GetShield(), FullShield - 20.0f, 0.01f);
		W.Run(Wait * 0.2f + 3.0f);
		P->SetGearAttributes(Only(ESOAttribute::Mending, Most));
		USOCombatStatics::ApplyDamage(nullptr, P, 20.0f, false);
		W.Run(Wait * T.Rule(ESOAttribute::Mending).AtMax + 0.4f);
		TestTrue(TEXT("full mending: already refilling by then"), P->GetShield() > FullShield - 20.0f + 1.0f);
	}

	// focus: the ultimate charges faster
	ASOCharacter* Q = W.SpawnCharacter(FVector(600, 0, 0));
	Q->GrantAbilitySet(Kit);
	P->SetGearAttributes(Only(ESOAttribute::Focus, Most));
	const float P0 = P->GetUltimate(), Q0 = Q->GetUltimate();
	W.Run(20.0f);
	const float Fast = P->GetUltimate() - P0, Slow = Q->GetUltimate() - Q0;
	TestTrue(FString::Printf(TEXT("full focus charges the ultimate faster (%.1f against %.1f in 20 s)"), Fast, Slow), Slow > 3.0f && Fast > Slow * (T.Rule(ESOAttribute::Focus).AtMax - 0.15f));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOAttributeWornTest, "ShatteredOrbit.Attributes.WornArmourFeedsTheBody", SOTest::Flags)
bool FSOAttributeWornTest::RunTest(const FString& Parameters)
{
	// The whole way: a player with an inventory takes a body; the body's attributes are what the worn pieces give;
	// taking a piece off or putting another on changes them at once.
	if (SOTest::PlayerBodyMissing(*this))
	{
		return true;
	}
	SOTest::FTestWorld W;
	W.AddBox(FVector(-2000, -2000, -100), FVector(2000, 2000, 0));
	APlayerController* PC = W.World->SpawnActor<APlayerController>();
	PC->SetAsLocalPlayerController();
	ASOPlayerState* PS = W.World->SpawnActor<ASOPlayerState>();
	PC->PlayerState = PS;
	USOInventoryComponent* Inventory = PS->FindComponentByClass<USOInventoryComponent>();
	if (!TestNotNull(TEXT("inventory"), Inventory))
	{
		return false;
	}
	Inventory->bPersist = false;
	ASOCharacter* Body = W.SpawnCharacter(FVector(0, 0, 0));
	PC->Possess(Body);
	W.Run(0.3f);
	const FSOAttributePoints Worn = Inventory->GetAttributePoints();
	if (Worn.Total() == 0)
	{
		AddWarning(TEXT("the wardrobe gives no armour (clothing not imported): skipped"));
		return true;
	}
	AddInfo(FString::Printf(TEXT("the starting outfit gives: plating %d, mending %d, stride %d, ordnance %d, impact %d, focus %d (armour rating %d)"),
		Worn.Get(ESOAttribute::Plating), Worn.Get(ESOAttribute::Mending), Worn.Get(ESOAttribute::Stride), Worn.Get(ESOAttribute::Ordnance),
		Worn.Get(ESOAttribute::Impact), Worn.Get(ESOAttribute::Focus), Inventory->GetArmorRating()));
	for (int32 i = 0; i < static_cast<int32>(ESOAttribute::Count); ++i)
	{
		const ESOAttribute A = static_cast<ESOAttribute>(i);
		TestEqual(TEXT("the body has what the worn pieces give"), Body->GetAttribute(A), static_cast<float>(Worn.Get(A)));
	}
	TestTrue(TEXT("a starting outfit is under the most in everything (room to grow)"), Worn.Get(ESOAttribute::Plating) < USOAttributeTable::Get().Max);

	// the coat is optional: off, and what it gave is gone from the body
	const FSOArmorInstance* Coat = Inventory->GetEquippedArmor(TEXT("outer"));
	if (TestNotNull(TEXT("a coat is worn"), Coat))
	{
		const FString Uid = Coat->Uid;
		const FSOAttributePoints Gave = Inventory->GetArmorPoints(*Coat);
		TestTrue(TEXT("the coat gives something"), Gave.Total() > 0);
		TestTrue(TEXT("taken off"), Inventory->EquipArmor(Uid));
		W.Run(0.1f);
		TestEqual(TEXT("its plating is gone from the body"), Body->GetAttribute(ESOAttribute::Plating), static_cast<float>(Worn.Get(ESOAttribute::Plating) - Gave.Get(ESOAttribute::Plating)));
		TestTrue(TEXT("put back on"), Inventory->EquipArmor(Uid));
		W.Run(0.1f);
		TestEqual(TEXT("and back with it"), Body->GetAttribute(ESOAttribute::Plating), static_cast<float>(Worn.Get(ESOAttribute::Plating)));
	}
	// a better copy of a worn piece (a reward raising it): the body follows
	if (const FSOArmorInstance* Vest = Inventory->GetEquippedArmor(TEXT("vest")))
	{
		const int32 Had = Inventory->GetArmorPoints(*Vest).Total();
		Inventory->AddArmorPiece(Vest->Slot, Vest->Item, 4, Vest->Power + 30, false);
		W.Run(0.1f);
		const FSOArmorInstance* Raised = Inventory->GetEquippedArmor(TEXT("vest"));
		TestTrue(TEXT("the raised piece gives more"), Raised && Inventory->GetArmorPoints(*Raised).Total() > Had);
		TestEqual(TEXT("and the body has it at once"), Body->GetAttribute(ESOAttribute::Plating), static_cast<float>(Inventory->GetAttributePoints().Get(ESOAttribute::Plating)));
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOUpgradeTest, "ShatteredOrbit.Progression.UpgradesAndLevels", SOTest::Flags)
bool FSOUpgradeTest::RunTest(const FString& Parameters)
{
	// Credits and alloy have a use: raising a piece's power. It is paid for in full or not done; a level sets how
	// far it can go; a raised gun hits harder and a raised armour piece gives more.
	const USOProgressionTable& Rules = USOProgressionTable::Get();
	TestTrue(TEXT("the table is the imported one (SO_IMPORT_ONLY=progression)"), &Rules != GetDefault<USOProgressionTable>());
	USOInventoryComponent* Inv = NewObject<USOInventoryComponent>();
	Inv->bPersist = false;
	Inv->NewProfile();
	if (!TestTrue(TEXT("a new profile owns a gun"), Inv->GetItems().Num() > 0))
	{
		return false;
	}
	const FString Gun = Inv->GetItems()[0].Uid;
	const int32 Power0 = Inv->GetItems()[0].Power, Rarity = Inv->GetItems()[0].Rarity;
	TestEqual(TEXT("a level-one character's gear can go this far"), Inv->GetPowerCap(), Rules.PowerCap(1));

	int32 NewPower = 0, CostCredits = 0, CostAlloy = 0, WantCredits = 0, WantAlloy = 0;
	if (!TestTrue(TEXT("the gun can be raised"), Inv->GetUpgrade(Gun, NewPower, CostCredits, CostAlloy)))
	{
		return false;
	}
	Rules.UpgradeCost(Rarity, Power0, WantCredits, WantAlloy);
	TestEqual(TEXT("by one step"), NewPower, Power0 + Rules.UpgradeStep);
	TestTrue(TEXT("for the table's price"), CostCredits == WantCredits && CostAlloy == WantAlloy && CostCredits > 0 && CostAlloy > 0);
	const float Damage0 = USOLootLibrary::ComputeStats(*Inv->Find(Gun)).Damage;
	const int32 Credits0 = Inv->GetCredits(), Alloy0 = Inv->GetAlloy();
	TestTrue(TEXT("raised"), Inv->Upgrade(Gun));
	TestEqual(TEXT("its power went up"), Inv->Find(Gun)->Power, NewPower);
	TestEqual(TEXT("the credits were paid"), Inv->GetCredits(), Credits0 - CostCredits);
	TestEqual(TEXT("and the alloy"), Inv->GetAlloy(), Alloy0 - CostAlloy);
	TestTrue(TEXT("a raised gun hits harder"), USOLootLibrary::ComputeStats(*Inv->Find(Gun)).Damage > Damage0);

	// short of either: nothing is taken and nothing changes
	TestTrue(TEXT("spending everything"), Inv->Spend(Inv->GetCredits(), 0));
	const int32 PowerNow = Inv->Find(Gun)->Power, AlloyNow = Inv->GetAlloy();
	TestFalse(TEXT("without credits it is refused"), Inv->Upgrade(Gun));
	TestTrue(TEXT("and nothing was taken or changed"), Inv->Find(Gun)->Power == PowerNow && Inv->GetAlloy() == AlloyNow && Inv->GetCredits() == 0);
	TestFalse(TEXT("nothing can be paid with what is not there"), Inv->Spend(1, 0));
	TestFalse(TEXT("nor a negative price"), Inv->Spend(-5, 0));

	// to the cap and no further; a level moves the cap
	Inv->AddCredits(1000000);
	Inv->AddAlloy(100000);
	int32 Steps = 0;
	while (Inv->Upgrade(Gun) && Steps < 200)
	{
		++Steps;
	}
	TestEqual(TEXT("it stops at what the level allows"), Inv->Find(Gun)->Power, Inv->GetPowerCap());
	TestFalse(TEXT("and says so"), Inv->GetUpgrade(Gun, NewPower, CostCredits, CostAlloy));
	const int32 Cap1 = Inv->GetPowerCap();
	Inv->AddXp(Rules.XpForLevel(1));
	TestEqual(TEXT("exactly the level's experience is a level"), Inv->GetLevel(), 2);
	TestEqual(TEXT("with nothing left over"), Inv->GetXp(), 0);
	TestEqual(TEXT("a level lets gear go further"), Inv->GetPowerCap(), Cap1 + Rules.PowerCapPerLevel);
	TestTrue(TEXT("so the gun can be raised again"), Inv->Upgrade(Gun));
	Inv->AddXp(100000000);
	TestEqual(TEXT("levels stop at the table's last"), Inv->GetLevel(), Rules.MaxLevel);

	// an armour piece: raised, it gives more
	if (Inv->GetArmor().Num() > 0)
	{
		const FSOArmorInstance* Piece = Inv->GetEquippedArmor(TEXT("vest"));
		Piece = Piece ? Piece : &Inv->GetArmor()[0];
		const FString Uid = Piece->Uid;
		const int32 Gave = Inv->GetArmorPoints(*Piece).Total();
		for (int32 i = 0; i < 10; ++i)
		{
			Inv->Upgrade(Uid);
		}
		TestTrue(TEXT("a raised armour piece gives more"), Inv->GetArmorPoints(*Inv->FindArmor(Uid)).Total() > Gave);
	}
	else
	{
		AddWarning(TEXT("no armour in a new profile (clothing not imported): the armour half is skipped"));
	}
	TestFalse(TEXT("something not owned cannot be raised"), Inv->Upgrade(TEXT("no_such_thing")));
	return true;
}

#endif
