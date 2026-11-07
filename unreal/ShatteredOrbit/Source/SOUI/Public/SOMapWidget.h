#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "SOMapWidget.generated.h"

class ASOMapPoint;
class UCanvasPanel;
class UImage;
class UTextBlock;
class UVerticalBox;

/** A marker on the map screen: click a fast-travel point to go there, an area gate to travel to that area. */
UCLASS()
class SOUI_API USOMapMarker : public UUserWidget
{
	GENERATED_BODY()

public:
	void Setup(class USOMapWidget* InScreen, ASOMapPoint* InPoint);

protected:
	virtual TSharedRef<SWidget> RebuildWidget() override;

	UFUNCTION()
	void OnClicked();

	UFUNCTION()
	void OnHovered();

	UPROPERTY(Transient)
	TObjectPtr<class USOMapWidget> Screen;

	TWeakObjectPtr<ASOMapPoint> Point;
};

/** An area button (other levels). */
UCLASS()
class SOUI_API USOAreaButton : public UUserWidget
{
	GENERATED_BODY()

public:
	void Setup(class USOMapWidget* InScreen, int32 InArea, bool bInCurrent) { Screen = InScreen; Area = InArea; bCurrent = bInCurrent; }

protected:
	virtual TSharedRef<SWidget> RebuildWidget() override;

	UFUNCTION()
	void OnClicked();

	UPROPERTY(Transient)
	TObjectPtr<class USOMapWidget> Screen;

	int32 Area = 0;
	bool bCurrent = false;
};

/**
 * The map screen (M / D-pad down): the area's map picture with every important place (ASOMapPoint) in its kind's colour,
 * the player's position, a legend, and quick travel: click a fast-travel point to go there, an area gate or one of
 * the areas on the right to travel to another area. Built in C++ (no widget blueprint).
 */
UCLASS()
class SOUI_API USOMapWidget : public UUserWidget
{
	GENERATED_BODY()

public:
	void Close();
	void TravelTo(ASOMapPoint* Point);
	void TravelToArea(int32 Area);
	void ShowInfo(ASOMapPoint* Point);

	TFunction<void()> OnClose;

	/** Side of the map picture on screen (slate units). */
	static constexpr float MapSize = 860.0f;

protected:
	virtual TSharedRef<SWidget> RebuildWidget() override;
	virtual void NativeTick(const FGeometry& MyGeometry, float InDeltaTime) override;
	virtual FReply NativeOnKeyDown(const FGeometry& InGeometry, const FKeyEvent& InKeyEvent) override;

	void BuildTree();

	UPROPERTY(Transient)
	TObjectPtr<UCanvasPanel> Markers;

	UPROPERTY(Transient)
	TObjectPtr<UImage> MapImage;

	UPROPERTY(Transient)
	TObjectPtr<UImage> PlayerMark;

	UPROPERTY(Transient)
	TObjectPtr<UTextBlock> InfoTitle;

	UPROPERTY(Transient)
	TObjectPtr<UTextBlock> InfoText;
};
