#include "SOReload.h"

namespace
{
	const FName NGun(TEXT("gun"));
	const FName NMag(TEXT("mag"));
	const FName NSpare(TEXT("spare"));
	const FName NBolt(TEXT("bolt"));
	const FName NHand(TEXT("hand"));
	const FName NFore(TEXT("fore"));
	const FName NPouch(TEXT("pouch"));
	const FName NDrop(TEXT("drop"));
	const FName NSeat(TEXT("seat"));
	const FName NSfx(TEXT("sfx"));
}

FSOKey::FSOKey(float InT, std::initializer_list<float> Values, ESOEase InEase, FName InAnchor)
	: T(InT)
	, Ease(InEase)
	, Anchor(InAnchor)
{
	int32 i = 0;
	for (float Value : Values)
	{
		if (i < 6)
		{
			V[i++] = Value;
		}
	}
}

float FSOReloadPlayer::Ease(ESOEase Mode, float X)
{
	X = FMath::Clamp(X, 0.0f, 1.0f);
	switch (Mode)
	{
	case ESOEase::Linear: return X;
	case ESOEase::Out: return 1.0f - FMath::Pow(1.0f - X, 3.0f);
	case ESOEase::In: return X * X * X;
	case ESOEase::Back:
	{
		const float C = 1.9f;
		return 1.0f + (C + 1.0f) * FMath::Pow(X - 1.0f, 3.0f) + C * FMath::Square(X - 1.0f);
	}
	default: return X * X * X * (X * (X * 6.0f - 15.0f) + 10.0f); // smootherstep
	}
}

void FSOReloadPlayer::SampleKeys(const TArray<FSOKey>& Keys, float T, int32 Count, float* Out)
{
	if (Keys.Num() == 0)
	{
		for (int32 i = 0; i < Count; ++i) { Out[i] = 0.0f; }
		return;
	}
	int32 K = 0;
	while (K < Keys.Num() - 1 && Keys[K + 1].T <= T) { ++K; }
	const FSOKey& A = Keys[K];
	const FSOKey& B = Keys[FMath::Min(K + 1, Keys.Num() - 1)];
	if (&A == &B || T <= A.T)
	{
		for (int32 i = 0; i < Count; ++i) { Out[i] = A.V[i]; }
		return;
	}
	const float F = FMath::Min(1.0f, (T - A.T) / FMath::Max(1e-6f, B.T - A.T));
	const float W = Ease(B.Ease, F);
	for (int32 i = 0; i < Count; ++i) { Out[i] = A.V[i] + (B.V[i] - A.V[i]) * W; }
}

void FSOReloadPlayer::Start(TArray<FSOReloadSegment>&& InSegments)
{
	Segments = MoveTemp(InSegments);
	Index = 0;
	Local = 0.0f;
	Elapsed = 0.0f;
	Duration = SOReload::GetDuration(Segments);
	FiredEvents.Reset();
	Pose.Reset();
	if (Segments.Num() > 0)
	{
		Sample(Segments[0], 0.0f);
	}
}

void FSOReloadPlayer::Cancel()
{
	Segments.Reset();
	Pose.Reset();
}

void FSOReloadPlayer::FireEvents(const FSOReloadSegment& Segment, float T, TArray<FSOReloadEvent>& OutEvents)
{
	for (int32 i = 0; i < Segment.Events.Num(); ++i)
	{
		const FSOReloadEvent& Event = Segment.Events[i];
		const int32 Id = Index * 1000 + i;
		if (Event.T > T || FiredEvents.Contains(Id))
		{
			continue;
		}
		FiredEvents.Add(Id);
		if (Event.Name == NDrop)
		{
			Pose.bMagVisible = false;
		}
		else if (Event.Name == NSpare)
		{
			Pose.bSpareVisible = true;
		}
		else if (Event.Name == NSeat)
		{
			Pose.bSpareVisible = false;
			Pose.bMagVisible = true;
			FMemory::Memzero(Pose.Mag, sizeof(Pose.Mag));
		}
		OutEvents.Add(Event);
	}
}

void FSOReloadPlayer::Sample(const FSOReloadSegment& Segment, float T)
{
	if (const TArray<FSOKey>* Keys = Segment.Channels.Find(NGun)) { SampleKeys(*Keys, T, 6, Pose.Gun); }
	if (const TArray<FSOKey>* Keys = Segment.Channels.Find(NMag)) { SampleKeys(*Keys, T, 6, Pose.Mag); }
	if (const TArray<FSOKey>* Keys = Segment.Channels.Find(NSpare)) { SampleKeys(*Keys, T, 6, Pose.Spare); }
	if (const TArray<FSOKey>* Keys = Segment.Channels.Find(NBolt)) { SampleKeys(*Keys, T, 1, &Pose.Bolt); }
	if (const TArray<FSOKey>* Keys = Segment.Channels.Find(NHand); Keys && Keys->Num() > 0)
	{
		int32 K = 0;
		while (K < Keys->Num() - 1 && (*Keys)[K + 1].T <= T) { ++K; }
		const FSOKey& A = (*Keys)[K];
		const FSOKey& B = (*Keys)[FMath::Min(K + 1, Keys->Num() - 1)];
		const float F = (&A == &B || T <= A.T) ? 0.0f : FMath::Min(1.0f, (T - A.T) / FMath::Max(1e-6f, B.T - A.T));
		Pose.bHand = true;
		Pose.HandAnchorA = A.Anchor;
		Pose.HandAnchorB = B.Anchor;
		FMemory::Memcpy(Pose.HandA, A.V, sizeof(Pose.HandA));
		FMemory::Memcpy(Pose.HandB, B.V, sizeof(Pose.HandB));
		Pose.HandAlpha = Ease(B.Ease, F);
	}
}

bool FSOReloadPlayer::Update(float DeltaTime, TArray<FSOReloadEvent>& OutEvents)
{
	KickTime += DeltaTime;
	if (Segments.Num() == 0)
	{
		// Blowback: the carrier snaps back and returns after a shot (rifle: 6 cm).
		const float K = KickTime;
		const float Env = K < 0.03f ? K / 0.03f : FMath::Max(0.0f, 1.0f - (K - 0.03f) / 0.07f);
		Pose.Bolt = 0.06f * Env;
		return false;
	}

	Elapsed += DeltaTime;
	Local += DeltaTime;
	while (Index < Segments.Num() && Local >= Segments[Index].Duration)
	{
		FireEvents(Segments[Index], 1.0001f, OutEvents);
		Sample(Segments[Index], 1.0f);
		Local -= Segments[Index].Duration;
		++Index;
		FiredEvents.Reset();
	}
	if (Index >= Segments.Num())
	{
		Segments.Reset();
		Pose.Reset();
		return true;
	}
	const FSOReloadSegment& Segment = Segments[Index];
	const float T = Local / FMath::Max(Segment.Duration, 1e-4f);
	FireEvents(Segment, T, OutEvents);
	Sample(Segment, T);
	return false;
}

// ---------------------------------------------------------------------------------------------

namespace SOReload
{
	float GetDuration(const TArray<FSOReloadSegment>& Segments)
	{
		float Total = 0.0f;
		for (const FSOReloadSegment& Segment : Segments)
		{
			Total += Segment.Duration;
		}
		return Total;
	}

	static FSOKey Hand(float T, FName Anchor, std::initializer_list<float> Values, ESOEase Ease = ESOEase::Smoother)
	{
		return FSOKey(T, Values, Ease, Anchor);
	}

	static FSOKey Gun(float T, const float* P, ESOEase Ease = ESOEase::Smoother)
	{
		return FSOKey(T, { P[0], P[1], P[2], P[3], P[4], P[5] }, Ease);
	}

	static void AddEvent(FSOReloadSegment& Segment, float T, const TCHAR* Name, const TCHAR* Arg = nullptr)
	{
		FSOReloadEvent Event;
		Event.T = T;
		Event.Name = Name;
		Event.Arg = Arg ? FName(Arg) : NAME_None;
		Segment.Events.Add(Event);
	}

	TArray<FSOReloadSegment> BuildMagReload(FName Archetype, bool bEmpty, float ReloadTime)
	{
		// reload.js magReload, stamped-rifle path: thumb the catch, rock the mag forward off its front lip, toss it,
		// hook the new one on its lip and rock it back; empty: overhand rack of the bolt.
		const bool bRifle = Archetype == TEXT("rifle") || Archetype.IsNone();
		const float Tilt[6] = { -0.04f, 0.03f, 0.03f, 0.22f, 0.32f, -0.55f };
		float T2[6];
		FMemory::Memcpy(T2, Tilt, sizeof(T2));
		T2[5] *= 0.8f;
		T2[3] += 0.06f;
		const float SeatT = 0.88f;
		const float SlapT = SeatT;

		TArray<FSOReloadSegment> Segments;

		// 1. old mag out, new mag in
		FSOReloadSegment Main;
		Main.Duration = 1.0f;
		{
			float TiltDown[6];
			FMemory::Memcpy(TiltDown, Tilt, sizeof(TiltDown));
			TiltDown[1] -= 0.01f;
			float Slap[6];
			FMemory::Memcpy(Slap, T2, sizeof(Slap));
			Slap[1] += 0.012f;
			Slap[3] += 0.05f;
			const float Zero[6] = { 0, 0, 0, 0, 0, 0 };
			Main.Channels.Add(NGun, { Gun(0, Zero), Gun(0.22f, Tilt), Gun(0.4f, TiltDown), Gun(0.5f, Tilt), Gun(0.7f, T2), Gun(0.84f, T2),
				Gun(SlapT, Slap, ESOEase::Out), Gun(1.0f, T2) });
		}
		if (bRifle)
		{
			Main.Channels.Add(NMag, { FSOKey(0, { 0, 0, 0, 0, 0, 0 }), FSOKey(0.25f, { 0, 0, 0, 0, 0, 0 }),
				FSOKey(0.42f, { 0, -0.004f, 0.004f, -0.45f, 0, 0 }), FSOKey(0.55f, { 0, -0.07f, 0.02f, -0.6f, 0, 0.1f }) });
			Main.Channels.Add(NHand, { Hand(0, NFore, { 0, 0, 0, 0, 0, 0 }), Hand(0.22f, NMag, { 0, -0.01f, -0.01f, -0.2f, 0, -0.3f }),
				Hand(0.55f, NMag, { 0, -0.01f, -0.01f, -0.3f, 0, -0.3f }), Hand(0.62f, NPouch, { 0, 0, 0, 0.5f, 0.3f, -0.6f }),
				Hand(0.7f, NPouch, { 0.04f, 0.1f, 0.1f, 0.4f, 0.3f, -0.5f }), Hand(0.74f, NSpare, { 0, 0, 0, -0.25f, 0.05f, -0.25f }),
				Hand(0.84f, NSpare, { 0, 0, 0, -0.2f, 0, -0.2f }), Hand(0.95f, NSpare, { 0, -0.006f, 0, -0.2f, 0, -0.2f }),
				Hand(1.0f, NSpare, { 0, -0.012f, 0, -0.2f, 0, -0.2f }) });
			const float Pre[6] = { 0, -0.035f, 0.012f, -0.42f, 0, 0 };
			Main.Channels.Add(NSpare, { FSOKey(0, { 0, -0.42f, -0.18f, 0.5f, 0.2f, 0.3f }), FSOKey(0.62f, { 0, -0.42f, -0.18f, 0.5f, 0.2f, 0.3f }),
				FSOKey(0.74f, { Pre[0] * 1.7f, Pre[1] * 1.7f, Pre[2] * 1.7f, Pre[3] * 1.7f, 0, 0 }), FSOKey(0.8f, { Pre[0], Pre[1], Pre[2], Pre[3], 0, 0 }),
				FSOKey(0.86f, { 0, -0.004f, 0.003f, -0.32f, 0, 0 }), FSOKey(0.92f, { 0, 0, 0, 0, 0, 0 }, ESOEase::Out) });
			AddEvent(Main, 0.55f, TEXT("drop"));
		}
		else
		{
			// Drop-free: press the release, the empty falls clear on its own.
			Main.Channels.Add(NMag, { FSOKey(0, { 0, 0, 0, 0, 0, 0 }), FSOKey(0.2f, { 0, 0, 0, 0, 0, 0 }), FSOKey(0.32f, { 0, -0.035f, 0, 0.04f, 0, 0 }, ESOEase::In) });
			Main.Channels.Add(NHand, { Hand(0, NFore, { 0, 0, 0, 0, 0, 0 }), Hand(0.2f, NFore, { -0.01f, -0.06f, -0.04f, 0.25f, 0.1f, -0.2f }),
				Hand(0.42f, NPouch, { 0.02f, 0.14f, 0.12f, 0.4f, 0.25f, -0.4f }), Hand(0.62f, NPouch, { 0, 0, 0, 0.5f, 0.3f, -0.6f }),
				Hand(0.74f, NSpare, { 0, 0, 0, -0.25f, 0.05f, -0.25f }), Hand(0.84f, NSpare, { 0, 0, 0, -0.2f, 0, -0.2f }),
				Hand(1.0f, NSpare, { 0, -0.012f, 0, -0.2f, 0, -0.2f }) });
			Main.Channels.Add(NSpare, { FSOKey(0, { 0, -0.42f, -0.18f, 0.5f, 0.2f, 0.3f }), FSOKey(0.62f, { 0, -0.42f, -0.18f, 0.5f, 0.2f, 0.3f }),
				FSOKey(0.74f, { 0, -0.085f, -0.0034f, 0.1f, 0, 0 }), FSOKey(0.8f, { 0, -0.05f, -0.002f, 0.06f, 0, 0 }), FSOKey(SeatT, { 0, 0, 0, 0, 0, 0 }, ESOEase::Out) });
			AddEvent(Main, 0.32f, TEXT("drop"));
		}
		AddEvent(Main, 0.18f, TEXT("sfx"), TEXT("magrelease"));
		AddEvent(Main, 0.5f, TEXT("sfx"), TEXT("pouch"));
		AddEvent(Main, 0.62f, TEXT("spare"));
		AddEvent(Main, SeatT - 0.04f, TEXT("sfx"), TEXT("magin"));
		AddEvent(Main, SlapT, TEXT("seat"));
		AddEvent(Main, SlapT, TEXT("sfx"), TEXT("slap"));
		Segments.Add(Main);

		// 2. empty: overhand rack (bolt back 9.5 cm, released)
		const float G2[6] = { -0.05f, 0.05f, 0.03f, 0.2f, 0.3f, -0.3f };
		const FSOKey LastMainHand = Main.Channels[NHand].Last();
		FSOKey LastHand = LastMainHand;
		if (bEmpty)
		{
			FSOReloadSegment Rack;
			Rack.Duration = 0.32f;
			float G2a[6];
			FMemory::Memcpy(G2a, G2, sizeof(G2a));
			G2a[2] += 0.015f;
			float G2b[6];
			FMemory::Memcpy(G2b, G2, sizeof(G2b));
			G2b[3] += 0.04f;
			Rack.Channels.Add(NGun, { Gun(0, T2), Gun(0.35f, G2), Gun(0.62f, G2a), Gun(0.76f, G2b, ESOEase::Out), Gun(1.0f, G2) });
			const float Travel = 0.095f;
			Rack.Channels.Add(NBolt, { FSOKey(0, { 0 }), FSOKey(0.42f, { 0 }), FSOKey(0.62f, { Travel }), FSOKey(0.7f, { Travel }), FSOKey(0.76f, { 0 }, ESOEase::Out) });
			FSOKey Cur = LastMainHand;
			Cur.T = 0.0f;
			Rack.Channels.Add(NHand, { Cur, Hand(0.4f, NBolt, { 0.004f, -0.03f, -0.01f, -0.35f, 0, 0.25f }),
				Hand(0.62f, NBolt, { 0.004f, -0.03f, -0.01f, -0.35f, 0, 0.25f }), Hand(0.72f, NBolt, { 0.004f, -0.01f, -0.04f, -0.35f, 0, 0.25f }),
				Hand(1.0f, NFore, { 0.02f, 0.03f, 0.04f, 0.1f, 0, 0 }) });
			AddEvent(Rack, 0.6f, TEXT("sfx"), TEXT("rackback"));
			AddEvent(Rack, 0.76f, TEXT("sfx"), TEXT("rackfwd"));
			LastHand = Rack.Channels[NHand].Last();
			Segments.Add(Rack);
		}

		// 3. back on the foregrip
		FSOReloadSegment Back;
		Back.Duration = 0.24f;
		const float Zero[6] = { 0, 0, 0, 0, 0, 0 };
		Back.Channels.Add(NGun, { Gun(0, bEmpty ? G2 : T2), Gun(1.0f, Zero) });
		LastHand.T = 0.0f;
		LastHand.Ease = ESOEase::Smoother;
		Back.Channels.Add(NHand, { LastHand, Hand(0.85f, NFore, { 0, 0, 0, 0, 0, 0 }), Hand(1.0f, NFore, { 0, 0, 0, 0, 0, 0 }) });
		Segments.Add(Back);

		// Scale: the tactical reload (main + back) lasts ReloadTime; the empty one adds the rack.
		const float Nominal = Segments[0].Duration + Segments.Last().Duration;
		const float K = ReloadTime / FMath::Max(Nominal, 1e-3f);
		for (FSOReloadSegment& Segment : Segments)
		{
			Segment.Duration *= K;
		}
		return Segments;
	}
}
