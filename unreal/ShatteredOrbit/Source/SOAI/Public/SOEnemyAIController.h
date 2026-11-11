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
	Dead,
	/** Heard or half-saw something: looks, edges toward it, mutters. */
	Suspicious,
	/** Lost the target: goes to where it was last seen and looks round. */
	Search,
	/** Moving to cover. */
	Cover,
	/** In cover: peeks out, shoots, ducks back. */
	Fight
};

/**
 * A creature's brain at ~10 Hz.
 *
 * Senses. Sight: a cone in front (and a weaker peripheral band to the sides), line of sight, range; noticing takes time
 * (awareness fills faster close up, slower for a crouched target, faster for a sprinting one, and a lit flashlight is
 * seen from much farther and from any side). Hearing: gunshots and running feet (ASOCharacter reports them). Being hurt.
 * So a quiet player can come at it from behind or the side and open with an ambush (ASOEnemy::AmbushDamageScale).
 *
 * States. Unaware: stands its post, wanders near home, mutters. Suspicious: turns to the stimulus and edges toward it.
 * Combat: cries out and alerts its squad; armed creatures that use cover look for a spot that hides them from the
 * target but has a peek or a line over the top (a few rings of nav points scored by range, travel, peek, flank angle
 * and other creatures' claims), peek and shoot in bursts, duck back, and move on when flanked or after a while; one in
 * three flanks wide. Others push in shooting (and strike in melee); unarmed ones chase and strike. Search: lost the
 * target, goes to where it was last seen, looks round, then calms down. Hunters (an operation's waves) always know
 * where the nearest player is.
 *
 * It notices when it is stuck (wants to move, has not moved) and steps to a free nav point; if it is ever standing in
 * the world's geometry it is put back on free ground.
 *
 * It does not stand there. Hit in the open, or with a gun levelled at it, it steps aside (and a cover-user finds new
 * cover); badly hurt it falls back to cover further off and stays down longer; when the target goes out of sight the
 * squad does not wait for it to come back: half of them push to where it was (the flankers round its side) while the
 * rest hold, then follow. Hunters know where the players are but only aim and fire at what they actually see. Claws
 * come in round the sides, not in a line. Everyone keeps its own distance so a squad is not a clump.
 */
UCLASS()
class SOAI_API ASOEnemyAIController : public AAIController
{
	GENERATED_BODY()

public:
	ASOEnemyAIController();

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|AI")
	float ThinkInterval = 0.1f;

	/** Half-angle of the sharp view cone (degrees). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|AI")
	float ViewHalfAngle = 60.0f;

	/** Half-angle of the peripheral band (degrees): seen there slowly. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|AI")
	float PeripheralHalfAngle = 100.0f;

	/** Closer than this, someone in its view is noticed at once (cm). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|AI")
	float AwareRadius = 400.0f;

	/** Seconds without seeing the target before it goes searching. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|AI")
	float LoseTargetTime = 6.0f;

	/** Seconds it searches before calming down. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|AI")
	float SearchTime = 12.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|AI")
	float WanderRadius = 700.0f;

	/** Allies within this range join the fight when it cries out (cm). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|AI")
	float AlertRadius = 3000.0f;

	/** An operation's wave creature: it knows where the nearest player is and never gives up. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|AI")
	bool bHunter = false;

	UFUNCTION(BlueprintPure, Category = "SO|AI")
	ESOEnemyState GetState() const { return State; }

	ASOCombatCharacter* GetTarget() const { return Target.Get(); }

	/** How sure it is that someone is there (0..1; 1 = combat). */
	float GetAwareness() const { return Awareness; }
	bool IsInCombat() const { return bInCombat; }

	/** Cover it holds or is heading to (false = none). */
	bool GetCover(FVector& OutPoint) const { OutPoint = CoverPoint; return bHasCover; }

	/** One in three flanks wide. */
	bool IsFlanker() const { return bFlanker; }

	/** A squad mate cried out: join the fight against Other (seen at At) after a short beat. */
	void Alert(ASOCombatCharacter* Other, const FVector& At);

	/** Chases the current target (nav path, or straight at it): for ThinkCombat. */
	void Chase() { ChaseTarget(); }

	/** True when the pawn moved along a nav mesh path last time it chased. */
	bool UsedNavigation() const { return bUsedNav; }

	/** Finds cover from a threat's eye: a nav point hidden from it, with a peek (or a line over the top) for shooting.
	 *  Exposed for tests. */
	bool FindCover(const FVector& ThreatEye, FVector& OutPoint, FVector& OutPeek) const;

	/** Badly hurt: falling back to cover further off. */
	bool IsRetreating() const { return bRetreating; }
	/** Pushing to where the target went out of sight. */
	bool IsPushing() const { return bPushing; }
	/** How many times it has stepped out of the way of a shot or a levelled gun (for tests). */
	int32 GetDodges() const { return Dodges; }

	//~ AAIController
	virtual void OnPossess(APawn* InPawn) override;
	virtual void OnUnPossess() override;
	virtual void Tick(float DeltaSeconds) override;

protected:
	void Think();
	/** Updates Awareness from sight; returns who it sees best (or null). */
	ASOCombatCharacter* Perceive(float Dt);
	/** How fast awareness of Other fills (per second); 0 = not seen. */
	float SightRate(const ASOCombatCharacter* Other) const;
	bool CanSee(const AActor* Other) const;
	void EnterCombat(ASOCombatCharacter* Other, bool bCryOut);
	void LeaveCombat();
	void ThinkUnaware();
	void ThinkCombat();
	void ThinkCoverFight(float Dist);
	void ThinkAssault(float Dist);
	void ChaseTarget();
	void Wander();
	void CheckStuck(float DeltaSeconds);
	void OnNoise(UWorld* World, const FVector& Location, AActor* NoiseInstigator, float Radius);
	ASOCombatCharacter* NearestPlayer() const;
	/** Foe has its sights on this creature (a player's aim within a few degrees). */
	bool AimedAt(const ASOCombatCharacter* Foe) const;
	/** Steps to the side of the line to Foe (a nav point; a little back if Foe is close). */
	bool Sidestep(const ASOCombatCharacter* Foe);
	/** The target is out of sight: go and find it (flankers round its side). */
	void Push();
	/** Out of the world's geometry, onto free nav ground near here. */
	bool Rescue();

	TWeakObjectPtr<ASOCombatCharacter> Target;
	FVector LastKnownLocation = FVector::ZeroVector;
	FVector Stimulus = FVector::ZeroVector;
	FVector Home = FVector::ZeroVector;
	float Awareness = 0.0f;
	float LastSeenTime = -100.0f;
	float LastStimulusTime = -100.0f;
	float NextThink = 0.0f;
	float NextWander = 0.0f;
	float LastThink = 0.0f;
	float SearchUntil = 0.0f;
	float NextQueryVoice = 0.0f;
	float PendingAlertAt = -1.0f;
	TWeakObjectPtr<ASOCombatCharacter> PendingAlertTarget;
	FVector PendingAlertLocation = FVector::ZeroVector;

	// cover
	bool bHasCover = false;
	FVector CoverPoint = FVector::ZeroVector;
	FVector PeekPoint = FVector::ZeroVector;
	float CoverTaken = 0.0f;
	float NextCoverSearch = 0.0f;
	float PhaseUntil = 0.0f;
	bool bPeeking = false;
	float NextStrafe = 0.0f;
	float LastHealth = -1.0f;

	// stuck
	FVector StuckCheckFrom = FVector::ZeroVector;
	float StuckTimer = 0.0f;
	float NextFitCheck = 0.0f;

	// reactions
	float LastHurtTime = -100.0f;
	float NextDodge = 0.0f;
	/** Until then a move it has committed to (a sidestep) is not replaced by the next thought. */
	float MoveCommitUntil = 0.0f;
	float NextRepath = 0.0f;
	bool bRetreating = false;
	bool bPushing = false;
	int32 Dodges = 0;
	/** Its own distance (a share of the species' preferred range) and side (-1 / 1): a squad is not a clump or a line. */
	float RangeBias = 1.0f;
	float SideBias = 1.0f;

	ESOEnemyState State = ESOEnemyState::Idle;
	bool bInCombat = false;
	bool bFlanker = false;
	bool bUsedNav = false;
	bool bDirectChase = false;
	FDelegateHandle NoiseHandle;
};
