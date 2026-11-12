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
#include "SOLocomotionAnimInstance.h"
#include "SOCharacterMovementComponent.h"
#include "SOInventoryComponent.h"
#include "SOLootLibrary.h"
#include "SOLootTypes.h"
#include "Engine/StaticMesh.h"
#include "StaticMeshResources.h"
#include "SOPlayerState.h"

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
	if (SOTest::PlayerBodyMissing(*this))
	{
		return true;
	}
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
			// (the hands are fitted to the gun: each wrist moves a little from the rig's own target onto its surfaces)
			const USOLocomotionAnimInstance* Anim = Cast<USOLocomotionAnimInstance>(Bodies[i]->GetAnimInstance());
			const FTransform RigT = Rigs[i]->GetComponentTransform();
			const FVector FitR = Anim ? RigT.TransformVector(Anim->GetFittedOffset(false)) : FVector::ZeroVector;
			const FVector FitL = Anim && !Rifle->IsReloading() ? RigT.TransformVector(Anim->GetFittedOffset(true)) : FVector::ZeroVector;
			const float DR = FVector::Dist(Bodies[i]->GetBoneLocation(TEXT("hand_R")), Right.GetLocation() + FitR);
			const float DL = FVector::Dist(Bodies[i]->GetBoneLocation(TEXT("hand_L")), Left.GetLocation() + FitL);
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
	TestTrue(FString::Printf(TEXT("sight in front of the eye (%.1f cm)"), Sight.X), Sight.X > 6.0f);
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

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOEverySightTest, "ShatteredOrbit.Aim.EverySightOnTheEyeLine", SOTest::Flags)
bool FSOEverySightTest::RunTest(const FString& Parameters)
{
	// Every gun with every sight it may carry (the owner: "the bullets don't even hit where the scope is ... test
	// scopes", "a sniper scope on a shotgun makes no sense"). Rounds leave along the eye's axis, so: aimed, the sight's
	// point lies on that axis and stays there through a burst; an optic's glass is centred on it, ahead of the eye;
	// and what a gun may carry follows its kind.
	const USOLootTables* Tables = USOLootLibrary::GetTables();
	if (!TestNotNull(TEXT("loot tables"), Tables))
	{
		return false;
	}
	SOTest::FTestWorld W;
	W.AddBox(FVector(-4000, -4000, -100), FVector(4000, 4000, 0));
	ASOCharacter* Player = W.SpawnCharacter(FVector(0, 0, 0));
	W.Run(0.3f);
	FRandomStream Rng(7);
	for (const FSOArchetypeEntry& Entry : Tables->Archetypes)
	{
		const USOWeaponData* Data = Entry.Data.LoadSynchronous();
		if (!Data)
		{
			continue;
		}
		const FString Gun = Entry.Id.ToString();
		const bool bHandgun = Data->MuzzleLocation.Y < 35.0f;
		const bool bPrecise = !Data->bAutomatic && Data->Burst == 0 && Data->Pellets <= 1 && !bHandgun && Data->Spread <= 0.3f;
		TestTrue(*FString::Printf(TEXT("%s: its own sight is one it may carry"), *Gun), Data->Sights.Contains(Data->DefaultSight));
		for (const FName SightId : Data->Sights)
		{
			const FString Name = FString::Printf(TEXT("%s + %s"), *Gun, *SightId.ToString());
			const FSOSightInfo* Sight = Tables->FindSight(SightId);
			if (!TestNotNull(*FString::Printf(TEXT("%s: the sight is in the table"), *Name), Sight))
			{
				continue;
			}
			// the rules: no glass on a handgun or a shotgun, long glass only on a precise single-shot rifle
			TestFalse(*FString::Printf(TEXT("%s: no magnified optic on a handgun, a shotgun or a launcher"), *Name),
				Sight->bScope && (bHandgun || Data->Pellets > 1 || Data->Projectile == ESOProjectileKind::Rocket));
			TestFalse(*FString::Printf(TEXT("%s: glass over 4x only on a precise rifle"), *Name), Sight->Zoom > 4.5f && !bPrecise);

			FSOWeaponInstance Copy = USOLootLibrary::MakeWeapon(Entry.Id, 2, 20, Rng);
			Copy.Sight = SightId;
			ASOWeapon* Weapon = Player->EquipInstance(Copy);
			if (!TestNotNull(*FString::Printf(TEXT("%s equips"), *Name), Weapon))
			{
				continue;
			}
			TestEqual(*FString::Printf(TEXT("%s: the copy keeps the sight"), *Name), Weapon->GetInstance().Sight, SightId);
			Player->HandleAimPressed();
			W.Run(0.9f);
			const USOGunRigComponent* Rig = Weapon->GetFirstPersonRig();
			const auto SightOff = [&]()
			{
				const FVector At = Player->GetEyeTransform(true).InverseTransformPosition(
					Rig->GetComponentTransform().TransformPosition(USOGunRigComponent::MeshToRig(Weapon->GetSightLocation())));
				return FVector2D(At.Y, At.Z).Size();
			};
			TestTrue(*FString::Printf(TEXT("%s: aimed, the sight is on the eye's axis (%.2f cm off)"), *Name, SightOff()), SightOff() < 0.05f);
			if (const UStaticMeshComponent* Optic = Rig->GetOptic(); Optic && Optic->GetStaticMesh())
			{
				// the glass (every `gun_lens*` section of the optic): centred on the axis, ahead of the eye
				const UStaticMesh* Mesh = Optic->GetStaticMesh();
				const FStaticMeshLODResources& LOD = Mesh->GetRenderData()->LODResources[0];
				const FIndexArrayView Indices = LOD.IndexBuffer.GetArrayView();
				FBox Glass(ForceInit);
				const FTransform ToEye = Optic->GetComponentTransform() * Player->GetEyeTransform(true).Inverse();
				for (const FStaticMeshSection& Section : LOD.Sections)
				{
					if (!Mesh->GetStaticMaterials().IsValidIndex(Section.MaterialIndex)
						|| !Mesh->GetStaticMaterials()[Section.MaterialIndex].MaterialSlotName.ToString().StartsWith(TEXT("gun_lens")))
					{
						continue;
					}
					for (uint32 i = Section.FirstIndex; i < Section.FirstIndex + Section.NumTriangles * 3; ++i)
					{
						Glass += ToEye.TransformPosition(FVector(LOD.VertexBuffers.PositionVertexBuffer.VertexPosition(Indices[i])));
					}
				}
				if (TestTrue(*FString::Printf(TEXT("%s: the optic has glass"), *Name), Glass.IsValid != 0))
				{
					const FVector C = Glass.GetCenter(), E = Glass.GetExtent();
					TestTrue(*FString::Printf(TEXT("%s: the glass is centred on the eye's axis (%.2f cm right, %.2f cm up)"), *Name, C.Y, C.Z),
						FMath::Abs(C.Y) < 0.3f && FMath::Abs(C.Z) < 0.3f);
					TestTrue(*FString::Printf(TEXT("%s: the glass is ahead of the eye (%.1f to %.1f cm)"), *Name, Glass.Min.X, Glass.Max.X), Glass.Min.X > 1.0f);
					// what the eye gets to look through: the window's half height seen from the eye (a reflex or a holo is a
					// window to look THROUGH: the owner's still showed a black box with a slot in it)
					if (!Sight->bScope)
					{
						const float Wide = FMath::RadiansToDegrees(FMath::Atan2(E.Y, FMath::Max(Glass.Min.X, 1.0)));
						const float High = FMath::RadiansToDegrees(FMath::Atan2(E.Z, FMath::Max(Glass.Min.X, 1.0)));
						// (on a handgun it is held out at arm's length: a smaller frame)
						const float Least = bHandgun ? 0.6f : 1.0f;
						TestTrue(*FString::Printf(TEXT("%s: the window is at least %.1f degrees wide and %.1f high (%.1f x %.1f)"), *Name, 11.0f * Least, 7.5f * Least,
							Wide * 2.0f, High * 2.0f), Wide >= 5.5f * Least && High >= 3.75f * Least);
					}
				}
			}
			if (Data->Projectile != ESOProjectileKind::Rocket)
			{
				// what the shooter was looking at as each round left (a bolt worked afterwards takes the gun off the eye:
				// that is the action, not the aim)
				float Worst = 0.0f, Before = SightOff();
				int32 Shots = Weapon->GetShotsFired();
				Weapon->StartFire();
				W.Run(0.45f, [&]()
				{
					if (Weapon->GetShotsFired() != Shots)
					{
						Worst = FMath::Max(Worst, Before);
						Shots = Weapon->GetShotsFired();
					}
					Before = SightOff();
				});
				Weapon->StopFire();
				TestTrue(*FString::Printf(TEXT("%s: the sight is on the axis as every round leaves (%.2f cm off at most)"), *Name, Worst), Worst < 0.3f);
			}
			Player->HandleAimReleased();
			W.Run(0.25f);
		}
	}
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

namespace SOTest
{
	USOWeaponData* LoadGun(const TCHAR* Name)
	{
		return LoadObject<USOWeaponData>(nullptr, *FString::Printf(TEXT("/Game/Weapons/%s/DA_%s.DA_%s"), Name, Name, Name));
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOThirdPersonShoulderTest, "ShatteredOrbit.Hold.ThirdPersonShouldered", SOTest::Flags)
bool FSOThirdPersonShoulderTest::RunTest(const FString& Parameters)
{
	if (SOTest::PlayerBodyMissing(*this))
	{
		return true;
	}
	SOTest::FTestWorld W;
	ASOCharacter* Player = SOTest::SpawnArmedPlayer(W);
	if (!TestNotNull(TEXT("player"), Player))
	{
		return false;
	}
	Player->SetViewMode(ESOViewMode::ThirdPerson);
	USkeletalMeshComponent* Body = Player->GetMesh();
	for (const TCHAR* Name : { TEXT("Rifle"), TEXT("Bolt"), TEXT("Dmr"), TEXT("Sniper"), TEXT("Pistol") })
	{
		USOWeaponData* Data = SOTest::LoadGun(Name);
		if (!TestNotNull(FString::Printf(TEXT("%s data"), Name), Data))
		{
			continue;
		}
		ASOWeapon* Gun = Player->EquipWeapon(Data);
		W.Run(0.7f);
		const bool bHandgun = Gun->GetThirdPersonRig()->IsHandgun();
		for (int32 Pass = 0; Pass < 2; ++Pass)
		{
			if (Pass == 1)
			{
				Player->HandleAimPressed();
				W.Run(0.8f);
			}
			const TCHAR* When = Pass ? TEXT("aimed") : TEXT("hip");
			const USOGunRigComponent* Rig = Gun->GetThirdPersonRig();
			const FTransform R = Rig->GetComponentTransform();
			const FBox B = Rig->GetRigBounds();
			// the head (a 9 cm ball round the skull's middle) never meets the gun
			const FVector Head = Body->GetBoneLocation(TEXT("head")) + FVector(0.0f, 0.0f, 9.0f);
			const float Clear = FMath::Sqrt(B.ComputeSquaredDistanceToPoint(R.InverseTransformPosition(Head)));
			TestTrue(FString::Printf(TEXT("%s %s: the gun stays clear of the head (%.1f cm)"), Name, When, Clear), Clear > 9.0f);
			// below the eyes, never at head height
			const float Below = Player->GetEyeTransform(false).GetLocation().Z - R.GetLocation().Z;
			TestTrue(FString::Printf(TEXT("%s %s: held below the eyes (%.1f cm)"), Name, When, Below), Below > 10.0f);
			if (!bHandgun)
			{
				// the butt in the right shoulder pocket
				const FVector Butt = R.TransformPosition(FVector(B.Min.X, 0.0f, 0.0f));
				const float ToShoulder = FVector::Dist(Butt, Body->GetBoneLocation(TEXT("upperarm_R")));
				// (the pocket is ~11 cm from the joint; a long forend draws the gun in toward the chest a little more)
				TestTrue(FString::Printf(TEXT("%s %s: butt at the shoulder (%.1f cm from the joint)"), Name, When, ToShoulder), ToShoulder < 17.0f);
				const float Right = Player->GetActorTransform().InverseTransformPosition(Butt).Y;
				TestTrue(FString::Printf(TEXT("%s %s: on the right side (%.1f cm)"), Name, When, Right), Right > 5.0f);
			}
			// both hands still on the gun
			FTransform HR, HL;
			if (Rig->GetHandTargets(HR, HL))
			{
				// (each wrist is moved from the rig's own target onto this gun's surfaces: the fitted grip)
				const USOLocomotionAnimInstance* Anim = Cast<USOLocomotionAnimInstance>(Body->GetAnimInstance());
				const FVector FitR = Anim ? R.TransformVector(Anim->GetFittedOffset(false)) : FVector::ZeroVector;
				const FVector FitL = Anim && !Gun->IsReloading() ? R.TransformVector(Anim->GetFittedOffset(true)) : FVector::ZeroVector;
				const float OffR = FVector::Dist(Body->GetBoneLocation(TEXT("hand_R")), HR.GetLocation() + FitR);
				TestTrue(FString::Printf(TEXT("%s %s: firing hand on the grip (%.1f cm off)"), Name, When, OffR), OffR < 1.5f);
				const float Off = FVector::Dist(Body->GetBoneLocation(TEXT("hand_L")), HL.GetLocation() + FitL);
				TestTrue(FString::Printf(TEXT("%s %s: support hand on the gun (%.1f cm off)"), Name, When, Off), Off < 2.5f);
			}
		}
		Player->HandleAimReleased();
		W.Run(0.4f);
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOScopeZoomTest, "ShatteredOrbit.Aim.ScopesZoom", SOTest::Flags)
bool FSOScopeZoomTest::RunTest(const FString& Parameters)
{
	SOTest::FTestWorld W;
	ASOCharacter* Player = SOTest::SpawnArmedPlayer(W);
	if (!TestNotNull(TEXT("player"), Player))
	{
		return false;
	}
	const float Hip = Player->GetHipFov();
	for (const TCHAR* Name : { TEXT("Sniper"), TEXT("Bolt"), TEXT("Dmr") })
	{
		USOWeaponData* Data = SOTest::LoadGun(Name);
		if (!TestNotNull(FString::Printf(TEXT("%s data"), Name), Data))
		{
			continue;
		}
		ASOWeapon* Gun = Player->EquipWeapon(Data);
		W.Run(0.6f);
		TestTrue(FString::Printf(TEXT("%s is scoped"), Name), Gun->IsScoped());
		const float Zoom = Gun->GetStats().Zoom;
		TestTrue(FString::Printf(TEXT("%s magnifies (%.1fx)"), Name, Zoom), Zoom >= 4.0f);
		for (const ESOViewMode Mode : { ESOViewMode::FirstPerson, ESOViewMode::ThirdPerson })
		{
			Player->SetViewMode(Mode);
			Player->HandleAimPressed();
			W.Run(0.9f);
			const TCHAR* View = Mode == ESOViewMode::FirstPerson ? TEXT("first person") : TEXT("third person");
			TestEqual(FString::Printf(TEXT("%s, %s: the eye zooms by the magnification"), Name, View),
				Player->GetFirstPersonCamera()->FieldOfView, Hip / Zoom, 0.2f);
			TestTrue(FString::Printf(TEXT("%s, %s: the shoulder camera never zooms onto the back"), Name, View),
				Player->GetThirdPersonCamera()->FieldOfView >= Hip / Player->ThirdPersonMaxZoom - 0.2f);
			Player->HandleAimReleased();
			W.Run(0.5f);
			TestEqual(FString::Printf(TEXT("%s, %s: unscoped back to the hip view"), Name, View), Player->GetFirstPersonCamera()->FieldOfView, Hip, 0.5f);
		}
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOFittedGripTest, "ShatteredOrbit.Hold.FittedGrip", SOTest::Flags)
bool FSOFittedGripTest::RunTest(const FString& Parameters)
{
	// Every kind of gun: the hands are fitted to its own shape. The firing hand is seated on the grip (the wrist moved
	// onto the backstrap, never further than the solver allows) and closes round it: the ring and little finger wrap.
	if (SOTest::PlayerBodyMissing(*this))
	{
		return true;
	}
	SOTest::FTestWorld W;
	ASOCharacter* Player = SOTest::SpawnArmedPlayer(W);
	if (!TestNotNull(TEXT("player"), Player))
	{
		return false;
	}
	for (const TCHAR* Arch : { TEXT("rifle"), TEXT("auto"), TEXT("smg"), TEXT("sidearm"), TEXT("handcannon"), TEXT("shotgun"), TEXT("sniper"),
		TEXT("hmg"), TEXT("rocket"), TEXT("vr_rifle"), TEXT("vr_pistol"), TEXT("vr_lmg") })
	{
		FRandomStream Rng(FCrc::StrCrc32(Arch));
		Player->EquipInstance(USOLootLibrary::MakeWeapon(Arch, 2, 20, Rng));
		W.Run(0.5f);
		const USOLocomotionAnimInstance* Anim = Cast<USOLocomotionAnimInstance>(Player->GetMesh()->GetAnimInstance());
		if (!TestTrue(FString::Printf(TEXT("%s: the hands were fitted"), Arch), Anim && Anim->HasFittedGrip()))
		{
			continue;
		}
		const FSOFingerPose& Hand = Anim->GetFittedFingers(false);
		TestTrue(FString::Printf(TEXT("%s: the ring finger wraps the grip (%.0f + %.0f deg)"), Arch, Hand.Curl[2][0], Hand.Curl[2][1]), Hand.Curl[2][0] + Hand.Curl[2][1] > 70.0f);
		TestTrue(FString::Printf(TEXT("%s: the little finger wraps the grip (%.0f + %.0f deg)"), Arch, Hand.Curl[3][0], Hand.Curl[3][1]), Hand.Curl[3][0] + Hand.Curl[3][1] > 40.0f);   // (a flared grip base stops it early: it rests on the base)
		TestTrue(FString::Printf(TEXT("%s: the firing wrist moved %.1f cm onto the grip (at most 6)"), Arch, Anim->GetFittedOffset(false).Size()), Anim->GetFittedOffset(false).Size() <= 6.05f);
		TestTrue(FString::Printf(TEXT("%s: the support palm moved %.1f cm onto the gun (at most 3)"), Arch, Anim->GetFittedOffset(true).Size()), Anim->GetFittedOffset(true).Size() <= 3.05f);
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOHolstersTest, "ShatteredOrbit.Hold.Holsters", SOTest::Flags)
bool FSOHolstersTest::RunTest(const FString& Parameters)
{
	// The loadout is worn: of the three equipped guns one is in the hands, the long gun of the others across the back,
	// the handgun at the hip; they change places when another slot is drawn, and the gun in hand goes to its holster
	// while the hands are busy on a climb.
	if (SOTest::PlayerBodyMissing(*this))
	{
		return true;
	}
	SOTest::FTestWorld W;
	W.AddBox(FVector(-4000, -4000, -100), FVector(4000, 4000, 0));
	W.AddBox(FVector(150, -300, 0), FVector(450, 300, 200));
	ASOCharacter* Player = W.SpawnCharacter(FVector(0, 0, 0));
	FActorSpawnParameters Params;
	Params.bDeferConstruction = true;
	ASOPlayerState* PS = W.World->SpawnActor<ASOPlayerState>(ASOPlayerState::StaticClass(), FTransform::Identity, Params);
	PS->GetInventory()->bPersist = false;
	PS->FinishSpawning(FTransform::Identity);
	Player->SetPlayerState(PS);
	USOInventoryComponent* Inv = PS->GetInventory();
	for (const TCHAR* Arch : { TEXT("rifle"), TEXT("sidearm"), TEXT("hmg") })
	{
		FRandomStream Rng(FCrc::StrCrc32(Arch));
		Inv->AddWeapon(USOLootLibrary::MakeWeapon(Arch, 2, 20, Rng), false);
	}
	Player->BindInventory();
	Inv->SelectSlot(0);
	W.Run(0.6f);
	if (!TestNotNull(TEXT("the rifle in hand"), Player->GetWeapon()))
	{
		return false;
	}
	TestNull(TEXT("the slot in hand is not worn"), Player->GetHolsteredRig(0));
	const USOGunRigComponent* Hip = Player->GetHolsteredRig(1);
	const USOGunRigComponent* Back = Player->GetHolsteredRig(2);
	if (TestNotNull(TEXT("the sidearm is worn"), Hip) && TestNotNull(TEXT("the heavy gun is worn"), Back))
	{
		TestTrue(TEXT("the sidearm hangs from the right thigh"), Hip->IsHandgun() && Hip->GetAttachSocketName() == TEXT("thigh_R"));
		TestTrue(TEXT("the heavy gun rides on the chest's bone"), !Back->IsHandgun() && Back->GetAttachSocketName() == TEXT("chest"));
		const FTransform ToBody = Player->GetMesh()->GetComponentTransform();
		const FVector BackAt = ToBody.InverseTransformPosition(Back->GetComponentLocation());
		const FVector HipAt = ToBody.InverseTransformPosition(Hip->GetComponentLocation());
		TestTrue(FString::Printf(TEXT("it is behind the back (%.0f cm behind the body's middle)"), -BackAt.Y), BackAt.Y < -9.0f);
		TestTrue(FString::Printf(TEXT("the sidearm is at the right hip (%.0f cm to the right, %.0f cm up)"), -HipAt.X, HipAt.Z), HipAt.X < -12.0f && HipAt.Z > 70.0f && HipAt.Z < 110.0f);
		TestTrue(TEXT("the heavy gun's muzzle points up over a shoulder"), ToBody.InverseTransformVector(Back->GetForwardVector()).Z > 0.7f);
		TestTrue(TEXT("the sidearm's muzzle points down"), ToBody.InverseTransformVector(Hip->GetForwardVector()).Z < -0.7f);
	}
	TestEqual(TEXT("the sidearm's place"), Player->GetHolsterPlace(1), FName(TEXT("hip_right")));
	TestEqual(TEXT("the heavy gun's place (the free side of the back)"), Player->GetHolsterPlace(2), FName(TEXT("back_right")));
	// what a worn gun covers (all its parts, world space)
	auto Covers = [](const USOGunRigComponent* Rig)
	{
		FBox Box(ForceInit);
		TArray<USceneComponent*> Parts;
		if (Rig)
		{
			Rig->GetChildrenComponents(true, Parts);
		}
		for (const USceneComponent* Part : Parts)
		{
			if (const UStaticMeshComponent* Mesh = Cast<UStaticMeshComponent>(Part); Mesh && Mesh->GetStaticMesh() && Mesh->IsVisible())
			{
				Box += Mesh->Bounds.GetBox();
			}
		}
		return Box;
	};
	// draw the sidearm: the rifle goes onto the back, beside the heavy gun, never on top of it
	Inv->SelectSlot(1);
	W.Run(0.6f);
	TestNull(TEXT("the sidearm left its holster"), Player->GetHolsteredRig(1));
	TestNotNull(TEXT("the rifle is on the back"), Player->GetHolsteredRig(0));
	TestNotNull(TEXT("the heavy gun stays on the back"), Player->GetHolsteredRig(2));
	TestEqual(TEXT("the rifle's place (the primary's home)"), Player->GetHolsterPlace(0), FName(TEXT("back_right")));
	TestEqual(TEXT("the heavy gun moved to the other shoulder"), Player->GetHolsterPlace(2), FName(TEXT("back_left")));
	{
		const FBox A = Covers(Player->GetHolsteredRig(0)).ExpandBy(-0.5f);
		const FBox B = Covers(Player->GetHolsteredRig(2)).ExpandBy(-0.5f);
		TestTrue(TEXT("both back guns are there"), A.IsValid && B.IsValid);
		// side by side: their bore lines a good hand apart, each inside the shoulders' width
		const FTransform Mesh = Player->GetMesh()->GetComponentTransform();
		const float LineR = static_cast<float>(Mesh.InverseTransformPosition(Player->GetHolsteredRig(0)->GetComponentLocation()).X);
		const float LineL = static_cast<float>(Mesh.InverseTransformPosition(Player->GetHolsteredRig(2)->GetComponentLocation()).X);
		TestTrue(FString::Printf(TEXT("the two guns on the back sit side by side (bore lines %.0f cm right and %.0f cm left of the spine)"), -LineR, LineL),
			LineR < -6.0f && LineL > 6.0f && LineR > -14.0f && LineL < 14.0f);
		const FTransform ToBody = Player->GetMesh()->GetComponentTransform();
		const float Right = static_cast<float>(ToBody.InverseTransformPosition(A.GetCenter()).X);
		const float Left = static_cast<float>(ToBody.InverseTransformPosition(B.GetCenter()).X);
		TestTrue(FString::Printf(TEXT("one behind each shoulder (%.0f cm right of the spine, %.0f cm left)"), -Right, Left), Right < -3.0f && Left > 3.0f);
	}
	// switching round and round leaves nothing behind: the body carries exactly the two guns that are not in hand
	{
		auto GunMeshes = [Player]()
		{
			int32 N = 0;
			TArray<UStaticMeshComponent*> All;
			Player->GetComponents(All);
			for (const UStaticMeshComponent* M : All)
			{
				N += M->GetStaticMesh() != nullptr && M->IsRegistered();
			}
			return N;
		};
		const int32 Before = GunMeshes();
		for (int32 Round = 0; Round < 3; ++Round)
		{
			for (const int32 Slot : { 0, 2, 1 })
			{
				Inv->SelectSlot(Slot);
				W.Run(0.5f);
			}
		}
		TestEqual(TEXT("after nine switches the body carries no more gun parts than before"), GunMeshes(), Before);
		TestTrue(TEXT("and wears the two guns not in hand"), Player->GetHolsteredRig(0) && Player->GetHolsteredRig(2) && !Player->GetHolsteredRig(1));
	}
	// a climb: the gun in hand is stowed for as long as it lasts
	USOCharacterMovementComponent* Move = Player->GetSOMovement();
	bool bMantled = false, bStowed = false, bWornWhileClimbing = false;
	Move->SetWantsToMantle(true);
	W.Run(2.5f, [&]
	{
		if (Move->IsMantling())
		{
			bMantled = true;
			bStowed |= Player->IsWeaponStowed();
			bWornWhileClimbing |= Player->GetHolsteredRig(1) != nullptr;
		}
		if (!bMantled || Move->IsMantling())
		{
			Player->AddMovementInput(FVector::ForwardVector, 1.0f);
		}
	});
	Move->SetWantsToMantle(false);
	W.Run(0.4f);
	TestTrue(TEXT("climbed the block"), bMantled);
	TestTrue(TEXT("the gun in hand was stowed for the climb"), bStowed && bWornWhileClimbing);
	TestTrue(TEXT("and is back in the hands after it"), !Player->IsWeaponStowed() && Player->GetHolsteredRig(1) == nullptr);
	// three long guns: each still has a place of its own (the third lies across the two on the back)
	{
		for (const TCHAR* Arch : { TEXT("shotgun") })
		{
			FRandomStream Rng(FCrc::StrCrc32(Arch));
			const FSOWeaponInstance Added = Inv->AddWeapon(USOLootLibrary::MakeWeapon(Arch, 2, 20, Rng), false);
			Inv->Equip(Added.Uid);
		}
		Inv->SelectSlot(2);
		W.Run(0.6f);
		TestEqual(TEXT("three long guns, heavy in hand: the primary behind the right shoulder"), Player->GetHolsterPlace(0), FName(TEXT("back_right")));
		TestEqual(TEXT("the special behind the left"), Player->GetHolsterPlace(1), FName(TEXT("back_left")));
		TestTrue(TEXT("and the heavy in the hands"), Player->GetHolsterPlace(2).IsNone() && Player->GetHolsteredRig(2) == nullptr);
		const FTransform Mesh = Player->GetMesh()->GetComponentTransform();
		TestTrue(TEXT("on either side of the spine"), Mesh.InverseTransformPosition(Player->GetHolsteredRig(0)->GetComponentLocation()).X < -6.0f
			&& Mesh.InverseTransformPosition(Player->GetHolsteredRig(1)->GetComponentLocation()).X > 6.0f);
	}
	return true;
}

#endif
