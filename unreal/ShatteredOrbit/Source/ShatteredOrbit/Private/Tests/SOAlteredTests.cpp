// The Altered (the operation's enemies): their content loads, the Veilborn's bolts hurt, the Bulwark's shield turns
// shots from the front, the Colossus's shield holds until its conduits fall and then it staggers.

#include "SOTestWorld.h"

#if WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR

#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "EngineUtils.h"
#include "Rendering/SkeletalMeshRenderData.h"
#include "SOAltered.h"
#include "SOCombatStatics.h"
#include "SOCombatTypes.h"
#include "SOProjectileSubsystem.h"
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
	B->SetAlert(true); // the shield alone (no ambush bonus)
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
	{
		const ASOEnemyAIController* AI = Cast<ASOEnemyAIController>(C->GetController());
		int32 Alive = 0;
		for (const TWeakObjectPtr<ASOConduit>& K : C->GetConduits()) { Alive += K.IsValid() && !K->IsDead(); }
		AddInfo(FString::Printf(TEXT("ai %d combat %d state %d target %d conduits %d alive %d"), AI != nullptr, AI && AI->IsInCombat(),
			AI ? (int32)AI->GetState() : -1, AI && AI->GetTarget() != nullptr, C->GetConduits().Num(), Alive));
	}
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


IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOBodiesFollowTest, "ShatteredOrbit.Altered.BodiesFollowTheBody", SOTest::Flags)
bool FSOBodiesFollowTest::RunTest(const FString& Parameters)
{
	// What a round lands on is the body that is drawn. Every creature is shot at from four sides, on a grid over its
	// height and width, with the bullet's own trace; where each shot meets its collision is compared with the nearest
	// point of the drawn (skinned) surface. The engine's automatic bodies stood up to a metre and a half off the
	// Colossus; bodies fitted per bone by the import (import_assets.fit_bodies) stay close. And a shot at the head
	// lands on the head.
	const float Allowed = 20.0f; // cm: a convex hull over a bone's part bridges its hollows (measured worst: 18.5 on the Colossus's chest)
	struct FKind { UClass* Class; const TCHAR* Name; };
	const FKind Kinds[] = { { ASOEnemy::StaticClass(), TEXT("stalker") }, { ASORemnant::StaticClass(), TEXT("remnant") },
		{ ASOVeilborn::StaticClass(), TEXT("veilborn") }, { ASOBulwark::StaticClass(), TEXT("bulwark") }, { ASOColossus::StaticClass(), TEXT("colossus") },
		{ ASOBearer::StaticClass(), TEXT("bearer") } };
	for (const FKind& Kind : Kinds)
	{
		SOTest::FTestWorld W;
		W.AddBox(FVector(-3000, -3000, -100), FVector(3000, 3000, 0));
		FActorSpawnParameters P;
		P.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
		const float Half = Cast<ASOEnemy>(Kind.Class->GetDefaultObject())->GetCapsuleComponent()->GetScaledCapsuleHalfHeight();
		ASOEnemy* E = W.World->SpawnActor<ASOEnemy>(Kind.Class, FVector(0, 0, Half + 2.0f), FRotator::ZeroRotator, P);
		if (!TestNotNull(Kind.Name, E))
		{
			continue;
		}
		if (AController* Brain = E->GetController())
		{
			Brain->UnPossess();
			Brain->Destroy();
		}
		W.Run(0.4f);
		USkeletalMeshComponent* Mesh = E->GetMesh();
		const FSkeletalMeshRenderData* Data = Mesh->GetSkeletalMeshRenderData();
		TArray<FVector3f> Local;
		if (Data && Data->LODRenderData.Num() > 0 && Mesh->GetSkinWeightBuffer(0))
		{
			TArray<FMatrix44f> RefToLocals;
			Mesh->CacheRefToLocalMatrices(RefToLocals);
			USkinnedMeshComponent::ComputeSkinnedPositions(Mesh, Local, RefToLocals, Data->LODRenderData[0], *Mesh->GetSkinWeightBuffer(0));
		}
		if (!TestTrue(FString::Printf(TEXT("%s: its drawn surface can be read"), Kind.Name), Local.Num() > 100))
		{
			continue;
		}
		TArray<FVector> Surface;
		Surface.Reserve(Local.Num());
		FBox Box(ForceInit);
		for (const FVector3f& V : Local)
		{
			Surface.Add(Mesh->GetComponentTransform().TransformPosition(FVector(V)));
			Box += Surface.Last();
		}
		auto OffSurface = [&Surface](const FVector& At)
		{
			float Best = TNumericLimits<float>::Max();
			for (const FVector& V : Surface)
			{
				Best = FMath::Min(Best, static_cast<float>(FVector::DistSquared(V, At)));
			}
			return FMath::Sqrt(Best);
		};
		FCollisionQueryParams Params(SCENE_QUERY_STAT(SOTest), true);
		int32 Shots = 0, Landed = 0, Wide = 0;
		float Worst = 0.0f, Sum = 0.0f;
		FVector WorstAt = FVector::ZeroVector;
		FName WorstBone;
		const FVector Mid = Box.GetCenter(), Ext = Box.GetExtent();
		const FVector Dirs[] = { FVector(1, 0, 0), FVector(-1, 0, 0), FVector(0, 1, 0), FVector(0, -1, 0) };
		for (const FVector& Dir : Dirs)
		{
			const FVector Across = FVector::CrossProduct(FVector::UpVector, Dir);
			const float Width = FMath::Abs(FVector::DotProduct(Across, Ext)) + 60.0f; // (past the body's sides too: nothing may be hit out there)
			for (int32 iz = 0; iz <= 12; ++iz)
			{
				for (int32 iy = -6; iy <= 6; ++iy)
				{
					const FVector Through = Mid + FVector(0, 0, Ext.Z * (iz / 6.0f - 1.0f) * 0.98f) + Across * Width * (iy / 6.0f);
					FHitResult Hit;
					++Shots;
					if (W.World->LineTraceSingleByChannel(Hit, Through - Dir * 900.0f, Through + Dir * 900.0f, SO_TRACE_BULLET, Params) && Hit.GetActor() == E)
					{
						++Landed;
						const float Off = OffSurface(Hit.ImpactPoint);
						Sum += Off;
						Wide += Off > Allowed;
						if (Off > Worst)
						{
							Worst = Off;
							WorstAt = Hit.ImpactPoint - E->GetActorLocation();
							WorstBone = Hit.BoneName;
						}
					}
				}
			}
		}
		AddInfo(FString::Printf(TEXT("%s: %d bodies; %d of %d shots landed, on average %.1f cm from the drawn surface, at worst %.1f cm (bone '%s', at %s from its middle), %d further than %.0f cm"),
			Kind.Name, Mesh->Bodies.Num(), Landed, Shots, Landed > 0 ? Sum / Landed : 0.0f, Worst, *WorstBone.ToString(), *WorstAt.ToCompactString(), Wide, Allowed));
		TestTrue(FString::Printf(TEXT("%s: shots land on it"), Kind.Name), Landed > 20);
		TestTrue(FString::Printf(TEXT("%s: what a round lands on is within %.0f cm of what is drawn (worst %.1f cm, on '%s')"), Kind.Name, Allowed, Worst, *WorstBone.ToString()), Worst <= Allowed);
		// the head
		if (Mesh->DoesSocketExist(TEXT("head")))
		{
			const FVector Head = Mesh->GetSocketLocation(TEXT("head")) + FVector(0, 0, 6.0f);
			FHitResult Hit;
			const bool bHit = W.World->LineTraceSingleByChannel(Hit, Head + E->GetActorForwardVector() * 600.0f, Head - E->GetActorForwardVector() * 200.0f, SO_TRACE_BULLET, Params) && Hit.GetActor() == E;
			TestTrue(FString::Printf(TEXT("%s: a shot at the head lands on the head (it landed on '%s')"), Kind.Name, bHit ? *Hit.BoneName.ToString() : TEXT("nothing")),
				bHit && USOProjectileSubsystem::IsPrecisionBone(Hit.BoneName));
		}
	}
	return true;
}
#endif // WITH_DEV_AUTOMATION_TESTS
