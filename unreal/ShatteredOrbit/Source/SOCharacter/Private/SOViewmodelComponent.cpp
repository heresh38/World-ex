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

	// Movement inertia: the gun trails strafes and landings, tucks in for a slide, drops away for a mantle.
	const FVector Vel = Character->GetVelocity();
	const float Strafe = FMath::Clamp(static_cast<float>(FVector::DotProduct(Vel, Character->GetActorRightVector())) / 440.0f, -1.2f, 1.2f);
	StrafeK = FMath::FInterpTo(StrafeK, bGrounded ? Strafe : Strafe * 0.5f, Dt, 6.0f);
	const float AirLift = Move && Move->IsFalling() ? FMath::Clamp(static_cast<float>(Vel.Z) / 900.0f, -1.0f, 1.0f) : 0.0f;
	AirK = FMath::FInterpTo(AirK, AirLift, Dt, 8.0f);
	SlideK = FMath::FInterpConstantTo(SlideK, Move && Move->IsSliding() ? 1.0f : 0.0f, Dt, 5.0f);
	MantleK = FMath::FInterpConstantTo(MantleK, Move && Move->IsMantling() ? 1.0f : 0.0f, Dt, 7.0f);
	const float SlideT = SlideK * SlideK * (3.0f - 2.0f * SlideK), MantleT = MantleK * MantleK * (3.0f - 2.0f * MantleK);
	const float Free = 1.0f - Ads * 0.85f;
	const float InX = (-StrafeK * 0.006f + SlideT * 0.008f) * Free;
	const float InY = (Character->GetLandDip() * 0.0025f - AirK * 0.008f - SlideT * 0.012f - MantleT * 0.09f) * Free;
	const float InPitch = (-MantleT * 0.5f + AirK * 0.03f) * Free;
	const float InRoll = (StrafeK * 0.05f + SlideT * 0.22f + MantleT * 0.35f) * Free;

	// Reload / cycling gun offsets (reload.js view space: x right, y up, z back; pitch, yaw (+left), roll).
	static const float Zero[6] = { 0, 0, 0, 0, 0, 0 };
	const float* G = Weapon ? Weapon->GetPose().Gun : Zero;

	// Hip vs ADS: in ADS the sight (rear sight line) lies on the eye axis, AdsSightDistance ahead.
	// Irons: the rear sight AdsSightDistance ahead. Optics: their own eye point at the eye, so the window frames the
	// view (about a quarter of it) with the dot in the middle and only the top of the receiver below.
	FVector AdsOffset(AdsSightDistance, 0.0f, 0.0f);
	if (Data)
	{
		const USOGunRigComponent* Rig = Weapon->GetFirstPersonRig();
		const float Distance = Rig && Rig->IsOpticMounted() ? AdsOpticEyeDistance
			: (Rig && Rig->HasBuiltInOptic() ? AdsBuiltInOpticDistance : AdsSightDistance);
		const FVector SightRig = USOGunRigComponent::MeshToRig(Weapon->GetSightLocation());
		AdsOffset = FVector(Distance - SightRig.X, -SightRig.Y, -SightRig.Z);
	}
	const float Lift = 1.0f - Ads * 0.8f;
	// view-space metres (x right, y up, z back) accumulated like viewmodel.js, then converted
	// Sprint: the gun is carried across the chest, muzzle up and to the left, canted, still in view (like every
	// shooter keeps it), and comes back to the hip in the gun's sprint-to-fire time.
	const float VX = BobX + SwayX * Lift + RunT * 0.01f + G[0] + InX;
	const float VY = BobY + SwayY * Lift - Lower * 0.35f + RunT * 0.035f + G[1] + InY;
	const float VZ = KickBack * (1.0f - Ads * 0.5f) + RunT * 0.03f + G[2];
	const bool bHandgun = Data && Data->MuzzleLocation.Y < 35.0f;
	// Bulky guns (launchers, the living guns) sit further out to the right and lower at the hip, so the body of
	// the gun stays in the corner of the view instead of filling it.
	FVector Bulk = FVector::ZeroVector;
	if (const USOGunRigComponent* Rig = Weapon ? Weapon->GetFirstPersonRig() : nullptr; Rig && Rig->IsBuilt() && !bHandgun)
	{
		const FBox B = Rig->GetRigBounds();
		const float HalfWidth = FMath::Max(-B.Min.Y, B.Max.Y);
		Bulk = FVector(0.0f, FMath::Max(0.0f, HalfWidth - 3.5f) * 0.9f, -FMath::Max(0.0f, B.Max.Z - 13.0f) * 0.6f);
	}
	const FVector Base = FMath::Lerp((bHandgun ? HandgunHipOffset : HipOffset) + Bulk, AdsOffset, Ads);
	const FVector Offset = Base + FVector(-VZ * 100.0f, VX * 100.0f, VY * 100.0f);

	// The muzzle flip stays small on the sights so the front post settles back on the target.
	const float EX = KickPitch * (1.0f - Ads * 0.85f) + G[3] - Lower * 0.6f + RunT * 0.14f + InPitch;
	const float EY = SwayX * 2.0f * (1.0f - Ads * 0.5f) + RunT * 0.55f + G[4];
	const float EZ = G[5] + RunT * 0.5f + InRoll;
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
