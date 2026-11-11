#pragma once

#include "CoreMinimal.h"
#include "SOCombatCharacter.h"
#include "SOWardrobe.h"
#include "SOCharacter.generated.h"

class USpotLightComponent;

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
enum class ESOMovementEvent : uint8;

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

	/** The point the crosshair is on: third person, what the shoulder camera's centre ray hits; first person (and
	 *  looking through a scope), straight along the kicked view. */
	FVector GetAimTarget() const;

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

	// --- First-person camera feel (local player, first person only; the third-person boom has its own lag) ---
	/** Head bob in step with the footsteps (0 = off). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Camera")
	float HeadBobScale = 1.0f;

	/** Extra field of view while sprinting / sliding (degrees, eased in and out). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Camera")
	float SprintFovBoost = 5.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Camera")
	float SlideFovBoost = 8.0f;

	/** The view tilts this many degrees into a slide, and a little toward a strafe. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Camera")
	float SlideCameraRoll = 3.5f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Camera")
	float StrafeCameraRoll = 0.7f;

	/** Current camera dip (cm, negative = down) from landings and jumps; the viewmodel lags it a little. */
	float GetLandDip() const { return LandDip; }

	/** Roll of the eye while vaulting (degrees). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Camera")
	float VaultCameraRoll = 2.5f;

	/** What the feet are on: concrete (the default), metal, dirt, grass, wood or water. From the floor's physical
	 *  material when it has one, else from the names of its material and mesh (material names are an API). */
	FName GetFloorSurface() const;

	/** The footstep / landing sound for a surface (the surface's own set when it exists, else the plain one). */
	static FName SurfaceSound(FName Surface, const TCHAR* Kind, int32 Takes);
	float GetCameraRoll() const { return CameraRoll; }

	/** Aim-down-sights field of view as a fraction of the hip field of view. */
	/** Aim zoom when no weapon is held (the weapon's AimZoom wins otherwise). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Camera")
	float AimFovScale = 0.8f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Camera")
	float FovInterpSpeed = 16.0f;

	/** Third person, fully aimed: the shoulder camera comes in to this arm length and offset (hip: 320 / 0,55,15). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Camera")
	float HipArmLength = 320.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Camera")
	FVector HipSocketOffset = FVector(0.0f, 55.0f, 15.0f);

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Camera")
	float AimArmLength = 175.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Camera")
	FVector AimSocketOffset = FVector(0.0f, 52.0f, 8.0f);

	/** Third person zooms at most this much while aiming (a magnified optic zooms at the eye, in the scope view). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Camera")
	float ThirdPersonMaxZoom = 1.35f;

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

	UPROPERTY(EditDefaultsOnly, Category = "SO|Input")
	TSoftObjectPtr<UInputAction> FlashlightAction;

	/** The flashlight (F): on or off at any time. Creatures see a lit light from farther and from any side. */
	UFUNCTION(BlueprintCallable, Category = "SO|Flashlight")
	void SetFlashlight(bool bOn);

	UFUNCTION(BlueprintPure, Category = "SO|Flashlight")
	bool IsFlashlightOn() const { return bFlashlightOn; }

	USpotLightComponent* GetFlashlight() const { return Flashlight; }

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
	void HandleFlashlight();

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

	/** The equipped guns that are not in the hands, worn where the body carries them, each in a place of its own
	 *  (sized from the gun, so two never overlap): long guns stand on the back side by side, one behind each
	 *  shoulder; handguns hang at the hips. Always there in third person; they follow the loadout and change
	 *  places with the gun in hand. Cheap when nothing changed. */
	void RefreshHolsters();

	/** The gun in hand is in its holster and the hands are free: while vaulting, mantling or climbing. */
	bool IsWeaponStowed() const { return bHeldStowed; }

	/** The worn gun of an equipped slot (null: that slot is empty or in the hands). */
	class USOGunRigComponent* GetHolsteredRig(int32 Slot) const { return HolsterRigs.IsValidIndex(Slot) ? HolsterRigs[Slot].Get() : nullptr; }

	/** Where an equipped slot's gun is worn: back_right, back_left, back_across, hip_right, hip_left, belt_back
	 *  (None: not worn). */
	FName GetHolsterPlace(int32 Slot) const { return HolsterPlaces.IsValidIndex(Slot) ? HolsterPlaces[Slot] : FName(); }

	/** The clothed body's surface behind the chest joint and beside the hip joint (cm; X = his, Y = hers): what the
	 *  worn guns rest on. */
	UPROPERTY(EditDefaultsOnly, Category = "SO|Weapon")
	FVector2D HolsterBackDepth = FVector2D(11.5f, 10.0f);

	/** What a worn coat or jacket adds behind the back (cm). */
	UPROPERTY(EditDefaultsOnly, Category = "SO|Weapon")
	float HolsterCoat = 3.0f;

	UPROPERTY(EditDefaultsOnly, Category = "SO|Weapon")
	FVector2D HolsterHipSide = FVector2D(9.5f, 9.5f);

	/** Fully aimed through magnified glass (either view; third person cuts to the eye): the scope picture replaces
	 *  the gun (HUD draws it). */
	bool IsScopeView() const { return bScopeView; }

	/** The crosshair is the shoulder camera's centre (third person, not looking through a scope). */
	bool UsesShoulderCrosshair() const;

	/** The hip field of view (the player's setting, degrees). */
	float GetHipFov() const;

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
	/** Walked into something: if it is a level's unseen net (an actor tagged SONet, behind the real barriers), say where:
	 * nobody should ever reach it, so every touch is a way out of the map that needs closing. */
	virtual void MoveBlockedBy(const FHitResult& Impact) override;
	double LastNetReport = -100.0;
	virtual void OnJumped_Implementation() override;
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

	UPROPERTY(Transient)
	TArray<TObjectPtr<class USOGunRigComponent>> HolsterRigs;
	TArray<FString> HolsterUids;
	TArray<FName> HolsterPlaces;
	float HolsterTimer = 0.0f;
	bool bHeldStowed = false;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "SO|Camera")
	TObjectPtr<UCameraComponent> FirstPersonCamera;

	/** A lamp on the chest, pointing where the player looks (placed every frame). */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "SO|Flashlight")
	TObjectPtr<USpotLightComponent> Flashlight;

	UPROPERTY(ReplicatedUsing = OnRep_Flashlight)
	bool bFlashlightOn = false;

	UFUNCTION()
	void OnRep_Flashlight();

	UFUNCTION(Server, Reliable)
	void ServerSetFlashlight(bool bOn);

	/** Feet on the ground make noise the creatures hear: running loud, walking soft, crouching none. */
	void TickFootstepNoise(float DeltaSeconds);
	float FootstepTimer = 0.0f;

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
	float GetTargetEyeOffset() const;

	/** Eye position relative to the capsule centre (interpolated across crouch changes). */
	float EyeOffset = 0.0f;

	/** First-person camera feel: step smoothing, landing spring, head bob, roll, field-of-view boost. */
	void UpdateCameraFeel(float DeltaSeconds);
	/** Sound, camera and effects for the movement component's one-off events (jump, land, slide, vault, ...). */
	void HandleMovementEvent(ESOMovementEvent Event, float Strength);
	/** A few puffs of dust at the feet (landings, slides, air jumps). */
	void KickDust(float Strength, const FVector& Along);
	float StepSmooth = 0.0f;      // cm: hides the capsule popping up / down steps
	double LastFeelZ = 0.0;
	bool bHaveFeelZ = false;
	float LandDip = 0.0f;         // cm, spring
	float LandDipVel = 0.0f;
	float LastAirVz = 0.0f;
	float BobPhase = 0.0f;
	float BobAmp = 0.0f;
	float CameraRoll = 0.0f;
	float FovBoost = 0.0f;
	FVector FeelOffset = FVector::ZeroVector;
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
