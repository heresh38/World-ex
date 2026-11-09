#include "SOEnemyAIController.h"

#include "EngineUtils.h"
#include "Engine/World.h"
#include "NavigationSystem.h"
#include "Navigation/PathFollowingComponent.h"
#include "SOCombatCharacter.h"
#include "SOCombatStatics.h"
#include "SOCombatTypes.h"
#include "SOEnemy.h"

ASOEnemyAIController::ASOEnemyAIController()
{
	PrimaryActorTick.bCanEverTick = true;
	bWantsPlayerState = false;
}

void ASOEnemyAIController::OnPossess(APawn* InPawn)
{
	Super::OnPossess(InPawn);
	Home = InPawn ? InPawn->GetActorLocation() : FVector::ZeroVector;
	NoiseHandle = USOCombatStatics::OnNoise().AddUObject(this, &ASOEnemyAIController::OnNoise);
	NextThink = GetWorld()->GetTimeSeconds() + FMath::FRandRange(0.0f, ThinkInterval);
}

void ASOEnemyAIController::OnUnPossess()
{
	USOCombatStatics::OnNoise().Remove(NoiseHandle);
	Super::OnUnPossess();
}

void ASOEnemyAIController::OnNoise(UWorld* World, const FVector& Location, AActor* NoiseInstigator, float Radius)
{
	ASOEnemy* Me = Cast<ASOEnemy>(GetPawn());
	ASOCombatCharacter* Source = Cast<ASOCombatCharacter>(NoiseInstigator);
	if (World != GetWorld() || !Me || Me->IsDead() || !Source || Source->IsDead() || !USOCombatStatics::AreHostile(Me, Source))
	{
		return;
	}
	if (FVector::Dist(Location, Me->GetActorLocation()) <= Radius && !Target.IsValid())
	{
		Target = Source;
		LastKnownLocation = Location;
		LastSeenTime = World->GetTimeSeconds();
	}
}

bool ASOEnemyAIController::CanSee(const AActor* Other) const
{
	const ASOEnemy* Me = Cast<ASOEnemy>(GetPawn());
	if (!Me || !Other)
	{
		return false;
	}
	const FVector Eye = Me->GetPawnViewLocation();
	const FVector Their = Other->GetActorLocation() + FVector(0, 0, 50.0f);
	const FVector To = Their - Eye;
	const float Dist = To.Size();
	if (Dist > Me->SightRange)
	{
		return false;
	}
	if (Dist > AwareRadius)
	{
		const float Cos = FVector::DotProduct(Me->GetActorForwardVector().GetSafeNormal2D(), To.GetSafeNormal2D());
		if (Cos < FMath::Cos(FMath::DegreesToRadians(ViewHalfAngle)))
		{
			return false;
		}
	}
	FCollisionQueryParams Params(SCENE_QUERY_STAT(SOSight), false, Me);
	Params.AddIgnoredActor(Other);
	return !GetWorld()->LineTraceTestByChannel(Eye, Their, ECC_Visibility, Params);
}

ASOCombatCharacter* ASOEnemyAIController::FindTarget() const
{
	const ASOEnemy* Me = Cast<ASOEnemy>(GetPawn());
	ASOCombatCharacter* Best = nullptr;
	float BestDist = BIG_NUMBER;
	for (TActorIterator<ASOCombatCharacter> It(GetWorld()); It; ++It)
	{
		ASOCombatCharacter* Other = *It;
		if (Other == Me || Other->IsDead() || !USOCombatStatics::AreHostile(Me, Other))
		{
			continue;
		}
		const float Dist = FVector::Dist(Other->GetActorLocation(), Me->GetActorLocation());
		if (Dist < BestDist && CanSee(Other))
		{
			Best = Other;
			BestDist = Dist;
		}
	}
	return Best;
}

void ASOEnemyAIController::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	ASOEnemy* Me = Cast<ASOEnemy>(GetPawn());
	if (!Me)
	{
		return;
	}
	if (Me->IsDead())
	{
		if (State != ESOEnemyState::Dead)
		{
			State = ESOEnemyState::Dead;
			StopMovement();
		}
		return;
	}
	// Without a nav path the chase steers straight at the target every frame.
	if (bDirectChase && Target.IsValid() && !Me->IsAttacking())
	{
		const FVector To = (Target->GetActorLocation() - Me->GetActorLocation()).GetSafeNormal2D();
		Me->AddMovementInput(To, 1.0f);
	}
	const float Now = GetWorld()->GetTimeSeconds();
	if (Now >= NextThink)
	{
		NextThink = Now + ThinkInterval;
		Think();
	}
}

void ASOEnemyAIController::Think()
{
	ASOEnemy* Me = Cast<ASOEnemy>(GetPawn());
	const float Now = GetWorld()->GetTimeSeconds();

	if (ASOCombatCharacter* Current = Target.Get(); Current && Current->IsDead())
	{
		Target = nullptr;
	}
	if (ASOCombatCharacter* Seen = FindTarget())
	{
		Target = Seen;
		LastKnownLocation = Seen->GetActorLocation();
		LastSeenTime = Now;
	}
	else if (bHunter)
	{
		// out of sight: still hunted (the nearest player, wherever they are)
		if (!Target.IsValid())
		{
			float Best = BIG_NUMBER;
			for (TActorIterator<ASOCombatCharacter> It(GetWorld()); It; ++It)
			{
				const float D = FVector::DistSquared(It->GetActorLocation(), Me->GetActorLocation());
				if (*It != Me && !It->IsDead() && It->IsPlayerControlled() && USOCombatStatics::AreHostile(Me, *It) && D < Best)
				{
					Best = D;
					Target = *It;
				}
			}
		}
		if (Target.IsValid())
		{
			LastKnownLocation = Target->GetActorLocation();
		}
	}
	else if (Target.IsValid() && Now - LastSeenTime > LoseTargetTime)
	{
		Target = nullptr;
	}

	if (!Target.IsValid())
	{
		bDirectChase = false;
		Me->SetRunning(false);
		Wander();
		return;
	}

	Me->SetRunning(true);
	if (Me->DistanceTo(Target.Get()) <= Me->MeleeRange)
	{
		State = ESOEnemyState::Attack;
		StopMovement();
		bDirectChase = false;
		Me->TryAttack(Target.Get());
		return;
	}
	State = ESOEnemyState::Chase;
	ChaseTarget();
}

void ASOEnemyAIController::ChaseTarget()
{
	ASOEnemy* Me = Cast<ASOEnemy>(GetPawn());
	UNavigationSystemV1* Nav = FNavigationSystem::GetCurrent<UNavigationSystemV1>(GetWorld());
	if (Nav && Nav->GetDefaultNavDataInstance(FNavigationSystem::DontCreate))
	{
		const EPathFollowingRequestResult::Type Result = MoveToActor(Target.Get(), Me->MeleeRange * 0.5f, true, true, true, nullptr, true);
		if (Result != EPathFollowingRequestResult::Failed)
		{
			if (!bUsedNav)
			{
				UE_LOG(LogSOCombat, Log, TEXT("%s hunts %s along the nav mesh"), *Me->GetName(), *Target->GetName());
			}
			bUsedNav = true;
			bDirectChase = false;
			return;
		}
	}
	bDirectChase = true; // no nav mesh or no path: straight at it
}

void ASOEnemyAIController::Wander()
{
	const float Now = GetWorld()->GetTimeSeconds();
	State = ESOEnemyState::Wander;
	if (Now < NextWander)
	{
		return;
	}
	NextWander = Now + FMath::FRandRange(3.5f, 7.0f);
	UNavigationSystemV1* Nav = FNavigationSystem::GetCurrent<UNavigationSystemV1>(GetWorld());
	FNavLocation Point;
	if (Nav && Nav->GetRandomReachablePointInRadius(Home, WanderRadius, Point))
	{
		MoveToLocation(Point.Location, 50.0f);
	}
	else
	{
		State = ESOEnemyState::Idle;
	}
}
