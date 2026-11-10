#include "SOEnemySpawner.h"

#include "Components/ArrowComponent.h"
#include "Engine/World.h"
#include "SOCombatStatics.h"
#include "SOEnemy.h"
#include "SOSpecies.h"
#include "TimerManager.h"

ASOEnemySpawner::ASOEnemySpawner()
{
	Arrow = CreateDefaultSubobject<UArrowComponent>(TEXT("Arrow"));
	Arrow->ArrowColor = FColor(180, 108, 255);
	Arrow->bIsScreenSizeScaled = true;
	RootComponent = Arrow;
	EnemyClass = ASOEnemy::StaticClass();
}

void ASOEnemySpawner::BeginPlay()
{
	Super::BeginPlay();
	if (!HasAuthority())
	{
		return;
	}
	DiedHandle = USOCombatStatics::OnCharacterDied().AddUObject(this, &ASOEnemySpawner::OnCharacterDied);
	if (bSpawnOnBeginPlay)
	{
		SpawnEnemy();
	}
}

void ASOEnemySpawner::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	USOCombatStatics::OnCharacterDied().Remove(DiedHandle);
	if (UWorld* World = GetWorld())
	{
		World->GetTimerManager().ClearTimer(RespawnTimer);
	}
	Super::EndPlay(EndPlayReason);
}

ASOEnemy* ASOEnemySpawner::SpawnEnemy()
{
	UWorld* World = GetWorld();
	// by species (the spawner's own, or the one its class names): the same creature as everywhere else
	const FName Kind = !Species.IsNone() ? Species : (EnemyClass ? EnemyClass->GetDefaultObject<ASOEnemy>()->SpeciesId : FName());
	if (!World || Kind.IsNone())
	{
		return nullptr;
	}
	FSOSpawnOptions Options;
	Options.bOnNav = false;                                      // exactly where the spawner stands
	Options.bNeedsRoom = false;
	ASOEnemy* Enemy = USOSpeciesLibrary::Spawn(World, Kind, GetActorLocation(), GetActorRotation().Yaw, Options);
	if (Enemy)
	{
		Current = Enemy;
		++SpawnCount;
	}
	return Enemy;
}

void ASOEnemySpawner::OnCharacterDied(ASOCombatCharacter* Victim, AActor* Killer, UWorld* World)
{
	if (World != GetWorld() || !Victim || Victim != Current.Get())
	{
		return;
	}
	Current = nullptr;
	FTimerDelegate Respawn = FTimerDelegate::CreateWeakLambda(this, [this]() { SpawnEnemy(); });
	World->GetTimerManager().SetTimer(RespawnTimer, Respawn, FMath::Max(RespawnDelay, 0.1f), false);
}
