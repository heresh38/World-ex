#include "SOViewmodelComponent.h"

#include "AnimationRuntime.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
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

	// Reloads: the gun comes up and cants toward the view so the magazine well and the hands are in sight
	// (it used to stay at the hip, the work happening under the camera).
	ReloadK = FMath::FInterpTo(ReloadK, Weapon && Weapon->IsReloading() ? 1.0f : 0.0f, Dt, 7.0f);
	const float RlT = ReloadK * ReloadK * (3.0f - 2.0f * ReloadK) * (1.0f - Ads);
	const float RlX = -ReloadLift.Y * 0.01f * RlT, RlY = ReloadLift.Z * 0.01f * RlT, RlZ = -ReloadLift.X * 0.01f * RlT;
	const float RlPitch = FMath::DegreesToRadians(ReloadTilt.Y) * RlT, RlRoll = FMath::DegreesToRadians(ReloadTilt.X) * RlT,
		RlYaw = FMath::DegreesToRadians(ReloadTilt.Z) * RlT;

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
	const float VX = BobX + SwayX * Lift + RunT * 0.01f + G[0] + InX + RlX;
	const float VY = BobY + SwayY * Lift - Lower * 0.35f + RunT * 0.035f + G[1] + InY + RlY;
	const float VZ = KickBack * (1.0f - Ads * 0.5f) + RunT * 0.03f + G[2] + RlZ;
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
	const float EX = KickPitch * (1.0f - Ads * 0.85f) + G[3] - Lower * 0.6f + RunT * 0.14f + InPitch + RlPitch;
	const float EY = SwayX * 2.0f * (1.0f - Ads * 0.5f) + RunT * 0.55f + G[4] + RlYaw;
	const float EZ = G[5] + RunT * 0.5f + InRoll + RlRoll;
	const FTransform Local(FRotator(FMath::RadiansToDegrees(EX), FMath::RadiansToDegrees(-EY), FMath::RadiansToDegrees(-EZ)), Offset);

	// First person: locked to the kicked eye, exactly what the camera shows.
	const FTransform Eye = Character->GetEyeTransform(true);
	SetWorldTransform(Local * Eye);

	// Third person: the body's own hold (the first-person one is built round the camera's eye and would put the gun
	// at head height, or through the head when aiming). Long guns: the butt in the right shoulder pocket, the bore on
	// the crosshair's point; aiming shoulders it a little higher and nearer the cheek (the head cants onto the stock,
	// USOLocomotionAnimInstance). Handguns: out in both hands in front of the chest. The reload choreography, kick,
	// raise, sprint carry and mantle offsets ride on top; the bob and sway stay out (the body animates).
	if (USceneComponent* ThirdPerson = Character->GetThirdPersonHold())
	{
		const float TX = RunT * 0.01f + G[0] + InX, TY = -Lower * 0.35f + RunT * 0.035f + G[1] + InY;
		const float TZ = KickBack * (1.0f - Ads * 0.5f) + RunT * 0.03f + G[2];
		const float PX = KickPitch * (1.0f - Ads * 0.85f) + G[3] - Lower * 0.6f + RunT * 0.14f + InPitch;
		const float PY = RunT * 0.55f + G[4], PZ = G[5] + RunT * 0.5f + InRoll;
		const FTransform Ride(FRotator(FMath::RadiansToDegrees(PX), FMath::RadiansToDegrees(-PY), FMath::RadiansToDegrees(-PZ)),
			FVector(-TZ * 100.0f, TX * 100.0f, TY * 100.0f));
		ThirdPerson->SetWorldTransform(Ride * ThirdPersonHoldTransform(Character, bHandgun, Dt));
	}
}

bool USOViewmodelComponent::GetShoulderPoints(const ASOCharacter* Character, FVector& OutPocket, FVector& OutChest) const
{
	// Actor space (X forward, Y right, Z up). From the body's last animated pose, so the stance (aim pitch, blade,
	// lean, the clip) carries the shoulder; the pocket's offset turns with the chest.
	OutPocket = DefaultPocket;
	OutChest = FVector(DefaultPocket.X, 0.0f, DefaultPocket.Z + 4.0f);
	const USkeletalMeshComponent* Body = Character->GetMesh();
	const USkeletalMesh* Mesh = Body ? Body->GetSkeletalMeshAsset() : nullptr;
	if (!Mesh)
	{
		return false;
	}
	const int32 ArmR = Body->GetBoneIndex(TEXT("upperarm_R")), ArmL = Body->GetBoneIndex(TEXT("upperarm_L"));
	const int32 Chest = Body->GetBoneIndex(TEXT("chest"));
	const TArray<FTransform>& CS = Body->GetComponentSpaceTransforms();
	if (ArmR == INDEX_NONE || ArmL == INDEX_NONE || Chest == INDEX_NONE || !CS.IsValidIndex(FMath::Max3(ArmR, ArmL, Chest)))
	{
		return false;
	}
	const FTransform ToActor = Body->GetRelativeTransform(); // the body hangs off the capsule (the actor's root)
	const FTransform RefChest = FAnimationRuntime::GetComponentSpaceTransformRefPose(Mesh->GetRefSkeleton(), Chest);
	const FQuat ChestTurn = CS[Chest].GetRotation() * RefChest.GetRotation().Inverse();
	const FVector OffsetCS = ToActor.InverseTransformVectorNoScale(PocketFromShoulder);
	OutPocket = ToActor.TransformPosition(CS[ArmR].GetLocation() + ChestTurn.RotateVector(OffsetCS / ToActor.GetScale3D()));
	OutChest = ToActor.TransformPosition((CS[ArmR].GetLocation() + CS[ArmL].GetLocation()) * 0.5f);
	return true;
}

FTransform USOViewmodelComponent::ThirdPersonHoldTransform(const ASOCharacter* Character, bool bHandgun, float Dt)
{
	const FTransform Actor = Character->GetActorTransform();
	FVector Pocket, Chest;
	GetShoulderPoints(Character, Pocket, Chest);
	const ASOWeapon* Weapon = Character->GetWeapon();
	const USOGunRigComponent* Rig = Weapon ? Weapon->GetThirdPersonRig() : nullptr;

	// Where the gun points: the crosshair's point, never nearer than a few metres (a wall at arm's length would
	// swing the muzzle sideways), eased so a trace flicking between near and far things never snaps the gun.
	const FVector Eye = Character->GetEyeTransform(true).GetLocation();
	FVector Target = Character->GetAimTarget();
	const FVector ToTarget = Target - Eye;
	if (ToTarget.SizeSquared() < FMath::Square(ThirdPersonMinAimDistance))
	{
		Target = Eye + Character->GetEyeTransform(true).GetRotation().GetForwardVector() * ThirdPersonMinAimDistance;
	}
	FVector Start;
	const FBox B = Rig && Rig->IsBuilt() ? Rig->GetRigBounds() : FBox(FVector(-20.0f, -3.0f, -12.0f), FVector(40.0f, 3.0f, 10.0f));
	const FVector Butt(B.Min.X + 1.0f, 0.0f, FMath::Clamp(ButtHeight, B.Min.Z + 4.0f, B.Max.Z - 4.0f));
	if (bHandgun)
	{
		Start = Actor.TransformPosition(Chest);
	}
	else
	{
		Start = Actor.TransformPosition(Pocket + FMath::Lerp(FVector::ZeroVector, PocketAimShift, Ads));
	}
	const FVector WantDir = (Target - Start).GetSafeNormal(1e-4f, Character->GetEyeTransform(true).GetRotation().GetForwardVector());
	if (!bHoldDirValid || Dt > 0.2f)
	{
		HoldDir = WantDir;
		bHoldDirValid = true;
	}
	else
	{
		HoldDir = FQuat::Slerp(FQuat::Identity, FQuat::FindBetweenNormals(HoldDir, WantDir), FMath::Min(1.0f, Dt * 30.0f)).RotateVector(HoldDir).GetSafeNormal();
	}
	const FQuat Aim = HoldDir.Rotation().Quaternion(); // level roll
	if (bHandgun)
	{
		// both arms out, the gun a little right of the middle, rising toward the eye line when aiming
		const FVector Out = FMath::Lerp(HandgunHold, HandgunAimHold, Ads);
		return FTransform(Aim, Start + Aim.RotateVector(Out));
	}
	FTransform Hold(Aim, Start - Aim.RotateVector(Butt));

	// A long forend can sit past the support arm's reach from the left shoulder: the gun then comes in toward the
	// chest (the butt rides inward from the pocket) just enough for the hand to stay on it. Not while reloading (the
	// off hand is away at the mag or the bolt).
	const USkeletalMeshComponent* Body = Character->GetMesh();
	const USceneComponent* HoldComp = Character->GetThirdPersonHold();
	FTransform HandR, HandL;
	const int32 Sh = Body ? Body->GetBoneIndex(TEXT("upperarm_L")) : INDEX_NONE;
	const int32 El = Body ? Body->GetBoneIndex(TEXT("forearm_L")) : INDEX_NONE;
	const int32 Wr = Body ? Body->GetBoneIndex(TEXT("hand_L")) : INDEX_NONE;
	if (Rig && HoldComp && Sh != INDEX_NONE && El != INDEX_NONE && Wr != INDEX_NONE && !Weapon->IsReloading() && Rig->GetHandTargets(HandR, HandL))
	{
		const FVector LeftInHold = HoldComp->GetComponentTransform().InverseTransformPosition(HandL.GetLocation());
		const FVector Shoulder = Body->GetBoneLocation(Body->GetBoneName(Sh));
		const float Reach = 0.97f * (FVector::Dist(Shoulder, Body->GetBoneLocation(Body->GetBoneName(El)))
			+ FVector::Dist(Body->GetBoneLocation(Body->GetBoneName(El)), Body->GetBoneLocation(Body->GetBoneName(Wr))));
		const FVector Left = Hold.TransformPosition(LeftInHold);
		const float Over = FVector::Dist(Left, Shoulder) - Reach;
		if (Over > 0.0f)
		{
			Hold.AddToTranslation((Shoulder - Left).GetSafeNormal() * FMath::Min(Over, 15.0f));
		}
	}
	return Hold;
}
