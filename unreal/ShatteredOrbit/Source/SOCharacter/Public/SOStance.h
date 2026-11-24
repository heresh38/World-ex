#pragma once

#include "CoreMinimal.h"

/**
 * How a body holds one class of gun in third person and stands with it (the owner, 2026-11-23: "a professional third-
 * person shooter character with a confident, aggressive, disciplined military combat stance"; one profile per class of
 * gun, configurable, never a pose per gun). Data/stances.json, read at runtime (SOData): every class, and which class a
 * gun's family is. Three states share it: RELAXED (out of a fight: the gun carried low, the arms easy, the feet a little
 * apart), READY (the gun up and forward on the shoulder, the elbows out at the sides, the knees bent over the toes, the
 * support foot forward, leaning in) and on the SIGHTS (shouldered, the cheek on the stock).
 */
struct SOCHARACTER_API FSOStance
{
	FName Id;
	// The gun. A long gun's butt rides the right shoulder pocket: shifted this much at the ready and on the sights (cm,
	// actor axes: forward, right, up); its muzzle dips this much at the ready (degrees). A handgun's grip from the
	// shoulders' middle (cm, forward, right, up), at the ready and aimed. Relaxed: the gun at the ready turned by
	// RelaxRot (pitch, yaw, roll in the body's facing: the muzzle down and turned in) about a point between the firing
	// hand's place on it (RelaxPivot 0) and the support hand's (1: a launcher's fore end is so far out that turned about
	// the firing hand it left the support arm's reach), and moved by RelaxOffset (cm, forward, right, up): from the eyes
	// it stays in the lower right of the picture. RelaxReach: relaxed, the gun comes in until the support hand is within
	// this share of its arm (the arms easy; 0 = as at the ready, USOViewmodelComponent::SupportReach).
	FVector ReadyShift = FVector(0.0f, 0.0f, 2.0f);
	FVector AimShift = FVector(1.5f, -2.5f, 7.0f);
	float ReadyDip = 0.0f;
	FVector HandHold = FVector(38.0f, 6.0f, -2.0f);
	FVector HandAimHold = FVector(44.0f, 5.0f, 2.0f);
	FVector RelaxOffset = FVector(-2.0f, 0.0f, -5.0f);
	FRotator RelaxRot = FRotator(-14.0f, -6.0f, -8.0f);
	float RelaxPivot = 0.0f;
	float RelaxReach = 0.0f;
	// The gun framed in the picture off the sights (the owner, 2026-11-23: "need to be in the screen more just like the
	// pistol/hand cannon ... this fix should be automated because what if we have a fov slider"): the camera settles up
	// to FrameDrop cm under the eyes so that the gun's sight at the ready lies FrameDown of the way down the picture, for
	// the field of view and the picture's shape the player has (0 = in the eyes). The body is not moved for it: moved up
	// or in, the long guns put the firing elbow across the chest.
	float FrameDown = 0.66f;
	float FrameDrop = 0.0f;
	// ...and rides up to FrameSide cm toward the gun's side so that its sight lies FrameAcross of the way across: the gun
	// nearer the middle, as a handgun is, and the slide onto the sights that much shorter (from the body's middle it was
	// 17 cm across in a fifth of a second).
	float FrameAcross = 0.62f;
	float FrameSide = 0.0f;
	// ...and sits FrameBack cm behind the eyes (inside the head, which its own camera never sees): a shouldered gun's sight
	// is only 13 to 19 cm ahead of the eyes, so from them it lies far out in the picture's corner whatever the camera's
	// height; seen from a little further back it lies nearer the middle, as a handgun held out does.
	float FrameBack = 0.0f;
	// The arms (0 the firing arm, 1 the support arm). Each elbow is carried at a swing round the line from its shoulder to
	// its wrist (radians from straight down, + out round the arm's outside, - in toward the body), at the ready and on the
	// sights; it goes WristShare of the way from there toward where its wrist runs straightest, stays between the least
	// and the most, and comes no further out than leaves its wrist within WristMax (degrees between the forearm and the
	// hand: the hand's place on the gun is fitted and stays). Shoulders: how much of the collarbones' forward pull is taken
	// out at the ready and on the sights (0..1: square shoulders, an open chest; all of the pull rounded them).
	float ElbowSwing[2] = { 0.8f, 0.35f };
	float ElbowSwingAim[2] = { 0.7f, 0.3f };
	float WristShare[2] = { 0.0f, 0.0f };
	float ElbowLeast[2] = { 0.3f, 0.0f };
	float ElbowMost[2] = { 1.45f, 1.2f };
	float WristMax[2] = { 72.0f, 66.0f };
	float Shoulders[2] = { 0.6f, 0.35f };
	// The trunk: turned toward the gun (blade) and leaning forward (lean), degrees at the ready and on the sights; the hips
	// turned with it standing (degrees, relaxed and at the ready: the support hip forward); the chin down (degrees).
	float Blade[2] = { 8.0f, 18.0f };
	float Lean[2] = { 7.0f, 10.0f };
	float Hips[2] = { 4.0f, 16.0f };
	float HeadDown = 4.0f;
	// The legs, relaxed and at the ready: the hips lowered (cm: the knees bent), standing the support foot ahead of the
	// firing foot and the feet further apart than the clip stands them (cm); the toes turned out at the ready (degrees: the
	// support foot, the firing foot; relaxed under half that); the knees carried out over the toes (cm), never in.
	float Knees[2] = { 1.0f, 7.0f };
	float Stagger[2] = { 6.0f, 28.0f };
	float Width[2] = { 6.0f, 14.0f };
	float ToeOut[2] = { 14.0f, 32.0f };
	float KneeOut = 2.0f;
	// Standing at the ready, the feet step round under an aim that turned this far (degrees; out of the stance the body's
	// own turn-in-place angle).
	float TurnStep = 18.0f;
};

struct SOCHARACTER_API FSOStanceData
{
	TMap<FName, FSOStance> Classes;
	/** A gun's family (USOWeaponData::Family) -> its class. */
	TMap<FName, FName> Families;
	/** How long the gun stays up after the last shot, aim, reload or hit (s), and how fast it comes up and goes down. */
	float CombatSeconds = 8.0f;
	float RaiseTime = 0.18f;
	float LowerTime = 0.7f;

	/** The class of a gun's family (the rifle's when the family is unknown). */
	const FSOStance& For(FName Family) const;
	static const FSOStanceData& Get();
};

/** What the animation needs of the stance each frame, already blended by the state (players only: a creature keeps its
 *  own way of holding). */
struct SOCHARACTER_API FSOStanceInputs
{
	bool bPlayer = false;
	/** 0 relaxed, 1 at the ready or on the sights (eased). */
	float Ready = 0.0f;
	/** How far on the sights (the viewmodel's eased aim): a long gun stays shouldered there and the trunk bows with a
	 *  downward aim. */
	float Aim = 0.0f;
	float ElbowSwing[2] = { 0.0f, 0.0f };
	float WristShare[2] = { 1.0f, 0.6f };
	float ElbowLeast[2] = { -0.5f, -0.5f };
	float ElbowMost[2] = { 1.45f, 0.9f };
	/** Degrees each wrist may bend at most (the elbow comes no further out). */
	float WristMax[2] = { 72.0f, 66.0f };
	float Shoulders = 0.0f;
	float HeadDown = 0.0f;
	/** Degrees the hips turn (the support hip forward). */
	float Hips = 0.0f;
	float Knees = 0.0f;
	float Stagger = 0.0f;
	float Width = 0.0f;
	/** Degrees each foot's toes turn out: the left (support) foot, the right (firing) foot. */
	float ToeOut[2] = { 0.0f, 0.0f };
	float KneeOut = 0.0f;
	/** Degrees of aim turned on the spot before the feet step round, at the ready. */
	float TurnStep = 36.0f;
};
