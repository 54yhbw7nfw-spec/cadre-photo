"""Diaporama plein écran : pygame + SDL2 (KMSDRM), rendu par textures GPU.

Chaque photo est décodée une fois, composée en 1280x720 (letterbox) puis envoyée
au GPU ; les transitions ne font que déplacer / mélanger des textures, ce qui
laisse le CPU du Pi Zero quasiment libre.
"""
import glob
import math
import json
import logging
import os
import queue
import random
import signal
import socket
import struct
import subprocess
import threading
import time
from datetime import datetime

os.environ.setdefault("SDL_VIDEODRIVER", "kmsdrm")
os.environ.setdefault("SDL_RENDER_DRIVER", "opengles2")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame  # noqa: E402
import qrcode  # noqa: E402
from pygame._sdl2.video import Renderer, Texture, Window  # noqa: E402
from PIL import Image, ImageOps  # noqa: E402

from . import config, places, weather  # noqa: E402

log = logging.getLogger("cadre.display")

W, H = config.SCREEN_SIZE
TRANSITION_TIME = 1.0  # secondes
POLL_INTERVAL = 0.25   # pendant l'affichage fixe
CHECK_INTERVAL = 2.0   # surveillance réglages / dossier photos
BLEND = 1              # SDL_BLENDMODE_BLEND
QR_TIME = 30           # secondes d'affichage d'un QR code, puis diaporama dans tous les cas
BG = (18, 18, 20)
TEXT = (235, 235, 235)
MUTED = (160, 160, 165)
ACCENT = (110, 170, 255)
MONTHS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre",
          "octobre", "novembre", "décembre")
SLEEP_CHECK = 5.0  # secondes entre deux vérifications pendant la veille
MESSAGE_EVERY = 5  # mode « écran » : une carte toutes les N photos
MEMORY_EVERY = 4   # « Ce jour-là » : un souvenir toutes les N photos
NEW_FOR = 24 * 3600  # « Nouveau » : photo arrivée depuis moins de 24 h


def years_ago(name, today=None):
    """Nombre d'années si la photo a été prise un jour comme aujourd'hui, une année passée."""
    try:
        d = datetime.strptime(name[:8], "%Y%m%d")
    except ValueError:
        return 0
    today = today or datetime.now()
    if (d.month, d.day) == (today.month, today.day) and d.year < today.year:
        return today.year - d.year
    return 0


def select_photos(names, settings, flags, icloud):
    """Photos à faire défiler : sans les masquées, selon la source et la période choisies."""
    hidden, fav = set(flags["hidden"]), set(flags["favorites"])
    start = settings["period_from"].replace("-", "")
    end = settings["period_to"].replace("-", "")
    source = settings["source"]
    keep = []
    for n in names:
        if n in hidden or (start and n[:8] < start) or (end and n[:8] > end):
            continue
        if ((source == "icloud" and n not in icloud) or (source == "uploads" and n in icloud)
                or (source == "favorites" and n not in fav)):
            continue
        keep.append(n)
    return keep


def weather_icon(kind, day, size=40):
    """Icône météo dessinée (pas de symboles dans la police) : tracée 4 fois plus grande puis
    réduite avec lissage."""
    k = 4
    s = pygame.Surface((size * k, size * k), pygame.SRCALPHA)
    u = size * k / 34  # unité : icône dessinée sur une grille de 34

    def p(x, y):
        return int(x * u), int(y * u)

    def sun(cx, cy, r):
        for i in range(8):
            a = i * math.pi / 4
            pygame.draw.line(s, (255, 200, 60), p(cx + math.cos(a) * r * 1.35, cy + math.sin(a) * r * 1.35),
                             p(cx + math.cos(a) * r * 1.9, cy + math.sin(a) * r * 1.9), int(2.2 * u))
        pygame.draw.circle(s, (255, 200, 60), p(cx, cy), int(r * u))

    def moon(cx, cy, r):
        pygame.draw.circle(s, (235, 235, 215), p(cx, cy), int(r * u))
        pygame.draw.circle(s, (0, 0, 0, 0), p(cx + r * 0.55, cy - r * 0.35), int(r * 0.85 * u))

    def cloud(color, dy=0):
        for cx, cy, r in ((11, 19, 6), (18, 15, 8), (25, 19, 6)):
            pygame.draw.circle(s, color, p(cx, cy + dy), int(r * u))
        pygame.draw.rect(s, color, (*p(11, 19 + dy), int(14 * u), int(6 * u)))

    light = (225, 230, 240)
    if kind == "clear":
        (sun if day else moon)(17, 17, 7)
    elif kind == "partly":
        (sun if day else moon)(22, 11, 5)
        cloud(light, 3)
    elif kind == "cloudy":
        cloud(light, 1)
    elif kind == "fog":
        for y in (12, 18, 24):
            pygame.draw.line(s, (200, 205, 215), p(6, y), p(28, y), int(3 * u))
    elif kind in ("rain", "snow", "storm"):
        cloud((150, 155, 170) if kind == "storm" else light, -4)
        if kind == "rain":
            for x in (12, 18, 24):
                pygame.draw.line(s, (110, 170, 255), p(x, 24), p(x - 2, 30), int(2.4 * u))
        elif kind == "snow":
            for x, y in ((12, 26), (18, 29), (24, 26)):
                pygame.draw.circle(s, (255, 255, 255), p(x, y), int(1.8 * u))
        else:
            pygame.draw.polygon(s, (255, 200, 60), [p(19, 20), p(13, 28), p(17, 28), p(15, 34),
                                                     p(23, 25), p(19, 25), p(21, 20)])
    return pygame.transform.smoothscale(s, (size, size))


def load_icloud_names():
    try:
        with open(config.ICLOUD_FILE) as f:
            return set(json.load(f).get("photos", {}).values())
    except (OSError, ValueError):
        return set()


def recent_photos(names):
    """Photos arrivées sur le cadre (fichier créé) depuis moins de NEW_FOR secondes."""
    limit = time.time() - NEW_FOR
    recent = set()
    for n in names:
        try:
            if os.stat(os.path.join(config.PHOTOS_DIR, n)).st_mtime >= limit:
                recent.add(n)
        except OSError:
            pass
    return recent


def message_active(msg, today=None):
    """Texte du message s'il est à afficher aujourd'hui, sinon None."""
    today = (today or datetime.now()).strftime("%Y-%m-%d")
    if msg["text"] and (not msg["until"] or today <= msg["until"]):
        return msg["text"]
    return None


def wrap(font, text, width):
    """Découpe text en lignes tenant dans width pixels avec cette police."""
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if line and font.size(trial)[0] > width:
            lines.append(line)
            line = word
        else:
            line = trial
    return lines + ([line] if line else [])


def photo_date(name):
    """« 26 septembre 2026 » d'après le nom AAAAMMJJ-HHMMSS_… (date de prise de vue)."""
    try:
        d = datetime.strptime(name[:15], "%Y%m%d-%H%M%S")
    except ValueError:
        return None
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


def in_sleep_window(settings, now=None):
    if not settings["sleep"]:
        return False
    now = (now or datetime.now()).strftime("%H:%M")
    start, end = settings["sleep_start"], settings["sleep_end"]
    if start == end:
        return False
    return start <= now < end if start < end else now >= start or now < end


def cec_run(*args):
    try:
        return subprocess.run(["cec-ctl", "-d0", *args], capture_output=True, text=True,
                              timeout=15).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def cec(*args):
    """Commande HDMI-CEC vers la télé, en tâche de fond (sans effet sur un écran sans CEC)."""
    threading.Thread(target=cec_run, args=args, daemon=True).start()


def cec_active_source(wake=False):
    """Se déclare source active (la télé envoie alors au cadre les touches de sa télécommande) ;
    wake : rallume d'abord la télé. En tâche de fond."""
    def run():
        if wake:
            cec_run("--to", "0", "--image-view-on")
        out = cec_run("--playback", "--osd-name", "Cadre photo")
        for line in out.splitlines():
            if "Physical Address" in line:
                addr = line.split(":", 1)[1].strip()
                if addr != "f.f.f.f":  # pas de télé CEC
                    cec_run("--to", "15", "--active-source", f"phys-addr={addr}")
    threading.Thread(target=run, daemon=True).start()


# Télécommande de la télé : le noyau traduit les touches HDMI-CEC en événements clavier sur ce
# périphérique. Testé sur une Samsung : OK, flèches et retour transmis, pas les couleurs.
# Périphérique trouvé via le récepteur CEC (/sys/class/rc) : le lien by-path « hdmi-event »
# désigne la prise audio HDMI, pas la télécommande.
REMOTE_GLOB = "/sys/class/rc/rc*/input*/event*"
INPUT_EVENT = struct.Struct("IIHHi")  # struct input_event 32 bits : sec, usec, type, code, value
EV_KEY = 1
KEY_UP, KEY_LEFT, KEY_RIGHT, KEY_DOWN = 103, 105, 106, 108
KEY_PAUSE, KEY_BACK, KEY_PLAYPAUSE, KEY_EXIT, KEY_PLAY = 119, 158, 164, 174, 207
KEY_OK, KEY_SELECT = 352, 353
PAUSE_KEYS = (KEY_UP, KEY_DOWN, KEY_PAUSE, KEY_PLAYPAUSE, KEY_PLAY)


def read_remote(keys):
    """Thread : met dans la file keys le code de chaque touche appuyée (sans les répétitions)."""
    while True:
        paths = ["/dev/input/" + os.path.basename(p) for p in glob.glob(REMOTE_GLOB)]
        if not paths:
            time.sleep(30)  # pas de CEC (ou pas encore) : on réessaie de temps en temps
            continue
        try:
            with open(paths[0], "rb", buffering=0) as f:
                while data := f.read(INPUT_EVENT.size):
                    _, _, kind, code, value = INPUT_EVENT.unpack(data)
                    if kind == EV_KEY and value == 1:
                        keys.put(code)
        except OSError as exc:
            log.warning("Télécommande : %s", exc)
            time.sleep(5)


class Playlist:
    """File de lecture ; les photos nouvellement ajoutées passent en tête."""

    def __init__(self):
        self.known = set()
        self.bad = set()  # illisibles : ignorés tant que le fichier existe
        self.queue = []
        self.last = None
        self.shuffle = True
        self.recent = set()  # nouveautés : en tête de chaque nouveau tour
        self.favorites = set()  # favoris : deux passages par tour (ordre aléatoire)

    def update(self, names, shuffle):
        if shuffle != self.shuffle:
            self.shuffle = shuffle
            self.queue = []
        self.bad &= set(names)
        current = set(names) - self.bad
        new = [n for n in names if n in current and n not in self.known]
        if self.shuffle:
            random.shuffle(new)
        self.queue = new + [n for n in self.queue if n in current]
        self.known = current

    def next(self):
        if not self.known:
            return None
        if not self.queue:
            self.queue = sorted(self.known)
            if self.shuffle:
                self.queue += sorted(self.favorites & self.known)
                random.shuffle(self.queue)
                if len(self.queue) > 1 and self.queue[0] == self.last:
                    self.queue.append(self.queue.pop(0))
            if self.recent:  # tri stable : l'ordre (aléatoire ou non) est gardé dans chaque groupe
                self.queue.sort(key=lambda n: n not in self.recent)
        self.last = self.queue.pop(0)
        return self.last

    def forget(self, name):
        self.bad.add(name)
        self.known.discard(name)
        self.queue = [n for n in self.queue if n != name]


def load_photo(path):
    """Renvoie une Surface de taille <= 1280x720, orientation EXIF appliquée.

    Les photos passées par l'admin web sont déjà prêtes : décodage direct par
    pygame (le plus rapide). Pillow ne sert que pour des fichiers déposés à la
    main, trop grands ou à pivoter.
    """
    with Image.open(path) as im:
        if im.width <= W and im.height <= H and im.getexif().get(0x0112, 1) == 1:
            return pygame.image.load(path)
        im.draft("RGB", (W, H))
        im = ImageOps.exif_transpose(im)
        im.thumbnail((W, H), Image.BILINEAR)
        im = im.convert("RGB")
        return pygame.image.frombuffer(im.tobytes(), im.size, "RGB").copy()


def smoothstep(t):
    return t * t * (3 - 2 * t)


class Display:
    def __init__(self):
        pygame.display.init()
        pygame.font.init()
        # Plein écran exclusif : SDL choisit le mode le plus proche de 1280x720. En « desktop »,
        # il garderait le mode préféré de la télé (souvent 1080p) et mettrait à l'échelle.
        self.window = Window("cadre", size=(W, H), fullscreen=True)
        self.renderer = Renderer(self.window, accelerated=1, vsync=True,
                                 target_texture=True)
        self.renderer.logical_size = (W, H)
        self.renderer.draw_color = (0, 0, 0, 255)
        pygame.mouse.set_visible(False)
        self.running = True
        self.due_at = 0.0
        self.qr_key = None    # QR code déjà montré (mode + adresse) : pas de répétition
        self.qr_until = 0.0
        self.date_font = pygame.font.Font(None, 34)
        self.info_until = 0.0  # QR code de l'admin demandé par la touche OK
        self.corner, self.corner_text = None, None  # heure et météo en bas à gauche
        self.keys = queue.Queue()
        threading.Thread(target=read_remote, args=(self.keys,), daemon=True).start()
        # Le Pi se présente à la télé (CEC) et devient la source active : nécessaire pour la
        # mettre en veille la nuit et pour recevoir les touches de sa télécommande.
        cec_active_source()
        signal.signal(signal.SIGTERM, self._stop)
        signal.signal(signal.SIGINT, self._stop)
        log.info("Affichage %s, sortie %sx%s, rendu logique %sx%s",
                 pygame.display.get_driver(), *self.window.size, W, H)

    def _stop(self, *_):
        self.running = False

    def texture(self, surf):
        """Texture plein écran : la photo est centrée sur fond noir par le GPU."""
        w, h = surf.get_size()
        if (w, h) == (W, H):
            tex = Texture.from_surface(self.renderer, surf)
        else:
            photo = Texture.from_surface(self.renderer, surf)
            tex = Texture(self.renderer, (W, H), target=True)
            self.renderer.target = tex
            self.renderer.clear()
            photo.draw(dstrect=((W - w) // 2, (H - h) // 2, w, h))
            self.renderer.target = None
        tex.blend_mode = BLEND
        return tex

    def update_corner(self, show_clock, show_weather, weather_data):
        """Coin bas gauche : heure et/ou icône météo + température, refait quand il change."""
        clock = time.strftime("%H:%M") if show_clock else None
        now = weather.current(weather_data) if show_weather else None
        key = (clock, now)
        if key == self.corner_text:
            return False
        self.corner_text = key
        self.corner = None
        parts = []
        if clock:
            parts.append(self.date_font.render(clock, True, TEXT))
        if now:
            kind, temp, day = now
            parts += [weather_icon(kind, day), self.date_font.render(f"{temp} °C", True, TEXT)]
        if parts:
            gap = 10
            w = sum(p.get_width() for p in parts) + gap * (len(parts) - 1) + 24
            h = max(p.get_height() for p in parts) + 10
            box = pygame.Surface((w, h), pygame.SRCALPHA)
            box.fill((0, 0, 0, 140))
            x = 12
            for part in parts:
                box.blit(part, (x, (h - part.get_height()) // 2))
                x += part.get_width() + gap
            self.corner = (Texture.from_surface(self.renderer, box), box.get_size())
        return True

    def draw_corner(self):
        if self.corner:
            tex, (w, h) = self.corner
            tex.draw(dstrect=(16, H - h - 16, w, h))

    def show(self, tex, badge=None):
        self.renderer.clear()
        tex.draw()
        self.draw_corner()
        if badge:  # petit cartouche en haut à gauche (« Pause »)
            img = self.date_font.render(badge, True, TEXT)
            box = pygame.Surface((img.get_width() + 24, img.get_height() + 12), pygame.SRCALPHA)
            box.fill((0, 0, 0, 160))
            box.blit(img, (12, 6))
            Texture.from_surface(self.renderer, box).draw(dstrect=(16, 16, *box.get_size()))
        self.renderer.present()

    def message_texture(self, lines):
        surf = pygame.Surface((W, H))
        font = pygame.font.Font(None, 64)
        y = H // 2 - len(lines) * 40
        for line in lines:
            img = font.render(line, True, (220, 220, 220))
            surf.blit(img, ((W - img.get_width()) // 2, y))
            y += 80
        return self.texture(surf)

    def qr_texture(self, url, lines):
        """QR code à gauche, texte à droite : lignes = [(texte, taille, couleur), ...]."""
        surf = pygame.Surface((W, H))
        surf.fill(BG)
        qr = qrcode.QRCode(border=0)
        qr.add_data(url)
        qr.make(fit=True)
        matrix = qr.get_matrix()
        n = len(matrix)
        box = 520
        cell = (box - 48) // n
        size = cell * n
        x0, y0 = 90, (H - box) // 2
        pygame.draw.rect(surf, (255, 255, 255), (x0, y0, box, box), border_radius=16)
        ox, oy = x0 + (box - size) // 2, y0 + (box - size) // 2
        for r, row in enumerate(matrix):
            for c, dark in enumerate(row):
                if dark:
                    surf.fill((0, 0, 0), (ox + c * cell, oy + r * cell, cell, cell))
        y = y0 + 30
        for text, size_pt, color in lines:
            if text:
                img = pygame.font.Font(None, size_pt).render(text, True, color)
                surf.blit(img, (x0 + box + 70, y))
            y += int(size_pt * 1.15)
        return self.texture(surf)

    def hotspot_texture(self, state):
        ssid, password, ip = state.get("ap_ssid", ""), state.get("ap_password", ""), state.get("ip")

        def esc(v):  # caractères réservés du format WIFI: des QR codes
            for ch in '\\;,:"':
                v = v.replace(ch, "\\" + ch)
            return v
        return self.qr_texture(f"WIFI:T:WPA;S:{esc(ssid)};P:{esc(password)};;", [
            ("Configuration du Wi-Fi", 66, TEXT),
            ("", 20, TEXT),
            ("1. Scannez le QR code pour rejoindre", 40, MUTED),
            (f"le réseau {ssid}", 40, MUTED),
            (f"mot de passe : {password}", 46, ACCENT),
            ("", 20, TEXT),
            ("2. La page de configuration s'ouvre.", 40, MUTED),
            ("Sinon, allez sur", 40, MUTED),
            (f"http://{ip}", 52, ACCENT),
        ])

    def network_screen(self, state):
        """Écran réseau prioritaire sur le diaporama : (clé, fabrique de texture) ou None.

        Le QR code de l'adresse s'affiche QR_TIME secondes à chaque nouvelle adresse, puis le
        diaporama reprend. L'écran du hotspot reste affiché tant que le hotspot est actif : c'est
        le seul endroit où figure son mot de passe.
        """
        mode = state.get("mode")
        key = None
        if mode == "connected" and state.get("ip"):
            key = ("qr", state["ip"])
        elif mode == "hotspot":
            key = ("hotspot", state.get("ap_ssid"), state.get("ap_password"))
        if key:
            if key != self.qr_key:
                self.qr_key = key
                self.qr_until = time.monotonic() + QR_TIME
            if mode == "hotspot":
                return key, lambda: self.hotspot_texture(state)
            if time.monotonic() >= max(self.qr_until, self.info_until):
                return None
            ip, host = state["ip"], socket.gethostname()
            return key, lambda: self.qr_texture(f"http://{ip}/", [
                ("Cadre photo", 80, TEXT),
                ("", 30, TEXT),
                ("Ajoutez vos photos :", 46, MUTED),
                (f"http://{ip}", 64, ACCENT),
                (f"ou http://{host}.local", 46, MUTED),
                ("", 40, TEXT),
                ("Scannez le QR code", 40, MUTED),
                ("avec votre téléphone", 40, MUTED),
            ])
        if mode in ("reboot", "poweroff"):  # demandé dans l'admin, l'arrêt suit dans 3 s
            lines = ["Redémarrage..."] if mode == "reboot" else [
                "Extinction...", "", "Débranchez le cadre quand", "sa diode verte est éteinte"]
            return (mode,), lambda: self.message_texture(lines)
        if mode == "connecting" and self.qr_key is None:
            # Seulement avant la première connexion : une coupure passagère ne masque pas les photos.
            return ("connecting",), lambda: self.message_texture(["Connexion au Wi-Fi..."])
        return None

    def transition(self, old, new, kind):
        if kind == "random":
            kind = random.choice([t for t in config.TRANSITIONS if t != "none"])
        if old is None or kind == "none":
            self.show(new)
            return
        r = self.renderer
        frames = 0
        start = time.monotonic()
        while self.running:
            t = (time.monotonic() - start) / TRANSITION_TIME
            if t >= 1:
                break
            e = smoothstep(t)
            r.clear()
            if kind == "fade":
                old.draw()
                new.alpha = int(255 * e)
                new.draw()
            elif kind == "wipe":
                old.draw()
                x = int(W * e)
                if x:
                    new.draw(srcrect=(0, 0, x, H), dstrect=(0, 0, x, H))
            else:  # slide_*
                dx, dy = {"slide_left": (-W, 0), "slide_right": (W, 0),
                          "slide_up": (0, -H), "slide_down": (0, H)}[kind]
                ox, oy = int(dx * e), int(dy * e)
                old.draw(dstrect=(ox, oy, W, H))
                new.draw(dstrect=(ox - dx, oy - dy, W, H))
            self.draw_corner()
            r.present()
            frames += 1
        new.alpha = 255
        self.show(new)
        elapsed = time.monotonic() - start
        log.info("Transition %s : %d images en %.2f s (%.1f i/s)",
                 kind, frames, elapsed, frames / elapsed)

    def draw_date(self, surf, name, place=None, show_date=True, prefix=None):
        """Lieu et/ou date de prise de vue en bas à droite de surf, sur un cartouche sombre ;
        prefix : « Il y a 3 ans » pour un souvenir."""
        text = " · ".join(t for t in (prefix, place, photo_date(name) if show_date else None)
                          if t)
        if not text:
            return
        img = self.date_font.render(text, True, TEXT)
        pad = 10
        box = pygame.Surface((img.get_width() + 2 * pad, img.get_height() + pad), pygame.SRCALPHA)
        box.fill((0, 0, 0, 140))
        box.blit(img, (pad, pad // 2))
        surf.blit(box, (surf.get_width() - box.get_width() - 16,
                        surf.get_height() - box.get_height() - 16))

    def draw_banner(self, surf, text):
        """Bandeau en haut de l'écran : le message, sur fond sombre (2 lignes au plus)."""
        font = pygame.font.Font(None, 54)
        lines = wrap(font, text, W - 120)[:2]
        height = 30 + 52 * len(lines)
        band = pygame.Surface((W, height), pygame.SRCALPHA)
        band.fill((0, 0, 0, 170))
        for i, line in enumerate(lines):
            img = font.render(line, True, TEXT)
            band.blit(img, ((W - img.get_width()) // 2, 18 + 52 * i))
        surf.blit(band, (0, 0))
        return height

    def draw_badge(self, surf, text, y=16):
        """Petit cartouche bleu en haut à gauche (« Nouveau »)."""
        img = self.date_font.render(text, True, (255, 255, 255))
        box = pygame.Surface((img.get_width() + 24, img.get_height() + 12), pygame.SRCALPHA)
        box.fill(ACCENT + (230,))
        box.blit(img, (12, 6))
        surf.blit(box, (16, y))

    def message_card(self, text):
        """Écran du message, entre les photos."""
        surf = pygame.Surface((W, H))
        surf.fill(BG)
        font = pygame.font.Font(None, 84)
        lines = wrap(font, text, W - 200)[:5]
        y = (H - 90 * len(lines)) // 2
        pygame.draw.rect(surf, ACCENT, ((W - 120) // 2, y - 60, 120, 8), border_radius=4)
        for line in lines:
            img = font.render(line, True, TEXT)
            surf.blit(img, ((W - img.get_width()) // 2, y))
            y += 90
        return self.texture(surf)

    def prepare(self, name, show_date=False, place=None, banner=None, prefix=None, badge=None):
        """Charge une photo et crée sa texture ; None si le fichier est illisible."""
        path = os.path.join(config.PHOTOS_DIR, name)
        t0 = time.monotonic()
        try:
            surf = load_photo(path)
        except (OSError, ValueError, Image.DecompressionBombError) as exc:
            log.warning("Photo ignorée %s : %s", name, exc)
            return None
        caption = show_date or place or prefix
        if caption or banner or badge:  # composés sur tout l'écran : coins de l'écran, pas de la photo
            screen = pygame.Surface((W, H))
            screen.blit(surf, ((W - surf.get_width()) // 2, (H - surf.get_height()) // 2))
            if caption:
                self.draw_date(screen, name, place, show_date, prefix)
            top = self.draw_banner(screen, banner) if banner else 0
            if badge:
                self.draw_badge(screen, badge, top + 16)
            surf = screen
        t1 = time.monotonic()
        tex = self.texture(surf)
        log.info("Photo %s : décodage %d ms, envoi GPU %d ms",
                 name, (t1 - t0) * 1000, (time.monotonic() - t1) * 1000)
        return tex

    def run(self):
        settings = config.load_settings()
        playlist = Playlist()  # remplie dès le premier tour (sélection : masquées, source…)
        settings_mtime = photos_mtime = places_mtime = message_mtime = None
        flags_mtime = icloud_mtime = weather_mtime = None
        flags, icloud, weather_data = config.load_flags(), set(), {}
        message = config.load_message()
        since_card = 0  # photos montrées depuis la dernière carte du message
        since_memory, memory_day, memories = 0, None, []  # « Ce jour-là »
        selection, all_names = None, []
        photo_places = {}
        current = None
        upcoming = None  # (nom, texture) préchargée pendant l'affichage fixe
        placeholder = None
        next_check = 0.0
        state, state_mtime = {}, None
        screen_key = None  # écran réseau affiché (QR code, connexion...)
        asleep = False
        paused = False
        history = []  # dernières photos affichées, pour la touche ←

        while self.running:
            now = time.monotonic()
            if now >= next_check:
                next_check = now + CHECK_INTERVAL
                m = mtime(config.SETTINGS_FILE)
                if m != settings_mtime:
                    settings_mtime = m
                    settings = config.load_settings()
                    photos_mtime = None  # sélection refaite plus bas (masquées, source, période)
                    log.info("Réglages : %s", settings)
                m = mtime(config.STATE_FILE)
                if m != state_mtime:
                    state_mtime = m
                    state = config.load_state()
                m = mtime(config.MESSAGE_FILE)
                if m != message_mtime:
                    message_mtime = m
                    message = config.load_message()
                    upcoming = None  # la prochaine photo prend le nouveau bandeau
                    since_card = MESSAGE_EVERY  # nouveau message en mode écran : tout de suite
                m = mtime(config.PLACES_FILE)
                if m != places_mtime:
                    places_mtime = m
                    photo_places = places.load()
                reselect = False
                for path, kind in ((config.FLAGS_FILE, "flags"), (config.ICLOUD_FILE, "icloud")):
                    m = mtime(path)
                    if kind == "flags" and m != flags_mtime:
                        flags_mtime, flags, reselect = m, config.load_flags(), True
                    elif kind == "icloud" and m != icloud_mtime:
                        icloud_mtime, icloud, reselect = m, load_icloud_names(), True
                m = mtime(config.WEATHER_FILE)
                if m != weather_mtime:
                    weather_mtime, weather_data = m, weather.load()
                m = mtime(config.PHOTOS_DIR)
                if (m != photos_mtime or memory_day != time.strftime("%Y%m%d") or reselect
                        or selection != (settings["source"], settings["period_from"],
                                         settings["period_to"])):
                    photos_mtime, memory_day = m, time.strftime("%Y%m%d")
                    selection = (settings["source"], settings["period_from"],
                                 settings["period_to"])
                    all_names = config.list_photos()
                    names = select_photos(all_names, settings, flags, icloud)
                    playlist.update(names, settings["shuffle"])
                    playlist.favorites = set(flags["favorites"])
                    playlist.recent = recent_photos(names)
                    memories = [n for n in names if years_ago(n)]
                    random.shuffle(memories)
                    if upcoming and upcoming[0] not in playlist.known:
                        upcoming = None

            if (self.update_corner(settings["show_clock"], settings["show_weather"], weather_data)
                    and current is not None):
                self.show(current, badge="Pause" if paused else None)

            if in_sleep_window(settings):
                if not asleep:
                    asleep = True
                    log.info("Veille jusqu'à %s", settings["sleep_end"])
                    black = Texture(self.renderer, (W, H), target=True)
                    self.renderer.target = black
                    self.renderer.clear()
                    self.renderer.target = None
                    self.transition(current, black, "fade")
                    current, upcoming, screen_key = black, None, None
                    cec("--to", "0", "--standby")
                self.idle(SLEEP_CHECK)
                next_check = 0.0  # réglages relus : la veille peut être désactivée
                continue
            if asleep:
                asleep = False
                log.info("Fin de la veille")
                cec_active_source(wake=True)
                self.due_at = 0.0

            while not self.keys.empty():
                code = self.keys.get()
                now = time.monotonic()
                if code in (KEY_OK, KEY_SELECT):
                    self.info_until = 0.0 if self.info_until > now else now + QR_TIME
                    paused = False
                elif code in (KEY_BACK, KEY_EXIT):
                    self.info_until = 0.0
                elif code == KEY_RIGHT:
                    self.info_until, paused, self.due_at = 0.0, False, 0.0
                elif code == KEY_LEFT and len(history) >= 2:
                    # Précédente, puis de nouveau l'actuelle et celle qui était préparée.
                    back = [history[-2], history[-1]] + ([upcoming[0]] if upcoming else [])
                    playlist.queue[:0] = back
                    del history[-2:]
                    upcoming = None
                    self.info_until, paused, self.due_at = 0.0, False, 0.0
                elif code in PAUSE_KEYS and current is not None and not screen_key:
                    paused = not paused
                    self.show(current, badge="Pause" if paused else None)
                    if not paused:
                        self.due_at = 0.0
                log.info("Télécommande : touche %d", code)

            screen = self.network_screen(state)
            if screen:
                key, build = screen
                if key != screen_key:
                    screen_key = key
                    tex = build()
                    self.transition(current, tex, "fade")
                    current = tex
                    placeholder = None
                self.idle(POLL_INTERVAL)
                continue
            if screen_key:
                screen_key = None
                self.due_at = 0.0  # photo suivante dès la fin de l'écran réseau

            if upcoming is None:
                name = None
                if settings["memories"] and memories and since_memory >= MEMORY_EVERY:
                    name = memories.pop(0)
                    memories.append(name)  # tour des souvenirs du jour
                    since_memory = 0
                else:
                    name = playlist.next()
                    since_memory += 1
                if name is None:
                    if placeholder is None:
                        placeholder = self.message_texture(
                            ["Aucune photo ne correspond à la sélection",
                             "Voir les réglages de la page de gestion"] if all_names else
                            ["Aucune photo",
                             f"Ajoutez-en sur http://{socket.gethostname()}.local"])
                        self.transition(current, placeholder, "fade")
                        current = placeholder
                    self.idle(POLL_INTERVAL)
                    continue
                text = message_active(message)
                ago = years_ago(name) if settings["memories"] else 0
                new = settings["highlight_new"] and name in playlist.recent
                tex = self.prepare(name, settings["show_date"],
                                   photo_places.get(name) if settings["show_place"] else None,
                                   text if message["mode"] == "banner" else None,
                                   f"Il y a {ago} an{'s' if ago > 1 else ''}" if ago else None,
                                   "Nouveau" if new else None)
                if tex is None:
                    playlist.forget(name)
                    next_check = 0.0  # fichier supprimé ? relire le dossier tout de suite
                    continue
                upcoming = (name, tex)

            if (current is None or current is placeholder
                    or (not paused and time.monotonic() >= self.due_at)):
                text = message_active(message)
                if text and message["mode"] == "screen" and since_card >= MESSAGE_EVERY:
                    card = self.message_card(text)
                    self.transition(current, card, "fade")
                    current, since_card = card, 0
                    self.due_at = time.monotonic() + settings["delay"]
                    continue
                since_card += 1
                self.transition(current, upcoming[1], settings["transition"])
                current = upcoming[1]
                history = (history + [upcoming[0]])[-50:]
                upcoming = None
                placeholder = None
                self.due_at = time.monotonic() + settings["delay"]
            else:
                self.idle(POLL_INTERVAL)

    def idle(self, seconds):
        # Rien à redessiner : l'image reste affichée sans présenter de nouvelle frame.
        pygame.event.pump()
        time.sleep(seconds)


def mtime(path):
    try:
        return os.stat(path).st_mtime_ns
    except FileNotFoundError:
        return None


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    os.makedirs(config.PHOTOS_DIR, exist_ok=True)
    try:
        Display().run()
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()
