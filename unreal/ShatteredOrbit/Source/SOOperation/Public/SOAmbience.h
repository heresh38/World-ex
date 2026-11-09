#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "SOAmbience.generated.h"

class UAudioComponent;

/**
 * A living spot of an operation's level: a looping sound in the world (the hive's machinery humming, a growth
 * creaking and clicking, the far chorus of the Altered) and, near growths, violet spores drifting up out of it, so the
 * base breathes around the player. Placed by make_operation_map.py from Data/op_<name>_art.json ("ambience").
 */
UCLASS()
class SOOPERATION_API ASOAmbience : public AActor
{
	GENERATED_BODY()

public:
	ASOAmbience();

	/** The loop (/Game/Audio/S_<Sound>): amb_alien_hum, amb_hive, amb_alien_chorus. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Ambience")
	FName Sound;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Ambience")
	float Volume = 1.0f;

	/** How far it is heard (cm); it fades out to nothing there. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Ambience", meta = (Units = "cm"))
	float Radius = 2000.0f;

	/** Drifting spores round it (only near a player, a few a second). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Ambience")
	bool bSpores = false;

	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

protected:
	UPROPERTY(Transient)
	TObjectPtr<UAudioComponent> Loop;

	float SporeTimer = 0.0f;
};
