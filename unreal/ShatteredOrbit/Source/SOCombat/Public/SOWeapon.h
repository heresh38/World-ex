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

	void StartFire();
	void StopFire();
	void StartReload();
	void CancelReload();

	bool CanReload() const;
	bool IsReloading() const { return bReloading; }
	bool IsTriggerHeld() const { return bTriggerHeld; }
	float GetReloadProgress() const { return Reload.GetProgress(); }
	float GetReloadDuration() const { return Reload.GetDuration(); }
	int32 GetMag() const { return Mag; }
	int32 GetReserve() const { return Reserve; }
	float GetLastShotTime() const { return LastShotTime; }
	int32 GetShotsFired() const { return ShotsFired; }

	/** Tests / pickups (server). */
	void SetAmmo(int32 InMag, int32 InReserve) { Mag = InMag; Reserve = InReserve; }

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
	void GrantAmmo();
	void BuildRigs();
	void BeginReloadLocal(bool bEmpty, int32 Rounds);
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

	UFUNCTION(NetMulticast, Reliable)
	void MulticastReload(bool bStart, bool bEmpty, int32 Rounds);

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
	bool bShotQueued = false;
	bool bReloading = false;
	float NextShotTime = 0.0f;
	float LastShotTime = -100.0f;
	float LastDryFireTime = -100.0f;
	int32 ShotsFired = 0;
	FRandomStream SpreadStream;
};
