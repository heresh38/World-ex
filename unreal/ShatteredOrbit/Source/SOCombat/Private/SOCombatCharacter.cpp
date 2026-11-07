#include "SOCombatCharacter.h"
#include "SOAttributeSet.h"

#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/World.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Net/UnrealNetwork.h"
#include "SOAbilitySystemComponent.h"
#include "SOAttributeSet.h"
#include "SOCombatStatics.h"
#include "SOWeapon.h"
#include "SOWeaponData.h"

ASOCombatCharacter::ASOCombatCharacter(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	AbilitySystem = CreateDefaultSubobject<USOAbilitySystemComponent>(TEXT("AbilitySystem"));
	Attributes = CreateDefaultSubobject<USOAttributeSet>(TEXT("Attributes"));
	SetNetUpdateFrequency(60.0f);
	PrimaryActorTick.bCanEverTick = true;
}

void ASOCombatCharacter::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (HasAuthority() && AbilitySystem && !bDead)
	{
		AbilitySystem->UpdateShieldRegen(DeltaSeconds);
	}
}

UAbilitySystemComponent* ASOCombatCharacter::GetAbilitySystemComponent() const
{
	return AbilitySystem;
}

float ASOCombatCharacter::GetHealth() const { return Attributes ? Attributes->GetHealth() : 0.0f; }
float ASOCombatCharacter::GetMaxHealth() const { return Attributes ? Attributes->GetMaxHealth() : 0.0f; }
float ASOCombatCharacter::GetShield() const { return Attributes ? Attributes->GetShield() : 0.0f; }
float ASOCombatCharacter::GetMaxShield() const { return Attributes ? Attributes->GetMaxShield() : 0.0f; }

void ASOCombatCharacter::PostInitializeComponents()
{
	Super::PostInitializeComponents();
	if (Attributes)
	{
		Attributes->InitMaxHealth(StartMaxHealth);
		Attributes->InitHealth(StartMaxHealth);
		Attributes->InitMaxShield(StartMaxShield);
		Attributes->InitShield(StartMaxShield);
	}
	if (AbilitySystem)
	{
		AbilitySystem->InitAbilityActorInfo(this, this);
	}
}

void ASOCombatCharacter::BeginPlay()
{
	Super::BeginPlay();
	SetupBulletCollision();
}

void ASOCombatCharacter::PossessedBy(AController* NewController)
{
	Super::PossessedBy(NewController);
	if (AbilitySystem)
	{
		AbilitySystem->InitAbilityActorInfo(this, this);
	}
}

void ASOCombatCharacter::SetupBulletCollision()
{
	USkeletalMeshComponent* Body = GetMesh();
	const bool bMeshHits = Body && Body->GetSkeletalMeshAsset() && Body->GetPhysicsAsset();
	GetCapsuleComponent()->SetCollisionResponseToChannel(SO_TRACE_BULLET, bMeshHits ? ECR_Ignore : ECR_Block);
	if (Body)
	{
		Body->SetCollisionResponseToChannel(SO_TRACE_BULLET, bMeshHits ? ECR_Block : ECR_Ignore);
		if (bMeshHits)
		{
			Body->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
		}
	}
}

void ASOCombatCharacter::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
	Super::GetLifetimeReplicatedProps(OutLifetimeProps);
	DOREPLIFETIME(ASOCombatCharacter, bDead);
	DOREPLIFETIME(ASOCombatCharacter, Weapon);
}

void ASOCombatCharacter::Die(AActor* Killer)
{
	if (bDead || !HasAuthority())
	{
		return;
	}
	bDead = true;
	DeathTime = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.0f;
	if (AbilitySystem)
	{
		AbilitySystem->AddLooseGameplayTag(SOTags::State_Dead);
	}
	HandleDeath();
	USOCombatStatics::OnCharacterDied().Broadcast(this, Killer, GetWorld());
	if (CorpseLifeSpan > 0.0f)
	{
		SetLifeSpan(CorpseLifeSpan);
	}
}

void ASOCombatCharacter::OnRep_Dead()
{
	if (bDead)
	{
		DeathTime = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.0f;
		HandleDeath();
	}
}

void ASOCombatCharacter::HandleDeath()
{
	if (bDeathHandled)
	{
		return;
	}
	bDeathHandled = true;
	if (UCharacterMovementComponent* Move = GetCharacterMovement())
	{
		Move->StopMovementImmediately();
		Move->DisableMovement();
	}
	UCapsuleComponent* Capsule = GetCapsuleComponent();
	Capsule->SetCollisionResponseToChannel(ECC_Pawn, ECR_Ignore);
	Capsule->SetCollisionResponseToChannel(ECC_Camera, ECR_Ignore);
	Capsule->SetCollisionResponseToChannel(SO_TRACE_BULLET, ECR_Ignore);
	if (GetMesh())
	{
		GetMesh()->SetCollisionResponseToChannel(SO_TRACE_BULLET, ECR_Ignore);
	}
	if (Weapon)
	{
		Weapon->StopFire();
		Weapon->CancelReload();
		Weapon->DropOnDeath(GetVelocity());
	}
}

void ASOCombatCharacter::Destroyed()
{
	if (Weapon && HasAuthority())
	{
		Weapon->Destroy();
	}
	Super::Destroyed();
}

ASOWeapon* ASOCombatCharacter::EquipWeapon(USOWeaponData* Data)
{
	if (!Data)
	{
		return nullptr;
	}
	return SpawnWeapon([Data](ASOWeapon* W) { W->SetData(Data); });
}

ASOWeapon* ASOCombatCharacter::EquipInstance(const FSOWeaponInstance& Instance)
{
	if (!Instance.IsValid())
	{
		return nullptr;
	}
	return SpawnWeapon([&Instance](ASOWeapon* W) { W->SetInstance(Instance); });
}

ASOWeapon* ASOCombatCharacter::SpawnWeapon(TFunctionRef<void(ASOWeapon*)> Setup)
{
	if (!HasAuthority() || !GetWorld())
	{
		return nullptr;
	}
	if (Weapon)
	{
		Weapon->Destroy();
		Weapon = nullptr;
	}
	FActorSpawnParameters Params;
	Params.Owner = this;
	Params.Instigator = this;
	Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	Params.bDeferConstruction = true;
	ASOWeapon* NewWeapon = GetWorld()->SpawnActor<ASOWeapon>(ASOWeapon::StaticClass(), GetActorTransform(), Params);
	if (!NewWeapon)
	{
		return nullptr;
	}
	Setup(NewWeapon);
	if (!NewWeapon->GetData())
	{
		NewWeapon->Destroy();
		return nullptr;
	}
	NewWeapon->FinishSpawning(GetActorTransform());
	Weapon = NewWeapon;
	OnRep_Weapon();
	return Weapon;
}

void ASOCombatCharacter::OnRep_Weapon()
{
	if (Weapon)
	{
		Weapon->AttachToHolder(this);
	}
	OnWeaponEquipped();
}

FVector ASOCombatCharacter::GetAimOrigin() const
{
	return GetPawnViewLocation();
}

FVector ASOCombatCharacter::GetAimDirection() const
{
	return GetBaseAimRotation().Vector();
}

void ASOCombatCharacter::Heal(float Amount)
{
	if (HasAuthority() && AbilitySystem && !bDead && Amount > 0.0f)
	{
		AbilitySystem->SetNumericAttributeBase(USOAttributeSet::GetHealthAttribute(), FMath::Min(GetMaxHealth(), GetHealth() + Amount));
	}
}
