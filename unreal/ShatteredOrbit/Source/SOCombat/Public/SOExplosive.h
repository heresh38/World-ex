#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "SOExplosive.generated.h"

class UPointLightComponent;
class UStaticMeshComponent;

/** What explodes: its mesh, its numbers, its look and its sound. */
UENUM(BlueprintType)
enum class ESOExplosiveKind : uint8
{
	/** a fuel drum: a rolling fireball */
	Drum,
	/** a gas bottle: a sharper blast */
	Cylinder,
	/** a Sarketh crystal cell: an amber burst of their light */
	Cell,
	/** a wrecked car's tank: the biggest, the wreck thrown up and left burning */
	Vehicle,
};

/**
 * A thing in the world that explodes (the owner's effects guide: "environmental explosion: reactive environment;
 * vehicle explosion: massive and dramatic"). Rounds, blows and blasts hurt it as they hurt a body (USOCombatStatics::
 * ApplyDamage, USOProjectileSubsystem::ApplySplash); hurt past half it is LIT (its leak burns, hissing) and goes by
 * itself a moment later; at nothing it goes at once; a blast that reaches another sets that one off a beat later (a
 * chain). Its blast is a round's splash whose instigator is whoever set it off (what it kills is theirs), heard far off,
 * seen and heard on every machine (USOCue). A level puts them down from data (an operation's plan "explosives").
 * Server-authoritative: what everyone needs (its kind, lit, spent, where it leaks) replicates.
 */
UCLASS()
class SOCOMBAT_API ASOExplosive : public AActor
{
	GENERATED_BODY()

public:
	ASOExplosive();

	/** What it is (its mesh and its numbers); before it begins play, or at once on a server. */
	void SetKind(ESOExplosiveKind InKind);
	ESOExplosiveKind GetKind() const { return Kind; }

	/** Server: a round, a blow or a blast (bBlast: another's blast or a grenade's: it goes after a short, random fuse,
	 *  so a chain ripples). Returns what it took (0 once it has gone). */
	float TakeHit(AActor* Source, float Amount, bool bBlast = false);

	/** Server: it goes now (its splash, its look and sound everywhere). */
	void Detonate();

	bool IsLit() const { return bLit; }
	bool IsSpent() const { return bSpent; }
	float GetHealth() const { return Health; }

	/** Its numbers (SetKind sets them by kind). */
	UPROPERTY(EditAnywhere, Category = "SO|Explosive")
	float MaxHealth = 60.0f;

	/** How far the blast reaches (cm) and what it does at its middle (a quarter at its edge, as a round's splash). */
	UPROPERTY(EditAnywhere, Category = "SO|Explosive")
	float Radius = 520.0f;

	UPROPERTY(EditAnywhere, Category = "SO|Explosive")
	float Damage = 240.0f;

	/** Lit: it goes by itself this long after (s). */
	UPROPERTY(EditAnywhere, Category = "SO|Explosive")
	float BurnFuse = 2.6f;

	/** How many have gone (tests, pictures). */
	static int32 NumDetonated;

	/** The mesh of a kind (/Game/Props/Explosives/SM_EX_<kind>). */
	static FString MeshPath(ESOExplosiveKind InKind);

	virtual void Tick(float DeltaSeconds) override;
	virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;

	virtual void OnConstruction(const FTransform& Transform) override;

protected:
	virtual void BeginPlay() override;

	UFUNCTION()
	void OnRep_Kind();

	UFUNCTION()
	void OnRep_State();

	/** The kind's numbers (health, reach, damage, fuse). */
	void SetNumbers();
	/** The kind's mesh on the component (every machine). */
	void ApplyMesh();
	/** Where its middle is (the blast's centre), world. */
	FVector Middle() const;

	UPROPERTY(VisibleAnywhere, Category = "SO|Explosive")
	TObjectPtr<UStaticMeshComponent> Mesh;

	/** The leak's light while it burns. */
	UPROPERTY(VisibleAnywhere, Category = "SO|Explosive")
	TObjectPtr<UPointLightComponent> Light;

	/** What it is (a level may set it: its mesh and numbers follow). */
	UPROPERTY(EditAnywhere, ReplicatedUsing = OnRep_Kind, Category = "SO|Explosive")
	ESOExplosiveKind Kind = ESOExplosiveKind::Drum;

	UPROPERTY(ReplicatedUsing = OnRep_State)
	bool bLit = false;

	UPROPERTY(ReplicatedUsing = OnRep_State)
	bool bSpent = false;

	/** Where it was hurt (its own space): its leak jets out from there. */
	UPROPERTY(Replicated)
	FVector_NetQuantize LeakAt = FVector::ZeroVector;

	UPROPERTY(Replicated)
	FVector_NetQuantizeNormal LeakOut = FVector::UpVector;

	float Health = 60.0f;
	/** Server: when it goes (lit, or set off by a blast); below 0 not yet. */
	float GoAt = -1.0f;
	TWeakObjectPtr<AActor> SetOffBy;
	/** Every machine: the leak's next puff, its hiss, the wreck's leap after its blast (time since; below 0: none). */
	float LeakTimer = 0.0f;
	float HissTimer = 0.0f;
	float Leap = -1.0f;
	FVector Home = FVector::ZeroVector;
	FRotator HomeTurn = FRotator::ZeroRotator;
	/** (the spent look was put on here: a late joiner gets it once) */
	bool bShownSpent = false;
};
