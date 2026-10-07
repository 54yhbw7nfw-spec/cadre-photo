# Cadre photo — documentation technique

Pour développer, déployer et dépanner le cadre. Présentation du projet : [README](../README.md) ;
cahier des charges : [cahier-des-charges.md](cahier-des-charges.md) ; mise à jour à distance :
[mise-a-jour.md](mise-a-jour.md).

## Avancement

| Étape | État |
|---|---|
| 1. Diaporama seul | ✅ testé sur le Pi (sans télé : rendu vérifié par les logs) |
| 2. Admin web Flask | ✅ testé par API (20 photos 12 Mpx) et depuis un navigateur |
| 3. QR code au boot | ✅ testé sur la télé ; Wi-Fi connecté à ~100 s après la mise sous tension |
| 4. Hotspot / portail captif | ✅ testé avec un iPhone : portail ouvert tout seul, Wi-Fi de la maison reconnecté en 5 s |
| 5. install.sh | ✅ testé sur une carte SD vierge (Raspberry Pi OS Lite trixie) : cadre complet au 1er redémarrage |
| 6. Album iCloud partagé | ✅ testé (album récent, 23 photos dont des HEIC) — ancien format de lien non testé |
| 7. Écrans de démarrage et d'arrêt, Redémarrer / Éteindre | ✅ testés sur la télé |
| 8. Télécommande (HDMI-CEC), veille programmée, date | ✅ testés sur une Samsung |
| 9. Admin : connexion, mot de passe, espace libre, liseré iCloud | ✅ |
| 10. Lieu des photos (OpenStreetMap, sinon hors ligne) | ✅ testé (album iCloud) |
| 11. Rapport de diagnostic | ✅ testé (4 s, 360 Ko) |
| 12. Mise à jour à distance (fichier signé, retour arrière) | ✅ 5 cas testés, dont une version cassée |
| 13. Message sur le cadre (bandeau ou écran, entre deux dates) | ✅ livré par mise à jour signée |
| 14. Souvenirs « ce jour-là » | ✅ testé (photos datées d'un 6 octobre passé) |
| 15. Nouveautés à l'honneur (pictogramme « nouveau ») | ✅ testé |
| 16. Favoris et photos masquées | livré par mise à jour signée, à tester |
| 17. Choix des photos affichées (source, période) | livré par mise à jour signée, à tester |
| 18. Heure et météo (Open-Meteo), icônes dessinées | livré par mise à jour signée, à tester |
| 19. Mise à jour depuis un lien (release GitHub), sur demande | ✅ cas d'erreur testés ; release à tester |
| 20. Traduction : admin et écrans en 9 langues (fr, en, es, de, pt, ro, ru, ar, zh) | ✅ testé sur le Pi (écrans rendus dans chaque langue, admin en chinois) |
| Mode d'emploi vidéo (9 langues) | ✅ `docs/video/`, à refaire après une évolution visible |

## Reste à faire / idées

- Album iCloud : tester un lien de l'ancien format (`www.icloud.com/sharedalbum/#B0…`).
- Doublons entre photos de l'admin et de l'album iCloud non détectés (réductions différentes).
- Lieu : impossible pour les photos déjà envoyées sans position (WhatsApp, ou réduites avant
  cette fonction) ; il faut renvoyer les originaux.
- Raspberry Pi Zero 2 W : démarrage ~3 fois plus rapide, 1080p envisageable.
- Garde-fou de mise à jour : il ne vérifie que les services et l'admin ; une régression plus
  discrète se corrige avec « Revenir à la version précédente ».

## Arborescence

```
cadre/               paquet Python déployé dans /opt/cadre/cadre
  config.py          chemins, réglages JSON (lecture/écriture atomique), liste des photos
  display.py         diaporama (service cadre-display)
  imaging.py         traitement des photos reçues (draft JPEG, EXIF, miniature)
  web.py             admin web Flask servi par waitress (service cadre-web)
  icloud.py          lecture d'un album partagé iCloud public (API non officielles)
  places.py          lieu des photos (OpenStreetMap, sinon data/villes.tsv.gz hors ligne)
  report.py          rapport de diagnostic (fabriqué par cadre-net, root)
  update.py          mise à jour à distance : vérification, installation, garde-fou
  splash.py          écran de démarrage dans /dev/fb0 (service cadre-splash)
  net.py             surveillance réseau, état dans /run/cadre/state.json (service cadre-net)
  templates/         page unique de l'admin (HTML/CSS/JS sans framework)
system/              fichiers de configuration système (repris par install.sh)
systemd/             unités copiées dans /etc/systemd/system par deploy.sh
tools/               outils côté PC (photos de test)
deploy.sh            envoi du code vers le Pi + redémarrage des services
make_update.sh       fichier de mise à jour signé (.cadre) pour un cadre installé loin
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
| `/var/lib/cadre/flags.json` | photos favorites et masquées |
| `/var/lib/cadre/weather.json` | ville de la météo et dernière relève |
| `/var/lib/cadre/message.json` | message affiché sur le cadre (texte, dates de début et de fin, mode) |
| `/var/lib/cadre/places.json` | lieu de chaque photo (« Ville, Pays ») |
| `/var/lib/cadre/icloud.json` | album iCloud suivi : lien, titre, identifiant iCloud → photo du cadre |
| `/var/lib/cadre/auth.json` | empreinte du mot de passe admin (absent = pas d'authentification) |
| `/run/cadre-web/incoming/` | fichiers reçus en attente de traitement (RAM) |

Mot de passe de l'admin (optionnel) : dans l'admin (section « Mot de passe de l'admin ») ou sur le
Pi `cd /opt/cadre && python3 -m cadre.web --set-password` (ou `--clear-password`). Page de
connexion (utilisateur « admin » prérempli), cookie de session signé valable 30 jours
(clé `/var/lib/cadre/secret_key`) ; changer le mot de passe déconnecte les autres navigateurs.
Le portail Wi-Fi du hotspot reste accessible sans mot de passe.

## Installation sur un Pi neuf

1. Raspberry Pi Imager : Raspberry Pi OS Lite (trixie), nom d'hôte `cadre`, utilisateur `cadre`,
   Wi-Fi de la maison, ssh par clé.
2. Hôte `cadre` dans `~/.ssh/config` (voir « Accès au Pi »).
3. Depuis Git Bash : `./install.sh` (ou `CADRE_SSH_KEY=~/.ssh/id_ed25519_cadre ./install.sh cadre@<ip>`),
   puis `ssh cadre sudo reboot`. Le mot de passe de `cadre` (choisi dans Imager) est demandé une
   fois : le script configure ensuite sudo sans mot de passe (deploy.sh). Coller la clé publique
   `id_ed25519_cadre.pub` dans Imager (SSH par clé).
   `--journal-sd` garde le journal sur la carte SD (50 Mo max) pour diagnostiquer un démarrage
   raté ; sans l'option il reste en RAM (moins d'écritures sur la SD), et l'option est retirée
   si elle avait été appliquée.

Test du 2026-10-06 (carte neuve, Pi Zero W, Wi-Fi du bureau) : installation ~25 min, dont les
paquets ; le répartiteur Raspbian renvoyait vers un miroir en 404 (`mirror.pyratelan.org`), d'où
le 2e essai par `ftp.halifax.rwth-aachen.de`. Au redémarrage : écran de démarrage à 31 s,
diaporama à 88 s, Wi-Fi à 110 s (hors netplan, filet retiré à 112 s), 180 Mo de RAM utilisés.

Le script reprend toute la « Configuration déjà appliquée au Pi » ; relancé, il ne refait que ce
qui manque ou a changé. Il ne touche jamais à une connexion active : la sortie de netplan prend
effet au redémarrage, protégée par `cadre-net-rollback`.

## Mode d'emploi vidéo

Une vidéo par langue dans `docs/video/` : `cadre-photo-mode-d-emploi.mp4` (français) et
`cadre-photo-mode-d-emploi-<langue>.mp4` (en, es, de, pt, ro, ru, ar, zh) ; copies de `build/video/…`,
~5 min, 18 diapositives commentées, voix neuronales Microsoft via `edge-tts` (Denise, Sonia,
Elvira, Katja, Raquel, Alina, Svetlana, Zariyah, Xiaoxiao ; Internet requis). Pour les refaire, sur le PC, pour
chaque langue :
1. `python tools/video/shots.py http://<ip du cadre> build/video/shots-<langue> <langue>`
   (captures de l'admin, Firefox sans fenêtre ; le temps des captures, la langue du cadre et la
   ville de la météo sont changées sur le cadre, puis remises ; lien de l'album iCloud, réseaux
   Wi-Fi et notes de mise à jour floutés par une feuille de style) ;
2. `tools/video/screens.py <sortie> <langue>` lancé sur le Pi (`PYTHONPATH=/opt/cadre
   SDL_VIDEODRIVER=dummy`), résultat copié dans `build/video/ecrans-<langue>` (écrans du cadre
   dessinés par son propre code) ;
3. `python tools/video/make_video.py build/video <langue>` (Pillow + ffmpeg). Textes : en
   français dans `make_video.py`, traduits dans `tools/video/locales/<langue>.json` (mêmes
   diapositives, dans le même ordre).

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

- Hôte ssh `cadre` défini dans `~/.ssh/config` : adresse IP du Pi, utilisateur `cadre`,
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
- Services `cadre-splash`, `cadre-shutdown`, `cadre-display`, `cadre-web` (port 80) et `cadre-net` activés ;
  `getty@tty1` désactivé (tty1 appartient à l'écran de démarrage puis au diaporama).
- Connexion Wi-Fi sortie de netplan : `/etc/NetworkManager/system-connections/cadre-<ssid>.nmconnection`
  (fichier NetworkManager natif, 0600), sauvegarde netplan dans `/root/netplan-backup/`.
  Script : `system/netplan/migrate-from-netplan.sh`, protégé au redémarrage suivant par
  `cadre-net-rollback` (restaure netplan si pas de passerelle en 5 min, puis se désactive).
- Watchdog matériel : celui de Raspberry Pi OS suffit
  (`/usr/lib/systemd/system.conf.d/40-rpi-enable-watchdog.conf`, 1 min). Écarté : 15 s, qui
  redémarrait le Pi Zero en boucle vers 67 s (chargement des pilotes vc4 / brcmfmac). Dépannage
  par la carte SD : ajouter `systemd.watchdog_sec=off` à `cmdline.txt`.
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
- Paquet `fonts-wqy-microhei` (police chinoise, 5 Mo) : écrans en chinois, ou message écrit en
  chinois. Posé sur les cadres déjà installés par `update/apply.sh`.

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
- Arrêt : `cadre-shutdown` (ExecStop, après l'arrêt du diaporama) affiche la même image avec
  « Redémarrage... » ou « Extinction... » (+ attendre l'extinction de la diode verte), selon la
  cible en cours (`systemctl list-jobs`). Boutons « Redémarrer » / « Éteindre » dans l'admin :
  `/api/power/<action>` → commande `reboot` / `poweroff` de `cadre-net` (root) : état publié
  (le diaporama affiche aussitôt le message), arrêt 3 s plus tard ; image d'arrêt gardée 3 s.
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

- Réduction dans le navigateur testée une fois par page (couleur connue encodée puis relue au
  pixel près) : Firefox avec anti-pistage rend un canvas noir et falsifie sa relecture. Canvas
  peu fiable, image réduite trop légère (< 0,03 octet/pixel) ou vide → l'original part tel quel.
  Le cadre refuse en dernier recours toute photo entièrement noire.
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
  retéléchargée, sauf synchronisation demandée dans l'admin (bouton) : l'album revient en
  entier. Liseré orange dans la galerie de l'admin. Photos de l'admin jamais touchées (pas de détection de doublon entre les deux).
- Mesuré : 10 photos ajoutées en 28 s, synchronisation sans nouveauté en 2 s.

## Message sur le cadre

Section « Message sur le cadre » de l'admin : texte (140 caractères), date de début (le jour même
par défaut ; un message peut être préparé à l'avance) et date de fin incluses (facultatives), affichage en bandeau en haut de chaque photo (2 lignes au plus, la photo est alors
composée en plein écran) ou en carte plein écran toutes les 5 photos (tout de suite quand le
message change). Pris en compte par le diaporama en quelques secondes (`message.json`).

## Souvenirs et nouveautés

- « Souvenirs « ce jour-là » » (réglage, actif par défaut) : les photos prises le même jour une
  année passée (date du nom de fichier) passent une fois sur 4, légende « Il y a N ans », suivie
  du lieu s'il est connu (la date, implicite, n'est pas répétée).
  Les photos sans date de prise de vue (WhatsApp) portent leur date d'arrivée : jamais de faux
  souvenir. Photos de test : `build/test-souvenirs/` (EXIF du 6 octobre 2020 et 2023).
- « Nouveautés à l'honneur » (réglage, actif par défaut) : photos arrivées depuis moins de 24 h
  (date du fichier sur le cadre) en tête de chaque tour du diaporama, pictogramme « nouveau » (étincelle sur pastille bleue) en haut
  à gauche (sous le bandeau du message s'il y en a un).

## Favoris, sélection, heure et météo

- Galerie : ★ favori (deux passages par tour en ordre aléatoire, étoile sur la miniature),
  👁 masquer (photo gardée mais plus affichée, miniature grisée). `flags.json`, nettoyé à la
  suppression d'une photo.
- Réglage « Photos affichées » : toutes, album iCloud, photos envoyées, favoris ; période
  facultative « prises du … au … » (date du nom de fichier). Rien ne correspond : l'écran le dit.
- Réglages « Heure » et « Météo » (séparés) : en bas à gauche, « 16:08 · icône · 28 °C »,
  redessiné chaque minute (pause et transitions comprises). Icônes dessinées par le diaporama
  (soleil ou lune, éclaircies, nuages, brouillard, pluie, neige, orage ; la police n'a pas ces
  symboles). Position : ville choisie (géocodage Open-Meteo) ou, champ vide, position de la
  connexion Internet (ip-api.com, une fois par jour ; au bureau elle donne la sortie Internet de
  l'entreprise). Météo Open-Meteo (gratuit, sans compte) relevée toutes les 30 min par cadre-web ;
  relève de plus de 3 h ou pas d'Internet : pas de météo.
- Légende (souvenir, lieu, date) toujours dans le coin bas droit de l'écran, quel que soit le
  format de la photo. Réglages de l'admin regroupés : Diaporama, Sur les photos, Écran, Envois.

## Mise à jour à distance

Guide complet (préparer, distribuer par fichier ou par lien, refus) : [mise-a-jour.md](mise-a-jour.md).

Pour un cadre installé loin (famille) : `./make_update.sh "ce qui change"` sur le PC fabrique
`build/cadre-maj-AAAAMMJJ-HHMM.cadre` (code commité seulement, ~2,6 Mo), à envoyer par messagerie ;
la personne l'installe dans l'admin (section « Mise à jour »).
- Signature `ssh-keygen -Y sign` (espace de noms `cadre-maj`) avec `~/.ssh/id_ed25519_cadre`
  (ou `CADRE_SIGN_KEY`). Clés de confiance du cadre : celles mises dans Raspberry Pi Imager
  (`authorized_keys` -> `/etc/cadre/allowed_signers`, par install.sh). Aucune clé dans le dépôt.
- Refusés : fichier non signé, modifié ou signé par une autre clé, version identique ou plus
  ancienne (date `AAAAMMJJ-HHMM` de `cadre/VERSION`, écrit aussi par deploy.sh et install.sh).
- Installation par `cadre-net` (root) : nouvelle version dans `/opt/cadre`, ancienne dans
  `/opt/cadre.prev`, unités systemd mises à jour, `update/apply.sh` éventuel (migration, root,
  une fois), services redémarrés. Garde-fou 150 s après (copie de `update.py` de l'ancienne
  version) : services actifs depuis 30 s et admin qui répond, sinon retour à l'ancienne version
  (la fautive part dans `/opt/cadre.failed`). Bouton « Revenir à la version précédente ».
- Testé : installation normale validée ; même version, fichier falsifié et fichier quelconque
  refusés ; version à l'admin cassé remise automatiquement en arrière.

## Rapport de diagnostic

Section « Diagnostic » de l'admin : cases (informations système, diaporama, admin et iCloud,
réseau, erreurs système, démarrage précédent) et période (1 h, aujourd'hui, 3 jours) ; bouton
« Télécharger le rapport » -> `cadre-rapport-AAAAMMJJ-HHMM.txt`, à envoyer par messagerie.
Fabriqué par `cadre-net` (root, commande `report` : journal système complet), 4 000 lignes au
plus par rubrique. Retirés : lien de l'album iCloud, `psk`/`password`/`mot de passe` = valeur ;
les mots de passe Wi-Fi, du hotspot et de l'admin ne sont jamais journalisés.
Mesuré : rapport complet de la journée en 4 s, 2 900 lignes, 360 Ko.

## Langues

Admin et écrans du cadre en français, anglais, espagnol, allemand, portugais (Portugal),
roumain, russe, arabe et chinois (mandarin simplifié). Le texte français du code sert de clé :
`cadre/locales/<langue>.json` contient les traductions (`cadre/i18n.py`).

- **Page de gestion** : langue choisie en haut de la page (cookie `lang`), sinon celle du
  navigateur, sinon celle du cadre. Textes des pages : `{{ _("…") }}` ; des scripts : `t("…")`,
  `tn("singulier", "pluriel", n)` (`templates/i18n_js.html`).
- **Écrans du cadre** (démarrage, QR codes, hotspot, extinction, « Il y a 2 ans », dates, pays
  du lieu) : réglage « Langue du cadre » (section Écran). Pays traduit à l'affichage par
  iso-codes (`places.localize`) : le lieu reste rangé en français dans `places.json`.
- **Messages des services** (erreurs de mise à jour, d'iCloud, du Wi-Fi, météo) : français dans
  le code et les fichiers d'état, traduits à la sortie de l'API (`web.translate_api`) par
  `i18n.message`, y compris ceux à parties variables (la clé `{…}` sert de modèle).
- Chinois : police WenQuanYi Micro Hei (`fonts-wqy-microhei`), choisie dès qu'un texte contient
  des caractères chinois. Sur le QR code, une ligne trop longue pour sa colonne est réduite.
- Arabe : écrit de droite à gauche (`dir="rtl"` sur les pages ; à droite sur le QR code) ;
  pygame ne sachant ni lier les lettres ni écrire de droite à gauche, le texte arabe est dessiné
  par Pillow (raqm) avec DejaVu Sans (`fonts-dejavu-core`), `display.ShapedFont`.
- Pluriels : une traduction peut être une liste de formes (russe : 3, arabe : 6), choisie par
  `i18n.plural_index` (et `pluralIndex` dans les pages).
- Ajout ou changement d'un texte : `python tools/i18n_check.py` liste ce qui manque dans chaque
  langue ; les messages des services sont à déclarer dans sa liste `MESSAGES`.

## Lieu des photos

- Réglage « Afficher le lieu » (désactivé par défaut) : « Ville, Pays · date » en bas à droite.
- Position : GPS de l'EXIF (fichier reçu), ou lue par le navigateur avant réduction et envoyée à
  part (champ `gps`), ou `locationEnc` de l'album iCloud (plist binaire). WhatsApp efface le GPS.
- Avec Internet : OpenStreetMap Nominatim (nom de commune en français, 1,1 s par photo, requêtes
  espacées de 1,1 s ; les coordonnées partent donc chez OpenStreetMap, une fois par photo).
- Sans Internet : ville la plus proche parmi les villes > 1 000 hab. de GeoNames
  (`cadre/data/villes.tsv.gz`, 171 000 villes, 2,5 Mo ; données GeoNames, licence CC BY 4.0) ;
  jusqu'à 25 km « Ville, Pays », jusqu'à 200 km « Pays », au-delà rien. Chargée une fois en
  tableaux numpy (19 s sur le Pi Zero, puis 0,07 s par photo). Pays en français par `iso-codes`.
- Calculé une fois à l'arrivée de la photo et rangé dans places.json.

## Choix techniques du diaporama

- Date de prise de vue (tirée du nom du fichier) en bas à droite de chaque photo, sur un
  cartouche sombre ; réglage « Afficher la date ».
- Télécommande de la télé (HDMI-CEC) : le noyau traduit les touches en événements clavier sur le
  périphérique du récepteur CEC (`/sys/class/rc/rc0/input*/event*` ; le lien by-path
  « hdmi-event » est la prise audio HDMI). OK : QR code de l'admin 30 s (OK ou retour : masquer),
  ← / → : photo précédente / suivante, ↑ / ↓ (ou lecture/pause) : pause avec cartouche « Pause ».
  Le cadre se déclare source active au lancement et au réveil (sinon la télé garde les touches).
  Testé sur une Samsung (Anynet+) : OK, flèches et retour transmis, ni couleurs ni lecture/pause.
  Veille testée sur la même télé : mise en veille puis rallumage sur l'entrée du cadre.
  Aussi vérifié sur cette télé : démarrage du cadre télé éteinte (image présente au rallumage),
  bascule automatique sur l'entrée du cadre à son démarrage, rien de rogné sur les bords.
- Veille (réglage « Veille de … à … », plage pouvant passer minuit) : fondu au noir, plus aucune
  photo décodée, et la télé est mise en veille par HDMI-CEC (`cec-ctl --standby`) puis rallumée
  (`--image-view-on`) ; sans CEC (écran d'ordinateur), l'écran reste simplement noir. Le Pi se
  déclare à la télé au lancement (`cec-ctl --playback --osd-name "Cadre photo"`).

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
