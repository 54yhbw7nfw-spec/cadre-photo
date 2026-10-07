#!/bin/sh
# Script de migration des mises à jour (lancé une fois, en root, dans /opt/cadre).
# Cumulatif et relançable : un cadre en retard de plusieurs versions ne lance que celui-ci.
# Voir docs/mise-a-jour.md.

# 20261007 : police chinoise (écrans en chinois). Sans Internet ou en cas d'échec, la mise à
# jour continue : seul le chinois s'affiche alors en carrés.
if ! dpkg -s fonts-wqy-microhei >/dev/null 2>&1; then
    apt-get install -y --no-install-recommends fonts-wqy-microhei \
        || { apt-get update && apt-get install -y --no-install-recommends fonts-wqy-microhei; } \
        || echo "police chinoise non installée"
fi
exit 0
