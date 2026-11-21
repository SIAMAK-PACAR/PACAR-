import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render as R
from render import *

R.OUT = os.path.dirname(os.path.abspath(__file__))
OIL = (232, 170, 40)

def bottle_sprite():
    S = 2
    w, h = 380 * S, 720 * S
    a = np.zeros((h, w, 4))
    cyl_fill(a, 0, w, 0, h, (44, 58, 84), 0.45, 0.4)
    img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGBA")
    mask = Image.new("L", (w, h), 0)
    m = ImageDraw.Draw(mask)
    m.rounded_rectangle([0, 160 * S, w, h], 50 * S, fill=255)              # body
    m.rounded_rectangle([60 * S, 90 * S, 220 * S, 200 * S], 30 * S, fill=255)  # shoulder/neck
    m.rounded_rectangle([230 * S, 70 * S, 360 * S, 300 * S], 40 * S, fill=255)  # handle
    m.rounded_rectangle([262 * S, 120 * S, 328 * S, 250 * S], 20 * S, fill=0)   # handle hole
    img.putalpha(mask)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([80 * S, 20 * S, 200 * S, 100 * S], 14 * S, fill=(205, 40, 40))  # cap
    for k in range(5):
        d.line([(92 * S + k * 24 * S, 26 * S), (92 * S + k * 24 * S, 94 * S)], fill=(160, 25, 25), width=3 * S)
    d.rounded_rectangle([40 * S, 300 * S, w - 40 * S, 620 * S], 24 * S, fill=(232, 236, 242))
    d.rectangle([40 * S, 300 * S, w - 40 * S, 360 * S], fill=(205, 40, 40))
    f = ImageFont.truetype(FD + "Inter-Black.otf", 44 * S)
    f2 = ImageFont.truetype(FD + "Inter-Black.otf", 70 * S)
    d.text((w // 2, 330 * S), "ENGINE OIL", font=f, fill=WHITE, anchor="mm")
    d.text((w // 2, 470 * S), "?W-??", font=f2, fill=(30, 36, 48), anchor="mm")
    d.text((w // 2, 570 * S), "4 L", font=f, fill=(90, 100, 115), anchor="mm")
    return img.resize((w // S, h // S), Image.LANCZOS)

BOTTLE = bottle_sprite()

def bearing(img, t, cx=W // 2, cy=1270, broken=0.0):
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    d.ellipse([cx - 300, cy - 300, cx + 300, cy + 300], fill=(80, 88, 104))
    d.ellipse([cx - 250, cy - 250, cx + 250, cy + 250], fill=(14, 18, 26))
    film = 1 - broken
    if film > 0:
        d.ellipse([cx - 246, cy - 246, cx + 246, cy + 246], fill=OIL + (int(230 * film),))
        for k in range(18):
            ang = t * 2.2 + k * (2 * math.pi / 18)
            x, y = cx + 232 * math.cos(ang), cy + 232 * math.sin(ang)
            d.ellipse([x - 9, y - 9, x + 9, y + 9], fill=(255, 225, 120, int(255 * film)))
    d.ellipse([cx - 212, cy - 212, cx + 212, cy + 212], fill=(14, 18, 26))
    img.alpha_composite(lay)
    sh = Image.new("RGBA", (424, 424), (0, 0, 0, 0))
    ds = ImageDraw.Draw(sh)
    ds.ellipse([0, 0, 423, 423], fill=(185, 192, 205))
    ds.ellipse([40, 40, 383, 383], fill=(160, 167, 180))
    ds.rectangle([200, 20, 224, 200], fill=(100, 106, 120))
    sh = sh.rotate(-math.degrees(t * 4), resample=Image.BICUBIC)
    off = int(18 * broken * math.sin(t * 40))
    img.alpha_composite(sh, (cx - 212 + off, cy - 212))
    if broken > 0:
        sp = Image.new("RGBA", img.size, (0, 0, 0, 0))
        dsp = ImageDraw.Draw(sp)
        for k in range(10):
            ang = t * 7 + k * 0.63
            x, y = cx + 215 * math.cos(ang), cy + 215 * math.sin(ang)
            dsp.ellipse([x - 7, y - 7, x + 7, y + 7], fill=(255, 200, 80, int(255 * broken)))
        sp = sp.filter(ImageFilter.GaussianBlur(3))
        img.alpha_composite(sp)

def s1(t):
    img = base()
    pa = ease(t / 0.5)
    shake = int(14 * math.sin(t * 90)) if 1.5 < t < 1.9 else 0
    xa = -300 + (300 + 300) * pa + shake
    xb = W + 300 - (W + 300 - 780) * pa + shake
    redglow = clamp((t - 1.5) / 0.3)
    paste_plug(img, BOTTLE, xa, 1250, 0.78)
    paste_plug(img, BOTTLE, xb, 1250, 0.78, glow=RED, glow_a=redglow * (0.7 + 0.3 * math.sin(t * 12)))
    la, dy = pop(t, 0.05)
    overlay_text(img, 280, "Same colour.", F("Black", 86), WHITE, la, dy)
    lb, dy2 = pop(t, 0.45)
    overlay_text(img, 385, "Same bottle size.", F("Black", 86), WHITE, lb, dy2)
    lc, dy3 = pop(t, 1.5, 0.25)
    overlay_text(img, 540, "One oil kills", F("Black", 100), RED, lc, dy3)
    overlay_text(img, 660, "your engine.", F("Black", 100), RED, lc, dy3)
    for lbl, x in (("A", xa), ("B", xb)):
        overlay_text(img, 1560, lbl, F("Black", 70), GREY, pa, cx=int(x))
    if 1.5 < t < 1.62:
        img.alpha_composite(Image.new("RGBA", img.size, (255, 40, 40, 70)))
    return img

def s2(t):
    img = base()
    overlay_text(img, 250, "What oil does", F("Black", 80), BLUE, ease(t / 0.3))
    steps = ["Thin film between metal parts", "→  Carries heat away", "→  Cleans out dirt"]
    for i, s in enumerate(steps):
        a, dy = pop(t, 0.4 + i * 0.8)
        overlay_text(img, 370 + i * 80, s, F("Bold", 54), WHITE, a, dy)
    bearing(img, t, cy=1130)
    a, _ = pop(t, 0.5)
    overlay_text(img, 1450, "oil film", F("Bold", 40), OIL, a)
    a, dy = pop(t, 3.4)
    card(img, 120, 1530, W - 120, 1640, a, border=RED)
    overlay_text(img, 1553, "No film = metal on metal", F("ExtraBold", 52), WHITE, a)
    fade_in(img, t)
    return img

def s3(t):
    img = base()
    overlay_text(img, 250, "The mistake", F("Black", 84), RED, ease(t / 0.3))
    heat = clamp((t - 0.5) / 2.0)
    paste_plug(img, BOTTLE, 225, 900, 0.5, glow=RED, glow_a=heat * (0.6 + 0.4 * math.sin(t * 9)))
    cards = [
        ("Wrong viscosity", "poor protection at cold start"),
        ("Wrong spec", "faster wear + sludge"),
        ("Turbo bearings", "can starve of oil and fail"),
    ]
    for i, (h, s) in enumerate(cards):
        a, dy = pop(t, 0.6 + i * 1.7)
        y = 420 + i * 300 + dy
        card(img, 420, y, W - 60, y + 250, a, border=RED)
        overlay_text(img, y + 45, h, F("ExtraBold", 50), WHITE, a, cx=(420 + W - 60) // 2)
        overlay_text(img, y + 130, s, F("Medium", 36), (255, 190, 190), a, cx=(420 + W - 60) // 2)
    a, dy = pop(t, 5.8)
    overlay_text(img, 1400, "Ticking  ·  Oil light  ·  Smoke", F("Bold", 48), ORANGE, a, dy)
    fade_in(img, t)
    return img

def s4(t):
    img = base()
    overlay_text(img, 250, "4 things must match", F("Black", 76), WHITE, ease(t / 0.3))
    overlay_text(img, 345, "YOUR engine", F("Black", 92), BLUE, ease((t - 0.2) / 0.3))
    items = [("1", "Viscosity, e.g. 0W-20"), ("2", "Maker approval code"), ("3", "Change interval"), ("4", "The right oil filter")]
    for i, (n, s) in enumerate(items):
        a, dy = pop(t, 0.7 + i * 0.75)
        y = 520 + i * 220 + dy
        card(img, 80, y, W - 80, y + 180, a)
        lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); dl = ImageDraw.Draw(lay)
        dl.ellipse([120, y + 40, 220, y + 140], fill=BLUE + (int(255 * a),))
        img.alpha_composite(lay)
        overlay_text(img, y + 52, n, F("Black", 60), WHITE, a, cx=170)
        lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); dl = ImageDraw.Draw(lay)
        dl.text((260, y + 90), s, font=F("Bold", 48), fill=WHITE + (int(255 * a),), anchor="lm")
        img.alpha_composite(lay)
    a, _ = pop(t, 3.9)
    card(img, 80, 1420, W - 80, 1600, a, border=OIL, fill=(40, 32, 14))
    overlay_text(img, 1445, "0W = how it flows when cold", F("Bold", 42), OIL, a)
    overlay_text(img, 1520, "20 = how thick it stays when hot", F("Bold", 42), OIL, a)
    fade_in(img, t)
    return img

def s5(t):
    img = base()
    overlay_text(img, 250, "Upgrade?", F("Black", 90), GREEN, ease(t / 0.3))
    a, dy = pop(t, 0.4)
    card(img, 80, 400 + dy, W - 80, 560 + dy, a, border=GREEN)
    overlay_text(img, 440, "Fully synthetic handles heat better", F("Bold", 44), WHITE, a, dy)
    a, dy = pop(t, 1.5)
    card(img, 80, 600 + dy, W - 80, 820 + dy, a, border=ORANGE)
    overlay_text(img, 635, "Trap: thicker oil is", F("Bold", 48), ORANGE, a, dy)
    overlay_text(img, 705, "NOT more protection", F("Black", 48), ORANGE, a, dy)
    bearing(img, t, cy=1200, broken=0.0)
    a, dy = pop(t, 2.4)
    overlay_text(img, 1560, "It flows slower on a cold start.", F("Medium", 40), GREY, a, dy)
    fade_in(img, t)
    return img

def s6(t):
    img = base()
    overlay_text(img, 250, "Don't guess.", F("Black", 96), WHITE, ease(t / 0.3))
    overlay_text(img, 370, "Pick your car. See what fits.", F("Bold", 54), BLUE, ease((t - 0.3) / 0.3))
    a = ease((t - 0.5) / 0.4)
    card(img, 140, 520, W - 140, 1480, a, border=(60, 70, 90), fill=(16, 22, 34))
    fields = [("Make", "Toyota"), ("Model", "Corolla"), ("Engine", "1.8 Hybrid")]
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
    overlay_text(img, 1315, "Oil + filter matched", F("Medium", 36), (190, 240, 205), ra)
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); dl = ImageDraw.Draw(lay)
    dl.rounded_rectangle([W - 330, 540, W - 170, 600], 14, fill=ORANGE + (int(255 * a),))
    dl.text((W - 250, 570), "DEMO", font=F("Black", 34), fill=(20, 20, 20, int(255 * a)), anchor="mm")
    img.alpha_composite(lay)
    fade_in(img, t)
    return img

def s7(t):
    img = base()
    k = ease(t / 0.4)
    d = ImageDraw.Draw(img)
    s = int(200 * (0.7 + 0.3 * k))
    d.rounded_rectangle([W // 2 - s // 2, 520, W // 2 + s // 2, 520 + s], 40, fill=BLUE)
    overlay_text(img, 520 + s // 2 - 80, "P", F("Black", 150), WHITE, k)
    overlay_text(img, 800, "PACAR", F("Black", 120), WHITE, k)
    a, dy = pop(t, 0.5)
    overlay_text(img, 1000, "Next: brakes, tyres or battery?", F("Bold", 54), WHITE, a, dy)
    a, dy = pop(t, 0.9)
    card(img, 190, 1120 + dy, W - 190, 1250 + dy, a, border=BLUE, fill=BLUE)
    overlay_text(img, 1148, "Comment + Subscribe", F("ExtraBold", 54), WHITE, a, dy)
    fade_in(img, t)
    return img

R.SCENES = [(s1, 3.2), (s2, 6.8), (s3, 7.5), (s4, 5.0), (s5, 4.0), (s6, 4.0), (s7, 2.5)]

if __name__ == "__main__":
    if sys.argv[1] == "stills":
        for i, (fn, dur), tt in zip(range(7), R.SCENES, [2.6, 4.0, 6.5, 4.6, 3.5, 3.5, 2.0]):
            fn(tt).convert("RGB").save(f"{R.OUT}/still{i}.jpg", quality=85)
        ims = [Image.open(f"{R.OUT}/still{i}.jpg").resize((360, 640)) for i in range(7)]
        c = Image.new("RGB", (1440, 1280), "white")
        for i, im in enumerate(ims): c.paste(im, ((i % 4) * 360, (i // 4) * 640))
        c.save(f"{R.OUT}/sheet.jpg")
    else:
        for i in [int(x) for x in sys.argv[1:]]:
            fn, dur = R.SCENES[i]
            R.render_scene(i, fn, dur)
