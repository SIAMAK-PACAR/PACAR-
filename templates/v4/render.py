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

# ---------- carbon weave panels ----------
PW, PH = 420, 600
TOW = 30
_yy, _xx = np.mgrid[0:PH, 0:PW]
_ci, _cj = _yy // TOW, _xx // TOW
WARP = ((_cj - _ci) % 4) < 2            # 2x2 twill: warp tow on top
_fy, _fx = (_yy % TOW) / TOW, (_xx % TOW) / TOW
# warp tows run vertically -> profile across x; weft horizontally -> across y
PROF = np.where(WARP, np.sin(_fx * np.pi), np.sin(_fy * np.pi)) ** 0.7
# fine fibre striations along each tow
STRI = np.where(WARP, np.sin(_xx * 2.1), np.sin(_yy * 2.1)) * 0.06
GAP = np.where(WARP, np.minimum(_fy, 1 - _fy), np.minimum(_fx, 1 - _fx)) < 0.04

def panel_real(phase, sweep):
    # light direction rotates -> warp and weft tows swap brightness (3D shimmer)
    a = 0.5 + 0.5 * math.cos(phase)
    b = 0.5 + 0.5 * math.cos(phase + math.pi)
    lum = 0.07 + PROF * np.where(WARP, 0.10 + 0.55 * a, 0.10 + 0.55 * b) + STRI * PROF
    lum = np.where(GAP, 0.03, lum)
    band = np.exp(-((_xx + _yy * 0.6 - sweep) ** 2) / (2 * 55 ** 2)) * 0.45
    lum = lum + band
    return lum

# fake: flat printed pattern — a fixed snapshot, blurred, the sheen moves but tows never change
_FAKE = None
def panel_fake(phase, sweep):
    global _FAKE
    if _FAKE is None:
        base = 0.07 + PROF * np.where(WARP, 0.42, 0.22)
        base = np.where(GAP, 0.05, base)
        img = Image.fromarray((np.clip(base, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.6))
        _FAKE = np.asarray(img).astype(np.float64) / 255 * 0.85
    band = np.exp(-((_xx + _yy * 0.6 - sweep) ** 2) / (2 * 55 ** 2)) * 0.45
    return _FAKE + band

def panel_img(lum, edge=None, tint=(1.0, 1.0, 1.05)):
    rgb = np.stack([np.clip(lum * tint[c], 0, 1) for c in range(3)], -1) * 255
    im = Image.fromarray(rgb.astype(np.uint8)).convert("RGBA")
    if edge == "real":   # layered edge: visible fibre plies
        d = ImageDraw.Draw(im)
        for k in range(6):
            col = (40, 40, 44) if k % 2 == 0 else (95, 95, 102)
            d.rectangle([0, PH - 60 + k * 10, PW, PH - 50 + k * 10], fill=col)
    elif edge == "fake":  # plain plastic edge
        d = ImageDraw.Draw(im)
        d.rectangle([0, PH - 60, PW, PH], fill=(70, 72, 78))
    m = Image.new("L", (PW, PH), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, PW - 1, PH - 1], 26, fill=255)
    im.putalpha(m)
    return im

XA, XB, PY = 60, 600, 930

def panels(img, t, phase=None, sweep=None, edge=False, alpha=1.0, glowA=None, glowB=None, dx=0, swap_speed=1.0):
    if phase is None: phase = t * 2.2 * swap_speed
    if sweep is None: sweep = (t * 420) % 1400 - 250
    for x, fn, side, g in ((XA, panel_real, "real", glowA), (XB, panel_fake, "fake", glowB)):
        im = panel_img(fn(phase, sweep), side if edge else None)
        if g:
            lay = Image.new("RGBA", (PW + 160, PH + 160), (0, 0, 0, 0))
            ImageDraw.Draw(lay).rounded_rectangle([80, 80, 80 + PW, 80 + PH], 30, fill=g + (200,))
            img.alpha_composite(lay.filter(ImageFilter.GaussianBlur(30)), (x + dx - 80, PY - 80))
        if alpha < 1:
            im.putalpha(im.split()[3].point(lambda v: int(v * alpha)))
        img.alpha_composite(im, (x + dx, PY))

def labels(img, a=1.0):
    overlay_text(img, PY + PH + 18, "A", F("Black", 64), GREY, a, cx=XA + PW // 2)
    overlay_text(img, PY + PH + 18, "B", F("Black", 64), GREY, a, cx=XB + PW // 2)

# ---------- scenes ----------
def c1(t):  # hook 0-3.2
    img = base()
    pa = ease(t / 0.5)
    shake = int(12 * math.sin(t * 90)) if 1.6 < t < 1.95 else 0
    panels(img, t, dx=shake, alpha=pa)
    labels(img, pa)
    a, dy = pop(t, 0.05); overlay_text(img, 280, "One is real carbon.", F("Black", 82), WHITE, a, dy)
    a, dy = pop(t, 0.6); overlay_text(img, 390, "One is plastic", F("Black", 82), WHITE, a, dy)
    overlay_text(img, 490, "with a sticker.", F("Black", 82), WHITE, a, dy)
    a, dy = pop(t, 1.6, 0.25); overlay_text(img, 650, "Can you tell?", F("Black", 104), RED, a, dy)
    if 1.6 < t < 1.72:
        img.alpha_composite(Image.new("RGBA", img.size, (255, 40, 40, 60)))
    return img

def c2(t):  # vote 3.2-7.2
    img = base()
    panels(img, t + 3.2)
    labels(img)
    a, dy = pop(t, 0.0)
    overlay_text(img, 280, "Comment A or B", F("Black", 92), BLUE, a, dy)
    overlay_text(img, 395, "before the reveal", F("Bold", 58), WHITE, a, dy)
    n = 3 - int(t // 1.2)
    if 0 < n <= 3 and t < 3.6:
        k = (t % 1.2) / 1.2
        lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); dl = ImageDraw.Draw(lay)
        cx, cy, r = W // 2, 640, 110
        dl.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(60, 70, 90, 255), width=14)
        dl.arc([cx - r, cy - r, cx + r, cy + r], -90, -90 + 360 * (1 - k), fill=BLUE + (255,), width=14)
        img.alpha_composite(lay)
        overlay_text(img, cy - 75, str(n), F("Black", 130), WHITE, 1.0)
    fade_in(img, t)
    return img

def c3(t):  # 3 ways to tell 7.2-16.2  (3 x 3.0 s)
    img = base()
    i = min(2, int(t // 3.0)); lt = t - i * 3.0
    overlay_text(img, 240, "3 ways to tell", F("Black", 80), WHITE, ease(t / 0.3))
    heads = ["1  Move the light", "2  Feel the weight", "3  Check the edge"]
    subs = [("Real weave flips light/dark", "Fake shine just slides over"),
            ("Real carbon is very light", "A wrapped part weighs like plastic"),
            ("Real shows layers of fibre", "Fake shows plain plastic")]
    a, dy = pop(lt, 0.0, 0.3)
    card(img, 70, 360 + dy, W - 70, 640 + dy, a, border=BLUE)
    overlay_text(img, 385, heads[i], F("ExtraBold", 60), BLUE, a, dy)
    overlay_text(img, 480, subs[i][0], F("Medium", 42), WHITE, a, dy)
    overlay_text(img, 548, subs[i][1], F("Medium", 42), (200, 205, 215), a, dy)
    if i == 0:
        panels(img, t, swap_speed=1.6)
    elif i == 1:
        panels(img, t)
        lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); dl = ImageDraw.Draw(lay)
        wa = ease((lt - 0.4) / 0.4)
        for x, txt, col in ((XA, "LIGHT", GREEN), (XB, "HEAVY", ORANGE)):
            dl.rounded_rectangle([x + 90, PY + 250, x + PW - 90, PY + 350], 20, fill=(10, 12, 18, int(220 * wa)))
            img.alpha_composite(lay); lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); dl = ImageDraw.Draw(lay)
            overlay_text(img, PY + 268, txt, F("Black", 52), col, wa, cx=x + PW // 2)
    else:
        panels(img, t, edge=True)
        ea = ease((lt - 0.5) / 0.4)
        lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); dl = ImageDraw.Draw(lay)
        for x in (XA, XB):
            dl.rounded_rectangle([x + 80, PY + PH - 135, x + PW - 80, PY + PH - 78], 16, fill=(10, 12, 18, int(230 * ea)))
        img.alpha_composite(lay)
        overlay_text(img, PY + PH - 125, "fibre plies", F("Bold", 34), GREEN, ea, cx=XA + PW // 2)
        overlay_text(img, PY + PH - 125, "plastic", F("Bold", 34), ORANGE, ea, cx=XB + PW // 2)
    labels(img)
    fade_in(img, t)
    return img

def c4(t):  # reveal 16.2-20.2
    img = base()
    g = ease((t - 0.3) / 0.3)
    panels(img, t + 16.2, glowA=GREEN if g > 0 else None, glowB=RED if g > 0 else None)
    labels(img)
    a, dy = pop(t, 0.3, 0.25)
    overlay_text(img, 280, "A is real.", F("Black", 104), GREEN, a, dy)
    overlay_text(img, 410, "B is fake.", F("Black", 104), RED, a, dy)
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); dl = ImageDraw.Draw(lay)
    s = int(80 * g)
    if s > 4:
        cxa, cxb, cy = XA + PW // 2, XB + PW // 2, PY - 90
        dl.ellipse([cxa - s, cy - s, cxa + s, cy + s], fill=GREEN + (255,))
        dl.line([(cxa - s * .45, cy), (cxa - s * .1, cy + s * .35), (cxa + s * .5, cy - s * .35)], fill=WHITE + (255,), width=max(2, s // 6))
        dl.ellipse([cxb - s, cy - s, cxb + s, cy + s], fill=RED + (255,))
        q = s * .4
        dl.line([(cxb - q, cy - q), (cxb + q, cy + q)], fill=WHITE + (255,), width=max(2, s // 6))
        dl.line([(cxb - q, cy + q), (cxb + q, cy - q)], fill=WHITE + (255,), width=max(2, s // 6))
    img.alpha_composite(lay)
    a, dy = pop(t, 1.6)
    overlay_text(img, 600, "Did you guess right?", F("Bold", 54), WHITE, a, dy)
    fade_in(img, t)
    return img

def c5(t):  # why it matters 20.2-24.4
    img = base()
    overlay_text(img, 250, "Why it matters", F("Black", 84), BLUE, ease(t / 0.3))
    rows = [("Price", "You pay for real material"),
            ("Weight", "Only real carbon saves it"),
            ("Strength", "A sticker adds none")]
    for i, (h, s) in enumerate(rows):
        a, dy = pop(t, 0.4 + i * 0.8)
        y = 420 + i * 280 + dy
        card(img, 80, y, W - 80, y + 230, a)
        overlay_text(img, y + 40, h, F("ExtraBold", 60), WHITE, a)
        overlay_text(img, y + 132, s, F("Medium", 44), (200, 210, 225), a)
    sm = panel_img(panel_real(t * 2.2, (t * 420) % 1400 - 250)).resize((210, 300))
    img.alpha_composite(sm, (W // 2 - 105, 1300))
    fade_in(img, t)
    return img

def c6(t):  # trap 24.4-27.4
    img = base()
    a, dy = pop(t, 0.1, 0.3)
    overlay_text(img, 300, "Trap:", F("Black", 90), ORANGE, a, dy)
    overlay_text(img, 460, "\"Carbon look\"", F("Black", 104), WHITE, a, dy)
    overlay_text(img, 590, "≠", F("Black", 120), ORANGE, a, dy)
    overlay_text(img, 740, "carbon fibre", F("Black", 104), WHITE, a, dy)
    a2, dy2 = pop(t, 1.0)
    overlay_text(img, 920, "Read the listing: material, not style.", F("Medium", 42), GREY, a2, dy2)
    sm = panel_img(panel_fake(0, (t * 420) % 1400 - 250)).resize((280, 400))
    img.alpha_composite(sm, (W // 2 - 140, 1080))
    fade_in(img, t)
    return img

def c7(t):  # PACAR picker 27.4-31.4
    img = base()
    overlay_text(img, 250, "Don't guess.", F("Black", 96), WHITE, ease(t / 0.3))
    overlay_text(img, 370, "Pick your car. See real parts.", F("Bold", 54), BLUE, ease((t - 0.3) / 0.3))
    a = ease((t - 0.5) / 0.4)
    card(img, 140, 520, W - 140, 1480, a, border=(60, 70, 90), fill=(16, 22, 34))
    fields = [("Make", "Porsche"), ("Model", "911"), ("Part", "Mirror cap")]
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
    overlay_text(img, 1235, "✓  Real carbon options", F("ExtraBold", 50), GREEN, ra)
    overlay_text(img, 1315, "Material listed for every part", F("Medium", 34), (190, 240, 205), ra)
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); dl = ImageDraw.Draw(lay)
    dl.rounded_rectangle([W - 330, 540, W - 170, 600], 14, fill=ORANGE + (int(255 * a),))
    dl.text((W - 250, 570), "DEMO", font=F("Black", 34), fill=(20, 20, 20, int(255 * a)), anchor="mm")
    img.alpha_composite(lay)
    fade_in(img, t)
    return img

def c8(t):  # CTA 31.4-34
    img = base()
    k = ease(t / 0.4)
    d = ImageDraw.Draw(img)
    s = int(200 * (0.7 + 0.3 * k))
    d.rounded_rectangle([W // 2 - s // 2, 520, W // 2 + s // 2, 520 + s], 40, fill=BLUE)
    overlay_text(img, 520 + s // 2 - 80, "P", F("Black", 150), WHITE, k)
    overlay_text(img, 800, "PACAR", F("Black", 120), WHITE, k)
    a, dy = pop(t, 0.4)
    overlay_text(img, 1000, "Got it right? Comment A or B", F("Bold", 54), WHITE, a, dy)
    a, dy = pop(t, 0.8)
    card(img, 230, 1120 + dy, W - 230, 1250 + dy, a, border=BLUE, fill=BLUE)
    overlay_text(img, 1148, "Subscribe", F("ExtraBold", 58), WHITE, a, dy)
    fade_in(img, t)
    return img

SCENES = [(c1, 3.2), (c2, 4.0), (c3, 9.0), (c4, 4.0), (c5, 4.2), (c6, 3.0), (c7, 4.0), (c8, 2.6)]
STILL_T = [2.4, 1.0, 1.5, 2.5, 3.5, 2.0, 3.3, 2.0]
EXTRA_STILLS = [(2, 4.5), (2, 7.5)]
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
        shots = [(i, tt) for i, tt in enumerate(STILL_T)] + EXTRA_STILLS
        for k, (i, tt) in enumerate(shots):
            SCENES[i][0](tt).convert("RGB").save(f"{OUT}/still{k}.jpg", quality=85)
    else:
        for i in [int(x) for x in sys.argv[1:]]:
            fn, dur = SCENES[i]
            render_scene(i, fn, dur)
