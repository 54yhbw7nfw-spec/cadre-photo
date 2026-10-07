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
# 20261007 : police arabe (DejaVu Sans, écrans en arabe), même principe.
if ! dpkg -s fonts-dejavu-core >/dev/null 2>&1; then
    apt-get install -y --no-install-recommends fonts-dejavu-core \
        || { apt-get update && apt-get install -y --no-install-recommends fonts-dejavu-core; } \
        || echo "police arabe non installée"
fi
# 20261007 : vidéos de l'album (lecture GStreamer, redressement ffmpeg, ~100 Mo). Sans
# Internet, la mise à jour continue : les vidéos restent alors affichées comme des photos.
VIDEO_PKGS="ffmpeg python3-gi gir1.2-gstreamer-1.0 gir1.2-gst-plugins-base-1.0
  gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-libav gstreamer1.0-alsa"
if ! dpkg -s $VIDEO_PKGS >/dev/null 2>&1; then
    apt-get install -y --no-install-recommends $VIDEO_PKGS \
        || { apt-get update && apt-get install -y --no-install-recommends $VIDEO_PKGS; } \
        || echo "paquets vidéo non installés"
fi
exit 0
