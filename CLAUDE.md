# Notes pour Claude Code

- Le code tourne sur le Pi (hôte ssh `cadre`), jamais sur le PC. Déployer avec `./deploy.sh [service]`
  depuis Git Bash, puis vérifier avec `ssh cadre journalctl -u <service>`.
- Toujours mesurer CPU/RAM sur le Pi après un changement d'affichage ou de traitement d'image.
- **Demander validation à l'utilisateur avant toute commande qui modifie le réseau du Pi**
  (nmcli, NetworkManager, hostapd, dnsmasq, avahi, pare-feu…) : risque de perdre l'accès SSH.
- Ne jamais écrire de mot de passe dans le dépôt.
- Fichiers en LF (`.gitattributes`), commentaires et messages en français.
- Tenir à jour la section « Configuration déjà appliquée au Pi » de docs/technique.md : elle sert de
  base à install.sh. Le README est la vitrine du projet (présentation, captures, matériel).
- Aucune trace du nom réel de l'utilisateur dans le dépôt ni dans l'historique : commits signés
  `gtt` (configuré dans ce dépôt), archives envoyées avec `--owner=0`.
- Hors de la maison, le Pi n'est pas à l'adresse de l'alias `cadre` : `ssh -i ~/.ssh/id_ed25519_cadre
  cadre@<ip>`, et pour deploy.sh `CADRE_HOST=cadre@<ip>` avec un `ssh` qui ajoute la clé.
- Une évolution visible (écran, admin) : mettre à jour docs/technique.md, le cahier des charges si
  besoin, les README si elle mérite d'être mise en avant, et refaire les vidéos des 7 langues (`tools/video/`, voir
  docs/technique.md) puis les copier dans docs/video/.
- Textes visibles (admin, écrans du cadre, messages d'erreur) : le français du code sert de clé ;
  ajouter la traduction dans les 6 fichiers `cadre/locales/*.json` et vérifier avec
  `python tools/i18n_check.py` (voir « Langues » dans docs/technique.md).
