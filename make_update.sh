#!/bin/sh
# Fabrique un fichier de mise à jour signé, pour un cadre installé loin (famille…).
# Usage (Git Bash) : ./make_update.sh ["description des changements"]
#   -> build/cadre-maj-AAAAMMJJ-HHMM.cadre, à installer depuis l'admin (section « Mise à jour »).
# Contenu : le code COMMITÉ (cadre/, systemd/, system/, install.sh) et, s'il existe,
# update/apply.sh (script de migration lancé une fois en root sur le cadre).
# Signature : clé ~/.ssh/id_ed25519_cadre (ou CADRE_SIGN_KEY), vérifiée par le cadre avec la clé
# publique de system/update/allowed_signers ; un fichier modifié ou non signé est refusé.
set -eu
cd "$(dirname "$0")"
KEY=${CADRE_SIGN_KEY:-$HOME/.ssh/id_ed25519_cadre}

if [ -n "$(git status --porcelain -- cadre systemd system install.sh update)" ]; then
    echo "Modifications non commitées (cadre/, systemd/, system/, update/) : commiter d'abord." >&2
    exit 1
fi
STAMP=$(date +%Y%m%d-%H%M)
VERSION="$STAMP $(git rev-parse --short HEAD)"
NOTES=${1:-$(git log -8 --format='- %s')}
OUT=build/cadre-maj-$STAMP.cadre

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
git archive HEAD cadre systemd system install.sh | tar -x -C "$TMP"
MEMBERS="cadre systemd system install.sh"
if git cat-file -e HEAD:update/apply.sh 2>/dev/null; then
    git show HEAD:update/apply.sh > "$TMP/apply.sh"
    MEMBERS="$MEMBERS apply.sh"
fi
printf '%s\n' "$VERSION" > "$TMP/cadre/VERSION"
printf '%s\n' "$NOTES" > "$TMP/cadre/NOTES"
# shellcheck disable=SC2086
tar -czf "$TMP/payload.tar.gz" -C "$TMP" $MEMBERS
ssh-keygen -Y sign -q -f "$KEY" -n cadre-maj "$TMP/payload.tar.gz"
mkdir -p build
tar -cf "$OUT" -C "$TMP" payload.tar.gz payload.tar.gz.sig
echo "Mise à jour $VERSION : $OUT ($(du -k "$OUT" | cut -f1) Ko)"
