#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "SONexusCity.generated.h"

class UInstancedStaticMeshComponent;
class UMaterialInstanceDynamic;
class UMaterialInterface;
class UStaticMesh;

/** One road of the city's network (Data/nexus_plan.json), in world space: for traffic, pedestrians and the map. */
USTRUCT(BlueprintType)
struct SOWORLD_API FSORoadEdge
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "SO|City")
	int32 A = INDEX_NONE;

	UPROPERTY(BlueprintReadOnly, Category = "SO|City")
	int32 B = INDEX_NONE;

	/** highway, ring, primary, secondary, access */
	UPROPERTY(BlueprintReadOnly, Category = "SO|City")
	FName Class;

	/** Kerb to kerb (cm). */
	UPROPERTY(BlueprintReadOnly, Category = "SO|City")
	float Width = 0.0f;

	/** Lanes each way, their width and the half median (cm); traffic keeps right: the lanes of travel A->B lie to
	 *  the right of that direction, the first one Median + LaneWidth / 2 from the centre line. */
	UPROPERTY(BlueprintReadOnly, Category = "SO|City")
	int32 LanesEachWay = 1;

	UPROPERTY(BlueprintReadOnly, Category = "SO|City")
	float LaneWidth = 350.0f;

	UPROPERTY(BlueprintReadOnly, Category = "SO|City")
	float Median = 10.0f;

	/** Centre line, A to B (world, z = road surface). */
	UPROPERTY(BlueprintReadOnly, Category = "SO|City")
	TArray<FVector> Points;
};

/** A rail or metro station on its viaduct. */
USTRUCT(BlueprintType)
struct SOWORLD_API FSOCityStation
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "SO|City")
	FString Name;

	/** rail | metro */
	UPROPERTY(BlueprintReadOnly, Category = "SO|City")
	FName Line;

	/** Deck top at the platform centre; the local X axis runs along the track. */
	UPROPERTY(BlueprintReadOnly, Category = "SO|City")
	FTransform Transform;
};

/**
 * Nexus Prime, the big city: builds itself from Data/nexus_plan.json (tools/city/nexus_plan.py: roads, blocks,
 * lots, districts, rail, metro, wall) and Data/nexus_city.json (tools/blender/nexus_city.py: the baked plan tiles,
 * the building designs per district kind, stations, lane layout). Everything placed is our own Blender kit under
 * /Game/Environments/NexusCity (and the Nexus landmarks under /Game/Environments/Nexus).
 *
 * Everything on the lots and streets comes from Data/nexus_instances.bin (tools/city/nexus_dress.py): one instanced
 * component per mesh. Buildings are unit-footprint designs scaled to their footprint; their custom data (width,
 * depth, height in m, seed, wear, boarded, lit share) lets M_SOFacade keep real bay and floor sizes, age and board up
 * the walls and light a share of the windows at night ("Night", driven from the time of day). Cars carry their paint
 * colour as custom data (M_SOCarPaint). Plan metres (E, N) map to world X = N, Y = E (cm), the Spire at the origin.
 *
 * Built in the editor on construction (transient, nothing saved into the level) and again at BeginPlay.
 */
UCLASS()
class SOWORLD_API ASONexusCity : public AActor
{
	GENERATED_BODY()

public:
	ASONexusCity();

	/** Relative to the project directory. */
	UPROPERTY(EditAnywhere, Category = "SO|City")
	FString PlanFile = TEXT("Data/nexus_plan.json");

	UPROPERTY(EditAnywhere, Category = "SO|City")
	FString CityFile = TEXT("Data/nexus_city.json");

	/** tools/city/nexus_dress.py's placements (buildings, doors, roofs, yards, trees, cars, street life). */
	UPROPERTY(EditAnywhere, Category = "SO|City")
	FString InstanceFile = TEXT("Data/nexus_instances.bin");

	UPROPERTY(EditAnywhere, Category = "SO|City")
	FString MeshFolder = TEXT("/Game/Environments/NexusCity");

	UPROPERTY(EditAnywhere, Category = "SO|City")
	bool bBuildInEditor = true;

	/** The Spire landmark's scale (the kit piece is ~190 m tall). */
	UPROPERTY(EditAnywhere, Category = "SO|City")
	float SpireScale = 2.2f;

	UPROPERTY(Transient, VisibleAnywhere, BlueprintReadOnly, Category = "SO|City")
	TArray<FVector> RoadNodes;

	UPROPERTY(Transient, VisibleAnywhere, BlueprintReadOnly, Category = "SO|City")
	TArray<FSORoadEdge> RoadEdges;

	UPROPERTY(Transient, VisibleAnywhere, BlueprintReadOnly, Category = "SO|City")
	TArray<FSOCityStation> Stations;

	UPROPERTY(Transient, VisibleAnywhere, BlueprintReadOnly, Category = "SO|City")
	int32 NumBuildings = 0;

	UPROPERTY(Transient, VisibleAnywhere, BlueprintReadOnly, Category = "SO|City")
	int32 NumInstances = 0;

	UPROPERTY(Transient, VisibleAnywhere, BlueprintReadOnly, Category = "SO|City")
	int32 MissingMeshes = 0;

	/** Rebuilds everything from the data files. */
	UFUNCTION(BlueprintCallable, CallInEditor, Category = "SO|City")
	void Build();

	/** Plan metres (E, N) -> world (cm). */
	static FVector PlanToWorld(double E, double N, double ZMetres = 0.0) { return FVector(N * 100.0, E * 100.0, ZMetres * 100.0); }

	/** The nearest road node to a world position (INDEX_NONE if none). */
	int32 NearestRoadNode(const FVector& World) const;

	virtual void OnConstruction(const FTransform& Transform) override;
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

private:
	UStaticMesh* LoadMesh(const FString& Name, bool bTiles = false) const;
	UInstancedStaticMeshComponent* Instancer(UStaticMesh* Mesh, int32 CustomFloats, bool bCollide);
	void AddMesh(UStaticMesh* Mesh, const FTransform& Transform, bool bCollide = true);
	void Clear();

	UPROPERTY(Transient)
	TArray<TObjectPtr<UActorComponent>> Built;

	UPROPERTY(Transient)
	TMap<TObjectPtr<UStaticMesh>, TObjectPtr<UInstancedStaticMeshComponent>> Instancers;

	UPROPERTY(Transient)
	TMap<TObjectPtr<UMaterialInterface>, TObjectPtr<UMaterialInstanceDynamic>> FacadeMIDs;

	float NightApplied = -1.0f;
};
