# Mettre à jour un cadre à distance

Un cadre installé loin (dans la famille, par exemple) se met à jour avec un fichier `.cadre`
signé : vous le préparez sur votre PC, puis la personne l'installe en deux clics depuis la page
de gestion du cadre. Rien ne s'installe sans son accord, et un fichier non signé par vous est
refusé.

## Ce qu'il faut une fois pour toutes

1. **Une clé SSH** sur votre PC, par exemple `~/.ssh/id_ed25519_cadre` :
   `ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519_cadre -C cadre-photo`
2. **Sa clé publique dans Raspberry Pi Imager** au moment d'écrire la carte SD du cadre (onglet
   Services, SSH par clé publique). `install.sh` en fait la clé de confiance des mises à jour
   (`/etc/cadre/allowed_signers`) : seul le détenteur de la clé privée correspondante peut
   ensuite mettre ce cadre à jour.
3. **Git Bash** (Git pour Windows) ou un terminal Linux / macOS : `make_update.sh` utilise `git`,
   `tar` et `ssh-keygen`.

## Préparer une mise à jour

1. Modifiez le code, testez-le sur votre propre cadre (`./deploy.sh`), puis **commitez** :
   seul le code commité part dans la mise à jour.
2. Lancez, depuis le dossier du projet :

   ```bash
   ./make_update.sh "Ce qui change, en une phrase lisible par la famille"
   ```

   Le texte s'affiche dans la page de gestion au moment de l'installation. Sans texte, ce sont
   les derniers messages de commit.
3. Le script produit deux fichiers identiques dans `build/` :
   - `cadre-maj-AAAAMMJJ-HHMM.cadre` : à envoyer par messagerie ou par e-mail ;
   - `cadre-maj.cadre` : le même, sous un nom fixe, à joindre à une release GitHub (voir plus bas).

Autre clé que `~/.ssh/id_ed25519_cadre` : `CADRE_SIGN_KEY=~/.ssh/ma_cle ./make_update.sh "…"`.

### Ce que contient le fichier

| Élément | Rôle |
|---|---|
| `cadre/`, `systemd/`, `system/`, `install.sh` | le code et les services, tels que commités |
| `cadre/VERSION` | date et heure de fabrication + commit (`20261006-1635 eb0208b`) |
| `cadre/NOTES` | le texte passé à `make_update.sh` |
| `apply.sh` (si `update/apply.sh` est commité) | script de migration, lancé une fois en root |
| signature `ssh-keygen -Y sign` | prouve que le fichier vient de vous et n'a pas été modifié |

Les archives ne contiennent aucun nom d'utilisateur (propriétaire `root`).

### Script de migration (facultatif)

Pour une évolution qui demande plus que du code (un paquet à installer, un réglage système),
commitez un fichier `update/apply.sh`. Il est lancé une seule fois, en root, dans `/opt/cadre`,
juste après l'installation du nouveau code (15 min au plus). S'il échoue, l'ancienne version
est remise. Exemple :

```sh
#!/bin/sh
set -e
dpkg -s python3-requests >/dev/null 2>&1 || apt-get install -y --no-install-recommends python3-requests
```

**Gardez-le cumulatif, ne le supprimez pas.** Un cadre en retard de plusieurs versions passe
directement à la dernière (chaque fichier contient tout le code) : seul le `apply.sh` de ce
dernier fichier est lancé. Ajoutez donc chaque nouvelle étape à la suite des précédentes, et
faites-la vérifier si elle est déjà faite (comme `dpkg -s … ||` ci-dessus) : le script part dans
chaque fichier et peut être relancé sur un cadre déjà à jour sans dommage. Exemple après deux
évolutions :

```sh
#!/bin/sh
set -e
# 20261101 : paquet requests
dpkg -s python3-requests >/dev/null 2>&1 || apt-get install -y --no-install-recommends python3-requests
# 20261215 : dossier des archives
[ -d /var/lib/cadre/archives ] || install -d -o cadre -g cadre /var/lib/cadre/archives
```

Il faut Internet sur le cadre pour `apt-get`.

## Distribuer la mise à jour

### Par fichier

Envoyez `build/cadre-maj-AAAAMMJJ-HHMM.cadre`. Sur le cadre : page de gestion, section
**Mise à jour**, **Installer depuis un fichier…**, choisir le fichier.

### Par lien (release GitHub)

Le dépôt doit être public (sinon le cadre ne peut pas télécharger sans identifiant).

1. Sur GitHub, page du dépôt, **Releases → Draft a new release**.
2. **Tag** : `vAAAAMMJJ-HHMM` (la version affichée par `make_update.sh`), **titre** libre.
3. Joindre **`build/cadre-maj.cadre`** (ce nom exact), puis **Publish release**.

Le lien `https://github.com/<compte>/<dépôt>/releases/latest/download/cadre-maj.cadre` désigne
toujours la dernière release. Sur le cadre : section **Mise à jour**, vérifier l'adresse,
**Rechercher une mise à jour**, puis **Installer cette version** si une version plus récente est
proposée. La recherche télécharge et vérifie le fichier sans rien installer. Aucune mise à jour
n'est jamais faite automatiquement.

## Ce qui se passe sur le cadre

1. Vérifications : fichier `.cadre` bien formé, signature d'une clé de confiance, version
   strictement plus récente que celle installée (la date de `VERSION`).
2. Installation par `cadre-net` (root) : nouveau code dans `/opt/cadre`, ancien gardé dans
   `/opt/cadre.prev`, services systemd mis à jour, `apply.sh` éventuel, services redémarrés
   (le diaporama s'interrompt environ une minute).
3. **Garde-fou** 2 min 30 plus tard : diaporama, page de gestion et réseau doivent tourner depuis
   30 s et la page doit répondre ; sinon l'ancienne version revient toute seule.
4. Le bouton **Revenir à la version précédente** remet l'ancienne version à la main (pour un
   défaut que le garde-fou ne voit pas).

## En cas de refus

| Message | Cause et remède |
|---|---|
| signature invalide | fichier modifié, ou signé avec une clé que ce cadre ne connaît pas (pas celle mise dans Imager) |
| déjà installée ou plus ancienne | la version du fichier n'est pas plus récente : refaire `make_update.sh` |
| ce n'est pas un fichier de mise à jour | mauvais fichier choisi |
| aucune mise à jour à cette adresse | pas de release, dépôt privé, ou fichier joint sous un autre nom que `cadre-maj.cadre` |
| l'adresse doit commencer par https:// | adresse mal recopiée |
| script de migration en échec | `apply.sh` a échoué : ancienne version remise ; voir le rapport de diagnostic |

Le rapport de diagnostic (section **Diagnostic** de la page de gestion) contient la version
installée et l'état de la dernière mise à jour.
