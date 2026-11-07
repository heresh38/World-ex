#include "SOInventoryWidget.h"

#include "Blueprint/WidgetTree.h"
#include "Brushes/SlateColorBrush.h"
#include "Components/BackgroundBlur.h"
#include "Components/Border.h"
#include "Components/Button.h"
#include "Components/ButtonSlot.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/HorizontalBox.h"
#include "Components/HorizontalBoxSlot.h"
#include "Components/ProgressBar.h"
#include "Components/ScrollBox.h"
#include "Components/ScrollBoxSlot.h"
#include "Components/SizeBox.h"
#include "Components/TextBlock.h"
#include "Components/VerticalBox.h"
#include "Components/VerticalBoxSlot.h"
#include "Framework/Application/SlateApplication.h"
#include "SOInventoryComponent.h"
#include "SOLootLibrary.h"
#include "SOSound.h"
#include "SOWeaponData.h"
#include "Styling/CoreStyle.h"

namespace
{
	const FLinearColor Ink(0.9f, 0.92f, 0.95f);
	const FLinearColor Dim(0.55f, 0.58f, 0.63f);
	const FLinearColor Panel(0.035f, 0.04f, 0.05f, 0.82f);
	const FLinearColor Card(0.07f, 0.08f, 0.095f, 0.92f);
	const FLinearColor CardHover(0.13f, 0.15f, 0.18f, 0.96f);
	const FLinearColor CardSelected(0.18f, 0.2f, 0.25f, 0.98f);
	const FLinearColor Good(0.45f, 0.95f, 0.5f);
	const FLinearColor Bad(1.0f, 0.42f, 0.35f);

	FSlateFontInfo Font(int32 Size, bool bBold = false)
	{
		return FCoreStyle::GetDefaultFontStyle(bBold ? "Bold" : "Regular", Size);
	}

	template <typename T>
	T* Make(UWidgetTree* Tree)
	{
		return Tree->ConstructWidget<T>(T::StaticClass());
	}

	UTextBlock* Text(UWidgetTree* Tree, const FString& Value, int32 Size, const FLinearColor& Color, bool bBold = false)
	{
		UTextBlock* T = Make<UTextBlock>(Tree);
		T->SetText(FText::FromString(Value));
		T->SetFont(Font(Size, bBold));
		T->SetColorAndOpacity(FSlateColor(Color));
		return T;
	}

	UBorder* Box(UWidgetTree* Tree, const FLinearColor& Color, const FMargin& Padding)
	{
		UBorder* B = Make<UBorder>(Tree);
		B->SetBrush(FSlateColorBrush(Color));
		B->SetPadding(Padding);
		return B;
	}

	void StyleButton(UButton* Button, const FLinearColor& Normal, const FLinearColor& Hover, const FLinearColor& Pressed)
	{
		FButtonStyle Style = Button->GetStyle();
		Style.SetNormal(FSlateColorBrush(Normal));
		Style.SetHovered(FSlateColorBrush(Hover));
		Style.SetPressed(FSlateColorBrush(Pressed));
		Style.SetNormalPadding(FMargin(0));
		Style.SetPressedPadding(FMargin(0));
		Button->SetStyle(Style);
	}

	const USOWeaponData* ArchetypeOf(const FSOWeaponInstance& W)
	{
		const USOLootTables* Tables = USOLootLibrary::GetTables();
		return Tables ? Tables->LoadArchetype(W.Archetype) : nullptr;
	}

	FString ClassName(const USOWeaponData* Data)
	{
		if (!Data)
		{
			return FString();
		}
		switch (Data->WeaponClass)
		{
		case ESOWeaponClass::Kinetic: return TEXT("Kinetic");
		case ESOWeaponClass::Horror: return TEXT("Horror");
		default: return TEXT("Energy");
		}
	}
}

// --- Card ------------------------------------------------------------------------------------------

void USOWeaponCardWidget::Setup(USOInventoryWidget* InScreen, const FSOWeaponInstance& W, bool bEquipped, bool bSelected)
{
	Screen = InScreen;
	Uid = W.Uid;
	const USOLootTables* Tables = USOLootLibrary::GetTables();
	const USOWeaponData* Data = ArchetypeOf(W);
	Rarity = Tables ? Tables->GetRarity(W.Rarity).Color : FLinearColor::White;
	Title = W.Name;
	Sub = FString::Printf(TEXT("%s  ·  %s"), *ClassName(Data), Data ? *Data->DisplayName.ToString() : *W.Archetype.ToString());
	Tags = FString(bEquipped ? TEXT("EQUIPPED  ") : TEXT("")) + (W.bNew ? TEXT("NEW  ") : TEXT("")) + (W.bKeep ? TEXT("LOCKED") : TEXT(""));
	Power = W.Power;
	bEquippedCard = bEquipped;
	bSelectedCard = bSelected;
}

TSharedRef<SWidget> USOWeaponCardWidget::RebuildWidget()
{
	if (WidgetTree && !WidgetTree->RootWidget)
	{
		UWidgetTree* T = WidgetTree;
		Button = Make<UButton>(T);
		StyleButton(Button, bSelectedCard ? CardSelected : Card, CardHover, CardSelected);
		Button->OnClicked.AddDynamic(this, &USOWeaponCardWidget::OnClicked);
		Button->OnHovered.AddDynamic(this, &USOWeaponCardWidget::OnHovered);
		UHorizontalBox* Row = Make<UHorizontalBox>(T);
		USizeBox* Stripe = Make<USizeBox>(T);
		Stripe->SetWidthOverride(5.0f);
		Stripe->SetContent(Box(T, Rarity, FMargin(0)));
		Row->AddChildToHorizontalBox(Stripe);
		UVerticalBox* Lines = Make<UVerticalBox>(T);
		Lines->AddChildToVerticalBox(Text(T, Title, 15, Rarity, true));
		Lines->AddChildToVerticalBox(Text(T, Sub, 11, Dim));
		if (!Tags.IsEmpty())
		{
			Lines->AddChildToVerticalBox(Text(T, Tags, 10, bEquippedCard ? FLinearColor(0.4f, 0.85f, 1.0f) : FLinearColor(1.0f, 0.85f, 0.3f), true));
		}
		UHorizontalBoxSlot* LinesSlot = Row->AddChildToHorizontalBox(Lines);
		LinesSlot->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
		LinesSlot->SetPadding(FMargin(10, 6, 6, 6));
		UHorizontalBoxSlot* PowerSlot = Row->AddChildToHorizontalBox(Text(T, FString::FromInt(Power), 18, Ink, true));
		PowerSlot->SetVerticalAlignment(VAlign_Center);
		PowerSlot->SetPadding(FMargin(6, 0, 12, 0));
		if (UButtonSlot* Fill = Cast<UButtonSlot>(Button->SetContent(Row)))
		{
			Fill->SetHorizontalAlignment(HAlign_Fill);
			Fill->SetVerticalAlignment(VAlign_Fill);
			Fill->SetPadding(FMargin(0));
		}
		WidgetTree->RootWidget = Button;
	}
	return Super::RebuildWidget();
}

void USOWeaponCardWidget::OnClicked()
{
	if (Screen)
	{
		Screen->Select(Uid);
	}
}

void USOWeaponCardWidget::OnHovered()
{
	if (Screen)
	{
		Screen->Preview(Uid);
	}
}

// --- Screen ----------------------------------------------------------------------------------------

TSharedRef<SWidget> USOInventoryWidget::RebuildWidget()
{
	if (WidgetTree && !WidgetTree->RootWidget)
	{
		BuildTree();
	}
	return Super::RebuildWidget();
}

void USOInventoryWidget::BuildTree()
{
	UWidgetTree* T = WidgetTree;
	UCanvasPanel* Root = Make<UCanvasPanel>(T);
	WidgetTree->RootWidget = Root;
	SetIsFocusable(true);

	UBackgroundBlur* Blur = Make<UBackgroundBlur>(T);
	Blur->SetBlurStrength(8.0f);
	Blur->SetContent(Box(T, FLinearColor(0.0f, 0.0f, 0.0f, 0.55f), FMargin(0)));
	UCanvasPanelSlot* BlurSlot = Root->AddChildToCanvas(Blur);
	BlurSlot->SetAnchors(FAnchors(0, 0, 1, 1));
	BlurSlot->SetOffsets(FMargin(0));

	UVerticalBox* Page = Make<UVerticalBox>(T);
	UCanvasPanelSlot* PageSlot = Root->AddChildToCanvas(Page);
	PageSlot->SetAnchors(FAnchors(0, 0, 1, 1));
	PageSlot->SetOffsets(FMargin(48, 36, 48, 30));

	// header
	UHorizontalBox* Top = Make<UHorizontalBox>(T);
	Top->AddChildToHorizontalBox(Text(T, TEXT("INVENTORY"), 28, Ink, true));
	Header = Text(T, TEXT(""), 14, Dim);
	UHorizontalBoxSlot* HeaderSlot = Top->AddChildToHorizontalBox(Header);
	HeaderSlot->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
	HeaderSlot->SetHorizontalAlignment(HAlign_Right);
	HeaderSlot->SetVerticalAlignment(VAlign_Bottom);
	Page->AddChildToVerticalBox(Top)->SetPadding(FMargin(0, 0, 0, 16));

	// three slot columns + details
	UHorizontalBox* Main = Make<UHorizontalBox>(T);
	UVerticalBoxSlot* MainSlot = Page->AddChildToVerticalBox(Main);
	MainSlot->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
	Columns.Reset();
	ColumnTitles.Reset();
	for (int32 SlotIndex = 0; SlotIndex < USOInventoryComponent::NumSlots; ++SlotIndex)
	{
		UVerticalBox* Column = Make<UVerticalBox>(T);
		UTextBlock* Title = Text(T, TEXT(""), 13, Dim, true);
		ColumnTitles.Add(Title);
		Column->AddChildToVerticalBox(Title)->SetPadding(FMargin(4, 0, 0, 8));
		UScrollBox* List = Make<UScrollBox>(T);
		Columns.Add(List);
		UVerticalBoxSlot* ListSlot = Column->AddChildToVerticalBox(List);
		ListSlot->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
		USizeBox* Width = Make<USizeBox>(T);
		Width->SetWidthOverride(330.0f);
		Width->SetContent(Column);
		Main->AddChildToHorizontalBox(Width)->SetPadding(FMargin(0, 0, 14, 0));
	}
	UBorder* DetailPanel = Box(T, Panel, FMargin(22, 18, 22, 18));
	UVerticalBox* DetailColumn = Make<UVerticalBox>(T);
	Details = Make<UVerticalBox>(T);
	UVerticalBoxSlot* DetailsSlot = DetailColumn->AddChildToVerticalBox(Details);
	DetailsSlot->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
	// actions
	UHorizontalBox* Actions = Make<UHorizontalBox>(T);
	auto Action = [&](UButton*& Out, TObjectPtr<UTextBlock>* Label, const TCHAR* Caption, const FLinearColor& Color)
	{
		Out = Make<UButton>(T);
		StyleButton(Out, Color * 0.35f, Color * 0.55f, Color * 0.75f);
		UTextBlock* L = Text(T, Caption, 14, Ink, true);
		Out->SetContent(Box(T, FLinearColor::Transparent, FMargin(18, 9, 18, 9)));
		Cast<UBorder>(Out->GetContent())->SetContent(L);
		if (Label)
		{
			*Label = L;
		}
		Actions->AddChildToHorizontalBox(Out)->SetPadding(FMargin(0, 0, 10, 0));
	};
	UButton* Equip = nullptr;
	UButton* Lock = nullptr;
	UButton* Break = nullptr;
	Action(Equip, nullptr, TEXT("EQUIP  [E]"), FLinearColor(0.25f, 0.65f, 1.0f));
	Action(Lock, &LockLabel, TEXT("LOCK  [L]"), FLinearColor(0.8f, 0.65f, 0.25f));
	Action(Break, &DismantleLabel, TEXT("DISMANTLE  [X]"), FLinearColor(0.85f, 0.3f, 0.25f));
	EquipButton = Equip;
	LockButton = Lock;
	DismantleButton = Break;
	EquipButton->OnClicked.AddDynamic(this, &USOInventoryWidget::OnEquip);
	LockButton->OnClicked.AddDynamic(this, &USOInventoryWidget::OnLock);
	DismantleButton->OnClicked.AddDynamic(this, &USOInventoryWidget::OnDismantle);
	DetailColumn->AddChildToVerticalBox(Actions)->SetPadding(FMargin(0, 12, 0, 0));
	DetailPanel->SetContent(DetailColumn);
	UHorizontalBoxSlot* PanelSlot = Main->AddChildToHorizontalBox(DetailPanel);
	PanelSlot->SetSize(FSlateChildSize(ESlateSizeRule::Fill));

	Page->AddChildToVerticalBox(Text(T, TEXT("Click a weapon to select it   ·   E equip   ·   L lock   ·   X dismantle (twice)   ·   1 2 3 / wheel switch   ·   I, Tab or Esc close"), 11, Dim))
		->SetPadding(FMargin(0, 12, 0, 0));
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
		if (const FSOWeaponInstance* Held = Inventory->GetEquipped(Inventory->GetActiveSlot()))
		{
			SelectedUid = Held->Uid;
		}
	}
	Refresh();
}

void USOInventoryWidget::NativeDestruct()
{
	if (Inventory && ChangedHandle.IsValid())
	{
		Inventory->OnChanged.Remove(ChangedHandle);
	}
	Super::NativeDestruct();
}

const FSOWeaponInstance* USOInventoryWidget::Shown() const
{
	if (!Inventory)
	{
		return nullptr;
	}
	const FSOWeaponInstance* P = Inventory->Find(PreviewUid);
	return P ? P : Inventory->Find(SelectedUid);
}

void USOInventoryWidget::Refresh()
{
	if (!Inventory || Columns.Num() == 0 || !WidgetTree)
	{
		return;
	}
	const USOLootTables* Tables = USOLootLibrary::GetTables();
	Header->SetText(FText::FromString(FString::Printf(TEXT("Power %d     Level %d     %d credits     %d alloy     Vault %d / %d"), Inventory->GetPower(),
		Inventory->GetLevel(), Inventory->GetCredits(), Inventory->GetAlloy(), Inventory->GetItems().Num(), USOLootLibrary::VaultCap)));
	TArray<TArray<const FSOWeaponInstance*>> BySlot;
	BySlot.SetNum(USOInventoryComponent::NumSlots);
	for (const FSOWeaponInstance& W : Inventory->GetItems())
	{
		const USOWeaponData* Data = ArchetypeOf(W);
		BySlot[Data ? FMath::Clamp(Data->Slot, 0, 2) : 0].Add(&W);
	}
	for (int32 Col = 0; Col < Columns.Num(); ++Col)
	{
		TArray<const FSOWeaponInstance*>& List = BySlot[Col];
		List.Sort([this](const FSOWeaponInstance& A, const FSOWeaponInstance& B)
		{
			const bool EA = Inventory->IsEquipped(A.Uid), EB = Inventory->IsEquipped(B.Uid);
			if (EA != EB) return EA;
			if (A.bNew != B.bNew) return A.bNew;
			if (A.Rarity != B.Rarity) return A.Rarity > B.Rarity;
			return A.Power > B.Power;
		});
		const FString Name = Tables && Tables->SlotNames.IsValidIndex(Col) ? Tables->SlotNames[Col].ToString() : FString::Printf(TEXT("Slot %d"), Col + 1);
		ColumnTitles[Col]->SetText(FText::FromString(FString::Printf(TEXT("%d  %s  (%d)"), Col + 1, *Name.ToUpper(), List.Num())));
		ColumnTitles[Col]->SetColorAndOpacity(FSlateColor(Col == Inventory->GetActiveSlot() ? Ink : Dim));
		UScrollBox* Column = Columns[Col];
		const float Scroll = Column->GetScrollOffset();
		Column->ClearChildren();
		for (const FSOWeaponInstance* W : List)
		{
			USOWeaponCardWidget* CardWidget = CreateWidget<USOWeaponCardWidget>(this, USOWeaponCardWidget::StaticClass());
			CardWidget->Setup(this, *W, Inventory->IsEquipped(W->Uid), W->Uid == SelectedUid);
			Column->AddChild(CardWidget);
			if (UPanelSlot* PanelSlot = CardWidget->Slot)
			{
				if (UScrollBoxSlot* S = Cast<UScrollBoxSlot>(PanelSlot))
				{
					S->SetPadding(FMargin(0, 0, 0, 6));
				}
			}
		}
		Column->SetScrollOffset(Scroll);
	}
	FillDetails();
}

void USOInventoryWidget::FillDetails()
{
	if (!Details || !WidgetTree)
	{
		return;
	}
	UWidgetTree* T = WidgetTree;
	Details->ClearChildren();
	const FSOWeaponInstance* W = Shown();
	const USOLootTables* Tables = USOLootLibrary::GetTables();
	if (!W || !Tables)
	{
		Details->AddChildToVerticalBox(Text(T, TEXT("Select a weapon"), 16, Dim));
		return;
	}
	const USOWeaponData* Data = ArchetypeOf(*W);
	const FSORarityInfo& Rarity = Tables->GetRarity(W->Rarity);
	Details->AddChildToVerticalBox(Text(T, W->Name, 30, Rarity.Color, true));
	Details->AddChildToVerticalBox(Text(T, FString::Printf(TEXT("%s  %s  ·  %s"), *Rarity.Name.ToString(), *ClassName(Data), Data ? *Data->DisplayName.ToString() : TEXT("")), 14, Ink));
	const FSOSightInfo* Sight = Tables->FindSight(W->Sight);
	Details->AddChildToVerticalBox(Text(T, FString::Printf(TEXT("Power %d     Rolls %d %%     %s%s"), W->Power, USOLootLibrary::RollQuality(*W),
		Sight ? *Sight->Name.ToString() : TEXT(""), W->Source.IsEmpty() ? TEXT("") : *FString::Printf(TEXT("     From: %s"), *W->Source)), 13, Dim))
		->SetPadding(FMargin(0, 4, 0, 14));

	// stats against the equipped copy of the same slot
	const FSOWeaponStats S = USOLootLibrary::ComputeStats(*W);
	const FSOWeaponInstance* Equipped = Data && Inventory ? Inventory->GetEquipped(FMath::Clamp(Data->Slot, 0, 2)) : nullptr;
	const bool bCompare = Equipped && Equipped->Uid != W->Uid;
	const FSOWeaponStats E = bCompare ? USOLootLibrary::ComputeStats(*Equipped) : S;
	const int32 Pellets = Data ? FMath::Max(1, Data->Pellets) : 1;
	struct FRow { const TCHAR* Name; float Value, Other, Max; FString Shown; bool bLowerBetter; };
	const FRow Rows[] = {
		{ TEXT("Damage"), S.Damage * Pellets, E.Damage * Pellets, 450.0f, Pellets > 1 ? FString::Printf(TEXT("%.0f x %d"), S.Damage, Pellets) : FString::Printf(TEXT("%.0f"), S.Damage), false },
		{ TEXT("Fire rate"), S.Rpm, E.Rpm, 1100.0f, FString::Printf(TEXT("%.0f rpm"), S.Rpm), false },
		{ TEXT("Magazine"), (float)S.Mag, (float)E.Mag, 150.0f, FString::FromInt(S.Mag), false },
		{ TEXT("Reload"), S.Reload, E.Reload, 4.0f, FString::Printf(TEXT("%.2f s"), S.Reload), true },
		{ TEXT("Range"), S.Range, E.Range, 180.0f, FString::Printf(TEXT("%.0f m"), S.Range), false },
		{ TEXT("Accuracy"), S.Spread, E.Spread, 7.0f, FString::Printf(TEXT("%.2f deg"), S.Spread), true },
		{ TEXT("Zoom"), S.Zoom, E.Zoom, 8.0f, FString::Printf(TEXT("%.2fx"), S.Zoom), false },
	};
	for (const FRow& R : Rows)
	{
		UHorizontalBox* Line = Make<UHorizontalBox>(T);
		USizeBox* NameBox = Make<USizeBox>(T);
		NameBox->SetWidthOverride(110.0f);
		NameBox->SetContent(Text(T, R.Name, 13, Dim));
		Line->AddChildToHorizontalBox(NameBox);
		UProgressBar* Bar = Make<UProgressBar>(T);
		const float Fill = R.bLowerBetter ? 1.0f - FMath::Clamp(R.Value / R.Max, 0.0f, 0.95f) : FMath::Clamp(R.Value / R.Max, 0.03f, 1.0f);
		Bar->SetPercent(Fill);
		Bar->SetFillColorAndOpacity(Ink * 0.85f);
		USizeBox* BarBox = Make<USizeBox>(T);
		BarBox->SetHeightOverride(8.0f);
		BarBox->SetContent(Bar);
		UHorizontalBoxSlot* BarSlot = Line->AddChildToHorizontalBox(BarBox);
		BarSlot->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
		BarSlot->SetVerticalAlignment(VAlign_Center);
		USizeBox* ValueBox = Make<USizeBox>(T);
		ValueBox->SetWidthOverride(110.0f);
		ValueBox->SetContent(Text(T, R.Shown, 13, Ink, true));
		Line->AddChildToHorizontalBox(ValueBox)->SetPadding(FMargin(12, 0, 0, 0));
		FString Delta;
		FLinearColor DeltaColor = Dim;
		if (bCompare && !FMath::IsNearlyEqual(R.Value, R.Other, FMath::Abs(R.Other) * 0.005f + 0.001f))
		{
			const bool bBetter = R.bLowerBetter ? R.Value < R.Other : R.Value > R.Other;
			Delta = FString::Printf(TEXT("%s%.0f %%"), R.Value > R.Other ? TEXT("+") : TEXT(""), (R.Value / FMath::Max(R.Other, 0.001f) - 1.0f) * 100.0f);
			DeltaColor = bBetter ? Good : Bad;
		}
		USizeBox* DeltaBox = Make<USizeBox>(T);
		DeltaBox->SetWidthOverride(70.0f);
		DeltaBox->SetContent(Text(T, Delta, 12, DeltaColor, true));
		Line->AddChildToHorizontalBox(DeltaBox);
		Details->AddChildToVerticalBox(Line)->SetPadding(FMargin(0, 3, 0, 3));
	}
	if (bCompare)
	{
		Details->AddChildToVerticalBox(Text(T, FString::Printf(TEXT("Compared with %s (equipped)"), *Equipped->Name), 11, Dim))->SetPadding(FMargin(0, 6, 0, 0));
	}

	// perks
	Details->AddChildToVerticalBox(Text(T, W->Perks.Num() > 0 ? TEXT("PERKS") : TEXT("NO PERKS"), 13, Dim, true))->SetPadding(FMargin(0, 18, 0, 6));
	for (const FName& PerkId : W->Perks)
	{
		if (const FSOPerkInfo* Perk = Tables->FindPerk(PerkId))
		{
			Details->AddChildToVerticalBox(Text(T, Perk->Name.ToString(), 15, Ink, true));
			UTextBlock* Desc = Text(T, Perk->Description.ToString(), 12, Dim);
			Desc->SetAutoWrapText(true);
			Details->AddChildToVerticalBox(Desc)->SetPadding(FMargin(0, 0, 0, 8));
		}
	}

	// actions reflect the shown copy
	const bool bEquipped = Inventory->IsEquipped(W->Uid);
	EquipButton->SetIsEnabled(!bEquipped);
	LockLabel->SetText(FText::FromString(W->bKeep ? TEXT("UNLOCK  [L]") : TEXT("LOCK  [L]")));
	DismantleButton->SetIsEnabled(!bEquipped && !W->bKeep);
	const bool bArmed = FPlatformTime::Seconds() - DismantleArmedAt < 2.5;
	DismantleLabel->SetText(FText::FromString(bArmed ? FString::Printf(TEXT("CONFIRM  +%d ALLOY"), USOLootLibrary::DismantleAlloy(*W))
		: FString::Printf(TEXT("DISMANTLE  [X]  +%d"), USOLootLibrary::DismantleAlloy(*W))));
}

void USOInventoryWidget::Select(const FString& Uid)
{
	SelectedUid = Uid;
	PreviewUid.Reset();
	DismantleArmedAt = -100.0;
	if (Inventory)
	{
		if (const FSOWeaponInstance* W = Inventory->Find(Uid); W && W->bNew)
		{
			Inventory->ServerMarkSeen(Uid);
		}
	}
	USOSoundLibrary::Play2D(this, TEXT("ui_move"), 0.5f, 0.0f);
	Refresh();
}

void USOInventoryWidget::Preview(const FString& Uid)
{
	if (PreviewUid != Uid)
	{
		PreviewUid = Uid;
		FillDetails();
	}
}

void USOInventoryWidget::OnEquip()
{
	if (const FSOWeaponInstance* W = Inventory ? Inventory->Find(SelectedUid) : nullptr; W && !Inventory->IsEquipped(W->Uid))
	{
		Inventory->ServerEquip(W->Uid);
		USOSoundLibrary::Play2D(this, TEXT("ui_equip"), 0.7f, 0.0f);
	}
}

void USOInventoryWidget::OnLock()
{
	if (const FSOWeaponInstance* W = Inventory ? Inventory->Find(SelectedUid) : nullptr)
	{
		Inventory->ServerSetKeep(W->Uid, !W->bKeep);
		USOSoundLibrary::Play2D(this, TEXT("ui_lock"), 0.6f, 0.0f);
	}
}

void USOInventoryWidget::OnDismantle()
{
	const FSOWeaponInstance* W = Inventory ? Inventory->Find(SelectedUid) : nullptr;
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
	SelectedUid.Reset();
	PreviewUid.Reset();
	USOSoundLibrary::Play2D(this, TEXT("ui_dismantle"), 0.7f, 0.0f);
}

void USOInventoryWidget::Close()
{
	if (OnClose)
	{
		OnClose();
	}
}

FReply USOInventoryWidget::NativeOnKeyDown(const FGeometry& InGeometry, const FKeyEvent& InKeyEvent)
{
	const FKey Key = InKeyEvent.GetKey();
	if (Key == EKeys::Escape || Key == EKeys::I || Key == EKeys::Tab || Key == EKeys::Gamepad_Special_Left || Key == EKeys::Gamepad_FaceButton_Right)
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
