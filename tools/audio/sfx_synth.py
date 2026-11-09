"""Shattered Orbit sound effects, synthesised offline (our own; no recorded or third-party audio).

    python tools/audio/sfx_synth.py [out_dir] [name ...]   (default: unreal/ShatteredOrbit/SourceArt/Audio; names = subset)

Weapons: every archetype gets `<id>_shot_fp` (stereo, the player's own gun) and `<id>_shot_world` (mono, positional),
from per-class recipes: KINETIC (kin_core), ENERGY (nrg_core: FM zaps, plasma noise, arcing), rocket and the horror
biomass guns (wet squelches, gurgles, spatter). Then reload / action foley, impacts, loot and UI sounds.

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


# ============================================================================ extended set (all weapons, foley, UI)
# ---------------------------------------------------------------------------- shared helpers

def mix(a, b, gain=1.0, at=0.0):
    """a + gain * b (b placed at `at` s), padding the shorter; a mono b is added to both channels of a stereo a."""
    i = secs(at)
    n = max(len(a), i + len(b))
    st = a.ndim == 2 or b.ndim == 2
    out = np.zeros((n, 2) if st else n)
    out[:len(a)] += a if (a.ndim == 2 or not st) else a[:, None]
    out[i:i + len(b)] += (b if (b.ndim == 2 or not st) else b[:, None]) * gain
    return out


def fadeout(x, t=0.03):
    """Release ramp so a layer never stops while it is still sounding (no click at its end)."""
    x = np.array(x, dtype=np.float64)
    k = min(secs(t), len(x))
    x[len(x) - k:] *= np.linspace(1, 0, k) ** 2
    return x


def tone(f0, f1, t, tau, attack=0.0015, kind="sine"):
    return osc(sweep(f0, f1, t), kind) * env_ad(t, attack, tau)


def thump(f0, f1, t, tau, drive=1.4, attack=0.0015):
    """Pitch-dropping low body hit, driven so it reads as pressure rather than a tone."""
    return saturate(tone(f0, f1, t, tau, attack) * 1.8, drive)


def headroom(x, ceiling):
    """Scale a layer stack so its peak is at most `ceiling` before the final saturation: a little driven glue is
    welcome, but a stack summing to 4-5 would be squashed flat for 30-40 ms and lose its transient."""
    pk = np.max(np.abs(x))
    return x * min(1.0, ceiling / pk) if pk > 0 else x


def nwave(dur):
    """Supersonic crack: pressure jump, linear fall through zero, snap back."""
    nw = max(secs(dur), 4)
    return filt(np.concatenate([np.linspace(1, -1, nw), [0.0]]), "high", 900)


def crackle(t, seed, rate, lo=2500, hi=12000, tau=None, width=0.00025):
    """Electric arcing / acid fizz: Poisson impulses, each a tiny decaying burst, band-limited."""
    r = rng(seed)
    n = secs(t)
    imp = np.zeros(n)
    k = r.poisson(rate * t)
    imp[r.integers(0, n, k)] = r.standard_normal(k)
    kern = np.exp(-np.arange(secs(0.0015)) / (SR * width))
    out = filt(np.convolve(imp, kern)[:n], "band", (lo, hi))
    if tau:
        out *= env_exp(t, tau, 0)
    return out


def fm_zap(t, f0, f1, ratio, index, idx_tau, amp_tau, seed=0, attack=0.0004):
    """Energy discharge: FM pair whose carrier dives in pitch while the modulation index collapses (bright -> pure)."""
    x = np.arange(secs(t)) / SR
    fc = sweep(f0, f1, t)
    mod = np.sin(2 * np.pi * np.cumsum(fc * ratio) / SR + rng(seed).uniform(0, 2 * np.pi))
    car = np.sin(2 * np.pi * np.cumsum(fc) / SR + index * np.exp(-x / idx_tau) * mod)
    return car * env_ad(t, attack, amp_tau)


def squelch(t, f0, f1, seed, q=5.0, attack=0.004, tau=None):
    """Wet resonant cavity: noise through a narrow swept band (gain normalised by q)."""
    return svf_sweep(noise(t, seed), "band", f0, f1, q) / q * env_ad(t, attack, tau or t * 0.3)


def bubbles(t, seed, n, lo, hi, t0, t1, amp=1.0, dur=(0.02, 0.06)):
    """Bubble pops: a bubble's resonance rises as it collapses, so short upward chirps."""
    r = rng(seed)
    out = silence(t)
    for _ in range(n):
        f = r.uniform(lo, hi)
        d = r.uniform(*dur)
        b = tone(f, f * r.uniform(1.3, 1.9), d, d * 0.3, 0.0015)
        out = place(out, b, r.uniform(t0, t1), amp * r.uniform(0.4, 1.0))
    return out


def spatter(t, seed, n, t0, t1, lo=900, hi=5000, amp=1.0):
    """Liquid droplets landing: tiny wet ticks (short band noise plus a quick pitch blip)."""
    r = rng(seed)
    out = silence(t)
    for _ in range(n):
        d = r.uniform(0.006, 0.02)
        g = filt(noise(d, int(r.integers(1e6))), "band", (lo, hi)) * env_exp(d, d * 0.25, 0.0003)
        f = r.uniform(lo * 0.6, lo * 1.6)
        g = g + tone(f, f * 1.5, d, d * 0.3, 0.0005) * 0.5
        out = place(out, g, r.uniform(t0, t1), amp * r.uniform(0.3, 1.0))
    return out


def gurgle(t, f0, f1, seed, form, rough=0.7):
    """Throat / sac gurgle: rough glottal source at low pitch through wet low formants."""
    src = glottal(sweep(f0, f1, t), seed, jitter=0.06, shimmer=0.6, breath=0.35)
    src *= 1 + rough * np.sin(2 * np.pi * np.cumsum(sweep(f0, f1, t) * 0.5) / SR)
    return formants(src, form, seed)


def brass(seed, amp=1.0, f=None):
    """An empty brass casing ringing: a thin tube, high inharmonic modes, fairly long ring."""
    r = rng(seed)
    f = f or r.uniform(3800, 5400)
    return modal(0.18, [(f, 0.06, 1.0), (f * 1.52, 0.04, 0.6), (f * 2.31, 0.025, 0.4), (f * 0.41, 0.03, 0.25)], seed) * amp


def bell(f, t, tau, partials=((1.0, 1.0, 1.0), (2.0, 0.32, 0.55), (3.0, 0.14, 0.35), (4.16, 0.07, 0.22)),
         attack=0.002):
    """Soft struck chime: a few partials, upper ones dying first, with a short attack (no click)."""
    x = np.arange(secs(t)) / SR
    out = np.zeros_like(x)
    for ratio, a, tr in partials:
        out += a * np.sin(2 * np.pi * f * ratio * x) * np.exp(-x / (tau * tr))
    return out * np.clip(x / attack, 0, 1)


def lean(ir, hp=160.0):
    """High-pass an impulse response's reflections and tail (not the direct sound). The synthetic tail is low-passed
    noise, so its gain at 30-60 Hz is far above the direct path; long rooms would otherwise swell a driven low thump
    into a late boom. Applied to the IRs of the extended set only."""
    if isinstance(ir, tuple):
        return tuple(lean(i, hp) for i in ir)
    out = ir.copy()
    out[1:] = filt(ir[1:], "high", hp)
    return out


def echo_taps(x, taps, stretch=1.0, lp=1600):
    """Late discrete echoes off distant facades / hills: darker, smeared copies of the dry shot."""
    k = secs(0.008)
    src = np.convolve(filt(x, "low", lp), np.hanning(k)) / (k / 2)
    out = silence(len(x) / SR + taps[-1][0] * 1.05 + 0.02)
    for t, g in taps:
        out = place(out, src, t * stretch, g)
    return out


EARLY_FP = ((0.018, 0.35), (0.041, 0.28), (0.067, 0.2), (0.11, 0.14), (0.17, 0.09))
EARLY_WORLD = ((0.025, 0.38), (0.06, 0.28), (0.12, 0.18), (0.2, 0.12), (0.32, 0.07))


def shot_space(dry, seed, fp, decay=0.32, wet=0.3, damping=3000, rumble=0.5, rumble_tau=0.28, taps=None, side=None,
               world_lp=7000):
    """Put a dry mono shot in the world. fp: stereo, closer and drier (`side` = decorrelated (l, r) layers for width);
    world: mono, more room, darker, a longer rumble."""
    if fp:
        ir = lean(impulse_response(max(1.2, decay * 4.5), seed, early=EARLY_FP, decay=decay, damping=damping,
                                   density=min(1.0, 0.33 / decay), stereo=True))
        dl, dr = dry, dry
        if side is not None:
            dl, dr = mix(dry, side[0]), mix(dry, side[1])
        n = max(len(dl), len(dr))
        dl, dr = np.pad(dl, (0, n - len(dl))), np.pad(dr, (0, n - len(dr)))
        out = np.stack([reverb(dl, ir[0], wet), reverb(dr, ir[1], wet)], axis=1)
        rd = max(0.8, rumble_tau * 4.5)
        out = mix(out, filt(noise(rd, seed + 3, "brown"), "low", 180) * env_ad(rd, 0.02, rumble_tau), rumble)
        if taps:
            out = mix(out, np.stack([echo_taps(dry, taps, 1.0), echo_taps(dry, taps, 1.04)], axis=1))
        return finish(out)
    d2 = decay * 1.3
    ir = lean(impulse_response(max(1.4, d2 * 4.5), seed + 1, early=EARLY_WORLD, decay=d2, damping=damping * 0.87,
                              density=min(1.0, 0.42 / d2)))  # long rooms: keep the tail energy near the rifle's
    out = filt(reverb(dry, ir, min(wet + 0.12, 0.6)), "low", world_lp)
    rd = max(1.0, rumble_tau * 5.5)
    out = mix(out, filt(noise(rd, seed + 4, "brown"), "low", 160) * env_ad(rd, 0.03, rumble_tau * 1.25), rumble * 1.2)
    if taps:
        out = mix(out, echo_taps(dry, [(t, g * 0.7) for t, g in taps], 1.0, 1200))
    return finish(out)


# ---------------------------------------------------------------------------- kinetic firearms

def act_carbine(s):  # light carrier, fast cycle
    return [(0.016, filt(noise(0.025, s), "band", (2200, 6000)) * env_exp(0.025, 0.005), 0.15),
            (0.027, click(s + 1, 4100, 0.3), 1.0),
            (0.046, modal(0.1, [(1380, 0.025, 0.6), (2890, 0.017, 0.5), (4720, 0.01, 0.35), (6850, 0.007, 0.2)], s + 2), 0.28),
            (0.046, tone(250, 140, 0.04, 0.01), 0.14)]


def act_dmr(s):  # long-stroke op rod: heavier, slower, more ring
    return [(0.026, filt(noise(0.04, s), "band", (1400, 4200)) * env_exp(0.04, 0.008), 0.2),
            (0.04, click(s + 1, 3000, 0.4), 1.0),
            (0.074, modal(0.16, [(880, 0.045, 0.7), (1910, 0.03, 0.55), (3330, 0.018, 0.4), (5120, 0.01, 0.25)], s + 2), 0.38),
            (0.074, tone(170, 90, 0.07, 0.018), 0.22)]


def act_ksmg(s):  # straight blowback: a short bolt slam, done before the next round
    return [(0.011, click(s, 3400, 0.35), 1.0),
            (0.028, modal(0.06, [(1310, 0.014, 0.6), (2620, 0.01, 0.45), (4410, 0.006, 0.3)], s + 1), 0.25),
            (0.028, tone(230, 130, 0.03, 0.007), 0.12)]


def act_pistol(s):  # slide snaps back to the frame, then slams home
    return [(0.007, filt(noise(0.014, s), "band", (2500, 6500)) * env_exp(0.014, 0.003), 0.18),
            (0.018, click(s + 1, 4400, 0.4), 1.0),
            (0.034, modal(0.08, [(2120, 0.018, 0.6), (3710, 0.012, 0.45), (5930, 0.007, 0.3)], s + 2), 0.3),
            (0.034, click(s + 3, 5200, 0.25), 1.0)]


ACTIONS = {"carbine": act_carbine, "dmr": act_dmr, "ksmg": act_ksmg, "pistol": act_pistol}


def kin_core(seed, P):
    """Dry firearm shot from a recipe P (same layers as rifle_core, sized per calibre / action)."""
    out = silence(P.get("T", 0.6))
    if "crack" in P:
        g, d = P["crack"]
        out = place(out, nwave(d), 0.0, g)
    if "snap" in P:  # sharp short-barrel transient
        out = place(out, filt(noise(0.008, seed + 7), "high", 3000) * env_exp(0.008, 0.0009, 0.0001), 0.0, P["snap"])
    d, tau, hi, lo, g = P["blast"]
    out = place(out, svf_sweep(noise(d, seed) * env_ad(d, 0.0004, tau), "low", hi, lo, 0.6), 0.0, g)
    f0, f1, d, tau, g, drive = P["thump"]
    out = place(out, thump(f0, f1, d, tau, drive), 0.0, g)
    lo, hi, tau, g = P["bark"]
    out = place(out, filt(noise(tau * 7, seed + 2), "band", (lo, hi)) * env_ad(tau * 7, 0.0006, tau), 0.0005, g)
    if "sub" in P:
        f0, f1, d, tau, g = P["sub"]
        out = place(out, tone(f0, f1, d, tau, 0.004), 0.002, g)
    if "boom" in P:  # shotgun: the slower expanding gas cloud under the blast
        d, lp, tau, g = P["boom"]
        out = place(out, filt(noise(d, seed + 8), "low", lp) * env_ad(d, 0.006, tau), 0.001, g)
    if "gap" in P:  # revolver: cylinder-gap jet, a hard sizzle
        out = place(out, filt(noise(0.08, seed + 6), "band", (3000, 11000)) * env_ad(0.08, 0.0003, 0.012), 0.0003, P["gap"])
    if "ring" in P:  # the gun's own steel ringing after the shot
        modes, g = P["ring"]
        out = place(out, modal(0.5, modes, seed + 9), 0.002, g)
    if P.get("action"):
        for at, sig, g in ACTIONS[P["action"]](seed + 10):
            out = place(out, sig, at, g)
    return saturate(headroom(out, P.get("hot", 3.0)) * 0.9, P.get("drive", 1.3))


KINETIC = {
    # 5.56-ish short carbine: snappier, brighter, lighter body than the rifle
    "carbine": dict(seed=1001, T=0.5, crack=(1.5, 0.00032), blast=(0.2, 0.03, 10000, 320, 1.45),
                    thump=(150, 55, 0.15, 0.027, 0.75, 1.4), bark=(900, 3000, 0.015, 1.0), action="carbine",
                    space=dict(decay=0.28, wet=0.3, rumble=0.4, rumble_tau=0.22)),
    # heavy battle rifle: big crack, deep chest punch, op rod clank
    "dmr": dict(seed=1101, T=0.8, crack=(1.9, 0.0005), blast=(0.3, 0.055, 8500, 230, 1.6),
                thump=(112, 38, 0.24, 0.05, 1.0, 1.5), bark=(600, 2000, 0.022, 0.9), sub=(70, 32, 0.35, 0.07, 0.25),
                action="dmr", drive=1.4,
                space=dict(decay=0.38, wet=0.32, rumble=0.42, rumble_tau=0.32, taps=[(0.42, 0.12)])),
    # compact pistol-calibre SMG: short, punchy, quick blowback (body done in ~80 ms at 850 rpm)
    "ksmg": dict(seed=1201, T=0.25, crack=(0.35, 0.0002), snap=0.5, blast=(0.12, 0.02, 8000, 450, 1.4),
                 thump=(190, 80, 0.09, 0.019, 0.6, 1.4), bark=(1000, 3200, 0.011, 1.1), action="ksmg",
                 space=dict(decay=0.24, wet=0.28, rumble=0.25, rumble_tau=0.16)),
    # big bolt-action: very loud crack, deep, long valley echo, barrel ring
    "bolt": dict(seed=1301, T=1.0, crack=(2.3, 0.0006), blast=(0.42, 0.065, 9500, 200, 1.7),
                 thump=(115, 32, 0.3, 0.055, 1.15, 1.5), bark=(650, 2200, 0.026, 0.9), sub=(60, 28, 0.45, 0.09, 0.3),
                 ring=([(1520, 0.06, 0.6), (3440, 0.04, 0.4), (5210, 0.025, 0.25)], 0.06), drive=1.45,
                 space=dict(decay=0.5, wet=0.34, rumble=0.5, rumble_tau=0.45,
                            taps=[(0.34, 0.2), (0.61, 0.14), (0.95, 0.09), (1.4, 0.05)])),
    # 9 mm-ish service pistol: subsonic (no crack), sharp snap, slide action
    "pistol": dict(seed=1401, T=0.45, snap=0.9, blast=(0.15, 0.026, 11000, 420, 1.5),
                   thump=(175, 70, 0.12, 0.026, 0.7, 1.4), bark=(1100, 3800, 0.013, 1.15), action="pistol",
                   space=dict(decay=0.3, wet=0.3, rumble=0.35, rumble_tau=0.2)),
    # heavy magnum revolver: booming, cylinder-gap sizzle, frame ring
    "revolver": dict(seed=1501, T=0.9, crack=(0.7, 0.0003), snap=0.4, blast=(0.32, 0.06, 7000, 180, 1.7),
                     thump=(100, 34, 0.26, 0.05, 1.15, 1.5), bark=(500, 1700, 0.024, 0.9), sub=(62, 30, 0.4, 0.08, 0.3),
                     gap=0.6, ring=([(1930, 0.05, 0.6), (4120, 0.03, 0.4)], 0.05), drive=1.45,
                     space=dict(decay=0.4, wet=0.33, rumble=0.45, rumble_tau=0.34, taps=[(0.38, 0.14), (0.7, 0.08)])),
    # 12-gauge pump: no crack, wide gas boom, deep thump, receiver/tube ring
    "pump": dict(seed=1601, T=1.0, blast=(0.4, 0.07, 6000, 150, 1.8), thump=(88, 32, 0.3, 0.06, 1.3, 1.5),
                 bark=(400, 1500, 0.03, 0.9), sub=(55, 26, 0.45, 0.09, 0.35), boom=(0.45, 900, 0.07, 0.6),
                 ring=([(700, 0.06, 0.6), (1650, 0.04, 0.45), (2900, 0.025, 0.3)], 0.05), drive=1.5, wide=0.45,
                 space=dict(decay=0.4, wet=0.34, rumble=0.5, rumble_tau=0.36, taps=[(0.45, 0.12)])),
}


def wide_layers(seed, d=0.35, tau=0.06, lp=2500, g=0.5):
    """Two decorrelated blast layers (left / right) so a big muzzle cloud sounds wide in the player's ears."""
    return tuple(filt(noise(d, seed + i), "low", lp) * env_ad(d, 0.002, tau) * g for i in (0, 1))


def kin_shot(gun, fp):
    P = KINETIC[gun]
    s = P["seed"] + (0 if fp else 50)
    dry = kin_core(s, P)
    side = wide_layers(s + 20, g=P["wide"]) if (fp and P.get("wide")) else None
    return shot_space(dry, s + 30, fp, side=side, **P["space"])


# ---------------------------------------------------------------------------- energy weapons

def nrg_core(seed, P):
    """Dry energy discharge: capacitor snap, FM zaps, plasma noise, air push, thump, arcing, emitter ring, whine."""
    out = silence(P["T"])
    r = rng(seed + 50)
    t0 = 0.0
    if "pre" in P:  # very short charge chirp right before the discharge
        d, f0, f1, g = P["pre"]
        ch = (osc(sweep(f0, f1, d)) + 0.4 * osc(sweep(f0 * 2.01, f1 * 2.01, d))) * np.linspace(0, 1, secs(d)) ** 2
        out = place(out, ch, 0.0, g)
        t0 = d
    if "tick" in P:
        f, g = P["tick"]
        out = place(out, click(seed, f, 1.0, 0.02), t0, g)
    for i, (f0, f1, d, ratio, idx, itau, atau, g) in enumerate(P.get("zaps", [])):
        out = place(out, fm_zap(d, f0, f1, ratio, idx, itau, atau, seed + 10 + i), t0, g)
    if "pellets" in P:
        n, spread, (lo, hi), (flo, fhi), d, ratio, idx, g = P["pellets"]
        for k in range(n):
            dd = d * r.uniform(0.8, 1.2)
            at = t0 + r.uniform(0, spread)
            z = fm_zap(dd, r.uniform(lo, hi), r.uniform(flo, fhi), ratio * r.uniform(0.97, 1.03), idx, dd * 0.3, dd * 0.3,
                       seed + 30 + k)
            out = place(out, z, at, g * r.uniform(0.6, 1.0))
            out = place(out, crackle(dd, seed + 60 + k, 2500, 3000, 12000, dd * 0.25), at, g * 0.8)
    if "burst" in P:
        d, f0, f1, q, tau, g = P["burst"]
        out = place(out, svf_sweep(noise(d, seed + 1), "band", f0, f1, q) / q ** 0.5 * env_ad(d, 0.0005, tau), t0, g)
    if "air" in P:
        d, hi, lo, tau, g = P["air"]
        out = place(out, svf_sweep(noise(d, seed + 2) * env_ad(d, 0.0004, tau), "low", hi, lo, 0.6), t0, g)
    if "thump" in P:
        f0, f1, d, tau, g, drive = P["thump"]
        out = place(out, thump(f0, f1, d, tau, drive), t0, g)
    if "sub" in P:
        f0, f1, d, tau, g = P["sub"]
        out = place(out, tone(f0, f1, d, tau, 0.004), t0 + 0.002, g)
    if "crackle" in P:
        d, rate, tau, g = P["crackle"]
        out = place(out, crackle(d, seed + 3, rate, 2500, 12000, tau), t0, g)
    if "ring" in P:
        modes, g = P["ring"]
        out = place(out, modal(max(m[1] for m in modes) * 6, modes, seed + 4), t0 + 0.001, g)
    if "whine" in P:  # capacitor recovering
        f0, f1, d, g, at = P["whine"]
        w = osc(sweep(f0, f1, d)) + 0.25 * osc(sweep(f0 * 3, f1 * 3, d), "tri")
        out = place(out, w * np.sin(np.pi * np.linspace(0, 1, secs(d)) ** 0.6) ** 2, t0 + at, g)
    return saturate(headroom(out, P.get("hot", 3.0)) * 0.9, P.get("drive", 1.3))


ENERGY = {
    # auto rifle, 600 rpm: mid, punchy, a little arcing
    "auto": dict(seed=2001, T=0.45, tick=(5200, 0.3), zaps=[(1900, 320, 0.09, 1.5, 3.0, 0.02, 0.022, 0.55)],
                 burst=(0.12, 5000, 900, 3, 0.02, 0.8), air=(0.15, 6500, 300, 0.028, 1.2),
                 thump=(150, 50, 0.14, 0.03, 0.9, 1.5), crackle=(0.08, 900, 0.02, 0.3),
                 ring=([(2300, 0.03, 0.5), (3900, 0.02, 0.35), (6100, 0.012, 0.2)], 0.15),
                 space=dict(decay=0.3, wet=0.28, rumble=0.35, rumble_tau=0.2)),
    # pulse rifle (3-round bursts at 900 rpm): tight bright pew with a resonant ring, body < 60 ms
    "pulse": dict(seed=2101, T=0.35, tick=(6200, 0.25),
                  zaps=[(2600, 520, 0.06, 2.0, 2.2, 0.015, 0.016, 0.6), (5200, 1100, 0.04, 1.0, 1.2, 0.01, 0.01, 0.2)],
                  burst=(0.08, 6200, 1400, 4, 0.012, 0.8), air=(0.1, 7000, 400, 0.017, 1.0),
                  thump=(180, 70, 0.08, 0.016, 0.7, 1.4), crackle=(0.05, 600, 0.015, 0.2),
                  ring=([(3100, 0.035, 0.5), (4870, 0.022, 0.35), (7400, 0.012, 0.2)], 0.2),
                  space=dict(decay=0.28, wet=0.28, rumble=0.3, rumble_tau=0.18)),
    # scout: precise and bright, long glassy emitter ring, faint recharge whine
    "scout": dict(seed=2201, T=0.9, tick=(6000, 0.4), zaps=[(3200, 600, 0.14, 1.41, 3.5, 0.03, 0.035, 0.55)],
                  burst=(0.18, 7500, 1200, 5, 0.03, 0.7), air=(0.22, 8000, 260, 0.04, 1.3),
                  thump=(140, 45, 0.2, 0.045, 1.0, 1.5), crackle=(0.2, 600, 0.06, 0.25),
                  ring=([(2700, 0.08, 0.5), (4450, 0.06, 0.4), (7300, 0.04, 0.25)], 0.2),
                  whine=(1800, 2600, 0.3, 0.04, 0.06),
                  space=dict(decay=0.38, wet=0.32, rumble=0.5, rumble_tau=0.3, taps=[(0.3, 0.1)])),
    # hand cannon: heavy energy revolver, growling sub-harmonic zap and a big punch
    "handcannon": dict(seed=2301, T=0.8, tick=(4200, 0.4), zaps=[(1200, 160, 0.2, 0.5, 4.0, 0.05, 0.05, 0.6)],
                       burst=(0.22, 3500, 400, 2.5, 0.04, 0.9), air=(0.3, 5500, 180, 0.055, 1.6),
                       thump=(105, 34, 0.26, 0.055, 1.2, 1.5), sub=(60, 30, 0.35, 0.07, 0.25),
                       crackle=(0.25, 700, 0.08, 0.3),
                       ring=([(1500, 0.06, 0.5), (2650, 0.04, 0.4), (4100, 0.03, 0.25)], 0.2), drive=1.45,
                       space=dict(decay=0.4, wet=0.33, rumble=0.45, rumble_tau=0.32, taps=[(0.36, 0.12)])),
    # energy shotgun: eight arcing pellets inside a wide blast, heavy crackle
    "shotgun": dict(seed=2401, T=1.0, tick=(3800, 0.4),
                    pellets=(8, 0.018, (2000, 3400), (300, 500), 0.07, 1.37, 2.5, 0.32),
                    burst=(0.3, 4500, 350, 1.5, 0.06, 1.0), air=(0.4, 6000, 150, 0.07, 1.8),
                    thump=(90, 30, 0.3, 0.06, 1.3, 1.5), crackle=(0.4, 2500, 0.1, 0.6), drive=1.5, wide=0.5,
                    space=dict(decay=0.42, wet=0.34, rumble=0.5, rumble_tau=0.36)),
    # sniper: a 20 ms charge chirp, then a high-power discharge with a lingering plasma fizz and recharge whine
    "sniper": dict(seed=2501, T=2.2, hot=2.4, pre=(0.02, 900, 3600, 0.25), tick=(7000, 0.6),
                   zaps=[(4200, 140, 0.5, 1.5, 6.0, 0.06, 0.09, 0.55), (800, 120, 0.4, 0.25, 3.0, 0.06, 0.07, 0.25)],
                   burst=(0.5, 9000, 300, 3, 0.07, 0.9), air=(0.6, 9000, 120, 0.09, 1.6),
                   thump=(120, 28, 0.45, 0.08, 1.3, 1.5), sub=(55, 30, 0.5, 0.09, 0.15),
                   crackle=(0.9, 500, 0.3, 0.35),
                   ring=([(1850, 0.25, 0.4), (3020, 0.18, 0.3), (4880, 0.12, 0.2), (7400, 0.08, 0.12)], 0.25),
                   whine=(900, 3400, 0.9, 0.05, 0.15), drive=1.45,
                   space=dict(decay=0.6, wet=0.36, rumble=0.65, rumble_tau=0.5,
                              taps=[(0.38, 0.22), (0.72, 0.15), (1.15, 0.09), (1.7, 0.05)])),
    # SMG, 900 rpm: light rapid zaps, body < 60 ms
    "smg": dict(seed=2601, T=0.3, tick=(6400, 0.2), zaps=[(2800, 700, 0.05, 2.5, 1.8, 0.012, 0.012, 0.55)],
                burst=(0.06, 6500, 1500, 3.5, 0.011, 0.8), air=(0.07, 7500, 600, 0.014, 1.0),
                thump=(220, 90, 0.06, 0.013, 0.55, 1.3), crackle=(0.05, 800, 0.015, 0.25),
                ring=([(3500, 0.02, 0.5), (5600, 0.012, 0.3)], 0.12),
                space=dict(decay=0.24, wet=0.26, rumble=0.22, rumble_tau=0.14)),
    # sidearm: light pistol zap
    "sidearm": dict(seed=2701, T=0.45, tick=(5800, 0.3),
                    zaps=[(2300, 480, 0.09, 1.5, 2.4, 0.02, 0.022, 0.6), (4600, 900, 0.05, 1.0, 1.0, 0.01, 0.012, 0.15)],
                    burst=(0.1, 5500, 900, 3, 0.02, 0.8), air=(0.13, 7000, 380, 0.024, 1.1),
                    thump=(180, 62, 0.11, 0.025, 0.7, 1.4),
                    ring=([(2900, 0.03, 0.5), (4700, 0.02, 0.3)], 0.12),
                    space=dict(decay=0.28, wet=0.28, rumble=0.3, rumble_tau=0.2)),
    # energy rifle, 6 pellets: crackling multi-zap with a sawtooth-ish growl underneath
    "energy": dict(seed=2801, T=0.9, tick=(4800, 0.35), zaps=[(1400, 300, 0.3, 0.5, 2.0, 0.08, 0.07, 0.3)],
                   pellets=(6, 0.028, (1600, 2600), (260, 420), 0.1, 1.37, 3.0, 0.4),
                   burst=(0.3, 6000, 1200, 2, 0.05, 0.6), air=(0.3, 6000, 250, 0.05, 1.2),
                   thump=(220, 70, 0.3, 0.06, 1.0, 1.5), crackle=(0.35, 3000, 0.09, 0.7),
                   ring=([(2100, 0.05, 0.5), (3470, 0.035, 0.35)], 0.15),
                   space=dict(decay=0.38, wet=0.32, rumble=0.55, rumble_tau=0.3)),
    # heavy machine gun, 1100 rpm: deep and short (body < 55 ms), low steel ring
    "hmg": dict(seed=2901, T=0.4, tick=(3600, 0.3), zaps=[(900, 140, 0.05, 0.5, 3.0, 0.012, 0.014, 0.5)],
                burst=(0.06, 3000, 500, 2, 0.01, 0.8), air=(0.08, 4500, 200, 0.013, 1.4),
                thump=(115, 42, 0.07, 0.014, 1.2, 1.5), crackle=(0.04, 500, 0.012, 0.15),
                ring=([(820, 0.03, 0.5), (1730, 0.02, 0.35)], 0.2), drive=1.45,
                space=dict(decay=0.3, wet=0.3, rumble=0.45, rumble_tau=0.2)),
}


def nrg_shot(gun, fp):
    P = ENERGY[gun]
    s = P["seed"] + (0 if fp else 50)
    dry = nrg_core(s, P)
    side = None
    if fp and P.get("wide"):
        side = tuple(crackle(0.35, s + 20 + i, 1800, 2000, 11000, 0.09) * P["wide"] * 0.6
                     + wide_layers(s + 22 + i, 0.35, 0.06, 3000, P["wide"])[0] for i in (0, 1))
    return shot_space(dry, s + 30, fp, side=side, **P["space"])


def rocket_core(seed):
    """Launch: motor ignition pop, tube back-blast, thump, then the motor roar leaving (falling pitch, flutter)."""
    T = 2.2
    out = silence(T)
    out = place(out, click(seed, 1800, 1.0, 0.03), 0.0, 0.6)
    out = place(out, svf_sweep(noise(0.5, seed + 1) * env_ad(0.5, 0.0006, 0.07), "low", 7000, 200, 0.6), 0.0, 1.4)
    out = place(out, thump(95, 34, 0.4, 0.09, 1.5, 0.002), 0.0, 1.0)
    d = 1.9
    fl = filt(rng(seed + 3).standard_normal(secs(d)), "low", 45)
    flutter = np.clip(1 + 0.35 * fl / np.std(fl), 0.2, None)  # turbulent gas flutter
    roar = svf_sweep(noise(d, seed + 2) * flutter, "band", 2200, 650, 1.1) * env_ad(d, 0.035, 0.45)
    out = place(out, roar, 0.01, 0.9)
    out = place(out, filt(noise(d, seed + 4), "band", (3500, 11000)) * env_ad(d, 0.02, 0.25) * flutter, 0.01, 0.35)
    out = place(out, filt(noise(d, seed + 5, "brown"), "low", 220) * env_ad(d, 0.05, 0.5), 0.0, 0.5)
    out = place(out, filt(osc(sweep(150, 95, d), "saw"), "low", 900) * env_ad(d, 0.04, 0.35), 0.01, 0.12)
    return saturate(out * 0.9, 1.4)


def rocket_shot(fp):
    dry = rocket_core(3001 + (0 if fp else 50))
    return shot_space(dry, 3031 + (0 if fp else 50), fp, decay=0.45, wet=0.34, rumble=0.7, rumble_tau=0.45,
                      taps=[(0.4, 0.12), (0.8, 0.07)])


# ---------------------------------------------------------------------------- horror biomass guns

def spit_core(seed):
    """Acid spit (300 rpm): lip pressure pop, a narrow wet squelch, the glob tearing free, a short acid fizz."""
    out = silence(0.5)
    out = place(out, filt(noise(0.03, seed), "low", 1400) * env_ad(0.03, 0.0008, 0.006), 0.0, 1.0)  # pressure pop
    out = place(out, thump(160, 60, 0.06, 0.012, 1.3), 0.0, 0.7)
    out = place(out, squelch(0.14, 2200, 700, seed + 1, 5.0, 0.003, 0.03), 0.002, 2.2)
    out = place(out, squelch(0.08, 900, 1700, seed + 2, 7.0, 0.002, 0.018), 0.01, 1.2)  # glob tearing free
    form = [(520, 420, 4, 1.0), (1150, 950, 6, 0.5)]
    out = place(out, gurgle(0.1, 110, 80, seed + 3, form, 0.8) * env_ad(0.1, 0.004, 0.025), 0.0, 0.35)
    out = place(out, crackle(0.3, seed + 4, 1800, 3000, 9000, 0.08) * env_ad(0.3, 0.02, 0.1), 0.02, 0.35)  # fizz
    out = place(out, bubbles(0.3, seed + 5, 3, 600, 1300, 0.03, 0.15, 0.12), 0.0)
    out = place(out, spatter(0.3, seed + 6, 5, 0.005, 0.06, 1200, 5000, 0.35), 0.0)
    return saturate(out * 0.9, 1.4)


def bile_core(seed):
    """Retching bile blast: a rough throat heave, a wide wet spray of pellets, a deep gut thump, gurgling after."""
    out = silence(0.95)
    form = [(500, 380, 4, 1.0), (1100, 800, 5, 0.6), (2300, 1900, 7, 0.3)]
    v = voice(0.32, 120, 190, 70, seed, form, rough=0.9, peak_at=0.2) * env_ad(0.32, 0.02, 0.09)
    out = place(out, v, 0.0, 0.7)
    out = place(out, svf_sweep(noise(0.4, seed + 1) * env_ad(0.4, 0.002, 0.06), "low", 3000, 250, 0.7), 0.01, 1.2)
    out = place(out, squelch(0.3, 900, 300, seed + 2, 3.0, 0.004, 0.06), 0.01, 1.6)
    out = place(out, thump(80, 38, 0.2, 0.05, 1.5), 0.008, 0.8)
    out = place(out, spatter(0.9, seed + 3, 34, 0.04, 0.4, 800, 4000, 0.4), 0.0)
    out = place(out, bubbles(0.9, seed + 4, 8, 300, 900, 0.1, 0.6, 0.12), 0.0)
    out = place(out, gurgle(0.45, 70, 50, seed + 5, [(380, 300, 4, 1.0), (850, 700, 5, 0.4)], 0.8)
                * env_ad(0.45, 0.06, 0.12), 0.18, 0.25)
    return saturate(out * 0.9, 1.5)


def brood_core(seed):
    """Brood sac launch: a heavy wet gut thump, the sac stretching free (rising pop), membrane slap, gurgle + vent."""
    out = silence(1.25)
    out = place(out, thump(75, 30, 0.3, 0.06, 1.5, 0.003), 0.0, 1.0)
    out = place(out, filt(noise(0.2, seed), "low", 600) * env_ad(0.2, 0.003, 0.05), 0.0, 1.0)
    out = place(out, squelch(0.16, 400, 1600, seed + 1, 4.0, 0.006, 0.04), 0.004, 2.2)  # womb pop
    out = place(out, filt(noise(0.02, seed + 2), "low", 2500) * env_exp(0.02, 0.006, 0.0003), 0.03, 0.6)  # membrane slap
    form = [(350, 300, 4, 1.0), (800, 650, 5, 0.45), (1700, 1500, 7, 0.2)]
    out = place(out, fadeout(gurgle(0.6, 60, 45, seed + 3, form, 0.8) * env_ad(0.6, 0.05, 0.16)), 0.1, 0.35)
    out = place(out, bubbles(1.0, seed + 4, 10, 180, 500, 0.08, 0.7, 0.15, (0.03, 0.08)), 0.0)
    out = place(out, filt(noise(0.5, seed + 5), "band", (400, 2500)) * env_ad(0.5, 0.05, 0.15), 0.08, 0.2)  # vent
    out = place(out, spatter(1.0, seed + 6, 10, 0.02, 0.25, 700, 3000, 0.25), 0.0)
    return saturate(out * 0.9, 1.5)


def horror_shot(gun, fp):
    core, seed, space = {
        "spitter": (spit_core, 4001, dict(decay=0.22, wet=0.24, rumble=0.18, rumble_tau=0.14, damping=4000)),
        "bile": (bile_core, 4101, dict(decay=0.3, wet=0.28, rumble=0.4, rumble_tau=0.25, damping=3500)),
        "brood": (brood_core, 4201, dict(decay=0.32, wet=0.28, rumble=0.3, rumble_tau=0.28, damping=3200)),
    }[gun]
    s = seed + (0 if fp else 50)
    return shot_space(core(s), s + 30, fp, **space)


# ---------------------------------------------------------------------------- reload / action foley

def mag_clatter():
    """An emptied mag dropping onto concrete: first hit, two bounces, follower rattle, settles with a scrape."""
    out = silence(0.7)
    for at, g, s in ((0.0, 1.0, 0), (0.11, 0.55, 1), (0.19, 0.3, 2)):
        out = place(out, click(501 + s, 1800, 0.9), at, g)
        out = place(out, modal(0.16, [(930, 0.03, 0.7), (1840, 0.022, 0.6), (3120, 0.014, 0.45), (4710, 0.009, 0.3)],
                               504 + s), at + 0.001, g * 0.8)
        out = place(out, filt(noise(0.05, 507 + s), "low", 900) * env_ad(0.05, 0.0006, 0.01), at, g * 0.7)
    r = rng(510)
    for k in range(5):  # follower / spring rattling inside
        out = place(out, click(511 + k, r.uniform(4000, 6500), 0.25, 0.02), 0.02 + k * 0.035 + r.uniform(0, 0.01))
    out = place(out, scrape(0.14, 1500, 900, 520, 0.35), 0.24)
    return finish(room(out, 0.2), -3)


def mag_tap():
    out = silence(0.18)
    out = place(out, filt(noise(0.06, 531), "low", 900) * env_ad(0.06, 0.0007, 0.012), 0.0, 1.0)
    out = place(out, thump(170, 90, 0.06, 0.014, 1.3), 0.0, 0.6)
    out = place(out, click(532, 2800, 0.4), 0.001)
    out = place(out, modal(0.08, [(1950, 0.014, 0.4), (3200, 0.009, 0.3)], 533), 0.002, 0.4)
    return finish(room(out, 0.2), -4)


def slide_back():
    out = silence(0.18)
    out = place(out, click(541, 3900, 0.4, 0.02), 0.0)  # fingers bite the serrations
    out = place(out, scrape(0.07, 1600, 4000, 542, 0.7), 0.004)
    out = place(out, click(543, 3600, 0.8), 0.068)  # slide at the rear
    out = place(out, modal(0.07, [(2400, 0.016, 0.4), (5300, 0.008, 0.3)], 544), 0.07, 0.35)
    return finish(room(out), -4)


def slide_fwd():
    out = silence(0.22)
    out = place(out, scrape(0.025, 3600, 2000, 551, 0.4), 0.0)
    out = place(out, modal(0.16, [(1310, 0.04, 0.7), (2720, 0.028, 0.6), (4610, 0.016, 0.45), (6890, 0.01, 0.3)], 552), 0.024, 1.0)
    out = place(out, click(553, 4600, 0.9), 0.024)
    out = place(out, thump(230, 110, 0.06, 0.015, 1.3), 0.024, 0.4)
    return finish(room(out, 0.22), -2)


def charge_back():
    out = silence(0.3)
    out = place(out, click(561, 4300, 0.45, 0.02), 0.0)  # handle unlatches
    out = place(out, scrape(0.11, 1000, 3000, 562, 0.75), 0.01)
    spring = modal(0.12, [(5900, 0.03, 0.4), (7350, 0.02, 0.3)], 563) * (1 + 0.5 * np.sin(np.linspace(0, 40, secs(0.12))))
    out = place(out, spring, 0.03, 0.15)  # buffer spring compressing
    out = place(out, click(564, 2600, 0.85), 0.118)
    out = place(out, modal(0.09, [(1380, 0.022, 0.5), (2950, 0.012, 0.35)], 565), 0.12, 0.4)
    return finish(room(out), -4)


def charge_fwd():
    out = silence(0.32)
    out = place(out, scrape(0.035, 3000, 1700, 571, 0.4), 0.0)
    out = place(out, modal(0.22, [(860, 0.06, 0.7), (2010, 0.035, 0.6), (3640, 0.02, 0.45), (5330, 0.012, 0.3)], 572), 0.032, 1.0)
    out = place(out, click(573, 3900, 0.9), 0.032)
    out = place(out, thump(220, 95, 0.08, 0.02, 1.3), 0.032, 0.5)
    out = place(out, click(574, 4800, 0.35, 0.02), 0.075)  # handle clicks home
    return finish(room(out, 0.22), -2)


def latch():
    out = silence(0.12)
    out = place(out, click(581, 4200, 0.8), 0.0)
    out = place(out, modal(0.06, [(5600, 0.01, 0.3), (8100, 0.006, 0.2)], 582), 0.002, 0.4)
    out = place(out, click(583, 3300, 0.45), 0.03)
    return finish(room(out), -6)


def cyl_open():
    out = silence(0.45)
    out = place(out, scrape(0.06, 900, 1800, 591, 0.45), 0.0)  # crane swing
    out = place(out, click(592, 2600, 0.8), 0.055)  # crane stops on the frame
    out = place(out, modal(0.14, [(1720, 0.035, 0.6), (3480, 0.02, 0.4), (5600, 0.012, 0.25)], 593), 0.056, 0.45)
    t = 0.07
    for k in range(7):  # cylinder spinning free on the crane, pawl ticking slower and slower
        t += 0.018 * 1.25 ** k
        out = place(out, click(594 + k, 5200, 0.22 * 0.85 ** k, 0.02), t)
    return finish(room(out), -4)


def cyl_close():
    out = silence(0.32)
    out = place(out, scrape(0.04, 1800, 900, 611, 0.4), 0.0)  # flick
    out = place(out, modal(0.18, [(1420, 0.045, 0.7), (2910, 0.03, 0.55), (4820, 0.018, 0.4)], 612), 0.038, 1.0)
    out = place(out, click(613, 3400, 0.9), 0.038)
    out = place(out, click(614, 4700, 0.6), 0.046)  # latch snaps
    out = place(out, thump(200, 100, 0.05, 0.013, 1.3), 0.038, 0.4)
    for k in range(2):
        out = place(out, click(615 + k, 5400, 0.18), 0.09 + k * 0.03)
    return finish(room(out, 0.22), -2)


def eject():
    """Ejector rod pushed, six empty cases tinkling out and bouncing on the ground."""
    out = silence(1.0)
    out = place(out, scrape(0.05, 1400, 2400, 621, 0.4), 0.0)
    out = place(out, click(622, 3000, 0.5), 0.045)
    r = rng(623)
    for k in range(6):
        at = 0.05 + r.uniform(0, 0.06)
        out = place(out, brass(630 + k, 0.25), at)  # cases rubbing free of the chambers
        land = 0.27 + r.uniform(0, 0.16)
        f = r.uniform(3800, 5400)
        for b in range(3):  # hits the floor, bounces twice
            out = place(out, brass(640 + k * 3 + b, 0.9 * 0.5 ** b, f * r.uniform(0.99, 1.01)), land + b * 0.06 * 0.7 ** b)
            out = place(out, click(660 + k * 3 + b, 6000, 0.3 * 0.5 ** b, 0.02), land + b * 0.06 * 0.7 ** b)
    return finish(room(out, 0.2), -4)


def speedload():
    out = silence(0.45)
    for k, at in enumerate((0.0, 0.004, 0.009, 0.011, 0.016, 0.02)):  # six noses finding the chambers
        out = place(out, scrape(0.03, 2600, 3400, 671 + k, 0.2), at)
        out = place(out, brass(680 + k, 0.12), at + 0.025)
    out = place(out, modal(0.1, [(1650, 0.025, 0.6), (3100, 0.015, 0.4)], 690), 0.05, 0.6)  # rounds seat together
    out = place(out, click(691, 2800, 0.7), 0.05)
    out = place(out, click(692, 4300, 0.6), 0.16)  # knob twist releases
    out = place(out, modal(0.06, [(6100, 0.012, 0.3)], 693), 0.161, 0.3)
    out = place(out, scrape(0.09, 2000, 1200, 694, 0.3), 0.22)  # loader pulled away
    return finish(room(out), -3)


def shell_in():
    out = silence(0.3)
    out = place(out, click(701, 3600, 0.5), 0.0)  # loading gate opens under the rim
    out = place(out, scrape(0.07, 1300, 2200, 702, 0.6), 0.006)  # plastic hull sliding in
    out = place(out, filt(noise(0.04, 703), "low", 800) * env_ad(0.04, 0.001, 0.01), 0.075, 0.6)  # thumb push
    out = place(out, click(704, 2900, 0.7), 0.08)  # shell latch
    out = place(out, modal(0.08, [(1180, 0.02, 0.5), (2600, 0.012, 0.3)], 705), 0.082, 0.3)
    return finish(room(out), -4)


def pump_back():
    out = silence(0.24)
    out = place(out, click(711, 3300, 0.55), 0.0)  # action unlocks
    out = place(out, scrape(0.08, 1100, 2600, 712, 0.85), 0.004)
    out = place(out, modal(0.12, [(1120, 0.03, 0.7), (2430, 0.02, 0.5), (3840, 0.012, 0.35)], 713), 0.082, 0.8)
    out = place(out, click(714, 2500, 0.8), 0.082)
    out = place(out, thump(180, 90, 0.07, 0.016, 1.3), 0.082, 0.5)
    return finish(room(out, 0.22), -2)


def pump_fwd():
    out = silence(0.3)
    out = place(out, scrape(0.065, 2600, 1400, 721, 0.75), 0.0)
    out = place(out, modal(0.2, [(950, 0.05, 0.7), (2110, 0.035, 0.6), (3520, 0.02, 0.45), (5410, 0.012, 0.3)], 722), 0.066, 1.0)
    out = place(out, click(723, 3700, 0.9), 0.066)
    out = place(out, thump(200, 85, 0.08, 0.02, 1.3), 0.066, 0.55)
    return finish(room(out, 0.22), -2)


def bolt_up():
    out = silence(0.15)
    out = place(out, scrape(0.04, 3000, 4200, 731, 0.4), 0.0)  # cocking cam
    out = place(out, click(732, 3100, 0.8), 0.035)
    out = place(out, modal(0.07, [(2600, 0.014, 0.4), (6300, 0.008, 0.25)], 733), 0.036, 0.35)
    return finish(room(out), -5)


def bolt_back():
    out = silence(0.34)
    out = place(out, scrape(0.12, 1300, 3400, 741, 0.8), 0.0)
    out = place(out, click(742, 2700, 0.8), 0.118)  # bolt stop
    out = place(out, modal(0.1, [(1500, 0.022, 0.5), (3300, 0.012, 0.35)], 743), 0.12, 0.4)
    out = place(out, brass(744, 0.3, 4600), 0.13)  # case flicks out
    out = place(out, brass(745, 0.18, 4600), 0.27)  # and lands
    return finish(room(out), -3)


def bolt_fwd():
    out = silence(0.24)
    out = place(out, scrape(0.1, 3200, 1500, 751, 0.75), 0.0)
    out = place(out, click(752, 3800, 0.35), 0.035)  # strips a round off the mag
    out = place(out, filt(noise(0.04, 753), "low", 1200) * env_ad(0.04, 0.001, 0.01), 0.1, 0.6)  # chambers
    out = place(out, modal(0.1, [(1250, 0.025, 0.5), (2700, 0.014, 0.35)], 754), 0.1, 0.45)
    return finish(room(out), -3)


def bolt_down():
    out = silence(0.2)
    out = place(out, click(761, 2400, 0.9), 0.0)
    out = place(out, modal(0.14, [(1080, 0.035, 0.7), (2390, 0.022, 0.5), (4170, 0.012, 0.35)], 762), 0.001, 0.8)
    out = place(out, thump(190, 90, 0.07, 0.016, 1.3), 0.0, 0.5)
    return finish(room(out, 0.22), -2)


def round_in():
    out = silence(0.15)
    out = place(out, scrape(0.04, 2200, 3200, 771, 0.45), 0.0)
    out = place(out, click(772, 3800, 0.7), 0.04)
    out = place(out, brass(773, 0.25, 5000), 0.041)
    return finish(room(out), -6)


def hatch_open():
    """A wet flesh flap peeling open: sticky stick-slip tearing, a rising squelch, the suction pop, a breath out."""
    t = 0.6
    out = silence(t)
    sticky = fadeout(crackle(0.4, 781, 900, 400, 2600, None, 0.0006) * env_ad(0.4, 0.15, 0.12), 0.08)
    out = place(out, sticky, 0.0, 1.0)
    out = place(out, fadeout(squelch(0.38, 600, 1400, 782, 6.0, 0.15, 0.08), 0.06), 0.0, 1.4)
    out = place(out, thump(140, 70, 0.08, 0.02, 1.2), 0.34, 0.5)  # suction lets go
    out = place(out, filt(noise(0.05, 783), "low", 1500) * env_ad(0.05, 0.001, 0.012), 0.34, 0.6)
    out = place(out, filt(noise(0.25, 784), "band", (500, 2400)) * env_ad(0.25, 0.04, 0.06), 0.36, 0.15)  # exhale
    out = place(out, spatter(t, 785, 4, 0.36, 0.5, 900, 3500, 0.25), 0.0)
    return finish(room(out, 0.2), -3)


def bio_in():
    out = silence(0.55)
    out = place(out, squelch(0.28, 1200, 300, 791, 5.0, 0.01, 0.07), 0.0, 1.8)
    out = place(out, thump(90, 45, 0.1, 0.03, 1.4), 0.02, 0.7)
    out = place(out, filt(noise(0.08, 792), "low", 900) * env_ad(0.08, 0.002, 0.02), 0.015, 0.7)
    out = place(out, crackle(0.25, 793, 700, 400, 2500, 0.08, 0.0006), 0.02, 0.5)
    out = place(out, bubbles(0.55, 794, 4, 250, 600, 0.1, 0.35, 0.15), 0.0)
    out = place(out, gurgle(0.2, 85, 60, 795, [(400, 320, 4, 1.0), (900, 750, 5, 0.4)], 0.7)
                * env_ad(0.2, 0.03, 0.05), 0.12, 0.35)
    return finish(room(out, 0.2), -3)


def hatch_close():
    out = silence(0.35)
    out = place(out, filt(noise(0.03, 801), "low", 2500) * env_exp(0.03, 0.005, 0.0003), 0.0, 1.0)  # slap
    out = place(out, thump(110, 50, 0.08, 0.016, 1.4), 0.0, 0.5)
    out = place(out, squelch(0.08, 900, 500, 802, 4.0, 0.002, 0.02), 0.0, 1.0)
    out = place(out, spatter(0.35, 803, 6, 0.01, 0.12, 900, 4000, 0.3), 0.0)
    out = place(out, crackle(0.12, 804, 600, 400, 2500, 0.04, 0.0006), 0.03, 0.4)  # seal sticking
    return finish(room(out, 0.2), -2)


def cell_out():
    out = silence(0.45)
    out = place(out, click(811, 4000, 0.7), 0.0)  # latch
    out = place(out, modal(0.1, [(1600, 0.02, 0.5), (3500, 0.012, 0.3)], 812), 0.012, 0.5)  # spring kicks the cell
    out = place(out, thump(210, 110, 0.05, 0.012, 1.2), 0.012, 0.4)
    out = place(out, scrape(0.08, 2600, 1500, 813, 0.45), 0.03)
    d = 0.32
    whine = (osc(sweep(2400, 500, d)) + 0.2 * osc(sweep(120, 100, d), "saw")) * env_ad(d, 0.005, 0.09)
    out = place(out, whine, 0.01, 0.2)  # power falling away
    out = place(out, crackle(0.08, 814, 2500, 3000, 12000, 0.02), 0.012, 0.3)  # contact spark
    return finish(room(out), -4)


def cell_in():
    out = silence(0.6)
    out = place(out, scrape(0.07, 1500, 2600, 821, 0.5), 0.0)
    out = place(out, modal(0.14, [(1240, 0.03, 0.6), (2780, 0.02, 0.5), (4520, 0.012, 0.3)], 822), 0.07, 0.9)
    out = place(out, click(823, 3500, 0.9), 0.07)
    out = place(out, click(824, 4800, 0.5), 0.085)  # latch
    out = place(out, crackle(0.03, 825, 3000, 3000, 12000, 0.008), 0.072, 0.25)
    d = 0.42
    w = osc(sweep(500, 2800, d)) + 0.3 * osc(sweep(1000, 5600, d), "tri")
    w *= np.sin(np.pi * np.linspace(0, 1, secs(d)) ** 0.5) ** 2
    out = place(out, w, 0.09, 0.12)  # power-up whine
    out = place(out, filt(osc(np.full(secs(d), 100.0), "saw"), "low", 600) * env_ad(d, 0.08, 0.12), 0.09, 0.08)  # hum
    return finish(room(out), -3)


def weapon_raise():
    out = silence(0.5)
    out = place(out, rustle(0.28, 831, 600, 4000, 45, 0.6), 0.0)  # sleeve / sling cloth
    out = place(out, filt(noise(0.25, 832, "brown"), "low", 400) * env_ad(0.25, 0.06, 0.06), 0.0, 0.6)
    for k, at in enumerate((0.05, 0.09, 0.12)):  # sling hardware
        out = place(out, modal(0.05, [(5200 + 600 * k, 0.012, 0.4), (7900, 0.007, 0.25)], 833 + k), at, 0.2)
    out = place(out, filt(noise(0.05, 840), "low", 900) * env_ad(0.05, 0.001, 0.012), 0.2, 0.6)  # palm on the grip
    out = place(out, modal(0.12, [(720, 0.03, 0.6), (1510, 0.02, 0.45), (2840, 0.012, 0.3)], 841), 0.2, 0.4)
    out = place(out, click(842, 3800, 0.45), 0.3)  # selector
    return finish(room(out), -6)


# ---------------------------------------------------------------------------- impacts and explosions

def rocket_explode():
    out = silence(2.6)
    out = place(out, filt(np.concatenate([np.linspace(1, -1, secs(0.0015)), [0.0]]), "high", 300), 0.0, 1.2)  # shock
    out = place(out, svf_sweep(noise(1.2, 851) * env_ad(1.2, 0.0008, 0.18), "low", 6000, 90, 0.6), 0.0, 1.6)
    out = place(out, thump(60, 22, 1.0, 0.18, 1.5, 0.003), 0.0, 1.2)
    out = place(out, filt(noise(0.3, 852), "band", (300, 1500)) * env_ad(0.3, 0.001, 0.05), 0.0, 0.9)  # crunch
    debris = rustle(1.8, 853, 2000, 11000, 120, 0.3) * np.exp(-np.linspace(0, 3, secs(1.8)))
    out = place(out, debris, 0.15)
    r = rng(854)
    for k in range(9):  # chunks landing
        f = r.uniform(500, 1800)
        out = place(out, modal(0.1, [(f, 0.02, 0.6), (f * 1.7, 0.012, 0.4)], 855 + k), r.uniform(0.35, 1.5), r.uniform(0.05, 0.15))
    out = place(out, fadeout(filt(noise(2.5, 870, "brown"), "low", 140) * env_ad(2.5, 0.05, 0.55), 0.5), 0.0, 0.6)
    out = saturate(out * 0.9, 1.6)
    ir = impulse_response(3.0, 871, early=((0.06, 0.3), (0.14, 0.25), (0.3, 0.18), (0.55, 0.12), (0.9, 0.08)),
                          decay=0.9, damping=1800, density=0.6)
    ir = lean(ir, 120)
    return finish(reverb(out, ir, 0.4))


def bolt_impact():
    out = silence(0.6)
    out = place(out, click(881, 5200, 0.8), 0.0)
    out = place(out, fm_zap(0.06, 3000, 600, 1.41, 2.5, 0.015, 0.015, 882), 0.0, 0.5)
    out = place(out, svf_sweep(noise(0.06, 883), "band", 7000, 2000, 3) * env_ad(0.06, 0.0005, 0.012), 0.0, 0.6)
    out = place(out, crackle(0.4, 884, 1500, 2500, 12000, 0.1), 0.004, 0.6)  # sizzle
    out = place(out, filt(noise(0.35, 885), "band", (3500, 10000)) * env_ad(0.35, 0.005, 0.08), 0.0, 0.3)
    out = place(out, thump(160, 80, 0.06, 0.014, 1.3), 0.0, 0.5)
    out = place(out, rustle(0.2, 886, 3000, 10000, 14, 0.2), 0.01)  # grit
    return finish(reverb(out, impulse_response(0.6, 887, decay=0.14, damping=4500), 0.22), -2)


def goo_splat():
    out = silence(1.2)
    out = place(out, filt(noise(0.06, 891), "low", 1800) * env_ad(0.06, 0.0008, 0.015), 0.0, 1.0)
    out = place(out, squelch(0.2, 1500, 400, 892, 5.0, 0.003, 0.04), 0.0, 1.8)
    out = place(out, thump(130, 60, 0.08, 0.02, 1.3), 0.0, 0.5)
    out = place(out, spatter(0.3, 893, 14, 0.02, 0.2, 1000, 4000, 0.4), 0.0)
    fz = 1.1
    hiss = crackle(fz, 894, 2500, 2500, 10000) * env_ad(fz, 0.03, 0.26)
    hiss += filt(noise(fz, 895), "band", (3000, 9000)) * env_ad(fz, 0.06, 0.22) * 0.12
    out = place(out, fadeout(hiss, 0.25), 0.03, 0.55)  # acid eating in
    out = place(out, bubbles(1.0, 896, 9, 900, 2200, 0.05, 0.8, 0.1, (0.01, 0.03)), 0.03)
    return finish(reverb(out, impulse_response(0.5, 897, decay=0.1, damping=5000), 0.18), -3)


def brood_burst():
    out = silence(1.0)
    out = place(out, filt(noise(0.03, 901), "low", 2000) * env_ad(0.03, 0.0005, 0.006), 0.0, 1.0)  # pressure pop
    out = place(out, crackle(0.06, 902, 3000, 500, 3000, 0.02, 0.0006), 0.0, 0.8)  # membrane tearing
    out = place(out, squelch(0.35, 900, 250, 903, 4.0, 0.004, 0.08), 0.005, 2.0)  # gush
    out = place(out, filt(noise(0.3, 904), "low", 1200) * env_ad(0.3, 0.002, 0.06), 0.005, 1.0)
    out = place(out, thump(90, 40, 0.15, 0.04, 1.5), 0.0, 0.9)
    out = place(out, spatter(1.0, 905, 30, 0.04, 0.5, 700, 4000, 0.4), 0.0)
    out = place(out, bubbles(1.0, 906, 6, 200, 600, 0.15, 0.7, 0.12, (0.03, 0.07)), 0.0)
    return finish(reverb(out, impulse_response(0.6, 907, decay=0.13, damping=4500), 0.2), -2)


# ---------------------------------------------------------------------------- loot and UI

def loot_drop():
    """A loot core materialising: a rising shimmer, a soft landing, a chime and a beating hum that settles."""
    out = silence(1.3)
    out = place(out, squelch(0.35, 400, 3200, 911, 2.0, 0.3, 0.03), 0.0, 0.5)  # gathering swell
    r = rng(912)
    for k in range(10):
        f = r.uniform(3000, 6500)
        out = place(out, bell(f, 0.12, 0.03), r.uniform(0.05, 0.36), 0.05)
    out = place(out, thump(120, 60, 0.12, 0.03, 1.2), 0.35, 0.5)
    out = place(out, filt(noise(0.05, 913), "low", 900) * env_ad(0.05, 0.001, 0.01), 0.35, 0.4)
    out = place(out, bell(1318.5, 0.8, 0.35), 0.35, 0.35)
    d = 0.9
    hum = (np.sin(2 * np.pi * 440 * np.arange(secs(d)) / SR) + np.sin(2 * np.pi * 441.6 * np.arange(secs(d)) / SR)) * 0.5
    out = place(out, hum * env_ad(d, 0.08, 0.25), 0.36, 0.15)
    return finish(reverb(out, impulse_response(0.9, 914, decay=0.2, damping=7000), 0.25), -5)


CHIMES = [
    [(0.0, 880.0)],
    [(0.0, 880.0), (0.07, 1318.5)],
    [(0.0, 880.0), (0.05, 1108.7), (0.1, 1318.5)],
    [(0.0, 659.3), (0.045, 880.0), (0.09, 1108.7), (0.135, 1318.5), (0.2, 1760.0)],
    [(0.0, 440.0), (0.035, 659.3), (0.07, 830.6), (0.105, 987.8), (0.14, 1108.7), (0.175, 1318.5), (0.24, 1760.0),
     (0.3, 2217.5)],
]


def loot_pickup(k):
    """Picking up loot by rarity: 0 a plain soft chime ... 4 a strummed, chorused, shimmering chord with a bloom."""
    T = [0.55, 0.7, 0.95, 1.5, 2.8][k]
    out = silence(T)
    r = rng(921 + k)
    out = place(out, squelch(0.1, 800, 3000 + 800 * k, 922 + k, 2.0, 0.04, 0.02), 0.0, 0.35)  # drawn in
    tau = [0.16, 0.22, 0.32, 0.5, 0.9][k]
    voices = [1, 1, 2, 3, 3][k]
    for at, f in CHIMES[k]:
        for v in range(voices):
            cents = 0 if voices == 1 else (v - (voices - 1) / 2) * 6
            out = place(out, bell(f * 2 ** (cents / 1200), T - at, tau), at, 0.5 / voices ** 0.5)
    sparkles = [0, 0, 6, 14, 32][k]
    for _ in range(sparkles):
        f = r.uniform(3000, 7000)
        out = place(out, bell(f, 0.15, 0.04), r.uniform(0.05, T * 0.6), 0.06)
    if k >= 3:  # pad bloom under the strike
        x = np.arange(secs(T)) / SR
        chord = (220.0, 330.0, 440.0) if k == 3 else (220.0, 329.6, 415.3, 554.4, 659.3)
        pad = sum(np.sin(2 * np.pi * f * x) + 0.5 * np.sin(2 * np.pi * f * 1.004 * x) for f in chord) / len(chord)
        if k == 4:
            pad *= 1 + 0.3 * np.sin(2 * np.pi * 6.5 * x)  # shimmer
            pad += 0.6 * np.sin(2 * np.pi * 110 * x)  # sub swell
        out = place(out, fadeout(pad * env_ad(T, 0.25 + 0.15 * (k - 3), 0.35 + 0.4 * (k - 3)), 0.4), 0.02, 0.18)
    if k == 4:
        x = np.arange(secs(T)) / SR
        out *= 1 + 0.12 * np.sin(2 * np.pi * 5.0 * x)  # the whole chord shimmers
    ir = impulse_response(1.0 + 0.5 * k, 931 + k, decay=0.15 + 0.12 * k, damping=7000)
    return finish(reverb(out, ir, 0.15 + 0.07 * k), [-8, -7, -6, -5, -4][k])


def ammo_pickup():
    out = silence(0.4)
    out = place(out, rustle(0.12, 941, 800, 5000, 16, 0.4), 0.0)
    out = place(out, filt(noise(0.05, 942), "low", 800) * env_ad(0.05, 0.002, 0.012), 0.01, 0.6)  # box in the hand
    r = rng(943)
    for k in range(5):  # rounds clinking together
        out = place(out, brass(944 + k, r.uniform(0.3, 0.6)), 0.02 + r.uniform(0, 0.11))
    out = place(out, click(950, 3200, 0.5), 0.15)
    return finish(room(out), -6)


def reliquary_open():
    """An ancient mechanism: a deep unlock, grinding, tumblers falling, the seal breaking, then a resonant hum swell."""
    T = 4.4
    out = silence(T)
    out = place(out, modal(0.5, [(182, 0.12, 0.8), (417, 0.08, 0.6), (763, 0.05, 0.4), (1290, 0.03, 0.25)], 961), 0.0, 0.8)
    out = place(out, thump(70, 40, 0.3, 0.07, 1.5), 0.0, 0.9)
    out = place(out, click(962, 1400, 0.6), 0.0)
    d = 0.9
    slip = np.clip(1 + 0.8 * filt(rng(963).standard_normal(secs(d)), "low", 30) * 8, 0, None)  # stick-slip
    grind = svf_sweep(noise(d, 964, "pink") * slip, "band", 300, 600, 2.0) * env_ad(d, 0.1, 0.3, 0.3)
    out = place(out, grind, 0.25, 0.7)
    for k, at in enumerate((0.4, 0.7, 1.0)):  # tumblers
        out = place(out, modal(0.15, [(820 + 90 * k, 0.03, 0.6), (1930 + 150 * k, 0.02, 0.4)], 965 + k), at, 0.5)
        out = place(out, click(970 + k, 2400, 0.4), at)
    out = place(out, modal(0.4, [(240, 0.1, 0.8), (530, 0.07, 0.5), (980, 0.04, 0.3)], 975), 1.2, 0.9)  # release
    out = place(out, thump(85, 38, 0.3, 0.07, 1.5), 1.2, 0.9)
    out = place(out, filt(noise(0.6, 976), "band", (2000, 8000)) * env_ad(0.6, 0.02, 0.15), 1.21, 0.35)  # seal hiss
    d = 3.1
    x = np.arange(secs(d)) / SR
    hum = sum(a * np.sin(2 * np.pi * f * x) for f, a in ((110, 1.0), (110.7, 0.6), (220, 0.5), (330.5, 0.35), (440, 0.2)))
    hum *= 1 + 0.15 * np.sin(2 * np.pi * 0.7 * x)
    out = place(out, fadeout(filt(hum, "low", 1500) * env_ad(d, 1.4, 0.55, 0.3), 0.6), 1.25, 0.2)
    out = place(out, bell(880, 2.0, 0.8), 2.6, 0.12)
    out = place(out, bell(1320, 1.8, 0.7), 2.66, 0.08)
    ir = lean(impulse_response(2.0, 977, early=((0.03, 0.4), (0.07, 0.3), (0.12, 0.2)), decay=0.55, damping=3500), 120)
    return finish(reverb(out, ir, 0.35), -2)


def ui_open():
    out = silence(0.3)
    out = place(out, squelch(0.18, 500, 2500, 981, 2.0, 0.08, 0.03), 0.0, 0.6)
    out = place(out, bell(660, 0.2, 0.05), 0.02, 0.4)
    out = place(out, bell(990, 0.2, 0.06), 0.07, 0.4)
    return finish(reverb(out, impulse_response(0.4, 982, decay=0.06, damping=8000), 0.15), -10)


def ui_close():
    out = silence(0.3)
    out = place(out, squelch(0.16, 2500, 500, 983, 2.0, 0.02, 0.04), 0.0, 0.6)
    out = place(out, bell(990, 0.2, 0.05), 0.0, 0.4)
    out = place(out, bell(660, 0.2, 0.06), 0.05, 0.4)
    return finish(reverb(out, impulse_response(0.4, 984, decay=0.06, damping=8000), 0.15), -10)


def ui_move():
    t = 0.04
    out = tone(2400, 2350, t, 0.004, 0.0003) * 0.6
    out = out + filt(noise(t, 985), "high", 4000) * env_exp(t, 0.0012, 0.0002) * 0.4
    return finish(out, -14, 0.005)


def ui_equip():
    out = silence(0.3)
    out = place(out, click(986, 3000, 0.6), 0.0)
    out = place(out, click(987, 2200, 1.0), 0.045)  # latch home
    out = place(out, modal(0.1, [(1400, 0.02, 0.5), (2900, 0.012, 0.3)], 988), 0.046, 0.5)
    out = place(out, thump(140, 80, 0.06, 0.015, 1.2), 0.045, 0.5)
    out = place(out, bell(1318.5, 0.2, 0.06), 0.06, 0.15)
    return finish(room(out, 0.15), -6)


def ui_lock():
    out = silence(0.3)
    out = place(out, click(989, 3600, 0.7), 0.0)
    out = place(out, modal(0.12, [(2600, 0.03, 0.5), (4100, 0.02, 0.3)], 990), 0.03, 0.6)  # shackle snaps
    out = place(out, click(991, 2800, 0.8), 0.03)
    out = place(out, bell(784, 0.2, 0.05), 0.05, 0.2)
    out = place(out, bell(1175, 0.2, 0.06), 0.09, 0.2)
    return finish(room(out, 0.15), -7)


def ui_dismantle():
    out = silence(0.85)
    r = rng(1990)
    for k in range(5):  # parts wrenched apart
        f = r.uniform(800, 3000)
        at = k * 0.05 + r.uniform(0, 0.02)
        out = place(out, modal(0.12, [(f, 0.025, 0.6), (f * 1.58, 0.016, 0.45), (f * 2.37, 0.01, 0.3)], 1991 + k), at, 0.6)
        out = place(out, click(2000 + k, f * 1.8, 0.5), at)
    out = place(out, scrape(0.25, 800, 4000, 2010, 0.5) + crackle(0.25, 2011, 800, 1500, 8000) * 0.4, 0.0)  # grinding
    out = place(out, thump(90, 45, 0.15, 0.04, 1.5), 0.2, 0.8)
    for k in range(8):  # small bits scattering
        out = place(out, click(2020 + k, r.uniform(3500, 6500), 0.3 * r.uniform(0.4, 1.0), 0.02), 0.3 + r.uniform(0, 0.3))
    out = place(out, tone(1200, 300, 0.35, 0.1, 0.01) * 0.15, 0.22)  # energy bleeding off
    return finish(room(out, 0.2), -5)


def ui_deny():
    out = silence(0.32)
    for at, f, d in ((0.0, 220.0, 0.09), (0.11, 165.0, 0.13)):
        x = np.arange(secs(d)) / SR
        buzz = sum(np.sin(2 * np.pi * f * h * x) / h for h in (1, 3, 5, 7, 9))  # band-limited square
        out = place(out, fadeout(filt(buzz, "low", 1400) * env_ad(d, 0.005, d * 0.5, d * 0.3), d * 0.4), at, 0.5)
    return finish(out, -12)


# ---------------------------------------------------------------------------- weather ambience (loops are seamless)

def seamless(make, total, xfade=1.5):
    """make(seconds) -> signal; returns `total` seconds whose end runs into its start (crossfaded)"""
    x = make(total + xfade)
    n, f = secs(total), secs(xfade)
    y = x[:n].copy()
    r = np.linspace(0, 1, f)
    if y.ndim == 2:
        r = r[:, None]
    y[:f] = x[:f] * r + x[n:n + f] * (1 - r)
    return y


def slow_lfo(t, seed, rate=0.15, lo=0.3, hi=1.0):
    """smoothed random wobble between lo and hi"""
    k = max(4, int(t * rate * 4))
    pts = rng(seed).uniform(lo, hi, k + 2)
    x = np.linspace(0, k, secs(t))
    i = np.floor(x).astype(int)
    f = x - i
    f = f * f * (3 - 2 * f)
    return pts[i] * (1 - f) + pts[i + 1] * f


def amb_wind():
    def make(t):
        chans = []
        for ch in range(2):
            s = 900 + ch * 37
            body = filt(noise(t, s, "brown"), "low", 420) * slow_lfo(t, s + 1, .12, .35, 1.0)
            whistle = sum(filt(noise(t, s + 10 + k, "pink"), "band", (f * .88, f * 1.13)) * slow_lfo(t, s + 20 + k, .2, 0.0, 1.0) ** 2 * g
                          for k, (f, g) in enumerate(((320, .5), (640, .35), (1250, .18))))
            hiss = filt(noise(t, s + 30, "pink"), "high", 2500) * slow_lfo(t, s + 31, .25, .05, .3)
            chans.append(body * 1.0 + whistle + hiss * .25)
        return np.stack(chans, 1)
    return finish(seamless(make, 16.0), -6, fade=0.0005)


def amb_rain():
    def make(t):
        chans = []
        for ch in range(2):
            s = 1200 + ch * 53
            bed = filt(filt(noise(t, s, "pink"), "high", 700), "low", 9000) * .45
            patter = np.zeros(secs(t))
            r = rng(s + 1)
            for at in r.uniform(0, t - .05, int(t * 260)):
                d = filt(noise(.03, int(at * 1000) + s), "band", ((fc := r.uniform(2200, 6500)) * .8, fc * 1.25)) * env_exp(.03, r.uniform(.003, .01))
                patter = place(patter, d, at, r.uniform(.15, .6))
            rumble = filt(noise(t, s + 2, "brown"), "low", 220) * .5
            chans.append(bed + patter * .35 + rumble)
        return np.stack(chans, 1)
    return finish(seamless(make, 12.0), -7, fade=0.0005)


def amb_gust():
    t = 4.0
    x = svf_sweep(noise(t, 1301, "pink"), "band", 280, 900, q=1.2)
    env = env_ad(t, 1.1, 0.9, 0.4)
    return finish(x * env, -8)


def amb_thunder():
    t = 7.5
    crack = filt(noise(.25, 1401), "high", 900) * env_exp(.25, .05)
    roll = filt(noise(t, 1402, "brown"), "low", 140) * env_ad(t, .25, 2.2, .3) * slow_lfo(t, 1403, 1.2, .4, 1.0)
    mid = filt(noise(t, 1404, "pink"), "band", (180, 360)) * env_ad(t, .1, 1.2) * .5
    out = place(roll * 1.4 + mid, crack, .02, .6)
    return finish(reverb(out, impulse_response(1.6, 1405), wet=.35), -3)


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
for _g in KINETIC:
    SOUNDS[_g + "_shot_fp"] = lambda g=_g: kin_shot(g, True)
    SOUNDS[_g + "_shot_world"] = lambda g=_g: kin_shot(g, False)
for _g in ENERGY:
    SOUNDS[_g + "_shot_fp"] = lambda g=_g: nrg_shot(g, True)
    SOUNDS[_g + "_shot_world"] = lambda g=_g: nrg_shot(g, False)
SOUNDS["rocket_shot_fp"] = lambda: rocket_shot(True)
SOUNDS["rocket_shot_world"] = lambda: rocket_shot(False)
for _g in ("spitter", "bile", "brood"):
    SOUNDS[_g + "_shot_fp"] = lambda g=_g: horror_shot(g, True)
    SOUNDS[_g + "_shot_world"] = lambda g=_g: horror_shot(g, False)
SOUNDS.update({
    "mag_clatter": mag_clatter, "mag_tap": mag_tap, "slide_back": slide_back, "slide_fwd": slide_fwd,
    "charge_back": charge_back, "charge_fwd": charge_fwd, "latch": latch, "cyl_open": cyl_open, "cyl_close": cyl_close,
    "eject": eject, "speedload": speedload, "shell_in": shell_in, "pump_back": pump_back, "pump_fwd": pump_fwd,
    "bolt_up": bolt_up, "bolt_back": bolt_back, "bolt_fwd": bolt_fwd, "bolt_down": bolt_down, "round_in": round_in,
    "hatch_open": hatch_open, "bio_in": bio_in, "hatch_close": hatch_close, "cell_out": cell_out, "cell_in": cell_in,
    "weapon_raise": weapon_raise,
    "rocket_explode": rocket_explode, "bolt_impact": bolt_impact, "goo_splat": goo_splat, "brood_burst": brood_burst,
    "loot_drop": loot_drop, "ammo_pickup": ammo_pickup, "reliquary_open": reliquary_open,
    "ui_open": ui_open, "ui_close": ui_close, "ui_move": ui_move, "ui_equip": ui_equip, "ui_lock": ui_lock,
    "ui_dismantle": ui_dismantle, "ui_deny": ui_deny,
})
for _k in range(5):
    SOUNDS[f"loot_pickup_{_k}"] = lambda k=_k: loot_pickup(k)
SOUNDS.update({"amb_wind": amb_wind, "amb_rain": amb_rain, "amb_gust": amb_gust, "amb_thunder": amb_thunder})


# ---------------------------------------------------------------------------- the Altered's voices and the alien base
# Five voice sets (remnant, veilborn, bulwark, stalker, colossus), each: idle_1..4 (mutters and chitters it makes on
# its own: the player hears it before seeing it), query_1..2 (it heard something), alert_1..3 (it saw you), hurt_1..3,
# death_1..2. Built from the creature voice (glottal source through swept formants), wet clicks, throat gurgles,
# ring modulation for the stranger ones.

VOICE_SETS = {
    #            f0 range        formant scale  rough  breath  ring (Hz)  clicks  reverb  seed
    "remnant": dict(f=(170, 430), fs=1.0, rough=0.65, ring=0.0, click=0.6, verb=0.28, seed=4100),
    "veilborn": dict(f=(480, 940), fs=1.35, rough=0.15, ring=37.0, click=0.25, verb=0.42, seed=4200),
    "bulwark": dict(f=(70, 170), fs=0.62, rough=0.9, ring=0.0, click=0.2, verb=0.32, seed=4300),
    "stalker": dict(f=(220, 520), fs=0.95, rough=0.5, ring=0.0, click=0.8, verb=0.28, seed=4400),
    "colossus": dict(f=(48, 120), fs=0.5, rough=0.95, ring=11.0, click=0.15, verb=0.5, seed=4500),
}


def _form(scale, open_=1.0):
    return [(650 * scale * open_, 850 * scale, 4, 1.0), (1250 * scale, 1750 * scale * open_, 6, 0.75),
            (2600 * scale, 3100 * scale, 8, 0.45), (3900 * scale, 4300 * scale, 10, 0.2)]


def _chitter(t, seed, rate, f_lo, f_hi, gain=1.0):
    """wet mandible clicks: short resonant ticks in uneven bursts"""
    r = rng(seed)
    out = silence(t)
    at = r.uniform(0, 0.05)
    while at < t - 0.03:
        f = r.uniform(f_lo, f_hi)
        tick = filt(noise(0.02, int(at * 997) + seed), "band", (f * 0.85, f * 1.2)) * env_exp(0.02, r.uniform(0.002, 0.006))
        out = place(out, tick, at, r.uniform(0.4, 1.0) * gain)
        at += r.exponential(1.0 / rate) if r.random() > 0.25 else r.uniform(0.006, 0.02)
    return out


def _ring(x, f):
    return x if f <= 0 else x * (0.55 + 0.45 * np.sin(2 * np.pi * f * np.arange(len(x)) / SR))


def _finish_voice(x, P, seed, t_verb=1.0, db=-3):
    x = _ring(x, P["ring"])
    x = saturate(x, 1.4 + P["rough"])
    return finish(reverb(x, impulse_response(t_verb * (1.6 if P["fs"] < 0.7 else 1.0), seed, decay=0.3, damping=4200), P["verb"]), db)


def alien_voice(set_name, kind, k):
    P = VOICE_SETS[set_name]
    lo, hi = P["f"]
    s = P["seed"] + {"idle": 0, "query": 100, "alert": 200, "hurt": 300, "death": 400}[kind] + k * 17
    r = rng(s)
    fs = P["fs"]
    if kind == "idle":
        # a mutter: two to four short warbling syllables with chitters between, quiet
        t = r.uniform(1.0, 1.8)
        out = silence(t)
        at = 0.05
        for i in range(r.integers(2, 5)):
            d = r.uniform(0.12, 0.3)
            if at + d > t - 0.05:
                break
            a, b = r.uniform(lo, (lo + hi) / 2), r.uniform(lo, hi * 0.8)
            syl = voice(d, a, b, a * r.uniform(0.8, 1.0), s + i, _form(fs, r.uniform(0.8, 1.2)), rough=P["rough"] * 0.7, peak_at=0.4)
            out = place(out, syl * env_ad(d, 0.02, d * 0.4, d * 0.3), at, r.uniform(0.5, 0.9))
            at += d + r.uniform(0.05, 0.22)
        out = out + _chitter(t, s + 50, 22, 1800 * fs, 4200 * fs, P["click"] * 0.5)
        return _finish_voice(out, P, s, 1.0, -9)
    if kind == "query":
        # a questioning rise, then clicks: it is listening
        t = r.uniform(0.7, 1.0)
        v = voice(t * 0.6, lo * 1.1, hi * 0.9, hi, s, _form(fs, 1.1), rough=P["rough"] * 0.5, peak_at=0.85) * env_ad(t * 0.6, 0.04, 0.18, 0.2)
        out = place(silence(t), v, 0.0)
        out = out + _chitter(t, s + 50, 30, 2200 * fs, 5000 * fs, P["click"]) * np.clip(np.linspace(-1, 2, secs(t)), 0, 1)
        return _finish_voice(out, P, s, 1.0, -6)
    if kind == "alert":
        # a cry to the others: loud, harsh, pitch thrown up and dragged down
        t = r.uniform(0.8, 1.2)
        v = voice(t, lo * 1.3, hi * 1.15, lo * 0.9, s, _form(fs, 1.3), rough=min(1.0, P["rough"] + 0.25), peak_at=0.22)
        v = v * env_ad(t, 0.03, t * 0.35, t * 0.25)
        hiss = filt(noise(t, s + 9), "band", (2500 * fs, 9000)) * env_ad(t, 0.01, 0.15) * 0.3
        return _finish_voice(v + hiss, P, s, 1.3, -2)
    if kind == "hurt":
        t = r.uniform(0.25, 0.4)
        v = voice(t, hi * 0.8, hi, lo * 1.2, s, _form(fs, 0.9), rough=min(1.0, P["rough"] + 0.3), peak_at=0.12)
        return _finish_voice(v * env_ad(t, 0.008, 0.07, 0.05), P, s, 0.8, -3)
    # death: a long falling cry that breaks into a gurgle
    t = r.uniform(1.3, 1.9) * (1.5 if fs < 0.6 else 1.0)
    v = voice(t, hi * 0.9, hi, lo * 0.4, s, _form(fs, 0.8), rough=min(1.0, P["rough"] + 0.2), peak_at=0.12) * env_ad(t, 0.03, t * 0.3, t * 0.15)
    gurgle = silence(t)
    for _ in range(16):
        f = r.uniform(150, 480) * (fs ** 0.5)
        gurgle = place(gurgle, osc(sweep(f, f * 0.6, 0.06)) * env_exp(0.06, 0.015), r.uniform(0.35, t - 0.1), 0.22)
    return _finish_voice(v + gurgle, P, s, 1.4, -2)


def torch(on):
    """the flashlight's switch: a firm plastic click (on) or a softer one (off)"""
    t = 0.12
    f = 3200 if on else 2400
    click = filt(noise(t, 4601 if on else 4602), "band", (f * 0.7, f * 1.5)) * env_exp(t, 0.006)
    body = tone(900 if on else 700, 600, t, 0.01) * 0.3
    return finish(reverb(click + body, impulse_response(0.3, 4603, decay=0.1, damping=6000), 0.08), -8)


def amb_alien_hum():
    """the base's machinery: a low drone with slow beating, a pulsing throb and a high whine that comes and goes"""
    def make(t):
        chans = []
        for ch in range(2):
            s = 4700 + ch * 31
            n = secs(t)
            x = np.arange(n) / SR
            drone = sum(np.sin(2 * np.pi * f * x + ch * 0.7) * g for f, g in ((41.0, 1.0), (41.6 + ch * 0.15, 0.8), (82.3, 0.35), (123.7, 0.18)))
            throb = 0.6 + 0.4 * np.sin(2 * np.pi * 0.5 * x) ** 2
            whine = np.sin(2 * np.pi * (1870 + 12 * np.sin(2 * np.pi * 0.07 * x)) * x) * slow_lfo(t, s + 3, 0.2, 0.0, 1.0) ** 3 * 0.08
            air = filt(noise(t, s + 4, "pink"), "band", (90, 600)) * 0.25 * slow_lfo(t, s + 5, 0.1, 0.4, 1.0)
            chans.append(drone * throb * 0.5 + whine + air)
        return np.stack(chans, 1)
    return finish(seamless(make, 14.0), -9, fade=0.0005)


def amb_alien_chorus():
    """far off voices of the hive: slow eerie swells, overlapping, never quite a word"""
    def make(t):
        r = rng(4800)
        chans = [silence(t), silence(t)]
        at = 0.0
        while at < t:
            d = r.uniform(2.0, 4.5)
            f0 = r.uniform(140, 420)
            v = voice(d, f0, f0 * r.uniform(1.1, 1.5), f0 * r.uniform(0.6, 0.9), int(at * 100) + 4801, _form(r.uniform(0.7, 1.3), 1.0), rough=0.2, peak_at=0.5)
            v = filt(v * env_ad(d, d * 0.35, d * 0.3, d * 0.2), "low", 2400)
            pan = r.uniform(0.2, 0.8)
            chans[0] = place(chans[0], v, at, (1 - pan) * 0.6)
            chans[1] = place(chans[1], v, at, pan * 0.6)
            at += r.uniform(0.8, 2.2)
        ir = impulse_response(3.0, 4802, decay=0.6, damping=2500)
        return np.stack([reverb(c, ir, 0.7) for c in chans], 1)
    return finish(seamless(make, 20.0, xfade=3.0), -12, fade=0.0005)


def amb_hive():
    """close to a growth: wet clicks, creaks and a slow pulse, like something breathing in the walls"""
    def make(t):
        chans = []
        for ch in range(2):
            s = 4900 + ch * 13
            clicks = _chitter(t, s, 6, 900, 3800, 0.6)
            pulse = filt(noise(t, s + 1, "brown"), "low", 160) * (0.5 + 0.5 * np.sin(2 * np.pi * 0.42 * np.arange(secs(t)) / SR) ** 4)
            chans.append(clicks * 0.6 + pulse * 1.2)
        return np.stack(chans, 1)
    return finish(seamless(make, 10.0), -11, fade=0.0005)


for _s in VOICE_SETS:
    for _kind, _n in (("idle", 4), ("query", 2), ("alert", 3), ("hurt", 3), ("death", 2)):
        for _k in range(1, _n + 1):
            SOUNDS[f"{_s}_{_kind}_{_k}"] = (lambda s=_s, kind=_kind, k=_k: alien_voice(s, kind, k))
SOUNDS.update({"torch_on": lambda: torch(True), "torch_off": lambda: torch(False), "amb_alien_hum": amb_alien_hum,
               "amb_alien_chorus": amb_alien_chorus, "amb_hive": amb_hive})


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "unreal", "ShatteredOrbit", "SourceArt", "Audio")
    only = set(sys.argv[2:])  # optional: build just these names
    os.makedirs(out_dir, exist_ok=True)
    for name, fn in SOUNDS.items():
        if only and name not in only:
            continue
        x = fn()
        write(os.path.join(out_dir, name + ".wav"), x)
        ch = 2 if x.ndim == 2 else 1
        rms = 20 * math.log10(max(np.sqrt(np.mean(x ** 2)), 1e-9))
        print(f"[sfx] {name:22s} {len(x) / SR:5.2f} s  {ch}ch  rms {rms:6.1f} dBFS")


if __name__ == "__main__":
    main()
