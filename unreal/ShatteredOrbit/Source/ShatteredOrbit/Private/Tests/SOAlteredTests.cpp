// The Altered (the operation's enemies): their content loads, the Veilborn's bolts hurt, the Bulwark's shield turns
// shots from the front, the Colossus's shield holds until its conduits fall and then it staggers.

#include "SOTestWorld.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "EngineUtils.h"
#include "SOAltered.h"
#include "SOCombatStatics.h"
#include "SOEnemyAIController.h"

namespace SOTest
{
	template <class T>
	T* SpawnAltered(FTestWorld& W, const FVector& Feet, float Yaw = 180.0f)
	{
		FActorSpawnParameters P;
		P.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
		const float Half = GetDefault<T>()->GetCapsuleComponent()->GetScaledCapsuleHalfHeight();
		T* E = W.World->SpawnActor<T>(T::StaticClass(), Feet + FVector(0, 0, Half + 2.0f), FRotator(0, Yaw, 0), P);
		if (E && !E->GetController())
		{
			E->SpawnDefaultController();
		}
		if (ASOEnemyAIController* AI = E ? Cast<ASOEnemyAIController>(E->GetController()) : nullptr)
		{
			AI->bHunter = true;
		}
		return E;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOAlteredContentTest, "ShatteredOrbit.Altered.Content", SOTest::Flags)
bool FSOAlteredContentTest::RunTest(const FString& Parameters)
{
	SOTest::FTestWorld W;
	W.AddBox(FVector(-2000, -2000, -100), FVector(2000, 2000, 0));
	struct FCase { UClass* Class; TArray<FName> Actions; };
	const FCase Cases[] = {
		{ ASORemnant::StaticClass(), {} },
		{ ASOVeilborn::StaticClass(), { TEXT("Cast"), TEXT("Blink") } },
		{ ASOBulwark::StaticClass(), { TEXT("Slam") } },
		{ ASOColossus::StaticClass(), { TEXT("Slam"), TEXT("Sweep"), TEXT("Barrage"), TEXT("Shield") } },
	};
	float X = 0.0f;
	for (const FCase& C : Cases)
	{
		FActorSpawnParameters P;
		P.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
		ASOEnemy* E = W.World->SpawnActor<ASOEnemy>(C.Class, FVector(X, 0, 500.0f), FRotator::ZeroRotator, P);
		X += 600.0f;
		if (!TestNotNull(*FString::Printf(TEXT("%s spawns"), *C.Class->GetName()), E))
		{
			continue;
		}
		TestNotNull(*FString::Printf(TEXT("%s has its body (import altered)"), *C.Class->GetName()), E->GetMesh()->GetSkeletalMeshAsset());
		for (const FName& A : C.Actions)
		{
			TestTrue(*FString::Printf(TEXT("%s clip %s"), *C.Class->GetName(), *A.ToString()), E->GetActionLength(A) > 0.0f);
		}
		TestFalse(*FString::Printf(TEXT("%s has a name"), *C.Class->GetName()), E->DisplayName.IsEmpty());
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOVeilbornTest, "ShatteredOrbit.Altered.VeilbornBolts", SOTest::Flags)
bool FSOVeilbornTest::RunTest(const FString& Parameters)
{
	SOTest::FTestWorld W;
	W.AddBox(FVector(-3000, -3000, -100), FVector(3000, 3000, 0));
	ASOCharacter* Player = W.SpawnCharacter(FVector(0, 0, 0));
	ASOVeilborn* V = SOTest::SpawnAltered<ASOVeilborn>(W, FVector(1500, 0, 0));
	if (!TestNotNull(TEXT("veilborn"), V))
	{
		return false;
	}
	const float Before = Player->GetHealth() + Player->GetShield();
	W.Run(6.0f);
	TestTrue(TEXT("it casts from range"), V->GetBoltsFired() >= 1);
	TestTrue(TEXT("its bolts hurt"), Player->GetHealth() + Player->GetShield() < Before);
	TestTrue(TEXT("it keeps its distance"), V->DistanceTo(Player) > 600.0f);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOBulwarkTest, "ShatteredOrbit.Altered.BulwarkShield", SOTest::Flags)
bool FSOBulwarkTest::RunTest(const FString& Parameters)
{
	SOTest::FTestWorld W;
	W.AddBox(FVector(-3000, -3000, -100), FVector(3000, 3000, 0));
	ASOCharacter* Front = W.SpawnCharacter(FVector(-800, 0, 0));
	ASOCharacter* Back = W.SpawnCharacter(FVector(800, 0, 0));
	ASOBulwark* B = SOTest::SpawnAltered<ASOBulwark>(W, FVector(0, 0, 0), 180.0f); // facing -X: toward Front
	if (!TestNotNull(TEXT("bulwark"), B))
	{
		return false;
	}
	B->GetController()->SetActorTickEnabled(false);
	const float FromFront = USOCombatStatics::ApplyDamage(Front, B, 100.0f, false);
	const float FromBehind = USOCombatStatics::ApplyDamage(Back, B, 100.0f, false);
	TestTrue(TEXT("the shield turns most of a shot from the front"), FromFront <= 30.0f);
	TestEqual(TEXT("a shot from behind lands in full"), FromBehind, 100.0f);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOColossusTest, "ShatteredOrbit.Altered.ColossusConduits", SOTest::Flags)
bool FSOColossusTest::RunTest(const FString& Parameters)
{
	SOTest::FTestWorld W;
	W.AddBox(FVector(-6000, -6000, -100), FVector(6000, 6000, 0));
	ASOCharacter* Player = W.SpawnCharacter(FVector(-3000, 0, 0));
	ASOColossus* C = SOTest::SpawnAltered<ASOColossus>(W, FVector(0, 0, 0));
	if (!TestNotNull(TEXT("colossus"), C))
	{
		return false;
	}
	W.Run(0.5f);
	// down to two thirds: it kneels behind its shield and the conduits rise
	USOCombatStatics::ApplyDamage(Player, C, C->GetMaxHealth() * 0.36f, false);
	W.Run(0.5f);
	TestTrue(TEXT("shielded at two thirds"), C->IsShielded() && C->IsImmune());
	TestEqual(TEXT("three conduits"), C->GetConduits().Num(), 3);
	TestEqual(TEXT("no damage through the shield"), USOCombatStatics::ApplyDamage(Player, C, 500.0f, false), 0.0f);
	for (const TWeakObjectPtr<ASOConduit>& K : C->GetConduits())
	{
		if (K.IsValid())
		{
			USOCombatStatics::ApplyDamage(Player, K.Get(), 5000.0f, false);
		}
	}
	W.Run(0.5f);
	TestFalse(TEXT("the shield breaks with its conduits"), C->IsShielded() || C->IsImmune());
	TestTrue(TEXT("it staggers"), C->IsStaggered());
	const float Hurt = USOCombatStatics::ApplyDamage(Player, C, 100.0f, false);
	TestEqual(TEXT("a staggered colossus takes half again"), Hurt, 150.0f);
	// a kill takes the conduits with it
	C->StartShield();
	W.Run(0.2f);
	C->Die(Player);
	W.Run(0.2f);
	int32 Standing = 0;
	for (TActorIterator<ASOConduit> It(W.World); It; ++It)
	{
		Standing += !It->IsDead();
	}
	TestEqual(TEXT("its conduits fall with it"), Standing, 0);
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
