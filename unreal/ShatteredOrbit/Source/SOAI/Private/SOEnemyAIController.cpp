#include "SOEnemyAIController.h"

#include "Components/CapsuleComponent.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "NavigationSystem.h"
#include "Navigation/PathFollowingComponent.h"
#include "SOCharacter.h"
#include "SOCharacterMovementComponent.h"
#include "SOCombatCharacter.h"
#include "SOCombatStatics.h"
#include "SOCombatTypes.h"
#include "SOEnemy.h"

namespace
{
	float Now(const UObject* O) { return O->GetWorld()->GetTimeSeconds(); }

	float Health01(const ASOCombatCharacter* C) { return C->GetHealth() / FMath::Max(C->GetMaxHealth(), 1.0f); }

	UNavigationSystemV1* NavOf(UWorld* World)
	{
		UNavigationSystemV1* Nav = FNavigationSystem::GetCurrent<UNavigationSystemV1>(World);
		return Nav && Nav->GetDefaultNavDataInstance(FNavigationSystem::DontCreate) ? Nav : nullptr;
	}

	/** World-only sight line (bodies and the route's invisible walls do not block). */
	bool Clear(UWorld* World, const FVector& A, const FVector& B, const AActor* IgnoreA, const AActor* IgnoreB = nullptr)
	{
		FCollisionQueryParams Params(SCENE_QUERY_STAT(SOSight), false, IgnoreA);
		if (IgnoreB)
		{
			Params.AddIgnoredActor(IgnoreB);
		}
		return !World->LineTraceTestByChannel(A, B, ECC_Visibility, Params);
	}
}

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
	HitHandle = USOCombatStatics::OnCharacterHit().AddUObject(this, &ASOEnemyAIController::OnHit);
	DiedHandle = USOCombatStatics::OnCharacterDied().AddUObject(this, &ASOEnemyAIController::OnDied);
	NextThink = GetWorld()->GetTimeSeconds() + FMath::FRandRange(0.0f, ThinkInterval);
	LastThink = GetWorld()->GetTimeSeconds();
	bFlanker = InPawn && (InPawn->GetUniqueID() % 3) == 0;
	StuckCheckFrom = Home;
	const uint32 Id = InPawn ? InPawn->GetUniqueID() : 0;
	RangeBias = 0.78f + 0.44f * ((Id * 2654435761u >> 8) % 1000) / 1000.0f;
	SideBias = (Id / 3) % 2 ? 1.0f : -1.0f;
}

void ASOEnemyAIController::OnUnPossess()
{
	USOCombatStatics::OnNoise().Remove(NoiseHandle);
	USOCombatStatics::OnCharacterHit().Remove(HitHandle);
	USOCombatStatics::OnCharacterDied().Remove(DiedHandle);
	Super::OnUnPossess();
}

// ------------------------------------------------------------------ senses

void ASOEnemyAIController::OnNoise(UWorld* World, const FVector& Location, AActor* NoiseInstigator, float Radius)
{
	ASOEnemy* Me = Cast<ASOEnemy>(GetPawn());
	ASOCombatCharacter* Source = Cast<ASOCombatCharacter>(NoiseInstigator);
	if (World != GetWorld() || !Me || Me->IsDead() || !Source || Source->IsDead() || !USOCombatStatics::AreHostile(Me, Source))
	{
		return;
	}
	const float Dist = FVector::Dist(Location, Me->GetActorLocation());
	if (Dist > Radius)
	{
		return;
	}
	// a gunshot (a big radius) brings it straight into the fight; footsteps make it wonder
	const bool bShot = Radius >= 2500.0f;
	Stimulus = Location;
	LastStimulusTime = World->GetTimeSeconds();
	if (bShot)
	{
		Awareness = 1.0f;
		if (!bInCombat)
		{
			EnterCombat(Source, true);
		}
		LastKnownLocation = Location;
		LastSeenTime = FMath::Max(LastSeenTime, World->GetTimeSeconds() - LoseTargetTime * 0.5f);
	}
	else
	{
		Awareness = FMath::Min(1.0f, Awareness + 0.35f * (1.0f - Dist / Radius) + 0.1f);
	}
}

bool ASOEnemyAIController::Notices(const AActor* Mate) const
{
	const ASOEnemy* Me = Cast<ASOEnemy>(GetPawn());
	if (!Me || !Mate || Mate == Me)
	{
		return false;
	}
	const FVector To = Mate->GetActorLocation() - Me->GetActorLocation();
	const float Dist = static_cast<float>(To.Size());
	if (Dist < MateFeelRadius)
	{
		return true;                                              // close by: the cry, the body going down
	}
	// further off: only what it is looking toward, with nothing in between
	return Dist < Me->SightRange * 1.25f
		&& FVector::DotProduct(Me->GetActorForwardVector().GetSafeNormal2D(), To.GetSafeNormal2D()) >= FMath::Cos(FMath::DegreesToRadians(PeripheralHalfAngle))
		&& Clear(GetWorld(), Me->GetPawnViewLocation(), Mate->GetActorLocation() + FVector(0, 0, 50.0f), Me, Mate);
}

void ASOEnemyAIController::OnHit(ASOCombatCharacter* Victim, AActor* Source, float Amount, UWorld* World)
{
	ASOEnemy* Me = Cast<ASOEnemy>(GetPawn());
	ASOCombatCharacter* Shooter = Cast<ASOCombatCharacter>(Source);
	if (World != GetWorld() || !Me || Me->IsDead() || !Victim || !Shooter || Shooter->IsDead() || !USOCombatStatics::AreHostile(Me, Shooter)
		|| USOCombatStatics::AreHostile(Me, Victim))
	{
		return;
	}
	if (Victim == Me)
	{
		// It is the one hit: it knows it is in a fight and roughly where the shot came from, from any distance.
		LastHurtTime = World->GetTimeSeconds();
		if (!bInCombat)
		{
			EnterCombat(Shooter, true);
			LastSeenTime = FMath::Max(LastSeenTime, World->GetTimeSeconds() - LoseTargetTime * 0.5f);
		}
		return;
	}
	// A mate was hit (or went down): whoever is close enough to feel it, or is looking that way, is warned. They in
	// turn are seen reacting by the next (EnterCombat), so it runs through a group in a second or two and stops where
	// nobody sees anybody.
	if (!bInCombat && Notices(Victim))
	{
		Alert(Shooter, Shooter->GetActorLocation());
	}
}

void ASOEnemyAIController::OnDied(ASOCombatCharacter* Victim, AActor* Killer, UWorld* World)
{
	OnHit(Victim, Killer, -1.0f, World);                          // (a kill in one shot is still a mate going down in front of them)
}

float ASOEnemyAIController::SightRate(const ASOCombatCharacter* Other) const
{
	const ASOEnemy* Me = Cast<ASOEnemy>(GetPawn());
	if (!Me || !Other)
	{
		return 0.0f;
	}
	const ASOCharacter* Player = Cast<ASOCharacter>(Other);
	const bool bLit = Player && Player->IsFlashlightOn();
	const FVector Eye = Me->GetPawnViewLocation();
	const FVector To = Other->GetActorLocation() + FVector(0, 0, 50.0f) - Eye;
	const float Dist = To.Size();
	const float Range = Me->SightRange * (bLit ? 1.6f : 1.0f);
	if (Dist > Range)
	{
		return 0.0f;
	}
	const float Cos = FVector::DotProduct(Me->GetActorForwardVector().GetSafeNormal2D(), To.GetSafeNormal2D());
	float Angle = 0.0f; // 1 = straight in view, a share for the sides, 0 = behind
	if (Cos >= FMath::Cos(FMath::DegreesToRadians(ViewHalfAngle)))
	{
		Angle = 1.0f;
	}
	else if (Cos >= FMath::Cos(FMath::DegreesToRadians(PeripheralHalfAngle)))
	{
		Angle = bLit ? 0.8f : 0.3f;
	}
	else if (bLit)
	{
		Angle = 0.35f; // a light is seen in the corner of the eye, the way it throws on the walls
	}
	if (Angle <= 0.0f || !CanSee(Other))
	{
		return 0.0f;
	}
	float Rate = 2.2f * (1.0f - 0.75f * Dist / Range) * Angle;
	if (Player)
	{
		if (Player->bIsCrouched)
		{
			Rate *= 0.45f;
		}
		if (const USOCharacterMovementComponent* Move = Cast<USOCharacterMovementComponent>(Player->GetCharacterMovement()); Move && Move->IsSprinting())
		{
			Rate *= 1.4f;
		}
	}
	if (Dist < AwareRadius && Angle >= 1.0f)
	{
		Rate = 50.0f; // right in front of it
	}
	return Rate;
}

bool ASOEnemyAIController::CanSee(const AActor* Other) const
{
	const ASOEnemy* Me = Cast<ASOEnemy>(GetPawn());
	return Me && Other && Clear(GetWorld(), Me->GetPawnViewLocation(), Other->GetActorLocation() + FVector(0, 0, 50.0f), Me, Other);
}

ASOCombatCharacter* ASOEnemyAIController::Perceive(float Dt)
{
	const ASOEnemy* Me = Cast<ASOEnemy>(GetPawn());
	ASOCombatCharacter* Best = nullptr;
	float BestRate = 0.0f;
	for (TActorIterator<ASOCombatCharacter> It(GetWorld()); It; ++It)
	{
		ASOCombatCharacter* Other = *It;
		if (Other == Me || Other->IsDead() || !USOCombatStatics::AreHostile(Me, Other))
		{
			continue;
		}
		const float Rate = SightRate(Other);
		if (Rate > BestRate)
		{
			BestRate = Rate;
			Best = Other;
		}
	}
	if (Best)
	{
		Awareness = FMath::Min(1.0f, Awareness + BestRate * Dt);
		Stimulus = Best->GetActorLocation();
		LastStimulusTime = Now(this);
	}
	else if (!bInCombat)
	{
		Awareness = FMath::Max(0.0f, Awareness - 0.12f * Dt);
	}
	return Best;
}

ASOCombatCharacter* ASOEnemyAIController::NearestPlayer() const
{
	const APawn* Me = GetPawn();
	ASOCombatCharacter* Best = nullptr;
	float BestD = BIG_NUMBER;
	for (TActorIterator<ASOCombatCharacter> It(GetWorld()); It; ++It)
	{
		const float D = FVector::DistSquared(It->GetActorLocation(), Me->GetActorLocation()) * (It->IsPlayerControlled() ? 1.0f : 4.0f);
		if (*It != Me && !It->IsDead() && (It->IsPlayerControlled() || It->Faction == ESOFaction::Player) && USOCombatStatics::AreHostile(Me, *It) && D < BestD)
		{
			BestD = D;
			Best = *It;
		}
	}
	return Best;
}

// ------------------------------------------------------------------ states

void ASOEnemyAIController::EnterCombat(ASOCombatCharacter* Other, bool bCryOut)
{
	ASOEnemy* Me = Cast<ASOEnemy>(GetPawn());
	if (!Me || !Other)
	{
		return;
	}
	const bool bWasCalm = !bInCombat;
	bInCombat = true;
	Awareness = 1.0f;
	Target = Other;
	LastKnownLocation = Other->GetActorLocation();
	Me->SetAlert(true);
	bHasCover = false;
	NextCoverSearch = 0.0f;
	if (bWasCalm)
	{
		if (bCryOut)
		{
			Me->Voice(TEXT("alert"), 1.0f);
		}
		// The squad joins: everyone in earshot when it cries out; when it only turns and raises its gun, whoever
		// sees it do that (or stands beside it). Each of those is seen in turn, a beat later.
		for (TActorIterator<ASOEnemy> It(GetWorld()); It; ++It)
		{
			if (*It == Me || It->IsDead())
			{
				continue;
			}
			ASOEnemyAIController* Mate = Cast<ASOEnemyAIController>(It->GetController());
			if (Mate && ((bCryOut && FVector::Dist(It->GetActorLocation(), Me->GetActorLocation()) < AlertRadius) || Mate->Notices(Me)))
			{
				Mate->Alert(Other, LastKnownLocation);
			}
		}
	}
}

void ASOEnemyAIController::Alert(ASOCombatCharacter* Other, const FVector& At)
{
	if (bInCombat || !Other || PendingAlertAt >= 0.0f)
	{
		return;
	}
	PendingAlertTarget = Other;
	PendingAlertLocation = At;
	PendingAlertAt = Now(this) + FMath::FRandRange(0.3f, 0.9f);
}

void ASOEnemyAIController::LeaveCombat()
{
	ASOEnemy* Me = Cast<ASOEnemy>(GetPawn());
	bInCombat = false;
	Target = nullptr;
	Awareness = 0.45f;
	bHasCover = false;
	bRetreating = bPushing = false;
	if (Me)
	{
		Me->SetAimTarget(nullptr);
		Me->SetWantsFire(false);
		Me->SetRunning(false);
	}
	ClearFocus(EAIFocusPriority::Gameplay);
	State = ESOEnemyState::Suspicious;
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
			Me->SetAimTarget(nullptr);
		}
		return;
	}
	// Without a nav path the chase steers straight at the target every frame.
	if (bDirectChase && Target.IsValid() && !Me->IsAttacking())
	{
		const FVector To = (Target->GetActorLocation() - Me->GetActorLocation()).GetSafeNormal2D();
		Me->AddMovementInput(To, 1.0f);
	}
	CheckStuck(DeltaSeconds);
	const float T = GetWorld()->GetTimeSeconds();
	if (T >= NextThink)
	{
		NextThink = T + ThinkInterval;
		Think();
	}
}

void ASOEnemyAIController::Think()
{
	ASOEnemy* Me = Cast<ASOEnemy>(GetPawn());
	const float T = Now(this);
	const float Dt = FMath::Clamp(T - LastThink, 0.0f, 0.5f);
	LastThink = T;

	if (ASOCombatCharacter* Current = Target.Get(); Current && Current->IsDead())
	{
		LeaveCombat();
	}
	// hurt: it knows
	const float Health = Me->GetHealth();
	if (LastHealth >= 0.0f && Health < LastHealth - 0.5f)
	{
		LastHurtTime = T;
		if (!bInCombat)
		{
			Me->SetAlert(true);
			if (ASOCombatCharacter* Who = NearestPlayer())
			{
				EnterCombat(Who, true);
			}
		}
	}
	LastHealth = Health;
	if (PendingAlertAt >= 0.0f && T >= PendingAlertAt)
	{
		PendingAlertAt = -1.0f;
			if (ASOCombatCharacter* Who = PendingAlertTarget.Get(); Who && !Who->IsDead() && !bInCombat)
		{
			EnterCombat(Who, false);
			LastKnownLocation = PendingAlertLocation;
			// (warned, not yet seeing it: it takes cover from that way and looks, before it goes searching)
			LastSeenTime = FMath::Max(LastSeenTime, T - LoseTargetTime * 0.5f);
		}
	}

	ASOCombatCharacter* Seen = Perceive(Dt);
	if (bHunter && !bInCombat)
	{
		if (ASOCombatCharacter* Who = NearestPlayer())
		{
			EnterCombat(Who, false);
		}
	}
	if (!bInCombat && Awareness >= 1.0f && Seen)
	{
		EnterCombat(Seen, true);
	}
	if (bInCombat)
	{
		if (Seen && Seen == Target.Get())
		{
			LastSeenTime = T;
			LastKnownLocation = Seen->GetActorLocation();
		}
		else if (bHunter && Target.IsValid())
		{
			// a hunter knows where its prey is: it does not see it through a wall (no aiming or firing at one)
			LastKnownLocation = Target->GetActorLocation();
		}
		ThinkCombat();
		return;
	}
	ThinkUnaware();
}

void ASOEnemyAIController::ThinkUnaware()
{
	ASOEnemy* Me = Cast<ASOEnemy>(GetPawn());
	const float T = Now(this);
	Me->SetAimTarget(nullptr);
	Me->SetRunning(false);
	bDirectChase = false;
	if (Awareness > 0.3f && T - LastStimulusTime < 8.0f)
	{
		// something is there: look at it, edge closer, mutter
		if (State != ESOEnemyState::Suspicious || T >= NextQueryVoice)
		{
			if (T >= NextQueryVoice)
			{
				Me->Voice(TEXT("query"), 0.9f);
				NextQueryVoice = T + FMath::FRandRange(4.0f, 7.0f);
			}
		}
		State = ESOEnemyState::Suspicious;
		SetFocalPoint(Stimulus, EAIFocusPriority::Gameplay);
		if (FVector::Dist2D(Stimulus, Me->GetActorLocation()) > 450.0f)
		{
			MoveToLocation(Stimulus, 350.0f);
		}
		else
		{
			StopMovement();
		}
		return;
	}
	ClearFocus(EAIFocusPriority::Gameplay);
	Wander();
}

void ASOEnemyAIController::ThinkCombat()
{
	ASOEnemy* Me = Cast<ASOEnemy>(GetPawn());
	ASOCombatCharacter* Foe = Target.Get();
	const float T = Now(this);
	if (!Foe)
	{
		LeaveCombat();
		return;
	}
	const bool bVisible = T - LastSeenTime < 0.6f;
	// lost it: search where it was last seen, then calm down
	if (!bHunter && T - LastSeenTime > LoseTargetTime)
	{
		if (State != ESOEnemyState::Search)
		{
			State = ESOEnemyState::Search;
			SearchUntil = T + SearchTime;
			Me->SetAimTarget(nullptr);
			Me->SetWantsFire(false);
			MoveToLocation(LastKnownLocation, 150.0f);
			SetFocalPoint(LastKnownLocation, EAIFocusPriority::Gameplay);
		}
		else if (T >= SearchUntil)
		{
			LeaveCombat();
		}
		else if (GetMoveStatus() == EPathFollowingStatus::Idle && T >= NextWander)
		{
			// look round the last place
			NextWander = T + FMath::FRandRange(1.5f, 3.0f);
			FNavLocation P;
			if (UNavigationSystemV1* Nav = NavOf(GetWorld()); Nav && Nav->GetRandomReachablePointInRadius(LastKnownLocation, 600.0f, P))
			{
				MoveToLocation(P.Location, 50.0f);
				SetFocalPoint(P.Location + (P.Location - LastKnownLocation), EAIFocusPriority::Gameplay);
			}
		}
		return;
	}
	Me->SetRunning(true);
	Me->SetAimTarget(bVisible || T - LastSeenTime < 1.5f ? Foe : nullptr);
	if (bVisible)
	{
		SetFocus(Foe, EAIFocusPriority::Gameplay);
	}
	else
	{
		SetFocalPoint(LastKnownLocation, EAIFocusPriority::Gameplay);
	}
	// a creature's own fighting first (specials: cast, slam, the boss)
	if (Me->ThinkCombat(this, Foe))
	{
		State = ESOEnemyState::Attack;
		bDirectChase = false;
		return;
	}
	const float Dist = Me->DistanceTo(Foe);
	const bool bArmed = Me->IsArmed();
	// It does not stand there: hit out in the open, or with a gun levelled at it, it steps aside (a cover-user then
	// looks for new cover). A step it has started is finished before the next plan.
	const bool bExposed = !bHasCover || bPeeking || State == ESOEnemyState::Cover;
	if (bVisible && bExposed && T >= NextDodge && Dist > Me->MeleeRange * 1.6f && !Me->IsAttacking()
		&& (T - LastHurtTime < 0.35f || (Dist < 3200.0f && AimedAt(Foe))))
	{
		NextDodge = T + FMath::FRandRange(bArmed ? 2.2f : 1.4f, bArmed ? 4.0f : 2.6f);
		if (Sidestep(Foe))
		{
			++Dodges;
			MoveCommitUntil = T + (bArmed ? 0.7f : 0.45f);
			if (Me->bUsesCover)
			{
				bHasCover = false;
				NextCoverSearch = MoveCommitUntil;
			}
		}
	}
	// badly hurt: fall back (cover further off, longer behind it), and say so
	const float Left = Health01(Me);
	if (bArmed && Me->bUsesCover && !bRetreating && Left < 0.34f)
	{
		bRetreating = true;
		bHasCover = false;
		NextCoverSearch = 0.0f;
		Me->Voice(TEXT("hurt"), 1.0f);
	}
	if (T < MoveCommitUntil)
	{
		Me->SetWantsFire(bArmed && Me->HasLineOfFire(Foe));
		return;
	}
	if (!bArmed)
	{
		// claws: come in round its side, then strike
		Me->SetWantsFire(false);
		if (Dist <= Me->MeleeRange)
		{
			State = ESOEnemyState::Attack;
			StopMovement();
			bDirectChase = false;
			Me->TryAttack(Foe);
			return;
		}
		State = ESOEnemyState::Chase;
		if (Dist > 650.0f && NavOf(GetWorld()))
		{
			// not down the line of its gun: a point off to this one's side of the target, closing as it nears
			if (T >= NextRepath)
			{
				NextRepath = T + 0.35f;
				const FVector To = (Foe->GetActorLocation() - Me->GetActorLocation()).GetSafeNormal2D();
				const FVector Off = FVector::CrossProduct(FVector::UpVector, To) * SideBias * FMath::Min(Dist * 0.45f, 520.0f);
				FNavLocation P;
				if (NavOf(GetWorld())->ProjectPointToNavigation(Foe->GetActorLocation() + Off, P, FVector(200.0f, 200.0f, 400.0f))
					&& MoveToLocation(P.Location, 60.0f, true, true, false, true) != EPathFollowingRequestResult::Failed)
				{
					bUsedNav = true;
					bDirectChase = false;
				}
				else
				{
					ChaseTarget();
				}
			}
			return;
		}
		ChaseTarget();
		return;
	}
	if (Dist <= Me->MeleeRange && Me->MeleeDamage > 0.0f)
	{
		Me->TryAttack(Foe); // too close: a strike with the stock or the claws
	}
	// The target went out of sight: the squad does not wait for it to come back. Half push to where it was (at once
	// if they have no cover to give up), the rest hold a little, then follow.
	const float Blind = T - LastSeenTime;
	const float Patience = bRetreating ? 9.0f : ((Me->GetUniqueID() % 2) == 0 || bFlanker ? 2.4f : 5.2f);
	bPushing = Blind > Patience && FVector::Dist2D(Me->GetActorLocation(), LastKnownLocation) > 350.0f;
	if (bPushing)
	{
		Push();
		return;
	}
	if (Me->bUsesCover)
	{
		ThinkCoverFight(Dist);
	}
	else
	{
		ThinkAssault(Dist);
	}
}

bool ASOEnemyAIController::AimedAt(const ASOCombatCharacter* Foe) const
{
	const APawn* Me = GetPawn();
	if (!Me || !Foe || !Foe->IsPlayerControlled())
	{
		return false;
	}
	const FVector To = Me->GetActorLocation() - Foe->GetPawnViewLocation();
	const float Dist = static_cast<float>(To.Size());
	return Dist > 1.0f && FVector::DotProduct(Foe->GetBaseAimRotation().Vector(), To / Dist) > FMath::Cos(FMath::DegreesToRadians(Dist < 900.0f ? 8.0f : 4.5f));
}

bool ASOEnemyAIController::Sidestep(const ASOCombatCharacter* Foe)
{
	ASOEnemy* Me = Cast<ASOEnemy>(GetPawn());
	UNavigationSystemV1* Nav = NavOf(GetWorld());
	if (!Me || !Foe || !Nav)
	{
		return false;
	}
	const FVector To = (Foe->GetActorLocation() - Me->GetActorLocation()).GetSafeNormal2D();
	const FVector Across = FVector::CrossProduct(FVector::UpVector, To);
	const float Dist = Me->DistanceTo(Foe);
	const float First = FMath::RandBool() ? 1.0f : -1.0f;
	for (const float Side : { First, -First })
	{
		const FVector Want = Me->GetActorLocation() + Across * Side * FMath::FRandRange(230.0f, 380.0f) - (Dist < Me->PreferredRange * 0.5f ? To * 220.0f : FVector::ZeroVector);
		FNavLocation P;
		// (a step it can take: on the nav mesh, and nothing between here and there)
		if (Nav->ProjectPointToNavigation(Want, P, FVector(90.0f, 90.0f, 250.0f))
			&& Clear(GetWorld(), Me->GetActorLocation(), P.Location + FVector(0, 0, Me->GetCapsuleComponent()->GetScaledCapsuleHalfHeight()), Me, Foe)
			&& MoveToLocation(P.Location, 20.0f, false, true, false, true) != EPathFollowingRequestResult::Failed)
		{
			bDirectChase = false;
			return true;
		}
	}
	return false;
}

void ASOEnemyAIController::Push()
{
	ASOEnemy* Me = Cast<ASOEnemy>(GetPawn());
	ASOCombatCharacter* Foe = Target.Get();
	const float T = Now(this);
	State = ESOEnemyState::Chase;
	bHasCover = false;
	Me->SetWantsFire(Me->HasLineOfFire(Foe));
	if (T < NextRepath)
	{
		return;
	}
	NextRepath = T + 0.6f;
	FVector Goal = LastKnownLocation;
	UNavigationSystemV1* Nav = NavOf(GetWorld());
	if (bFlanker && Nav)
	{
		// round its side: a point across the line it was last seen on
		const FVector To = (LastKnownLocation - Me->GetActorLocation()).GetSafeNormal2D();
		FNavLocation P;
		if (Nav->ProjectPointToNavigation(LastKnownLocation + FVector::CrossProduct(FVector::UpVector, To) * SideBias * 700.0f, P, FVector(250.0f, 250.0f, 400.0f)))
		{
			Goal = P.Location;
		}
	}
	const EPathFollowingRequestResult::Type Result = MoveToLocation(Goal, FMath::Max(Me->PreferredRange * 0.3f, 250.0f), true, true, true, true);
	bUsedNav |= Result != EPathFollowingRequestResult::Failed;
	bDirectChase = false;
}

void ASOEnemyAIController::ThinkCoverFight(float Dist)
{
	ASOEnemy* Me = Cast<ASOEnemy>(GetPawn());
	ASOCombatCharacter* Foe = Target.Get();
	const float T = Now(this);
	const FVector ThreatEye = Foe->GetActorLocation() + FVector(0, 0, 60.0f);
	const float Half = Me->GetCapsuleComponent()->GetScaledCapsuleHalfHeight();
	// is the cover still cover? (flanked: the target sees the hiding spot)
	if (bHasCover && Clear(GetWorld(), CoverPoint + FVector(0, 0, 30.0f), ThreatEye, Me, Foe))
	{
		bHasCover = false;
	}
	if (!bHasCover && T >= NextCoverSearch)
	{
		NextCoverSearch = T + 1.5f;
		FVector P, Peek;
		if (FindCover(ThreatEye, P, Peek))
		{
			bHasCover = true;
			CoverPoint = P + FVector(0, 0, Half);
			PeekPoint = Peek + FVector(0, 0, Half);
			CoverTaken = T;
			bPeeking = false;
			MoveToLocation(P, 30.0f);
			State = ESOEnemyState::Cover;
		}
	}
	if (!bHasCover)
	{
		ThinkAssault(Dist); // nowhere to hide: fight in the open
		return;
	}
	const bool bThere = FVector::Dist2D(Me->GetActorLocation(), bPeeking ? PeekPoint : CoverPoint) < 70.0f;
	if (State == ESOEnemyState::Cover && !bThere)
	{
		// moving to cover: it runs for it. It fires on the way only at something right on top of it (the owner: "they
		// should ... move from cover to cover then sneak and shoot not just stay in the open or run straight at the user")
		Me->SetWantsFire(Dist < 700.0f && Me->HasLineOfFire(Foe));
		return;
	}
	State = ESOEnemyState::Fight;
	// held long enough: move on to another spot (keeps the fight moving, and the flankers swing wider). Still far
	// from the range it likes, it holds only a few bursts before the next bound.
	const bool bFar = !bRetreating && Dist > Me->PreferredRange * RangeBias * 1.2f;
	if (T - CoverTaken > (bFar ? FMath::FRandRange(3.0f, 5.5f) : FMath::FRandRange(9.0f, 15.0f)))
	{
		bHasCover = false;
		NextCoverSearch = T;
		return;
	}
	if (T >= PhaseUntil)
	{
		bPeeking = !bPeeking;
		PhaseUntil = T + (bPeeking ? FMath::FRandRange(1.4f, 3.0f) : FMath::FRandRange(0.8f, 2.2f) * (bRetreating ? 2.2f : 1.0f));
		MoveToLocation(bPeeking ? PeekPoint - FVector(0, 0, Half) : CoverPoint - FVector(0, 0, Half), 20.0f, false, true, false, true);
	}
	Me->SetWantsFire(bPeeking && Me->HasLineOfFire(Foe));
}

void ASOEnemyAIController::ThinkAssault(float Dist)
{
	ASOEnemy* Me = Cast<ASOEnemy>(GetPawn());
	ASOCombatCharacter* Foe = Target.Get();
	const float T = Now(this);
	const bool bLine = Me->HasLineOfFire(Foe);
	Me->SetWantsFire(bLine);
	State = ESOEnemyState::Chase;
	const float Range = Me->PreferredRange * RangeBias;
	if (Dist > Range || !bLine)
	{
		// Close in (to a line of fire, then the range it likes: each its own, so a squad is not a clump), but not
		// down the line of the gun pointed at it: to a point at that range off to this one's side of the target, so
		// it comes round in an arc and stops there.
		EPathFollowingRequestResult::Type R = EPathFollowingRequestResult::Failed;
		if (UNavigationSystemV1* Nav = NavOf(GetWorld()); Nav && Me->bUsesCover)
		{
			if (T < NextRepath)
			{
				return;
			}
			NextRepath = T + 0.8f;
			const FVector Away = (Me->GetActorLocation() - Foe->GetActorLocation()).GetSafeNormal2D();
			const FVector Stand = Foe->GetActorLocation() + Away.RotateAngleAxis(SideBias * 38.0f, FVector::UpVector) * Range * 0.9f;
			FNavLocation P;
			if (Nav->ProjectPointToNavigation(Stand, P, FVector(250.0f, 250.0f, 400.0f)))
			{
				R = MoveToLocation(P.Location, 60.0f, true, true, false, true);
				Me->SetWantsFire(bLine && Dist < Range * 1.3f);     // (it shoots once it is nearly there, not the whole way in)
			}
		}
		if (R == EPathFollowingRequestResult::Failed)
		{
			R = MoveToActor(Foe, FMath::Max(Range * 0.7f, Me->MeleeRange * 0.5f), true, true, true, nullptr, true);
		}
		bUsedNav |= R != EPathFollowingRequestResult::Failed;
		bDirectChase = R == EPathFollowingRequestResult::Failed;
		return;
	}
	bDirectChase = false;
	// at range: side-step now and then so it is not a still target
	if (T >= NextStrafe)
	{
		NextStrafe = T + FMath::FRandRange(1.2f, 2.6f);
		const FVector To = (Foe->GetActorLocation() - Me->GetActorLocation()).GetSafeNormal2D();
		const FVector SideV = FVector::CrossProduct(FVector::UpVector, To) * (FMath::RandBool() ? 1.0f : -1.0f);
		FNavLocation P;
		UNavigationSystemV1* Nav = NavOf(GetWorld());
		const FVector Want = Me->GetActorLocation() + SideV * FMath::FRandRange(250.0f, 450.0f) - (Dist < Me->PreferredRange * 0.5f ? To * 300.0f : FVector::ZeroVector);
		if (Nav && Nav->ProjectPointToNavigation(Want, P, FVector(150.0f, 150.0f, 300.0f)))
		{
			MoveToLocation(P.Location, 30.0f, false, true, false, true);
		}
	}
}

// ------------------------------------------------------------------ cover

bool ASOEnemyAIController::FindCover(const FVector& ThreatEye, FVector& OutPoint, FVector& OutPeek) const
{
	const ASOEnemy* Me = Cast<ASOEnemy>(GetPawn());
	UWorld* World = GetWorld();
	UNavigationSystemV1* Nav = NavOf(World);
	if (!Me || !Nav)
	{
		return false;
	}
	const AActor* Foe = Target.Get();
	const FVector From = Me->GetActorLocation();
	const FVector ThreatFwd = Foe ? Foe->GetActorForwardVector().GetSafeNormal2D() : FVector::ZeroVector;
	float BestScore = -BIG_NUMBER;
	bool bFound = false;
	const float Phase = FMath::FRand() * UE_TWO_PI;
	for (const float R : { 350.0f, 700.0f, 1100.0f, 1500.0f })
	{
		for (int32 i = 0; i < 12; ++i)
		{
			const float A = Phase + UE_TWO_PI * i / 12.0f;
			FNavLocation N;
			if (!Nav->ProjectPointToNavigation(From + FVector(FMath::Cos(A), FMath::Sin(A), 0.0f) * R, N, FVector(150.0f, 150.0f, 400.0f)))
			{
				continue;
			}
			const FVector Floor = N.Location;
			const float ToThreat = FVector::Dist2D(Floor, ThreatEye);
			const float Liked = Me->PreferredRange * RangeBias * (bRetreating ? 1.6f : 1.0f);
			// (far from the range it likes it works its way in: any spot nearer the target than it stands now will do,
			// so a fight that starts at eighty metres is closed bound by bound, not in one run down the street)
			const float Here = static_cast<float>(FVector::Dist2D(From, ThreatEye));
			const bool bAdvance = !bRetreating && Here > Liked * 1.2f;
			if (ToThreat < (bRetreating ? 900.0f : 450.0f)
				|| ToThreat > FMath::Max(Me->PreferredRange * (bRetreating ? 3.0f : 2.0f), bAdvance ? Here - 150.0f : 0.0f))
			{
				continue;
			}
			// hidden: the threat sees neither its chest nor its hips there
			if (Clear(World, Floor + FVector(0, 0, 120.0f), ThreatEye, Me, Foe) || Clear(World, Floor + FVector(0, 0, 60.0f), ThreatEye, Me, Foe))
			{
				continue;
			}
			// a peek: a step to the side with a clear shot, or a line over the top
			const FVector Across = FVector::CrossProduct(FVector::UpVector, (ThreatEye - Floor).GetSafeNormal2D());
			FVector Peek = Floor;
			bool bPeek = Clear(World, Floor + FVector(0, 0, 165.0f), ThreatEye, Me, Foe);
			for (const float S : { 1.0f, -1.0f })
			{
				for (const float D : { 90.0f, 140.0f })
				{
					if (bPeek)
					{
						break;
					}
					FNavLocation PN;
					if (Nav->ProjectPointToNavigation(Floor + Across * S * D, PN, FVector(60.0f, 60.0f, 200.0f))
						&& Clear(World, PN.Location + FVector(0, 0, 150.0f), ThreatEye, Me, Foe))
					{
						bPeek = true;
						Peek = PN.Location;
					}
				}
			}
			float Score = 6.0f - FMath::Min(FMath::Abs(ToThreat - Liked) / 800.0f, 6.0f) - FVector::Dist2D(Floor, From) / 700.0f + (bPeek ? 3.0f : -1.5f);
			if (bAdvance)
			{
				Score += FMath::Clamp((Here - ToThreat) / 500.0f, -2.0f, 3.0f);     // ground made toward it
			}
			// falling back: away from the threat, not across its sights
			if (bRetreating && FVector::Dist2D(From, ThreatEye) > ToThreat)
			{
				Score -= 4.0f;
			}
			// flankers like spots off to the side of where the target looks
			if (bFlanker && !ThreatFwd.IsNearlyZero())
			{
				const float Off = FVector::DotProduct(ThreatFwd, (Floor - ThreatEye).GetSafeNormal2D());
				Score += (1.0f - FMath::Abs(Off)) * 3.0f;
			}
			// not a spot a squad mate holds
			for (TActorIterator<ASOEnemy> It(World); It; ++It)
			{
				if (*It == Me || It->IsDead())
				{
					continue;
				}
				FVector Theirs;
				if (const ASOEnemyAIController* Mate = Cast<ASOEnemyAIController>(It->GetController()); Mate && Mate->GetCover(Theirs)
					&& FVector::Dist2D(Theirs, Floor) < 250.0f)
				{
					Score -= 5.0f;
				}
				if (FVector::Dist2D(It->GetActorLocation(), Floor) < 120.0f)
				{
					Score -= 3.0f;
				}
			}
			if (Score > BestScore)
			{
				BestScore = Score;
				OutPoint = Floor;
				OutPeek = Peek;
				bFound = true;
			}
		}
	}
	return bFound;
}

// ------------------------------------------------------------------ moving

void ASOEnemyAIController::ChaseTarget()
{
	ASOEnemy* Me = Cast<ASOEnemy>(GetPawn());
	if (NavOf(GetWorld()))
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
	const float T = Now(this);
	State = ESOEnemyState::Wander;
	if (T < NextWander)
	{
		return;
	}
	NextWander = T + FMath::FRandRange(4.0f, 9.0f);
	FNavLocation Point;
	UNavigationSystemV1* Nav = NavOf(GetWorld());
	if (Nav && FMath::FRand() < 0.6f && Nav->GetRandomReachablePointInRadius(Home, WanderRadius, Point))
	{
		MoveToLocation(Point.Location, 50.0f);
	}
	else
	{
		State = ESOEnemyState::Idle; // stands its post and looks round
		if (APawn* Me = GetPawn())
		{
			SetFocalPoint(Me->GetActorLocation() + FRotator(0.0f, FMath::FRandRange(-180.0f, 180.0f), 0.0f).Vector() * 500.0f, EAIFocusPriority::Gameplay);
		}
	}
}

bool ASOEnemyAIController::Rescue()
{
	ASOEnemy* Me = Cast<ASOEnemy>(GetPawn());
	UNavigationSystemV1* Nav = NavOf(GetWorld());
	FNavLocation P;
	if (!Me || !Nav || !Nav->ProjectPointToNavigation(Me->GetActorLocation(), P, FVector(400.0f, 400.0f, 600.0f)))
	{
		return false;
	}
	const float Half = Me->GetCapsuleComponent()->GetScaledCapsuleHalfHeight();
	for (int32 Try = 0; Try < 8; ++Try)
	{
		FNavLocation Around = P;
		if (Try > 0 && !Nav->GetRandomReachablePointInRadius(P.Location, 150.0f + 80.0f * Try, Around))
		{
			continue;
		}
		const FVector Free = Around.Location + FVector(0, 0, Half + 2.0f);
		if (Me->FitsAt(Free) && Me->TeleportTo(Free, Me->GetActorRotation(), false, true))
		{
			return true;
		}
	}
	return false;
}

void ASOEnemyAIController::CheckStuck(float DeltaSeconds)
{
	APawn* Me = GetPawn();
	// standing in the world (pushed, spawned badly, a blink gone wrong): back onto free ground, whatever it is doing
	if (Me && Now(this) >= NextFitCheck)
	{
		NextFitCheck = Now(this) + 1.0f;
		if (Me->GetWorld()->EncroachingBlockingGeometry(Me, Me->GetActorLocation(), Me->GetActorRotation()) && Rescue())
		{
			StopMovement();
			bHasCover = false;
			bDirectChase = false;
			return;
		}
	}
	const bool bMoving = GetMoveStatus() == EPathFollowingStatus::Moving || bDirectChase;
	if (!Me || !bMoving)
	{
		StuckTimer = 0.0f;
		StuckCheckFrom = Me ? Me->GetActorLocation() : FVector::ZeroVector;
		return;
	}
	StuckTimer += DeltaSeconds;
	if (StuckTimer < 1.5f)
	{
		return;
	}
	const bool bStuck = FVector::Dist2D(Me->GetActorLocation(), StuckCheckFrom) < 30.0f;
	StuckTimer = 0.0f;
	StuckCheckFrom = Me->GetActorLocation();
	if (!bStuck)
	{
		return;
	}
	// wedged: step onto free nav ground nearby (out of a wall if it is in one), and drop the plan that wedged it
	UNavigationSystemV1* Nav = NavOf(GetWorld());
	FNavLocation P;
	if (Nav && Nav->ProjectPointToNavigation(Me->GetActorLocation(), P, FVector(250.0f, 250.0f, 400.0f)))
	{
		const float Half = Me->FindComponentByClass<UCapsuleComponent>()->GetScaledCapsuleHalfHeight();
		FVector Free = P.Location + FVector(0, 0, Half + 2.0f);
		FNavLocation Around;
		if (Nav->GetRandomReachablePointInRadius(P.Location, 300.0f, Around))
		{
			Free = Around.Location + FVector(0, 0, Half + 2.0f);
		}
		MoveToLocation(Free - FVector(0, 0, Half), 30.0f);
	}
	bHasCover = false;
	bDirectChase = false;
}
