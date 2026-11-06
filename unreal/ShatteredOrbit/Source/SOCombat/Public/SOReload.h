#pragma once

#include "CoreMinimal.h"

/**
 * Keyframed reloads, ported from the browser build's src/game/reload.js.
 * A reload is a list of segments; each segment has channels sampled over its normalised time:
 *   gun   holder offset in view space [x right, y up, z back (m), pitch (+muzzle up), yaw (+muzzle left), roll (rad)]
 *   mag / spare  part offsets from the rest pose in glTF gun space [dx, dy, dz (m), rx, ry, rz (rad, XYZ order)]
 *   bolt  metres back along the bore
 *   hand  the off (left) hand: anchor (fore, mag, spare, bolt, pouch, magbase) + offsets + rotation
 * and timed events (drop, spare, seat, sfx). Ammo arrives on "seat". glTF gun space: x right, y up, z = barrel.
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
	float Bolt = 0.0f;

	/** Hand: interpolate from anchor A (+ offsets) to anchor B with HandAlpha; rotation lerped likewise. */
	bool bHand = false;
	FName HandAnchorA, HandAnchorB;
	float HandA[6] = { 0, 0, 0, 0, 0, 0 };
	float HandB[6] = { 0, 0, 0, 0, 0, 0 };
	float HandAlpha = 0.0f;

	bool bMagVisible = true;
	bool bSpareVisible = false;

	void Reset() { *this = FSOReloadPose(); }
};

class SOCOMBAT_API FSOReloadPlayer
{
public:
	/** Starts a sequence; segment durations are absolute seconds. */
	void Start(TArray<FSOReloadSegment>&& InSegments);
	void Cancel();

	bool IsActive() const { return Segments.Num() > 0; }
	float GetDuration() const { return Duration; }
	float GetElapsed() const { return Elapsed; }
	float GetProgress() const { return Duration > 0.0f ? FMath::Clamp(Elapsed / Duration, 0.0f, 1.0f) : 0.0f; }

	/** Advances; OutEvents receives every event crossed. Returns true on the step the sequence finished. */
	bool Update(float DeltaTime, TArray<FSOReloadEvent>& OutEvents);

	/** A shot left the barrel: bolt / carrier blowback envelope when no reload is running. */
	void NotifyShot() { KickTime = 0.0f; }

	const FSOReloadPose& GetPose() const { return Pose; }

	static float Ease(ESOEase Mode, float X);
	static void SampleKeys(const TArray<FSOKey>& Keys, float T, int32 Count, float* Out);

private:
	void Sample(const FSOReloadSegment& Segment, float T);
	void FireEvents(const FSOReloadSegment& Segment, float T, TArray<FSOReloadEvent>& OutEvents);

	TArray<FSOReloadSegment> Segments;
	int32 Index = 0;
	float Local = 0.0f;
	float Elapsed = 0.0f;
	float Duration = 0.0f;
	TSet<int32> FiredEvents;
	FSOReloadPose Pose;
	float KickTime = 10.0f;
};

namespace SOReload
{
	/** Magazine reload (tactical, or empty = adds the chambering), scaled so the tactical one lasts ReloadTime. */
	SOCOMBAT_API TArray<FSOReloadSegment> BuildMagReload(FName Archetype, bool bEmpty, float ReloadTime);

	/** Total duration of BuildMagReload without building it twice. */
	SOCOMBAT_API float GetDuration(const TArray<FSOReloadSegment>& Segments);
}
