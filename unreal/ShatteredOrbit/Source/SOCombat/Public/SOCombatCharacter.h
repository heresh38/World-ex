#pragma once

#include "CoreMinimal.h"
#include "AbilitySystemInterface.h"
#include "GameFramework/Character.h"
#include "GameplayAbilitySpecHandle.h"
#include "GameplayTagContainer.h"
#include "Abilities/SOAbilitySet.h"
#include "ActiveGameplayEffectHandle.h"
#include "SOAttributes.h"
#include "SOCombatTypes.h"
#include "SOCombatCharacter.generated.h"

class ASOWeapon;
class USOAbilitySystemComponent;
class USOAttributeSet;
class USOWeaponData;

DECLARE_MULTICAST_DELEGATE_TwoParams(FSOOnHitConfirmed, bool /*bCrit*/, bool /*bKilled*/);

/** What the shooter's machine is told about a blow of theirs that went in (the HUD's damage numbers): how much,
 *  where, whether the victim's shield took it, how precise it was (0 = not; over 1 = a weak point worth more than
 *  the head). Rounds and blows land on the server only, so this travels with the hit's confirmation. */
USTRUCT()
struct SOCOMBAT_API FSOHitReport
{
	GENERATED_BODY()

	UPROPERTY()
	float Amount = 0.0f;

	UPROPERTY()
	FVector_NetQuantize Point = FVector::ZeroVector;

	UPROPERTY()
	bool bShield = false;

	UPROPERTY()
	bool bCrit = false;

	UPROPERTY()
	bool bKilled = false;

	UPROPERTY()
	float Precision = 0.0f;
};
DECLARE_MULTICAST_DELEGATE_OneParam(FSOOnHitReported, const FSOHitReport& /*Report*/);

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

	/** A body only to be looked at (the armoury's stand-in): on no side and hostile to nobody (so never anybody's
	 *  target or anybody's player: before this the creatures turned on the stand-in once the player was down, and an
	 *  operation counted it as a player), takes no damage, never dies, collides with nothing. */
	void SetDisplayOnly();
	bool IsDisplayOnly() const { return bDisplayOnly; }

	/** Scale on the damage of the rounds this character's gun fires (creatures hit softer than players). */
	virtual float GetOutgoingDamageScale() const { return 1.0f; }

	/** Holds its gun in the right hand only (the left arm is busy: a shield). */
	virtual bool HoldsWithOneHand() const { return false; }

	/** Takes no damage at all right now (a boss behind its shield). */
	virtual bool IsImmune() const { return false; }

	/** The damage this body actually takes from Source (armour plates facing the shot, weak points); server. */
	virtual float ScaleIncomingDamage(float Amount, const AActor* Source, bool bCrit) const { return Amount; }

	/** Is a round that landed like this a precision hit, and how much of one: 0 = no; otherwise the scale on the
	 *  round's own precision multiplier (1 = as the gun says). The head and neck by default; a boss adds its weak
	 *  points, which can be worth more. The one rule for everything that can be shot. */
	virtual float PrecisionAt(const FHitResult& Hit) const;

	/** Server: restores health up to the maximum (Siphon), as an effect (USOGameplayEffect_Heal). */
	void Heal(float Amount);

	// --- Abilities and conditions ---
	/** Server: gives this character a kit's abilities, by slot (replacing any it had). Null takes them away. */
	void GrantAbilitySet(USOAbilitySet* Set);

	const USOAbilitySet* GetAbilitySet() const { return AbilitySet; }

	/** Uses the ability in a slot: called on the machine that controls the character (a player's own, predicted and
	 *  confirmed by the server) or on the server for a creature. False if there is none or it cannot be used now. */
	bool ActivateSlot(ESOAbilitySlot Slot);

	/** For the HUD: the slot's charges ready and held, the seconds until the next one is back (0 when all are) and
	 *  the cooldown's length. False if the slot is empty. */
	bool GetAbilityState(ESOAbilitySlot Slot, int32& OutCharges, int32& OutMaxCharges, float& OutRemaining, float& OutCooldown) const;

	UFUNCTION(BlueprintPure, Category = "SO|Combat")
	float GetUltimate() const;
	UFUNCTION(BlueprintPure, Category = "SO|Combat")
	float GetMaxUltimate() const;

	/** Server: charge for the ultimate (negative spends it), as an effect (USOGameplayEffect_Ultimate). */
	void AddUltimate(float Amount);

	/** A blow from there lands on armour, not on the body (what it looks and sounds like: sparks and a ring, not a
	 *  wound). The damage is the gate's business (ScaleIncomingDamage); this is only how the hit is shown. */
	virtual bool TurnsBlow(const FVector& From) const { return false; }

	/** A hand to hand blow of this character's landed on Victim at Point (server; USOMeleeLibrary::Land): how it is
	 *  shown everywhere (the freeze, the sparks, the count). */
	virtual void OnMeleeHit(ASOCombatCharacter* Victim, const FVector& Point, float Weight, float HitStop) {}

	/** Server: damage from someone else just went in on this character (from the damage gate; where it landed:
	 *  USOCombatStatics::LastHit). What the body does about it. */
	virtual void OnTookDamage(AActor* Source, float Amount, bool bCrit) {}

	/** Server: this character's damage went in (from the damage gate): the kit's ultimate charges from it, and its
	 *  passive rule looks at what was hit. */
	void OnDealtDamage(float Amount, bool bKilled, const ASOCombatCharacter* Victim);

	/** Server: shield back at once, up to the maximum, as an effect (USOGameplayEffect_Shield). */
	void AddShield(float Amount);

	/** Carries the condition (Status.*) or state (State.*) tag right now. */
	bool HasStatus(const FGameplayTag& Tag) const;

	/** Seconds the condition has left (the longest of its applications; 0 when it is not on): the HUD's timers. */
	float GetStatusTimeLeft(const FGameplayTag& Tag) const;

	/** Never takes this condition (a boss is not staggered by a punch). */
	virtual bool ResistsStatus(const FGameplayTag& Status) const { return false; }

	/** Scale on the movement speed (1 normally, under 1 while slowed). */
	float GetMoveScale() const;

	/** Fired on the machine of the player whose round went in (the HUD's hit marker and its tick). Rounds are
	 *  simulated on the server only, so the server tells the shooter's machine (ConfirmHit). */
	mutable FSOOnHitConfirmed OnHitConfirmed;

	/** The same hit with its numbers (FSOHitReport): the HUD's damage numbers listen here. */
	mutable FSOOnHitReported OnHitReported;

	/** Server: a round or a blow of this character's did damage (Report: how much and where, for the shooter's HUD). */
	void ConfirmHit(bool bCrit, bool bKilled, const FSOHitReport& Report = FSOHitReport());

	/** An ability was used here: shows it on every machine exactly once (the user's own at once, the others through
	 *  the server). Called by the ability where it ran. */
	void ShowAbility(ESOAbilitySlot Slot, bool bWindUp = false);

	/** Who this character's next ability is meant for (a creature names its target before it uses one; a player's
	 *  abilities go where the player looks and ignore it). */
	void SetAbilityTarget(AActor* Target) { AbilityTarget = Target; }
	AActor* GetAbilityTarget() const { return AbilityTarget.Get(); }

	/** The slot's ability is in its wind-up right now. */
	bool IsAbilityActive(ESOAbilitySlot Slot) const;

	/** Scale on the damage this character's abilities do (a creature's variant: the same blow from a Warden). */
	virtual float GetAbilityDamageScale() const { return 1.0f; }

	/** Scale on how long the slot's ability takes to come back (a player's: its Ordnance for the grenade, its Impact
	 *  for the melee; a creature's: the difficulty level and a boss's phase). */
	virtual float GetAbilityCooldownScale(ESOAbilitySlot Slot) const;

	/** Server: a hostile round just passed close without hitting. It is under fire (Status.Suppressed for a moment):
	 *  its shield does not start refilling, a player's aim is less steady, a creature in cover keeps its head down
	 *  and one in the open shoots wider. At most once in a while per character, however many rounds pass. */
	void NoteNearMiss(AActor* From);

	// --- Attributes (SOAttributes.h) ---

	/** Server: the points this character's gear gives, in place of whatever it gave before. */
	void SetGearAttributes(const FSOAttributePoints& Points);

	/** Its points in an attribute, and what they scale that attribute's thing by (the table's rule). */
	float GetAttribute(ESOAttribute Attribute) const;
	float GetAttributeScale(ESOAttribute Attribute) const;

	/** The colour of this character's abilities' light (the kit's for a player, the Altered's for a creature). */
	virtual FLinearColor GetAbilityColor() const { return FLinearColor(0.45f, 0.9f, 1.0f); }

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

	/** All machines, once per use: the sound, the body's clip, the camera. */
	virtual void OnAbilityUsed(ESOAbilitySlot Slot);

	/** All machines, once, as an ability with a wind-up begins: the warning. */
	virtual void OnAbilityWindUp(ESOAbilitySlot Slot);

	/** The move scale changed (a slow came or went): whoever sets its own walking speed applies it again. */
	virtual void OnMoveScaleChanged() {}

	UFUNCTION(NetMulticast, Unreliable)
	void MulticastAbility(ESOAbilitySlot Slot, bool bWindUp);

	UFUNCTION(Client, Unreliable)
	void ClientHitConfirmed(bool bCrit, bool bKilled, const FSOHitReport& Report);

	/** The kit this character's abilities came from (their numbers, for the abilities and the HUD). */
	UPROPERTY(Replicated, BlueprintReadOnly, Category = "SO|Combat")
	TObjectPtr<USOAbilitySet> AbilitySet;

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
	bool bDisplayOnly = false;

private:
	void HandleMoveScaleChanged(const struct FOnAttributeChangeData& Change);

	TArray<FGameplayAbilitySpecHandle> GrantedAbilities;
	TWeakObjectPtr<AActor> AbilityTarget;
	/** Ultimate charge earned over time, handed over a point at a time. */
	float UltimateOwed = 0.0f;

	float LastNearMiss = -100.0f;

	/** The gear effect that is on (USOGameplayEffect_Gear). */
	FActiveGameplayEffectHandle GearEffect;
};
