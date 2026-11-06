// Stage 3 automation tests: damage, rounds, the rifle, reloads, the stalker, spawners, animation, content.

#include "SOTestWorld.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "Animation/AnimSequenceBase.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/StaticMesh.h"
#include "PhysicsEngine/PhysicsAsset.h"
#include "SOAbilitySystemComponent.h"
#include "SOCharacterMovementComponent.h"
#include "SOCombatStatics.h"
#include "SOEnemy.h"
#include "SOEnemyAIController.h"
#include "SOEnemySpawner.h"
#include "SOFxSubsystem.h"
#include "SOSound.h"
#include "Sound/SoundBase.h"
#include "SOGunRigComponent.h"
#include "SOLocomotionAnimInstance.h"
#include "SOProjectileSubsystem.h"
#include "SOReload.h"
#include "SOWeapon.h"
#include "SOWeaponData.h"

namespace SOTest
{
	ASOEnemy* SpawnStalker(FTestWorld& W, const FVector& Feet, const FRotator& Rotation = FRotator::ZeroRotator)
	{
		FActorSpawnParameters Params;
		Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
		return W.World->SpawnActor<ASOEnemy>(Feet + FVector(0, 0, 93.0f), Rotation, Params);
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSODamageTest, "ShatteredOrbit.Combat.ShieldThenHealth", SOTest::Flags)
bool FSODamageTest::RunTest(const FString& Parameters)
{
	SOTest::FTestWorld W;
	W.AddBox(FVector(-2000, -2000, -100), FVector(2000, 2000, 0));
	ASOCharacter* Player = W.SpawnCharacter(FVector(0, 0, 0));
	W.Run(0.1f);
	TestEqual(TEXT("player health"), Player->GetHealth(), 100.0f);
	TestEqual(TEXT("player shield"), Player->GetShield(), 50.0f);

	int32 Deaths = 0;
	const FDelegateHandle Handle = USOCombatStatics::OnCharacterDied().AddLambda([&Deaths, Player](ASOCombatCharacter* Victim, AActor*, UWorld*)
	{
		Deaths += Victim == Player;
	});

	USOCombatStatics::ApplyDamage(nullptr, Player, 60.0f, false);
	TestEqual(TEXT("shield absorbs first"), Player->GetShield(), 0.0f);
	TestEqual(TEXT("the rest comes off health"), Player->GetHealth(), 90.0f);
	TestFalse(TEXT("alive at 90"), Player->IsDead());

	// Shield regenerates after the delay.
	W.Run(Player->GetSOAbilitySystem()->ShieldRegenDelay + 1.0f);
	TestTrue(TEXT("shield regenerates"), Player->GetShield() > 10.0f);

	USOCombatStatics::ApplyDamage(nullptr, Player, 500.0f, false);
	TestEqual(TEXT("health clamps at 0"), Player->GetHealth(), 0.0f);
	TestTrue(TEXT("dead"), Player->IsDead());
	TestEqual(TEXT("death broadcast once"), Deaths, 1);
	TestEqual(TEXT("no damage to the dead"), USOCombatStatics::ApplyDamage(nullptr, Player, 10.0f, false), 0.0f);
	USOCombatStatics::OnCharacterDied().Remove(Handle);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOFactionTest, "ShatteredOrbit.Combat.NoFriendlyFire", SOTest::Flags)
bool FSOFactionTest::RunTest(const FString& Parameters)
{
	SOTest::FTestWorld W;
	ASOEnemy* A = SOTest::SpawnStalker(W, FVector(0, 0, 0));
	ASOEnemy* B = SOTest::SpawnStalker(W, FVector(300, 0, 0));
	ASOCharacter* Player = W.SpawnCharacter(FVector(600, 0, 0));
	TestEqual(TEXT("stalkers do not hurt stalkers"), USOCombatStatics::ApplyDamage(A, B, 20.0f, false), 0.0f);
	TestEqual(TEXT("stalker hurts player"), USOCombatStatics::ApplyDamage(A, Player, 20.0f, false), 20.0f);
	TestEqual(TEXT("stalker health"), B->GetHealth(), 140.0f);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOBulletDropTest, "ShatteredOrbit.Combat.BulletDropAndFalloff", SOTest::Flags)
bool FSOBulletDropTest::RunTest(const FString& Parameters)
{
	SOTest::FTestWorld W;
	USOProjectileSubsystem* Rounds = W.World->GetSubsystem<USOProjectileSubsystem>();
	if (!TestNotNull(TEXT("projectile subsystem"), Rounds))
	{
		return false;
	}
	FSOProjectile Round;
	Round.Origin = Round.Position = FVector(0, 0, 10000.0f);
	Round.Velocity = FVector(71500.0f, 0, 0); // 715 m/s
	Round.Gravity = 980.0f;
	for (int32 i = 0; i < 30; ++i)
	{
		Rounds->StepRound(Round, SOTest::Dt);
	}
	const float T = 30 * SOTest::Dt;
	TestEqual(TEXT("travel after 0.5 s"), static_cast<float>(Round.Position.X), 71500.0f * T, 1.0f);
	TestEqual(TEXT("drop after 0.5 s = g t^2 / 2"), static_cast<float>(10000.0f - Round.Position.Z), 0.5f * 980.0f * T * T, 0.5f);

	Round.Damage = 19.0f;
	Round.FalloffStart = 4000.0f;
	Round.MinDamageScale = 0.6f;
	TestEqual(TEXT("full damage inside range"), USOProjectileSubsystem::DamageAtDistance(Round, 3000.0f), 19.0f);
	TestEqual(TEXT("falloff halfway"), USOProjectileSubsystem::DamageAtDistance(Round, 6000.0f), 19.0f * 0.8f, 1e-3f);
	TestEqual(TEXT("floor at twice the range"), USOProjectileSubsystem::DamageAtDistance(Round, 20000.0f), 19.0f * 0.6f, 1e-3f);
	TestTrue(TEXT("head is a precision bone"), USOProjectileSubsystem::IsPrecisionBone(TEXT("head")));
	TestFalse(TEXT("chest is not"), USOProjectileSubsystem::IsPrecisionBone(TEXT("chest")));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSORifleTest, "ShatteredOrbit.Weapon.RifleFireAndReload", SOTest::Flags)
bool FSORifleTest::RunTest(const FString& Parameters)
{
	SOTest::FTestWorld W;
	W.AddBox(FVector(-4000, -4000, -100), FVector(4000, 4000, 0));
	ASOCharacter* Player = W.SpawnCharacter(FVector(0, 0, 0));
	W.Run(0.3f);
	ASOWeapon* Rifle = Player->GetWeapon();
	if (!TestNotNull(TEXT("default weapon equipped (DA_Rifle, run import_assets.py)"), Rifle) || !TestNotNull(TEXT("rifle data"), Rifle->GetData()))
	{
		return false;
	}
	const USOWeaponData* Data = Rifle->GetData();
	TestEqual(TEXT("magazine"), Rifle->GetMag(), 30);
	TestEqual(TEXT("reserve"), Rifle->GetReserve(), 300);
	TestTrue(TEXT("first-person rig built"), Rifle->GetFirstPersonRig()->IsBuilt());
	TestNotNull(TEXT("mag part"), Rifle->GetFirstPersonRig()->GetPart(TEXT("mag")));
	TestNotNull(TEXT("bolt part"), Rifle->GetFirstPersonRig()->GetPart(TEXT("bolt")));

	// 600 rpm for one second: 10 rounds (+1 for the first shot at t = 0).
	Rifle->StartFire();
	W.Run(1.0f);
	Rifle->StopFire();
	const int32 Fired = Rifle->GetShotsFired();
	TestTrue(FString::Printf(TEXT("600 rpm: %d shots in 1 s"), Fired), Fired >= 10 && Fired <= 11);
	TestEqual(TEXT("ammo used"), Rifle->GetMag(), 30 - Fired);

	// Tactical reload: the mag leaves and the spare arrives mid-way; ammo lands on the seat event.
	Rifle->StartReload();
	TestTrue(TEXT("reloading"), Rifle->IsReloading());
	TestEqual(TEXT("tactical reload time"), Rifle->GetReloadDuration(), Data->ReloadTime, 0.01f);
	bool bMagHidden = false, bSpareShown = false;
	UStaticMeshComponent* Mag = Rifle->GetFirstPersonRig()->GetPart(TEXT("mag"));
	W.Run(Data->ReloadTime + 0.1f, [&]()
	{
		bMagHidden |= Mag && !Mag->IsVisible();
		bSpareShown |= Rifle->GetFirstPersonRig()->GetSpare() && Rifle->GetFirstPersonRig()->GetSpare()->IsVisible();
	});
	TestTrue(TEXT("old mag dropped"), bMagHidden);
	TestTrue(TEXT("spare mag brought in"), bSpareShown);
	TestFalse(TEXT("reload finished"), Rifle->IsReloading());
	TestEqual(TEXT("magazine full"), Rifle->GetMag(), 30);
	TestEqual(TEXT("reserve paid"), Rifle->GetReserve(), 300 - Fired);

	// Empty reload adds the chambering (bolt rack).
	Rifle->SetAmmo(0, 100);
	Rifle->StartReload();
	TestTrue(TEXT("empty reload is longer"), Rifle->GetReloadDuration() > Data->ReloadTime + 0.3f);
	float MaxBolt = 0.0f;
	W.Run(Rifle->GetReloadDuration() + 0.1f, [&]() { MaxBolt = FMath::Max(MaxBolt, Rifle->GetPose().Bolt); });
	TestTrue(TEXT("bolt racked back ~9.5 cm"), MaxBolt > 0.08f);
	TestEqual(TEXT("empty reload fills"), Rifle->GetMag(), 30);
	TestEqual(TEXT("reserve after empty reload"), Rifle->GetReserve(), 70);

	// Recoil kicks the aim up and recovers by itself.
	const FVector Before0 = Player->GetAimDirection();
	float PeakRecoil = 0.0f;
	Rifle->StartFire();
	W.Run(0.25f, [&]() { PeakRecoil = FMath::Max(PeakRecoil, Player->GetRecoilPitch()); });
	Rifle->StopFire();
	TestTrue(FString::Printf(TEXT("recoil kicks the aim up (peak %.2f deg)"), PeakRecoil), PeakRecoil > 0.3f);
	W.Run(0.6f);
	TestEqual(TEXT("recoil recovered"), Player->GetRecoilPitch(), 0.0f, 0.01f);
	TestTrue(TEXT("aim back where it was"), Player->GetAimDirection().Equals(Before0, 1e-3f));
	Rifle->SetAmmo(30, 70);

	// Sprinting blocks the trigger.
	Player->GetSOMovement()->SetWantsToSprint(true);
	W.Run(0.5f, [Player]() { Player->AddMovementInput(FVector::ForwardVector, 1.0f); });
	const int32 Before = Rifle->GetShotsFired();
	Rifle->StartFire();
	W.Run(0.1f, [Player]() { Player->AddMovementInput(FVector::ForwardVector, 1.0f); });
	Rifle->StopFire();
	TestEqual(TEXT("no shots while sprinting"), Rifle->GetShotsFired(), Before);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOReloadTimelineTest, "ShatteredOrbit.Weapon.ReloadTimeline", SOTest::Flags)
bool FSOReloadTimelineTest::RunTest(const FString& Parameters)
{
	TArray<FSOReloadSegment> Tactical = SOReload::BuildMagReload(TEXT("rifle"), false, 2.3f);
	TArray<FSOReloadSegment> Empty = SOReload::BuildMagReload(TEXT("rifle"), true, 2.3f);
	TestEqual(TEXT("tactical segments"), Tactical.Num(), 2);
	TestEqual(TEXT("empty segments"), Empty.Num(), 3);
	TestEqual(TEXT("tactical = reload time"), SOReload::GetDuration(Tactical), 2.3f, 1e-3f);
	TestEqual(TEXT("empty adds the rack"), SOReload::GetDuration(Empty), 2.3f + 0.32f * 2.3f / 1.24f, 1e-3f);

	FSOReloadPlayer Player;
	Player.Start(MoveTemp(Tactical));
	float SeatAt = -1.0f, DropAt = -1.0f;
	float T = 0.0f;
	int32 FramesOffRestAfterSeat = 0;
	while (Player.IsActive() && T < 5.0f)
	{
		TArray<FSOReloadEvent> Events;
		Player.Update(SOTest::Dt, Events);
		T += SOTest::Dt;
		for (const FSOReloadEvent& E : Events)
		{
			if (E.Name == TEXT("seat")) { SeatAt = T; }
			if (E.Name == TEXT("drop")) { DropAt = T; }
		}
		// Once seated the magazine must stay home and visible (it used to snap back to the dropped pose).
		if (SeatAt >= 0.0f && Player.IsActive())
		{
			const FSOReloadPose& P = Player.GetPose();
			float Off = 0.0f;
			for (float V : P.Mag) { Off += FMath::Abs(V); }
			FramesOffRestAfterSeat += (Off > 1e-4f || !P.bMagVisible) ? 1 : 0;
		}
	}
	TestEqual(TEXT("seated magazine stays at rest"), FramesOffRestAfterSeat, 0);
	const float K = 2.3f / 1.24f;
	TestEqual(TEXT("mag drops at 0.55 of the main segment"), DropAt, 0.55f * K, 0.02f);
	TestEqual(TEXT("seat at 0.88 of the main segment"), SeatAt, 0.88f * K, 0.02f);
	TestFalse(TEXT("finished"), Player.IsActive());

	// Easing and glTF -> mesh conversions.
	TestEqual(TEXT("smootherstep midpoint"), FSOReloadPlayer::Ease(ESOEase::Smoother, 0.5f), 0.5f, 1e-5f);
	TestEqual(TEXT("ease out is fast early"), FSOReloadPlayer::Ease(ESOEase::Out, 0.5f), 0.875f, 1e-5f);
	TestTrue(TEXT("glTF barrel (+z) is mesh +Y"), USOGunRigComponent::GltfToMesh(0, 0, 1).Equals(FVector(0, 100, 0)));
	const FVector Up = USOGunRigComponent::GltfEulerToMesh(0.0f, 0.0f, 0.0f).RotateVector(FVector(0, 0, 1));
	TestTrue(TEXT("identity rotation"), Up.Equals(FVector(0, 0, 1), 1e-4f));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSORoundHitsStalkerTest, "ShatteredOrbit.Combat.RoundHitsStalker", SOTest::Flags)
bool FSORoundHitsStalkerTest::RunTest(const FString& Parameters)
{
	SOTest::FTestWorld W;
	W.AddBox(FVector(-4000, -4000, -100), FVector(4000, 4000, 0));
	ASOCharacter* Player = W.SpawnCharacter(FVector(0, 0, 0));
	ASOEnemy* Stalker = SOTest::SpawnStalker(W, FVector(2000, 0, 0), FRotator(0, 180, 0));
	W.Run(0.2f);
	Stalker->GetController()->SetActorTickEnabled(false); // hold still

	USOProjectileSubsystem* Rounds = W.World->GetSubsystem<USOProjectileSubsystem>();
	float Applied = 0.0f;
	FName HitBone;
	const FDelegateHandle Handle = Rounds->OnHit.AddLambda([&](const FSOProjectile&, const FHitResult& Hit, float Damage)
	{
		Applied += Damage;
		HitBone = Hit.BoneName;
	});
	FSOProjectile Round;
	Round.Origin = Round.Position = FVector(0, 0, 120.0f);
	const FVector Chest = Stalker->GetActorLocation() + FVector(0, 0, 20.0f);
	Round.Velocity = (Chest - Round.Origin).GetSafeNormal() * 71500.0f;
	Round.Gravity = 0.0f;
	Round.Damage = 19.0f;
	Round.CritMultiplier = 1.6f;
	Round.Instigator = Player;
	Rounds->Fire(Round);
	W.Run(0.2f);
	Rounds->OnHit.Remove(Handle);

	const bool bMeshHits = Stalker->GetMesh()->GetSkeletalMeshAsset() && Stalker->GetMesh()->GetPhysicsAsset();
	AddInfo(FString::Printf(TEXT("hit bone '%s' (per-bone hits: %d)"), *HitBone.ToString(), bMeshHits));
	TestTrue(TEXT("round hit the stalker"), Applied > 0.0f);
	TestEqual(TEXT("stalker took the damage"), Stalker->GetHealth(), 140.0f - Applied, 0.01f);

	// Kill it: dies once, stops moving.
	USOCombatStatics::ApplyDamage(Player, Stalker, 1000.0f, false);
	TestTrue(TEXT("stalker dead"), Stalker->IsDead());
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOStalkerAITest, "ShatteredOrbit.AI.StalkerHuntsAndStrikes", SOTest::Flags)
bool FSOStalkerAITest::RunTest(const FString& Parameters)
{
	SOTest::FTestWorld W;
	W.AddBox(FVector(-4000, -4000, -100), FVector(4000, 4000, 0));
	ASOCharacter* Player = W.SpawnCharacter(FVector(0, 0, 0));
	ASOEnemy* Stalker = SOTest::SpawnStalker(W, FVector(1200, 0, 0), FRotator(0, 180, 0));
	if (!TestNotNull(TEXT("stalker"), Stalker))
	{
		return false;
	}
	ASOEnemyAIController* AI = Cast<ASOEnemyAIController>(Stalker->GetController());
	if (!TestNotNull(TEXT("stalker is possessed by its AI"), AI))
	{
		return false;
	}
	bool bChased = false;
	W.Run(4.0f, [&]() { bChased |= AI->GetState() == ESOEnemyState::Chase; });
	TestTrue(TEXT("it noticed and chased the player"), bChased);
	TestTrue(TEXT("it targets the player"), AI->GetTarget() == Player);
	TestTrue(FString::Printf(TEXT("it struck (%d hits)"), Stalker->GetStrikesLanded()), Stalker->GetStrikesLanded() >= 1);
	TestTrue(TEXT("the player took melee damage"), Player->GetHealth() + Player->GetShield() < 150.0f);

	// Gunfire wakes a stalker that cannot see you.
	ASOEnemy* Behind = SOTest::SpawnStalker(W, FVector(-2500, 0, 0), FRotator(0, 180, 0)); // facing away
	W.Run(0.3f);
	ASOEnemyAIController* AI2 = Cast<ASOEnemyAIController>(Behind->GetController());
	TestTrue(TEXT("unaware before the shot"), AI2 && AI2->GetTarget() == nullptr);
	USOCombatStatics::ReportNoise(Player, Player->GetActorLocation(), Player, 4500.0f);
	W.Run(0.3f);
	TestTrue(TEXT("gunfire alerts it"), AI2 && AI2->GetTarget() == Player);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOSpawnerTest, "ShatteredOrbit.AI.SpawnerRespawns", SOTest::Flags)
bool FSOSpawnerTest::RunTest(const FString& Parameters)
{
	SOTest::FTestWorld W;
	W.AddBox(FVector(-4000, -4000, -100), FVector(4000, 4000, 0));
	FActorSpawnParameters Params;
	Params.bDeferConstruction = true;
	ASOEnemySpawner* Spawner = W.World->SpawnActor<ASOEnemySpawner>(FVector(0, 0, 0), FRotator::ZeroRotator, Params);
	Spawner->RespawnDelay = 1.0f;
	Spawner->FinishSpawning(FTransform::Identity);
	W.Run(0.1f);
	ASOEnemy* First = Spawner->GetCurrent();
	if (!TestNotNull(TEXT("spawned on begin play"), First))
	{
		return false;
	}
	USOCombatStatics::ApplyDamage(nullptr, First, 1000.0f, false);
	TestTrue(TEXT("first one dead"), First->IsDead());
	W.Run(0.5f);
	TestNull(TEXT("not yet back"), Spawner->GetCurrent());
	W.Run(0.8f);
	TestNotNull(TEXT("respawned after the delay"), Spawner->GetCurrent());
	TestEqual(TEXT("two spawns"), Spawner->GetSpawnCount(), 2);
	TestTrue(TEXT("the new one is alive"), Spawner->GetCurrent() && !Spawner->GetCurrent()->IsDead());
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOLocomotionAnimTest, "ShatteredOrbit.Anim.Locomotion", SOTest::Flags)
bool FSOLocomotionAnimTest::RunTest(const FString& Parameters)
{
	SOTest::FTestWorld W;
	W.AddBox(FVector(-8000, -8000, -100), FVector(8000, 8000, 0));
	ASOCharacter* Player = W.SpawnCharacter(FVector(0, 0, 0));
	Player->GetMesh()->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
	USOLocomotionAnimInstance* Anim = Cast<USOLocomotionAnimInstance>(Player->GetMesh()->GetAnimInstance());
	if (!TestNotNull(TEXT("locomotion anim instance (body mesh imported)"), Anim))
	{
		return false;
	}
	TestNotNull(TEXT("idle clip"), Anim->Clips.Idle.Get());
	TestNotNull(TEXT("walk clip"), Anim->Clips.Walk.Get());
	TestNotNull(TEXT("death clip"), Anim->Clips.Death.Get());
	W.Run(0.5f);
	TestTrue(TEXT("idle when standing"), Anim->Weights[0] > 0.9f);
	W.Run(1.0f, [Player]() { Player->AddMovementInput(FVector::ForwardVector, 1.0f); });
	TestTrue(FString::Printf(TEXT("walking blends in (walk %.2f)"), Anim->Weights[1]), Anim->Weights[1] > 0.6f);
	USOCombatStatics::ApplyDamage(nullptr, Player, 1000.0f, false);
	W.Run(0.5f);
	TestTrue(TEXT("death clip plays"), Anim->Weights[4] > 0.9f);

	// The imported body faces +X after the -90 degree mesh yaw: its left foot is on the actor left (-Y).
	const USkeletalMeshComponent* Body = Player->GetMesh();
	const FName FootL = Body->GetBoneIndex(TEXT("foot_L")) != INDEX_NONE ? FName(TEXT("foot_L")) : FName(TEXT("footL"));
	const FName FootR = Body->GetBoneIndex(TEXT("foot_R")) != INDEX_NONE ? FName(TEXT("foot_R")) : FName(TEXT("footR"));
	if (TestTrue(TEXT("foot bones exist"), Body->GetBoneIndex(FootL) != INDEX_NONE && Body->GetBoneIndex(FootR) != INDEX_NONE))
	{
		const FVector L = Player->GetActorTransform().InverseTransformPosition(Body->GetBoneLocation(FootL));
		const FVector R = Player->GetActorTransform().InverseTransformPosition(Body->GetBoneLocation(FootR));
		TestTrue(FString::Printf(TEXT("left foot left of right foot (L.y %.1f, R.y %.1f)"), L.Y, R.Y), L.Y < R.Y);
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOCombatContentTest, "ShatteredOrbit.Content.CombatAssets", SOTest::Flags)
bool FSOCombatContentTest::RunTest(const FString& Parameters)
{
	const USOWeaponData* Rifle = LoadObject<USOWeaponData>(nullptr, TEXT("/Game/Weapons/Rifle/DA_Rifle.DA_Rifle"));
	if (TestNotNull(TEXT("DA_Rifle (run import_assets.py)"), Rifle))
	{
		TestEqual(TEXT("rifle damage (data.js)"), Rifle->Damage, 19.0f);
		TestEqual(TEXT("rifle rpm"), Rifle->RoundsPerMinute, 600.0f);
		TestEqual(TEXT("rifle magazine"), Rifle->MagazineSize, 30);
		TestNotNull(TEXT("rifle body mesh"), Rifle->BodyMesh.LoadSynchronous());
		TestNotNull(TEXT("rifle mag part"), Rifle->FindPart(TEXT("mag")));
		TestNotNull(TEXT("rifle bolt part"), Rifle->FindPart(TEXT("bolt")));
		TestTrue(TEXT("muzzle in front (+Y in mesh space)"), Rifle->MuzzleLocation.Y > 50.0f);
		TestNotNull(TEXT("arms"), Rifle->ArmLeftMesh.LoadSynchronous());
	}
	const USkeletalMesh* Player = LoadObject<USkeletalMesh>(nullptr, TEXT("/Game/Characters/PlayerMale/SK_PlayerMale.SK_PlayerMale"));
	const USkeletalMesh* Stalker = LoadObject<USkeletalMesh>(nullptr, TEXT("/Game/Characters/Stalker/SK_Stalker.SK_Stalker"));
	if (TestNotNull(TEXT("player body"), Player))
	{
		TestNotNull(TEXT("player physics asset"), Player->GetPhysicsAsset());
		const FBox Box = Player->GetBounds().GetBox();
		TestTrue(FString::Printf(TEXT("player is ~1.8 m tall (%.0f cm)"), Box.GetSize().Z), Box.GetSize().Z > 160.0f && Box.GetSize().Z < 200.0f);
		FString Bones;
		const FReferenceSkeleton& Ref = Player->GetRefSkeleton();
		for (int32 i = 0; i < Ref.GetNum(); ++i)
		{
			Bones += Ref.GetBoneName(i).ToString() + TEXT(" ");
		}
		AddInfo(TEXT("player bones: ") + Bones);
		TestTrue(TEXT("weapon hand bone exists"), Ref.FindBoneIndex(GetDefault<ASOCharacter>()->WeaponSocket) != INDEX_NONE);
	}
	if (TestNotNull(TEXT("stalker body"), Stalker))
	{
		TestNotNull(TEXT("stalker physics asset"), Stalker->GetPhysicsAsset());
	}
	for (const TCHAR* Clip : { TEXT("/Game/Characters/PlayerMale/Anims/A_PlayerMale_Run.A_PlayerMale_Run"),
		TEXT("/Game/Characters/Stalker/Anims/A_Stalker_Attack.A_Stalker_Attack") })
	{
		TestNotNull(Clip, LoadObject<UAnimSequenceBase>(nullptr, Clip));
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOFxLifetimeTest, "ShatteredOrbit.FX.ImpactsSpawnAndExpire", SOTest::Flags)
bool FSOFxLifetimeTest::RunTest(const FString& Parameters)
{
	SOTest::FTestWorld W;
	USOFxSubsystem* Fx = W.World->GetSubsystem<USOFxSubsystem>();
	if (!TestNotNull(TEXT("fx subsystem"), Fx))
	{
		return false;
	}
	Fx->Impact(FVector(500, 0, 100), FVector(-1, 0, 0), false, FLinearColor::Black);
	Fx->Impact(FVector(500, 50, 100), FVector(-1, 0, 0), true, FLinearColor(0.3f, 0.0f, 0.5f));
	Fx->MuzzleFlash(FVector(0, 0, 150), FVector::ForwardVector);
	Fx->Tracer(FVector(0, 0, 150), FVector(3000, 0, 150), 71500.0f);
	TestTrue(FString::Printf(TEXT("particles spawned (%d)"), Fx->GetNumParticles()), Fx->GetNumParticles() > 20);
	W.Run(0.05f);
	TestEqual(TEXT("one bullet hole (none on flesh)"), Fx->GetNumDecals(), 1);
	W.Run(2.0f);
	TestEqual(TEXT("all particles expired"), Fx->GetNumParticles(), 0);
	TestEqual(TEXT("decal stays"), Fx->GetNumDecals(), 1);

	// Delayed impact (flight time) and the decal cap.
	Fx->Impact(FVector(800, 0, 100), FVector(-1, 0, 0), false, FLinearColor::Black, 0.2f);
	W.Run(0.1f);
	TestEqual(TEXT("impact waits for the round"), Fx->GetNumImpactsPlayed(), 2);
	W.Run(0.15f);
	TestEqual(TEXT("then plays"), Fx->GetNumImpactsPlayed(), 3);
	for (int32 i = 0; i < USOFxSubsystem::MaxDecals + 10; ++i)
	{
		Fx->Impact(FVector(900, i * 10.0f, 100), FVector(-1, 0, 0), false, FLinearColor::Black);
	}
	W.Run(0.05f);
	TestEqual(TEXT("decals capped"), Fx->GetNumDecals(), USOFxSubsystem::MaxDecals);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOShotFxTest, "ShatteredOrbit.FX.ShotsShowWhereTheyLand", SOTest::Flags)
bool FSOShotFxTest::RunTest(const FString& Parameters)
{
	SOTest::FTestWorld W;
	W.AddBox(FVector(-4000, -4000, -100), FVector(4000, 4000, 0));
	W.AddBox(FVector(1500, -500, 0), FVector(1600, 500, 400)); // a wall 15 m ahead
	ASOCharacter* Player = W.SpawnCharacter(FVector(0, 0, 0));
	W.Run(0.3f);
	USOFxSubsystem* Fx = W.World->GetSubsystem<USOFxSubsystem>();
	ASOWeapon* Rifle = Player->GetWeapon();
	if (!TestNotNull(TEXT("rifle"), Rifle))
	{
		return false;
	}
	Rifle->StartFire();
	W.Run(0.35f);
	Rifle->StopFire();
	W.Run(0.1f);
	TestTrue(FString::Printf(TEXT("impacts played on the wall (%d for %d shots)"), Fx->GetNumImpactsPlayed(), Rifle->GetShotsFired()),
		Fx->GetNumImpactsPlayed() >= Rifle->GetShotsFired() && Rifle->GetShotsFired() >= 3);
	TestTrue(FString::Printf(TEXT("bullet holes on the wall (%d)"), Fx->GetNumDecals()), Fx->GetNumDecals() >= 3);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOSoundsTest, "ShatteredOrbit.Audio.SoundsImported", SOTest::Flags)
bool FSOSoundsTest::RunTest(const FString& Parameters)
{
	for (const TCHAR* Name : { TEXT("rifle_shot_fp"), TEXT("rifle_shot_world"), TEXT("dry_fire"), TEXT("reload_start"), TEXT("mag_release"),
		TEXT("mag_out"), TEXT("pouch"), TEXT("mag_in"), TEXT("mag_slap"), TEXT("rack_back"), TEXT("rack_fwd"), TEXT("impact_hard"),
		TEXT("impact_flesh"), TEXT("stalker_attack"), TEXT("stalker_hurt"), TEXT("stalker_death"), TEXT("player_hurt"),
		TEXT("shield_break"), TEXT("shield_recharge"), TEXT("hit_tick"), TEXT("hit_crit"), TEXT("hit_kill"), TEXT("footstep_1"),
		TEXT("footstep_4") })
	{
		const USoundBase* Sound = USOSoundLibrary::Find(Name);
		if (TestNotNull(*FString::Printf(TEXT("S_%s (run import_assets.py)"), Name), Sound))
		{
			TestTrue(*FString::Printf(TEXT("%s has a duration"), Name), Sound->GetDuration() > 0.03f);
		}
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOClipMatchesSkeletonTest, "ShatteredOrbit.Content.ClipsMatchSkeleton", SOTest::Flags)
bool FSOClipMatchesSkeletonTest::RunTest(const FString& Parameters)
{
	// Bone lengths in every clip's first frame must match the skeleton's reference pose (units and axes).
	const TPair<const TCHAR*, const TCHAR*> Cases[] = {
		{ TEXT("/Game/Characters/PlayerMale/SK_PlayerMale.SK_PlayerMale"), TEXT("/Game/Characters/PlayerMale/Anims/A_PlayerMale_Idle.A_PlayerMale_Idle") },
		{ TEXT("/Game/Characters/Stalker/SK_Stalker.SK_Stalker"), TEXT("/Game/Characters/Stalker/Anims/A_Stalker_Idle.A_Stalker_Idle") } };
	for (const TPair<const TCHAR*, const TCHAR*>& Case : Cases)
	{
		const USkeletalMesh* Mesh = LoadObject<USkeletalMesh>(nullptr, Case.Key);
		const UAnimSequence* Clip = LoadObject<UAnimSequence>(nullptr, Case.Value);
		if (!TestNotNull(Case.Key, Mesh) || !TestNotNull(Case.Value, Clip))
		{
			continue;
		}
		const FReferenceSkeleton& Ref = Mesh->GetRefSkeleton();
		int32 Bad = 0;
		for (int32 i = 1; i < Ref.GetNum(); ++i)
		{
			const FName Bone = Ref.GetBoneName(i);
			FTransform Pose;
			Clip->GetBoneTransform(Pose, FSkeletonPoseBoneIndex(Clip->GetSkeleton()->GetReferenceSkeleton().FindBoneIndex(Bone)), 0.0, false);
			const FTransform& Rest = Ref.GetRefBonePose()[i];
			const float RestLen = Rest.GetTranslation().Size();
			const float PoseLen = Pose.GetTranslation().Size();
			const bool bOk = FMath::Abs(RestLen - PoseLen) <= FMath::Max(2.0f, RestLen * 0.25f);
			if (!bOk || i < 4)
			{
				AddInfo(FString::Printf(TEXT("%s %s: rest %s | clip %s | rot rest %s clip %s"), *Mesh->GetName(), *Bone.ToString(),
					*Rest.GetTranslation().ToCompactString(), *Pose.GetTranslation().ToCompactString(),
					*Rest.GetRotation().Rotator().ToCompactString(), *Pose.GetRotation().Rotator().ToCompactString()));
			}
			Bad += !bOk;
		}
		TestEqual(*FString::Printf(TEXT("%s bones whose clip length differs from the rest pose"), *Mesh->GetName()), Bad, 0);
	}
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
