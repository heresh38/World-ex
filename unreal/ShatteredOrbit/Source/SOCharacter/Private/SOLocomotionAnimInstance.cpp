#include "SOLocomotionAnimInstance.h"

#include "Animation/AnimSequenceBase.h"
#include "Animation/AnimationPoseData.h"
#include "AnimationRuntime.h"
#include "GameFramework/Character.h"
#include "SOCharacterMovementComponent.h"
#include "SOCombatCharacter.h"

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
	return true;
}
