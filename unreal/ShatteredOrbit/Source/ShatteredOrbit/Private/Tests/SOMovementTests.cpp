// Movement system tests: variable jump height, air jumps, vaults over thin obstacles, traversal on a moving platform,
// landing weight and the fall damage hook, movement states and events, and frame-rate independence.

#include "SOTestWorld.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "Components/CapsuleComponent.h"
#include "SOCharacterMovementComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "SOLocomotionAnimInstance.h"

namespace SOTest
{
	float Feet(const ASOCharacter* C)
	{
		return static_cast<float>(C->GetActorLocation().Z) - C->GetCapsuleComponent()->GetScaledCapsuleHalfHeight();
	}

	void Floor(FTestWorld& W)
	{
		W.AddBox(FVector(-3000, -3000, -100), FVector(6000, 3000, 0));
	}

	/** One frame of any length. */
	void StepFor(FTestWorld& W, float Seconds)
	{
		W.World->Tick(LEVELTICK_All, Seconds);
		++GFrameCounter;
	}

	/** What a run at an obstacle did. */
	struct FTraversalRun
	{
		ESOTraversal Kind = ESOTraversal::None;
		float EntrySpeed = 0.0f, ExitSpeed = 0.0f, Duration = 0.0f, TopFeet = 0.0f, BiggestStep = 0.0f, EndX = 0.0f, EndFeet = 0.0f;
		bool bWentBack = false, bOnGround = false;
	};

	/** Runs (or sprints) at whatever is in front for a while and records the traversal, if one happens. */
	FTraversalRun RunAt(FTestWorld& W, ASOCharacter* C, bool bSprint, bool bHoldJump, float Seconds = 2.2f)
	{
		USOCharacterMovementComponent* Move = C->GetSOMovement();
		FTraversalRun R;
		W.Run(0.3f);
		Move->SetWantsToSprint(bSprint);
		Move->SetWantsToMantle(bHoldJump);
		bool bWas = false, bDone = false;
		FVector Last = C->GetActorLocation();
		W.Run(Seconds, [&]
		{
			const FVector Now = C->GetActorLocation();
			const bool bIn = Move->IsMantling();
			if (bIn)
			{
				if (!bWas)
				{
					R.Kind = Move->GetTraversal();
				}
				R.Duration += Dt;
				R.TopFeet = FMath::Max(R.TopFeet, Feet(C));
				R.BiggestStep = FMath::Max(R.BiggestStep, static_cast<float>(FVector::Dist(Now, Last)));
				R.bWentBack |= Now.X < Last.X - 0.5f;
			}
			else if (bWas && !bDone)
			{
				bDone = true;
				R.ExitSpeed = static_cast<float>(Move->Velocity.Size2D());
			}
			else if (!bWas && !bDone)
			{
				R.EntrySpeed = static_cast<float>(Move->Velocity.Size2D());
			}
			bWas = bIn;
			Last = Now;
			if (!bDone)
			{
				C->AddMovementInput(FVector::ForwardVector, 1.0f);
			}
		});
		Move->SetWantsToSprint(false);
		Move->SetWantsToMantle(false);
		W.Run(0.4f);
		R.EndX = static_cast<float>(C->GetActorLocation().X);
		R.EndFeet = Feet(C);
		R.bOnGround = Move->IsMovingOnGround();
		return R;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOVariableJumpTest, "ShatteredOrbit.Movement.VariableJump", SOTest::Flags)
bool FSOVariableJumpTest::RunTest(const FString& Parameters)
{
	// Holding the button is the full jump; letting go at once is a hop.
	float Apex[2] = { 0.0f, 0.0f };
	for (int32 Hold = 0; Hold < 2; ++Hold)
	{
		SOTest::FTestWorld W;
		SOTest::Floor(W);
		ASOCharacter* C = W.SpawnCharacter(FVector(0, 0, 0));
		USOCharacterMovementComponent* Move = C->GetSOMovement();
		W.Run(0.3f);
		Move->SetWantsToMantle(Hold == 1);
		C->Jump();
		W.Run(1.2f, [&] { Apex[Hold] = FMath::Max(Apex[Hold], SOTest::Feet(C)); });
		TestTrue(TEXT("back on the ground"), Move->IsMovingOnGround());
	}
	TestTrue(FString::Printf(TEXT("a held jump is the full metre (%.0f cm)"), Apex[1]), Apex[1] > 92.0f && Apex[1] < 103.0f);
	TestTrue(FString::Printf(TEXT("a tapped jump is a hop (%.0f cm of %.0f)"), Apex[0], Apex[1]), Apex[0] > 22.0f && Apex[0] < Apex[1] * 0.55f);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOAirJumpTest, "ShatteredOrbit.Movement.AirJump", SOTest::Flags)
bool FSOAirJumpTest::RunTest(const FString& Parameters)
{
	SOTest::FTestWorld W;
	SOTest::Floor(W);
	ASOCharacter* C = W.SpawnCharacter(FVector(0, 0, 0));
	USOCharacterMovementComponent* Move = C->GetSOMovement();
	int32 Jumps = 0, AirJumps = 0, Landings = 0;
	Move->OnMovementEvent.AddLambda([&](ESOMovementEvent E, float)
	{
		Jumps += E == ESOMovementEvent::Jumped;
		AirJumps += E == ESOMovementEvent::AirJumped;
		Landings += E == ESOMovementEvent::Landed;
	});
	W.Run(0.3f);
	TestEqual(TEXT("one air jump by default (a double jump)"), Move->MaxAirJumps, 1);

	// up, and up again from the top of the first
	Move->SetWantsToMantle(true);
	C->Jump();
	W.Run(0.3f);
	const float First = SOTest::Feet(C);
	TestEqual(TEXT("an air jump left while rising"), Move->GetAirJumpsLeft(), 1);
	C->Jump();
	W.Run(3.0f * SOTest::Dt);
	TestTrue(FString::Printf(TEXT("the air jump goes up (vz %.0f)"), Move->Velocity.Z), Move->Velocity.Z > 380.0f);
	TestEqual(TEXT("none left after it"), Move->GetAirJumpsLeft(), 0);
	float Top = 0.0f;
	W.Run(0.3f, [&] { Top = FMath::Max(Top, SOTest::Feet(C)); });
	TestTrue(FString::Printf(TEXT("higher than one jump reaches (%.0f cm after %.0f)"), Top, First), Top > First + 60.0f);
	// a third press does nothing
	const float VzBefore = Move->Velocity.Z;
	C->Jump();
	W.Run(3.0f * SOTest::Dt);
	TestTrue(TEXT("a third press in the air does nothing"), Move->Velocity.Z < VzBefore);
	W.Run(1.5f);
	TestTrue(TEXT("landed"), Move->IsMovingOnGround());
	TestEqual(TEXT("touching down gives the air jump back"), Move->GetAirJumpsLeft(), 1);
	TestTrue(FString::Printf(TEXT("events: %d jump, %d air jump, %d landing"), Jumps, AirJumps, Landings), Jumps == 1 && AirJumps == 1 && Landings >= 1);

	// the correction in the air: an air jump turns the carried speed toward the stick and keeps it
	Move->SetWantsToSprint(true);
	W.Run(1.0f, [&] { C->AddMovementInput(FVector::ForwardVector, 1.0f); });
	C->Jump();
	W.Run(0.15f, [&] { C->AddMovementInput(FVector::ForwardVector, 1.0f); });
	const float Carried = static_cast<float>(Move->Velocity.Size2D());
	W.Run(3.0f * SOTest::Dt, [&] { C->AddMovementInput(FVector::RightVector, 1.0f); });
	C->Jump();
	W.Run(2.0f * SOTest::Dt, [&] { C->AddMovementInput(FVector::RightVector, 1.0f); });
	const FVector Flat = Move->Velocity.GetSafeNormal2D();
	const float Turned = FMath::RadiansToDegrees(FMath::Acos(FMath::Clamp(static_cast<float>(Flat.X), -1.0f, 1.0f)));
	TestTrue(FString::Printf(TEXT("the air jump turned the momentum %.0f degrees toward the stick"), Turned), Turned > 35.0f && Flat.Y > 0.0f);
	TestTrue(FString::Printf(TEXT("and kept the speed (%.0f of %.0f cm/s)"), Move->Velocity.Size2D(), Carried), Move->Velocity.Size2D() > Carried * 0.93f && Move->Velocity.Size2D() < Carried * 1.08f);
	TestTrue(FString::Printf(TEXT("sprint speed was carried into the air (%.0f cm/s)"), Carried), Carried > 780.0f);
	Move->SetWantsToSprint(false);
	W.Run(1.5f);

	// none, and two
	Move->SetMaxAirJumps(0);
	C->Jump();
	W.Run(0.3f);
	const float Vz0 = Move->Velocity.Z;
	C->Jump();
	W.Run(3.0f * SOTest::Dt);
	TestTrue(TEXT("with no air jumps a press in the air does nothing"), Move->Velocity.Z < Vz0);
	W.Run(1.5f);
	Move->SetMaxAirJumps(2);
	int32 Went = 0;
	C->Jump();
	W.Run(0.3f);
	for (int32 i = 0; i < 3; ++i)
	{
		C->Jump();
		W.Run(3.0f * SOTest::Dt);
		Went += Move->Velocity.Z > 380.0f;
		W.Run(0.3f);
	}
	TestEqual(TEXT("with two air jumps: a triple jump, and no fourth"), Went, 2);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOVaultTest, "ShatteredOrbit.Movement.Vault", SOTest::Flags)
bool FSOVaultTest::RunTest(const FString& Parameters)
{
	// A thin wall met at a sprint is vaulted without the jump button: over it in one motion (never standing on it),
	// down on the far side, the speed kept, no jump in the path.
	for (const float Height : { 80.0f, 105.0f, 150.0f })
	{
		SOTest::FTestWorld W;
		SOTest::Floor(W);
		W.AddBox(FVector(320, -300, 0), FVector(360, 300, Height));
		ASOCharacter* C = W.SpawnCharacter(FVector(0, 0, 0));
		const USOCharacterMovementComponent* Move = C->GetSOMovement();
		const SOTest::FTraversalRun R = SOTest::RunAt(W, C, true, false);
		const ESOTraversal Want = Height <= Move->VaultLowMaxHeight ? ESOTraversal::VaultLow : ESOTraversal::VaultMedium;
		const FString Name = FString::Printf(TEXT("%.0f cm wall"), Height);
		if (!TestTrue(Name + TEXT(": vaulted at a sprint without the button"), R.Kind == Want))
		{
			continue;
		}
		TestTrue(FString::Printf(TEXT("%s: down on the far side (x %.0f, feet %.0f)"), *Name, R.EndX, R.EndFeet), R.EndX > 394.0f && FMath::Abs(R.EndFeet) < 4.0f && R.bOnGround);
		TestTrue(FString::Printf(TEXT("%s: the legs tuck: the feet pass %.0f cm up, below its top"), *Name, R.TopFeet), R.TopFeet < Height - 8.0f && R.TopFeet > Height - 60.0f);
		TestTrue(FString::Printf(TEXT("%s: the speed is kept (%.0f in, %.0f out)"), *Name, R.EntrySpeed, R.ExitSpeed), R.ExitSpeed > R.EntrySpeed * 0.85f && R.EntrySpeed > 700.0f);
		TestTrue(FString::Printf(TEXT("%s: one smooth motion (biggest step %.1f cm a frame, never back)"), *Name, R.BiggestStep), R.BiggestStep < 26.0f && !R.bWentBack);
		TestTrue(FString::Printf(TEXT("%s: quick (%.2f s)"), *Name, R.Duration), R.Duration > 0.2f && R.Duration < 0.75f);
	}
	// The same low wall at a walk with the button held: no run-up, so up onto it instead.
	{
		SOTest::FTestWorld W;
		SOTest::Floor(W);
		W.AddBox(FVector(320, -300, 0), FVector(420, 300, 100));
		ASOCharacter* C = W.SpawnCharacter(FVector(0, 0, 0));
		const SOTest::FTraversalRun R = SOTest::RunAt(W, C, false, true, 1.6f);
		TestTrue(TEXT("at a walk the wall is mantled onto"), R.Kind == ESOTraversal::Mantle);
		TestEqual(TEXT("standing on it"), R.EndFeet, 100.0f, 4.0f);
	}
	// A deep block at a sprint: nothing to land on behind its near edge, so onto it (with the button).
	{
		SOTest::FTestWorld W;
		SOTest::Floor(W);
		W.AddBox(FVector(320, -300, 0), FVector(820, 300, 100));
		ASOCharacter* C = W.SpawnCharacter(FVector(0, 0, 0));
		const SOTest::FTraversalRun Auto = SOTest::RunAt(W, C, true, false, 1.0f);
		TestTrue(TEXT("a deep block is not vaulted by itself"), Auto.Kind == ESOTraversal::None);
	}
	{
		SOTest::FTestWorld W;
		SOTest::Floor(W);
		W.AddBox(FVector(320, -300, 0), FVector(820, 300, 100));
		ASOCharacter* C = W.SpawnCharacter(FVector(0, 0, 0));
		const SOTest::FTraversalRun Held = SOTest::RunAt(W, C, true, true, 1.0f);
		TestTrue(TEXT("with the button a deep block is mantled onto"), Held.Kind == ESOTraversal::Mantle);
		TestEqual(TEXT("standing on the block"), Held.EndFeet, 100.0f, 4.0f);
	}
	// A wall with a pit behind it is never vaulted.
	{
		SOTest::FTestWorld W;
		W.AddBox(FVector(-3000, -3000, -100), FVector(362, 3000, 0));
		W.AddBox(FVector(-3000, -3000, -1600), FVector(6000, 3000, -1500));
		W.AddBox(FVector(320, -300, 0), FVector(360, 300, 100));
		ASOCharacter* C = W.SpawnCharacter(FVector(0, 0, 0));
		const SOTest::FTraversalRun R = SOTest::RunAt(W, C, true, false, 1.0f);
		TestTrue(TEXT("no vault into a pit"), R.Kind == ESOTraversal::None && R.EndFeet > -4.0f);
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOMovingPlatformTest, "ShatteredOrbit.Movement.MovingPlatform", SOTest::Flags)
bool FSOMovingPlatformTest::RunTest(const FString& Parameters)
{
	// A ledge that moves while it is being climbed carries the climb with it: the body ends where it aimed on the
	// platform, not where the platform used to be.
	SOTest::FTestWorld W;
	SOTest::Floor(W);
	AActor* Platform = W.AddBox(FVector(200, -400, 0), FVector(700, 400, 160));
	ASOCharacter* C = W.SpawnCharacter(FVector(0, 0, 0));
	USOCharacterMovementComponent* Move = C->GetSOMovement();
	W.Run(0.3f);
	Move->SetWantsToMantle(true);
	const float Speed = 140.0f;                                  // the platform slides sideways
	bool bWas = false, bDone = false;
	float StartOffset = 0.0f, EndOffset = 0.0f, Carried = 0.0f, PlatformAtStart = 0.0f;
	W.Run(2.5f, [&]
	{
		Platform->SetActorLocation(Platform->GetActorLocation() + FVector(0.0f, Speed * SOTest::Dt, 0.0f));
		const float Offset = static_cast<float>(C->GetActorLocation().Y - Platform->GetActorLocation().Y);
		if (Move->IsMantling() && !bWas)
		{
			StartOffset = Offset;
			PlatformAtStart = static_cast<float>(Platform->GetActorLocation().Y);
		}
		if (!Move->IsMantling() && bWas && !bDone)
		{
			bDone = true;
			EndOffset = Offset;
			Carried = static_cast<float>(Platform->GetActorLocation().Y) - PlatformAtStart;
		}
		bWas = Move->IsMantling();
		if (!bDone)
		{
			C->AddMovementInput(FVector::ForwardVector, 1.0f);
		}
	});
	Move->SetWantsToMantle(false);
	if (!TestTrue(TEXT("climbed onto the moving platform"), bDone))
	{
		return false;
	}
	TestTrue(FString::Printf(TEXT("the platform moved %.0f cm during the climb"), Carried), Carried > 40.0f);
	TestTrue(FString::Printf(TEXT("and carried the climb with it (%.1f cm off where it aimed)"), EndOffset - StartOffset), FMath::Abs(EndOffset - StartOffset) < 8.0f);
	TestEqual(TEXT("standing on it"), SOTest::Feet(C), 160.0f, 5.0f);
	W.Run(0.6f, [&] { Platform->SetActorLocation(Platform->GetActorLocation() + FVector(0.0f, Speed * SOTest::Dt, 0.0f)); });
	const float After = static_cast<float>(C->GetActorLocation().Y - Platform->GetActorLocation().Y);
	TestTrue(FString::Printf(TEXT("and rides it afterwards (%.1f cm slip)"), After - EndOffset), FMath::Abs(After - EndOffset) < 12.0f);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOLandingTest, "ShatteredOrbit.Movement.Landing", SOTest::Flags)
bool FSOLandingTest::RunTest(const FString& Parameters)
{
	// A long fall lands hard: the impact speed is known (camera, sound, the fall damage hook) and the legs take a
	// moment to get back to speed. Fall damage is off unless a threshold is set.
	for (int32 Damage = 0; Damage < 2; ++Damage)
	{
		SOTest::FTestWorld W;
		SOTest::Floor(W);
		ASOCharacter* C = W.SpawnCharacter(FVector(0, 0, 900));
		USOCharacterMovementComponent* Move = C->GetSOMovement();
		if (Damage)
		{
			Move->FallDamageMinSpeed = 1200.0f;
		}
		float Impact = -1.0f;
		Move->OnMovementEvent.AddLambda([&](ESOMovementEvent E, float Strength) { if (E == ESOMovementEvent::Landed && Impact < 0.0f) { Impact = Strength; } });
		const float Before = C->GetHealth() + C->GetShield();
		int32 Guard = 0;
		while (!Move->IsMovingOnGround() && Guard++ < 600)
		{
			W.Step();
		}
		TestTrue(FString::Printf(TEXT("a 9 m fall lands at %.0f cm/s"), Impact), Impact > 1700.0f && Impact < 1950.0f && Move->GetLastLandSpeed() == Impact);
		TestTrue(TEXT("the state is Land right after"), Move->GetMovementState() == ESOMovementState::Land);
		float Early = 0.0f;
		W.Run(0.12f, [&] { C->AddMovementInput(FVector::ForwardVector, 1.0f); Early = FMath::Max(Early, static_cast<float>(Move->Velocity.Size2D())); });
		W.Run(0.6f, [&] { C->AddMovementInput(FVector::ForwardVector, 1.0f); });
		const float Late = static_cast<float>(Move->Velocity.Size2D());
		TestTrue(FString::Printf(TEXT("slow off a hard landing (%.0f cm/s), back to speed soon after (%.0f)"), Early, Late), Early < Move->MaxWalkSpeed * 0.8f && Late > Move->MaxWalkSpeed * 0.97f);
		const float Lost = Before - (C->GetHealth() + C->GetShield());
		if (Damage)
		{
			TestEqual(TEXT("with a threshold set the fall hurts"), Lost, Move->GetFallDamage(Impact), 6.0f);
			TestTrue(TEXT("and it is real damage"), Move->GetFallDamage(Impact) > 20.0f);
		}
		else
		{
			TestEqual(TEXT("no fall damage by default"), Lost, 0.0f, 0.01f);
		}
	}
	// an ordinary jump is not a hard landing
	{
		SOTest::FTestWorld W;
		SOTest::Floor(W);
		ASOCharacter* C = W.SpawnCharacter(FVector(0, 0, 0));
		USOCharacterMovementComponent* Move = C->GetSOMovement();
		W.Run(0.3f);
		Move->SetWantsToMantle(true);
		C->Jump();
		float Least = BIG_NUMBER;
		bool bLanded = false;
		W.Run(1.4f, [&]
		{
			C->AddMovementInput(FVector::ForwardVector, 1.0f);
			bLanded |= Move->IsMovingOnGround() && Move->GetLastLandSpeed() > 100.0f;
			if (bLanded)
			{
				Least = FMath::Min(Least, static_cast<float>(Move->Velocity.Size2D()));
			}
		});
		TestTrue(FString::Printf(TEXT("a jump lands without losing speed (never under %.0f cm/s)"), Least), bLanded && Least > Move->MaxWalkSpeed * 0.9f);
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOMovementStatesTest, "ShatteredOrbit.Movement.States", SOTest::Flags)
bool FSOMovementStatesTest::RunTest(const FString& Parameters)
{
	// One state at a time, announced as it changes; nothing is locked by it.
	SOTest::FTestWorld W;
	SOTest::Floor(W);
	ASOCharacter* C = W.SpawnCharacter(FVector(0, 0, 0));
	USOCharacterMovementComponent* Move = C->GetSOMovement();
	TArray<ESOMovementState> Seen;
	TArray<ESOMovementEvent> Events;
	Move->OnMovementStateChanged.AddLambda([&](ESOMovementState, ESOMovementState Now) { Seen.Add(Now); });
	Move->OnMovementEvent.AddLambda([&](ESOMovementEvent E, float) { Events.Add(E); });
	W.Run(0.4f);
	TestTrue(TEXT("standing: Idle"), Move->GetMovementState() == ESOMovementState::Idle);
	W.Run(0.5f, [&] { C->AddMovementInput(FVector::ForwardVector, 0.4f); });
	TestTrue(FString::Printf(TEXT("a light stick: Walk (%.0f cm/s)"), Move->Velocity.Size2D()), Move->GetMovementState() == ESOMovementState::Walk);
	W.Run(0.4f, [&] { C->AddMovementInput(FVector::ForwardVector, 1.0f); });
	TestTrue(TEXT("full stick: Run"), Move->GetMovementState() == ESOMovementState::Run);
	Move->SetWantsToSprint(true);
	W.Run(0.6f, [&] { C->AddMovementInput(FVector::ForwardVector, 1.0f); });
	TestTrue(TEXT("sprint held: Sprint"), Move->GetMovementState() == ESOMovementState::Sprint);
	Move->SetWantsToMantle(true);
	C->Jump();
	W.Run(0.1f, [&] { C->AddMovementInput(FVector::ForwardVector, 1.0f); });
	TestTrue(TEXT("rising: Jump"), Move->GetMovementState() == ESOMovementState::Jump);
	W.Run(0.4f, [&] { C->AddMovementInput(FVector::ForwardVector, 1.0f); });
	TestTrue(TEXT("coming down: Falling"), Move->GetMovementState() == ESOMovementState::Falling);
	Move->SetWantsToMantle(false);
	int32 Guard = 0;
	while (!Move->IsMovingOnGround() && Guard++ < 200)
	{
		C->AddMovementInput(FVector::ForwardVector, 1.0f);
		W.Step();
	}
	TestTrue(TEXT("touching down: Land"), Move->GetMovementState() == ESOMovementState::Land);
	// still sprinting: crouch into a slide, then stay down
	W.Run(0.5f, [&] { C->AddMovementInput(FVector::ForwardVector, 1.0f); });
	C->Crouch();
	W.Run(0.25f, [&] { C->AddMovementInput(FVector::ForwardVector, 1.0f); });
	TestTrue(TEXT("crouching at a sprint: Slide"), Move->GetMovementState() == ESOMovementState::Slide);
	Move->SetWantsToSprint(false);
	W.Run(1.6f);
	TestTrue(TEXT("the slide over, still down: Crouch"), Move->GetMovementState() == ESOMovementState::Crouch);
	C->UnCrouch();
	W.Run(0.5f);
	TestTrue(TEXT("up again: Idle"), Move->GetMovementState() == ESOMovementState::Idle);

	// announced in order
	int32 At = 0;
	for (const ESOMovementState Want : { ESOMovementState::Walk, ESOMovementState::Run, ESOMovementState::Sprint, ESOMovementState::Jump, ESOMovementState::Falling,
		ESOMovementState::Land, ESOMovementState::Slide, ESOMovementState::Crouch, ESOMovementState::Idle })
	{
		while (At < Seen.Num() && Seen[At] != Want)
		{
			++At;
		}
		TestTrue(FString::Printf(TEXT("state %d was announced in its turn"), static_cast<int32>(Want)), At < Seen.Num());
	}
	TestTrue(TEXT("events: a jump, a landing, a slide started and ended"), Events.Contains(ESOMovementEvent::Jumped) && Events.Contains(ESOMovementEvent::Landed)
		&& Events.Contains(ESOMovementEvent::SlideStarted) && Events.Contains(ESOMovementEvent::SlideEnded));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOFrameRateTest, "ShatteredOrbit.Movement.FrameRate", SOTest::Flags)
bool FSOFrameRateTest::RunTest(const FString& Parameters)
{
	// The same inputs give the same motion at 30, 60 and 144 frames a second: a jump's height, a sprint's distance,
	// a slide's length and a vault's time.
	const float Rates[3] = { 30.0f, 60.0f, 144.0f };
	float Apex[3], Sprint[3], Slide[3], Vault[3];
	for (int32 i = 0; i < 3; ++i)
	{
		const float Step = 1.0f / Rates[i];
		auto For = [&](SOTest::FTestWorld& W, float Seconds, TFunctionRef<void()> Input)
		{
			for (float T = 0.0f; T < Seconds - 1e-4f; T += Step)
			{
				Input();
				SOTest::StepFor(W, Step);
			}
		};
		{
			SOTest::FTestWorld W;
			SOTest::Floor(W);
			ASOCharacter* C = W.SpawnCharacter(FVector(0, 0, 0));
			USOCharacterMovementComponent* Move = C->GetSOMovement();
			For(W, 0.3f, [] {});
			Move->SetWantsToMantle(true);
			C->Jump();
			Apex[i] = 0.0f;
			For(W, 1.0f, [&] { Apex[i] = FMath::Max(Apex[i], SOTest::Feet(C)); });
		}
		{
			SOTest::FTestWorld W;
			SOTest::Floor(W);
			ASOCharacter* C = W.SpawnCharacter(FVector(-1000, 0, 0));
			USOCharacterMovementComponent* Move = C->GetSOMovement();
			For(W, 0.3f, [] {});
			Move->SetWantsToSprint(true);
			const float From = static_cast<float>(C->GetActorLocation().X);
			For(W, 1.0f, [&] { C->AddMovementInput(FVector::ForwardVector, 1.0f); });
			Sprint[i] = static_cast<float>(C->GetActorLocation().X) - From;
			C->Crouch();
			const float SlideFrom = static_cast<float>(C->GetActorLocation().X);
			For(W, 1.5f, [&] { C->AddMovementInput(FVector::ForwardVector, 1.0f); });
			Slide[i] = static_cast<float>(C->GetActorLocation().X) - SlideFrom;
		}
		{
			SOTest::FTestWorld W;
			SOTest::Floor(W);
			W.AddBox(FVector(320, -300, 0), FVector(360, 300, 100));
			ASOCharacter* C = W.SpawnCharacter(FVector(0, 0, 0));
			USOCharacterMovementComponent* Move = C->GetSOMovement();
			For(W, 0.3f, [] {});
			Move->SetWantsToSprint(true);
			Vault[i] = 0.0f;
			For(W, 1.5f, [&] { C->AddMovementInput(FVector::ForwardVector, 1.0f); Vault[i] += Move->IsVaulting() ? Step : 0.0f; });
		}
	}
	for (int32 i = 0; i < 3; ++i)
	{
		AddInfo(FString::Printf(TEXT("%.0f fps: jump %.1f cm, sprint %.0f cm in 1 s, slide %.0f cm, vault %.2f s"), Rates[i], Apex[i], Sprint[i], Slide[i], Vault[i]));
	}
	TestTrue(FString::Printf(TEXT("jump height (%.1f / %.1f / %.1f cm)"), Apex[0], Apex[1], Apex[2]), FMath::Abs(Apex[0] - Apex[2]) < 4.0f && FMath::Abs(Apex[1] - Apex[2]) < 3.0f);
	TestTrue(FString::Printf(TEXT("sprint distance (%.0f / %.0f / %.0f cm)"), Sprint[0], Sprint[1], Sprint[2]), FMath::Abs(Sprint[0] - Sprint[2]) < Sprint[2] * 0.04f);
	TestTrue(FString::Printf(TEXT("slide length (%.0f / %.0f / %.0f cm)"), Slide[0], Slide[1], Slide[2]), FMath::Abs(Slide[0] - Slide[2]) < Slide[2] * 0.08f);
	TestTrue(FString::Printf(TEXT("vault time (%.2f / %.2f / %.2f s)"), Vault[0], Vault[1], Vault[2]), Vault[2] > 0.2f && FMath::Abs(Vault[0] - Vault[2]) < 0.08f);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOBodyFollowsMotionTest, "ShatteredOrbit.Anim.BodyFollowsMotion", SOTest::Flags)
bool FSOBodyFollowsMotionTest::RunTest(const FString& Parameters)
{
	// The body is driven by what it is doing, not by a clock: standing, the feet stay planted while the aim turns and
	// step round past a limit; in the air the legs drive off, tuck at the top and reach for the ground; over a ledge
	// the hands are on its edge.
	if (SOTest::PlayerBodyMissing(*this))
	{
		return true;
	}
	SOTest::FTestWorld W;
	SOTest::Floor(W);
	W.AddBox(FVector(150, -300, 0), FVector(650, 300, 200));
	ASOCharacter* C = W.SpawnCharacter(FVector(0, 0, 0));
	USOCharacterMovementComponent* Move = C->GetSOMovement();
	USkeletalMeshComponent* Body = C->GetMesh();
	Body->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones; // (nothing renders here)
	W.Run(0.6f);
	const USOLocomotionAnimInstance* Anim = Cast<USOLocomotionAnimInstance>(Body->GetAnimInstance());
	if (!TestNotNull(TEXT("the body's animation"), Anim))
	{
		return false;
	}
	auto TurnBy = [&](float Degrees, float Seconds)
	{
		const int32 Frames = FMath::Max(FMath::RoundToInt(Seconds / SOTest::Dt), 1);
		for (int32 i = 0; i < Frames; ++i)
		{
			C->SetActorRotation(C->GetActorRotation() + FRotator(0.0f, Degrees / Frames, 0.0f));
			W.Step();
		}
	};

	// 1. a look to the side: the feet do not move, the hips keep their heading
	C->SetActorRotation(FRotator(0.0f, -90.0f, 0.0f));          // away from the block
	W.Run(1.2f);
	const FVector FootBefore = Body->GetBoneLocation(TEXT("foot_L"));
	TurnBy(34.0f, 0.3f);
	W.Run(0.1f);
	const float Slip = static_cast<float>(FVector::Dist2D(Body->GetBoneLocation(TEXT("foot_L")), FootBefore));
	TestTrue(FString::Printf(TEXT("turning the aim 34 degrees leaves the hips behind (%.0f degrees)"), Anim->GetStandYaw()), FMath::Abs(Anim->GetStandYaw() + 34.0f) < 4.0f);
	TestTrue(FString::Printf(TEXT("and the feet where they stood (%.1f cm of slip)"), Slip), Slip < 5.0f && !Anim->IsTurningInPlace());
	// 2. further: the body steps round under the aim
	TurnBy(40.0f, 0.3f);
	TestTrue(TEXT("past the limit it turns on the spot"), Anim->IsTurningInPlace());
	W.Run(0.9f);
	TestTrue(FString::Printf(TEXT("and comes square again (%.1f degrees left)"), Anim->GetStandYaw()), FMath::Abs(Anim->GetStandYaw()) < 2.0f && !Anim->IsTurningInPlace());
	// 3. moving, the legs come round at once
	TurnBy(30.0f, 0.2f);
	W.Run(0.4f, [&] { C->AddMovementInput(C->GetActorForwardVector(), 1.0f); });
	TestTrue(TEXT("walking off squares the hips"), FMath::Abs(Anim->GetStandYaw()) < 2.0f);
	W.Run(0.5f);

	// 4. the air pose follows the rise and the fall
	Move->SetWantsToMantle(true);
	C->Jump();
	W.Run(4.0f * SOTest::Dt);
	const float AtTakeoff = Anim->GetAirTuck();
	float AtTop = 0.0f;
	W.Run(0.5f, [&] { if (FMath::Abs(Move->Velocity.Z) < 60.0f && Move->IsFalling()) { AtTop = FMath::Max(AtTop, Anim->GetAirTuck()); } });
	Move->SetWantsToMantle(false);
	W.Run(0.8f);
	TestTrue(FString::Printf(TEXT("driving off the ground the legs are long (tuck %.2f), at the top they are tucked (%.2f)"), AtTakeoff, AtTop), AtTakeoff < 0.55f && AtTop > 0.8f);
	TestTrue(FString::Printf(TEXT("standing again they are down (%.2f)"), Anim->GetAirTuck()), Anim->GetAirTuck() < 0.05f);

	// 5. a ledge: the hands go onto its edge and stay there while the body comes up past them
	C->SetActorLocationAndRotation(FVector(60, 0, C->GetActorLocation().Z), FRotator::ZeroRotator);
	W.Run(0.4f);
	Move->SetWantsToMantle(true);
	float Best = BIG_NUMBER;
	bool bHands = false;
	FString Where;
	W.Run(1.6f, [&]
	{
		C->AddMovementInput(FVector::ForwardVector, 1.0f);
		if (Move->IsMantling() && Anim->HasLedgeHands() && Anim->GetHoldAlpha() > 0.95f)
		{
			bHands = true;
			for (const TCHAR* Hand : { TEXT("hand_L"), TEXT("hand_R") })
			{
				const FVector At = Body->GetBoneLocation(Hand);
				// on the top (200 cm), a hand's length in from the edge (x = 150)
				const float Off = FMath::Max(FMath::Abs(static_cast<float>(At.Z) - 202.0f), FMath::Abs(static_cast<float>(At.X) - 156.0f));
				if (Off < Best)
				{
					Best = Off;
					Where = FString::Printf(TEXT("%s at %s, body %s, alpha %.2f, shoulder %s"), Hand, *At.ToCompactString(), *C->GetActorLocation().ToCompactString(), Move->GetMantleAlpha(),
						*Body->GetBoneLocation(Hand[5] == TEXT('L') ? TEXT("upperarm_L") : TEXT("upperarm_R")).ToCompactString());
				}
			}
		}
	});
	Move->SetWantsToMantle(false);
	TestTrue(FString::Printf(TEXT("climbing, the hands are on the edge (%.1f cm off at best: %s)"), Best, *Where), bHands && Best < 6.0f);
	TestEqual(TEXT("and it ends standing on the ledge"), SOTest::Feet(C), 200.0f, 5.0f);
	W.Run(0.5f);
	TestFalse(TEXT("the hands are free again afterwards"), Anim->HasLedgeHands());
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSORunsTallTest, "ShatteredOrbit.Anim.RunsTall", SOTest::Flags)
bool FSORunsTallTest::RunTest(const FString& Parameters)
{
	// Running is tall: the hips ride at standing height (a few cm of spring in each step), never sunk into a crouch,
	// the feet come down under the body (his under the hip joints, about 8 cm a side: a man's track; hers on a line),
	// never out past the hips, and nothing the game adds on top of the clip lowers them.
	if (SOTest::PlayerBodyMissing(*this))
	{
		return true;
	}
	for (const int32 Pace : { 0, 1, 2 })
	{
		const bool bSprint = Pace == 2;
		const float Stick = Pace == 0 ? 0.34f : 1.0f;              // (a light stick: the slow walk)
		SOTest::FTestWorld W;
		SOTest::Floor(W);
		ASOCharacter* C = W.SpawnCharacter(FVector(-2500, 0, 0));
		USOCharacterMovementComponent* Move = C->GetSOMovement();
		USkeletalMeshComponent* Body = C->GetMesh();
		Body->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
		W.Run(1.5f);
		const USOLocomotionAnimInstance* Anim = Cast<USOLocomotionAnimInstance>(Body->GetAnimInstance());
		if (!TestNotNull(TEXT("the body's animation"), Anim))
		{
			return false;
		}
		const float Floor = SOTest::Feet(C);
		const float Standing = static_cast<float>(Body->GetBoneLocation(TEXT("hips")).Z) - Floor;
		Move->SetWantsToSprint(bSprint);
		W.Run(1.2f, [&] { C->AddMovementInput(FVector::ForwardVector, Stick); });
		float Low = BIG_NUMBER, High = -BIG_NUMBER, Sum = 0.0f, Drop = 0.0f, Wide = 0.0f, Crouch = 0.0f;
		int32 N = 0;
		W.Run(1.4f, [&]
		{
			C->AddMovementInput(FVector::ForwardVector, Stick);
			const float Z = static_cast<float>(Body->GetBoneLocation(TEXT("hips")).Z) - SOTest::Feet(C);
			Low = FMath::Min(Low, Z);
			High = FMath::Max(High, Z);
			Sum += Z;
			++N;
			Drop = FMath::Max(Drop, Anim->GetPelvisDrop());
			Crouch = FMath::Max(Crouch, Anim->GetCrouchAlpha());
			for (const TCHAR* Foot : { TEXT("foot_L"), TEXT("foot_R") })
			{
				const FVector At = C->GetActorTransform().InverseTransformPosition(Body->GetBoneLocation(Foot));
				if (At.Z < -78.0f)                                // (on or near the ground)
				{
					Wide = FMath::Max(Wide, FMath::Abs(static_cast<float>(At.Y)));
				}
			}
		});
		const TCHAR* Name = Pace == 0 ? TEXT("walk") : (bSprint ? TEXT("sprint") : TEXT("run"));
		AddInfo(FString::Printf(TEXT("%s: standing hips %.1f cm; running %.1f .. %.1f (mean %.1f); pelvis drop %.1f; crouch %.2f; feet %.1f cm from the line; weights walk %.2f run %.2f stroll %.2f idle %.2f"),
			Name, Standing, Low, High, Sum / N, Drop, Crouch, Wide, Anim->Weights[1], Anim->Weights[2], Anim->Weights[8], Anim->Weights[0]));
		TestTrue(FString::Printf(TEXT("%s: the hips ride tall (mean %.1f cm under standing height, lowest %.1f)"), Name, Standing - Sum / N, Standing - Low),
			Standing - Sum / N < 7.0f && Standing - Low < 12.0f);
		TestTrue(FString::Printf(TEXT("%s: nothing sinks the hips under the clip (%.1f cm, crouch %.2f)"), Name, Drop, Crouch), Drop < 3.0f && Crouch < 0.02f);
		TestTrue(FString::Printf(TEXT("%s: the feet land under the hips, not out past them (%.1f cm to the side at most)"), Name, Wide), Wide < 11.0f);
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOCrouchWalkTest, "ShatteredOrbit.Anim.CrouchWalk", SOTest::Flags)
bool FSOCrouchWalkTest::RunTest(const FString& Parameters)
{
	// Crouched, still and walking (forward, sideways, backward): the body plays its own crouch clips, nothing sinks
	// the hips at runtime, both feet stay on or over the floor, no knee comes near the floor or bends backward, and
	// the hips ride level (the legs never pop).
	if (SOTest::PlayerBodyMissing(*this))
	{
		return true;
	}
	static const TCHAR* Names[4] = { TEXT("still"), TEXT("forward"), TEXT("sideways"), TEXT("backward") };
	for (const int32 Way : { 0, 1, 2, 3 })
	{
		SOTest::FTestWorld W;
		SOTest::Floor(W);
		ASOCharacter* C = W.SpawnCharacter(FVector(0, -1500, 0));
		USkeletalMeshComponent* Body = C->GetMesh();
		Body->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
		W.Run(1.5f);
		const USOLocomotionAnimInstance* Anim = Cast<USOLocomotionAnimInstance>(Body->GetAnimInstance());
		if (!TestNotNull(TEXT("the body's animation"), Anim))
		{
			return false;
		}
		if (!Anim->HasCrouchClips())
		{
			AddWarning(TEXT("this body has no crouch clips yet (import them: SO_IMPORT_ONLY=player_clips)"));
			return true;
		}
		const float Standing = static_cast<float>(Body->GetBoneLocation(TEXT("hips")).Z) - SOTest::Feet(C);
		// the ball of the foot against the ankle, in the reference pose (the foot bone runs from the ankle to the ball)
		const FReferenceSkeleton& Ref = Body->GetSkeletalMeshAsset()->GetRefSkeleton();
		auto RefCS = [&Ref](const TCHAR* Name)
		{
			FTransform T = FTransform::Identity;
			for (int32 I = Ref.FindBoneIndex(Name); I != INDEX_NONE; I = Ref.GetParentIndex(I))
			{
				T = T * Ref.GetRefBonePose()[I];
			}
			return T;
		};
		const FVector Dir = Way == 2 ? FVector::RightVector : (Way == 3 ? -FVector::ForwardVector : FVector::ForwardVector);
		const float Stick = Way == 0 ? 0.0f : 1.0f;
		C->Crouch();
		W.Run(1.0f, [&] { C->AddMovementInput(Dir, Stick); });
		float FootLow = BIG_NUMBER, BallLow = BIG_NUMBER, KneeLow = BIG_NUMBER, KneeBack = BIG_NUMBER, HipLow = BIG_NUMBER, HipHigh = -BIG_NUMBER, Drop = 0.0f, Clip = 1.0f;
		W.Run(1.6f, [&]
		{
			C->AddMovementInput(Dir, Stick);
			const float Floor = SOTest::Feet(C);
			const float Z = static_cast<float>(Body->GetBoneLocation(TEXT("hips")).Z) - Floor;
			HipLow = FMath::Min(HipLow, Z);
			HipHigh = FMath::Max(HipHigh, Z);
			Drop = FMath::Max(Drop, Anim->GetPelvisDrop());
			Clip = FMath::Min(Clip, Anim->Weights[13] + Anim->Weights[14]);
			const FTransform ToMesh = Body->GetComponentTransform();
			for (int32 Side = 0; Side < 2; ++Side)
			{
				const TCHAR* Thigh = Side ? TEXT("thigh_R") : TEXT("thigh_L");
				const TCHAR* Shin = Side ? TEXT("shin_R") : TEXT("shin_L");
				const TCHAR* Foot = Side ? TEXT("foot_R") : TEXT("foot_L");
				const FVector Hip = Body->GetBoneLocation(Thigh), Knee = Body->GetBoneLocation(Shin), Ankle = Body->GetBoneLocation(Foot);
				FootLow = FMath::Min(FootLow, static_cast<float>(Ankle.Z) - Floor);
				KneeLow = FMath::Min(KneeLow, static_cast<float>(Knee.Z) - Floor);
				// the ball: the reference foot's ankle -> ball, carried by the foot bone as it is now
				const FTransform FootRef = RefCS(Foot);
				const FVector BallRef(FootRef.GetLocation().X, FootRef.GetLocation().Y + 13.0f, 2.6f);
				const FVector Ball = Body->GetBoneTransform(Body->GetBoneIndex(Foot)).TransformPosition(FootRef.InverseTransformPosition(BallRef));
				BallLow = FMath::Min(BallLow, static_cast<float>(Ball.Z) - Floor);
				// the knee against the line from the hip to the ankle, measured along the body's forward
				const FVector Line = (Ankle - Hip).GetSafeNormal();
				const FVector Off = (Knee - Hip) - Line * FVector::DotProduct(Knee - Hip, Line);
				KneeBack = FMath::Min(KneeBack, static_cast<float>(FVector::DotProduct(Off, ToMesh.GetUnitAxis(EAxis::Y))));
			}
		});
		AddInfo(FString::Printf(TEXT("crouched %s: hips %.1f .. %.1f cm (standing %.1f); ankles >= %.1f, balls >= %.1f, knees >= %.1f cm over the floor; knee %.1f cm ahead of the hip-ankle line at least; pelvis drop %.1f; crouch clips %.2f"),
			Names[Way], HipLow, HipHigh, Standing, FootLow, BallLow, KneeLow, KneeBack, Drop, Clip));
		TestTrue(FString::Printf(TEXT("crouched %s: the crouch clips play (%.2f)"), Names[Way], Clip), Clip > 0.97f);
		TestTrue(FString::Printf(TEXT("crouched %s: nothing bends the legs at runtime (pelvis drop %.1f cm)"), Names[Way], Drop), Drop < 3.0f);
		TestTrue(FString::Printf(TEXT("crouched %s: the hips are down (%.1f cm under standing) and level (%.1f cm of travel)"), Names[Way], Standing - HipHigh, HipHigh - HipLow),
			Standing - HipHigh > 14.0f && Standing - HipLow < 40.0f && HipHigh - HipLow < 6.0f);
		TestTrue(FString::Printf(TEXT("crouched %s: no foot under the floor (ankle %.1f cm, ball %.1f cm over it)"), Names[Way], FootLow, BallLow), FootLow > 3.0f && BallLow > -2.5f);
		TestTrue(FString::Printf(TEXT("crouched %s: the knees stay off the floor (%.1f cm)"), Names[Way], KneeLow), KneeLow > 14.0f);
		TestTrue(FString::Printf(TEXT("crouched %s: no knee bends backward (%.1f cm ahead of the hip-ankle line)"), Names[Way], KneeBack), KneeBack > 1.0f);
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOCrouchFirstPersonTest, "ShatteredOrbit.Anim.CrouchFirstPerson", SOTest::Flags)
bool FSOCrouchFirstPersonTest::RunTest(const FString& Parameters)
{
	// The first-person arms hang from the eye: crouched, sliding or standing, the shoulders sit as far under the camera
	// as they do standing (they used to stay on the capsule, and crouched the arms came down into the view from above).
	if (SOTest::PlayerBodyMissing(*this))
	{
		return true;
	}
	SOTest::FTestWorld W;
	SOTest::Floor(W);
	ASOCharacter* C = W.SpawnCharacter(FVector(0, 0, 0));
	C->SetViewMode(ESOViewMode::FirstPerson);
	USkeletalMeshComponent* Arms = C->GetFirstPersonArms();
	if (!TestNotNull(TEXT("the first-person arms"), Arms))
	{
		return false;
	}
	W.Run(1.0f);
	const bool bBone = Arms->GetBoneIndex(TEXT("upperarm_R")) != INDEX_NONE;
	auto Under = [&]()
	{
		const float Eye = static_cast<float>(C->GetEyeTransform(false).GetLocation().Z);
		return FVector2f(Eye - static_cast<float>(Arms->GetComponentLocation().Z), bBone ? Eye - static_cast<float>(Arms->GetBoneLocation(TEXT("upperarm_R")).Z) : 0.0f);
	};
	const FVector2f Standing = Under();
	const float EyeStanding = static_cast<float>(C->GetEyeTransform(false).GetLocation().Z) - SOTest::Feet(C);
	C->Crouch();
	float Worst = 0.0f;
	W.Run(1.5f, [&] { Worst = FMath::Max(Worst, FMath::Abs(Under().X - Standing.X)); });
	const FVector2f Crouched = Under();
	const float EyeCrouched = static_cast<float>(C->GetEyeTransform(false).GetLocation().Z) - SOTest::Feet(C);
	AddInfo(FString::Printf(TEXT("eye %.1f cm standing, %.1f crouched; arms' origin %.1f / %.1f cm under the eye; shoulder %.1f / %.1f cm under the eye; worst on the way down %.1f"),
		EyeStanding, EyeCrouched, Standing.X, Crouched.X, Standing.Y, Crouched.Y, Worst));
	TestTrue(TEXT("the eye came down with the crouch"), EyeStanding - EyeCrouched > 30.0f);
	TestTrue(FString::Printf(TEXT("the arms stay under the eye all the way down (%.1f cm off at most)"), Worst), Worst < 1.0f);
	TestTrue(FString::Printf(TEXT("crouched, the shoulder is as far under the eye as standing (%.1f against %.1f cm)"), Crouched.Y, Standing.Y),
		!bBone || FMath::Abs(Crouched.Y - Standing.Y) < 3.0f);
	C->UnCrouch();
	W.Run(1.0f);
	TestTrue(TEXT("standing again, the arms are back where they were"), FMath::Abs(Under().X - Standing.X) < 1.0f);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOStopsAndTurnsTest, "ShatteredOrbit.Anim.StopsAndTurns", SOTest::Flags)
bool FSOStopsAndTurnsTest::RunTest(const FString& Parameters)
{
	// Coming to a standstill out of a run plays the body's brake and lets go of it; a turn on the spot is stepped (each
	// foot comes off the ground in turn, never both at once); on a ledge the first-person hands are free of the gun.
	if (SOTest::PlayerBodyMissing(*this))
	{
		return true;
	}
	SOTest::FTestWorld W;
	SOTest::Floor(W);
	ASOCharacter* C = W.SpawnCharacter(FVector(-1000, 0, 0));
	USkeletalMeshComponent* Body = C->GetMesh();
	Body->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
	W.Run(1.0f);
	const USOLocomotionAnimInstance* Anim = Cast<USOLocomotionAnimInstance>(Body->GetAnimInstance());
	if (!TestNotNull(TEXT("the body's animation"), Anim))
	{
		return false;
	}
	if (Anim->Clips.Stop)
	{
		C->GetSOMovement()->SetWantsToSprint(true);
		W.Run(1.2f, [&] { C->AddMovementInput(FVector::ForwardVector, 1.0f); });
		C->GetSOMovement()->SetWantsToSprint(false);
		float Brake = 0.0f;
		W.Run(0.6f, [&] { Brake = FMath::Max(Brake, Anim->Weights[15]); });
		W.Run(0.6f);
		TestTrue(FString::Printf(TEXT("stopping out of a sprint shows the brake (%.2f)"), Brake), Brake > 0.3f);
		TestTrue(FString::Printf(TEXT("...and lets go of it (%.2f left, idle %.2f)"), Anim->Weights[15], Anim->Weights[0]), Anim->Weights[15] < 0.03f && Anim->Weights[0] > 0.9f);
	}
	else
	{
		AddWarning(TEXT("this body has no Stop clip yet (import it: SO_IMPORT_ONLY=player_clips)"));
	}
	// a quarter turn on the spot
	{
		W.Run(0.5f);
		float Up[2] = { 0.0f, 0.0f }, Both = 0.0f;
		bool bTurned = false;
		float Turned = 0.0f;
		W.Run(1.2f, [&]
		{
			if (Turned < 90.0f)
			{
				Turned += 6.0f;
				C->SetActorRotation(C->GetActorRotation() + FRotator(0.0f, 6.0f, 0.0f));
			}
			bTurned |= Anim->IsTurningInPlace();
			Up[0] = FMath::Max(Up[0], Anim->GetTurnLift(0));
			Up[1] = FMath::Max(Up[1], Anim->GetTurnLift(1));
			Both = FMath::Max(Both, FMath::Min(Anim->GetTurnLift(0), Anim->GetTurnLift(1)));
		});
		W.Run(0.5f);
		TestTrue(TEXT("a quarter turn standing still turns on the spot"), bTurned);
		TestTrue(FString::Printf(TEXT("each foot steps (left %.1f cm, right %.1f cm up)"), Up[0], Up[1]), Up[0] > 3.0f && Up[1] > 3.0f);
		TestTrue(FString::Printf(TEXT("never both off the ground at once (%.1f cm)"), Both), Both < 1.5f);
		TestTrue(TEXT("both planted again after the turn"), Anim->GetTurnLift(0) < 0.2f && Anim->GetTurnLift(1) < 0.2f);
	}
	return true;
}

#endif
