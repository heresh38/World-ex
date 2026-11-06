#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "SOReload.h"
#include "SOWeapon.generated.h"

class ASOCombatCharacter;
class USOGunRigComponent;
class USOWeaponData;

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

	/** Before FinishSpawning (server). Fills the magazine and reserve from the data. */
	void SetData(USOWeaponData* InData);
	USOWeaponData* GetData() const { return Data; }

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
	virtual void Tick(float DeltaSeconds) override;
	virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;

protected:
	void FireShot();
	void GrantAmmo();
	void BuildRigs();
	void BeginReloadLocal(bool bEmpty);
	ASOCombatCharacter* GetHolder() const;

	UFUNCTION(Server, Reliable)
	void ServerSetTrigger(bool bHeld);

	UFUNCTION(Server, Reliable)
	void ServerStartReload();

	UFUNCTION(Server, Reliable)
	void ServerCancelReload();

	UFUNCTION(NetMulticast, Unreliable)
	void MulticastShotFired();

	UFUNCTION(NetMulticast, Reliable)
	void MulticastReload(bool bStart, bool bEmpty);

	UFUNCTION()
	void OnRep_Data();

	UPROPERTY(ReplicatedUsing = OnRep_Data)
	TObjectPtr<USOWeaponData> Data;

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
	int32 ShotsFired = 0;
	FRandomStream SpreadStream;
};
