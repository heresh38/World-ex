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

ASOHUD::ASOHUD()
{
}

void ASOHUD::BeginPlay()
{
	Super::BeginPlay();
	if (USOProjectileSubsystem* Rounds = GetWorld()->GetSubsystem<USOProjectileSubsystem>())
	{
		HitHandle = Rounds->OnHit.AddUObject(this, &ASOHUD::OnRoundHit);
	}
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

void ASOHUD::DrawScope(float W, float H)
{
	// magnified glass: black outside a circle, a fine reticle inside
	const FVector2D C(W * 0.5f, H * 0.5f);
	const float R = H * 0.46f, Far = FMath::Max(W, H) * 1.5f;
	const int32 N = 72;
	TArray<FCanvasUVTri> Tris;
	for (int32 i = 0; i < N; ++i)
	{
		const float A0 = UE_TWO_PI * i / N, A1 = UE_TWO_PI * (i + 1) / N;
		const FVector2D I0 = C + FVector2D(FMath::Cos(A0), FMath::Sin(A0)) * R, I1 = C + FVector2D(FMath::Cos(A1), FMath::Sin(A1)) * R;
		const FVector2D O0 = C + FVector2D(FMath::Cos(A0), FMath::Sin(A0)) * Far, O1 = C + FVector2D(FMath::Cos(A1), FMath::Sin(A1)) * Far;
		FCanvasUVTri T1, T2;
		T1.V0_Pos = I0; T1.V1_Pos = O0; T1.V2_Pos = O1;
		T2.V0_Pos = I0; T2.V1_Pos = O1; T2.V2_Pos = I1;
		T1.V0_Color = T1.V1_Color = T1.V2_Color = T2.V0_Color = T2.V1_Color = T2.V2_Color = FLinearColor::Black;
		Tris.Add(T1);
		Tris.Add(T2);
	}
	FCanvasTriangleItem Ring(Tris, GWhiteTexture);
	Canvas->DrawItem(Ring);
	const FLinearColor Line(0.02f, 0.02f, 0.02f, 0.95f);
	const float S = H / 1080.0f;
	DrawLine(C.X - R, C.Y, C.X - 18.0f * S, C.Y, Line, 1.5f * S);
	DrawLine(C.X + 18.0f * S, C.Y, C.X + R, C.Y, Line, 1.5f * S);
	DrawLine(C.X, C.Y + 18.0f * S, C.X, C.Y + R, Line, 1.5f * S);
	DrawLine(C.X, C.Y - R * 0.6f, C.X, C.Y - 18.0f * S, Line, 1.0f * S);
	DrawRect(FLinearColor(1.0f, 0.15f, 0.1f, 0.95f), C.X - 1.5f * S, C.Y - 1.5f * S, 3.0f * S, 3.0f * S);
	for (int32 i = 1; i <= 4; ++i) // stadia ticks below the centre
	{
		DrawLine(C.X - 8.0f * S, C.Y + i * 40.0f * S, C.X + 8.0f * S, C.Y + i * 40.0f * S, Line, 1.0f * S);
	}
}

void ASOHUD::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	if (FeedInventory.IsValid())
	{
		FeedInventory->OnFeed.Remove(FeedHandle);
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

void ASOHUD::OnRoundHit(const FSOProjectile& Round, const FHitResult& Hit, float Damage)
{
	if (Damage <= 0.0f || Round.Instigator.Get() != GetOwningPawn())
	{
		return;
	}
	LastHitTime = GetWorld()->GetTimeSeconds();
	bLastHitCrit = USOProjectileSubsystem::IsPrecisionBone(Hit.BoneName);
	const ASOCombatCharacter* Victim = Cast<ASOCombatCharacter>(Hit.GetActor());
	bLastHitKill = Victim && Victim->IsDead();
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
	if (!InventoryWidget && !MapWidget && !Player->IsScopeView())
	{
		DrawMinimap(S);
	}
	const ASOWeapon* Weapon = Player->GetWeapon();
	if (Player->IsScopeView())
	{
		DrawScope(W, H);
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

	// Bars over hurt creatures in view (within 40 m).
	for (TActorIterator<ASOCombatCharacter> It(GetWorld()); It; ++It)
	{
		const ASOCombatCharacter* Other = *It;
		if (Other == Player || Other->IsDead() || Other->Faction == Player->Faction || Other->GetHealth() >= Other->GetMaxHealth())
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
		}
	}

	if (Player->IsDead())
	{
		const float Left = FMath::Max(0.0f, RespawnDelay - (Now - Player->GetDeathTime()));
		DrawText(TEXT("YOU ARE DOWN"), Hurt, W * 0.5f - 110.0f * S, H * 0.4f, Big, 1.6f * S);
		DrawText(FString::Printf(TEXT("Redeploying in %.1f s"), Left), Ink, W * 0.5f - 95.0f * S, H * 0.4f + 50.0f * S, Font, 1.2f * S);
		return;
	}

	// Crosshair: four ticks spread by the current cone, gone when fully aimed.
	const float Ads = Player->GetAimProgress();
	if (Ads < 0.95f)
	{
		const float Spread = Weapon ? Weapon->GetStats().Spread * Player->GetSpreadScale() : 1.0f;
		const float Gap = (6.0f + Spread * 9.0f) * S;
		const float Len = 7.0f * S;
		const FLinearColor C(Ink.R, Ink.G, Ink.B, Ink.A * (1.0f - Ads));
		const float CX = W * 0.5f, CY = H * 0.5f;
		DrawLine(CX - Gap - Len, CY, CX - Gap, CY, C, 2.0f * S);
		DrawLine(CX + Gap, CY, CX + Gap + Len, CY, C, 2.0f * S);
		DrawLine(CX, CY - Gap - Len, CX, CY - Gap, C, 2.0f * S);
		DrawLine(CX, CY + Gap, CX, CY + Gap + Len, C, 2.0f * S);
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

	// Ammo (bottom right) + reload progress.
	if (Weapon)
	{
		const FString Ammo = FString::Printf(TEXT("%d  /  %d"), Weapon->GetMag(), Weapon->GetReserve());
		DrawText(Ammo, Weapon->GetMag() == 0 ? Hurt : Ink, W - 230.0f * S, H - 90.0f * S, Big, 1.3f * S);
		if (Weapon->GetRampageStacks() > 0)
		{
			DrawText(FString::Printf(TEXT("RAMPAGE x%d"), Weapon->GetRampageStacks()), FLinearColor(1.0f, 0.5f, 0.2f), W - 230.0f * S, H - 60.0f * S, Font, 1.0f * S);
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
