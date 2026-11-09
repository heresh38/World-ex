#include "SOGameMode.h"

#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "SOCharacter.h"
#include "SOCombatStatics.h"
#include "SOHUD.h"
#include "SOOperation.h"
#include "SOLog.h"
#include "SOPlayerController.h"
#include "SOPlayerState.h"
#include "TimerManager.h"

ASOGameMode::ASOGameMode()
{
	DefaultPawnClass = ASOCharacter::StaticClass();
	PlayerControllerClass = ASOPlayerController::StaticClass();
	PlayerStateClass = ASOPlayerState::StaticClass();
	HUDClass = ASOHUD::StaticClass();
}

void ASOGameMode::StartPlay()
{
	Super::StartPlay();
	DiedHandle = USOCombatStatics::OnCharacterDied().AddUObject(this, &ASOGameMode::OnCharacterDied);
}

void ASOGameMode::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	USOCombatStatics::OnCharacterDied().Remove(DiedHandle);
	Super::EndPlay(EndPlayReason);
}

void ASOGameMode::OnCharacterDied(ASOCombatCharacter* Victim, AActor* Killer, UWorld* World)
{
	if (World != GetWorld() || !Victim)
	{
		return;
	}
	APlayerController* PC = Cast<APlayerController>(Victim->GetController());
	if (!PC)
	{
		return;
	}
	UE_LOG(LogShatteredOrbit, Log, TEXT("%s is down (by %s); redeploying in %.1f s"), *Victim->GetName(), Killer ? *Killer->GetName() : TEXT("?"), RespawnDelay);
	FTimerHandle Handle;
	TWeakObjectPtr<AController> WeakPC = PC;
	GetWorldTimerManager().SetTimer(Handle, FTimerDelegate::CreateWeakLambda(this, [this, WeakPC]()
	{
		if (AController* C = WeakPC.Get())
		{
			RespawnPlayer(C);
		}
	}), FMath::Max(RespawnDelay, 0.1f), false);
}

void ASOGameMode::RespawnPlayer(AController* Controller)
{
	if (!Controller)
	{
		return;
	}
	if (APawn* Old = Controller->GetPawn())
	{
		Old->DetachFromControllerPendingDestroy();
		Old->SetLifeSpan(BodyLifeSpan);
	}
	FTransform Checkpoint;
	if (const ASOOperation* Operation = ASOOperation::Get(this); Operation && Operation->GetCheckpoint(Checkpoint))
	{
		RestartPlayerAtTransform(Controller, Checkpoint);
		return;
	}
	RestartPlayer(Controller);
}
