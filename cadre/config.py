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
ICLOUD_FILE = os.path.join(DATA_DIR, "icloud.json")
PLACES_FILE = os.path.join(DATA_DIR, "places.json")
MESSAGE_FILE = os.path.join(DATA_DIR, "message.json")  # message affiché sur le cadre
FLAGS_FILE = os.path.join(DATA_DIR, "flags.json")      # photos favorites et masquées
WEATHER_FILE = os.path.join(DATA_DIR, "weather.json")  # ville et dernière météo relevée
UPDATE_URL_FILE = os.path.join(DATA_DIR, "update-url.txt")  # adresse des mises à jour
# Adresse proposée par défaut : dernière « release » du dépôt public (docs/mise-a-jour.md).
UPDATE_URL_DEFAULT = ("https://github.com/54yhbw7nfw-spec/cadre-photo/releases/latest/"
                      "download/cadre-maj.cadre")  # lieu de chaque photo (ville, pays)  # album iCloud suivi et ses photos
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
            "show_date": True, "show_place": False, "memories": True, "highlight_new": True,
            "sleep": False, "sleep_start": "23:00", "sleep_end": "07:00",
            "source": "all", "period_from": "", "period_to": "", "show_clock": False,
            "show_weather": False, "language": "fr"}
LANGUAGES = ("fr", "en", "es", "de", "pt", "ro", "zh")  # langue des écrans du cadre (i18n.LANGS)
SOURCES = ("all", "icloud", "uploads", "favorites")  # photos affichées par le diaporama
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
    for key in ("shuffle", "keep_originals", "show_date", "show_place", "memories",
                "highlight_new", "sleep", "show_clock", "show_weather"):
        if isinstance(raw.get(key), bool):
            s[key] = raw[key]
    for key in ("sleep_start", "sleep_end"):
        if isinstance(raw.get(key), str) and TIME_RE.match(raw[key]):
            s[key] = raw[key]
    if raw.get("language") in LANGUAGES:
        s["language"] = raw["language"]
    if raw.get("source") in SOURCES:
        s["source"] = raw["source"]
    for key in ("period_from", "period_to"):
        if isinstance(raw.get(key), str) and (raw[key] == "" or DATE_RE.match(raw[key])):
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


MESSAGE_MAX = 140
MESSAGE_MODES = ("banner", "screen")  # bandeau sur les photos, ou écran entre les photos
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def validate_message(raw):
    """Message de la famille : texte (vide = aucun), dates de début et de fin incluses
    (AAAA-MM-JJ, vide = tout de suite / sans fin), mode d'affichage."""
    text = " ".join(str(raw.get("text", "")).split())[:MESSAGE_MAX]
    since, until = str(raw.get("since", "")), str(raw.get("until", ""))
    return {"text": text, "since": since if DATE_RE.match(since) else "",
            "until": until if DATE_RE.match(until) else "",
            "mode": raw.get("mode") if raw.get("mode") in MESSAGE_MODES else "banner"}


def load_message():
    try:
        with open(MESSAGE_FILE) as f:
            return validate_message(json.load(f))
    except (OSError, ValueError):
        return validate_message({})


def save_message(message):
    atomic_write_json(MESSAGE_FILE, validate_message(message))


def load_flags():
    """{"favorites": [...], "hidden": [...]} : noms de photos."""
    try:
        with open(FLAGS_FILE) as f:
            data = json.load(f)
        return {k: [n for n in data.get(k, []) if isinstance(n, str)]
                for k in ("favorites", "hidden")}
    except (OSError, ValueError, AttributeError):
        return {"favorites": [], "hidden": []}


def set_flag(name, kind, on):
    flags = load_flags()
    names = set(flags[kind])
    names.add(name) if on else names.discard(name)
    flags[kind] = sorted(names)
    atomic_write_json(FLAGS_FILE, flags)


def forget_flags(name):
    flags = load_flags()
    if any(name in v for v in flags.values()):
        atomic_write_json(FLAGS_FILE, {k: [n for n in v if n != name] for k, v in flags.items()})


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
