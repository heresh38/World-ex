#include "SOExplosive.h"

#include "Components/PointLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Net/UnrealNetwork.h"
#include "SOCombatCharacter.h"
#include "SOCombatStatics.h"
#include "SOCue.h"
#include "SOFxSubsystem.h"
#include "SOProjectileSubsystem.h"
#include "SOSound.h"

int32 ASOExplosive::NumDetonated = 0;

namespace
{
	/** What each kind looks and sounds like when it goes. */
	struct FKindLook
	{
		USOFxSubsystem::EBlast Blast;
		FLinearColor Color;
		const TCHAR* Sound;
		/** the leak's flame (a Sarketh cell leaks its amber light) */
		FLinearColor Leak;
	};

	FKindLook LookOf(ESOExplosiveKind Kind)
	{
		switch (Kind)
		{
		case ESOExplosiveKind::Cylinder: return { USOFxSubsystem::EBlast::Fire, FLinearColor(1.0f, 0.62f, 0.26f), TEXT("gas_burst"), FLinearColor(0.55f, 0.75f, 1.0f) };
		case ESOExplosiveKind::Cell: return { USOFxSubsystem::EBlast::Zap, FLinearColor(1.0f, 0.62f, 0.18f), TEXT("cell_burst"), FLinearColor(1.0f, 0.6f, 0.16f) };
		case ESOExplosiveKind::Vehicle: return { USOFxSubsystem::EBlast::Fire, FLinearColor(1.0f, 0.5f, 0.18f), TEXT("vehicle_explode"), FLinearColor(1.0f, 0.5f, 0.15f) };
		default: return { USOFxSubsystem::EBlast::Fire, FLinearColor(1.0f, 0.55f, 0.2f), TEXT("drum_explode"), FLinearColor(1.0f, 0.55f, 0.18f) };
		}
	}

	const TCHAR* KindName(ESOExplosiveKind Kind)
	{
		switch (Kind)
		{
		case ESOExplosiveKind::Cylinder: return TEXT("cylinder");
		case ESOExplosiveKind::Cell: return TEXT("cell");
		case ESOExplosiveKind::Vehicle: return TEXT("car");
		default: return TEXT("drum");
		}
	}

	/** A wreck thrown up by its own blast: how high (cm), how long it is in the air (s). */
	constexpr float LeapHeight = 150.0f;
	constexpr float LeapTime = 1.05f;
}

ASOExplosive::ASOExplosive()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.TickInterval = 0.0f;
	bReplicates = true;
	SetReplicatingMovement(false);
	Mesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Mesh"));
	SetRootComponent(Mesh);
	// cover, and a target: it stops bodies, rounds and sight like the world does
	Mesh->SetCollisionProfileName(TEXT("BlockAll"));
	Mesh->SetCollisionResponseToChannel(SO_TRACE_BULLET, ECR_Block);
	Mesh->SetMobility(EComponentMobility::Movable);
	Mesh->SetCanEverAffectNavigation(true);
	Light = CreateDefaultSubobject<UPointLightComponent>(TEXT("Light"));
	Light->SetupAttachment(Mesh);
	Light->SetIntensityUnits(ELightUnits::Candelas);
	Light->SetIntensity(0.0f);
	Light->SetAttenuationRadius(420.0f);
	Light->SetCastShadows(false);
	Light->SetVisibility(false);
	SetNumbers();
}

FString ASOExplosive::MeshPath(ESOExplosiveKind InKind)
{
	const FString Name = FString::Printf(TEXT("SM_EX_%s"), KindName(InKind));
	return FString::Printf(TEXT("/Game/Props/Explosives/%s.%s"), *Name, *Name);
}

void ASOExplosive::SetKind(ESOExplosiveKind InKind)
{
	Kind = InKind;
	SetNumbers();
	if (!IsTemplate())
	{
		ApplyMesh();
	}
}

void ASOExplosive::SetNumbers()
{
	switch (Kind)
	{
	case ESOExplosiveKind::Cylinder: MaxHealth = 40.0f; Radius = 430.0f; Damage = 210.0f; BurnFuse = 1.9f; break;
	case ESOExplosiveKind::Cell: MaxHealth = 50.0f; Radius = 480.0f; Damage = 230.0f; BurnFuse = 2.3f; break;
	case ESOExplosiveKind::Vehicle: MaxHealth = 260.0f; Radius = 780.0f; Damage = 320.0f; BurnFuse = 4.2f; break;
	default: MaxHealth = 60.0f; Radius = 520.0f; Damage = 240.0f; BurnFuse = 2.6f; break;
	}
	Health = MaxHealth;
}

void ASOExplosive::ApplyMesh()
{
	if (Mesh && !IsTemplate())
	{
		if (UStaticMesh* SM = Cast<UStaticMesh>(FSoftObjectPath(MeshPath(Kind)).TryLoad()))
		{
			Mesh->SetStaticMesh(SM);
		}
	}
}

void ASOExplosive::OnConstruction(const FTransform& Transform)
{
	Super::OnConstruction(Transform);
	ApplyMesh();                                                     // (a level's: its kind's mesh, in the editor too)
}

void ASOExplosive::BeginPlay()
{
	Super::BeginPlay();
	SetNumbers();                                                    // (the kind a level gave it)
	ApplyMesh();
	Home = GetActorLocation();
	HomeTurn = GetActorRotation();
	if (HasAuthority())
	{
		Health = MaxHealth;
	}
	OnRep_State();
}

void ASOExplosive::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
	Super::GetLifetimeReplicatedProps(OutLifetimeProps);
	DOREPLIFETIME(ASOExplosive, Kind);
	DOREPLIFETIME(ASOExplosive, bLit);
	DOREPLIFETIME(ASOExplosive, bSpent);
	DOREPLIFETIME(ASOExplosive, LeakAt);
	DOREPLIFETIME(ASOExplosive, LeakOut);
}

void ASOExplosive::OnRep_Kind()
{
	ApplyMesh();
}

FVector ASOExplosive::Middle() const
{
	const FBox Box = Mesh && Mesh->GetStaticMesh() ? Mesh->Bounds.GetBox() : FBox(GetActorLocation(), GetActorLocation() + FVector(0, 0, 90.0f));
	return Box.GetCenter();
}

float ASOExplosive::TakeHit(AActor* Source, float Amount, bool bBlast)
{
	if (!HasAuthority() || bSpent || Amount <= 0.0f)
	{
		return 0.0f;
	}
	const float Took = FMath::Min(Amount, FMath::Max(Health, 0.0f));
	Health -= Amount;
	// whoever hurt it owns its blast (a chain keeps the one who began it: a blast's instigator is passed on)
	if (Source && (!SetOffBy.IsValid() || !bBlast))
	{
		SetOffBy = Source;
	}
	const float Now = GetWorld()->GetTimeSeconds();
	if (Health <= 0.0f)
	{
		// a round through it: at once; another's blast: a beat later, so a row of them ripples
		const float Fuse = bBlast ? FMath::FRandRange(0.12f, 0.42f) : 0.04f;
		GoAt = GoAt >= 0.0f ? FMath::Min(GoAt, Now + Fuse) : Now + Fuse;
	}
	else if (!bLit && Health <= MaxHealth * 0.5f)
	{
		// holed: it leaks and the leak takes fire; it goes by itself a moment later
		const FSOHitInfo& Hit = USOCombatStatics::LastHit();
		const FTransform& T = GetActorTransform();
		const FVector Top = Middle() + FVector(0.0f, 0.0f, Mesh ? Mesh->Bounds.BoxExtent.Z * 0.8f : 40.0f);
		const FVector At = Hit.bKnown && FVector::DistSquared(Hit.Point, Middle()) < FMath::Square(400.0f) ? Hit.Point : Top;
		LeakAt = T.InverseTransformPosition(At);
		const FVector Out = (At - Middle()).GetSafeNormal();
		LeakOut = T.InverseTransformVectorNoScale(Out.IsNearlyZero() ? FVector::UpVector : Out);
		bLit = true;
		GoAt = Now + BurnFuse;
		OnRep_State();
	}
	return Took;
}

void ASOExplosive::Detonate()
{
	if (!HasAuthority() || bSpent)
	{
		return;
	}
	bSpent = true;
	bLit = false;
	GoAt = -1.0f;
	++NumDetonated;
	const FVector At = Middle();
	const FKindLook Look = LookOf(Kind);
	// what it does: a round's splash, its instigator whoever set it off (the others in reach are set off by it)
	if (USOProjectileSubsystem* Rounds = GetWorld()->GetSubsystem<USOProjectileSubsystem>())
	{
		Rounds->ApplySplash(SetOffBy.Get(), At, Radius, Damage, this, nullptr);
	}
	// what it looks and sounds like, everywhere
	USOCue::Blast(this, At, FVector::UpVector, Radius * (Kind == ESOExplosiveKind::Vehicle ? 0.8f : 0.62f), Look.Blast, Look.Color);
	USOCue::Sound(this, Look.Sound, At, 1.0f, 0.05f, ESOSoundRange::Far);
	OnRep_State();
}

void ASOExplosive::OnRep_State()
{
	if (Light)
	{
		Light->SetVisibility(bLit && !bSpent);
		Light->SetLightColor(LookOf(Kind).Leak);
	}
	if (!bSpent || bShownSpent)
	{
		return;
	}
	bShownSpent = true;
	if (Kind == ESOExplosiveKind::Vehicle)
	{
		// the wreck is thrown up by its own blast, comes down, burns for a long time, black
		Leap = 0.0f;
		if (UWorld* World = GetWorld(); World && World->GetNetMode() != NM_DedicatedServer)
		{
			if (USOFxSubsystem* Fx = World->GetSubsystem<USOFxSubsystem>())
			{
				Fx->Burn(Middle(), FVector::UpVector, 170.0f, 22.0f);
			}
		}
		for (int32 i = 0; Mesh && i < Mesh->GetNumMaterials(); ++i)
		{
			if (UMaterialInstanceDynamic* D = Mesh->CreateAndSetMaterialInstanceDynamic(i))
			{
				D->SetVectorParameterValue(TEXT("BaseColorTint"), FLinearColor(0.10f, 0.09f, 0.085f));
				D->SetScalarParameterValue(TEXT("Grime"), 1.0f);
			}
		}
		return;
	}
	// a drum, a bottle, a cell: nothing is left of it (the blast scorched the ground under it)
	if (Mesh)
	{
		Mesh->SetHiddenInGame(true);
		Mesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	}
	if (HasAuthority())
	{
		SetLifeSpan(6.0f);
	}
}

void ASOExplosive::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	UWorld* World = GetWorld();
	if (!World)
	{
		return;
	}
	if (HasAuthority() && GoAt >= 0.0f && World->GetTimeSeconds() >= GoAt && !bSpent)
	{
		Detonate();
	}
	const bool bDraws = World->GetNetMode() != NM_DedicatedServer;
	// the leak: a jet of flame out of the hole, its glow, smoke rising off it, the hiss
	if (bLit && !bSpent && bDraws)
	{
		const FTransform& T = GetActorTransform();
		const FVector At = T.TransformPosition(LeakAt);
		const FVector Out = T.TransformVectorNoScale(LeakOut).GetSafeNormal();
		const FKindLook Look = LookOf(Kind);
		LeakTimer -= DeltaSeconds;
		if (USOFxSubsystem* Fx = World->GetSubsystem<USOFxSubsystem>(); Fx && LeakTimer <= 0.0f)
		{
			LeakTimer = 0.03f;
			FRandomStream R(FMath::Rand());
			for (int32 i = 0; i < 2; ++i)
			{
				FSOFxParticle Jet;
				Jet.Kind = ESOFxKind::Streak;
				Jet.Position = At;
				Jet.Velocity = (Out + R.VRand() * 0.18f + FVector(0, 0, 0.35f)).GetSafeNormal() * R.FRandRange(260.0f, 460.0f);
				Jet.Gravity = -260.0f;                               // (flame rises)
				Jet.Drag = 2.4f;
				Jet.Life = R.FRandRange(0.18f, 0.32f);
				Jet.Size0 = R.FRandRange(7.0f, 11.0f);
				Jet.Size1 = R.FRandRange(14.0f, 22.0f);
				Jet.Length = R.FRandRange(26.0f, 44.0f);
				Jet.Intensity0 = 3.2f;
				Jet.Intensity1 = 0.0f;
				Jet.Color = FMath::Lerp(Look.Leak, FLinearColor(1.0f, 0.92f, 0.7f), R.FRandRange(0.0f, 0.35f));
				Fx->Spawn(Jet);
			}
			FSOFxParticle Root;
			Root.Kind = ESOFxKind::Glow;
			Root.Position = At;
			Root.Life = 0.08f;
			Root.Size0 = Root.Size1 = R.FRandRange(14.0f, 20.0f);
			Root.Intensity0 = 2.4f;
			Root.Color = FLinearColor(1.0f, 0.85f, 0.55f);
			Fx->Spawn(Root);
			if (R.FRand() < 0.35f)
			{
				FSOFxParticle Smoke;
				Smoke.Kind = ESOFxKind::Smoke;
				Smoke.Position = At + Out * 20.0f;
				Smoke.Velocity = FVector(R.FRandRange(-20.0f, 20.0f), R.FRandRange(-20.0f, 20.0f), R.FRandRange(70.0f, 120.0f));
				Smoke.Drag = 0.6f;
				Smoke.Life = R.FRandRange(1.4f, 2.2f);
				Smoke.Size0 = 22.0f;
				Smoke.Size1 = 90.0f;
				Smoke.Intensity0 = 0.45f;
				Smoke.Color = FLinearColor(0.05f, 0.045f, 0.04f);
				Fx->Spawn(Smoke);
			}
		}
		HissTimer -= DeltaSeconds;
		if (HissTimer <= 0.0f)
		{
			HissTimer = 1.05f;
			USOSoundLibrary::PlayAt(this, TEXT("leak_hiss"), At, 0.85f, 0.06f, ESOSoundRange::Near);
		}
		if (Light)
		{
			Light->SetWorldLocation(At + Out * 25.0f);
			Light->SetIntensity(FMath::FRandRange(900.0f, 1700.0f));
		}
	}
	// a wreck thrown up by its blast: up, a turn in the air, down hard on its wheels a little askew, dust where it lands
	if (Leap >= 0.0f)
	{
		Leap = FMath::Min(Leap + DeltaSeconds, LeapTime);
		const float S = Leap / LeapTime;
		const float Up = 4.0f * LeapHeight * S * (1.0f - S);
		const float Settle = FMath::Sin(S * UE_PI);
		const FRotator Turn(4.0f * S + 9.0f * Settle, 11.0f * S, 6.0f * S + 14.0f * Settle);
		SetActorLocationAndRotation(Home + FVector(0.0f, 0.0f, Up), HomeTurn + Turn);
		if (Leap >= LeapTime)
		{
			Leap = -1.0f;
			if (USOFxSubsystem* Fx = bDraws ? World->GetSubsystem<USOFxSubsystem>() : nullptr)
			{
				Fx->Shockwave(Home + FVector(0, 0, 10.0f), 420.0f, FLinearColor(0.55f, 0.5f, 0.45f));
			}
			USOSoundLibrary::PlayAt(this, TEXT("move_land_hard"), Home, 1.0f, 0.05f, ESOSoundRange::Near);
		}
	}
}
