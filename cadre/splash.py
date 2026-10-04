"""Écran de démarrage (service cadre-splash) : image « Cadre photo » et, en bas, les derniers
messages de systemd, dessinés directement dans /dev/fb0 dès que l'écran existe.

Vers 60 s, le pilote vc4 remplace le framebuffer provisoire du firmware (simplefb) : l'image
est alors redessinée. Le service s'arrête de lui-même une fois le diaporama lancé (il occupe
alors l'écran via DRM, nos écritures dans fb0 ne sont plus visibles).
"""
import mmap
import os
import select
import subprocess
import time

from PIL import Image, ImageChops, ImageDraw, ImageFont

FB = "/dev/fb0"
FB_SYS = "/sys/class/graphics/fb0"
DISPLAY_ACTIVE = "/run/systemd/units/invocation:cadre-display.service"
STOP_AFTER_DISPLAY = 20  # s : le diaporama met quelques secondes à afficher sa première image

BG = (18, 18, 20)
TEXT = (235, 235, 235)
MUTED = (160, 160, 165)
DIM = (110, 110, 115)
ACCENT = (110, 170, 255)
LINES = 4
LINE_H = 30
FONT_DIR = "/usr/share/fonts/truetype/freefont"


def font(name, size):
    try:
        return ImageFont.truetype(os.path.join(FONT_DIR, name), size)
    except OSError:
        return ImageFont.load_default()


def read_sys(name):
    with open(os.path.join(FB_SYS, name)) as f:
        return f.read().strip()


def to_fb(img, bpp):
    """Image RGB → octets du framebuffer (RGB565 petit-boutiste ou 32 bits BGRX)."""
    if bpp == 32:
        return img.tobytes("raw", "BGRX")
    # Pillow n'a pas d'encodeur RGB565 : octets fort et faible calculés par canal.
    r, g, b = img.split()
    hi = ImageChops.add(r.point(lambda v: v & 0xF8), g.point(lambda v: v >> 5))
    lo = ImageChops.add(g.point(lambda v: (v & 0x1C) << 3), b.point(lambda v: v >> 3))
    return Image.merge("LA", (lo, hi)).tobytes()


def background(w, h):
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    fw, fh, cy = 180, 120, h // 2 - 130
    box = (w // 2 - fw // 2, cy - fh // 2, w // 2 + fw // 2, cy + fh // 2)
    d.rounded_rectangle(box, radius=10, outline=ACCENT, width=8)
    x0, y0, x1, y1 = box[0] + 24, box[1] + 24, box[2] - 24, box[3] - 24
    d.polygon([(x0, y1), (x0 + 45, y0 + 30), (x0 + 80, y1 - 20), (x0 + 105, y0 + 45), (x1, y1)],
              fill=ACCENT)
    d.ellipse((x1 - 30, y0, x1 - 6, y0 + 24), fill=ACCENT)
    d.text((w // 2, h // 2 + 20), "Cadre photo", font=font("FreeSansBold.ttf", 72), fill=TEXT,
           anchor="mm")
    d.text((w // 2, h // 2 + 95), "Démarrage...", font=font("FreeSansBold.ttf", 36), fill=MUTED,
           anchor="mm")
    return img


class Screen:
    def __init__(self):
        self.name = read_sys("name")
        self.w, self.h = (int(v) for v in read_sys("virtual_size").split(","))
        self.bpp = int(read_sys("bits_per_pixel"))
        self.stride = int(read_sys("stride"))
        self.fd = os.open(FB, os.O_RDWR)
        self.mem = mmap.mmap(self.fd, self.stride * self.h)
        self.font = font("FreeSans.ttf", 22)
        self.strip_y = self.h - 40 - LINES * LINE_H
        self.write(background(self.w, self.h), 0)

    def write(self, img, y):
        data = to_fb(img, self.bpp)
        row = img.width * self.bpp // 8
        if row == self.stride:
            self.mem[y * self.stride:y * self.stride + len(data)] = data
        else:
            for i in range(img.height):
                off = (y + i) * self.stride
                self.mem[off:off + row] = data[i * row:(i + 1) * row]

    def show_lines(self, lines):
        strip = Image.new("RGB", (self.w, LINES * LINE_H), BG)
        d = ImageDraw.Draw(strip)
        for i, line in enumerate(lines[-LINES:]):
            color = MUTED if i == len(lines[-LINES:]) - 1 else DIM
            d.text((self.w // 2, i * LINE_H + LINE_H // 2), line[:110], font=self.font,
                   fill=color, anchor="mm")
        self.write(strip, self.strip_y)

    def close(self):
        self.mem.close()
        os.close(self.fd)


def short(message):
    # « Started foo.service - Description lisible. » → « Started Description lisible »
    head, sep, desc = message.partition(" - ")
    if sep:
        message = head.split(" ", 1)[0] + " " + desc
    return message.rstrip(".")


def main():
    while not os.path.exists(FB):
        time.sleep(0.2)
    screen = Screen()
    # Messages de systemd (PID 1) : « Starting… », « Started… », « Reached target… ».
    journal = subprocess.Popen(
        ["journalctl", "-b", "-f", "-n", str(LINES), "-o", "cat", "_PID=1"],
        stdout=subprocess.PIPE)
    fd = journal.stdout.fileno()
    pending, lines, dirty, display_since = b"", [], False, None
    try:
        while True:
            # Lecture brute (pas de tampon Python) : select() voit tout ce qui reste à lire.
            if select.select([fd], [], [], 0.5)[0]:
                chunk = os.read(fd, 4096)
                if not chunk:
                    break
                *complete, pending = (pending + chunk).split(b"\n")
                for raw in complete:
                    lines = (lines + [short(raw.decode(errors="replace").strip())])[-LINES:]
                    dirty = True
            try:
                if read_sys("name") != screen.name:  # framebuffer remplacé (vc4)
                    screen.close()
                    screen = Screen()
                    dirty = True
            except OSError:
                continue  # fb0 en cours de remplacement
            if dirty:
                screen.show_lines(lines)
                dirty = False
            if os.path.lexists(DISPLAY_ACTIVE):
                display_since = display_since or time.monotonic()
                if time.monotonic() - display_since > STOP_AFTER_DISPLAY:
                    break
    finally:
        journal.terminate()
        screen.close()


if __name__ == "__main__":
    main()
