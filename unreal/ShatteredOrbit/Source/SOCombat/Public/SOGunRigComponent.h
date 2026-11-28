#pragma once

#include "CoreMinimal.h"
#include "Components/SceneComponent.h"
#include "SOGunRigComponent.generated.h"

class UStaticMesh;
class UStaticMeshComponent;
class USOWeaponData;
struct FSOReloadPose;
struct FSOWeaponInstance;

/**
 * Where a hand holds something, in rig space (+X barrel, +Y right, +Z up, cm): the wrist location and an anatomical
 * basis (X along the hand wrist -> fingers, Y towards the thumb, Z out of the palm). The character's arm IK reaches
 * the wrist and turns the hand bone onto the basis, so the same grips work for any body on the shared rig.
 */
struct SOCOMBAT_API FSOHandGrip
{
	FVector Wrist = FVector::ZeroVector;
	FQuat Basis = FQuat::Identity;

	/** Basis from the finger direction and the thumb side (a proper rotation; X along, Y thumb, Z = X x Y). */
	static FQuat MakeBasis(const FVector& Along, const FVector& Thumb, bool bLeft);
	/** Out of the palm: +Z of the basis on the right hand, -Z on the (mirrored) left hand. */
	static FVector PalmNormal(const FQuat& Basis, bool bLeft);
	/** A grip whose palm centre touches Contact (the wrist sits behind it along the hand, off the palm surface). */
	static FSOHandGrip AtPalm(const FVector& Contact, const FVector& Along, const FVector& Thumb, bool bLeft);
};

/**
 * How far each finger closes, degrees per joint (knuckle, middle, tip) for index, middle, ring, little finger and
 * thumb (base, middle, tip). The arm IK turns each finger about the axis that brings it towards the palm.
 */
struct SOCOMBAT_API FSOFingerPose
{
	float Curl[5][3] = { { 0, 0, 0 }, { 0, 0, 0 }, { 0, 0, 0 }, { 0, 0, 0 }, { 0, 0, 0 } };
	/** The thumb swung round the hand's long axis toward the palm's side, degrees: it lies on the far side of what
	 *  the fingers hold (a grip between thumb and fingers), instead of through it. */
	float ThumbSpread = 0.0f;
	/** The thumb drawn in toward the fingers, degrees about the palm's normal: it lies ALONG what the hand holds (a
	 *  thumb forward along a handguard) instead of standing off from it. */
	float ThumbIn = 0.0f;
	/** The index finger turned in the palm's plane (degrees about the palm's normal) before it closes: lifted to a
	 *  trigger that sits higher than the knuckles of a hand round its grip (the finger alone, the others as they are). */
	float IndexLift = 0.0f;
	/** How far the fingers close their fan, 0 .. 1: each of the index (the support hand's only: the firing hand's is on
	 *  the trigger), ring and little finger turned in the palm's plane toward the middle finger's line before it closes.
	 *  A hand at rest spreads its fingers; one that grips holds them together (spread, they touched what they held with
	 *  their tips only). */
	float Together = 0.0f;

	static FSOFingerPose Make(const float Index[3], const float Middle[3], const float Ring[3], const float Pinky[3], const float Thumb[3]);
	/** Firing hand on a pistol grip: three fingers wrapped, the index finger on the trigger, the thumb over the top. */
	static FSOFingerPose Trigger();
	/** Round a handguard / forend / vertical grip. */
	static FSOFingerPose Wrap(float Amount = 1.0f);
	/** Holding something small between thumb and fingers (rounds, shells, a speedloader, a cell). */
	static FSOFingerPose Pinch();
	/** Open palm (slapping a magazine home, pushing a lid). */
	static FSOFingerPose Flat();
	/** Relaxed, half closed. */
	static FSOFingerPose Relaxed();
	static FSOFingerPose Lerp(const FSOFingerPose& A, const FSOFingerPose& B, float Alpha);
};

/**
 * A gun's OWN hold: where both hands rest on it and how every finger closes, in the gun's frame (+X barrel, +Y right,
 * +Z up, cm from the top of the pistol grip; degrees). Each gun brings its own in a file of its own,
 * Data/holds/<archetype>.json (the owner, 2026-11-15: "the resting arm numbers should be in a file with the gun so
 * player switches to that gun and the new numbers are applied ... 100 guns means 100 probably different gun positions
 * that should come with the gun"). The rig reads it as it is built; the hands go where it says. A gun with no file is
 * fitted as it is picked up (USOLocomotionAnimInstance::FitGrip, which finds the grip, the handguard or a vertical
 * fore grip on the gun's own shape): that fit is also the tool that WRITES the files (`SOCaptureSeries 1 31`), and a
 * file may then be changed by hand: the file is what holds.
 */
struct SOCOMBAT_API FSOGunHold
{
	FSOHandGrip Firing;
	FSOHandGrip Support;
	FSOFingerPose FiringFingers;
	FSOFingerPose SupportFingers;

	/** The file of a gun's hold, relative to the project. */
	static FString File(FName Archetype) { return FString::Printf(TEXT("Data/holds/%s.json"), *Archetype.ToString()); }
	/** Reads the gun's file. False: it has none (or it does not parse): the gun is fitted as it is picked up. */
	static bool Load(FName Archetype, FSOGunHold& Out);
	/** The file's text for this hold (`About`: a line saying where it came from and how it measured). */
	FString ToJson(FName Archetype, const FString& About) const;
	/** Developer: while the files are being written, none is read (the fit works every hold out afresh). */
	static bool bIgnoreFiles;
};

/**
 * A posable gun: body + reload parts (+ spare mag) built from a USOWeaponData.
 * The component's +X is the barrel. Children live under GunSpace, which turns the imported mesh space (gun along +Y)
 * onto +X. ApplyPose() moves the parts and the off hand's grip (reload choreography); GetHandTargets() tells the
 * holder's arm IK where both hands go.
 */
UCLASS(ClassGroup = (ShatteredOrbit))
class SOCOMBAT_API USOGunRigComponent : public USceneComponent
{
	GENERATED_BODY()

public:
	USOGunRigComponent();

	/** Creates the mesh components: the gun, one model, seen by everyone and casting its shadow (the owner's own eyes
	 *  see the same gun in the same hands). */
	void Build(const USOWeaponData* Data);

	/** The copy's looks: mounts its optic on the rail (hiding the built-in sight it replaces), paints the body in its
	 *  finish and the glow in its rarity colour (material names are an API: gun_body, gun_glow). */
	void Dress(const FSOWeaponInstance& Instance);

	/** Removes the gun: every mesh it made, then itself. (Destroying only this component would hand its meshes to
	 *  whatever it was attached to: they would stay there.) */
	void Dismantle();

	/** Shows or hides the whole gun; parts the pose or a mounted optic keep hidden stay hidden. */
	void SetShown(bool bInShown);

	void ApplyPose(const FSOReloadPose& Pose);
	/** The turn of a rotary gun's barrel cluster (the part named `spin`), radians about the bore. */
	void SetBarrelSpin(float Radians) { BarrelSpin = Radians; }

	/** World-space muzzle position. */
	FVector GetMuzzleLocation() const;

	/** Off-hand anchor in mesh space (cm) against the parts as currently posed: fore, mag, spare, magbase, bolt,
	 *  charge, slide, pump, cyl, ejector, loader, shell, round, hatch, biomass, pouch, free. */
	FVector ResolveAnchor(FName Anchor) const;

	UStaticMeshComponent* GetPart(FName Name) const;
	UStaticMeshComponent* GetSpare() const { return Spare; }

	/** The magazine pouch on the holder's body (world), and the holder's facing: false without a holder's body. */
	bool PouchOnBody(FVector& OutWorld, FQuat* OutFacing = nullptr) const;

	/** World-space wrist targets with the hand bases as rotations (see FSOHandGrip). False until built. */
	bool GetHandTargets(FTransform& OutRight, FTransform& OutLeft) const;

	/** How both hands close right now (the off hand's follows what it is holding through the reload). */
	void GetFingerPoses(FSOFingerPose& OutRight, FSOFingerPose& OutLeft) const { OutRight = RightFingers; OutLeft = LeftFingers; }

	/** Finger pose for the off hand on an anchor (fore, mag, magbase, bolt, round, ...). */
	FSOFingerPose FingersForAnchor(FName Anchor) const;

	/** How far the off hand may turn about its own palm's normal on what it holds at an anchor, degrees either way: a
	 *  hand takes a magazine, a floor plate, a shell or a flap from wherever its arm comes (the owner, 2026-11-27:
	 *  "humans have bones and can't bend their hands/arms in such manner"), a handle it hooks only a little, the fore end
	 *  it is fitted to not at all. */
	float SpinFreeForAnchor(FName Anchor) const;
	/** That freedom right now (between the two places the reload's hand is going from and to). */
	float GetSupportSpinFree() const { return LeftSpinFree; }
	/** Where the gun WILL be once it has been turned for the reload hand's next job (InLead: the viewmodel's show for
	 *  that job) and where it WAS when the hand let go of the place it is leaving (InLeft), both in the gun's own frame of
	 *  now (identity: where it is). In flight between two places the hand goes from where it let go to where the part it
	 *  makes for will be, in the body's space, and the gun brings the part to the hand (ApplyPose). */
	void SetShowLead(const FTransform& InLead, const FTransform& InLeft) { ShowLead = InLead; ShowLeft = InLeft; }
	/** The reload's hand is BRINGING something to the gun (a fresh magazine, a speedloader, a shell, a round, a lump of
	 *  biomass: on its way from the pouch to where the choreography puts the thing): it rides in the hand that carries it.
	 *  SeatCarried lays it in that hand as the body has it NOW (the hand's own grip frame in the world: the wrist, and the
	 *  hand's basis as FSOHandGrip::MakeBasis makes one), in the hold the hand will have on it at the gun; near the gun it
	 *  goes over to its place in the choreography. Called after ApplyPose, by whoever knows the body (ASOWeapon::Tick). */
	bool IsCarrying() const { return CarriedPart.IsValid() && CarriedShare > 0.0f; }
	void SeatCarried(const FTransform& HandGripWorld);

	/** The gun body's bounds in rig space (+X barrel, +Y right, +Z up, cm). */
	FBox GetRigBounds() const;

	/** The whole gun as it is carried: the body with its parts (magazine, bolt, ...) and the mounted optic. */
	FBox GetWornBounds() const;

	/** Rig-space grips (tests / debugging). */
	const FSOHandGrip& GetRightGrip() const { return RightGrip; }
	const FSOHandGrip& GetLeftGrip() const { return LeftGrip; }
	/** Off-hand grip for an anchor (fore, mag, spare, magbase, bolt, pouch) against the current part poses. */
	FSOHandGrip GripForAnchor(FName Anchor) const;
	USceneComponent* GetGunSpace() const { return GunSpace; }
	bool IsBuilt() const { return bBuilt; }
	/** A handgun (short barrel, held out in both hands). */
	bool IsHandgun() const { return bHandgun; }
	/** The hands are fitted the snug way (USOWeaponData::bSnugGrip): the fingers together, the support thumb laid close
	 *  along the side. */
	bool IsSnugGrip() const { return bSnugGrip; }
	/** This gun brought its own hold (Data/holds/<archetype>.json): the hands go where it says, nothing is fitted. */
	bool HasHold() const { return bHasHold; }
	FName GetArchetype() const { return Archetype; }

	/** A rail optic is mounted (the gun's irons fold away, aiming looks through the optic). */
	bool IsOpticMounted() const { return bOpticMounted; }
	/** The optic on the rail (null with factory sights). */
	const UStaticMeshComponent* GetOptic() const { return bOpticMounted ? Optic.Get() : nullptr; }

	/** The gun carries its own optic (the energy line's built-in red dots) and no rail optic replaces it. */
	bool HasBuiltInOptic() const;

	/** glTF gun space (m, x right / y up / z barrel) -> imported mesh space (cm, gun along +Y). */
	static FVector GltfToMesh(float X, float Y, float Z) { return FVector(X * 100.0f, Z * 100.0f, Y * 100.0f); }
	/** glTF Euler XYZ (rad) -> mesh space rotation. */
	static FQuat GltfEulerToMesh(float RX, float RY, float RZ);

	/** Imported mesh space (gun along +Y) -> rig space (gun along +X). */
	static FVector MeshToRig(const FVector& V) { return FVector(V.Y, -V.X, V.Z); }

	/** Applies owner visibility rules to every mesh (third person: hide from owner while in first person). */
	void SetOwnerNoSeeAll(bool bNoSee);

private:
	UStaticMeshComponent* MakeMesh(FName Name, UStaticMesh* Mesh);

	UPROPERTY(Transient)
	TObjectPtr<USceneComponent> GunSpace;

	UPROPERTY(Transient)
	TObjectPtr<UStaticMeshComponent> Body;

	UPROPERTY(Transient)
	TArray<TObjectPtr<UStaticMeshComponent>> PartComponents;

	UPROPERTY(Transient)
	TObjectPtr<UStaticMeshComponent> Spare;

	UPROPERTY(Transient)
	TObjectPtr<UStaticMeshComponent> Optic;

	TMap<FName, FTransform> Rest;      // relative to the parent part (or the gun)
	TMap<FName, FTransform> RootRest;  // relative to the gun
	FVector Foregrip = FVector::ZeroVector;
	FSOHandGrip RightGrip;
	FSOHandGrip LeftGrip;
	FSOFingerPose RightFingers;
	FSOFingerPose LeftFingers;
	FSOFingerPose CurFingers;
	/** The gun's own hold, when it brought one. */
	FSOGunHold Hold;
	bool bHasHold = false;
	/** Where the off hand was when the current reload segment began (anchor "cur"). */
	FSOHandGrip CurGrip;
	float LeftSpinFree = 0.0f;
	float CurSpinFree = 0.0f;
	FTransform ShowLead = FTransform::Identity;
	FTransform ShowLeft = FTransform::Identity;
	/** What the reload's hand is bringing (ApplyPose), the hold it will have on it at its place in the choreography (rig
	 *  space), and how much of it is still the hand's (1 on the way, 0 as it arrives). */
	TWeakObjectPtr<UStaticMeshComponent> CarriedPart;
	FSOHandGrip CarriedGrip;
	float CarriedShare = 0.0f;
	int32 LastSegment = -1;
	FName Archetype;
	bool bShown = true;
	/** Hidden from its owner (the third-person copy while its owner looks through first person): a part made later is too. */
	bool bOwnerNoSee = false;
	bool bOpticMounted = false;
	float BarrelSpin = 0.0f;
	bool bHandgun = false;
	bool bSnugGrip = false;

	/** A part's current transform in mesh space (nested parts included). */
	FTransform PartInMesh(const UStaticMeshComponent* Comp) const;
	FVector Muzzle = FVector::ZeroVector;
	bool bBuilt = false;
};
