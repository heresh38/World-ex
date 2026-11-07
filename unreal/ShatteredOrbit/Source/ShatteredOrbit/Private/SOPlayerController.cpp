#include "SOPlayerController.h"

#include "EnhancedInputSubsystems.h"
#include "Engine/LocalPlayer.h"
#include "InputMappingContext.h"
#include "EngineUtils.h"
#include "Camera/CameraActor.h"
#include "Camera/CameraComponent.h"
#include "SOCharacter.h"
#include "SOGunRigComponent.h"
#include "SOViewmodelComponent.h"
#include "SOEnemy.h"
#include "SOLog.h"
#include "SOWeapon.h"
#include "TimerManager.h"
#include "UnrealClient.h"
#include "Kismet/KismetSystemLibrary.h"
#include "Engine/GameViewportClient.h"
#include "RHI.h"
#include "UnrealEngine.h"

ASOPlayerController::ASOPlayerController()
{
	DefaultMappingContext = TSoftObjectPtr<UInputMappingContext>(FSoftObjectPath(TEXT("/Game/Input/IMC_Default.IMC_Default")));
}

void ASOPlayerController::BeginPlay()
{
	Super::BeginPlay();
	if (IsLocalController())
	{
		AddDefaultMappingContext();
		SetInputMode(FInputModeGameOnly());
		SetShowMouseCursor(false);
	}
}

bool ASOPlayerController::AddDefaultMappingContext()
{
	UInputMappingContext* Context = DefaultMappingContext.LoadSynchronous();
	if (!Context)
	{
		UE_LOG(LogShatteredOrbit, Warning, TEXT("SOPlayerController: %s is missing; run Content/Python/setup_input.py"), *DefaultMappingContext.ToString());
		return false;
	}
	const ULocalPlayer* LocalPlayer = GetLocalPlayer();
	UEnhancedInputLocalPlayerSubsystem* Subsystem = LocalPlayer ? LocalPlayer->GetSubsystem<UEnhancedInputLocalPlayerSubsystem>() : nullptr;
	if (!Subsystem)
	{
		return false;
	}
	Subsystem->AddMappingContext(Context, DefaultMappingPriority);
	return true;
}

void ASOPlayerController::SOCaptureSeries(int32 bQuitWhenDone)
{
	bCaptureQuit = bQuitWhenDone != 0;
	CaptureIndex = 0;
	CaptureWait = 0.0f;
	// Freeze the creatures so they pose for the pictures instead of ending them.
	for (TActorIterator<ASOEnemy> It(GetWorld()); It; ++It)
	{
		if (AController* AI = It->GetController())
		{
			AI->SetActorTickEnabled(false);
			AI->StopMovement();
		}
	}

	auto Hero = [this]() { return Cast<ASOCharacter>(GetPawn()); };
	auto Shot = [this, Hero](const TCHAR* Name)
	{
		const FString File = FPaths::ProjectSavedDir() / TEXT("Screenshots") / FString::Printf(TEXT("SO_%s.png"), Name);
		FScreenshotRequest::RequestScreenshot(File, false, false);
		UE_LOG(LogShatteredOrbit, Log, TEXT("Capture: %s"), *File);
		if (ASOCharacter* H = Hero(); H && PlayerCameraManager)
		{
			UE_LOG(LogShatteredOrbit, Log, TEXT("  camera %s rot %s | actor %s yaw %.1f | aim %.2f"), *PlayerCameraManager->GetCameraLocation().ToCompactString(),
				*PlayerCameraManager->GetCameraRotation().ToCompactString(), *H->GetActorLocation().ToCompactString(), H->GetActorRotation().Yaw, H->GetAimProgress());
			if (const ASOWeapon* W = H->GetWeapon())
			{
				const USkeletalMeshComponent* Bodies[2] = { H->GetFirstPersonArms(), H->GetMesh() };
				const USOGunRigComponent* Rigs[2] = { W->GetFirstPersonRig(), W->GetThirdPersonRig() };
				for (int32 i = 0; i < 2; ++i)
				{
					FTransform R, L;
					if (Rigs[i] && Rigs[i]->GetHandTargets(R, L))
					{
						const FVector Local = H->GetActorTransform().InverseTransformPosition(Rigs[i]->GetComponentLocation());
						UE_LOG(LogShatteredOrbit, Log, TEXT("  %s rig at %s (actor space) fwd %s | R target %s bone %s | L target %s bone %s"),
							i == 0 ? TEXT("FP") : TEXT("TP"), *Local.ToCompactString(),
							*H->GetActorTransform().InverseTransformVector(Rigs[i]->GetForwardVector()).ToCompactString(),
							*H->GetActorTransform().InverseTransformPosition(R.GetLocation()).ToCompactString(),
							*H->GetActorTransform().InverseTransformPosition(Bodies[i]->GetBoneLocation(TEXT("hand_R"))).ToCompactString(),
							*H->GetActorTransform().InverseTransformPosition(L.GetLocation()).ToCompactString(),
							*H->GetActorTransform().InverseTransformPosition(Bodies[i]->GetBoneLocation(TEXT("hand_L"))).ToCompactString());
					}
				}
			}
		}
	};
	auto Weapon = [Hero]() { ASOCharacter* H = Hero(); return H ? H->GetWeapon() : nullptr; };
	// A free camera around the character (yaw relative to the character's facing, 0 = in front looking back).
	auto Orbit = [this, Hero](float Yaw, float Distance, float Height)
	{
		ASOCharacter* H = Hero();
		if (!H)
		{
			return;
		}
		if (!CaptureCamera)
		{
			CaptureCamera = GetWorld()->SpawnActor<ACameraActor>();
		}
		const FVector Focus = H->GetActorLocation() + FVector(0, 0, 50.0f);
		const FRotator Around(0.0f, H->GetActorRotation().Yaw + Yaw, 0.0f);
		const FVector Eye = Focus + Around.Vector() * Distance + FVector(0, 0, Height);
		CaptureCamera->SetActorLocationAndRotation(Eye, (Focus - Eye).Rotation());
		SetViewTarget(CaptureCamera);
	};
	auto Look = [this](float Pitch) { SetControlRotation(FRotator(Pitch, GetControlRotation().Yaw, 0.0f)); };
	auto Do = [this](float Delay, TFunction<void()> Action, TFunction<bool()> Ready = nullptr) -> void
	{
		CaptureCues.Add({ Delay, MoveTemp(Ready), MoveTemp(Action) });
	};

	CaptureCues.Reset();
	// The first cue waits for shaders and streaming to settle.
	// A screenshot is taken at the end of the frame, so a shot cue never changes anything else.
	auto Snap = [Do, Shot](float Delay, const TCHAR* Name, TFunction<bool()> Ready = nullptr) { Do(Delay, [Shot, Name]() { Shot(Name); }, MoveTemp(Ready)); };
	auto Act = [Do](TFunction<void()> Action) { Do(0.05f, MoveTemp(Action)); };
	auto Fire = [Hero](bool bDown) { if (ASOCharacter* H = Hero()) { if (bDown) { H->HandleFirePressed(); } else { H->HandleFireReleased(); } } };
	auto Aim = [Hero](bool bDown) { if (ASOCharacter* H = Hero()) { if (bDown) { H->HandleAimPressed(); } else { H->HandleAimReleased(); } } };
	auto EmptyReload = [Weapon]() { if (ASOWeapon* W = Weapon()) { W->SetAmmo(0, 120); W->StartReload(); } };
	auto MidMag = [Weapon]() { const ASOWeapon* W = Weapon(); return W && W->GetPose().bSpareVisible && W->GetPose().HandAlpha > 0.5f; };
	auto MidRack = [Weapon]() { const ASOWeapon* W = Weapon(); return W && W->GetPose().Bolt > 0.06f; };
	auto View = [Hero](ESOViewMode Mode) { if (ASOCharacter* H = Hero()) { H->SetViewMode(Mode); } };

	CaptureCues.Reset();
	Do(4.0f, [=, this]() { Look(0.0f); }); // shaders and streaming settle first
	Snap(1.0f, TEXT("1_hip"));
	Act([=, this]() { Fire(true); });
	Snap(0.3f, TEXT("2_firing"));
	Act([=, this]() { Fire(false); });
	Snap(0.6f, TEXT("3_impacts"));
	Act([=, this]() { Aim(true); });
	Snap(1.0f, TEXT("4_ads"));
	Act([=, this]() { Fire(true); });
	Snap(0.25f, TEXT("4b_ads_firing"));
	Act([=, this]() { Fire(false); });
	Snap(1.2f, TEXT("4c_ads_impacts"));
	Act([=, this]() { Aim(false); EmptyReload(); });
	Snap(0.0f, TEXT("5_reload_mag"), MidMag);
	Snap(0.0f, TEXT("5b_rack"), MidRack);
	Act([=, this]() { Look(-60.0f); });
	Snap(2.0f, TEXT("5c_look_down"));
	Act([=, this]() { Look(0.0f); View(ESOViewMode::ThirdPerson); });
	Snap(1.0f, TEXT("6_third_person"));
	Act([=, this]() { Fire(true); });
	Snap(0.6f, TEXT("7_third_person_firing"));
	Act([=, this]() { Fire(false); });
	Snap(0.5f, TEXT("7a_third_person_impacts"));
	Act([=, this]() { Aim(true); });
	Snap(0.8f, TEXT("7b_third_person_ads"));
	Act([=, this]() { Orbit(90.0f, 190.0f, 20.0f); });
	Snap(0.4f, TEXT("8_right_side_ads"));
	Act([=, this]() { Aim(false); });
	Snap(0.8f, TEXT("8b_right_side_hip"));
	Act([=, this]() { Orbit(-90.0f, 190.0f, 20.0f); });
	Snap(0.4f, TEXT("8c_left_side_hip"));
	Act([=, this]() { Orbit(30.0f, 210.0f, 30.0f); });
	Snap(0.4f, TEXT("9_front_hip"));
	Act([=, this]() { Aim(true); });
	Snap(0.8f, TEXT("9a_front_ads"));
	Act([=, this]() { Aim(false); Orbit(90.0f, 190.0f, 20.0f); Look(-45.0f); });
	Snap(0.8f, TEXT("9b_side_look_down"));
	Act([=, this]() { Look(35.0f); });
	Snap(0.8f, TEXT("9c_side_look_up"));
	Act([=, this]() { Look(0.0f); Orbit(-70.0f, 170.0f, 30.0f); EmptyReload(); });
	Snap(0.0f, TEXT("9d_left_side_mag"), MidMag);
	Snap(0.0f, TEXT("9e_left_side_rack"), MidRack);
	Act([=, this]() { SetViewTarget(GetPawn()); });
	Do(1.5f, []() {});

	// Poll often so condition cues (mid-reload) land on the right frame.
	GetWorldTimerManager().SetTimer(CaptureTimer, this, &ASOPlayerController::CaptureStep, 0.02f, true);
}

void ASOPlayerController::CaptureStep()
{
	CaptureWait += 0.02f;
	if (!CaptureCues.IsValidIndex(CaptureIndex))
	{
		GetWorldTimerManager().ClearTimer(CaptureTimer);
		if (bCaptureQuit)
		{
			UKismetSystemLibrary::QuitGame(this, this, EQuitPreference::Quit, false);
		}
		return;
	}
	const FCaptureCue& Cue = CaptureCues[CaptureIndex];
	if (CaptureWait < Cue.Delay || (Cue.Ready && !Cue.Ready()))
	{
		return;
	}
	CaptureWait = 0.0f;
	++CaptureIndex;
	Cue.Action();
}

void ASOPlayerController::SOBenchmark(float Seconds, int32 bQuitWhenDone)
{
	BenchWarmup = 5.0f;
	BenchLeft = FMath::Max(Seconds, 1.0f);
	bBenchQuit = bQuitWhenDone != 0;
	BenchFrame.Reset();
	BenchGame.Reset();
	BenchRender.Reset();
	BenchGpu.Reset();
	UE_LOG(LogShatteredOrbit, Log, TEXT("Benchmark: 5 s warm-up, then %.0f s"), BenchLeft);
}

void ASOPlayerController::PlayerTick(float DeltaTime)
{
	Super::PlayerTick(DeltaTime);
	if (BenchWarmup < 0.0f && BenchLeft <= 0.0f)
	{
		return;
	}
	if (BenchWarmup > 0.0f)
	{
		BenchWarmup -= DeltaTime;
		return;
	}
	BenchFrame.Add(DeltaTime * 1000.0f);
	BenchGame.Add(FPlatformTime::ToMilliseconds(GGameThreadTime));
	BenchRender.Add(FPlatformTime::ToMilliseconds(GRenderThreadTime));
	BenchGpu.Add(FPlatformTime::ToMilliseconds(RHIGetGPUFrameCycles(0)));
	BenchLeft -= DeltaTime;
	if (BenchLeft <= 0.0f)
	{
		BenchWarmup = -1.0f;
		FinishBenchmark();
	}
}

void ASOPlayerController::FinishBenchmark()
{
	auto Stats = [](TArray<float> V, float& Avg, float& P95)
	{
		Avg = P95 = 0.0f;
		if (V.Num() == 0)
		{
			return;
		}
		V.Sort();
		for (float X : V) { Avg += X; }
		Avg /= V.Num();
		P95 = V[FMath::Min(V.Num() - 1, FMath::FloorToInt(V.Num() * 0.95f))];
	};
	float FA, FP, GA, GP, RA, RP, UA, UP;
	Stats(BenchFrame, FA, FP);
	Stats(BenchGame, GA, GP);
	Stats(BenchRender, RA, RP);
	Stats(BenchGpu, UA, UP);
	FVector2D Size(0, 0);
	if (GEngine && GEngine->GameViewport)
	{
		GEngine->GameViewport->GetViewportSize(Size);
	}
	UE_LOG(LogShatteredOrbit, Log, TEXT("Benchmark %dx%d, %d frames: frame %.2f ms avg (%.0f fps), %.2f ms p95 | game %.2f / %.2f | render %.2f / %.2f | GPU %.2f / %.2f (avg / p95 ms)"),
		(int32)Size.X, (int32)Size.Y, BenchFrame.Num(), FA, FA > 0.0f ? 1000.0f / FA : 0.0f, FP, GA, GP, RA, RP, UA, UP);
	if (bBenchQuit)
	{
		UKismetSystemLibrary::QuitGame(this, this, EQuitPreference::Quit, false);
	}
}
