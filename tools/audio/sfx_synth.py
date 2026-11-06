"""Shattered Orbit sound effects, synthesised offline (our own; no recorded or third-party audio).

    python tools/audio/sfx_synth.py [out_dir]      (default: unreal/ShatteredOrbit/SourceArt/Audio)

Every sound is built from layers: a transient (clicks, the supersonic crack), a body (filtered noise blasts, pitch-
dropping thumps), mechanical detail (modal synthesis: damped resonant modes of steel parts) and space (a synthetic
impulse response with early reflections and a diffuse tail, convolved by FFT). Creature voices use a glottal source
(band-limited pulse train with jitter and vibrato) through moving formant filters. Deterministic seeds, so the files
rebuild bit-identical. Writes 48 kHz 16-bit WAV (stereo for the player's own gun, mono for positional sounds).
"""
import math
import os
import sys
import wave

import numpy as np
from scipy import signal

SR = 48000
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


# ---------------------------------------------------------------------------- primitives

def secs(t):
    return int(round(t * SR))


def silence(t):
    return np.zeros(secs(t))


def rng(seed):
    return np.random.default_rng(seed)


def noise(t, seed, colour="white"):
    n = rng(seed).standard_normal(secs(t))
    if colour == "pink":
        b, a = [0.049922035, -0.095993537, 0.050612699, -0.004408786], [1, -2.494956002, 2.017265875, -0.522189400]
        n = signal.lfilter(b, a, n) * 4.0
    elif colour == "brown":
        n = np.cumsum(n)
        n = signal.lfilter([1, -1], [1, -0.995], n) * 0.05
    return n


def env_exp(t, tau, attack=0.001):
    """Instant-ish attack, exponential decay with time constant tau (s)."""
    x = np.arange(secs(t)) / SR
    e = np.exp(-x / tau)
    if attack > 0:
        e *= np.clip(x / attack, 0, 1)
    return e


def env_ad(t, attack, decay_tau, hold=0.0):
    x = np.arange(secs(t)) / SR
    e = np.where(x < attack, x / max(attack, 1e-6), np.exp(-np.maximum(x - attack - hold, 0) / decay_tau))
    return e


def sweep(f0, f1, t, curve="exp"):
    x = np.linspace(0, 1, secs(t))
    return f0 * (f1 / f0) ** x if curve == "exp" else f0 + (f1 - f0) * x


def osc(freq, kind="sine", phase=0.0):
    """freq: array of instantaneous frequency (Hz)."""
    ph = phase + 2 * np.pi * np.cumsum(freq) / SR
    if kind == "sine":
        return np.sin(ph)
    if kind == "tri":
        return 2 / np.pi * np.arcsin(np.sin(ph))
    if kind == "saw":
        return 2 * ((ph / (2 * np.pi)) % 1.0) - 1
    if kind == "square":
        return np.sign(np.sin(ph))
    raise ValueError(kind)


def filt(x, kind, f, q=0.707, order=2):
    """Static Butterworth-style filter; f in Hz (or (lo, hi) for band)."""
    nyq = SR / 2
    if kind == "band":
        lo, hi = f
        sos = signal.butter(order, [max(lo, 10) / nyq, min(hi, nyq * 0.98) / nyq], btype="bandpass", output="sos")
    else:
        sos = signal.butter(order, min(f, nyq * 0.98) / nyq, btype="lowpass" if kind == "low" else "highpass", output="sos")
    return signal.sosfilt(sos, x)


def svf_sweep(x, kind, f0, f1, q=0.8, curve="exp"):
    """Time-varying state-variable filter (TPT form), cutoff swept f0 -> f1 across the signal."""
    f = sweep(f0, f1, len(x) / SR, curve)
    g = np.tan(np.pi * np.clip(f, 20, SR * 0.45) / SR)
    k = 1.0 / q
    ic1 = ic2 = 0.0
    out = np.empty_like(x)
    for i in range(len(x)):
        gi = g[i]
        a1 = 1.0 / (1.0 + gi * (gi + k))
        v3 = x[i] - ic2
        v1 = a1 * ic1 + gi * a1 * v3
        v2 = ic2 + gi * v1
        ic1 = 2 * v1 - ic1
        ic2 = 2 * v2 - ic2
        out[i] = v2 if kind == "low" else (v1 if kind == "band" else x[i] - k * v1 - v2)
    return out


def modal(t, modes, seed=0, strike=0.0015):
    """Sum of damped sinusoids: modes = [(freq Hz, decay tau s, amp)], excited by a short noise strike."""
    r = rng(seed)
    n = secs(t)
    x = np.arange(n) / SR
    out = np.zeros(n)
    for f, tau, a in modes:
        f = f * (1 + r.uniform(-0.01, 0.01))
        out += a * np.sin(2 * np.pi * f * x + r.uniform(0, 2 * np.pi)) * np.exp(-x / tau)
    exc = np.zeros(n)
    k = max(secs(strike), 2)
    exc[:k] = r.standard_normal(k) * np.hanning(k)
    out = out * (0.6 + 0.4 * np.clip(np.convolve(np.abs(exc), np.ones(k) / k, mode="same") * 4, 0, 1))
    return out


def click(seed, f=3200.0, amp=1.0, t=0.03):
    """A small hard contact: three modes around f plus a noise tick."""
    m = modal(t, [(f, 0.004, 1.0), (f * 1.63, 0.0025, 0.6), (f * 2.41, 0.0015, 0.35)], seed)
    tick = filt(noise(t, seed + 1), "high", 2500) * env_exp(t, 0.0012, 0.0001)
    return amp * (m * 0.7 + tick * 0.5)


def place(dst, src, at, gain=1.0):
    i = secs(at)
    if i >= len(dst):
        return dst
    n = min(len(src), len(dst) - i)
    dst[i:i + n] += src[:n] * gain
    return dst


def saturate(x, drive=1.0):
    return np.tanh(x * drive) / np.tanh(drive)


def impulse_response(t, seed, early=((0.011, 0.5), (0.023, 0.35), (0.037, 0.3), (0.058, 0.22), (0.083, 0.15)),
                     decay=0.35, damping=3500.0, density=1.0, stereo=False):
    """Synthetic room / outdoor response: discrete early reflections + diffuse tail (filtered noise, darkening)."""
    def one(s):
        r = rng(s)
        n = secs(t)
        ir = np.zeros(n)
        ir[0] = 1.0
        for at, g in early:
            j = secs(at * r.uniform(0.92, 1.08))
            if j < n:
                ir[j] += g * r.choice([-1, 1])
        x = np.arange(n) / SR
        tail = r.standard_normal(n) * np.exp(-x / decay) * density * 0.045
        tail *= np.clip(x / 0.02, 0, 1)
        tail = svf_sweep(tail, "low", damping, min(damping, 450.0), 0.7)  # air absorption: highs die first
        return ir + tail
    if stereo:
        return one(seed), one(seed + 101)
    return one(seed)


def reverb(x, ir, wet=0.35):
    if isinstance(ir, tuple):
        l = signal.fftconvolve(x, ir[0])[: len(x) + len(ir[0]) - 1]
        r = signal.fftconvolve(x, ir[1])[: len(x) + len(ir[1]) - 1]
        dry = np.pad(x, (0, len(l) - len(x)))
        return np.stack([dry * (1 - wet) + l * wet, dry * (1 - wet) + r * wet], axis=1)
    y = signal.fftconvolve(x, ir)
    dry = np.pad(x, (0, len(y) - len(x)))
    return dry * (1 - wet) + y * wet


def finish(x, peak_db=-1.0, fade=0.01):
    x = np.asarray(x, dtype=np.float64)
    nz = np.nonzero(np.abs(x) > 1e-4)[0]
    if len(nz):
        x = x[: nz[-1] + secs(0.02)]  # trim trailing silence
    f = min(secs(fade), len(x))
    ramp = np.linspace(1, 0, f)
    if x.ndim == 2:
        x[-f:] *= ramp[:, None]
    else:
        x[-f:] *= ramp
    x = x - (np.mean(x, axis=0) if x.ndim == 2 else np.mean(x))
    pk = np.max(np.abs(x))
    if pk > 0:
        x = x / pk * 10 ** (peak_db / 20)
    return x


def write(path, x):
    x = np.clip(x, -1, 1)
    data = (x * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(2 if x.ndim == 2 else 1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())


# ---------------------------------------------------------------------------- weapons

def rifle_core(seed, far=False):
    """Dry gunshot: crack + blast + thump + action."""
    T = 0.6
    out = silence(T)
    # Supersonic crack: an N-wave (pressure up, linear fall through zero, snap back), ~0.4 ms.
    nw = secs(0.0004)
    crack = np.concatenate([np.linspace(1, -1, nw), [0.0]])
    out = place(out, filt(crack, "high", 900), 0.0, 0.0 if far else 1.6)
    # Muzzle blast: broadband burst that darkens quickly.
    blast = noise(0.25, seed) * env_ad(0.25, 0.0004, 0.045)
    blast = svf_sweep(blast, "low", 9000 if not far else 3500, 260, 0.6)
    out = place(out, blast, 0.0, 1.5)
    # Body thump: chest-hit low sine with a fast pitch drop, driven.
    th = osc(sweep(125, 42, 0.22)) * env_ad(0.22, 0.0015, 0.05)
    out = place(out, saturate(th * 1.8, 1.5), 0.0, 0.9)
    # Mid "bark": bandpassed noise around 1-2 kHz, a touch of resonance.
    bark = filt(noise(0.12, seed + 2), "band", (700, 2400), order=2) * env_ad(0.12, 0.0006, 0.018)
    out = place(out, bark, 0.0005, 0.9)
    if not far:
        # The action cycling: carrier back (scrape + click), forward (heavier clack with ring).
        out = place(out, filt(noise(0.03, seed + 3), "band", (1800, 5200)) * env_exp(0.03, 0.006), 0.022, 0.18)
        out = place(out, click(seed + 4, 3600, 0.35), 0.034)
        out = place(out, modal(0.12, [(1150, 0.03, 0.6), (2470, 0.02, 0.5), (4130, 0.012, 0.35), (6020, 0.008, 0.2)], seed + 5), 0.058, 0.32)
        out = place(out, osc(sweep(210, 120, 0.05)) * env_exp(0.05, 0.012), 0.058, 0.18)
    return saturate(out * 0.9, 1.3)


def rifle_shot_fp():
    dry = rifle_core(11)
    ir = impulse_response(1.4, 21, early=((0.018, 0.35), (0.041, 0.28), (0.067, 0.2), (0.11, 0.14), (0.17, 0.09)),
                          decay=0.32, damping=3000, density=1.0, stereo=True)
    rumble = filt(noise(1.2, 24, "brown"), "low", 180) * env_ad(1.2, 0.02, 0.28) * 0.5  # distance rumble
    wet = reverb(dry, ir, wet=0.3)
    wet[: len(rumble)] += rumble[:, None]
    return finish(wet)


def rifle_shot_world():
    dry = rifle_core(13, far=False)
    ir = impulse_response(1.6, 23, early=((0.025, 0.38), (0.06, 0.28), (0.12, 0.18), (0.2, 0.12), (0.32, 0.07)),
                          decay=0.42, damping=2600, density=1.0)
    rumble = filt(noise(1.4, 25, "brown"), "low", 160) * env_ad(1.4, 0.03, 0.35) * 0.6
    return finish(place(filt(reverb(dry, ir, wet=0.42), "low", 7000), rumble, 0.0))


def dry_fire():
    out = silence(0.12)
    out = place(out, click(31, 2900, 1.0), 0.0)
    out = place(out, modal(0.08, [(1650, 0.012, 0.5), (3900, 0.006, 0.3)], 32), 0.004, 0.5)
    return finish(reverb(out, impulse_response(0.25, 33, decay=0.05, damping=6000), 0.2), -4)


# ---------------------------------------------------------------------------- reload foley (close, small room)

ROOM = None


def room(x, wet=0.18):
    global ROOM
    if ROOM is None:
        ROOM = impulse_response(0.35, 41, early=((0.004, 0.4), (0.009, 0.3), (0.015, 0.2)), decay=0.06, damping=7000)
    return reverb(x, ROOM, wet)


def scrape(t, f0, f1, seed, amp=1.0):
    n = noise(t, seed) * (0.6 + 0.4 * np.abs(rng(seed + 9).standard_normal(secs(t))) ** 0.5)
    n = svf_sweep(n, "band", f0, f1, 2.5)
    return n * env_ad(t, t * 0.25, t * 0.35) * amp


def rustle(t, seed, lo=1800, hi=7000, grains=40, amp=1.0):
    r = rng(seed)
    out = silence(t)
    for _ in range(grains):
        g = filt(noise(0.012, int(r.integers(1e6))), "band", (lo, hi)) * np.hanning(secs(0.012))
        out = place(out, g, r.uniform(0, t - 0.013), r.uniform(0.2, 1.0))
    return out * amp


def mag_release():
    out = silence(0.12)
    out = place(out, click(51, 3800, 0.9), 0.0)
    out = place(out, modal(0.07, [(5200, 0.01, 0.3), (7600, 0.006, 0.2)], 52), 0.003, 0.4)  # spring tick
    out = place(out, scrape(0.05, 2400, 1500, 53, 0.25), 0.012)
    return finish(room(out), -5)


def mag_out():
    out = silence(0.25)
    out = place(out, scrape(0.12, 2600, 1300, 61, 0.7), 0.0)
    out = place(out, click(62, 2300, 0.6), 0.1)
    out = place(out, osc(sweep(260, 160, 0.06)) * env_exp(0.06, 0.015), 0.1, 0.25)
    return finish(room(out), -5)


def pouch():
    out = silence(0.35)
    out = place(out, rustle(0.22, 71, grains=55, amp=0.6), 0.0)
    out = place(out, filt(noise(0.18, 72, "brown"), "low", 500) * env_ad(0.18, 0.03, 0.05), 0.04, 0.8)  # fabric thump
    out = place(out, rustle(0.06, 73, 3000, 9000, 18, 0.9), 0.0)  # velcro rip start
    return finish(room(out), -7)


def mag_in():
    out = silence(0.22)
    out = place(out, scrape(0.07, 1700, 2600, 81, 0.5), 0.0)
    out = place(out, modal(0.1, [(1820, 0.02, 0.8), (2930, 0.014, 0.6), (4480, 0.008, 0.4)], 82), 0.07, 0.8)
    out = place(out, click(83, 3300, 0.8), 0.07)
    out = place(out, osc(sweep(190, 110, 0.06)) * env_exp(0.06, 0.016), 0.07, 0.35)
    return finish(room(out), -3)


def mag_slap():
    out = silence(0.2)
    out = place(out, filt(noise(0.09, 91), "low", 1100) * env_ad(0.09, 0.0008, 0.02), 0.0, 1.0)
    out = place(out, saturate(osc(sweep(150, 70, 0.08)) * env_exp(0.08, 0.02), 1.4), 0.0, 0.8)
    out = place(out, click(92, 3500, 0.7), 0.002)
    out = place(out, modal(0.1, [(2050, 0.018, 0.5), (3350, 0.012, 0.35)], 93), 0.004, 0.5)
    return finish(room(out, 0.22), -2)


def rack_back():
    out = silence(0.2)
    out = place(out, scrape(0.09, 1200, 3600, 101, 0.8), 0.0)
    out = place(out, click(102, 2700, 0.8), 0.085)
    out = place(out, modal(0.08, [(1450, 0.02, 0.5), (3100, 0.01, 0.35)], 103), 0.087, 0.4)
    return finish(room(out), -4)


def rack_fwd():
    out = silence(0.3)
    out = place(out, scrape(0.04, 3200, 1800, 111, 0.4), 0.0)
    out = place(out, modal(0.22, [(910, 0.06, 0.7), (2240, 0.035, 0.6), (3890, 0.02, 0.45), (5710, 0.012, 0.3)], 112), 0.035, 1.0)
    out = place(out, click(113, 4200, 0.9), 0.035)
    out = place(out, saturate(osc(sweep(240, 95, 0.08)) * env_exp(0.08, 0.02), 1.3), 0.035, 0.5)
    return finish(room(out, 0.22), -2)


def reload_start():
    out = silence(0.3)
    out = place(out, rustle(0.2, 121, 600, 3500, 30, 0.5), 0.0)
    out = place(out, filt(noise(0.2, 122, "brown"), "low", 400) * env_ad(0.2, 0.05, 0.06), 0.0, 0.6)
    return finish(room(out), -10)


# ---------------------------------------------------------------------------- impacts

def impact_hard(seed=131):
    out = silence(0.45)
    crack = filt(noise(0.03, seed), "high", 1500) * env_exp(0.03, 0.004, 0.0002)
    out = place(out, filt(crack, "low", 9000), 0.0, 0.3)
    out = place(out, filt(noise(0.12, seed + 1), "low", 900) * env_ad(0.12, 0.0005, 0.02), 0.0, 1.0)  # chunk
    out = place(out, saturate(osc(sweep(140, 70, 0.07)) * env_exp(0.07, 0.018), 1.3), 0.0, 0.5)  # thud
    out = place(out, rustle(0.3, seed + 2, 3000, 11000, 26, 0.25) * np.linspace(1, 0.1, secs(0.3)), 0.01)  # grit
    out = place(out, modal(0.12, [(1700, 0.02, 0.3), (2900, 0.012, 0.2)], seed + 3), 0.0, 0.35)
    ir = impulse_response(0.6, seed + 4, decay=0.16, damping=3500)
    return finish(reverb(out, ir, 0.25), -3)


def impact_flesh(seed=141):
    out = silence(0.35)
    out = place(out, filt(noise(0.1, seed), "low", 700) * env_ad(0.1, 0.001, 0.025), 0.0, 1.0)  # thud
    out = place(out, saturate(osc(sweep(95, 50, 0.1)) * env_exp(0.1, 0.03), 1.2), 0.0, 0.7)
    wet = svf_sweep(noise(0.18, seed + 1), "band", 1500, 350, 6.0) * env_ad(0.18, 0.004, 0.04)  # squelch
    out = place(out, wet, 0.006, 0.8)
    r = rng(seed + 2)
    for _ in range(4):  # droplets
        f = r.uniform(500, 1200)
        out = place(out, osc(sweep(f, f * 0.55, 0.035)) * env_exp(0.035, 0.008), r.uniform(0.03, 0.15), 0.12)
    return finish(reverb(out, impulse_response(0.4, seed + 3, decay=0.08, damping=5000), 0.18), -3)


# ---------------------------------------------------------------------------- creature voice (stalker)

def glottal(f0, seed, jitter=0.02, shimmer=0.15, breath=0.2):
    """Band-limited pulse train following f0 (array) with jitter / shimmer, plus breath noise."""
    r = rng(seed)
    n = len(f0)
    j = signal.lfilter([0.02], [1, -0.98], r.standard_normal(n)) * jitter * 25
    f = f0 * (1 + j)
    ph = np.cumsum(f) / SR
    saw = 2 * (ph % 1.0) - 1
    src = filt(saw, "low", 5000) - 0.5 * filt(saw, "low", 400)
    amp = 1 + shimmer * signal.lfilter([0.05], [1, -0.95], r.standard_normal(n))
    return src * amp + filt(r.standard_normal(n), "high", 800) * breath


def formants(x, sets, seed=0):
    """sets: [(start_hz, end_hz, q, gain)] swept across the sound."""
    out = np.zeros_like(x)
    for f0, f1, q, g in sets:
        out += svf_sweep(x, "band", f0, f1, q) * g
    return out


def voice(t, f_start, f_peak, f_end, seed, form, rough=0.0, peak_at=0.3):
    n = secs(t)
    x = np.linspace(0, 1, n)
    f0 = np.where(x < peak_at, f_start + (f_peak - f_start) * np.clip(x / peak_at, 0, 1) ** 0.7,
                  f_peak + (f_end - f_peak) * np.clip((x - peak_at) / (1 - peak_at), 0, 1) ** 1.3)
    vib = 1 + 0.03 * np.sin(2 * np.pi * 7.5 * x * t)
    src = glottal(f0 * vib, seed, jitter=0.02 + rough * 0.06, shimmer=0.15 + rough * 0.4, breath=0.25 + rough * 0.3)
    if rough > 0:  # growl: subharmonic amplitude modulation
        src *= 1 + rough * np.sin(2 * np.pi * np.cumsum(f0 * 0.5) / SR)
    return formants(src, form, seed)


def stalker_attack():
    t = 0.62
    form = [(700, 900, 4, 1.0), (1300, 1900, 6, 0.8), (2700, 3300, 8, 0.5), (4200, 4600, 10, 0.25)]
    v = voice(t, 230, 520, 300, 151, form, rough=0.5, peak_at=0.25) * env_ad(t, 0.04, 0.16, 0.18)
    hiss = filt(noise(t, 152), "band", (2500, 9000)) * env_ad(t, 0.01, 0.1) * 0.35
    out = saturate((v + hiss) * 0.8, 1.6)
    return finish(reverb(out, impulse_response(1.0, 153, decay=0.25, damping=4500), 0.28), -2)


def stalker_hurt():
    t = 0.32
    form = [(800, 650, 5, 1.0), (1700, 1300, 7, 0.7), (3000, 2600, 9, 0.4)]
    v = voice(t, 420, 560, 260, 161, form, rough=0.7, peak_at=0.15) * env_ad(t, 0.01, 0.07, 0.05)
    out = saturate(v, 1.8)
    return finish(reverb(out, impulse_response(0.8, 162, decay=0.2, damping=4500), 0.25), -3)


def stalker_death():
    t = 1.5
    form = [(750, 420, 4, 1.0), (1500, 900, 6, 0.7), (2800, 2200, 8, 0.35)]
    v = voice(t, 330, 380, 70, 171, form, rough=0.9, peak_at=0.12) * env_ad(t, 0.03, 0.45, 0.25)
    r = rng(172)
    gurgle = silence(t)
    for _ in range(14):
        f = r.uniform(180, 520)
        gurgle = place(gurgle, osc(sweep(f, f * 0.6, 0.06)) * env_exp(0.06, 0.015), r.uniform(0.5, 1.3), 0.25)
    out = saturate(v + gurgle, 1.5)
    return finish(reverb(out, impulse_response(1.4, 173, decay=0.35, damping=3800), 0.3), -2)


# ---------------------------------------------------------------------------- player + UI

def player_hurt():
    out = silence(0.4)
    out = place(out, filt(noise(0.15, 181), "low", 600) * env_ad(0.15, 0.001, 0.035), 0.0, 1.0)  # hit on armour
    out = place(out, saturate(osc(sweep(110, 55, 0.14)) * env_exp(0.14, 0.04), 1.4), 0.0, 0.9)
    out = place(out, modal(0.15, [(1350, 0.03, 0.4), (2650, 0.02, 0.3)], 182), 0.002, 0.35)  # plate clink
    out = place(out, rustle(0.12, 183, 900, 4000, 14, 0.3), 0.01)
    return finish(out, -4)


def shield_break():
    t = 0.7
    x = np.arange(secs(t)) / SR
    buzz = osc(sweep(1400, 160, t), "saw") * (0.5 + 0.5 * np.sign(np.sin(2 * np.pi * 37 * x))) * 0.4
    fizz = filt(noise(t, 191), "high", 3000) * (rng(192).random(secs(t)) > 0.92) * 1.2
    out = (buzz + fizz) * env_ad(t, 0.005, 0.18)
    out = place(out, saturate(osc(sweep(180, 60, 0.2)) * env_exp(0.2, 0.06), 1.5), 0.0, 0.6)
    return finish(reverb(out, impulse_response(0.6, 193, decay=0.15, damping=6000), 0.2), -3)


def shield_recharge():
    t = 0.8
    x = np.linspace(0, 1, secs(t))
    tone = osc(sweep(220, 660, t)) * 0.5 + osc(sweep(330, 990, t)) * 0.25 + osc(sweep(440, 1320, t), "tri") * 0.15
    shimmer = 1 + 0.25 * np.sin(2 * np.pi * 18 * x * t)
    out = tone * shimmer * np.sin(np.pi * x) ** 0.6
    return finish(reverb(out, impulse_response(0.6, 201, decay=0.2, damping=7000), 0.25), -9)


def hit_tick():
    t = 0.06
    out = (osc(sweep(3300, 3100, t)) * 0.7 + osc(sweep(5100, 4900, t)) * 0.3) * env_exp(t, 0.012, 0.0005)
    out = out + filt(noise(t, 211), "high", 4000) * env_exp(t, 0.002) * 0.4
    return finish(out, -8)


def hit_crit():
    out = silence(0.1)
    for i, f in enumerate((4200, 5600)):
        out = place(out, (osc(sweep(f, f * 0.96, 0.05)) * env_exp(0.05, 0.012, 0.0004)), i * 0.028, 0.8)
    return finish(out, -7)


def hit_kill():
    t = 0.22
    out = saturate(osc(sweep(260, 120, t)) * env_exp(t, 0.06, 0.001), 2.0) * 0.8
    out = place(out, osc(sweep(2400, 2200, 0.06)) * env_exp(0.06, 0.015), 0.0, 0.5)
    out = place(out, osc(sweep(1600, 1500, 0.08)) * env_exp(0.08, 0.02), 0.05, 0.4)
    return finish(out, -6)


def footstep(seed):
    r = rng(seed)
    out = silence(0.22)
    heel = filt(noise(0.06, seed), "low", r.uniform(700, 1100)) * env_ad(0.06, 0.0015, 0.012)
    toe = filt(noise(0.05, seed + 1), "band", (1200, 5000)) * env_ad(0.05, 0.002, 0.01)
    out = place(out, heel, 0.0, 1.0)
    out = place(out, saturate(osc(sweep(90, 60, 0.05)) * env_exp(0.05, 0.012), 1.2), 0.0, 0.5)
    out = place(out, toe, r.uniform(0.035, 0.055), 0.45)
    out = place(out, rustle(0.08, seed + 2, 4000, 11000, 8, 0.12), 0.01)  # grit
    return finish(room(out, 0.15), -10)


SOUNDS = {
    "rifle_shot_fp": rifle_shot_fp,
    "rifle_shot_world": rifle_shot_world,
    "dry_fire": dry_fire,
    "reload_start": reload_start,
    "mag_release": mag_release,
    "mag_out": mag_out,
    "pouch": pouch,
    "mag_in": mag_in,
    "mag_slap": mag_slap,
    "rack_back": rack_back,
    "rack_fwd": rack_fwd,
    "impact_hard": impact_hard,
    "impact_flesh": impact_flesh,
    "stalker_attack": stalker_attack,
    "stalker_hurt": stalker_hurt,
    "stalker_death": stalker_death,
    "player_hurt": player_hurt,
    "shield_break": shield_break,
    "shield_recharge": shield_recharge,
    "hit_tick": hit_tick,
    "hit_crit": hit_crit,
    "hit_kill": hit_kill,
    "footstep_1": lambda: footstep(301),
    "footstep_2": lambda: footstep(311),
    "footstep_3": lambda: footstep(321),
    "footstep_4": lambda: footstep(331),
}


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "unreal", "ShatteredOrbit", "SourceArt", "Audio")
    os.makedirs(out_dir, exist_ok=True)
    for name, fn in SOUNDS.items():
        x = fn()
        write(os.path.join(out_dir, name + ".wav"), x)
        ch = 2 if x.ndim == 2 else 1
        rms = 20 * math.log10(max(np.sqrt(np.mean(x ** 2)), 1e-9))
        print(f"[sfx] {name:18s} {len(x) / SR:5.2f} s  {ch}ch  rms {rms:6.1f} dBFS")


if __name__ == "__main__":
    main()
