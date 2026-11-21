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
def s1(t):  # hook 0-3.2
    img = base()
    pa = ease(t / 0.5)
    shake = 0
    if 1.5 < t < 1.9: shake = int(14 * math.sin(t * 90))
    xa = -300 + (380 + 300) * pa + shake
    xb = W + 300 - (W + 300 - 700) * pa + shake
    redglow = clamp((t - 1.5) / 0.3)
    paste_plug(img, PLUG, xa, 1260, 0.82)
    paste_plug(img, PLUG, xb, 1260, 0.82, glow=RED, glow_a=redglow * (0.7 + 0.3 * math.sin(t * 12)))
    d = ImageDraw.Draw(img)
    la, dy = pop(t, 0.05)
    overlay_text(img, 300, "These 2 spark plugs", F("Black", 86), WHITE, la, dy)
    lb, dy2 = pop(t, 0.45)
    overlay_text(img, 405, "look identical.", F("Black", 86), WHITE, lb, dy2)
    lc, dy3 = pop(t, 1.5, 0.25)
    overlay_text(img, 560, "One will destroy", F("Black", 96), RED, lc, dy3)
    overlay_text(img, 675, "your engine.", F("Black", 96), RED, lc, dy3)
    for lbl, x in (("A", xa), ("B", xb)):
        overlay_text(img, 1690, lbl, F("Black", 70), GREY, pa, cx=int(x))
    if 1.5 < t < 1.62:
        img.alpha_composite(Image.new("RGBA", img.size, (255, 40, 40, 70)))
    return img

def cylinder(img, t, cx=W // 2, top=900):
    d = ImageDraw.Draw(img)
    wall = 300
    # cylinder walls
    d.rectangle([cx - wall - 40, top, cx - wall, top + 560], fill=(70, 78, 92))
    d.rectangle([cx + wall, top, cx + wall + 40, top + 560], fill=(70, 78, 92))
    d.rectangle([cx - wall - 40, top - 40, cx + wall + 40, top], fill=(70, 78, 92))
    cyc = (t * 1.1) % 1.0
    py = top + 120 + 220 * (0.5 - 0.5 * math.cos(cyc * 2 * math.pi))
    fire = cyc < 0.08 or cyc > 0.96
    burn = clamp(1 - ((cyc - 0.0) / 0.45)) if cyc < 0.45 else 0
    if burn > 0:
        lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        dl = ImageDraw.Draw(lay)
        dl.rectangle([cx - wall, top, cx + wall, py], fill=(255, 120, 30, int(190 * burn)))
        lay = lay.filter(ImageFilter.GaussianBlur(10))
        img.alpha_composite(lay)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([cx - wall + 6, py, cx + wall - 6, py + 180], 12, fill=(175, 182, 195))
    for k in range(3):
        d.line([(cx - wall + 6, py + 30 + k * 22), (cx + wall - 6, py + 30 + k * 22)], fill=(120, 126, 138), width=6)
    d.line([(cx, py + 120), (cx - 60 * math.sin(cyc * 2 * math.pi), py + 250)], fill=(140, 146, 158), width=36)
    paste_plug(img, PLUG, cx, top - 185, 0.42)
    if fire:
        lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        dl = ImageDraw.Draw(lay)
        dl.ellipse([cx - 60, top + 5, cx + 60, top + 95], fill=(120, 200, 255, 255))
        lay = lay.filter(ImageFilter.GaussianBlur(14))
        img.alpha_composite(lay)
        ImageDraw.Draw(img).ellipse([cx - 14, top + 36, cx + 14, top + 64], fill=(230, 245, 255))

def s2(t):  # what it does 3.2-10
    img = base()
    overlay_text(img, 250, "What it does", F("Black", 80), BLUE, ease(t / 0.3))
    steps = ["Spark", "Fuel ignites", "Piston pushed down", "Your car moves"]
    for i, s in enumerate(steps):
        a, dy = pop(t, 0.4 + i * 0.7)
        txt = s if i == 0 else "→  " + s
        overlay_text(img, 370 + i * 78, txt, F("Bold", 58), WHITE, a, dy)
    cylinder(img, t, top=1090)
    a, dy = pop(t, 3.6)
    card(img, 120, 1650, W - 120, 1760, a)
    overlay_text(img, 1675, "Up to 50 sparks every second", F("ExtraBold", 52), WHITE, a)
    fade_in(img, t)
    return img

def s3(t):  # the mistake 10-17.5
    img = base()
    overlay_text(img, 250, "The mistake", F("Black", 84), RED, ease(t / 0.3))
    heat = clamp((t - 0.5) / 2.0)
    paste_plug(img, PLUG_HOT if heat > 0.5 else PLUG, 230, 1040, 0.72, glow=ORANGE, glow_a=heat * (0.6 + 0.4 * math.sin(t * 9)))
    cards = [
        ("Wrong heat range", "tip overheats → pre-ignition"),
        ("Pre-ignition", "can burn a hole in the piston"),
        ("Wrong thread reach", "plug can hit the piston"),
    ]
    for i, (h, s) in enumerate(cards):
        a, dy = pop(t, 0.6 + i * 1.7)
        y = 470 + i * 300 + dy
        card(img, 420, y, W - 60, y + 250, a, border=RED)
        overlay_text(img, y + 45, h, F("ExtraBold", 50), WHITE, a, cx=(420 + W - 60) // 2)
        overlay_text(img, y + 130, s, F("Medium", 38), (255, 190, 190), a, cx=(420 + W - 60) // 2)
    a, dy = pop(t, 5.8)
    overlay_text(img, 1450, "Misfire  ·  Rough idle  ·  Power loss", F("Bold", 46), ORANGE, a, dy)
    fade_in(img, t)
    return img

def s4(t):  # 4 must match 17.5-22.5
    img = base()
    overlay_text(img, 250, "4 things must match", F("Black", 76), WHITE, ease(t / 0.3))
    overlay_text(img, 345, "YOUR engine", F("Black", 92), BLUE, ease((t - 0.2) / 0.3))
    items = [("1", "Thread size + reach"), ("2", "Heat range"), ("3", "Electrode gap"), ("4", "Tip: copper / platinum / iridium")]
    for i, (n, s) in enumerate(items):
        a, dy = pop(t, 0.7 + i * 0.75)
        y = 540 + i * 230 + dy
        card(img, 80, y, W - 80, y + 190, a)
        lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); dl = ImageDraw.Draw(lay)
        dl.ellipse([120, y + 45, 220, y + 145], fill=BLUE + (int(255 * a),))
        img.alpha_composite(lay)
        overlay_text(img, y + 57, n, F("Black", 60), WHITE, a, cx=170)
        lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); dl = ImageDraw.Draw(lay)
        f = F("Bold", 48 if len(s) < 22 else 40)
        dl.text((260, y + 95), s, font=f, fill=WHITE + (int(255 * a),), anchor="lm")
        img.alpha_composite(lay)
    a, _ = pop(t, 4.0)
    overlay_text(img, 1520, "Check the spec for your exact engine.", F("Medium", 40), GREY, a)
    fade_in(img, t)
    return img

def s5(t):  # upgrade + trap 22.5-26.5
    img = base()
    overlay_text(img, 250, "Upgrade?", F("Black", 90), GREEN, ease(t / 0.3))
    paste_plug(img, PLUG, W // 2, 1260, 0.62, glow=GREEN, glow_a=0.35)
    a, dy = pop(t, 0.4)
    card(img, 80, 400 + dy, W - 80, 560 + dy, a, border=GREEN)
    overlay_text(img, 440, "Iridium tips can last much longer", F("Bold", 46), WHITE, a, dy)
    a, dy = pop(t, 1.6)
    card(img, 80, 600 + dy, W - 80, 820 + dy, a, border=ORANGE)
    overlay_text(img, 635, "Trap: a \"colder\" plug is", F("Bold", 46), ORANGE, a, dy)
    overlay_text(img, 705, "not free power", F("Bold", 46), ORANGE, a, dy)
    a, dy = pop(t, 2.6)
    overlay_text(img, 1640, "Only change heat range on a tuned engine.", F("Medium", 38), GREY, a, dy)
    fade_in(img, t)
    return img

def s6(t):  # PACAR picker 26.5-30.5
    img = base()
    overlay_text(img, 250, "Don't guess.", F("Black", 96), WHITE, ease(t / 0.3))
    overlay_text(img, 370, "Pick your car. See what fits.", F("Bold", 54), BLUE, ease((t - 0.3) / 0.3))
    a = ease((t - 0.5) / 0.4)
    card(img, 140, 520, W - 140, 1480, a, border=(60, 70, 90), fill=(16, 22, 34))
    fields = [("Make", "Volvo"), ("Model", "V60"), ("Engine", "2.0 T5")]
    for i, (k, v) in enumerate(fields):
        fa = ease((t - 0.8 - i * 0.45) / 0.3)
        y = 600 + i * 190
        card(img, 200, y, W - 200, y + 150, fa * a, border=(50, 60, 80), fill=(26, 34, 50))
        lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); dl = ImageDraw.Draw(lay)
        dl.text((240, y + 20), k, font=F("Medium", 32), fill=GREY + (int(255 * fa),))
        dl.text((240, y + 62), v, font=F("Bold", 50), fill=WHITE + (int(255 * fa),))
        img.alpha_composite(lay)
    ra = ease((t - 2.3) / 0.35)
    card(img, 200, 1200, W - 200, 1400, ra, border=GREEN, fill=(18, 44, 30))
    overlay_text(img, 1235, "✓  Fits your engine", F("ExtraBold", 52), GREEN, ra)
    overlay_text(img, 1315, "Spark plug matched", F("Medium", 36), (190, 240, 205), ra)
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); dl = ImageDraw.Draw(lay)
    dl.rounded_rectangle([W - 330, 540, W - 170, 600], 14, fill=ORANGE + (int(255 * a),))
    dl.text((W - 250, 570), "DEMO", font=F("Black", 34), fill=(20, 20, 20, int(255 * a)), anchor="mm")
    img.alpha_composite(lay)
    fade_in(img, t)
    return img

def s7(t):  # CTA 30.5-33
    img = base()
    k = ease(t / 0.4)
    d = ImageDraw.Draw(img)
    s = int(200 * (0.7 + 0.3 * k))
    d.rounded_rectangle([W // 2 - s // 2, 520, W // 2 + s // 2, 520 + s], 40, fill=BLUE)
    overlay_text(img, 520 + s // 2 - 80, "P", F("Black", 150), WHITE, k)
    overlay_text(img, 800, "PACAR", F("Black", 120), WHITE, k)
    a, dy = pop(t, 0.5)
    overlay_text(img, 1000, "Next: turbo, oil or brakes?", F("Bold", 58), WHITE, a, dy)
    a, dy = pop(t, 0.9)
    card(img, 190, 1120 + dy, W - 190, 1250 + dy, a, border=BLUE, fill=BLUE)
    overlay_text(img, 1148, "Comment + Subscribe", F("ExtraBold", 54), WHITE, a, dy)
    fade_in(img, t)
    return img

SCENES = [(s1, 3.2), (s2, 6.8), (s3, 7.5), (s4, 5.0), (s5, 4.0), (s6, 4.0), (s7, 2.5)]

def render_scene(i, fn, dur):
    final = f"{OUT}/scene{i}.mp4"
    tmp = f"{OUT}/scene{i}.tmp.mp4"
    n = int(round(dur * FPS))
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                          "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-crf", "18",
                          "-preset", "veryfast", "-pix_fmt", "yuv420p", tmp], stdin=subprocess.PIPE)
    for f in range(n):
        p.stdin.write(fn(f / FPS).convert("RGB").tobytes())
    p.stdin.close()
    if p.wait() == 0:
        os.replace(tmp, final)

if __name__ == "__main__":
    if sys.argv[1] == "stills":
        for i, (fn, dur), tt in zip(range(7), SCENES, [2.6, 4.2, 6.5, 4.6, 3.5, 3.5, 2.0]):
            fn(tt).convert("RGB").save(f"{OUT}/still{i}.jpg", quality=85)
    else:
        for i in [int(x) for x in sys.argv[1:]]:
            fn, dur = SCENES[i]
            render_scene(i, fn, dur)
