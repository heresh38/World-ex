#pragma once

#include "CoreMinimal.h"

class AActor;
class ASOEnemy;
class UObject;

/** What the Altered share (private to their files): each species is one file in this folder, and this is the only
 *  thing they have in common besides ASOEnemy. */
namespace SOAltered
{
	extern const FLinearColor VoidColor;
	extern const TCHAR* const GlowMaterial;

	/** Mesh, clips and capsule of one of the Altered (/Game/Characters/<Name>/SK_<Name>). */
	// the body /Game/Characters/<Name>/SK_<Name> with its clips, on a capsule Radius x HalfHeight at its own size, all of
	// it made Scale times bigger (the heavy ranks wear the heavy Sarketh larger: the sheet's "bigger boss version")
	void Configure(ASOEnemy* E, const TCHAR* Name, float Radius, float HalfHeight, float Scale = 1.0f);

	float Now(const UObject* O);

	void FaceToward(AActor* Self, const FVector& Point, float DeltaSeconds, float Rate);

	/** A void bolt from Start at Target (the shooter's variant scales its damage). */
	void FireBolt(ASOEnemy* From, const FVector& Start, AActor* Target, float Damage, float Speed, float SpreadDeg);
}
