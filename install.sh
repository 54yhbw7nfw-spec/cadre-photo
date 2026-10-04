#!/bin/sh
# Installation complète du cadre photo sur une Raspberry Pi OS Lite (trixie) vierge, préparée
# avec Raspberry Pi Imager (utilisateur, Wi-Fi, ssh). Idempotent : peut être relancé.
#
# Depuis le PC (Git Bash) :  ./install.sh [--journal-sd] [hôte ssh]      (défaut : cadre)
#   envoie le dépôt dans /tmp/cadre-install sur le Pi, puis y lance « sudo sh install.sh --local ».
# Sur le Pi, en root :       sh install.sh --local [--journal-sd]   (depuis une copie du dépôt)
#
# --journal-sd : journal conservé sur la carte SD (50 Mo max) pour diagnostiquer un démarrage
#   raté. Sans l'option, journal en RAM (réglage de Raspberry Pi OS, moins d'écritures sur la SD).
#
# Après une première installation : redémarrer le Pi (cmdline.txt, sortie de netplan).
set -eu

LOCAL=0 JOURNAL_SD=0 HOST=${CADRE_HOST:-cadre}
for arg; do
    case $arg in
        --local) LOCAL=1 ;;
        --journal-sd) JOURNAL_SD=1 ;;
        -*) echo "Option inconnue : $arg" >&2; exit 1 ;;
        *) HOST=$arg ;;
    esac
done
OPTS=""
[ $JOURNAL_SD = 1 ] && OPTS="--journal-sd"

if [ $LOCAL = 0 ]; then
    cd "$(dirname "$0")"
    tar --exclude=__pycache__ -czf - install.sh cadre systemd system | ssh "$HOST" "
        set -e
        rm -rf /tmp/cadre-install && mkdir /tmp/cadre-install
        tar -xzf - -C /tmp/cadre-install
        sudo sh /tmp/cadre-install/install.sh --local $OPTS
        rm -rf /tmp/cadre-install"
    exit 0
fi

# --- Sur le Pi --------------------------------------------------------------------------------

[ "$(id -u)" = 0 ] || { echo "À lancer en root (sudo)." >&2; exit 1; }
cd "$(dirname "$0")"
SRC=$(pwd)
REBOOT=0

step() { echo "== $*"; }

# Copie un fichier seulement s'il a changé ; renvoie 0 si copié.
put() {  # put <source> <destination> <mode>
    if [ -e "$2" ] && cmp -s "$1" "$2"; then
        return 1
    fi
    install -D -m "$3" "$1" "$2"
    echo "   installé : $2"
}

step "Paquets"
PKGS="python3-pygame python3-pil libegl1 libegl-mesa0 libgles2 libgl1-mesa-dri
      python3-flask python3-waitress python3-qrcode iw
      network-manager dnsmasq-base wpasupplicant avahi-daemon
      rpi-splash-screen-support file"
MISSING=""
for p in $PKGS; do
    dpkg-query -W -f='${Status}' "$p" 2>/dev/null | grep -q "ok installed" || MISSING="$MISSING $p"
done
if [ -n "$MISSING" ]; then
    echo "   à installer :$MISSING"
    apt-get update
    # shellcheck disable=SC2086
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends $MISSING
else
    echo "   déjà installés"
fi

step "Utilisateur cadre"
if ! id cadre >/dev/null 2>&1; then
    useradd --system --create-home --home-dir /var/lib/cadre --shell /usr/sbin/nologin cadre
    echo "   créé (compte système)"
fi
usermod -a -G video,render,input cadre

step "Code et données"
install -d -o cadre -g cadre /opt/cadre /var/lib/cadre \
    /var/lib/cadre/photos /var/lib/cadre/thumbs /var/lib/cadre/originals
rm -rf /opt/cadre/cadre /opt/cadre/systemd
cp -r "$SRC/cadre" "$SRC/systemd" /opt/cadre/
find /opt/cadre -name __pycache__ -prune -exec rm -rf {} +
chown -R cadre:cadre /opt/cadre

step "Démarrage : sortie HDMI 720p forcée, console masquée"
CMDLINE=/boot/firmware/cmdline.txt
[ -e "$CMDLINE.orig" ] || cp -a "$CMDLINE" "$CMDLINE.orig"
line=$(cat "$CMDLINE")
for opt in video=HDMI-A-1:1280x720@60D vt.global_cursor_default=0 consoleblank=0; do
    case " $line " in
        *" ${opt%%=*}="*) ;;  # option déjà présente (valeur conservée)
        *) line="$line $opt"; REBOOT=1; echo "   ajouté : $opt" ;;
    esac
done
[ "$line" = "$(cat "$CMDLINE")" ] || printf '%s\n' "$line" > "$CMDLINE"

step "Image de démarrage (affichée par le noyau dès les premières secondes)"
TMP=$(mktemp --suffix .tga)
python3 system/splash/make-splash.py "$TMP"
if cmp -s "$TMP" /lib/firmware/logo.tga; then
    echo "   déjà en place"
else
    # Copie l'image, régénère l'initramfs (plusieurs minutes sur le Pi Zero) et adapte
    # cmdline.txt (retire console=tty1, ajoute fullscreen_logo=1).
    [ -e "$CMDLINE.avant-splash" ] || cp -a "$CMDLINE" "$CMDLINE.avant-splash"
    configure-splash "$TMP"
    REBOOT=1
fi
rm -f "$TMP"

step "cloud-init désactivé (ne sert qu'à la première configuration d'Imager)"
if [ -d /etc/cloud ] && [ ! -e /etc/cloud/cloud-init.disabled ]; then
    touch /etc/cloud/cloud-init.disabled
    echo "   désactivé"
fi

step "NetworkManager : Wi-Fi sans économie d'énergie, portail captif"
put system/NetworkManager/99-cadre-wifi.conf /etc/NetworkManager/conf.d/99-cadre-wifi.conf 644 \
    && REBOOT=1 || true
put system/NetworkManager/dnsmasq-shared.d/cadre-captive.conf \
    /etc/NetworkManager/dnsmasq-shared.d/cadre-captive.conf 644 || true

step "Connexions Wi-Fi hors de netplan"
if ls /etc/netplan/90-NM-*.yaml >/dev/null 2>&1; then
    sh system/netplan/migrate-from-netplan.sh
    REBOOT=1
else
    echo "   rien à faire"
fi

# Raspberry Pi OS le force en RAM (/usr/lib/systemd/journald.conf.d/40-rpi-volatile-storage.conf).
JOURNAL_CONF=/etc/systemd/journald.conf.d/50-cadre-persistent.conf
if [ $JOURNAL_SD = 1 ]; then
    step "Journal conservé sur la carte SD (50 Mo max)"
    mkdir -p /var/log/journal
    TMP=$(mktemp)
    printf '[Journal]\nStorage=persistent\nSystemMaxUse=50M\n' > "$TMP"
    if put "$TMP" "$JOURNAL_CONF" 644; then
        systemctl restart systemd-journald
    fi
    rm -f "$TMP"
else
    step "Journal en RAM (option --journal-sd pour le garder sur la carte SD)"
    if [ -e "$JOURNAL_CONF" ]; then
        rm -f "$JOURNAL_CONF"
        rm -rf /var/log/journal
        systemctl restart systemd-journald
        echo "   journal sur la carte SD retiré"
    fi
fi

step "Services"
changed=0
for f in systemd/*.service; do
    put "$f" "/etc/systemd/system/$(basename "$f")" 644 && changed=1 || true
done
[ $changed = 1 ] && systemctl daemon-reload
systemctl enable cadre-display.service cadre-web.service cadre-net.service 2>&1 | sed 's/^/   /'
for s in cadre-display cadre-web cadre-net; do
    # Mise à jour : relance des services actifs ; première installation : ils partiront au
    # redémarrage (cadre-display a besoin de la sortie HDMI forcée).
    systemctl is-active --quiet "$s" && systemctl restart "$s" && echo "   redémarré : $s"
done

echo
if [ $REBOOT = 1 ]; then
    echo "Installation terminée. Redémarrer le Pi pour l'appliquer : sudo reboot"
else
    echo "Installation à jour."
fi
