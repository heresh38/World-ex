#pragma once

#include "CoreMinimal.h"
#include "SOCombatCharacter.h"
#include "SOWardrobe.h"
#include "SOCharacter.generated.h"

class UAnimSequenceBase;
class UCameraComponent;
class USOViewmodelComponent;
class USOWeaponData;
class UInputAction;
class USkeletalMeshComponent;
class USOCharacterMovementComponent;
class USOLookComponent;
class USpringArmComponent;
class USOInventoryComponent;
struct FInputActionValue;

UENUM(BlueprintType)
enum class ESOViewMode : uint8
{
	FirstPerson,
	ThirdPerson
};

/**
 * The player character. First person by default: the eye at ~165 cm, and an arms-only copy of the player's own body
 * rendered with the camera's first-person FOV (the full body is hidden from the owner but still casts the shadow), so
 * the hands you see are the same hands everyone else sees. T toggles a third-person spring-arm camera with collision.
 * The gun is held by USOViewmodelComponent (a first-person and a third-person hold) and both bodies reach for its grips
 * with arm IK; aims down sights (zoom from the weapon); plays the Blender body's clips through USOLocomotionAnimInstance.
 */
UCLASS(config = Game)
class SOCHARACTER_API ASOCharacter : public ASOCombatCharacter
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

	/** 0..1 aim-down-sights progress (rate from the weapon's AdsTime). */
	UFUNCTION(BlueprintPure, Category = "SO|Combat")
	float GetAimProgress() const { return AimProgress; }

	// --- Content (loaded at spawn if present; created by Content/Python/import_assets.py) ---
	UPROPERTY(EditDefaultsOnly, Category = "SO|Content")
	TSoftObjectPtr<USkeletalMesh> BodyMesh;

	/** First-person arms: the body's own sleeves and gloves on the body's skeleton (export_fbx.py --arms-only). Without
	 *  it the first-person copy uses the whole body with everything but the arms collapsed. */
	UPROPERTY(EditDefaultsOnly, Category = "SO|Content")
	TSoftObjectPtr<USkeletalMesh> ArmsMesh;

	/** Folder + prefix of the body clips: <prefix>Idle, <prefix>Walk, ... */
	UPROPERTY(EditDefaultsOnly, Category = "SO|Content")
	FString ClipPathPrefix = TEXT("/Game/Characters/PlayerMale/Anims/A_PlayerMale_");

	UPROPERTY(EditDefaultsOnly, Category = "SO|Content")
	TSoftObjectPtr<USOWeaponData> DefaultWeapon;

	/** Firing-hand bone (Blender hand.R; dots become underscores on import). The gun is held by the hold components
	 *  and this hand reaches for its grip with IK. */
	UPROPERTY(EditDefaultsOnly, Category = "SO|Content")
	FName WeaponSocket = TEXT("hand_R");

	/** Recoil (weapons.js / player.js): each shot adds to a kick that decays RecoilRecovery per second; the view and
	 *  the rounds tilt up by kick * RecoilRadians and come back down by themselves. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Combat")
	float RecoilRadians = 0.03f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Combat")
	float RecoilRecovery = 6.0f;

	/** Current recoil pitch in degrees (view and aim). */
	float GetRecoilPitch() const { return FMath::RadiansToDegrees(RecoilKick * RecoilRadians); }

	USOViewmodelComponent* GetViewmodel() const { return Viewmodel; }
	USceneComponent* GetThirdPersonHold() const { return ThirdPersonHold; }

	/** The eye: camera eye position with the aim rotation (control rotation, or the replicated view for others),
	 *  optionally with the recoil kick the camera shows. */
	FTransform GetEyeTransform(bool bWithRecoil) const;

	/** Where the player looks, without recoil: the control rotation (or the replicated view for others). */
	FRotator GetAimRotation() const;

	//~ ASOCombatCharacter
	virtual FVector GetAimOrigin() const override;
	virtual FVector GetAimDirection() const override;
	virtual bool CanFireWeapon() const override;
	virtual bool IsAimingDownSights() const override { return bAiming; }
	virtual float GetSpreadScale() const override;
	virtual USceneComponent* GetFirstPersonWeaponParent() const override;
	virtual USceneComponent* GetThirdPersonWeaponParent() const override { return ThirdPersonHold; }
	virtual void OnWeaponFired(float Kick) override;
	virtual FVector ViewmodelToWorld(const FVector& ViewmodelPoint) const override;
	virtual bool IsFirstPersonView() const override;

	/** Eye height above the feet when standing / crouched (cm). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Camera")
	float StandingEyeHeight = 165.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Camera")
	float CrouchEyeHeight = 100.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Camera")
	float EyeHeightInterpSpeed = 14.0f;

	/** Aim-down-sights field of view as a fraction of the hip field of view. */
	/** Aim zoom when no weapon is held (the weapon's AimZoom wins otherwise). */
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
	UPROPERTY(EditDefaultsOnly, Category = "SO|Input")
	TSoftObjectPtr<UInputAction> Weapon1Action;
	UPROPERTY(EditDefaultsOnly, Category = "SO|Input")
	TSoftObjectPtr<UInputAction> Weapon2Action;
	UPROPERTY(EditDefaultsOnly, Category = "SO|Input")
	TSoftObjectPtr<UInputAction> Weapon3Action;
	UPROPERTY(EditDefaultsOnly, Category = "SO|Input")
	TSoftObjectPtr<UInputAction> NextWeaponAction;
	UPROPERTY(EditDefaultsOnly, Category = "SO|Input")
	TSoftObjectPtr<UInputAction> PrevWeaponAction;
	UPROPERTY(EditDefaultsOnly, Category = "SO|Input")
	TSoftObjectPtr<UInputAction> InventoryAction;
	UPROPERTY(EditDefaultsOnly, Category = "SO|Input")
	TSoftObjectPtr<UInputAction> MapAction;

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
	void HandleWeapon1();
	void HandleWeapon2();
	void HandleWeapon3();
	void HandleNextWeapon();
	void HandlePrevWeapon();
	void HandleInventory();
	void HandleMap();

	/** Quick travel to a map point (an actor tagged SOFastTravel; the server moves the pawn beside it). */
	void FastTravel(AActor* Point);
	/** Travel to another area (level), e.g. /Game/Maps/L_Nexus (the server / standalone game opens it). */
	void TravelToArea(const FString& Level);

	UFUNCTION(Server, Reliable)
	void ServerFastTravel(AActor* Point);

	UFUNCTION(Server, Reliable)
	void ServerTravelToArea(const FString& Level);

	/** The HUD opens / closes the map screen. */
	TFunction<void()> ToggleMapScreen;

	/** The owning player's vault + loadout (on the player state); null without one (tests, AI). */
	USOInventoryComponent* GetInventory() const;

	/** Server: follow the player state's inventory (loadout changes re-equip) and hold its active copy. */
	void BindInventory();

	/** Server: hold the copy the inventory has in the active slot (stores the current one's ammo first). */
	void EquipFromInventory();

	/** Fully aimed through magnified glass: the scope picture replaces the gun (HUD draws it). */
	bool IsScopeView() const { return bScopeView; }

	/** The interactable in reach that Interact would use (nearest one in front), or null. */
	AActor* FindInteractable() const;

	UFUNCTION(Server, Reliable)
	void ServerInteract(AActor* Target);

	/** Opens / closes the inventory screen (set by the HUD). */
	TFunction<void()> ToggleInventoryScreen;

	//~ ACharacter
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;
	virtual void SetupPlayerInputComponent(UInputComponent* PlayerInputComponent) override;
	virtual void Landed(const FHitResult& Hit) override;
	virtual void OnStartCrouch(float HalfHeightAdjust, float ScaledHalfHeightAdjust) override;
	virtual void OnEndCrouch(float HalfHeightAdjust, float ScaledHalfHeightAdjust) override;
	virtual bool CanJumpInternal_Implementation() const override;
	virtual bool CanJumpWhileFalling() const override;
	virtual void PostInitializeComponents() override;
	virtual void PossessedBy(AController* NewController) override;
	virtual void UnPossessed() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
	virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;

protected:
	virtual void HandleDeath() override;
	void LoadContent();
	void LoadBody(USkeletalMeshComponent* Body);
	virtual void OnWeaponEquipped() override;
	void SelectSlot(int32 Slot);
	void CycleSlot(int32 Step);
	void StoreWeaponAmmo();
	FDelegateHandle LoadoutHandle;
	TWeakObjectPtr<USOInventoryComponent> BoundInventory;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "SO|Camera")
	TObjectPtr<UCameraComponent> FirstPersonCamera;

	/** First person: a copy of the body seen only by its owner, posed like the body but with everything except the
	 *  arms collapsed (first-person rendering: own FOV, never clips into walls, no shadow). */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "SO|Camera")
	TObjectPtr<USkeletalMeshComponent> FirstPersonArms;

	/** Third-person hold: the gun's place as seen from outside (set every frame by the viewmodel component). */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "SO|Camera")
	TObjectPtr<USceneComponent> ThirdPersonHold;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "SO|Camera")
	TObjectPtr<USpringArmComponent> ThirdPersonBoom;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "SO|Camera")
	TObjectPtr<UCameraComponent> ThirdPersonCamera;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "SO|Look")
	TObjectPtr<USOLookComponent> Look;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "SO|Camera")
	TObjectPtr<USOViewmodelComponent> Viewmodel;

	/** Replicated so the server aims third-person shots at the crosshair the owner sees. */
	UPROPERTY(Replicated, Transient, BlueprintReadOnly, Category = "SO|Camera")
	ESOViewMode ViewMode = ESOViewMode::FirstPerson;

public:
	/** Dresses the character (server; replicated): the body and one wardrobe piece per slot. */
	void SetOutfit(const FSOOutfit& NewOutfit);
	const FSOOutfit& GetOutfit() const { return Outfit; }
	/** The worn piece of a slot (third-person body or first-person arms), null if none shows. */
	USkeletalMeshComponent* GetWornPiece(FName Slot, bool bFirstPerson) const;
	/** Body regions the worn pieces cover (their skin sections are hidden). */
	const TSet<FName>& GetHiddenRegions() const { return HiddenRegions; }

protected:
	/** Every piece is a skeletal mesh following the body's pose (leader pose), in both views. */
	UPROPERTY(ReplicatedUsing = OnRep_Outfit)
	FSOOutfit Outfit;

	UFUNCTION()
	void OnRep_Outfit();
	void ApplyOutfit();
	void OutfitFromInventory();
	FDelegateHandle OutfitHandle;
	FName AppliedBody;
	TSet<FName> HiddenRegions;

	UPROPERTY(Transient)
	TMap<FName, TObjectPtr<USkeletalMeshComponent>> WornThirdPerson;

	UPROPERTY(Transient)
	TMap<FName, TObjectPtr<USkeletalMeshComponent>> WornFirstPerson;

	UFUNCTION(Server, Reliable)
	void ServerSetViewMode(ESOViewMode NewMode);

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
	float AimProgress = 0.0f;
	float RecoilKick = 0.0f;
	float StepDistance = 0.0f;
	float LastHealthSeen = -1.0f;
	float LastShieldSeen = -1.0f;
	float LastHurtSound = -100.0f;
	bool bShieldRecharging = false;
	void UpdateFeedbackSounds(float DeltaSeconds);
	float LastSprintTime = -100.0f;
	bool bScopeView = false;
	bool bCrouchLatched = false;
};
