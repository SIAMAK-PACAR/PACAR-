import subprocess, wave, json, math, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
from scipy.signal import butter, sosfilt, fftconvolve

D = "/home/claude/blender/pops"
FPS, N, HOLD = 24, 312, 24
W, H = 1080, 1920
DUR = (N + HOLD) / FPS
OUT = f"{D}/2026-11-28-pops-and-bangs.mp4"
FB = "/usr/share/fonts/opentype/inter/Inter-Black.otf"; FX = "/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf"
FM = "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf"
WHITE, RED, GREEN, ORANGE, GREY = (255, 255, 255), (255, 70, 70), (70, 225, 120), (255, 150, 50), (190, 195, 205)
CAPS = [  # start, end, lines, color, size
    (0.0, 2.0, ["Why do tuned cars", "POP & BANG off throttle?"], WHITE, 68),
    (0.0, 2.0, ["Watch inside the engine"], ORANGE, 50),
    (2.0, 4.4, ["Normal ECU: you lift off,", "fuel is CUT. Quiet."], WHITE, 64),
    (4.4, 6.0, ["Pop & bang map:", "fuel keeps flowing..."], WHITE, 64),
    (6.0, 6.65, ["...and the spark", "fires LATE"], WHITE, 66),
    (6.65, 8.6, ["Still burning when the valve", "opens: it ignites in the", "hot exhaust. BANG."], ORANGE, 58),
    (8.6, 10.2, ["MYTH: pops & bangs", "add power"], RED, 64),
    (10.2, 11.7, ["TRUTH: the pops add NO power.", "They only happen off-throttle."], GREEN, 54),
    (11.7, 13.0, ["HIDDEN COST: extra fuel + heat", "can overheat the catalytic", "converter and stress a turbo"], WHITE, 54),
    (13.0, 99, ["Pops or quiet?", "Tell us below"], WHITE, 66),
]
ev = json.load(open(f"{D}/events.json")); proj = json.load(open(f"{D}/proj.json")); BANGS = json.load(open(f"{D}/bangs.json"))

def text_box(img, y, lines, color, size=66, font=FB, alpha=175):
    f = ImageFont.truetype(font, size); d = ImageDraw.Draw(img)
    ws = [d.textbbox((0, 0), s, font=f)[2] for s in lines]
    lh = int(size * 1.18); bw = max(ws) + 70; bh = lh * len(lines) + 40; x0 = (W - bw) // 2
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); ImageDraw.Draw(lay).rounded_rectangle([x0, y, x0 + bw, y + bh], 26, fill=(0, 0, 0, alpha))
    img.alpha_composite(lay); d = ImageDraw.Draw(img)
    for i, s in enumerate(lines): d.text(((W - ws[i]) // 2, y + 20 + i * lh), s, font=f, fill=color)
    return y + bh

def label(img, pt, text, dx, dy, a=1.0, col=WHITE):
    x, y = pt[0] * W, pt[1] * H; d = ImageDraw.Draw(img); f = ImageFont.truetype(FX, 34)
    tx, ty = x + dx, y + dy; tw = d.textbbox((0, 0), text, font=f)[2]
    bx0 = tx if dx > 0 else tx - tw - 30
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); dl = ImageDraw.Draw(lay)
    dl.line([x, y, tx, ty + 24], fill=(255, 255, 255, int(230 * a)), width=4)
    dl.ellipse([x - 9, y - 9, x + 9, y + 9], fill=(255, 150, 50, int(255 * a)), outline=(255, 255, 255, int(255 * a)), width=3)
    dl.rounded_rectangle([bx0, ty, bx0 + tw + 30, ty + 50], 12, fill=(0, 0, 0, int(190 * a)))
    dl.text((bx0 + 15, ty + 5), text, font=f, fill=(*col, int(255 * a)))
    img.alpha_composite(lay)

def glow(img, pt, lv, rad):
    if lv < 0.03: return
    lay = Image.new("RGB", (W // 4, H // 4), (0, 0, 0)); d = ImageDraw.Draw(lay); x, y = pt[0] * W / 4, pt[1] * H / 4
    for k in range(8, 0, -1):
        rk = rad / 4 * k / 8; c = (1 - k / 9) ** 1.6 * lv
        d.ellipse([x - rk, y - rk, x + rk, y + rk], fill=(int(255 * c), int(150 * c), int(50 * c)))
    lay = lay.filter(ImageFilter.GaussianBlur(9)).resize((W, H), Image.BILINEAR)
    img.paste(ImageChops.add(img.convert("RGB"), lay).convert("RGBA"))

def spray(img, pr, s):   # port fuel injector spray toward the intake valve (2D overlay)
    ix, iy = pr["injector"][0] * W, pr["injector"][1] * H; cx, cy = pr["chamber"][0] * W, pr["chamber"][1] * H
    def P(u): return ix + (cx - ix) * u, iy + (cy - iy) * u
    (x0, y0), (x1, y1) = P(0.31), P(0.66)
    nx, ny = -(y1 - y0), (x1 - x0); ln = math.hypot(nx, ny); nx, ny = nx / ln, ny / ln
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    for k in range(5, 0, -1):
        wdt = 4 + 9 * k
        d.polygon([(x0, y0), (x1 + nx * wdt, y1 + ny * wdt), (x1 - nx * wdt, y1 - ny * wdt)], fill=(170, 220, 255, int(115 * s)))
    lay = lay.filter(ImageFilter.GaussianBlur(4)); img.alpha_composite(lay)

def frame(i):
    t = i / FPS; src = min(i, N - 1); e = ev[src]; pr = proj[src]
    img = Image.open(f"{D}/frames/f{src + 1:04d}.jpg").resize((W, H), Image.LANCZOS).convert("RGBA")
    shake = e["bang"] if 6.4 < t < 7.3 else 0.0
    if shake > 0.3:
        dx, dy = int(10 * shake * math.sin(i * 2.7)), int(8 * shake * math.cos(i * 3.1))
        img = img.transform(img.size, Image.AFFINE, (1, 0, dx, 0, 1, dy), resample=Image.BILINEAR)
    if i < 6: img = Image.blend(Image.new("RGBA", (W, H), (0, 0, 0, 255)), img, (i + 1) / 6 * 0.6 + 0.4)
    if e["front"] is not None: glow(img, pr["pipe"], min(1, e["bang"] * 1.1), 520)
    if e["mode"] in ("fire", "pop") and 10 < e["phi"] < 200: spray(img, pr, math.sin(math.pi * (e["phi"] - 10) / 190))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([50, 140, 230, 200], 12, fill=(0, 87, 168, 255))
    d.text((70, 145), "PACAR", font=ImageFont.truetype(FB, 44), fill=WHITE)
    badge = "SLOW MOTION" if 4.5 <= t < 8.6 else ("#TUNING TRUTH" if t < 4.5 else None)
    if badge:
        f = ImageFont.truetype(FX, 30); tw = d.textbbox((0, 0), badge, font=f)[2]
        d.rounded_rectangle([W - tw - 90, 140, W - 50, 200], 12, fill=(255, 150, 50, 235)); d.text((W - tw - 70, 150), badge, font=f, fill=(0, 0, 0))
    if 2.1 <= t < 4.4:
        a = min(1, (t - 2.1) / 0.3, (4.4 - t) / 0.2)
        label(img, pr["plug"], "Spark plug", -170, -230, a)
        label(img, pr["injector"], "Fuel injector", 15, 150, a)
        label(img, pr["exvalve"], "Exhaust valve", 230, 330, a)
        label(img, pr["cat"], "Catalytic converter", -60, 170, a)
    if 11.7 <= t < 13.0:
        label(img, pr["cat"], "Catalytic converter", -60, 170, min(1, (t - 11.7) / 0.3), ORANGE)
    y = 250
    for (a, b, lines, col, size) in CAPS:
        if a <= t < b: y = text_box(img, y, lines, col, size, font=FX if size < 56 and col == ORANGE else FB) + 16
    if 11.7 <= t < 13.0: text_box(img, y, ["Check your local road laws"], GREY, 38, font=FM)
    if t >= 13.0: text_box(img, 1420, ["Follow PACAR for more"], WHITE, 50, font=FX)
    f = ImageFont.truetype(FM, 25)
    note = "Engine sound: synthetic (4-cyl). Pops: sound design. Simplified 3D model"
    tw = d.textbbox((0, 0), note, font=f)[2]; ImageDraw.Draw(img).text(((W - tw) // 2, 1870), note, font=f, fill=(165, 165, 170))
    if True:
        ImageDraw.Draw(img).text((60, 1830), "animation slowed for clarity", font=f, fill=(150, 150, 155))
    return img.convert("RGB")

# ---------------- sound ----------------
SR = 48000
def rpm_at(t):
    if t < 2.0: return 3000 + 2200 * (t / 2.0) ** 1.2
    if t < 4.4: return 3800 + 1400 * math.exp(-(t - 2.0) * 1.6)
    if t < 8.6: return 3700
    if t < 12.4: return 3700 - 1100 * (t - 8.6) / 3.8
    return 900 + 1700 * math.exp(-(t - 12.4) * 3)
def audio():
    n = int(DUR * SR); t = np.arange(n) / SR; rng = np.random.default_rng(11)
    rpm = np.repeat(np.array([rpm_at(x) for x in t[::48]]), 48)[:n]
    ang = np.cumsum(rpm / 60 * 360) / SR
    def ir(res, seed, bright=0.5, decay=1.0, ln=0.12):
        r = np.random.default_rng(seed); m = int(ln * SR); tt = np.arange(m) / SR; y = np.zeros(m)
        for k, f in enumerate(res): y += np.sin(2 * np.pi * f * tt + r.uniform(0, 6)) * np.exp(-tt * (30 + 22 * k) / decay) * 0.88 ** k
        y += r.standard_normal(m) * np.exp(-tt * 260) * 0.3 * bright
        return y / np.abs(y).max()
    IR = ir([95, 190, 380, 760], 3)
    slow = (t >= 4.4) & (t < 8.6)
    pulses = np.zeros(n)
    for k in range(int(ang[-1] // 180) + 1):          # inline-4: one firing every 180 crank deg
        i = np.searchsorted(ang, k * 180.0)
        if i >= n: break
        tt = t[i]
        if slow[i]: continue
        amp = 1.0 if tt < 2.0 else 0.13                    # on throttle vs. overrun (fuel cut / burble)
        pulses[i] += amp * (1 + rng.normal(0, 0.08))
    eng = fftconvolve(pulses, IR)[:n] * 0.9
    eng *= np.clip(np.minimum((4.4 - t) / 0.08, 1), 0, 1) + np.clip((t - 8.55) / 0.2, 0, 1)
    intake = sosfilt(butter(2, [300, 2600], "band", fs=SR, output="sos"), rng.standard_normal(n)) * np.where(t < 2.0, 0.09, 0.025) * ~slow
    # slow motion: low bed + spark tick + one big bang with a long tail
    bed = sosfilt(butter(2, [35, 150], "band", fs=SR, output="sos"), rng.standard_normal(n)) * 0.4 * np.clip(np.minimum((t - 4.35) / 0.3, (8.65 - t) / 0.2), 0, 1)
    tick = np.zeros(n); i6 = int(6.0 * SR); L = int(0.03 * SR); tick[i6:i6 + L] = rng.standard_normal(L) * np.exp(-np.arange(L) / SR * 200) * 0.2
    tick = sosfilt(butter(2, 3000, "high", fs=SR, output="sos"), tick)
    def pop(amp, dec, lowf, seed, big=False):
        r = np.random.default_rng(seed); m = int((1.4 if big else 0.18) * SR); tt = np.arange(m) / SR
        nz = sosfilt(butter(2, [120, 3200 if not big else 1800], "band", fs=SR, output="sos"), r.standard_normal(m))
        y = nz * np.exp(-tt / dec) * np.minimum(1, tt / 0.0012)
        y += np.sin(2 * np.pi * (lowf + 60 * np.exp(-tt * 40)) * tt) * np.exp(-tt / (dec * 2.2)) * 1.4
        if big: y += sosfilt(butter(2, 900, "low", fs=SR, output="sos"), r.standard_normal(m)) * np.exp(-tt / 0.45) * 0.35
        return np.tanh(y * 2.2) * amp
    pops = np.zeros(n)
    def add(tc, y):
        i = int(tc * SR); m = min(len(y), n - i)
        if m > 0: pops[i:i + m] += y[:m]
    big_t = BANGS[0]; add(big_t - 0.02, pop(1.0, 0.11, 48, 1, big=True))
    for j, b in enumerate(BANGS[1:]): add(b, pop(0.85, 0.035, 70, 10 + j))
    for j, tc in enumerate(np.sort(rng.uniform(8.75, 12.7, 26))):     # extra small crackles between the big pops
        add(tc, pop(rng.uniform(0.2, 0.5), rng.uniform(0.012, 0.025), 90, 100 + j))
    out = eng + intake + bed + tick + pops * 0.9
    out = np.tanh(out / (np.abs(out).max() + 1e-9) * 1.6)
    fi = int(0.01 * SR); out[:fi] *= np.linspace(0, 1, fi); fo = int(0.6 * SR); out[-fo:] *= np.linspace(1, 0, fo)
    out = out / np.abs(out).max() * 0.85
    st = np.stack([out, out], 1)
    with wave.open(f"{D}/pops.wav", "wb") as wv:
        wv.setnchannels(2); wv.setsampwidth(2); wv.setframerate(SR); wv.writeframes((st * 32767).astype(np.int16).tobytes())

if __name__ == "__main__":
    if "preview" in sys.argv:
        for s in [float(x) for x in sys.argv[2:]]: frame(int(s * FPS)).resize((540, 960)).save(f"{D}/prev_{s}.jpg")
        sys.exit()
    audio()
    p = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                          "-i", f"{D}/pops.wav", "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-crf", "19",
                          "-preset", "veryfast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", OUT], stdin=subprocess.PIPE)
    for i in range(N + HOLD): p.stdin.write(frame(i).tobytes())
    p.stdin.close(); p.wait()
