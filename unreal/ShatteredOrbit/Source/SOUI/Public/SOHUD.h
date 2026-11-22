#pragma once

#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "SOCombatCharacter.h"
#include "SOInventoryComponent.h"
#include "SOHUD.generated.h"

namespace SOHudPaint
{
	struct FPainter;
	struct FGlass;
	struct FHudAudit;
}

struct FSOProjectile;
class USOInventoryWidget;
class UTexture2D;

/** Where one of the HUD's elements sits and how big it is, over its designed place: every element is adjustable on
 *  its own (the owner's brief, 2026-11-21: "make all HUD elements independently adjustable"). The offset is in
 *  pixels at 1080 lines and scales with the screen; the scale is about the element's own anchor. */
USTRUCT(BlueprintType)
struct FSOHudElementLayout
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|HUD")
	FVector2D Offset = FVector2D::ZeroVector;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|HUD")
	float Scale = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|HUD")
	bool bVisible = true;
};

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

	/** Each element's place and size over its design (see FSOHudElementLayout). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|HUD|Layout")
	FSOHudElementLayout MinimapLayout;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|HUD|Layout")
	FSOHudElementLayout CompassLayout;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|HUD|Layout")
	FSOHudElementLayout ObjectiveLayout;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|HUD|Layout")
	FSOHudElementLayout ConditionsLayout;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|HUD|Layout")
	FSOHudElementLayout TrackedLayout;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|HUD|Layout")
	FSOHudElementLayout ItemsLayout;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|HUD|Layout")
	FSOHudElementLayout VitalsLayout;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|HUD|Layout")
	FSOHudElementLayout AbilitiesLayout;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|HUD|Layout")
	FSOHudElementLayout WeaponLayout;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|HUD|Layout")
	FSOHudElementLayout InteractLayout;

	/** Console (not in a shipping build): moves or scales one element (minimap, compass, objective, conditions,
	 *  tracked, items, vitals, abilities, weapon, interact) by DX, DY px at 1080 lines and Scale; "reset" puts all back. */
	UFUNCTION(Exec)
	void SOHudLayout(FName Element, float DX = 0.0f, float DY = 0.0f, float Scale = 1.0f);

	/** Console (not in a shipping build): the layout audit on or off: every overlap of words, pictures and glass is
	 *  logged as HUDOVERLAP while it runs. Also on with -SOHudAudit on the command line. */
	UFUNCTION(Exec)
	void SOHudAudit(int32 On);

	/** The capture series: the held gun's panel shows this name and count instead of the gun's (a long name, a big
	 *  magazine); an empty name puts the gun's own back. */
	void SetDebugWeapon(const FString& Name, int32 Mag, int32 Reserve);

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

	/** This player was hurt from somewhere (ASOCombatCharacter::OnDamagedFrom, on this machine; the capture series
	 *  calls it too): a mark on the ring round the crosshair, pointing the way it came from. */
	void OnDamagedFrom(const FVector& From, bool bShield, float Amount);
	/** Every element comes in from its own edge, a moment apart (back from the armoury or the map, a new body). */
	void ArriveAll(float Now);
	/** Where on the ring round the crosshair a blow from From is marked, seen from Eye looking along LookYaw: radians on
	 *  the screen (x right, y down), so straight ahead is up (-pi/2) and behind is down. */
	static float HitRingAngle(const FVector& Eye, float LookYaw, const FVector& From);

	/** The glass painter for one draw function: shapes on M_HUDGlass over what the painter P has drawn so far. */
	SOHudPaint::FGlass MakeGlass(SOHudPaint::FPainter& P, float S);

	/** The audit while it is on (every FType and FGlass is given it), else null. */
	SOHudPaint::FHudAudit* AuditPtr() const;

private:
	/** A picture (a gun's icon): DrawTexture, noted to the audit. */
	void Picture(UTexture2D* Tex, float X, float Y, float W, float H, float Alpha, const FString& Name);

	TSharedPtr<SOHudPaint::FHudAudit> Audit;
	bool bAuditing = false;
	bool bAuditLooked = false;
	float AuditLoggedAt = -100.0f;
	TArray<FString> AuditLast;

	FString DebugWeaponName;
	int32 DebugMag = -1;
	int32 DebugReserve = -1;

	/** The screen the fixed elements and the creatures' plates hold this frame and held last frame: what rises from
	 *  the world (a damage number) is laid clear of it. */
	TArray<FBox2D> Reserved;
	TArray<FBox2D> ReservedLast;
	FVector2D ElementOffset = FVector2D::ZeroVector;
	void Reserve(float X, float Y, float W, float H) { Reserved.Add(FBox2D(FVector2D(X, Y) + ElementOffset, FVector2D(X + W, Y + H) + ElementOffset)); }

	/** Where everything sits: the screen, the scale (1 at 1080 lines) and the frame the corners keep to on a wide
	 *  screen (2200 units at most, in the middle, as the armoury). */
	struct FLayout
	{
		float W = 0.0f, H = 0.0f, S = 1.0f;
		float X0 = 0.0f, X1 = 0.0f;   // the frame's left and right edges
		float CX = 0.0f;              // the screen's middle
		float Now = 0.0f;
	};

	/** Draws one element in its own layout: moved by its offset (the canvas carried with it, so everything it draws
	 *  moves together), its sizes scaled, named to the audit. */
	void DrawElement(const FLayout& L, const FSOHudElementLayout& E, const TCHAR* Name, TFunctionRef<void(const FLayout&)> Draw);

	/** A round of this player's went in (ASOCombatCharacter::OnHitConfirmed: on this machine, host or joined). */
	void OnHitConfirmed(bool bCrit, bool bKilled);
	void OnHitReported(const FSOHitReport& Report);
	/** The ring round the crosshair: an arc toward each place this player was hurt from, fading. */
	void DrawHitRing(const FLayout& L);
	/** RELOAD under the crosshair when the gun is empty (not part of the weapon panel: it stays at the crosshair
	 *  however the panel is moved or comes in). */
	void DrawEmptyWord(const FLayout& L);
	/** An element comes in again (a short way, from its own edge) when what it shows changes (Key). */
	void Arrive(const TCHAR* Name, const FString& Key);
	void BindInventory();
	void OnFeed(const FString& Text, const FLinearColor& Color);
	void OnFeedItem(const FSOFeedItem& Item);
	void OnReward(ESORewardKind Kind, int32 Amount);
	void OnLevelUp(int32 NewLevel);
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
	/** The loop's beats (the owner, 2026-11-20): what a kill or a pickup paid, popping up by the crosshair; the level
	 *  reached, announced in the upper middle; an elite seen for the first time, named under the compass. */
	void DrawRewards(const FLayout& L);
	void DrawLevelUp(const FLayout& L);
	void DrawEliteIntro(const FLayout& L);
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

	/** A damage number: where the blow landed, how much, what kind, when; pellets of one shot add up into one. Each
	 *  keeps the place it was given on the screen (a lane clear of the others) so numbers never lie on each other. */
	struct FDamageNumber
	{
		FVector Point;
		float Amount = 0.0f;
		uint8 Kind = 0;   // 0 normal, 1 shield, 2 precision, 3 critical
		bool bKilled = false;
		float Time = 0.0f;
		float Drift = 0.0f;
		float Lift = 0.0f;      // px it was moved up to clear another number (kept while it lives)
		float Side = 0.0f;      // px it was moved sideways
		bool bLaned = false;
	};
	TArray<FDamageNumber> DamageNumbers;

	UPROPERTY(Transient)
	TObjectPtr<USOInventoryWidget> InventoryWidget;

	UPROPERTY(Transient)
	TObjectPtr<class USOMapWidget> MapWidget;

	/** The glass (M_HUDGlass): its base, and a dynamic instance per shape drawn this frame, reused next frame. */
	UPROPERTY(Transient)
	TObjectPtr<class UMaterialInterface> GlassBase;
	UPROPERTY(Transient)
	TArray<TObjectPtr<class UMaterialInstanceDynamic>> GlassPool;
	int32 GlassUsed = 0;
	bool bGlassLooked = false;
	/** A new player's first start: the character builder was opened by itself (once). */
	bool bCreatorOffered = false;

	/** The guns' pictures (the armoury's icons), by archetype, held while the HUD lives. */
	UPROPERTY(Transient)
	TMap<FName, TObjectPtr<UTexture2D>> Icons;

	TWeakObjectPtr<USOInventoryComponent> FeedInventory;
	FDelegateHandle FeedHandle;
	FDelegateHandle FeedItemHandle;
	FDelegateHandle RewardHandle;
	FDelegateHandle LevelHandle;

	/** A reward as it came in: xp, credits or alloy; one kind within a moment adds up into one popup. */
	struct FRewardPop
	{
		uint8 Kind = 0;
		int32 Amount = 0;
		int32 Lane = 0;
		float Time = 0.0f;
		float Bump = 0.0f;
	};
	TArray<FRewardPop> Rewards;
	float LevelUpAt = -100.0f;
	int32 LevelUpTo = 0;
	float XpShown = -1.0f;   // the level bar's shown fill, eased toward the real one: a kill is SEEN to fill it
	float HudDt = 0.0f;
	float LastFrameTime = 0.0f;
	/** A kill confirmed: the marker bursts; kills within a few seconds of each other count up beside it. */
	float KillAt = -100.0f;
	int32 KillStreak = 0;
	/** The elites this player has been told of, and the one being announced. */
	TSet<TWeakObjectPtr<const AActor>> Introduced;
	float EliteAt = -100.0f;
	FString EliteName;
	int32 EliteLevel = 1;
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
	FDelegateHandle DamagedHandle;
	struct FDamageMark
	{
		FVector From = FVector::ZeroVector;
		float At = 0.0f;
		bool bShield = false;
		float Amount = 0.0f;
	};
	TArray<FDamageMark> DamageMarks;
	/** Each element's arrival (when it began, how far it comes from, px at 1080 lines) and what it showed. */
	struct FArrival
	{
		float At = 0.0f;
		float Dist = 56.0f;
	};
	TMap<FName, FArrival> Arrivals;
	TMap<FName, FString> ArriveKeys;
	bool bWasScreens = true;
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
