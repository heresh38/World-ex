#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "SOInventoryWidget.generated.h"

class ASceneCapture2D;
class APointLight;
class UBorder;
class UButton;
class UCanvasPanel;
class UImage;
class UScrollBox;
class UTextBlock;
class UTexture2D;
class UTextureRenderTarget2D;
class UVerticalBox;
class UWrapBox;
class USOInventoryComponent;
class USOInventoryWidget;
struct FSOArmorInstance;
struct FSOWeaponInstance;

/**
 * The picture of the player in the middle of the loadout screen: a stand-in character of its own (always there,
 * whatever the pawn is doing, dead or alive), high above the world, wearing the inventory's outfit and holding the gun
 * in hand, seen by a scene capture that draws only it (transparent background), lit by its own key and rim lights,
 * turned by dragging.
 */
UCLASS()
class SOUI_API USOCharacterPreview : public UObject
{
	GENERATED_BODY()

public:
	void Start(APlayerController* Player);
	/** Dresses and arms the stand-in like the inventory says (cheap when nothing changed). */
	void Sync(class USOInventoryComponent* Inventory);
	void Stop();
	void Tick(float DeltaTime);
	APawn* GetMannequin() const { return Subject.Get(); }
	UTextureRenderTarget2D* GetTarget() const { return Target; }

	/** Degrees round the character (0 = from the front). */
	float Yaw = 25.0f;

private:
	UPROPERTY(Transient)
	TObjectPtr<UTextureRenderTarget2D> Target;

	TWeakObjectPtr<ASceneCapture2D> Capture;
	TWeakObjectPtr<APointLight> Key;
	TWeakObjectPtr<APointLight> Rim;
	TWeakObjectPtr<APawn> Subject;
	FString ShownWeapon;
	void UpdateShowList();
	/** r.PostProcessing.PropagateAlpha before the preview turned it on (the picture's background is transparent). */
	int32 PreviousAlpha = -1;
};

/** One square on the loadout screen: a slot (what is worn / held there) or an owned item in a slot's grid. */
USTRUCT()
struct FSOTileInfo
{
	GENERATED_BODY()

	/** wslot | aslot | weapon | armor */
	FName Kind;
	/** slot id (wslot 0..2, aslot head..feet) or the item's uid */
	FString Key;
	UPROPERTY(Transient)
	TObjectPtr<UTexture2D> Icon = nullptr;
	FLinearColor Rarity = FLinearColor::White;
	FString Title;
	FString Sub;
	FString Badge;
	int32 Power = 0;
	bool bActive = false;
	bool bEquipped = false;
	bool bNew = false;
	bool bWide = false;
	FVector2D Size = FVector2D(110.0f, 110.0f);
};

UCLASS()
class SOUI_API USOInventoryTile : public UUserWidget
{
	GENERATED_BODY()

public:
	void Setup(USOInventoryWidget* InScreen, const FSOTileInfo& InInfo) { Screen = InScreen; Info = InInfo; }
	const FSOTileInfo& GetInfo() const { return Info; }

protected:
	virtual TSharedRef<SWidget> RebuildWidget() override;

	UFUNCTION()
	void OnClicked();

	UFUNCTION()
	void OnHovered();

	UFUNCTION()
	void OnUnhovered();

	UPROPERTY(Transient)
	TObjectPtr<USOInventoryWidget> Screen;

	UPROPERTY(Transient)
	FSOTileInfo Info;
};

/**
 * The loadout screen (I / Tab / View). Left: the three weapon slots and the outer layers (coat, rig); right: the
 * armour slots (head, chest, arms, legs, feet); middle: the player as they stand, turnable by dragging. A slot opens
 * its grid of everything owned for it (icon squares in rarity colours, NEW and locked marks) next to the slot, with
 * the hovered or selected item's details: stats against the equipped one, perks, armour, and the actions Equip (E),
 * Lock (L) and Dismantle (X, twice). Power, armour, level, credits and alloy across the top; the body (male / female)
 * under the character. Built in C++ (no widget blueprint).
 */
UCLASS()
class SOUI_API USOInventoryWidget : public UUserWidget
{
	GENERATED_BODY()

public:
	void Bind(USOInventoryComponent* InInventory);
	void Refresh();
	void Close();

	/** A tile was clicked / hovered (USOInventoryTile). */
	void OnTile(const FSOTileInfo& Tile);
	void OnTileHover(const FSOTileInfo& Tile, bool bHover);

	/** Opens a slot's grid ("0".."2" weapons, head / top / vest / outer / hands / legs / feet armour; empty = none). */
	void OpenSlot(const FString& SlotId);
	const FString& GetOpenSlot() const { return OpenSlotId; }

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

	UFUNCTION()
	void OnEquip();

	UFUNCTION()
	void OnLock();

	UFUNCTION()
	void OnDismantle();

	UFUNCTION()
	void OnBody();

	void BuildTree();
	void FillColumns();
	void FillFlyout();
	void FillDetails();
	void FillWeaponDetails(const FSOWeaponInstance& W);
	void FillArmorDetails(const FSOArmorInstance& A);
	FSOTileInfo WeaponTile(const FSOWeaponInstance& W, bool bSlot) const;
	FSOTileInfo ArmorTile(const FSOArmorInstance& A, bool bSlot) const;
	FString ShownKey() const;
	bool IsWeaponSlot(const FString& SlotKey) const { return SlotKey.Len() == 1 && FChar::IsDigit(SlotKey[0]); }

	UPROPERTY(Transient)
	TObjectPtr<USOInventoryComponent> Inventory;

	UPROPERTY(Transient)
	TObjectPtr<USOCharacterPreview> Preview;

	UPROPERTY(Transient)
	TObjectPtr<UCanvasPanel> Root;

	UPROPERTY(Transient)
	TObjectPtr<UVerticalBox> LeftColumn;

	UPROPERTY(Transient)
	TObjectPtr<UVerticalBox> RightColumn;

	UPROPERTY(Transient)
	TObjectPtr<UImage> PreviewImage;

	UPROPERTY(Transient)
	TObjectPtr<UBorder> Flyout;

	UPROPERTY(Transient)
	TObjectPtr<UWrapBox> Grid;

	UPROPERTY(Transient)
	TObjectPtr<UTextBlock> GridTitle;

	UPROPERTY(Transient)
	TObjectPtr<UVerticalBox> Details;

	UPROPERTY(Transient)
	TObjectPtr<UTextBlock> PowerText;

	UPROPERTY(Transient)
	TObjectPtr<UTextBlock> StatsText;

	UPROPERTY(Transient)
	TObjectPtr<UTextBlock> BodyLabel;

	UPROPERTY(Transient)
	TObjectPtr<UButton> EquipButton;

	UPROPERTY(Transient)
	TObjectPtr<UButton> LockButton;

	UPROPERTY(Transient)
	TObjectPtr<UButton> DismantleButton;

	UPROPERTY(Transient)
	TObjectPtr<UTextBlock> EquipLabel;

	UPROPERTY(Transient)
	TObjectPtr<UTextBlock> LockLabel;

	UPROPERTY(Transient)
	TObjectPtr<UTextBlock> DismantleLabel;

	FString OpenSlotId;
	FString SelectedKey;
	FString HoverKey;
	double DismantleArmedAt = -100.0;
	bool bDragging = false;
	FDelegateHandle ChangedHandle;
};
