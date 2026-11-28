#pragma once

#include "CoreMinimal.h"

/**
 * How a gun is SHOWN to its holder's own eyes while it is reloaded (the owner, 2026-11-27, a showcase of another game's
 * first-person guns: "this is how my first person must look and feel ... these reloads, these animations, this is the
 * level i want": a quality target only, nothing of its names or look). There a reload swings the gun up large into the
 * middle of the picture, its side and its magazine well turned to the eyes, the hands working in full view, the gun
 * turning from one presentation to the next with each thing the hand does (the magazine out, the fresh one in, the
 * handle racked), with weight: it overshoots, settles, and jolts as parts strike home.
 *
 * One show: where the part the reload works (USOViewmodelComponent::KeepReloadWork: the magazine well, a cylinder, a
 * port, a flap) lies in the picture and how the gun is turned there, in the view's own frame, for the field of view the
 * player has set. A style (SOReload::GetStyle; an archetype may have its own) has a base show and one for any of the
 * places the support hand goes (the choreography's hand anchors: fore, mag, pouch, spare, magbase, bolt, charge, slide,
 * pump, cyl, ejector, loader, shell, round, hatch, biomass): as the hand travels from one to the next the gun turns from
 * the one show to the other, on a spring. Data/reload_shows.json, read at runtime (SOData), so a pose is tuned without
 * building.
 */
struct SOCHARACTER_API FSOReloadShow
{
	/** cm ahead of the eyes; the share of the picture across and down; the muzzle up and in toward the middle (degrees);
	 *  the top rolled to the right (degrees: the left flank and the underside turn to the eyes; negative: the top and
	 *  the right flank). */
	float V[6] = { 38.0f, 0.55f, 0.64f, 30.0f, 20.0f, 45.0f };

	float Ahead() const { return V[0]; }
	float Across() const { return V[1]; }
	float Down() const { return V[2]; }
	float Pitch() const { return V[3]; }
	float Yaw() const { return V[4]; }
	float Roll() const { return V[5]; }

	static FSOReloadShow Lerp(const FSOReloadShow& A, const FSOReloadShow& B, float T)
	{
		FSOReloadShow Out;
		for (int32 i = 0; i < 6; ++i)
		{
			Out.V[i] = FMath::Lerp(A.V[i], B.V[i], T);
		}
		return Out;
	}
};

struct SOCHARACTER_API FSOReloadStyleShow
{
	FSOReloadShow Base;
	TMap<FName, FSOReloadShow> Anchors;

	const FSOReloadShow& For(FName Anchor) const
	{
		const FSOReloadShow* Show = Anchors.Find(Anchor);
		return Show ? *Show : Base;
	}
};

/** What one beat of handling a gun (a reload's sound events: the magazine let go, pushed home, slapped, a handle racked
 *  back and let fly) does to the gun in the hands and to the view: the furthest it throws each, cm and degrees. The gun:
 *  right, up, back, the muzzle up, the muzzle left, the top to the left. The view: up, left, a roll to the right. */
struct SOCHARACTER_API FSOHandlingBeat
{
	FVector GunMove = FVector::ZeroVector;
	FVector GunTurn = FVector::ZeroVector;
	FVector View = FVector::ZeroVector;
};

struct SOCHARACTER_API FSOReloadShowData
{
	FSOReloadStyleShow Default;
	TMap<FName, FSOReloadStyleShow> Styles;
	TMap<FName, FSOHandlingBeat> Beats;
	/** The show's spring (how fast, and how much it overshoots: 1 = not at all), and the jolts'. */
	float Omega = 11.0f;
	float Zeta = 0.62f;
	float JoltOmega = 17.0f;
	float JoltZeta = 0.45f;
	/** How much of the choreography's own keyed moves of the gun rides on top of the show (the shows carry the pose). */
	float GunMoves = 0.35f;
	/** Seconds the gun's turn runs AHEAD of the hand where the hand's next place is a handle or a slide, which the gun is
	 *  turned right over for (USOViewmodelComponent::UpdateHold). */
	float HandleLead = 0.12f;

	/** The archetype's own, else its style's, else the default. */
	const FSOReloadStyleShow& For(FName Archetype, FName Style) const;
	const FSOHandlingBeat* Beat(FName Event) const { return Beats.Find(Event); }

	static const FSOReloadShowData& Get();
};
