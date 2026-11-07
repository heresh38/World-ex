#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "SOInventoryWidget.generated.h"

class UBorder;
class UButton;
class UScrollBox;
class UTextBlock;
class UVerticalBox;
class USOInventoryComponent;
class USOInventoryWidget;
struct FSOWeaponInstance;

/** One weapon in a slot column: rarity stripe, name, archetype, power, NEW / locked / equipped marks. */
UCLASS()
class SOUI_API USOWeaponCardWidget : public UUserWidget
{
	GENERATED_BODY()

public:
	void Setup(USOInventoryWidget* InScreen, const FSOWeaponInstance& Weapon, bool bEquipped, bool bSelected);

	FString Uid;

protected:
	virtual TSharedRef<SWidget> RebuildWidget() override;

	UFUNCTION()
	void OnClicked();

	UFUNCTION()
	void OnHovered();

	UPROPERTY(Transient)
	TObjectPtr<USOInventoryWidget> Screen;

	UPROPERTY(Transient)
	TObjectPtr<UButton> Button;

	FString Title, Sub, Tags;
	FLinearColor Rarity = FLinearColor::White;
	int32 Power = 0;
	bool bEquippedCard = false;
	bool bSelectedCard = false;
};

/**
 * The inventory screen (I / Tab / View): every owned copy in three slot columns (Primary, Special, Heavy), a detail
 * panel for the hovered or selected copy (stat bars against the equipped copy of its slot, perks, sight, roll
 * quality, source) and the actions Equip (E), Lock (L) and Dismantle (X, twice). Credits, alloy, level and the vault
 * count across the top. Built in C++ (no widget blueprint); mouse, keyboard and gamepad focus navigation.
 */
UCLASS()
class SOUI_API USOInventoryWidget : public UUserWidget
{
	GENERATED_BODY()

public:
	void Bind(USOInventoryComponent* InInventory);
	void Refresh();
	void Select(const FString& Uid);
	void Preview(const FString& Uid);
	void Close();

	/** Called when the screen wants to close (the HUD restores game input). */
	TFunction<void()> OnClose;

protected:
	virtual TSharedRef<SWidget> RebuildWidget() override;
	virtual void NativeDestruct() override;
	virtual FReply NativeOnKeyDown(const FGeometry& InGeometry, const FKeyEvent& InKeyEvent) override;

	UFUNCTION()
	void OnEquip();

	UFUNCTION()
	void OnLock();

	UFUNCTION()
	void OnDismantle();

	void BuildTree();
	void FillDetails();
	const FSOWeaponInstance* Shown() const;

	UPROPERTY(Transient)
	TObjectPtr<USOInventoryComponent> Inventory;

	UPROPERTY(Transient)
	TArray<TObjectPtr<UScrollBox>> Columns;

	UPROPERTY(Transient)
	TArray<TObjectPtr<UTextBlock>> ColumnTitles;

	UPROPERTY(Transient)
	TObjectPtr<UTextBlock> Header;

	UPROPERTY(Transient)
	TObjectPtr<UVerticalBox> Details;

	UPROPERTY(Transient)
	TObjectPtr<UButton> EquipButton;

	UPROPERTY(Transient)
	TObjectPtr<UButton> LockButton;

	UPROPERTY(Transient)
	TObjectPtr<UButton> DismantleButton;

	UPROPERTY(Transient)
	TObjectPtr<UTextBlock> LockLabel;

	UPROPERTY(Transient)
	TObjectPtr<UTextBlock> DismantleLabel;

	FString SelectedUid;
	FString PreviewUid;
	double DismantleArmedAt = -100.0;
	FDelegateHandle ChangedHandle;
};
