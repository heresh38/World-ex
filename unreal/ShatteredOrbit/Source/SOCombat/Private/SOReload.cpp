#include "SOReload.h"

namespace
{
	const FName NGun(TEXT("gun"));
	const FName NMag(TEXT("mag"));
	const FName NSpare(TEXT("spare"));
	const FName NBio(TEXT("bio"));
	const FName NShell(TEXT("shell"));
	const FName NRound(TEXT("round"));
	const FName NLoader(TEXT("loader"));
	const FName NBolt(TEXT("bolt"));
	const FName NCharge(TEXT("charge"));
	const FName NChargeUp(TEXT("chargeUp"));
	const FName NSlide(TEXT("slide"));
	const FName NPump(TEXT("pump"));
	const FName NBoltRot(TEXT("boltRot"));
	const FName NCrane(TEXT("crane"));
	const FName NSpin(TEXT("spin"));
	const FName NHatch(TEXT("hatch"));
	const FName NHand(TEXT("hand"));
	const FName NFore(TEXT("fore"));
	const FName NPouch(TEXT("pouch"));
	const FName NDrop(TEXT("drop"));
	const FName NSeat(TEXT("seat"));
	const FName NSfx(TEXT("sfx"));
	const FName NEject(TEXT("eject"));
	const FName NRelease(TEXT("release"));
	const FName NHusk(TEXT("husk"));
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

void FSOReloadPlayer::Start(TArray<FSOReloadSegment>&& InSegments, int32 InLoopFrom, int32 InLoopTo)
{
	Segments = MoveTemp(InSegments);
	Index = 0;
	LoopFrom = InLoopFrom;
	LoopTo = InLoopTo;
	Local = 0.0f;
	Elapsed = 0.0f;
	Duration = SOReload::GetDuration(Segments);
	FiredEvents.Reset();
	CycleLocal = -1.0f;
	const int32 Segment = Pose.Segment;
	Pose.Reset();
	Pose.Segment = Segment + 1;
	if (Segments.Num() > 0)
	{
		Sample(Segments[0], 0.0f);
	}
}

void FSOReloadPlayer::Cancel()
{
	Segments.Reset();
	LoopFrom = LoopTo = -1;
	const int32 Segment = Pose.Segment;
	Pose.Reset();
	Pose.Segment = Segment + 1;
}

bool FSOReloadPlayer::Interrupt()
{
	if (!IsInterruptible())
	{
		return false;
	}
	// The round or shell in hand goes back to the pouch; the closing segment runs from its start.
	Duration = Elapsed + Segments.Last().Duration;
	Index = Segments.Num() - 1;
	Local = 0.0f;
	FiredEvents.Reset();
	Pose.bShell = false;
	Pose.bRound = false;
	++Pose.Segment;
	return true;
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
			if (Event.Arg == NLoader)
			{
				Pose.bLoader = false;
			}
			else
			{
				Pose.bMagVisible = false;
			}
		}
		else if (Event.Name == NSpare)
		{
			Pose.bSpareVisible = true;
		}
		else if (Event.Name == NSeat)
		{
			if (Pose.bSpareVisible)
			{
				Pose.bSpareVisible = false;
				Pose.bMagVisible = true;
				Pose.bMagSeated = true;
				FMemory::Memzero(Pose.Mag, sizeof(Pose.Mag));
			}
		}
		else if (Event.Name == NShell)
		{
			Pose.bShell = Event.Count > 0;
		}
		else if (Event.Name == NRound)
		{
			Pose.bRound = Event.Count > 0;
		}
		else if (Event.Name == NEject)
		{
			Pose.bRounds = false;
		}
		else if (Event.Name == NLoader)
		{
			Pose.bLoader = true;
		}
		else if (Event.Name == NRelease)
		{
			Pose.bRounds = true;
		}
		else if (Event.Name == NHusk)
		{
			Pose.bBio = false;
		}
		else if (Event.Name == NBio)
		{
			Pose.bBio = true;
		}
		OutEvents.Add(Event);
	}
}

void FSOReloadPlayer::Sample(const FSOReloadSegment& Segment, float T)
{
	auto Six = [&](FName Name, float* Out) { if (const TArray<FSOKey>* Keys = Segment.Channels.Find(Name)) { SampleKeys(*Keys, T, 6, Out); } };
	auto One = [&](FName Name, float& Out) { if (const TArray<FSOKey>* Keys = Segment.Channels.Find(Name)) { SampleKeys(*Keys, T, 1, &Out); } };
	Six(NGun, Pose.Gun);
	if (!Pose.bMagSeated)
	{
		Six(NMag, Pose.Mag);
	}
	Six(NSpare, Pose.Spare);
	Six(NBio, Pose.Bio);
	Six(NShell, Pose.Shell);
	Six(NRound, Pose.Round);
	if (const TArray<FSOKey>* Keys = Segment.Channels.Find(NLoader)) { SampleKeys(*Keys, T, 4, Pose.Loader); }
	One(NBolt, Pose.Bolt);
	One(NCharge, Pose.Charge);
	One(NChargeUp, Pose.ChargeUp);
	One(NSlide, Pose.Slide);
	One(NPump, Pose.Pump);
	One(NBoltRot, Pose.BoltRot);
	One(NCrane, Pose.Crane);
	One(NSpin, Pose.Spin);
	One(NHatch, Pose.Hatch);
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

void FSOReloadPlayer::NotifyShot(FName Archetype)
{
	KickTime = 0.0f;
	KickArch = Archetype;
	if (Segments.Num() == 0 && SOReload::BuildCycle(Archetype, Cycle, CycleDelay))
	{
		CycleLocal = 0.0f;
		CycleFired.Reset();
	}
}

void FSOReloadPlayer::Idle(float DeltaTime, TArray<FSOReloadEvent>& OutEvents)
{
	// Blowback: the slide / carrier snaps back and returns after a shot.
	const float K = KickTime;
	const float Env = K < 0.03f ? K / 0.03f : FMath::Max(0.0f, 1.0f - (K - 0.03f) / 0.07f);
	const int32 Segment = Pose.Segment;
	Pose.Reset();
	Pose.Segment = Segment;
	if (KickArch == TEXT("pistol"))
	{
		Pose.Slide = bSlideLock ? 0.045f : 0.045f * Env;
	}
	else if (KickArch == TEXT("rifle") || KickArch.IsNone())
	{
		Pose.Bolt = 0.06f * Env;
	}
	else if (KickArch == TEXT("carbine") || KickArch == TEXT("ksmg") || KickArch == TEXT("dmr"))
	{
		Pose.Bolt = 0.04f * Env;
	}

	// Pump rack / bolt throw after the shot.
	if (CycleLocal < 0.0f)
	{
		return;
	}
	if (CycleDelay > 0.0f)
	{
		CycleDelay -= DeltaTime;
		return;
	}
	CycleLocal += DeltaTime;
	if (CycleLocal >= Cycle.Duration)
	{
		CycleLocal = -1.0f;
		++Pose.Segment;
		return;
	}
	const float T = CycleLocal / Cycle.Duration;
	for (int32 i = 0; i < Cycle.Events.Num(); ++i)
	{
		if (Cycle.Events[i].T <= T && !CycleFired.Contains(i))
		{
			CycleFired.Add(i);
			OutEvents.Add(Cycle.Events[i]);
		}
	}
	Sample(Cycle, T);
}

bool FSOReloadPlayer::Update(float DeltaTime, TArray<FSOReloadEvent>& OutEvents)
{
	KickTime += DeltaTime;
	if (Segments.Num() == 0)
	{
		Idle(DeltaTime, OutEvents);
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
		++Pose.Segment;
		FiredEvents.Reset();
	}
	if (Index >= Segments.Num())
	{
		Segments.Reset();
		LoopFrom = LoopTo = -1;
		const int32 Segment = Pose.Segment;
		Pose.Reset();
		Pose.Segment = Segment + 1;
		return true;
	}
	const FSOReloadSegment& Segment = Segments[Index];
	const float T = Local / FMath::Max(Segment.Duration, 1e-4f);
	FireEvents(Segment, T, OutEvents);
	Sample(Segment, T);
	return false;
}

// ---------------------------------------------------------------------------------------------
// Sequences: a port of reload.js (magReload, revolverReload, pumpReload, boltReload, bioReload, cycleSeq).

namespace SOReload
{
	/** Six numbers with the small edits reload.js does on its arrays. */
	struct F6
	{
		float V[6] = { 0, 0, 0, 0, 0, 0 };
		F6() = default;
		F6(std::initializer_list<float> L)
		{
			int32 i = 0;
			for (float X : L) { if (i < 6) { V[i++] = X; } }
		}
		F6 Add(int32 i, float D) const { F6 R = *this; R.V[i] += D; return R; }
		F6 Mul(int32 i, float K) const { F6 R = *this; R.V[i] *= K; return R; }
		F6 Scale(float K) const { F6 R = *this; for (float& X : R.V) { X *= K; } return R; }
	};

	static FSOKey K(float T, const F6& P, ESOEase Ease = ESOEase::Smoother)
	{
		return FSOKey(T, { P.V[0], P.V[1], P.V[2], P.V[3], P.V[4], P.V[5] }, Ease);
	}

	static FSOKey K1(float T, float V, ESOEase Ease = ESOEase::Smoother)
	{
		return FSOKey(T, { V }, Ease);
	}

	static FSOKey H(float T, const TCHAR* Anchor, const F6& P, ESOEase Ease = ESOEase::Smoother)
	{
		return FSOKey(T, { P.V[0], P.V[1], P.V[2], P.V[3], P.V[4], P.V[5] }, Ease, FName(Anchor));
	}

	static void Ev(FSOReloadSegment& S, float T, const TCHAR* Name, const TCHAR* Arg = nullptr, int32 Count = 0)
	{
		FSOReloadEvent E;
		E.T = T;
		E.Name = Name;
		E.Arg = Arg ? FName(Arg) : NAME_None;
		E.Count = Count;
		S.Events.Add(E);
	}

	static FSOReloadSegment Seg(float Duration)
	{
		FSOReloadSegment S;
		S.Duration = Duration;
		return S;
	}

	float GetDuration(const TArray<FSOReloadSegment>& Segments)
	{
		float Total = 0.0f;
		for (const FSOReloadSegment& Segment : Segments)
		{
			Total += Segment.Duration;
		}
		return Total;
	}

	static const F6 Zero;

	static F6 G2For(FName Arch)
	{
		if (Arch == TEXT("carbine") || Arch == TEXT("ksmg")) return F6{ -0.04f, 0.05f, 0.03f, 0.2f, 0.2f, -0.2f };
		if (Arch == TEXT("pistol")) return F6{ -0.06f, 0.05f, 0.05f, 0.3f, 0.1f, 0.2f };
		return F6{ -0.05f, 0.05f, 0.03f, 0.2f, 0.3f, -0.3f }; // rifle, dmr
	}

	/** reload.js magReload: per-gun mag out (rock, strip, drop-free), seat (hook + rock, push, slap, tap) and chambering. */
	static TArray<FSOReloadSegment> MagSegments(FName Arch, bool bEmpty)
	{
		const bool bRifle = Arch == TEXT("rifle"), bKsmg = Arch == TEXT("ksmg"), bDmr = Arch == TEXT("dmr");
		const bool bPistol = Arch == TEXT("pistol"), bCarbine = Arch == TEXT("carbine");
		const F6 Tilt = bCarbine ? F6{ -0.05f, 0.04f, 0.02f, 0.16f, 0.26f, -0.42f } : bDmr ? F6{ -0.05f, 0.02f, 0.05f, 0.26f, 0.3f, -0.5f }
			: bKsmg ? F6{ -0.06f, 0.05f, 0.02f, 0.12f, 0.36f, -0.62f } : bPistol ? F6{ -0.09f, 0.06f, 0.06f, 0.38f, 0.22f, -0.35f }
			: F6{ -0.04f, 0.03f, 0.03f, 0.22f, 0.32f, -0.55f };
		const F6 T2 = Tilt.Mul(5, 0.8f).Add(3, 0.06f);
		TArray<FSOReloadSegment> Segs;

		FSOReloadSegment Main = Seg(1.0f);
		TArray<FSOKey> Mag, Hand;
		float DropT;
		if (bRifle)
		{
			Mag = { K(0, Zero), K(0.25f, Zero), K(0.42f, { 0, -0.004f, 0.004f, -0.45f, 0, 0 }), K(0.55f, { 0, -0.07f, 0.02f, -0.6f, 0, 0.1f }) };
			Hand = { H(0, TEXT("fore"), Zero), H(0.22f, TEXT("mag"), { 0, -0.01f, -0.01f, -0.2f, 0, -0.3f }), H(0.55f, TEXT("mag"), { 0, -0.01f, -0.01f, -0.3f, 0, -0.3f }),
				H(0.7f, TEXT("pouch"), { 0.04f, 0.1f, 0.1f, 0.4f, 0.3f, -0.5f }) };
			DropT = 0.55f;
		}
		else if (bKsmg)
		{
			Mag = { K(0, Zero), K(0.24f, Zero), K(0.4f, { 0, -0.03f, 0.012f, -0.15f, 0, 0 }), K(0.52f, { 0, -0.09f, 0.05f, -0.35f, 0, 0 }) };
			Hand = { H(0, TEXT("fore"), Zero), H(0.2f, TEXT("mag"), { 0, -0.02f, 0.02f, -0.3f, 0, -0.2f }), H(0.52f, TEXT("mag"), { 0, -0.02f, 0.03f, -0.4f, 0, -0.2f }),
				H(0.7f, TEXT("pouch"), { 0.05f, 0.12f, 0.1f, 0.4f, 0.3f, -0.5f }) };
			DropT = 0.52f;
		}
		else
		{
			Mag = { K(0, Zero), K(0.2f, Zero), K(0.32f, { 0, -0.035f, 0, 0.04f, 0, 0 }, ESOEase::In) };
			Hand = bPistol
				? TArray<FSOKey>{ H(0, TEXT("fore"), Zero), H(0.2f, TEXT("fore"), { 0.02f, -0.04f, 0.02f, 0.2f, 0.1f, -0.2f }), H(0.42f, TEXT("pouch"), { 0.02f, 0.18f, 0.14f, 0.4f, 0.25f, -0.4f }) }
				: TArray<FSOKey>{ H(0, TEXT("fore"), Zero), H(0.2f, TEXT("fore"), { -0.01f, -0.06f, -0.04f, 0.25f, 0.1f, -0.2f }), H(0.42f, TEXT("pouch"), { 0.02f, 0.14f, 0.12f, 0.4f, 0.25f, -0.4f }) };
			DropT = 0.32f;
		}
		const F6 Pre = bRifle ? F6{ 0, -0.035f, 0.012f, -0.42f, 0, 0 } : bKsmg ? F6{ 0, -0.05f, 0.006f, -0.08f, 0, 0 } : F6{ 0, -0.05f, -0.002f, 0.06f, 0, 0 };
		const float SeatT = bDmr ? 0.9f : bPistol ? 0.86f : 0.88f;
		TArray<FSOKey> Spare = { K(0, { 0, -0.42f, -0.18f, 0.5f, 0.2f, 0.3f }), K(0.62f, { 0, -0.42f, -0.18f, 0.5f, 0.2f, 0.3f }), K(0.74f, Pre.Scale(1.7f)), K(0.8f, Pre) };
		if (bRifle)
		{
			Spare.Append({ K(0.86f, { 0, -0.004f, 0.003f, -0.32f, 0, 0 }), K(0.92f, Zero, ESOEase::Out) }); // hook the lip, rock back
		}
		else if (bDmr)
		{
			Spare.Append({ K(0.85f, { 0, -0.008f, 0, 0, 0, 0 }), K(0.9f, Zero, ESOEase::Out) }); // firm push
		}
		else
		{
			Spare.Add(K(SeatT, Zero, ESOEase::Out));
		}
		Hand.Append({ H(0.62f, TEXT("pouch"), { 0, 0, 0, 0.5f, 0.3f, -0.6f }), H(0.74f, TEXT("spare"), { 0, 0, 0, -0.25f, 0.05f, -0.25f }),
			H(0.84f, TEXT("spare"), { 0, 0, 0, -0.2f, 0, -0.2f }) });
		if (bDmr)
		{
			Hand.Append({ H(0.93f, TEXT("magbase"), { 0, -0.03f, 0, -0.1f, 0, -0.1f }), H(0.97f, TEXT("magbase"), { 0, -0.004f, 0, -0.1f, 0, -0.1f }, ESOEase::Out) }); // tap the base
		}
		else if (bCarbine || bPistol)
		{
			Hand.Append({ H(0.9f, TEXT("magbase"), { 0, -0.035f, 0, -0.1f, 0, -0.15f }), H(0.94f, TEXT("magbase"), { 0, -0.006f, 0, -0.1f, 0, -0.15f }, ESOEase::Out) }); // slap
		}
		else
		{
			Hand.Add(H(0.95f, TEXT("spare"), { 0, -0.006f, 0, -0.2f, 0, -0.2f }));
		}
		Hand.Add(H(1.0f, TEXT("spare"), { 0, -0.012f, 0, -0.2f, 0, -0.2f }));
		const float SlapT = bDmr ? 0.97f : (bCarbine || bPistol) ? 0.94f : SeatT;
		Main.Channels.Add(NGun, { K(0, Zero), K(0.22f, Tilt), K(0.4f, Tilt.Add(1, -0.01f)), K(0.5f, Tilt), K(0.7f, T2), K(0.84f, T2),
			K(SlapT, T2.Add(1, 0.012f).Add(3, 0.05f), ESOEase::Out), K(1.0f, T2) });
		Main.Channels.Add(NHand, Hand);
		Main.Channels.Add(NMag, Mag);
		Main.Channels.Add(NSpare, Spare);
		if (bEmpty && bPistol)
		{
			Main.Channels.Add(NSlide, { K1(0, 0.045f) }); // locked back on the empty mag
		}
		Ev(Main, 0.18f, TEXT("sfx"), TEXT("magrelease"));
		Ev(Main, DropT, TEXT("drop"));
		Ev(Main, 0.5f, TEXT("sfx"), TEXT("pouch"));
		Ev(Main, 0.62f, TEXT("spare"));
		Ev(Main, SeatT - 0.04f, TEXT("sfx"), TEXT("magin"));
		Ev(Main, SlapT, TEXT("seat"));
		Ev(Main, SlapT, TEXT("sfx"), bDmr ? TEXT("tap") : TEXT("slap"));
		if (bPistol || bCarbine)
		{
			Ev(Main, 0.36f, TEXT("sfx"), TEXT("magclatter"));
		}
		Segs.Add(Main);

		// empty: chamber a round (per-gun manual of arms)
		const F6 G2 = G2For(Arch);
		if (bEmpty)
		{
			FSOReloadSegment Rack = Seg(0.32f);
			const TCHAR* Part = bPistol ? TEXT("slide") : (bCarbine || bKsmg) ? TEXT("charge") : TEXT("bolt");
			const F6 Hk = bCarbine ? F6{ 0.0f, 0.02f, -0.02f, -0.6f, 0, -0.25f } : bDmr ? F6{ 0.004f, -0.032f, 0.0f, -0.35f, 0, 0.25f }
				: bKsmg ? F6{ 0.01f, 0.0f, 0.0f, -0.3f, 0, -0.5f } : bPistol ? F6{ 0, 0.015f, -0.06f, -0.5f, -0.2f, -0.35f } : F6{ 0.004f, -0.03f, -0.01f, -0.35f, 0, 0.25f };
			const float Travel = bCarbine ? 0.065f : bDmr ? 0.07f : bKsmg ? 0.08f : bPistol ? 0.045f : 0.095f;
			Rack.Channels.Add(NGun, { K(0, T2), K(0.35f, G2), K(0.62f, G2.Add(2, 0.015f)), K(0.76f, G2.Add(3, 0.04f), ESOEase::Out), K(1.0f, G2) });
			Rack.Channels.Add(NHand, { H(0, TEXT("cur"), { 0, 0, 0, 0.2f, 0, -0.2f }), H(0.4f, Part, Hk), H(0.62f, Part, Hk), H(0.72f, Part, Hk.Add(1, 0.02f).Add(2, -0.03f)),
				H(1.0f, TEXT("fore"), { 0.02f, 0.03f, 0.04f, 0.1f, 0, 0 }) });
			const TArray<FSOKey> Pull = { K1(0, 0), K1(0.42f, 0), K1(0.62f, Travel), K1(0.7f, Travel), K1(0.76f, 0, ESOEase::Out) };
			Rack.Channels.Add(FName(Part), Pull);
			if (bCarbine || bKsmg)
			{
				Rack.Channels.Add(NBolt, { K1(0, 0), K1(0.42f, 0), K1(0.62f, 0.05f), K1(0.7f, 0.05f), K1(0.76f, 0, ESOEase::Out) });
			}
			if (bKsmg)
			{
				Rack.Channels.Add(NChargeUp, { K1(0, 0), K1(0.62f, 0), K1(0.68f, 0.006f), K1(0.72f, 0.006f), K1(0.76f, 0, ESOEase::Out) });
			}
			if (bPistol)
			{
				Rack.Channels.Add(NSlide, { K1(0, 0.045f), K1(0.42f, 0.045f), K1(0.6f, 0.05f), K1(0.66f, 0, ESOEase::Out) }); // slingshot from slide lock
			}
			Ev(Rack, 0.6f, TEXT("sfx"), bPistol ? TEXT("slideback") : TEXT("rackback"));
			Ev(Rack, bPistol ? 0.66f : 0.76f, TEXT("sfx"), bPistol ? TEXT("slidefwd") : TEXT("rackfwd"));
			Segs.Add(Rack);
		}

		// back on the foregrip
		FSOReloadSegment Back = Seg(0.24f);
		Back.Channels.Add(NGun, { K(0, bEmpty ? G2 : T2), K(1.0f, Zero) });
		Back.Channels.Add(NHand, { H(0, TEXT("cur"), { 0, 0, 0, 0.2f, 0, -0.2f }), H(0.85f, TEXT("fore"), Zero), H(1.0f, TEXT("fore"), Zero) });
		Segs.Add(Back);
		return Segs;
	}

	static TArray<FSOReloadSegment> RevolverSegments()
	{
		const F6 G1{ -0.06f, 0.03f, 0.05f, 0.25f, 0.3f, -0.7f }, G2{ -0.08f, 0.12f, 0.03f, 1.05f, 0.3f, -0.35f }, G3{ -0.06f, 0.02f, 0.05f, 0.1f, 0.25f, -0.75f };
		FSOReloadSegment S = Seg(1.0f);
		S.Channels.Add(NGun, { K(0, Zero), K(0.12f, G1), K(0.24f, G1), K(0.32f, G2), K(0.4f, G2.Add(1, -0.02f)), K(0.46f, G2), K(0.56f, G3), K(0.82f, G3),
			K(0.87f, G3.Add(5, -0.15f), ESOEase::Out), K(1.0f, Zero) });
		S.Channels.Add(NHand, { H(0, TEXT("fore"), Zero), H(0.12f, TEXT("cyl"), { 0.01f, 0, 0, -0.2f, 0, -0.6f }), H(0.22f, TEXT("cyl"), { 0.01f, 0, 0, -0.2f, 0, -0.6f }),
			H(0.32f, TEXT("ejector"), { 0, 0, 0.01f, -0.2f, 0, -0.4f }), H(0.38f, TEXT("ejector"), { 0, 0, -0.012f, -0.2f, 0, -0.4f }),
			H(0.42f, TEXT("ejector"), { 0, 0, 0.01f, -0.2f, 0, -0.4f }), H(0.52f, TEXT("pouch"), { 0, 0.05f, 0.05f, 0.5f, 0.3f, -0.6f }),
			H(0.6f, TEXT("pouch"), { 0, 0, 0, 0.5f, 0.3f, -0.6f }), H(0.7f, TEXT("loader"), { 0, 0, 0, -0.2f, 0, -0.5f }), H(0.76f, TEXT("loader"), { 0, 0, 0, -0.2f, 0, -0.5f }),
			H(0.8f, TEXT("loader"), { 0.01f, 0, -0.02f, -0.2f, 0, -0.5f }), H(0.84f, TEXT("cyl"), { 0.03f, 0, -0.01f, -0.2f, 0, -0.6f }),
			H(0.88f, TEXT("cyl"), { -0.006f, 0, 0, -0.2f, 0, -0.6f }, ESOEase::Out), H(1.0f, TEXT("fore"), Zero) });
		S.Channels.Add(NCrane, { K1(0, 0), K1(0.16f, 0), K1(0.24f, -1.5f, ESOEase::Back), K1(0.84f, -1.5f), K1(0.89f, 0, ESOEase::Out) });
		S.Channels.Add(NSpin, { K1(0, 0), K1(0.24f, 0), K1(0.3f, 0.6f, ESOEase::Out), K1(0.84f, 0.6f), K1(1.0f, 0.6f + UE_TWO_PI / 3.0f * 4.0f, ESOEase::Out) });
		S.Channels.Add(NLoader, { FSOKey(0, { 0.03f, -0.2f, -0.3f, 0 }), FSOKey(0.6f, { 0.03f, -0.2f, -0.3f, 0 }), FSOKey(0.7f, { 0, 0, -0.05f, 0 }),
			FSOKey(0.74f, { 0, 0, -0.01f, 0 }), FSOKey(0.76f, { 0, 0, 0, 0.25f }), FSOKey(0.79f, { 0, 0, 0, 0.25f }), FSOKey(0.82f, { -0.03f, 0.02f, -0.12f, 0.25f }) });
		Ev(S, 0.1f, TEXT("sfx"), TEXT("latch"));
		Ev(S, 0.22f, TEXT("sfx"), TEXT("cylopen"));
		Ev(S, 0.37f, TEXT("eject"));
		Ev(S, 0.37f, TEXT("sfx"), TEXT("eject"));
		Ev(S, 0.5f, TEXT("sfx"), TEXT("pouch"));
		Ev(S, 0.6f, TEXT("loader"));
		Ev(S, 0.74f, TEXT("sfx"), TEXT("speedload"));
		Ev(S, 0.77f, TEXT("release"));
		Ev(S, 0.77f, TEXT("seat"));
		Ev(S, 0.8f, TEXT("drop"), TEXT("loader"));
		Ev(S, 0.88f, TEXT("sfx"), TEXT("cylclose"));
		return { S };
	}

	/** Pump: one shell at a time into the tube from the loading port; racks at the end if it was empty. */
	static TArray<FSOReloadSegment> PumpSegments(int32 N, bool bEmpty)
	{
		const F6 G{ -0.05f, 0.04f, 0.04f, 0.18f, 0.2f, -0.95f };
		TArray<FSOReloadSegment> Segs;
		FSOReloadSegment First = Seg(1.0f);
		First.Channels.Add(NGun, { K(0, Zero), K(1.0f, G) });
		First.Channels.Add(NHand, { H(0, TEXT("fore"), Zero), H(1.0f, TEXT("pouch"), { 0.02f, 0.1f, 0.12f, 0.5f, 0.3f, -0.6f }) });
		Ev(First, 0.6f, TEXT("sfx"), TEXT("pouch"));
		Segs.Add(First);
		for (int32 i = 0; i < N; ++i)
		{
			FSOReloadSegment S = Seg(1.0f);
			S.Channels.Add(NGun, { K(0, G), K(0.62f, G), K(0.72f, G.Add(1, 0.006f).Add(3, 0.03f), ESOEase::Out), K(1.0f, G) });
			S.Channels.Add(NShell, { K(0, { 0.02f, -0.3f, -0.15f, 0, 0, 0 }), K(0.35f, { 0.015f, -0.07f, 0.02f, -0.2f, 0, 0 }), K(0.55f, { 0, -0.012f, 0.065f, -0.08f, 0, 0 }),
				K(0.72f, { 0, 0.046f, 0.14f, 0, 0, 0 }, ESOEase::Out) });
			S.Channels.Add(NHand, { H(0, TEXT("pouch"), { 0, 0, 0, 0.5f, 0.3f, -0.6f }), H(0.1f, TEXT("shell"), { 0, 0, 0, -0.3f, 0, -0.5f }),
				H(0.55f, TEXT("shell"), { 0, 0, 0, -0.2f, 0, -0.5f }), H(0.66f, TEXT("free"), { 0, 0.01f, 0.12f, -0.2f, 0, -0.5f }),
				H(0.74f, TEXT("free"), { 0, 0.015f, 0.15f, -0.15f, 0, -0.5f }), H(1.0f, TEXT("pouch"), { 0.01f, 0.05f, 0.06f, 0.5f, 0.3f, -0.6f }) });
			Ev(S, 0.0f, TEXT("shell"), nullptr, 1);
			Ev(S, 0.6f, TEXT("sfx"), TEXT("shellin"));
			Ev(S, 0.72f, TEXT("shell"), nullptr, 0);
			Ev(S, 0.72f, TEXT("grant"), nullptr, 1);
			Segs.Add(S);
		}
		FSOReloadSegment End = Seg(bEmpty ? 1.6f : 0.9f);
		if (bEmpty)
		{
			End.Channels.Add(NGun, { K(0, G), K(0.5f, { -0.03f, 0.02f, 0.02f, 0.1f, 0.1f, -0.3f }), K(0.75f, { -0.03f, 0.015f, 0.0f, 0.14f, 0.1f, -0.2f }),
				K(0.92f, { -0.03f, 0.02f, 0.03f, 0.12f, 0.1f, -0.25f }), K(1.0f, Zero) });
			End.Channels.Add(NPump, { K1(0, 0), K1(0.6f, 0), K1(0.75f, 0.075f, ESOEase::Out), K1(0.92f, 0, ESOEase::Out) });
			Ev(End, 0.68f, TEXT("sfx"), TEXT("pumpback"));
			Ev(End, 0.88f, TEXT("sfx"), TEXT("pumpfwd"));
		}
		else
		{
			End.Channels.Add(NGun, { K(0, G), K(0.5f, { -0.03f, 0.02f, 0.02f, 0.1f, 0.1f, -0.3f }), K(1.0f, Zero) });
		}
		End.Channels.Add(NHand, { H(0, TEXT("cur"), { 0, 0, 0, 0.5f, 0.3f, -0.6f }), H(0.6f, TEXT("pump"), { 0, -0.02f, 0, 0, 0, 0 }), H(1.0f, TEXT("pump"), { 0, -0.02f, 0, 0, 0, 0 }) });
		Segs.Add(End);
		return Segs;
	}

	/** Bolt-action: roll the rifle to show the port, bolt up and back, thumb rounds in one by one, bolt forward and down. */
	static TArray<FSOReloadSegment> BoltSegments(int32 N)
	{
		const F6 G{ -0.07f, 0.09f, 0.06f, 0.2f, 0.22f, 0.6f };
		const F6 Knob{ 0, 0, 0, -0.45f, -0.2f, -0.5f };
		TArray<FSOReloadSegment> Segs;
		FSOReloadSegment Open = Seg(1.0f);
		Open.Channels.Add(NGun, { K(0, Zero), K(0.4f, G), K(1.0f, G) });
		Open.Channels.Add(NHand, { H(0, TEXT("fore"), Zero), H(0.35f, TEXT("bolt"), Knob), H(0.7f, TEXT("bolt"), Knob), H(1.0f, TEXT("pouch"), { -0.04f, 0.12f, 0.12f, 0.5f, 0.3f, -0.6f }) });
		Open.Channels.Add(NBoltRot, { K1(0, 0), K1(0.4f, 0), K1(0.52f, -1.05f, ESOEase::Out), K1(1.0f, -1.05f) });
		Open.Channels.Add(NBolt, { K1(0, 0), K1(0.52f, 0), K1(0.68f, 0.085f, ESOEase::Out), K1(1.0f, 0.085f) });
		Ev(Open, 0.5f, TEXT("sfx"), TEXT("boltup"));
		Ev(Open, 0.66f, TEXT("sfx"), TEXT("boltback"));
		Ev(Open, 0.9f, TEXT("sfx"), TEXT("pouch"));
		Segs.Add(Open);
		for (int32 i = 0; i < N; ++i)
		{
			FSOReloadSegment S = Seg(1.0f);
			S.Channels.Add(NGun, { K(0, G), K(0.6f, G), K(0.7f, G.Add(1, -0.005f), ESOEase::Out), K(1.0f, G) });
			S.Channels.Add(NBoltRot, { K1(0, -1.05f) });
			S.Channels.Add(NBolt, { K1(0, 0.085f) });
			S.Channels.Add(NRound, { K(0, { -0.15f, -0.15f, -0.2f, 0, 0, 0 }), K(0.35f, { -0.07f, 0.1f, -0.005f, 0, 0.2f, 0 }), K(0.55f, { -0.022f, 0.09f, 0, 0, 0, 0 }),
				K(0.7f, { -0.004f, 0.072f, 0.002f, 0, 0, 0 }, ESOEase::Out) });
			S.Channels.Add(NHand, { H(0, TEXT("pouch"), { 0, 0, 0, 0.5f, 0.3f, -0.6f }), H(0.12f, TEXT("round"), Knob), H(0.55f, TEXT("round"), Knob),
				H(0.7f, TEXT("round"), Knob.Add(1, -0.004f)), H(1.0f, TEXT("pouch"), { -0.03f, 0.1f, 0.1f, 0.5f, 0.3f, -0.6f }) });
			Ev(S, 0.0f, TEXT("round"), nullptr, 1);
			Ev(S, 0.66f, TEXT("sfx"), TEXT("roundin"));
			Ev(S, 0.7f, TEXT("round"), nullptr, 0);
			Ev(S, 0.7f, TEXT("grant"), nullptr, 1);
			Segs.Add(S);
		}
		FSOReloadSegment Close = Seg(1.15f);
		Close.Channels.Add(NGun, { K(0, G), K(0.55f, G), K(0.62f, G.Add(3, 0.03f), ESOEase::Out), K(1.0f, Zero) });
		Close.Channels.Add(NHand, { H(0, TEXT("cur"), { 0, 0, 0, 0.5f, 0.3f, -0.6f }), H(0.3f, TEXT("bolt"), Knob), H(0.65f, TEXT("bolt"), Knob), H(1.0f, TEXT("fore"), Zero) });
		Close.Channels.Add(NBolt, { K1(0, 0.085f), K1(0.32f, 0.085f), K1(0.46f, 0, ESOEase::Out) });
		Close.Channels.Add(NBoltRot, { K1(0, -1.05f), K1(0.48f, -1.05f), K1(0.6f, 0, ESOEase::Out) });
		Ev(Close, 0.44f, TEXT("sfx"), TEXT("boltfwd"));
		Ev(Close, 0.58f, TEXT("sfx"), TEXT("boltdown"));
		Segs.Add(Close);
		return Segs;
	}

	/** Living guns: the hatch peels open, the spent husk slops out, fresh biomass is pushed in, the hatch squelches shut. */
	static TArray<FSOReloadSegment> BioSegments(FName Arch)
	{
		const bool bBrood = Arch == TEXT("brood"), bBile = Arch == TEXT("bile");
		const float Open = bBrood ? 1.25f : bBile ? -1.35f : 1.45f;
		const F6 G = bBrood ? F6{ -0.07f, -0.1f, -0.03f, -0.42f, 0.3f, -0.2f } : F6{ -0.1f, 0.06f, 0.1f, 0.22f, 0.5f, -0.8f };
		const FVector Off = bBrood ? FVector(0, 0.2f, -0.16f) : FVector(0.16f, -0.1f, -0.12f);
		FSOReloadSegment S = Seg(1.0f);
		S.Channels.Add(NGun, { K(0, Zero), K(0.16f, G), K(0.26f, G.Add(1, 0.01f), ESOEase::Out), K(0.34f, G), K(0.84f, G), K(0.9f, G.Add(3, 0.05f), ESOEase::Out), K(1.0f, Zero) });
		S.Channels.Add(NHand, { H(0, TEXT("fore"), Zero), H(0.14f, TEXT("hatch"), { 0, 0.02f, 0, -0.2f, 0, -0.4f }), H(0.22f, TEXT("hatch"), { 0, 0.03f, 0, -0.2f, 0, -0.4f }),
			H(0.4f, TEXT("pouch"), { 0, 0.1f, 0.1f, 0.5f, 0.3f, -0.6f }), H(0.5f, TEXT("pouch"), { 0, 0, 0, 0.5f, 0.3f, -0.6f }),
			H(0.62f, TEXT("biomass"), { 0, -0.025f, 0, -0.3f, 0, -0.5f }), H(0.74f, TEXT("biomass"), { 0, -0.022f, 0, -0.3f, 0, -0.5f }),
			H(0.8f, TEXT("biomass"), { 0, -0.01f, 0, -0.3f, 0, -0.5f }), H(0.86f, TEXT("hatch"), { 0, 0.015f, 0, -0.2f, 0, -0.4f }),
			H(0.9f, TEXT("hatch"), { 0, 0.005f, 0, -0.2f, 0, -0.4f }, ESOEase::Out), H(1.0f, TEXT("fore"), Zero) });
		S.Channels.Add(NHatch, { K1(0, 0), K1(0.18f, 0), K1(0.26f, Open * 1.15f, ESOEase::Back), K1(0.32f, Open * 0.92f), K1(0.4f, Open), K1(0.8f, Open),
			K1(0.86f, Open * 0.2f, ESOEase::In), K1(0.9f, -Open * 0.06f, ESOEase::Out), K1(0.95f, 0) });
		const F6 Far{ (float)Off.X, (float)Off.Y, (float)Off.Z, 0.6f, 0.4f, 0 };
		S.Channels.Add(NBio, { K(0, Zero), K(0.3f, Zero), K(0.301f, Far, ESOEase::Linear), K(0.5f, Far),
			K(0.66f, { (float)Off.X * 0.25f, (float)Off.Y * 0.25f, (float)Off.Z * 0.25f, 0.2f, 0.1f, 0 }),
			K(0.76f, { (float)Off.X * 0.05f, (float)Off.Y * 0.05f, (float)Off.Z * 0.05f, 0, 0, 0 }), K(0.8f, Zero, ESOEase::Out) });
		Ev(S, 0.2f, TEXT("sfx"), TEXT("hatchopen"));
		Ev(S, 0.22f, TEXT("drip"), TEXT("hatch"));
		Ev(S, 0.3f, TEXT("husk"));
		Ev(S, 0.45f, TEXT("sfx"), TEXT("pouch"));
		Ev(S, 0.5f, TEXT("bio"));
		Ev(S, 0.76f, TEXT("sfx"), TEXT("bioin"));
		Ev(S, 0.8f, TEXT("seat"));
		Ev(S, 0.8f, TEXT("drip"), TEXT("biomass"));
		Ev(S, 0.88f, TEXT("sfx"), TEXT("hatchclose"));
		Ev(S, 0.9f, TEXT("glow"));
		Ev(S, 0.92f, TEXT("drip"), TEXT("hatch"));
		return { S };
	}

	/** Energy line: the old cell-swap dip (reload.js energy: gun dips and rolls, the cell is swapped). */
	static TArray<FSOReloadSegment> EnergySegments()
	{
		FSOReloadSegment S = Seg(1.0f);
		const F6 Dip{ 0, -0.12f, 0, 0.5f, 0, 0.4f };
		S.Channels.Add(NGun, { K(0, Zero), K(0.5f, Dip), K(1.0f, Zero) });
		Ev(S, 0.22f, TEXT("sfx"), TEXT("cellout"));
		Ev(S, 0.62f, TEXT("sfx"), TEXT("cellin"));
		Ev(S, 0.98f, TEXT("seat"));
		return { S };
	}

	TArray<FSOReloadSegment> BuildReload(FName Arch, bool bEnergy, bool bHorror, bool bEmpty, float ReloadTime, int32 Rounds, int32& OutLoopFrom, int32& OutLoopTo)
	{
		OutLoopFrom = OutLoopTo = -1;
		TArray<FSOReloadSegment> Segs;
		const bool bLoop = Arch == TEXT("pump") || Arch == TEXT("bolt");
		if (bLoop)
		{
			const int32 N = FMath::Max(1, Rounds);
			Segs = Arch == TEXT("pump") ? PumpSegments(N, bEmpty) : BoltSegments(N);
			OutLoopFrom = 1;
			OutLoopTo = N;
			// per-round guns: ReloadTime is spread over nominal units (pump 2.8 s ~ 0.39 s a shell)
			const float Per = ReloadTime / (Arch == TEXT("pump") ? 7.2f : 6.5f);
			for (FSOReloadSegment& S : Segs)
			{
				S.Duration *= Per;
			}
			return Segs;
		}
		if (Arch == TEXT("rifle") || Arch == TEXT("carbine") || Arch == TEXT("dmr") || Arch == TEXT("ksmg") || Arch == TEXT("pistol"))
		{
			Segs = MagSegments(Arch, bEmpty);
		}
		else if (Arch == TEXT("revolver"))
		{
			Segs = RevolverSegments();
		}
		else if (bHorror)
		{
			Segs = BioSegments(Arch);
		}
		else
		{
			Segs = EnergySegments();
		}
		// tactical = the weapon's reload time; an empty reload adds the chambering
		const float Nominal = Segs.Num() > 1 ? Segs[0].Duration + Segs.Last().Duration : Segs[0].Duration;
		const float Scale = ReloadTime / FMath::Max(Nominal, 1e-3f);
		for (FSOReloadSegment& S : Segs)
		{
			S.Duration *= Scale;
		}
		return Segs;
	}

	TArray<FSOReloadSegment> BuildMagReload(FName Archetype, bool bEmpty, float ReloadTime)
	{
		int32 From, To;
		return BuildReload(Archetype.IsNone() ? FName(TEXT("rifle")) : Archetype, false, false, bEmpty, ReloadTime, 0, From, To);
	}

	bool BuildCycle(FName Arch, FSOReloadSegment& Out, float& OutDelay)
	{
		Out = FSOReloadSegment();
		if (Arch == TEXT("pump"))
		{
			Out.Duration = 0.62f;
			Out.Channels.Add(NPump, { K1(0, 0), K1(0.32f, 0), K1(0.55f, 0.075f, ESOEase::Out), K1(0.82f, 0, ESOEase::Out) });
			Out.Channels.Add(NGun, { K(0, Zero), K(0.32f, Zero), K(0.55f, { -0.01f, -0.01f, 0.025f, 0.02f, 0.04f, -0.12f }), K(0.82f, { 0, -0.005f, 0.01f, 0.03f, 0.02f, -0.06f }), K(1.0f, Zero) });
			Out.Channels.Add(NHand, { H(0, TEXT("pump"), { 0, -0.02f, 0, 0, 0, 0 }), H(1.0f, TEXT("pump"), { 0, -0.02f, 0, 0, 0, 0 }) });
			Ev(Out, 0.4f, TEXT("sfx"), TEXT("pumpback"));
			Ev(Out, 0.7f, TEXT("sfx"), TEXT("pumpfwd"));
			OutDelay = 0.22f;
			return true;
		}
		if (Arch == TEXT("bolt"))
		{
			const F6 Knob{ 0, 0, 0, -0.45f, -0.2f, -0.5f };
			Out.Duration = 1.05f;
			Out.Channels.Add(NGun, { K(0, Zero), K(0.2f, { -0.02f, 0.02f, 0.03f, 0.06f, 0.08f, 0.35f }), K(0.8f, { -0.02f, 0.02f, 0.03f, 0.06f, 0.08f, 0.35f }), K(1.0f, Zero) });
			Out.Channels.Add(NHand, { H(0, TEXT("fore"), Zero), H(0.3f, TEXT("bolt"), Knob), H(0.75f, TEXT("bolt"), Knob), H(1.0f, TEXT("fore"), Zero) });
			Out.Channels.Add(NBoltRot, { K1(0, 0), K1(0.32f, 0), K1(0.42f, -1.05f, ESOEase::Out), K1(0.66f, -1.05f), K1(0.74f, 0, ESOEase::Out) });
			Out.Channels.Add(NBolt, { K1(0, 0), K1(0.42f, 0), K1(0.52f, 0.085f, ESOEase::Out), K1(0.58f, 0.085f), K1(0.66f, 0, ESOEase::Out) });
			Ev(Out, 0.4f, TEXT("sfx"), TEXT("boltup"));
			Ev(Out, 0.5f, TEXT("sfx"), TEXT("boltback"));
			Ev(Out, 0.5f, TEXT("eject"));
			Ev(Out, 0.62f, TEXT("sfx"), TEXT("boltfwd"));
			Ev(Out, 0.72f, TEXT("sfx"), TEXT("boltdown"));
			OutDelay = 0.3f;
			return true;
		}
		return false;
	}
}
