"""Génère des photos de test synthétiques (tailles, orientations, EXIF) dans le dossier indiqué.

Usage : python tools/make_test_photos.py build/testphotos
"""
import colorsys
import os
import sys

from PIL import Image, ImageDraw, ImageFont

SPECS = [
    ("01_paysage_720p", 1280, 720),
    ("02_portrait", 720, 1280),
    ("03_carre", 1000, 1000),
    ("04_large_4000x3000", 4000, 3000),
    ("06_panorama", 1280, 400),
    ("07_petit", 640, 480),
    ("08_paysage_1080p", 1920, 1080),
]


def gradient(i, w, h, label):
    im = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(im)
    for y in range(0, h, 4):
        r, g, b = colorsys.hsv_to_rgb((i / 8 + y / h * 0.3) % 1, 0.6, 0.9)
        d.rectangle([0, y, w, y + 4], fill=(int(r * 255), int(g * 255), int(b * 255)))
    d.rectangle([0, 0, w - 1, h - 1], outline="white", width=max(4, w // 200))
    font = ImageFont.load_default(size=max(24, min(w, h) // 10))
    d.text((w // 2, h // 2), label, fill="black", font=font, anchor="mm", align="center")
    return im


def main(out):
    os.makedirs(out, exist_ok=True)
    for i, (name, w, h) in enumerate(SPECS):
        gradient(i, w, h, name).save(os.path.join(out, name + ".jpg"), quality=90)
    # Stockée couchée avec Orientation=6 : le texte doit apparaître droit une fois corrigée.
    im = gradient(4, 4000, 3000, "05_exif_rot90\n(texte doit etre droit)").rotate(90, expand=True)
    exif = Image.Exif()
    exif[0x0112] = 6
    im.save(os.path.join(out, "05_exif_rot90.jpg"), quality=90, exif=exif)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "build/testphotos")
