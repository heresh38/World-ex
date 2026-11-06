#include "SOEnemy.h"

#include "Animation/AnimSequenceBase.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "SOCombatStatics.h"
#include "SOEnemyAIController.h"
#include "SOLocomotionAnimInstance.h"
#include "SOSound.h"

ASOEnemy::ASOEnemy(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	PrimaryActorTick.bCanEverTick = true;
	Faction = ESOFaction::Alien;
	StartMaxHealth = 140.0f;
	StartMaxShield = 0.0f;
	CorpseLifeSpan = 6.0f;
	BloodColor = FLinearColor::FromSRGBColor(FColor(0x5a, 0x2a, 0x8a)); // enemies.js stalker blood

	GetCapsuleComponent()->InitCapsuleSize(38.0f, 92.0f);
	USkeletalMeshComponent* Body = GetMesh();
	Body->SetRelativeLocation(FVector(0.0f, 0.0f, -92.0f));
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
	Move->bUseRVOAvoidance = false;

	AIControllerClass = ASOEnemyAIController::StaticClass();
	AutoPossessAI = EAutoPossessAI::PlacedInWorldOrSpawned;

	BodyMesh = TSoftObjectPtr<USkeletalMesh>(FSoftObjectPath(TEXT("/Game/Characters/Stalker/SK_Stalker.SK_Stalker")));
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
		auto Clip = [this](const TCHAR* Name) -> UAnimSequenceBase*
		{
			const FString Asset = FPaths::GetBaseFilename(ClipPathPrefix) + Name;
			return TSoftObjectPtr<UAnimSequenceBase>(FSoftObjectPath(ClipPathPrefix + Name + TEXT(".") + Asset)).LoadSynchronous();
		};
		Anim->Clips.Idle = Clip(TEXT("Idle"));
		Anim->Clips.Walk = Clip(TEXT("Walk"));
		Anim->Clips.Run = Clip(TEXT("Run"));
		Anim->Clips.Attack = Clip(TEXT("Attack"));
		Anim->Clips.Death = Clip(TEXT("Death"));
		Anim->Clips.WalkSpeed = WalkSpeed;
		Anim->Clips.RunSpeed = RunSpeed;
	}
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
	USOSoundLibrary::PlayAt(this, TEXT("stalker_attack"), GetActorLocation() + FVector(0, 0, 60.0f), 1.0f, 0.08f, ESOSoundRange::Mid);
	if (USOLocomotionAnimInstance* Anim = Cast<USOLocomotionAnimInstance>(GetMesh()->GetAnimInstance()))
	{
		const float Length = Anim->GetAttackLength();
		Anim->PlayAttack(Length > 0.0f ? Length / FMath::Max(MeleeCooldown, 0.3f) : 1.0f);
	}
}

void ASOEnemy::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (UWorld* W = GetWorld(); W && !bDead)
	{
		const float Health = GetHealth();
		if (LastHealthSeen >= 0.0f && Health < LastHealthSeen - 0.5f && W->GetTimeSeconds() - LastHurtSound > 0.35f)
		{
			LastHurtSound = W->GetTimeSeconds();
			USOSoundLibrary::PlayAt(this, TEXT("stalker_hurt"), GetActorLocation() + FVector(0, 0, 60.0f), 0.9f, 0.1f, ESOSoundRange::Mid);
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
	USOSoundLibrary::PlayAt(this, TEXT("stalker_death"), GetActorLocation() + FVector(0, 0, 60.0f), 1.0f, 0.06f, ESOSoundRange::Mid);
	PendingStrikeTime = -1.0f;
	GetCapsuleComponent()->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
	if (AController* AI = GetController())
	{
		AI->StopMovement();
	}
}
