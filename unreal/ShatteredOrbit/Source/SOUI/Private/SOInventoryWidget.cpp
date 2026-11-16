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
#include "Components/OverlaySlot.h"
#include "Components/PointLightComponent.h"
#include "Components/SceneCaptureComponent2D.h"
#include "Components/ScrollBox.h"
#include "Components/SizeBox.h"
#include "Components/Spacer.h"
#include "Components/TextBlock.h"
#include "Components/VerticalBox.h"
#include "Components/VerticalBoxSlot.h"
#include "Engine/PointLight.h"
#include "Engine/SceneCapture2D.h"
#include "Engine/Texture2D.h"
#include "Engine/TextureRenderTarget2D.h"
#include "Engine/World.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "HAL/IConsoleManager.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "SOAttributes.h"
#include "SOCharacter.h"
#include "SOInventoryComponent.h"
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
	constexpr float PanelBottom = 116.0f;
	constexpr float PanelWidth = 444.0f;
	constexpr float StageTop = 46.0f;
	constexpr float StageHeight = 1010.0f;
	constexpr float StageWidth = StageHeight * 0.75f;
	constexpr float FootY = StageTop + StageHeight * USOCharacterPreview::FeetInPicture;
	constexpr float FooterY = 1004.0f;
	constexpr float HintY = 1052.0f;

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

	/** The words of a set's or a slot's id ("void_sentinel" -> "VOID SENTINEL"). */
	FString IdWords(FName Id)
	{
		return Id.ToString().Replace(TEXT("_"), TEXT(" ")).ToUpper();
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
	C->ShowOnlyActors.Add(Pawn);
	TArray<AActor*> Attached;
	Pawn->GetAttachedActors(Attached, true, true);
	C->ShowOnlyActors.Append(Attached);
}

void USOCharacterPreview::Sync(USOInventoryComponent* Inventory, const FString& ShowWeapon, const FString& ShowArmor)
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
	// The framing (FeetInPicture follows from it): the capsule's middle is 90 cm over the feet; the eye 470 cm off and
	// 20 cm over a point 8 cm above it, a 24 degree lens on a 3:4 picture (31.6 degrees tall): the feet 0.88 down it.
	const FVector Center = Pawn->GetActorLocation() + FVector(0.0f, 0.0f, 8.0f);
	const FRotator Facing(0.0f, Pawn->GetActorRotation().Yaw + Yaw, 0.0f);
	const FVector Dir = Facing.Vector();                        // from the character towards the camera
	const FVector Eye = Center + Dir * 470.0f + FVector(0.0f, 0.0f, 20.0f);
	Cam->SetActorLocationAndRotation(Eye, (Center + FVector(0.0f, 0.0f, 4.0f) - Eye).Rotation());
	const FVector Right = FRotationMatrix(Facing).GetUnitAxis(EAxis::Y);
	const FVector Places[] = {
		Center + Dir * 230.0f + Right * 170.0f + FVector(0.0f, 0.0f, 130.0f),      // key: in front, to the right, high
		Center - Dir * 190.0f - Right * 150.0f + FVector(0.0f, 0.0f, 110.0f),      // rim: behind, to the left
		Center - Dir * 170.0f + Right * 160.0f + FVector(0.0f, 0.0f, 70.0f),       // rim: behind, to the right
		Center + Dir * 260.0f - Right * 200.0f + FVector(0.0f, 0.0f, 10.0f),       // fill: in front, to the left, low
		Center + Dir * 140.0f + FVector(0.0f, 0.0f, -80.0f) };                     // the platform's light from below
	for (int32 i = 0; i < Lights.Num() && i < static_cast<int32>(UE_ARRAY_COUNT(Places)); ++i)
	{
		if (APointLight* L = Lights[i].Get())
		{
			L->SetActorLocation(Places[i]);
		}
	}
}

// --- Card --------------------------------------------------------------------------------------------

TSharedRef<SWidget> USOInventoryTile::RebuildWidget()
{
	if (WidgetTree && !WidgetTree->RootWidget)
	{
		UWidgetTree* T = WidgetTree;
		const bool bWeapon = Info.Kind == TEXT("wslot") || Info.Kind == TEXT("weapon") || Info.Kind == TEXT("mslot") || Info.Kind == TEXT("blade");
		const bool bSlot = Info.Kind == TEXT("wslot") || Info.Kind == TEXT("aslot") || Info.Kind == TEXT("mslot");
		const FLinearColor Rarity = Alpha(Info.Rarity, 1.0f);
		const float Height = bWeapon ? (bSlot ? 168.0f : 128.0f) : (bSlot ? 100.0f : 92.0f);
		Button = Make<UButton>(T);
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
		UTextBlock* Name = Text(T, Info.Title, bWeapon ? (bSlot ? 21 : 19) : (bSlot ? 19 : 18), Info.bEmpty ? Dim : Ink, FaceCond, 30);
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
			const FVector2D Size = bWeapon ? (bSlot ? FVector2D(252.0f, 126.0f) : FVector2D(206.0f, 103.0f)) : (bSlot ? FVector2D(84.0f, 84.0f) : FVector2D(78.0f, 78.0f));
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
				S->SetPadding(FMargin(0, bSlot ? 14.0f : 8.0f, Info.Icon ? 8.0f : 86.0f, 0));
			}
			UOverlaySlot* W = Body->AddChildToOverlay(Sized(T, Words, bSlot ? 168.0f : 186.0f, 0.0f));
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

void USOInventoryTile::Restyle()
{
	if (!Button)
	{
		return;
	}
	const bool bWeapon = Info.Kind == TEXT("wslot") || Info.Kind == TEXT("weapon") || Info.Kind == TEXT("mslot") || Info.Kind == TEXT("blade");
	const float GlowX = bWeapon ? 0.68f : 0.88f;
	const float Glow = bWeapon ? (Info.Icon ? 0.95f : 0.45f) : 0.65f;
	const float Chosen = Info.bActive ? 1.0f : 0.0f;
	StyleButton(Button, CardBrush(this, Info.Rarity, 0.0f, Chosen, Info.bEmpty, GlowX, Glow), CardBrush(this, Info.Rarity, 1.0f, Chosen, Info.bEmpty, GlowX, Glow),
		CardBrush(this, Info.Rarity, 1.6f, Chosen, Info.bEmpty, GlowX, Glow));
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
	if (!FMath::IsNearlyEqual(Lift, LiftTarget, 0.05f))
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
	LiftTarget = 7.0f;                                          // (leans toward the stage)
	if (Screen)
	{
		Screen->OnTileHover(this, true);
	}
}

void USOInventoryTile::OnUnhovered()
{
	LiftTarget = 0.0f;
	if (Screen)
	{
		Screen->OnTileHover(this, false);
	}
}

// --- Tab ---------------------------------------------------------------------------------------------

TSharedRef<SWidget> USOArmouryTab::RebuildWidget()
{
	if (WidgetTree && !WidgetTree->RootWidget)
	{
		UWidgetTree* T = WidgetTree;
		UButton* Button = Make<UButton>(T);
		if (bChip)
		{
			// an armour slot's chip over its list: a small plate, lit when it is the one open
			FPlate Normal;
			Normal.Cut = 6.0f;
			Normal.Fill = bActive ? FLinearColor(0.010f, 0.032f, 0.052f, 0.95f) : FLinearColor(0.005f, 0.008f, 0.016f, 0.9f);
			Normal.FillLow = Normal.Fill;
			Normal.Edge = bActive ? Alpha(Cyan, 0.9f) : FLinearColor(1.0f, 1.0f, 1.0f, 0.12f);
			FPlate Over = Normal;
			Over.Edge = Alpha(Cyan, 1.0f);
			Over.TopLight = 1.0f;
			StyleButton(Button, PlateBrush(this, Normal), PlateBrush(this, Over), PlateBrush(this, Over));
		}
		else
		{
			const FSlateColorBrush Clear(FLinearColor::Transparent);
			const FSlateRoundedBoxBrush Over(FLinearColor(1.0f, 1.0f, 1.0f, 0.045f), 3.0f);
			const FSlateRoundedBoxBrush Down(FLinearColor(1.0f, 1.0f, 1.0f, 0.09f), 3.0f);
			StyleButton(Button, Clear, Over, Down);
		}
		Button->OnClicked.AddDynamic(this, &USOArmouryTab::OnClicked);
		UVerticalBox* Column = Make<UVerticalBox>(T);
		UHorizontalBox* Row = Make<UHorizontalBox>(T);
		Row->AddChildToHorizontalBox(Text(T, Label, bChip ? 9 : 12, bActive ? Ink : Dim, FaceBold, bChip ? 160 : 320))->SetVerticalAlignment(VAlign_Center);
		if (bNew)
		{
			Row->AddChildToHorizontalBox(Glyph(T, this, 4, Gold, 9))->SetPadding(FMargin(5, 0, 0, 0));
		}
		Column->AddChildToVerticalBox(Row)->SetHorizontalAlignment(HAlign_Center);
		if (!bChip)
		{
			// the one open is underlined with light
			UVerticalBoxSlot* Under = Column->AddChildToVerticalBox(Sized(T, Box(T, FSlateColorBrush(bActive ? Cyan : FLinearColor::Transparent), FMargin(0)), 0.0f, 2.0f));
			Under->SetPadding(FMargin(0, 6, 0, 0));
		}
		UBorder* Pad = Box(T, FSlateColorBrush(FLinearColor::Transparent), bChip ? FMargin(6, 6, 6, 6) : FMargin(16, 6, 16, 2));
		Pad->SetContent(Column);
		Button->SetContent(Pad);
		WidgetTree->RootWidget = Button;
	}
	return Super::RebuildWidget();
}

void USOArmouryTab::OnClicked()
{
	if (Screen)
	{
		Screen->OnTab(Key);
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
		SyncPreview();
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
	Animate();
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
	// the panels slide in from their sides and fade up after a change of view
	if (Arrive < 1.0f)
	{
		Arrive = FMath::Min(1.0f, Arrive + FMath::Min(InDeltaTime, 0.05f) / 0.3f);
		const float E = 1.0f - FMath::Pow(1.0f - Arrive, 3.0f);
		if (LeftPanel)
		{
			LeftPanel->SetRenderTranslation(FVector2D(-36.0f * (1.0f - E), 0.0f));
			LeftPanel->SetRenderOpacity(E);
		}
		if (RightPanel)
		{
			RightPanel->SetRenderTranslation(FVector2D(36.0f * (1.0f - E), 0.0f));
			RightPanel->SetRenderOpacity(E);
		}
		if (AttributeColumn)
		{
			AttributeColumn->SetRenderOpacity(E);
		}
	}
}

void USOInventoryWidget::Animate()
{
	Arrive = 0.0f;
	if (LeftPanel)
	{
		LeftPanel->SetRenderOpacity(0.0f);
	}
	if (RightPanel)
	{
		RightPanel->SetRenderOpacity(0.0f);
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
	Back->SetVisibility(ESlateVisibility::HitTestInvisible);
	Place(Back, FAnchors(0.0f, 0.0f, 1.0f, 1.0f), FMargin(0.0f));

	// the platform under the feet: rings of light in perspective, a pool of light, the feet's shadow
	UImage* Floor = Make<UImage>(T);
	if (UMaterialInstanceDynamic* MID = Instance(this, TEXT("M_UI_Floor")))
	{
		Floor->SetBrush(MaterialBrush(MID));
		Floor->SetVisibility(ESlateVisibility::HitTestInvisible);
	}
	else
	{
		Floor->SetVisibility(ESlateVisibility::Collapsed);
	}
	Place(Floor, FAnchors(0.5f, 0.0f), FMargin(0.0f, FootY, 640.0f, 176.0f), FVector2D(0.5f, 0.5f));

	// the character
	PreviewImage = Make<UImage>(T);
	PreviewImage->SetVisibility(ESlateVisibility::HitTestInvisible);
	Place(PreviewImage, FAnchors(0.5f, 0.0f), FMargin(0.0f, StageTop, StageWidth, StageHeight), FVector2D(0.5f, 0.0f));

	// the banner: who, how far along, the body; what is owned; the power
	UHorizontalBox* Banner = Make<UHorizontalBox>(T);
	Banner->AddChildToHorizontalBox(Glyph(T, this, 0, Cyan, 46.0f))->SetVerticalAlignment(VAlign_Center);
	UVerticalBox* Who = Make<UVerticalBox>(T);
	NameText = Text(T, TEXT("WAYFARER"), 24, Ink, FaceCond, 260);
	Who->AddChildToVerticalBox(NameText);
	UHorizontalBox* LevelRow = Make<UHorizontalBox>(T);
	LevelText = Text(T, TEXT("LEVEL 1"), 10, Cyan, FaceBold, 220);
	LevelRow->AddChildToHorizontalBox(LevelText)->SetVerticalAlignment(VAlign_Center);
	XpBar = StatBar(T, this, 0.0f, 0.0f, 24, Cyan);
	UHorizontalBoxSlot* BarSlot = LevelRow->AddChildToHorizontalBox(Sized(T, XpBar, 170.0f, 5.0f));
	BarSlot->SetVerticalAlignment(VAlign_Center);
	BarSlot->SetPadding(FMargin(12, 0, 10, 0));
	XpText = Text(T, TEXT(""), 9, Dim, FaceBold, 120);
	LevelRow->AddChildToHorizontalBox(XpText)->SetVerticalAlignment(VAlign_Center);
	Who->AddChildToVerticalBox(LevelRow)->SetPadding(FMargin(0, 2, 0, 0));
	UHorizontalBoxSlot* WhoSlot = Banner->AddChildToHorizontalBox(Who);
	WhoSlot->SetPadding(FMargin(14, 0, 0, 0));
	WhoSlot->SetVerticalAlignment(VAlign_Center);
	{
		UButton* BodyButton = Make<UButton>(T);
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
		MaleLabel = Text(T, TEXT("MALE"), 9, Ink, FaceBold, 220);
		FemaleLabel = Text(T, TEXT("FEMALE"), 9, Dim, FaceBold, 220);
		Pair->AddChildToHorizontalBox(MaleLabel);
		Pair->AddChildToHorizontalBox(Text(T, TEXT("/"), 9, Dim, FaceBold))->SetPadding(FMargin(8, 0, 8, 0));
		Pair->AddChildToHorizontalBox(FemaleLabel);
		BodyButton->SetContent(Box(T, FSlateColorBrush(FLinearColor::Transparent), FMargin(14, 6, 14, 6)));
		Cast<UBorder>(BodyButton->GetContent())->SetContent(Pair);
		BodyButton->OnClicked.AddDynamic(this, &USOInventoryWidget::OnBody);
		BodyButton->SetToolTipText(FText::FromString(TEXT("The body you play")));
		UHorizontalBoxSlot* BodySlot = Banner->AddChildToHorizontalBox(BodyButton);
		BodySlot->SetPadding(FMargin(34, 0, 0, 0));
		BodySlot->SetVerticalAlignment(VAlign_Center);
	}
	Banner->AddChildToHorizontalBox(Make<USpacer>(T))->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
	Currencies = Make<UHorizontalBox>(T);
	Banner->AddChildToHorizontalBox(Currencies)->SetVerticalAlignment(VAlign_Center);
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
		Banner->AddChildToHorizontalBox(PowerBox)->SetVerticalAlignment(VAlign_Center);
	}
	Place(Banner, FAnchors(0.0f, 0.0f, 1.0f, 0.0f), FMargin(Margin, 20.0f, Margin, 66.0f));
	Place(Box(T, FSlateColorBrush(Faint), FMargin(0)), FAnchors(0.0f, 0.0f, 1.0f, 0.0f), FMargin(Margin, 100.0f, Margin, 1.0f));
	Place(Box(T, FSlateColorBrush(Cyan), FMargin(0)), FAnchors(0.0f, 0.0f), FMargin(Margin, 99.0f, 120.0f, 2.0f));

	// the panels, the attributes beside the stage, a card's quick look
	LeftPanel = Make<UVerticalBox>(T);
	Place(LeftPanel, FAnchors(0.0f, 0.0f, 0.0f, 1.0f), FMargin(Margin, PanelTop, PanelWidth, PanelBottom));
	RightPanel = Make<UVerticalBox>(T);
	Place(RightPanel, FAnchors(1.0f, 0.0f, 1.0f, 1.0f), FMargin(-(Margin + PanelWidth), PanelTop, PanelWidth, PanelBottom));
	AttributeColumn = Make<UVerticalBox>(T);
	Place(AttributeColumn, FAnchors(1.0f, 0.0f), FMargin(-(Margin + PanelWidth + 104.0f), 236.0f, 84.0f, 0.0f), FVector2D::ZeroVector, true);
	FPlate LookPlate;
	LookPlate.Cut = 14.0f;
	LookPlate.Fill = FLinearColor(0.005f, 0.008f, 0.016f, 0.97f);
	LookPlate.FillLow = FLinearColor(0.003f, 0.0045f, 0.009f, 0.97f);
	LookPlate.Edge = Alpha(Cyan, 0.35f);
	LookPlate.TopLight = 1.0f;
	QuickLook = Box(T, PlateBrush(this, LookPlate), FMargin(22, 16, 22, 16));
	QuickLook->SetVisibility(ESlateVisibility::Collapsed);
	Place(QuickLook, FAnchors(0.0f, 0.0f), FMargin(0.0f), FVector2D::ZeroVector, true);

	// the foot: a hairline, the tabs in the middle, what the keys do
	Place(Box(T, FSlateColorBrush(Faint), FMargin(0)), FAnchors(0.0f, 1.0f, 1.0f, 1.0f), FMargin(Margin, -(1080.0f - 978.0f), Margin, 1.0f));
	TabRow = Make<UHorizontalBox>(T);
	Place(TabRow, FAnchors(0.5f, 1.0f), FMargin(0.0f, -(1080.0f - FooterY), 0.0f, 0.0f), FVector2D(0.5f, 0.5f), true);
	HintRow = Make<UHorizontalBox>(T);
	Place(HintRow, FAnchors(1.0f, 1.0f), FMargin(-Margin + 22.0f, -(1080.0f - HintY), 0.0f, 0.0f), FVector2D(1.0f, 0.5f), true);
	Place(Hint(T, TEXT("DRAG"), TEXT("TURN")), FAnchors(0.0f, 1.0f), FMargin(Margin, -(1080.0f - HintY), 0.0f, 0.0f), FVector2D(0.0f, 0.5f), true);

	// the inspect panel (an armoury puts it in the right panel): its content scrolls, its buttons stay under it
	FPlate InspectPlate;
	InspectPlate.Cut = 20.0f;
	InspectPlate.Fill = FLinearColor(0.0055f, 0.0085f, 0.017f, 0.88f);
	InspectPlate.FillLow = FLinearColor(0.003f, 0.0045f, 0.0095f, 0.92f);
	InspectPlate.Edge = FLinearColor(1.0f, 1.0f, 1.0f, 0.12f);
	InspectPlate.Hatch = 1.0f;
	InspectPlate.TopLight = 0.6f;
	UBorder* Frame = Box(T, PlateBrush(this, InspectPlate), FMargin(28, 22, 20, 20));
	UVerticalBox* FrameColumn = Make<UVerticalBox>(T);
	InspectScroll = Scroll(T);
	Inspect = Make<UVerticalBox>(T);
	InspectScroll->AddChild(Inspect);
	FrameColumn->AddChildToVerticalBox(InspectScroll)->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
	UVerticalBox* Actions = Make<UVerticalBox>(T);
	auto Action = [&](TObjectPtr<UButton>& Out, TObjectPtr<UTextBlock>& Label, const TCHAR* Key, const TCHAR* Caption, const FLinearColor& Color) -> UButton*
	{
		Out = Make<UButton>(T);
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
		Row->AddChildToHorizontalBox(KeyCap(T, Key))->SetVerticalAlignment(VAlign_Center);
		Label = Text(T, Caption, 9, Ink, FaceBold, 110);
		UHorizontalBoxSlot* L = Row->AddChildToHorizontalBox(Label);
		L->SetPadding(FMargin(8, 0, 0, 0));
		L->SetVerticalAlignment(VAlign_Center);
		UBorder* Pad = Box(T, FSlateColorBrush(FLinearColor::Transparent), FMargin(8, 10, 8, 10));
		Pad->SetHorizontalAlignment(HAlign_Center);
		Pad->SetContent(Row);
		Out->SetContent(Pad);
		return Out;
	};
	UHorizontalBox* Main = Make<UHorizontalBox>(T);
	Main->AddChildToHorizontalBox(Action(EquipButton, EquipLabel, TEXT("E"), TEXT("EQUIP"), Cyan))->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
	UHorizontalBoxSlot* LockSlot = Main->AddChildToHorizontalBox(Action(LockButton, LockLabel, TEXT("L"), TEXT("LOCK"), Gold));
	LockSlot->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
	LockSlot->SetPadding(FMargin(8, 0, 8, 0));
	Main->AddChildToHorizontalBox(Action(DismantleButton, DismantleLabel, TEXT("X"), TEXT("DISMANTLE"), Bad))->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
	Actions->AddChildToVerticalBox(Main);
	Actions->AddChildToVerticalBox(Action(UpgradeButton, UpgradeLabel, TEXT("U"), TEXT("RAISE"), Good))->SetPadding(FMargin(0, 8, 0, 0));
	EquipButton->OnClicked.AddDynamic(this, &USOInventoryWidget::OnEquip);
	LockButton->OnClicked.AddDynamic(this, &USOInventoryWidget::OnLock);
	DismantleButton->OnClicked.AddDynamic(this, &USOInventoryWidget::OnDismantle);
	UpgradeButton->OnClicked.AddDynamic(this, &USOInventoryWidget::OnUpgrade);
	ActionBlock = Actions;
	FrameColumn->AddChildToVerticalBox(Actions)->SetPadding(FMargin(0, 14, 8, 0));
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
	Tile.Tag = FString::Printf(TEXT("%s  ·  %s"), *KindName(Data).ToUpper(), *ClassName(Data).ToUpper());
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
	if (OpenSlotId.IsEmpty())
	{
		FillLoadout();
	}
	else
	{
		FillArmoury();
	}
	FillTabs();
	FillHints();
	SyncPreview();
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
	PowerText->SetText(FText::AsNumber(Inventory->GetPower()));
}

void USOInventoryWidget::FillLoadout()
{
	UWidgetTree* T = WidgetTree;
	ListTiles.Reset();
	ListScroll = nullptr;
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
}

void USOInventoryWidget::FillArmoury()
{
	UWidgetTree* T = WidgetTree;
	if (ListScroll)
	{
		ListOffset = ListScroll->GetScrollOffset();               // (kept across a refresh: equipping, locking)
	}
	ListTiles.Reset();
	QuickLook->SetVisibility(ESlateVisibility::Collapsed);
	QuickKey.Reset();
	LeftPanel->ClearChildren();
	TArray<FSOTileInfo> Tiles;
	FString Title;
	UWidget* Chips = nullptr;
	if (OpenSlotId == TEXT("melee"))
	{
		// the fists, and every blade owned
		const USOMeleeTable* Melee = USOMeleeTable::Get();
		TArray<FName> Styles = { FName(TEXT("fists")) };
		Styles.Append(Inventory->GetBlades());
		const FName In = Inventory->GetMeleeSlot().IsNone() ? FName(TEXT("fists")) : Inventory->GetMeleeSlot();
		for (const FName Id : Styles)
		{
			const FSOMeleeStyle* Style = Melee ? Melee->Find(Id) : nullptr;
			const bool bFists = Id == TEXT("fists");
			FSOTileInfo Info;
			Info.Kind = TEXT("blade");
			Info.Key = TEXT("melee:") + Id.ToString();
			Info.Title = Style && !Style->Name.IsEmpty() ? Style->Name.ToString() : Id.ToString();
			Info.Icon = Style ? Style->Icon.LoadSynchronous() : nullptr;
			Info.Tag = bFists ? TEXT("HAND TO HAND") : TEXT("BLADE  ·  HAND TO HAND");
			Info.Rarity = bFists ? Steel : BladeLight;
			Info.Glyph = bFists ? 11 : 13;
			Info.bEquipped = Id == In;
			Tiles.Add(Info);
		}
		if (SelectedKey.IsEmpty())
		{
			SelectedKey = TEXT("melee:") + In.ToString();
		}
		Title = TEXT("MELEE");
	}
	else if (IsWeaponSlot(OpenSlotId))
	{
		const int32 SlotId = FCString::Atoi(*OpenSlotId);
		const FSOWeaponInstance* Equipped = Inventory->GetEquipped(SlotId);
		TArray<const FSOWeaponInstance*> List;
		for (const FSOWeaponInstance& W : Inventory->GetItems())
		{
			const USOWeaponData* Data = ArchetypeOf(W);
			if (Data && FMath::Clamp(Data->Slot, 0, USOInventoryComponent::NumSlots - 1) == SlotId)
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
		for (const FSOWeaponInstance* W : List)
		{
			FSOTileInfo Info = WeaponTile(*W, false);
			Info.PowerDelta = Equipped && Equipped->Uid != W->Uid ? W->Power - Equipped->Power : 0;
			Tiles.Add(Info);
		}
		Title = SlotName(SlotId).ToUpper();
	}
	else
	{
		// the armour: its slots as chips over the list of what is owned for the one open
		const FName SlotId(*OpenSlotId);
		const USOWardrobeData* Wardrobe = USOWardrobeData::Get(Inventory->GetBody());
		for (const FSOArmorInstance& A : Inventory->GetArmor())
		{
			if (A.Slot == SlotId && (!Wardrobe || Wardrobe->Find(A.Slot, A.Item)))
			{
				Tiles.Add(ArmorTile(A, false));
			}
		}
		Tiles.Sort([](const FSOTileInfo& A, const FSOTileInfo& B)
		{
			if (A.bEquipped != B.bEquipped) return A.bEquipped;
			if (A.bNew != B.bNew) return A.bNew;
			return A.Power != B.Power ? A.Power > B.Power : A.Title < B.Title;
		});
		UHorizontalBox* Row = Make<UHorizontalBox>(T);
		for (const FName Each : USOWardrobeData::ArmourSlots())
		{
			bool bNew = false;
			for (const FSOArmorInstance& A : Inventory->GetArmor())
			{
				bNew |= A.Slot == Each && A.bNew;
			}
			USOArmouryTab* Chip = CreateWidget<USOArmouryTab>(this, USOArmouryTab::StaticClass());
			Chip->Setup(this, Each.ToString(), USOWardrobeData::SlotLabel(Each).ToString().ToUpper(), Each == SlotId, true, bNew);
			UHorizontalBoxSlot* S = Row->AddChildToHorizontalBox(Chip);
			S->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
			S->SetPadding(FMargin(0, 0, Each == USOWardrobeData::ArmourSlots().Last() ? 0 : 4, 0));
		}
		Chips = Row;
		Title = TEXT("ARMOUR");
	}
	LeftPanel->AddChildToVerticalBox(Header(T, Title, FString::Printf(TEXT("%d OWNED"), Tiles.Num())))->SetPadding(FMargin(0, 0, 0, 12));
	if (Chips)
	{
		LeftPanel->AddChildToVerticalBox(Chips)->SetPadding(FMargin(0, 0, 0, 12));
	}
	if (SelectedKey.IsEmpty() && Tiles.Num() > 0)
	{
		SelectedKey = Tiles[0].Key;                              // (nothing in the slot yet: the first thing owned for it)
	}
	ListScroll = Scroll(T);
	UVerticalBox* List = Make<UVerticalBox>(T);
	for (FSOTileInfo& Info : Tiles)
	{
		Info.bActive = Info.Key == SelectedKey;
		Info.bLeft = true;
		USOInventoryTile* Tile = CreateWidget<USOInventoryTile>(this, USOInventoryTile::StaticClass());
		Tile->Setup(this, Info);
		List->AddChildToVerticalBox(Tile)->SetPadding(FMargin(0, 0, 0, 10));
		ListTiles.Add(Tile);
	}
	if (Tiles.Num() == 0)
	{
		UTextBlock* None = Text(T, TEXT("Nothing owned for this slot yet. What the operations and the caches give you comes here."), 12, Dim, FaceItalic);
		None->SetAutoWrapText(true);
		List->AddChildToVerticalBox(None)->SetPadding(FMargin(4, 8, 4, 0));
	}
	ListScroll->AddChild(List);
	LeftPanel->AddChildToVerticalBox(ListScroll)->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
	ListScroll->SetScrollOffset(ListOffset);
	RightPanel->ClearChildren();
	RightPanel->AddChildToVerticalBox(InspectFrame)->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
	FillInspect();
}

void USOInventoryWidget::FillTabs()
{
	UWidgetTree* T = WidgetTree;
	TabRow->ClearChildren();
	bool bNewSlot[USOInventoryComponent::NumSlots] = {};
	for (const FSOWeaponInstance& W : Inventory->GetItems())
	{
		const USOWeaponData* Data = W.bNew ? ArchetypeOf(W) : nullptr;
		if (Data)
		{
			bNewSlot[FMath::Clamp(Data->Slot, 0, USOInventoryComponent::NumSlots - 1)] = true;
		}
	}
	bool bNewArmour = false;
	for (const FSOArmorInstance& A : Inventory->GetArmor())
	{
		bNewArmour |= A.bNew;
	}
	const FString Active = OpenSlotId.IsEmpty() ? FString() : IsArmourSlot(OpenSlotId) ? FString(TEXT("armour")) : OpenSlotId;
	TabRow->AddChildToHorizontalBox(KeyCap(T, TEXT("A")))->SetVerticalAlignment(VAlign_Center);
	auto Tab = [&](const FString& Key, const FString& Label, bool bNew)
	{
		USOArmouryTab* Widget = CreateWidget<USOArmouryTab>(this, USOArmouryTab::StaticClass());
		Widget->Setup(this, Key, Label, Key == Active, false, bNew);
		TabRow->AddChildToHorizontalBox(Widget)->SetPadding(FMargin(4, 0, 4, 0));
	};
	Tab(FString(), TEXT("LOADOUT"), false);
	for (int32 SlotId = 0; SlotId < USOInventoryComponent::NumSlots; ++SlotId)
	{
		Tab(FString::FromInt(SlotId), SlotName(SlotId).ToUpper(), bNewSlot[SlotId]);
	}
	Tab(TEXT("melee"), TEXT("MELEE"), false);
	Tab(TEXT("armour"), TEXT("ARMOUR"), bNewArmour);
	TabRow->AddChildToHorizontalBox(KeyCap(T, TEXT("D")))->SetVerticalAlignment(VAlign_Center);
}

void USOInventoryWidget::FillHints()
{
	UWidgetTree* T = WidgetTree;
	HintRow->ClearChildren();
	auto Add = [&](const TCHAR* Key, const TCHAR* Label) { HintRow->AddChildToHorizontalBox(Hint(T, Key, Label)); };
	if (OpenSlotId.IsEmpty())
	{
		Add(TEXT("CLICK"), TEXT("OPEN"));
		Add(TEXT("1-3"), TEXT("IN HAND"));
		Add(TEXT("ESC"), TEXT("CLOSE"));
		return;
	}
	if (IsWeaponSlot(OpenSlotId))
	{
		Add(TEXT("E"), TEXT("EQUIP"));
		Add(TEXT("L"), TEXT("LOCK"));
		Add(TEXT("X"), TEXT("DISMANTLE"));
		Add(TEXT("U"), TEXT("RAISE"));
	}
	else if (OpenSlotId == TEXT("melee"))
	{
		Add(TEXT("E"), TEXT("EQUIP"));
	}
	else
	{
		Add(TEXT("E"), TEXT("WEAR"));
		Add(TEXT("U"), TEXT("RAISE"));
	}
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
	else
	{
		UTextBlock* None = Text(WidgetTree, TEXT("Choose something on the left to see it here."), 13, Dim, FaceItalic);
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
	// what it is, its name, its line
	UTextBlock* Kind = Text(T, FString::Printf(TEXT("%s  ·  %s  ·  %s"), *RarityName(W.Rarity).ToUpper(), *ClassName(Data).ToUpper(), *KindName(Data).ToUpper()), 9, Rarity, FaceBold, 260);
	Kind->SetAutoWrapText(true);
	Inspect->AddChildToVerticalBox(Kind);
	UTextBlock* Name = Text(T, W.Name.ToUpper(), 34, Ink, FaceCond, 40);
	Name->SetAutoWrapText(true);
	Inspect->AddChildToVerticalBox(Name)->SetPadding(FMargin(0, 2, 0, 0));
	Inspect->AddChildToVerticalBox(Rule(T, Rarity))->SetPadding(FMargin(0, 6, 0, 12));
	if (Data && !Data->Lore.IsEmpty())
	{
		UTextBlock* Lore = Text(T, Data->Lore.ToString(), 12, Soft, FaceItalic);
		Lore->SetAutoWrapText(true);
		Inspect->AddChildToVerticalBox(Lore)->SetPadding(FMargin(0, 0, 0, 12));
	}

	// power, and this copy's particulars
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
		Particulars->AddChildToVerticalBox(Text(T, Sight->Name.ToString().ToUpper(), 9, Soft, FaceBold, 160))->SetHorizontalAlignment(HAlign_Right);
	}
	Particulars->AddChildToVerticalBox(Text(T, FString::Printf(TEXT("ROLLED %d %%"), USOLootLibrary::RollQuality(W)), 9, Soft, FaceBold, 160))->SetHorizontalAlignment(HAlign_Right);
	if (!W.Source.IsEmpty())
	{
		Particulars->AddChildToVerticalBox(Text(T, W.Source.ToUpper(), 8, Dim, FaceBold, 160))->SetHorizontalAlignment(HAlign_Right);
	}
	PowerRow->AddChildToHorizontalBox(Particulars)->SetVerticalAlignment(VAlign_Center);
	Inspect->AddChildToVerticalBox(PowerRow)->SetPadding(FMargin(0, 0, 0, 12));

	// performance against the one equipped in its slot
	const FSOWeaponStats S = USOLootLibrary::ComputeStats(W);
	const FSOWeaponInstance* Equipped = Data ? Inventory->GetEquipped(FMath::Clamp(Data->Slot, 0, USOInventoryComponent::NumSlots - 1)) : nullptr;
	const bool bCompare = Equipped && Equipped->Uid != W.Uid;
	const USOWeaponData* EquippedData = bCompare ? ArchetypeOf(*Equipped) : Data;
	const FSOWeaponStats E = bCompare ? USOLootLibrary::ComputeStats(*Equipped) : S;
	Inspect->AddChildToVerticalBox(Header(T, TEXT("PERFORMANCE"), bCompare ? FString::Printf(TEXT("AGAINST %s"), *Equipped->Name.ToUpper()) : FString()))->SetPadding(FMargin(0, 0, 0, 10));
	const int32 Pellets = Data ? FMath::Max(1, Data->Pellets) : 1;
	const int32 OtherPellets = EquippedData ? FMath::Max(1, EquippedData->Pellets) : Pellets;
	const bool bCondenses = Data && Data->RefillTime > 0.0f;
	const bool bOtherCondenses = EquippedData && EquippedData->RefillTime > 0.0f;
	// (Curve: a bar's fill is (value / max) ^ curve: damage and range span a wide range, the root keeps both ends readable)
	struct FRow { const TCHAR* Name; float Value, Other, Max; FString Shown; bool bLowerBetter; float Curve = 1.0f; };
	TArray<FRow> Rows;
	Rows.Add({ TEXT("IMPACT"), S.Damage * Pellets, E.Damage * OtherPellets, 450.0f,
		Pellets > 1 ? FString::Printf(TEXT("%.0f x %d"), S.Damage, Pellets) : FString::Printf(TEXT("%.0f"), S.Damage), false, 0.5f });
	Rows.Add({ TEXT("FIRE RATE"), S.Rpm, E.Rpm, 1100.0f, FString::Printf(TEXT("%.0f RPM"), S.Rpm), false });
	Rows.Add({ TEXT("RANGE"), S.Range, E.Range, 180.0f, FString::Printf(TEXT("%.0f M"), S.Range), false, 0.5f });
	Rows.Add({ TEXT("STABILITY"), S.Spread, E.Spread, 7.0f, FString::Printf(TEXT("%.2f°"), S.Spread), true });
	Rows.Add({ TEXT("VELOCITY"), Data ? Data->MuzzleVelocity : 0.0f, EquippedData ? EquippedData->MuzzleVelocity : 0.0f, 1000.0f,
		FString::Printf(TEXT("%.0f M/S"), Data ? Data->MuzzleVelocity : 0.0f), false });
	Rows.Add({ TEXT("MAGAZINE"), static_cast<float>(S.Mag), static_cast<float>(E.Mag), 150.0f, FString::FromInt(S.Mag), false });
	if (bCondenses)
	{
		// a gun that condenses its rounds: how long a full load takes to form once the crystal is cold
		Rows.Add({ TEXT("CONDENSE"), Data->RefillTime, bOtherCondenses ? EquippedData->RefillTime : Data->RefillTime, 5.0f, FString::Printf(TEXT("%.1f S"), Data->RefillTime), true });
	}
	else
	{
		Rows.Add({ TEXT("RELOAD"), S.Reload, bOtherCondenses ? S.Reload : E.Reload, 4.0f, FString::Printf(TEXT("%.2f S"), S.Reload), true });
	}
	Rows.Add({ TEXT("ZOOM"), S.Zoom, E.Zoom, 8.0f, FString::Printf(TEXT("%.1fx"), S.Zoom), false });
	for (const FRow& R : Rows)
	{
		auto Fill = [&](float V) { return R.bLowerBetter ? 1.0f - FMath::Clamp(V / R.Max, 0.0f, 0.95f) : FMath::Pow(FMath::Clamp(V / R.Max, 0.002f, 1.0f), R.Curve); };
		const bool bDiffers = bCompare && !FMath::IsNearlyEqual(R.Value, R.Other, FMath::Abs(R.Other) * 0.005f + 0.001f);
		const bool bBetter = bDiffers && (R.bLowerBetter ? R.Value < R.Other : R.Value > R.Other);
		UHorizontalBox* Line = Make<UHorizontalBox>(T);
		Line->AddChildToHorizontalBox(Sized(T, Text(T, R.Name, 9, Soft, FaceBold, 180), 104.0f, 0.0f))->SetVerticalAlignment(VAlign_Center);
		UHorizontalBoxSlot* BarSlot = Line->AddChildToHorizontalBox(Sized(T, StatBar(T, this, Fill(R.Value), bDiffers ? Fill(R.Other) : Fill(R.Value), 14, FLinearColor(0.84f, 0.9f, 1.0f, 0.92f)), 0.0f, 8.0f));
		BarSlot->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
		BarSlot->SetVerticalAlignment(VAlign_Center);
		UTextBlock* Value = Text(T, R.Shown, 11, Ink, FaceBold);
		Value->SetJustification(ETextJustify::Right);
		Line->AddChildToHorizontalBox(Sized(T, Value, 84.0f, 0.0f))->SetVerticalAlignment(VAlign_Center);
		FString Delta;
		if (bDiffers)
		{
			Delta = FString::Printf(TEXT("%+.0f%%"), (R.Value / FMath::Max(R.Other, 0.001f) - 1.0f) * 100.0f);
		}
		UTextBlock* DeltaText = Text(T, Delta, 9, bBetter ? Good : Bad, FaceBold);
		DeltaText->SetJustification(ETextJustify::Right);
		Line->AddChildToHorizontalBox(Sized(T, DeltaText, 50.0f, 0.0f))->SetVerticalAlignment(VAlign_Center);
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
		UOverlaySlot* Line = Spine->AddChildToOverlay(Sized(T, Column, 44.0f, 0.0f));
		Line->SetHorizontalAlignment(HAlign_Left);
		Line->SetVerticalAlignment(VAlign_Fill);
	}
	UVerticalBox* Nodes = Make<UVerticalBox>(T);
	auto Node = [&](int32 Which, const FLinearColor& Color, const FString& Title, const FString& Words, float Gap)
	{
		UHorizontalBox* Row = Make<UHorizontalBox>(T);
		Row->AddChildToHorizontalBox(Hex(T, this, Which, Color, 44.0f))->SetVerticalAlignment(VAlign_Center);
		UVerticalBox* Lines = Make<UVerticalBox>(T);
		Lines->AddChildToVerticalBox(Text(T, Title, 12, Color == Gold ? Gold : Ink, FaceBold, 60));
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

	// what can be done with it
	SetActions(true);
	LockButton->SetVisibility(ESlateVisibility::Visible);
	DismantleButton->SetVisibility(ESlateVisibility::Visible);
	UpgradeButton->SetVisibility(ESlateVisibility::Visible);
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
	DismantleLabel->SetText(FText::FromString(bArmed ? FString::Printf(TEXT("CONFIRM +%d"), USOLootLibrary::DismantleAlloy(W)) : FString(TEXT("DISMANTLE"))));
	DismantleLabel->SetColorAndOpacity(FSlateColor(bCanDismantle ? (bArmed ? Bad : Ink) : Dim));
	ShowUpgrade(W.Uid);
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
		Inspect->AddChildToVerticalBox(Lore)->SetPadding(FMargin(0, 0, 0, 16));
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
	// an item in the list: choose it (a second click on the one chosen equips / wears it)
	if (SelectedKey == Tile.Key)
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
	SyncPreview();
	if (const FSOWeaponInstance* W = Inventory ? Inventory->Find(Key) : nullptr; W && W->bNew)
	{
		Inventory->ServerMarkSeen(Key);                           // (the inventory changes: the screen refreshes)
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
		// the loadout: the hovered slot's quick look beside it
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
	if (Info.Kind != TEXT("weapon") && Info.Kind != TEXT("armor") && Info.Kind != TEXT("blade"))
	{
		return;
	}
	const FString Want = bHover ? Info.Key : FString();
	if (HoverKey != Want)
	{
		HoverKey = Want;
		FillInspect();
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

void USOInventoryWidget::OnTab(const FString& Key)
{
	if (IsArmourSlot(Key))
	{
		if (Key != OpenSlotId)
		{
			OpenSlot(Key);                                      // (an armour slot's chip)
		}
		return;
	}
	const bool bArmourOpen = IsArmourSlot(OpenSlotId);
	if (Key == OpenSlotId || (Key == TEXT("armour") && bArmourOpen))
	{
		return;
	}
	OpenSlot(Key);
}

void USOInventoryWidget::OpenSlot(const FString& SlotId)
{
	const FString Want = SlotId == TEXT("armour") ? LastArmourSlot : SlotId;
	if (IsArmourSlot(Want))
	{
		LastArmourSlot = Want;
	}
	const bool bSameView = IsArmourSlot(Want) && IsArmourSlot(OpenSlotId);
	OpenSlotId = Want;
	SelectedKey.Reset();
	HoverKey.Reset();
	QuickKey.Reset();
	DismantleArmedAt = -100.0;
	ListScroll = nullptr;
	ListOffset = 0.0f;
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
		else if (const FSOArmorInstance* A = IsArmourSlot(Want) ? Inventory->GetEquippedArmor(FName(*Want)) : nullptr)
		{
			SelectedKey = A->Uid;
		}
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
	static const TCHAR* Tabs[] = { TEXT(""), TEXT("0"), TEXT("1"), TEXT("2"), TEXT("melee"), TEXT("armour") };
	int32 Now = 0;
	if (IsWeaponSlot(OpenSlotId))
	{
		Now = 1 + FMath::Clamp(FCString::Atoi(*OpenSlotId), 0, 2);
	}
	else if (OpenSlotId == TEXT("melee"))
	{
		Now = 4;
	}
	else if (IsArmourSlot(OpenSlotId))
	{
		Now = 5;
	}
	const int32 Count = static_cast<int32>(UE_ARRAY_COUNT(Tabs));
	OpenSlot(Tabs[(Now + Step + Count) % Count]);
}

void USOInventoryWidget::StepList(int32 Step)
{
	if (OpenSlotId.IsEmpty() || ListTiles.Num() == 0)
	{
		return;
	}
	int32 Now = ListTiles.IndexOfByPredicate([this](const USOInventoryTile* Tile) { return Tile && Tile->GetInfo().Key == SelectedKey; });
	const int32 Next = Now == INDEX_NONE ? 0 : FMath::Clamp(Now + Step, 0, ListTiles.Num() - 1);
	if (Next == Now || !ListTiles[Next])
	{
		return;
	}
	Choose(ListTiles[Next]->GetInfo().Key);
	if (ListScroll)
	{
		ListScroll->ScrollWidgetIntoView(ListTiles[Next], true, EDescendantScrollDestination::IntoView);
	}
}

void USOInventoryWidget::SyncPreview()
{
	if (!Preview || !Inventory)
	{
		return;
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
	int32 NewPower = 0, CostCredits = 0, CostAlloy = 0;
	if (Uid.IsEmpty() || !Inventory)
	{
		UpgradeButton->SetIsEnabled(false);
		UpgradeLabel->SetText(FText::FromString(TEXT("RAISE")));
		UpgradeLabel->SetColorAndOpacity(FSlateColor(Dim));
	}
	else if (!Inventory->GetUpgrade(Uid, NewPower, CostCredits, CostAlloy))
	{
		// as far as this level lets it go
		UpgradeButton->SetIsEnabled(false);
		UpgradeLabel->SetText(FText::FromString(FString::Printf(TEXT("AS HIGH AS LEVEL %d ALLOWS  (%d)"), Inventory->GetLevel(), Inventory->GetPowerCap())));
		UpgradeLabel->SetColorAndOpacity(FSlateColor(Dim));
	}
	else
	{
		const bool bCanPay = Inventory->GetCredits() >= CostCredits && Inventory->GetAlloy() >= CostAlloy;
		UpgradeButton->SetIsEnabled(bCanPay);
		UpgradeLabel->SetText(FText::FromString(FString::Printf(TEXT("RAISE TO %d     %s CREDITS  ·  %s ALLOY"), NewPower, *Number(CostCredits), *Number(CostAlloy))));
		UpgradeLabel->SetColorAndOpacity(FSlateColor(bCanPay ? Ink : Bad));
	}
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
	const int32 At = ListTiles.IndexOfByPredicate([&Gone](const USOInventoryTile* Tile) { return Tile && Tile->GetInfo().Key == Gone; });
	SelectedKey.Reset();
	if (At != INDEX_NONE && ListTiles.Num() > 1)
	{
		const int32 Next = At + 1 < ListTiles.Num() ? At + 1 : At - 1;
		SelectedKey = ListTiles[Next] ? ListTiles[Next]->GetInfo().Key : FString();
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
		return FReply::Handled().CaptureMouse(TakeWidget());
	}
	if (InMouseEvent.GetEffectingButton() == EKeys::RightMouseButton && !OpenSlotId.IsEmpty())
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
			OpenSlot(FString());                                 // back to the loadout first
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
	if (Key == EKeys::A || Key == EKeys::Left || Key == EKeys::Gamepad_LeftTrigger)
	{
		StepTab(-1);
		return FReply::Handled();
	}
	if (Key == EKeys::D || Key == EKeys::Right || Key == EKeys::Gamepad_RightTrigger)
	{
		StepTab(1);
		return FReply::Handled();
	}
	if (Key == EKeys::W || Key == EKeys::Up || Key == EKeys::Gamepad_DPad_Up)
	{
		StepList(-1);
		return FReply::Handled();
	}
	if (Key == EKeys::S || Key == EKeys::Down || Key == EKeys::Gamepad_DPad_Down)
	{
		StepList(1);
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
	if (Key == EKeys::U || Key == EKeys::Gamepad_LeftShoulder)
	{
		OnUpgrade();
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
