#pragma once

#include "CoreMinimal.h"

/**
 * A damped spring stepped stably at any frame time (the owner, 2026-11-23: "in first person the gun is constantly
 * shaking"): X follows Target with its own velocity V (Omega: how fast, per second; Zeta: 1 = no overshoot, less = a
 * little). Stepped once a frame, a stiff spring goes unstable when the frame is long: the camera's (Omega 30) did below
 * 36 frames a second and shook the picture 2 cm every frame, the gun with it. Here a long frame is taken in sub-steps
 * of at most MaxStep / Omega seconds.
 */
namespace SOSpring
{
	inline constexpr float MaxStep = 0.3f;

	template <typename T>
	void Step(T& X, T& V, const T& Target, float Omega, float Zeta, float Dt)
	{
		if (Dt <= 0.0f || Omega <= 0.0f)
		{
			return;
		}
		const int32 N = FMath::Clamp(FMath::CeilToInt(Dt * Omega / MaxStep), 1, 64);
		const float H = Dt / static_cast<float>(N);
		for (int32 i = 0; i < N; ++i)
		{
			V += ((Target - X) * (Omega * Omega) - V * (2.0f * Zeta * Omega)) * H;
			X += V * H;
		}
	}
}
