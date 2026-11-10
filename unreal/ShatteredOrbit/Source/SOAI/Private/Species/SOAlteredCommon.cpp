#include "SOAltered.h"

#include "SOAlteredCommon.h"

#include "Components/CapsuleComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Materials/MaterialInterface.h"
#include "NavigationSystem.h"
#include "SOCombatCharacter.h"
#include "SOCombatStatics.h"
#include "SOEnemyAIController.h"
#include "SOFxSubsystem.h"
#include "SOLocomotionAnimInstance.h"
#include "UObject/ConstructorHelpers.h"
#include "SOSound.h"

// What the Altered share: their void colour and glow, the body set-up, small helpers, the void bolt's launch.
namespace SOAltered
{
	extern const FLinearColor VoidColor;
	const FLinearColor VoidColor(0.62f, 0.36f, 1.0f);
	extern const TCHAR* const GlowMaterial;
	const TCHAR* const GlowMaterial = TEXT("/Game/Environments/Meridian/MI_ru_glow.MI_ru_glow");

	/** Mesh, clips and capsule of one of the Altered (/Game/Characters/<Name>/SK_<Name>). */
	void Configure(ASOEnemy* E, const TCHAR* Name, float Radius, float HalfHeight)
	{
		E->BodyMesh = TSoftObjectPtr<USkeletalMesh>(FSoftObjectPath(FString::Printf(TEXT("/Game/Characters/%s/SK_%s.SK_%s"), Name, Name, Name)));
		E->ClipPathPrefix = FString::Printf(TEXT("/Game/Characters/%s/Anims/A_%s_"), Name, Name);
		E->GetCapsuleComponent()->InitCapsuleSize(Radius, HalfHeight);
		E->GetMesh()->SetRelativeLocation(FVector(0.0f, 0.0f, -HalfHeight));
		E->GetMesh()->SetRelativeScale3D(FVector(1.0f));
		E->BloodColor = FLinearColor(0.32f, 0.1f, 0.55f);
	}

	float Now(const UObject* O) { return O->GetWorld() ? O->GetWorld()->GetTimeSeconds() : 0.0f; }

	void FaceToward(AActor* Self, const FVector& Point, float DeltaSeconds, float Rate)
	{
		const FVector To = (Point - Self->GetActorLocation()).GetSafeNormal2D();
		if (!To.IsNearlyZero())
		{
			const FRotator Want = To.Rotation();
			Self->SetActorRotation(DeltaSeconds > 0.0f ? FMath::RInterpTo(Self->GetActorRotation(), Want, DeltaSeconds, Rate) : Want);
		}
	}

	void FireBolt(ASOEnemy* From, const FVector& Start, AActor* Target, float Damage, float Speed, float SpreadDeg)
	{
		UWorld* World = From->GetWorld();
		if (!World || !Target)
		{
			return;
		}
		const FVector Aim = Target->GetActorLocation() + FVector(0, 0, 40.0f) + Target->GetVelocity() * 0.25f;
		FVector Dir = (Aim - Start).GetSafeNormal();
		Dir = FMath::VRandCone(Dir, FMath::DegreesToRadians(SpreadDeg));
		FActorSpawnParameters Params;
		Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
		Params.Instigator = From;
		if (ASOVoidBolt* Bolt = World->SpawnActor<ASOVoidBolt>(ASOVoidBolt::StaticClass(), Start, Dir.Rotation(), Params))
		{
			Bolt->Launch(From, Dir, Target, Damage * From->GetDamageScale(), Speed);
		}
		USOSoundLibrary::PlayAt(From, TEXT("energy_shot_world"), Start, 0.8f, 0.15f, ESOSoundRange::Mid);
	}
}
