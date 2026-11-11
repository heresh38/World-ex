#include "SOEnemy.h"

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
	DisplayName = NSLOCTEXT("SO", "Stalker", "Stalker");
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
	Body->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::OnlyTickPoseWhenRendered;

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
	GetCharacterMovement()->MaxWalkSpeed = bRun ? RunSpeed : WalkSpeed;
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
	USOSoundLibrary::PlayAt(this, FName(SoundPrefix + TEXT("_attack")), GetActorLocation() + FVector(0, 0, 60.0f), 1.0f, 0.08f, ESOSoundRange::Mid);
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
			if (VoicePrefix.IsEmpty()) { USOSoundLibrary::PlayAt(this, FName(SoundPrefix + TEXT("_hurt")), GetActorLocation() + FVector(0, 0, 60.0f), 0.9f, 0.1f, ESOSoundRange::Mid); } else { Voice(TEXT("hurt"), 0.9f); }
		}
		LastHealthSeen = Health;
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
	if (VoicePrefix.IsEmpty())
	{
		USOSoundLibrary::PlayAt(this, FName(SoundPrefix + TEXT("_death")), GetActorLocation() + FVector(0, 0, 60.0f), 1.0f, 0.06f, ESOSoundRange::Mid);
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

FVector ASOEnemy::GetAimDirection() const
{
	const AActor* T = AimTarget.Get();
	if (!T)
	{
		return Super::GetAimDirection();
	}
	// at the chest, off by an error that grows with range and a moving target and shrinks while it tracks
	const FVector Origin = GetAimOrigin();
	const FVector Chest = T->GetActorLocation() + FVector(0, 0, 25.0f);
	const float Dist = FVector::Dist(Origin, Chest);
	const float Tracked = FMath::Clamp((GetWorld()->GetTimeSeconds() - AimSince) / 2.5f, 0.0f, 1.0f);
	const float Err = AimError * (Dist / 1000.0f) * (1.0f + T->GetVelocity().Size2D() / 450.0f) * FMath::Lerp(1.7f, 0.65f, Tracked);
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
	return bAlert ? Amount : Amount * AmbushDamageScale;
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
	USOSoundLibrary::PlayAt(this, FName(Name), GetActorLocation() + FVector(0, 0, 60.0f), Volume, 0.08f, ESOSoundRange::Mid);
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
	if (Rig->IsHandgun())
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
			NextBurst = Now + FMath::FRandRange(BurstPause.X, BurstPause.Y);
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
	bool bCan = bWantsFire && T && Raise > 0.8f && !IsAttacking() && !W->IsReloading();
	if (bCan)
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
		TriggerUntil = Now + FMath::FRandRange(BurstTime.X, BurstTime.Y);
	}
}
