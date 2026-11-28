import subprocess, wave, json, math, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from scipy.signal import butter, sosfilt, fftconvolve

D = "/home/claude/blender/cai"
FPS, N, HOLD = 24, 300, 36
W, H = 1080, 1920
DUR = (N + HOLD) / FPS
OUT = f"{D}/2026-11-29-cold-air-intake.mp4"
FB = "/usr/share/fonts/opentype/inter/Inter-Black.otf"; FX = "/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf"
FM = "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf"
WHITE, RED, GREEN, ORANGE, BLUE, GREY = (255, 255, 255), (255, 70, 70), (70, 225, 120), (255, 150, 50), (90, 170, 255), (190, 195, 205)
CAPS = [
    (0.0, 2.2, ["Does a cold air intake", "really add power?"], WHITE, 70),
    (0.0, 2.2, ["Watch where the air comes from"], ORANGE, 48),
    (2.2, 4.5, ["An open cone filter next to", "the engine breathes HOT", "engine-bay air"], WHITE, 60),
    (4.5, 6.6, ["Hot air is less dense:", "less oxygen per intake stroke", "= less power at full throttle"], ORANGE, 56),
    (6.6, 8.3, ["MYTH: louder intake", "= more power"], RED, 68),
    (8.3, 10.5, ["TRUTH: power comes from", "COLDER air, not noise.", "Shield it + feed outside air"], GREEN, 56),
    (10.5, 12.3, ["HIDDEN COST: an over-oiled", "filter can coat the MAF sensor", "= check-engine light"], WHITE, 54),
    (12.3, 99, ["Stock airbox or cone?", "Tell us below"], WHITE, 68),
]
ev = json.load(open(f"{D}/events.json")); proj = json.load(open(f"{D}/proj.json"))

def text_box(img, y, lines, color, size=66, font=FB, alpha=175):
    f = ImageFont.truetype(font, size); d = ImageDraw.Draw(img)
    ws = [d.textbbox((0, 0), s, font=f)[2] for s in lines]
    lh = int(size * 1.18); bw = max(ws) + 70; bh = lh * len(lines) + 40; x0 = (W - bw) // 2
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); ImageDraw.Draw(lay).rounded_rectangle([x0, y, x0 + bw, y + bh], 26, fill=(0, 0, 0, alpha))
    img.alpha_composite(lay); d = ImageDraw.Draw(img)
    for i, s in enumerate(lines): d.text(((W - ws[i]) // 2, y + 20 + i * lh), s, font=f, fill=color)
    return y + bh

def label(img, pt, text, dx, dy, a=1.0, col=WHITE, dot=(255, 150, 50)):
    x, y = pt[0] * W, pt[1] * H; f = ImageFont.truetype(FX, 36)
    tx, ty = x + dx, y + dy; tw = ImageDraw.Draw(img).textbbox((0, 0), text, font=f)[2]
    bx0 = tx if dx > 0 else tx - tw - 30
    bx0 = max(30, min(W - tw - 60, bx0))
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); dl = ImageDraw.Draw(lay)
    dl.line([x, y, min(max(tx, bx0), bx0 + tw + 30), ty + 25], fill=(255, 255, 255, int(230 * a)), width=4)
    dl.ellipse([x - 10, y - 10, x + 10, y + 10], fill=(*dot, int(255 * a)), outline=(255, 255, 255, int(255 * a)), width=3)
    dl.rounded_rectangle([bx0, ty, bx0 + tw + 30, ty + 52], 12, fill=(0, 0, 0, int(195 * a)))
    dl.text((bx0 + 15, ty + 5), text, font=f, fill=(*col, int(255 * a)))
    img.alpha_composite(lay)

def chip(img, pt, text, col, a):   # air temperature chip near the filter (no fake numbers)
    if a <= 0: return
    f = ImageFont.truetype(FB, 40); x, y = pt[0] * W, pt[1] * H - 210
    tw = ImageDraw.Draw(img).textbbox((0, 0), text, font=f)[2]
    x0 = max(40, min(W - tw - 80, x - tw / 2 - 20))
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); dl = ImageDraw.Draw(lay)
    dl.rounded_rectangle([x0, y, x0 + tw + 40, y + 64], 32, fill=(*col, int(235 * a)))
    dl.text((x0 + 20, y + 8), text, font=f, fill=(0, 0, 0, int(255 * a)))
    img.alpha_composite(lay)

def frame(i):
    t = i / FPS; src = min(i, N - 1); pr = proj[src]
    img = Image.open(f"{D}/frames/f{src + 1:04d}.jpg").resize((W, H), Image.LANCZOS).convert("RGBA")
    if i < 6: img = Image.blend(Image.new("RGBA", (W, H), (0, 0, 0, 255)), img, (i + 1) / 6 * 0.6 + 0.4)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([50, 140, 230, 200], 12, fill=(0, 87, 168, 255))
    d.text((70, 145), "PACAR", font=ImageFont.truetype(FB, 44), fill=WHITE)
    badge = "SLOW MOTION" if 4.5 <= t < 6.6 else ("#TUNING TRUTH" if t < 4.5 else None)
    if badge:
        f = ImageFont.truetype(FX, 30); tw = d.textbbox((0, 0), badge, font=f)[2]
        d.rounded_rectangle([W - tw - 90, 140, W - 50, 200], 12, fill=(255, 150, 50, 235)); d.text((W - tw - 70, 150), badge, font=f, fill=(0, 0, 0))
    if 2.3 <= t < 4.5:
        a = min(1, (t - 2.3) / 0.3, (4.5 - t) / 0.2)
        label(img, pr["filter"], "Open cone filter", -60, 300, a)
        label(img, pr["manifold"], "Hot exhaust manifold", 60, -330, a)
        label(img, pr["radiator"], "Radiator + fan", 40, 260, a)
    if 1.0 <= t < 8.3: chip(img, pr["filter"], "AIR IN: HOT", ORANGE, min(1, (t - 1.0) / 0.3, (8.3 - t) / 0.2))
    if 9.0 <= t < 10.5:
        a = min(1, (t - 9.0) / 0.3, (10.5 - t) / 0.2)
        chip(img, pr["filter"], "AIR IN: COLD", BLUE, a)
        label(img, pr["duct"], "Outside air", 60, 240, a, BLUE, (90, 170, 255))
    if 10.5 <= t < 12.3:
        label(img, pr["maf"], "MAF sensor", -60, -300, min(1, (t - 10.5) / 0.3), ORANGE)
    y = 250
    for (a, b, lines, col, size) in CAPS:
        if a <= t < b: y = text_box(img, y, lines, col, size, font=FX if size < 50 else FB) + 16
    if 8.3 <= t < 10.5: text_box(img, y, ["On its own, a CAI often adds little"], GREY, 38, font=FM)
    if 6.6 <= t < 8.3: text_box(img, y, ["Check your local road laws"], GREY, 36, font=FM)
    if t >= 12.3: text_box(img, 1400, ["Follow PACAR for more"], WHITE, 50, font=FX)
    f = ImageFont.truetype(FM, 25)
    note = "Engine sound: synthetic (inline-4, 1-3-4-2 firing order). Simplified 3D model"
    tw = d.textbbox((0, 0), note, font=f)[2]; ImageDraw.Draw(img).text(((W - tw) // 2, 1870), note, font=f, fill=(165, 165, 170))
    return img.convert("RGB")

# ---------------- sound: synthetic inline-4 + induction roar + fan + whoosh ----------------
SR = 48000
def rpm_at(t):
    if t < 0.4: return 850
    if t < 1.3: return 850 + 4200 * math.sin(math.pi / 2 * (t - 0.4) / 0.9)      # blip
    if t < 2.4: return 2600 + 2450 * math.exp(-(t - 1.3) * 3)
    if t < 6.6: return 2600
    if t < 7.8: return 2600 + 3600 * ((t - 6.6) / 1.2) ** 1.3                    # hard rev for the "myth"
    if t < 8.6: return 6200 - 3400 * (t - 7.8) / 0.8
    if t < 12.0: return 2800 - 1900 * (t - 8.6) / 3.4
    return 900
def throttle(t):
    return 1.0 if (0.4 <= t < 1.3 or 6.6 <= t < 7.8) else 0.25
def audio():
    n = int(DUR * SR); t = np.arange(n) / SR; rng = np.random.default_rng(5)
    tt = t[::48]; rpm = np.repeat(np.array([rpm_at(x) for x in tt]), 48)[:n]; thr = np.repeat(np.array([throttle(x) for x in tt]), 48)[:n]
    thr = sosfilt(butter(1, 6, "low", fs=SR, output="sos"), thr)
    slow = ((t >= 4.5) & (t < 6.6)).astype(float); slow = sosfilt(butter(1, 4, "low", fs=SR, output="sos"), slow)
    ang = np.cumsum(rpm / 60 * 360) / SR
    def ir(res, seed, ln=0.12):
        r = np.random.default_rng(seed); m = int(ln * SR); k_t = np.arange(m) / SR; y = np.zeros(m)
        for k, f in enumerate(res): y += np.sin(2 * np.pi * f * k_t + r.uniform(0, 6)) * np.exp(-k_t * (30 + 22 * k)) * 0.88 ** k
        y += r.standard_normal(m) * np.exp(-k_t * 260) * 0.3
        return y / np.abs(y).max()
    IR = ir([90, 180, 330, 700], 3)
    pulses = np.zeros(n)
    for k in range(int(ang[-1] // 180) + 1):     # inline-4 (1-3-4-2): one firing every 180 crank degrees
        i = np.searchsorted(ang, k * 180.0)
        if i >= n: break
        pulses[i] += (0.35 + 0.65 * thr[i]) * (1 + rng.normal(0, 0.07))
    eng = fftconvolve(pulses, IR)[:n] * (1 - 0.85 * slow)
    # induction roar: band noise whose centre follows rpm, loud at full throttle (that's what a cone filter makes louder)
    nz = rng.standard_normal(n); roar = np.zeros(n)
    for lo, hi in ((150, 500), (400, 1200), (900, 2600)):
        roar += sosfilt(butter(2, [lo, hi], "band", fs=SR, output="sos"), nz)
    roar *= (0.03 + 0.22 * thr * (rpm / 6000)) * (1 - 0.9 * slow)
    hum = np.sin(2 * np.pi * np.cumsum(rpm / 60 * 2) / SR) * 0.12 * thr      # 2nd order intake hum
    fan = sosfilt(butter(2, [250, 900], "band", fs=SR, output="sos"), rng.standard_normal(n)) * 0.05
    fan += np.sin(2 * np.pi * 7 * 2.2 * t) * 0.0   # placeholder (blade-pass very low, inaudible)
    bed = sosfilt(butter(2, [40, 160], "band", fs=SR, output="sos"), rng.standard_normal(n)) * 0.35 * slow
    air = sosfilt(butter(2, [200, 1400], "band", fs=SR, output="sos"), rng.standard_normal(n)) * 0.18 * slow   # slow airflow whoosh
    # shield + duct snap into place (8.3-9.0): rising whoosh + plastic/metal clunk at 9.0
    wh = np.clip((t - 8.3) / 0.7, 0, 1) * (t < 9.05)
    whoosh = sosfilt(butter(2, [300, 3000], "band", fs=SR, output="sos"), rng.standard_normal(n)) * 0.25 * wh ** 2
    clunk = np.zeros(n); i9 = int(9.0 * SR); m = int(0.25 * SR); kt = np.arange(m) / SR
    clunk[i9:i9 + m] = (np.sin(2 * np.pi * 110 * kt) * 0.9 + np.sin(2 * np.pi * 420 * kt) * 0.4) * np.exp(-kt * 22) + \
        sosfilt(butter(2, [800, 4000], "band", fs=SR, output="sos"), rng.standard_normal(m)) * np.exp(-kt * 60) * 0.5
    out = eng + roar + hum + fan + bed + air + whoosh + clunk * 0.6
    out = np.tanh(out / (np.abs(out).max() + 1e-9) * 1.5)
    fi = int(0.01 * SR); out[:fi] *= np.linspace(0, 1, fi); fo = int(0.8 * SR); out[-fo:] *= np.linspace(1, 0, fo)
    out = out / np.abs(out).max() * 0.85
    st = np.stack([out, out], 1)
    with wave.open(f"{D}/cai.wav", "wb") as wv:
        wv.setnchannels(2); wv.setsampwidth(2); wv.setframerate(SR); wv.writeframes((st * 32767).astype(np.int16).tobytes())

if __name__ == "__main__":
    if "preview" in sys.argv:
        for s in [float(x) for x in sys.argv[2:]]: frame(int(s * FPS)).resize((540, 960)).save(f"{D}/prev_{s}.jpg")
        sys.exit()
    audio()
    p = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                          "-i", f"{D}/cai.wav", "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-crf", "19",
                          "-preset", "veryfast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", OUT], stdin=subprocess.PIPE)
    for i in range(N + HOLD): p.stdin.write(frame(i).tobytes())
    p.stdin.close(); p.wait()
