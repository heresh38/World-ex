#pragma once

#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "SOCombatCharacter.h"
#include "SOInventoryComponent.h"
#include "SOHUD.generated.h"

struct FSOProjectile;
class USOInventoryWidget;
class UTexture2D;

/**
 * The combat HUD, drawn on the canvas (the owner's two reference screens of 2026-11-20, `art/reference/ui/hud_*.webp`;
 * the words and glyphs are ours). Night-blue glass, cyan lines, gold for what matters, as the armoury. Top left the
 * round mini-map and the area's name; top centre the compass strip and the objective banner; top right the conditions
 * on the player with their timers, the tracked objectives and the NEW ITEM card; over a creature its level, name and
 * bar; bottom left the kit's emblem with the shield and health bars; bottom centre the abilities and the ultimate's
 * meter; bottom right the three weapon cards and the held gun's panel. Hit feedback: damage numbers at the hit, the
 * crosshair's four states (tight, moving, aiming, locked), loot beams by rarity, the screen's edge on a shield hit, low
 * health and an ability coming ready. Keeps every set's own scope glass, the Sarketh heat gauge, the boss bar, the
 * melee counters and the operation's banners. Opens the inventory screen (USOInventoryWidget) and the map.
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

	/** Shows a NEW ITEM card as if the gun had just come in (the capture series; a real one comes through the
	 *  inventory's OnFeedItem). */
	void ShowItemCard(const FSOFeedItem& Item);

	/** Shows a hit as if a round of the player's had landed there (the capture series). */
	void ShowHit(const FSOHitReport& Report);

private:
	/** Where everything sits: the screen, the scale (1 at 1080 lines) and the frame the corners keep to on a wide
	 *  screen (2200 units at most, in the middle, as the armoury). */
	struct FLayout
	{
		float W = 0.0f, H = 0.0f, S = 1.0f;
		float X0 = 0.0f, X1 = 0.0f;   // the frame's left and right edges
		float CX = 0.0f;              // the screen's middle
		float Now = 0.0f;
	};

	/** A round of this player's went in (ASOCombatCharacter::OnHitConfirmed: on this machine, host or joined). */
	void OnHitConfirmed(bool bCrit, bool bKilled);
	void OnHitReported(const FSOHitReport& Report);
	void BindInventory();
	void OnFeed(const FString& Text, const FLinearColor& Color);
	void OnFeedItem(const FSOFeedItem& Item);
	UTexture2D* IconOf(FName Archetype);

	void DrawMinimap(const FLayout& L);
	void DrawCompass(const FLayout& L);
	void DrawObjective(const FLayout& L);
	void DrawConditions(const FLayout& L);
	void DrawTracked(const FLayout& L);
	void DrawItemCards(const FLayout& L);
	void DrawCreatures(const FLayout& L);
	void DrawVitals(const FLayout& L);
	void DrawAbilities(const FLayout& L);
	void DrawWeapon(const FLayout& L);
	void DrawCrosshair(const FLayout& L);
	void DrawMelee(const FLayout& L);
	void DrawDamageNumbers(const FLayout& L);
	void DrawLootBeams(const FLayout& L);
	void DrawScreenEdge(const FLayout& L);
	void DrawInteract(const FLayout& L);
	void DrawDowned(const FLayout& L);
	void DrawScope(float W, float H);

	/** An operation (ASOOperation): the stage's title as it begins, the briefing and the radio, a marker on the goal,
	 *  the boss's health across the top, and the end screen with what every player earned. */
	void DrawOperation(const FLayout& L);

	/** A boss's health across the top: its name, a notch where each phase of its table begins, the phase's name,
	 *  why nothing hurts it (the shield) or that it reels. The operation's boss, or one met outside an operation. */
	void DrawBossBar(const class ASOEnemy* Boss, const FLayout& L);

	/** The AI debug view (console: SOAIDebug; not in a shipping build): over every creature within 60 m what its
	 *  brain is doing (state, awareness, target, cover, role flags, its kit's readiness), a line to its cover and to
	 *  where it last knew its target to be, and at the top what the brains cost. Brains run on the server only, so
	 *  a joined player sees nothing here. */
	void DrawAIDebug(float W, float H, float S);
	float AIDebugReadAt = 0.0f;
	int32 AIDebugThinks = 0;
	float AIDebugMs = 0.0f;

	struct FFeedLine
	{
		FString Text;
		FLinearColor Color;
		float Time;
	};
	TArray<FFeedLine> FeedLines;

	/** A NEW ITEM card: what came in and when. */
	struct FItemCard
	{
		FSOFeedItem Item;
		float Time = 0.0f;
	};
	TArray<FItemCard> ItemCards;

	/** A damage number: where the blow landed, how much, what kind, when; pellets of one shot add up into one. */
	struct FDamageNumber
	{
		FVector Point;
		float Amount = 0.0f;
		uint8 Kind = 0;   // 0 normal, 1 shield, 2 precision, 3 critical
		bool bKilled = false;
		float Time = 0.0f;
		float Drift = 0.0f;
	};
	TArray<FDamageNumber> DamageNumbers;

	UPROPERTY(Transient)
	TObjectPtr<USOInventoryWidget> InventoryWidget;

	UPROPERTY(Transient)
	TObjectPtr<class USOMapWidget> MapWidget;

	/** The guns' pictures (the armoury's icons), by archetype, held while the HUD lives. */
	UPROPERTY(Transient)
	TMap<FName, TObjectPtr<UTexture2D>> Icons;

	TWeakObjectPtr<USOInventoryComponent> FeedInventory;
	FDelegateHandle FeedHandle;
	FDelegateHandle FeedItemHandle;
	TWeakObjectPtr<APawn> BoundPawn;

	float LastHitTime = -100.0f;
	float LastDamageTime = -100.0f;
	bool bLastDamageHealth = false;
	float LastHealth = -1.0f;
	float LastShield = -1.0f;
	bool bLastHitCrit = false;
	bool bLastHitKill = false;
	FDelegateHandle HitHandle;
	FDelegateHandle HitReportHandle;
	TWeakObjectPtr<const ASOCombatCharacter> HitPawn;

	/** The abilities: which were ready last frame (a slot coming ready pulses), and when each last came ready. */
	bool bSlotWasReady[5] = { false, false, false, false, false };
	float SlotReadyAt[5] = { -100.0f, -100.0f, -100.0f, -100.0f, -100.0f };
	float UltimateReadyAt = -100.0f;
	bool bUltimateWasReady = false;

	/** Who the crosshair is on this frame (a hostile within 60 m), for the lock and its plate. */
	TWeakObjectPtr<const ASOCombatCharacter> Locked;
	float LockedAt = -100.0f;

	/** Where the next thing on the right goes (under the tracked panel: the cards, then the feed). */
	float RightFlowY = 0.0f;
};
