// Automation tests: Session Frontend > Automation, filter "ShatteredOrbit", or headless:
// UnrealEditor-Cmd.exe ShatteredOrbit.uproject -ExecCmds="Automation RunTests ShatteredOrbit; Quit" -unattended -nullrhi

#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "Camera/CameraComponent.h"
#include "Components/BoxComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkyAtmosphereComponent.h"
#include "Engine/DirectionalLight.h"
#include "Engine/Engine.h"
#include "Engine/ExponentialHeightFog.h"
#include "Engine/Level.h"
#include "Engine/PostProcessVolume.h"
#include "Engine/SkyLight.h"
#include "Engine/World.h"
#include "Engine/CollisionProfile.h"
#include "GameFramework/PlayerStart.h"
#include "GameFramework/SpringArmComponent.h"
#include "GameFramework/WorldSettings.h"
#include "HAL/IConsoleManager.h"
#include "InputAction.h"
#include "InputMappingContext.h"
#include "SOCharacter.h"
#include "SOCharacterMovementComponent.h"
#include "SOGameMode.h"
#include "SOGameUserSettings.h"
#include "SOLookComponent.h"
#include "SOTimeOfDaySubsystem.h"

#include "SOTestWorld.h"


// ---------------------------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOMovementDefaultsTest, "ShatteredOrbit.Movement.Defaults", SOTest::Flags)
bool FSOMovementDefaultsTest::RunTest(const FString& Parameters)
{
	const USOCharacterMovementComponent* Move = GetDefault<USOCharacterMovementComponent>();
	TestEqual(TEXT("walk speed"), Move->MaxWalkSpeed, 440.0f);
	TestEqual(TEXT("sprint speed"), Move->SprintSpeed, 860.0f);
	TestEqual(TEXT("crouch speed"), Move->MaxWalkSpeedCrouched, 270.0f);
	TestEqual(TEXT("coyote time"), Move->CoyoteTime, 0.12f);
	TestEqual(TEXT("jump buffer"), Move->JumpBufferTime, 0.12f);
	TestEqual(TEXT("mantle min"), Move->MantleMinHeight, 50.0f);
	TestEqual(TEXT("mantle max"), Move->MantleMaxHeight, 245.0f);

	const ASOCharacter* Character = GetDefault<ASOCharacter>();
	TestTrue(TEXT("character uses the SO movement component"), Character->GetSOMovement() != nullptr);
	const float EyeFromFeet = Character->GetFirstPersonCamera()->GetRelativeLocation().Z + Character->GetCapsuleComponent()->GetUnscaledCapsuleHalfHeight();
	TestEqual(TEXT("eye height ~165 cm"), EyeFromFeet, 165.0f, 1.0f);
	TestTrue(TEXT("third-person boom collides"), Character->GetThirdPersonBoom()->bDoCollisionTest);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOMovementSpeedsTest, "ShatteredOrbit.Movement.Speeds", SOTest::Flags)
bool FSOMovementSpeedsTest::RunTest(const FString& Parameters)
{
	SOTest::FTestWorld W;
	W.AddBox(FVector(-20000, -20000, -100), FVector(20000, 20000, 0));
	ASOCharacter* C = W.SpawnCharacter(FVector(0, 0, 0));
	if (!TestNotNull(TEXT("character"), C))
	{
		return false;
	}
	USOCharacterMovementComponent* Move = C->GetSOMovement();
	W.Run(0.3f);
	TestTrue(TEXT("lands on the floor"), Move->IsMovingOnGround());

	auto Forward = [C] { C->AddMovementInput(FVector::ForwardVector, 1.0f); };

	W.Run(1.0f, Forward);
	TestEqual(TEXT("walk speed reached"), static_cast<float>(Move->Velocity.Size2D()), 440.0f, 5.0f);

	Move->SetWantsToSprint(true);
	W.Run(1.0f, Forward);
	TestTrue(TEXT("sprinting"), Move->IsSprinting());
	TestEqual(TEXT("sprint speed reached"), static_cast<float>(Move->Velocity.Size2D()), 860.0f, 5.0f);

	// Sprint is forward only.
	auto Sideways = [C] { C->AddMovementInput(FVector::RightVector, 1.0f); };
	W.Run(1.0f, Sideways);
	TestFalse(TEXT("no sprint sideways"), Move->IsSprinting());
	TestEqual(TEXT("sideways falls back to walk speed"), static_cast<float>(Move->Velocity.Size2D()), 440.0f, 5.0f);

	// Crouch at sprint speed: slide (boost, then friction decay, then crouch walk).
	W.Run(1.0f, Forward);
	C->Crouch();
	W.Run(4.0f * SOTest::Dt, Forward);
	TestTrue(TEXT("crouching at sprint speed slides"), Move->IsSliding());
	TestTrue(TEXT("slide boost"), Move->Velocity.Size2D() > 880.0f);
	W.Run(1.2f, Forward);
	TestFalse(TEXT("slide ends"), Move->IsSliding());
	TestTrue(TEXT("still crouched after the slide"), C->bIsCrouched);
	W.Run(1.0f, Forward);
	TestEqual(TEXT("crouch speed"), static_cast<float>(Move->Velocity.Size2D()), 270.0f, 5.0f);

	// Jump: ~1 m apex, lands again.
	C->UnCrouch();
	Move->SetWantsToSprint(false);
	W.Run(0.5f);
	const float StartZ = C->GetActorLocation().Z;
	float ApexZ = StartZ;
	C->Jump();
	W.Step();
	C->StopJumping();
	W.Run(1.2f, [C, &ApexZ] { ApexZ = FMath::Max(ApexZ, static_cast<float>(C->GetActorLocation().Z)); });
	TestEqual(TEXT("jump apex ~98 cm"), ApexZ - StartZ, 98.0f, 8.0f);
	TestTrue(TEXT("landed after the jump"), Move->IsMovingOnGround());
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOMovementCoyoteTest, "ShatteredOrbit.Movement.CoyoteTime", SOTest::Flags)
bool FSOMovementCoyoteTest::RunTest(const FString& Parameters)
{
	for (const float Delay : { 0.05f, 0.3f })
	{
		SOTest::FTestWorld W;
		W.AddBox(FVector(-3000, -1000, -100), FVector(0, 1000, 0));       // platform ending at x = 0
		W.AddBox(FVector(-3000, -3000, -2100), FVector(6000, 3000, -2000)); // far below
		ASOCharacter* C = W.SpawnCharacter(FVector(-200, 0, 0));
		USOCharacterMovementComponent* Move = C->GetSOMovement();
		W.Run(0.3f);

		int32 Guard = 0;
		while (!Move->IsFalling() && Guard++ < 300)
		{
			C->AddMovementInput(FVector::ForwardVector, 1.0f);
			W.Step();
		}
		W.Run(Delay);
		const float VzBefore = Move->Velocity.Z;
		C->Jump();
		W.Run(2.0f * SOTest::Dt);
		C->StopJumping();
		const bool bJumped = Move->Velocity.Z > 400.0f;
		if (Delay < Move->CoyoteTime)
		{
			TestTrue(FString::Printf(TEXT("jump %.2f s after leaving the ledge works (vz %.0f -> %.0f)"), Delay, VzBefore, Move->Velocity.Z), bJumped);
		}
		else
		{
			TestFalse(FString::Printf(TEXT("jump %.2f s after leaving the ledge is refused"), Delay), bJumped);
		}
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOMovementMantleTest, "ShatteredOrbit.Movement.Mantle", SOTest::Flags)
bool FSOMovementMantleTest::RunTest(const FString& Parameters)
{
	for (const float Height : { 60.0f, 120.0f, 200.0f, 240.0f, 300.0f })
	{
		SOTest::FTestWorld W;
		W.AddBox(FVector(-3000, -3000, -100), FVector(3000, 3000, 0));
		W.AddBox(FVector(150, -300, 0), FVector(450, 300, Height));
		ASOCharacter* C = W.SpawnCharacter(FVector(0, 0, 0));
		USOCharacterMovementComponent* Move = C->GetSOMovement();
		W.Run(0.3f);

		// Push toward the ledge with jump held until a mantle has finished (the block is only 3 m deep), then settle.
		bool bMantled = false;
		Move->SetWantsToMantle(true);
		W.Run(2.0f, [C, Move, &bMantled]
		{
			bMantled |= Move->IsMantling();
			if (!bMantled || Move->IsMantling())
			{
				C->AddMovementInput(FVector::ForwardVector, 1.0f);
			}
		});
		Move->SetWantsToMantle(false);
		W.Run(0.3f);

		const float FeetZ = C->GetActorLocation().Z - C->GetCapsuleComponent()->GetScaledCapsuleHalfHeight();
		if (Height <= Move->MantleMaxHeight)
		{
			TestTrue(FString::Printf(TEXT("mantles a %.0f cm ledge"), Height), bMantled);
			TestEqual(FString::Printf(TEXT("stands on the %.0f cm ledge"), Height), FeetZ, Height, 4.0f);
			TestTrue(TEXT("walking after the mantle"), Move->IsMovingOnGround());
		}
		else
		{
			TestFalse(FString::Printf(TEXT("does not mantle a %.0f cm wall"), Height), bMantled);
			TestEqual(TEXT("still on the floor"), FeetZ, 0.0f, 4.0f);
		}
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOViewToggleTest, "ShatteredOrbit.Camera.ViewToggle", SOTest::Flags)
bool FSOViewToggleTest::RunTest(const FString& Parameters)
{
	SOTest::FTestWorld W;
	ASOCharacter* C = W.SpawnCharacter(FVector(0, 0, 0));
	TestTrue(TEXT("first person by default"), C->GetViewMode() == ESOViewMode::FirstPerson);
	TestTrue(TEXT("first-person camera active"), C->GetFirstPersonCamera()->IsActive());
	TestTrue(TEXT("body hidden from owner"), C->GetMesh()->bOwnerNoSee);
	C->ToggleViewMode();
	TestTrue(TEXT("third person after toggle"), C->GetViewMode() == ESOViewMode::ThirdPerson);
	TestTrue(TEXT("third-person camera active"), C->GetThirdPersonCamera()->IsActive());
	TestFalse(TEXT("first-person camera inactive"), C->GetFirstPersonCamera()->IsActive());
	TestFalse(TEXT("body visible to owner"), C->GetMesh()->bOwnerNoSee);
	C->ToggleViewMode();
	TestTrue(TEXT("back to first person"), C->GetFirstPersonCamera()->IsActive());
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOLookMathTest, "ShatteredOrbit.Look.Math", SOTest::Flags)
bool FSOLookMathTest::RunTest(const FString& Parameters)
{
	TestEqual(TEXT("zoom scale 90 -> 72"), USOLookComponent::ZoomScale(90.0f, 72.0f), FMath::Tan(FMath::DegreesToRadians(36.0f)), 1e-4f);
	TestEqual(TEXT("zoom scale identity"), USOLookComponent::ZoomScale(80.0f, 80.0f), 1.0f, 1e-5f);
	TestEqual(TEXT("response curve x^2"), static_cast<float>(USOLookComponent::ApplyResponseCurve(FVector2D(0.5f, 0.0f), 2.0f).X), 0.25f, 1e-5f);
	TestEqual(TEXT("response curve keeps full deflection"), static_cast<float>(USOLookComponent::ApplyResponseCurve(FVector2D(0.0f, -1.0f), 3.0f).Y), -1.0f, 1e-5f);

	USOLookComponent* Look = NewObject<USOLookComponent>();
	Look->bApplyToController = false;
	Look->MouseSensitivity = 1.0f;
	Look->AimSmoothing = 0.0f;
	Look->AddMouseInput(FVector2D(100.0f, 0.0f));
	TestEqual(TEXT("raw mouse degrees"), static_cast<float>(Look->ConsumeLookDelta(SOTest::Dt).X), 100.0f * Look->MouseDegreesPerCount, 1e-3f);

	Look->SetAim(true, 90.0f, 72.0f);
	Look->AimSensitivityMultiplier = 1.0f;
	Look->AddMouseInput(FVector2D(100.0f, 0.0f));
	TestEqual(TEXT("zoom-matched aim degrees"), static_cast<float>(Look->ConsumeLookDelta(SOTest::Dt).X),
		100.0f * Look->MouseDegreesPerCount * USOLookComponent::ZoomScale(90.0f, 72.0f), 1e-3f);
	Look->SetAim(false, 90.0f, 90.0f);

	// Smoothing: time constant = setting * 0.06 s; a steady input converges, a step lags by ~tau.
	Look->AimSmoothing = 0.3f;
	Look->ResetLook();
	TestEqual(TEXT("time constant"), Look->GetSmoothingTimeConstant(), 0.018f, 1e-6f);
	float Total = 0.0f;
	float Last = 0.0f;
	for (int32 i = 0; i < 60; ++i)
	{
		Look->AddMouseInput(FVector2D(10.0f, 0.0f));
		Last = static_cast<float>(Look->ConsumeLookDelta(SOTest::Dt).X);
		Total += Last;
	}
	const float PerFrame = 10.0f * Look->MouseDegreesPerCount;
	TestEqual(TEXT("smoothed steady state"), Last, PerFrame, PerFrame * 0.01f);
	TestTrue(TEXT("smoothing lags a little"), Total < PerFrame * 60.0f && Total > PerFrame * 58.0f);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOSettingsApplyTest, "ShatteredOrbit.Settings.ApplyGraphics", SOTest::Flags)
bool FSOSettingsApplyTest::RunTest(const FString& Parameters)
{
	USOGameUserSettings* Settings = USOGameUserSettings::Get();
	if (!TestNotNull(TEXT("GameUserSettingsClassName is SOGameUserSettings"), Settings))
	{
		return false;
	}
	auto GetInt = [](const TCHAR* Name) { IConsoleVariable* V = IConsoleManager::Get().FindConsoleVariable(Name); return V ? V->GetInt() : -999; };
	auto GetFloat = [](const TCHAR* Name) { IConsoleVariable* V = IConsoleManager::Get().FindConsoleVariable(Name); return V ? V->GetFloat() : -999.0f; };

	const bool bLumen = Settings->bLumen;
	const bool bVsm = Settings->bVirtualShadowMaps;
	const ESOAntiAliasing AA = Settings->AntiAliasing;
	const float SP = Settings->ScreenPercentage;
	const bool bMB = Settings->bMotionBlur;

	Settings->bLumen = false;
	Settings->bVirtualShadowMaps = false;
	Settings->AntiAliasing = ESOAntiAliasing::FXAA;
	Settings->ScreenPercentage = 75.0f;
	Settings->bMotionBlur = true;
	Settings->ApplyGraphics();
	TestEqual(TEXT("GI off"), GetInt(TEXT("r.DynamicGlobalIlluminationMethod")), 0);
	TestEqual(TEXT("SSR"), GetInt(TEXT("r.ReflectionMethod")), 2);
	TestEqual(TEXT("VSM off"), GetInt(TEXT("r.Shadow.Virtual.Enable")), 0);
	TestEqual(TEXT("FXAA"), GetInt(TEXT("r.AntiAliasingMethod")), 1);
	TestEqual(TEXT("screen percentage"), GetFloat(TEXT("r.ScreenPercentage")), 75.0f);
	TestEqual(TEXT("motion blur on"), GetInt(TEXT("r.MotionBlurQuality")), 4);

	Settings->bLumen = true;
	Settings->bVirtualShadowMaps = true;
	Settings->AntiAliasing = ESOAntiAliasing::TSR;
	Settings->ScreenPercentage = 100.0f;
	Settings->bMotionBlur = false;
	Settings->ApplyGraphics();
	TestEqual(TEXT("Lumen GI"), GetInt(TEXT("r.DynamicGlobalIlluminationMethod")), 1);
	TestEqual(TEXT("Lumen reflections"), GetInt(TEXT("r.ReflectionMethod")), 1);
	TestEqual(TEXT("VSM on"), GetInt(TEXT("r.Shadow.Virtual.Enable")), 1);
	TestEqual(TEXT("TSR"), GetInt(TEXT("r.AntiAliasingMethod")), 4);
	TestEqual(TEXT("motion blur off"), GetInt(TEXT("r.MotionBlurQuality")), 0);

	Settings->bLumen = bLumen;
	Settings->bVirtualShadowMaps = bVsm;
	Settings->AntiAliasing = AA;
	Settings->ScreenPercentage = SP;
	Settings->bMotionBlur = bMB;
	Settings->ApplyGraphics();
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOTimeOfDayTest, "ShatteredOrbit.World.TimeOfDay", SOTest::Flags)
bool FSOTimeOfDayTest::RunTest(const FString& Parameters)
{
	USOTimeOfDaySubsystem* Clock = NewObject<USOTimeOfDaySubsystem>();
	Clock->SetHour(12.0f);
	TestTrue(TEXT("noon sun is high in the south"), Clock->GetSunDirection().Z > 0.8f && Clock->GetSunDirection().X < 0.0f);
	Clock->SetHour(6.0f);
	TestTrue(TEXT("sunrise in the east"), FMath::Abs(Clock->GetSunDirection().Z) < 0.02f && Clock->GetSunDirection().Y > 0.9f);
	Clock->SetHour(20.0f);
	TestTrue(TEXT("sunset in the west"), Clock->GetSunDirection().Y < -0.9f);
	Clock->SetHour(1.0f);
	TestTrue(TEXT("night"), Clock->GetDaylight() < 0.01f);
	Clock->SetHour(25.5f);
	TestEqual(TEXT("hour wraps"), Clock->GetHour(), 1.5f, 1e-4f);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOInputAssetsTest, "ShatteredOrbit.Content.InputAssets", SOTest::Flags)
bool FSOInputAssetsTest::RunTest(const FString& Parameters)
{
	const ASOCharacter* C = GetDefault<ASOCharacter>();
	const TSoftObjectPtr<UInputAction> Actions[] = { C->MoveAction, C->LookAction, C->LookGamepadAction, C->JumpAction, C->SprintAction,
		C->CrouchAction, C->ToggleViewAction, C->InteractAction, C->FireAction, C->AimAction, C->ReloadAction };
	for (const TSoftObjectPtr<UInputAction>& Action : Actions)
	{
		TestNotNull(*FString::Printf(TEXT("input action %s (run setup_input.py)"), *Action.ToString()), Action.LoadSynchronous());
	}
	const UInputMappingContext* Context = LoadObject<UInputMappingContext>(nullptr, TEXT("/Game/Input/IMC_Default.IMC_Default"));
	if (TestNotNull(TEXT("IMC_Default"), Context))
	{
		TestTrue(TEXT("keyboard/mouse + gamepad mappings"), Context->GetMappings().Num() >= 20);
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOTestMapTest, "ShatteredOrbit.Content.TestRangeLoads", SOTest::Flags)
bool FSOTestMapTest::RunTest(const FString& Parameters)
{
	UWorld* Map = LoadObject<UWorld>(nullptr, TEXT("/Game/Maps/L_TestRange.L_TestRange"));
	if (!TestNotNull(TEXT("L_TestRange loads (run make_test_map.py)"), Map) || !TestNotNull(TEXT("persistent level"), Map->PersistentLevel.Get()))
	{
		return false;
	}
	int32 PlayerStarts = 0, Suns = 0, SkyLights = 0, Fogs = 0, PostProcess = 0, Atmospheres = 0, Blocks = 0;
	for (AActor* Actor : Map->PersistentLevel->Actors)
	{
		if (!Actor)
		{
			continue;
		}
		PlayerStarts += Actor->IsA<APlayerStart>();
		Suns += Actor->IsA<ADirectionalLight>();
		SkyLights += Actor->IsA<ASkyLight>();
		Fogs += Actor->IsA<AExponentialHeightFog>();
		PostProcess += Actor->IsA<APostProcessVolume>();
		Atmospheres += Actor->FindComponentByClass<USkyAtmosphereComponent>() != nullptr;
		Blocks += Actor->ActorHasTag(TEXT("SOTestGeometry"));
	}
	TestEqual(TEXT("player start"), PlayerStarts, 1);
	TestEqual(TEXT("sun"), Suns, 1);
	TestEqual(TEXT("sky light"), SkyLights, 1);
	TestEqual(TEXT("height fog"), Fogs, 1);
	TestEqual(TEXT("post process volume"), PostProcess, 1);
	TestEqual(TEXT("sky atmosphere"), Atmospheres, 1);
	TestTrue(TEXT("floor, walls, ledges and ramps"), Blocks >= 12);
	const AWorldSettings* WorldSettings = Map->GetWorldSettings();
	TestTrue(TEXT("game mode override is SOGameMode"), WorldSettings && WorldSettings->DefaultGameMode.Get() == ASOGameMode::StaticClass());
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
