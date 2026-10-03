# Cadre photo — Raspberry Pi Zero W

Diaporama plein écran sur télé HDMI, administré depuis un navigateur.
Cahier des charges : [docs/cahier-des-charges.md](docs/cahier-des-charges.md).

## Avancement

| Étape | État |
|---|---|
| 1. Diaporama seul | ✅ testé sur le Pi (sans télé : rendu vérifié par les logs) |
| 2. Admin web Flask | ✅ testé par API (20 photos 12 Mpx) — test navigateur à faire |
| 3. QR code au boot | ✅ testé sur la télé (démarrage encore lent : netplan, voir ci-dessous) |
| 4. Hotspot / portail captif | à faire |
| 5. install.sh | à faire |

## Arborescence

```
cadre/               paquet Python déployé dans /opt/cadre/cadre
  config.py          chemins, réglages JSON (lecture/écriture atomique), liste des photos
  display.py         diaporama (service cadre-display)
  imaging.py         traitement des photos reçues (draft JPEG, EXIF, miniature)
  web.py             admin web Flask servi par waitress (service cadre-web)
  net.py             surveillance réseau, état dans /run/cadre/state.json (service cadre-net)
  templates/         page unique de l'admin (HTML/CSS/JS sans framework)
system/              fichiers de configuration système (repris par install.sh)
systemd/             unités copiées dans /etc/systemd/system par deploy.sh
tools/               outils côté PC (photos de test)
deploy.sh            envoi du code vers le Pi + redémarrage des services
```

Sur le Pi :

| Chemin | Contenu |
|---|---|
| `/opt/cadre/` | code (propriétaire `cadre`) |
| `/var/lib/cadre/photos/` | photos prêtes à afficher (≤ 1280x720, JPEG) |
| `/var/lib/cadre/thumbs/` | miniatures 320x180 de l'admin |
| `/var/lib/cadre/originals/` | originaux, si l'option est cochée |
| `/var/lib/cadre/settings.json` | réglages, relus à chaud toutes les 2 s |
| `/var/lib/cadre/auth.json` | empreinte du mot de passe admin (absent = pas d'authentification) |
| `/run/cadre-web/incoming/` | fichiers reçus en attente de traitement (RAM) |

Mot de passe de l'admin (optionnel, authentification HTTP Basic) : sur le Pi,
`cd /opt/cadre && python3 -m cadre.web --set-password` (ou `--clear-password`).

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

- Paquets : `python3-pygame python3-pil libegl1 libegl-mesa0 libgles2 libgl1-mesa-dri
  python3-flask python3-waitress iw` (`--no-install-recommends`).
- `/boot/firmware/cmdline.txt` (sauvegarde `cmdline.txt.orig`) :
  `video=HDMI-A-1:1280x720@60D vt.global_cursor_default=0 consoleblank=0`.
  Le `D` force la sortie HDMI même sans télé branchée ou éteinte au boot ; sans cela SDL
  refuse KMSDRM (« kmsdrm not available »).
- Paquet `python3-qrcode`.
- Services `cadre-display` (remplace getty sur tty1), `cadre-web` (port 80) et `cadre-net` activés.
- cloud-init désactivé (`/etc/cloud/cloud-init.disabled`) : il ne servait qu'à la première
  configuration par Raspberry Pi Imager et bloquait chaque démarrage ~1 min.
- Économie d'énergie Wi-Fi désactivée : `system/NetworkManager/99-cadre-wifi.conf` copié dans
  `/etc/NetworkManager/conf.d/` (débit d'upload ×2, plus de coupures).

## Démarrage et QR code

- `cadre-net` lit l'IP de `wlan0` directement dans le noyau (ioctl, aucun processus lancé) et
  publie `connecting` / `connected` (ip, ssid) / `offline` (rien après 30 s) dans
  `/run/cadre/state.json`, avec une date en horloge monotone (insensible au réglage NTP).
- Le diaporama donne priorité aux écrans réseau : « Connexion au Wi-Fi... » (seulement avant la
  première connexion), puis QR code `http://<ip>/` + `cadre.local` pendant 20 s, de nouveau si
  l'adresse change.
- Sortie forcée en 1280x720 (plein écran exclusif) : sinon SDL garde le mode préféré de la télé.
- Démarrage mesuré : écran allumé à ~80 s, mais Wi-Fi connecté seulement vers 2 min 30 :
  NetworkManager régénère la configuration netplan et recharge systemd 4 fois (20 s chacune).

## Admin web

- Le navigateur réduit chaque photo à 2560x1440 max (orientation EXIF appliquée, JPEG 0,9) avant
  l'envoi, sauf si « Conserver les originaux » est coché. L'EXIF étant perdu, il envoie à part la
  date de prise de vue (`taken`) et une signature nom|taille|date du fichier (`sig`) qui sert à
  détecter les doublons. La photo suivante est préparée pendant l'envoi de la courante.
- Envoi séquentiel, 6 essais avec pauses croissantes (Wi-Fi faible) ; le serveur range chaque fichier en RAM et répond
  503 quand la file dépasse 40 Mo (le navigateur réessaie). Un thread traite un fichier à la fois,
  avec `Nice=10` et E/S en priorité basse pour ne pas saccader le diaporama.
- Nom des photos `AAAAMMJJ-HHMMSS_<empreinte>.jpg` : date de prise de vue EXIF (sinon date de
  réception) → ordre chronologique en mode non aléatoire ; empreinte → doublons ignorés et
  miniatures mises en cache par le navigateur.
- Écriture atomique (fichier caché + renommage) : le diaporama ne voit jamais de photo partielle.

| Mesure (Pi Zero W) | Valeur |
|---|---|
| Traitement d'une photo réduite par le navigateur | 0,3 à 0,7 s |
| Traitement d'une photo 12 Mpx (originaux conservés) | 1,4 à 2,1 s (médiane), 5 s max |
| 20 photos 12 Mpx de bout en bout | 85 s / 12 Mo réduites, contre 308 s / 60 Mo en originaux |
| Diaporama pendant le traitement | 59,5 i/s médiane, 52 i/s au pire |
| Mémoire de l'admin | 31 Mo (pic 44 Mo) |
| Débit d'upload actuel | ~200 à 500 Ko/s : signal Wi-Fi faible (-80 dBm) à l'emplacement du Pi |

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
