#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "SOProjectileSubsystem.generated.h"

/** One round in flight: a real projectile with muzzle velocity and bullet drop (kinetic class). */
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

	FSOOnProjectileHit OnHit;

	//~ UTickableWorldSubsystem
	virtual void Tick(float DeltaTime) override;
	virtual TStatId GetStatId() const override;

protected:
	virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;

private:
	TArray<FSOProjectile> Rounds;
};
