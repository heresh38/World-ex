#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Engine/DataAsset.h"
#include "SOBoss.generated.h"

class ASOConduit;
class ASOEnemy;
class UPointLightComponent;
struct FHitResult;
struct FSOProjectile;

// What makes a creature a boss. A boss is not another kind of creature: it is a species (or a level's variant of
// one) that names a boss table (ASOEnemy::BossId, a variant's "boss"), and the table says how the fight goes:
// its phases by health, the shield between them, where it can be hurt most. Its attacks are abilities like
// everyone's (a phase names the kit it fights with), its damage goes through the one gate, and what it is worth is
// the operation's reward. Data/game_data.json "bosses" is the source (SO_IMPORT_ONLY=bosses -> /Game/Data/DA_Boss_<Id>).

/** One stretch of a boss fight. */
USTRUCT(BlueprintType)
struct SOAI_API FSOBossPhase
{
	GENERATED_BODY()

	/** Shown under the boss's bar while it lasts. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Boss")
	FText Name;

	/** It begins when the boss's health is at or below this share of the whole (the first phase: 1). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Boss")
	float FromHealth = 1.0f;

	/** The abilities it fights with from here on (Data/game_data.json "kits"; none: what it had). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Boss")
	FName Kit;

	/** On its abilities' cooldowns while the phase lasts (below 1: its moves come back faster). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Boss")
	float Cooldown = 1.0f;

	/** On its speed. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Boss")
	float Speed = 1.0f;

	/** On all the damage it takes (armour: below 1). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Boss")
	float DamageTaken = 1.0f;

	/** Seconds between the end of one of its moves and the next, from / to (for a boss that paces itself). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Boss")
	FVector2D MovePause = FVector2D(3.0f, 4.5f);

	/** It begins behind a shield: nothing hurts it until the conduits that feed the shield are destroyed (on the
	 *  level's actors tagged "SOConduit", or Conduits of them in a ring round it); then it reels for Stagger seconds. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Boss")
	bool bShield = false;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Boss")
	int32 Conduits = 3;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Boss", meta = (Units = "s"))
	float Stagger = 5.0f;
};

/** Somewhere a boss is hurt more: a ball round a point on its body. */
USTRUCT(BlueprintType)
struct SOAI_API FSOWeakPoint
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Boss")
	FName Name;

	/** The bone it sits on (none: the body's middle), and how far from it: forward, right, up of the body (cm). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Boss")
	FName Bone;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Boss")
	FVector Offset = FVector::ZeroVector;

	/** A round whose line passes within this of it (cm), on its way in, is a precision hit. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Boss")
	float Radius = 40.0f;

	/** On top of the round's own precision multiplier. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Boss")
	float Scale = 1.5f;

	/** Only from in front of the body (it sits in a hollow, behind plate from the back). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Boss")
	bool bFront = false;

	/** This much damage on it within one phase breaks it: the boss reels for BreakStagger seconds and the point is
	 *  shut until the next phase (0 = it cannot be broken). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Boss")
	float BreakDamage = 0.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Boss", meta = (Units = "s"))
	float BreakStagger = 3.0f;
};

/** A boss fight as data. */
UCLASS(BlueprintType)
class SOAI_API USOBossData : public UPrimaryDataAsset
{
	GENERATED_BODY()

public:
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Boss")
	FName BossId;

	/** In order, the first from full health. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Boss")
	TArray<FSOBossPhase> Phases;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Boss")
	TArray<FSOWeakPoint> WeakPoints;

	/** While it reels it takes this much of everything. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Boss")
	float StaggerDamage = 1.5f;

	/** Shown under its bar while the shield is up. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Boss")
	FText ShieldText;

	/** The phase a boss with this share of its health left belongs in. */
	int32 PhaseAt(float HealthFraction) const;

	/** The table by id ("colossus" -> /Game/Data/DA_Boss_Colossus), loaded; null if it was never imported. */
	static USOBossData* Load(FName BossId);
};

/**
 * Runs a boss's table on its creature (made by ASOEnemy when it names one; on every machine). The server moves it
 * through its phases, raises and breaks its shield, counts what lands on its weak points; what the others need to
 * know travels on the creature itself (ASOEnemy::BossPhase, BossWeakBroken, its immunity), so this component is not
 * replicated. Every machine lights the weak points that are open.
 */
UCLASS()
class SOAI_API USOBossComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	USOBossComponent();

	void Setup(USOBossData* InData);
	const USOBossData* GetData() const { return Data; }

	int32 GetPhase() const;
	const FSOBossPhase* GetPhaseData() const;
	int32 NumPhases() const { return Data ? Data->Phases.Num() : 0; }

	/** Server: the shield goes up now, with its conduits. */
	void StartShield();
	bool IsShielded() const { return bShielded; }
	const TArray<TWeakObjectPtr<ASOConduit>>& GetConduits() const { return Conduits; }

	/** Server: it reels (even one that resists being staggered by others): its brain stops, its moves are cut
	 *  short, and it takes the table's StaggerDamage of everything. */
	void Stagger(float Seconds);
	bool IsStaggered() const;

	/** The weak point a hit landed on (-1: none, or it is shut). */
	int32 WeakPointAt(const FHitResult& Hit) const;
	FVector GetWeakPointLocation(int32 Index) const;
	bool IsWeakPointOpen(int32 Index) const;
	float GetWeakPointDamage(int32 Index) const { return WeakDamage.IsValidIndex(Index) ? WeakDamage[Index] : 0.0f; }

	/** Server: damage landed on a weak point (rounds report themselves; exposed for tests). */
	void HitWeakPoint(int32 Index, float Damage);

	/** The phase's scales, and the table's while it reels. */
	float ScaleDamage(float Amount) const;
	float GetCooldownScale() const;
	float GetSpeedScale() const;
	float NextMovePause() const;

	/** Server: its creature died (the conduits go with it). */
	void OwnerDied();

	DECLARE_MULTICAST_DELEGATE_OneParam(FSOOnBossPhase, int32 /*Phase*/);
	/** Server: a phase began. */
	FSOOnBossPhase OnPhaseChanged;

	virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

private:
	ASOEnemy* GetBoss() const;
	void EnterPhase(int32 Index);
	void BreakShield();
	void OnRoundHit(const FSOProjectile& Round, const FHitResult& Hit, float Applied);

	UPROPERTY(Transient)
	TObjectPtr<USOBossData> Data;

	UPROPERTY(Transient)
	TArray<TObjectPtr<UPointLightComponent>> Lights;

	TArray<TWeakObjectPtr<ASOConduit>> Conduits;
	TArray<float> WeakDamage;
	FDelegateHandle RoundHandle;
	bool bShielded = false;
};
