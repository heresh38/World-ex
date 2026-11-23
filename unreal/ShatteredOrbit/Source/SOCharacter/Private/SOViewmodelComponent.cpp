#include "SOViewmodelComponent.h"
#include "SOStance.h"
#include "SOWeaponData.h"

#include "AnimationRuntime.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "SOCharacter.h"
#include "SOCharacterMovementComponent.h"
#include "SOGunRigComponent.h"
#include "SOLocomotionAnimInstance.h"
#include "SOLookComponent.h"
#include "SOWeapon.h"

USOViewmodelComponent::USOViewmodelComponent()
{
	PrimaryComponentTick.bCanEverTick = true;
	// After movement and look, before the body animates (its arm IK reads the hold).
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
		if (USkeletalMeshComponent* Body = Character->GetMesh())
		{
			Body->AddTickPrerequisiteComponent(this);
		}
	}
}

namespace
{
	/** A damped spring: X toward Target with its own velocity V (Omega: how fast, Zeta: 1 = no overshoot, less = a
	 *  little; the owner, 2026-11-20: "very fluid, like water": nothing moves on a straight line and stops dead). */
	void Spring(float& X, float& V, float Target, float Omega, float Zeta, float Dt)
	{
		const float Accel = Omega * Omega * (Target - X) - 2.0f * Zeta * Omega * V;
		V += Accel * Dt;
		X += V * Dt;
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
	const USOGunRigComponent* Rig = Weapon ? Weapon->GetRig() : nullptr;
	const float Dt = FMath::Max(DeltaTime, 1e-4f);

	// ADS (smoothstep of the character's aim progress).
	const float A = Character->GetAimProgress();
	Ads = A * A * (3.0f - 2.0f * A);
	const bool bGrounded = Move && Move->IsMovingOnGround();
	const bool bRunning = (Move && Move->IsSprinting()) || Character->IsDisplayCarry();
	KickBack *= FMath::Pow(0.0005f, Dt);
	KickPitch *= FMath::Pow(0.0008f, Dt);
	Lower = FMath::Max(0.0f, Lower - Dt * 4.0f);
	// the sprint carry: the gun swings down into it and back up in the gun's sprint-to-fire time, as a spring (it ran on
	// a straight line before: a machine's motion)
	Spring(RunK, RunV, bRunning ? 1.0f : 0.0f, 4.2f / FMath::Max(Data ? Data->SprintToFireTime : 0.2f, 0.05f), 0.82f, Dt);
	RunK = FMath::Clamp(RunK, -0.15f, 1.15f);
	const float RunC = FMath::Clamp(RunK, 0.0f, 1.0f);
	const float RunT = RunC * RunC * (3.0f - 2.0f * RunC) + (RunK - RunC) * 0.5f;   // (the overshoot kept, halved)

	// Movement inertia: the gun trails strafes and landings, tucks in for a slide, drops away for a mantle.
	const FVector Vel = Character->GetVelocity();
	const float Strafe = FMath::Clamp(static_cast<float>(FVector::DotProduct(Vel, Character->GetActorRightVector())) / 440.0f, -1.6f, 1.6f);
	Spring(StrafeK, StrafeV, bGrounded ? Strafe : Strafe * 0.5f, 9.0f, 0.62f, Dt);
	StrafeK = FMath::Clamp(StrafeK, -2.0f, 2.0f);
	const float AirLift = Move && Move->IsFalling() ? FMath::Clamp(static_cast<float>(Vel.Z) / 900.0f, -1.0f, 1.0f) : 0.0f;
	AirK = FMath::FInterpTo(AirK, AirLift, Dt, 8.0f);
	Spring(SlideK, SlideV, Move && Move->IsSliding() ? 1.0f : 0.0f, 13.0f, 0.85f, Dt);
	Spring(MantleK, MantleV, Move && Move->IsMantling() ? 1.0f : 0.0f, 16.0f, 0.9f, Dt);
	SlideK = FMath::Clamp(SlideK, -0.1f, 1.1f);
	MantleK = FMath::Clamp(MantleK, -0.1f, 1.1f);
	const float SlideT = SlideK, MantleT = FMath::Clamp(MantleK, 0.0f, 1.0f);
	const float DodgeT = Move && Move->IsDodging() ? FMath::Sin(Move->GetDodgeAlpha() * PI) : 0.0f;
	const float Free = 1.0f - Ads * 0.85f;
	const float InX = (-StrafeK * 0.006f + SlideT * 0.008f) * Free;
	const float InY = (Character->GetLandDip() * 0.0025f - AirK * 0.008f - SlideT * 0.012f - MantleT * 0.09f - DodgeT * 0.012f) * Free;
	const float InPitch = (-MantleT * 0.5f + AirK * 0.03f + DodgeT * 0.06f) * Free;
	const float InRoll = (StrafeK * 0.05f + SlideT * 0.22f + MantleT * 0.35f) * Free;

	ReloadK = FMath::FInterpTo(ReloadK, Weapon && Weapon->IsReloading() ? 1.0f : 0.0f, Dt, 7.0f);

	// The reload's own moves of the gun (reload.js: the cant, the lift, the slap), a share of them in the hands: the gun
	// works in them and never leaves them (the owner's ULTIMATE rule, 2026-11-23: "all players hands must always at all
	// times be on this ... to ensure we get no floating guns"; whole, they swung the gun up beside the head).
	static const float Zero[6] = { 0, 0, 0, 0, 0, 0 };
	const float* G = Weapon ? Weapon->GetPose().Gun : Zero;
	static constexpr float GunMoves = 0.35f;

	const bool bHandgun = Data && Data->MuzzleLocation.Y < 35.0f;
	USceneComponent* Held = Character->GetGunHold();
	if (!Held)
	{
		Character->SetSightEye(FVector::ZeroVector, 0.0f);
		return;
	}
	// Where the body holds it (the stance's place, relaxed or at the ready, the sprint's carry, the reload's; on the
	// sights a long gun shouldered, the butt in the pocket).
	FTransform Hold = InFiringReach(Character, Rig, InSupportReach(Character, Rig, HoldTransform(Character, Data, bHandgun, Dt, RunT)));

	// On the sights (one body, one camera, the owner, 2026-11-23): the sight on the camera's line. A long gun stays where
	// the body shoulders it and the CAMERA alone comes to its sight's line, where a cheek on the comb would put an eye
	// (the owner: "Don't move the eyes ... just move the camera": the head keeps its own pose for those watching; the
	// shots go along the camera's line). Before, the gun went to the eyes at a fixed 9 cm: with one body its butt went
	// through the shoulder and out of the back. A handgun comes up to the eyes' line, held out at the arms' reach.
	FVector AdsOffset(AdsSightDistance, 0.0f, 0.0f);
	FVector SightPivot = FVector::ZeroVector;
	{
		const FTransform Eye = Character->GetEyeTransform(true);
		float SightEye = 0.0f;
		FVector SightEyeCS = FVector::ZeroVector;
		if (Data && Rig && Rig->IsBuilt())
		{
			const FVector SightRig = USOGunRigComponent::MeshToRig(Weapon->GetSightLocation());
			float Relief = AdsHandgunSightDistance;
			if (bHandgun)
			{
				Relief = HandgunRelief(Character, Rig, SightRig, Eye);
			}
			else
			{
				const FBox B = Rig->GetRigBounds();
				const float Least = Rig->IsOpticMounted() ? OpticEyeRelief : (Rig->HasBuiltInOptic() ? BuiltInOpticEyeRelief : IronsEyeRelief);
				Relief = FMath::Max(static_cast<float>(SightRig.X - B.Min.X) - CheekFromButt, Least);
				// (on the view's line through the shouldered gun's sight: the rounds go along it; looking steeply down
				// the stock comes off the shoulder and the head stays up: the gun comes to the eyes there)
				const float PitchDeg = FRotator::NormalizeAxis(Character->GetAimRotation().Pitch);
				const float Down = FMath::Clamp((-PitchDeg - 20.0f) / 50.0f, 0.0f, 1.0f);
				const FVector SightWorld = Hold.TransformPosition(SightRig);
				SightEyeCS = Character->GetCapsuleComponent()->GetComponentTransform().InverseTransformPosition(SightWorld - Eye.GetRotation().GetForwardVector() * Relief);
				SightEye = Ads * (1.0f - Down);
			}
			AdsOffset = FVector(Relief - SightRig.X, -SightRig.Y, -SightRig.Z);
			SightPivot = SightRig;
		}
		Character->SetSightEye(SightEyeCS, SightEye);
	}

	// The kick, the raise, the reload's moves and the motion's inertia on top (the walk's bob and sway are the body's own).
	{
		const float TX = G[0] * GunMoves + InX, TY = -Lower * 0.35f + G[1] * GunMoves + InY;
		const float TZ = KickBack * (1.0f - Ads) + G[2] * GunMoves;
		const float PX = KickPitch * (1.0f - Ads) + G[3] * GunMoves - Lower * 0.6f + InPitch;
		const float PY = G[4] * GunMoves, PZ = G[5] * GunMoves + InRoll;
		const FTransform Ride(FRotator(FMath::RadiansToDegrees(PX), FMath::RadiansToDegrees(-PY), FMath::RadiansToDegrees(-PZ)),
			FVector(-TZ * 100.0f, TX * 100.0f, TY * 100.0f));
		Hold = Ride * Hold;
	}
	// On the sights (the same gun in the same hands, first person or not): the sight on the line of the body's eyes,
	// where the camera is in first person; the kick turns the gun about its SIGHT, so the reticle stays on the point the
	// rounds hit (the owner: "the bullets don't even hit where the scope is").
	if (Ads > 1e-3f)
	{
		const float EX = KickPitch * 0.15f + G[3] * GunMoves * 0.3f + InPitch * 0.15f;
		const float EZ = (G[5] * GunMoves + InRoll) * 0.15f;
		const FRotator Turn(FMath::RadiansToDegrees(EX), 0.0f, FMath::RadiansToDegrees(-EZ));
		const FVector Offset = AdsOffset + (SightPivot - Turn.RotateVector(SightPivot)) + FVector(-KickBack * 15.0f, 0.0f, 0.0f);
		const FTransform Sighted = FTransform(Turn, Offset) * Character->GetEyeTransform(true);   // (the eye: on the shouldered gun's sight line)
		FTransform Mixed;
		Mixed.Blend(Hold, Sighted, Ads);
		Hold = Mixed;
	}
	Hold = ClearOfWalls(Character, Rig, Hold, Dt);
	// (both hands again after the motion's sway and the kick: they carried a pump's fore end out of the support hand's reach;
	// on the sights the sight stays on the eye's line, the gun was put in reach before the eye came to it)
	{
		FTransform Reached = InSupportReach(Character, Rig, Hold);
		Reached.SetTranslation(FMath::Lerp(Reached.GetTranslation(), Hold.GetTranslation(), static_cast<double>(Ads)));
		Hold = InFiringReach(Character, Rig, Reached);
	}
	Held->SetWorldTransform(Hold);
	SetWorldTransform(Hold);
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

FTransform USOViewmodelComponent::HoldTransform(const ASOCharacter* Character, const USOWeaponData* Data, bool bHandgun, float Dt, float RunT)
{
	const FTransform Actor = Character->GetActorTransform();
	FVector Pocket, Chest;
	GetShoulderPoints(Character, Pocket, Chest);
	const ASOWeapon* Weapon = Character->GetWeapon();
	const USOGunRigComponent* Rig = Weapon ? Weapon->GetRig() : nullptr;
	// the gun's class: where it rides relaxed, at the ready and on the sights (FSOStance, Data/stances.json)
	const FSOStance& St = FSOStanceData::Get().For(Data ? Data->Family : NAME_None);
	const FQuat Facing = FRotator(0.0f, Character->GetAimRotation().Yaw, 0.0f).Quaternion();

	// Where the gun points: the crosshair's point, never nearer than a few metres (a wall at arm's length would
	// swing the muzzle sideways), eased so a trace flicking between near and far things never snaps the gun.
	const FVector Eye = Character->GetEyeTransform(true).GetLocation();
	FVector Target = Character->GetAimTarget();
	const FVector ToTarget = Target - Eye;
	if (ToTarget.SizeSquared() < FMath::Square(MinAimDistance))
	{
		Target = Eye + Character->GetEyeTransform(true).GetRotation().GetForwardVector() * MinAimDistance;
	}
	FVector Start;
	const FBox B = Rig && Rig->IsBuilt() ? Rig->GetRigBounds() : FBox(FVector(-20.0f, -3.0f, -12.0f), FVector(40.0f, 3.0f, 10.0f));
	FVector Butt(B.Min.X + 1.0f, 0.0f, FMath::Clamp(ButtHeight, B.Min.Z + 4.0f, B.Max.Z - 4.0f));
	// Pointed steeply down the stock comes off the shoulder: the gun is held lower, in front of the body and nearer
	// its middle, both hands on it with the elbows bent (a man pointing a rifle at the ground); from the shoulder
	// pocket it pointed down along the body, the support hand beyond reach and the firing hand at the hip (the
	// owner, 2026-11-20: "looking down completely ... the players hand splits and the gun moves weirdly").
	const float PitchDeg = FRotator::NormalizeAxis(Character->GetAimRotation().Pitch);
	const float Down = FMath::Clamp((-PitchDeg - 20.0f) / 50.0f, 0.0f, 1.0f) * (1.0f - Ads * 0.35f);
	if (bHandgun)
	{
		Start = Actor.TransformPosition(Chest + FVector(6.0f, 0.0f, -14.0f) * Down);
	}
	else
	{
		const FVector Low = Chest + LowHold;                               // low and ahead of the chest, a little right
		// (at 10 cm ahead the gun hung against the belly and thighs with the hands stacked on it)
		// (the butt in the shoulder pocket, raised by the class at the ready so the gun is up and forward; on the sights
		// the sight goes on the eyes' line: UpdateHold)
		Start = Actor.TransformPosition(FMath::Lerp(Pocket + FMath::Lerp(St.ReadyShift, St.AimShift, Ads), Low, Down));
		Butt.X = FMath::Lerp(Butt.X, Butt.X + 16.0f, Down);               // (the butt no longer in a pocket: the gun's middle hangs from the point)
	}
	FVector WantDir = (Target - Start).GetSafeNormal(1e-4f, Character->GetEyeTransform(true).GetRotation().GetForwardVector());
	// The gun's own pitch is held within what a body can do (a rifle at the low ready points down at most about 55
	// degrees: the shooter bends to look at the ground, the stock stays under the arm): pointed straight down from
	// the chest the stock stood up along the face (the owner, 2026-11-21). The shot still goes where the eyes look.
	if (!bHandgun)
	{
		FRotator R = WantDir.Rotation();
		R.Pitch = FMath::Clamp(static_cast<float>(R.Pitch), -MaxDownPitch, MaxUpPitch);
		R.Pitch -= St.ReadyDip * (1.0f - Ads);                      // (at the ready the muzzle a touch under the line)
		WantDir = R.Vector();
	}
	if (!bHoldDirValid || Dt > 0.2f)
	{
		HoldDir = WantDir;
		bHoldDirValid = true;
	}
	else
	{
		HoldDir = FQuat::Slerp(FQuat::Identity, FQuat::FindBetweenNormals(HoldDir, WantDir), FMath::Min(1.0f, Dt * 30.0f)).RotateVector(HoldDir).GetSafeNormal();
	}
	FRotator AimRot = HoldDir.Rotation(); // level roll
	if (!bHandgun)
	{
		// held low the gun cants a little inward (the top toward the body's left), as a rifle carried at the low
		// ready does: the firing wrist stays nearer straight on the grip
		AimRot.Roll = -LowCant * Down;
	}
	const FQuat Aim = AimRot.Quaternion();
	FTransform Hold;
	if (bHandgun)
	{
		// both arms out, the gun a little right of the middle, rising toward the eye line when aiming
		Hold = FTransform(Aim, Start + Aim.RotateVector(FMath::Lerp(St.HandHold, St.HandAimHold, Ads)));
	}
	else
	{
		Hold = FTransform(Aim, Start - Aim.RotateVector(Butt));
		// (a long fore end past the support arm's reach: the gun comes in toward that shoulder, InSupportReach)
	}

	// Relaxed (out of a fight, FSOStance; the owner's reference): the gun carried low across the body, the arms easy (from
	// the eyes it is below the picture); it comes up to the ready on a shot, an aim, a reload or a hit
	// (ASOCharacter::GetCombatReady), never a body walking about on the sights.
	if (const float Relax = (1.0f - Character->GetCombatReady()) * (1.0f - Ads); Relax > 1e-3f)
	{
		const FTransform LowCarry(Facing * St.RelaxRot.Quaternion(), Actor.TransformPosition(Chest + St.RelaxOffset));
		FTransform Eased;
		Eased.Blend(Hold, LowCarry, Relax * Relax * (3.0f - 2.0f * Relax));
		Hold = Eased;
	}
	// Off the shoulder: a sprint carries the gun low across the chest (muzzle down and to the left); a reload brings it
	// down in front of the chest, canted so the support hand works the mag well in front of the body.
	const float Reload = ReloadK * ReloadK * (3.0f - 2.0f * ReloadK) * (1.0f - Ads);
	if (RunT > 1e-3f || Reload > 1e-3f)
	{
		// (as the gun's data says: low, short, high; a gun that says nothing, a handgun high and anything else low)
		const FName Style = Data ? Data->SprintCarry : NAME_None;
		const bool bHigh = Style == TEXT("high") || (Style.IsNone() && bHandgun), bShort = Style == TEXT("short");
		const FTransform Carry(Facing * (bHigh ? HandgunCarryRot : (bShort ? ShortCarryRot : CarryRot)).Quaternion(),
			Actor.TransformPosition(Chest + (bHigh ? HandgunCarryOffset : (bShort ? ShortCarryOffset : CarryOffset))));
		const FTransform Reloading(Facing * ReloadRot.Quaternion(), Actor.TransformPosition(Chest + ReloadOffset));
		FTransform Blended;
		Blended.Blend(Hold, Carry, RunT);
		Hold = Blended;
		Blended.Blend(Hold, Reloading, bHandgun ? Reload * 0.5f : Reload);
		Hold = Blended;
	}
	return Hold;
}

FTransform USOViewmodelComponent::ClearOfWalls(const ASOCharacter* Character, const USOGunRigComponent* Rig, const FTransform& Hold, float Dt)
{
	// One gun in the body's hands, seen from its own eyes: it must never go into a wall in front (a gun of its own drawn
	// for the eyes could pass through walls; the one in the hands cannot). Swept from the butt along the barrel; what is
	// in the way pulls the gun back along itself (up to a third of its length), and beyond that the muzzle turns up past
	// it (the high ready), eased in and out as a spring.
	float Want = 0.0f;
	const UWorld* World = Character->GetWorld();
	if (Rig && Rig->IsBuilt() && World)
	{
		const FBox B = Rig->GetRigBounds();
		const float Length = static_cast<float>(B.Max.X - B.Min.X);
		const FVector Axis = Hold.GetRotation().GetForwardVector();
		const FVector From = Hold.TransformPosition(FVector(B.Min.X + 2.0f, 0.0f, 0.0f));
		FCollisionQueryParams Params(SCENE_QUERY_STAT(SOGunWall), false, Character);
		Params.AddIgnoredActor(Character->GetWeapon());
		FHitResult Hit;
		if (World->SweepSingleByChannel(Hit, From, From + Axis * (Length + 4.0f), FQuat::Identity, ECC_Visibility, FCollisionShape::MakeSphere(2.5f), Params))
		{
			Want = FMath::Clamp(Length + 4.0f - static_cast<float>(Hit.Distance), 0.0f, Length);
		}
	}
	Spring(WallK, WallV, Want, 18.0f, 0.95f, FMath::Min(Dt, 0.05f));
	WallK = FMath::Max(WallK, 0.0f);
	if (WallK < 0.2f || !Rig || !Rig->IsBuilt())
	{
		return Hold;
	}
	const FBox B = Rig->GetRigBounds();
	const float Length = static_cast<float>(B.Max.X - B.Min.X);
	const float Back = FMath::Min(WallK, Length * 0.33f);
	const float Up = FMath::Clamp((WallK - Back) / FMath::Max(Length * 0.5f, 1.0f), 0.0f, 1.0f) * 60.0f;
	FTransform Out = Hold;
	Out.AddToTranslation(-Hold.GetRotation().GetForwardVector() * Back);
	if (Up > 0.1f)
	{
		// turned about the grip (the rig's origin, where the hand is): the muzzle up, the butt down
		const FQuat Raise(Hold.GetRotation().GetRightVector(), -FMath::DegreesToRadians(Up));
		Out.SetRotation(Raise * Out.GetRotation());
	}
	return Out;
}

float USOViewmodelComponent::HandgunRelief(const ASOCharacter* Character, const USOGunRigComponent* Rig, const FVector& SightRig, const FTransform& Eye) const
{
	// Held out in both hands, the sight on the eyes' line: as far ahead as puts the firing wrist at HandgunReach of the
	// arm from its shoulder in the body's last pose (the arms nearly straight). The wrist with the sight at the eye is
	// P0; with it Relief further ahead, P0 + Forward x Relief: on a sphere round the shoulder.
	const USkeletalMeshComponent* Body = Character->GetMesh();
	FTransform R, L;
	if (!Body || !Rig->GetHandTargets(R, L))
	{
		return AdsHandgunSightDistance;
	}
	const int32 Sh = Body->GetBoneIndex(TEXT("upperarm_R")), El = Body->GetBoneIndex(TEXT("forearm_R")), Wr = Body->GetBoneIndex(TEXT("hand_R"));
	if (Sh == INDEX_NONE || El == INDEX_NONE || Wr == INDEX_NONE)
	{
		return AdsHandgunSightDistance;
	}
	const FVector Shoulder = Body->GetBoneLocation(Body->GetBoneName(Sh));
	const FVector Elbow = Body->GetBoneLocation(Body->GetBoneName(El));
	const float Arm = static_cast<float>(FVector::Dist(Shoulder, Elbow) + FVector::Dist(Elbow, Body->GetBoneLocation(Body->GetBoneName(Wr))));
	const FVector Forward = Eye.GetRotation().GetForwardVector();
	// the furthest the wrist at InGun may be held out along the eyes' line, Reach of an arm Length from Joint
	auto Furthest = [&](const FVector& InGun, const FVector& Joint, float Reach, float Length)
	{
		const FVector D = Eye.TransformPosition(InGun - SightRig) - Joint;
		const float Bq = static_cast<float>(FVector::DotProduct(Forward, D));
		const float Disc = Bq * Bq - (static_cast<float>(D.SizeSquared()) - FMath::Square(Reach * Length));
		return Disc < 0.0f ? -1.0f : -Bq + FMath::Sqrt(Disc);
	};
	float Relief = Furthest(Rig->GetComponentTransform().InverseTransformPosition(R.GetLocation()), Shoulder, HandgunReach, Arm);
	if (Relief < 0.0f)
	{
		return AdsHandgunSightDistance;
	}
	// (and the support hand round it: no further out than that arm reaches either)
	FVector SupportInGun, SupportShoulder;
	float SupportLength = 0.0f;
	if (SupportArm(Character, Rig, SupportInGun, SupportShoulder, SupportLength))
	{
		const float Support = Furthest(SupportInGun, SupportShoulder, FMath::Min(HandgunReach, SupportReach), SupportLength);
		if (Support > 0.0f)
		{
			Relief = FMath::Min(Relief, Support);
		}
	}
	return FMath::Clamp(Relief, 16.0f, 60.0f);
}

bool USOViewmodelComponent::SupportArm(const ASOCharacter* Character, const USOGunRigComponent* Rig, FVector& OutInGun, FVector& OutShoulder, float& OutArm) const
{
	const USkeletalMeshComponent* Body = Character->GetMesh();
	FTransform R, L;
	if (!Body || !Rig || !Rig->IsBuilt() || !Rig->GetHandTargets(R, L))
	{
		return false;
	}
	const int32 Sh = Body->GetBoneIndex(TEXT("upperarm_L")), El = Body->GetBoneIndex(TEXT("forearm_L")), Wr = Body->GetBoneIndex(TEXT("hand_L"));
	if (Sh == INDEX_NONE || El == INDEX_NONE || Wr == INDEX_NONE)
	{
		return false;
	}
	OutShoulder = Body->GetBoneLocation(Body->GetBoneName(Sh));
	const FVector Elbow = Body->GetBoneLocation(Body->GetBoneName(El));
	OutArm = static_cast<float>(FVector::Dist(OutShoulder, Elbow) + FVector::Dist(Elbow, Body->GetBoneLocation(Body->GetBoneName(Wr))));
	// where the hand is fitted on this gun (the rig's own target, moved onto the gun's surfaces)
	OutInGun = Rig->GetComponentTransform().InverseTransformPosition(L.GetLocation());
	if (const USOLocomotionAnimInstance* Anim = Cast<USOLocomotionAnimInstance>(Body->GetAnimInstance()); Anim && Anim->HasFittedGrip())
	{
		OutInGun += Anim->GetFittedOffset(true);
	}
	return true;
}

FTransform USOViewmodelComponent::InSupportReach(const ASOCharacter* Character, const USOGunRigComponent* Rig, const FTransform& Hold) const
{
	// The support hand is on the gun too (the owner's ULTIMATE rule, 2026-11-23: "the gun is placed where the hand can
	// be, never the hand chasing a gun out of its reach"): its place on the gun past the support arm's reach (looking
	// far up or down, a long fore end) brings the gun in toward that shoulder. A long gun's butt goes no further back
	// than in front of the firing shoulder (pulled into it, the owner's "the gun is in the players shoulder"); what is
	// left the anim's hold slides the hand back along the gun for. Not while a reload or an action works the hand.
	const ASOWeapon* Weapon = Character->GetWeapon();
	FVector InGun, Shoulder;
	float Arm = 0.0f;
	if (!Weapon || Weapon->IsReloading() || Weapon->GetPose().bHand || Character->HoldsWithOneHand() || !SupportArm(Character, Rig, InGun, Shoulder, Arm))
	{
		return Hold;
	}
	const FVector Wrist = Hold.TransformPosition(InGun);
	const float D = static_cast<float>(FVector::Dist(Wrist, Shoulder));
	if (D <= SupportReach * Arm || D < 1e-3f)
	{
		return Hold;
	}
	FVector Move = (Shoulder - Wrist) / D * (D - SupportReach * Arm);
	// (pointed steeply down the stock is off the shoulder: the gun hangs in front of the body and comes in freely)
	const float PitchDeg = FRotator::NormalizeAxis(Character->GetAimRotation().Pitch);
	const float Down = FMath::Clamp((-PitchDeg - 20.0f) / 50.0f, 0.0f, 1.0f);
	// (and pointed steeply up the shoulder rises under the stock: a long fore end may bring it back a little further)
	const float Up = FMath::Clamp((PitchDeg - 35.0f) / 25.0f, 0.0f, 1.0f);
	if (!Rig->IsHandgun() && Down < 1.0f)
	{
		const USkeletalMeshComponent* Body = Character->GetMesh();
		const int32 ShR = Body->GetBoneIndex(TEXT("upperarm_R"));
		if (ShR != INDEX_NONE)
		{
			const FVector Axis = Hold.GetRotation().GetForwardVector();
			const FVector Butt = Hold.TransformPosition(FVector(Rig->GetRigBounds().Min.X, 0.0f, 0.0f));
			const float Room = FMath::Max(0.0f, static_cast<float>(FVector::DotProduct(Butt - Body->GetBoneLocation(Body->GetBoneName(ShR)), Axis)) - ButtAheadOfShoulder + 6.0f * Up) / FMath::Max(1.0f - Down, 1e-3f);
			const float Back = static_cast<float>(-FVector::DotProduct(Move, Axis));
			if (Back > Room)
			{
				Move += Axis * (Back - Room);
			}
		}
	}
	FTransform Out = Hold;
	Out.AddToTranslation(Move);
	return Out;
}

FTransform USOViewmodelComponent::InFiringReach(const ASOCharacter* Character, const USOGunRigComponent* Rig, const FTransform& Hold) const
{
	// The firing hand is always on its handle (the owner's ULTIMATE rule, 2026-11-23): the gun is never placed where the
	// hand cannot be. Its wrist's place on the gun (the rig rides the hold), against the firing shoulder in the body's
	// last pose: further than FiringReach of the arm, the gun comes in; folded closer than a third of it, out.
	const USkeletalMeshComponent* Body = Character->GetMesh();
	FTransform R, L;
	if (!Rig || !Rig->IsBuilt() || !Body || !Rig->GetHandTargets(R, L))
	{
		return Hold;
	}
	const int32 Sh = Body->GetBoneIndex(TEXT("upperarm_R")), El = Body->GetBoneIndex(TEXT("forearm_R")), Wr = Body->GetBoneIndex(TEXT("hand_R"));
	if (Sh == INDEX_NONE || El == INDEX_NONE || Wr == INDEX_NONE)
	{
		return Hold;
	}
	const FVector Shoulder = Body->GetBoneLocation(Body->GetBoneName(Sh));
	const FVector Elbow = Body->GetBoneLocation(Body->GetBoneName(El));
	const float Arm = static_cast<float>(FVector::Dist(Shoulder, Elbow) + FVector::Dist(Elbow, Body->GetBoneLocation(Body->GetBoneName(Wr))));
	const FVector WristInGun = Rig->GetComponentTransform().InverseTransformPosition(R.GetLocation());
	const FVector Off = Hold.TransformPosition(WristInGun) - Shoulder;
	const float D = static_cast<float>(Off.Size());
	FTransform Out = Hold;
	if (D > FiringReach * Arm)
	{
		Out.AddToTranslation(-Off / FMath::Max(D, 1e-3f) * (D - FiringReach * Arm));
	}
	else if (D < 0.33f * Arm && D > 1e-3f)
	{
		Out.AddToTranslation(Off / D * (0.33f * Arm - D));
	}
	return Out;
}
