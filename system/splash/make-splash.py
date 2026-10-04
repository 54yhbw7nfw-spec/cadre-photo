"""Image de démarrage affichée par le noyau (rpi-splash-screen-support) : TGA 24 bits,
1280x720, moins de 224 couleurs. Mêmes couleurs et police que les écrans du diaporama.

Usage (sur le Pi) : python3 make-splash.py <sortie.tga>
"""
import importlib.util
import os
import sys

from PIL import Image, ImageDraw, ImageFont

W, H = 1280, 720
BG = (18, 18, 20)
TEXT = (235, 235, 235)
MUTED = (160, 160, 165)
ACCENT = (110, 170, 255)


def font(size):
    # Police de pygame (celle du diaporama), trouvée sans importer pygame (lent sur le Pi).
    spec = importlib.util.find_spec("pygame")
    path = os.path.join(os.path.dirname(spec.origin), "freesansbold.ttf")
    return ImageFont.truetype(path, size)


def main(out):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    # Petit cadre photo stylisé au-dessus du titre.
    fw, fh, cy = 180, 120, H // 2 - 130
    box = (W // 2 - fw // 2, cy - fh // 2, W // 2 + fw // 2, cy + fh // 2)
    d.rounded_rectangle(box, radius=10, outline=ACCENT, width=8)
    x0, y0, x1, y1 = box[0] + 24, box[1] + 24, box[2] - 24, box[3] - 24
    d.polygon([(x0, y1), (x0 + 45, y0 + 30), (x0 + 80, y1 - 20), (x0 + 105, y0 + 45), (x1, y1)],
              fill=ACCENT)
    d.ellipse((x1 - 30, y0, x1 - 6, y0 + 24), fill=ACCENT)
    d.text((W // 2, H // 2 + 20), "Cadre photo", font=font(72), fill=TEXT, anchor="mm")
    d.text((W // 2, H // 2 + 95), "Démarrage...", font=font(36), fill=MUTED, anchor="mm")
    # Moins de 224 couleurs (exigence du noyau) ; reste en TGA 24 bits.
    img = img.quantize(colors=200).convert("RGB")
    img.save(out, format="TGA")


if __name__ == "__main__":
    main(sys.argv[1])
