#include "SOLocomotionAnimInstance.h"

#include "Animation/AnimSequenceBase.h"
#include "Animation/AnimationPoseData.h"
#include "AnimationRuntime.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "SOCharacterMovementComponent.h"
#include "SOCharacter.h"
#include "SOCombatCharacter.h"
#include "SOGunRigComponent.h"
#include "SOViewmodelComponent.h"
#include "SOWeapon.h"

namespace
{
	enum ELayer { Idle = 0, Walk, Run, Jump, Death, Attack, Slide, Fidget, Count };
}

void USOLocomotionAnimInstance::PlayAttack(float PlayRate)
{
	PlayAction(Clips.Attack, PlayRate);
}

void USOLocomotionAnimInstance::PlayAction(UAnimSequenceBase* Clip, float PlayRate)
{
	if (Clip)
	{
		ActiveAttack = Clip;
		AttackTime = 0.0f;
		AttackRate = FMath::Max(PlayRate, 0.05f);
	}
}

float USOLocomotionAnimInstance::GetAttackLength() const
{
	return Clips.Attack ? Clips.Attack->GetPlayLength() : 0.0f;
}

void USOLocomotionAnimInstance::NativeUpdateAnimation(float DeltaSeconds)
{
	Super::NativeUpdateAnimation(DeltaSeconds);

	const ACharacter* Character = Cast<ACharacter>(TryGetPawnOwner());
	if (Character)
	{
		Speed = Character->GetVelocity().Size2D();
		const UCharacterMovementComponent* Move = Character->GetCharacterMovement();
		bInAir = Move && Move->IsFalling();
		const USOCharacterMovementComponent* SOMove = Cast<USOCharacterMovementComponent>(Move);
		bSliding = SOMove && SOMove->IsSliding();
		bMantling = SOMove && SOMove->IsMantling();
		const ASOCombatCharacter* Combat = Cast<ASOCombatCharacter>(Character);
		bDead = Combat && Combat->IsDead();
	}

	// Held gun: the hold components were placed this frame (they tick before the bodies); reach for the rig's grips.
	bHold = false;
	const ASOCharacter* Player = Cast<ASOCharacter>(Character);
	const USkeletalMeshComponent* Mesh = GetSkelMeshComponent();
	bArmsOnly = Player && Mesh && Mesh == Player->GetFirstPersonArms();
	// The arms mesh is already only arms; the whole body standing in for it gets everything else collapsed.
	bCollapseBody = bArmsOnly && Mesh->GetSkeletalMeshAsset() == Player->GetMesh()->GetSkeletalMeshAsset();
	// anyone who fights holds their gun this way: the player, and the creatures that carry guns
	const ASOCombatCharacter* Holder = Cast<ASOCombatCharacter>(Character);
	const ASOWeapon* Held = Holder ? Holder->GetWeapon() : nullptr;
	const USOGunRigComponent* Rig = Held ? (bArmsOnly ? Held->GetFirstPersonRig() : Held->GetThirdPersonRig()) : nullptr;
	FTransform Right, Left;
	if (!bDead && Mesh && Rig && Rig->GetAttachParent() && Rig->GetHandTargets(Right, Left))
	{
		const FTransform ToMesh = Mesh->GetComponentTransform();
		RightTarget = Right.GetRelativeTransform(ToMesh);
		LeftTarget = Left.GetRelativeTransform(ToMesh);
		Rig->GetFingerPoses(RightFingers, LeftFingers);
		const float Ads = Player ? (Player->GetViewmodel() ? Player->GetViewmodel()->GetAds() : 0.0f) : (Holder->IsAimingDownSights() ? 1.0f : 0.0f);
		AimPitch = FRotator::NormalizeAxis(Player ? Player->GetAimRotation().Pitch : Holder->GetBaseAimRotation().Pitch);
		EyeCS = ToMesh.InverseTransformPosition(Player ? Player->GetEyeTransform(false).GetLocation() : Holder->GetPawnViewLocation());
		bOneHand = Holder->HoldsWithOneHand();
		// First person keeps a gentler stance so the off shoulder stays out of the corner of the view.
		const float Stance = bArmsOnly ? 0.5f : 1.0f;
		// long guns blade the body to the gun; handguns square up (both arms out, an isosceles stance)
		const bool bHandgun = Rig->IsHandgun();
		Blade = (bHandgun ? FMath::Lerp(5.0f, 8.0f, Ads) : FMath::Lerp(12.0f, 24.0f, Ads)) * Stance;
		Lean = FMath::Lerp(4.0f, 9.0f, Ads) * Stance;
		HeadCant = bArmsOnly || bHandgun ? 0.0f : Ads * 14.0f;
		bHold = true;
	}

	UpdateBodyMotion(Character, DeltaSeconds);

	// Target weights.
	float Target[Count] = { 0, 0, 0, 0, 0, 0, 0, 0 };
	const bool bAttacking = AttackTime >= 0.0f && ActiveAttack;
	if (bDead && Clips.Death)
	{
		Target[Death] = 1.0f;
	}
	else if (bAttacking)
	{
		Target[Attack] = 1.0f;
	}
	else if (bSliding && Clips.Slide)
	{
		Target[Slide] = 1.0f;
	}
	else if ((bInAir || bMantling) && Clips.Jump)
	{
		Target[Jump] = 1.0f;
	}
	else
	{
		const float Walk01 = FMath::Clamp(Speed / FMath::Max(Clips.WalkSpeed * 0.5f, 1.0f), 0.0f, 1.0f);
		const float Run01 = FMath::Clamp((Speed - Clips.WalkSpeed) / FMath::Max(Clips.RunSpeed - Clips.WalkSpeed, 1.0f), 0.0f, 1.0f);
		Target[Idle] = 1.0f - Walk01;
		Target[Walk] = Walk01 * (Clips.Run ? 1.0f - Run01 : 1.0f);
		Target[Run] = Clips.Run ? Walk01 * Run01 : 0.0f;
	}

	// Idle variations: standing still, not aiming, a full body (the first-person arms never fidget).
	const bool bAimingNow = Player && Player->GetViewmodel() && Player->GetViewmodel()->GetAds() > 0.01f;
	const bool bStill = Target[Idle] > 0.99f && Speed < 10.0f && !bArmsOnly && !bAimingNow && Clips.Fidgets.Num() > 0;
	if (!bStill)
	{
		StillTime = 0.0f;
		ActiveFidget = -1;
	}
	else if (ActiveFidget < 0)
	{
		if (NextFidget < 0.0f)
		{
			NextFidget = FMath::FRandRange(FidgetDelay.X, FidgetDelay.Y);
		}
		StillTime += DeltaSeconds;
		if (StillTime >= NextFidget)
		{
			const int32 N = Clips.Fidgets.Num();
			int32 Pick = FMath::RandRange(0, N - 1);
			if (N > 1 && Pick == LastFidget)
			{
				Pick = (Pick + 1) % N;
			}
			if (Clips.Fidgets[Pick])
			{
				ActiveFidget = LastFidget = Pick;
				FidgetClip = Clips.Fidgets[Pick];
				Times[Fidget] = 0.0f;
			}
			StillTime = 0.0f;
			NextFidget = FMath::FRandRange(FidgetDelay.X, FidgetDelay.Y);
		}
	}
	if (ActiveFidget >= 0 && FidgetClip)
	{
		Times[Fidget] += DeltaSeconds;
		if (Times[Fidget] >= FidgetClip->GetPlayLength() - BlendTime)
		{
			ActiveFidget = -1;             // blends back into the idle it started from
		}
		else
		{
			Target[Fidget] = Target[Idle];
			Target[Idle] = 0.0f;
		}
	}

	// Cross-fade (death snaps faster so it never floats).
	const float Rate = DeltaSeconds / FMath::Max(bDead ? BlendTime * 0.5f : BlendTime, 1e-3f);
	float Sum = 0.0f;
	for (int32 i = 0; i < Count; ++i)
	{
		Weights[i] = FMath::FInterpConstantTo(Weights[i], Target[i], 1.0f, Rate);
		Sum += Weights[i];
	}
	if (Sum > 1e-4f)
	{
		for (int32 i = 0; i < Count; ++i)
		{
			Weights[i] /= Sum;
		}
	}

	// Clip times: locomotion rate-matched to the ground speed, the rest at 1x; death and attack do not loop.
	const float WalkRate = FMath::Clamp(Speed / FMath::Max(Clips.WalkSpeed, 1.0f), 0.6f, 1.6f);
	const float RunRate = FMath::Clamp(Speed / FMath::Max(Clips.RunSpeed, 1.0f), 0.7f, 1.4f);
	Times[Idle] += DeltaSeconds;
	const float Direction = bBackward ? -1.0f : 1.0f; // backpedalling plays the cycle in reverse
	// One cycle phase for walk and run (both start on the left foot), advanced by the blend of their rates, so
	// blending the two never crosses the legs.
	const float WalkLen = Clips.Walk ? FMath::Max(Clips.Walk->GetPlayLength(), 0.05f) : 1.0f;
	const float RunLen = Clips.Run ? FMath::Max(Clips.Run->GetPlayLength(), 0.05f) : WalkLen;
	const float WW = Weights[Walk], WR = Weights[Run];
	const float PhaseRate = WW + WR > 1e-3f ? (WW * WalkRate / WalkLen + WR * RunRate / RunLen) / (WW + WR) : WalkRate / WalkLen;
	CyclePhase += DeltaSeconds * PhaseRate * Direction;
	CyclePhase -= FMath::FloorToFloat(CyclePhase);
	Times[Walk] = CyclePhase * WalkLen;
	Times[Run] = CyclePhase * RunLen;
	Times[Jump] = bInAir ? Times[Jump] + DeltaSeconds : 0.0f;
	Times[Death] = bDead ? Times[Death] + DeltaSeconds : 0.0f;
	Times[Slide] = bSliding ? Times[Slide] + DeltaSeconds : 0.0f;
	if (bAttacking)
	{
		AttackTime += DeltaSeconds * AttackRate;
		Times[Attack] = AttackTime;
		if (AttackTime >= ActiveAttack->GetPlayLength())
		{
			AttackTime = -1.0f;
		}
	}
}

void USOLocomotionAnimInstance::UpdateBodyMotion(const ACharacter* Character, float DeltaSeconds)
{
	const USkeletalMeshComponent* Mesh = GetSkelMeshComponent();
	const float Dt = FMath::Max(DeltaSeconds, 1e-4f);
	bBodyMotion = Character && Mesh && !bArmsOnly && !bDead;
	if (!bBodyMotion)
	{
		WarpYaw = LeanRoll = LeanPitch = PelvisDrop = FootIKAlpha = 0.0f;
		return;
	}
	const FTransform ToMesh = Mesh->GetComponentTransform();
	const FVector VelCS = ToMesh.InverseTransformVectorNoScale(Character->GetVelocity());

	// Orientation warping: component space has +Y forward, +X to the character's left; the angle that turns +Y onto
	// the velocity about +Z is atan2(-x, y). Past ~100 degrees the move is a backpedal: the cycle runs in reverse and
	// the legs only turn by what is left over.
	const float Speed2D = FVector2D(VelCS.X, VelCS.Y).Size();
	const bool bStriding = Speed2D > 40.0f && !bInAir && !bSliding && !bMantling;
	if (bStriding)
	{
		MoveYaw = FMath::RadiansToDegrees(FMath::Atan2(-VelCS.X, VelCS.Y));
		const float Abs = FMath::Abs(MoveYaw);
		bBackward = bBackward ? Abs > 95.0f : Abs > 110.0f;   // hysteresis: no flicker at the boundary
	}
	else if (Speed2D <= 40.0f)
	{
		bBackward = false;
	}
	float WantWarp = 0.0f;
	if (bStriding)
	{
		WantWarp = bBackward ? FRotator::NormalizeAxis(MoveYaw - 180.0f) : MoveYaw;
		WantWarp = FMath::Clamp(WantWarp, -MaxWarpYaw, MaxWarpYaw);
	}
	WarpYaw = FMath::FInterpTo(WarpYaw, WantWarp, Dt, 9.0f);

	// Lean into the acceleration (smoothed), a touch forward with speed.
	const FVector RawAccel = (VelCS - LastVelocityCS) / Dt;
	LastVelocityCS = VelCS;
	AccelCS = FMath::VInterpTo(AccelCS, bInAir ? FVector::ZeroVector : RawAccel, Dt, 7.0f);
	const float K = LeanPerAccel / 100.0f; // per cm/s2
	float WantRoll = FMath::Clamp(AccelCS.X * K, -MaxLean, MaxLean);
	float WantPitch = FMath::Clamp(-AccelCS.Y * K, -MaxLean, MaxLean) - FMath::Min(Speed2D / 860.0f, 1.0f) * 2.0f * (bBackward ? -1.0f : 1.0f);
	if (bSliding)
	{
		WantRoll = 0.0f;
		WantPitch = 0.0f;
	}

	// Landing: the hips sink with the impact and spring back.
	if (bInAir)
	{
		LastAirVz = Character->GetVelocity().Z;
	}
	else if (bWasInAir && !bMantling)
	{
		CompressVel += FMath::Clamp((-LastAirVz - 200.0f) * 0.12f, 0.0f, 160.0f);
	}
	bWasInAir = bInAir;
	const float Stiff = 260.0f, Damp = 2.0f * FMath::Sqrt(Stiff) * 0.75f;
	CompressVel += (-Stiff * Compress - Damp * CompressVel) * Dt;
	Compress = FMath::Max(Compress + CompressVel * Dt, 0.0f);
	WantPitch -= Compress * 0.6f;
	LeanRoll = FMath::FInterpTo(LeanRoll, WantRoll, Dt, 8.0f);
	LeanPitch = FMath::FInterpTo(LeanPitch, WantPitch, Dt, 8.0f);

	// Feet on the ground: a short trace under each ankle; the hips drop so the lower foot reaches.
	const UCharacterMovementComponent* Move = Character->GetCharacterMovement();
	const bool bGrounded = Move && Move->IsMovingOnGround() && !bSliding && !bMantling;
	const float WantAlpha = bGrounded ? FMath::Lerp(1.0f, 0.45f, FMath::Clamp(Speed2D / 860.0f, 0.0f, 1.0f)) : 0.0f;
	FootIKAlpha = FMath::FInterpTo(FootIKAlpha, WantAlpha, Dt, 10.0f);
	float Want[2] = { 0.0f, 0.0f };
	if (FootIKAlpha > 0.01f && GetWorld())
	{
		static const FName Feet[2] = { TEXT("foot_L"), TEXT("foot_R") };
		const float FloorZ = ToMesh.GetLocation().Z;
		FCollisionQueryParams Params(SCENE_QUERY_STAT(SOFootIK), false, Character);
		for (int32 i = 0; i < 2; ++i)
		{
			if (Mesh->GetBoneIndex(Feet[i]) == INDEX_NONE)
			{
				continue;
			}
			const FVector Ankle = Mesh->GetBoneLocation(Feet[i]);
			const FVector Start(Ankle.X, Ankle.Y, FloorZ + FootReach + 10.0f);
			const FVector End(Ankle.X, Ankle.Y, FloorZ - FootReach - 10.0f);
			FHitResult Hit;
			if (GetWorld()->LineTraceSingleByChannel(Hit, Start, End, ECC_Visibility, Params) && Hit.ImpactNormal.Z > 0.6f)
			{
				Want[i] = FMath::Clamp(static_cast<float>(Hit.ImpactPoint.Z - FloorZ), -FootReach, FootReach);
			}
		}
	}
	for (int32 i = 0; i < 2; ++i)
	{
		FootOffset[i] = FMath::FInterpTo(FootOffset[i], FootIKAlpha > 0.01f ? Want[i] : 0.0f, Dt, 14.0f);
	}
	PelvisFeet = FMath::FInterpTo(PelvisFeet, FMath::Max(0.0f, -FMath::Min(FootOffset[0], FootOffset[1])), Dt, 14.0f);
	PelvisDrop = PelvisFeet * FootIKAlpha + Compress;
}

FAnimInstanceProxy* USOLocomotionAnimInstance::CreateAnimInstanceProxy()
{
	return new FSOLocomotionProxy(this);
}

void USOLocomotionAnimInstance::DestroyAnimInstanceProxy(FAnimInstanceProxy* InProxy)
{
	delete static_cast<FSOLocomotionProxy*>(InProxy);
}

void FSOLocomotionProxy::PreUpdate(UAnimInstance* InAnimInstance, float DeltaSeconds)
{
	FAnimInstanceProxy::PreUpdate(InAnimInstance, DeltaSeconds);
	const USOLocomotionAnimInstance* Instance = CastChecked<USOLocomotionAnimInstance>(InAnimInstance);
	const UAnimSequenceBase* ClipList[Count] = { Instance->Clips.Idle, Instance->Clips.Walk, Instance->Clips.Run, Instance->Clips.Jump,
		Instance->Clips.Death, Instance->ActiveAttack ? Instance->ActiveAttack.Get() : Instance->Clips.Attack.Get(), Instance->Clips.Slide, Instance->FidgetClip };
	for (int32 i = 0; i < Count; ++i)
	{
		FSOLocomotionLayer& Layer = Layers[i];
		Layer.Clip = ClipList[i];
		Layer.Weight = Instance->Weights[i];
		Layer.bLoop = i != Death && i != Attack && i != Jump && i != Fidget;
		const float Length = Layer.Clip ? Layer.Clip->GetPlayLength() : 0.0f;
		const float T = Instance->Times[i];
		// positive modulo: the walk / run cycles run backward when backpedalling
		Layer.Time = Length <= 0.0f ? 0.0f : (Layer.bLoop ? T - FMath::FloorToFloat(T / Length) * Length : FMath::Min(T, Length - 1e-3f));
	}
	bHold = Instance->bHold;
	bOneHand = Instance->bOneHand;
	bArmsOnly = Instance->bArmsOnly;
	bCollapseBody = Instance->bCollapseBody;
	AimPitch = Instance->AimPitch;
	Blade = Instance->Blade;
	Lean = Instance->Lean;
	HeadCant = Instance->HeadCant;
	RightTarget = Instance->RightTarget;
	LeftTarget = Instance->LeftTarget;
	RightFingers = Instance->RightFingers;
	LeftFingers = Instance->LeftFingers;
	EyeCS = Instance->EyeCS;
	bBodyMotion = Instance->bBodyMotion;
	WarpYaw = Instance->WarpYaw;
	LeanRoll = Instance->LeanRoll;
	LeanPitch = Instance->LeanPitch;
	PelvisDrop = Instance->PelvisDrop;
	FootOffset[0] = Instance->FootOffset[0];
	FootOffset[1] = Instance->FootOffset[1];
	FootIKAlpha = Instance->FootIKAlpha;
}

bool FSOLocomotionProxy::Evaluate(FPoseContext& Output)
{
	int32 Active[Count];
	float ActiveWeights[Count];
	int32 NumActive = 0;
	float Total = 0.0f;
	for (int32 i = 0; i < Count; ++i)
	{
		if (Layers[i].Clip && Layers[i].Weight > 0.01f)
		{
			Active[NumActive] = i;
			ActiveWeights[NumActive] = Layers[i].Weight;
			Total += Layers[i].Weight;
			++NumActive;
		}
	}
	if (NumActive == 0)
	{
		Output.ResetToRefPose();
		return true;
	}

	if (NumActive == 1)
	{
		const FSOLocomotionLayer& Layer = Layers[Active[0]];
		FAnimationPoseData PoseData(Output);
		Layer.Clip->GetAnimationPose(PoseData, FAnimExtractContext(static_cast<double>(Layer.Time), false, {}, Layer.bLoop));
		ApplyBody(Output);
		ApplyHold(Output);
		return true;
	}

	TArray<FCompactPose> Poses;
	TArray<FBlendedCurve> Curves;
	TArray<UE::Anim::FStackAttributeContainer> Attributes;
	TArray<float> Weights;
	Poses.SetNum(NumActive);
	Curves.SetNum(NumActive);
	Attributes.SetNum(NumActive);
	Weights.SetNum(NumActive);
	for (int32 n = 0; n < NumActive; ++n)
	{
		const FSOLocomotionLayer& Layer = Layers[Active[n]];
		Poses[n].SetBoneContainer(&Output.Pose.GetBoneContainer());
		Curves[n].InitFrom(Output.Curve);
		FAnimationPoseData PoseData(Poses[n], Curves[n], Attributes[n]);
		Layer.Clip->GetAnimationPose(PoseData, FAnimExtractContext(static_cast<double>(Layer.Time), false, {}, Layer.bLoop));
		Weights[n] = ActiveWeights[n] / Total;
	}
	FAnimationPoseData OutData(Output);
	FAnimationRuntime::BlendPosesTogether(Poses, Curves, Attributes, Weights, OutData);
	ApplyBody(Output);
	ApplyHold(Output);
	return true;
}

void FSOLocomotionProxy::ApplyBody(FPoseContext& Output) const
{
	if (!bBodyMotion)
	{
		return;
	}
	FCompactPose& Pose = Output.Pose;
	const FBoneContainer& Bones = Pose.GetBoneContainer();
	auto Find = [&Bones](const TCHAR* Name) -> int32
	{
		const int32 MeshIndex = Bones.GetPoseBoneIndexForBoneName(FName(Name));
		return MeshIndex == INDEX_NONE ? INDEX_NONE : Bones.MakeCompactPoseIndex(FMeshPoseBoneIndex(MeshIndex)).GetInt();
	};
	const int32 Hips = Find(TEXT("hips")), Spine = Find(TEXT("spine")), Chest = Find(TEXT("chest"));
	const int32 Leg[2][3] = { { Find(TEXT("thigh_L")), Find(TEXT("shin_L")), Find(TEXT("foot_L")) },
		{ Find(TEXT("thigh_R")), Find(TEXT("shin_R")), Find(TEXT("foot_R")) } };
	if (Hips == INDEX_NONE)
	{
		return;
	}

	const int32 Num = Pose.GetNumBones();
	TArray<int32, TInlineAllocator<64>> Parent;
	TArray<FTransform, TInlineAllocator<64>> Local, CS;
	Parent.SetNum(Num);
	Local.SetNum(Num);
	CS.SetNum(Num);
	for (FCompactPoseBoneIndex Index : Pose.ForEachBoneIndex())
	{
		const int32 I = Index.GetInt();
		const FCompactPoseBoneIndex P = Bones.GetParentBoneIndex(Index);
		Parent[I] = P.IsValid() ? P.GetInt() : INDEX_NONE;
		Local[I] = Pose[Index];
		CS[I] = Parent[I] == INDEX_NONE ? Local[I] : Local[I] * CS[Parent[I]];
	}
	auto Refresh = [&]()
	{
		for (int32 I = 0; I < Num; ++I)
		{
			CS[I] = Parent[I] == INDEX_NONE ? Local[I] : Local[I] * CS[Parent[I]];
		}
	};
	auto SetCS = [&](int32 I, const FTransform& T)
	{
		Local[I] = Parent[I] == INDEX_NONE ? T : T.GetRelativeTransform(CS[Parent[I]]);
		Refresh();
	};
	auto Turn = [&](int32 I, const FQuat& Q)
	{
		SetCS(I, FTransform(Q * CS[I].GetRotation(), CS[I].GetLocation(), CS[I].GetScale3D()));
	};

	// Component space: +Y forward, +Z up, +X the character's left.
	const FVector Side(1.0f, 0.0f, 0.0f), Fwd(0.0f, 1.0f, 0.0f), Up(0.0f, 0.0f, 1.0f);

	// 1. Orientation warping: the hips (and legs) turn toward the movement, spine and chest turn back so the
	//    shoulders keep facing the aim.
	if (FMath::Abs(WarpYaw) > 0.1f)
	{
		const float W = FMath::DegreesToRadians(WarpYaw);
		Turn(Hips, FQuat(Up, W));
		if (Spine != INDEX_NONE)
		{
			Turn(Spine, FQuat(Up, -W * 0.55f));
		}
		if (Chest != INDEX_NONE)
		{
			Turn(Chest, FQuat(Up, -W * 0.45f));
		}
	}

	// 2. Leans: the upper body rolls into sideways acceleration and pitches with forward acceleration / landings.
	const float Roll = FMath::DegreesToRadians(LeanRoll), PitchL = FMath::DegreesToRadians(LeanPitch);
	if (FMath::Abs(Roll) + FMath::Abs(PitchL) > 1e-3f)
	{
		Turn(Hips, FQuat(Fwd, Roll * 0.25f) * FQuat(Side, PitchL * 0.2f));
		if (Spine != INDEX_NONE)
		{
			Turn(Spine, FQuat(Fwd, Roll * 0.45f) * FQuat(Side, PitchL * 0.45f));
		}
		if (Chest != INDEX_NONE)
		{
			Turn(Chest, FQuat(Fwd, Roll * 0.3f) * FQuat(Side, PitchL * 0.35f));
		}
	}

	// Where the feet should be: as animated (after the warp), raised or lowered onto the ground under them.
	FTransform FootWanted[2];
	bool bLeg[2] = { false, false };
	for (int32 i = 0; i < 2; ++i)
	{
		bLeg[i] = Leg[i][0] != INDEX_NONE && Leg[i][1] != INDEX_NONE && Leg[i][2] != INDEX_NONE;
		if (bLeg[i])
		{
			FootWanted[i] = CS[Leg[i][2]];
			FootWanted[i].AddToTranslation(Up * FootOffset[i] * FootIKAlpha);
		}
	}

	// 3. The hips sink (landing, or so the lower foot reaches a step below).
	if (PelvisDrop > 0.01f)
	{
		FTransform H = CS[Hips];
		H.AddToTranslation(-Up * PelvisDrop);
		SetCS(Hips, H);
	}

	// 4. Two-bone leg IK onto the wanted feet; the knee keeps the side the animation bent it to.
	if (PelvisDrop > 0.01f || FootIKAlpha > 0.01f)
	{
		for (int32 i = 0; i < 2; ++i)
		{
			if (!bLeg[i])
			{
				continue;
			}
			const int32 Upper = Leg[i][0], Lower = Leg[i][1], Foot = Leg[i][2];
			const FVector S = CS[Upper].GetLocation();
			const FVector Knee0 = CS[Lower].GetLocation();
			const float L1 = FVector::Dist(S, Knee0);
			const float L2 = FVector::Dist(Knee0, CS[Foot].GetLocation());
			const FVector ToTarget = FootWanted[i].GetLocation() - S;
			const FVector Dir = ToTarget.GetSafeNormal(1e-4f, -Up);
			const float D = FMath::Clamp(static_cast<float>(ToTarget.Size()), FMath::Abs(L1 - L2) + 0.5f, (L1 + L2) * 0.999f);
			const float Along = (L1 * L1 - L2 * L2 + D * D) / (2.0f * D);
			const float Height = FMath::Sqrt(FMath::Max(L1 * L1 - Along * Along, 0.0f));
			FVector Bend = (Knee0 - S) - Dir * FVector::DotProduct(Knee0 - S, Dir);
			Bend = Bend.GetSafeNormal(1e-4f, Fwd);
			const FVector Knee = S + Dir * Along + Bend * Height;
			const FVector Ankle = S + Dir * D;
			Turn(Upper, FQuat::FindBetweenNormals((CS[Lower].GetLocation() - S).GetSafeNormal(), (Knee - S).GetSafeNormal()));
			const FVector E = CS[Lower].GetLocation();
			Turn(Lower, FQuat::FindBetweenNormals((CS[Foot].GetLocation() - E).GetSafeNormal(), (Ankle - E).GetSafeNormal()));
			SetCS(Foot, FTransform(FootWanted[i].GetRotation(), CS[Foot].GetLocation(), CS[Foot].GetScale3D()));
		}
	}

	for (FCompactPoseBoneIndex Index : Pose.ForEachBoneIndex())
	{
		Pose[Index] = Local[Index.GetInt()];
	}
}

void FSOLocomotionProxy::ApplyHold(FPoseContext& Output) const
{
	if (!bHold)
	{
		return;
	}
	FCompactPose& Pose = Output.Pose;
	const FBoneContainer& Bones = Pose.GetBoneContainer();
	auto Find = [&Bones](const TCHAR* Name) -> int32
	{
		const int32 MeshIndex = Bones.GetPoseBoneIndexForBoneName(FName(Name));
		return MeshIndex == INDEX_NONE ? INDEX_NONE : Bones.MakeCompactPoseIndex(FMeshPoseBoneIndex(MeshIndex)).GetInt();
	};
	const int32 Spine = Find(TEXT("spine")), Chest = Find(TEXT("chest")), Neck = Find(TEXT("neck")), HeadBone = Find(TEXT("head"));
	const int32 Arm[2][3] = { { Find(TEXT("upperarm_R")), Find(TEXT("forearm_R")), Find(TEXT("hand_R")) },
		{ Find(TEXT("upperarm_L")), Find(TEXT("forearm_L")), Find(TEXT("hand_L")) } };
	const int32 Clavicle[2] = { Find(TEXT("clavicle_R")), Find(TEXT("clavicle_L")) }; // (older rigs have none)
	for (const int32 (&Chain)[3] : Arm)
	{
		if (Chain[0] == INDEX_NONE || Chain[1] == INDEX_NONE || Chain[2] == INDEX_NONE)
		{
			return;
		}
	}

	// Local and component-space transforms (compact poses list parents before children).
	const int32 Num = Pose.GetNumBones();
	TArray<int32, TInlineAllocator<64>> Parent;
	TArray<FTransform, TInlineAllocator<64>> Local, CS, RefCS;
	Parent.SetNum(Num);
	Local.SetNum(Num);
	CS.SetNum(Num);
	RefCS.SetNum(Num);
	for (FCompactPoseBoneIndex Index : Pose.ForEachBoneIndex())
	{
		const int32 I = Index.GetInt();
		const FCompactPoseBoneIndex P = Bones.GetParentBoneIndex(Index);
		Parent[I] = P.IsValid() ? P.GetInt() : INDEX_NONE;
		Local[I] = Pose[Index];
		CS[I] = Parent[I] == INDEX_NONE ? Local[I] : Local[I] * CS[Parent[I]];
		const FTransform Ref = Pose.GetRefPose(Index);
		RefCS[I] = Parent[I] == INDEX_NONE ? Ref : Ref * RefCS[Parent[I]];
	}
	auto Refresh = [&]()
	{
		for (int32 I = 0; I < Num; ++I)
		{
			CS[I] = Parent[I] == INDEX_NONE ? Local[I] : Local[I] * CS[Parent[I]];
		}
	};
	auto SetCS = [&](int32 I, const FTransform& T)
	{
		Local[I] = Parent[I] == INDEX_NONE ? T : T.GetRelativeTransform(CS[Parent[I]]);
		Refresh();
	};
	auto Turn = [&](int32 I, const FQuat& Q) // about the bone's own pivot, in component space
	{
		SetCS(I, FTransform(Q * CS[I].GetRotation(), CS[I].GetLocation(), CS[I].GetScale3D()));
	};

	// Component space of the shared rig: +Y forward, +Z up, the character's left is +X.
	const FVector Side(1.0f, 0.0f, 0.0f), Up(0.0f, 0.0f, 1.0f);
	const float Pitch = FMath::DegreesToRadians(FMath::Clamp(AimPitch, -80.0f, 80.0f));
	const float BladeRad = FMath::DegreesToRadians(Blade), LeanRad = FMath::DegreesToRadians(Lean);

	// 1. Stance: the torso follows the aim pitch (70 %), leans into the gun and turns the off shoulder forward.
	//    First person: the shoulders turn with the whole view about the eye instead, so looking down never shows the
	//    shoulders from above and looking up never leaves the gun out of the arms' reach.
	const float StancePitch = bArmsOnly ? 0.0f : Pitch;
	if (Spine != INDEX_NONE)
	{
		Turn(Spine, FQuat(Up, BladeRad * 0.4f) * FQuat(Side, StancePitch * 0.3f - LeanRad * 0.5f));
	}
	if (Chest != INDEX_NONE)
	{
		Turn(Chest, FQuat(Up, BladeRad * 0.6f) * FQuat(Side, StancePitch * 0.4f - LeanRad * 0.5f));
		if (bArmsOnly)
		{
			const FQuat View(Side, Pitch);
			const FTransform C = CS[Chest];
			SetCS(Chest, FTransform(View * C.GetRotation(), EyeCS + View.RotateVector(C.GetLocation() - EyeCS), C.GetScale3D()));
		}
	}
	// 2. The head looks along the aim regardless of the stance or the clip: neck and head take their rest-pose
	//    facing (straight ahead) and share the aim pitch.
	if (Neck != INDEX_NONE && !bArmsOnly)
	{
		SetCS(Neck, FTransform(FQuat(Side, Pitch * 0.4f) * RefCS[Neck].GetRotation(), CS[Neck].GetLocation(), CS[Neck].GetScale3D()));
		if (HeadBone != INDEX_NONE)
		{
			// aiming a long gun: the head cants toward the right shoulder and dips onto the stock (cheek weld)
			const float Cant = FMath::DegreesToRadians(HeadCant);
			const FQuat Weld = FQuat(FVector(0.0f, 1.0f, 0.0f), -Cant) * FQuat(Side, -Cant * 0.7f);
			SetCS(HeadBone, FTransform(Weld * FQuat(Side, Pitch) * RefCS[HeadBone].GetRotation(), CS[HeadBone].GetLocation(), CS[HeadBone].GetScale3D()));
		}
	}

	// 3. Arms: two-bone IK to the wrist targets, elbows down and out, forearm shares the wrist twist, hand on the grip.
	for (int32 SideIndex = 0; SideIndex < (bOneHand ? 1 : 2); ++SideIndex)
	{
		const bool bLeft = SideIndex == 1;
		const int32 Upper = Arm[SideIndex][0], Lower = Arm[SideIndex][1], Hand = Arm[SideIndex][2];
		const FTransform& Target = bLeft ? LeftTarget : RightTarget;

		// Shoulder girdle: the clavicle carries part of a forward / across reach (protraction) and of a raise above
		// the horizontal (elevation), like the shoulder blade does, so the shoulder keeps its volume instead of the
		// upper arm twisting it flat.
		if (const int32 Clav = Clavicle[SideIndex]; Clav != INDEX_NONE)
		{
			const FVector Joint = CS[Upper].GetLocation();
			const FVector Reach = (Target.GetLocation() - Joint).GetSafeNormal();
			const float Out = bLeft ? Reach.X : -Reach.X;                 // + = out to its own side, - = across the body
			const float Forward = FMath::Max(0.0f, (float)Reach.Y);
			const float Protract = FMath::Clamp(Forward * 0.22f + FMath::Max(0.0f, -Out) * 0.30f, 0.0f, 0.42f);   // rad (~24 deg max)
			const float Elevate = FMath::Clamp((float)Reach.Z * 0.30f + 0.04f * Forward, 0.0f, 0.30f);          // rad (~17 deg max)
			const float Sign = bLeft ? 1.0f : -1.0f;
			Turn(Clav, FQuat(Up, Sign * Protract) * FQuat(FVector(0.0f, 1.0f, 0.0f), -Sign * Elevate));
		}

		// Hand bone vs its anatomical basis, from the rest pose (relaxed hands: thumb forward, palm to the thigh).
		const FVector RestAlong = (RefCS[Hand].GetLocation() - RefCS[Lower].GetLocation()).GetSafeNormal();
		const FQuat RestBasis = FSOHandGrip::MakeBasis(RestAlong, FVector(0.0f, 1.0f, 0.0f), bLeft);
		const FQuat HandOffset = RestBasis.Inverse() * RefCS[Hand].GetRotation();

		const FVector S = CS[Upper].GetLocation();
		const float L1 = FVector::Dist(S, CS[Lower].GetLocation());
		const float L2 = FVector::Dist(CS[Lower].GetLocation(), CS[Hand].GetLocation());
		const FVector ToTarget = Target.GetLocation() - S;
		const FVector Dir = ToTarget.GetSafeNormal(1e-4f, FVector(0.0f, 1.0f, 0.0f));
		const float D = FMath::Clamp(ToTarget.Size(), FMath::Abs(L1 - L2) + 0.5f, (L1 + L2) * 0.999f);
		const float Along = (L1 * L1 - L2 * L2 + D * D) / (2.0f * D);
		const float Height = FMath::Sqrt(FMath::Max(L1 * L1 - Along * Along, 0.0f));
		const FVector Pole(bLeft ? 0.45f : -0.45f, -0.25f, -1.0f); // out, back, down
		FVector Bend = Pole - Dir * FVector::DotProduct(Pole, Dir);
		Bend = Bend.GetSafeNormal(1e-4f, FVector(0.0f, 0.0f, -1.0f));
		const FVector Elbow = S + Dir * Along + Bend * Height;
		const FVector Wrist = S + Dir * D;

		Turn(Upper, FQuat::FindBetweenNormals((CS[Lower].GetLocation() - S).GetSafeNormal(), (Elbow - S).GetSafeNormal()));
		const FVector E = CS[Lower].GetLocation();
		Turn(Lower, FQuat::FindBetweenNormals((CS[Hand].GetLocation() - E).GetSafeNormal(), (Wrist - E).GetSafeNormal()));

		const FQuat Wanted = Target.GetRotation() * HandOffset;
		const FVector ForearmAxis = (CS[Hand].GetLocation() - CS[Lower].GetLocation()).GetSafeNormal();
		FQuat Swing, Twist;
		(Wanted * CS[Hand].GetRotation().Inverse()).ToSwingTwist(ForearmAxis, Swing, Twist);
		Turn(Lower, FQuat::Slerp(FQuat::Identity, Twist, 0.6f));
		SetCS(Hand, FTransform(Wanted, CS[Hand].GetLocation(), CS[Hand].GetScale3D()));

		// Fingers close round what the hand holds: each finger turns at its three joints about the axis that brings
		// it towards the palm (bodies without finger bones skip this).
		static const TCHAR* FingerNames[5] = { TEXT("index"), TEXT("middle"), TEXT("ring"), TEXT("pinky"), TEXT("thumb") };
		const FSOFingerPose& Fingers = bLeft ? LeftFingers : RightFingers;
		const FVector Palm = FSOHandGrip::PalmNormal(Target.GetRotation(), bLeft);
		for (int32 f = 0; f < 5; ++f)
		{
			int32 Chain[3];
			for (int32 k = 0; k < 3; ++k)
			{
				Chain[k] = Find(*FString::Printf(TEXT("%s_0%d_%s"), FingerNames[f], k + 1, bLeft ? TEXT("L") : TEXT("R")));
			}
			if (Chain[0] == INDEX_NONE || Chain[1] == INDEX_NONE || Chain[2] == INDEX_NONE)
			{
				continue;
			}
			FTransform ParentCS = CS[Hand];
			FVector Axis = FVector::ZeroVector;
			for (int32 k = 0; k < 3; ++k)
			{
				const int32 I = Chain[k];
				const FTransform Rigid = Local[I] * ParentCS;
				if (k == 0)
				{
					const FVector FingerDir = ((Local[Chain[1]] * Rigid).GetLocation() - Rigid.GetLocation()).GetSafeNormal();
					Axis = FVector::CrossProduct(FingerDir, Palm).GetSafeNormal();
				}
				const FQuat Close(Axis, FMath::DegreesToRadians(Fingers.Curl[f][k]));
				CS[I] = FTransform(Close * Rigid.GetRotation(), Rigid.GetLocation(), Rigid.GetScale3D());
				Local[I] = CS[I].GetRelativeTransform(ParentCS);
				ParentCS = CS[I];
			}
		}
	}

	// 4. First-person copy of the whole body: only the arms remain (everything else shrinks into its bone).
	if (bCollapseBody)
	{
		TArray<FTransform, TInlineAllocator<64>> Final = CS;
		for (int32 I = 0; I < Num; ++I)
		{
			bool bArm = false;
			for (const int32 (&Chain)[3] : Arm)
			{
				bArm |= I == Chain[0] || I == Chain[1] || I == Chain[2];
				for (int32 P = Parent[I]; P != INDEX_NONE && !bArm; P = Parent[P])
				{
					bArm = P == Chain[2]; // fingers under the hand
				}
			}
			if (!bArm)
			{
				Final[I].SetScale3D(FVector(0.001f));
			}
		}
		for (int32 I = 0; I < Num; ++I)
		{
			Local[I] = Parent[I] == INDEX_NONE ? Final[I] : Final[I].GetRelativeTransform(Final[Parent[I]]);
		}
	}

	for (FCompactPoseBoneIndex Index : Pose.ForEachBoneIndex())
	{
		Pose[Index] = Local[Index.GetInt()];
	}
}
