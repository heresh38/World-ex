#include "SOViewmodelComponent.h"

#include "Components/SkeletalMeshComponent.h"
#include "SOCharacter.h"
#include "SOCharacterMovementComponent.h"
#include "SOGunRigComponent.h"
#include "SOLookComponent.h"
#include "SOWeapon.h"
#include "SOWeaponData.h"

USOViewmodelComponent::USOViewmodelComponent()
{
	PrimaryComponentTick.bCanEverTick = true;
	// After movement and look, before the bodies animate (their arm IK reads the holds).
	PrimaryComponentTick.TickGroup = TG_PrePhysics;
}

void USOViewmodelComponent::BeginPlay()
{
	Super::BeginPlay();
	if (ASOCharacter* Character = Cast<ASOCharacter>(GetOwner()))
	{
		if (UActorComponent* Move = Character->GetCharacterMovement())
		{
			AddTickPrerequisiteComponent(Move);
		}
		if (USOLookComponent* Look = Character->GetLook())
		{
			AddTickPrerequisiteComponent(Look);
		}
		for (USkeletalMeshComponent* Body : { Character->GetMesh(), Character->GetFirstPersonArms() })
		{
			if (Body)
			{
				Body->AddTickPrerequisiteComponent(this);
			}
		}
	}
}

void USOViewmodelComponent::Kick(float Strength)
{
	KickBack = FMath::Min(0.12f, KickBack + 0.03f * Strength);
	KickPitch = FMath::Min(0.25f, KickPitch + 0.05f * Strength);
}

void USOViewmodelComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);
	UpdateHold(DeltaTime);
}

void USOViewmodelComponent::UpdateHold(float DeltaTime)
{
	ASOCharacter* Character = Cast<ASOCharacter>(GetOwner());
	if (!Character)
	{
		return;
	}
	const USOCharacterMovementComponent* Move = Character->GetSOMovement();
	const ASOWeapon* Weapon = Character->GetWeapon();
	const USOWeaponData* Data = Weapon ? Weapon->GetData() : nullptr;
	const float Dt = FMath::Max(DeltaTime, 1e-4f);

	// ADS (smoothstep of the character's aim progress), sway from look, bob from speed.
	const float A = Character->GetAimProgress();
	Ads = A * A * (3.0f - 2.0f * A);
	const FVector2D Look = Character->GetLook() ? Character->GetLook()->GetLastDelta() / 0.07f : FVector2D::ZeroVector; // ~mouse counts (0.07 deg each)
	SwayX += ((-Look.X * 0.0006f) - SwayX) * FMath::Min(1.0f, Dt * 10.0f);
	SwayY += ((Look.Y * 0.0006f) - SwayY) * FMath::Min(1.0f, Dt * 10.0f);
	const float Speed = Character->GetVelocity().Size2D() / 100.0f; // m/s
	const bool bGrounded = Move && Move->IsMovingOnGround();
	const bool bRunning = Move && Move->IsSprinting();
	if (bGrounded)
	{
		BobT += Dt * Speed * 1.15f;
	}
	const float BobA = FMath::Min(1.0f, Speed / 7.0f) * (1.0f - Ads * 0.92f) * (bRunning ? 1.6f : 1.0f);
	const float BobX = FMath::Sin(BobT) * 0.012f * BobA;
	const float BobY = -FMath::Abs(FMath::Cos(BobT)) * 0.014f * BobA;
	KickBack *= FMath::Pow(0.0005f, Dt);
	KickPitch *= FMath::Pow(0.0008f, Dt);
	Lower = FMath::Max(0.0f, Lower - Dt * 4.0f);
	RunK = FMath::FInterpConstantTo(RunK, bRunning ? 1.0f : 0.0f, Dt, 1.0f / FMath::Max(Data ? Data->SprintToFireTime : 0.2f, 0.05f));
	const float RunT = RunK * RunK * (3.0f - 2.0f * RunK);

	// Reload / cycling gun offsets (reload.js view space: x right, y up, z back; pitch, yaw (+left), roll).
	static const float Zero[6] = { 0, 0, 0, 0, 0, 0 };
	const float* G = Weapon ? Weapon->GetPose().Gun : Zero;

	// Hip vs ADS: in ADS the sight (rear sight line) lies on the eye axis, AdsSightDistance ahead.
	FVector AdsOffset(AdsSightDistance, 0.0f, 0.0f);
	if (Data)
	{
		const FVector SightRig = USOGunRigComponent::MeshToRig(Data->SightLocation);
		AdsOffset = FVector(AdsSightDistance - SightRig.X, -SightRig.Y, -SightRig.Z);
	}
	const float Lift = 1.0f - Ads * 0.8f;
	// view-space metres (x right, y up, z back) accumulated like viewmodel.js, then converted
	const float VX = BobX + SwayX * Lift + RunT * 0.05f + G[0];
	const float VY = BobY + SwayY * Lift - Lower * 0.35f - RunT * 0.04f + G[1];
	const float VZ = KickBack * (1.0f - Ads * 0.5f) + G[2];
	const FVector Base = FMath::Lerp(HipOffset, AdsOffset, Ads);
	const FVector Offset = Base + FVector(-VZ * 100.0f, VX * 100.0f, VY * 100.0f);

	// The muzzle flip stays small on the sights so the front post settles back on the target.
	const float EX = KickPitch * (1.0f - Ads * 0.85f) + G[3] - Lower * 0.6f - RunT * 0.35f;
	const float EY = SwayX * 2.0f * (1.0f - Ads * 0.5f) + RunT * 0.6f + G[4];
	const float EZ = G[5] + RunT * 0.25f;
	const FTransform Local(FRotator(FMath::RadiansToDegrees(EX), FMath::RadiansToDegrees(-EY), FMath::RadiansToDegrees(-EZ)), Offset);

	// First person: locked to the kicked eye, exactly what the camera shows.
	const FTransform Eye = Character->GetEyeTransform(true);
	SetWorldTransform(Local * Eye);

	// Third person: the same hold at the character's own eyes; looking down pushes the hip hold forward so the gun
	// stays in front of the chest instead of sinking into it.
	if (USceneComponent* ThirdPerson = Character->GetThirdPersonHold())
	{
		FTransform EyeTP = Eye;
		EyeTP.AddToTranslation(FVector(0.0f, 0.0f, ThirdPersonEyeLift));
		FTransform World = Local * EyeTP;
		const float Pitch = FRotator::NormalizeAxis(Character->GetAimRotation().Pitch);
		const float Down = FMath::Max(0.0f, -FMath::Sin(FMath::DegreesToRadians(Pitch)));
		const FVector Flat = FRotator(0.0f, Eye.Rotator().Yaw, 0.0f).Vector();
		World.AddToTranslation(Flat * ThirdPersonDownReach * Down * (1.0f - Ads));
		ThirdPerson->SetWorldTransform(World);
	}
}
