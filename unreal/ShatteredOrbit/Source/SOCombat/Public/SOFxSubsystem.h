#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "SOFxSubsystem.generated.h"

class UDecalComponent;
class UInstancedStaticMeshComponent;
class UMaterialInterface;
class UPointLightComponent;
class UStaticMesh;

/** Particle look: which instanced card set draws it. */
enum class ESOFxKind : uint8
{
	Glow,   // additive soft dot (embers, sparks seen head-on)
	Streak, // additive card stretched along the velocity (tracers, spark streaks)
	Star,   // additive muzzle-flash star, along a direction
	Smoke,  // translucent soft dot (dust, smoke, blood mist)
	Count
};

struct FSOFxParticle
{
	ESOFxKind Kind = ESOFxKind::Glow;
	FVector Position = FVector::ZeroVector;
	FVector Velocity = FVector::ZeroVector;
	FVector Axis = FVector::ForwardVector; // Star / fixed streak direction
	float Gravity = 0.0f;                  // cm/s^2 down
	float Drag = 0.0f;                     // 1/s
	float Age = 0.0f;
	float Life = 1.0f;
	float Delay = 0.0f;                    // seconds before it appears
	float Size0 = 10.0f, Size1 = 10.0f;   // cm
	float Length = 0.0f;                   // Streak / Star length (cm); 0 = from speed
	float Intensity0 = 1.0f, Intensity1 = 0.0f;
	FLinearColor Color = FLinearColor::White;
	float Spin = 0.0f;
	bool bFlat = false;  // lies on the surface whose normal is Axis (pools) instead of facing the eye
	bool bHold = false;  // Intensity0 held over the life with a short fade in / out (instead of Intensity0 -> 1)
};

/**
 * Combat effects without Niagara (authorable headless, deterministic for tests): a pooled CPU particle system drawing
 * the Blender effect cards through instanced meshes (one draw per look), bullet-hole decals (ring buffer), and short
 * point-light flashes. All presentation: nothing here affects gameplay. Runs on every machine that renders.
 */
UCLASS()
class SOCOMBAT_API USOFxSubsystem : public UTickableWorldSubsystem
{
	GENERATED_BODY()

public:
	/** Muzzle flash along Dir (star + light + a wisp of smoke). */
	void MuzzleFlash(const FVector& Muzzle, const FVector& Dir, float Scale = 1.0f, bool bViewmodel = false);

	/** A tracer from the muzzle to where the round lands, at the round's speed (cm/s). */
	void Tracer(const FVector& From, const FVector& To, float Speed, const FLinearColor& Color = FLinearColor(1.0f, 0.74f, 0.4f), float Width = 2.2f);

	/** What a slow projectile looks like in flight and where it lands. */
	enum class ETrail : uint8 { Rocket, Acid, Bile, Brood };

	/** A slow projectile (rocket, horror goo): a glowing head that flies the real ballistic arc for FlightTime,
	 *  leaving smoke (rocket) or drips (goo) behind it. */
	void Trail(const FVector& From, const FVector& Velocity, float Gravity, float FlightTime, ETrail Kind, const FLinearColor& Color);

	/** What a blast looks like. */
	enum class EBlast : uint8 { Fire, Acid, Zap };

	/** An explosion / splash / energy burst of about Radius cm, Delay seconds from now. */
	void Blast(const FVector& Point, const FVector& Normal, float Radius, EBlast Kind, const FLinearColor& Color, float Delay = 0.0f);

	/** A round hitting something: sparks + dust + a bullet hole on hard surfaces, a mist of Blood on creatures.
	 *  Delay = flight time. */
	void Impact(const FVector& Point, const FVector& Normal, bool bFlesh, const FLinearColor& Blood, float Delay = 0.0f, bool bDecal = true);

	/** Poison lying on the floor at Point for Duration seconds (glowing goo, bubbles, fumes), Delay seconds from now.
	 *  A splash onto a puddle that is still fresh adds nothing new. */
	void Pool(const FVector& Point, const FVector& Normal, float Radius, const FLinearColor& Color, float Delay, float Duration);
	int32 GetNumPools() const { return PoolMarks.Num(); }

	void Spawn(const FSOFxParticle& Particle);

	int32 GetNumParticles() const { return Particles.Num(); }
	int32 GetNumDecals() const;
	int32 GetNumImpactsPlayed() const { return ImpactsPlayed; }

	/** Hard caps (oldest dropped first). */
	static constexpr int32 MaxParticles = 1500;
	static constexpr int32 MaxDecals = 64;

	//~ UTickableWorldSubsystem
	virtual void Tick(float DeltaTime) override;
	virtual TStatId GetStatId() const override;
	virtual void Deinitialize() override;

protected:
	virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;

private:
	bool EnsureHost();
	void AddDecal(const FVector& Point, const FVector& Normal);
	void FlashLight(const FVector& Point, float Intensity, const FLinearColor& Color, float Duration);

	struct FPendingImpact
	{
		FVector Point, Normal;
		FLinearColor Blood;
		float Delay;
		bool bFlesh, bDecal;
	};

	struct FLightFlash
	{
		TWeakObjectPtr<UPointLightComponent> Light;
		float Age = 0.0f, Life = 0.0f, Peak = 0.0f;
	};

	struct FPendingLight
	{
		FVector Point;
		FLinearColor Color;
		float Intensity, Duration, Delay;
	};

	struct FPoolMark
	{
		FVector Point;
		float Radius;
		float Born;  // world time it was made
		float Until; // world time it is gone
	};
	TArray<FPoolMark> PoolMarks;

	TArray<FSOFxParticle> Particles;
	TArray<FPendingImpact> Pending;
	TArray<FPendingLight> PendingLights;
	TArray<FLightFlash> Lights;
	TWeakObjectPtr<AActor> Host;
	TWeakObjectPtr<UInstancedStaticMeshComponent> Cards[static_cast<int32>(ESOFxKind::Count)];
	TArray<TWeakObjectPtr<UDecalComponent>> Decals;
	int32 NextDecal = 0;
	int32 NextLight = 0;
	int32 ImpactsPlayed = 0;
	FRandomStream Random{ 1337 };
};
