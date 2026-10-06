"""Photos de démonstration (paysages stylisés) pour les captures du mode d'emploi vidéo.

Usage : python tools/video/make_demo_photos.py build/demo
Chaque image porte une date de prise de vue EXIF (ordre chronologique dans le cadre).
"""
import os
import random
import sys
from datetime import datetime, timedelta

from PIL import Image, ImageDraw, ImageFilter

W, H = 2400, 1600
EXIF_DATETIME_ORIGINAL = 0x9003
EXIF_IFD = 0x8769

# (nom, ciel haut, ciel bas, soleil, plans du fond vers l'avant)
SCENES = [
    ("coucher-de-soleil", (40, 30, 90), (250, 140, 70), (255, 220, 120),
     [(120, 60, 90), (80, 40, 70), (40, 25, 45)]),
    ("montagne", (70, 130, 200), (190, 220, 245), (255, 250, 220),
     [(140, 160, 190), (90, 110, 140), (50, 80, 70)]),
    ("mer", (90, 160, 220), (210, 235, 250), (255, 255, 230),
     [(40, 110, 170), (30, 90, 150), (230, 210, 160)]),
    ("foret", (120, 180, 220), (225, 240, 230), (255, 245, 200),
     [(80, 130, 90), (50, 100, 60), (30, 70, 40)]),
    ("aube", (60, 70, 130), (240, 180, 170), (255, 235, 200),
     [(150, 120, 150), (100, 80, 120), (60, 50, 80)]),
    ("desert", (120, 170, 230), (245, 220, 180), (255, 250, 210),
     [(220, 170, 110), (200, 140, 80), (170, 110, 60)]),
    ("lac", (100, 150, 210), (220, 235, 245), (255, 250, 230),
     [(110, 140, 160), (70, 120, 100), (60, 120, 160)]),
    ("automne", (130, 170, 210), (240, 220, 190), (255, 240, 200),
     [(190, 120, 60), (160, 80, 40), (110, 60, 30)]),
    ("nuit", (10, 15, 40), (40, 50, 100), (240, 240, 255),
     [(30, 35, 70), (20, 25, 50), (10, 12, 30)]),
    ("prairie", (110, 170, 230), (230, 240, 250), (255, 250, 220),
     [(130, 170, 110), (100, 150, 80), (70, 120, 50)]),
    ("neige", (150, 180, 220), (240, 245, 250), (255, 255, 240),
     [(200, 210, 230), (170, 185, 210), (235, 240, 248)]),
    ("crepuscule", (30, 40, 80), (200, 110, 120), (255, 200, 150),
     [(90, 60, 100), (60, 40, 80), (30, 20, 50)]),
]


def lerp(a, b, t):
    return tuple(int(x + (y - x) * t) for x, y in zip(a, b))


def scene(rng, top, bottom, sun, layers):
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    for y in range(H):
        d.line([(0, y), (W, y)], fill=lerp(top, bottom, y / H))
    sx, sy, r = rng.randint(500, W - 500), rng.randint(250, 650), rng.randint(90, 150)
    glow = Image.new("L", (W, H), 0)
    ImageDraw.Draw(glow).ellipse((sx - 3 * r, sy - 3 * r, sx + 3 * r, sy + 3 * r), fill=110)
    img.paste(Image.new("RGB", (W, H), sun), mask=glow.filter(ImageFilter.GaussianBlur(120)))
    d.ellipse((sx - r, sy - r, sx + r, sy + r), fill=sun)
    for i, color in enumerate(layers):
        base = int(H * (0.55 + 0.13 * i))
        amp, step = rng.randint(80, 220) // (i + 1), rng.randint(140, 320)
        pts, x, y = [(0, H)], 0, base
        while x <= W + step:
            pts.append((x, y))
            x += step
            y = max(int(H * 0.35), min(H - 60, base + rng.randint(-amp, amp)))
        pts.append((W, H))
        d.polygon(pts, fill=color)
    return img.filter(ImageFilter.GaussianBlur(1.2))


def main(out):
    os.makedirs(out, exist_ok=True)
    rng = random.Random(42)
    date = datetime(2025, 4, 12, 10, 30)
    for i, (name, *colors) in enumerate(SCENES):
        img = scene(rng, *colors)
        exif = Image.Exif()
        exif.get_ifd(EXIF_IFD)[EXIF_DATETIME_ORIGINAL] = date.strftime("%Y:%m:%d %H:%M:%S")
        img.save(os.path.join(out, f"{i + 1:02d}_{name}.jpg"), quality=90, exif=exif)
        date += timedelta(days=rng.randint(12, 60), hours=rng.randint(0, 8))
    print(f"{len(SCENES)} photos dans {out}")


if __name__ == "__main__":
    main(sys.argv[1])
