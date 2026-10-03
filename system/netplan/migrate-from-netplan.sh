#!/bin/sh
# Sort les connexions Wi-Fi de netplan vers des fichiers NetworkManager natifs.
# Raison : au démarrage, NetworkManager régénère netplan et recharge systemd 4 fois
# (~20 s chacune sur le Pi Zero) avant d'activer le Wi-Fi.
# À lancer en root depuis le dossier de ce script. N'agit pas sur la connexion active :
# la bascule a lieu au redémarrage suivant, protégé par cadre-net-rollback.
set -eu
cd "$(dirname "$0")"
BACKUP=/root/netplan-backup
CONN_DIR=/etc/NetworkManager/system-connections

ls /etc/netplan/90-NM-*.yaml >/dev/null 2>&1 || { echo "Aucune connexion netplan : rien à faire."; exit 0; }
mkdir -p "$BACKUP"
cp -a /etc/netplan/*.yaml "$BACKUP"/

for src in /run/NetworkManager/system-connections/netplan-wlan0-*.nmconnection; do
    [ -e "$src" ] || continue
    ssid=$(sed -n 's/^ssid=//p' "$src")
    dst="$CONN_DIR/cadre-$(printf %s "$ssid" | tr -c 'A-Za-z0-9_-' '_').nmconnection"
    # Même contenu, avec un nom et un identifiant propres (indépendants de netplan).
    sed -e "s/^id=.*/id=$ssid/" -e "s/^uuid=.*/uuid=$(cat /proc/sys/kernel/random/uuid)/" "$src" > "$dst.tmp"
    chmod 600 "$dst.tmp"
    mv "$dst.tmp" "$dst"
    nmcli connection load "$dst"   # validation : profil chargé à côté de l'actif, sans bascule
    echo "Créé : $dst"
done

rm -f /etc/netplan/90-NM-*.yaml
install -m 755 cadre-net-rollback /usr/local/sbin/cadre-net-rollback
install -m 644 cadre-net-rollback.service /etc/systemd/system/cadre-net-rollback.service
systemctl daemon-reload
systemctl enable cadre-net-rollback.service
nmcli -f NAME,UUID,ACTIVE,FILENAME connection show
