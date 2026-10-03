"""Surveillance réseau (service cadre-net) : publie l'état dans /run/cadre/state.json.

États écrits (lus par le diaporama) :
  {"mode": "connecting"}                                  attente d'un réseau connu
  {"mode": "connected", "ip": ..., "ssid": ..., "since": t}
  {"mode": "offline"}                                     aucun réseau après WAIT_CONNECT
"since" est une horloge monotone (time.monotonic, commune à tous les processus depuis le boot) :
insensible au réglage de l'heure par NTP, qui a lieu justement juste après la connexion.

Étape 3 : lecture seule, ce service ne modifie pas le réseau. Le hotspot viendra à l'étape 4.
"""
import fcntl
import logging
import os
import socket
import struct
import subprocess
import time

from . import config

log = logging.getLogger("cadre.net")

IFACE = os.environ.get("CADRE_WIFI_IFACE", "wlan0")
WAIT_CONNECT = 30   # secondes d'attente d'un réseau connu au démarrage
POLL = 2            # intervalle de surveillance
SIOCGIFADDR = 0x8915


def ipv4(iface):
    """Adresse IPv4 de l'interface, lue directement dans le noyau (pas de processus lancé)."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            req = struct.pack("256s", iface[:15].encode())
            return socket.inet_ntoa(fcntl.ioctl(s.fileno(), SIOCGIFADDR, req)[20:24])
        except OSError:
            return None


def current_ssid(iface):
    try:
        out = subprocess.run(["/usr/sbin/iw", "dev", iface, "link"],
                             capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.TimeoutExpired):
        return None
    for line in out.splitlines():
        if line.strip().startswith("SSID:"):
            return line.split(":", 1)[1].strip()
    return None


class StateWriter:
    def __init__(self):
        os.makedirs(config.RUN_DIR, exist_ok=True)
        self.state = None

    def set(self, mode, **extra):
        state = {"mode": mode, **extra}
        if state == self.state:
            return
        self.state = state
        config.atomic_write_json(config.STATE_FILE, {**state, "since": time.monotonic()})
        log.info("État : %s", state)


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    writer = StateWriter()
    writer.set("connecting")
    lost_at = time.monotonic()  # démarrage = pas encore de connexion

    while True:
        ip = ipv4(IFACE)
        if ip:
            if writer.state.get("ip") != ip:
                writer.set("connected", ip=ip, ssid=current_ssid(IFACE))
            lost_at = None
        else:
            if lost_at is None:
                lost_at = time.monotonic()
                writer.set("connecting")
            elif time.monotonic() - lost_at > WAIT_CONNECT:
                writer.set("offline")
        time.sleep(POLL)


if __name__ == "__main__":
    main()
