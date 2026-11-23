// The gun is steady in the eyes (the owner, 2026-11-23: "in first person the gun is constantly shaking, it's maybe the
// hands shaking that does that"). Standing still in first person, relaxed, at the ready and on the sights, the gun's
// place in the camera's picture may drift with the breath, smoothly, and never shake: frame to frame it changes by no
// more than a smooth motion does (the second difference of its place and turn, what a shake is made of).

#include "SOTestWorld.h"

#if WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR

#include "Camera/CameraComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "GameFramework/PlayerController.h"
#include "SOCharacter.h"
#include "SOGunRigComponent.h"
#include "SOInventoryComponent.h"
#include "SOLootLibrary.h"
#include "SOLootTypes.h"
#include "SOPlayerState.h"
#include "SOViewmodelComponent.h"
#include "SOWeapon.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOSteadyGunTest, "ShatteredOrbit.Hold.SteadyInTheEyes", SOTest::Flags)
bool FSOSteadyGunTest::RunTest(const FString& Parameters)
{
	if (SOTest::PlayerBodyMissing(*this))
	{
		return true;
	}
	SOTest::FTestWorld W;
	W.AddBox(FVector(-5000, -5000, -100), FVector(5000, 5000, 0));
	ASOCharacter* Player = W.SpawnCharacter(FVector(0, 0, 0));
	if (!TestNotNull(TEXT("player"), Player))
	{
		return false;
	}
	APlayerController* PC = W.World->SpawnActor<APlayerController>();
	PC->SetAsLocalPlayerController();
	FActorSpawnParameters StateParams;
	StateParams.bDeferConstruction = true;
	ASOPlayerState* PS = W.World->SpawnActor<ASOPlayerState>(ASOPlayerState::StaticClass(), FTransform::Identity, StateParams);
	PS->GetInventory()->bPersist = false;
	PS->FinishSpawning(FTransform::Identity);
	PC->PlayerState = PS;
	PC->Possess(Player);
	PC->SetControlRotation(FRotator::ZeroRotator);
	Player->GetMesh()->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
	Player->SetViewMode(ESOViewMode::FirstPerson);
	FString Only;
	FParse::Value(FCommandLine::Get(), TEXT("SOHoldOnly="), Only);
	FRandomStream Rng(3);
	// (a frame of its own length: the owner's machine is not a test world's steady 60 a second)
	float Step = SOTest::Dt;
	auto RunAt = [&](float Seconds, TFunctionRef<void()> Each)
	{
		for (int32 i = 0, n = FMath::CeilToInt(Seconds / Step); i < n; ++i)
		{
			Each();
			W.World->Tick(LEVELTICK_All, Step);
			++GFrameCounter;
		}
	};
	for (const float Rate : { 60.0f, 30.0f, 24.0f })
	for (const TCHAR* Arch : { TEXT("rifle"), TEXT("pistol"), TEXT("smg"), TEXT("sniper") })
	{
		Step = 1.0f / Rate;
		if (!Only.IsEmpty() && Only != Arch)
		{
			continue;
		}
		ASOWeapon* Gun = Player->EquipInstance(USOLootLibrary::MakeWeapon(Arch, 2, 20, Rng));
		RunAt(1.0f, [] {});
		if (!TestNotNull(FString::Printf(TEXT("%s in the hands"), Arch), Gun) || !Gun->GetRig())
		{
			continue;
		}
		for (int32 Mode = 0; Mode < 3; ++Mode)
		{
			const TCHAR* State = Mode == 0 ? TEXT("relaxed") : (Mode == 1 ? TEXT("at the ready") : TEXT("on the sights"));
			if (Mode == 0)
			{
				Player->CancelCombat();
			}
			if (Mode == 2)
			{
				Player->HandleAimPressed();
			}
			RunAt(1.2f, [&]() { if (Mode > 0) { Player->MarkCombat(); } PC->SetControlRotation(FRotator::ZeroRotator); Player->FaceRotation(PC->GetControlRotation(), Step); });
			// the gun in the camera's frame, the camera in the capsule's, every frame for two seconds
			TArray<FVector> Place, Eye, Hold, HandR, HandL;
			TArray<FRotator> Turn;
			RunAt(2.0f, [&]()
			{
				if (Mode > 0)
				{
					Player->MarkCombat();
				}
				PC->SetControlRotation(FRotator::ZeroRotator);
				Player->FaceRotation(PC->GetControlRotation(), Step);
				const FTransform Cam = Player->GetCamera()->GetComponentTransform();
				const FTransform G = Gun->GetRig()->GetComponentTransform().GetRelativeTransform(Cam);
				Place.Add(G.GetLocation());
				Turn.Add(G.Rotator());
				Eye.Add(Player->GetActorTransform().InverseTransformPosition(Cam.GetLocation()));
				Hold.Add(Player->GetActorTransform().InverseTransformPosition(Gun->GetRig()->GetComponentLocation()));
				// (the hands on the gun, in the gun's own frame: the owner thought it might be the hands)
				const FTransform& RigT = Gun->GetRig()->GetComponentTransform();
				HandR.Add(RigT.InverseTransformPosition(Player->GetMesh()->GetBoneLocation(TEXT("hand_R"))));
				HandL.Add(RigT.InverseTransformPosition(Player->GetMesh()->GetBoneLocation(TEXT("hand_L"))));
			});
			// a shake: the second difference (how much the frame's step differs from the one before)
			float ShakePlace = 0.0f, ShakeTurn = 0.0f, ShakeEye = 0.0f, ShakeHold = 0.0f, Drift = 0.0f, ShakeHands = 0.0f;
			for (int32 i = 2; i < Place.Num(); ++i)
			{
				ShakePlace = FMath::Max(ShakePlace, static_cast<float>((Place[i] - 2.0 * Place[i - 1] + Place[i - 2]).Size()));
				const FRotator D2 = (Turn[i] - Turn[i - 1]).GetNormalized() - (Turn[i - 1] - Turn[i - 2]).GetNormalized();
				ShakeTurn = FMath::Max(ShakeTurn, FMath::Abs(D2.Pitch) + FMath::Abs(D2.Yaw) + FMath::Abs(D2.Roll));
				ShakeEye = FMath::Max(ShakeEye, static_cast<float>((Eye[i] - 2.0 * Eye[i - 1] + Eye[i - 2]).Size()));
				ShakeHold = FMath::Max(ShakeHold, static_cast<float>((Hold[i] - 2.0 * Hold[i - 1] + Hold[i - 2]).Size()));
				Drift = FMath::Max(Drift, static_cast<float>((Place[i] - Place[0]).Size()));
				ShakeHands = FMath::Max(ShakeHands, static_cast<float>(FMath::Max((HandR[i] - 2.0 * HandR[i - 1] + HandR[i - 2]).Size(),
					(HandL[i] - 2.0 * HandL[i - 1] + HandL[i - 2]).Size())));
			}
			AddInfo(FString::Printf(TEXT("STEADY %.0f fps %s %s: gun in the picture shakes %.3f cm / %.3f deg a frame (drift %.2f cm); the camera on the capsule %.3f, the gun on the capsule %.3f; the hands on the gun %.3f"),
				Rate, Arch, State, ShakePlace, ShakeTurn, Drift, ShakeEye, ShakeHold, ShakeHands));
			// (a millimetre of jerk a frame at most: the breath's own motion is a third of that; the camera's shake was 80)
			TestTrue(FString::Printf(TEXT("%.0f fps, %s %s: the gun is steady in the picture (%.3f cm, %.3f deg of shake a frame)"), Rate, Arch, State, ShakePlace, ShakeTurn),
				ShakePlace < 0.1f && ShakeTurn < 0.1f);
			TestTrue(FString::Printf(TEXT("%.0f fps, %s %s: the hands are steady on the gun (%.3f cm of shake a frame)"), Rate, Arch, State, ShakeHands), ShakeHands < 0.1f);
			if (Mode == 2)
			{
				Player->HandleAimReleased();
				RunAt(0.5f, [] {});
			}
		}
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOHeadShadowTest, "ShatteredOrbit.Camera.HeadKeepsItsShadow", SOTest::Flags)
bool FSOHeadShadowTest::RunTest(const FString& Parameters)
{
	// One body seen from its own eyes (the owner, 2026-11-23: its shadow had no head): its own player's camera does not
	// see the head (its face, eyes and lashes cut out of that picture by their materials, the hair worn on it hidden from
	// that camera), and the head is whole for the shadow and for every other camera: never shrunk into its joint.
	if (SOTest::PlayerBodyMissing(*this))
	{
		return true;
	}
	SOTest::FTestWorld W;
	W.AddBox(FVector(-3000, -3000, -100), FVector(3000, 3000, 0));
	ASOCharacter* Player = W.SpawnCharacter(FVector(0, 0, 0));
	if (!TestNotNull(TEXT("player"), Player))
	{
		return false;
	}
	APlayerController* PC = W.World->SpawnActor<APlayerController>();
	PC->SetAsLocalPlayerController();
	FActorSpawnParameters StateParams;
	StateParams.bDeferConstruction = true;
	ASOPlayerState* PS = W.World->SpawnActor<ASOPlayerState>(ASOPlayerState::StaticClass(), FTransform::Identity, StateParams);
	PS->GetInventory()->bPersist = false;
	PS->FinishSpawning(FTransform::Identity);
	PC->PlayerState = PS;
	PC->Possess(Player);
	PC->SetViewTarget(Player);
	USkeletalMeshComponent* Body = Player->GetMesh();
	Body->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
	Player->SetViewMode(ESOViewMode::FirstPerson);
	W.Run(1.0f);
	TestTrue(TEXT("first person: the head is hidden from its own camera"), Player->IsHeadHidden());
	if (!TestTrue(TEXT("the male's head parts are hidden by their materials"), Player->IsHeadHiddenByMaterial()))
	{
		return false;
	}
	const TArray<float>& Data = Body->GetCustomPrimitiveData().Data;
	TestTrue(TEXT("the body tells its head parts to stay out of its own camera's picture"), Data.Num() > 0 && Data[0] > 0.5f);
	const FVector HeadScale = Body->GetBoneTransform(Body->GetBoneIndex(TEXT("head"))).GetScale3D();
	TestTrue(FString::Printf(TEXT("the head is whole, for its shadow (scale %.2f)"), HeadScale.X), HeadScale.X > 0.9f);
	if (const USkeletalMeshComponent* Hair = Player->GetWornPiece(TEXT("hair")))
	{
		TestTrue(TEXT("the hair is hidden from its own camera"), Hair->bOwnerNoSee);
		TestTrue(TEXT("and still casts its shadow"), Hair->bCastHiddenShadow);
	}
	// the camera out behind the shoulder: the whole head seen
	Player->SetViewMode(ESOViewMode::ThirdPerson);
	W.Run(1.0f);
	TestFalse(TEXT("third person: the head is seen"), Player->IsHeadHidden());
	TestTrue(TEXT("third person: the head parts are in the picture"), Body->GetCustomPrimitiveData().Data.Num() > 0 && Body->GetCustomPrimitiveData().Data[0] < 0.5f);
	if (const USkeletalMeshComponent* Hair = Player->GetWornPiece(TEXT("hair")))
	{
		TestFalse(TEXT("third person: the hair is seen"), Hair->bOwnerNoSee);
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOSmoothOnTheMoveTest, "ShatteredOrbit.Hold.SmoothOnTheMove", SOTest::Flags)
bool FSOSmoothOnTheMoveTest::RunTest(const FString& Parameters)
{
	// First person, off the sights, the gun in the picture walking and the camera turning with the mouse (the owner,
	// 2026-11-23: "when in first person not scoped and walking the guns shake too much ... when moving the mouse in first
	// person not zoomed the camera seems too wobbly instead of smooth"): how far the gun moves in the picture, how hard
	// its motion jerks from frame to frame, and how far the camera itself moves while only the view turns (MOVE lines).
	if (SOTest::PlayerBodyMissing(*this))
	{
		return true;
	}
	SOTest::FTestWorld W;
	W.AddBox(FVector(-20000, -20000, -100), FVector(20000, 20000, 0));
	ASOCharacter* Player = W.SpawnCharacter(FVector(0, 0, 0));
	if (!TestNotNull(TEXT("player"), Player))
	{
		return false;
	}
	APlayerController* PC = W.World->SpawnActor<APlayerController>();
	PC->SetAsLocalPlayerController();
	FActorSpawnParameters StateParams;
	StateParams.bDeferConstruction = true;
	ASOPlayerState* PS = W.World->SpawnActor<ASOPlayerState>(ASOPlayerState::StaticClass(), FTransform::Identity, StateParams);
	PS->GetInventory()->bPersist = false;
	PS->FinishSpawning(FTransform::Identity);
	PC->PlayerState = PS;
	PC->Possess(Player);
	PC->SetControlRotation(FRotator::ZeroRotator);
	Player->GetMesh()->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
	Player->SetViewMode(ESOViewMode::FirstPerson);
	FRandomStream Rng(5);
	for (const TCHAR* Arch : { TEXT("rifle"), TEXT("pistol") })
	{
		ASOWeapon* Gun = Player->EquipInstance(USOLootLibrary::MakeWeapon(Arch, 2, 20, Rng));
		W.Run(1.0f);
		if (!TestNotNull(FString::Printf(TEXT("%s in the hands"), Arch), Gun) || !Gun->GetRig())
		{
			continue;
		}
		for (int32 Case = 0; Case < 3; ++Case)
		{
			const TCHAR* What = Case == 0 ? TEXT("walking") : (Case == 1 ? TEXT("walking at the ready") : TEXT("turning the view"));
			Player->CancelCombat();
			float Yaw = PC->GetControlRotation().Yaw;
			auto Each = [&](float T)
			{
				if (Case == 1)
				{
					Player->MarkCombat();
				}
				if (Case < 2)
				{
					Player->AddMovementInput(Player->GetActorForwardVector(), 1.0f);
				}
				else
				{
					// a hand on a mouse: 120 degrees a second, never quite even
					Yaw += (120.0f + 60.0f * FMath::Sin(T * 7.0f)) * SOTest::Dt;
				}
				PC->SetControlRotation(FRotator(0.0f, Yaw, 0.0f));
				Player->FaceRotation(PC->GetControlRotation(), SOTest::Dt);
			};
			float T = 0.0f;
			W.Run(1.0f, [&]() { Each(T); T += SOTest::Dt; });
			TArray<FVector> Place, Eye;
			W.Run(2.0f, [&]()
			{
				Each(T);
				T += SOTest::Dt;
				const FTransform Cam = Player->GetCamera()->GetComponentTransform();
				Place.Add(Gun->GetRig()->GetComponentTransform().GetRelativeTransform(Cam).GetLocation());
				Eye.Add(Player->GetActorTransform().InverseTransformPosition(Cam.GetLocation()));
			});
			FBox PlaceBox(ForceInit), EyeBox(ForceInit);
			float Step = 0.0f, Jerk = 0.0f, EyeStep = 0.0f, EyeJerk = 0.0f;
			for (int32 i = 0; i < Place.Num(); ++i)
			{
				PlaceBox += Place[i];
				EyeBox += Eye[i];
				if (i >= 1)
				{
					Step = FMath::Max(Step, static_cast<float>((Place[i] - Place[i - 1]).Size()));
					EyeStep = FMath::Max(EyeStep, static_cast<float>((Eye[i] - Eye[i - 1]).Size()));
				}
				if (i >= 2)
				{
					Jerk = FMath::Max(Jerk, static_cast<float>((Place[i] - 2.0 * Place[i - 1] + Place[i - 2]).Size()));
					EyeJerk = FMath::Max(EyeJerk, static_cast<float>((Eye[i] - 2.0 * Eye[i - 1] + Eye[i - 2]).Size()));
				}
			}
			const FVector Sway = PlaceBox.GetSize(), EyeSway = EyeBox.GetSize();
			AddInfo(FString::Printf(TEXT("MOVE %s %s: the gun in the picture sways %.1f x %.1f x %.1f cm, steps %.2f cm, jerks %.3f cm a frame; the camera on the capsule sways %.1f x %.1f x %.1f, steps %.2f, jerks %.3f"),
				Arch, What, Sway.X, Sway.Y, Sway.Z, Step, Jerk, EyeSway.X, EyeSway.Y, EyeSway.Z, EyeStep, EyeJerk));
			// (walking, the gun in the picture jerked half a centimetre a frame before the owner's word, 0.02 after; turning
			// the view, the camera swung 3-4 cm side to side round the neck, none after)
			if (Case < 2)
			{
				TestTrue(FString::Printf(TEXT("%s %s: the gun in the picture jerks %.3f cm a frame (under 0.1)"), Arch, What, Jerk), Jerk < 0.1f);
				TestTrue(FString::Printf(TEXT("%s %s: the gun in the picture sways %.1f cm up and down (under 1.5)"), Arch, What, Sway.Z), Sway.Z < 1.5f);
			}
			else
			{
				TestTrue(FString::Printf(TEXT("%s %s: the camera moves %.2f cm side to side on the capsule (under 0.5)"), Arch, What, EyeSway.Y), EyeSway.Y < 0.5f);
			}
		}
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOGunInThePictureTest, "ShatteredOrbit.Hold.GunInThePicture", SOTest::Flags)
bool FSOGunInThePictureTest::RunTest(const FString& Parameters)
{
	// The gun is seen from the eyes (the owner, 2026-11-23: "weapons are not very visible, i think the camera is too high
	// so lower it a bit maybe so we see more of the gun when idle/walking"): first person, standing and walking, relaxed
	// and at the ready, a gun of every class has 15 % or more of it in the picture (most have a third to a half) (points through its bounds, a 16:9
	// picture at the camera's own field of view). Carried low across the body when relaxed none of it was.
	if (SOTest::PlayerBodyMissing(*this))
	{
		return true;
	}
	SOTest::FTestWorld W;
	W.AddBox(FVector(-20000, -20000, -100), FVector(20000, 20000, 0));
	ASOCharacter* Player = W.SpawnCharacter(FVector(0, 0, 0));
	if (!TestNotNull(TEXT("player"), Player))
	{
		return false;
	}
	APlayerController* PC = W.World->SpawnActor<APlayerController>();
	PC->SetAsLocalPlayerController();
	FActorSpawnParameters StateParams;
	StateParams.bDeferConstruction = true;
	ASOPlayerState* PS = W.World->SpawnActor<ASOPlayerState>(ASOPlayerState::StaticClass(), FTransform::Identity, StateParams);
	PS->GetInventory()->bPersist = false;
	PS->FinishSpawning(FTransform::Identity);
	PC->PlayerState = PS;
	PC->Possess(Player);
	PC->SetControlRotation(FRotator::ZeroRotator);
	Player->GetMesh()->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
	Player->SetViewMode(ESOViewMode::FirstPerson);
	// how much of the gun is in the picture: points through its bounds, in the camera's frame
	auto InPicture = [&](const ASOWeapon* Gun)
	{
		const USOGunRigComponent* Rig = Gun ? Gun->GetRig() : nullptr;
		if (!Rig || !Rig->IsBuilt() || !Player->GetViewmodel())
		{
			return 0.0f;
		}
		const FTransform Cam = Player->GetCamera()->GetComponentTransform();
		const float TanX = FMath::Tan(FMath::DegreesToRadians(Player->GetCamera()->FieldOfView * 0.5f)), TanY = TanX * 9.0f / 16.0f;
		const FBox B = Rig->GetRigBounds();
		const FTransform T = Player->GetViewmodel()->GetComponentTransform();
		int32 In = 0, All = 0;
		for (int32 i = 0; i <= 15; ++i)
		{
			for (int32 j = 0; j <= 2; ++j)
			{
				for (int32 k = 0; k <= 2; ++k)
				{
					const FVector P = Cam.InverseTransformPosition(T.TransformPosition(FVector(FMath::Lerp(B.Min.X, B.Max.X, i / 15.0),
						FMath::Lerp(B.Min.Y, B.Max.Y, j / 2.0), FMath::Lerp(B.Min.Z, B.Max.Z, k / 2.0))));
					++All;
					In += P.X > 1.0 && FMath::Abs(P.Y / P.X) <= TanX && FMath::Abs(P.Z / P.X) <= TanY ? 1 : 0;
				}
			}
		}
		return 100.0f * In / FMath::Max(All, 1);
	};
	FRandomStream Rng(17);
	for (const TCHAR* Arch : { TEXT("rifle"), TEXT("smg"), TEXT("pistol"), TEXT("shotgun"), TEXT("hmg"), TEXT("sniper"), TEXT("rocket") })
	{
		Player->SetActorLocation(FVector(0.0f, 0.0f, 92.0f));
		PC->SetControlRotation(FRotator::ZeroRotator);
		ASOWeapon* Gun = Player->EquipInstance(USOLootLibrary::MakeWeapon(Arch, 2, 20, Rng));
		if (!TestNotNull(FString::Printf(TEXT("%s in the hands"), Arch), Gun))
		{
			continue;
		}
		auto Face = [&]() { Player->FaceRotation(PC->GetControlRotation(), SOTest::Dt); };
		Player->CancelCombat();
		W.Run(1.6f, Face);
		const float RelaxedStill = InPicture(Gun);
		float RelaxedWalk = 100.0f;
		W.Run(0.9f, [&]() { Player->AddMovementInput(Player->GetActorForwardVector(), 1.0f); Face(); RelaxedWalk = FMath::Min(RelaxedWalk, InPicture(Gun)); });
		W.Run(0.6f, Face);
		Player->MarkCombat();
		W.Run(1.0f, [&]() { Player->MarkCombat(); Face(); });
		const float ReadyStill = InPicture(Gun);
		float ReadyWalk = 100.0f;
		W.Run(0.9f, [&]() { Player->MarkCombat(); Player->AddMovementInput(Player->GetActorForwardVector(), 1.0f); Face(); ReadyWalk = FMath::Min(ReadyWalk, InPicture(Gun)); });
		AddInfo(FString::Printf(TEXT("GUNSEEN %s: relaxed %.0f %% standing, %.0f %% walking at least; at the ready %.0f %% standing, %.0f %% walking at least"),
			Arch, RelaxedStill, RelaxedWalk, ReadyStill, ReadyWalk));
		TestTrue(FString::Printf(TEXT("%s relaxed: %.0f %% of the gun in the picture standing, %.0f %% walking (15 at least)"), Arch, RelaxedStill, RelaxedWalk),
			RelaxedStill >= 15.0f && RelaxedWalk >= 15.0f);
		TestTrue(FString::Printf(TEXT("%s at the ready: %.0f %% of the gun in the picture standing, %.0f %% walking (15 at least)"), Arch, ReadyStill, ReadyWalk),
			ReadyStill >= 15.0f && ReadyWalk >= 15.0f);
		Player->CancelCombat();
		W.Run(0.3f, Face);
	}
	return true;
}

#endif
