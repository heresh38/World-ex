#include "SOAreaSubsystem.h"

#include "Containers/Ticker.h"
#include "Dom/JsonObject.h"
#include "Engine/Engine.h"
#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "HAL/IConsoleManager.h"
#include "Kismet/GameplayStatics.h"
#include "Kismet/KismetSystemLibrary.h"
#include "Misc/FileHelper.h"
#include "Misc/PackageName.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "SOLog.h"
#include "UObject/Package.h"
#include "UObject/UObjectIterator.h"

namespace
{
	/** /Game/Environments/Meridian/SM_x -> /Game/Environments/Meridian; /Game/Audio/S_x -> /Game/Audio. */
	FString FolderOf(const FString& Package)
	{
		TArray<FString> Parts;
		Package.ParseIntoArray(Parts, TEXT("/"));
		if (Parts.Num() < 2 || Parts[0] != TEXT("Game"))
		{
			return FString();
		}
		static const TSet<FString> Deep = { TEXT("Environments"), TEXT("Characters"), TEXT("Props"), TEXT("Weapons") };
		return Deep.Contains(Parts[1]) && Parts.Num() > 3 ? FString::Printf(TEXT("/Game/%s/%s"), *Parts[1], *Parts[2]) : TEXT("/Game/") + Parts[1];
	}

	FString LevelPackage(const FString& Level)
	{
		FString Out = Level;
		int32 Dot = INDEX_NONE;
		if (Out.FindChar(TEXT('.'), Dot))
		{
			Out.LeftInline(Dot);
		}
		return Out;
	}

	USOAreaSubsystem* FromWorld(UWorld* World)
	{
		return USOAreaSubsystem::Get(World);
	}

	FAutoConsoleCommandWithWorldAndArgs GAreasCmd(TEXT("SOAreas"), TEXT("Lists the areas and which one is being played."),
		FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>&, UWorld* World)
		{
			if (const USOAreaSubsystem* Areas = FromWorld(World))
			{
				const FSOArea* Current = Areas->GetCurrent();
				for (const FSOArea& A : Areas->GetAreas())
				{
					UE_LOG(LogShatteredOrbit, Display, TEXT("Area %s%s: %s (%s) %s"), &A == Current ? TEXT("* ") : TEXT(""), *A.Id.ToString(), *A.Name.ToString(), *A.Kind.ToString(), *A.Level);
				}
			}
		}));

	FAutoConsoleCommandWithWorldAndArgs GTravelCmd(TEXT("SOTravel"), TEXT("SOTravel <area>: leaves for another area."),
		FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
		{
			USOAreaSubsystem* Areas = FromWorld(World);
			if (Areas && Args.Num() > 0 && !Areas->Travel(FName(*Args[0])))
			{
				UE_LOG(LogShatteredOrbit, Warning, TEXT("SOTravel: cannot go to '%s'"), *Args[0]);
			}
		}));

	FAutoConsoleCommandWithWorldAndArgs GCensusCmd(TEXT("SOCensus"), TEXT("Logs what is loaded, by content folder, and anything that belongs to another area."),
		FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>&, UWorld* World)
		{
			if (const USOAreaSubsystem* Areas = FromWorld(World))
			{
				Areas->LogCensus();
			}
		}));

	FAutoConsoleCommandWithWorldAndArgs GTourCmd(TEXT("SOAreaTour"), TEXT("SOAreaTour [quit] [area ...]: visits every area (or the ones named) and back, with a census at each (Saved/area_tour.json)."),
		FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
		{
			if (USOAreaSubsystem* Areas = FromWorld(World))
			{
				TArray<FName> Only;
				for (const FString& A : Args)
				{
					if (A != TEXT("quit"))
					{
						Only.Add(FName(*A));
					}
				}
				Areas->StartTour(Args.Contains(TEXT("quit")), Only);
			}
		}));
}

USOAreaSubsystem* USOAreaSubsystem::Get(const UObject* WorldContext)
{
	const UWorld* World = WorldContext ? WorldContext->GetWorld() : nullptr;
	const UGameInstance* Instance = World ? World->GetGameInstance() : nullptr;
	return Instance ? Instance->GetSubsystem<USOAreaSubsystem>() : nullptr;
}

FSimpleMulticastDelegate& USOAreaSubsystem::OnReleaseContent()
{
	static FSimpleMulticastDelegate Delegate;
	return Delegate;
}

void USOAreaSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);
	LoadAreas();
	PreLoadHandle = FCoreUObjectDelegates::PreLoadMap.AddUObject(this, &USOAreaSubsystem::OnPreLoadMap);
	PostLoadHandle = FCoreUObjectDelegates::PostLoadMapWithWorld.AddUObject(this, &USOAreaSubsystem::OnPostLoadMap);
	// one clock for the whole session: it counts down to the census after each arrival
	SettleHandle = FTSTicker::GetCoreTicker().AddTicker(FTickerDelegate::CreateUObject(this, &USOAreaSubsystem::Settle), 0.25f);
}

void USOAreaSubsystem::Deinitialize()
{
	FCoreUObjectDelegates::PreLoadMap.Remove(PreLoadHandle);
	FCoreUObjectDelegates::PostLoadMapWithWorld.Remove(PostLoadHandle);
	FTSTicker::GetCoreTicker().RemoveTicker(SettleHandle);
	Super::Deinitialize();
}

void USOAreaSubsystem::LoadAreas()
{
	Areas.Reset();
	FString Text;
	TSharedPtr<FJsonObject> Root;
	if (!FFileHelper::LoadFileToString(Text, *(FPaths::ProjectDir() / TEXT("Data/areas.json")))
		|| !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Root) || !Root)
	{
		UE_LOG(LogShatteredOrbit, Warning, TEXT("Areas: could not read Data/areas.json"));
		return;
	}
	Shared.Reset();
	Root->TryGetStringArrayField(TEXT("shared"), Shared);
	for (const TSharedPtr<FJsonValue>& V : Root->GetArrayField(TEXT("areas")))
	{
		const TSharedPtr<FJsonObject> O = V->AsObject();
		FSOArea A;
		A.Id = FName(O->GetStringField(TEXT("id")));
		A.Name = FText::FromString(O->GetStringField(TEXT("name")));
		A.Kind = FName(O->GetStringField(TEXT("kind")));
		A.Level = O->GetStringField(TEXT("level"));
		O->TryGetStringField(TEXT("plan"), A.Plan);
		O->TryGetStringArrayField(TEXT("content"), A.Content);
		Areas.Add(A);
	}
}

const FSOArea* USOAreaSubsystem::Find(FName Id) const
{
	return Areas.FindByPredicate([Id](const FSOArea& A) { return A.Id == Id; });
}

const FSOArea* USOAreaSubsystem::FindByLevel(const FString& Level) const
{
	// (a level in play may carry a prefix on its short name: compare the short names)
	const FString Short = FPackageName::GetShortName(LevelPackage(Level));
	return Areas.FindByPredicate([&Short](const FSOArea& A) { return Short.EndsWith(FPackageName::GetShortName(A.Level)); });
}

const FSOArea* USOAreaSubsystem::GetCurrent() const
{
	const UWorld* World = GetGameInstance() ? GetGameInstance()->GetWorld() : nullptr;
	return World ? FindByLevel(World->GetOutermost()->GetName()) : nullptr;
}

bool USOAreaSubsystem::Travel(FName Id)
{
	const FSOArea* Area = Find(Id);
	return Area && TravelToLevel(Area->Level);
}

bool USOAreaSubsystem::TravelToLevel(const FString& Level)
{
	UWorld* World = GetGameInstance() ? GetGameInstance()->GetWorld() : nullptr;
	const FSOArea* Area = FindByLevel(Level);
	if (!World || !Area || World->GetNetMode() == NM_Client)
	{
		return false;
	}
	UE_LOG(LogShatteredOrbit, Log, TEXT("Area: leaving for %s (%s)"), *Area->Name.ToString(), *Area->Level);
	// The old level, everything it built and everything held for it go when the engine loads the new map (it tears
	// the world down and collects the garbage before the new one is built); OnPreLoadMap lets go of what we keep.
	if (World->GetNetMode() == NM_Standalone)
	{
		UGameplayStatics::OpenLevel(World, FName(*Area->Level));
	}
	else
	{
		World->ServerTravel(Area->Level + TEXT("?listen"));
	}
	return true;
}

void USOAreaSubsystem::OnPreLoadMap(const FString& Map)
{
	OnReleaseContent().Broadcast();
}

void USOAreaSubsystem::OnPostLoadMap(UWorld* World)
{
	if (!World || !World->IsGameWorld() || World->GetGameInstance() != GetGameInstance())
	{
		return;
	}
	// once more when the new level stands (what the old one let go of late), then the census when it has settled
	if (GEngine)
	{
		GEngine->ForceGarbageCollection(true);
	}
	SettleAt = FPlatformTime::Seconds() + (TourIndex != INDEX_NONE ? 8.0 : 4.0);
	bSettling = true;
	const FSOArea* Area = GetCurrent();
	UE_LOG(LogShatteredOrbit, Log, TEXT("Area: arrived at %s"), Area ? *Area->Name.ToString() : *World->GetOutermost()->GetName());
}

bool USOAreaSubsystem::Settle(float DeltaSeconds)
{
	if (!bSettling || FPlatformTime::Seconds() < SettleAt)
	{
		return true;
	}
	bSettling = false;
	const float Megabytes = LogCensus();
	if (TourIndex != INDEX_NONE)
	{
		const FSOArea* Area = GetCurrent();
		FString Rows;
		for (const FSOCensusRow& R : Census())
		{
			Rows += FString::Printf(TEXT("%s{\"folder\": \"%s\", \"packages\": %d, \"mb\": %.1f}"), Rows.IsEmpty() ? TEXT("") : TEXT(", "), *R.Folder, R.Packages, R.Megabytes);
		}
		FString LeakList;
		for (const FString& L : Leaks())
		{
			LeakList += FString::Printf(TEXT("%s\"%s\""), LeakList.IsEmpty() ? TEXT("") : TEXT(", "), *L);
		}
		TourReport.Add(FString::Printf(TEXT(" {\"stop\": %d, \"area\": \"%s\", \"mb\": %.1f, \"leaks\": [%s], \"loaded\": [%s]}"), TourIndex,
			Area ? *Area->Id.ToString() : TEXT("?"), Megabytes, *LeakList, *Rows));
		TourStep();
	}
	return true;
}

TArray<FSOCensusRow> USOAreaSubsystem::Census() const
{
	TMap<FString, FSOCensusRow> Rows;
	for (TObjectIterator<UPackage> It; It; ++It)
	{
		const FString Folder = FolderOf(It->GetName());
		if (!Folder.IsEmpty())
		{
			FSOCensusRow& Row = Rows.FindOrAdd(Folder);
			Row.Folder = Folder;
			++Row.Packages;
		}
	}
	for (FThreadSafeObjectIterator It; It; ++It)
	{
		UObject* O = *It;
		// assets only: the live level's own actors and components (the nav mesh being built, ...) are not content,
		// and asking them for their size can wait on their own work
		if (O->IsA<UPackage>() || O->HasAnyFlags(RF_ClassDefaultObject) || O->IsA<UWorld>() || O->GetTypedOuter<UWorld>())
		{
			continue;
		}
		if (FSOCensusRow* Row = Rows.Find(FolderOf(O->GetOutermost()->GetName())))
		{
			Row->Megabytes += static_cast<float>(O->GetResourceSizeBytes(EResourceSizeMode::EstimatedTotal) / (1024.0 * 1024.0));
		}
	}
	TArray<FSOCensusRow> Out;
	Rows.GenerateValueArray(Out);
	Out.Sort([](const FSOCensusRow& A, const FSOCensusRow& B) { return A.Megabytes > B.Megabytes; });
	return Out;
}

TArray<FString> USOAreaSubsystem::Leaks() const
{
	TArray<FString> Out;
	const FSOArea* Current = GetCurrent();
	for (TObjectIterator<UPackage> It; It; ++It)
	{
		const FString Name = It->GetName();
		if (!Name.StartsWith(TEXT("/Game/")) || Shared.ContainsByPredicate([&Name](const FString& Prefix) { return Name.StartsWith(Prefix); }))
		{
			continue;
		}
		for (const FSOArea& A : Areas)
		{
			if (&A == Current)
			{
				continue;
			}
			const bool bTheirLevel = Name == A.Level;
			const bool bTheirs = bTheirLevel || A.Content.ContainsByPredicate([&Name](const FString& Folder) { return Name.StartsWith(Folder + TEXT("/")); });
			const bool bOursToo = Current && Current->Content.ContainsByPredicate([&Name](const FString& Folder) { return Name.StartsWith(Folder + TEXT("/")); });
			if (bTheirs && !bOursToo)
			{
				Out.Add(Name);
				break;
			}
		}
	}
	Out.Sort();
	return Out;
}

float USOAreaSubsystem::LogCensus() const
{
	const FSOArea* Area = GetCurrent();
	UE_LOG(LogShatteredOrbit, Log, TEXT("Area census: counting what is loaded"));
	const TArray<FSOCensusRow> Rows = Census();
	float Total = 0.0f;
	int32 Packages = 0;
	for (const FSOCensusRow& R : Rows)
	{
		Total += R.Megabytes;
		Packages += R.Packages;
	}
	UE_LOG(LogShatteredOrbit, Display, TEXT("Area census (%s): %d packages, %.0f MB of the game's content loaded"), Area ? *Area->Id.ToString() : TEXT("no area"), Packages, Total);
	for (const FSOCensusRow& R : Rows)
	{
		UE_LOG(LogShatteredOrbit, Display, TEXT("  %-34s %4d packages %8.1f MB"), *R.Folder, R.Packages, R.Megabytes);
	}
	const TArray<FString> Leaked = Leaks();
	if (Leaked.Num() > 0)
	{
		UE_LOG(LogShatteredOrbit, Warning, TEXT("Area census: %d packages of another area are loaded (first: %s)"), Leaked.Num(), *Leaked[0]);
		for (int32 i = 0; i < FMath::Min(Leaked.Num(), 40); ++i)
		{
			UE_LOG(LogShatteredOrbit, Display, TEXT("  leak: %s"), *Leaked[i]);
		}
	}
	else
	{
		UE_LOG(LogShatteredOrbit, Display, TEXT("Area census: nothing of another area is loaded"));
	}
	return Total;
}

void USOAreaSubsystem::StartTour(bool bQuitAfter, const TArray<FName>& Only)
{
	const FSOArea* Here = GetCurrent();
	if (!Here || TourIndex != INDEX_NONE)
	{
		return;
	}
	// here, then every other area with a return here after each: every pair of "there and back" is in the report
	TourStops.Reset();
	TourReport.Reset();
	TourStops.Add(Here->Id);
	for (const FSOArea& A : Areas)
	{
		if (A.Id != Here->Id && (Only.Num() == 0 || Only.Contains(A.Id)))
		{
			TourStops.Add(A.Id);
			TourStops.Add(Here->Id);
		}
	}
	bTourQuit = bQuitAfter;
	TourIndex = 0;
	SettleAt = FPlatformTime::Seconds() + 1.0;
	bSettling = true;
}

void USOAreaSubsystem::TourStep()
{
	++TourIndex;
	if (TourStops.IsValidIndex(TourIndex) && Travel(TourStops[TourIndex]))
	{
		return;
	}
	const FString Path = FPaths::ProjectSavedDir() / TEXT("area_tour.json");
	FFileHelper::SaveStringToFile(TEXT("[\n") + FString::Join(TourReport, TEXT(",\n")) + TEXT("\n]\n"), *Path);
	UE_LOG(LogShatteredOrbit, Display, TEXT("Area tour done: %d stops, report %s"), TourReport.Num(), *Path);
	TourIndex = INDEX_NONE;
	if (bTourQuit)
	{
		UWorld* World = GetGameInstance() ? GetGameInstance()->GetWorld() : nullptr;
		UKismetSystemLibrary::QuitGame(World, nullptr, EQuitPreference::Quit, false);
	}
}
