#pragma once

#include "CoreMinimal.h"
#include "AbilitySystemInterface.h"
#include "GameFramework/Character.h"
#include "SOCombatTypes.h"
#include "SOCombatCharacter.generated.h"

class ASOWeapon;
class USOAbilitySystemComponent;
class USOAttributeSet;
class USOWeaponData;

/** Trace channel for rounds (DefaultEngine.ini: GameTraceChannel1 "SOBullet", blocks by default). */
#define SO_TRACE_BULLET ECC_GameTraceChannel1

/**
 * Base for everything that fights: the player and the creatures. Owns its ability system + attributes
 * (health, shield), dies on the server when health reaches 0 (replicated), carries one weapon.
 */
UCLASS(Abstract)
class SOCOMBAT_API ASOCombatCharacter : public ACharacter, public IAbilitySystemInterface
{
	GENERATED_BODY()

public:
	ASOCombatCharacter(const FObjectInitializer& ObjectInitializer);

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Combat")
	ESOFaction Faction = ESOFaction::Neutral;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Combat")
	float StartMaxHealth = 100.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Combat")
	float StartMaxShield = 0.0f;

	/** Colour of the mist and drops when rounds hit this body. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Combat")
	FLinearColor BloodColor = FLinearColor(0.32f, 0.015f, 0.012f);

	/** Killing it can leave loot (pickups); off for things that are not creatures (the Colossus's conduits). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Combat")
	bool bDropsLoot = true;

	/** Seconds the body stays after death (0 = until removed by someone else). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Combat")
	float CorpseLifeSpan = 0.0f;

	//~ IAbilitySystemInterface
	virtual UAbilitySystemComponent* GetAbilitySystemComponent() const override;

	USOAbilitySystemComponent* GetSOAbilitySystem() const { return AbilitySystem; }
	const USOAttributeSet* GetAttributes() const { return Attributes; }

	UFUNCTION(BlueprintPure, Category = "SO|Combat")
	float GetHealth() const;
	UFUNCTION(BlueprintPure, Category = "SO|Combat")
	float GetMaxHealth() const;
	UFUNCTION(BlueprintPure, Category = "SO|Combat")
	float GetShield() const;
	UFUNCTION(BlueprintPure, Category = "SO|Combat")
	float GetMaxShield() const;

	UFUNCTION(BlueprintPure, Category = "SO|Combat")
	bool IsDead() const { return bDead; }

	UFUNCTION(BlueprintPure, Category = "SO|Combat")
	float GetDeathTime() const { return DeathTime; }

	/** Scale on the damage of the rounds this character's gun fires (creatures hit softer than players). */
	virtual float GetOutgoingDamageScale() const { return 1.0f; }

	/** Holds its gun in the right hand only (the left arm is busy: a shield). */
	virtual bool HoldsWithOneHand() const { return false; }

	/** Takes no damage at all right now (a boss behind its shield). */
	virtual bool IsImmune() const { return false; }

	/** The damage this body actually takes from Source (armour plates facing the shot, weak points); server. */
	virtual float ScaleIncomingDamage(float Amount, const AActor* Source, bool bCrit) const { return Amount; }

	/** Server: restores health up to the maximum (Siphon). */
	void Heal(float Amount);

	/** Server: health reached zero. */
	virtual void Die(AActor* Killer);

	// --- Weapon ---
	UFUNCTION(BlueprintPure, Category = "SO|Combat")
	ASOWeapon* GetWeapon() const { return Weapon; }

	/** Server: spawns and equips a weapon built from Data (replaces the current one). */
	ASOWeapon* EquipWeapon(USOWeaponData* Data);

	/** Server: spawns and equips a rolled copy (replaces the current one). */
	ASOWeapon* EquipInstance(const struct FSOWeaponInstance& Instance);

	/** Where rounds start and which way they go (the camera for players, the eyes for creatures). */
	virtual FVector GetAimOrigin() const;
	virtual FVector GetAimDirection() const;

	/** False while e.g. sprinting or just out of a sprint. */
	virtual bool CanFireWeapon() const { return !bDead; }
	virtual bool IsAimingDownSights() const { return false; }
	/** 1 at the hip, smaller while aiming / crouched, larger while moving or airborne. */
	virtual float GetSpreadScale() const { return 1.0f; }

	/** Attach points for the weapon's first-person and third-person rigs. */
	virtual USceneComponent* GetFirstPersonWeaponParent() const { return nullptr; }
	virtual FName GetThirdPersonWeaponSocket() const { return NAME_None; }
	/** A component the third-person rig attaches to instead of a socket (held guns); null = use the socket. */
	virtual USceneComponent* GetThirdPersonWeaponParent() const { return nullptr; }

	/** World point where a point of the first-person viewmodel appears on screen (the viewmodel renders with its own
	 *  field of view); effects such as the muzzle flash are placed there. */
	virtual FVector ViewmodelToWorld(const FVector& ViewmodelPoint) const { return ViewmodelPoint; }

	/** True while the local player sees this character's first-person viewmodel. */
	virtual bool IsFirstPersonView() const { return false; }

	/** A shot left the muzzle (all machines): recoil, viewmodel kick. */
	virtual void OnWeaponFired(float Kick) {}

	//~ AActor
	virtual void PostInitializeComponents() override;
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;
	virtual void PossessedBy(AController* NewController) override;
	virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;
	virtual void Destroyed() override;

protected:
	/** All machines, once: stop moving, drop collision, stop the weapon. */
	virtual void HandleDeath();

	/** Rounds hit the skinned mesh (per-bone, head = precision) when it has a physics asset, else the capsule. */
	void SetupBulletCollision();

	UFUNCTION()
	void OnRep_Dead();

	UFUNCTION()
	void OnRep_Weapon();

	/** The weapon actor changed (all machines, after it attached). */
	virtual void OnWeaponEquipped() {}

	ASOWeapon* SpawnWeapon(TFunctionRef<void(ASOWeapon*)> Setup);

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "SO|Combat")
	TObjectPtr<USOAbilitySystemComponent> AbilitySystem;

	UPROPERTY()
	TObjectPtr<USOAttributeSet> Attributes;

	UPROPERTY(ReplicatedUsing = OnRep_Dead, BlueprintReadOnly, Category = "SO|Combat")
	bool bDead = false;

	UPROPERTY(ReplicatedUsing = OnRep_Weapon, BlueprintReadOnly, Category = "SO|Combat")
	TObjectPtr<ASOWeapon> Weapon;

	float DeathTime = 0.0f;
	bool bDeathHandled = false;
};
