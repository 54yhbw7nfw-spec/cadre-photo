"""Admin web : upload, galerie, réglages. Servi par waitress (service cadre-web).

Les fichiers reçus sont posés en RAM (INCOMING_DIR) puis traités un par un par un thread
de fond ; quand la file dépasse QUEUE_MAX_BYTES, l'upload répond 503 et le navigateur
réessaie un peu plus tard.

Mot de passe optionnel (page de connexion, aussi modifiable dans l'admin) :
    python3 -m cadre.web --set-password     # demande le mot de passe
    python3 -m cadre.web --clear-password
"""
import argparse
import collections
import getpass
import hashlib
import secrets
import json
import logging
import os
import socket
import threading
import time
import urllib.parse
import urllib.request
import uuid

from flask import (Flask, jsonify, redirect, render_template, request, session,
                   send_from_directory)
from werkzeug.security import check_password_hash, generate_password_hash

from . import config, icloud, imaging

log = logging.getLogger("cadre.web")

QUEUE_MAX_BYTES = 40 * 1024 * 1024
# Marge laissée au système (journal, mises à jour, fichiers temporaires) : les envois sont
# refusés quand l'espace libre passerait en dessous.
DISK_RESERVE_MIN = 1024 ** 3
DISK_RESERVE_RATIO = 0.05
PER_PAGE_MAX = 200

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 60 * 1024 * 1024
app.config["PERMANENT_SESSION_LIFETIME"] = 30 * 86400
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"


class ProcessingQueue:
    """File de traitement en tâche de fond ; un seul fichier traité à la fois (1 cœur)."""

    def __init__(self):
        self.items = collections.deque()
        self.cond = threading.Condition()
        self.pending_bytes = 0
        self.busy = False
        self.done = 0         # compteurs cumulés depuis le démarrage du service :
        self.failed = 0       # le navigateur calcule sa progression par différence
        self.errors = collections.deque(maxlen=50)

    def start(self):
        threading.Thread(target=self._run, name="traitement", daemon=True).start()

    def full(self):
        return self.pending_bytes > QUEUE_MAX_BYTES

    def put(self, path, original_name, size, taken="", sig=""):
        with self.cond:
            self.items.append((path, original_name, size, taken, sig))
            self.pending_bytes += size
            self.cond.notify()

    def status(self):
        with self.cond:
            return {"pending": len(self.items) + self.busy, "done": self.done,
                    "failed": self.failed, "errors": list(self.errors)}

    def _run(self):
        while True:
            with self.cond:
                while not self.items:
                    self.cond.wait()
                path, original_name, size, taken, sig = self.items.popleft()
                self.busy = True
            t0 = time.monotonic()
            error = None
            try:
                with process_lock:
                    name, new = imaging.process(path, config.load_settings()["keep_originals"],
                                                original_name, taken, sig)
                log.info("%s -> %s%s en %d ms", original_name, name,
                         "" if new else " (doublon)", (time.monotonic() - t0) * 1000)
            except imaging.Rejected as exc:
                error = str(exc)
            except Exception as exc:  # disque plein, etc. : ne pas tuer le thread
                log.exception("Échec du traitement de %s", original_name)
                error = f"erreur interne ({exc})"
            finally:
                try:
                    os.unlink(path)
                except FileNotFoundError:
                    pass  # déplacé vers les originaux
            with self.cond:
                self.busy = False
                self.pending_bytes -= size
                if error:
                    self.failed += 1
                    self.errors.append({"id": self.failed, "file": original_name, "error": error})
                    log.warning("Rejeté %s : %s", original_name, error)
                else:
                    self.done += 1


queue = ProcessingQueue()
process_lock = threading.Lock()  # un seul traitement d'image à la fois (1 cœur) : file + iCloud


def disk_status():
    st = os.statvfs(config.DATA_DIR)
    total = st.f_blocks * st.f_frsize
    free = st.f_bavail * st.f_frsize
    reserve = max(DISK_RESERVE_MIN, int(total * DISK_RESERVE_RATIO))
    return {"total": total, "free": free, "reserve": reserve,
            "free_pct": round(100 * free / total, 1) if total else 0.0,
            "full": free - queue.pending_bytes < reserve}


# --- Album iCloud partagé ------------------------------------------------------------------

ICLOUD_EVERY = 30 * 60
ICLOUD_FIRST_DELAY = 120  # s après le lancement : le diaporama et le Wi-Fi d'abord
ICLOUD_MAX_BYTES = 40 * 1024 * 1024


class IcloudSync:
    """Garde le cadre aligné sur un album partagé iCloud : nouvelles photos téléchargées et
    traitées comme un envoi, photos retirées de l'album supprimées. icloud.json associe
    l'identifiant iCloud de chaque photo à son nom sur le cadre ; les photos envoyées par
    l'admin n'y figurent pas et ne sont jamais touchées. Une photo de l'album supprimée dans
    l'admin n'est pas retéléchargée."""

    def __init__(self):
        self.wake = threading.Event()
        self.lock = threading.Lock()  # lecture-modification-écriture de icloud.json
        self.running = False
        self.progress = ""
        self.force = False  # synchronisation demandée dans l'admin : tout l'album revient

    def load(self):
        try:
            with open(config.ICLOUD_FILE) as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def update(self, url, fn):
        """Applique fn à l'état si l'album n'a pas changé entre-temps ; renvoie True si fait."""
        with self.lock:
            st = self.load()
            if st.get("url", "") != url:
                return False
            st.setdefault("photos", {})
            fn(st)
            config.atomic_write_json(config.ICLOUD_FILE, st)
            return True

    def status(self):
        st = self.load()
        return {"url": st.get("url", ""), "title": st.get("title", ""),
                "count": len(st.get("photos", {})), "last_sync": st.get("last_sync"),
                "error": st.get("error", ""), "running": self.running, "progress": self.progress}

    def set_url(self, url):
        """Change d'album (ou l'arrête si url est vide) ; les photos de l'ancien sont retirées."""
        url = url.strip()
        if url:
            icloud.parse_link(url)  # AlbumError si le lien n'est pas reconnu
        with self.lock:
            st = self.load()
            if url == st.get("url", ""):
                return
            for name in st.get("photos", {}).values():
                imaging.delete(name)
            config.atomic_write_json(config.ICLOUD_FILE, {"url": url, "photos": {}})
        log.info("Album iCloud : %s", url or "aucun")
        self.wake.set()

    def start(self):
        threading.Thread(target=self._run, name="icloud", daemon=True).start()

    def _run(self):
        self.wake.wait(ICLOUD_FIRST_DELAY)
        while True:
            self.wake.clear()
            try:
                self.sync()
            except Exception:  # ne jamais arrêter le thread
                log.exception("Synchronisation iCloud")
            finally:
                self.running, self.progress = False, ""
            self.wake.wait(ICLOUD_EVERY)

    def sync(self):
        url = self.load().get("url", "")
        if not url or config.load_state().get("mode") == "hotspot":
            return
        self.running = True
        t0 = time.monotonic()
        try:
            title, photos = icloud.fetch_album(url)
        except icloud.AlbumError as exc:
            log.warning("Album iCloud : %s", exc)
            self.update(url, lambda st: st.update(error=str(exc), last_sync=time.time()))
            return
        self.update(url, lambda st: st.update(title=title))

        album = {p["id"] for p in photos}
        known = self.load().get("photos", {})
        if self.force:
            self.force = False
            missing = {pid for pid, name in known.items()
                       if not os.path.exists(os.path.join(config.PHOTOS_DIR, name))}
            known = {pid: name for pid, name in known.items() if pid not in missing}
            self.update(url, lambda st: [st["photos"].pop(pid, None) for pid in missing])
        gone = {pid: name for pid, name in known.items() if pid not in album}
        for name in gone.values():
            imaging.delete(name)
        self.update(url, lambda st: [st["photos"].pop(pid, None) for pid in gone])

        new = [p for p in photos if p["id"] not in known]
        error = ""
        for i, p in enumerate(new, 1):
            self.progress = f"{i} / {len(new)}"
            if disk_status()["full"]:
                error = "carte SD pleine : synchronisation arrêtée"
                break
            try:
                name = self.add(p)
            except (OSError, imaging.Rejected) as exc:
                log.warning("Photo iCloud %s : %s", p["id"], exc)
                error = f"une photo n'a pas pu être ajoutée ({exc})"
                continue
            if not self.update(url, lambda st: st["photos"].__setitem__(p["id"], name)):
                imaging.delete(name)  # album changé pendant le téléchargement
                return
        self.update(url, lambda st: st.update(error=error, last_sync=time.time()))
        log.info("Album iCloud « %s » : %d photos, %d ajoutées, %d retirées en %d s",
                 title, len(photos), len(new), len(gone), time.monotonic() - t0)

    def add(self, photo):
        path = os.path.join(config.INCOMING_DIR, "icloud-" + uuid.uuid4().hex)
        try:
            req = urllib.request.Request(photo["url"],
                                         headers={"User-Agent": icloud.HEADERS["User-Agent"]})
            with urllib.request.urlopen(req, timeout=60) as r, open(path, "wb") as f:
                size = 0
                while chunk := r.read(1 << 16):
                    size += len(chunk)
                    if size > ICLOUD_MAX_BYTES:
                        raise OSError("fichier trop volumineux")
                    f.write(chunk)
            taken = photo["taken"].strftime("%Y:%m:%d %H:%M:%S") if photo["taken"] else ""
            with process_lock:
                name, _ = imaging.process(path, False, "icloud.jpg", taken,
                                          "icloud:" + photo["id"])
            return name
        finally:
            try:
                os.unlink(path)
            except FileNotFoundError:
                pass


icloud_sync = IcloudSync()


# --- Portail captif -------------------------------------------------------------------------

@app.before_request
def captive_portal():
    """En mode hotspot, le DNS du Pi répond 10.42.0.1 pour tous les noms : toute page demandée
    par le téléphone (test de connectivité compris) est renvoyée vers la configuration Wi-Fi,
    ce qui fait apparaître le portail automatiquement."""
    state = config.load_state()
    if state.get("mode") != "hotspot":
        return None
    host = request.host.split(":")[0].lower()
    # Peu de requêtes en hotspot : on les garde pour comprendre les tests des téléphones.
    log.info("Portail : %s %s%s (%s)", request.method, host, request.path,
             request.headers.get("User-Agent", "")[:60])
    hostname = socket.gethostname().lower()
    if host in (state.get("ip"), hostname, hostname + ".local"):
        return None
    return redirect(f"http://{state.get('ip')}/wifi", 302)


# --- Authentification optionnelle -------------------------------------------------------
# Page de connexion et cookie de session signé (30 jours). Le cookie porte une empreinte du
# mot de passe : le changer déconnecte les autres navigateurs. Le hachage pbkdf2 n'a lieu qu'à
# la connexion (lent sur le Pi Zero).

LOGIN_EXEMPT = ("/login", "/static/")


def load_auth():
    try:
        with open(config.AUTH_FILE) as f:
            return json.load(f).get("password_hash")
    except (OSError, ValueError):
        return None


def auth_fingerprint(pw_hash):
    return hashlib.sha256(pw_hash.encode()).hexdigest()[:16]


def write_password(pw):
    """Enregistre le mot de passe (vide : authentification désactivée) ; renvoie l'empreinte."""
    if not pw:
        try:
            os.unlink(config.AUTH_FILE)
        except FileNotFoundError:
            pass
        return None
    # pbkdf2 allégé : supportable sur le Pi Zero, une seule fois par connexion.
    pw_hash = generate_password_hash(pw, method="pbkdf2:sha256:50000")
    config.atomic_write_json(config.AUTH_FILE, {"password_hash": pw_hash})
    os.chmod(config.AUTH_FILE, 0o600)
    return auth_fingerprint(pw_hash)


def load_secret_key():
    """Clé de signature des cookies, créée au premier lancement (0600)."""
    path = os.path.join(config.DATA_DIR, "secret_key")
    try:
        with open(path) as f:
            return f.read().strip()
    except FileNotFoundError:
        key = secrets.token_hex(32)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(key)
        return key


@app.before_request
def require_password():
    pw_hash = load_auth()
    if not pw_hash:
        return None
    path = request.path
    if path.startswith(LOGIN_EXEMPT):
        return None
    # Portail du hotspot : seul qui voit l'écran (mot de passe du hotspot) peut s'y connecter,
    # et la page doit s'ouvrir seule sur le téléphone, sans page de connexion.
    if config.load_state().get("mode") == "hotspot" and (
            path in ("/wifi", "/api/wifi") or path.startswith("/api/wifi/")):
        return None
    if session.get("auth") == auth_fingerprint(pw_hash):
        return None
    if path.startswith("/api/"):
        return jsonify(error="connexion requise"), 401
    return redirect("/login?next=" + urllib.parse.quote(path))


@app.route("/login", methods=["GET", "POST"])
def login():
    pw_hash = load_auth()
    target = request.values.get("next", "/")
    if not target.startswith("/") or target.startswith("//"):
        target = "/"
    if not pw_hash:
        return redirect(target)
    error = ""
    if request.method == "POST":
        if check_password_hash(pw_hash, request.form.get("password", "")):
            session.permanent = True
            session["auth"] = auth_fingerprint(pw_hash)
            return redirect(target)
        time.sleep(1)  # freine les essais en rafale
        error = "Mot de passe incorrect."
        log.warning("Connexion refusée depuis %s", request.remote_addr)
    return render_template("login.html", error=error, next=target)


@app.get("/logout")
def logout():
    session.clear()
    return redirect("/login")


@app.get("/api/password")
def password_status():
    return jsonify(enabled=bool(load_auth()))


@app.post("/api/password")
def password_change():
    data = request.get_json(silent=True) or {}
    pw_hash = load_auth()
    if pw_hash and not check_password_hash(pw_hash, str(data.get("current", ""))):
        time.sleep(1)
        return jsonify(error="mot de passe actuel incorrect"), 403
    new = str(data.get("new", ""))
    if new and len(new) < 6:
        return jsonify(error="6 caractères minimum"), 400
    fingerprint = write_password(new)
    if fingerprint:
        session.permanent = True
        session["auth"] = fingerprint  # ce navigateur reste connecté
    else:
        session.clear()
    log.info("Mot de passe de l'admin %s", "changé" if new else "supprimé")
    return jsonify(enabled=bool(new))


# --- Pages et API ------------------------------------------------------------------------

@app.get("/")
def index():
    return render_template("index.html", transitions=config.TRANSITIONS)


@app.get("/wifi")
def wifi_page():
    return render_template("wifi.html")


@app.get("/thumbs/<name>")
def thumb(name):
    return send_from_directory(config.THUMBS_DIR, name, max_age=30 * 86400)


@app.get("/photos/<name>")
def photo(name):
    return send_from_directory(config.PHOTOS_DIR, name, max_age=30 * 86400)


@app.post("/api/upload")
def upload():
    f = request.files.get("file")
    if f is None or not f.filename:
        return jsonify(error="aucun fichier"), 400
    if queue.full():
        return jsonify(busy=True), 503
    disk = disk_status()
    if disk["free"] - queue.pending_bytes - (request.content_length or 0) < disk["reserve"]:
        return jsonify(error="carte SD pleine (marge du système atteinte)"), 507
    dest = os.path.join(config.INCOMING_DIR, uuid.uuid4().hex)
    f.save(dest)
    # Photo réduite par le navigateur : EXIF perdu, d'où la date et la signature transmises à part.
    queue.put(dest, os.path.basename(f.filename), os.path.getsize(dest),
              request.form.get("taken", "")[:19], request.form.get("sig", "")[:300])
    return jsonify(ok=True)


@app.get("/api/status")
def status():
    return jsonify(queue=queue.status(), count=len(config.list_photos()), disk=disk_status())


@app.get("/api/photos")
def photos():
    names = config.list_photos()[::-1]  # plus récentes d'abord
    per = max(1, min(PER_PAGE_MAX, request.args.get("per", 48, type=int)))
    pages = max(1, -(-len(names) // per))
    page = max(1, min(pages, request.args.get("page", 1, type=int)))
    items = names[(page - 1) * per:page * per]
    cloud = set(icloud_sync.load().get("photos", {}).values())
    return jsonify(total=len(names), page=page, pages=pages, disk=disk_status(),
                   items=items, cloud=[n for n in items if n in cloud])


@app.post("/api/delete")
def delete():
    names = (request.get_json(silent=True) or {}).get("names", [])
    deleted = sum(imaging.delete(n) for n in names if isinstance(n, str))
    return jsonify(deleted=deleted)


@app.get("/api/icloud")
def icloud_status():
    return jsonify(icloud_sync.status())


@app.post("/api/icloud")
def icloud_set():
    try:
        icloud_sync.set_url((request.get_json(silent=True) or {}).get("url", ""))
    except icloud.AlbumError as exc:
        return jsonify(error=str(exc)), 400
    return jsonify(icloud_sync.status())


@app.post("/api/icloud/sync")
def icloud_sync_now():
    icloud_sync.force = True
    icloud_sync.wake.set()
    return jsonify(ok=True)


@app.get("/api/settings")
def get_settings():
    return jsonify(config.load_settings())


@app.post("/api/settings")
def set_settings():
    settings = config.load_settings()
    settings.update(request.get_json(silent=True) or {})
    config.save_settings(settings)
    return jsonify(config.load_settings())


# --- Wi-Fi : relais vers cadre-net (seul service autorisé à modifier le réseau) ----------

def net_command(cmd, **args):
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(60)
            s.connect(config.NET_SOCKET)
            s.sendall(json.dumps({"cmd": cmd, **args}).encode() + b"\n")
            data = b""
            while not data.endswith(b"\n"):
                chunk = s.recv(65536)
                if not chunk:
                    break
                data += chunk
        return json.loads(data)
    except (OSError, ValueError) as exc:
        return {"ok": False, "error": f"service réseau indisponible ({exc})"}


@app.get("/api/wifi")
def wifi_status():
    return jsonify(net_command("status"))


@app.post("/api/wifi/<action>")
def wifi_action(action):
    if action not in ("scan", "save", "connect", "forget"):
        return jsonify(ok=False, error="action inconnue"), 404
    body = request.get_json(silent=True) or {}
    args = {k: body[k] for k in ("ssid", "password", "hidden", "uuid") if k in body}
    return jsonify(net_command(action, **args))


# --- Lancement ---------------------------------------------------------------------------

def set_password(clear):
    if clear:
        try:
            os.unlink(config.AUTH_FILE)
        except FileNotFoundError:
            pass
        print("Mot de passe supprimé : admin accessible sans authentification.")
        return
    pw = getpass.getpass("Nouveau mot de passe : ")
    if not pw or pw != getpass.getpass("Confirmation : "):
        raise SystemExit("Mots de passe vides ou différents, rien n'est changé.")
    write_password(pw)
    print("Mot de passe enregistré.")


def main():
    parser = argparse.ArgumentParser(description="Admin web du cadre photo")
    parser.add_argument("--set-password", action="store_true")
    parser.add_argument("--clear-password", action="store_true")
    parser.add_argument("--port", type=int, default=int(os.environ.get("CADRE_WEB_PORT", 80)))
    args = parser.parse_args()
    if args.set_password or args.clear_password:
        set_password(args.clear_password)
        return

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logging.getLogger("waitress.queue").setLevel(logging.ERROR)
    for d in (config.PHOTOS_DIR, config.THUMBS_DIR, config.ORIGINALS_DIR, config.INCOMING_DIR):
        os.makedirs(d, exist_ok=True)
    for leftover in os.listdir(config.INCOMING_DIR):
        os.unlink(os.path.join(config.INCOMING_DIR, leftover))
    app.secret_key = load_secret_key()
    queue.start()
    icloud_sync.start()

    from waitress import serve
    log.info("Admin web sur le port %d", args.port)
    serve(app, host="0.0.0.0", port=args.port, threads=4, ident="cadre",
          channel_timeout=300)


if __name__ == "__main__":
    main()
