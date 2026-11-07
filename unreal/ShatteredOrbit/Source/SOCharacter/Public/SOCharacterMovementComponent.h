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
	Mantle = 2
};

/**
 * Character movement for Shattered Orbit: walk / sprint, coyote time, crouch, slide (custom mode with
 * exponential friction decay) and mantling onto 50-245 cm ledges (custom mode).
 * Sprint and the "jump held" intent travel in the saved moves' compressed flags (FLAG_Custom_0/1);
 * slide / mantle / coyote state is saved per move so replays after a server correction match.
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

	// --- Jump ---
	/** A jump is still allowed this long after walking off a ledge. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Jump", meta = (Units = "s"))
	float CoyoteTime = 0.12f;

	/** A jump pressed this long before landing fires on landing (handled by the character's input). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Jump", meta = (Units = "s"))
	float JumpBufferTime = 0.12f;

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

	// --- Mantle ---
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Mantle", meta = (Units = "cm"))
	float MantleMinHeight = 50.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Mantle", meta = (Units = "cm"))
	float MantleMaxHeight = 245.0f;

	/** How far in front of the capsule a ledge is searched. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Mantle", meta = (Units = "cm"))
	float MantleReach = 55.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Mantle", meta = (Units = "s"))
	float MantleBaseTime = 0.22f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Mantle", meta = (Units = "s"))
	float MantleTimePerMeter = 0.16f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Mantle", meta = (Units = "cm/s"))
	float MantleExitSpeed = 180.0f;

	/** Share of the approach speed a mantle keeps on the far side (a sprint vault flows on instead of stopping). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Mantle")
	float MantleKeepSpeed = 0.8f;

	/** A mantle at full sprint takes this fraction of the time a standing one does. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Mantle")
	float MantleFastTimeScale = 0.7f;

	/** Downhill steeper than this (degrees) a slide keeps going past SlideMaxTime while it still has speed. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Slide")
	float SlideDownhillAngle = 8.0f;

	/** 0..1 through the current mantle (0 when not mantling). */
	float GetMantleAlpha() const { return IsMantling() && MantleDuration > 0.0f ? FMath::Clamp(MantleElapsed / MantleDuration, 0.0f, 1.0f) : 0.0f; }

	// --- Intents (set by the owning client, replicated via compressed flags) ---
	UFUNCTION(BlueprintCallable, Category = "SO|Movement")
	void SetWantsToSprint(bool bWants) { bWantsToSprint = bWants; }

	UFUNCTION(BlueprintCallable, Category = "SO|Movement")
	void SetWantsToMantle(bool bWants) { bWantsToMantle = bWants; }

	UFUNCTION(BlueprintCallable, Category = "SO|Movement")
	void SetWantsToAim(bool bWants) { bWantsToAim = bWants; }

	bool WantsToAim() const { return bWantsToAim; }

	bool WantsToSprint() const { return bWantsToSprint; }
	bool WantsToMantle() const { return bWantsToMantle; }

	// --- State queries ---
	UFUNCTION(BlueprintPure, Category = "SO|Movement")
	bool IsSprinting() const;

	UFUNCTION(BlueprintPure, Category = "SO|Movement")
	bool IsSliding() const { return IsCustomMode(ESOCustomMovementMode::Slide); }

	UFUNCTION(BlueprintPure, Category = "SO|Movement")
	bool IsMantling() const { return IsCustomMode(ESOCustomMovementMode::Mantle); }

	bool IsCustomMode(ESOCustomMovementMode Mode) const
	{
		return MovementMode == MOVE_Custom && CustomMovementMode == static_cast<uint8>(Mode);
	}

	/** Walked off a ledge (not jumped) recently enough to still jump. */
	bool IsInCoyoteWindow() const { return IsFalling() && FallTime <= CoyoteTime; }

	float GetFallTime() const { return FallTime; }
	float GetSlideElapsed() const { return SlideElapsed; }
	float GetSlideCooldownLeft() const { return SlideCooldownLeft; }

	/** Searches for a ledge in front and starts the mantle if one fits. */
	bool TryMantle();

	//~ UCharacterMovementComponent
	virtual float GetMaxSpeed() const override;
	virtual float GetMaxAcceleration() const override;
	virtual bool IsMovingOnGround() const override;
	virtual bool CanAttemptJump() const override;
	virtual void UpdateCharacterStateBeforeMovement(float DeltaSeconds) override;
	virtual void UpdateFromCompressedFlags(uint8 Flags) override;
	virtual FNetworkPredictionData_Client* GetPredictionData_Client() const override;
	virtual void PhysCustom(float DeltaTime, int32 Iterations) override;

protected:
	virtual void OnMovementModeChanged(EMovementMode PreviousMovementMode, uint8 PreviousCustomMode) override;

	void EnterSlide();
	void PhysSlide(float DeltaTime, int32 Iterations);
	void PhysMantle(float DeltaTime, int32 Iterations);

	uint8 bWantsToSprint : 1;
	uint8 bWantsToMantle : 1;
	uint8 bWantsToAim : 1;

	float FallTime = 0.0f;
	float SlideElapsed = 0.0f;
	float SlideCooldownLeft = 0.0f;

	FVector MantleStart = FVector::ZeroVector;
	FVector MantleTarget = FVector::ZeroVector;
	float MantleElapsed = 0.0f;
	float MantleDuration = 0.0f;
	float MantleEntrySpeed = 0.0f;
};
