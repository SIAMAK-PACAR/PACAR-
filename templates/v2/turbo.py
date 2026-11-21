import math, sys
from PIL import Image, ImageDraw, ImageFilter
import render as R
from render import (W, H, FPS, F, BLUE, RED, GREEN, WHITE, GREY, ORANGE, ease, clamp,
                    overlay_text, pop, card, base, fade_in, render_scene)

def lerp(a, b, k): return tuple(int(a[i] + (b[i] - a[i]) * k) for i in range(3))

def turbo(angle, hot=0.0):
    S = 2
    w, h = 720 * S, 560 * S
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    def P(*v): return [x * S for x in v]
    # turbine housing (right, cast iron)
    tc = lerp((62, 64, 70), (255, 95, 25), hot)
    d.rectangle(P(560, 380, 700, 520), fill=lerp((52, 54, 60), (230, 80, 20), hot))   # outlet flange
    d.ellipse(P(420, 160, 700, 440), fill=tc)
    d.ellipse(P(500, 240, 620, 360), fill=lerp((35, 36, 40), (150, 40, 10), hot))
    d.ellipse(P(440, 175, 560, 260), fill=lerp((95, 98, 106), (255, 170, 80), hot))
    # center section
    d.rectangle(P(360, 230, 450, 370), fill=(150, 112, 60))
    d.rectangle(P(390, 150, 418, 232), fill=(185, 160, 110))          # oil feed line
    d.rectangle(P(378, 140, 430, 158), fill=(205, 180, 130))
    d.rectangle(P(360, 250, 450, 262), fill=(110, 80, 40))
    d.rectangle(P(360, 340, 450, 352), fill=(110, 80, 40))
    # compressor housing (left, aluminium)
    d.polygon(P(70, 40, 190, 40, 230, 170, 120, 200), fill=(176, 182, 192))  # outlet tube
    d.ellipse(P(70, 20, 190, 70), fill=(150, 156, 168))
    d.ellipse(P(30, 110, 400, 480), fill=(188, 194, 204))
    d.ellipse(P(55, 130, 300, 330), fill=(222, 226, 234))                 # highlight
    d.ellipse(P(30, 110, 400, 480), outline=(130, 136, 148), width=6 * S)
    d.ellipse(P(100, 180, 330, 410), fill=(40, 44, 52))                   # inlet
    d.ellipse(P(100, 180, 330, 410), outline=(215, 220, 228), width=10 * S)
    # compressor wheel
    cx, cy, r = 215 * S, 295 * S, 100 * S
    for k in range(10):
        a0 = angle + k * 2 * math.pi / 10
        pts = []
        for j in range(8):
            rr = 18 * S + (r - 18 * S) * j / 7
            aa = a0 + 0.55 * (j / 7) ** 1.3
            pts.append((cx + rr * math.cos(aa), cy + rr * math.sin(aa)))
        for j in range(7, -1, -1):
            rr = 18 * S + (r - 18 * S) * j / 7
            aa = a0 + 0.55 * (j / 7) ** 1.3 + 0.16
            pts.append((cx + rr * math.cos(aa), cy + rr * math.sin(aa)))
        d.polygon(pts, fill=(200, 206, 216), outline=(120, 126, 138))
    d.ellipse([cx - 26 * S, cy - 26 * S, cx + 26 * S, cy + 26 * S], fill=(230, 232, 238))
    d.ellipse([cx - 9 * S, cy - 9 * S, cx + 9 * S, cy + 9 * S], fill=(90, 94, 104))
    # actuator
    d.line(P(250, 470, 300, 520), fill=(120, 120, 120), width=8 * S)
    d.ellipse(P(200, 460, 300, 550), fill=(205, 170, 70))
    d.ellipse(P(220, 478, 280, 532), fill=(175, 140, 50))
    return im.resize((w // S, h // S), Image.LANCZOS)

def put(img, angle, cx, cy, scale=1.0, hot=0.0, glow=None, glow_a=0.0):
    sp = turbo(angle, hot)
    sp = sp.resize((int(sp.width * scale), int(sp.height * scale)), Image.LANCZOS)
    x, y = int(cx - sp.width / 2), int(cy - sp.height / 2)
    if glow and glow_a > 0:
        g = Image.new("RGBA", (sp.width + 200, sp.height + 200), (0, 0, 0, 0))
        m = sp.split()[3].point(lambda v: int(v * glow_a))
        g.paste(Image.new("RGBA", sp.size, glow + (255,)), (100, 100), m)
        img.alpha_composite(g.filter(ImageFilter.GaussianBlur(40)), (x - 100, y - 100))
    img.alpha_composite(sp, (x, y))
    return x, y, sp.width / 720

def smoke(img, t, x, y, a=1.0, col=(150, 160, 190)):
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    for k in range(7):
        p = ((t * 0.6 + k / 7) % 1)
        r = 18 + 42 * p
        d.ellipse([x + 40 * math.sin(k * 2.1 + t) - r, y - 110 * p - r, x + 40 * math.sin(k * 2.1 + t) + r, y - 110 * p + r],
                  fill=col + (int(110 * (1 - p) * a),))
    img.alpha_composite(lay.filter(ImageFilter.GaussianBlur(12)))

def s1(t):
    img = base()
    pa = ease(t / 0.5)
    shake = int(14 * math.sin(t * 90)) if 1.5 < t < 1.9 else 0
    xa = -350 + (300 + 350) * pa + shake
    xb = W + 350 - (W + 350 - 790) * pa + shake
    red = clamp((t - 1.5) / 0.3)
    put(img, t * 2, xa, 1200, 0.6)
    put(img, t * 2, xb, 1200, 0.6, glow=RED, glow_a=red * (0.7 + 0.3 * math.sin(t * 12)))
    a, dy = pop(t, 0.05); overlay_text(img, 300, "These 2 turbos", F("Black", 92), WHITE, a, dy)
    a, dy = pop(t, 0.45); overlay_text(img, 410, "look identical.", F("Black", 92), WHITE, a, dy)
    a, dy = pop(t, 1.5, 0.25)
    overlay_text(img, 570, "One gives you", F("Black", 100), RED, a, dy)
    overlay_text(img, 690, "only lag.", F("Black", 100), RED, a, dy)
    for lbl, x in (("A", xa), ("B", xb)):
        overlay_text(img, 1430, lbl, F("Black", 70), GREY, pa, cx=int(x))
    if 1.5 < t < 1.62:
        img.alpha_composite(Image.new("RGBA", img.size, (255, 40, 40, 70)))
    return img

def s2(t):
    img = base()
    overlay_text(img, 250, "What it does", F("Black", 80), BLUE, ease(t / 0.3))
    steps = ["Exhaust spins the turbine", "→  The shaft spins the compressor", "→  More air is pushed in",
             "→  More fuel can burn = more power"]
    for i, s in enumerate(steps):
        a, dy = pop(t, 0.4 + i * 0.7)
        overlay_text(img, 370 + i * 76, s, F("Bold", 48), WHITE, a, dy)
    cx, cy, sc = W // 2, 1130, 1.1
    x0, y0, k = put(img, t * 18, cx, cy, sc, hot=0.25)
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    for j in range(12):      # exhaust in (orange) to turbine, from right
        p = (t * 1.4 + j / 12) % 1
        px, py = x0 + (760 - 200 * p) * k, y0 + (300 + 30 * math.sin(j)) * k
        d.ellipse([px - 10, py - 10, px + 10, py + 10], fill=ORANGE + (int(230 * (1 - p)),))
    for j in range(12):      # compressed air out (blue) through outlet, upward
        p = (t * 1.4 + j / 12) % 1
        px, py = x0 + (130 + 10 * math.sin(j)) * k, y0 + (40 - 160 * p) * k
        d.ellipse([px - 10, py - 10, px + 10, py + 10], fill=(110, 190, 255, int(230 * (1 - p))))
    img.alpha_composite(lay.filter(ImageFilter.GaussianBlur(2)))
    a, dy = pop(t, 3.6)
    card(img, 120, 1530, W - 120, 1640, a)
    overlay_text(img, 1555, "It can spin over 100,000 rpm", F("ExtraBold", 50), WHITE, a)
    fade_in(img, t)
    return img

def s3(t):
    img = base()
    overlay_text(img, 250, "The mistake", F("Black", 84), RED, ease(t / 0.3))
    heat = clamp((t - 0.5) / 2.0)
    put(img, t * 6, W // 2, 620, 0.55, hot=heat, glow=ORANGE, glow_a=heat * (0.5 + 0.3 * math.sin(t * 9)))
    smoke(img, t, W // 2 - 210, 520, a=clamp((t - 2.3) / 1.0))
    cards = [("Wrong part number", "wrong size for your engine → lag"),
             ("Bad oil feed", "bearings fail → blue smoke"),
             ("Worn seals", "oil leaks, whining, power loss")]
    for i, (hd, s) in enumerate(cards):
        a, dy = pop(t, 0.6 + i * 1.7)
        y = 800 + i * 270 + dy
        card(img, 80, y, W - 80, y + 230, a, border=RED)
        overlay_text(img, y + 40, hd, F("ExtraBold", 54), WHITE, a)
        overlay_text(img, y + 128, s, F("Medium", 40), (255, 190, 190), a)
    fade_in(img, t)
    return img

def s4(t):
    img = base()
    overlay_text(img, 250, "4 things must match", F("Black", 76), WHITE, ease(t / 0.3))
    overlay_text(img, 345, "YOUR engine", F("Black", 92), BLUE, ease((t - 0.2) / 0.3))
    items = [("1", "Part number"), ("2", "Oil + coolant lines"), ("3", "Actuator type"), ("4", "Housing + flange")]
    for i, (n, s) in enumerate(items):
        a, dy = pop(t, 0.7 + i * 0.75)
        y = 540 + i * 230 + dy
        card(img, 80, y, W - 80, y + 190, a)
        lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); dl = ImageDraw.Draw(lay)
        dl.ellipse([120, y + 45, 220, y + 145], fill=BLUE + (int(255 * a),))
        dl.text((260, y + 95), s, font=F("Bold", 52), fill=WHITE + (int(255 * a),), anchor="lm")
        img.alpha_composite(lay)
        overlay_text(img, y + 57, n, F("Black", 60), WHITE, a, cx=170)
    a, _ = pop(t, 4.0)
    overlay_text(img, 1520, "Check the spec for your exact engine.", F("Medium", 40), GREY, a)
    fade_in(img, t)
    return img

def s5(t):
    img = base()
    overlay_text(img, 250, "Upgrade?", F("Black", 90), GREEN, ease(t / 0.3))
    a, dy = pop(t, 0.3)
    card(img, 80, 400 + dy, W - 80, 560 + dy, a, border=ORANGE)
    overlay_text(img, 440, "A bigger turbo is not free power", F("Bold", 46), ORANGE, a, dy)
    a, dy = pop(t, 1.2)
    card(img, 80, 600 + dy, W - 80, 840 + dy, a, border=GREEN)
    overlay_text(img, 635, "It needs fuel, cooling", F("Bold", 48), WHITE, a, dy)
    overlay_text(img, 710, "and a remap", F("Bold", 48), WHITE, a, dy)
    a, dy = pop(t, 2.0)
    overlay_text(img, 880, "...or you just buy lag.", F("ExtraBold", 54), RED, a, dy)
    put(img, t * 10, W // 2, 1250, 0.62, glow=GREEN, glow_a=0.3)
    a, dy = pop(t, 2.6)
    overlay_text(img, 1520, "Tuning must pass your local inspection rules.", F("Medium", 36), GREY, a, dy)
    fade_in(img, t)
    return img

def s6(t):
    img = base()
    overlay_text(img, 250, "Don't guess.", F("Black", 96), WHITE, ease(t / 0.3))
    overlay_text(img, 370, "Pick your car. See what fits.", F("Bold", 54), BLUE, ease((t - 0.3) / 0.3))
    a = ease((t - 0.5) / 0.4)
    card(img, 140, 520, W - 140, 1480, a, border=(60, 70, 90), fill=(16, 22, 34))
    for i, (k, v) in enumerate([("Make", "Volkswagen"), ("Model", "Golf GTI"), ("Engine", "2.0 TSI")]):
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
    overlay_text(img, 1315, "Turbo matched", F("Medium", 36), (190, 240, 205), ra)
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
    overlay_text(img, 1000, "Next: oil, timing belt or brakes?", F("Bold", 52), WHITE, a, dy)
    a, dy = pop(t, 0.9)
    card(img, 190, 1120 + dy, W - 190, 1250 + dy, a, border=BLUE, fill=BLUE)
    overlay_text(img, 1148, "Comment + Subscribe", F("ExtraBold", 54), WHITE, a, dy)
    fade_in(img, t)
    return img

SCENES = [(s1, 3.2), (s2, 6.8), (s3, 7.5), (s4, 5.0), (s5, 4.0), (s6, 4.0), (s7, 2.5)]

if __name__ == "__main__":
    if sys.argv[1] == "stills":
        for i, ((fn, dur), tt) in enumerate(zip(SCENES, [2.6, 4.2, 6.5, 4.6, 3.5, 3.5, 2.0])):
            fn(tt).convert("RGB").save(f"{R.OUT}/still{i}.jpg", quality=85)
    else:
        for i in [int(x) for x in sys.argv[1:]]:
            fn, dur = SCENES[i]
            render_scene(i, fn, dur)
