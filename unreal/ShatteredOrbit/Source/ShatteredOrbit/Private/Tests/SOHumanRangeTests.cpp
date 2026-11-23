// The body moves only as a human body can (the owner, 2026-11-23, word for word: "head/arms/legs/body bends a normal
// amount not crazy" and "these rules should always apply, the player should not be bending any part of their body in a
// way a normal human cant or in a way harmful to a humans"). Every joint of the player's body is measured, in every
// state a player puts it in and in both views, against a normal, healthy human range of motion: the head on the chest,
// the chest on the hips, the elbows, the wrists, the knees (never bent backward), the ankles.

#include "SOTestWorld.h"

#if WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR

#include "Algo/IndexOf.h"
#include "AnimationRuntime.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "GameFramework/PlayerController.h"
#include "SOCharacter.h"
#include "SOCharacterMovementComponent.h"
#include "SOInventoryComponent.h"
#include "SOLootLibrary.h"
#include "SOLootTypes.h"
#include "SOPlayerState.h"
#include "SOWeapon.h"

namespace SOHumanRange
{
	/** One limit: a joint's measure (degrees, or cm for a knee behind its line) and the range a healthy human body has. */
	struct FLimit
	{
		const TCHAR* Joint;
		float Least;
		float Most;
	};

	// (normal ranges of motion, a little inside what a supple body reaches)
	static const FLimit Limits[] = {
		{ TEXT("head pitch on the chest (+ up)"), -65.0f, 65.0f },
		{ TEXT("head turn on the chest"), -80.0f, 80.0f },
		{ TEXT("head tilt on the chest"), -45.0f, 45.0f },
		{ TEXT("chest pitch on the hips (+ back)"), -80.0f, 30.0f },
		{ TEXT("chest twist on the hips"), -50.0f, 50.0f },
		{ TEXT("chest side bend on the hips"), -35.0f, 35.0f },
		{ TEXT("right elbow bend"), 0.0f, 150.0f },
		{ TEXT("left elbow bend"), 0.0f, 150.0f },
		{ TEXT("right wrist bend"), 0.0f, 80.0f },
		{ TEXT("left wrist bend"), 0.0f, 80.0f },
		{ TEXT("right knee bend"), 0.0f, 145.0f },
		{ TEXT("left knee bend"), 0.0f, 145.0f },
		{ TEXT("right knee behind its line (cm)"), -100.0f, 2.0f },
		{ TEXT("left knee behind its line (cm)"), -100.0f, 2.0f },
		{ TEXT("right ankle (90 standing)"), 54.0f, 145.0f },   // (35 degrees up with the knee bent, a deep squat's; 55 down)
		{ TEXT("left ankle (90 standing)"), 54.0f, 145.0f },
	};
	static constexpr int32 NumLimits = UE_ARRAY_COUNT(Limits);

	/** Every measure of the body's last pose, in the order of Limits; false when the skeleton lacks a bone. */
	bool Measure(const USkeletalMeshComponent* Body, float (&Out)[NumLimits])
	{
		const USkeletalMesh* Mesh = Body ? Body->GetSkeletalMeshAsset() : nullptr;
		if (!Mesh)
		{
			return false;
		}
		const FReferenceSkeleton& Ref = Mesh->GetRefSkeleton();
		const TArray<FTransform>& CS = Body->GetComponentSpaceTransforms();
		auto Index = [&](const TCHAR* Name) { return Body->GetBoneIndex(Name); };
		for (const TCHAR* Name : { TEXT("hips"), TEXT("chest"), TEXT("head"), TEXT("upperarm_R"), TEXT("forearm_R"), TEXT("hand_R"), TEXT("middle_01_R"),
			TEXT("upperarm_L"), TEXT("forearm_L"), TEXT("hand_L"), TEXT("middle_01_L"), TEXT("thigh_R"), TEXT("shin_R"), TEXT("foot_R"), TEXT("thigh_L"),
			TEXT("shin_L"), TEXT("foot_L") })
		{
			if (Index(Name) == INDEX_NONE || !CS.IsValidIndex(Index(Name)))
			{
				return false;
			}
		}
		auto At = [&](const TCHAR* Name) { return CS[Index(Name)].GetLocation(); };
		// a bone's own forward / up / left now, from what they were at rest (component space: +Y forward, +Z up, +X left)
		auto Axis = [&](const TCHAR* Name, const FVector& RestAxis)
		{
			const int32 I = Index(Name);
			const FQuat Rest = FAnimationRuntime::GetComponentSpaceTransformRefPose(Ref, I).GetRotation();
			return CS[I].GetRotation().RotateVector(Rest.UnrotateVector(RestAxis)).GetSafeNormal();
		};
		const FVector Fwd(0.0f, 1.0f, 0.0f), Up(0.0f, 0.0f, 1.0f), Left(1.0f, 0.0f, 0.0f);
		auto Deg = [](double R) { return static_cast<float>(FMath::RadiansToDegrees(R)); };
		// one frame against another: pitch (+ up), turn (+ to the left), tilt (+ the top to the right)
		auto Against = [&](const TCHAR* Bone, const TCHAR* Base, float& Pitch, float& Turn, float& Tilt)
		{
			const FVector F = Axis(Bone, Fwd), L = Axis(Bone, Left);
			const FVector BF = Axis(Base, Fwd), BU = Axis(Base, Up), BL = Axis(Base, Left);
			Pitch = Deg(FMath::Asin(FMath::Clamp(FVector::DotProduct(F, BU), -1.0, 1.0)));
			Turn = Deg(FMath::Atan2(FVector::DotProduct(F, BL), FVector::DotProduct(F, BF)));
			Tilt = Deg(FMath::Asin(FMath::Clamp(FVector::DotProduct(L, BU), -1.0, 1.0)));
		};
		Against(TEXT("head"), TEXT("chest"), Out[0], Out[1], Out[2]);
		Against(TEXT("chest"), TEXT("hips"), Out[3], Out[4], Out[5]);
		auto Bend = [&](const FVector& A, const FVector& B, const FVector& C)
		{
			return Deg(FMath::Acos(FMath::Clamp(FVector::DotProduct((B - A).GetSafeNormal(), (C - B).GetSafeNormal()), -1.0, 1.0)));
		};
		Out[6] = Bend(At(TEXT("upperarm_R")), At(TEXT("forearm_R")), At(TEXT("hand_R")));
		Out[7] = Bend(At(TEXT("upperarm_L")), At(TEXT("forearm_L")), At(TEXT("hand_L")));
		Out[8] = Bend(At(TEXT("forearm_R")), At(TEXT("hand_R")), At(TEXT("middle_01_R")));
		Out[9] = Bend(At(TEXT("forearm_L")), At(TEXT("hand_L")), At(TEXT("middle_01_L")));
		Out[10] = Bend(At(TEXT("thigh_R")), At(TEXT("shin_R")), At(TEXT("foot_R")));
		Out[11] = Bend(At(TEXT("thigh_L")), At(TEXT("shin_L")), At(TEXT("foot_L")));
		// a knee bends forward over the toes, never back: how far it stands behind the line from its hip to its ankle,
		// along the way its foot points
		auto Behind = [&](const TCHAR* Thigh, const TCHAR* Shin, const TCHAR* Foot)
		{
			const FVector H = At(Thigh), K = At(Shin), A = At(Foot);
			const FVector D = (A - H).GetSafeNormal();
			const FVector Off = (K - H) - D * FVector::DotProduct(K - H, D);
			FVector Toes = Axis(Foot, Fwd);
			Toes = (Toes - D * FVector::DotProduct(Toes, D)).GetSafeNormal();
			return static_cast<float>(-FVector::DotProduct(Off, Toes));
		};
		Out[12] = Behind(TEXT("thigh_R"), TEXT("shin_R"), TEXT("foot_R"));
		Out[13] = Behind(TEXT("thigh_L"), TEXT("shin_L"), TEXT("foot_L"));
		// the ankle: between the way up the shin and the way the foot points (90 standing; less, the toes drawn up;
		// more, pointed)
		auto Ankle = [&](const TCHAR* Shin, const TCHAR* Foot)
		{
			const FVector UpShin = (At(Shin) - At(Foot)).GetSafeNormal();
			return Deg(FMath::Acos(FMath::Clamp(FVector::DotProduct(UpShin, Axis(Foot, Fwd)), -1.0, 1.0)));
		};
		Out[14] = Ankle(TEXT("shin_R"), TEXT("foot_R"));
		Out[15] = Ankle(TEXT("shin_L"), TEXT("foot_L"));
		return true;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOHumanRangeTest, "ShatteredOrbit.Body.HumanRange", SOTest::Flags)
bool FSOHumanRangeTest::RunTest(const FString& Parameters)
{
	using namespace SOHumanRange;
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
	USkeletalMeshComponent* Body = Player->GetMesh();
	Body->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
	USOCharacterMovementComponent* Move = Player->GetSOMovement();

	// the worst of every joint in every state (and what it was), over every frame once the state is under way
	TMap<FString, TPair<float, float>> Worst;   // (state + joint) -> (least, most) seen
	FString State;
	int32 Frames = 0;
	auto Sample = [&]()
	{
		float M[NumLimits];
		if (!Measure(Body, M))
		{
			return;
		}
		++Frames;
		for (int32 i = 0; i < NumLimits; ++i)
		{
			TPair<float, float>& Seen = Worst.FindOrAdd(State + TEXT(": ") + Limits[i].Joint, TPair<float, float>(M[i], M[i]));
			Seen.Key = FMath::Min(Seen.Key, M[i]);
			Seen.Value = FMath::Max(Seen.Value, M[i]);
		}
	};
	auto Hold = [&](const FString& Name, float Seconds, TFunctionRef<void()> Each)
	{
		State = Name;
		int32 Frame = 0;
		const int32 Settle = Name.Contains(TEXT("reload")) || Name.Contains(TEXT("blow")) ? 0 : FMath::RoundToInt(0.2f / SOTest::Dt);
		W.Run(Seconds, [&]() { Each(); Player->FaceRotation(PC->GetControlRotation(), SOTest::Dt); if (++Frame > Settle && (Frame % 2) == 0) { Sample(); } });
	};

	FRandomStream Rng(31);
	for (const TCHAR* Arch : { TEXT("rifle"), TEXT("pistol"), TEXT("smg"), TEXT("hmg"), TEXT("sniper"), TEXT("shotgun"), TEXT("rocket") })
	{
		Player->SetActorLocation(FVector(0.0f, 0.0f, 92.0f));
		PC->SetControlRotation(FRotator::ZeroRotator);
		ASOWeapon* Gun = Player->EquipInstance(USOLootLibrary::MakeWeapon(Arch, 2, 20, Rng));
		W.Run(0.8f);
		if (!TestNotNull(FString::Printf(TEXT("%s in the hands"), Arch), Gun))
		{
			continue;
		}
		for (int32 Pass = 0; Pass < 2; ++Pass)
		{
			const FString View = Pass == 0 ? TEXT("first person") : TEXT("third person");
			Player->SetViewMode(Pass == 0 ? ESOViewMode::FirstPerson : ESOViewMode::ThirdPerson);
			Player->CancelCombat();
			W.Run(0.4f);
			auto Name = [&](const TCHAR* What) { return FString::Printf(TEXT("%s, %s, %s"), Arch, *View, What); };
			Hold(Name(TEXT("relaxed")), 0.8f, [&]() {});
			Hold(Name(TEXT("at the ready")), 0.6f, [&]() { Player->MarkCombat(); });
			Player->HandleAimPressed();
			Hold(Name(TEXT("on the sights")), 0.7f, [&]() { Player->MarkCombat(); });
			Gun->StartFire();
			Hold(Name(TEXT("firing")), 0.45f, [&]() { Player->MarkCombat(); });
			Gun->StopFire();
			Player->HandleAimReleased();
			Hold(Name(TEXT("walking")), 0.8f, [&]() { Player->AddMovementInput(Player->GetActorForwardVector(), 1.0f); });
			float Yaw = PC->GetControlRotation().Yaw;
			Hold(Name(TEXT("turning")), 0.6f, [&]() { Yaw += 4.0f; PC->SetControlRotation(FRotator(0.0f, Yaw, 0.0f)); Player->MarkCombat(); });
			for (const float Pitch : { 80.0f, 60.0f, -60.0f, -80.0f })
			{
				Hold(Name(*FString::Printf(TEXT("looking %s %.0f"), Pitch > 0.0f ? TEXT("up") : TEXT("down"), FMath::Abs(Pitch))), 0.6f,
					[&]() { PC->SetControlRotation(FRotator(Pitch, Yaw, 0.0f)); Player->MarkCombat(); });
			}
			Player->HandleAimPressed();
			Hold(Name(TEXT("on the sights looking up 60")), 0.7f, [&]() { PC->SetControlRotation(FRotator(60.0f, Yaw, 0.0f)); Player->MarkCombat(); });
			Hold(Name(TEXT("on the sights looking down 60")), 0.7f, [&]() { PC->SetControlRotation(FRotator(-60.0f, Yaw, 0.0f)); Player->MarkCombat(); });
			Player->HandleAimReleased();
			PC->SetControlRotation(FRotator(0.0f, Yaw, 0.0f));
			Gun->SetAmmo(0, 200);
			Gun->StartReload();
			Hold(Name(TEXT("reloading")), FMath::Max(Gun->GetReloadDuration(), 0.5f) + 0.3f, [&]() {});
			if (Pass == 1)
			{
				continue;   // (the body moves the same whichever view is on it: the movement once)
			}
			Move->SetWantsToSprint(true);
			Hold(Name(TEXT("sprinting")), 1.0f, [&]() { Player->AddMovementInput(Player->GetActorForwardVector(), 1.0f); });
			Player->Crouch();
			Hold(Name(TEXT("sliding")), 0.6f, [&]() { Player->AddMovementInput(Player->GetActorForwardVector(), 1.0f); });
			Move->SetWantsToSprint(false);
			Player->UnCrouch();
			W.Run(0.5f);
			Player->Jump();
			Hold(Name(TEXT("jumping")), 0.9f, [&]() { Player->AddMovementInput(Player->GetActorForwardVector(), 1.0f); });
			Player->StopJumping();
			Player->Crouch();
			Hold(Name(TEXT("crouched, walking")), 1.0f, [&]() { Player->AddMovementInput(Player->GetActorForwardVector(), 1.0f); });
			Hold(Name(TEXT("crouched, looking down 60")), 0.6f, [&]() { PC->SetControlRotation(FRotator(-60.0f, Yaw, 0.0f)); });
			PC->SetControlRotation(FRotator(0.0f, Yaw, 0.0f));
			Player->UnCrouch();
			W.Run(0.4f);
		}
	}
	// hand to hand: the guard, the light chain, the heavy blow, on the move
	Player->SetViewMode(ESOViewMode::FirstPerson);
	PC->SetControlRotation(FRotator::ZeroRotator);
	Player->SetFists(true);
	W.Run(0.4f);
	Hold(TEXT("fists, the guard"), 0.6f, [&]() {});
	for (int32 k = 0; k < 4; ++k)
	{
		Player->MeleeStrike(false);
		Hold(FString::Printf(TEXT("fists, light blow %d"), k + 1), 0.55f, [&]() {});
	}
	Player->MeleeStrike(true);
	Hold(TEXT("fists, the heavy blow"), 1.0f, [&]() {});
	Hold(TEXT("fists, walking"), 0.8f, [&]() { Player->AddMovementInput(Player->GetActorForwardVector(), 1.0f); });
	Move->SetWantsToSprint(true);
	Hold(TEXT("fists, sprinting"), 0.8f, [&]() { Player->AddMovementInput(Player->GetActorForwardVector(), 1.0f); });
	Move->SetWantsToSprint(false);

	for (const TPair<FString, TPair<float, float>>& It : Worst)
	{
		const int32 Joint = static_cast<int32>(Algo::IndexOfByPredicate(Limits, [&](const FLimit& L) { return It.Key.EndsWith(L.Joint); }));
		if (Joint == INDEX_NONE)
		{
			continue;
		}
		const FLimit& L = Limits[Joint];
		TestTrue(FString::Printf(TEXT("%s: %.1f to %.1f, a human's %.0f to %.0f"), *It.Key, It.Value.Key, It.Value.Value, L.Least, L.Most),
			It.Value.Key >= L.Least && It.Value.Value <= L.Most);
	}
	AddInfo(FString::Printf(TEXT("%d frames of %d states measured"), Frames, Worst.Num() / NumLimits));
	TestTrue(TEXT("the body was measured"), Frames > 0);
	return true;
}

#endif
