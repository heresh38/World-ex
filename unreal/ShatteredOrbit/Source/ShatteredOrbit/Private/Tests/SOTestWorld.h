#pragma once

// Shared helpers for the automation tests: a transient game world ticked by hand.

#include "CoreMinimal.h"
#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "Components/BoxComponent.h"
#include "Engine/CollisionProfile.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/WorldSettings.h"
#include "SOCharacter.h"

namespace SOTest
{
	inline constexpr EAutomationTestFlags Flags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter;
	inline constexpr float Dt = 1.0f / 60.0f;

	/** A transient game world with a floor, ticked by hand. */
	struct FTestWorld
	{
		UWorld* World = nullptr;
		uint64 CachedFrameCounter = 0;

		FTestWorld()
		{
			CachedFrameCounter = GFrameCounter;
			World = UWorld::CreateWorld(EWorldType::Game, false, TEXT("SOTestWorld"));
			FWorldContext& Context = GEngine->CreateNewWorldContext(EWorldType::Game);
			Context.SetCurrentWorld(World);
			World->InitializeActorsForPlay(FURL());
			World->BeginPlay();
			World->GetWorldSettings()->NotifyBeginPlay();
		}

		~FTestWorld()
		{
			World->BeginTearingDown();
			World->EndPlay(EEndPlayReason::Quit);
			GFrameCounter = CachedFrameCounter;
			GEngine->DestroyWorldContext(World);
			World->DestroyWorld(false);
		}

		/** A static blocking box from Min to Max (world space). */
		AActor* AddBox(const FVector& Min, const FVector& Max)
		{
			AActor* Actor = World->SpawnActor<AActor>();
			UBoxComponent* Box = NewObject<UBoxComponent>(Actor);
			Box->SetBoxExtent((Max - Min) * 0.5f, false);
			Box->SetCollisionProfileName(UCollisionProfile::BlockAll_ProfileName);
			Actor->SetRootComponent(Box);
			Box->RegisterComponent();
			Box->SetWorldLocation((Min + Max) * 0.5f);
			return Actor;
		}

		ASOCharacter* SpawnCharacter(const FVector& FeetLocation)
		{
			FActorSpawnParameters Params;
			Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
			ASOCharacter* Character = World->SpawnActor<ASOCharacter>(FeetLocation + FVector(0, 0, 91.0f), FRotator::ZeroRotator, Params);
			if (Character)
			{
				Character->GetCharacterMovement()->bRunPhysicsWithNoController = true;
				Character->GetCharacterMovement()->SetMovementMode(MOVE_Falling);
			}
			return Character;
		}

		/** One frame. Tick functions run once per GFrameCounter value, so the counter advances like in a game. */
		void Step()
		{
			World->Tick(LEVELTICK_All, Dt);
			++GFrameCounter;
		}

		/** Ticks for Seconds; Input (if set) is applied before every frame. */
		void Run(float Seconds, TFunctionRef<void()> Input)
		{
			const int32 Frames = FMath::CeilToInt(Seconds / Dt);
			for (int32 i = 0; i < Frames; ++i)
			{
				Input();
				Step();
			}
		}

		void Run(float Seconds)
		{
			Run(Seconds, [] {});
		}
	};
}

#endif // WITH_DEV_AUTOMATION_TESTS
