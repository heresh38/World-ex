#pragma once

#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "SOMelee.generated.h"

class ASOCombatCharacter;
class UStaticMesh;

/**
 * Hand to hand (the owner, 2026-11-15: "mele is when we put away all our guns on our back so we hold nothing but our
 * fists and we need to implement hand combat like punching, or if we have a blade then blade strikes (light and hard
 * strike for everything in mele)"). A style is how a player fights with the guns on the back: the fists, or a blade in
 * the right hand. Every style has a guard (a looping clip on the upper body), a chain of light blows (fire, again and
 * again: each next blow if pressed before the last one is over) and one heavy blow (aim: wound up, slower, harder).
 * Source: Data/game_data.json "melee" -> /Game/Data/DA_Melee (SO_IMPORT_ONLY=melee).
 */
USTRUCT(BlueprintType)
struct SOCOMBAT_API FSOMeleeBlow
{
	GENERATED_BODY()

	/** The body's clip (each body has its own: hero/<sex>/motion.py), begun and ended in the style's guard. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Melee")
	FName Clip;

	/** Seconds into the clip at which the blow lands (what comes before is the wind-up). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Melee", meta = (Units = "s"))
	float HitTime = 0.1f;

	/** Seconds before the next blow can start (the clip may run on: the next one cuts its recovery short). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Melee", meta = (Units = "s"))
	float Recover = 0.3f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Melee")
	float Damage = 20.0f;

	/** Reach from the body's middle (cm) and the cone it lands in (degrees either side of the aim). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Melee", meta = (Units = "cm"))
	float Range = 170.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Melee")
	float Angle = 45.0f;

	/** Thrown back by (cm/s) and staggered for (s) on a hit. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Melee")
	float Force = 0.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Melee", meta = (Units = "s"))
	float Stagger = 0.0f;

	/** The body steps in by this much as it lands (cm/s along the aim, on the ground). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Melee")
	float Lunge = 0.0f;

	/** Sounds: the swing (as the wind-up ends) and the hit (sfx_synth.py "melee"). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Melee")
	FName SwingSound;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Melee")
	FName HitSound;
};

USTRUCT(BlueprintType)
struct SOCOMBAT_API FSOMeleeStyle
{
	GENERATED_BODY()

	/** "fists", or the archetype id of a blade. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Melee")
	FName Id;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Melee")
	FText Name;

	/** What the hand holds (a blade; none for the fists), placed in the right fist by ASOCharacter. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Melee")
	TSoftObjectPtr<UStaticMesh> Mesh;

	/** The set it belongs to: a set cache (ASOReliquary::RewardSet) gives every style of its set. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Melee")
	FName SetId;

	/** The guard: a looping clip on the upper body while the style is out. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Melee")
	FName Guard;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Melee")
	TArray<FSOMeleeBlow> Light;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Melee")
	FSOMeleeBlow Heavy;

	/** A light blow pressed this long after the last one could start goes on with the chain; later it begins again. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Melee", meta = (Units = "s"))
	float ChainGrace = 0.45f;

	/** A blade draws its edge as a sweep of light (the set's colour); fists do not. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Melee")
	bool bEdge = false;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Melee")
	FLinearColor EdgeColor = FLinearColor(1.0f, 0.6f, 0.18f);
};

UCLASS(BlueprintType)
class SOCOMBAT_API USOMeleeTable : public UPrimaryDataAsset
{
	GENERATED_BODY()

public:
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Melee")
	TArray<FSOMeleeStyle> Styles;

	const FSOMeleeStyle* Find(FName Id) const;

	/** /Game/Data/DA_Melee (loaded once, kept). */
	static const USOMeleeTable* Get();
};

UCLASS()
class SOCOMBAT_API USOMeleeLibrary : public UObject
{
	GENERATED_BODY()

public:
	/** Lands a blow (server only): every body of the other side within reach, in the cone round the aim and not behind
	 *  the world's geometry, takes the damage through the gate, is staggered and thrown back. Returns how many it hit. */
	static int32 Land(ASOCombatCharacter* User, const FSOMeleeBlow& Blow);
};
