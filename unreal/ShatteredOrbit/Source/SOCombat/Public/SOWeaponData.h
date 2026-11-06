#pragma once

#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "SOCombatTypes.h"
#include "SOWeaponData.generated.h"

class UStaticMesh;

/** One moving reload part (node names are an API: mag, bolt, charge, slide, pump, ...). Mesh space = imported FBX space. */
USTRUCT(BlueprintType)
struct SOCOMBAT_API FSOWeaponPart
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Part")
	FName Name;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Part")
	TSoftObjectPtr<UStaticMesh> Mesh;

	/** Rest pivot in the gun's mesh space (cm; the gun faces +Y there). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Part")
	FVector RestLocation = FVector::ZeroVector;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Part")
	FQuat RestRotation = FQuat::Identity;
};

/**
 * A weapon archetype: numbers from the browser build's data.js ARCHETYPES plus the Blender-built visuals.
 * Created by Content/Python/import_assets.py from tools/blender/export_fbx.py output.
 */
UCLASS(BlueprintType)
class SOCOMBAT_API USOWeaponData : public UPrimaryDataAsset
{
	GENERATED_BODY()

public:
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Weapon")
	FText DisplayName;

	/** data.js archetype key (rifle, carbine, ...): picks the reload choreography. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Weapon")
	FName Archetype = TEXT("rifle");

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Weapon")
	ESOWeaponClass WeaponClass = ESOWeaponClass::Kinetic;

	// --- Stats (data.js units: damage per round, rpm, m, m/s) ---
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Stats")
	float Damage = 19.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Stats")
	float RoundsPerMinute = 600.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Stats")
	int32 MagazineSize = 30;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Stats")
	int32 ReserveAmmo = 300;

	/** Tactical reload time; an empty reload adds the chambering. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Stats", meta = (Units = "s"))
	float ReloadTime = 2.3f;

	/** Full damage up to this range, then it falls off to MinDamageScale at twice the range. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Stats", meta = (Units = "m"))
	float Range = 40.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Stats")
	float MinDamageScale = 0.6f;

	/** Hip-fire cone half-angle in degrees. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Stats")
	float Spread = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Stats")
	float CritMultiplier = 1.6f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Stats")
	bool bAutomatic = true;

	/** ADS magnification (field of view divided by this). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Stats")
	float AimZoom = 1.35f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Stats", meta = (Units = "m/s"))
	float MuzzleVelocity = 715.0f;

	/** Bullet drop: 1 = normal gravity. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Stats")
	float GravityScale = 1.0f;

	/** Recoil strength (camera pitch kick ~0.3 degrees per unit). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Stats")
	float Kick = 1.3f;

	/** weaponHandling: seconds to aim in, seconds from sprint to fire. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Stats", meta = (Units = "s"))
	float AdsTime = 0.24f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Stats", meta = (Units = "s"))
	float SprintToFireTime = 0.2f;

	// --- Visuals (mesh space: cm, gun faces +Y) ---
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Visuals")
	TSoftObjectPtr<UStaticMesh> BodyMesh;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Visuals")
	TArray<FSOWeaponPart> Parts;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Visuals")
	FVector MuzzleLocation = FVector(0.0f, 60.0f, 5.0f);

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Visuals")
	FVector SightLocation = FVector(0.0f, 0.0f, 10.0f);

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Visuals")
	FVector ForegripLocation = FVector(0.0f, 30.0f, 0.0f);

	/** First-person arms (viewmodel_arms.glb): the right arm sits at the gun origin, the left on the foregrip. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Visuals")
	TSoftObjectPtr<UStaticMesh> ArmLeftMesh;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Visuals")
	TSoftObjectPtr<UStaticMesh> ArmRightMesh;

	const FSOWeaponPart* FindPart(FName PartName) const;
	float GetShotInterval() const { return RoundsPerMinute > 0.0f ? 60.0f / RoundsPerMinute : 0.1f; }
};
