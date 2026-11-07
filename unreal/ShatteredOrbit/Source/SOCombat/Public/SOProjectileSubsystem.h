#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "SOProjectileSubsystem.generated.h"

/** One projectile in flight: a round with muzzle velocity and drop, an energy bolt (no drop), a rocket or horror goo
 *  (splash, acid over time, a brood swarm). */
USTRUCT(BlueprintType)
struct SOCOMBAT_API FSOProjectile
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadWrite, Category = "Projectile")
	FVector Origin = FVector::ZeroVector;

	UPROPERTY(BlueprintReadWrite, Category = "Projectile")
	FVector Position = FVector::ZeroVector;

	/** cm/s */
	UPROPERTY(BlueprintReadWrite, Category = "Projectile")
	FVector Velocity = FVector::ZeroVector;

	/** Downward acceleration in cm/s^2 (980 = normal gravity). */
	UPROPERTY(BlueprintReadWrite, Category = "Projectile")
	float Gravity = 980.0f;

	UPROPERTY(BlueprintReadWrite, Category = "Projectile")
	float Damage = 10.0f;

	UPROPERTY(BlueprintReadWrite, Category = "Projectile")
	float CritMultiplier = 1.5f;

	/** cm: full damage up to FalloffStart, MinDamageScale at FalloffStart * 2. */
	UPROPERTY(BlueprintReadWrite, Category = "Projectile")
	float FalloffStart = 4000.0f;

	UPROPERTY(BlueprintReadWrite, Category = "Projectile")
	float MinDamageScale = 0.6f;

	/** Seconds before the round is dropped. */
	UPROPERTY(BlueprintReadWrite, Category = "Projectile")
	float Life = 3.0f;

	UPROPERTY(BlueprintReadWrite, Category = "Projectile")
	TWeakObjectPtr<AActor> Instigator;

	/** The weapon that fired it (perks listen to its hits). */
	UPROPERTY(BlueprintReadWrite, Category = "Projectile")
	TWeakObjectPtr<AActor> Weapon;

	/** Splash radius (cm): everyone hostile within it takes damage falling off to 25 % at the edge. */
	UPROPERTY(BlueprintReadWrite, Category = "Projectile")
	float Splash = 0.0f;

	/** Share of the damage dealt again as acid over 3 s. */
	UPROPERTY(BlueprintReadWrite, Category = "Projectile")
	float Dot = 0.0f;

	/** Brood: parasites left where it bursts (each chews for a while). */
	UPROPERTY(BlueprintReadWrite, Category = "Projectile")
	int32 Swarm = 0;

	/** Horror goo: seconds the poison lies on the ground where it lands (a pool hurting anyone hostile standing in it). */
	UPROPERTY(BlueprintReadWrite, Category = "Projectile")
	float Pool = 0.0f;
};

DECLARE_MULTICAST_DELEGATE_ThreeParams(FSOOnProjectileHit, const FSOProjectile& /*Round*/, const FHitResult& /*Hit*/, float /*DamageApplied*/);

/**
 * Simulates every round in the world: each tick a round moves along its ballistic arc with a line trace on the
 * SOBullet channel; on a hit the server applies damage (precision hits on head bones). Clients do not simulate.
 */
UCLASS()
class SOCOMBAT_API USOProjectileSubsystem : public UTickableWorldSubsystem
{
	GENERATED_BODY()

public:
	void Fire(const FSOProjectile& Round);

	/** Advances one round by DeltaTime; returns false once it hit something or expired. */
	bool StepRound(FSOProjectile& Round, float DeltaTime, FHitResult* OutHit = nullptr);

	/** Damage a round deals at this distance (cm) before precision multipliers. */
	static float DamageAtDistance(const FSOProjectile& Round, float Distance);

	/** True for bones that count as a precision hit. */
	static bool IsPrecisionBone(FName Bone);

	int32 GetNumInFlight() const { return Rounds.Num(); }
	int32 GetNumBurning() const { return Burns.Num(); }
	int32 GetNumPools() const { return Pools.Num(); }

	/** Seconds poison stays on the ground. */
	static constexpr float PoolSeconds = 5.0f;

	/** Pool radius (cm) for a goo round with this splash radius (cm). */
	static float PoolRadius(float Splash) { return FMath::Clamp(Splash * 0.8f, 120.0f, 600.0f); }

	/** Poison on the ground at Point (projected onto the floor below it, server): PerSecond to everyone hostile within
	 *  Radius for Duration seconds. A pool landing on a fresh one of the same shooter feeds it instead of stacking. */
	void AddPool(AActor* Instigator, const FVector& Point, float Radius, float PerSecond, float Duration);

	/** The floor under Point (WorldStatic), or false when there is none within 6 m. */
	static bool FindFloor(const UWorld* World, const FVector& Point, FVector& OutFloor, FVector& OutNormal);

	/** Damage in a radius around Center (server): linear falloff to 25 % at the edge, blocked by walls. Returns the
	 *  total applied. Hit actors are added to OutVictims. */
	float ApplySplash(AActor* Instigator, const FVector& Center, float Radius, float Damage, AActor* Ignore = nullptr, TArray<AActor*>* OutVictims = nullptr);

	/** Acid / parasites: Total damage over Duration seconds to Victim (server). */
	void AddBurn(AActor* Instigator, AActor* Victim, float Total, float Duration = 3.0f);

	FSOOnProjectileHit OnHit;

	//~ UTickableWorldSubsystem
	virtual void Tick(float DeltaTime) override;
	virtual TStatId GetStatId() const override;

protected:
	virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;

private:
	void OnImpact(const FSOProjectile& Round, const FHitResult& Hit, float Applied);

	struct FBurn
	{
		TWeakObjectPtr<AActor> Instigator;
		TWeakObjectPtr<AActor> Victim;
		float PerSecond = 0.0f;
		float Left = 0.0f;
		float Tick = 0.0f;
	};

	struct FSwarm
	{
		TWeakObjectPtr<AActor> Instigator;
		FVector Center;
		float Radius = 300.0f;
		float PerSecond = 0.0f;
		float Left = 0.0f;
		float Tick = 0.0f;
	};

	struct FPool
	{
		TWeakObjectPtr<AActor> Instigator;
		FVector Center;
		float Radius = 150.0f;
		float PerSecond = 0.0f;
		float Cap = 0.0f;
		float Left = 0.0f;
		float Tick = 0.0f;
	};

	/** Flat damage to every hostile character standing within Radius of Center (feet within 1.5 m of its height). */
	void ApplyGround(AActor* Instigator, const FVector& Center, float Radius, float Damage);

	TArray<FSOProjectile> Rounds;
	TArray<FBurn> Burns;
	TArray<FSwarm> Swarms;
	TArray<FPool> Pools;
};
