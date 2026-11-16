// Hand to hand (the owner, 2026-11-15): the guns on the back, fire the light chain, aim the heavy blow; numbers from
// Data/game_data.json "melee" (DA_Melee). Single machine (the server's side).

#include "SOTestWorld.h"

#if WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR

#include "GameFramework/PlayerController.h"
#include "SOCombatStatics.h"
#include "SOCombatTypes.h"
#include "SOEnemy.h"
#include "SOLocomotionAnimInstance.h"
#include "SOMelee.h"
#include "SOPlayerState.h"

namespace SOTest
{
	ASOEnemy* SpawnStalker(FTestWorld& W, const FVector& Feet, const FRotator& Rotation);
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOMeleeTableTest, "ShatteredOrbit.Melee.StylesAreData", SOTest::Flags)
bool FSOMeleeTableTest::RunTest(const FString& Parameters)
{
	const USOMeleeTable* Table = USOMeleeTable::Get();
	if (!TestNotNull(TEXT("DA_Melee is imported (SO_IMPORT_ONLY=melee)"), Table))
	{
		return false;
	}
	for (const TCHAR* Id : { TEXT("fists"), TEXT("skr_blade") })
	{
		const FSOMeleeStyle* Style = Table->Find(Id);
		if (!TestNotNull(FString::Printf(TEXT("style %s"), Id), Style))
		{
			continue;
		}
		TestTrue(FString::Printf(TEXT("%s: a guard and a chain of light blows"), Id), !Style->Guard.IsNone() && Style->Light.Num() >= 2);
		float LightMost = 0.0f;
		for (const FSOMeleeBlow& B : Style->Light)
		{
			TestTrue(FString::Printf(TEXT("%s %s: lands inside its own recovery"), Id, *B.Clip.ToString()), B.HitTime > 0.0f && B.HitTime < B.Recover);
			LightMost = FMath::Max(LightMost, B.Damage);
		}
		TestTrue(FString::Printf(TEXT("%s: the heavy blow is slower and harder than any light one"), Id),
			Style->Heavy.Damage > LightMost && Style->Heavy.HitTime > Style->Light[0].HitTime && Style->Heavy.Stagger > 0.0f);
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOMeleeFistsTest, "ShatteredOrbit.Melee.FistsLightChainAndHeavy", SOTest::Flags)
bool FSOMeleeFistsTest::RunTest(const FString& Parameters)
{
	const USOMeleeTable* Table = USOMeleeTable::Get();
	const FSOMeleeStyle* Fists = Table ? Table->Find(TEXT("fists")) : nullptr;
	if (!TestNotNull(TEXT("the fists' style"), Fists))
	{
		return false;
	}
	SOTest::FTestWorld W;
	W.AddBox(FVector(-3000, -3000, -100), FVector(3000, 3000, 0));
	APlayerController* PC = W.World->SpawnActor<APlayerController>();
	PC->SetAsLocalPlayerController();
	PC->PlayerState = W.World->SpawnActor<ASOPlayerState>();
	ASOCharacter* Player = W.SpawnCharacter(FVector(0, 0, 0));
	PC->Possess(Player);
	PC->SetControlRotation(FRotator::ZeroRotator);
	ASOEnemy* Target = SOTest::SpawnStalker(W, FVector(130, 0, 0), FRotator(0, 180, 0));
	ASOEnemy* Behind = SOTest::SpawnStalker(W, FVector(-130, 0, 0), FRotator::ZeroRotator);
	for (ASOEnemy* E : { Target, Behind })
	{
		E->SetAlert(true);
		E->DetachFromControllerPendingDestroy();                 // (no brain: this is about the blows, not the dodge)
	}
	W.Run(0.2f);

	// out come the fists, away go the guns; fire while they are up is a blow, never a shot
	TestFalse(TEXT("not fighting hand to hand at first"), Player->IsFists());
	Player->MeleeStrike(false);
	TestEqual(TEXT("no blow without the fists up"), Player->GetMeleeLastBlow(), -1);
	Player->SetFists(true);
	W.Run(0.1f);
	TestTrue(TEXT("fists up"), Player->IsFists());
	TestTrue(TEXT("the hands are free: the guns are on the back"), Player->IsWeaponStowed());

	// the light chain: jab, cross, hook, each pressed as the last one frees the hands
	const float Full = Target->GetHealth();
	Player->MeleeStrike(false);
	TestEqual(TEXT("the first light blow"), Player->GetMeleeLastBlow(), 0);
	const double First = Player->GetMeleeLastStart();
	Player->MeleeStrike(false);
	TestEqual(TEXT("pressed again at once: too early, nothing new"), Player->GetMeleeLastStart(), First);
	W.Run(Fists->Light[0].HitTime + 0.05f);
	TestTrue(FString::Printf(TEXT("the jab landed (%.0f of %.0f)"), Target->GetHealth(), Full), Target->GetHealth() < Full - 1.0f);
	TestEqual(TEXT("the one behind is not touched"), Behind->GetHealth(), Behind->GetMaxHealth());
	W.Run(FMath::Max(Fists->Light[0].Recover - Fists->Light[0].HitTime, 0.0f));
	Player->MeleeStrike(false);
	TestEqual(TEXT("within the grace: the chain goes on (the cross)"), Player->GetMeleeLastBlow(), 1);
	W.Run(Fists->Light[1].Recover + 0.02f);
	Player->MeleeStrike(false);
	TestEqual(TEXT("and on (the hook)"), Player->GetMeleeLastBlow(), 2);
	W.Run(Fists->Light[2].Recover + Fists->ChainGrace + 0.3f);
	const float AfterChain = Target->GetHealth();
	TestTrue(TEXT("three blows landed"), AfterChain < Full - (Fists->Light[0].Damage + Fists->Light[1].Damage) * 0.8f || Target->IsDead());
	Player->MeleeStrike(false);
	TestEqual(TEXT("after a pause the chain begins again"), Player->GetMeleeLastBlow(), 0);

	// the heavy blow: wound up, staggers what it hits
	ASOEnemy* Fresh = SOTest::SpawnStalker(W, FVector(120, 40, 0), FRotator(0, 180, 0));
	Fresh->SetAlert(true);
	Fresh->DetachFromControllerPendingDestroy();
	Target->Destroy();
	W.Run(Fists->Light[0].Recover + 0.1f);
	const float FreshFull = Fresh->GetHealth();
	Player->MeleeStrike(true);
	TestEqual(TEXT("aim is the heavy blow"), Player->GetMeleeLastBlow(), -1);
	W.Run(Fists->Heavy.HitTime * 0.5f);
	TestEqual(TEXT("nothing lands during the wind-up"), Fresh->GetHealth(), FreshFull);
	W.Run(Fists->Heavy.HitTime * 0.5f + 0.05f);
	TestTrue(FString::Printf(TEXT("the heavy blow landed hard (%.0f of %.0f)"), Fresh->GetHealth(), FreshFull),
		Fresh->IsDead() || Fresh->GetHealth() < FreshFull - Fists->Light[2].Damage);
	TestTrue(TEXT("and staggered it"), Fresh->IsDead() || Fresh->HasStatus(SOTags::Status_Stagger));

	// the guard is on the body while the fists are up
	if (!SOTest::PlayerBodyMissing(*this))
	{
		const USOLocomotionAnimInstance* Anim = Cast<USOLocomotionAnimInstance>(Player->GetMesh()->GetAnimInstance());
		TestTrue(TEXT("the guard plays on the body"), Anim && Anim->MeleeGuard && Anim->GetMeleeWeight() > 0.5f);
	}

	// a gun's key (or the fists key again) puts them down and the gun comes back
	Player->SetFists(false);
	W.Run(0.1f);
	TestFalse(TEXT("fists down"), Player->IsFists());
	TestFalse(TEXT("the hands are back on the gun"), Player->IsWeaponStowed());
	return true;
}

#endif
