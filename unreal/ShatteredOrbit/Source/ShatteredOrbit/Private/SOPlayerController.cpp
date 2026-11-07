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
#include "SOInventoryComponent.h"
#include "SOLootActors.h"
#include "SOLootLibrary.h"
#include "SOHUD.h"
#include "SOInventoryWidget.h"
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

void ASOPlayerController::SOCaptureSeries(int32 bQuitWhenDone, int32 Set)
{
	bCaptureQuit = bQuitWhenDone != 0;
	CaptureIndex = 0;
	CaptureWait = 0.0f;
	// Pictures only: nothing the series picks up or opens reaches the player's save.
	if (USOInventoryComponent* Inventory = SOFindInventory(this))
	{
		Inventory->bPersist = false;
	}
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
		FScreenshotRequest::RequestScreenshot(File, true, false); // with UI (the inventory screen is UMG)
		UE_LOG(LogShatteredOrbit, Log, TEXT("Capture: %s"), *File);
		if (ASOCharacter* H = Hero(); H && PlayerCameraManager)
		{
			UE_LOG(LogShatteredOrbit, Log, TEXT("  camera %s rot %s | actor %s yaw %.1f | aim %.2f"), *PlayerCameraManager->GetCameraLocation().ToCompactString(),
				*PlayerCameraManager->GetCameraRotation().ToCompactString(), *H->GetActorLocation().ToCompactString(), H->GetActorRotation().Yaw, H->GetAimProgress());
			const USkeletalMeshComponent* Arms = H->GetFirstPersonArms();
			UE_LOG(LogShatteredOrbit, Log, TEXT("  arms visible %d rendered %d hiddenInGame %d bounds %s r=%.0f view %d"), Arms->IsVisible(), Arms->WasRecentlyRendered(0.2f),
				Arms->bHiddenInGame, *Arms->Bounds.Origin.ToCompactString(), Arms->Bounds.SphereRadius, (int32)H->GetViewMode());
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
	auto Snap = [Do, Shot](float Delay, const FString& Name, TFunction<bool()> Ready = nullptr) { Do(Delay, [Shot, Name]() { Shot(*Name); }, MoveTemp(Ready)); };
	auto Act = [Do](TFunction<void()> Action) { Do(0.05f, MoveTemp(Action)); };
	auto Fire = [Hero](bool bDown) { if (ASOCharacter* H = Hero()) { if (bDown) { H->HandleFirePressed(); } else { H->HandleFireReleased(); } } };
	auto Aim = [Hero](bool bDown) { if (ASOCharacter* H = Hero()) { if (bDown) { H->HandleAimPressed(); } else { H->HandleAimReleased(); } } };
	auto EmptyReload = [Weapon]() { if (ASOWeapon* W = Weapon()) { W->SetAmmo(0, 120); W->StartReload(); } };
	auto MidMag = [Weapon]() { const ASOWeapon* W = Weapon(); return W && W->GetPose().bSpareVisible && W->GetPose().HandAlpha > 0.5f; };
	auto MidRack = [Weapon]() { const ASOWeapon* W = Weapon(); return W && W->GetPose().Bolt > 0.06f; };
	auto View = [Hero](ESOViewMode Mode) { if (ASOCharacter* H = Hero()) { H->SetViewMode(Mode); } };

	CaptureCues.Reset();
	if (Set == 2)
	{
		// Loadout screen and both bodies only (files l3..l6, p1..p5).
		auto Hud = [this]() { return Cast<ASOHUD>(GetHUD()); };
		auto OpenSlot = [Hud](const TCHAR* SlotKey) { if (ASOHUD* H = Hud(); H && H->GetInventoryWidget()) { H->GetInventoryWidget()->OpenSlot(SlotKey); } };
		Do(4.0f, [=, this]() { Look(0.0f); });
		Act([=]() { if (ASOHUD* H = Hud()) { H->ToggleInventory(); } });
		Snap(1.5f, TEXT("l3_inventory"));
		Act([=]() { OpenSlot(TEXT("0")); });
		Snap(0.6f, TEXT("l4_inventory_primary"));
		Act([=]() { OpenSlot(TEXT("outer")); });
		Snap(0.6f, TEXT("l5_inventory_coat"));
		Act([=]() { OpenSlot(TEXT("hands")); });
		Snap(0.6f, TEXT("l5b_inventory_hands"));
		Act([=, this]() { OpenSlot(TEXT("")); if (USOInventoryComponent* Inv = SOFindInventory(this)) { Inv->SetBody(TEXT("female")); } });
		Snap(1.5f, TEXT("l6_inventory_female"));
		Act([=, this]() { if (ASOHUD* H = Hud()) { H->ToggleInventory(); } View(ESOViewMode::ThirdPerson); Orbit(10.0f, 260.0f, 30.0f); });
		Snap(1.0f, TEXT("p1_female_front"));
		Act([=, this]() { Orbit(40.0f, 90.0f, 75.0f); });
		Snap(0.5f, TEXT("p2_female_face"));
		Act([=, this]() { if (USOInventoryComponent* Inv = SOFindInventory(this)) { Inv->SetBody(TEXT("male")); } Orbit(10.0f, 260.0f, 30.0f); });
		Snap(1.2f, TEXT("p3_male_front"));
		Act([=, this]() { Orbit(160.0f, 260.0f, 30.0f); });
		Snap(0.5f, TEXT("p4_male_back"));
		Act([=, this]() { Orbit(40.0f, 90.0f, 75.0f); });
		Snap(0.5f, TEXT("p5_male_face"));
		Do(0.5f, []() {});
		GetWorldTimerManager().SetTimer(CaptureTimer, this, &ASOPlayerController::CaptureStep, 0.02f, true);
		return;
	}
	if (Set == 1)
	{
		// Hold study: every gun in the hands from every side the player sees it.
		const TCHAR* Guns[] = { TEXT("rifle"), TEXT("carbine"), TEXT("dmr"), TEXT("ksmg"), TEXT("bolt"), TEXT("pistol"), TEXT("revolver"), TEXT("pump"),
			TEXT("auto"), TEXT("pulse"), TEXT("scout"), TEXT("handcannon"), TEXT("shotgun"), TEXT("sniper"), TEXT("smg"), TEXT("sidearm"), TEXT("energy"),
			TEXT("hmg"), TEXT("rocket"), TEXT("spitter"), TEXT("bile"), TEXT("brood") };
		auto Arm = [Hero](const TCHAR* Arch)
		{
			if (ASOCharacter* H = Hero())
			{
				FRandomStream Rng(FCrc::StrCrc32(Arch));
				FSOWeaponInstance W = USOLootLibrary::MakeWeapon(Arch, 2, 20, Rng);
				W.Sight = TEXT("default");
				H->EquipInstance(W);
			}
		};
		auto Reloading = [Weapon](float F) { return [Weapon, F]() { const ASOWeapon* W = Weapon(); return W && W->IsReloading() && W->GetReloadProgress() > F; }; };
		FString Only;
		FParse::Value(FCommandLine::Get(), TEXT("SOGuns="), Only, false); // a comma list
		Do(4.0f, [=, this]() { Look(0.0f); });
		for (int32 i = 0; i < UE_ARRAY_COUNT(Guns); ++i)
		{
			const TCHAR* Arch = Guns[i];
			if (!Only.IsEmpty() && !Only.Contains(Arch))
			{
				continue;
			}
			const FString Tag = FString::Printf(TEXT("h%02d_%s"), i, Arch);
			Act([=, this]() { SetViewTarget(GetPawn()); View(ESOViewMode::FirstPerson); Look(0.0f); Arm(Arch); });
			Snap(1.0f, Tag + TEXT("_a_hip"));
			Act([=, this]() { Aim(true); });
			Snap(0.8f, Tag + TEXT("_b_ads"));
			Act([=, this]() { Aim(false); });
			Do(0.5f, [=]() { EmptyReload(); });
			Snap(0.0f, Tag + TEXT("_c_reload"), Reloading(0.4f));
			Do(5.0f, []() {});
			Act([=, this]() { View(ESOViewMode::ThirdPerson); Orbit(80.0f, 150.0f, 15.0f); });
			Snap(0.8f, Tag + TEXT("_d_tp_right"));
			Act([=, this]() { Orbit(-55.0f, 150.0f, 25.0f); });
			Snap(0.4f, Tag + TEXT("_e_tp_left"));
			Act([=, this]() { Aim(true); Orbit(100.0f, 140.0f, 5.0f); });
			Snap(0.8f, Tag + TEXT("_f_tp_ads"));
			Act([=, this]() { Aim(false); });
		}
		GetWorldTimerManager().SetTimer(CaptureTimer, this, &ASOPlayerController::CaptureStep, 0.02f, true);
		return;
	}
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
	Act([=, this]() { SetViewTarget(GetPawn()); View(ESOViewMode::FirstPerson); Look(0.0f); });

	// Stage 5: every archetype in hand (rarity glow, mounted optics), the reload families mid-way, the projectile kinds
	// firing, an optic picture, loot cores by rarity, the reliquary and the inventory screen.
	auto Equip = [Hero](const TCHAR* Arch, int32 Rarity, const TCHAR* Sight)
	{
		ASOCharacter* H = Hero();
		if (!H)
		{
			return;
		}
		FRandomStream Rng(FCrc::StrCrc32(Arch));
		FSOWeaponInstance W = USOLootLibrary::MakeWeapon(Arch, Rarity, 20, Rng);
		if (Sight)
		{
			W.Sight = Sight;
		}
		H->EquipInstance(W);
	};
	auto MidReload = [Weapon](float F) { return [Weapon, F]() { const ASOWeapon* W = Weapon(); return W && W->IsReloading() && W->GetReloadProgress() > F; }; };
	const TCHAR* All[] = { TEXT("rifle"), TEXT("carbine"), TEXT("dmr"), TEXT("ksmg"), TEXT("bolt"), TEXT("pistol"), TEXT("revolver"), TEXT("pump"),
		TEXT("auto"), TEXT("pulse"), TEXT("scout"), TEXT("handcannon"), TEXT("shotgun"), TEXT("sniper"), TEXT("smg"), TEXT("sidearm"), TEXT("energy"),
		TEXT("hmg"), TEXT("rocket"), TEXT("spitter"), TEXT("bile"), TEXT("brood") };
	for (int32 i = 0; i < UE_ARRAY_COUNT(All); ++i)
	{
		const TCHAR* Arch = All[i];
		Act([=, this]() { Equip(Arch, i % 5, nullptr); });
		Snap(0.9f, *FString::Printf(TEXT("g%02d_%s"), i, Arch));
	}
	// reload families mid-way (empty: chambering too)
	const TPair<const TCHAR*, float> Reloads[] = { { TEXT("pistol"), 0.82f }, { TEXT("carbine"), 0.84f }, { TEXT("revolver"), 0.32f }, { TEXT("revolver"), 0.72f },
		{ TEXT("pump"), 0.3f }, { TEXT("bolt"), 0.35f }, { TEXT("spitter"), 0.6f }, { TEXT("auto"), 0.5f } };
	for (int32 i = 0; i < UE_ARRAY_COUNT(Reloads); ++i)
	{
		const TCHAR* Arch = Reloads[i].Key;
		Act([=, this]() { Equip(Arch, 2, nullptr); });
		Do(0.5f, [=]() { EmptyReload(); });
		Snap(0.0f, *FString::Printf(TEXT("r%d_%s"), i, Arch), MidReload(Reloads[i].Value));
		Do(4.0f, []() {});
	}
	// projectile kinds firing (screenshot a moment after the shot)
	const TPair<const TCHAR*, float> Shots[] = { { TEXT("pump"), 0.06f }, { TEXT("auto"), 0.08f }, { TEXT("rocket"), 0.25f }, { TEXT("spitter"), 0.2f }, { TEXT("brood"), 0.5f } };
	for (int32 i = 0; i < UE_ARRAY_COUNT(Shots); ++i)
	{
		const TCHAR* Arch = Shots[i].Key;
		Act([=, this]() { Equip(Arch, 3, nullptr); Look(-4.0f); });
		Do(0.8f, [=]() { Fire(true); });
		Do(0.05f, [=]() { Fire(false); });
		Snap(Shots[i].Value, *FString::Printf(TEXT("s%d_%s"), i, Arch));
		Do(1.5f, []() {});
	}
	// optics: a 4x scope on the rifle (the scope picture), a holo on the carbine
	Act([=, this]() { Equip(TEXT("rifle"), 3, TEXT("x4")); Look(0.0f); });
	Act([=, this]() { Aim(true); });
	Snap(0.9f, TEXT("o1_rifle_x4_scope"));
	Act([=, this]() { Aim(false); Equip(TEXT("carbine"), 3, TEXT("holo")); });
	Act([=, this]() { Aim(true); });
	Snap(0.9f, TEXT("o2_carbine_holo"));
	Act([=, this]() { Aim(false); });
	// loot cores of every rarity and the reliquary
	Act([=, this]()
	{
		if (USOLootSubsystem* Loot = GetWorld()->GetSubsystem<USOLootSubsystem>(); Loot && Hero())
		{
			const FVector Base = Hero()->GetActorLocation() + Hero()->GetActorForwardVector() * 700.0f - FVector(0, 0, 90.0f);
			for (int32 r = 0; r < 5; ++r)
			{
				Loot->SpawnPickup(Base + Hero()->GetActorRightVector() * (r - 2) * 160.0f, ESOPickupKind::Core, r, 20);
			}
			Loot->SpawnPickup(Base + Hero()->GetActorForwardVector() * -250.0f, ESOPickupKind::Ammo, 0, 20);
		}
		Look(-8.0f);
	});
	Snap(1.5f, TEXT("l1_loot_cores"));
	Act([=, this]()
	{
		for (TActorIterator<ASOReliquary> It(GetWorld()); It; ++It)
		{
			Orbit(0.0f, 1.0f, 0.0f); // reset the free camera, then frame the reliquary from the player's side
			const FVector At = It->GetActorLocation();
			CaptureCamera->SetActorLocationAndRotation(At + FVector(-260.0f, 180.0f, 160.0f), (At + FVector(0, 0, 70.0f) - (At + FVector(-260.0f, 180.0f, 160.0f))).Rotation());
			if (ASOCharacter* H = Hero())
			{
				It->Interact(H);
			}
			break;
		}
	});
	Snap(0.6f, TEXT("l2_reliquary_opened"));
	Act([=, this]() { SetViewTarget(GetPawn()); if (ASOHUD* Hud = Cast<ASOHUD>(GetHUD())) { Hud->ToggleInventory(); } });
	Snap(1.0f, TEXT("l3_inventory"));
	auto OpenSlot = [this](const TCHAR* SlotKey)
	{
		if (ASOHUD* Hud = Cast<ASOHUD>(GetHUD()); Hud && Hud->GetInventoryWidget())
		{
			Hud->GetInventoryWidget()->OpenSlot(SlotKey);
		}
	};
	Act([=]() { OpenSlot(TEXT("0")); });
	Snap(0.6f, TEXT("l4_inventory_primary"));
	Act([=]() { OpenSlot(TEXT("outer")); });
	Snap(0.6f, TEXT("l5_inventory_coat"));
	Act([=, this]() { OpenSlot(TEXT("")); if (USOInventoryComponent* Inv = SOFindInventory(this)) { Inv->SetBody(TEXT("female")); } });
	Snap(1.2f, TEXT("l6_inventory_female"));
	Act([=, this]() { if (ASOHUD* Hud = Cast<ASOHUD>(GetHUD())) { Hud->ToggleInventory(); } View(ESOViewMode::ThirdPerson); Orbit(10.0f, 260.0f, 30.0f); });
	Snap(1.0f, TEXT("p1_female_front"));
	Act([=, this]() { Orbit(160.0f, 260.0f, 30.0f); });
	Snap(0.5f, TEXT("p2_female_back"));
	Act([=, this]() { if (USOInventoryComponent* Inv = SOFindInventory(this)) { Inv->SetBody(TEXT("male")); } Orbit(10.0f, 260.0f, 30.0f); });
	Snap(1.2f, TEXT("p3_male_front"));
	Act([=, this]() { Orbit(160.0f, 260.0f, 30.0f); });
	Snap(0.5f, TEXT("p4_male_back"));
	Act([=, this]() { Orbit(20.0f, 70.0f, 70.0f); });
	Snap(0.5f, TEXT("p5_male_face"));
	Act([=, this]() { SetViewTarget(GetPawn()); View(ESOViewMode::FirstPerson); });
	Do(1.0f, []() {});

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
