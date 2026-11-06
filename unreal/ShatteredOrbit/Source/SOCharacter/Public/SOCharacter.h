#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "SOCharacter.generated.h"

class UCameraComponent;
class UInputAction;
class USkeletalMeshComponent;
class USOCharacterMovementComponent;
class USOLookComponent;
class USpringArmComponent;
struct FInputActionValue;

UENUM(BlueprintType)
enum class ESOViewMode : uint8
{
	FirstPerson,
	ThirdPerson
};

/**
 * The player character. First person by default (eye at ~165 cm, arms mesh rendered with the camera's
 * first-person FOV, body hidden from the owner but still casting shadows); T toggles a third-person
 * spring-arm camera with collision.
 */
UCLASS(config = Game)
class SOCHARACTER_API ASOCharacter : public ACharacter
{
	GENERATED_BODY()

public:
	ASOCharacter(const FObjectInitializer& ObjectInitializer);

	UFUNCTION(BlueprintPure, Category = "SO|Character")
	USOCharacterMovementComponent* GetSOMovement() const;

	UFUNCTION(BlueprintCallable, Category = "SO|Camera")
	void SetViewMode(ESOViewMode NewMode);

	UFUNCTION(BlueprintCallable, Category = "SO|Camera")
	void ToggleViewMode();

	UFUNCTION(BlueprintPure, Category = "SO|Camera")
	ESOViewMode GetViewMode() const { return ViewMode; }

	UFUNCTION(BlueprintPure, Category = "SO|Combat")
	bool IsAiming() const { return bAiming; }

	/** Eye height above the feet when standing / crouched (cm). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Camera")
	float StandingEyeHeight = 165.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Camera")
	float CrouchEyeHeight = 100.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Camera")
	float EyeHeightInterpSpeed = 14.0f;

	/** Aim-down-sights field of view as a fraction of the hip field of view. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Camera")
	float AimFovScale = 0.8f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Camera")
	float FovInterpSpeed = 16.0f;

	/** Field of view of the first-person arms / gun (independent of the world FOV). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Camera")
	float ViewmodelFov = 74.0f;

	/** A tap shorter than this latches sprint / crouch (toggle); holding longer releases on key up. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Input")
	float TapToToggleTime = 0.22f;

	// --- Input actions (created by Content/Python/setup_input.py) ---
	UPROPERTY(EditDefaultsOnly, Category = "SO|Input")
	TSoftObjectPtr<UInputAction> MoveAction;
	UPROPERTY(EditDefaultsOnly, Category = "SO|Input")
	TSoftObjectPtr<UInputAction> LookAction;
	UPROPERTY(EditDefaultsOnly, Category = "SO|Input")
	TSoftObjectPtr<UInputAction> LookGamepadAction;
	UPROPERTY(EditDefaultsOnly, Category = "SO|Input")
	TSoftObjectPtr<UInputAction> JumpAction;
	UPROPERTY(EditDefaultsOnly, Category = "SO|Input")
	TSoftObjectPtr<UInputAction> SprintAction;
	UPROPERTY(EditDefaultsOnly, Category = "SO|Input")
	TSoftObjectPtr<UInputAction> CrouchAction;
	UPROPERTY(EditDefaultsOnly, Category = "SO|Input")
	TSoftObjectPtr<UInputAction> ToggleViewAction;
	UPROPERTY(EditDefaultsOnly, Category = "SO|Input")
	TSoftObjectPtr<UInputAction> InteractAction;
	UPROPERTY(EditDefaultsOnly, Category = "SO|Input")
	TSoftObjectPtr<UInputAction> FireAction;
	UPROPERTY(EditDefaultsOnly, Category = "SO|Input")
	TSoftObjectPtr<UInputAction> AimAction;
	UPROPERTY(EditDefaultsOnly, Category = "SO|Input")
	TSoftObjectPtr<UInputAction> ReloadAction;

	UCameraComponent* GetFirstPersonCamera() const { return FirstPersonCamera; }
	UCameraComponent* GetThirdPersonCamera() const { return ThirdPersonCamera; }
	USpringArmComponent* GetThirdPersonBoom() const { return ThirdPersonBoom; }
	USkeletalMeshComponent* GetFirstPersonArms() const { return FirstPersonArms; }
	USOLookComponent* GetLook() const { return Look; }

	// --- Input handlers (public so tests and the controller can drive them) ---
	void HandleMove(const FInputActionValue& Value);
	void HandleLook(const FInputActionValue& Value);
	void HandleLookGamepad(const FInputActionValue& Value);
	void HandleJumpPressed();
	void HandleJumpReleased();
	void HandleSprintPressed();
	void HandleSprintReleased();
	void HandleCrouchPressed();
	void HandleCrouchReleased();
	void HandleToggleView();
	void HandleInteract();
	void HandleFirePressed();
	void HandleFireReleased();
	void HandleAimPressed();
	void HandleAimReleased();
	void HandleReload();

	//~ ACharacter
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;
	virtual void SetupPlayerInputComponent(UInputComponent* PlayerInputComponent) override;
	virtual void Landed(const FHitResult& Hit) override;
	virtual void OnStartCrouch(float HalfHeightAdjust, float ScaledHalfHeightAdjust) override;
	virtual void OnEndCrouch(float HalfHeightAdjust, float ScaledHalfHeightAdjust) override;
	virtual bool CanJumpInternal_Implementation() const override;
	virtual bool CanJumpWhileFalling() const override;

protected:
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "SO|Camera")
	TObjectPtr<UCameraComponent> FirstPersonCamera;

	/** Placeholder for the Blender-built first-person arms (assigned once the FBX is imported). */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "SO|Camera")
	TObjectPtr<USkeletalMeshComponent> FirstPersonArms;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "SO|Camera")
	TObjectPtr<USpringArmComponent> ThirdPersonBoom;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "SO|Camera")
	TObjectPtr<UCameraComponent> ThirdPersonCamera;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "SO|Look")
	TObjectPtr<USOLookComponent> Look;

	UPROPERTY(Transient, BlueprintReadOnly, Category = "SO|Camera")
	ESOViewMode ViewMode = ESOViewMode::FirstPerson;

	UPROPERTY(Transient, BlueprintReadOnly, Category = "SO|Combat")
	bool bAiming = false;

private:
	void ApplyViewMode();
	float GetHipFov() const;
	float GetTargetEyeOffset() const;

	/** Eye position relative to the capsule centre (interpolated across crouch changes). */
	float EyeOffset = 0.0f;
	float CurrentFov = 90.0f;

	float BufferedJumpTime = -1.0f;
	float SprintPressTime = -1.0f;
	float CrouchPressTime = -1.0f;
	bool bSprintLatched = false;
	bool bCrouchLatched = false;
};
