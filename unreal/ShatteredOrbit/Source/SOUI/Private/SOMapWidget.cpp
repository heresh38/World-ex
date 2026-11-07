#include "SOMapWidget.h"

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
#include "Components/SizeBox.h"
#include "Components/TextBlock.h"
#include "Components/VerticalBox.h"
#include "Components/VerticalBoxSlot.h"
#include "Engine/TextureRenderTarget2D.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"
#include "SOCharacter.h"
#include "SOMap.h"
#include "SOSound.h"
#include "Styling/CoreStyle.h"

namespace
{
	const FLinearColor Ink(0.88f, 0.92f, 0.97f);
	const FLinearColor Dim(0.48f, 0.54f, 0.64f);
	const FLinearColor Cyan(0.1f, 0.85f, 1.0f);

	FSlateFontInfo MapFont(int32 Size, bool bBold = false, int32 Spacing = 0)
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

	UTextBlock* Label(UWidgetTree* Tree, const FString& Value, int32 Size, const FLinearColor& Color, bool bBold = false, int32 Spacing = 0)
	{
		UTextBlock* T = Make<UTextBlock>(Tree);
		T->SetText(FText::FromString(Value));
		T->SetFont(MapFont(Size, bBold, Spacing));
		T->SetColorAndOpacity(FSlateColor(Color));
		return T;
	}

	void Style(UButton* B, const FLinearColor& Fill, const FLinearColor& Edge)
	{
		FButtonStyle S = B->GetStyle();
		S.SetNormal(FSlateRoundedBoxBrush(Fill, 3.0f, Edge, 1.0f));
		S.SetHovered(FSlateRoundedBoxBrush(Fill * 1.8f, 3.0f, Cyan, 1.5f));
		S.SetPressed(FSlateRoundedBoxBrush(Fill * 2.2f, 3.0f, Cyan, 2.0f));
		S.SetNormalPadding(FMargin(0));
		S.SetPressedPadding(FMargin(0));
		B->SetStyle(S);
	}

	ASOCharacter* Traveller(const UUserWidget* W)
	{
		return W ? Cast<ASOCharacter>(W->GetOwningPlayerPawn()) : nullptr;
	}
}

// --- Marker --------------------------------------------------------------------------------------

void USOMapMarker::Setup(USOMapWidget* InScreen, ASOMapPoint* InPoint)
{
	Screen = InScreen;
	Point = InPoint;
}

TSharedRef<SWidget> USOMapMarker::RebuildWidget()
{
	if (WidgetTree && !WidgetTree->RootWidget && Point.IsValid())
	{
		UWidgetTree* T = WidgetTree;
		const ASOMapPoint* P = Point.Get();
		const FLinearColor C = ASOMapPoint::KindColor(P->Kind);
		UButton* Button = Make<UButton>(T);
		Style(Button, FLinearColor(0.02f, 0.03f, 0.05f, 0.85f), C);
		Button->OnClicked.AddDynamic(this, &USOMapMarker::OnClicked);
		Button->OnHovered.AddDynamic(this, &USOMapMarker::OnHovered);
		UHorizontalBox* Row = Make<UHorizontalBox>(T);
		Row->AddChildToHorizontalBox(Label(T, P->bFastTravel || P->Kind == ESOMapPointKind::AreaTravel ? TEXT("◆") : TEXT("◇"), 13, C, true))
			->SetVerticalAlignment(VAlign_Center);
		Row->AddChildToHorizontalBox(Label(T, P->Label.ToString(), 11, Ink, true))->SetPadding(FMargin(5, 0, 2, 0));
		UBorder* Pad = Make<UBorder>(T);
		Pad->SetBrush(FSlateColorBrush(FLinearColor::Transparent));
		Pad->SetPadding(FMargin(6, 2, 7, 2));
		Pad->SetContent(Row);
		Button->SetContent(Pad);
		WidgetTree->RootWidget = Button;
	}
	return Super::RebuildWidget();
}

void USOMapMarker::OnClicked()
{
	if (Screen && Point.IsValid())
	{
		Screen->TravelTo(Point.Get());
	}
}

void USOMapMarker::OnHovered()
{
	if (Screen && Point.IsValid())
	{
		Screen->ShowInfo(Point.Get());
	}
}

// --- Area button ---------------------------------------------------------------------------------

TSharedRef<SWidget> USOAreaButton::RebuildWidget()
{
	if (WidgetTree && !WidgetTree->RootWidget && ASOMapInfo::Areas().IsValidIndex(Area))
	{
		UWidgetTree* T = WidgetTree;
		UButton* Button = Make<UButton>(T);
		Style(Button, FLinearColor(0.04f, 0.06f, 0.1f, 0.9f), bCurrent ? Cyan : FLinearColor(0.3f, 0.35f, 0.45f));
		Button->OnClicked.AddDynamic(this, &USOAreaButton::OnClicked);
		UVerticalBox* Lines = Make<UVerticalBox>(T);
		Lines->AddChildToVerticalBox(Label(T, ASOMapInfo::Areas()[Area].Name.ToString().ToUpper(), 13, bCurrent ? Cyan : Ink, true, 120));
		Lines->AddChildToVerticalBox(Label(T, bCurrent ? TEXT("You are here") : TEXT("Travel"), 10, Dim));
		UBorder* Pad = Make<UBorder>(T);
		Pad->SetBrush(FSlateColorBrush(FLinearColor::Transparent));
		Pad->SetPadding(FMargin(12, 8, 12, 8));
		Pad->SetContent(Lines);
		Button->SetContent(Pad);
		WidgetTree->RootWidget = Button;
	}
	return Super::RebuildWidget();
}

void USOAreaButton::OnClicked()
{
	if (Screen && !bCurrent)
	{
		Screen->TravelToArea(Area);
	}
}

// --- Screen --------------------------------------------------------------------------------------

TSharedRef<SWidget> USOMapWidget::RebuildWidget()
{
	if (WidgetTree && !WidgetTree->RootWidget)
	{
		BuildTree();
	}
	return Super::RebuildWidget();
}

void USOMapWidget::BuildTree()
{
	UWidgetTree* T = WidgetTree;
	UCanvasPanel* Root = Make<UCanvasPanel>(T);
	WidgetTree->RootWidget = Root;
	SetIsFocusable(true);
	ASOMapInfo* Info = ASOMapInfo::Get(this);

	UBackgroundBlur* Blur = Make<UBackgroundBlur>(T);
	Blur->SetBlurStrength(10.0f);
	UBorder* Shade = Make<UBorder>(T);
	Shade->SetBrush(FSlateColorBrush(FLinearColor(0.01f, 0.015f, 0.035f, 0.88f)));
	Blur->SetContent(Shade);
	UCanvasPanelSlot* BlurSlot = Root->AddChildToCanvas(Blur);
	BlurSlot->SetAnchors(FAnchors(0, 0, 1, 1));
	BlurSlot->SetOffsets(FMargin(0));

	// title
	UVerticalBox* Title = Make<UVerticalBox>(T);
	Title->AddChildToVerticalBox(Label(T, Info ? Info->AreaName.ToString().ToUpper() : TEXT("UNCHARTED"), 30, Ink, true, 420));
	Title->AddChildToVerticalBox(Label(T, TEXT("MAP  ·  QUICK TRAVEL"), 10, Cyan, true, 300));
	UCanvasPanelSlot* TitleSlot = Root->AddChildToCanvas(Title);
	TitleSlot->SetAutoSize(true);
	TitleSlot->SetOffsets(FMargin(56, 26, 0, 0));

	// the map picture with its markers
	UOverlay* Board = Make<UOverlay>(T);
	UBorder* Frame = Make<UBorder>(T);
	Frame->SetBrush(FSlateRoundedBoxBrush(FLinearColor(0.02f, 0.03f, 0.05f, 1.0f), 4.0f, Cyan * FLinearColor(1, 1, 1, 0.5f), 1.5f));
	if (UOverlaySlot* FS = Board->AddChildToOverlay(Frame)) { FS->SetHorizontalAlignment(HAlign_Fill); FS->SetVerticalAlignment(VAlign_Fill); }
	MapImage = Make<UImage>(T);
	if (Info && Info->GetMapTexture())
	{
		MapImage->SetBrushResourceObject(Info->GetMapTexture());
	}
	MapImage->SetColorAndOpacity(FLinearColor(0.8f, 0.85f, 0.95f));
	UOverlaySlot* ImageSlot = Board->AddChildToOverlay(MapImage);
	ImageSlot->SetPadding(FMargin(2));
	ImageSlot->SetHorizontalAlignment(HAlign_Fill);
	ImageSlot->SetVerticalAlignment(VAlign_Fill);
	Markers = Make<UCanvasPanel>(T);
	if (UOverlaySlot* MS = Board->AddChildToOverlay(Markers)) { MS->SetHorizontalAlignment(HAlign_Fill); MS->SetVerticalAlignment(VAlign_Fill); }
	USizeBox* Square = Make<USizeBox>(T);
	Square->SetWidthOverride(MapSize);
	Square->SetHeightOverride(MapSize);
	Square->SetContent(Board);
	UCanvasPanelSlot* BoardSlot = Root->AddChildToCanvas(Square);
	BoardSlot->SetAnchors(FAnchors(0.5f, 0.5f, 0.5f, 0.5f));
	BoardSlot->SetAlignment(FVector2D(0.5f, 0.5f));
	BoardSlot->SetAutoSize(true);
	BoardSlot->SetOffsets(FMargin(-170.0f, 30.0f, 0.0f, 0.0f));

	// every place on the map
	if (Info)
	{
		for (TActorIterator<ASOMapPoint> It(GetWorld()); It; ++It)
		{
			const FVector2D UV = Info->WorldToMap(It->GetActorLocation());
			if (UV.X < 0.0f || UV.X > 1.0f || UV.Y < 0.0f || UV.Y > 1.0f)
			{
				continue;
			}
			USOMapMarker* Marker = CreateWidget<USOMapMarker>(this, USOMapMarker::StaticClass());
			Marker->Setup(this, *It);
			UCanvasPanelSlot* S = Markers->AddChildToCanvas(Marker);
			S->SetAutoSize(true);
			S->SetAlignment(FVector2D(0.5f, 0.5f));
			S->SetPosition(UV * MapSize);
		}
	}
	PlayerMark = Make<UImage>(T);
	PlayerMark->SetBrush(FSlateRoundedBoxBrush(Cyan, 7.0f, FLinearColor::White, 2.0f));
	PlayerMark->SetDesiredSizeOverride(FVector2D(14.0f, 14.0f));
	UCanvasPanelSlot* PlayerSlot = Markers->AddChildToCanvas(PlayerMark);
	PlayerSlot->SetSize(FVector2D(14.0f, 14.0f));
	PlayerSlot->SetAlignment(FVector2D(0.5f, 0.5f));

	// the side panel: what the hovered place is, the legend and the areas
	UVerticalBox* Side = Make<UVerticalBox>(T);
	InfoTitle = Label(T, TEXT("Hover a place"), 18, Ink, true);
	InfoText = Label(T, TEXT("Click a ◆ to quick travel there."), 11, Dim);
	InfoText->SetAutoWrapText(true);
	Side->AddChildToVerticalBox(InfoTitle);
	Side->AddChildToVerticalBox(InfoText)->SetPadding(FMargin(0, 4, 0, 18));
	Side->AddChildToVerticalBox(Label(T, TEXT("LEGEND"), 11, Ink, true, 260))->SetPadding(FMargin(0, 0, 0, 8));
	for (int32 K = 0; K <= static_cast<int32>(ESOMapPointKind::AreaTravel); ++K)
	{
		const ESOMapPointKind Kind = static_cast<ESOMapPointKind>(K);
		UHorizontalBox* Row = Make<UHorizontalBox>(T);
		Row->AddChildToHorizontalBox(Label(T, TEXT("◆"), 12, ASOMapPoint::KindColor(Kind)));
		Row->AddChildToHorizontalBox(Label(T, ASOMapPoint::KindName(Kind).ToString(), 11, Ink))->SetPadding(FMargin(8, 0, 0, 0));
		Side->AddChildToVerticalBox(Row)->SetPadding(FMargin(0, 2, 0, 2));
	}
	Side->AddChildToVerticalBox(Label(T, TEXT("AREAS"), 11, Ink, true, 260))->SetPadding(FMargin(0, 18, 0, 8));
	const FString Here = GetWorld() ? UWorld::RemovePIEPrefix(GetWorld()->GetOutermost()->GetName()) : FString();
	for (int32 A = 0; A < ASOMapInfo::Areas().Num(); ++A)
	{
		USOAreaButton* Button = CreateWidget<USOAreaButton>(this, USOAreaButton::StaticClass());
		Button->Setup(this, A, Here == ASOMapInfo::Areas()[A].Level);
		Side->AddChildToVerticalBox(Button)->SetPadding(FMargin(0, 0, 0, 6));
	}
	USizeBox* SideWidth = Make<USizeBox>(T);
	SideWidth->SetWidthOverride(300.0f);
	SideWidth->SetContent(Side);
	UCanvasPanelSlot* SideSlot = Root->AddChildToCanvas(SideWidth);
	SideSlot->SetAnchors(FAnchors(1, 0, 1, 1));
	SideSlot->SetOffsets(FMargin(-360.0f, 120.0f, 300.0f, 60.0f));

	UTextBlock* Hints = Label(T, TEXT("Click a ◆ to quick travel   ·   an area to travel there   ·   M or Esc close"), 11, Dim);
	UCanvasPanelSlot* HintSlot = Root->AddChildToCanvas(Hints);
	HintSlot->SetAnchors(FAnchors(0.5f, 1.0f, 0.5f, 1.0f));
	HintSlot->SetAlignment(FVector2D(0.5f, 1.0f));
	HintSlot->SetAutoSize(true);
	HintSlot->SetOffsets(FMargin(0.0f, -18.0f, 0.0f, 0.0f));
}

void USOMapWidget::NativeTick(const FGeometry& MyGeometry, float InDeltaTime)
{
	Super::NativeTick(MyGeometry, InDeltaTime);
	const ASOMapInfo* Info = ASOMapInfo::Get(this);
	const APawn* Pawn = GetOwningPlayerPawn();
	if (Info && Pawn && PlayerMark)
	{
		if (UCanvasPanelSlot* S = Cast<UCanvasPanelSlot>(PlayerMark->Slot))
		{
			S->SetPosition(Info->WorldToMap(Pawn->GetActorLocation()) * MapSize);
		}
	}
}

void USOMapWidget::ShowInfo(ASOMapPoint* Point)
{
	if (!Point || !InfoTitle)
	{
		return;
	}
	InfoTitle->SetText(Point->Label);
	InfoTitle->SetColorAndOpacity(FSlateColor(ASOMapPoint::KindColor(Point->Kind)));
	FString Line = ASOMapPoint::KindName(Point->Kind).ToString();
	if (!Point->Subtitle.IsEmpty())
	{
		Line += TEXT("  ·  ") + Point->Subtitle.ToString();
	}
	Line += Point->Kind == ESOMapPointKind::AreaTravel ? TEXT("\nClick to travel to this area.") : (Point->bFastTravel ? TEXT("\nClick to quick travel here.") : TEXT(""));
	InfoText->SetText(FText::FromString(Line));
}

void USOMapWidget::TravelTo(ASOMapPoint* Point)
{
	ASOCharacter* Player = Traveller(this);
	if (!Point || !Player)
	{
		return;
	}
	if (Point->Kind == ESOMapPointKind::AreaTravel && !Point->TravelLevel.IsEmpty())
	{
		USOSoundLibrary::Play2D(this, TEXT("ui_equip"), 0.7f, 0.0f);
		Player->TravelToArea(Point->TravelLevel);
		Close();
		return;
	}
	if (!Point->bFastTravel)
	{
		USOSoundLibrary::Play2D(this, TEXT("ui_deny"), 0.6f, 0.0f);
		return;
	}
	USOSoundLibrary::Play2D(this, TEXT("ui_equip"), 0.7f, 0.0f);
	Player->FastTravel(Point);
	Close();
}

void USOMapWidget::TravelToArea(int32 Area)
{
	ASOCharacter* Player = Traveller(this);
	if (Player && ASOMapInfo::Areas().IsValidIndex(Area))
	{
		USOSoundLibrary::Play2D(this, TEXT("ui_equip"), 0.7f, 0.0f);
		Player->TravelToArea(ASOMapInfo::Areas()[Area].Level);
		Close();
	}
}

void USOMapWidget::Close()
{
	if (OnClose)
	{
		OnClose();
	}
}

FReply USOMapWidget::NativeOnKeyDown(const FGeometry& InGeometry, const FKeyEvent& InKeyEvent)
{
	const FKey Key = InKeyEvent.GetKey();
	if (Key == EKeys::Escape || Key == EKeys::M || Key == EKeys::Gamepad_FaceButton_Right || Key == EKeys::Gamepad_DPad_Down)
	{
		Close();
		return FReply::Handled();
	}
	return Super::NativeOnKeyDown(InGeometry, InKeyEvent);
}
