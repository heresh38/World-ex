// The inspect (the owner, 2026-11-24, a video of first-person guns: "its satisfying animations"; ASOWeapon::StartInspect,
// SOReload::BuildInspect): the gun brought up and looked over, its manual of arms worked as a shooter checks a gun, both
// hands on it (ShatteredOrbit.Hold.AlwaysInHand and ShatteredOrbit.Body.HumanRange measure it in every gun). Here what it
// does: each manual of arms works its own part, nothing is loaded or spent, a shot or a reload waits for the gun to be
// back in the hands' hold, and the reload key on a gun with nothing to load looks it over.

#include "SOTestWorld.h"

#if WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR

#include "GameFramework/PlayerController.h"
#include "SOCharacter.h"
#include "SOInventoryComponent.h"
#include "SOLootLibrary.h"
#include "SOLootTypes.h"
#include "SOPlayerState.h"
#include "SOReload.h"
#include "SOWeapon.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOInspectTest, "ShatteredOrbit.Weapon.InspectChecksTheGun", SOTest::Flags)
bool FSOInspectTest::RunTest(const FString& Parameters)
{
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

	// one gun of each manual of arms, and what its check moves (the part, and how far at the least)
	struct FCase
	{
		const TCHAR* Arch;
		const TCHAR* Part;
		float Least;
	};
	const FCase Cases[] = {
		{ TEXT("pistol"), TEXT("slide"), 0.015f }, { TEXT("rifle"), TEXT("bolt"), 0.02f }, { TEXT("carbine"), TEXT("charge"), 0.02f },
		{ TEXT("pump"), TEXT("pump"), 0.02f }, { TEXT("bolt"), TEXT("boltRot"), 0.8f }, { TEXT("revolver"), TEXT("crane"), 1.0f },
		{ TEXT("auto"), TEXT("mag"), 0.008f }, { TEXT("sniper"), TEXT("hatch"), 0.4f }, { TEXT("sidearm"), TEXT("hatch"), 0.4f },
		{ TEXT("brood"), TEXT("hatch"), 0.3f }, { TEXT("skr_rifle"), TEXT("mag"), 0.008f },
	};
	FRandomStream Rng(7);
	for (const FCase& Case : Cases)
	{
		Player->SetActorLocation(FVector(0.0f, 0.0f, 92.0f));
		PC->SetControlRotation(FRotator::ZeroRotator);
		ASOWeapon* Gun = Player->EquipInstance(USOLootLibrary::MakeWeapon(FName(Case.Arch), 2, 20, Rng));
		W.Run(0.8f);
		if (!TestNotNull(FString::Printf(TEXT("%s in the hands"), Case.Arch), Gun))
		{
			continue;
		}
		const int32 Mag = Gun->GetMag(), Reserve = Gun->GetReserve();
		Gun->StartInspect();
		TestTrue(FString::Printf(TEXT("%s: the inspect begins"), Case.Arch), Gun->IsInspecting());
		float Moved = 0.0f, Turned = 0.0f;
		float Seconds = 0.0f;
		W.Run(5.0f, [&]()
		{
			const FSOReloadPose& P = Gun->GetPose();
			const FString Part = Case.Part;
			const float V = Part == TEXT("slide") ? P.Slide : Part == TEXT("bolt") ? P.Bolt : Part == TEXT("charge") ? P.Charge : Part == TEXT("pump") ? P.Pump
				: Part == TEXT("boltRot") ? -P.BoltRot : Part == TEXT("crane") ? -P.Crane : Part == TEXT("mag") ? -P.Mag[1] : FMath::Abs(P.Hatch);
			Moved = FMath::Max(Moved, V);
			Turned = FMath::Max(Turned, FMath::Abs(P.Gun[5]));
			if (Gun->IsInspecting())
			{
				Seconds += SOTest::Dt;
			}
		});
		TestTrue(FString::Printf(TEXT("%s: its %s is worked (%.3f, at least %.3f)"), Case.Arch, Case.Part, Moved, Case.Least), Moved >= Case.Least);
		TestTrue(FString::Printf(TEXT("%s: the gun is turned over to be looked at (%.2f rad)"), Case.Arch, Turned), Turned > 0.4f);
		TestTrue(FString::Printf(TEXT("%s: it lasts a look, not a flick (%.2f s)"), Case.Arch, Seconds), Seconds > 2.0f && Seconds < 4.5f);
		TestFalse(FString::Printf(TEXT("%s: over by itself"), Case.Arch), Gun->IsInspecting());
		TestTrue(FString::Printf(TEXT("%s: nothing loaded or spent (%d / %d, was %d / %d)"), Case.Arch, Gun->GetMag(), Gun->GetReserve(), Mag, Reserve),
			Gun->GetMag() == Mag && Gun->GetReserve() == Reserve);
	}

	// a shot cuts it short: the gun back in the hands' hold first (no round while it is on its way), then the shot
	{
		ASOWeapon* Gun = Player->EquipInstance(USOLootLibrary::MakeWeapon(TEXT("rifle"), 2, 20, Rng));
		W.Run(0.8f);
		if (TestNotNull(TEXT("rifle in the hands"), Gun))
		{
			const int32 Mag = Gun->GetMag();
			Gun->StartInspect();
			W.Run(1.0f);
			Gun->StartFire();
			TestTrue(TEXT("the shot cuts the inspect short: the gun is on its way back"), Gun->IsInspecting());
			W.Run(ASOWeapon::InspectReturnTime * 0.6f);
			TestEqual(TEXT("no round leaves while the gun comes back into the hands"), Gun->GetMag(), Mag);
			W.Run(0.3f);
			Gun->StopFire();
			TestFalse(TEXT("the gun is back in the hands' hold"), Gun->IsInspecting());
			TestTrue(FString::Printf(TEXT("then the shot (%d of %d left)"), Gun->GetMag(), Mag), Gun->GetMag() < Mag);
		}
	}

	// a reload asked for during it waits for the gun to come back, then begins
	{
		ASOWeapon* Gun = Player->GetWeapon();
		if (TestNotNull(TEXT("the rifle still in the hands"), Gun))
		{
			W.Run(0.5f);
			Gun->SetAmmo(3, 120);
			Gun->StartInspect();
			W.Run(0.8f);
			Gun->StartReload();
			TestFalse(TEXT("no reload while the gun is turned to be looked at"), Gun->IsReloading());
			W.Run(ASOWeapon::InspectReturnTime + 0.1f);
			TestFalse(TEXT("the inspect is over"), Gun->IsInspecting());
			TestTrue(TEXT("and the reload has begun"), Gun->IsReloading());
			W.Run(Gun->GetReloadDuration() + 0.3f);
		}
	}

	// the reload key on a gun with nothing to load looks it over (the pad's way to the inspect)
	{
		ASOWeapon* Gun = Player->GetWeapon();
		if (TestNotNull(TEXT("the rifle in the hands for the reload key"), Gun))
		{
			Gun->SetAmmo(Gun->GetStats().Mag, 120);
			W.Run(0.3f);
			Player->HandleReload();
			Player->HandleReloadReleased();
			TestTrue(TEXT("the reload key on a full gun inspects it"), Gun->IsInspecting());
			TestFalse(TEXT("and does not reload it"), Gun->IsReloading());
			Player->HandleAimPressed();
			W.Run(ASOWeapon::InspectReturnTime + 0.1f);
			TestFalse(TEXT("the sights cut it short"), Gun->IsInspecting());
			Player->HandleAimReleased();
		}
	}
	return true;
}

#endif
