#pragma once

#include "CoreMinimal.h"
#include "SOCombatCharacter.h"
#include "SOEnemy.generated.h"

class USkeletalMesh;
class UAnimSequenceBase;
class ASOEnemyAIController;
class ASOCombatCharacter;
struct FSOSpeciesVariant;

/**
 * A creature. One class per species (see SOSpecies.h): everything it is lives in its class (body, clips, voice, gun,
 * numbers, its own moves in ThinkCombat), it names itself with SpeciesId, and levels ask for it by that id. The
 * defaults here are the feral stalker (hp 140, 5.4 m/s, melee 18 damage at 2.2 m every 0.9 s). Melee strikes land
 * after a wind-up if the target is still in reach.
 */
UCLASS()
class SOAI_API ASOEnemy : public ASOCombatCharacter
{
	GENERATED_BODY()

public:
	ASOEnemy(const FObjectInitializer& ObjectInitializer);

	/** What it is: the id every level asks for it by (USOSpeciesLibrary). A class without one is not a species. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "SO|Species")
	FName SpeciesId;

	/** Server: a level's dressing on top of the species' own numbers (health, damage, speed, aim, sight, another gun,
	 *  another name). The only way a level changes a creature; its behaviour stays the species'. Before it begins play
	 *  (USOSpeciesLibrary::Spawn does that) it also arms itself with the variant's gun. */
	virtual void ApplyVariant(const FSOSpeciesVariant& Variant);
	FName GetVariantId() const { return VariantId; }

	/** What its special moves multiply their damage by (a variant's). */
	float GetDamageScale() const { return DamageScale; }

	/** Loads everything it needs to appear (body, clips, voice, gun; WeaponOverride: a variant's) into OutHeld. */
	virtual void LoadSpeciesContent(FName WeaponOverride, TArray<UObject*>& OutHeld) const;

	/** What the player sees (the boss bar). */
	UPROPERTY(EditAnywhere, Replicated, BlueprintReadOnly, Category = "SO|Enemy")
	FText DisplayName;

	/** Why it takes no damage right now (shown under the boss bar). */
	UPROPERTY(Replicated, BlueprintReadOnly, Category = "SO|Enemy")
	FText ImmuneReason;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Enemy")
	float WalkSpeed = 220.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Enemy")
	float RunSpeed = 540.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Enemy")
	float MeleeDamage = 18.0f;

	/** Reach from capsule edge to capsule edge (cm). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Enemy")
	float MeleeRange = 220.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Enemy")
	float MeleeCooldown = 0.9f;

	/** Strike lands this long after the attack starts. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Enemy")
	float MeleeWindup = 0.35f;

	/** Forward lunge speed at the start of an attack (cm/s). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Enemy")
	float LungeSpeed = 520.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Enemy")
	float SightRange = 3500.0f;

	UPROPERTY(EditDefaultsOnly, Category = "SO|Content")
	TSoftObjectPtr<USkeletalMesh> BodyMesh;

	UPROPERTY(EditDefaultsOnly, Category = "SO|Content")
	FString ClipPathPrefix = TEXT("/Game/Characters/Stalker/Anims/A_Stalker_");

	/** Extra one-shot clips (<ClipPathPrefix><Name>) the creature's special moves play (Cast, Slam, ...). */
	UPROPERTY(EditDefaultsOnly, Category = "SO|Content")
	TArray<FName> ActionClips;

	/** Its sounds: <SoundPrefix>_attack / _hurt / _death. */
	UPROPERTY(EditDefaultsOnly, Category = "SO|Content")
	FString SoundPrefix = TEXT("stalker");

	/** Server, every think (~10 Hz) with a target: a creature's own fighting (ranged, specials). Return true when it
	 *  handled this think (the controller then does nothing more); false falls back to chase and melee. */
	virtual bool ThinkCombat(ASOEnemyAIController* AI, ASOCombatCharacter* Target) { return false; }

	/** Server: plays a named action clip on every machine. */
	void PlayAction(FName Clip, float Rate = 1.0f);
	float GetActionLength(FName Clip) const;

	/** Server: damages every hostile within Radius of Center (a slam, a blast) and throws them back by Knock cm/s. */
	int32 DamageAround(const FVector& Center, float Radius, float Damage, float Knock);

	/** Server: starts a melee attack on Target if off cooldown. */
	bool TryAttack(AActor* Target);

	bool IsAttacking() const { return PendingStrikeTime >= 0.0f; }
	float GetLastAttackTime() const { return LastAttackTime; }
	int32 GetStrikesLanded() const { return StrikesLanded; }

	/** Gap between two capsules (cm). */
	float DistanceTo(const AActor* Other) const;

	void SetRunning(bool bRun);

	// --- Arms: the Altered carry our guns ---------------------------------------------------------------------

	/** The gun it carries (an archetype of Data/game_data.json); None = claws only. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Enemy|Arms")
	FName WeaponArchetype;

	/** Its rounds hit this much softer than a player's. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Enemy|Arms")
	float WeaponDamageScale = 0.35f;

	/** How far its shots stray at 10 m (cm); grows with range and a moving target, shrinks the longer it tracks. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Enemy|Arms")
	float AimError = 70.0f;

	/** The range it likes to fight at (cm). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Enemy|Arms")
	float PreferredRange = 1500.0f;

	/** Fights from cover (peeks, shoots, ducks back, moves on when flanked); false = pushes in. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Enemy|Arms")
	bool bUsesCover = true;

	/** Bursts: how long it holds the trigger and how long it waits between (s). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Enemy|Arms")
	FVector2D BurstTime = FVector2D(0.35f, 1.0f);

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Enemy|Arms")
	FVector2D BurstPause = FVector2D(0.6f, 1.5f);

	/** Shots on an enemy that has not noticed anyone hit this much harder (a clean ambush). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Enemy")
	float AmbushDamageScale = 2.0f;

	bool IsArmed() const { return GetWeapon() != nullptr; }

	/** Server: what it aims at (null = nothing: the gun comes down). */
	void SetAimTarget(AActor* InTarget);
	AActor* GetAimTarget() const { return AimTarget.Get(); }

	/** Server: wants to shoot its aim target (the burst rhythm, line of fire and reloads are its own). */
	void SetWantsFire(bool bWants) { bWantsFire = bWants; }
	bool WantsFire() const { return bWantsFire; }
	int32 GetShotsFired() const { return ShotsFired; }

	/** A clear line from its eyes to Other's body for a round: the same trace a bullet makes, a little fat (no shots
	 *  through a crack), blocked by the world and by anyone standing in the way (it holds its fire behind a mate). */
	bool HasLineOfFire(const AActor* Other) const;

	/** Would its capsule stand free of the world at Location (the capsule's centre)? Anything that puts it somewhere
	 *  without walking (a blink, a rescue from being wedged) asks first. */
	bool FitsAt(const FVector& Location) const;

	/** It knows someone is there (set by its brain): until then it is unaware and ambushes hit harder. */
	void SetAlert(bool bOn) { bAlert = bOn; }
	bool IsAlert() const { return bAlert; }

	/** A cry in its own voice: idle, query (it heard something), alert (it saw you), hurt, death. */
	void Voice(FName Kind, float Volume = 1.0f);

	/** Its voice set (sounds <VoicePrefix>_<kind>[_N]). */
	UPROPERTY(EditDefaultsOnly, Category = "SO|Content")
	FString VoicePrefix;

	virtual FVector GetAimOrigin() const override;
	virtual FVector GetAimDirection() const override;
	virtual USceneComponent* GetThirdPersonWeaponParent() const override;
	virtual float GetOutgoingDamageScale() const override { return WeaponDamageScale; }
	virtual float ScaleIncomingDamage(float Amount, const AActor* Source, bool bCrit) const override;
	virtual void BeginPlay() override;

	/** Server: on / off immunity (with the reason shown to players). */
	void SetImmune(bool bOn, const FText& Reason = FText());
	virtual bool IsImmune() const override { return bImmune; }

	//~ AActor
	virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;
	virtual void PostInitializeComponents() override;
	virtual void Tick(float DeltaSeconds) override;

protected:
	virtual void HandleDeath() override;

	UFUNCTION(NetMulticast, Unreliable)
	void MulticastAttack();

	UFUNCTION(NetMulticast, Reliable)
	void MulticastAction(FName Clip, float Rate);

	UPROPERTY(Transient)
	TMap<FName, TObjectPtr<UAnimSequenceBase>> Actions;

	void LoadContent();
	UAnimSequenceBase* LoadClip(const TCHAR* Name) const;

	FName VariantId;
	float DamageScale = 1.0f;

	UPROPERTY(Replicated)
	bool bImmune = false;

	/** Places the held gun: at the right shoulder aimed at the target, or carried low. */
	void UpdateGunHold(float DeltaSeconds);
	void TickTrigger(float DeltaSeconds);

	UPROPERTY(VisibleAnywhere, Category = "SO|Enemy|Arms")
	TObjectPtr<USceneComponent> GunHold;

	TWeakObjectPtr<AActor> AimTarget;
	float AimSince = 0.0f;
	float Raise = 0.0f;
	bool bWantsFire = false;
	bool bFiring = false;
	float TriggerUntil = 0.0f;
	float NextBurst = 0.0f;
	int32 ShotsFired = 0;
	int32 LastMag = -1;
	bool bAlert = false;
	float NextIdleVoice = 0.0f;

	float LastAttackTime = -100.0f;
	float PendingStrikeTime = -1.0f;
	int32 StrikesLanded = 0;
	float LastHealthSeen = -1.0f;
	float LastHurtSound = -100.0f;
	TWeakObjectPtr<AActor> AttackTarget;
};
