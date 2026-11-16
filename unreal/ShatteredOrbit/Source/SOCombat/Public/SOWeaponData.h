#pragma once

#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "SOCombatTypes.h"
#include "SOWeaponData.generated.h"

class UStaticMesh;
class UTexture2D;

/** What leaves the muzzle (data.js: kinetic rounds with drop, energy bolts, rockets, horror goo). */
UENUM(BlueprintType)
enum class ESOProjectileKind : uint8
{
	Round,   // kinetic bullet (gravity)
	Bolt,    // energy bolt (no drop, coloured tracer)
	Rocket,  // slow, splash
	Spit,    // horror: acid glob, splash + acid damage over time
	Bile,    // horror: bile pellets
	Brood,   // horror: a brood sac that bursts into a swarm
	Slug     // Sarketh: a crystalline slug in an amber field: flies (seen), its shell ruptures on a hit, the slug goes on
	         // into the body (docs/orion/SARKETH_WEAPONS.md)
};

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

	/** Nested parts (crane > cylinder > rounds) move with their parent part; None = the gun body. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Part")
	FName Parent;
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
	/** The kind of gun (Auto Rifle, Pump Shotgun, ...). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Weapon")
	FText DisplayName;

	/** The gun's one name: every copy of it carries it, whatever its rarity, rolls or perks. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Weapon")
	FText Title;

	/** The armoury's words for it (game_data.json): its line, its class's name (Light / Ballistic / Living) and the
	 *  trait its set or class carries (the gold node of the perk web). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Weapon")
	FText Lore;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Weapon")
	FText ClassName;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Weapon")
	FText TraitName;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Weapon")
	FText TraitText;

	/** data.js archetype key (rifle, carbine, ...): picks the reload choreography. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Weapon")
	FName Archetype = TEXT("rifle");

	/** Equip slot: 0 Primary, 1 Special, 2 Heavy. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Weapon")
	int32 Slot = 0;

	/** Relative chance in random loot (horror guns are rarer finds; 0 = never: a raid set's gun, earned only). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Weapon")
	float LootWeight = 1.0f;

	/** The finish every copy wears (a raid set's own: requiem); None = the default. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Weapon")
	FName DefaultShader;

	/** The set it belongs to (void_requiem), or None. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Weapon")
	FName SetId;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Weapon")
	ESOWeaponClass WeaponClass = ESOWeaponClass::Kinetic;

	/** Sounds: <prefix>_shot_fp (own, 2D) and <prefix>_shot_world (everyone else, 3D). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Weapon")
	FName SoundPrefix = TEXT("rifle");

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

	/** Rounds per trigger pull in a burst (0 = none) and the rate inside the burst. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Stats")
	int32 Burst = 0;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Stats")
	float BurstRpm = 0.0f;

	/** Projectiles per shot (shotguns); Damage is per pellet. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Stats")
	int32 Pellets = 1;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Stats")
	ESOProjectileKind Projectile = ESOProjectileKind::Round;

	/** Splash radius (m) for rockets and goo; 0 = none. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Stats", meta = (Units = "m"))
	float Splash = 0.0f;

	/** Share of the damage dealt again as acid over 3 s (horror). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Stats")
	float Dot = 0.0f;

	/** Brood: parasites released where the sac bursts. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Stats")
	int32 Swarm = 0;

	/** The set's colours (game_data.json "palettes"; the owner, 2026-11-15: every gun of a set has the same colour
	 *  palette and fires the same colour): what it fires, and the light on the gun (alpha 0: none set, the rarity's). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Visuals")
	FLinearColor TracerColor = FLinearColor(1.0f, 0.78f, 0.45f);

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Visuals")
	FLinearColor GlowColor = FLinearColor(0.0f, 0.0f, 0.0f, 0.0f);

	/** A slug's remaining crystal goes on through the body it ruptured on: how many bodies it passes after the first,
	 *  and the share of its damage it keeps through each (the Sarketh's rounds; the Penetrator pierces several). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Stats")
	int32 Pierce = 0;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Stats")
	float PierceKeep = 0.6f;

	/** How big the round is drawn (1 = the assault rifle's slug); 0 = from its damage. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Visuals")
	float RoundSize = 0.0f;

	/** Thermal accumulation (the Sarketh's guns): the heat one shot adds to the crystal (1 = full; 0 = the gun has
	 *  none), how much it loses a second once the trigger has rested HeatCoolDelay, the vent it is forced into at
	 *  full heat (s, it cannot fire meanwhile), and how much faster its rounds fly at high heat. Medium heat: the
	 *  rounds burn brighter. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Heat")
	float HeatPerShot = 0.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Heat")
	float HeatCool = 0.6f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Heat")
	float HeatCoolDelay = 0.3f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Heat")
	float VentTime = 1.4f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Heat")
	float HeatSpeed = 1.3f;

	/** The Sarketh's guns never reload (the owner, 2026-11-16: "remove loading and keep venting so after we stop
	 *  shooting and the counter rests to 0 or after venting we slowly add bullets from reserve to magazine"): once the
	 *  trigger rests and the crystal has cooled to nothing (or a vent has ended), rounds condense from the reserve into
	 *  it, a full load in this many seconds. An empty trigger or the reload key vents it. 0 = a gun that reloads. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Heat", meta = (Units = "s"))
	float RefillTime = 0.0f;

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

	/** How the gun is carried in first person on a sprint (data "carry"): low (a long gun at the low ready), short (an
	 *  SMG, up part of the way), high (a handgun, muzzle to the sky). None: a handgun high, anything else low. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Stats")
	FName SprintCarry;

	// --- Visuals (mesh space: cm, gun faces +Y) ---
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Visuals")
	TSoftObjectPtr<UStaticMesh> BodyMesh;

	/** Inventory icon: the gun rendered side-on from our model (tools/blender/icons.py). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Visuals")
	TSoftObjectPtr<UTexture2D> Icon;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Visuals")
	TArray<FSOWeaponPart> Parts;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Visuals")
	FVector MuzzleLocation = FVector(0.0f, 60.0f, 5.0f);

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Visuals")
	FVector SightLocation = FVector(0.0f, 0.0f, 10.0f);

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Visuals")
	FVector ForegripLocation = FVector(0.0f, 30.0f, 0.0f);

	/** Optic mount (mesh space); bHasRail = optics can be mounted. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Visuals")
	FVector RailLocation = FVector::ZeroVector;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Visuals")
	bool bHasRail = false;

	/** The factory sight is magnified glass (scout, sniper): fully aimed, the scope picture replaces the gun. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Visuals")
	bool bBuiltInScope = false;

	/** Optics this gun takes (data.js sights: default = factory sights, reflex, holo, x2, x4, x8) and the one it ships with. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Visuals")
	TArray<FName> Sights;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Visuals")
	FName DefaultSight = TEXT("default");

	/** First-person arms (viewmodel_arms.glb): the right arm sits at the gun origin, the left on the foregrip. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Visuals")
	TSoftObjectPtr<UStaticMesh> ArmLeftMesh;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Visuals")
	TSoftObjectPtr<UStaticMesh> ArmRightMesh;

	const FSOWeaponPart* FindPart(FName PartName) const;
	float GetShotInterval() const { return RoundsPerMinute > 0.0f ? 60.0f / RoundsPerMinute : 0.1f; }
};
