// The gun is steady in the eyes (the owner, 2026-11-23: "in first person the gun is constantly shaking, it's maybe the
// hands shaking that does that"). Standing still in first person, relaxed, at the ready and on the sights, the gun's
// place in the camera's picture may drift with the breath, smoothly, and never shake: frame to frame it changes by no
// more than a smooth motion does (the second difference of its place and turn, what a shake is made of).

#include "SOTestWorld.h"

#if WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR

#include "Camera/CameraComponent.h"
#include "Camera/CameraTypes.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "GameFramework/PlayerController.h"
#include "SOCharacter.h"
#include "SOCharacterMovementComponent.h"
#include "SOGunRigComponent.h"
#include "SOGameUserSettings.h"
#include "Engine/Engine.h"
#include "SOInventoryComponent.h"
#include "SOLootLibrary.h"
#include "SOLootTypes.h"
#include "SOPlayerState.h"
#include "SOViewmodelComponent.h"
#include "SOWeapon.h"
#include "SOWeaponData.h"

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

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOSteadyAtAnyFovTest, "ShatteredOrbit.Camera.SteadyAtAnyFov", SOTest::Flags)
bool FSOSteadyAtAnyFovTest::RunTest(const FString& Parameters)
{
	// The picture holds still and the gun stays framed whatever the field of view and the frame rate (the owner,
	// 2026-11-23: "the screen shakes again since we moved the camera again, this fix should be automated because what if
	// we have a fov slider in the game settings"). First person at 75, 95 and 110 degrees, 60 and 30 frames a second:
	// standing at the ready, a hand on the mouse (small turns every frame), walking, onto the sights and off them. In
	// PIXELS of a 1920 x 1080 picture, as the player sees it: the gun's sight frame to frame (its second difference: a
	// shake turns back every frame) and the camera on the body; and the long guns framed (their sight's height in the
	// picture). FOVSTEADY lines.
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
	Player->GetMesh()->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
	Player->SetViewMode(ESOViewMode::FirstPerson);
	USOGameUserSettings* Settings = Cast<USOGameUserSettings>(GEngine ? GEngine->GetGameUserSettings() : nullptr);
	if (!TestNotNull(TEXT("the game's settings"), Settings))
	{
		return false;
	}
	const float FovBefore = Settings->FieldOfView;
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
	// a point in the picture (pixels of 1920 x 1080 at the camera's own field of view)
	auto Pixel = [&](const FVector& World)
	{
		const FTransform Cam = Player->GetCamera()->GetComponentTransform();
		const FVector L = Cam.InverseTransformPosition(World);
		const float TanH = FMath::Tan(FMath::DegreesToRadians(Player->GetCamera()->FieldOfView * 0.5f)), TanV = TanH * 9.0f / 16.0f;
		const float F = FMath::Max(static_cast<float>(L.X), 1.0f);
		return FVector2D(960.0 * (1.0 + L.Y / (F * TanH)), 540.0 * (1.0 - L.Z / (F * TanV)));
	};
	FRandomStream Rng(9), Hand(11);
	for (const float Fov : { 75.0f, 95.0f, 110.0f })
	for (const float Rate : { 60.0f, 30.0f })
	for (const TCHAR* Arch : { TEXT("rifle"), TEXT("smg"), TEXT("pistol") })
	{
		Settings->FieldOfView = Fov;
		Step = 1.0f / Rate;
		Player->SetActorLocation(FVector(0.0f, 0.0f, 92.0f));
		PC->SetControlRotation(FRotator::ZeroRotator);
		ASOWeapon* Gun = Player->EquipInstance(USOLootLibrary::MakeWeapon(Arch, 2, 20, Rng));
		if (!TestNotNull(FString::Printf(TEXT("%s in the hands"), Arch), Gun) || !Gun->GetRig())
		{
			continue;
		}
		const bool bLong = !Gun->GetRig()->IsHandgun();
		float Yaw = 0.0f, Pitch = 0.0f, YawRate = 0.0f, PitchRate = 0.0f;
		auto Face = [&]() { PC->SetControlRotation(FRotator(Pitch, Yaw, 0.0f)); Player->MarkCombat(); Player->FaceRotation(PC->GetControlRotation(), Step); };
		RunAt(2.5f, Face);
		const float AdsTime = Gun->GetData() ? Gun->GetData()->AdsTime : 0.24f;
		static const TCHAR* Names[] = { TEXT("standing at the ready"), TEXT("a hand on the mouse"), TEXT("starting to walk"), TEXT("walking"),
			TEXT("onto the sights"), TEXT("off the sights") };
		for (int32 Case = 0; Case < 6; ++Case)
		{
			if (Case == 4)
			{
				RunAt(1.2f, Face);                                           // (stopped, settled)
				Player->HandleAimPressed();
			}
			if (Case == 5)
			{
				Player->HandleAimReleased();
			}
			const bool bWalk = Case == 2 || Case == 3;
			TArray<FVector2D> Sight;
			TArray<FVector> Eye;
			RunAt(Case == 2 || Case >= 4 ? 0.6f : 1.5f, [&]()
			{
				if (Case == 1)
				{
					// (a hand's small corrections: the turn's rate wanders a few degrees a second either way, changing a few
					// times a second, never white noise a frame)
					const float Ease = 1.0f - FMath::Exp(-6.0f * Step);
					YawRate += (Hand.FRandRange(-6.0f, 6.0f) - YawRate) * Ease;
					PitchRate += (Hand.FRandRange(-4.0f, 4.0f) - PitchRate) * Ease;
					Yaw += YawRate * Step;
					Pitch = FMath::Clamp(Pitch + PitchRate * Step, -2.0f, 2.0f);
				}
				if (bWalk)
				{
					Player->AddMovementInput(Player->GetActorForwardVector(), 1.0f);
				}
				Face();
				Sight.Add(Pixel(Gun->GetRig()->GetComponentTransform().TransformPosition(USOGunRigComponent::MeshToRig(Gun->GetSightLocation()))));
				Eye.Add(Player->GetActorTransform().InverseTransformPosition(Player->GetCamera()->GetComponentLocation()));
			});
			float SightJerk = 0.0f, EyeJerk = 0.0f, SightWay = 0.0f, EyeWay = 0.0f;
			for (int32 k = 2; k < Sight.Num(); ++k)
			{
				SightJerk = FMath::Max(SightJerk, static_cast<float>((Sight[k] - 2.0 * Sight[k - 1] + Sight[k - 2]).Size()));
				EyeJerk = FMath::Max(EyeJerk, static_cast<float>((Eye[k] - 2.0 * Eye[k - 1] + Eye[k - 2]).Size()));
			}
			// A SHAKE turns back and forth: on any axis the motion reversing three times within a fifth of a second (above a
			// whisker of motion a frame), whatever its size; a sway, a slide or a lean does not
			auto Shakes = [&](auto Get, int32 Axes, float Whisker)
			{
				int32 Worst = 0;
				for (int32 Ax = 0; Ax < Axes; ++Ax)
				{
					TArray<int32> Turns;
					for (int32 k = 2; k < Sight.Num(); ++k)
					{
						const float A = Get(k - 1, Ax) - Get(k - 2, Ax), B = Get(k, Ax) - Get(k - 1, Ax);
						if (FMath::Abs(A) > Whisker && FMath::Abs(B) > Whisker && A * B < 0.0f)
						{
							Turns.Add(k);
						}
					}
					const int32 Window = FMath::Max(FMath::RoundToInt(0.2f * Rate), 3);
					for (int32 t = 0; t < Turns.Num(); ++t)
					{
						int32 n = 1;
						while (t + n < Turns.Num() && Turns[t + n] - Turns[t] <= Window)
						{
							++n;
						}
						Worst = FMath::Max(Worst, n);
					}
				}
				return Worst;
			};
			const int32 SightTurns = Shakes([&](int32 k, int32 Ax) { return static_cast<float>(Ax == 0 ? Sight[k].X : Sight[k].Y); }, 2, 1.0f * 60.0f / Rate);
			const int32 EyeTurns = Shakes([&](int32 k, int32 Ax) { return static_cast<float>(Eye[k][Ax]); }, 3, 0.05f * 60.0f / Rate);
			for (int32 k = 1; k < Sight.Num(); ++k)
			{
				SightWay = FMath::Max(SightWay, static_cast<float>((Sight[k] - Sight[0]).Size()));
				EyeWay = FMath::Max(EyeWay, static_cast<float>((Eye[k] - Eye[0]).Size()));
			}
			const float Down = Sight.Num() > 0 ? static_cast<float>(Sight.Last().Y / 1080.0) : 0.0f;
			const float Across = Sight.Num() > 0 ? static_cast<float>(Sight.Last().X / 1920.0) : 0.0f;
			const FString Label = FString::Printf(TEXT("FOV %.0f, %.0f fps, %s %s"), Fov, Rate, Arch, Names[Case]);
			AddInfo(FString::Printf(TEXT("FOVSTEADY %s: the sight jerks %.2f px a frame at most (moves %.0f px, turns back %d times in a fifth of a second at most), sits %.0f %% across, %.0f %% down the picture; the camera on the body jerks %.3f cm (moves %.1f cm, turns back %d times)"),
				*Label, SightJerk, SightWay, SightTurns, 100.0f * Across, 100.0f * Down, EyeJerk, EyeWay, EyeTurns));
			TestTrue(FString::Printf(TEXT("%s: the picture does not shake (the sight turns back %d times, the camera %d, in a fifth of a second)"), *Label, SightTurns, EyeTurns),
				SightTurns < 3 && EyeTurns < 3);
			if (Case == 0 && Rate == 60.0f)
			{
				const FTransform Cam = Player->GetCamera()->GetComponentTransform();
				const FVector S = Cam.InverseTransformPosition(Gun->GetRig()->GetComponentTransform().TransformPosition(USOGunRigComponent::MeshToRig(Gun->GetSightLocation())));
				AddInfo(FString::Printf(TEXT("FRAMING %s FOV %.0f: the sight %.1f ahead, %.1f right, %.1f up of the camera; the camera %.1f back, %.1f right, %.1f down of the eyes"),
					Arch, Fov, S.X, S.Y, S.Z, Player->GetFrameBack(), Player->GetFrameSide(), Player->GetFrameDrop()));
			}
			if (Case <= 1 || Case == 3)
			{
				// (steady: standing, turning by hand or walking along, the gun's sight in the picture turns no harder than 6 px a
				// frame at 60 frames a second, nor the camera on the body 1.5 mm: the same motion at 30 frames a second turns 4
				// times as far a frame)
				const float PerFrame = FMath::Square(60.0f / Rate);
				TestTrue(FString::Printf(TEXT("%s: the gun steady in the picture (%.2f px of jerk a frame, %.1f at most)"), *Label, SightJerk, 6.0f * PerFrame), SightJerk < 6.0f * PerFrame);
				TestTrue(FString::Printf(TEXT("%s: the camera steady on the body (%.3f cm of jerk a frame, %.2f at most)"), *Label, EyeJerk, 0.15f * PerFrame), EyeJerk < 0.15f * PerFrame);
			}
			else
			{
				// (a move, not a shake: onto the sights, off them, the body leaning into a walk, the picture and the camera
				// turn within four times as hard as an eased slide of the same length over the move's time, the aim's or the
				// walk's lean (a slide eased in and out turns at most 6 x its length / its frames squared a frame; coming onto
				// the sights the sight's own perspective quickens as the camera nears it, and the view zooms), whatever the
				// field of view and the frame rate; a shake turns back every frame)
				const float Frames = FMath::Max((Case == 2 ? 0.2f : AdsTime) * Rate, 2.0f);      // (the body leans into a walk in a fifth of a second)
				const float SightMost = 4.0f * 6.0f * SightWay / FMath::Square(Frames) + 3.0f;
				const float EyeMost = 4.0f * 6.0f * EyeWay / FMath::Square(Frames) + 0.05f;
				TestTrue(FString::Printf(TEXT("%s: the gun moves smoothly in the picture (%.2f px of jerk a frame, %.2f at most)"), *Label, SightJerk, SightMost),
					SightJerk <= SightMost);
				TestTrue(FString::Printf(TEXT("%s: the camera moves smoothly on the body (%.3f cm of jerk a frame, %.3f at most)"), *Label, EyeJerk, EyeMost),
					EyeJerk <= EyeMost);
			}
			if (Case == 0)
			{
				// (framed: the sight near its class's place in the picture whatever the field of view, the long guns as the
				// handguns are: FSOStance::FrameDown / FrameAcross; the camera goes at most 5 cm under the eyes (the owner,
				// 2026-11-23: "it feels like the player is very short"), so narrow, a long gun is seen nearer the picture's foot)
				TestTrue(FString::Printf(TEXT("%s: the gun framed in the picture (its sight %.0f %% across, %.0f %% down)"), *Label, 100.0f * Across, 100.0f * Down),
					Down > 0.55f && Down < (Fov < 90.0f ? 0.93f : 0.8f) && Across > 0.45f && Across < (bLong ? (Fov < 90.0f ? 0.9f : 0.78f) : 0.65f));
			}
		}
	}
	Settings->FieldOfView = FovBefore;
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOSmoothThroughEveryMoveTest, "ShatteredOrbit.Movement.SmoothThroughEveryMove", SOTest::Flags)
bool FSOSmoothThroughEveryMoveTest::RunTest(const FString& Parameters)
{
	// Every move the body makes, from its own eyes (the owner, 2026-11-24: "movement and gunplay are the most important and
	// core part of our game ... do 5 passes of the movement"): setting off and stopping, a strafe turned the other way, the
	// sprint begun and let go, a jump with its take-off, its hang and its landing, a slide in and out, a dodge, crouching and
	// standing again. For each, how hard the camera's place on the capsule jerks from frame to frame and how hard the gun
	// jerks in the picture (EVERYMOVE lines; a jerk is the second difference a frame at 60 frames a second): a move may
	// carry the view and the gun far, never in a jolt.
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
	USOCharacterMovementComponent* Move = Player->GetSOMovement();
	FRandomStream Rng(9);
	ASOWeapon* Gun = Player->EquipInstance(USOLootLibrary::MakeWeapon(TEXT("rifle"), 2, 20, Rng));
	W.Run(1.0f);
	if (!TestNotNull(TEXT("rifle in the hands"), Gun) || !Gun->GetRig())
	{
		return false;
	}
	FVector Stick = FVector::ZeroVector;
	auto Frame = [&]()
	{
		Player->MarkCombat();                   // (at the ready throughout: the fight's own state)
		if (!Stick.IsNearlyZero())
		{
			Player->AddMovementInput(Player->GetActorTransform().TransformVectorNoScale(Stick), 1.0f);
		}
		Player->FaceRotation(PC->GetControlRotation(), SOTest::Dt);
	};
	// one move: what to do as it begins and how long to watch it. Measured each frame from the view the player is given
	// (UCameraComponent::GetCameraView: the view's own roll, lean and width are in it): the gun in that picture (its grip and
	// a point 50 cm out along it, so a turn of it shows too), the view's place over the FEET (the capsule's middle jumps
	// as it shrinks for a crouch or a slide; the feet do not), its turn against the aim and its width.
	// (-SOMoveTrace=<part of a move's name>, or all: every frame of those moves as MOVETRACE lines)
	FString TraceMoves;
	FParse::Value(FCommandLine::Get(), TEXT("SOMoveTrace="), TraceMoves);
	struct FWorst { const TCHAR* What; float Gun; float Eye; float Turn; float Fov; int32 GunFlips; int32 EyeFlips; };
	TArray<FWorst> Worst;
	auto Measure = [&](const TCHAR* What, TFunctionRef<void()> Begin, float Seconds)
	{
		Begin();
		const bool bTrace = !TraceMoves.IsEmpty() && (TraceMoves == TEXT("all") || FString(What).Contains(TraceMoves));
		TArray<FVector> Grip, Front, Eye, Turn, Fov;
		W.Run(Seconds, [&]()
		{
			Frame();
			FMinimalViewInfo View;
			Player->GetCamera()->GetCameraView(SOTest::Dt, View);
			const FTransform Cam(View.Rotation, View.Location);
			const FTransform InPicture = Gun->GetRig()->GetComponentTransform().GetRelativeTransform(Cam);
			Grip.Add(InPicture.GetLocation());
			Front.Add(InPicture.TransformPosition(FVector(50.0f, 0.0f, 0.0f)));
			const float Half = Player->GetCapsuleComponent()->GetScaledCapsuleHalfHeight();
			Eye.Add(Player->GetActorTransform().InverseTransformPosition(View.Location) + FVector(0.0f, 0.0f, Half));
			const FRotator Feel = (PC->GetControlRotation().Quaternion().Inverse() * View.Rotation.Quaternion()).Rotator();
			Turn.Add(FVector(Feel.Pitch, Feel.Yaw, Feel.Roll));
			Fov.Add(FVector(View.FOV, 0.0f, 0.0f));
			if (bTrace)
			{
				const FVector V = Player->GetVelocity();
				// (the head and the firing shoulder over the feet too: the camera follows the one, the gun the other)
				const FVector Feet(0.0f, 0.0f, Half);
				const FVector Head = Player->GetActorTransform().InverseTransformPosition(Player->GetMesh()->GetBoneLocation(TEXT("head"))) + Feet;
				const FVector Shoulder = Player->GetActorTransform().InverseTransformPosition(Player->GetMesh()->GetBoneLocation(TEXT("upperarm_R"))) + Feet;
				// (each hand's reach: the wrist's distance from its shoulder over the arm's length, the hands' limits in it)
				auto ReachOf = [&](const TCHAR* Up, const TCHAR* Fore, const TCHAR* Hand)
				{
					const FVector S = Player->GetMesh()->GetBoneLocation(Up), E = Player->GetMesh()->GetBoneLocation(Fore), H = Player->GetMesh()->GetBoneLocation(Hand);
					return static_cast<float>(FVector::Dist(S, H) / FMath::Max(FVector::Dist(S, E) + FVector::Dist(E, H), 1.0));
				};
				const float ReachR = ReachOf(TEXT("upperarm_R"), TEXT("forearm_R"), TEXT("hand_R")), ReachL = ReachOf(TEXT("upperarm_L"), TEXT("forearm_L"), TEXT("hand_L"));
				AddInfo(FString::Printf(TEXT("MOVETRACE %s %d: grip %s front %s eye %s turn %s fov %.2f | speed %.0f vz %.0f feet %.1f %s%s | head %s shoulder %s | reach %.3f %.3f"),
					What, Grip.Num(), *Grip.Last().ToCompactString(), *Front.Last().ToCompactString(), *Eye.Last().ToCompactString(),
					*Turn.Last().ToCompactString(), View.FOV, V.Size2D(), V.Z, Player->GetActorLocation().Z - Half,
					Move->IsMovingOnGround() ? TEXT("ground") : TEXT("air"), Player->bIsCrouched ? TEXT(" crouched") : TEXT(""),
					*Head.ToCompactString(), *Shoulder.ToCompactString(), ReachR, ReachL));
			}
		});
		auto JerkOf = [](const TArray<FVector>& P)
		{
			float J = 0.0f;
			for (int32 i = 2; i < P.Num(); ++i)
			{
				J = FMath::Max(J, static_cast<float>((P[i] - 2.0 * P[i - 1] + P[i - 2]).Size()));
			}
			return J;
		};
		// (a JOLT: on any axis the motion turned back on itself between one frame and the next while going at speed both
		// ways, half a centimetre a frame or more, 30 cm a second: a smooth reversal passes through rest, a jolt does not)
		auto FlipsOf = [](const TArray<FVector>& P, float Fast)
		{
			int32 N = 0;
			for (int32 i = 2; i < P.Num(); ++i)
			{
				for (int32 Ax = 0; Ax < 3; ++Ax)
				{
					const double A = P[i - 1][Ax] - P[i - 2][Ax], B = P[i][Ax] - P[i - 1][Ax];
					if (A * B < 0.0 && FMath::Min(FMath::Abs(A), FMath::Abs(B)) > Fast)
					{
						++N;
					}
				}
			}
			return N;
		};
		auto SpanOf = [](const TArray<FVector>& P)
		{
			FBox B(ForceInit);
			for (const FVector& V : P)
			{
				B += V;
			}
			return static_cast<float>(B.GetSize().Size());
		};
		const float GunJerk = FMath::Max(JerkOf(Grip), JerkOf(Front)), EyeJerk = JerkOf(Eye), TurnJerk = JerkOf(Turn), FovJerk = JerkOf(Fov);
		const int32 GunFlips = FMath::Max(FlipsOf(Grip, 0.5f), FlipsOf(Front, 0.5f)), EyeFlips = FlipsOf(Eye, 0.5f);
		AddInfo(FString::Printf(TEXT("EVERYMOVE %s: the gun in the picture moves %.1f cm (its front %.1f), jerks %.3f cm a frame, jolts %d; the view over the feet moves %.1f cm, jerks %.3f, jolts %d; its own turn %.1f deg, jerks %.3f; its width %.1f deg, jerks %.3f"),
			What, SpanOf(Grip), SpanOf(Front), GunJerk, GunFlips, SpanOf(Eye), EyeJerk, EyeFlips, SpanOf(Turn), TurnJerk, SpanOf(Fov), FovJerk));
		Worst.Add({ What, GunJerk, EyeJerk, TurnJerk, FovJerk, GunFlips, EyeFlips });
	};
	W.Run(0.8f, Frame);
	Measure(TEXT("setting off"), [&]() { Stick = FVector(1, 0, 0); }, 0.8f);
	Measure(TEXT("stopping"), [&]() { Stick = FVector::ZeroVector; }, 0.8f);
	Measure(TEXT("strafing right"), [&]() { Stick = FVector(0, 1, 0); }, 0.6f);
	Measure(TEXT("the strafe turned left"), [&]() { Stick = FVector(0, -1, 0); }, 0.8f);
	Measure(TEXT("stopping a strafe"), [&]() { Stick = FVector::ZeroVector; }, 0.6f);
	Measure(TEXT("into a sprint"), [&]() { Stick = FVector(1, 0, 0); Move->SetWantsToSprint(true); }, 1.2f);
	Measure(TEXT("the sprint let go"), [&]() { Move->SetWantsToSprint(false); }, 0.8f);
	Measure(TEXT("a jump: the take-off and the hang"), [&]() { Move->SetWantsToMantle(true); Player->Jump(); }, 0.45f);
	Measure(TEXT("a jump: the landing"), [&]() { Move->SetWantsToMantle(false); Player->StopJumping(); }, 0.9f);
	Measure(TEXT("into a slide"), [&]() { Move->SetWantsToSprint(true); }, 0.9f);
	Measure(TEXT("the slide"), [&]() { Player->Crouch(); }, 0.9f);
	Measure(TEXT("out of the slide"), [&]() { Move->SetWantsToSprint(false); Player->UnCrouch(); }, 0.9f);
	Measure(TEXT("a dodge"), [&]() { Stick = FVector(0, -1, 0); Move->SetWantsToDodge(true); }, 0.7f);
	Measure(TEXT("crouching"), [&]() { Stick = FVector::ZeroVector; Player->Crouch(); }, 0.7f);
	Measure(TEXT("standing up"), [&]() { Player->UnCrouch(); }, 0.7f);
	// What may never happen in any move: a JOLT (the gun in the picture or the view turning back on itself between two
	// frames while going at speed both ways). And how hard either may lurch in a frame at 60 frames a second: a big move done
	// quickly needs some (a slide drops the view 60 cm in a fifth of a second; the sprint's carry swings the gun's front 47
	// cm in as long), a jump in its pose does not: before these passes a landing snapped the view 19 cm in a frame, and the
	// gun jolted 4-8 cm a frame into a sprint and out of it, a jump, a slide and a crouch (17 jolts in these 15 moves).
	for (const FWorst& M : Worst)
	{
		TestTrue(FString::Printf(TEXT("%s: the gun in the picture never jolts (%d)"), M.What, M.GunFlips), M.GunFlips == 0);
		TestTrue(FString::Printf(TEXT("%s: the view never jolts (%d)"), M.What, M.EyeFlips), M.EyeFlips == 0);
		TestTrue(FString::Printf(TEXT("%s: the gun in the picture lurches %.2f cm a frame at most (under 4)"), M.What, M.Gun), M.Gun < 4.0f);
		TestTrue(FString::Printf(TEXT("%s: the view over the feet lurches %.2f cm a frame at most (under 4)"), M.What, M.Eye), M.Eye < 4.0f);
		TestTrue(FString::Printf(TEXT("%s: the view's own turn changes %.3f degrees a frame at most (under 0.15)"), M.What, M.Turn), M.Turn < 0.15f);
		TestTrue(FString::Printf(TEXT("%s: its width changes %.3f degrees a frame at most (under 0.15)"), M.What, M.Fov), M.Fov < 0.15f);
	}
	return true;
}

#endif
