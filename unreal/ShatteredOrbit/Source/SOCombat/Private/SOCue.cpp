#include "SOCue.h"

#include "Engine/World.h"

int32 ASOCueRelay::NumReceived = 0;

ASOCueRelay::ASOCueRelay()
{
	bReplicates = true;
	bAlwaysRelevant = true;
	SetNetUpdateFrequency(1.0f); // it has no state: only its calls travel
}

void ASOCueRelay::MulticastSound_Implementation(FName Name, FVector_NetQuantize Location, float Volume, float PitchJitter, ESOSoundRange Range)
{
	++NumReceived;
	USOSoundLibrary::PlayAt(this, Name, Location, Volume, PitchJitter, Range);
}

void ASOCueRelay::MulticastBlast_Implementation(FVector_NetQuantize Point, FVector_NetQuantizeNormal Normal, float Radius, uint8 Kind, FLinearColor Color, float Delay)
{
	++NumReceived;
	if (USOFxSubsystem* Fx = GetWorld() ? GetWorld()->GetSubsystem<USOFxSubsystem>() : nullptr)
	{
		Fx->Blast(Point, Normal, Radius, static_cast<USOFxSubsystem::EBlast>(Kind), Color, Delay);
	}
}

void ASOCueRelay::MulticastWarn_Implementation(FVector_NetQuantize Point, float Radius, float HalfAngle, float Yaw, float Time, FLinearColor Color)
{
	++NumReceived;
	if (USOFxSubsystem* Fx = GetWorld() ? GetWorld()->GetSubsystem<USOFxSubsystem>() : nullptr)
	{
		Fx->Warn(Point, Radius, HalfAngle, Yaw, Time, Color);
	}
}

ASOCueRelay* USOCueSubsystem::GetRelay()
{
	UWorld* World = GetWorld();
	if (!Relay && World && World->GetNetMode() != NM_Client && !World->bIsTearingDown)
	{
		FActorSpawnParameters Params;
		Params.ObjectFlags |= RF_Transient;
		Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
		Relay = World->SpawnActor<ASOCueRelay>(Params);
	}
	return Relay;
}

void USOCue::Sound(const UObject* WorldContext, FName Name, const FVector& Location, float Volume, float PitchJitter, ESOSoundRange Range)
{
	UWorld* World = WorldContext ? WorldContext->GetWorld() : nullptr;
	if (!World || World->GetNetMode() == NM_Client)
	{
		return; // a joined player's machine: the server's call arrives
	}
	if (World->GetNetMode() == NM_Standalone)
	{
		USOSoundLibrary::PlayAt(WorldContext, Name, Location, Volume, PitchJitter, Range);
		return;
	}
	USOCueSubsystem* Cues = World->GetSubsystem<USOCueSubsystem>();
	if (ASOCueRelay* Relay = Cues ? Cues->GetRelay() : nullptr)
	{
		Relay->MulticastSound(Name, Location, Volume, PitchJitter, Range);
	}
}

void USOCue::Blast(const UObject* WorldContext, const FVector& Point, const FVector& Normal, float Radius, USOFxSubsystem::EBlast Kind,
	const FLinearColor& Color, float Delay)
{
	UWorld* World = WorldContext ? WorldContext->GetWorld() : nullptr;
	if (!World || World->GetNetMode() == NM_Client)
	{
		return;
	}
	if (World->GetNetMode() == NM_Standalone)
	{
		if (USOFxSubsystem* Fx = World->GetSubsystem<USOFxSubsystem>())
		{
			Fx->Blast(Point, Normal, Radius, Kind, Color, Delay);
		}
		return;
	}
	USOCueSubsystem* Cues = World->GetSubsystem<USOCueSubsystem>();
	if (ASOCueRelay* Relay = Cues ? Cues->GetRelay() : nullptr)
	{
		Relay->MulticastBlast(Point, Normal.GetSafeNormal(UE_SMALL_NUMBER, FVector::UpVector), Radius, static_cast<uint8>(Kind), Color, Delay);
	}
}

void USOCue::Warn(const UObject* WorldContext, const FVector& Point, float Radius, float HalfAngle, float Yaw, float Time, const FLinearColor& Color)
{
	UWorld* World = WorldContext ? WorldContext->GetWorld() : nullptr;
	if (!World || World->GetNetMode() == NM_Client)
	{
		return;
	}
	if (World->GetNetMode() == NM_Standalone)
	{
		if (USOFxSubsystem* Fx = World->GetSubsystem<USOFxSubsystem>())
		{
			Fx->Warn(Point, Radius, HalfAngle, Yaw, Time, Color);
		}
		return;
	}
	USOCueSubsystem* Cues = World->GetSubsystem<USOCueSubsystem>();
	if (ASOCueRelay* Relay = Cues ? Cues->GetRelay() : nullptr)
	{
		Relay->MulticastWarn(Point, Radius, HalfAngle, Yaw, Time, Color);
	}
}

void ASOCueRelay::MulticastAimLine_Implementation(AActor* Shooter, FVector_NetQuantize Offset, AActor* Target, float Time, float Lock, FLinearColor Color)
{
	++NumReceived;
	USOFxSubsystem* Fx = GetWorld() ? GetWorld()->GetSubsystem<USOFxSubsystem>() : nullptr;
	if (Fx && Shooter && Target)
	{
		Fx->AimLine(Shooter, Offset, Target, Time, Lock, Color);
	}
}

void ASOCueRelay::MulticastTracer_Implementation(FVector_NetQuantize From, FVector_NetQuantize To, float Speed, FLinearColor Color, float Width, float Length, bool bBolt)
{
	++NumReceived;
	if (USOFxSubsystem* Fx = GetWorld() ? GetWorld()->GetSubsystem<USOFxSubsystem>() : nullptr)
	{
		Fx->Tracer(From, To, Speed, Color, Width, Length, bBolt);
	}
}

void USOCue::AimLine(const UObject* WorldContext, AActor* Shooter, const FVector& Offset, AActor* Target, float Time, float Lock, const FLinearColor& Color)
{
	UWorld* World = WorldContext ? WorldContext->GetWorld() : nullptr;
	if (!World || World->GetNetMode() == NM_Client || !Shooter || !Target)
	{
		return;
	}
	if (World->GetNetMode() == NM_Standalone)
	{
		if (USOFxSubsystem* Fx = World->GetSubsystem<USOFxSubsystem>())
		{
			Fx->AimLine(Shooter, Offset, Target, Time, Lock, Color);
		}
		return;
	}
	USOCueSubsystem* Cues = World->GetSubsystem<USOCueSubsystem>();
	if (ASOCueRelay* Relay = Cues ? Cues->GetRelay() : nullptr)
	{
		Relay->MulticastAimLine(Shooter, Offset, Target, Time, Lock, Color);
	}
}

void USOCue::Tracer(const UObject* WorldContext, const FVector& From, const FVector& To, float Speed, const FLinearColor& Color, float Width, float Length, bool bBolt)
{
	UWorld* World = WorldContext ? WorldContext->GetWorld() : nullptr;
	if (!World || World->GetNetMode() == NM_Client)
	{
		return;
	}
	if (World->GetNetMode() == NM_Standalone)
	{
		if (USOFxSubsystem* Fx = World->GetSubsystem<USOFxSubsystem>())
		{
			Fx->Tracer(From, To, Speed, Color, Width, Length, bBolt);
		}
		return;
	}
	USOCueSubsystem* Cues = World->GetSubsystem<USOCueSubsystem>();
	if (ASOCueRelay* Relay = Cues ? Cues->GetRelay() : nullptr)
	{
		Relay->MulticastTracer(From, To, Speed, Color, Width, Length, bBolt);
	}
}
