#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "SOEnemy.h"
#include "SOAltered.generated.h"

class UPointLightComponent;
class UStaticMeshComponent;
class ASOConduit;

/**
 * The Sarketh, the species that holds Meridian (docs/story/WORLD.md). The classes, ids and assets here still carry
 * the names of the first bodies ("the Altered": Remnant, Stalker, Veilborn, Bulwark, Colossus), which are being
 * replaced by one humanoid people ranked by what they are issued; what the player reads is each one's DisplayName.
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

	// Its void bolt is an ability (the kit "veilborn", slot Grenade: the cast's length, the bolt's damage and speed
	// and the cooldown are data).

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Enemy")
	float BlinkCooldown = 6.0f;

	int32 GetBoltsFired() const { return BoltsFired; }
	int32 GetBlinks() const { return Blinks; }

	virtual bool ThinkCombat(ASOEnemyAIController* AI, ASOCombatCharacter* Target) override;
	virtual void Tick(float DeltaSeconds) override;

protected:
	bool Blink(const FVector& Away);

	virtual void OnAbilityWindUp(ESOAbilitySlot Slot) override;
	virtual void OnAbilityUsed(ESOAbilitySlot Slot) override;

	float NextCast = 0.0f;
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

	// Its ground slam is an ability (the kit "bulwark", slot Class: wind-up, radius, damage, cooldown are data).

	virtual float ScaleIncomingDamage(float Amount, const AActor* Source, bool bCrit) const override;
	virtual bool ThinkCombat(ASOEnemyAIController* AI, ASOCombatCharacter* Target) override;
	/** The left arm is the shield: the gun is held in the right hand. */
	virtual bool HoldsWithOneHand() const override { return true; }
	/** Its plate is up between it and From: not while it reels, and not while a gunner holds the trigger. */
	bool PlateFaces(const FVector& From) const;
	virtual bool TurnsBlow(const FVector& From) const override { return PlateFaces(From); }
	/** Behind its plate it is not pinned down by rounds passing close. */
	virtual bool ResistsStatus(const FGameplayTag& Status) const override { return Status == SOTags::Status_Suppressed; }

protected:
	virtual void OnAbilityWindUp(ESOAbilitySlot Slot) override;
	virtual void OnAbilityUsed(ESOAbilitySlot Slot) override;
};

/** The Bearer: the gun carrier. A broad plated husk with a drum of crystal-fused bone on its back that feeds the
 *  heavy gun it carries at the hip in both hands. Slow; it does not take cover: it plants itself and keeps the place
 *  its target went to ground under fire while the others move up. Its plates turn half of what hits it from the
 *  front, but they part round the gun while it holds the trigger, and they are down while it reels. */
UCLASS()
class SOAI_API ASOBearer : public ASOEnemy
{
	GENERATED_BODY()

public:
	ASOBearer(const FObjectInitializer& ObjectInitializer);

	/** Share of the damage it takes from in front while its plates are closed. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Enemy")
	float FrontDamageScale = 0.5f;

	/** Its plates are closed between it and From: not while it fires, not while it reels. */
	bool PlateFaces(const FVector& From) const;

	virtual float ScaleIncomingDamage(float Amount, const AActor* Source, bool bCrit) const override;
	virtual bool TurnsBlow(const FVector& From) const override { return PlateFaces(From); }
	virtual bool HoldsAtHip() const override { return true; }
	/** Behind its plates it is not pinned down by rounds passing close. */
	virtual bool ResistsStatus(const FGameplayTag& Status) const override { return Status == SOTags::Status_Suppressed; }
	virtual void Tick(float DeltaSeconds) override;

protected:
	bool bWasFiring = false;
	float NextBrace = 0.0f;
};

/** A conduit feeding the Colossus's shield: it stands on its socket and tethers a beam to the boss's heart. */
UCLASS()
class SOAI_API ASOConduit : public ASOEnemy
{
	GENERATED_BODY()

public:
	/** A thing, not a creature. */
	virtual bool ResistsStatus(const FGameplayTag& Status) const override { return Status == SOTags::Status_Stagger || Status == SOTags::Status_Slow || Status == SOTags::Status_Suppressed; }

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
 * The Hollow Colossus: the operation's boss. What it is lives here (its body, its gun, how it closes and when it
 * moves); how its fight goes is data: the boss table "colossus" (three phases by health; the second and third begin
 * behind a shield fed by three conduits on the level's sockets, actors tagged "SOConduit", or in a ring round it;
 * breaking them makes it reel; the heart in its hollow chest is its weak point and can be broken once a phase) and
 * the kits its phases name (a sweep across its front, a slam into the ground, a barrage of void bolts from the
 * heart, from the second phase the ground breaking open under those it fights). Every one of its attacks is an
 * ability with a wind-up, and those that land on the ground draw where.
 */
UCLASS()
class SOAI_API ASOColossus : public ASOEnemy
{
	GENERATED_BODY()

public:
	/** Too big to be knocked about or slowed by anyone: it reels only when its shield or its heart breaks
	 *  (USOBossComponent::Stagger). */
	virtual bool ResistsStatus(const FGameplayTag& Status) const override { return Status == SOTags::Status_Stagger || Status == SOTags::Status_Slow || Status == SOTags::Status_Suppressed; }

	ASOColossus(const FObjectInitializer& ObjectInitializer);

	/** Its fight's state (the boss table's: see USOBossComponent). */
	bool IsShielded() const;
	bool IsStaggered() const;
	const TArray<TWeakObjectPtr<ASOConduit>>& GetConduits() const;

	/** Server: raises the shield and the conduits now (exposed for tests). */
	void StartShield();

	/** What it casts leaves it from the heart. */
	virtual FVector GetCastOrigin() const override { return Heart(); }
	virtual bool ThinkCombat(ASOEnemyAIController* AI, ASOCombatCharacter* Target) override;
	virtual void Tick(float DeltaSeconds) override;

protected:
	virtual void HandleDeath() override;

	FVector Heart() const;

	TWeakObjectPtr<ASOCombatCharacter> Foe;
	float NextMove = 0.0f;
	bool bApproach = false;
	bool bInMove = false;
};
