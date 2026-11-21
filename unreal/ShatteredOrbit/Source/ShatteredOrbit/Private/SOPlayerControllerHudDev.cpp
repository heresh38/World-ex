// Developer tools: the HUD's capture set (SOCaptureSeries 1 38). Nothing of this is in a shipping build.

#include "SOPlayerController.h"
#include "SOCharacter.h"
#include "SOCombatStatics.h"
#include "SOCombatTypes.h"
#include "SOEnemy.h"
#include "SOHUD.h"
#include "SOInventoryComponent.h"
#include "SOLog.h"
#include "SOLootActors.h"
#include "SOSpecies.h"
#include "SOWeapon.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "TimerManager.h"
#include "UnrealClient.h"

#if UE_BUILD_SHIPPING
void ASOPlayerController::CaptureHud() {}
#else

/**
 * Set 38: the HUD in play (files hud_<n>_<what>), first person in the range (or wherever the game was started: on
 * L_Meridian the operation's objective banner, tracked panel and compass goal are in the pictures too): at rest; on
 * the move (the crosshair opens); aimed over the shoulder (it closes to a point); a creature put in front of the player
 * and the crosshair on it (the lock, its plate with level, name and bar); a burst into it (the damage numbers: the
 * real hits, then one of each kind laid on it); a hit on the player's shield (the edge's cells) and on the body; low
 * health (the pulse); the melee ability used (its cell cooling) and the moment it comes back (the gold pulse); two
 * loot cores dropped ahead (the beams) and the player walking onto one (the NEW ITEM card); the ultimate filled; the
 * conditions on the player with their timers; hand to hand; third person; the flashlight.
 */
void ASOPlayerController::CaptureHud()
{
	auto Hero = [this]() { return Cast<ASOCharacter>(GetPawn()); };
	auto Hud = [this]() { return Cast<ASOHUD>(GetHUD()); };
	auto Do = [this](float Delay, TFunction<void()> Action, TFunction<bool()> Ready = nullptr) -> void
	{
		CaptureCues.Add({ Delay, MoveTemp(Ready), MoveTemp(Action) });
	};
	auto Shot = [this](const FString& Name)
	{
		const FString File = FPaths::ProjectSavedDir() / TEXT("Screenshots") / FString::Printf(TEXT("SO_%s.png"), *Name);
		FScreenshotRequest::RequestScreenshot(File, true, false);
		UE_LOG(LogShatteredOrbit, Log, TEXT("Capture: %s"), *File);
	};
	auto Snap = [Do, Shot](float Delay, const FString& Name, TFunction<bool()> Ready = nullptr) { Do(Delay, [Shot, Name]() { Shot(Name); }, MoveTemp(Ready)); };
	auto Act = [Do](TFunction<void()> Action) { Do(0.05f, MoveTemp(Action)); };
	auto Fire = [Hero](bool bDown) { if (ASOCharacter* H = Hero()) { if (bDown) { H->HandleFirePressed(); } else { H->HandleFireReleased(); } } };
	auto Aim = [Hero](bool bDown) { if (ASOCharacter* H = Hero()) { if (bDown) { H->HandleAimPressed(); } else { H->HandleAimReleased(); } } };
	auto View = [Hero](ESOViewMode Mode) { if (ASOCharacter* H = Hero()) { H->SetViewMode(Mode); } };
	const TSharedRef<TWeakObjectPtr<ASOEnemy>> Victim = MakeShared<TWeakObjectPtr<ASOEnemy>>();
	auto Ahead = [this]() { return FRotator(0.0f, GetControlRotation().Yaw, 0.0f).Vector(); };
	auto Right = [this]() { return FRotator(0.0f, GetControlRotation().Yaw + 90.0f, 0.0f).Vector(); };

	CaptureCues.Reset();
	Do(6.0f, [=, this]()
	{
		ConsoleCommand(TEXT("DisableAllScreenMessages"));
		View(ESOViewMode::FirstPerson);
		SetControlRotation(FRotator(0.0f, GetControlRotation().Yaw, 0.0f));
	});
	Snap(1.0f, TEXT("hud_01_idle"));
	// on the move: the crosshair opens
	Act([=, this]() { CaptureMove = FVector2D(0.0f, 1.0f); });
	Snap(0.7f, TEXT("hud_02_moving"));
	Act([=, this]() { CaptureMove = FVector2D::ZeroVector; });
	// aimed over the shoulder: it closes on a point
	Act([=]() { View(ESOViewMode::ThirdPerson); Aim(true); });
	Snap(0.8f, TEXT("hud_03_aiming"));
	Act([=]() { Aim(false); View(ESOViewMode::FirstPerson); });
	// a creature in front, the crosshair on it: the lock and its plate
	Do(0.6f, [=, this]()
	{
		ASOCharacter* H = Hero();
		if (!H)
		{
			return;
		}
		FSOSpawnOptions Options;
		Options.bOnNav = false;
		const FVector Feet = H->GetActorLocation() + Ahead() * 700.0f - FVector(0.0f, 0.0f, H->GetSimpleCollisionHalfHeight());
		*Victim = USOSpeciesLibrary::Spawn(GetWorld(), TEXT("stalker"), Feet, GetControlRotation().Yaw + 180.0f, Options);
		if (ASOEnemy* E = Victim->Get())
		{
			if (AController* Brain = E->GetController())
			{
				Brain->UnPossess();
				Brain->Destroy();
			}
		}
		UE_LOG(LogShatteredOrbit, Display, TEXT("HUD check: creature %s"), Victim->IsValid() ? TEXT("spawned") : TEXT("NOT spawned"));
	});
	Act([=, this]()
	{
		if (ASOEnemy* E = Victim->Get())
		{
			const FVector Eye = Hero() ? Hero()->GetPawnViewLocation() : FVector::ZeroVector;
			SetControlRotation((E->GetActorLocation() + FVector(0.0f, 0.0f, 20.0f) - Eye).Rotation());
		}
	});
	Snap(0.5f, TEXT("hud_04_locked"));
	// a burst into it: the numbers as they land (slowed so the eye can read them in one picture)
	Act([=, this]() { if (ASOWeapon* W = Hero() ? Hero()->GetWeapon() : nullptr) { W->SetAmmo(30, 120); } Fire(true); });
	Snap(0.35f, TEXT("hud_05_hits"));
	Act([=]() { Fire(false); });
	// one of each kind laid on it (on the shield, precise, critical), so every colour is in one picture
	Do(1.2f, [=, this]()
	{
		ASOHUD* H = Hud();
		ASOEnemy* E = Victim->Get();
		if (!H || !E)
		{
			return;
		}
		const FVector C = E->GetActorLocation();
		const FVector R = Right();
		FSOHitReport Hit;
		Hit.Amount = 148.0f; Hit.Point = C - R * 30.0f + FVector(0, 0, 10.0f);
		H->ShowHit(Hit);
		Hit.Amount = 221.0f; Hit.bShield = true; Hit.Point = C + R * 30.0f + FVector(0, 0, -20.0f);
		H->ShowHit(Hit);
		Hit.Amount = 430.0f; Hit.bShield = false; Hit.bCrit = true; Hit.Precision = 1.0f; Hit.Point = C - R * 20.0f + FVector(0, 0, 60.0f);
		H->ShowHit(Hit);
		Hit.Amount = 920.0f; Hit.Precision = 1.5f; Hit.Point = C + R * 25.0f + FVector(0, 0, 70.0f);
		H->ShowHit(Hit);
	});
	Snap(0.2f, TEXT("hud_06_number_kinds"));
	// the player hit: on the shield, then on the body
	Act([=, this]() { if (ASOCharacter* H = Hero()) { USOCombatStatics::ApplyDamage(Victim->Get(), H, 28.0f, false); } });
	Snap(0.1f, TEXT("hud_07_shield_hit"));
	Do(0.8f, [=, this]()
	{
		if (ASOCharacter* H = Hero())
		{
			// through the shield and most of the health, in steps (the gate scales each by the plating worn)
			for (int32 i = 0; i < 60 && (H->GetShield() > 0.0f || H->GetHealth() > H->GetMaxHealth() * 0.28f); ++i)
			{
				USOCombatStatics::ApplyDamage(Victim->Get(), H, 8.0f, false);
			}
		}
	});
	Snap(0.1f, TEXT("hud_08_health_hit"));
	Snap(0.9f, TEXT("hud_09_low_health"));
	Act([=, this]() { if (ASOCharacter* H = Hero()) { H->Heal(1000.0f); H->AddShield(1000.0f); } });
	// the melee ability: its cell cools, then comes back with a pulse
	Do(0.6f, [=, this]() { if (ASOCharacter* H = Hero()) { H->ActivateSlot(ESOAbilitySlot::Melee); } });
	Snap(1.2f, TEXT("hud_10_ability_cooling"));
	Do(2.0f, []() {});
	Do(0.0f, []() {}, [=, this]()
	{
		int32 Charges = 0, Max = 0;
		float Left = 0.0f, Cooldown = 0.0f;
		return Hero() && Hero()->GetAbilityState(ESOAbilitySlot::Melee, Charges, Max, Left, Cooldown) && Charges > 0;
	});
	Snap(0.12f, TEXT("hud_11_ability_ready"));
	// loot: two cores ahead (the beams), and the player walks onto the first (the NEW ITEM card)
	Do(0.5f, [=, this]()
	{
		ASOCharacter* H = Hero();
		USOLootSubsystem* Loot = GetWorld()->GetSubsystem<USOLootSubsystem>();
		if (!H || !Loot)
		{
			return;
		}
		const FVector Floor = H->GetActorLocation() - FVector(0.0f, 0.0f, H->GetSimpleCollisionHalfHeight() - 2.0f);
		Loot->SpawnPickup(Floor + Ahead() * 260.0f - Right() * 60.0f, ESOPickupKind::Core, 3, 12);
		Loot->SpawnPickup(Floor + Ahead() * 420.0f + Right() * 120.0f, ESOPickupKind::Core, 4, 12);
		Loot->SpawnPickup(Floor + Ahead() * 380.0f - Right() * 230.0f, ESOPickupKind::Core, 2, 12);
	});
	Act([=, this]() { SetControlRotation(FRotator(-6.0f, GetControlRotation().Yaw, 0.0f)); });
	Snap(1.0f, TEXT("hud_12_loot_beams"));
	Act([=, this]() { CaptureMove = FVector2D(-0.25f, 1.0f); });
	Do(0.0f, [=, this]() { CaptureMove = FVector2D::ZeroVector; }, [=, this]()
	{
		// (until the first core is gone: collected)
		int32 Cores = 0;
		for (TActorIterator<ASOLootPickup> It(GetWorld()); It; ++It) { Cores += It->GetKind() == ESOPickupKind::Core ? 1 : 0; }
		return Cores < 3;
	});
	Snap(0.45f, TEXT("hud_13_new_item"));
	// the ultimate filled
	Act([=, this]() { if (ASOCharacter* H = Hero()) { H->AddUltimate(100.0f); } });
	Snap(0.25f, TEXT("hud_14_ultimate_pulse"));
	Snap(1.0f, TEXT("hud_15_ultimate_ready"));
	// the conditions, with their timers
	Act([=, this]()
	{
		if (ASOCharacter* H = Hero())
		{
			H->ActivateSlot(ESOAbilitySlot::Class);
			USOCombatStatics::ApplyStatus(Victim->Get(), H, SOTags::Status_Slow, 8.0f, 0.6f);
			USOCombatStatics::ApplyStatus(Victim->Get(), H, SOTags::Status_Burn, 5.0f, 6.0f);
		}
	});
	Snap(0.9f, TEXT("hud_16_conditions"));
	// the flashlight, hand to hand, third person
	Act([=]() { if (ASOCharacter* H = Hero()) { H->SetFlashlight(true); } });
	Snap(0.5f, TEXT("hud_17_flashlight"));
	Act([=]() { if (ASOCharacter* H = Hero()) { H->SetFlashlight(false); H->HandleFists(); } });
	Snap(0.8f, TEXT("hud_18_fists"));
	Act([=]() { if (ASOCharacter* H = Hero()) { H->HandleFists(); } View(ESOViewMode::ThirdPerson); });
	Snap(0.8f, TEXT("hud_19_third_person"));
	Act([=]() { View(ESOViewMode::FirstPerson); });
	Do(0.5f, []() {});
	GetWorldTimerManager().SetTimer(CaptureTimer, this, &ASOPlayerController::CaptureStep, 0.02f, true);
}

#endif
