#pragma once

#include "CoreMinimal.h"

/**
 * An arm as its BONES (the owner, 2026-11-27, with red marks on our own pictures of a reload, word for word: "the
 * players hands can't bend in a way that is not posible for a real human, learn it once and apply it to all guns and
 * done" and "humans have bones and can't bend their hands/arms in such manner so mark where they are in the body and
 * ensure these rules are always followed at all times for everything").
 *
 * Until then a wrist was measured as ONE angle (the forearm's line against the hand's, under 80 degrees) and an elbow
 * as one, and poses passed that no arm can make: a wrist bends far toward the palm and toward the back of the hand but
 * only a little to either side, and the palm turns about the forearm (its two bones, radius and ulna, crossing) so far
 * and no further. Here each joint is marked where it is in the body and measured the way an examiner measures it:
 *
 *   the shoulder   where the upper arm leaves the trunk: how far the upper arm is turned about its own length (the
 *                  forearm swung in across the body, or out), from the arm hanging with the forearm forward
 *   the elbow      a hinge: 0 straight, to about 150
 *   the forearm    its twist: 0 with the thumb up and the palm in (a handshake); + supination (the palm turned up),
 *                  - pronation (the palm turned down)
 *   the wrist      flexion (+ toward the palm) and extension (-), and sideways: + toward the thumb (radial), - toward
 *                  the little finger (ulnar). The two are one joint: bent far one way it has little left the other, so
 *                  they are held inside an ellipse together (WristStrain: 1 is its edge).
 *
 * Every measure is taken from where the joints ARE (the shoulder, the elbow, the wrist, the knuckles of the index, middle
 * and little fingers), never from a bone's own turn, so it reads the same for any pose however it was made: a clip, the
 * arm solve, a blend. One model for every gun, state and view: the arm solve keeps inside it (USOLocomotionAnimInstance)
 * and ShatteredOrbit.Body.HumanRange measures it for every gun through everything a player does.
 */
namespace SOArmBones
{
	/** A healthy adult's ranges of motion, degrees (the clinical norms, a little inside what a supple body reaches). */
	struct FRange
	{
		float Elbow = 150.0f;        // (flexion from straight)
		float Supinate = 85.0f;      // (the palm turned up)
		float Pronate = 80.0f;       // (the palm turned down)
		float Flex = 75.0f;          // (the wrist toward the palm)
		float Extend = 68.0f;        // (toward the back of the hand)
		float Radial = 20.0f;        // (sideways toward the thumb)
		float Ulnar = 35.0f;         // (sideways toward the little finger)
		float TurnIn = 95.0f;        // (the upper arm about itself: the forearm swung in across the body)
		float TurnOut = 75.0f;       // (the forearm swung out)
	};

	/** One arm, measured. Degrees. */
	struct FArm
	{
		float Elbow = 0.0f;          // 0 straight
		float Twist = 0.0f;          // + supination, - pronation
		float Flex = 0.0f;           // + flexion, - extension
		float Deviate = 0.0f;        // + radial (thumb), - ulnar (little finger)
		float Turn = 0.0f;           // the upper arm about itself: + in, - out
		/** The elbow is bent enough for the forearm's twist to be told from the upper arm's turn (a straight arm turns its
		 *  palm with both at once: neither is defined alone). */
		bool bBent = false;

		/** The wrist inside its ellipse: under 1 a wrist can be there, 1 is its edge. */
		float WristStrain(const FRange& R = FRange()) const
		{
			const float F = Flex / (Flex >= 0.0f ? R.Flex : R.Extend), D = Deviate / (Deviate >= 0.0f ? R.Radial : R.Ulnar);
			return FMath::Sqrt(F * F + D * D);
		}
		/** The forearm's twist against its range: under 1 inside. */
		float TwistStrain(const FRange& R = FRange()) const
		{
			return bBent ? (Twist >= 0.0f ? Twist / R.Supinate : -Twist / R.Pronate) : 0.0f;
		}
		/** The upper arm's turn against its range. */
		float TurnStrain(const FRange& R = FRange()) const
		{
			return bBent ? (Turn >= 0.0f ? Turn / R.TurnIn : -Turn / R.TurnOut) : 0.0f;
		}
		/** The worst of what the elbow's place round the arm can change (the wrist, the forearm's twist, the upper arm's
		 *  turn: the elbow's own bend is set by how far the hand is from the shoulder, wherever the elbow hangs). */
		float Asks(const FRange& R = FRange()) const
		{
			return FMath::Max3(WristStrain(R), TwistStrain(R), TurnStrain(R));
		}
		/** The worst of the arm's joints against a human's range: under 1, an arm can be there. */
		float Strain(const FRange& R = FRange()) const
		{
			return FMath::Max(FMath::Max(WristStrain(R), TwistStrain(R)), FMath::Max(TurnStrain(R), Elbow / R.Elbow));
		}
	};

	/** The signed angle about Axis from A to B (both square to it), radians, by the engine's own cross product. */
	inline float AngleAbout(const FVector& Axis, const FVector& A, const FVector& B)
	{
		return FMath::Atan2(static_cast<float>(FVector::DotProduct(FVector::CrossProduct(A, B), Axis)), static_cast<float>(FVector::DotProduct(A, B)));
	}

	/**
	 * One arm from where its joints are, in any one frame (the body's component space: +X the body's left, +Y forward,
	 * +Z up): the shoulder, the elbow, the wrist; the hand's long line (wrist to the middle finger's knuckle) and its thumb
	 * side (from the little finger's knuckle toward the index finger's: square to the line or not, it is squared here);
	 * the trunk's forward and up (the chest's).
	 */
	inline FArm Measure(const FVector& Shoulder, const FVector& ElbowAt, const FVector& Wrist, const FVector& HandLine, const FVector& ThumbSide, bool bLeft,
		const FVector& TrunkForward = FVector(0.0f, 1.0f, 0.0f), const FVector& TrunkUp = FVector(0.0f, 0.0f, 1.0f))
	{
		FArm Out;
		const FVector U = (ElbowAt - Shoulder).GetSafeNormal(), F = (Wrist - ElbowAt).GetSafeNormal();
		const FVector A = HandLine.GetSafeNormal();
		if (U.IsNearlyZero() || F.IsNearlyZero() || A.IsNearlyZero())
		{
			return Out;
		}
		Out.Elbow = FMath::RadiansToDegrees(FMath::Acos(FMath::Clamp(static_cast<float>(FVector::DotProduct(U, F)), -1.0f, 1.0f)));
		// the hand's own frame: its line, its thumb side squared to the line, and out of its palm (hands are mirror images)
		FVector R = ThumbSide - A * FVector::DotProduct(ThumbSide, A);
		if (!R.Normalize(1e-4f))
		{
			return Out;
		}
		const FVector N = bLeft ? -FVector::CrossProduct(A, R) : FVector::CrossProduct(A, R);
		// the wrist: the swing that takes the forearm's line onto the hand's, and which way it leans
		const float Swing = FMath::Acos(FMath::Clamp(static_cast<float>(FVector::DotProduct(F, A)), -1.0f, 1.0f));
		const FQuat Unswing = FQuat::FindBetweenNormals(A, F);
		const FVector N1 = Unswing.RotateVector(N), R1 = Unswing.RotateVector(R);   // (the hand's palm and thumb side were the wrist straight)
		FVector Lean = A - F * FVector::DotProduct(A, F);
		if (Lean.Normalize(1e-4f))
		{
			Out.Flex = FMath::RadiansToDegrees(Swing) * static_cast<float>(FVector::DotProduct(Lean, N1));
			Out.Deviate = FMath::RadiansToDegrees(Swing) * static_cast<float>(FVector::DotProduct(Lean, R1));
		}
		// the forearm's twist: from where the palm faces with the thumb toward the shoulder's side of the bent arm (a
		// handshake) to where it faces now, about the forearm
		FVector Thumb0 = -U - F * FVector::DotProduct(-U, F);
		Out.bBent = Out.Elbow > 12.0f && Thumb0.Normalize(1e-4f);
		if (Out.bBent)
		{
			const FVector Palm0 = bLeft ? -FVector::CrossProduct(F, Thumb0) : FVector::CrossProduct(F, Thumb0);
			const float Raw = FMath::RadiansToDegrees(AngleAbout(F, Palm0, N1));
			Out.Twist = bLeft ? Raw : -Raw;
			// the upper arm's turn about itself: from the forearm lying forward of an arm swung here from hanging, to where
			// the forearm lies now
			const FVector Down = -TrunkUp.GetSafeNormal();
			if (FVector::DotProduct(Down, U) > -0.9)
			{
				const FVector Forward0 = FQuat::FindBetweenNormals(Down, U).RotateVector(TrunkForward.GetSafeNormal());
				FVector Fore = F - U * FVector::DotProduct(F, U), Ref = Forward0 - U * FVector::DotProduct(Forward0, U);
				if (Fore.Normalize(1e-4f) && Ref.Normalize(1e-4f))
				{
					const float RawTurn = FMath::RadiansToDegrees(AngleAbout(U, Ref, Fore));
					Out.Turn = bLeft ? -RawTurn : RawTurn;
				}
			}
		}
		return Out;
	}

	/**
	 * The hand bone's turn for an arm whose joints are given and whose forearm is twisted and wrist bent so far (degrees,
	 * as Measure reads them): the other way round. An arm too straight for its twist to be told (FArm::bBent false) has
	 * none of its own: PalmStraight is then where the palm faces with the wrist straight (square to the forearm).
	 */
	inline FQuat Compose(const FVector& Shoulder, const FVector& ElbowAt, const FVector& Wrist, float Twist, float Flex, float Deviate, const FVector& LineLocal,
		const FVector& ThumbLocal, bool bLeft, const FVector& PalmStraight = FVector::ZeroVector)
	{
		const FVector U = (ElbowAt - Shoulder).GetSafeNormal(), F = (Wrist - ElbowAt).GetSafeNormal();
		FVector N1 = PalmStraight - F * FVector::DotProduct(PalmStraight, F);
		FVector Thumb0 = -U - F * FVector::DotProduct(-U, F);
		if (PalmStraight.IsNearlyZero() || !N1.Normalize(1e-4f))
		{
			if (!Thumb0.Normalize(1e-4f))
			{
				Thumb0 = FVector::CrossProduct(F, FVector(0.3f, 0.5f, 0.8f)).GetSafeNormal();   // (a straight arm with nothing said: any side)
			}
			const FVector Palm0 = bLeft ? -FVector::CrossProduct(F, Thumb0) : FVector::CrossProduct(F, Thumb0);
			N1 = FQuat(F, FMath::DegreesToRadians(bLeft ? Twist : -Twist)).RotateVector(Palm0);
		}
		const FVector R1 = bLeft ? FVector::CrossProduct(F, N1) : FVector::CrossProduct(N1, F);
		FVector A2 = F, R2 = R1;
		if (const float Total = FMath::Sqrt(Flex * Flex + Deviate * Deviate); Total > 1e-3f)
		{
			const FVector Lean = (N1 * Flex + R1 * Deviate) / Total;
			const float Angle = FMath::DegreesToRadians(Total);
			A2 = (F * FMath::Cos(Angle) + Lean * FMath::Sin(Angle)).GetSafeNormal();
			R2 = FQuat::FindBetweenNormals(F, A2).RotateVector(R1);
		}
		// the hand bone's own frame of its line and thumb side, onto the one worked out
		const FVector L = LineLocal.GetSafeNormal();
		const FVector T = (ThumbLocal - L * FVector::DotProduct(ThumbLocal, L)).GetSafeNormal();
		const FQuat Own(FMatrix(L, T, FVector::CrossProduct(L, T), FVector::ZeroVector)), New(FMatrix(A2, R2, FVector::CrossProduct(A2, R2), FVector::ZeroVector));
		return (New * Own.Inverse()).GetNormalized();
	}

	/**
	 * A hand's turn brought inside what this arm's bones allow: the forearm's twist held within its range and the wrist
	 * inside its ellipse (Edge of it: 1 the range itself), everything else as it was. HandRot is the hand bone's turn in
	 * the frame the joints are given in; LineLocal and ThumbLocal the hand's long line and thumb side in the bone's own
	 * frame (from the rest pose's knuckles). The joints are never asked for more: what the hand holds gives way.
	 * OutWas: the arm as it was asked for.
	 */
	inline FQuat Within(const FVector& Shoulder, const FVector& ElbowAt, const FVector& Wrist, const FQuat& HandRot, const FVector& LineLocal, const FVector& ThumbLocal,
		bool bLeft, const FRange& Range = FRange(), float Edge = 1.0f, FArm* OutWas = nullptr)
	{
		const FVector A = HandRot.RotateVector(LineLocal).GetSafeNormal();
		FVector R = HandRot.RotateVector(ThumbLocal);
		R -= A * FVector::DotProduct(R, A);
		const FArm Was = Measure(Shoulder, ElbowAt, Wrist, A, R, bLeft);
		if (OutWas)
		{
			*OutWas = Was;
		}
		if (!R.Normalize(1e-4f) || A.IsNearlyZero())
		{
			return HandRot;
		}
		float Twist = Was.Twist, Flex = Was.Flex, Deviate = Was.Deviate;
		bool bGives = false;
		if (Was.bBent && (Twist > Range.Supinate * Edge || Twist < -Range.Pronate * Edge))
		{
			Twist = FMath::Clamp(Twist, -Range.Pronate * Edge, Range.Supinate * Edge);
			bGives = true;
		}
		if (const float Strain = Was.WristStrain(Range); Strain > Edge)
		{
			Flex *= Edge / Strain;
			Deviate *= Edge / Strain;
			bGives = true;
		}
		if (!bGives)
		{
			return HandRot;
		}
		const FVector U = (ElbowAt - Shoulder).GetSafeNormal(), F = (Wrist - ElbowAt).GetSafeNormal();
		const FVector N = bLeft ? -FVector::CrossProduct(A, R) : FVector::CrossProduct(A, R);
		// the palm with the wrist straight: where the twist allowed puts it (a straight arm: where it faces now)
		FVector N1 = FQuat::FindBetweenNormals(A, F).RotateVector(N);
		FVector Thumb0 = -U - F * FVector::DotProduct(-U, F);
		if (Was.bBent && Thumb0.Normalize(1e-4f))
		{
			const FVector Palm0 = bLeft ? -FVector::CrossProduct(F, Thumb0) : FVector::CrossProduct(F, Thumb0);
			N1 = FQuat(F, FMath::DegreesToRadians(bLeft ? Twist : -Twist)).RotateVector(Palm0);
		}
		const FVector R1 = bLeft ? FVector::CrossProduct(F, N1) : FVector::CrossProduct(N1, F);
		// the wrist's lean allowed: toward the palm by Flex, toward the thumb by Deviate
		FVector A2 = F, R2 = R1;
		if (const float Total = FMath::Sqrt(Flex * Flex + Deviate * Deviate); Total > 1e-3f)
		{
			const FVector Lean = (N1 * Flex + R1 * Deviate) / Total;
			const float Angle = FMath::DegreesToRadians(Total);
			A2 = (F * FMath::Cos(Angle) + Lean * FMath::Sin(Angle)).GetSafeNormal();
			R2 = FQuat::FindBetweenNormals(F, A2).RotateVector(R1);
		}
		// the turn that takes the hand's frame as it was asked for onto the one the bones allow
		const FQuat Old(FMatrix(A, R, FVector::CrossProduct(A, R), FVector::ZeroVector)), New(FMatrix(A2, R2, FVector::CrossProduct(A2, R2), FVector::ZeroVector));
		return (New * Old.Inverse() * HandRot).GetNormalized();
	}
}
