#pragma once

#include "CoreMinimal.h"
#include "Components/SceneComponent.h"
#include "SOViewmodelComponent.generated.h"

class ASOCharacter;
class ASOWeapon;
class USOGunRigComponent;
class USOWeaponData;

/**
 * Where the body holds its gun: ONE gun in ONE body's hands, the same in first person (the game: seen from the body's
 * own eyes) and in the third-person test view (the owner, 2026-11-23: one model, one camera). Ticks after movement and
 * look and before the body animates, and places the character's gun hold (the gun rides it; the body's arm IK reaches
 * for its grips):
 *  - the body's own hold by the gun's class (FSOStance): relaxed low across the body, at the ready on the shoulder,
 *    handguns out in both hands; the sprint's carry, the reload's, a steep look down;
 *  - on the sights, the sight on the line of the body's eyes (where the camera is in first person), the kick turning
 *    the gun about its sight;
 *  - the recoil's kick, the raise, the reload's own moves and the motion's inertia on top;
 *  - never into a wall (pulled back, then up), never out of the firing hand's reach (the owner's ULTIMATE rule: the
 *    hands are always on the gun).
 * Actor and eye space: +X forward, +Y right, +Z up (cm).
 */
UCLASS(ClassGroup = (ShatteredOrbit))
class SOCHARACTER_API USOViewmodelComponent : public USceneComponent
{
	GENERATED_BODY()

public:
	USOViewmodelComponent();

	/** On the sights of a long gun the gun stays shouldered (its butt in the pocket) and the camera alone comes to its
	 *  sight's line (the head keeps its own pose): this far ahead of the butt (cm along the gun: where a cheek on the
	 *  comb would put the eye). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	float CheekFromButt = 13.0f;

	/** ...but never nearer the sight than this (cm): irons (a rear sight nearer the eye is a blur), a gun's built-in
	 *  optic (its sight point), a rail optic (its sight point is its eye point, set per optic in gun_attach.glb). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	float IronsEyeRelief = 6.0f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	float BuiltInOpticEyeRelief = 4.0f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	float OpticEyeRelief = 0.0f;

	/** A handgun on the sights is held out in both hands, its sight on the eyes' line where the firing wrist is this
	 *  share of the arm from its shoulder (the arms nearly straight); without a body, this far ahead of the eyes (cm). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	float HandgunReach = 0.88f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	float AdsHandgunSightDistance = 30.0f;

	/** Without a gun's shape yet: a long gun's sight this far ahead of the eyes (cm). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	float AdsSightDistance = 16.0f;

	/** The shoulder pocket (where the butt sits) from the right shoulder joint, actor axes at rest (cm: X forward, Y
	 *  right, Z up): in front of the joint, toward the chest, a little below it. Turns with the chest. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	FVector PocketFromShoulder = FVector(9.0f, -4.5f, -4.0f);

	/** Height of the butt's middle in rig space (cm above the top of the pistol grip). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	float ButtHeight = 1.5f;

	/** The gun points at the crosshair's point, but never at one nearer than this (cm). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	float MinAimDistance = 400.0f;

	/** A long gun pointed steeply down: where its middle hangs from, in actor space off the chest point (ahead, right,
	 *  up); the gun's own pitch is held within these off the sights (degrees), and it cants this much at the full low hold (+
	 *  inward: -10, a little out, since the elbows keep out of the trunk: canted 28 in, the wrists bent past 80 for it). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	FVector LowHold = FVector(22.0f, 10.0f, -39.0f);            // (27 under: the grip hung 27 cm under its shoulder and 20 ahead, and no elbow suits a wrist there)
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	float MaxDownPitch = 44.0f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	float MaxUpPitch = 65.0f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	float LowCant = -22.0f;

	/** Sprinting, as the gun's data says (USOWeaponData::SprintCarry, the owner, 2026-11-15: "on running we lower the gun
	 *  for rifles ... smaller guns like smg/pistol/revolver/handcannon we take it up"): the grip from the shoulders'
	 *  middle (cm, actor axes: forward, right, up) and the gun's turn (pitch, yaw, roll) against the facing. Low (a long
	 *  gun): the low ready, across the chest, muzzle down and to the left. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	FVector CarryOffset = FVector(26.0f, 9.0f, -8.0f);          // (the front of it in the corner of the eyes' picture: 24
	                                                             // below the shoulders and 30 degrees down it was out of it;
	                                                             // at the shoulders' height the firing wrist bent 85)
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	FRotator CarryRot = FRotator(-18.0f, -32.0f, -10.0f);

	/** Short (an SMG): up part of the way, in front of the chest, muzzle up and in. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	FVector ShortCarryOffset = FVector(26.0f, 8.0f, -10.0f);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	FRotator ShortCarryRot = FRotator(32.0f, -18.0f, -12.0f);

	/** High (a handgun): up by the face in both hands, muzzle to the sky. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	FVector HandgunCarryOffset = FVector(22.0f, 9.0f, 6.0f);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	FRotator HandgunCarryRot = FRotator(72.0f, -8.0f, 0.0f);


	/** Reloading, the reload SEEN (the owner, 2026-11-24: "During reloads most guns are either not visible in the screen or
	 *  they're facing the wrong way, the m4 for example should tilt more to the right so the reload clip is visible or
	 *  player should raise the gun with one hand and then reload ... the player can see the magazine fully"; and
	 *  2026-11-27, a showcase of another game's first-person guns: "this is how my first person must look and feel ...
	 *  these reloads, these animations"): the gun is SHOWN (FSOReloadShow, Data/reload_shows.json): swung up large into the
	 *  picture with the part its reload works (KeepReloadWork: its magazine, cell, cylinder, flap, loading port) where the
	 *  show says and the gun turned as it says, for the field of view the player has set; the show changes with what the
	 *  support hand is doing (the choreography's hand anchors: the magazine out, the fresh one in, a handle racked) and the
	 *  gun follows it on a spring (ShowNow): it swings, overshoots a little and settles. Each beat of the handling (a
	 *  reload's sound events: Handle) jolts the gun in the hands and nudges the view. Before, one pose for every gun in
	 *  front of the chest, canted 28 degrees the other way: the work lay under the foot of the picture and was seen from
	 *  straight above, the receiver over it. */
	void Handle(FName Event);

	/** The part the reload works, at rest, in the gun rig's frame, and the side of the bore it lies on (rig Y, Z) (tests). */
	FVector GetReloadWork() const { return ReloadWork; }
	FVector2D GetReloadSide() const { return ReloadSide; }
	/** The show the gun is in now (tests): FSOReloadShow's six numbers. */
	const float* GetReloadShow() const { return ShowNow; }

	/** Without a body pose yet: the pocket in actor space (cm). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	FVector DefaultPocket = FVector(1.0f, 12.0f, 48.5f);

	/** The firing hand's wrist is kept within this share of the arm's length from its shoulder (the gun comes in when it
	 *  would be further: the hand is always on its handle). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	float FiringReach = 0.95f;
	/** ... nor nearer than this share of it: a gun whose grip sat a third of the arm from the shoulder (a short gun
	 *  shouldered: the ksmg) folded the firing arm shut with the forearm square across the gun, and no wrist follows that
	 *  (SOArmBones): the gun goes out to where the arm has a bend an arm makes. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	float FiringReachLeast = 0.42f;
	/** A handgun's: it is held OUT, both arms: crouched, the hold came in to 57 % of the arm, the forearm steep across to
	 *  it, and the firing wrist was asked past its range (the hand turned 1.6 cm into the revolver's grip). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	float HandgunReachLeast = 0.66f;

	/** The support hand's place on the gun is kept within this share of its arm from its shoulder: the gun comes in
	 *  toward that shoulder (a long gun's butt no further back than this far in front of the firing shoulder joint, cm). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	float SupportReach = 0.87f;
	/** ...and after the sway, the kick and the walls, a safety only: this share of the arm (the gun's place is set by the
	 *  body's hold before; at the same share the walk's shoulder pushed the rifle's fore end over it and back every few
	 *  frames, and the gun jerked in the picture). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	float SupportReachLast = 0.93f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	float ButtAheadOfShoulder = 2.0f;

	/** Walking off the sights the gun's place against the eyes' steady place follows the body's hold through this spring
	 *  (the owner, 2026-11-23: "when in first person not scoped and walking the guns shake too much": the walk's shoulder
	 *  bob and twist came through as a shake in the picture; now a slow sway). Standing, reloading and sprinting the hold
	 *  is as it is. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold")
	float InEyesFollowMoving = 9.0f;

	/** The step's own motion (the owner's movement guide: "walk: subtle bob and sway ... sprint: dynamic arm movement"):
	 *  locked to the gait's cycle, each the full swing at the run (a stroll a part of it, crouched 0.6): how far the gun
	 *  dips as each foot takes the weight and sways across a stride (cm) and rolls with it (degrees), how late after the
	 *  footfall it is lowest (of a cycle); and the sprint carry's swing on top (cm, degrees: the arms pump it). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold|Step")
	float StepDip = 0.35f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold|Step")
	float StepSway = 0.45f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold|Step")
	float StepRoll = 0.7f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold|Step")
	float StepLag = 0.05f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold|Step")
	float SprintStepDip = 0.6f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold|Step")
	float SprintStepSway = 1.2f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold|Step")
	float SprintStepRoll = 2.0f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold|Step")
	float SprintStepYaw = 1.6f;
	/** At the run (not a stroll, not a sprint) the gun rides canted in this many degrees, this much lower and further in
	 *  (cm): running reads apart from walking (the owner's second movement video, 2026-11-24). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold|Step")
	float RunCant = 7.0f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold|Step")
	float RunDrop = 0.6f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold|Step")
	float RunIn = 0.5f;

	/** The gun's weight (movement pass 2, 2026-11-24): as the body sets off the gun is drawn after it, this many cm back
	 *  toward the eyes and its muzzle lifting this many degrees, as it stops it swings on as far forward with its muzzle
	 *  dipping, and settles; a unit is a change of pace of 440 cm/s within about MoveInertiaLag (a stop from a run). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold|Weight")
	float MoveInertiaBack = 1.4f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold|Weight")
	float MoveInertiaPitch = 1.6f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold|Weight", meta = (Units = "s"))
	float MoveInertiaLag = 0.14f;
	/** A landing dips the muzzle this many degrees for every cm the view dips with it (ASOCharacter::GetLandDip). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Hold|Weight")
	float LandMuzzleDip = 0.3f;

	/** The shoulder pocket and the shoulders' middle (actor space, cm) from the body's last pose; false = defaults. */
	bool GetShoulderPoints(const ASOCharacter* Character, FVector& OutPocket, FVector& OutChest) const;

	void Kick(float Strength);
	void Raise() { Lower = 1.0f; }

	/** Eased ADS amount 0..1 the hold currently uses. */
	float GetAds() const { return Ads; }

	/** How far a wall in front has pushed the gun back (cm, eased). */
	float GetWallPush() const { return WallK; }

	/** Places the gun hold now (also called by the tick). */
	void UpdateHold(float DeltaTime);

	virtual void BeginPlay() override;
	virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

private:
	float Ads = 0.0f;
	float KickBack = 0.0f;   // m
	float KickPitch = 0.0f;  // rad
	float Lower = 1.0f;
	float RunK = 0.0f;
	float RunV = 0.0f;       // (the carries and the trail are springs: a little overshoot, then settled)
	float StrafeK = 0.0f;
	float StrafeV = 0.0f;
	float SlideV = 0.0f, MantleV = 0.0f;
	float AirK = 0.0f, AirV = 0.0f;
	float FwdLag = 0.0f, FwdK = 0.0f, FwdV = 0.0f;   // (the body's pace along its facing, lagged; the weight's spring)
	float SlideK = 0.0f;
	float MantleK = 0.0f;
	float ReloadK = 0.0f;
	/** How far an inspect (ASOWeapon::IsInspecting) has the gun: it is looked over from the ready hold, never the relaxed
	 *  carry (eased: the gun comes up out of the carry into it). */
	float InspectK = 0.0f;
	float WallK = 0.0f, WallV = 0.0f;
	FVector HoldDir = FVector::ForwardVector;
	/** HoldDir in the view's own frame, where it is eased (HoldTransform). */
	FVector HoldDirView = FVector::ForwardVector;
	bool bHoldDirValid = false;
	/** How far under the eyes the camera settles to frame the gun in the picture (FSOStance::FrameDown, cm), eased. */
	float FrameDrop = 0.0f, FrameDropVel = 0.0f, FrameWant = 0.0f;
	float FrameSide = 0.0f, FrameSideVel = 0.0f, FrameSideWant = 0.0f;
	float FrameBack = 0.0f, FrameBackVel = 0.0f;
	/** The gun's place against the eyes' steady place, followed (InEyesFollowMoving). */
	FVector InEyesPos = FVector::ZeroVector, InEyesVel = FVector::ZeroVector;
	float WalkK = 0.0f, WalkV = 0.0f;   // (how much of the walk's smoothing counts, eased)
	/** The reload's work (ReloadPose): where on the gun, the side of the bore it lies on (rig Y, Z), and which gun. */
	FVector ReloadWork = FVector(10.0f, 0.0f, -8.0f);
	FVector2D ReloadSide = FVector2D(0.0f, -1.0f);
	TWeakObjectPtr<const USOGunRigComponent> ReloadWorkRig;
	/** The show the gun is in (FSOReloadShow's six numbers, sprung toward the one the hand's work asks), the one a
	 *  segment began in (the hand anchor "cur"), and whether a reload is under way. */
	float ShowNow[6] = { 38.0f, 0.55f, 0.64f, 30.0f, 20.0f, 45.0f };
	float ShowVel[6] = { 0, 0, 0, 0, 0, 0 };
	float ShowCur[6] = { 38.0f, 0.55f, 0.64f, 30.0f, 20.0f, 45.0f };
	float ShowWant[6] = { 38.0f, 0.55f, 0.64f, 30.0f, 20.0f, 45.0f };
	/** The show of the place the reload's hand is on its way to (while it is in flight between two places: bShowFlight):
	 *  where the gun will be when the hand arrives (USOGunRigComponent::SetShowLead). */
	float ShowTo[6] = { 38.0f, 0.55f, 0.64f, 30.0f, 20.0f, 45.0f };
	bool bShowFlight = false;
	/** That flight (its segment and its two places), and the gun's hold as it was when the hand let go, in the show's own
	 *  frame (the view's, ShowFrame): the hand's way begins where it was then, whatever the gun has done since. */
	int32 FlightSegment = -1;
	FName FlightA, FlightB;
	bool bFlightBegan = false;
	FTransform FlightHold = FTransform::Identity;
	/** The frame the shows are laid in: at the eyes, the view's turn with its pitch held within 35 degrees and no roll. */
	FTransform ShowFrame(const ASOCharacter* Character) const;
	int32 ShowSegment = -1;
	bool bShowing = false;
	/** The handling's jolts on the gun in the hands (cm: right, up, back; degrees: the muzzle up, the muzzle left, the
	 *  top to the left): springs knocked by each beat, back to nothing. */
	FVector JoltMove = FVector::ZeroVector, JoltMoveVel = FVector::ZeroVector;
	FVector JoltTurn = FVector::ZeroVector, JoltTurnVel = FVector::ZeroVector;
	FQuat InEyesRot = FQuat::Identity;
	bool bInEyesValid = false;

	/** Where the body holds the gun: the stance's place, the sprint's carry, the reload's, a steep look down. */
	FTransform HoldTransform(const ASOCharacter* Character, const USOWeaponData* Data, bool bHandgun, float Dt, float RunT);
	/** The sprint's carry and the reload's workspace, blended onto a hold the hands' reach has already been laid on. */
	FTransform OffTheShoulder(const ASOCharacter* Character, const USOWeaponData* Data, bool bHandgun, float RunT, const FTransform& Hold) const;
	/** Finds the part the gun's reload works, at rest (kept from before a reload begins: the gun never chases a magazine
	 *  on its way out). */
	void KeepReloadWork(const ASOWeapon* Weapon, const USOGunRigComponent* Rig);
	/** Where the gun is held to be reloaded: its work in the picture and turned toward the eyes (ReloadWorkAhead ...). */
	FTransform ReloadPose(const ASOCharacter* Character, const float* Show = nullptr) const;
	/** Pulled back from a wall in front (along itself, then the muzzle turned up past it), eased. */
	FTransform ClearOfWalls(const ASOCharacter* Character, const USOGunRigComponent* Rig, const FTransform& Hold, float Dt);
	/** Never further from the firing shoulder than the arm reaches, nor folded into it: the hand stays on its handle. */
	FTransform InFiringReach(const ASOCharacter* Character, const USOGunRigComponent* Rig, const FTransform& Hold) const;
	/** Never turned further than the firing arm's bones can hold it (SOArmBones): the gun gives way about the hand on its
	 *  grip, eased. Off the sights (on them the gun is on the eye's line). */
	FTransform InFiringRange(const ASOCharacter* Character, const USOGunRigComponent* Rig, const FTransform& Hold, float Dt);
	FQuat RangeGive = FQuat::Identity;
	float WorkedTail = 0.0f;
	/** Never further from the support shoulder than that arm reaches with a bend left in it: the gun comes in toward it
	 *  (the support hand is on the gun too; slid back along the gun its fingers closed in it, or it left a handgun). */
	FTransform InSupportReach(const ASOCharacter* Character, const USOGunRigComponent* Rig, const FTransform& Hold, float Reach, float StockOff = 0.0f) const;
	/** The support wrist's place on the gun (the rig's frame, the fitted hold), its shoulder and arm in the body's last pose. */
	bool SupportArm(const ASOCharacter* Character, const USOGunRigComponent* Rig, FVector& OutInGun, FVector& OutShoulder, float& OutArm) const;
	/** A handgun held out on the sights: how far ahead of the eye its sight is, from the reach of the arms. */
	float HandgunRelief(const ASOCharacter* Character, const USOGunRigComponent* Rig, const FVector& SightRig, const FTransform& Eye) const;
};
