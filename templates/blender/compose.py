import subprocess, wave, numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

FPS, N, HOLD = 24, 264, 48
W, H = 1080, 1920
DUR = (N + HOLD) / FPS
FB = "/usr/share/fonts/opentype/inter/Inter-Black.otf"; FX = "/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf"
WHITE, RED, GREEN, ORANGE = (255, 255, 255), (255, 70, 70), (70, 225, 120), (255, 150, 50)
CAPS = [  # start, end, lines, color
    (0.0, 2.3, ["Our brake video", "had a mistake."], WHITE),
    (0.0, 2.3, ["Here's how it REALLY works"], ORANGE),
    (2.3, 4.5, ["The caliper is bolted", "to the car. It NEVER spins."], WHITE),
    (4.5, 6.6, ["Pedal pressed:", "pistons squeeze the pads"], WHITE),
    (6.6, 8.6, ["Friction turns speed", "into HEAT"], ORANGE),
    (8.6, 10.5, ["Wrong: riding the", "brakes down long hills"], RED),
    (10.5, 13.0, ["Right: use a lower gear", "and brake in short bursts"], GREEN),
]

def text_box(img, y, lines, color, size=74, sub=False):
    f = ImageFont.truetype(FX if sub else FB, size)
    d = ImageDraw.Draw(img)
    ws = [d.textbbox((0, 0), s, font=f)[2] for s in lines]
    lh = int(size * 1.18); bw = max(ws) + 70; bh = lh * len(lines) + 40
    x0 = (W - bw) // 2
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); dl = ImageDraw.Draw(lay)
    dl.rounded_rectangle([x0, y, x0 + bw, y + bh], 26, fill=(0, 0, 0, 165))
    img.alpha_composite(lay)
    d = ImageDraw.Draw(img)
    for i, s in enumerate(lines):
        d.text(((W - ws[i]) // 2, y + 20 + i * lh), s, font=f, fill=color)
    return y + bh

def frame(i):
    t = i / FPS
    src = min(i, N - 1) + 1
    img = Image.open(f"/home/claude/blender/frames/f{src:04d}.jpg").resize((W, H), Image.LANCZOS).convert("RGBA")
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([50, 140, 230, 200], 12, fill=(0, 87, 168, 255))
    d.text((70, 145), "PACAR", font=ImageFont.truetype(FB, 44), fill=WHITE)
    y = 260
    for (a, b, lines, col) in CAPS:
        if a <= t < b:
            y = text_box(img, y, lines, col, 66 if col != ORANGE or a > 0 else 58) + 18
    if t >= 12.2:
        text_box(img, 1560, ["Follow PACAR for more"], WHITE, 54, sub=True)
    return img.convert("RGB")

def audio():
    sr = 48000; n = int(DUR * sr); t = np.arange(n) / sr; rng = np.random.default_rng(5)
    clamp, stop = 4.6, 8.4
    w = np.where(t < clamp, 1.0, np.where(t < stop, 1 - (t - clamp) / (stop - clamp), 0.0))
    noise = rng.standard_normal(n)
    from scipy.signal import butter, sosfilt
    whoosh = sosfilt(butter(2, [200, 1800], "band", fs=sr, output="sos"), noise) * (0.15 + 0.35 * w) * w
    whoosh *= 1 + 0.25 * np.sin(2 * np.pi * (0.55 * 20) * t)        # hole pattern passing the pads
    fric_env = np.where((t >= clamp) & (t < stop), np.sin(np.pi * (t - clamp) / (stop - clamp)) ** 0.5, 0)
    friction = sosfilt(butter(2, [1500, 6000], "band", fs=sr, output="sos"), noise) * 0.35 * fric_env
    hum = np.sin(2 * np.pi * 48 * t) * 0.10 + np.sin(2 * np.pi * 72 * t) * 0.05
    out = whoosh + friction + hum
    for tc, amp in ((clamp - 0.05, 0.9), (stop, 0.5)):
        i = int(tc * sr); L = int(0.4 * sr); tt = np.arange(L) / sr
        hit = np.sin(2 * np.pi * (60 + 80 * np.exp(-tt * 20)) * tt) * np.exp(-tt * 9) * amp
        out[i:i + L] += hit[: n - i]
    for tc in (0.0, 2.3, 4.5, 6.6, 8.6, 10.5):                     # soft tick on each caption
        i = int(tc * sr); L = int(0.08 * sr); tt = np.arange(L) / sr
        out[i:i + L] += np.sin(2 * np.pi * 1200 * tt) * np.exp(-tt * 60) * 0.12
    fo = int(0.8 * sr); out[-fo:] *= np.linspace(1, 0, fo)
    out = out / np.max(np.abs(out)) * 0.8
    pcm = (np.stack([out, out], 1) * 32767).astype(np.int16)
    with wave.open("/home/claude/blender/brake.wav", "wb") as wv:
        wv.setnchannels(2); wv.setsampwidth(2); wv.setframerate(sr); wv.writeframes(pcm.tobytes())

audio()
p = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                      "-i", "/home/claude/blender/brake.wav", "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-crf", "17",
                      "-preset", "veryfast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest",
                      "/home/claude/blender/pacar_brake_correct.mp4"], stdin=subprocess.PIPE)
for i in range(N + HOLD):
    p.stdin.write(frame(i).tobytes())
p.stdin.close(); p.wait()
for s in (1.0, 3.0, 5.5, 7.5, 9.5, 12.5):
    frame(int(s * FPS)).resize((270, 480)).save(f"/tmp/c_{s}.jpg")
