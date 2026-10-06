"""Préparation des photos reçues : orientation EXIF, réduction à l'écran, miniature.

Nom des fichiers produits : AAAAMMJJ-HHMMSS_<empreinte>.jpg
- la date (prise de vue EXIF, sinon réception) donne l'ordre chronologique du mode non aléatoire ;
- l'empreinte du fichier reçu détecte les doublons et rend les URL immuables (cache navigateur).
"""
import hashlib
import os
import re
import shutil
import tempfile
from datetime import datetime

from PIL import Image, ImageOps

from . import config, places

# Au-delà : refus (bombe de décompression, RAM du Pi).
Image.MAX_IMAGE_PIXELS = 60_000_000

W, H = config.SCREEN_SIZE
TW, TH = config.THUMB_SIZE
EXIF_ORIENTATION = 0x0112
EXIF_IFD = 0x8769
EXIF_DATETIME_ORIGINAL = 0x9003
EXIF_DATETIME = 0x0132
EXIF_GPS = 0x8825
ROTATED_90 = {5, 6, 7, 8}
NAME_RE = re.compile(r"^\d{8}-\d{6}_[0-9a-f]{10}\.jpg$")


class Rejected(Exception):
    """Fichier qui n'est pas une image exploitable."""


def file_digest(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()[:10]


def find_by_digest(digest):
    suffix = f"_{digest}.jpg"
    for name in config.list_photos():
        if name.endswith(suffix):
            return name
    return None


def parse_exif_date(raw):
    try:
        return datetime.strptime(str(raw).strip("\x00 "), "%Y:%m:%d %H:%M:%S")
    except ValueError:
        return None


def read_gps(path):
    """Coordonnées GPS de l'EXIF (lat, lon) ou None. WhatsApp, par exemple, les efface."""
    try:
        with Image.open(path) as im:
            gps = im.getexif().get_ifd(EXIF_GPS)

        def degrees(v):
            d, m, s = (float(x) for x in v)
            return d + m / 60 + s / 3600
        lat = degrees(gps[2]) * (-1 if gps.get(1) == "S" else 1)
        lon = degrees(gps[4]) * (-1 if gps.get(3) == "W" else 1)
        return lat, lon
    except (OSError, KeyError, TypeError, ValueError, ZeroDivisionError):
        return None


def shot_date(exif):
    return parse_exif_date(exif.get_ifd(EXIF_IFD).get(EXIF_DATETIME_ORIGINAL)
                           or exif.get(EXIF_DATETIME))


def save_jpeg_atomic(img, path, quality):
    """Écrit à côté sous un nom caché puis renomme : jamais de fichier partiel visible."""
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".tmp-", suffix=".jpg")
    os.close(fd)
    try:
        img.save(tmp, "JPEG", quality=quality)
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise


def load_for_screen(src):
    """Ouvre, applique l'orientation EXIF et réduit pour tenir dans l'écran."""
    with Image.open(src) as im:
        exif = im.getexif()
        w, h = im.size
        ow, oh = (h, w) if exif.get(EXIF_ORIENTATION) in ROTATED_90 else (w, h)
        fit = min(W / ow, H / oh)
        if im.format == "JPEG" and fit < 1:
            # Décodage JPEG à 1/2, 1/4 ou 1/8 directement : de loin le plus gros gain sur le Pi.
            # Taille arrondie vers le bas : un pixel de trop et draft() renonce à la réduction
            # (1920x1440 -> décodage complet 1,6 s au lieu de 0,28 s).
            im.draft("RGB", (max(1, int(w * fit)), max(1, int(h * fit))))
        img = ImageOps.exif_transpose(im)
        if img.mode != "RGB":
            img = img.convert("RGB")
        img.thumbnail((W, H), Image.LANCZOS)
        return img, shot_date(exif)


def process(src, keep_original=False, original_name="", taken="", sig=""):
    """Traite un fichier reçu ; renvoie (nom, nouveau). Lève Rejected si illisible.

    taken / sig : fournis par le navigateur quand il a réduit la photo avant l'envoi
    (date EXIF de l'original, signature nom|taille|date du fichier pour les doublons).
    """
    digest = hashlib.sha1(sig.encode()).hexdigest()[:10] if sig else file_digest(src)
    existing = find_by_digest(digest)
    if existing:
        return existing, False
    try:
        img, date = load_for_screen(src)
    except (OSError, ValueError, SyntaxError, Image.DecompressionBombError) as exc:
        raise Rejected(f"image illisible ou format non pris en charge ({exc})") from None
    if img.getextrema() == ((0, 0), (0, 0), (0, 0)):
        # Aucune vraie photo n'est noire à 100 % : réduction ratée côté navigateur.
        raise Rejected("image entièrement noire (réduction du navigateur ratée) : "
                       "renvoyer la photo, ou cocher « Conserver les originaux »")
    date = date or parse_exif_date(taken) or datetime.now()
    name = f"{date:%Y%m%d-%H%M%S}_{digest}.jpg"

    thumb = img.copy()
    thumb.thumbnail((TW, TH), Image.BICUBIC, reducing_gap=2.0)
    # Miniature d'abord : la grille de l'admin ne voit jamais une photo sans miniature.
    save_jpeg_atomic(thumb, os.path.join(config.THUMBS_DIR, name), quality=80)
    save_jpeg_atomic(img, os.path.join(config.PHOTOS_DIR, name), quality=90)

    if keep_original:
        ext = os.path.splitext(original_name)[1].lower() or ".bin"
        shutil.move(src, os.path.join(config.ORIGINALS_DIR, name[:-4] + ext))
    return name, True


def delete(name):
    """Supprime une photo, sa miniature, son original éventuel et son lieu. True si trouvée."""
    if not NAME_RE.match(name):
        return False
    places.remove(name)
    found = False
    for path in (os.path.join(config.PHOTOS_DIR, name), os.path.join(config.THUMBS_DIR, name)):
        try:
            os.unlink(path)
            found = True
        except FileNotFoundError:
            pass
    stem = name[:-4]
    try:
        for orig in os.listdir(config.ORIGINALS_DIR):
            if orig.startswith(stem + "."):
                os.unlink(os.path.join(config.ORIGINALS_DIR, orig))
    except FileNotFoundError:
        pass
    return found
