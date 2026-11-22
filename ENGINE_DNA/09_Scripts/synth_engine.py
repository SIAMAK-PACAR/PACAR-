#!/usr/bin/env python3
"""ENGINE DNA procedural engine-sound generator (CUSTOM / SYNTHETIC, original, free).

Physics it respects: number of cylinders, firing order, firing intervals in crank degrees,
which bank each cylinder exhausts into, RPM over time, throttle load.
It does NOT reproduce any real vehicle; every output is labelled CUSTOM / SYNTHETIC.

  python3 synth_engine.py --config V8_CROSSPLANE --profile rev --out v8_rev.wav [--seed 1] [--json params.json]
Profiles: idle, rev, high, accel, startup
"""
import argparse, json, math, wave
import numpy as np
from scipy.signal import fftconvolve, butter, sosfilt

SR = 48000

# firing order + bank of each cylinder (L/R). Intervals follow from firing order and 720 / n.
ENGINES = {
    "INLINE_4":       dict(order=[1, 3, 4, 2], banks={c: "L" for c in range(1, 5)}, res=[90, 180, 330, 700], bright=0.6, idle=800, red=6800),
    "INLINE_6":       dict(order=[1, 5, 3, 6, 2, 4], banks={c: "L" for c in range(1, 7)}, res=[110, 230, 420, 880], bright=0.9, idle=700, red=7200),
    # cross-plane V8 (e.g. firing order 1-8-7-2-6-5-4-3, odd cylinders left bank): uneven pulses per bank -> "rumble"
    "V8_CROSSPLANE":  dict(order=[1, 8, 7, 2, 6, 5, 4, 3], banks={c: ("L" if c % 2 else "R") for c in range(1, 9)},
                           res=[65, 130, 240, 480], bright=0.5, idle=650, red=6800),
    # flat-plane V8: banks alternate evenly -> sharper, higher-pitched note
    "V8_FLATPLANE":   dict(order=[1, 5, 3, 7, 4, 8, 2, 6], banks={c: ("L" if c <= 4 else "R") for c in range(1, 9)},
                           res=[95, 200, 380, 760], bright=0.95, idle=900, red=9000),
    # even-firing V10 (72 deg): banks alternate
    "V10":            dict(order=[1, 6, 5, 10, 2, 7, 3, 8, 4, 9], banks={c: ("L" if c <= 5 else "R") for c in range(1, 11)},
                           res=[100, 210, 410, 820], bright=1.0, idle=850, red=8700),
    # 60-degree V12 (60 deg even firing): banks alternate
    "V12":            dict(order=[1, 7, 5, 11, 3, 9, 6, 12, 2, 8, 4, 10], banks={c: ("L" if c <= 6 else "R") for c in range(1, 13)},
                           res=[120, 250, 480, 950], bright=1.1, idle=800, red=9000),
    "BOXER_4":        dict(order=[1, 3, 2, 4], banks={1: "L", 2: "R", 3: "L", 4: "R"}, res=[75, 150, 300, 600], bright=0.5, idle=750, red=7000),
}

def rpm_profile(kind, eng, dur):
    t = np.arange(int(dur * SR)) / SR
    idle, red = eng["idle"], eng["red"]
    if kind == "idle":
        rpm = idle + 25 * np.sin(2 * np.pi * 0.7 * t) + 10 * np.sin(2 * np.pi * 2.3 * t); load = np.full_like(t, 0.15)
    elif kind == "high":
        rpm = 0.85 * red + 0.05 * red * np.sin(2 * np.pi * 0.25 * t); load = np.full_like(t, 0.9)
    elif kind == "accel":
        k = np.clip(t / (dur * 0.9), 0, 1); rpm = idle * 1.5 + (red * 0.95 - idle * 1.5) * k ** 1.3; load = np.full_like(t, 1.0)
    elif kind == "startup":
        rpm = np.where(t < 0.6, 250, idle + (1600 - idle) * np.exp(-(t - 0.6) * 2.0) * (t >= 0.6))
        rpm = np.where((t >= 0.6) & (t < 0.9), 250 + (1600 - 250) * (t - 0.6) / 0.3, rpm)
        load = np.where(t < 0.9, 0.6, 0.2)
    else:  # rev: idle -> blip -> big rev -> idle
        rpm = np.full_like(t, float(idle)); load = np.full_like(t, 0.15)
        def blip(t0, up, top, down):
            m = (t >= t0) & (t < t0 + up); rpm[m] = idle + (top - idle) * ((t[m] - t0) / up) ** 0.8; load[m] = 1.0
            m2 = (t >= t0 + up) & (t < t0 + up + down)
            rpm[m2] = idle + (top - idle) * np.exp(-(t[m2] - t0 - up) * 3.2 / down); load[m2] = 0.05
        blip(0.8, 0.35, 0.55 * red, 1.2); blip(2.6, 0.9, 0.95 * red, 2.2)
    return t, np.maximum(rpm, 150), load

def exhaust_ir(eng, rng, bank):
    n = int(0.08 * SR); t = np.arange(n) / SR
    ir = np.zeros(n)
    for i, f in enumerate(eng["res"]):
        f *= 1 + rng.normal(0, 0.03) + (0.02 if bank == "R" else 0)
        ir += np.sin(2 * np.pi * f * t + rng.uniform(0, 6.28)) * np.exp(-t * (35 + 25 * i)) * (0.9 ** i) * (eng["bright"] if i >= 2 else 1)
    ir += rng.standard_normal(n) * np.exp(-t * 300) * 0.25 * eng["bright"]
    return ir / np.max(np.abs(ir))

def synth(config, profile, dur, seed=1):
    eng = ENGINES[config]; rng = np.random.default_rng(seed)
    t, rpm, load = rpm_profile(profile, eng, dur)
    n = len(eng["order"]); interval = 720.0 / n
    ang = np.cumsum(rpm / 60.0 * 360.0) / SR                      # crank degrees
    out = {"L": np.zeros(len(t)), "R": np.zeros(len(t))}
    k0, k1 = math.ceil(ang[0] / interval), math.floor(ang[-1] / interval)
    idx = np.searchsorted(ang, np.arange(k0, k1 + 1) * interval)
    for j, i in enumerate(idx):
        if i <= 0 or i >= len(t): continue
        cyl = eng["order"][(k0 + j) % n]
        amp = (0.35 + 0.65 * load[i]) * (1 + rng.normal(0, 0.08))
        if load[i] < 0.1 and rng.random() < 0.02 * (rpm[i] / eng["red"]): amp *= 2.5   # rare overrun pop
        out[eng["banks"][cyl]][i] += amp
    chans = {}
    for b in "LR":
        y = fftconvolve(out[b], exhaust_ir(eng, rng, b))[:len(t)]
        chans[b] = y
    # intake / induction noise follows rpm and load
    noise = rng.standard_normal(len(t))
    sos = butter(2, [300, 2500], btype="band", fs=SR, output="sos")
    intake = sosfilt(sos, noise) * (0.03 + 0.10 * load) * (rpm / eng["red"])
    # mechanical whine: harmonic of crank speed
    crank_f = rpm / 60.0; phase = np.cumsum(2 * np.pi * crank_f * 12) / SR
    mech = np.sin(phase) * 0.01 * (rpm / eng["red"])
    L = chans["L"] + 0.35 * chans["R"] + intake + mech
    R = chans["R"] + 0.35 * chans["L"] + intake + mech
    st = np.stack([L, R], 1)
    st = np.tanh(st / (np.max(np.abs(st)) + 1e-9) * 1.8)        # gentle saturation like a real exhaust note
    fade = int(0.03 * SR); st[:fade] *= np.linspace(0, 1, fade)[:, None]; st[-fade:] *= np.linspace(1, 0, fade)[:, None]
    st = st / np.max(np.abs(st)) * 0.79                             # peak about -2 dBFS (headroom for inter-sample peaks)
    return st, dict(generator="synth_engine.py v1", classification="CUSTOM / SYNTHETIC", config=config, profile=profile,
                    duration_s=dur, seed=seed, sample_rate=SR, firing_order=eng["order"],
                    firing_interval_deg=interval, idle_rpm=eng["idle"], redline_rpm=eng["red"],
                    note="Procedural sound based on firing order and intervals; not a recording of any real vehicle.")

def write_wav(path, st):
    pcm = (st * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())

if __name__ == "__main__":
    p = argparse.ArgumentParser(); p.add_argument("--config", required=True, choices=list(ENGINES))
    p.add_argument("--profile", default="rev"); p.add_argument("--dur", type=float, default=6.0)
    p.add_argument("--seed", type=int, default=1); p.add_argument("--out", required=True); p.add_argument("--json")
    a = p.parse_args()
    st, meta = synth(a.config, a.profile, a.dur, a.seed)
    write_wav(a.out, st)
    if a.json: json.dump(meta, open(a.json, "w"), indent=2)
    print("wrote", a.out)
