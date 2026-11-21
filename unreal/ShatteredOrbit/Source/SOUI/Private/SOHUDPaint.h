#pragma once

#include "CoreMinimal.h"
#include "CanvasItem.h"
#include "CanvasTypes.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/Font.h"
#include "Fonts/FontMeasure.h"
#include "Framework/Application/SlateApplication.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "Styling/CoreStyle.h"

/**
 * The HUD's shapes, drawn as batches of vertex-coloured triangles on the canvas (nothing is a texture or a material:
 * every plate, hexagon, ring and sweep is geometry, sharp at any resolution). All sizes are in screen pixels: the
 * caller scales by its layout. The look is the armoury's: night-blue glass, cyan lines, gold for what matters.
 */
namespace SOHudPaint
{
	// --- the palette (canvas colours) ---
	const FLinearColor Glass(0.010f, 0.018f, 0.038f, 0.80f);     // a panel's body
	const FLinearColor GlassDeep(0.005f, 0.009f, 0.020f, 0.90f); // a panel's lower half, the backs of bars
	const FLinearColor Line(0.30f, 0.80f, 1.0f, 0.42f);           // a panel's edge
	const FLinearColor Cyan(0.30f, 0.85f, 1.0f, 1.0f);            // what is active
	const FLinearColor Gold(1.0f, 0.80f, 0.32f, 1.0f);            // what matters
	const FLinearColor Ink(0.93f, 0.96f, 1.0f, 0.95f);            // words
	const FLinearColor Dim(0.62f, 0.70f, 0.82f, 0.85f);           // lesser words
	const FLinearColor ShieldBlue(0.32f, 0.74f, 1.0f, 1.0f);
	const FLinearColor HealthRed(0.96f, 0.30f, 0.26f, 1.0f);
	const FLinearColor Hurt(1.0f, 0.35f, 0.25f, 0.95f);
	const FLinearColor Lock(1.0f, 0.22f, 0.16f, 1.0f);

	inline FLinearColor A(const FLinearColor& C, float Alpha) { return FLinearColor(C.R, C.G, C.B, C.A * Alpha); }
	inline FLinearColor Mix(const FLinearColor& X, const FLinearColor& Y, float T) { return FMath::Lerp(X, Y, T); }

	/** A batch of triangles, drawn in one go on Flush (or when the texture changes). */
	struct FPainter
	{
		UCanvas* Canvas = nullptr;
		TArray<FCanvasUVTri> Tris;
		FTexture* Texture = nullptr;

		explicit FPainter(UCanvas* InCanvas) : Canvas(InCanvas) {}
		~FPainter() { Flush(); }

		void Flush()
		{
			if (Tris.Num() > 0 && Canvas)
			{
				FCanvasTriangleItem Item(Tris, Texture ? Texture : GWhiteTexture);
				Item.BlendMode = SE_BLEND_Translucent;
				Canvas->DrawItem(Item);
			}
			Tris.Reset();
			Texture = nullptr;
		}

		void Tri(const FVector2D& P0, const FVector2D& P1, const FVector2D& P2, const FLinearColor& C0, const FLinearColor& C1, const FLinearColor& C2)
		{
			if (Texture)
			{
				Flush();
			}
			FCanvasUVTri T;
			T.V0_Pos = P0; T.V1_Pos = P1; T.V2_Pos = P2;
			T.V0_Color = C0; T.V1_Color = C1; T.V2_Color = C2;
			T.V0_UV = T.V1_UV = T.V2_UV = FVector2D::ZeroVector;
			Tris.Add(T);
		}

		void Tri(const FVector2D& P0, const FVector2D& P1, const FVector2D& P2, const FLinearColor& C) { Tri(P0, P1, P2, C, C, C); }

		/** A quad from edge A (A0-A1) to edge B (B0-B1) with a colour per edge. */
		void Quad(const FVector2D& A0, const FVector2D& A1, const FVector2D& B0, const FVector2D& B1, const FLinearColor& CA, const FLinearColor& CB)
		{
			Tri(A0, B0, B1, CA, CB, CB);
			Tri(A0, B1, A1, CA, CB, CA);
		}

		/** A filled convex polygon (a fan from its first point). */
		void Fill(const TArray<FVector2D>& P, const FLinearColor& C)
		{
			for (int32 i = 1; i + 1 < P.Num(); ++i)
			{
				Tri(P[0], P[i], P[i + 1], C);
			}
		}

		/** A filled polygon shaded from its centre (CC) to its edge (CE). */
		void FillFan(const FVector2D& Centre, const TArray<FVector2D>& P, const FLinearColor& CC, const FLinearColor& CE)
		{
			for (int32 i = 0; i < P.Num(); ++i)
			{
				Tri(Centre, P[i], P[(i + 1) % P.Num()], CC, CE, CE);
			}
		}

		/** A polygon filled from its top (CT) to its bottom (CB). */
		void FillDown(const TArray<FVector2D>& P, const FLinearColor& CT, const FLinearColor& CB)
		{
			float Y0 = FLT_MAX, Y1 = -FLT_MAX;
			for (const FVector2D& V : P) { Y0 = FMath::Min(Y0, static_cast<float>(V.Y)); Y1 = FMath::Max(Y1, static_cast<float>(V.Y)); }
			auto ColourAt = [&](const FVector2D& V) { return Mix(CT, CB, FMath::Clamp((static_cast<float>(V.Y) - Y0) / FMath::Max(Y1 - Y0, 1.0f), 0.0f, 1.0f)); };
			for (int32 i = 1; i + 1 < P.Num(); ++i)
			{
				Tri(P[0], P[i], P[i + 1], ColourAt(P[0]), ColourAt(P[i]), ColourAt(P[i + 1]));
			}
		}

		/** A polygon filled from its left (CL) to its right (CR). */
		void FillAcross(const TArray<FVector2D>& P, const FLinearColor& CL, const FLinearColor& CR)
		{
			float X0 = FLT_MAX, X1 = -FLT_MAX;
			for (const FVector2D& V : P) { X0 = FMath::Min(X0, static_cast<float>(V.X)); X1 = FMath::Max(X1, static_cast<float>(V.X)); }
			auto ColourAt = [&](const FVector2D& V) { return Mix(CL, CR, FMath::Clamp((static_cast<float>(V.X) - X0) / FMath::Max(X1 - X0, 1.0f), 0.0f, 1.0f)); };
			for (int32 i = 1; i + 1 < P.Num(); ++i)
			{
				Tri(P[0], P[i], P[i + 1], ColourAt(P[0]), ColourAt(P[i]), ColourAt(P[i + 1]));
			}
		}

		/** The outline of a polyline, T px wide, centred on the line. */
		void Stroke(const TArray<FVector2D>& P, const FLinearColor& C, float T, bool bClosed = true)
		{
			const int32 N = bClosed ? P.Num() : P.Num() - 1;
			for (int32 i = 0; i < N; ++i)
			{
				const FVector2D& A0 = P[i];
				const FVector2D& A1 = P[(i + 1) % P.Num()];
				const FVector2D D = (A1 - A0).GetSafeNormal();
				const FVector2D Nrm(-D.Y, D.X);
				// a hair past each end so the corners close
				const FVector2D E0 = A0 - D * T * 0.5f, E1 = A1 + D * T * 0.5f;
				Quad(E0 + Nrm * T * 0.5f, E1 + Nrm * T * 0.5f, E0 - Nrm * T * 0.5f, E1 - Nrm * T * 0.5f, C, C);
			}
		}

		/** A line drawn as light: a soft halo under a sharp core. */
		void Glow(const TArray<FVector2D>& P, const FLinearColor& C, float T, bool bClosed = true)
		{
			Stroke(P, A(C, 0.18f), T * 4.0f, bClosed);
			Stroke(P, A(C, 0.45f), T * 2.0f, bClosed);
			Stroke(P, C, T, bClosed);
		}

		void Segment(const FVector2D& P0, const FVector2D& P1, const FLinearColor& C, float T)
		{
			Stroke({ P0, P1 }, C, T, false);
		}

		/** A ring (or an arc from A0 to A1, radians, screen space) between radii R0 and R1, coloured inside (C0) to outside (C1). */
		void Ring(const FVector2D& C, float R0, float R1, const FLinearColor& C0, const FLinearColor& C1, float A0 = 0.0f, float A1 = UE_TWO_PI, int32 N = 64)
		{
			const int32 Steps = FMath::Max(3, FMath::CeilToInt(N * FMath::Abs(A1 - A0) / UE_TWO_PI));
			for (int32 i = 0; i < Steps; ++i)
			{
				const float T0 = A0 + (A1 - A0) * i / Steps, T1 = A0 + (A1 - A0) * (i + 1) / Steps;
				const FVector2D D0(FMath::Cos(T0), FMath::Sin(T0)), D1(FMath::Cos(T1), FMath::Sin(T1));
				Quad(C + D0 * R0, C + D1 * R0, C + D0 * R1, C + D1 * R1, C0, C1);
			}
		}

		/** A disc. */
		void Disc(const FVector2D& C, float R, const FLinearColor& CC, const FLinearColor& CE, int32 N = 64)
		{
			TArray<FVector2D> P;
			for (int32 i = 0; i < N; ++i)
			{
				const float T = UE_TWO_PI * i / N;
				P.Add(C + FVector2D(FMath::Cos(T), FMath::Sin(T)) * R);
			}
			FillFan(C, P, CC, CE);
		}

		/** A pie: the sector of a disc from A0 to A1 (radians, screen space). */
		void Sector(const FVector2D& C, float R, float A0, float A1, const FLinearColor& CC, const FLinearColor& CE, int32 N = 48)
		{
			const int32 Steps = FMath::Max(2, FMath::CeilToInt(N * FMath::Abs(A1 - A0) / UE_TWO_PI));
			for (int32 i = 0; i < Steps; ++i)
			{
				const float T0 = A0 + (A1 - A0) * i / Steps, T1 = A0 + (A1 - A0) * (i + 1) / Steps;
				Tri(C, C + FVector2D(FMath::Cos(T0), FMath::Sin(T0)) * R, C + FVector2D(FMath::Cos(T1), FMath::Sin(T1)) * R, CC, CE, CE);
			}
		}

		/** From C along angle T to the polygon's edge (C inside). */
		static FVector2D Ray(const TArray<FVector2D>& P, const FVector2D& C, float T)
		{
			const FVector2D D(FMath::Cos(T), FMath::Sin(T));
			float Best = FLT_MAX;
			for (int32 i = 0; i < P.Num(); ++i)
			{
				const FVector2D& A0 = P[i];
				const FVector2D E = P[(i + 1) % P.Num()] - A0;
				const float Den = D.X * E.Y - D.Y * E.X;
				if (FMath::Abs(Den) < KINDA_SMALL_NUMBER)
				{
					continue;
				}
				const FVector2D W = A0 - C;
				const float Tt = (W.X * E.Y - W.Y * E.X) / Den;
				const float U = (W.X * D.Y - W.Y * D.X) / Den;
				if (Tt > 0.0f && U >= -0.001f && U <= 1.001f)
				{
					Best = FMath::Min(Best, Tt);
				}
			}
			return Best < FLT_MAX ? D * Best : FVector2D::ZeroVector;
		}

		/** The part of a convex polygon swept from the top, clockwise, as far as Frac (a cooldown coming back). */
		void Sweep(const TArray<FVector2D>& P, const FVector2D& C, float Frac, const FLinearColor& Col)
		{
			Frac = FMath::Clamp(Frac, 0.0f, 1.0f);
			if (Frac <= 0.0f)
			{
				return;
			}
			const int32 Steps = 36;
			const float A0 = -UE_HALF_PI, A1 = A0 + UE_TWO_PI * Frac;
			FVector2D Prev = C + Ray(P, C, A0);
			for (int32 i = 1; i <= Steps; ++i)
			{
				const float T = A0 + (A1 - A0) * i / Steps;
				const FVector2D Next = C + Ray(P, C, T);
				Tri(C, Prev, Next, Col);
				Prev = Next;
			}
		}

		/** A textured disc: the map's picture cut round (UVs about UVCentre, UVPerPx per pixel). */
		void TexturedDisc(const FVector2D& C, float R, FTexture* Tex, const FVector2D& UVCentre, float UVPerPx, const FLinearColor& Tint, int32 N = 72)
		{
			Flush();
			Texture = Tex;
			for (int32 i = 0; i < N; ++i)
			{
				const float T0 = UE_TWO_PI * i / N, T1 = UE_TWO_PI * (i + 1) / N;
				const FVector2D D0(FMath::Cos(T0), FMath::Sin(T0)), D1(FMath::Cos(T1), FMath::Sin(T1));
				FCanvasUVTri T;
				T.V0_Pos = C; T.V1_Pos = C + D0 * R; T.V2_Pos = C + D1 * R;
				T.V0_UV = UVCentre; T.V1_UV = UVCentre + D0 * R * UVPerPx; T.V2_UV = UVCentre + D1 * R * UVPerPx;
				T.V0_Color = T.V1_Color = T.V2_Color = Tint;
				Tris.Add(T);
			}
			Flush();
		}
	};

	// --- shapes ---
	inline TArray<FVector2D> Diamond(const FVector2D& C, float RX, float RY)
	{
		return { C + FVector2D(0, -RY), C + FVector2D(RX, 0), C + FVector2D(0, RY), C + FVector2D(-RX, 0) };
	}

	/** A regular hexagon, a point up (Rot 0) or a flat top (Rot pi/6). */
	inline TArray<FVector2D> Hex(const FVector2D& C, float R, float Rot = 0.0f)
	{
		TArray<FVector2D> P;
		for (int32 i = 0; i < 6; ++i)
		{
			const float T = -UE_HALF_PI + Rot + i * UE_PI / 3.0f;
			P.Add(C + FVector2D(FMath::Cos(T), FMath::Sin(T)) * R);
		}
		return P;
	}

	/** A rectangle with its top-left and bottom-right corners cut (the armoury's cards). */
	inline TArray<FVector2D> Plate(float X, float Y, float W, float H, float Cut)
	{
		return { FVector2D(X + Cut, Y), FVector2D(X + W, Y), FVector2D(X + W, Y + H - Cut), FVector2D(X + W - Cut, Y + H), FVector2D(X, Y + H), FVector2D(X, Y + Cut) };
	}

	/** A rectangle with all four corners cut. */
	inline TArray<FVector2D> Plate4(float X, float Y, float W, float H, float Cut)
	{
		return { FVector2D(X + Cut, Y), FVector2D(X + W - Cut, Y), FVector2D(X + W, Y + Cut), FVector2D(X + W, Y + H - Cut),
			FVector2D(X + W - Cut, Y + H), FVector2D(X + Cut, Y + H), FVector2D(X, Y + H - Cut), FVector2D(X, Y + Cut) };
	}

	inline TArray<FVector2D> Rectangle(float X, float Y, float W, float H)
	{
		return { FVector2D(X, Y), FVector2D(X + W, Y), FVector2D(X + W, Y + H), FVector2D(X, Y + H) };
	}

	/** The shape moved by D. */
	inline TArray<FVector2D> Shifted(const TArray<FVector2D>& P, const FVector2D& D)
	{
		TArray<FVector2D> Out;
		for (const FVector2D& V : P)
		{
			Out.Add(V + D);
		}
		return Out;
	}

	/** The shape drawn in by D toward its middle (a convex shape's inner line). */
	inline TArray<FVector2D> Inset(const TArray<FVector2D>& P, float D)
	{
		FVector2D C(0, 0);
		for (const FVector2D& V : P)
		{
			C += V;
		}
		C /= FMath::Max(P.Num(), 1);
		TArray<FVector2D> Out;
		for (const FVector2D& V : P)
		{
			const FVector2D R = V - C;
			const float L = static_cast<float>(R.Size());
			Out.Add(L > D ? C + R * ((L - D) / L) : C);
		}
		return Out;
	}

	/** The shadow a shape casts on the world behind it: two soft steps down from it. */
	inline void Shadow(FPainter& P, const TArray<FVector2D>& Shape, float Depth, float Alpha = 1.0f)
	{
		P.Fill(Shifted(Shape, FVector2D(0.0f, Depth * 1.6f)), FLinearColor(0.0f, 0.0f, 0.0f, 0.18f * Alpha));
		P.Fill(Shifted(Shape, FVector2D(0.0f, Depth * 0.8f)), FLinearColor(0.0f, 0.0f, 0.0f, 0.26f * Alpha));
	}

	/** What gives a shape its thickness: a dark line a step inside its edge (the glass's own depth) and a line of
	 *  light along the edges that run near level across its top (lit from above). */
	inline void Bevel(FPainter& P, const TArray<FVector2D>& Shape, float EdgeT, float Alpha = 1.0f)
	{
		P.Stroke(Inset(Shape, EdgeT * 2.6f), FLinearColor(0.0f, 0.004f, 0.012f, 0.55f * Alpha), EdgeT);
		float Y0 = FLT_MAX, Y1 = -FLT_MAX;
		for (const FVector2D& V : Shape)
		{
			Y0 = FMath::Min(Y0, static_cast<float>(V.Y));
			Y1 = FMath::Max(Y1, static_cast<float>(V.Y));
		}
		for (int32 i = 0; i < Shape.Num(); ++i)
		{
			const FVector2D& A0 = Shape[i];
			const FVector2D& A1 = Shape[(i + 1) % Shape.Num()];
			const bool bLevel = FMath::Abs(A1.Y - A0.Y) < FMath::Abs(A1.X - A0.X) * 0.6f;
			const bool bTop = (A0.Y + A1.Y) * 0.5f < Y0 + (Y1 - Y0) * 0.34f;
			if (bLevel && bTop)
			{
				P.Segment(A0 + FVector2D(0.0f, EdgeT * 1.3f), A1 + FVector2D(0.0f, EdgeT * 1.3f), FLinearColor(0.78f, 0.9f, 1.0f, 0.24f * Alpha), EdgeT);
			}
		}
	}

	/** A glass panel with depth (the owner, 2026-11-21: "the hud still looks flat, it needs more depth, more
	 *  definition, more volume"): the shadow it casts, its body lit from above and shaded down, an inner line a
	 *  step inside its edge, the edge, and light along its top. */
	inline void Panel(FPainter& P, const TArray<FVector2D>& Shape, float EdgeT, float Alpha = 1.0f, const FLinearColor& Edge = Line)
	{
		Shadow(P, Shape, EdgeT * 4.0f, Alpha);
		P.FillDown(Shape, A(Mix(Glass, Line, 0.10f), Alpha), A(GlassDeep, Alpha));
		Bevel(P, Shape, EdgeT, Alpha);
		P.Stroke(Shape, A(Edge, Alpha), EdgeT);
	}

	/** A bar with depth: a trough darker at its floor, the fill lit from above with a gloss along its top, brighter
	 *  toward its head, a bright head, and a thin frame. */
	inline void Bar(FPainter& P, float X, float Y, float W, float H, float Frac, const FLinearColor& Fill, float Alpha = 1.0f, float EdgeT = 1.0f)
	{
		P.Fill(Rectangle(X, Y + H * 0.4f, W, H), FLinearColor(0.0f, 0.0f, 0.0f, 0.28f * Alpha));
		P.FillDown(Rectangle(X, Y, W, H), A(GlassDeep, Alpha), A(Mix(GlassDeep, FLinearColor::Black, 0.55f), Alpha));
		const float FW = W * FMath::Clamp(Frac, 0.0f, 1.0f);
		if (FW > 0.5f)
		{
			P.FillDown(Rectangle(X, Y, FW, H), A(Mix(Fill, FLinearColor::White, 0.28f), Alpha), A(Mix(Fill, FLinearColor::Black, 0.28f), Alpha));
			P.FillAcross(Rectangle(X, Y, FW, H), A(Fill, 0.0f), A(Mix(Fill, FLinearColor::White, 0.4f), 0.4f * Alpha));
			P.Fill(Rectangle(X, Y, FW, H * 0.32f), FLinearColor(1.0f, 1.0f, 1.0f, 0.17f * Alpha));
			const float Head = FMath::Min(EdgeT * 2.0f, FW);
			P.Fill(Rectangle(X + FW - Head, Y, Head, H), A(Mix(Fill, FLinearColor::White, 0.75f), Alpha));
		}
		P.Stroke(Rectangle(X, Y, W, H), A(Line, Alpha * 0.8f), EdgeT);
	}

	/** How a piece of glass looks: its body top and bottom, its edge, an inner glow (reach in px, GlowA 0 = none),
	 *  its shadow, and an alpha over all of it. */
	struct FGlassStyle
	{
		FLinearColor FillA = FLinearColor(0.022f, 0.036f, 0.066f, 0.86f);
		FLinearColor FillB = FLinearColor(0.005f, 0.009f, 0.019f, 0.93f);
		FLinearColor Edge = FLinearColor(0.30f, 0.80f, 1.0f, 0.55f);
		FLinearColor Glow = FLinearColor(0.30f, 0.85f, 1.0f, 1.0f);
		float GlowW = 16.0f;
		float GlowA = 0.0f;
		float EdgeT = 1.0f;
		float ShadowOff = 5.0f;
		float ShadowBlur = 7.0f;
		float ShadowA = 0.38f;
		float Alpha = 1.0f;
	};

	/** The HUD's glass (the owner, 2026-11-21: "a triple a hud ... everything must be very crisp like 4k"): every shape
	 *  is one quad of M_HUDGlass drawn on the canvas, worked out as a signed distance in pixels, so its edge is
	 *  anti-aliased at any size and resolution, with a shadow, a body lit from above, an inner glow, light along
	 *  its top and its edge. A dynamic instance per shape per frame from a pool the HUD keeps. The painter it is
	 *  given is flushed first, so what was drawn before lies under the glass. */
	struct FGlass
	{
		UCanvas* Canvas = nullptr;
		FPainter* Painter = nullptr;
		UMaterialInterface* Base = nullptr;
		TArray<TObjectPtr<UMaterialInstanceDynamic>>* Pool = nullptr;
		int32* Used = nullptr;
		UObject* Outer = nullptr;
		float S = 1.0f;

		enum EShape : int32 { ShapePlate = 0, ShapePlate4 = 1, ShapeHexUp = 2, ShapeHexFlat = 3, ShapeDiamond = 4, ShapeRing = 5, ShapeDisc = 6, ShapeBar = 7 };

		UMaterialInstanceDynamic* Next() const
		{
			if (!Base || !Pool || !Used || !Outer)
			{
				return nullptr;
			}
			while (Pool->Num() <= *Used)
			{
				Pool->Add(UMaterialInstanceDynamic::Create(Base, Outer));
			}
			return (*Pool)[(*Used)++];
		}

		/** The shape in the box X, Y, W, H (the box is the shape's extent; the quad drawn is bigger by the shadow's
		 *  reach). Cut: a plate's corner, a ring's thickness. Frac / FillAxis: a fill (1 across, 2 up). Arc: a ring's
		 *  from / to (degrees, screen space, -90 the top), a bar's segment length and gap (px). */
		void Shape(int32 Kind, float X, float Y, float W, float H, float Cut, const FGlassStyle& St, float Frac = 1.0f, int32 FillAxis = 0,
			const FVector4& Arc = FVector4(0.0f, 360.0f, 0.0f, 0.0f)) const
		{
			if (Painter)
			{
				Painter->Flush();
			}
			if (!Canvas || W < 1.0f || H < 1.0f)
			{
				return;
			}
			UMaterialInstanceDynamic* M = Next();
			if (!M)
			{
				// (the material is not imported: the flat shapes of before)
				if (!Painter)
				{
					return;
				}
				const FVector2D C(X + W * 0.5f, Y + H * 0.5f);
				switch (Kind)
				{
				case ShapePlate: Panel(*Painter, SOHudPaint::Plate(X, Y, W, H, Cut), St.EdgeT, St.Alpha, St.Edge); break;
				case ShapePlate4: Panel(*Painter, SOHudPaint::Plate4(X, Y, W, H, Cut), St.EdgeT, St.Alpha, St.Edge); break;
				case ShapeBar: SOHudPaint::Bar(*Painter, X, Y, W, H, Frac, St.FillA, St.Alpha, St.EdgeT); break;
				case ShapeHexUp: Painter->Fill(Hex(C, W * 0.5f), A(St.FillA, St.Alpha)); Painter->Stroke(Hex(C, W * 0.5f), A(St.Edge, St.Alpha), St.EdgeT); break;
				case ShapeHexFlat: Painter->Fill(Hex(C, W * 0.5f, UE_PI / 6.0f), A(St.FillA, St.Alpha)); Painter->Stroke(Hex(C, W * 0.5f, UE_PI / 6.0f), A(St.Edge, St.Alpha), St.EdgeT); break;
				case ShapeDiamond: Painter->Fill(SOHudPaint::Diamond(C, W * 0.5f, H * 0.5f), A(St.FillA, St.Alpha)); Painter->Stroke(SOHudPaint::Diamond(C, W * 0.5f, H * 0.5f), A(St.Edge, St.Alpha), St.EdgeT); break;
				case ShapeRing: Painter->Ring(C, W * 0.5f - Cut, W * 0.5f, A(St.FillA, St.Alpha), A(St.FillA, St.Alpha), FMath::DegreesToRadians(Arc.X), FMath::DegreesToRadians(Arc.Y)); break;
				default: Painter->Disc(C, W * 0.5f, A(St.FillA, St.Alpha), A(St.FillB, St.Alpha)); break;
				}
				return;
			}
			const float Pad = FMath::CeilToFloat(St.ShadowOff + St.ShadowBlur + 2.0f);
			const float QW = W + 2.0f * Pad, QH = H + 2.0f * Pad;
			M->SetVectorParameterValue(TEXT("Size"), FLinearColor(QW, QH, Pad, static_cast<float>(Kind)));
			M->SetVectorParameterValue(TEXT("Geo"), FLinearColor(Cut, St.EdgeT, Frac, static_cast<float>(FillAxis)));
			M->SetVectorParameterValue(TEXT("FillA"), A(St.FillA, St.Alpha));
			M->SetVectorParameterValue(TEXT("FillB"), A(St.FillB, St.Alpha));
			M->SetVectorParameterValue(TEXT("EdgeCol"), A(St.Edge, St.Alpha));
			M->SetVectorParameterValue(TEXT("Glow"), FLinearColor(St.Glow.R, St.Glow.G, St.Glow.B, St.GlowW));
			M->SetVectorParameterValue(TEXT("Shadow"), FLinearColor(St.ShadowOff, St.ShadowBlur, St.ShadowA * St.Alpha, St.GlowA * St.Alpha));
			M->SetVectorParameterValue(TEXT("Arc"), FLinearColor(Arc.X, Arc.Y, Arc.Z, Arc.W));
			Canvas->K2_DrawMaterial(M, FVector2D(X - Pad, Y - Pad), FVector2D(QW, QH), FVector2D(0.0f, 0.0f), FVector2D(1.0f, 1.0f));
		}
		void Plate(float X, float Y, float W, float H, float Cut, const FGlassStyle& St) const { Shape(ShapePlate, X, Y, W, H, Cut, St); }
		void Plate4(float X, float Y, float W, float H, float Cut, const FGlassStyle& St) const { Shape(ShapePlate4, X, Y, W, H, Cut, St); }
		void HexUp(const FVector2D& C, float R, const FGlassStyle& St, float Frac = 1.0f, int32 FillAxis = 0) const { Shape(ShapeHexUp, C.X - R, C.Y - R, 2.0f * R, 2.0f * R, 0.0f, St, Frac, FillAxis); }
		void HexFlat(const FVector2D& C, float R, const FGlassStyle& St) const { Shape(ShapeHexFlat, C.X - R, C.Y - R, 2.0f * R, 2.0f * R, 0.0f, St); }
		void Diamond(const FVector2D& C, float RX, float RY, const FGlassStyle& St, float Frac = 1.0f, int32 FillAxis = 0) const { Shape(ShapeDiamond, C.X - RX, C.Y - RY, 2.0f * RX, 2.0f * RY, 0.0f, St, Frac, FillAxis); }
		void Disc(const FVector2D& C, float R, const FGlassStyle& St) const { Shape(ShapeDisc, C.X - R, C.Y - R, 2.0f * R, 2.0f * R, 0.0f, St); }
		/** A ring of outer radius R and thickness T, from A0 to A1 degrees (screen space: -90 is the top, clockwise). */
		void Ring(const FVector2D& C, float R, float T, float A0, float A1, const FGlassStyle& St) const { Shape(ShapeRing, C.X - R, C.Y - R, 2.0f * R, 2.0f * R, T, St, 1.0f, 0, FVector4(A0, A1, 0.0f, 0.0f)); }
		/** A bar filled Frac of the way from the left, Fill over Trough; Segments > 0: cut into pieces that long (px)
		 *  with Gap px between them. */
		void Bar(float X, float Y, float W, float H, float Frac, const FLinearColor& Fill, const FLinearColor& Trough, float EdgeT, float Alpha = 1.0f,
			float Segment = 0.0f, float Gap = 0.0f, float ShadowA = 0.3f) const
		{
			FGlassStyle St;
			St.FillA = Fill;
			St.FillB = Trough;
			St.Edge = A(Line, 0.6f);
			St.EdgeT = EdgeT;
			St.ShadowOff = H * 0.35f;
			St.ShadowBlur = H * 0.5f + 1.0f;
			St.ShadowA = ShadowA;
			St.Alpha = Alpha;
			Shape(ShapeBar, X, Y, W, H, 0.0f, St, Frac, 1, FVector4(0.0f, 360.0f, Segment, Gap));
		}
	};

	// --- text (the engine's Roboto: the armoury's face) ---
	/** The HUD's type. A size is a face in PIXELS at scale 1 (Small 10, Medium 12, Large 20: the large one bold), and
	 *  every string is rasterised by Slate's font cache at the size it is drawn (size x scale), so it is crisp at any
	 *  scale and resolution. Before, the engine's bitmap Roboto and its distance-field face were scaled as pictures:
	 *  the magazine's count and every label were soft and pixelated (the owner, 2026-11-21: "the numbers are blurry
	 *  ... fix this too so numbers/letters are crisp, not pixelated"). The face is Slate's own Roboto. */
	/** The faces (the engine's own Roboto, every weight it ships): Auto = Regular, Bold from the large size on;
	 *  Cond = the bold condensed face for labels in tracked capitals; Light for the big numbers. */
	enum class EFace : uint8 { Auto, Regular, Light, Medium, Bold, Cond, Black };

	struct FType
	{
		UCanvas* Canvas;
		float Small = 10.0f;
		float Medium = 12.0f;
		float Large = 20.0f;
		mutable EFace Face = EFace::Auto;   // (the caller sets it before drawing and puts it back)

		explicit FType(UCanvas* InCanvas) : Canvas(InCanvas) {}

		FSlateFontInfo FontOf(float F, float Scale) const
		{
			const TCHAR* Name = TEXT("Regular");
			switch (Face)
			{
			case EFace::Light: Name = TEXT("Light"); break;
			case EFace::Medium: Name = TEXT("Medium"); break;
			case EFace::Bold: Name = TEXT("Bold"); break;
			case EFace::Cond: Name = TEXT("BoldCondensed"); break;
			case EFace::Black: Name = TEXT("Black"); break;
			case EFace::Regular: Name = TEXT("Regular"); break;
			default: Name = F >= 18.0f ? TEXT("Bold") : TEXT("Regular"); break;
			}
			return FCoreStyle::GetDefaultFontStyle(Name, FMath::Max(6.0f, F * Scale));
		}

		/** The canvas draws nothing without a font object, and takes the Slate font info only through a RUNTIME-cached
		 *  one: the engine's Roboto (the UMG default) is; the distance-field face is not. */
		static UFont* RuntimeFont()
		{
			UFont* F = GEngine ? GEngine->GetMediumFont() : nullptr;
			if (F && F->FontCacheType == EFontCacheType::Runtime)
			{
				return F;
			}
			F = FindObject<UFont>(nullptr, TEXT("/Engine/EngineFonts/Roboto.Roboto"));
			if (!F)
			{
				F = LoadObject<UFont>(nullptr, TEXT("/Engine/EngineFonts/Roboto.Roboto"));
			}
			return F && F->FontCacheType == EFontCacheType::Runtime ? F : nullptr;
		}

		FVector2D Size(const FString& Text, float F, float Scale) const
		{
			if (!FSlateApplication::IsInitialized() || Text.IsEmpty())
			{
				return FVector2D::ZeroVector;
			}
			const TSharedRef<FSlateFontMeasure> Measure = FSlateApplication::Get().GetRenderer()->GetFontMeasureService();
			return Measure->Measure(Text, FontOf(F, Scale));
		}

		/** Draws at X, Y (top left); returns the width. */
		float Draw(const FString& Text, float X, float Y, float F, float Scale, const FLinearColor& C, bool bShadow = true) const
		{
			if (!Canvas || Text.IsEmpty())
			{
				return 0.0f;
			}
			UFont* Font = RuntimeFont();
			if (!Font)
			{
				return 0.0f;
			}
			FCanvasTextItem Item(FVector2D(X, Y), FText::FromString(Text), Font, C);
			Item.SlateFontInfo = FontOf(F, Scale);
			if (bShadow)
			{
				Item.EnableShadow(FLinearColor(0.0f, 0.0f, 0.0f, C.A * 0.7f), FVector2D(1.0f, 1.0f));
			}
			Item.BlendMode = SE_BLEND_Translucent;
			Canvas->DrawItem(Item);
			return Size(Text, F, Scale).X;
		}

		float DrawRight(const FString& Text, float XRight, float Y, float F, float Scale, const FLinearColor& C) const
		{
			const float W = Size(Text, F, Scale).X;
			Draw(Text, XRight - W, Y, F, Scale, C);
			return W;
		}

		float DrawCentred(const FString& Text, float XMid, float Y, float F, float Scale, const FLinearColor& C) const
		{
			const float W = Size(Text, F, Scale).X;
			Draw(Text, XMid - W * 0.5f, Y, F, Scale, C);
			return W;
		}

		float CapsWidth(const FString& Text, float F, float Scale, float Spacing) const
		{
			const FString Up = Text.ToUpper();
			float W = 0.0f;
			for (int32 i = 0; i < Up.Len(); ++i)
			{
				W += Size(Up.Mid(i, 1), F, Scale).X + (i + 1 < Up.Len() ? Spacing : 0.0f);
			}
			return W;
		}

		/** Letter-spaced capitals (a label); returns the width. Align: 0 left, 1 right, 0.5 centred on X. */
		float Caps(const FString& Text, float X, float Y, float F, float Scale, const FLinearColor& C, float Spacing, float Align = 0.0f) const
		{
			const FString Up = Text.ToUpper();
			const float W = CapsWidth(Text, F, Scale, Spacing);
			float Cx = X - W * Align;
			for (int32 i = 0; i < Up.Len(); ++i)
			{
				const FString Ch = Up.Mid(i, 1);
				Draw(Ch, Cx, Y, F, Scale, C);
				Cx += Size(Ch, F, Scale).X + Spacing;
			}
			return W;
		}

		/** A label: tracked capitals in the condensed face. */
		float Label(const FString& Text, float X, float Y, float F, float Scale, const FLinearColor& C, float Spacing, float Align = 0.0f) const
		{
			const EFace Was = Face;
			Face = EFace::Cond;
			const float W = Caps(Text, X, Y, F, Scale, C, Spacing, Align);
			Face = Was;
			return W;
		}
		float LabelWidth(const FString& Text, float F, float Scale, float Spacing) const
		{
			const EFace Was = Face;
			Face = EFace::Cond;
			const float W = CapsWidth(Text, F, Scale, Spacing);
			Face = Was;
			return W;
		}

		/** A number: the light face, big. Returns the width. */
		float Number(const FString& Text, float X, float Y, float F, float Scale, const FLinearColor& C, float Align = 0.0f) const
		{
			const EFace Was = Face;
			Face = EFace::Light;
			const float W = Size(Text, F, Scale).X;
			Draw(Text, X - W * Align, Y, F, Scale, C);
			Face = Was;
			return W;
		}
		FVector2D NumberSize(const FString& Text, float F, float Scale) const
		{
			const EFace Was = Face;
			Face = EFace::Light;
			const FVector2D Sz = Size(Text, F, Scale);
			Face = Was;
			return Sz;
		}
	};
}
