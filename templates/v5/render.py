import math, os, sys, subprocess
from PIL import Image, ImageDraw, ImageFilter
from lib import (W, H, FPS, F, BLUE, RED, GREEN, WHITE, GREY, ORANGE, ease, clamp,
                 overlay_text, pop, card, base, fade_in)

OUT = os.path.dirname(os.path.abspath(__file__))
PAINT = (200, 30, 40)       # base coat colour
CLEAR = (180, 210, 235)
PRIMER = (150, 150, 140)
METAL = (110, 116, 126)
CERAMIC = (120, 230, 255)
PPF = (140, 200, 255)

def stone_poly(cx, cy, r, rot):
    pts = []
    for k, rr in enumerate([1.0, 0.8, 1.1, 0.85, 1.0, 0.75, 0.95]):
        a = rot + k * 2 * math.pi / 7
        pts.append((cx + r * rr * math.cos(a), cy + r * rr * math.sin(a)))
    return pts

def draw_stone(img, cx, cy, r, rot, a=1.0):
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    d.polygon(stone_poly(cx, cy, r, rot), fill=(125, 118, 108, int(255 * a)))
    d.polygon(stone_poly(cx - r * 0.2, cy - r * 0.2, r * 0.45, rot), fill=(160, 152, 140, int(255 * a)))
    img.alpha_composite(lay)

def section(img, t, mode, top=820, hit=1.2):
    """Paint cross-section. mode: 'ceramic' or 'ppf'. hit = impact time."""
    x0, x1 = 90, W - 90
    cx = W // 2
    layers = [("Clear coat", CLEAR, 70), ("Base coat (colour)", PAINT, 70), ("Primer", PRIMER, 55), ("Metal", METAL, 120)]
    top_t = 26 if mode == "ceramic" else 90
    top_col = CERAMIC if mode == "ceramic" else PPF
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    p = clamp((t - hit) / 0.25)          # after impact
    # dent for PPF
    dent = 0
    if mode == "ppf" and t > hit:
        dent = 34 * math.exp(-(t - hit) * 2.2) * min(1, (t - hit) / 0.08)
    # top layer
    y = top
    alpha_top = 200 if mode == "ppf" else 255
    d.rectangle([x0, y, x1, y + top_t], fill=top_col + (alpha_top,))
    if dent > 0:
        d.ellipse([cx - 110, y - dent * 0.2, cx + 110, y + dent * 1.6], fill=(70, 120, 180, 230))
    y += top_t
    ys = []
    for name, col, th in layers:
        d.rectangle([x0, y, x1, y + th], fill=col + (255,))
        ys.append((name, y, th))
        y += th
    bottom = y
    # chip for ceramic
    if mode == "ceramic" and p > 0:
        depth = top + top_t + 70 + 70 * ease(p)
        chip = [(cx - 120 * ease(p), top - 2), (cx + 120 * ease(p), top - 2), (cx + 30, depth), (cx - 40, depth)]
        d.polygon(chip, fill=(12, 16, 24, 255))
        d.line(chip + [chip[0]], fill=RED + (255,), width=5)
        for k in range(6):  # flying fragments
            ang = -math.pi / 2 + (k - 2.5) * 0.45
            dist = 260 * ease((t - hit) / 0.8)
            fx, fy = cx + dist * math.cos(ang), top - 20 + dist * math.sin(ang) + 300 * ((t - hit) / 0.8) ** 2
            if t - hit < 1.2:
                d.rectangle([fx - 9, fy - 9, fx + 9, fy + 9], fill=PAINT + (255,))
    img.alpha_composite(lay)
    # labels
    for name, yy, th in ys:
        overlay_text(img, yy + th / 2 - 22, name, F("Bold", 34), (15, 15, 20) if name != "Metal" else WHITE, 1.0, cx=280)
    lbl = "Ceramic coating: a few microns" if mode == "ceramic" else "PPF film: ~150–200 microns"
    overlay_text(img, top - 70, lbl, F("ExtraBold", 40), top_col, 1.0)
    # stone flight
    if t < hit:
        k = t / hit
        sx = W - 40 - (W - 40 - cx) * k
        sy = top - 430 + (430 - 40) * k
        draw_stone(img, sx, sy, 38, t * 6)
    elif mode == "ppf":
        k = (t - hit) / 0.9
        if k < 1:
            draw_stone(img, cx + 380 * k, top - 40 - 420 * k + 200 * k * k, 38, t * 6, 1 - k)
    else:
        k = (t - hit) / 0.6
        if k < 1:
            draw_stone(img, cx + 150 * k, top - 40 - 200 * k, 38, t * 6, 1 - k)
    if hit < t < hit + 0.08:
        img.alpha_composite(Image.new("RGBA", img.size, (255, 255, 255, 60)))
    return bottom

def s1(t):  # hook 0-3.5
    img = base()
    a, dy = pop(t, 0.05)
    overlay_text(img, 280, "A stone hits your paint", F("Black", 76), WHITE, a, dy)
    a, dy = pop(t, 0.4)
    overlay_text(img, 380, "at 100 km/h.", F("Black", 96), ORANGE, a, dy)
    a, dy = pop(t, 1.9, 0.25)
    overlay_text(img, 1450, "Which one saves it?", F("Black", 88), BLUE, a, dy)
    # car door panel with incoming stone
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    d.rounded_rectangle([120, 760, W - 120, 1320], 60, fill=PAINT + (255,))
    d.rounded_rectangle([150, 790, W - 150, 900], 50, fill=(235, 90, 95, 120))
    img.alpha_composite(lay)
    k = clamp(t / 1.7)
    sx, sy = W + 80 - (W + 80 - W // 2) * ease(k), 520 + (1020 - 520) * ease(k)
    sc = 20 + 60 * k
    draw_stone(img, sx, sy, sc, t * 7)
    if 1.7 < t < 1.85:
        img.alpha_composite(Image.new("RGBA", img.size, (255, 255, 255, 90)))
    overlay_text(img, 1560, "Ceramic coating  vs  PPF", F("Bold", 50), GREY, ease((t - 2.2) / 0.3))
    return img

def s2(t):  # ceramic 3.5-10
    img = base()
    overlay_text(img, 240, "Ceramic coating", F("Black", 84), CERAMIC, ease(t / 0.3))
    section(img, t, "ceramic", top=760, hit=1.3)
    a, dy = pop(t, 2.4)
    card(img, 80, 1230 + dy, W - 80, 1360 + dy, a, border=GREEN)
    overlay_text(img, 1262, "Gloss + easy cleaning + UV help", F("Bold", 46), WHITE, a, dy)
    a, dy = pop(t, 3.6)
    card(img, 80, 1400 + dy, W - 80, 1530 + dy, a, border=RED)
    overlay_text(img, 1432, "Does NOT stop stone chips", F("ExtraBold", 50), RED, a, dy)
    fade_in(img, t)
    return img

def s3(t):  # ppf 10-17
    img = base()
    overlay_text(img, 240, "PPF (paint protection film)", F("Black", 64), PPF, ease(t / 0.3))
    section(img, t, "ppf", top=760, hit=1.3)
    a, dy = pop(t, 2.3)
    card(img, 80, 1290 + dy, W - 80, 1420 + dy, a, border=GREEN)
    overlay_text(img, 1322, "Thick film absorbs the hit", F("ExtraBold", 50), GREEN, a, dy)
    a, dy = pop(t, 3.8)
    card(img, 80, 1450 + dy, W - 80, 1580 + dy, a, border=ORANGE)
    overlay_text(img, 1482, "Many films self-heal light swirls with heat", F("Bold", 38), WHITE, a, dy)
    # heat waves
    if t > 4.2:
        lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
        for k in range(3):
            xx = 380 + k * 160
            pts = [(xx + 18 * math.sin((yy + t * 300) / 22), 690 - yy) for yy in range(0, 120, 6)]
            d.line(pts, fill=ORANGE + (180,), width=6)
        img.alpha_composite(lay)
    fade_in(img, t)
    return img

def car_side(img, cx, cy, s, front_a):
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    def P(x, y): return (cx + x * s, cy + y * s)
    body = [P(-420, 60), P(-430, -20), P(-300, -40), P(-160, -150), P(120, -150), P(260, -50), P(420, -30), P(440, 60)]
    d.polygon(body, fill=(60, 66, 80, 255))
    d.polygon([P(-140, -135), P(100, -135), P(220, -50), P(-260, -50)], fill=(30, 40, 58, 255))
    # front PPF zone (right side = front)
    front = [P(160, -110), P(260, -50), P(420, -30), P(440, 60), P(200, 60), P(160, -40)]
    d.polygon(front, fill=PPF + (int(170 * front_a),))
    for wx in (-260, 260):
        d.ellipse([*P(wx - 75, -10), *P(wx + 75, 140)], fill=(20, 20, 24, 255))
        d.ellipse([*P(wx - 40, 25), *P(wx + 40, 105)], fill=(130, 136, 148, 255))
    img.alpha_composite(lay)

def s4(t):  # best combo 17-22
    img = base()
    overlay_text(img, 250, "Best combo", F("Black", 96), GREEN, ease(t / 0.3))
    car_side(img, W // 2 - 20, 960, 1.15, ease((t - 0.6) / 0.5))
    # ceramic sheen sweep
    if t > 1.6:
        k = ((t - 1.6) / 1.4) % 1.0
        lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
        x = 60 + k * (W - 120)
        d.polygon([(x, 780), (x + 60, 780), (x - 40, 1100), (x - 100, 1100)], fill=(255, 255, 255, 70))
        img.alpha_composite(lay.filter(ImageFilter.GaussianBlur(8)))
    a, dy = pop(t, 0.7)
    card(img, 80, 1200 + dy, W - 80, 1320 + dy, a, border=PPF)
    overlay_text(img, 1228, "PPF on the front", F("ExtraBold", 54), PPF, a, dy)
    a, dy = pop(t, 1.6)
    card(img, 80, 1350 + dy, W - 80, 1470 + dy, a, border=CERAMIC)
    overlay_text(img, 1378, "Ceramic on top", F("ExtraBold", 54), CERAMIC, a, dy)
    overlay_text(img, 380, "bumper · hood · mirrors", F("Bold", 48), GREY, ease((t - 0.9) / 0.3))
    fade_in(img, t)
    return img

def s5(t):  # trap 22-26
    img = base()
    overlay_text(img, 250, "The trap", F("Black", 96), ORANGE, ease(t / 0.3))
    # yellowed peeling film panel
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    d.rounded_rectangle([160, 430, W - 160, 900], 40, fill=PAINT + (255,))
    yk = ease((t - 0.3) / 1.2)
    img.alpha_composite(lay); lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    d.rounded_rectangle([160, 430, W - 160, 900], 40, fill=(230, 200, 70, int(90 * yk)))
    img.alpha_composite(lay); lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    peel = ease((t - 0.8) / 1.0)
    d.polygon([(W - 160, 430), (W - 160 - 220 * peel, 430), (W - 160, 430 + 260 * peel)], fill=(12, 16, 24, 255))
    d.polygon([(W - 160 - 220 * peel, 430), (W - 160, 430 + 260 * peel), (W - 160 - 150 * peel, 430 + 120 * peel)], fill=(230, 210, 140, 230))
    img.alpha_composite(lay)
    a, dy = pop(t, 0.5)
    card(img, 80, 990 + dy, W - 80, 1120 + dy, a, border=ORANGE)
    overlay_text(img, 1022, "Cheap film can yellow or peel", F("ExtraBold", 48), WHITE, a, dy)
    a, dy = pop(t, 1.6)
    card(img, 80, 1160 + dy, W - 80, 1290 + dy, a, border=BLUE)
    overlay_text(img, 1192, "Get it fitted by a pro", F("ExtraBold", 52), WHITE, a, dy)
    fade_in(img, t)
    return img

def s6(t):  # PACAR picker 26-30
    img = base()
    overlay_text(img, 250, "Don't guess.", F("Black", 96), WHITE, ease(t / 0.3))
    overlay_text(img, 370, "Pick your car. See what fits.", F("Bold", 54), BLUE, ease((t - 0.3) / 0.3))
    a = ease((t - 0.5) / 0.4)
    card(img, 140, 520, W - 140, 1480, a, border=(60, 70, 90), fill=(16, 22, 34))
    for i, (k, v) in enumerate([("Make", "Audi"), ("Model", "A4"), ("Protect", "Front PPF + ceramic")]):
        fa = ease((t - 0.8 - i * 0.45) / 0.3)
        y = 600 + i * 190
        card(img, 200, y, W - 200, y + 150, fa * a, border=(50, 60, 80), fill=(26, 34, 50))
        lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); dl = ImageDraw.Draw(lay)
        dl.text((240, y + 20), k, font=F("Medium", 32), fill=GREY + (int(255 * fa),))
        dl.text((240, y + 62), v, font=F("Bold", 46), fill=WHITE + (int(255 * fa),))
        img.alpha_composite(lay)
    ra = ease((t - 2.3) / 0.35)
    card(img, 200, 1200, W - 200, 1400, ra, border=GREEN, fill=(18, 44, 30))
    overlay_text(img, 1235, "✓  Front kit fits", F("ExtraBold", 52), GREEN, ra)
    overlay_text(img, 1315, "Bumper · hood · mirrors", F("Medium", 36), (190, 240, 205), ra)
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); dl = ImageDraw.Draw(lay)
    dl.rounded_rectangle([W - 330, 540, W - 170, 600], 14, fill=ORANGE + (int(255 * a),))
    dl.text((W - 250, 570), "DEMO", font=F("Black", 34), fill=(20, 20, 20, int(255 * a)), anchor="mm")
    img.alpha_composite(lay)
    fade_in(img, t)
    return img

def s7(t):  # CTA 30-32.5
    img = base()
    k = ease(t / 0.4)
    d = ImageDraw.Draw(img)
    s = int(200 * (0.7 + 0.3 * k))
    d.rounded_rectangle([W // 2 - s // 2, 520, W // 2 + s // 2, 520 + s], 40, fill=BLUE)
    overlay_text(img, 520 + s // 2 - 80, "P", F("Black", 150), WHITE, k)
    overlay_text(img, 800, "PACAR", F("Black", 120), WHITE, k)
    a, dy = pop(t, 0.5)
    overlay_text(img, 1000, "Next: carbon, wraps or wheels?", F("Bold", 54), WHITE, a, dy)
    a, dy = pop(t, 0.9)
    card(img, 190, 1120 + dy, W - 190, 1250 + dy, a, border=BLUE, fill=BLUE)
    overlay_text(img, 1148, "Comment + Subscribe", F("ExtraBold", 54), WHITE, a, dy)
    fade_in(img, t)
    return img

SCENES = [(s1, 3.5), (s2, 6.5), (s3, 7.0), (s4, 5.0), (s5, 4.0), (s6, 4.0), (s7, 2.5)]
STILL_T = [2.5, 4.5, 5.0, 2.5, 2.5, 3.0, 2.0]

def render_scene(i):
    fn, dur = SCENES[i]
    final, tmp = f"{OUT}/scene{i}.mp4", f"{OUT}/scene{i}.tmp.mp4"
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                          "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-crf", "18",
                          "-preset", "veryfast", "-pix_fmt", "yuv420p", tmp], stdin=subprocess.PIPE)
    for f in range(int(round(dur * FPS))):
        p.stdin.write(fn(f / FPS).convert("RGB").tobytes())
    p.stdin.close()
    if p.wait() == 0:
        os.replace(tmp, final)

if __name__ == "__main__":
    if sys.argv[1] == "stills":
        for i, (fn, _) in enumerate(SCENES):
            fn(STILL_T[i]).convert("RGB").save(f"{OUT}/still{i}.jpg", quality=85)
        ims = [Image.open(f"{OUT}/still{i}.jpg").resize((360, 640)) for i in range(7)]
        c = Image.new("RGB", (1440, 1280), "white")
        for i, im in enumerate(ims): c.paste(im, ((i % 4) * 360, (i // 4) * 640))
        c.save(f"{OUT}/sheet.jpg")
    else:
        for i in [int(x) for x in sys.argv[1:]]:
            render_scene(i)
