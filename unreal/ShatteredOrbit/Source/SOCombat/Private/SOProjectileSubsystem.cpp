#include "SOProjectileSubsystem.h"

#include "CollisionQueryParams.h"
#include "Engine/World.h"
#include "SOCombatCharacter.h"
#include "SOCombatStatics.h"

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

void USOProjectileSubsystem::Tick(float DeltaTime)
{
	for (int32 i = Rounds.Num() - 1; i >= 0; --i)
	{
		if (!StepRound(Rounds[i], DeltaTime))
		{
			Rounds.RemoveAtSwap(i, 1, EAllowShrinking::No);
		}
	}
}
