"""Mise à jour à distance par fichier signé (.cadre), installée par cadre-net (root).

Fichier .cadre (fabriqué par make_update.sh sur le PC) : archive tar de deux membres,
payload.tar.gz (cadre/ avec VERSION et NOTES, systemd/, system/, et éventuellement apply.sh)
et payload.tar.gz.sig, signature « ssh-keygen -Y sign » (espace de noms « cadre-maj ») vérifiée
avec /etc/cadre/allowed_signers (clé publique du développeur, posée par install.sh).

Installation : vérification, version strictement plus récente, code mis dans /opt/cadre (l'ancien
gardé dans /opt/cadre.prev), unités systemd mises à jour, apply.sh éventuel (root, une fois), puis
redémarrage des services. Un garde-fou lancé 150 s plus tard (copie de CE fichier, tirée de
l'ancienne version : il marche même si la nouvelle est cassée) vérifie les services et l'admin,
sinon remet l'ancienne version.

Module sans dépendance au reste du paquet : il est aussi exécuté seul (python3 fichier guard).
"""
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request

OPT = "/opt/cadre"
PREV = "/opt/cadre.prev"
FAILED = "/opt/cadre.failed"
WORK = "/var/lib/cadre-updates"            # root seulement
STATUS = "/var/lib/cadre/update-status.json"  # lu par l'admin
SIGNERS = "/etc/cadre/allowed_signers"
NAMESPACE = PRINCIPAL = "cadre-maj"
SERVICES = ["cadre-web", "cadre-display", "cadre-net"]
GUARD_DELAY = 150  # s : démarrage du diaporama (~30 s) et de l'admin (~10 s), avec marge
APPLY_TIMEOUT = 900


class UpdateError(Exception):
    """Mise à jour refusée ou ratée (message pour l'admin)."""


def version(root=OPT):
    try:
        with open(os.path.join(root, "cadre", "VERSION")) as f:
            return f.read().strip()
    except OSError:
        return ""


def status():
    try:
        with open(STATUS) as f:
            st = json.load(f)
    except (OSError, ValueError):
        st = {}
    st["current"] = version()
    st["previous"] = version(PREV)
    return st


def write_status(**fields):
    st = {k: v for k, v in status().items() if k not in ("current", "previous")}
    st.update(fields, time=time.time())
    tmp = STATUS + ".tmp"
    with open(tmp, "w") as f:
        json.dump(st, f, ensure_ascii=False)
    os.chmod(tmp, 0o644)
    os.replace(tmp, STATUS)


def run(*cmd, timeout=120, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, **kw)


def sync_units(root):
    """Unités systemd de root/systemd vers /etc/systemd/system (comme deploy.sh)."""
    changed = False
    src_dir = os.path.join(root, "systemd")
    for name in sorted(os.listdir(src_dir)) if os.path.isdir(src_dir) else []:
        src, dst = os.path.join(src_dir, name), os.path.join("/etc/systemd/system", name)
        if name.endswith(".service") and (not os.path.exists(dst)
                                          or open(src, "rb").read() != open(dst, "rb").read()):
            shutil.copyfile(src, dst)
            os.chmod(dst, 0o644)
            changed = True
    if changed:
        run("systemctl", "daemon-reload")


def restart_later(delay=3):
    """Redémarre les services hors de cadre-net (qui en fait partie) : unité transitoire."""
    run("systemd-run", f"--on-active={delay}", "--timer-property=AccuracySec=1s",
        "--unit", f"cadre-restart-{int(time.time())}", "systemctl", "restart", *SERVICES)


def chown_cadre(path):
    run("chown", "-R", "cadre:cadre", path)


def verify(bundle, tmp):
    """Vérifie un fichier .cadre et l'extrait dans tmp/new ; renvoie (dossier, version, notes)."""
    try:
        with tarfile.open(bundle) as t:
            names = sorted(t.getnames())
            if names != ["payload.tar.gz", "payload.tar.gz.sig"]:
                raise UpdateError("ce n'est pas un fichier de mise à jour du cadre")
            t.extractall(tmp, filter="data")
    except tarfile.TarError:
        raise UpdateError("fichier illisible : ce n'est pas un fichier de mise à jour") from None
    payload = os.path.join(tmp, "payload.tar.gz")
    with open(payload, "rb") as f:
        check = run("ssh-keygen", "-Y", "verify", "-f", SIGNERS, "-I", PRINCIPAL,
                    "-n", NAMESPACE, "-s", payload + ".sig", stdin=f)
    if check.returncode != 0:
        raise UpdateError("signature invalide : fichier modifié ou non fourni par le "
                          "développeur du cadre")
    new = os.path.join(tmp, "new")
    with tarfile.open(payload) as t:
        t.extractall(new, filter="data")
    new_version = version(new)
    if not new_version:
        raise UpdateError("version absente du fichier")
    notes = ""
    try:
        with open(os.path.join(new, "cadre", "NOTES")) as f:
            notes = f.read().strip()
    except OSError:
        pass
    return new, new_version, notes


def is_newer(new_version, current):
    return not current or new_version.split()[0] > current.split()[0]


def check(bundle):
    """Vérifie sans installer : {"version", "notes", "newer", "current"} (UpdateError sinon)."""
    os.makedirs(WORK, mode=0o700, exist_ok=True)
    tmp = tempfile.mkdtemp(dir=WORK)
    try:
        _, new_version, notes = verify(bundle, tmp)
        return {"version": new_version, "notes": notes,
                "newer": is_newer(new_version, version()), "current": version()}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def download(url, dest, limit=60 * 1024 * 1024):
    """Télécharge un .cadre (lien https, par exemple une release GitHub publique)."""
    if not url.startswith("https://"):
        raise UpdateError("l'adresse doit commencer par https://")
    os.makedirs(WORK, mode=0o700, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "cadre-photo"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
            size = 0
            while chunk := r.read(1 << 16):
                size += len(chunk)
                if size > limit:
                    raise UpdateError("fichier trop volumineux")
                f.write(chunk)
    except urllib.error.HTTPError as exc:
        raise UpdateError("aucune mise à jour à cette adresse" if exc.code == 404
                          else f"téléchargement refusé (HTTP {exc.code})") from None
    except OSError as exc:
        raise UpdateError(f"téléchargement impossible ({exc})") from None


def install(bundle):
    """Vérifie et installe un fichier .cadre ; renvoie la nouvelle version."""
    os.makedirs(WORK, mode=0o700, exist_ok=True)
    tmp = tempfile.mkdtemp(dir=WORK)
    try:
        new, new_version, notes = verify(bundle, tmp)
        st = status()
        if (st.get("state") in ("installing", "pending")
                and time.time() - st.get("time", 0) < GUARD_DELAY + 60):
            raise UpdateError("la mise à jour précédente est encore en vérification : "
                              "réessayez dans quelques minutes")
        current = version()
        if not is_newer(new_version, current):
            raise UpdateError(f"version {new_version} déjà installée ou plus ancienne "
                              f"(installée : {current})")

        # Garde-fou de l'ancienne version, mis de côté avant tout changement.
        guard = os.path.join(WORK, "guard.py")
        shutil.copyfile(os.path.abspath(__file__), guard)
        write_status(state="installing", version=new_version, previous_version=current,
                     notes=notes, message="installation en cours")
        shutil.rmtree(PREV, ignore_errors=True)
        shutil.rmtree(FAILED, ignore_errors=True)
        staged = OPT + ".new"
        shutil.rmtree(staged, ignore_errors=True)
        shutil.copytree(new, staged, symlinks=True)
        chown_cadre(staged)
        os.rename(OPT, PREV)
        os.rename(staged, OPT)
        sync_units(OPT)
        script = os.path.join(OPT, "apply.sh")
        if os.path.exists(script):
            res = run("sh", script, timeout=APPLY_TIMEOUT, cwd=OPT)
            if res.returncode != 0:
                rollback(f"script de migration en échec : {(res.stdout + res.stderr)[-300:]}")
                raise UpdateError("script de migration en échec : ancienne version remise")
        write_status(state="pending", message="services en redémarrage, vérification dans "
                     f"{GUARD_DELAY // 60} min {GUARD_DELAY % 60} s")
        # Précision à la seconde : par défaut, une minuterie systemd peut partir 1 min en retard.
        run("systemd-run", f"--on-active={GUARD_DELAY}", "--timer-property=AccuracySec=1s",
            "--unit", f"cadre-update-guard-{int(time.time())}", sys.executable, guard, "guard",
            new_version)
        restart_later()
        return new_version
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def rollback(reason="demandé dans l'admin"):
    """Remet /opt/cadre.prev en place (la version écartée part dans /opt/cadre.failed)."""
    if not os.path.isdir(PREV):
        raise UpdateError("aucune version précédente disponible")
    bad = version()
    shutil.rmtree(FAILED, ignore_errors=True)
    os.rename(OPT, FAILED)
    os.rename(PREV, OPT)
    sync_units(OPT)
    write_status(state="rolled_back", message=f"version {bad} retirée : {reason}")
    restart_later()


def healthy():
    """Services actifs sans interruption depuis 30 s (un service qui plante redémarre toutes les
    3 s), et admin qui répond."""
    for service in SERVICES:
        if run("systemctl", "is-active", service).stdout.strip() != "active":
            return f"{service} ne tourne pas"
        since = run("systemctl", "show", "-p", "ActiveEnterTimestampMonotonic", "--value",
                    service).stdout.strip()
        # Horloge monotone de systemd = CLOCK_MONOTONIC, comme time.monotonic() sous Linux.
        if since.isdigit() and time.monotonic() - int(since) / 1e6 < 30:
            return f"{service} redémarre en boucle"
    try:
        with urllib.request.urlopen("http://127.0.0.1/login", timeout=20) as r:
            if r.status >= 500:
                return f"l'admin répond {r.status}"
    except OSError as exc:
        return f"l'admin ne répond pas ({exc})"
    return None


def guard(expected=None):
    """Vérifie l'installation de la version expected, et elle seule : si une autre a été
    installée ou remise depuis, ce garde-fou n'a plus rien à juger."""
    st = status()
    if expected and (st.get("version") != expected or st.get("state") != "pending"):
        return
    problem = healthy()
    if problem:
        rollback(f"vérification après installation : {problem}")
    else:
        write_status(state="ok", message="installée et vérifiée")


if __name__ == "__main__":
    if sys.argv[1:2] == ["guard"]:
        guard(" ".join(sys.argv[2:]) or None)
