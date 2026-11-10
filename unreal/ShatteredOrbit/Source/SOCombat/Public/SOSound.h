#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "SOSound.generated.h"

class USoundBase;

/** How far a positional sound carries (spherical attenuation, natural falloff, distance low-pass). */
UENUM(BlueprintType)
enum class ESOSoundRange : uint8
{
	Near,  // foley, footsteps, impacts: ~25 m
	Mid,   // creature voices: ~60 m
	Far    // gunfire: ~150 m
};

/**
 * Plays the synthesised effects in /Game/Audio (tools/audio/sfx_synth.py -> S_<name>) by name.
 * Sounds load on first use and stay cached; missing ones are silently skipped (tests, headless runs).
 */
UCLASS()
class SOCOMBAT_API USOSoundLibrary : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	static USoundBase* Find(FName Name);

	/** Sounds stay loaded once played, but only for the area being played: leaving it (USOAreaSubsystem) lets them
	 *  all go. */
	static void ReleaseAll();
	static int32 NumHeld();

	/** 3D at Location. PitchJitter = random +- fraction so repeats do not sound identical. */
	UFUNCTION(BlueprintCallable, Category = "SO|Sound", meta = (WorldContext = "WorldContext"))
	static void PlayAt(const UObject* WorldContext, FName Name, FVector Location, float Volume = 1.0f, float PitchJitter = 0.04f, ESOSoundRange Range = ESOSoundRange::Near);

	/** Non-spatial (the local player's own gun, UI). */
	UFUNCTION(BlueprintCallable, Category = "SO|Sound", meta = (WorldContext = "WorldContext"))
	static void Play2D(const UObject* WorldContext, FName Name, float Volume = 1.0f, float PitchJitter = 0.03f);

	/** Local player's own sound in 2D, everyone else's in 3D. */
	static void PlayFor(const AActor* Source, FName Name, FVector Location, float Volume, ESOSoundRange Range, float PitchJitter = 0.04f);
};
