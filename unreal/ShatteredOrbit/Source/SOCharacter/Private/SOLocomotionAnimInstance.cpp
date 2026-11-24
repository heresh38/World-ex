#include "SOLocomotionAnimInstance.h"
#include "SOSpring.h"

#include "Animation/AnimSequenceBase.h"
#include "Animation/AnimationPoseData.h"
#include "AnimationRuntime.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/StaticMesh.h"
#include "ReferenceSkeleton.h"
#include "Engine/World.h"
#include "Misc/ScopeExit.h"
#include "GameFramework/Character.h"
#include "SOCharacterMovementComponent.h"
#include "SOCharacter.h"
#include "SOCombatCharacter.h"
#include "SOGunRigComponent.h"
#include "SOViewmodelComponent.h"
#include "SOWeapon.h"
#include "SOWeaponData.h"

namespace
{
	enum ELayer { Idle = 0, Walk, Run, Jump, Death, Attack, Slide, Fidget, Stroll, Land, Vault, Mantle, Climb, Crouch, CrouchWalk, Stop, Dodge, Count };
}

void USOLocomotionAnimInstance::Flinch(float Roll, float Pitch)
{
	FlinchRoll = FMath::Clamp(FlinchRoll + Roll, -34.0f, 34.0f);
	FlinchPitch = FMath::Clamp(FlinchPitch + Pitch, -34.0f, 34.0f);
}

void USOLocomotionAnimInstance::HitKick(ESOHitRegion Region, const FVector& Toward, float Strength)
{
	const float Front = static_cast<float>(Toward.X), Right = static_cast<float>(Toward.Y);
	switch (Region)
	{
	case ESOHitRegion::Head:
		// the head goes with the blow, the trunk only a little
		HeadKickPitch = FMath::Clamp(HeadKickPitch + Front * 42.0f * Strength, -48.0f, 48.0f);
		HeadKickYaw = FMath::Clamp(HeadKickYaw - Right * 34.0f * Strength, -40.0f, 40.0f);
		Flinch(Right * 7.0f * Strength, Front * 9.0f * Strength);
		break;
	case ESOHitRegion::ArmLeft:
	case ESOHitRegion::ArmRight:
	{
		// the shoulder is driven back (or forward, from behind) and the chest turns with it
		const float Side = Region == ESOHitRegion::ArmLeft ? -1.0f : 1.0f;
		FlinchTwist = FMath::Clamp(FlinchTwist + Side * (Front >= 0.0f ? 1.0f : -1.0f) * 30.0f * Strength, -40.0f, 40.0f);
		Flinch(Right * 11.0f * Strength, Front * 11.0f * Strength);
		break;
	}
	case ESOHitRegion::LegLeft:
	case ESOHitRegion::LegRight:
		// the leg gives: the hips drop and the trunk folds over it
		FlinchDip = FMath::Min(FlinchDip + 15.0f * Strength, 24.0f);
		Flinch((Region == ESOHitRegion::LegLeft ? 11.0f : -11.0f) * Strength, -13.0f * Strength);
		break;
	default:
		Flinch(Right * 24.0f * Strength, Front * 26.0f * Strength);
		break;
	}
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

void USOLocomotionAnimInstance::SetMeleeGuard(UAnimSequenceBase* Guard, float HoldAt)
{
	MeleeGuardHold = HoldAt;
	if (Guard != MeleeGuard)
	{
		MeleeGuard = Guard;
		MeleeGuardTime = 0.0f;
		if (!Guard)
		{
			MeleeBlowTime = -1.0f;
		}
	}
}

void USOLocomotionAnimInstance::PlayMeleeBlow(UAnimSequenceBase* Clip, float PlayRate)
{
	if (Clip)
	{
		MeleeBlow = Clip;
		MeleeBlowTime = 0.0f;
		MeleeBlowRate = FMath::Max(PlayRate, 0.05f);
	}
}

float USOLocomotionAnimInstance::GetAttackLength() const
{
	return Clips.Attack ? Clips.Attack->GetPlayLength() : 0.0f;
}

namespace
{
	/** A fitted grip, kept per gun and body for the rest of the session (see NativeUpdateAnimation). */
	struct FSOFitMemo
	{
		FSOFingerPose Fingers[2];
		FVector Offset[2];
		bool bTurn = false;
		bool bIndexInside = false;
		FQuat Basis = FQuat::Identity;
		float Drop = 0.0f;
	};
	TMap<FString, FSOFitMemo>& FitMemos()
	{
		static TMap<FString, FSOFitMemo> Memos;
		return Memos;
	}
}

bool USOLocomotionAnimInstance::RestoreFit(const FString& Key, const USOGunRigComponent* Rig)
{
	const FSOFitMemo* M = Key.IsEmpty() ? nullptr : FitMemos().Find(Key);
	if (!M)
	{
		return false;
	}
	FitFingers[0] = M->Fingers[0];
	FitFingers[1] = M->Fingers[1];
	FitOffset[0] = M->Offset[0];
	FitOffset[1] = M->Offset[1];
	bFitTurn = M->bTurn;
	bFitIndexInside = M->bIndexInside;
	FitBasis = M->Basis;
	FitGripDrop = M->Drop;
	FitRig = Rig;
	bFitDone = true;
	return true;
}

void USOLocomotionAnimInstance::KeepFit(const FString& Key)
{
	if (Key.IsEmpty() || !bFitDone)
	{
		return;
	}
	FSOFitMemo& M = FitMemos().FindOrAdd(Key);
	M.Fingers[0] = FitFingers[0];
	M.Fingers[1] = FitFingers[1];
	M.Offset[0] = FitOffset[0];
	M.Offset[1] = FitOffset[1];
	M.bTurn = bFitTurn;
	M.bIndexInside = bFitIndexInside;
	M.Basis = FitBasis;
	M.Drop = FitGripDrop;
}

void USOLocomotionAnimInstance::ForgetFits()
{
	FitMemos().Reset();
}

void USOLocomotionAnimInstance::NativeUpdateAnimation(float DeltaSeconds)
{
	Super::NativeUpdateAnimation(DeltaSeconds);
	// whatever this update decides goes to the pose this same frame (the engine's PreUpdate ran before it)
	ON_SCOPE_EXIT
	{
		GetProxyOnGameThread<FSOLocomotionProxy>().CopyFrom(this);
	};

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
		const bool bWasDodging = bDodging;
		bDodging = SOMove && SOMove->IsDodging();
		if (bDodging && !bWasDodging)
		{
			// the clip for the way it goes: the body's left or right, back, or ahead
			const FVector Dir = SOMove->GetDodgeDir();
			const float Side = static_cast<float>(FVector::DotProduct(Dir, Character->GetActorRightVector()));
			const float Fore = static_cast<float>(FVector::DotProduct(Dir, Character->GetActorForwardVector()));
			ActiveDodge = FMath::Abs(Side) > 0.5f ? (Side > 0.0f ? Clips.DodgeR : Clips.DodgeL) : (Fore < 0.0f ? Clips.DodgeB : Clips.DodgeF);
			DodgeTime = 0.0f;
		}
		DodgeTime += DeltaSeconds;
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
	// (one body in every view: first person is this body's own eyes, its head hidden from that camera alone)
	// (a body whose head parts are cut out of its own camera's picture by their materials keeps its head, and the head's
	// shadow: ASOCharacter::UpdateHeadHiding; the head is shrunk into its joint only for a body whose materials cannot)
	bHideHead = Player && Mesh && Mesh == Player->GetMesh() && Player->IsHeadHidden() && !Player->IsHeadHiddenByMaterial();
	{
		const USOCharacterMovementComponent* Move = Player ? Cast<USOCharacterMovementComponent>(Player->GetCharacterMovement()) : nullptr;
		bCarried = Player && ((Move && Move->IsSprinting()) || Player->IsDisplayCarry());
		// (a creature's head stays on its aim whatever its clip twitches; a player's and the stand-in's breathe with the clip)
		bHeadFree = Character->IsPlayerControlled() || !Character->GetController();
	}
	// anyone who fights holds their gun this way: the player, and the creatures that carry guns
	const ASOCombatCharacter* Holder = Cast<ASOCombatCharacter>(Character);
	const ASOWeapon* Held = Holder ? Holder->GetWeapon() : nullptr;
	const USOGunRigComponent* Rig = Held ? Held->GetRig() : nullptr;
	if (Player && Player->IsWeaponStowed())
	{
		Rig = nullptr;                                           // (the gun is put away: the hands are free)
	}
	FTransform Right, Left;
	GunAxis = FVector::ZeroVector;
	if (!bDead && Mesh && Rig && Rig->GetAttachParent() && Rig->GetHandTargets(Right, Left))
	{
		const FTransform ToMesh = Mesh->GetComponentTransform();
		RightTarget = Right.GetRelativeTransform(ToMesh);
		LeftTarget = Left.GetRelativeTransform(ToMesh);
		GunAxis = Held->IsReloading() ? FVector::ZeroVector : ToMesh.InverseTransformVectorNoScale(Rig->GetComponentTransform().GetUnitAxis(EAxis::X));
		Rig->GetFingerPoses(RightFingers, LeftFingers);
		// the hands fitted to this gun (once per gun, when it is at rest in them). The fit is a search of the gun's own
		// shape (tens of thousands of sweeps) and the same gun in the same hands always comes out the same: it is kept
		// per gun and body, and a switch back to a gun already fitted takes the kept one (the owner: "when switching
		// guns the entire game freezes for a second": every switch fitted both bodies again from nothing). The optic on its
		// rail is part of the gun's shape (a scope's mount is where the firing thumb wraps): kept per optic too, or a copy
		// of the gun with another sight took the first one's fit (the bolt-action's firing wrist at 83 degrees on its irons
		// with the fit made round a scope, 54 fitted to its own shape)
		const UStaticMeshComponent* Optic = Rig ? Rig->GetOptic() : nullptr;
		const FString MemoKey = Rig ? FString::Printf(TEXT("%s|%s|%s|%d"), *Rig->GetArchetype().ToString(),
			Optic && Optic->GetStaticMesh() ? *Optic->GetStaticMesh()->GetName() : TEXT("own"),
			Mesh->GetSkeletalMeshAsset() ? *Mesh->GetSkeletalMeshAsset()->GetPathName() : TEXT("-"), Holder->HoldsWithOneHand() ? 1 : 0) : FString();
		if ((FitRig.Get() != Rig || !bFitDone) && !Held->IsReloading() && RestoreFit(MemoKey, Rig))
		{
		}
		else if ((FitRig.Get() != Rig || !bFitDone) && !Held->IsReloading())
		{
			FitGripDrop = 0.0f;
			FitGrip(Rig, Mesh, Holder->HoldsWithOneHand());
			// (the trigger finger starts in the gun: this grip's trigger, frame or what hangs ahead of it (a drum) stands
			// where the usual seat puts the finger. The hand a little higher, then a little lower, the first that frees it.)
			for (const float Drop : { -0.75f, -1.5f, 0.75f, 1.5f, 2.25f })
			{
				if (!bFitDone || !bFitIndexInside)
				{
					break;
				}
				FitGripDrop = Drop;
				FitGrip(Rig, Mesh, Holder->HoldsWithOneHand());
			}
			if (bFitIndexInside && FitGripDrop != 0.0f)
			{
				FitGripDrop = 0.0f;                               // (no better lower: as it was)
				FitGrip(Rig, Mesh, Holder->HoldsWithOneHand());
			}
			else if (FitGripDrop != 0.0f)
			{
				UE_LOG(LogTemp, Verbose, TEXT("FitGrip: %s firing hand set %.2f cm lower (negative: higher): the trigger finger is free"), *Rig->GetArchetype().ToString(), FitGripDrop);
			}
			KeepFit(MemoKey);
		}
		if (bFitDone && FitRig.Get() == Rig)
		{
			const FTransform& RigT = Rig->GetComponentTransform();
			RightFingers = FitFingers[0];
			RightTarget.AddToTranslation(ToMesh.InverseTransformVector(RigT.TransformVector(FitOffset[0])));
			// (away only while the reload's own hand works a part: as far as its choreography has the hand at the fore end,
			// the hand is on its fitted hold there, so it comes home onto it; eased back in after the reload had ended, it
			// lay a centimetre or three into the gun for a tenth of a second)
			float FitTarget = 1.0f;
			if (const FSOReloadPose& P = Held->GetPose(); Held->IsReloading() && P.bHand)
			{
				auto AtHold = [](FName Anchor, const float* Off)
				{
					return (Anchor.IsNone() || Anchor == TEXT("fore")) && FMath::Abs(Off[0]) + FMath::Abs(Off[1]) + FMath::Abs(Off[2]) < 1e-3f ? 1.0f : 0.0f;
				};
				FitTarget = FMath::Lerp(AtHold(P.HandAnchorA, P.HandA), AtHold(P.HandAnchorB, P.HandB), FMath::Clamp(P.HandAlpha, 0.0f, 1.0f));
			}
			FitWeight = FMath::FInterpConstantTo(FitWeight, FitTarget, DeltaSeconds, 14.0f);
			if (FitWeight > 0.0f)
			{
				LeftFingers = FSOFingerPose::Lerp(LeftFingers, FitFingers[1], FitWeight);
				LeftTarget.AddToTranslation(ToMesh.InverseTransformVector(RigT.TransformVector(FitOffset[1] * FitWeight)));
				if (bFitTurn)
				{
					const FQuat Turned = ToMesh.GetRotation().Inverse() * (RigT.GetRotation() * FitBasis);
					LeftTarget.SetRotation(FQuat::Slerp(LeftTarget.GetRotation(), Turned, FitWeight));
				}
			}
		}
		const float Ads = Player ? (Player->GetViewmodel() ? Player->GetViewmodel()->GetAds() : 0.0f) : (Holder->IsAimingDownSights() ? 1.0f : 0.0f);
		AimPitch = FRotator::NormalizeAxis(Player ? Player->GetAimRotation().Pitch : Holder->GetBaseAimRotation().Pitch);
		bOneHand = Holder->HoldsWithOneHand();
		bSnugHold = Rig->IsSnugGrip();
		bHandgunHold = Rig->IsHandgun();
		// long guns blade the body to the gun; handguns square up (both arms out, an isosceles stance)
		const bool bHandgun = Rig->IsHandgun();
		Blade = bHandgun ? FMath::Lerp(5.0f, 8.0f, Ads) : FMath::Lerp(12.0f, 24.0f, Ads);
		Lean = FMath::Lerp(4.0f, 9.0f, Ads);
		HeadCant = bHandgun ? 0.0f : Ads * 14.0f;
		// The combat stance (FSOStance, the owner, 2026-11-23): the gun's class sets how the arms hold it and how the body
		// stands, at the ready and on the sights; relaxed (out of a fight) the body eases out of it.
		Stance = FSOStanceInputs();
		if (Player)
		{
			const USOWeaponData* Data = Held->GetData();
			const FSOStance& St = FSOStanceData::Get().For(Data ? Data->Family : NAME_None);
			const float Ready = FMath::Clamp(FMath::Max(Player->GetCombatReady(), Ads), 0.0f, 1.0f);
			const float R = Ready * Ready * (3.0f - 2.0f * Ready);
			Stance.bPlayer = true;
			Stance.Ready = R;
			Stance.Aim = Ads;
			// The elbows carried OUT at the sides at the ready and on the sights (the owner, 2026-11-23, on the first pass:
			// "arm not showing ... the arms are gone and the gun is in the players shoulder": an elbow put where the wrist
			// ran straightest hung under the gun in front of the chest, and from behind the body hid the whole arm). Each
			// comes no further out than leaves its wrist within the class's WristMax.
			for (int32 k = 0; k < 2; ++k)
			{
				Stance.ElbowSwing[k] = FMath::Lerp(St.ElbowSwing[k], St.ElbowSwingAim[k], Ads);
				Stance.WristShare[k] = St.WristShare[k];
				Stance.ElbowLeast[k] = St.ElbowLeast[k];
				Stance.ElbowMost[k] = St.ElbowMost[k];
				Stance.WristMax[k] = St.WristMax[k];
				Stance.ToeOut[k] = St.ToeOut[k] * FMath::Lerp(0.4f, 1.0f, R);
			}
			Stance.Shoulders = FMath::Lerp(St.Shoulders[0], St.Shoulders[1], Ads);
			Stance.HeadDown = St.HeadDown * R;
			// the legs: relaxed a little apart, at the ready the athletic stance (the knees bent over the toes)
			Stance.Hips = FMath::Lerp(St.Hips[0], St.Hips[1], R);
			Stance.Knees = FMath::Lerp(St.Knees[0], St.Knees[1], R);
			Stance.Stagger = FMath::Lerp(St.Stagger[0], St.Stagger[1], R);
			Stance.Width = FMath::Lerp(St.Width[0], St.Width[1], R);
			Stance.KneeOut = St.KneeOut;
			Stance.TurnStep = St.TurnStep;
			// (blading the trunk 12-24 degrees to the gun turned the off shoulder forward: with the collarbones' pull,
			// the rounded shoulders of the owner's picture)
			Blade = FMath::Lerp(St.Blade[0], St.Blade[1], Ads) * FMath::Lerp(0.4f, 1.0f, R);
			Lean = FMath::Lerp(St.Lean[0], St.Lean[1], Ads) * FMath::Lerp(0.3f, 1.0f, R);
		}
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
		// the dodge over whatever the legs are doing: its clip whole while the burst runs, fading as it plays out
		const float DodgeLength = ActiveDodge ? ActiveDodge->GetPlayLength() : 0.0f;
		const float Dodging = DodgeLength > 0.0f && DodgeTime < DodgeLength ? 1.0f - FMath::SmoothStep(DodgeLength * 0.55f, DodgeLength, DodgeTime) : 0.0f;
		if (Dodging > 0.0f)
		{
			for (float& T : Target)
			{
				T *= 1.0f - Dodging;
			}
			Target[Dodge] = Dodging;
		}
	}

	// Idle variations: standing still, not aiming.
	const bool bAimingNow = Player && Player->GetViewmodel() && Player->GetViewmodel()->GetAds() > 0.01f;
	const bool bStill = Target[Idle] > 0.99f && Speed < 10.0f && !bAimingNow && Clips.Fidgets.Num() > 0;
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
	Times[Dodge] = DodgeTime;
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
	// hand to hand: the guard comes on over a few frames, a blow runs once, standing the legs take it too
	MeleeWeight = FMath::FInterpConstantTo(MeleeWeight, MeleeGuard && !bDead ? 1.0f : 0.0f, DeltaSeconds, 5.0f);
	MeleeGuardTime += DeltaSeconds;
	if (MeleeBlowTime >= 0.0f)
	{
		MeleeBlowTime += DeltaSeconds * MeleeBlowRate;
		if (!MeleeBlow || MeleeBlowTime >= MeleeBlow->GetPlayLength())
		{
			MeleeBlowTime = -1.0f;
		}
	}
	const bool bPlanted = Speed < 120.0f && !bInAir && !bMantling && !bSliding;
	MeleeLegs = FMath::FInterpConstantTo(MeleeLegs, bPlanted ? 1.0f : 0.0f, DeltaSeconds, 4.0f);
	if (const APawn* Owner = TryGetPawnOwner(); Owner && MeleeWeight > 0.0f)
	{
		MeleePitch = FMath::Clamp(FRotator::NormalizeAxis(Owner->GetBaseAimRotation().Pitch), -60.0f, 60.0f);
	}
}

FQuat USOLocomotionAnimInstance::FingersTogether(const FVector& FingerDir, const FVector& MiddleDir, const FVector& Palm, float Amount)
{
	// both lines laid in the palm's plane; the finger turned that share of the way round the palm's normal toward the middle's
	const FVector A = (FingerDir - Palm * FVector::DotProduct(FingerDir, Palm)).GetSafeNormal();
	const FVector B = (MiddleDir - Palm * FVector::DotProduct(MiddleDir, Palm)).GetSafeNormal();
	if (A.IsNearlyZero() || B.IsNearlyZero())
	{
		return FQuat::Identity;
	}
	const float Angle = FMath::Atan2(static_cast<float>(FVector::DotProduct(FVector::CrossProduct(A, B), Palm)), static_cast<float>(FVector::DotProduct(A, B)));
	return FQuat(Palm, Angle * FMath::Clamp(Amount, 0.0f, 1.0f));
}

void USOLocomotionAnimInstance::FitGrip(const USOGunRigComponent* Rig, const USkeletalMeshComponent* Mesh, bool bOneHanded, float SlideBack)
{
	FitRig = Rig;
	bFitDone = false;
	bFitSlid = SlideBack > 0.0f;
	bFitIndexInside = false;
	FitOffset[0] = FitOffset[1] = FVector::ZeroVector;
	bFitTurn = false;
	Rig->GetFingerPoses(FitFingers[0], FitFingers[1]);
	if (Rig->HasHold())
	{
		// the gun brought its own hold (Data/holds/<archetype>.json): the hands rest where it says, as it says
		bFitDone = true;
		return;
	}
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
		FQuat Basis = Target[Side].GetRotation();
		FVector Along = Basis.GetAxisX();
		FVector Palm = FSOHandGrip::PalmNormal(Basis, bLeft);
		bool bPost = false;

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
				FVector WristR = FVector(BackX + 0.5f, 0.0f, -1.6f - FitGripDrop) - AlongR * 6.2f - ThumbR * 3.0f;
				WristR.Y = SideY + 1.3f;
				const FVector Now = RigT.InverseTransformPosition(Wrist);
				const FVector Move = (WristR - Now).GetClampedToMaxSize(6.0f);
				FitOffset[Side] = Move;
				Wrist = RigT.TransformPosition(Now + Move);
			}
		}
		else
		{
			// A POST under the gun (a vertical fore grip) is WRAPPED like a handle, not cupped from below: found by
			// what is round the gun's fore point a little above it (something a hand goes round: under 5.5 cm across and
			// 6.5 along, at two heights of three). The palm goes on its left side at half its height, the fingers round
			// its front, the thumb up; the hand runs forward and a little in.
			{
				const FVector ForeR = RigT.InverseTransformPosition(Wrist + Along * 5.0f + Palm * 1.3f) + FVector(0.0f, 1.2f, -0.4f);
				auto On = [&](const FVector& A, const FVector& B, FVector& Out)
				{
					// (a ray laid exactly along an edge of the mesh can slip between its two faces: missed, it is tried again a
					// hair to either side. The ksmg's post was found by one view's gun and not the other's on that alone.)
					for (const FVector& Nudge : { FVector::ZeroVector, FVector(0.07f, 0.0f, 0.05f), FVector(-0.07f, 0.0f, -0.05f) })
					{
						FVector Hit;
						if (Surface(RigT.TransformPosition(A + Nudge), RigT.TransformPosition(B + Nudge), Hit))
						{
							Out = RigT.InverseTransformPosition(Hit) - Nudge;
							return true;
						}
					}
					return false;
				};
				int32 Rings = 0;
				float LeftY = 0.0f, MidX = 0.0f, FrontX = 0.0f;
				// (looked for at the fore point, then a little ahead of it and behind, and lower down if nothing is found where
				// a post usually is: where the hand's target puts the fore point is not always on the post, and not every post
				// stands that high; the heavy machine gun's stood 8 cm behind it, and the hand closed on its drum)
				float PostUp = 3.5f;                                   // (how far above the fore point the palm goes)
				for (int32 Pass = 0; Pass < 2 && Rings < 2; ++Pass)
				{
					for (const float Dx : { 0.0f, 3.0f, -3.0f, 6.0f, -6.0f, 9.0f, -9.0f, 12.0f })
					{
						Rings = 0;
						for (const float Up : Pass == 0 ? TArray<float>{ 2.0f, 3.5f, 5.0f } : TArray<float>{ -1.0f, 0.5f, 2.0f })
						{
							const FVector C = ForeR + FVector(Dx, 0.0f, Up);
							FVector L, R, F, B;
							// (its front and back are looked for from 9 cm off, then nearer: a probe begun inside what stands next to the
							// post (the heavy machine gun's drum, close behind its grip) met that instead, and the post read 11 cm long)
							auto Length = [&]()
							{
								for (const float Off : { 9.0f, 5.0f, 3.0f })
								{
									if (On(C + FVector(Off, 0.0f, 0.0f), C + FVector(-9.0f, 0.0f, 0.0f), F) && On(C + FVector(-Off, 0.0f, 0.0f), C + FVector(9.0f, 0.0f, 0.0f), B)
										&& F.X - B.X > 1.0f && F.X - B.X < 6.5f)
									{
										return true;
									}
								}
								return false;
							};
							if (!Rig->IsHandgun() && On(C + FVector(0.0f, -9.0f, 0.0f), C + FVector(0.0f, 9.0f, 0.0f), L) && On(C + FVector(0.0f, 9.0f, 0.0f), C + FVector(0.0f, -9.0f, 0.0f), R)
								&& R.Y - L.Y > 1.0f && R.Y - L.Y < 5.5f && Length())
							{
								++Rings;
								LeftY = static_cast<float>(L.Y);
								MidX = static_cast<float>((F.X + B.X) * 0.5);
								FrontX = static_cast<float>(F.X);
							}
						}
						if (Rings >= 2)
						{
							PostUp = Pass == 0 ? 3.5f : 0.5f;
							break;
						}
					}
				}
				// (and it HANGS there: a hand's breadth ahead of it and behind it there is no underside at its foot's height.
				// A handguard is narrow too, and a band or a swivel inside it stops a ray across it: its underside runs on.)
				auto UnderAt = [&](float Dx)
				{
					FVector Hit;
					return On(ForeR + FVector(Dx, 0.0f, -6.0f), ForeR + FVector(Dx, 0.0f, 3.0f), Hit) && FMath::Abs(Hit.Z - ForeR.Z) < 1.5f;
				};
				UE_LOG(LogTemp, Verbose, TEXT("FitGrip: %s fore point (%.1f %.1f %.1f): %d rings, underside ahead %d behind %d"), *Rig->GetArchetype().ToString(), ForeR.X, ForeR.Y, ForeR.Z,
					Rings, Rings ? UnderAt(MidX - static_cast<float>(ForeR.X) + 4.5f) : -1, Rings ? UnderAt(MidX - static_cast<float>(ForeR.X) - 4.5f) : -1);
				if (Rings >= 2 && !UnderAt(MidX - static_cast<float>(ForeR.X) + 4.5f) && !UnderAt(MidX - static_cast<float>(ForeR.X) - 4.5f))
				{
				// (the post lies across the root of the fingers: the knuckles at its front, so the fingers close round
				// it; with the palm's middle on the post's middle, a thin post ended under the palm and the fingers
				// closed on the air ahead of it)
				// (and a centimetre out from its left side: the hand runs a little inward, so with the palm on the
				// post's side line the knuckles of the middle and ring fingers stood inside it)
				const float PalmX = FMath::Min(MidX, FrontX - 4.3f);
				// (the hand runs along the post's side, hardly in: angled 30 % into it, the bones of the palm crossed the post)
				const FSOHandGrip Wrap = FSOHandGrip::AtPalm(FVector(PalmX, LeftY - 1.0f, ForeR.Z + PostUp), FVector(0.97f, 0.1f, -0.2f), FVector(0.0f, 0.0f, 1.0f), true);
				// A post further out than the arm reaches is not taken: the arm slides the hand back along the gun to
				// where it does reach (the IK's own rule), off the post, and fingers curled round it ended up in the gun.
				// The hand holds the fore end there instead, as on a gun without one. (The shoulder: where it stands when
				// a long gun is held, as the reach rule further down takes it.)
				bool bReaches = SlideBack <= 0.0f;                 // (fitted again because the arm did not reach it: not taken)
				if (bReaches && Lower != INDEX_NONE && Ref.GetParentIndex(Lower) != INDEX_NONE)
				{
					const FVector ShoulderR(-23.0f, -27.0f, 5.0f);
					const float Arm = static_cast<float>(FVector::Dist(RefCS(Ref.GetParentIndex(Lower)).GetLocation(), RefCS(Lower).GetLocation())
						+ FVector::Dist(RefCS(Lower).GetLocation(), RefCS(Hand).GetLocation())) * static_cast<float>(Mesh->GetComponentScale().X);
					// (a hand round a post may reach to 98.5 % at the arm's own rule: taken up to 93 % of the estimate, which is
					// good to five centimetres; at 90 the heavy machine gun's post, 90.4 % out, was left for a grip on its drum)
					bReaches = FVector::Dist(ShoulderR, Wrap.Wrist) <= 0.93f * Arm;
					UE_LOG(LogTemp, Verbose, TEXT("FitGrip: %s post %s (%.0f %% of the arm)"), *Rig->GetArchetype().ToString(), bReaches ? TEXT("in reach") : TEXT("OUT of reach"),
						100.0f * FVector::Dist(ShoulderR, Wrap.Wrist) / FMath::Max(Arm, 1.0f));
				}
				if (bReaches)
				{
					bPost = true;
					FitOffset[Side] = Wrap.Wrist - RigT.InverseTransformPosition(Wrist);
					FitBasis = Wrap.Basis;
					bFitTurn = true;
					Basis = RigT.GetRotation() * Wrap.Basis;
					Along = Basis.GetAxisX();
					Palm = FSOHandGrip::PalmNormal(Basis, bLeft);
					Wrist = RigT.TransformPosition(Wrap.Wrist);
				}
				}
			}
			// (fitted again where the arm reaches: that far back along the gun to begin with)
			if (SlideBack > 0.0f && !bPost)
			{
				FitOffset[Side] += FVector(-SlideBack, 0.0f, 0.0f);
				Wrist -= RigT.GetUnitAxis(EAxis::X) * SlideBack;
			}
			// The support hand: first ALONG the gun to where the whole hand has room on one unbroken surface (centred
			// on a short handguard, the web of the thumb stood in its front cap), then onto that surface.
			const FVector ContactR = RigT.InverseTransformPosition(Wrist + Along * 5.0f + Palm * 1.3f);
			auto Depth = [&](float Dx, float& Out)
			{
				const FVector P = RigT.TransformPosition(ContactR + FVector(Dx, 0.0f, 0.0f));
				FVector On;
				if (!Surface(P - Palm * 7.0f, P + Palm * 5.0f, On))
				{
					return false;
				}
				Out = static_cast<float>(FVector::DotProduct(On - P, Palm));
				return true;
			};
			float D0 = 0.0f, ShiftX = 0.0f;
			if (!Rig->IsHandgun() && !bPost && Depth(0.0f, D0))
			{
				float Rear = 0.0f, Front = 0.0f, D = 0.0f;
				for (float X = -1.0f; X >= -14.0f && Depth(X, D) && FMath::Abs(D - D0) < 0.6f; X -= 1.0f)
				{
					Rear = X;
				}
				for (float X = 1.0f; X <= 14.0f && Depth(X, D) && FMath::Abs(D - D0) < 0.6f; X += 1.0f)
				{
					Front = X;
				}
				// along the gun the hand takes 4.5 cm behind the palm's middle (to the little finger's edge) and 9.5
				// ahead of it (the thumb lies forward along the side); where the surface is shorter than that, the
				// hand is centred on it
				const float Lo = Rear + 4.5f, Hi = Front - 9.5f;
				ShiftX = FMath::Clamp(Lo <= Hi ? FMath::Clamp(0.0f, Lo, Hi) : (Rear + Front) * 0.5f - 2.5f, -8.0f, 8.0f);
			}
			if (SlideBack > 0.0f)
			{
				ShiftX = FMath::Min(ShiftX, 0.0f);                    // (never forward again)
			}
			// ...and never further out along the gun than the arm reaches with a bend left in it. The shoulder is taken
			// where it stands when a long gun is held (measured in the gun's frame over every gun: the first-person arms'
			// within a centimetre or two, the body's within five), not where it happens to be this frame (a gun is
			// fitted as it comes up into the hands: the arm is not there yet).
			if (!Rig->IsHandgun() && !bPost && Lower != INDEX_NONE && Ref.GetParentIndex(Lower) != INDEX_NONE)
			{
				const FVector ShoulderR(-23.0f, -27.0f, 5.0f);
				const float Arm = static_cast<float>(FVector::Dist(RefCS(Ref.GetParentIndex(Lower)).GetLocation(), RefCS(Lower).GetLocation())
					+ FVector::Dist(RefCS(Lower).GetLocation(), RefCS(Hand).GetLocation())) * static_cast<float>(Mesh->GetComponentScale().X);
				const FVector WristR = RigT.InverseTransformPosition(Wrist);
				// (the body's shoulder is known to five centimetres, the arms' to one or two: the body keeps a wider margin, or
				// the arm's own rule (93 %) slid the hand back off where it was fitted, palm off the gun, fingers into it)
				const float Reach = 0.87f;
				while (ShiftX > -14.0f && FVector::Dist(ShoulderR, WristR + FVector(ShiftX, 0.0f, 0.0f)) > Reach * Arm)
				{
					ShiftX -= 1.0f;
				}
			}
			FVector Move(ShiftX, 0.0f, 0.0f);
			float Dn = 0.0f;
			if (!bPost && Depth(ShiftX, Dn))
			{
				// (on a handgun the palm stays a finger's thickness off the grip: the firing hand's fingertips lie under it)
				Move += RigT.InverseTransformVectorNoScale(Palm) * FMath::Clamp(Dn - (Rig->IsHandgun() ? 1.3f : 0.0f), -3.0f, 3.0f);
			}
			FitOffset[Side] += Move;
			Wrist += RigT.TransformVector(Move);
		}

		// 1b. the palm itself is never IN the gun: where one of its own bones (wrist to a knuckle) passes through the
		//     gun's surface (a fore end fatter or squarer than the grip was written for), the hand backs off along its
		//     palm's normal until it lies on it.
		const float Size = static_cast<float>(Mesh->GetComponentScale().X);
		{
			auto PalmIn = [&](const FVector& At)
			{
				const FTransform HW(Basis * HandOffset, At, Mesh->GetComponentScale());
				for (int32 F = 0; F < 4; ++F)
				{
					const int32 Knuckle = Ref.FindBoneIndex(*FString::Printf(TEXT("%s_01_%s"), FingerNames[F], bLeft ? TEXT("L") : TEXT("R")));
					if (Knuckle == INDEX_NONE)
					{
						continue;
					}
					const FVector K = (RefLocal[Knuckle] * HW).GetLocation();
					if (Touches(FMath::Lerp(At, K, 0.35f), K, 0.6f * Size))           // (a margin: the arm that holds it is not always exactly where the fit put it)
					{
						return true;
					}
				}
				return false;
			};
			for (int32 Step = 0; Step < 10 && PalmIn(Wrist); ++Step)
			{
				Wrist -= Palm * 0.4f;
				FitOffset[Side] -= RigT.InverseTransformVectorNoScale(Palm) * 0.4f;
			}
		}

		// 1c. the firing hand sits LOW enough on its grip for the middle finger to pass under the trigger guard: where
		//     that finger's first bone is in the gun however it is bent, the hand goes down the grip (away from the
		//     thumb's side) a little at a time.
		if (!bLeft)
		{
			const int32 M0 = Ref.FindBoneIndex(TEXT("middle_01_R")), M1 = Ref.FindBoneIndex(TEXT("middle_02_R"));
			auto MiddleFree = [&](const FVector& At)
			{
				const FTransform HW(Basis * HandOffset, At, Mesh->GetComponentScale());
				const FTransform Rigid = RefLocal[M0] * HW;
				const FVector J0 = Rigid.GetLocation();
				const FVector Bone = (RefLocal[M1] * Rigid).GetLocation() - J0;
				const FVector Axis = FVector::CrossProduct(Bone.GetSafeNormal(), Palm).GetSafeNormal();
				for (const float Bent : { 25.0f, 45.0f, 65.0f })
				{
					const FVector J1 = J0 + FQuat(Axis, FMath::DegreesToRadians(Bent)).RotateVector(Bone);
					if (!Touches(FMath::Lerp(J0, J1, 0.4f), J1, 0.5f * Size))
					{
						return true;
					}
				}
				return false;
			};
			const FVector Down = -Basis.GetAxisY();
			for (int32 Step = 0; M0 != INDEX_NONE && M1 != INDEX_NONE && Step < 8 && !MiddleFree(Wrist); ++Step)
			{
				Wrist += Down * 0.3f;
				FitOffset[Side] += RigT.InverseTransformVectorNoScale(Down) * 0.3f;
			}
		}

		// 1d. the TRIGGER, found on the gun's own shape by how THIN it is: probes across the gun (right to left and back)
		//     from the grip forward, at three heights under the receiver: the grip is several centimetres across, the
		//     gap in front of it is empty, and the trigger is a blade under a centimetre thick with that gap behind it.
		//     The finger on it is posed below. (Probes dropped from above read the grip, the blade and the guard as
		//     one: on most guns nothing is open under the receiver between them.)
		FVector TriggerAt = FVector::ZeroVector;           // (rig space: a finger's radius in front of the blade)
		bool bTrigger = false;
		if (!bLeft)
		{
			auto Across = [&](float X, float Z, float& OutWidth)
			{
				FVector R, L;
				if (!Surface(RigT.TransformPosition(FVector(X, 5.0f, Z)), RigT.TransformPosition(FVector(X, -5.0f, Z)), R)
					|| !Surface(RigT.TransformPosition(FVector(X, -5.0f, Z)), RigT.TransformPosition(FVector(X, 5.0f, Z)), L))
				{
					return false;
				}
				OutWidth = static_cast<float>(RigT.InverseTransformPosition(R).Y - RigT.InverseTransformPosition(L).Y);
				return true;
			};
			for (const float Z : { -1.2f, -1.8f, -2.4f })
			{
				bool bGap = false;
				for (float X = 0.0f; X <= 10.0f && !bTrigger; X += 0.25f)
				{
					float W = 0.0f;
					const bool bHit = Across(X, Z, W);
					if (!bHit)
					{
						bGap = true;                                  // (open: the space in front of the grip)
						continue;
					}
					if (bGap && W > 0.15f && W < 1.1f)
					{
						// a thin blade with the gap behind it; its front face is where the thin run ends
						float Front = X;
						for (float X2 = X + 0.1f; X2 <= X + 1.5f; X2 += 0.1f)
						{
							float W2 = 0.0f;
							if (!Across(X2, Z, W2) || W2 > 1.1f)
							{
								break;
							}
							Front = X2;
						}
						bTrigger = true;
						TriggerAt = FVector(Front + 1.05f, 0.0f, Z);
					}
					else if (W >= 1.1f)
					{
						bGap = false;                                 // (the grip, or something solid: not the blade)
					}
				}
				if (bTrigger)
				{
					break;
				}
			}
			UE_LOG(LogTemp, Verbose, TEXT("FitGrip: %s trigger %s at %s"), *Rig->GetArchetype().ToString(), bTrigger ? TEXT("found") : TEXT("not found"),
				*TriggerAt.ToCompactString());
		}

		// 2. the fingers, joint by joint from the knuckle: each closes until the rest of the finger touches the gun
		const FTransform HandWorld(Basis * HandOffset, Wrist, Mesh->GetComponentScale());
		// (the snug way: the fingers brought together toward the middle finger's line before they close)
		const float Together = Rig->IsSnugGrip() ? SnugTogether : 0.0f;
		FVector MiddleDir = FVector::ZeroVector;
		{
			const int32 M0 = Ref.FindBoneIndex(*FString::Printf(TEXT("middle_01_%s"), bLeft ? TEXT("L") : TEXT("R")));
			const int32 M1 = Ref.FindBoneIndex(*FString::Printf(TEXT("middle_02_%s"), bLeft ? TEXT("L") : TEXT("R")));
			if (M0 != INDEX_NONE && M1 != INDEX_NONE)
			{
				const FTransform M = RefLocal[M0] * HandWorld;
				MiddleDir = ((RefLocal[M1] * M).GetLocation() - M.GetLocation()).GetSafeNormal();
			}
		}
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
			float SpreadDeg = 0.0f, InDeg = 0.0f, LiftDeg = 0.0f;
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
						const FVector FingerDir = ((RefLocal[Chain[1]] * Rigid).GetLocation() - Rigid.GetLocation()).GetSafeNormal();
						FVector ThumbDir = FingerDir;
						Axis = FVector::CrossProduct(FingerDir, Palm).GetSafeNormal();
						if (Together > 0.0f && (F == 2 || F == 3 || (F == 0 && bLeft)) && !MiddleDir.IsNearlyZero())
						{
							const FQuat Toward = FingersTogether(FingerDir, MiddleDir, Palm, Together);
							Rigid.SetRotation(Toward * Rigid.GetRotation());
							Axis = FVector::CrossProduct(Toward.RotateVector(FingerDir), Palm).GetSafeNormal();
						}
						if (F == 4 && FMath::Abs(SpreadDeg) > 0.01f)
						{
							// (the axis it closes about TURNS WITH the thumb: taken again from the swung thumb and the palm,
							// it vanished once the thumb pointed along the palm's normal, and a thumb swung right round a
							// grip could not close: it stood straight out)
							const float Sign = FVector::DotProduct(Axis, Along) >= 0.0f ? 1.0f : -1.0f;
							const FQuat Spread(Along, FMath::DegreesToRadians(SpreadDeg) * Sign);
							Rigid.SetRotation(Spread * Rigid.GetRotation());
							Axis = Spread.RotateVector(Axis);
							ThumbDir = Spread.RotateVector(ThumbDir);
						}
						if (F == 0 && FMath::Abs(LiftDeg) > 0.01f)
						{
							// (the index turned in the palm's plane, up to a trigger higher than its knuckle)
							const FQuat Lift(Palm, FMath::DegreesToRadians(LiftDeg));
							Rigid.SetRotation(Lift * Rigid.GetRotation());
							Axis = Lift.RotateVector(Axis);
						}
						if (F == 4 && InDeg > 0.01f)
						{
							// drawn in toward the fingers, about the palm's normal (whichever way round brings it there)
							FQuat In(Palm, FMath::DegreesToRadians(InDeg));
							if (FVector::DotProduct(In.RotateVector(ThumbDir), Along) < FVector::DotProduct(In.Inverse().RotateVector(ThumbDir), Along))
							{
								In = In.Inverse();
							}
							Rigid.SetRotation(In * Rigid.GetRotation());
							Axis = In.RotateVector(Axis);
						}
					}
					const FQuat Close(Axis, FMath::DegreesToRadians(Curl[K]));
					const FQuat Before = Parent.GetRotation();         // (the bone before this one, as posed)
					Parent = FTransform(Close * Rigid.GetRotation(), Rigid.GetLocation(), Rigid.GetScale3D());
					Joint[K] = Rigid.GetLocation();
					if (K == 2)
					{
						// the tip runs on the way the last bone turns from the one before it, its resting bend included (as
						// MeasureHold and the drawn finger do: the curl alone left a bent tip pointing too straight)
						Dir = (Parent.GetRotation() * Before.Inverse()).RotateVector((Joint[2] - Joint[1]).GetSafeNormal());
					}
				}
				Joint[3] = Joint[2] + Dir * TipLength;
			};
			float Clearance = 1.0f;                                     // (the thumb's search keeps a margin: see below)
			auto Blocked = [&](int32 From)
			{
				FVector J[4];
				Pose(J);
				// (the knuckle end of the first bone lies in the palm, against what the palm rests on: the test starts
				// a little way out; the thumb's first bone is the ball of the thumb itself and is left out)
				for (int32 K = FMath::Max(From, F == 4 ? 1 : 0); K < 3; ++K)
				{
					const FVector A = K == 0 ? FMath::Lerp(J[0], J[1], 0.4f) : J[K];
					if (Touches(A, J[K + 1], Clearance * FingerRadius[F] * Size * (K == 0 ? 0.80f : (K == 1 ? 0.78f : 0.82f))))
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
			bool bThumbHeld = false;
			if (F == 4)
			{
				// The thumb lies where it is free, tried in the order the grip is held in. The firing hand's goes round
				// the back of the grip to its far side. The support hand's lies along the side its palm is on: lifted
				// off that side first, and only then round.
				static const float Tries[2][12] = {
					{ 0.0f, 12.0f, 24.0f, 36.0f, 48.0f, 60.0f, 70.0f, 80.0f, 88.0f, -10.0f, -20.0f, -30.0f },
					{ 0.0f, -8.0f, -16.0f, -24.0f, -32.0f, -40.0f, 10.0f, 20.0f, 30.0f, 40.0f, -50.0f, -60.0f } };   // (never far round: it would stand up over the gun's top, in the sights)
				bool bPlaced = false;
				// The thumb is placed ON the gun where a hand puts it, found on this gun's own surface: the firing hand's
				// round the back of the grip and along its FAR side (the left), pointing forward; the support hand's
				// forward along the left side of the fore end, a little up, never over its top. Of the free poses
				// (swung, drawn in, partly closed), the one whose tip comes nearest that place. (Taken as the first
				// free way and then closed toward the palm, the firing thumb stood out under the grip and the support
				// thumb curled up over the handguard into the sights.)
				FVector Goal = FVector::ZeroVector;
				const bool bGoal = !bPost && !(bLeft && Rig->IsHandgun()) && [&]()
				{
					SpreadDeg = InDeg = 0.0f;
					Set(0.0f);
					FVector J[4];
					Pose(J);
					const FVector B = RigT.InverseTransformPosition(J[0]);
					const float Len = static_cast<float>(FVector::Dist(J[0], J[3]) / FMath::Max(RigT.GetScale3D().X, 0.01));
					// (the firing thumb goes round the back first: its tip ends little further forward than its root)
					const float AimX = static_cast<float>(B.X) + (bLeft ? 0.85f : 0.45f) * Len;
					// (the snug way the support thumb's place is at its root's height, not above it: from the eye it stood up
					// beside the handguard, its tip by the front sight)
					const float AimZ = static_cast<float>(B.Z) + (bLeft ? (Rig->IsSnugGrip() ? 0.0f : 1.5f) : 0.5f);
					FVector Hit;
					if (!Surface(RigT.TransformPosition(FVector(AimX, -16.0f, AimZ)), RigT.TransformPosition(FVector(AimX, 16.0f, AimZ)), Hit))
					{
						return false;
					}
					const FVector H = RigT.InverseTransformPosition(Hit);
					Goal = RigT.TransformPosition(FVector(AimX, H.Y - FingerRadius[4] * (Rig->IsSnugGrip() ? 0.6f : 0.9f), AimZ));
					return true;
				}();
				if (bGoal)
				{
					// (with a margin: the body breathes and an arm that falls short slides the hand a little, and a thumb
					// laid exactly on the surface went into it)
					Clearance = Rig->IsSnugGrip() ? 1.25f : 1.6f;             // (the hands no longer trail the gun: a closer margin holds)
					float Best = 1e9f, BS = 0.0f, BI = 0.0f, BT = 0.0f;
					auto Try = [&](float S, float In, float Tc)
					{
						SpreadDeg = S;
						InDeg = In;
						Set(Tc);
						if (Blocked(0))
						{
							return;
						}
						FVector J[4];
						Pose(J);
						const float D = static_cast<float>(FVector::Dist(J[3], Goal) + 0.35 * FVector::Dist(FMath::Lerp(J[1], J[2], 0.5f), Goal));
						if (D < Best)
						{
							Best = D;
							BS = S;
							BI = In;
							BT = Tc;
						}
					};
					for (float S = -75.0f; S <= 90.0f; S += 15.0f)
					{
						for (float In = 0.0f; In <= 60.0f; In += 20.0f)
						{
							for (float Tc = 0.0f; Tc <= 0.76f; Tc += 0.15f)
							{
								Try(S, In, Tc);
							}
						}
					}
					if (Best < 1e8f)
					{
						const float S0 = BS, I0 = BI, T0 = BT;
						for (const float dS : { -7.5f, 0.0f, 7.5f })
						{
							for (const float dI : { -10.0f, 0.0f, 10.0f })
							{
								for (const float dT : { -0.075f, 0.0f, 0.075f })
								{
									Try(S0 + dS, FMath::Max(I0 + dI, 0.0f), FMath::Clamp(T0 + dT, 0.0f, 0.85f));
								}
							}
						}
						SpreadDeg = BS;
						InDeg = BI;
						Set(BT);
						bPlaced = bThumbHeld = true;
					}
					Clearance = 1.0f;
					if (bPlaced)
					{
						UE_LOG(LogTemp, Verbose, TEXT("FitGrip:   %s thumb onto the gun's side: %.1f cm from its place"), bLeft ? TEXT("L") : TEXT("R"), Best);
					}
				}
				if (!bPlaced && bLeft && !Rig->IsHandgun())
				{
					// The support hand's thumb on a long gun lies FORWARD along the gun (a little up): of the ways it is
					// free, the one that points most that way. (By a fixed order it came to stand straight up the
					// flank and over the top, in the sights.)
					// (round a post it goes round the BACK to the fingers' side, as a fist closes on a handle)
					const FVector Want = bPost ? (RigT.GetUnitAxis(EAxis::X) * -0.2f + RigT.GetUnitAxis(EAxis::Y) * 0.9f + RigT.GetUnitAxis(EAxis::Z) * -0.2f).GetSafeNormal()
						: (RigT.GetUnitAxis(EAxis::X) * 0.95f + RigT.GetUnitAxis(EAxis::Z) * 0.2f).GetSafeNormal();
					float Best = -2.0f, BestSpread = 0.0f, BestIn = 0.0f;
					for (float In = 0.0f; In <= 60.0f; In += 15.0f)
					{
						for (float S = -70.0f; S <= 70.0f; S += 10.0f)
						{
							SpreadDeg = S;
							InDeg = In;
							if (Blocked(0))
							{
								continue;
							}
							FVector J[4];
							Pose(J);
							const float Score = static_cast<float>(FVector::DotProduct((J[3] - J[1]).GetSafeNormal(), Want));
							if (Score > Best)
							{
								Best = Score;
								BestSpread = S;
								BestIn = In;
								bPlaced = true;
							}
						}
					}
					SpreadDeg = BestSpread;
					InDeg = BestIn;
				}
				else if (!bPlaced)
				{
					for (const float S : Tries[bPost ? 0 : Side])            // (round a post the thumb goes as round a grip)
					{
						SpreadDeg = S;
						if (!Blocked(0))
						{
							bPlaced = true;
							break;
						}
					}
				}
				if (!bPlaced)
				{
					// free nowhere while straight: partly closed, the first way it comes free
					InDeg = 0.0f;
					for (const float S : Tries[Side])
					{
						for (const float Closed : { 0.25f, 0.5f, 0.75f, 1.0f })
						{
							SpreadDeg = S;
							Set(Closed);
							if (!Blocked(0))
							{
								bPlaced = bThumbHeld = true;
								break;
							}
						}
						if (bPlaced)
						{
							break;
						}
					}
				}
				if (!bPlaced)
				{
					SpreadDeg = 0.0f;
					Set(0.0f);
				}
			}
			bool bOnTrigger = false;
			if (F == 0 && bTrigger)
			{
				// The TRIGGER finger lies on the trigger: of its poses whose first two bones are clear of the gun, the
				// one that brings the pad of its tip nearest the trigger's front face (closed like the others, it lay
				// curled under the guard).
				const FVector Goal = RigT.TransformPosition(TriggerAt);
				auto Clear = [&]()
				{
					FVector J[4];
					Pose(J);
					return !Touches(FMath::Lerp(J[0], J[1], 0.15f), J[1], FingerRadius[0] * Size * 0.8f) && !Touches(J[1], J[2], FingerRadius[0] * Size * 0.72f)
						&& !Touches(J[2], J[3], 0.45f * Size);
				};
				float Best = 1e9f, B0 = 0.0f, B1 = 0.0f, B2 = 0.0f, BL = 0.0f;
				auto Try = [&](float C0, float C1, float C2)
				{
					Curl[0] = C0; Curl[1] = C1; Curl[2] = C2;
					if (!Clear())
					{
						return;
					}
					FVector J[4];
					Pose(J);
					// (and a finger's own way of bending: the middle joint more than the tip, a hard-bent tip on a straight
					// finger read as a claw)
					const float D = static_cast<float>(FVector::Dist(FMath::Lerp(J[2], J[3], 0.6f), Goal)) + 0.03f * FMath::Max(0.0f, C2 - 0.75f * C1)
						+ 0.01f * FMath::Max(0.0f, -C0) + 0.006f * FMath::Abs(LiftDeg);
					if (D < Best)
					{
						Best = D; B0 = C0; B1 = C1; B2 = C2; BL = LiftDeg;
					}
				};
				// (and lifted in the palm's plane, either way: a trigger higher than the knuckles of the hand round a short
				// grip is out of reach of a finger that only closes; the heavy machine gun's guard ran along the straight finger)
				for (const float Lift : { 0.0f, 8.0f, -8.0f, 16.0f, -16.0f, 24.0f, -24.0f })
				{
					LiftDeg = Lift;
					for (float C0 = -10.0f; C0 <= 80.0f; C0 += 10.0f)
					{
						for (float C1 = 0.0f; C1 <= 100.0f; C1 += 12.5f)
						{
							for (float C2 = 0.0f; C2 <= 70.0f; C2 += 14.0f)
							{
								Try(C0, C1, C2);
							}
						}
					}
				}
				LiftDeg = BL;
				if (Best < 1e8f)
				{
					const float A0 = B0, A1 = B1, A2 = B2;
					for (const float D0 : { -5.0f, 0.0f, 5.0f })
					{
						for (const float D1 : { -6.0f, 0.0f, 6.0f })
						{
							for (const float D2 : { -7.0f, 0.0f, 7.0f })
							{
								Try(A0 + D0, FMath::Max(A1 + D1, 0.0f), FMath::Max(A2 + D2, 0.0f));
							}
						}
					}
				}
				if (Best < 3.0f)
				{
					Curl[0] = B0; Curl[1] = B1; Curl[2] = B2; LiftDeg = BL;
					bOnTrigger = bThumbHeld = true;               // (placed: it stays as placed)
					FitFingers[Side].IndexLift = BL;
					UE_LOG(LogTemp, Verbose, TEXT("FitGrip:   R index on the trigger, %.1f cm off its face (curl %.0f %.0f %.0f, lifted %.0f)"), Best, B0, B1, B2, BL);
				}
				else
				{
					Curl[0] = Curl[1] = Curl[2] = 0.0f;
					LiftDeg = 0.0f;
				}
			}
			const bool bStartsInside = Blocked(0) && !bOnTrigger;
			if (!bLeft && F == 0 && bStartsInside)
			{
				bFitIndexInside = true;
			}
			const float Step = 0.035f;
			float T = 0.0f;
			bool bFree = !bStartsInside;
			bool bOpened = bThumbHeld;                               // (a thumb placed partly closed stays as it was placed)
			bAnyContact |= bThumbHeld;
			// Opened BACK at the knuckle until it lies along the gun's side, its two outer joints then closing on their
			// own: only for a finger that comes free NO OTHER WAY (a frame wider than its grip, where closing further
			// only frees it once it has passed through the frame). The fingers that wrap a grip begin in whatever
			// stands ahead of the hand and close past it; opened back first, they came free and never wrapped, and the
			// trigger finger lay straight along the frame instead of on the trigger.
			auto OpenBack = [&]()
			{
				for (float Back = -6.0f; Back >= -24.0f; Back -= 6.0f)
				{
					Curl[0] = Back;
					Curl[1] = Curl[2] = 0.0f;
					if (!Blocked(0))
					{
						return true;
					}
				}
				Curl[0] = 0.0f;
				return false;
			};
			auto CloseOuter = [&]()
			{
				for (int32 K = 1; K < 3; ++K)
				{
					bool bTouched = false;
					for (float A = 3.0f; A <= MaxCurl[F][K]; A += 3.0f)
					{
						const float Keep = Curl[K];
						Curl[K] = A;
						if (Blocked(K))
						{
							Curl[K] = Keep;
							bTouched = true;
							break;
						}
					}
					if (!bTouched)
					{
						Curl[K] = K == 1 ? 45.0f : 28.0f;         // (nothing to close on: bent like a finger at rest)
					}
				}
			};
			for (; !bFree && T <= 1.0f; T += Step)
			{
				Set(T);
				bFree = !Blocked(0);
			}
			if (!bFree && F < 4 && OpenBack())
			{
				bFree = bOpened = bAnyContact = true;
				CloseOuter();
			}
			if (bFree && !bOpened)
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
			UE_LOG(LogTemp, Verbose, TEXT("FitGrip:   %s %s %s spread %.0f in %.0f curl %.0f %.0f %.0f (preset %.0f %.0f %.0f)"), bLeft ? TEXT("L") : TEXT("R"), FingerNames[F],
				bStartsInside ? TEXT("INSIDE") : (bAnyContact ? TEXT("fit") : TEXT("no contact")), SpreadDeg, InDeg, Curl[0], Curl[1], Curl[2],
				FitFingers[Side].Curl[F][0], FitFingers[Side].Curl[F][1], FitFingers[Side].Curl[F][2]);
			FitFingers[Side].Together = Together;
			if (F == 4 && !bStartsInside)
			{
				// the thumb keeps where it came free even with nothing to press on (its preset would put it back through)
				FitFingers[Side].ThumbSpread = SpreadDeg;
				FitFingers[Side].ThumbIn = InDeg;
				if (!bAnyContact)
				{
					// free, with nothing to press on: closed over what the fingers hold (left straight, it stands out)
					Set(bLeft ? 0.35f : 0.6f);
					bAnyContact = true;
				}
			}
			if (F < 4 && bFree && !bAnyContact)
			{
				// free, with nothing to close on: closed like a hand that holds (its preset was written for another gun
				// and may lie in this one); the trigger finger stays long
				Set(!bLeft && F == 0 ? 0.3f : 0.8f);
				bAnyContact = true;
			}
			if (bAnyContact)
			{
				// the trigger finger rests on the trigger: it never closes harder than its preset (unless that is the only
				// way it is clear of the gun)
				for (int32 K = 0; K < 3; ++K)
				{
					const float Preset = FitFingers[Side].Curl[F][K];
					FitFingers[Side].Curl[F][K] = (!bLeft && F == 0 && !bStartsInside && !bOnTrigger) ? FMath::Min(Curl[K], Preset + 30.0f) : Curl[K];
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

float USOLocomotionAnimInstance::DebugSwing[2][5] = {};

FString USOLocomotionAnimInstance::FHoldReport::ToString() const
{
	FString Out;
	for (int32 Side = 0; Side < 2; ++Side)
	{
		Out += FString::Printf(TEXT("%s%s hand: wrist %.0f deg, reach %.2f, %d of %d bones in the gun [%s], palm %.1f cm at (%.1f %.1f %.1f), forearm (%.2f %.2f %.2f) hand (%.2f %.2f %.2f) palm (%.2f %.2f %.2f)"),
			Side ? TEXT(" | ") : TEXT(""), Side ? TEXT("support") : TEXT("firing"), WristBend[Side], Reach[Side], Inside[Side], Bones[Side], *Which[Side], PalmGap[Side],
			PalmAt[Side].X, PalmAt[Side].Y, PalmAt[Side].Z,
			Forearm[Side].X, Forearm[Side].Y, Forearm[Side].Z, Along[Side].X, Along[Side].Y, Along[Side].Z, Palm[Side].X, Palm[Side].Y, Palm[Side].Z);
	}
	return Out;
}

USOLocomotionAnimInstance::FHoldReport USOLocomotionAnimInstance::MeasureHold(const USOGunRigComponent* Rig, const USkeletalMeshComponent* Mesh)
{
	FHoldReport Report;
	if (!Rig || !Mesh || !Rig->IsBuilt() || !Rig->GetGunSpace())
	{
		return Report;
	}
	// (the gun's meshes answer shape queries for the length of the measure: they collide with nothing otherwise)
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
	const float Size = static_cast<float>(Mesh->GetComponentScale().X);
	static const TCHAR* FingerNames[5] = { TEXT("index"), TEXT("middle"), TEXT("ring"), TEXT("pinky"), TEXT("thumb") };
	for (int32 Side = 0; Side < 2; ++Side)
	{
		const bool bLeft = Side == 1;
		const TCHAR* Sfx = bLeft ? TEXT("L") : TEXT("R");
		const FName HandName(*FString::Printf(TEXT("hand_%s"), Sfx));
		if (Mesh->GetBoneIndex(HandName) == INDEX_NONE)
		{
			continue;
		}
		auto Bone = [&](const TCHAR* Name, int32 K) { return FName(*FString::Printf(TEXT("%s_0%d_%s"), Name, K, Sfx)); };
		const FVector Hand = Mesh->GetBoneLocation(HandName);
		const FVector Elbow = Mesh->GetBoneLocation(Mesh->GetParentBone(HandName));
		if (Mesh->GetBoneIndex(Bone(TEXT("middle"), 1)) == INDEX_NONE)
		{
			continue;
		}
		// the hand's own frame from its bones: along it (wrist to the middle knuckle), to the thumb's side, out of the palm
		const FVector Along = (Mesh->GetBoneLocation(Bone(TEXT("middle"), 1)) - Hand).GetSafeNormal();
		const FVector Thumb = (Mesh->GetBoneLocation(Bone(TEXT("index"), 1)) - Mesh->GetBoneLocation(Bone(TEXT("pinky"), 1))).GetSafeNormal();
		const FVector Palm = FSOHandGrip::PalmNormal(FSOHandGrip::MakeBasis(Along, Thumb, bLeft), bLeft);
		const FTransform RigT = Rig->GetComponentTransform();
		Report.Forearm[Side] = RigT.InverseTransformVectorNoScale((Hand - Elbow).GetSafeNormal());
		Report.Along[Side] = RigT.InverseTransformVectorNoScale(Along);
		Report.Palm[Side] = RigT.InverseTransformVectorNoScale(Palm);
		Report.PalmAt[Side] = RigT.InverseTransformPosition(Hand + Along * 5.0f * Size);
		if (const FName Upper = Mesh->GetParentBone(Mesh->GetParentBone(HandName)); !Upper.IsNone())
		{
			const FVector Shoulder = Mesh->GetBoneLocation(Upper);
			Report.ShoulderAt[Side] = RigT.InverseTransformPosition(Shoulder);
			Report.Reach[Side] = static_cast<float>(FVector::Dist(Shoulder, Hand) / FMath::Max(FVector::Dist(Shoulder, Elbow) + FVector::Dist(Elbow, Hand), 1.0));
		}
		Report.WristBend[Side] = FMath::RadiansToDegrees(FMath::Acos(FMath::Clamp(static_cast<float>(FVector::DotProduct((Hand - Elbow).GetSafeNormal(), Along)), -1.0f, 1.0f)));
		// the palm: its skin lies 1.3 cm off the bones, its middle 5 cm from the wrist
		// (the palm runs on to the root of the fingers: a handle held in the fist lies there, ahead of the middle, so
		// the palm is measured at its middle and 2.5 cm on, and the nearer of the two counts)
		float Best = 99.0f;
		FHitResult Hit;
		FCollisionQueryParams Params(SCENE_QUERY_STAT(SOMeasureHold), true);
		for (const float On : { 5.0f, 7.5f })
		{
			const FVector Centre = Hand + Along * On * Size;
			float Here = 99.0f;
			for (UStaticMeshComponent* Part : Parts)
			{
				if (Part->LineTraceComponent(Hit, Centre - Palm * 4.0f * Size, Centre + Palm * 8.0f * Size, Params))
				{
					Here = FMath::Min(Here, static_cast<float>(FVector::DotProduct(Hit.ImpactPoint - Centre, Palm)) / Size - 1.3f);
				}
			}
			if (FMath::Abs(Here) < FMath::Abs(Best))
			{
				Best = Here;
			}
		}
		Report.PalmGap[Side] = Best;
		// the bones: each finger's three and its tip, and the palm's own (wrist to each knuckle)
		for (int32 F = 0; F < 5; ++F)
		{
			FVector J[4];
			bool bChain = true;
			for (int32 K = 0; K < 3; ++K)
			{
				bChain &= Mesh->GetBoneIndex(Bone(FingerNames[F], K + 1)) != INDEX_NONE;
				J[K] = bChain ? Mesh->GetBoneLocation(Bone(FingerNames[F], K + 1)) : FVector::ZeroVector;
			}
			if (!bChain)
			{
				continue;
			}
			// (the tip runs on from the last joint the way that bone turns: carried straight on from the middle bone, a
			// bent tip was measured as if it pointed into the gun)
			const FQuat Middle = Mesh->GetBoneQuaternion(Bone(FingerNames[F], 2)), Last = Mesh->GetBoneQuaternion(Bone(FingerNames[F], 3));
			J[3] = J[2] + (Last * Middle.Inverse()).RotateVector(J[2] - J[1]) * 0.8f;
			const float Core = 0.3f * Size;
			auto Count = [&](const FVector& A, const FVector& B, int32 K)
			{
				++Report.Bones[Side];
				if (Touches(A, B, Core))
				{
					++Report.Inside[Side];
					Report.Which[Side] += FString::Printf(TEXT("%s%d "), FingerNames[F], K);
				}
			};
			if (F < 4)
			{
				Count(FMath::Lerp(Hand, J[0], 0.35f), J[0], 0);      // the palm's own bone to this knuckle
			}
			for (int32 K = F == 4 ? 1 : 0; K < 3; ++K)
			{
				Count(K == 0 ? FMath::Lerp(J[0], J[1], 0.4f) : J[K], J[K + 1], K + 1);
			}
		}
	}
	for (UStaticMeshComponent* Part : Parts)
	{
		Part->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	}
	return Report;
}

void USOLocomotionAnimInstance::UpdateBodyMotion(const ACharacter* Character, float DeltaSeconds)
{
	const USkeletalMeshComponent* Mesh = GetSkelMeshComponent();
	const float Dt = FMath::Max(DeltaSeconds, 1e-4f);
	bBodyMotion = Character && Mesh && !bDead;
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
	const ASOCombatCharacter* Combat = Cast<ASOCombatCharacter>(Character);
	if (Combat && Combat->IsDisplayOnly())
	{
		// the armoury's stand-in is turned on a turntable: the whole body turns with it (the planted feet and the
		// stepped turn twisted it against the drag, the head holding its heading: the owner's "chicken")
		StandYaw = 0.0f;
		bTurning = false;
	}
	else if (bStanding && !bTurning)
	{
		// (in the combat stance the feet step round sooner: a split stance left planted under an aim that turned 30
		// degrees stood with its feet in line with the aim, and from behind the legs read as crossed)
		const float StepAt = Stance.bPlayer ? FMath::Lerp(TurnInPlaceAngle, FMath::Min(TurnInPlaceAngle, Stance.TurnStep), Stance.Ready * StanceStill) : TurnInPlaceAngle;
		StandYaw = FMath::Clamp(StandYaw - Turned, -StepAt - 12.0f, StepAt + 12.0f);
		bTurning = FMath::Abs(StandYaw) > StepAt;
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
	SOSpring::Step(Compress, CompressVel, 0.0f, FMath::Sqrt(260.0f), 0.75f, Dt);
	Compress = FMath::Max(Compress, 0.0f);
	WantPitch -= Compress * 0.6f;
	LeanRoll = FMath::FInterpTo(LeanRoll, WantRoll, Dt, bMantling ? 14.0f : 8.0f);
	LeanPitch = FMath::FInterpTo(LeanPitch, WantPitch, Dt, bMantling ? 14.0f : 8.0f);
	// a blow's knock comes back by itself; reeling holds the trunk bowed and swaying
	FlinchRoll = FMath::FInterpTo(FlinchRoll, 0.0f, Dt, 5.5f);
	FlinchPitch = FMath::FInterpTo(FlinchPitch, 0.0f, Dt, 5.5f);
	FlinchTwist = FMath::FInterpTo(FlinchTwist, 0.0f, Dt, 5.5f);
	HeadKickPitch = FMath::FInterpTo(HeadKickPitch, 0.0f, Dt, 6.5f);
	HeadKickYaw = FMath::FInterpTo(HeadKickYaw, 0.0f, Dt, 6.5f);
	FlinchDip = FMath::FInterpTo(FlinchDip, 0.0f, Dt, 5.0f);
	ReelBlend = FMath::FInterpTo(ReelBlend, bReeling ? 1.0f : 0.0f, Dt, 6.0f);
	ReelClock += Dt;

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
	// The combat stance's body (FSOStance): a gun in the hands, the knees bend (the hips lower: a little relaxed, more at
	// the ready) and, standing, the support foot goes forward, the feet apart, the toes out, the hips turned; on the ground
	// only, never crouched, at a sprint or in a traversal, and eased out as the walk becomes a run (the gait's own feet
	// take over).
	{
		const bool bStanceBody = Stance.bPlayer && bHold && !bCarried && !bInAir && !bSliding && !bMantling && !bCrouched && !bDodging;
		const float Moving = 1.0f - FMath::SmoothStep(260.0f, 520.0f, Speed);
		const float Still = 1.0f - FMath::SmoothStep(40.0f, 160.0f, Speed);
		StanceBody = FMath::FInterpTo(StanceBody, bStanceBody ? Moving : 0.0f, Dt, 6.0f);
		StanceStill = FMath::FInterpTo(StanceStill, bStanceBody ? Still : 0.0f, Dt, 5.0f);
		PelvisDrop += Stance.Knees * StanceBody;
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
	// (this frame's state arrives at the end of NativeUpdateAnimation, which the engine runs after this: CopyFrom)
}

void FSOLocomotionProxy::CopyFrom(const USOLocomotionAnimInstance* Instance)
{
	const UAnimSequenceBase* ClipList[Count] = { Instance->Clips.Idle, Instance->Clips.Walk, Instance->Clips.Run, Instance->Clips.Jump,
		Instance->Clips.Death, Instance->ActiveAttack ? Instance->ActiveAttack.Get() : Instance->Clips.Attack.Get(), Instance->Clips.Slide, Instance->FidgetClip,
		Instance->Clips.Stroll, Instance->Clips.Land, Instance->Clips.Vault, Instance->Clips.Mantle, Instance->Clips.Climb,
		Instance->Clips.Crouch, Instance->Clips.CrouchWalk, Instance->Clips.Stop, Instance->GetActiveDodge() };
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
	bHandgunHold = Instance->bHandgunHold;
	bHideHead = Instance->bHideHead;
	bCarried = Instance->bCarried;
	bHeadFree = Instance->bHeadFree;
	AimPitch = Instance->AimPitch;
	Blade = Instance->Blade;
	Lean = Instance->Lean;
	HeadCant = Instance->HeadCant;
	Stance = Instance->Stance;
	StanceBody = Instance->StanceBody;
	StanceStill = Instance->StanceStill;
	RightTarget = Instance->RightTarget;
	LeftTarget = Instance->LeftTarget;
	bSupportOnPost = Instance->IsSupportOnPost();
	bSnugHold = Instance->bSnugHold;
	RightFingers = Instance->RightFingers;
	LeftFingers = Instance->LeftFingers;
	GunAxis = Instance->GunAxis;
	bBodyMotion = Instance->bBodyMotion;
	WarpYaw = Instance->WarpYaw;
	StandYaw = Instance->GetStandYaw();
	MaxWaistTwist = Instance->MaxWaistTwist;
	TrunkHalfWidth = Instance->TrunkHalfWidth;
	TrunkHalfDepth = Instance->TrunkHalfDepth;
	HoldAlpha = Instance->GetHoldAlpha();
	LeanRoll = Instance->LeanRoll + Instance->FlinchRoll + Instance->ReelBlend * 7.0f * FMath::Sin(Instance->ReelClock * 4.3f);
	LeanPitch = Instance->LeanPitch + Instance->FlinchPitch - Instance->ReelBlend * (18.0f + 5.0f * FMath::Sin(Instance->ReelClock * 6.1f));
	PelvisDrop = Instance->PelvisDrop + Instance->FlinchDip + Instance->ReelBlend * 7.0f;
	FlinchTwist = Instance->FlinchTwist;
	HeadKickPitch = Instance->HeadKickPitch;
	HeadKickYaw = Instance->HeadKickYaw;
	FootOffset[0] = Instance->FootOffset[0];
	FootOffset[1] = Instance->FootOffset[1];
	TurnLift[0] = Instance->GetTurnLift(0);
	TurnLift[1] = Instance->GetTurnLift(1);
	FootIKAlpha = Instance->FootIKAlpha;
	const bool bBlow = Instance->MeleeBlowTime >= 0.0f && Instance->MeleeBlow;
	MeleeClip = bBlow ? Instance->MeleeBlow.Get() : Instance->MeleeGuard.Get();
	bMeleeLoop = !bBlow;
	MeleeTime = bBlow ? Instance->MeleeBlowTime : (Instance->MeleeGuardHold >= 0.0f ? Instance->MeleeGuardHold : Instance->MeleeGuardTime);
	if (MeleeClip && bMeleeLoop && MeleeClip->GetPlayLength() > 0.0f)
	{
		MeleeTime = FMath::Fmod(MeleeTime, MeleeClip->GetPlayLength());
	}
	else if (MeleeClip)
	{
		MeleeTime = FMath::Min(MeleeTime, MeleeClip->GetPlayLength() - 1e-3f);
	}
	MeleeWeight = MeleeClip ? Instance->MeleeWeight : 0.0f;
	MeleeLegs = Instance->MeleeLegs;
	MeleePitch = Instance->MeleePitch;
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
		ApplyMelee(Output);
		ApplyBody(Output);
		ApplyHold(Output);
		ApplyHit(Output);
		HideHead(Output);
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
	ApplyMelee(Output);
	ApplyBody(Output);
	ApplyHold(Output);
	ApplyHit(Output);
	HideHead(Output);
	return true;
}

void FSOLocomotionProxy::HideHead(FPoseContext& Output) const
{
	// First person is this body's own eyes (the owner, 2026-11-23: one model, one camera): the head the camera sits in
	// shrinks into its joint, and with it what it carries (the eyes, the hair, a helmet: their pieces follow this pose).
	// Only on its own player's machine: everyone else sees the whole body.
	if (!bHideHead)
	{
		return;
	}
	const FBoneContainer& Bones = Output.Pose.GetBoneContainer();
	const int32 MeshIndex = Bones.GetPoseBoneIndexForBoneName(TEXT("head"));
	if (MeshIndex != INDEX_NONE)
	{
		const FCompactPoseBoneIndex Head = Bones.MakeCompactPoseIndex(FMeshPoseBoneIndex(MeshIndex));
		if (Head.IsValid())
		{
			Output.Pose[Head].SetScale3D(FVector(0.01f));
		}
	}
}

void FSOLocomotionProxy::ApplyMelee(FPoseContext& Output) const
{
	if (!MeleeClip || MeleeWeight <= 0.01f)
	{
		return;
	}
	FCompactPose& Pose = Output.Pose;
	const FBoneContainer& Bones = Pose.GetBoneContainer();
	FCompactPose Upper;
	Upper.SetBoneContainer(&Bones);
	FBlendedCurve Curve;
	Curve.InitFrom(Output.Curve);
	UE::Anim::FStackAttributeContainer Attributes;
	FAnimationPoseData Data(Upper, Curve, Attributes);
	MeleeClip->GetAnimationPose(Data, FAnimExtractContext(static_cast<double>(MeleeTime), false, {}, bMeleeLoop));

	// The upper body is the spine and everything under it (compact poses list parents before children); below it the
	// clip takes over only as far as the body is standing still.
	const int32 SpineMesh = Bones.GetPoseBoneIndexForBoneName(FName(TEXT("spine")));
	const FCompactPoseBoneIndex Spine = SpineMesh == INDEX_NONE ? FCompactPoseBoneIndex(INDEX_NONE) : Bones.MakeCompactPoseIndex(FMeshPoseBoneIndex(SpineMesh));
	TArray<bool, TInlineAllocator<160>> IsUpper;
	IsUpper.SetNumZeroed(Pose.GetNumBones());
	for (FCompactPoseBoneIndex Index : Pose.ForEachBoneIndex())
	{
		const FCompactPoseBoneIndex P = Bones.GetParentBoneIndex(Index);
		const bool bUpper = Index == Spine || (P.IsValid() && IsUpper[P.GetInt()]);
		IsUpper[Index.GetInt()] = bUpper;
		const float W = MeleeWeight * (bUpper ? 1.0f : MeleeLegs);
		if (W <= 0.001f)
		{
			continue;
		}
		FTransform& T = Pose[Index];
		const FTransform& U = Upper[Index];
		T.SetRotation(FQuat::Slerp(T.GetRotation(), U.GetRotation(), W).GetNormalized());
		T.SetTranslation(FMath::Lerp(T.GetTranslation(), U.GetTranslation(), W));
	}

	// Where the eyes look the blows go: the trunk pitched with the aim (about the body's own left axis; the arms of the
	// first-person copy hang from the chest, so it takes the whole pitch there to keep the fists in the view).
	if (FMath::Abs(MeleePitch) < 0.5f)
	{
		return;
	}
	const FQuat Pitch(FVector(1.0f, 0.0f, 0.0f), FMath::DegreesToRadians(MeleePitch * MeleeWeight));
	auto Turn = [&](const TCHAR* Name, float Share)
	{
		const int32 MeshIndex = Bones.GetPoseBoneIndexForBoneName(FName(Name));
		const FCompactPoseBoneIndex Bone = MeshIndex == INDEX_NONE ? FCompactPoseBoneIndex(INDEX_NONE) : Bones.MakeCompactPoseIndex(FMeshPoseBoneIndex(MeshIndex));
		if (!Bone.IsValid())
		{
			return;
		}
		FQuat Above = FQuat::Identity;
		for (FCompactPoseBoneIndex P = Bones.GetParentBoneIndex(Bone); P.IsValid(); P = Bones.GetParentBoneIndex(P))
		{
			Above = Pose[P].GetRotation() * Above;
		}
		const FQuat Part = FQuat::Slerp(FQuat::Identity, Pitch, Share);
		Pose[Bone].SetRotation((Above.Inverse() * Part * Above * Pose[Bone].GetRotation()).GetNormalized());
	};
	{
		Turn(TEXT("spine"), 0.3f);
		Turn(TEXT("chest"), 0.35f);
		Turn(TEXT("neck"), 0.15f);
		Turn(TEXT("head"), 0.2f);
	}
}

void FSOLocomotionProxy::ApplyHit(FPoseContext& Output) const
{
	if (!bBodyMotion || FMath::Abs(HeadKickPitch) + FMath::Abs(HeadKickYaw) <= 0.05f)
	{
		return;
	}
	FCompactPose& Pose = Output.Pose;
	const FBoneContainer& Bones = Pose.GetBoneContainer();
	// Component space: +Y forward, +Z up, +X the character's left.
	const FQuat Kick = FQuat(FVector::UpVector, FMath::DegreesToRadians(HeadKickYaw)) * FQuat(FVector(1.0f, 0.0f, 0.0f), FMath::DegreesToRadians(HeadKickPitch));
	auto Turn = [&](const TCHAR* Name, float Share)
	{
		const int32 MeshIndex = Bones.GetPoseBoneIndexForBoneName(FName(Name));
		if (MeshIndex == INDEX_NONE)
		{
			return;
		}
		const FCompactPoseBoneIndex Bone = Bones.MakeCompactPoseIndex(FMeshPoseBoneIndex(MeshIndex));
		if (!Bone.IsValid())
		{
			return;
		}
		// the parent's rotation in component space: the turn is about the body's axes, not the bone's own
		FQuat Above = FQuat::Identity;
		for (FCompactPoseBoneIndex P = Bones.GetParentBoneIndex(Bone); P.IsValid(); P = Bones.GetParentBoneIndex(P))
		{
			Above = Pose[P].GetRotation() * Above;
		}
		const FQuat Part = FQuat::Slerp(FQuat::Identity, Kick, Share);
		Pose[Bone].SetRotation((Above.Inverse() * Part * Above * Pose[Bone].GetRotation()).GetNormalized());
	};
	Turn(TEXT("neck"), 0.4f);
	Turn(TEXT("head"), 0.6f);
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

	// 2b. A hit: a shoulder driven back turns the chest.
	if (FMath::Abs(FlinchTwist) > 0.05f)
	{
		const float Twist = FMath::DegreesToRadians(FlinchTwist);
		if (Spine != INDEX_NONE)
		{
			Turn(Spine, FQuat(Up, Twist * 0.4f));
		}
		if (Chest != INDEX_NONE)
		{
			Turn(Chest, FQuat(Up, Twist * 0.6f));
		}
	}
	// (the head's own kick is put on last of all: ApplyHit)

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

	// 2c. The combat stance's feet (standing with a gun in the hands, FSOStance): the support (left) foot forward and the
	//     firing foot back along the way the legs face, both further apart, the toes turned out; the legs' IK below puts
	//     them there. (In the legs' own frame: a planted stance under an aim that turned on the spot stays the same
	//     stance.)
	const FQuat LegTurn(Up, FMath::DegreesToRadians(Total));
	const FVector Heading = LegTurn.RotateVector(Fwd), Lateral = LegTurn.RotateVector(Side);   // the legs' forward and left
	const float StanceFeet = Stance.bPlayer ? StanceStill * StanceBody : 0.0f;
	const float StanceStagger = Stance.Stagger * StanceFeet, StanceWidth = Stance.Width * StanceFeet;
	float ToeTurn[2] = { 0.0f, 0.0f };
	if (StanceFeet > 0.001f)
	{
		if (bLeg[0])
		{
			FootWanted[0].AddToTranslation(Heading * (StanceStagger * 0.55f) + Lateral * (StanceWidth * 0.5f));
		}
		if (bLeg[1])
		{
			FootWanted[1].AddToTranslation(-Heading * (StanceStagger * 0.45f) - Lateral * (StanceWidth * 0.5f));
		}
		// each foot turned about its ankle, the toes out (+X is the left: the left foot turns that way)
		ToeTurn[0] = -FMath::DegreesToRadians(Stance.ToeOut[0] * StanceFeet);
		ToeTurn[1] = FMath::DegreesToRadians(Stance.ToeOut[1] * StanceFeet);
		for (int32 i = 0; i < 2; ++i)
		{
			if (bLeg[i])
			{
				FootWanted[i].SetRotation(FQuat(Up, ToeTurn[i]) * FootWanted[i].GetRotation());
			}
		}
	}

	// 3. The hips sink (landing, or so the lower foot reaches a step below).
	if (PelvisDrop > 0.01f)
	{
		FTransform H = CS[Hips];
		H.AddToTranslation(-Up * PelvisDrop);
		SetCS(Hips, H);
	}
	// The stance turns the hips with the support foot forward (the support hip ahead), the spine turning back so the
	// chest keeps the hold's own blade (USOLocomotionAnimInstance::Blade); the legs' IK keeps the feet where they stand.
	if (const float HipTurn = FMath::DegreesToRadians(Stance.Hips * StanceFeet); FMath::Abs(HipTurn) > 1e-3f)
	{
		Turn(Hips, FQuat(Up, HipTurn));
		if (Spine != INDEX_NONE)
		{
			Turn(Spine, FQuat(Up, -HipTurn));
		}
	}

	// 4. Two-bone leg IK onto the wanted feet. The knee keeps the side the animation bent it to, but a knee only bends
	//    one way: ahead of the line from the hip to the ankle, in the leg's own heading. An almost straight animated
	//    leg says nothing about that side (its offset from the line is a few millimetres of noise, and it flipped the
	//    knee backward and through the floor when the hips came down), so the leg's forward is always part of it and
	//    whatever points behind the line is taken out.
	// (one leg onto an ankle and a foot's turn: used below for the wanted feet, and again where an ankle would bend past
	// a human's, 5.)
	auto SolveLeg = [&](int32 i, const FVector& AnkleAt, const FQuat& FootTurn)
	{
		{
			const int32 Upper = Leg[i][0], Lower = Leg[i][1], Foot = Leg[i][2];
			const FVector S = CS[Upper].GetLocation();
			const FVector Knee0 = CS[Lower].GetLocation();
			const float L1 = FVector::Dist(S, Knee0);
			const float L2 = FVector::Dist(Knee0, CS[Foot].GetLocation());
			const FVector ToTarget = AnkleAt - S;
			const FVector Dir = ToTarget.GetSafeNormal(1e-4f, -Up);
			const float D = FMath::Clamp(static_cast<float>(ToTarget.Size()), FMath::Abs(L1 - L2) + 0.5f, (L1 + L2) * 0.999f);
			const float Along = (L1 * L1 - L2 * L2 + D * D) / (2.0f * D);
			const float Height = FMath::Sqrt(FMath::Max(L1 * L1 - Along * Along, 0.0f));
			FVector Bend = (Knee0 - S) - Dir * FVector::DotProduct(Knee0 - S, Dir);      // cm off the line, as animated
			// (the leg's forward is the way its toes point: the stance turns them out)
			const FVector LegFwd = FQuat(Up, ToeTurn[i]).RotateVector(Heading);
			const FVector Ahead = (LegFwd - Dir * FVector::DotProduct(LegFwd, Dir)).GetSafeNormal(1e-4f, Fwd);
			const float Behind = static_cast<float>(FVector::DotProduct(Bend, Ahead));
			if (Behind < 0.0f)
			{
				Bend -= Ahead * Behind;
			}
			// A player standing with a gun: the knee goes over the toes and a little out, never in toward the other leg. The
			// clip's knee sits a little in (the idle's knees 22 cm apart over ankles 26), and the stance's deeper bend carried
			// that side 16 cm off the line: knock knees, the legs an X from behind (the owner, 2026-11-23: "the player legs
			// are completely wrong and crossed").
			if (StanceFeet > 0.001f)
			{
				const FVector Outward = i == 0 ? Lateral : -Lateral;
				const FVector OutAcross = (Outward - Dir * FVector::DotProduct(Outward, Dir)).GetSafeNormal(1e-4f, Outward);
				const float OutNow = static_cast<float>(FVector::DotProduct(Bend, OutAcross));
				Bend += OutAcross * ((OutNow < 0.0f ? -OutNow : 0.0f) + Stance.KneeOut) * StanceFeet;
			}
			Bend = (Bend + Ahead * KneeAhead).GetSafeNormal(1e-4f, Ahead);
			const FVector Knee = S + Dir * Along + Bend * Height;
			const FVector Ankle = S + Dir * D;
			Turn(Upper, FQuat::FindBetweenNormals((CS[Lower].GetLocation() - S).GetSafeNormal(), (Knee - S).GetSafeNormal()));
			const FVector E = CS[Lower].GetLocation();
			Turn(Lower, FQuat::FindBetweenNormals((CS[Foot].GetLocation() - E).GetSafeNormal(), (Ankle - E).GetSafeNormal()));
			SetCS(Foot, FTransform(FootTurn, CS[Foot].GetLocation(), CS[Foot].GetScale3D()));
		}
	};
	if (PelvisDrop > 0.01f || FootIKAlpha > 0.01f || StanceFeet > 0.001f)
	{
		for (int32 i = 0; i < 2; ++i)
		{
			if (bLeg[i])
			{
				SolveLeg(i, FootWanted[i].GetLocation(), FootWanted[i].GetRotation());
			}
		}
	}

	// 5. Every joint as a human's (the owner, 2026-11-23: "the player should not be bending any part of their body in a
	//    way a normal human cant or in a way harmful to a humans"): an ankle draws the toes up toward the shin some 35
	//    degrees and points them some 55. What asks more (a crouch, a run's swing, the stance's deep knees: the clips
	//    reached 74 degrees up) is met the way a body meets it: a planted foot lifts its heel, turning about the ball of
	//    the foot, and the leg reaches the ankle raised; a foot off the ground turns about its ankle. (A player's body:
	//    the Sarketh walk on their toes.)
	if (bHeadFree)
	{
		// (degrees between the way up the shin and the way the foot points: 90 standing)
		constexpr float MinAnkle = 55.0f, MaxAnkle = 145.0f;
		for (int32 i = 0; i < 2; ++i)
		{
			if (!bLeg[i])
			{
				continue;
			}
			const int32 Lower = Leg[i][1], Foot = Leg[i][2];
			// the foot's forward and up at rest, in its own frame; its ankle's standing height
			FTransform RestFoot = Pose.GetRefPose(FCompactPoseBoneIndex(Foot));
			for (int32 P = Parent[Foot]; P != INDEX_NONE; P = Parent[P])
			{
				RestFoot = RestFoot * Pose.GetRefPose(FCompactPoseBoneIndex(P));
			}
			const FVector ToesRest = RestFoot.GetRotation().UnrotateVector(Fwd), UpRest = RestFoot.GetRotation().UnrotateVector(Up);
			const bool bPlanted = CS[Foot].GetLocation().Z < RestFoot.GetLocation().Z + 4.0f;
			for (int32 Pass = 0; Pass < 3; ++Pass)
			{
				const FVector Ankle = CS[Foot].GetLocation();
				const FVector UpShin = (CS[Lower].GetLocation() - Ankle).GetSafeNormal();
				const FVector Toes = CS[Foot].GetRotation().RotateVector(ToesRest).GetSafeNormal();
				const float Angle = static_cast<float>(FMath::Acos(FMath::Clamp(FVector::DotProduct(UpShin, Toes), -1.0, 1.0)));
				const float Need = Angle < FMath::DegreesToRadians(MinAnkle) ? FMath::DegreesToRadians(MinAnkle) - Angle
					: (Angle > FMath::DegreesToRadians(MaxAnkle) ? FMath::DegreesToRadians(MaxAnkle) - Angle : 0.0f);
				const FVector Axis = FVector::CrossProduct(UpShin, Toes).GetSafeNormal();
				if (FMath::Abs(Need) < FMath::DegreesToRadians(0.5f) || Axis.IsNearlyZero())
				{
					break;
				}
				const FQuat Turned(Axis, Need);          // (+: the toes away from the shin)
				if (bPlanted && Need > 0.0f)
				{
					// the heel lifts: the foot turns about the ball of the foot, a hand's breadth ahead of the ankle on the floor
					const FVector FootUp = CS[Foot].GetRotation().RotateVector(UpRest).GetSafeNormal();
					const FVector Ball = Ankle + Toes * 13.0f - FootUp * 7.0f;
					SolveLeg(i, Ball + Turned.RotateVector(Ankle - Ball), Turned * CS[Foot].GetRotation());
				}
				else
				{
					SetCS(Foot, FTransform(Turned * CS[Foot].GetRotation(), Ankle, CS[Foot].GetScale3D()));
				}
			}
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
	const int32 Hips = Find(TEXT("hips"));
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
	TArray<FTransform, TInlineAllocator<64>> Local, CS, RefCS, RefLocal;
	Parent.SetNum(Num);
	Local.SetNum(Num);
	CS.SetNum(Num);
	RefCS.SetNum(Num);
	RefLocal.SetNum(Num);
	for (FCompactPoseBoneIndex Index : Pose.ForEachBoneIndex())
	{
		const int32 I = Index.GetInt();
		const FCompactPoseBoneIndex P = Bones.GetParentBoneIndex(Index);
		Parent[I] = P.IsValid() ? P.GetInt() : INDEX_NONE;
		Local[I] = Pose[Index];
		CS[I] = Parent[I] == INDEX_NONE ? Local[I] : Local[I] * CS[Parent[I]];
		const FTransform Ref = Pose.GetRefPose(Index);
		RefLocal[I] = Ref;
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

	// 1. Stance: the torso follows the aim pitch (60 %), leans into the gun and turns the off shoulder forward.
	// (the trunk's share of the pitch stops at a lean: looking straight down the body folded 56 degrees at the waist
	// and the gun pointed down along it with the hands at the hips; a man looking at his feet bends his neck and
	// leans a little, the gun comes down in front of him instead: USOViewmodelComponent::HoldTransform. Every bend a
	// normal amount, the owner, 2026-11-23: "head/arms/legs/body bends a normal amount not crazy": at 70 % of up to 57
	// degrees the trunk leaned back 40 looking up.)
	// On the sights a long gun stays shouldered whatever the pitch (USOViewmodelComponent: the stock comes off the
	// shoulder looking down only off the sights), so the trunk BOWS with a downward aim, from the lower back and the
	// chest, as a body bends to aim at the ground: up to 85 % of it, down to 70 degrees (the chest's forward bend on the
	// hips stays inside a body's 80). Held at 60 % of 40 with the gun on the eye's line, the firing elbow went into the
	// chest and the wrist bent past 120 (the owner, 2026-11-23: "looking down ... the right arm is basically gone and
	// moved into the body").
	const float Bow = Stance.bPlayer && !bHandgunHold && AimPitch < 0.0f ? FMath::Clamp(Stance.Aim, 0.0f, 1.0f) : 0.0f;
	const float StancePitch = FMath::DegreesToRadians(FMath::Clamp(AimPitch, FMath::Lerp(-40.0f, -70.0f, Bow), 45.0f));
	const float SpineShare = FMath::Lerp(0.25f, 0.4f, Bow), ChestShare = FMath::Lerp(0.35f, 0.55f, Bow);
	if (Spine != INDEX_NONE)
	{
		Turn(Spine, FQuat(Up, BladeRad * 0.4f) * FQuat(Side, StancePitch * SpineShare - LeanRad * 0.5f));
	}
	if (Chest != INDEX_NONE)
	{
		Turn(Chest, FQuat(Up, BladeRad * 0.6f) * FQuat(Side, StancePitch * ChestShare - LeanRad * 0.5f));
	}
	const float TrunkPitch = StancePitch * (SpineShare + ChestShare) - LeanRad;     // (what the trunk took of the aim's pitch, up +)
	// 2. The head looks along the aim: neck and head share the aim pitch ON TOP of what the clip gave them (the
	//    idle's breathing, a glance, a fidget's turn), about their own pivots. Set to the rest facing instead, the
	//    head stood dead still over a body that breathed and shifted (the owner, 2026-11-21, on the armoury's
	//    stand-in: "the head stays still like a chicken"). The trunk's stance (1.) carries under it unchanged.
	if (Neck != INDEX_NONE)
	{
		// aiming a long gun: the head cants toward the right shoulder and dips onto the stock (cheek weld)
		const float Cant = FMath::DegreesToRadians(HeadCant);
		const FQuat Weld = FQuat(FVector(0.0f, 1.0f, 0.0f), -Cant) * FQuat(Side, -Cant * 0.7f);
		if (bHeadFree)
		{
			// (the head stays on the target over a trunk bladed to the gun: turned with the chest it looked off to the side)
			if (Stance.bPlayer && FMath::Abs(BladeRad) > 1e-3f)
			{
				Turn(Neck, FQuat(Up, -BladeRad * 0.45f));
				if (HeadBone != INDEX_NONE)
				{
					Turn(HeadBone, FQuat(Up, -BladeRad * 0.55f));
				}
			}
			// (the neck and the head take what the trunk did not, within what a neck does: they took the whole aim on top
			// of the trunk's share, and looking 60 degrees up the face pointed 100 degrees up, past the sky)
			const float HeadPitch = FMath::Clamp(Pitch - TrunkPitch, FMath::DegreesToRadians(-55.0f), FMath::DegreesToRadians(50.0f));
			Turn(Neck, FQuat(Side, HeadPitch * 0.4f));
			if (HeadBone != INDEX_NONE)
			{
				Turn(HeadBone, Weld * FQuat(Side, HeadPitch * 0.6f - FMath::DegreesToRadians(Stance.HeadDown)));   // (the chin a little down: the stance)
			}
		}
		else
		{
			// (a creature: its clip's twitches never take its eyes off its target)
			SetCS(Neck, FTransform(FQuat(Side, Pitch * 0.4f) * RefCS[Neck].GetRotation(), CS[Neck].GetLocation(), CS[Neck].GetScale3D()));
			if (HeadBone != INDEX_NONE)
			{
				SetCS(HeadBone, FTransform(Weld * FQuat(Side, Pitch) * RefCS[HeadBone].GetRotation(), CS[HeadBone].GetLocation(), CS[HeadBone].GetScale3D()));
			}
		}
	}

	// 3. Arms: two-bone IK to the wrist targets, elbows down and out, forearm shares the wrist twist, hand on the grip.
	for (int32 SideIndex = 0; SideIndex < (bOneHand ? 1 : 2); ++SideIndex)
	{
		const bool bLeft = SideIndex == 1;
		const int32 Upper = Arm[SideIndex][0], Lower = Arm[SideIndex][1], Hand = Arm[SideIndex][2];
		FTransform Target = bLeft ? LeftTarget : RightTarget;      // (a copy: the support hand's may slide back along the gun)

		// Shoulder girdle: the clavicle carries part of a forward / across reach (protraction) and of a raise above
		// the horizontal (elevation), like the shoulder blade does, so the shoulder keeps its volume instead of the
		// upper arm twisting it flat.
		if (const int32 Clav = Clavicle[SideIndex]; Clav != INDEX_NONE)
		{
			// (forward, out and up are the TRUNK's: a body bowed over a gun aimed at the ground reaches forward of its chest
			// where the world's axes said down, and its shoulders stayed back with the arms folded into it)
			const FQuat Bowed(Side, TrunkPitch + LeanRad);
			const FVector Joint = CS[Upper].GetLocation();
			const FVector Reach = Bowed.UnrotateVector((Target.GetLocation() - Joint).GetSafeNormal());
			const float Out = bLeft ? Reach.X : -Reach.X;                 // + = out to its own side, - = across the body
			const float Forward = FMath::Max(0.0f, (float)Reach.Y);
			// (the stance squares the shoulders: all of this pull rounded them, the chest closed)
			const float Protract = FMath::Clamp(Forward * 0.22f + FMath::Max(0.0f, -Out) * 0.30f, 0.0f, 0.42f) * (Stance.bPlayer ? 1.0f - Stance.Shoulders : 1.0f);   // rad (~24 deg max)
			const float Elevate = FMath::Clamp((float)Reach.Z * 0.30f + 0.04f * Forward, 0.0f, 0.30f);          // rad (~17 deg max)
			const float Sign = bLeft ? 1.0f : -1.0f;
			Turn(Clav, FQuat(Bowed.RotateVector(Up), Sign * Protract) * FQuat(Bowed.RotateVector(FVector(0.0f, 1.0f, 0.0f)), -Sign * Elevate));
		}

		// Hand bone vs its anatomical basis, from the rest pose (relaxed hands: thumb forward, palm to the thigh).
		const FVector RestAlong = (RefCS[Hand].GetLocation() - RefCS[Lower].GetLocation()).GetSafeNormal();
		const FQuat RestBasis = FSOHandGrip::MakeBasis(RestAlong, FVector(0.0f, 1.0f, 0.0f), bLeft);
		const FQuat HandOffset = RestBasis.Inverse() * RefCS[Hand].GetRotation();

		const FVector S = CS[Upper].GetLocation();
		const float L1 = FVector::Dist(S, CS[Lower].GetLocation());
		const float L2 = FVector::Dist(CS[Lower].GetLocation(), CS[Hand].GetLocation());
		// The support hand never holds the gun further out than the arm reaches with a bend left in it: it slides BACK
		// along the gun to where it does. (Held at a fore point a long way out, the arm was dead straight and the hand
		// stopped short of the gun with its fingers closing in it.)
		if (bLeft && !GunAxis.IsNearlyZero())
		{
			// (a hand round a vertical fore grip may reach nearly straight: slid back, it left the post with its fingers
			// still curled for it, in the gun)
			// (95 %: a long fore end, a pump's, is held with the arm nearly straight; slid back at 93 % while walking a pump
			// gun's hand came off its pump, the palm over nothing)
			const float Most = (bSupportOnPost ? 0.985f : 0.95f) * (L1 + L2);
			const FVector V = Target.GetLocation() - S;
			if (V.SizeSquared() > Most * Most)
			{
				const float Va = static_cast<float>(FVector::DotProduct(V, GunAxis));
				const float Disc = Va * Va - static_cast<float>(V.SizeSquared() - Most * Most);
				if (Disc > 0.0f)
				{
					// (up to 30 cm: at 14 a gun pointed steeply down left the hand floating short of it; on a handgun 2: slid
					// further it came off the pistol's back, round nothing: the viewmodel brings a handgun into reach)
					Target.AddToTranslation(-GunAxis * FMath::Clamp(Va - FMath::Sqrt(Disc), 0.0f, bHandgunHold ? 2.0f : 30.0f));
				}
			}
		}
		// The swing's frame round the shoulder-to-wrist line: straight down from it, and out round the arm's outside. "Down"
		// is the TRUNK's (turned with what it took of the aim's pitch): measured from the world's down, the elbows of a body
		// bowed over a gun aimed at the ground hung toward the floor, into the chest (the owner, 2026-11-23: "the right arm
		// is basically gone and moved into the body").
		const FVector TrunkDown = FQuat(Side, TrunkPitch + LeanRad).RotateVector(FVector(0.0f, 0.0f, -1.0f));
		auto SwingFrame = [bLeft, TrunkDown](const FVector& Line, FVector& OutDown, FVector& OutOut)
		{
			OutDown = TrunkDown - Line * FVector::DotProduct(TrunkDown, Line);
			if (!OutDown.Normalize(1e-3f))
			{
				return false;
			}
			OutOut = FVector::CrossProduct(Line, OutDown);
			if ((bLeft ? OutOut.X : -OutOut.X) < 0.0f)
			{
				OutOut = -OutOut;
			}
			return true;
		};
		const FVector ToTarget = Target.GetLocation() - S;
		const FVector Dir = ToTarget.GetSafeNormal(1e-4f, FVector(0.0f, 1.0f, 0.0f));
		const float D = FMath::Clamp(ToTarget.Size(), FMath::Abs(L1 - L2) + 0.5f, (L1 + L2) * 0.999f);
		const float Along = (L1 * L1 - L2 * L2 + D * D) / (2.0f * D);
		const float Height = FMath::Sqrt(FMath::Max(L1 * L1 - Along * Along, 0.0f));
		// out, back, down
		const float PoleOut = 0.45f;
		const FVector Pole = FQuat(Side, TrunkPitch + LeanRad).RotateVector(FVector(bLeft ? PoleOut : -PoleOut, -0.25f, -1.0f));   // (the trunk's, as the swing's)
		FVector Bend = Pole - Dir * FVector::DotProduct(Pole, Dir);
		Bend = Bend.GetSafeNormal(1e-4f, FVector(0.0f, 0.0f, -1.0f));
		// The elbow swings round the shoulder-to-wrist line toward where the WRIST bends least (the forearm running
		// on into the hand): held down and out whatever the hand did, the wrists were bent further than a wrist goes.
		// Measured from straight down, + round the arm's outside, - toward the body; most of the way there, between
		// a hand's breadth inside of down (tucked) and nearly level.
		// A player's body at the ready or on the sights carries its elbows OUT at the sides by the gun's class instead
		// (FSOStance::ElbowSwing, a share of the way toward the straight wrist): taken where the wrist ran straightest the
		// firing elbow hung under the gun in front of the chest, the forearm standing straight up to the grip, and from
		// behind the body hid the whole arm (the owner, 2026-11-23: "arm not showing ... the arms are gone").
		const bool bStanceArms = Stance.bPlayer && !bCarried && Stance.Ready > 0.0f;
		bool bSwung = false;
		{
			static const float ElbowToWrist = 0.6f;
			FVector Down, Out;
			if (SwingFrame(Dir, Down, Out))
			{
				auto Swing = [&](const FVector& V) { return FMath::Atan2(static_cast<float>(FVector::DotProduct(V, Out)), static_cast<float>(FVector::DotProduct(V, Down))); };
				const FVector HandAxis = Target.GetRotation().GetAxisX();
				const FVector Straight = -(HandAxis - Dir * FVector::DotProduct(HandAxis, Dir));
				const float Ask = static_cast<float>(Straight.Size());   // (a hand that already runs along the arm asks nothing)
				const float A0 = Swing(Bend);
				const float A1 = Ask > 0.15f ? Swing(Straight) : A0;
				float A = A0;
				// (the support elbow stays LOW: swung up level with the gun, the whole forearm lay across the bottom of the
				// first-person view, and stood out like a wing in third person)
				// (and the firing elbow of a gun carried low, at a sprint or by the armoury's stand-in, stays by the side:
				// swung out to line the forearm up with the canted grip it stood out level with the shoulder, the owner's "arm
				// seems very bend out", 2026-11-17)
				const float Most = bLeft ? 0.9f : (bCarried ? 0.55f : 1.45f);
				if (Ask > 0.15f)
				{
					// (the firing arm goes further: on the sights its wrist is the tightest)
					const float Share = (bLeft ? ElbowToWrist : 1.0f) * FMath::SmoothStep(0.15f, 0.5f, Ask);
					A = FMath::Clamp(A0 + (A1 - A0) * Share, -0.5f, Most);
					bSwung = true;
				}
				if (bStanceArms)
				{
					const float Least = Stance.ElbowLeast[SideIndex];
					float Want = FMath::Clamp(FMath::Lerp(Stance.ElbowSwing[SideIndex], A1, Ask > 0.15f ? Stance.WristShare[SideIndex] : 0.0f),
						Least, FMath::Max(Least, Stance.ElbowMost[SideIndex]));
					// never past a wrist's range: from the class's swing toward the straightest wrist, the first swing whose hand
					// is within it (the hand's place on the gun is fitted and stays: turned round the grip to follow the
					// forearm, the palm went into the grip's front)
					const float MinCos = FMath::Cos(FMath::DegreesToRadians(Stance.WristMax[SideIndex]));
					auto Straightness = [&](float Swing)
					{
						const FVector E = S + Dir * Along + (Down * FMath::Cos(Swing) + Out * FMath::Sin(Swing)) * Height;
						return static_cast<float>(FVector::DotProduct((S + Dir * D - E).GetSafeNormal(), HandAxis));
					};
					if (Ask > 0.15f && Straightness(Want) < MinCos)
					{
						const float From = Want;
						for (int32 Step = 1; Step <= 12; ++Step)
						{
							Want = FMath::Lerp(From, A1, Step / 12.0f);
							if (Straightness(Want) >= MinCos)
							{
								break;
							}
						}
					}
					A = FMath::Lerp(A, Want, Stance.Ready);
					bSwung = true;
				}
				if (bSwung)
				{
					Bend = Down * FMath::Cos(A) + Out * FMath::Sin(A);
				}
#if !UE_BUILD_SHIPPING
				{
					float* Sw = USOLocomotionAnimInstance::DebugSwing[SideIndex]; Sw[0] = A0; Sw[1] = A1; Sw[2] = A; Sw[3] = Ask; Sw[4] = Most;
				}
#endif
			}
		}
		// The arm stays out of the body (the owner, 2026-11-23: "when scoping in third person and looking down ... the right
		// arm is basically gone and moved into the body, remember we said not unnatural movements"): on the sights looking
		// down the swing put the firing elbow deep in the chest. The trunk: an ellipse round the line from the hips to the
		// neck in the chest's own frame (TrunkHalfWidth to either side, TrunkHalfDepth before and behind, the arm's own
		// thickness in them); the elbow and the middles of the upper arm and the forearm lie outside it. Of the swings round
		// the shoulder-to-wrist line, the nearest that does, outward first (the elbow flares out, as a body's does).
		if (Hips != INDEX_NONE && Neck != INDEX_NONE && Chest != INDEX_NONE)
		{
			FVector Down, Out;
			if (SwingFrame(Dir, Down, Out))
			{
				const FVector Base = CS[Hips].GetLocation(), Top = CS[Neck].GetLocation();
				const FVector TrunkUp = (Top - Base).GetSafeNormal(1e-4f, FVector(0.0f, 0.0f, 1.0f));
				const float TrunkLength = static_cast<float>(FVector::Dist(Base, Top));
				const FQuat ChestTurn = CS[Chest].GetRotation() * RefCS[Chest].GetRotation().Inverse();
				const FVector TrunkFwd = ChestTurn.RotateVector(FVector(0.0f, 1.0f, 0.0f)), TrunkLeft = ChestTurn.RotateVector(FVector(1.0f, 0.0f, 0.0f));
				auto Depth = [&](const FVector& P)
				{
					const float T = static_cast<float>(FVector::DotProduct(P - Base, TrunkUp));
					if (T < 0.0f || T > TrunkLength)
					{
						return 9.0f;
					}
					const FVector Off = (P - Base) - TrunkUp * T;
					// (narrower at the waist than at the ribs: 85 % of the chest's breadth and depth below its middle)
					const float Taper = FMath::Lerp(0.85f, 1.0f, FMath::SmoothStep(0.3f, 0.65f, T / FMath::Max(TrunkLength, 1.0f)));
					const float X = static_cast<float>(FVector::DotProduct(Off, TrunkLeft)) / (TrunkHalfWidth * Taper);
					const float Y = static_cast<float>(FVector::DotProduct(Off, TrunkFwd)) / (TrunkHalfDepth * Taper);
					return X * X + Y * Y;
				};
				const FVector W = S + Dir * D;
				auto Clear = [&](float Sw)
				{
					const FVector E = S + Dir * Along + (Down * FMath::Cos(Sw) + Out * FMath::Sin(Sw)) * Height;
					return FMath::Min3(Depth(E), Depth((S + E) * 0.5), Depth((E + W) * 0.5));
				};
				const float A = FMath::Atan2(static_cast<float>(FVector::DotProduct(Bend, Out)), static_cast<float>(FVector::DotProduct(Bend, Down)));
				if (Clear(A) < 1.0f)
				{
					// (the nearest swing either way that is clear of the trunk AND leaves the wrist within its range: the hand's
					// place on the gun stays, so the forearm's line decides the wrist; failing both, the clear one with the
					// straightest wrist: nothing is solved by bending a joint past what a body does)
					const FVector HandAxis = Target.GetRotation().GetAxisX();
					const float WristLimit = FMath::Cos(FMath::DegreesToRadians(Stance.bPlayer ? Stance.WristMax[SideIndex] : 75.0f));
					auto WristCos = [&](float Sw)
					{
						const FVector E = S + Dir * Along + (Down * FMath::Cos(Sw) + Out * FMath::Sin(Sw)) * Height;
						return static_cast<float>(FVector::DotProduct((W - E).GetSafeNormal(), HandAxis));
					};
					float Best = A, BestCos = -2.0f;
					bool bFound = false;
					for (int32 Step = 1; Step <= 32 && !bFound; ++Step)
					{
						for (const float Sign : { 1.0f, -1.0f })                 // (out first)
						{
							const float Try = A + Sign * Step * 0.07f;
							if (Try > 2.2f || Try < -1.2f || Clear(Try) < 1.0f)
							{
								continue;
							}
							const float C = WristCos(Try);
							if (C >= WristLimit)
							{
								Best = Try;
								bFound = true;
								break;
							}
							if (C > BestCos)
							{
								Best = Try;
								BestCos = C;
							}
						}
					}
					Bend = Down * FMath::Cos(Best) + Out * FMath::Sin(Best);
				}
			}
		}
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
		FVector MiddleDir = FVector::ZeroVector;
		if (Fingers.Together > 0.0f)
		{
			const int32 M0 = Find(bLeft ? TEXT("middle_01_L") : TEXT("middle_01_R")), M1 = Find(bLeft ? TEXT("middle_02_L") : TEXT("middle_02_R"));
			if (M0 != INDEX_NONE && M1 != INDEX_NONE)
			{
				const FTransform M = RefLocal[M0] * CS[Hand];
				MiddleDir = ((RefLocal[M1] * M).GetLocation() - M.GetLocation()).GetSafeNormal();
			}
		}
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
				// (from the finger's REST pose, as the fit measured it: closed on top of what the clip had already
				// curled, as it was, every finger went a clip's curl further than fitted, into the gun)
				FTransform Rigid = RefLocal[I] * ParentCS;
				if (k == 0)
				{
					const FVector FingerDir = ((RefLocal[Chain[1]] * Rigid).GetLocation() - Rigid.GetLocation()).GetSafeNormal();
					FVector ThumbDir = FingerDir;
					Axis = FVector::CrossProduct(FingerDir, Palm).GetSafeNormal();
					if (Fingers.Together > 0.0f && (f == 2 || f == 3 || (f == 0 && bLeft)) && !MiddleDir.IsNearlyZero())
					{
						const FQuat Toward = USOLocomotionAnimInstance::FingersTogether(FingerDir, MiddleDir, Palm, Fingers.Together);
						Rigid.SetRotation(Toward * Rigid.GetRotation());
						Axis = FVector::CrossProduct(Toward.RotateVector(FingerDir), Palm).GetSafeNormal();
					}
					if (f == 4 && FMath::Abs(Fingers.ThumbSpread) > 0.01f)
					{
						// the thumb round the hand's long axis, toward the palm's side (+) or off it (-); the axis it
						// closes about turns with it (see FitGrip)
						const FVector AlongHand = Target.GetRotation().GetAxisX();
						const float Sign = FVector::DotProduct(Axis, AlongHand) >= 0.0f ? 1.0f : -1.0f;
						const FQuat Spread(AlongHand, FMath::DegreesToRadians(Fingers.ThumbSpread) * Sign);
						Rigid.SetRotation(Spread * Rigid.GetRotation());
						Axis = Spread.RotateVector(Axis);
						ThumbDir = Spread.RotateVector(ThumbDir);
					}
					if (f == 0 && FMath::Abs(Fingers.IndexLift) > 0.01f)
					{
						// the index turned in the palm's plane (see FitGrip)
						const FQuat Lift(Palm, FMath::DegreesToRadians(Fingers.IndexLift));
						Rigid.SetRotation(Lift * Rigid.GetRotation());
						Axis = Lift.RotateVector(Axis);
					}
					if (f == 4 && Fingers.ThumbIn > 0.01f)
					{
						// drawn in toward the fingers, about the palm's normal (see FitGrip)
						const FVector AlongHand = Target.GetRotation().GetAxisX();
						FQuat In(Palm, FMath::DegreesToRadians(Fingers.ThumbIn));
						if (FVector::DotProduct(In.RotateVector(ThumbDir), AlongHand) < FVector::DotProduct(In.Inverse().RotateVector(ThumbDir), AlongHand))
						{
							In = In.Inverse();
						}
						Rigid.SetRotation(In * Rigid.GetRotation());
						Axis = In.RotateVector(Axis);
					}
				}
				const FQuat Close(Axis, FMath::DegreesToRadians(Fingers.Curl[f][k]));
				CS[I] = FTransform(Close * Rigid.GetRotation(), Rigid.GetLocation(), Rigid.GetScale3D());
				Local[I] = CS[I].GetRelativeTransform(ParentCS);
				ParentCS = CS[I];
			}
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
