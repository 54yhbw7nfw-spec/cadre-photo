#!/bin/sh
# Prépare un essai réseau : sauvegarde des connexions + filet de sécurité au prochain boot.
set -eu
cd "$(dirname "$0")"
mkdir -p /root/nm-backup
cp -a /etc/NetworkManager/system-connections/*.nmconnection /root/nm-backup/
install -m 755 cadre-net-safety /usr/local/sbin/cadre-net-safety
install -m 644 cadre-net-safety.service /etc/systemd/system/cadre-net-safety.service
systemctl daemon-reload
systemctl enable cadre-net-safety.service
ls -l /root/nm-backup
