"""Diaporama plein écran : pygame + SDL2 (KMSDRM), rendu par textures GPU.

Chaque photo est décodée une fois, composée en 1280x720 (letterbox) puis envoyée
au GPU ; les transitions ne font que déplacer / mélanger des textures, ce qui
laisse le CPU du Pi Zero quasiment libre.
"""
import logging
import os
import random
import signal
import socket
import time

os.environ.setdefault("SDL_VIDEODRIVER", "kmsdrm")
os.environ.setdefault("SDL_RENDER_DRIVER", "opengles2")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame  # noqa: E402
import qrcode  # noqa: E402
from pygame._sdl2.video import Renderer, Texture, Window  # noqa: E402
from PIL import Image, ImageOps  # noqa: E402

from . import config  # noqa: E402

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


class Playlist:
    """File de lecture ; les photos nouvellement ajoutées passent en tête."""

    def __init__(self):
        self.known = set()
        self.bad = set()  # illisibles : ignorés tant que le fichier existe
        self.queue = []
        self.last = None
        self.shuffle = True

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
                random.shuffle(self.queue)
                if len(self.queue) > 1 and self.queue[0] == self.last:
                    self.queue.append(self.queue.pop(0))
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

    def show(self, tex):
        self.renderer.clear()
        tex.draw()
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

        Un QR code s'affiche QR_TIME secondes à chaque nouvelle situation (connecté à une
        adresse, ou hotspot), puis le diaporama reprend même si rien n'a été fait.
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
            if time.monotonic() >= self.qr_until:
                return None
            if mode == "hotspot":
                return key, lambda: self.hotspot_texture(state)
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
            r.present()
            frames += 1
        new.alpha = 255
        self.show(new)
        elapsed = time.monotonic() - start
        log.info("Transition %s : %d images en %.2f s (%.1f i/s)",
                 kind, frames, elapsed, frames / elapsed)

    def prepare(self, name):
        """Charge une photo et crée sa texture ; None si le fichier est illisible."""
        path = os.path.join(config.PHOTOS_DIR, name)
        t0 = time.monotonic()
        try:
            surf = load_photo(path)
        except (OSError, ValueError, Image.DecompressionBombError) as exc:
            log.warning("Photo ignorée %s : %s", name, exc)
            return None
        t1 = time.monotonic()
        tex = self.texture(surf)
        log.info("Photo %s : décodage %d ms, envoi GPU %d ms",
                 name, (t1 - t0) * 1000, (time.monotonic() - t1) * 1000)
        return tex

    def run(self):
        settings = config.load_settings()
        playlist = Playlist()
        playlist.update(config.list_photos(), settings["shuffle"])
        settings_mtime = photos_mtime = None
        current = None
        upcoming = None  # (nom, texture) préchargée pendant l'affichage fixe
        placeholder = None
        next_check = 0.0
        state, state_mtime = {}, None
        screen_key = None  # écran réseau affiché (QR code, connexion...)

        while self.running:
            now = time.monotonic()
            if now >= next_check:
                next_check = now + CHECK_INTERVAL
                m = mtime(config.SETTINGS_FILE)
                if m != settings_mtime:
                    settings_mtime = m
                    settings = config.load_settings()
                    playlist.update(config.list_photos(), settings["shuffle"])
                    log.info("Réglages : %s", settings)
                m = mtime(config.STATE_FILE)
                if m != state_mtime:
                    state_mtime = m
                    state = config.load_state()
                m = mtime(config.PHOTOS_DIR)
                if m != photos_mtime:
                    photos_mtime = m
                    playlist.update(config.list_photos(), settings["shuffle"])
                    if upcoming and upcoming[0] not in playlist.known:
                        upcoming = None

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
                name = playlist.next()
                if name is None:
                    if placeholder is None:
                        placeholder = self.message_texture(
                            ["Aucune photo",
                             f"Ajoutez-en sur http://{socket.gethostname()}.local"])
                        self.transition(current, placeholder, "fade")
                        current = placeholder
                    self.idle(POLL_INTERVAL)
                    continue
                tex = self.prepare(name)
                if tex is None:
                    playlist.forget(name)
                    next_check = 0.0  # fichier supprimé ? relire le dossier tout de suite
                    continue
                upcoming = (name, tex)

            if current is None or current is placeholder or time.monotonic() >= self.due_at:
                self.transition(current, upcoming[1], settings["transition"])
                current = upcoming[1]
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
