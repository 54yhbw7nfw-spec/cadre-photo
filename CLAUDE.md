# Notes pour Claude Code

- Le code tourne sur le Pi (hôte ssh `cadre`), jamais sur le PC. Déployer avec `./deploy.sh [service]`
  depuis Git Bash, puis vérifier avec `ssh cadre journalctl -u <service>`.
- Toujours mesurer CPU/RAM sur le Pi après un changement d'affichage ou de traitement d'image.
- **Demander validation à l'utilisateur avant toute commande qui modifie le réseau du Pi**
  (nmcli, NetworkManager, hostapd, dnsmasq, avahi, pare-feu…) : risque de perdre l'accès SSH.
- Ne jamais écrire de mot de passe dans le dépôt.
- Fichiers en LF (`.gitattributes`), commentaires et messages en français.
- Tenir à jour la section « Configuration déjà appliquée au Pi » du README : elle sert de base à install.sh.
