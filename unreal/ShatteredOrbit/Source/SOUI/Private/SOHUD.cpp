#include "SOHUD.h"

#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/Font.h"
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
#include "SOCombatCharacter.h"
#include "SOProjectileSubsystem.h"
#include "SOSound.h"
#include "SOWeapon.h"
#include "SOWeaponData.h"

namespace
{
	const FLinearColor Ink(0.92f, 0.95f, 1.0f, 0.9f);
	const FLinearColor Shield(0.25f, 0.8f, 1.0f, 0.95f);
	const FLinearColor Health(0.95f, 0.95f, 0.95f, 0.95f);
	const FLinearColor Hurt(1.0f, 0.35f, 0.25f, 0.95f);
	const FLinearColor Back(0.0f, 0.0f, 0.0f, 0.45f);
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
		}
		FeedInventory = Inventory;
		FeedHandle = Inventory->OnFeed.AddUObject(this, &ASOHUD::OnFeed);
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

void ASOHUD::DrawMinimap(float S)
{
	const ASOMapInfo* Info = ASOMapInfo::Get(this);
	const APawn* Pawn = GetOwningPawn();
	UTextureRenderTarget2D* Map = Info ? Info->GetMapTexture() : nullptr;
	if (!Info || !Pawn || !Map || !Map->GetResource())
	{
		return;
	}
	// a 300 m window round the player, north up
	const float Side = 230.0f * S;
	const FVector2D Origin(28.0f * S, 28.0f * S);
	// share of the map shown (never more than the whole map; the window stops at the map's edges, no wrapping)
	const float Window = FMath::Min(1.0f, 30000.0f / FMath::Max(Info->HalfSize * 2.0f, 1.0f));
	const FVector2D Me = Info->WorldToMap(Pawn->GetActorLocation());
	FVector2D UV0 = Me - FVector2D(Window * 0.5f);
	UV0.X = FMath::Clamp(UV0.X, 0.0f, 1.0f - Window);
	UV0.Y = FMath::Clamp(UV0.Y, 0.0f, 1.0f - Window);
	const FVector2D UV1 = UV0 + FVector2D(Window);
	DrawRect(FLinearColor(0.01f, 0.015f, 0.03f, 0.85f), Origin.X - 3 * S, Origin.Y - 3 * S, Side + 6 * S, Side + 6 * S);
	FCanvasTileItem Tile(Origin, Map->GetResource(), FVector2D(Side, Side), UV0, UV1, FLinearColor(0.8f, 0.85f, 0.95f, 0.95f));
	Tile.BlendMode = SE_BLEND_Opaque;
	Canvas->DrawItem(Tile);
	// frame: thin cyan edges with brighter corners
	const FLinearColor Edge(0.1f, 0.85f, 1.0f, 0.55f);
	DrawRect(Edge, Origin.X - 3 * S, Origin.Y - 3 * S, Side + 6 * S, 1.5f * S);
	DrawRect(Edge, Origin.X - 3 * S, Origin.Y + Side + 1.5f * S, Side + 6 * S, 1.5f * S);
	DrawRect(Edge, Origin.X - 3 * S, Origin.Y - 3 * S, 1.5f * S, Side + 6 * S);
	DrawRect(Edge, Origin.X + Side + 1.5f * S, Origin.Y - 3 * S, 1.5f * S, Side + 6 * S);
	UFont* Small = GEngine ? GEngine->GetSmallFont() : nullptr;
	DrawText(TEXT("N"), FLinearColor(0.1f, 0.85f, 1.0f), Origin.X + Side * 0.5f - 4 * S, Origin.Y + 2 * S, Small, 1.0f * S);
	// the important places in view (fast travel and gates labelled)
	for (TActorIterator<ASOMapPoint> It(GetWorld()); It; ++It)
	{
		const FVector2D UV = Info->WorldToMap(It->GetActorLocation());
		const FVector2D T = (UV - UV0) / Window;
		if (T.X < 0.03f || T.X > 0.97f || T.Y < 0.06f || T.Y > 0.97f)
		{
			continue;
		}
		const FVector2D P = Origin + T * Side;
		const FLinearColor C = ASOMapPoint::KindColor(It->Kind);
		DrawRect(FLinearColor(0, 0, 0, 0.6f), P.X - 5 * S, P.Y - 5 * S, 10 * S, 10 * S);
		DrawRect(C, P.X - 3.5f * S, P.Y - 3.5f * S, 7 * S, 7 * S);
		if (It->bFastTravel || It->Kind == ESOMapPointKind::AreaTravel)
		{
			DrawText(It->Label.ToString(), FLinearColor(0.88f, 0.92f, 0.97f, 0.9f), P.X + 7 * S, P.Y - 7 * S, Small, 0.85f * S);
		}
	}
	// you: an arrow pointing where you look
	const FVector2D C = Origin + ((Me - UV0) / Window).ClampAxes(0.0f, 1.0f) * Side;
	const float Yaw = FMath::DegreesToRadians(Pawn->GetControlRotation().Yaw);
	// map space: up = world +X, right = world +Y
	const FVector2D Fwd(FMath::Sin(Yaw), -FMath::Cos(Yaw));
	const FVector2D Rt(-Fwd.Y, Fwd.X);
	FCanvasTriangleItem Arrow(C + Fwd * 9.0f * S, C - Fwd * 6.0f * S + Rt * 6.0f * S, C - Fwd * 6.0f * S - Rt * 6.0f * S, GWhiteTexture);
	Arrow.SetColor(FLinearColor(0.1f, 0.85f, 1.0f));
	Canvas->DrawItem(Arrow);
	DrawText(Info->AreaName.ToString().ToUpper(), FLinearColor(0.88f, 0.92f, 0.97f, 0.9f), Origin.X, Origin.Y + Side + 8 * S, Small, 1.0f * S);
}

void ASOHUD::DrawOperation(float W, float H, float S)
{
	const ASOOperation* Op = ASOOperation::Get(this);
	const APawn* Pawn = GetOwningPawn();
	if (!Op || !Pawn)
	{
		return;
	}
	UFont* Small = GEngine ? GEngine->GetSmallFont() : nullptr;
	UFont* Font = GEngine ? GEngine->GetMediumFont() : nullptr;
	UFont* Big = GEngine ? GEngine->GetLargeFont() : nullptr;
	const FLinearColor Void(0.66f, 0.42f, 1.0f, 0.95f);
	const FLinearColor Dim(0.78f, 0.82f, 0.9f, 0.85f);
	const FSOStage* Stage = Op->GetStage();
	const float Age = Op->GetStageAge();
	auto Centred = [&](const FString& Text, float Y, UFont* F, float Scale, FLinearColor C)
	{
		float TW = 0.0f, TH = 0.0f;
		GetTextSize(Text, TW, TH, F, Scale);
		DrawText(Text, C, W * 0.5f - TW * 0.5f, Y, F, Scale);
		return TW;
	};

	// text broken into lines no wider than MaxW, centred, from Y down; returns the Y under the last line
	auto Wrapped = [&](const FString& Text, float Y, float MaxW, UFont* F, float Scale, FLinearColor C)
	{
		TArray<FString> Words;
		Text.ParseIntoArray(Words, TEXT(" "));
		FString Line;
		float TW = 0.0f, TH = 0.0f;
		for (int32 i = 0; i <= Words.Num(); ++i)
		{
			const FString Try = i < Words.Num() ? (Line.IsEmpty() ? Words[i] : Line + TEXT(" ") + Words[i]) : FString();
			if (i < Words.Num())
			{
				GetTextSize(Try, TW, TH, F, Scale);
			}
			if (i == Words.Num() || (TW > MaxW && !Line.IsEmpty()))
			{
				Centred(Line, Y, F, Scale, C);
				GetTextSize(Line, TW, TH, F, Scale);
				Y += TH + 3.0f * S;
				Line = i < Words.Num() ? Words[i] : FString();
			}
			else
			{
				Line = Try;
			}
		}
		return Y;
	};

	// the end screen: what every player earned
	if (Op->GetState() == ESOOperationState::Complete)
	{
		const float A = FMath::Clamp(Age * 1.5f, 0.0f, 1.0f) * FMath::Clamp(14.0f - Age, 0.0f, 1.0f);
		if (A > 0.0f)
		{
			DrawRect(FLinearColor(0.02f, 0.0f, 0.05f, 0.55f * A), 0.0f, H * 0.24f, W, 230.0f * S);
			DrawRect(FLinearColor(Void.R, Void.G, Void.B, 0.8f * A), 0.0f, H * 0.24f, W, 2.0f * S);
			DrawRect(FLinearColor(Void.R, Void.G, Void.B, 0.8f * A), 0.0f, H * 0.24f + 228.0f * S, W, 2.0f * S);
			Centred(Op->OperationName.ToString().ToUpper(), H * 0.24f + 22.0f * S, Font, 1.1f * S, FLinearColor(Void.R, Void.G, Void.B, A));
			Centred(TEXT("OPERATION COMPLETE"), H * 0.24f + 52.0f * S, Big, 2.0f * S, FLinearColor(1, 1, 1, A));
			if (!Op->Outcome.IsEmpty())
			{
				Wrapped(Op->Outcome.ToString(), H * 0.24f + 240.0f * S, W * 0.6f, Font, 1.0f * S, FLinearColor(Dim.R, Dim.G, Dim.B, A));
			}
			float Y = H * 0.24f + 130.0f * S;
			const APlayerState* Mine = GetOwningPlayerController() ? GetOwningPlayerController()->PlayerState : nullptr;
			for (const FSOOperationReward& R : Op->GetRewards())
			{
				const USOLootTables* Tables = USOLootLibrary::GetTables();
				FLinearColor C = Tables ? Tables->GetRarity(R.Rarity).Color : Void;
				C.A = A;
				const FString Who = R.Player == Mine ? TEXT("You earned") : (R.Player ? R.Player->GetPlayerName() : FString(TEXT("?")));
				Centred(FString::Printf(TEXT("%s   %s"), *Who, *R.Label), Y, Font, (R.Player == Mine ? 1.35f : 1.0f) * S, C);
				Y += (R.Player == Mine ? 34.0f : 26.0f) * S;
			}
		}
		return;
	}
	if (!Stage || Op->GetState() != ESOOperationState::Active)
	{
		return;
	}

	// the objective, under the mini-map
	const float X = 28.0f * S, Y0 = 300.0f * S;
	DrawRect(FLinearColor(0.0f, 0.0f, 0.0f, 0.35f), X - 6.0f * S, Y0 - 6.0f * S, 330.0f * S, 72.0f * S);
	DrawRect(Void, X - 6.0f * S, Y0 - 6.0f * S, 2.5f * S, 72.0f * S);
	DrawText(Op->OperationName.ToString().ToUpper(), Void, X + 4.0f * S, Y0, Small, 0.95f * S);
	DrawText(Stage->Title.ToString(), FLinearColor(1, 1, 1, 0.95f), X + 4.0f * S, Y0 + 16.0f * S, Font, 1.0f * S);
	DrawText(Op->GetObjectiveLine(), Dim, X + 4.0f * S, Y0 + 40.0f * S, Font, 0.85f * S);

	// the stage's title as it begins
	if (Age < 5.0f)
	{
		const float A = FMath::Clamp(Age * 2.0f, 0.0f, 1.0f) * FMath::Clamp(5.0f - Age, 0.0f, 1.0f);
		const float TW = Centred(Stage->Title.ToString().ToUpper(), H * 0.16f, Big, 1.7f * S, FLinearColor(1, 1, 1, A));
		DrawRect(FLinearColor(Void.R, Void.G, Void.B, A * 0.9f), W * 0.5f - TW * 0.35f, H * 0.16f + 50.0f * S, TW * 0.7f, 2.0f * S);
		Centred(Stage->Objective.ToString(), H * 0.16f + 60.0f * S, Font, 1.1f * S, FLinearColor(Dim.R, Dim.G, Dim.B, A));
	}

	// why anyone goes: as the operation begins, a line at a time over the lower third (then the first stage's radio line)
	const bool bOpening = Op->GetStageIndex() == 0 && Op->Briefing.Num() > 0;
	const float Per = 5.5f, BriefEnd = bOpening ? Per * Op->Briefing.Num() : 0.0f;
	if (bOpening && Age < BriefEnd)
	{
		const int32 Line = FMath::Min(Op->Briefing.Num() - 1, FMath::FloorToInt(Age / Per));
		const float T = Age - Line * Per;
		const float A = FMath::Clamp(T * 2.0f, 0.0f, 1.0f) * FMath::Clamp((Per - T) * 2.0f, 0.0f, 1.0f);
		DrawRect(FLinearColor(0.0f, 0.0f, 0.0f, 0.55f * A), 0.0f, H * 0.70f, W, 112.0f * S);
		Centred(Op->OperationName.ToString().ToUpper(), H * 0.70f + 10.0f * S, Small, 1.3f * S, FLinearColor(Void.R, Void.G, Void.B, A));
		Wrapped(Op->Briefing[Line].ToString(), H * 0.70f + 34.0f * S, W * 0.7f, Font, 1.7f * S, FLinearColor(1, 1, 1, A));
	}
	// the radio as a stage begins: who, and what this place means
	const float RadioAge = Age - BriefEnd - 1.0f, RadioTime = 11.0f;
	if (!Stage->Intel.IsEmpty() && RadioAge > 0.0f && RadioAge < RadioTime)
	{
		const float A = FMath::Clamp(RadioAge * 2.0f, 0.0f, 1.0f) * FMath::Clamp(RadioTime - RadioAge, 0.0f, 1.0f);
		const float Y = H * 0.76f;
		DrawRect(FLinearColor(0.0f, 0.0f, 0.0f, 0.5f * A), W * 0.17f, Y - 8.0f * S, W * 0.66f, 96.0f * S);
		DrawRect(FLinearColor(Void.R, Void.G, Void.B, 0.9f * A), W * 0.17f, Y - 8.0f * S, 2.5f * S, 96.0f * S);
		Centred(Stage->IntelWho.ToString(), Y - 2.0f * S, Small, 1.3f * S, FLinearColor(Void.R, Void.G, Void.B, A));
		Wrapped(Stage->Intel.ToString(), Y + 20.0f * S, W * 0.62f, Font, 1.4f * S, FLinearColor(1, 1, 1, A));
	}

	// a marker on the goal (where to go), with the distance
	if (Stage->Kind == ESOStageKind::Travel || Stage->Kind == ESOStageKind::Hold)
	{
		const FVector Screen = Project(Stage->Goal + FVector(0, 0, 150.0f), true);
		if (Screen.Z > 0.0f)
		{
			const FVector2D P(FMath::Clamp<float>(Screen.X, 40.0f * S, W - 40.0f * S), FMath::Clamp<float>(Screen.Y, 60.0f * S, H - 60.0f * S));
			const float R = 9.0f * S;
			DrawLine(P.X, P.Y - R, P.X + R, P.Y, Void, 2.0f * S);
			DrawLine(P.X + R, P.Y, P.X, P.Y + R, Void, 2.0f * S);
			DrawLine(P.X, P.Y + R, P.X - R, P.Y, Void, 2.0f * S);
			DrawLine(P.X - R, P.Y, P.X, P.Y - R, Void, 2.0f * S);
			const int32 Metres = FMath::RoundToInt(FVector::Dist(Pawn->GetActorLocation(), Stage->Goal) / 100.0f);
			DrawText(FString::Printf(TEXT("%d m"), Metres), Dim, P.X - 12.0f * S, P.Y + R + 4.0f * S, Small, 0.95f * S);
		}
	}

	// the boss across the top
	DrawBossBar(Op->GetBoss(), W, S);
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
		for (const FString& Line : Lines)
		{
			if (!Line.IsEmpty())
			{
				DrawText(Line, Brain->IsInCombat() ? FLinearColor(1.0f, 0.85f, 0.5f) : FLinearColor(0.7f, 0.9f, 1.0f), Screen.X - 60.0f * S, Y, Small, 0.9f * S);
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

void ASOHUD::DrawBossBar(const ASOEnemy* Boss, float W, float S)
{
	if (!Boss || Boss->IsDead())
	{
		return;
	}
	UFont* Small = GEngine ? GEngine->GetSmallFont() : nullptr;
	UFont* Font = GEngine ? GEngine->GetMediumFont() : nullptr;
	const FLinearColor Void(0.66f, 0.42f, 1.0f, 0.95f);
	auto Centred = [&](const FString& Text, float Y, UFont* F, float Scale, FLinearColor C)
	{
		float TW = 0.0f, TH = 0.0f;
		GetTextSize(Text, TW, TH, F, Scale);
		DrawText(Text, C, W * 0.5f - TW * 0.5f, Y, F, Scale);
	};
	{
		const float BW = 640.0f * S, BX = W * 0.5f - BW * 0.5f, BY = 62.0f * S;
		Centred(Boss->DisplayName.ToString().ToUpper(), BY - 26.0f * S, Font, 1.05f * S, FLinearColor(1, 1, 1, 0.95f));
		DrawRect(FLinearColor(0, 0, 0, 0.55f), BX - 3.0f * S, BY - 3.0f * S, BW + 6.0f * S, 18.0f * S);
		DrawBar(BX, BY, BW, 12.0f * S, Boss->GetHealth() / FMath::Max(Boss->GetMaxHealth(), 1.0f), Void);
		if (Boss->GetMaxShield() > 0.0f && Boss->GetShield() > 0.0f)
		{
			DrawRect(Shield, BX, BY + 13.0f * S, BW * Boss->GetShield() / Boss->GetMaxShield(), 3.0f * S);
		}
		// its fight: a notch on the bar where each phase begins, the phase's name, and when it reels
		const USOBossComponent* Fight = Boss->GetBoss();
		const USOBossData* Table = Fight ? Fight->GetData() : nullptr;
		for (int32 i = 1; Table && i < Table->Phases.Num(); ++i)
		{
			const float Notch = BX + BW * FMath::Clamp(Table->Phases[i].FromHealth, 0.0f, 1.0f);
			DrawRect(FLinearColor(0, 0, 0, 0.85f), Notch - 1.5f * S, BY - 2.0f * S, 3.0f * S, 16.0f * S);
			DrawRect(FLinearColor(1, 1, 1, i > Fight->GetPhase() ? 0.9f : 0.3f), Notch - 0.5f * S, BY - 2.0f * S, 1.0f * S, 16.0f * S);
		}
		if (Boss->IsImmune())
		{
			Centred(Boss->ImmuneReason.ToString(), BY + 22.0f * S, Small, 1.0f * S, FLinearColor(1.0f, 0.75f, 0.35f, 0.95f));
		}
		else if (Boss->HasStatus(SOTags::Status_Stagger))
		{
			Centred(NSLOCTEXT("SO", "BossReels", "REELING").ToString(), BY + 22.0f * S, Small, 1.0f * S, FLinearColor(1.0f, 0.95f, 0.6f, 0.6f + 0.4f * FMath::Abs(FMath::Sin(GetWorld()->GetTimeSeconds() * 6.0f))));
		}
		else if (const FSOBossPhase* Phase = Fight ? Fight->GetPhaseData() : nullptr; Phase && !Phase->Name.IsEmpty())
		{
			Centred(Phase->Name.ToString().ToUpper(), BY + 22.0f * S, Small, 0.95f * S, FLinearColor(0.8f, 0.7f, 1.0f, 0.8f));
		}
	}
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
	TArray<FCanvasUVTri> Body, Rim, Glass;
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
		Quad(Glass, C + E0, C + E1, C + E0 * (1.0f - Look.EdgeDepth), C + E1 * (1.0f - Look.EdgeDepth), Look.Edge, Clear);
	}
	for (TArray<FCanvasUVTri>* Tris : { &Glass, &Body, &Rim })
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
		const FLinearColor Gold(0.95f, 0.64f, 0.24f, 0.9f);
		const FLinearColor GoldDim(0.95f, 0.64f, 0.24f, 0.55f);
		const float Top = Radius(Theme, -UE_HALF_PI, R, Time) / S, Side = Radius(Theme, 0.0f, R, Time) / S;
		Poly({ FVector2D(-120, -Top - 26), FVector2D(0, -Top - 8), FVector2D(120, -Top - 26) }, Gold, 3.0f * S, false);
		Poly({ FVector2D(-70, -Top - 40), FVector2D(0, -Top - 24), FVector2D(70, -Top - 40) }, GoldDim, 2.0f * S, false);
		for (int32 j = 0; j < 3; ++j)
		{
			const float X = Side + 26.0f + j * 30.0f;
			Poly({ FVector2D(X, 0), FVector2D(X + 18.0f, 0) }, Gold, 3.0f * S, false);
			Poly({ FVector2D(-X, 0), FVector2D(-X - 18.0f, 0) }, Gold, 3.0f * S, false);
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
		const FLinearColor Line(0.02f, 0.02f, 0.02f, 0.95f);
		DrawLine(C.X - R, C.Y, C.X - 18.0f * S, C.Y, Line, 1.5f * S);
		DrawLine(C.X + 18.0f * S, C.Y, C.X + R, C.Y, Line, 1.5f * S);
		DrawLine(C.X, C.Y + 18.0f * S, C.X, C.Y + R, Line, 1.5f * S);
		DrawLine(C.X, C.Y - R * 0.6f, C.X, C.Y - 18.0f * S, Line, 1.0f * S);
		DrawRect(FLinearColor(1.0f, 0.15f, 0.1f, 0.95f), C.X - 1.5f * S, C.Y - 1.5f * S, 3.0f * S, 3.0f * S);
		for (int32 i = 1; i <= 4; ++i) // stadia ticks below the centre
		{
			DrawLine(C.X - 8.0f * S, C.Y + i * 40.0f * S, C.X + 8.0f * S, C.Y + i * 40.0f * S, Line, 1.0f * S);
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
	}
	if (HitPawn.IsValid())
	{
		HitPawn->OnHitConfirmed.Remove(HitHandle);
	}
	if (UWorld* World = GetWorld())
	{
		if (USOProjectileSubsystem* Rounds = World->GetSubsystem<USOProjectileSubsystem>())
		{
			Rounds->OnHit.Remove(HitHandle);
		}
	}
	Super::EndPlay(EndPlayReason);
}

void ASOHUD::OnHitConfirmed(bool bCrit, bool bKilled)
{
	LastHitTime = GetWorld()->GetTimeSeconds();
	bLastHitCrit = bCrit;
	bLastHitKill = bKilled;
	USOSoundLibrary::Play2D(this, bLastHitKill ? TEXT("hit_kill") : (bLastHitCrit ? TEXT("hit_crit") : TEXT("hit_tick")), 0.55f, 0.02f);
}

void ASOHUD::DrawBar(float X, float Y, float W, float H, float Fraction, const FLinearColor& Color)
{
	DrawRect(Back, X, Y, W, H);
	DrawRect(Color, X, Y, W * FMath::Clamp(Fraction, 0.0f, 1.0f), H);
}

void ASOHUD::DrawHUD()
{
	Super::DrawHUD();
	if (!Canvas)
	{
		return;
	}
	const float W = Canvas->ClipX;
	const float H = Canvas->ClipY;
	const float S = H / 1080.0f;
	const float Now = GetWorld()->GetTimeSeconds();
	UFont* Font = GEngine ? GEngine->GetMediumFont() : nullptr;
	UFont* Big = GEngine ? GEngine->GetLargeFont() : nullptr;

	BindInventory();
	const USOInventoryComponent* Inventory = FeedInventory.Get();

	// loot feed (right, middle): name · archetype · power in the rarity colour, fading after 6 s
	for (int32 i = FeedLines.Num() - 1, Row = 0; i >= 0; --i, ++Row)
	{
		const float Age = Now - FeedLines[i].Time;
		if (Age > 6.0f)
		{
			continue;
		}
		FLinearColor C = FeedLines[i].Color;
		C.A = FMath::Clamp(6.0f - Age, 0.0f, 1.0f) * FMath::Clamp(Age * 6.0f, 0.0f, 1.0f);
		float TW = 0.0f, TH = 0.0f;
		GetTextSize(FeedLines[i].Text, TW, TH, Font, 1.05f * S);
		DrawRect(FLinearColor(0, 0, 0, 0.35f * C.A), W - TW - 64.0f * S, H * 0.42f - Row * 30.0f * S - 4.0f * S, TW + 24.0f * S, TH + 8.0f * S);
		DrawText(FeedLines[i].Text, C, W - TW - 52.0f * S, H * 0.42f - Row * 30.0f * S, Font, 1.05f * S);
	}

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
		}
		HitPawn = Player;
		HitHandle = Player->OnHitConfirmed.AddUObject(this, &ASOHUD::OnHitConfirmed);
	}
	if (!InventoryWidget && !MapWidget && !Player->IsScopeView())
	{
		DrawMinimap(S);
	}
	const ASOWeapon* Weapon = Player->GetWeapon();
	if (Player->IsScopeView())
	{
		DrawScope(W, H);
	}
	if (!InventoryWidget && !MapWidget)
	{
		DrawOperation(W, H, S);
	}

	// Damage flash: red when health drops, blue when only the shield takes it.
	if (LastHealth >= 0.0f && (Player->GetHealth() < LastHealth - 0.5f || Player->GetShield() < LastShield - 0.5f))
	{
		LastDamageTime = Now;
		bLastDamageHealth = Player->GetHealth() < LastHealth - 0.5f;
	}
	LastHealth = Player->GetHealth();
	LastShield = Player->GetShield();
	const float DamageAge = Now - LastDamageTime;
	if (DamageAge < 0.45f)
	{
		const float A = (1.0f - DamageAge / 0.45f) * (bLastDamageHealth ? 0.28f : 0.16f);
		DrawRect(bLastDamageHealth ? FLinearColor(0.7f, 0.02f, 0.0f, A) : FLinearColor(0.1f, 0.45f, 1.0f, A), 0.0f, 0.0f, W, H);
	}

	// Bars over hurt creatures in view (within 40 m); an operation's boss has its own bar across the top.
	const ASOOperation* Operation = ASOOperation::Get(this);
	const ASOEnemy* LoneBoss = nullptr;
	for (TActorIterator<ASOCombatCharacter> It(GetWorld()); It; ++It)
	{
		const ASOCombatCharacter* Other = *It;
		if ((Operation && Other == Operation->GetBoss()) || Other == Player || Other->IsDead() || Other->Faction == Player->Faction)
		{
			continue;
		}
		// a boss met outside an operation (a level's variant with a boss table) has the bar across the top too,
		// once the fight is on
		if (const ASOEnemy* Creature = Cast<ASOEnemy>(Other); Creature && Creature->GetBoss())
		{
			if (!(Operation && Operation->GetBoss()) && (Creature->GetHealth() < Creature->GetMaxHealth() || Creature->IsImmune())
				&& FVector::Dist(Creature->GetActorLocation(), Player->GetActorLocation()) < 7000.0f)
			{
				LoneBoss = Creature;
			}
			continue;
		}
		if (Other->GetHealth() >= Other->GetMaxHealth())
		{
			continue;
		}
		const FVector Top = Other->GetActorLocation() + FVector(0, 0, 120.0f);
		if (FVector::Dist(Top, Player->GetActorLocation()) > 4000.0f)
		{
			continue;
		}
		const FVector Screen = Project(Top, true);
		if (Screen.Z > 0.0f)
		{
			DrawBar(Screen.X - 40.0f * S, Screen.Y, 80.0f * S, 6.0f * S, Other->GetHealth() / FMath::Max(Other->GetMaxHealth(), 1.0f), Hurt);
			// what is on it: a pip per condition under the bar (burning, slowed, staggered)
			float PipX = Screen.X - 40.0f * S;
			const TPair<FGameplayTag, FLinearColor> Pips[] = { { SOTags::Status_Burn, FLinearColor(1.0f, 0.5f, 0.1f) },
				{ SOTags::Status_Slow, FLinearColor(0.4f, 0.7f, 1.0f) }, { SOTags::Status_Stagger, FLinearColor(1.0f, 0.9f, 0.4f) },
				{ SOTags::Status_Haste, FLinearColor(0.7f, 0.4f, 1.0f) } };
			for (const TPair<FGameplayTag, FLinearColor>& Pip : Pips)
			{
				if (Other->HasStatus(Pip.Key))
				{
					DrawRect(Pip.Value, PipX, Screen.Y + 8.0f * S, 12.0f * S, 4.0f * S);
					PipX += 15.0f * S;
				}
			}
		}
	}
	DrawBossBar(LoneBoss, W, S);
	DrawAIDebug(W, H, S);

	if (Player->IsDead())
	{
		const float Left = FMath::Max(0.0f, RespawnDelay - (Now - Player->GetDeathTime()));
		DrawText(TEXT("YOU ARE DOWN"), Hurt, W * 0.5f - 110.0f * S, H * 0.4f, Big, 1.6f * S);
		DrawText(FString::Printf(TEXT("Redeploying in %.1f s"), Left), Ink, W * 0.5f - 95.0f * S, H * 0.4f + 50.0f * S, Font, 1.2f * S);
		return;
	}

	// Crosshair: four ticks spread by the current cone. First person it fades out over the first third of aiming, so
	// looking through the sights (or an optic's window) shows only the sight's own dot or post, and comes back as the
	// gun comes down. Third person nothing lines up with the eye, so it stays while aiming over the shoulder; only the
	// scope view (a magnified optic, either view) takes it away for the scope's own reticle.
	const float Ads = Player->IsScopeView() ? 1.0f
		: (Player->UsesShoulderCrosshair() ? 0.0f : FMath::Clamp(Player->GetAimProgress() * 3.0f, 0.0f, 1.0f));
	if (Player->IsFists())
	{
		// hand to hand: a point and a short bracket either side (the reach is the body's, not a gun's cone)
		const float CX = W * 0.5f, CY = H * 0.5f, T = FMath::Max(2.0f * S, 1.5f), G = 10.0f * S, L = 6.0f * S;
		DrawRect(Ink, CX - 1.5f * S, CY - 1.5f * S, 3.0f * S, 3.0f * S);
		for (const float Side : { -1.0f, 1.0f })
		{
			DrawLine(CX + Side * G, CY - L, CX + Side * (G + 3.0f * S), CY, Ink, T);
			DrawLine(CX + Side * (G + 3.0f * S), CY, CX + Side * G, CY + L, Ink, T);
		}
	}
	else if (Ads < 0.99f)
	{
		const float Spread = Weapon ? Weapon->GetStats().Spread * Player->GetSpreadScale() : 1.0f;
		const float Gap = (6.0f + Spread * 9.0f) * S;
		const float Len = FMath::Max(7.0f * S, 5.0f);
		const float CX = W * 0.5f, CY = H * 0.5f, T = FMath::Max(2.0f * S, 1.5f); // never thinner than a pixel and a half
		// each set's own crosshair, in its light (mixed with white so it reads on anything): the Sarketh's a lozenge of
		// four ticks under the brow's point, the Requiem's three closing in, the light guns' four round a point, the living
		// guns' two curved brackets, a human gun's plain four
		using namespace SOSightTheme;
		const USOWeaponData* CrossData = Weapon ? Weapon->GetData() : nullptr;
		const ETheme Theme = Of(CrossData);
		const FLinearColor Tint = Theme == ETheme::Kinetic ? Ink : FMath::Lerp(Ink, Lit(Glow(CrossData), Ink.A), 0.6f);
		const FLinearColor C(Tint.R, Tint.G, Tint.B, Ink.A * (1.0f - Ads));
		auto Tick = [&](float Deg, float From, float To)
		{
			const FVector2D D(FMath::Cos(FMath::DegreesToRadians(Deg)), FMath::Sin(FMath::DegreesToRadians(Deg)));
			DrawLine(CX + D.X * From, CY + D.Y * From, CX + D.X * To, CY + D.Y * To, C, T);
		};
		switch (Theme)
		{
		case ETheme::Sarketh:
			for (const float Deg : { 45.0f, 135.0f, 225.0f, 315.0f })
			{
				Tick(Deg, Gap, Gap + Len);
			}
			Tick(270.0f, Gap + Len * 0.4f, Gap + Len * 1.3f);
			DrawRect(C, CX - 1.5f * S, CY - 1.5f * S, 3.0f * S, 3.0f * S);
			break;
		case ETheme::Void:
			for (const float Deg : { 90.0f, 210.0f, 330.0f })
			{
				Tick(Deg, Gap, Gap + Len * 1.2f);
			}
			DrawRect(C, CX - 1.0f * S, CY - 1.0f * S, 2.0f * S, 2.0f * S);
			break;
		case ETheme::Living:
			for (const float Side : { 0.0f, 180.0f })
			{
				for (int32 k = 0; k < 4; ++k)
				{
					const float A0 = FMath::DegreesToRadians(Side - 40.0f + k * 20.0f), A1 = A0 + FMath::DegreesToRadians(20.0f);
					const float Rr = Gap + Len * 0.5f;
					DrawLine(CX + FMath::Cos(A0) * Rr, CY + FMath::Sin(A0) * Rr, CX + FMath::Cos(A1) * Rr, CY + FMath::Sin(A1) * Rr, C, T);
				}
			}
			DrawRect(C, CX - 1.5f * S, CY - 1.5f * S, 3.0f * S, 3.0f * S);
			break;
		default:
			for (const float Deg : { 0.0f, 90.0f, 180.0f, 270.0f })
			{
				Tick(Deg, Gap, Gap + Len);
			}
			if (Theme == ETheme::Light)
			{
				DrawRect(C, CX - 1.0f * S, CY - 1.0f * S, 2.0f * S, 2.0f * S);
			}
			break;
		}
	}

	// Interact prompt.
	if (const AActor* Target = Player->FindInteractable())
	{
		if (const ISOInteractable* Thing = Cast<ISOInteractable>(Target))
		{
			const FString Prompt = FString::Printf(TEXT("%s   %s"), Thing->CanInteract(Player) ? TEXT("[E]") : TEXT("   "), *Thing->GetInteractPrompt(Player).ToString());
			float TW = 0.0f, TH = 0.0f;
			GetTextSize(Prompt, TW, TH, Font, 1.2f * S);
			DrawRect(FLinearColor(0, 0, 0, 0.45f), W * 0.5f - TW * 0.5f - 14.0f * S, H * 0.64f - 6.0f * S, TW + 28.0f * S, TH + 12.0f * S);
			DrawText(Prompt, Thing->CanInteract(Player) ? Ink : FLinearColor(0.6f, 0.6f, 0.6f), W * 0.5f - TW * 0.5f, H * 0.64f, Font, 1.2f * S);
		}
	}

	// Hit marker.
	const float HitAge = Now - LastHitTime;
	if (HitAge < 0.18f)
	{
		const FLinearColor C = bLastHitKill ? Hurt : (bLastHitCrit ? FLinearColor(1.0f, 0.85f, 0.2f, 1.0f) : Ink);
		const float CX = W * 0.5f, CY = H * 0.5f, A = 6.0f * S, B = 13.0f * S;
		DrawLine(CX - B, CY - B, CX - A, CY - A, C, 2.5f * S);
		DrawLine(CX + A, CY - A, CX + B, CY - B, C, 2.5f * S);
		DrawLine(CX - B, CY + B, CX - A, CY + A, C, 2.5f * S);
		DrawLine(CX + A, CY + A, CX + B, CY + B, C, 2.5f * S);
	}

	// Health + shield (bottom left).
	const float BX = 40.0f * S, BY = H - 70.0f * S, BW = 300.0f * S;
	if (Player->GetMaxShield() > 0.0f)
	{
		DrawBar(BX, BY - 14.0f * S, BW, 8.0f * S, Player->GetShield() / Player->GetMaxShield(), Shield);
	}
	const float HealthFraction = Player->GetHealth() / FMath::Max(Player->GetMaxHealth(), 1.0f);
	DrawBar(BX, BY, BW, 14.0f * S, HealthFraction, HealthFraction < 0.35f ? Hurt : Health);

	// Conditions on the player: a frame of light round the view while braced, a word over the bars for the rest.
	{
		if (Player->HasStatus(SOTags::Status_Guard))
		{
			const FLinearColor Frame(0.45f, 0.9f, 1.0f, 0.5f);
			const float T = 4.0f * S;
			DrawRect(Frame, 0.0f, 0.0f, W, T);
			DrawRect(Frame, 0.0f, H - T, W, T);
			DrawRect(Frame, 0.0f, T, T, H - 2.0f * T);
			DrawRect(Frame, W - T, T, T, H - 2.0f * T);
		}
		float ChipX = BX;
		const TPair<FGameplayTag, const TCHAR*> Chips[] = { { SOTags::Status_Guard, TEXT("BRACED") }, { SOTags::Status_Burn, TEXT("BURNING") },
			{ SOTags::Status_Slow, TEXT("SLOWED") }, { SOTags::Status_Stagger, TEXT("STAGGERED") }, { SOTags::Status_Jam, TEXT("JAMMED") },
			{ SOTags::Status_Suppressed, TEXT("UNDER FIRE") } };
		for (const TPair<FGameplayTag, const TCHAR*>& Chip : Chips)
		{
			if (Player->HasStatus(Chip.Key))
			{
				float TW = 0.0f, TH = 0.0f;
				GetTextSize(Chip.Value, TW, TH, Font, 0.85f * S);
				DrawRect(Back, ChipX, BY - 44.0f * S, TW + 14.0f * S, TH + 6.0f * S);
				DrawText(Chip.Value, Chip.Key == SOTags::Status_Guard ? FLinearColor(0.45f, 0.9f, 1.0f) : Hurt, ChipX + 7.0f * S, BY - 41.0f * S, Font, 0.85f * S);
				ChipX += TW + 20.0f * S;
			}
		}
	}

	// Abilities (under the health bar): a cell per slot the kit fills, bright when a charge is ready, with the next
	// charge's progress along its foot; the ultimate's charge as a line between the bars and the cells.
	{
		static const TCHAR* Keys[] = { TEXT("G"), TEXT("V"), TEXT("Q"), TEXT(""), TEXT("X") };
		const FLinearColor Ready(0.45f, 0.9f, 1.0f, 0.95f);
		const FLinearColor Waiting(0.45f, 0.9f, 1.0f, 0.3f);
		const float Cell = 30.0f * S, Y = BY + 26.0f * S;
		float X = BX;
		for (int32 i = 0; i < static_cast<int32>(ESOAbilitySlot::Count); ++i)
		{
			const ESOAbilitySlot Slot = static_cast<ESOAbilitySlot>(i);
			int32 Charges = 0, MaxCharges = 0;
			float Left = 0.0f, Cooldown = 0.0f;
			if (!Player->GetAbilityState(Slot, Charges, MaxCharges, Left, Cooldown))
			{
				continue;
			}
			const bool bUltimate = Slot == ESOAbilitySlot::Ultimate;
			const bool bReady = Charges > 0 && (!bUltimate || Player->GetUltimate() >= Player->GetMaxUltimate() - 0.5f);
			DrawRect(Back, X, Y, Cell, Cell);
			DrawRect(bReady ? (bUltimate ? FLinearColor(1.0f, 0.82f, 0.3f, 0.95f) : Ready) : Waiting, X, Y, Cell, Cell);
			if (Charges < MaxCharges && Cooldown > 0.0f)
			{
				DrawRect(Ink, X, Y + Cell - 3.0f * S, Cell * FMath::Clamp(1.0f - Left / Cooldown, 0.0f, 1.0f), 3.0f * S);
			}
			DrawText(Keys[i], bReady ? FLinearColor::Black : Ink, X + 9.0f * S, Y + 6.0f * S, Font, 0.9f * S);
			if (MaxCharges > 1)
			{
				DrawText(FString::FromInt(Charges), Ink, X + Cell + 4.0f * S, Y + 8.0f * S, Font, 0.85f * S);
			}
			X += Cell + (MaxCharges > 1 ? 24.0f : 8.0f) * S;
		}
		if (Player->GetAbilitySet() && Player->GetAbilitySet()->Find(ESOAbilitySlot::Ultimate) && Player->GetMaxUltimate() > 0.0f)
		{
			const float Charge = Player->GetUltimate() / Player->GetMaxUltimate();
			DrawBar(BX, BY + 17.0f * S, BW, 3.0f * S, Charge, Charge >= 0.995f ? FLinearColor(1.0f, 0.82f, 0.3f, 1.0f) : Ready);
		}
	}

	// Ammo (bottom right) + reload progress.
	if (Weapon)
	{
		const FString Ammo = FString::Printf(TEXT("%d  /  %d"), Weapon->GetMag(), Weapon->GetReserve());
		DrawText(Ammo, Weapon->GetMag() == 0 ? Hurt : Ink, W - 230.0f * S, H - 90.0f * S, Big, 1.3f * S);
		if (Weapon->GetRampageStacks() > 0)
		{
			DrawText(FString::Printf(TEXT("RAMPAGE x%d"), Weapon->GetRampageStacks()), FLinearColor(1.0f, 0.5f, 0.2f), W - 230.0f * S, H - 60.0f * S, Font, 1.0f * S);
		}
		if (Weapon->HasHeat())
		{
			// the crystal's heat under the count: amber, turning white-hot past the point where its rounds fly faster;
			// at full it vents and the gauge says so
			const float Heat = Weapon->GetHeat();
			const FLinearColor Cool(1.0f, 0.5f, 0.1f), Hot(1.0f, 0.93f, 0.8f);
			const FLinearColor C = FMath::Lerp(Cool, Hot, FMath::Clamp((Heat - ASOWeapon::HeatMedium) / (1.0f - ASOWeapon::HeatMedium), 0.0f, 1.0f));
			DrawRect(FLinearColor(1, 1, 1, 0.08f), W - 230.0f * S, H - 100.0f * S, 150.0f * S, 4.0f * S);
			DrawBar(W - 230.0f * S, H - 100.0f * S, 150.0f * S, 4.0f * S, Heat, C);
			if (Weapon->IsVenting())
			{
				DrawText(TEXT("VENTING"), Hot, W - 74.0f * S, H - 108.0f * S, Font, 0.8f * S);
			}
		}
		// the three slots: number, name in the rarity colour, the one in hand bright
		const USOLootTables* Tables = USOLootLibrary::GetTables();
		for (int32 Slot = 0; Slot < USOInventoryComponent::NumSlots; ++Slot)
		{
			const FSOWeaponInstance* Copy = Inventory ? Inventory->GetEquipped(Slot) : nullptr;
			const bool bActive = Inventory ? Inventory->GetActiveSlot() == Slot : Slot == 0;
			const FString Name = Copy ? Copy->Name : (Slot == 0 && Weapon->GetData() ? Weapon->GetData()->DisplayName.ToString() : FString(TEXT("-")));
			FLinearColor C = Copy && Tables ? Tables->GetRarity(Copy->Rarity).Color : Ink;
			C.A = bActive ? 1.0f : 0.45f;
			const float Y = H - 200.0f * S + Slot * 24.0f * S;
			if (bActive)
			{
				DrawRect(FLinearColor(1, 1, 1, 0.08f), W - 240.0f * S, Y - 2.0f * S, 210.0f * S, 22.0f * S);
			}
			DrawText(FString::Printf(TEXT("%d   %s"), Slot + 1, *Name), C, W - 232.0f * S, Y, Font, (bActive ? 1.0f : 0.9f) * S);
		}
		if (Weapon->IsReloading())
		{
			DrawBar(W * 0.5f - 60.0f * S, H * 0.5f + 40.0f * S, 120.0f * S, 4.0f * S, Weapon->GetReloadProgress(), Ink);
		}
		else if (Weapon->GetMag() == 0 && Weapon->GetReserve() > 0)
		{
			DrawText(TEXT("RELOAD"), Hurt, W * 0.5f - 32.0f * S, H * 0.5f + 34.0f * S, Font, 1.1f * S);
		}
	}
}
