#include "SOPlayerController.h"

#include "EnhancedInputSubsystems.h"
#include "Engine/LocalPlayer.h"
#include "InputMappingContext.h"
#include "EngineUtils.h"
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
	// Freeze the creatures so they pose for the pictures instead of ending them.
	for (TActorIterator<ASOEnemy> It(GetWorld()); It; ++It)
	{
		if (AController* AI = It->GetController())
		{
			AI->SetActorTickEnabled(false);
			AI->StopMovement();
		}
	}
	// The first steps give shaders and streaming time to settle.
	GetWorldTimerManager().SetTimer(CaptureTimer, this, &ASOPlayerController::CaptureStep, 1.0f, true, 4.0f);
}

void ASOPlayerController::CaptureStep()
{
	ASOCharacter* Hero = Cast<ASOCharacter>(GetPawn());
	auto Shot = [this, Hero](const TCHAR* Name)
	{
		const FString File = FPaths::ProjectSavedDir() / TEXT("Screenshots") / FString::Printf(TEXT("SO_%s.png"), Name);
		FScreenshotRequest::RequestScreenshot(File, false, false);
		UE_LOG(LogShatteredOrbit, Log, TEXT("Capture: %s"), *File);
		if (Hero && PlayerCameraManager)
		{
			const FBox Body = Hero->GetMesh()->Bounds.GetBox();
			UE_LOG(LogShatteredOrbit, Log, TEXT("  camera %s | actor %s | FP active %d TP active %d at %s | body %s..%s visible %d ownerNoSee %d | viewmodel rel %s"),
				*PlayerCameraManager->GetCameraLocation().ToCompactString(), *Hero->GetActorLocation().ToCompactString(),
				Hero->GetFirstPersonCamera()->IsActive(), Hero->GetThirdPersonCamera()->IsActive(),
				*Hero->GetThirdPersonCamera()->GetComponentLocation().ToCompactString(), *Body.Min.ToCompactString(), *Body.Max.ToCompactString(),
				Hero->GetMesh()->IsVisible(), Hero->GetMesh()->bOwnerNoSee, *Hero->GetViewmodel()->GetRelativeLocation().ToCompactString());
			if (const ASOWeapon* W = Hero->GetWeapon())
			{
				const float* G = W->GetPose().Gun;
				TArray<USceneComponent*> Kids;
				W->GetFirstPersonRig()->GetChildrenComponents(true, Kids);
				int32 Visible = 0;
				for (USceneComponent* K : Kids) { Visible += K->IsVisible(); }
				const FVector Rel = PlayerCameraManager->GetCameraRotation().UnrotateVector(W->GetFirstPersonRig()->GetComponentLocation() - PlayerCameraManager->GetCameraLocation());
				UE_LOG(LogShatteredOrbit, Log, TEXT("  gun pose %.3f %.3f %.3f %.3f %.3f %.3f | fp rig rel cam %s | %d/%d fp parts visible | rig visible %d"),
					G[0], G[1], G[2], G[3], G[4], G[5], *Rel.ToCompactString(), Visible, Kids.Num(), W->GetFirstPersonRig()->IsVisible());
			}
		}
	};
	switch (CaptureIndex++)
	{
	// A screenshot is taken at the end of the frame, so every change of pose gets its own step.
	case 0: Shot(TEXT("1_hip")); if (Hero) { Hero->HandleFirePressed(); } break;
	case 1: Shot(TEXT("2_firing")); break;
	case 2: Shot(TEXT("3_impacts")); if (Hero) { Hero->HandleFireReleased(); Hero->HandleAimPressed(); } break;
	case 3: Shot(TEXT("4_ads")); if (Hero) { Hero->HandleAimReleased(); if (ASOWeapon* W = Hero->GetWeapon()) { W->SetAmmo(0, 120); W->StartReload(); } } break;
	case 4: Shot(TEXT("5_reload")); break;
	case 5: if (Hero) { Hero->SetViewMode(ESOViewMode::ThirdPerson); } break;
	case 6: Shot(TEXT("6_third_person")); if (Hero) { Hero->HandleFirePressed(); } break;
	case 7: Shot(TEXT("7_third_person_firing")); if (Hero) { Hero->HandleFireReleased(); } SetControlRotation(FRotator(-10.0f, 180.0f, 0.0f)); break;
	case 8: break;
	case 9: Shot(TEXT("8_third_person_front")); break;
	default:
		GetWorldTimerManager().ClearTimer(CaptureTimer);
		if (bCaptureQuit)
		{
			UKismetSystemLibrary::QuitGame(this, this, EQuitPreference::Quit, false);
		}
		break;
	}
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
