import math, os, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS = 1080, 1920, 30
OUT = os.path.dirname(os.path.abspath(__file__))
FD = "/usr/share/fonts/opentype/inter/"
def F(w, s): return ImageFont.truetype(FD + f"Inter-{w}.otf", s)

BG1, BG2 = (9, 12, 18), (18, 24, 36)
BLUE = (30, 120, 255)
RED = (255, 64, 64)
GREEN = (60, 220, 120)
WHITE = (245, 247, 250)
GREY = (150, 160, 175)
ORANGE = (255, 150, 40)

def ease(x): x = max(0, min(1, x)); return 1 - (1 - x) ** 3
def clamp(x): return max(0.0, min(1.0, x))

# ---------- background ----------
def make_bg():
    y = np.linspace(0, 1, H)[:, None]
    x = np.linspace(-1, 1, W)[None, :]
    g = np.clip(1 - (x ** 2 * 0.5 + (y - 0.45) ** 2 * 1.2), 0, 1)
    arr = np.zeros((H, W, 3))
    for i in range(3):
        arr[..., i] = BG1[i] + (BG2[i] - BG1[i]) * g
    img = Image.fromarray(arr.astype(np.uint8))
    d = ImageDraw.Draw(img)
    for gx in range(0, W, 90):
        d.line([(gx, 0), (gx, H)], fill=(24, 31, 44), width=1)
    for gy in range(0, H, 90):
        d.line([(0, gy), (W, gy)], fill=(24, 31, 44), width=1)
    return img
BG = make_bg()

# ---------- spark plug sprite ----------
def cyl_fill(arr, x0, x1, y0, y1, base, hi=0.6, lo=0.35):
    w = x1 - x0
    if w <= 0: return
    xs = np.linspace(0, 1, w)
    shade = lo + (1 - lo) * np.sin(xs * math.pi) ** 0.6
    shade = shade + hi * np.exp(-((xs - 0.3) ** 2) / 0.004)
    for c in range(3):
        arr[y0:y1, x0:x1, c] = np.clip(base[c] * shade[None, :], 0, 255)
    arr[y0:y1, x0:x1, 3] = 255

def plug_sprite(tip_heat=0.0):
    S = 2
    w, h = 260 * S, 980 * S
    a = np.zeros((h, w, 4), dtype=np.float64)
    cx = w // 2
    def seg(y0, y1, half, base, hi=0.5):
        cyl_fill(a, cx - half, cx + half, y0, y1, base, hi)
    seg(0, 40 * S, 22 * S, (170, 170, 175))            # terminal
    seg(40 * S, 70 * S, 34 * S, (150, 150, 155))
    seg(70 * S, 80 * S, 18 * S, (120, 120, 125))
    # ceramic insulator with ribs
    for i, y in enumerate(range(80, 400, 20)):
        half = 46 if i % 2 == 0 else 40
        seg(y * S, (y + 20) * S, half * S, (235, 232, 225), 0.25)
    seg(400 * S, 440 * S, 52 * S, (235, 232, 225), 0.25)
    # hex nut
    seg(440 * S, 560 * S, 92 * S, (185, 190, 198), 0.7)
    for k in (-46, 0, 46):
        a[440 * S:560 * S, cx + k * S - 2:cx + k * S + 2, :3] *= 0.55
    seg(560 * S, 590 * S, 70 * S, (160, 165, 172), 0.5)  # shell
    seg(590 * S, 606 * S, 82 * S, (205, 170, 90), 0.5)   # gasket
    # threads
    seg(606 * S, 860 * S, 62 * S, (150, 155, 162), 0.6)
    for y in range(606, 860, 16):
        for xx in range(-62 * S, 62 * S):
            yy = int((y + (xx / S) * 0.12) * S)
            if 606 * S <= yy < 860 * S - 4:
                a[yy:yy + 5, cx + xx, :3] *= 0.6
    # insulator nose + center electrode
    seg(860 * S, 905 * S, 18 * S, (235, 232, 225), 0.25)
    tip = np.array([200, 200, 205]) * (1 - tip_heat) + np.array([255, 120, 30]) * tip_heat
    seg(905 * S, 935 * S, 6 * S, tuple(tip), 0.4)
    # ground electrode (L)
    a[860 * S:960 * S, cx + 48 * S:cx + 62 * S, :3] = (140, 140, 148)
    a[860 * S:960 * S, cx + 48 * S:cx + 62 * S, 3] = 255
    a[945 * S:960 * S, cx - 14 * S:cx + 62 * S, :3] = (140, 140, 148)
    a[945 * S:960 * S, cx - 14 * S:cx + 62 * S, 3] = 255
    img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGBA")
    return img.resize((w // S, h // S), Image.LANCZOS)

PLUG = plug_sprite(0)
PLUG_HOT = plug_sprite(1)

def paste_plug(img, sprite, cx, cy, scale=1.0, glow=None, glow_a=0.0):
    sp = sprite.resize((int(sprite.width * scale), int(sprite.height * scale)), Image.LANCZOS)
    x, y = int(cx - sp.width / 2), int(cy - sp.height / 2)
    if glow and glow_a > 0:
        g = Image.new("RGBA", (sp.width + 200, sp.height + 200), (0, 0, 0, 0))
        m = sp.split()[3].point(lambda v: int(v * glow_a))
        col = Image.new("RGBA", sp.size, glow + (255,))
        g.paste(col, (100, 100), m)
        g = g.filter(ImageFilter.GaussianBlur(40))
        img.alpha_composite(g, (x - 100, y - 100))
    img.alpha_composite(sp, (x, y))

# ---------- text helpers ----------
def text_c(d, y, s, font, fill, a=1.0, cx=W // 2):
    if a <= 0: return
    fill = tuple(int(c * a + 0 * (1 - a)) for c in fill[:3])
    bb = d.textbbox((0, 0), s, font=font)
    d.text((cx - (bb[2] - bb[0]) / 2, y), s, font=font, fill=fill)

def overlay_text(img, y, s, font, fill, a=1.0, dy=0, cx=W // 2):
    if a <= 0: return
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    bb = d.textbbox((0, 0), s, font=font)
    d.text((cx - (bb[2] - bb[0]) / 2, y + dy), s, font=font, fill=fill + (int(255 * a),))
    img.alpha_composite(lay)

def pop(t, start, dur=0.35):
    p = ease((t - start) / dur)
    return p, (1 - p) * 40

def card(img, x0, y0, x1, y1, a, border=BLUE, fill=(22, 30, 46)):
    if a <= 0: return
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    d.rounded_rectangle([x0, y0, x1, y1], 28, fill=fill + (int(235 * a),), outline=border + (int(255 * a),), width=4)
    img.alpha_composite(lay)

def header(img):
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([60, 120, 104, 164], 10, fill=BLUE)
    d.text((70, 122), "P", font=F("Black", 34), fill=WHITE)
    d.text((118, 124), "PACAR", font=F("ExtraBold", 34), fill=WHITE)

def base():
    img = BG.copy().convert("RGBA")
    header(img)
    return img

def fade_in(img, t, d=0.2):
    if t < d:
        k = t / d
        blk = Image.new("RGBA", img.size, (0, 0, 0, int(255 * (1 - k))))
        img.alpha_composite(blk)

# ---------- scenes ----------
