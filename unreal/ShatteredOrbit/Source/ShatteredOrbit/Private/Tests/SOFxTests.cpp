// The effect system on the owner's guide (2026-11-20, "effects aren't just visuals, they are communication"): what
// can be measured without a picture. A hit's surface is read from its names; each surface spawns its own impact;
// a casing lands on the floor under it and stays there; the hit kinds on a body spawn the shield's cells; fire left
// by a blast keeps breathing for its time.

#include "SOTestWorld.h"

#if WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR

#include "Components/StaticMeshComponent.h"
#include "Engine/HitResult.h"
#include "SOFxSubsystem.h"

namespace
{
	FHitResult HitOn(SOTest::FTestWorld& W, const TCHAR* ActorName)
	{
		AActor* A = W.World->SpawnActor<AActor>();
		A->Rename(ActorName);
		UStaticMeshComponent* C = NewObject<UStaticMeshComponent>(A);
		A->SetRootComponent(C);
		C->RegisterComponent();
		FHitResult H;
		H.Component = C;
		H.HitObjectHandle = FActorInstanceHandle(A);
		H.ImpactPoint = FVector(300, 0, 0);
		H.ImpactNormal = FVector::UpVector;
		return H;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOFxSurfaceTest, "ShatteredOrbit.Fx.SurfaceOfAHit", SOTest::Flags)
bool FSOFxSurfaceTest::RunTest(const FString& Parameters)
{
	SOTest::FTestWorld W;
	using ES = USOFxSubsystem::ESurface;
	TestEqual(TEXT("a grate is metal"), USOFxSubsystem::SurfaceOf(HitOn(W, TEXT("Catwalk_Grate_7"))), ES::Metal);
	TestEqual(TEXT("a wreck is metal"), USOFxSubsystem::SurfaceOf(HitOn(W, TEXT("MR_street_wreck_2"))), ES::Metal);
	TestEqual(TEXT("rubble is dirt"), USOFxSubsystem::SurfaceOf(HitOn(W, TEXT("Rubble_heap_3"))), ES::Dirt);
	TestEqual(TEXT("moss is grass"), USOFxSubsystem::SurfaceOf(HitOn(W, TEXT("Moss_cushion_1"))), ES::Grass);
	TestEqual(TEXT("a crate is wood"), USOFxSubsystem::SurfaceOf(HitOn(W, TEXT("Crate_wood_4"))), ES::Wood);
	TestEqual(TEXT("a puddle is water"), USOFxSubsystem::SurfaceOf(HitOn(W, TEXT("Puddle_5"))), ES::Water);
	TestEqual(TEXT("anything else is concrete"), USOFxSubsystem::SurfaceOf(HitOn(W, TEXT("Facade_block_9"))), ES::Concrete);
	TestEqual(TEXT("and the floor's footsteps read the same names"), USOFxSubsystem::SurfaceName(ES::Metal), FName(TEXT("metal")));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOFxImpactsTest, "ShatteredOrbit.Fx.ImpactsPerSurfaceAndHitKinds", SOTest::Flags)
bool FSOFxImpactsTest::RunTest(const FString& Parameters)
{
	SOTest::FTestWorld W;
	USOFxSubsystem* Fx = W.World->GetSubsystem<USOFxSubsystem>();
	if (!TestNotNull(TEXT("fx subsystem"), Fx))
	{
		return false;
	}
	using ES = USOFxSubsystem::ESurface;
	int32 Before = Fx->GetNumParticles();
	for (const ES S : { ES::Concrete, ES::Metal, ES::Dirt, ES::Grass, ES::Wood, ES::Water })
	{
		Fx->Impact(FVector(500, 0, 100), FVector(-1, 0, 0), false, FLinearColor::Black, 0.0f, false, S);
		const int32 Spawned = Fx->GetNumParticles() - Before;
		TestTrue(FString::Printf(TEXT("surface %d spawns its own impact (%d particles)"), static_cast<int32>(S), Spawned), Spawned >= 8);
		Before = Fx->GetNumParticles();
	}
	// the hit kinds: a shield hit lights cells, a break throws more, a critical flares, a weak point bursts with a ring
	Fx->HitKind(FVector(500, 0, 100), FVector(-1, 0, 0), true, false, false, false, FLinearColor::Blue);
	const int32 ShieldHit = Fx->GetNumParticles() - Before;
	Before = Fx->GetNumParticles();
	Fx->HitKind(FVector(500, 0, 100), FVector(-1, 0, 0), true, true, false, false, FLinearColor::Blue);
	const int32 ShieldBroken = Fx->GetNumParticles() - Before;
	Before = Fx->GetNumParticles();
	Fx->HitKind(FVector(500, 0, 100), FVector(-1, 0, 0), false, false, true, false, FLinearColor::Red);
	const int32 Crit = Fx->GetNumParticles() - Before;
	Before = Fx->GetNumParticles();
	Fx->HitKind(FVector(500, 0, 100), FVector(-1, 0, 0), false, false, false, true, FLinearColor::Yellow);
	const int32 Weak = Fx->GetNumParticles() - Before;
	TestTrue(FString::Printf(TEXT("a shield hit lights the cells (%d)"), ShieldHit), ShieldHit >= 8);
	TestTrue(FString::Printf(TEXT("a shield broken throws more (%d > %d)"), ShieldBroken, ShieldHit), ShieldBroken > ShieldHit);
	TestTrue(FString::Printf(TEXT("a critical flares with lines out (%d)"), Crit), Crit >= 7);
	TestTrue(FString::Printf(TEXT("a weak point bursts with more and a ring (%d > %d)"), Weak, Crit), Weak > Crit);
	// a blast on the ground leaves fire that breathes for its time
	Before = Fx->GetNumParticles();
	Fx->Blast(FVector(800, 0, 0), FVector::UpVector, 150.0f, USOFxSubsystem::EBlast::Fire, FLinearColor(1.0f, 0.7f, 0.3f));
	TestTrue(TEXT("a grenade's blast leaves a fire"), Fx->GetNumBurns() == 1);
	W.Run(1.0f);
	const int32 AfterASecond = Fx->GetNumParticles();
	W.Run(0.5f);
	TestTrue(TEXT("the fire keeps breathing out flames"), Fx->GetNumParticles() > 0 && Fx->GetNumBurns() == 1);
	W.Run(2.0f);
	TestTrue(TEXT("and dies down when its time is up"), Fx->GetNumBurns() == 0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOFxCasingTest, "ShatteredOrbit.Fx.CasingsLandOnTheFloor", SOTest::Flags)
bool FSOFxCasingTest::RunTest(const FString& Parameters)
{
	SOTest::FTestWorld W;
	USOFxSubsystem* Fx = W.World->GetSubsystem<USOFxSubsystem>();
	if (!TestNotNull(TEXT("fx subsystem"), Fx))
	{
		return false;
	}
	// thrown from a port 1.2 m up with a floor at 20 cm: it arcs, lands, bounces and comes to rest on the floor
	for (int32 i = 0; i < 5; ++i)
	{
		Fx->Casing(FVector(0, 0, 120), FVector::RightVector, FVector::UpVector, FVector::ZeroVector, 1.0f, 20.0f);
	}
	TestTrue(TEXT("casings in the air"), Fx->GetNumParticles() >= 5);
	W.Run(1.2f);
	TestTrue(FString::Printf(TEXT("after 1.2 s nothing is under the floor (lowest %.1f)"), Fx->LowestParticleZ()), Fx->LowestParticleZ() >= 19.5f);
	TestTrue(FString::Printf(TEXT("and they have come down to it (lowest %.1f)"), Fx->LowestParticleZ()), Fx->LowestParticleZ() <= 21.0f);
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
