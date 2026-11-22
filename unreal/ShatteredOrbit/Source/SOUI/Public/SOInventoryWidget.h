#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "Components/Button.h"
#include "SOInventoryWidget.generated.h"

class ASceneCapture2D;
class APointLight;
class UBorder;
class UButton;
class UMaterialInstanceDynamic;
class UCanvasPanel;
class UCanvasPanelSlot;
class UHorizontalBox;
class UImage;
class UScrollBox;
class UTextBlock;
class UTexture2D;
class UTextureRenderTarget2D;
class UVerticalBox;
class UWrapBox;
class UWidget;
class USOInventoryComponent;
class USOInventoryWidget;
struct FSOArmorInstance;
struct FSOOutfit;
struct FSOGoodsInfo;
struct FSOWeaponInstance;
struct FSOMeleeStyle;

/** A button the keyboard and the pad never focus: the armoury keeps the focus itself and moves its own highlight. */
UCLASS()
class SOUI_API USOQuietButton : public UButton
{
	GENERATED_BODY()

public:
	USOQuietButton(const FObjectInitializer& ObjectInitializer) : Super(ObjectInitializer) { InitIsFocusable(false); }
};

/**
 * The picture of the player in the middle of the armoury: a stand-in character of its own (always there, whatever the
 * pawn is doing), high above the world, wearing the inventory's outfit and holding the gun in hand carried low across
 * the chest (a hero's stance, ASOCharacter::SetDisplayCarry), seen by a scene capture that draws only it (transparent
 * background), lit by its own key, two rims, a fill and the platform's light from below, turned by dragging. While an
 * item is chosen in an armoury it holds that gun, raises those fists or that blade, or wears that piece instead.
 */
UCLASS()
class SOUI_API USOCharacterPreview : public UObject
{
	GENERATED_BODY()

public:
	void Start(APlayerController* Player);
	/** Dresses and arms the stand-in like the inventory says (cheap when nothing changed). ShowWeapon: a gun's uid or
	 *  "melee:<style>" to hold that instead of the gun in hand; ShowArmor: a piece's uid to wear over its slot. */
	void Sync(USOInventoryComponent* Inventory, const FString& ShowWeapon = FString(), const FString& ShowArmor = FString(), const FSOOutfit* Look = nullptr);
	void Stop();
	void Tick(float DeltaTime);
	/** The face's sliders and the tones of a look on the stand-in at once (a slider being dragged). */
	void ShowLook(const FSOOutfit& Look);
	/** How close the picture is (0 the whole body, about .55 head and shoulders, 1 the face: eased), and only the
	 *  body and what it wears drawn (the character builder: no gun in the hands or on the back). */
	void SetFraming(float InClose, bool bInBodyOnly);
	/** Turns the stand-in to so many degrees (eased; a drag takes over). */
	void TurnTo(float Degrees) { YawGoal = Degrees; bTurning = true; }
	void StopTurning() { bTurning = false; }
	APawn* GetMannequin() const { return Subject.Get(); }
	UTextureRenderTarget2D* GetTarget() const { return Target; }

	/** Degrees round the character (0 = from the front). */
	float Yaw = 24.0f;

	/** The picture's height on the screen is the stage's; where the feet stand in it (0 top .. 1 bottom), worked out
	 *  from the capture's framing (Tick): the platform is drawn there. */
	static constexpr float FeetInPicture = 0.88f;

private:
	UPROPERTY(Transient)
	TObjectPtr<UTextureRenderTarget2D> Target;

	TWeakObjectPtr<ASceneCapture2D> Capture;
	TArray<TWeakObjectPtr<APointLight>> Lights;
	TWeakObjectPtr<APawn> Subject;
	FString ShownWeapon;
	FString ShownOutfit;
	float Close = 0.0f;
	float CloseTarget = 0.0f;
	bool bBodyOnly = false;
	float YawGoal = 0.0f;
	bool bTurning = false;
	void UpdateShowList();
	/** r.PostProcessing.PropagateAlpha before the preview turned it on (the picture's background is transparent). */
	int32 PreviousAlpha = -1;
};

/** How a card is drawn: the loadout's big card, a cell of an armoury's grid, a row of its list. */
UENUM()
enum class ESOTileStyle : uint8
{
	Card,
	Cell,
	Row,
};

/** One card on the armoury screen: a slot (what is held / worn there), an owned item in an armoury's grid or list, or
 *  a collected item in the inventory. */
USTRUCT()
struct FSOTileInfo
{
	GENERATED_BODY()

	/** wslot | mslot | aslot (the loadout's slots) | weapon | blade | armor | goods (an armoury's items) */
	FName Kind;
	/** a slot's key ("0".."2", "melee", head .. feet), the item's uid ("melee:<style>" for a melee style, "goods:<id>"
	 *  for a collected item) */
	FString Key;
	UPROPERTY(Transient)
	TObjectPtr<UTexture2D> Icon = nullptr;
	FLinearColor Rarity = FLinearColor::White;
	FString Title;
	/** the small line over the name (the slot: PRIMARY, CHEST ...) */
	FString Sub;
	/** the line under the name (what it is: AUTO RIFLE · LIGHT, LEGENDARY · 17 ARMOUR) */
	FString Tag;
	int32 Power = 0;
	/** power against the one equipped in its slot (an armoury's item; 0 = the same or nothing to compare) */
	int32 PowerDelta = 0;
	/** a collected item: how many are held (-1: not a collected item) */
	int32 Count = -1;
	/** what it is used for the sort by rarity and by newest (its rarity; its place in the vault, newest last) */
	int32 RarityIndex = 0;
	int32 Order = 0;
	ESOTileStyle Style = ESOTileStyle::Card;
	/** which column it stands in (its quick look opens on the stage's side) */
	bool bLeft = true;
	/** chosen in its list, or its slot is open */
	bool bActive = false;
	bool bEquipped = false;
	bool bInHand = false;
	bool bNew = false;
	bool bLocked = false;
	bool bEmpty = false;
	/** a square picture (an armour piece, a collected item), not a gun's long one */
	bool bSquare = false;
	/** a glyph drawn where there is no picture (M_UI_Glyph's index; -1 none) */
	int32 Glyph = -1;
};

UCLASS()
class SOUI_API USOInventoryTile : public UUserWidget
{
	GENERATED_BODY()

public:
	void Setup(USOInventoryWidget* InScreen, const FSOTileInfo& InInfo) { Screen = InScreen; Info = InInfo; }
	const FSOTileInfo& GetInfo() const { return Info; }
	/** Lights the card as the one chosen in its list (or not) without building it again. */
	void SetChosen(bool bChosen);
	/** The keyboard's or pad's highlight is on it (it looks and leans as if hovered). */
	void SetFocused(bool bOn);

	/** A grid's cell and a list's row (the armoury's sizes, from its layout). */
	static constexpr float CellHeight = 130.0f;
	static constexpr float RowHeight = 56.0f;
	float Width = 134.0f;

protected:
	virtual TSharedRef<SWidget> RebuildWidget() override;
	virtual void NativeTick(const FGeometry& MyGeometry, float InDeltaTime) override;

	/** A grid's cell / a list's row (the loadout's card is built by RebuildWidget itself). */
	UWidget* BuildCell();
	UWidget* BuildRow();

	UFUNCTION()
	void OnClicked();

	UFUNCTION()
	void OnHovered();

	UFUNCTION()
	void OnUnhovered();

	void Restyle();

	UPROPERTY(Transient)
	TObjectPtr<USOInventoryWidget> Screen;

	UPROPERTY(Transient)
	TObjectPtr<UButton> Button;

	UPROPERTY(Transient)
	FSOTileInfo Info;

	/** The card leans toward the stage while hovered or focused (pixels, eased). */
	float Lift = 0.0f;
	float LiftTarget = 0.0f;
	bool bHovered = false;
	bool bFocused = false;
};

/** What an armoury control is: a tab of the bar along the top, a slot's tile, a row of a list (a family, an origin,
 *  an armour slot, a kind of collected item), a page's number, a tool (the sort, the views, the page's arrows). */
UENUM()
enum class ESOArmouryControl : uint8
{
	Tab,
	SlotTile,
	Row,
	Page,
	Tool,
	/** the character builder: a tone (its colour, its name) */
	Swatch,
	/** the character builder: one of a few choices as a wide plate (the body) */
	Choice,
};

/** One of the armoury's small controls: clicked, it tells the screen what it is and its key. */
UCLASS()
class SOUI_API USOArmouryButton : public UUserWidget
{
	GENERATED_BODY()

public:
	void Setup(USOInventoryWidget* InScreen, ESOArmouryControl InKind, const FString& InKey, const FString& InLabel, bool bInActive)
	{
		Screen = InScreen;
		Kind = InKind;
		Key = InKey;
		Label = InLabel;
		bActive = bInActive;
	}

	/** A row's figure at its far end ("12"). */
	FString Count;
	/** A slot tile's picture (the gun equipped there) or its glyph (M_UI_Glyph's index) where there is none. */
	UPROPERTY(Transient)
	TObjectPtr<UTexture2D> Icon = nullptr;
	int32 GlyphIndex = -1;
	/** Something new waits in it (a gold mark); nothing is in it (dimmed). */
	bool bNew = false;
	bool bDim = false;
	/** Its width (0: as wide as its words). */
	float Width = 0.0f;
	/** A tool's own drawing: 1 the grid view's squares, 2 the list view's bars. */
	int32 Drawing = 0;
	/** A swatch's colour (linear, as drawn). */
	FLinearColor SwatchColor = FLinearColor::White;

protected:
	virtual TSharedRef<SWidget> RebuildWidget() override;

	UFUNCTION()
	void OnClicked();

	UPROPERTY(Transient)
	TObjectPtr<USOInventoryWidget> Screen;

	ESOArmouryControl Kind = ESOArmouryControl::Row;
	FString Key;
	FString Label;
	bool bActive = false;
};

/** One of the character builder's sliders: a face key (-1..1) with its name and figure, a track with the middle
 *  marked, the fill from the middle to the value, a knob; dragged (the stand-in follows as it moves, the value is kept
 *  when it is let go), the wheel nudges it, a double click puts it back to the middle. */
UCLASS()
class SOUI_API USOCreatorSlider : public UUserWidget
{
	GENERATED_BODY()

public:
	void Setup(USOInventoryWidget* InScreen, FName InKey, const FString& InLabel, float InValue, float InWidth)
	{
		Screen = InScreen;
		Key = InKey;
		Label = InLabel;
		Value = InValue;
		Width = InWidth;
	}
	FName GetKey() const { return Key; }
	float GetValue() const { return Value; }
	bool IsDragging() const { return bDragging; }
	/** Moves the knob, the fill and the figure (nothing is built again). */
	void SetValue(float InValue);
	/** The keyboard's or pad's highlight is on it. */
	void SetFocused(bool bOn);

	static constexpr float Height = 54.0f;

protected:
	virtual TSharedRef<SWidget> RebuildWidget() override;
	virtual FReply NativeOnMouseButtonDown(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) override;
	virtual FReply NativeOnMouseMove(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) override;
	virtual FReply NativeOnMouseButtonUp(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) override;
	virtual FReply NativeOnMouseButtonDoubleClick(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) override;
	virtual FReply NativeOnMouseWheel(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) override;
	virtual void NativeOnMouseEnter(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) override;
	virtual void NativeOnMouseLeave(const FPointerEvent& InMouseEvent) override;

	float ValueAt(const FGeometry& Geometry, const FPointerEvent& Event) const;
	void Restyle();
	float TrackLeft() const { return 18.0f; }
	float TrackRight() const { return Width - 18.0f; }

	UPROPERTY(Transient)
	TObjectPtr<USOInventoryWidget> Screen;

	UPROPERTY(Transient)
	TObjectPtr<UBorder> Frame;

	UPROPERTY(Transient)
	TObjectPtr<UTextBlock> LabelText;

	UPROPERTY(Transient)
	TObjectPtr<UTextBlock> ValueText;

	UPROPERTY(Transient)
	TObjectPtr<UWidget> Knob;

	UPROPERTY(Transient)
	TObjectPtr<UWidget> FillBar;

	UPROPERTY(Transient)
	TObjectPtr<UWidget> AccentBar;

	FName Key;
	FString Label;
	float Value = 0.0f;
	float Width = 400.0f;
	bool bHovered = false;
	bool bFocused = false;
	bool bDragging = false;
};

/**
 * The armoury (I / Tab). The owner, 2026-11-16: "take our menu and upgrade it ready for a triple a game release on
 * steam"; and 2026-11-20, with their reference screen (art/reference/ui/armoury_arsenal.webp, its words and glyphs the
 * picture-maker's, never ours): "how to better organize weapons and other things we need like an inventory to hold
 * items we collect".
 *
 * Along the top the banner (the emblem, the name, the level; credits, alloy, the vault, power) with the TABS between
 * (Q / E, the triggers): LOADOUT · ARSENAL · ARMOUR · INVENTORY.
 *
 * LOADOUT: the character large on a lit platform in the middle holding the gun low; left the four weapon cards
 * (primary, special, heavy, melee), right the seven armour cards, the six attributes beside the stage; a hovered card's
 * quick look; the body (male / female) under the stage.
 *
 * ARSENAL (a weapon slot's guns, or the melee styles), ARMOUR (a slot's pieces), INVENTORY (the collected items: USOLoot-
 * Tables::Goods): left the slot's name and its tiles (A / D, the bumpers), then the categories with their counts (every
 * family of the slot, then every origin; the armour's slots; the kinds of items: materials, consumables, keys, relics);
 * in the middle a GRID of cards (power, name, its rarity's light; the equipped, new and locked marked) with a sort
 * (power, rarity, newest, name), a grid or a list, pages; the character between the grid and the panel holding,
 * raising or wearing what is chosen; right the INSPECT panel (what it is, its name, its line, a large picture, power
 * and how far it can be raised, the stats beside the perks, the trait; DETAILS (F) for every number against the one
 * equipped) with its actions (equip / use, details, lock, dismantle, raise with what it takes). Hold C: the chosen gun
 * against the one carried in its slot, side by side over the grid.
 *
 * Every card is M_UI_Card, every shape its own material (sized from the UV derivatives: crisp at any resolution). Built
 * in C++. The layout audit (-SOHudAudit, as the HUD's) logs ARMOURYOVERLAP / ARMOURYCLIP for words, pictures and glyphs
 * that cross or are cut.
 */
UCLASS()
class SOUI_API USOInventoryWidget : public UUserWidget
{
	GENERATED_BODY()

public:
	/** What the screen shows: the loadout, a weapon slot's arsenal (or the melee styles), an armour slot, the inventory,
	 *  the character builder, the journal (in the order of the tabs). */
	enum class EView : uint8 { Loadout, Arsenal, Armour, Goods, Character, Journal };

	void Bind(USOInventoryComponent* InInventory);
	void Refresh();
	void Close();

	/** A card was clicked / hovered (USOInventoryTile). */
	void OnTile(const FSOTileInfo& Tile);
	void OnTileHover(USOInventoryTile* Tile, bool bHover);
	/** A control was clicked (USOArmouryButton). */
	void OnControl(ESOArmouryControl Kind, const FString& Key);

	/** Opens a view: "0".."2" a weapon slot's arsenal, "melee", head .. feet an armour slot ("armour": the one open
	 *  last), "goods" the inventory, "character" the builder, "journal" the journal; empty = the loadout. */
	void OpenSlot(const FString& SlotId);
	const FString& GetOpenSlot() const { return OpenSlotId; }
	EView GetView() const;
	/** Opens a loadout card's quick look as a hover does (its slot's key; empty = closes it): the capture series. */
	void PeekSlot(const FString& SlotKey);
	/** Spins the stand-in as a flick does (degrees a second, settling); the capture series. */
	void SpinStandIn(float DegreesPerSecond) { SpinVelocity = DegreesPerSecond; bDragging = false; }
	/** The keyboard's / pad's highlight (the arrows, the d-pad, the left stick, W / S): in the loadout over the cards (a
	 *  column and a row; the first press only shows where it is), in a grid the choice (a row is a column's width).
	 *  Accept (Enter, Space, the pad's A) opens the slot, equips or uses. */
	void MoveFocus(int32 DX, int32 DY);
	void Accept();

	/** The capture series and the keys: the open list's category ("family:<id>", "origin:<id>", "kind:<goods kind>";
	 *  empty = all), its order (0 power, 1 rarity, 2 newest, 3 name), the list instead of the grid, the details, the
	 *  comparison held, the item chosen. */
	void SetFilter(const FString& InFilter);
	void SetSort(int32 Mode);
	void SetListView(bool bList);
	void SetDetails(bool bOn);
	void SetCompare(bool bOn);
	void ChooseItem(const FString& Key) { Choose(Key); }
	/** The layout audit (also -SOHudAudit on the command line). */
	void SetAudit(bool bOn) { bAuditing = bOn; AuditLast.Reset(); }

	/** The character builder (the CHARACTER tab): its group ("body", "hair", "eyes" ...: Data/creator.json); a slider
	 *  moved (bCommit: let go, kept on the profile; otherwise the stand-in alone follows it). */
	void SetCreatorGroup(FName Group);
	FName GetCreatorGroup() const { return CreatorGroup; }
	void OnSlider(FName Key, float Value, bool bCommit);
	/** The mouse is over a slider (the keyboard's highlight follows it). */
	void OnSliderHover(FName Key);

	/** Called when the screen wants to close (the HUD restores game input). */
	TFunction<void()> OnClose;

protected:
	virtual TSharedRef<SWidget> RebuildWidget() override;
	virtual void NativeConstruct() override;
	virtual void NativeDestruct() override;
	virtual void NativeTick(const FGeometry& MyGeometry, float InDeltaTime) override;
	virtual FReply NativeOnKeyDown(const FGeometry& InGeometry, const FKeyEvent& InKeyEvent) override;
	virtual FReply NativeOnKeyUp(const FGeometry& InGeometry, const FKeyEvent& InKeyEvent) override;
	virtual FReply NativeOnMouseButtonDown(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) override;
	virtual FReply NativeOnMouseButtonUp(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) override;
	virtual FReply NativeOnMouseMove(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) override;
	virtual FReply NativeOnMouseWheel(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) override;
	virtual FNavigationReply NativeOnNavigation(const FGeometry& MyGeometry, const FNavigationEvent& InNavigationEvent, const FNavigationReply& InDefaultReply) override;
	virtual FReply NativeOnAnalogValueChanged(const FGeometry& InGeometry, const FAnalogInputEvent& InAnalogEvent) override;
	virtual FCursorReply NativeOnCursorQuery(const FGeometry& InGeometry, const FPointerEvent& InCursorEvent) override;

	UFUNCTION()
	void OnEquip();

	UFUNCTION()
	void OnLock();

	UFUNCTION()
	void OnDismantle();

	UFUNCTION()
	void OnUpgrade();

	UFUNCTION()
	void OnBody();

	UFUNCTION()
	void OnDetails();

	void BuildTree();
	void FillBanner();
	void FillLoadout();
	/** An armoury view: its column (the slot's name, its tiles, the categories), its grid, its inspect panel. */
	void FillArmoury();
	void FillTabs();
	void FillHints();
	void FillInspect();
	void FillWeaponInspect(const FSOWeaponInstance& W);
	void FillArmorInspect(const FSOArmorInstance& A);
	void FillMeleeInspect(const FSOMeleeStyle& Style, FName Id);
	void FillGoodsInspect(const FSOGoodsInfo& Info);
	/** The journal (the JOURNAL tab: SOJournal.h): an entry to read (its section and what it is, its title, its
	 *  portrait beside its words, what it notes, its tally), one not yet learned, or the service record. */
	void FillJournalInspect(FName EntryId);
	void FillRecord();
	/** The journal's open section (its filter "section:<id>"; none: the first). */
	FName JournalSection() const;
	/** Cards a page holds: a list's rows (the journal is always a list) or the grid's cells. */
	int32 CardsPerPage() const;
	/** The six attributes; with a piece, what wearing it would change. */
	void FillAttributes(const FSOArmorInstance* TryOn);
	void FillQuickLook(USOInventoryTile* Tile);
	/** The chosen gun against the one carried in its slot (C held), over the grid. */
	void FillCompare();
	void ShowUpgrade(const FString& Uid);
	/** Shows or hides the inspect panel's buttons (nothing to act on: hidden). */
	void SetActions(bool bShow);
	/** Chooses an item of the open list (the card lit, the inspect panel and the stand-in follow). */
	void Choose(const FString& Key);
	FSOTileInfo WeaponTile(const FSOWeaponInstance& W, bool bSlot) const;
	FSOTileInfo ArmorTile(const FSOArmorInstance& A, bool bSlot) const;
	/** The open view's items, in its category and order (all pages). */
	TArray<FSOTileInfo> ListItems() const;
	/** The page of the open list an item is on (0 when it is not in it). */
	int32 PageOf(const FString& Key) const;
	FString ShownKey() const;
	bool IsWeaponSlot(const FString& SlotKey) const { return SlotKey.Len() == 1 && FChar::IsDigit(SlotKey[0]); }
	bool IsArmourSlot(const FString& SlotKey) const;
	/** Moves the armoury one tab left or right (from the loadout too). */
	void StepTab(int32 Step);
	/** Moves to the slot (the arsenal's, the armour's) or the kind of item beside the open one. */
	void StepSlot(int32 Step);
	/** Moves the choice in the open grid by so many (a page turns with it). */
	void StepList(int32 Step);
	void StepPage(int32 Step);
	/** Shows the chosen gun / style / piece on the stand-in. */
	void SyncPreview();
	/** The panels slide and fade in after a change of view. */
	void Animate();
	void ApplyFocus();
	TArray<USOInventoryTile*> ColumnTiles(int32 Column) const;
	/** Places everything for the screen's width in its own units and the view: wider than 2200 the layout keeps to a
	 *  frame of 2200 in the middle; narrower, the grid and the panel give way (fewer columns, a narrower panel). */
	void UpdateLayout(float Width);
	/** The layout audit: every word, picture and glyph on the screen against the others. */
	void Audit();
	/** The character builder: its column (the groups), its sliders or its tones; the look as the player has it with
	 *  what is being moved on top; the keyboard's row and what left / right does there; a tone chosen; the resets. */
	void FillCharacter();
	FSOOutfit CurrentLook() const;
	void CreatorStep(int32 DX, int32 DY);
	void ApplyCreatorFocus();
	void ChooseTone(bool bHair, int32 Index);
	void ResetLook(bool bAll);
	void RandomFace();
	/** The body has this face key's morph target (the two bodies' faces were built apart). */
	bool HasMorph(FName Key) const;
	/** The groups the body can use (a face group with none of its keys on this body is left out). */
	TArray<FName> CreatorGroups() const;

	UPROPERTY(Transient)
	TObjectPtr<USOInventoryComponent> Inventory;

	UPROPERTY(Transient)
	TObjectPtr<USOCharacterPreview> Preview;

	UPROPERTY(Transient)
	TObjectPtr<UCanvasPanel> Root;

	UPROPERTY(Transient)
	TObjectPtr<UImage> PreviewImage;

	/** The picture's material (its soft edge is the character builder's). */
	UPROPERTY(Transient)
	TObjectPtr<UMaterialInstanceDynamic> StageMaterial;

	UPROPERTY(Transient)
	TObjectPtr<UImage> FloorImage;

	/** The banner: the name, the level line, the level's bar; the currencies; the power. */
	UPROPERTY(Transient)
	TObjectPtr<UTextBlock> NameText;

	UPROPERTY(Transient)
	TObjectPtr<UTextBlock> LevelText;

	UPROPERTY(Transient)
	TObjectPtr<UTextBlock> XpText;

	UPROPERTY(Transient)
	TObjectPtr<UImage> XpBar;

	UPROPERTY(Transient)
	TObjectPtr<UTextBlock> MaleLabel;

	UPROPERTY(Transient)
	TObjectPtr<UTextBlock> FemaleLabel;

	UPROPERTY(Transient)
	TObjectPtr<UHorizontalBox> Currencies;

	UPROPERTY(Transient)
	TObjectPtr<UTextBlock> PowerText;

	/** The loadout's columns. */
	UPROPERTY(Transient)
	TObjectPtr<UVerticalBox> LeftPanel;

	UPROPERTY(Transient)
	TObjectPtr<UVerticalBox> RightPanel;

	UPROPERTY(Transient)
	TObjectPtr<UVerticalBox> AttributeColumn;

	/** An armoury's column (its name, its tiles, its categories, the comparison's key), its grid, and the inspect
	 *  panel's place. */
	UPROPERTY(Transient)
	TObjectPtr<UVerticalBox> CategoryPanel;

	UPROPERTY(Transient)
	TObjectPtr<UVerticalBox> GridPanel;

	UPROPERTY(Transient)
	TObjectPtr<UVerticalBox> InspectPanel;

	/** The comparison over the grid (C held). */
	UPROPERTY(Transient)
	TObjectPtr<UBorder> CompareBox;

	/** A hovered loadout card's quick look, beside it. */
	UPROPERTY(Transient)
	TObjectPtr<UBorder> QuickLook;

	UPROPERTY(Transient)
	TObjectPtr<UHorizontalBox> TabRow;

	UPROPERTY(Transient)
	TObjectPtr<UHorizontalBox> HintRow;

	/** The grid's cards (this page, in order). */
	UPROPERTY(Transient)
	TArray<TObjectPtr<USOInventoryTile>> ListTiles;

	/** The inspect panel (built once, put in its place by an armoury): its content (scrolls), its buttons. */
	UPROPERTY(Transient)
	TObjectPtr<UWidget> InspectFrame;

	UPROPERTY(Transient)
	TObjectPtr<UScrollBox> InspectScroll;

	UPROPERTY(Transient)
	TObjectPtr<UVerticalBox> Inspect;

	UPROPERTY(Transient)
	TObjectPtr<UWidget> ActionBlock;

	UPROPERTY(Transient)
	TObjectPtr<UButton> EquipButton;

	UPROPERTY(Transient)
	TObjectPtr<UButton> DetailsButton;

	UPROPERTY(Transient)
	TObjectPtr<UButton> LockButton;

	UPROPERTY(Transient)
	TObjectPtr<UButton> DismantleButton;

	UPROPERTY(Transient)
	TObjectPtr<UButton> UpgradeButton;

	UPROPERTY(Transient)
	TObjectPtr<UTextBlock> EquipLabel;

	/** The equip button's key (it gives way on a narrow panel). */
	UPROPERTY(Transient)
	TObjectPtr<UWidget> EquipKey;

	UPROPERTY(Transient)
	TObjectPtr<UTextBlock> DetailsLabel;

	UPROPERTY(Transient)
	TObjectPtr<UTextBlock> LockLabel;

	UPROPERTY(Transient)
	TObjectPtr<UTextBlock> DismantleLabel;

	UPROPERTY(Transient)
	TObjectPtr<UTextBlock> UpgradeLabel;

	/** What a raise takes beside credits and alloy (its materials, under the RAISE button). */
	UPROPERTY(Transient)
	TObjectPtr<UWrapBox> UpgradeGoodsRow;

	/** What UpdateLayout moves. */
	UPROPERTY(Transient)
	TObjectPtr<UWidget> BannerLeft;

	UPROPERTY(Transient)
	TObjectPtr<UWidget> BannerRight;

	UPROPERTY(Transient)
	TObjectPtr<UWidget> BannerRule;

	UPROPERTY(Transient)
	TObjectPtr<UWidget> BannerLit;

	UPROPERTY(Transient)
	TObjectPtr<UWidget> FooterRule;

	UPROPERTY(Transient)
	TObjectPtr<UWidget> DragHint;

	UPROPERTY(Transient)
	TObjectPtr<UWidget> BodyToggle;

	FString OpenSlotId;
	FString LastArmourSlot = TEXT("head");
	FString LastArsenalSlot = TEXT("0");
	/** The open list's category, its order, the list instead of the grid, its page; the details shown; C held. */
	FString Filter;
	int32 SortMode = 0;
	bool bListView = false;
	int32 Page = 0;
	bool bDetails = false;
	bool bComparing = false;
	int32 FocusColumn = 0;
	int32 FocusRow = 0;
	/** The highlight shows (the keyboard or the pad moved it; the mouse takes over on a hover). */
	bool bKeyFocus = false;
	/** Turning the character: the right stick's deflection, the spin a drag leaves behind (degrees a second). */
	float StickYaw = 0.0f;
	float SpinVelocity = 0.0f;
	double LastDragTime = 0.0;
	float LaidOutWidth = 0.0f;
	double LastLayoutAt = 0.0;
	/** The layout for the width: the grid's columns, a cell's width, the grid's and the panel's widths, where the stage
	 *  stands, where the panels begin (lower when the tabs need a row of their own). */
	int32 Columns = 4;
	float CellWidth = 134.0f;
	float GridWidth = 566.0f;
	float InspectWidth = 500.0f;
	float StageX = 960.0f;
	float PanelsTop = 122.0f;
	FString SelectedKey;
	FString HoverKey;
	FString QuickKey;
	double DismantleArmedAt = -100.0;
	bool bDragging = false;
	/** The panels' slide in (0 just changed .. 1 settled). */
	float Arrive = 1.0f;
	FDelegateHandle ChangedHandle;
	/** The character builder: the group open, the row the keyboard is on, what was built (the group and the body:
	 *  the same again only moves the sliders), the sliders, what is being moved and not yet on the profile (a value
	 *  and when it was let go: a joined player's comes back a moment later), the reset or random asked once. */
	FName CreatorGroup = TEXT("body");
	int32 CreatorRow = 0;
	FString CreatorBuilt;
	UPROPERTY(Transient)
	TArray<TObjectPtr<USOCreatorSlider>> CreatorSliders;
	struct FPendingValue
	{
		float Value = 0.0f;
		double At = 0.0;
	};
	TMap<FName, FPendingValue> PendingFace;
	FLinearColor PendingSkin = FLinearColor(0.0f, 0.0f, 0.0f, 0.0f);
	FLinearColor PendingHair = FLinearColor(0.0f, 0.0f, 0.0f, 0.0f);
	double PendingSkinAt = -100.0;
	double PendingHairAt = -100.0;
	FString CreatorArmed;
	double CreatorArmedAt = -100.0;
	/** The builder was open (a new profile's first start is over when the armoury closes after it). */
	bool bShowedCreator = false;
	bool bAuditing = false;
	double AuditAt = 0.0;
	FString AuditLast;
};
