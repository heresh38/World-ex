#pragma once

#include "CoreMinimal.h"
#include "Animation/AnimInstance.h"
#include "Animation/AnimInstanceProxy.h"
#include "SOGunRigComponent.h"
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

	/** Idle variations (Fidget1..n): one plays now and then while standing still and not aiming; each starts and ends
	 *  on the idle pose. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Clips")
	TArray<TObjectPtr<UAnimSequenceBase>> Fidgets;

	/** Ground speeds (cm/s) the walk and run clips were authored at; playback rate follows the real speed. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Clips")
	float WalkSpeed = 440.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Clips")
	float RunSpeed = 860.0f;
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

	/** 0 Idle, 1 Walk, 2 Run, 3 Jump, 4 Death, 5 Attack, 6 Slide, 7 Fidget */
	FSOLocomotionLayer Layers[8];

	// Held gun (players): copied from the instance each update.
	bool bHold = false;
	/** Only the right arm reaches for the gun (the left is busy: a shield). */
	bool bOneHand = false;
	bool bArmsOnly = false;
	bool bCollapseBody = false;
	float AimPitch = 0.0f;
	float Blade = 0.0f;
	float Lean = 0.0f;
	float HeadCant = 0.0f;   // degrees: aiming a long gun in third person, the head leans onto the stock
	FTransform RightTarget;
	FTransform LeftTarget;
	FSOFingerPose RightFingers;
	FSOFingerPose LeftFingers;
	/** Eye position in component space (first person: the shoulders turn with the view about it). */
	FVector EyeCS = FVector::ZeroVector;

	// Body motion (third-person bodies; see USOLocomotionAnimInstance).
	float WarpYaw = 0.0f;
	float LeanRoll = 0.0f;
	float LeanPitch = 0.0f;
	float PelvisDrop = 0.0f;
	float FootOffset[2] = { 0.0f, 0.0f };
	float FootIKAlpha = 0.0f;
	bool bBodyMotion = false;

private:
	/** Orientation warping (legs toward the movement direction, the chest kept on the aim), leans into acceleration,
	 *  landing compression and foot placement on uneven ground (two-bone leg IK). */
	void ApplyBody(FPoseContext& Output) const;

	/** Stance (aim pitch through the spine, lean, blade), head on the aim, both arms onto the grips (two-bone IK);
	 *  first-person copies keep only the arms. */
	void ApplyHold(FPoseContext& Output) const;
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

	// State read by the proxy (game thread).
	float Speed = 0.0f;
	bool bInAir = false;
	bool bDead = false;
	bool bSliding = false;
	bool bMantling = false;

	// --- Body motion (how Unreal's sample characters stay fluid without a clip per direction) ---
	/** Max yaw the legs turn toward the movement direction (orientation warping); beyond it a backward move plays
	 *  the cycle in reverse. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Anim")
	float MaxWarpYaw = 80.0f;

	/** Lean into acceleration: degrees per m/s2, and the cap. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Anim")
	float LeanPerAccel = 0.55f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Anim")
	float MaxLean = 9.0f;

	/** Feet find the ground (stairs, slopes, ledges) within this many cm of the capsule's floor. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Anim")
	float FootReach = 40.0f;

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
	/** First-person copy of the body: everything but the arms collapses. */
	bool bArmsOnly = false;
	bool bCollapseBody = false;
	float AimPitch = 0.0f;
	float Blade = 0.0f;
	float Lean = 0.0f;
	float HeadCant = 0.0f;   // degrees: aiming a long gun in third person, the head leans onto the stock
	FTransform RightTarget;
	FTransform LeftTarget;
	FSOFingerPose RightFingers;
	FSOFingerPose LeftFingers;
	FVector EyeCS = FVector::ZeroVector;

	/** The hands fitted to the gun in them (FitGrip): how each finger closes on this gun's surfaces and how far each
	 *  wrist moves (rig space, cm) to lay the palm on it. Solved once per gun and body. */
	const FSOFingerPose& GetFittedFingers(bool bLeft) const { return FitFingers[bLeft ? 1 : 0]; }
	FVector GetFittedOffset(bool bLeft) const { return FitOffset[bLeft ? 1 : 0]; }
	bool HasFittedGrip() const { return bFitDone; }

	/** Current blend weights (for tests): Idle, Walk, Run, Jump, Death, Attack, Slide, Fidget. */
	float Weights[8] = { 1, 0, 0, 0, 0, 0, 0, 0 };
	float Times[8] = { 0, 0, 0, 0, 0, 0, 0, 0 };

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
	void FitGrip(const class USOGunRigComponent* Rig, const class USkeletalMeshComponent* Mesh, bool bOneHanded);

	TWeakObjectPtr<const class USOGunRigComponent> FitRig;
	FSOFingerPose FitFingers[2];
	FVector FitOffset[2] = { FVector::ZeroVector, FVector::ZeroVector };
	bool bFitDone = false;

	virtual void NativeUpdateAnimation(float DeltaSeconds) override;
	void UpdateBodyMotion(const ACharacter* Character, float DeltaSeconds);

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
