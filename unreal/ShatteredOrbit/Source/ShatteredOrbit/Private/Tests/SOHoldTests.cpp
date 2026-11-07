// Holding the gun: both bodies' hands on the grips, sights on the crosshair, third-person shots at the crosshair,
// and the off hand never passing through the receiver during reloads.

#include "SOTestWorld.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "Camera/CameraComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "SOCombatCharacter.h"
#include "SOGunRigComponent.h"
#include "SOReload.h"
#include "SOWeapon.h"
#include "SOWeaponData.h"

namespace SOTest
{
	/** A player with the default rifle, both bodies animating every frame (nothing renders in tests). */
	ASOCharacter* SpawnArmedPlayer(FTestWorld& W)
	{
		W.AddBox(FVector(-4000, -4000, -100), FVector(4000, 4000, 0));
		ASOCharacter* Player = W.SpawnCharacter(FVector(0, 0, 0));
		if (Player)
		{
			Player->GetFirstPersonArms()->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
			Player->GetMesh()->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
			W.Run(0.4f);
		}
		return Player;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOHandsOnGripsTest, "ShatteredOrbit.Hold.HandsOnGrips", SOTest::Flags)
bool FSOHandsOnGripsTest::RunTest(const FString& Parameters)
{
	SOTest::FTestWorld W;
	ASOCharacter* Player = SOTest::SpawnArmedPlayer(W);
	ASOWeapon* Rifle = Player ? Player->GetWeapon() : nullptr;
	if (!TestNotNull(TEXT("armed player (run import_assets.py)"), Rifle))
	{
		return false;
	}
	const USkeletalMesh* Arms = Player->GetFirstPersonArms()->GetSkeletalMeshAsset();
	TestTrue(TEXT("first person uses the body's own arms mesh"), Arms && Arms->GetName() == TEXT("SK_PlayerMaleArms"));
	TestTrue(TEXT("arms mesh shares the body skeleton"), Arms && Player->GetMesh()->GetSkeletalMeshAsset() &&
		Arms->GetSkeleton() == Player->GetMesh()->GetSkeletalMeshAsset()->GetSkeleton());

	auto Check = [&](const TCHAR* When, bool bFirstPersonOn = true)
	{
		const USkeletalMeshComponent* Bodies[2] = { Player->GetFirstPersonArms(), Player->GetMesh() };
		const USOGunRigComponent* Rigs[2] = { Rifle->GetFirstPersonRig(), Rifle->GetThirdPersonRig() };
		for (int32 i = bFirstPersonOn ? 0 : 1; i < 2; ++i) // the first-person arms only animate in first person
		{
			FTransform Right, Left;
			if (!TestTrue(TEXT("hand targets"), Rigs[i]->GetHandTargets(Right, Left)))
			{
				continue;
			}
			const TCHAR* View = i == 0 ? TEXT("first person") : TEXT("third person");
			const float DR = FVector::Dist(Bodies[i]->GetBoneLocation(TEXT("hand_R")), Right.GetLocation());
			const float DL = FVector::Dist(Bodies[i]->GetBoneLocation(TEXT("hand_L")), Left.GetLocation());
			TestTrue(FString::Printf(TEXT("%s, %s: firing hand on the grip (%.2f cm off)"), View, When, DR), DR < 1.0f);
			TestTrue(FString::Printf(TEXT("%s, %s: support hand on the handguard (%.2f cm off)"), View, When, DL), DL < 2.0f);
		}
	};
	Check(TEXT("hip"));
	Player->HandleAimPressed();
	W.Run(0.5f);
	Check(TEXT("aiming"));
	Player->HandleAimReleased();
	Player->SetViewMode(ESOViewMode::ThirdPerson);
	W.Run(0.5f);
	Check(TEXT("third-person view"), false);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOSightsOnCrosshairTest, "ShatteredOrbit.Hold.SightsOnCrosshair", SOTest::Flags)
bool FSOSightsOnCrosshairTest::RunTest(const FString& Parameters)
{
	SOTest::FTestWorld W;
	ASOCharacter* Player = SOTest::SpawnArmedPlayer(W);
	ASOWeapon* Rifle = Player ? Player->GetWeapon() : nullptr;
	if (!TestNotNull(TEXT("armed player"), Rifle) || !Rifle->GetData())
	{
		return false;
	}
	Player->HandleAimPressed();
	W.Run(0.6f);
	TestEqual(TEXT("fully aimed"), Player->GetAimProgress(), 1.0f, 1e-3f);

	// The sight line (rear sight + front post, both at the sight socket's height) lies on the eye's axis.
	const FTransform Eye = Player->GetEyeTransform(true);
	const USOGunRigComponent* Rig = Rifle->GetFirstPersonRig();
	const FVector Sight = Eye.InverseTransformPosition(Rig->GetComponentTransform().TransformPosition(USOGunRigComponent::MeshToRig(Rifle->GetData()->SightLocation)));
	TestEqual(TEXT("sight centred left-right (cm)"), Sight.Y, 0.0, 0.05);
	TestEqual(TEXT("sight centred up-down (cm)"), Sight.Z, 0.0, 0.05);
	TestTrue(FString::Printf(TEXT("sight in front of the eye (%.1f cm)"), Sight.X), Sight.X > 20.0f);
	const FVector Barrel = Eye.InverseTransformVector(Rig->GetForwardVector());
	TestTrue(TEXT("barrel parallel to the line of sight"), Barrel.X > 0.9999f);

	// Recoil kicks the view and the gun together, so the sights stay on the crosshair while firing.
	float PeakRecoil = 0.0f, WorstOff = 0.0f, WorstDir = 1.0f;
	Rifle->StartFire();
	W.Run(0.5f, [&]()
	{
		PeakRecoil = FMath::Max(PeakRecoil, Player->GetRecoilPitch());
		const FTransform Kicked = Player->GetEyeTransform(true);
		WorstDir = FMath::Min(WorstDir, (float)Kicked.InverseTransformVector(Player->GetAimDirection()).X);
		const FVector KickedSight = Kicked.InverseTransformPosition(Rig->GetComponentTransform().TransformPosition(USOGunRigComponent::MeshToRig(Rifle->GetData()->SightLocation)));
		WorstOff = FMath::Max(WorstOff, (float)FVector2D(KickedSight.Y, KickedSight.Z).Size());
	});
	Rifle->StopFire();
	TestTrue(FString::Printf(TEXT("recoil kicked (peak %.2f deg)"), PeakRecoil), PeakRecoil > 0.3f);
	TestTrue(TEXT("rounds go along the kicked view"), WorstDir > 0.99999f);
	TestTrue(FString::Printf(TEXT("sights follow the kick (at most %.2f cm off the axis)"), WorstOff), WorstOff < 1.5f);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOThirdPersonAimTest, "ShatteredOrbit.Aim.ThirdPersonHitsCrosshair", SOTest::Flags)
bool FSOThirdPersonAimTest::RunTest(const FString& Parameters)
{
	SOTest::FTestWorld W;
	W.AddBox(FVector(1500, -3000, 0), FVector(1600, 3000, 800)); // a wall 15 m ahead
	ASOCharacter* Player = SOTest::SpawnArmedPlayer(W);
	if (!TestNotNull(TEXT("player"), Player))
	{
		return false;
	}
	auto WallHit = [&](const FVector& From, const FVector& Dir, FVector& Out)
	{
		FHitResult Hit;
		FCollisionQueryParams Params(SCENE_QUERY_STAT(SOTest), true, Player);
		if (Player->GetWeapon())
		{
			Params.AddIgnoredActor(Player->GetWeapon());
		}
		const bool bHit = W.World->LineTraceSingleByChannel(Hit, From, From + Dir * 5000.0f, SO_TRACE_BULLET, Params);
		Out = Hit.ImpactPoint;
		return bHit;
	};

	Player->SetViewMode(ESOViewMode::ThirdPerson);
	W.Run(0.5f);
	const UCameraComponent* Camera = Player->GetThirdPersonCamera();
	FVector Crosshair, Round;
	TestTrue(TEXT("camera centre ray hits the wall"), WallHit(Camera->GetComponentLocation(), Camera->GetForwardVector(), Crosshair));
	TestTrue(TEXT("round hits the wall"), WallHit(Player->GetAimOrigin(), Player->GetAimDirection(), Round));
	TestTrue(FString::Printf(TEXT("third person: the round lands on the crosshair (%.2f cm off)"), FVector::Dist(Crosshair, Round)),
		FVector::Dist(Crosshair, Round) < 1.0f);
	TestTrue(TEXT("the shoulder camera sits beside the head"), FMath::Abs(Player->GetActorTransform().InverseTransformPosition(Camera->GetComponentLocation()).Y) > 20.0f);

	Player->SetViewMode(ESOViewMode::FirstPerson);
	W.Run(0.1f);
	TestTrue(TEXT("first person: rounds go straight along the view"),
		Player->GetAimDirection().Equals(Player->GetEyeTransform(true).GetRotation().GetForwardVector(), 1e-4f));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSORackHandTest, "ShatteredOrbit.Weapon.ReloadHandStaysOutsideTheGun", SOTest::Flags)
bool FSORackHandTest::RunTest(const FString& Parameters)
{
	SOTest::FTestWorld W;
	ASOCharacter* Player = SOTest::SpawnArmedPlayer(W);
	ASOWeapon* Rifle = Player ? Player->GetWeapon() : nullptr;
	if (!TestNotNull(TEXT("armed player"), Rifle))
	{
		return false;
	}
	USOGunRigComponent* Rig = Rifle->GetFirstPersonRig();
	const UStaticMeshComponent* Bolt = Rig->GetPart(TEXT("bolt"));
	// Receiver + dust cover in rig space (cm): x -20..18, half width 2.3, from the mag well up to the cover's top, at the
	// rifle's real-world scale (weapons.GUN_SCALE 'gun_rifle' .82: the gun was modelled 1.2x too large).
	const float K = 0.82f;
	const FBox Receiver(FVector(-20.0f, -2.3f, 2.0f) * K, FVector(18.0f, 2.3f, 11.2f) * K);

	Rifle->SetAmmo(0, 100);
	Rifle->StartReload();
	int32 Frames = 0, Inside = 0, RackFrames = 0, RackOnTop = 0, RackOnHandle = 0;
	W.Run(Rifle->GetReloadDuration() + 0.1f, [&]()
	{
		const FSOHandGrip& Grip = Rig->GetLeftGrip();
		const FVector Palm = Grip.Wrist + Grip.Basis.GetAxisX() * 5.0f + FSOHandGrip::PalmNormal(Grip.Basis, true) * 1.3f;
		++Frames;
		if (Receiver.IsInside(Palm) || Receiver.IsInside(Grip.Wrist))
		{
			++Inside;
			const FSOReloadPose& Pose = Rifle->GetPose();
			AddInfo(FString::Printf(TEXT("inside: %s -> %s at %.2f, palm %s wrist %s"), *Pose.HandAnchorA.ToString(), *Pose.HandAnchorB.ToString(),
				Pose.HandAlpha, *Palm.ToCompactString(), *Grip.Wrist.ToCompactString()));
		}
		if (Rifle->GetPose().Bolt > 0.06f && Bolt)
		{
			++RackFrames;
			RackOnTop += Palm.Z > Receiver.Max.Z && FSOHandGrip::PalmNormal(Grip.Basis, true).Z < -0.5f ? 1 : 0;
			RackOnHandle += FMath::Abs(Palm.X - USOGunRigComponent::MeshToRig(Bolt->GetRelativeLocation()).X) < 1.5f ? 1 : 0;
		}
	});
	TestTrue(TEXT("reload ran"), Frames > 60);
	TestEqual(TEXT("frames with the off hand inside the receiver"), Inside, 0);
	TestTrue(TEXT("the rack was seen"), RackFrames > 0);
	TestEqual(TEXT("rack: palm down on top of the receiver"), RackOnTop, RackFrames);
	TestEqual(TEXT("rack: the hand rides the charging handle back"), RackOnHandle, RackFrames);
	return true;
}

#endif
