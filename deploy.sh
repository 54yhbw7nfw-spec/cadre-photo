#!/usr/bin/env bash
# Déploie le code vers le Pi (tar via ssh : rsync n'est pas disponible sous Git Bash).
# Usage : ./deploy.sh [service...]   ex. ./deploy.sh cadre-display
# Les services cités sont redémarrés ; sans argument, seuls ceux déjà actifs le sont.
set -euo pipefail
HOST=${CADRE_HOST:-cadre}
cd "$(dirname "$0")"

tar --exclude=__pycache__ -czf - cadre systemd | ssh "$HOST" "
set -e
sudo install -d -o cadre -g cadre /opt/cadre /var/lib/cadre /var/lib/cadre/photos
sudo rm -rf /opt/cadre/cadre /opt/cadre/systemd  # sudo : __pycache__ de cadre-net (root)
tar -xzf - -C /opt/cadre
changed=0
for f in /opt/cadre/systemd/*.service; do
    dst=/etc/systemd/system/\$(basename \$f)
    cmp -s \$f \$dst || { sudo install -m 644 \$f \$dst; changed=1; }
done
[ \$changed = 1 ] && sudo systemctl daemon-reload
services='$*'
[ -z \"\$services\" ] && services=\$(systemctl list-units --state=active --plain --no-legend 'cadre-*' | awk '{print \$1}')
for s in \$services; do sudo systemctl restart \$s && echo \"redémarré : \$s\"; done
"
