#pragma once

#include "CoreMinimal.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "SOCharacterMovementComponent.generated.h"

/** Values used with MOVE_Custom. */
UENUM(BlueprintType)
enum class ESOCustomMovementMode : uint8
{
	None = 0 UMETA(Hidden),
	Slide = 1,
	/** Every traversal over or onto an obstacle (see ESOTraversal). */
	Mantle = 2
};

/** How an obstacle is taken. */
UENUM(BlueprintType)
enum class ESOTraversal : uint8
{
	None,
	/** A thin obstacle up to hip height taken at speed: over it in one motion, the speed kept. */
	VaultLow,
	/** A thin obstacle up to chest height taken at speed: a hand plant and over. */
	VaultMedium,
	/** Up onto a ledge up to head height and a bit. */
	Mantle,
	/** A ledge above that: a hang and a pull up. */
	Climb
};

/** What the body is doing, for animation, sound, the camera and anything else that wants to know. One at a time,
 *  derived every move from the movement mode and the numbers: it never locks anything. */
UENUM(BlueprintType)
enum class ESOMovementState : uint8
{
	Idle,
	/** Moving slowly (a light stick). */
	Walk,
	/** The normal pace. */
	Run,
	Sprint,
	Crouch,
	/** Rising from a jump. */
	Jump,
	Falling,
	/** The moment after touching down. */
	Land,
	Slide,
	Vault,
	Mantle,
	Climb
};

/** One-off things that happen while moving: hooks for sound, the camera and effects. */
UENUM(BlueprintType)
enum class ESOMovementEvent : uint8
{
	Jumped,
	AirJumped,
	/** Strength: the speed it hit the ground at (cm/s). */
	Landed,
	SlideStarted,
	SlideEnded,
	/** Strength: the speed it was entered at (cm/s). */
	VaultStarted,
	MantleStarted,
	ClimbStarted,
	TraversalEnded
};

DECLARE_MULTICAST_DELEGATE_TwoParams(FSOOnMovementStateChanged, ESOMovementState /*Old*/, ESOMovementState /*New*/);
DECLARE_MULTICAST_DELEGATE_TwoParams(FSOOnMovementEvent, ESOMovementEvent /*Event*/, float /*Strength*/);

/**
 * Character movement for Shattered Orbit.
 *
 * Ground: instant acceleration to the run, a gentler build to the sprint, hard braking; analog input scales the
 * speed. Jump: coyote time, a buffered press (the character's input), variable height (letting go early cuts the
 * rise), air jumps that turn the momentum toward the stick, strong air control that never adds speed beyond what was
 * carried. Slide: crouch at speed (custom mode, exponential friction, gravity along the slope, steering, off ledges,
 * jump out). Traversal (custom mode Mantle, see ESOTraversal): the obstacle in front is measured (height, depth, what
 * is behind it) and taken as a low or medium vault over it, a mantle onto it or a climb; the body follows a path
 * that was checked for room, relative to what it climbs (a moving platform carries it), and leaves with its speed.
 * Landing: the impact speed is kept (camera, sound, fall damage hook), a very hard landing takes a moment to recover.
 *
 * States and events: GetMovementState() / OnMovementStateChanged and OnMovementEvent are the one place animation,
 * sound, camera and effects listen to; a new ability adds a custom mode, a state and its events here.
 *
 * Network: sprint, "jump held" and aim travel in the saved moves' compressed flags (FLAG_Custom_0/1/2); slide,
 * traversal, landing and coyote state is saved per move so replays after a server correction match. Every step is
 * integrated per sub-step (GetSimulationTimeStep) or from elapsed time: the same at any frame rate.
 */
UCLASS()
class SOCHARACTER_API USOCharacterMovementComponent : public UCharacterMovementComponent
{
	GENERATED_BODY()

	friend class FSOSavedMove;

public:
	USOCharacterMovementComponent();

	// --- Sprint ---
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Sprint", meta = (Units = "cm/s"))
	float SprintSpeed = 860.0f;

	/** Acceleration while building from walk to sprint speed (the base acceleration gets you to walk speed). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Sprint")
	float SprintBuildAcceleration = 2400.0f;

	/** Sprint needs the move input within this cosine of the facing (forward only). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Sprint")
	float SprintForwardDot = 0.7f;

	/** Move speed while aiming down sights, as a fraction of walk speed. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Sprint")
	float AimSpeedScale = 0.58f;

	/** Below this ground speed the state is Walk, above it Run (cm/s). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Sprint", meta = (Units = "cm/s"))
	float WalkStateSpeed = 250.0f;

	// --- Jump ---
	/** A jump is still allowed this long after walking off a ledge. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Jump", meta = (Units = "s"))
	float CoyoteTime = 0.12f;

	/** A jump pressed this long before landing fires on landing (handled by the character's input). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Jump", meta = (Units = "s"))
	float JumpBufferTime = 0.12f;

	/** Variable height: while rising from a jump with the button let go, gravity is this much stronger (a tap is a
	 *  hop, a hold the full jump). 1 = always the full jump. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Jump")
	float JumpCutGravityScale = 2.6f;

	/** Gravity on the way down (1 = the same as up; a little more makes the fall less floaty). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Jump")
	float FallGravityScale = 1.0f;

	/** Jumps in the air after the first (0 = none, 1 = double jump, 2 = triple). Set with SetMaxAirJumps at runtime. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Jump")
	int32 MaxAirJumps = 1;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Jump", meta = (Units = "cm/s"))
	float AirJumpZVelocity = 560.0f;

	/** How much of the carried speed an air jump turns toward the stick (0 = none, 1 = all of it): the correction in
	 *  the air. The speed itself is kept. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Jump")
	float AirJumpRedirect = 0.7f;

	/** Server / owner: changes how many air jumps there are (keeps the character's jump count in step). */
	void SetMaxAirJumps(int32 Count);

	// --- Landing ---
	/** Hitting the ground faster than this is a hard landing: it takes a moment to get back up to speed. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Landing", meta = (Units = "cm/s"))
	float HeavyLandSpeed = 1500.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Landing", meta = (Units = "s"))
	float LandRecoverTime = 0.35f;

	/** Share of the ground speed right after a hard landing (eases back to 1 over LandRecoverTime). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Landing")
	float LandSpeedScale = 0.55f;

	/** How long the Land state lasts after any touchdown. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Landing", meta = (Units = "s"))
	float LandStateTime = 0.2f;

	/** Fall damage hook: landing faster than this hurts (0 = no fall damage, the default). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Landing", meta = (Units = "cm/s"))
	float FallDamageMinSpeed = 0.0f;

	/** Damage per cm/s above FallDamageMinSpeed. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Landing")
	float FallDamagePerSpeed = 0.06f;

	/** What a landing at ImpactSpeed costs (0 while fall damage is off). */
	float GetFallDamage(float ImpactSpeed) const;

	/** The speed of the last touchdown (cm/s, downward). */
	float GetLastLandSpeed() const { return LastLandSpeed; }

	// --- Slide ---
	/** Crouching while moving at least this fast starts a slide. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Slide", meta = (Units = "cm/s"))
	float SlideEnterSpeed = 650.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Slide", meta = (Units = "cm/s"))
	float SlideBoost = 240.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Slide", meta = (Units = "cm/s"))
	float SlideMaxSpeed = 1100.0f;

	/** Velocity decays by exp(-SlideFriction * t). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Slide")
	float SlideFriction = 1.35f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Slide", meta = (Units = "s"))
	float SlideMaxTime = 0.9f;

	/** The slide ends below this speed. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Slide", meta = (Units = "cm/s"))
	float SlideExitSpeed = 320.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Slide", meta = (Units = "s"))
	float SlideCooldown = 1.0f;

	/** Sideways steering acceleration at full stick. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Slide")
	float SlideSteerAcceleration = 420.0f;

	/** Downhill steeper than this (degrees) a slide keeps going past SlideMaxTime while it still has speed. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Slide")
	float SlideDownhillAngle = 8.0f;

	// --- Vault (over a thin obstacle) ---
	/** Obstacles up to this high are a low vault. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Vault", meta = (Units = "cm"))
	float VaultLowMaxHeight = 110.0f;

	/** ... up to this a medium vault; higher ones are mantled onto. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Vault", meta = (Units = "cm"))
	float VaultMediumMaxHeight = 170.0f;

	/** Only obstacles no deeper than this are vaulted over (deeper ones are mantled onto). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Vault", meta = (Units = "cm"))
	float VaultMaxDepth = 120.0f;

	/** The ground behind the obstacle may be this much lower than the ground in front (never vault into a pit). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Vault", meta = (Units = "cm"))
	float VaultMaxDrop = 140.0f;

	/** Moving toward the obstacle at least this fast it is vaulted over; slower, it is mantled onto. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Vault", meta = (Units = "cm/s"))
	float VaultEntrySpeed = 470.0f;

	/** The speed along the vault's path: the speed it was entered at, kept inside these. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Vault", meta = (Units = "cm/s"))
	FVector2D VaultPathSpeed = FVector2D(420.0f, 900.0f);

	/** Share of the entry speed kept on the far side. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Vault")
	float VaultKeepSpeed = 0.95f;

	/** How far the legs tuck while passing over (low / medium): the body passes that much lower than standing on it. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Vault", meta = (Units = "cm"))
	FVector2D VaultTuck = FVector2D(58.0f, 32.0f);

	/** Sprinting into a vaultable obstacle vaults it without pressing jump. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Vault")
	bool bAutoVault = true;

	// --- Mantle / climb ---
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Mantle", meta = (Units = "cm"))
	float MantleMinHeight = 50.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Mantle", meta = (Units = "cm"))
	float MantleMaxHeight = 245.0f;

	/** How far in front of the capsule a ledge is searched. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Mantle", meta = (Units = "cm"))
	float MantleReach = 55.0f;

	/** Higher ledges than a mantle, up to this, are climbed: a hang and a pull up (cm). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Mantle", meta = (Units = "cm"))
	float ClamberMaxHeight = 380.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Mantle", meta = (Units = "s"))
	float ClamberBaseTime = 0.5f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Mantle", meta = (Units = "s"))
	float ClamberTimePerMeter = 0.2f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Mantle", meta = (Units = "s"))
	float MantleBaseTime = 0.22f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Mantle", meta = (Units = "s"))
	float MantleTimePerMeter = 0.16f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Mantle", meta = (Units = "cm/s"))
	float MantleExitSpeed = 180.0f;

	/** Share of the approach speed a mantle keeps on the far side (a sprint mantle flows on instead of stopping). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Mantle")
	float MantleKeepSpeed = 0.8f;

	/** A mantle at full sprint takes this fraction of the time a standing one does. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Mantle")
	float MantleFastTimeScale = 0.7f;

	/** The current traversal (None when not in one). */
	UFUNCTION(BlueprintPure, Category = "SO|Movement")
	ESOTraversal GetTraversal() const { return IsMantling() ? Traversal : ESOTraversal::None; }

	/** True while the current traversal is a climb (a ledge above MantleMaxHeight). */
	bool IsClambering() const { return GetTraversal() == ESOTraversal::Climb; }

	/** True while vaulting over an obstacle. */
	bool IsVaulting() const { const ESOTraversal T = GetTraversal(); return T == ESOTraversal::VaultLow || T == ESOTraversal::VaultMedium; }

	/** 0..1 through the current traversal (0 when not in one). */
	float GetMantleAlpha() const { return IsMantling() && MantleDuration > 0.0f ? FMath::Clamp(MantleElapsed / MantleDuration, 0.0f, 1.0f) : 0.0f; }

	/** The edge the hands go on during a traversal: a point on the top of the near face and the face's outward
	 *  normal (world space, following a moving obstacle). False when not in a traversal. */
	bool GetTraversalLedge(FVector& OutPoint, FVector& OutNormal) const;

	// --- Intents (set by the owning client, replicated via compressed flags) ---
	UFUNCTION(BlueprintCallable, Category = "SO|Movement")
	void SetWantsToSprint(bool bWants) { bWantsToSprint = bWants; }

	/** The jump button is held: toward a ledge it grabs and takes it; in a jump it keeps the full height. */
	UFUNCTION(BlueprintCallable, Category = "SO|Movement")
	void SetWantsToMantle(bool bWants) { bWantsToMantle = bWants; }

	UFUNCTION(BlueprintCallable, Category = "SO|Movement")
	void SetWantsToAim(bool bWants) { bWantsToAim = bWants; }

	bool WantsToAim() const { return bWantsToAim; }

	bool WantsToSprint() const { return bWantsToSprint; }
	bool WantsToMantle() const { return bWantsToMantle; }

	// --- State queries ---
	UFUNCTION(BlueprintPure, Category = "SO|Movement")
	ESOMovementState GetMovementState() const { return State; }

	/** Fired when the state changes (all machines). */
	FSOOnMovementStateChanged OnMovementStateChanged;

	/** Fired for one-off movement events (all machines that simulate the move; not during replays). */
	FSOOnMovementEvent OnMovementEvent;

	UFUNCTION(BlueprintPure, Category = "SO|Movement")
	bool IsSprinting() const;

	UFUNCTION(BlueprintPure, Category = "SO|Movement")
	bool IsSliding() const { return IsCustomMode(ESOCustomMovementMode::Slide); }

	/** In any traversal (vault, mantle, climb). */
	UFUNCTION(BlueprintPure, Category = "SO|Movement")
	bool IsMantling() const { return IsCustomMode(ESOCustomMovementMode::Mantle); }

	bool IsCustomMode(ESOCustomMovementMode Mode) const
	{
		return MovementMode == MOVE_Custom && CustomMovementMode == static_cast<uint8>(Mode);
	}

	/** Walked off a ledge (not jumped) recently enough to still jump. */
	bool IsInCoyoteWindow() const;

	/** Air jumps still available before touching down. */
	int32 GetAirJumpsLeft() const;

	float GetFallTime() const { return FallTime; }
	float GetSlideElapsed() const { return SlideElapsed; }
	float GetSlideCooldownLeft() const { return SlideCooldownLeft; }

	/** Measures the obstacle in front and starts the traversal that fits it (bVaultOnly: only a vault over it). */
	bool TryMantle(bool bVaultOnly = false);

	//~ UCharacterMovementComponent
	virtual float GetMaxSpeed() const override;
	virtual float GetMaxAcceleration() const override;
	virtual float GetGravityZ() const override;
	virtual bool IsMovingOnGround() const override;
	virtual bool CanAttemptJump() const override;
	virtual bool DoJump(bool bReplayingMoves, float DeltaTime) override;
	virtual void UpdateCharacterStateBeforeMovement(float DeltaSeconds) override;
	virtual void UpdateCharacterStateAfterMovement(float DeltaSeconds) override;
	virtual void UpdateFromCompressedFlags(uint8 Flags) override;
	virtual FNetworkPredictionData_Client* GetPredictionData_Client() const override;
	virtual void PhysCustom(float DeltaTime, int32 Iterations) override;
	virtual void ProcessLanded(const FHitResult& Hit, float RemainingTime, int32 Iterations) override;
	virtual void BeginPlay() override;

protected:
	virtual void OnMovementModeChanged(EMovementMode PreviousMovementMode, uint8 PreviousCustomMode) override;

	void EnterSlide();
	void PhysSlide(float DeltaTime, int32 Iterations);
	void PhysMantle(float DeltaTime, int32 Iterations);

	/** Where the body is Alpha (0..1) through the current traversal, in the frame it began in. */
	FVector TraversalPoint(float Alpha) const;
	/** A point of that frame where it is now (the obstacle may have moved). */
	FVector FromTraversalFrame(const FVector& Point) const;
	FVector DirFromTraversalFrame(const FVector& Dir) const;

	ESOMovementState ComputeState() const;
	void Notify(ESOMovementEvent Event, float Strength = 0.0f);

	uint8 bWantsToSprint : 1;
	uint8 bWantsToMantle : 1;
	uint8 bWantsToAim : 1;

	float FallTime = 0.0f;
	float SlideElapsed = 0.0f;
	float SlideCooldownLeft = 0.0f;
	float LandRecoverLeft = 0.0f;
	float LandStateLeft = 0.0f;
	float LastLandSpeed = 0.0f;

	// the current traversal (saved per move)
	ESOTraversal Traversal = ESOTraversal::None;
	FVector MantleStart = FVector::ZeroVector;
	FVector MantleTarget = FVector::ZeroVector;
	/** A mantle / climb: where the body stands against the face before it rises. */
	FVector MantleNear = FVector::ZeroVector;
	float MantleElapsed = 0.0f;
	float MantleDuration = 0.0f;
	float MantleEntrySpeed = 0.0f;
	/** A vault: how far to the obstacle, how far over it, the height the body passes at, and where along the move
	 *  (0..1) the approach ends and the descent begins. */
	float VaultApproach = 0.0f;
	float VaultOver = 0.0f;
	float VaultApexZ = 0.0f;
	float VaultRiseEnd = 0.0f;
	float VaultDropStart = 1.0f;
	/** What is being climbed, when it can move, and where it was when the traversal began. */
	TWeakObjectPtr<UPrimitiveComponent> TraversalBase;
	FTransform TraversalBaseStart = FTransform::Identity;
	FVector LedgePoint = FVector::ZeroVector;
	FVector LedgeNormal = FVector::ForwardVector;

	ESOMovementState State = ESOMovementState::Idle;
};
