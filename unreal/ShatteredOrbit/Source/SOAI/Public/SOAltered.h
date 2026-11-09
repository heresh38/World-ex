#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "SOEnemy.h"
#include "SOAltered.generated.h"

class UPointLightComponent;
class UStaticMeshComponent;
class ASOConduit;

/**
 * The Altered (tools/blender/altered.py): people and beasts the Stillfall changed, grown through with void crystal.
 * The operation's enemies: the Remnant (a fast, frail husk that comes in numbers), the Veilborn (keeps its distance,
 * hurls void bolts, blinks away when pressed), the Bulwark (slow; its shield arm turns shots from the front, it slams
 * the ground when you close in), and the Hollow Colossus (the boss: slam, sweep, void barrage, and twice it kneels into
 * the beam behind a shield that holds until its three conduits are destroyed).
 */

/** A void bolt: a slow violet shot that curves a little toward its target (server-moved, replicated movement). */
UCLASS()
class SOAI_API ASOVoidBolt : public AActor
{
	GENERATED_BODY()

public:
	ASOVoidBolt();

	/** Server: sends it off from where it is. */
	void Launch(AActor* InShooter, const FVector& Direction, AActor* InTarget, float InDamage, float InSpeed = 2600.0f);

	float Damage = 15.0f;
	float Speed = 2600.0f;
	/** How hard it turns toward its target (degrees per second). */
	float Turn = 30.0f;
	float Life = 4.5f;
	float Radius = 18.0f;

	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

protected:
	void Burst(const FVector& At, const FVector& Normal);

	UPROPERTY(VisibleAnywhere, Category = "SO|Bolt")
	TObjectPtr<UStaticMeshComponent> Core;

	UPROPERTY(VisibleAnywhere, Category = "SO|Bolt")
	TObjectPtr<UPointLightComponent> Light;

	FVector Velocity = FVector::ZeroVector;
	TWeakObjectPtr<AActor> Shooter;
	TWeakObjectPtr<AActor> Target;
	float Age = 0.0f;
	bool bSpent = false;
};

/** The operation's stalker: the hunting animal, now carrying an auto rifle and fighting from cover. */
UCLASS()
class SOAI_API ASOArmedStalker : public ASOEnemy
{
	GENERATED_BODY()

public:
	ASOArmedStalker(const FObjectInitializer& ObjectInitializer);
};

/** The Remnant: a husk. Fast, frail; an SMG and its claws; pushes in, comes in numbers. */
UCLASS()
class SOAI_API ASORemnant : public ASOEnemy
{
	GENERATED_BODY()

public:
	ASORemnant(const FObjectInitializer& ObjectInitializer);
};

/** The Veilborn: a scout rifle from cover at long range; now and then a void bolt; blinks aside when you close in
 *  or hurt it badly. */
UCLASS()
class SOAI_API ASOVeilborn : public ASOEnemy
{
	GENERATED_BODY()

public:
	ASOVeilborn(const FObjectInitializer& ObjectInitializer);

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Enemy")
	float MinRange = 800.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Enemy")
	float CastCooldown = 2.4f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Enemy")
	float BoltDamage = 15.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Enemy")
	float BlinkCooldown = 6.0f;

	int32 GetBoltsFired() const { return BoltsFired; }
	int32 GetBlinks() const { return Blinks; }

	virtual bool ThinkCombat(ASOEnemyAIController* AI, ASOCombatCharacter* Target) override;
	virtual void Tick(float DeltaSeconds) override;

protected:
	bool Blink(const FVector& Away);

	TWeakObjectPtr<AActor> CastTarget;
	float NextCast = 0.0f;
	float PendingCast = -1.0f;
	float NextBlink = 0.0f;
	float HealthAtBlink = -1.0f;
	int32 BoltsFired = 0;
	int32 Blinks = 0;
};

/** The Bulwark: slow and huge; its shield arm turns three quarters of what hits it from the front; a one-handed
 *  shotgun; slams the ground up close. */
UCLASS()
class SOAI_API ASOBulwark : public ASOEnemy
{
	GENERATED_BODY()

public:
	ASOBulwark(const FObjectInitializer& ObjectInitializer);

	/** Share of the damage it takes from in front (the shield). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Enemy")
	float FrontDamageScale = 0.25f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Enemy")
	float SlamRadius = 520.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Enemy")
	float SlamDamage = 34.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Enemy")
	float SlamCooldown = 7.0f;

	virtual float ScaleIncomingDamage(float Amount, const AActor* Source, bool bCrit) const override;
	virtual bool ThinkCombat(ASOEnemyAIController* AI, ASOCombatCharacter* Target) override;
	virtual void Tick(float DeltaSeconds) override;
	/** The left arm is the shield: the gun is held in the right hand. */
	virtual bool HoldsWithOneHand() const override { return true; }

protected:
	float NextSlam = 0.0f;
	float PendingSlam = -1.0f;
};

/** A conduit feeding the Colossus's shield: it stands on its socket and tethers a beam to the boss's heart. */
UCLASS()
class SOAI_API ASOConduit : public ASOEnemy
{
	GENERATED_BODY()

public:
	ASOConduit(const FObjectInitializer& ObjectInitializer);

	/** What the tether reaches for. */
	TWeakObjectPtr<AActor> Anchor;

	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

protected:
	virtual void HandleDeath() override;

	UPROPERTY(VisibleAnywhere, Category = "SO|Enemy")
	TObjectPtr<UStaticMeshComponent> Crystal;

	UPROPERTY(VisibleAnywhere, Category = "SO|Enemy")
	TObjectPtr<UStaticMeshComponent> Tether;

	UPROPERTY(VisibleAnywhere, Category = "SO|Enemy")
	TObjectPtr<UPointLightComponent> Light;
};

/**
 * The Hollow Colossus: the operation's boss (~8 m). Close in it slams the ground (a shock ring) or sweeps an arm across
 * its front; at range it throws a barrage of void bolts from its heart. At two thirds and one third of its health it
 * kneels into the beam, immune, while three conduits rise on their sockets (actors tagged "SOConduit", or a ring round
 * where it stands); destroying them breaks the shield and staggers it (it takes half again as much damage for a while).
 */
UCLASS()
class SOAI_API ASOColossus : public ASOEnemy
{
	GENERATED_BODY()

public:
	ASOColossus(const FObjectInitializer& ObjectInitializer);

	/** Health fractions where it raises its shield. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Enemy")
	TArray<float> ShieldAt;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Enemy")
	TSubclassOf<ASOConduit> ConduitClass;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Enemy", meta = (Units = "s"))
	float StaggerTime = 5.0f;

	bool IsShielded() const { return bShielded; }
	bool IsStaggered() const;
	const TArray<TWeakObjectPtr<ASOConduit>>& GetConduits() const { return Conduits; }

	virtual float ScaleIncomingDamage(float Amount, const AActor* Source, bool bCrit) const override;
	virtual bool ThinkCombat(ASOEnemyAIController* AI, ASOCombatCharacter* Target) override;
	virtual void Tick(float DeltaSeconds) override;

	/** Server: raises the shield and the conduits now (exposed for tests). */
	void StartShield();

protected:
	virtual void HandleDeath() override;

	enum class EMove : uint8 { None, Slam, Sweep, Barrage };
	void Begin(EMove Move, FName Clip, float ImpactAfter, float Rate = 1.0f);
	FVector Heart() const;

	TArray<TWeakObjectPtr<ASOConduit>> Conduits;
	TWeakObjectPtr<ASOCombatCharacter> Foe;
	EMove Pending = EMove::None;
	float ImpactAt = 0.0f;
	float MoveEnd = 0.0f;
	float NextMove = 0.0f;
	float NextShot = 0.0f;
	int32 ShotsLeft = 0;
	int32 NextShield = 0;
	float StaggerUntil = -1.0f;
	bool bShielded = false;
	bool bApproach = false;
};
