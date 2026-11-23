#pragma once

#include "CoreMinimal.h"
#include "Animation/AnimInstance.h"
#include "Animation/AnimInstanceProxy.h"
#include "SOCombatTypes.h"
#include "SOGunRigComponent.h"
#include "SOStance.h"
#include "SOLocomotionAnimInstance.generated.h"

class UAnimSequenceBase;

/** Clips the native locomotion graph uses (each body's own Blender set: Idle, Walk, Run, Jump, Death, Attack, Slide,
 *  and the idle variations it slips in while standing). */
USTRUCT(BlueprintType)
struct SOCHARACTER_API FSOLocomotionClips
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Clips")
	TObjectPtr<UAnimSequenceBase> Idle;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Clips")
	TObjectPtr<UAnimSequenceBase> Walk;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Clips")
	TObjectPtr<UAnimSequenceBase> Run;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Clips")
	TObjectPtr<UAnimSequenceBase> Jump;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Clips")
	TObjectPtr<UAnimSequenceBase> Death;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Clips")
	TObjectPtr<UAnimSequenceBase> Attack;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Clips")
	TObjectPtr<UAnimSequenceBase> Slide;

	/** The slow walk (a light stick, aiming, crouched). Without it the walk clip is slowed down instead. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Clips")
	TObjectPtr<UAnimSequenceBase> Stroll;

	/** The landing after a fall (blended in by how hard it was). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Clips")
	TObjectPtr<UAnimSequenceBase> Land;

	/** Crouched: still, and the crouched walk (authored down there, feet planted at CrouchSpeed). A body with both
	 *  plays them while crouched; without them the standing clips are sunk over bent legs (CrouchDrop). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Clips")
	TObjectPtr<UAnimSequenceBase> Crouch;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Clips")
	TObjectPtr<UAnimSequenceBase> CrouchWalk;

	/** Braking out of a run to a standstill (blended in by how fast the body was going). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Clips")
	TObjectPtr<UAnimSequenceBase> Stop;

	/** Over and onto obstacles: each is read by how far through the move the body is, never by the clock. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Clips")
	TObjectPtr<UAnimSequenceBase> Vault;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Clips")
	TObjectPtr<UAnimSequenceBase> Mantle;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Clips")
	TObjectPtr<UAnimSequenceBase> Climb;
	/** The dodge: a step out of the line to his left, right, back or ahead (0.32 s, played over the gait by the
	 *  movement's dodge; a body without them dodges on its gait and lean). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Clips")
	TObjectPtr<UAnimSequenceBase> DodgeL;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Clips")
	TObjectPtr<UAnimSequenceBase> DodgeR;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Clips")
	TObjectPtr<UAnimSequenceBase> DodgeB;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Clips")
	TObjectPtr<UAnimSequenceBase> DodgeF;

	/** Idle variations (Fidget1..n): one plays now and then while standing still and not aiming; each starts and ends
	 *  on the idle pose. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Clips")
	TArray<TObjectPtr<UAnimSequenceBase>> Fidgets;

	/** Ground speeds (cm/s) the walk and run clips were authored at; playback rate follows the real speed. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Clips")
	float WalkSpeed = 440.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Clips")
	float RunSpeed = 860.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Clips")
	float StrollSpeed = 150.0f;

	/** The ground speed the crouched walk was made for (cm/s). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Clips")
	float CrouchSpeed = 270.0f;
};

struct FSOLocomotionLayer
{
	const UAnimSequenceBase* Clip = nullptr;
	float Time = 0.0f;
	float Weight = 0.0f;
	bool bLoop = true;
};

/** Game-thread state machine + worker-thread pose blend; no animation blueprint needed. */
struct SOCHARACTER_API FSOLocomotionProxy : public FAnimInstanceProxy
{
	FSOLocomotionProxy() = default;
	explicit FSOLocomotionProxy(UAnimInstance* Instance) : FAnimInstanceProxy(Instance) {}

	virtual void PreUpdate(UAnimInstance* InAnimInstance, float DeltaSeconds) override;
	virtual bool Evaluate(FPoseContext& Output) override;
	/** Takes this frame's state from the instance. Called at the END of USOLocomotionAnimInstance::NativeUpdateAnimation:
	 *  the engine calls PreUpdate BEFORE NativeUpdateAnimation, so what was copied there was the frame before's (the
	 *  hands reached for where the gun had been a frame ago: every bob, kick and turn left them off it for a frame, the
	 *  owner's "the player hand keeps moving and feels like the player is not properly gripping the guns"). */
	void CopyFrom(const class USOLocomotionAnimInstance* Instance);

	/** 0 Idle, 1 Walk, 2 Run, 3 Jump, 4 Death, 5 Attack, 6 Slide, 7 Fidget, 8 Stroll, 9 Land, 10 Vault, 11 Mantle,
	 *  12 Climb, 13 Crouch, 14 CrouchWalk, 15 Stop */
	FSOLocomotionLayer Layers[17];

	// Held gun (players): copied from the instance each update.
	bool bHold = false;
	/** Only the right arm reaches for the gun (the left is busy: a shield). */
	bool bOneHand = false;
	bool bArmsOnly = false;
	bool bCollapseBody = false;
	bool bCarried = false;
	bool bHeadFree = false;     // the head carries its clip's own motion under the aim (a player's body, the stand-in); a creature's is held on its aim      // the gun carried low (a sprint, the armoury's stand-in): the firing elbow stays down
	float AimPitch = 0.0f;
	float Blade = 0.0f;
	float Lean = 0.0f;
	float HeadCant = 0.0f;   // degrees: aiming a long gun in third person, the head leans onto the stock
	/** The combat stance (FSOStance: the gun's class, the state); the body's share of it, and how still it stands. */
	FSOStanceInputs Stance;
	float StanceBody = 0.0f;
	float StanceStill = 0.0f;
	FTransform RightTarget;
	FTransform LeftTarget;
	bool bSupportOnPost = false;   // (the support hand is round a vertical fore grip: it may reach nearly straight)
	bool bSnugHold = false;        // (the gun is held the snug way: the first-person firing shoulder goes back from its hand)
	FSOFingerPose RightFingers;
	FSOFingerPose LeftFingers;
	/** Eye position in component space (first person: the shoulders turn with the view about it). */
	FVector EyeCS = FVector::ZeroVector;
	FVector GunAxis = FVector::ZeroVector;

	/** How much of the arm / stance solve shows (1 = all; hands coming onto and off a ledge blend through it). */
	float HoldAlpha = 1.0f;

	// Body motion (third-person bodies; see USOLocomotionAnimInstance).
	float WarpYaw = 0.0f;
	/** The hips and legs stay where they stood while the aim turns on the spot (degrees, see StandYaw). */
	float StandYaw = 0.0f;
	float MaxWaistTwist = 20.0f;
	float LeanRoll = 0.0f;
	float LeanPitch = 0.0f;
	float FlinchTwist = 0.0f;
	float HeadKickPitch = 0.0f;
	float HeadKickYaw = 0.0f;
	float PelvisDrop = 0.0f;
	float FootOffset[2] = { 0.0f, 0.0f };
	float TurnLift[2] = { 0.0f, 0.0f };
	float FootIKAlpha = 0.0f;
	bool bBodyMotion = false;

	// Hand to hand: the guard or the blow on the upper body (see USOLocomotionAnimInstance::SetMeleeGuard).
	const UAnimSequenceBase* MeleeClip = nullptr;
	float MeleeTime = 0.0f;
	bool bMeleeLoop = true;
	float MeleeWeight = 0.0f;
	float MeleeLegs = 0.0f;
	float MeleePitch = 0.0f;

private:
	/** The melee layer laid over the blended locomotion (before the body motion, the hold and the hit). */
	void ApplyMelee(FPoseContext& Output) const;

	/** Orientation warping (legs toward the movement direction, the chest kept on the aim), leans into acceleration,
	 *  landing compression and foot placement on uneven ground (two-bone leg IK). */
	void ApplyBody(FPoseContext& Output) const;

	/** Stance (aim pitch through the spine, lean, blade), head on the aim, both arms onto the grips (two-bone IK);
	 *  first-person copies keep only the arms. */
	void ApplyHold(FPoseContext& Output) const;
	/** The head thrown by a blow to it: the last thing done to the pose (the hold sets neck and head afresh). */
	void ApplyHit(FPoseContext& Output) const;
};

/**
 * Native locomotion: idle / walk / run blended by ground speed (rate-matched), jump while airborne, slide,
 * a one-shot attack, death (held on its last frame). Driven by the owning pawn's movement and USOCombat state.
 */
UCLASS(Transient)
class SOCHARACTER_API USOLocomotionAnimInstance : public UAnimInstance
{
	GENERATED_BODY()

public:
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Anim")
	FSOLocomotionClips Clips;

	/** Seconds to cross-fade between states. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Anim")
	float BlendTime = 0.18f;

	/** Plays the attack clip once (creatures). */
	UFUNCTION(BlueprintCallable, Category = "SO|Anim")
	void PlayAttack(float PlayRate = 1.0f);

	UFUNCTION(BlueprintPure, Category = "SO|Anim")
	float GetAttackLength() const;

	/** Plays any one-shot clip on the attack layer (a creature's special moves: cast, slam, sweep...). */
	void PlayAction(UAnimSequenceBase* Clip, float PlayRate = 1.0f);

	/** True while an attack or action clip plays. */
	bool IsPlayingAction() const { return AttackTime >= 0.0f; }

	/** The clip on the attack layer right now. */
	UPROPERTY(Transient)
	TObjectPtr<UAnimSequenceBase> ActiveAttack;

	/**
	 * Hand to hand (the guns on the back): the style's guard loops on the UPPER body (the spine and all above it) over
	 * whatever the legs are doing, and a blow plays there once and goes back to the guard. Standing, the whole body takes
	 * the clip (its feet set as it was made); on the move the legs keep their gait. None = no melee layer.
	 */
	void SetMeleeGuard(UAnimSequenceBase* Guard, float HoldAt = -1.0f);
	void PlayMeleeBlow(UAnimSequenceBase* Clip, float PlayRate = 1.0f);
	bool IsMeleeBlowPlaying() const { return MeleeBlowTime >= 0.0f; }
	float GetMeleeWeight() const { return MeleeWeight; }

	UPROPERTY(Transient)
	TObjectPtr<UAnimSequenceBase> MeleeGuard;

	UPROPERTY(Transient)
	TObjectPtr<UAnimSequenceBase> MeleeBlow;

	float MeleeBlowTime = -1.0f;
	float MeleeBlowRate = 1.0f;
	float MeleeGuardTime = 0.0f;
	float MeleeGuardHold = -1.0f;   // (>= 0: the guard is held at this moment of its clip: the block)
	float MeleeWeight = 0.0f;   // the layer coming on and off (0 to 1)
	float MeleeLegs = 0.0f;     // how much of the legs it takes (1 standing)
	float MeleePitch = 0.0f;    // the aim's pitch: blows go where the eyes look

	// State read by the proxy (game thread).
	float Speed = 0.0f;
	bool bInAir = false;
	bool bDead = false;
	bool bSliding = false;
	bool bDodging = false;
	bool bMantling = false;

	// --- Body motion (how Unreal's sample characters stay fluid without a clip per direction) ---
	/** Max yaw the legs turn toward the movement direction (orientation warping); beyond it a backward move plays
	 *  the cycle in reverse. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Anim")
	float MaxWarpYaw = 60.0f;

	/** Lean into acceleration: degrees per m/s2, and the cap. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Anim")
	float LeanPerAccel = 0.55f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Anim")
	float MaxLean = 9.0f;

	/** Feet find the ground (stairs, slopes, ledges) within this many cm of the capsule's floor. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Anim")
	float FootReach = 40.0f;

	/** Standing still, the feet stay planted while the aim turns: the hips keep their heading and the spine takes
	 *  the twist, up to this many degrees; past it the body steps round (a turn on the spot). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Anim")
	float TurnInPlaceAngle = 36.0f;

	/** The most the pelvis turns against the chest (degrees), whatever the legs are doing: strafing, or standing
	 *  while the aim turns. The legs take the rest of the turn about their own hip joints. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Anim")
	float MaxWaistTwist = 20.0f;

	/** How far the hips sink when crouched (cm): only for a body without its own crouch clips. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Anim")
	float CrouchDrop = 34.0f;

	/** Where in the jump clip the tuck is complete (s). In the air the clip is not played by the clock: the pose
	 *  follows the rise and the fall (legs driving off, tucked at the top, reaching for the ground coming down). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Anim")
	float JumpTuckTime = 0.22f;

	/** The hips' heading left behind the aim while standing (degrees; 0 when moving). */
	float GetStandYaw() const { return StandYaw; }
	bool IsTurningInPlace() const { return bTurning; }
	/** 0 = legs long, 1 = fully tucked (in the air and through a traversal). */
	float GetAirTuck() const { return AirTuck; }
	/** 0 standing .. 1 crouched (the body's pose, eased). */
	float GetCrouchAlpha() const { return CrouchAlpha; }
	/** How high the turn on the spot has each foot off the ground right now (cm; 0 left, 1 right). */
	float GetTurnLift(int32 Foot) const { return TurnLift[Foot ? 1 : 0]; }
	/** This body has its own crouch clips (nothing is bent at runtime). */
	bool HasCrouchClips() const { return Clips.Crouch != nullptr && Clips.CrouchWalk != nullptr; }
	/** How much of the landing clip shows right now (0..1). */
	float GetLandWeight() const { return Weights[9]; }
	/** The hands are on a ledge (a vault, a mantle or a climb). */
	bool HasLedgeHands() const { return bLedge; }
	float GetHoldAlpha() const { return HoldAlpha; }
	/** How far the hips are sunk below the clip's (cm) and the body's pitch from leaning (deg): for tests. */
	float GetPelvisDrop() const { return PelvisDrop; }
	float GetLeanPitch() const { return LeanPitch; }
	/** The dodge's clip, picked as it began (for the proxy). */
	const UAnimSequenceBase* GetActiveDodge() const { return ActiveDodge; }

	/** A blow: the trunk is knocked this far (degrees: roll to its left, pitch back) and comes back by itself.
	 *  It lies over whatever clip is playing: nothing is interrupted. */
	void Flinch(float Roll, float Pitch);

	/** A hit, shown where it landed. Toward: the way to where it came from, in the actor's own space (X forward,
	 *  Y right). The head is thrown back and round; a shoulder is driven back and the chest turns with it; a leg
	 *  gives and the hips drop over it; the trunk is knocked away. All of it lies over the clip and comes back. */
	void HitKick(ESOHitRegion Region, const FVector& Toward, float Strength);
	float FlinchTwist = 0.0f;
	float HeadKickPitch = 0.0f;
	float HeadKickYaw = 0.0f;
	float FlinchDip = 0.0f;

	/** Reeling (staggered): held bowed and swaying while this is set. */
	bool bReeling = false;
	float FlinchRoll = 0.0f;
	float FlinchPitch = 0.0f;
	float ReelBlend = 0.0f;
	float ReelClock = 0.0f;

	/** Movement yaw relative to the facing (deg, 0 = forward) and whether the cycle runs backward. */
	float MoveYaw = 0.0f;
	bool bBackward = false;
	float WarpYaw = 0.0f;
	float LeanRoll = 0.0f;
	float LeanPitch = 0.0f;
	float PelvisDrop = 0.0f;
	float FootOffset[2] = { 0.0f, 0.0f };
	float FootIKAlpha = 0.0f;
	bool bBodyMotion = false;
	float AttackTime = -1.0f;
	float AttackRate = 1.0f;

	/** Held gun (players): component-space wrist targets with hand bases (FSOHandGrip) for the arm IK. */
	bool bHold = false;
	/** Only the right arm reaches for the gun (the left is busy: a shield). */
	bool bOneHand = false;
	/** The gun in the hands is held the snug way (USOGunRigComponent::IsSnugGrip). */
	bool bSnugHold = false;
	/** First-person copy of the body: everything but the arms collapses. */
	bool bArmsOnly = false;
	bool bCollapseBody = false;
	/** The gun is carried low (a sprint, the armoury's stand-in): the firing elbow stays by the side. */
	bool bCarried = false;
	bool bHeadFree = false;     // the head carries its clip's own motion under the aim (a player's body, the stand-in); a creature's is held on its aim
	float AimPitch = 0.0f;
	float Blade = 0.0f;
	float Lean = 0.0f;
	float HeadCant = 0.0f;   // degrees: aiming a long gun in third person, the head leans onto the stock
	/** The combat stance (FSOStance: the gun's class, the state); the body's share of it, and how still it stands. */
	FSOStanceInputs Stance;
	float StanceBody = 0.0f;
	float StanceStill = 0.0f;
	FTransform RightTarget;
	FTransform LeftTarget;
	FSOFingerPose RightFingers;
	FSOFingerPose LeftFingers;
	FVector EyeCS = FVector::ZeroVector;
	/** The way the held gun points, in the mesh's space (zero: no gun): the support hand slides back along it where
	 *  the arm would not reach. */
	FVector GunAxis = FVector::ZeroVector;

	/** The hands fitted to the gun in them (FitGrip): how each finger closes on this gun's surfaces and how far each
	 *  wrist moves (rig space, cm) to lay the palm on it. Solved once per gun and body. */
	const FSOFingerPose& GetFittedFingers(bool bLeft) const { return FitFingers[bLeft ? 1 : 0]; }

	/** How well a body's hands hold a gun right now, measured on its posed bones against the gun's own triangles
	 *  (index 0 the firing hand, 1 the support hand). The gun is solid and so are the hands: nothing of a hand is IN
	 *  the gun, the palm lies on it, the wrist is not bent further than a wrist bends. */
	struct FHoldReport
	{
		/** Degrees between the forearm and the hand (wrist to the middle knuckle): past about 70 no wrist goes. */
		float WristBend[2] = { 0.0f, 0.0f };
		/** Finger and palm bones whose core (a third of the finger's thickness) passes through the gun's surface. */
		int32 Inside[2] = { 0, 0 };
		/** Of how many bones. */
		int32 Bones[2] = { 0, 0 };
		/** Cm from the palm's skin to the gun along the palm's normal: + a gap, - sunk in; 99 = nothing under it. */
		float PalmGap[2] = { 99.0f, 99.0f };
		/** In the gun's frame (+X barrel, +Y right, +Z up): the way the forearm runs (elbow to wrist), the way the hand
		 *  runs (wrist to the middle knuckle), and out of the palm. */
		FVector Forearm[2] = { FVector::ZeroVector, FVector::ZeroVector };
		FVector Along[2] = { FVector::ZeroVector, FVector::ZeroVector };
		FVector Palm[2] = { FVector::ZeroVector, FVector::ZeroVector };
		/** How far the arm is stretched: shoulder to wrist over the arm's own length (1 = straight, cannot reach further). */
		float Reach[2] = { 0.0f, 0.0f };
		/** The shoulder joint in the gun's frame, cm. */
		FVector ShoulderAt[2] = { FVector::ZeroVector, FVector::ZeroVector };
		/** The palm's middle in the gun's frame, cm. */
		FVector PalmAt[2] = { FVector::ZeroVector, FVector::ZeroVector };
		/** Which bones are in the gun (for the log). */
		FString Which[2];
		SOCHARACTER_API FString ToString() const;
	};
	static FHoldReport MeasureHold(const class USOGunRigComponent* Rig, const class USkeletalMeshComponent* Mesh);
	/** The last elbow swing solved (not in shipping; a measurement aid for the capture series): per side the swing
	 *  the pole asked (rad from straight down, + outward), the one that straightens the wrist, what was taken, how
	 *  much the hand asked, and the most allowed. */
	static float DebugSwing[2][5];
	/** The turn that brings a finger's line (FingerDir) Amount of the way toward the middle finger's, in the palm's plane. */
	static FQuat FingersTogether(const FVector& FingerDir, const FVector& MiddleDir, const FVector& Palm, float Amount);
	/** How far the snug way brings the fingers together (FSOFingerPose::Together). */
	static constexpr float SnugTogether = 0.85f;
	FVector GetFittedOffset(bool bLeft) const { return FitOffset[bLeft ? 1 : 0]; }
	bool HasFittedGrip() const { return bFitDone; }
	/** The support hand was turned to another hold than the rig's own (a vertical fore grip): its basis in the gun's frame. */
	bool GetFittedTurn(FQuat& OutBasis) const { OutBasis = FitBasis; return bFitTurn; }
	/** The support hand holds a vertical fore grip now (fitted round one, and not reloading). */
	bool IsSupportOnPost() const { return bFitTurn && FitWeight > 0.5f; }

	/** Current blend weights (for tests): Idle, Walk, Run, Jump, Death, Attack, Slide, Fidget, Stroll, Land, Vault,
	 *  Mantle, Climb, Crouch, CrouchWalk, Stop. */
	float Weights[17] = { 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 };
	float Times[17] = { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 };

	/** Seconds of standing still before an idle variation, picked between these (random each time). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Anim")
	FVector2D FidgetDelay = FVector2D(7.0f, 15.0f);

	/** Starts the wait for the next idle variation over (a new random delay from FidgetDelay). */
	void ResetFidgetTimer() { NextFidget = -1.0f; StillTime = 0.0f; }

	/** The idle variation playing (index into Clips.Fidgets), or -1. */
	int32 ActiveFidget = -1;
	/** The clip the fidget layer shows (kept while it blends out). */
	const UAnimSequenceBase* FidgetClip = nullptr;
	/** Shared walk / run cycle phase (0..1 per cycle): both clips start on the left foot, so blending never crosses
	 *  the legs. */
	float CyclePhase = 0.0f;

protected:
	/** Fits both hands to the gun's own shape: the palm laid on the surface under it, every finger closed joint by
	 *  joint until it touches (swept against the gun's triangles). Game thread; the gun must be at rest in the hands. */
	void FitGrip(const class USOGunRigComponent* Rig, const class USkeletalMeshComponent* Mesh, bool bOneHanded, float SlideBack = 0.0f);
	/** The support hand was fitted again further back, where this body's arm reaches (once a gun). */
	bool bFitSlid = false;
	// how far the firing hand is set below its usual seat (cm), and whether the trigger finger's root started in the gun
	// at the last fit: a grip whose frame comes down low ahead of it is held lower, so the finger clears the frame
	float FitGripDrop = 0.0f;
	bool bFitIndexInside = false;

	TWeakObjectPtr<const class USOGunRigComponent> FitRig;
	/** A fit kept per gun and body (key: archetype, body mesh, one-handed): handed back instead of fitting again. */
	bool RestoreFit(const FString& Key, const class USOGunRigComponent* Rig);
	void KeepFit(const FString& Key);
public:
	/** Forgets every kept fit (a test that changes a gun's shape, or one that must fit from nothing). */
	static void ForgetFits();
protected:
	FSOFingerPose FitFingers[2];
	FVector FitOffset[2] = { FVector::ZeroVector, FVector::ZeroVector };
	bool bFitDone = false;
	/** The support hand turned to another hold than the gun's own (a vertical fore grip is wrapped, not cupped): its
	 *  basis in the gun's frame. */
	bool bFitTurn = false;
	FQuat FitBasis = FQuat::Identity;
	/** How much of the fit the support hand has (0..1): it lets go of it through a reload and takes it up again
	 *  after, eased (dropped and put back in one frame, the hand jumped). */
	float FitWeight = 0.0f;

	virtual void NativeUpdateAnimation(float DeltaSeconds) override;
	void UpdateBodyMotion(const ACharacter* Character, float DeltaSeconds);

	float StandYaw = 0.0f;
	float LastActorYaw = 0.0f;
	bool bHaveYaw = false;
	bool bTurning = false;
	float AirTuck = 0.0f;
	bool bLedge = false;
	bool bLedgeWas = false;
	float HoldAlpha = 1.0f;
	float HoldAlphaLast = 0.0f;
	/** 0..1 through the current traversal and what kind (0 none, 1 vault, 2 mantle / climb). */
	float TraversalAlpha = 0.0f;
	int32 TraversalKind = 0;
	bool TraversalClimb = false;
	/** This update the body touched down, and how fast (cm/s). */
	bool bLanded = false;
	float LandImpact = 0.0f;
	/** Linear cross-fade progress per layer; the weights are its eased shape. */
	float Ramp[17] = { 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 };
	/** Where in the jump clip the air pose is read (s): take-off at 0, the tuck at JumpTuckTime, the reach for the
	 *  ground at the end. */
	float JumpPose = 0.0f;
	/** The landing layer: how strong this landing is (0..1) and how far through its clip. */
	float LandStrength = 0.0f;
	float LandTime = 100.0f;
	/** The dodge's clip (picked by its direction as it begins) and the time into it. */
	UPROPERTY(Transient)
	TObjectPtr<UAnimSequenceBase> ActiveDodge;
	float DodgeTime = 100.0f;
	/** 0 standing, 1 crouched: the hips sink over bent legs and the chest comes forward. */
	float CrouchAlpha = 0.0f;
	/** Crouched on the ground right now (the crouch clips play). */
	bool bCrouchPose = false;
	/** The brake layer: how hard this stop is (0..1), how far through its clip, and how fast the body was going a
	 *  moment ago (cm/s, decaying). */
	float StopStrength = 0.0f;
	float StopTime = 100.0f;
	float RecentSpeed = 0.0f;
	/** A turn on the spot is stepped: seconds into it, and how high each foot (left, right) is off the ground (cm). */
	float TurnTime = 0.0f;
	float TurnLift[2] = { 0.0f, 0.0f };

	FVector LastVelocityCS = FVector::ZeroVector;
	FVector AccelCS = FVector::ZeroVector;
	float LastAirVz = 0.0f;
	bool bWasInAir = false;
	float Compress = 0.0f;       // landing: cm the hips sink (spring)
	float CompressVel = 0.0f;
	float PelvisFeet = 0.0f;     // cm the hips drop so the lower foot reaches the ground
	float StillTime = 0.0f;      // seconds standing still (idle variations)
	float NextFidget = -1.0f;    // (picked from FidgetDelay)
	int32 LastFidget = -1;
	virtual FAnimInstanceProxy* CreateAnimInstanceProxy() override;
	virtual void DestroyAnimInstanceProxy(FAnimInstanceProxy* InProxy) override;
};
