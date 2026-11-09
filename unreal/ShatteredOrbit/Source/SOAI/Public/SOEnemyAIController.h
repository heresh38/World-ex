#pragma once

#include "CoreMinimal.h"
#include "AIController.h"
#include "SOEnemyAIController.generated.h"

class ASOCombatCharacter;
class ASOEnemy;

UENUM(BlueprintType)
enum class ESOEnemyState : uint8
{
	Idle,
	Wander,
	Chase,
	Attack,
	Dead
};

/**
 * Creature brain at ~10 Hz: wander around home, notice hostiles by sight (cone + line of sight) or by gunfire,
 * chase (nav mesh path when there is one, straight at the target otherwise), melee when in reach, give up after
 * losing sight for a while. A StateTree version replaces this once the behaviours grow (plan: stage 7).
 */
UCLASS()
class SOAI_API ASOEnemyAIController : public AAIController
{
	GENERATED_BODY()

public:
	ASOEnemyAIController();

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|AI")
	float ThinkInterval = 0.1f;

	/** Half-angle of the view cone (degrees); anything closer than AwareRadius is noticed regardless. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|AI")
	float ViewHalfAngle = 70.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|AI")
	float AwareRadius = 600.0f;

	/** Seconds without seeing the target before giving up. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|AI")
	float LoseTargetTime = 6.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|AI")
	float WanderRadius = 700.0f;

	/** An operation's enemy: with nothing in sight it goes for the nearest player anyway, and never gives up. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|AI")
	bool bHunter = false;

	UFUNCTION(BlueprintPure, Category = "SO|AI")
	ESOEnemyState GetState() const { return State; }

	ASOCombatCharacter* GetTarget() const { return Target.Get(); }

	/** True when the pawn moved along a nav mesh path last time it chased. */
	bool UsedNavigation() const { return bUsedNav; }

	//~ AAIController
	virtual void OnPossess(APawn* InPawn) override;
	virtual void OnUnPossess() override;
	virtual void Tick(float DeltaSeconds) override;

protected:
	void Think();
	ASOCombatCharacter* FindTarget() const;
	bool CanSee(const AActor* Other) const;
	void ChaseTarget();
	void Wander();
	void OnNoise(UWorld* World, const FVector& Location, AActor* NoiseInstigator, float Radius);

	TWeakObjectPtr<ASOCombatCharacter> Target;
	FVector LastKnownLocation = FVector::ZeroVector;
	FVector Home = FVector::ZeroVector;
	float LastSeenTime = -100.0f;
	float NextThink = 0.0f;
	float NextWander = 0.0f;
	ESOEnemyState State = ESOEnemyState::Idle;
	bool bUsedNav = false;
	bool bDirectChase = false;
	FDelegateHandle NoiseHandle;
};
