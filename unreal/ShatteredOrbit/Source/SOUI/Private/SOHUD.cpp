#include "SOHUD.h"

#include "SOHUDPaint.h"
#include "Materials/MaterialInterface.h"
#include "Materials/MaterialInstanceDynamic.h"
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
#include "Misc/CommandLine.h"

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

FGlass ASOHUD::MakeGlass(FPainter& P, float S)
{
	FGlass G;
	G.Canvas = Canvas;
	G.Painter = &P;
	G.Base = GlassBase;
	G.Pool = &GlassPool;
	G.Used = &GlassUsed;
	G.Outer = this;
	G.S = S;
	G.Audit = AuditPtr();
	return G;
}

FHudAudit* ASOHUD::AuditPtr() const
{
	return bAuditing ? Audit.Get() : nullptr;
}

void ASOHUD::DrawElement(const FLayout& L, const FSOHudElementLayout& E, const TCHAR* Name, TFunctionRef<void(const FLayout&)> Draw)
{
	if (!E.bVisible || !Canvas || !Canvas->Canvas)
	{
		return;
	}
	FLayout LE = L;
	LE.S = L.S * FMath::Max(E.Scale, 0.1f);
	const FVector2D Off = E.Offset * L.S;
	const bool bMoved = !Off.IsNearlyZero();
	if (bMoved)
	{
		Canvas->Canvas->PushRelativeTransform(FTranslationMatrix(FVector(Off.X, Off.Y, 0.0f)));
	}
	ElementOffset = Off;
	if (FHudAudit* Au = AuditPtr())
	{
		Au->Element = Name;
	}
	Draw(LE);
	ElementOffset = FVector2D::ZeroVector;
	if (FHudAudit* Au = AuditPtr())
	{
		Au->Element.Reset();
	}
	if (bMoved)
	{
		Canvas->Canvas->PopTransform();
	}
}

void ASOHUD::Picture(UTexture2D* Tex, float X, float Y, float W, float H, float Alpha, const FString& Name)
{
	if (!Tex)
	{
		return;
	}
	DrawTexture(Tex, X, Y, W, H, 0.0f, 0.0f, 1.0f, 1.0f, FLinearColor(1.0f, 1.0f, 1.0f, Alpha));
	if (FHudAudit* Au = AuditPtr())
	{
		Au->Note(FHudAudit::Image, FRegion(X, Y, W, H), Name);
	}
}

void ASOHUD::SOHudLayout(FName Element, float DX, float DY, float Scale)
{
#if !UE_BUILD_SHIPPING
	FSOHudElementLayout* All[] = { &MinimapLayout, &CompassLayout, &ObjectiveLayout, &ConditionsLayout, &TrackedLayout, &ItemsLayout, &VitalsLayout, &AbilitiesLayout, &WeaponLayout, &InteractLayout };
	const TCHAR* Names[] = { TEXT("minimap"), TEXT("compass"), TEXT("objective"), TEXT("conditions"), TEXT("tracked"), TEXT("items"), TEXT("vitals"), TEXT("abilities"), TEXT("weapon"), TEXT("interact") };
	if (Element == TEXT("reset"))
	{
		for (FSOHudElementLayout* E : All)
		{
			*E = FSOHudElementLayout();
		}
		return;
	}
	for (int32 i = 0; i < UE_ARRAY_COUNT(All); ++i)
	{
		if (Element == Names[i])
		{
			All[i]->Offset = FVector2D(DX, DY);
			All[i]->Scale = Scale;
			UE_LOG(LogTemp, Display, TEXT("SOHudLayout: %s at %.0f, %.0f x %.2f"), Names[i], DX, DY, Scale);
			return;
		}
	}
	UE_LOG(LogTemp, Warning, TEXT("SOHudLayout: no element '%s' (minimap compass objective conditions tracked items vitals abilities weapon interact reset)"), *Element.ToString());
#endif
}

void ASOHUD::SOHudAudit(int32 On)
{
#if !UE_BUILD_SHIPPING
	bAuditing = On != 0;
	if (bAuditing && !Audit.IsValid())
	{
		Audit = MakeShared<FHudAudit>();
	}
	AuditLast.Reset();
	UE_LOG(LogTemp, Display, TEXT("SOHudAudit: %s"), bAuditing ? TEXT("on") : TEXT("off"));
#endif
}

void ASOHUD::SetDebugWeapon(const FString& Name, int32 Mag, int32 Reserve)
{
	DebugWeaponName = Name;
	DebugMag = Mag;
	DebugReserve = Reserve;
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
	// its lane: under the live popups on its side (xp to the right of the crosshair, the rest to the left)
	Pop.Lane = 0;
	for (const FRewardPop& R : Rewards)
	{
		if ((R.Kind == static_cast<uint8>(ESORewardKind::Xp)) == (Kind == ESORewardKind::Xp))
		{
			Pop.Lane = FMath::Max(Pop.Lane, R.Lane + 1);
		}
	}
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
	FType Type(Canvas, AuditPtr());
	const FGlass Pane = MakeGlass(P, S);
	// the owner's screens: a radar dish in the corner, dark and clear, a thin cyan rim lit from inside and nothing
	// else round it; 14 % smaller than the last round's
	const FVector2D C(L.X0 + 110.0f * S, 110.0f * S);
	const float R = 72.0f * S;
	// a 300 m window round the player, north up; the window stops at the map's edges (no wrapping), so near an edge
	// the player stands off the middle
	const float Window = FMath::Min(1.0f, 30000.0f / FMath::Max(Info->HalfSize * 2.0f, 1.0f));
	const float UVPerPx = Window / (2.0f * R);
	const FVector2D Me = Info->WorldToMap(Player->GetActorLocation());
	const FVector2D UVc(FMath::Clamp(static_cast<float>(Me.X), Window * 0.5f, 1.0f - Window * 0.5f), FMath::Clamp(static_cast<float>(Me.Y), Window * 0.5f, 1.0f - Window * 0.5f));
	auto OnMap = [&](const FVector& World) { return C + (Info->WorldToMap(World) - UVc) / UVPerPx; };

	{
		FGlassStyle Dish;
		Dish.FillA = A(Glass, 0.72f);
		Dish.FillB = A(GlassDeep, 0.82f);
		Dish.Glow = Cyan;
		Dish.GlowA = 0.32f;
		Dish.GlowW = 7.0f * S;
		Dish.Edge = A(Cyan, 0.85f);
		Dish.EdgeT = 1.3f * S;
		Dish.ShadowOff = 4.0f * S;
		Dish.ShadowBlur = 8.0f * S;
		Dish.ShadowA = 0.35f;
		Pane.Disc(C, R + 3.0f * S, Dish);
	}
	Reserve(C.X - R - 12.0f * S, C.Y - R - 32.0f * S, 2.0f * R + 24.0f * S, 2.0f * R + 32.0f * S + 50.0f * S);
	// the picture, dark, fading into the rim; a faint second ring outside
	P.TexturedDisc(C, R, Map->GetResource(), UVc, UVPerPx, FLinearColor(0.42f, 0.52f, 0.68f, 0.78f));
	P.Ring(C, R * 0.80f, R, FLinearColor(0, 0, 0, 0), FLinearColor(0.0f, 0.004f, 0.012f, 0.75f));
	P.Ring(C, R + 7.5f * S, R + 8.5f * S, A(Line, 0.28f), A(Line, 0.28f));

	// where the player looks: a soft, lighter cone
	const float Yaw = FMath::DegreesToRadians(Player->GetControlRotation().Yaw);
	const FVector2D Fwd(FMath::Sin(Yaw), -FMath::Cos(Yaw));     // map space: up = world +X, right = world +Y
	const FVector2D Rt(-Fwd.Y, Fwd.X);
	const FVector2D Mine = C + (Me - UVc) / UVPerPx;
	const float Heading = FMath::Atan2(Fwd.Y, Fwd.X);
	P.Sector(Mine, R * 0.95f, Heading - FMath::DegreesToRadians(40.0f), Heading + FMath::DegreesToRadians(40.0f), A(Cyan, 0.26f), A(Cyan, 0.0f));

	// the important places: only the few nearest, small (the owner's brief: fewer markers)
	{
		TArray<TPair<float, const ASOMapPoint*>> Near;
		for (TActorIterator<ASOMapPoint> It(GetWorld()); It; ++It)
		{
			const FVector2D Pt = OnMap(It->GetActorLocation());
			if ((Pt - C).Size() <= R - 8.0f * S)
			{
				Near.Add({ static_cast<float>((Pt - Mine).Size()), *It });
			}
		}
		Near.Sort([](const TPair<float, const ASOMapPoint*>& X, const TPair<float, const ASOMapPoint*>& Y) { return X.Key < Y.Key; });
		for (int32 i = 0; i < FMath::Min(Near.Num(), 5); ++i)
		{
			const FVector2D Pt = OnMap(Near[i].Value->GetActorLocation());
			P.Fill(Diamond(Pt, 4.2f * S, 4.2f * S), A(FLinearColor::Black, 0.5f));
			P.Fill(Diamond(Pt, 3.0f * S, 3.0f * S), A(ASOMapPoint::KindColor(Near[i].Value->Kind), 0.9f));
		}
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
			P.Stroke(Diamond(Pt, 6.0f * S, 6.0f * S), Gold, 1.4f * S);
			P.Fill(Diamond(Pt, 2.2f * S, 2.2f * S), Gold);
		}
	}
	// creatures: the ones this side knows of (awake to the fight, or close), red points; a boss a ring
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
			P.Ring(Pt, 3.5f * S, 5.5f * S, Lock, Lock);
		}
		else
		{
			P.Disc(Pt, 4.0f * S, A(FLinearColor::Black, 0.5f), A(FLinearColor::Black, 0.0f), 16);
			P.Disc(Pt, 3.0f * S, Lock, A(Lock, 0.85f), 16);
		}
	}
	// you
	P.Tri(Mine + Fwd * 10.0f * S, Mine - Fwd * 6.0f * S + Rt * 6.0f * S, Mine - Fwd * 6.0f * S - Rt * 6.0f * S, A(FLinearColor::Black, 0.7f));
	P.Tri(Mine + Fwd * 8.0f * S, Mine - Fwd * 4.5f * S + Rt * 4.5f * S, Mine - Fwd * 4.5f * S - Rt * 4.5f * S, Cyan);
	// the rim's marks: north in gold above it, a short tick at the other three points
	for (int32 i = 1; i < 4; ++i)
	{
		const float T = FMath::DegreesToRadians(i * 90.0f - 90.0f);
		const FVector2D D(FMath::Cos(T), FMath::Sin(T));
		P.Segment(C + D * (R + 4.5f * S), C + D * (R + 8.5f * S), A(Line, 0.8f), 1.2f * S);
	}
	P.Segment(C + FVector2D(0.0f, -(R + 4.5f * S)), C + FVector2D(0.0f, -(R + 8.5f * S)), Gold, 1.4f * S);
	P.Flush();
	Type.Face = EFace::Cond;
	Type.DrawCentred(TEXT("N"), C.X, C.Y - R - 24.0f * S, Type.Medium, 1.1f * S, Gold);
	Type.Face = EFace::Auto;

	// the area's name, and where in it (the nearest important place within 400 m, or the operation's stage): the
	// name in bright tracked capitals, the place dim and smaller under it, both left-aligned with the dish
	const float NameX = C.X - R - 2.0f * S, NameY = C.Y + R + 20.0f * S;
	Type.Label(Info->AreaName.ToString(), NameX, NameY, Type.Medium, 1.15f * S, Ink, 3.0f * S);
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
		Type.Label(Where, NameX, NameY + 20.0f * S, Type.Small, 0.95f * S, Dim, 2.0f * S);
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
	FType Type(Canvas, AuditPtr());
	// a slim scale across the top (the owner's screens): a thin line fading to its ends, ticks, the letters above
	// it, a gold mark on its middle, the objective's bearing and the places as small marks on the line
	const float Y = 18.0f * S, HalfW = 230.0f * S, PxPerDeg = HalfW / 100.0f;
	const float LineY = Y + 14.0f * S;
	Reserve(L.CX - HalfW - 10.0f * S, Y - 20.0f * S, 2.0f * HalfW + 20.0f * S, 56.0f * S);
	const float Yaw = FRotator::NormalizeAxis(Player->GetControlRotation().Yaw);   // 0 = north (world +X), 90 = east
	auto Fade = [&](float Deg) { return FMath::Clamp(1.0f - FMath::Pow(FMath::Abs(Deg) / 100.0f, 3.0f), 0.0f, 1.0f); };
	auto Rel = [&](float WorldDeg) { return FRotator::NormalizeAxis(WorldDeg - Yaw); };

	P.FillAcross(Rectangle(L.CX - HalfW, LineY, HalfW, 1.0f * S), A(Line, 0.0f), A(Line, 1.6f));
	P.FillAcross(Rectangle(L.CX, LineY, HalfW, 1.0f * S), A(Line, 1.6f), A(Line, 0.0f));
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
		P.Segment(FVector2D(X, LineY - (bMajor ? 6.0f : 3.0f) * S), FVector2D(X, LineY), A(Line, Fade(R) * (bMajor ? 1.0f : 0.55f)), 1.0f * S);
	}
	// the objective's bearing: a gold diamond on the line; the important places: small dim ones
	if (const ASOOperation* Op = ASOOperation::Get(this))
	{
		if (const FSOStage* Stage = Op->GetState() == ESOOperationState::Active ? Op->GetStage() : nullptr; Stage && (Stage->Kind == ESOStageKind::Travel || Stage->Kind == ESOStageKind::Hold))
		{
			const FVector To = Stage->Goal - Player->GetActorLocation();
			const float R = Rel(FMath::RadiansToDegrees(FMath::Atan2(To.Y, To.X)));
			const float X = L.CX + FMath::Clamp(R, -100.0f, 100.0f) * PxPerDeg;
			P.Fill(Diamond(FVector2D(X, LineY + 0.5f * S), 4.5f * S, 4.5f * S), Gold);
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
		P.Fill(Diamond(FVector2D(L.CX + R * PxPerDeg, LineY + 0.5f * S), 2.6f * S, 2.6f * S), A(ASOMapPoint::KindColor(It->Kind), Fade(R) * 0.75f));
	}
	// the heading's mark: a small gold diamond standing on the line's middle
	P.Fill(Diamond(FVector2D(L.CX, LineY - 5.0f * S), 4.5f * S, 5.0f * S), A(FLinearColor::Black, 0.5f));
	P.Stroke(Diamond(FVector2D(L.CX, LineY - 5.0f * S), 4.0f * S, 4.5f * S), Gold, 1.2f * S);
	P.Flush();
	// the letters above the line (the condensed face, north in gold), the heading small under it
	const TPair<float, const TCHAR*> Cardinals[] = { { 0.0f, TEXT("N") }, { 90.0f, TEXT("E") }, { 180.0f, TEXT("S") }, { 270.0f, TEXT("W") } };
	Type.Face = EFace::Cond;
	for (const TPair<float, const TCHAR*>& Cd : Cardinals)
	{
		const float R = Rel(Cd.Key);
		if (FMath::Abs(R) < 100.0f && FMath::Abs(R) > 4.0f)
		{
			Type.DrawCentred(Cd.Value, L.CX + R * PxPerDeg, Y - 14.0f * S, Type.Medium, 1.3f * S, A(Cd.Key == 0.0f ? Gold : Ink, Fade(R)));
		}
		else if (FMath::Abs(R) <= 4.0f)
		{
			// (right over the mark: drawn a little higher, so neither hides the other)
			Type.DrawCentred(Cd.Value, L.CX, Y - 17.0f * S, Type.Medium, 1.3f * S, A(Cd.Key == 0.0f ? Gold : Ink, 1.0f));
		}
	}
	Type.Face = EFace::Auto;
	Type.Number(FString::Printf(TEXT("%d"), FMath::RoundToInt(FMath::Fmod(Yaw + 360.0f, 360.0f))), L.CX, LineY + 8.0f * S, Type.Small, 1.0f * S, A(Dim, 0.9f), 0.5f);
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
	FType Type(Canvas, AuditPtr());
	const FGlass Pane = MakeGlass(P, S);
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
	{
		FGlassStyle St;
		St.Glow = Gold;
		St.GlowA = 0.2f;
		St.GlowW = 22.0f * S;
		Pane.Plate4(X, Y, W, H, 9.0f * S, St);
		Reserve(X, Y, W, H);
	}
	P.Segment(FVector2D(X + 10.0f * S, Y), FVector2D(X + W - 10.0f * S, Y), A(Gold, 0.85f), 1.5f * S);
	// the glyph: a diamond with a point in it
	const FVector2D G(X + 26.0f * S, Y + 21.0f * S);
	P.Stroke(Diamond(G, 9.0f * S, 9.0f * S), Gold, 1.5f * S);
	P.Fill(Diamond(G, 3.0f * S, 3.0f * S), Gold);
	Pane.Bar(X + 46.0f * S, Y + 38.0f * S, W - 62.0f * S, 4.0f * S, Frac, Gold, GlassDeep, 0.8f * S);
	P.Flush();
	// the words: the objective, shrunk to fit beside the count
	const float RightW = Type.Size(Right, Type.Medium, 1.1f * S).X;
	const float Room = W - 62.0f * S - RightW - 16.0f * S;
	float Scale = 1.05f * S, Spacing = 1.8f * S;
	while (Type.LabelWidth(Stage->Objective.ToString(), Type.Medium, Scale, Spacing) > Room && Scale > 0.7f * S)
	{
		Scale -= 0.05f * S;
		Spacing = FMath::Max(Spacing - 0.3f * S, 0.5f * S);
	}
	Type.Label(Stage->Objective.ToString(), X + 46.0f * S, Y + 10.0f * S, Type.Medium, Scale, Ink, Spacing);
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
	FType Type(Canvas, AuditPtr());
	const FGlass Pane = MakeGlass(P, S);
	// the owner's screens: a square cell per condition with its mark in its own colour and the time left under it
	float X = L.X1 - 40.0f * S;
	const float X0 = X;
	const float Y = 24.0f * S, Side = 34.0f * S;
	for (int32 i = UE_ARRAY_COUNT(Conditions) - 1; i >= 0; --i)
	{
		const FConditionLook& Cnd = Conditions[i];
		if (!Player->HasStatus(*Cnd.Tag))
		{
			continue;
		}
		const float Left = Player->GetStatusTimeLeft(*Cnd.Tag);
		const float Pulse = Left > 0.0f && Left < 1.5f ? 0.6f + 0.4f * FMath::Abs(FMath::Sin(L.Now * 8.0f)) : 1.0f;
		const FRegion Cell(X - Side, Y, Side, Side);
		{
			FGlassStyle St;
			St.Glow = Cnd.Color;
			St.GlowA = 0.45f * Pulse;
			St.GlowW = 8.0f * S;
			St.Edge = A(Cnd.Color, 0.9f * Pulse);
			St.EdgeT = 1.2f * S;
			St.ShadowOff = 3.0f * S;
			St.ShadowBlur = 5.0f * S;
			Pane.Plate4(Cell.X, Cell.Y, Cell.W, Cell.H, 5.0f * S, St);
		}
		ConditionGlyph(P, Cnd.Glyph, Cell.Centre(), 9.0f * S, A(Cnd.Color, Pulse), 1.6f * S);
		P.Flush();
		if (Left > 0.0f)
		{
			const int32 T = FMath::CeilToInt(Left);
			Type.Number(FString::Printf(TEXT("%d:%02d"), T / 60, T % 60), Cell.Centre().X, Cell.Bottom() + 4.0f * S, Type.Small, 1.05f * S, A(Ink, Pulse), 0.5f);
		}
		X -= Side + 12.0f * S;
	}
	if (X < X0)
	{
		Reserve(X + 12.0f * S, Y - 2.0f * S, X0 - X - 12.0f * S, Side + 26.0f * S);
	}
}

void ASOHUD::DrawTracked(const FLayout& L)
{
	const float S = L.S;
	FPainter P(Canvas);
	FType Type(Canvas, AuditPtr());
	const FGlass Pane = MakeGlass(P, S);
	const float W = 330.0f * S, X = L.X1 - 40.0f * S - W;
	float Y = 112.0f * S;
	const ASOOperation* Op = ASOOperation::Get(this);
	if (Op && Op->GetState() == ESOOperationState::Active && Op->GetStage())
	{
		// the header
		Pane.Plate(X, Y, W, 26.0f * S, 6.0f * S, FGlassStyle());
		Reserve(X, Y, W, 26.0f * S);
		P.Segment(FVector2D(X + 6.0f * S, Y), FVector2D(X + W, Y), A(Gold, 0.7f), 1.0f * S);
		P.Flush();
		Type.Label(TEXT("Tracked"), X + 12.0f * S, Y + 6.0f * S, Type.Small, 1.05f * S, Gold, 2.4f * S);
		Type.Label(Op->OperationName.ToString(), X + W - 12.0f * S, Y + 6.0f * S, Type.Small, 0.95f * S, Dim, 1.4f * S, 1.0f);
		Y += 26.0f * S;
		// the stage before (done), this one, the next: a glyph, the title, its bar and count
		const int32 Idx = Op->GetStageIndex();
		TArray<int32> Rows;
		if (Idx > 0) { Rows.Add(Idx - 1); }
		Rows.Add(Idx);
		if (Op->Stages.IsValidIndex(Idx + 1)) { Rows.Add(Idx + 1); }
		const float RowH = 38.0f * S;
		{
			FGlassStyle St;
			St.Alpha = 0.9f;
			Pane.Plate4(X, Y, W, RowH * Rows.Num() + 6.0f * S, 0.0f, St);
			Reserve(X, Y, W, RowH * Rows.Num() + 6.0f * S);
		}
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
			Pane.Bar(X + 30.0f * S, RY + 22.0f * S, W - 44.0f * S, 3.0f * S, Frac, bNow ? Gold : A(Dim, 0.6f), GlassDeep, 0.8f * S, bDone ? 0.5f : 1.0f);
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
	FType Type(Canvas, AuditPtr());
	const FGlass Pane = MakeGlass(P, S);
	const float W = 400.0f * S, H = 100.0f * S;
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
		{
			FGlassStyle St;
			St.Alpha = Alpha;
			St.Edge = A(Col, 0.6f);
			St.Glow = Col;
			St.GlowA = 0.26f;
			St.GlowW = 28.0f * S;
			Pane.Plate(X, Y, W, H, 10.0f * S, St);
			Reserve(X, Y, W, H);
		}
		// its rarity's light down the left and under the glass
		P.FillAcross(Rectangle(X, Y + 10.0f * S, 90.0f * S, H - 10.0f * S), A(Col, 0.22f * Alpha), A(Col, 0.0f));
		P.Fill(Rectangle(X, Y + 10.0f * S, 3.0f * S, H - 10.0f * S), A(Col, Alpha));
		P.Flush();
		Type.Label(TEXT("New item"), X + 16.0f * S, Y + 9.0f * S, Type.Small, 1.05f * S, A(Col, Alpha), 2.8f * S);
		// the name, fitted to the room before the picture
		Type.Face = EFace::Medium;
		const float NameRoom = W - 152.0f * S;
		Type.Fit(Card.Item.Name, X + 16.0f * S, Y + 30.0f * S, NameRoom, Type.Large, 1.3f * S, 0.85f * S, A(Ink, Alpha));
		Type.Face = EFace::Auto;
		FString LineText = Rar ? Rar->Name.ToString() : FString();
		if (Data)
		{
			LineText += (LineText.IsEmpty() ? TEXT("") : TEXT("  ·  ")) + Data->ClassName.ToString() + TEXT("  ·  ") + Data->DisplayName.ToString();
		}
		// its line too (a long kind's name ran under the picture)
		Type.FitLabel(LineText, X + 16.0f * S, Y + 70.0f * S, NameRoom, Type.Small, 0.9f * S, 0.68f * S, A(Dim, Alpha), 1.4f * S);
		Type.Number(FString::Printf(TEXT("%d"), Card.Item.Power), X + W - 14.0f * S, Y + 6.0f * S, Type.Large, 1.0f * S, A(Gold, Alpha), 1.0f);
		if (UTexture2D* Icon = IconOf(Card.Item.Archetype))
		{
			Picture(Icon, X + W - 130.0f * S, Y + 34.0f * S, 116.0f * S, 58.0f * S, Alpha, TEXT("new item"));
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
		{
			FGlassStyle St;
			St.Alpha = Alpha * 0.9f;
			St.ShadowOff = 3.0f * S;
			St.ShadowBlur = 4.0f * S;
			Pane.Plate(X, Y, Sz.X + 24.0f * S, Sz.Y + 10.0f * S, 5.0f * S, St);
			Reserve(X, Y, Sz.X + 24.0f * S, Sz.Y + 10.0f * S);
		}
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
	FType Type(Canvas, AuditPtr());
	const FGlass Pane = MakeGlass(P, S);
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
		{
			FGlassStyle St;
			St.Alpha = Alpha;
			St.Edge = bLocked ? Lock : Line;
			St.Glow = Lock;
			St.GlowA = bLocked ? 0.4f : 0.0f;
			St.GlowW = 8.0f * S;
			St.ShadowOff = 3.0f * S;
			St.ShadowBlur = 4.0f * S;
			Pane.Plate4(NX - 2.0f * S, NY - 2.0f * S, BoxW, 18.0f * S, 3.0f * S, St);
		}
		Reserve(FMath::Min(NX - 4.0f * S, BX - 2.0f * S), NY - 4.0f * S, FMath::Max(Total + 8.0f * S, BW + 4.0f * S), 18.0f * S + 20.0f * S);
		// the bar: health red, the shield as a thin line over it
		if (FHudAudit* Au = AuditPtr())
		{
			Au->Note(FHudAudit::Bar, FRegion(BX - 1.5f * S, BY - 1.5f * S, BW + 3.0f * S, 9.0f * S), TEXT("creature bar"));
		}
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
	FType Type(Canvas, AuditPtr());
	const FGlass Pane = MakeGlass(P, S);
	const USOInventoryComponent* Inventory = FeedInventory.Get();
	const FLinearColor KitLight = Player->GetAbilityColor();
	const FVector2D E(L.X0 + 78.0f * S, L.H - 88.0f * S);
	const float R = 40.0f * S;
	Reserve(L.X0 + 30.0f * S, L.H - 136.0f * S, 336.0f * S, 126.0f * S);
	const float HealthFrac = Player->GetHealth() / FMath::Max(Player->GetMaxHealth(), 1.0f);
	const bool bLow = HealthFrac < 0.35f;
	const float LowPulse = bLow ? 0.7f + 0.3f * FMath::Abs(FMath::Sin(L.Now * 5.0f)) : 1.0f;
	const FLinearColor HealthCol = bLow ? A(Hurt, LowPulse) : FLinearColor(0.86f, 0.30f, 0.28f);   // a muted red

	// the owner's screens: the emblem a diamond of graphite with a cyan rim and the kit's light in it, the broken
	// orbit at its heart; nothing behind the bars but their troughs
	{
		FGlassStyle St;
		St.Edge = A(Cyan, 0.9f);
		St.EdgeT = 1.5f * S;
		St.Glow = KitLight;
		St.GlowA = 0.4f;
		St.GlowW = 12.0f * S;
		St.ShadowOff = 5.0f * S;
		St.ShadowBlur = 8.0f * S;
		Pane.Diamond(E, R, R, St);
	}
	P.Stroke(Diamond(E, R * 0.80f, R * 0.80f), A(KitLight, 0.5f), 1.0f * S);
	OrbitMark(P, E, 13.0f * S, bLow ? A(Hurt, LowPulse) : Ink, 2.0f * S);
	// the level: a gold badge under the emblem (the owner's brief: more prominent), its word beside it
	const FVector2D LB(E.X, E.Y + R + 17.0f * S);
	if (Inventory)
	{
		FGlassStyle B;
		B.FillA = A(Mix(Gold, GlassDeep, 0.78f), 0.95f);
		B.FillB = A(GlassDeep, 0.95f);
		B.Edge = A(Gold, 0.95f);
		B.EdgeT = 1.2f * S;
		B.Glow = Gold;
		B.GlowA = 0.3f;
		B.GlowW = 6.0f * S;
		B.ShadowOff = 3.0f * S;
		B.ShadowBlur = 4.0f * S;
		Pane.Diamond(LB, 15.0f * S, 15.0f * S, B);
	}
	// the bars: the shield cyan, the health a muted red, each with its mark and word above it and its number at its
	// end
	const float BX = E.X + R + 20.0f * S, BW = 210.0f * S, BH = 10.0f * S;
	const float ShieldY = L.H - 108.0f * S, HealthY = L.H - 76.0f * S;
	const bool bShield = Player->GetMaxShield() > 0.0f;
	if (bShield)
	{
		Pane.Bar(BX, ShieldY, BW, BH, Player->GetShield() / Player->GetMaxShield(), A(Cyan, 0.95f), GlassDeep, 1.0f * S);
	}
	Pane.Bar(BX, HealthY, BW, BH, HealthFrac, HealthCol, GlassDeep, 1.0f * S);
	// the level's progress: a thin gold line under the health bar, eased toward the real fill (a kill is SEEN to
	// fill it); at a level-up it runs to the end, flares, and starts again from nothing
	const USOProgressionTable& Rules = USOProgressionTable::Get();
	if (Inventory)
	{
		const float XpFrac = static_cast<float>(Inventory->GetXp()) / FMath::Max(Rules.XpForLevel(Inventory->GetLevel()), 1);
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
		Pane.Bar(BX, HealthY + BH + 7.0f * S - Flare * 1.0f * S, BW, (2.5f + 2.0f * Flare) * S, XpShown, A(Gold, 0.85f + 0.15f * Flare), GlassDeep, 0.5f * S, 0.9f, 0.0f, 0.0f, 0.0f);
	}
	// the marks before the words: a small shield, a cross
	{
		const FVector2D SM(BX + 5.0f * S, ShieldY - 8.0f * S), HM(BX + 5.0f * S, HealthY - 8.0f * S);
		const float M = 4.0f * S;
		if (bShield)
		{
			P.Stroke({ SM + FVector2D(-M, -M * 0.7f), SM + FVector2D(0, -M), SM + FVector2D(M, -M * 0.7f), SM + FVector2D(M * 0.85f, M * 0.1f), SM + FVector2D(0, M), SM + FVector2D(-M * 0.85f, M * 0.1f) }, A(Dim, 0.9f), 1.1f * S, true);
		}
		P.Segment(HM + FVector2D(-M, 0), HM + FVector2D(M, 0), A(Dim, 0.9f), 1.4f * S);
		P.Segment(HM + FVector2D(0, -M), HM + FVector2D(0, M), A(Dim, 0.9f), 1.4f * S);
	}
	P.Flush();
	// the words
	if (bShield)
	{
		Type.Label(TEXT("Shield"), BX + 14.0f * S, ShieldY - 14.0f * S, Type.Small, 0.95f * S, Dim, 2.2f * S);
		Type.Number(FString::Printf(TEXT("%d"), FMath::CeilToInt(Player->GetShield())), BX + BW + 10.0f * S, ShieldY - 6.0f * S, Type.Large, 1.0f * S, Ink);
	}
	Type.Label(TEXT("Health"), BX + 14.0f * S, HealthY - 14.0f * S, Type.Small, 0.95f * S, Dim, 2.2f * S);
	Type.Number(FString::Printf(TEXT("%d"), FMath::CeilToInt(Player->GetHealth())), BX + BW + 10.0f * S, HealthY - 6.0f * S, Type.Large, 1.0f * S, bLow ? A(Hurt, LowPulse) : Ink);
	if (Inventory)
	{
		Type.Number(FString::FromInt(Inventory->GetLevel()), LB.X, LB.Y - 7.0f * S, Type.Medium, 1.1f * S, Gold, 0.5f);
		Type.Label(TEXT("Level"), LB.X + 20.0f * S, LB.Y - 5.0f * S, Type.Small, 0.8f * S, A(Gold, 0.85f), 1.8f * S);
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
	FType Type(Canvas, AuditPtr());
	const FGlass Pane = MakeGlass(P, S);
	const bool bJammed = Player->HasStatus(SOTags::Status_Jam);
	const FLinearColor KitLight = Player->GetAbilityColor();
	const float UltFrac = Player->GetMaxUltimate() > 0.0f ? Player->GetUltimate() / Player->GetMaxUltimate() : 0.0f;
	const bool bUltFull = UltFrac >= 0.995f;
	// the owner's second screen: the three cells in a row (a fifth bigger than the last round's), each key in a
	// small badge under its cell; under the row the ultimate, a gold diamond between two bars that fill out from it
	const float Y = L.H - 118.0f * S;
	const float R = 26.0f * S, Gap = 72.0f * S;
	Reserve(L.CX - 186.0f * S, L.H - 150.0f * S, 372.0f * S, 140.0f * S);
	const ESOAbilitySlot Order[] = { ESOAbilitySlot::Grenade, ESOAbilitySlot::Melee, ESOAbilitySlot::Class };
	auto KeyBadge = [&](const FVector2D& At, const TCHAR* Key, const FLinearColor& Col, bool bLit)
	{
		FGlassStyle K;
		K.FillA = bLit ? A(Mix(Col, GlassDeep, 0.7f), 0.95f) : A(Glass, 0.9f);
		K.FillB = A(GlassDeep, 0.95f);
		K.Edge = bLit ? A(Col, 0.9f) : A(Line, 0.5f);
		K.EdgeT = 1.0f * S;
		K.ShadowA = 0.2f;
		K.ShadowOff = 2.0f * S;
		K.ShadowBlur = 3.0f * S;
		Pane.Plate4(At.X - 9.0f * S, At.Y, 18.0f * S, 18.0f * S, 3.0f * S, K);
		Type.Label(Key, At.X, At.Y + 3.0f * S, Type.Small, 0.95f * S, bLit ? Ink : Dim, 0.0f, 0.5f);
	};
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
		const FVector2D C(L.CX + (k - 1) * Gap, Y);
		{
			FGlassStyle St;
			St.Glow = KitLight;
			St.GlowA = bReady ? 0.5f : 0.0f;
			St.GlowW = 12.0f * S;
			St.Edge = bReady ? A(KitLight, 0.95f) : (bJammed ? A(Hurt, 0.8f) : A(Line, 0.6f));
			St.EdgeT = 1.3f * S;
			St.ShadowOff = 4.0f * S;
			St.ShadowBlur = 6.0f * S;
			Pane.HexUp(C, R, St);
			if (!bReady && Cooldown > 0.0f)
			{
				// the cooldown coming back: a ring round the cell, filling clockwise from the top
				FGlassStyle Track;
				Track.FillA = Track.FillB = A(Line, 0.2f);
				Track.Edge = A(Line, 0.0f);
				Track.ShadowA = 0.0f;
				Pane.Ring(C, R + 5.5f * S, 2.4f * S, -90.0f, 270.0f, Track);
				FGlassStyle Arc;
				Arc.FillA = Arc.FillB = A(KitLight, 0.95f);
				Arc.Edge = A(KitLight, 0.0f);
				Arc.ShadowA = 0.0f;
				Pane.Ring(C, R + 5.5f * S, 2.4f * S, -90.0f, -90.0f + 360.0f * FMath::Clamp(1.0f - Left / Cooldown, 0.0f, 0.999f), Arc);
			}
		}
		// its mark; dim and behind the count while it cools
		const bool bCooling = !bReady && Left > 0.0f;
		SlotGlyph(P, Slot, C, 11.0f * S, bReady ? Ink : A(Dim, bCooling ? 0.22f : 0.55f), 1.8f * S);
		if (bJammed)
		{
			ConditionGlyph(P, 4, C, 9.0f * S, A(Hurt, 0.9f), 2.0f * S);
		}
		const float Age = L.Now - SlotReadyAt[i];
		if (Age >= 0.0f && Age < 0.6f)
		{
			P.Stroke(Hex(C, R + Age * 40.0f * S), A(Gold, (1.0f - Age / 0.6f) * 0.9f), 2.0f * S);
		}
		P.Flush();
		if (bCooling)
		{
			Type.Number(Left >= 10.0f ? FString::Printf(TEXT("%d"), FMath::CeilToInt(Left)) : FString::Printf(TEXT("%.1f"), Left), C.X, C.Y - 7.0f * S, Type.Medium, 1.15f * S, Ink, 0.5f);
		}
		if (MaxCharges > 1)
		{
			Type.Number(FString::FromInt(Charges), C.X + R + 3.0f * S, C.Y - R - 2.0f * S, Type.Small, 1.0f * S, bReady ? Ink : Dim);
		}
		KeyBadge(FVector2D(C.X, C.Y + R + 8.0f * S), SlotKey(Slot), KitLight, bReady);
	}
	// the ultimate: a diamond that fills from its foot as it charges, gold through and through when it is there,
	// a bar either side filling outward from it; the share under it, or the word
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
			const FVector2D C(L.CX, L.H - 44.0f * S);
			const float UR = 18.0f * S, BarW = 118.0f * S, BarH = 5.0f * S;
			const float Pulse = bReady ? 0.75f + 0.25f * FMath::Abs(FMath::Sin(L.Now * 3.0f)) : 1.0f;
			const FLinearColor Fill = bUltFull ? A(Gold, Pulse) : A(Cyan, 0.9f);
			Pane.Bar(C.X - UR - 10.0f * S - BarW, C.Y - BarH * 0.5f, BarW, BarH, UltFrac, Fill, GlassDeep, 0.8f * S, 1.0f, 0.0f, 0.0f, 0.3f, 3);
			Pane.Bar(C.X + UR + 10.0f * S, C.Y - BarH * 0.5f, BarW, BarH, UltFrac, Fill, GlassDeep, 0.8f * S, 1.0f, 0.0f, 0.0f, 0.3f, 1);
			{
				FGlassStyle St;
				St.FillA = bReady ? A(Gold, 0.5f * Pulse) : A(Mix(Gold, Glass, 0.5f), 0.9f);
				St.FillB = bReady ? A(Gold, 0.22f) : A(GlassDeep, 0.95f);
				St.Edge = bReady ? A(Gold, Pulse) : A(Line, 0.75f);
				St.EdgeT = 1.6f * S;
				St.Glow = Gold;
				St.GlowA = bReady ? 0.6f * Pulse : 0.0f;
				St.GlowW = 12.0f * S;
				St.ShadowOff = 4.0f * S;
				St.ShadowBlur = 6.0f * S;
				Pane.Diamond(C, UR, UR, St, bReady ? 1.0f : FMath::Clamp(UltFrac, 0.0f, 1.0f), 2);
			}
			SlotGlyph(P, ESOAbilitySlot::Ultimate, C, 8.5f * S, bReady ? A(FLinearColor::White, Pulse) : A(Dim, 0.55f), 1.6f * S);
			const float Age = L.Now - UltimateReadyAt;
			if (Age >= 0.0f && Age < 0.8f)
			{
				P.Stroke(Diamond(C, UR + Age * 60.0f * S, UR + Age * 60.0f * S), A(Gold, (1.0f - Age / 0.8f) * 0.9f), 2.5f * S);
			}
			if (bUltFull)
			{
				P.Fill(Rectangle(C.X - UR - 10.0f * S - BarW, C.Y - BarH * 0.5f - 2.0f * S, 2.0f * (BarW + UR + 10.0f * S), BarH + 4.0f * S), A(Gold, 0.08f + 0.08f * FMath::Abs(FMath::Sin(L.Now * 3.0f))));
			}
			P.Flush();
			const float WordY = C.Y + UR + 5.0f * S;
			if (bReady)
			{
				Type.Label(TEXT("Ultimate ready"), C.X, WordY, Type.Small, 1.0f * S, A(Gold, 0.8f + 0.2f * FMath::Abs(FMath::Sin(L.Now * 3.0f))), 3.0f * S, 0.5f);
			}
			else
			{
				Type.Number(FString::Printf(TEXT("%d%%"), FMath::FloorToInt(UltFrac * 100.0f)), C.X, WordY - 1.0f * S, Type.Medium, 1.1f * S, bUltFull ? Gold : Ink, 0.5f);
			}
			KeyBadge(FVector2D(C.X + UR + 10.0f * S + BarW + 16.0f * S, C.Y - 9.0f * S), SlotKey(ESOAbilitySlot::Ultimate), Gold, bReady);
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
	FType Type(Canvas, AuditPtr());
	const FGlass Pane = MakeGlass(P, S);
	const USOInventoryComponent* Inventory = FeedInventory.Get();
	const USOWeaponData* Data = Weapon->GetData();
	const FSOWeaponInstance& Held = Weapon->GetInstance();
	const FLinearColor HeldCol = RarityColour(Held.Rarity);
	// the owner's screens: the panel in the corner with a safe margin, the three cards above it; inside it every
	// thing in a region of its own (the picture's column at the right, the name's row, the kind's row, the count's
	// room), so nothing is ever drawn over anything else
	const float W = 360.0f * S, H = 100.0f * S;
	const float X = L.X1 - 40.0f * S - W, Y = L.H - 44.0f * S - H;
	const FRegion Panel(X, Y, W, H);

	// the three cards: the active one lit with a cyan rim, each gun's picture beside its number in a column of its own
	const float CW = 86.0f * S, CH = 40.0f * S, CGap = 8.0f * S, CY = Y - CH - 10.0f * S;
	Reserve(X - 6.0f * S, CY - 6.0f * S, W + 12.0f * S, H + CH + 16.0f * S + 42.0f * S);
	for (int32 Slot = 0; Slot < USOInventoryComponent::NumSlots; ++Slot)
	{
		const FSOWeaponInstance* Copy = Inventory ? Inventory->GetEquipped(Slot) : nullptr;
		const bool bActive = Inventory ? Inventory->GetActiveSlot() == Slot : Slot == 0;
		const FRegion Card(X + W - (3 - Slot) * (CW + CGap) + CGap, CY, CW, CH);
		const float Alpha = bActive ? 1.0f : 0.55f;
		const FLinearColor Col = Copy ? RarityColour(Copy->Rarity) : A(Dim, 0.5f);
		{
			FGlassStyle St;
			St.Alpha = Alpha;
			St.Edge = bActive ? A(Cyan, 0.95f) : A(Line, 0.45f);
			St.EdgeT = bActive ? 1.3f * S : 1.0f * S;
			St.Glow = Cyan;
			St.GlowA = bActive ? 0.3f : 0.0f;
			St.GlowW = 10.0f * S;
			St.ShadowOff = 4.0f * S;
			St.ShadowBlur = 6.0f * S;
			Pane.Plate(Card.X, Card.Y, Card.W, Card.H, 5.0f * S, St);
		}
		P.Fill(Rectangle(Card.X + 6.0f * S, Card.Bottom() - 2.5f * S, Card.W - 12.0f * S, 2.0f * S), A(Col, Alpha));
		P.Flush();
		FRegion Inner = Card.Inset(4.0f * S, 3.0f * S);
		const FRegion NumCol = Inner.CutLeft(11.0f * S, 2.0f * S);
		Type.Draw(FString::FromInt(Slot + 1), NumCol.X, NumCol.Y - 1.0f * S, Type.Small, 0.95f * S, bActive ? Ink : Dim);
		const FName Arch = Copy ? Copy->Archetype : (Slot == 0 && Data ? Data->Archetype : NAME_None);
		if (UTexture2D* Icon = IconOf(Arch))
		{
			const float IH = Inner.W * 0.5f;
			Picture(Icon, Inner.X, Inner.Y + (Inner.H - IH) * 0.5f - 1.0f * S, Inner.W, IH, bActive ? 1.0f : 0.5f, FString::Printf(TEXT("slot %d"), Slot + 1));
		}
		else if (!Copy)
		{
			Type.DrawCentred(TEXT("\u2014"), Inner.Centre().X, Inner.Y + 8.0f * S, Type.Medium, 1.0f * S, A(Dim, 0.5f));
		}
	}

	// the panel, the rarity's light inside its rim
	{
		FGlassStyle St;
		St.Glow = HeldCol;
		St.GlowA = 0.14f;
		St.GlowW = 32.0f * S;
		Pane.Plate(Panel.X, Panel.Y, Panel.W, Panel.H, 9.0f * S, St);
	}
	P.Segment(FVector2D(X + W - 70.0f * S, Y), FVector2D(X + W, Y), A(HeldCol, 0.9f), 1.5f * S);
	// the regions
	FRegion Body = Panel.Inset(12.0f * S, 8.0f * S);
	FRegion Side = Body.CutRight(124.0f * S, 10.0f * S);
	const FRegion PowerRow = Side.CutTop(20.0f * S, 4.0f * S);
	const FRegion NameRow = Body.CutTop(22.0f * S, 2.0f * S);
	const FRegion KindRow = Body.CutTop(13.0f * S, 4.0f * S);
	FRegion Count = Body;
	const bool bHeat = Weapon->HasHeat();
	const FRegion HeatRow = bHeat ? Count.CutBottom(12.0f * S, 2.0f * S) : FRegion();
	// the reload along the panel's foot; the heat in its row
	if (Weapon->IsReloading())
	{
		P.Fill(Rectangle(X + 10.0f * S, Y + H - 4.0f * S, (W - 20.0f * S) * Weapon->GetReloadProgress(), 2.5f * S), A(Cyan, 0.9f));
	}
	const FLinearColor Cool(1.0f, 0.5f, 0.1f), Hot(1.0f, 0.93f, 0.8f);
	if (bHeat)
	{
		const float Heat = Weapon->GetHeat();
		const FLinearColor C = FMath::Lerp(Cool, Hot, FMath::Clamp((Heat - ASOWeapon::HeatMedium) / (1.0f - ASOWeapon::HeatMedium), 0.0f, 1.0f));
		Pane.Bar(HeatRow.X, HeatRow.Y + 4.0f * S, 100.0f * S, 4.0f * S, Heat, C, GlassDeep, 0.8f * S);
	}
	P.Flush();
	// the name and the kind, each fitted to its row; the power at the top of the picture's column
	const FString Name = !DebugWeaponName.IsEmpty() ? DebugWeaponName : (Held.Name.IsEmpty() ? (Data ? Data->DisplayName.ToString() : FString(TEXT("-"))) : Held.Name);
	Type.Face = EFace::Medium;
	Type.Fit(Name, NameRow.X, NameRow.Y - 1.0f * S, NameRow.W, Type.Large, 1.0f * S, 0.78f * S, Ink);
	Type.Face = EFace::Auto;
	FString KindText = Data ? Data->ClassName.ToString() : FString();
	if (Data && !Data->DisplayName.IsEmpty())
	{
		KindText += (KindText.IsEmpty() ? TEXT("") : TEXT("  \u00b7  ")) + Data->DisplayName.ToString();
	}
	Type.FitLabel(KindText, KindRow.X, KindRow.Y, KindRow.W, Type.Small, 0.85f * S, 0.66f * S, A(HeldCol, 0.95f), 1.5f * S);
	{
		const float PW = Type.Number(FString::FromInt(Held.Power), PowerRow.Right(), PowerRow.Y - 1.0f * S, Type.Large, 1.0f * S, Gold, 1.0f);
		P.Stroke(Diamond(FVector2D(PowerRow.Right() - PW - 10.0f * S, PowerRow.Y + 10.0f * S), 4.0f * S, 4.0f * S), Gold, 1.2f * S);
		P.Flush();
	}
	// the count: the magazine big in the light face, the reserve smaller after it on the same baseline; both shrink
	// together until they fit the room (a four-figure magazine, a five-figure reserve)
	const int32 MagN = DebugMag >= 0 ? DebugMag : Weapon->GetMag();
	const int32 ReserveN = DebugReserve >= 0 ? DebugReserve : Weapon->GetReserve();
	const FString Mag = FString::FromInt(MagN);
	const FString Res = FString::Printf(TEXT("/ %d"), ReserveN);
	float MagScale = (bHeat ? 1.4f : 1.85f) * S, ResScale = 1.1f * S;
	for (int32 Tries = 0; Tries < 20; ++Tries)
	{
		const float Need = Type.NumberSize(Mag, Type.Large, MagScale).X + 8.0f * S + Type.Size(Res, Type.Medium, ResScale).X;
		if (Need <= Count.W || MagScale <= 0.9f * S)
		{
			break;
		}
		MagScale -= 0.07f * S;
		ResScale = FMath::Max(0.85f * S, ResScale - 0.02f * S);
	}
	const FVector2D MagSz = Type.NumberSize(Mag, Type.Large, MagScale);
	const FVector2D ResSz = Type.Size(Res, Type.Medium, ResScale);
	const float CountY = Count.Y + FMath::Max(0.0f, (Count.H - MagSz.Y) * 0.5f) - 2.0f * S;
	Type.Number(Mag, Count.X, CountY, Type.Large, MagScale, MagN == 0 ? Hurt : Ink);
	Type.Draw(Res, Count.X + MagSz.X + 8.0f * S, CountY + MagSz.Y - ResSz.Y - 3.0f * S, Type.Medium, ResScale, Dim);
	// what else the gun says, in the room left of the count's row or the heat's
	if (bHeat)
	{
		if (Weapon->IsVenting())
		{
			Type.Label(TEXT("Venting"), HeatRow.X + 108.0f * S, HeatRow.Y + 1.0f * S, Type.Small, 0.8f * S, Hot, 1.4f * S);
		}
		else if (Weapon->IsCondensing())
		{
			// rounds condensing from the reserve (the Sarketh's guns never reload): the word pulses with them
			Type.Label(TEXT("Condensing"), HeatRow.X + 108.0f * S, HeatRow.Y + 1.0f * S, Type.Small, 0.8f * S, A(Cool, 0.55f + 0.45f * FMath::Sin(L.Now * 6.0f)), 1.4f * S);
		}
	}
	if (Weapon->GetRampageStacks() > 0)
	{
		const FString Word = FString::Printf(TEXT("Rampage x%d"), Weapon->GetRampageStacks());
		const float Need = Type.LabelWidth(Word, Type.Small, 0.8f * S, 1.2f * S);
		const float Free = Count.Right() - (Count.X + MagSz.X + 8.0f * S + ResSz.X + 8.0f * S);
		if (Need <= Free)
		{
			Type.Label(Word, Count.Right(), CountY + MagSz.Y - 13.0f * S, Type.Small, 0.8f * S, FLinearColor(1.0f, 0.5f, 0.2f), 1.2f * S, 1.0f);
		}
	}
	// the picture, in its own column
	if (UTexture2D* Icon = IconOf(Data ? Data->Archetype : NAME_None))
	{
		const float IW = FMath::Min(Side.W, 116.0f * S), IH = IW * 0.5f;
		Picture(Icon, Side.X + (Side.W - IW) * 0.5f, Side.Y + (Side.H - IH) * 0.5f, IW, IH, 0.95f, TEXT("held gun"));
	}

	// under the panel: the grenade's charges, the melee style, the flashlight, in a row of their own
	{
		const float RY = Y + H + 10.0f * S;
		float RX = X + 4.0f * S;
		int32 Charges = 0, MaxCharges = 0;
		float Left = 0.0f, Cooldown = 0.0f;
		if (Player->GetAbilityState(ESOAbilitySlot::Grenade, Charges, MaxCharges, Left, Cooldown))
		{
			SlotGlyph(P, ESOAbilitySlot::Grenade, FVector2D(RX + 10.0f * S, RY + 10.0f * S), 8.0f * S, Charges > 0 ? Ink : Dim, 1.5f * S);
			P.Flush();
			Type.Number(FString::FromInt(Charges), RX + 26.0f * S, RY + 2.0f * S, Type.Medium, 1.2f * S, Charges > 0 ? Ink : Dim);
			RX += 60.0f * S;
		}
		const FSOMeleeStyle* Style = Player->GetMeleeStyle();
		UTexture2D* StyleIcon = Style && !Style->Icon.IsNull() ? Style->Icon.LoadSynchronous() : nullptr;
		if (StyleIcon)
		{
			Picture(StyleIcon, RX, RY - 1.0f * S, 44.0f * S, 22.0f * S, Player->IsFists() ? 1.0f : 0.7f, TEXT("melee"));
			RX += 50.0f * S;
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
		Type.Number(TEXT("4"), RX, RY + 2.0f * S, Type.Medium, 1.2f * S, Player->IsFists() ? Ink : Dim);
		// the flashlight's key, lit when it is on
		const float FX = X + W - 24.0f * S;
		const bool bOn = Player->IsFlashlightOn();
		{
			FGlassStyle K;
			K.FillA = bOn ? A(Gold, 0.3f) : A(Glass, 0.9f);
			K.FillB = bOn ? A(Gold, 0.15f) : A(GlassDeep, 0.9f);
			K.Edge = bOn ? Gold : A(Line, 0.6f);
			K.Glow = Gold;
			K.GlowA = bOn ? 0.4f : 0.0f;
			K.GlowW = 6.0f * S;
			K.ShadowA = 0.2f;
			K.ShadowOff = 2.0f * S;
			K.ShadowBlur = 3.0f * S;
			Pane.Plate4(FX, RY, 22.0f * S, 20.0f * S, 3.0f * S, K);
		}
		Type.Label(TEXT("F"), FX + 11.0f * S, RY + 3.0f * S, Type.Small, 1.05f * S, bOn ? Gold : Dim, 0.0f, 0.5f);
	}

	// the word at the crosshair when the gun is empty
	if (!Weapon->IsReloading() && Weapon->GetMag() == 0 && Weapon->GetReserve() > 0 && !Weapon->IsCondensing() && !Weapon->IsVenting())
	{
		const float RW = Type.CapsWidth(TEXT("Reload"), Type.Medium, 1.0f * S, 2.0f * S);
		Reserve(L.CX - RW * 0.5f - 6.0f * S, L.H * 0.5f + 30.0f * S, RW + 12.0f * S, 24.0f * S);
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
	FType Type(Canvas, AuditPtr());
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
	FType Type(Canvas, AuditPtr());
	const float Life = 1.1f;
	const float RiseMax = 46.0f * S;
	// every number rises the same way (quick out of the hit, slowing as it fades) with a small sideways set of its
	// own, so the places they are given hold: each is laid, the first time it is drawn, where the WHOLE of its rise is
	// clear of the others' and of the screen a fixed element or a creature's plate holds (the owner's brief: numbers
	// never on numbers, never on anything), and keeps that lane
	TArray<FRegion> Placed;
	for (int32 i = 0; i < DamageNumbers.Num(); ++i)
	{
		FDamageNumber& N = DamageNumbers[i];
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
		const float Alpha = FMath::Clamp((1.0f - T) / 0.4f, 0.0f, 1.0f) * FMath::Min(1.0f, Age / 0.05f);
		const float Rise = (1.0f - FMath::Pow(1.0f - T, 2.2f)) * RiseMax;
		const float Pop = 1.0f + 0.35f * FMath::Clamp(1.0f - Age / 0.1f, 0.0f, 1.0f);
		FLinearColor Col;
		float Scale;
		switch (N.Kind)
		{
		case 1: Col = FLinearColor(0.45f, 0.80f, 1.0f); Scale = 1.5f; break;             // on a shield: cyan-blue
		case 2: Col = FLinearColor(1.0f, 0.92f, 0.50f); Scale = 1.85f; break;            // precise: pale gold
		case 3: Col = FLinearColor(1.0f, 0.74f, 0.22f); Scale = 2.4f; break;             // critical: gold
		default: Col = Ink; Scale = 1.5f; break;                                           // plain: white
		}
		if (N.bKilled)
		{
			Scale *= 1.15f;
		}
		const FString Text = FString::FromInt(FMath::RoundToInt(N.Amount));
		const FVector2D Sz = Type.Size(Text, Type.Large, Scale * S * 1.35f);   // (its box at the pop's biggest)
		const float CritH = N.Kind == 3 ? 14.0f * S : 0.0f;
		const float HomeX = Screen.X + 14.0f * S + N.Drift * 8.0f * S, HomeY = Screen.Y - 30.0f * S;
		if (!N.bLaned)
		{
			// the box its whole rise sweeps, from where it is born to where it fades; if that lies on anything, the
			// nearest clear spot is taken from a fixed order (beside it first, then above, below, then diagonally,
			// further out each time): one answer, never a spot between two obstacles
			const FRegion Home(HomeX, HomeY - RiseMax - CritH, Sz.X, Sz.Y + RiseMax + CritH);
			TArray<FRegion> Taken = Placed;
			for (const TArray<FBox2D>* List : { &Reserved, &ReservedLast })
			{
				for (const FBox2D& B : *List)
				{
					Taken.Add(FRegion(B.Min.X, B.Min.Y, B.Max.X - B.Min.X, B.Max.Y - B.Min.Y));
				}
			}
			auto Clear = [&](const FRegion& R)
			{
				for (const FRegion& O : Taken)
				{
					if (R.Overlaps(O, 1.0f))
					{
						return false;
					}
				}
				return true;
			};
			FRegion Me = Home;
			if (!Clear(Me))
			{
				const float StepX = Sz.X + 8.0f * S, StepY = Sz.Y + 6.0f * S;
				bool bFound = false;
				for (int32 k = 1; k <= 7 && !bFound; ++k)
				{
					const FVector2D Offsets[] = { FVector2D(k * StepX, 0.0f), FVector2D(-k * StepX, 0.0f), FVector2D(0.0f, -k * StepY), FVector2D(0.0f, k * StepY),
						FVector2D(k * StepX, -k * StepY * 0.5f), FVector2D(-k * StepX, -k * StepY * 0.5f), FVector2D(k * StepX, k * StepY * 0.5f), FVector2D(-k * StepX, k * StepY * 0.5f) };
					for (const FVector2D& O : Offsets)
					{
						const FRegion Try(Home.X + O.X, Home.Y + O.Y, Home.W, Home.H);
						if (Try.X >= 0.0f && Try.Right() <= L.W && Try.Y >= 0.0f && Try.Bottom() <= L.H && Clear(Try))
						{
							Me = Try;
							bFound = true;
							break;
						}
					}
				}
			}
			N.Side = Me.X - Home.X;
			N.Lift = Home.Y - Me.Y;
			N.bLaned = true;
		}
		const float X = HomeX + N.Side, Y = HomeY - Rise - N.Lift;
		Placed.Add(FRegion(HomeX + N.Side, HomeY - N.Lift - RiseMax - CritH, Sz.X, Sz.Y + RiseMax + CritH));
		Type.Draw(Text, X, Y, Type.Large, Scale * S * Pop, A(Col, Alpha));
		if (N.Kind == 3)
		{
			Type.Caps(TEXT("Crit"), X + 2.0f * S, Y - 13.0f * S, Type.Small, 1.0f * S, A(Col, Alpha), 2.0f * S);
		}
	}
}

// ---------------------------------------------------------------------------------------------------------------------
// The loop's beats (the owner, 2026-11-20): what a kill paid, the level reached, an elite seen

void ASOHUD::DrawRewards(const FLayout& L)
{
	const float S = L.S;
	FType Type(Canvas, AuditPtr());
	const float Life = 1.6f;
	// each kind has a place of its own under the eye's line (the owner's brief: xp and credits appear independently,
	// never on a damage number, which rises above the line): xp to the right of the crosshair rising and drifting
	// right, credits to the left drifting left, alloy under the credits
	const float Y0 = L.H * 0.5f + 48.0f * S;
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
		const float Rise = (1.0f - FMath::Pow(1.0f - T, 2.5f)) * 36.0f * S;
		const float Pop = 1.0f + 0.3f * FMath::Clamp(1.0f - (L.Now - R.Bump) / 0.12f, 0.0f, 1.0f);
		FLinearColor Col;
		FString Word;
		float Side = 1.0f;
		switch (R.Kind)
		{
		case 1: Col = Cyan; Word = TEXT("credits"); Side = -1.0f; break;
		case 2: Col = Dim; Word = TEXT("alloy"); Side = -1.0f; break;
		default: Col = Gold; Word = TEXT("xp"); break;
		}
		const FString Number = FString::Printf(TEXT("+%d"), R.Amount);
		const float LaneH = Type.Size(TEXT("0"), Type.Large, 1.45f * S).Y + 4.0f * S;
		const float Y = Y0 + R.Lane * LaneH - Rise;
		const FVector2D NS = Type.Size(Number, Type.Large, 1.45f * S * Pop);
		const float WordW = Type.CapsWidth(Word, Type.Small, 0.95f * S, 1.8f * S);
		const float WordH = Type.Size(TEXT("X"), Type.Small, 0.95f * S).Y;
		const float Total = NS.X + 7.0f * S + WordW;
		const float X = Side > 0.0f ? L.CX + 64.0f * S + 10.0f * S * T : L.CX - 64.0f * S - Total - 10.0f * S * T;
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
	FType Type(Canvas, AuditPtr());
	const FGlass Pane = MakeGlass(P, S);
	const float In = FMath::Clamp(Age / 0.3f, 0.0f, 1.0f);
	const float Ease = 1.0f - FMath::Pow(1.0f - In, 3.0f);
	const float Out = FMath::Clamp((3.0f - Age) / 0.5f, 0.0f, 1.0f);
	const float Y = L.H * 0.34f;   // (under the elite's plate, over the crosshair: both may show at once)
	// a line of gold opening out from the middle, a soft light over it, the level above and what it allows under
	const float Half = 170.0f * S * Ease;
	const USOProgressionTable& Rules = USOProgressionTable::Get();
	const FString LevelText = FString::Printf(TEXT("Level %d"), LevelUpTo);
	const FString GearText = FString::Printf(TEXT("Gear can be raised to %d"), Rules.PowerCap(LevelUpTo));
	const float WordsW = FMath::Max(Type.LabelWidth(LevelText, Type.Large, 1.6f * S, 6.5f * S), Type.CapsWidth(GearText, Type.Small, 1.0f * S, 2.4f * S));
	const float HalfPlate = FMath::Max(Half, WordsW * 0.5f + 4.0f * S);
	{
		FGlassStyle St;
		St.Alpha = 0.8f * Out * Ease;
		St.Glow = Gold;
		St.GlowA = 0.3f;
		St.GlowW = 26.0f * S;
		St.Edge = A(Gold, 0.5f);
		St.ShadowOff = 8.0f * S;
		St.ShadowBlur = 12.0f * S;
		Pane.Plate4(L.CX - HalfPlate - 24.0f * S, Y - 54.0f * S, 2.0f * HalfPlate + 48.0f * S, 82.0f * S, 10.0f * S, St);
		Reserve(L.CX - HalfPlate - 24.0f * S, Y - 54.0f * S, 2.0f * HalfPlate + 48.0f * S, 82.0f * S);
	}
	P.Quad(FVector2D(L.CX - Half, Y - 1.0f * S), FVector2D(L.CX - Half, Y + 1.0f * S), FVector2D(L.CX, Y - 1.0f * S), FVector2D(L.CX, Y + 1.0f * S), A(Gold, 0.0f), A(Gold, 0.9f * Out));
	P.Quad(FVector2D(L.CX, Y - 1.0f * S), FVector2D(L.CX, Y + 1.0f * S), FVector2D(L.CX + Half, Y - 1.0f * S), FVector2D(L.CX + Half, Y + 1.0f * S), A(Gold, 0.9f * Out), A(Gold, 0.0f));
	P.Quad(FVector2D(L.CX - Half, Y - 48.0f * S), FVector2D(L.CX + Half, Y - 48.0f * S), FVector2D(L.CX - Half, Y), FVector2D(L.CX + Half, Y), A(Gold, 0.0f), A(Gold, 0.10f * Out * Ease));
	P.Flush();
	Type.Label(LevelText, L.CX, Y - 46.0f * S, Type.Large, 1.6f * S, A(Gold, Out * In), 6.5f * S, 0.5f);
	Type.Caps(GearText, L.CX, Y + 10.0f * S, Type.Small, 1.0f * S, A(Ink, 0.8f * Out * FMath::Clamp((Age - 0.25f) / 0.3f, 0.0f, 1.0f)), 2.4f * S, 0.5f);
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
	FType Type(Canvas, AuditPtr());
	const FGlass Pane = MakeGlass(P, S);
	const float In = 1.0f - FMath::Pow(1.0f - FMath::Clamp(Age / 0.25f, 0.0f, 1.0f), 3.0f);
	const float Out = FMath::Clamp((3.2f - Age) / 0.4f, 0.0f, 1.0f);
	const float Alpha = In * Out;
	const float Y = L.H * 0.20f - (1.0f - In) * 12.0f * S;
	const float W = FMath::Max(Type.LabelWidth(EliteName, Type.Medium, 1.2f * S, 3.2f * S) + 64.0f * S, 240.0f * S);
	{
		FGlassStyle St;
		St.Alpha = Alpha;
		St.Edge = A(Lock, 0.7f);
		St.EdgeT = 1.2f * S;
		St.Glow = Lock;
		St.GlowA = 0.4f;
		St.GlowW = 18.0f * S;
		Pane.Plate(L.CX - W * 0.5f, Y, W, 44.0f * S, 8.0f * S, St);
		Reserve(L.CX - W * 0.5f, Y, W, 44.0f * S);
	}
	// a red mark either side: the thing to fear
	P.Fill(Diamond(FVector2D(L.CX - W * 0.5f + 16.0f * S, Y + 22.0f * S), 4.0f * S, 7.0f * S), A(Lock, Alpha));
	P.Fill(Diamond(FVector2D(L.CX + W * 0.5f - 16.0f * S, Y + 22.0f * S), 4.0f * S, 7.0f * S), A(Lock, Alpha));
	P.Flush();
	Type.Label(FString::Printf(TEXT("Elite  ·  %d"), EliteLevel), L.CX, Y + 5.0f * S, Type.Small, 0.95f * S, A(Lock, Alpha), 2.8f * S, 0.5f);
	Type.Label(EliteName, L.CX, Y + 20.0f * S, Type.Medium, 1.2f * S, A(Ink, Alpha), 3.2f * S, 0.5f);
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
	FType Type(Canvas, AuditPtr());
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
				const float LabelY = Screen.Y - Height - 14.0f * S;
				bool bInBand = FMath::Abs(Screen.X - L.CX) < 240.0f * S && LabelY > L.H * 0.5f - 150.0f * S && LabelY < L.H * 0.5f + 130.0f * S;
				{
					const float LW = Type.CapsWidth(Rar->Name.ToString(), Type.Small, 0.9f * S, 1.6f * S) + 8.0f * S;
					const FBox2D LabelBox(FVector2D(Screen.X - LW * 0.5f, LabelY - 2.0f * S), FVector2D(Screen.X + LW * 0.5f, LabelY + 16.0f * S));
					for (const TArray<FBox2D>* List : { &Reserved, &ReservedLast })
					{
						for (const FBox2D& B : *List)
						{
							bInBand |= B.Intersect(LabelBox);
						}
					}
				}
				if (!bInBand)
				{
					Type.Caps(Rar->Name.ToString(), Screen.X, LabelY, Type.Small, 0.9f * S, A(Col, FMath::Clamp((1500.0f - Dist) / 400.0f, 0.0f, 1.0f)), 1.6f * S, 0.5f);
				}
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
	// a blast near the player: a pulse of fire at the edge, by how near it was
	const float BlastAge = L.Now - Player->GetLastBlastTime();
	if (BlastAge >= 0.0f && BlastAge < 0.45f)
	{
		Bands(240.0f * S, A(FLinearColor(1.0f, 0.62f, 0.3f), 0.55f * Player->GetLastBlastStrength() * (1.0f - BlastAge / 0.45f)));
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
	FType Type(Canvas, AuditPtr());
	const FGlass Pane = MakeGlass(P, S);
	const bool bCan = Thing->CanInteract(Player);
	const FString Prompt = Thing->GetInteractPrompt(Player).ToString();
	const FVector2D Sz = Type.Size(Prompt, Type.Medium, 1.15f * S);
	const float W = Sz.X + 70.0f * S, H = Sz.Y + 16.0f * S, X = L.CX - W * 0.5f, Y = L.H * 0.64f;
	{
		FGlassStyle St;
		St.Alpha = 0.95f;
		St.Glow = Cyan;
		St.GlowA = bCan ? 0.22f : 0.0f;
		St.GlowW = 14.0f * S;
		Pane.Plate4(X, Y, W, H, 6.0f * S, St);
		Reserve(X, Y, W, H);
		FGlassStyle K;
		K.FillA = bCan ? A(Cyan, 0.3f) : A(Glass, 0.6f);
		K.FillB = bCan ? A(Cyan, 0.14f) : A(GlassDeep, 0.6f);
		K.Edge = bCan ? Cyan : A(Line, 0.6f);
		K.ShadowA = 0.15f;
		K.ShadowOff = 2.0f * S;
		K.ShadowBlur = 3.0f * S;
		Pane.Plate4(X + 12.0f * S, Y + 6.0f * S, 24.0f * S, H - 12.0f * S, 3.0f * S, K);
	}
	Type.Label(TEXT("E"), X + 24.0f * S, Y + 8.0f * S, Type.Medium, 1.05f * S, bCan ? Ink : Dim, 0.0f, 0.5f);
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
	FType Type(Canvas, AuditPtr());
	const FGlass Pane = MakeGlass(P, S);
	const float Left = FMath::Max(0.0f, RespawnDelay - (L.Now - Player->GetDeathTime()));
	const float W = 520.0f * S, H = 110.0f * S, X = L.CX - W * 0.5f, Y = L.H * 0.38f;
	{
		FGlassStyle St;
		St.Alpha = 0.95f;
		St.Edge = A(Hurt, 0.7f);
		St.Glow = Hurt;
		St.GlowA = 0.3f;
		St.GlowW = 30.0f * S;
		St.ShadowOff = 8.0f * S;
		St.ShadowBlur = 12.0f * S;
		Pane.Plate4(X, Y, W, H, 12.0f * S, St);
	}
	P.Segment(FVector2D(X + 40.0f * S, Y + 62.0f * S), FVector2D(X + W - 40.0f * S, Y + 62.0f * S), A(Hurt, 0.6f), 1.0f * S);
	P.Flush();
	Type.Label(TEXT("You are down"), L.CX, Y + 18.0f * S, Type.Large, 1.5f * S, Hurt, 5.5f * S, 0.5f);
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
	FType Type(Canvas, AuditPtr());
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
	FType Type(Canvas, AuditPtr());
	const FGlass Pane = MakeGlass(P, S);
	const float BW = 640.0f * S, BX = L.CX - BW * 0.5f, BY = 150.0f * S;
	{
		FGlassStyle St;
		St.Alpha = 0.9f;
		St.Edge = A(Lock, 0.5f);
		St.Glow = Lock;
		St.GlowA = 0.25f;
		St.GlowW = 26.0f * S;
		Pane.Plate4(BX - 14.0f * S, BY - 30.0f * S, BW + 28.0f * S, 66.0f * S, 8.0f * S, St);
		Reserve(BX - 14.0f * S, BY - 30.0f * S, BW + 28.0f * S, 66.0f * S);
	}
	Pane.Bar(BX, BY, BW, 10.0f * S, Boss->GetHealth() / FMath::Max(Boss->GetMaxHealth(), 1.0f), HealthRed, GlassDeep, 1.0f * S);
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
	Type.Label(Boss->DisplayName.ToString(), L.CX, BY - 24.0f * S, Type.Medium, 1.15f * S, Ink, 3.4f * S, 0.5f);
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
	GlassUsed = 0;
	ReservedLast = MoveTemp(Reserved);
	Reserved.Reset();
	if (!bGlassLooked)
	{
		bGlassLooked = true;
		GlassBase = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/UI/M_HUDGlass.M_HUDGlass"));
		if (!GlassBase)
		{
			UE_LOG(LogTemp, Warning, TEXT("SOHUD: /Game/UI/M_HUDGlass is not imported (SO_IMPORT_ONLY=ui): the HUD draws its old flat panels"));
		}
	}
#if !UE_BUILD_SHIPPING
	if (!bAuditLooked)
	{
		bAuditLooked = true;
		if (FParse::Param(FCommandLine::Get(), TEXT("SOHudAudit")))
		{
			SOHudAudit(1);
		}
	}
#endif
	if (FHudAudit* Au = AuditPtr())
	{
		Au->Rects.Reset();
		Au->Element.Reset();
	}
	auto Tag = [this](const TCHAR* Name) { if (FHudAudit* Au = AuditPtr()) { Au->Element = Name; } };

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
	Tag(TEXT("edge"));
	DrawScreenEdge(L);
	if (!bScope)
	{
		DrawElement(L, MinimapLayout, TEXT("minimap"), [this](const FLayout& LE) { DrawMinimap(LE); });
		DrawElement(L, CompassLayout, TEXT("compass"), [this](const FLayout& LE) { DrawCompass(LE); });
		DrawElement(L, ObjectiveLayout, TEXT("objective"), [this](const FLayout& LE) { DrawObjective(LE); });
		DrawElement(L, ConditionsLayout, TEXT("conditions"), [this](const FLayout& LE) { DrawConditions(LE); });
		DrawElement(L, TrackedLayout, TEXT("tracked"), [this](const FLayout& LE) { DrawTracked(LE); });
		DrawElement(L, ItemsLayout, TEXT("items"), [this](const FLayout& LE) { DrawItemCards(LE); });
		Tag(TEXT("beams"));
		DrawLootBeams(L);
		Tag(TEXT("creatures"));
		DrawCreatures(L);
		Tag(TEXT("elite"));
		DrawEliteIntro(L);
	}
	Tag(TEXT("operation"));
	DrawOperation(L);
	DrawAIDebug(L.W, L.H, L.S);
	if (Player->IsDead())
	{
		Tag(TEXT("downed"));
		DrawDowned(L);
		return;
	}
	Tag(TEXT("damage"));
	DrawDamageNumbers(L);
	Tag(TEXT("rewards"));
	DrawRewards(L);
	Tag(TEXT("levelup"));
	DrawLevelUp(L);
	Tag(TEXT("crosshair"));
	DrawCrosshair(L);
	Tag(TEXT("melee"));
	DrawMelee(L);
	DrawElement(L, InteractLayout, TEXT("interact"), [this](const FLayout& LE) { DrawInteract(LE); });
	DrawElement(L, VitalsLayout, TEXT("vitals"), [this](const FLayout& LE) { DrawVitals(LE); });
	DrawElement(L, AbilitiesLayout, TEXT("abilities"), [this](const FLayout& LE) { DrawAbilities(LE); });
	DrawElement(L, WeaponLayout, TEXT("weapon"), [this](const FLayout& LE) { DrawWeapon(LE); });

	// the audit: every overlap this frame, logged when the set of them changes (and again every two seconds)
	if (FHudAudit* Au = AuditPtr())
	{
		const TArray<FString> Lines = Au->Check();
		if (Lines != AuditLast || L.Now - AuditLoggedAt > 2.0f)
		{
			AuditLast = Lines;
			AuditLoggedAt = L.Now;
			UE_LOG(LogTemp, Display, TEXT("HUDAUDIT %dx%d: %d overlaps, %d rects"), FMath::RoundToInt(L.W), FMath::RoundToInt(L.H), Lines.Num(), Au->Rects.Num());
			for (const FString& Row : Lines)
			{
				UE_LOG(LogTemp, Display, TEXT("HUDOVERLAP %s"), *Row);
			}
		}
	}
}
