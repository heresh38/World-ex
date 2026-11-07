#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "SOMap.generated.h"

class UStaticMeshComponent;
class USceneCaptureComponent2D;
class UTextureRenderTarget2D;

/** What a place on the map is (icon colour and glyph on the mini-map and the map screen). */
UENUM(BlueprintType)
enum class ESOMapPointKind : uint8
{
	Landmark,
	FastTravel,
	Vendor,
	Mission,
	BlackMarket,
	PvP,
	SafeZone,
	/** Leads to another area (another level): the map screen offers the travel. */
	AreaTravel,
};

/**
 * An important place in an area: shown on the mini-map and the map screen; with bFastTravel the player can quick
 * travel to it from the map (it carries the actor tag "SOFastTravel" the server checks). An optional beacon mesh marks
 * it in the world.
 */
UCLASS()
class SOWORLD_API ASOMapPoint : public AActor
{
	GENERATED_BODY()

public:
	ASOMapPoint();

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Map")
	FText Label;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Map")
	FText Subtitle;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Map")
	ESOMapPointKind Kind = ESOMapPointKind::Landmark;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Map")
	bool bFastTravel = true;

	/** AreaTravel: the level it leads to (e.g. /Game/Maps/L_Nexus). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Map")
	FString TravelLevel;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "SO|Map")
	TObjectPtr<UStaticMeshComponent> Beacon;

	static FLinearColor KindColor(ESOMapPointKind Kind);
	static FText KindName(ESOMapPointKind Kind);

	/** Where a traveller arrives (beside the point, facing it). */
	FTransform ArrivalTransform() const;

	virtual void PostInitializeComponents() override;
};

/** An area the player can travel to (another level). */
USTRUCT(BlueprintType)
struct SOWORLD_API FSOAreaInfo
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "SO|Map")
	FText Name;

	UPROPERTY(BlueprintReadOnly, Category = "SO|Map")
	FString Level;
};

/**
 * One per area: its name and extent, and the map picture (a top-down orthographic capture of the level made once it
 * has loaded) the mini-map and the map screen draw. Map space: u to world +Y (east), v down to world -X (north up).
 */
UCLASS()
class SOWORLD_API ASOMapInfo : public AActor
{
	GENERATED_BODY()

public:
	ASOMapInfo();

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Map")
	FText AreaName;

	/** Half the side of the square the map covers (cm), centred on this actor. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Map")
	float HalfSize = 25000.0f;

	UTextureRenderTarget2D* GetMapTexture() const { return MapTexture; }

	/** World position -> map (0..1, may be outside). */
	FVector2D WorldToMap(const FVector& World) const;

	/** The area's map info (null if the level has none). */
	static ASOMapInfo* Get(const UObject* WorldContext);

	/** Every area of the game (Nexus Prime, the test range, ...). */
	static const TArray<FSOAreaInfo>& Areas();

	/** Renders the map picture now (also done automatically after load). */
	void Capture();

	virtual void BeginPlay() override;

private:
	UPROPERTY(Transient)
	TObjectPtr<UTextureRenderTarget2D> MapTexture;

	UPROPERTY(Transient)
	TObjectPtr<USceneCaptureComponent2D> MapCamera;

	FTimerHandle CaptureTimer;
	int32 Captures = 0;
};
