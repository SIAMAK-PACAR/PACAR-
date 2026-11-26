import subprocess, wave, json, math, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
from scipy.signal import butter, sosfilt, fftconvolve

FPS, N, HOLD = 24, 300, 36
W, H = 1080, 1920
DUR = (N + HOLD) / FPS
OUT = "/home/claude/blender/2026-11-27-gt86-fa20-boxer.mp4"
FB = "/usr/share/fonts/opentype/inter/Inter-Black.otf"; FX = "/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf"
FM = "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf"
WHITE, RED, GREEN, ORANGE, GREY = (255, 255, 255), (255, 70, 70), (70, 225, 120), (255, 150, 50), (190, 195, 205)
CAPS = [  # start, end, lines, color, size
    (0.0, 2.5, ["Why doesn't a GT86", "RUMBLE like a classic WRX?"], WHITE, 70),
    (0.0, 2.5, ["Both are boxer engines"], ORANGE, 54),
    (2.5, 4.4, ["FA20: 2.0 L flat-four", "pistons punch sideways"], WHITE, 64),
    (4.4, 6.5, ["Firing order 1-3-2-4:", "one bang every 180°"], WHITE, 64),
    (6.5, 9.2, ["Peak power at", "7,000 rpm"], WHITE, 66),
    (9.2, 10.9, ["MYTH: the rumble comes", "from the boxer layout"], RED, 60),
    (10.9, 12.7, ["TRUTH: it comes from", "unequal-length headers.", "The 86 has equal-length."], GREEN, 56),
    (12.7, 14.1, ["Rumble or smooth?", "Tell us below"], WHITE, 64),
]
proj = json.load(open("/home/claude/blender/boxer_flash2d.json"))

def text_box(img, y, lines, color, size=66, font=FB, alpha=170):
    f = ImageFont.truetype(font, size); d = ImageDraw.Draw(img)
    ws = [d.textbbox((0, 0), s, font=f)[2] for s in lines]
    lh = int(size * 1.18); bw = max(ws) + 70; bh = lh * len(lines) + 40; x0 = (W - bw) // 2
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); ImageDraw.Draw(lay).rounded_rectangle([x0, y, x0 + bw, y + bh], 26, fill=(0, 0, 0, alpha))
    img.alpha_composite(lay); d = ImageDraw.Draw(img)
    for i, s in enumerate(lines): d.text(((W - ws[i]) // 2, y + 20 + i * lh), s, font=f, fill=color)
    return y + bh

# ---------------- stylised coupe silhouette (generic, no logos) ----------------
def coupe(w=600, h=180):
    S = 4; im = Image.new("L", (w * S, h * S), 0); d = ImageDraw.Draw(im)
    pts = [(0.0, 0.60), (0.01, 0.47), (0.08, 0.41), (0.33, 0.35), (0.45, 0.30), (0.55, 0.12), (0.66, 0.09), (0.78, 0.13),
           (0.88, 0.29), (0.98, 0.31), (1.0, 0.45), (0.99, 0.64), (0.01, 0.64)]
    d.polygon([(x * w * S, y * h * S) for x, y in pts], fill=255)
    WX, WR, WY = (0.19, 0.81), 0.068 * w, 0.64 * h
    for cx in WX:
        rr = WR + 7; d.ellipse([(cx * w - rr) * S, (WY - rr) * S, (cx * w + rr) * S, (WY + rr) * S], fill=0)
    m = im.resize((w, h), Image.LANCZOS)
    col = Image.new("RGBA", (w, h), (215, 220, 230, 255)); col.putalpha(m)
    glass = Image.new("L", (w * S, h * S), 0); dg = ImageDraw.Draw(glass)
    dg.polygon([(x * w * S, y * h * S) for x, y in [(0.46, 0.29), (0.555, 0.14), (0.66, 0.115), (0.77, 0.15), (0.85, 0.28)]], fill=255)
    gl = Image.new("RGBA", (w, h), (40, 70, 110, 255)); gl.putalpha(glass.resize((w, h), Image.LANCZOS))
    col.alpha_composite(gl)
    for cx in WX:
        wl = Image.new("RGBA", (w, h), (0, 0, 0, 0)); dw = ImageDraw.Draw(wl); r = WR
        dw.ellipse([cx * w - r, WY - r, cx * w + r, WY + r], fill=(25, 25, 28, 255), outline=(160, 165, 175, 255), width=4)
        dw.ellipse([cx * w - r * 0.55, WY - r * 0.55, cx * w + r * 0.55, WY + r * 0.55], outline=(160, 165, 175, 255), width=3)
        col.alpha_composite(wl)
    return col
CAR = coupe()

def panel(img):
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    d.rounded_rectangle([40, 1545, W - 40, 1870], 28, fill=(8, 10, 14, 215), outline=(255, 150, 50, 160), width=3)
    img.alpha_composite(lay)
    img.alpha_composite(CAR, ((W - CAR.width) // 2, 1552))
    d = ImageDraw.Draw(img)
    for txt, y, f, col in (("TOYOTA GT86  ·  FA20 2.0 BOXER-4", 1742, ImageFont.truetype(FB, 44), WHITE),
                           ("200 PS · naturally aspirated · 86 x 86 mm", 1797, ImageFont.truetype(FM, 32), GREY)):
        tw = d.textbbox((0, 0), txt, font=f)[2]; d.text(((W - tw) // 2, y), txt, font=f, fill=col)
    f = ImageFont.truetype(FM, 24); txt = "Engine sound: synthetic (flat-4, 1-3-2-4 firing order)"
    tw = d.textbbox((0, 0), txt, font=f)[2]; d.text(((W - tw) // 2, 1880), txt, font=f, fill=(170, 170, 175))

# ---------------- rpm curve for sound + tachometer ----------------
def rpm_at(t):
    if t < 1.0: return 250.0
    if t < 1.3: return 250 + (1600 - 250) * (t - 1.0) / 0.3
    if t < 6.5: return 750 + (1600 - 750) * math.exp(-(t - 1.3) * 2.2)
    if t < 8.3: return 800 + (7000 - 800) * ((t - 6.5) / 1.8) ** 1.25
    if t < 8.6: return 7000
    if t < 9.6: return 1500 + 5500 * math.exp(-(t - 8.6) * 3.5)
    if t < 12.7: return 2500
    return 2500 + (800 - 2500) * min(1, (t - 12.7) / 0.6)

def tach(img, t):
    if not (6.3 <= t < 9.8): return
    a = min(1, (t - 6.3) / 0.2, (9.8 - t) / 0.2)
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    cx, cy, r = W // 2, 1290, 170
    d.ellipse([cx - r - 18, cy - r - 18, cx + r + 18, cy + r + 18], fill=(5, 6, 9, int(200 * a)))
    def ang(rpm): return math.radians(135 + 270 * rpm / 8000)
    d.arc([cx - r, cy - r, cx + r, cy + r], 135, 135 + 270 * 7400 / 8000, fill=(200, 205, 215, int(255 * a)), width=8)
    d.arc([cx - r, cy - r, cx + r, cy + r], 135 + 270 * 7400 / 8000, 405, fill=(255, 60, 60, int(255 * a)), width=8)
    fs = ImageFont.truetype(FX, 26)
    for k in range(0, 9):
        th = ang(k * 1000); x1, y1 = cx + (r - 14) * math.cos(th), cy + (r - 14) * math.sin(th)
        x2, y2 = cx + (r - 34) * math.cos(th), cy + (r - 34) * math.sin(th)
        d.line([x1, y1, x2, y2], fill=(230, 230, 235, int(255 * a)), width=4)
        lx, ly = cx + (r - 58) * math.cos(th), cy + (r - 58) * math.sin(th)
        if 0 < k < 8: d.text((lx - 8, ly - 14), str(k), font=fs, fill=(230, 230, 235, int(255 * a)))
    rpm = rpm_at(t); th = ang(rpm)
    d.line([cx, cy, cx + (r - 20) * math.cos(th), cy + (r - 20) * math.sin(th)], fill=(255, 120, 40, int(255 * a)), width=7)
    d.ellipse([cx - 14, cy - 14, cx + 14, cy + 14], fill=(255, 120, 40, int(255 * a)))
    f = ImageFont.truetype(FB, 40); s = f"{int(round(rpm, -1)):,} rpm"; tw = d.textbbox((0, 0), s, font=f)[2]
    d.text((cx - tw // 2, cy + 62), s, font=f, fill=(255, 255, 255, int(255 * a)))
    f2 = ImageFont.truetype(FM, 22); s2 = "x1000"; d.text((cx - 28, cy - 70), s2, font=f2, fill=(180, 180, 185, int(255 * a)))
    img.alpha_composite(lay)

def glow(img, i):
    src = min(i, N - 1); row = proj[src]
    lay = Image.new("RGBA", (W // 4, H // 4), (0, 0, 0, 0)); d = ImageDraw.Draw(lay); any_ = False
    for c, (u, v, lv) in row.items():
        if lv < 0.03: continue
        any_ = True; x, y = u * W / 4, v * H / 4; rr = 18 + 10 * lv
        for k in range(6, 0, -1):
            rk = rr * k / 6; al = int(255 * lv * (1 - k / 7) ** 1.4)
            d.ellipse([x - rk, y - rk, x + rk, y + rk], fill=(255, 140 + 15 * (6 - k), 60 + 25 * (6 - k), al))
    if not any_: return
    lay = lay.filter(ImageFilter.GaussianBlur(5)).resize((W, H), Image.BILINEAR)
    base = img.convert("RGB"); add = Image.new("RGB", (W, H)); add.paste(lay.convert("RGB"), mask=lay.split()[3])
    img.paste(ImageChops.add(base, add).convert("RGBA"))

def cyl_labels(img, t, i):
    if not (2.6 <= t < 6.5): return
    row = proj[min(i, N - 1)]; d = ImageDraw.Draw(img); f = ImageFont.truetype(FB, 40)
    for c, (u, v, lv) in row.items():
        if lv < 0.25: continue
        x, y = u * W, v * H - 75
        d.ellipse([x - 34, y - 34, x + 34, y + 34], fill=(255, 120, 30, 235), outline=WHITE, width=3)
        tw = d.textbbox((0, 0), c, font=f)[2]; d.text((x - tw / 2, y - 25), c, font=f, fill=WHITE)

def badge(img, t):
    d = ImageDraw.Draw(img); f = ImageFont.truetype(FX, 30)
    s = None
    if 2.6 <= t < 6.5: s = "SLOW MOTION"
    elif 9.6 <= t < 10.9: s = "SOUND: unequal-length (simulated)"
    elif 10.9 <= t < 12.7: s = "SOUND: equal-length, like the 86"
    if s:
        tw = d.textbbox((0, 0), s, font=f)[2]
        d.rounded_rectangle([W - tw - 90, 140, W - 50, 200], 12, fill=(255, 150, 50, 230)); d.text((W - tw - 70, 150), s, font=f, fill=(0, 0, 0))

def frame(i):
    t = i / FPS; src = min(i, N - 1) + 1
    img = Image.open(f"/home/claude/blender/frames/f{src:04d}.jpg").resize((W, H), Image.LANCZOS).convert("RGBA")
    if i < 8: img = Image.blend(Image.new("RGBA", (W, H), (0, 0, 0, 255)), img, (i + 1) / 8 * 0.6 + 0.4)
    glow(img, i)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([50, 140, 230, 200], 12, fill=(0, 87, 168, 255))
    d.text((70, 145), "PACAR", font=ImageFont.truetype(FB, 44), fill=WHITE)
    badge(img, t)
    y = 260
    for (a, b, lines, col, size) in CAPS:
        if a <= t < b: y = text_box(img, y, lines, col, size) + 18
    if t >= 12.7: text_box(img, 1380, ["Follow PACAR for more"], WHITE, 50, font=FX)
    cyl_labels(img, t, i); tach(img, t); panel(img)
    if 6.5 <= t < 9.6:
        f = ImageFont.truetype(FM, 24); ImageDraw.Draw(img).text((60, 1500), "animation slowed for clarity", font=f, fill=(170, 170, 175))
    return img.convert("RGB")

# ---------------- sound ----------------
SR = 48000
def audio():
    n = int(DUR * SR); t = np.arange(n) / SR; rng = np.random.default_rng(7)
    rpm = np.array([rpm_at(x) for x in t[::48]]); rpm = np.repeat(rpm, 48)[:n]
    ang = np.cumsum(rpm / 60 * 360) / SR
    load = np.where((t > 6.5) & (t < 8.6), 1.0, np.where(t < 1.3, 0.6, 0.25))
    def ir(res, seed, bright=0.55, decay=1.0):
        r = np.random.default_rng(seed); m = int(0.12 * SR); tt = np.arange(m) / SR; y = np.zeros(m)
        for k, f in enumerate(res): y += np.sin(2 * np.pi * f * tt + r.uniform(0, 6)) * np.exp(-tt * (30 + 22 * k) / decay) * 0.88 ** k
        y += r.standard_normal(m) * np.exp(-tt * 260) * 0.25 * bright
        return y / np.abs(y).max()
    IR = ir([78, 155, 310, 620], 3)
    # which audio segments use which pulse timing
    eq = np.zeros(n); un = np.zeros(n)
    order = [1, 3, 2, 4]; unequal_delay = {1: 0, 3: 70, 2: 0, 4: 70}   # crank-degree arrival delays (simulated long/short runners)
    k0, k1 = 0, int(ang[-1] // 180)
    for k in range(k0, k1 + 1):
        cyl = order[k % 4]
        i = np.searchsorted(ang, k * 180.0)
        if i >= n: break
        tt = t[i]
        if tt < 1.0 or (2.5 <= tt < 6.5): continue          # cranking / slow-motion handled separately
        amp = (0.35 + 0.65 * load[i]) * (1 + rng.normal(0, 0.07))
        if 9.6 <= tt < 10.9:
            j = np.searchsorted(ang, k * 180.0 + unequal_delay[cyl]);
            if j < n: un[j] += 1.5 * amp * (1.15 if unequal_delay[cyl] else 0.85)
        else: eq[i] += amp
    eng = fftconvolve(eq + un, IR)[:n]
    # cranking: starter whine + slow compression chugs
    crank = (t < 1.05)
    whine = (np.sin(2 * np.pi * 420 * t) * 0.5 + np.sin(2 * np.pi * 840 * t) * 0.25) * 0.08 * crank
    chug = np.zeros(n)
    for tc in np.arange(0.05, 1.0, 1 / 8.3): chug[int(tc * SR)] += 0.5
    chug = fftconvolve(chug, ir([60, 120, 240], 5, 0.2, 1.4))[:n] * 0.5
    # slow motion: low rumble bed + one big thump per visual firing (t = 3, 4, 5, 6 s)
    bed = sosfilt(butter(2, [40, 160], "band", fs=SR, output="sos"), rng.standard_normal(n)) * 0.25
    bedenv = np.clip(np.minimum((t - 2.4) / 0.3, (6.6 - t) / 0.2), 0, 1); bed *= bedenv
    thumps = np.zeros(n)
    for tc in (3.0, 4.0, 5.0, 6.0): thumps[int(tc * SR)] += 1.6
    thumps = fftconvolve(thumps, ir([45, 90, 180, 360], 9, 0.6, 3.0))[:n]
    tail = np.exp(-np.arange(int(0.6 * SR)) / SR * 5)
    thumps = fftconvolve(thumps, np.r_[1, np.zeros(1500), 0.3 * tail[:6000]])[:n] if False else thumps
    intake = sosfilt(butter(2, [300, 2400], "band", fs=SR, output="sos"), rng.standard_normal(n)) * (0.02 + 0.08 * load) * (rpm / 7400)
    intake *= ~((t >= 2.5) & (t < 6.5))
    out = eng * 0.8 + whine + chug + bed + thumps * 0.9 + intake
    # duck the real-speed engine during slow-mo window transitions
    duck = np.ones(n); duck[(t >= 2.45) & (t < 6.55)] = 0.0
    out = (eng * 0.8 * duck) + whine + chug + bed + thumps * 0.9 + intake
    out = np.tanh(out / (np.abs(out).max() + 1e-9) * 1.7)
    fi = int(0.02 * SR); out[:fi] *= np.linspace(0, 1, fi); fo = int(0.7 * SR); out[-fo:] *= np.linspace(1, 0, fo)
    out = out / np.abs(out).max() * 0.8
    st = np.stack([out, out], 1)
    with wave.open("/home/claude/blender/boxer.wav", "wb") as wv:
        wv.setnchannels(2); wv.setsampwidth(2); wv.setframerate(SR); wv.writeframes((st * 32767).astype(np.int16).tobytes())

if __name__ == "__main__":
    if "preview" in sys.argv:
        for s in [float(x) for x in sys.argv[2:]]:
            frame(int(s * FPS)).resize((540, 960)).save(f"/home/claude/blender/prev_{s}.jpg")
        sys.exit()
    audio()
    p = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                          "-i", "/home/claude/blender/boxer.wav", "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-crf", "18",
                          "-preset", "veryfast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", OUT], stdin=subprocess.PIPE)
    for i in range(N + HOLD): p.stdin.write(frame(i).tobytes())
    p.stdin.close(); p.wait()
