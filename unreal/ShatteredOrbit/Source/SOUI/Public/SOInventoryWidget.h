#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "Components/Button.h"
#include "SOInventoryWidget.generated.h"

class ASceneCapture2D;
class APointLight;
class UBorder;
class UButton;
class UCanvasPanel;
class UCanvasPanelSlot;
class UHorizontalBox;
class UImage;
class UScrollBox;
class UTextBlock;
class UTexture2D;
class UTextureRenderTarget2D;
class UVerticalBox;
class UWidget;
class USOInventoryComponent;
class USOInventoryWidget;
struct FSOArmorInstance;
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
	void Sync(USOInventoryComponent* Inventory, const FString& ShowWeapon = FString(), const FString& ShowArmor = FString());
	void Stop();
	void Tick(float DeltaTime);
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
	void UpdateShowList();
	/** r.PostProcessing.PropagateAlpha before the preview turned it on (the picture's background is transparent). */
	int32 PreviousAlpha = -1;
};

/** One card on the armoury screen: a slot (what is held / worn there) or an owned item in a slot's list. */
USTRUCT()
struct FSOTileInfo
{
	GENERATED_BODY()

	/** wslot | mslot | aslot (the loadout's slots) | weapon | blade | armor (an armoury list's items) */
	FName Kind;
	/** a slot's key ("0".."2", "melee", head .. feet) or the item's uid ("melee:<style>" for a melee style) */
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
	/** power against the one equipped in its slot (an armoury list's item; 0 = the same or nothing to compare) */
	int32 PowerDelta = 0;
	/** which column it stands in (its quick look opens on the stage's side) */
	bool bLeft = true;
	/** chosen in its list, or its slot is open */
	bool bActive = false;
	bool bEquipped = false;
	bool bInHand = false;
	bool bNew = false;
	bool bLocked = false;
	bool bEmpty = false;
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

protected:
	virtual TSharedRef<SWidget> RebuildWidget() override;
	virtual void NativeTick(const FGeometry& MyGeometry, float InDeltaTime) override;

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

/** A tab of the armoury's bar, or one of the armour list's slot chips: a word that is lit when it is the one open. */
UCLASS()
class SOUI_API USOArmouryTab : public UUserWidget
{
	GENERATED_BODY()

public:
	void Setup(USOInventoryWidget* InScreen, const FString& InKey, const FString& InLabel, bool bInActive, bool bInChip, bool bInNew)
	{
		Screen = InScreen;
		Key = InKey;
		Label = InLabel;
		bActive = bInActive;
		bChip = bInChip;
		bNew = bInNew;
	}

protected:
	virtual TSharedRef<SWidget> RebuildWidget() override;

	UFUNCTION()
	void OnClicked();

	UPROPERTY(Transient)
	TObjectPtr<USOInventoryWidget> Screen;

	FString Key;
	FString Label;
	bool bActive = false;
	bool bChip = false;
	/** something new is waiting in it (a gold mark) */
	bool bNew = false;
};

/**
 * The armoury (I / Tab): the loadout screen. The owner, 2026-11-16: "take our menu and upgrade it ready for a triple a
 * game release on steam"; their mockup and the reference screens set the bar, every look and word here is ours.
 *
 * LOADOUT (the overview): the backdrop (M_UI_Backdrop: night blue lit from the stage, the broken orbit turning faint
 * behind the character, motes in the light), the character large on a lit platform (M_UI_Floor) holding the gun low;
 * the banner across the top (the emblem, the name, the level and its bar, the body; credits, alloy, the vault and the
 * power); left the ARSENAL: four cards (primary, special, heavy, melee) with the gun's own render glowing in its
 * rarity's light; right the ARMOUR: seven cards; between them and the stage the six attributes; a hovered card opens
 * its quick look beside it. The tab bar along the foot: LOADOUT · PRIMARY · SPECIAL · HEAVY · MELEE · ARMOUR (A / D,
 * the triggers), and the keys.
 *
 * A slot's ARMOURY (a card clicked, or its tab): left everything owned for it (cards; the armour's slots as chips over
 * its list; up / down moves through it), right the INSPECT panel (the name large, its rarity, class and kind, its line,
 * power, the stats against the equipped one in segmented bars, the perks on a spine of hexagons with the trait of its
 * set or class in gold at its foot; a piece's attributes against the one worn, which the attribute column shows as
 * well; a melee style's blows) with Equip (E), Lock (L), Dismantle (X, twice) and Raise (U); the character holds the
 * chosen gun, raises the chosen fists or blade, or wears the chosen piece. Every card is M_UI_Card, every shape drawn
 * by its own material (sized from the UV derivatives: crisp at any resolution). Built in C++.
 */
UCLASS()
class SOUI_API USOInventoryWidget : public UUserWidget
{
	GENERATED_BODY()

public:
	void Bind(USOInventoryComponent* InInventory);
	void Refresh();
	void Close();

	/** A card was clicked / hovered (USOInventoryTile). */
	void OnTile(const FSOTileInfo& Tile);
	void OnTileHover(USOInventoryTile* Tile, bool bHover);
	/** A tab or an armour chip was clicked (USOArmouryTab). */
	void OnTab(const FString& Key);

	/** Opens a slot's armoury ("0".."2" weapons, "melee", head / top / vest / outer / hands / legs / feet armour, "armour"
	 *  the armour slot open last; empty = back to the loadout). */
	void OpenSlot(const FString& SlotId);
	const FString& GetOpenSlot() const { return OpenSlotId; }
	/** Opens a loadout card's quick look as a hover does (its slot's key; empty = closes it): the capture series. */
	void PeekSlot(const FString& SlotKey);
	/** The keyboard's / pad's highlight (the arrows, the d-pad, the left stick, W / S): in the loadout over the cards (a
	 *  column and a row; the first press only shows where it is), in an armoury the list's choice (and, over the armour,
	 *  its slot). Accept (Enter, Space, the pad's A) opens the slot or equips. */
	void MoveFocus(int32 DX, int32 DY);
	void Accept();

	/** Called when the screen wants to close (the HUD restores game input). */
	TFunction<void()> OnClose;

protected:
	virtual TSharedRef<SWidget> RebuildWidget() override;
	virtual void NativeConstruct() override;
	virtual void NativeDestruct() override;
	virtual void NativeTick(const FGeometry& MyGeometry, float InDeltaTime) override;
	virtual FReply NativeOnKeyDown(const FGeometry& InGeometry, const FKeyEvent& InKeyEvent) override;
	virtual FReply NativeOnMouseButtonDown(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) override;
	virtual FReply NativeOnMouseButtonUp(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) override;
	virtual FReply NativeOnMouseMove(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) override;
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

	void BuildTree();
	void FillBanner();
	void FillLoadout();
	void FillArmoury();
	void FillTabs();
	void FillHints();
	void FillInspect();
	void FillWeaponInspect(const FSOWeaponInstance& W);
	void FillArmorInspect(const FSOArmorInstance& A);
	void FillMeleeInspect(const FSOMeleeStyle& Style, FName Id);
	/** The six attributes; with a piece, what wearing it would change. */
	void FillAttributes(const FSOArmorInstance* TryOn);
	void FillQuickLook(USOInventoryTile* Tile);
	void ShowUpgrade(const FString& Uid);
	/** Shows or hides the inspect panel's buttons (nothing to act on: hidden). */
	void SetActions(bool bShow);
	/** Chooses an item of the open list (the card lit, the inspect panel and the stand-in follow). */
	void Choose(const FString& Key);
	FSOTileInfo WeaponTile(const FSOWeaponInstance& W, bool bSlot) const;
	FSOTileInfo ArmorTile(const FSOArmorInstance& A, bool bSlot) const;
	FString ShownKey() const;
	bool IsWeaponSlot(const FString& SlotKey) const { return SlotKey.Len() == 1 && FChar::IsDigit(SlotKey[0]); }
	bool IsArmourSlot(const FString& SlotKey) const;
	/** Moves the armoury one tab left or right (from the loadout too). */
	void StepTab(int32 Step);
	/** Moves the choice in the open list up or down. */
	void StepList(int32 Step);
	/** Shows the chosen gun / style / piece on the stand-in. */
	void SyncPreview();
	/** The panels slide and fade in after a change of view. */
	void Animate();
	void ApplyFocus();
	TArray<USOInventoryTile*> ColumnTiles(int32 Column) const;
	/** Places everything for the screen's width in its own units: wider than 2200 the layout keeps to a frame of 2200
	 *  in the middle; narrower than 1650 the attribute column gives way to the character. */
	void UpdateLayout(float Width);

	UPROPERTY(Transient)
	TObjectPtr<USOInventoryComponent> Inventory;

	UPROPERTY(Transient)
	TObjectPtr<USOCharacterPreview> Preview;

	UPROPERTY(Transient)
	TObjectPtr<UCanvasPanel> Root;

	UPROPERTY(Transient)
	TObjectPtr<UImage> PreviewImage;

	/** The banner: the name, the level line, the level's bar, the body; the currencies; the power. */
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

	/** The left and right panels (the loadout's columns, or an armoury's list and its inspect panel). */
	UPROPERTY(Transient)
	TObjectPtr<UVerticalBox> LeftPanel;

	UPROPERTY(Transient)
	TObjectPtr<UVerticalBox> RightPanel;

	UPROPERTY(Transient)
	TObjectPtr<UVerticalBox> AttributeColumn;

	/** A hovered loadout card's quick look, beside it. */
	UPROPERTY(Transient)
	TObjectPtr<UBorder> QuickLook;

	UPROPERTY(Transient)
	TObjectPtr<UHorizontalBox> TabRow;

	UPROPERTY(Transient)
	TObjectPtr<UHorizontalBox> HintRow;

	/** An armoury's list (its cards, in order) and where it was scrolled to. */
	UPROPERTY(Transient)
	TObjectPtr<UScrollBox> ListScroll;

	UPROPERTY(Transient)
	TArray<TObjectPtr<USOInventoryTile>> ListTiles;

	/** The inspect panel (built once, put in the right panel by an armoury): its content (scrolls), its buttons. */
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
	TObjectPtr<UButton> LockButton;

	UPROPERTY(Transient)
	TObjectPtr<UButton> DismantleButton;

	UPROPERTY(Transient)
	TObjectPtr<UButton> UpgradeButton;

	UPROPERTY(Transient)
	TObjectPtr<UTextBlock> EquipLabel;

	UPROPERTY(Transient)
	TObjectPtr<UTextBlock> LockLabel;

	UPROPERTY(Transient)
	TObjectPtr<UTextBlock> DismantleLabel;

	UPROPERTY(Transient)
	TObjectPtr<UTextBlock> UpgradeLabel;

	/** What UpdateLayout moves. */
	UPROPERTY(Transient)
	TObjectPtr<UWidget> BannerWidget;

	UPROPERTY(Transient)
	TObjectPtr<UWidget> BannerRule;

	UPROPERTY(Transient)
	TObjectPtr<UWidget> BannerLit;

	UPROPERTY(Transient)
	TObjectPtr<UWidget> FooterRule;

	UPROPERTY(Transient)
	TObjectPtr<UWidget> DragHint;

	FString OpenSlotId;
	FString LastArmourSlot = TEXT("head");
	int32 FocusColumn = 0;
	int32 FocusRow = 0;
	/** The highlight shows (the keyboard or the pad moved it; the mouse takes over on a hover). */
	bool bKeyFocus = false;
	/** Turning the character: the right stick's deflection, the spin a drag leaves behind (degrees a second). */
	float StickYaw = 0.0f;
	float SpinVelocity = 0.0f;
	double LastDragTime = 0.0;
	float LaidOutWidth = 0.0f;
	FString SelectedKey;
	FString HoverKey;
	FString QuickKey;
	float ListOffset = 0.0f;
	double DismantleArmedAt = -100.0;
	bool bDragging = false;
	/** The panels' slide in (0 just changed .. 1 settled). */
	float Arrive = 1.0f;
	FDelegateHandle ChangedHandle;
};
