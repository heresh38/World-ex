// The HUD's own pieces of the owner's ideas: the quick-use key for consumables (tapped: used; held: the next one
// chosen) and the ring round the crosshair that points where a blow came from.

#include "SOTestWorld.h"

#if WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR

#include "GameFramework/PlayerController.h"
#include "SOCombatStatics.h"
#include "SOEnemy.h"
#include "SOHUD.h"
#include "SOInventoryComponent.h"
#include "SOLootLibrary.h"
#include "SOPlayerState.h"
#include "SOSpecies.h"

namespace
{
	/** A player's body in the world, possessed by a local controller, with an inventory that saves nothing. */
	ASOCharacter* SpawnPlayer(SOTest::FTestWorld& W, USOInventoryComponent*& OutInv)
	{
		APlayerController* PC = W.World->SpawnActor<APlayerController>();
		PC->SetAsLocalPlayerController();
		FActorSpawnParameters Params;
		Params.bDeferConstruction = true;
		ASOPlayerState* PS = W.World->SpawnActor<ASOPlayerState>(ASOPlayerState::StaticClass(), FTransform::Identity, Params);
		PS->GetInventory()->bPersist = false;
		PS->FinishSpawning(FTransform::Identity);
		PC->PlayerState = PS;
		ASOCharacter* Player = W.SpawnCharacter(FVector(0, 0, 0));
		PC->Possess(Player);
		PC->SetControlRotation(FRotator::ZeroRotator);
		OutInv = PS->GetInventory();
		return Player;
	}

	/** Takes every one of an item the inventory holds. */
	void TakeAll(USOInventoryComponent* Inv, FName Id)
	{
		FSOGoodsCost Cost;
		Cost.Item = Id;
		Cost.Count = Inv->CountOf(Id);
		if (Cost.Count > 0)
		{
			Inv->TakeGoods({ Cost });
		}
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOHudQuickUseTest, "ShatteredOrbit.Hud.QuickUseUsesAConsumable", SOTest::Flags)
bool FSOHudQuickUseTest::RunTest(const FString& Parameters)
{
	SOTest::FTestWorld W;
	W.AddBox(FVector(-4000, -4000, -100), FVector(4000, 4000, 0));
	USOInventoryComponent* Inv = nullptr;
	ASOCharacter* Player = SpawnPlayer(W, Inv);
	W.Run(0.2f);
	const USOLootTables* Tables = USOLootLibrary::GetTables();
	if (!TestNotNull(TEXT("inventory"), Inv) || !TestNotNull(TEXT("the loot tables"), Tables))
	{
		return false;
	}
	// none held (the starting stock taken away): nothing is chosen, and the key does nothing but say so
	for (const FSOGoodsInfo& Info : Tables->Goods)
	{
		if (Info.Kind == ESOGoodsKind::Consumable && Inv->CountOf(Info.Id) > 0)
		{
			TakeAll(Inv, Info.Id);
		}
	}
	TestTrue(TEXT("none held: none chosen"), Player->GetQuickUse().IsNone());
	TestFalse(TEXT("so the key does nothing"), Player->QuickUse());
	TestTrue(TEXT("and says it was refused"), Player->WasQuickUseRefused());

	Inv->AddGoods(TEXT("stim"), 2, false);
	Inv->AddGoods(TEXT("cell"), 1, false);
	TestEqual(TEXT("the first held (in the goods' order) is chosen"), Player->GetQuickUse(), FName(TEXT("stim")));
	TestFalse(TEXT("at full health a stim would do nothing: refused"), Player->QuickUse());
	TestEqual(TEXT("and kept"), Inv->CountOf(TEXT("stim")), 2);

	// hurt through the shield into the health: now it is used
	USOCombatStatics::ApplyDamage(nullptr, Player, Player->GetShield() + Player->GetMaxHealth() * 0.5f, false);
	W.Run(0.1f);
	const float Hurt = Player->GetHealth();
	TestTrue(TEXT("the body is hurt"), Hurt < Player->GetMaxHealth() - 1.0f && !Player->IsDead());
	TestTrue(TEXT("tapped, the key uses it"), Player->QuickUse());
	TestFalse(TEXT("not refused"), Player->WasQuickUseRefused());
	W.Run(0.05f);
	TestTrue(TEXT("it gave health back"), Player->GetHealth() > Hurt + 1.0f);
	TestEqual(TEXT("one was used"), Inv->CountOf(TEXT("stim")), 1);

	// held, the key chooses the next one held, round and round; a choice no longer held falls back to the first
	Player->NextQuickUse();
	TestEqual(TEXT("the next one"), Player->GetQuickUse(), FName(TEXT("cell")));
	Player->NextQuickUse();
	TestEqual(TEXT("and round again"), Player->GetQuickUse(), FName(TEXT("stim")));
	const FName Before = Player->GetQuickUse();
	const int32 Stims = Inv->CountOf(TEXT("stim")), Cells = Inv->CountOf(TEXT("cell"));
	Player->HandleQuickUsePressed();
	W.Run(0.5f);
	Player->HandleQuickUseReleased();
	TestTrue(TEXT("holding the key chose another"), Player->GetQuickUse() != Before);
	TestTrue(TEXT("and used nothing"), Inv->CountOf(TEXT("stim")) == Stims && Inv->CountOf(TEXT("cell")) == Cells);
	TakeAll(Inv, TEXT("cell"));
	TestEqual(TEXT("the chosen one used up: the first held"), Player->GetQuickUse(), FName(TEXT("stim")));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOHudDamageFromTest, "ShatteredOrbit.Hud.DamageShowsWhereItCameFrom", SOTest::Flags)
bool FSOHudDamageFromTest::RunTest(const FString& Parameters)
{
	// the ring's angle: ahead is up, to the right is right, behind is down, to the left is left (the view's own frame)
	const FVector Eye(0, 0, 0);
	auto Deg = [](float Rad) { return FRotator::NormalizeAxis(FMath::RadiansToDegrees(Rad)); };
	TestTrue(TEXT("ahead: up"), FMath::IsNearlyEqual(Deg(ASOHUD::HitRingAngle(Eye, 0.0f, FVector(1000, 0, 0))), -90.0f, 0.5f));
	TestTrue(TEXT("to the right: right"), FMath::IsNearlyEqual(Deg(ASOHUD::HitRingAngle(Eye, 0.0f, FVector(0, 1000, 0))), 0.0f, 0.5f));
	TestTrue(TEXT("behind: down"), FMath::IsNearlyEqual(Deg(ASOHUD::HitRingAngle(Eye, 0.0f, FVector(-1000, 0, 0))), 90.0f, 0.5f));
	TestTrue(TEXT("to the left: left"), FMath::IsNearlyEqual(FMath::Abs(Deg(ASOHUD::HitRingAngle(Eye, 0.0f, FVector(0, -1000, 0)))), 180.0f, 0.5f));
	TestTrue(TEXT("it turns with the view (looking right, ahead of the body is on the left)"),
		FMath::IsNearlyEqual(FMath::Abs(Deg(ASOHUD::HitRingAngle(Eye, 90.0f, FVector(1000, 0, 0)))), 180.0f, 0.5f));

	// a blow tells its player where it came from, and whether the shield took it
	SOTest::FTestWorld W;
	W.AddBox(FVector(-4000, -4000, -100), FVector(4000, 4000, 0));
	USOInventoryComponent* Inv = nullptr;
	ASOCharacter* Player = SpawnPlayer(W, Inv);
	FSOSpawnOptions Options;
	Options.bOnNav = false;
	ASOEnemy* Other = USOSpeciesLibrary::Spawn(W.World, TEXT("remnant"), FVector(0, -900, 0), 90.0f, Options);
	if (!TestNotNull(TEXT("a creature to the player's left"), Other))
	{
		return false;
	}
	if (AController* Brain = Other->GetController())
	{
		Brain->UnPossess();
		Brain->Destroy();
	}
	W.Run(0.2f);
	int32 Count = 0;
	FVector Got = FVector::ZeroVector;
	bool bGotShield = false;
	Player->OnDamagedFrom.AddLambda([&](const FVector& From, bool bShield, float Amount)
	{
		++Count;
		Got = From;
		bGotShield = bShield;
	});
	USOCombatStatics::ApplyDamage(Other, Player, 10.0f, false);
	TestEqual(TEXT("told once"), Count, 1);
	TestTrue(TEXT("from where the creature stands"), Got.Equals(Other->GetActorLocation(), 1.0f));
	TestTrue(TEXT("on the shield"), bGotShield);
	USOCombatStatics::ApplyDamage(Other, Player, Player->GetShield() + 20.0f, false);
	TestTrue(TEXT("through it into the body"), Count == 2 && !bGotShield);
	USOCombatStatics::ApplyDamage(Player, Player, 5.0f, false);
	TestEqual(TEXT("its own blast tells it nothing"), Count, 2);
	return true;
}

#endif
