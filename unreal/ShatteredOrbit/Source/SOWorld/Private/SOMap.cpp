#include "SOMap.h"

#include "Components/SceneCaptureComponent2D.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/CollisionProfile.h"
#include "Engine/TextureRenderTarget2D.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "TimerManager.h"

// --- Map point -----------------------------------------------------------------------------------

ASOMapPoint::ASOMapPoint()
{
	PrimaryActorTick.bCanEverTick = false;
	USceneComponent* Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	RootComponent = Root;
	Beacon = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Beacon"));
	Beacon->SetupAttachment(Root);
	// a solid monument: the player can't walk through it and the shoulder camera stops at it
	Beacon->SetCollisionProfileName(UCollisionProfile::BlockAll_ProfileName);
}

void ASOMapPoint::PostInitializeComponents()
{
	Super::PostInitializeComponents();
	if (bFastTravel)
	{
		Tags.AddUnique(TEXT("SOFastTravel"));
	}
}

FTransform ASOMapPoint::ArrivalTransform() const
{
	// a few metres out from the point on its front (+X), facing it, a little above the ground
	const FVector Front = GetActorForwardVector();
	const FVector At = GetActorLocation() + Front * 400.0f + FVector(0.0f, 0.0f, 120.0f);
	return FTransform((-Front).Rotation(), At);
}

FLinearColor ASOMapPoint::KindColor(ESOMapPointKind Kind)
{
	switch (Kind)
	{
	case ESOMapPointKind::FastTravel: return FLinearColor(0.55f, 0.36f, 1.0f);
	case ESOMapPointKind::Vendor: return FLinearColor(0.1f, 0.75f, 1.0f);
	case ESOMapPointKind::Mission: return FLinearColor(1.0f, 0.68f, 0.25f);
	case ESOMapPointKind::BlackMarket: return FLinearColor(1.0f, 0.3f, 0.3f);
	case ESOMapPointKind::PvP: return FLinearColor(0.4f, 0.95f, 0.45f);
	case ESOMapPointKind::SafeZone: return FLinearColor(0.35f, 1.0f, 0.75f);
	case ESOMapPointKind::AreaTravel: return FLinearColor(0.95f, 0.85f, 0.4f);
	default: return FLinearColor(0.85f, 0.9f, 0.97f);
	}
}

FText ASOMapPoint::KindName(ESOMapPointKind Kind)
{
	switch (Kind)
	{
	case ESOMapPointKind::FastTravel: return NSLOCTEXT("SO", "MapFast", "Fast Travel");
	case ESOMapPointKind::Vendor: return NSLOCTEXT("SO", "MapVendor", "Vendor");
	case ESOMapPointKind::Mission: return NSLOCTEXT("SO", "MapMission", "Mission Hub");
	case ESOMapPointKind::BlackMarket: return NSLOCTEXT("SO", "MapBlack", "Black Market");
	case ESOMapPointKind::PvP: return NSLOCTEXT("SO", "MapPvP", "PvP Zone");
	case ESOMapPointKind::SafeZone: return NSLOCTEXT("SO", "MapSafe", "Safe Zone");
	case ESOMapPointKind::AreaTravel: return NSLOCTEXT("SO", "MapArea", "Area Travel");
	default: return NSLOCTEXT("SO", "MapLandmark", "Landmark");
	}
}

// --- Map info ------------------------------------------------------------------------------------

ASOMapInfo::ASOMapInfo()
{
	PrimaryActorTick.bCanEverTick = false;
	RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
}

ASOMapInfo* ASOMapInfo::Get(const UObject* WorldContext)
{
	const UWorld* World = WorldContext ? WorldContext->GetWorld() : nullptr;
	if (!World)
	{
		return nullptr;
	}
	for (TActorIterator<ASOMapInfo> It(World); It; ++It)
	{
		return *It;
	}
	return nullptr;
}

const TArray<FSOAreaInfo>& ASOMapInfo::Areas()
{
	static const TArray<FSOAreaInfo> List = []()
	{
		TArray<FSOAreaInfo> L;
		L.Add({ NSLOCTEXT("SO", "AreaNexus", "Nexus Prime"), TEXT("/Game/Maps/L_Nexus") });
		L.Add({ NSLOCTEXT("SO", "AreaRange", "Proving Range"), TEXT("/Game/Maps/L_TestRange") });
		return L;
	}();
	return List;
}

FVector2D ASOMapInfo::WorldToMap(const FVector& World) const
{
	const FVector D = World - GetActorLocation();
	const float Size = FMath::Max(HalfSize * 2.0f, 1.0f);
	return FVector2D(0.5f + D.Y / Size, 0.5f - D.X / Size);
}

void ASOMapInfo::BeginPlay()
{
	Super::BeginPlay();
	UWorld* World = GetWorld();
	if (!World || World->GetNetMode() == NM_DedicatedServer)
	{
		return;
	}
	MapTexture = NewObject<UTextureRenderTarget2D>(this);
	MapTexture->RenderTargetFormat = ETextureRenderTargetFormat::RTF_RGBA8_SRGB;
	MapTexture->ClearColor = FLinearColor(0.02f, 0.03f, 0.05f, 1.0f);
	MapTexture->InitAutoFormat(1024, 1024);
	MapTexture->UpdateResourceImmediate(true);

	MapCamera = NewObject<USceneCaptureComponent2D>(this, TEXT("MapCamera"));
	MapCamera->SetupAttachment(RootComponent);
	MapCamera->ProjectionType = ECameraProjectionMode::Orthographic;
	MapCamera->OrthoWidth = HalfSize * 2.0f;
	MapCamera->TextureTarget = MapTexture;
	MapCamera->CaptureSource = ESceneCaptureSource::SCS_FinalColorLDR;
	MapCamera->bCaptureEveryFrame = false;
	MapCamera->bCaptureOnMovement = false;
	MapCamera->ShowFlags.SetFog(false);
	MapCamera->ShowFlags.SetAtmosphere(false);
	MapCamera->ShowFlags.SetVolumetricFog(false);
	MapCamera->ShowFlags.SetCloud(false);
	MapCamera->ShowFlags.SetMotionBlur(false);
	MapCamera->PostProcessSettings.bOverride_AutoExposureMinBrightness = true;
	MapCamera->PostProcessSettings.bOverride_AutoExposureMaxBrightness = true;
	MapCamera->PostProcessSettings.AutoExposureMinBrightness = 1.0f;
	MapCamera->PostProcessSettings.AutoExposureMaxBrightness = 1.0f;
	MapCamera->RegisterComponent();
	// high above the centre, looking straight down with world +X at the top of the picture
	MapCamera->SetWorldLocationAndRotation(GetActorLocation() + FVector(0.0f, 0.0f, 60000.0f), FRotator(-90.0f, 0.0f, 0.0f));
	// once the level has streamed its textures in; again a little later in case they were still coming
	World->GetTimerManager().SetTimer(CaptureTimer, FTimerDelegate::CreateWeakLambda(this, [this]()
	{
		Capture();
		if (++Captures >= 2)
		{
			GetWorldTimerManager().ClearTimer(CaptureTimer);
		}
	}), 2.5f, true, 1.0f);
}

void ASOMapInfo::Capture()
{
	if (MapCamera)
	{
		MapCamera->CaptureScene();
	}
}
