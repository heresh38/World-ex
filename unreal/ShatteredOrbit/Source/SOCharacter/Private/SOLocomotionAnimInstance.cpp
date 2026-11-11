#include "SOLocomotionAnimInstance.h"

#include "Animation/AnimSequenceBase.h"
#include "Animation/AnimationPoseData.h"
#include "AnimationRuntime.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "ReferenceSkeleton.h"
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
	enum ELayer { Idle = 0, Walk, Run, Jump, Death, Attack, Slide, Fidget, Stroll, Land, Vault, Mantle, Climb, Crouch, CrouchWalk, Stop, Count };
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
		const bool bWasFalling = bInAir;
		bInAir = Move && Move->IsFalling();
		const USOCharacterMovementComponent* Lander = Cast<USOCharacterMovementComponent>(Move);
		bLanded = bWasFalling && !bInAir && Lander && !Lander->IsMantling();
		LandImpact = Lander ? Lander->GetLastLandSpeed() : 0.0f;
		const USOCharacterMovementComponent* SOMove = Cast<USOCharacterMovementComponent>(Move);
		bSliding = SOMove && SOMove->IsSliding();
		bMantling = SOMove && SOMove->IsMantling();
		TraversalAlpha = SOMove ? SOMove->GetMantleAlpha() : 0.0f;
		TraversalKind = !bMantling ? 0 : (SOMove->IsVaulting() ? 1 : 2);
		TraversalClimb = bMantling && SOMove->IsClambering();
		// The air pose follows the motion, not the clock: legs long driving off the ground, tucked at the top,
		// reaching for the ground on the way down; over an obstacle the knees come up as the body passes it.
		float WantTuck = 0.0f;
		if (bMantling)
		{
			WantTuck = (TraversalKind == 1 ? 0.35f : 0.2f) + (TraversalKind == 1 ? 0.65f : 0.6f) * FMath::Sin(TraversalAlpha * PI);
		}
		else if (bInAir)
		{
			const float Vz = static_cast<float>(Character->GetVelocity().Z);
			WantTuck = Vz > 0.0f ? FMath::Lerp(1.0f, 0.3f, FMath::Clamp(Vz / 600.0f, 0.0f, 1.0f)) : FMath::Lerp(1.0f, 0.25f, FMath::Clamp(-Vz / 950.0f, 0.0f, 1.0f));
		}
		AirTuck = FMath::FInterpTo(AirTuck, WantTuck, FMath::Max(DeltaSeconds, 1e-4f), 9.0f);
		// The jump clip is three poses in a row (driving off the ground, tucked at the top, reaching for the ground):
		// rising reads the first part by how much rise is left, falling the second by how fast.
		if (bInAir && !bMantling && Clips.Jump)
		{
			const float Vz = static_cast<float>(Character->GetVelocity().Z);
			const float Length = Clips.Jump->GetPlayLength();
			const float Tuck = FMath::Min(JumpTuckTime, Length);
			const float Want = Vz > 0.0f ? Tuck * (1.0f - FMath::Clamp(Vz / 600.0f, 0.0f, 1.0f)) : Tuck + (Length - Tuck) * FMath::Clamp(-Vz / 900.0f, 0.0f, 1.0f);
			JumpPose = FMath::FInterpTo(JumpPose, Want, FMath::Max(DeltaSeconds, 1e-4f), 14.0f);
			AirTuck = JumpPose <= Tuck ? JumpPose / FMath::Max(Tuck, 1e-3f) : 1.0f - 0.75f * (JumpPose - Tuck) / FMath::Max(Length - Tuck, 1e-3f);
		}
		else if (!bMantling)
		{
			JumpPose = 0.0f;
		}
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
	if (Player && Player->IsWeaponStowed())
	{
		Rig = nullptr;                                           // (the gun is put away: the hands are free)
	}
	FTransform Right, Left;
	if (!bDead && Mesh && Rig && Rig->GetAttachParent() && Rig->GetHandTargets(Right, Left))
	{
		const FTransform ToMesh = Mesh->GetComponentTransform();
		RightTarget = Right.GetRelativeTransform(ToMesh);
		LeftTarget = Left.GetRelativeTransform(ToMesh);
		Rig->GetFingerPoses(RightFingers, LeftFingers);
		// the hands fitted to this gun (once per gun, when it is at rest in them)
		if ((FitRig.Get() != Rig || !bFitDone) && !Held->IsReloading())
		{
			FitGrip(Rig, Mesh, Holder->HoldsWithOneHand());
		}
		if (bFitDone && FitRig.Get() == Rig)
		{
			const FTransform& RigT = Rig->GetComponentTransform();
			RightFingers = FitFingers[0];
			RightTarget.AddToTranslation(ToMesh.InverseTransformVector(RigT.TransformVector(FitOffset[0])));
			if (!Held->IsReloading())
			{
				LeftFingers = FitFingers[1];
				LeftTarget.AddToTranslation(ToMesh.InverseTransformVector(RigT.TransformVector(FitOffset[1])));
			}
		}
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

	// A vault, a mantle or a climb: the hands go onto the edge and stay there while the body moves past them (reaching
	// up for it, pulling, then pushing down on it), coming on and off through HoldAlpha. A vault plants one hand.
	bLedge = false;
	HoldAlpha = 1.0f;
	const USOCharacterMovementComponent* Traverse = Character ? Cast<USOCharacterMovementComponent>(Character->GetCharacterMovement()) : nullptr;
	FVector Edge, EdgeNormal;
	if (!bHold && !bDead && Mesh && Traverse && Traverse->GetTraversalLedge(Edge, EdgeNormal))
	{
		const FTransform ToMesh = Mesh->GetComponentTransform();
		const FVector EdgeCS = ToMesh.InverseTransformPosition(Edge);
		const FVector Out = ToMesh.InverseTransformVectorNoScale(EdgeNormal).GetSafeNormal2D(1e-4f, FVector(0.0f, -1.0f, 0.0f)); // off the face, toward the body
		FVector Along = FVector::CrossProduct(FVector::UpVector, Out).GetSafeNormal();
		if (Along.X < 0.0f)
		{
			Along = -Along;                                          // toward the character's left (+X)
		}
		const bool bVault = TraversalKind == 1;
		const float Half = bVault ? 13.0f : 19.0f;                    // each hand's distance from the body's line
		for (int32 Side = 0; Side < 2; ++Side)
		{
			const bool bLeft = Side == 1;
			const FVector SideDir = bLeft ? Along : -Along;
			// the palm flat on the top a little in from the edge, fingers onto the ledge, thumbs toward each other
			const FVector Wrist = EdgeCS + SideDir * Half - Out * 6.0f + FVector(0.0f, 0.0f, 2.2f);
			(bLeft ? LeftTarget : RightTarget) = FTransform(FSOHandGrip::MakeBasis(-Out, -SideDir, bLeft), Wrist);
		}
		RightFingers = LeftFingers = FSOFingerPose::Wrap(0.45f);
		bOneHand = bVault;
		AimPitch = 0.0f;
		Blade = Lean = HeadCant = 0.0f;
		// On while the edge can be reached: reaching up for it from below (the arms go straight toward it), on it while
		// the body comes up and pushes, off once the shoulders are too far above it for the arms.
		float Reach = 1.0f;
		for (int32 Side = 0; Side < (bVault ? 1 : 2); ++Side)
		{
			const bool bLeft = Side == 1;
			const FName Upper = bLeft ? TEXT("upperarm_L") : TEXT("upperarm_R"), Lower = bLeft ? TEXT("forearm_L") : TEXT("forearm_R"), Hand = bLeft ? TEXT("hand_L") : TEXT("hand_R");
			if (Mesh->GetBoneIndex(Upper) == INDEX_NONE || Mesh->GetBoneIndex(Lower) == INDEX_NONE || Mesh->GetBoneIndex(Hand) == INDEX_NONE)
			{
				continue;
			}
			const FVector Shoulder = ToMesh.InverseTransformPosition(Mesh->GetBoneLocation(Upper));
			const float Arm = static_cast<float>(FVector::Dist(Mesh->GetBoneLocation(Upper), Mesh->GetBoneLocation(Lower)) + FVector::Dist(Mesh->GetBoneLocation(Lower), Mesh->GetBoneLocation(Hand)));
			const FVector To = (bLeft ? LeftTarget : RightTarget).GetLocation() - Shoulder;
			const float Far = To.Z > 0.0f ? FMath::Min(static_cast<float>(To.Size()), Arm) : static_cast<float>(To.Size());
			Reach = FMath::Min(Reach, 1.0f - FMath::SmoothStep(Arm * 1.02f, Arm * 1.28f, Far));
		}
		const float In = bVault ? 0.06f : 0.0f, Full = bVault ? 0.24f : 0.1f;
		HoldAlpha = FMath::FInterpTo(bLedgeWas ? HoldAlphaLast : 0.0f, FMath::SmoothStep(In, Full, TraversalAlpha) * Reach, FMath::Max(DeltaSeconds, 1e-4f), 18.0f);
		bLedge = HoldAlpha > 0.01f;
		bHold = bLedge;
	}
	bLedgeWas = bLedge;
	HoldAlphaLast = HoldAlpha;

	UpdateBodyMotion(Character, DeltaSeconds);

	// Target weights.
	float Target[Count] = {};
	const bool bAttacking = AttackTime >= 0.0f && ActiveAttack;
	// over or onto an obstacle: the clip made for it (read by progress); bodies without one hold the jump's tuck
	const UAnimSequenceBase* Over = !bMantling ? nullptr : (TraversalKind == 1 ? Clips.Vault.Get() : (TraversalClimb ? Clips.Climb.Get() : Clips.Mantle.Get()));
	// a landing: shown by how hard it was, less the faster the body is already moving on
	if (bLanded)
	{
		LandStrength = Clips.Land ? FMath::Clamp((LandImpact - 320.0f) / 620.0f, 0.0f, 1.0f) * FMath::Lerp(1.0f, 0.35f, FMath::Clamp(Speed / 500.0f, 0.0f, 1.0f)) : 0.0f;
		LandTime = 0.0f;
	}
	LandTime += DeltaSeconds;
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
	else if (Over)
	{
		Target[TraversalKind == 1 ? Vault : (TraversalClimb ? Climb : Mantle)] = 1.0f;
	}
	else if ((bInAir || bMantling) && Clips.Jump)
	{
		Target[Jump] = 1.0f;
	}
	else
	{
		const float Run01 = FMath::Clamp((Speed - Clips.WalkSpeed) / FMath::Max(Clips.RunSpeed - Clips.WalkSpeed, 1.0f), 0.0f, 1.0f);
		if (Clips.Stroll)
		{
			// standing -> the slow walk -> the run -> the sprint, each handing over to the next with the speed
			const float Slow = FMath::Max(Clips.StrollSpeed, 1.0f);
			const float Moving = FMath::Clamp(Speed / (Slow * 0.45f), 0.0f, 1.0f);
			const float Jog = FMath::Clamp((Speed - Slow) / FMath::Max(Clips.WalkSpeed - Slow, 1.0f), 0.0f, 1.0f);
			Target[Idle] = 1.0f - Moving;
			Target[Stroll] = Moving * (1.0f - Jog);
			Target[Walk] = Moving * Jog * (Clips.Run ? 1.0f - Run01 : 1.0f);
			Target[Run] = Clips.Run ? Moving * Jog * Run01 : 0.0f;
		}
		else
		{
			const float Walk01 = FMath::Clamp(Speed / FMath::Max(Clips.WalkSpeed * 0.5f, 1.0f), 0.0f, 1.0f);
			Target[Idle] = 1.0f - Walk01;
			Target[Walk] = Walk01 * (Clips.Run ? 1.0f - Run01 : 1.0f);
			Target[Run] = Clips.Run ? Walk01 * Run01 : 0.0f;
		}
		// Crouched: the body's own crouch clips take over from the standing set (still <-> the crouched walk with the
		// speed). They are authored down there, feet planted: nothing is bent at runtime.
		if (bCrouchPose && HasCrouchClips())
		{
			const float Go = FMath::Clamp(Speed / FMath::Max(Clips.CrouchSpeed * 0.4f, 1.0f), 0.0f, 1.0f);
			for (float& T : Target)
			{
				T = 0.0f;
			}
			Target[Crouch] = 1.0f - Go;
			Target[CrouchWalk] = Go;
		}
		// Braking out of a run to a standstill: the body's brake over the idle, by how fast it was going, gone the
		// moment it moves off again.
		RecentSpeed = FMath::Max(Speed, RecentSpeed - 520.0f * DeltaSeconds);
		const float StopLength = Clips.Stop ? Clips.Stop->GetPlayLength() : 0.0f;
		if (StopLength > 0.0f && !bCrouchPose && Speed < 90.0f && RecentSpeed > 280.0f && StopTime >= StopLength)
		{
			StopStrength = FMath::Clamp((RecentSpeed - 200.0f) / 420.0f, 0.4f, 1.0f);
			StopTime = 0.0f;
			RecentSpeed = Speed;
		}
		StopTime += DeltaSeconds;
		const float Braking = StopLength > 0.0f && StopTime < StopLength && Speed < 140.0f && !bCrouchPose
			? StopStrength * (1.0f - FMath::SmoothStep(StopLength * 0.4f, StopLength, StopTime)) : 0.0f;
		if (Braking > 0.0f)
		{
			for (float& T : Target)
			{
				T *= 1.0f - Braking;
			}
			Target[Stop] = Braking;
		}
		// the landing over whatever comes next, fading as its clip plays out
		const float LandLength = Clips.Land ? Clips.Land->GetPlayLength() : 0.0f;
		const float Landing = LandLength > 0.0f && LandTime < LandLength ? LandStrength * (1.0f - FMath::SmoothStep(LandLength * 0.45f, LandLength, LandTime)) : 0.0f;
		if (Landing > 0.0f)
		{
			for (float& T : Target)
			{
				T *= 1.0f - Landing;
			}
			Target[Land] = Landing;
		}
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
		// (linear progress, eased shape: a blend starts and ends gently instead of at full rate)
		Ramp[i] = FMath::FInterpConstantTo(Ramp[i], Target[i], 1.0f, Rate);
		Weights[i] = Ramp[i] * Ramp[i] * (3.0f - 2.0f * Ramp[i]);
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
	const float StrollLen = Clips.Stroll ? FMath::Max(Clips.Stroll->GetPlayLength(), 0.05f) : WalkLen;
	const float StrollRate = FMath::Clamp(Speed / FMath::Max(Clips.StrollSpeed, 1.0f), 0.45f, 1.7f);
	const float CrouchLen = Clips.CrouchWalk ? FMath::Max(Clips.CrouchWalk->GetPlayLength(), 0.05f) : WalkLen;
	const float CrouchRate = FMath::Clamp(Speed / FMath::Max(Clips.CrouchSpeed, 1.0f), 0.5f, 1.5f);
	const float WW = Weights[Walk], WR = Weights[Run], WS = Weights[Stroll], WC = Clips.CrouchWalk ? Weights[CrouchWalk] : 0.0f;
	const float PhaseRate = WW + WR + WS + WC > 1e-3f
		? (WW * WalkRate / WalkLen + WR * RunRate / RunLen + WS * StrollRate / StrollLen + WC * CrouchRate / CrouchLen) / (WW + WR + WS + WC)
		: (Clips.Stroll ? StrollRate / StrollLen : WalkRate / WalkLen);
	CyclePhase += DeltaSeconds * PhaseRate * Direction;
	CyclePhase -= FMath::FloorToFloat(CyclePhase);
	Times[Walk] = CyclePhase * WalkLen;
	Times[Run] = CyclePhase * RunLen;
	Times[Stroll] = CyclePhase * StrollLen;
	Times[CrouchWalk] = CyclePhase * CrouchLen;
	Times[Crouch] += DeltaSeconds;
	Times[Land] = LandTime;
	Times[Stop] = StopTime;
	// over and onto things: the pose for how far through the move the body is
	for (const int32 Layer : { static_cast<int32>(Vault), static_cast<int32>(Mantle), static_cast<int32>(Climb) })
	{
		const UAnimSequenceBase* Clip = Layer == Vault ? Clips.Vault.Get() : (Layer == Mantle ? Clips.Mantle.Get() : Clips.Climb.Get());
		if (Clip && bMantling)
		{
			Times[Layer] = TraversalAlpha * Clip->GetPlayLength();
		}
	}
	// (players: the air pose is picked by the motion; creatures play their jump clip through)
	Times[Jump] = Cast<ASOCharacter>(TryGetPawnOwner()) ? (bMantling ? JumpTuckTime * AirTuck : JumpPose) : (bInAir ? Times[Jump] + DeltaSeconds : 0.0f);
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

void USOLocomotionAnimInstance::FitGrip(const USOGunRigComponent* Rig, const USkeletalMeshComponent* Mesh, bool bOneHanded)
{
	FitRig = Rig;
	bFitDone = false;
	FitOffset[0] = FitOffset[1] = FVector::ZeroVector;
	Rig->GetFingerPoses(FitFingers[0], FitFingers[1]);
	const USkeletalMesh* Asset = Mesh ? Mesh->GetSkeletalMeshAsset() : nullptr;
	FTransform Target[2];
	if (!Asset || !Rig->IsBuilt() || !Rig->GetGunSpace() || !Rig->GetHandTargets(Target[0], Target[1]))
	{
		return;
	}
	const FReferenceSkeleton& Ref = Asset->GetRefSkeleton();
	const TArray<FTransform>& RefLocal = Ref.GetRefBonePose();
	auto RefCS = [&](int32 Bone)
	{
		FTransform T = FTransform::Identity;
		for (int32 I = Bone; I != INDEX_NONE; I = Ref.GetParentIndex(I))
		{
			T = T * RefLocal[I];
		}
		return T;
	};

	// The gun's meshes answer shape queries for the length of the fit (they collide with nothing otherwise).
	TArray<USceneComponent*> Children;
	Rig->GetGunSpace()->GetChildrenComponents(true, Children);
	TArray<UStaticMeshComponent*> Parts;
	for (USceneComponent* Child : Children)
	{
		UStaticMeshComponent* Part = Cast<UStaticMeshComponent>(Child);
		if (Part && Part->GetStaticMesh() && Part->IsVisible())
		{
			Part->SetCollisionResponseToAllChannels(ECR_Ignore);
			Part->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
			Parts.Add(Part);
		}
	}
	auto Touches = [&Parts](const FVector& A, const FVector& B, float Radius)
	{
		FHitResult Hit;
		for (UStaticMeshComponent* Part : Parts)
		{
			if (Part->SweepComponent(Hit, A, B, FQuat::Identity, FCollisionShape::MakeSphere(Radius), true))
			{
				return true;
			}
		}
		return false;
	};
	auto Surface = [&Parts](const FVector& A, const FVector& B, FVector& OutPoint)
	{
		bool bAny = false;
		float Best = 2.0f;
		FHitResult Hit;
		FCollisionQueryParams Params(SCENE_QUERY_STAT(SOFitGrip), true);
		for (UStaticMeshComponent* Part : Parts)
		{
			if (Part->LineTraceComponent(Hit, A, B, Params) && Hit.Time < Best)
			{
				Best = Hit.Time;
				OutPoint = Hit.ImpactPoint;
				bAny = true;
			}
		}
		return bAny;
	};

	static const TCHAR* FingerNames[5] = { TEXT("index"), TEXT("middle"), TEXT("ring"), TEXT("pinky"), TEXT("thumb") };
	static const float FingerRadius[5] = { 0.92f, 0.96f, 0.90f, 0.80f, 1.05f };
	static const float MaxCurl[5][3] = { { 88, 100, 70 }, { 90, 102, 72 }, { 92, 104, 72 }, { 94, 104, 72 }, { 46, 50, 55 } };
	const FTransform RigT = Rig->GetComponentTransform();
	int32 Fitted = 0;
	for (int32 Side = 0; Side < (bOneHanded ? 1 : 2); ++Side)
	{
		const bool bLeft = Side == 1;
		const int32 Hand = Ref.FindBoneIndex(bLeft ? TEXT("hand_L") : TEXT("hand_R"));
		const int32 Lower = Hand != INDEX_NONE ? Ref.GetParentIndex(Hand) : INDEX_NONE;
		if (Hand == INDEX_NONE || Lower == INDEX_NONE)
		{
			continue;
		}
		const FTransform HandRef = RefCS(Hand);
		const FVector RestAlong = (HandRef.GetLocation() - RefCS(Lower).GetLocation()).GetSafeNormal();
		const FQuat RestBasis = FSOHandGrip::MakeBasis(RestAlong, FVector(0.0f, 1.0f, 0.0f), bLeft);
		const FQuat HandOffset = RestBasis.Inverse() * HandRef.GetRotation();
		const FQuat Basis = Target[Side].GetRotation();
		const FVector Along = Basis.GetAxisX();
		const FVector Palm = FSOHandGrip::PalmNormal(Basis, bLeft);

		// 1. the hand onto the gun. The firing hand is seated on the grip as this gun has it: the web between thumb and
		//    index under the top of the backstrap, the palm on the grip's side (measured on the mesh: the backstrap from
		//    behind, the side from the right). The support hand's palm goes onto the surface under it.
		FVector Wrist = Target[Side].GetLocation();
		if (!bLeft)
		{
			auto RigPoint = [&RigT](float X, float Y, float Z) { return RigT.TransformPosition(FVector(X, Y, Z)); };
			FVector Back, SideHit;
			if (Surface(RigPoint(-18.0f, 0.0f, -4.0f), RigPoint(3.0f, 0.0f, -4.0f), Back))
			{
				const float BackX = static_cast<float>(RigT.InverseTransformPosition(Back).X);
				float SideY = 1.6f;
				if (Surface(RigPoint(BackX + 1.8f, 8.0f, -4.5f), RigPoint(BackX + 1.8f, -1.0f, -4.5f), SideHit))
				{
					SideY = static_cast<float>(RigT.InverseTransformPosition(SideHit).Y);
				}
				// rig-space basis of the grip (the same the rig built the target from)
				const FVector AlongR = RigT.InverseTransformVectorNoScale(Along);
				const FVector ThumbR = RigT.InverseTransformVectorNoScale(Basis.GetAxisY());
				// the web sits about 6.2 cm along the hand and 3 cm to the thumb's side of the wrist
				FVector WristR = FVector(BackX + 0.5f, 0.0f, -1.6f) - AlongR * 6.2f - ThumbR * 3.0f;
				WristR.Y = SideY + 1.3f;
				const FVector Now = RigT.InverseTransformPosition(Wrist);
				const FVector Move = (WristR - Now).GetClampedToMaxSize(6.0f);
				FitOffset[Side] = Move;
				Wrist = RigT.TransformPosition(Now + Move);
			}
		}
		else
		{
			const FVector Contact = Wrist + Along * 5.0f + Palm * 1.3f;
			FVector On;
			if (Surface(Contact - Palm * 6.0f, Contact + Palm * 5.0f, On))
			{
				const float Shift = FMath::Clamp(static_cast<float>(FVector::DotProduct(On - Contact, Palm)), -3.0f, 3.0f);
				Wrist += Palm * Shift;
				FitOffset[Side] = RigT.InverseTransformVector(Palm * Shift);
			}
		}

		// 2. the fingers, joint by joint from the knuckle: each closes until the rest of the finger touches the gun
		const FTransform HandWorld(Basis * HandOffset, Wrist, Mesh->GetComponentScale());
		const float Size = static_cast<float>(Mesh->GetComponentScale().X);
		for (int32 F = 0; F < 5; ++F)
		{
			int32 Chain[3];
			bool bChain = true;
			for (int32 K = 0; K < 3; ++K)
			{
				Chain[K] = Ref.FindBoneIndex(*FString::Printf(TEXT("%s_0%d_%s"), FingerNames[F], K + 1, bLeft ? TEXT("L") : TEXT("R")));
				bChain &= Chain[K] != INDEX_NONE;
			}
			if (!bChain)
			{
				continue;
			}
			const float TipLength = static_cast<float>(RefLocal[Chain[2]].GetLocation().Size()) * 0.8f * Size;
			float Curl[3] = { 0.0f, 0.0f, 0.0f };
			float SpreadDeg = 0.0f;
			// the finger's joints and tip in world space for the current curl
			auto Pose = [&](FVector Joint[4])
			{
				FTransform Parent = HandWorld;
				FVector Axis = FVector::ZeroVector;
				FVector Dir = Along;
				for (int32 K = 0; K < 3; ++K)
				{
					FTransform Rigid = RefLocal[Chain[K]] * Parent;
					if (K == 0)
					{
						FVector FingerDir = ((RefLocal[Chain[1]] * Rigid).GetLocation() - Rigid.GetLocation()).GetSafeNormal();
						if (F == 4 && SpreadDeg > 0.01f)
						{
							const float Sign = FVector::DotProduct(FVector::CrossProduct(FingerDir, Palm), Along) >= 0.0f ? 1.0f : -1.0f;
							const FQuat Spread(Along, FMath::DegreesToRadians(SpreadDeg) * Sign);
							Rigid.SetRotation(Spread * Rigid.GetRotation());
							FingerDir = Spread.RotateVector(FingerDir);
						}
						Axis = FVector::CrossProduct(FingerDir, Palm).GetSafeNormal();
					}
					const FQuat Close(Axis, FMath::DegreesToRadians(Curl[K]));
					Parent = FTransform(Close * Rigid.GetRotation(), Rigid.GetLocation(), Rigid.GetScale3D());
					Joint[K] = Rigid.GetLocation();
					if (K == 2)
					{
						Dir = (Joint[2] - Joint[1]).GetSafeNormal();
						Dir = Close.RotateVector(Dir);
					}
				}
				Joint[3] = Joint[2] + Dir * TipLength;
			};
			auto Blocked = [&](int32 From)
			{
				FVector J[4];
				Pose(J);
				// (the knuckle end of the first bone lies in the palm, against what the palm rests on: the test starts
				// a little way out; the thumb's first bone is the ball of the thumb itself and is left out)
				for (int32 K = FMath::Max(From, F == 4 ? 1 : 0); K < 3; ++K)
				{
					const FVector A = K == 0 ? FMath::Lerp(J[0], J[1], 0.4f) : J[K];
					if (Touches(A, J[K + 1], FingerRadius[F] * Size * (K == 0 ? 0.80f : (K == 1 ? 0.78f : 0.72f))))
					{
						return true;
					}
				}
				return false;
			};
			// Closing: all three joints together in a natural proportion (a curved finger, not a hook). A straight
			// finger often starts inside something in front of the hand (the magazine, the trigger guard): the first
			// free pose past that is where the wrap begins; from there it closes until it touches, then the middle
			// and tip joints go on alone until they touch too.
			static const float Share[3] = { 0.82f, 1.0f, 0.62f };
			auto Set = [&](float T) { for (int32 K = 0; K < 3; ++K) { Curl[K] = T * MaxCurl[F][K] * Share[K]; } };
			bool bAnyContact = false;
			if (F == 4 && Blocked(0))
			{
				// the thumb lies through what the hand holds: swing it round to the far side until it comes free
				for (float S = 8.0f; S <= 80.0f; S += 8.0f)
				{
					SpreadDeg = S;
					if (!Blocked(0))
					{
						SpreadDeg = FMath::Min(S + 6.0f, 80.0f);      // a little clear of the edge it came round
						break;
					}
				}
				if (Blocked(0))
				{
					SpreadDeg = 0.0f;
				}
			}
			const bool bStartsInside = Blocked(0);
			const float Step = 0.035f;
			float T = 0.0f;
			bool bFree = !bStartsInside;
			for (; !bFree && T <= 1.0f; T += Step)
			{
				Set(T);
				bFree = !Blocked(0);
			}
			if (bFree)
			{
				float Last = T;
				for (T += Step; T <= 1.0f; T += Step)
				{
					Set(T);
					if (Blocked(0))
					{
						bAnyContact = true;
						break;
					}
					Last = T;
				}
				Set(Last);
				for (int32 K = 1; K < 3 && bAnyContact; ++K)
				{
					for (float A = Curl[K] + 3.0f; A <= MaxCurl[F][K]; A += 3.0f)
					{
						const float Keep = Curl[K];
						Curl[K] = A;
						if (Blocked(K))
						{
							Curl[K] = Keep;
							break;
						}
					}
				}
			}
			UE_LOG(LogTemp, Verbose, TEXT("FitGrip:   %s %s %s curl %.0f %.0f %.0f (preset %.0f %.0f %.0f)"), bLeft ? TEXT("L") : TEXT("R"), FingerNames[F],
				bStartsInside ? TEXT("INSIDE") : (bAnyContact ? TEXT("fit") : TEXT("no contact")), Curl[0], Curl[1], Curl[2],
				FitFingers[Side].Curl[F][0], FitFingers[Side].Curl[F][1], FitFingers[Side].Curl[F][2]);
			if (F == 4 && !bStartsInside)
			{
				// the thumb keeps where it came free even with nothing to press on (its preset would put it back through)
				FitFingers[Side].ThumbSpread = SpreadDeg;
				if (!bAnyContact && SpreadDeg > 0.0f)
				{
					Set(0.18f);
					bAnyContact = true;
				}
			}
			if (bAnyContact)
			{
				// the trigger finger rests on the trigger: it never closes harder than its preset
				for (int32 K = 0; K < 3; ++K)
				{
					const float Preset = FitFingers[Side].Curl[F][K];
					FitFingers[Side].Curl[F][K] = (!bLeft && F == 0) ? FMath::Min(Curl[K], Preset + 30.0f) : Curl[K];
				}
				++Fitted;
			}
		}
	}
	for (UStaticMeshComponent* Part : Parts)
	{
		Part->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	}
	bFitDone = true;
	UE_LOG(LogTemp, Verbose, TEXT("FitGrip: %d fingers fitted on %d parts, offsets %s / %s"), Fitted, Parts.Num(), *FitOffset[0].ToCompactString(), *FitOffset[1].ToCompactString());
}

void USOLocomotionAnimInstance::UpdateBodyMotion(const ACharacter* Character, float DeltaSeconds)
{
	const USkeletalMeshComponent* Mesh = GetSkelMeshComponent();
	const float Dt = FMath::Max(DeltaSeconds, 1e-4f);
	bBodyMotion = Character && Mesh && !bArmsOnly && !bDead;
	if (!bBodyMotion)
	{
		WarpYaw = LeanRoll = LeanPitch = PelvisDrop = FootIKAlpha = StandYaw = 0.0f;
		bHaveYaw = bTurning = bCrouchPose = false;
		TurnTime = TurnLift[0] = TurnLift[1] = 0.0f;
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

	// Standing: the feet stay where they are while the aim turns (the hips keep their heading, the spine takes the
	// twist). Past TurnInPlaceAngle the body steps round under the aim; moving, the legs come round at once.
	const float ActorYaw = static_cast<float>(Character->GetActorRotation().Yaw);
	const float Turned = bHaveYaw ? FRotator::NormalizeAxis(ActorYaw - LastActorYaw) : 0.0f;
	LastActorYaw = ActorYaw;
	bHaveYaw = true;
	const bool bStanding = Speed2D < 25.0f && !bInAir && !bSliding && !bMantling;
	if (bStanding && !bTurning)
	{
		StandYaw = FMath::Clamp(StandYaw - Turned, -TurnInPlaceAngle - 12.0f, TurnInPlaceAngle + 12.0f);
		bTurning = FMath::Abs(StandYaw) > TurnInPlaceAngle;
	}
	else
	{
		StandYaw = FMath::FInterpTo(StandYaw - (bStanding ? Turned : 0.0f), 0.0f, Dt, bStanding ? 6.5f : 12.0f);
		bTurning = bTurning && bStanding && FMath::Abs(StandYaw) > 1.5f;
	}
	// A turn on the spot is stepped, not slid: the foot on the side of the turn comes off the ground and is carried
	// round first while the other pivots on its ball, then that one follows.
	TurnTime = bTurning ? TurnTime + Dt : 0.0f;
	{
		auto Step = [this](float From, float To) { return TurnTime > From && TurnTime < To ? FMath::Sin((TurnTime - From) / (To - From) * PI) : 0.0f; };
		const int32 Lead = StandYaw < 0.0f ? 1 : 0;              // the hips are behind to the left: the turn is to the right
		const float Want[2] = { 5.5f * (Lead == 0 ? Step(0.0f, 0.22f) : Step(0.18f, 0.42f)), 5.5f * (Lead == 1 ? Step(0.0f, 0.22f) : Step(0.18f, 0.42f)) };
		for (int32 i = 0; i < 2; ++i)
		{
			TurnLift[i] = bTurning ? Want[i] : FMath::FInterpTo(TurnLift[i], 0.0f, Dt, 20.0f);
		}
	}

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
	if (bMantling)
	{
		// over an obstacle: a vault lays the body over away from the planted (right) hand; a mantle / climb folds
		// forward over the lip as the chest comes past it
		// (a body with its own vault / mantle / climb clips gets all of this from them)
		const bool bOwnClip = TraversalKind == 1 ? Clips.Vault != nullptr : (TraversalClimb ? Clips.Climb != nullptr : Clips.Mantle != nullptr);
		const float Arc = bOwnClip ? 0.0f : FMath::Sin(TraversalAlpha * PI);
		WantRoll = TraversalKind == 1 ? 18.0f * Arc : 0.0f;
		WantPitch = bOwnClip ? 0.0f : (TraversalKind == 1 ? -30.0f * Arc : -18.0f * FMath::SmoothStep(0.2f, 0.6f, TraversalAlpha) * (1.0f - FMath::SmoothStep(0.8f, 1.0f, TraversalAlpha)));
	}

	// Landing: the hips sink with the impact and spring back.
	if (bInAir)
	{
		LastAirVz = Character->GetVelocity().Z;
	}
	else if (bWasInAir && !bMantling)
	{
		// (with a landing clip the clip folds the body: the spring only adds the first give)
		CompressVel += FMath::Clamp((-LastAirVz - 200.0f) * 0.12f, 0.0f, 160.0f) * (Clips.Land ? 0.45f : 1.0f);
	}
	bWasInAir = bInAir;
	// Crouched: a body with its own crouch clips plays them (see the weights). One without: the hips sink over bent
	// legs (the feet stay where the standing clip puts them) and the chest comes forward.
	const bool bCrouched = Character->bIsCrouched && !bSliding && !bMantling && !bInAir;
	bCrouchPose = bCrouched;
	CrouchAlpha = FMath::FInterpTo(CrouchAlpha, bCrouched ? 1.0f : 0.0f, Dt, 9.0f);
	const float SunkCrouch = HasCrouchClips() ? 0.0f : CrouchAlpha;
	WantPitch -= 15.0f * SunkCrouch;
	const float Stiff = 260.0f, Damp = 2.0f * FMath::Sqrt(Stiff) * 0.75f;
	CompressVel += (-Stiff * Compress - Damp * CompressVel) * Dt;
	Compress = FMath::Max(Compress + CompressVel * Dt, 0.0f);
	WantPitch -= Compress * 0.6f;
	LeanRoll = FMath::FInterpTo(LeanRoll, WantRoll, Dt, bMantling ? 14.0f : 8.0f);
	LeanPitch = FMath::FInterpTo(LeanPitch, WantPitch, Dt, bMantling ? 14.0f : 8.0f);

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
	// (a turn on the spot: the weight sinks a touch while the feet step round)
	// (a vault: the body goes over low, hips down by the planted hand, the knees up under it)
	const float VaultLow = bMantling && TraversalKind == 1 && !Clips.Vault ? 26.0f * FMath::Sin(TraversalAlpha * PI) : 0.0f;
	PelvisDrop = PelvisFeet * FootIKAlpha + Compress + VaultLow + CrouchDrop * SunkCrouch + (bTurning ? 1.6f * FMath::Min(FMath::Abs(StandYaw) / FMath::Max(TurnInPlaceAngle, 1.0f), 1.0f) : 0.0f);
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
		Instance->Clips.Death, Instance->ActiveAttack ? Instance->ActiveAttack.Get() : Instance->Clips.Attack.Get(), Instance->Clips.Slide, Instance->FidgetClip,
		Instance->Clips.Stroll, Instance->Clips.Land, Instance->Clips.Vault, Instance->Clips.Mantle, Instance->Clips.Climb,
		Instance->Clips.Crouch, Instance->Clips.CrouchWalk, Instance->Clips.Stop };
	for (int32 i = 0; i < Count; ++i)
	{
		FSOLocomotionLayer& Layer = Layers[i];
		Layer.Clip = ClipList[i];
		Layer.Weight = Instance->Weights[i];
		Layer.bLoop = i == Idle || i == Walk || i == Run || i == Slide || i == Stroll || i == Crouch || i == CrouchWalk;
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
	StandYaw = Instance->GetStandYaw();
	MaxWaistTwist = Instance->MaxWaistTwist;
	HoldAlpha = Instance->GetHoldAlpha();
	LeanRoll = Instance->LeanRoll;
	LeanPitch = Instance->LeanPitch;
	PelvisDrop = Instance->PelvisDrop;
	FootOffset[0] = Instance->FootOffset[0];
	FootOffset[1] = Instance->FootOffset[1];
	TurnLift[0] = Instance->GetTurnLift(0);
	TurnLift[1] = Instance->GetTurnLift(1);
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
	const float KneeAhead = 4.0f;       // cm of "forward" added to the animated knee's offset from the hip-ankle line

	// 1. Orientation warping: the hips (and legs) turn toward the movement, spine and chest turn back so the
	//    shoulders keep facing the aim.
	//    Standing, the same turn keeps the feet planted while the aim (and the capsule) turns on the spot: that one
	//    is about the capsule's own axis (the component's origin), so the feet stay exactly where they were.
	//    The waist only twists so far (a body is not a hinge: a bare waist shows every degree): the pelvis takes half
	//    of the turn up to MaxWaistTwist, undone by the spine and chest, and the legs take the rest about their own
	//    hip joints.
	const float Total = WarpYaw + StandYaw;
	if (FMath::Abs(Total) > 0.1f)
	{
		const float Pelvis = FMath::Clamp(Total * 0.5f, -MaxWaistTwist, MaxWaistTwist);
		const float Legs = Total - Pelvis;
		const float W = FMath::DegreesToRadians(Pelvis);
		const FQuat Stand(Up, FMath::DegreesToRadians(Pelvis * StandYaw / Total));
		const FTransform H = CS[Hips];
		SetCS(Hips, FTransform(H.GetRotation(), Stand.RotateVector(H.GetLocation()), H.GetScale3D()));
		Turn(Hips, FQuat(Up, W));
		if (Spine != INDEX_NONE)
		{
			Turn(Spine, FQuat(Up, -W * 0.5f));
		}
		if (Chest != INDEX_NONE)
		{
			Turn(Chest, FQuat(Up, -W * 0.5f));
		}
		for (int32 i = 0; i < 2; ++i)
		{
			if (Leg[i][0] != INDEX_NONE)
			{
				Turn(Leg[i][0], FQuat(Up, FMath::DegreesToRadians(Legs)));
			}
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
			FootWanted[i].AddToTranslation(Up * (FootOffset[i] * FootIKAlpha + TurnLift[i]));
		}
	}

	// 3. The hips sink (landing, or so the lower foot reaches a step below).
	if (PelvisDrop > 0.01f)
	{
		FTransform H = CS[Hips];
		H.AddToTranslation(-Up * PelvisDrop);
		SetCS(Hips, H);
	}

	// 4. Two-bone leg IK onto the wanted feet. The knee keeps the side the animation bent it to, but a knee only bends
	//    one way: ahead of the line from the hip to the ankle, in the leg's own heading. An almost straight animated
	//    leg says nothing about that side (its offset from the line is a few millimetres of noise, and it flipped the
	//    knee backward and through the floor when the hips came down), so the leg's forward is always part of it and
	//    whatever points behind the line is taken out.
	if (PelvisDrop > 0.01f || FootIKAlpha > 0.01f)
	{
		const FVector LegFwd = FQuat(Up, FMath::DegreesToRadians(Total)).RotateVector(Fwd);
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
			FVector Bend = (Knee0 - S) - Dir * FVector::DotProduct(Knee0 - S, Dir);      // cm off the line, as animated
			const FVector Ahead = (LegFwd - Dir * FVector::DotProduct(LegFwd, Dir)).GetSafeNormal(1e-4f, Fwd);
			const float Behind = static_cast<float>(FVector::DotProduct(Bend, Ahead));
			if (Behind < 0.0f)
			{
				Bend -= Ahead * Behind;
			}
			Bend = (Bend + Ahead * KneeAhead).GetSafeNormal(1e-4f, Ahead);
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

	// (what the clips gave, to blend the solve in and out by HoldAlpha)
	const TArray<FTransform, TInlineAllocator<64>> Before = Local;

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
				FTransform Rigid = Local[I] * ParentCS;
				if (k == 0)
				{
					FVector FingerDir = ((Local[Chain[1]] * Rigid).GetLocation() - Rigid.GetLocation()).GetSafeNormal();
					if (f == 4 && FMath::Abs(Fingers.ThumbSpread) > 0.01f)
					{
						// the thumb round the hand's long axis, toward the palm's side
						const FVector AlongHand = Target.GetRotation().GetAxisX();
						const float Sign = FVector::DotProduct(FVector::CrossProduct(FingerDir, Palm), AlongHand) >= 0.0f ? 1.0f : -1.0f;
						const FQuat Spread(AlongHand, FMath::DegreesToRadians(Fingers.ThumbSpread) * Sign);
						Rigid.SetRotation(Spread * Rigid.GetRotation());
						FingerDir = Spread.RotateVector(FingerDir);
					}
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

	if (HoldAlpha < 0.999f)
	{
		for (int32 I = 0; I < Num; ++I)
		{
			FTransform Mixed;
			Mixed.Blend(Before[I], Local[I], HoldAlpha);
			Local[I] = Mixed;
		}
	}
	for (FCompactPoseBoneIndex Index : Pose.ForEachBoneIndex())
	{
		Pose[Index] = Local[Index.GetInt()];
	}
}
