#include "SOInventoryWidget.h"

#include "Blueprint/WidgetTree.h"
#include "Brushes/SlateColorBrush.h"
#include "Brushes/SlateRoundedBoxBrush.h"
#include "Components/BackgroundBlur.h"
#include "Components/Border.h"
#include "Components/Button.h"
#include "Components/ButtonSlot.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/HorizontalBox.h"
#include "Components/HorizontalBoxSlot.h"
#include "Components/Image.h"
#include "Components/Overlay.h"
#include "Components/OverlaySlot.h"
#include "Components/ProgressBar.h"
#include "Components/ScrollBox.h"
#include "Components/SizeBox.h"
#include "Components/Spacer.h"
#include "Components/TextBlock.h"
#include "Components/VerticalBox.h"
#include "Components/VerticalBoxSlot.h"
#include "Components/WrapBox.h"
#include "Components/WrapBoxSlot.h"
#include "Components/PointLightComponent.h"
#include "Components/SceneCaptureComponent2D.h"
#include "Engine/PointLight.h"
#include "Engine/SceneCapture2D.h"
#include "Engine/Texture2D.h"
#include "Engine/TextureRenderTarget2D.h"
#include "Engine/World.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "SOInventoryComponent.h"
#include "SOLootLibrary.h"
#include "SOSound.h"
#include "SOWardrobe.h"
#include "SOWeaponData.h"
#include "SOCharacter.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Styling/CoreStyle.h"
#include "HAL/IConsoleManager.h"
#include "Materials/MaterialInstanceDynamic.h"

// The look follows the owner's world art: night-blue gunmetal glass, cyan light lines, violet crystal glow, gold.
namespace
{
	const FLinearColor Ink(0.88f, 0.92f, 0.97f);
	const FLinearColor Dim(0.48f, 0.54f, 0.64f);
	const FLinearColor Cyan(0.1f, 0.85f, 1.0f);
	const FLinearColor Violet(0.55f, 0.36f, 1.0f);
	const FLinearColor Gold(0.95f, 0.72f, 0.32f);
	const FLinearColor Glass(0.03f, 0.045f, 0.075f, 0.9f);
	const FLinearColor TileFill(0.05f, 0.07f, 0.11f, 0.94f);
	const FLinearColor Good(0.45f, 0.95f, 0.55f);
	const FLinearColor Bad(1.0f, 0.42f, 0.35f);

	FSlateFontInfo Font(int32 Size, bool bBold = false, int32 Spacing = 0)
	{
		FSlateFontInfo F = FCoreStyle::GetDefaultFontStyle(bBold ? "Bold" : "Regular", Size);
		F.LetterSpacing = Spacing;
		return F;
	}

	template <typename T>
	T* Make(UWidgetTree* Tree)
	{
		return Tree->ConstructWidget<T>(T::StaticClass());
	}

	UTextBlock* Text(UWidgetTree* Tree, const FString& Value, int32 Size, const FLinearColor& Color, bool bBold = false, int32 Spacing = 0)
	{
		UTextBlock* T = Make<UTextBlock>(Tree);
		T->SetText(FText::FromString(Value));
		T->SetFont(Font(Size, bBold, Spacing));
		T->SetColorAndOpacity(FSlateColor(Color));
		return T;
	}

	FSlateRoundedBoxBrush Rounded(const FLinearColor& Fill, const FLinearColor& Outline = FLinearColor::Transparent, float Width = 0.0f, float Radius = 3.0f)
	{
		return FSlateRoundedBoxBrush(Fill, Radius, Outline, Width);
	}

	UBorder* Box(UWidgetTree* Tree, const FSlateBrush& Brush, const FMargin& Padding)
	{
		UBorder* B = Make<UBorder>(Tree);
		B->SetBrush(Brush);
		B->SetPadding(Padding);
		return B;
	}

	USizeBox* Sized(UWidgetTree* Tree, UWidget* Content, float W, float H)
	{
		USizeBox* S = Make<USizeBox>(Tree);
		if (W > 0.0f) S->SetWidthOverride(W);
		if (H > 0.0f) S->SetHeightOverride(H);
		S->SetContent(Content);
		return S;
	}

	void StyleButton(UButton* Button, const FSlateBrush& Normal, const FSlateBrush& Hover, const FSlateBrush& Pressed)
	{
		FButtonStyle Style = Button->GetStyle();
		Style.SetNormal(Normal);
		Style.SetHovered(Hover);
		Style.SetPressed(Pressed);
		Style.SetDisabled(Normal);
		Style.SetNormalPadding(FMargin(0));
		Style.SetPressedPadding(FMargin(0));
		Button->SetStyle(Style);
	}

	FLinearColor Alpha(const FLinearColor& C, float A)
	{
		return FLinearColor(C.R, C.G, C.B, A);
	}

	/** The game's panel (M_UI_Plate): a rectangle with two cut corners, a hairline, a fill that deepens downwards, an
	 *  accent bar on the left and / or along the bottom, a wash of the accent rising from the bottom. */
	struct FPlate
	{
		FLinearColor Fill = FLinearColor(0.035f, 0.045f, 0.07f, 0.92f);
		FLinearColor FillLow = FLinearColor(0.02f, 0.026f, 0.045f, 0.94f);
		FLinearColor Edge = FLinearColor(1.0f, 1.0f, 1.0f, 0.13f);
		FLinearColor Accent = FLinearColor(0.0f, 0.0f, 0.0f, 0.0f);
		float Cut = 12.0f;
		float EdgeWidth = 1.0f;
		float AccentLeft = 0.0f;
		float AccentBottom = 0.0f;
		float Wash = 0.0f;
		float Hatch = 0.0f;
		float TopLight = 0.0f;
	};

	FSlateBrush PlateBrush(UObject* Outer, const FPlate& P)
	{
		UMaterialInterface* Base = Cast<UMaterialInterface>(FSoftObjectPath(TEXT("/Game/UI/M_UI_Plate.M_UI_Plate")).TryLoad());
		UMaterialInstanceDynamic* MID = Base ? UMaterialInstanceDynamic::Create(Base, Outer) : nullptr;
		if (!MID)
		{
			return FSlateRoundedBoxBrush(P.Fill, 3.0f, P.Edge, P.EdgeWidth);
		}
		MID->SetVectorParameterValue(TEXT("Fill"), P.Fill);
		MID->SetVectorParameterValue(TEXT("FillLow"), P.FillLow);
		MID->SetVectorParameterValue(TEXT("Edge"), P.Edge);
		MID->SetVectorParameterValue(TEXT("Accent"), P.Accent);
		MID->SetVectorParameterValue(TEXT("Shape"), FLinearColor(P.Cut, P.EdgeWidth, P.AccentLeft, P.AccentBottom));
		MID->SetVectorParameterValue(TEXT("Look"), FLinearColor(P.Wash, P.Hatch, P.TopLight, 0.0f));
		FSlateBrush Brush;
		Brush.SetResourceObject(MID);
		Brush.DrawAs = ESlateBrushDrawType::Image;
		Brush.ImageSize = FVector2D(32.0f, 32.0f);
		Brush.TintColor = FSlateColor(FLinearColor::White);
		return Brush;
	}

	/** A section header: a short bar of light, the title, a hairline to the edge. */
	UWidget* Header(UWidgetTree* T, const FString& Title)
	{
		UHorizontalBox* Row = Make<UHorizontalBox>(T);
		Row->AddChildToHorizontalBox(Sized(T, Box(T, FSlateColorBrush(Cyan), FMargin(0)), 3.0f, 12.0f))->SetVerticalAlignment(VAlign_Center);
		Row->AddChildToHorizontalBox(Text(T, Title, 11, Ink, true, 300))->SetPadding(FMargin(9, 0, 12, 0));
		UHorizontalBoxSlot* Line = Row->AddChildToHorizontalBox(Sized(T, Box(T, FSlateColorBrush(FLinearColor(1.0f, 1.0f, 1.0f, 0.1f)), FMargin(0)), 0.0f, 1.0f));
		Line->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
		Line->SetVerticalAlignment(VAlign_Center);
		return Row;
	}

	/** A small filled tag (the rarity's name on its own colour). */
	UWidget* Chip(UWidgetTree* T, const FString& Label, const FLinearColor& Color)
	{
		UBorder* C = Box(T, FSlateRoundedBoxBrush(Alpha(Color, 1.0f), 2.0f), FMargin(7, 2, 7, 2));
		C->SetContent(Text(T, Label, 9, FLinearColor(0.02f, 0.025f, 0.04f), true, 160));
		return C;
	}

	/** A key cap and what the key does. */
	UWidget* Hint(UWidgetTree* T, const FString& Key, const FString& Label)
	{
		UHorizontalBox* Row = Make<UHorizontalBox>(T);
		UBorder* Cap = Box(T, FSlateRoundedBoxBrush(FLinearColor(1.0f, 1.0f, 1.0f, 0.05f), 3.0f, FLinearColor(1.0f, 1.0f, 1.0f, 0.3f), 1.0f), FMargin(7, 1, 7, 2));
		Cap->SetContent(Text(T, Key, 10, Ink, true));
		Row->AddChildToHorizontalBox(Cap)->SetVerticalAlignment(VAlign_Center);
		UHorizontalBoxSlot* L = Row->AddChildToHorizontalBox(Text(T, Label, 10, Dim, false, 60));
		L->SetVerticalAlignment(VAlign_Center);
		L->SetPadding(FMargin(8, 0, 26, 0));
		return Row;
	}

	/** A number under its label (the top bar's figures). */
	UWidget* Figure(UWidgetTree* T, const FString& Label, const FString& Value, const FLinearColor& Color, int32 Size = 16)
	{
		UVerticalBox* Box = Make<UVerticalBox>(T);
		Box->AddChildToVerticalBox(Text(T, Label, 9, Dim, true, 240));
		Box->AddChildToVerticalBox(Text(T, Value, Size, Color, true));
		return Box;
	}

	/** A thin flat bar (stats). */
	void FlatBar(UProgressBar* Bar)
	{
		FProgressBarStyle Style;
		Style.SetBackgroundImage(FSlateColorBrush(FLinearColor(1.0f, 1.0f, 1.0f, 0.09f)));
		Style.SetFillImage(FSlateColorBrush(FLinearColor::White));
		Style.SetMarqueeImage(FSlateColorBrush(FLinearColor::Transparent));
		Bar->SetWidgetStyle(Style);
	}

	const USOWeaponData* ArchetypeOf(const FSOWeaponInstance& W)
	{
		const USOLootTables* Tables = USOLootLibrary::GetTables();
		return Tables ? Tables->LoadArchetype(W.Archetype) : nullptr;
	}

	FString ClassName(const USOWeaponData* Data)
	{
		if (!Data) return FString();
		switch (Data->WeaponClass)
		{
		case ESOWeaponClass::Kinetic: return TEXT("Kinetic");
		case ESOWeaponClass::Horror: return TEXT("Living");
		default: return TEXT("Energy");
		}
	}

	FLinearColor RarityColor(int32 Rarity)
	{
		const USOLootTables* Tables = USOLootLibrary::GetTables();
		return Tables ? Tables->GetRarity(Rarity).Color : FLinearColor::White;
	}

	FString RarityName(int32 Rarity)
	{
		const USOLootTables* Tables = USOLootLibrary::GetTables();
		return Tables ? Tables->GetRarity(Rarity).Name.ToString() : FString();
	}
}

// --- Character preview -----------------------------------------------------------------------------

void USOCharacterPreview::Start(APlayerController* Player)
{
	UWorld* World = Player ? Player->GetWorld() : nullptr;
	if (!World)
	{
		return;
	}
	// the stand-in: a character of the player's class far above the range, still (no movement, no gravity)
	TSubclassOf<ASOCharacter> Class = ASOCharacter::StaticClass();
	if (const APawn* Own = Player->GetPawn(); Own && Own->IsA<ASOCharacter>())
	{
		Class = Own->GetClass();
	}
	FActorSpawnParameters Spawn;
	Spawn.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	Spawn.ObjectFlags |= RF_Transient;
	ASOCharacter* Pawn = World->SpawnActor<ASOCharacter>(Class, FVector(0.0f, 0.0f, 100000.0f), FRotator::ZeroRotator, Spawn);
	if (!Pawn)
	{
		return;
	}
	Pawn->SetReplicates(false);
	if (UCharacterMovementComponent* Move = Pawn->GetCharacterMovement())
	{
		Move->GravityScale = 0.0f;
		Move->DisableMovement();
	}
	Pawn->SetViewMode(ESOViewMode::ThirdPerson);
	Pawn->GetMesh()->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
	Subject = Pawn;
	// alpha through post-processing: what the capture does not draw stays transparent over the screen
	if (IConsoleVariable* Alpha = IConsoleManager::Get().FindConsoleVariable(TEXT("r.PostProcessing.PropagateAlpha")))
	{
		PreviousAlpha = Alpha->GetInt();
		Alpha->Set(1, ECVF_SetByCode);
	}
	Target = NewObject<UTextureRenderTarget2D>(this);
	Target->ClearColor = FLinearColor(0.0f, 0.0f, 0.0f, 1.0f);
	Target->RenderTargetFormat = ETextureRenderTargetFormat::RTF_RGBA8_SRGB;
	Target->InitAutoFormat(900, 1200);
	Target->UpdateResourceImmediate(true);

	FActorSpawnParameters Params;
	Params.ObjectFlags |= RF_Transient;
	ASceneCapture2D* Cam = World->SpawnActor<ASceneCapture2D>(Params);
	USceneCaptureComponent2D* C = Cam->GetCaptureComponent2D();
	C->TextureTarget = Target;
	C->CaptureSource = ESceneCaptureSource::SCS_FinalColorLDR;
	C->PrimitiveRenderMode = ESceneCapturePrimitiveRenderMode::PRM_UseShowOnlyList;
	C->bCaptureEveryFrame = true;
	C->bConsiderUnrenderedOpaquePixelAsFullyTranslucent = true;
	C->bCaptureOnMovement = false;
	C->FOVAngle = 26.0f;
	C->ShowFlags.SetAtmosphere(false);
	C->ShowFlags.SetFog(false);
	C->ShowFlags.SetVolumetricFog(false);
	C->ShowFlags.SetMotionBlur(false);
	C->ShowFlags.SetCloud(false);
	C->PostProcessSettings.bOverride_AutoExposureMinBrightness = true;
	C->PostProcessSettings.bOverride_AutoExposureMaxBrightness = true;
	C->PostProcessSettings.AutoExposureMinBrightness = 1.0f;
	C->PostProcessSettings.AutoExposureMaxBrightness = 1.0f;
	C->PostProcessSettings.bOverride_BloomIntensity = true;
	C->PostProcessSettings.BloomIntensity = 0.6f;
	Capture = Cam;
	UpdateShowList();

	auto Light = [&](float Intensity, const FLinearColor& Color) -> APointLight*
	{
		APointLight* L = World->SpawnActor<APointLight>(Params);
		UPointLightComponent* P = Cast<UPointLightComponent>(L->GetLightComponent());
		P->SetMobility(EComponentMobility::Movable);
		P->SetIntensityUnits(ELightUnits::Candelas);
		P->SetIntensity(Intensity);
		P->SetLightColor(Color);
		P->SetAttenuationRadius(700.0f);
		P->SetSourceRadius(60.0f);
		P->SetCastShadows(false);
		return L;
	};
	Key = Light(160.0f, FLinearColor(1.0f, 0.95f, 0.9f));
	Rim = Light(220.0f, FLinearColor(0.35f, 0.7f, 1.0f));
	Tick(0.0f);
}

void USOCharacterPreview::UpdateShowList()
{
	ASceneCapture2D* Cam = Capture.Get();
	APawn* Pawn = Subject.Get();
	if (!Cam || !Pawn)
	{
		return;
	}
	USceneCaptureComponent2D* C = Cam->GetCaptureComponent2D();
	C->ShowOnlyActors.Reset();
	C->ShowOnlyActors.Add(Pawn);
	TArray<AActor*> Attached;
	Pawn->GetAttachedActors(Attached, true, true);
	C->ShowOnlyActors.Append(Attached);
}

void USOCharacterPreview::Sync(USOInventoryComponent* Inventory)
{
	ASOCharacter* Pawn = Cast<ASOCharacter>(Subject.Get());
	if (!Pawn || !Inventory)
	{
		return;
	}
	Pawn->SetOutfit(Inventory->GetOutfit());
	const FSOWeaponInstance* Held = Inventory->GetEquipped(Inventory->GetActiveSlot());
	const FString Want = Held ? Held->Uid + Held->Sight.ToString() + FString::FromInt(Held->Rarity) : FString();
	if (Held && Want != ShownWeapon)
	{
		ShownWeapon = Want;
		Pawn->EquipInstance(*Held);
	}
	UpdateShowList();
}

void USOCharacterPreview::Stop()
{
	for (AActor* A : { (AActor*)Capture.Get(), (AActor*)Key.Get(), (AActor*)Rim.Get(), (AActor*)Subject.Get() })
	{
		if (A)
		{
			A->Destroy();
		}
	}
	Capture = nullptr;
	Key = nullptr;
	Rim = nullptr;
	if (IConsoleVariable* Alpha = IConsoleManager::Get().FindConsoleVariable(TEXT("r.PostProcessing.PropagateAlpha")); Alpha && PreviousAlpha >= 0)
	{
		Alpha->Set(PreviousAlpha, ECVF_SetByCode);
		PreviousAlpha = -1;
	}
}

void USOCharacterPreview::Tick(float DeltaTime)
{
	APawn* Pawn = Subject.Get();
	ASceneCapture2D* Cam = Capture.Get();
	if (!Pawn || !Cam)
	{
		return;
	}
	const FVector Center = Pawn->GetActorLocation() + FVector(0.0f, 0.0f, 8.0f);
	const FRotator Facing(0.0f, Pawn->GetActorRotation().Yaw + Yaw, 0.0f);
	const FVector Dir = Facing.Vector();                        // from the character towards the camera
	const FVector Eye = Center + Dir * 430.0f + FVector(0.0f, 0.0f, 20.0f);
	Cam->SetActorLocationAndRotation(Eye, (Center + FVector(0.0f, 0.0f, 4.0f) - Eye).Rotation());
	const FVector Right = FRotationMatrix(Facing).GetUnitAxis(EAxis::Y);
	if (APointLight* K = Key.Get())
	{
		K->SetActorLocation(Center + Dir * 220.0f + Right * 160.0f + FVector(0, 0, 120.0f));
	}
	if (APointLight* R = Rim.Get())
	{
		R->SetActorLocation(Center - Dir * 200.0f - Right * 120.0f + FVector(0, 0, 90.0f));
	}
}

// --- Tile --------------------------------------------------------------------------------------------

TSharedRef<SWidget> USOInventoryTile::RebuildWidget()
{
	if (WidgetTree && !WidgetTree->RootWidget)
	{
		UWidgetTree* T = WidgetTree;
		const bool bSlot = Info.Kind == TEXT("wslot") || Info.Kind == TEXT("aslot");
		const FLinearColor Rarity = Alpha(Info.Rarity, 1.0f);
		UButton* Button = Make<UButton>(T);
		// the plate: a slot card carries its rarity as a bar down its left edge, an owned item as a bar along its foot
		// and a wash rising behind the picture; the one that is open / selected is framed in light
		FPlate Plate;
		Plate.Cut = bSlot ? 14.0f : 10.0f;
		Plate.Accent = Info.Icon ? Rarity : Alpha(Dim, 0.5f);
		Plate.AccentLeft = bSlot ? 4.0f : 0.0f;
		Plate.AccentBottom = bSlot ? 0.0f : 3.0f;
		Plate.Wash = Info.Icon ? (bSlot ? 0.2f : 0.55f) : 0.0f;
		Plate.Hatch = bSlot ? 1.0f : 0.0f;
		Plate.Edge = Info.bActive ? Cyan : FLinearColor(1.0f, 1.0f, 1.0f, 0.13f);
		Plate.EdgeWidth = Info.bActive ? 2.0f : 1.0f;
		FPlate Hover = Plate;
		Hover.Fill = FLinearColor(0.07f, 0.09f, 0.14f, 0.96f);
		Hover.Edge = Cyan;
		Hover.EdgeWidth = FMath::Max(Plate.EdgeWidth, 1.5f);
		Hover.TopLight = 1.0f;
		Hover.Wash = Plate.Wash + 0.15f;
		FPlate Down = Hover;
		Down.Fill = FLinearColor(0.1f, 0.13f, 0.2f, 1.0f);
		Down.EdgeWidth = 2.5f;
		StyleButton(Button, PlateBrush(this, Plate), PlateBrush(this, Hover), PlateBrush(this, Down));
		Button->OnClicked.AddDynamic(this, &USOInventoryTile::OnClicked);
		Button->OnHovered.AddDynamic(this, &USOInventoryTile::OnHovered);
		Button->OnUnhovered.AddDynamic(this, &USOInventoryTile::OnUnhovered);

		// the picture, with power in the corner and the NEW / equipped / locked mark on an owned item
		const FVector2D IconSize = bSlot ? (Info.bWide ? FVector2D(176.0f, 88.0f) : FVector2D(84.0f, 84.0f)) : Info.Size;
		UOverlay* Square = Make<UOverlay>(T);
		if (Info.Icon)
		{
			UImage* Icon = Make<UImage>(T);
			Icon->SetBrushFromTexture(Info.Icon, false);
			UOverlaySlot* IconSlot = Square->AddChildToOverlay(Icon);
			IconSlot->SetHorizontalAlignment(HAlign_Fill);
			IconSlot->SetVerticalAlignment(VAlign_Fill);
			IconSlot->SetPadding(FMargin(bSlot ? 0.0f : 5.0f));
		}
		else
		{
			UOverlaySlot* Empty = Square->AddChildToOverlay(Text(T, TEXT("EMPTY"), 9, Alpha(Dim, 0.7f), true, 300));
			Empty->SetHorizontalAlignment(HAlign_Center);
			Empty->SetVerticalAlignment(VAlign_Center);
		}
		if (!bSlot)
		{
			if (Info.Power > 0)
			{
				UOverlaySlot* P = Square->AddChildToOverlay(Text(T, FString::FromInt(Info.Power), 11, Ink, true));
				P->SetHorizontalAlignment(HAlign_Right);
				P->SetVerticalAlignment(VAlign_Top);
				P->SetPadding(FMargin(0, 4, 14, 0));          // (clear of the cut corner)
			}
			if (Info.bNew || Info.bEquipped || !Info.Badge.IsEmpty())
			{
				const FString Mark = Info.bEquipped ? TEXT("IN USE") : (Info.bNew ? TEXT("NEW") : Info.Badge);
				UOverlaySlot* M = Square->AddChildToOverlay(Text(T, Mark, 8, Info.bEquipped ? Cyan : Gold, true, 160));
				M->SetHorizontalAlignment(HAlign_Left);
				M->SetVerticalAlignment(VAlign_Top);
				M->SetPadding(FMargin(7, 5, 0, 0));
			}
		}
		UWidget* Content = Sized(T, Square, IconSize.X, IconSize.Y);
		if (bSlot)
		{
			// a slot card: the picture, then which slot it is, what is in it and what kind of thing that is, its power
			// at the far end
			UHorizontalBox* Row = Make<UHorizontalBox>(T);
			UHorizontalBoxSlot* Pic = Row->AddChildToHorizontalBox(Content);
			Pic->SetPadding(FMargin(14, 8, 2, 8));
			Pic->SetVerticalAlignment(VAlign_Center);
			UVerticalBox* Lines = Make<UVerticalBox>(T);
			Lines->AddChildToVerticalBox(Text(T, Info.Sub, 9, Dim, true, 220));
			UTextBlock* Name = Text(T, Info.Title, 14, Info.Icon ? Ink : Dim, true);
			Name->SetAutoWrapText(true);
			Lines->AddChildToVerticalBox(Name)->SetPadding(FMargin(0, 3, 0, 3));
			if (!Info.Tag.IsEmpty())
			{
				UTextBlock* Tag = Text(T, Info.Tag, 9, Rarity, true, 120);
				Tag->SetAutoWrapText(true);
				Lines->AddChildToVerticalBox(Tag);
			}
			UHorizontalBoxSlot* LinesSlot = Row->AddChildToHorizontalBox(Lines);
			LinesSlot->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
			LinesSlot->SetVerticalAlignment(VAlign_Center);
			LinesSlot->SetPadding(FMargin(10, 6, 6, 6));
			if (Info.Power > 0)
			{
				UVerticalBox* Power = Make<UVerticalBox>(T);
				Power->AddChildToVerticalBox(Text(T, FString::FromInt(Info.Power), 22, Gold, true))->SetHorizontalAlignment(HAlign_Right);
				Power->AddChildToVerticalBox(Text(T, TEXT("POWER"), 8, Dim, true, 240))->SetHorizontalAlignment(HAlign_Right);
				UHorizontalBoxSlot* PowerSlot = Row->AddChildToHorizontalBox(Power);
				PowerSlot->SetVerticalAlignment(VAlign_Center);
				PowerSlot->SetPadding(FMargin(0, 0, 18, 0));
			}
			Content = Row;
		}
		if (UButtonSlot* Fill = Cast<UButtonSlot>(Button->SetContent(Content)))
		{
			Fill->SetHorizontalAlignment(HAlign_Fill);
			Fill->SetVerticalAlignment(VAlign_Fill);
			Fill->SetPadding(FMargin(1));
		}
		WidgetTree->RootWidget = Button;
	}
	return Super::RebuildWidget();
}

void USOInventoryTile::OnClicked()
{
	if (Screen)
	{
		Screen->OnTile(Info);
	}
}

void USOInventoryTile::OnHovered()
{
	if (Screen)
	{
		Screen->OnTileHover(Info, true);
	}
}

void USOInventoryTile::OnUnhovered()
{
	if (Screen)
	{
		Screen->OnTileHover(Info, false);
	}
}

// --- Screen ------------------------------------------------------------------------------------------

TSharedRef<SWidget> USOInventoryWidget::RebuildWidget()
{
	if (WidgetTree && !WidgetTree->RootWidget)
	{
		BuildTree();
	}
	return Super::RebuildWidget();
}

void USOInventoryWidget::NativeConstruct()
{
	Super::NativeConstruct();
	if (!Preview)
	{
		Preview = NewObject<USOCharacterPreview>(this);
	}
	if (APlayerController* Player = GetOwningPlayer())
	{
		Preview->Start(Player);
		Preview->Sync(Inventory);
		if (PreviewImage && Preview->GetTarget())
		{
			// the capture's alpha is inverse opacity: M_UI_Stage turns it round so only the character draws
			UMaterialInterface* Stage = Cast<UMaterialInterface>(FSoftObjectPath(TEXT("/Game/UI/M_UI_Stage.M_UI_Stage")).TryLoad());
			if (UMaterialInstanceDynamic* MID = Stage ? UMaterialInstanceDynamic::Create(Stage, this) : nullptr)
			{
				MID->SetTextureParameterValue(TEXT("Stage"), Preview->GetTarget());
				PreviewImage->SetBrushFromMaterial(MID);
			}
			else
			{
				PreviewImage->SetBrushResourceObject(Preview->GetTarget());
			}
		}
	}
}

void USOInventoryWidget::NativeDestruct()
{
	if (Preview)
	{
		Preview->Stop();
	}
	if (Inventory && ChangedHandle.IsValid())
	{
		Inventory->OnChanged.Remove(ChangedHandle);
	}
	Super::NativeDestruct();
}

void USOInventoryWidget::NativeTick(const FGeometry& MyGeometry, float InDeltaTime)
{
	Super::NativeTick(MyGeometry, InDeltaTime);
	if (Preview)
	{
		Preview->Tick(InDeltaTime);
	}
	// the character steps into the gap between an open bay and the details (and back to the middle)
	if (StageSlot && !FMath::IsNearlyEqual(StageShift, StageShiftTarget, 0.25f))
	{
		StageShift = FMath::FInterpTo(StageShift, StageShiftTarget, FMath::Min(InDeltaTime, 0.05f), 10.0f);
		StageSlot->SetOffsets(FMargin(-330.0f + StageShift, 96.0f, 660.0f, 60.0f));
		if (OrbitSlot)
		{
			OrbitSlot->SetOffsets(FMargin(-700.0f + StageShift, 0.0f, 1400.0f, 0.0f));
		}
	}
}

void USOInventoryWidget::BuildTree()
{
	UWidgetTree* T = WidgetTree;
	Root = Make<UCanvasPanel>(T);
	WidgetTree->RootWidget = Root;
	SetIsFocusable(true);

	// the world behind, blurred and sunk into night blue
	UBackgroundBlur* Blur = Make<UBackgroundBlur>(T);
	Blur->SetBlurStrength(14.0f);
	Blur->SetContent(Box(T, FSlateColorBrush(FLinearColor(0.008f, 0.011f, 0.026f, 0.86f)), FMargin(0)));
	UCanvasPanelSlot* BlurSlot = Root->AddChildToCanvas(Blur);
	BlurSlot->SetAnchors(FAnchors(0, 0, 1, 1));
	BlurSlot->SetOffsets(FMargin(0));

	// the broken orbit, turning slowly behind the character (it goes where the character goes)
	UImage* Orbit = Make<UImage>(T);
	if (UMaterialInterface* Rings = Cast<UMaterialInterface>(FSoftObjectPath(TEXT("/Game/UI/M_UI_Orbit.M_UI_Orbit")).TryLoad()))
	{
		Orbit->SetBrushFromMaterial(Rings);
		Orbit->SetVisibility(ESlateVisibility::HitTestInvisible);
	}
	else
	{
		Orbit->SetVisibility(ESlateVisibility::Collapsed);
	}
	OrbitSlot = Root->AddChildToCanvas(Orbit);
	OrbitSlot->SetAnchors(FAnchors(0.5f, 0.0f, 0.5f, 1.0f));
	OrbitSlot->SetOffsets(FMargin(-700.0f, 0.0f, 1400.0f, 0.0f));

	// the character, centre stage
	UOverlay* Stage = Make<UOverlay>(T);
	PreviewImage = Make<UImage>(T);
	PreviewImage->SetColorAndOpacity(FLinearColor::White);
	UOverlaySlot* ImageSlot = Stage->AddChildToOverlay(PreviewImage);
	ImageSlot->SetHorizontalAlignment(HAlign_Fill);
	ImageSlot->SetVerticalAlignment(VAlign_Fill);
	UVerticalBox* Under = Make<UVerticalBox>(T);
	UButton* BodyButton = Make<UButton>(T);
	FPlate BodyPlate;
	BodyPlate.Cut = 8.0f;
	BodyPlate.Edge = Alpha(Cyan, 0.4f);
	FPlate BodyHover = BodyPlate;
	BodyHover.Edge = Cyan;
	BodyHover.EdgeWidth = 1.5f;
	BodyHover.TopLight = 1.0f;
	StyleButton(BodyButton, PlateBrush(this, BodyPlate), PlateBrush(this, BodyHover), PlateBrush(this, BodyHover));
	BodyLabel = Text(T, TEXT("BODY"), 10, Ink, true, 240);
	BodyButton->SetContent(Box(T, FSlateColorBrush(FLinearColor::Transparent), FMargin(18, 6, 18, 6)));
	Cast<UBorder>(BodyButton->GetContent())->SetContent(BodyLabel);
	BodyButton->OnClicked.AddDynamic(this, &USOInventoryWidget::OnBody);
	Under->AddChildToVerticalBox(BodyButton)->SetHorizontalAlignment(HAlign_Center);
	UOverlaySlot* UnderSlot = Stage->AddChildToOverlay(Under);
	UnderSlot->SetHorizontalAlignment(HAlign_Center);
	UnderSlot->SetVerticalAlignment(VAlign_Bottom);
	StageSlot = Root->AddChildToCanvas(Stage);
	StageSlot->SetAnchors(FAnchors(0.5f, 0.0f, 0.5f, 1.0f));
	StageSlot->SetOffsets(FMargin(-330.0f, 96.0f, 660.0f, 60.0f));

	// top bar: what this is, the figures, power on its own plate
	UHorizontalBox* Top = Make<UHorizontalBox>(T);
	UVerticalBox* Title = Make<UVerticalBox>(T);
	Title->AddChildToVerticalBox(Text(T, TEXT("LOADOUT"), 30, Ink, true, 460));
	Title->AddChildToVerticalBox(Text(T, TEXT("WAYFARER  ·  SHATTERED ORBIT"), 9, Cyan, true, 340));
	Top->AddChildToHorizontalBox(Title);
	UHorizontalBoxSlot* Spacer = Top->AddChildToHorizontalBox(Make<USpacer>(T));
	Spacer->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
	StatsRow = Make<UHorizontalBox>(T);
	Top->AddChildToHorizontalBox(StatsRow)->SetVerticalAlignment(VAlign_Center);
	FPlate PowerPlate;
	PowerPlate.Cut = 12.0f;
	PowerPlate.Edge = Alpha(Gold, 0.55f);
	PowerPlate.Accent = Gold;
	PowerPlate.AccentLeft = 3.0f;
	PowerPlate.Wash = 0.16f;
	UBorder* PowerBox = Box(T, PlateBrush(this, PowerPlate), FMargin(18, 5, 22, 5));
	UVerticalBox* PowerLines = Make<UVerticalBox>(T);
	PowerLines->AddChildToVerticalBox(Text(T, TEXT("POWER"), 8, Gold, true, 320));
	PowerText = Text(T, TEXT("0"), 30, Gold, true);
	PowerLines->AddChildToVerticalBox(PowerText);
	PowerBox->SetContent(PowerLines);
	UHorizontalBoxSlot* PowerSlot = Top->AddChildToHorizontalBox(PowerBox);
	PowerSlot->SetVerticalAlignment(VAlign_Center);
	UCanvasPanelSlot* TopSlot = Root->AddChildToCanvas(Top);
	TopSlot->SetAnchors(FAnchors(0, 0, 1, 0));
	TopSlot->SetOffsets(FMargin(56.0f, 24.0f, 56.0f, 72.0f));
	UBorder* Rule = Box(T, FSlateColorBrush(FLinearColor(1.0f, 1.0f, 1.0f, 0.1f)), FMargin(0));
	UCanvasPanelSlot* RuleSlot = Root->AddChildToCanvas(Rule);
	RuleSlot->SetAnchors(FAnchors(0, 0, 1, 0));
	RuleSlot->SetOffsets(FMargin(56.0f, 102.0f, 56.0f, 1.0f));
	UBorder* RuleLit = Box(T, FSlateColorBrush(Cyan), FMargin(0));
	UCanvasPanelSlot* RuleLitSlot = Root->AddChildToCanvas(RuleLit);
	RuleLitSlot->SetAnchors(FAnchors(0, 0, 0, 0));
	RuleLitSlot->SetOffsets(FMargin(56.0f, 101.0f, 150.0f, 2.0f));

	// the columns
	LeftColumn = Make<UVerticalBox>(T);
	UCanvasPanelSlot* LeftSlot = Root->AddChildToCanvas(LeftColumn);
	LeftSlot->SetAnchors(FAnchors(0, 0, 0, 1));
	LeftSlot->SetOffsets(FMargin(56.0f, 122.0f, 390.0f, 60.0f));
	RightColumn = Make<UVerticalBox>(T);
	UCanvasPanelSlot* RightSlot = Root->AddChildToCanvas(RightColumn);
	RightSlot->SetAnchors(FAnchors(1, 0, 1, 1));
	RightSlot->SetOffsets(FMargin(-396.0f, 122.0f, 340.0f, 60.0f));

	// a slot's bay: everything owned for it, beside its own column
	FPlate BayPlate;
	BayPlate.Cut = 18.0f;
	BayPlate.Fill = FLinearColor(0.02f, 0.028f, 0.05f, 0.95f);
	BayPlate.FillLow = FLinearColor(0.012f, 0.016f, 0.03f, 0.96f);
	BayPlate.Edge = Alpha(Cyan, 0.35f);
	BayPlate.Hatch = 1.0f;
	Flyout = Box(T, PlateBrush(this, BayPlate), FMargin(18, 14, 8, 16));
	UVerticalBox* GridColumn = Make<UVerticalBox>(T);
	GridTitle = Text(T, TEXT(""), 11, Ink, true, 300);
	GridColumn->AddChildToVerticalBox(GridTitle)->SetPadding(FMargin(0, 0, 0, 12));
	UScrollBox* GridScroll = Make<UScrollBox>(T);
	Grid = Make<UWrapBox>(T);
	Grid->SetInnerSlotPadding(FVector2D(8.0f, 8.0f));
	GridScroll->AddChild(Grid);
	UVerticalBoxSlot* GridScrollSlot = GridColumn->AddChildToVerticalBox(GridScroll);
	GridScrollSlot->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
	Flyout->SetContent(GridColumn);
	Flyout->SetVisibility(ESlateVisibility::Collapsed);
	Root->AddChildToCanvas(Flyout);

	// the details of the item under the cursor, on the far side
	FPlate DetailPlate = BayPlate;
	DetailPlate.Edge = FLinearColor(1.0f, 1.0f, 1.0f, 0.14f);
	DetailPanel = Box(T, PlateBrush(this, DetailPlate), FMargin(24, 18, 22, 18));
	UVerticalBox* DetailColumn = Make<UVerticalBox>(T);
	UScrollBox* DetailScroll = Make<UScrollBox>(T);
	Details = Make<UVerticalBox>(T);
	DetailScroll->AddChild(Details);
	UVerticalBoxSlot* DetailsSlot = DetailColumn->AddChildToVerticalBox(DetailScroll);
	DetailsSlot->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
	UHorizontalBox* Actions = Make<UHorizontalBox>(T);
	auto Action = [&](TObjectPtr<UButton>& Out, TObjectPtr<UTextBlock>& Label, const TCHAR* Caption, const FLinearColor& Color)
	{
		Out = Make<UButton>(T);
		FPlate Normal;
		Normal.Cut = 9.0f;
		Normal.Accent = Alpha(Color, 1.0f);
		Normal.Wash = 0.5f;
		Normal.Edge = Alpha(Color, 0.55f);
		FPlate Over = Normal;
		Over.Wash = 0.95f;
		Over.Edge = Alpha(Color, 1.0f);
		Over.EdgeWidth = 1.5f;
		Over.TopLight = 1.0f;
		FPlate Down = Over;
		Down.Wash = 1.3f;
		Down.EdgeWidth = 2.0f;
		StyleButton(Out, PlateBrush(this, Normal), PlateBrush(this, Over), PlateBrush(this, Down));
		Label = Text(T, Caption, 11, Ink, true, 140);
		Out->SetContent(Box(T, FSlateColorBrush(FLinearColor::Transparent), FMargin(16, 9, 16, 9)));
		Cast<UBorder>(Out->GetContent())->SetContent(Label);
		Actions->AddChildToHorizontalBox(Out)->SetPadding(FMargin(0, 0, 8, 0));
	};
	Action(EquipButton, EquipLabel, TEXT("EQUIP  [E]"), Cyan);
	Action(LockButton, LockLabel, TEXT("LOCK  [L]"), Gold);
	Action(DismantleButton, DismantleLabel, TEXT("DISMANTLE  [X]"), Bad);
	EquipButton->OnClicked.AddDynamic(this, &USOInventoryWidget::OnEquip);
	LockButton->OnClicked.AddDynamic(this, &USOInventoryWidget::OnLock);
	DismantleButton->OnClicked.AddDynamic(this, &USOInventoryWidget::OnDismantle);
	DetailColumn->AddChildToVerticalBox(Actions)->SetPadding(FMargin(0, 14, 0, 0));
	DetailPanel->SetContent(DetailColumn);
	DetailPanel->SetVisibility(ESlateVisibility::Collapsed);
	Root->AddChildToCanvas(DetailPanel);

	// what the keys do
	UHorizontalBox* Hints = Make<UHorizontalBox>(T);
	Hints->AddChildToHorizontalBox(Hint(T, TEXT("CLICK"), TEXT("OPEN A SLOT")));
	Hints->AddChildToHorizontalBox(Hint(T, TEXT("E"), TEXT("EQUIP")));
	Hints->AddChildToHorizontalBox(Hint(T, TEXT("L"), TEXT("LOCK")));
	Hints->AddChildToHorizontalBox(Hint(T, TEXT("X"), TEXT("DISMANTLE (TWICE)")));
	Hints->AddChildToHorizontalBox(Hint(T, TEXT("DRAG"), TEXT("TURN")));
	Hints->AddChildToHorizontalBox(Hint(T, TEXT("ESC"), TEXT("BACK")));
	UCanvasPanelSlot* HintSlot = Root->AddChildToCanvas(Hints);
	HintSlot->SetAnchors(FAnchors(0.5f, 1.0f, 0.5f, 1.0f));
	HintSlot->SetAlignment(FVector2D(0.5f, 1.0f));
	HintSlot->SetAutoSize(true);
	HintSlot->SetOffsets(FMargin(0.0f, -20.0f, 0.0f, 0.0f));
	Refresh();
}

void USOInventoryWidget::Bind(USOInventoryComponent* InInventory)
{
	if (Inventory && ChangedHandle.IsValid())
	{
		Inventory->OnChanged.Remove(ChangedHandle);
	}
	Inventory = InInventory;
	if (Inventory)
	{
		ChangedHandle = Inventory->OnChanged.AddUObject(this, &USOInventoryWidget::Refresh);
	}
	Refresh();
}

FSOTileInfo USOInventoryWidget::WeaponTile(const FSOWeaponInstance& W, bool bSlot) const
{
	FSOTileInfo Tile;
	const USOWeaponData* Data = ArchetypeOf(W);
	Tile.Kind = bSlot ? FName(TEXT("wslot")) : FName(TEXT("weapon"));
	Tile.Key = W.Uid;
	Tile.Icon = Data ? Data->Icon.LoadSynchronous() : nullptr;
	Tile.Rarity = RarityColor(W.Rarity);
	Tile.Title = W.Name;
	Tile.Sub = Data ? FString::Printf(TEXT("%s %s"), *ClassName(Data).ToUpper(), *Data->DisplayName.ToString().ToUpper()) : FString();
	Tile.Tag = Tile.Sub;
	Tile.Power = W.Power;
	Tile.bEquipped = Inventory && Inventory->IsEquipped(W.Uid) && !bSlot;
	Tile.bNew = W.bNew;
	Tile.bWide = true;
	Tile.Size = FVector2D(190.0f, 95.0f);
	if (!bSlot && W.bKeep && !Tile.bEquipped && !Tile.bNew)
	{
		Tile.Badge = TEXT("LOCKED");
	}
	return Tile;
}

FSOTileInfo USOInventoryWidget::ArmorTile(const FSOArmorInstance& A, bool bSlot) const
{
	FSOTileInfo Tile;
	const USOWardrobeData* Wardrobe = Inventory ? USOWardrobeData::Get(Inventory->GetBody()) : nullptr;
	const FSOWardrobeItem* Item = Wardrobe ? Wardrobe->Find(A.Slot, A.Item) : nullptr;
	Tile.Kind = bSlot ? FName(TEXT("aslot")) : FName(TEXT("armor"));
	Tile.Key = A.Uid;
	Tile.Icon = Item ? Item->Icon.LoadSynchronous() : nullptr;
	Tile.Rarity = RarityColor(A.Rarity);
	Tile.Title = Item ? Item->Label.ToString() : A.Item.ToString();
	Tile.Sub = USOWardrobeData::SlotLabel(A.Slot).ToString().ToUpper();
	Tile.Power = A.Power;
	Tile.bEquipped = A.bEquipped && !bSlot;
	Tile.bNew = A.bNew;
	Tile.Size = FVector2D(91.0f, 91.0f);
	if (bSlot && Item)
	{
		Tile.Tag = FString::Printf(TEXT("%d ARMOUR"), Item->Armor);
	}
	return Tile;
}

void USOInventoryWidget::Refresh()
{
	if (!Inventory || !WidgetTree || !LeftColumn)
	{
		return;
	}
	if (Preview)
	{
		Preview->Sync(Inventory);
	}
	PowerText->SetText(FText::AsNumber(Inventory->GetPower()));
	StatsRow->ClearChildren();
	const TPair<const TCHAR*, FString> Figures[] = {
		{ TEXT("ARMOUR"), FString::FromInt(Inventory->GetArmorRating()) }, { TEXT("LEVEL"), FString::FromInt(Inventory->GetLevel()) },
		{ TEXT("CREDITS"), FText::AsNumber(Inventory->GetCredits()).ToString() }, { TEXT("ALLOY"), FText::AsNumber(Inventory->GetAlloy()).ToString() },
		{ TEXT("VAULT"), FString::Printf(TEXT("%d / %d"), Inventory->GetItems().Num(), USOLootLibrary::VaultCap) } };
	for (const TPair<const TCHAR*, FString>& F : Figures)
	{
		StatsRow->AddChildToHorizontalBox(Figure(WidgetTree, F.Key, F.Value, Ink))->SetPadding(FMargin(0, 0, 38, 0));
	}
	BodyLabel->SetText(FText::FromString(Inventory->GetBody() == TEXT("female") ? TEXT("BODY   /   FEMALE") : TEXT("BODY   /   MALE")));
	FillColumns();
	FillFlyout();
}

void USOInventoryWidget::FillColumns()
{
	UWidgetTree* T = WidgetTree;
	const USOLootTables* Tables = USOLootLibrary::GetTables();
	auto AddTile = [&](UVerticalBox* Column, const FSOTileInfo& Info)
	{
		USOInventoryTile* Widget = CreateWidget<USOInventoryTile>(this, USOInventoryTile::StaticClass());
		Widget->Setup(this, Info);
		Column->AddChildToVerticalBox(Widget)->SetPadding(FMargin(0, 0, 0, 8));
	};
	auto ArmorSlotTile = [&](FName SlotId)
	{
		FSOTileInfo Info;
		if (const FSOArmorInstance* A = Inventory->GetEquippedArmor(SlotId))
		{
			Info = ArmorTile(*A, true);
		}
		else
		{
			Info.Kind = TEXT("aslot");
			Info.Sub = USOWardrobeData::SlotLabel(SlotId).ToString().ToUpper();
			Info.Title = TEXT("Nothing worn");
			Info.Rarity = Dim;
		}
		Info.Key = SlotId.ToString();
		Info.bActive = OpenSlotId == SlotId.ToString();
		return Info;
	};

	LeftColumn->ClearChildren();
	LeftColumn->AddChildToVerticalBox(Header(T, TEXT("WEAPONS")))->SetPadding(FMargin(0, 0, 0, 10));
	for (int32 SlotId = 0; SlotId < USOInventoryComponent::NumSlots; ++SlotId)
	{
		FSOTileInfo Info;
		if (const FSOWeaponInstance* W = Inventory->GetEquipped(SlotId))
		{
			Info = WeaponTile(*W, true);
		}
		else
		{
			Info.Kind = TEXT("wslot");
			Info.Title = TEXT("Empty");
			Info.Rarity = Dim;
			Info.bWide = true;
		}
		const FString Name = Tables && Tables->SlotNames.IsValidIndex(SlotId) ? Tables->SlotNames[SlotId].ToString().ToUpper() : FString::Printf(TEXT("SLOT %d"), SlotId + 1);
		Info.Sub = FString::Printf(TEXT("%d  %s%s"), SlotId + 1, *Name, SlotId == Inventory->GetActiveSlot() ? TEXT("  ·  IN HAND") : TEXT(""));
		Info.Badge.Reset();
		Info.Key = FString::FromInt(SlotId);
		Info.bActive = OpenSlotId == Info.Key;
		AddTile(LeftColumn, Info);
	}
	LeftColumn->AddChildToVerticalBox(Header(T, TEXT("OUTER LAYERS")))->SetPadding(FMargin(0, 14, 0, 10));
	for (const FName SlotId : { FName(TEXT("outer")), FName(TEXT("vest")) })
	{
		AddTile(LeftColumn, ArmorSlotTile(SlotId));
	}
	RightColumn->ClearChildren();
	RightColumn->AddChildToVerticalBox(Header(T, TEXT("ARMOUR")))->SetPadding(FMargin(0, 0, 0, 10));
	for (const FName SlotId : { FName(TEXT("head")), FName(TEXT("top")), FName(TEXT("hands")), FName(TEXT("legs")), FName(TEXT("feet")) })
	{
		AddTile(RightColumn, ArmorSlotTile(SlotId));
	}
}

void USOInventoryWidget::OpenSlot(const FString& SlotId)
{
	OpenSlotId = SlotId;
	SelectedKey.Reset();
	HoverKey.Reset();
	DismantleArmedAt = -100.0;
	if (!SlotId.IsEmpty() && Inventory)
	{
		// the item there now is the first one shown
		if (IsWeaponSlot(SlotId))
		{
			if (const FSOWeaponInstance* W = Inventory->GetEquipped(FCString::Atoi(*SlotId)))
			{
				SelectedKey = W->Uid;
			}
		}
		else if (const FSOArmorInstance* A = Inventory->GetEquippedArmor(FName(*SlotId)))
		{
			SelectedKey = A->Uid;
		}
	}
	USOSoundLibrary::Play2D(this, SlotId.IsEmpty() ? TEXT("ui_close") : TEXT("ui_open"), 0.45f, 0.0f);
	Refresh();
}

void USOInventoryWidget::FillFlyout()
{
	if (!Flyout)
	{
		return;
	}
	if (OpenSlotId.IsEmpty() || !Inventory)
	{
		Flyout->SetVisibility(ESlateVisibility::Collapsed);
		DetailPanel->SetVisibility(ESlateVisibility::Collapsed);
		LeftColumn->SetVisibility(ESlateVisibility::Visible);
		RightColumn->SetVisibility(ESlateVisibility::Visible);
		StageShiftTarget = 0.0f;
		return;
	}
	Flyout->SetVisibility(ESlateVisibility::Visible);
	DetailPanel->SetVisibility(ESlateVisibility::Visible);
	// The bay beside the slot's own column, the details where the other column was, the character in the gap
	// between them (1920 wide: column 56-446, bay 462-910, gap, details 1364-1864; mirrored for the right column).
	const bool bLeft = IsWeaponSlot(OpenSlotId) || OpenSlotId == TEXT("outer") || OpenSlotId == TEXT("vest");
	LeftColumn->SetVisibility(bLeft ? ESlateVisibility::Visible : ESlateVisibility::Collapsed);
	RightColumn->SetVisibility(bLeft ? ESlateVisibility::Collapsed : ESlateVisibility::Visible);
	StageShiftTarget = bLeft ? 177.0f : -177.0f;
	if (UCanvasPanelSlot* S = Cast<UCanvasPanelSlot>(Flyout->Slot))
	{
		S->SetAnchors(bLeft ? FAnchors(0, 0, 0, 1) : FAnchors(1, 0, 1, 1));
		S->SetAlignment(FVector2D(bLeft ? 0.0f : 1.0f, 0.0f));
		S->SetOffsets(bLeft ? FMargin(462.0f, 122.0f, 448.0f, 60.0f) : FMargin(-412.0f, 122.0f, 448.0f, 60.0f));
	}
	if (UCanvasPanelSlot* S = Cast<UCanvasPanelSlot>(DetailPanel->Slot))
	{
		S->SetAnchors(bLeft ? FAnchors(1, 0, 1, 1) : FAnchors(0, 0, 0, 1));
		S->SetAlignment(FVector2D(bLeft ? 1.0f : 0.0f, 0.0f));
		S->SetOffsets(bLeft ? FMargin(-56.0f, 122.0f, 500.0f, 60.0f) : FMargin(56.0f, 122.0f, 500.0f, 60.0f));
	}
	Grid->ClearChildren();
	TArray<FSOTileInfo> Tiles;
	if (IsWeaponSlot(OpenSlotId))
	{
		const int32 SlotId = FCString::Atoi(*OpenSlotId);
		const USOLootTables* Tables = USOLootLibrary::GetTables();
		TArray<const FSOWeaponInstance*> List;
		for (const FSOWeaponInstance& W : Inventory->GetItems())
		{
			const USOWeaponData* Data = ArchetypeOf(W);
			if (Data && FMath::Clamp(Data->Slot, 0, 2) == SlotId)
			{
				List.Add(&W);
			}
		}
		List.Sort([this](const FSOWeaponInstance& A, const FSOWeaponInstance& B)
		{
			const bool EA = Inventory->IsEquipped(A.Uid), EB = Inventory->IsEquipped(B.Uid);
			if (EA != EB) return EA;
			if (A.bNew != B.bNew) return A.bNew;
			if (A.Rarity != B.Rarity) return A.Rarity > B.Rarity;
			return A.Power > B.Power;
		});
		const FString Name = Tables && Tables->SlotNames.IsValidIndex(SlotId) ? Tables->SlotNames[SlotId].ToString().ToUpper() : TEXT("WEAPONS");
		GridTitle->SetText(FText::FromString(FString::Printf(TEXT("%s  ·  %d"), *Name, List.Num())));
		for (const FSOWeaponInstance* W : List)
		{
			Tiles.Add(WeaponTile(*W, false));
		}
	}
	else
	{
		const FName SlotId(*OpenSlotId);
		const USOWardrobeData* Wardrobe = USOWardrobeData::Get(Inventory->GetBody());
		for (const FSOArmorInstance& A : Inventory->GetArmor())
		{
			if (A.Slot == SlotId && (!Wardrobe || Wardrobe->Find(A.Slot, A.Item)))
			{
				Tiles.Add(ArmorTile(A, false));
			}
		}
		Tiles.Sort([](const FSOTileInfo& A, const FSOTileInfo& B) { return A.bEquipped != B.bEquipped ? A.bEquipped : A.Title < B.Title; });
		GridTitle->SetText(FText::FromString(FString::Printf(TEXT("%s  ·  %d"), *USOWardrobeData::SlotLabel(SlotId).ToString().ToUpper(), Tiles.Num())));
	}
	if (SelectedKey.IsEmpty() && Tiles.Num() > 0)
	{
		SelectedKey = Tiles[0].Key;                 // (nothing in the slot yet: the first thing owned for it is shown)
	}
	for (FSOTileInfo& Info : Tiles)
	{
		Info.bActive = Info.Key == SelectedKey;
		USOInventoryTile* Widget = CreateWidget<USOInventoryTile>(this, USOInventoryTile::StaticClass());
		Widget->Setup(this, Info);
		Grid->AddChildToWrapBox(Widget);
	}
	FillDetails();
}

FString USOInventoryWidget::ShownKey() const
{
	return HoverKey.IsEmpty() ? SelectedKey : HoverKey;
}

void USOInventoryWidget::FillDetails()
{
	if (!Details || !Inventory)
	{
		return;
	}
	Details->ClearChildren();
	const FString Key = ShownKey();
	if (const FSOWeaponInstance* W = Inventory->Find(Key))
	{
		FillWeaponDetails(*W);
	}
	else if (const FSOArmorInstance* A = Inventory->FindArmor(Key))
	{
		FillArmorDetails(*A);
	}
	else
	{
		Details->AddChildToVerticalBox(Text(WidgetTree, TEXT("Nothing selected"), 14, Dim));
		EquipButton->SetIsEnabled(false);
		LockButton->SetIsEnabled(false);
		DismantleButton->SetIsEnabled(false);
	}
}

void USOInventoryWidget::FillWeaponDetails(const FSOWeaponInstance& W)
{
	UWidgetTree* T = WidgetTree;
	const USOLootTables* Tables = USOLootLibrary::GetTables();
	const USOWeaponData* Data = ArchetypeOf(W);
	const FLinearColor Rarity = RarityColor(W.Rarity);
	UTextBlock* GunName = Text(T, W.Name.ToUpper(), 24, Ink, true, 60);
	GunName->SetAutoWrapText(true);
	Details->AddChildToVerticalBox(GunName);
	UHorizontalBox* Kind = Make<UHorizontalBox>(T);
	Kind->AddChildToHorizontalBox(Chip(T, RarityName(W.Rarity).ToUpper(), Rarity))->SetVerticalAlignment(VAlign_Center);
	UHorizontalBoxSlot* KindSlot = Kind->AddChildToHorizontalBox(Text(T, FString::Printf(TEXT("%s %s"), *ClassName(Data).ToUpper(),
		Data ? *Data->DisplayName.ToString().ToUpper() : TEXT("")), 10, Dim, true, 180));
	KindSlot->SetVerticalAlignment(VAlign_Center);
	KindSlot->SetPadding(FMargin(10, 0, 0, 0));
	Details->AddChildToVerticalBox(Kind)->SetPadding(FMargin(0, 6, 0, 0));
	if (UTexture2D* Icon = Data ? Data->Icon.LoadSynchronous() : nullptr)
	{
		UImage* Big = Make<UImage>(T);
		Big->SetBrushFromTexture(Icon, false);
		UOverlay* Frame = Make<UOverlay>(T);
		FPlate Shown;
		Shown.Cut = 16.0f;
		Shown.Accent = Alpha(Rarity, 1.0f);
		Shown.AccentBottom = 2.0f;
		Shown.Wash = 0.5f;
		Shown.Hatch = 1.0f;
		Frame->AddChildToOverlay(Box(T, PlateBrush(this, Shown), FMargin(0)));
		UOverlaySlot* BigSlot = Frame->AddChildToOverlay(Big);
		BigSlot->SetHorizontalAlignment(HAlign_Fill);
		BigSlot->SetVerticalAlignment(VAlign_Fill);
		Details->AddChildToVerticalBox(Sized(T, Frame, 440.0f, 200.0f))->SetPadding(FMargin(0, 12, 0, 12));
	}
	UHorizontalBox* PowerRow = Make<UHorizontalBox>(T);
	PowerRow->AddChildToHorizontalBox(Figure(T, TEXT("POWER"), FString::FromInt(W.Power), Gold, 26));
	const FSOSightInfo* Sight = Tables ? Tables->FindSight(W.Sight) : nullptr;
	UHorizontalBoxSlot* InfoSlot = PowerRow->AddChildToHorizontalBox(Text(T, FString::Printf(TEXT("Rolls %d %%   %s%s"), USOLootLibrary::RollQuality(W),
		Sight ? *Sight->Name.ToString() : TEXT(""), W.Source.IsEmpty() ? TEXT("") : *FString::Printf(TEXT("   ·   %s"), *W.Source)), 12, Dim));
	InfoSlot->SetVerticalAlignment(VAlign_Bottom);
	InfoSlot->SetPadding(FMargin(18, 0, 0, 6));
	Details->AddChildToVerticalBox(PowerRow)->SetPadding(FMargin(0, 0, 0, 10));

	// stats against the equipped copy of the same slot
	const FSOWeaponStats S = USOLootLibrary::ComputeStats(W);
	const FSOWeaponInstance* Equipped = Data ? Inventory->GetEquipped(FMath::Clamp(Data->Slot, 0, 2)) : nullptr;
	const bool bCompare = Equipped && Equipped->Uid != W.Uid;
	const FSOWeaponStats E = bCompare ? USOLootLibrary::ComputeStats(*Equipped) : S;
	const int32 Pellets = Data ? FMath::Max(1, Data->Pellets) : 1;
	struct FRow { const TCHAR* Name; float Value, Other, Max; FString Shown; bool bLowerBetter; };
	const FRow Rows[] = {
		{ TEXT("Impact"), S.Damage * Pellets, E.Damage * Pellets, 450.0f, Pellets > 1 ? FString::Printf(TEXT("%.0f x %d"), S.Damage, Pellets) : FString::Printf(TEXT("%.0f"), S.Damage), false },
		{ TEXT("Fire rate"), S.Rpm, E.Rpm, 1100.0f, FString::Printf(TEXT("%.0f rpm"), S.Rpm), false },
		{ TEXT("Magazine"), (float)S.Mag, (float)E.Mag, 150.0f, FString::FromInt(S.Mag), false },
		{ TEXT("Reload"), S.Reload, E.Reload, 4.0f, FString::Printf(TEXT("%.2f s"), S.Reload), true },
		{ TEXT("Range"), S.Range, E.Range, 180.0f, FString::Printf(TEXT("%.0f m"), S.Range), false },
		{ TEXT("Stability"), S.Spread, E.Spread, 7.0f, FString::Printf(TEXT("%.2f°"), S.Spread), true },
		{ TEXT("Zoom"), S.Zoom, E.Zoom, 8.0f, FString::Printf(TEXT("%.1fx"), S.Zoom), false },
	};
	for (const FRow& R : Rows)
	{
		UHorizontalBox* Line = Make<UHorizontalBox>(T);
		Line->AddChildToHorizontalBox(Sized(T, Text(T, R.Name, 12, Dim), 90.0f, 0.0f));
		UProgressBar* Bar = Make<UProgressBar>(T);
		const float Fill = R.bLowerBetter ? 1.0f - FMath::Clamp(R.Value / R.Max, 0.0f, 0.95f) : FMath::Clamp(R.Value / R.Max, 0.03f, 1.0f);
		FlatBar(Bar);
		Bar->SetPercent(Fill);
		bool bBetter = false, bWorse = false;
		if (bCompare && !FMath::IsNearlyEqual(R.Value, R.Other, FMath::Abs(R.Other) * 0.005f + 0.001f))
		{
			bBetter = R.bLowerBetter ? R.Value < R.Other : R.Value > R.Other;
			bWorse = !bBetter;
		}
		Bar->SetFillColorAndOpacity(bBetter ? Good : bWorse ? Bad : Ink * 0.85f);
		UHorizontalBoxSlot* BarSlot = Line->AddChildToHorizontalBox(Sized(T, Bar, 0.0f, 4.0f));
		BarSlot->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
		BarSlot->SetVerticalAlignment(VAlign_Center);
		Line->AddChildToHorizontalBox(Sized(T, Text(T, R.Shown, 12, Ink, true), 92.0f, 0.0f))->SetPadding(FMargin(10, 0, 0, 0));
		FString Delta;
		if (bBetter || bWorse)
		{
			Delta = FString::Printf(TEXT("%s%.0f%%"), R.Value > R.Other ? TEXT("+") : TEXT(""), (R.Value / FMath::Max(R.Other, 0.001f) - 1.0f) * 100.0f);
		}
		Line->AddChildToHorizontalBox(Sized(T, Text(T, Delta, 11, bBetter ? Good : Bad, true), 52.0f, 0.0f));
		Details->AddChildToVerticalBox(Line)->SetPadding(FMargin(0, 3, 0, 3));
	}
	if (bCompare)
	{
		Details->AddChildToVerticalBox(Text(T, FString::Printf(TEXT("against %s (equipped)"), *Equipped->Name), 10, Dim))->SetPadding(FMargin(0, 4, 0, 0));
	}
	// perks: what sets this copy apart
	Details->AddChildToVerticalBox(Header(T, W.Perks.Num() > 0 ? TEXT("PERKS") : TEXT("NO PERKS")))->SetPadding(FMargin(0, 14, 0, 8));
	for (const FName& PerkId : W.Perks)
	{
		if (const FSOPerkInfo* Perk = Tables ? Tables->FindPerk(PerkId) : nullptr)
		{
			UHorizontalBox* Row = Make<UHorizontalBox>(T);
			Row->AddChildToHorizontalBox(Sized(T, Box(T, FSlateColorBrush(Violet), FMargin(0)), 3.0f, 0.0f))->SetPadding(FMargin(0, 2, 12, 2));
			UVerticalBox* Lines = Make<UVerticalBox>(T);
			Lines->AddChildToVerticalBox(Text(T, Perk->Name.ToString(), 13, Ink, true));
			UTextBlock* Desc = Text(T, Perk->Description.ToString(), 11, Dim);
			Desc->SetAutoWrapText(true);
			Lines->AddChildToVerticalBox(Desc);
			Row->AddChildToHorizontalBox(Lines)->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
			Details->AddChildToVerticalBox(Row)->SetPadding(FMargin(0, 0, 0, 8));
		}
	}
	const bool bEquipped = Inventory->IsEquipped(W.Uid);
	EquipButton->SetIsEnabled(!bEquipped);
	EquipLabel->SetText(FText::FromString(bEquipped ? TEXT("EQUIPPED") : TEXT("EQUIP  [E]")));
	LockButton->SetIsEnabled(true);
	LockLabel->SetText(FText::FromString(W.bKeep ? TEXT("UNLOCK  [L]") : TEXT("LOCK  [L]")));
	DismantleButton->SetIsEnabled(!bEquipped && !W.bKeep);
	const bool bArmed = FPlatformTime::Seconds() - DismantleArmedAt < 2.5;
	DismantleLabel->SetText(FText::FromString(bArmed ? FString::Printf(TEXT("CONFIRM  +%d ALLOY"), USOLootLibrary::DismantleAlloy(W))
		: FString::Printf(TEXT("DISMANTLE  [X]  +%d"), USOLootLibrary::DismantleAlloy(W))));
}

void USOInventoryWidget::FillArmorDetails(const FSOArmorInstance& A)
{
	UWidgetTree* T = WidgetTree;
	const USOWardrobeData* Wardrobe = USOWardrobeData::Get(Inventory->GetBody());
	const FSOWardrobeItem* Item = Wardrobe ? Wardrobe->Find(A.Slot, A.Item) : nullptr;
	const FLinearColor Rarity = RarityColor(A.Rarity);
	UTextBlock* PieceName = Text(T, (Item ? Item->Label.ToString() : A.Item.ToString()).ToUpper(), 22, Ink, true, 60);
	PieceName->SetAutoWrapText(true);
	Details->AddChildToVerticalBox(PieceName);
	UHorizontalBox* Kind = Make<UHorizontalBox>(T);
	Kind->AddChildToHorizontalBox(Chip(T, RarityName(A.Rarity).ToUpper(), Rarity))->SetVerticalAlignment(VAlign_Center);
	UHorizontalBoxSlot* KindSlot = Kind->AddChildToHorizontalBox(Text(T, FString::Printf(TEXT("%s ARMOUR"), *USOWardrobeData::SlotLabel(A.Slot).ToString().ToUpper()), 10, Dim, true, 180));
	KindSlot->SetVerticalAlignment(VAlign_Center);
	KindSlot->SetPadding(FMargin(10, 0, 0, 0));
	Details->AddChildToVerticalBox(Kind)->SetPadding(FMargin(0, 6, 0, 0));
	if (UTexture2D* Icon = Item ? Item->Icon.LoadSynchronous() : nullptr)
	{
		UImage* Big = Make<UImage>(T);
		Big->SetBrushFromTexture(Icon, false);
		UOverlay* Frame = Make<UOverlay>(T);
		FPlate Shown;
		Shown.Cut = 16.0f;
		Shown.Accent = Alpha(Rarity, 1.0f);
		Shown.AccentBottom = 2.0f;
		Shown.Wash = 0.5f;
		Shown.Hatch = 1.0f;
		Frame->AddChildToOverlay(Box(T, PlateBrush(this, Shown), FMargin(0)));
		UOverlaySlot* BigSlot = Frame->AddChildToOverlay(Big);
		BigSlot->SetHorizontalAlignment(HAlign_Fill);
		BigSlot->SetVerticalAlignment(VAlign_Fill);
		Details->AddChildToVerticalBox(Sized(T, Frame, 260.0f, 260.0f))->SetPadding(FMargin(0, 8, 0, 8));
	}
	const int32 Armor = Item ? Item->Armor : 0;
	const FSOArmorInstance* Worn = Inventory->GetEquippedArmor(A.Slot);
	const FSOWardrobeItem* WornItem = Worn && Wardrobe ? Wardrobe->Find(Worn->Slot, Worn->Item) : nullptr;
	FString Compare;
	if (WornItem && Worn->Uid != A.Uid && WornItem->Armor != Armor)
	{
		Compare = FString::Printf(TEXT("   %s%d against what is worn"), Armor > WornItem->Armor ? TEXT("+") : TEXT(""), Armor - WornItem->Armor);
	}
	UHorizontalBox* Figures = Make<UHorizontalBox>(T);
	Figures->AddChildToHorizontalBox(Figure(T, TEXT("POWER"), FString::FromInt(A.Power), Gold, 26))->SetPadding(FMargin(0, 0, 30, 0));
	Figures->AddChildToHorizontalBox(Figure(T, TEXT("ARMOUR"), FString::FromInt(Armor), Ink, 26));
	if (!Compare.IsEmpty())
	{
		UHorizontalBoxSlot* CompareSlot = Figures->AddChildToHorizontalBox(Text(T, Compare, 11, Armor > (WornItem ? WornItem->Armor : 0) ? Good : Bad, true));
		CompareSlot->SetVerticalAlignment(VAlign_Bottom);
		CompareSlot->SetPadding(FMargin(6, 0, 0, 6));
	}
	Details->AddChildToVerticalBox(Figures)->SetPadding(FMargin(0, 0, 0, 10));
	Details->AddChildToVerticalBox(Header(T, TEXT("PERKS")))->SetPadding(FMargin(0, 8, 0, 8));
	UTextBlock* Note = Text(T, TEXT("Armour perks come with the world's later chapters: for now every piece is its look and its armour."), 11, Dim);
	Note->SetAutoWrapText(true);
	Details->AddChildToVerticalBox(Note);
	// a required slot can be swapped but never emptied: what is worn there shows as WORN
	const bool bRequired = !USOWardrobeData::IsOptionalSlot(A.Slot);
	EquipButton->SetIsEnabled(!(A.bEquipped && bRequired));
	EquipLabel->SetText(FText::FromString(A.bEquipped ? (bRequired ? TEXT("WORN") : TEXT("TAKE OFF  [E]")) : TEXT("WEAR  [E]")));
	LockButton->SetIsEnabled(false);
	DismantleButton->SetIsEnabled(false);
	LockLabel->SetText(FText::FromString(TEXT("LOCK  [L]")));
	DismantleLabel->SetText(FText::FromString(TEXT("DISMANTLE  [X]")));
}

void USOInventoryWidget::OnTile(const FSOTileInfo& Tile)
{
	if (Tile.Kind == TEXT("wslot") || Tile.Kind == TEXT("aslot"))
	{
		OpenSlot(OpenSlotId == Tile.Key ? FString() : Tile.Key);
		return;
	}
	// a grid item: select it (a second click on the selected one equips / wears it)
	if (SelectedKey == Tile.Key)
	{
		OnEquip();
		return;
	}
	SelectedKey = Tile.Key;
	DismantleArmedAt = -100.0;
	if (const FSOWeaponInstance* W = Inventory ? Inventory->Find(Tile.Key) : nullptr; W && W->bNew)
	{
		Inventory->ServerMarkSeen(Tile.Key);
	}
	USOSoundLibrary::Play2D(this, TEXT("ui_move"), 0.5f, 0.0f);
	FillFlyout();
}

void USOInventoryWidget::OnTileHover(const FSOTileInfo& Tile, bool bHover)
{
	if (Tile.Kind != TEXT("weapon") && Tile.Kind != TEXT("armor"))
	{
		return;
	}
	const FString Want = bHover ? Tile.Key : FString();
	if (HoverKey != Want)
	{
		HoverKey = Want;
		FillDetails();
	}
}

void USOInventoryWidget::OnEquip()
{
	if (!Inventory)
	{
		return;
	}
	if (const FSOWeaponInstance* W = Inventory->Find(SelectedKey); W && !Inventory->IsEquipped(W->Uid))
	{
		Inventory->ServerEquip(W->Uid);
		USOSoundLibrary::Play2D(this, TEXT("ui_equip"), 0.7f, 0.0f);
	}
	else if (const FSOArmorInstance* A = Inventory->FindArmor(SelectedKey))
	{
		Inventory->ServerEquipArmor(A->Uid);
		USOSoundLibrary::Play2D(this, TEXT("ui_equip"), 0.7f, 0.0f);
	}
}

void USOInventoryWidget::OnLock()
{
	if (const FSOWeaponInstance* W = Inventory ? Inventory->Find(SelectedKey) : nullptr)
	{
		Inventory->ServerSetKeep(W->Uid, !W->bKeep);
		USOSoundLibrary::Play2D(this, TEXT("ui_lock"), 0.6f, 0.0f);
	}
}

void USOInventoryWidget::OnDismantle()
{
	const FSOWeaponInstance* W = Inventory ? Inventory->Find(SelectedKey) : nullptr;
	if (!W || Inventory->IsEquipped(W->Uid) || W->bKeep)
	{
		USOSoundLibrary::Play2D(this, TEXT("ui_deny"), 0.6f, 0.0f);
		return;
	}
	if (FPlatformTime::Seconds() - DismantleArmedAt > 2.5)
	{
		DismantleArmedAt = FPlatformTime::Seconds(); // press again to confirm
		FillDetails();
		return;
	}
	DismantleArmedAt = -100.0;
	Inventory->ServerDismantle(W->Uid);
	SelectedKey.Reset();
	HoverKey.Reset();
	USOSoundLibrary::Play2D(this, TEXT("ui_dismantle"), 0.7f, 0.0f);
}

void USOInventoryWidget::OnBody()
{
	if (Inventory)
	{
		Inventory->ServerSetBody(Inventory->GetBody() == TEXT("female") ? FName(TEXT("male")) : FName(TEXT("female")));
		USOSoundLibrary::Play2D(this, TEXT("ui_equip"), 0.6f, 0.0f);
	}
}

void USOInventoryWidget::Close()
{
	if (OnClose)
	{
		OnClose();
	}
}

FReply USOInventoryWidget::NativeOnMouseButtonDown(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent)
{
	if (InMouseEvent.GetEffectingButton() == EKeys::LeftMouseButton)
	{
		bDragging = true;
		return FReply::Handled().CaptureMouse(TakeWidget());
	}
	return Super::NativeOnMouseButtonDown(InGeometry, InMouseEvent);
}

FReply USOInventoryWidget::NativeOnMouseButtonUp(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent)
{
	if (bDragging)
	{
		bDragging = false;
		return FReply::Handled().ReleaseMouseCapture();
	}
	return Super::NativeOnMouseButtonUp(InGeometry, InMouseEvent);
}

FReply USOInventoryWidget::NativeOnMouseMove(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent)
{
	if (bDragging && Preview)
	{
		Preview->Yaw -= InMouseEvent.GetCursorDelta().X * 0.45f;
		return FReply::Handled();
	}
	return Super::NativeOnMouseMove(InGeometry, InMouseEvent);
}

FReply USOInventoryWidget::NativeOnKeyDown(const FGeometry& InGeometry, const FKeyEvent& InKeyEvent)
{
	const FKey Key = InKeyEvent.GetKey();
	if (Key == EKeys::Escape || Key == EKeys::Gamepad_FaceButton_Right)
	{
		if (!OpenSlotId.IsEmpty())
		{
			OpenSlot(FString()); // back out of the grid first
		}
		else
		{
			Close();
		}
		return FReply::Handled();
	}
	if (Key == EKeys::I || Key == EKeys::Tab || Key == EKeys::Gamepad_Special_Left)
	{
		Close();
		return FReply::Handled();
	}
	if (Key == EKeys::E || Key == EKeys::Gamepad_FaceButton_Top)
	{
		OnEquip();
		return FReply::Handled();
	}
	if (Key == EKeys::L || Key == EKeys::Gamepad_RightShoulder)
	{
		OnLock();
		return FReply::Handled();
	}
	if (Key == EKeys::X || Key == EKeys::Gamepad_FaceButton_Left)
	{
		OnDismantle();
		return FReply::Handled();
	}
	if (Key == EKeys::One || Key == EKeys::Two || Key == EKeys::Three)
	{
		if (Inventory)
		{
			Inventory->ServerSelectSlot(Key == EKeys::One ? 0 : Key == EKeys::Two ? 1 : 2);
		}
		return FReply::Handled();
	}
	return Super::NativeOnKeyDown(InGeometry, InKeyEvent);
}
