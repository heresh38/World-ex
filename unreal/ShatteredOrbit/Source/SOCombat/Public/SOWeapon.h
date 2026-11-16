#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "SOLootTypes.h"
#include "SOReload.h"
#include "SOWeapon.generated.h"

class ASOCombatCharacter;
class USOGunRigComponent;
class USOWeaponData;
struct FSOProjectile;

DECLARE_MULTICAST_DELEGATE_OneParam(FSOOnWeaponEvent, FName /*Event*/);

/**
 * A held weapon. Server-authoritative: the trigger and reload requests go to the server, which fires rounds
 * (USOProjectileSubsystem) and owns the ammo (replicated). Every machine plays the reload timeline and poses two
 * rigs: first person (owner only, on the holder's viewmodel) and third person (on the body's hand socket).
 */
UCLASS()
class SOCOMBAT_API ASOWeapon : public AActor
{
	GENERATED_BODY()

public:
	ASOWeapon();

	/** Before FinishSpawning (server). Fills the magazine and reserve from the data (a plain, unrolled copy). */
	void SetData(USOWeaponData* InData);
	USOWeaponData* GetData() const { return Data; }

	/** Before FinishSpawning (server): the rolled copy this actor fires (archetype, rarity, perks, rolls, sight,
	 *  finish, saved ammo). */
	void SetInstance(const FSOWeaponInstance& InInstance);
	const FSOWeaponInstance& GetInstance() const { return Instance; }

	/** What this copy fires with (state.js weaponStats + the sight's zoom). */
	const FSOWeaponStats& GetStats() const { return Stats; }

	/** Mesh-space point on the line of sight: the factory sight, or the mounted optic's eye point. */
	FVector GetSightLocation() const;

	/** Magnified glass mounted (or built in): fully aimed, the scope picture replaces the gun. */
	bool IsScoped() const;

	/** Seconds between shots now (fire rate roll, Overclock while the shield is down). */
	float GetShotInterval() const;

	/** Rampage stacks currently active (0..3). */
	int32 GetRampageStacks() const;

	/** Attaches the rigs to the holder (all machines). */
	void AttachToHolder(ASOCombatCharacter* Holder);

	/** First person: show the viewmodel rig, hide the world rig from the owner. */
	void SetFirstPersonView(bool bFirstPerson);

	/** The holder died: the gun leaves the hands and falls (a physics copy of what the world sees; cosmetic, every
	 *  machine), the held rigs hide. */
	void DropOnDeath(const FVector& HolderVelocity);
	bool IsDropped() const { return bDropped; }

	void StartFire();
	void StopFire();
	void StartReload();
	void CancelReload();

	bool CanReload() const;
	bool IsReloading() const { return bReloading; }

	/** Thermal accumulation (the Sarketh's guns, docs/orion/SARKETH_WEAPONS.md): the crystal's heat 0..1, every shot
	 *  adds the data's HeatPerShot, it cools once the trigger rests. Medium heat: the rounds burn brighter; high heat:
	 *  they fly faster; full heat: the gun vents by itself and cannot fire until it has. */
	bool HasHeat() const;
	float GetHeat() const { return Heat; }
	bool IsVenting() const;
	/** A gun that condenses its rounds from the reserve instead of reloading (USOWeaponData::RefillTime). */
	bool Condenses() const;
	/** Rounds are condensing into it now (the trigger at rest, the crystal cold, room in it and rounds in reserve). */
	bool IsCondensing() const;
	/** Dumps the crystal's heat now (a condensing gun's reload key, or its empty trigger); nothing if it is cold. */
	void StartVent();
	static constexpr float HeatMedium = 0.4f;
	static constexpr float HeatHigh = 0.7f;
	/** How much faster its rounds fly at heat H (1 below HeatHigh, up to the data's HeatSpeed at full). */
	float HeatSpeedScale(float H) const;
	/** How much brighter its rounds burn at heat H (1 below HeatMedium, up to 1.8 at full). */
	static float HeatBright(float H);
	bool IsTriggerHeld() const { return bTriggerHeld; }
	float GetReloadProgress() const { return Reload.GetProgress(); }
	float GetReloadDuration() const { return Reload.GetDuration(); }
	int32 GetMag() const { return Mag; }
	int32 GetReserve() const { return Reserve; }
	float GetLastShotTime() const { return LastShotTime; }
	int32 GetShotsFired() const { return ShotsFired; }

	/** Tests / pickups (server). */
	void SetAmmo(int32 InMag, int32 InReserve) { Mag = InMag; Reserve = InReserve; }

	/** Server: rounds straight from the reserve into the magazine, up to Share of a full one (1 = fill it); any
	 *  reload under way is over. A perk's: a kill, a slide. Returns how many went in. */
	int32 RefillFromReserve(float Share = 1.0f);

	const FSOReloadPose& GetPose() const { return Reload.GetPose(); }
	USOGunRigComponent* GetFirstPersonRig() const { return FirstPersonRig; }
	USOGunRigComponent* GetThirdPersonRig() const { return ThirdPersonRig; }

	/** Reload and shot events (seat, drop, sfx, fired) for audio / effects. */
	FSOOnWeaponEvent OnWeaponEvent;

	//~ AActor
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
	virtual void Tick(float DeltaSeconds) override;
	virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;

protected:
	void FireShot();

	/** A joined player's own machine: shows the shot as the trigger breaks (flash, kick, tracer, sound) on the same
	 *  clock the server fires by. The round, its spread and its damage are the server's; its echo is skipped here. */
	void PredictShot();
	void GrantAmmo();
	void BuildRigs();
	void BeginReloadLocal(bool bEmpty, int32 Rounds, float TimeScale = 1.0f);
	ASOCombatCharacter* GetHolder() const;

	UFUNCTION(Server, Reliable)
	void ServerSetTrigger(bool bHeld);

	UFUNCTION(Server, Reliable)
	void ServerStartReload();

	UFUNCTION(Server, Reliable)
	void ServerCancelReload();

	/** Every pellet's direction comes from Seed, so all machines draw the same spread. */
	UFUNCTION(NetMulticast, Unreliable)
	void MulticastShotFired(FVector_NetQuantize Origin, FVector_NetQuantizeNormal Aim, int32 Seed, float HalfAngle);

	/** Muzzle flash, tracer / projectile trail, impact (cosmetic path) and the shot sound, on every machine that renders. */
	void PlayShotEffects(const FVector& Origin, const FVector& Aim, int32 Seed, float HalfAngle);

	/** Pellet directions for a shot. */
	void ShotDirections(const FVector& Aim, int32 Seed, float HalfAngle, TArray<FVector>& Out) const;

	/** Perks that react to hits and kills (server). */
	void OnRoundHit(const FSOProjectile& Round, const FHitResult& Hit, float Damage);

	UFUNCTION()
	void OnRep_Instance();
	void PlayEventSound(FName Event);
	/** A light gun's reload and heat, seen on the gun in the view that shows it (first person: the viewmodel's place
	 *  in the world): "vent", "intake" (at its flap), "cellpop" (at its cell), "charge" (round the gun), "overheat"
	 *  (a small vent by itself after a long burst). Seconds = how long it runs. */
	void PlayReloadFx(FName Kind, float Seconds);

	UFUNCTION(NetMulticast, Reliable)
	void MulticastReload(bool bStart, bool bEmpty, int32 Rounds, float TimeScale);

	/** A spent magazine / speedloader / husk falls from the world rig (cosmetic). */
	void DropPart(FName Part);

	UFUNCTION()
	void OnRep_Data();

	UPROPERTY(ReplicatedUsing = OnRep_Data)
	TObjectPtr<USOWeaponData> Data;

	UPROPERTY(ReplicatedUsing = OnRep_Instance)
	FSOWeaponInstance Instance;

	FSOWeaponStats Stats;
	int32 BurstLeft = 0;
	int32 RampageStacks = 0;
	float RampageUntil = 0.0f;
	FDelegateHandle HitHandle;

	UPROPERTY(Replicated)
	int32 Mag = 0;

	UPROPERTY(Replicated)
	int32 Reserve = 0;

	UPROPERTY(VisibleAnywhere, Category = "SO|Weapon")
	TObjectPtr<USceneComponent> Root;

	UPROPERTY(VisibleAnywhere, Category = "SO|Weapon")
	TObjectPtr<USOGunRigComponent> FirstPersonRig;

	UPROPERTY(VisibleAnywhere, Category = "SO|Weapon")
	TObjectPtr<USOGunRigComponent> ThirdPersonRig;

	FSOReloadPlayer Reload;
	bool bTriggerHeld = false;
	/** A click waiting for the gun to be ready (fire-rate gap, sprint-to-fire), valid until ShotQueuedUntil. A reload
	 *  drops it (and the held trigger): only a press after the reload fires again. */
	bool bShotQueued = false;
	float ShotQueuedUntil = 0.0f;
	void QueueShot(float Window);
	bool bReloading = false;
	bool bDropped = false;
	float NextShotTime = 0.0f;
	float LastShotTime = -100.0f;

	/** When this gun last killed (server): a perk's faster reload after a kill. */
	float LastKillTime = -100.0f;
	/** The barrel cluster of a rotary gun (rig part `spin`): its angle and how fast it turns (rad, rad/s). */
	float BarrelSpin = 0.0f;
	float BarrelSpinRate = 0.0f;
	/** A light gun's heat: bolts fired in the burst running now (a long one vents by itself when it ends). */
	int32 HeatShots = 0;
	float LastBoltTime = -100.0f;
	/** Thermal accumulation (above): the heat now, the heat as the shot being shown left the gun, when it last fired,
	 *  and until when it vents. Each machine that fires or shows the gun runs it (the server's is the one that counts). */
	float Heat = 0.0f;
	float ShotHeat = 0.0f;
	float LastHeatTime = -100.0f;
	float VentUntil = -100.0f;
	float VentLength = 1.0f;      // (this vent's length, and the heat it began from)
	float VentFrom = 1.0f;
	float RefillCarry = 0.0f;     // (the part of a round condensed so far)
	void AddHeat();
	float LastDryFireTime = -100.0f;
	int32 ShotsFired = 0;
	FRandomStream SpreadStream;
};
