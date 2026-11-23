#pragma once

#include "CoreMinimal.h"

/** One of the character builder's groups (Data/creator.json "groups"): its sliders are the body's morph targets
 *  face_<key>, each -1..1; a group with none (the body and its skin, the hair) chooses a tone instead. */
struct FSOCreatorGroup
{
	FName Id;
	FString Name;
	FString Line;
	/** (key, the slider's name); a slider shows only on a body that has its morph target */
	TArray<TPair<FName, FString>> Sliders;
};

/** A tone the builder offers (a linear tint over the body's own maps). */
struct FSOCreatorTone
{
	FString Name;
	FLinearColor Tint = FLinearColor::White;
};

/**
 * The character builder's words and choices (the armoury's CHARACTER tab; the owner, 2026-11-16: "the face will be
 * heavily customizable in game when the player first starts"), read once from Data/creator.json (SOData: in a package
 * from the staged data). The first tone of each list is the body's own (what alpha 0 on the outfit means).
 */
/** A beard the builder offers (none = clean-shaven: the base face), and the bodies whose faces carry it. */
struct FSOCreatorBeard
{
	FName Id;
	FString Name;
};

struct SOUI_API FSOCreatorData
{
	TArray<FSOCreatorGroup> Groups;
	TArray<FSOCreatorBeard> Beards;
	TArray<FName> BeardBodies;
	TArray<FSOCreatorTone> SkinTones;
	TArray<FSOCreatorTone> HairColours;

	static const FSOCreatorData& Get();
	const FSOCreatorGroup* Find(FName Id) const;
	/** Every face key the builder names (all groups). */
	TArray<FName> AllKeys() const;
};
