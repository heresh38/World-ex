#pragma once

#include "CoreMinimal.h"
#include "Containers/Ticker.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "SOAreaSubsystem.generated.h"

/** A place the game can be in: the proving range, the city, an operation. Data/areas.json lists them. */
USTRUCT(BlueprintType)
struct SOCORE_API FSOArea
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Area")
	FName Id;

	UPROPERTY(BlueprintReadOnly, Category = "Area")
	FText Name;

	/** range, city, operation. */
	UPROPERTY(BlueprintReadOnly, Category = "Area")
	FName Kind;

	/** Its level (/Game/Maps/L_...). */
	UPROPERTY(BlueprintReadOnly, Category = "Area")
	FString Level;

	/** An operation's plan (Data/op_<name>.json). */
	UPROPERTY(BlueprintReadOnly, Category = "Area")
	FString Plan;

	/** Content folders that belong to this area alone: loaded only while it is the one being played. */
	UPROPERTY(BlueprintReadOnly, Category = "Area")
	TArray<FString> Content;
};

/** What is loaded from one content folder. */
USTRUCT(BlueprintType)
struct SOCORE_API FSOCensusRow
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Area")
	FString Folder;

	UPROPERTY(BlueprintReadOnly, Category = "Area")
	int32 Packages = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Area")
	float Megabytes = 0.0f;
};

/**
 * One area at a time. Only the area being played exists: its level, what its level builds when it begins (the city's
 * blocks, an operation's waves and the species it uses) and what that pulls in. Going somewhere else (Travel) lets go
 * of everything the game keeps by hand (OnReleaseContent: sound and other caches drop what they hold), tears the old
 * level down, collects the garbage and only then builds the next: nothing of the city is in memory on the range,
 * nothing of an operation in the city. Lives for the whole session (it is what survives a level change).
 *
 * It can prove it: Census() lists what is loaded by content folder, Leaks() names anything loaded that belongs to
 * another area (Data/areas.json: "content"), and both are logged a few seconds after every arrival. Console:
 * SOAreas, SOTravel <area>, SOCensus, SOAreaTour [quit] [area ...] (visits every area, or the ones named, and comes
 * back after each; writes Saved/area_tour.json).
 */
UCLASS()
class SOCORE_API USOAreaSubsystem : public UGameInstanceSubsystem
{
	GENERATED_BODY()

public:
	static USOAreaSubsystem* Get(const UObject* WorldContext);

	const TArray<FSOArea>& GetAreas() const { return Areas; }
	const FSOArea* Find(FName Id) const;
	const FSOArea* FindByLevel(const FString& Level) const;

	/** The area being played (null: a level that is no area, e.g. a test world). */
	const FSOArea* GetCurrent() const;

	/** Server: leave for another area (false: no such area, or not the server). */
	bool Travel(FName Id);

	/** Server: the same by level path (/Game/Maps/L_...); a level that is no listed area is refused. */
	bool TravelToLevel(const FString& Level);

	/** What is loaded right now from the game's content, by folder, biggest first. */
	TArray<FSOCensusRow> Census() const;

	/** Loaded packages that belong to an area other than the current one (should be empty). */
	TArray<FString> Leaks() const;

	/** Logs the census and the leaks; returns the megabytes loaded from the game's content. */
	float LogCensus() const;

	/** Visits every area in turn and comes back, taking the census a few seconds after each arrival; writes
	 *  Saved/area_tour.json; bQuitAfter closes the game when done. */
	void StartTour(bool bQuitAfter, const TArray<FName>& Only = TArray<FName>());

	/** Reads Data/areas.json again. */
	void Reload() { LoadAreas(); }

	/** Fired just before a level is torn down: whoever keeps loaded content by hand lets go of it here. */
	static FSimpleMulticastDelegate& OnReleaseContent();

	//~ USubsystem
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Deinitialize() override;

private:
	void LoadAreas();
	void OnPreLoadMap(const FString& Map);
	void OnPostLoadMap(UWorld* World);
	bool Settle(float DeltaSeconds);
	void TourStep();

	TArray<FSOArea> Areas;
	/** Packages (prefixes) every area may use although they live in one area's folder (Data/areas.json: "shared"). */
	TArray<FString> Shared;
	FDelegateHandle PreLoadHandle;
	FDelegateHandle PostLoadHandle;
	FTSTicker::FDelegateHandle SettleHandle;
	double SettleAt = 0.0;
	bool bSettling = false;

	// the tour
	TArray<FName> TourStops;
	TArray<FString> TourReport;
	int32 TourIndex = INDEX_NONE;
	bool bTourQuit = false;
};
