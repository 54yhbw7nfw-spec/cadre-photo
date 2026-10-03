"""Génère des photos de test synthétiques dans le dossier indiqué.

Usage :
  python tools/make_test_photos.py build/testphotos              tailles et orientations variées
  python tools/make_test_photos.py build/realistic --realistic   20 photos 12 Mpx bruitées (~3 Mo),
                                                                 date EXIF, 1 sur 5 avec rotation EXIF
"""
import colorsys
import os
import random
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


def realistic(out, count=20):
    """Photos proches d'un smartphone : le bruit les rend aussi lourdes et lentes à décoder."""
    os.makedirs(out, exist_ok=True)
    rnd = random.Random(1)
    for i in range(count):
        w, h = (4032, 3024) if i % 4 else (3024, 4032)
        base = Image.radial_gradient("L").resize((w, h)).convert("RGB")
        color = Image.new("RGB", (w, h), tuple(rnd.randrange(256) for _ in range(3)))
        im = Image.blend(base, color, 0.6)
        noise = Image.effect_noise((w // 2, h // 2), 40).resize((w, h)).convert("RGB")
        im = Image.blend(im, noise, 0.25)
        ImageDraw.Draw(im).text((w // 2, h // 2), f"IMG_{i:04d}", fill="white",
                                font=ImageFont.load_default(size=w // 12), anchor="mm")
        exif = Image.Exif()
        exif.get_ifd(0x8769)[0x9003] = f"2025:{1 + i % 9:02d}:{1 + i:02d} 12:00:00"
        if i % 5 == 0:
            im = im.rotate(90, expand=True)
            exif[0x0112] = 6
        im.save(os.path.join(out, f"IMG_{i:04d}.jpg"), quality=92, exif=exif)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--realistic" in sys.argv:
        realistic(args[0] if args else "build/realistic")
    else:
        main(args[0] if args else "build/testphotos")
