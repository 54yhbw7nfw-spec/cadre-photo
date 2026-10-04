"""Réseau (service cadre-net, root) : connexion Wi-Fi, hotspot de configuration, commandes.

État publié dans /run/cadre/state.json (lu par le diaporama et l'admin) :
  {"mode": "connecting"}                                   attente d'un réseau connu
  {"mode": "connected", "ip", "ssid"}
  {"mode": "hotspot", "ip", "ap_ssid", "ap_password"}      portail de configuration actif
  {"mode": "offline"}                                      NetworkManager absent
"since" : horloge monotone (commune à tous les processus, insensible au réglage NTP).

Seul ce service modifie le réseau. L'admin web lui envoie des commandes JSON (une ligne)
sur la socket /run/cadre/net.sock (root:cadre 0660) : status, scan, save, connect, forget.

Les réseaux enregistrés sont des fichiers NetworkManager natifs (jamais netplan : sinon
NetworkManager régénère netplan et recharge systemd à chaque démarrage, ~20 s par passe).
Le profil du hotspot est créé en RAM (/run), son mot de passe change à chaque démarrage.
"""
import configparser
import fcntl
import glob
import grp
import json
import logging
import os
import secrets
import socket
import socketserver
import struct
import subprocess
import threading
import time
import uuid

from . import config

log = logging.getLogger("cadre.net")

IFACE = os.environ.get("CADRE_WIFI_IFACE", "wlan0")
AP_SSID = os.environ.get("CADRE_AP_SSID", "CadrePhoto-Setup")
AP_IP = "10.42.0.1"
WAIT_CONNECT = 30    # au démarrage, une fois NetworkManager prêt
LOST_GRACE = 120     # connexion perdue en cours de route : délai avant le hotspot
RETRY_EVERY = 300    # en hotspot sans client : nouvel essai des réseaux connus
ACTIVATE_TIMEOUT = 45
POLL = 2
CONN_DIR = "/etc/NetworkManager/system-connections"
AP_PROFILE = "/run/NetworkManager/system-connections/cadre-hotspot.nmconnection"
AP_UUID = "6a1d0c5e-2f2b-4f8e-9c39-c0ffee000001"
SIOCGIFADDR = 0x8915


# --- Accès système -------------------------------------------------------------------------

def ipv4(iface=IFACE):
    """Adresse IPv4 de l'interface, lue directement dans le noyau (pas de processus lancé)."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            req = struct.pack("256s", iface[:15].encode())
            return socket.inet_ntoa(fcntl.ioctl(s.fileno(), SIOCGIFADDR, req)[20:24])
        except OSError:
            return None


def run(*cmd, timeout=60):
    """Lance une commande ; renvoie (code, sortie). Les arguments ne sont jamais journalisés
    (ils peuvent contenir un mot de passe Wi-Fi)."""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout + p.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return -1, str(exc)


def nm_ready():
    return run("nmcli", "-t", "-f", "RUNNING", "general", timeout=10) == (0, "running")


def current_ssid():
    for line in run("/usr/sbin/iw", "dev", IFACE, "link", timeout=10)[1].splitlines():
        if line.strip().startswith("SSID:"):
            return line.split(":", 1)[1].strip()
    return None


def split_nmcli(line):
    """Découpe une ligne « nmcli -t » : ':' séparateur, '\\:' littéral."""
    fields, cur, esc = [], "", False
    for ch in line:
        if esc:
            cur += ch
            esc = False
        elif ch == "\\":
            esc = True
        elif ch == ":":
            fields.append(cur)
            cur = ""
        else:
            cur += ch
    fields.append(cur)
    return fields


def scan():
    """Réseaux visibles (rafraîchis), du plus fort au plus faible, un par nom."""
    code, out = run("nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY", "device", "wifi", "list",
                    "ifname", IFACE, "--rescan", "yes", timeout=40)
    best = {}
    for line in out.splitlines() if code == 0 else []:
        f = split_nmcli(line)
        if len(f) < 3 or not f[0] or f[0] == AP_SSID:
            continue
        signal = int(f[1]) if f[1].isdigit() else 0
        if f[0] not in best or signal > best[f[0]]["signal"]:
            best[f[0]] = {"ssid": f[0], "signal": signal, "secure": f[2] not in ("", "--")}
    return sorted(best.values(), key=lambda n: -n["signal"])


def saved_networks():
    """Profils Wi-Fi client enregistrés (lus directement : un appel nmcli par profil coûte cher)."""
    nets = []
    for path in sorted(glob.glob(os.path.join(CONN_DIR, "*.nmconnection"))):
        kf = configparser.ConfigParser(interpolation=None, strict=False)
        try:
            kf.read(path)
        except configparser.Error:
            continue
        if kf.get("connection", "type", fallback="") not in ("wifi", "802-11-wireless"):
            continue
        if kf.get("wifi", "mode", fallback="infrastructure") != "infrastructure":
            continue
        nets.append({"uuid": kf.get("connection", "uuid", fallback=""),
                     "ssid": kf.get("wifi", "ssid", fallback=kf.get("connection", "id"))})
    return nets


def keyfile_escape(value):
    """Échappement GKeyFile minimal pour une valeur sur une ligne."""
    value = value.replace("\\", "\\\\")
    return "\\s" + value[1:] if value.startswith(" ") else value


def write_profile(path, sections):
    tmp = path + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        for name, items in sections.items():
            f.write(f"[{name}]\n")
            for k, v in items.items():
                f.write(f"{k}={v}\n")
            f.write("\n")
    os.replace(tmp, path)


def create_client_profile(ssid, password, hidden):
    """Écrit et charge un profil Wi-Fi client ; renvoie son uuid."""
    conn_uuid = str(uuid.uuid4())
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in ssid)[:32]
    path = os.path.join(CONN_DIR, f"cadre-{safe}-{conn_uuid[:8]}.nmconnection")
    sections = {
        "connection": {"id": keyfile_escape(ssid), "uuid": conn_uuid, "type": "wifi",
                       "autoconnect": "true"},
        "wifi": {"mode": "infrastructure", "ssid": keyfile_escape(ssid),
                 "hidden": "true" if hidden else "false"},
        "ipv4": {"method": "auto"},
        "ipv6": {"method": "ignore"},
    }
    if password:
        sections["wifi-security"] = {"key-mgmt": "wpa-psk", "psk": keyfile_escape(password)}
    write_profile(path, sections)
    code, out = run("nmcli", "connection", "load", path)
    if code != 0:
        os.unlink(path)
        raise RuntimeError(f"profil refusé par NetworkManager ({out})")
    return conn_uuid


def delete_profile(conn_uuid):
    run("nmcli", "connection", "delete", "uuid", conn_uuid)


def ap_clients():
    return "Station" in run("/usr/sbin/iw", "dev", IFACE, "station", "dump", timeout=10)[1]


def wifi_qr_escape(value):
    for ch in "\\;,:\"":
        value = value.replace(ch, "\\" + ch)
    return value


# --- Contrôleur ----------------------------------------------------------------------------

class Controller:
    def __init__(self):
        os.makedirs(config.RUN_DIR, exist_ok=True)
        self.lock = threading.RLock()          # une seule opération réseau à la fois
        self.state = {}
        self.networks = []                     # dernier scan (le hotspot empêche de scanner)
        self.result = None                     # résultat de la dernière demande de connexion
        self.busy = False
        # Mot de passe du hotspot : nouveau à chaque démarrage, affiché sur la télé.
        alphabet = "abcdefghjkmnpqrstuvwxyz23456789"
        self.ap_password = "".join(secrets.choice(alphabet) for _ in range(10))

    # État publié
    def publish(self, mode, **extra):
        state = {"mode": mode, **extra}
        if state == self.state:
            return
        self.state = state
        config.atomic_write_json(config.STATE_FILE, {**state, "since": time.monotonic()})
        shown = {k: v for k, v in state.items() if k != "ap_password"}
        log.info("État : %s", shown)

    @property
    def mode(self):
        return self.state.get("mode")

    def set_connected(self, ip):
        self.publish("connected", ip=ip, ssid=current_ssid())

    # Hotspot
    def hotspot_start(self):
        write_profile(AP_PROFILE, {
            "connection": {"id": "cadre-hotspot", "uuid": AP_UUID, "type": "wifi",
                           "autoconnect": "false", "interface-name": IFACE},
            "wifi": {"mode": "ap", "ssid": AP_SSID, "band": "bg", "channel": "6"},
            "wifi-security": {"key-mgmt": "wpa-psk", "proto": "rsn", "pairwise": "ccmp",
                              "group": "ccmp", "pmf": "1", "psk": self.ap_password},
            "ipv4": {"method": "shared", "address1": f"{AP_IP}/24"},
            "ipv6": {"method": "disabled"},
        })
        run("nmcli", "connection", "load", AP_PROFILE)
        code, out = run("nmcli", "-w", "30", "connection", "up", "uuid", AP_UUID)
        if code != 0:
            log.error("Échec du hotspot : %s", out)
            return False
        self.publish("hotspot", ip=AP_IP, ap_ssid=AP_SSID, ap_password=self.ap_password)
        return True

    def hotspot_stop(self):
        run("nmcli", "connection", "down", "uuid", AP_UUID, timeout=30)

    def enter_hotspot(self):
        """Scan AVANT de passer en point d'accès (impossible ensuite), puis hotspot."""
        self.networks = scan()
        log.info("%d réseaux visibles avant le hotspot", len(self.networks))
        if not self.hotspot_start():
            self.publish("offline")

    def wait_ip(self, seconds):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            ip = ipv4()
            if ip and ip != AP_IP:
                return ip
            time.sleep(1)
        return None

    # Commandes de l'admin
    def status(self):
        return {"state": {k: v for k, v in self.state.items() if k != "ap_password"},
                "saved": saved_networks(), "networks": self.networks,
                "busy": self.busy, "result": self.result}

    def do_scan(self):
        if self.mode == "hotspot":
            return {"ok": True, "cached": True}  # scanner couperait le point d'accès
        with self.lock:
            self.networks = scan()
        return {"ok": True}

    def do_save(self, ssid, password, hidden):
        with self.lock:
            for net in saved_networks():
                if net["ssid"] == ssid:
                    delete_profile(net["uuid"])
            create_client_profile(ssid, password, hidden)
        log.info("Réseau enregistré : %s", ssid)
        return {"ok": True}

    def do_connect(self, ssid, password, hidden):
        if self.busy:
            return {"ok": False, "error": "une connexion est déjà en cours"}
        self.busy = True
        self.result = {"ssid": ssid, "status": "en cours"}
        threading.Thread(target=self._connect, args=(ssid, password, hidden), daemon=True).start()
        return {"ok": True}

    def _connect(self, ssid, password, hidden):
        with self.lock:
            try:
                was_hotspot = self.mode == "hotspot"
                previous = None if was_hotspot else run(
                    "nmcli", "-t", "-g", "GENERAL.CONNECTION", "device", "show", IFACE)[1]
                if was_hotspot:
                    self.hotspot_stop()
                self.publish("connecting")
                new_uuid = create_client_profile(ssid, password, hidden)
                code, out = run("nmcli", "-w", str(ACTIVATE_TIMEOUT), "connection", "up",
                                "uuid", new_uuid, timeout=ACTIVATE_TIMEOUT + 15)
                ip = self.wait_ip(20) if code == 0 else None
                if ip:
                    for net in saved_networks():  # remplace les anciens profils du même nom
                        if net["ssid"] == ssid and net["uuid"] != new_uuid:
                            delete_profile(net["uuid"])
                    self.set_connected(ip)
                    self.result = {"ssid": ssid, "status": "connecté", "ip": ip}
                    log.info("Connecté à %s (%s)", ssid, ip)
                    return
                delete_profile(new_uuid)
                self.result = {"ssid": ssid, "status": "échec",
                               "error": "connexion impossible : mot de passe ou signal ?"}
                log.warning("Échec de connexion à %s : %s", ssid, out.splitlines()[-1:] or "")
                if was_hotspot:
                    self.enter_hotspot_after_failure()
                elif previous:
                    run("nmcli", "-w", "30", "connection", "up", "id", previous, timeout=45)
                    ip = self.wait_ip(20)
                    self.set_connected(ip) if ip else self.publish("connecting")
            except Exception as exc:  # ne jamais laisser le cadre sans réseau ni hotspot
                log.exception("Erreur pendant la connexion")
                self.result = {"ssid": ssid, "status": "échec", "error": str(exc)}
                if not ipv4():
                    self.enter_hotspot_after_failure()
            finally:
                self.busy = False

    def enter_hotspot_after_failure(self):
        # Les réseaux connus ont peut-être repris la main entre-temps.
        ip = self.wait_ip(10)
        if ip:
            self.set_connected(ip)
        else:
            self.enter_hotspot()

    def do_forget(self, conn_uuid):
        with self.lock:
            if any(n["uuid"] == conn_uuid for n in saved_networks()):
                delete_profile(conn_uuid)
                return {"ok": True}
        return {"ok": False, "error": "réseau inconnu"}

    # Boucle principale
    def run(self):
        self.publish("connecting")
        while not nm_ready():
            time.sleep(1)
        log.info("NetworkManager prêt")
        ip = self.wait_ip(WAIT_CONNECT)
        with self.lock:
            if ip:
                self.set_connected(ip)
            else:
                self.enter_hotspot()

        lost_at = None
        hotspot_since = time.monotonic()
        while True:
            time.sleep(POLL)
            if not self.lock.acquire(blocking=False):
                continue  # une commande est en cours
            try:
                if self.mode in ("connected", "connecting"):
                    ip = ipv4()
                    if ip and ip != AP_IP:
                        lost_at = None
                        if self.mode != "connected" or ip != self.state.get("ip"):
                            self.set_connected(ip)
                    elif lost_at is None:
                        lost_at = time.monotonic()
                    elif time.monotonic() - lost_at > LOST_GRACE:
                        log.warning("Connexion perdue depuis %d s : hotspot", LOST_GRACE)
                        lost_at = None
                        self.enter_hotspot()
                        hotspot_since = time.monotonic()
                elif self.mode in ("hotspot", "offline"):
                    if (time.monotonic() - hotspot_since > RETRY_EVERY and saved_networks()
                            and not ap_clients()):
                        log.info("Nouvel essai des réseaux connus")
                        self.hotspot_stop()
                        ip = self.wait_ip(WAIT_CONNECT + 10)
                        if ip:
                            self.set_connected(ip)
                        else:
                            self.enter_hotspot()
                        hotspot_since = time.monotonic()
            finally:
                self.lock.release()


# --- Socket de commandes -------------------------------------------------------------------

class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        try:
            req = json.loads(self.rfile.readline(64 * 1024) or b"{}")
            ctl = self.server.controller
            cmd = req.get("cmd")
            ssid = str(req.get("ssid", ""))[:32]
            password = str(req.get("password", ""))
            if cmd == "status":
                resp = ctl.status()
            elif cmd == "scan":
                resp = ctl.do_scan()
            elif cmd in ("save", "connect"):
                if not ssid:
                    resp = {"ok": False, "error": "nom de réseau manquant"}
                elif password and not (8 <= len(password) <= 63 and password.isprintable()):
                    resp = {"ok": False, "error": "mot de passe Wi-Fi : 8 à 63 caractères"}
                else:
                    action = ctl.do_save if cmd == "save" else ctl.do_connect
                    resp = action(ssid, password, bool(req.get("hidden")))
            elif cmd == "forget":
                resp = ctl.do_forget(str(req.get("uuid", "")))
            else:
                resp = {"ok": False, "error": "commande inconnue"}
        except Exception as exc:
            log.exception("Commande en erreur")
            resp = {"ok": False, "error": str(exc)}
        self.wfile.write(json.dumps(resp).encode() + b"\n")


def serve_commands(controller):
    try:
        os.unlink(config.NET_SOCKET)
    except FileNotFoundError:
        pass
    server = socketserver.ThreadingUnixStreamServer(config.NET_SOCKET, Handler)
    server.daemon_threads = True
    server.controller = controller
    os.chown(config.NET_SOCKET, 0, grp.getgrnam("cadre").gr_gid)
    os.chmod(config.NET_SOCKET, 0o660)
    threading.Thread(target=server.serve_forever, name="commandes", daemon=True).start()


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    controller = Controller()
    serve_commands(controller)
    controller.run()


if __name__ == "__main__":
    main()
