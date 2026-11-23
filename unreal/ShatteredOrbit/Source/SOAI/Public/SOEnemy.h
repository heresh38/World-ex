#pragma once

#include "CoreMinimal.h"
#include "SOCombatCharacter.h"
#include "SOEnemy.generated.h"

class USkeletalMesh;
class UAnimSequenceBase;
class ASOEnemyAIController;
class ASOCombatCharacter;
class USOBossComponent;
struct FSOSpeciesVariant;

/**
 * A creature. One class per species (see SOSpecies.h): everything it is lives in its class (body, clips, voice, gun,
 * numbers, its own moves in ThinkCombat), it names itself with SpeciesId, and levels ask for it by that id. The
 * defaults here are the feral stalker (hp 140, 5.4 m/s, melee 18 damage at 2.2 m every 0.9 s). Melee strikes land
 * after a wind-up if the target is still in reach.
 */
/** How a creature moves: a walk, the jog a gunman moves from place to place at, a run (claws; a gunman only for cover
 *  with rounds landing round it, or falling back). */
UENUM(BlueprintType)
enum class ESOPace : uint8
{
	Walk,
	Jog,
	Run
};

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

	/** Its numbers as data (the keys of USOSpeciesTable, see there): every number, switch and range this class lets
	 *  an editor set, as this creature has them now. */
	void GetNumbers(TMap<FName, float>& Out) const;

	/** Sets the numbers it is given (keys it does not have are left alone: the table's entry also holds its brain's).
	 *  Returns how many it set. Called with the species table's entry as the creature is made; before a variant,
	 *  which scales them. */
	int32 ApplyNumbers(const TMap<FName, float>& Numbers);
	FName GetVariantId() const { return VariantId; }
	/** A level's named dressing (a variant with a name of its own): the HUD announces it the first time it is seen. */
	bool IsElite() const { return bElite; }

	//~ ASOCombatCharacter: a variant's own drops (its relic), a boss's, the elites' and the bosses' lists
	virtual FName GetLootKey() const override { return !VariantId.IsNone() ? VariantId : BossId; }
	virtual int32 GetLootTier() const override { return !BossId.IsNone() ? 2 : (bElite ? 1 : 0); }
	//~ ASOCombatCharacter: what the journal learns of it (its species; a variant: its own name)
	virtual FName GetJournalKind() const override { return SpeciesId; }
	virtual FName GetJournalName() const override { return VariantId; }

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

	/** A pack animal: with others of its kind round, it does not go in alone. It holds off PackRing cm from its
	 *  target, moving round it, until enough of the pack is in place, then they all go together
	 *  (ASOEnemyAIController::PackGoes). Only matters to a creature that fights with its claws. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Enemy")
	bool bPack = true;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Enemy")
	float PackRing = 1000.0f;

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

	/** Its rank's colours (the owner, 2026-11-22: "give the different types different colour set, not too wild but
	 *  enough to distinguish them"): tints laid on the Sarketh's own materials as the body is set (ApplyRankColours):
	 *  the pale plates and the claws (MI_skr_armour, MI_skr_claw), the dark lacquer (MI_skr_armour_dark), and the small
	 *  lights on the body (MI_skr_glow_amber, its glow's colour). The eyes stay the species' own. White plates and
	 *  lacquer and a black light = as imported. Never violet (another species' colour). */
	UPROPERTY(EditDefaultsOnly, Category = "SO|Content")
	FLinearColor PlateTint = FLinearColor::White;

	UPROPERTY(EditDefaultsOnly, Category = "SO|Content")
	FLinearColor LacquerTint = FLinearColor::White;

	UPROPERTY(EditDefaultsOnly, Category = "SO|Content")
	FLinearColor LightTint = FLinearColor::Black;

	/** Its sounds: <SoundPrefix>_attack / _hurt / _death. */
	UPROPERTY(EditDefaultsOnly, Category = "SO|Content")
	FString SoundPrefix = TEXT("stalker");

	/** Server, every think (~10 Hz) with a target: a creature's own fighting (ranged, specials). Return true when it
	 *  handled this think (the controller then does nothing more); false falls back to chase and melee. */
	virtual bool ThinkCombat(ASOEnemyAIController* AI, ASOCombatCharacter* Target);

	/** Its kit by rule: while one of its abilities winds up it stands and turns with its target; otherwise it asks
	 *  each ability of its kit whether it would use it now (USOGameplayAbility::WantsUse) and uses the first that
	 *  says yes. True when it is busy with one (the brain leaves it to it this time). A species with moves of its
	 *  own decides those itself and ends on this (Super::ThinkCombat). */
	bool UseKit(ASOEnemyAIController* AI, ASOCombatCharacter* Target, bool bAnyOrder = false);

	/** One of its kit's abilities is winding up or still going. */
	bool IsUsingAbility() const;

	/** It carries its gun low at the right hip, in both hands, not at the shoulder (a gun too heavy to shoulder). */
	virtual bool HoldsAtHip() const { return false; }

	/** Where what it casts leaves it (a bolt, a volley). */
	virtual FVector GetCastOrigin() const;

	// --- A boss --------------------------------------------------------------------------------------------------

	/** The boss table it fights by (Data/game_data.json "bosses"; none: it is not a boss). A species names its own;
	 *  a level makes a boss of any species with a variant ("boss"). See SOBoss.h. */
	UPROPERTY(EditAnywhere, ReplicatedUsing = OnRep_BossId, BlueprintReadOnly, Category = "SO|Enemy")
	FName BossId;

	/** Which phase of its table it is in, and which of its weak points are broken (a bit each): what every machine
	 *  needs to know of the fight (the rest is the server's, in USOBossComponent). */
	UPROPERTY(Replicated, BlueprintReadOnly, Category = "SO|Enemy")
	uint8 BossPhase = 0;

	UPROPERTY(Replicated, BlueprintReadOnly, Category = "SO|Enemy")
	uint8 BossWeakBroken = 0;

	USOBossComponent* GetBoss() const { return Boss; }

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
	/** Walk, jog (JogShare of the way from WalkSpeed to RunSpeed) or run. */
	void SetPace(ESOPace NewPace);
	/** Nothing of the world between the two bodies, and not a floor above or below: a blow can land. */
	bool CanReach(const AActor* Target) const;
	ESOPace GetPace() const { return Pace; }

	/** Where its jog sits between its walk and its run. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Enemy")
	float JogShare = 0.35f;

	//~ ASOCombatCharacter: a round seen or heard near it goes to its brain
	virtual void NoteRoundNear(AActor* From, const FVector& Origin) override;

	//~ ASOCombatCharacter
	virtual void OnMoveScaleChanged() override;
	virtual float GetAbilityDamageScale() const override { return DamageScale; }
	virtual float GetAbilityCooldownScale(ESOAbilitySlot Slot) const override;
	virtual FLinearColor GetAbilityColor() const override { return AbilityColor; }
	virtual float PrecisionAt(const FHitResult& Hit) const override;

	/** The kit this species' own moves come from (Data/game_data.json "kits"; none = it has no abilities). Given on
	 *  the server as it enters play, like a player's. The species decides WHEN to use a slot (ThinkCombat), the kit
	 *  says what it does. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Enemy")
	FName KitId;

	/** The Altered's violet. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Enemy")
	FLinearColor AbilityColor = FLinearColor(0.62f, 0.3f, 1.0f);

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

	/** A suppressor: when its target goes to ground it does not go looking; it keeps the place under fire, in long
	 *  bursts, so the others can move (and they push sooner while it does). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Enemy|Arms")
	bool bSuppressor = false;

	/** Looks for cover above its target (a marksman). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Enemy|Arms")
	bool bLikesHigh = false;

	/** The share of the true lead it gives a moving target once it has tracked it (0 = it shoots at where the target
	 *  is; 1 = it would never miss a target that keeps its course). What it fires takes time to arrive. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Enemy|Arms")
	float ShotLead = 0.7f;

	/** How far a hit knocks its trunk about (1 = a man-sized creature; a heavy one barely moves). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Enemy")
	float FlinchScale = 1.0f;

	/** Server: fire at this place, seen or not, until the time given (suppression). */
	void SuppressAt(const FVector& Point, float Until);
	bool IsSuppressing() const;
	bool IsFiring() const { return bFiring; }

	// --- Every hit counts ------------------------------------------------------------------------------------
	// A hit does three things beside the damage. It CHECKS the creature: for a moment it moves at HitSlow of its
	// speed (a leg hit longer), so fire slows what runs at it. It UNSTEADIES it: the damage, as a share of its full
	// health, fills a meter that drains by PoiseRecover a second; a precise hit counts PrecisionPoise times. When the
	// meter passes Poise the creature STUMBLES: staggered for StumbleTime (the blow it was winding up is lost, an
	// ability's wind-up broken, its fire stops) and knocked a step back; then it cannot be stumbled again for
	// StumbleRest. And it SHOWS: the body is knocked where it was hit (USOLocomotionAnimInstance::HitKick).
	// A creature that resists stagger (a boss: it reels by its own table) is not checked or stumbled.

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Enemy|Hit")
	float Poise = 0.22f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Enemy|Hit")
	float PoiseRecover = 0.12f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Enemy|Hit")
	float PrecisionPoise = 2.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Enemy|Hit")
	float StumbleTime = 0.75f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Enemy|Hit")
	float StumbleRest = 2.2f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Enemy|Hit")
	float HitSlow = 0.55f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Enemy|Hit")
	float HitSlowTime = 0.35f;

	/** What its armour turned still shakes it: this share of the damage a plate took off counts toward the stumble
	 *  (so fire on a plate is never wasted: enough of it and the creature reels, and reeling its plate is down). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Enemy|Hit")
	float ArmourPoise = 0.6f;

	/** The damage its armour took off the blow now being applied (set by the species in ScaleIncomingDamage). */
	mutable float AbsorbedByArmour = 0.0f;

	/** Below this share of its health it is wounded and moves at WoundedSpeed of its speed. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Enemy|Hit")
	float WoundedAt = 0.3f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Enemy|Hit")
	float WoundedSpeed = 0.85f;

	/** Server: it was hit by Source for that much (where: USOCombatStatics::LastHit). See above. */
	void HitReact(AActor* Source, float Amount, bool bPrecision);
	virtual void OnTookDamage(AActor* Source, float Amount, bool bCrit) override;

	/** How unsteady it is right now (0 to Poise), how often it has stumbled, and whether a hit is checking it. */
	float GetPoiseDamage() const { return PoiseDamage; }
	int32 GetStumbles() const { return Stumbles; }
	bool IsChecked() const;

	/** Server: a quick leap out of the line of fire (a clawed creature that is being shot at as it comes). */
	void Juke(const FVector& Direction);

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
	virtual USceneComponent* GetWeaponParent() const override;
	virtual float GetOutgoingDamageScale() const override { return WeaponDamageScale; }
	virtual float ScaleIncomingDamage(float Amount, const AActor* Source, bool bCrit) const override;
	virtual void BeginPlay() override;

	/** Server: on / off immunity (with the reason shown to players). */
	void SetImmune(bool bOn, const FText& Reason = FText());
	virtual bool IsImmune() const override { return bImmune; }

	//~ AActor
	virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;
	virtual void PostActorCreated() override;
	virtual void PostInitializeComponents() override;
	virtual void Tick(float DeltaSeconds) override;

protected:
	virtual void HandleDeath() override;

	/** A creature's ability moves its body: the grant's clip, drawn out so the blow in it lands as the wind-up ends. */
	virtual void OnAbilityWindUp(ESOAbilitySlot Slot) override;
	virtual void OnAbilityUsed(ESOAbilitySlot Slot) override;

	UFUNCTION()
	void OnRep_BossId();

	/** Makes the component that runs its boss table (every machine; nothing if it names none). */
	void MakeBoss();

	UPROPERTY(Transient)
	TObjectPtr<USOBossComponent> Boss;

	UFUNCTION(NetMulticast, Unreliable)
	void MulticastAttack();

	UFUNCTION(NetMulticast, Unreliable)
	void MulticastFlinch(FVector_NetQuantizeNormal Toward, float Strength, ESOHitRegion Region);

	float PoiseDamage = 0.0f;
	float NextStumble = 0.0f;
	float HitSlowUntil = -1.0f;
	bool bHitSlowed = false;
	int32 Stumbles = 0;

	FVector SuppressPoint = FVector::ZeroVector;
	float SuppressUntil = -1.0f;
	float LastFlinch = -100.0f;

	UFUNCTION(NetMulticast, Reliable)
	void MulticastAction(FName Clip, float Rate);

	UPROPERTY(Transient)
	TMap<FName, TObjectPtr<UAnimSequenceBase>> Actions;

	void LoadContent();
	/** lays the rank's colours (PlateTint, LacquerTint, LightTint) on the body's Sarketh materials */
	void ApplyRankColours();
	UAnimSequenceBase* LoadClip(const TCHAR* Name) const;

	FName VariantId;
	UPROPERTY(Replicated)
	bool bElite = false;
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
	bool bRunning = false;
	ESOPace Pace = ESOPace::Walk;
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
