#include "SOFxSubsystem.h"

#include "Camera/PlayerCameraManager.h"
#include "Components/DecalComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/PointLightComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInterface.h"
#include "SOSound.h"

namespace
{
	const TCHAR* CardMeshes[] = { TEXT("/Game/FX/SM_FX_Quad.SM_FX_Quad"), TEXT("/Game/FX/SM_FX_Streak.SM_FX_Streak"),
		TEXT("/Game/FX/SM_FX_Star.SM_FX_Star"), TEXT("/Game/FX/SM_FX_Quad.SM_FX_Quad") };
	const TCHAR* CardMaterials[] = { TEXT("/Game/FX/MI_FxGlow.MI_FxGlow"), TEXT("/Game/FX/MI_FxStreak.MI_FxStreak"),
		TEXT("/Game/FX/MI_FxFlash.MI_FxFlash"), TEXT("/Game/FX/MI_FxSmoke.MI_FxSmoke") };
	const TCHAR* DecalMaterial = TEXT("/Game/FX/M_SOBulletHole.M_SOBulletHole");
	const FLinearColor Spark(1.0f, 0.62f, 0.25f);
	const FLinearColor Fire(1.0f, 0.74f, 0.4f);
}

bool USOFxSubsystem::DoesSupportWorldType(const EWorldType::Type WorldType) const
{
	return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

TStatId USOFxSubsystem::GetStatId() const
{
	RETURN_QUICK_DECLARE_CYCLE_STAT(USOFxSubsystem, STATGROUP_Tickables);
}

void USOFxSubsystem::Deinitialize()
{
	if (AActor* Actor = Host.Get())
	{
		Actor->Destroy();
	}
	Super::Deinitialize();
}

bool USOFxSubsystem::EnsureHost()
{
	if (Host.IsValid())
	{
		return true;
	}
	UWorld* World = GetWorld();
	if (!World || World->bIsTearingDown || World->GetNetMode() == NM_DedicatedServer)
	{
		return false;
	}
	FActorSpawnParameters Params;
	Params.Name = MakeUniqueObjectName(World, AActor::StaticClass(), TEXT("SOFxHost"));
	Params.ObjectFlags = RF_Transient;
	AActor* Actor = World->SpawnActor<AActor>(AActor::StaticClass(), FTransform::Identity, Params);
	if (!Actor)
	{
		return false;
	}
	USceneComponent* Root = NewObject<USceneComponent>(Actor, TEXT("Root"));
	Actor->SetRootComponent(Root);
	Root->RegisterComponent();
	for (int32 k = 0; k < static_cast<int32>(ESOFxKind::Count); ++k)
	{
		UInstancedStaticMeshComponent* ISM = NewObject<UInstancedStaticMeshComponent>(Actor);
		ISM->SetupAttachment(Root);
		ISM->SetStaticMesh(Cast<UStaticMesh>(FSoftObjectPath(CardMeshes[k]).TryLoad()));
		ISM->SetMaterial(0, Cast<UMaterialInterface>(FSoftObjectPath(CardMaterials[k]).TryLoad()));
		ISM->NumCustomDataFloats = 4;
		ISM->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		ISM->SetCastShadow(false);
		ISM->bAffectDistanceFieldLighting = false;
		ISM->SetMobility(EComponentMobility::Movable);
		ISM->TranslucencySortPriority = k == static_cast<int32>(ESOFxKind::Smoke) ? 0 : 1;
		ISM->RegisterComponent();
		Cards[k] = ISM;
	}
	Host = Actor;
	return true;
}

void USOFxSubsystem::Spawn(const FSOFxParticle& Particle)
{
	if (Particles.Num() >= MaxParticles)
	{
		Particles.RemoveAt(0, 1, EAllowShrinking::No);
	}
	Particles.Add(Particle);
}

int32 USOFxSubsystem::GetNumDecals() const
{
	int32 Count = 0;
	for (const TWeakObjectPtr<UDecalComponent>& D : Decals)
	{
		Count += D.IsValid() && D->IsVisible();
	}
	return Count;
}

// --- Effects -------------------------------------------------------------------------------------

void USOFxSubsystem::MuzzleFlash(const FVector& Muzzle, const FVector& Dir, float Scale)
{
	const FVector D = Dir.GetSafeNormal();
	FSOFxParticle Star;
	Star.Kind = ESOFxKind::Star;
	Star.Position = Muzzle;
	Star.Axis = D;
	Star.Life = 0.05f;
	Star.Length = Random.FRandRange(32.0f, 46.0f) * Scale;
	Star.Size0 = Star.Size1 = Random.FRandRange(18.0f, 26.0f) * Scale;
	Star.Intensity0 = 40.0f;
	Star.Intensity1 = 0.0f;
	Star.Color = Fire;
	Star.Spin = Random.FRandRange(0.0f, 360.0f);
	Spawn(Star);

	FSOFxParticle Core;
	Core.Kind = ESOFxKind::Glow;
	Core.Position = Muzzle + D * 4.0f * Scale;
	Core.Life = 0.045f;
	Core.Size0 = 26.0f * Scale;
	Core.Size1 = 12.0f * Scale;
	Core.Intensity0 = 30.0f;
	Core.Color = Fire;
	Spawn(Core);

	for (int32 i = 0; i < 2; ++i)
	{
		FSOFxParticle Wisp;
		Wisp.Kind = ESOFxKind::Smoke;
		Wisp.Position = Muzzle + D * (6.0f + i * 8.0f) * Scale;
		Wisp.Velocity = D * Random.FRandRange(60.0f, 140.0f) + FVector(0, 0, 25.0f) + Random.VRand() * 15.0f;
		Wisp.Drag = 2.5f;
		Wisp.Life = Random.FRandRange(0.5f, 0.8f);
		Wisp.Size0 = 6.0f * Scale;
		Wisp.Size1 = 34.0f * Scale;
		Wisp.Intensity0 = 0.22f;
		Wisp.Color = FLinearColor(0.55f, 0.55f, 0.56f);
		Wisp.Spin = Random.FRandRange(0.0f, 360.0f);
		Spawn(Wisp);
	}
	FlashLight(Muzzle + D * 10.0f, 220.0f * Scale, Fire, 0.05f);
}

void USOFxSubsystem::Tracer(const FVector& From, const FVector& To, float Speed, const FLinearColor& Color, float Width)
{
	const FVector Path = To - From;
	const float Distance = Path.Size();
	if (Distance < 200.0f || Speed <= 0.0f)
	{
		return;
	}
	FSOFxParticle T;
	T.Kind = ESOFxKind::Streak;
	T.Position = From;
	T.Axis = Path / Distance;
	T.Velocity = T.Axis * Speed;
	T.Life = Distance / Speed;
	T.Length = 380.0f;
	T.Size0 = T.Size1 = Width;
	T.Intensity0 = T.Intensity1 = 22.0f;
	T.Color = Color;
	Spawn(T);
}

void USOFxSubsystem::Trail(const FVector& From, const FVector& Velocity, float Gravity, float FlightTime, ETrail Kind, const FLinearColor& Color)
{
	if (FlightTime <= 0.0f)
	{
		return;
	}
	const bool bRocket = Kind == ETrail::Rocket;
	// The head: particles follow ballistic arcs on their own (velocity + gravity, no drag).
	FSOFxParticle Head;
	Head.Kind = ESOFxKind::Glow;
	Head.Position = From;
	Head.Velocity = Velocity;
	Head.Gravity = Gravity;
	Head.Life = FlightTime;
	Head.Size0 = Head.Size1 = bRocket ? 26.0f : (Kind == ETrail::Brood ? 22.0f : 12.0f);
	Head.Intensity0 = Head.Intensity1 = bRocket ? 40.0f : 9.0f;
	Head.Color = Color;
	Spawn(Head);
	if (Kind != ETrail::Rocket)
	{
		FSOFxParticle Core = Head; // a darker, wet core inside the glow
		Core.Kind = ESOFxKind::Smoke;
		Core.Size0 = Core.Size1 = Head.Size0 * 0.6f;
		Core.Intensity0 = Core.Intensity1 = 1.0f;
		Core.Color = Color * 0.35f;
		Spawn(Core);
	}
	// Behind it: smoke puffs (rocket) or drips (goo) released along the path at the time the head passes.
	const float Step = bRocket ? 0.018f : 0.05f;
	for (float T = Step; T < FlightTime; T += Step)
	{
		const FVector At = From + Velocity * T + FVector(0.0f, 0.0f, -0.5f * Gravity * T * T);
		FSOFxParticle P;
		P.Position = At;
		P.Delay = T;
		if (bRocket)
		{
			P.Kind = ESOFxKind::Smoke;
			P.Velocity = Random.VRand() * 25.0f + FVector(0, 0, 20.0f);
			P.Drag = 1.5f;
			P.Life = Random.FRandRange(0.9f, 1.6f);
			P.Size0 = 14.0f;
			P.Size1 = Random.FRandRange(60.0f, 95.0f);
			P.Intensity0 = 0.55f;
			P.Color = FLinearColor(0.42f, 0.41f, 0.4f);
			P.Spin = Random.FRandRange(0.0f, 360.0f);
			Spawn(P);
			FSOFxParticle Ember = P;
			Ember.Kind = ESOFxKind::Glow;
			Ember.Life = 0.12f;
			Ember.Size0 = 18.0f;
			Ember.Size1 = 6.0f;
			Ember.Intensity0 = 16.0f;
			Ember.Color = Fire;
			Spawn(Ember);
		}
		else
		{
			P.Kind = ESOFxKind::Smoke;
			P.Velocity = Velocity * 0.05f + Random.VRand() * 20.0f;
			P.Gravity = 980.0f;
			P.Life = Random.FRandRange(0.4f, 0.8f);
			P.Size0 = Random.FRandRange(2.5f, 4.5f);
			P.Size1 = P.Size0 * 0.7f;
			P.Intensity0 = 1.0f;
			P.Intensity1 = 0.6f;
			P.Color = Color * 0.6f;
			Spawn(P);
		}
	}
}

void USOFxSubsystem::Blast(const FVector& Point, const FVector& Normal, float Radius, EBlast Kind, const FLinearColor& Color, float Delay)
{
	const FVector N = Normal.IsNearlyZero() ? FVector::UpVector : Normal.GetSafeNormal();
	const float R = FMath::Max(Radius, 30.0f);
	const int32 Sparks = Kind == EBlast::Fire ? 28 : (Kind == EBlast::Zap ? 14 : 10);
	// flash / fireball core
	for (int32 i = 0; i < (Kind == EBlast::Fire ? 6 : 3); ++i)
	{
		FSOFxParticle Core;
		Core.Kind = ESOFxKind::Glow;
		Core.Position = Point + N * R * 0.15f + Random.VRand() * R * 0.15f;
		Core.Velocity = Random.VRand() * R * 0.6f;
		Core.Drag = 5.0f;
		Core.Delay = Delay;
		Core.Life = Kind == EBlast::Fire ? Random.FRandRange(0.18f, 0.32f) : 0.16f;
		Core.Size0 = R * 0.5f;
		Core.Size1 = R * (Kind == EBlast::Fire ? 1.1f : 0.6f);
		Core.Intensity0 = Kind == EBlast::Fire ? 30.0f : 14.0f;
		Core.Color = Color;
		Spawn(Core);
	}
	// sparks / spatter
	for (int32 i = 0; i < Sparks; ++i)
	{
		FSOFxParticle S;
		S.Kind = Kind == EBlast::Acid ? ESOFxKind::Smoke : ESOFxKind::Streak;
		S.Position = Point + N * 2.0f;
		S.Velocity = Random.VRandCone(N, FMath::DegreesToRadians(75.0f)) * Random.FRandRange(R * 2.0f, R * 6.0f);
		S.Gravity = 980.0f;
		S.Drag = Kind == EBlast::Acid ? 0.5f : 1.5f;
		S.Delay = Delay;
		S.Life = Random.FRandRange(0.3f, 0.7f);
		S.Size0 = Kind == EBlast::Acid ? Random.FRandRange(3.0f, 6.0f) : 1.6f;
		S.Size1 = S.Size0 * 0.6f;
		S.Intensity0 = Kind == EBlast::Acid ? 1.0f : 30.0f;
		S.Color = Kind == EBlast::Fire ? Spark : Color;
		Spawn(S);
	}
	// smoke / acid mist
	for (int32 i = 0; i < (Kind == EBlast::Fire ? 10 : 5); ++i)
	{
		FSOFxParticle M;
		M.Kind = ESOFxKind::Smoke;
		M.Position = Point + N * R * 0.2f + Random.VRand() * R * 0.3f;
		M.Velocity = (N * 0.7f + Random.VRand() * 0.6f) * R * 0.9f;
		M.Drag = 2.5f;
		M.Delay = Delay + Random.FRandRange(0.02f, 0.12f);
		M.Life = Random.FRandRange(1.2f, 2.4f);
		M.Size0 = R * 0.3f;
		M.Size1 = R * Random.FRandRange(1.0f, 1.6f);
		M.Intensity0 = Kind == EBlast::Fire ? 0.6f : 0.45f;
		M.Color = Kind == EBlast::Fire ? FLinearColor(0.16f, 0.15f, 0.14f) : Color * 0.5f;
		M.Spin = Random.FRandRange(0.0f, 360.0f);
		Spawn(M);
	}
	const float Light = Kind == EBlast::Fire ? 2600.0f : 500.0f;
	PendingLights.Add({ Point + N * 30.0f, Kind == EBlast::Fire ? Fire : Color, Light, Kind == EBlast::Fire ? 0.25f : 0.12f, Delay });
}

void USOFxSubsystem::Impact(const FVector& Point, const FVector& Normal, bool bFlesh, const FLinearColor& Blood, float Delay, bool bDecal)
{
	if (Delay > 0.0f)
	{
		Pending.Add({ Point, Normal.GetSafeNormal(), Blood, Delay, bFlesh, bDecal });
		return;
	}
	++ImpactsPlayed;
	const FVector N = Normal.GetSafeNormal();
	if (bFlesh)
	{
		for (int32 i = 0; i < 4; ++i)
		{
			FSOFxParticle Mist;
			Mist.Kind = ESOFxKind::Smoke;
			Mist.Position = Point + N * 3.0f;
			Mist.Velocity = N * Random.FRandRange(60.0f, 180.0f) + Random.VRand() * 60.0f;
			Mist.Drag = 4.0f;
			Mist.Life = Random.FRandRange(0.35f, 0.6f);
			Mist.Size0 = 8.0f;
			Mist.Size1 = Random.FRandRange(30.0f, 50.0f);
			Mist.Intensity0 = 0.85f;
			Mist.Color = Blood;
			Mist.Spin = Random.FRandRange(0.0f, 360.0f);
			Spawn(Mist);
		}
		for (int32 i = 0; i < 8; ++i)
		{
			FSOFxParticle Drop;
			Drop.Kind = ESOFxKind::Smoke;
			Drop.Position = Point;
			Drop.Velocity = Random.VRandCone(N, FMath::DegreesToRadians(55.0f)) * Random.FRandRange(250.0f, 650.0f);
			Drop.Gravity = 980.0f;
			Drop.Life = Random.FRandRange(0.4f, 0.7f);
			Drop.Size0 = Random.FRandRange(2.5f, 4.0f);
			Drop.Size1 = Drop.Size0 * 0.6f;
			Drop.Intensity0 = 1.0f;
			Drop.Intensity1 = 0.7f;
			Drop.Color = Blood * 0.7f;
			Spawn(Drop);
		}
		USOSoundLibrary::PlayAt(this, TEXT("impact_flesh"), Point, 0.9f, 0.08f, ESOSoundRange::Near);
		return;
	}

	for (int32 i = 0; i < 10; ++i)
	{
		FSOFxParticle S;
		S.Kind = ESOFxKind::Streak;
		S.Position = Point + N * 1.0f;
		S.Velocity = Random.VRandCone(N, FMath::DegreesToRadians(65.0f)) * Random.FRandRange(500.0f, 1700.0f);
		S.Gravity = 980.0f;
		S.Drag = 2.0f;
		S.Life = Random.FRandRange(0.15f, 0.4f);
		S.Size0 = S.Size1 = 1.3f;
		S.Intensity0 = 35.0f;
		S.Color = Spark;
		Spawn(S);
	}
	FSOFxParticle Hot;
	Hot.Kind = ESOFxKind::Glow;
	Hot.Position = Point + N * 2.0f;
	Hot.Life = 0.07f;
	Hot.Size0 = 18.0f;
	Hot.Size1 = 6.0f;
	Hot.Intensity0 = 25.0f;
	Hot.Color = Spark;
	Spawn(Hot);
	for (int32 i = 0; i < 3; ++i)
	{
		FSOFxParticle Dust;
		Dust.Kind = ESOFxKind::Smoke;
		Dust.Position = Point + N * 4.0f;
		Dust.Velocity = N * Random.FRandRange(60.0f, 170.0f) + Random.VRand() * 40.0f;
		Dust.Drag = 3.0f;
		Dust.Gravity = -10.0f;
		Dust.Life = Random.FRandRange(0.7f, 1.1f);
		Dust.Size0 = 10.0f;
		Dust.Size1 = Random.FRandRange(45.0f, 70.0f);
		Dust.Intensity0 = 0.5f;
		Dust.Color = FLinearColor(0.46f, 0.43f, 0.39f);
		Dust.Spin = Random.FRandRange(0.0f, 360.0f);
		Spawn(Dust);
	}
	if (bDecal)
	{
		AddDecal(Point, N);
	}
	USOSoundLibrary::PlayAt(this, TEXT("impact_hard"), Point, 0.8f, 0.1f, ESOSoundRange::Near);
}

void USOFxSubsystem::Pool(const FVector& Point, const FVector& Normal, float Radius, const FLinearColor& Color, float Delay, float Duration)
{
	const UWorld* World = GetWorld();
	if (!World || World->GetNetMode() == NM_DedicatedServer)
	{
		return;
	}
	const float Now = World->GetTimeSeconds();
	PoolMarks.RemoveAll([Now](const FPoolMark& M) { return M.Until < Now; });
	for (const FPoolMark& M : PoolMarks)
	{
		if (FVector::DistSquared(M.Point, Point) < FMath::Square(M.Radius * 0.55f) && Now + Delay - M.Born < 1.5f)
		{
			return; // the same puddle (shotgun pellets, rapid fire): it already looks like this
		}
	}
	PoolMarks.Add({ Point, Radius, Now + Delay, Now + Delay + Duration });

	const FVector N = Normal.GetSafeNormal();
	const FVector T = FVector::CrossProduct(N, FMath::Abs(N.Z) < 0.9f ? FVector::UpVector : FVector::ForwardVector).GetSafeNormal();
	const FVector B = FVector::CrossProduct(N, T);
	auto InDisk = [&](float Spread)
	{
		const float A = Random.FRandRange(0.0f, 2.0f * PI);
		const float R = Radius * Spread * FMath::Sqrt(Random.FRand());
		return Point + (T * FMath::Cos(A) + B * FMath::Sin(A)) * R;
	};
	const FLinearColor Dark = Color * 0.28f;
	// the puddle: overlapping dark blobs of goo (stacked a hair apart so they never fight the floor)
	const int32 Blobs = FMath::Clamp(FMath::RoundToInt(Radius / 35.0f), 4, 14);
	for (int32 i = 0; i < Blobs; ++i)
	{
		FSOFxParticle P;
		P.Kind = ESOFxKind::Smoke;
		P.bFlat = true;
		P.bHold = true;
		P.Axis = N;
		P.Position = (i == 0 ? Point : InDisk(0.6f)) + N * (1.2f + 0.15f * i);
		P.Life = Duration + Random.FRandRange(-0.4f, 0.0f);
		P.Delay = Delay;
		P.Size0 = Radius * (i == 0 ? 1.7f : Random.FRandRange(0.7f, 1.15f));
		P.Size1 = P.Size0 * 1.08f;
		P.Intensity0 = 0.9f;
		P.Color = Dark;
		P.Spin = Random.FRandRange(0.0f, 360.0f);
		Spawn(P);
	}
	// glowing acid at the heart of the puddle
	for (int32 i = 0; i < FMath::Max(2, Blobs / 2); ++i)
	{
		FSOFxParticle P;
		P.Kind = ESOFxKind::Glow;
		P.bFlat = true;
		P.bHold = true;
		P.Axis = N;
		P.Position = InDisk(0.55f) + N * 3.5f;
		P.Life = Duration * Random.FRandRange(0.8f, 1.0f);
		P.Delay = Delay;
		P.Size0 = Radius * Random.FRandRange(0.5f, 0.9f);
		P.Size1 = P.Size0 * 0.7f;
		P.Intensity0 = 1.6f;
		P.Color = Color;
		P.Spin = Random.FRandRange(0.0f, 360.0f);
		Spawn(P);
	}
	// bubbles popping and fumes rising off it while it lasts
	const int32 Fumes = FMath::Clamp(FMath::RoundToInt(Radius / 18.0f), 5, 28);
	for (int32 i = 0; i < Fumes; ++i)
	{
		const float At = Delay + Random.FRandRange(0.1f, FMath::Max(0.2f, Duration - 0.8f));
		FSOFxParticle Fume;
		Fume.Kind = ESOFxKind::Smoke;
		Fume.Position = InDisk(0.8f) + N * 8.0f;
		Fume.Velocity = N * Random.FRandRange(25.0f, 55.0f) + FMath::VRand() * 8.0f;
		Fume.Drag = 0.6f;
		Fume.Life = Random.FRandRange(1.2f, 2.0f);
		Fume.Delay = At;
		Fume.Size0 = Random.FRandRange(14.0f, 24.0f);
		Fume.Size1 = Fume.Size0 * 3.0f;
		Fume.Intensity0 = 0.32f;
		Fume.Color = Color * 0.55f;
		Fume.Spin = Random.FRandRange(0.0f, 360.0f);
		Spawn(Fume);
		FSOFxParticle Pop;
		Pop.Kind = ESOFxKind::Glow;
		Pop.Position = Fume.Position - N * 4.0f;
		Pop.Life = 0.22f;
		Pop.Delay = At;
		Pop.Size0 = 3.0f;
		Pop.Size1 = 9.0f;
		Pop.Intensity0 = 3.0f;
		Pop.Color = Color;
		Spawn(Pop);
	}
}

void USOFxSubsystem::AddDecal(const FVector& Point, const FVector& Normal)
{
	if (!EnsureHost())
	{
		return;
	}
	UDecalComponent* Decal = nullptr;
	if (Decals.Num() < MaxDecals)
	{
		Decal = NewObject<UDecalComponent>(Host.Get());
		Decal->SetDecalMaterial(Cast<UMaterialInterface>(FSoftObjectPath(DecalMaterial).TryLoad()));
		Decal->DecalSize = FVector(4.0f, 4.5f, 4.5f);
		Decal->SetFadeScreenSize(0.002f);
		Decal->RegisterComponent();
		Decals.Add(Decal);
	}
	else
	{
		Decal = Decals[NextDecal].Get();
		NextDecal = (NextDecal + 1) % MaxDecals;
	}
	if (!Decal)
	{
		return;
	}
	FRotator Rot = (-Normal).Rotation();
	Rot.Roll = Random.FRandRange(0.0f, 360.0f);
	Decal->SetWorldLocationAndRotation(Point, Rot);
	Decal->SetWorldScale3D(FVector(1.0f, Random.FRandRange(0.8f, 1.2f), Random.FRandRange(0.8f, 1.2f)));
	Decal->SetVisibility(true);
	Decal->SetFadeOut(25.0f, 4.0f, false);
}

void USOFxSubsystem::FlashLight(const FVector& Point, float Intensity, const FLinearColor& Color, float Duration)
{
	if (!EnsureHost())
	{
		return;
	}
	if (Lights.Num() < 4)
	{
		UPointLightComponent* Light = NewObject<UPointLightComponent>(Host.Get());
		Light->SetCastShadows(false);
		Light->SetIntensityUnits(ELightUnits::Candelas);
		Light->SetAttenuationRadius(450.0f);
		Light->SetIntensity(0.0f);
		Light->RegisterComponent();
		Lights.Add({ Light, 1.0f, 0.0f, 0.0f });
	}
	FLightFlash& Flash = Lights[NextLight];
	NextLight = (NextLight + 1) % Lights.Num();
	if (UPointLightComponent* Light = Flash.Light.Get())
	{
		Light->SetWorldLocation(Point);
		Light->SetAttenuationRadius(Intensity > 1000.0f ? 1600.0f : 450.0f); // explosions light the surroundings
		Light->SetLightColor(Color);
		Light->SetIntensity(Intensity);
		Flash.Age = 0.0f;
		Flash.Life = Duration;
		Flash.Peak = Intensity;
	}
}

// --- Simulation + drawing ------------------------------------------------------------------------

void USOFxSubsystem::Tick(float DeltaTime)
{
	for (int32 i = Pending.Num() - 1; i >= 0; --i)
	{
		Pending[i].Delay -= DeltaTime;
		if (Pending[i].Delay <= 0.0f)
		{
			const FPendingImpact P = Pending[i];
			Pending.RemoveAtSwap(i, 1, EAllowShrinking::No);
			Impact(P.Point, P.Normal, P.bFlesh, P.Blood, 0.0f, P.bDecal);
		}
	}
	for (int32 i = PendingLights.Num() - 1; i >= 0; --i)
	{
		PendingLights[i].Delay -= DeltaTime;
		if (PendingLights[i].Delay <= 0.0f)
		{
			const FPendingLight L = PendingLights[i];
			PendingLights.RemoveAtSwap(i, 1, EAllowShrinking::No);
			FlashLight(L.Point, L.Intensity, L.Color, L.Duration);
		}
	}
	for (FLightFlash& Flash : Lights)
	{
		if (UPointLightComponent* Light = Flash.Light.Get(); Light && Flash.Life > 0.0f)
		{
			Flash.Age += DeltaTime;
			const float K = FMath::Clamp(1.0f - Flash.Age / Flash.Life, 0.0f, 1.0f);
			Light->SetIntensity(Flash.Peak * K * K);
			if (K <= 0.0f)
			{
				Flash.Life = 0.0f;
			}
		}
	}

	for (int32 i = Particles.Num() - 1; i >= 0; --i)
	{
		FSOFxParticle& P = Particles[i];
		if (P.Delay > 0.0f)
		{
			P.Delay -= DeltaTime;
			continue;
		}
		P.Age += DeltaTime;
		if (P.Age >= P.Life)
		{
			Particles.RemoveAtSwap(i, 1, EAllowShrinking::No);
			continue;
		}
		P.Velocity.Z -= P.Gravity * DeltaTime;
		P.Velocity *= FMath::Exp(-P.Drag * DeltaTime);
		P.Position += P.Velocity * DeltaTime;
	}

	if (Particles.Num() == 0 && !Host.IsValid())
	{
		return;
	}
	if (!EnsureHost())
	{
		return;
	}

	FVector Eye = FVector::ZeroVector;
	FVector Up = FVector::UpVector;
	if (APlayerCameraManager* Camera = UGameplayStatics::GetPlayerCameraManager(GetWorld(), 0))
	{
		Eye = Camera->GetCameraLocation();
		Up = Camera->GetCameraRotation().Quaternion().GetUpVector();
	}

	TArray<FTransform> Transforms[static_cast<int32>(ESOFxKind::Count)];
	TArray<float> Custom[static_cast<int32>(ESOFxKind::Count)];
	for (const FSOFxParticle& P : Particles)
	{
		if (P.Delay > 0.0f)
		{
			continue;
		}
		const float A = FMath::Clamp(P.Age / FMath::Max(P.Life, 1e-4f), 0.0f, 1.0f);
		const float Size = FMath::Lerp(P.Size0, P.Size1, A);
		const float Intensity = P.bHold ? P.Intensity0 * FMath::Min(1.0f, A * 14.0f) * FMath::Min(1.0f, (1.0f - A) * 4.0f)
			: FMath::Lerp(P.Intensity0, P.Intensity1, A);
		const FVector ToEye = (Eye - P.Position).GetSafeNormal();
		FTransform T;
		switch (P.Kind)
		{
		case ESOFxKind::Streak:
		{
			// Card along +Y (tail at the origin), facing the eye around its own axis.
			const FVector Dir = (P.Length > 0.0f ? P.Axis : P.Velocity.GetSafeNormal());
			const float Length = P.Length > 0.0f ? FMath::Min(P.Length, P.Velocity.Size() * P.Age + 1.0f) : FMath::Clamp(P.Velocity.Size() * 0.03f, 2.0f, 60.0f);
			T = FTransform(FRotationMatrix::MakeFromYX(Dir, ToEye).ToQuat(), P.Position - Dir * Length, FVector(1.0f, Length / 100.0f, Size / 100.0f));
			break;
		}
		case ESOFxKind::Star:
		{
			const FQuat Base = FRotationMatrix::MakeFromYZ(P.Axis, FVector::UpVector).ToQuat();
			const FQuat Roll(P.Axis, FMath::DegreesToRadians(P.Spin));
			T = FTransform(Roll * Base, P.Position, FVector(Size / 100.0f, P.Length / 100.0f, Size / 100.0f));
			break;
		}
		default:
			if (P.bFlat)
			{
				// lying on the surface: the card faces along its normal, turned by Spin about it
				const FVector N = P.Axis.GetSafeNormal();
				const FVector Side = FVector::CrossProduct(N, FMath::Abs(N.Z) < 0.9f ? FVector::UpVector : FVector::ForwardVector).GetSafeNormal();
				const FVector Turned = FQuat(N, FMath::DegreesToRadians(P.Spin)).RotateVector(Side);
				T = FTransform(FRotationMatrix::MakeFromYZ(N, Turned).ToQuat(), P.Position, FVector(Size / 100.0f));
				break;
			}
		{
			const FVector SpunUp = FQuat(ToEye, FMath::DegreesToRadians(P.Spin + A * 40.0f)).RotateVector(Up);
			T = FTransform(FRotationMatrix::MakeFromYZ(ToEye, SpunUp).ToQuat(), P.Position, FVector(Size / 100.0f));
			break;
		}
		}
		const int32 K = static_cast<int32>(P.Kind);
		Transforms[K].Add(T);
		Custom[K].Append({ P.Color.R, P.Color.G, P.Color.B, Intensity });
	}

	for (int32 K = 0; K < static_cast<int32>(ESOFxKind::Count); ++K)
	{
		UInstancedStaticMeshComponent* ISM = Cards[K].Get();
		if (!ISM)
		{
			continue;
		}
		ISM->ClearInstances();
		if (Transforms[K].Num() == 0)
		{
			continue;
		}
		ISM->AddInstances(Transforms[K], false, true, false);
		for (int32 i = 0; i < Transforms[K].Num(); ++i)
		{
			ISM->SetCustomData(i, MakeArrayView(Custom[K].GetData() + i * 4, 4), false);
		}
		ISM->MarkRenderStateDirty();
	}
}
