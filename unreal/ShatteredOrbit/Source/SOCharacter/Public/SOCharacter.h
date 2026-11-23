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
 * The player character. The game is FIRST PERSON, always (the owner, 2026-11-23): ONE body holding ONE gun, seen from
 * its own eyes by ONE camera (its head hidden from that camera alone, on its own player's machine: everyone else sees
 * the whole body). T moves the same camera out behind the right shoulder: the third-person test view of how others see
 * the player. The gun is held by USOViewmodelComponent (where the body holds it; on the sights, its sight on the eyes'
 * line) and the body's arms reach for its grips with IK; aims down sights (zoom from the weapon); plays the Blender
 * body's clips through USOLocomotionAnimInstance.
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
	/** Where the gun is held (placed every frame by the viewmodel component; the gun rides it). */
	USceneComponent* GetGunHold() const { return GunHold; }

	/** The body's own eyes (where the camera sits in first person, and the shots start) with the aim rotation (control
	 *  rotation, or the replicated view for others), optionally with the recoil kick the camera shows. */
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
	virtual USceneComponent* GetWeaponParent() const override { return GunHold; }
	virtual void OnWeaponFired(float Kick) override;
	virtual bool IsFirstPersonView() const override;

	/** Eye height above the feet when standing / crouched (cm). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Camera")
	float StandingEyeHeight = 165.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Camera")
	float CrouchEyeHeight = 100.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Camera")
	float EyeHeightInterpSpeed = 14.0f;

	/** The camera's place from the head joint at rest (cm: forward, right, up in the body's facing), where the shots
	 *  start: the Orion male's eyeballs' middle is 8.6 ahead of the joint and 4.6 above it, the corneas 9.9 ahead, and
	 *  the camera sits 5 cm under them (the owner, 2026-11-23: "weapons are not very visible, i think the camera is too
	 *  high so lower it a bit maybe so we see more of the gun": at the ready a fifth more of the gun is in the picture),
	 *  inside the head its own camera does not see. On the sights a long gun's sight line takes it (SetSightEye). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Camera")
	FVector EyeFromHead = FVector(10.0f, 0.0f, -0.4f);

	/** How the camera follows the eyes (a spring, per second: the pose's jitter smoothed), and never further behind
	 *  them than EyeMaxLag (cm): a crouch, a slide, the cheek coming down onto the stock carry the eyes all the way. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Camera")
	float EyeFollow = 30.0f;
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Camera")
	float EyeMaxLag = 2.0f;

	/** On the move off the sights the camera rides the head's bob softer (the owner, 2026-11-23: "when in first person
	 *  not scoped and walking the guns shake too much so smooth the camera a bit more there"): this spring, and this far
	 *  behind the head at most (cm). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Camera")
	float EyeFollowMoving = 10.0f;
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Camera")
	float EyeMaxLagMoving = 5.0f;

	/** How long the camera takes to move between the eyes and the test view behind the shoulder (s). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Camera")
	float ViewSwitchTime = 0.35f;

	/** Where the camera is: 0 in the body's eyes (first person: the game), 1 behind the shoulder (the test view). */
	float GetViewBlend() const { return ViewBlend; }

	/** On the sights of a long gun the gun stays shouldered and the CAMERA alone goes to its sight's line (the owner,
	 *  2026-11-23: "Don't move the eyes since other players will be looking at us ... just move the camera"): the body's
	 *  head and eyes keep their own pose for everyone watching. USOViewmodelComponent sets where (the capsule's frame,
	 *  cm) and how far on the sights (0..1) each frame; the camera and the shots go there. */
	void SetSightEye(const FVector& InCapsuleFrame, float Alpha) { SightEyeCS = InCapsuleFrame; SightEyeAlpha = FMath::Clamp(Alpha, 0.0f, 1.0f); }
	float GetSightEye(FVector& OutCapsuleFrame) const { OutCapsuleFrame = SightEyeCS; return SightEyeAlpha; }
	/** The eyes' place on the head (the capsule's frame) before the camera goes to a sight (UpdateEye), and their steady
	 *  place without the head's own motion (the walk's bob): the eyes' height on the capsule, on its middle. */
	FVector GetHeadEyeCS() const { return EyeHeadCS; }
	FVector GetSteadyEyeCS() const { return FVector(EyeFromHead.X, EyeFromHead.Y, EyeOffset); }

	/** Its own player's camera is in this body's head (first person): the head is hidden from it, on this machine only,
	 *  and its shadow still falls (the owner, 2026-11-23). The head's own parts (its face, eyes, lashes) are cut out of
	 *  that camera's picture by their materials (the body's custom primitive data 0, OwnViewHide; import_assets
	 *  HEAD_PARTS), what is worn on the head (the hair, a helmet) is hidden from it casting its shadow; a body whose head
	 *  materials cannot (IsHeadHiddenByMaterial false: the female until her new body) has the head shrunk into its joint
	 *  by USOLocomotionAnimInstance, shadow and all. */
	bool IsHeadHidden() const;
	bool IsHeadHiddenByMaterial() const { return bHeadByMaterial; }

	// --- The camera's feel in the eyes (local player; behind the shoulder the boom has its own lag) ---
	/** Extra field of view while sprinting / sliding / dodging (degrees, eased in and out). The owner's movement guide
	 *  (2026-11-20): walk 95, sprint 103-108. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Camera")
	float SprintFovBoost = 10.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Camera")
	float SlideFovBoost = 10.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Camera")
	float DodgeFovBoost = 4.0f;

	/** The view tilts this many degrees into a slide, toward a strafe (the guide: a lean of 3-5 degrees) and into a dodge. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Camera")
	float SlideCameraRoll = 3.5f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Camera")
	float StrafeCameraRoll = 2.5f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Camera")
	float DodgeCameraRoll = 5.0f;

	/** Third person: the shoulder camera's arm is this much longer at a sprint (eased: the view opens as the body
	 *  stretches out). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Camera")
	float SprintArmExtra = 40.0f;
	float SprintView = 0.0f;      // 0..1, eased: how far into the sprint the cameras are

	/** At a sprint the view leans forward this many degrees (the guide: "camera leans forward"). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Camera")
	float SprintCameraPitch = 1.2f;

	/** A hard landing shakes the view: degrees of roll it is knocked by at the hardest (a wobble that settles). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Camera")
	float LandShakeRoll = 1.6f;
	/** A blast within five times its radius knocks the view: this many degrees of roll at the blast itself. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Camera")
	float BlastShakeRoll = 6.0f;
	float GetLastBlastTime() const { return LastBlastTime; }
	float GetLastBlastStrength() const { return LastBlastStrength; }

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

	/** Third person: the shoulder camera's arm length and offset (cm: Y right of the body). Over the RIGHT shoulder, the
	 *  player left of the middle of the screen (the owner, 2026-11-15, tried it over the left one and asked for it back). */
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
	/** The pad's B: crouch (held, or tapped standing or at a sprint, where it slides) and, tapped while the stick is
	 *  pushed at a walk or a run, the dodge (every face button is taken: the two share one). */
	UPROPERTY(EditDefaultsOnly, Category = "SO|Input")
	TSoftObjectPtr<UInputAction> PadCrouchDodgeAction;
	UPROPERTY(EditDefaultsOnly, Category = "SO|Input")
	TSoftObjectPtr<UInputAction> DodgeAction;
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
	/** The quick-use key (H, the pad's d-pad down): tapped, the chosen consumable is used; held, the next one held is
	 *  chosen (the owner's HUD ideas: "a quick-use key for consumables"). */
	UPROPERTY(EditDefaultsOnly, Category = "SO|Input")
	TSoftObjectPtr<UInputAction> QuickUseAction;

	// the kit's abilities, one action per slot (ASOCombatCharacter::ActivateSlot)
	UPROPERTY(EditDefaultsOnly, Category = "SO|Input")
	TSoftObjectPtr<UInputAction> GrenadeAction;
	UPROPERTY(EditDefaultsOnly, Category = "SO|Input")
	TSoftObjectPtr<UInputAction> MeleeAction;
	UPROPERTY(EditDefaultsOnly, Category = "SO|Input")
	TSoftObjectPtr<UInputAction> ClassAbilityAction;
	UPROPERTY(EditDefaultsOnly, Category = "SO|Input")
	TSoftObjectPtr<UInputAction> UltimateAction;
	/** Hand to hand: the guns go on the back, the hands are free (key 4; the mouse wheel and the pad's d-pad reach it
	 *  past the last gun). */
	UPROPERTY(EditDefaultsOnly, Category = "SO|Input")
	TSoftObjectPtr<UInputAction> FistsAction;

	UPROPERTY(EditDefaultsOnly, Category = "SO|Input")
	TSoftObjectPtr<UInputAction> PadShoulderRightAction;
	UPROPERTY(EditDefaultsOnly, Category = "SO|Input")
	TSoftObjectPtr<UInputAction> PadShoulderLeftAction;

	/** How long a pad shoulder waits for the other one before it counts alone (both together = the ultimate). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Input")
	float PadChordWindow = 0.09f;

	/** A pad shoulder went down or came up: right alone is the grenade, left alone the melee, both the ultimate. */
	void HandlePadShoulder(bool bRight, bool bDown);
	void HandlePadRightDown() { HandlePadShoulder(true, true); }
	void HandlePadRightUp() { HandlePadShoulder(true, false); }
	void HandlePadLeftDown() { HandlePadShoulder(false, true); }
	void HandlePadLeftUp() { HandlePadShoulder(false, false); }

	void HandleGrenade();
	void HandleMelee();
	void HandleClassAbility();
	void HandleUltimate();

	/** The flashlight (F): on or off at any time. Creatures see a lit light from farther and from any side. */
	UFUNCTION(BlueprintCallable, Category = "SO|Flashlight")
	void SetFlashlight(bool bOn);

	UFUNCTION(BlueprintPure, Category = "SO|Flashlight")
	bool IsFlashlightOn() const { return bFlashlightOn; }

	USpotLightComponent* GetFlashlight() const { return Flashlight; }

	/** The one camera (the owner, 2026-11-23: "one model and one camera that moves from player head to behind player"). */
	UCameraComponent* GetCamera() const { return Camera; }
	USpringArmComponent* GetCameraBoom() const { return CameraBoom; }
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
	void HandlePadCrouchDodgePressed();
	void HandlePadCrouchDodgeReleased();
	bool bPadPressWasDodge = false;
	void HandleDodgePressed();
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
	void HandleFists();
	void HandleNextWeapon();
	void HandlePrevWeapon();
	void HandleInventory();
	void HandleMap();
	void HandleFlashlight();
	void HandleQuickUsePressed();
	void HandleQuickUseReleased();

	/** The consumable the quick-use key uses: the one chosen while it is held, else the first held (none: none held). */
	FName GetQuickUse() const;
	/** Uses it (true: it did something; false: none held, or it would do nothing now). */
	bool QuickUse();
	/** Chooses the next consumable held. */
	void NextQuickUse();
	/** When it was last used or refused (the HUD's flash on the slot), and whether it was refused. */
	double GetQuickUseAt() const { return QuickUseAt; }
	bool WasQuickUseRefused() const { return bQuickUseRefused; }

	// (the quick-use key's state: the choice, when it was pressed, whether a hold changed the choice, the last use)
	FName QuickUseChoice;
	double QuickUsePressedAt = -1.0;
	bool bQuickUseCycled = false;
	double QuickUseAt = -100.0;
	bool bQuickUseRefused = false;

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

	/** The gun in hand is in its holster and the hands are free: while vaulting, mantling or climbing, and in hand to hand. */
	bool IsWeaponStowed() const { return bHeldStowed; }

	/**
	 * Hand to hand (the owner, 2026-11-15: "mele is when we put away all our guns on our back so we hold nothing but our
	 * fists ... light and hard strike for everything in mele"): every gun on the back, the style's guard on the upper
	 * body; fire is the light blow (a chain: each press within the style's grace goes on to the next), aim the heavy one.
	 * The style and its numbers are data (USOMeleeTable, Data/game_data.json "melee"). The server lands the blow.
	 */
	bool IsFists() const { return bFists; }

	/** The loadout's stand-in: the gun carried low across the chest (the sprint's carry), a hero's stance for the picture. */
	void SetDisplayCarry(bool bOn) { bDisplayCarry = bOn; }
	bool IsDisplayCarry() const { return bDisplayCarry; }
	/** The gun's state in third person (FSOStance): 0 RELAXED (carried low out of a fight), 1 at the READY (up and
	 *  forward, the body in its combat stance). It comes up on a shot, an aim, a reload or a hit, and goes back down
	 *  FSOStanceData::CombatSeconds after the last of them; eased (raise / lower time). Every machine: the owner from its
	 *  own input, the others from the server's word (bCombatReady). */
	float GetCombatReady() const { return CombatReady; }
	/** Bring the gun up and keep it up for a while (a shot, an aim, a reload, a hit, a capture's picture). */
	void MarkCombat();
	/** Back to relaxed at once (a capture's next gun; nothing else). */
	void CancelCombat() { CombatUntil = -1000.0; CombatReady = 0.0f; }
	virtual void OnTookDamage(AActor* Source, float Amount, bool bCrit) override;
	/** Nothing carried: no gun in the hands or on the body, the body in its own idle (an outfit's pictures). */
	void SetEmptyHanded(bool bOn) { bEmptyHanded = bOn; }
	void SetFists(bool bOn);
	/** The style in use: "fists", or a blade the player owns (USOInventoryComponent::HasBlade). Key 4 goes from the gun
	 *  to the first blade owned (or the fists), from a blade to the fists, from the fists back to the gun. */
	FName GetMeleeStyleId() const { return MeleeStyle; }
	void SetMeleeStyle(FName Style);
	/** The loadout's stand-in only: shows a style whether or not anybody owns it (a picture, never a player). */
	void SetDisplayMelee(FName Style)
	{
		if (Style != MeleeStyle)
		{
			MeleeStyle = Style;
			OnRep_MeleeStyle();
		}
	}
	/** The blade in the body's hand, null while none is out. */
	class UStaticMeshComponent* GetHeldBlade() const { return HeldBlade.Get(); }
	const struct FSOMeleeStyle* GetMeleeStyle() const;
	/** A blow from this player's own input (light, or heavy): shown at once here, landed by the server. */
	void MeleeStrike(bool bHeavy);
	/** Hand to hand's guard (the reload key held): blows from the front mostly turned, a parry just as it goes up. */
	void SetBlocking(bool bOn);
	bool IsBlocking() const { return bBlocking; }
	/** The combo now (blows landed one after another) and how long since the last; when this player last parried. */
	int32 GetComboHits() const { return ComboHits; }
	double GetComboAge() const;
	double GetParryShownAt() const { return ParryShownAt; }
	virtual float ScaleIncomingDamage(float Amount, const AActor* Source, bool bCrit) const override;
	virtual void OnMeleeHit(ASOCombatCharacter* Victim, const FVector& Point, float Weight, float HitStop) override;
	void HandleReloadReleased();
	/** Which blow the last one was (0.. the light chain, -1 heavy) and when it began (world seconds). */
	int32 GetMeleeLastBlow() const { return MeleeLastIndex; }
	double GetMeleeLastStart() const { return MeleeLastStart; }

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
	virtual void OnAbilityUsed(ESOAbilitySlot Slot) override;
	virtual void OnAbilityWindUp(ESOAbilitySlot Slot) override;

	/** An ability begins to show on this body (at its wind-up, or at its use if it has none): the hands leave the
	 *  gun, and standing still the whole body plays the ability's clip with the gun put away. Moving, the legs keep
	 *  their own motion and no clip is played (there is no upper-body layer yet). */
	void BeginAbilityShow(ESOAbilitySlot Slot);

	/** This body's clip of that name (its own set: A_Player<Sex>_<Name>), loaded once; null if it has none. */
	UAnimSequenceBase* GetAbilityClip(FName Name);

	UPROPERTY(Transient)
	TMap<FName, TObjectPtr<UAnimSequenceBase>> AbilityClips;
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
	bool bEmptyHanded = false;

	/** A lamp on the chest, pointing where the player looks (placed every frame). */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "SO|Flashlight")
	TObjectPtr<USpotLightComponent> Flashlight;

	UPROPERTY(ReplicatedUsing = OnRep_Flashlight)
	bool bFlashlightOn = false;

	UFUNCTION()
	void OnRep_Flashlight();

	UFUNCTION(Server, Reliable)
	void ServerSetFlashlight(bool bOn);

	// --- hand to hand
	UPROPERTY(ReplicatedUsing = OnRep_Fists)
	bool bFists = false;

	UPROPERTY(ReplicatedUsing = OnRep_MeleeStyle)
	FName MeleeStyle = TEXT("fists");

	UFUNCTION()
	void OnRep_MeleeStyle();

	UFUNCTION(Server, Reliable)
	void ServerSetMeleeStyle(FName Style);

	/** The style's blade in the body's right fist (made as it is first needed). */
	UPROPERTY(Transient)
	TObjectPtr<class UStaticMeshComponent> HeldBlade;

	FName BladeStyle;
	void UpdateBlade();
	/** Where the blade lies in a fist: its handle across the palm, the blade out of the thumb's side, the edge toward
	 *  the knuckles, from the hand's own bones (as the hold fit reads them). */
	static bool BladeInHand(const USkeletalMeshComponent* Skel, FTransform& OutWorld);

	UFUNCTION()
	void OnRep_Fists();

	UFUNCTION(Server, Reliable)
	void ServerSetFists(bool bOn);

	UFUNCTION(Server, Reliable)
	void ServerMeleeBlow(int16 Index);

	UFUNCTION(NetMulticast, Reliable)
	void MulticastMeleeBlow(int16 Index);

	/** A blow landed: shown on every machine (the freeze of both bodies, sparks, the camera, the count). */
	UFUNCTION(NetMulticast, Unreliable)
	void MulticastMeleeImpact(ASOCombatCharacter* Victim, FVector_NetQuantize Point, float Weight, float HitStop);

	UFUNCTION(Server, Reliable)
	void ServerSetBlocking(bool bOn);

	/** The next blow for a press now, by the body's stance and the chain (SOMeleeMove: crouched, at a sprint, in the
	 *  air, or after lights), or -2 when the last one is still too early to follow. */
	int32 NextMeleeBlow(bool bHeavy) const;
	/** Whether this blow may start now (the server's check of what a joined player asked for). */
	bool MeleeBlowAllowed(int32 Index) const;
	const struct FSOMeleeBlow* MeleeBlowAt(int32 Index) const;
	/** The clip, the sounds, the edge's light, the step in (this machine). */
	void ShowMeleeBlow(int32 Index);
	/** Starts a blow's clock (both the predicting machine and the server keep it). */
	void BeginMeleeBlow(int32 Index);
	/** The guard on (or off) both bodies' animation. */
	void UpdateMeleeGuard();

	bool bDisplayCarry = false;

	int32 MeleeLastIndex = -1;
	double MeleeLastStart = -100.0;

	// blocking and parrying (the server's: BlockStart is when the guard went up; CounterUntil the parry's reward)
	UPROPERTY(Replicated)
	bool bBlocking = false;
	double BlockStart = -100.0;
	double CounterUntil = -100.0;
	double ParryShownAt = -100.0;
	/** The count of blows landed one after another (this player's own machine: the HUD's combo). */
	int32 ComboHits = 0;
	double ComboLast = -100.0;
	float ComboDamage = 0.0f;
	double MeleePredicted = -100.0;  // (this machine showed the blow it asked for: the server's echo is skipped)
	FTimerHandle MeleeHitTimer;
	FTimerHandle MeleeEdgeTimer;

	/** Feet on the ground make noise the creatures hear: running loud, walking soft, crouching none. */
	void TickFootstepNoise(float DeltaSeconds);
	float FootstepTimer = 0.0f;

	/** Where the gun is held (set every frame by the viewmodel component; the gun rides it). */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "SO|Camera")
	TObjectPtr<USceneComponent> GunHold;

	/** The one camera's boom: no length in the eyes (first person), out behind the shoulder for the test view. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "SO|Camera")
	TObjectPtr<USpringArmComponent> CameraBoom;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "SO|Camera")
	TObjectPtr<UCameraComponent> Camera;

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
	/** The worn piece of a slot, null if none shows. */
	USkeletalMeshComponent* GetWornPiece(FName Slot) const;
	/** Body regions the worn pieces cover (their skin sections are hidden). */
	const TSet<FName>& GetHiddenRegions() const { return HiddenRegions; }
	/** Only the face's sliders and the skin's and the hair's tones from an outfit, on this body as it is dressed (the
	 *  armoury's stand-in while a slider is dragged: nothing dressed again). */
	void SetLook(const FSOOutfit& From);
	/** The face's BeardMask for a beard (stubble, short, full: the beard map's R, G, B; none: nothing). */
	static FLinearColor BeardMask(FName Beard);

protected:
	/** Every piece is a skeletal mesh following the body's pose (leader pose), in both views. */
	UPROPERTY(ReplicatedUsing = OnRep_Outfit)
	FSOOutfit Outfit;

	UFUNCTION()
	void OnRep_Outfit();
	void ApplyOutfit();
	/** The outfit's face sliders onto the body's morph targets (face_<key>). */
	void ApplyFace();
	void OutfitFromInventory();
	FDelegateHandle OutfitHandle;
	FName AppliedBody;
	TSet<FName> HiddenRegions;

	UPROPERTY(Transient)
	TMap<FName, TObjectPtr<USkeletalMeshComponent>> WornPieces;

	UFUNCTION(Server, Reliable)
	void ServerSetViewMode(ESOViewMode NewMode);

	/** On the sights. Set by the player's own machine from the input; the server takes it from the movement's aim
	 *  flag (it arrives with every move) and passes it to everyone else, so the spread the server rolls and the
	 *  pose the others see are the aimed ones. */
	UPROPERTY(Transient, Replicated, BlueprintReadOnly, Category = "SO|Combat")
	bool bAiming = false;
	/** At the ready (the server's word, for the other machines: GetCombatReady). */
	UPROPERTY(Replicated)
	bool bCombatReady = false;
	double CombatUntil = -1000.0;
	float CombatReady = 0.0f;

private:
	void ApplyViewMode();
	float GetTargetEyeOffset() const;

	/** The capsule's eye height over its centre (eased across crouch changes): the eyes until the body has a pose. */
	float EyeOffset = 0.0f;

	/** The body's own eyes in the capsule's frame (followed by a spring), and their place on the head joint. */
	void UpdateEye(float DeltaSeconds);
	FVector EyeCS = FVector::ZeroVector;
	FVector EyeVelCS = FVector::ZeroVector;
	FVector EyeHeadCS = FVector::ZeroVector;
	bool bHaveEye = false;
	/** The camera's place on the sights (the capsule's frame) and how far on them: SetSightEye. */
	FVector SightEyeCS = FVector::ZeroVector;
	float SightEyeAlpha = 0.0f;

	/** The head hidden from its own player's camera, its shadow kept (IsHeadHidden): the body's custom primitive data and
	 *  the head's worn pieces, as the camera comes into the eyes or leaves them. */
	void UpdateHeadHiding();
	bool bHeadHiddenNow = false;
	bool bHeadByMaterial = false;
	TWeakObjectPtr<const USkeletalMesh> HeadPartMesh;

	/** The one camera: in the eyes, or out behind the shoulder (ViewBlend), its field of view between the two. */
	void UpdateCamera(float DeltaSeconds, float Ads, float EyeFov, float ShoulderFov);
	float ViewBlend = 0.0f;

	/** The camera's feel in the eyes: step smoothing, landing spring, roll, field-of-view boost. */
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
	float CameraRoll = 0.0f;
	float CameraRollVel = 0.0f;   // (the roll is a spring: it leans in and settles, never a straight line)
	float EyeVel = 0.0f;          // (so is the eye's height across crouch, slide and stand)
	float FeelPitch = 0.0f;       // degrees: the sprint's forward lean
	float BlastPunch = 0.0f;      // degrees: a nearby blast's punch on the view (decays)
	float LastBlastTime = -100.0f;
	float LastBlastStrength = 0.0f;
	FDelegateHandle BlastHandle;
	/** A blast went off near this body (USOFxSubsystem::OnBlast): the view is knocked and the screen's edge flashes
	 *  by how near it was. */
	void OnBlastNearby(const FVector& Point, float Radius);
	float ShakeRoll = 0.0f;       // degrees: a landing's wobble (a spring)
	float ShakeRollVel = 0.0f;
	float FovBoost = 0.0f;
	FVector FeelOffset = FVector::ZeroVector;
	float CurrentFov = 90.0f;

	float BufferedJumpTime = -1.0f;
	float SprintPressTime = -1.0f;
	float CrouchPressTime = -1.0f;
	bool bSprintLatched = false;
	float AimProgress = 0.0f;
	float RecoilKick = 0.0f;

	/** Degrees of pitch an ability's use knocked the view by (down for a blow); recovers on its own. */
	float AbilityKick = 0.0f;

	bool bPadShoulderDown[2] = { false, false };   // [0] left, [1] right
	FTimerHandle PadChordTimer;
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
