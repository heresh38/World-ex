#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "SOFxSubsystem.generated.h"

class UDecalComponent;
class UMaterialInstanceDynamic;
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

class ASOWeapon;

/** A particle's hold on a gun: a point in the gun's rig frame it keeps its place against. Each frame the particle is
 *  moved by however far that point moved, so what a gun breathes out, draws in or spits stays WITH the gun through a
 *  turn, a stop or the viewmodel's sway (spawned with the holder's velocity of the moment, a reload's cloud hung in the
 *  air where the reload began: the owner, 2026-11-20). Its own velocity is on top of that. */
struct FSOFxAnchor
{
	TWeakObjectPtr<const ASOWeapon> Gun;
	FVector Local = FVector::ZeroVector;  // the point, in the gun's rig frame
	FVector Last = FVector::ZeroVector;   // where it was last frame (world)
	bool bViewmodel = false;              // the first-person gun (its rig is drawn in the viewmodel's space)
	bool IsSet() const { return Gun.IsValid(); }
};

struct FSOFxParticle
{
	ESOFxKind Kind = ESOFxKind::Glow;
	FSOFxAnchor Anchor;
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
	bool bWhole = false; // a streak drawn at its whole Length from the start (it lies where it is, it does not grow out of a muzzle)
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
	/** The flash at the muzzle: tongues of flame in the gun's own colour, a hot core, a wisp of smoke. bThroughScope:
	 * the shooter is looking down a magnified optic (a flash at arm's length fills the lens: only a flicker is drawn). */
	void MuzzleFlash(const FVector& Muzzle, const FVector& Dir, float Scale = 1.0f, bool bViewmodel = false,
		const FLinearColor& Color = FLinearColor(1.0f, 0.74f, 0.4f), bool bThroughScope = false);

	// --- Plasma: what a light gun fires. Not a bullet: a bolt you can see fly. -------------------------------------
	/** A bolt of plasma from the muzzle to where it lands, at its own speed (cm/s): a white-hot core in a corona of
	 *  the gun's colour at the FRONT of a short tail (longer the faster it flies), and what it leaves behind it: the
	 *  air along its path glows as it passes, a length at a time, and cools within a tenth of a second.
	 *  Size: 1 = a rifle's bolt. */
	void PlasmaBolt(const FVector& From, const FVector& To, float Speed, const FLinearColor& Color, float Size = 1.0f,
		const FVector& Carry = FVector::ZeroVector);

	// --- A light gun's reload (and its heat): what it looks like as the gun works. All of it carries the holder's
	// velocity (Carry), so it stays with the gun; bViewmodel = the first-person gun, a hand's breadth from the eye. ---
	/** The heat purged out of an open flap At, along Out, for Duration seconds: a jet of glowing gas that blooms and
	 *  rises, a white-hot core at the opening, sparks thrown out, its light on the hands. Strength 1 = a reload's
	 *  purge; a little after a long burst (the gun venting its heat by itself). */
	void ReloadVent(const FVector& At, const FVector& Out, const FLinearColor& Color, float Duration, float Strength, const FVector& Carry, bool bViewmodel,
		const FSOFxAnchor& Anchor = FSOFxAnchor());
	/** Energy drawn in from the air through an open flap At (Out = the way it faces) for Duration seconds: motes of
	 *  light appearing all round and streaming in, a glow at the opening that grows as it fills. */
	void ReloadIntake(const FVector& At, const FVector& Out, const FLinearColor& Color, float Duration, const FVector& Carry, bool bViewmodel,
		const FSOFxAnchor& Anchor = FSOFxAnchor());
	/** A battery's lock releasing: a puff of vapour and a spit of light round its seat. */
	void ReloadCellPop(const FVector& At, const FLinearColor& Color, const FVector& Carry, bool bViewmodel, const FSOFxAnchor& Anchor = FSOFxAnchor());
	/** The gun charging up as it closes: a ring of its light swelling round it and a flash. */
	void ReloadCharge(const FVector& At, const FLinearColor& Color, float Duration, const FVector& Carry, bool bViewmodel, const FSOFxAnchor& Anchor = FSOFxAnchor());

	/** Plasma landing: it splashes: a flare, drops of it thrown out ALONG the surface, a breath of vapour, a glow on
	 *  the place that cools over half a second, and light by its size (a pellet's is small: a shotgun's pattern must
	 *  not flood a wall). No bullet hole, no dust: nothing solid struck. bFlesh: smaller; the blood is Impact's. */
	void PlasmaImpact(const FVector& Point, const FVector& Normal, const FLinearColor& Color, float Size = 1.0f, float Delay = 0.0f, bool bFlesh = false);

	/** The muzzle of a light gun as it fires: a bloom of its light and a few motes thrown forward. No flame, no smoke. */
	void PlasmaFlash(const FVector& Muzzle, const FVector& Dir, float Scale, bool bViewmodel, const FLinearColor& Color, bool bThroughScope = false);
	int32 GetPlasmaBolts() const { return PlasmaBolts; }

	// --- The Sarketh's slugs (docs/orion/SARKETH_WEAPONS.md): a crystalline slug in an amber field ----------------
	/** A slug from From to To at Speed (cm/s): a white-hot core in an amber shell at the front of a SHORT golden-orange
	 *  trail, drawn in the shooter's frame (Carry) as a plasma bolt is. Size: 1 = the rifle's slug; Bright: 1, more as
	 *  the gun's crystal heats. Delay: seconds before it appears (a slug going on out of a body). */
	void SlugRound(const FVector& From, const FVector& To, float Speed, float Size = 1.0f, float Bright = 1.0f, const FVector& Carry = FVector::ZeroVector,
		float Delay = 0.0f);
	/** Its shell rupturing where it lands: a sharp orange flash, white and gold sparks, dark smoke and a glowing mark
	 *  (into a body: the flash and sparks only). Splash > 0 (a Breach Charge): the whole burst, that radius (cm). */
	void SlugImpact(const FVector& Point, const FVector& Normal, float Size = 1.0f, float Delay = 0.0f, bool bFlesh = false, float Splash = 0.0f);
	/** The muzzle: a hard white-gold flash and the amber field tearing off the slug; no flame, no smoke. */
	void SlugFlash(const FVector& Muzzle, const FVector& Dir, float Scale, bool bViewmodel, float Bright = 1.0f, bool bThroughScope = false);
	int32 GetSlugs() const { return Slugs; }
	/** (where and when plasma last lit what it struck: a pattern of pellets lights the place once) */
	FVector LastPlasmaLightAt = FVector::ZeroVector;
	double LastPlasmaLightTime = -1.0;

	/** A tracer from the muzzle to where the round lands, at the round's speed (cm/s). */
	void Tracer(const FVector& From, const FVector& To, float Speed, const FLinearColor& Color = FLinearColor(1.0f, 0.74f, 0.4f), float Width = 2.2f,
		float Length = 380.0f, bool bBolt = false);

	/** What a slow projectile looks like in flight and where it lands. */
	enum class ETrail : uint8 { Rocket, Acid, Bile, Brood };

	/** A slow projectile (rocket, horror goo): a glowing head that flies the real ballistic arc for FlightTime,
	 *  leaving smoke (rocket) or drips (goo) behind it. */
	void Trail(const FVector& From, const FVector& Velocity, float Gravity, float FlightTime, ETrail Kind, const FLinearColor& Color);

	/** What a blast looks like. */
	enum class EBlast : uint8 { Fire, Acid, Zap };

	/** An explosion / splash / energy burst of about Radius cm, Delay seconds from now. */
	void Blast(const FVector& Point, const FVector& Normal, float Radius, EBlast Kind, const FLinearColor& Color, float Delay = 0.0f);

	/** A blow into the ground: a ring of light racing out along it to Radius, dust lifting behind the ring, chips
	 *  thrown up from the middle. */
	void Shockwave(const FVector& Point, float Radius, const FLinearColor& Color, float Delay = 0.0f);

	/** A blow through the air: an arc of light fanned across HalfAngle (degrees) in front of Origin, out to Reach. */
	void Sweep(const FVector& Origin, const FVector& Forward, float Reach, float HalfAngle, const FLinearColor& Color);

	/** A warning on the ground: where an area attack lands, Time seconds from now. A ring (HalfAngle 180) or a sector
	 *  (opening along Yaw, HalfAngle degrees to each side) of Radius cm, drawn on whatever lies under it, filling
	 *  from the middle outward: when the fill reaches the rim, it lands. Follow: it stays under that actor's feet and
	 *  turns with it (a blow whose user still turns with its target). */
	void Warn(const FVector& Point, float Radius, float HalfAngle, float Yaw, float Time, const FLinearColor& Color, const AActor* Follow = nullptr);

	/** A line of sight made visible: a thin line of light from Shooter (Offset in its own frame) to Target for Time
	 *  seconds. It follows the target until the last Lock seconds, then holds still where it was: what comes down it
	 *  misses whoever moved after that. It thickens and brightens as the time runs out. */
	void AimLine(const AActor* Shooter, const FVector& Offset, const AActor* Target, float Time, float Lock, const FLinearColor& Color);
	int32 GetNumAimLines() const { return AimLines.Num(); }

	/** Warnings on the ground right now. */
	int32 GetNumWarnings() const { return Warnings.Num(); }

	/** A field coming up round a body standing at Feet: lines of light rising in a ring to about Height. */
	void Ward(const FVector& Feet, float Height, const FLinearColor& Color);

	/** A round hitting something: sparks + dust + a bullet hole on hard surfaces, a mist of Blood on creatures.
	 *  Delay = flight time. */
	void Impact(const FVector& Point, const FVector& Normal, bool bFlesh, const FLinearColor& Blood, float Delay = 0.0f, bool bDecal = true);

	/** Poison lying on the floor at Point for Duration seconds (glowing goo, bubbles, fumes), Delay seconds from now.
	 *  A splash onto a puddle that is still fresh adds nothing new. */
	void Pool(const FVector& Point, const FVector& Normal, float Radius, const FLinearColor& Color, float Delay, float Duration);
	int32 GetNumPools() const { return PoolMarks.Num(); }

	void Spawn(const FSOFxParticle& Particle);

	int32 GetNumParticles() const { return Particles.Num(); }
	int32 PlasmaBolts = 0;
	int32 Slugs = 0;
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

	struct FWarning
	{
		TWeakObjectPtr<UDecalComponent> Decal;
		TWeakObjectPtr<UMaterialInstanceDynamic> Material;
		TWeakObjectPtr<const AActor> Follow;
		FVector Point = FVector::ZeroVector;
		FLinearColor Color = FLinearColor::White;
		float Radius = 100.0f, CosHalf = -1.0f, Yaw = 0.0f, YawOffset = 0.0f, Age = 0.0f, Time = 1.0f;
		bool bFollow = false;
	};
	struct FAimLine
	{
		TWeakObjectPtr<const AActor> Shooter, Target;
		FVector Offset = FVector::ZeroVector, End = FVector::ZeroVector;
		FLinearColor Color = FLinearColor::White;
		float Age = 0.0f, Time = 1.0f, Lock = 0.3f;
	};
	TArray<FAimLine> AimLines;
	TArray<FWarning> Warnings;
	TArray<TWeakObjectPtr<UDecalComponent>> FreeWarnings; // (their decals, kept for the next)
	void PlaceWarning(FWarning& W) const;

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
