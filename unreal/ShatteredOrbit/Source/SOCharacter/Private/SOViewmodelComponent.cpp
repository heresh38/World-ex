#include "SOViewmodelComponent.h"
#include "SOArmBones.h"
#include "SOSpring.h"
#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
#include "SOStance.h"
#include "SOWeaponData.h"

#include "AnimationRuntime.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "SOCharacter.h"
#include "SOCharacterMovementComponent.h"
#include "SOGunRigComponent.h"
#include "SOLocomotionAnimInstance.h"
#include "SOLookComponent.h"
#include "SOReload.h"
#include "SOReloadShow.h"
#include "SOWeapon.h"

USOViewmodelComponent::USOViewmodelComponent()
{
	PrimaryComponentTick.bCanEverTick = true;
	// After movement and look, before the body animates (its arm IK reads the hold).
	PrimaryComponentTick.TickGroup = TG_PrePhysics;
}

void USOViewmodelComponent::BeginPlay()
{
	Super::BeginPlay();
	if (ASOCharacter* Character = Cast<ASOCharacter>(GetOwner()))
	{
		if (UActorComponent* Move = Character->GetCharacterMovement())
		{
			AddTickPrerequisiteComponent(Move);
		}
		if (USOLookComponent* Look = Character->GetLook())
		{
			AddTickPrerequisiteComponent(Look);
		}
		if (USkeletalMeshComponent* Body = Character->GetMesh())
		{
			Body->AddTickPrerequisiteComponent(this);
		}
	}
}

namespace
{
	/** A damped spring: X toward Target with its own velocity V (Omega: how fast, Zeta: 1 = no overshoot, less = a
	 *  little; the owner, 2026-11-20: "very fluid, like water": nothing moves on a straight line and stops dead). */
	void Spring(float& X, float& V, float Target, float Omega, float Zeta, float Dt)
	{
		SOSpring::Step(X, V, Target, Omega, Zeta, Dt);   // (stable at any frame time: SOSpring.h)
	}
}

void USOViewmodelComponent::Kick(float Strength)
{
	KickBack = FMath::Min(0.12f, KickBack + 0.03f * Strength);
	KickPitch = FMath::Min(0.25f, KickPitch + 0.05f * Strength);
}

void USOViewmodelComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);
	UpdateHold(DeltaTime);
}

void USOViewmodelComponent::UpdateHold(float DeltaTime)
{
	ASOCharacter* Character = Cast<ASOCharacter>(GetOwner());
	if (!Character)
	{
		return;
	}
	const USOCharacterMovementComponent* Move = Character->GetSOMovement();
	const ASOWeapon* Weapon = Character->GetWeapon();
	const USOWeaponData* Data = Weapon ? Weapon->GetData() : nullptr;
	const USOGunRigComponent* Rig = Weapon ? Weapon->GetRig() : nullptr;
	const float Dt = FMath::Max(DeltaTime, 1e-4f);

	// ADS (smoothstep of the character's aim progress).
	const float A = Character->GetAimProgress();
	Ads = A * A * (3.0f - 2.0f * A);
	const bool bGrounded = Move && Move->IsMovingOnGround();
	const bool bRunning = (Move && Move->IsSprinting()) || Character->IsDisplayCarry();
	KickBack *= FMath::Pow(0.0005f, Dt);
	KickPitch *= FMath::Pow(0.0008f, Dt);
	Lower = FMath::Max(0.0f, Lower - Dt * 4.0f);
	// the sprint carry: the gun swings down into it and back up in the gun's sprint-to-fire time, as a spring (it ran on
	// a straight line before: a machine's motion)
	Spring(RunK, RunV, bRunning ? 1.0f : 0.0f, 4.2f / FMath::Max(Data ? Data->SprintToFireTime : 0.2f, 0.05f), 0.82f, Dt);
	RunK = FMath::Clamp(RunK, -0.15f, 1.15f);
	const float RunC = FMath::Clamp(RunK, 0.0f, 1.0f);
	const float RunT = RunC * RunC * (3.0f - 2.0f * RunC) + (RunK - RunC) * 0.5f;   // (the overshoot kept, halved)

	// Movement inertia: the gun trails strafes and landings, tucks in for a slide, drops away for a mantle.
	const FVector Vel = Character->GetVelocity();
	const float Strafe = FMath::Clamp(static_cast<float>(FVector::DotProduct(Vel, Character->GetActorRightVector())) / 440.0f, -1.6f, 1.6f);
	Spring(StrafeK, StrafeV, bGrounded ? Strafe : Strafe * 0.5f, 9.0f, 0.62f, Dt);
	StrafeK = FMath::Clamp(StrafeK, -2.0f, 2.0f);
	const float AirLift = Move && Move->IsFalling() ? FMath::Clamp(static_cast<float>(Vel.Z) / 900.0f, -1.0f, 1.0f) : 0.0f;
	Spring(AirK, AirV, AirLift, 10.0f, 0.9f, Dt);   // (a spring: as an exponential the gun jumped into its tilt at a take-off)
	// (the weight: the body's change of pace along its facing, its pace against a lagged copy of it: a steady pace carries
	// nothing; on a spring with a little overshoot, below)
	{
		const float Pace = static_cast<float>(FVector::DotProduct(Vel, Character->GetActorForwardVector().GetSafeNormal2D()));
		FwdLag += (Pace - FwdLag) * (1.0f - FMath::Exp(-Dt / FMath::Max(MoveInertiaLag, 0.02f)));
		// (nearly critically damped: with a spring's overshoot the weight's return crossed the step's sway, and setting off
		// at 30 frames a second the SMG's sight turned back three times in a fifth of a second)
		Spring(FwdK, FwdV, FMath::Clamp((Pace - FwdLag) / 440.0f, -1.5f, 1.5f), 10.0f, 0.9f, Dt);
		FwdK = FMath::Clamp(FwdK, -1.8f, 1.8f);
	}
	Spring(SlideK, SlideV, Move && Move->IsSliding() ? 1.0f : 0.0f, 13.0f, 0.85f, Dt);
	Spring(MantleK, MantleV, Move && Move->IsMantling() ? 1.0f : 0.0f, 16.0f, 0.9f, Dt);
	SlideK = FMath::Clamp(SlideK, -0.1f, 1.1f);
	MantleK = FMath::Clamp(MantleK, -0.1f, 1.1f);
	const float SlideT = SlideK, MantleT = FMath::Clamp(MantleK, 0.0f, 1.0f);
	// (a dodge's dip and tilt in and out on a smooth window: on a sine's half the gun started and stopped at full speed)
	const float DodgeT = Move && Move->IsDodging() ? FMath::Square(FMath::Sin(Move->GetDodgeAlpha() * PI)) : 0.0f;
	const float Free = 1.0f - Ads * 0.85f;
	const float InX = (-StrafeK * 0.006f + SlideT * 0.008f) * Free;
	// (in the air the gun tilts with the rise and the fall: the guide's "weapon tilts naturally"; at 0.03 / 0.008 it barely
	// showed)
	const float InY = (Character->GetLandDip() * 0.0025f - AirK * 0.012f - SlideT * 0.012f - MantleT * 0.09f - DodgeT * 0.012f) * Free;
	const float InPitch = (-MantleT * 0.5f + AirK * 0.05f + DodgeT * 0.06f) * Free;
	const float InRoll = (StrafeK * 0.05f + SlideT * 0.22f + MantleT * 0.35f) * Free;

	ReloadK = FMath::FInterpTo(ReloadK, Weapon && Weapon->IsReloading() ? 1.0f : 0.0f, Dt, 7.0f);
	KeepReloadWork(Weapon, Rig);
	{
		// The show (FSOReloadShow): the one the support hand's work asks for, between the shows of the two places the hand is
		// going from and to (the choreography's anchors; "cur" = wherever the last segment left it), followed on a spring
		const FSOReloadShowData& Shows = FSOReloadShowData::Get();
		const bool bReloading = Weapon && Weapon->IsReloading() && Rig;
		if (bReloading)
		{
			const FSOReloadStyleShow& Style = Shows.For(Rig->GetArchetype(), SOReload::GetStyle(Rig->GetArchetype()));
			const FSOReloadPose& P = Weapon->GetPose();
			static const FName NCur(TEXT("cur")), NFore(TEXT("fore"));
			if (!bShowing || P.Segment != ShowSegment)
			{
				// (a reload begins in the show the hand leaves the fore end from; a segment begins in the one the last ended in)
				FMemory::Memcpy(ShowCur, bShowing ? ShowWant : Style.For(NFore).V, sizeof(ShowCur));
				ShowSegment = P.Segment;
			}
			// The hand's job as the gun's turn reads it. Where the hand's next place is a handle or a slide, which the gun
			// is turned right over for (from a magazine well shown on its left to a handle on its right: 130 degrees and
			// more about the bore), the gun's turn runs a little AHEAD of the hand (Shows.HandleLead; "cur" named by the
			// player): it is rolling before the hand lets go of the magazine and is nearly round as the hand arrives.
			// Turned with the hand, the gun was still showing the last job when the hand reached the handle on its far
			// side: the forearm lay across the top of the gun and over the picture (rack frames, capture set 53).
			bool bHand = P.bHand;
			FName HandA = P.HandAnchorA, HandB = P.HandAnchorB;
			float HandAlpha = P.HandAlpha;
			{
				static const FName NBolt(TEXT("bolt")), NCharge(TEXT("charge")), NSlide(TEXT("slide"));
				FName AheadA, AheadB;
				float AheadAlpha = 0.0f;
				if (Shows.HandleLead > 0.0f && Weapon->PeekReloadHand(Shows.HandleLead, AheadA, AheadB, AheadAlpha)
					&& (AheadB == NBolt || AheadB == NCharge || AheadB == NSlide))
				{
					bHand = true;
					HandA = AheadA;
					HandB = AheadB;
					HandAlpha = AheadAlpha;
				}
			}
			FSOReloadShow From, To;
			FMemory::Memcpy(From.V, bHand && HandA != NCur ? Style.For(HandA).V : ShowCur, sizeof(From.V));
			FMemory::Memcpy(To.V, !bHand ? Style.Base.V : (HandB != NCur ? Style.For(HandB).V : From.V), sizeof(To.V));
			// (the gun is turned for the hand's next job while the hand is still on its way there, done by six tenths of the
			// way: turned evenly with the hand, it was still showing the last job as the hand arrived for this one)
			const float T = bHand ? FMath::Clamp(HandAlpha * 1.65f, 0.0f, 1.0f) : 1.0f;
			FSOReloadShow Want = FSOReloadShow::Lerp(From, To, T * T * (3.0f - 2.0f * T));
			// (a flap that stands open is shown for as long as it is open, wherever the hands are: a light gun's vent is
			// thrown open and the hand goes back to the fore end while the heat is purged, and with the hand's show the gun
			// went back down with the flap still open and venting under the picture)
			const float Open = FMath::SmoothStep(0.03f, 0.3f, FMath::Abs(P.Hatch));
			if (Open > 0.0f)
			{
				Want = FSOReloadShow::Lerp(Want, Style.Base, Open);
			}
			FMemory::Memcpy(ShowWant, Want.V, sizeof(ShowWant));
			// (and the show of the place the hand is flying to NOW: where the gun will be when it arrives, for the rig)
			const bool bWasFlight = bShowFlight;
			bShowFlight = P.bHand && P.HandAnchorA != P.HandAnchorB && P.HandAnchorB != NCur;
			if (bShowFlight && (!bWasFlight || P.Segment != FlightSegment || P.HandAnchorA != FlightA || P.HandAnchorB != FlightB))
			{
				// (the hand lets go: where the gun is held now is where its way begins, below)
				FlightSegment = P.Segment;
				FlightA = P.HandAnchorA;
				FlightB = P.HandAnchorB;
				bFlightBegan = true;
			}
			if (bShowFlight)
			{
				FSOReloadShow Arrive;
				FMemory::Memcpy(Arrive.V, Style.For(P.HandAnchorB).V, sizeof(Arrive.V));
				FMemory::Memcpy(ShowTo, FSOReloadShow::Lerp(Arrive, Style.Base, Open).V, sizeof(ShowTo));
			}
			if (!bShowing)
			{
				FMemory::Memcpy(ShowNow, ShowWant, sizeof(ShowNow));
				FMemory::Memzero(ShowVel, sizeof(ShowVel));
				bShowing = true;
			}
		}
		else if (ReloadK < 0.02f)
		{
			bShowing = false;
		}
		if (!bReloading)
		{
			bShowFlight = false;
		}
		if (bShowing)
		{
			for (int32 i = 0; i < 6; ++i)
			{
				SOSpring::Step(ShowNow[i], ShowVel[i], ShowWant[i], Shows.Omega, Shows.Zeta, Dt);
			}
		}
		// (the handling's jolts settle)
		SOSpring::Step(JoltMove, JoltMoveVel, FVector::ZeroVector, Shows.JoltOmega, Shows.JoltZeta, Dt);
		SOSpring::Step(JoltTurn, JoltTurnVel, FVector::ZeroVector, Shows.JoltOmega, Shows.JoltZeta, Dt);
	}
	const bool bInspect = Weapon && Weapon->IsInspecting();
	InspectK = FMath::FInterpTo(InspectK, bInspect ? 1.0f : 0.0f, Dt, 9.0f);

	// The reload's own moves of the gun (reload.js: the cant, the lift, the slap), a share of them in the hands: the gun
	// works in them and never leaves them (the owner's ULTIMATE rule, 2026-11-23: "all players hands must always at all
	// times be on this ... to ensure we get no floating guns"; whole, they swung the gun up beside the head).
	static const float Zero[6] = { 0, 0, 0, 0, 0, 0 };
	// (an inspect's moves are the gun shown to the eyes: turned whole about the firing hand, below, not a share of them here)
	const float* G = Weapon && !bInspect ? Weapon->GetPose().Gun : Zero;
	const float GunMoves = FSOReloadShowData::Get().GunMoves;

	const bool bHandgun = Data && Data->MuzzleLocation.Y < 35.0f;
	USceneComponent* Held = Character->GetGunHold();
	if (!Held)
	{
		Character->SetSightEye(FVector::ZeroVector, 0.0f);
		return;
	}
	// Where the body holds it (the stance's place, relaxed or at the ready, the sprint's carry, the reload's; on the
	// sights a long gun shouldered, the butt in the pocket).
	// (relaxed the arms are easy: a class may bring the gun nearer the support shoulder then, FSOStance::RelaxReach)
	const FSOStance& Stance = FSOStanceData::Get().For(Data ? Data->Family : NAME_None);
	const float Relaxed = (1.0f - Character->GetCombatReady()) * (1.0f - Ads) * (1.0f - InspectK);
	const float Reach = Stance.RelaxReach > 0.0f ? FMath::Lerp(SupportReach, Stance.RelaxReach, Relaxed) : SupportReach;
	const float StockOff = Stance.RelaxReach > 0.0f ? Relaxed : 0.0f;    // (and the stock may come off the shoulder for it)
	FTransform Hold = OffTheShoulder(Character, Data, bHandgun, RunT,
		InFiringReach(Character, Rig, InSupportReach(Character, Rig, HoldTransform(Character, Data, bHandgun, Dt, RunT), Reach, StockOff)));
	// (the camera's framing, HoldTransform; it gives way as the player looks down or up, the camera back in the eyes by
	// 55 degrees: set behind them, looking at the floor it saw down through the body, and looking up the raised arms are
	// nearer it)
	{
		const float Look = FMath::Clamp((FMath::Abs(FRotator::NormalizeAxis(Character->GetAimRotation().Pitch)) - 15.0f) / 40.0f, 0.0f, 1.0f);
		const float Framed = 1.0f - Look * Look * (3.0f - 2.0f * Look);
		Character->SetFrame(FrameDrop * Framed, FrameSide * Framed, FrameBack * Framed);
	}

	// On the sights (one body, one camera, the owner, 2026-11-23): the sight on the camera's line. A long gun stays where
	// the body shoulders it and the CAMERA alone comes to its sight's line, where a cheek on the comb would put an eye
	// (the owner: "Don't move the eyes ... just move the camera": the head keeps its own pose for those watching; the
	// shots go along the camera's line). Before, the gun went to the eyes at a fixed 9 cm: with one body its butt went
	// through the shoulder and out of the back. A handgun comes up to the eyes' line, held out at the arms' reach.
	FVector AdsOffset(AdsSightDistance, 0.0f, 0.0f);
	FVector SightPivot = FVector::ZeroVector;
	FVector SightShift = FVector::ZeroVector;
	{
		const FTransform Eye = Character->GetEyeTransform(true);
		float SightEye = 0.0f;
		FVector SightEyeCS = FVector::ZeroVector;
		if (Data && Rig && Rig->IsBuilt())
		{
			const FVector SightRig = USOGunRigComponent::MeshToRig(Weapon->GetSightLocation());
			float Relief = AdsHandgunSightDistance;
			if (bHandgun)
			{
				Relief = HandgunRelief(Character, Rig, SightRig, Eye);
			}
			else
			{
				const FBox B = Rig->GetRigBounds();
				const float Least = Rig->IsOpticMounted() ? OpticEyeRelief : (Rig->HasBuiltInOptic() ? BuiltInOpticEyeRelief : IronsEyeRelief);
				Relief = FMath::Max(static_cast<float>(SightRig.X - B.Min.X) - CheekFromButt, Least);
				// (on the view's line through the shouldered gun's sight: the rounds go along it; looking steeply down
				// the stock comes off the shoulder and the head stays up: the gun comes to the eyes there)
				const float PitchDeg = FRotator::NormalizeAxis(Character->GetAimRotation().Pitch);
				const float Down = FMath::Clamp((-PitchDeg - 20.0f) / 50.0f, 0.0f, 1.0f) * (1.0f - Ads);
				const FVector SightWorld = Hold.TransformPosition(SightRig);
				const FTransform Capsule = Character->GetCapsuleComponent()->GetComponentTransform();
				SightEyeCS = Capsule.InverseTransformPosition(SightWorld - Eye.GetRotation().GetForwardVector() * Relief);
				SightEye = Ads * (1.0f - Down);
				// (the camera comes to the sight on a spring as the gun comes up: until it is there the gun is laid against
				// where the camera is going, not where it is: below)
				SightShift = Capsule.TransformVector((SightEyeCS - Character->GetHeadEyeCS()) * (1.0f - Down));
			}
			AdsOffset = FVector(Relief - SightRig.X, -SightRig.Y, -SightRig.Z);
			SightPivot = SightRig;
		}
		Character->SetSightEye(SightEyeCS, SightEye);
	}

	// The kick, the raise, the reload's moves and the motion's inertia on top (the walk's bob and sway are the body's own).
	{
		// (and the handling's jolts: each beat of a reload knocks the gun in the hands, USOViewmodelComponent::Handle)
		const float TX = G[0] * GunMoves + InX + static_cast<float>(JoltMove.X) * 0.01f, TY = -Lower * 0.35f + G[1] * GunMoves + InY + static_cast<float>(JoltMove.Y) * 0.01f;
		const float TZ = KickBack * (1.0f - Ads) + G[2] * GunMoves + static_cast<float>(JoltMove.Z) * 0.01f;
		const float PX = KickPitch * (1.0f - Ads) + G[3] * GunMoves - Lower * 0.6f + InPitch + FMath::DegreesToRadians(static_cast<float>(JoltTurn.X));
		const float PY = G[4] * GunMoves + FMath::DegreesToRadians(static_cast<float>(JoltTurn.Y)), PZ = G[5] * GunMoves + InRoll + FMath::DegreesToRadians(static_cast<float>(JoltTurn.Z));
		const FTransform Ride(FRotator(FMath::RadiansToDegrees(PX), FMath::RadiansToDegrees(-PY), FMath::RadiansToDegrees(-PZ)),
			FVector(-TZ * 100.0f, TX * 100.0f, TY * 100.0f));
		Hold = Ride * Hold;
	}
	// The inspect (ASOWeapon::IsInspecting, SOReload::BuildInspect; the owner, 2026-11-24, a video of first-person guns:
	// "its satisfying animations"): the gun turned about the FIRING hand's place on it, as a wrist turns a gun in the hand,
	// and moved up and in toward the eyes, whole: a reload's moves are the gun working in the hands (a third of them, above),
	// these are the gun shown to the eyes. The hands' reach below keeps the gun where the arms can hold it.
	if (bInspect && Rig && Rig->IsBuilt())
	{
		const float* S = Weapon->GetPose().Gun;
		FVector Grip = FVector::ZeroVector;
		FTransform RT, LT;
		if (Rig->GetHandTargets(RT, LT))
		{
			Grip = Rig->GetComponentTransform().InverseTransformPosition(RT.GetLocation());
		}
		// (a long gun about its middle, between its two hands, at the grip's height: both hands go with it)
		if (!bHandgun)
		{
			const FBox GunBox = Rig->GetRigBounds();
			Grip.X = FMath::Clamp(static_cast<float>(GunBox.GetCenter().X), static_cast<float>(Grip.X), static_cast<float>(Grip.X) + 25.0f);
		}
		const FQuat Turn = FRotator(FMath::RadiansToDegrees(S[3]), FMath::RadiansToDegrees(-S[4]), FMath::RadiansToDegrees(-S[5])).Quaternion();
		const FVector Shift(-S[2] * 100.0f, S[0] * 100.0f, S[1] * 100.0f);     // (the gun's frame: forward, right, up)
		Hold = FTransform(Turn, Grip - Turn.RotateVector(Grip) + Shift) * Hold;
	}
	// Walking off the sights the gun rides steadier than the shoulder carries it: its place against the eyes' steady place
	// (the view's turn at the eyes' height on the capsule) follows the body's hold through a soft spring (the owner,
	// 2026-11-23: "when in first person not scoped and walking the guns shake too much"). Against the steady place, never
	// the camera itself: the camera carries the head's bob and comes back from a sight, and smoothed against it the gun
	// dragged behind it coming off the sights, the hand round the heavy machine gun's grip bent 84 degrees.
	{
		// (walking only: standing the hold is as it is, and a reload's and a sprint's own moves are never held back: smoothed,
		// the reload's swing left the gun out of both arms' reach)
		const FTransform Eye(Character->GetEyeTransform(true).GetRotation(),
			Character->GetCapsuleComponent()->GetComponentTransform().TransformPosition(Character->GetSteadyEyeCS()));
		const FTransform Against = Hold.GetRelativeTransform(Eye);
		const float Walking = bGrounded ? Character->GetMovingEase() * (1.0f - FMath::Max(ReloadK, InspectK)) * (1.0f - FMath::Clamp(RunT, 0.0f, 1.0f)) : 0.0f;
		if (!bInEyesValid || Dt > 0.25f)
		{
			InEyesPos = Against.GetLocation();
			InEyesVel = FVector::ZeroVector;
			InEyesRot = Against.GetRotation();
			WalkK = Walking;
			WalkV = 0.0f;
			bInEyesValid = true;
		}
		// (how much of it counts is eased, movement pass 3: a jump's take-off and its landing switched it in a frame, and
		// the gun jumped across the smoothing's own lag, 2.9 cm a frame as the feet left the ground; stiffening the follow as
		// it was let go as well made setting off shakier at 30 frames a second, and was dropped)
		SOSpring::Step(WalkK, WalkV, Walking, 20.0f, 1.0f, Dt);   // (at 12 a share of it lingered a third of a second after a walk and held the gun off the hold)
		WalkK = FMath::Clamp(WalkK, 0.0f, 1.0f);
		// (and while the gun swings into or out of the sprint's carry, a reload or an inspect, the smoothed place keeps close
		// to the hold, movement pass 5: lagging the swing, it held the gun back as the walk's share rose with the pace and let
		// it go as the carry took over, and the gun turned back on itself, 4 cm a frame setting off into a sprint)
		const float Swinging = FMath::Max(FMath::Clamp(RunT, 0.0f, 1.0f) * (1.0f - FMath::Clamp(RunT, 0.0f, 1.0f)) * 4.0f, FMath::Max(ReloadK, InspectK));
		const float Follow = InEyesFollowMoving * (1.0f + 8.0f * FMath::Max(Swinging, bRunning ? 1.0f : 0.0f));
		SOSpring::Step(InEyesPos, InEyesVel, Against.GetLocation(), Follow, 1.0f, Dt);
		InEyesRot = FQuat::Slerp(InEyesRot, Against.GetRotation(), 1.0f - FMath::Exp(-Follow * Dt)).GetNormalized();
		// (its last two hundredths cut off smoothly: a lingering share of a smoothed place a long way off the hold, after a
		// walk and an aim flicked from the sky to the floor, bent a crouched sniper's wrist past 80)
		const float Share = FMath::Max(WalkK - 0.02f, 0.0f) / 0.98f;
		if (Share > 1e-4f)
		{
			FTransform Ridden;
			Ridden.Blend(Hold, FTransform(InEyesRot, InEyesPos) * Eye, Share);
			Hold = Ridden;
		}
	}
	// The step's own motion (the owner's movement guide, 2026-11-20: "walk: subtle bob and sway ... sprint: dynamic arm
	// movement"; the owner, 2026-11-24: "first do another pass at our movement"): the gun dips as each foot takes the
	// body's weight and sways across with the stride, locked to the gait's own cycle (USOLocomotionAnimInstance::CyclePhase:
	// the walk and the run start on the left foot), as large as the pace asks: a stroll barely, the run a little, the
	// sprint's carry swung with the arms. Two sines a stride, after the walk's smoothing above (smoothed, it lagged and lost
	// half itself): a rhythm, never a shake. Off on the sights, in a reload and an inspect. At the run (not a stroll, not a
	// sprint) the gun rides canted in a little, lower and further in: running reads apart from walking (the owner's second
	// movement video, 2026-11-24).
	if (const USOLocomotionAnimInstance* Anim = Cast<USOLocomotionAnimInstance>(Character->GetMesh() ? Character->GetMesh()->GetAnimInstance() : nullptr); Anim && bGrounded)
	{
		const float Speed = static_cast<float>(Vel.Size2D());
		const float Moving = Character->GetMovingEase();
		const float Paced = FMath::SmoothStep(30.0f, 440.0f, Speed) * Moving;
		const float Sprinted = FMath::Clamp(RunT, 0.0f, 1.0f) * FMath::SmoothStep(500.0f, 860.0f, Speed);
		const float Step = (1.0f - Ads) * (1.0f - FMath::Max(ReloadK, InspectK)) * (Character->bIsCrouched ? 0.6f : 1.0f);
		const float Phase = UE_TWO_PI * (Anim->CyclePhase - StepLag);
		const float Dip = (StepDip * Paced + SprintStepDip * Sprinted) * Step;
		const float Sway = (StepSway * Paced + SprintStepSway * Sprinted) * Step;
		const float Roll = (StepRoll * Paced + SprintStepRoll * Sprinted) * Step;
		const float Yaw = SprintStepYaw * Sprinted * Step;
		const float Running = FMath::SmoothStep(250.0f, 440.0f, Speed) * (1.0f - Sprinted) * Step * Moving;
		const FRotator Turn(-0.25f * Dip * FMath::Cos(2.0f * Phase), 0.5f * Yaw * FMath::Sin(Phase + 0.25f * PI), 0.5f * Roll * FMath::Sin(Phase) - RunCant * Running);
		const FVector Shift(0.0f, -0.5f * Sway * FMath::Sin(Phase) - RunIn * Running, -0.5f * Dip * FMath::Cos(2.0f * Phase) - RunDrop * Running);
		Hold = FTransform(Turn, Shift) * Hold;
	}
	// The gun's weight (movement pass 2, 2026-11-24): held in two hands its mass is above and ahead of them, so as the body
	// sets off it is drawn after it, back toward the eyes with its muzzle lifting a little, and as the body stops it swings
	// on, forward with its muzzle dipping, and settles; a landing dips the muzzle with the view's own dip. After the walk's smoothing (smoothed, it lagged and lost half itself). A little of it on the sights (they stay
	// still: the guide's "ADS stable"), half of it in a reload or an inspect.
	{
		const float Weight = (1.0f - Ads * 0.85f) * (1.0f - 0.5f * FMath::Max(ReloadK, InspectK));
		const float Back = FwdK * MoveInertiaBack * Weight;
		const float Lift = (FwdK * MoveInertiaPitch + Character->GetLandDip() * LandMuzzleDip) * Weight;
		Hold = FTransform(FRotator(Lift, 0.0f, 0.0f), FVector(-Back, 0.0f, 0.0f)) * Hold;
	}
	// On the sights (the same gun in the same hands, first person or not): the sight on the line of the body's eyes,
	// where the camera is in first person; the kick turns the gun about its SIGHT, so the reticle stays on the point the
	// rounds hit (the owner: "the bullets don't even hit where the scope is").
	if (Ads > 1e-3f)
	{
		const float EX = KickPitch * 0.15f + G[3] * GunMoves * 0.3f + InPitch * 0.15f;
		const float EZ = (G[5] * GunMoves + InRoll) * 0.15f;
		const FRotator Turn(FMath::RadiansToDegrees(EX), 0.0f, FMath::RadiansToDegrees(-EZ));
		const FVector Offset = AdsOffset + (SightPivot - Turn.RotateVector(SightPivot)) + FVector(-KickBack * 15.0f, 0.0f, 0.0f);
		// (the eye: on the shouldered gun's sight line. The camera comes to it on a spring: on the way the frame is moved to
		// where the camera is going, so a long gun stays shouldered as it comes up and only the camera moves (laid against
		// the camera on its way, the gun was pulled toward the head's eyes and the hand round the heavy machine gun's grip
		// bent 80 degrees halfway up); on the sights it is the camera's own line again)
		FTransform Frame = Character->GetEyeTransform(true);
		Frame.AddToTranslation(SightShift * (1.0f - Ads));
		const FTransform Sighted = FTransform(Turn, Offset) * Frame;
		FTransform Mixed;
		Mixed.Blend(Hold, Sighted, Ads);
		Hold = Mixed;
	}
	Hold = ClearOfWalls(Character, Rig, Hold, Dt);
	// (both hands again after the motion's sway and the kick: they carried a pump's fore end out of the support hand's reach;
	// on the sights the sight stays on the eye's line, the gun was put in reach before the eye came to it)
	{
		FTransform Reached = InSupportReach(Character, Rig, Hold, SupportReachLast, StockOff);
		Reached.SetTranslation(FMath::Lerp(Reached.GetTranslation(), Hold.GetTranslation(), static_cast<double>(Ads)));
		Hold = InFiringReach(Character, Rig, Reached);
	}
	Hold = InFiringRange(Character, Rig, Hold, Dt);
	Held->SetWorldTransform(Hold);
	SetWorldTransform(Hold);
	// A reload's hand in flight between two places flies in the BODY's space (USOGunRigComponent::SetShowLead): from where
	// the gun WAS when the hand let go (kept in the show's own frame, the view's), to where the gun WILL be when the hand
	// arrives: the show of the place it is flying to, with what the hands' reach and the handling lay on the show now
	// carried along by as much as the reload's pose is in. Both in the gun's own frame of now.
	if (USOGunRigComponent* Shown = Weapon ? Weapon->GetRig() : nullptr)
	{
		FTransform Lead = FTransform::Identity, Left = FTransform::Identity;
		if (bShowing && bShowFlight && Weapon->IsReloading() && Ads < 0.99f)
		{
			const FTransform Frame = ShowFrame(Character);
			if (bFlightBegan)
			{
				FlightHold = Hold.GetRelativeTransform(Frame);
				bFlightBegan = false;
			}
			const float In = ReloadK * ReloadK * (3.0f - 2.0f * ReloadK);
			FTransform Laid;
			Laid.Blend(FTransform::Identity, ReloadPose(Character).Inverse() * Hold, In);
			const FTransform RigNow = Shown->GetComponentTransform();
			const FTransform OnHold = RigNow.GetRelativeTransform(Hold);
			FTransform Then = (OnHold * (ReloadPose(Character, ShowTo) * Laid)).GetRelativeTransform(RigNow);
			Then.SetScale3D(FVector::OneVector);
			Lead.Blend(FTransform::Identity, Then, 1.0f - Ads);
			Left = (OnHold * (FlightHold * Frame)).GetRelativeTransform(RigNow);
			Left.SetScale3D(FVector::OneVector);
		}
		else
		{
			bFlightBegan = false;
		}
		Shown->SetShowLead(Lead, Left);
	}
}

FTransform USOViewmodelComponent::ShowFrame(const ASOCharacter* Character) const
{
	const FTransform Eye = Character->GetEyeTransform(false);
	FRotator View = Eye.Rotator();
	View.Pitch = FMath::Clamp(FRotator::NormalizeAxis(View.Pitch), -35.0f, 35.0f);
	View.Roll = 0.0f;
	return FTransform(View.Quaternion(), Eye.GetLocation());
}

bool USOViewmodelComponent::GetShoulderPoints(const ASOCharacter* Character, FVector& OutPocket, FVector& OutChest) const
{
	// Actor space (X forward, Y right, Z up). From the body's last animated pose, so the stance (aim pitch, blade,
	// lean, the clip) carries the shoulder; the pocket's offset turns with the chest.
	OutPocket = DefaultPocket;
	OutChest = FVector(DefaultPocket.X, 0.0f, DefaultPocket.Z + 4.0f);
	const USkeletalMeshComponent* Body = Character->GetMesh();
	const USkeletalMesh* Mesh = Body ? Body->GetSkeletalMeshAsset() : nullptr;
	if (!Mesh)
	{
		return false;
	}
	const int32 ArmR = Body->GetBoneIndex(TEXT("upperarm_R")), ArmL = Body->GetBoneIndex(TEXT("upperarm_L"));
	const int32 Chest = Body->GetBoneIndex(TEXT("chest"));
	const TArray<FTransform>& CS = Body->GetComponentSpaceTransforms();
	if (ArmR == INDEX_NONE || ArmL == INDEX_NONE || Chest == INDEX_NONE || !CS.IsValidIndex(FMath::Max3(ArmR, ArmL, Chest)))
	{
		return false;
	}
	const FTransform ToActor = Body->GetRelativeTransform(); // the body hangs off the capsule (the actor's root)
	const FTransform RefChest = FAnimationRuntime::GetComponentSpaceTransformRefPose(Mesh->GetRefSkeleton(), Chest);
	const FQuat ChestTurn = CS[Chest].GetRotation() * RefChest.GetRotation().Inverse();
	const FVector OffsetCS = ToActor.InverseTransformVectorNoScale(PocketFromShoulder);
	OutPocket = ToActor.TransformPosition(CS[ArmR].GetLocation() + ChestTurn.RotateVector(OffsetCS / ToActor.GetScale3D()));
	OutChest = ToActor.TransformPosition((CS[ArmR].GetLocation() + CS[ArmL].GetLocation()) * 0.5f);
	return true;
}

FTransform USOViewmodelComponent::HoldTransform(const ASOCharacter* Character, const USOWeaponData* Data, bool bHandgun, float Dt, float RunT)
{
	const FTransform Actor = Character->GetActorTransform();
	FVector Pocket, Chest;
	GetShoulderPoints(Character, Pocket, Chest);
	const ASOWeapon* Weapon = Character->GetWeapon();
	const USOGunRigComponent* Rig = Weapon ? Weapon->GetRig() : nullptr;
	// the gun's class: where it rides relaxed, at the ready and on the sights (FSOStance, Data/stances.json)
	const FSOStance& St = FSOStanceData::Get().For(Data ? Data->Family : NAME_None);
	const FQuat Facing = FRotator(0.0f, Character->GetAimRotation().Yaw, 0.0f).Quaternion();

	// Where the gun points: the crosshair's point, never nearer than a few metres (a wall at arm's length would
	// swing the muzzle sideways), eased so a trace flicking between near and far things never snaps the gun.
	const FVector Eye = Character->GetEyeTransform(true).GetLocation();
	FVector Target = Character->GetAimTarget();
	const FVector ToTarget = Target - Eye;
	if (ToTarget.SizeSquared() < FMath::Square(MinAimDistance))
	{
		Target = Eye + Character->GetEyeTransform(true).GetRotation().GetForwardVector() * MinAimDistance;
	}
	FVector Start;
	const FBox B = Rig && Rig->IsBuilt() ? Rig->GetRigBounds() : FBox(FVector(-20.0f, -3.0f, -12.0f), FVector(40.0f, 3.0f, 10.0f));
	FVector Butt(B.Min.X + 1.0f, 0.0f, FMath::Clamp(ButtHeight, B.Min.Z + 4.0f, B.Max.Z - 4.0f));
	// Pointed steeply down the stock comes off the shoulder: the gun is held lower, in front of the body and nearer
	// its middle, both hands on it with the elbows bent (a man pointing a rifle at the ground); from the shoulder
	// pocket it pointed down along the body, the support hand beyond reach and the firing hand at the hip (the
	// owner, 2026-11-20: "looking down completely ... the players hand splits and the gun moves weirdly").
	const float PitchDeg = FRotator::NormalizeAxis(Character->GetAimRotation().Pitch);
	// (only off the sights: on them a long gun stays shouldered at any pitch and the trunk bows with the aim,
	// USOLocomotionAnimInstance; a handgun comes up to the eyes)
	const float Down = FMath::Clamp((-PitchDeg - 20.0f) / 50.0f, 0.0f, 1.0f) * (1.0f - Ads * (bHandgun ? 0.35f : 1.0f));
	if (bHandgun)
	{
		Start = Actor.TransformPosition(Chest + FVector(6.0f, 0.0f, -14.0f) * Down);
	}
	else
	{
		const FVector Low = Chest + LowHold;                               // low and ahead of the chest, a little right
		// (at 10 cm ahead the gun hung against the belly and thighs with the hands stacked on it)
		// (the butt in the shoulder pocket, raised by the class at the ready so the gun is up and forward; on the sights
		// the sight goes on the eyes' line: UpdateHold. The raise is the CHEST's: on the sights looking down the trunk
		// bows with the aim, USOLocomotionAnimInstance (up to 95 % of it to 70 degrees), and a raise kept upright pushed
		// the butt up the bowed chest toward the face: the firing arm folded into the body, its wrist bent past 85)
		FVector Shift = FMath::Lerp(St.ReadyShift, St.AimShift, Ads);
		if (PitchDeg < 0.0f && Ads > 0.0f)
		{
			const float BowDeg = FMath::Clamp(PitchDeg, FMath::Lerp(-40.0f, -70.0f, Ads), 0.0f) * FMath::Lerp(0.6f, 0.95f, Ads) * Ads;
			Shift = FRotator(BowDeg, 0.0f, 0.0f).RotateVector(Shift);
		}
		Start = Actor.TransformPosition(FMath::Lerp(Pocket + Shift, Low, Down));
		Butt.X = FMath::Lerp(Butt.X, Butt.X + 16.0f, Down);               // (the butt no longer in a pocket: the gun's middle hangs from the point)
	}
	FVector WantDir = (Target - Start).GetSafeNormal(1e-4f, Character->GetEyeTransform(true).GetRotation().GetForwardVector());
	// (on the sights along the eyes' line, as the sight is laid on it, UpdateHold: in the third-person test view the
	// crosshair's point is the shoulder camera's, and at the floor close under a gun aimed down it turned the shouldered
	// gun a few degrees off the line the sight then went onto, and the firing wrist past its range)
	WantDir = FMath::Lerp(WantDir, Character->GetEyeTransform(true).GetRotation().GetForwardVector(), static_cast<double>(Ads)).GetSafeNormal(1e-4f, WantDir);
	// The gun's own pitch is held within what a body can do (a rifle at the low ready points down at most about 55
	// degrees: the shooter bends to look at the ground, the stock stays under the arm): pointed straight down from
	// the chest the stock stood up along the face (the owner, 2026-11-21). The shot still goes where the eyes look.
	if (!bHandgun)
	{
		FRotator R = WantDir.Rotation();
		// (on the sights it points where the eyes look, the trunk bowing under it, USOLocomotionAnimInstance: held at 48
		// while the sight's line went to 60, the gun turned 12 degrees about its sight, the butt rose into the face and the
		// firing arm folded into the body)
		R.Pitch = FMath::Clamp(static_cast<float>(R.Pitch), FMath::Lerp(-MaxDownPitch, -80.0f, Ads), MaxUpPitch);
		R.Pitch -= St.ReadyDip * (1.0f - Ads);                      // (at the ready the muzzle a touch under the line)
		WantDir = R.Vector();
	}
	// (eased so a trace flicking between near and far things never snaps the gun, in the VIEW's own frame: the view's own
	// turn is taken whole. Eased in the world's frame the gun trailed every turn of the view by a share that changed with
	// each frame's length, and shook in the picture as the player turned, half a centimetre a frame at a quick turn: the
	// owner, 2026-11-23, "Camera is still very shake in first person")
	const FQuat ViewQ = Character->GetEyeTransform(true).GetRotation();
	const FVector WantView = ViewQ.UnrotateVector(WantDir);
	if (!bHoldDirValid || Dt > 0.2f)
	{
		HoldDirView = WantView;
		bHoldDirValid = true;
	}
	else
	{
		HoldDirView = FQuat::Slerp(FQuat::Identity, FQuat::FindBetweenNormals(HoldDirView, WantView), 1.0f - FMath::Exp(-30.0f * Dt)).RotateVector(HoldDirView).GetSafeNormal();
	}
	HoldDir = ViewQ.RotateVector(HoldDirView);
	FRotator AimRot = HoldDir.Rotation(); // level roll
	if (!bHandgun)
	{
		// held low the gun cants a little inward (the top toward the body's left), as a rifle carried at the low
		// ready does: the firing wrist stays nearer straight on the grip
		AimRot.Roll = -LowCant * Down;
	}
	const FQuat Aim = AimRot.Quaternion();
	FTransform Hold;
	if (bHandgun)
	{
		// both arms out, the gun a little right of the middle, rising toward the eye line when aiming
		Hold = FTransform(Aim, Start + Aim.RotateVector(FMath::Lerp(St.HandHold, St.HandAimHold, Ads)));
	}
	else
	{
		Hold = FTransform(Aim, Start - Aim.RotateVector(Butt));
		// (a long fore end past the support arm's reach: the gun comes in toward that shoulder, InSupportReach)
	}

	// The gun framed in the picture (the owner, 2026-11-23: "the pistol and hand cannon are good but the rest are bad and
	// need to be in the screen more just like the pistol/hand cannon ... this fix should be automated because what if we
	// have a fov slider"): off the sights the camera settles behind the eyes by the class's FrameBack, and under them and
	// toward the gun's side as far as FrameDrop and FrameSide allow, so that the sight of the gun at the ready lies
	// FrameDown of the way down the picture and FrameAcross of the way across, for the field of view the player has set
	// and the picture's shape (ASOCharacter::SetFrame). Worked out from the READY hold (before the relaxed carry, the
	// sprint and the reload) and the camera as it follows the head (the walk's lean in it: walking the eyes go 5 cm
	// forward), only while the view is near level and off the sights: looking up or down, or on the sights, the last
	// answer holds (the camera would slide about as the player looked at the floor). Eased slowly, so a switch of gun or
	// of the field of view glides and nothing ever shakes. The body is not moved for it (moved up or in, a long gun put
	// the firing elbow across the chest). On the sights the camera goes to the sight's line as before.
	{
		const bool bFrames = St.FrameDrop > 0.0f || St.FrameSide > 0.0f || St.FrameBack > 0.0f;
		SOSpring::Step(FrameBack, FrameBackVel, bFrames ? St.FrameBack : 0.0f, 3.0f, 1.0f, FMath::Min(Dt, 0.1f));
		float Want = bFrames ? FrameWant : 0.0f, WantSide = bFrames ? FrameSideWant : 0.0f;
		if (Weapon && Rig && Rig->IsBuilt() && bFrames && Down <= 0.0f && PitchDeg < 20.0f && Ads < 0.02f)
		{
			const FVector SightRig = USOGunRigComponent::MeshToRig(Weapon->GetSightLocation());
			const FTransform Capsule = Character->GetCapsuleComponent()->GetComponentTransform();
			const FVector Cam = Capsule.TransformPosition(Character->GetHeadCameraCS() - FVector(St.FrameBack, 0.0f, 0.0f));
			const FQuat View = Character->GetEyeTransform(false).GetRotation();
			const FVector L = View.UnrotateVector(Hold.TransformPosition(SightRig) - Cam);   // (forward, right, up)
			if (L.X > 5.0f)
			{
				float Aspect = 16.0f / 9.0f;
				if (GEngine && GEngine->GameViewport)
				{
					FVector2D Size;
					GEngine->GameViewport->GetViewportSize(Size);
					if (Size.X > 1.0 && Size.Y > 1.0)
					{
						Aspect = static_cast<float>(Size.X / Size.Y);
					}
				}
				const float TanH = FMath::Tan(FMath::DegreesToRadians(FMath::Clamp(Character->GetHipFov(), 40.0f, 140.0f) * 0.5f)), TanV = TanH / Aspect;
				const float Yt = 1.0f - 2.0f * St.FrameDown;                                 // (the picture's height, -1 at the foot)
				const float Xt = 2.0f * St.FrameAcross - 1.0f;                               // (its width, -1 at the left)
				// (the camera h lower sees the sight h higher: (L.Z + h) / (L.X TanV) = Yt; s to the right sees it s further
				// left: (L.Y - s) / (L.X TanH) = Xt)
				Want = FMath::Clamp(Yt * static_cast<float>(L.X) * TanV - static_cast<float>(L.Z), 0.0f, St.FrameDrop);
				WantSide = FMath::Clamp(static_cast<float>(L.Y) - Xt * static_cast<float>(L.X) * TanH, 0.0f, St.FrameSide);
			}
			FrameWant = Want;
			FrameSideWant = WantSide;
		}
		SOSpring::Step(FrameDrop, FrameDropVel, Want, 3.0f, 1.0f, FMath::Min(Dt, 0.1f));   // (UpdateHold hands all three to the body)
		SOSpring::Step(FrameSide, FrameSideVel, WantSide, 3.0f, 1.0f, FMath::Min(Dt, 0.1f));
	}
	// Relaxed (out of a fight, FSOStance): the gun lowered from the ready, turned about the firing hand's place on it (the
	// hand stays where it is at the ready, the muzzle dips and turns in round it), so from the eyes it stays in the lower
	// right of the picture (the owner, 2026-11-23: "weapons are not very visible ... so we see more of the gun when
	// idle/walking": carried low across the body it was out of the picture altogether, at any height of the camera;
	// turned about its butt the fore end dropped out of the support arm's reach and the gun was pulled back into the
	// middle). It comes up to the ready on a shot, an aim, a reload or a hit (ASOCharacter::GetCombatReady), never a body
	// walking about on the sights.
	if (const float Relax = (1.0f - Character->GetCombatReady()) * (1.0f - Ads) * (1.0f - InspectK); Relax > 1e-3f)
	{
		// (about the firing hand's place on the gun, or toward the support hand's: FSOStance::RelaxPivot)
		FVector Grip = FVector::ZeroVector;
		FTransform RT, LT;
		if (Rig && Rig->IsBuilt() && Rig->GetHandTargets(RT, LT))
		{
			const FTransform InRig = Rig->GetComponentTransform();
			Grip = FMath::Lerp(InRig.InverseTransformPosition(RT.GetLocation()), InRig.InverseTransformPosition(LT.GetLocation()),
				static_cast<double>(FMath::Clamp(St.RelaxPivot, 0.0f, 1.0f)));
		}
		const FVector Pivot = Hold.TransformPosition(Grip);
		const FQuat Turn = Facing * St.RelaxRot.Quaternion() * Facing.Inverse();   // (pitch, yaw, roll in the body's facing)
		const FTransform Lowered(Turn * Hold.GetRotation(), Pivot + Turn.RotateVector(Hold.GetLocation() - Pivot) + Facing.RotateVector(St.RelaxOffset));
		FTransform Eased;
		Eased.Blend(Hold, Lowered, Relax * Relax * (3.0f - 2.0f * Relax));
		Hold = Eased;
	}
	return Hold;
}

FTransform USOViewmodelComponent::OffTheShoulder(const ASOCharacter* Character, const USOWeaponData* Data, bool bHandgun, float RunT, const FTransform& In) const
{
	// Off the shoulder: a sprint carries the gun low across the chest (muzzle down and to the left); a reload brings it
	// down in front of the chest, canted so the support hand works the mag well in front of the body. Blended onto the hold
	// AFTER the hands' reach has been laid on it (movement pass 5): the long guns' hold at the ready sits on the support
	// arm's reach, and laid on the blend, the reach let go of the gun the frame the carry's turn brought the fore end in,
	// and the gun turned back on itself, 5 cm a frame setting off into a sprint; now its hold on the gun fades as the carry
	// comes in.
	FTransform Hold = In;
	const FTransform Actor = Character->GetActorTransform();
	FVector Pocket, Chest;
	GetShoulderPoints(Character, Pocket, Chest);
	const FQuat Facing = FRotator(0.0f, Character->GetAimRotation().Yaw, 0.0f).Quaternion();
	const float Reload = ReloadK * ReloadK * (3.0f - 2.0f * ReloadK) * (1.0f - Ads);
	if (RunT > 1e-3f || Reload > 1e-3f)
	{
		// (as the gun's data says: low, short, high; a gun that says nothing, a handgun high and anything else low)
		const FName Style = Data ? Data->SprintCarry : NAME_None;
		const bool bHigh = Style == TEXT("high") || (Style.IsNone() && bHandgun), bShort = Style == TEXT("short");
		const FTransform Carry(Facing * (bHigh ? HandgunCarryRot : (bShort ? ShortCarryRot : CarryRot)).Quaternion(),
			Actor.TransformPosition(Chest + (bHigh ? HandgunCarryOffset : (bShort ? ShortCarryOffset : CarryOffset))));
		FTransform Blended;
		Blended.Blend(Hold, Carry, RunT);
		Hold = Blended;
		if (Reload > 1e-3f)
		{
			Blended.Blend(Hold, ReloadPose(Character), Reload);
			Hold = Blended;
		}
	}
	return Hold;
}

void USOViewmodelComponent::KeepReloadWork(const ASOWeapon* Weapon, const USOGunRigComponent* Rig)
{
	if (!Weapon || !Rig || !Rig->IsBuilt() || ((Weapon->IsReloading() || ReloadK > 0.02f) && ReloadWorkRig.Get() == Rig))
	{
		return;
	}
	// The part the hands work in this gun's reload (SOReload::GetStyle): a revolver's cylinder (the crane swings it out to
	// the left), a bolt-action's bolt, a pump's loading port under the receiver (where the shell channel puts a shell in),
	// a light gun's or a living gun's flap, else the magazine (a light gun's cell is its part "mag").
	const FName Style = SOReload::GetStyle(Rig->GetArchetype());
	const FTransform RigT = Rig->GetComponentTransform();
	auto CentreOf = [&](const TCHAR* Name, FVector& Out)
	{
		const UStaticMeshComponent* Part = Rig->GetPart(Name);
		const UStaticMesh* Mesh = Part ? Part->GetStaticMesh() : nullptr;
		if (!Mesh)
		{
			return false;
		}
		Out = RigT.InverseTransformPosition(Part->GetComponentTransform().TransformPosition(Mesh->GetBoundingBox().GetCenter()));
		return true;
	};
	const bool bFlap = Style == TEXT("vent") || Style == TEXT("intake") || Style == TEXT("vr_fusion") || Style == TEXT("vr_rocket")
		|| Style == TEXT("bile") || Style == TEXT("brood") || Style == TEXT("spitter");
	FVector Work = FVector::ZeroVector;
	bool bFound = false;
	if (Style == TEXT("revolver"))
	{
		bFound = CentreOf(TEXT("cylinder"), Work);
	}
	else if (Style == TEXT("bolt"))
	{
		bFound = CentreOf(TEXT("bolt"), Work);
	}
	else if (Style == TEXT("pump"))
	{
		Work = USOGunRigComponent::MeshToRig(USOGunRigComponent::GltfToMesh(0.0f, -0.012f, 0.065f));
		bFound = true;
	}
	else if (bFlap)
	{
		bFound = CentreOf(TEXT("hatch"), Work);
	}
	bFound = bFound || CentreOf(TEXT("mag"), Work) || CentreOf(TEXT("hatch"), Work);
	if (!bFound)
	{
		Work = USOGunRigComponent::MeshToRig(Rig->ResolveAnchor(TEXT("mag")));
	}
	ReloadWork = Work;
	// (the side of the bore it lies on: under it, on its left, on its top or its right)
	const float BoreZ = static_cast<float>(RigT.InverseTransformPosition(Rig->GetMuzzleLocation()).Z);
	FVector2D Side(static_cast<float>(Work.Y), static_cast<float>(Work.Z) - BoreZ);
	if (Style == TEXT("revolver") || Side.Size() < 1.5f)
	{
		Side = Style == TEXT("revolver") ? FVector2D(-1.0f, 0.0f) : FVector2D(0.0f, -1.0f);
	}
	ReloadSide = Side.GetSafeNormal();
	ReloadWorkRig = Rig;
}

FTransform USOViewmodelComponent::ReloadPose(const ASOCharacter* Character, const float* Show) const
{
	// (Show: another show than the one the gun is in now, ShowNow: where the gun would be in it)
	const float* S = Show ? Show : ShowNow;
	// The show (ShowNow): where the FIRING hand holds the gun (the top of its grip: the rig's origin) in the picture at the
	// player's field of view and the picture's shape, so far ahead of the eyes, in the view's frame (its pitch held within
	// 35 degrees: the arms carry the gun up and down with the look only so far), and the gun turned about that hand. The
	// hand stays LOW, near the foot of the picture, and the gun is turned UP about it, so the gun stands up into the middle
	// of the picture and both forearms come to it from below with their wrists straight (the owner, 2026-11-27, of the
	// reference: "just compare where their arms are and how to fix yours": in it the firing fist never leaves the foot of
	// the picture). Placed by the part the reload works instead, as it first was, the hands went up to the chin with the
	// gun and the arms folded in front of the face.
	const FTransform Eye = Character->GetEyeTransform(false);
	FRotator View = Eye.Rotator();
	View.Pitch = FMath::Clamp(FRotator::NormalizeAxis(View.Pitch), -35.0f, 35.0f);
	View.Roll = 0.0f;
	const FQuat ViewQ = View.Quaternion();
	float Aspect = 16.0f / 9.0f;
	if (GEngine && GEngine->GameViewport)
	{
		FVector2D Size;
		GEngine->GameViewport->GetViewportSize(Size);
		if (Size.X > 1.0 && Size.Y > 1.0)
		{
			Aspect = static_cast<float>(Size.X / Size.Y);
		}
	}
	const float TanH = FMath::Tan(FMath::DegreesToRadians(FMath::Clamp(Character->GetHipFov(), 40.0f, 140.0f) * 0.5f)), TanV = TanH / Aspect;
	const float Ahead = FMath::Clamp(S[0], 15.0f, 80.0f);
	const FVector Target = Eye.GetLocation() + ViewQ.RotateVector(FVector(Ahead, (2.0f * S[1] - 1.0f) * Ahead * TanH, -(2.0f * S[2] - 1.0f) * Ahead * TanV));
	// The gun's turn: the muzzle up and in, then rolled about its own bore, the top to the right (the left flank and the
	// underside to the eyes) or, negative, to the left
	const FQuat Turn = ViewQ * FRotator(S[3], -S[4], 0.0f).Quaternion() * FQuat(FVector::ForwardVector, -FMath::DegreesToRadians(S[5]));
	FTransform Pose(Turn, Target);
	// The part the reload works stays in the picture (the owner, 2026-11-24: "so reload is visible and the player can see
	// the magazine fully"): where the gun turned about the firing hand leaves it outside (a launcher's flap far along its
	// flank, a bolt behind the grip, a pistol's magazine in the foot of the picture), the whole gun, the hand with it, is
	// moved in the picture's own plane the least that brings it in, a hand's breadth at most (the arm's reach and range
	// have the last word, UpdateHold).
	const FVector Work = ViewQ.UnrotateVector(Pose.TransformPosition(ReloadWork) - Eye.GetLocation());   // (ahead, right, up)
	if (Work.X > 8.0)
	{
		const float Across = 0.5f + 0.5f * static_cast<float>(Work.Y / Work.X) / TanH, Down = 0.5f - 0.5f * static_cast<float>(Work.Z / Work.X) / TanV;
		// (a handgun's magazine is in its grip, in the firing hand, and that hand stays low: it comes in from the foot of
		// the picture, as in the owner's reference; lifted to show the whole of it, the pistol stood in front of the face)
		const bool bHandgun = ReloadWorkRig.IsValid() && ReloadWorkRig->IsHandgun();
		const FVector Shift(0.0f, (FMath::Clamp(Across, 0.2f, 0.84f) - Across) * 2.0f * TanH * static_cast<float>(Work.X),
			-(FMath::Clamp(Down, 0.16f, bHandgun ? 0.93f : 0.82f) - Down) * 2.0f * TanV * static_cast<float>(Work.X));
		Pose.AddToTranslation(ViewQ.RotateVector(Shift.GetClampedToMaxSize(12.0f)));
	}
	return Pose;
}

void USOViewmodelComponent::Handle(FName Event)
{
	// One beat of the handling (a reload's sound events, ASOWeapon -> ASOCombatCharacter::OnWeaponHandled): the gun is
	// knocked in the hands as far as the beat says (a spring's kick: the speed that throws it that far) and settles
	const FSOReloadShowData& Shows = FSOReloadShowData::Get();
	if (const FSOHandlingBeat* Beat = Shows.Beat(Event))
	{
		// (an underdamped spring knocked at speed v goes about 0.55 v / omega far at a damping near a half)
		const float Speed = Shows.JoltOmega / 0.55f;
		JoltMoveVel += Beat->GunMove * Speed;
		JoltTurnVel += Beat->GunTurn * Speed;
	}
}

FTransform USOViewmodelComponent::ClearOfWalls(const ASOCharacter* Character, const USOGunRigComponent* Rig, const FTransform& Hold, float Dt)
{
	// One gun in the body's hands, seen from its own eyes: it must never go into a wall in front (a gun of its own drawn
	// for the eyes could pass through walls; the one in the hands cannot). Swept from the butt along the barrel; what is
	// in the way pulls the gun back along itself (up to a third of its length), and beyond that the muzzle turns up past
	// it (the high ready), eased in and out as a spring.
	float Want = 0.0f;
	const UWorld* World = Character->GetWorld();
	if (Rig && Rig->IsBuilt() && World)
	{
		const FBox B = Rig->GetRigBounds();
		const float Length = static_cast<float>(B.Max.X - B.Min.X);
		const FVector Axis = Hold.GetRotation().GetForwardVector();
		const FVector From = Hold.TransformPosition(FVector(B.Min.X + 2.0f, 0.0f, 0.0f));
		FCollisionQueryParams Params(SCENE_QUERY_STAT(SOGunWall), false, Character);
		Params.AddIgnoredActor(Character->GetWeapon());
		FHitResult Hit;
		if (World->SweepSingleByChannel(Hit, From, From + Axis * (Length + 4.0f), FQuat::Identity, ECC_Visibility, FCollisionShape::MakeSphere(2.5f), Params))
		{
			Want = FMath::Clamp(Length + 4.0f - static_cast<float>(Hit.Distance), 0.0f, Length);
		}
	}
	Spring(WallK, WallV, Want, 18.0f, 0.95f, FMath::Min(Dt, 0.1f));
	WallK = FMath::Max(WallK, 0.0f);
	if (WallK < 0.2f || !Rig || !Rig->IsBuilt())
	{
		return Hold;
	}
	const FBox B = Rig->GetRigBounds();
	const float Length = static_cast<float>(B.Max.X - B.Min.X);
	const float Back = FMath::Min(WallK, Length * 0.33f);
	const float Up = FMath::Clamp((WallK - Back) / FMath::Max(Length * 0.5f, 1.0f), 0.0f, 1.0f) * 60.0f;
	FTransform Out = Hold;
	Out.AddToTranslation(-Hold.GetRotation().GetForwardVector() * Back);
	if (Up > 0.1f)
	{
		// turned about the grip (the rig's origin, where the hand is): the muzzle up, the butt down
		const FQuat Raise(Hold.GetRotation().GetRightVector(), -FMath::DegreesToRadians(Up));
		Out.SetRotation(Raise * Out.GetRotation());
	}
	return Out;
}

float USOViewmodelComponent::HandgunRelief(const ASOCharacter* Character, const USOGunRigComponent* Rig, const FVector& SightRig, const FTransform& Eye) const
{
	// Held out in both hands, the sight on the eyes' line: as far ahead as puts the firing wrist at HandgunReach of the
	// arm from its shoulder in the body's last pose (the arms nearly straight). The wrist with the sight at the eye is
	// P0; with it Relief further ahead, P0 + Forward x Relief: on a sphere round the shoulder.
	const USkeletalMeshComponent* Body = Character->GetMesh();
	FTransform R, L;
	if (!Body || !Rig->GetHandTargets(R, L))
	{
		return AdsHandgunSightDistance;
	}
	const int32 Sh = Body->GetBoneIndex(TEXT("upperarm_R")), El = Body->GetBoneIndex(TEXT("forearm_R")), Wr = Body->GetBoneIndex(TEXT("hand_R"));
	if (Sh == INDEX_NONE || El == INDEX_NONE || Wr == INDEX_NONE)
	{
		return AdsHandgunSightDistance;
	}
	const FVector Shoulder = Body->GetBoneLocation(Body->GetBoneName(Sh));
	const FVector Elbow = Body->GetBoneLocation(Body->GetBoneName(El));
	const float Arm = static_cast<float>(FVector::Dist(Shoulder, Elbow) + FVector::Dist(Elbow, Body->GetBoneLocation(Body->GetBoneName(Wr))));
	const FVector Forward = Eye.GetRotation().GetForwardVector();
	// the furthest the wrist at InGun may be held out along the eyes' line, Reach of an arm Length from Joint
	auto Furthest = [&](const FVector& InGun, const FVector& Joint, float Reach, float Length)
	{
		const FVector D = Eye.TransformPosition(InGun - SightRig) - Joint;
		const float Bq = static_cast<float>(FVector::DotProduct(Forward, D));
		const float Disc = Bq * Bq - (static_cast<float>(D.SizeSquared()) - FMath::Square(Reach * Length));
		return Disc < 0.0f ? -1.0f : -Bq + FMath::Sqrt(Disc);
	};
	float Relief = Furthest(Rig->GetComponentTransform().InverseTransformPosition(R.GetLocation()), Shoulder, HandgunReach, Arm);
	if (Relief < 0.0f)
	{
		return AdsHandgunSightDistance;
	}
	// (and the support hand round it: no further out than that arm reaches either)
	FVector SupportInGun, SupportShoulder;
	float SupportLength = 0.0f;
	if (SupportArm(Character, Rig, SupportInGun, SupportShoulder, SupportLength))
	{
		const float Support = Furthest(SupportInGun, SupportShoulder, FMath::Min(HandgunReach, SupportReach), SupportLength);
		if (Support > 0.0f)
		{
			Relief = FMath::Min(Relief, Support);
		}
	}
	return FMath::Clamp(Relief, 16.0f, 60.0f);
}

bool USOViewmodelComponent::SupportArm(const ASOCharacter* Character, const USOGunRigComponent* Rig, FVector& OutInGun, FVector& OutShoulder, float& OutArm) const
{
	const USkeletalMeshComponent* Body = Character->GetMesh();
	FTransform R, L;
	if (!Body || !Rig || !Rig->IsBuilt() || !Rig->GetHandTargets(R, L))
	{
		return false;
	}
	const int32 Sh = Body->GetBoneIndex(TEXT("upperarm_L")), El = Body->GetBoneIndex(TEXT("forearm_L")), Wr = Body->GetBoneIndex(TEXT("hand_L"));
	if (Sh == INDEX_NONE || El == INDEX_NONE || Wr == INDEX_NONE)
	{
		return false;
	}
	OutShoulder = Body->GetBoneLocation(Body->GetBoneName(Sh));
	const FVector Elbow = Body->GetBoneLocation(Body->GetBoneName(El));
	OutArm = static_cast<float>(FVector::Dist(OutShoulder, Elbow) + FVector::Dist(Elbow, Body->GetBoneLocation(Body->GetBoneName(Wr))));
	// where the hand is fitted on this gun (the rig's own target, moved onto the gun's surfaces); an inspect's hand where
	// its choreography has it (a handle, a hatch: the fit is the fore end's)
	OutInGun = Rig->GetComponentTransform().InverseTransformPosition(L.GetLocation());
	const ASOWeapon* Weapon = Character->GetWeapon();
	const bool bAway = Weapon && Weapon->IsInspecting() && Weapon->GetPose().bHand
		&& !(Weapon->GetPose().HandAnchorA == TEXT("fore") && Weapon->GetPose().HandAnchorB == TEXT("fore"));
	if (const USOLocomotionAnimInstance* Anim = Cast<USOLocomotionAnimInstance>(Body->GetAnimInstance()); Anim && Anim->HasFittedGrip() && !bAway)
	{
		OutInGun += Anim->GetFittedOffset(true);
	}
	return true;
}

FTransform USOViewmodelComponent::InSupportReach(const ASOCharacter* Character, const USOGunRigComponent* Rig, const FTransform& Hold, float Reach, float StockOff) const
{
	// The support hand is on the gun too (the owner's ULTIMATE rule, 2026-11-23: "the gun is placed where the hand can
	// be, never the hand chasing a gun out of its reach"): its place on the gun past the support arm's reach (looking
	// far up or down, a long fore end) brings the gun in toward that shoulder. A long gun's butt goes no further back
	// than in front of the firing shoulder (pulled into it, the owner's "the gun is in the players shoulder"); what is
	// left the anim's hold slides the hand back along the gun for. Not while a reload or an action works the hand; an
	// inspect does, with the hand wherever its choreography has it on the gun (a handle, a hatch): turned to be looked at,
	// a long fore end went 8 cm past the support arm's reach and the arm hung straight with the palm off the gun.
	const ASOWeapon* Weapon = Character->GetWeapon();
	FVector InGun, Shoulder;
	float Arm = 0.0f;
	if (!Weapon || Weapon->IsReloading() || (Weapon->GetPose().bHand && !Weapon->IsInspecting()) || Character->HoldsWithOneHand()
		|| !SupportArm(Character, Rig, InGun, Shoulder, Arm))
	{
		return Hold;
	}
	const FVector Wrist = Hold.TransformPosition(InGun);
	const float D = static_cast<float>(FVector::Dist(Wrist, Shoulder));
	if (D <= Reach * Arm || D < 1e-3f)
	{
		return Hold;
	}
	FVector Move = (Shoulder - Wrist) / D * (D - Reach * Arm);
	// (pointed steeply down the stock is off the shoulder: the gun hangs in front of the body and comes in freely; so it
	// does carried relaxed by a class whose arms are easy then, FSOStance::RelaxReach)
	const float PitchDeg = FRotator::NormalizeAxis(Character->GetAimRotation().Pitch);
	const float Down = FMath::Max(FMath::Clamp((-PitchDeg - 20.0f) / 50.0f, 0.0f, 1.0f), FMath::Clamp(StockOff, 0.0f, 1.0f));
	// (and pointed steeply up the shoulder rises under the stock: a long fore end may bring it back a little further)
	const float Up = FMath::Clamp((PitchDeg - 35.0f) / 25.0f, 0.0f, 1.0f);
	if (!Rig->IsHandgun() && Down < 1.0f)
	{
		const USkeletalMeshComponent* Body = Character->GetMesh();
		const int32 ShR = Body->GetBoneIndex(TEXT("upperarm_R"));
		if (ShR != INDEX_NONE)
		{
			const FVector Axis = Hold.GetRotation().GetForwardVector();
			const FVector Butt = Hold.TransformPosition(FVector(Rig->GetRigBounds().Min.X, 0.0f, 0.0f));
			const float Room = FMath::Max(0.0f, static_cast<float>(FVector::DotProduct(Butt - Body->GetBoneLocation(Body->GetBoneName(ShR)), Axis)) - ButtAheadOfShoulder + 6.0f * Up) / FMath::Max(1.0f - Down, 1e-3f);
			const float Back = static_cast<float>(-FVector::DotProduct(Move, Axis));
			if (Back > Room)
			{
				Move += Axis * (Back - Room);
			}
		}
	}
	FTransform Out = Hold;
	Out.AddToTranslation(Move);
	return Out;
}

FTransform USOViewmodelComponent::InFiringRange(const ASOCharacter* Character, const USOGunRigComponent* Rig, const FTransform& Hold, float Dt)
{
	// The gun gives way to the firing hand's BONES (the owner, 2026-11-27: "humans have bones and can't bend their
	// hands/arms in such manner ... ensure these rules are always followed at all times for everything"; and the rule
	// from the first: nothing is solved by bending a joint further, the gun gives way). The firing hand is on its grip
	// whatever the gun does, so a gun turned where no wrist follows (looked over in an inspect, pointed at the floor from
	// the chest, carried across the body) would ask the arm solve's guard to turn the hand off the grip instead. Here the
	// hold is tried against the firing arm as an arm is measured (SOArmBones: the forearm's twist, the wrist's two ways),
	// at the elbow the body has; what is past the range is taken out of the GUN's turn, about the palm's place on the
	// grip, so the hand stays whole on its handle and the gun points as far as the arm lets it. A long gun only while it
	// is worked (a reload, an inspect) and a moment after, a handgun at any time (below). Off the sights only: on them the
	// gun lies on the eye's line and the stance carries the arm.
	FQuat Want = FQuat::Identity;
	FVector About = Hold.GetLocation();
	const USkeletalMeshComponent* Body = Character->GetMesh();
	const USkeletalMesh* Mesh = Body ? Body->GetSkeletalMeshAsset() : nullptr;
	FTransform R, L;
	if (Mesh && Rig && Rig->IsBuilt() && Ads < 0.98f && Rig->GetHandTargets(R, L))
	{
		const int32 Sh = Body->GetBoneIndex(TEXT("upperarm_R")), El = Body->GetBoneIndex(TEXT("forearm_R")), Wr = Body->GetBoneIndex(TEXT("hand_R"));
		const int32 Knuckle = Body->GetBoneIndex(TEXT("middle_01_R")), First = Body->GetBoneIndex(TEXT("index_01_R")), Last = Body->GetBoneIndex(TEXT("pinky_01_R"));
		const int32 Chest = Body->GetBoneIndex(TEXT("chest"));
		if (Sh != INDEX_NONE && El != INDEX_NONE && Wr != INDEX_NONE && Knuckle != INDEX_NONE && First != INDEX_NONE && Last != INDEX_NONE && Chest != INDEX_NONE)
		{
			const FReferenceSkeleton& Ref = Mesh->GetRefSkeleton();
			auto Rest = [&](int32 Bone) { return FAnimationRuntime::GetComponentSpaceTransformRefPose(Ref, Bone); };
			const FTransform HandRest = Rest(Wr);
			// (the hand bone against its anatomical basis, and its long line and thumb side in its own frame: as the arm solve has them)
			const FVector RestAlong = (HandRest.GetLocation() - Rest(El).GetLocation()).GetSafeNormal();
			const FQuat HandOffset = FSOHandGrip::MakeBasis(RestAlong, FVector(0.0f, 1.0f, 0.0f), false).Inverse() * HandRest.GetRotation();
			const FVector LineLocal = HandRest.GetRotation().UnrotateVector(Rest(Knuckle).GetLocation() - HandRest.GetLocation());
			const FVector ThumbLocal = HandRest.GetRotation().UnrotateVector(Rest(First).GetLocation() - Rest(Last).GetLocation());
			// (everything in the body's own component space, as the arm solve works: +X its left, +Y forward, +Z up)
			const TArray<FTransform>& CS = Body->GetComponentSpaceTransforms();
			if (!CS.IsValidIndex(FMath::Max3(Sh, El, Wr)) || !CS.IsValidIndex(Chest))
			{
				return Hold;
			}
			const FVector Sb = CS[Sh].GetLocation();
			const float L1 = static_cast<float>(FVector::Dist(Sb, CS[El].GetLocation())), L2 = static_cast<float>(FVector::Dist(CS[El].GetLocation(), CS[Wr].GetLocation()));
			// the hand on its grip in this hold (the fit's own seat on the grip with it)
			FTransform InGun = R.GetRelativeTransform(Rig->GetComponentTransform());
			if (const USOLocomotionAnimInstance* Anim = Cast<USOLocomotionAnimInstance>(Body->GetAnimInstance()))
			{
				InGun.AddToTranslation(Anim->GetFittedOffset(false));
				if (FQuat Fitted; Anim->GetFittedFiringBasis(Fitted))
				{
					InGun.SetRotation(Fitted);
				}
			}
			const FTransform Target = InGun * Hold;
			const FTransform ToWorld = Body->GetComponentTransform();
			const FTransform ToBody = ToWorld.Inverse();
			const FVector Wb = ToBody.TransformPosition(Target.GetLocation());
			const FQuat HandRot = (ToBody.GetRotation() * Target.GetRotation()) * HandOffset;
			const FVector LineNow = HandRot.RotateVector(LineLocal), ThumbNow = HandRot.RotateVector(ThumbLocal);
			const FQuat ChestCS = CS[Chest].GetRotation() * Rest(Chest).GetRotation().Inverse();
			const FVector FwdCS = ChestCS.RotateVector(FVector(0.0f, 1.0f, 0.0f)), UpCS = ChestCS.RotateVector(FVector(0.0f, 0.0f, 1.0f));
			const FVector To = Wb - Sb;
			const float D = FMath::Clamp(static_cast<float>(To.Size()), FMath::Abs(L1 - L2) + 0.5f, (L1 + L2) * 0.999f);
			const FVector Dir = To.GetSafeNormal(1e-4f, FVector(0.0f, 1.0f, 0.0f));
			FVector Down = -UpCS - Dir * FVector::DotProduct(-UpCS, Dir);
			if (L1 > 1.0f && L2 > 1.0f && Down.Normalize(1e-3f))
			{
				FVector Out = FVector::CrossProduct(Dir, Down);
				if (Out.X > 0.0f)
				{
					Out = -Out;                                          // (round the right arm's own side: the body's left is +X)
				}
				const float Along = (L1 * L1 - L2 * L2 + D * D) / (2.0f * D), Height = FMath::Sqrt(FMath::Max(L1 * L1 - Along * Along, 0.0f));
				const FVector WristAt = Sb + Dir * D;
				static const SOArmBones::FRange Human;
				// (while the gun is WORKED, a reload or an inspect: at the elbow the body HAS, on its way round the arm to this
				// wrist: the arm solve brings it to the swing that asks least, but only as fast as an elbow turns and never into
				// the trunk, so the best swing of all is not always the one it stands at, and what the gun did not give the
				// solve's guard took out of the hand's hold. Otherwise at the best swing of all: read at the elbow's own place
				// on a walk, whose every step sways it, the gun was nudged a little each step and jerked in the picture)
				// (and for a third of a second after: the work done, the firing elbow swings back out from under the gun to
				// where the stance carries it, and on the way round the arm the wrist is asked more than it has: the pistol's
				// hand was turned 18 degrees off its grip for six frames as its inspect ended)
				const ASOWeapon* Worked = Character->GetWeapon();
				WorkedTail = Worked && Worked->IsWorkingTheGun() ? 0.35f : FMath::Max(WorkedTail - Dt, 0.0f);
				// (a handgun's is read at the elbow the body has at all times: crouched on the move its elbow is not where the
				// best swing of all would have it, and what the gun did not give the guard took out of the revolver's hold,
				// 22 degrees; eased there, below, so a step's sway does not nudge it)
				const bool bWorked = WorkedTail > 0.0f || Rig->IsHandgun();
				// (a gun being WORKED is turned quickly, and the elbow read here is last frame's: it gives a little inside the
				// range, so what the frame's lag leaves is still inside it: at the range itself the pistol's inspect left the
				// hand 18 degrees to turn off its grip at the ends of its rolls)
				const float Edge = WorkedTail > 0.0f ? 0.93f : 1.0f;   // (a handgun at rest: the range itself, or it gave a little all the time and shook)
				FVector Round = CS[El].GetLocation() - Sb;
				Round -= Dir * FVector::DotProduct(Round, Dir);
				FVector Best = Sb + Dir * Along + (Round.Normalize(1e-3f) ? Round : Down) * Height;
				float Least = SOArmBones::Measure(Sb, Best, WristAt, LineNow, ThumbNow, false, FwdCS, UpCS).Asks(Human);
				if (!bWorked)
				{
					for (int32 i = 0; i <= 36; ++i)
					{
						const float Sw = FMath::Lerp(-0.6f, 1.7f, i / 36.0f);
						const FVector E = Sb + Dir * Along + (Down * FMath::Cos(Sw) + Out * FMath::Sin(Sw)) * Height;
						if (const float Asks = SOArmBones::Measure(Sb, E, WristAt, LineNow, ThumbNow, false, FwdCS, UpCS).Asks(Human); Asks < Least)
						{
							Least = Asks;
							Best = E;
						}
					}
				}
				// (only what is past the range itself: a shouldered gun's firing wrist is near the edge of its range wherever the
				// elbow hangs, and a rule set inside that turned the gun off its aim at the ready, a little more or less each
				// frame as the body moved: the gun shook in the picture)
				// (a long gun only while it is worked, and the moment after: in ordinary movement its holds are made inside the
				// arm's range (the stance, the low hold, the least reach), and a rifle that gave way there as the body rose
				// out of a slide turned back on itself in the picture, three jolts out of one slide. A handgun always: held out
				// in two hands on the body's middle line its firing wrist is near the edge of its range standing, and crouched
				// on the move the guard turned the revolver's hand 22 degrees off its grip)
				if (Least > Edge && bWorked)
				{
					const FQuat Allowed = SOArmBones::Within(Sb, Best, WristAt, HandRot, LineLocal, ThumbLocal, false, Human, Edge);
					// (the turn that takes the hand as this hold asks it onto the one the arm allows, in the world)
					Want = ToWorld.GetRotation() * (Allowed * HandRot.Inverse()) * ToBody.GetRotation();
				}
				About = Target.GetLocation() + Target.GetRotation().GetAxisX() * 5.0f + FSOHandGrip::PalmNormal(Target.GetRotation(), false) * 1.3f;
			}
		}
	}
	Want = FQuat::Slerp(FQuat::Identity, Want, 1.0f - FMath::Clamp(Ads, 0.0f, 1.0f)).GetNormalized();
	// (while the gun is WORKED it gives at once, as far as the arm asks, and comes back eased: eased both ways it trailed
	// a gun turned quickly in an inspect, and the hand was turned off its grip for the frames it took to catch up. In
	// ordinary movement it is eased both ways: a body setting off, coming out of a slide or starting to walk leans for a
	// few frames, the arm asks a little more than it has and less again, and a gun that gave at once and came back eased
	// sawed in the picture: the pistol's sight turned back three times in a fifth of a second, the rifle lurched 8 cm in a
	// frame out of a slide)
	const bool bAtOnce = WorkedTail > 0.0f && Want.GetAngle() >= RangeGive.GetAngle();
	RangeGive = Dt > 0.25f || bAtOnce ? Want : FQuat::Slerp(RangeGive, Want, 1.0f - FMath::Exp(-(WorkedTail > 0.0f ? 20.0f : 12.0f) * Dt)).GetNormalized();
	if (RangeGive.IsIdentity(1e-5f))
	{
		return Hold;
	}
	return FTransform(RangeGive * Hold.GetRotation(), About + RangeGive.RotateVector(Hold.GetLocation() - About), Hold.GetScale3D());
}

FTransform USOViewmodelComponent::InFiringReach(const ASOCharacter* Character, const USOGunRigComponent* Rig, const FTransform& Hold) const
{
	// The firing hand is always on its handle (the owner's ULTIMATE rule, 2026-11-23): the gun is never placed where the
	// hand cannot be. Its wrist's place on the gun (the rig rides the hold), against the firing shoulder in the body's
	// last pose: further than FiringReach of the arm, the gun comes in; folded closer than a third of it, out.
	const USkeletalMeshComponent* Body = Character->GetMesh();
	FTransform R, L;
	if (!Rig || !Rig->IsBuilt() || !Body || !Rig->GetHandTargets(R, L))
	{
		return Hold;
	}
	const int32 Sh = Body->GetBoneIndex(TEXT("upperarm_R")), El = Body->GetBoneIndex(TEXT("forearm_R")), Wr = Body->GetBoneIndex(TEXT("hand_R"));
	if (Sh == INDEX_NONE || El == INDEX_NONE || Wr == INDEX_NONE)
	{
		return Hold;
	}
	const FVector Shoulder = Body->GetBoneLocation(Body->GetBoneName(Sh));
	const FVector Elbow = Body->GetBoneLocation(Body->GetBoneName(El));
	const float Arm = static_cast<float>(FVector::Dist(Shoulder, Elbow) + FVector::Dist(Elbow, Body->GetBoneLocation(Body->GetBoneName(Wr))));
	// (the wrist where the hand is FITTED on this grip: the fit seats it on the backstrap, up to 6 cm from where the rig
	// has it, and a handgun's rule read 66 % of the arm where the body's wrist was at 57)
	FVector WristInGun = Rig->GetComponentTransform().InverseTransformPosition(R.GetLocation());
	if (const USOLocomotionAnimInstance* Anim = Cast<USOLocomotionAnimInstance>(Body->GetAnimInstance()))
	{
		WristInGun += Anim->GetFittedOffset(false);
	}
	const FVector Off = Hold.TransformPosition(WristInGun) - Shoulder;
	const float D = static_cast<float>(Off.Size());
	FTransform Out = Hold;
	if (D > FiringReach * Arm)
	{
		Out.AddToTranslation(-Off / FMath::Max(D, 1e-3f) * (D - FiringReach * Arm));
	}
	else if (const float Least = Rig->IsHandgun() ? HandgunReachLeast : FiringReachLeast; D < Least * Arm && D > 1e-3f)
	{
		Out.AddToTranslation(Off / D * (Least * Arm - D));
	}
	return Out;
}
