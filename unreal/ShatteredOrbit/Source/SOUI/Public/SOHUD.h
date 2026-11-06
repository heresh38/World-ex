#pragma once

#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "SOHUD.generated.h"

struct FSOProjectile;

/**
 * Stage 3 combat HUD drawn on the canvas (the CommonUI HUD replaces it later): spread-sized crosshair, hit markers,
 * ammo, health + shield, reload progress, bars over hurt creatures, and the downed / respawn message.
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

private:
	void OnRoundHit(const FSOProjectile& Round, const FHitResult& Hit, float Damage);
	void DrawBar(float X, float Y, float W, float H, float Fraction, const FLinearColor& Color);

	float LastHitTime = -100.0f;
	bool bLastHitCrit = false;
	bool bLastHitKill = false;
	FDelegateHandle HitHandle;
};
