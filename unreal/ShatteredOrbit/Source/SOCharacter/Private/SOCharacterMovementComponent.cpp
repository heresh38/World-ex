#include "SOCharacterMovementComponent.h"

#include "Components/CapsuleComponent.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"

// ---------------------------------------------------------------------------------------------
// Saved moves: the client records the intents (compressed flags) and the custom state at the
// start of each move, so that moves replayed after a server correction start from the same state.
// ---------------------------------------------------------------------------------------------

class FSOSavedMove : public FSavedMove_Character
{
public:
	typedef FSavedMove_Character Super;

	uint8 bSavedWantsToSprint : 1;
	uint8 bSavedWantsToMantle : 1;
	float SavedFallTime = 0.0f;
	float SavedSlideElapsed = 0.0f;
	float SavedSlideCooldownLeft = 0.0f;
	FVector SavedMantleStart = FVector::ZeroVector;
	FVector SavedMantleTarget = FVector::ZeroVector;
	float SavedMantleElapsed = 0.0f;
	float SavedMantleDuration = 0.0f;

	FSOSavedMove()
		: bSavedWantsToSprint(false)
		, bSavedWantsToMantle(false)
	{
	}

	virtual void Clear() override
	{
		Super::Clear();
		bSavedWantsToSprint = false;
		bSavedWantsToMantle = false;
		SavedFallTime = 0.0f;
		SavedSlideElapsed = 0.0f;
		SavedSlideCooldownLeft = 0.0f;
		SavedMantleStart = FVector::ZeroVector;
		SavedMantleTarget = FVector::ZeroVector;
		SavedMantleElapsed = 0.0f;
		SavedMantleDuration = 0.0f;
	}

	virtual uint8 GetCompressedFlags() const override
	{
		uint8 Result = Super::GetCompressedFlags();
		if (bSavedWantsToSprint)
		{
			Result |= FLAG_Custom_0;
		}
		if (bSavedWantsToMantle)
		{
			Result |= FLAG_Custom_1;
		}
		return Result;
	}

	virtual bool CanCombineWith(const FSavedMovePtr& NewMove, ACharacter* InCharacter, float MaxDelta) const override
	{
		const FSOSavedMove* Other = static_cast<const FSOSavedMove*>(NewMove.Get());
		if (bSavedWantsToSprint != Other->bSavedWantsToSprint || bSavedWantsToMantle != Other->bSavedWantsToMantle)
		{
			return false;
		}
		return Super::CanCombineWith(NewMove, InCharacter, MaxDelta);
	}

	virtual void SetMoveFor(ACharacter* C, float InDeltaTime, FVector const& NewAccel, FNetworkPredictionData_Client_Character& ClientData) override
	{
		Super::SetMoveFor(C, InDeltaTime, NewAccel, ClientData);
		if (const USOCharacterMovementComponent* Move = Cast<USOCharacterMovementComponent>(C->GetCharacterMovement()))
		{
			bSavedWantsToSprint = Move->bWantsToSprint;
			bSavedWantsToMantle = Move->bWantsToMantle;
			SavedFallTime = Move->FallTime;
			SavedSlideElapsed = Move->SlideElapsed;
			SavedSlideCooldownLeft = Move->SlideCooldownLeft;
			SavedMantleStart = Move->MantleStart;
			SavedMantleTarget = Move->MantleTarget;
			SavedMantleElapsed = Move->MantleElapsed;
			SavedMantleDuration = Move->MantleDuration;
		}
	}

	virtual void PrepMoveFor(ACharacter* C) override
	{
		Super::PrepMoveFor(C);
		if (USOCharacterMovementComponent* Move = Cast<USOCharacterMovementComponent>(C->GetCharacterMovement()))
		{
			Move->FallTime = SavedFallTime;
			Move->SlideElapsed = SavedSlideElapsed;
			Move->SlideCooldownLeft = SavedSlideCooldownLeft;
			Move->MantleStart = SavedMantleStart;
			Move->MantleTarget = SavedMantleTarget;
			Move->MantleElapsed = SavedMantleElapsed;
			Move->MantleDuration = SavedMantleDuration;
		}
	}
};

class FSONetworkPredictionData_Client : public FNetworkPredictionData_Client_Character
{
public:
	typedef FNetworkPredictionData_Client_Character Super;

	explicit FSONetworkPredictionData_Client(const UCharacterMovementComponent& ClientMovement)
		: Super(ClientMovement)
	{
	}

	virtual FSavedMovePtr AllocateNewMove() override
	{
		return FSavedMovePtr(new FSOSavedMove());
	}
};

// ---------------------------------------------------------------------------------------------

USOCharacterMovementComponent::USOCharacterMovementComponent()
	: bWantsToSprint(false)
	, bWantsToMantle(false)
{
	// Fast modern shooter feel (numbers from the browser build's MOVE table, in cm).
	MaxWalkSpeed = 440.0f;
	MaxWalkSpeedCrouched = 270.0f;
	MaxAcceleration = 5500.0f;              // walk speed in ~0.08 s
	BrakingDecelerationWalking = 7000.0f;   // stop / reverse
	bUseSeparateBrakingFriction = true;
	BrakingFriction = 0.0f;
	GroundFriction = 8.0f;
	JumpZVelocity = 610.0f;                 // ~1.0 m at gravity 19 m/s2
	GravityScale = 1900.0f / 980.0f;
	AirControl = 0.15f;
	AirControlBoostMultiplier = 1.0f;
	FallingLateralFriction = 0.0f;
	BrakingDecelerationFalling = 0.0f;      // momentum is kept in the air
	MaxStepHeight = 45.0f;
	SetWalkableFloorAngle(46.0f);
	bCanWalkOffLedgesWhenCrouching = true;
	SetCrouchedHalfHeight(58.0f);
	bOrientRotationToMovement = false;
	NavAgentProps.bCanCrouch = true;
	NavAgentProps.bCanJump = true;
}

bool USOCharacterMovementComponent::IsSprinting() const
{
	if (!bWantsToSprint || !UpdatedComponent || IsCrouching() || MovementMode != MOVE_Walking)
	{
		return false;
	}
	const FVector Input = Acceleration.GetSafeNormal2D();
	if (Input.IsNearlyZero())
	{
		return false;
	}
	const FVector Forward = UpdatedComponent->GetForwardVector().GetSafeNormal2D();
	return FVector::DotProduct(Input, Forward) >= SprintForwardDot;
}

float USOCharacterMovementComponent::GetMaxSpeed() const
{
	if (IsSliding())
	{
		return SlideMaxSpeed;
	}
	if (MovementMode == MOVE_Walking || MovementMode == MOVE_NavWalking)
	{
		if (IsCrouching())
		{
			return MaxWalkSpeedCrouched;
		}
		if (IsSprinting())
		{
			return SprintSpeed;
		}
		return MaxWalkSpeed;
	}
	return Super::GetMaxSpeed();
}

float USOCharacterMovementComponent::GetMaxAcceleration() const
{
	// Reach walk speed with the full acceleration, then build more gently up to sprint speed.
	if (IsSprinting() && Velocity.Size2D() >= MaxWalkSpeed * 0.95f)
	{
		return SprintBuildAcceleration;
	}
	return Super::GetMaxAcceleration();
}

bool USOCharacterMovementComponent::IsMovingOnGround() const
{
	return Super::IsMovingOnGround() || IsSliding();
}

bool USOCharacterMovementComponent::CanAttemptJump() const
{
	// A slide is crouched, but jumping out of it is allowed (it keeps the momentum).
	if (IsSliding())
	{
		return IsJumpAllowed();
	}
	return Super::CanAttemptJump();
}

void USOCharacterMovementComponent::UpdateCharacterStateBeforeMovement(float DeltaSeconds)
{
	SlideCooldownLeft = FMath::Max(0.0f, SlideCooldownLeft - DeltaSeconds);
	FallTime = IsFalling() ? FallTime + DeltaSeconds : 0.0f;

	// Crouch / uncrouch (the slide counts as moving on ground, so it stays crouched).
	Super::UpdateCharacterStateBeforeMovement(DeltaSeconds);

	if (!CharacterOwner)
	{
		return;
	}

	// Crouching at sprint speed starts a slide.
	if (MovementMode == MOVE_Walking && IsCrouching() && bWantsToCrouch && SlideCooldownLeft <= 0.0f
		&& Velocity.Size2D() >= SlideEnterSpeed)
	{
		EnterSlide();
	}

	// Jump held toward a ledge: mantle (works from the ground and in the air).
	if (bWantsToMantle && !IsCrouching() && (IsFalling() || MovementMode == MOVE_Walking))
	{
		TryMantle();
	}
}

void USOCharacterMovementComponent::UpdateFromCompressedFlags(uint8 Flags)
{
	Super::UpdateFromCompressedFlags(Flags);
	bWantsToSprint = (Flags & FSavedMove_Character::FLAG_Custom_0) != 0;
	bWantsToMantle = (Flags & FSavedMove_Character::FLAG_Custom_1) != 0;
}

FNetworkPredictionData_Client* USOCharacterMovementComponent::GetPredictionData_Client() const
{
	if (ClientPredictionData == nullptr)
	{
		USOCharacterMovementComponent* MutableThis = const_cast<USOCharacterMovementComponent*>(this);
		MutableThis->ClientPredictionData = new FSONetworkPredictionData_Client(*this);
		MutableThis->ClientPredictionData->MaxSmoothNetUpdateDist = 92.0f;
		MutableThis->ClientPredictionData->NoSmoothNetUpdateDist = 140.0f;
	}
	return ClientPredictionData;
}

void USOCharacterMovementComponent::OnMovementModeChanged(EMovementMode PreviousMovementMode, uint8 PreviousCustomMode)
{
	Super::OnMovementModeChanged(PreviousMovementMode, PreviousCustomMode);

	const bool bWasSliding = PreviousMovementMode == MOVE_Custom && PreviousCustomMode == static_cast<uint8>(ESOCustomMovementMode::Slide);
	if (bWasSliding && !IsSliding())
	{
		SlideCooldownLeft = SlideCooldown;
		// Jumping out of a slide stands up and keeps the momentum.
		if (MovementMode == MOVE_Falling)
		{
			bWantsToCrouch = false;
		}
	}

	if (IsSliding())
	{
		// The slide is ground movement: keep the feet planted when the capsule shrinks.
		bCrouchMaintainsBaseLocation = true;
		FindFloor(UpdatedComponent->GetComponentLocation(), CurrentFloor, false);
	}

	if (MovementMode == MOVE_Falling && PreviousMovementMode != MOVE_Falling)
	{
		FallTime = 0.0f;
	}
}

void USOCharacterMovementComponent::PhysCustom(float DeltaTime, int32 Iterations)
{
	switch (static_cast<ESOCustomMovementMode>(CustomMovementMode))
	{
	case ESOCustomMovementMode::Slide:
		PhysSlide(DeltaTime, Iterations);
		break;
	case ESOCustomMovementMode::Mantle:
		PhysMantle(DeltaTime, Iterations);
		break;
	default:
		Super::PhysCustom(DeltaTime, Iterations);
		break;
	}
}

void USOCharacterMovementComponent::EnterSlide()
{
	const FVector Dir = Velocity.GetSafeNormal2D();
	Velocity = (Velocity + Dir * SlideBoost).GetClampedToMaxSize(SlideMaxSpeed);
	SlideElapsed = 0.0f;
	SetMovementMode(MOVE_Custom, static_cast<uint8>(ESOCustomMovementMode::Slide));
}

void USOCharacterMovementComponent::PhysSlide(float DeltaTime, int32 Iterations)
{
	if (DeltaTime < MIN_TICK_TIME)
	{
		return;
	}
	if (!CharacterOwner || !UpdatedComponent)
	{
		return;
	}

	float RemainingTime = DeltaTime;
	while (RemainingTime >= MIN_TICK_TIME && Iterations < MaxSimulationIterations)
	{
		++Iterations;
		const float TimeTick = GetSimulationTimeStep(RemainingTime, Iterations);
		RemainingTime -= TimeTick;

		const FVector OldLocation = UpdatedComponent->GetComponentLocation();

		FFindFloorResult Floor;
		FindFloor(OldLocation, Floor, false);
		if (!Floor.IsWalkableFloor())
		{
			SetMovementMode(MOVE_Falling);
			StartNewPhysics(RemainingTime + TimeTick, Iterations - 1);
			return;
		}
		const FVector FloorNormal = Floor.HitResult.ImpactNormal;

		// Gravity along the slope: downhill keeps the slide going, uphill ends it sooner.
		const FVector Gravity(0.0f, 0.0f, GetGravityZ());
		Velocity += FVector::VectorPlaneProject(Gravity, FloorNormal) * TimeTick;

		// A little steering: only the input component across the slide direction.
		const FVector VelDir = Velocity.GetSafeNormal();
		const FVector InputOnFloor = FVector::VectorPlaneProject(Acceleration, FloorNormal) / FMath::Max(GetMaxAcceleration(), 1.0f);
		const FVector Across = InputOnFloor - VelDir * FVector::DotProduct(InputOnFloor, VelDir);
		Velocity += Across.GetClampedToMaxSize(1.0f) * SlideSteerAcceleration * TimeTick;

		// Exponential friction decay.
		Velocity *= FMath::Exp(-SlideFriction * TimeTick);
		Velocity = FVector::VectorPlaneProject(Velocity, FloorNormal).GetClampedToMaxSize(SlideMaxSpeed);

		const FVector Delta = Velocity * TimeTick;
		FHitResult Hit(1.0f);
		SafeMoveUpdatedComponent(Delta, UpdatedComponent->GetComponentQuat(), true, Hit);
		if (Hit.Time < 1.0f)
		{
			HandleImpact(Hit, TimeTick, Delta);
			SlideAlongSurface(Delta, 1.0f - Hit.Time, Hit.Normal, Hit, true);
		}

		FindFloor(UpdatedComponent->GetComponentLocation(), CurrentFloor, false);
		if (!CurrentFloor.IsWalkableFloor())
		{
			SetMovementMode(MOVE_Falling);
			StartNewPhysics(RemainingTime, Iterations);
			return;
		}
		AdjustFloorHeight();
		SetBaseFromFloor(CurrentFloor);

		// Keep the velocity consistent with what actually happened (walls stop the slide).
		if (!bJustTeleported)
		{
			const FVector Moved = UpdatedComponent->GetComponentLocation() - OldLocation;
			Velocity = FVector::VectorPlaneProject(Moved / TimeTick, CurrentFloor.HitResult.ImpactNormal);
		}

		SlideElapsed += TimeTick;
		if (SlideElapsed >= SlideMaxTime || Velocity.Size() < SlideExitSpeed || !bWantsToCrouch)
		{
			SetMovementMode(MOVE_Walking);
			StartNewPhysics(RemainingTime, Iterations);
			return;
		}
	}
}

bool USOCharacterMovementComponent::TryMantle()
{
	if (!CharacterOwner || !UpdatedComponent || IsMantling())
	{
		return false;
	}
	UWorld* World = GetWorld();
	const UCapsuleComponent* Capsule = CharacterOwner->GetCapsuleComponent();
	if (!World || !Capsule)
	{
		return false;
	}

	const FVector Forward = UpdatedComponent->GetForwardVector().GetSafeNormal2D();
	const FVector Input = Acceleration.GetSafeNormal2D();
	if (Forward.IsNearlyZero() || FVector::DotProduct(Input, Forward) < 0.5f)
	{
		return false; // only when pushing toward the ledge
	}

	const float Radius = Capsule->GetScaledCapsuleRadius();
	const float HalfHeight = Capsule->GetScaledCapsuleHalfHeight();
	const FVector Location = UpdatedComponent->GetComponentLocation();
	const float FeetZ = Location.Z - HalfHeight;

	FCollisionQueryParams Params(SCENE_QUERY_STAT(SOMantle), false, CharacterOwner);
	FCollisionResponseParams Response;
	InitCollisionParams(Params, Response);
	const ECollisionChannel Channel = UpdatedComponent->GetCollisionObjectType();

	// 1. A wall in front, somewhere between just above step height and the max ledge height.
	FHitResult WallHit;
	bool bFoundWall = false;
	for (float Height = MaxStepHeight - 10.0f; Height <= MantleMaxHeight; Height += 15.0f)
	{
		const FVector Start(Location.X, Location.Y, FeetZ + Height);
		const FVector End = Start + Forward * (Radius + MantleReach);
		if (World->LineTraceSingleByChannel(WallHit, Start, End, Channel, Params, Response)
			&& WallHit.ImpactNormal.Z < 0.5f && FVector::DotProduct(-WallHit.ImpactNormal.GetSafeNormal2D(), Forward) > 0.5f)
		{
			bFoundWall = true;
			break;
		}
	}
	if (!bFoundWall)
	{
		return false;
	}

	// 2. The top of the ledge: a sphere swept down just beyond the wall face.
	const FVector WallNormal2D = WallHit.ImpactNormal.GetSafeNormal2D();
	const FVector TopXY = WallHit.ImpactPoint - WallNormal2D * (Radius + 6.0f);
	const FVector DownStart(TopXY.X, TopXY.Y, FeetZ + MantleMaxHeight + Radius + 2.0f);
	const FVector DownEnd(TopXY.X, TopXY.Y, FeetZ + MantleMinHeight - 2.0f);
	FHitResult TopHit;
	if (!World->SweepSingleByChannel(TopHit, DownStart, DownEnd, FQuat::Identity, Channel, FCollisionShape::MakeSphere(Radius * 0.6f), Params, Response)
		|| TopHit.bStartPenetrating || !IsWalkable(TopHit))
	{
		return false;
	}
	const float LedgeZ = TopHit.ImpactPoint.Z;
	const float LedgeHeight = LedgeZ - FeetZ;
	if (LedgeHeight < MantleMinHeight || LedgeHeight > MantleMaxHeight)
	{
		return false;
	}

	// 3. The standing capsule fits on top, and the path (straight up, then over) is clear.
	const FVector Target(TopXY.X, TopXY.Y, LedgeZ + HalfHeight + 2.0f);
	const FCollisionShape Shape = Capsule->GetCollisionShape(-2.0f);
	if (World->OverlapBlockingTestByChannel(Target, FQuat::Identity, Channel, Shape, Params, Response))
	{
		return false;
	}
	const FVector Raised(Location.X, Location.Y, Target.Z);
	FHitResult PathHit;
	if (World->SweepSingleByChannel(PathHit, Location, Raised, FQuat::Identity, Channel, Shape, Params, Response)
		|| World->SweepSingleByChannel(PathHit, Raised, Target, FQuat::Identity, Channel, Shape, Params, Response))
	{
		return false;
	}

	MantleStart = Location;
	MantleTarget = Target;
	MantleElapsed = 0.0f;
	MantleDuration = MantleBaseTime + MantleTimePerMeter * (LedgeHeight / 100.0f);
	Velocity = FVector::ZeroVector;
	SetMovementMode(MOVE_Custom, static_cast<uint8>(ESOCustomMovementMode::Mantle));
	return true;
}

void USOCharacterMovementComponent::PhysMantle(float DeltaTime, int32 Iterations)
{
	if (DeltaTime < MIN_TICK_TIME || !UpdatedComponent)
	{
		return;
	}

	MantleElapsed += DeltaTime;
	const float Alpha = MantleDuration > 0.0f ? FMath::Clamp(MantleElapsed / MantleDuration, 0.0f, 1.0f) : 1.0f;

	// Up first (eased out), then over the lip (smooth step): this is the path TryMantle validated.
	const float Rise = FMath::Clamp(Alpha / 0.6f, 0.0f, 1.0f);
	const float RiseEased = 1.0f - FMath::Square(1.0f - Rise);
	const float Over = FMath::SmoothStep(0.0f, 1.0f, FMath::Clamp((Alpha - 0.6f) / 0.4f, 0.0f, 1.0f));

	const FVector Desired(
		FMath::Lerp(MantleStart.X, MantleTarget.X, Over),
		FMath::Lerp(MantleStart.Y, MantleTarget.Y, Over),
		FMath::Lerp(MantleStart.Z, MantleTarget.Z, RiseEased));
	const FVector Delta = Desired - UpdatedComponent->GetComponentLocation();
	MoveUpdatedComponent(Delta, UpdatedComponent->GetComponentQuat(), false);
	Velocity = Delta / DeltaTime;

	if (Alpha >= 1.0f)
	{
		Velocity = (MantleTarget - MantleStart).GetSafeNormal2D() * MantleExitSpeed;
		SetMovementMode(MOVE_Walking);
	}
}
