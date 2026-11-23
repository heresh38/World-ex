// The Altered's senses and guns: a quiet player behind them goes unnoticed, one in front does not, a lit flashlight
// gives you away from any side, running feet are heard, an ambush hits harder, armed creatures shoot; loot lands on
// the ground.

#include "SOTestWorld.h"

#if WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR

#include "Components/CapsuleComponent.h"
#include "Components/SpotLightComponent.h"
#include "EngineUtils.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "SOGunRigComponent.h"
#include "SOAltered.h"
#include "SOCombatStatics.h"
#include "SOEnemyAIController.h"
#include "SOLootActors.h"
#include "SOProjectileSubsystem.h"
#include "SOWeapon.h"

namespace SOTest
{
	template <class T>
	T* SpawnCreature(FTestWorld& W, const FVector& Feet, float Yaw)
	{
		FActorSpawnParameters P;
		P.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
		const float Half = GetDefault<T>()->GetCapsuleComponent()->GetScaledCapsuleHalfHeight();
		T* E = W.World->SpawnActor<T>(T::StaticClass(), Feet + FVector(0, 0, Half + 2.0f), FRotator(0, Yaw, 0), P);
		if (E && !E->GetController())
		{
			E->SpawnDefaultController();
		}
		return E;
	}

	ASOEnemyAIController* Brain(ASOEnemy* E) { return E ? Cast<ASOEnemyAIController>(E->GetController()) : nullptr; }
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOSneakTest, "ShatteredOrbit.AI.SneakAndAmbush", SOTest::Flags)
bool FSOSneakTest::RunTest(const FString& Parameters)
{
	SOTest::FTestWorld W;
	W.AddBox(FVector(-4000, -4000, -100), FVector(4000, 4000, 0));
	// it looks along +X; the player stands 6 m behind it, crouched
	ASORemnant* E = SOTest::SpawnCreature<ASORemnant>(W, FVector(0, 0, 0), 0.0f);
	ASOCharacter* Player = W.SpawnCharacter(FVector(-600, 0, 0));
	if (!TestNotNull(TEXT("remnant"), E))
	{
		return false;
	}
	W.Run(0.3f);
	Player->Crouch();
	W.Run(2.5f);
	ASOEnemyAIController* AI = SOTest::Brain(E);
	TestFalse(TEXT("a crouched player behind it is not noticed"), AI && AI->IsInCombat());
	TestFalse(TEXT("unaware"), E->IsAlert());
	// the opening shot of an ambush lands harder
	const float Hit = USOCombatStatics::ApplyDamage(Player, E, 10.0f, false);
	TestEqual(TEXT("ambush damage"), Hit, 10.0f * E->AmbushDamageScale);
	W.Run(0.3f);
	TestTrue(TEXT("hurt: it knows"), AI && AI->IsInCombat() && E->IsAlert());

	// one standing 15 m in front of it is seen within a couple of seconds
	ASORemnant* E2 = SOTest::SpawnCreature<ASORemnant>(W, FVector(0, 2000, 0), 0.0f);
	ASOCharacter* P2 = W.SpawnCharacter(FVector(1500, 2000, 0));
	W.Run(2.5f);
	TestTrue(TEXT("a player in front is seen"), SOTest::Brain(E2) && SOTest::Brain(E2)->IsInCombat() && SOTest::Brain(E2)->GetTarget() == P2);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOSquadAlertTest, "ShatteredOrbit.AI.AHitAlertsTheSquad", SOTest::Flags)
bool FSOSquadAlertTest::RunTest(const FString& Parameters)
{
	// One of them is shot from far outside anyone's sight (the owner: "if one is sniped then rest don't do anything").
	// The one hit knows; a mate that is looking at it is warned, and so is one standing close by with its back turned;
	// one a long way off looking elsewhere is not. The same when the shot kills outright.
	for (const bool bKill : { false, true })
	{
		SOTest::FTestWorld W;
		W.AddBox(FVector(-16000, -16000, -100), FVector(16000, 16000, 0));
		ASOCharacter* Player = W.SpawnCharacter(FVector(-12000, 0, 0));
		ASORemnant* Hit = SOTest::SpawnCreature<ASORemnant>(W, FVector(0, 0, 0), 0.0f);
		ASORemnant* Watching = SOTest::SpawnCreature<ASORemnant>(W, FVector(2400, 0, 0), 180.0f);     // 24 m off, facing it
		ASORemnant* Beside = SOTest::SpawnCreature<ASORemnant>(W, FVector(0, 800, 0), 90.0f);         // 8 m off, back turned
		ASORemnant* Far = SOTest::SpawnCreature<ASORemnant>(W, FVector(0, -9000, 0), -90.0f);         // 90 m off, back turned
		if (!TestTrue(TEXT("four remnants"), Hit && Watching && Beside && Far))
		{
			return false;
		}
		W.Run(1.0f);
		TestFalse(TEXT("nobody has noticed a player 120 m away"), SOTest::Brain(Hit)->IsInCombat() || SOTest::Brain(Watching)->IsInCombat() || SOTest::Brain(Beside)->IsInCombat());
		// (a sentry with nowhere to walk looks round, a random way at a time: the one watching is turned back onto its
		// mate as the shot lands, or it was sometimes looking elsewhere and the test said nothing about warning)
		const FRotator Facing(0.0f, 180.0f, 0.0f);
		SOTest::Brain(Watching)->ClearFocus(EAIFocusPriority::Gameplay);
		SOTest::Brain(Watching)->SetControlRotation(Facing);
		Watching->SetActorRotation(Facing);
		USOCombatStatics::ApplyDamage(Player, Hit, bKill ? 100000.0f : 5.0f, false);
		W.Run(2.0f);
		const FString Name = bKill ? TEXT("killed outright") : TEXT("hit");
		if (bKill)
		{
			TestTrue(Name + TEXT(": it is dead"), Hit->IsDead());
		}
		else
		{
			TestTrue(Name + TEXT(": the one hit is in the fight"), SOTest::Brain(Hit)->IsInCombat() && SOTest::Brain(Hit)->GetTarget() == Player);
		}
		TestTrue(Name + TEXT(": the one watching it is in the fight"), SOTest::Brain(Watching)->IsInCombat() && SOTest::Brain(Watching)->GetTarget() == Player);
		TestTrue(Name + TEXT(": the one beside it is in the fight"), SOTest::Brain(Beside)->IsInCombat());
		TestFalse(Name + TEXT(": the one 90 m off with its back turned is not"), SOTest::Brain(Far)->IsInCombat());
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOFlashlightTest, "ShatteredOrbit.AI.FlashlightAndFootsteps", SOTest::Flags)
bool FSOFlashlightTest::RunTest(const FString& Parameters)
{
	SOTest::FTestWorld W;
	W.AddBox(FVector(-4000, -4000, -100), FVector(4000, 4000, 0));
	ASORemnant* E = SOTest::SpawnCreature<ASORemnant>(W, FVector(0, 0, 0), 0.0f);
	ASOCharacter* Player = W.SpawnCharacter(FVector(-900, 0, 0));
	W.Run(0.3f);
	Player->SetFlashlight(true);
	TestTrue(TEXT("flashlight on"), Player->IsFlashlightOn() && Player->GetFlashlight()->IsVisible());
	W.Run(3.0f);
	TestTrue(TEXT("a lit light behind it gives you away"), SOTest::Brain(E) && SOTest::Brain(E)->GetAwareness() > 0.5f);
	Player->SetFlashlight(false);
	TestFalse(TEXT("flashlight off"), Player->IsFlashlightOn() || Player->GetFlashlight()->IsVisible());

	// running feet behind another one: heard (it turns suspicious), never seen
	ASORemnant* E2 = SOTest::SpawnCreature<ASORemnant>(W, FVector(0, 2500, 0), 0.0f);
	ASOCharacter* Runner = W.SpawnCharacter(FVector(-700, 2500, 0));
	W.Run(0.3f);
	Runner->GetCharacterMovement()->MaxWalkSpeed = 900.0f;
	W.Run(1.5f, [Runner]() { Runner->AddMovementInput(FVector(0, 1, 0), 1.0f); });
	TestTrue(TEXT("running feet are heard"), SOTest::Brain(E2) && SOTest::Brain(E2)->GetAwareness() > 0.05f);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOArmedTest, "ShatteredOrbit.AI.ArmedAlteredShoot", SOTest::Flags)
bool FSOArmedTest::RunTest(const FString& Parameters)
{
	SOTest::FTestWorld W;
	W.AddBox(FVector(-4000, -4000, -100), FVector(4000, 4000, 0));
	ASOCharacter* Player = W.SpawnCharacter(FVector(0, 0, 0));
	ASOArmedStalker* S = SOTest::SpawnCreature<ASOArmedStalker>(W, FVector(1300, 0, 0), 180.0f);
	if (!TestNotNull(TEXT("armed stalker"), S))
	{
		return false;
	}
	W.Run(0.3f);
	if (!TestNotNull(TEXT("it carries a gun (DA_LootTables imported)"), S->GetWeapon()))
	{
		return false;
	}
	TestTrue(TEXT("the gun is held (attached to its hold)"), S->GetWeapon()->GetRig() && S->GetWeapon()->GetRig()->GetAttachParent() != nullptr);
	const float Before = Player->GetHealth() + Player->GetShield();
	W.Run(6.0f);
	TestTrue(FString::Printf(TEXT("it shoots (%d rounds)"), S->GetShotsFired()), S->GetShotsFired() > 0);
	TestTrue(TEXT("its rounds hurt"), Player->GetHealth() + Player->GetShield() < Before);
	TestTrue(TEXT("a creature's round hits softer than the same gun in a player's hands"), S->GetOutgoingDamageScale() < 1.0f);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSONoShotsThroughWallsTest, "ShatteredOrbit.AI.NoShotsThroughWalls", SOTest::Flags)
bool FSONoShotsThroughWallsTest::RunTest(const FString& Parameters)
{
	// A hunter knows where its prey is. With a wall between them it neither levels its gun at the wall nor fires
	// through it; the moment the wall is gone it shoots.
	SOTest::FTestWorld W;
	W.AddBox(FVector(-4000, -4000, -100), FVector(4000, 4000, 0));
	AActor* Wall = W.AddBox(FVector(620, -1500, 0), FVector(660, 1500, 500));
	ASOCharacter* Player = W.SpawnCharacter(FVector(0, 0, 0));
	ASOArmedStalker* S = SOTest::SpawnCreature<ASOArmedStalker>(W, FVector(1300, 0, 0), 180.0f);
	ASOEnemyAIController* AI = S ? Cast<ASOEnemyAIController>(S->GetController()) : nullptr;
	if (!TestNotNull(TEXT("an armed stalker with a brain"), AI))
	{
		return false;
	}
	AI->bHunter = true;
	const float Before = Player->GetHealth() + Player->GetShield();
	bool bAimed = false;
	W.Run(5.0f, [&] { bAimed |= AI->IsInCombat() && S->GetAimTarget() != nullptr && W.World->GetTimeSeconds() > 2.5f; });
	TestTrue(TEXT("it knows the player is there"), AI->IsInCombat());
	TestFalse(TEXT("there is no line of fire through the wall"), S->HasLineOfFire(Player));
	TestEqual(TEXT("it fires nothing through the wall"), S->GetShotsFired(), 0);
	TestFalse(TEXT("it does not stand aiming at the wall"), bAimed);
	TestEqual(TEXT("the player is untouched"), Player->GetHealth() + Player->GetShield(), Before, 0.01f);
	Wall->Destroy();
	W.Run(6.0f);
	TestTrue(FString::Printf(TEXT("with the wall gone it shoots (%d rounds)"), S->GetShotsFired()), S->GetShotsFired() > 0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOLootGroundTest, "ShatteredOrbit.Loot.DropsOnTheGround", SOTest::Flags)
bool FSOLootGroundTest::RunTest(const FString& Parameters)
{
	SOTest::FTestWorld W;
	W.AddBox(FVector(-2000, -2000, -100), FVector(2000, 2000, 0));
	USOLootSubsystem* Loot = W.World->GetSubsystem<USOLootSubsystem>();
	if (!TestNotNull(TEXT("loot subsystem"), Loot))
	{
		return false;
	}
	// a creature killed high up (on a ledge that is not there, or mid-jump): its drop still lands on the floor
	ASOLootPickup* Core = Loot->SpawnPickup(FVector(0, 0, 900.0f), ESOPickupKind::Core, 2, 10);
	ASOLootPickup* Ammo = Loot->SpawnPickup(FVector(200, 0, 90.0f), ESOPickupKind::Ammo, 0, 10);
	TestTrue(TEXT("a core lands on the floor"), Core && FMath::Abs(Core->GetActorLocation().Z) < 5.0f);
	TestTrue(TEXT("ammo lands on the floor"), Ammo && FMath::Abs(Ammo->GetActorLocation().Z) < 5.0f);
	return true;
}

// The owner, 2026-11-22: "if i shoot beside them they do nothing, they need to listen to sound, see bullets and react".
// One far beyond the sound of the gun (70 m) and out of sight: a round cracks past it three metres off. It is in the
// fight at once, against the one who fired, and knows only roughly where they are (the way the round came).
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOShotsNearbyTest, "ShatteredOrbit.AI.ShotsNearbyAreNoticed", SOTest::Flags)
bool FSOShotsNearbyTest::RunTest(const FString& Parameters)
{
	SOTest::FTestWorld W;
	W.AddBox(FVector(-16000, -16000, -100), FVector(16000, 16000, 0));
	ASOCharacter* Player = W.SpawnCharacter(FVector(-7000, 0, 0));
	ASORemnant* E = SOTest::SpawnCreature<ASORemnant>(W, FVector(0, 0, 0), 90.0f);     // looking away, across the line
	ASOEnemyAIController* AI = SOTest::Brain(E);
	USOProjectileSubsystem* Rounds = W.World->GetSubsystem<USOProjectileSubsystem>();
	if (!TestNotNull(TEXT("a remnant with a brain"), AI) || !TestNotNull(TEXT("rounds"), Rounds))
	{
		return false;
	}
	W.Run(1.0f);
	TestFalse(TEXT("nothing yet: the player is 70 m off, out of sight and silent"), AI->IsInCombat());
	FSOProjectile Round;
	Round.Origin = Round.Position = Player->GetActorLocation() + FVector(0, 0, 60.0f);
	const FVector Beside = E->GetActorLocation() + FVector(0, 300.0f, 0);
	Round.Velocity = (Beside - Round.Origin).GetSafeNormal() * 80000.0f;
	Round.Gravity = 0.0f;
	Round.Damage = 10.0f;
	Round.Life = 1.5f;
	Round.Instigator = Player;
	Rounds->Fire(Round);
	W.Run(1.2f);
	TestTrue(TEXT("a round cracking past three metres off puts it in the fight"), AI->IsInCombat());
	TestTrue(TEXT("against the one who fired"), AI->GetTarget() == Player);
	const float Off = static_cast<float>(FVector::Dist2D(AI->GetLastKnownLocation(), Player->GetActorLocation()));
	TestTrue(FString::Printf(TEXT("it knows roughly where from (%.0f cm off the shooter)"), Off), Off < 1000.0f);
	TestTrue(TEXT("it knows it is being shot at"), AI->SinceShotAt() < 2.0f);
	return true;
}

// Shot from fifty metres by someone it cannot see, one that holds ground does not run at the shooter (the owner: "they
// get shot by the player then just ran straight to the player no matter how far the player is like they are mindless
// zombies"): it knows the way the round came and roughly how far, and keeps to its ground.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOHoldsGroundTest, "ShatteredOrbit.AI.HoldsGroundWhenShotFromAfar", SOTest::Flags)
bool FSOHoldsGroundTest::RunTest(const FString& Parameters)
{
	SOTest::FTestWorld W;
	W.AddBox(FVector(-16000, -16000, -100), FVector(16000, 16000, 0));
	ASOCharacter* Player = W.SpawnCharacter(FVector(-5000, 0, 0));
	ASORemnant* E = SOTest::SpawnCreature<ASORemnant>(W, FVector(0, 0, 0), 0.0f);      // its back to the player
	ASOEnemyAIController* AI = SOTest::Brain(E);
	if (!TestNotNull(TEXT("a remnant with a brain"), AI))
	{
		return false;
	}
	AI->SetFlanker(false);
	W.Run(0.5f);
	const FVector Start = E->GetActorLocation();
	USOCombatStatics::ApplyDamage(Player, E, 5.0f, false);
	W.Run(0.5f);
	TestTrue(TEXT("hit: it is in the fight"), AI->IsInCombat());
	const float Off = static_cast<float>(FVector::Dist2D(AI->GetLastKnownLocation(), Player->GetActorLocation()));
	TestTrue(FString::Printf(TEXT("it knows roughly where the shot came from, not the place (%.0f cm off)"), Off), Off > 50.0f && Off < 1000.0f);
	W.Run(10.0f);
	const float Closed = static_cast<float>(FVector::Dist2D(Start, Player->GetActorLocation()) - FVector::Dist2D(E->GetActorLocation(), Player->GetActorLocation()));
	TestTrue(FString::Printf(TEXT("it keeps to its ground (closed %.0f cm of 50 m in ten seconds)"), Closed), Closed < AI->HoldRadius + 150.0f);
	TestTrue(FString::Printf(TEXT("it is within its ground (%.0f cm from its post)"), FVector::Dist2D(E->GetActorLocation(), AI->GetHome())),
		FVector::Dist2D(E->GetActorLocation(), AI->GetHome()) < AI->HoldRadius + 150.0f);
	return true;
}

// The owner: zoomed in on one "they just move out of the way fast ... shooting needs to be a bit more easier and more
// fun". A gun levelled at a creature in the open no longer makes it jump aside: in view of the player, aimed at for six
// seconds, it fights from where it stands.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSONoDodgeTest, "ShatteredOrbit.AI.AimingDoesNotMakeThemDodge", SOTest::Flags)
bool FSONoDodgeTest::RunTest(const FString& Parameters)
{
	SOTest::FTestWorld W;
	W.AddBox(FVector(-8000, -8000, -100), FVector(8000, 8000, 0));
	ASOCharacter* Player = W.SpawnCharacter(FVector(0, 0, 0));
	ASOArmedStalker* E = SOTest::SpawnCreature<ASOArmedStalker>(W, FVector(1800, 0, 0), 180.0f);
	ASOEnemyAIController* AI = SOTest::Brain(E);
	if (!TestNotNull(TEXT("an armed stalker with a brain"), AI))
	{
		return false;
	}
	if (AController* C = Player->GetController())
	{
		C->SetControlRotation((E->GetActorLocation() - Player->GetActorLocation()).Rotation());
	}
	W.Run(1.5f);
	TestTrue(TEXT("it has seen the player"), AI->IsInCombat());
	const FVector Start = E->GetActorLocation();
	W.Run(6.0f, [&] {
		if (AController* C = Player->GetController())
		{
			C->SetControlRotation((E->GetActorLocation() - Player->GetActorLocation()).Rotation());
		}
	});
	TestEqual(TEXT("aimed at, it never jumped aside"), AI->GetDodges(), 0);
	TestTrue(FString::Printf(TEXT("it fought from about where it stood (moved %.0f cm)"), FVector::Dist2D(Start, E->GetActorLocation())),
		FVector::Dist2D(Start, E->GetActorLocation()) < 400.0f);
	TestTrue(FString::Printf(TEXT("and it shot back (%d rounds)"), E->GetShotsFired()), E->GetShotsFired() > 0);
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
