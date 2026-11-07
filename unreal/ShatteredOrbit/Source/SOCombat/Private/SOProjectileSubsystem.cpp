#include "SOProjectileSubsystem.h"

#include "CollisionQueryParams.h"
#include "Engine/World.h"
#include "SOCombatCharacter.h"
#include "SOCombatStatics.h"
#include "EngineUtils.h"

bool USOProjectileSubsystem::DoesSupportWorldType(const EWorldType::Type WorldType) const
{
	return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

TStatId USOProjectileSubsystem::GetStatId() const
{
	RETURN_QUICK_DECLARE_CYCLE_STAT(USOProjectileSubsystem, STATGROUP_Tickables);
}

void USOProjectileSubsystem::Fire(const FSOProjectile& Round)
{
	Rounds.Add(Round);
}

float USOProjectileSubsystem::DamageAtDistance(const FSOProjectile& Round, float Distance)
{
	if (Round.FalloffStart <= 0.0f || Distance <= Round.FalloffStart)
	{
		return Round.Damage;
	}
	const float Alpha = FMath::Clamp((Distance - Round.FalloffStart) / Round.FalloffStart, 0.0f, 1.0f);
	return Round.Damage * FMath::Lerp(1.0f, Round.MinDamageScale, Alpha);
}

bool USOProjectileSubsystem::IsPrecisionBone(FName Bone)
{
	const FString Name = Bone.ToString().ToLower();
	return Name.Contains(TEXT("head")) || Name.Contains(TEXT("neck"));
}

bool USOProjectileSubsystem::StepRound(FSOProjectile& Round, float DeltaTime, FHitResult* OutHit)
{
	UWorld* World = GetWorld();
	if (!World || DeltaTime <= 0.0f)
	{
		return true;
	}
	Round.Life -= DeltaTime;

	const FVector Start = Round.Position;
	const FVector Gravity(0.0f, 0.0f, -Round.Gravity);
	const FVector End = Start + Round.Velocity * DeltaTime + 0.5f * Gravity * DeltaTime * DeltaTime;
	Round.Velocity += Gravity * DeltaTime;

	FCollisionQueryParams Params(SCENE_QUERY_STAT(SORound), true);
	Params.bReturnPhysicalMaterial = false;
	if (AActor* Shooter = Round.Instigator.Get())
	{
		Params.AddIgnoredActor(Shooter);
		TArray<AActor*> Attached;
		Shooter->GetAttachedActors(Attached);
		Params.AddIgnoredActors(Attached);
	}

	FHitResult Hit;
	if (World->LineTraceSingleByChannel(Hit, Start, End, SO_TRACE_BULLET, Params))
	{
		Round.Position = Hit.ImpactPoint;
		float Applied = 0.0f;
		if (World->GetNetMode() != NM_Client && Hit.GetActor())
		{
			const bool bCrit = IsPrecisionBone(Hit.BoneName);
			const float Distance = FVector::Dist(Round.Origin, Hit.ImpactPoint);
			const float Amount = DamageAtDistance(Round, Distance) * (bCrit ? Round.CritMultiplier : 1.0f);
			Applied = USOCombatStatics::ApplyDamage(Round.Instigator.Get(), Hit.GetActor(), Amount, bCrit);
		}
		if (World->GetNetMode() != NM_Client)
		{
			OnImpact(Round, Hit, Applied);
		}
		OnHit.Broadcast(Round, Hit, Applied);
		if (OutHit)
		{
			*OutHit = Hit;
		}
		return false;
	}
	Round.Position = End;
	return Round.Life > 0.0f && Round.Position.Z > World->GetWorldSettings()->KillZ;
}

void USOProjectileSubsystem::OnImpact(const FSOProjectile& Round, const FHitResult& Hit, float Applied)
{
	AActor* Instigator = Round.Instigator.Get();
	AActor* Direct = Applied > 0.0f ? Hit.GetActor() : nullptr;
	TArray<AActor*> Victims;
	if (Direct)
	{
		Victims.Add(Direct);
	}
	if (Round.Splash > 0.0f)
	{
		ApplySplash(Instigator, FVector(Hit.ImpactPoint) + FVector(Hit.ImpactNormal) * 10.0f, Round.Splash, Round.Damage, Direct, &Victims);
	}
	if (Round.Dot > 0.0f)
	{
		for (AActor* Victim : Victims)
		{
			AddBurn(Instigator, Victim, Round.Damage * Round.Dot, 3.0f);
		}
	}
	if (Round.Swarm > 0)
	{
		// each parasite chews ~8 % of the sac's damage per second for 4 s around the burst
		Swarms.Add({ Instigator, FVector(Hit.ImpactPoint), FMath::Max(Round.Splash, 250.0f), Round.Damage * 0.08f * Round.Swarm, 4.0f, 0.0f });
	}
}

float USOProjectileSubsystem::ApplySplash(AActor* Instigator, const FVector& Center, float Radius, float Damage, AActor* Ignore, TArray<AActor*>* OutVictims)
{
	UWorld* World = GetWorld();
	if (!World || Radius <= 0.0f || World->GetNetMode() == NM_Client)
	{
		return 0.0f;
	}
	float Total = 0.0f;
	for (TActorIterator<ASOCombatCharacter> It(World); It; ++It)
	{
		ASOCombatCharacter* Victim = *It;
		if (Victim == Ignore || Victim->IsDead())
		{
			continue;
		}
		const float Distance = FVector::Dist(Center, Victim->GetActorLocation());
		if (Distance > Radius)
		{
			continue;
		}
		FCollisionQueryParams Params(SCENE_QUERY_STAT(SOSplash), false, Victim);
		Params.AddIgnoredActor(Instigator);
		if (World->LineTraceTestByChannel(Center, Victim->GetActorLocation(), ECC_Visibility, Params))
		{
			continue; // behind a wall
		}
		const float Amount = Damage * FMath::Lerp(1.0f, 0.25f, Distance / Radius);
		const float Applied = USOCombatStatics::ApplyDamage(Instigator, Victim, Amount, false);
		Total += Applied;
		if (Applied > 0.0f && OutVictims)
		{
			OutVictims->Add(Victim);
		}
	}
	return Total;
}

void USOProjectileSubsystem::AddBurn(AActor* Instigator, AActor* Victim, float Total, float Duration)
{
	if (Victim && Total > 0.0f && Duration > 0.0f)
	{
		Burns.Add({ Instigator, Victim, Total / Duration, Duration, 0.0f });
	}
}

void USOProjectileSubsystem::Tick(float DeltaTime)
{
	// acid and parasites deal their damage in 0.5 s ticks
	for (int32 i = Burns.Num() - 1; i >= 0; --i)
	{
		FBurn& B = Burns[i];
		const float Step = FMath::Min(DeltaTime, B.Left);
		B.Left -= Step;
		B.Tick += Step;
		if (B.Tick >= 0.5f || B.Left <= 0.0f)
		{
			if (AActor* Victim = B.Victim.Get())
			{
				USOCombatStatics::ApplyDamage(B.Instigator.Get(), Victim, B.PerSecond * B.Tick, false);
			}
			B.Tick = 0.0f;
		}
		if (B.Left <= 0.0f || !B.Victim.IsValid())
		{
			Burns.RemoveAtSwap(i, 1, EAllowShrinking::No);
		}
	}
	for (int32 i = Swarms.Num() - 1; i >= 0; --i)
	{
		FSwarm& S = Swarms[i];
		const float Step = FMath::Min(DeltaTime, S.Left);
		S.Left -= Step;
		S.Tick += Step;
		if (S.Tick >= 0.5f || S.Left <= 0.0f)
		{
			ApplySplash(S.Instigator.Get(), S.Center + FVector(0, 0, 40.0f), S.Radius, S.PerSecond * S.Tick);
			S.Tick = 0.0f;
		}
		if (S.Left <= 0.0f)
		{
			Swarms.RemoveAtSwap(i, 1, EAllowShrinking::No);
		}
	}

	for (int32 i = Rounds.Num() - 1; i >= 0; --i)
	{
		if (!StepRound(Rounds[i], DeltaTime))
		{
			Rounds.RemoveAtSwap(i, 1, EAllowShrinking::No);
		}
	}
}
