#pragma once

#include "CoreMinimal.h"

/**
 * How a body holds one class of gun in third person and stands with it (the owner, 2026-11-23: "a professional third-
 * person shooter character with a confident, aggressive, disciplined military combat stance"; one profile per class of
 * gun, configurable, never a pose per gun). Data/stances.json, read at runtime (SOData): every class, and which class a
 * gun's family is. Three states share it: RELAXED (out of a fight: the gun carried low, the arms easy), READY (the gun
 * up and forward on the shoulder, the elbows bent out, the knees bent, leaning in) and on the SIGHTS (shouldered, the
 * cheek on the stock).
 */
struct SOCHARACTER_API FSOStance
{
	FName Id;
	// The gun. A long gun's butt rides the right shoulder pocket: shifted this much at the ready and on the sights (cm,
	// actor axes: forward, right, up); its muzzle dips this much at the ready (degrees). A handgun's grip from the
	// shoulders' middle (cm, forward, right, up), at the ready and aimed. Relaxed: carried from the chest point (cm) and
	// turned against the facing (pitch, yaw, roll).
	FVector ReadyShift = FVector(0.0f, 0.0f, 3.0f);
	FVector AimShift = FVector(1.5f, -2.5f, 7.0f);
	float ReadyDip = 3.0f;
	FVector HandHold = FVector(38.0f, 6.0f, -2.0f);
	FVector HandAimHold = FVector(44.0f, 5.0f, 2.0f);
	FVector RelaxOffset = FVector(24.0f, 8.0f, -24.0f);
	FRotator RelaxRot = FRotator(-32.0f, -38.0f, -16.0f);
	// The arms (0 the firing arm, 1 the support arm). Each elbow leans this far out from straight down before the wrist
	// asks anything; it may then swing between the least and the most (radians from straight down: + out round the arm's
	// outside, - toward the body). Shoulders: how much of the collarbones' forward pull is taken out (0..1: the shoulders
	// square, the chest open; all of it rounded them).
	float ElbowOut[2] = { 0.8f, 0.8f };
	float ElbowLeast[2] = { 0.1f, 0.15f };
	float ElbowMost[2] = { 1.45f, 1.15f };
	float Shoulders = 0.5f;
	// The body: the trunk turned toward the gun and leaning forward (degrees, at the ready and aimed), the chin down
	// (degrees), the hips lowered (cm: the knees bent), and standing the support foot forward and the feet wider (cm).
	float Blade[2] = { 6.0f, 10.0f };
	float Lean[2] = { 7.0f, 10.0f };
	float HeadDown = 4.0f;
	float Knees = 5.0f;
	float Stagger = 18.0f;
	float Width = 6.0f;
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

/** What the animation needs of the stance each frame (players only: a creature keeps its own way of holding). */
struct SOCHARACTER_API FSOStanceInputs
{
	bool bPlayer = false;
	/** 0 relaxed, 1 at the ready or on the sights. */
	float Ready = 0.0f;
	float ElbowOut[2] = { 0.45f, 0.45f };
	float ElbowLeast[2] = { -0.5f, -0.5f };
	float ElbowMost[2] = { 1.45f, 0.9f };
	float Shoulders = 0.0f;
	float HeadDown = 0.0f;
	float Knees = 0.0f;
	float Stagger = 0.0f;
	float Width = 0.0f;
};
