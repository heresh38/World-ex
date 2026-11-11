// The Altered's senses and guns: a quiet player behind them goes unnoticed, one in front does not, a lit flashlight
// gives you away from any side, running feet are heard, an ambush hits harder, armed creatures shoot; loot lands on
// the ground.

#include "SOTestWorld.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "Components/CapsuleComponent.h"
#include "Components/SpotLightComponent.h"
#include "EngineUtils.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "SOGunRigComponent.h"
#include "SOAltered.h"
#include "SOCombatStatics.h"
#include "SOEnemyAIController.h"
#include "SOLootActors.h"
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
	TestTrue(TEXT("the gun is held (attached to its hold)"), S->GetWeapon()->GetThirdPersonRig() && S->GetWeapon()->GetThirdPersonRig()->GetAttachParent() != nullptr);
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

#endif // WITH_DEV_AUTOMATION_TESTS
