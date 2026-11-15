#include "SOCombatCharacter.h"
#include "SOAttributes.h"
#include "SOProjectileSubsystem.h"

#include "Abilities/SOGameplayAbility.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/World.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Net/UnrealNetwork.h"
#include "SOAbilitySystemComponent.h"
#include "SOAttributeSet.h"
#include "SOCombatStatics.h"
#include "SOGameplayEffects.h"
#include "SOSound.h"
#include "SOWeapon.h"
#include "SOWeaponData.h"

ASOCombatCharacter::ASOCombatCharacter(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	AbilitySystem = CreateDefaultSubobject<USOAbilitySystemComponent>(TEXT("AbilitySystem"));
	Attributes = CreateDefaultSubobject<USOAttributeSet>(TEXT("Attributes"));
	SetNetUpdateFrequency(60.0f);
	PrimaryActorTick.bCanEverTick = true;
	GetMesh()->bReceivesDecals = false; // what is drawn on the ground (a warning, a bullet hole) is not drawn on a body
}

void ASOCombatCharacter::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (HasAuthority() && AbilitySystem && !bDead)
	{
		AbilitySystem->UpdateShieldRegen(DeltaSeconds);
		if (AbilitySet && AbilitySet->UltimatePerSecond > 0.0f)
		{
			UltimateOwed += AbilitySet->UltimatePerSecond * GetAttributeScale(ESOAttribute::Focus) * DeltaSeconds;
			if (UltimateOwed >= 1.0f)
			{
				AddUltimate(UltimateOwed);
				UltimateOwed = 0.0f;
			}
		}
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
		AbilitySystem->GetGameplayAttributeValueChangeDelegate(USOAttributeSet::GetMoveScaleAttribute()).AddUObject(this, &ASOCombatCharacter::HandleMoveScaleChanged);
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
	DOREPLIFETIME(ASOCombatCharacter, AbilitySet);
}

void ASOCombatCharacter::Die(AActor* Killer)
{
	if (bDead || !HasAuthority())
	{
		return;
	}
	bDead = true;
	DeathTime = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.0f;
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
	if (AbilitySystem)
	{
		AbilitySystem->SetState(SOTags::State_Dead, true);
	}
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
		const FGameplayEffectSpecHandle Spec = AbilitySystem->MakeOutgoingSpec(USOGameplayEffect_Heal::StaticClass(), 1.0f, AbilitySystem->MakeEffectContext());
		if (Spec.IsValid())
		{
			Spec.Data->SetSetByCallerMagnitude(SOTags::SetByCaller_Magnitude, Amount);
			AbilitySystem->ApplyGameplayEffectSpecToSelf(*Spec.Data);
		}
	}
}

// --- Abilities and conditions --------------------------------------------------------------------

void ASOCombatCharacter::GrantAbilitySet(USOAbilitySet* Set)
{
	if (!HasAuthority() || !AbilitySystem)
	{
		return;
	}
	for (const FGameplayAbilitySpecHandle& Handle : GrantedAbilities)
	{
		AbilitySystem->ClearAbility(Handle);
	}
	GrantedAbilities.Reset();
	AbilitySet = Set;
	if (!Set)
	{
		return;
	}
	for (const FSOAbilityGrant& Grant : Set->Abilities)
	{
		if (Grant.Ability)
		{
			// the slot is the ability's input and the kit is where its numbers are read from
			GrantedAbilities.Add(AbilitySystem->GiveAbility(FGameplayAbilitySpec(Grant.Ability, 1, static_cast<int32>(Grant.Slot), Set)));
		}
	}
}

bool ASOCombatCharacter::ActivateSlot(ESOAbilitySlot Slot)
{
	if (!AbilitySystem || bDead)
	{
		return false;
	}
	FGameplayAbilitySpecHandle Handle;
	for (const FGameplayAbilitySpec& Spec : AbilitySystem->GetActivatableAbilities())
	{
		if (Spec.InputID == static_cast<int32>(Slot))
		{
			Handle = Spec.Handle;
			break;
		}
	}
	return Handle.IsValid() && AbilitySystem->TryActivateAbility(Handle);
}

bool ASOCombatCharacter::GetAbilityState(ESOAbilitySlot Slot, int32& OutCharges, int32& OutMaxCharges, float& OutRemaining, float& OutCooldown) const
{
	const FSOAbilityGrant* Grant = AbilitySet ? AbilitySet->Find(Slot) : nullptr;
	if (!Grant || !AbilitySystem)
	{
		return false;
	}
	const FGameplayTagContainer SlotTags(USOGameplayAbility::CooldownTag(Slot));
	const TArray<TPair<float, float>> Running = AbilitySystem->GetActiveEffectsTimeRemainingAndDuration(FGameplayEffectQuery::MakeQuery_MatchAnyOwningTags(SlotTags));
	OutMaxCharges = FMath::Max(1, Grant->Charges);
	OutCharges = FMath::Max(0, OutMaxCharges - Running.Num());
	OutCooldown = Grant->Cooldown;
	OutRemaining = 0.0f;
	for (int32 i = 0; i < Running.Num(); ++i)
	{
		OutRemaining = i == 0 ? Running[i].Key : FMath::Min(OutRemaining, Running[i].Key);
	}
	return true;
}

float ASOCombatCharacter::GetUltimate() const { return Attributes ? Attributes->GetUltimate() : 0.0f; }
float ASOCombatCharacter::GetMaxUltimate() const { return Attributes ? Attributes->GetMaxUltimate() : 0.0f; }

void ASOCombatCharacter::AddUltimate(float Amount)
{
	if (!HasAuthority() || !AbilitySystem || bDead || FMath::IsNearlyZero(Amount) || (Amount > 0.0f && GetUltimate() >= GetMaxUltimate()))
	{
		return;
	}
	const FGameplayEffectSpecHandle Spec = AbilitySystem->MakeOutgoingSpec(USOGameplayEffect_Ultimate::StaticClass(), 1.0f, AbilitySystem->MakeEffectContext());
	if (Spec.IsValid())
	{
		Spec.Data->SetSetByCallerMagnitude(SOTags::SetByCaller_Magnitude, Amount);
		AbilitySystem->ApplyGameplayEffectSpecToSelf(*Spec.Data);
	}
}

void ASOCombatCharacter::OnDealtDamage(float Amount, bool bKilled, const ASOCombatCharacter* Victim)
{
	if (!AbilitySet)
	{
		return;
	}
	AddUltimate((Amount * AbilitySet->UltimatePerDamage + (bKilled ? AbilitySet->UltimatePerKill : 0.0f)) * GetAttributeScale(ESOAttribute::Focus));
	// the kit's passive rule
	if (bKilled && Victim && AbilitySet->CloseKillShield > 0.0f && FVector::Dist(GetActorLocation(), Victim->GetActorLocation()) <= AbilitySet->CloseRange)
	{
		AddShield(AbilitySet->CloseKillShield);
	}
}

void ASOCombatCharacter::AddShield(float Amount)
{
	if (!HasAuthority() || !AbilitySystem || bDead || Amount <= 0.0f || GetShield() >= GetMaxShield())
	{
		return;
	}
	const FGameplayEffectSpecHandle Spec = AbilitySystem->MakeOutgoingSpec(USOGameplayEffect_Shield::StaticClass(), 1.0f, AbilitySystem->MakeEffectContext());
	if (Spec.IsValid())
	{
		Spec.Data->SetSetByCallerMagnitude(SOTags::SetByCaller_Magnitude, Amount);
		AbilitySystem->ApplyGameplayEffectSpecToSelf(*Spec.Data);
	}
}

bool ASOCombatCharacter::HasStatus(const FGameplayTag& Tag) const
{
	return AbilitySystem && AbilitySystem->HasMatchingGameplayTag(Tag);
}

float ASOCombatCharacter::GetMoveScale() const
{
	// what it is under (a slow, haste) and what it wears (stride)
	return Attributes ? Attributes->GetMoveScale() * GetAttributeScale(ESOAttribute::Stride) : 1.0f;
}

void ASOCombatCharacter::NoteNearMiss(AActor* From)
{
	UWorld* World = GetWorld();
	if (!HasAuthority() || !World || bDead || World->GetTimeSeconds() - LastNearMiss < 0.6f)
	{
		return;
	}
	LastNearMiss = World->GetTimeSeconds();
	if (USOCombatStatics::ApplyStatus(From, this, SOTags::Status_Suppressed, 1.6f) && AbilitySystem)
	{
		AbilitySystem->NoteUnderFire(); // (the shield does not come back while rounds are landing round it)
	}
}

float ASOCombatCharacter::GetAttribute(ESOAttribute Attribute) const
{
	if (!Attributes)
	{
		return 0.0f;
	}
	switch (Attribute)
	{
	case ESOAttribute::Plating: return Attributes->GetPlating();
	case ESOAttribute::Mending: return Attributes->GetMending();
	case ESOAttribute::Stride: return Attributes->GetStride();
	case ESOAttribute::Ordnance: return Attributes->GetOrdnance();
	case ESOAttribute::Impact: return Attributes->GetImpact();
	case ESOAttribute::Focus: return Attributes->GetFocus();
	default: return 0.0f;
	}
}

float ASOCombatCharacter::GetAttributeScale(ESOAttribute Attribute) const
{
	return USOAttributeTable::Get().Scale(Attribute, GetAttribute(Attribute));
}

float ASOCombatCharacter::GetAbilityCooldownScale(ESOAbilitySlot Slot) const
{
	return Slot == ESOAbilitySlot::Grenade ? GetAttributeScale(ESOAttribute::Ordnance)
		: (Slot == ESOAbilitySlot::Melee ? GetAttributeScale(ESOAttribute::Impact) : 1.0f);
}

void ASOCombatCharacter::SetGearAttributes(const FSOAttributePoints& Points)
{
	if (!HasAuthority() || !AbilitySystem)
	{
		return;
	}
	if (GearEffect.IsValid())
	{
		AbilitySystem->RemoveActiveGameplayEffect(GearEffect);
		GearEffect.Invalidate();
	}
	if (Points.Total() <= 0)
	{
		return;
	}
	const FGameplayEffectSpecHandle Spec = AbilitySystem->MakeOutgoingSpec(USOGameplayEffect_Gear::StaticClass(), 1.0f, AbilitySystem->MakeEffectContext());
	if (Spec.IsValid())
	{
		Spec.Data->SetSetByCallerMagnitude(SOTags::SetByCaller_Gear_Plating, Points.Get(ESOAttribute::Plating));
		Spec.Data->SetSetByCallerMagnitude(SOTags::SetByCaller_Gear_Mending, Points.Get(ESOAttribute::Mending));
		Spec.Data->SetSetByCallerMagnitude(SOTags::SetByCaller_Gear_Stride, Points.Get(ESOAttribute::Stride));
		Spec.Data->SetSetByCallerMagnitude(SOTags::SetByCaller_Gear_Ordnance, Points.Get(ESOAttribute::Ordnance));
		Spec.Data->SetSetByCallerMagnitude(SOTags::SetByCaller_Gear_Impact, Points.Get(ESOAttribute::Impact));
		Spec.Data->SetSetByCallerMagnitude(SOTags::SetByCaller_Gear_Focus, Points.Get(ESOAttribute::Focus));
		GearEffect = AbilitySystem->ApplyGameplayEffectSpecToSelf(*Spec.Data);
	}
	OnMoveScaleChanged(); // (stride)
}

void ASOCombatCharacter::HandleMoveScaleChanged(const FOnAttributeChangeData& Change)
{
	OnMoveScaleChanged();
}

void ASOCombatCharacter::ConfirmHit(bool bCrit, bool bKilled)
{
	if (!HasAuthority())
	{
		return;
	}
	if (IsLocallyControlled())
	{
		OnHitConfirmed.Broadcast(bCrit, bKilled); // the host's own shot, or a creature's (nobody listens)
	}
	else if (IsPlayerControlled())
	{
		ClientHitConfirmed(bCrit, bKilled);
	}
}

void ASOCombatCharacter::ClientHitConfirmed_Implementation(bool bCrit, bool bKilled)
{
	OnHitConfirmed.Broadcast(bCrit, bKilled);
}

void ASOCombatCharacter::ShowAbility(ESOAbilitySlot Slot, bool bWindUp)
{
	if (HasAuthority())
	{
		MulticastAbility(Slot, bWindUp); // reaches this machine too
	}
	else if (bWindUp)
	{
		OnAbilityWindUp(Slot); // the player's own machine, ahead of the server
	}
	else
	{
		OnAbilityUsed(Slot);
	}
}

void ASOCombatCharacter::MulticastAbility_Implementation(ESOAbilitySlot Slot, bool bWindUp)
{
	if (!HasAuthority() && IsLocallyControlled())
	{
		return; // shown when it was pressed
	}
	if (bWindUp)
	{
		OnAbilityWindUp(Slot);
	}
	else
	{
		OnAbilityUsed(Slot);
	}
}

void ASOCombatCharacter::OnAbilityWindUp(ESOAbilitySlot Slot)
{
	const FSOAbilityGrant* Grant = AbilitySet ? AbilitySet->Find(Slot) : nullptr;
	if (Grant && !Grant->WindUpSound.IsNone())
	{
		USOSoundLibrary::PlayFor(this, Grant->WindUpSound, GetActorLocation(), 1.0f, ESOSoundRange::Far);
	}
	if (const USOGameplayAbility* Ability = Grant && Grant->Ability ? Grant->Ability.GetDefaultObject() : nullptr)
	{
		Ability->Telegraph(this, *Grant);
	}
}

bool ASOCombatCharacter::IsAbilityActive(ESOAbilitySlot Slot) const
{
	if (AbilitySystem)
	{
		for (const FGameplayAbilitySpec& Spec : AbilitySystem->GetActivatableAbilities())
		{
			if (Spec.InputID == static_cast<int32>(Slot))
			{
				return Spec.IsActive();
			}
		}
	}
	return false;
}

float ASOCombatCharacter::PrecisionAt(const FHitResult& Hit) const
{
	return USOProjectileSubsystem::IsPrecisionBone(Hit.BoneName) ? 1.0f : 0.0f;
}

void ASOCombatCharacter::OnAbilityUsed(ESOAbilitySlot Slot)
{
	const FSOAbilityGrant* Grant = AbilitySet ? AbilitySet->Find(Slot) : nullptr;
	if (!Grant)
	{
		return;
	}
	if (!Grant->Sound.IsNone())
	{
		// a thrown thing is heard nearby, a blow further, the big one across the field
		const ESOSoundRange Reach = Slot == ESOAbilitySlot::Ultimate ? ESOSoundRange::Far
			: (Slot == ESOAbilitySlot::Melee || Slot == ESOAbilitySlot::Class ? ESOSoundRange::Mid : ESOSoundRange::Near);
		USOSoundLibrary::PlayFor(this, Grant->Sound, GetActorLocation(), 1.0f, Reach);
	}
	if (const USOGameplayAbility* Ability = Grant->Ability ? Grant->Ability.GetDefaultObject() : nullptr)
	{
		Ability->Show(this, *Grant);
	}
}
