#include "SOHUD.h"

#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/Font.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "SOCharacter.h"
#include "SOCombatCharacter.h"
#include "SOProjectileSubsystem.h"
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

void ASOHUD::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
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

	const ASOCharacter* Player = Cast<ASOCharacter>(GetOwningPawn());
	if (!Player)
	{
		return;
	}
	const ASOWeapon* Weapon = Player->GetWeapon();

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
		const float Spread = Weapon && Weapon->GetData() ? Weapon->GetData()->Spread * Player->GetSpreadScale() : 1.0f;
		const float Gap = (6.0f + Spread * 9.0f) * S;
		const float Len = 7.0f * S;
		const FLinearColor C(Ink.R, Ink.G, Ink.B, Ink.A * (1.0f - Ads));
		const float CX = W * 0.5f, CY = H * 0.5f;
		DrawLine(CX - Gap - Len, CY, CX - Gap, CY, C, 2.0f * S);
		DrawLine(CX + Gap, CY, CX + Gap + Len, CY, C, 2.0f * S);
		DrawLine(CX, CY - Gap - Len, CX, CY - Gap, C, 2.0f * S);
		DrawLine(CX, CY + Gap, CX, CY + Gap + Len, C, 2.0f * S);
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
		if (const USOWeaponData* Data = Weapon->GetData())
		{
			DrawText(Data->DisplayName.ToString(), Ink, W - 230.0f * S, H - 120.0f * S, Font, 1.0f * S);
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
