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
#include "SOInventoryComponent.h"
#include "Components/StaticMeshComponent.h"

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

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOMeleeBladeTest, "ShatteredOrbit.Melee.TheBladeIsOwnedAndHeld", SOTest::Flags)
bool FSOMeleeBladeTest::RunTest(const FString& Parameters)
{
	const USOMeleeTable* Table = USOMeleeTable::Get();
	const FSOMeleeStyle* Blade = Table ? Table->Find(TEXT("skr_blade")) : nullptr;
	if (!TestNotNull(TEXT("the blade's style"), Blade) || !TestFalse(TEXT("the blade has its mesh (SO_IMPORT_ONLY=melee)"), Blade->Mesh.IsNull()))
	{
		return false;
	}
	TestEqual(TEXT("the Sarketh cache gives it"), Blade->SetId, FName(TEXT("sarketh")));
	SOTest::FTestWorld W;
	W.AddBox(FVector(-3000, -3000, -100), FVector(3000, 3000, 0));
	APlayerController* PC = W.World->SpawnActor<APlayerController>();
	PC->SetAsLocalPlayerController();
	ASOPlayerState* PS = W.World->SpawnActor<ASOPlayerState>();
	PC->PlayerState = PS;
	ASOCharacter* Player = W.SpawnCharacter(FVector(0, 0, 0));
	PC->Possess(Player);
	W.Run(0.2f);
	USOInventoryComponent* Inventory = Player->GetInventory();
	if (!TestNotNull(TEXT("an inventory"), Inventory))
	{
		return false;
	}

	// without the blade, key 4 is the fists and back
	Player->SetMeleeStyle(TEXT("skr_blade"));
	TestEqual(TEXT("a blade not owned cannot be taken up"), Player->GetMeleeStyleId(), FName(TEXT("fists")));
	Player->HandleFists();
	TestTrue(TEXT("the fists"), Player->IsFists() && Player->GetMeleeStyleId() == TEXT("fists"));
	Player->HandleFists();
	TestFalse(TEXT("and back to the gun"), Player->IsFists());

	// owned: it goes into the empty melee slot, and key 4 brings up what is in the slot
	Inventory->AddBlade(TEXT("skr_blade"));
	TestTrue(TEXT("owned"), Inventory->HasBlade(TEXT("skr_blade")));
	TestEqual(TEXT("the first blade goes in the melee slot"), Inventory->GetMeleeSlot(), FName(TEXT("skr_blade")));
	Player->HandleFists();
	TestTrue(TEXT("key 4: the blade"), Player->IsFists() && Player->GetMeleeStyleId() == TEXT("skr_blade"));
	W.Run(0.2f);
	const UStaticMeshComponent* Held = Player->GetHeldBlade();
	TestTrue(TEXT("the blade is in the body's hand"), Held && Held->IsVisible() && Held->GetStaticMesh());
	if (Held && !SOTest::PlayerBodyMissing(*this))
	{
		const FVector Hand = Player->GetMesh()->GetBoneLocation(TEXT("hand_R"));
		const FVector Grip = Held->GetComponentTransform().TransformPosition(FVector(0.0f, -6.0f, 0.0f));
		TestTrue(FString::Printf(TEXT("its handle is in the fist (%.1f cm from the wrist)"), FVector::Dist(Grip, Hand)), FVector::Dist(Grip, Hand) < 12.0f);
	}
	const float Light = Table->Find(TEXT("skr_blade"))->Light[0].Damage;
	TestTrue(TEXT("its blows are the blade's"), Light > Table->Find(TEXT("fists"))->Light[0].Damage);
	Player->HandleFists();
	TestFalse(TEXT("key 4 again: the gun"), Player->IsFists());
	W.Run(0.1f);
	TestFalse(TEXT("the blade is put away"), Held && Held->IsVisible());
	// the fists in the slot: key 4 brings them up
	Inventory->ServerSetMeleeSlot(TEXT("fists"));
	TestTrue(TEXT("the slot is the fists"), Inventory->GetMeleeSlot().IsNone());
	Player->HandleFists();
	TestTrue(TEXT("key 4: the fists"), Player->IsFists() && Player->GetMeleeStyleId() == TEXT("fists"));
	return true;
}

// The fighter's moves: the stance picks the move, a finisher ends a chain, a launcher throws up, the guard turns blows
// and a guard raised just as a blow comes is a parry (the attacker reels, the next blow is a counter).
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOMeleeMovesTest, "ShatteredOrbit.Melee.SpecialsBlockAndParry", SOTest::Flags)
bool FSOMeleeMovesTest::RunTest(const FString& Parameters)
{
	const USOMeleeTable* Table = USOMeleeTable::Get();
	const FSOMeleeStyle* Fists = Table ? Table->Find(TEXT("fists")) : nullptr;
	if (!TestNotNull(TEXT("the fists' style"), Fists))
	{
		return false;
	}
	for (const int32 Move : { SOMeleeMove::Finisher, SOMeleeMove::Rush, SOMeleeMove::Sweep, SOMeleeMove::Riser, SOMeleeMove::Air })
	{
		TestNotNull(*FString::Printf(TEXT("the fists have move %d"), Move), USOMeleeTable::Blow(*Fists, Move));
	}
	TestTrue(TEXT("the launcher throws up"), Fists->Riser.Launch > 0.0f && Fists->Finisher.Launch > 0.0f);
	TestTrue(TEXT("the slam is a ring"), Fists->Air.Shock > 0.0f);
	TestFalse(TEXT("there is a guard"), Fists->BlockClip.IsNone());

	SOTest::FTestWorld W;
	W.AddBox(FVector(-3000, -3000, -100), FVector(3000, 3000, 0));
	APlayerController* PC = W.World->SpawnActor<APlayerController>();
	PC->SetAsLocalPlayerController();
	PC->PlayerState = W.World->SpawnActor<ASOPlayerState>();
	ASOCharacter* Player = W.SpawnCharacter(FVector(0, 0, 0));
	PC->Possess(Player);
	PC->SetControlRotation(FRotator::ZeroRotator);
	ASOEnemy* Target = SOTest::SpawnStalker(W, FVector(120, 0, 0), FRotator(0, 180, 0));
	Target->SetAlert(true);
	Target->DetachFromControllerPendingDestroy();
	Target->GetCharacterMovement()->bRunPhysicsWithNoController = true;   // (no brain here, but it must fly when launched)
	W.Run(0.2f);
	Player->SetFists(true);
	W.Run(0.1f);

	// light, light, heavy: the finisher, and it throws the target up
	Player->MeleeStrike(false);
	W.Run(Fists->Light[0].Recover + 0.02f);
	Player->MeleeStrike(false);
	W.Run(Fists->Light[1].Recover + 0.02f);
	const float TargetDist = FVector::Dist2D(Target->GetActorLocation(), Player->GetActorLocation());
	TestTrue(FString::Printf(TEXT("the light blows keep the target in reach of the chain (%.0f cm)"), TargetDist), TargetDist < Fists->Finisher.Range);
	Player->MeleeStrike(true);
	TestEqual(TEXT("light, light, heavy is the finisher"), Player->GetMeleeLastBlow(), SOMeleeMove::Finisher);
	W.Run(Fists->Finisher.HitTime + 0.05f);
	TestTrue(TEXT("the finisher launched it"), Target->IsDead() || Target->GetVelocity().Z > 100.0f || Target->GetCharacterMovement()->IsFalling());
	TestTrue(TEXT("the blows counted as a combo"), Player->GetComboHits() >= 2);
	W.Run(1.5f);

	// crouched: light is the sweep, heavy the launcher
	Player->Crouch();
	W.Run(0.3f);
	Player->MeleeStrike(false);
	TestEqual(TEXT("crouched, light: the sweep"), Player->GetMeleeLastBlow(), SOMeleeMove::Sweep);
	W.Run(Fists->Sweep.Recover + 0.3f);
	Player->MeleeStrike(true);
	TestEqual(TEXT("crouched, heavy: the launcher"), Player->GetMeleeLastBlow(), SOMeleeMove::Riser);
	Player->UnCrouch();
	W.Run(Fists->Riser.Recover + 0.5f);

	// the guard: a blow from the front mostly turned; raised just as it comes, nothing gets through and the attacker reels
	ASOEnemy* Attacker = SOTest::SpawnStalker(W, FVector(150, 60, 0), FRotator(0, 200, 0));
	Attacker->SetAlert(true);
	Attacker->DetachFromControllerPendingDestroy();
	W.Run(Fists->ParryWindow + 0.3f);
	Player->SetBlocking(true);
	TestTrue(TEXT("guarding"), Player->IsBlocking());
	W.Run(Fists->ParryWindow + 0.1f);
	float Before = Player->GetHealth() + Player->GetShield();
	USOCombatStatics::ApplyDamage(Attacker, Player, 40.0f, false);
	const float Took = Before - (Player->GetHealth() + Player->GetShield());
	TestTrue(FString::Printf(TEXT("the guard turned most of it (%.1f of 40)"), Took), Took > 0.0f && Took <= 40.0f * Fists->BlockScale + 0.5f);
	Player->SetBlocking(false);
	W.Run(0.2f);
	Player->SetBlocking(true);
	Before = Player->GetHealth() + Player->GetShield();
	USOCombatStatics::ApplyDamage(Attacker, Player, 40.0f, false);
	TestEqual(TEXT("a parry: nothing gets through"), Player->GetHealth() + Player->GetShield(), Before, 0.01f);
	TestTrue(TEXT("and the attacker reels"), Attacker->HasStatus(SOTags::Status_Stagger));
	Player->SetBlocking(false);
	TestFalse(TEXT("no blows while guarding"), false);
	return true;
}

#endif
