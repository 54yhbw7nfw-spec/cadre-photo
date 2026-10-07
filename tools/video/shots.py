"""Captures de l'admin pour le mode d'emploi vidéo (Firefox sans fenêtre).

Firefox --screenshot photographie dès l'événement « load », avant les appels à l'API : la page
est donc affichée dans un cadre (iframe) d'une page locale dont le « load » est retardé par
une image servie lentement.

Usage : python tools/video/shots.py http://<ip du cadre> build/video/shots [langue]
La langue (fr, en, es, de, pt, ro, ru, ar, zh ; fr par défaut) est celle que Firefox demande à la page
(Accept-Language) : un profil Firefox par langue.

Données personnelles floutées par une feuille de style du profil (userContent.css), quelle que
soit la mise en page de la langue : lien de l'album iCloud, réseaux Wi-Fi, notes de mise à jour.
La ville de la météo (CITY) et la langue du cadre (celle des captures) sont changées sur le
cadre le temps des captures, puis remises.
"""
import http.server
import json
import os
import subprocess
import sys
import threading
import time
import urllib.request

FIREFOX = r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe"
PORT = 8766
WAIT = 15  # s laissées à la page pour charger photos et réglages
CITY = "Niort"  # ville de la météo montrée sur les captures

# Flou fort : illisible même agrandi dans la vidéo.
BLUR = "color: transparent !important; text-shadow: 0 0 16px rgba(0, 0, 0, .7) !important;"
USER_CSS = f"""
#icloud-form input[name=url], #wifi-state, #wifi-result, #wifi-saved .grow,
#wifi-visible .grow {{ {BLUR} }}
#upd-notes {{ display: none !important; }}
"""

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


def main(base, out, lang="fr"):
    os.makedirs(out, exist_ok=True)
    profile = os.path.abspath(os.path.join(out, "..", "ffprofile-" + lang))
    os.makedirs(profile, exist_ok=True)
    with open(os.path.join(profile, "user.js"), "w") as f:
        f.write(f'user_pref("intl.accept_languages", "{lang}");\n'
                'user_pref("toolkit.legacyUserProfileCustomizations.stylesheets", true);\n')
    os.makedirs(os.path.join(profile, "chrome"), exist_ok=True)
    with open(os.path.join(profile, "chrome", "userContent.css"), "w") as f:
        f.write(USER_CSS)
    city = weather_city(base, CITY)
    frame_lang = frame_language(base, lang)
    try:  # le cadre retrouve sa ville et sa langue, même après une erreur
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
    finally:
        weather_city(base, city)
        frame_language(base, frame_lang)


def frame_language(base, lang):
    """Change la langue du cadre (réglage) ; renvoie l'ancienne."""
    with urllib.request.urlopen(base + "/api/settings", timeout=30) as r:
        old = json.load(r)["language"]
    req = urllib.request.Request(base + "/api/settings", json.dumps({"language": lang}).encode(),
                                 {"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=30).close()
    return old


def weather_city(base, city):
    """Change la ville de la météo du cadre ; renvoie l'ancienne."""
    with urllib.request.urlopen(base + "/api/weather", timeout=30) as r:
        old = json.load(r)["city"]
    req = urllib.request.Request(base + "/api/weather", json.dumps({"city": city}).encode(),
                                 {"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=60).close()
    return old


if __name__ == "__main__":
    main(sys.argv[1].rstrip("/"), *sys.argv[2:4])
