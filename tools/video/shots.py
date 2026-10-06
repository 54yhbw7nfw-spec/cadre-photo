"""Captures de l'admin pour le mode d'emploi vidéo (Firefox sans fenêtre).

Firefox --screenshot photographie dès l'événement « load », avant les appels à l'API : la page
est donc affichée dans un cadre (iframe) d'une page locale dont le « load » est retardé par
une image servie lentement.

Usage : python tools/video/shots.py http://<ip du cadre> build/video/shots
"""
import http.server
import os
import subprocess
import sys
import threading
import time

FIREFOX = r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe"
PORT = 8766
WAIT = 15  # s laissées à la page pour charger photos et réglages

# (fichier, chemin sur le cadre, largeur, hauteur, défilement vertical dans la page)
SHOTS = [
    ("admin-haut.png", "/", 1280, 1000, 0),
    ("admin-photos.png", "/", 1280, 1100, 470),
    ("admin-complet.png", "/", 1280, 4200, 0),
    ("portail-wifi.png", "/wifi", 400, 860, 0),
]

PAGE = """<!doctype html><html><head><style>html,body{{margin:0;overflow:hidden}}
iframe{{border:0;width:{w}px;height:{full}px;margin-top:-{y}px}}</style></head><body>
<iframe src="{url}"></iframe><img src="/lent" width="1" height="1" style="position:absolute">
</body></html>"""


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/lent":
            time.sleep(WAIT)
            body, kind = b"GIF89a\x01\x00\x01\x00\x00\x00\x00;", "image/gif"
        else:
            body, kind = self.server.pages[self.path].encode(), "text/html; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        pass


def main(base, out):
    os.makedirs(out, exist_ok=True)
    profile = os.path.abspath(os.path.join(out, "..", "ffprofile"))
    os.makedirs(profile, exist_ok=True)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    server.pages = {}
    threading.Thread(target=server.serve_forever, daemon=True).start()
    for name, path, w, h, y in SHOTS:
        key = "/" + name
        server.pages[key] = PAGE.format(url=base + path, w=w, full=h + y, y=y)
        dest = os.path.abspath(os.path.join(out, name))
        subprocess.run([FIREFOX, "--headless", "--no-remote", "--profile", profile,
                        "--window-size", f"{w},{h}", "--screenshot", dest,
                        f"http://127.0.0.1:{PORT}{key}"], capture_output=True, timeout=120)
        print(name, "ok" if os.path.exists(dest) else "ÉCHEC")
    server.shutdown()


if __name__ == "__main__":
    main(sys.argv[1].rstrip("/"), sys.argv[2])
