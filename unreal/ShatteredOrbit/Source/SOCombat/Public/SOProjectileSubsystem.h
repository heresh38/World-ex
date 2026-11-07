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

	TArray<FSOProjectile> Rounds;
	TArray<FBurn> Burns;
	TArray<FSwarm> Swarms;
};
