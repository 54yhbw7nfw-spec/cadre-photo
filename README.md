# Cadre photo — Raspberry Pi Zero W

Diaporama plein écran sur télé HDMI, administré depuis un navigateur.
Cahier des charges : [docs/cahier-des-charges.md](docs/cahier-des-charges.md).

## Avancement

| Étape | État |
|---|---|
| 1. Diaporama seul | ✅ testé sur le Pi (sans télé : rendu vérifié par les logs) |
| 2. Admin web Flask | ✅ testé par API (20 photos 12 Mpx) et depuis un navigateur |
| 3. QR code au boot | ✅ testé sur la télé ; Wi-Fi connecté à ~100 s après la mise sous tension |
| 4. Hotspot / portail captif | ✅ testé avec un iPhone : portail ouvert tout seul, Wi-Fi de la maison reconnecté en 5 s |
| 6. Album iCloud partagé | ✅ testé (album récent, 10 photos dont 3 HEIC) — ancien format de lien non testé |
| 5. install.sh | écrit — à tester : relance sur le Pi actuel, puis carte SD vierge |

## Arborescence

```
cadre/               paquet Python déployé dans /opt/cadre/cadre
  config.py          chemins, réglages JSON (lecture/écriture atomique), liste des photos
  display.py         diaporama (service cadre-display)
  imaging.py         traitement des photos reçues (draft JPEG, EXIF, miniature)
  web.py             admin web Flask servi par waitress (service cadre-web)
  icloud.py          lecture d'un album partagé iCloud public (API non officielles)
  splash.py          écran de démarrage dans /dev/fb0 (service cadre-splash)
  net.py             surveillance réseau, état dans /run/cadre/state.json (service cadre-net)
  templates/         page unique de l'admin (HTML/CSS/JS sans framework)
system/              fichiers de configuration système (repris par install.sh)
systemd/             unités copiées dans /etc/systemd/system par deploy.sh
tools/               outils côté PC (photos de test)
deploy.sh            envoi du code vers le Pi + redémarrage des services
install.sh           installation complète sur une Raspberry Pi OS Lite vierge (idempotent)
```

Sur le Pi :

| Chemin | Contenu |
|---|---|
| `/opt/cadre/` | code (propriétaire `cadre`) |
| `/var/lib/cadre/photos/` | photos prêtes à afficher (≤ 1280x720, JPEG) |
| `/var/lib/cadre/thumbs/` | miniatures 320x180 de l'admin |
| `/var/lib/cadre/originals/` | originaux, si l'option est cochée |
| `/var/lib/cadre/settings.json` | réglages, relus à chaud toutes les 2 s |
| `/var/lib/cadre/icloud.json` | album iCloud suivi : lien, titre, identifiant iCloud → photo du cadre |
| `/var/lib/cadre/auth.json` | empreinte du mot de passe admin (absent = pas d'authentification) |
| `/run/cadre-web/incoming/` | fichiers reçus en attente de traitement (RAM) |

Mot de passe de l'admin (optionnel, authentification HTTP Basic) : sur le Pi,
`cd /opt/cadre && python3 -m cadre.web --set-password` (ou `--clear-password`).

## Installation sur un Pi neuf

1. Raspberry Pi Imager : Raspberry Pi OS Lite (trixie), nom d'hôte `cadre`, utilisateur `cadre`,
   Wi-Fi de la maison, ssh par clé.
2. Hôte `cadre` dans `~/.ssh/config` (voir « Accès au Pi »).
3. Depuis Git Bash : `./install.sh` (ou `./install.sh <hôte>`), puis `ssh cadre sudo reboot`.
   `--journal-sd` garde le journal sur la carte SD (50 Mo max) pour diagnostiquer un démarrage
   raté ; sans l'option il reste en RAM (moins d'écritures sur la SD), et l'option est retirée
   si elle avait été appliquée.

Le script reprend toute la « Configuration déjà appliquée au Pi » ; relancé, il ne refait que ce
qui manque ou a changé. Il ne touche jamais à une connexion active : la sortie de netplan prend
effet au redémarrage, protégée par `cadre-net-rollback`.

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
  `video=HDMI-A-1:1280x720@60D vt.global_cursor_default=0 consoleblank=0 quiet`
  (`quiet` : rien par-dessus l'écran de démarrage ; sauvegarde `cmdline.txt.avant-quiet`).
  Le `D` force la sortie HDMI même sans télé branchée ou éteinte au boot ; sans cela SDL
  refuse KMSDRM (« kmsdrm not available »).
- Paquet `python3-qrcode`.
- Services `cadre-splash`, `cadre-display`, `cadre-web` (port 80) et `cadre-net` activés ;
  `getty@tty1` désactivé (tty1 appartient à l'écran de démarrage puis au diaporama).
- Connexion Wi-Fi sortie de netplan : `/etc/NetworkManager/system-connections/cadre-<ssid>.nmconnection`
  (fichier NetworkManager natif, 0600), sauvegarde netplan dans `/root/netplan-backup/`.
  Script : `system/netplan/migrate-from-netplan.sh`, protégé au redémarrage suivant par
  `cadre-net-rollback` (restaure netplan si pas de passerelle en 5 min, puis se désactive).
- cloud-init désactivé (`/etc/cloud/cloud-init.disabled`) : il ne servait qu'à la première
  configuration par Raspberry Pi Imager et bloquait chaque démarrage ~1 min.
- Économie d'énergie Wi-Fi désactivée : `system/NetworkManager/99-cadre-wifi.conf` copié dans
  `/etc/NetworkManager/conf.d/` (débit d'upload ×2, plus de coupures).
- Portail captif : `system/NetworkManager/dnsmasq-shared.d/cadre-captive.conf` copié dans
  `/etc/NetworkManager/dnsmasq-shared.d/` (le dnsmasq du hotspot répond 10.42.0.1 à tous les noms).
- Journal conservé sur la carte SD (option `--journal-sd` d'install.sh ; sinon journal en RAM,
  réglage de Raspberry Pi OS via
  `/usr/lib/systemd/journald.conf.d/40-rpi-volatile-storage.conf`) :
  `/etc/systemd/journald.conf.d/50-cadre-persistent.conf` = `[Journal]` `Storage=persistent`
  `SystemMaxUse=50M`, et dossier `/var/log/journal`.

## Démarrage et QR code

- `cadre-net` lit l'IP de `wlan0` directement dans le noyau (ioctl, aucun processus lancé) et
  publie `connecting` / `connected` (ip, ssid) / `offline` (rien après 30 s) dans
  `/run/cadre/state.json`, avec une date en horloge monotone (insensible au réglage NTP).
- Le diaporama donne priorité aux écrans réseau : « Connexion au Wi-Fi... » (seulement avant la
  première connexion), puis QR code `http://<ip>/` + `cadre.local` pendant 20 s, de nouveau si
  l'adresse change.
- Sortie forcée en 1280x720 (plein écran exclusif) : sinon SDL garde le mode préféré de la télé.
- Écran de démarrage `cadre-splash` (root, lancé dès que le journal tourne) : image « Cadre
  photo » et 4 derniers messages de systemd dessinés dans `/dev/fb0`, redessinés quand vc4
  remplace le framebuffer du firmware ; arrêt quand le diaporama a pris l'écran (message
  « Affichage KMSDRM »). Mesuré : image à 31 s, diaporama à 86 s, Wi-Fi à 108 s, sans écran noir ;
  6 s de CPU pendant le démarrage. Sans getty sur tty1, le diaporama démarre ~25 s plus tôt.
- Écarté : l'image de démarrage du noyau (`rpi-splash-screen-support`, `fullscreen_logo=1`).
  L'image s'affiche dès la mise sous tension, mais le Pi Zero W se bloque ensuite (2 démarrages
  sur 2, sans trace dans le journal) ; retour à l'état antérieur par la carte SD.
- Démarrage mesuré (secondes depuis la mise sous tension) : `cadre-net` 63 s, écran 80 s,
  Wi-Fi connecté et QR code 103 s. Avant : 158 s / 177 s / 160 s. Gains : cloud-init désactivé,
  services cadre lancés sans attendre le réseau, et surtout sortie de netplan (NetworkManager
  régénérait netplan et rechargeait systemd 4 fois, 20 s chacune : 1 min 33 → 35 s).
- Le délai de 30 s avant le hotspot part du moment où NetworkManager est prêt (et non plus du
  lancement de `cadre-net`, qui le faisait partir à tort).

## Hotspot et portail captif

- Sans réseau connu 30 s après NetworkManager : scan des réseaux, puis point d'accès
  `CadrePhoto-Setup` (10.42.0.1, WPA2, mot de passe aléatoire à chaque démarrage). La télé affiche
  QR code Wi-Fi + mot de passe tant que le hotspot est actif. Mesuré : hotspot à 140 s après la
  mise sous tension.
- Pi Zero W (puce BCM43430, micrologiciel 7.45.98) : NetworkManager 1.52 configure le point
  d'accès en `WPA-PSK WPA-PSK-SHA256`, même avec `pmf=disable` ; le téléphone abandonne alors au
  message 3/4 de l'échange de clés et affiche « mot de passe incorrect ». `cadre-net` remet
  `WPA-PSK` seul par `wpa_cli` juste après le démarrage du hotspot (`ap_wpa2_psk_only`).
- Portail : tous les noms pointent vers le Pi ; toute page d'un autre hôte est redirigée vers
  `/wifi`. L'iPhone ouvre la page tout seul (test `captive.apple.com/hotspot-detect.html`). Les
  pages demandées en mode hotspot sont journalisées (`Portail : ...` dans `cadre-web`).
- « Se connecter » coupe le hotspot, essaie le réseau (45 s), remplace l'ancien profil du même
  nom si ça marche, sinon relance le hotspot. Sans client, nouvel essai des réseaux connus toutes
  les 5 min.
- L'admin affiche un bandeau tant que le cadre n'est connecté à aucun Wi-Fi.
- Essais réseau : `system/safety/arm.sh` sauvegarde les connexions et arme `cadre-net-safety`
  (usage unique) : sans passerelle 10 min après le démarrage, il restaure la sauvegarde et
  redémarre. Pour simuler l'absence de réseau connu :
  `sudo nmcli connection modify <réseau> connection.autoconnect no && sudo reboot`.
- Mesures (connecté, diaporama en cours) : RAM utilisée 186 Mo / 427 (241 Mo disponibles) ;
  RSS `cadre-display` 78 Mo, `cadre-web` 28 Mo, `cadre-net` 15 Mo.

## Admin web

- Espace libre affiché en haut (pourcentage et Go). Marge gardée pour le système :
  5 % de la carte, 1 Go minimum ; en dessous l'envoi répond 507, le navigateur arrête le lot et
  un bandeau demande de supprimer des photos.
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

## Album iCloud partagé

- Lien collé dans l'admin ; l'album doit avoir « Site web public » activé. Synchronisation par un
  thread de `cadre-web` 2 min après le lancement puis toutes les 30 min (bouton pour forcer),
  sauf en mode hotspot.
- Album récent (`photos.icloud.com/shared/album/<code>`) : CloudKit sans compte.
  `public/records/resolve` (code) → zone + jeton anonyme 20 min ; `shared/records/query`
  (`CPLAssetAndMasterByAssetDateWithoutHiddenOrDeleted`, paramètres `sharing_url_key` et
  `publicAccessAuthToken`) → `CPLAsset` (date, retouche) et `CPLMaster` (fichiers). Fichier
  choisi : retouche (`resJPEGFullRes`), sinon JPEG 2048 px d'Apple (`resJPEGMedRes`, fourni pour
  les HEIC, déjà redressé), sinon original JPEG/PNG. Vidéos ignorées.
- Ancien album (`www.icloud.com/sharedalbum/#<jeton>`) : `sharedstreams` webstream +
  webasseturls (réponse 330 = autre serveur) ; plus grande version ≤ 2560 px. Non testé faute
  d'album de ce type.
- Photos traitées comme un envoi (`imaging.process`, signature `icloud:<id>`), un seul traitement
  à la fois avec la file de l'admin. Photo retirée de l'album → supprimée du cadre ; changement
  d'album → photos de l'ancien retirées ; photo de l'album supprimée dans l'admin → pas
  retéléchargée. Photos de l'admin jamais touchées (pas de détection de doublon entre les deux).
- Mesuré : 10 photos ajoutées en 28 s, synchronisation sans nouveauté en 2 s.

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
