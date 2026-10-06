# Projet : cadre photo sur Raspberry Pi Zero W

## Cible
- Raspberry Pi Zero W (2017) : ARMv6, 1 cœur 1 GHz, 512 Mo RAM
- Raspberry Pi OS Lite 32 bits, NetworkManager, pas de serveur graphique
- Accès : ssh <user>@cadre.local (clé SSH déjà en place)
- Développement sur mon PC, déploiement via tar/ssh (deploy.sh). Claude Code ne tourne pas sur le Pi.

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
- Limiter les écritures sur la SD (journal en RAM par défaut ; option --journal-sd d'install.sh).
- Pas de mot de passe en dur. Mot de passe de l'admin optionnel (page de connexion).
- Aucune trace du nom réel du développeur dans le dépôt, l'historique et les fichiers envoyés.
- Me demander validation avant toute commande qui modifie le réseau du Pi
  (risque de perdre l'accès SSH).

## Évolutions ajoutées en cours de projet

- Album iCloud partagé (« Site web public ») synchronisé toutes les 30 min, photos retirées de
  l'album supprimées du cadre, liseré dans la galerie, synchronisation forcée qui rétablit tout.
- Écran de démarrage (image + messages du démarrage), écran d'extinction / de redémarrage,
  boutons Redémarrer et Éteindre dans l'admin.
- Télécommande de la télé (HDMI-CEC) : photo précédente / suivante, pause, QR code de l'admin.
- Veille programmée la nuit (écran noir, télé mise en veille par CEC), date et lieu de prise de
  vue sur les photos (options).
- Admin : espace libre affiché, marge gardée pour le système, page de connexion, changement du
  mot de passe, bandeau si pas de Wi-Fi, portail Wi-Fi accessible sans mot de passe.
- Lieu des photos : OpenStreetMap avec Internet, sinon villes > 1 000 hab. hors ligne.
- Rapport de diagnostic téléchargeable (journaux choisis, données sensibles retirées).
- Mise à jour à distance par fichier signé (clé SSH du développeur), retour arrière automatique.
- Message de la famille affiché sur le cadre (bandeau ou écran), jusqu'à une date.
- Souvenirs « ce jour-là » et nouvelles photos mises en avant (badge « Nouveau »).
- Favoris et photos masquées, choix des photos affichées (source, période), heure et météo.
- Mode d'emploi vidéo (diapositives commentées) pour la famille.

## Méthode
Avancer par étapes testées sur le Pi :
1) diaporama seul, 2) admin web, 3) QR code au boot, 4) hotspot/portail captif, 5) install.sh,
puis les évolutions ci-dessus (étapes 6 à 12 du README).
