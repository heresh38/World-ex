#pragma once

#include "CoreMinimal.h"

/**
 * Keyframed reloads.
 * A reload is a list of segments; each segment has channels sampled over its normalised time:
 *   gun    holder offset in view space [x right, y up, z back (m), pitch (+muzzle up), yaw (+muzzle left), roll (rad)]
 *   mag / spare / bio  part offsets from the rest pose in glTF gun space [dx, dy, dz (m), rx, ry, rz (rad, XYZ order)]
 *   shell / round      loose props, absolute in glTF gun space; loader [x, y, z, spin]
 *   bolt / charge / slide / pump  metres back along the bore; chargeUp lifts the charging handle
 *   boltRot / crane / spin / hatch  rotations (rad): bolt handle, revolver crane, cylinder, horror hatch
 *   hand   the off (left) hand: anchor (fore, mag, spare, magbase, bolt, charge, slide, pump, cyl, ejector, loader,
 *          shell, round, hatch, biomass, pouch, free, cur) + offsets
 * and timed events (drop, spare, seat, grant, shell, round, eject, loader, release, husk, bio, glow, drip, sfx).
 * Magazine guns get their ammo on "seat", pump / bolt-action one round per "grant". glTF gun space: x right, y up,
 * z = barrel.
 */
enum class ESOEase : uint8
{
	Smoother,
	Linear,
	Out,
	In,
	Back
};

struct SOCOMBAT_API FSOKey
{
	float T = 0.0f;
	float V[6] = { 0, 0, 0, 0, 0, 0 };
	ESOEase Ease = ESOEase::Smoother;
	FName Anchor; // hand channel only

	FSOKey() = default;
	FSOKey(float InT, std::initializer_list<float> Values, ESOEase InEase = ESOEase::Smoother, FName InAnchor = NAME_None);
};

struct SOCOMBAT_API FSOReloadEvent
{
	float T = 0.0f;
	FName Name;
	FName Arg;
	int32 Count = 0; // grant / shell / round
};

struct SOCOMBAT_API FSOReloadSegment
{
	float Duration = 1.0f;
	TMap<FName, TArray<FSOKey>> Channels;
	TArray<FSOReloadEvent> Events;
};

/** The sampled pose; rigs resolve the hand anchors against their own parts. */
struct SOCOMBAT_API FSOReloadPose
{
	float Gun[6] = { 0, 0, 0, 0, 0, 0 };
	float Mag[6] = { 0, 0, 0, 0, 0, 0 };
	float Spare[6] = { 0, 0, 0, 0, 0, 0 };
	float Bio[6] = { 0, 0, 0, 0, 0, 0 };
	float Shell[6] = { 0, 0, 0, 0, 0, 0 };
	float Round[6] = { 0, 0, 0, 0, 0, 0 };
	float Loader[4] = { 0, 0, 0, 0 };
	float Bolt = 0.0f;
	float Charge = 0.0f;
	float ChargeUp = 0.0f;
	float Slide = 0.0f;
	float Pump = 0.0f;
	float BoltRot = 0.0f;
	float Crane = 0.0f;
	float Spin = 0.0f;
	float Hatch = 0.0f;

	/** Hand: interpolate from anchor A (+ offsets) to anchor B with HandAlpha. */
	bool bHand = false;
	FName HandAnchorA, HandAnchorB;
	float HandA[6] = { 0, 0, 0, 0, 0, 0 };
	float HandB[6] = { 0, 0, 0, 0, 0, 0 };
	float HandAlpha = 0.0f;
	/** Counts segments, so rigs can remember where the hand was when one began (anchor "cur"). */
	int32 Segment = 0;

	bool bMagVisible = true;
	bool bSpareVisible = false;
	/** The new magazine is home: from here on the mag sits at rest (the old mag channel no longer applies). */
	bool bMagSeated = false;
	bool bBio = true;        // horror: the biomass is in the gun
	bool bRounds = true;     // revolver: rounds in the cylinder
	bool bLoader = false;    // revolver: speedloader in hand
	bool bShell = false;     // pump: a shell in hand
	bool bRound = false;     // bolt-action: a cartridge in hand

	void Reset() { *this = FSOReloadPose(); }
};

class SOCOMBAT_API FSOReloadPlayer
{
public:
	/** Starts a sequence; segment durations are absolute seconds. LoopFrom..LoopTo = per-round segments that firing
	 *  may cut short (pump, bolt-action). */
	void Start(TArray<FSOReloadSegment>&& InSegments, int32 InLoopFrom = -1, int32 InLoopTo = -1);
	void Cancel();

	/** Firing during a per-round reload: skip to the closing segment (bolt closes / hand back on the pump). */
	bool Interrupt();
	bool IsInterruptible() const { return LoopFrom >= 0 && Index >= LoopFrom && Index < Segments.Num() - 1; }

	bool IsActive() const { return Segments.Num() > 0; }
	float GetDuration() const { return Duration; }
	float GetElapsed() const { return Elapsed; }
	float GetProgress() const { return Duration > 0.0f ? FMath::Clamp(Elapsed / Duration, 0.0f, 1.0f) : 0.0f; }

	/** Advances; OutEvents receives every event crossed. Returns true on the step the sequence finished. */
	bool Update(float DeltaTime, TArray<FSOReloadEvent>& OutEvents);

	/** A shot left the barrel: blowback (slide / carrier) and, for pump / bolt-action, the cycling after it. */
	void NotifyShot(FName Archetype);

	/** Pistol slide locks back on an empty magazine. */
	void SetSlideLock(bool bLocked) { bSlideLock = bLocked; }

	const FSOReloadPose& GetPose() const { return Pose; }

	static float Ease(ESOEase Mode, float X);
	static void SampleKeys(const TArray<FSOKey>& Keys, float T, int32 Count, float* Out);

private:
	void Sample(const FSOReloadSegment& Segment, float T);
	void FireEvents(const FSOReloadSegment& Segment, float T, TArray<FSOReloadEvent>& OutEvents);
	void Idle(float DeltaTime, TArray<FSOReloadEvent>& OutEvents);

	TArray<FSOReloadSegment> Segments;
	int32 Index = 0;
	int32 LoopFrom = -1;
	int32 LoopTo = -1;
	float Local = 0.0f;
	float Elapsed = 0.0f;
	float Duration = 0.0f;
	TSet<int32> FiredEvents;
	FSOReloadPose Pose;
	float KickTime = 10.0f;
	FName KickArch;
	bool bSlideLock = false;

	// post-shot cycling (pump rack, bolt throw)
	FSOReloadSegment Cycle;
	float CycleDelay = 0.0f;
	float CycleLocal = -1.0f;
	TSet<int32> CycleFired;
};

namespace SOReload
{
	/** Magazine reload (tactical, or empty = adds the chambering), scaled so the tactical one lasts ReloadTime. */
	SOCOMBAT_API TArray<FSOReloadSegment> BuildMagReload(FName Archetype, bool bEmpty, float ReloadTime);

	/** The reload for any archetype (reload.js start): magazine guns, revolver, pump and bolt-action (Rounds loaded one
	 *  at a time; OutLoopFrom / OutLoopTo mark those segments), horror biomass, energy cell swap. */
	SOCOMBAT_API TArray<FSOReloadSegment> BuildReload(FName Archetype, bool bEnergy, bool bHorror, bool bEmpty, float ReloadTime, int32 Rounds,
		int32& OutLoopFrom, int32& OutLoopTo);

	/** The cycling after a shot (pump rack, bolt throw); empty when the gun has none. Delay: seconds after the shot. */
	SOCOMBAT_API bool BuildCycle(FName Archetype, FSOReloadSegment& OutCycle, float& OutDelay);

	/** The manual of arms an archetype reloads with. The Void Requiem set (vr_*) was built on the same parts as the
	 *  kinetic guns (cell magazine + charging handle, straight-pull bolt, slide, pump and shells, crane and cylinder),
	 *  so each maps to that family; the belt-fed gun, the fusion rifle and the launcher have sequences of their own. */
	SOCOMBAT_API FName GetStyle(FName Archetype);

	/** Total duration of a sequence. */
	SOCOMBAT_API float GetDuration(const TArray<FSOReloadSegment>& Segments);
}
