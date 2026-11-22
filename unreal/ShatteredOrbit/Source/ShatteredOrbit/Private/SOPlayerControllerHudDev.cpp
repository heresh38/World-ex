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
#include "SOLootLibrary.h"
#include "SOProgression.h"
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
		if (ASOCharacter* H = Hero())
		{
			// the rifle in hand whatever the profile last held (a rocket launcher from a saved loadout fired rockets at
			// the creature seven metres off and the player with it)
			FRandomStream Rng(1);
			FSOWeaponInstance Copy = USOLootLibrary::MakeWeapon(TEXT("rifle"), 2, 20, Rng);
			Copy.Sight = TEXT("default");
			H->EquipInstance(Copy);
		}
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
	// the loop's beats: the kill paid on screen (xp, credits, the marker's burst), the level reached, an elite seen
	Act([=, this]()
	{
		if (ASOEnemy* E = Victim->Get())
		{
			const FVector Eye = Hero() ? Hero()->GetPawnViewLocation() : FVector::ZeroVector;
			SetControlRotation((E->GetActorLocation() + FVector(0.0f, 0.0f, 20.0f) - Eye).Rotation());
		}
	});
	Do(0.4f, [=, this]()
	{
		ASOCharacter* H = Hero();
		ASOEnemy* E = Victim->Get();
		if (H && E)
		{
			USOCombatStatics::ApplyDamage(H, E, 100000.0f, true);
			H->ConfirmHit(true, true);   // (a round's kill is confirmed by the projectile subsystem; this blow is direct)
		}
	});
	Snap(0.2f, TEXT("hud_20_kill_paid"));
	Do(0.5f, [=, this]()
	{
		if (USOInventoryComponent* Inv = SOFindInventory(this))
		{
			Inv->AddXp(USOProgressionTable::Get().XpForLevel(Inv->GetLevel()) - Inv->GetXp() + 1);
		}
	});
	Snap(0.35f, TEXT("hud_21_level_up"));
	Snap(0.9f, TEXT("hud_22_level_up_settled"));
	Do(0.8f, [=, this]()
	{
		ASOCharacter* H = Hero();
		if (!H)
		{
			return;
		}
		FSOSpeciesVariant V;
		V.Id = TEXT("captain");
		V.DisplayName = FText::FromString(TEXT("Remnant Captain"));
		FSOSpawnOptions Options;
		Options.bOnNav = false;
		Options.Variant = &V;
		const FVector Feet = H->GetActorLocation() + Ahead() * 900.0f + Right() * 120.0f - FVector(0.0f, 0.0f, H->GetSimpleCollisionHalfHeight());
		if (ASOEnemy* E = USOSpeciesLibrary::Spawn(GetWorld(), TEXT("remnant"), Feet, GetControlRotation().Yaw + 180.0f, Options))
		{
			if (AController* Brain = E->GetController())
			{
				Brain->UnPossess();
				Brain->Destroy();
			}
		}
	});
	Snap(0.5f, TEXT("hud_23_elite_seen"));
	// the layout's trials (the owner's brief, 2026-11-21): a long name with a big count in the held gun's panel,
	// every kind of number at once with the rewards beside them, each of the three slots held
	Act([=, this]() { if (ASOHUD* H = Hud()) { H->SetDebugWeapon(TEXT("The Long Silence of the Northern Approach"), 1000, 12000); } });
	Snap(0.5f, TEXT("hud_24_long_name"));
	Act([=, this]() { if (ASOHUD* H = Hud()) { H->SetDebugWeapon(TEXT("Old Winter"), 100, 999999); } });
	Snap(0.3f, TEXT("hud_25_big_count"));
	Act([=, this]() { if (ASOHUD* H = Hud()) { H->SetDebugWeapon(FString(), -1, -1); } });
	Do(0.3f, [=, this]()
	{
		ASOHUD* H = Hud();
		ASOCharacter* Me = Hero();
		if (!H || !Me)
		{
			return;
		}
		const FVector C = Me->GetPawnViewLocation() + Ahead() * 600.0f;
		const FVector R = Right();
		const float Amounts[] = { 148.0f, 221.0f, 430.0f, 920.0f, 77.0f, 1240.0f, 305.0f, 64.0f };
		for (int32 i = 0; i < 8; ++i)
		{
			FSOHitReport Hit;
			Hit.Amount = Amounts[i];
			Hit.Point = C + R * (i % 3 - 1) * 70.0f + FVector(0.0f, 0.0f, (i / 3) * 50.0f - 10.0f);
			Hit.bShield = i % 4 == 1;
			Hit.bCrit = i % 4 >= 2;
			Hit.Precision = i % 4 == 3 ? 1.5f : 1.0f;
			H->ShowHit(Hit);
		}
		if (USOInventoryComponent* Inv = SOFindInventory(this))
		{
			Inv->AddXp(431);
			Inv->AddCredits(71);
			Inv->AddAlloy(12);
		}
	});
	Snap(0.22f, TEXT("hud_26_many_numbers"));
	Act([=, this]() { if (USOInventoryComponent* Inv = SOFindInventory(this)) { Inv->SelectSlot(1); } });
	Snap(0.7f, TEXT("hud_27_slot_2"));
	Act([=, this]() { if (USOInventoryComponent* Inv = SOFindInventory(this)) { Inv->SelectSlot(2); } });
	Snap(0.7f, TEXT("hud_28_slot_3"));
	Act([=, this]() { if (USOInventoryComponent* Inv = SOFindInventory(this)) { Inv->SelectSlot(0); } });
	// the ring round the crosshair: hurt from the left (on the shield), from behind on the right (the body), from ahead
	Do(0.8f, [=, this]()
	{
		ASOHUD* H = Hud();
		ASOCharacter* Me = Hero();
		if (!H || !Me)
		{
			return;
		}
		const FVector At = Me->GetActorLocation();
		H->OnDamagedFrom(At - Right() * 900.0f, true, 30.0f);
		H->OnDamagedFrom(At - Ahead() * 700.0f + Right() * 500.0f, false, 45.0f);
		H->OnDamagedFrom(At + Ahead() * 1200.0f + Right() * 150.0f, true, 12.0f);
	});
	Snap(0.25f, TEXT("hud_29_hit_ring"));
	// the quick-use key: a stim used while hurt (the slot lit), then refused at full health (red)
	Do(1.8f, [=, this]()
	{
		ASOCharacter* Me = Hero();
		if (USOInventoryComponent* Inv = SOFindInventory(this))
		{
			Inv->AddGoods(TEXT("stim"), 3, false);
		}
		if (Me)
		{
			USOCombatStatics::ApplyDamage(nullptr, Me, Me->GetShield() + Me->GetMaxHealth() * 0.3f, false);
		}
	});
	Do(0.3f, [=]() { if (ASOCharacter* Me = Hero()) { Me->QuickUse(); } });
	Snap(0.1f, TEXT("hud_30_quick_use"));
	Act([=, this]() { if (ASOCharacter* Me = Hero()) { Me->Heal(1000.0f); Me->AddShield(1000.0f); } });
	Do(0.9f, [=]() { if (ASOCharacter* Me = Hero()) { Me->QuickUse(); } });
	Snap(0.1f, TEXT("hud_31_quick_use_refused"));
	// the HUD coming in (as after the armoury or a new body): a moment into its arrival
	Do(1.0f, [=, this]() { if (ASOHUD* H = Hud()) { H->ArriveAll(GetWorld()->GetTimeSeconds()); } });
	Snap(0.2f, TEXT("hud_32_arriving"));
	// every kind of gun its own reticle (at the hip, first person): one of each family of the human and the light guns
	for (const TCHAR* Kind : { TEXT("rifle"), TEXT("pulse"), TEXT("dmr"), TEXT("bolt"), TEXT("energy"), TEXT("smg"), TEXT("pistol"),
		TEXT("revolver"), TEXT("pump"), TEXT("hmg"), TEXT("rocket") })
	{
		const FName Id(Kind);
		Do(0.5f, [=]()
		{
			if (ASOCharacter* Me = Hero())
			{
				FRandomStream Rng(1);
				FSOWeaponInstance Copy = USOLootLibrary::MakeWeapon(Id, 2, 20, Rng);
				Copy.Sight = TEXT("default");
				Me->EquipInstance(Copy);
			}
		});
		Snap(1.0f, FString::Printf(TEXT("hud_33_reticle_%s"), Kind));
	}
	Do(0.5f, []() {});
	GetWorldTimerManager().SetTimer(CaptureTimer, this, &ASOPlayerController::CaptureStep, 0.02f, true);
}

#endif
