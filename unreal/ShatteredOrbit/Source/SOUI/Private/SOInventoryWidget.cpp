#include "SOInventoryWidget.h"

#include "Blueprint/WidgetTree.h"
#include "Brushes/SlateColorBrush.h"
#include "Brushes/SlateNoResource.h"
#include "Brushes/SlateRoundedBoxBrush.h"
#include "Components/Border.h"
#include "Components/Button.h"
#include "Components/ButtonSlot.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/HorizontalBox.h"
#include "Components/HorizontalBoxSlot.h"
#include "Components/Image.h"
#include "Components/Overlay.h"
#include "Components/PanelWidget.h"
#include "Components/OverlaySlot.h"
#include "Components/PointLightComponent.h"
#include "Components/SceneCaptureComponent2D.h"
#include "Components/ScrollBox.h"
#include "Components/SizeBox.h"
#include "Components/Spacer.h"
#include "Components/TextBlock.h"
#include "Components/VerticalBox.h"
#include "Components/VerticalBoxSlot.h"
#include "Components/WrapBox.h"
#include "Engine/PointLight.h"
#include "Engine/SceneCapture2D.h"
#include "Engine/Texture2D.h"
#include "Engine/TextureRenderTarget2D.h"
#include "Engine/World.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "HAL/IConsoleManager.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Engine/SkeletalMesh.h"
#include "SOAttributes.h"
#include "SOCharacter.h"
#include "SOCreator.h"
#include "SOInventoryComponent.h"
#include "SOJournal.h"
#include "SOLootLibrary.h"
#include "SOMelee.h"
#include "SOProgression.h"
#include "SOSound.h"
#include "SOWardrobe.h"
#include "SOWeaponData.h"
#include "Styling/CoreStyle.h"

// The armoury's look: night blue glass over the stage's light, cyan for what is chosen and lit, gold for power and the
// traits, each item in its rarity's light. Every shape is drawn by its own material (/Game/UI, import_assets.ui_shape).
namespace
{
	const FLinearColor Ink(0.90f, 0.93f, 0.97f);
	const FLinearColor Soft(0.42f, 0.48f, 0.58f);
	const FLinearColor Dim(0.20f, 0.24f, 0.31f);
	const FLinearColor Faint(1.0f, 1.0f, 1.0f, 0.10f);
	const FLinearColor Cyan(0.25f, 0.85f, 1.0f);
	const FLinearColor Gold(0.95f, 0.58f, 0.14f);
	const FLinearColor Good(0.42f, 0.95f, 0.55f);
	const FLinearColor Bad(1.0f, 0.40f, 0.34f);
	/** A blade's light in the armoury (the Sarketh's orange); the bare hands' a cold steel. */
	const FLinearColor BladeLight(1.0f, 0.42f, 0.08f);
	const FLinearColor Steel(0.30f, 0.42f, 0.58f);

	const TCHAR* const FaceRegular = TEXT("Regular");
	const TCHAR* const FaceBold = TEXT("Bold");
	const TCHAR* const FaceCond = TEXT("BoldCondensed");
	const TCHAR* const FaceItalic = TEXT("Italic");

	// The layout, in the screen's 1920 x 1080 units (UMG scales them to the window): the banner over everything, the
	// arsenal / list on the left, the armour / inspect panel on the right, the attributes beside the stage, the tab bar
	// at the foot; the character in the middle, the picture StageHeight tall from StageTop, its feet on the platform.
	constexpr float Margin = 56.0f;
	constexpr float PanelTop = 122.0f;
	constexpr float PanelBottom = 84.0f;
	constexpr float PanelWidth = 444.0f;
	constexpr float StageTop = 46.0f;
	constexpr float StageHeight = 1010.0f;
	constexpr float StageWidth = StageHeight * 0.75f;
	constexpr float FootY = StageTop + StageHeight * USOCharacterPreview::FeetInPicture;
	constexpr float BannerY = 53.0f;
	constexpr float FooterRuleY = 1010.0f;
	constexpr float HintY = 1046.0f;
	/** An armoury's column, the gap after it, the gap between the grid's cells, the rows of a page (grid, list). */
	constexpr float CatWidth = 236.0f;
	constexpr float ColumnGap = 22.0f;
	constexpr float CellGap = 10.0f;
	constexpr int32 GridRows = 5;
	constexpr int32 ListRows = 11;

	FSlateFontInfo Font(int32 Size, const TCHAR* Face = FaceRegular, int32 Spacing = 0)
	{
		FSlateFontInfo F = FCoreStyle::GetDefaultFontStyle(Face, Size);
		F.LetterSpacing = Spacing;
		return F;
	}

	template <typename T>
	T* Make(UWidgetTree* Tree)
	{
		return Tree->ConstructWidget<T>(T::StaticClass());
	}

	FLinearColor Alpha(const FLinearColor& C, float A)
	{
		return FLinearColor(C.R, C.G, C.B, A);
	}

	UTextBlock* Text(UWidgetTree* Tree, const FString& Value, int32 Size, const FLinearColor& Color, const TCHAR* Face = FaceRegular, int32 Spacing = 0)
	{
		UTextBlock* T = Make<UTextBlock>(Tree);
		T->SetText(FText::FromString(Value));
		T->SetFont(Font(Size, Face, Spacing));
		T->SetColorAndOpacity(FSlateColor(Color));
		return T;
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

	void StyleButton(UButton* Button, const FSlateBrush& Normal, const FSlateBrush& Hover, const FSlateBrush& Pressed, const FSlateBrush* Disabled = nullptr)
	{
		FButtonStyle Style = Button->GetStyle();
		Style.SetNormal(Normal);
		Style.SetHovered(Hover);
		Style.SetPressed(Pressed);
		Style.SetDisabled(Disabled ? *Disabled : Normal);
		Style.SetNormalPadding(FMargin(0));
		Style.SetPressedPadding(FMargin(0));
		Button->SetStyle(Style);
	}

	UMaterialInstanceDynamic* Instance(UObject* Outer, const TCHAR* Name)
	{
		UMaterialInterface* Base = Cast<UMaterialInterface>(FSoftObjectPath(FString::Printf(TEXT("/Game/UI/%s.%s"), Name, Name)).TryLoad());
		return Base ? UMaterialInstanceDynamic::Create(Base, Outer) : nullptr;
	}

	FSlateBrush MaterialBrush(UMaterialInstanceDynamic* MID, const FVector2D& Size = FVector2D(32.0f, 32.0f))
	{
		FSlateBrush Brush;
		Brush.SetResourceObject(MID);
		Brush.DrawAs = ESlateBrushDrawType::Image;
		Brush.ImageSize = Size;
		Brush.TintColor = FSlateColor(FLinearColor::White);
		return Brush;
	}

	/** The game's panel (M_UI_Plate): a rectangle with two cut corners, a hairline, a fill that deepens downwards, an
	 *  accent bar on the left and / or along the bottom, a wash of the accent rising from the bottom. */
	struct FPlate
	{
		FLinearColor Fill = FLinearColor(0.007f, 0.010f, 0.020f, 0.92f);
		FLinearColor FillLow = FLinearColor(0.004f, 0.006f, 0.012f, 0.94f);
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
		UMaterialInstanceDynamic* MID = Instance(Outer, TEXT("M_UI_Plate"));
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
		return MaterialBrush(MID);
	}

	/** An armoury card (M_UI_Card): the rarity's light rising in it and glowing behind the picture at GlowX. */
	FSlateBrush CardBrush(UObject* Outer, const FLinearColor& Rarity, float Hover, float Chosen, bool bEmpty, float GlowX, float Glow)
	{
		UMaterialInstanceDynamic* MID = Instance(Outer, TEXT("M_UI_Card"));
		if (!MID)
		{
			return FSlateRoundedBoxBrush(FLinearColor(0.03f, 0.045f, 0.08f, 0.93f), 3.0f, Alpha(Rarity, 0.35f + 0.65f * FMath::Clamp(FMath::Max(Hover, Chosen), 0.0f, 1.0f)), 1.0f + Chosen);
		}
		MID->SetVectorParameterValue(TEXT("Rarity"), Alpha(Rarity, 1.0f));
		MID->SetVectorParameterValue(TEXT("State"), FLinearColor(Hover, Chosen, 0.0f, bEmpty ? 1.0f : 0.0f));
		MID->SetVectorParameterValue(TEXT("Shape"), FLinearColor(16.0f, GlowX, Glow, 6.0f));
		return MaterialBrush(MID);
	}

	/** One of the armoury's glyphs of light (M_UI_Glyph: 0 the emblem, 1 credits, 2 alloy, 3 the vault, 4 power, 5 .. 10
	 *  the six attributes, 11 the fists, 12 a lock, 13 a blade). */
	UWidget* Glyph(UWidgetTree* T, UObject* Outer, int32 Which, const FLinearColor& Color, float Size)
	{
		UImage* I = Make<UImage>(T);
		if (UMaterialInstanceDynamic* MID = Instance(Outer, TEXT("M_UI_Glyph")))
		{
			MID->SetVectorParameterValue(TEXT("Color"), Color);
			MID->SetVectorParameterValue(TEXT("Glyph"), FLinearColor(static_cast<float>(Which), 0.0f, 0.0f, 0.0f));
			I->SetBrush(MaterialBrush(MID, FVector2D(Size, Size)));
		}
		else
		{
			I->SetBrush(FSlateRoundedBoxBrush(Alpha(Color, 0.6f), Size * 0.25f));      // (a dot until the materials are imported)
		}
		I->SetVisibility(ESlateVisibility::HitTestInvisible);
		return Sized(T, I, Size, Size);
	}

	/** A perk's node (M_UI_Hex): a hexagon of light with a glyph in it (0 .. 7). */
	UWidget* Hex(UWidgetTree* T, UObject* Outer, int32 Which, const FLinearColor& Color, float Size, float Lit = 1.0f)
	{
		UImage* I = Make<UImage>(T);
		if (UMaterialInstanceDynamic* MID = Instance(Outer, TEXT("M_UI_Hex")))
		{
			MID->SetVectorParameterValue(TEXT("Color"), Alpha(Color, 1.0f));
			MID->SetVectorParameterValue(TEXT("Glyph"), FLinearColor(static_cast<float>(Which), Lit, 0.0f, 0.0f));
			I->SetBrush(MaterialBrush(MID, FVector2D(Size, Size)));
		}
		else
		{
			I->SetBrush(FSlateRoundedBoxBrush(Alpha(Color, 0.5f), Size * 0.3f));
		}
		I->SetVisibility(ESlateVisibility::HitTestInvisible);
		return Sized(T, I, Size, Size);
	}

	/** A stat's bar (M_UI_StatBar): the value in segments, what it gains or loses against Compare. */
	UImage* StatBar(UWidgetTree* T, UObject* Outer, float Value, float Compare, int32 Segments, const FLinearColor& FillColor)
	{
		UImage* I = Make<UImage>(T);
		if (UMaterialInstanceDynamic* MID = Instance(Outer, TEXT("M_UI_StatBar")))
		{
			MID->SetVectorParameterValue(TEXT("Values"), FLinearColor(FMath::Clamp(Value, 0.0f, 1.0f), FMath::Clamp(Compare, 0.0f, 1.0f), static_cast<float>(Segments), 0.0f));
			MID->SetVectorParameterValue(TEXT("Fill"), FillColor);
			I->SetBrush(MaterialBrush(MID, FVector2D(100.0f, 8.0f)));
		}
		else
		{
			I->SetBrush(FSlateColorBrush(Alpha(FillColor, 0.5f)));
		}
		I->SetVisibility(ESlateVisibility::HitTestInvisible);
		return I;
	}

	/** A section's head: a short bar of light, the title, a hairline to the far side, a figure at its end. */
	UWidget* Header(UWidgetTree* T, const FString& Title, const FString& Right = FString(), const FLinearColor& Accent = Cyan)
	{
		UHorizontalBox* Row = Make<UHorizontalBox>(T);
		Row->AddChildToHorizontalBox(Sized(T, Box(T, FSlateColorBrush(Accent), FMargin(0)), 3.0f, 13.0f))->SetVerticalAlignment(VAlign_Center);
		UHorizontalBoxSlot* Name = Row->AddChildToHorizontalBox(Text(T, Title, 11, Ink, FaceBold, 320));
		Name->SetPadding(FMargin(10, 0, 14, 0));
		Name->SetVerticalAlignment(VAlign_Center);
		UHorizontalBoxSlot* Line = Row->AddChildToHorizontalBox(Sized(T, Box(T, FSlateColorBrush(Faint), FMargin(0)), 0.0f, 1.0f));
		Line->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
		Line->SetVerticalAlignment(VAlign_Center);
		if (!Right.IsEmpty())
		{
			UHorizontalBoxSlot* R = Row->AddChildToHorizontalBox(Text(T, Right, 9, Dim, FaceBold, 220));
			R->SetPadding(FMargin(14, 0, 0, 0));
			R->SetVerticalAlignment(VAlign_Center);
		}
		return Row;
	}

	/** The rule under a name: a short bar in its colour and a hairline on to the edge. */
	UWidget* Rule(UWidgetTree* T, const FLinearColor& Color)
	{
		UHorizontalBox* Row = Make<UHorizontalBox>(T);
		Row->AddChildToHorizontalBox(Sized(T, Box(T, FSlateColorBrush(Alpha(Color, 1.0f)), FMargin(0)), 64.0f, 3.0f))->SetVerticalAlignment(VAlign_Center);
		UHorizontalBoxSlot* Line = Row->AddChildToHorizontalBox(Sized(T, Box(T, FSlateColorBrush(Alpha(Color, 0.18f)), FMargin(0)), 0.0f, 1.0f));
		Line->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
		Line->SetVerticalAlignment(VAlign_Center);
		return Row;
	}

	UWidget* KeyCap(UWidgetTree* T, const FString& Key)
	{
		UBorder* Cap = Box(T, FSlateRoundedBoxBrush(FLinearColor(1.0f, 1.0f, 1.0f, 0.06f), 3.0f, FLinearColor(1.0f, 1.0f, 1.0f, 0.34f), 1.0f), FMargin(6, 1, 6, 2));
		Cap->SetHorizontalAlignment(HAlign_Center);
		Cap->SetContent(Text(T, Key, 9, Ink, FaceBold));
		return Sized(T, Cap, Key.Len() > 2 ? 0.0f : 22.0f, 0.0f);
	}

	/** A key cap and what the key does. */
	UWidget* Hint(UWidgetTree* T, const FString& Key, const FString& Label)
	{
		UHorizontalBox* Row = Make<UHorizontalBox>(T);
		Row->AddChildToHorizontalBox(KeyCap(T, Key))->SetVerticalAlignment(VAlign_Center);
		UHorizontalBoxSlot* L = Row->AddChildToHorizontalBox(Text(T, Label, 9, Soft, FaceBold, 200));
		L->SetVerticalAlignment(VAlign_Center);
		L->SetPadding(FMargin(8, 0, 22, 0));
		return Row;
	}

	FScrollBarStyle ThinBar()
	{
		FScrollBarStyle Bar = FCoreStyle::Get().GetWidgetStyle<FScrollBarStyle>("ScrollBar");
		Bar.SetVerticalBackgroundImage(FSlateColorBrush(FLinearColor(1.0f, 1.0f, 1.0f, 0.03f)));
		Bar.SetVerticalTopSlotImage(FSlateNoResource());
		Bar.SetVerticalBottomSlotImage(FSlateNoResource());
		Bar.SetNormalThumbImage(FSlateRoundedBoxBrush(FLinearColor(1.0f, 1.0f, 1.0f, 0.2f), 2.0f));
		Bar.SetHoveredThumbImage(FSlateRoundedBoxBrush(Alpha(Cyan, 0.6f), 2.0f));
		Bar.SetDraggedThumbImage(FSlateRoundedBoxBrush(Alpha(Cyan, 0.9f), 2.0f));
		Bar.SetThickness(3.0f);
		return Bar;
	}

	UScrollBox* Scroll(UWidgetTree* T)
	{
		UScrollBox* S = Make<UScrollBox>(T);
		S->SetWidgetBarStyle(ThinBar());
		S->SetScrollbarThickness(FVector2D(3.0f, 3.0f));
		S->SetScrollbarPadding(FMargin(6, 0, 0, 0));
		return S;
	}

	const USOWeaponData* ArchetypeOf(const FSOWeaponInstance& W)
	{
		const USOLootTables* Tables = USOLootLibrary::GetTables();
		return Tables ? Tables->LoadArchetype(W.Archetype) : nullptr;
	}

	/** The class as the armoury names it (Light, Ballistic, Living: game_data.json "classNames"). */
	FString ClassName(const USOWeaponData* Data)
	{
		if (!Data) return FString();
		if (!Data->ClassName.IsEmpty()) return Data->ClassName.ToString();
		switch (Data->WeaponClass)
		{
		case ESOWeaponClass::Kinetic: return TEXT("Ballistic");
		case ESOWeaponClass::Horror: return TEXT("Living");
		default: return TEXT("Light");
		}
	}

	FString KindName(const USOWeaponData* Data)
	{
		return Data ? Data->DisplayName.ToString() : FString();
	}

	/** A gun's own light: its set's glow (one palette a set), brought to full brightness; cyan without one. */
	FLinearColor GunLight(const USOWeaponData* Data)
	{
		if (Data)
		{
			const FLinearColor C = Data->GlowColor;
			const float M = FMath::Max3(C.R, C.G, C.B);
			if (M > 0.01f)
			{
				return FLinearColor(C.R / M, C.G / M, C.B / M, 1.0f);
			}
		}
		return Cyan;
	}

	FLinearColor RarityColor(int32 Rarity)
	{
		const USOLootTables* Tables = USOLootLibrary::GetTables();
		return Tables ? Alpha(Tables->GetRarity(Rarity).Color, 1.0f) : FLinearColor::White;
	}

	FString RarityName(int32 Rarity)
	{
		const USOLootTables* Tables = USOLootLibrary::GetTables();
		return Tables ? Tables->GetRarity(Rarity).Name.ToString() : FString();
	}

	FString SlotName(int32 SlotId)
	{
		const USOLootTables* Tables = USOLootLibrary::GetTables();
		return Tables && Tables->SlotNames.IsValidIndex(SlotId) ? Tables->SlotNames[SlotId].ToString() : FString::Printf(TEXT("Slot %d"), SlotId + 1);
	}

	FString Number(int32 Value)
	{
		return FText::AsNumber(Value).ToString();
	}

	/** A perk's glyph in its hexagon: the same perk always the same (0 .. 6; 7 is the trait's). */
	int32 PerkGlyph(FName Perk)
	{
		return static_cast<int32>(GetTypeHash(Perk) % 7u);
	}

	/** Words that must stay in their box: cut with an ellipsis rather than run out of it. */
	UTextBlock* Fit(UTextBlock* T)
	{
		T->SetTextOverflowPolicy(ETextOverflowPolicy::Ellipsis);
		T->SetClipping(EWidgetClipping::ClipToBounds);         // (Slate draws the ellipsis only where the words are clipped)
		return T;
	}

	/** A collected item's kind: its id in the data, its name on the screen (one, many), its glyph where it has no picture. */
	FString GoodsKindId(ESOGoodsKind Kind)
	{
		switch (Kind)
		{
		case ESOGoodsKind::Consumable: return TEXT("consumable");
		case ESOGoodsKind::Key: return TEXT("key");
		case ESOGoodsKind::Relic: return TEXT("relic");
		default: return TEXT("material");
		}
	}

	FString GoodsKindName(ESOGoodsKind Kind, bool bMany)
	{
		switch (Kind)
		{
		case ESOGoodsKind::Consumable: return bMany ? TEXT("CONSUMABLES") : TEXT("CONSUMABLE");
		case ESOGoodsKind::Key: return bMany ? TEXT("KEYS") : TEXT("KEY");
		case ESOGoodsKind::Relic: return bMany ? TEXT("RELICS") : TEXT("RELIC");
		default: return bMany ? TEXT("MATERIALS") : TEXT("MATERIAL");
		}
	}

	int32 GoodsKindGlyph(ESOGoodsKind Kind)
	{
		switch (Kind)
		{
		case ESOGoodsKind::Consumable: return 7;
		case ESOGoodsKind::Key: return 3;
		case ESOGoodsKind::Relic: return 0;
		default: return 2;
		}
	}

	/** A journal page's picture (/Game/UI/Journal/T_Journal_<id>: a Sarketh's portrait in its rank's colours, the whole
	 *  body two by three; bBust: head and shoulders, square, for a row). */
	UTexture2D* JournalPicture(FName Id, bool bBust = false)
	{
		if (Id.IsNone())
		{
			return nullptr;
		}
		const FString Name = FString::Printf(TEXT("T_Journal_%s%s"), *Id.ToString(), bBust ? TEXT("_bust") : TEXT(""));
		return Cast<UTexture2D>(FSoftObjectPath(FString::Printf(TEXT("/Game/UI/Journal/%s.%s"), *Name, *Name)).TryLoad());
	}

	/** What would teach a page not yet learned (by its key's kind: SOJournal). */
	FString JournalHint(const FSOJournalEntry& E)
	{
		const FString Key = E.Unlock.ToString();
		if (Key.StartsWith(TEXT("met:"))) return TEXT("KILL ONE TO LEARN MORE");
		if (Key.StartsWith(TEXT("named:"))) return TEXT("ONE OF THEIR NAMED, NOT YET FOUGHT");
		if (Key.StartsWith(TEXT("stage:"))) return TEXT("NOT YET REACHED");
		if (Key.StartsWith(TEXT("done:"))) return TEXT("FINISH THE OPERATION");
		if (Key.StartsWith(TEXT("origin:"))) return TEXT("CARRY ONE OF THEIR GUNS");
		return TEXT("NOT YET KNOWN");
	}

	/** An arsenal slot's line under its name (ours). */
	const TCHAR* SlotLine(const FString& SlotId)
	{
		if (SlotId == TEXT("0")) return TEXT("RIFLES AND SUBMACHINE GUNS");
		if (SlotId == TEXT("1")) return TEXT("PRECISION AND CLOSE WORK");
		if (SlotId == TEXT("2")) return TEXT("LAUNCHERS AND MACHINE GUNS");
		if (SlotId == TEXT("melee")) return TEXT("FISTS AND BLADES");
		return TEXT("");
	}

	/** The orders a list is shown in (guns and armour; collected items: their own order first). */
	const TCHAR* SortName(int32 Mode, bool bGoods)
	{
		switch (Mode)
		{
		case 1: return TEXT("RARITY");
		case 2: return TEXT("NEWEST");
		case 3: return TEXT("NAME");
		default: return bGoods ? TEXT("TYPE") : TEXT("POWER");
		}
	}

	/** A gun's numbers as the armoury shows them, in one order for every gun (so two can be set side by side). */
	struct FStatRow
	{
		FString Name;
		float Value = 0.0f;
		float Max = 1.0f;
		FString Shown;
		bool bLowerBetter = false;
		/** a bar's fill is (value / max) ^ curve: damage and range span a wide range, the root keeps both ends readable */
		float Curve = 1.0f;
		/** shown in the summary (zoom only in the details) */
		bool bSummary = true;

		float Fill(float V) const
		{
			return bLowerBetter ? 1.0f - FMath::Clamp(V / Max, 0.0f, 0.95f) : FMath::Pow(FMath::Clamp(V / Max, 0.002f, 1.0f), Curve);
		}
	};

	TArray<FStatRow> GunStats(const FSOWeaponInstance& W, const USOWeaponData* Data)
	{
		const FSOWeaponStats S = USOLootLibrary::ComputeStats(W);
		const int32 Pellets = Data ? FMath::Max(1, Data->Pellets) : 1;
		const bool bCondenses = Data && Data->RefillTime > 0.0f;
		TArray<FStatRow> Rows;
		Rows.Add({ TEXT("IMPACT"), S.Damage * Pellets, 450.0f, Pellets > 1 ? FString::Printf(TEXT("%.0f x %d"), S.Damage, Pellets) : FString::Printf(TEXT("%.0f"), S.Damage), false, 0.5f });
		Rows.Add({ TEXT("FIRE RATE"), S.Rpm, 1100.0f, FString::Printf(TEXT("%.0f"), S.Rpm) });
		Rows.Add({ TEXT("RANGE"), S.Range, 180.0f, FString::Printf(TEXT("%.0f M"), S.Range), false, 0.5f });
		Rows.Add({ TEXT("STABILITY"), S.Spread, 7.0f, FString::Printf(TEXT("%.2f°"), S.Spread), true });
		Rows.Add({ TEXT("VELOCITY"), Data ? Data->MuzzleVelocity : 0.0f, 1000.0f, FString::Printf(TEXT("%.0f M/S"), Data ? Data->MuzzleVelocity : 0.0f) });
		// a gun that condenses its rounds: how long a full load takes to form once the crystal is cold
		Rows.Add({ bCondenses ? TEXT("CONDENSE") : TEXT("RELOAD"), bCondenses ? Data->RefillTime : S.Reload, bCondenses ? 5.0f : 4.0f,
			FString::Printf(TEXT("%.1f S"), bCondenses ? Data->RefillTime : S.Reload), true });
		Rows.Add({ TEXT("MAGAZINE"), static_cast<float>(S.Mag), 150.0f, FString::FromInt(S.Mag) });
		FStatRow Zoom{ TEXT("ZOOM"), S.Zoom, 8.0f, FString::Printf(TEXT("%.1fx"), S.Zoom) };
		Zoom.bSummary = false;
		Rows.Add(Zoom);
		return Rows;
	}

	/** The words of a set's or a slot's id ("void_sentinel" -> "VOID SENTINEL"). */
	FString IdWords(FName Id)
	{
		return Id.ToString().Replace(TEXT("_"), TEXT(" ")).ToUpper();
	}

	/** A skin tone's swatch: the tint over a light skin's own colour (linear, as the maps carry it). */
	FLinearColor SkinSwatch(const FLinearColor& Tint)
	{
		return FLinearColor(0.74f * Tint.R, 0.46f * Tint.G, 0.34f * Tint.B, 1.0f);
	}

	/** A hair colour's swatch: the tint lifted a little (the strands' sheen: the darkest would read as one black). */
	FLinearColor HairSwatch(const FLinearColor& Tint)
	{
		return FLinearColor(FMath::Min(1.0f, 1.7f * Tint.R + 0.004f), FMath::Min(1.0f, 1.7f * Tint.G + 0.004f), FMath::Min(1.0f, 1.7f * Tint.B + 0.004f), 1.0f);
	}

	/** The builder's group as the stand-in shows it: how close (0 the whole body, 1 the face), and turned how far
	 *  (the ears from the side, the nose and the jaw in three quarters, the eyes and the mouth nearly from the front). */
	float GroupClose(FName Group)
	{
		return Group == TEXT("body") ? 0.5f : Group == TEXT("hair") ? 0.62f : 1.0f;
	}

	float GroupYaw(FName Group)
	{
		static const TMap<FName, float> Yaws = { { TEXT("body"), 24.0f }, { TEXT("hair"), 38.0f }, { TEXT("brow"), 30.0f }, { TEXT("eyes"), 12.0f },
			{ TEXT("nose"), 40.0f }, { TEXT("cheeks"), 26.0f }, { TEXT("mouth"), 14.0f }, { TEXT("jaw"), 34.0f }, { TEXT("ears"), 74.0f } };
		const float* Yaw = Yaws.Find(Group);
		return Yaw ? *Yaw : 20.0f;
	}

	/** Which of a list of tones the look has (alpha 0: the body's own = the first; -1: none of them). */
	int32 ToneIndex(const TArray<FSOCreatorTone>& Tones, const FLinearColor& Tone)
	{
		if (Tone.A <= 0.0f)
		{
			return 0;
		}
		for (int32 i = 0; i < Tones.Num(); ++i)
		{
			if (Tones[i].Tint.Equals(FLinearColor(Tone.R, Tone.G, Tone.B, 1.0f), 2e-3f))
			{
				return i;
			}
		}
		return -1;
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
	Pawn->SetDisplayOnly();                                   // on no side, never a target, never damaged or killed
	Pawn->SetDisplayCarry(true);                              // the gun low across the chest: a hero's stance
	Pawn->GetMesh()->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
	Subject = Pawn;
	// alpha through post-processing: what the capture does not draw stays transparent over the screen
	if (IConsoleVariable* AlphaVar = IConsoleManager::Get().FindConsoleVariable(TEXT("r.PostProcessing.PropagateAlpha")))
	{
		PreviousAlpha = AlphaVar->GetInt();
		AlphaVar->Set(1, ECVF_SetByCode);
	}
	Target = NewObject<UTextureRenderTarget2D>(this);
	Target->ClearColor = FLinearColor(0.0f, 0.0f, 0.0f, 1.0f);
	Target->RenderTargetFormat = ETextureRenderTargetFormat::RTF_RGBA8_SRGB;
	Target->InitAutoFormat(1200, 1600);
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
	C->FOVAngle = 24.0f;
	C->bAlwaysPersistRenderingState = true;                   // (its own history: the hair's dither resolves, close up)
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
	C->PostProcessSettings.BloomIntensity = 0.55f;
	Capture = Cam;
	UpdateShowList();

	// a studio of its own: a warm key, a cyan rim and a pale one from behind, a soft fill, the platform's light below
	auto Light = [&](float Candelas, const FLinearColor& Color, float Source) -> APointLight*
	{
		APointLight* L = World->SpawnActor<APointLight>(Params);
		UPointLightComponent* P = Cast<UPointLightComponent>(L->GetLightComponent());
		P->SetMobility(EComponentMobility::Movable);
		P->SetIntensityUnits(ELightUnits::Candelas);
		P->SetIntensity(Candelas);
		P->SetLightColor(Color);
		P->SetAttenuationRadius(750.0f);
		P->SetSourceRadius(Source);
		P->SetCastShadows(false);
		return L;
	};
	Lights.Reset();
	Lights.Add(Light(175.0f, FLinearColor(1.0f, 0.93f, 0.85f), 55.0f));
	Lights.Add(Light(300.0f, FLinearColor(0.30f, 0.75f, 1.0f), 30.0f));
	Lights.Add(Light(210.0f, FLinearColor(0.72f, 0.84f, 1.0f), 30.0f));
	Lights.Add(Light(45.0f, FLinearColor(0.45f, 0.60f, 1.0f), 90.0f));
	Lights.Add(Light(40.0f, FLinearColor(0.30f, 0.80f, 1.0f), 60.0f));
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
	C->ShowOnlyComponents.Reset();
	if (bBodyOnly)
	{
		// the character builder: the body and what it wears, nothing in the hands or on the back
		TArray<USkeletalMeshComponent*> Meshes;
		Pawn->GetComponents(Meshes);
		for (USkeletalMeshComponent* Mesh : Meshes)
		{
			if (Mesh && !Mesh->bOnlyOwnerSee && !Mesh->IsFirstPersonRelevant())
			{
				C->ShowOnlyComponent(Mesh);
			}
		}
		return;
	}
	C->ShowOnlyActors.Add(Pawn);
	TArray<AActor*> Attached;
	Pawn->GetAttachedActors(Attached, true, true);
	C->ShowOnlyActors.Append(Attached);
}

void USOCharacterPreview::ShowLook(const FSOOutfit& Look)
{
	if (ASOCharacter* Pawn = Cast<ASOCharacter>(Subject.Get()))
	{
		Pawn->SetLook(Look);
	}
}

void USOCharacterPreview::SetFraming(float InClose, bool bInBodyOnly)
{
	CloseTarget = FMath::Clamp(InClose, 0.0f, 1.0f);
	if (bBodyOnly != bInBodyOnly)
	{
		bBodyOnly = bInBodyOnly;
		UpdateShowList();
	}
}

void USOCharacterPreview::Sync(USOInventoryComponent* Inventory, const FString& ShowWeapon, const FString& ShowArmor, const FSOOutfit* Look)
{
	ASOCharacter* Pawn = Cast<ASOCharacter>(Subject.Get());
	if (!Pawn || !Inventory)
	{
		return;
	}
	// dressed as the inventory says, with the piece chosen tried on over its slot
	FSOOutfit Outfit = Inventory->GetOutfit();
	if (const FSOArmorInstance* Try = ShowArmor.IsEmpty() ? nullptr : Inventory->FindArmor(ShowArmor))
	{
		Outfit.Set(Try->Slot, Try->Item);
	}
	FString Dressed = Outfit.Body.ToString();
	for (int32 i = 0; i < Outfit.Slots.Num(); ++i)
	{
		Dressed += FString::Printf(TEXT(";%s:%s"), *Outfit.Slots[i].ToString(), Outfit.Items.IsValidIndex(i) ? *Outfit.Items[i].ToString() : TEXT(""));
	}
	if (Dressed != ShownOutfit)
	{
		ShownOutfit = Dressed;
		Pawn->SetOutfit(Outfit);
	}
	// in the hands: the melee style chosen (the guard up, the blade in the fist), the gun chosen, or the gun in hand
	if (ShowWeapon.StartsWith(TEXT("melee:")))
	{
		Pawn->SetDisplayMelee(FName(*ShowWeapon.RightChop(6)));
		Pawn->SetFists(true);
	}
	else
	{
		Pawn->SetFists(false);
		const FSOWeaponInstance* Held = ShowWeapon.IsEmpty() ? nullptr : Inventory->Find(ShowWeapon);
		if (!Held)
		{
			Held = Inventory->GetEquipped(Inventory->GetActiveSlot());
		}
		const FString Want = Held ? Held->Uid + Held->Sight.ToString() + FString::FromInt(Held->Rarity) : FString();
		if (Held && Want != ShownWeapon)
		{
			ShownWeapon = Want;
			Pawn->EquipInstance(*Held);
		}
	}
	// the face and the tones (a slider being moved, a tone chosen: nothing is dressed again for them)
	Pawn->SetLook(Look ? *Look : Outfit);
	UpdateShowList();
}

void USOCharacterPreview::Stop()
{
	for (const TWeakObjectPtr<APointLight>& L : Lights)
	{
		if (APointLight* Lamp = L.Get())
		{
			Lamp->Destroy();
		}
	}
	Lights.Reset();
	for (AActor* A : { static_cast<AActor*>(Capture.Get()), static_cast<AActor*>(Subject.Get()) })
	{
		if (A)
		{
			A->Destroy();
		}
	}
	Capture = nullptr;
	Subject = nullptr;
	if (IConsoleVariable* AlphaVar = IConsoleManager::Get().FindConsoleVariable(TEXT("r.PostProcessing.PropagateAlpha")); AlphaVar && PreviousAlpha >= 0)
	{
		AlphaVar->Set(PreviousAlpha, ECVF_SetByCode);
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
	// how close (eased), and a turn asked for (eased the shorter way round; a drag stops it)
	const float Dt = FMath::Min(DeltaTime, 0.05f);
	Close = DeltaTime <= 0.0f ? CloseTarget : FMath::FInterpTo(Close, CloseTarget, Dt, 5.0f);
	if (bTurning)
	{
		const float Goal = YawGoal + 360.0f * FMath::RoundToFloat((Yaw - YawGoal) / 360.0f);
		Yaw = FMath::FInterpTo(Yaw, Goal, Dt, 6.0f);
		bTurning = FMath::Abs(Goal - Yaw) > 0.3f;
	}
	// The framing (FeetInPicture follows from it): the capsule's middle is 90 cm over the feet; the eye 470 cm off and
	// 20 cm over a point 8 cm above it, a 24 degree lens on a 3:4 picture (31.6 degrees tall): the feet 0.88 down it.
	// Closer (the character builder): head and shoulders at .55 (1.4 m off, on the chin), the face at 1 (76 cm off, on
	// the middle of the face, at the eyes' height)
	const FVector Center = Pawn->GetActorLocation() + FVector(0.0f, 0.0f, 8.0f);
	const FRotator Facing(0.0f, Pawn->GetActorRotation().Yaw + Yaw, 0.0f);
	const FVector Dir = Facing.Vector();                        // from the character towards the camera
	FVector Look = Center + FVector(0.0f, 0.0f, 4.0f);
	FVector Eye = Center + Dir * 470.0f + FVector(0.0f, 0.0f, 20.0f);
	if (Close > 0.001f)
	{
		const ACharacter* Body = Cast<ACharacter>(Pawn);
		const USkeletalMeshComponent* Mesh = Body ? Body->GetMesh() : nullptr;
		const int32 HeadBone = Mesh ? Mesh->GetBoneIndex(TEXT("head")) : INDEX_NONE;
		const FVector Ahead = FRotator(0.0f, Pawn->GetActorRotation().Yaw, 0.0f).Vector();
		const FVector Head = HeadBone != INDEX_NONE ? Mesh->GetBoneLocation(TEXT("head")) : Center + FVector(0.0f, 0.0f, 72.0f);
		const FVector Face = Head + FVector(0.0f, 0.0f, 7.0f) + Ahead * 5.0f;
		const FVector Chin = Head + FVector(0.0f, 0.0f, -10.0f) + Ahead * 3.0f;
		const float A = FMath::Clamp(Close / 0.55f, 0.0f, 1.0f);
		const float B = FMath::Clamp((Close - 0.55f) / 0.45f, 0.0f, 1.0f);
		const float SA = A * A * (3.0f - 2.0f * A), SB = B * B * (3.0f - 2.0f * B);
		const FVector Aim = FMath::Lerp(FMath::Lerp(Look, Chin, SA), Face, SB);
		const float Distance = FMath::Lerp(FMath::Lerp(470.0f, 140.0f, SA), 76.0f, SB);
		const float Rise = FMath::Lerp(FMath::Lerp(20.0f, 6.0f, SA), 1.0f, SB);
		Look = Aim;
		Eye = Aim + Dir * Distance + FVector(0.0f, 0.0f, Rise);
	}
	Cam->SetActorLocationAndRotation(Eye, (Look - Eye).Rotation());
	const FVector Right = FRotationMatrix(Facing).GetUnitAxis(EAxis::Y);
	const FVector Places[] = {
		Center + Dir * 230.0f + Right * 170.0f + FVector(0.0f, 0.0f, 130.0f),      // key: in front, to the right, high
		Center - Dir * 190.0f - Right * 150.0f + FVector(0.0f, 0.0f, 110.0f),      // rim: behind, to the left
		Center - Dir * 170.0f + Right * 160.0f + FVector(0.0f, 0.0f, 70.0f),       // rim: behind, to the right
		Center + Dir * 260.0f - Right * 200.0f + FVector(0.0f, 0.0f, 10.0f),       // fill: in front, to the left, low
		Center + Dir * 140.0f + FVector(0.0f, 0.0f, -80.0f) };                     // the platform's light from below
	// close on the face (the character builder) a portrait's light: the key a third up and to the side of the face and
	// softer, the rims at the head, the fill under the jaw's line, no platform; and all of it gentler (at the whole
	// body's strength the forehead and the nose went white)
	const FVector Places1[] = {
		Look + Dir * 150.0f + Right * 120.0f + FVector(0.0f, 0.0f, 105.0f),
		Look - Dir * 160.0f - Right * 140.0f + FVector(0.0f, 0.0f, 60.0f),
		Look - Dir * 140.0f + Right * 150.0f + FVector(0.0f, 0.0f, 50.0f),
		Look + Dir * 170.0f - Right * 150.0f + FVector(0.0f, 0.0f, -25.0f),
		Look + Dir * 140.0f + FVector(0.0f, 0.0f, -120.0f) };
	static const float Strength[] = { 175.0f, 300.0f, 210.0f, 45.0f, 40.0f };
	// (the rims a little above the head and low: level with it they shone through the jaw's thin edge in the skin's
	// scatter and drew a red line along it; high and strong they lit the hair's top white)
	static const float Strength1[] = { 58.0f, 40.0f, 28.0f, 24.0f, 0.0f };
	static const float Source[] = { 55.0f, 30.0f, 30.0f, 90.0f, 60.0f };
	static const float Source1[] = { 95.0f, 30.0f, 30.0f, 110.0f, 60.0f };
	const float C = FMath::Clamp(Close, 0.0f, 1.0f);
	for (int32 i = 0; i < Lights.Num() && i < static_cast<int32>(UE_ARRAY_COUNT(Places)); ++i)
	{
		if (APointLight* L = Lights[i].Get())
		{
			L->SetActorLocation(FMath::Lerp(Places[i], Places1[i], C));
			if (UPointLightComponent* P = Cast<UPointLightComponent>(L->GetLightComponent()))
			{
				P->SetIntensity(FMath::Lerp(Strength[i], Strength1[i], C));
				P->SetSourceRadius(FMath::Lerp(Source[i], Source1[i], C));
			}
		}
	}
}

// --- Card --------------------------------------------------------------------------------------------

TSharedRef<SWidget> USOInventoryTile::RebuildWidget()
{
	if (WidgetTree && !WidgetTree->RootWidget && Info.Style != ESOTileStyle::Card)
	{
		// an armoury's cell or row
		UWidgetTree* T = WidgetTree;
		Button = Make<USOQuietButton>(T);
		Restyle();
		Button->OnClicked.AddDynamic(this, &USOInventoryTile::OnClicked);
		Button->OnHovered.AddDynamic(this, &USOInventoryTile::OnHovered);
		Button->OnUnhovered.AddDynamic(this, &USOInventoryTile::OnUnhovered);
		UWidget* Body = Info.Style == ESOTileStyle::Cell ? BuildCell() : BuildRow();
		if (UButtonSlot* Fill = Cast<UButtonSlot>(Button->SetContent(Body)))
		{
			Fill->SetHorizontalAlignment(HAlign_Fill);
			Fill->SetVerticalAlignment(VAlign_Fill);
			Fill->SetPadding(FMargin(0));
		}
		WidgetTree->RootWidget = Sized(T, Button, Width, Info.Style == ESOTileStyle::Cell ? CellHeight : RowHeight);
		return Super::RebuildWidget();
	}
	if (WidgetTree && !WidgetTree->RootWidget)
	{
		UWidgetTree* T = WidgetTree;
		const bool bWeapon = Info.Kind == TEXT("wslot") || Info.Kind == TEXT("weapon") || Info.Kind == TEXT("mslot") || Info.Kind == TEXT("blade");
		const bool bSlot = Info.Kind == TEXT("wslot") || Info.Kind == TEXT("aslot") || Info.Kind == TEXT("mslot");
		const FLinearColor Rarity = Alpha(Info.Rarity, 1.0f);
		const float Height = bWeapon ? (bSlot ? 168.0f : 128.0f) : (bSlot ? 100.0f : 92.0f);
		Button = Make<USOQuietButton>(T);
		Restyle();
		Button->OnClicked.AddDynamic(this, &USOInventoryTile::OnClicked);
		Button->OnHovered.AddDynamic(this, &USOInventoryTile::OnHovered);
		Button->OnUnhovered.AddDynamic(this, &USOInventoryTile::OnUnhovered);
		UOverlay* Body = Make<UOverlay>(T);

		// the marks: in hand, equipped / worn, new, locked
		UHorizontalBox* Marks = Make<UHorizontalBox>(T);
		auto Mark = [&](const TCHAR* Label, const FLinearColor& Color)
		{
			const float Gap = Marks->GetChildrenCount() > 0 ? 10.0f : 0.0f;
			Marks->AddChildToHorizontalBox(Text(T, Label, 8, Color, FaceBold, 240))->SetPadding(FMargin(Gap, 0, 0, 0));
		};
		if (Info.bInHand) Mark(TEXT("IN HAND"), Cyan);
		if (Info.bEquipped) Mark(bWeapon ? TEXT("EQUIPPED") : TEXT("WORN"), Cyan);
		if (Info.bNew) Mark(TEXT("NEW"), Gold);
		if (Info.bLocked)
		{
			Marks->AddChildToHorizontalBox(Glyph(T, this, 12, Gold, 12))->SetPadding(FMargin(Marks->GetChildrenCount() > 0 ? 10.0f : 0.0f, 0, 0, 0));
		}

		// the words: the slot over the name, what it is under it
		UVerticalBox* Words = Make<UVerticalBox>(T);
		if (!Info.Sub.IsEmpty())
		{
			Words->AddChildToVerticalBox(Text(T, Info.Sub, 9, Dim, FaceBold, 260));
		}
		UTextBlock* Name = Text(T, Info.Title, bWeapon ? (bSlot ? 20 : 19) : (bSlot ? 19 : 18), Info.bEmpty ? Dim : Ink, FaceCond, 30);
		Name->SetAutoWrapText(true);
		Words->AddChildToVerticalBox(Name)->SetPadding(FMargin(0, Info.Sub.IsEmpty() ? 0 : 3, 0, 2));
		if (!Info.Tag.IsEmpty())
		{
			UTextBlock* Tag = Text(T, Info.Tag, 9, Info.bEmpty ? Dim : Rarity, FaceBold, 140);
			Tag->SetAutoWrapText(true);
			Words->AddChildToVerticalBox(Tag);
		}

		UHorizontalBox* Power = Make<UHorizontalBox>(T);
		if (Info.Power > 0)
		{
			Power->AddChildToHorizontalBox(Glyph(T, this, 4, Gold, 12))->SetVerticalAlignment(VAlign_Center);
			UHorizontalBoxSlot* N = Power->AddChildToHorizontalBox(Text(T, FString::FromInt(Info.Power), bSlot ? 24 : 20, Gold, FaceCond));
			N->SetPadding(FMargin(5, 0, 0, 0));
			N->SetVerticalAlignment(VAlign_Center);
			if (Info.PowerDelta != 0)
			{
				UHorizontalBoxSlot* D = Power->AddChildToHorizontalBox(Text(T, FString::Printf(TEXT("%+d"), Info.PowerDelta), 10, Info.PowerDelta > 0 ? Good : Bad, FaceBold));
				D->SetPadding(FMargin(7, 0, 0, 0));
				D->SetVerticalAlignment(VAlign_Center);
			}
		}

		// the picture, or a glyph where there is none
		UWidget* Picture = nullptr;
		if (Info.Icon)
		{
			UImage* Pic = Make<UImage>(T);
			Pic->SetBrushFromTexture(Info.Icon, false);
			Pic->SetVisibility(ESlateVisibility::HitTestInvisible);
			const FVector2D Size = bWeapon ? (bSlot ? FVector2D(222.0f, 111.0f) : FVector2D(206.0f, 103.0f)) : (bSlot ? FVector2D(84.0f, 84.0f) : FVector2D(78.0f, 78.0f));
			Picture = Sized(T, Pic, Size.X, Size.Y);
		}
		else if (Info.Glyph >= 0)
		{
			Picture = Glyph(T, this, Info.Glyph, Alpha(Soft, 0.5f), bWeapon ? (bSlot ? 68.0f : 54.0f) : 40.0f);
		}

		if (bWeapon)
		{
			// a gun's card: its render large on the right in its rarity's glow, the words top left, power at the foot
			if (Picture)
			{
				UOverlaySlot* S = Body->AddChildToOverlay(Picture);
				S->SetHorizontalAlignment(HAlign_Right);
				S->SetVerticalAlignment(VAlign_Center);
				S->SetPadding(FMargin(0, bSlot ? 22.0f : 8.0f, Info.Icon ? 10.0f : 86.0f, 0));
			}
			UOverlaySlot* W = Body->AddChildToOverlay(Sized(T, Words, bSlot ? 156.0f : 186.0f, 0.0f));
			W->SetHorizontalAlignment(HAlign_Left);
			W->SetVerticalAlignment(VAlign_Top);
			W->SetPadding(FMargin(26, bSlot ? 16 : 12, 0, 0));
			UOverlaySlot* P = Body->AddChildToOverlay(Power);
			P->SetHorizontalAlignment(HAlign_Left);
			P->SetVerticalAlignment(VAlign_Bottom);
			P->SetPadding(FMargin(26, 0, 0, bSlot ? 12 : 9));
			UOverlaySlot* M = Body->AddChildToOverlay(Marks);
			M->SetHorizontalAlignment(HAlign_Right);
			M->SetVerticalAlignment(VAlign_Top);
			M->SetPadding(FMargin(0, 10, 16, 0));
		}
		else
		{
			// a piece's card: the words, its power, its picture at the far end
			UHorizontalBox* Row = Make<UHorizontalBox>(T);
			UVerticalBox* Left = Make<UVerticalBox>(T);
			Left->AddChildToVerticalBox(Words);
			if (Marks->GetChildrenCount() > 0)
			{
				Left->AddChildToVerticalBox(Marks)->SetPadding(FMargin(0, 3, 0, 0));
			}
			UHorizontalBoxSlot* L = Row->AddChildToHorizontalBox(Left);
			L->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
			L->SetVerticalAlignment(VAlign_Center);
			L->SetPadding(FMargin(26, 0, 8, 0));
			UHorizontalBoxSlot* P = Row->AddChildToHorizontalBox(Power);
			P->SetVerticalAlignment(VAlign_Center);
			P->SetPadding(FMargin(0, 0, 14, 0));
			if (Picture)
			{
				UHorizontalBoxSlot* Pic = Row->AddChildToHorizontalBox(Picture);
				Pic->SetVerticalAlignment(VAlign_Center);
				Pic->SetPadding(FMargin(0, 0, 10, 0));
			}
			UOverlaySlot* R = Body->AddChildToOverlay(Row);
			R->SetHorizontalAlignment(HAlign_Fill);
			R->SetVerticalAlignment(VAlign_Fill);
		}
		if (UButtonSlot* Fill = Cast<UButtonSlot>(Button->SetContent(Body)))
		{
			Fill->SetHorizontalAlignment(HAlign_Fill);
			Fill->SetVerticalAlignment(VAlign_Fill);
			Fill->SetPadding(FMargin(0));
		}
		WidgetTree->RootWidget = Sized(T, Button, 0.0f, Height);
	}
	return Super::RebuildWidget();
}

UWidget* USOInventoryTile::BuildCell()
{
	// a grid's cell, top to bottom in rows of their own (nothing lies on anything): the marks (equipped or worn, new,
	// locked) at the right of the top (the rarity's diamond is in the cut corner at the left), the picture, the figure
	// (power and its difference against the one equipped; a collected item's count), the name
	UWidgetTree* T = WidgetTree;
	UVerticalBox* Column = Make<UVerticalBox>(T);
	UHorizontalBox* Marks = Make<UHorizontalBox>(T);
	Marks->AddChildToHorizontalBox(Make<USpacer>(T))->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
	auto Mark = [&](const TCHAR* Label, const FLinearColor& Color)
	{
		UHorizontalBoxSlot* S = Marks->AddChildToHorizontalBox(Text(T, Label, 7, Color, FaceBold, 200));
		S->SetPadding(FMargin(6, 0, 0, 0));
		S->SetVerticalAlignment(VAlign_Center);
	};
	if (Info.bEquipped)
	{
		Mark(Info.Kind == TEXT("armor") ? TEXT("WORN") : TEXT("EQUIPPED"), Cyan);
	}
	if (Info.bNew)
	{
		Mark(TEXT("NEW"), Gold);
	}
	if (Info.bLocked)
	{
		UHorizontalBoxSlot* S = Marks->AddChildToHorizontalBox(Glyph(T, this, 12, Gold, 10.0f));
		S->SetPadding(FMargin(6, 0, 0, 0));
		S->SetVerticalAlignment(VAlign_Center);
	}
	Column->AddChildToVerticalBox(Sized(T, Marks, 0.0f, 12.0f));
	UWidget* Picture = nullptr;
	if (Info.Icon)
	{
		UImage* Pic = Make<UImage>(T);
		Pic->SetBrushFromTexture(Info.Icon, false);
		Pic->SetVisibility(ESlateVisibility::HitTestInvisible);
		const float W = Info.bSquare ? 58.0f : FMath::Min(Width - 20.0f, 116.0f);
		Picture = Sized(T, Pic, W, Info.bSquare ? 58.0f : W * 0.5f);
	}
	else
	{
		Picture = Glyph(T, this, Info.Glyph >= 0 ? Info.Glyph : 4, Alpha(Soft, 0.6f), 34.0f);
	}
	UBorder* Holder = Box(T, FSlateColorBrush(FLinearColor::Transparent), FMargin(0));
	Holder->SetHorizontalAlignment(HAlign_Center);
	Holder->SetVerticalAlignment(VAlign_Center);
	Holder->SetContent(Picture);
	Column->AddChildToVerticalBox(Sized(T, Holder, 0.0f, 62.0f))->SetPadding(FMargin(0, 2, 0, 0));
	UHorizontalBox* Figure = Make<UHorizontalBox>(T);
	if (Info.Count >= 0)
	{
		Figure->AddChildToHorizontalBox(Text(T, FString::Printf(TEXT("× %s"), *Number(Info.Count)), 15, Ink, FaceCond))->SetVerticalAlignment(VAlign_Center);
	}
	else if (Info.Power > 0)
	{
		Figure->AddChildToHorizontalBox(Glyph(T, this, 4, Gold, 10.0f))->SetVerticalAlignment(VAlign_Center);
		UHorizontalBoxSlot* N = Figure->AddChildToHorizontalBox(Text(T, FString::FromInt(Info.Power), 15, Gold, FaceCond));
		N->SetPadding(FMargin(4, 0, 0, 0));
		N->SetVerticalAlignment(VAlign_Center);
		Figure->AddChildToHorizontalBox(Make<USpacer>(T))->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
		if (Info.PowerDelta != 0)
		{
			Figure->AddChildToHorizontalBox(Text(T, FString::Printf(TEXT("%+d"), Info.PowerDelta), 9, Info.PowerDelta > 0 ? Good : Bad, FaceBold))->SetVerticalAlignment(VAlign_Center);
		}
	}
	Column->AddChildToVerticalBox(Sized(T, Figure, 0.0f, 20.0f))->SetPadding(FMargin(0, 2, 0, 0));
	Column->AddChildToVerticalBox(Fit(Text(T, Info.Title, 10, Info.bEmpty ? Dim : Ink, FaceBold, 20)));
	UBorder* Pad = Box(T, FSlateColorBrush(FLinearColor::Transparent), FMargin(12, 6, 10, 8));
	Pad->SetContent(Column);
	return Pad;
}

UWidget* USOInventoryTile::BuildRow()
{
	// a list's row, left to right: the picture, the name over what it is, the marks, the figure
	UWidgetTree* T = WidgetTree;
	UHorizontalBox* Row = Make<UHorizontalBox>(T);
	UWidget* Picture = nullptr;
	if (Info.Icon)
	{
		UImage* Pic = Make<UImage>(T);
		Pic->SetBrushFromTexture(Info.Icon, false);
		Pic->SetVisibility(ESlateVisibility::HitTestInvisible);
		Picture = Sized(T, Pic, Info.bSquare ? 44.0f : 88.0f, 44.0f);
	}
	else
	{
		Picture = Glyph(T, this, Info.Glyph >= 0 ? Info.Glyph : 4, Alpha(Soft, 0.6f), 26.0f);
	}
	UBorder* Holder = Box(T, FSlateColorBrush(FLinearColor::Transparent), FMargin(0));
	Holder->SetHorizontalAlignment(HAlign_Center);
	Holder->SetVerticalAlignment(VAlign_Center);
	Holder->SetContent(Picture);
	Row->AddChildToHorizontalBox(Sized(T, Holder, 92.0f, 0.0f))->SetVerticalAlignment(VAlign_Fill);
	UVerticalBox* Words = Make<UVerticalBox>(T);
	Words->AddChildToVerticalBox(Fit(Text(T, Info.Title, 13, Info.bEmpty ? Dim : Ink, FaceCond, 30)));
	if (!Info.Tag.IsEmpty())
	{
		Words->AddChildToVerticalBox(Fit(Text(T, Info.Tag, 8, Alpha(Info.Rarity, 1.0f), FaceBold, 140)))->SetPadding(FMargin(0, 1, 0, 0));
	}
	UHorizontalBoxSlot* WordsSlot = Row->AddChildToHorizontalBox(Words);
	WordsSlot->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
	WordsSlot->SetVerticalAlignment(VAlign_Center);
	WordsSlot->SetPadding(FMargin(12, 0, 10, 0));
	auto Mark = [&](const TCHAR* Label, const FLinearColor& Color)
	{
		UHorizontalBoxSlot* S = Row->AddChildToHorizontalBox(Text(T, Label, 7, Color, FaceBold, 200));
		S->SetPadding(FMargin(0, 0, 10, 0));
		S->SetVerticalAlignment(VAlign_Center);
	};
	if (Info.bEquipped)
	{
		Mark(Info.Kind == TEXT("armor") ? TEXT("WORN") : TEXT("EQUIPPED"), Cyan);
	}
	if (Info.bNew)
	{
		Mark(TEXT("NEW"), Gold);
	}
	if (Info.bLocked)
	{
		UHorizontalBoxSlot* S = Row->AddChildToHorizontalBox(Glyph(T, this, 12, Gold, 11.0f));
		S->SetPadding(FMargin(0, 0, 10, 0));
		S->SetVerticalAlignment(VAlign_Center);
	}
	UHorizontalBox* Figure = Make<UHorizontalBox>(T);
	if (Info.Count >= 0)
	{
		Figure->AddChildToHorizontalBox(Text(T, FString::Printf(TEXT("× %s"), *Number(Info.Count)), 17, Ink, FaceCond))->SetVerticalAlignment(VAlign_Center);
	}
	else if (Info.Power > 0)
	{
		Figure->AddChildToHorizontalBox(Glyph(T, this, 4, Gold, 11.0f))->SetVerticalAlignment(VAlign_Center);
		UHorizontalBoxSlot* N = Figure->AddChildToHorizontalBox(Text(T, FString::FromInt(Info.Power), 18, Gold, FaceCond));
		N->SetPadding(FMargin(5, 0, 0, 0));
		N->SetVerticalAlignment(VAlign_Center);
		if (Info.PowerDelta != 0)
		{
			UHorizontalBoxSlot* D = Figure->AddChildToHorizontalBox(Text(T, FString::Printf(TEXT("%+d"), Info.PowerDelta), 9, Info.PowerDelta > 0 ? Good : Bad, FaceBold));
			D->SetPadding(FMargin(6, 0, 0, 0));
			D->SetVerticalAlignment(VAlign_Center);
		}
	}
	Row->AddChildToHorizontalBox(Sized(T, Figure, 78.0f, 0.0f))->SetVerticalAlignment(VAlign_Center);
	UBorder* Pad = Box(T, FSlateColorBrush(FLinearColor::Transparent), FMargin(24, 5, 12, 5));
	Pad->SetContent(Row);
	return Pad;
}

void USOInventoryTile::Restyle()
{
	if (!Button)
	{
		return;
	}
	const bool bWeapon = Info.Kind == TEXT("wslot") || Info.Kind == TEXT("weapon") || Info.Kind == TEXT("mslot") || Info.Kind == TEXT("blade");
	float GlowX = bWeapon ? 0.68f : 0.88f;
	float Glow = bWeapon ? (Info.Icon ? 0.95f : 0.45f) : 0.65f;
	if (Info.Style == ESOTileStyle::Cell)
	{
		GlowX = 0.5f;                                            // (behind the picture in the cell's middle)
		Glow = Info.Icon ? 0.9f : 0.45f;
	}
	else if (Info.Style == ESOTileStyle::Row)
	{
		GlowX = 0.08f;
		Glow = Info.Icon ? 0.7f : 0.35f;
	}
	const float Chosen = Info.bActive ? 1.0f : 0.0f;
	StyleButton(Button, CardBrush(this, Info.Rarity, bFocused ? 1.0f : 0.0f, Chosen, Info.bEmpty, GlowX, Glow), CardBrush(this, Info.Rarity, 1.0f, Chosen, Info.bEmpty, GlowX, Glow),
		CardBrush(this, Info.Rarity, 1.6f, Chosen, Info.bEmpty, GlowX, Glow));
}

void USOInventoryTile::SetFocused(bool bOn)
{
	if (bFocused != bOn)
	{
		bFocused = bOn;
		LiftTarget = bFocused || bHovered ? 7.0f : 0.0f;
		Restyle();
	}
}

void USOInventoryTile::SetChosen(bool bChosen)
{
	if (Info.bActive != bChosen)
	{
		Info.bActive = bChosen;
		Restyle();
	}
}

void USOInventoryTile::NativeTick(const FGeometry& MyGeometry, float InDeltaTime)
{
	Super::NativeTick(MyGeometry, InDeltaTime);
	if (Info.Style == ESOTileStyle::Card && !FMath::IsNearlyEqual(Lift, LiftTarget, 0.05f))
	{
		Lift = FMath::FInterpTo(Lift, LiftTarget, FMath::Min(InDeltaTime, 0.05f), 16.0f);
		SetRenderTranslation(FVector2D(Info.bLeft ? Lift : -Lift, 0.0f));
	}
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
	bHovered = true;
	LiftTarget = 7.0f;                                          // (leans toward the stage)
	if (Screen)
	{
		Screen->OnTileHover(this, true);
	}
}

void USOInventoryTile::OnUnhovered()
{
	bHovered = false;
	LiftTarget = bFocused ? 7.0f : 0.0f;
	if (Screen)
	{
		Screen->OnTileHover(this, false);
	}
}

// --- Controls ----------------------------------------------------------------------------------------

TSharedRef<SWidget> USOArmouryButton::RebuildWidget()
{
	if (WidgetTree && !WidgetTree->RootWidget)
	{
		UWidgetTree* T = WidgetTree;
		UButton* Button = Make<USOQuietButton>(T);
		Button->OnClicked.AddDynamic(this, &USOArmouryButton::OnClicked);
		const FSlateColorBrush Clear(FLinearColor::Transparent);
		const FLinearColor Word = bActive ? Ink : (bDim ? Dim : Soft);
		UWidget* Content = nullptr;
		switch (Kind)
		{
		case ESOArmouryControl::Tab:
		{
			// a word along the top, underlined with light when it is the one open
			StyleButton(Button, Clear, FSlateRoundedBoxBrush(FLinearColor(1.0f, 1.0f, 1.0f, 0.045f), 3.0f), FSlateRoundedBoxBrush(FLinearColor(1.0f, 1.0f, 1.0f, 0.09f), 3.0f));
			UVerticalBox* Column = Make<UVerticalBox>(T);
			UHorizontalBox* Row = Make<UHorizontalBox>(T);
			Row->AddChildToHorizontalBox(Text(T, Label, 12, bActive ? Ink : Dim, FaceBold, 300))->SetVerticalAlignment(VAlign_Center);
			if (bNew)
			{
				UHorizontalBoxSlot* N = Row->AddChildToHorizontalBox(Glyph(T, this, 4, Gold, 9.0f));
				N->SetPadding(FMargin(6, 0, 0, 0));
				N->SetVerticalAlignment(VAlign_Center);
			}
			Column->AddChildToVerticalBox(Row)->SetHorizontalAlignment(HAlign_Center);
			UVerticalBoxSlot* Under = Column->AddChildToVerticalBox(Sized(T, Box(T, FSlateColorBrush(bActive ? Cyan : FLinearColor::Transparent), FMargin(0)), 0.0f, 2.0f));
			Under->SetPadding(FMargin(0, 7, 0, 0));
			UBorder* Pad = Box(T, Clear, FMargin(14, 8, 14, 2));
			Pad->SetContent(Column);
			Content = Pad;
			break;
		}
		case ESOArmouryControl::SlotTile:
		{
			// one of the arsenal's slots: what is carried in it, its name under it, lit when it is the one open
			FPlate Normal;
			Normal.Cut = 7.0f;
			Normal.Fill = bActive ? FLinearColor(0.010f, 0.034f, 0.056f, 0.95f) : FLinearColor(0.006f, 0.009f, 0.018f, 0.9f);
			Normal.FillLow = bActive ? FLinearColor(0.006f, 0.020f, 0.034f, 0.95f) : FLinearColor(0.004f, 0.006f, 0.012f, 0.9f);
			Normal.Edge = bActive ? Alpha(Cyan, 0.95f) : FLinearColor(1.0f, 1.0f, 1.0f, 0.12f);
			if (bActive)
			{
				Normal.Accent = Cyan;
				Normal.AccentBottom = 2.0f;
				Normal.Wash = 0.45f;
			}
			FPlate Over = Normal;
			Over.Edge = Alpha(Cyan, 1.0f);
			Over.TopLight = 1.0f;
			StyleButton(Button, PlateBrush(this, Normal), PlateBrush(this, Over), PlateBrush(this, Over));
			UWidget* Picture = nullptr;
			if (Icon)
			{
				UImage* Pic = Make<UImage>(T);
				Pic->SetBrushFromTexture(Icon, false);
				Pic->SetVisibility(ESlateVisibility::HitTestInvisible);
				Picture = Sized(T, Pic, 44.0f, 22.0f);
			}
			else
			{
				Picture = Glyph(T, this, GlyphIndex >= 0 ? GlyphIndex : 4, bActive ? Cyan : Soft, 20.0f);
			}
			UBorder* Holder = Box(T, Clear, FMargin(0));
			Holder->SetHorizontalAlignment(HAlign_Center);
			Holder->SetVerticalAlignment(VAlign_Center);
			Holder->SetContent(Picture);
			UVerticalBox* Column = Make<UVerticalBox>(T);
			Column->AddChildToVerticalBox(Sized(T, Holder, 0.0f, 26.0f));
			// (something new in it: its name in gold; a mark beside the name had no room in a quarter of the column)
			Column->AddChildToVerticalBox(Fit(Text(T, Label, 7, bNew ? Gold : Word, FaceBold, 100)))->SetHorizontalAlignment(HAlign_Center);
			UBorder* Pad = Box(T, Clear, FMargin(3, 8, 3, 7));
			Pad->SetContent(Column);
			Content = Sized(T, Pad, Width, 62.0f);
			break;
		}
		case ESOArmouryControl::Row:
		{
			// a category with its count: a bar of light and a lit band when it is the one shown
			StyleButton(Button, bActive ? FSlateColorBrush(FLinearColor(0.016f, 0.075f, 0.12f, 0.88f)) : Clear,
				FSlateColorBrush(bActive ? FLinearColor(0.022f, 0.10f, 0.16f, 0.92f) : FLinearColor(1.0f, 1.0f, 1.0f, 0.045f)),
				FSlateColorBrush(FLinearColor(1.0f, 1.0f, 1.0f, 0.09f)));
			UHorizontalBox* Line = Make<UHorizontalBox>(T);
			UHorizontalBoxSlot* Bar = Line->AddChildToHorizontalBox(Sized(T, Box(T, FSlateColorBrush(bActive ? Cyan : FLinearColor(1.0f, 1.0f, 1.0f, 0.07f)), FMargin(0)), bActive ? 3.0f : 1.0f, 0.0f));
			Bar->SetVerticalAlignment(VAlign_Fill);
			UHorizontalBoxSlot* N = Line->AddChildToHorizontalBox(Fit(Text(T, Label, 10, Word, FaceBold, 170)));
			N->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
			N->SetPadding(FMargin(bActive ? 12.0f : 14.0f, 0, 8, 0));
			N->SetVerticalAlignment(VAlign_Center);
			if (bNew)
			{
				UHorizontalBoxSlot* G = Line->AddChildToHorizontalBox(Glyph(T, this, 4, Gold, 8.0f));
				G->SetPadding(FMargin(0, 0, 8, 0));
				G->SetVerticalAlignment(VAlign_Center);
			}
			if (!Count.IsEmpty())
			{
				UHorizontalBoxSlot* C = Line->AddChildToHorizontalBox(Text(T, Count, 10, bActive ? Ink : Dim, FaceBold, 60));
				C->SetPadding(FMargin(0, 0, 12, 0));
				C->SetVerticalAlignment(VAlign_Center);
			}
			Content = Sized(T, Line, Width, 32.0f);
			break;
		}
		case ESOArmouryControl::Swatch:
		case ESOArmouryControl::Choice:
		{
			// a tone (its colour, its name under it) or one of a few choices (a word on a wide plate): lit when chosen
			FPlate Normal;
			Normal.Cut = 7.0f;
			Normal.Fill = bActive ? FLinearColor(0.010f, 0.034f, 0.056f, 0.95f) : FLinearColor(0.006f, 0.009f, 0.018f, 0.9f);
			Normal.FillLow = bActive ? FLinearColor(0.006f, 0.020f, 0.034f, 0.95f) : FLinearColor(0.004f, 0.006f, 0.012f, 0.9f);
			Normal.Edge = bActive ? Alpha(Cyan, 0.95f) : FLinearColor(1.0f, 1.0f, 1.0f, 0.12f);
			if (bActive)
			{
				Normal.Accent = Cyan;
				Normal.AccentBottom = 2.0f;
				Normal.Wash = 0.35f;
			}
			FPlate Over = Normal;
			Over.Edge = Alpha(Cyan, 1.0f);
			Over.TopLight = 1.0f;
			StyleButton(Button, PlateBrush(this, Normal), PlateBrush(this, Over), PlateBrush(this, Over));
			UVerticalBox* Column = Make<UVerticalBox>(T);
			if (Kind == ESOArmouryControl::Swatch)
			{
				UBorder* Chip = Box(T, FSlateRoundedBoxBrush(Alpha(SwatchColor, 1.0f), 4.0f, bActive ? Alpha(Ink, 0.85f) : FLinearColor(1.0f, 1.0f, 1.0f, 0.16f), bActive ? 2.0f : 1.0f), FMargin(0));
				Column->AddChildToVerticalBox(Sized(T, Chip, 0.0f, 32.0f));
			}
			UTextBlock* Caption = Fit(Text(T, Label, Kind == ESOArmouryControl::Choice ? 11 : 8, bActive ? Ink : Soft, FaceBold, Kind == ESOArmouryControl::Choice ? 300 : 150));
			Caption->SetJustification(ETextJustify::Center);
			UVerticalBoxSlot* N = Column->AddChildToVerticalBox(Caption);
			N->SetHorizontalAlignment(HAlign_Fill);
			N->SetPadding(FMargin(0, Kind == ESOArmouryControl::Swatch ? 7.0f : 0.0f, 0, 0));
			UBorder* Pad = Box(T, Clear, Kind == ESOArmouryControl::Swatch ? FMargin(9, 9, 9, 8) : FMargin(10, 0, 10, 0));
			Pad->SetVerticalAlignment(VAlign_Center);
			Pad->SetContent(Column);
			Content = Sized(T, Pad, Width, Kind == ESOArmouryControl::Swatch ? 76.0f : 44.0f);
			break;
		}
		case ESOArmouryControl::Page:
		case ESOArmouryControl::Tool:
		{
			// a page's number, the arrows, the order, the two views: small plates, lit when they are what is shown
			FPlate Normal;
			Normal.Cut = 5.0f;
			Normal.Fill = bActive ? FLinearColor(0.012f, 0.040f, 0.066f, 0.95f) : FLinearColor(0.006f, 0.009f, 0.018f, Kind == ESOArmouryControl::Page ? 0.0f : 0.85f);
			Normal.FillLow = Normal.Fill;
			Normal.Edge = bActive ? Alpha(Cyan, 0.85f) : FLinearColor(1.0f, 1.0f, 1.0f, Kind == ESOArmouryControl::Page ? 0.0f : 0.14f);
			FPlate Over = Normal;
			Over.Fill = FLinearColor(0.012f, 0.030f, 0.050f, 0.95f);
			Over.FillLow = Over.Fill;
			Over.Edge = Alpha(Cyan, 1.0f);
			Over.TopLight = 1.0f;
			StyleButton(Button, PlateBrush(this, Normal), PlateBrush(this, Over), PlateBrush(this, Over));
			UWidget* Inner = nullptr;
			const FLinearColor Mark = Alpha(bActive ? Cyan : Soft, 0.95f);
			auto Dot = [&](float W, float H) { return Sized(T, Box(T, FSlateColorBrush(Mark), FMargin(0)), W, H); };
			if (Drawing == 1)
			{
				// the grid's view: four squares
				UVerticalBox* Squares = Make<UVerticalBox>(T);
				for (int32 r = 0; r < 2; ++r)
				{
					UHorizontalBox* Pair = Make<UHorizontalBox>(T);
					Pair->AddChildToHorizontalBox(Dot(5.0f, 5.0f));
					Pair->AddChildToHorizontalBox(Dot(5.0f, 5.0f))->SetPadding(FMargin(3, 0, 0, 0));
					Squares->AddChildToVerticalBox(Pair)->SetPadding(FMargin(0, r > 0 ? 3.0f : 0.0f, 0, 0));
				}
				Inner = Squares;
			}
			else if (Drawing == 2)
			{
				// the list's view: three bars
				UVerticalBox* Bars = Make<UVerticalBox>(T);
				for (int32 r = 0; r < 3; ++r)
				{
					Bars->AddChildToVerticalBox(Dot(13.0f, 2.0f))->SetPadding(FMargin(0, r > 0 ? 3.0f : 0.0f, 0, 0));
				}
				Inner = Bars;
			}
			else
			{
				Inner = Text(T, Label, Kind == ESOArmouryControl::Page ? 11 : 8, bActive ? Ink : (bDim ? Dim : Soft), FaceBold, Kind == ESOArmouryControl::Page ? 0 : 200);
			}
			UBorder* Pad = Box(T, Clear, Drawing > 0 ? FMargin(7, 6, 7, 6) : (Kind == ESOArmouryControl::Page ? FMargin(8, 3, 8, 3) : FMargin(10, 5, 10, 5)));
			Pad->SetHorizontalAlignment(HAlign_Center);
			Pad->SetVerticalAlignment(VAlign_Center);
			Pad->SetContent(Inner);
			Content = Sized(T, Pad, Width, 26.0f);
			break;
		}
		}
		if (UButtonSlot* Fill = Cast<UButtonSlot>(Button->SetContent(Content)))
		{
			Fill->SetHorizontalAlignment(HAlign_Fill);
			Fill->SetVerticalAlignment(VAlign_Fill);
			Fill->SetPadding(FMargin(0));
		}
		WidgetTree->RootWidget = Button;
	}
	return Super::RebuildWidget();
}

void USOArmouryButton::OnClicked()
{
	if (Screen)
	{
		Screen->OnControl(Kind, Key);
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
	bAuditing |= FParse::Param(FCommandLine::Get(), TEXT("SOHudAudit"));
	if (!Preview)
	{
		Preview = NewObject<USOCharacterPreview>(this);
	}
	if (APlayerController* Player = GetOwningPlayer())
	{
		Preview->Start(Player);
		SyncPreview();
		if (PreviewImage && Preview->GetTarget())
		{
			// the capture's alpha is inverse opacity: M_UI_Stage turns it round so only the character draws
			UMaterialInterface* Stage = Cast<UMaterialInterface>(FSoftObjectPath(TEXT("/Game/UI/M_UI_Stage.M_UI_Stage")).TryLoad());
			if (UMaterialInstanceDynamic* MID = Stage ? UMaterialInstanceDynamic::Create(Stage, this) : nullptr)
			{
				MID->SetTextureParameterValue(TEXT("Stage"), Preview->GetTarget());
				PreviewImage->SetBrushFromMaterial(MID);
				StageMaterial = MID;
			}
			else
			{
				PreviewImage->SetBrushResourceObject(Preview->GetTarget());
			}
		}
	}
	Animate();
}

void USOInventoryWidget::NativeDestruct()
{
	if (Inventory && (bShowedCreator || GetView() == EView::Character) && !Inventory->IsCharacterMade())
	{
		Inventory->ServerSetCharacterMade();                   // (a new player's first start is over)
	}
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
	if (Root)
	{
		// the layout follows the width (a change of the grid's columns builds the grid again), and looks again now and
		// then (the tabs' place waits on the banner's measured size)
		const float Width = static_cast<float>(Root->GetCachedGeometry().GetLocalSize().X);
		if (Width > 100.0f && (!FMath::IsNearlyEqual(Width, LaidOutWidth, 1.0f) || FPlatformTime::Seconds() - LastLayoutAt > 0.5))
		{
			const int32 Cols = Columns;
			const float Cell = CellWidth;
			UpdateLayout(Width);
			if (Cols != Columns || !FMath::IsNearlyEqual(Cell, CellWidth) )
			{
				Refresh();
			}
		}
	}
	if (Preview)
	{
		const float Dt = FMath::Min(InDeltaTime, 0.05f);
		if (FMath::Abs(StickYaw) > 0.18f)
		{
			Preview->Yaw -= StickYaw * 150.0f * Dt;               // (the right stick turns it)
			SpinVelocity = 0.0f;
		}
		else if (!bDragging && FMath::Abs(SpinVelocity) > 1.0f)
		{
			Preview->Yaw += SpinVelocity * Dt;                    // (a drag let go spins on and settles)
			SpinVelocity *= FMath::Exp(-5.0f * Dt);
		}
		Preview->Tick(InDeltaTime);
	}
	// the panels slide in from their sides and fade up after a change of view
	if (Arrive < 1.0f)
	{
		Arrive = FMath::Min(1.0f, Arrive + FMath::Min(InDeltaTime, 0.05f) / 0.3f);
		const float E = 1.0f - FMath::Pow(1.0f - Arrive, 3.0f);
		for (UWidget* W : { static_cast<UWidget*>(LeftPanel.Get()), static_cast<UWidget*>(CategoryPanel.Get()), static_cast<UWidget*>(GridPanel.Get()) })
		{
			if (W)
			{
				W->SetRenderTranslation(FVector2D(-36.0f * (1.0f - E), 0.0f));
				W->SetRenderOpacity(E);
			}
		}
		for (UWidget* W : { static_cast<UWidget*>(RightPanel.Get()), static_cast<UWidget*>(InspectPanel.Get()) })
		{
			if (W)
			{
				W->SetRenderTranslation(FVector2D(36.0f * (1.0f - E), 0.0f));
				W->SetRenderOpacity(E);
			}
		}
		if (AttributeColumn)
		{
			AttributeColumn->SetRenderOpacity(E);
		}
	}
	if (bAuditing && Arrive >= 1.0f && FPlatformTime::Seconds() - AuditAt > 0.5)
	{
		AuditAt = FPlatformTime::Seconds();
		Audit();
	}
}

void USOInventoryWidget::Audit()
{
	// every word, picture and glyph on the screen as it is drawn (its render transform, a scroll's clip), against every
	// other: words or pictures that cross are logged, and words that need more room than they were given
	if (!Root)
	{
		return;
	}
	struct FMarkBox
	{
		FString Name;
		FBox2D Box;
		/** a button or a plate: what lies on it whole is by design, what crosses its edge is not */
		bool bFrame = false;
	};
	TArray<FMarkBox> Marks;
	TArray<FString> Lines;
	const FGeometry RootGeometry = Root->GetCachedGeometry();
	const FVector2D RootSize = RootGeometry.GetLocalSize();
	auto Overlap = [](const FBox2D& A, const FBox2D& B)
	{
		FBox2D Out(ForceInit);
		if (A.bIsValid && B.bIsValid)
		{
			const FVector2D Min(FMath::Max(A.Min.X, B.Min.X), FMath::Max(A.Min.Y, B.Min.Y));
			const FVector2D Max(FMath::Min(A.Max.X, B.Max.X), FMath::Min(A.Max.Y, B.Max.Y));
			if (Min.X < Max.X && Min.Y < Max.Y)
			{
				Out = FBox2D(Min, Max);
			}
		}
		return Out;
	};
	TFunction<void(UWidget*, const FBox2D&)> Walk;
	Walk = [&](UWidget* W, const FBox2D& Clip)
	{
		if (!W || W->GetVisibility() == ESlateVisibility::Collapsed || W->GetVisibility() == ESlateVisibility::Hidden || W->GetRenderOpacity() < 0.05f)
		{
			return;
		}
		const FGeometry& G = W->GetCachedGeometry();
		const FVector2D Size = G.GetLocalSize();
		const FSlateRenderTransform& Xf = G.GetAccumulatedRenderTransform();
		const FVector2D A = RootGeometry.AbsoluteToLocal(Xf.TransformPoint(FVector2D::ZeroVector));
		const FVector2D B = RootGeometry.AbsoluteToLocal(Xf.TransformPoint(Size));
		const FBox2D Box(FVector2D(FMath::Min(A.X, B.X), FMath::Min(A.Y, B.Y)), FVector2D(FMath::Max(A.X, B.X), FMath::Max(A.Y, B.Y)));
		const FBox2D Inside = W->IsA<UScrollBox>() ? Overlap(Clip, Box) : Clip;
		const UBorder* Plate = Cast<UBorder>(W);
		const bool bFrame = W->IsA<UButton>() || (Plate && (Plate->Background.GetResourceObject() != nullptr
			|| (Plate->Background.DrawAs != ESlateBrushDrawType::NoDrawType && Plate->Background.TintColor.GetSpecifiedColor().A > 0.02f)));
		if (bFrame && Box.GetSize().X > 4.0f && Box.GetSize().Y > 4.0f && Box.GetSize().X < RootSize.X * 0.9f)
		{
			const FBox2D Seen = Overlap(Box, Inside);
			if (Seen.bIsValid)
			{
				Marks.Add({ FString::Printf(TEXT("%s %.0fx%.0f"), W->IsA<UButton>() ? TEXT("button") : TEXT("plate"), Box.GetSize().X, Box.GetSize().Y), Seen, true });
			}
		}
		if (const UTextBlock* Words = Cast<UTextBlock>(W))
		{
			const FString Str = Words->GetText().ToString();
			if (!Str.TrimStartAndEnd().IsEmpty())
			{
				const float Want = static_cast<float>(Words->GetDesiredSize().X);
				if (Want > Size.X + 1.5f && Words->GetTextOverflowPolicy() != ETextOverflowPolicy::Ellipsis && !Words->GetAutoWrapText() && Overlap(Box, Inside).bIsValid)
				{
					Lines.Add(FString::Printf(TEXT("ARMOURYCLIP '%s' needs %.0f, has %.0f"), *Str.Left(36), Want, Size.X));
				}
				const float Pad = Box.GetSize().Y * 0.14f;
				const FBox2D Seen = Overlap(FBox2D(Box.Min + FVector2D(0.0f, Pad), Box.Max - FVector2D(0.0f, Pad)), Inside);
				if (Seen.bIsValid)
				{
					Marks.Add({ FString::Printf(TEXT("text '%s'"), *Str.Left(28)), Seen });
				}
			}
		}
		else if (const UImage* Picture = Cast<UImage>(W))
		{
			const FBox2D Seen = Overlap(Box, Inside);
			if (Picture != PreviewImage && Picture != FloorImage && Box.GetSize().X < RootSize.X * 0.6f && Seen.bIsValid)
			{
				Marks.Add({ FString::Printf(TEXT("picture %.0fx%.0f"), Box.GetSize().X, Box.GetSize().Y), Seen });
			}
		}
		if (const UPanelWidget* Panel = Cast<UPanelWidget>(W))
		{
			for (int32 i = 0; i < Panel->GetChildrenCount(); ++i)
			{
				Walk(Panel->GetChildAt(i), Inside);
			}
		}
		else if (const UUserWidget* User = Cast<UUserWidget>(W))
		{
			if (User->WidgetTree)
			{
				Walk(User->WidgetTree->RootWidget, Inside);
			}
		}
	};
	Walk(Root, FBox2D(FVector2D::ZeroVector, RootSize));
	for (int32 i = 0; i < Marks.Num(); ++i)
	{
		for (int32 j = i + 1; j < Marks.Num(); ++j)
		{
			const FBox2D& A = Marks[i].Box;
			const FBox2D& B = Marks[j].Box;
			const float OX = FMath::Min(A.Max.X, B.Max.X) - FMath::Max(A.Min.X, B.Min.X);
			const float OY = FMath::Min(A.Max.Y, B.Max.Y) - FMath::Max(A.Min.Y, B.Min.Y);
			if (OX > 1.0f && OY > 1.0f)
			{
				if (Marks[i].bFrame || Marks[j].bFrame)
				{
					// a frame holds what lies on it whole; only what crosses its edge is wrong
					auto Holds = [](const FBox2D& Outer, const FBox2D& In)
					{
						return In.Min.X >= Outer.Min.X - 1.0f && In.Min.Y >= Outer.Min.Y - 1.0f && In.Max.X <= Outer.Max.X + 1.0f && In.Max.Y <= Outer.Max.Y + 1.0f;
					};
					if (Holds(A, B) || Holds(B, A))
					{
						continue;
					}
				}
				Lines.Add(FString::Printf(TEXT("ARMOURYOVERLAP %s  x  %s"), *Marks[i].Name, *Marks[j].Name));
			}
		}
	}
	const FString Summary = FString::Printf(TEXT("ARMOURYAUDIT %s: %d words and pictures, %d crossings"), *OpenSlotId, Marks.Num(), Lines.Num());
	const FString Everything = Summary + FString::Join(Lines, TEXT("|"));
	if (Everything != AuditLast)
	{
		AuditLast = Everything;
		UE_LOG(LogTemp, Display, TEXT("%s"), *Summary);
		for (const FString& L : Lines)
		{
			UE_LOG(LogTemp, Display, TEXT("%s"), *L);
		}
	}
}

void USOInventoryWidget::Animate()
{
	Arrive = 0.0f;
	for (UWidget* W : { static_cast<UWidget*>(LeftPanel.Get()), static_cast<UWidget*>(RightPanel.Get()), static_cast<UWidget*>(CategoryPanel.Get()),
		static_cast<UWidget*>(GridPanel.Get()), static_cast<UWidget*>(InspectPanel.Get()) })
	{
		if (W)
		{
			W->SetRenderOpacity(0.0f);
		}
	}
}

void USOInventoryWidget::BuildTree()
{
	UWidgetTree* T = WidgetTree;
	Root = Make<UCanvasPanel>(T);
	WidgetTree->RootWidget = Root;
	SetIsFocusable(true);
	auto Place = [&](UWidget* W, const FAnchors& Anchors, const FMargin& Offsets, const FVector2D& Align = FVector2D::ZeroVector, bool bAuto = false)
	{
		UCanvasPanelSlot* S = Root->AddChildToCanvas(W);
		S->SetAnchors(Anchors);
		S->SetAlignment(Align);
		S->SetAutoSize(bAuto);
		S->SetOffsets(Offsets);
		return S;
	};

	// the backdrop: night blue lit from the stage, the broken orbit faint behind the character, motes in the light
	UImage* Back = Make<UImage>(T);
	if (UMaterialInstanceDynamic* MID = Instance(this, TEXT("M_UI_Backdrop")))
	{
		MID->SetVectorParameterValue(TEXT("Stage"), FLinearColor(0.5f, 0.45f, FootY / 1080.0f, 1.0f));
		Back->SetBrush(MaterialBrush(MID));
	}
	else
	{
		Back->SetBrush(FSlateColorBrush(FLinearColor(0.008f, 0.012f, 0.026f, 1.0f)));
	}
	Back->SetVisibility(ESlateVisibility::Visible);             // (catches the clicks no card takes: a drag turns the character)
	Place(Back, FAnchors(0.0f, 0.0f, 1.0f, 1.0f), FMargin(0.0f));

	// the platform under the feet and the character on it (where they stand follows the view: UpdateLayout)
	FloorImage = Make<UImage>(T);
	if (UMaterialInstanceDynamic* MID = Instance(this, TEXT("M_UI_Floor")))
	{
		FloorImage->SetBrush(MaterialBrush(MID));
		FloorImage->SetVisibility(ESlateVisibility::HitTestInvisible);
	}
	else
	{
		FloorImage->SetVisibility(ESlateVisibility::Collapsed);
	}
	Place(FloorImage, FAnchors(0.0f, 0.0f), FMargin(960.0f, FootY, 640.0f, 176.0f), FVector2D(0.5f, 0.5f));
	PreviewImage = Make<UImage>(T);
	PreviewImage->SetVisibility(ESlateVisibility::HitTestInvisible);
	Place(PreviewImage, FAnchors(0.0f, 0.0f), FMargin(960.0f, StageTop, StageWidth, StageHeight), FVector2D(0.5f, 0.0f));

	// the banner's left: who, how far along
	UHorizontalBox* Left = Make<UHorizontalBox>(T);
	Left->AddChildToHorizontalBox(Glyph(T, this, 0, Cyan, 46.0f))->SetVerticalAlignment(VAlign_Center);
	UVerticalBox* Who = Make<UVerticalBox>(T);
	NameText = Text(T, TEXT("ORION OPERATIVE"), 24, Ink, FaceCond, 260);    // (ours: the reference picture's brand is never used)
	Who->AddChildToVerticalBox(NameText);
	UHorizontalBox* LevelRow = Make<UHorizontalBox>(T);
	LevelText = Text(T, TEXT("LEVEL 1"), 10, Cyan, FaceBold, 220);
	LevelRow->AddChildToHorizontalBox(LevelText)->SetVerticalAlignment(VAlign_Center);
	XpBar = StatBar(T, this, 0.0f, 0.0f, 24, Cyan);
	UHorizontalBoxSlot* BarSlot = LevelRow->AddChildToHorizontalBox(Sized(T, XpBar, 150.0f, 5.0f));
	BarSlot->SetVerticalAlignment(VAlign_Center);
	BarSlot->SetPadding(FMargin(12, 0, 10, 0));
	XpText = Text(T, TEXT(""), 9, Dim, FaceBold, 120);
	LevelRow->AddChildToHorizontalBox(XpText)->SetVerticalAlignment(VAlign_Center);
	Who->AddChildToVerticalBox(LevelRow)->SetPadding(FMargin(0, 2, 0, 0));
	UHorizontalBoxSlot* WhoSlot = Left->AddChildToHorizontalBox(Who);
	WhoSlot->SetPadding(FMargin(14, 0, 0, 0));
	WhoSlot->SetVerticalAlignment(VAlign_Center);
	BannerLeft = Left;
	Place(Left, FAnchors(0.0f, 0.0f), FMargin(Margin, BannerY, 0.0f, 0.0f), FVector2D(0.0f, 0.5f), true);

	// the banner's right: what is owned, the power
	UHorizontalBox* Right = Make<UHorizontalBox>(T);
	Currencies = Make<UHorizontalBox>(T);
	Right->AddChildToHorizontalBox(Currencies)->SetVerticalAlignment(VAlign_Center);
	{
		FPlate PowerPlate;
		PowerPlate.Cut = 12.0f;
		PowerPlate.Fill = FLinearColor(0.012f, 0.008f, 0.003f, 0.9f);
		PowerPlate.FillLow = FLinearColor(0.006f, 0.004f, 0.0015f, 0.92f);
		PowerPlate.Edge = Alpha(Gold, 0.5f);
		PowerPlate.Accent = Gold;
		PowerPlate.AccentLeft = 3.0f;
		PowerPlate.Wash = 0.22f;
		UBorder* PowerBox = Box(T, PlateBrush(this, PowerPlate), FMargin(16, 4, 22, 4));
		UHorizontalBox* PowerRow = Make<UHorizontalBox>(T);
		PowerRow->AddChildToHorizontalBox(Glyph(T, this, 4, Gold, 24.0f))->SetVerticalAlignment(VAlign_Center);
		UVerticalBox* PowerLines = Make<UVerticalBox>(T);
		PowerLines->AddChildToVerticalBox(Text(T, TEXT("POWER"), 8, Gold, FaceBold, 320));
		PowerText = Text(T, TEXT("0"), 32, Gold, FaceCond);
		PowerLines->AddChildToVerticalBox(PowerText)->SetPadding(FMargin(0, -4, 0, 0));
		UHorizontalBoxSlot* Lines = PowerRow->AddChildToHorizontalBox(PowerLines);
		Lines->SetPadding(FMargin(12, 0, 0, 0));
		Lines->SetVerticalAlignment(VAlign_Center);
		PowerBox->SetContent(PowerRow);
		Right->AddChildToHorizontalBox(PowerBox)->SetVerticalAlignment(VAlign_Center);
	}
	BannerRight = Right;
	Place(Right, FAnchors(1.0f, 0.0f), FMargin(-Margin, BannerY, 0.0f, 0.0f), FVector2D(1.0f, 0.5f), true);

	// the tabs between (a row of their own under the banner when the screen is too narrow: UpdateLayout)
	TabRow = Make<UHorizontalBox>(T);
	Place(TabRow, FAnchors(0.5f, 0.0f), FMargin(0.0f, BannerY, 0.0f, 0.0f), FVector2D(0.5f, 0.5f), true);
	BannerRule = Box(T, FSlateColorBrush(Faint), FMargin(0));
	Place(BannerRule, FAnchors(0.0f, 0.0f, 1.0f, 0.0f), FMargin(Margin, 100.0f, Margin, 1.0f));
	BannerLit = Box(T, FSlateColorBrush(Cyan), FMargin(0));
	Place(BannerLit, FAnchors(0.0f, 0.0f), FMargin(Margin, 99.0f, 120.0f, 2.0f));

	// the loadout's columns, the attributes beside the stage
	LeftPanel = Make<UVerticalBox>(T);
	Place(LeftPanel, FAnchors(0.0f, 0.0f, 0.0f, 1.0f), FMargin(Margin, PanelTop, PanelWidth, PanelBottom));
	RightPanel = Make<UVerticalBox>(T);
	Place(RightPanel, FAnchors(1.0f, 0.0f, 1.0f, 1.0f), FMargin(-(Margin + PanelWidth), PanelTop, PanelWidth, PanelBottom));
	AttributeColumn = Make<UVerticalBox>(T);
	Place(AttributeColumn, FAnchors(1.0f, 0.0f), FMargin(-(Margin + PanelWidth + 104.0f), 236.0f, 84.0f, 0.0f), FVector2D::ZeroVector, true);

	// an armoury's column, its grid, its inspect panel; the comparison over the grid
	CategoryPanel = Make<UVerticalBox>(T);
	Place(CategoryPanel, FAnchors(0.0f, 0.0f, 0.0f, 1.0f), FMargin(Margin, PanelTop, CatWidth, PanelBottom));
	GridPanel = Make<UVerticalBox>(T);
	Place(GridPanel, FAnchors(0.0f, 0.0f, 0.0f, 1.0f), FMargin(Margin + CatWidth + ColumnGap, PanelTop, GridWidth, PanelBottom));
	InspectPanel = Make<UVerticalBox>(T);
	Place(InspectPanel, FAnchors(1.0f, 0.0f, 1.0f, 1.0f), FMargin(-(Margin + InspectWidth), PanelTop, InspectWidth, PanelBottom));
	{
		FPlate ComparePlate;
		ComparePlate.Cut = 16.0f;
		ComparePlate.Fill = FLinearColor(0.004f, 0.007f, 0.014f, 0.97f);
		ComparePlate.FillLow = FLinearColor(0.003f, 0.0045f, 0.009f, 0.98f);
		ComparePlate.Edge = Alpha(Cyan, 0.45f);
		ComparePlate.TopLight = 1.0f;
		CompareBox = Box(T, PlateBrush(this, ComparePlate), FMargin(24, 18, 24, 20));
		CompareBox->SetVisibility(ESlateVisibility::Collapsed);
		Place(CompareBox, FAnchors(0.0f, 0.0f), FMargin(Margin + CatWidth + ColumnGap, PanelTop + 50.0f, 0.0f, 0.0f), FVector2D::ZeroVector, true);
	}

	// a hovered loadout card's quick look
	FPlate LookPlate;
	LookPlate.Cut = 14.0f;
	LookPlate.Fill = FLinearColor(0.005f, 0.008f, 0.016f, 0.97f);
	LookPlate.FillLow = FLinearColor(0.003f, 0.0045f, 0.009f, 0.97f);
	LookPlate.Edge = Alpha(Cyan, 0.35f);
	LookPlate.TopLight = 1.0f;
	QuickLook = Box(T, PlateBrush(this, LookPlate), FMargin(22, 16, 22, 16));
	QuickLook->SetVisibility(ESlateVisibility::Collapsed);
	Place(QuickLook, FAnchors(0.0f, 0.0f), FMargin(0.0f), FVector2D::ZeroVector, true);

	// the foot: a hairline; the drag's hint and the body on the left, what the keys do on the right
	FooterRule = Box(T, FSlateColorBrush(Faint), FMargin(0));
	Place(FooterRule, FAnchors(0.0f, 1.0f, 1.0f, 1.0f), FMargin(Margin, -(1080.0f - FooterRuleY), Margin, 1.0f));
	HintRow = Make<UHorizontalBox>(T);
	Place(HintRow, FAnchors(1.0f, 1.0f), FMargin(-Margin + 22.0f, -(1080.0f - HintY), 0.0f, 0.0f), FVector2D(1.0f, 0.5f), true);
	DragHint = Hint(T, TEXT("DRAG"), TEXT("TURN"));
	Place(DragHint, FAnchors(0.0f, 1.0f), FMargin(Margin, -(1080.0f - HintY), 0.0f, 0.0f), FVector2D(0.0f, 0.5f), true);
	{
		UButton* BodyButton = Make<USOQuietButton>(T);
		FPlate Normal;
		Normal.Cut = 7.0f;
		Normal.Fill = FLinearColor(0.006f, 0.009f, 0.018f, 0.8f);
		Normal.FillLow = Normal.Fill;
		Normal.Edge = Alpha(Cyan, 0.3f);
		FPlate Over = Normal;
		Over.Edge = Cyan;
		Over.TopLight = 1.0f;
		StyleButton(BodyButton, PlateBrush(this, Normal), PlateBrush(this, Over), PlateBrush(this, Over));
		UHorizontalBox* Pair = Make<UHorizontalBox>(T);
		Pair->AddChildToHorizontalBox(Text(T, TEXT("BODY"), 8, Dim, FaceBold, 240))->SetVerticalAlignment(VAlign_Center);
		MaleLabel = Text(T, TEXT("MALE"), 9, Ink, FaceBold, 220);
		FemaleLabel = Text(T, TEXT("FEMALE"), 9, Dim, FaceBold, 220);
		Pair->AddChildToHorizontalBox(MaleLabel)->SetPadding(FMargin(10, 0, 0, 0));
		Pair->AddChildToHorizontalBox(Text(T, TEXT("/"), 9, Dim, FaceBold))->SetPadding(FMargin(8, 0, 8, 0));
		Pair->AddChildToHorizontalBox(FemaleLabel);
		UBorder* Pad = Box(T, FSlateColorBrush(FLinearColor::Transparent), FMargin(12, 5, 12, 5));
		Pad->SetContent(Pair);
		BodyButton->SetContent(Pad);
		BodyButton->OnClicked.AddDynamic(this, &USOInventoryWidget::OnBody);
		BodyButton->SetToolTipText(FText::FromString(TEXT("The body you play")));
		BodyToggle = BodyButton;
		Place(BodyButton, FAnchors(0.0f, 1.0f), FMargin(Margin + 150.0f, -(1080.0f - HintY), 0.0f, 0.0f), FVector2D(0.0f, 0.5f), true);
	}

	// the inspect panel (an armoury puts it in its place): its content scrolls, its buttons stay under it
	FPlate InspectPlate;
	InspectPlate.Cut = 20.0f;
	InspectPlate.Fill = FLinearColor(0.0055f, 0.0085f, 0.017f, 0.88f);
	InspectPlate.FillLow = FLinearColor(0.003f, 0.0045f, 0.0095f, 0.92f);
	InspectPlate.Edge = FLinearColor(1.0f, 1.0f, 1.0f, 0.12f);
	InspectPlate.Hatch = 1.0f;
	InspectPlate.TopLight = 0.6f;
	UBorder* Frame = Box(T, PlateBrush(this, InspectPlate), FMargin(26, 20, 18, 18));
	UVerticalBox* FrameColumn = Make<UVerticalBox>(T);
	InspectScroll = Scroll(T);
	Inspect = Make<UVerticalBox>(T);
	InspectScroll->AddChild(Inspect);
	FrameColumn->AddChildToVerticalBox(InspectScroll)->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
	UVerticalBox* Actions = Make<UVerticalBox>(T);
	auto Action = [&](TObjectPtr<UButton>& Out, TObjectPtr<UTextBlock>& Label, const TCHAR* Key, const TCHAR* Caption, const FLinearColor& Color) -> UButton*
	{
		Out = Make<USOQuietButton>(T);
		FPlate Normal;
		Normal.Cut = 8.0f;
		Normal.Fill = FLinearColor(0.008f, 0.012f, 0.024f, 0.95f);
		Normal.FillLow = FLinearColor(0.005f, 0.008f, 0.016f, 0.95f);
		Normal.Accent = Alpha(Color, 1.0f);
		Normal.AccentBottom = 2.0f;
		Normal.Wash = 0.35f;
		Normal.Edge = Alpha(Color, 0.4f);
		FPlate Over = Normal;
		Over.Wash = 0.85f;
		Over.Edge = Alpha(Color, 1.0f);
		Over.EdgeWidth = 1.5f;
		Over.TopLight = 1.0f;
		FPlate Down = Over;
		Down.Wash = 1.25f;
		Down.EdgeWidth = 2.0f;
		FPlate Off = Normal;
		Off.Accent = Alpha(Color, 0.18f);
		Off.Edge = FLinearColor(1.0f, 1.0f, 1.0f, 0.07f);
		Off.Wash = 0.0f;
		const FSlateBrush OffBrush = PlateBrush(this, Off);
		StyleButton(Out, PlateBrush(this, Normal), PlateBrush(this, Over), PlateBrush(this, Down), &OffBrush);
		UHorizontalBox* Row = Make<UHorizontalBox>(T);
		UWidget* Cap = KeyCap(T, Key);
		Row->AddChildToHorizontalBox(Cap)->SetVerticalAlignment(VAlign_Center);
		if (&Out == &EquipButton)
		{
			EquipKey = Cap;
		}
		Label = Text(T, Caption, 9, Ink, FaceBold, 60);
		UHorizontalBoxSlot* L = Row->AddChildToHorizontalBox(Label);
		L->SetPadding(FMargin(6, 0, 0, 0));
		L->SetVerticalAlignment(VAlign_Center);
		UBorder* Pad = Box(T, FSlateColorBrush(FLinearColor::Transparent), FMargin(4, 10, 4, 10));
		Pad->SetHorizontalAlignment(HAlign_Center);
		Pad->SetContent(Row);
		Out->SetContent(Pad);
		return Out;
	};
	UHorizontalBox* Main = Make<UHorizontalBox>(T);
	auto Put = [&](UButton* B, float Share, bool bLast)
	{
		UHorizontalBoxSlot* S = Main->AddChildToHorizontalBox(B);
		FSlateChildSize Size(ESlateSizeRule::Fill);
		Size.Value = Share;
		S->SetSize(Size);
		S->SetPadding(FMargin(0, 0, bLast ? 0.0f : 6.0f, 0));
	};
	Put(Action(EquipButton, EquipLabel, TEXT("ENTER"), TEXT("EQUIP"), Cyan), 1.3f, false);
	Put(Action(DetailsButton, DetailsLabel, TEXT("F"), TEXT("DETAILS"), Steel), 1.0f, false);
	Put(Action(LockButton, LockLabel, TEXT("R"), TEXT("LOCK"), Gold), 0.8f, false);
	Put(Action(DismantleButton, DismantleLabel, TEXT("X"), TEXT("DISMANTLE"), Bad), 1.05f, true);
	Actions->AddChildToVerticalBox(Main);
	Actions->AddChildToVerticalBox(Action(UpgradeButton, UpgradeLabel, TEXT("U"), TEXT("RAISE"), Good))->SetPadding(FMargin(0, 8, 0, 0));
	UpgradeGoodsRow = Make<UWrapBox>(T);
	UpgradeGoodsRow->SetInnerSlotPadding(FVector2D(10.0f, 2.0f));
	Actions->AddChildToVerticalBox(UpgradeGoodsRow)->SetHorizontalAlignment(HAlign_Center);
	EquipButton->OnClicked.AddDynamic(this, &USOInventoryWidget::OnEquip);
	DetailsButton->OnClicked.AddDynamic(this, &USOInventoryWidget::OnDetails);
	LockButton->OnClicked.AddDynamic(this, &USOInventoryWidget::OnLock);
	DismantleButton->OnClicked.AddDynamic(this, &USOInventoryWidget::OnDismantle);
	UpgradeButton->OnClicked.AddDynamic(this, &USOInventoryWidget::OnUpgrade);
	ActionBlock = Actions;
	FrameColumn->AddChildToVerticalBox(Actions)->SetPadding(FMargin(0, 12, 8, 0));
	Frame->SetContent(FrameColumn);
	InspectFrame = Frame;
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

bool USOInventoryWidget::IsArmourSlot(const FString& SlotKey) const
{
	return !SlotKey.IsEmpty() && USOWardrobeData::ArmourSlots().Contains(FName(*SlotKey));
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
	// (the loadout's card: what kind of gun alone, on one line; the class is in its quick look)
	Tile.Tag = bSlot ? KindName(Data).ToUpper() : FString::Printf(TEXT("%s  ·  %s"), *KindName(Data).ToUpper(), *ClassName(Data).ToUpper());
	Tile.Power = W.Power;
	Tile.bEquipped = !bSlot && Inventory && Inventory->IsEquipped(W.Uid);
	Tile.bNew = W.bNew;
	Tile.bLocked = W.bKeep;
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
	Tile.Sub = bSlot ? USOWardrobeData::SlotLabel(A.Slot).ToString().ToUpper() : FString();
	Tile.Tag = FString::Printf(TEXT("%s  ·  %d ARMOUR"), *RarityName(A.Rarity).ToUpper(), Item ? Item->Armor : 0);
	Tile.Power = A.Power;
	Tile.bEquipped = A.bEquipped && !bSlot;
	Tile.bNew = A.bNew;
	Tile.bLeft = !bSlot;
	return Tile;
}

void USOInventoryWidget::Refresh()
{
	if (!Inventory || !WidgetTree || !LeftPanel)
	{
		return;
	}
	FillBanner();
	const bool bLoadout = GetView() == EView::Loadout;
	const bool bCreator = GetView() == EView::Character;
	const bool bJournal = GetView() == EView::Journal;
	for (UWidget* W : { static_cast<UWidget*>(LeftPanel.Get()), static_cast<UWidget*>(RightPanel.Get()) })
	{
		W->SetVisibility(bLoadout ? ESlateVisibility::SelfHitTestInvisible : ESlateVisibility::Collapsed);
	}
	for (UWidget* W : { static_cast<UWidget*>(CategoryPanel.Get()), static_cast<UWidget*>(GridPanel.Get()), static_cast<UWidget*>(InspectPanel.Get()) })
	{
		W->SetVisibility(bLoadout ? ESlateVisibility::Collapsed : ESlateVisibility::SelfHitTestInvisible);
	}
	// the character builder: the stage takes the inspect panel's room, close on the face (no platform under it)
	InspectPanel->SetVisibility(bLoadout || bCreator ? ESlateVisibility::Collapsed : ESlateVisibility::SelfHitTestInvisible);
	if (FloorImage && FloorImage->GetBrush().GetResourceObject())
	{
		FloorImage->SetVisibility(bCreator || bJournal ? ESlateVisibility::Collapsed : ESlateVisibility::HitTestInvisible);
	}
	// the journal is read: its reading pane takes the stand-in's room (and what turns or changes the stand-in goes)
	if (PreviewImage)
	{
		PreviewImage->SetVisibility(bJournal ? ESlateVisibility::Collapsed : ESlateVisibility::HitTestInvisible);
	}
	if (DragHint)
	{
		DragHint->SetVisibility(bJournal ? ESlateVisibility::Collapsed : ESlateVisibility::SelfHitTestInvisible);
	}
	if (BodyToggle)
	{
		BodyToggle->SetVisibility(bJournal ? ESlateVisibility::Collapsed : ESlateVisibility::Visible);   // (a button: it is clicked)
	}
	if (bLoadout)
	{
		FillLoadout();
	}
	else if (bCreator)
	{
		FillCharacter();
	}
	else
	{
		FillArmoury();
	}
	FillTabs();
	FillHints();
	FillCompare();
	SyncPreview();
	UpdateLayout(LaidOutWidth > 100.0f ? LaidOutWidth : 1920.0f);
}

void USOInventoryWidget::FillBanner()
{
	UWidgetTree* T = WidgetTree;
	const USOProgressionTable& Rules = USOProgressionTable::Get();
	const int32 Level = Inventory->GetLevel();
	const int32 Need = FMath::Max(1, Rules.XpForLevel(Level));
	const bool bTop = Level >= Rules.MaxLevel;
	LevelText->SetText(FText::FromString(FString::Printf(TEXT("LEVEL %d"), Level)));
	XpText->SetText(FText::FromString(bTop ? FString(TEXT("THE HIGHEST LEVEL")) : FString::Printf(TEXT("%s / %s"), *Number(Inventory->GetXp()), *Number(Need))));
	if (UMaterialInstanceDynamic* MID = XpBar ? XpBar->GetDynamicMaterial() : nullptr)
	{
		const float Share = bTop ? 1.0f : FMath::Clamp(static_cast<float>(Inventory->GetXp()) / Need, 0.0f, 1.0f);
		MID->SetVectorParameterValue(TEXT("Values"), FLinearColor(Share, Share, 24.0f, 0.0f));
	}
	const bool bFemale = Inventory->GetBody() == TEXT("female");
	MaleLabel->SetColorAndOpacity(FSlateColor(bFemale ? Dim : Ink));
	FemaleLabel->SetColorAndOpacity(FSlateColor(bFemale ? Ink : Dim));
	Currencies->ClearChildren();
	auto Currency = [&](int32 Which, const FLinearColor& Color, const FString& Value, const TCHAR* Label)
	{
		UHorizontalBox* C = Make<UHorizontalBox>(T);
		C->AddChildToHorizontalBox(Glyph(T, this, Which, Color, 22.0f))->SetVerticalAlignment(VAlign_Center);
		UVerticalBox* V = Make<UVerticalBox>(T);
		V->AddChildToVerticalBox(Text(T, Value, 15, Ink, FaceBold));
		V->AddChildToVerticalBox(Text(T, Label, 7, Dim, FaceBold, 280));
		UHorizontalBoxSlot* VS = C->AddChildToHorizontalBox(V);
		VS->SetPadding(FMargin(9, 0, 0, 0));
		VS->SetVerticalAlignment(VAlign_Center);
		Currencies->AddChildToHorizontalBox(C)->SetPadding(FMargin(0, 0, 34, 0));
	};
	Currency(1, Gold, Number(Inventory->GetCredits()), TEXT("CREDITS"));
	Currency(2, Cyan, Number(Inventory->GetAlloy()), TEXT("ALLOY"));
	Currency(3, Soft, FString::Printf(TEXT("%d / %d"), Inventory->GetItems().Num(), USOLootLibrary::VaultCap), TEXT("VAULT"));
	if (UHorizontalBoxSlot* Last = Currencies->GetChildrenCount() > 0 ? Cast<UHorizontalBoxSlot>(Currencies->GetChildAt(Currencies->GetChildrenCount() - 1)->Slot) : nullptr)
	{
		Last->SetPadding(FMargin(0, 0, 26, 0));                 // (the power's plate after it)
	}
	PowerText->SetText(FText::AsNumber(Inventory->GetPower()));
}

void USOInventoryWidget::FillLoadout()
{
	UWidgetTree* T = WidgetTree;
	ListTiles.Reset();
	auto Add = [&](UVerticalBox* Column, const FSOTileInfo& Info, float Gap)
	{
		USOInventoryTile* Tile = CreateWidget<USOInventoryTile>(this, USOInventoryTile::StaticClass());
		Tile->Setup(this, Info);
		Column->AddChildToVerticalBox(Tile)->SetPadding(FMargin(0, 0, 0, Gap));
	};

	// the arsenal: the three guns and the hands
	LeftPanel->ClearChildren();
	LeftPanel->AddChildToVerticalBox(Header(T, TEXT("ARSENAL"), FString::Printf(TEXT("%d OWNED"), Inventory->GetItems().Num())))->SetPadding(FMargin(0, 0, 0, 12));
	for (int32 SlotId = 0; SlotId < USOInventoryComponent::NumSlots; ++SlotId)
	{
		FSOTileInfo Info;
		const FSOWeaponInstance* W = Inventory->GetEquipped(SlotId);
		if (W)
		{
			Info = WeaponTile(*W, true);
		}
		else
		{
			Info.Kind = TEXT("wslot");
			Info.Title = TEXT("Empty");
			Info.Tag = TEXT("NOTHING CARRIED");
			Info.Rarity = Dim;
			Info.bEmpty = true;
		}
		Info.Sub = SlotName(SlotId).ToUpper();
		Info.bInHand = W && SlotId == Inventory->GetActiveSlot();
		Info.Key = FString::FromInt(SlotId);
		Info.bLeft = true;
		Add(LeftPanel, Info, 12.0f);
	}
	{
		const USOMeleeTable* Melee = USOMeleeTable::Get();
		const FName In = Inventory->GetMeleeSlot();
		const FSOMeleeStyle* Style = Melee ? Melee->Find(In.IsNone() ? FName(TEXT("fists")) : In) : nullptr;
		FSOTileInfo Info;
		Info.Kind = TEXT("mslot");
		Info.Key = TEXT("melee");
		Info.Title = Style && !Style->Name.IsEmpty() ? Style->Name.ToString() : TEXT("Fists");
		Info.Icon = Style ? Style->Icon.LoadSynchronous() : nullptr;
		Info.Sub = TEXT("MELEE");
		Info.Tag = In.IsNone() ? TEXT("HAND TO HAND") : TEXT("BLADE  ·  HAND TO HAND");
		Info.Rarity = In.IsNone() ? Steel : BladeLight;
		Info.Glyph = In.IsNone() ? 11 : 13;
		Info.bLeft = true;
		Add(LeftPanel, Info, 0.0f);
	}

	// the armour, slot by slot
	RightPanel->ClearChildren();
	RightPanel->AddChildToVerticalBox(Header(T, TEXT("ARMOUR"), FString::Printf(TEXT("RATING %d"), Inventory->GetArmorRating())))->SetPadding(FMargin(0, 0, 0, 12));
	for (const FName SlotId : USOWardrobeData::ArmourSlots())
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
			Info.bEmpty = true;
		}
		Info.Key = SlotId.ToString();
		Info.bLeft = false;
		Add(RightPanel, Info, 10.0f);
	}
	QuickLook->SetVisibility(ESlateVisibility::Collapsed);
	QuickKey.Reset();
	FillAttributes(nullptr);
	if (bKeyFocus)
	{
		ApplyFocus();
	}
}

void USOInventoryWidget::FillArmoury()
{
	UWidgetTree* T = WidgetTree;
	const EView View = GetView();
	const USOLootTables* Tables = USOLootLibrary::GetTables();
	ListTiles.Reset();
	QuickLook->SetVisibility(ESlateVisibility::Collapsed);
	QuickKey.Reset();
	const TArray<FSOTileInfo> All = ListItems();
	if (!SelectedKey.IsEmpty() && !All.ContainsByPredicate([this](const FSOTileInfo& I) { return I.Key == SelectedKey; }))
	{
		SelectedKey.Reset();                                      // (not in this category: the first one that is)
	}
	const int32 PerPage = CardsPerPage();
	const bool bRows = bListView || View == EView::Journal;
	const int32 Pages = FMath::Max(1, (All.Num() + PerPage - 1) / PerPage);
	Page = FMath::Clamp(Page, 0, Pages - 1);
	if (SelectedKey.IsEmpty() && All.Num() > 0)
	{
		SelectedKey = All[FMath::Min(Page * PerPage, All.Num() - 1)].Key;
		if (View == EView::Journal)
		{
			// the journal opens on the first page not yet read, else the first learned
			const FSOTileInfo* First = All.FindByPredicate([](const FSOTileInfo& I) { return I.bNew; });
			First = First ? First : All.FindByPredicate([](const FSOTileInfo& I) { return !I.bEmpty; });
			if (First)
			{
				SelectedKey = First->Key;
				Page = All.IndexOfByPredicate([&](const FSOTileInfo& I) { return I.Key == First->Key; }) / FMath::Max(PerPage, 1);
			}
		}
	}

	// --- the column: the view's name and its line, the arsenal's slots, the categories with their counts ---------------
	CategoryPanel->ClearChildren();
	FString Title, Line;
	if (View == EView::Arsenal)
	{
		Title = OpenSlotId == TEXT("melee") ? FString(TEXT("MELEE")) : SlotName(FCString::Atoi(*OpenSlotId)).ToUpper();
		Line = SlotLine(OpenSlotId);
	}
	else if (View == EView::Armour)
	{
		Title = TEXT("ARMOUR");
		Line = TEXT("WORN OVER THE UNDERSUIT");
	}
	else if (View == EView::Journal)
	{
		Title = TEXT("JOURNAL");
		Line = TEXT("WHAT WE HAVE LEARNED");
	}
	else
	{
		Title = TEXT("INVENTORY");
		Line = TEXT("WHAT YOU HAVE GATHERED");
	}
	CategoryPanel->AddChildToVerticalBox(Fit(Text(T, Title, 26, Ink, FaceCond, 140)));
	{
		UHorizontalBox* Under = Make<UHorizontalBox>(T);
		Under->AddChildToHorizontalBox(Sized(T, Box(T, FSlateColorBrush(Cyan), FMargin(0)), 3.0f, 10.0f))->SetVerticalAlignment(VAlign_Center);
		UHorizontalBoxSlot* L = Under->AddChildToHorizontalBox(Fit(Text(T, Line, 8, Soft, FaceBold, 220)));
		L->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
		L->SetPadding(FMargin(8, 0, 0, 0));
		L->SetVerticalAlignment(VAlign_Center);
		CategoryPanel->AddChildToVerticalBox(Under)->SetPadding(FMargin(0, 2, 0, 14));
	}
	auto AddRow = [&](const FString& Key, const FString& Label, int32 Count, bool bActive, bool bNew)
	{
		USOArmouryButton* B = CreateWidget<USOArmouryButton>(this, USOArmouryButton::StaticClass());
		B->Setup(this, ESOArmouryControl::Row, Key, Label, bActive);
		B->Count = Number(Count);
		B->bDim = Count == 0;
		B->bNew = bNew;
		B->Width = CatWidth;
		CategoryPanel->AddChildToVerticalBox(B)->SetPadding(FMargin(0, 0, 0, 2));
	};
	auto Heading = [&](const FString& Label) { CategoryPanel->AddChildToVerticalBox(Header(T, Label))->SetPadding(FMargin(0, 14, 0, 8)); };
	if (View == EView::Arsenal)
	{
		// the four slots as tiles, each with what is carried in it
		UHorizontalBox* Tiles = Make<UHorizontalBox>(T);
		static const TCHAR* Keys[] = { TEXT("0"), TEXT("1"), TEXT("2"), TEXT("melee") };
		bool bNewIn[USOInventoryComponent::NumSlots] = {};
		for (const FSOWeaponInstance& W : Inventory->GetItems())
		{
			if (const USOWeaponData* Data = W.bNew ? ArchetypeOf(W) : nullptr)
			{
				bNewIn[FMath::Clamp(Data->Slot, 0, USOInventoryComponent::NumSlots - 1)] = true;
			}
		}
		const float TileW = (CatWidth - 3.0f * 5.0f) / 4.0f;
		for (int32 i = 0; i < 4; ++i)
		{
			USOArmouryButton* B = CreateWidget<USOArmouryButton>(this, USOArmouryButton::StaticClass());
			const FString Key = Keys[i];
			B->Setup(this, ESOArmouryControl::SlotTile, Key, i < 3 ? SlotName(i).ToUpper() : FString(TEXT("MELEE")), Key == OpenSlotId);
			if (i < 3)
			{
				const FSOWeaponInstance* W = Inventory->GetEquipped(i);
				const USOWeaponData* Data = W ? ArchetypeOf(*W) : nullptr;
				B->Icon = Data ? Data->Icon.LoadSynchronous() : nullptr;
				B->bNew = bNewIn[i];
			}
			else
			{
				const USOMeleeTable* Melee = USOMeleeTable::Get();
				const FName In = Inventory->GetMeleeSlot();
				const FSOMeleeStyle* Style = Melee ? Melee->Find(In.IsNone() ? FName(TEXT("fists")) : In) : nullptr;
				B->Icon = Style ? Style->Icon.LoadSynchronous() : nullptr;
				B->GlyphIndex = In.IsNone() ? 11 : 13;
			}
			B->Width = TileW;
			Tiles->AddChildToHorizontalBox(B)->SetPadding(FMargin(i > 0 ? 5.0f : 0.0f, 0, 0, 0));
		}
		CategoryPanel->AddChildToVerticalBox(Tiles)->SetPadding(FMargin(0, 0, 0, 14));
		if (IsWeaponSlot(OpenSlotId))
		{
			// every family of the slot, then every origin, with how many of each are owned
			const int32 SlotId = FCString::Atoi(*OpenSlotId);
			TMap<FName, int32> ByFamily, ByOrigin;
			TSet<FName> NewFamily, NewOrigin;
			int32 Total = 0;
			for (const FSOWeaponInstance& W : Inventory->GetItems())
			{
				const USOWeaponData* Data = ArchetypeOf(W);
				if (Data && FMath::Clamp(Data->Slot, 0, USOInventoryComponent::NumSlots - 1) == SlotId)
				{
					++Total;
					ByFamily.FindOrAdd(Data->Family)++;
					ByOrigin.FindOrAdd(Data->Origin)++;
					if (W.bNew)
					{
						NewFamily.Add(Data->Family);
						NewOrigin.Add(Data->Origin);
					}
				}
			}
			AddRow(FString(), TEXT("ALL"), Total, Filter.IsEmpty(), false);
			if (Tables)
			{
				for (const FSOGunGroup& Family : Tables->Families)
				{
					if (Family.Slot == SlotId)
					{
						const FString Key = TEXT("family:") + Family.Id.ToString();
						AddRow(Key, Family.Name.ToString().ToUpper(), ByFamily.FindRef(Family.Id), Filter == Key, NewFamily.Contains(Family.Id));
					}
				}
				Heading(TEXT("ORIGIN"));
				for (const FSOGunGroup& Origin : Tables->Origins)
				{
					const FString Key = TEXT("origin:") + Origin.Id.ToString();
					AddRow(Key, Origin.Name.ToString().ToUpper(), ByOrigin.FindRef(Origin.Id), Filter == Key, NewOrigin.Contains(Origin.Id));
				}
			}
		}
		else
		{
			AddRow(FString(), TEXT("ALL"), All.Num(), true, false);
		}
	}
	else if (View == EView::Journal)
	{
		// every section, with how much of it is learned (of all there is to learn) and a mark where a page waits unread
		const FSOJournalData& Journal = FSOJournalData::Get();
		const FName Open = JournalSection();
		for (const FSOJournalSection& Section : Journal.Sections)
		{
			int32 Learned = 0, Total = 0;
			bool bNew = false;
			for (const FSOJournalEntry& E : Journal.Entries)
			{
				if (E.Section == Section.Id)
				{
					++Total;
					Learned += Inventory->IsJournalOpen(E.Id) ? 1 : 0;
					bNew |= Inventory->IsJournalNew(E.Id);
				}
			}
			USOArmouryButton* B = CreateWidget<USOArmouryButton>(this, USOArmouryButton::StaticClass());
			B->Setup(this, ESOArmouryControl::Row, TEXT("section:") + Section.Id.ToString(), Section.Name.ToUpper(), Section.Id == Open);
			B->Count = Section.Id == TEXT("record") ? FString() : FString::Printf(TEXT("%d/%d"), Learned, Total);
			B->bDim = Learned == 0;
			B->bNew = bNew;
			B->Width = CatWidth;
			CategoryPanel->AddChildToVerticalBox(B)->SetPadding(FMargin(0, 0, 0, 2));
		}
		// how much of all of it is known, at the column's foot
		int32 Known = 0;
		for (const FSOJournalEntry& E : Journal.Entries)
		{
			Known += Inventory->IsJournalOpen(E.Id) ? 1 : 0;
		}
		CategoryPanel->AddChildToVerticalBox(Make<USpacer>(T))->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
		CategoryPanel->AddChildToVerticalBox(Header(T, TEXT("LEARNED"), FString::Printf(TEXT("%d / %d"), Known, Journal.Entries.Num())))->SetPadding(FMargin(0, 0, 0, 8));
		UImage* Bar = StatBar(T, this, Journal.Entries.Num() > 0 ? static_cast<float>(Known) / Journal.Entries.Num() : 0.0f, 0.0f, 20, Cyan);
		CategoryPanel->AddChildToVerticalBox(Sized(T, Bar, CatWidth, 8.0f));
	}
	else if (View == EView::Armour)
	{
		// the seven slots, each with how many pieces are owned for it
		const USOWardrobeData* Wardrobe = USOWardrobeData::Get(Inventory->GetBody());
		for (const FName SlotId : USOWardrobeData::ArmourSlots())
		{
			int32 Count = 0;
			bool bNew = false;
			for (const FSOArmorInstance& A : Inventory->GetArmor())
			{
				if (A.Slot == SlotId && (!Wardrobe || Wardrobe->Find(A.Slot, A.Item)))
				{
					++Count;
					bNew |= A.bNew;
				}
			}
			AddRow(TEXT("slot:") + SlotId.ToString(), USOWardrobeData::SlotLabel(SlotId).ToString().ToUpper(), Count, SlotId.ToString() == OpenSlotId, bNew);
		}
	}
	else
	{
		// every kind of collected item, with how many different ones are held
		TMap<ESOGoodsKind, int32> ByKind;
		TSet<ESOGoodsKind> NewKind;
		int32 Total = 0;
		for (const FSOGoodsStack& Stack : Inventory->GetGoods())
		{
			if (const FSOGoodsInfo* Info = Tables && Stack.Count > 0 ? Tables->FindGoods(Stack.Id) : nullptr)
			{
				++Total;
				ByKind.FindOrAdd(Info->Kind)++;
				if (Stack.bNew)
				{
					NewKind.Add(Info->Kind);
				}
			}
		}
		AddRow(FString(), TEXT("ALL"), Total, Filter.IsEmpty(), NewKind.Num() > 0);
		for (ESOGoodsKind Kind : { ESOGoodsKind::Material, ESOGoodsKind::Consumable, ESOGoodsKind::Key, ESOGoodsKind::Relic })
		{
			const FString Key = TEXT("kind:") + GoodsKindId(Kind);
			AddRow(Key, GoodsKindName(Kind, true), ByKind.FindRef(Kind), Filter == Key, NewKind.Contains(Kind));
		}
	}
	// the comparison's key at the column's foot: a gun with another carried in its slot
	if (View == EView::Arsenal && IsWeaponSlot(OpenSlotId))
	{
		if (const FSOWeaponInstance* Carried = Inventory->GetEquipped(FCString::Atoi(*OpenSlotId)))
		{
			CategoryPanel->AddChildToVerticalBox(Make<USpacer>(T))->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
			FPlate KeyPlate;
			KeyPlate.Cut = 10.0f;
			KeyPlate.Fill = FLinearColor(0.006f, 0.009f, 0.018f, 0.9f);
			KeyPlate.FillLow = FLinearColor(0.004f, 0.006f, 0.012f, 0.92f);
			KeyPlate.Edge = FLinearColor(1.0f, 1.0f, 1.0f, 0.12f);
			KeyPlate.TopLight = 0.6f;
			UBorder* KeyBox = Box(T, PlateBrush(this, KeyPlate), FMargin(12, 10, 12, 10));
			UHorizontalBox* Row = Make<UHorizontalBox>(T);
			const USOWeaponData* Data = ArchetypeOf(*Carried);
			if (UTexture2D* Icon = Data ? Data->Icon.LoadSynchronous() : nullptr)
			{
				UImage* Pic = Make<UImage>(T);
				Pic->SetBrushFromTexture(Icon, false);
				Pic->SetVisibility(ESlateVisibility::HitTestInvisible);
				Row->AddChildToHorizontalBox(Sized(T, Pic, 60.0f, 30.0f))->SetVerticalAlignment(VAlign_Center);
			}
			UVerticalBox* Words = Make<UVerticalBox>(T);
			UHorizontalBox* Hold = Make<UHorizontalBox>(T);
			Hold->AddChildToHorizontalBox(Text(T, TEXT("COMPARE"), 10, Ink, FaceBold, 220))->SetVerticalAlignment(VAlign_Center);
			UHorizontalBoxSlot* HoldKey = Hold->AddChildToHorizontalBox(KeyCap(T, TEXT("C")));
			HoldKey->SetPadding(FMargin(8, 0, 0, 0));
			HoldKey->SetVerticalAlignment(VAlign_Center);
			UHorizontalBoxSlot* HoldWord = Hold->AddChildToHorizontalBox(Text(T, TEXT("HOLD"), 7, Dim, FaceBold, 160));
			HoldWord->SetPadding(FMargin(5, 0, 0, 0));
			HoldWord->SetVerticalAlignment(VAlign_Center);
			Words->AddChildToVerticalBox(Hold);
			Words->AddChildToVerticalBox(Fit(Text(T, TEXT("AGAINST ") + Carried->Name.ToUpper(), 7, Dim, FaceBold, 160)))->SetPadding(FMargin(0, 4, 0, 0));
			UHorizontalBoxSlot* WordsSlot = Row->AddChildToHorizontalBox(Words);
			WordsSlot->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
			WordsSlot->SetPadding(FMargin(10, 0, 0, 0));
			WordsSlot->SetVerticalAlignment(VAlign_Center);
			KeyBox->SetContent(Row);
			CategoryPanel->AddChildToVerticalBox(KeyBox);
		}
	}

	// --- the grid: its head (what is shown, the order, the view, how many), the cards of this page, the pages ---------
	GridPanel->ClearChildren();
	{
		FString Shown;
		const FString Rest = Filter.Contains(TEXT(":")) ? Filter.RightChop(Filter.Find(TEXT(":")) + 1) : FString();
		const FSOGunGroup* Group = !Tables || Rest.IsEmpty() ? nullptr : Filter.StartsWith(TEXT("family:")) ? Tables->FindFamily(FName(*Rest)) : Filter.StartsWith(TEXT("origin:")) ? Tables->FindOrigin(FName(*Rest)) : nullptr;
		if (View == EView::Arsenal)
		{
			Shown = Group ? FString::Printf(TEXT("%s  ·  %s"), *Group->Name.ToString().ToUpper(), *Title) : FString::Printf(TEXT("ALL %s"), *Title);
		}
		else if (View == EView::Armour)
		{
			Shown = FString::Printf(TEXT("%s  ·  ARMOUR"), *USOWardrobeData::SlotLabel(FName(*OpenSlotId)).ToString().ToUpper());
		}
		else if (View == EView::Journal)
		{
			const FSOJournalSection* Section = FSOJournalData::Get().FindSection(JournalSection());
			Shown = Section ? FString::Printf(TEXT("%s  ·  %s"), *Section->Name.ToUpper(), *Section->Line.ToUpper()) : FString(TEXT("JOURNAL"));
		}
		else
		{
			Shown = Filter.IsEmpty() ? FString(TEXT("EVERYTHING GATHERED")) : Rest == TEXT("consumable") ? GoodsKindName(ESOGoodsKind::Consumable, true)
				: Rest == TEXT("key") ? GoodsKindName(ESOGoodsKind::Key, true) : Rest == TEXT("relic") ? GoodsKindName(ESOGoodsKind::Relic, true) : GoodsKindName(ESOGoodsKind::Material, true);
		}
		FPlate HeadPlate;
		HeadPlate.Cut = 7.0f;
		HeadPlate.Fill = FLinearColor(0.006f, 0.009f, 0.018f, 0.88f);
		HeadPlate.FillLow = FLinearColor(0.004f, 0.006f, 0.012f, 0.9f);
		HeadPlate.Edge = FLinearColor(1.0f, 1.0f, 1.0f, 0.11f);
		UBorder* Head = Box(T, PlateBrush(this, HeadPlate), FMargin(12, 5, 8, 5));
		UHorizontalBox* Row = Make<UHorizontalBox>(T);
		const FSOJournalSection* HeadSection = View == EView::Journal ? FSOJournalData::Get().FindSection(JournalSection()) : nullptr;
		Row->AddChildToHorizontalBox(Glyph(T, this, HeadSection ? HeadSection->Glyph : View == EView::Goods ? 2 : 3, HeadSection ? HeadSection->Color : Soft, 14.0f))->SetVerticalAlignment(VAlign_Center);
		UHorizontalBoxSlot* Name = Row->AddChildToHorizontalBox(Fit(Text(T, Shown, 9, Ink, FaceBold, 220)));
		Name->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
		Name->SetPadding(FMargin(10, 0, 10, 0));
		Name->SetVerticalAlignment(VAlign_Center);
		auto Tool = [&](const FString& Key, const FString& Label, bool bActive, int32 Drawing, float Gap)
		{
			USOArmouryButton* B = CreateWidget<USOArmouryButton>(this, USOArmouryButton::StaticClass());
			B->Setup(this, ESOArmouryControl::Tool, Key, Label, bActive);
			B->Drawing = Drawing;
			UHorizontalBoxSlot* S = Row->AddChildToHorizontalBox(B);
			S->SetPadding(FMargin(Gap, 0, 0, 0));
			S->SetVerticalAlignment(VAlign_Center);
		};
		if (View != EView::Journal)
		{
			Tool(TEXT("sort"), FString::Printf(TEXT("SORT  ·  %s"), SortName(SortMode, View == EView::Goods)), false, 0, 0.0f);
			Tool(TEXT("grid"), FString(), !bListView, 1, 8.0f);
			Tool(TEXT("list"), FString(), bListView, 2, 4.0f);
		}
		const int32 Open = All.FilterByPredicate([](const FSOTileInfo& I) { return !I.bEmpty; }).Num();
		const FString Count = View == EView::Arsenal && IsWeaponSlot(OpenSlotId) ? FString::Printf(TEXT("%d / %d"), Inventory->GetItems().Num(), USOLootLibrary::VaultCap)
			: View == EView::Journal ? FString::Printf(TEXT("%d / %d"), Open, All.Num()) : FString::Printf(TEXT("%d"), All.Num());
		UHorizontalBoxSlot* CountSlot = Row->AddChildToHorizontalBox(Text(T, Count, 9, Dim, FaceBold, 120));
		CountSlot->SetPadding(FMargin(12, 0, 4, 0));
		CountSlot->SetVerticalAlignment(VAlign_Center);
		Head->SetContent(Row);
		GridPanel->AddChildToVerticalBox(Sized(T, Head, 0.0f, 38.0f))->SetPadding(FMargin(0, 0, 0, 12));
	}
	const int32 From = Page * PerPage, To = FMath::Min(All.Num(), From + PerPage);
	auto MakeTile = [&](FSOTileInfo Info, float W)
	{
		Info.bActive = Info.Key == SelectedKey;
		Info.bLeft = true;
		USOInventoryTile* Tile = CreateWidget<USOInventoryTile>(this, USOInventoryTile::StaticClass());
		Tile->Setup(this, Info);
		Tile->Width = W;
		ListTiles.Add(Tile);
		return Tile;
	};
	if (bRows)
	{
		for (int32 i = From; i < To; ++i)
		{
			GridPanel->AddChildToVerticalBox(MakeTile(All[i], GridWidth))->SetPadding(FMargin(0, 0, 0, 6));
		}
	}
	else
	{
		for (int32 Start = From; Start < To; Start += Columns)
		{
			UHorizontalBox* Row = Make<UHorizontalBox>(T);
			for (int32 i = Start; i < FMath::Min(To, Start + Columns); ++i)
			{
				Row->AddChildToHorizontalBox(MakeTile(All[i], CellWidth))->SetPadding(FMargin(i > Start ? CellGap : 0.0f, 0, 0, 0));
			}
			GridPanel->AddChildToVerticalBox(Row)->SetPadding(FMargin(0, 0, 0, CellGap));
		}
	}
	if (All.Num() == 0)
	{
		UTextBlock* None = Text(T, View == EView::Goods ? TEXT("Nothing of this kind gathered yet. Kills, elites, bosses and caches pay into here.")
			: View == EView::Journal ? TEXT("Nothing in this section yet.")
			: TEXT("Nothing of this kind owned yet. What the operations and the caches give you comes here."), 12, Dim, FaceItalic);
		None->SetAutoWrapText(true);
		GridPanel->AddChildToVerticalBox(None)->SetPadding(FMargin(4, 8, 4, 0));
	}
	if (Pages > 1)
	{
		// the pages: the arrows and the numbers about the one shown
		UHorizontalBox* Bar = Make<UHorizontalBox>(T);
		auto PageButton = [&](const FString& Key, const FString& Label, bool bActive, bool bDim)
		{
			USOArmouryButton* B = CreateWidget<USOArmouryButton>(this, USOArmouryButton::StaticClass());
			B->Setup(this, ESOArmouryControl::Page, Key, Label, bActive);
			B->bDim = bDim;
			B->Width = 30.0f;
			Bar->AddChildToHorizontalBox(B)->SetPadding(FMargin(3, 0, 3, 0));
		};
		PageButton(TEXT("prev"), TEXT("‹"), false, Page == 0);
		const int32 First = FMath::Clamp(Page - 3, 0, FMath::Max(0, Pages - 7));
		for (int32 p = First; p < FMath::Min(Pages, First + 7); ++p)
		{
			PageButton(FString::FromInt(p + 1), FString::FromInt(p + 1), p == Page, false);
		}
		PageButton(TEXT("next"), TEXT("›"), false, Page == Pages - 1);
		GridPanel->AddChildToVerticalBox(Bar)->SetHorizontalAlignment(HAlign_Center);
	}

	// --- the inspect panel ---------------------------------------------------------------------------------------------
	InspectPanel->ClearChildren();
	InspectPanel->AddChildToVerticalBox(InspectFrame)->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
	FillInspect();
}

void USOInventoryWidget::FillTabs()
{
	UWidgetTree* T = WidgetTree;
	TabRow->ClearChildren();
	const bool bNewGun = Inventory->GetItems().ContainsByPredicate([](const FSOWeaponInstance& W) { return W.bNew; });
	const bool bNewArmour = Inventory->GetArmor().ContainsByPredicate([](const FSOArmorInstance& A) { return A.bNew; });
	const bool bNewGoods = Inventory->GetGoods().ContainsByPredicate([](const FSOGoodsStack& G) { return G.bNew; });
	const EView View = GetView();
	TabRow->AddChildToHorizontalBox(KeyCap(T, TEXT("Q")))->SetVerticalAlignment(VAlign_Center);
	auto Tab = [&](const FString& Key, const FString& Label, bool bActive, bool bNew)
	{
		USOArmouryButton* B = CreateWidget<USOArmouryButton>(this, USOArmouryButton::StaticClass());
		B->Setup(this, ESOArmouryControl::Tab, Key, Label, bActive);
		B->bNew = bNew;
		TabRow->AddChildToHorizontalBox(B)->SetPadding(FMargin(4, 0, 4, 0));
	};
	Tab(FString(), TEXT("LOADOUT"), View == EView::Loadout, false);
	Tab(TEXT("arsenal"), TEXT("ARSENAL"), View == EView::Arsenal, bNewGun);
	Tab(TEXT("armour"), TEXT("ARMOUR"), View == EView::Armour, bNewArmour);
	Tab(TEXT("goods"), TEXT("INVENTORY"), View == EView::Goods, bNewGoods);
	Tab(TEXT("character"), TEXT("CHARACTER"), View == EView::Character, !Inventory->IsCharacterMade());
	Tab(TEXT("journal"), TEXT("JOURNAL"), View == EView::Journal, Inventory->HasJournalNew());
	TabRow->AddChildToHorizontalBox(KeyCap(T, TEXT("E")))->SetVerticalAlignment(VAlign_Center);
}

void USOInventoryWidget::FillHints()
{
	UWidgetTree* T = WidgetTree;
	HintRow->ClearChildren();
	auto Add = [&](const TCHAR* Key, const TCHAR* Label) { HintRow->AddChildToHorizontalBox(Hint(T, Key, Label)); };
	switch (GetView())
	{
	case EView::Loadout:
		Add(TEXT("CLICK"), TEXT("OPEN"));
		Add(TEXT("1-3"), TEXT("IN HAND"));
		Add(TEXT("ESC"), TEXT("CLOSE"));
		return;
	case EView::Arsenal:
		Add(TEXT("A D"), TEXT("SLOT"));
		Add(TEXT("ENTER"), TEXT("EQUIP"));
		if (IsWeaponSlot(OpenSlotId))
		{
			Add(TEXT("F"), TEXT("DETAILS"));
			Add(TEXT("C"), TEXT("COMPARE"));
			Add(TEXT("R"), TEXT("LOCK"));
			Add(TEXT("X"), TEXT("DISMANTLE"));
			Add(TEXT("U"), TEXT("RAISE"));
		}
		break;
	case EView::Armour:
		Add(TEXT("A D"), TEXT("SLOT"));
		Add(TEXT("ENTER"), TEXT("WEAR"));
		Add(TEXT("U"), TEXT("RAISE"));
		break;
	case EView::Goods:
		Add(TEXT("A D"), TEXT("KIND"));
		Add(TEXT("ENTER"), TEXT("USE"));
		break;
	case EView::Character:
		Add(TEXT("A D"), TEXT("GROUP"));
		Add(TEXT("W S"), TEXT("CHOOSE"));
		Add(TEXT("\u2039 \u203A"), TEXT("ADJUST"));
		Add(TEXT("R"), TEXT("RESET"));
		Add(TEXT("ESC"), TEXT("DONE"));
		return;
	case EView::Journal:
		Add(TEXT("A D"), TEXT("SECTION"));
		Add(TEXT("W S"), TEXT("CHOOSE"));
		Add(TEXT("ESC"), TEXT("BACK"));
		return;
	}
	Add(TEXT("Z"), TEXT("SORT"));
	Add(TEXT("ESC"), TEXT("BACK"));
}

void USOInventoryWidget::FillAttributes(const FSOArmorInstance* TryOn)
{
	UWidgetTree* T = WidgetTree;
	if (!AttributeColumn)
	{
		return;
	}
	AttributeColumn->ClearChildren();
	const USOAttributeTable& Rules = USOAttributeTable::Get();
	const FSOAttributePoints Have = Inventory->GetAttributePoints();
	FSOAttributePoints Would = Have;
	if (TryOn)
	{
		// what wearing it would change: the piece worn there off, this one on
		const FSOArmorInstance* Worn = Inventory->GetEquippedArmor(TryOn->Slot);
		if (!Worn || Worn->Uid != TryOn->Uid)
		{
			const FSOAttributePoints Off = Worn ? Inventory->GetArmorPoints(*Worn) : FSOAttributePoints();
			const FSOAttributePoints On = Inventory->GetArmorPoints(*TryOn);
			for (int32 i = 0; i < static_cast<int32>(ESOAttribute::Count); ++i)
			{
				const ESOAttribute A = static_cast<ESOAttribute>(i);
				Would.At(A) = FMath::Clamp(Have.Get(A) - Off.Get(A) + On.Get(A), 0, FMath::RoundToInt(Rules.Max));
			}
		}
	}
	for (int32 i = 0; i < static_cast<int32>(ESOAttribute::Count); ++i)
	{
		const ESOAttribute A = static_cast<ESOAttribute>(i);
		const int32 Now = Have.Get(A), Then = Would.Get(A);
		const bool bFull = Now >= Rules.Max;
		UVerticalBox* Cell = Make<UVerticalBox>(T);
		Cell->AddChildToVerticalBox(Glyph(T, this, 5 + i, bFull ? Gold : Cyan, 24.0f))->SetHorizontalAlignment(HAlign_Center);
		UHorizontalBox* Figure = Make<UHorizontalBox>(T);
		Figure->AddChildToHorizontalBox(Text(T, FString::FromInt(Now), 20, bFull ? Gold : Ink, FaceCond))->SetVerticalAlignment(VAlign_Center);
		if (Then != Now)
		{
			UHorizontalBoxSlot* D = Figure->AddChildToHorizontalBox(Text(T, FString::Printf(TEXT("%+d"), Then - Now), 10, Then > Now ? Good : Bad, FaceBold));
			D->SetPadding(FMargin(4, 0, 0, 0));
			D->SetVerticalAlignment(VAlign_Center);
		}
		Cell->AddChildToVerticalBox(Figure)->SetHorizontalAlignment(HAlign_Center);
		Cell->AddChildToVerticalBox(Text(T, Rules.Rule(A).Name.ToString().ToUpper(), 7, Dim, FaceBold, 220))->SetHorizontalAlignment(HAlign_Center);
		UVerticalBoxSlot* BarSlot = Cell->AddChildToVerticalBox(Sized(T, StatBar(T, this, Now / Rules.Max, Then / Rules.Max, 10, bFull ? Gold : Cyan), 58.0f, 3.0f));
		BarSlot->SetHorizontalAlignment(HAlign_Center);
		BarSlot->SetPadding(FMargin(0, 5, 0, 0));
		Cell->SetToolTipText(Rules.Rule(A).Effect);
		AttributeColumn->AddChildToVerticalBox(Cell)->SetPadding(FMargin(0, 0, 0, 20));
	}
}

FString USOInventoryWidget::ShownKey() const
{
	return HoverKey.IsEmpty() ? SelectedKey : HoverKey;
}

void USOInventoryWidget::SetActions(bool bShow)
{
	if (ActionBlock)
	{
		ActionBlock->SetVisibility(bShow ? ESlateVisibility::Visible : ESlateVisibility::Collapsed);
	}
}

void USOInventoryWidget::FillInspect()
{
	if (!Inspect || !Inventory)
	{
		return;
	}
	Inspect->ClearChildren();
	const FString Key = ShownKey();
	const FSOArmorInstance* TryOn = nullptr;
	const USOLootTables* Tables = USOLootLibrary::GetTables();
	if (const FSOWeaponInstance* W = Inventory->Find(Key))
	{
		FillWeaponInspect(*W);
	}
	else if (const FSOArmorInstance* A = Inventory->FindArmor(Key))
	{
		FillArmorInspect(*A);
		TryOn = A;
	}
	else if (Key.StartsWith(TEXT("melee:")))
	{
		const USOMeleeTable* Melee = USOMeleeTable::Get();
		const FName Id(*Key.RightChop(6));
		if (const FSOMeleeStyle* Style = Melee ? Melee->Find(Id) : nullptr)
		{
			FillMeleeInspect(*Style, Id);
		}
	}
	else if (const FSOGoodsInfo* Goods = Tables && Key.StartsWith(TEXT("goods:")) ? Tables->FindGoods(FName(*Key.RightChop(6))) : nullptr)
	{
		FillGoodsInspect(*Goods);
	}
	else if (Key.StartsWith(TEXT("journal:")))
	{
		FillJournalInspect(FName(*Key.RightChop(8)));
	}
	else
	{
		UTextBlock* None = Text(WidgetTree, TEXT("Choose something in the grid to see it here."), 13, Dim, FaceItalic);
		None->SetAutoWrapText(true);
		Inspect->AddChildToVerticalBox(None);
		SetActions(false);
	}
	FillAttributes(TryOn);
	if (InspectScroll)
	{
		InspectScroll->ScrollToStart();
	}
}

void USOInventoryWidget::FillWeaponInspect(const FSOWeaponInstance& W)
{
	UWidgetTree* T = WidgetTree;
	const USOLootTables* Tables = USOLootLibrary::GetTables();
	const USOWeaponData* Data = ArchetypeOf(W);
	const FLinearColor Rarity = RarityColor(W.Rarity);
	const FLinearColor Light = GunLight(Data);
	const float Wide = FMath::Max(200.0f, InspectWidth - 66.0f);  // (the frame's padding and the scroll bar)
	// what it is, its name, who made it, its line
	UTextBlock* Kind = Text(T, FString::Printf(TEXT("%s  ·  %s  ·  %s"), *RarityName(W.Rarity).ToUpper(), *ClassName(Data).ToUpper(), *KindName(Data).ToUpper()), 9, Rarity, FaceBold, 240);
	Kind->SetAutoWrapText(true);
	Inspect->AddChildToVerticalBox(Kind);
	UTextBlock* Name = Text(T, W.Name.ToUpper(), 32, Ink, FaceCond, 40);
	Name->SetAutoWrapText(true);
	Inspect->AddChildToVerticalBox(Name)->SetPadding(FMargin(0, 2, 0, 0));
	if (const FSOGunGroup* Origin = Tables && Data ? Tables->FindOrigin(Data->Origin) : nullptr)
	{
		const FSOGunGroup* Family = Tables->FindFamily(Data->Family);
		const FString Words = Family ? FString::Printf(TEXT("%s  ·  %s"), *Origin->Name.ToString().ToUpper(), *Family->Name.ToString().ToUpper()) : Origin->Name.ToString().ToUpper();
		Inspect->AddChildToVerticalBox(Fit(Text(T, Words, 9, Gold, FaceBold, 220)))->SetPadding(FMargin(0, 2, 0, 0));
	}
	Inspect->AddChildToVerticalBox(Rule(T, Rarity))->SetPadding(FMargin(0, 8, 0, 10));
	if (Data && !Data->Lore.IsEmpty())
	{
		UTextBlock* Lore = Text(T, Data->Lore.ToString(), 11, Soft, FaceItalic);
		Lore->SetAutoWrapText(true);
		Inspect->AddChildToVerticalBox(Lore)->SetPadding(FMargin(0, 0, 0, 8));
	}
	// the gun large (the summary)
	if (UTexture2D* Icon = !bDetails && Data ? Data->Icon.LoadSynchronous() : nullptr)
	{
		UImage* Pic = Make<UImage>(T);
		Pic->SetBrushFromTexture(Icon, false);
		Pic->SetVisibility(ESlateVisibility::HitTestInvisible);
		const float PicW = FMath::Min(Wide, 400.0f);
		UVerticalBoxSlot* PicSlot = Inspect->AddChildToVerticalBox(Sized(T, Pic, PicW, PicW * 0.5f));
		PicSlot->SetHorizontalAlignment(HAlign_Center);
		PicSlot->SetPadding(FMargin(0, 0, 0, 4));
	}

	// power, how far it can be raised, and this copy's particulars
	UHorizontalBox* PowerRow = Make<UHorizontalBox>(T);
	PowerRow->AddChildToHorizontalBox(Glyph(T, this, 4, Gold, 20.0f))->SetVerticalAlignment(VAlign_Center);
	UHorizontalBoxSlot* PowerSlot = PowerRow->AddChildToHorizontalBox(Text(T, FString::FromInt(W.Power), 34, Gold, FaceCond));
	PowerSlot->SetPadding(FMargin(8, 0, 0, 0));
	PowerSlot->SetVerticalAlignment(VAlign_Center);
	UVerticalBox* PowerWords = Make<UVerticalBox>(T);
	PowerWords->AddChildToVerticalBox(Text(T, TEXT("POWER"), 8, Gold, FaceBold, 300));
	PowerWords->AddChildToVerticalBox(Text(T, FString::Printf(TEXT("RAISED UP TO %d"), Inventory->GetPowerCap()), 8, Dim, FaceBold, 160));
	UHorizontalBoxSlot* PowerWordsSlot = PowerRow->AddChildToHorizontalBox(PowerWords);
	PowerWordsSlot->SetPadding(FMargin(10, 0, 0, 0));
	PowerWordsSlot->SetVerticalAlignment(VAlign_Center);
	PowerRow->AddChildToHorizontalBox(Make<USpacer>(T))->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
	UVerticalBox* Particulars = Make<UVerticalBox>(T);
	const FSOSightInfo* Sight = Tables ? Tables->FindSight(W.Sight) : nullptr;
	if (Sight && !Sight->Name.IsEmpty())
	{
		Particulars->AddChildToVerticalBox(Text(T, Sight->Name.ToString().ToUpper(), 8, Soft, FaceBold, 160))->SetHorizontalAlignment(HAlign_Right);
	}
	Particulars->AddChildToVerticalBox(Text(T, FString::Printf(TEXT("ROLLED %d %%"), USOLootLibrary::RollQuality(W)), 8, Soft, FaceBold, 160))->SetHorizontalAlignment(HAlign_Right);
	if (!W.Source.IsEmpty())
	{
		Particulars->AddChildToVerticalBox(Fit(Text(T, W.Source.ToUpper(), 8, Dim, FaceBold, 160)))->SetHorizontalAlignment(HAlign_Right);
	}
	PowerRow->AddChildToHorizontalBox(Sized(T, Particulars, FMath::Min(170.0f, Wide * 0.4f), 0.0f))->SetVerticalAlignment(VAlign_Center);
	Inspect->AddChildToVerticalBox(PowerRow)->SetPadding(FMargin(0, 0, 0, 12));

	// its numbers against the one carried in its slot
	const FSOWeaponInstance* Equipped = Data ? Inventory->GetEquipped(FMath::Clamp(Data->Slot, 0, USOInventoryComponent::NumSlots - 1)) : nullptr;
	const bool bCompare = Equipped && Equipped->Uid != W.Uid;
	const TArray<FStatRow> Mine = GunStats(W, Data);
	const TArray<FStatRow> Theirs = bCompare ? GunStats(*Equipped, ArchetypeOf(*Equipped)) : Mine;
	auto Other = [&](int32 i) { return Theirs.IsValidIndex(i) ? Theirs[i].Value : Mine[i].Value; };
	auto Differs = [&](int32 i) { return bCompare && !FMath::IsNearlyEqual(Mine[i].Value, Other(i), FMath::Abs(Other(i)) * 0.005f + 0.001f); };
	if (bDetails)
	{
		// every number, each against the carried gun's
		Inspect->AddChildToVerticalBox(Header(T, TEXT("PERFORMANCE"), bCompare ? FString::Printf(TEXT("AGAINST %s"), *Equipped->Name.ToUpper().Left(22)) : FString()))->SetPadding(FMargin(0, 0, 0, 10));
		for (int32 i = 0; i < Mine.Num(); ++i)
		{
			const FStatRow& R = Mine[i];
			const bool bDiffers = Differs(i);
			const bool bBetter = bDiffers && (R.bLowerBetter ? R.Value < Other(i) : R.Value > Other(i));
			UHorizontalBox* Line = Make<UHorizontalBox>(T);
			Line->AddChildToHorizontalBox(Sized(T, Text(T, R.Name, 9, Soft, FaceBold, 180), 100.0f, 0.0f))->SetVerticalAlignment(VAlign_Center);
			UHorizontalBoxSlot* BarSlot = Line->AddChildToHorizontalBox(Sized(T, StatBar(T, this, R.Fill(R.Value), bDiffers ? R.Fill(Other(i)) : R.Fill(R.Value), 14, FLinearColor(0.84f, 0.9f, 1.0f, 0.92f)), 0.0f, 8.0f));
			BarSlot->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
			BarSlot->SetVerticalAlignment(VAlign_Center);
			UTextBlock* Value = Text(T, R.Shown, 11, Ink, FaceBold);
			Value->SetJustification(ETextJustify::Right);
			Line->AddChildToHorizontalBox(Sized(T, Value, 80.0f, 0.0f))->SetVerticalAlignment(VAlign_Center);
			UTextBlock* DeltaText = Text(T, bDiffers ? FString::Printf(TEXT("%+.0f%%"), (R.Value / FMath::Max(Other(i), 0.001f) - 1.0f) * 100.0f) : FString(), 9, bBetter ? Good : Bad, FaceBold);
			DeltaText->SetJustification(ETextJustify::Right);
			Line->AddChildToHorizontalBox(Sized(T, DeltaText, 48.0f, 0.0f))->SetVerticalAlignment(VAlign_Center);
			Inspect->AddChildToVerticalBox(Line)->SetPadding(FMargin(0, 3, 0, 3));
		}
		// the perks on a spine of hexagons, the trait of its set or class in gold at its foot
		Inspect->AddChildToVerticalBox(Header(T, TEXT("PERKS"), W.Perks.Num() > 0 ? FString::Printf(TEXT("%d"), W.Perks.Num()) : FString(TEXT("NONE ROLLED"))))->SetPadding(FMargin(0, 14, 0, 10));
		UOverlay* Spine = Make<UOverlay>(T);
		{
			UBorder* Column = Box(T, FSlateColorBrush(FLinearColor::Transparent), FMargin(0, 24, 0, 24));
			Column->SetHorizontalAlignment(HAlign_Center);
			Column->SetVerticalAlignment(VAlign_Fill);
			Column->SetContent(Sized(T, Box(T, FSlateColorBrush(Alpha(Light, 0.3f)), FMargin(0)), 2.0f, 0.0f));
			UOverlaySlot* SpineLine = Spine->AddChildToOverlay(Sized(T, Column, 44.0f, 0.0f));
			SpineLine->SetHorizontalAlignment(HAlign_Left);
			SpineLine->SetVerticalAlignment(VAlign_Fill);
		}
		UVerticalBox* Nodes = Make<UVerticalBox>(T);
		auto Node = [&](int32 Which, const FLinearColor& Color, const FString& Title, const FString& Words, float Gap)
		{
			UHorizontalBox* Row = Make<UHorizontalBox>(T);
			Row->AddChildToHorizontalBox(Hex(T, this, Which, Color, 44.0f))->SetVerticalAlignment(VAlign_Center);
			UVerticalBox* Lines = Make<UVerticalBox>(T);
			Lines->AddChildToVerticalBox(Fit(Text(T, Title, 12, Color == Gold ? Gold : Ink, FaceBold, 60)));
			UTextBlock* Desc = Text(T, Words, 10, Soft);
			Desc->SetAutoWrapText(true);
			Lines->AddChildToVerticalBox(Desc)->SetPadding(FMargin(0, 1, 0, 0));
			UHorizontalBoxSlot* LinesSlot = Row->AddChildToHorizontalBox(Lines);
			LinesSlot->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
			LinesSlot->SetVerticalAlignment(VAlign_Center);
			LinesSlot->SetPadding(FMargin(14, 0, 0, 0));
			Nodes->AddChildToVerticalBox(Row)->SetPadding(FMargin(0, 0, 0, Gap));
		};
		for (const FName& PerkId : W.Perks)
		{
			if (const FSOPerkInfo* Perk = Tables ? Tables->FindPerk(PerkId) : nullptr)
			{
				Node(PerkGlyph(PerkId), Light, Perk->Name.ToString().ToUpper(), Perk->Description.ToString(), 8.0f);
			}
		}
		if (Data && !Data->TraitName.IsEmpty())
		{
			Node(7, Gold, FString::Printf(TEXT("%s  ·  TRAIT"), *Data->TraitName.ToString().ToUpper()), Data->TraitText.ToString(), 0.0f);
		}
		UOverlaySlot* NodesSlot = Spine->AddChildToOverlay(Nodes);
		NodesSlot->SetHorizontalAlignment(HAlign_Fill);
		NodesSlot->SetVerticalAlignment(VAlign_Top);
		Inspect->AddChildToVerticalBox(Spine)->SetPadding(FMargin(0, 0, 0, 6));
	}
	else
	{
		// the summary: the stats beside the perks, the trait in a plate of gold under them
		UHorizontalBox* Pair = Make<UHorizontalBox>(T);
		UVerticalBox* Stats = Make<UVerticalBox>(T);
		Stats->AddChildToVerticalBox(Header(T, TEXT("STATS")))->SetPadding(FMargin(0, 0, 0, 8));
		for (int32 i = 0; i < Mine.Num(); ++i)
		{
			const FStatRow& R = Mine[i];
			if (!R.bSummary)
			{
				continue;
			}
			UHorizontalBox* Line = Make<UHorizontalBox>(T);
			Line->AddChildToHorizontalBox(Sized(T, Fit(Text(T, R.Name, 8, Soft, FaceBold, 140)), 70.0f, 0.0f))->SetVerticalAlignment(VAlign_Center);
			UHorizontalBoxSlot* BarSlot = Line->AddChildToHorizontalBox(Sized(T, StatBar(T, this, R.Fill(R.Value), Differs(i) ? R.Fill(Other(i)) : R.Fill(R.Value), 10, FLinearColor(0.84f, 0.9f, 1.0f, 0.92f)), 0.0f, 6.0f));
			BarSlot->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
			BarSlot->SetVerticalAlignment(VAlign_Center);
			UTextBlock* Value = Text(T, R.Shown, 10, Ink, FaceBold);
			Value->SetJustification(ETextJustify::Right);
			Line->AddChildToHorizontalBox(Sized(T, Value, 58.0f, 0.0f))->SetVerticalAlignment(VAlign_Center);
			Stats->AddChildToVerticalBox(Line)->SetPadding(FMargin(0, 3, 0, 3));
		}
		UVerticalBox* Perks = Make<UVerticalBox>(T);
		Perks->AddChildToVerticalBox(Header(T, TEXT("PERKS")))->SetPadding(FMargin(0, 0, 0, 8));
		for (const FName& PerkId : W.Perks)
		{
			if (const FSOPerkInfo* Perk = Tables ? Tables->FindPerk(PerkId) : nullptr)
			{
				UHorizontalBox* Row = Make<UHorizontalBox>(T);
				Row->AddChildToHorizontalBox(Hex(T, this, PerkGlyph(PerkId), Light, 30.0f))->SetVerticalAlignment(VAlign_Top);
				UVerticalBox* Lines = Make<UVerticalBox>(T);
				Lines->AddChildToVerticalBox(Fit(Text(T, Perk->Name.ToString(), 10, Ink, FaceBold, 30)));
				UTextBlock* Desc = Text(T, Perk->Description.ToString(), 8, Soft);
				Desc->SetAutoWrapText(true);
				Lines->AddChildToVerticalBox(Desc)->SetPadding(FMargin(0, 1, 0, 0));
				UHorizontalBoxSlot* LinesSlot = Row->AddChildToHorizontalBox(Lines);
				LinesSlot->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
				LinesSlot->SetPadding(FMargin(10, 0, 0, 0));
				Perks->AddChildToVerticalBox(Row)->SetPadding(FMargin(0, 0, 0, 8));
			}
		}
		if (W.Perks.Num() == 0)
		{
			UTextBlock* None = Text(T, TEXT("Its rarity rolled none."), 9, Dim, FaceItalic);
			None->SetAutoWrapText(true);
			Perks->AddChildToVerticalBox(None);
		}
		UHorizontalBoxSlot* StatsSlot = Pair->AddChildToHorizontalBox(Stats);
		StatsSlot->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
		UHorizontalBoxSlot* PerksSlot = Pair->AddChildToHorizontalBox(Perks);
		PerksSlot->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
		PerksSlot->SetPadding(FMargin(18, 0, 0, 0));
		Inspect->AddChildToVerticalBox(Pair);
		if (Data && !Data->TraitName.IsEmpty())
		{
			Inspect->AddChildToVerticalBox(Header(T, TEXT("TRAIT"), FString(), Gold))->SetPadding(FMargin(0, 12, 0, 8));
			FPlate TraitPlate;
			TraitPlate.Cut = 10.0f;
			TraitPlate.Fill = FLinearColor(0.012f, 0.008f, 0.003f, 0.9f);
			TraitPlate.FillLow = FLinearColor(0.006f, 0.004f, 0.0015f, 0.92f);
			TraitPlate.Edge = Alpha(Gold, 0.45f);
			TraitPlate.Accent = Gold;
			TraitPlate.AccentLeft = 3.0f;
			TraitPlate.Wash = 0.16f;
			UBorder* TraitBox = Box(T, PlateBrush(this, TraitPlate), FMargin(14, 10, 14, 10));
			UHorizontalBox* Row = Make<UHorizontalBox>(T);
			Row->AddChildToHorizontalBox(Hex(T, this, 7, Gold, 34.0f))->SetVerticalAlignment(VAlign_Center);
			UVerticalBox* Lines = Make<UVerticalBox>(T);
			Lines->AddChildToVerticalBox(Fit(Text(T, Data->TraitName.ToString(), 11, Gold, FaceBold, 40)));
			UTextBlock* Desc = Text(T, Data->TraitText.ToString(), 9, Soft);
			Desc->SetAutoWrapText(true);
			Lines->AddChildToVerticalBox(Desc)->SetPadding(FMargin(0, 1, 0, 0));
			UHorizontalBoxSlot* LinesSlot = Row->AddChildToHorizontalBox(Lines);
			LinesSlot->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
			LinesSlot->SetPadding(FMargin(12, 0, 0, 0));
			LinesSlot->SetVerticalAlignment(VAlign_Center);
			TraitBox->SetContent(Row);
			Inspect->AddChildToVerticalBox(TraitBox)->SetPadding(FMargin(0, 0, 0, 4));
		}
	}

	// what can be done with it
	SetActions(true);
	for (UButton* B : { DetailsButton.Get(), LockButton.Get(), DismantleButton.Get(), UpgradeButton.Get() })
	{
		B->SetVisibility(ESlateVisibility::Visible);
	}
	DetailsButton->SetIsEnabled(true);
	DetailsLabel->SetText(FText::FromString(bDetails ? TEXT("SUMMARY") : TEXT("DETAILS")));
	DetailsLabel->SetColorAndOpacity(FSlateColor(Ink));
	const bool bEquipped = Inventory->IsEquipped(W.Uid);
	EquipButton->SetIsEnabled(!bEquipped);
	EquipLabel->SetText(FText::FromString(bEquipped ? TEXT("EQUIPPED") : TEXT("EQUIP")));
	EquipLabel->SetColorAndOpacity(FSlateColor(bEquipped ? Dim : Ink));
	LockButton->SetIsEnabled(true);
	LockLabel->SetText(FText::FromString(W.bKeep ? TEXT("UNLOCK") : TEXT("LOCK")));
	LockLabel->SetColorAndOpacity(FSlateColor(Ink));
	const bool bCanDismantle = !bEquipped && !W.bKeep;
	DismantleButton->SetIsEnabled(bCanDismantle);
	const bool bArmed = FPlatformTime::Seconds() - DismantleArmedAt < 2.5;
	DismantleLabel->SetText(FText::FromString(bArmed ? TEXT("CONFIRM") : TEXT("DISMANTLE")));
	DismantleLabel->SetColorAndOpacity(FSlateColor(bCanDismantle ? (bArmed ? Bad : Ink) : Dim));
	ShowUpgrade(W.Uid);
	if (bArmed)
	{
		// what breaking it down gives, under the buttons while the second press is awaited
		UpgradeGoodsRow->ClearChildren();
		FString Gives = FString::Printf(TEXT("DISMANTLE FOR %d ALLOY"), USOLootLibrary::DismantleAlloy(W));
		for (const FSOGoodsCost& Part : USOLootLibrary::DismantleGoods(W))
		{
			if (const FSOGoodsInfo* Info = Tables ? Tables->FindGoods(Part.Item) : nullptr)
			{
				Gives += FString::Printf(TEXT("  ·  %d %s"), Part.Count, *Info->Name.ToString().ToUpper());
			}
		}
		UpgradeGoodsRow->AddChildToWrapBox(Text(T, Gives, 8, Bad, FaceBold, 160));
		UpgradeGoodsRow->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
	}
}

void USOInventoryWidget::FillGoodsInspect(const FSOGoodsInfo& Info)
{
	UWidgetTree* T = WidgetTree;
	const FLinearColor Rarity = RarityColor(Info.Rarity);
	const int32 Held = Inventory->CountOf(Info.Id);
	// what it is, its name, its line
	Inspect->AddChildToVerticalBox(Fit(Text(T, FString::Printf(TEXT("%s  ·  %s"), *RarityName(Info.Rarity).ToUpper(), *GoodsKindName(Info.Kind, false)), 9, Rarity, FaceBold, 240)));
	UTextBlock* Name = Text(T, Info.Name.ToString().ToUpper(), 32, Ink, FaceCond, 40);
	Name->SetAutoWrapText(true);
	Inspect->AddChildToVerticalBox(Name)->SetPadding(FMargin(0, 2, 0, 0));
	Inspect->AddChildToVerticalBox(Rule(T, Rarity))->SetPadding(FMargin(0, 8, 0, 10));
	if (!Info.Lore.IsEmpty())
	{
		UTextBlock* Lore = Text(T, Info.Lore.ToString(), 11, Soft, FaceItalic);
		Lore->SetAutoWrapText(true);
		Inspect->AddChildToVerticalBox(Lore)->SetPadding(FMargin(0, 0, 0, 8));
	}
	// it, large
	UWidget* Picture = nullptr;
	if (UTexture2D* Icon = Info.Icon.LoadSynchronous())
	{
		UImage* Pic = Make<UImage>(T);
		Pic->SetBrushFromTexture(Icon, false);
		Pic->SetVisibility(ESlateVisibility::HitTestInvisible);
		Picture = Sized(T, Pic, 200.0f, 200.0f);
	}
	else
	{
		Picture = Glyph(T, this, GoodsKindGlyph(Info.Kind), Alpha(Rarity, 0.8f), 96.0f);
	}
	UVerticalBoxSlot* PicSlot = Inspect->AddChildToVerticalBox(Picture);
	PicSlot->SetHorizontalAlignment(HAlign_Center);
	PicSlot->SetPadding(FMargin(0, 4, 0, 8));
	// how many are held, of how many
	UHorizontalBox* HeldRow = Make<UHorizontalBox>(T);
	HeldRow->AddChildToHorizontalBox(Glyph(T, this, GoodsKindGlyph(Info.Kind), Rarity, 20.0f))->SetVerticalAlignment(VAlign_Center);
	UHorizontalBoxSlot* Count = HeldRow->AddChildToHorizontalBox(Text(T, Number(Held), 34, Ink, FaceCond));
	Count->SetPadding(FMargin(10, 0, 0, 0));
	Count->SetVerticalAlignment(VAlign_Center);
	UVerticalBox* HeldWords = Make<UVerticalBox>(T);
	HeldWords->AddChildToVerticalBox(Text(T, TEXT("HELD"), 8, Soft, FaceBold, 300));
	HeldWords->AddChildToVerticalBox(Text(T, FString::Printf(TEXT("AT MOST %s"), *Number(FMath::Max(1, Info.Stack))), 8, Dim, FaceBold, 160));
	UHorizontalBoxSlot* HeldWordsSlot = HeldRow->AddChildToHorizontalBox(HeldWords);
	HeldWordsSlot->SetPadding(FMargin(10, 0, 0, 0));
	HeldWordsSlot->SetVerticalAlignment(VAlign_Center);
	Inspect->AddChildToVerticalBox(HeldRow)->SetPadding(FMargin(0, 0, 0, 12));
	// what it is for (a material: what of what is owned takes it), where it comes from
	Inspect->AddChildToVerticalBox(Header(T, TEXT("WHAT IT IS FOR")))->SetPadding(FMargin(0, 0, 0, 8));
	UTextBlock* Use = Text(T, Info.Use.ToString(), 11, Ink);
	Use->SetAutoWrapText(true);
	Inspect->AddChildToVerticalBox(Use);
	if (Info.Kind == ESOGoodsKind::Material)
	{
		int32 Guns = 0, Pieces = 0;
		TArray<FSOGoodsCost> Takes;
		for (const FSOWeaponInstance& W : Inventory->GetItems())
		{
			Inventory->GetUpgradeGoods(W.Uid, Takes);
			Guns += Takes.ContainsByPredicate([&Info](const FSOGoodsCost& C) { return C.Item == Info.Id; }) ? 1 : 0;
		}
		for (const FSOArmorInstance& A : Inventory->GetArmor())
		{
			Inventory->GetUpgradeGoods(A.Uid, Takes);
			Pieces += Takes.ContainsByPredicate([&Info](const FSOGoodsCost& C) { return C.Item == Info.Id; }) ? 1 : 0;
		}
		if (Guns + Pieces > 0)
		{
			const FString Line = Guns > 0 && Pieces > 0 ? FString::Printf(TEXT("Raising %d of your guns and %d of your armour pieces takes it."), Guns, Pieces)
				: Guns > 0 ? FString::Printf(TEXT("Raising %d of your guns takes it."), Guns) : FString::Printf(TEXT("Raising %d of your armour pieces takes it."), Pieces);
			UTextBlock* Needed = Text(T, Line, 9, Soft);
			Needed->SetAutoWrapText(true);
			Inspect->AddChildToVerticalBox(Needed)->SetPadding(FMargin(0, 4, 0, 0));
		}
	}
	Inspect->AddChildToVerticalBox(Header(T, TEXT("WHERE IT COMES FROM")))->SetPadding(FMargin(0, 14, 0, 8));
	UTextBlock* Source = Text(T, Info.Source.ToString(), 10, Soft);
	Source->SetAutoWrapText(true);
	Inspect->AddChildToVerticalBox(Source)->SetPadding(FMargin(0, 0, 0, 6));
	// a consumable is used; anything else only kept
	const bool bConsumable = Info.Kind == ESOGoodsKind::Consumable;
	SetActions(bConsumable);
	for (UButton* B : { DetailsButton.Get(), LockButton.Get(), DismantleButton.Get(), UpgradeButton.Get() })
	{
		B->SetVisibility(ESlateVisibility::Collapsed);
	}
	UpgradeGoodsRow->ClearChildren();
	UpgradeGoodsRow->SetVisibility(ESlateVisibility::Collapsed);
	if (bConsumable)
	{
		const bool bCan = Inventory->CanUseGoods(Info.Id);
		EquipButton->SetIsEnabled(bCan);
		EquipLabel->SetText(FText::FromString(bCan ? TEXT("USE") : (Held > 0 ? TEXT("NOT NEEDED NOW") : TEXT("NONE HELD"))));
		EquipLabel->SetColorAndOpacity(FSlateColor(bCan ? Ink : Dim));
	}
}

void USOInventoryWidget::FillJournalInspect(FName EntryId)
{
	UWidgetTree* T = WidgetTree;
	const FSOJournalData& Journal = FSOJournalData::Get();
	const FSOJournalEntry* E = Journal.Find(EntryId);
	SetActions(false);
	if (!E)
	{
		return;
	}
	const FSOJournalSection* Section = Journal.FindSection(E->Section);
	const FLinearColor Light = Section ? Section->Color : Cyan;
	const bool bOpen = Inventory->IsJournalOpen(EntryId);
	// its section and what it is, its title
	const FString Kind = Section ? Section->Name.ToUpper() : FString();
	Inspect->AddChildToVerticalBox(Fit(Text(T, bOpen && !E->Sub.IsEmpty() ? FString::Printf(TEXT("%s  ·  %s"), *Kind, *E->Sub) : Kind, 9, Light, FaceBold, 240)));
	UTextBlock* Title = Text(T, bOpen ? E->Title.ToUpper() : FString(TEXT("NOT YET LEARNED")), 32, bOpen ? Ink : Dim, FaceCond, 40);
	Title->SetAutoWrapText(true);
	Inspect->AddChildToVerticalBox(Title)->SetPadding(FMargin(0, 2, 0, 0));
	Inspect->AddChildToVerticalBox(Rule(T, Light))->SetPadding(FMargin(0, 8, 0, 14));
	if (!bOpen)
	{
		UTextBlock* Hint = Text(T, JournalHint(*E), 11, Soft, FaceBold, 200);
		Hint->SetAutoWrapText(true);
		Inspect->AddChildToVerticalBox(Hint);
		return;
	}
	if (E->Section == TEXT("record"))
	{
		FillRecord();
		return;
	}
	// its words a paragraph at a time; what it notes under its own head; its tally
	UVerticalBox* Words = Make<UVerticalBox>(T);
	TArray<FString> Paragraphs;
	E->Text.ParseIntoArray(Paragraphs, TEXT("\n\n"));
	for (const FString& P : Paragraphs)
	{
		UTextBlock* Para = Text(T, P.TrimStartAndEnd(), 12, Ink);
		Para->SetAutoWrapText(true);
		Words->AddChildToVerticalBox(Para)->SetPadding(FMargin(0, 0, 0, 12));
	}
	if (!E->Note.IsEmpty())
	{
		const TCHAR* NoteHead = E->Section == TEXT("sarketh") ? TEXT("ISSUED") : E->Section == TEXT("operations") ? TEXT("THE STAGE ASKED") : TEXT("NOTE");
		Words->AddChildToVerticalBox(Header(T, NoteHead, FString(), Light))->SetPadding(FMargin(0, 6, 0, 8));
		UTextBlock* Note = Text(T, E->Note, 11, Soft, FaceBold, 60);
		Note->SetAutoWrapText(true);
		Words->AddChildToVerticalBox(Note)->SetPadding(FMargin(0, 0, 0, 12));
	}
	if (!E->Tally.IsNone())
	{
		UHorizontalBox* Row = Make<UHorizontalBox>(T);
		Row->AddChildToHorizontalBox(Glyph(T, this, Section ? Section->Glyph : 4, Light, 20.0f))->SetVerticalAlignment(VAlign_Center);
		UHorizontalBoxSlot* N = Row->AddChildToHorizontalBox(Text(T, Number(Inventory->GetTally(E->Tally)), 34, Ink, FaceCond));
		N->SetPadding(FMargin(10, 0, 0, 0));
		N->SetVerticalAlignment(VAlign_Center);
		UHorizontalBoxSlot* L = Row->AddChildToHorizontalBox(Text(T, E->TallyLabel.IsEmpty() ? FString(TEXT("COUNTED")) : E->TallyLabel.ToUpper(), 8, Soft, FaceBold, 300));
		L->SetPadding(FMargin(10, 0, 0, 0));
		L->SetVerticalAlignment(VAlign_Center);
		Words->AddChildToVerticalBox(Row)->SetPadding(FMargin(0, 4, 0, 0));
	}
	// the portrait beside the words where the pane is wide, over them where it is not
	UTexture2D* Picture = JournalPicture(E->Picture);
	const float Wide = FMath::Max(200.0f, InspectWidth - 66.0f);  // (the frame's padding and the scroll bar)
	auto Portrait = [&](float W)
	{
		UImage* Pic = Make<UImage>(T);
		Pic->SetBrushFromTexture(Picture, false);
		Pic->SetVisibility(ESlateVisibility::HitTestInvisible);
		return Sized(T, Pic, W, W * 1.5f);
	};
	if (Picture && Wide >= 640.0f)
	{
		UHorizontalBox* Pair = Make<UHorizontalBox>(T);
		Pair->AddChildToHorizontalBox(Portrait(FMath::Clamp(Wide * 0.36f, 220.0f, 300.0f)))->SetVerticalAlignment(VAlign_Top);
		UHorizontalBoxSlot* W = Pair->AddChildToHorizontalBox(Words);
		W->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
		W->SetPadding(FMargin(24, 0, 0, 0));
		Inspect->AddChildToVerticalBox(Pair);
	}
	else
	{
		if (Picture)
		{
			UVerticalBoxSlot* PicSlot = Inspect->AddChildToVerticalBox(Portrait(200.0f));
			PicSlot->SetHorizontalAlignment(HAlign_Center);
			PicSlot->SetPadding(FMargin(0, 0, 0, 14));
		}
		// (a line no longer than reads comfortably: across a wide pane a line ran to 150 letters)
		USizeBox* Measure = Make<USizeBox>(T);
		Measure->SetMaxDesiredWidth(FMath::Min(Wide, 720.0f));
		Measure->SetContent(Words);
		Inspect->AddChildToVerticalBox(Measure)->SetHorizontalAlignment(HAlign_Left);
	}
}

void USOInventoryWidget::FillRecord()
{
	UWidgetTree* T = WidgetTree;
	const FSOJournalData& Journal = FSOJournalData::Get();
	// the record in two columns (a figure for every line): the field, the Sarketh rank by rank, the operations, the
	// journal itself
	UHorizontalBox* Columns2 = Make<UHorizontalBox>(T);
	UVerticalBox* Left = Make<UVerticalBox>(T);
	UVerticalBox* Right = Make<UVerticalBox>(T);
	const bool bTwo = InspectWidth - 66.0f >= 640.0f;
	auto Line = [&](UVerticalBox* To, const FString& Label, const FString& Value, const FLinearColor& Color)
	{
		UHorizontalBox* Row = Make<UHorizontalBox>(T);
		UHorizontalBoxSlot* L = Row->AddChildToHorizontalBox(Fit(Text(T, Label, 10, Soft, FaceBold, 200)));
		L->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
		L->SetVerticalAlignment(VAlign_Center);
		UHorizontalBoxSlot* V = Row->AddChildToHorizontalBox(Text(T, Value, 18, Color, FaceCond));
		V->SetPadding(FMargin(12, 0, 0, 0));
		V->SetVerticalAlignment(VAlign_Center);
		To->AddChildToVerticalBox(Row)->SetPadding(FMargin(0, 0, 0, 4));
		To->AddChildToVerticalBox(Sized(T, Box(T, FSlateColorBrush(Faint), FMargin(0)), 0.0f, 1.0f))->SetPadding(FMargin(0, 0, 0, 7));
	};
	auto Head = [&](UVerticalBox* To, const TCHAR* Label, const FLinearColor& Accent, bool bFirst)
	{
		To->AddChildToVerticalBox(Header(T, Label, FString(), Accent))->SetPadding(FMargin(0, bFirst ? 0.0f : 14.0f, 0, 10));
	};
	if (const FSOJournalEntry* E = Journal.Find(TEXT("record_service")); E && !E->Text.IsEmpty())
	{
		UTextBlock* Intro = Text(T, E->Text, 11, Soft, FaceItalic);
		Intro->SetAutoWrapText(true);
		Inspect->AddChildToVerticalBox(Intro)->SetPadding(FMargin(0, 0, 0, 16));
	}
	Head(Left, TEXT("IN THE FIELD"), Cyan, true);
	Line(Left, TEXT("LEVEL"), FString::FromInt(Inventory->GetLevel()), Ink);
	Line(Left, TEXT("POWER"), FString::FromInt(Inventory->GetPower()), Gold);
	Line(Left, TEXT("KILLS"), Number(Inventory->GetTally(SOJournal::KillsTally())), Ink);
	Line(Left, TEXT("NAMED ONES KILLED"), Number(Inventory->GetTally(SOJournal::NamedTally())), Gold);
	Line(Left, TEXT("TIMES DOWN"), Number(Inventory->GetTally(SOJournal::DeathsTally())), Bad);
	UVerticalBox* Second = bTwo ? Right : Left;
	const FSOJournalSection* Sarketh = Journal.FindSection(TEXT("sarketh"));
	Head(Second, TEXT("THE SARKETH"), Sarketh ? Sarketh->Color : Gold, bTwo);
	for (const FSOJournalEntry& Each : Journal.Entries)
	{
		if (Each.Section == TEXT("sarketh") && !Each.Tally.IsNone())
		{
			const bool bKnown = Inventory->IsJournalOpen(Each.Id);
			Line(Second, bKnown ? Each.Title.ToUpper() : FString(TEXT("NOT YET MET")), Number(Inventory->GetTally(Each.Tally)), bKnown ? Ink : Dim);
		}
	}
	Head(Left, TEXT("OPERATIONS FINISHED"), Gold, false);
	for (const FSOJournalEntry& Each : Journal.Entries)
	{
		if (Each.Section == TEXT("operations") && Each.Id.ToString().EndsWith(TEXT("_briefing")))
		{
			Line(Left, Each.Title.ToUpper(), Number(Inventory->GetTally(Each.Tally)), Ink);
		}
	}
	int32 Known = 0;
	for (const FSOJournalEntry& Each : Journal.Entries)
	{
		Known += Inventory->IsJournalOpen(Each.Id) ? 1 : 0;
	}
	Head(Left, TEXT("THE JOURNAL"), Cyan, false);
	Line(Left, TEXT("PAGES LEARNED"), FString::Printf(TEXT("%d / %d"), Known, Journal.Entries.Num()), Cyan);
	Line(Left, TEXT("GUNS IN THE VAULT"), FString::Printf(TEXT("%d / %d"), Inventory->GetItems().Num(), USOLootLibrary::VaultCap), Ink);
	UHorizontalBoxSlot* LS = Columns2->AddChildToHorizontalBox(Left);
	LS->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
	if (bTwo)
	{
		UHorizontalBoxSlot* RS = Columns2->AddChildToHorizontalBox(Right);
		RS->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
		RS->SetPadding(FMargin(28, 0, 0, 0));
	}
	Inspect->AddChildToVerticalBox(Columns2);
}

void USOInventoryWidget::FillCompare()
{
	if (!CompareBox)
	{
		return;
	}
	const FSOWeaponInstance* Chosen = Inventory && IsWeaponSlot(OpenSlotId) ? Inventory->Find(ShownKey()) : nullptr;
	const FSOWeaponInstance* Carried = Chosen ? Inventory->GetEquipped(FCString::Atoi(*OpenSlotId)) : nullptr;
	if (!bComparing || GetView() != EView::Arsenal || !Chosen || !Carried)
	{
		CompareBox->SetVisibility(ESlateVisibility::Collapsed);
		for (USOInventoryTile* Tile : ListTiles)
		{
			if (Tile && Tile->GetVisibility() == ESlateVisibility::Hidden)
			{
				Tile->SetVisibility(ESlateVisibility::Visible);
			}
		}
		return;
	}
	UWidgetTree* T = WidgetTree;
	const float W = GridWidth - 48.0f;
	UVerticalBox* Column = Make<UVerticalBox>(T);
	Column->AddChildToVerticalBox(Header(T, TEXT("COMPARE"), Chosen->Uid == Carried->Uid ? FString(TEXT("THE ONE YOU CARRY")) : FString(TEXT("AGAINST THE ONE YOU CARRY"))))->SetPadding(FMargin(0, 0, 0, 14));
	// the two side by side: what each is, its picture, its name, its power
	UHorizontalBox* Heads = Make<UHorizontalBox>(T);
	auto Head = [&](const FSOWeaponInstance& G, const TCHAR* Over) -> UWidget*
	{
		const USOWeaponData* D = ArchetypeOf(G);
		const FLinearColor R = RarityColor(G.Rarity);
		UVerticalBox* V = Make<UVerticalBox>(T);
		V->AddChildToVerticalBox(Text(T, Over, 7, Dim, FaceBold, 260));
		if (UTexture2D* Icon = D ? D->Icon.LoadSynchronous() : nullptr)
		{
			UImage* Pic = Make<UImage>(T);
			Pic->SetBrushFromTexture(Icon, false);
			Pic->SetVisibility(ESlateVisibility::HitTestInvisible);
			const float PicW = FMath::Min(200.0f, W * 0.5f - 20.0f);
			V->AddChildToVerticalBox(Sized(T, Pic, PicW, PicW * 0.5f))->SetPadding(FMargin(0, 4, 0, 4));
		}
		V->AddChildToVerticalBox(Fit(Text(T, G.Name.ToUpper(), 16, Ink, FaceCond, 30)));
		UHorizontalBox* P = Make<UHorizontalBox>(T);
		P->AddChildToHorizontalBox(Glyph(T, this, 4, Gold, 12.0f))->SetVerticalAlignment(VAlign_Center);
		UHorizontalBoxSlot* N = P->AddChildToHorizontalBox(Text(T, FString::FromInt(G.Power), 16, Gold, FaceCond));
		N->SetPadding(FMargin(5, 0, 0, 0));
		N->SetVerticalAlignment(VAlign_Center);
		UHorizontalBoxSlot* RN = P->AddChildToHorizontalBox(Fit(Text(T, RarityName(G.Rarity).ToUpper(), 8, R, FaceBold, 200)));
		RN->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
		RN->SetPadding(FMargin(10, 0, 0, 0));
		RN->SetVerticalAlignment(VAlign_Center);
		V->AddChildToVerticalBox(P);
		return V;
	};
	UHorizontalBoxSlot* A = Heads->AddChildToHorizontalBox(Head(*Chosen, TEXT("CHOSEN")));
	A->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
	UHorizontalBoxSlot* B = Heads->AddChildToHorizontalBox(Head(*Carried, TEXT("CARRIED")));
	B->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
	B->SetPadding(FMargin(20, 0, 0, 0));
	Column->AddChildToVerticalBox(Heads)->SetPadding(FMargin(0, 0, 0, 14));
	// every number: the chosen one's, its bar, the carried one's bar, its number, the difference
	const TArray<FStatRow> Mine = GunStats(*Chosen, ArchetypeOf(*Chosen));
	const TArray<FStatRow> Theirs = GunStats(*Carried, ArchetypeOf(*Carried));
	for (int32 i = 0; i < Mine.Num() && i < Theirs.Num(); ++i)
	{
		const FStatRow& R = Mine[i];
		const float O = Theirs[i].Value;
		const bool bDiffers = !FMath::IsNearlyEqual(R.Value, O, FMath::Abs(O) * 0.005f + 0.001f);
		const bool bBetter = bDiffers && (R.bLowerBetter ? R.Value < O : R.Value > O);
		UHorizontalBox* Line = Make<UHorizontalBox>(T);
		Line->AddChildToHorizontalBox(Sized(T, Fit(Text(T, R.Name, 8, Soft, FaceBold, 140)), 82.0f, 0.0f))->SetVerticalAlignment(VAlign_Center);
		UTextBlock* Value = Text(T, R.Shown, 10, bDiffers ? (bBetter ? Good : Bad) : Ink, FaceBold);
		Value->SetJustification(ETextJustify::Right);
		Line->AddChildToHorizontalBox(Sized(T, Value, 66.0f, 0.0f))->SetVerticalAlignment(VAlign_Center);
		UHorizontalBoxSlot* BarA = Line->AddChildToHorizontalBox(Sized(T, StatBar(T, this, R.Fill(R.Value), R.Fill(R.Value), 10, FLinearColor(0.84f, 0.9f, 1.0f, 0.92f)), 0.0f, 6.0f));
		BarA->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
		BarA->SetVerticalAlignment(VAlign_Center);
		BarA->SetPadding(FMargin(10, 0, 6, 0));
		UHorizontalBoxSlot* BarB = Line->AddChildToHorizontalBox(Sized(T, StatBar(T, this, R.Fill(O), R.Fill(O), 10, Alpha(Soft, 0.9f)), 0.0f, 6.0f));
		BarB->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
		BarB->SetVerticalAlignment(VAlign_Center);
		BarB->SetPadding(FMargin(6, 0, 10, 0));
		UTextBlock* Them = Text(T, Theirs[i].Shown, 10, Soft, FaceBold);
		Line->AddChildToHorizontalBox(Sized(T, Them, 66.0f, 0.0f))->SetVerticalAlignment(VAlign_Center);
		UTextBlock* Delta = Text(T, bDiffers ? FString::Printf(TEXT("%+.0f%%"), (R.Value / FMath::Max(O, 0.001f) - 1.0f) * 100.0f) : FString(TEXT("=")), 9, bDiffers ? (bBetter ? Good : Bad) : Dim, FaceBold);
		Delta->SetJustification(ETextJustify::Right);
		Line->AddChildToHorizontalBox(Sized(T, Delta, 48.0f, 0.0f))->SetVerticalAlignment(VAlign_Center);
		Column->AddChildToVerticalBox(Line)->SetPadding(FMargin(0, 3, 0, 3));
	}
	CompareBox->SetContent(Sized(T, Column, W, 0.0f));
	CompareBox->SetVisibility(ESlateVisibility::HitTestInvisible);
	for (USOInventoryTile* Tile : ListTiles)
	{
		if (Tile)
		{
			Tile->SetVisibility(ESlateVisibility::Hidden);      // (the cards under it step aside)
		}
	}
}

void USOInventoryWidget::FillArmorInspect(const FSOArmorInstance& A)
{
	UWidgetTree* T = WidgetTree;
	const USOWardrobeData* Wardrobe = USOWardrobeData::Get(Inventory->GetBody());
	const FSOWardrobeItem* Item = Wardrobe ? Wardrobe->Find(A.Slot, A.Item) : nullptr;
	const FLinearColor Rarity = RarityColor(A.Rarity);
	Inspect->AddChildToVerticalBox(Text(T, FString::Printf(TEXT("%s  ·  %s ARMOUR"), *RarityName(A.Rarity).ToUpper(), *USOWardrobeData::SlotLabel(A.Slot).ToString().ToUpper()), 9, Rarity, FaceBold, 260));
	UTextBlock* Name = Text(T, (Item ? Item->Label.ToString() : A.Item.ToString()).ToUpper(), 34, Ink, FaceCond, 40);
	Name->SetAutoWrapText(true);
	Inspect->AddChildToVerticalBox(Name)->SetPadding(FMargin(0, 2, 0, 0));
	Inspect->AddChildToVerticalBox(Rule(T, Rarity))->SetPadding(FMargin(0, 6, 0, 12));
	if (Item && !Item->Set.IsNone())
	{
		Inspect->AddChildToVerticalBox(Text(T, FString::Printf(TEXT("OF THE %s SET"), *IdWords(Item->Set)), 9, Gold, FaceBold, 220))->SetPadding(FMargin(0, 0, 0, 12));
	}
	if (UTexture2D* Icon = Item ? Item->Icon.LoadSynchronous() : nullptr)
	{
		UImage* Pic = Make<UImage>(T);
		Pic->SetBrushFromTexture(Icon, false);
		Pic->SetVisibility(ESlateVisibility::HitTestInvisible);
		UVerticalBoxSlot* PicSlot = Inspect->AddChildToVerticalBox(Sized(T, Pic, 180.0f, 180.0f));
		PicSlot->SetHorizontalAlignment(HAlign_Center);
		PicSlot->SetPadding(FMargin(0, 0, 0, 10));
	}
	// power and armour, against what is worn there
	const int32 Armor = Item ? Item->Armor : 0;
	const FSOArmorInstance* Worn = Inventory->GetEquippedArmor(A.Slot);
	const FSOWardrobeItem* WornItem = Worn && Wardrobe ? Wardrobe->Find(Worn->Slot, Worn->Item) : nullptr;
	const bool bCompare = Worn && Worn->Uid != A.Uid;
	UHorizontalBox* Figures = Make<UHorizontalBox>(T);
	auto Figure = [&](int32 GlyphIndex, const FLinearColor& Color, int32 Value, int32 Other, const TCHAR* Label)
	{
		UHorizontalBox* F = Make<UHorizontalBox>(T);
		if (GlyphIndex >= 0)
		{
			F->AddChildToHorizontalBox(Glyph(T, this, GlyphIndex, Color, 18.0f))->SetVerticalAlignment(VAlign_Center);
		}
		UHorizontalBoxSlot* N = F->AddChildToHorizontalBox(Text(T, FString::FromInt(Value), 34, Color, FaceCond));
		N->SetPadding(FMargin(GlyphIndex >= 0 ? 8.0f : 0.0f, 0, 0, 0));
		N->SetVerticalAlignment(VAlign_Center);
		UVerticalBox* W = Make<UVerticalBox>(T);
		W->AddChildToVerticalBox(Text(T, Label, 8, Color, FaceBold, 300));
		if (bCompare && Value != Other)
		{
			W->AddChildToVerticalBox(Text(T, FString::Printf(TEXT("%+d"), Value - Other), 10, Value > Other ? Good : Bad, FaceBold));
		}
		UHorizontalBoxSlot* WS = F->AddChildToHorizontalBox(W);
		WS->SetPadding(FMargin(8, 0, 0, 0));
		WS->SetVerticalAlignment(VAlign_Center);
		Figures->AddChildToHorizontalBox(F)->SetPadding(FMargin(0, 0, 34, 0));
	};
	Figure(4, Gold, A.Power, bCompare ? Worn->Power : A.Power, TEXT("POWER"));
	Figure(5, Ink, Armor, WornItem ? WornItem->Armor : Armor, TEXT("ARMOUR"));
	Inspect->AddChildToVerticalBox(Figures)->SetPadding(FMargin(0, 0, 0, 16));

	// what it gives: its points in each attribute against the piece worn in its slot
	Inspect->AddChildToVerticalBox(Header(T, TEXT("ATTRIBUTES"), bCompare ? FString(TEXT("AGAINST WHAT IS WORN")) : FString()))->SetPadding(FMargin(0, 0, 0, 10));
	const USOAttributeTable& Rules = USOAttributeTable::Get();
	const FSOAttributePoints Gives = Inventory->GetArmorPoints(A);
	const FSOAttributePoints WornGives = bCompare ? Inventory->GetArmorPoints(*Worn) : Gives;
	int32 Most = 1;
	for (int32 i = 0; i < static_cast<int32>(ESOAttribute::Count); ++i)
	{
		Most = FMath::Max3(Most, Gives.Get(static_cast<ESOAttribute>(i)), WornGives.Get(static_cast<ESOAttribute>(i)));
	}
	const float Scale = FMath::Max(30.0f, Most * 1.15f);
	for (int32 i = 0; i < static_cast<int32>(ESOAttribute::Count); ++i)
	{
		const ESOAttribute Which = static_cast<ESOAttribute>(i);
		const int32 Mine = Gives.Get(Which), Theirs = WornGives.Get(Which);
		UHorizontalBox* Line = Make<UHorizontalBox>(T);
		Line->AddChildToHorizontalBox(Glyph(T, this, 5 + i, Mine > 0 ? Cyan : Alpha(Dim, 0.6f), 16.0f))->SetVerticalAlignment(VAlign_Center);
		UHorizontalBoxSlot* L = Line->AddChildToHorizontalBox(Sized(T, Text(T, Rules.Rule(Which).Name.ToString().ToUpper(), 9, Mine > 0 ? Soft : Dim, FaceBold, 180), 96.0f, 0.0f));
		L->SetPadding(FMargin(10, 0, 0, 0));
		L->SetVerticalAlignment(VAlign_Center);
		UHorizontalBoxSlot* B = Line->AddChildToHorizontalBox(Sized(T, StatBar(T, this, Mine / Scale, Theirs / Scale, 12, FLinearColor(0.84f, 0.9f, 1.0f, 0.92f)), 0.0f, 8.0f));
		B->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
		B->SetVerticalAlignment(VAlign_Center);
		UTextBlock* Value = Text(T, FString::Printf(TEXT("+%d"), Mine), 11, Mine > 0 ? Ink : Dim, FaceBold);
		Value->SetJustification(ETextJustify::Right);
		Line->AddChildToHorizontalBox(Sized(T, Value, 48.0f, 0.0f))->SetVerticalAlignment(VAlign_Center);
		UTextBlock* Delta = Text(T, Mine != Theirs ? FString::Printf(TEXT("%+d"), Mine - Theirs) : FString(), 9, Mine > Theirs ? Good : Bad, FaceBold);
		Delta->SetJustification(ETextJustify::Right);
		Line->AddChildToHorizontalBox(Sized(T, Delta, 40.0f, 0.0f))->SetVerticalAlignment(VAlign_Center);
		Line->SetToolTipText(Rules.Rule(Which).Effect);
		Inspect->AddChildToVerticalBox(Line)->SetPadding(FMargin(0, 4, 0, 4));
	}
	Inspect->AddChildToVerticalBox(Header(T, TEXT("PERKS")))->SetPadding(FMargin(0, 18, 0, 10));
	UTextBlock* Note = Text(T, TEXT("Armour perks come with the world's later chapters: for now a piece is its look and what it gives."), 11, Dim, FaceItalic);
	Note->SetAutoWrapText(true);
	Inspect->AddChildToVerticalBox(Note);

	// a required slot can be swapped but never emptied: what is worn there shows as WORN
	SetActions(true);
	DetailsButton->SetVisibility(ESlateVisibility::Collapsed);
	LockButton->SetVisibility(ESlateVisibility::Collapsed);
	DismantleButton->SetVisibility(ESlateVisibility::Collapsed);
	UpgradeButton->SetVisibility(ESlateVisibility::Visible);
	const bool bRequired = !USOWardrobeData::IsOptionalSlot(A.Slot);
	EquipButton->SetIsEnabled(!(A.bEquipped && bRequired));
	EquipLabel->SetText(FText::FromString(A.bEquipped ? (bRequired ? TEXT("WORN") : TEXT("TAKE OFF")) : TEXT("WEAR")));
	EquipLabel->SetColorAndOpacity(FSlateColor(A.bEquipped && bRequired ? Dim : Ink));
	LockButton->SetIsEnabled(false);
	LockLabel->SetText(FText::FromString(TEXT("LOCK")));
	LockLabel->SetColorAndOpacity(FSlateColor(Dim));
	DismantleButton->SetIsEnabled(false);
	DismantleLabel->SetText(FText::FromString(TEXT("DISMANTLE")));
	DismantleLabel->SetColorAndOpacity(FSlateColor(Dim));
	ShowUpgrade(A.Uid);
}

void USOInventoryWidget::FillMeleeInspect(const FSOMeleeStyle& Style, FName Id)
{
	UWidgetTree* T = WidgetTree;
	const bool bFists = Id == TEXT("fists");
	const FLinearColor Light = bFists ? Steel : BladeLight;
	Inspect->AddChildToVerticalBox(Text(T, bFists ? TEXT("HAND TO HAND  ·  MELEE") : TEXT("BLADE  ·  HAND TO HAND  ·  MELEE"), 9, Light, FaceBold, 260));
	UTextBlock* Name = Text(T, (Style.Name.IsEmpty() ? Id.ToString() : Style.Name.ToString()).ToUpper(), 34, Ink, FaceCond, 40);
	Name->SetAutoWrapText(true);
	Inspect->AddChildToVerticalBox(Name)->SetPadding(FMargin(0, 2, 0, 0));
	Inspect->AddChildToVerticalBox(Rule(T, Light))->SetPadding(FMargin(0, 6, 0, 12));
	if (!Style.Lore.IsEmpty())
	{
		UTextBlock* Lore = Text(T, Style.Lore.ToString(), 12, Soft, FaceItalic);
		Lore->SetAutoWrapText(true);
		Inspect->AddChildToVerticalBox(Lore)->SetPadding(FMargin(0, 0, 0, 12));
	}
	{
		UWidget* Picture = nullptr;
		if (UTexture2D* Icon = Style.Icon.LoadSynchronous())
		{
			UImage* Pic = Make<UImage>(T);
			Pic->SetBrushFromTexture(Icon, false);
			Pic->SetVisibility(ESlateVisibility::HitTestInvisible);
			const float PicW = FMath::Min(FMath::Max(200.0f, InspectWidth - 66.0f), 380.0f);
			Picture = Sized(T, Pic, PicW, PicW * 0.5f);
		}
		else
		{
			Picture = Glyph(T, this, bFists ? 11 : 13, Alpha(Light, 0.8f), 96.0f);
		}
		UVerticalBoxSlot* PicSlot = Inspect->AddChildToVerticalBox(Picture);
		PicSlot->SetHorizontalAlignment(HAlign_Center);
		PicSlot->SetPadding(FMargin(0, 0, 0, 12));
	}
	// every blow it has, how it is thrown and what it does
	Inspect->AddChildToVerticalBox(Header(T, TEXT("BLOWS")))->SetPadding(FMargin(0, 0, 0, 10));
	float Most = 1.0f;
	for (const FSOMeleeBlow* B : { &Style.Heavy, &Style.Finisher, &Style.Rush, &Style.Sweep, &Style.Riser, &Style.Air })
	{
		Most = FMath::Max(Most, B->Damage);
	}
	for (const FSOMeleeBlow& B : Style.Light)
	{
		Most = FMath::Max(Most, B.Damage);
	}
	auto Blow = [&](int32 Which, const FString& What, const FString& How, float Damage, const FString& Shown)
	{
		UHorizontalBox* Row = Make<UHorizontalBox>(T);
		Row->AddChildToHorizontalBox(Hex(T, this, Which, Light, 34.0f))->SetVerticalAlignment(VAlign_Center);
		UVerticalBox* Lines = Make<UVerticalBox>(T);
		Lines->AddChildToVerticalBox(Text(T, What, 11, Ink, FaceBold, 120));
		Lines->AddChildToVerticalBox(Text(T, How, 9, Dim));
		UHorizontalBoxSlot* LinesSlot = Row->AddChildToHorizontalBox(Sized(T, Lines, 150.0f, 0.0f));
		LinesSlot->SetPadding(FMargin(12, 0, 0, 0));
		LinesSlot->SetVerticalAlignment(VAlign_Center);
		UHorizontalBoxSlot* B = Row->AddChildToHorizontalBox(Sized(T, StatBar(T, this, Damage / (Most * 1.1f), Damage / (Most * 1.1f), 10, Alpha(Light, 0.9f)), 0.0f, 7.0f));
		B->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
		B->SetVerticalAlignment(VAlign_Center);
		UTextBlock* Value = Text(T, Shown.IsEmpty() ? FString::Printf(TEXT("%.0f"), Damage) : Shown, 12, Ink, FaceBold);
		Value->SetJustification(ETextJustify::Right);
		Row->AddChildToHorizontalBox(Sized(T, Value, 60.0f, 0.0f))->SetVerticalAlignment(VAlign_Center);
		Inspect->AddChildToVerticalBox(Row)->SetPadding(FMargin(0, 3, 0, 3));
	};
	if (Style.Light.Num() > 0)
	{
		float Least = Style.Light[0].Damage, Best = Least;
		for (const FSOMeleeBlow& B : Style.Light)
		{
			Least = FMath::Min(Least, B.Damage);
			Best = FMath::Max(Best, B.Damage);
		}
		Blow(0, FString::Printf(TEXT("LIGHT CHAIN  ·  %d"), Style.Light.Num()), TEXT("fire, again and again"), Best,
			FMath::IsNearlyEqual(Least, Best) ? FString() : FString::Printf(TEXT("%.0f-%.0f"), Least, Best));
	}
	struct FNamed { const FSOMeleeBlow* B; const TCHAR* What; const TCHAR* How; int32 Glyph; };
	const FNamed Named[] = {
		{ &Style.Heavy, TEXT("HEAVY"), TEXT("aim"), 4 },
		{ &Style.Finisher, TEXT("FINISHER"), TEXT("light, light, heavy"), 2 },
		{ &Style.Rush, TEXT("RUSH"), TEXT("light at a sprint"), 5 },
		{ &Style.Sweep, TEXT("SWEEP"), TEXT("light crouched"), 6 },
		{ &Style.Riser, TEXT("RISER"), TEXT("heavy crouched"), 1 },
		{ &Style.Air, TEXT("SLAM"), TEXT("heavy in the air"), 3 } };
	for (const FNamed& N : Named)
	{
		if (!N.B->Clip.IsNone())
		{
			Blow(N.Glyph, N.What, N.How, N.B->Damage, FString());
		}
	}
	Inspect->AddChildToVerticalBox(Header(T, TEXT("GUARD")))->SetPadding(FMargin(0, 18, 0, 10));
	UTextBlock* Guard = Text(T, FString::Printf(TEXT("Hold R to guard: %.0f %% of a blow from the front gets through. Raised just as a blow comes it is a parry: nothing through, the attacker reels, and your next blow within %.1f s lands %.0f %%."),
		Style.BlockScale * 100.0f, Style.CounterTime, Style.CounterScale * 100.0f), 11, Soft);
	Guard->SetAutoWrapText(true);
	Inspect->AddChildToVerticalBox(Guard);

	SetActions(true);
	DetailsButton->SetVisibility(ESlateVisibility::Collapsed);
	LockButton->SetVisibility(ESlateVisibility::Collapsed);
	DismantleButton->SetVisibility(ESlateVisibility::Collapsed);
	UpgradeButton->SetVisibility(ESlateVisibility::Collapsed);
	const FName In = Inventory->GetMeleeSlot().IsNone() ? FName(TEXT("fists")) : Inventory->GetMeleeSlot();
	EquipButton->SetIsEnabled(In != Id);
	EquipLabel->SetText(FText::FromString(In == Id ? TEXT("EQUIPPED") : TEXT("EQUIP")));
	EquipLabel->SetColorAndOpacity(FSlateColor(In == Id ? Dim : Ink));
	for (UButton* B : { LockButton.Get(), DismantleButton.Get() })
	{
		B->SetIsEnabled(false);
	}
	LockLabel->SetText(FText::FromString(TEXT("LOCK")));
	LockLabel->SetColorAndOpacity(FSlateColor(Dim));
	DismantleLabel->SetText(FText::FromString(TEXT("DISMANTLE")));
	DismantleLabel->SetColorAndOpacity(FSlateColor(Dim));
	ShowUpgrade(FString());
}

void USOInventoryWidget::FillQuickLook(USOInventoryTile* Tile)
{
	UWidgetTree* T = WidgetTree;
	const FSOTileInfo& Info = Tile->GetInfo();
	UVerticalBox* Column = Make<UVerticalBox>(T);
	bool bAny = false;
	if (Info.Kind == TEXT("wslot"))
	{
		if (const FSOWeaponInstance* W = Inventory->GetEquipped(FCString::Atoi(*Info.Key)))
		{
			const USOWeaponData* Data = ArchetypeOf(*W);
			const USOLootTables* Tables = USOLootLibrary::GetTables();
			const FLinearColor Rarity = RarityColor(W->Rarity);
			Column->AddChildToVerticalBox(Text(T, FString::Printf(TEXT("%s  ·  %s"), *RarityName(W->Rarity).ToUpper(), *KindName(Data).ToUpper()), 8, Rarity, FaceBold, 240));
			Column->AddChildToVerticalBox(Text(T, W->Name.ToUpper(), 24, Ink, FaceCond, 30));
			Column->AddChildToVerticalBox(Rule(T, Rarity))->SetPadding(FMargin(0, 4, 0, 10));
			const FSOWeaponStats S = USOLootLibrary::ComputeStats(*W);
			const int32 Pellets = Data ? FMath::Max(1, Data->Pellets) : 1;
			auto Bar = [&](const TCHAR* Name, float Fill, const FString& Shown)
			{
				UHorizontalBox* Line = Make<UHorizontalBox>(T);
				Line->AddChildToHorizontalBox(Sized(T, Text(T, Name, 8, Soft, FaceBold, 180), 84.0f, 0.0f))->SetVerticalAlignment(VAlign_Center);
				UHorizontalBoxSlot* B = Line->AddChildToHorizontalBox(Sized(T, StatBar(T, this, Fill, Fill, 12, FLinearColor(0.84f, 0.9f, 1.0f, 0.92f)), 150.0f, 6.0f));
				B->SetVerticalAlignment(VAlign_Center);
				UHorizontalBoxSlot* V = Line->AddChildToHorizontalBox(Text(T, Shown, 9, Ink, FaceBold));
				V->SetPadding(FMargin(10, 0, 0, 0));
				V->SetVerticalAlignment(VAlign_Center);
				Column->AddChildToVerticalBox(Line)->SetPadding(FMargin(0, 2, 0, 2));
			};
			Bar(TEXT("IMPACT"), FMath::Clamp(S.Damage * Pellets / 450.0f, 0.03f, 1.0f), FString::Printf(TEXT("%.0f"), S.Damage * Pellets));
			Bar(TEXT("FIRE RATE"), FMath::Clamp(S.Rpm / 1100.0f, 0.03f, 1.0f), FString::Printf(TEXT("%.0f"), S.Rpm));
			Bar(TEXT("RANGE"), FMath::Clamp(S.Range / 180.0f, 0.03f, 1.0f), FString::Printf(TEXT("%.0f M"), S.Range));
			Bar(TEXT("MAGAZINE"), FMath::Clamp(S.Mag / 150.0f, 0.03f, 1.0f), FString::FromInt(S.Mag));
			if (W->Perks.Num() > 0 || (Data && !Data->TraitName.IsEmpty()))
			{
				UVerticalBox* Perks = Make<UVerticalBox>(T);
				for (const FName& PerkId : W->Perks)
				{
					if (const FSOPerkInfo* Perk = Tables ? Tables->FindPerk(PerkId) : nullptr)
					{
						UHorizontalBox* Row = Make<UHorizontalBox>(T);
						Row->AddChildToHorizontalBox(Hex(T, this, PerkGlyph(PerkId), GunLight(Data), 24.0f))->SetVerticalAlignment(VAlign_Center);
						UHorizontalBoxSlot* N = Row->AddChildToHorizontalBox(Text(T, Perk->Name.ToString().ToUpper(), 9, Ink, FaceBold, 120));
						N->SetPadding(FMargin(8, 0, 0, 0));
						N->SetVerticalAlignment(VAlign_Center);
						Perks->AddChildToVerticalBox(Row)->SetPadding(FMargin(0, 0, 0, 4));
					}
				}
				if (Data && !Data->TraitName.IsEmpty())
				{
					UHorizontalBox* Row = Make<UHorizontalBox>(T);
					Row->AddChildToHorizontalBox(Hex(T, this, 7, Gold, 24.0f))->SetVerticalAlignment(VAlign_Center);
					UHorizontalBoxSlot* N = Row->AddChildToHorizontalBox(Text(T, Data->TraitName.ToString().ToUpper(), 9, Gold, FaceBold, 120));
					N->SetPadding(FMargin(8, 0, 0, 0));
					N->SetVerticalAlignment(VAlign_Center);
					Perks->AddChildToVerticalBox(Row);
				}
				Column->AddChildToVerticalBox(Perks)->SetPadding(FMargin(0, 12, 0, 0));
			}
			bAny = true;
		}
	}
	else if (Info.Kind == TEXT("aslot"))
	{
		if (const FSOArmorInstance* A = Inventory->GetEquippedArmor(FName(*Info.Key)))
		{
			const FLinearColor Rarity = RarityColor(A->Rarity);
			Column->AddChildToVerticalBox(Text(T, FString::Printf(TEXT("%s  ·  %s"), *RarityName(A->Rarity).ToUpper(), *USOWardrobeData::SlotLabel(A->Slot).ToString().ToUpper()), 8, Rarity, FaceBold, 240));
			Column->AddChildToVerticalBox(Text(T, Info.Title.ToUpper(), 22, Ink, FaceCond, 30));
			Column->AddChildToVerticalBox(Rule(T, Rarity))->SetPadding(FMargin(0, 4, 0, 10));
			const USOAttributeTable& Rules = USOAttributeTable::Get();
			const FSOAttributePoints Gives = Inventory->GetArmorPoints(*A);
			for (int32 i = 0; i < static_cast<int32>(ESOAttribute::Count); ++i)
			{
				const ESOAttribute Which = static_cast<ESOAttribute>(i);
				if (Gives.Get(Which) <= 0)
				{
					continue;
				}
				UHorizontalBox* Row = Make<UHorizontalBox>(T);
				Row->AddChildToHorizontalBox(Glyph(T, this, 5 + i, Cyan, 14.0f))->SetVerticalAlignment(VAlign_Center);
				UHorizontalBoxSlot* N = Row->AddChildToHorizontalBox(Sized(T, Text(T, Rules.Rule(Which).Name.ToString().ToUpper(), 9, Soft, FaceBold, 160), 110.0f, 0.0f));
				N->SetPadding(FMargin(8, 0, 0, 0));
				N->SetVerticalAlignment(VAlign_Center);
				Row->AddChildToHorizontalBox(Text(T, FString::Printf(TEXT("+%d"), Gives.Get(Which)), 11, Ink, FaceBold))->SetVerticalAlignment(VAlign_Center);
				Column->AddChildToVerticalBox(Row)->SetPadding(FMargin(0, 2, 0, 2));
			}
			bAny = true;
		}
	}
	else if (Info.Kind == TEXT("mslot"))
	{
		const USOMeleeTable* Melee = USOMeleeTable::Get();
		const FName In = Inventory->GetMeleeSlot().IsNone() ? FName(TEXT("fists")) : Inventory->GetMeleeSlot();
		if (const FSOMeleeStyle* Style = Melee ? Melee->Find(In) : nullptr)
		{
			const FLinearColor Light = In == TEXT("fists") ? Steel : BladeLight;
			Column->AddChildToVerticalBox(Text(T, TEXT("MELEE"), 8, Light, FaceBold, 240));
			Column->AddChildToVerticalBox(Text(T, Info.Title.ToUpper(), 24, Ink, FaceCond, 30));
			Column->AddChildToVerticalBox(Rule(T, Light))->SetPadding(FMargin(0, 4, 0, 10));
			if (!Style->Lore.IsEmpty())
			{
				UTextBlock* Lore = Text(T, Style->Lore.ToString(), 11, Soft, FaceItalic);
				Lore->SetAutoWrapText(true);
				Column->AddChildToVerticalBox(Lore);
			}
			bAny = true;
		}
	}
	if (!bAny)
	{
		QuickLook->SetVisibility(ESlateVisibility::Collapsed);
		return;
	}
	Column->AddChildToVerticalBox(Text(T, TEXT("CLICK TO OPEN ITS ARMOURY"), 7, Dim, FaceBold, 240))->SetPadding(FMargin(0, 14, 0, 0));
	QuickLook->SetContent(Sized(T, Column, 330.0f, 0.0f));
	QuickLook->SetVisibility(ESlateVisibility::HitTestInvisible);
	// beside the card, on the stage's side of it
	if (UCanvasPanelSlot* S = Cast<UCanvasPanelSlot>(QuickLook->Slot))
	{
		const FGeometry& Card = Tile->GetCachedGeometry();
		const FVector2D TopLeft = Root->GetCachedGeometry().AbsoluteToLocal(Card.GetAbsolutePosition());
		const FVector2D Size = Card.GetLocalSize();
		const float Y = FMath::Clamp(static_cast<float>(TopLeft.Y), PanelTop, 1080.0f - PanelBottom - 330.0f);
		if (Info.bLeft)
		{
			S->SetAlignment(FVector2D(0.0f, 0.0f));
			S->SetPosition(FVector2D(TopLeft.X + Size.X + 18.0f, Y));
		}
		else
		{
			S->SetAlignment(FVector2D(1.0f, 0.0f));
			S->SetPosition(FVector2D(TopLeft.X - 118.0f, Y));          // (clear of the attribute column)
		}
	}
}

void USOInventoryWidget::OnTile(const FSOTileInfo& Tile)
{
	if (Tile.Kind == TEXT("wslot") || Tile.Kind == TEXT("aslot") || Tile.Kind == TEXT("mslot"))
	{
		OpenSlot(Tile.Key);
		return;
	}
	// an item in the list: choose it (a second click on the one chosen equips / wears it; a page of the journal is only read)
	if (SelectedKey == Tile.Key && Tile.Kind != TEXT("journal"))
	{
		OnEquip();
		return;
	}
	Choose(Tile.Key);
}

void USOInventoryWidget::Choose(const FString& Key)
{
	SelectedKey = Key;
	HoverKey.Reset();
	DismantleArmedAt = -100.0;
	for (USOInventoryTile* Tile : ListTiles)
	{
		if (Tile)
		{
			Tile->SetChosen(Tile->GetInfo().Key == Key);
		}
	}
	USOSoundLibrary::Play2D(this, Key.StartsWith(TEXT("melee:")) ? TEXT("melee_ready") : TEXT("ui_move"), 0.45f, 0.0f);
	FillInspect();
	FillCompare();
	SyncPreview();
	if (!Inventory)
	{
		return;
	}
	if (const FSOWeaponInstance* W = Inventory->Find(Key); W && W->bNew)
	{
		Inventory->ServerMarkSeen(Key);                           // (the inventory changes: the screen refreshes)
	}
	else if (Key.StartsWith(TEXT("goods:")))
	{
		const FName Id(*Key.RightChop(6));
		if (Inventory->GetGoods().ContainsByPredicate([Id](const FSOGoodsStack& G) { return G.Id == Id && G.bNew; }))
		{
			Inventory->ServerMarkGoodsSeen(Id);
		}
	}
	else if (Key.StartsWith(TEXT("journal:")))
	{
		const FName Id(*Key.RightChop(8));
		if (Inventory->IsJournalNew(Id))
		{
			Inventory->ServerMarkJournalRead(Id);                  // (read: the inventory changes, the screen refreshes)
		}
	}
}

void USOInventoryWidget::OnTileHover(USOInventoryTile* Tile, bool bHover)
{
	if (!Tile)
	{
		return;
	}
	const FSOTileInfo& Info = Tile->GetInfo();
	if (bHover)
	{
		USOSoundLibrary::Play2D(this, TEXT("ui_move"), 0.12f, 0.0f);
	}
	if (OpenSlotId.IsEmpty())
	{
		// the loadout: the mouse takes the highlight to the card it is on; the hovered slot's quick look beside it
		if (bHover)
		{
			FocusColumn = Info.bLeft ? 0 : 1;
			FocusRow = FMath::Max(0, ColumnTiles(FocusColumn).IndexOfByKey(Tile));
			if (bKeyFocus)
			{
				bKeyFocus = false;
				for (int32 Column = 0; Column < 2; ++Column)
				{
					for (USOInventoryTile* Each : ColumnTiles(Column))
					{
						Each->SetFocused(false);
					}
				}
			}
		}
		if (bHover && !Info.bEmpty)
		{
			QuickKey = Info.Key;
			FillQuickLook(Tile);
		}
		else if (!bHover && QuickKey == Info.Key)
		{
			QuickKey.Reset();
			QuickLook->SetVisibility(ESlateVisibility::Collapsed);
		}
		return;
	}
	if (Info.Kind != TEXT("weapon") && Info.Kind != TEXT("armor") && Info.Kind != TEXT("blade") && Info.Kind != TEXT("goods"))
	{
		return;
	}
	const FString Want = bHover ? Info.Key : FString();
	if (HoverKey != Want)
	{
		HoverKey = Want;
		FillInspect();
		FillCompare();
	}
}

void USOInventoryWidget::PeekSlot(const FString& SlotKey)
{
	if (SlotKey.IsEmpty())
	{
		QuickKey.Reset();
		if (QuickLook)
		{
			QuickLook->SetVisibility(ESlateVisibility::Collapsed);
		}
		return;
	}
	for (UVerticalBox* Column : { LeftPanel.Get(), RightPanel.Get() })
	{
		for (UWidget* Child : Column ? Column->GetAllChildren() : TArray<UWidget*>())
		{
			if (USOInventoryTile* Tile = Cast<USOInventoryTile>(Child); Tile && Tile->GetInfo().Key == SlotKey)
			{
				OnTileHover(Tile, true);
				return;
			}
		}
	}
}

USOInventoryWidget::EView USOInventoryWidget::GetView() const
{
	if (OpenSlotId.IsEmpty())
	{
		return EView::Loadout;
	}
	if (OpenSlotId == TEXT("goods"))
	{
		return EView::Goods;
	}
	if (OpenSlotId == TEXT("character"))
	{
		return EView::Character;
	}
	if (OpenSlotId == TEXT("journal"))
	{
		return EView::Journal;
	}
	return IsArmourSlot(OpenSlotId) ? EView::Armour : EView::Arsenal;
}

FName USOInventoryWidget::JournalSection() const
{
	const FSOJournalData& Journal = FSOJournalData::Get();
	const FName Want = Filter.StartsWith(TEXT("section:")) ? FName(*Filter.RightChop(8)) : NAME_None;
	return Journal.FindSection(Want) ? Want : (Journal.Sections.Num() > 0 ? Journal.Sections[0].Id : NAME_None);
}

int32 USOInventoryWidget::CardsPerPage() const
{
	return bListView || GetView() == EView::Journal ? ListRows : Columns * GridRows;
}

TArray<FSOTileInfo> USOInventoryWidget::ListItems() const
{
	TArray<FSOTileInfo> Out;
	if (!Inventory)
	{
		return Out;
	}
	const EView View = GetView();
	const USOLootTables* Tables = USOLootLibrary::GetTables();
	const ESOTileStyle Style = bListView ? ESOTileStyle::Row : ESOTileStyle::Cell;
	const FString Rest = Filter.Contains(TEXT(":")) ? Filter.RightChop(Filter.Find(TEXT(":")) + 1) : FString();
	if (View == EView::Journal)
	{
		// the section's pages in the journal's own order: one learned with its title and what it is (its portrait, how
		// many of them this player has killed), one not yet learned as a locked row with what would teach it
		const FSOJournalData& Journal = FSOJournalData::Get();
		const FName SectionId = JournalSection();
		const FSOJournalSection* Section = Journal.FindSection(SectionId);
		for (const FSOJournalEntry& E : Journal.Entries)
		{
			if (E.Section != SectionId)
			{
				continue;
			}
			FSOTileInfo Tile;
			Tile.Kind = TEXT("journal");
			Tile.Key = TEXT("journal:") + E.Id.ToString();
			Tile.Style = ESOTileStyle::Row;
			Tile.Rarity = Section ? Section->Color : Cyan;
			Tile.bSquare = true;
			Tile.Order = Out.Num();
			if (Inventory->IsJournalOpen(E.Id))
			{
				Tile.Title = E.Title;
				Tile.Tag = E.Sub;
				Tile.Icon = JournalPicture(E.Picture, true);
				Tile.Glyph = Section ? Section->Glyph : 0;
				Tile.bNew = Inventory->IsJournalNew(E.Id);
				Tile.Count = E.Tally.IsNone() || E.Section != TEXT("sarketh") ? -1 : Inventory->GetTally(E.Tally);   // (how many of them killed)
			}
			else
			{
				Tile.Title = TEXT("NOT YET LEARNED");
				Tile.Tag = JournalHint(E);
				Tile.Glyph = 12;
				Tile.bEmpty = true;
				Tile.Rarity = Dim;
			}
			Out.Add(Tile);
		}
		return Out;
	}
	if (View == EView::Arsenal && OpenSlotId == TEXT("melee"))
	{
		// the fists, and every blade owned
		const USOMeleeTable* Melee = USOMeleeTable::Get();
		TArray<FName> Styles = { FName(TEXT("fists")) };
		Styles.Append(Inventory->GetBlades());
		const FName In = Inventory->GetMeleeSlot().IsNone() ? FName(TEXT("fists")) : Inventory->GetMeleeSlot();
		for (int32 i = 0; i < Styles.Num(); ++i)
		{
			const FName Id = Styles[i];
			const FSOMeleeStyle* MeleeStyle = Melee ? Melee->Find(Id) : nullptr;
			const bool bFists = Id == TEXT("fists");
			FSOTileInfo Info;
			Info.Kind = TEXT("blade");
			Info.Key = TEXT("melee:") + Id.ToString();
			Info.Title = MeleeStyle && !MeleeStyle->Name.IsEmpty() ? MeleeStyle->Name.ToString() : Id.ToString();
			Info.Icon = MeleeStyle ? MeleeStyle->Icon.LoadSynchronous() : nullptr;
			Info.Tag = bFists ? TEXT("HAND TO HAND") : TEXT("BLADE  ·  HAND TO HAND");
			Info.Rarity = bFists ? Steel : BladeLight;
			Info.Glyph = bFists ? 11 : 13;
			Info.bEquipped = Id == In;
			Info.Style = Style;
			Info.Order = i;
			Out.Add(Info);
		}
	}
	else if (View == EView::Arsenal)
	{
		// the slot's guns, in the category shown
		const int32 SlotId = FCString::Atoi(*OpenSlotId);
		const FSOWeaponInstance* Equipped = Inventory->GetEquipped(SlotId);
		const TArray<FSOWeaponInstance>& Items = Inventory->GetItems();
		for (int32 i = 0; i < Items.Num(); ++i)
		{
			const FSOWeaponInstance& W = Items[i];
			const USOWeaponData* Data = ArchetypeOf(W);
			if (!Data || FMath::Clamp(Data->Slot, 0, USOInventoryComponent::NumSlots - 1) != SlotId)
			{
				continue;
			}
			if ((Filter.StartsWith(TEXT("family:")) && Data->Family != FName(*Rest)) || (Filter.StartsWith(TEXT("origin:")) && Data->Origin != FName(*Rest)))
			{
				continue;
			}
			FSOTileInfo Info = WeaponTile(W, false);
			Info.PowerDelta = Equipped && Equipped->Uid != W.Uid ? W.Power - Equipped->Power : 0;
			Info.Style = Style;
			Info.RarityIndex = W.Rarity;
			Info.Order = i;                                    // (the vault's order: newest last)
			Out.Add(Info);
		}
	}
	else if (View == EView::Armour)
	{
		const FName SlotId(*OpenSlotId);
		const USOWardrobeData* Wardrobe = USOWardrobeData::Get(Inventory->GetBody());
		const TArray<FSOArmorInstance>& Pieces = Inventory->GetArmor();
		for (int32 i = 0; i < Pieces.Num(); ++i)
		{
			const FSOArmorInstance& A = Pieces[i];
			if (A.Slot == SlotId && (!Wardrobe || Wardrobe->Find(A.Slot, A.Item)))
			{
				FSOTileInfo Info = ArmorTile(A, false);
				Info.Style = Style;
				Info.bSquare = true;
				Info.RarityIndex = A.Rarity;
				Info.Order = i;
				Out.Add(Info);
			}
		}
	}
	else
	{
		// what is held of every collected item, in the category shown
		for (const FSOGoodsStack& Stack : Inventory->GetGoods())
		{
			const FSOGoodsInfo* Info = Tables && Stack.Count > 0 ? Tables->FindGoods(Stack.Id) : nullptr;
			if (!Info || (Filter.StartsWith(TEXT("kind:")) && GoodsKindId(Info->Kind) != Rest))
			{
				continue;
			}
			FSOTileInfo Tile;
			Tile.Kind = TEXT("goods");
			Tile.Key = TEXT("goods:") + Info->Id.ToString();
			Tile.Icon = Info->Icon.LoadSynchronous();
			Tile.Rarity = RarityColor(Info->Rarity);
			Tile.Title = Info->Name.ToString();
			Tile.Tag = FString::Printf(TEXT("%s  ·  %s"), *RarityName(Info->Rarity).ToUpper(), *GoodsKindName(Info->Kind, false));
			Tile.Count = Stack.Count;
			Tile.bNew = Stack.bNew;
			Tile.bSquare = true;
			Tile.Glyph = GoodsKindGlyph(Info->Kind);
			Tile.Style = Style;
			Tile.RarityIndex = Info->Rarity;
			Tile.Order = Tables->Goods.IndexOfByPredicate([Info](const FSOGoodsInfo& G) { return G.Id == Info->Id; });
			Out.Add(Tile);
		}
	}
	// the order: power (collected items: their own order), rarity, the newest, the name; then the equipped first,
	// power, rarity, name
	const bool bGoods = View == EView::Goods;
	const int32 Mode = SortMode;
	Out.StableSort([Mode, bGoods](const FSOTileInfo& A, const FSOTileInfo& B)
	{
		switch (Mode)
		{
		case 1:
			if (A.RarityIndex != B.RarityIndex) return A.RarityIndex > B.RarityIndex;
			break;
		case 2:
			if (A.bNew != B.bNew) return A.bNew;
			if (!bGoods && A.Order != B.Order) return A.Order > B.Order;
			break;
		case 3:
			if (A.Title != B.Title) return A.Title < B.Title;
			break;
		default:
			if (bGoods && A.Order != B.Order) return A.Order < B.Order;
			if (!bGoods && A.Power != B.Power) return A.Power > B.Power;
			break;
		}
		if (A.bEquipped != B.bEquipped) return A.bEquipped;
		if (A.Power != B.Power) return A.Power > B.Power;
		if (A.RarityIndex != B.RarityIndex) return A.RarityIndex > B.RarityIndex;
		return A.Order < B.Order;
	});
	return Out;
}

int32 USOInventoryWidget::PageOf(const FString& Key) const
{
	const TArray<FSOTileInfo> All = ListItems();
	const int32 At = All.IndexOfByPredicate([&Key](const FSOTileInfo& I) { return I.Key == Key; });
	const int32 PerPage = CardsPerPage();
	return At == INDEX_NONE ? 0 : At / FMath::Max(PerPage, 1);
}

void USOInventoryWidget::OnControl(ESOArmouryControl Kind, const FString& Key)
{
	switch (Kind)
	{
	case ESOArmouryControl::Tab:
		if (Key.IsEmpty() && GetView() != EView::Loadout)
		{
			OpenSlot(FString());
		}
		else if (Key == TEXT("arsenal") && GetView() != EView::Arsenal)
		{
			OpenSlot(LastArsenalSlot);
		}
		else if (Key == TEXT("armour") && GetView() != EView::Armour)
		{
			OpenSlot(TEXT("armour"));
		}
		else if (Key == TEXT("goods") && GetView() != EView::Goods)
		{
			OpenSlot(TEXT("goods"));
		}
		else if (Key == TEXT("character") && GetView() != EView::Character)
		{
			OpenSlot(TEXT("character"));
		}
		else if (Key == TEXT("journal") && GetView() != EView::Journal)
		{
			OpenSlot(TEXT("journal"));
		}
		break;
	case ESOArmouryControl::SlotTile:
		if (Key != OpenSlotId)
		{
			OpenSlot(Key);
		}
		break;
	case ESOArmouryControl::Row:
		if (Key.StartsWith(TEXT("group:")))
		{
			SetCreatorGroup(FName(*Key.RightChop(6)));
		}
		else if (Key.StartsWith(TEXT("slot:")))
		{
			if (Key.RightChop(5) != OpenSlotId)
			{
				OpenSlot(Key.RightChop(5));                    // (an armour slot)
			}
		}
		else
		{
			SetFilter(Key);
		}
		break;
	case ESOArmouryControl::Page:
		if (Key == TEXT("prev"))
		{
			StepPage(-1);
		}
		else if (Key == TEXT("next"))
		{
			StepPage(1);
		}
		else
		{
			StepPage(FCString::Atoi(*Key) - 1 - Page);
		}
		break;
	case ESOArmouryControl::Tool:
		if (Key == TEXT("sort"))
		{
			SetSort(SortMode + 1);
		}
		else if (Key == TEXT("reset"))
		{
			ResetLook(false);
		}
		else if (Key == TEXT("resetall") || Key == TEXT("random"))
		{
			// the whole look at once: asked twice (the first press arms it for three seconds)
			if (CreatorArmed == Key && FPlatformTime::Seconds() - CreatorArmedAt < 3.0)
			{
				CreatorArmed.Reset();
				if (Key == TEXT("random"))
				{
					RandomFace();
				}
				else
				{
					ResetLook(true);
				}
			}
			else
			{
				CreatorArmed = Key;
				CreatorArmedAt = FPlatformTime::Seconds();
				USOSoundLibrary::Play2D(this, TEXT("ui_move"), 0.5f, 0.0f);
				Refresh();
			}
		}
		else
		{
			SetListView(Key == TEXT("list"));
		}
		break;
	case ESOArmouryControl::Swatch:
		ChooseTone(Key.StartsWith(TEXT("hair:")), FCString::Atoi(*Key.RightChop(5)));
		break;
	case ESOArmouryControl::Choice:
		if (Inventory && Key.StartsWith(TEXT("body:")) && Inventory->GetBody() != FName(*Key.RightChop(5)))
		{
			Inventory->ServerSetBody(FName(*Key.RightChop(5)));
			USOSoundLibrary::Play2D(this, TEXT("ui_equip"), 0.6f, 0.0f);
		}
		break;
	}
}

void USOInventoryWidget::SetFilter(const FString& InFilter)
{
	if (InFilter == Filter)
	{
		return;
	}
	Filter = InFilter;
	SelectedKey.Reset();
	HoverKey.Reset();
	Page = 0;
	DismantleArmedAt = -100.0;
	USOSoundLibrary::Play2D(this, TEXT("ui_move"), 0.4f, 0.0f);
	Refresh();
}

void USOInventoryWidget::SetSort(int32 Mode)
{
	SortMode = ((Mode % 4) + 4) % 4;
	Page = PageOf(SelectedKey);
	USOSoundLibrary::Play2D(this, TEXT("ui_move"), 0.4f, 0.0f);
	Refresh();
}

void USOInventoryWidget::SetListView(bool bList)
{
	if (bListView == bList)
	{
		return;
	}
	bListView = bList;
	Page = PageOf(SelectedKey);
	USOSoundLibrary::Play2D(this, TEXT("ui_move"), 0.4f, 0.0f);
	Refresh();
}

void USOInventoryWidget::SetDetails(bool bOn)
{
	if (bDetails == bOn)
	{
		return;
	}
	bDetails = bOn;
	USOSoundLibrary::Play2D(this, TEXT("ui_move"), 0.4f, 0.0f);
	FillInspect();
}

void USOInventoryWidget::SetCompare(bool bOn)
{
	if (bComparing == bOn)
	{
		return;
	}
	bComparing = bOn;
	if (bOn)
	{
		USOSoundLibrary::Play2D(this, TEXT("ui_move"), 0.4f, 0.0f);
	}
	FillCompare();
}

void USOInventoryWidget::OnDetails()
{
	if (Inventory && GetView() == EView::Arsenal && Inventory->Find(SelectedKey))
	{
		SetDetails(!bDetails);
		return;
	}
	USOSoundLibrary::Play2D(this, TEXT("ui_deny"), 0.6f, 0.0f);
}

void USOInventoryWidget::OpenSlot(const FString& SlotId)
{
	const FString Want = SlotId == TEXT("armour") ? LastArmourSlot : SlotId;
	if (IsArmourSlot(Want))
	{
		LastArmourSlot = Want;
	}
	if (IsWeaponSlot(Want) || Want == TEXT("melee"))
	{
		LastArsenalSlot = Want;
	}
	const EView Before = GetView();
	OpenSlotId = Want;
	const bool bSameView = Before == GetView() && Before != EView::Loadout;
	if (GetView() == EView::Character)
	{
		bShowedCreator = true;
		CreatorBuilt.Reset();
		if (Before != EView::Character && Preview)
		{
			Preview->TurnTo(GroupYaw(CreatorGroup));
		}
	}
	else if (Before == EView::Character)
	{
		if (Inventory && !Inventory->IsCharacterMade())
		{
			Inventory->ServerSetCharacterMade();               // (a new player's first start is over)
		}
		if (Preview)
		{
			Preview->TurnTo(24.0f);
		}
	}
	SelectedKey.Reset();
	HoverKey.Reset();
	QuickKey.Reset();
	DismantleArmedAt = -100.0;
	Filter.Reset();
	Page = 0;
	bDetails = false;
	bComparing = false;
	if (!Want.IsEmpty() && Inventory)
	{
		// the item there now is the one shown first
		if (IsWeaponSlot(Want))
		{
			if (const FSOWeaponInstance* W = Inventory->GetEquipped(FCString::Atoi(*Want)))
			{
				SelectedKey = W->Uid;
			}
		}
		else if (Want == TEXT("melee"))
		{
			SelectedKey = TEXT("melee:") + (Inventory->GetMeleeSlot().IsNone() ? FString(TEXT("fists")) : Inventory->GetMeleeSlot().ToString());
		}
		else if (const FSOArmorInstance* A = IsArmourSlot(Want) ? Inventory->GetEquippedArmor(FName(*Want)) : nullptr)
		{
			SelectedKey = A->Uid;
		}
		Page = PageOf(SelectedKey);
	}
	USOSoundLibrary::Play2D(this, Want.IsEmpty() ? TEXT("ui_close") : TEXT("ui_open"), 0.45f, 0.0f);
	if (!bSameView)
	{
		Animate();
	}
	Refresh();
}

void USOInventoryWidget::StepTab(int32 Step)
{
	static const TCHAR* Tabs[] = { TEXT(""), TEXT("arsenal"), TEXT("armour"), TEXT("goods"), TEXT("character"), TEXT("journal") };
	constexpr int32 Count = UE_ARRAY_COUNT(Tabs);
	const int32 Now = static_cast<int32>(GetView());
	OnControl(ESOArmouryControl::Tab, Tabs[(Now + Step % Count + Count) % Count]);
}

void USOInventoryWidget::StepSlot(int32 Step)
{
	switch (GetView())
	{
	case EView::Arsenal:
	{
		static const TCHAR* Slots[] = { TEXT("0"), TEXT("1"), TEXT("2"), TEXT("melee") };
		int32 Now = 0;
		for (int32 i = 0; i < 4; ++i)
		{
			Now = OpenSlotId == Slots[i] ? i : Now;
		}
		OpenSlot(Slots[(Now + Step % 4 + 4) % 4]);
		break;
	}
	case EView::Armour:
	{
		const TArray<FName>& Slots = USOWardrobeData::ArmourSlots();
		const int32 Now = FMath::Max(0, Slots.IndexOfByKey(FName(*OpenSlotId)));
		OpenSlot(Slots[(Now + Step % Slots.Num() + Slots.Num()) % Slots.Num()].ToString());
		break;
	}
	case EView::Goods:
	{
		static const TCHAR* Kinds[] = { TEXT(""), TEXT("kind:material"), TEXT("kind:consumable"), TEXT("kind:key"), TEXT("kind:relic") };
		int32 Now = 0;
		for (int32 i = 0; i < 5; ++i)
		{
			Now = Filter == Kinds[i] ? i : Now;
		}
		SetFilter(Kinds[(Now + Step % 5 + 5) % 5]);
		break;
	}
	case EView::Character:
	{
		const TArray<FName> Groups = CreatorGroups();
		if (Groups.Num() > 0)
		{
			const int32 Now = FMath::Max(0, Groups.IndexOfByKey(CreatorGroup));
			SetCreatorGroup(Groups[(Now + Step % Groups.Num() + Groups.Num()) % Groups.Num()]);
		}
		break;
	}
	case EView::Journal:
	{
		const TArray<FSOJournalSection>& Sections = FSOJournalData::Get().Sections;
		if (Sections.Num() > 0)
		{
			const int32 Now = FMath::Max(0, Sections.IndexOfByPredicate([this](const FSOJournalSection& S) { return S.Id == JournalSection(); }));
			SetFilter(TEXT("section:") + Sections[(Now + Step % Sections.Num() + Sections.Num()) % Sections.Num()].Id.ToString());
		}
		break;
	}
	default:
		break;
	}
}

void USOInventoryWidget::StepList(int32 Step)
{
	if (GetView() == EView::Loadout || GetView() == EView::Character)
	{
		return;
	}
	const TArray<FSOTileInfo> All = ListItems();
	if (All.Num() == 0)
	{
		return;
	}
	const int32 Now = All.IndexOfByPredicate([this](const FSOTileInfo& I) { return I.Key == SelectedKey; });
	const int32 Next = Now == INDEX_NONE ? 0 : FMath::Clamp(Now + Step, 0, All.Num() - 1);
	if (Next == Now)
	{
		return;
	}
	const int32 PerPage = CardsPerPage();
	if (Next / PerPage != Page)
	{
		// the choice went over the page's edge: the page turns with it
		Page = Next / PerPage;
		SelectedKey = All[Next].Key;
		Refresh();
	}
	Choose(All[Next].Key);
}

void USOInventoryWidget::StepPage(int32 Step)
{
	if (GetView() == EView::Loadout || GetView() == EView::Character || Step == 0)
	{
		return;
	}
	const TArray<FSOTileInfo> All = ListItems();
	const int32 PerPage = CardsPerPage();
	const int32 Pages = FMath::Max(1, (All.Num() + PerPage - 1) / PerPage);
	const int32 Want = FMath::Clamp(Page + Step, 0, Pages - 1);
	if (Want == Page)
	{
		USOSoundLibrary::Play2D(this, TEXT("ui_deny"), 0.4f, 0.0f);
		return;
	}
	Page = Want;
	SelectedKey = All.IsValidIndex(Want * PerPage) ? All[Want * PerPage].Key : FString();
	HoverKey.Reset();
	DismantleArmedAt = -100.0;
	USOSoundLibrary::Play2D(this, TEXT("ui_move"), 0.45f, 0.0f);
	Refresh();
}

TArray<USOInventoryTile*> USOInventoryWidget::ColumnTiles(int32 Column) const
{
	TArray<USOInventoryTile*> Out;
	if (const UVerticalBox* Panel = Column == 0 ? LeftPanel.Get() : RightPanel.Get())
	{
		for (UWidget* Child : Panel->GetAllChildren())
		{
			if (USOInventoryTile* Tile = Cast<USOInventoryTile>(Child))
			{
				Out.Add(Tile);
			}
		}
	}
	return Out;
}

void USOInventoryWidget::MoveFocus(int32 DX, int32 DY)
{
	if (GetView() == EView::Character)
	{
		CreatorStep(DX, DY);
		return;
	}
	if (!OpenSlotId.IsEmpty())
	{
		// an armoury: through the grid (a row is a column's width); in the list (the journal's too) up and down, left
		// and right the pages
		if (bListView || GetView() == EView::Journal)
		{
			if (DY != 0)
			{
				StepList(DY);
			}
			else if (DX != 0)
			{
				StepPage(DX);
			}
		}
		else
		{
			StepList(DX + DY * Columns);
		}
		return;
	}
	// the loadout: a column (the arsenal, the armour) and a row in it; the first press only shows where it is
	if (bKeyFocus)
	{
		if (DX != 0)
		{
			const int32 From = ColumnTiles(FocusColumn).Num();
			const int32 Column = FMath::Clamp(FocusColumn + DX, 0, 1);
			if (Column != FocusColumn)
			{
				const int32 To = ColumnTiles(Column).Num();
				FocusRow = From > 1 && To > 1 ? FMath::RoundToInt(static_cast<float>(FocusRow) * (To - 1) / (From - 1)) : 0;
				FocusColumn = Column;
			}
		}
		FocusRow += DY;
	}
	bKeyFocus = true;
	USOSoundLibrary::Play2D(this, TEXT("ui_move"), 0.3f, 0.0f);
	ApplyFocus();
}

void USOInventoryWidget::ApplyFocus()
{
	if (!OpenSlotId.IsEmpty())
	{
		return;
	}
	const TArray<USOInventoryTile*> Column = ColumnTiles(FocusColumn);
	FocusRow = Column.Num() > 0 ? FMath::Clamp(FocusRow, 0, Column.Num() - 1) : 0;
	for (int32 Each = 0; Each < 2; ++Each)
	{
		for (USOInventoryTile* Tile : ColumnTiles(Each))
		{
			Tile->SetFocused(bKeyFocus && Each == FocusColumn && Column.IsValidIndex(FocusRow) && Tile == Column[FocusRow]);
		}
	}
	if (bKeyFocus && Column.IsValidIndex(FocusRow))
	{
		USOInventoryTile* Tile = Column[FocusRow];
		if (!Tile->GetInfo().bEmpty)
		{
			QuickKey = Tile->GetInfo().Key;
			FillQuickLook(Tile);
		}
		else
		{
			QuickKey.Reset();
			QuickLook->SetVisibility(ESlateVisibility::Collapsed);
		}
	}
}

void USOInventoryWidget::Accept()
{
	if (GetView() == EView::Character || GetView() == EView::Journal)
	{
		return;                                                  // (left / right choose there; a page is only read)
	}
	if (!OpenSlotId.IsEmpty())
	{
		OnEquip();
		return;
	}
	const TArray<USOInventoryTile*> Column = ColumnTiles(FocusColumn);
	if (Column.IsValidIndex(FocusRow))
	{
		OpenSlot(Column[FocusRow]->GetInfo().Key);
	}
}

FNavigationReply USOInventoryWidget::NativeOnNavigation(const FGeometry& MyGeometry, const FNavigationEvent& InNavigationEvent, const FNavigationReply& InDefaultReply)
{
	// the arrows, the d-pad and the left stick move the armoury's own highlight; nothing else takes the focus
	switch (InNavigationEvent.GetNavigationType())
	{
	case EUINavigation::Up: MoveFocus(0, -1); break;
	case EUINavigation::Down: MoveFocus(0, 1); break;
	case EUINavigation::Left: MoveFocus(-1, 0); break;
	case EUINavigation::Right: MoveFocus(1, 0); break;
	default: break;
	}
	return FNavigationReply::Stop();
}

FReply USOInventoryWidget::NativeOnAnalogValueChanged(const FGeometry& InGeometry, const FAnalogInputEvent& InAnalogEvent)
{
	if (InAnalogEvent.GetKey() == EKeys::Gamepad_RightX)
	{
		StickYaw = InAnalogEvent.GetAnalogValue();
		return FReply::Handled();
	}
	return Super::NativeOnAnalogValueChanged(InGeometry, InAnalogEvent);
}

FCursorReply USOInventoryWidget::NativeOnCursorQuery(const FGeometry& InGeometry, const FPointerEvent& InCursorEvent)
{
	if (bDragging)
	{
		return FCursorReply::Cursor(EMouseCursor::GrabHandClosed);
	}
	return Super::NativeOnCursorQuery(InGeometry, InCursorEvent);
}

void USOInventoryWidget::UpdateLayout(float Width)
{
	LaidOutWidth = Width;
	LastLayoutAt = FPlatformTime::Seconds();
	// the frame: the whole screen up to 2200 wide (an ultrawide keeps it in the middle)
	const float Frame = FMath::Min(Width, 2200.0f);
	const float Side = (Width - Frame) * 0.5f + Margin;
	const float Inner = Frame - 2.0f * Margin;
	// an armoury: its column, the grid (fewer columns when narrow), the stage between it and the panel
	Columns = Inner >= 1500.0f ? 4 : 3;
	CellWidth = Columns == 4 ? 134.0f : 130.0f;
	GridWidth = Columns * CellWidth + (Columns - 1) * CellGap;
	InspectWidth = FMath::Clamp(Inner * 0.28f, 440.0f, 520.0f);
	const float GridLeft = Side + CatWidth + ColumnGap;
	if (GetView() == EView::Journal)
	{
		// (no stand-in: the reading pane from beyond the list to the frame's edge, at most a comfortable line)
		InspectWidth = FMath::Clamp(Width - Side - (GridLeft + GridWidth + 2.0f * ColumnGap), 440.0f, 980.0f);
	}
	const float PanelLeft = Width - Side - InspectWidth;
	const bool bLoadout = GetView() == EView::Loadout;
	StageX = bLoadout ? Width * 0.5f : GetView() == EView::Character ? (GridLeft + GridWidth + Width - Side) * 0.5f : (GridLeft + GridWidth + PanelLeft) * 0.5f;
	// the tabs between the banner's two ends, or on a row of their own under it where they would touch either
	const float LeftW = BannerLeft ? static_cast<float>(BannerLeft->GetDesiredSize().X) : 0.0f;
	const float RightW = BannerRight ? static_cast<float>(BannerRight->GetDesiredSize().X) : 0.0f;
	const float TabsW = TabRow ? static_cast<float>(TabRow->GetDesiredSize().X) : 0.0f;
	const bool bTabsBelow = TabsW > 1.0f && (Width * 0.5f - TabsW * 0.5f < Side + LeftW + 24.0f || Width * 0.5f + TabsW * 0.5f > Width - Side - RightW - 24.0f);
	PanelsTop = bTabsBelow ? PanelTop + 46.0f : PanelTop;
	auto Offsets = [](UWidget* W, const FMargin& M)
	{
		if (UCanvasPanelSlot* S = W ? Cast<UCanvasPanelSlot>(W->Slot) : nullptr)
		{
			if (!(S->GetOffsets() == M))
			{
				S->SetOffsets(M);
			}
		}
	};
	Offsets(BannerLeft, FMargin(Side, BannerY, 0.0f, 0.0f));
	Offsets(BannerRight, FMargin(-Side, BannerY, 0.0f, 0.0f));
	Offsets(TabRow, FMargin(0.0f, bTabsBelow ? 126.0f : BannerY, 0.0f, 0.0f));
	Offsets(BannerRule, FMargin(Side, 100.0f, Side, 1.0f));
	Offsets(BannerLit, FMargin(Side, 99.0f, 120.0f, 2.0f));
	Offsets(LeftPanel, FMargin(Side, PanelsTop, PanelWidth, PanelBottom));
	Offsets(RightPanel, FMargin(-(Side + PanelWidth), PanelsTop, PanelWidth, PanelBottom));
	Offsets(AttributeColumn, FMargin(-(Side + PanelWidth + 104.0f), PanelsTop + 114.0f, 84.0f, 0.0f));
	Offsets(CategoryPanel, FMargin(Side, PanelsTop, CatWidth, PanelBottom));
	Offsets(GridPanel, FMargin(GridLeft, PanelsTop, GridWidth, PanelBottom));
	Offsets(InspectPanel, FMargin(-(Side + InspectWidth), PanelsTop, InspectWidth, PanelBottom));
	Offsets(CompareBox, FMargin(GridLeft, PanelsTop + 50.0f, 0.0f, 0.0f));
	Offsets(PreviewImage, FMargin(StageX, StageTop, StageWidth, StageHeight));
	Offsets(FloorImage, FMargin(StageX, FootY, 640.0f, 176.0f));
	Offsets(FooterRule, FMargin(Side, -(1080.0f - FooterRuleY), Side, 1.0f));
	Offsets(HintRow, FMargin(-Side + 22.0f, -(1080.0f - HintY), 0.0f, 0.0f));
	Offsets(DragHint, FMargin(Side, -(1080.0f - HintY), 0.0f, 0.0f));
	const float DragW = DragHint ? static_cast<float>(DragHint->GetDesiredSize().X) : 0.0f;
	Offsets(BodyToggle, FMargin(Side + FMath::Max(DragW, 100.0f) + 4.0f, -(1080.0f - HintY), 0.0f, 0.0f));
	if (EquipKey)
	{
		EquipKey->SetVisibility(InspectWidth >= 480.0f ? ESlateVisibility::SelfHitTestInvisible : ESlateVisibility::Collapsed);
	}
	// narrow (4:3, 5:4): the attributes give way, the character keeps the middle between the panels
	if (AttributeColumn)
	{
		AttributeColumn->SetVisibility(bLoadout && Inner >= 1650.0f ? ESlateVisibility::SelfHitTestInvisible : ESlateVisibility::Collapsed);
	}
}

void USOInventoryWidget::SyncPreview()
{
	if (!Preview || !Inventory)
	{
		return;
	}
	if (GetView() == EView::Character)
	{
		// the builder: close on the face or on head and shoulders, the body alone, the look as it is being moved
		const FSOOutfit Look = CurrentLook();
		Preview->SetFraming(GroupClose(CreatorGroup), true);
		Preview->Sync(Inventory, FString(), FString(), &Look);
		if (StageMaterial)
		{
			StageMaterial->SetScalarParameterValue(TEXT("Edge"), 0.16f);   // (the shoulders fade out at the picture's sides)
		}
		return;
	}
	Preview->SetFraming(0.0f, false);
	if (StageMaterial)
	{
		StageMaterial->SetScalarParameterValue(TEXT("Edge"), 0.0f);
	}
	FString Weapon, Armor;
	if (!OpenSlotId.IsEmpty())
	{
		if (SelectedKey.StartsWith(TEXT("melee:")) || Inventory->Find(SelectedKey))
		{
			Weapon = SelectedKey;
		}
		else if (Inventory->FindArmor(SelectedKey))
		{
			Armor = SelectedKey;
		}
	}
	Preview->Sync(Inventory, Weapon, Armor);
}

void USOInventoryWidget::OnEquip()
{
	if (!Inventory || OpenSlotId.IsEmpty())
	{
		return;
	}
	if (SelectedKey.StartsWith(TEXT("goods:")))
	{
		// a consumable: used on the body (and only when it would do something)
		const FName Id(*SelectedKey.RightChop(6));
		if (Inventory->CanUseGoods(Id))
		{
			Inventory->ServerUseGoods(Id);
			USOSoundLibrary::Play2D(this, TEXT("ui_equip"), 0.7f, 0.0f);
		}
		else
		{
			USOSoundLibrary::Play2D(this, TEXT("ui_deny"), 0.6f, 0.0f);
		}
		return;
	}
	if (SelectedKey.StartsWith(TEXT("melee:")))
	{
		const FName Id(*SelectedKey.RightChop(6));
		const FName In = Inventory->GetMeleeSlot().IsNone() ? FName(TEXT("fists")) : Inventory->GetMeleeSlot();
		if (Id != In)
		{
			Inventory->ServerSetMeleeSlot(Id);
			USOSoundLibrary::Play2D(this, TEXT("ui_equip"), 0.7f, 0.0f);
		}
		return;
	}
	if (const FSOWeaponInstance* W = Inventory->Find(SelectedKey))
	{
		if (!Inventory->IsEquipped(W->Uid))
		{
			Inventory->ServerEquip(W->Uid);
			USOSoundLibrary::Play2D(this, TEXT("ui_equip"), 0.7f, 0.0f);
		}
	}
	else if (const FSOArmorInstance* A = Inventory->FindArmor(SelectedKey))
	{
		if (A->bEquipped && !USOWardrobeData::IsOptionalSlot(A->Slot))
		{
			USOSoundLibrary::Play2D(this, TEXT("ui_deny"), 0.6f, 0.0f);
			return;
		}
		Inventory->ServerEquipArmor(A->Uid);
		USOSoundLibrary::Play2D(this, TEXT("ui_equip"), 0.7f, 0.0f);
	}
}

void USOInventoryWidget::ShowUpgrade(const FString& Uid)
{
	UWidgetTree* T = WidgetTree;
	UpgradeGoodsRow->ClearChildren();
	UpgradeGoodsRow->SetVisibility(ESlateVisibility::Collapsed);
	int32 NewPower = 0, CostCredits = 0, CostAlloy = 0;
	if (Uid.IsEmpty() || !Inventory)
	{
		UpgradeButton->SetIsEnabled(false);
		UpgradeLabel->SetText(FText::FromString(TEXT("RAISE")));
		UpgradeLabel->SetColorAndOpacity(FSlateColor(Dim));
		return;
	}
	if (!Inventory->GetUpgrade(Uid, NewPower, CostCredits, CostAlloy))
	{
		// as far as this level lets it go
		UpgradeButton->SetIsEnabled(false);
		UpgradeLabel->SetText(FText::FromString(FString::Printf(TEXT("AS HIGH AS LEVEL %d ALLOWS  (%d)"), Inventory->GetLevel(), Inventory->GetPowerCap())));
		UpgradeLabel->SetColorAndOpacity(FSlateColor(Dim));
		return;
	}
	TArray<FSOGoodsCost> Takes;
	Inventory->GetUpgradeGoods(Uid, Takes);
	const bool bCredits = Inventory->GetCredits() >= CostCredits, bAlloy = Inventory->GetAlloy() >= CostAlloy, bGoods = Inventory->HasGoods(Takes);
	const bool bCanPay = bCredits && bAlloy && bGoods;
	UpgradeButton->SetIsEnabled(bCanPay);
	UpgradeLabel->SetText(FText::FromString(FString::Printf(TEXT("RAISE TO %d"), NewPower)));
	UpgradeLabel->SetColorAndOpacity(FSlateColor(bCanPay ? Ink : Bad));
	// what it takes, each in red where there is not enough of it
	auto Cost = [&](int32 GlyphIndex, const FString& Words, bool bHave)
	{
		UHorizontalBox* One = Make<UHorizontalBox>(T);
		if (GlyphIndex >= 0)
		{
			One->AddChildToHorizontalBox(Glyph(T, this, GlyphIndex, bHave ? Soft : Bad, 10.0f))->SetVerticalAlignment(VAlign_Center);
		}
		UHorizontalBoxSlot* W = One->AddChildToHorizontalBox(Text(T, Words, 8, bHave ? Soft : Bad, FaceBold, 140));
		W->SetPadding(FMargin(GlyphIndex >= 0 ? 4.0f : 0.0f, 0, 0, 0));
		W->SetVerticalAlignment(VAlign_Center);
		UpgradeGoodsRow->AddChildToWrapBox(One);
	};
	Cost(1, FString::Printf(TEXT("%s CREDITS"), *Number(CostCredits)), bCredits);
	Cost(2, FString::Printf(TEXT("%s ALLOY"), *Number(CostAlloy)), bAlloy);
	const USOLootTables* Tables = USOLootLibrary::GetTables();
	for (const FSOGoodsCost& C : Takes)
	{
		if (const FSOGoodsInfo* Info = Tables ? Tables->FindGoods(C.Item) : nullptr)
		{
			Cost(-1, FString::Printf(TEXT("%d %s  (%s)"), C.Count, *Info->Name.ToString().ToUpper(), *Number(Inventory->CountOf(C.Item))), Inventory->CountOf(C.Item) >= C.Count);
		}
	}
	UpgradeGoodsRow->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
}

void USOInventoryWidget::OnUpgrade()
{
	int32 NewPower = 0, CostCredits = 0, CostAlloy = 0;
	if (!Inventory || OpenSlotId.IsEmpty() || SelectedKey.IsEmpty() || !Inventory->GetUpgrade(SelectedKey, NewPower, CostCredits, CostAlloy)
		|| Inventory->GetCredits() < CostCredits || Inventory->GetAlloy() < CostAlloy)
	{
		USOSoundLibrary::Play2D(this, TEXT("ui_deny"), 0.6f, 0.0f);
		return;
	}
	Inventory->ServerUpgrade(SelectedKey);
	USOSoundLibrary::Play2D(this, TEXT("ui_equip"), 0.7f, 0.0f);
}

void USOInventoryWidget::OnLock()
{
	if (const FSOWeaponInstance* W = Inventory && !OpenSlotId.IsEmpty() ? Inventory->Find(SelectedKey) : nullptr)
	{
		Inventory->ServerSetKeep(W->Uid, !W->bKeep);
		USOSoundLibrary::Play2D(this, TEXT("ui_lock"), 0.6f, 0.0f);
	}
}

void USOInventoryWidget::OnDismantle()
{
	const FSOWeaponInstance* W = Inventory && !OpenSlotId.IsEmpty() ? Inventory->Find(SelectedKey) : nullptr;
	if (!W || Inventory->IsEquipped(W->Uid) || W->bKeep)
	{
		USOSoundLibrary::Play2D(this, TEXT("ui_deny"), 0.6f, 0.0f);
		return;
	}
	if (FPlatformTime::Seconds() - DismantleArmedAt > 2.5)
	{
		DismantleArmedAt = FPlatformTime::Seconds();             // press again to confirm
		FillInspect();
		return;
	}
	DismantleArmedAt = -100.0;
	const FString Gone = W->Uid;
	// the next one in the list is chosen in its place
	const TArray<FSOTileInfo> All = ListItems();
	const int32 At = All.IndexOfByPredicate([&Gone](const FSOTileInfo& I) { return I.Key == Gone; });
	SelectedKey.Reset();
	if (At != INDEX_NONE && All.Num() > 1)
	{
		SelectedKey = All[At + 1 < All.Num() ? At + 1 : At - 1].Key;
	}
	HoverKey.Reset();
	Inventory->ServerDismantle(Gone);
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
		SpinVelocity = 0.0f;
		if (Preview)
		{
			Preview->StopTurning();
		}
		LastDragTime = FPlatformTime::Seconds();
		return FReply::Handled().CaptureMouse(TakeWidget()).SetUserFocus(TakeWidget());
	}
	if (InMouseEvent.GetEffectingButton() == EKeys::RightMouseButton && !OpenSlotId.IsEmpty() && !bComparing)
	{
		OpenSlot(FString());                                     // (a right click goes back, as Esc does)
		return FReply::Handled();
	}
	return Super::NativeOnMouseButtonDown(InGeometry, InMouseEvent);
}

FReply USOInventoryWidget::NativeOnMouseButtonUp(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent)
{
	if (bDragging)
	{
		bDragging = false;
		if (FPlatformTime::Seconds() - LastDragTime > 0.08)
		{
			SpinVelocity = 0.0f;                                  // (it was held still before it was let go)
		}
		return FReply::Handled().ReleaseMouseCapture();
	}
	return Super::NativeOnMouseButtonUp(InGeometry, InMouseEvent);
}

FReply USOInventoryWidget::NativeOnMouseMove(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent)
{
	if (bDragging && Preview)
	{
		const float Turn = -static_cast<float>(InMouseEvent.GetCursorDelta().X) * 0.45f;
		Preview->Yaw += Turn;
		const double Now = FPlatformTime::Seconds();
		const float Dt = FMath::Max(static_cast<float>(Now - LastDragTime), 1.0f / 240.0f);
		SpinVelocity = FMath::Lerp(SpinVelocity, FMath::Clamp(Turn / Dt, -900.0f, 900.0f), 0.5f);
		LastDragTime = Now;
		return FReply::Handled();
	}
	return Super::NativeOnMouseMove(InGeometry, InMouseEvent);
}

FReply USOInventoryWidget::NativeOnKeyDown(const FGeometry& InGeometry, const FKeyEvent& InKeyEvent)
{
	const FKey Key = InKeyEvent.GetKey();
	auto Is = [&Key](std::initializer_list<FKey> Keys)
	{
		for (const FKey& K : Keys)
		{
			if (Key == K)
			{
				return true;
			}
		}
		return false;
	};
	if (Is({ EKeys::Escape, EKeys::Gamepad_FaceButton_Right }))
	{
		if (!OpenSlotId.IsEmpty())
		{
			OpenSlot(FString());                                 // back to the loadout first
		}
		else
		{
			Close();
		}
		return FReply::Handled();
	}
	if (Is({ EKeys::I, EKeys::Tab, EKeys::Gamepad_Special_Left }))
	{
		Close();
		return FReply::Handled();
	}
	if (Is({ EKeys::Q, EKeys::Gamepad_LeftTrigger }))
	{
		StepTab(-1);
	}
	else if (Is({ EKeys::E, EKeys::Gamepad_RightTrigger }))
	{
		StepTab(1);
	}
	else if (Is({ EKeys::A, EKeys::Gamepad_LeftShoulder }))
	{
		StepSlot(-1);
	}
	else if (Is({ EKeys::D, EKeys::Gamepad_RightShoulder }))
	{
		StepSlot(1);
	}
	else if (Key == EKeys::W)
	{
		MoveFocus(0, -1);
	}
	else if (Key == EKeys::S)
	{
		MoveFocus(0, 1);
	}
	else if (Is({ EKeys::Enter, EKeys::SpaceBar, EKeys::Gamepad_FaceButton_Bottom, EKeys::Virtual_Accept }))
	{
		Accept();
	}
	else if (Is({ EKeys::F, EKeys::Gamepad_RightThumbstick }))
	{
		OnDetails();
	}
	else if (Is({ EKeys::R, EKeys::Gamepad_Special_Right }))
	{
		if (GetView() == EView::Character)
		{
			ResetLook(false);                                    // (the builder: the group back to the body's own)
		}
		else
		{
			OnLock();
		}
	}
	else if (Is({ EKeys::X, EKeys::Gamepad_FaceButton_Left }))
	{
		OnDismantle();
	}
	else if (Is({ EKeys::U, EKeys::Gamepad_FaceButton_Top }))
	{
		OnUpgrade();
	}
	else if (Is({ EKeys::C, EKeys::Gamepad_LeftThumbstick }))
	{
		if (!InKeyEvent.IsRepeat())
		{
			SetCompare(true);                                    // (held: let go, it closes)
		}
	}
	else if (Key == EKeys::Z)
	{
		if (GetView() != EView::Loadout && GetView() != EView::Character && GetView() != EView::Journal)
		{
			SetSort(SortMode + 1);
		}
	}
	else if (Key == EKeys::V)
	{
		if (GetView() != EView::Loadout && GetView() != EView::Character && GetView() != EView::Journal)
		{
			SetListView(!bListView);
		}
	}
	else if (Is({ EKeys::PageUp, EKeys::LeftBracket }))
	{
		StepPage(-1);
	}
	else if (Is({ EKeys::PageDown, EKeys::RightBracket }))
	{
		StepPage(1);
	}
	else if (Is({ EKeys::One, EKeys::Two, EKeys::Three }))
	{
		if (Inventory)
		{
			Inventory->ServerSelectSlot(Key == EKeys::One ? 0 : Key == EKeys::Two ? 1 : 2);
		}
	}
	else
	{
		return Super::NativeOnKeyDown(InGeometry, InKeyEvent);
	}
	return FReply::Handled();
}

FReply USOInventoryWidget::NativeOnKeyUp(const FGeometry& InGeometry, const FKeyEvent& InKeyEvent)
{
	if (InKeyEvent.GetKey() == EKeys::C || InKeyEvent.GetKey() == EKeys::Gamepad_LeftThumbstick)
	{
		SetCompare(false);
		return FReply::Handled();
	}
	return Super::NativeOnKeyUp(InGeometry, InKeyEvent);
}

FReply USOInventoryWidget::NativeOnMouseWheel(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent)
{
	// over the grid the wheel turns its pages (over the inspect panel its own scroll takes it first)
	if (GetView() != EView::Loadout && GetView() != EView::Character && GridPanel && GridPanel->GetCachedGeometry().IsUnderLocation(InMouseEvent.GetScreenSpacePosition()))
	{
		StepPage(InMouseEvent.GetWheelDelta() < 0.0f ? 1 : -1);
		return FReply::Handled();
	}
	return Super::NativeOnMouseWheel(InGeometry, InMouseEvent);
}

// --- Character builder ---------------------------------------------------------------------------------

TSharedRef<SWidget> USOCreatorSlider::RebuildWidget()
{
	if (WidgetTree && !WidgetTree->RootWidget)
	{
		UWidgetTree* T = WidgetTree;
		Frame = Box(T, FSlateNoResource(), FMargin(0));
		Frame->SetVisibility(ESlateVisibility::Visible);
		UCanvasPanel* Canvas = Make<UCanvasPanel>(T);
		auto Put = [&](UWidget* W, const FVector2D& At, const FVector2D& Size, const FVector2D& Align, bool bAuto)
		{
			UCanvasPanelSlot* S = Canvas->AddChildToCanvas(W);
			S->SetAutoSize(bAuto);
			S->SetAlignment(Align);
			S->SetPosition(At);
			if (!bAuto)
			{
				S->SetSize(Size);
			}
			return S;
		};
		const float Y = 37.0f;
		const float X0 = TrackLeft(), X1 = TrackRight(), Mid = (X0 + X1) * 0.5f;
		AccentBar = Box(T, FSlateColorBrush(Cyan), FMargin(0));
		Put(AccentBar, FVector2D(0.0f, 9.0f), FVector2D(3.0f, Height - 18.0f), FVector2D::ZeroVector, false);
		LabelText = Fit(Text(T, Label.ToUpper(), 10, Soft, FaceBold, 170));
		Put(Sized(T, LabelText, Width - 120.0f, 0.0f), FVector2D(18.0f, 8.0f), FVector2D::ZeroVector, FVector2D::ZeroVector, true);
		ValueText = Text(T, TEXT("0"), 11, Dim, FaceBold, 40);
		ValueText->SetJustification(ETextJustify::Right);
		Put(Sized(T, ValueText, 64.0f, 0.0f), FVector2D(Width - 18.0f, 7.0f), FVector2D::ZeroVector, FVector2D(1.0f, 0.0f), true);
		// the track, its quarters, the middle, the fill from the middle, the knob
		Put(Box(T, FSlateColorBrush(FLinearColor(1.0f, 1.0f, 1.0f, 0.13f)), FMargin(0)), FVector2D(X0, Y - 1.0f), FVector2D(X1 - X0, 2.0f), FVector2D::ZeroVector, false);
		for (const float F : { -1.0f, -0.5f, 0.5f, 1.0f })
		{
			Put(Box(T, FSlateColorBrush(FLinearColor(1.0f, 1.0f, 1.0f, 0.18f)), FMargin(0)), FVector2D(Mid + F * (X1 - Mid) - 0.5f, Y - 3.0f), FVector2D(1.0f, 6.0f), FVector2D::ZeroVector, false);
		}
		Put(Box(T, FSlateColorBrush(Alpha(Soft, 0.95f)), FMargin(0)), FVector2D(Mid - 1.0f, Y - 6.0f), FVector2D(2.0f, 12.0f), FVector2D::ZeroVector, false);
		FillBar = Box(T, FSlateColorBrush(Cyan), FMargin(0));
		Put(FillBar, FVector2D(Mid, Y - 1.5f), FVector2D(0.0f, 3.0f), FVector2D::ZeroVector, false);
		Knob = Box(T, FSlateRoundedBoxBrush(Ink, 6.0f, Alpha(Cyan, 1.0f), 2.0f), FMargin(0));
		Put(Knob, FVector2D(Mid, Y), FVector2D(12.0f, 12.0f), FVector2D(0.5f, 0.5f), false);
		Frame->SetContent(Sized(T, Canvas, Width, Height));
		WidgetTree->RootWidget = Frame;
		Restyle();
		SetValue(Value);
	}
	return Super::RebuildWidget();
}

void USOCreatorSlider::SetValue(float InValue)
{
	Value = FMath::Clamp(InValue, -1.0f, 1.0f);
	if (!Knob || !FillBar || !ValueText)
	{
		return;
	}
	const float X0 = TrackLeft(), X1 = TrackRight(), Mid = (X0 + X1) * 0.5f;
	const float X = Mid + Value * (X1 - Mid);
	if (UCanvasPanelSlot* S = Cast<UCanvasPanelSlot>(Knob->Slot))
	{
		S->SetPosition(FVector2D(X, 37.0f));
	}
	if (UCanvasPanelSlot* S = Cast<UCanvasPanelSlot>(FillBar->Slot))
	{
		S->SetPosition(FVector2D(FMath::Min(X, Mid), 35.5f));
		S->SetSize(FVector2D(FMath::Abs(X - Mid), 3.0f));
	}
	const int32 Shown = FMath::RoundToInt(Value * 100.0f);
	ValueText->SetText(FText::FromString(Shown == 0 ? FString(TEXT("0")) : FString::Printf(TEXT("%+d"), Shown)));
	ValueText->SetColorAndOpacity(FSlateColor(Shown == 0 ? Dim : Cyan));
}

void USOCreatorSlider::SetFocused(bool bOn)
{
	if (bFocused != bOn)
	{
		bFocused = bOn;
		Restyle();
	}
}

void USOCreatorSlider::Restyle()
{
	if (!Frame)
	{
		return;
	}
	const bool bLit = bHovered || bFocused || bDragging;
	FPlate P;
	P.Cut = 8.0f;
	P.Fill = bLit ? FLinearColor(0.010f, 0.028f, 0.046f, 0.93f) : FLinearColor(0.006f, 0.009f, 0.018f, 0.86f);
	P.FillLow = bLit ? FLinearColor(0.006f, 0.017f, 0.028f, 0.94f) : FLinearColor(0.004f, 0.006f, 0.012f, 0.88f);
	P.Edge = bLit ? Alpha(Cyan, bFocused ? 0.8f : 0.5f) : FLinearColor(1.0f, 1.0f, 1.0f, 0.10f);
	P.TopLight = bLit ? 1.0f : 0.0f;
	Frame->SetBrush(PlateBrush(this, P));
	if (LabelText)
	{
		LabelText->SetColorAndOpacity(FSlateColor(bLit ? Ink : Soft));
	}
	if (AccentBar)
	{
		AccentBar->SetVisibility(bFocused ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Hidden);
	}
}

float USOCreatorSlider::ValueAt(const FGeometry& Geometry, const FPointerEvent& Event) const
{
	const float X = static_cast<float>(Geometry.AbsoluteToLocal(Event.GetScreenSpacePosition()).X);
	const float Mid = (TrackLeft() + TrackRight()) * 0.5f;
	float V = FMath::Clamp((X - Mid) / FMath::Max(1.0f, TrackRight() - Mid), -1.0f, 1.0f);
	if (FMath::Abs(V) < 0.035f)
	{
		V = 0.0f;                                                // (a catch at the middle: the body's own)
	}
	return FMath::RoundToFloat(V * 100.0f) / 100.0f;
}

FReply USOCreatorSlider::NativeOnMouseButtonDown(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent)
{
	if (InMouseEvent.GetEffectingButton() == EKeys::LeftMouseButton)
	{
		bDragging = true;
		SetValue(ValueAt(InGeometry, InMouseEvent));
		Restyle();
		if (Screen)
		{
			Screen->OnSlider(Key, Value, false);
		}
		return FReply::Handled().CaptureMouse(TakeWidget());
	}
	return Super::NativeOnMouseButtonDown(InGeometry, InMouseEvent);
}

FReply USOCreatorSlider::NativeOnMouseMove(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent)
{
	if (bDragging)
	{
		const float V = ValueAt(InGeometry, InMouseEvent);
		if (!FMath::IsNearlyEqual(V, Value))
		{
			SetValue(V);
			if (Screen)
			{
				Screen->OnSlider(Key, Value, false);
			}
		}
		return FReply::Handled();
	}
	return Super::NativeOnMouseMove(InGeometry, InMouseEvent);
}

FReply USOCreatorSlider::NativeOnMouseButtonUp(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent)
{
	if (bDragging)
	{
		bDragging = false;
		Restyle();
		if (Screen)
		{
			Screen->OnSlider(Key, Value, true);
		}
		return FReply::Handled().ReleaseMouseCapture();
	}
	return Super::NativeOnMouseButtonUp(InGeometry, InMouseEvent);
}

FReply USOCreatorSlider::NativeOnMouseButtonDoubleClick(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent)
{
	SetValue(0.0f);
	if (Screen)
	{
		Screen->OnSlider(Key, 0.0f, true);
	}
	return FReply::Handled();
}

FReply USOCreatorSlider::NativeOnMouseWheel(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent)
{
	const float Step = InMouseEvent.GetWheelDelta() > 0.0f ? 0.05f : -0.05f;
	SetValue(FMath::Clamp(FMath::RoundToFloat((Value + Step) * 20.0f) / 20.0f, -1.0f, 1.0f));
	if (Screen)
	{
		Screen->OnSlider(Key, Value, true);
	}
	return FReply::Handled();
}

void USOCreatorSlider::NativeOnMouseEnter(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent)
{
	Super::NativeOnMouseEnter(InGeometry, InMouseEvent);
	bHovered = true;
	Restyle();
	if (Screen)
	{
		Screen->OnSliderHover(Key);
	}
}

void USOCreatorSlider::NativeOnMouseLeave(const FPointerEvent& InMouseEvent)
{
	Super::NativeOnMouseLeave(InMouseEvent);
	bHovered = false;
	Restyle();
}

bool USOInventoryWidget::HasMorph(FName Key) const
{
	const USOWardrobeData* Wardrobe = Inventory ? USOWardrobeData::Get(Inventory->GetBody()) : nullptr;
	const USkeletalMesh* Mesh = Wardrobe ? Wardrobe->BodyMesh.LoadSynchronous() : nullptr;
	return Mesh && Mesh->FindMorphTarget(FName(*(TEXT("face_") + Key.ToString()))) != nullptr;
}

TArray<FName> USOInventoryWidget::CreatorGroups() const
{
	TArray<FName> Out;
	for (const FSOCreatorGroup& G : FSOCreatorData::Get().Groups)
	{
		bool bAny = G.Sliders.Num() == 0;
		for (const TPair<FName, FString>& S : G.Sliders)
		{
			bAny |= HasMorph(S.Key);
		}
		if (bAny)
		{
			Out.Add(G.Id);
		}
	}
	return Out;
}

FSOOutfit USOInventoryWidget::CurrentLook() const
{
	FSOOutfit Look = Inventory ? Inventory->GetOutfit() : FSOOutfit();
	for (const TPair<FName, FPendingValue>& P : PendingFace)
	{
		const int32 i = Look.FaceKeys.IndexOfByKey(P.Key);
		if (FMath::IsNearlyZero(P.Value.Value, 1e-3f))
		{
			if (i != INDEX_NONE)
			{
				Look.FaceKeys.RemoveAt(i);
				if (Look.FaceValues.IsValidIndex(i))
				{
					Look.FaceValues.RemoveAt(i);
				}
			}
		}
		else if (i == INDEX_NONE || !Look.FaceValues.IsValidIndex(i))
		{
			Look.FaceKeys.Add(P.Key);
			Look.FaceValues.SetNum(Look.FaceKeys.Num() - 1);
			Look.FaceValues.Add(P.Value.Value);
		}
		else
		{
			Look.FaceValues[i] = P.Value.Value;
		}
	}
	const double Now = FPlatformTime::Seconds();
	if (Now - PendingSkinAt < 2.5)
	{
		Look.SkinTone = PendingSkin;
	}
	if (Now - PendingHairAt < 2.5)
	{
		Look.HairTone = PendingHair;
	}
	return Look;
}

void USOInventoryWidget::FillCharacter()
{
	UWidgetTree* T = WidgetTree;
	const FSOCreatorData& Data = FSOCreatorData::Get();
	ListTiles.Reset();
	QuickLook->SetVisibility(ESlateVisibility::Collapsed);
	QuickKey.Reset();
	const TArray<FName> Groups = CreatorGroups();
	if (!Groups.Contains(CreatorGroup) && Groups.Num() > 0)
	{
		CreatorGroup = Groups[0];
	}
	// what was moved and is on the profile now (or was let go a while ago) waits no more
	const double Now = FPlatformTime::Seconds();
	for (auto It = PendingFace.CreateIterator(); It; ++It)
	{
		if (Now - It.Value().At > 2.5 || (Now >= It.Value().At && FMath::IsNearlyEqual(Inventory->GetFace(It.Key()), It.Value().Value, 2e-3f)))
		{
			It.RemoveCurrent();
		}
	}
	if (Inventory->GetSkinTone().Equals(PendingSkin, 1e-3f))
	{
		PendingSkinAt = -100.0;
	}
	if (Inventory->GetHairTone().Equals(PendingHair, 1e-3f))
	{
		PendingHairAt = -100.0;
	}
	if (Now - CreatorArmedAt > 3.0)
	{
		CreatorArmed.Reset();
	}
	const FSOOutfit Look = CurrentLook();
	auto FaceValue = [&Look](FName Key)
	{
		const int32 i = Look.FaceKeys.IndexOfByKey(Key);
		return i != INDEX_NONE && Look.FaceValues.IsValidIndex(i) ? Look.FaceValues[i] : 0.0f;
	};

	// --- the column: the builder's name and line, its groups (a face group's figure: how many of its sliders are
	// moved), the whole look at once at its foot
	CategoryPanel->ClearChildren();
	CategoryPanel->AddChildToVerticalBox(Fit(Text(T, TEXT("CHARACTER"), 26, Ink, FaceCond, 140)));
	{
		UHorizontalBox* Under = Make<UHorizontalBox>(T);
		Under->AddChildToHorizontalBox(Sized(T, Box(T, FSlateColorBrush(Cyan), FMargin(0)), 3.0f, 10.0f))->SetVerticalAlignment(VAlign_Center);
		UHorizontalBoxSlot* L = Under->AddChildToHorizontalBox(Fit(Text(T, TEXT("WHO WEARS THE ARMOUR"), 8, Soft, FaceBold, 220)));
		L->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
		L->SetPadding(FMargin(8, 0, 0, 0));
		L->SetVerticalAlignment(VAlign_Center);
		CategoryPanel->AddChildToVerticalBox(Under)->SetPadding(FMargin(0, 2, 0, 14));
	}
	for (const FName Id : Groups)
	{
		const FSOCreatorGroup* G = Data.Find(Id);
		int32 Moved = 0;
		for (const TPair<FName, FString>& S : G->Sliders)
		{
			Moved += HasMorph(S.Key) && !FMath::IsNearlyZero(FaceValue(S.Key), 1e-3f) ? 1 : 0;
		}
		USOArmouryButton* B = CreateWidget<USOArmouryButton>(this, USOArmouryButton::StaticClass());
		B->Setup(this, ESOArmouryControl::Row, TEXT("group:") + Id.ToString(), G->Name.ToUpper(), Id == CreatorGroup);
		B->Count = Moved > 0 ? FString::FromInt(Moved) : FString();
		B->Width = CatWidth;
		CategoryPanel->AddChildToVerticalBox(B)->SetPadding(FMargin(0, 0, 0, 2));
	}
	CategoryPanel->AddChildToVerticalBox(Make<USpacer>(T))->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
	CategoryPanel->AddChildToVerticalBox(Header(T, TEXT("THE WHOLE LOOK")))->SetPadding(FMargin(0, 0, 0, 8));
	{
		UHorizontalBox* Row = Make<UHorizontalBox>(T);
		auto Whole = [&](const FString& Key, const FString& Label, bool bFirst)
		{
			USOArmouryButton* B = CreateWidget<USOArmouryButton>(this, USOArmouryButton::StaticClass());
			const bool bArmed = CreatorArmed == Key;
			B->Setup(this, ESOArmouryControl::Tool, Key, bArmed ? FString(TEXT("CONFIRM")) : Label, bArmed);
			B->Width = (CatWidth - 6.0f) * 0.5f;
			Row->AddChildToHorizontalBox(B)->SetPadding(FMargin(bFirst ? 0.0f : 6.0f, 0, 0, 0));
		};
		Whole(TEXT("random"), TEXT("RANDOM FACE"), true);
		Whole(TEXT("resetall"), TEXT("RESET ALL"), false);
		CategoryPanel->AddChildToVerticalBox(Row);
	}

	// --- the group: its head, its line, its sliders or its tones (moving a slider only moves the sliders built)
	const FSOCreatorGroup* Group = Data.Find(CreatorGroup);
	const bool bTones = !Group || Group->Sliders.Num() == 0;
	const FString Built = CreatorGroup.ToString() + TEXT("|") + Inventory->GetBody().ToString();
	if (!bTones && Built == CreatorBuilt && CreatorSliders.Num() > 0)
	{
		for (USOCreatorSlider* S : CreatorSliders)
		{
			if (S && !S->IsDragging())
			{
				S->SetValue(FaceValue(S->GetKey()));
			}
		}
		ApplyCreatorFocus();
		return;
	}
	CreatorBuilt = Built;
	GridPanel->ClearChildren();
	CreatorSliders.Reset();
	{
		FPlate HeadPlate;
		HeadPlate.Cut = 7.0f;
		HeadPlate.Fill = FLinearColor(0.006f, 0.009f, 0.018f, 0.88f);
		HeadPlate.FillLow = FLinearColor(0.004f, 0.006f, 0.012f, 0.9f);
		HeadPlate.Edge = FLinearColor(1.0f, 1.0f, 1.0f, 0.11f);
		UBorder* Head = Box(T, PlateBrush(this, HeadPlate), FMargin(12, 5, 8, 5));
		UHorizontalBox* Row = Make<UHorizontalBox>(T);
		Row->AddChildToHorizontalBox(Glyph(T, this, 0, Soft, 14.0f))->SetVerticalAlignment(VAlign_Center);
		UHorizontalBoxSlot* Name = Row->AddChildToHorizontalBox(Fit(Text(T, Group ? Group->Name.ToUpper() : FString(), 9, Ink, FaceBold, 220)));
		Name->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
		Name->SetPadding(FMargin(10, 0, 10, 0));
		Name->SetVerticalAlignment(VAlign_Center);
		USOArmouryButton* Reset = CreateWidget<USOArmouryButton>(this, USOArmouryButton::StaticClass());
		Reset->Setup(this, ESOArmouryControl::Tool, TEXT("reset"), TEXT("RESET"), false);
		Row->AddChildToHorizontalBox(Reset)->SetVerticalAlignment(VAlign_Center);
		Head->SetContent(Row);
		GridPanel->AddChildToVerticalBox(Sized(T, Head, 0.0f, 38.0f))->SetPadding(FMargin(0, 0, 0, 8));
		if (Group && !Group->Line.IsEmpty())
		{
			GridPanel->AddChildToVerticalBox(Fit(Text(T, Group->Line.ToUpper(), 8, Soft, FaceBold, 200)))->SetPadding(FMargin(2, 0, 0, 16));
		}
	}
	auto ChosenOf = [&](bool bHair)
	{
		const TArray<FSOCreatorTone>& Tones = bHair ? Data.HairColours : Data.SkinTones;
		const int32 i = ToneIndex(Tones, bHair ? Look.HairTone : Look.SkinTone);
		return Tones.IsValidIndex(i) ? Tones[i].Name.ToUpper() : FString();
	};
	auto Swatches = [&](bool bHair)
	{
		const TArray<FSOCreatorTone>& Tones = bHair ? Data.HairColours : Data.SkinTones;
		const int32 Chosen = ToneIndex(Tones, bHair ? Look.HairTone : Look.SkinTone);
		const int32 PerRow = 4;
		const float W = (GridWidth - (PerRow - 1) * CellGap) / PerRow;
		for (int32 Start = 0; Start < Tones.Num(); Start += PerRow)
		{
			UHorizontalBox* Row = Make<UHorizontalBox>(T);
			for (int32 i = Start; i < FMath::Min(Tones.Num(), Start + PerRow); ++i)
			{
				USOArmouryButton* B = CreateWidget<USOArmouryButton>(this, USOArmouryButton::StaticClass());
				B->Setup(this, ESOArmouryControl::Swatch, FString::Printf(TEXT("%s:%d"), bHair ? TEXT("hair") : TEXT("skin"), i), Tones[i].Name.ToUpper(), i == Chosen);
				B->SwatchColor = bHair ? HairSwatch(Tones[i].Tint) : SkinSwatch(Tones[i].Tint);
				B->Width = W;
				Row->AddChildToHorizontalBox(B)->SetPadding(FMargin(i > Start ? CellGap : 0.0f, 0, 0, 0));
			}
			GridPanel->AddChildToVerticalBox(Row)->SetPadding(FMargin(0, 0, 0, CellGap));
		}
	};
	if (CreatorGroup == TEXT("body"))
	{
		// the body (the two are built apart), then the skin's tone
		const bool bFemale = Inventory->GetBody() == TEXT("female");
		GridPanel->AddChildToVerticalBox(Header(T, TEXT("BODY"), bFemale ? TEXT("FEMALE") : TEXT("MALE"), CreatorRow == 0 ? Cyan : Dim))->SetPadding(FMargin(0, 0, 0, 10));
		UHorizontalBox* Pair = Make<UHorizontalBox>(T);
		for (int32 i = 0; i < 2; ++i)
		{
			USOArmouryButton* B = CreateWidget<USOArmouryButton>(this, USOArmouryButton::StaticClass());
			B->Setup(this, ESOArmouryControl::Choice, i == 0 ? TEXT("body:male") : TEXT("body:female"), i == 0 ? TEXT("MALE") : TEXT("FEMALE"), (i == 1) == bFemale);
			B->Width = (GridWidth - CellGap) * 0.5f;
			Pair->AddChildToHorizontalBox(B)->SetPadding(FMargin(i > 0 ? CellGap : 0.0f, 0, 0, 0));
		}
		GridPanel->AddChildToVerticalBox(Pair)->SetPadding(FMargin(0, 0, 0, 22));
		GridPanel->AddChildToVerticalBox(Header(T, TEXT("SKIN TONE"), ChosenOf(false), CreatorRow == 1 ? Cyan : Dim))->SetPadding(FMargin(0, 0, 0, 10));
		Swatches(false);
	}
	else if (CreatorGroup == TEXT("hair"))
	{
		GridPanel->AddChildToVerticalBox(Header(T, TEXT("HAIR COLOUR"), ChosenOf(true), Cyan))->SetPadding(FMargin(0, 0, 0, 10));
		Swatches(true);
		GridPanel->AddChildToVerticalBox(Fit(Text(T, TEXT("THE BROWS FOLLOW THE HAIR"), 8, Dim, FaceBold, 200)))->SetPadding(FMargin(2, 6, 0, 0));
	}
	else if (Group)
	{
		for (const TPair<FName, FString>& S : Group->Sliders)
		{
			if (!HasMorph(S.Key))
			{
				continue;
			}
			USOCreatorSlider* Slider = CreateWidget<USOCreatorSlider>(this, USOCreatorSlider::StaticClass());
			Slider->Setup(this, S.Key, S.Value, FaceValue(S.Key), GridWidth);
			CreatorSliders.Add(Slider);
			GridPanel->AddChildToVerticalBox(Slider)->SetPadding(FMargin(0, 0, 0, 8));
		}
		CreatorRow = FMath::Clamp(CreatorRow, 0, FMath::Max(0, CreatorSliders.Num() - 1));
	}
	ApplyCreatorFocus();
}

void USOInventoryWidget::ApplyCreatorFocus()
{
	for (int32 i = 0; i < CreatorSliders.Num(); ++i)
	{
		if (CreatorSliders[i])
		{
			CreatorSliders[i]->SetFocused(i == CreatorRow);
		}
	}
}

void USOInventoryWidget::OnSliderHover(FName Key)
{
	const int32 i = CreatorSliders.IndexOfByPredicate([Key](const USOCreatorSlider* S) { return S && S->GetKey() == Key; });
	if (i != INDEX_NONE && i != CreatorRow)
	{
		CreatorRow = i;
		ApplyCreatorFocus();
	}
}

void USOInventoryWidget::OnSlider(FName Key, float Value, bool bCommit)
{
	if (!Inventory || Key.IsNone())
	{
		return;
	}
	FPendingValue& P = PendingFace.FindOrAdd(Key);
	P.Value = FMath::Clamp(Value, -1.0f, 1.0f);
	P.At = bCommit ? FPlatformTime::Seconds() : FPlatformTime::Seconds() + 1.0e6;   // (being dragged: it waits)
	if (Preview)
	{
		Preview->ShowLook(CurrentLook());
	}
	if (bCommit)
	{
		USOSoundLibrary::Play2D(this, TEXT("ui_move"), 0.25f, 0.0f);
		Inventory->ServerSetFace(Key, P.Value);
	}
}

void USOInventoryWidget::SetCreatorGroup(FName Group)
{
	if (GetView() == EView::Character && Group == CreatorGroup)
	{
		return;
	}
	CreatorGroup = Group;
	CreatorRow = 0;
	CreatorBuilt.Reset();
	if (Preview)
	{
		Preview->TurnTo(GroupYaw(Group));
	}
	if (GetView() != EView::Character)
	{
		OpenSlot(TEXT("character"));
		return;
	}
	USOSoundLibrary::Play2D(this, TEXT("ui_move"), 0.4f, 0.0f);
	Refresh();
}

void USOInventoryWidget::CreatorStep(int32 DX, int32 DY)
{
	if (!Inventory)
	{
		return;
	}
	const FSOCreatorData& Data = FSOCreatorData::Get();
	if (CreatorGroup == TEXT("body") || CreatorGroup == TEXT("hair"))
	{
		// rows: the body and the skin (the hair: its colour); left and right choose in the row
		const int32 Rows = CreatorGroup == TEXT("body") ? 2 : 1;
		if (DY != 0)
		{
			const int32 Row = FMath::Clamp(CreatorRow + DY, 0, Rows - 1);
			if (Row != CreatorRow)
			{
				CreatorRow = Row;
				CreatorBuilt.Reset();
				USOSoundLibrary::Play2D(this, TEXT("ui_move"), 0.3f, 0.0f);
				Refresh();
			}
		}
		if (DX != 0)
		{
			if (CreatorGroup == TEXT("body") && CreatorRow == 0)
			{
				OnControl(ESOArmouryControl::Choice, Inventory->GetBody() == TEXT("female") ? TEXT("body:male") : TEXT("body:female"));
			}
			else
			{
				const bool bHair = CreatorGroup == TEXT("hair");
				const TArray<FSOCreatorTone>& Tones = bHair ? Data.HairColours : Data.SkinTones;
				const FSOOutfit Look = CurrentLook();
				const int32 Now = FMath::Max(0, ToneIndex(Tones, bHair ? Look.HairTone : Look.SkinTone));
				if (Tones.Num() > 0)
				{
					ChooseTone(bHair, (Now + DX % Tones.Num() + Tones.Num()) % Tones.Num());
				}
			}
		}
		return;
	}
	if (CreatorSliders.Num() == 0)
	{
		return;
	}
	if (DY != 0)
	{
		const int32 Row = FMath::Clamp(CreatorRow + DY, 0, CreatorSliders.Num() - 1);
		if (Row != CreatorRow)
		{
			CreatorRow = Row;
			ApplyCreatorFocus();
			USOSoundLibrary::Play2D(this, TEXT("ui_move"), 0.3f, 0.0f);
		}
	}
	if (DX != 0 && CreatorSliders.IsValidIndex(CreatorRow) && CreatorSliders[CreatorRow])
	{
		USOCreatorSlider* S = CreatorSliders[CreatorRow];
		const float V = FMath::Clamp(FMath::RoundToFloat((S->GetValue() + DX * 0.05f) * 20.0f) / 20.0f, -1.0f, 1.0f);
		S->SetValue(V);
		OnSlider(S->GetKey(), V, true);
	}
}

void USOInventoryWidget::ChooseTone(bool bHair, int32 Index)
{
	const TArray<FSOCreatorTone>& Tones = bHair ? FSOCreatorData::Get().HairColours : FSOCreatorData::Get().SkinTones;
	if (!Inventory || !Tones.IsValidIndex(Index))
	{
		return;
	}
	// the first is the body's own: nothing laid over it
	const FLinearColor Tone = Index == 0 ? FLinearColor(0.0f, 0.0f, 0.0f, 0.0f) : FLinearColor(Tones[Index].Tint.R, Tones[Index].Tint.G, Tones[Index].Tint.B, 1.0f);
	if (bHair)
	{
		PendingHair = Tone;
		PendingHairAt = FPlatformTime::Seconds();
		Inventory->ServerSetHairTone(Tone);
	}
	else
	{
		PendingSkin = Tone;
		PendingSkinAt = FPlatformTime::Seconds();
		Inventory->ServerSetSkinTone(Tone);
	}
	USOSoundLibrary::Play2D(this, TEXT("ui_equip"), 0.45f, 0.0f);
	CreatorBuilt.Reset();
	Refresh();
}

void USOInventoryWidget::ResetLook(bool bAll)
{
	if (!Inventory)
	{
		return;
	}
	if (bAll)
	{
		PendingFace.Reset();
		PendingSkinAt = PendingHairAt = -100.0;
		Inventory->ServerSetLook(TArray<FName>(), TArray<float>(), FLinearColor(0.0f, 0.0f, 0.0f, 0.0f), FLinearColor(0.0f, 0.0f, 0.0f, 0.0f));
	}
	else if (CreatorGroup == TEXT("body") || CreatorGroup == TEXT("hair"))
	{
		ChooseTone(CreatorGroup == TEXT("hair"), 0);
		return;
	}
	else if (const FSOCreatorGroup* Group = FSOCreatorData::Get().Find(CreatorGroup))
	{
		// the group's sliders back to the middle, the rest as they are
		const FSOOutfit Look = CurrentLook();
		TArray<FName> Keys;
		TArray<float> Values;
		for (int32 i = 0; i < FMath::Min(Look.FaceKeys.Num(), Look.FaceValues.Num()); ++i)
		{
			if (!Group->Sliders.ContainsByPredicate([&](const TPair<FName, FString>& S) { return S.Key == Look.FaceKeys[i]; }))
			{
				Keys.Add(Look.FaceKeys[i]);
				Values.Add(Look.FaceValues[i]);
			}
		}
		for (const TPair<FName, FString>& S : Group->Sliders)
		{
			PendingFace.Remove(S.Key);
		}
		Inventory->ServerSetLook(Keys, Values, Inventory->GetSkinTone(), Inventory->GetHairTone());
	}
	USOSoundLibrary::Play2D(this, TEXT("ui_close"), 0.4f, 0.0f);
	CreatorBuilt.Reset();
	Refresh();
}

void USOInventoryWidget::RandomFace()
{
	if (!Inventory)
	{
		return;
	}
	// every slider this body has, mostly near the middle and now and then far out (the difference of two even draws)
	TArray<FName> Keys;
	TArray<float> Values;
	for (const FName Key : FSOCreatorData::Get().AllKeys())
	{
		const float V = FMath::RoundToFloat((FMath::FRand() - FMath::FRand()) * 0.85f * 100.0f) / 100.0f;
		if (HasMorph(Key) && FMath::Abs(V) > 0.03f)
		{
			Keys.Add(Key);
			Values.Add(V);
		}
	}
	PendingFace.Reset();
	Inventory->ServerSetLook(Keys, Values, Inventory->GetSkinTone(), Inventory->GetHairTone());
	USOSoundLibrary::Play2D(this, TEXT("ui_equip"), 0.5f, 0.0f);
	CreatorBuilt.Reset();
	Refresh();
}
