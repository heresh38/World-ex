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

	/** A squad mate hit or killed this close is felt without being looked at (the cry, the body going down) (cm). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|AI")
	float MateFeelRadius = 1300.0f;

	/** An operation's wave creature: it knows where the nearest player is and never gives up. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|AI")
	bool bHunter = false;

	/** How far from its post (where it was put into the world) one that holds ground fights and looks for cover (cm).
	 *  Flankers and hunters are not held by it: they move up, a bound at a time. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|AI")
	float HoldRadius = 1800.0f;

	/** How far one bound goes before it stops, looks and goes again (cm). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|AI")
	float BoundLength = 900.0f;

	/** A round went past or struck near it (ASOEnemy::NoteRoundNear): it knows it is under fire and roughly from where
	 *  (never the place), and one caught in the open makes for cover. */
	void OnShotNear(ASOCombatCharacter* Shooter, const FVector& Origin);

	/** It holds ground: not a flanker, not a hunter (most of a squad). */
	bool HoldsGround() const { return !bFlanker && !bHunter; }
	/** A level or a test may say who goes round the side (otherwise a share of the squad by the difficulty). */
	void SetFlanker(bool bFlank) { bFlanker = bFlank; }
	/** Where it was put into the world. */
	FVector GetHome() const { return Home; }
	/** Seconds since a round last went past it, struck near it or hit it. */
	float SinceShotAt() const;
	/** How many bounds it has made toward a target it lost (for tests). */
	int32 GetBounds() const { return Bounds; }

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
	/** The pack it belongs to is being cut down and it has broken off for a moment. */
	bool IsScattering() const;
	/** How often it has leapt out of the line of fire. */
	int32 GetJukes() const { return Jukes; }
	/** Pushing to where the target went out of sight. */
	bool IsPushing() const { return bPushing; }
	/** How many times it has stepped out of the way of a shot or a levelled gun (for tests). */
	int32 GetDodges() const { return Dodges; }

	/** What the brains cost: thinks done and the time they took since something last read and cleared them (the AI
	 *  debug view does, once a second). Only counted in builds that have the view. */
	static int32 ThinksCounted;
	static double ThinkSecondsCounted;

	/** Gives up the cover it has and looks for another at once (a marksman after a few shots). */
	void Relocate();
	FVector GetLastKnownLocation() const { return LastKnownLocation; }
	bool HasCover() const { return bHasCover; }
	FVector GetCoverPoint() const { return CoverPoint; }

	//~ AAIController
	virtual void OnPossess(APawn* InPawn) override;
	virtual void OnUnPossess() override;
	virtual void Tick(float DeltaSeconds) override;

protected:
	void Think();

	/** In a fight: every second or so, is someone else the better target? One it can see that is much nearer than
	 *  the one it has (or that it cannot see any more), or the one who just hurt it. Switching costs it its cover. */
	void ReconsiderTarget(float T);

	/** How much less often it thinks than ThinkInterval: 1 in a fight or near a player, 2 further off, 5 where
	 *  nobody is (a level's far garrisons cost a fifth of what they did). */
	float ThinkPace() const;
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

	/** The pack's rule (a clawed creature with others of its kind round the same target): true once the pack goes
	 *  in. It goes when three of it (or all of it, if fewer) are within reach of the ring, when the target has come
	 *  to one of them, when this one has been hurt, or when it has waited long enough; and when one goes, all go. */
	bool PackGoes(ASOEnemy* Me, ASOCombatCharacter* Foe, float T);

	/** Holding off: to a point on the ring round the target, on this one's own side, moving round. */
	void HoldRing(ASOEnemy* Me, ASOCombatCharacter* Foe, float T);

	/** A pack that is being cut down breaks off: when a second of its kind dies near this one within PackLossWindow
	 *  seconds of the last, it runs out to its own side and away for a few seconds, then the pack forms its ring
	 *  again (no more often than every ScatterEvery seconds: it is a flinch, not a rout). */
	float ScatterUntil = 0.0f;
	float NextScatter = 0.0f;
	float LastPackLoss = -100.0f;
	static constexpr float PackLossWindow = 4.0f;
	static constexpr float ScatterEvery = 14.0f;

	/** A clawed creature that has been badly hurt on its way in breaks off once (out to its side and away, as when
	 *  its pack is cut down) and comes again from somewhere else. */
	bool bBrokeOff = false;
	float NextJuke = 0.0f;
	int32 Jukes = 0;

	/** The target cannot shoot back this moment (it is loading its gun) and this one saw it a moment ago: an opening
	 *  (not taken on the easiest level). In cover it comes out and fires at once; a pack on its ring goes in. */
	bool TargetIsOpen(const ASOCombatCharacter* Foe, float T) const;
	float NextOpportunity = 0.0f;

	/** The pack goes in until this time (set on every one of it when one decides). */
	float PackGoUntil = 0.0f;
	float PackWaitSince = -1.0f;
	/** Without a nav mesh the hold steers straight at its spot every frame (as the chase does at its target). */
	bool bDirectHold = false;
	FVector HoldSpot = FVector::ZeroVector;
	void Wander();
	void CheckStuck(float DeltaSeconds);
	void OnNoise(UWorld* World, const FVector& Location, AActor* NoiseInstigator, float Radius);
	/** Somebody was hit (or, with Amount < 0, killed). If it is this one, it knows who; if it is a mate this one sees
	 * or stands near, it is warned; a mate that reacts is seen by the next (EnterCombat passes it on). */
	void OnHit(ASOCombatCharacter* Victim, AActor* Source, float Amount, UWorld* World);
	void OnDied(ASOCombatCharacter* Victim, AActor* Killer, UWorld* World);
	/** Does this one notice what just happened to Mate (near enough to feel it, or in view)? */
	bool Notices(const AActor* Mate) const;
	ASOCombatCharacter* NearestPlayer() const;
	/** Foe has its sights on this creature (a player's aim within a few degrees). Nothing dodges for it any more (the
	 *  owner: aimed down the sights they "just move out of the way fast ... shooting needs to be a bit more easier"). */
	bool AimedAt(const ASOCombatCharacter* Foe) const;
	/** Where it believes someone is that it heard or saw the rounds of but has not seen: At, off by an error that grows
	 *  with the distance (a tenth or so of it). */
	FVector Guess(const FVector& At) const;
	/** P is on the ground it holds (always true for one that does not hold ground). */
	bool OnItsGround(const FVector& P) const;
	/** Steps to the side of the line to Foe (a nav point; a little back if Foe is close). */
	bool Sidestep(const ASOCombatCharacter* Foe);
	/** The target is out of sight (or it holds no line on it): move up toward where it was, a bound at a time (the next
	 *  stretch of the way, then a moment there looking), flankers round its side; one that holds ground goes no
	 *  further than the edge of its ground. Never one run down the street. */
	void Push();
	float BoundPauseUntil = 0.0f;
	bool bBounding = false;
	int32 Bounds = 0;
	/** When rounds last went past it or struck near it (or hit it). */
	float LastShotAtTime = -100.0f;
	/** How long it means to keep the cover it took. */
	float CoverHoldFor = 10.0f;
	/** Where its search goes (the target's last place, or the edge of its ground toward it). */
	FVector SearchCentre = FVector::ZeroVector;
	/** One of its own side near it is keeping the target's last place under fire (so it can move up). */
	bool SquadSuppressing() const;
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
	float NextTargetCheck = 0.0f;
	TWeakObjectPtr<ASOCombatCharacter> LastAttacker;
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
	FDelegateHandle HitHandle;
	FDelegateHandle DiedHandle;
};
