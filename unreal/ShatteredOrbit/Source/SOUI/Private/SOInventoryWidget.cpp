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

	/** A thin cyan rule with a diamond: the section headers. */
	UWidget* Header(UWidgetTree* T, const FString& Title)
	{
		UHorizontalBox* Row = Make<UHorizontalBox>(T);
		Row->AddChildToHorizontalBox(Text(T, TEXT("◆"), 10, Cyan))->SetVerticalAlignment(VAlign_Center);
		Row->AddChildToHorizontalBox(Text(T, Title, 12, Ink, true, 260))->SetPadding(FMargin(8, 0, 10, 0));
		UHorizontalBoxSlot* Line = Row->AddChildToHorizontalBox(Sized(T, Box(T, FSlateColorBrush(Cyan * FLinearColor(1, 1, 1, 0.35f)), FMargin(0)), 0.0f, 1.0f));
		Line->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
		Line->SetVerticalAlignment(VAlign_Center);
		return Row;
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
		UButton* Button = Make<UButton>(T);
		const FLinearColor Edge = Info.bActive ? Cyan : Info.Rarity * FLinearColor(1, 1, 1, 0.55f);
		StyleButton(Button, Rounded(TileFill, Edge, Info.bActive ? 2.0f : 1.2f), Rounded(TileFill * 1.6f, Cyan, 2.0f), Rounded(TileFill * 2.0f, Cyan, 2.5f));
		Button->OnClicked.AddDynamic(this, &USOInventoryTile::OnClicked);
		Button->OnHovered.AddDynamic(this, &USOInventoryTile::OnHovered);
		Button->OnUnhovered.AddDynamic(this, &USOInventoryTile::OnUnhovered);

		// the icon square: rarity glow from below, the rendered icon, power in the corner, NEW / equipped marks
		const FVector2D IconSize = bSlot ? (Info.bWide ? FVector2D(190.0f, 95.0f) : FVector2D(92.0f, 92.0f)) : Info.Size;
		UOverlay* Square = Make<UOverlay>(T);
		UBorder* Wash = Box(T, Rounded(Info.Rarity * FLinearColor(0.28f, 0.28f, 0.28f, 0.55f), FLinearColor::Transparent, 0.0f, 2.0f), FMargin(0));
		UOverlaySlot* WashSlot = Square->AddChildToOverlay(Wash);
		WashSlot->SetHorizontalAlignment(HAlign_Fill);
		WashSlot->SetVerticalAlignment(VAlign_Fill);
		UBorder* Strip = Box(T, FSlateColorBrush(Info.Rarity), FMargin(0));
		UOverlaySlot* StripSlot = Square->AddChildToOverlay(Sized(T, Strip, 0.0f, 3.0f));
		StripSlot->SetHorizontalAlignment(HAlign_Fill);
		StripSlot->SetVerticalAlignment(VAlign_Bottom);
		if (Info.Icon)
		{
			UImage* Icon = Make<UImage>(T);
			Icon->SetBrushFromTexture(Info.Icon, false);
			UOverlaySlot* IconSlot = Square->AddChildToOverlay(Icon);
			IconSlot->SetHorizontalAlignment(HAlign_Fill);
			IconSlot->SetVerticalAlignment(VAlign_Fill);
			IconSlot->SetPadding(FMargin(4));
		}
		else
		{
			UOverlaySlot* Empty = Square->AddChildToOverlay(Text(T, Info.Kind == TEXT("aslot") || Info.Kind == TEXT("armor") ? TEXT("◇") : TEXT("—"), 22, Dim));
			Empty->SetHorizontalAlignment(HAlign_Center);
			Empty->SetVerticalAlignment(VAlign_Center);
		}
		if (Info.Power > 0 && !bSlot)
		{
			UOverlaySlot* P = Square->AddChildToOverlay(Text(T, FString::FromInt(Info.Power), 11, Ink, true));
			P->SetHorizontalAlignment(HAlign_Right);
			P->SetVerticalAlignment(VAlign_Top);
			P->SetPadding(FMargin(0, 3, 5, 0));
		}
		if (Info.bNew || Info.bEquipped || !Info.Badge.IsEmpty())
		{
			const FString Mark = Info.bEquipped ? TEXT("◆") : (Info.bNew ? TEXT("NEW") : Info.Badge);
			UOverlaySlot* M = Square->AddChildToOverlay(Text(T, Mark, 10, Info.bEquipped ? Cyan : Gold, true));
			M->SetHorizontalAlignment(HAlign_Left);
			M->SetVerticalAlignment(VAlign_Top);
			M->SetPadding(FMargin(5, 3, 0, 0));
		}
		UWidget* Content = Sized(T, Square, IconSize.X, IconSize.Y);
		if (bSlot)
		{
			// slots: the icon with the slot name, what is there and its power / armour beside it
			UHorizontalBox* Row = Make<UHorizontalBox>(T);
			Row->AddChildToHorizontalBox(Content)->SetPadding(FMargin(6));
			UVerticalBox* Lines = Make<UVerticalBox>(T);
			Lines->AddChildToVerticalBox(Text(T, Info.Sub, 10, Dim, true, 180));
			UTextBlock* Name = Text(T, Info.Title, 15, Info.Title.IsEmpty() ? Dim : Info.Rarity, true);
			Name->SetAutoWrapText(true);
			Lines->AddChildToVerticalBox(Name)->SetPadding(FMargin(0, 2, 0, 2));
			if (!Info.Badge.IsEmpty())
			{
				Lines->AddChildToVerticalBox(Text(T, Info.Badge, 12, Gold, true));
			}
			UHorizontalBoxSlot* LinesSlot = Row->AddChildToHorizontalBox(Lines);
			LinesSlot->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
			LinesSlot->SetVerticalAlignment(VAlign_Center);
			LinesSlot->SetPadding(FMargin(8, 4, 10, 4));
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
}

void USOInventoryWidget::BuildTree()
{
	UWidgetTree* T = WidgetTree;
	Root = Make<UCanvasPanel>(T);
	WidgetTree->RootWidget = Root;
	SetIsFocusable(true);

	// the world behind, blurred and darkened to night blue
	UBackgroundBlur* Blur = Make<UBackgroundBlur>(T);
	Blur->SetBlurStrength(10.0f);
	Blur->SetContent(Box(T, FSlateColorBrush(FLinearColor(0.01f, 0.015f, 0.035f, 0.82f)), FMargin(0)));
	UCanvasPanelSlot* BlurSlot = Root->AddChildToCanvas(Blur);
	BlurSlot->SetAnchors(FAnchors(0, 0, 1, 1));
	BlurSlot->SetOffsets(FMargin(0));

	// the character, centre stage, on a glowing ring
	UOverlay* Stage = Make<UOverlay>(T);
	UBorder* Halo = Box(T, Rounded(FLinearColor(0.08f, 0.05f, 0.2f, 0.35f), Violet * FLinearColor(1, 1, 1, 0.25f), 1.0f, 300.0f), FMargin(0));
	UOverlaySlot* HaloSlot = Stage->AddChildToOverlay(Sized(T, Halo, 520.0f, 70.0f));
	HaloSlot->SetHorizontalAlignment(HAlign_Center);
	HaloSlot->SetVerticalAlignment(VAlign_Bottom);
	HaloSlot->SetPadding(FMargin(0, 0, 0, 40));
	PreviewImage = Make<UImage>(T);
	PreviewImage->SetColorAndOpacity(FLinearColor::White);
	UOverlaySlot* ImageSlot = Stage->AddChildToOverlay(PreviewImage);
	ImageSlot->SetHorizontalAlignment(HAlign_Fill);
	ImageSlot->SetVerticalAlignment(VAlign_Fill);
	UVerticalBox* Under = Make<UVerticalBox>(T);
	UButton* BodyButton = Make<UButton>(T);
	StyleButton(BodyButton, Rounded(Glass, Cyan * FLinearColor(1, 1, 1, 0.4f), 1.0f), Rounded(Glass * 1.8f, Cyan, 1.5f), Rounded(Glass * 2.2f, Cyan, 2.0f));
	BodyLabel = Text(T, TEXT("BODY"), 11, Ink, true, 200);
	BodyButton->SetContent(Box(T, FSlateColorBrush(FLinearColor::Transparent), FMargin(16, 6, 16, 6)));
	Cast<UBorder>(BodyButton->GetContent())->SetContent(BodyLabel);
	BodyButton->OnClicked.AddDynamic(this, &USOInventoryWidget::OnBody);
	Under->AddChildToVerticalBox(BodyButton)->SetHorizontalAlignment(HAlign_Center);
	Under->AddChildToVerticalBox(Text(T, TEXT("drag to turn"), 10, Dim))->SetHorizontalAlignment(HAlign_Center);
	UOverlaySlot* UnderSlot = Stage->AddChildToOverlay(Under);
	UnderSlot->SetHorizontalAlignment(HAlign_Center);
	UnderSlot->SetVerticalAlignment(VAlign_Bottom);
	UCanvasPanelSlot* StageSlot = Root->AddChildToCanvas(Stage);
	StageSlot->SetAnchors(FAnchors(0.5f, 0.0f, 0.5f, 1.0f));
	StageSlot->SetOffsets(FMargin(-330.0f, 96.0f, 660.0f, 60.0f));

	// top bar: title, power and the purse
	UHorizontalBox* Top = Make<UHorizontalBox>(T);
	UVerticalBox* Title = Make<UVerticalBox>(T);
	Title->AddChildToVerticalBox(Text(T, TEXT("LOADOUT"), 30, Ink, true, 420));
	Title->AddChildToVerticalBox(Text(T, TEXT("WAYFARER  ·  SHATTERED ORBIT"), 10, Cyan, true, 300));
	Top->AddChildToHorizontalBox(Title);
	UHorizontalBoxSlot* Spacer = Top->AddChildToHorizontalBox(Make<USpacer>(T));
	Spacer->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
	StatsText = Text(T, TEXT(""), 13, Dim, true, 80);
	Top->AddChildToHorizontalBox(StatsText)->SetVerticalAlignment(VAlign_Center);
	UHorizontalBox* PowerBox = Make<UHorizontalBox>(T);
	PowerBox->AddChildToHorizontalBox(Text(T, TEXT("◆"), 22, Gold))->SetVerticalAlignment(VAlign_Center);
	PowerText = Text(T, TEXT("0"), 38, Gold, true);
	PowerBox->AddChildToHorizontalBox(PowerText)->SetPadding(FMargin(6, 0, 0, 0));
	Top->AddChildToHorizontalBox(PowerBox)->SetPadding(FMargin(28, 0, 0, 0));
	UCanvasPanelSlot* TopSlot = Root->AddChildToCanvas(Top);
	TopSlot->SetAnchors(FAnchors(0, 0, 1, 0));
	TopSlot->SetOffsets(FMargin(56.0f, 26.0f, 56.0f, 70.0f));
	UBorder* Rule = Box(T, FSlateColorBrush(Cyan * FLinearColor(1, 1, 1, 0.3f)), FMargin(0));
	UCanvasPanelSlot* RuleSlot = Root->AddChildToCanvas(Rule);
	RuleSlot->SetAnchors(FAnchors(0, 0, 1, 0));
	RuleSlot->SetOffsets(FMargin(56.0f, 100.0f, 56.0f, 1.0f));

	// the columns
	LeftColumn = Make<UVerticalBox>(T);
	UCanvasPanelSlot* LeftSlot = Root->AddChildToCanvas(LeftColumn);
	LeftSlot->SetAnchors(FAnchors(0, 0, 0, 1));
	LeftSlot->SetOffsets(FMargin(56.0f, 118.0f, 390.0f, 60.0f));
	RightColumn = Make<UVerticalBox>(T);
	UCanvasPanelSlot* RightSlot = Root->AddChildToCanvas(RightColumn);
	RightSlot->SetAnchors(FAnchors(1, 0, 1, 1));
	RightSlot->SetOffsets(FMargin(-396.0f, 118.0f, 340.0f, 60.0f));

	// the flyout: a slot's grid and the details of the item under the cursor
	Flyout = Box(T, Rounded(FLinearColor(0.02f, 0.03f, 0.055f, 0.97f), Cyan * FLinearColor(1, 1, 1, 0.45f), 1.2f, 4.0f), FMargin(18, 14, 18, 14));
	UHorizontalBox* FlyRow = Make<UHorizontalBox>(T);
	UVerticalBox* GridColumn = Make<UVerticalBox>(T);
	GridTitle = Text(T, TEXT(""), 12, Ink, true, 240);
	GridColumn->AddChildToVerticalBox(GridTitle)->SetPadding(FMargin(0, 0, 0, 10));
	UScrollBox* GridScroll = Make<UScrollBox>(T);
	Grid = Make<UWrapBox>(T);
	Grid->SetInnerSlotPadding(FVector2D(8.0f, 8.0f));
	GridScroll->AddChild(Grid);
	UVerticalBoxSlot* GridScrollSlot = GridColumn->AddChildToVerticalBox(GridScroll);
	GridScrollSlot->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
	FlyRow->AddChildToHorizontalBox(Sized(T, GridColumn, 420.0f, 0.0f));
	UBorder* Divider = Box(T, FSlateColorBrush(Cyan * FLinearColor(1, 1, 1, 0.2f)), FMargin(0));
	FlyRow->AddChildToHorizontalBox(Sized(T, Divider, 1.0f, 0.0f))->SetPadding(FMargin(16, 0, 16, 0));
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
		StyleButton(Out, Rounded(Color * FLinearColor(0.3f, 0.3f, 0.3f, 0.9f), Color * FLinearColor(1, 1, 1, 0.6f), 1.0f),
			Rounded(Color * FLinearColor(0.5f, 0.5f, 0.5f, 1.0f), Color, 1.5f), Rounded(Color * FLinearColor(0.7f, 0.7f, 0.7f, 1.0f), Color, 2.0f));
		Label = Text(T, Caption, 12, Ink, true, 120);
		Out->SetContent(Box(T, FSlateColorBrush(FLinearColor::Transparent), FMargin(14, 8, 14, 8)));
		Cast<UBorder>(Out->GetContent())->SetContent(Label);
		Actions->AddChildToHorizontalBox(Out)->SetPadding(FMargin(0, 0, 8, 0));
	};
	Action(EquipButton, EquipLabel, TEXT("EQUIP  [E]"), Cyan);
	Action(LockButton, LockLabel, TEXT("LOCK  [L]"), Gold);
	Action(DismantleButton, DismantleLabel, TEXT("DISMANTLE  [X]"), Bad);
	EquipButton->OnClicked.AddDynamic(this, &USOInventoryWidget::OnEquip);
	LockButton->OnClicked.AddDynamic(this, &USOInventoryWidget::OnLock);
	DismantleButton->OnClicked.AddDynamic(this, &USOInventoryWidget::OnDismantle);
	DetailColumn->AddChildToVerticalBox(Actions)->SetPadding(FMargin(0, 12, 0, 0));
	FlyRow->AddChildToHorizontalBox(Sized(T, DetailColumn, 470.0f, 0.0f));
	Flyout->SetContent(FlyRow);
	Flyout->SetVisibility(ESlateVisibility::Collapsed);
	Root->AddChildToCanvas(Flyout);

	// key hints
	UTextBlock* Hints = Text(T, TEXT("Click a slot to open it   ·   E equip   ·   L lock   ·   X dismantle (twice)   ·   drag the character to turn   ·   Esc back / close"), 11, Dim);
	UCanvasPanelSlot* HintSlot = Root->AddChildToCanvas(Hints);
	HintSlot->SetAnchors(FAnchors(0.5f, 1.0f, 0.5f, 1.0f));
	HintSlot->SetAlignment(FVector2D(0.5f, 1.0f));
	HintSlot->SetAutoSize(true);
	HintSlot->SetOffsets(FMargin(0.0f, -18.0f, 0.0f, 0.0f));
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
	Tile.Power = W.Power;
	Tile.bEquipped = Inventory && Inventory->IsEquipped(W.Uid) && !bSlot;
	Tile.bNew = W.bNew;
	Tile.bWide = true;
	Tile.Size = FVector2D(196.0f, 98.0f);
	if (!bSlot && W.bKeep && !Tile.bEquipped && !Tile.bNew)
	{
		Tile.Badge = TEXT("■");
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
	Tile.Size = FVector2D(98.0f, 98.0f);
	if (bSlot && Item)
	{
		Tile.Badge = FString::Printf(TEXT("◇ %d armour"), Item->Armor);
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
	StatsText->SetText(FText::FromString(FString::Printf(TEXT("ARMOUR %d     LEVEL %d     %d CREDITS     %d ALLOY     VAULT %d / %d"), Inventory->GetArmorRating(),
		Inventory->GetLevel(), Inventory->GetCredits(), Inventory->GetAlloy(), Inventory->GetItems().Num(), USOLootLibrary::VaultCap)));
	BodyLabel->SetText(FText::FromString(Inventory->GetBody() == TEXT("female") ? TEXT("BODY  ◂  FEMALE  ▸") : TEXT("BODY  ◂  MALE  ▸")));
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
		Info.Badge = Info.Power > 0 ? FString::Printf(TEXT("◆ %d"), Info.Power) : FString();
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
		return;
	}
	Flyout->SetVisibility(ESlateVisibility::Visible);
	// beside the slot's column, over the stage
	const bool bLeft = IsWeaponSlot(OpenSlotId) || OpenSlotId == TEXT("outer") || OpenSlotId == TEXT("vest");
	if (UCanvasPanelSlot* S = Cast<UCanvasPanelSlot>(Flyout->Slot))
	{
		S->SetAnchors(bLeft ? FAnchors(0, 0, 0, 1) : FAnchors(1, 0, 1, 1));
		S->SetAlignment(FVector2D(bLeft ? 0.0f : 1.0f, 0.0f));
		S->SetOffsets(bLeft ? FMargin(404.0f, 118.0f, 960.0f, 60.0f) : FMargin(-410.0f, 118.0f, 960.0f, 60.0f));
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
	Details->AddChildToVerticalBox(Text(T, W.Name.ToUpper(), 24, Rarity, true, 60));
	Details->AddChildToVerticalBox(Text(T, FString::Printf(TEXT("%s  ·  %s %s"), *RarityName(W.Rarity).ToUpper(), *ClassName(Data).ToUpper(),
		Data ? *Data->DisplayName.ToString().ToUpper() : TEXT("")), 11, Ink, true, 140));
	if (UTexture2D* Icon = Data ? Data->Icon.LoadSynchronous() : nullptr)
	{
		UImage* Big = Make<UImage>(T);
		Big->SetBrushFromTexture(Icon, false);
		UOverlay* Frame = Make<UOverlay>(T);
		Frame->AddChildToOverlay(Box(T, Rounded(Rarity * FLinearColor(0.18f, 0.18f, 0.18f, 0.5f), Rarity * FLinearColor(1, 1, 1, 0.35f), 1.0f), FMargin(0)));
		UOverlaySlot* BigSlot = Frame->AddChildToOverlay(Big);
		BigSlot->SetHorizontalAlignment(HAlign_Fill);
		BigSlot->SetVerticalAlignment(VAlign_Fill);
		Details->AddChildToVerticalBox(Sized(T, Frame, 440.0f, 210.0f))->SetPadding(FMargin(0, 8, 0, 8));
	}
	UHorizontalBox* PowerRow = Make<UHorizontalBox>(T);
	PowerRow->AddChildToHorizontalBox(Text(T, FString::Printf(TEXT("◆ %d"), W.Power), 26, Gold, true));
	const FSOSightInfo* Sight = Tables ? Tables->FindSight(W.Sight) : nullptr;
	UHorizontalBoxSlot* InfoSlot = PowerRow->AddChildToHorizontalBox(Text(T, FString::Printf(TEXT("Rolls %d %%   %s%s"), USOLootLibrary::RollQuality(W),
		Sight ? *Sight->Name.ToString() : TEXT(""), W.Source.IsEmpty() ? TEXT("") : *FString::Printf(TEXT("   ·   %s"), *W.Source)), 12, Dim));
	InfoSlot->SetVerticalAlignment(VAlign_Center);
	InfoSlot->SetPadding(FMargin(14, 0, 0, 0));
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
		Bar->SetPercent(Fill);
		bool bBetter = false, bWorse = false;
		if (bCompare && !FMath::IsNearlyEqual(R.Value, R.Other, FMath::Abs(R.Other) * 0.005f + 0.001f))
		{
			bBetter = R.bLowerBetter ? R.Value < R.Other : R.Value > R.Other;
			bWorse = !bBetter;
		}
		Bar->SetFillColorAndOpacity(bBetter ? Good : bWorse ? Bad : Ink * 0.85f);
		UHorizontalBoxSlot* BarSlot = Line->AddChildToHorizontalBox(Sized(T, Bar, 0.0f, 7.0f));
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
			Row->AddChildToHorizontalBox(Text(T, TEXT("◈"), 16, Violet))->SetPadding(FMargin(0, 0, 10, 0));
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
	Details->AddChildToVerticalBox(Text(T, (Item ? Item->Label.ToString() : A.Item.ToString()).ToUpper(), 22, Rarity, true, 60));
	Details->AddChildToVerticalBox(Text(T, FString::Printf(TEXT("%s  ·  %s ARMOUR"), *RarityName(A.Rarity).ToUpper(),
		*USOWardrobeData::SlotLabel(A.Slot).ToString().ToUpper()), 11, Ink, true, 140));
	if (UTexture2D* Icon = Item ? Item->Icon.LoadSynchronous() : nullptr)
	{
		UImage* Big = Make<UImage>(T);
		Big->SetBrushFromTexture(Icon, false);
		UOverlay* Frame = Make<UOverlay>(T);
		Frame->AddChildToOverlay(Box(T, Rounded(Rarity * FLinearColor(0.18f, 0.18f, 0.18f, 0.5f), Rarity * FLinearColor(1, 1, 1, 0.35f), 1.0f), FMargin(0)));
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
	Details->AddChildToVerticalBox(Text(T, FString::Printf(TEXT("◆ %d     ◇ %d armour%s"), A.Power, Armor, *Compare), 14, Gold, true))->SetPadding(FMargin(0, 0, 0, 10));
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
