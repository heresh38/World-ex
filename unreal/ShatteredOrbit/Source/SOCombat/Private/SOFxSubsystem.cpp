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
#include "PhysicalMaterials/PhysicalMaterial.h"
#include "Components/PrimitiveComponent.h"
#include "Engine/HitResult.h"
#include "SOSound.h"
#include "SOWeapon.h"

namespace
{
	const TCHAR* CardMeshes[] = { TEXT("/Game/FX/SM_FX_Quad.SM_FX_Quad"), TEXT("/Game/FX/SM_FX_Streak.SM_FX_Streak"),
		TEXT("/Game/FX/SM_FX_Star.SM_FX_Star"), TEXT("/Game/FX/SM_FX_Quad.SM_FX_Quad"), TEXT("/Game/FX/SM_FX_Quad.SM_FX_Quad") };
	const TCHAR* CardMaterials[] = { TEXT("/Game/FX/MI_FxGlow.MI_FxGlow"), TEXT("/Game/FX/MI_FxStreak.MI_FxStreak"),
		TEXT("/Game/FX/MI_FxFlash.MI_FxFlash"), TEXT("/Game/FX/MI_FxSmoke.MI_FxSmoke"), TEXT("/Game/FX/MI_FxCell.MI_FxCell") };
	const FLinearColor Brass(0.85f, 0.62f, 0.25f);
	const FLinearColor Dust(0.46f, 0.43f, 0.39f);
	const FLinearColor Earth(0.36f, 0.27f, 0.18f);
	const FLinearColor Wood(0.62f, 0.45f, 0.26f);
	const FLinearColor Water(0.75f, 0.85f, 0.95f);
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

USOFxSubsystem::ESurface USOFxSubsystem::SurfaceOf(const FHitResult& Hit)
{
	FString Key;
	if (const UPhysicalMaterial* Phys = Hit.PhysMaterial.Get())
	{
		Key = Phys->GetName();
	}
	if (const UPrimitiveComponent* Comp = Hit.GetComponent())
	{
		const UMaterialInterface* Material = Comp->GetNumMaterials() > 0 ? Comp->GetMaterial(FMath::Max(0, static_cast<int32>(Hit.ElementIndex))) : nullptr;
		Key += TEXT(" ") + (Material ? Material->GetName() : FString()) + TEXT(" ") + Comp->GetName() + TEXT(" ") + GetNameSafe(Comp->GetOwner());
	}
	else if (const AActor* Actor = Hit.GetActor())
	{
		Key += TEXT(" ") + Actor->GetName();
	}
	const FString Lower = Key.ToLower();
	auto Has = [&Lower](std::initializer_list<const TCHAR*> Words)
	{
		for (const TCHAR* Word : Words)
		{
			if (Lower.Contains(Word))
			{
				return true;
			}
		}
		return false;
	};
	if (Has({ TEXT("water"), TEXT("puddle"), TEXT("pool") })) { return ESurface::Water; }
	if (Has({ TEXT("metal"), TEXT("steel"), TEXT("grate"), TEXT("plate"), TEXT("hull"), TEXT("alloy"), TEXT("rail"), TEXT("pipe"), TEXT("catwalk"), TEXT("iron"), TEXT("container"), TEXT("vehicle"), TEXT("wreck") })) { return ESurface::Metal; }
	if (Has({ TEXT("grass"), TEXT("moss"), TEXT("lawn"), TEXT("leaf"), TEXT("park"), TEXT("flora"), TEXT("plant") })) { return ESurface::Grass; }
	if (Has({ TEXT("dirt"), TEXT("soil"), TEXT("mud"), TEXT("sand"), TEXT("gravel"), TEXT("rubble"), TEXT("ash"), TEXT("hive"), TEXT("chitin"), TEXT("heap") })) { return ESurface::Dirt; }
	if (Has({ TEXT("wood"), TEXT("plank"), TEXT("crate"), TEXT("timber"), TEXT("furniture"), TEXT("desk"), TEXT("shelf") })) { return ESurface::Wood; }
	return ESurface::Concrete;
}

FName USOFxSubsystem::SurfaceName(ESurface Surface)
{
	switch (Surface)
	{
	case ESurface::Metal: return TEXT("metal");
	case ESurface::Dirt: return TEXT("dirt");
	case ESurface::Grass: return TEXT("grass");
	case ESurface::Wood: return TEXT("wood");
	case ESurface::Water: return TEXT("water");
	default: return TEXT("concrete");
	}
}

float USOFxSubsystem::LowestParticleZ() const
{
	float Z = 1.0e9f;
	for (const FSOFxParticle& P : Particles)
	{
		Z = FMath::Min(Z, static_cast<float>(P.Position.Z));
	}
	return Z;
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

void USOFxSubsystem::MuzzleFlash(const FVector& Muzzle, const FVector& Dir, float Scale, bool bViewmodel, const FLinearColor& Color, bool bThroughScope, EFlash Style)
{
	const FVector D = Dir.GetSafeNormal();
	if (bThroughScope)
	{
		// down a scope the muzzle is a hand's width from the glass and magnified with everything else: nothing is drawn
		// there (the shot is felt in the kick and seen in the tracer)
		return;
	}
	// Each kind of gun its own flash (the owner's guide): how long and wide the blades are, the core, the smoke,
	// the light, and how much burning powder it throws out (a shotgun's is a wide burst, a rifle's clean and sharp,
	// an SMG's small and quick, a long gun's a jet with a ring of pressure, a launcher's back-blast is smoke).
	struct FProfile { float Length, Width, Core, Smoke, Light, Sparks; bool bRing; };
	static const FProfile Profiles[] = {
		{ 1.0f, 1.0f, 1.0f, 1.0f, 1.0f, 0.0f, false },   // Rifle: sharp and punchy
		{ 0.65f, 0.8f, 0.8f, 0.6f, 0.7f, 0.0f, false },  // Short: fast and small
		{ 1.9f, 0.9f, 1.1f, 1.6f, 1.5f, 3.0f, true },    // Long: loud, a jet, a ring of pressure
		{ 1.3f, 1.8f, 1.5f, 2.0f, 1.6f, 14.0f, true },   // Shotgun: massive and wide, powder burning in the air
		{ 1.25f, 1.3f, 1.3f, 1.2f, 1.3f, 4.0f, false },  // Heavy: big and steady
		{ 1.1f, 1.6f, 1.6f, 2.5f, 1.4f, 6.0f, true },    // Launcher: a back-blast of smoke
	};
	const FProfile& P = Profiles[FMath::Clamp(static_cast<int32>(Style), 0, 5)];
	// Tongues of flame: the card is five thin blades about the bore (the shader shapes each to a point and tears
	// it), a different length and turn every shot, gone in three frames.
	FSOFxParticle Star;
	Star.Kind = ESOFxKind::Star;
	Star.Position = Muzzle;
	Star.Axis = D;
	Star.Life = Random.FRandRange(0.035f, 0.055f);
	Star.Length = Random.FRandRange(20.0f, 34.0f) * Scale * P.Length;
	Star.Size0 = Star.Size1 = Random.FRandRange(9.0f, 14.0f) * Scale * P.Width;
	Star.Intensity0 = 13.0f;                  // (more than this burns every colour to white)
	Star.Intensity1 = 0.0f;
	Star.Color = Color;
	Star.Spin = Random.FRandRange(0.0f, 360.0f);
	Spawn(Star);

	FSOFxParticle Core;
	Core.Kind = ESOFxKind::Glow;
	Core.Position = Muzzle + D * 3.0f * Scale;
	Core.Life = 0.04f;
	Core.Size0 = 15.0f * Scale * P.Core;
	Core.Size1 = 6.0f * Scale * P.Core;
	Core.Intensity0 = 11.0f;
	Core.Color = FMath::Lerp(Color, FLinearColor::White, 0.25f);
	Spawn(Core);

	const int32 Wisps = FMath::Max(1, FMath::RoundToInt(2.0f * P.Smoke));
	for (int32 i = 0; i < Wisps; ++i)
	{
		FSOFxParticle Wisp;
		Wisp.Kind = ESOFxKind::Smoke;
		Wisp.Position = Muzzle + D * (6.0f + i * 8.0f) * Scale;
		Wisp.Velocity = D * Random.FRandRange(60.0f, 140.0f) + FVector(0, 0, 25.0f) + Random.VRand() * 15.0f;
		Wisp.Drag = 2.5f;
		Wisp.Life = Random.FRandRange(0.5f, 0.8f) * FMath::Sqrt(P.Smoke);
		Wisp.Size0 = 6.0f * Scale;
		Wisp.Size1 = 34.0f * Scale * FMath::Sqrt(P.Smoke);
		Wisp.Intensity0 = 0.22f;
		Wisp.Color = FLinearColor(0.55f, 0.55f, 0.56f);
		Wisp.Spin = Random.FRandRange(0.0f, 360.0f);
		Spawn(Wisp);
	}
	// burning powder: sparks thrown out along the bore, falling
	for (int32 i = 0; i < FMath::RoundToInt(P.Sparks); ++i)
	{
		FSOFxParticle S;
		S.Kind = ESOFxKind::Streak;
		S.Position = Muzzle + D * 4.0f * Scale;
		S.Velocity = Random.VRandCone(D, FMath::DegreesToRadians(Style == EFlash::Shotgun ? 16.0f : 7.0f)) * Random.FRandRange(700.0f, 1500.0f) * Scale;
		S.Gravity = 980.0f;
		S.Drag = 3.0f;
		S.Life = Random.FRandRange(0.08f, 0.22f);
		S.Size0 = S.Size1 = 1.1f * Scale;
		S.Intensity0 = 22.0f;
		S.Color = Spark;
		Spawn(S);
	}
	if (P.bRing)
	{
		// the pressure of the shot: a faint ring of vapour across the bore, gone as it opens
		FSOFxParticle Ring;
		Ring.Kind = ESOFxKind::Smoke;
		Ring.Position = Muzzle + D * 10.0f * Scale;
		Ring.Axis = D;
		Ring.bFlat = true;
		Ring.Life = 0.07f;
		Ring.Size0 = 10.0f * Scale;
		Ring.Size1 = 75.0f * Scale * P.Width;
		Ring.Intensity0 = 0.5f;
		Ring.Color = FLinearColor(0.8f, 0.8f, 0.82f);
		Spawn(Ring);
	}
	// The flash lights the surroundings; for the gun in your own hands it sits well ahead of the muzzle and gentler,
	// so the gun itself does not flare white on every shot.
	// the light of the flash, in its own colour. In first person it stands well ahead of the muzzle and under the
	// bore: beside the muzzle it raked along the top of the gun and every grain of its finish sparkled.
	FlashLight(Muzzle + D * (bViewmodel ? 120.0f : 10.0f) - FVector(0.0f, 0.0f, bViewmodel ? 22.0f : 0.0f), 220.0f * Scale * P.Light * (bViewmodel ? 0.25f : 1.0f),
		FMath::Lerp(Color, Fire, 0.35f), 0.05f);
}

void USOFxSubsystem::Casing(const FVector& Port, const FVector& Out, const FVector& Up, const FVector& Carry, float Size, float FloorZ)
{
	// the brass: a small bright bit that tumbles out to the right and up, arcs over, lands and skitters to rest
	const FVector V = Out * Random.FRandRange(240.0f, 420.0f) + Up * Random.FRandRange(170.0f, 320.0f) + Random.VRand() * 40.0f + Carry;
	FSOFxParticle B;
	B.Kind = ESOFxKind::Smoke;
	B.Position = Port;
	B.Velocity = V;
	B.Gravity = 980.0f;
	B.Drag = 0.25f;
	B.Life = Random.FRandRange(1.4f, 2.0f);
	B.Size0 = B.Size1 = 1.3f * Size;
	B.Intensity0 = B.Intensity1 = 1.0f;
	B.Color = Brass;
	B.Spin = Random.FRandRange(0.0f, 360.0f);
	B.FloorZ = FloorZ;
	B.Bounce = 0.35f;
	Spawn(B);
	// the case itself: a short brass bar (a rifle's is 4 cm long), turned any way, flying with the dot
	FSOFxParticle Case;
	Case.Kind = ESOFxKind::Streak;
	Case.Position = Port;
	Case.Velocity = V;
	Case.Gravity = 980.0f;
	Case.Drag = 0.25f;
	Case.Axis = Random.VRand();
	Case.Length = 3.8f * Size;
	Case.bWhole = true;
	Case.Life = B.Life;
	Case.Size0 = Case.Size1 = 1.1f * Size;
	Case.Intensity0 = Case.Intensity1 = 2.6f;
	Case.Color = Brass;
	Case.FloorZ = FloorZ;
	Case.Bounce = 0.35f;
	Spawn(Case);
	// its glint: a point of light that flies with it for its first hand's breadths
	FSOFxParticle G;
	G.Kind = ESOFxKind::Glow;
	G.Position = Port;
	G.Velocity = V;
	G.Gravity = 980.0f;
	G.Drag = 0.25f;
	G.Life = 0.14f;
	G.Size0 = 2.2f * Size;
	G.Size1 = 1.0f * Size;
	G.Intensity0 = 7.0f;
	G.Color = FMath::Lerp(Brass, FLinearColor::White, 0.5f);
	Spawn(G);
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

void USOFxSubsystem::ReloadVent(const FVector& At, const FVector& Out, const FLinearColor& Color, float Duration, float Strength, const FVector& Carry, bool bViewmodel,
	const FSOFxAnchor& Anchor)
{
	auto Put = [&](FSOFxParticle& P) { P.Anchor = Anchor; Spawn(P); };
	const FVector N = Out.GetSafeNormal(UE_SMALL_NUMBER, FVector::UpVector);
	const float S = (bViewmodel ? 0.42f : 1.0f) * FMath::Clamp(Strength, 0.1f, 1.5f);
	const float T = FMath::Max(Duration, 0.1f);
	const FLinearColor Hot = FMath::Lerp(Color, FLinearColor::White, 0.65f);
	// the jet: gas leaving the opening fast, slowing as it blooms, rising as it cools; thickest at the start
	const int32 Puffs = FMath::Max(4, FMath::RoundToInt(26.0f * FMath::Min(Strength, 1.0f)));
	for (int32 i = 0; i < Puffs; ++i)
	{
		const float At01 = FMath::Pow(Random.FRand(), 1.6f);                  // (most of it early)
		FSOFxParticle Gas;
		Gas.Kind = ESOFxKind::Glow;
		Gas.Position = At + Random.VRand() * 1.5f * S;
		Gas.Velocity = (N + Random.VRand() * 0.35f).GetSafeNormal() * Random.FRandRange(180.0f, 420.0f) * S + Carry;
		Gas.Gravity = -60.0f * S;                                               // (hot: it rises)
		Gas.Drag = 5.5f;
		Gas.Delay = At01 * T * 0.85f;
		Gas.Life = Random.FRandRange(0.28f, 0.5f);
		Gas.Size0 = Random.FRandRange(5.0f, 8.0f) * S;
		Gas.Size1 = Random.FRandRange(18.0f, 30.0f) * S;
		Gas.Intensity0 = Random.FRandRange(3.0f, 5.5f) * (1.0f - At01 * 0.6f) * (bViewmodel ? 0.7f : 1.0f);
		Gas.Intensity1 = 0.0f;
		Gas.Color = FMath::Lerp(Color, Hot, Random.FRand() * 0.5f);
		Put(Gas);
		// and what it leaves: haze that hangs a moment and drifts up
		if (i % 3 == 0)
		{
			FSOFxParticle Haze;
			Haze.Kind = ESOFxKind::Smoke;
			Haze.Position = At + N * 4.0f * S;
			Haze.Velocity = N * Random.FRandRange(60.0f, 120.0f) * S + FVector(0.0f, 0.0f, 25.0f * S) + Carry;
			Haze.Drag = 3.0f;
			Haze.Delay = Gas.Delay + 0.05f;
			Haze.Life = Random.FRandRange(0.6f, 1.0f);
			Haze.Size0 = 6.0f * S;
			Haze.Size1 = Random.FRandRange(22.0f, 34.0f) * S;
			Haze.Intensity0 = 0.35f;
			Haze.Color = Color * 0.45f;
			Haze.Spin = Random.FRandRange(0.0f, 360.0f);
			Put(Haze);
		}
	}
	// the core at the opening, white-hot while it runs
	FSOFxParticle Core;
	Core.Kind = ESOFxKind::Glow;
	Core.Position = At + N * 1.5f * S;
	Core.Velocity = Carry;
	Core.Life = T;
	Core.bHold = true;
	Core.Size0 = Core.Size1 = 9.0f * S;
	Core.Intensity0 = Core.Intensity1 = 14.0f * FMath::Min(Strength, 1.0f);
	Core.Color = Hot;
	Put(Core);
	// sparks thrown out of it as it blows
	for (int32 i = 0; i < FMath::RoundToInt(10.0f * FMath::Min(Strength, 1.0f)); ++i)
	{
		FSOFxParticle Ember;
		Ember.Kind = ESOFxKind::Streak;
		Ember.Position = At;
		Ember.Velocity = (N + Random.VRand() * 0.6f).GetSafeNormal() * Random.FRandRange(250.0f, 600.0f) * S + Carry;
		Ember.Gravity = 380.0f;
		Ember.Drag = 2.5f;
		Ember.Delay = Random.FRand() * T * 0.4f;
		Ember.Life = Random.FRandRange(0.12f, 0.3f);
		Ember.Size0 = 1.4f * S;
		Ember.Size1 = 0.5f * S;
		Ember.Intensity0 = 20.0f;
		Ember.Intensity1 = 0.0f;
		Ember.Color = Hot;
		Put(Ember);
	}
	PendingLights.Add({ At + N * 12.0f * S, Color, (bViewmodel ? 6.0f : 40.0f) * FMath::Min(Strength, 1.0f), T * 0.8f, 0.0f });   // (at the hands: hundreds flooded the view)
}

void USOFxSubsystem::ReloadIntake(const FVector& At, const FVector& Out, const FLinearColor& Color, float Duration, const FVector& Carry, bool bViewmodel,
	const FSOFxAnchor& Anchor)
{
	auto Put = [&](FSOFxParticle& P) { P.Anchor = Anchor; Spawn(P); };
	const FVector N = Out.GetSafeNormal(UE_SMALL_NUMBER, FVector::UpVector);
	const float S = bViewmodel ? 0.42f : 1.0f;
	const float T = FMath::Max(Duration, 0.15f);
	// motes of light out of the air round the gun, each drawn in to the opening, faster as it nears it
	const int32 Motes = 46;
	for (int32 i = 0; i < Motes; ++i)
	{
		const float Life = Random.FRandRange(0.22f, 0.4f);
		const float Start = Random.FRand() * FMath::Max(T - Life, 0.0f);
		// (from the side the opening faces, a half sphere round it, 25-60 cm off)
		FVector From = Random.VRand();
		if (FVector::DotProduct(From, N) < 0.0f)
		{
			From -= 1.6f * FVector::DotProduct(From, N) * N;
		}
		const FVector P0 = At + From.GetSafeNormal() * Random.FRandRange(25.0f, 60.0f) * S;
		FSOFxParticle Mote;
		Mote.Kind = ESOFxKind::Streak;
		Mote.Position = P0;
		Mote.Velocity = (At - P0) / Life + Carry;
		Mote.Delay = Start;
		Mote.Life = Life;
		Mote.Length = 6.0f * S;
		Mote.Axis = (At - P0).GetSafeNormal();
		Mote.Size0 = 0.8f * S;
		Mote.Size1 = 2.2f * S;
		Mote.Intensity0 = 1.5f;
		Mote.Intensity1 = 9.0f;
		Mote.Color = FMath::Lerp(Color, FLinearColor::White, Random.FRand() * 0.4f);
		Put(Mote);
	}
	// the opening fills: a glow that grows while it draws, brightest as it closes
	for (int32 k = 0; k < 3; ++k)
	{
		FSOFxParticle Fill;
		Fill.Kind = ESOFxKind::Glow;
		Fill.Position = At + N * 1.0f * S;
		Fill.Velocity = Carry;
		Fill.Delay = T * k / 3.0f;
		Fill.Life = T / 3.0f + 0.05f;
		Fill.Size0 = (7.0f + 5.0f * k) * S;
		Fill.Size1 = (12.0f + 5.0f * k) * S;
		Fill.Intensity0 = 1.5f + 2.0f * k;
		Fill.Intensity1 = 3.0f + 2.0f * k;   // (stronger, it washed the hands in its colour)
		Fill.Color = FMath::Lerp(Color, FLinearColor::White, 0.2f * k);
		Put(Fill);
	}
	PendingLights.Add({ At + N * 10.0f * S, Color, bViewmodel ? 4.0f : 25.0f, T, 0.0f });
}

void USOFxSubsystem::ReloadCellPop(const FVector& At, const FLinearColor& Color, const FVector& Carry, bool bViewmodel, const FSOFxAnchor& Anchor)
{
	auto Put = [&](FSOFxParticle& P) { P.Anchor = Anchor; Spawn(P); };
	const float S = bViewmodel ? 0.42f : 1.0f;
	for (int32 i = 0; i < 5; ++i)
	{
		FSOFxParticle Puff;
		Puff.Kind = ESOFxKind::Smoke;
		Puff.Position = At + Random.VRand() * 2.0f * S;
		Puff.Velocity = Random.VRand() * 70.0f * S + FVector(0.0f, 0.0f, -30.0f * S) + Carry;
		Puff.Drag = 4.0f;
		Puff.Life = Random.FRandRange(0.35f, 0.6f);
		Puff.Size0 = 3.0f * S;
		Puff.Size1 = Random.FRandRange(10.0f, 15.0f) * S;
		Puff.Intensity0 = 0.4f;
		Puff.Color = FMath::Lerp(Color, FLinearColor::White, 0.5f) * 0.6f;
		Puff.Spin = Random.FRandRange(0.0f, 360.0f);
		Put(Puff);
	}
	FSOFxParticle Spit;
	Spit.Kind = ESOFxKind::Glow;
	Spit.Position = At;
	Spit.Velocity = Carry;
	Spit.Life = 0.12f;
	Spit.Size0 = 5.0f * S;
	Spit.Size1 = 11.0f * S;
	Spit.Intensity0 = 14.0f;
	Spit.Intensity1 = 0.0f;
	Spit.Color = FMath::Lerp(Color, FLinearColor::White, 0.5f);
	Put(Spit);
}

void USOFxSubsystem::ReloadCharge(const FVector& At, const FLinearColor& Color, float Duration, const FVector& Carry, bool bViewmodel, const FSOFxAnchor& Anchor)
{
	auto Put = [&](FSOFxParticle& P) { P.Anchor = Anchor; Spawn(P); };
	const float S = bViewmodel ? 0.42f : 1.0f;
	const float T = FMath::Max(Duration, 0.08f);
	FSOFxParticle Swell;
	Swell.Kind = ESOFxKind::Glow;
	Swell.Position = At;
	Swell.Velocity = Carry;
	Swell.Life = T;
	Swell.Size0 = 6.0f * S;
	Swell.Size1 = 26.0f * S;
	Swell.Intensity0 = 4.0f;
	Swell.Intensity1 = 0.0f;
	Swell.Color = Color;
	Put(Swell);
	FSOFxParticle Flash = Swell;
	Flash.Life = 0.07f;
	Flash.Size0 = 10.0f * S;
	Flash.Size1 = 4.0f * S;
	Flash.Intensity0 = 18.0f;
	Flash.Color = FMath::Lerp(Color, FLinearColor::White, 0.7f);
	Put(Flash);
	PendingLights.Add({ At, Color, bViewmodel ? 5.0f : 30.0f, 0.12f, 0.0f });
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

// --- The Sarketh's slugs (docs/orion/SARKETH_WEAPONS.md: "amber-charged kinetic projectiles. Not ordinary bullets, not
// lasers, and not generic plasma beams"). The colours are the brief's own table: the core white-hot, the shell amber,
// the trail golden orange, the sparks white and gold, the burst orange with dark smoke.
namespace SOSlug
{
	const FLinearColor Core(1.0f, 0.93f, 0.80f);
	const FLinearColor Shell(1.0f, 0.50f, 0.10f);
	const FLinearColor Trail(1.0f, 0.62f, 0.18f);
	const FLinearColor SparkWhite(1.0f, 0.95f, 0.85f);
	const FLinearColor SparkGold(1.0f, 0.72f, 0.28f);
	const FLinearColor Burst(1.0f, 0.42f, 0.10f);
	const FLinearColor Smoke(0.05f, 0.045f, 0.04f);
}

void USOFxSubsystem::SlugRound(const FVector& From, const FVector& To, float Speed, float Size, float Bright, const FVector& Carry, float Delay)
{
	if (FVector::Dist(From, To) < 40.0f || Speed <= 0.0f)
	{
		return;
	}
	++Slugs;
	// in the shooter's frame, as a plasma bolt is (PlasmaBolt): it leaves a moving gun with the gun's speed and lands on To
	const float Flight = FVector::Dist(From, To) / Speed;
	const FVector Path = To - From - Carry * Flight;
	const float Distance = FMath::Max(static_cast<float>(Path.Size()), 1.0f);
	const FVector Axis = Path / Distance;
	const float Rel = Distance / Flight;
	// a SHORT trail (a solid slug, not a lance of light): a hand's length at a rifle's speed
	FSOFxParticle Tail;
	Tail.Kind = ESOFxKind::Streak;
	Tail.Position = From;
	Tail.Axis = Axis;
	Tail.Velocity = Axis * Rel + Carry;
	Tail.Delay = Delay;
	Tail.Life = Flight;
	Tail.Length = FMath::Min(FMath::Clamp(Speed * 0.0022f, 45.0f, 220.0f) * Size, Distance);
	Tail.Size0 = Tail.Size1 = 4.5f * Size;
	Tail.Intensity0 = Tail.Intensity1 = 11.0f * Bright;
	Tail.Color = SOSlug::Trail;
	Spawn(Tail);
	// the amber field round it, and the white-hot slug in it (at the trail's front)
	FSOFxParticle Field;
	Field.Kind = ESOFxKind::Glow;
	Field.Position = From;
	Field.Velocity = Tail.Velocity;
	Field.Delay = Delay;
	Field.Life = Flight;
	Field.Size0 = Field.Size1 = 19.0f * Size * FMath::Sqrt(Bright);
	Field.Intensity0 = Field.Intensity1 = 8.0f * Bright;
	Field.Color = SOSlug::Shell;
	Spawn(Field);
	FSOFxParticle Slug = Field;
	Slug.Size0 = Slug.Size1 = 6.0f * Size;
	Slug.Intensity0 = Slug.Intensity1 = 34.0f * Bright;
	Slug.Color = SOSlug::Core;
	Spawn(Slug);
	// a hot crystal sheds a few gold sparks behind it (more as the gun heats)
	const int32 Sheds = FMath::Clamp(FMath::RoundToInt(Distance / 700.0f * Bright), 0, 5);
	for (int32 i = 0; i < Sheds; ++i)
	{
		const float Along = Distance * (i + Random.FRandRange(0.2f, 0.8f)) / FMath::Max(Sheds, 1);
		FSOFxParticle Mote;
		Mote.Kind = ESOFxKind::Glow;
		Mote.Delay = Delay + Along / Rel;
		Mote.Position = From + Axis * Along + Carry * (Along / Rel);
		Mote.Velocity = Random.VRand() * 40.0f + FVector(0.0f, 0.0f, -60.0f) + Carry;
		Mote.Gravity = 300.0f;
		Mote.Life = Random.FRandRange(0.08f, 0.16f);
		Mote.Size0 = 2.2f * Size;
		Mote.Size1 = 0.6f * Size;
		Mote.Intensity0 = 14.0f;
		Mote.Intensity1 = 0.0f;
		Mote.Color = SOSlug::SparkGold;
		Spawn(Mote);
	}
}

void USOFxSubsystem::SlugImpact(const FVector& Point, const FVector& Normal, float Size, float Delay, bool bFlesh, float Splash)
{
	const FVector N = Normal.GetSafeNormal(UE_SMALL_NUMBER, FVector::UpVector);
	const float R = 24.0f * Size;
	// the shell ruptures: a sharp thermal flash (short and hard: a crack, not a bloom)
	FSOFxParticle Flash;
	Flash.Kind = ESOFxKind::Glow;
	Flash.Position = Point + N * R * 0.25f;
	Flash.Delay = Delay;
	Flash.Life = 0.08f;
	Flash.Size0 = R * 1.1f;
	Flash.Size1 = R * 1.6f;
	Flash.Intensity0 = 18.0f;
	Flash.Intensity1 = 0.0f;
	Flash.Color = SOSlug::Burst;
	Spawn(Flash);
	FSOFxParticle Hot = Flash;
	Hot.Life = 0.045f;
	Hot.Size0 = R * 0.5f;
	Hot.Size1 = R * 0.3f;
	Hot.Intensity0 = 34.0f;
	Hot.Color = SOSlug::Core;
	Spawn(Hot);
	FSOFxParticle Crack;                                    // the rupture's tongues, out of the surface
	Crack.Kind = ESOFxKind::Star;
	Crack.Position = Point + N * 2.0f;
	Crack.Axis = N;
	Crack.Delay = Delay;
	Crack.Life = 0.06f;
	Crack.Length = R * 1.3f;
	Crack.Size0 = R * 0.9f;
	Crack.Size1 = R * 1.2f;
	Crack.Intensity0 = 16.0f;
	Crack.Intensity1 = 0.0f;
	Crack.Color = SOSlug::Burst;
	Crack.Spin = Random.FRandRange(0.0f, 360.0f);
	Spawn(Crack);
	// white and gold sparks thrown out off the surface, falling
	const FVector Side = FVector::CrossProduct(N, FMath::Abs(N.Z) < 0.9f ? FVector::UpVector : FVector::ForwardVector).GetSafeNormal();
	const int32 Sparks = bFlesh ? 5 : 12;
	for (int32 i = 0; i < Sparks; ++i)
	{
		const FVector Out = FQuat(N, (i + Random.FRand()) / Sparks * 2.0f * UE_PI).RotateVector(Side);
		FSOFxParticle Mote;
		Mote.Kind = ESOFxKind::Streak;
		Mote.Position = Point + N * 2.0f;
		Mote.Velocity = (Out + N * Random.FRandRange(0.3f, 1.1f)) * Random.FRandRange(R * 14.0f, R * 28.0f);
		Mote.Gravity = 900.0f;
		Mote.Drag = 3.0f;
		Mote.Delay = Delay;
		Mote.Life = Random.FRandRange(0.12f, 0.30f);
		Mote.Size0 = 1.5f * Size;
		Mote.Size1 = 0.5f * Size;
		Mote.Intensity0 = 26.0f;
		Mote.Intensity1 = 0.0f;
		Mote.Color = (i % 2 == 0) ? SOSlug::SparkWhite : SOSlug::SparkGold;
		Spawn(Mote);
	}
	const double Now = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.0;
	if (Now - LastPlasmaLightTime > 0.04 || FVector::DistSquared(Point, LastPlasmaLightAt) > FMath::Square(260.0f))
	{
		LastPlasmaLightTime = Now;
		LastPlasmaLightAt = Point;
		PendingLights.Add({ Point + N * 30.0f, SOSlug::Burst, FMath::Clamp(260.0f * Size * Size, 110.0f, 1600.0f), 0.08f, Delay });
	}
	if (Splash > 0.0f)
	{
		// a Breach Charge: the whole charge goes (the burst's own fire and smoke)
		Blast(Point, N, Splash, EBlast::Fire, SOSlug::Burst, Delay);
	}
	if (bFlesh)
	{
		return; // (into a body the rest is the body's: it bleeds)
	}
	// dark smoke off what it burned, and the place glowing where the crystal went in
	for (int32 i = 0; i < 3; ++i)
	{
		FSOFxParticle Puff;
		Puff.Kind = ESOFxKind::Smoke;
		Puff.Position = Point + N * R * 0.3f + Random.VRand() * R * 0.2f;
		Puff.Velocity = N * R * 1.2f + Random.VRand() * R * 0.5f + FVector(0.0f, 0.0f, 28.0f);
		Puff.Drag = 2.2f;
		Puff.Delay = Delay + Random.FRandRange(0.01f, 0.05f);
		Puff.Life = Random.FRandRange(0.8f, 1.3f);
		Puff.Size0 = R * 0.35f;
		Puff.Size1 = R * Random.FRandRange(1.3f, 1.8f);
		Puff.Intensity0 = 0.6f;
		Puff.Color = SOSlug::Smoke;
		Puff.Spin = Random.FRandRange(0.0f, 360.0f);
		Spawn(Puff);
	}
	FSOFxParticle Ember;
	Ember.Kind = ESOFxKind::Glow;
	Ember.Position = Point + N * 2.0f;
	Ember.Delay = Delay;
	Ember.Life = 0.5f;
	Ember.Size0 = 12.0f * Size;
	Ember.Size1 = 4.0f * Size;
	Ember.Intensity0 = 10.0f;
	Ember.Intensity1 = 0.0f;
	Ember.Color = SOSlug::Shell;
	Spawn(Ember);
}

void USOFxSubsystem::SlugFlash(const FVector& Muzzle, const FVector& Dir, float Scale, bool bViewmodel, float Bright, bool bThroughScope)
{
	if (bThroughScope)
	{
		return;
	}
	const FVector D = Dir.GetSafeNormal();
	// the rails' discharge: a hard white-gold flash, no flame and no smoke (nothing burns: the slug is thrown)
	FSOFxParticle Flash;
	Flash.Kind = ESOFxKind::Glow;
	Flash.Position = Muzzle + D * 3.0f * Scale;
	Flash.Life = 0.05f;
	Flash.Size0 = 16.0f * Scale;
	Flash.Size1 = 7.0f * Scale;
	Flash.Intensity0 = 14.0f * Bright;
	Flash.Intensity1 = 0.0f;
	Flash.Color = SOSlug::Shell;
	Spawn(Flash);
	FSOFxParticle Core = Flash;
	Core.Life = 0.035f;
	Core.Size0 = 7.0f * Scale;
	Core.Size1 = 3.0f * Scale;
	Core.Intensity0 = 30.0f * Bright;
	Core.Color = SOSlug::Core;
	Spawn(Core);
	// the amber field tearing off the slug as it leaves: a few gold sparks forward and out
	for (int32 i = 0; i < 4; ++i)
	{
		FSOFxParticle Mote;
		Mote.Kind = ESOFxKind::Streak;
		Mote.Position = Muzzle + D * 4.0f * Scale;
		Mote.Velocity = (D + Random.VRand() * 0.6f) * Random.FRandRange(300.0f, 650.0f) * Scale;
		Mote.Drag = 6.0f;
		Mote.Life = Random.FRandRange(0.05f, 0.10f);
		Mote.Size0 = 1.2f * Scale;
		Mote.Size1 = 0.4f * Scale;
		Mote.Intensity0 = 20.0f * Bright;
		Mote.Intensity1 = 0.0f;
		Mote.Color = SOSlug::SparkGold;
		Spawn(Mote);
	}
	FlashLight(Muzzle + D * (bViewmodel ? 120.0f : 10.0f) - FVector(0.0f, 0.0f, bViewmodel ? 22.0f : 0.0f), 220.0f * Scale * (bViewmodel ? 0.25f : 1.0f),
		SOSlug::Shell, 0.05f);
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
	const bool bOnGround = N.Z > 0.6f;
	if (Kind == EBlast::Fire)
	{
		// the owner's guide: "powerful area damage ... large and cinematic ... reactive environment": debris thrown
		// out and landing, embers, a column of smoke standing after it, the ground scorched, the shock racing out
		// along the ground, and fire left burning on a big one
		for (int32 i = 0; i < 14; ++i)
		{
			FSOFxParticle D;
			D.Kind = ESOFxKind::Smoke;
			D.Position = Point + N * 10.0f;
			D.Velocity = Random.VRandCone(N, FMath::DegreesToRadians(60.0f)) * Random.FRandRange(R * 3.0f, R * 8.0f);
			D.Gravity = 980.0f;
			D.Drag = 0.4f;
			D.Delay = Delay;
			D.Life = Random.FRandRange(1.0f, 2.2f);
			D.Size0 = D.Size1 = Random.FRandRange(2.5f, 6.0f) * FMath::Sqrt(R / 100.0f);
			D.Intensity0 = D.Intensity1 = 1.0f;
			D.Color = FLinearColor(0.12f, 0.1f, 0.09f);
			D.Spin = Random.FRandRange(0.0f, 360.0f);
			if (bOnGround)
			{
				D.FloorZ = Point.Z + 2.0f;
				D.Bounce = 0.3f;
			}
			Spawn(D);
		}
		for (int32 i = 0; i < 16; ++i)
		{
			FSOFxParticle E;
			E.Kind = ESOFxKind::Glow;
			E.Position = Point + N * 10.0f;
			E.Velocity = Random.VRandCone(N, FMath::DegreesToRadians(70.0f)) * Random.FRandRange(R * 2.0f, R * 6.0f);
			E.Gravity = 400.0f;
			E.Drag = 1.2f;
			E.Delay = Delay;
			E.Life = Random.FRandRange(0.7f, 1.5f);
			E.Size0 = E.Size1 = 1.6f;
			E.Intensity0 = 14.0f;
			E.Color = Spark;
			Spawn(E);
		}
		for (int32 i = 0; i < 6; ++i)
		{
			FSOFxParticle Column;
			Column.Kind = ESOFxKind::Smoke;
			Column.Position = Point + N * R * 0.3f + Random.VRand() * R * 0.2f;
			Column.Velocity = N * Random.FRandRange(R * 0.5f, R * 0.9f) + FVector(0, 0, 60.0f) + Random.VRand() * 20.0f;
			Column.Drag = 1.0f;
			Column.Delay = Delay + 0.1f + i * 0.05f;
			Column.Life = Random.FRandRange(2.5f, 4.0f);
			Column.Size0 = R * 0.4f;
			Column.Size1 = R * Random.FRandRange(1.6f, 2.4f);
			Column.Intensity0 = 0.55f;
			Column.Color = FLinearColor(0.12f, 0.11f, 0.1f);
			Column.Spin = Random.FRandRange(0.0f, 360.0f);
			Spawn(Column);
		}
		if (bOnGround)
		{
			if (Delay <= 0.0f)
			{
				AddDecal(Point, N, R * 0.9f);
			}
			Shockwave(Point, R * 1.6f, Fire, Delay);
			if (R >= 120.0f)
			{
				// (a rocket's, a grenade's: it burns on for a while)
				Burns.Add({ Point, N, R * 0.45f, -Delay, R >= 200.0f ? 4.0f : 2.0f, 0.0f });
			}
		}
	}
	else if (Kind == EBlast::Zap)
	{
		// an energy burst: arcs of light stepping out from the point in jagged chains, a ring opening on the surface
		for (int32 Arc = 0; Arc < 8; ++Arc)
		{
			FVector At = Point + N * 4.0f;
			FVector Dir = Random.VRandCone(N, FMath::DegreesToRadians(80.0f));
			for (int32 Step = 0; Step < 4; ++Step)
			{
				const float Len = Random.FRandRange(R * 0.15f, R * 0.35f);
				FSOFxParticle S;
				S.Kind = ESOFxKind::Streak;
				S.Position = At + Dir * Len;
				S.Axis = Dir;
				S.Length = Len;
				S.bWhole = true;
				S.Delay = Delay + Step * 0.012f;
				S.Life = Random.FRandRange(0.06f, 0.12f);
				S.Size0 = S.Size1 = Random.FRandRange(1.5f, 3.0f);
				S.Intensity0 = 30.0f;
				S.bHold = true;
				S.Color = FMath::Lerp(Color, FLinearColor::White, 0.4f);
				Spawn(S);
				At += Dir * Len;
				Dir = (Dir + Random.VRand() * 0.7f).GetSafeNormal();
			}
		}
		FSOFxParticle Ring;
		Ring.Kind = ESOFxKind::Glow;
		Ring.Position = Point + N * 2.0f;
		Ring.Axis = N;
		Ring.bFlat = true;
		Ring.Delay = Delay;
		Ring.Life = 0.25f;
		Ring.Size0 = R * 0.2f;
		Ring.Size1 = R * 2.2f;
		Ring.Intensity0 = 7.0f;
		Ring.Color = Color;
		Spawn(Ring);
	}
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

void USOFxSubsystem::Impact(const FVector& Point, const FVector& Normal, bool bFlesh, const FLinearColor& Blood, float Delay, bool bDecal, ESurface Surface)
{
	if (Delay > 0.0f)
	{
		Pending.Add({ Point, Normal.GetSafeNormal(), Blood, Delay, bFlesh, bDecal, Surface });
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

	// what the surface gives (the owner's guide: each its own look and sound)
	auto Sparks = [&](int32 Count, float Speed, float Life, float Cone, float Bright, float Width = 1.3f)
	{
		for (int32 i = 0; i < Count; ++i)
		{
			FSOFxParticle S;
			S.Kind = ESOFxKind::Streak;
			S.Position = Point + N * 1.0f;
			S.Velocity = Random.VRandCone(N, FMath::DegreesToRadians(Cone)) * Random.FRandRange(Speed * 0.35f, Speed);
			S.Gravity = 980.0f;
			S.Drag = 2.0f;
			S.Life = Random.FRandRange(Life * 0.5f, Life);
			S.Size0 = S.Size1 = Width;
			S.Intensity0 = Bright;
			S.Color = Spark;
			Spawn(S);
		}
	};
	auto Hot = [&](float Size, float Bright, const FLinearColor& Col)
	{
		FSOFxParticle H;
		H.Kind = ESOFxKind::Glow;
		H.Position = Point + N * 2.0f;
		H.Life = 0.07f;
		H.Size0 = Size;
		H.Size1 = Size * 0.33f;
		H.Intensity0 = Bright;
		H.Color = Col;
		Spawn(H);
	};
	auto Puff = [&](int32 Count, const FLinearColor& Col, float Size, float Life, float Speed, float Opacity)
	{
		for (int32 i = 0; i < Count; ++i)
		{
			FSOFxParticle D;
			D.Kind = ESOFxKind::Smoke;
			D.Position = Point + N * 4.0f;
			D.Velocity = N * Random.FRandRange(Speed * 0.4f, Speed) + Random.VRand() * Speed * 0.25f;
			D.Drag = 3.0f;
			D.Gravity = -10.0f;
			D.Life = Random.FRandRange(Life * 0.7f, Life);
			D.Size0 = Size * 0.2f;
			D.Size1 = Random.FRandRange(Size * 0.7f, Size);
			D.Intensity0 = Opacity;
			D.Color = Col;
			D.Spin = Random.FRandRange(0.0f, 360.0f);
			Spawn(D);
		}
	};
	// bits thrown off (chips, crumbs, splinters, drops): small, with weight, in the surface's own colour
	auto Bits = [&](int32 Count, const FLinearColor& Col, float Size, float Speed, float Cone, bool bStreak = false)
	{
		for (int32 i = 0; i < Count; ++i)
		{
			FSOFxParticle B;
			B.Kind = bStreak ? ESOFxKind::Streak : ESOFxKind::Smoke;
			B.Position = Point + N * 2.0f;
			B.Velocity = Random.VRandCone(N, FMath::DegreesToRadians(Cone)) * Random.FRandRange(Speed * 0.3f, Speed);
			B.Gravity = 980.0f;
			B.Drag = 0.8f;
			B.Life = Random.FRandRange(0.35f, 0.7f);
			B.Size0 = B.Size1 = Random.FRandRange(Size * 0.6f, Size);
			B.Intensity0 = bStreak ? 1.6f : 1.0f;
			B.Intensity1 = bStreak ? 0.8f : 0.8f;
			B.Color = Col;
			B.Spin = Random.FRandRange(0.0f, 360.0f);
			Spawn(B);
		}
	};
	const TCHAR* Sound = TEXT("impact_hard");
	bool bHole = bDecal;
	switch (Surface)
	{
	case ESurface::Metal:
		// sparks and metal debris: a hard bright shower, ricochets skating off at a glance, a bright hot point
		Sparks(16, 1500.0f, 0.45f, 70.0f, 40.0f);
		Sparks(3, 1800.0f, 0.3f, 88.0f, 30.0f, 2.0f);
		Hot(22.0f, 34.0f, FMath::Lerp(Spark, FLinearColor::White, 0.4f));
		Bits(5, FLinearColor(0.5f, 0.5f, 0.52f), 1.6f, 500.0f, 60.0f);
		Puff(2, FLinearColor(0.5f, 0.5f, 0.52f), 40.0f, 0.7f, 100.0f, 0.5f);
		Sound = TEXT("impact_metal");
		break;
	case ESurface::Dirt:
	case ESurface::Grass:
		// a clod thrown up: no spark in earth; dust and crumbs, and torn grass where there is grass
		Puff(6, Surface == ESurface::Grass ? FLinearColor(0.34f, 0.32f, 0.2f) : Earth, 85.0f, 1.2f, 170.0f, 0.95f);
		Bits(10, Surface == ESurface::Grass ? FLinearColor(0.25f, 0.33f, 0.14f) : Earth * 0.8f, 3.6f, 420.0f, 45.0f);
		Sound = TEXT("impact_dirt");
		bHole = false;
		break;
	case ESurface::Wood:
		// splinters: pale slivers spinning off, a little dust, one or two sparks off a nail
		Bits(8, Wood, 2.2f, 650.0f, 50.0f, true);
		Puff(3, FLinearColor(0.55f, 0.48f, 0.38f), 50.0f, 0.9f, 120.0f, 0.7f);
		Sparks(2, 900.0f, 0.2f, 60.0f, 20.0f);
		Sound = TEXT("impact_wood");
		break;
	case ESurface::Water:
	{
		// a splash: white drops thrown up, a ring opening on the surface, a mist hanging over it
		Bits(12, Water, 2.4f, 520.0f, 28.0f);
		Puff(2, Water, 40.0f, 0.5f, 120.0f, 0.35f);
		FSOFxParticle Ring;
		Ring.Kind = ESOFxKind::Smoke;
		Ring.Position = Point + N * 1.0f;
		Ring.Axis = N;
		Ring.bFlat = true;
		Ring.Life = 0.45f;
		Ring.Size0 = 6.0f;
		Ring.Size1 = 70.0f;
		Ring.Intensity0 = 0.55f;
		Ring.Color = Water;
		Spawn(Ring);
		Sound = TEXT("impact_water");
		bHole = false;
		break;
	}
	default:
		// concrete: dust and fragments; a few sparks off the aggregate, chips of the surface
		Sparks(6, 1100.0f, 0.35f, 65.0f, 30.0f);
		Hot(16.0f, 20.0f, Spark);
		Puff(5, Dust, 90.0f, 1.2f, 170.0f, 0.9f);
		Bits(8, Dust * 0.85f, 3.0f, 480.0f, 50.0f);
		break;
	}
	if (bHole)
	{
		AddDecal(Point, N);
	}
	USOSoundLibrary::PlayAt(this, Sound, Point, 0.8f, 0.1f, ESOSoundRange::Near);
}

void USOFxSubsystem::HitKind(const FVector& Point, const FVector& Normal, bool bShield, bool bShieldBroken, bool bCrit, bool bWeak, const FLinearColor& Color)
{
	const FVector N = Normal.GetSafeNormal(1e-4f, FVector::UpVector);
	const FVector Side = FVector::CrossProduct(N, FMath::Abs(N.Z) < 0.9f ? FVector::UpVector : FVector::ForwardVector).GetSafeNormal();
	const FVector Up2 = FVector::CrossProduct(Side, N);
	if (bShield || bShieldBroken)
	{
		// the shield's skin: a hexagonal cell at the hit and a ring of six round it, lit and gone; broken, every cell
		// is thrown off the body and the whole skin flashes
		const float Cell = 9.0f;
		for (int32 i = 0; i < 7; ++i)
		{
			const float A = FMath::DegreesToRadians(60.0f * (i - 1));
			const FVector Off = i == 0 ? FVector::ZeroVector : (Side * FMath::Cos(A) + Up2 * FMath::Sin(A)) * Cell * 1.75f;
			FSOFxParticle C;
			C.Kind = ESOFxKind::Cell;
			C.Position = Point + N * 1.5f + Off;
			C.Axis = N;
			C.bFlat = true;
			C.Spin = FMath::RadiansToDegrees(FMath::Atan2(Up2.Z, Side.Z)); // (the cells share one lattice)
			C.Life = bShieldBroken ? 0.5f : (i == 0 ? 0.3f : 0.22f);
			C.Size0 = C.Size1 = Cell;
			C.Intensity0 = i == 0 ? 9.0f : 5.0f;
			C.Color = Color;
			if (bShieldBroken)
			{
				C.Velocity = Off.GetSafeNormal(1e-4f, N) * 180.0f + N * 90.0f + Random.VRand() * 40.0f;
				C.Gravity = 400.0f;
				C.Drag = 1.0f;
				C.bFlat = false;
			}
			Spawn(C);
		}
		FSOFxParticle Flash;
		Flash.Kind = ESOFxKind::Glow;
		Flash.Position = Point + N * 3.0f;
		Flash.Life = bShieldBroken ? 0.16f : 0.08f;
		Flash.Size0 = bShieldBroken ? 60.0f : 26.0f;
		Flash.Size1 = bShieldBroken ? 90.0f : 10.0f;
		Flash.Intensity0 = bShieldBroken ? 14.0f : 8.0f;
		Flash.Color = FMath::Lerp(Color, FLinearColor::White, bShieldBroken ? 0.6f : 0.3f);
		Spawn(Flash);
		if (bShieldBroken)
		{
			for (int32 i = 0; i < 10; ++i)
			{
				const float A = Random.FRandRange(0.0f, UE_TWO_PI);
				FSOFxParticle Shard;
				Shard.Kind = ESOFxKind::Cell;
				Shard.Position = Point + N * 2.0f + (Side * FMath::Cos(A) + Up2 * FMath::Sin(A)) * Random.FRandRange(8.0f, 30.0f);
				Shard.Velocity = (Shard.Position - Point).GetSafeNormal() * Random.FRandRange(120.0f, 260.0f) + N * Random.FRandRange(40.0f, 120.0f);
				Shard.Gravity = 500.0f;
				Shard.Drag = 1.2f;
				Shard.Life = Random.FRandRange(0.4f, 0.7f);
				Shard.Size0 = Shard.Size1 = Random.FRandRange(5.0f, 9.0f);
				Shard.Intensity0 = 6.0f;
				Shard.Color = Color;
				Shard.Spin = Random.FRandRange(0.0f, 360.0f);
				Spawn(Shard);
			}
			USOSoundLibrary::PlayAt(this, TEXT("shield_break"), Point, 0.9f, 0.05f, ESOSoundRange::Near);
		}
		else
		{
			USOSoundLibrary::PlayAt(this, TEXT("shield_hit"), Point, 0.6f, 0.08f, ESOSoundRange::Near);
		}
	}
	if (bCrit || bWeak)
	{
		// larger: a flare, and lines of light out of it; a weak point bursts in its own colour with a ring opening
		// on the surface
		FSOFxParticle Flare;
		Flare.Kind = ESOFxKind::Glow;
		Flare.Position = Point + N * 3.0f;
		Flare.Life = 0.12f;
		Flare.Size0 = bWeak ? 52.0f : 38.0f;
		Flare.Size1 = 12.0f;
		Flare.Intensity0 = bWeak ? 26.0f : 20.0f;
		Flare.Color = FMath::Lerp(Color, FLinearColor::White, 0.35f);
		Spawn(Flare);
		for (int32 i = 0; i < (bWeak ? 10 : 6); ++i)
		{
			const float A = UE_TWO_PI * i / (bWeak ? 10.0f : 6.0f) + Random.FRandRange(-0.2f, 0.2f);
			FSOFxParticle L;
			L.Kind = ESOFxKind::Streak;
			L.Position = Point + N * 3.0f;
			L.Axis = (Side * FMath::Cos(A) + Up2 * FMath::Sin(A) + N * 0.3f).GetSafeNormal();
			L.Velocity = L.Axis * Random.FRandRange(500.0f, 900.0f);
			L.Length = bWeak ? 40.0f : 26.0f;
			L.Life = 0.14f;
			L.Size0 = L.Size1 = bWeak ? 2.6f : 2.0f;
			L.Intensity0 = 24.0f;
			L.Color = Color;
			Spawn(L);
		}
		if (bWeak)
		{
			FSOFxParticle Ring;
			Ring.Kind = ESOFxKind::Glow;
			Ring.Position = Point + N * 2.0f;
			Ring.Axis = N;
			Ring.bFlat = true;
			Ring.Life = 0.22f;
			Ring.Size0 = 14.0f;
			Ring.Size1 = 95.0f;
			Ring.Intensity0 = 6.0f;
			Ring.Color = Color;
			Spawn(Ring);
		}
		FlashLight(Point + N * 25.0f, bWeak ? 900.0f : 500.0f, Color, 0.1f);
	}
}

void USOFxSubsystem::Burn(const FVector& Point, const FVector& Normal, float Radius, float Duration)
{
	Burns.Add({ Point, Normal.GetSafeNormal(1e-4f, FVector::UpVector), FMath::Max(Radius, 20.0f), 0.0f, FMath::Max(Duration, 0.3f), 0.0f });
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

void USOFxSubsystem::AddDecal(const FVector& Point, const FVector& Normal, float Size)
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
	const float K = Size / 4.5f;
	Decal->SetWorldScale3D(FVector(FMath::Max(1.0f, K * 0.5f), K * Random.FRandRange(0.8f, 1.2f), K * Random.FRandRange(0.8f, 1.2f)));
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
			Impact(P.Point, P.Normal, P.bFlesh, P.Blood, 0.0f, P.bDecal, P.Surface);
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

	for (int32 i = Burns.Num() - 1; i >= 0; --i)
	{
		FBurn& B = Burns[i];
		B.Age += DeltaTime;
		if (B.Age >= B.Life)
		{
			Burns.RemoveAtSwap(i, 1, EAllowShrinking::No);
			continue;
		}
		const float Left = FMath::Clamp((B.Life - B.Age) / (B.Life * 0.35f), 0.0f, 1.0f); // (it dies down in its last third)
		B.Due -= DeltaTime;
		while (B.Due <= 0.0f)
		{
			B.Due += 0.02f / FMath::Max(Left, 0.15f);
			const FVector Side = FVector::CrossProduct(B.Normal, FMath::Abs(B.Normal.Z) < 0.9f ? FVector::UpVector : FVector::ForwardVector).GetSafeNormal();
			const FVector Up2 = FVector::CrossProduct(Side, B.Normal);
			const float A = Random.FRandRange(0.0f, UE_TWO_PI), R = B.Radius * FMath::Sqrt(Random.FRand());
			const FVector At = B.Point + (Side * FMath::Cos(A) + Up2 * FMath::Sin(A)) * R + B.Normal * 3.0f;
			// a flame: a tongue of light rising off the patch, orange to a dull red as it goes
			FSOFxParticle F;
			F.Kind = ESOFxKind::Star;
			F.Position = At;
			F.Axis = (B.Normal + FVector(0, 0, 0.6f) + Random.VRand() * 0.25f).GetSafeNormal();
			F.Velocity = F.Axis * Random.FRandRange(40.0f, 90.0f);
			F.Drag = 1.0f;
			F.Life = Random.FRandRange(0.25f, 0.45f);
			const float Tall = Random.FRandRange(30.0f, 55.0f) * (0.6f + 0.4f * Left) * FMath::Sqrt(B.Radius / 70.0f);
			F.Length = Tall;
			F.Size0 = Tall * 0.35f;
			F.Size1 = Tall * 0.2f;
			F.Intensity0 = 12.0f * Left;
			F.Intensity1 = 0.0f;
			F.Color = FLinearColor(1.0f, Random.FRandRange(0.45f, 0.7f), 0.15f);
			F.Spin = Random.FRandRange(0.0f, 360.0f);
			Spawn(F);
			FSOFxParticle Core; // the heat at its root
			Core.Kind = ESOFxKind::Glow;
			Core.Position = At;
			Core.Velocity = F.Velocity * 0.5f;
			Core.Life = F.Life;
			Core.Size0 = Tall * 0.45f;
			Core.Size1 = Tall * 0.25f;
			Core.Intensity0 = 8.0f * Left;
			Core.Color = FLinearColor(1.0f, 0.62f, 0.2f);
			Spawn(Core);
			if (Random.FRand() < 0.35f)
			{
				FSOFxParticle E; // an ember carried up, falling back
				E.Kind = ESOFxKind::Glow;
				E.Position = At;
				E.Velocity = FVector(0, 0, Random.FRandRange(120.0f, 220.0f)) + Random.VRand() * 50.0f;
				E.Gravity = 180.0f;
				E.Drag = 0.6f;
				E.Life = Random.FRandRange(0.8f, 1.6f);
				E.Size0 = E.Size1 = 1.4f;
				E.Intensity0 = 12.0f;
				E.Color = Spark;
				Spawn(E);
			}
			if (Random.FRand() < 0.3f)
			{
				FSOFxParticle S; // smoke off the fire
				S.Kind = ESOFxKind::Smoke;
				S.Position = At + B.Normal * 12.0f;
				S.Velocity = FVector(0, 0, Random.FRandRange(45.0f, 80.0f)) + Random.VRand() * 20.0f;
				S.Drag = 0.8f;
				S.Life = Random.FRandRange(1.4f, 2.4f);
				S.Size0 = 10.0f;
				S.Size1 = Random.FRandRange(45.0f, 80.0f);
				S.Intensity0 = 0.45f;
				S.Color = FLinearColor(0.14f, 0.13f, 0.12f);
				S.Spin = Random.FRandRange(0.0f, 360.0f);
				Spawn(S);
			}
		}
	}
	for (int32 i = Particles.Num() - 1; i >= 0; --i)
	{
		FSOFxParticle& P = Particles[i];
		if (P.Delay > 0.0f)
		{
			P.Delay -= DeltaTime;
			if (P.Anchor.IsSet())
			{
				const FVector Now = P.Anchor.Gun->RigPointToWorld(P.Anchor.Local, P.Anchor.bViewmodel);
				P.Position += Now - P.Anchor.Last;
				P.Anchor.Last = Now;
			}
			continue;
		}
		P.Age += DeltaTime;
		if (P.Age >= P.Life)
		{
			Particles.RemoveAtSwap(i, 1, EAllowShrinking::No);
			continue;
		}
		if (P.Anchor.IsSet())
		{
			// held to its gun: moved by however far the gun's point moved since last frame (its own motion on top)
			const FVector Now = P.Anchor.Gun->RigPointToWorld(P.Anchor.Local, P.Anchor.bViewmodel);
			P.Position += Now - P.Anchor.Last;
			P.Anchor.Last = Now;
		}
		P.Velocity.Z -= P.Gravity * DeltaTime;
		P.Velocity *= FMath::Exp(-P.Drag * DeltaTime);
		P.Position += P.Velocity * DeltaTime;
		if (P.Bounce > 0.0f && P.Position.Z < P.FloorZ)
		{
			// landed: it bounces, loses most of its run, and comes to rest on the floor
			P.Position.Z = P.FloorZ;
			if (P.Velocity.Z < 0.0f)
			{
				P.Velocity.Z = -P.Velocity.Z * P.Bounce;
				P.Velocity.X *= 0.55f;
				P.Velocity.Y *= 0.55f;
				P.Spin *= 0.5f;
				if (P.Velocity.Z < 30.0f)
				{
					P.Velocity = FVector::ZeroVector;
					P.Gravity = 0.0f;
					P.Bounce = 0.0f;
				}
			}
		}
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
				: (P.Length > 0.0f ? FMath::Min(P.Length, P.Velocity.Size() * P.Age + 1.0f) : FMath::Clamp(P.Velocity.Size() * 0.025f, 2.0f, 42.0f));
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
