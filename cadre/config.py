"""Chemins et réglages partagés par le diaporama, l'admin web et le service réseau."""
import json
import os
import re
import tempfile

DATA_DIR = os.environ.get("CADRE_DATA", "/var/lib/cadre")
PHOTOS_DIR = os.path.join(DATA_DIR, "photos")
THUMBS_DIR = os.path.join(DATA_DIR, "thumbs")
ORIGINALS_DIR = os.path.join(DATA_DIR, "originals")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
AUTH_FILE = os.path.join(DATA_DIR, "auth.json")
ICLOUD_FILE = os.path.join(DATA_DIR, "icloud.json")  # album iCloud suivi et ses photos
RUN_DIR = os.environ.get("CADRE_RUN", "/run/cadre")
STATE_FILE = os.path.join(RUN_DIR, "state.json")  # état réseau publié par cadre-net
NET_SOCKET = os.path.join(RUN_DIR, "net.sock")     # commandes Wi-Fi envoyées à cadre-net
# Fichiers reçus en attente de traitement : en RAM (tmpfs) pour épargner la carte SD.
INCOMING_DIR = os.environ.get("CADRE_INCOMING", "/run/cadre-web/incoming")

SCREEN_SIZE = (1280, 720)
THUMB_SIZE = (320, 180)
PHOTO_EXT = ".jpg"

TRANSITIONS = ("fade", "slide_left", "slide_right", "slide_up", "slide_down", "wipe", "none")
DEFAULTS = {"transition": "random", "delay": 10, "shuffle": True, "keep_originals": False,
            "show_date": True, "sleep": False, "sleep_start": "23:00", "sleep_end": "07:00"}
TIME_RE = re.compile(r"^([01][0-9]|2[0-3]):[0-5][0-9]$")


def atomic_write_json(path, data):
    """Écrit via un fichier temporaire + rename : un lecteur ne voit jamais un JSON partiel."""
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".tmp-")
    try:
        os.fchmod(fd, 0o644)  # mkstemp crée en 0600 : les autres services doivent pouvoir lire
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise


def validate_settings(raw):
    s = dict(DEFAULTS)
    if raw.get("transition") in TRANSITIONS + ("random",):
        s["transition"] = raw["transition"]
    try:
        s["delay"] = max(2, min(3600, int(raw.get("delay", s["delay"]))))
    except (TypeError, ValueError):
        pass
    for key in ("shuffle", "keep_originals", "show_date", "sleep"):
        if isinstance(raw.get(key), bool):
            s[key] = raw[key]
    for key in ("sleep_start", "sleep_end"):
        if isinstance(raw.get(key), str) and TIME_RE.match(raw[key]):
            s[key] = raw[key]
    return s


def load_settings():
    try:
        with open(SETTINGS_FILE) as f:
            return validate_settings(json.load(f))
    except (OSError, ValueError):
        return dict(DEFAULTS)


def save_settings(settings):
    atomic_write_json(SETTINGS_FILE, validate_settings(settings))


def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def list_photos():
    try:
        return sorted(n for n in os.listdir(PHOTOS_DIR)
                      if n.endswith(PHOTO_EXT) and not n.startswith("."))
    except FileNotFoundError:
        return []
