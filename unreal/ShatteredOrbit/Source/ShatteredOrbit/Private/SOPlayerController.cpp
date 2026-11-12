#include "SOPlayerController.h"
#include "SOAreaSubsystem.h"

#include "SOLocomotionAnimInstance.h"

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
#include "SOAltered.h"
#include "NavigationSystem.h"
#include "NavigationPath.h"
#include "Components/CapsuleComponent.h"
#include "SOOperation.h"
#include "SOOperationBarrier.h"
#include "SOEnemyAIController.h"
#include "SOLog.h"
#include "SOWeapon.h"
#include "SOInventoryComponent.h"
#include "SOLootActors.h"
#include "SOLootLibrary.h"
#include "SOFxSubsystem.h"
#include "SOWeaponData.h"
#include "SOHUD.h"
#include "SOTimeOfDaySubsystem.h"
#include "SOWeather.h"
#include "SOCombatStatics.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "SOInventoryWidget.h"
#include "TimerManager.h"
#include "UnrealClient.h"
#include "Kismet/KismetSystemLibrary.h"
#include "Engine/GameViewportClient.h"
#include "RHI.h"
#include "UnrealEngine.h"
#include "Engine/StaticMeshActor.h"
#include "Framework/Application/SlateApplication.h"
#include "Engine/CollisionProfile.h"
#include "Kismet/GameplayStatics.h"
#include "SOCharacterMovementComponent.h"

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
		// Leaving the window (the Windows key, alt-tab) and coming back: no key stays held, and the game takes the
		// mouse again by itself instead of waiting for a click.
		if (FSlateApplication::IsInitialized())
		{
			ActivationHandle = FSlateApplication::Get().OnApplicationActivationStateChanged().AddUObject(this, &ASOPlayerController::OnWindowActivation);
		}
	}
}

void ASOPlayerController::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	if (ActivationHandle.IsValid() && FSlateApplication::IsInitialized())
	{
		FSlateApplication::Get().OnApplicationActivationStateChanged().Remove(ActivationHandle);
	}
	Super::EndPlay(EndPlayReason);
}

void ASOPlayerController::OnWindowActivation(bool bActive)
{
	FlushPressedKeys();
	if (bActive && !bShowMouseCursor)
	{
		SetInputMode(FInputModeGameOnly());
		FSlateApplication::Get().SetAllUserFocusToGameViewport();
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
			if (const USOLocomotionAnimInstance* Anim = Cast<USOLocomotionAnimInstance>(H->GetMesh()->GetAnimInstance()))
			{
				const float Floor = static_cast<float>(H->GetActorLocation().Z) - H->GetCapsuleComponent()->GetScaledCapsuleHalfHeight();
				UE_LOG(LogShatteredOrbit, Log, TEXT("  body: hips %.1f cm up, pelvis drop %.1f, crouch %.2f (capsule %s, half height %.0f), lean %.1f, speed %.0f, weights idle %.2f stroll %.2f walk %.2f run %.2f jump %.2f land %.2f"),
					static_cast<float>(H->GetMesh()->GetBoneLocation(TEXT("hips")).Z) - Floor, Anim->GetPelvisDrop(), Anim->GetCrouchAlpha(), H->bIsCrouched ? TEXT("crouched") : TEXT("standing"),
					H->GetCapsuleComponent()->GetScaledCapsuleHalfHeight(), Anim->GetLeanPitch(), H->GetVelocity().Size2D(), Anim->Weights[0], Anim->Weights[8], Anim->Weights[1], Anim->Weights[2], Anim->Weights[3], Anim->Weights[9]);
			}
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
	if (Set == 19)
	{
		// The loadout screen alone (files u*): as it opens, a weapon slot's bay with the details, an armour slot's
		// (mirrored), a hovered item against the equipped one.
		auto Hud = [this]() { return Cast<ASOHUD>(GetHUD()); };
		auto OpenSlot = [Hud](const TCHAR* SlotKey) { if (ASOHUD* H = Hud(); H && H->GetInventoryWidget()) { H->GetInventoryWidget()->OpenSlot(SlotKey); } };
		Do(5.0f, [=, this]() { ConsoleCommand(TEXT("DisableAllScreenMessages")); if (ASOHUD* H = Hud()) { H->ToggleInventory(); } });
		Snap(2.0f, TEXT("u1_loadout"));
		Act([=]() { OpenSlot(TEXT("0")); });
		Snap(1.2f, TEXT("u2_loadout_primary"));
		Act([=]() { OpenSlot(TEXT("2")); });
		Snap(1.2f, TEXT("u3_loadout_heavy"));
		Act([=]() { OpenSlot(TEXT("head")); });
		Snap(1.2f, TEXT("u4_loadout_head"));
		Act([=]() { OpenSlot(TEXT("")); });
		Snap(1.2f, TEXT("u5_loadout_closed"));
	}
	if (Set == 18)
	{
		// The gun in first person (files v_<gun>_<sight>_<view>): at the hip, on the sights, and firing on the sights,
		// with every sight the gun may carry. For checking the sight pictures, the flash, the tracer and how much of the
		// gun shows.
		static const TCHAR* Guns[] = { TEXT("rifle"), TEXT("auto"), TEXT("hmg"), TEXT("scout"), TEXT("shotgun"), TEXT("sidearm"),
			TEXT("energy"), TEXT("spitter"), TEXT("smg"), TEXT("pump"), TEXT("dmr"), TEXT("handcannon"), TEXT("pistol"), TEXT("carbine") };
		Do(6.0f, [=, this]()
		{
			ConsoleCommand(TEXT("DisableAllScreenMessages"));
			if (ASOCharacter* H = Hero())
			{
				SetControlRotation(FRotator(0.0f, H->GetActorRotation().Yaw + 90.0f, 0.0f));   // the open side of the range
				View(ESOViewMode::FirstPerson);
				SetViewTarget(H);
			}
		});
		// the flash by itself, in front of the eye: a round's, a bolt of light's, a living gun's; from the side (top row)
		// and three quarters on (bottom row), time nearly stopped
		Do(1.0f, [=, this]()
		{
			USOFxSubsystem* Fx = GetWorld()->GetSubsystem<USOFxSubsystem>();
			FVector Eye;
			FRotator Look;
			GetPlayerViewPoint(Eye, Look);
			const FVector F = Look.Vector(), R = FRotationMatrix(Look).GetUnitAxis(EAxis::Y), U = FRotationMatrix(Look).GetUnitAxis(EAxis::Z);
			const FLinearColor Colors[] = { FLinearColor(1.0f, 0.74f, 0.4f), FLinearColor(0.44f, 0.91f, 1.0f), FLinearColor(0.61f, 1.0f, 0.29f) };
			for (int32 i = 0; Fx && i < 3; ++i)
			{
				Fx->MuzzleFlash(Eye + F * 160.0f + R * (i - 1) * 62.0f - R * 14.0f + U * 22.0f, R, 1.0f, false, Colors[i]);
				Fx->MuzzleFlash(Eye + F * 160.0f + R * (i - 1) * 62.0f - U * 24.0f, (R * 0.5f - F * 0.86f).GetSafeNormal(), 1.0f, false, Colors[i]);
			}
			UGameplayStatics::SetGlobalTimeDilation(this, 0.02f);
		});
		Snap(0.0f, TEXT("v_0_flashes"));
		Act([=, this]() { UGameplayStatics::SetGlobalTimeDilation(this, 1.0f); });
		// (a shot's still is taken the moment the round leaves, with time nearly stopped from there: the flash lives
		// three frames)
		TSharedRef<int32> Shots = MakeShared<int32>(0);
		TFunction<bool()> Fired = [=, this]()
		{
			const ASOCharacter* H = Hero();
			if (H && H->GetWeapon() && H->GetWeapon()->GetShotsFired() != *Shots)
			{
				UGameplayStatics::SetGlobalTimeDilation(this, 0.02f);
				return true;
			}
			return false;
		};
		const USOLootTables* Tables = USOLootLibrary::GetTables();
		for (const TCHAR* G : Guns)
		{
			const FString A = G;
			const FSOArchetypeEntry* Entry = Tables ? Tables->Archetypes.FindByPredicate([&](const FSOArchetypeEntry& E) { return E.Id == FName(*A); }) : nullptr;
			const USOWeaponData* Data = Entry ? Entry->Data.LoadSynchronous() : nullptr;
			if (!Data)
			{
				continue;
			}
			bool bFirst = true;
			for (const FName SightId : Data->Sights)
			{
				const FString S = SightId.ToString();
				Do(0.3f, [=]()
				{
					if (ASOCharacter* H = Hero())
					{
						FRandomStream Rng(FCrc::StrCrc32(*A));
						FSOWeaponInstance Copy = USOLootLibrary::MakeWeapon(*A, 2, 20, Rng);
						Copy.Sight = SightId;
						H->EquipInstance(Copy);
					}
				});
				if (bFirst)
				{
					Snap(0.9f, FString::Printf(TEXT("v_%s_%s_1_hip"), *A, *S));
					// (time nearly stopped as the round leaves: the flash lives three frames)
					Act([=]() { if (ASOCharacter* H = Hero(); H && H->GetWeapon()) { *Shots = H->GetWeapon()->GetShotsFired(); H->GetWeapon()->StartFire(); } });
					Snap(0.0f, FString::Printf(TEXT("v_%s_%s_2_hipfire"), *A, *S), Fired);
					Act([=, this]() { UGameplayStatics::SetGlobalTimeDilation(this, 1.0f); if (ASOCharacter* H = Hero(); H && H->GetWeapon()) { H->GetWeapon()->StopFire(); } });
				}
				Do(bFirst ? 0.5f : 0.9f, [=]() { if (ASOCharacter* H = Hero()) { H->HandleAimPressed(); } });
				Snap(0.9f, FString::Printf(TEXT("v_%s_%s_3_aim"), *A, *S));
				Act([=]() { if (ASOCharacter* H = Hero(); H && H->GetWeapon()) { *Shots = H->GetWeapon()->GetShotsFired(); H->GetWeapon()->StartFire(); } });
				Snap(0.0f, FString::Printf(TEXT("v_%s_%s_4_aimfire"), *A, *S), Fired);
				Act([=, this]() { UGameplayStatics::SetGlobalTimeDilation(this, 1.0f); if (ASOCharacter* H = Hero()) { if (H->GetWeapon()) { H->GetWeapon()->StopFire(); } H->HandleAimReleased(); } });
				bFirst = false;
			}
		}
	}
	if (Set == 17)
	{
		// Meridian (L_Meridian): the torch in a dark shop of the mall, first person then third (files t*). The
		// operation is held so nothing walks in.
		for (TActorIterator<ASOOperation> It(GetWorld()); It; ++It)
		{
			It->SetActorTickEnabled(false);
		}
		Act([this, Hero, View]()
		{
			if (ASOCharacter* H = Hero())
			{
				H->SetActorLocation(FVector(-146200.0f, 2500.0f, 100.0f));      // plan E 25, N -1462: just inside a shop
				SetControlRotation(FRotator(-4.0f, 80.0f, 0.0f));
				H->SetFlashlight(true);
				View(ESOViewMode::FirstPerson);
				SetViewTarget(H);
			}
		});
		Snap(5.0f, TEXT("t1_torch_first"));
		Act([this]() { SetControlRotation(FRotator(-10.0f, 125.0f, 0.0f)); });
		Snap(1.5f, TEXT("t2_torch_first_side"));
		Act([this, View]() { View(ESOViewMode::ThirdPerson); SetControlRotation(FRotator(-6.0f, 80.0f, 0.0f)); });
		Snap(2.0f, TEXT("t3_torch_third"));
	}
	if (Set == 16)
	{
		// Meridian (L_Meridian): the operation's opening as a player sees it (files o*): why anyone goes, a line at a
		// time, then what comes over the radio at the first stage.
		for (int32 i = 1; i <= 8; ++i)
		{
			Snap(i == 1 ? 6.0f : 5.5f, FString::Printf(TEXT("o%d_opening"), i));
		}
	}
	if (Set == 9)
	{
		// Meridian (L_Meridian): a camera tour of the route, then each of the Altered posed in the plaza and the
		// Colossus on the Crown (files m*). The operation is held so no wave walks into the pictures.
		for (TActorIterator<ASOOperation> It(GetWorld()); It; ++It)
		{
			It->SetActorTickEnabled(false);
		}
		auto Cam = [this](const FVector& PlanEye, const FVector& PlanAt)
		{
			// plan metres (E, N, up) -> world cm (X = N, Y = E)
			const FVector Eye(PlanEye.Y * 100.0f, PlanEye.X * 100.0f, PlanEye.Z * 100.0f);
			const FVector At(PlanAt.Y * 100.0f, PlanAt.X * 100.0f, PlanAt.Z * 100.0f);
			if (!CaptureCamera)
			{
				CaptureCamera = GetWorld()->SpawnActor<ACameraActor>();
			}
			if (ACameraActor* CamActor = Cast<ACameraActor>(CaptureCamera)) { CamActor->GetCameraComponent()->SetFieldOfView(75.0f); }
			CaptureCamera->SetActorLocationAndRotation(Eye, (At - Eye).Rotation());
			SetViewTarget(CaptureCamera);
		};
		auto Pose = [this](UClass* Class, const FVector& Plan, float Yaw)
		{
			FActorSpawnParameters P;
			P.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AdjustIfPossibleButAlwaysSpawn;
			const ASOEnemy* Cdo = Cast<ASOEnemy>(Class->GetDefaultObject());
			const float Half = Cdo ? Cdo->GetCapsuleComponent()->GetScaledCapsuleHalfHeight() : 90.0f;
			if (ASOEnemy* E = GetWorld()->SpawnActor<ASOEnemy>(Class, FVector(Plan.Y * 100.0f, Plan.X * 100.0f, Plan.Z * 100.0f + Half + 5.0f), FRotator(0, Yaw, 0), P))
			{
				if (AController* AI = E->GetController())
				{
					AI->SetActorTickEnabled(false);
				}
			}
		};
		struct FView { const TCHAR* Name; FVector Eye, At; };
		const FView Views[] = {
			// the long way in (files s*): the city's edge, the estate, the mall, the station, the canal
			{ TEXT("s01_pad"), FVector(3, -2304, 1.7), FVector(0, -2200, 5) },
			{ TEXT("s02_toll"), FVector(4, -2152, 1.7), FVector(0, -2110, 3) },
			{ TEXT("s03_gatehouse"), FVector(0, -1980, 1.7), FVector(0, -1940, 5) },
			{ TEXT("s04_lobby"), FVector(0, -1957, 1.7), FVector(2, -1925, 1.6) },
			{ TEXT("s05_yard"), FVector(0, -1916, 1.7), FVector(0, -1840, 3) },
			{ TEXT("s06_alley"), FVector(0, -1786, 1.7), FVector(0, -1700, 4) },
			{ TEXT("s07_forecourt"), FVector(0, -1636, 1.7), FVector(0, -1598, 4) },
			{ TEXT("s08_mall"), FVector(0, -1594, 1.7), FVector(0, -1500, 3) },
			{ TEXT("s09_gallery"), FVector(-15, -1566, 6.7), FVector(4, -1470, 4) },
			{ TEXT("s10_rotunda"), FVector(-13, -1478, 1.7), FVector(2, -1448, 2) },
			{ TEXT("s11_gate"), FVector(0, -1362, 1.7), FVector(0, -1300, 2) },
			{ TEXT("s12_stair"), FVector(0, -1290, 1.7), FVector(0, -1245, -2) },
			{ TEXT("s13_hall"), FVector(0, -1233, -4.3), FVector(0, -1200, -4.6) },
			{ TEXT("s14_platform"), FVector(1, -1196, -4.3), FVector(0, -1120, -4.8) },
			{ TEXT("s15_tunnel"), FVector(0, -1086, -5.5), FVector(0, -1030, -5.5) },
			{ TEXT("s16_canal"), FVector(0, -877, -3.3), FVector(0, -800, -2) },
			{ TEXT("s17_pump"), FVector(3, -745, -3.3), FVector(0, -700, -1) },
			{ TEXT("s18_causeway"), FVector(45, -552, 1.7), FVector(30, -500, 2) },
			{ TEXT("s19_aerial_south"), FVector(150, -2250, 150), FVector(0, -1900, 0) },
			// each district's landmark, and the growth where it is thickest (files l*)
			{ TEXT("l1_tower"), FVector(6, -2300, 1.7), FVector(-47, -2292, 20) },
			{ TEXT("l2_gantry"), FVector(0, -2034, 1.7), FVector(0, -1988, 10) },
			{ TEXT("l3_slabs"), FVector(20, -1900, 1.7), FVector(-84, -1852, 45) },
			{ TEXT("l4_arch"), FVector(0, -1640, 1.7), FVector(0, -1604, 11) },
			{ TEXT("l5_canopy"), FVector(-12, -1292, 1.7), FVector(2, -1256, 5) },
			{ TEXT("l6_annex"), FVector(11, -788, -3.3), FVector(-48, -736, 9) },
			{ TEXT("l7_cooling"), FVector(-9, -792, -3.3), FVector(77, -764, 20) },
			{ TEXT("l8_gunship"), FVector(23, -478, 1.7), FVector(22, -503, 2.0) },
			{ TEXT("l9_dome"), FVector(26, -22, 1.7), FVector(-98, 16, 46) },
			{ TEXT("l10_grove"), FVector(9, -646, -3.3), FVector(-4, -668, 0) },
			{ TEXT("l11_moss"), FVector(40, -522, 1.7), FVector(31, -513, 0.3) },
			// the mall's shops (files i*), the things that stop the player and the buildings that can be walked into (files b*)
			{ TEXT("i1_concourse"), FVector(-4, -1594, 1.7), FVector(10, -1540, 2.4) },
			{ TEXT("i2_shop"), FVector(17, -1570, 1.7), FVector(30, -1570, 1.4) },
			{ TEXT("i3_books"), FVector(-17, -1474, 1.7), FVector(-30, -1474, 1.4) },
			{ TEXT("i4_cafe"), FVector(17, -1426, 1.7), FVector(30, -1426, 1.4) },
			{ TEXT("i5_inside"), FVector(24.5, -1543, 1.7), FVector(33, -1549, 1.2) },
			{ TEXT("i6_gallery"), FVector(-14, -1590, 6.7), FVector(-16, -1540, 7.2) },
			{ TEXT("b1_boxes"), FVector(7, -2298, 2.2), FVector(14, -2322, 5) },
			{ TEXT("b2_row"), FVector(-6, -2260, 1.7), FVector(44, -2236, 5) },
			{ TEXT("b3_door"), FVector(-28, -2290, 1.7), FVector(-39, -2292.2, 1.5) },
			{ TEXT("b4_inside"), FVector(-41.5, -2292.2, 1.7), FVector(-52, -2286, 1.3) },
			{ TEXT("b5_quarantine"), FVector(0, -1990, 1.7), FVector(-40, -1973, 5) },
			{ TEXT("b6_yard_block"), FVector(10, -1880, 1.7), FVector(-46, -1868, 5) },
			{ TEXT("b7_alley_room"), FVector(0, -1760, 1.7), FVector(9.5, -1750, 1.6) },
			{ TEXT("b8_forecourt"), FVector(0, -1625, 1.7), FVector(37, -1630, 5) },
			// the ground under the terraces and round the Crown, where a fall lands (files e*)
			{ TEXT("e1_yard"), FVector(74, 30, 1.7), FVector(88, 64, 9) },
			{ TEXT("e2_under_bridge"), FVector(4, 122, 1.7), FVector(0, 190, 9) },
			{ TEXT("e3_plate"), FVector(-22, 150, 1.7), FVector(-40, 172, 6) },
			{ TEXT("e4_ribs"), FVector(20, 236, 11.7), FVector(48, 250, 14) },
			{ TEXT("m1_approach"), FVector(2, -306, 1.7), FVector(0, -200, 9) },
			{ TEXT("m2_gate"), FVector(-6, -228, 1.7), FVector(0, -200, 10) },
			{ TEXT("m3_court"), FVector(10, -192, 2.0), FVector(-4, -140, 4) },
			{ TEXT("m4_boulevard"), FVector(-6, -130, 1.7), FVector(0, -60, 6) },
			{ TEXT("m5_ring"), FVector(18, -32, 2.0), FVector(-4, 6, 6) },
			{ TEXT("m6_ramp"), FVector(30, -3, 1.8), FVector(80, 2, 10) },
			{ TEXT("m7_terraces"), FVector(80, 6, 11.7), FVector(80, 90, 14) },
			{ TEXT("m8_north_leg"), FVector(70, 114, 11.7), FVector(0, 116, 13) },
			{ TEXT("m9_bridge"), FVector(0, 124, 11.7), FVector(0, 200, 18) },
			{ TEXT("m10_crown"), FVector(24, 168, 13.0), FVector(0, 205, 16) },
			{ TEXT("m11_aerial"), FVector(160, -260, 140), FVector(10, 0, 0) },
		};
		Do(8.0f, []() {});
		for (const FView& V : Views)
		{
			const FView Copy = V;
			Act([=]() { Cam(Copy.Eye, Copy.At); });
			// (a view far from the last one hitches while its district comes in: a still taken sooner showed the next view)
			Snap(2.6f, Copy.Name);
			// how fast this view draws: frames counted over the second after the still (the engine's running average
			// carried the hitch of arriving somewhere new, and read 2 fps for views that draw at 90)
			static uint64 PerfFrame = 0;
			static double PerfTime = 0.0;
			Act([]() { PerfFrame = GFrameCounter; PerfTime = FPlatformTime::Seconds(); });
			Do(1.0f, [Copy]()
			{
				const double Took = FPlatformTime::Seconds() - PerfTime;
				UE_LOG(LogShatteredOrbit, Log, TEXT("Perf: %s %.1f fps"), Copy.Name, Took > 0.0 ? double(GFrameCounter - PerfFrame) / Took : 0.0);
			});
		}
		// the Altered, lined up in the plaza; the Colossus on the Crown
		Act([=]()
		{
			Pose(ASORemnant::StaticClass(), FVector(-6, -26, 0), 180.0f);
			Pose(ASOVeilborn::StaticClass(), FVector(-2, -26, 0), 180.0f);
			Pose(ASOBulwark::StaticClass(), FVector(3, -26, 0), 180.0f);
			Pose(ASOEnemy::StaticClass(), FVector(8, -26, 0), 180.0f);
			Pose(ASOColossus::StaticClass(), FVector(6, 225, 10), 190.0f);
		});
		Act([=]() { Cam(FVector(1, -35, 1.8), FVector(1, -26, 1.2)); });
		Snap(2.5f, TEXT("m12_altered"));
		Act([=]() { Cam(FVector(24, 186, 12.0), FVector(6, 225, 15)); });
		Snap(1.5f, TEXT("m13_colossus"));
		// the nav mesh: a walkable path from the entry to the crown, and how much of the route has nav under it
		// (with every barrier open: a closed one cuts the nav mesh, as it should)
		Act([this]()
		{
			for (TActorIterator<ASOOperationBarrier> It(GetWorld()); It; ++It)
			{
				It->SetActorTickEnabled(false);
				It->SetOpen(true);
			}
		});
		Do(5.0f, []() {});
		// (the nav mesh is built as the level runs, and there is a lot of walked ground: wait for it to finish, up to two
		// minutes, or a leg in the last district to be built reads as broken)
		for (int32 i = 0; i < 14; ++i)
		{
			Do(1.0f, []() {}, [this]()
			{
				UNavigationSystemV1* N = FNavigationSystem::GetCurrent<UNavigationSystemV1>(GetWorld());
				return !N || !N->IsNavigationBuildInProgress();
			});
		}
		Act([this]()
		{
			const UNavigationSystemV1* N = FNavigationSystem::GetCurrent<UNavigationSystemV1>(GetWorld());
			UE_LOG(LogShatteredOrbit, Log, TEXT("Nav: %d build tasks left when the legs are checked"), N ? N->GetNumRemainingBuildTasks() : -1);
		});
		Act([this]()
		{
			UNavigationSystemV1* Nav = FNavigationSystem::GetCurrent<UNavigationSystemV1>(GetWorld());
			if (!Nav || !Nav->GetDefaultNavDataInstance(FNavigationSystem::DontCreate))
			{
				UE_LOG(LogShatteredOrbit, Warning, TEXT("Nav: no nav mesh"));
				return;
			}
			// (world cm: X = N, Y = E) the whole way from the landing pad, leg by leg, so a break names its district
			struct FLeg { const TCHAR* Name; FVector From, To; };
			const FLeg Legs[] = {
				{ TEXT("pad -> gatehouse"), FVector(-229000, 0, 50), FVector(-196400, 0, 50) },
				{ TEXT("gatehouse -> yard"), FVector(-196400, 0, 50), FVector(-190000, 0, 50) },
				{ TEXT("yard -> alley -> forecourt"), FVector(-190000, 0, 50), FVector(-161500, 0, 50) },
				{ TEXT("forecourt -> rotunda"), FVector(-161500, 0, 50), FVector(-147500, 600, 50) },
				{ TEXT("rotunda -> gallery (the escalator)"), FVector(-147500, 600, 50), FVector(-156000, -1500, 550) },
				{ TEXT("rotunda -> loading yard"), FVector(-147500, 600, 50), FVector(-128000, 0, 50) },
				{ TEXT("yard -> ticket hall"), FVector(-128000, 0, 50), FVector(-122000, 0, -550) },
				{ TEXT("hall -> platform -> tunnel"), FVector(-122000, 0, -550), FVector(-106000, 0, -670) },
				{ TEXT("platform -> a track bed"), FVector(-116000, 0, -550), FVector(-116000, 750, -670) },
				{ TEXT("tunnel (round the fall) -> canal"), FVector(-106000, 0, -670), FVector(-86000, 0, -450) },
				{ TEXT("canal -> spillway top"), FVector(-86000, 0, -450), FVector(-55500, 4500, 50) },
				{ TEXT("spillway -> old approach"), FVector(-55500, 4500, 50), FVector(-31000, 0, 50) },
				{ TEXT("old approach -> crown"), FVector(-30600, 200, 50), FVector(15000, 0, 1050) },
				// (the last one in pieces, so a break names its place)
				{ TEXT("ring -> ramp top"), FVector(-2000, 0, 50), FVector(0, 7600, 1050) },
				{ TEXT("ramp top -> north deck"), FVector(0, 8000, 1050), FVector(11400, 4000, 1050) },
				{ TEXT("north deck -> bridge"), FVector(11400, 4000, 1050), FVector(15000, 0, 1050) },
			};
			for (const FLeg& Leg : Legs)
			{
				const UNavigationPath* Path = Nav->FindPathToLocationSynchronously(GetWorld(), Leg.From, Leg.To);
				const bool bWhole = Path && Path->IsValid() && !Path->IsPartial();
				UE_LOG(LogShatteredOrbit, Log, TEXT("Nav: %s %s (%d points, %.0f m%s)"), Leg.Name, bWhole ? TEXT("found") : TEXT("NOT FOUND"),
					Path ? Path->PathPoints.Num() : 0, Path ? Path->GetPathLength() / 100.0f : 0.0f, Path && Path->IsPartial() ? TEXT(", partial") : TEXT(""));
				if (!bWhole && Path && Path->PathPoints.Num() > 0)
				{
					// where it stops (plan metres): the break is just past this
					const FVector End = Path->PathPoints.Last();
					UE_LOG(LogShatteredOrbit, Warning, TEXT("Nav:   it stops at E %.1f N %.1f z %.1f"), End.Y / 100.0f, End.X / 100.0f, End.Z / 100.0f);
				}
			}
			int32 On = 0, Total = 0;
			for (float N = -229000.0f; N <= 22000.0f; N += 2000.0f)
			{
				for (const float E : { -1000.0f, 0.0f, 1000.0f, 8000.0f })
				{
					FNavLocation L;
					++Total;
					On += Nav->ProjectPointToNavigation(FVector(N, E, 500.0f), L, FVector(200.0f, 200.0f, 1200.0f)) ? 1 : 0;
				}
			}
			UE_LOG(LogShatteredOrbit, Log, TEXT("Nav: %d of %d probes along the route have nav"), On, Total);
			// every creature of every wave has a floor to stand on where the plan puts it
			for (TActorIterator<ASOOperation> It(GetWorld()); It; ++It)
			{
				TArray<FString> Problems;
				It->AuditSpawns(Problems);
				for (const FString& Problem : Problems)
				{
					UE_LOG(LogShatteredOrbit, Warning, TEXT("Operation audit: no floor for %s"), *Problem);
				}
			}
		});
		Do(0.5f, []() {});
		GetWorldTimerManager().SetTimer(CaptureTimer, this, &ASOPlayerController::CaptureStep, 0.02f, true);
		return;
	}
	if (Set == 10 || Set == 11)
	{
		// The holds (files g_<body>_<gun>_<n>): every gun in the hands of one body (10 = male, 11 = female), close on
		// the firing hand, the support hand and from above in third person, the first-person view, then jogging and
		// sprinting from the side. For checking that the fingers close on every grip and nothing passes through.
		const FString Body = Set == 10 ? TEXT("male") : TEXT("female");
		static const TCHAR* Guns[] = {
			TEXT("auto"), TEXT("pulse"), TEXT("scout"), TEXT("handcannon"), TEXT("shotgun"), TEXT("sniper"), TEXT("smg"), TEXT("sidearm"),
			TEXT("energy"), TEXT("hmg"), TEXT("rocket"), TEXT("rifle"), TEXT("carbine"), TEXT("dmr"), TEXT("ksmg"), TEXT("bolt"), TEXT("pistol"),
			TEXT("revolver"), TEXT("pump"), TEXT("spitter"), TEXT("bile"), TEXT("brood"), TEXT("vr_rifle"), TEXT("vr_sniper"), TEXT("vr_smg"),
			TEXT("vr_shotgun"), TEXT("vr_lmg"), TEXT("vr_handcannon"), TEXT("vr_pistol"), TEXT("vr_fusion"), TEXT("vr_rocket") };
		auto EquipGun = [Hero](const FString& Arch)
		{
			if (ASOCharacter* H = Hero())
			{
				FRandomStream Rng(FCrc::StrCrc32(*Arch));
				H->EquipInstance(USOLootLibrary::MakeWeapon(*Arch, 2, 20, Rng));
			}
		};
		// a camera close on the held gun (yaw relative to the facing: +90 = from the character's right)
		auto Close = [this, Hero](float Yaw, float Distance, float Height, int32 On = 0)
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
			FVector Focus = H->GetActorLocation() + FVector(0, 0, 40.0f);
			if (const ASOWeapon* W = H->GetWeapon())
			{
				if (const USOGunRigComponent* Rig = W->GetThirdPersonRig())
				{
					// 0 = the whole hold, 1 = the firing hand on the grip, 2 = the support hand
					Focus = On == 1 ? Rig->GetComponentLocation() - Rig->GetForwardVector() * 1.0f - Rig->GetUpVector() * 5.0f
						: (On == 2 ? H->GetMesh()->GetBoneLocation(TEXT("hand_L")) : Rig->GetComponentLocation() + Rig->GetForwardVector() * 12.0f);
				}
			}
			const FRotator Around(0.0f, H->GetActorRotation().Yaw + Yaw, 0.0f);
			const FVector Eye = Focus + Around.Vector() * Distance + FVector(0, 0, Height);
			CaptureCamera->SetActorLocationAndRotation(Eye, (Focus - Eye).Rotation());
			if (ACameraActor* Cam = Cast<ACameraActor>(CaptureCamera)) { Cam->GetCameraComponent()->SetFieldOfView(On == 0 ? 50.0f : 34.0f); }
			SetViewTarget(CaptureCamera);
		};
		TSharedRef<FTransform> Start = MakeShared<FTransform>();
		auto Back = [Hero, Start, this]()
		{
			if (ASOCharacter* H = Hero())
			{
				CaptureMove = FVector2D::ZeroVector;
				H->HandleSprintReleased();
				H->TeleportTo(Start->GetLocation(), Start->Rotator());
				H->GetCharacterMovement()->StopMovementImmediately();
				SetControlRotation(Start->Rotator());
			}
		};
		Do(6.0f, [=, this]()
		{
			ConsoleCommand(TEXT("DisableAllScreenMessages"));
			if (USOInventoryComponent* Inv = SOFindInventory(this)) { Inv->SetBody(*Body); }
			if (ASOCharacter* H = Hero())
			{
				SetControlRotation(FRotator(0.0f, H->GetActorRotation().Yaw + 90.0f, 0.0f));   // the open side of the range
				*Start = FTransform(FRotator(0.0f, H->GetActorRotation().Yaw + 90.0f, 0.0f), H->GetActorLocation());
			}
		});
		Do(1.0f, [=]() { Back(); });
		for (const TCHAR* G : Guns)
		{
			const FString A = G;
			Do(0.3f, [=]() { EquipGun(A); View(ESOViewMode::ThirdPerson); });
			Do(0.9f, [=]() { Close(80.0f, 60.0f, 6.0f, 1); });
			Snap(0.15f, FString::Printf(TEXT("g_%s_%s_1_right"), *Body, *A));
			Act([=]() { Close(-80.0f, 60.0f, 6.0f, 2); });
			Snap(0.15f, FString::Printf(TEXT("g_%s_%s_2_left"), *Body, *A));
			Act([=]() { Close(55.0f, 45.0f, -55.0f, 0); });
			Snap(0.15f, FString::Printf(TEXT("g_%s_%s_3_front"), *Body, *A));
			Act([=]() { Close(-125.0f, 55.0f, 22.0f, 1); });
			Snap(0.15f, FString::Printf(TEXT("g_%s_%s_7_thumb"), *Body, *A));
			Act([=, this]() { View(ESOViewMode::FirstPerson); if (ASOCharacter* H = Hero()) { SetViewTarget(H); } });
			Snap(0.5f, FString::Printf(TEXT("g_%s_%s_4_fp"), *Body, *A));
			Act([=, this]() { View(ESOViewMode::ThirdPerson); CaptureMove = FVector2D(0.0f, 1.0f); });
			Do(0.8f, [=]() { Close(90.0f, 150.0f, 15.0f); });
			Snap(0.0f, FString::Printf(TEXT("g_%s_%s_5_jog"), *Body, *A));
			Act([=]() { if (ASOCharacter* H = Hero()) { H->HandleSprintPressed(); } });
			Do(0.8f, [=]() { Close(90.0f, 150.0f, 15.0f); });
			Snap(0.0f, FString::Printf(TEXT("g_%s_%s_6_sprint"), *Body, *A));
			Do(0.05f, [=]() { Back(); });
		}
		// the loadout worn: each slot in hand in turn, the other two on the back / at the hip (files h_<body>_<slot>_<view>)
		for (int32 Slot = 0; Slot < 3; ++Slot)
		{
			Do(0.4f, [=, this]()
			{
				if (ASOCharacter* H = Hero())
				{
					if (Slot == 0) { H->HandleWeapon1(); } else if (Slot == 1) { H->HandleWeapon2(); } else { H->HandleWeapon3(); }
					if (USOInventoryComponent* Inv = SOFindInventory(this)) { Inv->SelectSlot(Slot); }
					View(ESOViewMode::ThirdPerson);
				}
			});
			Do(1.6f, [=]() { Orbit(180.0f, 230.0f, 30.0f); });
			Snap(0.2f, FString::Printf(TEXT("h_%s_%d_1_back"), *Body, Slot));
			Act([=]() { Orbit(235.0f, 230.0f, 30.0f); });
			Snap(0.2f, FString::Printf(TEXT("h_%s_%d_2_backright"), *Body, Slot));
			Act([=]() { Orbit(60.0f, 230.0f, 20.0f); });
			Snap(0.2f, FString::Printf(TEXT("h_%s_%d_3_frontright"), *Body, Slot));
			Act([=]() { Orbit(-60.0f, 230.0f, 20.0f); });
			Snap(0.2f, FString::Printf(TEXT("h_%s_%d_4_frontleft"), *Body, Slot));
		}
		Do(0.5f, []() {});
		GetWorldTimerManager().SetTimer(CaptureTimer, this, &ASOPlayerController::CaptureStep, 0.02f, true);
		return;
	}
	if (Set == 14 || Set == 15)
	{
		// The body in motion (files m_<body>_<n>): in slow motion from the side, a turn on the spot (the feet stay), a
		// jump at take-off, at the top and coming down, a vault over a low wall, a mantle onto a 2 m ledge and a climb
		// up a 3.3 m one. For checking that the pose follows the motion and the hands land on the edges.
		const FString Body = Set == 14 ? TEXT("male") : TEXT("female");
		TSharedRef<FTransform> Start = MakeShared<FTransform>();
		TSharedRef<TArray<TWeakObjectPtr<AActor>>> Walls = MakeShared<TArray<TWeakObjectPtr<AActor>>>();
		auto Slow = [this](float Rate) { UGameplayStatics::SetGlobalTimeDilation(this, Rate); };
		// a block in front of where the character starts: Near cm ahead, Deep cm deep, High cm high
		auto Wall = [this, Start, Walls](float Near, float Deep, float High)
		{
			// (3 m wide: the camera sees the body past its end)
			AStaticMeshActor* A = GetWorld()->SpawnActor<AStaticMeshActor>();
			UStaticMeshComponent* M = A->GetStaticMeshComponent();
			M->SetMobility(EComponentMobility::Movable);
			M->SetStaticMesh(LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube")));
			M->SetCollisionProfileName(UCollisionProfile::BlockAll_ProfileName);
			const FVector Fwd = Start->GetRotation().GetForwardVector();
			const float Floor = static_cast<float>(Start->GetLocation().Z) - 90.0f;
			A->SetActorLocationAndRotation(FVector(Start->GetLocation().X, Start->GetLocation().Y, Floor + High * 0.5f) + Fwd * (Near + Deep * 0.5f), Start->GetRotation());
			A->SetActorScale3D(FVector(Deep / 100.0f, 3.0f, High / 100.0f));
			Walls->Add(A);
		};
		auto Reset = [this, Hero, Start, Walls, Slow]()
		{
			Slow(1.0f);
			for (const TWeakObjectPtr<AActor>& W : *Walls)
			{
				if (W.IsValid())
				{
					W->Destroy();
				}
			}
			Walls->Reset();
			if (ASOCharacter* H = Hero())
			{
				CaptureMove = FVector2D::ZeroVector;
				H->HandleSprintReleased();
				H->HandleJumpReleased();
				H->TeleportTo(Start->GetLocation(), Start->Rotator());
				H->GetCharacterMovement()->StopMovementImmediately();
				SetControlRotation(Start->Rotator());
			}
		};
		// from the character's right, level with the chest, looking at a point Ahead cm in front of the start
		auto Side = [this, Start](float Ahead, float Up, float Distance, float YawOff = 0.0f)
		{
			if (!CaptureCamera)
			{
				CaptureCamera = GetWorld()->SpawnActor<ACameraActor>();
			}
			const FVector Focus = Start->GetLocation() + Start->GetRotation().GetForwardVector() * Ahead + FVector(0, 0, Up);
			const FVector Eye = Focus + FRotator(0.0f, Start->Rotator().Yaw + 90.0f + YawOff, 0.0f).Vector() * Distance + FVector(0, 0, 25.0f);
			CaptureCamera->SetActorLocationAndRotation(Eye, (Focus - Eye).Rotation());
			if (ACameraActor* Cam = Cast<ACameraActor>(CaptureCamera)) { Cam->GetCameraComponent()->SetFieldOfView(50.0f); }
			SetViewTarget(CaptureCamera);
		};
		Do(6.0f, [=, this]()
		{
			ConsoleCommand(TEXT("DisableAllScreenMessages"));
			if (USOInventoryComponent* Inv = SOFindInventory(this)) { Inv->SetBody(*Body); }
			if (ASOCharacter* H = Hero())
			{
				*Start = FTransform(FRotator(0.0f, H->GetActorRotation().Yaw + 90.0f, 0.0f), H->GetActorLocation());
				View(ESOViewMode::ThirdPerson);
			}
		});
		Do(1.0f, [=]() { Reset(); });
		// 1. a turn on the spot: the aim goes 40 degrees round, the feet stay
		Do(1.0f, [=]() { Side(0.0f, 0.0f, 300.0f, -55.0f); });
		Snap(0.3f, FString::Printf(TEXT("m_%s_1_stand"), *Body));
		Act([=, this]() { SetControlRotation(FRotator(0.0f, Start->Rotator().Yaw + 40.0f, 0.0f)); });
		Snap(0.6f, FString::Printf(TEXT("m_%s_2_turned"), *Body));
		Do(0.1f, [=]() { Reset(); });
		// 2. a jump: off the ground, at the top, coming down
		Do(0.6f, [=]() { Side(0.0f, 40.0f, 380.0f, -55.0f); Slow(0.2f); if (ASOCharacter* H = Hero()) { H->HandleJumpPressed(); } });
		Snap(0.07f, FString::Printf(TEXT("m_%s_3_takeoff"), *Body));
		Snap(0.25f, FString::Printf(TEXT("m_%s_4_top"), *Body));
		Snap(0.24f, FString::Printf(TEXT("m_%s_5_down"), *Body));
		Snap(0.07f, FString::Printf(TEXT("m_%s_5b_land"), *Body), [Hero]() { const ASOCharacter* H = Hero(); return H && H->GetCharacterMovement()->IsMovingOnGround(); });
		Do(0.3f, [=]() { Reset(); });
		// 2b. crouched, then the slow walk, the run and the sprint from the side
		Do(0.5f, [=]() { if (ASOCharacter* H = Hero()) { H->Crouch(); } Side(0.0f, 0.0f, 300.0f, -55.0f); });
		Snap(0.6f, FString::Printf(TEXT("m_%s_12_crouch"), *Body));
		Act([=, this]() { CaptureMove = FVector2D(0.0f, 0.34f); });
		Do(1.1f, [=]() { Orbit(80.0f, 300.0f, 10.0f); });
		Snap(0.0f, FString::Printf(TEXT("m_%s_13_crouch_walk"), *Body));
		// ...and through the player's own eyes: standing for comparison, then crouched still and moving
		Act([=, this]() { CaptureMove = FVector2D::ZeroVector; if (ASOCharacter* H = Hero()) { H->UnCrouch(); H->SetViewMode(ESOViewMode::FirstPerson); SetViewTarget(H); } });
		Snap(0.9f, FString::Printf(TEXT("m_%s_13a_fp_stand"), *Body));
		Act([=]() { if (ASOCharacter* H = Hero()) { H->Crouch(); } });
		Snap(0.9f, FString::Printf(TEXT("m_%s_13b_fp_crouch"), *Body));
		Act([=, this]() { CaptureMove = FVector2D(0.0f, 1.0f); });
		Snap(0.7f, FString::Printf(TEXT("m_%s_13c_fp_crouch_walk"), *Body));
		Act([=, this]() { CaptureMove = FVector2D::ZeroVector; if (ASOCharacter* H = Hero()) { H->SetViewMode(ESOViewMode::ThirdPerson); } });
		Do(0.1f, [=]() { if (ASOCharacter* H = Hero()) { H->UnCrouch(); } Reset(); });
		for (int32 Pace = 0; Pace < 5; ++Pace)
		{
			// (the last two: a strafe to the right and the run again, both seen from behind: the waist and the track)
			static const TCHAR* Names[5] = { TEXT("14_stroll"), TEXT("15_run"), TEXT("16_sprint"), TEXT("17_strafe"), TEXT("18_run_behind") };
			Do(0.5f, [=, this]()
			{
				CaptureMove = Pace == 3 ? FVector2D(1.0f, 0.0f) : FVector2D(0.0f, Pace == 0 ? 0.34f : 1.0f);
				if (ASOCharacter* H = Hero(); H && Pace == 2) { H->HandleSprintPressed(); }
			});
			for (int32 Take = 0; Take < 3; ++Take)
			{
				Do(Take == 0 ? 1.0f : (Pace == 0 ? 0.26f : 0.12f), [=]() { Orbit(Pace >= 3 ? 180.0f : 80.0f, 520.0f, 10.0f); });
				Snap(0.0f, FString::Printf(TEXT("m_%s_%s_%d"), *Body, Names[Pace], Take));
			}
			Do(0.1f, [=]() { Reset(); });
		}
		// 3. a vault over a low wall at a sprint
		Do(0.5f, [=, this]() { Wall(330.0f, 40.0f, 90.0f); Side(350.0f, 40.0f, 330.0f, -35.0f); Slow(0.2f); CaptureMove = FVector2D(0.0f, 1.0f); if (ASOCharacter* H = Hero()) { H->HandleSprintPressed(); } });
		Snap(0.0f, FString::Printf(TEXT("m_%s_6_vault_a"), *Body), [Hero]() { const ASOCharacter* H = Hero(); return H && H->GetSOMovement()->GetMantleAlpha() > 0.3f; });
		Snap(0.0f, FString::Printf(TEXT("m_%s_7_vault_b"), *Body), [Hero]() { const ASOCharacter* H = Hero(); return H && (H->GetSOMovement()->GetMantleAlpha() > 0.6f || !H->GetSOMovement()->IsMantling()); });
		Do(0.3f, [=]() { Reset(); });
		// 4. a mantle onto a 2 m ledge
		Do(0.5f, [=, this]() { Wall(170.0f, 300.0f, 200.0f); Side(150.0f, 150.0f, 400.0f); Slow(0.2f); CaptureMove = FVector2D(0.0f, 1.0f); if (ASOCharacter* H = Hero()) { H->HandleJumpPressed(); } });
		Snap(0.0f, FString::Printf(TEXT("m_%s_8_mantle_a"), *Body), [Hero]() { const ASOCharacter* H = Hero(); return H && H->GetSOMovement()->GetMantleAlpha() > 0.3f; });
		Snap(0.0f, FString::Printf(TEXT("m_%s_9_mantle_b"), *Body), [Hero]() { const ASOCharacter* H = Hero(); return H && (H->GetSOMovement()->GetMantleAlpha() > 0.55f || !H->GetSOMovement()->IsMantling()); });
		Do(0.3f, [=]() { Reset(); });
		// 5. a climb up a 3.3 m ledge
		Do(0.5f, [=, this]() { Wall(170.0f, 300.0f, 330.0f); Side(150.0f, 230.0f, 520.0f); Slow(0.2f); CaptureMove = FVector2D(0.0f, 1.0f); if (ASOCharacter* H = Hero()) { H->HandleJumpPressed(); } });
		Snap(0.0f, FString::Printf(TEXT("m_%s_10_climb_a"), *Body), [Hero]() { const ASOCharacter* H = Hero(); return H && H->GetSOMovement()->GetMantleAlpha() > 0.22f; });
		Snap(0.0f, FString::Printf(TEXT("m_%s_11_climb_b"), *Body), [Hero]() { const ASOCharacter* H = Hero(); return H && (H->GetSOMovement()->GetMantleAlpha() > 0.6f || !H->GetSOMovement()->IsMantling()); });
		Do(0.3f, [=]() { Reset(); });
		Do(0.5f, []() {});
		GetWorldTimerManager().SetTimer(CaptureTimer, this, &ASOPlayerController::CaptureStep, 0.02f, true);
		return;
	}
	if (Set == 12 || Set == 13)
	{
		// The loadout worn (files w_<body>_<loadout>_<slot in hand>_<view>): three loadouts (three long guns; a rifle,
		// a sidearm and a launcher; the Void Requiem set), each slot in hand in turn, from behind, three-quarter and
		// the right side: every worn gun in a place of its own, nothing stacked.
		const FString Body = Set == 12 ? TEXT("male") : TEXT("female");
		static const TCHAR* Loadouts[3][3] = {
			{ TEXT("rifle"), TEXT("shotgun"), TEXT("hmg") },
			{ TEXT("auto"), TEXT("sidearm"), TEXT("rocket") },
			{ TEXT("vr_rifle"), TEXT("vr_handcannon"), TEXT("vr_lmg") } };
		Do(6.0f, [=, this]()
		{
			ConsoleCommand(TEXT("DisableAllScreenMessages"));
			if (USOInventoryComponent* Inv = SOFindInventory(this)) { Inv->SetBody(*Body); }
			if (ASOCharacter* H = Hero()) { SetControlRotation(FRotator(0.0f, H->GetActorRotation().Yaw + 90.0f, 0.0f)); }
		});
		for (int32 L = 0; L < 3; ++L)
		{
			Do(0.6f, [=, this]()
			{
				if (USOInventoryComponent* Inv = SOFindInventory(this))
				{
					for (const TCHAR* Arch : Loadouts[L])
					{
						FRandomStream Rng(FCrc::StrCrc32(Arch));
						Inv->Equip(Inv->AddWeapon(USOLootLibrary::MakeWeapon(Arch, 2, 20, Rng), false).Uid);
					}
				}
			});
			for (int32 Slot = 0; Slot < 3; ++Slot)
			{
				Do(0.4f, [=, this]()
				{
					if (USOInventoryComponent* Inv = SOFindInventory(this)) { Inv->SelectSlot(Slot); }
					View(ESOViewMode::ThirdPerson);
				});
				Do(1.4f, [=]() { Orbit(180.0f, 260.0f, 30.0f); });
				Snap(0.2f, FString::Printf(TEXT("w_%s_%d_%d_1_back"), *Body, L, Slot));
				Act([=]() { Orbit(232.0f, 260.0f, 30.0f); });
				Snap(0.2f, FString::Printf(TEXT("w_%s_%d_%d_2_quarter"), *Body, L, Slot));
				Act([=]() { Orbit(270.0f, 260.0f, 10.0f); });
				Snap(0.2f, FString::Printf(TEXT("w_%s_%d_%d_3_side"), *Body, L, Slot));
			}
		}
		Do(0.5f, []() {});
		GetWorldTimerManager().SetTimer(CaptureTimer, this, &ASOPlayerController::CaptureStep, 0.02f, true);
		return;
	}
	if (Set == 4)
	{
		// Nexus Prime (L_Nexus): the start, street level in three districts, a gate, aerials by day and at night.
		// Plan metres (E, N) -> world (X = N, Y = E); each view waits for Nanite / Lumen to settle.
		auto CityView = [this](double E, double N, double Z, float Yaw, float Pitch, float Fov)
		{
			if (!CaptureCamera)
			{
				CaptureCamera = GetWorld()->SpawnActor<ACameraActor>();
			}
			CaptureCamera->SetActorLocationAndRotation(FVector(N * 100.0, E * 100.0, Z * 100.0), FRotator(Pitch, Yaw, 0.0f));
			if (ACameraActor* Cam = Cast<ACameraActor>(CaptureCamera))
			{
				Cam->GetCameraComponent()->SetFieldOfView(Fov);
			}
			SetViewTarget(CaptureCamera);
		};
		auto Hour = [this](float H) { if (USOTimeOfDaySubsystem* T = GetWorld()->GetSubsystem<USOTimeOfDaySubsystem>()) { T->SetHour(H); T->SetPaused(true); } };
		struct FCityShot { const TCHAR* Name; double E, N, Z, Yaw, Pitch, Fov; float Hour; };
		static const FCityShot Shots[] = {
			{ TEXT("n1_spire_plaza"), 0, -330, 1.8, 0, 8, 80, 15.5f },
			{ TEXT("n2_market_street"), -2394, 0, 1.8, 0, 2, 80, 15.5f },
			{ TEXT("n3_core_avenue"), 0, -900, 1.8, 0, 6, 80, 15.5f },
			{ TEXT("n4_research"), 1500, 1100, 1.8, 90, 4, 80, 15.5f },
			{ TEXT("n5_south_gate"), 0, -2850, 2.0, 180, 6, 80, 15.5f },
			{ TEXT("n6_aerial_core"), -900, -1400, 420, 35, -22, 70, 15.5f },
			{ TEXT("n7_aerial_city"), 0, -5200, 1300, 0, -16, 70, 15.5f },
			{ TEXT("n8_rail_viaduct"), -1200, -250, 1.8, 0, 8, 80, 15.5f },
			{ TEXT("n11_refuge_park"), 0, -1600, 40, 180, -18, 80, 15.5f },
			// street level at the places the dressing made (tools/city/nexus_dress.py, data of 2026-11-07)
			{ TEXT("v1_shop_street"), -2042.2, 314.2, 1.7, -160.7, 4.0, 80, 14.5f },
			{ TEXT("v2_apartments"), 1514.5, -708.4, 1.7, 57.1, 8.0, 80, 14.5f },
			{ TEXT("v3_loading_docks"), -2534.9, -2328.8, 2.5, 48.4, -2.0, 80, 14.5f },
			{ TEXT("v4_office_lobby"), -398.1, 1081.3, 1.7, 131.2, 12.0, 80, 14.5f },
			{ TEXT("v5_abandoned"), 3779.8, -2275.9, 1.7, 168.0, 2.0, 80, 14.5f },
			{ TEXT("v6_fire_station"), -548.9, -2774.7, 1.7, 131.2, 3.0, 80, 14.5f },
			{ TEXT("v7_building_site"), -3941.4, 500.3, 1.7, 118.4, 14.0, 80, 14.5f },
			{ TEXT("v8_car_park"), -50.7, 2026.4, 2.5, -63.4, -4.0, 80, 14.5f },
			{ TEXT("v9_checkpoint"), 0.0, 2096.1, 1.8, 180.0, 2.0, 80, 14.5f },
			{ TEXT("v10_crew_site"), -1850.3, -996.9, 1.8, -11.8, -3.0, 80, 14.5f },
			{ TEXT("n9_night_core"), -900, -1400, 420, 35, -22, 70, 21.5f },
			{ TEXT("n10_night_street"), 0, -900, 1.8, 0, 6, 80, 21.5f },
		};
		Do(8.0f, [=, this]() { Look(0.0f); ConsoleCommand(TEXT("DisableAllScreenMessages")); });
		Snap(0.5f, TEXT("n0_start"));
		for (const FCityShot& S : Shots)
		{
			const FCityShot Copy = S;
			Do(0.2f, [=]() { Hour(Copy.Hour); CityView(Copy.E, Copy.N, Copy.Z, float(Copy.Yaw), float(Copy.Pitch), float(Copy.Fov)); });
			Snap(6.0f, Copy.Name);
		}
		// the weather (USOWeatherSubsystem): each state set at once, the streets soaked for the wet ones
		struct FWeatherShot { const TCHAR* Name; ESOWeather Weather; float Wet; double E, N, Z, Yaw, Pitch; };
		static const FWeatherShot WeatherShots[] = {
			{ TEXT("w1_rain_avenue"), ESOWeather::Rain, 0.9f, 0, -900, 1.8, 0, 4 },
			{ TEXT("w2_storm_aerial"), ESOWeather::Storm, 1.0f, -900, -1400, 420, 35, -22 },
			{ TEXT("w3_fog_market"), ESOWeather::Fog, 0.3f, -2394, 0, 1.8, 0, 2 },
			{ TEXT("w4_windy_street"), ESOWeather::Windy, 0.0f, -2042.2, 314.2, 1.7, -160.7, -8 },
			{ TEXT("w5_steam_crew_site"), ESOWeather::Rain, 0.8f, -1850.3, -996.9, 1.8, -11.8, -3 },
			{ TEXT("w6_smoke_industry"), ESOWeather::Overcast, 0.2f, 2216.4, -2664.4, 35.0, 45.0, 2 },
		};
		auto Weather = [this](ESOWeather W, float Wet) { if (USOWeatherSubsystem* S = GetWorld()->GetSubsystem<USOWeatherSubsystem>()) { S->bAutomatic = false; S->SetWeather(W, 0.0f); S->SetWetness(Wet); } };
		for (const FWeatherShot& S : WeatherShots)
		{
			const FWeatherShot Copy = S;
			Do(0.2f, [=]() { Hour(14.5f); Weather(Copy.Weather, Copy.Wet); CityView(Copy.E, Copy.N, Copy.Z, float(Copy.Yaw), float(Copy.Pitch), 80.0f); });
			Snap(7.0f, Copy.Name);
		}
		Do(0.5f, []() {});
		GetWorldTimerManager().SetTimer(CaptureTimer, this, &ASOPlayerController::CaptureStep, 0.02f, true);
		return;
	}
	if (Set == 3)
	{
		// Head study: both bodies, as worn and bald (hair and coat off), from eight angles at 75 cm with a 30 degree
		// lens: the same framing the MetaHuman reference shots use.
		auto HeadView = [this, Hero](float Yaw, float Pitch)
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
			const FVector Focus = H->GetMesh()->GetBoneLocation(TEXT("head")) + FVector(0, 0, 6.0f);
			const FRotator Around(Pitch, H->GetActorRotation().Yaw + Yaw, 0.0f);
			const FVector Eye = Focus + Around.Vector() * 75.0f;
			CaptureCamera->SetActorLocationAndRotation(Eye, (Focus - Eye).Rotation());
			if (ACameraActor* Cam = Cast<ACameraActor>(CaptureCamera))
			{
				Cam->GetCameraComponent()->SetFieldOfView(50.9f);   // 30 degrees vertically at 16:9, as the reference shots
			}
			SetViewTarget(CaptureCamera);
		};
		struct FView { const TCHAR* Name; float Yaw; float Pitch; };
		static const FView Views[] = { { TEXT("a_front"), 0, 0 }, { TEXT("b_3q_left"), 45, 0 }, { TEXT("c_profile_left"), 90, 0 },
			{ TEXT("d_back_3q_left"), 135, 0 }, { TEXT("e_back"), 180, 0 }, { TEXT("f_3q_right"), -45, 0 }, { TEXT("g_profile_right"), -90, 0 },
			{ TEXT("h_above"), 20, 40 } };
		Do(4.0f, [=, this]() { Look(0.0f); View(ESOViewMode::ThirdPerson); if (ASOWeapon* W = Weapon()) { W->SetActorHiddenInGame(true); } });
		for (const TCHAR* Sex : { TEXT("male"), TEXT("female") })
		{
			for (int32 Bald = 0; Bald < 2; ++Bald)
			{
				const FString SexName(Sex);
				Act([=, this]()
				{
					if (USOInventoryComponent* Inv = SOFindInventory(this)) { Inv->SetBody(FName(*SexName)); }
				});
				Do(0.8f, [=, this]()
				{
					if (ASOCharacter* H = Hero())
					{
						FSOOutfit O = H->GetOutfit();
						if (Bald)
						{
							O.Set(TEXT("hair"), TEXT("none"));
							O.Set(TEXT("outer"), TEXT("none"));
							O.Set(TEXT("head"), TEXT("none"));
						}
						H->SetOutfit(O);
						if (ASOWeapon* W = Weapon()) { W->SetActorHiddenInGame(true); }
					}
				});
				for (const FView& V : Views)
				{
					const FString Name = FString::Printf(TEXT("head_%s_%s_%s"), Sex, Bald ? TEXT("bald") : TEXT("worn"), V.Name);
					const float Yaw = V.Yaw, Pitch = V.Pitch;
					Do(0.6f, [=]() { HeadView(Yaw, Pitch); });
					Snap(0.3f, Name);
				}
			}
		}
		Do(0.5f, []() {});
		GetWorldTimerManager().SetTimer(CaptureTimer, this, &ASOPlayerController::CaptureStep, 0.02f, true);
		return;
	}
	if (Set == 8)
	{
		// In motion, both bodies in their outfits (files c_<body>_*): jog, sprint, slide, jump from the side and behind,
		// a third-person reload, a weapon swap, an idle variation.
		TSharedRef<FTransform> Start = MakeShared<FTransform>();
		auto Reset = [=, this]()
		{
			CaptureMove = FVector2D::ZeroVector;
			if (ASOCharacter* H = Hero())
			{
				H->HandleSprintReleased();
				H->HandleCrouchReleased();
				H->TeleportTo(Start->GetLocation(), Start->Rotator());
				H->GetCharacterMovement()->StopMovementImmediately();
				SetControlRotation(Start->Rotator());
				SetViewTarget(H);
			}
		};
		Do(4.0f, [=, this]()
		{
			View(ESOViewMode::ThirdPerson);
			if (ASOCharacter* H = Hero())
			{
				SetControlRotation(FRotator(0.0f, H->GetActorRotation().Yaw + 90.0f, 0.0f));   // the open side of the range
				*Start = FTransform(FRotator(0.0f, H->GetActorRotation().Yaw + 90.0f, 0.0f), H->GetActorLocation());
			}
		});
		for (const TCHAR* Body : { TEXT("male"), TEXT("female") })
		{
			const FString B = Body;
			Act([=, this]() { if (USOInventoryComponent* Inv = SOFindInventory(this)) { Inv->SetBody(*B); } Reset(); });
			Do(1.5f, [=, this]() { CaptureMove = FVector2D(0.0f, 1.0f); });
			Do(1.2f, [=]() { Orbit(90.0f, 380.0f, 40.0f); });
			Snap(0.0f, FString::Printf(TEXT("c_%s_1_jog_side"), Body));
			Do(0.35f, [=]() { Orbit(90.0f, 380.0f, 40.0f); });
			Snap(0.0f, FString::Printf(TEXT("c_%s_2_jog_side"), Body));
			Do(0.1f, [=]() { Orbit(200.0f, 360.0f, 60.0f); });
			Snap(0.0f, FString::Printf(TEXT("c_%s_3_jog_behind"), Body));
			Act([=]() { if (ASOCharacter* H = Hero()) { H->HandleSprintPressed(); } });
			Do(1.0f, [=]() { Orbit(90.0f, 420.0f, 40.0f); });
			Snap(0.0f, FString::Printf(TEXT("c_%s_4_sprint_side"), Body));
			Do(0.15f, [=]() { Orbit(90.0f, 420.0f, 40.0f); });
			Snap(0.0f, FString::Printf(TEXT("c_%s_5_sprint_side"), Body));
			Act([=]() { if (ASOCharacter* H = Hero()) { H->HandleCrouchPressed(); } });
			Do(0.25f, [=]() { Orbit(90.0f, 380.0f, 30.0f); });
			Snap(0.0f, FString::Printf(TEXT("c_%s_6_slide"), Body));
			Act([=]() { if (ASOCharacter* H = Hero()) { H->HandleCrouchReleased(); H->HandleJumpPressed(); } });
			Do(0.3f, [=]() { Orbit(90.0f, 380.0f, 40.0f); });
			Snap(0.0f, FString::Printf(TEXT("c_%s_7_jump"), Body));
			Act([=]() { if (ASOCharacter* H = Hero()) { H->HandleJumpReleased(); } });
			Do(0.8f, [=]() { Reset(); });
			Do(0.8f, [=]() { EmptyReload(); });
			Do(1.1f, [=]() { Orbit(60.0f, 260.0f, 30.0f); });        // (timed: about mid-swap on the rifle)
			Snap(0.0f, FString::Printf(TEXT("c_%s_8_reload"), Body));
			Do(2.5f, [=]() { if (ASOCharacter* H = Hero()) { H->HandleWeapon2(); } });
			Do(0.35f, [=]() { Orbit(40.0f, 260.0f, 30.0f); });
			Snap(0.0f, FString::Printf(TEXT("c_%s_9_swap"), Body));
			Do(1.0f, [=, this]()
			{
				if (ASOCharacter* H = Hero())
				{
					H->HandleWeapon1();
					if (USOLocomotionAnimInstance* A = Cast<USOLocomotionAnimInstance>(H->GetMesh()->GetAnimInstance()))
					{
						A->FidgetDelay = FVector2D(0.5f, 0.5f);
						A->ResetFidgetTimer();
					}
				}
			});
			Do(2.2f, [=]() { Orbit(30.0f, 260.0f, 30.0f); });
			Snap(0.0f, FString::Printf(TEXT("c_%s_10_idle_variation"), Body));
			// the sealed helmet, worn through the inventory, then off again (the hair comes back)
			auto Helmet = [=, this](bool bOn)
			{
				if (USOInventoryComponent* Inv = SOFindInventory(this))
				{
					const FSOArmorInstance* H = Inv->GetArmor().FindByPredicate([](const FSOArmorInstance& A) { return A.Slot == TEXT("head") && A.Item == TEXT("orion_helmet"); });
					if (H && H->bEquipped != bOn)
					{
						Inv->EquipArmor(H->Uid);
					}
				}
			};
			Act([=]() { Helmet(true); Orbit(10.0f, 150.0f, 55.0f); });
			Snap(1.0f, FString::Printf(TEXT("c_%s_11_helmet_front"), Body));
			Act([=]() { Orbit(45.0f, 150.0f, 55.0f); });
			Snap(0.4f, FString::Printf(TEXT("c_%s_12_helmet_q34"), Body));
			Act([=]() { Orbit(170.0f, 160.0f, 55.0f); });
			Snap(0.4f, FString::Printf(TEXT("c_%s_13_helmet_back"), Body));
			Act([=]() { Helmet(false); Orbit(30.0f, 150.0f, 55.0f); });
			Snap(0.8f, FString::Printf(TEXT("c_%s_14_helmet_off"), Body));
		}
		Do(0.5f, []() {});
		GetWorldTimerManager().SetTimer(CaptureTimer, this, &ASOPlayerController::CaptureStep, 0.02f, true);
		return;
	}
	if (Set == 7)
	{
		// Shoulders while aiming (files b*): pistol and rifle aimed, close orbits round the upper body.
		auto Equip = [Hero](const TCHAR* Arch)
		{
			if (ASOCharacter* H = Hero())
			{
				FRandomStream Rng(FCrc::StrCrc32(Arch));
				H->EquipInstance(USOLootLibrary::MakeWeapon(Arch, 2, 20, Rng));
			}
		};
		auto Own = [this, Hero]() { if (ASOCharacter* H = Hero()) { SetViewTarget(H); } };
		Do(4.0f, [=]() { Look(0.0f); View(ESOViewMode::ThirdPerson); Equip(TEXT("sidearm")); });
		for (const TCHAR* Arch : { TEXT("sidearm"), TEXT("rifle") })
		{
			const FString A = Arch;
			Act([=]() { Own(); Equip(*A); });
			Do(1.2f, [=]() { Aim(true); });
			Snap(0.8f, FString::Printf(TEXT("b_%s_0_camera"), Arch));
			const float Yaws[] = { 180.0f, 225.0f, 270.0f, 315.0f, 20.0f, 90.0f };
			for (int32 i = 0; i < 6; ++i)
			{
				const float Yaw = Yaws[i];
				Act([=]() { Orbit(Yaw, 115.0f, 25.0f); });
				Snap(0.3f, FString::Printf(TEXT("b_%s_%d_yaw%d"), Arch, i + 1, (int32)Yaw));
			}
			Act([=]() { Aim(false); });
			Snap(0.6f, FString::Printf(TEXT("b_%s_7_hip_behind_left"), Arch));
		}
		Do(0.5f, []() {});
		GetWorldTimerManager().SetTimer(CaptureTimer, this, &ASOPlayerController::CaptureStep, 0.02f, true);
		return;
	}
	if (Set == 6)
	{
		// Aiming (files a1..a17): the third-person holds (rifle, pistol, sniper) from the shoulder camera, the side
		// and the front, hip and aimed; the scope view in both views; the crosshair rules.
		auto Equip = [Hero](const TCHAR* Arch, const TCHAR* Sight)
		{
			if (ASOCharacter* H = Hero())
			{
				FRandomStream Rng(FCrc::StrCrc32(Arch));
				FSOWeaponInstance W = USOLootLibrary::MakeWeapon(Arch, 2, 20, Rng);
				W.Sight = Sight;
				H->EquipInstance(W);
			}
		};
		auto Own = [this, Hero]() { if (ASOCharacter* H = Hero()) { SetViewTarget(H); } };
		Do(4.0f, [=]() { Look(0.0f); View(ESOViewMode::ThirdPerson); Equip(TEXT("rifle"), TEXT("default")); });
		Snap(1.2f, TEXT("a1_tp_rifle_hip"));
		Act([=]() { Aim(true); });
		Snap(0.8f, TEXT("a2_tp_rifle_ads"));
		Act([=]() { Orbit(90.0f, 170.0f, 15.0f); });
		Snap(0.4f, TEXT("a3_tp_rifle_ads_side"));
		Act([=]() { Orbit(35.0f, 190.0f, 25.0f); });
		Snap(0.4f, TEXT("a4_tp_rifle_ads_front"));
		Act([=]() { Aim(false); });
		Snap(0.8f, TEXT("a5_tp_rifle_hip_front"));
		Act([=]() { Orbit(90.0f, 170.0f, 15.0f); });
		Snap(0.4f, TEXT("a6_tp_rifle_hip_side"));
		Act([=]() { Own(); Look(-35.0f); });
		Snap(0.8f, TEXT("a7_tp_rifle_look_down"));
		Act([=]() { Look(30.0f); });
		Snap(0.8f, TEXT("a8_tp_rifle_look_up"));
		Act([=]() { Look(0.0f); Equip(TEXT("pistol"), TEXT("default")); });
		Snap(1.2f, TEXT("a9_tp_pistol_hip"));
		Act([=]() { Aim(true); });
		Snap(0.8f, TEXT("a10_tp_pistol_ads"));
		Act([=]() { Orbit(90.0f, 170.0f, 15.0f); });
		Snap(0.4f, TEXT("a11_tp_pistol_ads_side"));
		Act([=]() { Aim(false); Own(); Equip(TEXT("bolt"), TEXT("x8")); });
		Snap(1.2f, TEXT("a12_tp_sniper_hip"));
		Act([=]() { Aim(true); });
		Snap(0.15f, TEXT("a13_tp_sniper_shouldering"));
		Snap(0.8f, TEXT("a14_tp_sniper_scope"));
		Act([=]() { Aim(false); View(ESOViewMode::FirstPerson); });
		Snap(0.8f, TEXT("a15_fp_sniper_hip"));
		Act([=]() { Aim(true); });
		Snap(0.9f, TEXT("a16_fp_sniper_scope"));
		Act([=]() { Aim(false); });
		Snap(0.6f, TEXT("a17_fp_unscoped_crosshair_back"));
		Do(0.5f, []() {});
		GetWorldTimerManager().SetTimer(CaptureTimer, this, &ASOPlayerController::CaptureStep, 0.02f, true);
		return;
	}
	if (Set == 2)
	{
		// Loadout screen and both bodies only (files l3..l6, p1..p5).
		auto Hud = [this]() { return Cast<ASOHUD>(GetHUD()); };
		auto OpenSlot = [Hud](const TCHAR* SlotKey) { if (ASOHUD* H = Hud(); H && H->GetInventoryWidget()) { H->GetInventoryWidget()->OpenSlot(SlotKey); } };
		TSharedRef<FTransform> Start = MakeShared<FTransform>();
		Do(4.0f, [=, this]() { Look(0.0f); View(ESOViewMode::FirstPerson); if (ASOCharacter* H = Hero()) { *Start = H->GetActorTransform(); } });
		// first person at the pitch limits, firing, and sprinting (the gun stays in view)
		Act([=]() { Look(-88.0f); });
		Snap(0.8f, TEXT("f1_fp_look_down"));
		Act([=]() { Look(88.0f); });
		Snap(0.8f, TEXT("f2_fp_look_up"));
		Act([=]() { Look(0.0f); Fire(true); });
		Snap(0.08f, TEXT("f3_fp_fire"));
		Act([=]() { Fire(false); if (ASOCharacter* H = Hero()) { H->HandleSprintPressed(); } });
		Act([this]() { CaptureMove = FVector2D(0.0f, 1.0f); });
		Snap(1.6f, TEXT("f4_fp_sprint"));
		Act([this]() { CaptureMove = FVector2D::ZeroVector; });
		Act([=]() { if (ASOCharacter* H = Hero()) { H->TeleportTo(Start->GetLocation(), Start->Rotator()); H->GetCharacterMovement()->StopMovementImmediately(); } });
		Act([=]() { if (ASOCharacter* H = Hero()) { H->HandleSprintReleased(); } });
		// aiming through optics: the window frames the view, irons folded away, no crosshair
		auto EquipSight = [Hero](const TCHAR* Arch, const TCHAR* Sight)
		{
			if (ASOCharacter* H = Hero())
			{
				FRandomStream Rng(FCrc::StrCrc32(Arch));
				FSOWeaponInstance W = USOLootLibrary::MakeWeapon(Arch, 2, 20, Rng);
				W.Sight = Sight;
				H->EquipInstance(W);
			}
		};
		Act([=]() { EquipSight(TEXT("rifle"), TEXT("default")); });
		Do(1.0f, [=]() { Aim(true); });
		Snap(0.8f, TEXT("s0_ads_irons"));
		Act([=]() { Aim(false); EquipSight(TEXT("rifle"), TEXT("reflex")); });
		Snap(1.0f, TEXT("s1_hip_reflex"));
		Act([=]() { Aim(true); });
		Snap(0.8f, TEXT("s2_ads_reflex"));
		Act([=]() { Aim(false); EquipSight(TEXT("carbine"), TEXT("holo")); });
		Do(1.0f, [=]() { Aim(true); });
		Snap(0.8f, TEXT("s3_ads_holo"));
		Act([=]() { Aim(false); EquipSight(TEXT("rifle"), TEXT("default")); });
		// reloading in first person: the gun comes up and cants so the mag well is in view
		Do(1.0f, [=]() { EmptyReload(); });
		Snap(0.0f, TEXT("r1_fp_reload_mag"), MidMag);
		Snap(0.0f, TEXT("r2_fp_reload_rack"), MidRack);
		Snap(4.0f, TEXT("m1_minimap"));                       // the map picture is captured ~1-3.5 s after load
		Act([=]() { if (ASOHUD* H = Hud()) { H->ToggleMap(); } });
		Snap(1.0f, TEXT("m2_map_screen"));
		Act([=]() { if (ASOHUD* H = Hud()) { H->ToggleMap(); } });
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
		// third person on the move: legs turn toward a strafe, the cycle runs backward for a backpedal
		Act([=, this]() { View(ESOViewMode::ThirdPerson); CaptureMove = FVector2D(1.0f, 0.0f); });
		Do(0.9f, [=, this]() { Orbit(35.0f, 320.0f, 60.0f); });
		Snap(0.0f, TEXT("t1_tp_strafe_right"));
		Act([=, this]() { CaptureMove = FVector2D(0.0f, -1.0f); });
		Do(0.9f, [=, this]() { Orbit(70.0f, 320.0f, 60.0f); });
		Snap(0.0f, TEXT("t2_tp_backpedal"));
		Act([=, this]() { CaptureMove = FVector2D(-0.7f, 0.7f); });
		Do(0.9f, [=, this]() { Orbit(20.0f, 320.0f, 60.0f); });
		Snap(0.0f, TEXT("t3_tp_forward_left"));
		Act([=, this]() { CaptureMove = FVector2D::ZeroVector; if (ASOCharacter* H = Hero()) { H->TeleportTo(Start->GetLocation(), Start->Rotator()); } });
		// dying: the gun leaves the hands and falls with the body
		Act([=, this]() { if (ASOCharacter* H = Hero()) { USOCombatStatics::ApplyDamage(nullptr, H, 100000.0f, false); } Orbit(70.0f, 320.0f, 120.0f); });
		Snap(2.5f, TEXT("d1_death_gun_dropped"));
		Do(0.5f, []() {});
		GetWorldTimerManager().SetTimer(CaptureTimer, this, &ASOPlayerController::CaptureStep, 0.02f, true);
		return;
	}
	if (Set == 1)
	{
		// Hold study: every gun in the hands from every side the player sees it.
		const TCHAR* Guns[] = { TEXT("rifle"), TEXT("carbine"), TEXT("dmr"), TEXT("ksmg"), TEXT("bolt"), TEXT("pistol"), TEXT("revolver"), TEXT("pump"),
			TEXT("auto"), TEXT("pulse"), TEXT("scout"), TEXT("handcannon"), TEXT("shotgun"), TEXT("sniper"), TEXT("smg"), TEXT("sidearm"), TEXT("energy"),
			TEXT("hmg"), TEXT("rocket"), TEXT("spitter"), TEXT("bile"), TEXT("brood"), TEXT("vr_rifle"), TEXT("vr_sniper"), TEXT("vr_smg"), TEXT("vr_shotgun"),
			TEXT("vr_lmg"), TEXT("vr_handcannon"), TEXT("vr_pistol"), TEXT("vr_fusion"), TEXT("vr_rocket") };
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
			Snap(0.0f, Tag + TEXT("_c2_reload"), Reloading(0.62f));
			Snap(0.0f, Tag + TEXT("_c3_reload"), Reloading(0.8f));
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
	if (USOAreaSubsystem::IsArriving(this))
	{
		return;                                 // (the travelling screen is still up)
	}
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
	// (a cue whose moment never comes is taken anyway after a while: the series never hangs)
	if (CaptureWait < Cue.Delay || (Cue.Ready && !Cue.Ready() && CaptureWait < Cue.Delay + 8.0f))
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
	if (!CaptureMove.IsZero())
	{
		if (APawn* P = GetPawn())
		{
			P->AddMovementInput(P->GetActorForwardVector(), CaptureMove.Y);
			P->AddMovementInput(P->GetActorRightVector(), CaptureMove.X);
		}
	}
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
