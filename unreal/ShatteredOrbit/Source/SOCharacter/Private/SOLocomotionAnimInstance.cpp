#include "SOLocomotionAnimInstance.h"

#include "Animation/AnimSequenceBase.h"
#include "Animation/AnimationPoseData.h"
#include "AnimationRuntime.h"
#include "GameFramework/Character.h"
#include "SOCharacterMovementComponent.h"
#include "SOCharacter.h"
#include "SOCombatCharacter.h"
#include "SOGunRigComponent.h"
#include "SOViewmodelComponent.h"
#include "SOWeapon.h"

namespace
{
	enum ELayer { Idle = 0, Walk, Run, Jump, Death, Attack, Slide, Count };
}

void USOLocomotionAnimInstance::PlayAttack(float PlayRate)
{
	if (Clips.Attack)
	{
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
	const ASOWeapon* Held = Player ? Player->GetWeapon() : nullptr;
	const USOGunRigComponent* Rig = Held ? (bArmsOnly ? Held->GetFirstPersonRig() : Held->GetThirdPersonRig()) : nullptr;
	FTransform Right, Left;
	if (!bDead && Mesh && Rig && Rig->GetAttachParent() && Rig->GetHandTargets(Right, Left))
	{
		const FTransform ToMesh = Mesh->GetComponentTransform();
		RightTarget = Right.GetRelativeTransform(ToMesh);
		LeftTarget = Left.GetRelativeTransform(ToMesh);
		const float Ads = Player->GetViewmodel() ? Player->GetViewmodel()->GetAds() : 0.0f;
		AimPitch = FRotator::NormalizeAxis(Player->GetAimRotation().Pitch);
		// First person keeps a gentler stance so the off shoulder stays out of the corner of the view.
		const float Stance = bArmsOnly ? 0.5f : 1.0f;
		Blade = FMath::Lerp(12.0f, 24.0f, Ads) * Stance;
		Lean = FMath::Lerp(4.0f, 9.0f, Ads) * Stance;
		bHold = true;
	}

	// Target weights.
	float Target[Count] = { 0, 0, 0, 0, 0, 0, 0 };
	const bool bAttacking = AttackTime >= 0.0f && Clips.Attack;
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
	else if (bInAir && Clips.Jump)
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
	Times[Walk] += DeltaSeconds * WalkRate;
	Times[Run] += DeltaSeconds * RunRate;
	Times[Jump] = bInAir ? Times[Jump] + DeltaSeconds : 0.0f;
	Times[Death] = bDead ? Times[Death] + DeltaSeconds : 0.0f;
	Times[Slide] = bSliding ? Times[Slide] + DeltaSeconds : 0.0f;
	if (bAttacking)
	{
		AttackTime += DeltaSeconds * AttackRate;
		Times[Attack] = AttackTime;
		if (AttackTime >= Clips.Attack->GetPlayLength())
		{
			AttackTime = -1.0f;
		}
	}
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
		Instance->Clips.Death, Instance->Clips.Attack, Instance->Clips.Slide };
	for (int32 i = 0; i < Count; ++i)
	{
		FSOLocomotionLayer& Layer = Layers[i];
		Layer.Clip = ClipList[i];
		Layer.Weight = Instance->Weights[i];
		Layer.bLoop = i != Death && i != Attack && i != Jump;
		const float Length = Layer.Clip ? Layer.Clip->GetPlayLength() : 0.0f;
		const float T = Instance->Times[i];
		Layer.Time = Length <= 0.0f ? 0.0f : (Layer.bLoop ? FMath::Fmod(T, Length) : FMath::Min(T, Length - 1e-3f));
	}
	bHold = Instance->bHold;
	bArmsOnly = Instance->bArmsOnly;
	bCollapseBody = Instance->bCollapseBody;
	AimPitch = Instance->AimPitch;
	Blade = Instance->Blade;
	Lean = Instance->Lean;
	RightTarget = Instance->RightTarget;
	LeftTarget = Instance->LeftTarget;
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
	ApplyHold(Output);
	return true;
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
	const int32 Spine = Find(TEXT("spine")), Chest = Find(TEXT("chest")), Neck = Find(TEXT("neck"));
	const int32 Arm[2][3] = { { Find(TEXT("upperarm_R")), Find(TEXT("forearm_R")), Find(TEXT("hand_R")) },
		{ Find(TEXT("upperarm_L")), Find(TEXT("forearm_L")), Find(TEXT("hand_L")) } };
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
	const FQuat NeckBefore = Neck != INDEX_NONE ? CS[Neck].GetRotation() : FQuat::Identity;

	// 1. Stance: the torso follows the aim pitch (70 %), leans into the gun and turns the off shoulder forward.
	if (Spine != INDEX_NONE)
	{
		Turn(Spine, FQuat(Up, BladeRad * 0.4f) * FQuat(Side, Pitch * 0.3f - LeanRad * 0.5f));
	}
	if (Chest != INDEX_NONE)
	{
		Turn(Chest, FQuat(Up, BladeRad * 0.6f) * FQuat(Side, Pitch * 0.4f - LeanRad * 0.5f));
	}
	// 2. The head looks along the aim regardless of the stance.
	if (Neck != INDEX_NONE && !bArmsOnly)
	{
		SetCS(Neck, FTransform(FQuat(Side, Pitch) * NeckBefore, CS[Neck].GetLocation(), CS[Neck].GetScale3D()));
	}

	// 3. Arms: two-bone IK to the wrist targets, elbows down and out, forearm shares the wrist twist, hand on the grip.
	for (int32 SideIndex = 0; SideIndex < 2; ++SideIndex)
	{
		const bool bLeft = SideIndex == 1;
		const int32 Upper = Arm[SideIndex][0], Lower = Arm[SideIndex][1], Hand = Arm[SideIndex][2];
		const FTransform& Target = bLeft ? LeftTarget : RightTarget;

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
