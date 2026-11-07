#pragma once

#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "SOHUD.generated.h"

struct FSOProjectile;
class USOInventoryComponent;
class USOInventoryWidget;

/**
 * The combat HUD drawn on the canvas (the CommonUI HUD replaces it later): spread-sized crosshair, hit markers,
 * ammo, health + shield, reload progress, bars over hurt creatures, the downed / respawn message, the three weapon
 * slots, the loot feed, the interact prompt and the scope picture. Opens the inventory screen (USOInventoryWidget).
 */
UCLASS()
class SOUI_API ASOHUD : public AHUD
{
	GENERATED_BODY()

public:
	ASOHUD();

	/** Matches ASOGameMode::RespawnDelay for the countdown. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|HUD")
	float RespawnDelay = 4.0f;

	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
	virtual void DrawHUD() override;

	/** Opens or closes the inventory screen. */
	void ToggleInventory();
	void ToggleMap();
	bool IsMapOpen() const { return MapWidget != nullptr; }
	bool IsInventoryOpen() const { return InventoryWidget != nullptr; }
	USOInventoryWidget* GetInventoryWidget() const { return InventoryWidget; }

private:
	void OnRoundHit(const FSOProjectile& Round, const FHitResult& Hit, float Damage);
	void DrawBar(float X, float Y, float W, float H, float Fraction, const FLinearColor& Color);
	void DrawScope(float W, float H);
	void BindInventory();
	void OnFeed(const FString& Text, const FLinearColor& Color);

	struct FFeedLine
	{
		FString Text;
		FLinearColor Color;
		float Time;
	};
	TArray<FFeedLine> FeedLines;

	UPROPERTY(Transient)
	TObjectPtr<USOInventoryWidget> InventoryWidget;

	UPROPERTY(Transient)
	TObjectPtr<class USOMapWidget> MapWidget;

	/** The mini-map (top left): the area's map picture round the player, north up, the important places, you. */
	void DrawMinimap(float S);

	TWeakObjectPtr<USOInventoryComponent> FeedInventory;
	FDelegateHandle FeedHandle;
	TWeakObjectPtr<APawn> BoundPawn;

	float LastHitTime = -100.0f;
	float LastDamageTime = -100.0f;
	bool bLastDamageHealth = false;
	float LastHealth = -1.0f;
	float LastShield = -1.0f;
	bool bLastHitCrit = false;
	bool bLastHitKill = false;
	FDelegateHandle HitHandle;
};
