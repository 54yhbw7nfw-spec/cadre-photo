# Cadre photo — Raspberry Pi Zero W

Diaporama plein écran sur télé HDMI, administré depuis un navigateur.
Cahier des charges : [docs/cahier-des-charges.md](docs/cahier-des-charges.md).

## Avancement

| Étape | État |
|---|---|
| 1. Diaporama seul | ✅ testé sur le Pi (sans télé : rendu vérifié par les logs) |
| 2. Admin web Flask | à faire |
| 3. QR code au boot | à faire |
| 4. Hotspot / portail captif | à faire |
| 5. install.sh | à faire |

## Arborescence

```
cadre/               paquet Python déployé dans /opt/cadre/cadre
  config.py          chemins, réglages JSON (lecture/écriture atomique), liste des photos
  display.py         diaporama (service cadre-display)
systemd/             unités copiées dans /etc/systemd/system par deploy.sh
tools/               outils côté PC (photos de test)
deploy.sh            envoi du code vers le Pi + redémarrage des services
```

Sur le Pi :

| Chemin | Contenu |
|---|---|
| `/opt/cadre/` | code (propriétaire `cadre`) |
| `/var/lib/cadre/photos/` | photos prêtes à afficher (≤ 1280x720, JPEG) |
| `/var/lib/cadre/settings.json` | réglages, relus à chaud toutes les 2 s |

## Travailler depuis VS Code

Le terminal intégré est Git Bash. Tâches (`Ctrl+Maj+P` → *Tasks: Run Task*, ou `Ctrl+Maj+B`
pour déployer) :

- **Déployer** — `./deploy.sh` : envoie `cadre/` et `systemd/` (tar via ssh, rsync absent sous
  Windows), installe les unités modifiées, redémarre les services actifs ;
  `./deploy.sh cadre-display` redémarre le service cité.
- **Logs** — `journalctl -f` des services sur le Pi.
- **État du Pi** — services, RAM, charge, température.
- **Envoyer les photos de test** — génère des photos synthétiques et les copie sur le Pi.

## Accès au Pi

- Hôte ssh `cadre` défini dans `~/.ssh/config` : `192.168.1.20`, utilisateur `cadre`,
  clé `~/.ssh/id_ed25519_cadre`.
- `sudo` sans mot de passe pour `cadre` (`/etc/sudoers.d/010_cadre-nopasswd`).

## Configuration déjà appliquée au Pi (à reprendre dans install.sh)

- Paquets : `python3-pygame python3-pil libegl1 libegl-mesa0 libgles2 libgl1-mesa-dri`
  (`--no-install-recommends`).
- `/boot/firmware/cmdline.txt` (sauvegarde `cmdline.txt.orig`) :
  `video=HDMI-A-1:1280x720@60D vt.global_cursor_default=0 consoleblank=0`.
  Le `D` force la sortie HDMI même sans télé branchée ou éteinte au boot ; sans cela SDL
  refuse KMSDRM (« kmsdrm not available »).
- Service `cadre-display` activé (remplace getty sur tty1).

## Choix techniques du diaporama

- Rendu GPU via `pygame._sdl2.video` (Renderer/Texture), pilote forcé `opengles2` : le
  pilote `opengl` par défaut ne gère pas les textures cibles sur VC4.
- Chaque photo est décodée une fois puis envoyée au GPU ; le letterbox est composé sur le GPU
  (texture cible). Les transitions ne font que déplacer/mélanger des textures.
- La photo suivante est préchargée pendant l'affichage de la courante.
- Les photos ajoutées passent en tête de file ; un fichier illisible est écarté tant qu'il
  existe.

### Mesures sur le Pi Zero W

| Mesure | Valeur |
|---|---|
| Transitions | 60 i/s (vsync), coût CPU non mesurable |
| Photo 720p (format après upload) | ~150 ms décodage + ~100 ms envoi GPU |
| Photo 12 Mpx brute | 1,3 à 3 s (d'où le pré-redimensionnement à l'upload) |
| CPU moyen, délai 10 s | ~7 % avec photos de test brutes, ~3 % attendu avec photos prêtes |
| Mémoire | 25 Mo privés (RSS 81 Mo dont bibliothèques partagées) |
