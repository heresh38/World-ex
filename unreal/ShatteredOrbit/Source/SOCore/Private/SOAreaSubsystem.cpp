#include "SOAreaSubsystem.h"

#include "Containers/Ticker.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "AssetRegistry/IAssetRegistry.h"
#include "ContentStreaming.h"
#include "Engine/AssetManager.h"
#include "Engine/GameViewportClient.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "Misc/App.h"
#include "NavigationSystem.h"
#include "RenderingThread.h"
#include "ShaderCompiler.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Notifications/SProgressBar.h"
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
#include "MoviePlayer.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "SOLog.h"
#include "UObject/Package.h"
#include "UObject/UObjectIterator.h"
#include "Styling/CoreStyle.h"
#include "Widgets/Images/SThrobber.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/Text/STextBlock.h"

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

namespace
{
	/** The travelling screen: where the player is going, on a dark screen, a thin line of progress and what is being
	 *  done under it. The same widget while the map loads (the engine's movie player) and while the area comes up. */
	TSharedRef<SWidget> MakeTravelScreen(const FText& Kind, const FText& Name, TSharedPtr<SProgressBar>* OutBar, TSharedPtr<STextBlock>* OutStep)
	{
		static const FSlateColorBrush Back(FLinearColor(1.0f, 1.0f, 1.0f, 0.09f));
		static const FSlateColorBrush Fill(FLinearColor(0.62f, 0.72f, 1.0f, 1.0f));
		static const FProgressBarStyle BarStyle = FProgressBarStyle().SetBackgroundImage(Back).SetFillImage(Fill).SetMarqueeImage(Fill);
		TSharedPtr<SProgressBar> Bar;
		TSharedPtr<STextBlock> Step;
		TSharedRef<SWidget> Screen = SNew(SBorder)
			.BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush"))
			.BorderBackgroundColor(FLinearColor(0.008f, 0.009f, 0.016f, 1.0f))
			.Padding(FMargin(110.0f, 0.0f, 110.0f, 96.0f))
			.VAlign(VAlign_Bottom)
			[
				SNew(SVerticalBox)
				+ SVerticalBox::Slot().AutoHeight()
				[
					SNew(STextBlock)
					.Text(Kind)
					.Font(FCoreStyle::GetDefaultFontStyle("Regular", 15))
					.ColorAndOpacity(FLinearColor(0.55f, 0.62f, 0.85f, 1.0f))
				]
				+ SVerticalBox::Slot().AutoHeight().Padding(0.0f, 6.0f, 0.0f, 22.0f)
				[
					SNew(STextBlock)
					.Text(Name)
					.Font(FCoreStyle::GetDefaultFontStyle("Bold", 46))
					.ColorAndOpacity(FLinearColor(0.92f, 0.94f, 1.0f, 1.0f))
				]
				+ SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Left)
				[
					SNew(SBox).WidthOverride(520.0f).HeightOverride(3.0f)
					[
						SAssignNew(Bar, SProgressBar).Style(&BarStyle).BorderPadding(FVector2D::ZeroVector).Percent(TOptional<float>())
					]
				]
				+ SVerticalBox::Slot().AutoHeight().Padding(0.0f, 12.0f, 0.0f, 0.0f)
				[
					SAssignNew(Step, STextBlock)
					.Text(NSLOCTEXT("SO", "StepMap", "LOADING THE MAP"))
					.Font(FCoreStyle::GetDefaultFontStyle("Regular", 11))
					.ColorAndOpacity(FLinearColor(0.42f, 0.46f, 0.58f, 1.0f))
				]
			];
		if (OutBar)
		{
			*OutBar = Bar;
		}
		if (OutStep)
		{
			*OutStep = Step;
		}
		return Screen;
	}

	FText KindLine(const FSOArea* Area)
	{
		if (Area && Area->Kind == TEXT("operation"))
		{
			return NSLOCTEXT("SO", "KindOperation", "OPERATION");
		}
		if (Area && Area->Kind == TEXT("city"))
		{
			return NSLOCTEXT("SO", "KindCity", "THE LAST WALL");
		}
		return NSLOCTEXT("SO", "Travelling", "EN ROUTE");
	}
}

bool USOAreaSubsystem::IsArriving(const UObject* WorldContext)
{
	const USOAreaSubsystem* Areas = Get(WorldContext);
	return Areas && Areas->IsArriving();
}

TArray<FSoftObjectPath> USOAreaSubsystem::AssetsFor(const FSOArea* Area) const
{
	TArray<FSoftObjectPath> Out;
	IAssetRegistry& Registry = FModuleManager::LoadModuleChecked<FAssetRegistryModule>(TEXT("AssetRegistry")).Get();
	if (Registry.IsLoadingAssets())
	{
		Registry.ScanPathsSynchronous({ TEXT("/Game") });           // (an uncooked game still reading its content folder)
	}
	TArray<FString> Skip = { TEXT("/Game/Maps/"), TEXT("/Game/Developers/"), TEXT("/Game/Collections/"), TEXT("/Game/Python/") };
	for (const FSOArea& Other : Areas)
	{
		if (&Other != Area)
		{
			for (const FString& Folder : Other.Content)
			{
				Skip.Add(Folder.EndsWith(TEXT("/")) ? Folder : Folder + TEXT("/"));
			}
		}
	}
	TArray<FAssetData> Found;
	Registry.GetAssetsByPath(TEXT("/Game"), Found, true);
	if (Found.Num() == 0)
	{
		Registry.ScanPathsSynchronous({ TEXT("/Game") });           // (the first level of an uncooked game: nothing read yet)
		Registry.GetAssetsByPath(TEXT("/Game"), Found, true);
	}
	for (const FAssetData& Asset : Found)
	{
		const FString Package = Asset.PackageName.ToString();
		if (!Skip.ContainsByPredicate([&](const FString& S) { return Package.StartsWith(S); }))
		{
			Out.Add(Asset.GetSoftObjectPath());
		}
	}
	return Out;
}

void USOAreaSubsystem::BeginArrival(UWorld* World)
{
	const FSOArea* Area = GetCurrent();
	if (!World || !Area || IsRunningCommandlet() || IsRunningDedicatedServer())
	{
		return;
	}
	ArrivalWorld = World;
	ArrivalProgress = 0.0f;
	// everything this area can use, asked for now and held until it is left
	const TArray<FSoftObjectPath> Assets = AssetsFor(Area);
	HeldAssets = Assets.Num() > 0 ? UAssetManager::GetStreamableManager().RequestAsyncLoad(Assets, FStreamableDelegate(), FStreamableManager::AsyncLoadHighPriority) : nullptr;
	UE_LOG(LogShatteredOrbit, Log, TEXT("Area: arriving at %s, loading %d assets"), *Area->Name.ToString(), Assets.Num());
	if (UGameViewportClient* Viewport = FApp::CanEverRender() ? World->GetGameViewport() : nullptr)
	{
		// nothing of the new world is drawn until what it is made of is in
		Viewport->bDisableWorldRendering = true;
		ArrivalScreen = MakeTravelScreen(KindLine(Area), Area->Name.ToUpper(), &ArrivalBar, &ArrivalStep);
		Viewport->AddViewportWidgetContent(ArrivalScreen.ToSharedRef(), 10000);
	}
	SetArrival(EArrival::Loading);
	if (!ArrivalHandle.IsValid())
	{
		ArrivalHandle = FTSTicker::GetCoreTicker().AddTicker(FTickerDelegate::CreateUObject(this, &USOAreaSubsystem::TickArrival), 0.0f);
	}
}

void USOAreaSubsystem::SetArrival(EArrival Phase)
{
	Arrival = Phase;
	PhaseAt = FPlatformTime::Seconds();
	PhaseFrames = 0;
	static const TCHAR* Names[] = { TEXT("done"), TEXT("loading assets"), TEXT("building"), TEXT("warming up"), TEXT("lifting") };
	UE_LOG(LogShatteredOrbit, Log, TEXT("Area: arrival %s"), Names[static_cast<int32>(Phase)]);
}

void USOAreaSubsystem::HoldPlayers(UWorld* World, bool bHold)
{
	for (FConstPlayerControllerIterator It = World->GetPlayerControllerIterator(); It; ++It)
	{
		APlayerController* PC = It->Get();
		if (!PC || !PC->IsLocalController())
		{
			continue;
		}
		if (bHold == PC->InputEnabled())
		{
			bHold ? PC->DisableInput(PC) : PC->EnableInput(PC);
		}
		if (APawn* Pawn = PC->GetPawn(); Pawn && bHold == Pawn->InputEnabled())
		{
			bHold ? Pawn->DisableInput(PC) : Pawn->EnableInput(PC);
		}
	}
}

bool USOAreaSubsystem::TickArrival(float DeltaSeconds)
{
	if (Arrival == EArrival::None)
	{
		return true;
	}
	UWorld* World = ArrivalWorld.Get();
	if (!World)
	{
		EndArrival();
		return true;
	}
	const float In = static_cast<float>(FPlatformTime::Seconds() - PhaseAt);
	++PhaseFrames;
	if (Arrival != EArrival::Lifting)
	{
		HoldPlayers(World, true);
	}
	FText Step;
	switch (Arrival)
	{
	case EArrival::Loading:
	{
		const float Loaded = HeldAssets.IsValid() ? HeldAssets->GetProgress() : 1.0f;
		ArrivalProgress = 0.7f * Loaded;
		Step = FText::Format(NSLOCTEXT("SO", "StepAssets", "LOADING ASSETS  {0}%"), FText::AsNumber(FMath::RoundToInt(Loaded * 100.0f)));
		if ((!HeldAssets.IsValid() || HeldAssets->HasLoadCompleted() || HeldAssets->WasCanceled()) && !IsAsyncLoading() && PhaseFrames > 3)
		{
			// what the place just left let go of late goes now, before anything of this one is drawn
			if (GEngine)
			{
				GEngine->ForceGarbageCollection(true);
			}
			UNavigationSystemV1* Nav = FNavigationSystem::GetCurrent<UNavigationSystemV1>(World);
			NavTasksAtStart = Nav ? FMath::Max(1, Nav->GetNumRemainingBuildTasks()) : 1;
			SetArrival(EArrival::Building);
		}
		break;
	}
	case EArrival::Building:
	{
		UNavigationSystemV1* Nav = FNavigationSystem::GetCurrent<UNavigationSystemV1>(World);
		const int32 Left = Nav && Nav->IsNavigationBuildInProgress() ? FMath::Max(1, Nav->GetNumRemainingBuildTasks()) : 0;
		NavTasksAtStart = FMath::Max(NavTasksAtStart, Left);
		ArrivalProgress = 0.7f + 0.15f * (1.0f - static_cast<float>(Left) / NavTasksAtStart);
		Step = NSLOCTEXT("SO", "StepBuild", "RAISING THE GROUND");
		bool bPawn = false;
		for (FConstPlayerControllerIterator It = World->GetPlayerControllerIterator(); It; ++It)
		{
			bPawn |= It->IsValid() && It->Get()->GetPawn() != nullptr;
		}
		if ((Left == 0 && In > 0.5f && (bPawn || In > 6.0f)) || In > 45.0f)
		{
			if (UGameViewportClient* Viewport = World->GetGameViewport(); Viewport && ArrivalScreen.IsValid())
			{
				FlushRenderingCommands();
				Viewport->bDisableWorldRendering = false;       // drawn behind the screen from here: shaders, textures, shadows
			}
			SetArrival(ArrivalScreen.IsValid() ? EArrival::Warming : EArrival::Lifting);
		}
		break;
	}
	case EArrival::Warming:
	{
		const bool bShaders = GShaderCompilingManager && GShaderCompilingManager->IsCompiling();
		const bool bTextures = IStreamingManager::Get().GetNumWantingResources() > 0;
		ArrivalProgress = 0.85f + 0.15f * FMath::Clamp(In / 2.0f, 0.0f, bShaders || bTextures ? 0.9f : 1.0f);
		Step = bShaders ? NSLOCTEXT("SO", "StepShaders", "COMPILING SHADERS") : NSLOCTEXT("SO", "StepWarm", "FIRST LIGHT");
		if ((PhaseFrames >= 45 && In >= 1.5f && !bShaders && !bTextures) || In > 25.0f)
		{
			SetArrival(EArrival::Lifting);
		}
		break;
	}
	case EArrival::Lifting:
	{
		ArrivalProgress = 1.0f;
		HoldPlayers(World, false);
		const float Fade = 0.45f;
		if (ArrivalScreen.IsValid())
		{
			ArrivalScreen->SetRenderOpacity(FMath::Clamp(1.0f - In / Fade, 0.0f, 1.0f));
		}
		if (In >= Fade || !ArrivalScreen.IsValid())
		{
			EndArrival();
		}
		return true;
	}
	default:
		break;
	}
	if (ArrivalBar.IsValid())
	{
		ArrivalBar->SetPercent(ArrivalProgress);
	}
	if (ArrivalStep.IsValid() && !Step.IsEmpty())
	{
		ArrivalStep->SetText(Step);
	}
	return true;
}

void USOAreaSubsystem::EndArrival()
{
	UWorld* World = ArrivalWorld.Get();
	if (World)
	{
		HoldPlayers(World, false);
		if (UGameViewportClient* Viewport = World->GetGameViewport())
		{
			Viewport->bDisableWorldRendering = false;
			if (ArrivalScreen.IsValid())
			{
				Viewport->RemoveViewportWidgetContent(ArrivalScreen.ToSharedRef());
			}
		}
	}
	ArrivalScreen.Reset();
	ArrivalBar.Reset();
	ArrivalStep.Reset();
	ArrivalWorld.Reset();
	if (Arrival != EArrival::None)
	{
		Arrival = EArrival::None;
		UE_LOG(LogShatteredOrbit, Log, TEXT("Area: arrival done"));
	}
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
	FTSTicker::GetCoreTicker().RemoveTicker(ArrivalHandle);
	EndArrival();
	HeldAssets.Reset();
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
	// What the player looks at while the old area is torn down and the new one is built: where they are going, on a
	// dark screen, until the map is in (the engine plays it when the load begins and takes it down when it ends).
	if (IsMoviePlayerEnabled() && !IsRunningDedicatedServer())
	{
		FLoadingScreenAttributes Screen;
		Screen.bAutoCompleteWhenLoadingCompletes = true;
		Screen.MinimumLoadingScreenDisplayTime = 0.5f;
		Screen.WidgetLoadingScreen = MakeTravelScreen(KindLine(Area), Area->Name.ToUpper(), nullptr, nullptr);
		GetMoviePlayer()->SetupLoadingScreen(Screen);
	}
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
	// what was held for the area being left goes with it
	EndArrival();
	if (HeldAssets.IsValid())
	{
		HeldAssets->ReleaseHandle();
		HeldAssets.Reset();
	}
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
	BeginArrival(World);
}

bool USOAreaSubsystem::Settle(float DeltaSeconds)
{
	if (!bSettling || FPlatformTime::Seconds() < SettleAt || IsArriving())
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
