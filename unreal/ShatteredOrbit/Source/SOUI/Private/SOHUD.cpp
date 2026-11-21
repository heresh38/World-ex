#include "SOHUD.h"

#include "SOHUDPaint.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/Font.h"
#include "Engine/Texture2D.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "SOCharacter.h"
#include "CanvasItem.h"
#include "GameFramework/PlayerController.h"
#include "SOInventoryComponent.h"
#include "SOInventoryWidget.h"
#include "SOMapWidget.h"
#include "SOMap.h"
#include "SOBoss.h"
#include "SODifficulty.h"
#include "SOEnemy.h"
#include "SOEnemyAIController.h"
#include "HAL/IConsoleManager.h"
#include "SOOperation.h"
#include "GameFramework/PlayerState.h"
#include "Engine/TextureRenderTarget2D.h"
#include "SOLootActors.h"
#include "SOLootLibrary.h"
#include "SOLootTypes.h"
#include "SOMelee.h"
#include "SOCombatCharacter.h"
#include "SOCombatStatics.h"
#include "SOProgression.h"
#include "SOProjectileSubsystem.h"
#include "SOSound.h"
#include "SOWeapon.h"
#include "SOWeaponData.h"

using namespace SOHudPaint;

namespace
{
	/** The conditions the HUD shows on the player, in the order they are laid: tag, word, colour. */
	struct FConditionLook
	{
		const FNativeGameplayTag* Tag;
		const TCHAR* Word;
		FLinearColor Color;
		int32 Glyph;
	};
	const FConditionLook Conditions[] = {
		{ &SOTags::Status_Guard, TEXT("Braced"), FLinearColor(0.45f, 0.9f, 1.0f), 0 },
		{ &SOTags::Status_Haste, TEXT("Haste"), FLinearColor(0.75f, 0.55f, 1.0f), 5 },
		{ &SOTags::Status_Burn, TEXT("Burning"), FLinearColor(1.0f, 0.5f, 0.12f), 1 },
		{ &SOTags::Status_Slow, TEXT("Slowed"), FLinearColor(0.45f, 0.72f, 1.0f), 2 },
		{ &SOTags::Status_Stagger, TEXT("Staggered"), FLinearColor(1.0f, 0.88f, 0.4f), 3 },
		{ &SOTags::Status_Jam, TEXT("Jammed"), FLinearColor(1.0f, 0.35f, 0.3f), 4 },
		{ &SOTags::Status_Suppressed, TEXT("Under fire"), FLinearColor(1.0f, 0.62f, 0.3f), 6 },
	};

	/** A condition's mark (geometry, R px): a chevron for the brace, a flame, a down chevron, a zigzag, a cross, a
	 *  double chevron, three dashes. */
	void ConditionGlyph(FPainter& P, int32 Glyph, const FVector2D& C, float R, const FLinearColor& Col, float T)
	{
		switch (Glyph)
		{
		case 0: // the brace: a chevron over a bar
			P.Stroke({ C + FVector2D(-R, R * 0.3f), C + FVector2D(0, -R * 0.7f), C + FVector2D(R, R * 0.3f) }, Col, T, false);
			P.Segment(C + FVector2D(-R * 0.6f, R * 0.85f), C + FVector2D(R * 0.6f, R * 0.85f), Col, T);
			break;
		case 1: // a flame: a leaf standing, a notch cut
			P.Fill({ C + FVector2D(0, -R), C + FVector2D(R * 0.75f, R * 0.1f), C + FVector2D(R * 0.35f, R), C + FVector2D(-R * 0.35f, R), C + FVector2D(-R * 0.75f, R * 0.1f) }, Col);
			P.Fill({ C + FVector2D(0, R * 0.05f), C + FVector2D(R * 0.3f, R * 0.55f), C + FVector2D(0, R), C + FVector2D(-R * 0.3f, R * 0.55f) }, A(FLinearColor::Black, 0.55f));
			break;
		case 2: // slowed: a chevron pointing down, twice
			P.Stroke({ C + FVector2D(-R, -R * 0.8f), C + FVector2D(0, -R * 0.1f), C + FVector2D(R, -R * 0.8f) }, Col, T, false);
			P.Stroke({ C + FVector2D(-R, R * 0.1f), C + FVector2D(0, R * 0.8f), C + FVector2D(R, R * 0.1f) }, Col, T, false);
			break;
		case 3: // staggered: a zigzag
			P.Stroke({ C + FVector2D(-R, -R * 0.6f), C + FVector2D(-R * 0.3f, R * 0.2f), C + FVector2D(R * 0.3f, -R * 0.4f), C + FVector2D(R, R * 0.6f) }, Col, T, false);
			break;
		case 4: // jammed: a cross
			P.Segment(C + FVector2D(-R * 0.75f, -R * 0.75f), C + FVector2D(R * 0.75f, R * 0.75f), Col, T);
			P.Segment(C + FVector2D(R * 0.75f, -R * 0.75f), C + FVector2D(-R * 0.75f, R * 0.75f), Col, T);
			break;
		case 5: // haste: two chevrons forward
			P.Stroke({ C + FVector2D(-R * 0.9f, -R * 0.7f), C + FVector2D(-R * 0.2f, 0), C + FVector2D(-R * 0.9f, R * 0.7f) }, Col, T, false);
			P.Stroke({ C + FVector2D(0.0f, -R * 0.7f), C + FVector2D(R * 0.7f, 0), C + FVector2D(0.0f, R * 0.7f) }, Col, T, false);
			break;
		default: // under fire: three dashes coming in
			for (int32 i = 0; i < 3; ++i)
			{
				const float Y = -R * 0.6f + i * R * 0.6f;
				P.Segment(C + FVector2D(-R * 0.9f, Y), C + FVector2D(R * (0.1f + i * 0.3f), Y), Col, T);
			}
			break;
		}
	}

	/** A slot's mark on its cell: the grenade a charge with its pin, the melee a blade, the class a shield, the
	 *  ultimate a four-pointed star. */
	void SlotGlyph(FPainter& P, ESOAbilitySlot Slot, const FVector2D& C, float R, const FLinearColor& Col, float T)
	{
		switch (Slot)
		{
		case ESOAbilitySlot::Grenade:
			P.Ring(C + FVector2D(0, R * 0.15f), R * 0.5f, R * 0.5f + T, Col, Col);
			P.Segment(C + FVector2D(0, -R * 0.35f), C + FVector2D(0, -R * 0.95f), Col, T);
			P.Segment(C + FVector2D(-R * 0.3f, -R * 0.95f), C + FVector2D(R * 0.3f, -R * 0.95f), Col, T);
			break;
		case ESOAbilitySlot::Melee:
			P.Segment(C + FVector2D(-R * 0.8f, R * 0.8f), C + FVector2D(R * 0.7f, -R * 0.7f), Col, T * 1.4f);
			P.Segment(C + FVector2D(-R * 0.25f, -R * 0.05f), C + FVector2D(0.05f * R, R * 0.25f), Col, T * 2.2f);
			P.Segment(C + FVector2D(-R * 0.55f, R * 0.25f), C + FVector2D(-R * 0.25f, R * 0.55f), Col, T);
			break;
		case ESOAbilitySlot::Class:
			P.Stroke({ C + FVector2D(-R * 0.8f, -R * 0.6f), C + FVector2D(0, -R * 0.85f), C + FVector2D(R * 0.8f, -R * 0.6f), C + FVector2D(R * 0.7f, R * 0.1f),
				C + FVector2D(0, R * 0.9f), C + FVector2D(-R * 0.7f, R * 0.1f) }, Col, T, true);
			P.Segment(C + FVector2D(0, -R * 0.4f), C + FVector2D(0, R * 0.35f), Col, T);
			break;
		case ESOAbilitySlot::Ultimate:
			P.Fill(Diamond(C, R * 0.28f, R * 0.95f), Col);
			P.Fill(Diamond(C, R * 0.95f, R * 0.28f), Col);
			break;
		default:
			P.Fill(Diamond(C, R * 0.5f, R * 0.5f), Col);
			break;
		}
	}

	/** The key under a slot (our bindings: G grenade, V melee, Q class, X ultimate). */
	const TCHAR* SlotKey(ESOAbilitySlot Slot)
	{
		switch (Slot)
		{
		case ESOAbilitySlot::Grenade: return TEXT("G");
		case ESOAbilitySlot::Melee: return TEXT("V");
		case ESOAbilitySlot::Class: return TEXT("Q");
		case ESOAbilitySlot::Ultimate: return TEXT("X");
		default: return TEXT("");
		}
	}

	/** The game's mark: a ring broken at its top right, a point at its heart (the broken orbit of the armoury's
	 *  backdrop). */
	void OrbitMark(FPainter& P, const FVector2D& C, float R, const FLinearColor& Col, float T)
	{
		P.Ring(C, R - T * 0.5f, R + T * 0.5f, Col, Col, FMath::DegreesToRadians(-40.0f), FMath::DegreesToRadians(250.0f), 48);
		P.Fill(Diamond(C, R * 0.28f, R * 0.28f), Col);
		P.Segment(C + FVector2D(FMath::Cos(FMath::DegreesToRadians(-60.0f)), FMath::Sin(FMath::DegreesToRadians(-60.0f))) * R * 1.15f,
			C + FVector2D(FMath::Cos(FMath::DegreesToRadians(-60.0f)), FMath::Sin(FMath::DegreesToRadians(-60.0f))) * R * 1.5f, Col, T);
	}

	/** Smooth in and out. */
	float Ease(float T) { T = FMath::Clamp(T, 0.0f, 1.0f); return T * T * (3.0f - 2.0f * T); }

	const FSORarityInfo* RarityOf(int32 Rarity)
	{
		const USOLootTables* Tables = USOLootLibrary::GetTables();
		return Tables ? &Tables->GetRarity(Rarity) : nullptr;
	}

	FLinearColor RarityColour(int32 Rarity)
	{
		const FSORarityInfo* R = RarityOf(Rarity);
		return R ? R->Color : Ink;
	}
}

/**
 * Every set (or, with no set, its class's family) looks through its own glass (the owner, 2026-11-15: "the zoomed in
 * screen should be unique to the weapon set like instead of a black screen it should be unique with the guns theme and
 * the crosshair too"): the window's shape, what stands round it, its rim, the reticle and the hip crosshair, all in the
 * set's light (the palette's glow, `Data/game_data.json` "palettes"). What the sight does is the same for all.
 */
namespace SOSightTheme
{
	enum class ETheme : uint8 { Kinetic, Light, Sarketh, Void, Living };

	ETheme Of(const USOWeaponData* D)
	{
		if (!D)
		{
			return ETheme::Kinetic;
		}
		if (D->SetId == TEXT("sarketh"))
		{
			return ETheme::Sarketh;
		}
		if (D->SetId == TEXT("void_requiem"))
		{
			return ETheme::Void;
		}
		switch (D->WeaponClass)
		{
		case ESOWeaponClass::Energy: return ETheme::Light;
		case ESOWeaponClass::Horror: return ETheme::Living;
		default: return ETheme::Kinetic;
		}
	}

	/** The set's light (its palette's glow; the tracer where a gun has no glow). */
	FLinearColor Glow(const USOWeaponData* D)
	{
		if (!D)
		{
			return FLinearColor(1.0f, 0.2f, 0.1f);
		}
		return D->GlowColor.A > 0.0f ? FLinearColor(D->GlowColor.R, D->GlowColor.G, D->GlowColor.B, 1.0f) : D->TracerColor;
	}

	/** Brighter for a reticle on a dark ground: the colour scaled so its brightest channel is 1. */
	FLinearColor Lit(const FLinearColor& C, float A)
	{
		const float M = FMath::Max3(C.R, C.G, C.B);
		const float K = M > KINDA_SMALL_NUMBER ? 1.0f / M : 1.0f;
		return FLinearColor(C.R * K, C.G * K, C.B * K, A);
	}

	/** The window's edge at angle A (radians, screen space: +Y down) for a window of size R. */
	float Radius(ETheme T, float A, float R, float Time)
	{
		switch (T)
		{
		case ETheme::Sarketh:
		{
			// the lozenge of their emblem, wider than tall, its points softened (a superellipse, p 1.35)
			const float Ax = R * 1.36f, By = R * 0.88f, P = 1.35f;
			const float Cx = FMath::Abs(FMath::Cos(A)) / Ax, Sy = FMath::Abs(FMath::Sin(A)) / By;
			return 1.0f / FMath::Pow(FMath::Pow(Cx, P) + FMath::Pow(Sy, P), 1.0f / P);
		}
		case ETheme::Void:
		{
			// a hexagon standing on a point
			const float Seg = UE_PI / 3.0f;
			const float L = FMath::Fmod(A + UE_PI * 2.0f + UE_PI / 2.0f, Seg) - Seg * 0.5f;
			return R * 1.02f * FMath::Cos(Seg * 0.5f) / FMath::Cos(L);
		}
		case ETheme::Living:
			// a membrane that breathes
			return R * (1.0f + 0.03f * FMath::Sin(5.0f * A + 0.8f * Time) + 0.018f * FMath::Sin(9.0f * A - 1.3f * Time)
				+ 0.012f * FMath::Sin(2.0f * A + 0.5f * Time));
		default:
			return R;
		}
	}

	struct FLook
	{
		FLinearColor Near, Far;      // what stands round the window: next to it, toward the screen's edge
		FLinearColor Rim;            // the window's frame
		float RimWidth = 3.0f;       // px at 1080
		FLinearColor Edge;           // the glass's tint at its edge, fading inward
		float EdgeDepth = 0.1f;      // of the window's size
	};

	FLook LookOf(ETheme T, const FLinearColor& G)
	{
		FLook L;
		switch (T)
		{
		case ETheme::Sarketh:
			// dark orange lacquer round the glass, a gold rim, the glass amber at its edge
			L.Near = FLinearColor(0.11f, 0.04f, 0.012f, 1.0f);
			L.Far = FLinearColor(0.018f, 0.007f, 0.003f, 1.0f);
			L.Rim = FLinearColor(0.95f, 0.62f, 0.22f, 1.0f);
			L.RimWidth = 4.0f;
			L.Edge = FLinearColor(G.R, G.G, G.B, 0.30f);
			L.EdgeDepth = 0.14f;
			break;
		case ETheme::Void:
			L.Near = FLinearColor(0.05f, 0.018f, 0.09f, 1.0f);
			L.Far = FLinearColor(0.012f, 0.004f, 0.025f, 1.0f);
			L.Rim = FLinearColor(0.78f, 0.74f, 0.86f, 1.0f);
			L.RimWidth = 2.5f;
			L.Edge = FLinearColor(G.R, G.G, G.B, 0.26f);
			L.EdgeDepth = 0.12f;
			break;
		case ETheme::Light:
			L.Near = FLinearColor(0.012f, 0.04f, 0.06f, 1.0f);
			L.Far = FLinearColor(0.003f, 0.01f, 0.018f, 1.0f);
			L.Rim = FLinearColor(0.16f, 0.2f, 0.24f, 1.0f);
			L.RimWidth = 5.0f;
			L.Edge = FLinearColor(G.R, G.G, G.B, 0.20f);
			L.EdgeDepth = 0.08f;
			break;
		case ETheme::Living:
			L.Near = FLinearColor(0.07f, 0.1f, 0.02f, 1.0f);
			L.Far = FLinearColor(0.012f, 0.02f, 0.004f, 1.0f);
			L.Rim = FLinearColor(0.2f, 0.12f, 0.1f, 1.0f);
			L.RimWidth = 9.0f;
			L.Edge = FLinearColor(G.R, G.G, G.B, 0.22f);
			L.EdgeDepth = 0.16f;
			break;
		default:
			L.Near = FLinearColor(0.012f, 0.012f, 0.012f, 1.0f);
			L.Far = FLinearColor::Black;
			L.Rim = FLinearColor(0.08f, 0.08f, 0.085f, 1.0f);
			L.RimWidth = 3.0f;
			L.Edge = FLinearColor(0.0f, 0.0f, 0.0f, 0.55f);
			L.EdgeDepth = 0.1f;
			break;
		}
		return L;
	}
}

ASOHUD::ASOHUD()
{
}

void ASOHUD::BeginPlay()
{
	Super::BeginPlay();
}

void ASOHUD::BindInventory()
{
	ASOCharacter* Player = Cast<ASOCharacter>(GetOwningPawn());
	if (Player && BoundPawn.Get() != Player)
	{
		BoundPawn = Player;
		TWeakObjectPtr<ASOHUD> Self(this);
		Player->ToggleInventoryScreen = [Self]() { if (Self.IsValid()) { Self->ToggleInventory(); } };
		Player->ToggleMapScreen = [Self]() { if (Self.IsValid()) { Self->ToggleMap(); } };
	}
	USOInventoryComponent* Inventory = SOFindInventory(GetOwningPlayerController());
	if (Inventory && FeedInventory.Get() != Inventory)
	{
		if (FeedInventory.IsValid())
		{
			FeedInventory->OnFeed.Remove(FeedHandle);
			FeedInventory->OnFeedItem.Remove(FeedItemHandle);
			FeedInventory->OnReward.Remove(RewardHandle);
			FeedInventory->OnLevelUp.Remove(LevelHandle);
		}
		FeedInventory = Inventory;
		FeedHandle = Inventory->OnFeed.AddUObject(this, &ASOHUD::OnFeed);
		FeedItemHandle = Inventory->OnFeedItem.AddUObject(this, &ASOHUD::OnFeedItem);
		RewardHandle = Inventory->OnReward.AddUObject(this, &ASOHUD::OnReward);
		LevelHandle = Inventory->OnLevelUp.AddUObject(this, &ASOHUD::OnLevelUp);
	}
}

void ASOHUD::OnFeed(const FString& Text, const FLinearColor& Color)
{
	FeedLines.Add({ Text, Color, static_cast<float>(GetWorld()->GetTimeSeconds()) });
	if (FeedLines.Num() > 6)
	{
		FeedLines.RemoveAt(0);
	}
}

void ASOHUD::OnFeedItem(const FSOFeedItem& Item)
{
	ShowItemCard(Item);
}

void ASOHUD::OnReward(ESORewardKind Kind, int32 Amount)
{
	const float Now = GetWorld()->GetTimeSeconds();
	for (FRewardPop& R : Rewards)
	{
		if (R.Kind == static_cast<uint8>(Kind) && Now - R.Time < 0.8f)
		{
			R.Amount += Amount;   // the same kind within a moment adds up ("+120 xp"), with a bump
			R.Bump = Now;
			return;
		}
	}
	FRewardPop Pop;
	Pop.Kind = static_cast<uint8>(Kind);
	Pop.Amount = Amount;
	Pop.Lane = Rewards.Num() > 0 ? (Rewards.Last().Lane + 1) % 4 : 0;
	Pop.Time = Pop.Bump = Now;
	Rewards.Add(Pop);
	if (Rewards.Num() > 6)
	{
		Rewards.RemoveAt(0);
	}
	if (Kind == ESORewardKind::Xp)
	{
		USOSoundLibrary::Play2D(this, TEXT("reward_xp"), 0.4f, 0.04f);
	}
}

void ASOHUD::OnLevelUp(int32 NewLevel)
{
	LevelUpAt = GetWorld()->GetTimeSeconds();
	LevelUpTo = NewLevel;
	USOSoundLibrary::Play2D(this, TEXT("level_up"), 0.85f, 0.0f);
}

void ASOHUD::ShowItemCard(const FSOFeedItem& Item)
{
	ItemCards.Insert({ Item, static_cast<float>(GetWorld()->GetTimeSeconds()) }, 0);
	if (ItemCards.Num() > 3)
	{
		ItemCards.SetNum(3);
	}
	IconOf(Item.Archetype);
	USOSoundLibrary::Play2D(this, TEXT("ui_open"), 0.35f, 0.15f);
}

UTexture2D* ASOHUD::IconOf(FName Archetype)
{
	if (Archetype.IsNone())
	{
		return nullptr;
	}
	if (const TObjectPtr<UTexture2D>* Found = Icons.Find(Archetype))
	{
		return *Found;
	}
	const USOLootTables* Tables = USOLootLibrary::GetTables();
	const USOWeaponData* Data = Tables ? Tables->LoadArchetype(Archetype) : nullptr;
	UTexture2D* Icon = Data ? Data->Icon.LoadSynchronous() : nullptr;
	Icons.Add(Archetype, Icon);
	return Icon;
}

void ASOHUD::ToggleInventory()
{
	APlayerController* PC = GetOwningPlayerController();
	if (!PC)
	{
		return;
	}
	if (InventoryWidget)
	{
		InventoryWidget->RemoveFromParent();
		InventoryWidget = nullptr;
		PC->SetInputMode(FInputModeGameOnly());
		PC->SetShowMouseCursor(false);
		USOSoundLibrary::Play2D(this, TEXT("ui_close"), 0.6f, 0.0f);
		return;
	}
	USOInventoryComponent* Inventory = SOFindInventory(PC);
	if (!Inventory)
	{
		return;
	}
	if (ASOCharacter* Player = Cast<ASOCharacter>(GetOwningPawn()))
	{
		Player->HandleFireReleased();
		Player->HandleAimReleased();
	}
	InventoryWidget = CreateWidget<USOInventoryWidget>(PC, USOInventoryWidget::StaticClass());
	TWeakObjectPtr<ASOHUD> Self(this);
	InventoryWidget->OnClose = [Self]() { if (Self.IsValid() && Self->InventoryWidget) { Self->ToggleInventory(); } };
	InventoryWidget->AddToViewport(10);
	InventoryWidget->Bind(Inventory);
	FInputModeUIOnly Mode;
	Mode.SetWidgetToFocus(InventoryWidget->TakeWidget());
	Mode.SetLockMouseToViewportBehavior(EMouseLockMode::LockAlways);
	PC->SetInputMode(Mode);
	PC->SetShowMouseCursor(true);
	USOSoundLibrary::Play2D(this, TEXT("ui_open"), 0.6f, 0.0f);
}

void ASOHUD::ToggleMap()
{
	APlayerController* PC = GetOwningPlayerController();
	if (!PC)
	{
		return;
	}
	if (MapWidget)
	{
		MapWidget->RemoveFromParent();
		MapWidget = nullptr;
		PC->SetInputMode(FInputModeGameOnly());
		PC->SetShowMouseCursor(false);
		USOSoundLibrary::Play2D(this, TEXT("ui_close"), 0.6f, 0.0f);
		return;
	}
	if (InventoryWidget)
	{
		ToggleInventory();
	}
	if (ASOCharacter* Player = Cast<ASOCharacter>(GetOwningPawn()))
	{
		Player->HandleFireReleased();
		Player->HandleAimReleased();
	}
	MapWidget = CreateWidget<USOMapWidget>(PC, USOMapWidget::StaticClass());
	TWeakObjectPtr<ASOHUD> Self(this);
	MapWidget->OnClose = [Self]() { if (Self.IsValid() && Self->MapWidget) { Self->ToggleMap(); } };
	MapWidget->AddToViewport(11);
	FInputModeUIOnly Mode;
	Mode.SetWidgetToFocus(MapWidget->TakeWidget());
	Mode.SetLockMouseToViewportBehavior(EMouseLockMode::LockAlways);
	PC->SetInputMode(Mode);
	PC->SetShowMouseCursor(true);
	USOSoundLibrary::Play2D(this, TEXT("ui_open"), 0.6f, 0.0f);
}

// ---------------------------------------------------------------------------------------------------------------------
// Top left: the round mini-map and the area's name

void ASOHUD::DrawMinimap(const FLayout& L)
{
	const ASOMapInfo* Info = ASOMapInfo::Get(this);
	const ASOCharacter* Player = Cast<ASOCharacter>(GetOwningPawn());
	UTextureRenderTarget2D* Map = Info ? Info->GetMapTexture() : nullptr;
	if (!Info || !Player || !Map || !Map->GetResource())
	{
		return;
	}
	const float S = L.S;
	FPainter P(Canvas);
	FType Type(Canvas);
	const FVector2D C(L.X0 + 150.0f * S, 150.0f * S);
	const float R = 104.0f * S;
	// a 300 m window round the player, north up; the window stops at the map's edges (no wrapping), so near an edge
	// the player stands off the middle
	const float Window = FMath::Min(1.0f, 30000.0f / FMath::Max(Info->HalfSize * 2.0f, 1.0f));
	const float UVPerPx = Window / (2.0f * R);
	const FVector2D Me = Info->WorldToMap(Player->GetActorLocation());
	const FVector2D UVc(FMath::Clamp(static_cast<float>(Me.X), Window * 0.5f, 1.0f - Window * 0.5f), FMath::Clamp(static_cast<float>(Me.Y), Window * 0.5f, 1.0f - Window * 0.5f));
	auto OnMap = [&](const FVector& World) { return C + (Info->WorldToMap(World) - UVc) / UVPerPx; };

	// the glass round it, the picture, a dark edge into the rim
	P.Disc(C, R + 9.0f * S, A(Glass, 0.9f), A(GlassDeep, 0.9f));
	P.TexturedDisc(C, R, Map->GetResource(), UVc, UVPerPx, FLinearColor(0.50f, 0.60f, 0.80f, 0.96f));
	P.Ring(C, R * 0.80f, R, FLinearColor(0, 0, 0, 0), FLinearColor(0.0f, 0.004f, 0.012f, 0.75f));

	// where the player looks: a soft cone
	const float Yaw = FMath::DegreesToRadians(Player->GetControlRotation().Yaw);
	const FVector2D Fwd(FMath::Sin(Yaw), -FMath::Cos(Yaw));     // map space: up = world +X, right = world +Y
	const FVector2D Rt(-Fwd.Y, Fwd.X);
	const FVector2D Mine = C + (Me - UVc) / UVPerPx;
	const float Heading = FMath::Atan2(Fwd.Y, Fwd.X);
	P.Sector(Mine, R * 0.92f, Heading - FMath::DegreesToRadians(42.0f), Heading + FMath::DegreesToRadians(42.0f), A(Cyan, 0.32f), A(Cyan, 0.0f));

	// the important places
	for (TActorIterator<ASOMapPoint> It(GetWorld()); It; ++It)
	{
		const FVector2D Pt = OnMap(It->GetActorLocation());
		if ((Pt - C).Size() > R - 8.0f * S)
		{
			continue;
		}
		const FLinearColor Col = ASOMapPoint::KindColor(It->Kind);
		P.Fill(Diamond(Pt, 5.5f * S, 5.5f * S), A(FLinearColor::Black, 0.6f));
		P.Fill(Diamond(Pt, 4.0f * S, 4.0f * S), Col);
	}
	// an operation's goal: a gold diamond, held at the rim when it is out of the window (the way to it)
	if (const ASOOperation* Op = ASOOperation::Get(this))
	{
		if (const FSOStage* Stage = Op->GetState() == ESOOperationState::Active ? Op->GetStage() : nullptr; Stage && (Stage->Kind == ESOStageKind::Travel || Stage->Kind == ESOStageKind::Hold))
		{
			FVector2D Pt = OnMap(Stage->Goal);
			const FVector2D D = Pt - C;
			if (D.Size() > R - 10.0f * S)
			{
				Pt = C + D.GetSafeNormal() * (R - 10.0f * S);
			}
			P.Stroke(Diamond(Pt, 7.0f * S, 7.0f * S), Gold, 1.5f * S);
			P.Fill(Diamond(Pt, 2.5f * S, 2.5f * S), Gold);
		}
	}
	// creatures: the ones this side knows of (awake to the fight, or close), red; a boss a ring
	for (TActorIterator<ASOEnemy> It(GetWorld()); It; ++It)
	{
		const ASOEnemy* E = *It;
		if (E->IsDead() || E->IsDisplayOnly() || !USOCombatStatics::AreHostile(Player, E))
		{
			continue;
		}
		const ASOEnemyAIController* Brain = Cast<ASOEnemyAIController>(E->GetController());
		const ESOEnemyState State = Brain ? Brain->GetState() : ESOEnemyState::Idle;
		const bool bAwake = State != ESOEnemyState::Idle && State != ESOEnemyState::Wander && State != ESOEnemyState::Dead;
		const float Dist = FVector::Dist2D(E->GetActorLocation(), Player->GetActorLocation());
		if (!bAwake && Dist > 1500.0f)
		{
			continue;
		}
		const FVector2D Pt = OnMap(E->GetActorLocation());
		if ((Pt - C).Size() > R - 6.0f * S)
		{
			continue;
		}
		if (E->GetBoss())
		{
			P.Ring(Pt, 4.0f * S, 6.0f * S, Lock, Lock);
		}
		else
		{
			P.Disc(Pt, 4.5f * S, A(FLinearColor::Black, 0.5f), A(FLinearColor::Black, 0.0f), 16);
			P.Disc(Pt, 3.8f * S, Lock, A(Lock, 0.85f), 16);
		}
	}
	// you
	P.Tri(Mine + Fwd * 11.0f * S, Mine - Fwd * 7.0f * S + Rt * 7.0f * S, Mine - Fwd * 7.0f * S - Rt * 7.0f * S, A(FLinearColor::Black, 0.7f));
	P.Tri(Mine + Fwd * 9.0f * S, Mine - Fwd * 5.5f * S + Rt * 5.5f * S, Mine - Fwd * 5.5f * S - Rt * 5.5f * S, Cyan);
	// the rim: a thin ring, ticks at the eight points, north marked
	P.Ring(C, R, R + 1.5f * S, Line, Line);
	P.Ring(C, R + 8.0f * S, R + 9.5f * S, A(Line, 0.5f), A(Line, 0.5f));
	for (int32 i = 0; i < 8; ++i)
	{
		const float T = UE_TWO_PI * i / 8.0f - UE_HALF_PI;
		const FVector2D D(FMath::Cos(T), FMath::Sin(T));
		P.Segment(C + D * (R + 2.0f * S), C + D * (R + (i % 2 ? 5.0f : 8.0f) * S), i == 0 ? Gold : Line, 1.5f * S);
	}
	P.Flush();
	Type.DrawCentred(TEXT("N"), C.X, C.Y - R - 26.0f * S, Type.Medium, 1.0f * S, Gold);

	// the area's name, and where in it (the nearest important place within 400 m, or the operation's stage)
	const float NameY = C.Y + R + 22.0f * S;
	Type.Caps(Info->AreaName.ToString(), L.X0 + 46.0f * S, NameY, Type.Medium, 1.2f * S, Ink, 3.0f * S);
	FString Where;
	if (const ASOOperation* Op = ASOOperation::Get(this); Op && Op->GetStage() && Op->GetState() == ESOOperationState::Active)
	{
		Where = Op->GetStage()->Title.ToString();
	}
	else
	{
		float Best = 40000.0f;
		for (TActorIterator<ASOMapPoint> It(GetWorld()); It; ++It)
		{
			const float D = FVector::Dist2D(It->GetActorLocation(), Player->GetActorLocation());
			if (D < Best)
			{
				Best = D;
				Where = It->Label.ToString();
			}
		}
	}
	if (!Where.IsEmpty())
	{
		Type.Caps(Where, L.X0 + 46.0f * S, NameY + 22.0f * S, Type.Small, 0.95f * S, Dim, 2.0f * S);
	}
}

// ---------------------------------------------------------------------------------------------------------------------
// Top centre: the compass strip and the objective banner

void ASOHUD::DrawCompass(const FLayout& L)
{
	const ASOCharacter* Player = Cast<ASOCharacter>(GetOwningPawn());
	if (!Player)
	{
		return;
	}
	const float S = L.S;
	FPainter P(Canvas);
	FType Type(Canvas);
	const float Y = 14.0f * S, HalfW = 250.0f * S, PxPerDeg = HalfW / 100.0f;
	const float Yaw = FRotator::NormalizeAxis(Player->GetControlRotation().Yaw);   // 0 = north (world +X), 90 = east
	auto Fade = [&](float Deg) { return FMath::Clamp(1.0f - FMath::Pow(FMath::Abs(Deg) / 100.0f, 3.0f), 0.0f, 1.0f); };
	auto Rel = [&](float WorldDeg) { return FRotator::NormalizeAxis(WorldDeg - Yaw); };

	// the baseline, fading to the ends
	P.FillAcross(Rectangle(L.CX - HalfW, Y + 15.0f * S, HalfW, 1.2f * S), A(Line, 0.0f), A(Line, 1.6f));
	P.FillAcross(Rectangle(L.CX, Y + 15.0f * S, HalfW, 1.2f * S), A(Line, 1.6f), A(Line, 0.0f));
	// ticks every 15 degrees, the eighths taller
	for (int32 Deg = -105; Deg <= 105; Deg += 15)
	{
		const float World = FMath::Fmod(Yaw + Deg + 720.0f, 360.0f);
		const float Snapped = FMath::RoundToFloat(World / 15.0f) * 15.0f;
		const float R = Rel(Snapped);
		if (FMath::Abs(R) > 100.0f)
		{
			continue;
		}
		const bool bMajor = FMath::IsNearlyZero(FMath::Fmod(Snapped, 45.0f), 0.1f);
		const float X = L.CX + R * PxPerDeg;
		P.Segment(FVector2D(X, Y + (bMajor ? 7.0f : 11.0f) * S), FVector2D(X, Y + 15.0f * S), A(Line, Fade(R) * (bMajor ? 1.0f : 0.6f)), 1.0f * S);
	}
	// the objective's bearing and the important places
	if (const ASOOperation* Op = ASOOperation::Get(this))
	{
		if (const FSOStage* Stage = Op->GetState() == ESOOperationState::Active ? Op->GetStage() : nullptr; Stage && (Stage->Kind == ESOStageKind::Travel || Stage->Kind == ESOStageKind::Hold))
		{
			const FVector To = Stage->Goal - Player->GetActorLocation();
			const float R = Rel(FMath::RadiansToDegrees(FMath::Atan2(To.Y, To.X)));
			const float X = L.CX + FMath::Clamp(R, -100.0f, 100.0f) * PxPerDeg;
			P.Fill(Diamond(FVector2D(X, Y + 21.0f * S), 5.0f * S, 5.0f * S), Gold);
		}
	}
	for (TActorIterator<ASOMapPoint> It(GetWorld()); It; ++It)
	{
		const FVector To = It->GetActorLocation() - Player->GetActorLocation();
		if (To.Size2D() > 60000.0f)
		{
			continue;
		}
		const float R = Rel(FMath::RadiansToDegrees(FMath::Atan2(To.Y, To.X)));
		if (FMath::Abs(R) > 100.0f)
		{
			continue;
		}
		P.Fill(Diamond(FVector2D(L.CX + R * PxPerDeg, Y + 20.0f * S), 3.5f * S, 3.5f * S), A(ASOMapPoint::KindColor(It->Kind), Fade(R)));
	}
	// the heading mark
	P.Tri(FVector2D(L.CX - 5.0f * S, Y - 2.0f * S), FVector2D(L.CX + 5.0f * S, Y - 2.0f * S), FVector2D(L.CX, Y + 5.0f * S), Gold);
	P.Flush();
	// the letters
	const TPair<float, const TCHAR*> Cardinals[] = { { 0.0f, TEXT("N") }, { 90.0f, TEXT("E") }, { 180.0f, TEXT("S") }, { 270.0f, TEXT("W") } };
	for (const TPair<float, const TCHAR*>& Cd : Cardinals)
	{
		const float R = Rel(Cd.Key);
		if (FMath::Abs(R) < 100.0f)
		{
			Type.DrawCentred(Cd.Value, L.CX + R * PxPerDeg, Y - 6.0f * S, Type.Medium, 1.25f * S, A(Cd.Key == 0.0f ? Gold : Ink, Fade(R)));
		}
	}
	Type.DrawCentred(FString::Printf(TEXT("%d"), FMath::RoundToInt(FMath::Fmod(Yaw + 360.0f, 360.0f))), L.CX, Y + 24.0f * S, Type.Small, 0.95f * S, Dim);
}

void ASOHUD::DrawObjective(const FLayout& L)
{
	const ASOOperation* Op = ASOOperation::Get(this);
	const ASOCharacter* Player = Cast<ASOCharacter>(GetOwningPawn());
	const FSOStage* Stage = Op && Op->GetState() == ESOOperationState::Active ? Op->GetStage() : nullptr;
	if (!Stage || !Player)
	{
		return;
	}
	const float S = L.S;
	FPainter P(Canvas);
	FType Type(Canvas);
	const float W = 460.0f * S, H = 54.0f * S, X = L.CX - W * 0.5f, Y = 56.0f * S;
	// what the stage asks: its count, its clock, its distance, the boss's health
	FString Right;
	float Frac = 0.0f;
	switch (Stage->Kind)
	{
	case ESOStageKind::Clear:
		Right = FString::Printf(TEXT("%d / %d"), FMath::Min(Op->GetKills(), Op->GetGoalCount()), Op->GetGoalCount());
		Frac = Op->GetGoalCount() > 0 ? static_cast<float>(Op->GetKills()) / Op->GetGoalCount() : 0.0f;
		break;
	case ESOStageKind::Hold:
	{
		const int32 Left = FMath::CeilToInt(Op->GetHoldLeft());
		Right = FString::Printf(TEXT("%d:%02d"), Left / 60, Left % 60);
		Frac = Stage->HoldTime > 0.0f ? 1.0f - Op->GetHoldLeft() / Stage->HoldTime : 0.0f;
		break;
	}
	case ESOStageKind::Boss:
		if (const ASOEnemy* Boss = Op->GetBoss())
		{
			Frac = 1.0f - Boss->GetHealth() / FMath::Max(Boss->GetMaxHealth(), 1.0f);
			Right = FString::Printf(TEXT("%d%%"), FMath::RoundToInt(Frac * 100.0f));
		}
		break;
	default:
	{
		const float Dist = FMath::Max(0.0f, FVector::Dist(Player->GetActorLocation(), Stage->Goal) - Stage->GoalRadius);
		Right = FString::Printf(TEXT("%d m"), FMath::RoundToInt(Dist / 100.0f));
		Frac = FMath::Clamp(1.0f - Dist / 3000.0f, 0.0f, 1.0f);
		break;
	}
	}
	Panel(P, Plate4(X, Y, W, H, 9.0f * S), 1.0f * S);
	P.Segment(FVector2D(X + 10.0f * S, Y), FVector2D(X + W - 10.0f * S, Y), A(Gold, 0.85f), 1.5f * S);
	// the glyph: a diamond with a point in it
	const FVector2D G(X + 26.0f * S, Y + 21.0f * S);
	P.Stroke(Diamond(G, 9.0f * S, 9.0f * S), Gold, 1.5f * S);
	P.Fill(Diamond(G, 3.0f * S, 3.0f * S), Gold);
	Bar(P, X + 46.0f * S, Y + 38.0f * S, W - 62.0f * S, 4.0f * S, Frac, Gold);
	P.Flush();
	// the words: the objective, shrunk to fit beside the count
	const float RightW = Type.Size(Right, Type.Medium, 1.1f * S).X;
	const float Room = W - 62.0f * S - RightW - 16.0f * S;
	float Scale = 1.05f * S, Spacing = 1.8f * S;
	while (Type.CapsWidth(Stage->Objective.ToString(), Type.Medium, Scale, Spacing) > Room && Scale > 0.7f * S)
	{
		Scale -= 0.05f * S;
		Spacing = FMath::Max(Spacing - 0.3f * S, 0.5f * S);
	}
	Type.Caps(Stage->Objective.ToString(), X + 46.0f * S, Y + 10.0f * S, Type.Medium, Scale, Ink, Spacing);
	Type.DrawRight(Right, X + W - 16.0f * S, Y + 9.0f * S, Type.Medium, 1.1f * S, Ink);
}

// ---------------------------------------------------------------------------------------------------------------------
// Top right: the conditions on the player, the tracked objectives, the NEW ITEM cards, the feed

void ASOHUD::DrawConditions(const FLayout& L)
{
	const ASOCharacter* Player = Cast<ASOCharacter>(GetOwningPawn());
	if (!Player)
	{
		return;
	}
	const float S = L.S;
	FPainter P(Canvas);
	FType Type(Canvas);
	float X = L.X1 - 40.0f * S;
	const float Y = 40.0f * S, R = 22.0f * S;
	for (int32 i = UE_ARRAY_COUNT(Conditions) - 1; i >= 0; --i)
	{
		const FConditionLook& Cnd = Conditions[i];
		if (!Player->HasStatus(*Cnd.Tag))
		{
			continue;
		}
		const float Left = Player->GetStatusTimeLeft(*Cnd.Tag);
		const float Pulse = Left > 0.0f && Left < 1.5f ? 0.6f + 0.4f * FMath::Abs(FMath::Sin(L.Now * 8.0f)) : 1.0f;
		const FVector2D C(X - R - 4.0f * S, Y + R);
		const TArray<FVector2D> Cell = Hex(C, R, UE_PI / 6.0f);
		P.FillFan(C, Cell, A(Cnd.Color, 0.22f * Pulse), A(Glass, 0.9f));
		P.Stroke(Cell, A(Cnd.Color, 0.9f * Pulse), 1.2f * S);
		ConditionGlyph(P, Cnd.Glyph, C, 9.5f * S, A(Cnd.Color, Pulse), 1.7f * S);
		P.Flush();
		Type.Caps(Cnd.Word, C.X, Y + 2.0f * R + 5.0f * S, Type.Small, 0.85f * S, A(Dim, Pulse), 1.0f * S, 0.5f);
		if (Left > 0.0f)
		{
			Type.DrawCentred(Left >= 10.0f ? FString::Printf(TEXT("%d s"), FMath::CeilToInt(Left)) : FString::Printf(TEXT("%.1f s"), Left), C.X, Y + 2.0f * R + 17.0f * S, Type.Small, 0.95f * S, A(Ink, Pulse));
		}
		X -= 2.0f * R + 26.0f * S;
	}
}

void ASOHUD::DrawTracked(const FLayout& L)
{
	const float S = L.S;
	FPainter P(Canvas);
	FType Type(Canvas);
	const float W = 330.0f * S, X = L.X1 - 40.0f * S - W;
	float Y = 112.0f * S;
	const ASOOperation* Op = ASOOperation::Get(this);
	if (Op && Op->GetState() == ESOOperationState::Active && Op->GetStage())
	{
		// the header
		Panel(P, Plate(X, Y, W, 26.0f * S, 6.0f * S), 1.0f * S);
		P.Segment(FVector2D(X + 6.0f * S, Y), FVector2D(X + W, Y), A(Gold, 0.7f), 1.0f * S);
		P.Flush();
		Type.Caps(TEXT("Tracked"), X + 12.0f * S, Y + 6.0f * S, Type.Small, 1.0f * S, Gold, 2.2f * S);
		Type.Caps(Op->OperationName.ToString(), X + W - 12.0f * S, Y + 6.0f * S, Type.Small, 0.9f * S, Dim, 1.2f * S, 1.0f);
		Y += 26.0f * S;
		// the stage before (done), this one, the next: a glyph, the title, its bar and count
		const int32 Idx = Op->GetStageIndex();
		TArray<int32> Rows;
		if (Idx > 0) { Rows.Add(Idx - 1); }
		Rows.Add(Idx);
		if (Op->Stages.IsValidIndex(Idx + 1)) { Rows.Add(Idx + 1); }
		const float RowH = 38.0f * S;
		Panel(P, Rectangle(X, Y, W, RowH * Rows.Num() + 6.0f * S), 1.0f * S, 0.9f);
		for (int32 r = 0; r < Rows.Num(); ++r)
		{
			const int32 i = Rows[r];
			const FSOStage& St = Op->Stages[i];
			const bool bDone = i < Idx, bNow = i == Idx;
			const float RY = Y + 6.0f * S + r * RowH;
			const FVector2D G(X + 16.0f * S, RY + 10.0f * S);
			if (bDone)
			{
				P.Fill(Diamond(G, 5.0f * S, 5.0f * S), A(Dim, 0.7f));
			}
			else
			{
				P.Stroke(Diamond(G, 5.5f * S, 5.5f * S), bNow ? Gold : A(Dim, 0.6f), 1.2f * S);
				if (bNow)
				{
					P.Fill(Diamond(G, 2.0f * S, 2.0f * S), Gold);
				}
			}
			float Frac = bDone ? 1.0f : 0.0f;
			FString Count;
			if (bNow)
			{
				switch (St.Kind)
				{
				case ESOStageKind::Clear:
					Frac = Op->GetGoalCount() > 0 ? static_cast<float>(Op->GetKills()) / Op->GetGoalCount() : 0.0f;
					Count = FString::Printf(TEXT("%d / %d"), FMath::Min(Op->GetKills(), Op->GetGoalCount()), Op->GetGoalCount());
					break;
				case ESOStageKind::Hold:
					Frac = St.HoldTime > 0.0f ? 1.0f - Op->GetHoldLeft() / St.HoldTime : 0.0f;
					Count = FString::Printf(TEXT("%d s"), FMath::CeilToInt(Op->GetHoldLeft()));
					break;
				case ESOStageKind::Boss:
					if (const ASOEnemy* Boss = Op->GetBoss())
					{
						Frac = 1.0f - Boss->GetHealth() / FMath::Max(Boss->GetMaxHealth(), 1.0f);
					}
					break;
				default:
					if (const APawn* Pawn = GetOwningPawn())
					{
						const float Dist = FMath::Max(0.0f, FVector::Dist(Pawn->GetActorLocation(), St.Goal) - St.GoalRadius);
						Frac = FMath::Clamp(1.0f - Dist / 3000.0f, 0.0f, 1.0f);
						Count = FString::Printf(TEXT("%d m"), FMath::RoundToInt(Dist / 100.0f));
					}
					break;
				}
			}
			Bar(P, X + 30.0f * S, RY + 22.0f * S, W - 44.0f * S, 3.0f * S, Frac, bNow ? Gold : A(Dim, 0.6f), bDone ? 0.5f : 1.0f);
			P.Flush();
			Type.Draw(St.Title.ToString(), X + 30.0f * S, RY + 2.0f * S, Type.Medium, 0.95f * S, bNow ? Ink : A(Dim, bDone ? 0.7f : 0.85f));
			if (!Count.IsEmpty())
			{
				Type.DrawRight(Count, X + W - 14.0f * S, RY + 2.0f * S, Type.Medium, 0.95f * S, Ink);
			}
		}
		Y += RowH * Rows.Num() + 6.0f * S + 12.0f * S;
	}
	RightFlowY = Y;
}

void ASOHUD::DrawItemCards(const FLayout& L)
{
	const float S = L.S;
	FPainter P(Canvas);
	FType Type(Canvas);
	const float W = 360.0f * S, H = 100.0f * S;
	float Y = RightFlowY;
	for (int32 i = 0; i < ItemCards.Num(); ++i)
	{
		const FItemCard& Card = ItemCards[i];
		const float Age = L.Now - Card.Time;
		const float Hold = 7.0f;
		if (Age > Hold)
		{
			ItemCards.RemoveAt(i--);
			continue;
		}
		const float In = Ease(Age / 0.3f);
		const float Out = FMath::Clamp((Hold - Age) / 0.5f, 0.0f, 1.0f);
		const float Alpha = In * Out;
		const float X = L.X1 - 40.0f * S - W + (1.0f - In) * 60.0f * S;
		const FLinearColor Col = RarityColour(Card.Item.Rarity);
		const FSORarityInfo* Rar = RarityOf(Card.Item.Rarity);
		const USOLootTables* Tables = USOLootLibrary::GetTables();
		const USOWeaponData* Data = Tables ? Tables->LoadArchetype(Card.Item.Archetype) : nullptr;
		const TArray<FVector2D> Shape = Plate(X, Y, W, H, 10.0f * S);
		Panel(P, Shape, 1.0f * S, Alpha, A(Col, 0.6f));
		// its rarity's light down the left and under the glass
		P.FillAcross(Rectangle(X, Y + 10.0f * S, 90.0f * S, H - 10.0f * S), A(Col, 0.22f * Alpha), A(Col, 0.0f));
		P.Fill(Rectangle(X, Y + 10.0f * S, 3.0f * S, H - 10.0f * S), A(Col, Alpha));
		P.Flush();
		Type.Caps(TEXT("New item"), X + 16.0f * S, Y + 9.0f * S, Type.Small, 1.0f * S, A(Col, Alpha), 2.6f * S);
		Type.Draw(Card.Item.Name, X + 16.0f * S, Y + 30.0f * S, Type.Large, 1.3f * S, A(Ink, Alpha));
		FString LineText = Rar ? Rar->Name.ToString() : FString();
		if (Data)
		{
			LineText += (LineText.IsEmpty() ? TEXT("") : TEXT("  ·  ")) + Data->ClassName.ToString() + TEXT("  ·  ") + Data->DisplayName.ToString();
		}
		Type.Caps(LineText, X + 16.0f * S, Y + 70.0f * S, Type.Small, 0.85f * S, A(Dim, Alpha), 1.2f * S);
		Type.DrawRight(FString::Printf(TEXT("%d"), Card.Item.Power), X + W - 14.0f * S, Y + 8.0f * S, Type.Medium, 1.2f * S, A(Gold, Alpha));
		if (UTexture2D* Icon = IconOf(Card.Item.Archetype))
		{
			DrawTexture(Icon, X + W - 156.0f * S, Y + 28.0f * S, 140.0f * S, 70.0f * S, 0.0f, 0.0f, 1.0f, 1.0f, FLinearColor(1, 1, 1, Alpha));
		}
		Y += H + 12.0f * S;
	}
	// the feed: lesser news (a level, a dismantle, ammo), fading after 6 s
	for (int32 i = FeedLines.Num() - 1; i >= 0; --i)
	{
		const float Age = L.Now - FeedLines[i].Time;
		if (Age > 6.0f)
		{
			continue;
		}
		const float Alpha = FMath::Clamp(6.0f - Age, 0.0f, 1.0f) * Ease(Age * 4.0f);
		const FVector2D Sz = Type.Size(FeedLines[i].Text, Type.Medium, 0.95f * S);
		const float X = L.X1 - 40.0f * S - Sz.X - 24.0f * S;
		Panel(P, Plate(X, Y, Sz.X + 24.0f * S, Sz.Y + 10.0f * S, 5.0f * S), 1.0f * S, Alpha * 0.9f);
		P.Flush();
		Type.Draw(FeedLines[i].Text, X + 12.0f * S, Y + 5.0f * S, Type.Medium, 0.95f * S, A(FeedLines[i].Color, Alpha));
		Y += Sz.Y + 16.0f * S;
	}
}

// ---------------------------------------------------------------------------------------------------------------------
// Over the creatures: level, name, bar; the lone boss's bar

void ASOHUD::DrawCreatures(const FLayout& L)
{
	const ASOCharacter* Player = Cast<ASOCharacter>(GetOwningPawn());
	if (!Player)
	{
		return;
	}
	const float S = L.S;
	FPainter P(Canvas);
	FType Type(Canvas);
	const ASOOperation* Operation = ASOOperation::Get(this);
	const USOInventoryComponent* Inventory = FeedInventory.Get();
	const int32 MyLevel = Inventory ? Inventory->GetLevel() : 1;
	const ASOEnemy* LoneBoss = nullptr;
	for (TActorIterator<ASOCombatCharacter> It(GetWorld()); It; ++It)
	{
		const ASOCombatCharacter* Other = *It;
		if ((Operation && Other == Operation->GetBoss()) || Other == Player || Other->IsDead() || !USOCombatStatics::AreHostile(Player, Other) || Other->IsDisplayOnly())
		{
			continue;
		}
		const ASOEnemy* Creature = Cast<ASOEnemy>(Other);
		// a boss met outside an operation (a level's variant with a boss table) has the bar across the top too, once
		// the fight is on
		if (Creature && Creature->GetBoss())
		{
			if (!(Operation && Operation->GetBoss()) && (Creature->GetHealth() < Creature->GetMaxHealth() || Creature->IsImmune())
				&& FVector::Dist(Creature->GetActorLocation(), Player->GetActorLocation()) < 7000.0f)
			{
				LoneBoss = Creature;
			}
			continue;
		}
		// an elite (a variant with a name of its own) in view for the first time: announced
		if (Creature && Creature->IsElite() && !Introduced.Contains(TWeakObjectPtr<const AActor>(Other))
			&& FVector::Dist(Other->GetActorLocation(), Player->GetActorLocation()) < 4500.0f)
		{
			const FVector Sc = Project(Other->GetActorLocation() + FVector(0, 0, 60.0f), true);
			if (Sc.Z > 0.0f && Sc.X > 0.0f && Sc.X < L.W && Sc.Y > 0.0f && Sc.Y < L.H)
			{
				Introduced.Add(TWeakObjectPtr<const AActor>(Other));
				EliteAt = L.Now;
				EliteName = Creature->DisplayName.ToString();
				EliteLevel = FMath::Max(1, FMath::RoundToInt(MyLevel * Creature->GetDamageScale()));
				USOSoundLibrary::Play2D(this, TEXT("elite_seen"), 0.7f, 0.0f);
			}
		}
		const bool bLocked = Locked.Get() == Other;
		const bool bHurt = Other->GetHealth() < Other->GetMaxHealth() || (Other->GetMaxShield() > 0.0f && Other->GetShield() < Other->GetMaxShield());
		if (!bHurt && !bLocked)
		{
			continue;
		}
		const float Dist = FVector::Dist(Other->GetActorLocation(), Player->GetActorLocation());
		if (Dist > 4000.0f)
		{
			continue;
		}
		const FVector Top = Other->GetActorLocation() + FVector(0, 0, Other->GetSimpleCollisionHalfHeight() + 34.0f);
		const FVector Screen = Project(Top, true);
		if (Screen.Z <= 0.0f)
		{
			continue;
		}
		const float Alpha = FMath::Clamp(1.4f - Dist / 4000.0f, 0.35f, 1.0f);
		const float BW = 110.0f * S, BX = Screen.X - BW * 0.5f, BY = Screen.Y;
		// the name, its level before it (the player's level scaled by what the creature was made: an elite reads above)
		const FString Name = (Creature ? Creature->DisplayName : FText::FromString(Other->GetName())).ToString();
		const int32 Level = FMath::Max(1, FMath::RoundToInt(MyLevel * (Creature ? Creature->GetDamageScale() : 1.0f)));
		const FString LevelText = FString::Printf(TEXT("%d"), Level);
		const float NameW = Type.CapsWidth(Name, Type.Small, 1.05f * S, 1.5f * S);
		const float BoxW = Type.Size(LevelText, Type.Small, 1.0f * S).X + 12.0f * S;
		const float Total = BoxW + 6.0f * S + NameW;
		const float NX = Screen.X - Total * 0.5f, NY = BY - 24.0f * S;
		P.Fill(Rectangle(NX - 2.0f * S, NY - 2.0f * S, BoxW, 18.0f * S), A(Glass, Alpha));
		P.Stroke(Rectangle(NX - 2.0f * S, NY - 2.0f * S, BoxW, 18.0f * S), A(bLocked ? Lock : Line, Alpha), 1.0f * S);
		// the bar: health red, the shield as a thin line over it
		P.Fill(Rectangle(BX - 1.5f * S, BY - 1.5f * S, BW + 3.0f * S, 9.0f * S), A(GlassDeep, Alpha));
		P.Fill(Rectangle(BX, BY, BW * FMath::Clamp(Other->GetHealth() / FMath::Max(Other->GetMaxHealth(), 1.0f), 0.0f, 1.0f), 6.0f * S), A(bLocked ? Lock : HealthRed, Alpha));
		if (Other->GetMaxShield() > 0.0f && Other->GetShield() > 0.0f)
		{
			P.Fill(Rectangle(BX, BY + 7.0f * S, BW * Other->GetShield() / Other->GetMaxShield(), 2.0f * S), A(ShieldBlue, Alpha));
		}
		// what is on it: a pip per condition under the bar
		float PipX = BX;
		const TPair<FGameplayTag, FLinearColor> Pips[] = { { SOTags::Status_Burn, FLinearColor(1.0f, 0.5f, 0.1f) },
			{ SOTags::Status_Slow, FLinearColor(0.4f, 0.7f, 1.0f) }, { SOTags::Status_Stagger, FLinearColor(1.0f, 0.9f, 0.4f) },
			{ SOTags::Status_Haste, FLinearColor(0.7f, 0.4f, 1.0f) }, { SOTags::Status_Suppressed, FLinearColor(1.0f, 0.62f, 0.3f) } };
		for (const TPair<FGameplayTag, FLinearColor>& Pip : Pips)
		{
			if (Other->HasStatus(Pip.Key))
			{
				P.Fill(Rectangle(PipX, BY + 11.0f * S, 12.0f * S, 3.0f * S), A(Pip.Value, Alpha));
				PipX += 15.0f * S;
			}
		}
		if (bLocked)
		{
			// the lock: a bracket either side of the plate
			const float Bx0 = NX - 10.0f * S, Bx1 = Screen.X + Total * 0.5f + 8.0f * S, By0 = NY - 6.0f * S, By1 = BY + 11.0f * S, K = 6.0f * S;
			P.Stroke({ FVector2D(Bx0 + K, By0), FVector2D(Bx0, By0), FVector2D(Bx0, By0 + K) }, A(Lock, Alpha), 1.5f * S, false);
			P.Stroke({ FVector2D(Bx0 + K, By1), FVector2D(Bx0, By1), FVector2D(Bx0, By1 - K) }, A(Lock, Alpha), 1.5f * S, false);
			P.Stroke({ FVector2D(Bx1 - K, By0), FVector2D(Bx1, By0), FVector2D(Bx1, By0 + K) }, A(Lock, Alpha), 1.5f * S, false);
			P.Stroke({ FVector2D(Bx1 - K, By1), FVector2D(Bx1, By1), FVector2D(Bx1, By1 - K) }, A(Lock, Alpha), 1.5f * S, false);
		}
		P.Flush();
		Type.Draw(LevelText, NX + 4.0f * S, NY, Type.Small, 1.0f * S, A(Gold, Alpha));
		Type.Caps(Name, NX + BoxW + 6.0f * S, NY, Type.Small, 1.05f * S, A(Ink, Alpha), 1.5f * S);
	}
	P.Flush();
	DrawBossBar(LoneBoss, L);
}

// ---------------------------------------------------------------------------------------------------------------------
// Bottom left: the kit's emblem, shield and health

void ASOHUD::DrawVitals(const FLayout& L)
{
	const ASOCharacter* Player = Cast<ASOCharacter>(GetOwningPawn());
	if (!Player)
	{
		return;
	}
	const float S = L.S;
	FPainter P(Canvas);
	FType Type(Canvas);
	const USOInventoryComponent* Inventory = FeedInventory.Get();
	const FVector2D E(L.X0 + 96.0f * S, L.H - 92.0f * S);
	const float R = 52.0f * S;
	const float HealthFrac = Player->GetHealth() / FMath::Max(Player->GetMaxHealth(), 1.0f);
	const bool bLow = HealthFrac < 0.35f;
	const float LowPulse = bLow ? 0.7f + 0.3f * FMath::Abs(FMath::Sin(L.Now * 5.0f)) : 1.0f;

	// the emblem: a diamond of glass, the broken orbit in it; the kit's light at its rim
	const TArray<FVector2D> Outer = Diamond(E, R, R);
	P.FillFan(E, Outer, A(Glass, 0.95f), A(GlassDeep, 0.95f));
	P.Stroke(Outer, Line, 1.5f * S);
	P.Stroke(Diamond(E, R * 0.82f, R * 0.82f), A(Player->GetAbilityColor(), 0.55f), 1.0f * S);
	OrbitMark(P, E, 15.0f * S, bLow ? A(Hurt, LowPulse) : Ink, 2.2f * S);
	// the bracket under the bars
	const float BX = E.X + R + 20.0f * S, BW = 300.0f * S;
	P.Segment(FVector2D(BX - 6.0f * S, L.H - 56.0f * S), FVector2D(BX + BW + 50.0f * S, L.H - 56.0f * S), A(Line, 0.6f), 1.0f * S);
	P.Segment(FVector2D(BX + BW + 50.0f * S, L.H - 56.0f * S), FVector2D(BX + BW + 50.0f * S, L.H - 64.0f * S), A(Line, 0.6f), 1.0f * S);
	// the bars
	const float ShieldY = L.H - 122.0f * S, HealthY = L.H - 84.0f * S;
	if (Player->GetMaxShield() > 0.0f)
	{
		Bar(P, BX, ShieldY, BW, 14.0f * S, Player->GetShield() / Player->GetMaxShield(), ShieldBlue, 1.0f, 1.0f * S);
	}
	Bar(P, BX, HealthY, BW, 14.0f * S, HealthFrac, bLow ? A(Hurt, LowPulse) : HealthRed, 1.0f, 1.0f * S);
	// the level's bar: thin, under the kit's name
	const USOProgressionTable& Rules = USOProgressionTable::Get();
	if (Inventory)
	{
		const float XpFrac = static_cast<float>(Inventory->GetXp()) / FMath::Max(Rules.XpForLevel(Inventory->GetLevel()), 1);
		// eased toward the real fill (a kill is SEEN to fill it); at a level-up it runs to the end, flares, and starts
		// again from nothing
		const float LevelAge = L.Now - LevelUpAt;
		const bool bFilling = LevelAge >= 0.0f && LevelAge < 0.45f;
		if (XpShown < 0.0f)
		{
			XpShown = XpFrac;
		}
		if (!bFilling && XpShown > XpFrac + 0.5f)
		{
			XpShown = 0.0f;
		}
		XpShown += ((bFilling ? 1.0f : XpFrac) - XpShown) * (1.0f - FMath::Exp(-9.0f * HudDt));
		const float Flare = LevelAge >= 0.0f && LevelAge < 0.8f ? 1.0f - LevelAge / 0.8f : 0.0f;
		Bar(P, BX, L.H - 146.0f * S - Flare * 1.0f * S, BW, (2.0f + 2.5f * Flare) * S, XpShown, A(Gold, 0.8f + 0.2f * Flare), 0.8f, 0.5f * S);
	}
	P.Flush();
	// the words
	if (Player->GetMaxShield() > 0.0f)
	{
		Type.Caps(TEXT("Shield"), BX, ShieldY - 17.0f * S, Type.Small, 0.95f * S, Dim, 2.2f * S);
		Type.Draw(FString::Printf(TEXT("%d"), FMath::CeilToInt(Player->GetShield())), BX + BW + 10.0f * S, ShieldY - 7.0f * S, Type.Large, 1.5f * S, Ink);
	}
	Type.Caps(TEXT("Health"), BX, HealthY - 17.0f * S, Type.Small, 0.95f * S, Dim, 2.2f * S);
	Type.Draw(FString::Printf(TEXT("%d"), FMath::CeilToInt(Player->GetHealth())), BX + BW + 10.0f * S, HealthY - 7.0f * S, Type.Large, 1.5f * S, bLow ? A(Hurt, LowPulse) : Ink);
	const USOAbilitySet* Kit = Player->GetAbilitySet();
	if (Kit && !Kit->DisplayName.IsEmpty())
	{
		Type.Caps(Kit->DisplayName.ToString(), BX, L.H - 164.0f * S, Type.Small, 1.05f * S, Gold, 3.0f * S);
	}
	if (Inventory)
	{
		Type.Caps(FString::Printf(TEXT("Level %d"), Inventory->GetLevel()), BX + BW, L.H - 164.0f * S, Type.Small, 1.0f * S, Dim, 2.0f * S, 1.0f);
	}
}

// ---------------------------------------------------------------------------------------------------------------------
// Bottom centre: the abilities and the ultimate

void ASOHUD::DrawAbilities(const FLayout& L)
{
	const ASOCharacter* Player = Cast<ASOCharacter>(GetOwningPawn());
	if (!Player || !Player->GetAbilitySet())
	{
		return;
	}
	const float S = L.S;
	FPainter P(Canvas);
	FType Type(Canvas);
	const bool bJammed = Player->HasStatus(SOTags::Status_Jam);
	const FLinearColor KitLight = Player->GetAbilityColor();
	const float Y = L.H - 100.0f * S;
	const float UltFrac = Player->GetMaxUltimate() > 0.0f ? Player->GetUltimate() / Player->GetMaxUltimate() : 0.0f;
	const bool bUltFull = UltFrac >= 0.995f;
	// the three cells left of the middle, the ultimate's diamond right of them
	const ESOAbilitySlot Order[] = { ESOAbilitySlot::Grenade, ESOAbilitySlot::Melee, ESOAbilitySlot::Class };
	for (int32 k = 0; k < 3; ++k)
	{
		const ESOAbilitySlot Slot = Order[k];
		int32 Charges = 0, MaxCharges = 0;
		float Left = 0.0f, Cooldown = 0.0f;
		if (!Player->GetAbilityState(Slot, Charges, MaxCharges, Left, Cooldown))
		{
			continue;
		}
		const int32 i = static_cast<int32>(Slot);
		const bool bReady = Charges > 0 && !bJammed;
		if (bReady && !bSlotWasReady[i])
		{
			SlotReadyAt[i] = L.Now;
		}
		bSlotWasReady[i] = bReady;
		const FVector2D C(L.CX - 128.0f * S + k * 70.0f * S, Y);
		const float R = 28.0f * S;
		const TArray<FVector2D> Cell = Hex(C, R);
		P.FillFan(C, Cell, bReady ? A(KitLight, 0.26f) : A(Glass, 0.95f), bReady ? A(KitLight, 0.05f) : A(GlassDeep, 0.95f));
		if (!bReady && Cooldown > 0.0f)
		{
			P.Sweep(Cell, C, FMath::Clamp(1.0f - Left / Cooldown, 0.0f, 1.0f), A(KitLight, 0.18f));
		}
		P.Stroke(Cell, bReady ? KitLight : (bJammed ? A(Hurt, 0.8f) : A(Line, 0.9f)), 1.4f * S);
		SlotGlyph(P, Slot, C, 11.0f * S, bReady ? Ink : A(Dim, 0.55f), 1.9f * S);
		if (bJammed)
		{
			ConditionGlyph(P, 4, C, 10.0f * S, A(Hurt, 0.9f), 2.2f * S);
		}
		// the pulse as it comes ready
		const float Age = L.Now - SlotReadyAt[i];
		if (Age >= 0.0f && Age < 0.6f)
		{
			P.Stroke(Hex(C, R + Age * 40.0f * S), A(Gold, (1.0f - Age / 0.6f) * 0.9f), 2.0f * S);
		}
		P.Flush();
		if (!bReady && Left > 0.0f)
		{
			Type.DrawCentred(Left >= 10.0f ? FString::Printf(TEXT("%d"), FMath::CeilToInt(Left)) : FString::Printf(TEXT("%.1f"), Left), C.X, C.Y + 10.0f * S, Type.Small, 1.05f * S, Ink);
		}
		if (MaxCharges > 1)
		{
			Type.Draw(FString::Printf(TEXT("%d"), Charges), C.X + R * 0.72f, C.Y - R * 1.05f, Type.Small, 0.95f * S, bReady ? Ink : Dim);
		}
		Type.Caps(SlotKey(Slot), C.X, C.Y + R + 8.0f * S, Type.Small, 1.0f * S, bReady ? Ink : Dim, 0.0f, 0.5f);
	}
	// the ultimate: a bigger diamond that fills as it charges, gold when it is there
	{
		int32 Charges = 0, MaxCharges = 0;
		float Left = 0.0f, Cooldown = 0.0f;
		const bool bHas = Player->GetAbilityState(ESOAbilitySlot::Ultimate, Charges, MaxCharges, Left, Cooldown) && Player->GetMaxUltimate() > 0.0f;
		if (bHas)
		{
			const bool bReady = bUltFull && Charges > 0 && !bJammed;
			if (bReady && !bUltimateWasReady)
			{
				UltimateReadyAt = L.Now;
				USOSoundLibrary::Play2D(this, TEXT("ui_open"), 0.4f, 0.4f);
			}
			bUltimateWasReady = bReady;
			const FVector2D C(L.CX + 116.0f * S, Y);
			const float R = 38.0f * S;
			const float Pulse = bReady ? 0.75f + 0.25f * FMath::Abs(FMath::Sin(L.Now * 3.0f)) : 1.0f;
			const TArray<FVector2D> Cell = Diamond(C, R, R);
			P.FillFan(C, Cell, bReady ? A(Gold, 0.35f * Pulse) : A(Glass, 0.95f), bReady ? A(Gold, 0.08f) : A(GlassDeep, 0.95f));
			if (!bReady)
			{
				// the charge rising from the diamond's foot
				const float Fill = FMath::Clamp(UltFrac, 0.0f, 1.0f);
				const float Top = C.Y + R - 2.0f * R * Fill;
				TArray<FVector2D> Cut;
				for (int32 j = 0; j < 4; ++j)
				{
					const FVector2D& A0 = Cell[j];
					const FVector2D& A1 = Cell[(j + 1) % 4];
					if (A0.Y >= Top) { Cut.Add(A0); }
					if ((A0.Y < Top) != (A1.Y < Top))
					{
						const float T = (Top - A0.Y) / (A1.Y - A0.Y);
						Cut.Add(A0 + (A1 - A0) * T);
					}
				}
				if (Cut.Num() >= 3)
				{
					P.Fill(Cut, A(Gold, 0.22f));
				}
			}
			P.Stroke(Cell, bReady ? A(Gold, Pulse) : A(Line, 0.9f), 1.6f * S);
			if (bReady)
			{
				SlotGlyph(P, ESOAbilitySlot::Ultimate, C, 14.0f * S, A(FLinearColor::White, Pulse), 2.0f * S);
			}
			const float Age = L.Now - UltimateReadyAt;
			if (Age >= 0.0f && Age < 0.8f)
			{
				P.Stroke(Diamond(C, R + Age * 60.0f * S, R + Age * 60.0f * S), A(Gold, (1.0f - Age / 0.8f) * 0.9f), 2.5f * S);
			}
			P.Flush();
			Type.Caps(SlotKey(ESOAbilitySlot::Ultimate), C.X, C.Y + R + 8.0f * S, Type.Small, 1.0f * S, bReady ? Gold : Dim, 0.0f, 0.5f);
			if (!bReady)
			{
				Type.DrawCentred(FString::Printf(TEXT("%d%%"), FMath::FloorToInt(UltFrac * 100.0f)), C.X, C.Y - 8.0f * S, Type.Medium, 1.1f * S, Ink);
			}
		}
		// its meter under the row, and the word
		if (bHas)
		{
			const float MX = L.CX - 160.0f * S, MY = L.H - 40.0f * S, MW = 320.0f * S;
			Bar(P, MX, MY, MW, 4.0f * S, UltFrac, bUltFull ? Gold : A(Cyan, 0.9f), 1.0f, 0.8f * S);
			if (bUltFull)
			{
				P.Fill(Rectangle(MX, MY - 2.0f * S, MW, 8.0f * S), A(Gold, 0.12f + 0.1f * FMath::Abs(FMath::Sin(L.Now * 3.0f))));
			}
			P.Flush();
			if (bUltFull)
			{
				Type.Caps(TEXT("Ultimate ready"), L.CX, L.H - 30.0f * S, Type.Small, 1.0f * S, A(Gold, 0.8f + 0.2f * FMath::Abs(FMath::Sin(L.Now * 3.0f))), 3.0f * S, 0.5f);
			}
			else
			{
				Type.Caps(TEXT("Ultimate"), L.CX, L.H - 30.0f * S, Type.Small, 0.9f * S, Dim, 2.6f * S, 0.5f);
			}
		}
	}
}

// ---------------------------------------------------------------------------------------------------------------------
// Bottom right: the three weapon cards, the held gun's panel, what the hands carry besides

void ASOHUD::DrawWeapon(const FLayout& L)
{
	const ASOCharacter* Player = Cast<ASOCharacter>(GetOwningPawn());
	const ASOWeapon* Weapon = Player ? Player->GetWeapon() : nullptr;
	if (!Player || !Weapon)
	{
		return;
	}
	const float S = L.S;
	FPainter P(Canvas);
	FType Type(Canvas);
	const USOInventoryComponent* Inventory = FeedInventory.Get();
	const USOWeaponData* Data = Weapon->GetData();
	const USOLootTables* Tables = USOLootLibrary::GetTables();
	const float W = 400.0f * S, H = 124.0f * S;
	const float X = L.X1 - 40.0f * S - W, Y = L.H - 50.0f * S - H;
	const FSOWeaponInstance& Held = Weapon->GetInstance();
	const FLinearColor HeldCol = RarityColour(Held.Rarity);

	// the three cards
	for (int32 Slot = 0; Slot < USOInventoryComponent::NumSlots; ++Slot)
	{
		const FSOWeaponInstance* Copy = Inventory ? Inventory->GetEquipped(Slot) : nullptr;
		const bool bActive = Inventory ? Inventory->GetActiveSlot() == Slot : Slot == 0;
		const float CW = 112.0f * S, CH = 50.0f * S, CX = X + W - (3 - Slot) * (CW + 8.0f * S) + 8.0f * S, CY = Y - CH - 10.0f * S;
		const float Alpha = bActive ? 1.0f : 0.6f;
		const FLinearColor Col = Copy ? RarityColour(Copy->Rarity) : A(Dim, 0.5f);
		Panel(P, Plate(CX, CY, CW, CH, 6.0f * S), 1.0f * S, Alpha, bActive ? A(Cyan, 0.9f) : Line);
		P.Fill(Rectangle(CX + 6.0f * S, CY + CH - 2.0f * S, CW - 8.0f * S, 2.0f * S), A(Col, Alpha));
		P.Flush();
		Type.Draw(FString::FromInt(Slot + 1), CX + 5.0f * S, CY + 3.0f * S, Type.Small, 0.95f * S, bActive ? Ink : Dim);
		const FName Arch = Copy ? Copy->Archetype : (Slot == 0 && Data ? Data->Archetype : NAME_None);
		if (UTexture2D* Icon = IconOf(Arch))
		{
			DrawTexture(Icon, CX + 18.0f * S, CY + 4.0f * S, 88.0f * S, 44.0f * S, 0.0f, 0.0f, 1.0f, 1.0f, FLinearColor(1, 1, 1, bActive ? 1.0f : 0.5f));
		}
		else if (!Copy)
		{
			Type.DrawCentred(TEXT("—"), CX + CW * 0.55f, CY + 14.0f * S, Type.Medium, 1.0f * S, A(Dim, 0.5f));
		}
	}

	// the held gun's panel
	Panel(P, Plate(X, Y, W, H, 10.0f * S), 1.0f * S);
	P.Segment(FVector2D(X + W - 80.0f * S, Y), FVector2D(X + W, Y), A(HeldCol, 0.9f), 1.5f * S);
	P.Fill(Diamond(FVector2D(X + W - 62.0f * S, Y + 19.0f * S), 5.0f * S, 5.0f * S), Gold);
	// the reload along the panel's foot; the heat under the count
	if (Weapon->IsReloading())
	{
		P.Fill(Rectangle(X + 2.0f * S, Y + H - 4.0f * S, (W - 4.0f * S) * Weapon->GetReloadProgress(), 3.0f * S), A(Cyan, 0.9f));
	}
	const bool bHeat = Weapon->HasHeat();
	if (bHeat)
	{
		const float Heat = Weapon->GetHeat();
		const FLinearColor Cool(1.0f, 0.5f, 0.1f), Hot(1.0f, 0.93f, 0.8f);
		const FLinearColor C = FMath::Lerp(Cool, Hot, FMath::Clamp((Heat - ASOWeapon::HeatMedium) / (1.0f - ASOWeapon::HeatMedium), 0.0f, 1.0f));
		Bar(P, X + 16.0f * S, Y + H - 16.0f * S, 150.0f * S, 4.0f * S, Heat, C, 1.0f, 0.8f * S);
	}
	P.Flush();
	const FString Name = Held.Name.IsEmpty() ? (Data ? Data->DisplayName.ToString() : FString(TEXT("-"))) : Held.Name;
	Type.Draw(Name, X + 16.0f * S, Y + 8.0f * S, Type.Large, 1.35f * S, Ink);
	const FSORarityInfo* Rar = RarityOf(Held.Rarity);
	FString LineText = Rar ? Rar->Name.ToString() : FString();
	if (Data)
	{
		LineText += (LineText.IsEmpty() ? TEXT("") : TEXT("  ·  ")) + Data->ClassName.ToString() + TEXT("  ·  ") + Data->DisplayName.ToString();
	}
	Type.Caps(LineText, X + 16.0f * S, Y + 38.0f * S, Type.Small, 0.85f * S, A(HeldCol, 0.9f), 1.4f * S);
	Type.Draw(FString::FromInt(Held.Power), X + W - 52.0f * S, Y + 8.0f * S, Type.Medium, 1.3f * S, Gold);
	// the count: the magazine big, the reserve after it
	const FString Mag = FString::FromInt(Weapon->GetMag());
	const float MagW = Type.Draw(Mag, X + 14.0f * S, Y + 54.0f * S, Type.Large, 2.6f * S, Weapon->GetMag() == 0 ? Hurt : Ink);
	Type.Draw(FString::Printf(TEXT("/ %d"), Weapon->GetReserve()), X + 22.0f * S + MagW, Y + 78.0f * S, Type.Medium, 1.25f * S, Dim);
	if (Weapon->GetRampageStacks() > 0)
	{
		Type.Caps(FString::Printf(TEXT("Rampage x%d"), Weapon->GetRampageStacks()), X + 16.0f * S, Y + H - 30.0f * S, Type.Small, 0.85f * S, FLinearColor(1.0f, 0.5f, 0.2f), 1.2f * S);
	}
	if (bHeat)
	{
		const FLinearColor Cool(1.0f, 0.5f, 0.1f), Hot(1.0f, 0.93f, 0.8f);
		if (Weapon->IsVenting())
		{
			Type.Caps(TEXT("Venting"), X + 174.0f * S, Y + H - 20.0f * S, Type.Small, 0.85f * S, Hot, 1.4f * S);
		}
		else if (Weapon->IsCondensing())
		{
			// rounds condensing from the reserve (the Sarketh's guns never reload): the word pulses with them
			Type.Caps(TEXT("Condensing"), X + 174.0f * S, Y + H - 20.0f * S, Type.Small, 0.85f * S, A(Cool, 0.55f + 0.45f * FMath::Sin(L.Now * 6.0f)), 1.4f * S);
		}
	}
	if (UTexture2D* Icon = IconOf(Data ? Data->Archetype : NAME_None))
	{
		DrawTexture(Icon, X + W - 180.0f * S, Y + 40.0f * S, 168.0f * S, 84.0f * S, 0.0f, 0.0f, 1.0f, 1.0f, FLinearColor(1, 1, 1, 0.95f));
	}

	// under the panel: the grenade's charges, the melee style, the flashlight
	{
		const float RY = L.H - 38.0f * S;
		float RX = X + 2.0f * S;
		int32 Charges = 0, MaxCharges = 0;
		float Left = 0.0f, Cooldown = 0.0f;
		if (Player->GetAbilityState(ESOAbilitySlot::Grenade, Charges, MaxCharges, Left, Cooldown))
		{
			SlotGlyph(P, ESOAbilitySlot::Grenade, FVector2D(RX + 10.0f * S, RY + 10.0f * S), 8.0f * S, Charges > 0 ? Ink : Dim, 1.5f * S);
			P.Flush();
			Type.Draw(FString::FromInt(Charges), RX + 26.0f * S, RY + 1.0f * S, Type.Medium, 1.2f * S, Charges > 0 ? Ink : Dim);
			RX += 60.0f * S;
		}
		// the melee style: a blade's own picture, or the fists
		const FSOMeleeStyle* Style = Player->GetMeleeStyle();
		UTexture2D* StyleIcon = Style && !Style->Icon.IsNull() ? Style->Icon.LoadSynchronous() : nullptr;
		if (StyleIcon)
		{
			DrawTexture(StyleIcon, RX, RY - 4.0f * S, 56.0f * S, 28.0f * S, 0.0f, 0.0f, 1.0f, 1.0f, FLinearColor(1, 1, 1, Player->IsFists() ? 1.0f : 0.7f));
			RX += 60.0f * S;
		}
		else
		{
			// the fists: a knuckle line
			const FVector2D F(RX + 10.0f * S, RY + 10.0f * S);
			const FLinearColor FC = Player->IsFists() ? Ink : Dim;
			P.Stroke(Plate4(F.X - 8.0f * S, F.Y - 5.0f * S, 16.0f * S, 11.0f * S, 3.0f * S), FC, 1.5f * S);
			for (int32 k = 0; k < 3; ++k)
			{
				P.Segment(FVector2D(F.X - 4.0f * S + k * 4.0f * S, F.Y - 5.0f * S), FVector2D(F.X - 4.0f * S + k * 4.0f * S, F.Y - 1.0f * S), FC, 1.2f * S);
			}
			P.Flush();
			RX += 28.0f * S;
		}
		Type.Draw(TEXT("4"), RX, RY + 1.0f * S, Type.Medium, 1.2f * S, Player->IsFists() ? Ink : Dim);
		// the flashlight's key, lit when it is on
		const float FX = X + W - 24.0f * S;
		const bool bOn = Player->IsFlashlightOn();
		P.Fill(Plate4(FX, RY, 22.0f * S, 20.0f * S, 3.0f * S), bOn ? A(Gold, 0.3f) : A(Glass, 0.9f));
		P.Stroke(Plate4(FX, RY, 22.0f * S, 20.0f * S, 3.0f * S), bOn ? Gold : Line, 1.0f * S);
		P.Flush();
		Type.DrawCentred(TEXT("F"), FX + 11.0f * S, RY + 3.0f * S, Type.Small, 1.0f * S, bOn ? Gold : Dim);
	}

	// the word at the crosshair when the gun is empty
	if (!Weapon->IsReloading() && Weapon->GetMag() == 0 && Weapon->GetReserve() > 0 && !Weapon->IsCondensing() && !Weapon->IsVenting())
	{
		Type.Caps(TEXT("Reload"), L.CX, L.H * 0.5f + 34.0f * S, Type.Medium, 1.0f * S, Hurt, 2.0f * S, 0.5f);
	}
}

// ---------------------------------------------------------------------------------------------------------------------
// The crosshair: tight at rest, wide on the move, a point while aiming, red on a hostile

void ASOHUD::DrawCrosshair(const FLayout& L)
{
	const ASOCharacter* Player = Cast<ASOCharacter>(GetOwningPawn());
	if (!Player)
	{
		return;
	}
	const ASOWeapon* Weapon = Player->GetWeapon();
	const float S = L.S;
	FPainter P(Canvas);
	const float CX = L.W * 0.5f, CY = L.H * 0.5f, T = FMath::Max(2.0f * S, 1.5f); // never thinner than a pixel and a half
	const bool bLocked = Locked.IsValid();
	if (Player->IsFists())
	{
		// hand to hand: a point and a short bracket either side (the reach is the body's, not a gun's cone)
		const float G = 10.0f * S, Ln = 6.0f * S;
		const FLinearColor C = bLocked ? Lock : Ink;
		P.Fill(Diamond(FVector2D(CX, CY), 2.0f * S, 2.0f * S), C);
		for (const float Side : { -1.0f, 1.0f })
		{
			P.Stroke({ FVector2D(CX + Side * G, CY - Ln), FVector2D(CX + Side * (G + 3.0f * S), CY), FVector2D(CX + Side * G, CY + Ln) }, C, T, false);
		}
		return;
	}
	// First person it fades out over the first third of aiming, so looking through the sights (or an optic's window)
	// shows only the sight's own dot or post, and comes back as the gun comes down. Third person nothing lines up with
	// the eye, so it stays while aiming over the shoulder, drawn in to a point; only the scope view (a magnified
	// optic, either view) takes it away for the scope's own reticle.
	const bool bShoulder = Player->UsesShoulderCrosshair();
	const float Aim = Player->IsScopeView() ? 1.0f : Player->GetAimProgress();
	const float Fade = Player->IsScopeView() ? 1.0f : (bShoulder ? 0.0f : FMath::Clamp(Aim * 3.0f, 0.0f, 1.0f));
	if (Fade > 0.99f)
	{
		return;
	}
	const float Spread = Weapon ? Weapon->GetStats().Spread * Player->GetSpreadScale() : 1.0f;
	const float Move = FMath::Clamp(Player->GetVelocity().Size() / 600.0f, 0.0f, 1.0f);
	const float Open = (6.0f + Spread * 9.0f + Move * 5.0f) * S * (bShoulder ? 1.0f - 0.55f * Aim : 1.0f);
	const float Len = FMath::Max(7.0f * S, 5.0f) * (bShoulder ? 1.0f - 0.4f * Aim : 1.0f);
	// each set's own crosshair, in its light (mixed with white so it reads on anything): the Sarketh's a lozenge of
	// four ticks under the brow's point, the Requiem's three closing in, the light guns' four round a point, the living
	// guns' two curved brackets, a human gun's plain four; on a hostile every one turns red
	using namespace SOSightTheme;
	const USOWeaponData* CrossData = Weapon ? Weapon->GetData() : nullptr;
	const ETheme Theme = Of(CrossData);
	const FLinearColor Tint = bLocked ? Lock : (Theme == ETheme::Kinetic ? Ink : FMath::Lerp(Ink, Lit(Glow(CrossData), Ink.A), 0.6f));
	const FLinearColor C(Tint.R, Tint.G, Tint.B, Ink.A * (1.0f - Fade));
	auto Tick = [&](float Deg, float From, float To)
	{
		const FVector2D D(FMath::Cos(FMath::DegreesToRadians(Deg)), FMath::Sin(FMath::DegreesToRadians(Deg)));
		P.Segment(FVector2D(CX + D.X * From, CY + D.Y * From), FVector2D(CX + D.X * To, CY + D.Y * To), C, T);
	};
	switch (Theme)
	{
	case ETheme::Sarketh:
		for (const float Deg : { 45.0f, 135.0f, 225.0f, 315.0f })
		{
			Tick(Deg, Open, Open + Len);
		}
		Tick(270.0f, Open + Len * 0.4f, Open + Len * 1.3f);
		P.Fill(Diamond(FVector2D(CX, CY), 2.0f * S, 2.0f * S), C);
		break;
	case ETheme::Void:
		for (const float Deg : { 90.0f, 210.0f, 330.0f })
		{
			Tick(Deg, Open, Open + Len * 1.2f);
		}
		P.Fill(Rectangle(CX - 1.0f * S, CY - 1.0f * S, 2.0f * S, 2.0f * S), C);
		break;
	case ETheme::Living:
		for (const float Side : { 0.0f, 180.0f })
		{
			for (int32 k = 0; k < 4; ++k)
			{
				const float A0 = FMath::DegreesToRadians(Side - 40.0f + k * 20.0f), A1 = A0 + FMath::DegreesToRadians(20.0f);
				const float Rr = Open + Len * 0.5f;
				P.Segment(FVector2D(CX + FMath::Cos(A0) * Rr, CY + FMath::Sin(A0) * Rr), FVector2D(CX + FMath::Cos(A1) * Rr, CY + FMath::Sin(A1) * Rr), C, T);
			}
		}
		P.Fill(Rectangle(CX - 1.5f * S, CY - 1.5f * S, 3.0f * S, 3.0f * S), C);
		break;
	default:
		for (const float Deg : { 0.0f, 90.0f, 180.0f, 270.0f })
		{
			Tick(Deg, Open, Open + Len);
		}
		if (Theme == ETheme::Light || (bShoulder && Aim > 0.3f))
		{
			P.Fill(Rectangle(CX - 1.0f * S, CY - 1.0f * S, 2.0f * S, 2.0f * S), C);
		}
		break;
	}
	// over the shoulder, aimed: a fine ring closes on the point
	if (bShoulder && Aim > 0.05f)
	{
		P.Ring(FVector2D(CX, CY), Open + Len + 3.0f * S, Open + Len + 3.0f * S + 1.0f * S, A(C, 0.5f * Aim), A(C, 0.5f * Aim), 0.0f, UE_TWO_PI, 48);
	}
	// the lock: a bracket at the four corners, closing on the target
	if (bLocked)
	{
		const float Age = FMath::Clamp((L.Now - LockedAt) / 0.15f, 0.0f, 1.0f);
		const float B = Open + Len + (14.0f - 6.0f * Age) * S, K = 5.0f * S;
		for (const float SX : { -1.0f, 1.0f })
		{
			for (const float SY : { -1.0f, 1.0f })
			{
				P.Stroke({ FVector2D(CX + SX * (B - K), CY + SY * B), FVector2D(CX + SX * B, CY + SY * B), FVector2D(CX + SX * B, CY + SY * (B - K)) }, A(Lock, 0.9f * (1.0f - Fade)), T, false);
			}
		}
	}
	P.Flush();
	// the hit marker
	const float HitAge = L.Now - LastHitTime;
	if (HitAge < 0.18f)
	{
		const FLinearColor HC = bLastHitKill ? Hurt : (bLastHitCrit ? FLinearColor(1.0f, 0.85f, 0.2f, 1.0f) : Ink);
		const float A0 = 6.0f * S, B0 = 13.0f * S;
		for (const float SX : { -1.0f, 1.0f })
		{
			for (const float SY : { -1.0f, 1.0f })
			{
				P.Segment(FVector2D(CX + SX * B0, CY + SY * B0), FVector2D(CX + SX * A0, CY + SY * A0), HC, 2.5f * S);
			}
		}
	}
	// a kill: the marker bursts outward; kills close on each other count up beside it
	const float KillAge = L.Now - KillAt;
	if (KillAge >= 0.0f && KillAge < 0.35f)
	{
		const float K = KillAge / 0.35f;
		const float R = (12.0f + 30.0f * (1.0f - FMath::Square(1.0f - K))) * S;
		const FLinearColor KC = A(Hurt, (1.0f - K) * 0.9f);
		P.Ring(FVector2D(CX, CY), R - 2.0f * S, R, KC, KC);
	}
	if (KillStreak >= 2 && KillAge >= 0.0f && KillAge < 1.4f)
	{
		P.Flush();
		FType KillType(Canvas);
		KillType.Caps(FString::Printf(TEXT("x%d"), KillStreak), CX + 24.0f * S, CY - 32.0f * S, KillType.Medium, 1.1f * S,
			A(Gold, FMath::Clamp((1.4f - KillAge) / 0.4f, 0.0f, 1.0f)), 2.0f * S);
	}
}

// ---------------------------------------------------------------------------------------------------------------------
// Hand to hand: the count of blows landed one after another (a fighter's combo), the parry, the guard

void ASOHUD::DrawMelee(const FLayout& L)
{
	const ASOCharacter* Player = Cast<ASOCharacter>(GetOwningPawn());
	if (!Player || !Player->IsFists())
	{
		return;
	}
	const float S = L.S;
	FType Type(Canvas);
	const int32 Hits = Player->GetComboHits();
	const float Age = static_cast<float>(Player->GetComboAge());
	if (Hits >= 2 && Age < 1.6f)
	{
		const float Alpha = FMath::Clamp((1.6f - Age) / 0.4f, 0.0f, 1.0f);
		const float Pop = 1.0f + 0.25f * FMath::Clamp(1.0f - Age / 0.12f, 0.0f, 1.0f);    // (each hit punches the number)
		const FString Count = FString::Printf(TEXT("%d"), Hits);
		const FVector2D Sz = Type.Size(Count, Type.Large, 2.6f * S * Pop);
		Type.Draw(Count, L.W * 0.70f - Sz.X, L.H * 0.36f, Type.Large, 2.6f * S * Pop, FLinearColor(1.0f, 0.78f, 0.35f, Alpha));
		Type.Caps(TEXT("Hits"), L.W * 0.70f + 8.0f * S, L.H * 0.36f + Sz.Y * 0.45f, Type.Medium, 1.1f * S, FLinearColor(1.0f, 0.93f, 0.85f, Alpha), 2.0f * S);
	}
	const float ParryAge = static_cast<float>(L.Now - Player->GetParryShownAt());
	if (ParryAge < 0.7f)
	{
		const float Alpha = FMath::Clamp((0.7f - ParryAge) / 0.3f, 0.0f, 1.0f);
		Type.Caps(TEXT("Parry"), L.W * 0.5f, L.H * 0.30f, Type.Large, 1.8f * S, FLinearColor(1.0f, 0.85f, 0.4f, Alpha), 4.0f * S, 0.5f);
	}
	if (Player->IsBlocking())
	{
		Type.Caps(TEXT("Guard"), L.W * 0.5f, L.H * 0.5f + 26.0f * S, Type.Medium, 0.9f * S, FLinearColor(0.9f, 0.95f, 1.0f, 0.8f), 2.0f * S, 0.5f);
	}
}

// ---------------------------------------------------------------------------------------------------------------------
// Hit feedback: the numbers, the loot beams, the screen's edge

void ASOHUD::OnHitConfirmed(bool bCrit, bool bKilled)
{
	LastHitTime = GetWorld()->GetTimeSeconds();
	bLastHitCrit = bCrit;
	bLastHitKill = bKilled;
	if (bKilled)
	{
		KillStreak = LastHitTime - KillAt < 4.0f ? KillStreak + 1 : 1;
		KillAt = LastHitTime;
	}
	USOSoundLibrary::Play2D(this, bLastHitKill ? TEXT("hit_kill") : (bLastHitCrit ? TEXT("hit_crit") : TEXT("hit_tick")), 0.55f, 0.02f);
}

void ASOHUD::OnHitReported(const FSOHitReport& Report)
{
	ShowHit(Report);
}

void ASOHUD::ShowHit(const FSOHitReport& Report)
{
	if (Report.Amount < 0.5f)
	{
		return;
	}
	const float Now = GetWorld()->GetTimeSeconds();
	// normal, on the shield, precise (the head), critical (a weak point worth more than the head, or the precise shot
	// that ended it)
	const uint8 Kind = Report.bCrit ? ((Report.Precision > 1.01f || Report.bKilled) ? 3 : 2) : (Report.bShield ? 1 : 0);
	// the pellets of one shot, or two rounds of a burst on the same body, add up into one number
	for (FDamageNumber& N : DamageNumbers)
	{
		if (N.Kind == Kind && Now - N.Time < 0.12f && FVector::Dist(N.Point, Report.Point) < 60.0f)
		{
			N.Amount += Report.Amount;
			N.bKilled |= Report.bKilled;
			N.Time = Now;
			return;
		}
	}
	FDamageNumber N;
	N.Point = Report.Point;
	N.Amount = Report.Amount;
	N.Kind = Kind;
	N.bKilled = Report.bKilled;
	N.Time = Now;
	N.Drift = FMath::FRandRange(-1.0f, 1.0f);
	DamageNumbers.Add(N);
	if (DamageNumbers.Num() > 24)
	{
		DamageNumbers.RemoveAt(0);
	}
}

void ASOHUD::DrawDamageNumbers(const FLayout& L)
{
	const float S = L.S;
	FType Type(Canvas);
	const float Life = 1.0f;
	for (int32 i = 0; i < DamageNumbers.Num(); ++i)
	{
		const FDamageNumber& N = DamageNumbers[i];
		const float Age = L.Now - N.Time;
		if (Age > Life)
		{
			DamageNumbers.RemoveAt(i--);
			continue;
		}
		const FVector Screen = Project(N.Point, true);
		if (Screen.Z <= 0.0f)
		{
			continue;
		}
		const float T = Age / Life;
		const float Alpha = FMath::Clamp((1.0f - T) / 0.4f, 0.0f, 1.0f);
		const float Rise = (1.0f - FMath::Pow(1.0f - T, 2.0f)) * 42.0f * S;
		const float Pop = 1.0f + 0.35f * FMath::Clamp(1.0f - Age / 0.1f, 0.0f, 1.0f);
		FLinearColor Col;
		float Scale;
		switch (N.Kind)
		{
		case 1: Col = FLinearColor(0.45f, 0.78f, 1.0f); Scale = 1.5f; break;
		case 2: Col = FLinearColor(1.0f, 0.86f, 0.25f); Scale = 1.9f; break;
		case 3: Col = FLinearColor(1.0f, 0.55f, 0.15f); Scale = 2.4f; break;
		default: Col = Ink; Scale = 1.5f; break;
		}
		if (N.bKilled)
		{
			Scale *= 1.15f;
		}
		const FString Text = FString::FromInt(FMath::RoundToInt(N.Amount));
		const float X = Screen.X + N.Drift * 20.0f * S + 14.0f * S, Y = Screen.Y - 30.0f * S - Rise;
		Type.Draw(Text, X, Y, Type.Large, Scale * S * Pop, A(Col, Alpha));
		if (N.Kind == 3)
		{
			Type.Caps(TEXT("Crit"), X + 2.0f * S, Y - 14.0f * S, Type.Small, 1.0f * S, A(Col, Alpha), 2.0f * S);
		}
	}
}

// ---------------------------------------------------------------------------------------------------------------------
// The loop's beats (the owner, 2026-11-20): what a kill paid, the level reached, an elite seen

void ASOHUD::DrawRewards(const FLayout& L)
{
	const float S = L.S;
	FType Type(Canvas);
	const float Life = 1.5f;
	const float X = L.CX + 56.0f * S, Y0 = L.H * 0.5f + 46.0f * S;   // (Y is each popup's baseline)
	for (int32 i = 0; i < Rewards.Num(); ++i)
	{
		const FRewardPop& R = Rewards[i];
		const float Age = L.Now - R.Time;
		if (Age > Life)
		{
			Rewards.RemoveAt(i--);
			continue;
		}
		const float T = Age / Life;
		const float Alpha = FMath::Min(1.0f, Age / 0.08f) * FMath::Clamp((1.0f - T) / 0.35f, 0.0f, 1.0f);
		const float Rise = (1.0f - FMath::Pow(1.0f - T, 2.5f)) * 34.0f * S;
		const float Pop = 1.0f + 0.3f * FMath::Clamp(1.0f - (L.Now - R.Bump) / 0.12f, 0.0f, 1.0f);
		FLinearColor Col;
		FString Word;
		switch (R.Kind)
		{
		case 1: Col = Cyan; Word = TEXT("credits"); break;
		case 2: Col = Dim; Word = TEXT("alloy"); break;
		default: Col = Gold; Word = TEXT("xp"); break;
		}
		const float Y = Y0 + R.Lane * 30.0f * S - Rise;
		// the number at the damage numbers' size, the word small on its baseline
		const FString Number = FString::Printf(TEXT("+%d"), R.Amount);
		const FVector2D NS = Type.Size(Number, Type.Large, 1.45f * S * Pop);
		const float WordH = Type.Size(TEXT("X"), Type.Small, 0.95f * S).Y;
		Type.Draw(Number, X, Y - NS.Y, Type.Large, 1.45f * S * Pop, A(Col, Alpha));
		Type.Caps(Word, X + NS.X + 7.0f * S, Y - WordH - 3.0f * S, Type.Small, 0.95f * S, A(Col, Alpha * 0.85f), 1.8f * S);
	}
}

void ASOHUD::DrawLevelUp(const FLayout& L)
{
	const float Age = L.Now - LevelUpAt;
	if (Age < 0.0f || Age > 3.0f)
	{
		return;
	}
	const float S = L.S;
	FPainter P(Canvas);
	FType Type(Canvas);
	const float In = FMath::Clamp(Age / 0.3f, 0.0f, 1.0f);
	const float Ease = 1.0f - FMath::Pow(1.0f - In, 3.0f);
	const float Out = FMath::Clamp((3.0f - Age) / 0.5f, 0.0f, 1.0f);
	const float Y = L.H * 0.34f;   // (under the elite's plate, over the crosshair: both may show at once)
	// a line of gold opening out from the middle, a soft light over it, the level above and what it allows under
	const float Half = 170.0f * S * Ease;
	P.Quad(FVector2D(L.CX - Half, Y - 1.0f * S), FVector2D(L.CX - Half, Y + 1.0f * S), FVector2D(L.CX, Y - 1.0f * S), FVector2D(L.CX, Y + 1.0f * S), A(Gold, 0.0f), A(Gold, 0.9f * Out));
	P.Quad(FVector2D(L.CX, Y - 1.0f * S), FVector2D(L.CX, Y + 1.0f * S), FVector2D(L.CX + Half, Y - 1.0f * S), FVector2D(L.CX + Half, Y + 1.0f * S), A(Gold, 0.9f * Out), A(Gold, 0.0f));
	P.Quad(FVector2D(L.CX - Half, Y - 48.0f * S), FVector2D(L.CX + Half, Y - 48.0f * S), FVector2D(L.CX - Half, Y), FVector2D(L.CX + Half, Y), A(Gold, 0.0f), A(Gold, 0.10f * Out * Ease));
	P.Flush();
	const float Scale = 1.0f + 0.25f * (1.0f - Ease);
	Type.Caps(FString::Printf(TEXT("Level %d"), LevelUpTo), L.CX, Y - 40.0f * S, Type.Large, 1.5f * S * Scale, A(Gold, Out * In), 6.0f * S, 0.5f);
	const USOProgressionTable& Rules = USOProgressionTable::Get();
	Type.Caps(FString::Printf(TEXT("Gear can be raised to %d"), Rules.PowerCap(LevelUpTo)), L.CX, Y + 8.0f * S, Type.Small, 1.0f * S,
		A(Ink, 0.8f * Out * FMath::Clamp((Age - 0.25f) / 0.3f, 0.0f, 1.0f)), 2.4f * S, 0.5f);
}

void ASOHUD::DrawEliteIntro(const FLayout& L)
{
	const float Age = L.Now - EliteAt;
	if (Age < 0.0f || Age > 3.2f)
	{
		return;
	}
	const float S = L.S;
	FPainter P(Canvas);
	FType Type(Canvas);
	const float In = 1.0f - FMath::Pow(1.0f - FMath::Clamp(Age / 0.25f, 0.0f, 1.0f), 3.0f);
	const float Out = FMath::Clamp((3.2f - Age) / 0.4f, 0.0f, 1.0f);
	const float Alpha = In * Out;
	const float Y = L.H * 0.20f - (1.0f - In) * 12.0f * S;
	const float W = FMath::Max(Type.CapsWidth(EliteName, Type.Medium, 1.15f * S, 3.0f * S) + 64.0f * S, 240.0f * S);
	const TArray<FVector2D> Body = Plate(L.CX - W * 0.5f, Y, W, 44.0f * S, 8.0f * S);
	P.Fill(Body, A(Glass, Alpha));
	P.Stroke(Body, A(Lock, 0.7f * Alpha), 1.2f * S);
	// a red mark either side: the thing to fear
	P.Fill(Diamond(FVector2D(L.CX - W * 0.5f + 16.0f * S, Y + 22.0f * S), 4.0f * S, 7.0f * S), A(Lock, Alpha));
	P.Fill(Diamond(FVector2D(L.CX + W * 0.5f - 16.0f * S, Y + 22.0f * S), 4.0f * S, 7.0f * S), A(Lock, Alpha));
	P.Flush();
	Type.Caps(FString::Printf(TEXT("Elite  ·  %d"), EliteLevel), L.CX, Y + 5.0f * S, Type.Small, 0.9f * S, A(Lock, Alpha), 2.6f * S, 0.5f);
	Type.Caps(EliteName, L.CX, Y + 20.0f * S, Type.Medium, 1.15f * S, A(Ink, Alpha), 3.0f * S, 0.5f);
}

void ASOHUD::DrawLootBeams(const FLayout& L)
{
	const APawn* Pawn = GetOwningPawn();
	if (!Pawn)
	{
		return;
	}
	const float S = L.S;
	FPainter P(Canvas);
	FType Type(Canvas);
	for (TActorIterator<ASOLootPickup> It(GetWorld()); It; ++It)
	{
		const ASOLootPickup* Pick = *It;
		if (Pick->GetKind() != ESOPickupKind::Core)
		{
			continue;
		}
		const float Dist = FVector::Dist(Pick->GetActorLocation(), Pawn->GetActorLocation());
		if (Dist > 9000.0f)
		{
			continue;
		}
		const FVector Screen = Project(Pick->GetActorLocation() + FVector(0, 0, 18.0f), true);
		if (Screen.Z <= 0.0f)
		{
			continue;
		}
		const int32 Rarity = Pick->GetRarity();
		const FLinearColor Col = RarityColour(Rarity);
		// a shaft of its light rising from it, taller and wider the rarer; a diamond at its foot
		const float Height = (110.0f + Rarity * 22.0f) * S / (1.0f + Dist / 4000.0f);
		const float Width = (2.0f + Rarity * 0.8f) * S;
		const float Breath = 0.85f + 0.15f * FMath::Sin(L.Now * 2.5f + Rarity);
		const FVector2D Foot(Screen.X, Screen.Y);
		P.Quad(Foot + FVector2D(-Width * 2.5f, 0), Foot + FVector2D(Width * 2.5f, 0), Foot + FVector2D(-Width * 1.2f, -Height), Foot + FVector2D(Width * 1.2f, -Height), A(Col, 0.22f * Breath), A(Col, 0.0f));
		P.Quad(Foot + FVector2D(-Width * 0.6f, 0), Foot + FVector2D(Width * 0.6f, 0), Foot + FVector2D(-Width * 0.25f, -Height), Foot + FVector2D(Width * 0.25f, -Height), A(FLinearColor::White, 0.75f * Breath), A(Col, 0.0f));
		P.Fill(Diamond(Foot, 5.0f * S, 7.0f * S), A(Col, 0.95f));
		P.Stroke(Diamond(Foot, 8.0f * S, 11.0f * S), A(Col, 0.6f), 1.0f * S);
		if (Dist < 1500.0f)
		{
			if (const FSORarityInfo* Rar = RarityOf(Rarity))
			{
				P.Flush();
				Type.Caps(Rar->Name.ToString(), Screen.X, Screen.Y - Height - 14.0f * S, Type.Small, 0.9f * S, A(Col, FMath::Clamp((1500.0f - Dist) / 400.0f, 0.0f, 1.0f)), 1.6f * S, 0.5f);
			}
		}
	}
}

void ASOHUD::DrawScreenEdge(const FLayout& L)
{
	const ASOCharacter* Player = Cast<ASOCharacter>(GetOwningPawn());
	if (!Player)
	{
		return;
	}
	const float S = L.S;
	FPainter P(Canvas);
	// a band of colour fading in from each edge
	auto Bands = [&](float Depth, const FLinearColor& Col)
	{
		const FLinearColor Clear = A(Col, 0.0f);
		P.Quad(FVector2D(0, 0), FVector2D(L.W, 0), FVector2D(0, Depth), FVector2D(L.W, Depth), Col, Clear);
		P.Quad(FVector2D(0, L.H), FVector2D(L.W, L.H), FVector2D(0, L.H - Depth), FVector2D(L.W, L.H - Depth), Col, Clear);
		P.Quad(FVector2D(0, 0), FVector2D(0, L.H), FVector2D(Depth, 0), FVector2D(Depth, L.H), Col, Clear);
		P.Quad(FVector2D(L.W, 0), FVector2D(L.W, L.H), FVector2D(L.W - Depth, 0), FVector2D(L.W - Depth, L.H), Col, Clear);
	};
	// a hit: the shield's cells light along the edge in blue; the body's loss a red surge
	const float DamageAge = L.Now - LastDamageTime;
	if (DamageAge < 0.55f)
	{
		const float K = 1.0f - DamageAge / 0.55f;
		if (bLastDamageHealth)
		{
			Bands(220.0f * S, A(HealthRed, 0.45f * K));
			P.Fill(Rectangle(0, 0, L.W, L.H), A(HealthRed, 0.07f * K));
		}
		else
		{
			Bands(140.0f * S, A(ShieldBlue, 0.28f * K));
			// the cells: hexagons along the border, each lit a little differently
			const float R = 26.0f * S, Step = R * 1.76f;
			int32 n = 0;
			auto Cell = [&](const FVector2D& C)
			{
				const float Own = 0.35f + 0.65f * FMath::Frac(FMath::Sin(n * 12.9898f + 78.233f) * 43758.5453f);
				const float Fade = FMath::Clamp(K * 1.5f - (1.0f - Own) * 0.5f, 0.0f, 1.0f);
				P.Stroke(Hex(C, R * 0.92f, UE_PI / 6.0f), A(ShieldBlue, 0.55f * Fade), 1.2f * S);
				++n;
			};
			for (float X = R; X < L.W + R; X += Step)
			{
				Cell(FVector2D(X, R * 0.3f));
				Cell(FVector2D(X + Step * 0.5f, R * 0.3f + R * 1.5f));
				Cell(FVector2D(X, L.H - R * 0.3f));
				Cell(FVector2D(X + Step * 0.5f, L.H - R * 0.3f - R * 1.5f));
			}
			for (float Y = R * 3.0f; Y < L.H - R * 3.0f; Y += R * 1.5f)
			{
				Cell(FVector2D(R * 0.3f + (static_cast<int32>(Y / (R * 1.5f)) % 2) * Step * 0.5f, Y));
				Cell(FVector2D(L.W - R * 0.3f - (static_cast<int32>(Y / (R * 1.5f)) % 2) * Step * 0.5f, Y));
			}
		}
	}
	// low health: the edge pulses red
	const float HealthFrac = Player->GetHealth() / FMath::Max(Player->GetMaxHealth(), 1.0f);
	if (HealthFrac < 0.35f && !Player->IsDead())
	{
		const float Pulse = 0.5f + 0.5f * FMath::Abs(FMath::Sin(L.Now * 4.5f));
		const float Depth = 1.0f - HealthFrac / 0.35f * 0.5f;   // (deeper the lower it is)
		Bands(300.0f * S, A(HealthRed, (0.22f + 0.26f * Pulse) * Depth));
		Bands(80.0f * S, A(HealthRed, 0.35f * Pulse * Depth));
	}
	// braced: a frame of the kit's light
	if (Player->HasStatus(SOTags::Status_Guard))
	{
		const FLinearColor Frame = A(Player->GetAbilityColor(), 0.5f);
		Bands(50.0f * S, A(Frame, 0.5f));
		const float T = 3.0f * S;
		P.Fill(Rectangle(0, 0, L.W, T), Frame);
		P.Fill(Rectangle(0, L.H - T, L.W, T), Frame);
		P.Fill(Rectangle(0, T, T, L.H - 2.0f * T), Frame);
		P.Fill(Rectangle(L.W - T, T, T, L.H - 2.0f * T), Frame);
	}
	// an ability coming ready: a breath of gold at the edge; the ultimate a longer one
	float Ready = 0.0f;
	for (int32 i = 0; i < 5; ++i)
	{
		const float Age = L.Now - SlotReadyAt[i];
		if (Age >= 0.0f && Age < 0.5f)
		{
			Ready = FMath::Max(Ready, (1.0f - Age / 0.5f) * 0.22f);
		}
	}
	const float UltAge = L.Now - UltimateReadyAt;
	if (UltAge >= 0.0f && UltAge < 1.0f)
	{
		Ready = FMath::Max(Ready, (1.0f - UltAge) * 0.38f);
	}
	const float LevelAge = L.Now - LevelUpAt;
	if (LevelAge >= 0.0f && LevelAge < 1.2f)
	{
		Ready = FMath::Max(Ready, (1.0f - LevelAge / 1.2f) * 0.45f);
	}
	if (Ready > 0.0f)
	{
		Bands(120.0f * S, A(Gold, Ready));
	}
}

// ---------------------------------------------------------------------------------------------------------------------
// The interact prompt, the downed message

void ASOHUD::DrawInteract(const FLayout& L)
{
	const ASOCharacter* Player = Cast<ASOCharacter>(GetOwningPawn());
	const AActor* Target = Player ? Player->FindInteractable() : nullptr;
	const ISOInteractable* Thing = Target ? Cast<ISOInteractable>(Target) : nullptr;
	if (!Thing)
	{
		return;
	}
	const float S = L.S;
	FPainter P(Canvas);
	FType Type(Canvas);
	const bool bCan = Thing->CanInteract(Player);
	const FString Prompt = Thing->GetInteractPrompt(Player).ToString();
	const FVector2D Sz = Type.Size(Prompt, Type.Medium, 1.15f * S);
	const float W = Sz.X + 70.0f * S, H = Sz.Y + 16.0f * S, X = L.CX - W * 0.5f, Y = L.H * 0.64f;
	Panel(P, Plate4(X, Y, W, H, 6.0f * S), 1.0f * S, 0.95f);
	P.Fill(Plate4(X + 12.0f * S, Y + 6.0f * S, 24.0f * S, H - 12.0f * S, 3.0f * S), bCan ? A(Cyan, 0.25f) : A(Glass, 0.5f));
	P.Stroke(Plate4(X + 12.0f * S, Y + 6.0f * S, 24.0f * S, H - 12.0f * S, 3.0f * S), bCan ? Cyan : Line, 1.0f * S);
	P.Flush();
	Type.DrawCentred(TEXT("E"), X + 24.0f * S, Y + 8.0f * S, Type.Medium, 1.0f * S, bCan ? Ink : Dim);
	Type.Draw(Prompt, X + 48.0f * S, Y + 8.0f * S, Type.Medium, 1.15f * S, bCan ? Ink : Dim);
}

void ASOHUD::DrawDowned(const FLayout& L)
{
	const ASOCharacter* Player = Cast<ASOCharacter>(GetOwningPawn());
	if (!Player)
	{
		return;
	}
	const float S = L.S;
	FPainter P(Canvas);
	FType Type(Canvas);
	const float Left = FMath::Max(0.0f, RespawnDelay - (L.Now - Player->GetDeathTime()));
	const float W = 520.0f * S, H = 110.0f * S, X = L.CX - W * 0.5f, Y = L.H * 0.38f;
	Panel(P, Plate4(X, Y, W, H, 12.0f * S), 1.0f * S, 0.95f, A(Hurt, 0.7f));
	P.Segment(FVector2D(X + 40.0f * S, Y + 62.0f * S), FVector2D(X + W - 40.0f * S, Y + 62.0f * S), A(Hurt, 0.6f), 1.0f * S);
	P.Flush();
	Type.Caps(TEXT("You are down"), L.CX, Y + 18.0f * S, Type.Large, 1.4f * S, Hurt, 5.0f * S, 0.5f);
	Type.DrawCentred(FString::Printf(TEXT("Redeploying in %.1f s"), Left), L.CX, Y + 72.0f * S, Type.Medium, 1.2f * S, Ink);
}

// ---------------------------------------------------------------------------------------------------------------------
// An operation: the stage's title as it begins, the briefing, the radio, the goal marker, the boss bar, the end screen

void ASOHUD::DrawOperation(const FLayout& L)
{
	const ASOOperation* Op = ASOOperation::Get(this);
	const APawn* Pawn = GetOwningPawn();
	if (!Op || !Pawn)
	{
		return;
	}
	const float S = L.S, W = L.W, H = L.H;
	FPainter P(Canvas);
	FType Type(Canvas);
	const FSOStage* Stage = Op->GetStage();
	const float Age = Op->GetStageAge();

	// text broken into lines no wider than MaxW, centred, from Y down; returns the Y under the last line
	auto Wrapped = [&](const FString& Text, float Y, float MaxW, float F, float Scale, FLinearColor C)
	{
		TArray<FString> Words;
		Text.ParseIntoArray(Words, TEXT(" "));
		FString LineText;
		for (int32 i = 0; i <= Words.Num(); ++i)
		{
			const FString Try = i < Words.Num() ? (LineText.IsEmpty() ? Words[i] : LineText + TEXT(" ") + Words[i]) : FString();
			const float TW = i < Words.Num() ? Type.Size(Try, F, Scale).X : 0.0f;
			if (i == Words.Num() || (TW > MaxW && !LineText.IsEmpty()))
			{
				Type.DrawCentred(LineText, W * 0.5f, Y, F, Scale, C);
				Y += Type.Size(LineText, F, Scale).Y + 3.0f * S;
				LineText = i < Words.Num() ? Words[i] : FString();
			}
			else
			{
				LineText = Try;
			}
		}
		return Y;
	};

	// the end screen: what every player earned
	if (Op->GetState() == ESOOperationState::Complete)
	{
		const float Alpha = FMath::Clamp(Age * 1.5f, 0.0f, 1.0f) * FMath::Clamp(14.0f - Age, 0.0f, 1.0f);
		if (Alpha > 0.0f)
		{
			P.FillDown(Rectangle(0.0f, H * 0.24f, W, 230.0f * S), A(Glass, 0.9f * Alpha), A(GlassDeep, 0.9f * Alpha));
			P.Fill(Rectangle(0.0f, H * 0.24f, W, 1.5f * S), A(Gold, 0.8f * Alpha));
			P.Fill(Rectangle(0.0f, H * 0.24f + 228.5f * S, W, 1.5f * S), A(Gold, 0.8f * Alpha));
			P.Flush();
			Type.Caps(Op->OperationName.ToString(), W * 0.5f, H * 0.24f + 22.0f * S, Type.Medium, 1.1f * S, A(Gold, Alpha), 3.0f * S, 0.5f);
			Type.Caps(TEXT("Operation complete"), W * 0.5f, H * 0.24f + 52.0f * S, Type.Large, 2.0f * S, A(Ink, Alpha), 6.0f * S, 0.5f);
			if (!Op->Outcome.IsEmpty())
			{
				Wrapped(Op->Outcome.ToString(), H * 0.24f + 240.0f * S, W * 0.6f, Type.Medium, 1.0f * S, A(Dim, Alpha));
			}
			float Y = H * 0.24f + 130.0f * S;
			const APlayerState* Mine = GetOwningPlayerController() ? GetOwningPlayerController()->PlayerState : nullptr;
			for (const FSOOperationReward& R : Op->GetRewards())
			{
				const FString Who = R.Player == Mine ? TEXT("You earned") : (R.Player ? R.Player->GetPlayerName() : FString(TEXT("?")));
				Type.DrawCentred(FString::Printf(TEXT("%s   %s"), *Who, *R.Label), W * 0.5f, Y, Type.Medium, (R.Player == Mine ? 1.35f : 1.0f) * S, A(RarityColour(R.Rarity), Alpha));
				Y += (R.Player == Mine ? 34.0f : 26.0f) * S;
			}
		}
		return;
	}
	if (!Stage || Op->GetState() != ESOOperationState::Active)
	{
		return;
	}

	// the stage's title as it begins
	if (Age < 5.0f)
	{
		const float Alpha = FMath::Clamp(Age * 2.0f, 0.0f, 1.0f) * FMath::Clamp(5.0f - Age, 0.0f, 1.0f);
		const float TW = Type.CapsWidth(Stage->Title.ToString(), Type.Large, 1.6f * S, 6.0f * S);
		P.FillAcross(Rectangle(W * 0.5f - TW * 0.5f, H * 0.16f + 48.0f * S, TW * 0.5f, 1.5f * S), A(Gold, 0.0f), A(Gold, Alpha));
		P.FillAcross(Rectangle(W * 0.5f, H * 0.16f + 48.0f * S, TW * 0.5f, 1.5f * S), A(Gold, Alpha), A(Gold, 0.0f));
		P.Flush();
		Type.Caps(Stage->Title.ToString(), W * 0.5f, H * 0.16f, Type.Large, 1.6f * S, A(Ink, Alpha), 6.0f * S, 0.5f);
		Type.DrawCentred(Stage->Objective.ToString(), W * 0.5f, H * 0.16f + 58.0f * S, Type.Medium, 1.1f * S, A(Dim, Alpha));
	}

	// why anyone goes: as the operation begins, a line at a time over the lower third (then the first stage's radio line)
	const bool bOpening = Op->GetStageIndex() == 0 && Op->Briefing.Num() > 0;
	const float Per = 5.5f, BriefEnd = bOpening ? Per * Op->Briefing.Num() : 0.0f;
	if (bOpening && Age < BriefEnd)
	{
		const int32 Line0 = FMath::Min(Op->Briefing.Num() - 1, FMath::FloorToInt(Age / Per));
		const float T = Age - Line0 * Per;
		const float Alpha = FMath::Clamp(T * 2.0f, 0.0f, 1.0f) * FMath::Clamp((Per - T) * 2.0f, 0.0f, 1.0f);
		P.FillDown(Rectangle(0.0f, H * 0.70f, W, 112.0f * S), A(Glass, 0.8f * Alpha), A(GlassDeep, 0.8f * Alpha));
		P.Flush();
		Type.Caps(Op->OperationName.ToString(), W * 0.5f, H * 0.70f + 10.0f * S, Type.Small, 1.3f * S, A(Gold, Alpha), 3.0f * S, 0.5f);
		Wrapped(Op->Briefing[Line0].ToString(), H * 0.70f + 34.0f * S, W * 0.7f, Type.Medium, 1.7f * S, A(Ink, Alpha));
	}
	// the radio as a stage begins: who, and what this place means
	const float RadioAge = Age - BriefEnd - 1.0f, RadioTime = 11.0f;
	if (!Stage->Intel.IsEmpty() && RadioAge > 0.0f && RadioAge < RadioTime)
	{
		const float Alpha = FMath::Clamp(RadioAge * 2.0f, 0.0f, 1.0f) * FMath::Clamp(RadioTime - RadioAge, 0.0f, 1.0f);
		const float Y = H * 0.70f;   // (clear of the vitals and the abilities under it)
		Panel(P, Plate(W * 0.17f, Y - 8.0f * S, W * 0.66f, 96.0f * S, 10.0f * S), 1.0f * S, 0.9f * Alpha);
		P.Fill(Rectangle(W * 0.17f, Y + 2.0f * S, 2.5f * S, 86.0f * S), A(Gold, 0.9f * Alpha));
		P.Flush();
		Type.Caps(Stage->IntelWho.ToString(), W * 0.5f, Y - 2.0f * S, Type.Small, 1.3f * S, A(Gold, Alpha), 2.5f * S, 0.5f);
		Wrapped(Stage->Intel.ToString(), Y + 20.0f * S, W * 0.62f, Type.Medium, 1.4f * S, A(Ink, Alpha));
	}

	// a marker on the goal (where to go), with the distance
	if (Stage->Kind == ESOStageKind::Travel || Stage->Kind == ESOStageKind::Hold)
	{
		const FVector Screen = Project(Stage->Goal + FVector(0, 0, 150.0f), true);
		if (Screen.Z > 0.0f)
		{
			const FVector2D Pt(FMath::Clamp<float>(Screen.X, 40.0f * S, W - 40.0f * S), FMath::Clamp<float>(Screen.Y, 130.0f * S, H - 60.0f * S));
			P.Stroke(Diamond(Pt, 10.0f * S, 10.0f * S), Gold, 2.0f * S);
			P.Fill(Diamond(Pt, 3.0f * S, 3.0f * S), Gold);
			P.Flush();
			const int32 Metres = FMath::RoundToInt(FVector::Dist(Pawn->GetActorLocation(), Stage->Goal) / 100.0f);
			Type.DrawCentred(FString::Printf(TEXT("%d m"), Metres), Pt.X, Pt.Y + 14.0f * S, Type.Small, 1.0f * S, Ink);
		}
	}

	// the boss across the top
	DrawBossBar(Op->GetBoss(), L);
}

void ASOHUD::DrawBossBar(const ASOEnemy* Boss, const FLayout& L)
{
	if (!Boss || Boss->IsDead())
	{
		return;
	}
	const float S = L.S;
	FPainter P(Canvas);
	FType Type(Canvas);
	const float BW = 640.0f * S, BX = L.CX - BW * 0.5f, BY = 150.0f * S;
	Panel(P, Plate4(BX - 14.0f * S, BY - 30.0f * S, BW + 28.0f * S, 66.0f * S, 8.0f * S), 1.0f * S, 0.9f, A(Lock, 0.5f));
	Bar(P, BX, BY, BW, 10.0f * S, Boss->GetHealth() / FMath::Max(Boss->GetMaxHealth(), 1.0f), HealthRed, 1.0f, 1.0f * S);
	if (Boss->GetMaxShield() > 0.0f && Boss->GetShield() > 0.0f)
	{
		P.Fill(Rectangle(BX, BY + 11.0f * S, BW * Boss->GetShield() / Boss->GetMaxShield(), 2.5f * S), ShieldBlue);
	}
	// its fight: a notch on the bar where each phase begins, the phase's name, and when it reels
	const USOBossComponent* Fight = Boss->GetBoss();
	const USOBossData* Table = Fight ? Fight->GetData() : nullptr;
	for (int32 i = 1; Table && i < Table->Phases.Num(); ++i)
	{
		const float Notch = BX + BW * FMath::Clamp(Table->Phases[i].FromHealth, 0.0f, 1.0f);
		P.Fill(Rectangle(Notch - 1.5f * S, BY - 2.0f * S, 3.0f * S, 14.0f * S), A(FLinearColor::Black, 0.85f));
		P.Fill(Rectangle(Notch - 0.5f * S, BY - 2.0f * S, 1.0f * S, 14.0f * S), A(Gold, i > Fight->GetPhase() ? 0.95f : 0.35f));
	}
	P.Flush();
	Type.Caps(Boss->DisplayName.ToString(), L.CX, BY - 24.0f * S, Type.Medium, 1.05f * S, Ink, 3.0f * S, 0.5f);
	if (Boss->IsImmune())
	{
		Type.Caps(Boss->ImmuneReason.ToString(), L.CX, BY + 18.0f * S, Type.Small, 1.0f * S, FLinearColor(1.0f, 0.75f, 0.35f, 0.95f), 1.5f * S, 0.5f);
	}
	else if (Boss->HasStatus(SOTags::Status_Stagger))
	{
		Type.Caps(NSLOCTEXT("SO", "BossReels", "REELING").ToString(), L.CX, BY + 18.0f * S, Type.Small, 1.0f * S, FLinearColor(1.0f, 0.95f, 0.6f, 0.6f + 0.4f * FMath::Abs(FMath::Sin(L.Now * 6.0f))), 2.5f * S, 0.5f);
	}
	else if (const FSOBossPhase* Phase = Fight ? Fight->GetPhaseData() : nullptr; Phase && !Phase->Name.IsEmpty())
	{
		Type.Caps(Phase->Name.ToString(), L.CX, BY + 18.0f * S, Type.Small, 0.95f * S, A(Dim, 0.9f), 2.0f * S, 0.5f);
	}
}

namespace
{
	bool bSOAIDebug = false;
#if !UE_BUILD_SHIPPING
	FAutoConsoleCommand SOAIDebugCommand(TEXT("SOAIDebug"), TEXT("Shows what every creature near the player is thinking, and what the brains cost (on / off)."),
		FConsoleCommandDelegate::CreateLambda([]() { bSOAIDebug = !bSOAIDebug; }));
#endif
}

void ASOHUD::DrawAIDebug(float W, float H, float S)
{
#if !UE_BUILD_SHIPPING
	const APawn* Pawn = GetOwningPawn();
	UFont* Small = GEngine ? GEngine->GetSmallFont() : nullptr;
	if (!bSOAIDebug || !Pawn || !Small)
	{
		return;
	}
	const float Now = GetWorld()->GetTimeSeconds();
	if (Now - AIDebugReadAt >= 1.0f || Now < AIDebugReadAt)
	{
		// what the brains cost over the last second
		AIDebugThinks = ASOEnemyAIController::ThinksCounted;
		AIDebugMs = static_cast<float>(ASOEnemyAIController::ThinkSecondsCounted * 1000.0);
		ASOEnemyAIController::ThinksCounted = 0;
		ASOEnemyAIController::ThinkSecondsCounted = 0.0;
		AIDebugReadAt = Now;
	}
	static const TCHAR* States[] = { TEXT("idle"), TEXT("wander"), TEXT("chase"), TEXT("attack"), TEXT("dead"), TEXT("suspicious"), TEXT("search"), TEXT("to cover"), TEXT("in cover") };
	int32 Alive = 0, Fighting = 0, Shown = 0;
	for (TActorIterator<ASOEnemy> It(GetWorld()); It; ++It)
	{
		const ASOEnemy* E = *It;
		const ASOEnemyAIController* Brain = Cast<ASOEnemyAIController>(E->GetController());
		if (E->IsDead())
		{
			continue;
		}
		++Alive;
		Fighting += Brain && Brain->IsInCombat() ? 1 : 0;
		const FVector Head = E->GetActorLocation() + FVector(0.0f, 0.0f, E->GetSimpleCollisionHalfHeight() + 30.0f);
		if (!Brain || FVector::Dist(Head, Pawn->GetActorLocation()) > 6000.0f)
		{
			continue;
		}
		const FVector Screen = Project(Head, true);
		if (Screen.Z <= 0.0f)
		{
			continue;
		}
		++Shown;
		const int32 StateIndex = static_cast<int32>(Brain->GetState());
		const ASOCombatCharacter* Target = Brain->GetTarget();
		FString Flags;
		Flags += Brain->IsFlanker() ? TEXT(" flanker") : TEXT("");
		Flags += Brain->IsRetreating() ? TEXT(" falling-back") : TEXT("");
		Flags += Brain->IsScattering() ? TEXT(" SCATTERING") : TEXT("");
		Flags += E->bSuppressor ? TEXT(" suppressor") : TEXT("");
		Flags += E->IsSuppressing() ? TEXT(" SUPPRESSING") : TEXT("");
		Flags += E->HasStatus(SOTags::Status_Suppressed) ? TEXT(" PINNED") : TEXT("");
		Flags += E->HasStatus(SOTags::Status_Stagger) ? TEXT(" REELING") : TEXT("");
		Flags += E->bLikesHigh ? TEXT(" high-ground") : TEXT("");
		FString Kit;
		if (const USOAbilitySet* Set = E->GetAbilitySet())
		{
			Kit = Set->KitId.ToString() + TEXT(":");
			for (const FSOAbilityGrant& Grant : Set->Abilities)
			{
				int32 Charges = 0, Max = 0;
				float Left = 0.0f, Cooldown = 0.0f;
				E->GetAbilityState(Grant.Slot, Charges, Max, Left, Cooldown);
				Kit += E->IsAbilityActive(Grant.Slot) ? TEXT(" [using]") : (Charges > 0 ? TEXT(" [ready]") : *FString::Printf(TEXT(" [%.0fs]"), Left));
			}
		}
		const FString Lines[] = {
			FString::Printf(TEXT("%s  %s"), E->GetVariantId().IsNone() ? *E->SpeciesId.ToString() : *E->GetVariantId().ToString(),
				States[FMath::Clamp(StateIndex, 0, static_cast<int32>(UE_ARRAY_COUNT(States)) - 1)]),
			FString::Printf(TEXT("aware %.0f%%  target %s%s"), Brain->GetAwareness() * 100.0f, Target ? (Target->IsPlayerControlled() ? TEXT("player") : *Target->GetName()) : TEXT("none"),
				Brain->HasCover() ? TEXT("  has cover") : TEXT("")),
			Flags.TrimStart(), Kit };
		float Y = Screen.Y - 44.0f * S;
		for (const FString& Row : Lines)
		{
			if (!Row.IsEmpty())
			{
				DrawText(Row, Brain->IsInCombat() ? FLinearColor(1.0f, 0.85f, 0.5f) : FLinearColor(0.7f, 0.9f, 1.0f), Screen.X - 60.0f * S, Y, Small, 0.9f * S);
				Y += 11.0f * S;
			}
		}
		// where it means to stand (cyan) and where it last knew its target to be (yellow)
		if (Brain->HasCover())
		{
			const FVector Cover = Project(Brain->GetCoverPoint(), true);
			if (Cover.Z > 0.0f)
			{
				DrawLine(Screen.X, Screen.Y, Cover.X, Cover.Y, FLinearColor(0.2f, 0.9f, 1.0f, 0.8f), 1.5f);
				DrawRect(FLinearColor(0.2f, 0.9f, 1.0f, 0.9f), Cover.X - 3.0f, Cover.Y - 3.0f, 6.0f, 6.0f);
			}
		}
		if (Brain->IsInCombat())
		{
			const FVector Last = Project(Brain->GetLastKnownLocation() + FVector(0.0f, 0.0f, 40.0f), true);
			if (Last.Z > 0.0f)
			{
				DrawLine(Screen.X, Screen.Y, Last.X, Last.Y, FLinearColor(1.0f, 0.9f, 0.2f, 0.5f), 1.0f);
				DrawRect(FLinearColor(1.0f, 0.9f, 0.2f, 0.9f), Last.X - 3.0f, Last.Y - 3.0f, 6.0f, 6.0f);
			}
		}
	}
	DrawRect(FLinearColor(0.0f, 0.0f, 0.0f, 0.55f), W * 0.5f - 250.0f * S, 96.0f * S, 500.0f * S, 18.0f * S);
	DrawText(FString::Printf(TEXT("AI  %d alive, %d fighting, %d shown  |  %d thinks/s, %.2f ms/s  |  level %s"), Alive, Fighting, Shown, AIDebugThinks, AIDebugMs,
		*USODifficultySubsystem::Get(this).Id.ToString()), FLinearColor(0.8f, 1.0f, 0.8f), W * 0.5f - 244.0f * S, 99.0f * S, Small, 1.0f * S);
#endif
}

void ASOHUD::DrawScope(float W, float H)
{
	using namespace SOSightTheme;
	const ASOCharacter* Player = Cast<ASOCharacter>(GetOwningPawn());
	const ASOWeapon* Weapon = Player ? Player->GetWeapon() : nullptr;
	const USOWeaponData* Data = Weapon ? Weapon->GetData() : nullptr;
	const ETheme Theme = Of(Data);
	const FLinearColor G = Glow(Data);
	const FLook Look = LookOf(Theme, G);
	const float Time = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.0f;
	const float S = H / 1080.0f;
	const FVector2D C(W * 0.5f, H * 0.5f);
	const float R = H * 0.46f, Far = FMath::Max(W, H) * 1.5f;
	const int32 N = 144;

	auto Edge = [&](int32 i) { const float A = UE_TWO_PI * i / N; return FVector2D(FMath::Cos(A), FMath::Sin(A)) * Radius(Theme, A, R, Time); };
	auto Quad = [](TArray<FCanvasUVTri>& Tris, const FVector2D& A0, const FVector2D& A1, const FVector2D& B0, const FVector2D& B1,
		const FLinearColor& CA, const FLinearColor& CB)
	{
		FCanvasUVTri T1, T2;
		T1.V0_Pos = A0; T1.V1_Pos = B0; T1.V2_Pos = B1;
		T2.V0_Pos = A0; T2.V1_Pos = B1; T2.V2_Pos = A1;
		T1.V0_Color = CA; T1.V1_Color = CB; T1.V2_Color = CB;
		T2.V0_Color = CA; T2.V1_Color = CB; T2.V2_Color = CA;
		Tris.Add(T1);
		Tris.Add(T2);
	};

	// what stands round the window (the set's own body, darkening toward the screen's edge), its rim, the glass's tint
	TArray<FCanvasUVTri> Body, Rim, Pane;
	const float RimW = Look.RimWidth * S;
	const float Mid = FMath::Max(W, H) * 0.42f;
	FLinearColor Clear = Look.Edge;
	Clear.A = 0.0f;
	for (int32 i = 0; i < N; ++i)
	{
		const FVector2D E0 = Edge(i), E1 = Edge(i + 1);
		const FVector2D D0 = E0.GetSafeNormal(), D1 = E1.GetSafeNormal();
		Quad(Body, C + E0 + D0 * RimW, C + E1 + D1 * RimW, C + E0 + D0 * Mid, C + E1 + D1 * Mid, Look.Near, Look.Far);
		Quad(Body, C + E0 + D0 * Mid, C + E1 + D1 * Mid, C + D0 * Far, C + D1 * Far, Look.Far, Look.Far);
		// the light guns' rim is a ring of segments with gaps (a lit bezel)
		const bool bGap = Theme == ETheme::Light && (i % 6) == 5;
		const FLinearColor RimC = bGap ? Look.Near : Look.Rim;
		Quad(Rim, C + E0, C + E1, C + E0 + D0 * RimW, C + E1 + D1 * RimW, RimC, RimC * FLinearColor(0.65f, 0.65f, 0.65f, 1.0f));
		Quad(Pane, C + E0, C + E1, C + E0 * (1.0f - Look.EdgeDepth), C + E1 * (1.0f - Look.EdgeDepth), Look.Edge, Clear);
	}
	for (TArray<FCanvasUVTri>* Tris : { &Pane, &Body, &Rim })
	{
		FCanvasTriangleItem Item(*Tris, GWhiteTexture);
		Item.BlendMode = SE_BLEND_Translucent;
		Canvas->DrawItem(Item);
	}

	// a line drawn as light: a soft halo under a sharp core
	auto Glowing = [&](const FVector2D& A, const FVector2D& B, const FLinearColor& Col, float T)
	{
		DrawLine(A.X, A.Y, B.X, B.Y, FLinearColor(Col.R, Col.G, Col.B, Col.A * 0.22f), T * 3.5f);
		DrawLine(A.X, A.Y, B.X, B.Y, Col, T);
	};
	// a polyline in 1080 px about the centre
	auto Poly = [&](std::initializer_list<FVector2D> Pts, const FLinearColor& Col, float T, bool bClosed)
	{
		const TArray<FVector2D> P(Pts);
		for (int32 i = 0; i + 1 < P.Num(); ++i)
		{
			Glowing(C + P[i] * S, C + P[i + 1] * S, Col, T);
		}
		if (bClosed && P.Num() > 2)
		{
			Glowing(C + P.Last() * S, C + P[0] * S, Col, T);
		}
	};
	const float Edge0 = R / S; // the window's size in 1080 px

	switch (Theme)
	{
	case ETheme::Sarketh:
	{
		// their emblem in gold on the lacquer round the glass: the brow's chevron over the window, three dashes either side
		const FLinearColor SkrGold(0.95f, 0.64f, 0.24f, 0.9f);
		const FLinearColor GoldDim(0.95f, 0.64f, 0.24f, 0.55f);
		const float Top = Radius(Theme, -UE_HALF_PI, R, Time) / S, Side = Radius(Theme, 0.0f, R, Time) / S;
		Poly({ FVector2D(-120, -Top - 26), FVector2D(0, -Top - 8), FVector2D(120, -Top - 26) }, SkrGold, 3.0f * S, false);
		Poly({ FVector2D(-70, -Top - 40), FVector2D(0, -Top - 24), FVector2D(70, -Top - 40) }, GoldDim, 2.0f * S, false);
		for (int32 j = 0; j < 3; ++j)
		{
			const float X = Side + 26.0f + j * 30.0f;
			Poly({ FVector2D(X, 0), FVector2D(X + 18.0f, 0) }, SkrGold, 3.0f * S, false);
			Poly({ FVector2D(-X, 0), FVector2D(-X - 18.0f, 0) }, SkrGold, 3.0f * S, false);
		}
		// the reticle, in the set's amber: an open lozenge round a point, the brow's chevron over it, three dashes either
		// side, the slug's drop below as falling chevrons; it brightens as the gun heats
		const float Heat = Weapon && Weapon->HasHeat() ? Weapon->GetHeat() : 0.0f;
		const FLinearColor A = Lit(FMath::Lerp(G, FLinearColor(1.0f, 0.9f, 0.7f), Heat * 0.5f), 0.92f);
		const float T = 1.6f * S;
		Poly({ FVector2D(-11, 0), FVector2D(0, -8), FVector2D(11, 0), FVector2D(0, 8) }, A, T, true);
		DrawRect(A, C.X - 1.5f * S, C.Y - 1.5f * S, 3.0f * S, 3.0f * S);
		Poly({ FVector2D(-30, -34), FVector2D(0, -18), FVector2D(30, -34) }, A, T, false);
		for (int32 j = 0; j < 3; ++j)
		{
			const float X = 30.0f + j * 22.0f;
			Poly({ FVector2D(X, 0), FVector2D(X + 12.0f, 0) }, A, T, false);
			Poly({ FVector2D(-X, 0), FVector2D(-X - 12.0f, 0) }, A, T, false);
		}
		const FLinearColor Faint(A.R, A.G, A.B, 0.4f);
		Poly({ FVector2D(110, 0), FVector2D(Edge0 * 1.3f, 0) }, Faint, 1.0f * S, false);
		Poly({ FVector2D(-110, 0), FVector2D(-Edge0 * 1.3f, 0) }, Faint, 1.0f * S, false);
		for (int32 j = 1; j <= 4; ++j)
		{
			const float Y = 26.0f + j * 30.0f, Wd = 9.0f - j;
			Poly({ FVector2D(-Wd, Y - Wd * 0.6f), FVector2D(0, Y), FVector2D(Wd, Y - Wd * 0.6f) }, A, 1.3f * S, false);
		}
		break;
	}
	case ETheme::Void:
	{
		// three lines closing on a small triangle, in the set's violet; a mark off each of the window's points
		const FLinearColor V = Lit(G, 0.9f);
		const float T = 1.4f * S;
		for (int32 j = 0; j < 3; ++j)
		{
			const float Ang = UE_HALF_PI + j * UE_TWO_PI / 3.0f, Next = Ang + UE_TWO_PI / 3.0f;
			const FVector2D D(FMath::Cos(Ang), FMath::Sin(Ang)), DN(FMath::Cos(Next), FMath::Sin(Next));
			Poly({ D * 16.0f, D * Edge0 * 0.85f }, V, T, false);
			Poly({ D * -9.0f, DN * -9.0f }, V, T, false);
		}
		const FLinearColor Mark(Look.Rim.R, Look.Rim.G, Look.Rim.B, 0.8f);
		for (int32 j = 0; j < 6; ++j)
		{
			const float Ang = -UE_HALF_PI + j * UE_PI / 3.0f;
			const FVector2D D(FMath::Cos(Ang), FMath::Sin(Ang));
			const float Rr = Radius(Theme, Ang, R, Time) / S;
			Poly({ D * (Rr + 10.0f), D * (Rr + 42.0f) }, Mark, 2.0f * S, false);
		}
		DrawRect(V, C.X - 1.0f * S, C.Y - 1.0f * S, 2.0f * S, 2.0f * S);
		break;
	}
	case ETheme::Light:
	{
		// fine lines of light: a broken ring round a point, a ruler along the horizon, the drop line below
		const FLinearColor L = Lit(G, 0.9f);
		const float T = 1.2f * S;
		for (int32 j = 0; j < 8; ++j)
		{
			const float A0 = j * UE_TWO_PI / 8.0f + 0.12f, A1 = (j + 1) * UE_TWO_PI / 8.0f - 0.12f;
			Poly({ FVector2D(FMath::Cos(A0), FMath::Sin(A0)) * 12.0f, FVector2D(FMath::Cos(A1), FMath::Sin(A1)) * 12.0f }, L, T, false);
		}
		DrawRect(L, C.X - 1.0f * S, C.Y - 1.0f * S, 2.0f * S, 2.0f * S);
		Poly({ FVector2D(24, 0), FVector2D(Edge0, 0) }, L, T, false);
		Poly({ FVector2D(-24, 0), FVector2D(-Edge0, 0) }, L, T, false);
		Poly({ FVector2D(0, 24), FVector2D(0, Edge0) }, L, T, false);
		for (int32 j = 1; j * 36.0f < Edge0 * 0.8f; ++j)
		{
			const float Len = (j % 2) ? 4.0f : 8.0f;
			Poly({ FVector2D(j * 36.0f, -Len), FVector2D(j * 36.0f, Len) }, L, 1.0f * S, false);
			Poly({ FVector2D(-j * 36.0f, -Len), FVector2D(-j * 36.0f, Len) }, L, 1.0f * S, false);
		}
		break;
	}
	case ETheme::Living:
	{
		// four claws curling round a point, drops hanging below, in the living green
		const FLinearColor L = Lit(G, 0.88f);
		const float T = 1.8f * S;
		for (int32 q = 0; q < 4; ++q)
		{
			const float Mid4 = UE_PI / 4.0f + q * UE_HALF_PI;
			FVector2D Prev = FVector2D::ZeroVector;
			for (int32 k = 0; k <= 6; ++k)
			{
				const float Ang = Mid4 - 0.5f + k / 6.0f;
				const FVector2D P = FVector2D(FMath::Cos(Ang), FMath::Sin(Ang)) * (22.0f - k * 1.6f);
				if (k > 0)
				{
					Poly({ Prev, P }, L, T, false);
				}
				Prev = P;
			}
		}
		DrawRect(L, C.X - 1.5f * S, C.Y - 1.5f * S, 3.0f * S, 3.0f * S);
		for (int32 j = 1; j <= 3; ++j)
		{
			const float Y = 30.0f + j * 34.0f, D = 4.0f - j * 0.7f;
			DrawRect(L, C.X - D * S, C.Y + (Y - D) * S, 2.0f * D * S, 2.0f * D * S);
		}
		break;
	}
	default:
	{
		// a human optic: fine dark lines, a red point, stadia below
		const FLinearColor Dark(0.02f, 0.02f, 0.02f, 0.95f);
		DrawLine(C.X - R, C.Y, C.X - 18.0f * S, C.Y, Dark, 1.5f * S);
		DrawLine(C.X + 18.0f * S, C.Y, C.X + R, C.Y, Dark, 1.5f * S);
		DrawLine(C.X, C.Y + 18.0f * S, C.X, C.Y + R, Dark, 1.5f * S);
		DrawLine(C.X, C.Y - R * 0.6f, C.X, C.Y - 18.0f * S, Dark, 1.0f * S);
		DrawRect(FLinearColor(1.0f, 0.15f, 0.1f, 0.95f), C.X - 1.5f * S, C.Y - 1.5f * S, 3.0f * S, 3.0f * S);
		for (int32 i = 1; i <= 4; ++i) // stadia ticks below the centre
		{
			DrawLine(C.X - 8.0f * S, C.Y + i * 40.0f * S, C.X + 8.0f * S, C.Y + i * 40.0f * S, Dark, 1.0f * S);
		}
		break;
	}
	}
}

void ASOHUD::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	if (FeedInventory.IsValid())
	{
		FeedInventory->OnFeed.Remove(FeedHandle);
		FeedInventory->OnFeedItem.Remove(FeedItemHandle);
	}
	if (HitPawn.IsValid())
	{
		HitPawn->OnHitConfirmed.Remove(HitHandle);
		HitPawn->OnHitReported.Remove(HitReportHandle);
	}
	Super::EndPlay(EndPlayReason);
}

void ASOHUD::DrawHUD()
{
	Super::DrawHUD();
	if (!Canvas)
	{
		return;
	}
	FLayout L;
	L.W = Canvas->ClipX;
	L.H = Canvas->ClipY;
	L.S = L.H / 1080.0f;
	// wider than 2200 units the corners keep to a 2200 frame in the middle (the armoury's rule): the eye need not
	// travel to the far edges of an ultra-wide screen
	const float Frame = FMath::Min(L.W, 2200.0f * L.S);
	L.X0 = (L.W - Frame) * 0.5f;
	L.X1 = L.X0 + Frame;
	L.CX = L.W * 0.5f;
	L.Now = GetWorld()->GetTimeSeconds();
	HudDt = FMath::Clamp(L.Now - LastFrameTime, 0.0f, 0.1f);
	LastFrameTime = L.Now;
	RightFlowY = 112.0f * L.S;

	BindInventory();
	const ASOCharacter* Player = Cast<ASOCharacter>(GetOwningPawn());
	if (!Player)
	{
		return;
	}
	if (HitPawn.Get() != Player)
	{
		// the body changes with every respawn: listen to the one in play
		if (HitPawn.IsValid())
		{
			HitPawn->OnHitConfirmed.Remove(HitHandle);
			HitPawn->OnHitReported.Remove(HitReportHandle);
		}
		HitPawn = Player;
		HitHandle = Player->OnHitConfirmed.AddUObject(this, &ASOHUD::OnHitConfirmed);
		HitReportHandle = Player->OnHitReported.AddUObject(this, &ASOHUD::OnHitReported);
	}
	const bool bScreens = InventoryWidget || MapWidget;
	const bool bScope = Player->IsScopeView();

	// a hit on the player: when, and whether the body took it or only the shield
	if (LastHealth >= 0.0f && (Player->GetHealth() < LastHealth - 0.5f || Player->GetShield() < LastShield - 0.5f))
	{
		LastDamageTime = L.Now;
		bLastDamageHealth = Player->GetHealth() < LastHealth - 0.5f;
	}
	LastHealth = Player->GetHealth();
	LastShield = Player->GetShield();

	// who the crosshair is on: a hostile within 60 m along the eye's line
	{
		const ASOCombatCharacter* Was = Locked.Get();
		Locked = nullptr;
		if (APlayerController* PC = GetOwningPlayerController())
		{
			FVector Eye;
			FRotator Look;
			PC->GetPlayerViewPoint(Eye, Look);
			FCollisionQueryParams Params(SCENE_QUERY_STAT(HudLock), false, Player);
			if (const ASOWeapon* Gun = Player->GetWeapon())
			{
				Params.AddIgnoredActor(Gun);
			}
			FHitResult Hit;
			if (GetWorld()->LineTraceSingleByChannel(Hit, Eye, Eye + Look.Vector() * 6000.0f, SO_TRACE_BULLET, Params))
			{
				const ASOCombatCharacter* Other = Cast<ASOCombatCharacter>(Hit.GetActor());
				if (Other && !Other->IsDead() && !Other->IsDisplayOnly() && USOCombatStatics::AreHostile(Player, Other))
				{
					Locked = Other;
				}
			}
		}
		if (Locked.IsValid() && Locked.Get() != Was)
		{
			LockedAt = L.Now;
		}
	}

	if (bScope)
	{
		DrawScope(L.W, L.H);
	}
	if (bScreens)
	{
		return;
	}
	DrawScreenEdge(L);
	if (!bScope)
	{
		DrawMinimap(L);
		DrawCompass(L);
		DrawObjective(L);
		DrawConditions(L);
		DrawTracked(L);
		DrawItemCards(L);
		DrawLootBeams(L);
		DrawCreatures(L);
		DrawEliteIntro(L);
	}
	DrawOperation(L);
	DrawAIDebug(L.W, L.H, L.S);
	if (Player->IsDead())
	{
		DrawDowned(L);
		return;
	}
	DrawDamageNumbers(L);
	DrawRewards(L);
	DrawLevelUp(L);
	DrawCrosshair(L);
	DrawMelee(L);
	DrawInteract(L);
	DrawVitals(L);
	DrawAbilities(L);
	DrawWeapon(L);
}
