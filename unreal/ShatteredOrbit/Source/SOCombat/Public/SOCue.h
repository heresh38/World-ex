#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Info.h"
#include "Subsystems/WorldSubsystem.h"
#include "SOFxSubsystem.h"
#include "SOSound.h"
#include "SOCue.generated.h"

/**
 * A sound or an effect that everyone should get, called from code that runs on the server (a creature's voice, a
 * boss's slam, a blink, a bolt bursting). USOSoundLibrary::PlayAt and USOFxSubsystem::Blast only play on the machine
 * that calls them, so called on the server alone they never reached a joined player.
 *
 * USOCue::Sound / USOCue::Blast do the right thing wherever they are called:
 *  - alone (standalone): play here;
 *  - on a server: sent to every machine through the world's relay (and played on a listen server's own screen);
 *  - on a joined player's machine: nothing, the server's call arrives.
 * So code that runs on every machine may call them too: each machine still gets it exactly once.
 * Unreliable: a lost voice line is not worth a resend.
 */
UCLASS()
class SOCOMBAT_API ASOCueRelay : public AInfo
{
	GENERATED_BODY()

public:
	ASOCueRelay();

	UFUNCTION(NetMulticast, Unreliable)
	void MulticastSound(FName Name, FVector_NetQuantize Location, float Volume, float PitchJitter, ESOSoundRange Range);

	/** How many cues this machine has been sent (the two-player check reads it on the guest). */
	static int32 NumReceived;

	UFUNCTION(NetMulticast, Unreliable)
	void MulticastBlast(FVector_NetQuantize Point, FVector_NetQuantizeNormal Normal, float Radius, uint8 Kind, FLinearColor Color, float Delay);

	/** (Reliable: a warning that does not arrive is a blow nobody could have seen coming.) */
	UFUNCTION(NetMulticast, Reliable)
	void MulticastWarn(FVector_NetQuantize Point, float Radius, float HalfAngle, float Yaw, float Time, FLinearColor Color);

	/** (Reliable for the same reason: the line is the warning of the shot.) */
	UFUNCTION(NetMulticast, Reliable)
	void MulticastAimLine(AActor* Shooter, FVector_NetQuantize Offset, AActor* Target, float Time, float Lock, FLinearColor Color);

	UFUNCTION(NetMulticast, Unreliable)
	void MulticastTracer(FVector_NetQuantize From, FVector_NetQuantize To, float Speed, FLinearColor Color, float Width, float Length, bool bBolt);
};

/** Holds the world's relay (made by the server the first time something is cued). */
UCLASS()
class SOCOMBAT_API USOCueSubsystem : public UWorldSubsystem
{
	GENERATED_BODY()

public:
	ASOCueRelay* GetRelay();

private:
	UPROPERTY(Transient)
	TObjectPtr<ASOCueRelay> Relay;
};

struct SOCOMBAT_API USOCue
{
	static void Sound(const UObject* WorldContext, FName Name, const FVector& Location, float Volume = 1.0f, float PitchJitter = 0.04f,
		ESOSoundRange Range = ESOSoundRange::Near);

	static void Blast(const UObject* WorldContext, const FVector& Point, const FVector& Normal, float Radius, USOFxSubsystem::EBlast Kind,
		const FLinearColor& Color, float Delay = 0.0f);

	/** A warning on the ground at a place the server chose (USOFxSubsystem::Warn), on every machine. A warning that
	 *  goes with an ability's own wind-up needs no cue: the ability's Telegraph already runs everywhere. */
	static void Warn(const UObject* WorldContext, const FVector& Point, float Radius, float HalfAngle, float Yaw, float Time, const FLinearColor& Color);

	/** A line of sight from Shooter (Offset in its own space) to Target for Time seconds (USOFxSubsystem::AimLine),
	 *  on every machine. Who a creature aims at is known to the server alone, so its ability's Telegraph cannot
	 *  draw this by itself on a joined player's machine. */
	static void AimLine(const UObject* WorldContext, AActor* Shooter, const FVector& Offset, AActor* Target, float Time, float Lock, const FLinearColor& Color);

	/** A tracer for a round the server fired by hand (not from a gun, which shows its own), on every machine. */
	static void Tracer(const UObject* WorldContext, const FVector& From, const FVector& To, float Speed, const FLinearColor& Color, float Width = 2.2f,
		float Length = 380.0f, bool bBolt = false);
};
