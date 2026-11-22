"""PACAR Engine Lab: inline-4 explainer Short (1080x1920, 30 fps) with synced synthesized engine sound."""
import math, subprocess, sys, wave, os
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS = 1080, 1920, 30
OUT = os.path.dirname(os.path.abspath(__file__))
MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
INTER = "/usr/share/fonts/opentype/inter/Inter-Black.otf"
def mono(s): return ImageFont.truetype(MONO, s)
def inter(s): return ImageFont.truetype(INTER, s)

NAVY = (14, 18, 38); GRID = (26, 32, 60); LINE = (60, 70, 110)
CREAM = (232, 214, 170); STEEL = (150, 158, 180); DARK = (40, 46, 70)
BLUE = (90, 170, 255); ORANGE = (255, 150, 40); YELLOW = (255, 220, 80)
RED = (255, 70, 70); WHITE = (240, 242, 250); PINK = (255, 90, 180); GREEN = (70, 220, 130)

# ---------------- timeline ----------------
DUR = 33.0
IDLE, REDLINE = 800.0, 6500.0
def segment(t):
    """returns (rpm shown on tach, slow-motion factor, label)"""
    if t < 2.5:  return IDLE, 1.0, "REAL SPEED"
    if t < 4.0:
        k = (t - 2.5) / 1.5
        return IDLE, 1.0 + (60 - 1.0) * k * k, "SLOWING..."
    if t < 16.0: return IDLE, 60.0, "SLOW-MO 1/60"
    if t < 17.0:
        k = (t - 16.0); return IDLE, 60 - 40 * k, "SLOW-MO"
    if t < 21.0: return IDLE, 20.0, "SLOW-MO 1/20"
    if t < 22.0:
        k = t - 21.0; return IDLE, 20 - 19 * k, "SPEEDING UP"
    if t < 25.0: return IDLE, 1.0, "REAL SPEED"
    if t < 30.0:
        k = (t - 25.0) / 5.0
        return IDLE + (REDLINE - IDLE) * (k ** 1.6), 1.0, "REAL SPEED"
    return REDLINE * max(0.0, 1 - (t - 30.0) / 1.5) + IDLE * min(1.0, (t - 30.0) / 1.5), 1.0, "REAL SPEED"

# integrate crank angle (degrees) at audio resolution
SR = 44100
N = int(DUR * SR)
ts = np.arange(N) / SR
rate = np.empty(N)
for i in range(0, N, 441):                 # every 10 ms
    rpm, slow, _ = segment(ts[i])
    rate[i:i + 441] = rpm / 60.0 * 360.0 / slow   # deg per second
ang = np.cumsum(rate) / SR
# shift so cylinder 1 is at the start of intake (phase 0) exactly at t = 4.0
i4 = int(4.0 * SR)
ang = ang - ang[i4]
def crank(t):
    i = min(N - 1, max(0, int(t * SR)))
    return ang[i]

# firing order 1-3-4-2: phase offsets
OFF = {1: 0.0, 3: -180.0, 4: -360.0, 2: -540.0}
def phase(cyl, a): return (a + OFF[cyl]) % 720.0

# ---------------- audio ----------------
def make_audio():
    out = np.zeros(N)
    rng = np.random.default_rng(3)
    # spark events: any cylinder crossing phase 360
    # cylinder fires when (a + off) mod 720 crosses 360  -> global crossings every 180 deg of a
    a0 = ang[0]
    k_start = math.ceil(a0 / 180.0)
    k_end = math.floor(ang[-1] / 180.0)
    idx = np.searchsorted(ang, np.arange(k_start, k_end + 1) * 180.0)
    for j, i in enumerate(idx):
        if i <= 0 or i >= N: continue
        t = ts[i]
        rpm, slow, _ = segment(t)
        slow_mo = slow > 1.5
        L = int((0.55 if slow_mo else 0.05) * SR)
        tt = np.arange(L) / SR
        if slow_mo:
            boom = np.sin(2 * np.pi * (55 + 40 * np.exp(-tt * 9)) * tt) * np.exp(-tt * 6)
            crack = rng.standard_normal(L) * np.exp(-tt * 40) * 0.35
            sig = (boom + crack) * 0.9
        else:
            load = (rpm - IDLE) / (REDLINE - IDLE)
            f1 = 95 + 60 * load
            sig = (np.sin(2 * np.pi * f1 * tt) + 0.6 * np.sin(2 * np.pi * 2.1 * f1 * tt)) * np.exp(-tt * (90 + 120 * load))
            sig += np.convolve(rng.standard_normal(L), np.ones(8) / 8, "same") * np.exp(-tt * 140) * 0.8
            sig *= 0.55 + 0.45 * load
            sig *= 1 + 0.12 * rng.standard_normal()
        j2 = min(N, i + L)
        out[i:j2] += sig[:j2 - i]
    # intake / mechanical hum scaled by rpm in real speed
    hum = np.zeros(N)
    for i in range(0, N, 441):
        rpm, slow, _ = segment(ts[i])
        if slow < 1.5:
            hum[i:i + 441] = (rpm / REDLINE)
    hum = np.convolve(hum, np.ones(2000) / 2000, "same")
    noise = np.convolve(rng.standard_normal(N), np.ones(20) / 20, "same")
    out += noise * hum * 0.25
    # gentle low drone under the slow-mo part
    drone_env = np.clip(1 - np.abs(ts - 10.0) / 7.5, 0, 1)
    out += np.sin(2 * np.pi * 41 * ts) * drone_env * 0.08
    fi, fo = int(0.05 * SR), int(1.0 * SR)
    out[:fi] *= np.linspace(0, 1, fi); out[-fo:] *= np.linspace(1, 0, fo)
    out = np.tanh(out * 1.6)
    out = out / np.max(np.abs(out)) * 0.9
    pcm = (np.stack([out, out], 1) * 32767).astype(np.int16)
    with wave.open(f"{OUT}/engine.wav", "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())

# ---------------- drawing ----------------
CX = [540 + (i - 1.5) * 220 for i in range(4)]   # cylinders 1..4 left to right
BORE = 170
CYL_TOP, CRANK_Y = 720, 1135
R, L_ROD, PIN_TO_TOP, PIST_H = 70, 230, 55, 110

def piston_y(theta):
    th = math.radians(theta)
    pin = CRANK_Y - (R * math.cos(th) + math.sqrt(L_ROD ** 2 - (R * math.sin(th)) ** 2))
    return pin, pin - PIN_TO_TOP

def bg():
    img = Image.new("RGB", (W, H), NAVY)
    d = ImageDraw.Draw(img)
    for x in range(0, W, 60): d.line([(x, 0), (x, H)], fill=GRID)
    for y in range(0, H, 60): d.line([(0, y), (W, y)], fill=GRID)
    return img
BG = bg()

def box_text(d, cx, y, lines, fonts, colors, pad=18, border=CREAM):
    ws = [d.textbbox((0, 0), s, font=f)[2] for s, f in zip(lines, fonts)]
    hs = [d.textbbox((0, 0), s, font=f)[3] for s, f in zip(lines, fonts)]
    bw = max(ws) + 2 * pad; bh = sum(hs) + 12 * (len(lines) - 1) + 2 * pad
    x0 = cx - bw / 2
    d.rectangle([x0, y, x0 + bw, y + bh], fill=(10, 12, 26), outline=border, width=4)
    yy = y + pad
    for s, f, c, w_, h_ in zip(lines, fonts, colors, ws, hs):
        d.text((cx - w_ / 2, yy), s, font=f, fill=c); yy += h_ + 12

def chamber_color(ph):
    if ph < 180:  return BLUE, 0.35 + 0.35 * (ph / 180)        # intake
    if ph < 360:  return (150, 110, 255), 0.5 + 0.4 * ((ph - 180) / 180)  # compression
    if ph < 540:
        k = (ph - 360) / 180
        c = tuple(int(YELLOW[i] * (1 - k) + RED[i] * k) for i in range(3))
        return c, 0.95 - 0.5 * k                                 # power
    return (150, 150, 160), 0.45 * (1 - (ph - 540) / 180) + 0.1  # exhaust

def blend(c, a, base=DARK): return tuple(int(base[i] * (1 - a) + c[i] * a) for i in range(3))

def draw_engine(img, a, focus=None, blur=1):
    d = ImageDraw.Draw(img)
    # block outline
    d.rectangle([90, CYL_TOP - 130, 990, CRANK_Y + 140], fill=(30, 36, 66), outline=CREAM, width=6)
    for k, cyl in enumerate([1, 2, 3, 4]):
        cx = CX[k]
        dim = focus is not None and cyl != focus
        x0, x1 = cx - BORE / 2, cx + BORE / 2
        ph = phase(cyl, a)
        # cylinder liner
        d.rectangle([x0 - 10, CYL_TOP, x1 + 10, CRANK_Y - 120], fill=CREAM if not dim else (120, 112, 95))
        d.rectangle([x0, CYL_TOP, x1, CRANK_Y - 120], fill=DARK)
        # chamber gas above piston
        _, top = piston_y(ph % 360)
        col, al = chamber_color(ph)
        if dim: al *= 0.35
        d.rectangle([x0, CYL_TOP, x1, top], fill=blend(col, al))
        # spark flash
        if 355 <= ph <= 385 and blur == 1:
            fl = Image.new("RGBA", img.size, (0, 0, 0, 0))
            ImageDraw.Draw(fl).ellipse([cx - 70, CYL_TOP - 10, cx + 70, CYL_TOP + 90], fill=(255, 240, 160, 230 if not dim else 90))
            img.paste(fl.filter(ImageFilter.GaussianBlur(18)), (0, 0), fl.filter(ImageFilter.GaussianBlur(18)))
            d = ImageDraw.Draw(img)
        # head: valves + spark plug
        d.rectangle([x0 - 10, CYL_TOP - 110, x1 + 10, CYL_TOP], fill=(60, 66, 100) if not dim else (45, 50, 75))
        li = math.sin(math.radians(ph)) * 22 if ph < 180 else 0
        le = math.sin(math.radians(ph - 540)) * 22 if ph >= 540 else 0
        for vx, lift, vc in ((cx - 45, li, BLUE), (cx + 45, le, (170, 170, 180))):
            vc2 = vc if not dim else blend(vc, 0.4)
            d.line([(vx, CYL_TOP - 100), (vx, CYL_TOP - 8 + lift)], fill=vc2, width=10)
            d.rectangle([vx - 28, CYL_TOP - 14 + lift, vx + 28, CYL_TOP - 2 + lift], fill=vc2)
        d.rectangle([cx - 8, CYL_TOP - 110, cx + 8, CYL_TOP - 4], fill=(230, 230, 230) if not dim else (110, 110, 110))
        # piston(s) with motion blur at high speed
        pin, top = piston_y(ph % 360)
        pc = STEEL if not dim else (85, 90, 110)
        d.rectangle([x0 + 4, top, x1 - 4, top + PIST_H], fill=pc)
        for r_ in range(3):
            d.line([(x0 + 4, top + 14 + r_ * 12), (x1 - 4, top + 14 + r_ * 12)], fill=(100, 106, 128), width=4)
        # rod + crank pin
        th = math.radians(ph % 360)
        crx, cry = cx + R * math.sin(th), CRANK_Y - R * math.cos(th)
        d.line([(cx, pin), (crx, cry)], fill=(120, 126, 150) if not dim else (70, 74, 95), width=26)
        d.ellipse([crx - 22, cry - 22, crx + 22, cry + 22], fill=(170, 176, 196))
        d.ellipse([cx - 52, CRANK_Y - 52, cx + 52, CRANK_Y + 52], outline=(90, 96, 128), width=8)
        # cylinder number
        d.text((cx - 14, CYL_TOP - 175), str(cyl), font=mono(44), fill=YELLOW if (focus in (None, cyl)) else (100, 100, 110))
    d.line([(110, CRANK_Y), (970, CRANK_Y)], fill=(90, 96, 128), width=14)

def firing_strip(d, a, show, active_only=False):
    if not show: return
    y = 1330
    d.rectangle([150, y, 930, y + 120], fill=(10, 12, 26), outline=LINE, width=3)
    d.text((540 - d.textbbox((0, 0), "FIRING ORDER 1 - 3 - 4 - 2", font=mono(34))[2] / 2, y + 12),
           "FIRING ORDER 1 - 3 - 4 - 2", font=mono(34), fill=CREAM)
    for k, cyl in enumerate([1, 3, 4, 2]):
        ph = phase(cyl, a)
        on = 360 <= ph < 540
        x = 260 + k * 160
        d.rectangle([x, y + 60, x + 120, y + 105], fill=ORANGE if on else (30, 34, 60), outline=CREAM, width=2)
        d.text((x + 48, y + 62), str(cyl), font=mono(36), fill=(20, 20, 20) if on else WHITE)

def tach(d, rpm):
    cx, cy, r = 880, 1560, 105
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(10, 12, 26), outline=CREAM, width=5)
    for v in range(0, 8):
        an = math.radians(225 - v * 270 / 7)
        x1, y1 = cx + (r - 8) * math.cos(an), cy - (r - 8) * math.sin(an)
        x2, y2 = cx + (r - 24) * math.cos(an), cy - (r - 24) * math.sin(an)
        d.line([(x1, y1), (x2, y2)], fill=RED if v >= 6 else CREAM, width=4)
    an = math.radians(225 - min(rpm, 7000) / 7000 * 270)
    d.line([(cx, cy), (cx + (r - 20) * math.cos(an), cy - (r - 20) * math.sin(an))], fill=ORANGE, width=6)
    s = f"{int(round(rpm / 10) * 10):,}"
    d.text((cx - d.textbbox((0, 0), s, font=mono(30))[2] / 2, cy + 30), s, font=mono(30), fill=WHITE)
    d.text((cx - 22, cy + 64), "RPM", font=mono(20), fill=CREAM)

STROKES = [("1 INTAKE", "PISTON DOWN, AIR + FUEL IN", BLUE),
           ("2 COMPRESSION", "SQUEEZED ABOUT 10 TIMES", (170, 130, 255)),
           ("3 POWER", "SPARK! IT BURNS + SLAMS THE PISTON DOWN", ORANGE),
           ("4 EXHAUST", "BURNT GAS PUSHED OUT", (200, 200, 210))]

def frame(t):
    img = BG.copy()
    rpm, slow, label = segment(t)
    a = crank(t)
    d = ImageDraw.Draw(img)
    focus = 1 if 4.0 <= t < 16.0 else None
    draw_engine(img, a, focus=focus)
    d = ImageDraw.Draw(img)
    # speed badge + PACAR tag
    d.rectangle([40, 170, 40 + 18 * len(label) + 30, 220], fill=(10, 12, 26), outline=YELLOW if slow > 1.5 else RED, width=3)
    d.text((55, 178), label, font=mono(30), fill=YELLOW if slow > 1.5 else RED)
    d.rectangle([W - 210, 170, W - 40, 220], fill=(0, 87, 168))
    d.text((W - 190, 176), "PACAR", font=mono(34), fill=WHITE)
    # captions
    if t < 2.5:
        box_text(d, 540, 260, ["HOW YOUR CAR", "ENGINE WORKS"], [inter(84), inter(84)], [WHITE, YELLOW])
    elif t < 4.0:
        box_text(d, 540, 290, ["LET'S SLOW IT DOWN...", "...A LOT"], [mono(44), mono(44)], [WHITE, WHITE])
    elif t < 16.0:
        ph = phase(1, a)
        st = STROKES[int(ph // 180) % 4]
        box_text(d, 540, 260, [st[0], st[1]], [mono(64), mono(36)], [st[2], WHITE], border=st[2])
    elif t < 21.0:
        if t < 18.5:
            box_text(d, 540, 280, ["ONE CYCLE = 2 TURNS", "OF THE CRANKSHAFT"], [mono(46), mono(46)], [WHITE, WHITE])
        else:
            box_text(d, 540, 280, ["ONLY 1 STROKE IN 4 PUSHES", "SO THE 4 CYLINDERS TAKE TURNS"], [mono(40), mono(34)], [ORANGE, WHITE])
    elif t < 25.0:
        box_text(d, 540, 280, ["REAL SPEED: IDLE", f"{int(IDLE)} RPM = 27 BANGS A SECOND"], [mono(52), mono(38)], [RED, WHITE])
    elif t < 30.0:
        bangs = int(rpm / 60 * 2)
        box_text(d, 540, 280, ["NOW... FLOOR IT", f"{int(round(rpm/10)*10):,} RPM = {bangs} BANGS/SEC"], [mono(60), mono(40)], [RED, WHITE])
    else:
        box_text(d, 540, 270, ["WHICH ENGINE NEXT?", "V8, BOXER OR DIESEL?", "FOLLOW PACAR"], [mono(52), mono(44), mono(44)], [YELLOW, WHITE, (90, 170, 255)])
    firing_strip(d, a, show=t >= 16.0)
    tach(d, rpm)
    return img

def render_video():
    n = int(DUR * FPS)
    tmp = f"{OUT}/engine4.tmp.mp4"
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                          "-r", str(FPS), "-i", "-", "-i", f"{OUT}/engine.wav", "-map", "0:v", "-map", "1:a",
                          "-c:v", "libx264", "-crf", "18", "-preset", "veryfast", "-pix_fmt", "yuv420p",
                          "-c:a", "aac", "-b:a", "192k", "-shortest", tmp], stdin=subprocess.PIPE)
    for f in range(n):
        p.stdin.write(frame(f / FPS).tobytes())
    p.stdin.close()
    if p.wait() == 0:
        os.replace(tmp, f"{OUT}/pacar_engine4.mp4")

if __name__ == "__main__":
    if sys.argv[1] == "stills":
        for t in [1.0, 3.2, 6.0, 9.0, 12.0, 15.0, 19.5, 23.0, 28.0, 31.5]:
            frame(t).save(f"{OUT}/s_{t}.jpg", quality=80)
    else:
        make_audio()
        render_video()
