import numpy as np, wave
SR = 44100
DUR = 34.0
n = int(SR * DUR)
t = np.arange(n) / SR
out = np.zeros(n)
rng = np.random.default_rng(7)
bpm = 124; beat = 60 / bpm

def add(sig, start):
    i = int(start * SR); j = min(n, i + len(sig))
    if i < n: out[i:j] += sig[:j - i]

def kick():
    tt = np.arange(int(0.35 * SR)) / SR
    f = 50 + 110 * np.exp(-tt * 35)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 9) * 0.9

def hat():
    tt = np.arange(int(0.05 * SR)) / SR
    x = rng.standard_normal(len(tt)); x = np.diff(np.concatenate([[0], x]))
    return x * np.exp(-tt * 90) * 0.12

def bass(freq, length):
    tt = np.arange(int(length * SR)) / SR
    s = np.sign(np.sin(2 * np.pi * freq * tt)) * 0.5 + np.sin(2 * np.pi * freq * tt)
    env = np.minimum(1, tt * 60) * np.exp(-tt * 3)
    return s * env * 0.16

def whoosh(length=0.5):
    m = int(length * SR); x = rng.standard_normal(m)
    k = np.exp(-np.linspace(-2, 2, m) ** 2)
    sm = np.convolve(x, np.ones(30) / 30, mode="same")
    return sm * k * 0.5

def impact():
    tt = np.arange(int(1.2 * SR)) / SR
    boom = np.sin(2 * np.pi * (40 + 60 * np.exp(-tt * 8)) * tt) * np.exp(-tt * 3.5)
    noise = rng.standard_normal(len(tt)) * np.exp(-tt * 14) * 0.4
    return (boom + noise) * 0.9

def ping(freq=1320):
    tt = np.arange(int(0.25 * SR)) / SR
    return np.sin(2 * np.pi * freq * tt) * np.exp(-tt * 18) * 0.18

notes = [55, 55, 65.4, 49]  # A1 A1 C2 G1
b = 0.0; k = 0
while b < DUR - 0.5:
    if not (1.45 < b < 3.2) and not (16.0 < b < 16.6):          # drop out before the hook hit
        add(kick(), b)
        if k % 2 == 1: add(hat(), b)
        add(hat(), b + beat / 2)
        if k % 4 == 0: add(bass(notes[(k // 4) % 4], beat * 4), b)
    b += beat; k += 1

add(impact(), 1.6); add(impact(), 16.5)
for s in [3.2, 7.2, 10.2, 13.2, 16.2, 20.2, 24.4, 27.4, 31.4]:
    add(whoosh(), s - 0.25)
for s in [3.2, 4.4, 5.6, 20.6, 21.4, 22.2, 27.4 + 2.3]:
    add(ping(), s)
# fade out
fo = int(1.2 * SR); out[-fo:] *= np.linspace(1, 0, fo)
out = out / np.max(np.abs(out)) * 0.85
st = np.stack([out, out], 1)
pcm = (st * 32767).astype(np.int16)
with wave.open("music.wav", "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
