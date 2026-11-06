#include "SOLookComponent.h"

#include "GameFramework/Controller.h"
#include "GameFramework/Pawn.h"
#include "SOGameUserSettings.h"

USOLookComponent::USOLookComponent()
{
	PrimaryComponentTick.bCanEverTick = true;
	PrimaryComponentTick.TickGroup = TG_PrePhysics;
}

void USOLookComponent::BeginPlay()
{
	Super::BeginPlay();
	LoadFromSettings();
	if (USOGameUserSettings* Settings = USOGameUserSettings::Get())
	{
		SettingsHandle = Settings->OnLookSettingsChanged.AddUObject(this, &USOLookComponent::LoadFromSettings);
	}
}

void USOLookComponent::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	if (USOGameUserSettings* Settings = USOGameUserSettings::Get())
	{
		Settings->OnLookSettingsChanged.Remove(SettingsHandle);
	}
	Super::EndPlay(EndPlayReason);
}

void USOLookComponent::LoadFromSettings()
{
	if (const USOGameUserSettings* Settings = USOGameUserSettings::Get())
	{
		MouseSensitivity = Settings->MouseSensitivity;
		AimSensitivityMultiplier = Settings->AimSensitivityMultiplier;
		GamepadSensitivity = Settings->GamepadSensitivity;
		GamepadResponseExponent = Settings->GamepadResponseExponent;
		AimSmoothing = Settings->AimSmoothing;
		bInvertPitch = Settings->bInvertPitch;
	}
}

void USOLookComponent::AddMouseInput(const FVector2D& Counts)
{
	PendingMouseCounts += Counts;
}

void USOLookComponent::AddGamepadInput(const FVector2D& Stick)
{
	PendingStick = Stick;
}

void USOLookComponent::SetAim(bool bInAiming, float InHipFov, float InAimFov)
{
	bAiming = bInAiming;
	HipFov = InHipFov;
	AimFov = InAimFov;
}

float USOLookComponent::ZoomScale(float HipFovDeg, float ZoomFovDeg)
{
	const float HipHalf = FMath::DegreesToRadians(FMath::Clamp(HipFovDeg, 1.0f, 170.0f) * 0.5f);
	const float ZoomHalf = FMath::DegreesToRadians(FMath::Clamp(ZoomFovDeg, 1.0f, 170.0f) * 0.5f);
	return FMath::Tan(ZoomHalf) / FMath::Tan(HipHalf);
}

FVector2D USOLookComponent::ApplyResponseCurve(const FVector2D& Stick, float Exponent)
{
	const float Magnitude = FMath::Min(Stick.Size(), 1.0f);
	if (Magnitude <= KINDA_SMALL_NUMBER)
	{
		return FVector2D::ZeroVector;
	}
	const float Curved = FMath::Pow(Magnitude, FMath::Max(Exponent, 0.1f));
	return Stick.GetSafeNormal() * Curved;
}

float USOLookComponent::GetCurrentSensitivityScale() const
{
	if (!bAiming)
	{
		return 1.0f;
	}
	const float Zoom = bZoomMatchedAim ? ZoomScale(HipFov, AimFov) : 1.0f;
	return AimSensitivityMultiplier * Zoom;
}

FVector2D USOLookComponent::ConsumeLookDelta(float DeltaTime)
{
	const float Scale = GetCurrentSensitivityScale();

	// Degrees this frame from the mouse, degrees per second from the stick.
	const FVector2D MouseDegrees = PendingMouseCounts * MouseDegreesPerCount * MouseSensitivity * Scale;
	const FVector2D Curved = ApplyResponseCurve(PendingStick, GamepadResponseExponent);
	const FVector2D StickRate(Curved.X * GamepadYawRate * GamepadSensitivity * Scale, Curved.Y * GamepadPitchRate * GamepadSensitivity * Scale);
	PendingMouseCounts = FVector2D::ZeroVector;
	PendingStick = FVector2D::ZeroVector;

	if (DeltaTime <= 0.0f)
	{
		return MouseDegrees;
	}

	const FVector2D TargetRate = MouseDegrees / DeltaTime + StickRate;
	const float Tau = GetSmoothingTimeConstant();
	if (Tau <= 1e-4f)
	{
		SmoothedRate = TargetRate;
	}
	else
	{
		const float K = 1.0f - FMath::Exp(-DeltaTime / Tau);
		SmoothedRate += (TargetRate - SmoothedRate) * K;
	}

	FVector2D Delta = SmoothedRate * DeltaTime;
	if (bInvertPitch)
	{
		Delta.Y = -Delta.Y;
	}
	return Delta;
}

void USOLookComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);

	if (!bApplyToController)
	{
		return;
	}
	APawn* Pawn = Cast<APawn>(GetOwner());
	if (!Pawn || !Pawn->IsLocallyControlled())
	{
		return;
	}
	AController* Controller = Pawn->GetController();
	if (Controller && Controller != TickAfterController.Get())
	{
		// Tick after the controller so this frame's input (gathered in its tick) is applied this frame.
		AddTickPrerequisiteActor(Controller);
		TickAfterController = Controller;
	}
	const FVector2D Delta = ConsumeLookDelta(DeltaTime);
	if (!Controller || Delta.IsNearlyZero() || Controller->IsLookInputIgnored())
	{
		return;
	}
	// Written straight into the control rotation (not AddControllerYawInput, which the controller would only
	// apply next frame): the camera update later this frame already uses it. Positive pitch looks up.
	FRotator Rotation = Controller->GetControlRotation();
	Rotation.Yaw = FRotator::NormalizeAxis(Rotation.Yaw + Delta.X);
	Rotation.Pitch = FMath::ClampAngle(FRotator::NormalizeAxis(Rotation.Pitch) + Delta.Y, -MaxPitch, MaxPitch);
	Rotation.Roll = 0.0f;
	Controller->SetControlRotation(Rotation);
}
