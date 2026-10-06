"""Rapport de diagnostic (texte) à envoyer au développeur, fabriqué par cadre-net (root : le
journal système complet n'est lisible qu'ainsi).

Les données sensibles sont retirées : mots de passe Wi-Fi et du hotspot, empreinte du mot de
passe de l'admin (jamais lus ici), lien de l'album iCloud.
"""
import json
import os
import re
import shutil
import subprocess
import time

from . import config

# Choix proposés dans l'admin -> unités systemd (ou options) correspondantes.
GROUPS = {
    "display": ("Diaporama", ["-u", "cadre-display", "-u", "cadre-splash", "-u", "cadre-shutdown"]),
    "web": ("Admin et album iCloud", ["-u", "cadre-web"]),
    "network": ("Réseau (Wi-Fi, hotspot)", ["-u", "cadre-net", "-u", "NetworkManager",
                                            "-u", "wpa_supplicant"]),
    "system": ("Système (avertissements et erreurs)", ["-p", "warning"]),
}
PERIODS = {"1h": "-1h", "today": "today", "3d": "-3d"}
MAX_LINES = 4000  # par rubrique : le rapport reste lisible et transmissible par messagerie

REDACT = [
    (re.compile(r"(icloud\.com/(?:shared/album|photos)/)[A-Za-z0-9_-]+"), r"\1…"),
    (re.compile(r"(sharedalbum/(?:[a-z-]+/)?#)[A-Za-z0-9]+"), r"\1…"),
    (re.compile(r"(?i)\b(psk|password|passwd|mot de passe)(\s*[=:]\s*)\S+"), r"\1\2…"),
]


def redact(text):
    for pattern, repl in REDACT:
        text = pattern.sub(repl, text)
    return text


def run(*cmd, timeout=60):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return (p.stdout + p.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"({exc})"


def read(path, default=""):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return default


def system_info():
    st = os.statvfs(config.DATA_DIR)
    temp = read("/sys/class/thermal/thermal_zone0/temp", "0")
    state = {k: v for k, v in config.load_state().items() if k != "ap_password"}
    icloud = {}
    try:
        with open(config.ICLOUD_FILE) as f:
            data = json.load(f)
        icloud = {"album suivi": bool(data.get("url")), "titre": data.get("title", ""),
                  "photos": len(data.get("photos", {})), "erreur": data.get("error", "")}
    except (OSError, ValueError):
        pass
    lines = [
        f"Version du code : {read(os.path.join(os.path.dirname(__file__), 'VERSION'), 'inconnue')}",
        f"Système : {read('/etc/debian_version')} / noyau {os.uname().release}",
        f"Allumé depuis : {run('uptime', '-p')}",
        f"Température : {int(temp) / 1000:.1f} °C",
        "Mémoire :\n" + run("free", "-m"),
        f"Carte SD : {st.f_bavail * st.f_frsize / 1e9:.1f} Go libres sur "
        f"{st.f_blocks * st.f_frsize / 1e9:.1f} Go",
        f"Photos : {len(config.list_photos())}",
        f"Réseau : {json.dumps(state, ensure_ascii=False)}",
        f"Réglages : {json.dumps(config.load_settings(), ensure_ascii=False)}",
        f"Album iCloud : {json.dumps(icloud, ensure_ascii=False)}",
        "Services :\n" + run("systemctl", "--no-pager", "--plain", "--no-legend", "list-units",
                             "cadre-*"),
        "Démarrages enregistrés :\n" + run("journalctl", "--no-pager", "--list-boots"),
        "Démarrage :\n" + run("systemd-analyze"),
    ]
    if shutil.which("vcgencmd"):
        lines.append(f"Alimentation (sous-tension) : {run('vcgencmd', 'get_throttled')}")
    return "\n".join(lines)


def build(groups, period, previous_boot, info):
    since = PERIODS.get(period, "-1h")
    parts = [f"Rapport du cadre photo — {time.strftime('%d/%m/%Y %H:%M')}"]
    if info:
        parts.append("== Informations système ==\n" + system_info())
    for key in groups:
        if key not in GROUPS:
            continue
        title, args = GROUPS[key]
        base = ["journalctl", "--no-pager", "-o", "short-iso", "-n", str(MAX_LINES), *args]
        parts.append(f"== {title} — depuis {period} ==\n"
                     + run(*base, "--since", since, timeout=120))
        if previous_boot:
            parts.append(f"== {title} — démarrage précédent ==\n"
                         + run(*base, "-b", "-1", timeout=120))
    return redact("\n\n".join(parts)) + "\n"
