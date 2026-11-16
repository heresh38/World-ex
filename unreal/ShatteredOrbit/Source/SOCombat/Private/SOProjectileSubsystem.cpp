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

void USOProjectileSubsystem::NoteNearMisses(const FSOProjectile& Round, const FVector& From, const FVector& To, const AActor* Struck)
{
	ASOCombatCharacter* Shooter = Cast<ASOCombatCharacter>(Round.Instigator.Get());
	UWorld* World = GetWorld();
	if (!Shooter || !World || Round.Damage <= 0.0f)
	{
		return;
	}
	// who there is to pass close to: looked up now and then, not for every round on every frame
	if (World->GetTimeSeconds() - NearMissListAt > 0.5f || World->GetTimeSeconds() < NearMissListAt)
	{
		NearMissListAt = World->GetTimeSeconds();
		NearMissList.Reset();
		for (TActorIterator<ASOCombatCharacter> It(World); It; ++It)
		{
			NearMissList.Add(*It);
		}
	}
	for (const TWeakObjectPtr<ASOCombatCharacter>& Entry : NearMissList)
	{
		ASOCombatCharacter* Near = Entry.Get();
		if (!Near || Near == Shooter || Near == Struck || Near->IsDead() || !USOCombatStatics::AreHostile(Shooter, Near))
		{
			continue;
		}
		if (FMath::PointDistToSegmentSquared(Near->GetActorLocation(), From, To) <= FMath::Square(NearMissRadius))
		{
			Near->NoteNearMiss(Shooter);
		}
	}
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
	for (const TWeakObjectPtr<AActor>& Through : Round.Passed)
	{
		Params.AddIgnoredActor(Through.Get());
	}

	FHitResult Hit;
	const bool bMet = World->LineTraceSingleByChannel(Hit, Start, End, SO_TRACE_BULLET, Params);
	if (World->GetNetMode() != NM_Client)
	{
		NoteNearMisses(Round, Start, bMet ? FVector(Hit.ImpactPoint) : End, bMet ? Hit.GetActor() : nullptr);
	}
	if (bMet)
	{
		Round.Position = Hit.ImpactPoint;
		float Applied = 0.0f;
		// a precision hit is the victim's to call (the head; a boss's weak points, which can be worth more)
		const ASOCombatCharacter* Struck = Cast<ASOCombatCharacter>(Hit.GetActor());
		const float Precision = Struck ? Struck->PrecisionAt(Hit) : (IsPrecisionBone(Hit.BoneName) ? 1.0f : 0.0f);
		const bool bCrit = Precision > 0.0f;
		if (World->GetNetMode() != NM_Client && Hit.GetActor())
		{
			const float Distance = FVector::Dist(Round.Origin, Hit.ImpactPoint);
			float Amount = DamageAtDistance(Round, Distance) * (bCrit ? Round.CritMultiplier * Precision : 1.0f);
			if (Struck)
			{
				Amount *= Struck->GetShield() > 0.0f ? Round.ShieldScale : Round.HealthScale; // (a perk: harder on shields, or on flesh)
			}
			// (where it landed goes with the damage: the body shows the hit there)
			const FSOHitScope Where(Hit.BoneName, Hit.ImpactPoint, Round.Velocity.GetSafeNormal(), bCrit);
			Applied = USOCombatStatics::ApplyDamage(Round.Instigator.Get(), Hit.GetActor(), Amount, bCrit);
		}
		if (World->GetNetMode() != NM_Client)
		{
			OnImpact(Round, Hit, Applied);
		}
		OnHit.Broadcast(Round, Hit, Applied);
		if (Applied > 0.0f)
		{
			// the shooter's machine marks the hit (rounds fly on the server only)
			if (ASOCombatCharacter* Shooter = Cast<ASOCombatCharacter>(Round.Instigator.Get()))
			{
				const ASOCombatCharacter* Victim = Cast<ASOCombatCharacter>(Hit.GetActor());
				Shooter->ConfirmHit(bCrit, Victim && Victim->IsDead());
			}
		}
		if (OutHit)
		{
			*OutHit = Hit;
		}
		// a slug's crystal goes on into the body and out the far side (the next body in line takes what it has left);
		// a wall stops it, and so does a plate that turns the blow
		if (Round.Pierce > 0 && Struck && !Struck->TurnsBlow(Round.Origin))
		{
			--Round.Pierce;
			Round.Damage *= Round.PierceKeep;
			Round.Passed.Add(Hit.GetActor());
			Round.Position = FVector(Hit.ImpactPoint) + Round.Velocity.GetSafeNormal() * 2.0f;
			return Round.Life > 0.0f;
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
	if (Round.Status.IsValid() && Round.StatusDuration > 0.0f)
	{
		for (AActor* Victim : Victims)
		{
			USOCombatStatics::ApplyStatus(Instigator, Victim, Round.Status, Round.StatusDuration, Round.StatusMagnitude);
		}
	}
	if (Round.Swarm > 0)
	{
		// each parasite chews ~8 % of the sac's damage per second for 4 s around the burst
		Swarms.Add({ Instigator, FVector(Hit.ImpactPoint), FMath::Max(Round.Splash, 250.0f), Round.Damage * 0.08f * Round.Swarm, 4.0f, 0.0f });
	}
	if (Round.Pool > 0.0f)
	{
		// the poison soaks the ground: half the round's acid share per second, every second it lies there
		const float PerSecond = Round.Damage * FMath::Max(Round.Dot, 0.3f) * 0.5f;
		AddPool(Instigator, FVector(Hit.ImpactPoint) + FVector(Hit.ImpactNormal) * 5.0f, PoolRadius(Round.Splash), PerSecond, Round.Pool);
	}
}

bool USOProjectileSubsystem::FindFloor(const UWorld* World, const FVector& Point, FVector& OutFloor, FVector& OutNormal)
{
	if (!World)
	{
		return false;
	}
	FHitResult Floor;
	FCollisionObjectQueryParams Objects(ECC_WorldStatic);
	FCollisionQueryParams Params(SCENE_QUERY_STAT(SOPoolFloor), false);
	if (!World->LineTraceSingleByObjectType(Floor, Point + FVector(0, 0, 20.0f), Point - FVector(0, 0, 600.0f), Objects, Params) || Floor.ImpactNormal.Z < 0.55f)
	{
		return false;
	}
	OutFloor = Floor.ImpactPoint;
	OutNormal = Floor.ImpactNormal;
	return true;
}

void USOProjectileSubsystem::AddPool(AActor* Instigator, const FVector& Point, float Radius, float PerSecond, float Duration)
{
	FVector Floor, Normal;
	if (PerSecond <= 0.0f || Duration <= 0.0f || !FindFloor(GetWorld(), Point, Floor, Normal))
	{
		return;
	}
	for (FPool& P : Pools)
	{
		if (P.Instigator == Instigator && FVector::DistSquared(P.Center, Floor) < FMath::Square(P.Radius * 0.6f))
		{
			// more goo on the same puddle: it lasts longer and burns harder, up to four rounds' worth
			P.Left = FMath::Max(P.Left, Duration);
			P.PerSecond = FMath::Min(P.PerSecond + PerSecond * 0.5f, P.Cap);
			P.Radius = FMath::Max(P.Radius, Radius);
			return;
		}
	}
	Pools.Add({ Instigator, Floor, Radius, PerSecond, PerSecond * 4.0f, Duration, 0.0f });
}

void USOProjectileSubsystem::ApplyGround(AActor* Instigator, const FVector& Center, float Radius, float Damage)
{
	UWorld* World = GetWorld();
	if (!World || Damage <= 0.0f || World->GetNetMode() == NM_Client)
	{
		return;
	}
	for (TActorIterator<ASOCombatCharacter> It(World); It; ++It)
	{
		ASOCombatCharacter* Victim = *It;
		if (Victim == Instigator || Victim->IsDead())
		{
			continue;
		}
		const float HalfHeight = Victim->GetSimpleCollisionHalfHeight();
		const FVector Feet = Victim->GetActorLocation() - FVector(0, 0, HalfHeight);
		if (FVector::DistSquared2D(Feet, Center) <= FMath::Square(Radius) && FMath::Abs(Feet.Z - Center.Z) < 150.0f)
		{
			USOCombatStatics::ApplyDamage(Instigator, Victim, Damage, false);
		}
	}
}

float USOProjectileSubsystem::ApplySplash(AActor* Instigator, const FVector& Center, float Radius, float Damage, AActor* Ignore, TArray<AActor*>* OutVictims)
{
	if (Radius >= 200.0f)
	{
		USOCombatStatics::ReportNoise(this, Center, Instigator, 5000.0f); // (a blast is heard further than any gun)
	}
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
	// a condition on the victim (Status.Burn): half-second ticks through the damage gate, seen by every machine
	USOCombatStatics::ApplyStatus(Instigator, Victim, SOTags::Status_Burn, Duration, Total);
}

void USOProjectileSubsystem::Tick(float DeltaTime)
{
	// parasites and poison on the ground deal their damage in 0.5 s ticks
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
	for (int32 i = Pools.Num() - 1; i >= 0; --i)
	{
		FPool& P = Pools[i];
		const float Step = FMath::Min(DeltaTime, P.Left);
		P.Left -= Step;
		P.Tick += Step;
		if (P.Tick >= 0.5f || P.Left <= 0.0f)
		{
			ApplyGround(P.Instigator.Get(), P.Center, P.Radius, P.PerSecond * P.Tick);
			P.Tick = 0.0f;
		}
		if (P.Left <= 0.0f)
		{
			Pools.RemoveAtSwap(i, 1, EAllowShrinking::No);
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
