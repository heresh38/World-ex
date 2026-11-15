#include "SOEnemy.h"
#include "SOBoss.h"
#include "SODifficulty.h"
#include "SOLog.h"
#include "Misc/ScopeExit.h"
#include "SOAbility_Bolt.h"
#include "Abilities/SOGameplayAbility.h"
#include "SOCue.h"

#include "Animation/AnimSequenceBase.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Net/UnrealNetwork.h"
#include "SOCombatStatics.h"
#include "SOEnemyAIController.h"
#include "SOLocomotionAnimInstance.h"
#include "SOSound.h"
#include "SOSpecies.h"
#include "SOAttributeSet.h"
#include "SOGunRigComponent.h"
#include "SOLootLibrary.h"
#include "SOLootTypes.h"
#include "SOWeapon.h"
#include "SOWeaponData.h"

ASOEnemy::ASOEnemy(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	PrimaryActorTick.bCanEverTick = true;
	Faction = ESOFaction::Alien;
	SpeciesId = TEXT("stalker_feral");
	DisplayName = NSLOCTEXT("SO", "Stalker", "Runner");
	StartMaxHealth = 140.0f;
	StartMaxShield = 0.0f;
	CorpseLifeSpan = 6.0f;
	BloodColor = FLinearColor::FromSRGBColor(FColor(0x5a, 0x2a, 0x8a)); // enemies.js stalker blood

	// the player's capsule and step rules: it fits and walks wherever a player does
	GetCapsuleComponent()->InitCapsuleSize(34.0f, 90.0f);
	GunHold = CreateDefaultSubobject<USceneComponent>(TEXT("GunHold"));
	GunHold->SetupAttachment(GetCapsuleComponent());
	GunHold->SetUsingAbsoluteLocation(true);
	GunHold->SetUsingAbsoluteRotation(true);
	USkeletalMeshComponent* Body = GetMesh();
	Body->SetRelativeLocation(FVector(0.0f, 0.0f, -90.0f));
	Body->SetRelativeRotation(FRotator(0.0f, -90.0f, 0.0f)); // Blender -Y forward -> UE +X
	Body->SetRelativeScale3D(FVector(1.05f));
	// Animation is budgeted: a creature that is far off or small on the screen updates its pose every few frames
	// and blends between (the engine's update-rate optimisation); one nobody on this machine sees does not
	// update at all, except on a server with others joined (BeginPlay).
	Body->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::OnlyTickPoseWhenRendered;
	Body->bEnableUpdateRateOptimizations = true;

	bUseControllerRotationYaw = false;
	UCharacterMovementComponent* Move = GetCharacterMovement();
	Move->bOrientRotationToMovement = true;
	Move->RotationRate = FRotator(0.0f, 540.0f, 0.0f);
	Move->MaxWalkSpeed = WalkSpeed;
	Move->MaxAcceleration = 2400.0f;
	Move->BrakingDecelerationWalking = 2400.0f;
	Move->bUseRVOAvoidance = true;
	Move->AvoidanceConsiderationRadius = 300.0f;
	Move->MaxStepHeight = 45.0f;
	Move->SetWalkableFloorAngle(46.0f);
	Move->bCanWalkOffLedges = true;

	AIControllerClass = ASOEnemyAIController::StaticClass();
	AutoPossessAI = EAutoPossessAI::PlacedInWorldOrSpawned;

	BodyMesh = TSoftObjectPtr<USkeletalMesh>(FSoftObjectPath(TEXT("/Game/Characters/Stalker/SK_Stalker.SK_Stalker")));
}

void ASOEnemy::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
	Super::GetLifetimeReplicatedProps(OutLifetimeProps);
	DOREPLIFETIME(ASOEnemy, bImmune);
	DOREPLIFETIME(ASOEnemy, ImmuneReason);
	DOREPLIFETIME(ASOEnemy, DisplayName);
	DOREPLIFETIME(ASOEnemy, BossId);
	DOREPLIFETIME(ASOEnemy, BossPhase);
	DOREPLIFETIME(ASOEnemy, BossWeakBroken);
}

namespace
{
	/** How many takes each cry has (sounds <VoicePrefix>_<kind>_<n>; one take: no number). */
	const TMap<FName, int32>& VoiceTakes()
	{
		static const TMap<FName, int32> Takes = { { TEXT("idle"), 4 }, { TEXT("query"), 2 }, { TEXT("alert"), 3 }, { TEXT("hurt"), 3 }, { TEXT("death"), 2 } };
		return Takes;
	}
}

void ASOEnemy::GetNumbers(TMap<FName, float>& Out) const
{
	FSONumbers::Get(this, ASOEnemy::StaticClass(), Out);
	Out.Add(TEXT("health"), StartMaxHealth);
	Out.Add(TEXT("shield"), StartMaxShield);
}

int32 ASOEnemy::ApplyNumbers(const TMap<FName, float>& Numbers)
{
	int32 Set = FSONumbers::Apply(this, ASOEnemy::StaticClass(), Numbers);
	if (const float* Health = Numbers.Find(TEXT("health")))
	{
		StartMaxHealth = *Health;
		++Set;
	}
	if (const float* Shield = Numbers.Find(TEXT("shield")))
	{
		StartMaxShield = *Shield;
		++Set;
	}
	// what follows from them
	GetCharacterMovement()->MaxWalkSpeed = WalkSpeed;
	if (IsActorInitialized() && Attributes)
	{
		const float Fraction = GetMaxHealth() > 0.0f ? GetHealth() / GetMaxHealth() : 1.0f;
		Attributes->InitMaxHealth(StartMaxHealth);
		Attributes->InitHealth(StartMaxHealth * Fraction);
	}
	return Set;
}

void ASOEnemy::PostActorCreated()
{
	Super::PostActorCreated();
	// Its numbers are data: whatever made it (the species library, a level, a test), it takes them from the table
	// here, before it has components running or a variant on top.
	if (const TMap<FName, float>* Numbers = USOSpeciesTable::Get().Find(SpeciesId))
	{
		ApplyNumbers(*Numbers);
	}
}

void ASOEnemy::ApplyVariant(const FSOSpeciesVariant& Variant)
{
	VariantId = Variant.Id;
	if (!Variant.DisplayName.IsEmpty())
	{
		DisplayName = Variant.DisplayName;
	}
	StartMaxHealth *= Variant.Health;
	if (IsActorInitialized() && Attributes)
	{
		const float Fraction = GetMaxHealth() > 0.0f ? GetHealth() / GetMaxHealth() : 1.0f;
		Attributes->InitMaxHealth(StartMaxHealth);
		Attributes->InitHealth(StartMaxHealth * Fraction);
	}
	DamageScale *= Variant.Damage;
	WeaponDamageScale *= Variant.Damage;
	MeleeDamage *= Variant.Damage;
	WalkSpeed *= Variant.Speed;
	RunSpeed *= Variant.Speed;
	GetCharacterMovement()->MaxWalkSpeed *= Variant.Speed;
	if (USOLocomotionAnimInstance* Anim = Cast<USOLocomotionAnimInstance>(GetMesh()->GetAnimInstance()))
	{
		Anim->Clips.WalkSpeed = WalkSpeed;
		Anim->Clips.RunSpeed = RunSpeed;
	}
	AimError *= Variant.AimError;
	SightRange *= Variant.Sight;
	BurstTime *= Variant.Burst;
	BurstPause *= Variant.BurstPause;
	PreferredRange *= Variant.Range;
	bSuppressor |= Variant.bSuppressor;
	bLikesHigh |= Variant.bLikesHigh;
	if (!Variant.Kit.IsNone())
	{
		KitId = Variant.Kit; // (given as it begins play; a creature already in play gets it at once)
		if (HasActorBegunPlay() && HasAuthority())
		{
			GrantAbilitySet(USOAbilitySet::Load(KitId));
		}
	}
	if (!Variant.Boss.IsNone())
	{
		BossId = Variant.Boss; // a level's boss: this species, fighting by that table
		if (HasActorBegunPlay())
		{
			MakeBoss();
		}
	}
	if (!Variant.Weapon.IsNone() && Variant.Weapon != WeaponArchetype)
	{
		WeaponArchetype = Variant.Weapon;
		if (HasActorBegunPlay() && HasAuthority())
		{
			if (const USOLootTables* Tables = USOLootLibrary::GetTables())
			{
				if (ASOWeapon* W = EquipWeapon(Tables->LoadArchetype(WeaponArchetype)))
				{
					W->SetAmmo(W->GetMag() > 0 ? W->GetMag() : 30, 9999);
				}
			}
		}
	}
}

UAnimSequenceBase* ASOEnemy::LoadClip(const TCHAR* Name) const
{
	if (ClipPathPrefix.IsEmpty())
	{
		return nullptr;
	}
	const FString Asset = FPaths::GetBaseFilename(ClipPathPrefix) + Name;
	return TSoftObjectPtr<UAnimSequenceBase>(FSoftObjectPath(ClipPathPrefix + Name + TEXT(".") + Asset)).LoadSynchronous();
}

void ASOEnemy::LoadSpeciesContent(FName WeaponOverride, TArray<UObject*>& OutHeld) const
{
	auto Hold = [&OutHeld](UObject* O) { if (O) { OutHeld.AddUnique(O); } };
	Hold(BodyMesh.LoadSynchronous());
	for (const TCHAR* Name : { TEXT("Idle"), TEXT("Walk"), TEXT("Run"), TEXT("Attack"), TEXT("Death") })
	{
		Hold(LoadClip(Name));
	}
	for (const FName& Name : ActionClips)
	{
		Hold(LoadClip(*Name.ToString()));
	}
	if (!VoicePrefix.IsEmpty())
	{
		for (const TPair<FName, int32>& Take : VoiceTakes())
		{
			for (int32 N = 1; N <= Take.Value; ++N)
			{
				Hold(USOSoundLibrary::Find(FName(FString::Printf(TEXT("%s_%s_%d"), *VoicePrefix, *Take.Key.ToString(), N))));
			}
		}
	}
	const FName Gun = WeaponOverride.IsNone() ? WeaponArchetype : WeaponOverride;
	if (const USOLootTables* Tables = Gun.IsNone() ? nullptr : USOLootLibrary::GetTables())
	{
		if (USOWeaponData* Data = Tables->LoadArchetype(Gun))
		{
			Hold(Data);
			Hold(Data->BodyMesh.LoadSynchronous());
		}
	}
}

void ASOEnemy::SetImmune(bool bOn, const FText& Reason)
{
	bImmune = bOn;
	ImmuneReason = bOn ? Reason : FText();
}

void ASOEnemy::PostInitializeComponents()
{
	LoadContent();
	Super::PostInitializeComponents();
}

void ASOEnemy::LoadContent()
{
	USkeletalMeshComponent* Body = GetMesh();
	if (!Body->GetSkeletalMeshAsset() && !BodyMesh.IsNull())
	{
		if (USkeletalMesh* Loaded = BodyMesh.LoadSynchronous())
		{
			Body->SetSkeletalMesh(Loaded);
		}
	}
	if (!Body->GetSkeletalMeshAsset())
	{
		return;
	}
	if (!Body->GetAnimInstance())
	{
		Body->SetAnimInstanceClass(USOLocomotionAnimInstance::StaticClass());
	}
	if (USOLocomotionAnimInstance* Anim = Cast<USOLocomotionAnimInstance>(Body->GetAnimInstance()))
	{
		auto Clip = [this](const TCHAR* Name) { return LoadClip(Name); };
		Anim->Clips.Idle = Clip(TEXT("Idle"));
		Anim->Clips.Walk = Clip(TEXT("Walk"));
		Anim->Clips.Run = Clip(TEXT("Run"));
		Anim->Clips.Attack = Clip(TEXT("Attack"));
		Anim->Clips.Death = Clip(TEXT("Death"));
		Anim->Clips.WalkSpeed = WalkSpeed;
		Anim->Clips.RunSpeed = RunSpeed;
		for (const FName& Name : ActionClips)
		{
			if (UAnimSequenceBase* A = Clip(*Name.ToString()))
			{
				Actions.Add(Name, A);
			}
		}
	}
}

void ASOEnemy::PlayAction(FName Clip, float Rate)
{
	if (HasAuthority())
	{
		MulticastAction(Clip, Rate);
	}
}

void ASOEnemy::MulticastAction_Implementation(FName Clip, float Rate)
{
	USOLocomotionAnimInstance* Anim = Cast<USOLocomotionAnimInstance>(GetMesh()->GetAnimInstance());
	if (const TObjectPtr<UAnimSequenceBase>* A = Actions.Find(Clip); A && Anim)
	{
		Anim->PlayAction(*A, Rate);
	}
}

float ASOEnemy::GetActionLength(FName Clip) const
{
	const TObjectPtr<UAnimSequenceBase>* A = Actions.Find(Clip);
	return A && *A ? (*A)->GetPlayLength() : 0.0f;
}

int32 ASOEnemy::DamageAround(const FVector& Center, float Radius, float Damage, float Knock)
{
	int32 Hits = 0;
	for (TActorIterator<ASOCombatCharacter> It(GetWorld()); It; ++It)
	{
		ASOCombatCharacter* Other = *It;
		if (Other == this || Other->IsDead() || !USOCombatStatics::AreHostile(this, Other))
		{
			continue;
		}
		const FVector D = Other->GetActorLocation() - Center;
		if (D.Size2D() > Radius || FMath::Abs(D.Z) > 350.0f)
		{
			continue;
		}
		const float Falloff = 1.0f - 0.5f * D.Size2D() / FMath::Max(Radius, 1.0f);
		if (USOCombatStatics::ApplyDamage(this, Other, Damage * DamageScale * Falloff, false) > 0.0f)
		{
			++Hits;
		}
		if (Knock > 0.0f)
		{
			Other->LaunchCharacter(D.GetSafeNormal2D() * Knock * Falloff + FVector(0, 0, Knock * 0.45f), true, true);
		}
	}
	return Hits;
}

void ASOEnemy::SetRunning(bool bRun)
{
	bRunning = bRun;
	// (checked by a hit for a moment; slower for good once it is badly hurt)
	const float Hurt = (IsChecked() ? HitSlow : 1.0f) * (GetHealth() < GetMaxHealth() * WoundedAt ? WoundedSpeed : 1.0f);
	GetCharacterMovement()->MaxWalkSpeed = (bRun ? RunSpeed : WalkSpeed) * GetMoveScale() * (Boss ? Boss->GetSpeedScale() : 1.0f) * Hurt;
}

bool ASOEnemy::IsUsingAbility() const
{
	if (const USOAbilitySet* Kit = GetAbilitySet())
	{
		for (const FSOAbilityGrant& Grant : Kit->Abilities)
		{
			if (IsAbilityActive(Grant.Slot))
			{
				return true;
			}
		}
	}
	return false;
}

FVector ASOEnemy::GetCastOrigin() const
{
	return GetActorLocation() + GetActorForwardVector() * 70.0f + FVector(0.0f, 0.0f, 55.0f); // the hands
}

float ASOEnemy::PrecisionAt(const FHitResult& Hit) const
{
	const int32 Weak = Boss ? Boss->WeakPointAt(Hit) : INDEX_NONE;
	return Weak != INDEX_NONE ? Boss->GetData()->WeakPoints[Weak].Scale : Super::PrecisionAt(Hit);
}

void ASOEnemy::MakeBoss()
{
	if (Boss || BossId.IsNone())
	{
		return;
	}
	USOBossData* Table = USOBossData::Load(BossId);
	if (!Table)
	{
		UE_LOG(LogTemp, Warning, TEXT("%s names the boss table '%s', which was never imported (SO_IMPORT_ONLY=bosses)"), *GetName(), *BossId.ToString());
		return;
	}
	Boss = NewObject<USOBossComponent>(this, TEXT("Boss"));
	Boss->RegisterComponent();
	Boss->Setup(Table);
}

void ASOEnemy::OnRep_BossId()
{
	if (HasActorBegunPlay())
	{
		MakeBoss();
	}
}

namespace
{
	/** The clip a grant names, at the speed that puts the blow in it on the end of the wind-up. */
	float ClipRate(const FSOAbilityGrant& Grant)
	{
		return Grant.ClipLead > 0.0f && Grant.WindUp > 0.0f ? FMath::Clamp(Grant.ClipLead / Grant.WindUp, 0.25f, 3.0f) : 1.0f;
	}
}

void ASOEnemy::OnAbilityWindUp(ESOAbilitySlot Slot)
{
	Super::OnAbilityWindUp(Slot);
	const FSOAbilityGrant* Grant = GetAbilitySet() ? GetAbilitySet()->Find(Slot) : nullptr;
	if (HasAuthority() && Grant && Actions.Contains(Grant->Clip))
	{
		PlayAction(Grant->Clip, ClipRate(*Grant)); // the body going into it is the first warning
	}
}

void ASOEnemy::OnAbilityUsed(ESOAbilitySlot Slot)
{
	Super::OnAbilityUsed(Slot);
	const FSOAbilityGrant* Grant = GetAbilitySet() ? GetAbilitySet()->Find(Slot) : nullptr;
	if (HasAuthority() && Grant && Grant->WindUp <= 0.0f && Actions.Contains(Grant->Clip))
	{
		PlayAction(Grant->Clip, 1.0f);
	}
}

bool ASOEnemy::ThinkCombat(ASOEnemyAIController* AI, ASOCombatCharacter* Target)
{
	return UseKit(AI, Target);
}

bool ASOEnemy::UseKit(ASOEnemyAIController* AI, ASOCombatCharacter* Target, bool bAnyOrder)
{
	const USOAbilitySet* Kit = GetAbilitySet();
	if (!Kit || !Target || IsDead())
	{
		return false;
	}
	if (IsUsingAbility())
	{
		// winding up, or in the middle of it: it stands, holds its fire and turns with whoever it is for
		if (AI)
		{
			AI->StopMovement();
		}
		SetWantsFire(false);
		if (const AActor* For = GetAbilityTarget())
		{
			const FVector To = For->GetActorLocation() - GetActorLocation();
			SetActorRotation(FMath::RInterpTo(GetActorRotation(), FRotator(0.0f, To.Rotation().Yaw, 0.0f), 0.1f, 10.0f));
		}
		return true;
	}
	if (IsAttacking())
	{
		return false;
	}
	// those it would use now: the first in the kit's order, or (a boss mixing its moves) any of them
	const bool bSees = HasLineOfFire(Target);
	TArray<const FSOAbilityGrant*, TInlineAllocator<5>> Ready;
	for (const FSOAbilityGrant& Grant : Kit->Abilities)
	{
		const USOGameplayAbility* Ability = Grant.Ability ? Grant.Ability.GetDefaultObject() : nullptr;
		int32 Charges = 0, MaxCharges = 0;
		float Left = 0.0f, Cooldown = 0.0f;
		if (Ability && GetAbilityState(Grant.Slot, Charges, MaxCharges, Left, Cooldown) && Charges > 0
			&& Ability->WantsUse(this, Target, Grant, bSees))
		{
			Ready.Add(&Grant);
		}
	}
	if (bAnyOrder)
	{
		for (int32 i = Ready.Num() - 1; i > 0; --i)
		{
			Ready.Swap(i, FMath::RandRange(0, i));
		}
	}
	for (const FSOAbilityGrant* Grant : Ready)
	{
		SetAbilityTarget(Target);
		if (ActivateSlot(Grant->Slot))
		{
			return Grant->WindUp > 0.0f || IsAbilityActive(Grant->Slot); // an instant one does not hold it up
		}
	}
	return false;
}

float ASOEnemy::GetAbilityCooldownScale(ESOAbilitySlot Slot) const
{
	return USODifficultySubsystem::Get(this).AbilityCooldown * (Boss ? Boss->GetCooldownScale() : 1.0f);
}

void ASOEnemy::OnMoveScaleChanged()
{
	SetRunning(bRunning); // a slow came or went
}

float ASOEnemy::DistanceTo(const AActor* Other) const
{
	if (!Other)
	{
		return BIG_NUMBER;
	}
	float OtherRadius = 0.0f;
	if (const ACharacter* Char = Cast<ACharacter>(Other))
	{
		OtherRadius = Char->GetCapsuleComponent()->GetScaledCapsuleRadius();
	}
	const float Center = FVector::Dist2D(GetActorLocation(), Other->GetActorLocation());
	return FMath::Max(0.0f, Center - GetCapsuleComponent()->GetScaledCapsuleRadius() - OtherRadius);
}

bool ASOEnemy::TryAttack(AActor* Target)
{
	UWorld* World = GetWorld();
	if (!HasAuthority() || bDead || !Target || !World || IsAttacking())
	{
		return false;
	}
	const float Now = World->GetTimeSeconds();
	if (Now - LastAttackTime < MeleeCooldown || DistanceTo(Target) > MeleeRange)
	{
		return false;
	}
	LastAttackTime = Now;
	PendingStrikeTime = Now + MeleeWindup;
	AttackTarget = Target;

	// Face and lunge.
	const FVector To = (Target->GetActorLocation() - GetActorLocation()).GetSafeNormal2D();
	SetActorRotation(To.Rotation());
	LaunchCharacter(To * LungeSpeed, true, false);
	MulticastAttack();
	return true;
}

void ASOEnemy::MulticastAttack_Implementation()
{
	USOCue::Sound(this, FName(SoundPrefix + TEXT("_attack")), GetActorLocation() + FVector(0, 0, 60.0f), 1.0f, 0.08f, ESOSoundRange::Mid);
	if (USOLocomotionAnimInstance* Anim = Cast<USOLocomotionAnimInstance>(GetMesh()->GetAnimInstance()))
	{
		const float Length = Anim->GetAttackLength();
		Anim->PlayAttack(Length > 0.0f ? Length / FMath::Max(MeleeCooldown, 0.3f) : 1.0f);
	}
}

void ASOEnemy::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	UpdateGunHold(DeltaSeconds);
	TickTrigger(DeltaSeconds);
	if (HasAuthority() && !IsDead() && !VoicePrefix.IsEmpty() && GetWorld()->GetTimeSeconds() >= NextIdleVoice)
	{
		// it mutters to itself: the player hears where it is before seeing it
		NextIdleVoice = GetWorld()->GetTimeSeconds() + (bAlert ? FMath::FRandRange(5.0f, 10.0f) : FMath::FRandRange(4.0f, 9.0f));
		Voice(bAlert ? FName(TEXT("alert")) : FName(TEXT("idle")), bAlert ? 0.9f : 0.75f);
	}
	if (UWorld* W = GetWorld(); W && !bDead)
	{
		const float Health = GetHealth();
		if (LastHealthSeen >= 0.0f && Health < LastHealthSeen - 0.5f && W->GetTimeSeconds() - LastHurtSound > 0.35f)
		{
			LastHurtSound = W->GetTimeSeconds();
			if (VoicePrefix.IsEmpty()) { USOCue::Sound(this, FName(SoundPrefix + TEXT("_hurt")), GetActorLocation() + FVector(0, 0, 60.0f), 0.9f, 0.1f, ESOSoundRange::Mid); } else { Voice(TEXT("hurt"), 0.9f); }
		}
		LastHealthSeen = Health;
		// reeling (staggered): the body shows it on every machine
		const bool bStaggered = HasStatus(SOTags::Status_Stagger);
		if (USOLocomotionAnimInstance* Anim = Cast<USOLocomotionAnimInstance>(GetMesh()->GetAnimInstance()))
		{
			Anim->bReeling = bStaggered;
		}
		if (HasAuthority())
		{
			// it steadies again; a check that has run out gives it its speed back; a blow is not struck while it reels
			PoiseDamage = FMath::Max(0.0f, PoiseDamage - PoiseRecover * DeltaSeconds);
			if (bHitSlowed && !IsChecked())
			{
				bHitSlowed = false;
				SetRunning(bRunning);
			}
			if (bStaggered)
			{
				PendingStrikeTime = -1.0f;
			}
		}
	}
	UWorld* World = GetWorld();
	if (!HasAuthority() || !World || PendingStrikeTime < 0.0f || World->GetTimeSeconds() < PendingStrikeTime)
	{
		return;
	}
	PendingStrikeTime = -1.0f;
	AActor* Target = AttackTarget.Get();
	if (bDead || !Target)
	{
		return;
	}
	// The strike lands if the target is still within reach (a little extra for the lunge) and in front.
	const FVector To = (Target->GetActorLocation() - GetActorLocation()).GetSafeNormal2D();
	const bool bInFront = FVector::DotProduct(GetActorForwardVector().GetSafeNormal2D(), To) > 0.3f;
	if (bInFront && DistanceTo(Target) <= MeleeRange + 40.0f)
	{
		if (USOCombatStatics::ApplyDamage(this, Target, MeleeDamage, false) > 0.0f)
		{
			++StrikesLanded;
		}
	}
}

void ASOEnemy::HandleDeath()
{
	Super::HandleDeath();
	if (Boss && HasAuthority())
	{
		Boss->OwnerDied();
	}
	// One that rallied the others is what held them together: with it down, those round it lose a moment
	// (kill the leader first).
	if (HasAuthority() && GetAbilitySet())
	{
		for (const FSOAbilityGrant& Grant : GetAbilitySet()->Abilities)
		{
			if (Grant.Ability && Grant.Ability->IsChildOf(USOAbility_Rally::StaticClass()))
			{
				for (TActorIterator<ASOEnemy> It(GetWorld()); It; ++It)
				{
					if (*It != this && !It->IsDead() && It->Faction == Faction && FVector::Dist(It->GetActorLocation(), GetActorLocation()) < Grant.Radius)
					{
						USOCombatStatics::ApplyStatus(nullptr, *It, SOTags::Status_Stagger, 1.5f);
					}
				}
				break;
			}
		}
	}
	if (VoicePrefix.IsEmpty())
	{
		USOCue::Sound(this, FName(SoundPrefix + TEXT("_death")), GetActorLocation() + FVector(0, 0, 60.0f), 1.0f, 0.06f, ESOSoundRange::Mid);
	}
	else
	{
		Voice(TEXT("death"), 1.0f);
	}
	PendingStrikeTime = -1.0f;
	GetCapsuleComponent()->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
	if (AController* AI = GetController())
	{
		AI->StopMovement();
	}
}

// ------------------------------------------------------------------ arms

void ASOEnemy::BeginPlay()
{
	Super::BeginPlay();
	if (GetNetMode() == NM_ListenServer || GetNetMode() == NM_DedicatedServer)
	{
		// A server's rounds land on the bodies as the server has them: a creature the host is not looking at must
		// still be where a joined player sees it (its bones move, every few frames while it is not drawn here).
		GetMesh()->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
	}
	if (HasAuthority() && !WeaponArchetype.IsNone())
	{
		if (const USOLootTables* Tables = USOLootLibrary::GetTables())
		{
			if (ASOWeapon* W = EquipWeapon(Tables->LoadArchetype(WeaponArchetype)))
			{
				W->SetAmmo(W->GetMag() > 0 ? W->GetMag() : 30, 9999);
			}
		}
	}
	if (HasAuthority() && !KitId.IsNone())
	{
		GrantAbilitySet(USOAbilitySet::Load(KitId));
	}
	MakeBoss(); // (every machine, if it names a table: after its own kit, so a phase can put another in its place)
	NextIdleVoice = GetWorld()->GetTimeSeconds() + FMath::FRandRange(1.0f, 8.0f);
}

USceneComponent* ASOEnemy::GetThirdPersonWeaponParent() const
{
	return GunHold;
}

void ASOEnemy::SetAimTarget(AActor* InTarget)
{
	if (AimTarget.Get() == InTarget)
	{
		return;
	}
	AimTarget = InTarget;
	AimSince = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.0f;
	// facing: toward the target while it aims (strafing between covers), along its path otherwise
	UCharacterMovementComponent* Move = GetCharacterMovement();
	Move->bOrientRotationToMovement = InTarget == nullptr;
	Move->bUseControllerDesiredRotation = InTarget != nullptr;
	if (!InTarget)
	{
		bWantsFire = false;
	}
}

FVector ASOEnemy::GetAimOrigin() const
{
	return GetPawnViewLocation();
}

void ASOEnemy::SuppressAt(const FVector& Point, float Until)
{
	SuppressPoint = Point;
	SuppressUntil = Until;
}

bool ASOEnemy::IsSuppressing() const
{
	return GetWorld() && GetWorld()->GetTimeSeconds() < SuppressUntil;
}

bool ASOEnemy::IsChecked() const
{
	const UWorld* World = GetWorld();
	return World && World->GetTimeSeconds() < HitSlowUntil;
}

void ASOEnemy::OnTookDamage(AActor* Source, float Amount, bool bCrit)
{
	Super::OnTookDamage(Source, Amount, bCrit);
	HitReact(Source, Amount, bCrit);
}

void ASOEnemy::HitReact(AActor* Source, float Amount, bool bPrecision)
{
	UWorld* World = GetWorld();
	if (!HasAuthority() || !World || IsDead() || !Source || Amount <= 0.0f)
	{
		return;
	}
	const float T = World->GetTimeSeconds();
	const FSOHitInfo& Hit = USOCombatStatics::LastHit();
	ON_SCOPE_EXIT { AbsorbedByArmour = 0.0f; };
	const ESOHitRegion Region = Hit.bKnown ? Hit.Region() : ESOHitRegion::Torso;
	const bool bLeg = Region == ESOHitRegion::LegLeft || Region == ESOHitRegion::LegRight;
	const float Share = Amount / FMath::Max(GetMaxHealth(), 1.0f);
	// where it came from: against the way the blow was travelling if that is known, else from whoever dealt it
	FVector Toward = Hit.bKnown && !Hit.Direction.IsNearlyZero() ? -Hit.Direction : Source->GetActorLocation() - GetActorLocation();
	Toward = Toward.GetSafeNormal2D();
	if (Toward.IsNearlyZero())
	{
		Toward = GetActorForwardVector();
	}
	// (anything that fights by a boss table reels by that table, never from fire: a variant made a boss too)
	const bool bSteady = Boss != nullptr || ResistsStatus(SOTags::Status_Stagger) || HasStatus(SOTags::Status_Guard);
	bool bStumbled = false;
	if (!bSteady)
	{
		// checked: for a moment it does not move as it did
		if (HitSlow < 1.0f && Share > 0.01f)
		{
			HitSlowUntil = FMath::Max(HitSlowUntil, T + HitSlowTime * (bLeg ? 1.6f : 1.0f));
			bHitSlowed = true;
			SetRunning(bRunning);
		}
		// unsteadied; and past what it can take, it stumbles
		const float Turned = AbsorbedByArmour * ArmourPoise / FMath::Max(GetMaxHealth(), 1.0f); // (what a plate took still shakes it)
		PoiseDamage += (Share + Turned) * (bPrecision ? PrecisionPoise : 1.0f) * (bLeg ? 1.25f : 1.0f);
		if (T < NextStumble)
		{
			PoiseDamage = FMath::Min(PoiseDamage, Poise * 0.5f); // (no stumble the instant its rest is over)
		}
		if (Poise > 0.0f && PoiseDamage >= Poise && T >= NextStumble && USOCombatStatics::ApplyStatus(Source, this, SOTags::Status_Stagger, StumbleTime))
		{
			bStumbled = true;
			++Stumbles;
			PoiseDamage = 0.0f;
			NextStumble = T + StumbleTime + StumbleRest;
			PendingStrikeTime = -1.0f;                            // the blow it was winding up is lost
			bWantsFire = false;
			// knocked off its feet for a moment: a stagger back of a metre or so (a heavy body half that)
			GetCharacterMovement()->StopMovementImmediately();
			const float Weight = FMath::Clamp(FlinchScale, 0.35f, 1.0f);
			LaunchCharacter(-Toward * 470.0f * Weight + FVector(0.0f, 0.0f, 150.0f * Weight), true, true);
			if (VoicePrefix.IsEmpty())
			{
				USOCue::Sound(this, FName(SoundPrefix + TEXT("_hurt")), GetActorLocation() + FVector(0, 0, 60.0f), 1.0f, 0.1f, ESOSoundRange::Mid);
			}
			else
			{
				Voice(TEXT("hurt"), 1.0f);
			}
			LastHurtSound = T;
		}
	}
	// shown, where it landed. A stumble always; a precise or heavy hit almost always; a light one not more than
	// some eight times a second, so a burst reads as blows and not as a shake.
	if (FlinchScale <= 0.0f || (!bStumbled && T - LastFlinch < (bPrecision || Share > 0.1f ? 0.07f : 0.12f)))
	{
		return;
	}
	LastFlinch = T;
	const float Strength = bStumbled ? 1.7f : FMath::Clamp(Share / 0.1f, 0.6f, 1.0f) * (bPrecision ? 1.35f : 1.0f);
	MulticastFlinch(Toward, Strength * FlinchScale, Region);
}

void ASOEnemy::Juke(const FVector& Direction)
{
	if (HasAuthority() && !IsDead() && !IsAttacking() && GetCharacterMovement()->IsMovingOnGround())
	{
		LaunchCharacter(Direction.GetSafeNormal2D() * 620.0f + FVector(0.0f, 0.0f, 150.0f), true, true);
	}
}

void ASOEnemy::MulticastFlinch_Implementation(FVector_NetQuantizeNormal Toward, float Strength, ESOHitRegion Region)
{
	if (USOLocomotionAnimInstance* Anim = Cast<USOLocomotionAnimInstance>(GetMesh()->GetAnimInstance()))
	{
		// knocked away from where it came from, where it was hit
		Anim->HitKick(Region, GetActorTransform().InverseTransformVectorNoScale(FVector(Toward)), Strength);
	}
}

FVector ASOEnemy::GetAimDirection() const
{
	if (IsSuppressing())
	{
		// at the place, not at anyone: a loose cone over it
		return (SuppressPoint + FMath::VRand() * FMath::FRandRange(20.0f, 150.0f) - GetAimOrigin()).GetSafeNormal();
	}
	const AActor* T = AimTarget.Get();
	if (!T)
	{
		return Super::GetAimDirection();
	}
	// at the chest, off by an error that grows with range and a moving target and shrinks while it tracks
	const FVector Origin = GetAimOrigin();
	FVector Chest = T->GetActorLocation() + FVector(0, 0, 25.0f);
	const float Dist = FVector::Dist(Origin, Chest);
	// (the difficulty level: how fast the aim settles, how wide it is)
	const FSODifficulty& Level = USODifficultySubsystem::Get(this);
	const float Tracked = FMath::Clamp((GetWorld()->GetTimeSeconds() - AimSince) / FMath::Max(2.5f * Level.Reaction, 0.1f), 0.0f, 1.0f);
	// What it fires takes time to arrive (a bolt of plasma far more than a bullet): it aims where the target will be,
	// better the longer it has tracked it, never perfectly (ShotLead: the share of the true lead it gives).
	const ASOWeapon* Gun = GetWeapon();
	const float ShotSpeed = Gun && Gun->GetData() ? Gun->GetData()->MuzzleVelocity * 100.0f : 0.0f;
	if (ShotSpeed > 1.0f)
	{
		Chest += T->GetVelocity() * (Dist / ShotSpeed) * ShotLead * Tracked;
	}
	const float Err = AimError * Level.AimError * (Dist / 1000.0f) * (1.0f + T->GetVelocity().Size2D() / 450.0f) * FMath::Lerp(1.7f, 0.65f, Tracked)
		* (HasStatus(SOTags::Status_Suppressed) ? 1.6f : 1.0f); // (under fire itself, it shoots wider)
	const FVector Off = FMath::VRand() * Err * FMath::Sqrt(FMath::FRand());
	return (Chest + Off - Origin).GetSafeNormal();
}

bool ASOEnemy::HasLineOfFire(const AActor* Other) const
{
	if (!Other)
	{
		return false;
	}
	FCollisionQueryParams Params(SCENE_QUERY_STAT(SOLineOfFire), false, this);
	Params.AddIgnoredActor(Other);
	if (const AActor* W = GetWeapon())
	{
		Params.AddIgnoredActor(W);
	}
	const FVector From = GetAimOrigin(), To = Other->GetActorLocation() + FVector(0, 0, 25.0f);
	return !GetWorld()->SweepTestByChannel(From, To, FQuat::Identity, SO_TRACE_BULLET, FCollisionShape::MakeSphere(6.0f), Params)
		&& !GetWorld()->LineTraceTestByChannel(From, To, ECC_Visibility, Params);
}

bool ASOEnemy::FitsAt(const FVector& Location) const
{
	const UCapsuleComponent* Capsule = GetCapsuleComponent();
	FCollisionQueryParams Params(SCENE_QUERY_STAT(SOFits), false, this);
	return !GetWorld()->OverlapBlockingTestByChannel(Location, FQuat::Identity, ECC_Pawn,
		FCollisionShape::MakeCapsule(Capsule->GetScaledCapsuleRadius() + 3.0f, FMath::Max(Capsule->GetScaledCapsuleHalfHeight() - 3.0f, Capsule->GetScaledCapsuleRadius() + 3.0f)), Params);
}

float ASOEnemy::ScaleIncomingDamage(float Amount, const AActor* Source, bool bCrit) const
{
	// a boss's phase (armour) and its reeling, then the ambush
	const float Taken = Boss ? Boss->ScaleDamage(Amount) : Amount;
	return bAlert ? Taken : Taken * AmbushDamageScale;
}

void ASOEnemy::Voice(FName Kind, float Volume)
{
	if (VoicePrefix.IsEmpty())
	{
		return;
	}
	const int32 N = VoiceTakes().FindRef(Kind);
	const FString Name = N > 1 ? FString::Printf(TEXT("%s_%s_%d"), *VoicePrefix, *Kind.ToString(), FMath::RandRange(1, N))
		: FString::Printf(TEXT("%s_%s"), *VoicePrefix, *Kind.ToString());
	USOCue::Sound(this, FName(Name), GetActorLocation() + FVector(0, 0, 60.0f), Volume, 0.08f, ESOSoundRange::Mid);
}

void ASOEnemy::UpdateGunHold(float DeltaSeconds)
{
	const ASOWeapon* W = GetWeapon();
	const USOGunRigComponent* Rig = W ? W->GetThirdPersonRig() : nullptr;
	if (!Rig)
	{
		return;
	}
	const AActor* T = AimTarget.Get();
	Raise = FMath::FInterpTo(Raise, T && !IsDead() ? 1.0f : 0.0f, DeltaSeconds, 5.0f);
	const FRotator Facing(0.0f, GetActorRotation().Yaw, 0.0f);
	FVector Shoulder = GetActorLocation() + Facing.RotateVector(FVector(8.0f, 20.0f, 48.0f));
	if (GetMesh()->GetBoneIndex(TEXT("upperarm_R")) != INDEX_NONE)
	{
		Shoulder = GetMesh()->GetBoneLocation(TEXT("upperarm_R"));
	}
	// aimed at the target's chest, or carried low across the body
	const FQuat Low = FRotator(-32.0f, Facing.Yaw - 25.0f, 0.0f).Quaternion();
	const FQuat Aimed = T ? (T->GetActorLocation() + FVector(0, 0, 25.0f) - Shoulder).Rotation().Quaternion() : Low;
	const FQuat Q = FQuat::Slerp(Low, Aimed, Raise);
	FTransform Hold;
	if (HoldsAtHip() && !Rig->IsHandgun() && Rig->IsBuilt())
	{
		// Carried at the hip: the hand on the rear grip sits beside the right hip, the barrel is laid on the target
		// from there (or hangs forward and down across the thigh when there is nothing to shoot at).
		FVector Hip = GetActorLocation() + Facing.RotateVector(FVector(16.0f, 32.0f, 14.0f));
		if (GetMesh()->GetBoneIndex(TEXT("thigh_R")) != INDEX_NONE)
		{
			Hip = GetMesh()->GetBoneLocation(TEXT("thigh_R")) + Facing.RotateVector(FVector(20.0f, 16.0f, 4.0f));
		}
		const FQuat Carried = FRotator(-16.0f, Facing.Yaw - 6.0f, 0.0f).Quaternion();
		const FQuat OnTarget = T ? (T->GetActorLocation() + FVector(0, 0, 25.0f) - Hip).Rotation().Quaternion() : Carried;
		const FQuat Lay = FQuat::Slerp(Carried, OnTarget, Raise);
		Hold = FTransform(Lay, Hip - Lay.RotateVector(Rig->GetRightGrip().Wrist));
		// The off hand has to reach its place on the gun too: if the fore grip is further from the left shoulder
		// than that arm is long, the whole gun comes in toward that shoulder until it is in reach.
		if (GetMesh()->GetBoneIndex(TEXT("upperarm_L")) != INDEX_NONE && GetMesh()->GetBoneIndex(TEXT("hand_L")) != INDEX_NONE)
		{
			const FVector Shoulder2 = GetMesh()->GetBoneLocation(TEXT("upperarm_L"));
			const FVector Elbow = GetMesh()->GetBoneLocation(TEXT("forearm_L"));
			const float ArmLength = static_cast<float>(FVector::Dist(Shoulder2, Elbow) + FVector::Dist(Elbow, GetMesh()->GetBoneLocation(TEXT("hand_L"))));
			const FVector Fore = Hold.TransformPosition(Rig->GetLeftGrip().Wrist);
			const float Away = static_cast<float>(FVector::Dist(Shoulder2, Fore));
			if (Away > ArmLength * 0.93f)
			{
				Hold.AddToTranslation((Shoulder2 - Fore).GetSafeNormal() * (Away - ArmLength * 0.93f));
			}
		}
	}
	else if (Rig->IsHandgun())
	{
		// both arms out in front of the chest
		Hold = FTransform(Q, Shoulder + Q.RotateVector(FVector(42.0f, -14.0f, -8.0f)));
	}
	else
	{
		const FBox B = Rig->IsBuilt() ? Rig->GetRigBounds() : FBox(FVector(-20.0f, -3.0f, -12.0f), FVector(40.0f, 3.0f, 10.0f));
		const FVector Butt(B.Min.X + 1.0f, 0.0f, FMath::Clamp(1.5f, B.Min.Z + 4.0f, B.Max.Z - 4.0f));
		const FVector Pocket = Shoulder + Q.RotateVector(FVector(4.0f, -5.0f, -5.0f));
		Hold = FTransform(Q, Pocket - Q.RotateVector(Butt));
	}
	GunHold->SetWorldTransform(Hold);
}

void ASOEnemy::TickTrigger(float DeltaSeconds)
{
	ASOWeapon* W = GetWeapon();
	UWorld* World = GetWorld();
	if (!W || !World || !HasAuthority())
	{
		return;
	}
	const float Now = World->GetTimeSeconds();
	auto Release = [&]()
	{
		if (bFiring)
		{
			W->StopFire();
			bFiring = false;
			NextBurst = Now + FMath::FRandRange(BurstPause.X, BurstPause.Y) * USODifficultySubsystem::Get(this).BurstPause;
		}
	};
	if (IsDead())
	{
		Release();
		return;
	}
	if (W->GetReserve() < 200)
	{
		W->SetAmmo(W->GetMag(), 9999);
	}
	if (LastMag >= 0 && W->GetMag() < LastMag)
	{
		ShotsFired += LastMag - W->GetMag();
	}
	LastMag = W->GetMag();
	if (W->GetMag() <= 0)
	{
		Release();
		if (!W->IsReloading())
		{
			W->StartReload();
		}
		return;
	}
	const AActor* T = AimTarget.Get();
	const bool bAtPlace = IsSuppressing();
	bool bCan = bWantsFire && (T || bAtPlace) && Raise > 0.8f && !IsAttacking() && !W->IsReloading();
	if (bCan && bAtPlace)
	{
		// at a place: it must be facing it, with nothing of its own side on the line and no wall right in front
		const FVector Eye = GetAimOrigin();
		const FVector To = (SuppressPoint - GetActorLocation()).GetSafeNormal2D();
		FHitResult Hit;
		FCollisionQueryParams Params(SCENE_QUERY_STAT(SOSuppress), false, this);
		const bool bMet = World->LineTraceSingleByChannel(Hit, Eye, SuppressPoint, SO_TRACE_BULLET, Params);
		const ASOCombatCharacter* Met = bMet ? Cast<ASOCombatCharacter>(Hit.GetActor()) : nullptr;
		bCan = FVector::DotProduct(GetActorForwardVector().GetSafeNormal2D(), To) > 0.85f && !(Met && Met->Faction == Faction)
			&& !(bMet && Hit.Distance < 250.0f);
	}
	else if (bCan)
	{
		const FVector To = (T->GetActorLocation() - GetActorLocation()).GetSafeNormal2D();
		bCan = FVector::DotProduct(GetActorForwardVector().GetSafeNormal2D(), To) > 0.9f && HasLineOfFire(T);
	}
	if (bFiring)
	{
		if (!bCan || Now >= TriggerUntil)
		{
			Release();
		}
		else
		{
			W->StartFire(); // semi-automatic guns fire again as soon as they can
		}
	}
	else if (bCan && Now >= NextBurst)
	{
		W->StartFire();
		bFiring = true;
		TriggerUntil = Now + FMath::FRandRange(BurstTime.X, BurstTime.Y) * USODifficultySubsystem::Get(this).Burst;
	}
}
