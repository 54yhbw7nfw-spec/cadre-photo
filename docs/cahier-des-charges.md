# Projet : cadre photo sur Raspberry Pi Zero W

## Cible
- Raspberry Pi Zero W (2017) : ARMv6, 1 cœur 1 GHz, 512 Mo RAM
- Raspberry Pi OS Lite 32 bits, NetworkManager, pas de serveur graphique
- Accès : ssh <user>@cadre.local (clé SSH déjà en place)
- Développement sur mon PC, déploiement via rsync/ssh. Claude Code ne tourne pas sur le Pi.

## Fonctionnement attendu
1. Au boot : attente ~30 s d'une connexion Wi-Fi connue.
2. Si connecté : QR code plein écran vers http://<ip> + texte "cadre.local", pendant 20 s, puis diaporama.
3. Si non connecté : scan des réseaux AVANT de passer en AP, puis hotspot "CadrePhoto-Setup"
   (nmcli). L'écran affiche un QR code Wi-Fi (format WIFI:S:...;;) + l'URL du portail.
   Portail captif : liste des réseaux scannés + saisie du mot de passe.
   Une fois connecté : hotspot coupé, retour étape 2. En cas d'échec : hotspot relancé.
4. Diaporama en boucle sur la télé HDMI, photos adaptées à l'écran (letterbox), transitions.

## Choix techniques imposés
- Affichage : Python 3 + pygame (SDL2, backend KMSDRM), sortie 1280x720.
- Photos pré-redimensionnées à l'upload (Pillow, Image.draft() pour JPEG,
  rotation EXIF appliquée, conversion JPEG qualité 90). Originaux non conservés
  (option à prévoir).
- Transitions : fondu, glissement (4 sens), volet, aucune, aléatoire. Pas de Ken Burns.
- Admin web : Flask, page unique légère (pas de framework JS lourd) :
  - upload multiple glisser-déposer (centaines de photos), file d'attente de traitement
    en tâche de fond + barre de progression
  - grille de miniatures paginée, suppression unitaire et par sélection
  - réglages : transition, délai (secondes), ordre aléatoire on/off
  - réglages stockés en JSON, pris en compte à chaud par le diaporama
- Services systemd séparés : réseau/hotspot, diaporama, admin web. Redémarrage auto.
- avahi pour cadre.local.
- Script install.sh idempotent qui installe tout depuis une Raspberry Pi OS Lite vierge.

## Contraintes
- Économiser la RAM et le CPU, tester les perfs réelles sur le Pi.
- Limiter les écritures sur la SD (logs en RAM via journald volatile si pertinent).
- Pas de mot de passe en dur. Admin web sans auth pour l'instant, mais prévoir un mot de
  passe optionnel.
- Me demander validation avant toute commande qui modifie le réseau du Pi
  (risque de perdre l'accès SSH).

## Méthode
Avancer par étapes testées sur le Pi :
1) diaporama seul, 2) admin web, 3) QR code au boot, 4) hotspot/portail captif, 5) install.sh.
