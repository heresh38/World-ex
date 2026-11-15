#include "SOBoss.h"

#include "AbilitySystemComponent.h"
#include "Abilities/SOAbilitySet.h"
#include "Components/CapsuleComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "SOAbilitySystemComponent.h"
#include "SOAltered.h"
#include "SOCombatStatics.h"
#include "SOCombatTypes.h"
#include "SOCue.h"
#include "SOEnemy.h"
#include "SOProjectileSubsystem.h"

int32 USOBossData::PhaseAt(float HealthFraction) const
{
	int32 Phase = 0;
	for (int32 i = 1; i < Phases.Num(); ++i)
	{
		if (HealthFraction <= Phases[i].FromHealth)
		{
			Phase = i;
		}
	}
	return Phase;
}

USOBossData* USOBossData::Load(FName BossId)
{
	if (BossId.IsNone())
	{
		return nullptr;
	}
	FString Name = BossId.ToString();
	Name[0] = FChar::ToUpper(Name[0]);
	const FString Path = FString::Printf(TEXT("/Game/Data/DA_Boss_%s.DA_Boss_%s"), *Name, *Name);
	return Cast<USOBossData>(FSoftObjectPath(Path).TryLoad());
}

namespace
{
	/** How far behind the spot where a round met the body a weak point may lie and still be what it hit (cm). */
	const float WeakPointDepth = 260.0f;
}

USOBossComponent::USOBossComponent()
{
	PrimaryComponentTick.bCanEverTick = true;
	PrimaryComponentTick.TickInterval = 0.05f;
}

ASOEnemy* USOBossComponent::GetBoss() const
{
	return Cast<ASOEnemy>(GetOwner());
}

int32 USOBossComponent::GetPhase() const
{
	const ASOEnemy* Boss = GetBoss();
	return Boss ? Boss->BossPhase : 0;
}

const FSOBossPhase* USOBossComponent::GetPhaseData() const
{
	return Data && Data->Phases.IsValidIndex(GetPhase()) ? &Data->Phases[GetPhase()] : nullptr;
}

void USOBossComponent::Setup(USOBossData* InData)
{
	ASOEnemy* Boss = GetBoss();
	UWorld* World = GetWorld();
	Data = InData;
	if (!Data || !Boss || !World)
	{
		return;
	}
	WeakDamage.Init(0.0f, Data->WeakPoints.Num());
	if (World->GetNetMode() != NM_DedicatedServer)
	{
		// a light on every weak point: where to shoot is something seen, not something told
		for (int32 i = 0; i < Data->WeakPoints.Num(); ++i)
		{
			UPointLightComponent* Light = NewObject<UPointLightComponent>(Boss);
			Light->SetupAttachment(Boss->GetRootComponent());
			Light->SetLightColor(FLinearColor(0.85f, 0.7f, 1.0f));
			Light->SetIntensity(0.0f);
			Light->SetAttenuationRadius(420.0f);
			Light->SetCastShadows(false);
			Light->RegisterComponent();
			Lights.Add(Light);
		}
	}
	if (Boss->HasAuthority())
	{
		if (USOProjectileSubsystem* Rounds = World->GetSubsystem<USOProjectileSubsystem>())
		{
			RoundHandle = Rounds->OnHit.AddUObject(this, &USOBossComponent::OnRoundHit);
		}
		if (Data->Phases.Num() > 0)
		{
			EnterPhase(0);
		}
	}
}

void USOBossComponent::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	if (RoundHandle.IsValid())
	{
		if (USOProjectileSubsystem* Rounds = GetWorld() ? GetWorld()->GetSubsystem<USOProjectileSubsystem>() : nullptr)
		{
			Rounds->OnHit.Remove(RoundHandle);
		}
		RoundHandle.Reset();
	}
	Super::EndPlay(EndPlayReason);
}

void USOBossComponent::EnterPhase(int32 Index)
{
	ASOEnemy* Boss = GetBoss();
	if (!Boss || !Boss->HasAuthority() || !Data || !Data->Phases.IsValidIndex(Index))
	{
		return;
	}
	const FSOBossPhase& Phase = Data->Phases[Index];
	Boss->BossPhase = static_cast<uint8>(Index);
	Boss->BossWeakBroken = 0; // what was broken is whole again: every phase it can be broken once
	WeakDamage.Init(0.0f, Data->WeakPoints.Num());
	if (!Phase.Kit.IsNone())
	{
		if (UAbilitySystemComponent* Abilities = Boss->GetAbilitySystemComponent())
		{
			Abilities->CancelAllAbilities(); // whatever it was in the middle of belongs to the phase that is over
		}
		Boss->GrantAbilitySet(USOAbilitySet::Load(Phase.Kit));
	}
	Boss->OnMoveScaleChanged(); // (the phase's speed)
	if (Index > 0)
	{
		// it is heard and seen to change
		Boss->Voice(TEXT("alert"), 1.0f);
		USOCue::Sound(Boss, TEXT("boss_phase"), Boss->GetActorLocation(), 1.0f, 0.0f, ESOSoundRange::Far);
		USOCue::Blast(Boss, Boss->GetActorLocation(), FVector::UpVector, 420.0f, USOFxSubsystem::EBlast::Zap, Boss->GetAbilityColor());
	}
	OnPhaseChanged.Broadcast(Index);
	if (Phase.bShield)
	{
		StartShield();
	}
}

void USOBossComponent::StartShield()
{
	ASOEnemy* Boss = GetBoss();
	UWorld* World = GetWorld();
	if (bShielded || !Boss || !World || !Boss->HasAuthority() || Boss->IsDead())
	{
		return;
	}
	bShielded = true;
	if (UAbilitySystemComponent* Abilities = Boss->GetAbilitySystemComponent())
	{
		Abilities->CancelAllAbilities();
	}
	Boss->SetWantsFire(false);
	Boss->SetImmune(true, Data && !Data->ShieldText.IsEmpty() ? Data->ShieldText : NSLOCTEXT("SO", "BossShield", "Shielded: destroy the conduits"));
	// where the conduits rise: the level's own sockets, or a ring round where it stands
	TArray<FVector> Sockets;
	for (TActorIterator<AActor> It(World); It; ++It)
	{
		if (It->ActorHasTag(TEXT("SOConduit")))
		{
			Sockets.Add(It->GetActorLocation());
		}
	}
	if (Sockets.Num() == 0)
	{
		const FSOBossPhase* Phase = GetPhaseData();
		const int32 Count = FMath::Max(1, Phase ? Phase->Conduits : 3);
		const FVector Feet = Boss->GetActorLocation() - FVector(0, 0, Boss->GetCapsuleComponent()->GetScaledCapsuleHalfHeight());
		for (int32 i = 0; i < Count; ++i)
		{
			const float A = UE_TWO_PI * i / Count + 0.5f;
			Sockets.Add(Feet + FVector(FMath::Cos(A), FMath::Sin(A), 0.0f) * 2800.0f);
		}
	}
	Conduits.Reset();
	for (const FVector& S : Sockets)
	{
		FActorSpawnParameters Params;
		Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
		if (ASOConduit* C = World->SpawnActor<ASOConduit>(ASOConduit::StaticClass(), S + FVector(0, 0, 300.0f), FRotator::ZeroRotator, Params))
		{
			C->Anchor = Boss;
			Conduits.Add(C);
			USOCue::Blast(Boss, S, FVector::UpVector, 220.0f, USOFxSubsystem::EBlast::Zap, Boss->GetAbilityColor());
		}
	}
	USOCue::Sound(Boss, TEXT("reliquary_open"), Boss->GetActorLocation(), 1.0f, 0.0f, ESOSoundRange::Far);
}

void USOBossComponent::BreakShield()
{
	ASOEnemy* Boss = GetBoss();
	if (!bShielded || !Boss)
	{
		return;
	}
	// the shield breaks: it reels, open to everything
	bShielded = false;
	Boss->SetImmune(false);
	const FSOBossPhase* Phase = GetPhaseData();
	Stagger(Phase ? Phase->Stagger : 5.0f);
	const FVector At = Data && Data->WeakPoints.Num() > 0 ? GetWeakPointLocation(0) : Boss->GetActorLocation();
	USOCue::Sound(Boss, TEXT("boss_reel"), At, 1.0f, 0.0f, ESOSoundRange::Far);
	USOCue::Blast(Boss, At, Boss->GetActorForwardVector(), 400.0f, USOFxSubsystem::EBlast::Zap, Boss->GetAbilityColor());
}

void USOBossComponent::Stagger(float Seconds)
{
	ASOEnemy* Boss = GetBoss();
	if (!Boss || !Boss->HasAuthority() || Seconds <= 0.0f || Boss->IsDead())
	{
		return;
	}
	if (UAbilitySystemComponent* Abilities = Boss->GetAbilitySystemComponent())
	{
		Abilities->CancelAllAbilities();
	}
	Boss->SetWantsFire(false);
	// from itself: what it resists is what others would do to it
	USOCombatStatics::ApplyStatus(Boss, Boss, SOTags::Status_Stagger, Seconds);
}

bool USOBossComponent::IsStaggered() const
{
	const ASOEnemy* Boss = GetBoss();
	return Boss && Boss->HasStatus(SOTags::Status_Stagger);
}

FVector USOBossComponent::GetWeakPointLocation(int32 Index) const
{
	const ASOEnemy* Boss = GetBoss();
	if (!Boss || !Data || !Data->WeakPoints.IsValidIndex(Index))
	{
		return Boss ? Boss->GetActorLocation() : FVector::ZeroVector;
	}
	const FSOWeakPoint& Point = Data->WeakPoints[Index];
	const USkeletalMeshComponent* Mesh = Boss->GetMesh();
	const FVector Base = !Point.Bone.IsNone() && Mesh && Mesh->DoesSocketExist(Point.Bone) ? Mesh->GetSocketLocation(Point.Bone) : Boss->GetActorLocation();
	return Base + Boss->GetActorForwardVector() * Point.Offset.X + Boss->GetActorRightVector() * Point.Offset.Y + FVector(0.0f, 0.0f, Point.Offset.Z);
}

bool USOBossComponent::IsWeakPointOpen(int32 Index) const
{
	const ASOEnemy* Boss = GetBoss();
	return Boss && Data && Data->WeakPoints.IsValidIndex(Index) && !Boss->IsImmune() && !Boss->IsDead() && (Boss->BossWeakBroken & (1 << Index)) == 0;
}

int32 USOBossComponent::WeakPointAt(const FHitResult& Hit) const
{
	const ASOEnemy* Boss = GetBoss();
	if (!Boss || !Data)
	{
		return INDEX_NONE;
	}
	for (int32 i = 0; i < Data->WeakPoints.Num(); ++i)
	{
		const FSOWeakPoint& Point = Data->WeakPoints[i];
		if (!IsWeakPointOpen(i))
		{
			continue;
		}
		// The round's line, not the spot where it met the body's collision: a creature's bodies are a few coarse
		// shapes round its bones, well off the drawn surface. It is a hit on the point if the round was going
		// through it and had not already gone past it.
		const FVector At = GetWeakPointLocation(i);
		const FVector Shot = (Hit.TraceEnd - Hit.TraceStart).GetSafeNormal();
		if (Shot.IsNearlyZero())
		{
			if (FVector::DistSquared(Hit.ImpactPoint, At) > FMath::Square(Point.Radius))
			{
				continue;
			}
		}
		else
		{
			const float Along = FVector::DotProduct(At - Hit.ImpactPoint, Shot);
			if (Along < -Point.Radius || Along > WeakPointDepth || FVector::DistSquared(Hit.ImpactPoint + Shot * Along, At) > FMath::Square(Point.Radius))
			{
				continue;
			}
			if (Point.bFront && FVector::DotProduct(Shot, Boss->GetActorForwardVector()) > -0.15f)
			{
				continue; // from the side or behind: plate
			}
		}
		return i;
	}
	return INDEX_NONE;
}

void USOBossComponent::OnRoundHit(const FSOProjectile& Round, const FHitResult& Hit, float Applied)
{
	if (Applied > 0.0f && Hit.GetActor() == GetOwner())
	{
		HitWeakPoint(WeakPointAt(Hit), Applied);
	}
}

void USOBossComponent::HitWeakPoint(int32 Index, float Damage)
{
	ASOEnemy* Boss = GetBoss();
	if (!Boss || !Boss->HasAuthority() || !IsWeakPointOpen(Index) || !WeakDamage.IsValidIndex(Index))
	{
		return;
	}
	const FSOWeakPoint& Point = Data->WeakPoints[Index];
	WeakDamage[Index] += Damage;
	if (Point.BreakDamage > 0.0f && WeakDamage[Index] >= Point.BreakDamage)
	{
		// it breaks: shut for the rest of the phase, and the boss reels
		const FVector At = GetWeakPointLocation(Index);
		Boss->BossWeakBroken |= static_cast<uint8>(1 << Index);
		USOCue::Blast(Boss, At, Boss->GetActorForwardVector(), 300.0f, USOFxSubsystem::EBlast::Zap, Boss->GetAbilityColor());
		USOCue::Sound(Boss, TEXT("boss_reel"), At, 0.9f, 0.05f, ESOSoundRange::Far);
		Stagger(Point.BreakStagger);
	}
}

float USOBossComponent::ScaleDamage(float Amount) const
{
	const FSOBossPhase* Phase = GetPhaseData();
	return Amount * (Phase ? Phase->DamageTaken : 1.0f) * (Data && IsStaggered() ? Data->StaggerDamage : 1.0f);
}

float USOBossComponent::GetCooldownScale() const
{
	const FSOBossPhase* Phase = GetPhaseData();
	return Phase ? Phase->Cooldown : 1.0f;
}

float USOBossComponent::GetSpeedScale() const
{
	const FSOBossPhase* Phase = GetPhaseData();
	return Phase ? Phase->Speed : 1.0f;
}

float USOBossComponent::NextMovePause() const
{
	const FSOBossPhase* Phase = GetPhaseData();
	return Phase ? FMath::FRandRange(Phase->MovePause.X, FMath::Max(Phase->MovePause.X, Phase->MovePause.Y)) : 3.5f;
}

void USOBossComponent::OwnerDied()
{
	for (const TWeakObjectPtr<ASOConduit>& C : Conduits)
	{
		if (C.IsValid() && !C->IsDead())
		{
			C->Die(nullptr);
		}
	}
	bShielded = false;
	for (UPointLightComponent* Light : Lights)
	{
		if (Light)
		{
			Light->SetIntensity(0.0f);
		}
	}
}

void USOBossComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);
	ASOEnemy* Boss = GetBoss();
	if (!Boss || !Data || Boss->IsDead())
	{
		return;
	}
	if (Boss->HasAuthority())
	{
		if (bShielded)
		{
			Conduits.RemoveAll([](const TWeakObjectPtr<ASOConduit>& C) { return !C.IsValid() || C->IsDead(); });
			if (Conduits.Num() == 0)
			{
				BreakShield();
			}
		}
		else if (!IsStaggered() && Data->PhaseAt(Boss->GetHealth() / FMath::Max(Boss->GetMaxHealth(), 1.0f)) > GetPhase())
		{
			// One at a time (a blow that crosses two thresholds still meets each phase's shield), and never while it
			// reels: the opening the players earned is theirs to the end before the next shield comes up.
			EnterPhase(GetPhase() + 1);
		}
	}
	// the weak points that are open glow, brighter while it reels
	const float T = GetWorld()->GetTimeSeconds();
	const bool bReeling = IsStaggered();
	for (int32 i = 0; i < Lights.Num(); ++i)
	{
		if (UPointLightComponent* Light = Lights[i])
		{
			Light->SetWorldLocation(GetWeakPointLocation(i) + Boss->GetActorForwardVector() * 14.0f);
			Light->SetIntensity(IsWeakPointOpen(i) ? (bReeling ? 150.0f : 70.0f) * (0.75f + 0.25f * FMath::Sin(T * (bReeling ? 11.0f : 4.3f))) : 0.0f);
		}
	}
}
