#include "SOFxSubsystem.h"

#include "Camera/PlayerCameraManager.h"
#include "Components/DecalComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/PointLightComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "SOSound.h"

namespace
{
	const TCHAR* CardMeshes[] = { TEXT("/Game/FX/SM_FX_Quad.SM_FX_Quad"), TEXT("/Game/FX/SM_FX_Streak.SM_FX_Streak"),
		TEXT("/Game/FX/SM_FX_Star.SM_FX_Star"), TEXT("/Game/FX/SM_FX_Quad.SM_FX_Quad") };
	const TCHAR* CardMaterials[] = { TEXT("/Game/FX/MI_FxGlow.MI_FxGlow"), TEXT("/Game/FX/MI_FxStreak.MI_FxStreak"),
		TEXT("/Game/FX/MI_FxFlash.MI_FxFlash"), TEXT("/Game/FX/MI_FxSmoke.MI_FxSmoke") };
	const TCHAR* DecalMaterial = TEXT("/Game/FX/M_SOBulletHole.M_SOBulletHole");
	const TCHAR* WarnMaterial = TEXT("/Game/FX/M_SOWarn.M_SOWarn");
	const float WarnFade = 0.2f; // seconds a warning takes to go once it has landed
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

void USOFxSubsystem::MuzzleFlash(const FVector& Muzzle, const FVector& Dir, float Scale, bool bViewmodel, const FLinearColor& Color, bool bThroughScope)
{
	const FVector D = Dir.GetSafeNormal();
	if (bThroughScope)
	{
		// down a scope the muzzle is a hand's width from the glass and magnified with everything else: nothing is drawn
		// there (the shot is felt in the kick and seen in the tracer)
		return;
	}
	// Tongues of flame: the card is five thin blades about the bore (the shader shapes each to a point and tears
	// it), a different length and turn every shot, gone in three frames.
	FSOFxParticle Star;
	Star.Kind = ESOFxKind::Star;
	Star.Position = Muzzle;
	Star.Axis = D;
	Star.Life = Random.FRandRange(0.035f, 0.055f);
	Star.Length = Random.FRandRange(20.0f, 34.0f) * Scale;
	Star.Size0 = Star.Size1 = Random.FRandRange(9.0f, 14.0f) * Scale;
	Star.Intensity0 = 13.0f;                  // (more than this burns every colour to white)
	Star.Intensity1 = 0.0f;
	Star.Color = Color;
	Star.Spin = Random.FRandRange(0.0f, 360.0f);
	Spawn(Star);

	FSOFxParticle Core;
	Core.Kind = ESOFxKind::Glow;
	Core.Position = Muzzle + D * 3.0f * Scale;
	Core.Life = 0.04f;
	Core.Size0 = 15.0f * Scale;
	Core.Size1 = 6.0f * Scale;
	Core.Intensity0 = 11.0f;
	Core.Color = FMath::Lerp(Color, FLinearColor::White, 0.25f);
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
	// The flash lights the surroundings; for the gun in your own hands it sits well ahead of the muzzle and gentler,
	// so the gun itself does not flare white on every shot.
	// the light of the flash, in its own colour. In first person it stands well ahead of the muzzle and under the
	// bore: beside the muzzle it raked along the top of the gun and every grain of its finish sparkled.
	FlashLight(Muzzle + D * (bViewmodel ? 120.0f : 10.0f) - FVector(0.0f, 0.0f, bViewmodel ? 22.0f : 0.0f), 220.0f * Scale * (bViewmodel ? 0.25f : 1.0f),
		FMath::Lerp(Color, Fire, 0.35f), 0.05f);
}

void USOFxSubsystem::PlasmaBolt(const FVector& From, const FVector& To, float Speed, const FLinearColor& Color, float Size, const FVector& Carry)
{
	if (FVector::Dist(From, To) < 60.0f || Speed <= 0.0f)
	{
		return;
	}
	++PlasmaBolts;
	// The shot is drawn in the SHOOTER's frame: the bolt, its trail and its breaths of glowing air all carry the
	// shooter's own velocity (Carry), as a round leaves a moving gun with the gun's speed added. Drawn fixed in the
	// world, a player strafing or walking while firing left every trail hanging where the gun had been, a metre and
	// more beside the barrel (the owner: "the bullets don't seem to come out of the gun's barrel" on the move). The
	// bolt is aimed so that it still lands on To as it ends: from the shooter it flies toward where To will be.
	const float Flight = FVector::Dist(From, To) / Speed;
	const FVector Path = To - From - Carry * Flight;
	const float Distance = FMath::Max(static_cast<float>(Path.Size()), 1.0f);
	const FVector Axis = Path / Distance;
	const float Rel = Distance / Flight;                  // (its speed against the shooter)
	// the tail: short and thick at a rifle bolt's speed, drawn out into a lance by a fast one
	const float Length = FMath::Min(FMath::Clamp(Speed * 0.0058f, 90.0f, 620.0f) * Size, Distance);
	FSOFxParticle Tail;
	Tail.Kind = ESOFxKind::Streak;
	Tail.Position = From;
	Tail.Axis = Axis;
	Tail.Velocity = Axis * Rel + Carry;
	Tail.Life = Flight;
	Tail.Length = Length;
	Tail.Size0 = Tail.Size1 = 8.0f * Size;
	Tail.Intensity0 = Tail.Intensity1 = 16.0f;
	Tail.Color = Color;
	Spawn(Tail);
	// the head rides the FRONT of the tail (a streak's position is its front: the tail grows out behind it).
	// the corona: the gun's own colour, wide and soft
	FSOFxParticle Corona;
	Corona.Kind = ESOFxKind::Glow;
	Corona.Position = From;
	Corona.Velocity = Tail.Velocity;
	Corona.Life = Flight;
	Corona.Size0 = Corona.Size1 = 34.0f * Size;
	Corona.Intensity0 = Corona.Intensity1 = 9.0f;
	Corona.Color = Color;
	Spawn(Corona);
	// the core: white-hot
	FSOFxParticle Core = Corona;
	Core.Size0 = Core.Size1 = 13.0f * Size;
	Core.Intensity0 = Core.Intensity1 = 30.0f;
	Core.Color = FMath::Lerp(Color, FLinearColor::White, 0.78f);
	Spawn(Core);
	// what it leaves behind: the air along its path glows as it passes, a length at a time, thins and goes out. Short
	// enough in time that a burst is a row of bolts each with its own fading trail, never one beam.
	const int32 Lengths = FMath::Clamp(FMath::CeilToInt(Distance / 130.0f), 1, 16);
	const float Each = Distance / Lengths;
	for (int32 i = 0; i < Lengths; ++i)
	{
		FSOFxParticle Glow;
		Glow.Kind = ESOFxKind::Streak;
		Glow.bWhole = true;
		Glow.Axis = Axis;
		Glow.Delay = Each * (i + 1.0f) / Rel;
		Glow.Position = From + Axis * Each * (i + 1.0f) + Carry * Glow.Delay;   // (where the bolt is as it lights)
		Glow.Velocity = Carry;
		Glow.Length = Each;
		Glow.Life = Random.FRandRange(0.085f, 0.115f);
		Glow.Size0 = 4.2f * Size;
		Glow.Size1 = 1.0f * Size;
		Glow.Intensity0 = 5.5f;
		Glow.Intensity1 = 0.0f;
		Glow.Color = Color;
		Spawn(Glow);
	}
	// and a few breaths of it that hang a little longer and drift up
	const int32 Puffs = FMath::Clamp(FMath::RoundToInt(Distance / 420.0f), 0, 6);
	for (int32 i = 0; i < Puffs; ++i)
	{
		const float Along = Distance * (i + Random.FRandRange(0.25f, 0.75f)) / Puffs;
		FSOFxParticle Wake;
		Wake.Kind = ESOFxKind::Glow;
		Wake.Delay = Along / Rel;
		Wake.Position = From + Axis * Along + Carry * Wake.Delay + Random.VRand() * 2.5f * Size;
		Wake.Velocity = Random.VRand() * 6.0f + FVector(0.0f, 0.0f, 9.0f) + Carry;
		Wake.Life = Random.FRandRange(0.18f, 0.30f);
		Wake.Size0 = 9.0f * Size;
		Wake.Size1 = 2.5f * Size;
		Wake.Intensity0 = 3.5f;
		Wake.Intensity1 = 0.0f;
		Wake.Color = Color;
		Spawn(Wake);
	}
}

void USOFxSubsystem::PlasmaImpact(const FVector& Point, const FVector& Normal, const FLinearColor& Color, float Size, float Delay, bool bFlesh)
{
	const FVector N = Normal.GetSafeNormal(UE_SMALL_NUMBER, FVector::UpVector);
	const float R = (bFlesh ? 18.0f : 28.0f) * Size;
	// the flare as it bursts
	FSOFxParticle Flare;
	Flare.Kind = ESOFxKind::Glow;
	Flare.Position = Point + N * R * 0.2f;
	Flare.Delay = Delay;
	Flare.Life = 0.13f;
	Flare.Size0 = R * 0.7f;
	Flare.Size1 = R * 1.5f;
	Flare.Intensity0 = 11.0f * FMath::Min(1.0f, Size);
	Flare.Intensity1 = 0.0f;
	Flare.Color = Color;
	Spawn(Flare);
	FSOFxParticle Hot = Flare;
	Hot.Life = 0.07f;
	Hot.Size0 = R * 0.45f;
	Hot.Size1 = R * 0.3f;
	Hot.Intensity0 = 26.0f;
	Hot.Color = FMath::Lerp(Color, FLinearColor::White, 0.7f);
	Spawn(Hot);
	// it splashes: drops of it thrown out along the surface, not back at the gun
	const FVector Side = FVector::CrossProduct(N, FMath::Abs(N.Z) < 0.9f ? FVector::UpVector : FVector::ForwardVector).GetSafeNormal();
	const int32 Drops = bFlesh ? 5 : 9;
	for (int32 i = 0; i < Drops; ++i)
	{
		const FVector Out = FQuat(N, (i + Random.FRand()) / Drops * 2.0f * UE_PI).RotateVector(Side);
		FSOFxParticle Drop;
		Drop.Kind = ESOFxKind::Streak;
		Drop.Position = Point + N * 2.0f;
		Drop.Velocity = (Out + N * Random.FRandRange(0.1f, 0.45f)) * Random.FRandRange(R * 5.0f, R * 12.0f);
		Drop.Gravity = 420.0f;
		Drop.Drag = 4.0f;
		Drop.Delay = Delay;
		Drop.Life = Random.FRandRange(0.16f, 0.32f);
		Drop.Size0 = 2.2f * Size;
		Drop.Size1 = 0.8f * Size;
		Drop.Intensity0 = 24.0f;
		Drop.Intensity1 = 0.0f;
		Drop.Color = Color;
		Spawn(Drop);
	}
	// its light on the place: once for a pattern of pellets landing together (twelve lights flooded a wall), and
	// the flares of the small ones kept low
	const double Now = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.0;
	if (Now - LastPlasmaLightTime > 0.04 || FVector::DistSquared(Point, LastPlasmaLightAt) > FMath::Square(260.0f))
	{
		LastPlasmaLightTime = Now;
		LastPlasmaLightAt = Point;
		PendingLights.Add({ Point + N * 30.0f, Color, FMath::Clamp(230.0f * Size * Size, 90.0f, 1400.0f), 0.1f, Delay });
	}
	if (bFlesh)
	{
		return;
	}
	// a breath of vapour off what it burned
	for (int32 i = 0; i < 2; ++i)
	{
		FSOFxParticle Mist;
		Mist.Kind = ESOFxKind::Smoke;
		Mist.Position = Point + N * R * 0.2f + Random.VRand() * R * 0.2f;
		Mist.Velocity = N * R * 0.8f + Random.VRand() * R * 0.4f + FVector(0.0f, 0.0f, 22.0f);
		Mist.Drag = 2.5f;
		Mist.Delay = Delay + Random.FRandRange(0.02f, 0.08f);
		Mist.Life = Random.FRandRange(0.5f, 0.9f);
		Mist.Size0 = R * 0.3f;
		Mist.Size1 = R * Random.FRandRange(0.9f, 1.3f);
		Mist.Intensity0 = 0.3f;
		Mist.Color = Color * 0.5f;
		Mist.Spin = Random.FRandRange(0.0f, 360.0f);
		Spawn(Mist);
	}
	// what it struck glows where it landed, and cools
	FSOFxParticle Scorch;
	Scorch.Kind = ESOFxKind::Glow;
	Scorch.Position = Point + N * 2.5f;
	Scorch.Delay = Delay;
	Scorch.Life = 0.62f;
	Scorch.Size0 = 24.0f * Size;
	Scorch.Size1 = 7.0f * Size;
	Scorch.Intensity0 = 9.0f;
	Scorch.Intensity1 = 0.0f;
	Scorch.Color = FMath::Lerp(Color, FLinearColor::White, 0.25f);
	Spawn(Scorch);
	// motes of it drifting up off the place
	for (int32 i = 0; i < 4; ++i)
	{
		FSOFxParticle Mote;
		Mote.Kind = ESOFxKind::Glow;
		Mote.Position = Point + N * 4.0f + Random.VRand() * 5.0f * Size;
		Mote.Velocity = N * Random.FRandRange(20.0f, 70.0f) + Random.VRand() * 25.0f + FVector(0.0f, 0.0f, 30.0f);
		Mote.Drag = 2.0f;
		Mote.Delay = Delay + Random.FRandRange(0.0f, 0.06f);
		Mote.Life = Random.FRandRange(0.35f, 0.7f);
		Mote.Size0 = 3.2f * Size;
		Mote.Size1 = 0.8f * Size;
		Mote.Intensity0 = 12.0f;
		Mote.Intensity1 = 0.0f;
		Mote.Color = Color;
		Spawn(Mote);
	}
}

void USOFxSubsystem::PlasmaFlash(const FVector& Muzzle, const FVector& Dir, float Scale, bool bViewmodel, const FLinearColor& Color, bool bThroughScope)
{
	if (bThroughScope)
	{
		return; // (as with a flame: nothing is drawn a hand's width from a magnified glass)
	}
	const FVector D = Dir.GetSafeNormal();
	FSOFxParticle Bloom;
	Bloom.Kind = ESOFxKind::Glow;
	Bloom.Position = Muzzle + D * 4.0f * Scale;
	Bloom.Life = 0.07f;
	Bloom.Size0 = 22.0f * Scale;
	Bloom.Size1 = 9.0f * Scale;
	Bloom.Intensity0 = 10.0f;
	Bloom.Intensity1 = 0.0f;
	Bloom.Color = Color;
	Spawn(Bloom);
	FSOFxParticle Core = Bloom;
	Core.Life = 0.045f;
	Core.Size0 = 9.0f * Scale;
	Core.Size1 = 4.0f * Scale;
	Core.Intensity0 = 26.0f;
	Core.Color = FMath::Lerp(Color, FLinearColor::White, 0.75f);
	Spawn(Core);
	for (int32 i = 0; i < 3; ++i)
	{
		FSOFxParticle Mote;
		Mote.Kind = ESOFxKind::Glow;
		Mote.Position = Muzzle + D * 6.0f * Scale;
		Mote.Velocity = (D + Random.VRand() * 0.45f) * Random.FRandRange(120.0f, 260.0f);
		Mote.Drag = 5.0f;
		Mote.Life = Random.FRandRange(0.10f, 0.20f);
		Mote.Size0 = 3.0f * Scale;
		Mote.Size1 = 0.6f * Scale;
		Mote.Intensity0 = 12.0f;
		Mote.Intensity1 = 0.0f;
		Mote.Color = Color;
		Spawn(Mote);
	}
	FlashLight(Muzzle + D * (bViewmodel ? 120.0f : 10.0f) - FVector(0.0f, 0.0f, bViewmodel ? 22.0f : 0.0f), 240.0f * Scale * (bViewmodel ? 0.25f : 1.0f),
		Color, 0.06f);
}

void USOFxSubsystem::Tracer(const FVector& From, const FVector& To, float Speed, const FLinearColor& Color, float Width, float Length, bool bBolt)
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
	T.Length = Length;
	T.Size0 = T.Size1 = Width;
	T.Intensity0 = T.Intensity1 = 22.0f;
	T.Color = Color;
	Spawn(T);
	if (bBolt)
	{
		// a bolt of light has a head: a bead of its own colour riding at the front of the streak
		FSOFxParticle Head;
		Head.Kind = ESOFxKind::Glow;
		Head.Position = From;                    // (a streak's position is its front: the tail grows out behind it)
		Head.Velocity = T.Velocity;
		Head.Life = T.Life;
		Head.Size0 = Head.Size1 = Width * 3.4f;
		Head.Intensity0 = Head.Intensity1 = 16.0f;
		Head.Color = FMath::Lerp(Color, FLinearColor::White, 0.3f);
		Spawn(Head);
	}
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

void USOFxSubsystem::Shockwave(const FVector& Point, float Radius, const FLinearColor& Color, float Delay)
{
	const float R = FMath::Max(Radius, 100.0f);
	const FVector Up = FVector::UpVector;
	// the ring: streaks racing out along the ground (drag 3 over 0.55 s carries a particle 0.269 of its speed)
	const int32 Rays = 56;
	for (int32 i = 0; i < Rays; ++i)
	{
		const float A = (i + Random.FRand() * 0.6f) / Rays * 2.0f * UE_PI;
		const FVector Dir(FMath::Cos(A), FMath::Sin(A), 0.0f);
		FSOFxParticle S;
		S.Kind = ESOFxKind::Streak;
		S.Position = Point + Dir * 40.0f + Up * 6.0f;
		S.Velocity = Dir * (R - 40.0f) / 0.269f * Random.FRandRange(0.82f, 1.0f) + Up * Random.FRandRange(0.0f, 60.0f);
		S.Drag = 3.0f;
		S.Delay = Delay;
		S.Life = 0.55f;
		S.Size0 = 3.5f;
		S.Size1 = 1.4f;
		S.Length = 90.0f;
		S.Intensity0 = 26.0f;
		S.Color = Color;
		Spawn(S);
	}
	// light rolling out with it, and the dust it lifts, which hangs
	for (int32 i = 0; i < 16; ++i)
	{
		const float A = (i + Random.FRand()) / 16.0f * 2.0f * UE_PI;
		const FVector Dir(FMath::Cos(A), FMath::Sin(A), 0.0f);
		FSOFxParticle G;
		G.Kind = ESOFxKind::Glow;
		G.Position = Point + Dir * R * 0.2f + Up * 12.0f;
		G.Velocity = Dir * R * 1.5f;
		G.Drag = 3.0f;
		G.Delay = Delay;
		G.Life = 0.4f;
		G.Size0 = R * 0.05f;
		G.Size1 = R * 0.14f;
		G.Intensity0 = 2.6f;
		G.Color = Color;
		Spawn(G);

		FSOFxParticle D;
		D.Kind = ESOFxKind::Smoke;
		D.Position = Point + Dir * R * Random.FRandRange(0.15f, 0.55f) + Up * 10.0f;
		D.Velocity = Dir * R * 0.7f + Up * Random.FRandRange(60.0f, 140.0f);
		D.Drag = 2.5f;
		D.Delay = Delay + Random.FRandRange(0.03f, 0.18f);
		D.Life = Random.FRandRange(1.2f, 2.2f);
		D.Size0 = R * 0.1f;
		D.Size1 = R * Random.FRandRange(0.28f, 0.42f);
		D.Intensity0 = 0.45f;
		D.Color = FLinearColor(0.2f, 0.2f, 0.22f);
		D.Spin = Random.FRandRange(0.0f, 360.0f);
		Spawn(D);
	}
	// the blow itself, and what it throws up
	FSOFxParticle Core;
	Core.Kind = ESOFxKind::Glow;
	Core.Position = Point + Up * 30.0f;
	Core.Delay = Delay;
	Core.Life = 0.2f;
	Core.Size0 = R * 0.08f;
	Core.Size1 = R * 0.22f;
	Core.Intensity0 = 12.0f;
	Core.Color = Color;
	Spawn(Core);
	for (int32 i = 0; i < 22; ++i)
	{
		FSOFxParticle C;
		C.Kind = ESOFxKind::Streak;
		C.Position = Point + Up * 4.0f;
		C.Velocity = Random.VRandCone(Up, FMath::DegreesToRadians(62.0f)) * Random.FRandRange(400.0f, 1100.0f);
		C.Gravity = 980.0f;
		C.Drag = 1.0f;
		C.Delay = Delay;
		C.Life = Random.FRandRange(0.4f, 0.8f);
		C.Size0 = 1.6f;
		C.Size1 = 1.0f;
		C.Intensity0 = 24.0f;
		C.Color = Color;
		Spawn(C);
	}
	PendingLights.Add({ Point + Up * 60.0f, Color, 1800.0f, 0.22f, Delay });
}

void USOFxSubsystem::Sweep(const FVector& Origin, const FVector& Forward, float Reach, float HalfAngle, const FLinearColor& Color)
{
	const FVector F = Forward.GetSafeNormal2D(UE_SMALL_NUMBER, FVector::ForwardVector);
	const FVector Right = FVector::CrossProduct(FVector::UpVector, F);
	const float Half = FMath::DegreesToRadians(FMath::Clamp(HalfAngle, 10.0f, 180.0f));
	const float Out = FMath::Max(Reach, 60.0f);
	const int32 Rays = 26;
	for (int32 i = 0; i < Rays; ++i)
	{
		const float T = i / float(Rays - 1);
		const float A = FMath::Lerp(-Half, Half, T);
		const FVector Dir = F * FMath::Cos(A) + Right * FMath::Sin(A);
		FSOFxParticle S;
		S.Kind = ESOFxKind::Streak;
		S.Position = Origin + Dir * 45.0f - FVector(0.0f, 0.0f, 22.0f);
		S.Velocity = Dir * Out / 0.103f + FVector(0.0f, 0.0f, Random.FRandRange(-40.0f, 40.0f)); // drag 6 over 0.16 s: 0.103 of its speed
		S.Drag = 6.0f;
		S.Delay = T * 0.05f; // across, like an arm
		S.Life = 0.16f;
		S.Size0 = 3.0f;
		S.Size1 = 1.0f;
		S.Length = 70.0f;
		S.Intensity0 = 22.0f;
		S.Color = Color;
		Spawn(S);
	}
	for (int32 i = 0; i < 3; ++i)
	{
		FSOFxParticle G;
		G.Kind = ESOFxKind::Glow;
		G.Position = Origin + F * Out * (0.35f + 0.2f * i) - FVector(0.0f, 0.0f, 20.0f);
		G.Delay = 0.02f * i;
		G.Life = 0.12f;
		G.Size0 = Out * 0.1f;
		G.Size1 = Out * 0.24f;
		G.Intensity0 = 1.4f;
		G.Color = Color;
		Spawn(G);
	}
}

void USOFxSubsystem::AimLine(const AActor* Shooter, const FVector& Offset, const AActor* Target, float Time, float Lock, const FLinearColor& Color)
{
	if (!Shooter || !Target)
	{
		return;
	}
	FAimLine Line;
	Line.Shooter = Shooter;
	Line.Target = Target;
	Line.Offset = Offset;
	Line.End = Target->GetActorLocation();
	Line.Color = Color;
	Line.Time = FMath::Max(Time, 0.1f);
	Line.Lock = FMath::Clamp(Lock, 0.0f, Line.Time);
	AimLines.Add(Line);
}

void USOFxSubsystem::Warn(const FVector& Point, float Radius, float HalfAngle, float Yaw, float Time, const FLinearColor& Color, const AActor* Follow)
{
	FWarning W;
	W.Point = Point;
	W.Color = Color;
	W.Radius = FMath::Max(Radius, 30.0f);
	W.CosHalf = HalfAngle >= 179.0f ? -1.0f : FMath::Cos(FMath::DegreesToRadians(FMath::Max(HalfAngle, 5.0f)));
	W.Yaw = Yaw;
	W.Time = FMath::Max(Time, 0.05f);
	W.Follow = Follow;
	W.bFollow = Follow != nullptr;
	W.YawOffset = Follow ? FRotator::NormalizeAxis(Yaw - Follow->GetActorRotation().Yaw) : 0.0f;
	if (EnsureHost())
	{
		UDecalComponent* Decal = nullptr;
		while (!Decal && FreeWarnings.Num() > 0)
		{
			Decal = FreeWarnings.Pop(EAllowShrinking::No).Get();
		}
		if (!Decal)
		{
			// drawn straight down onto whatever is there; the picture itself is worked out from the world position
			// in the material, so the decal's own turn does not matter
			Decal = NewObject<UDecalComponent>(Host.Get());
			Decal->DecalSize = FVector(260.0f, 100.0f, 100.0f);
			Decal->SetFadeScreenSize(0.0f);
			Decal->SortOrder = 8;
			Decal->SetWorldRotation(FRotator(-90.0f, 0.0f, 0.0f));
			Decal->RegisterComponent();
			if (UMaterialInterface* Parent = Cast<UMaterialInterface>(FSoftObjectPath(WarnMaterial).TryLoad()))
			{
				Decal->SetDecalMaterial(UMaterialInstanceDynamic::Create(Parent, Decal));
			}
		}
		W.Decal = Decal;
		W.Material = Cast<UMaterialInstanceDynamic>(Decal->GetDecalMaterial());
		const float S = W.Radius * 1.03f / 100.0f;
		Decal->SetWorldScale3D(FVector(1.0f, S, S));
		Decal->SetVisibility(true);
	}
	PlaceWarning(W);
	Warnings.Add(W);
}

void USOFxSubsystem::PlaceWarning(FWarning& W) const
{
	if (W.bFollow)
	{
		if (const AActor* Under = W.Follow.Get())
		{
			W.Point = Under->GetActorLocation() - FVector(0.0f, 0.0f, Under->GetSimpleCollisionHalfHeight());
			W.Yaw = Under->GetActorRotation().Yaw + W.YawOffset;
		}
		else
		{
			W.Age = FMath::Max(W.Age, W.Time); // whoever it was under is gone: so is the warning
		}
	}
	if (UDecalComponent* Decal = W.Decal.Get())
	{
		Decal->SetWorldLocation(W.Point);
	}
	if (UMaterialInstanceDynamic* M = W.Material.Get())
	{
		const float Gone = FMath::Clamp((W.Age - W.Time) / WarnFade, 0.0f, 1.0f);
		const float A = FMath::DegreesToRadians(W.Yaw);
		M->SetVectorParameterValue(TEXT("Center"), FLinearColor(W.Point.X, W.Point.Y, W.Point.Z, W.Radius));
		M->SetVectorParameterValue(TEXT("Shape"), FLinearColor(FMath::Cos(A), FMath::Sin(A), W.CosHalf, FMath::Clamp(W.Age / W.Time, 0.0f, 1.0f)));
		M->SetVectorParameterValue(TEXT("Color"), FLinearColor(W.Color.R, W.Color.G, W.Color.B, 1.0f - Gone));
	}
}

void USOFxSubsystem::Ward(const FVector& Feet, float Height, const FLinearColor& Color)
{
	const FVector Up = FVector::UpVector;
	const float H = FMath::Max(Height, 80.0f);
	for (int32 i = 0; i < 40; ++i)
	{
		const float A = (i + Random.FRand()) / 40.0f * 2.0f * UE_PI;
		const FVector Dir(FMath::Cos(A), FMath::Sin(A), 0.0f);
		FSOFxParticle S;
		S.Kind = ESOFxKind::Streak;
		S.Position = Feet + Dir * 72.0f + Up * Random.FRandRange(0.0f, H * 0.25f);
		S.Velocity = Up * Random.FRandRange(H * 1.4f, H * 2.3f) + Dir * 15.0f;
		S.Drag = 1.2f;
		S.Delay = Random.FRandRange(0.0f, 0.25f);
		S.Life = Random.FRandRange(0.5f, 0.8f);
		S.Size0 = 2.4f;
		S.Size1 = 1.0f;
		S.Length = 55.0f;
		S.Intensity0 = 18.0f;
		S.Color = Color;
		Spawn(S);
	}
	for (int32 i = 0; i < 10; ++i)
	{
		const float A = Random.FRand() * 2.0f * UE_PI;
		FSOFxParticle G;
		G.Kind = ESOFxKind::Glow;
		G.Position = Feet + FVector(FMath::Cos(A), FMath::Sin(A), 0.0f) * 72.0f + Up * H * Random.FRand();
		G.Velocity = Up * 120.0f;
		G.Delay = Random.FRandRange(0.05f, 0.3f);
		G.Life = 0.5f;
		G.Size0 = 30.0f;
		G.Size1 = 60.0f;
		G.Intensity0 = 3.5f;
		G.Color = Color;
		Spawn(G);
	}
	PendingLights.Add({ Feet + Up * H * 0.6f, Color, 900.0f, 0.3f, 0.0f });
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

	for (int32 i = AimLines.Num() - 1; i >= 0; --i)
	{
		FAimLine& Line = AimLines[i];
		Line.Age += DeltaTime;
		const AActor* Shooter = Line.Shooter.Get();
		if (!Shooter || Line.Age >= Line.Time)
		{
			AimLines.RemoveAtSwap(i, 1, EAllowShrinking::No);
			continue;
		}
		if (const AActor* Target = Line.Target.Get(); Target && Line.Age < Line.Time - Line.Lock)
		{
			Line.End = Target->GetActorLocation() + FVector(0.0f, 0.0f, 20.0f); // (it follows until it locks)
		}
		const FVector From = Shooter->GetActorLocation() + Shooter->GetActorRotation().RotateVector(Line.Offset);
		const FVector Path = Line.End - From;
		const float Distance = Path.Size();
		if (Distance < 100.0f)
		{
			continue;
		}
		// drawn afresh every frame (a streak that lives one frame): thin and faint at first, hard and bright once it
		// has locked
		const float K = Line.Age / Line.Time;
		const bool bLocked = Line.Age >= Line.Time - Line.Lock;
		FSOFxParticle S;
		S.Kind = ESOFxKind::Streak;
		S.Position = From;
		S.Axis = Path / Distance;
		S.Length = FMath::Min(Distance + 250.0f, 9000.0f);
		S.Life = FMath::Max(DeltaTime * 1.1f, 0.02f);
		S.Size0 = S.Size1 = bLocked ? 3.2f : FMath::Lerp(0.9f, 1.8f, K);
		S.Intensity0 = S.Intensity1 = bLocked ? 30.0f : FMath::Lerp(5.0f, 14.0f, K);
		S.bHold = true;
		S.Color = bLocked ? FMath::Lerp(Line.Color, FLinearColor::White, 0.5f) : Line.Color;
		Spawn(S);
		FSOFxParticle Glint; // where it comes from: a point of light that swells
		Glint.Kind = ESOFxKind::Glow;
		Glint.Position = From;
		Glint.Life = S.Life;
		// (to the one it points at the line is seen end-on, almost a dot: what they read is this light, so it keeps
		// its size in their view however far off it is, and flares once the line has locked)
		float Far = 1.0f;
		if (const APlayerCameraManager* Camera = UGameplayStatics::GetPlayerCameraManager(GetWorld(), 0))
		{
			Far = FMath::Clamp(FVector::Dist(Camera->GetCameraLocation(), From) / 500.0f, 1.0f, 14.0f);
		}
		Glint.Size0 = Glint.Size1 = FMath::Lerp(8.0f, 26.0f, K) * Far * (bLocked ? 1.5f : 1.0f);
		Glint.Intensity0 = Glint.Intensity1 = bLocked ? 34.0f : FMath::Lerp(4.0f, 14.0f, K);
		Glint.bHold = true;
		Glint.Color = S.Color;
		Spawn(Glint);
	}

	for (int32 i = Warnings.Num() - 1; i >= 0; --i)
	{
		FWarning& W = Warnings[i];
		W.Age += DeltaTime;
		PlaceWarning(W);
		if (W.Age >= W.Time + WarnFade)
		{
			if (UDecalComponent* Decal = W.Decal.Get())
			{
				Decal->SetVisibility(false);
				FreeWarnings.Add(Decal);
			}
			Warnings.RemoveAtSwap(i, 1, EAllowShrinking::No);
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
			const float Length = P.bWhole ? P.Length
				: (P.Length > 0.0f ? FMath::Min(P.Length, P.Velocity.Size() * P.Age + 1.0f) : FMath::Clamp(P.Velocity.Size() * 0.03f, 2.0f, 60.0f));
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
