"""Vérifie les traductions (cadre/locales/*.json) : textes du code absents, en trop, ou parties
variables {…} qui ne correspondent pas.

Textes repérés dans le code : _("…") des pages, t("…") et tn("…", "…") des scripts,
tr("…"), gettext("…") et ngettext("…", "…") en Python. Les messages des services (erreurs de
mise à jour, d'iCloud, du Wi-Fi…), traduits à la volée par i18n.message, sont listés dans
MESSAGES ci-dessous : à compléter quand un service en ajoute un qui arrive jusqu'à l'admin.

Usage : python tools/i18n_check.py            (rapport, code de sortie 1 si incomplet)
        python tools/i18n_check.py --keys     (tous les textes à traduire, un par ligne)
"""
import glob
import json
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
LOCALES = os.path.join(ROOT, "cadre", "locales")

# Messages des services (français dans le code), traduits à l'affichage.
MESSAGES = [
    # web.py
    "connexion requise", "Mot de passe incorrect.", "mot de passe actuel incorrect",
    "6 caractères minimum", "aucun fichier", "carte SD pleine (marge du système atteinte)",
    "photo inconnue", "action inconnue", "service réseau indisponible ({exc})",
    "service météo injoignable ({exc})", "carte SD pleine : synchronisation arrêtée",
    "une photo n'a pas pu être ajoutée ({exc})", "erreur interne ({exc})",
    # imaging.py
    "image illisible ou format non pris en charge ({exc})",
    "image entièrement noire (réduction du navigateur ratée) : renvoyer la photo, ou cocher « Conserver les originaux »",
    # weather.py
    "ville « {city} » introuvable", "position introuvable", "{temp} °C, {label}",
    "ciel clair", "peu nuageux", "nuageux", "couvert", "brouillard", "bruine",
    "bruine verglaçante", "pluie faible", "pluie", "forte pluie", "pluie verglaçante",
    "neige faible", "neige", "forte neige", "grains de neige", "averses", "fortes averses",
    "averses de neige", "orage", "orage et grêle",
    # icloud.py
    "lien non reconnu : attendu https://photos.icloud.com/shared/album/… ou https://www.icloud.com/sharedalbum/#…",
    "réponse d'iCloud inattendue ({exc})",
    "album introuvable : vérifiez le lien et que « Site web public » est activé",
    "liste des photos refusée par iCloud (HTTP {status})",
    "adresses des photos refusées par iCloud (HTTP {status})",
    "fichier trop volumineux",
    # net.py
    "une connexion est déjà en cours", "connexion impossible : mot de passe ou signal ?",
    "réseau inconnu", "nom de réseau manquant", "mot de passe Wi-Fi : 8 à 63 caractères",
    "rien à installer : rechercher d'abord", "commande inconnue",
    "profil refusé par NetworkManager ({out})",
    # update.py
    "ce n'est pas un fichier de mise à jour du cadre",
    "fichier illisible : ce n'est pas un fichier de mise à jour",
    "signature invalide : fichier modifié ou non fourni par le développeur du cadre",
    "version absente du fichier", "l'adresse doit commencer par https://",
    "aucune mise à jour à cette adresse", "téléchargement refusé (HTTP {code})",
    "téléchargement impossible ({exc})",
    "la mise à jour précédente est encore en vérification : réessayez dans quelques minutes",
    "version {version} déjà installée ou plus ancienne (installée : {current})",
    "installation en cours", "script de migration en échec : ancienne version remise",
    "script de migration en échec : {output}",
    "services en redémarrage, vérification dans {min} min {s} s",
    "aucune version précédente disponible", "version {version} retirée : {reason}",
    "demandé dans l'admin", "vérification après installation : {problem}",
    "{service} ne tourne pas", "{service} redémarre en boucle", "l'admin répond {code}",
    "l'admin ne répond pas ({exc})", "installée et vérifiée",
]

# Clés spéciales du catalogue (format des dates), pas des textes.
SPECIAL = {"@date", "@months"}

PATTERNS = {
    ".html": [r'''\b_\(\s*"((?:[^"\\]|\\.)*)"''', r"""\b_\(\s*'((?:[^'\\]|\\.)*)'"""],
    ".js": [r'''\bt\(\s*"((?:[^"\\]|\\.)*)"''',
            r'''\btn\(\s*"((?:[^"\\]|\\.)*)",\s*"((?:[^"\\]|\\.)*)"'''],
    ".py": [r'''\b(?:tr|gettext)\(\s*"((?:[^"\\]|\\.)*)"''',
            r'''\bngettext\(\s*"((?:[^"\\]|\\.)*)",\s*"((?:[^"\\]|\\.)*)"'''],
}


def code_keys():
    keys = set(MESSAGES)
    files = (glob.glob(os.path.join(ROOT, "cadre", "**", "*.py"), recursive=True)
             + glob.glob(os.path.join(ROOT, "cadre", "templates", "*.html"))
             + glob.glob(os.path.join(ROOT, "cadre", "static", "*.js")))
    for path in files:
        if path.endswith("i18n.py"):
            continue
        text = open(path, encoding="utf-8").read()
        kinds = [".html", ".js"] if path.endswith(".html") else [os.path.splitext(path)[1]]
        for kind in kinds:
            for pattern in PATTERNS[kind]:
                for m in re.finditer(pattern, text):
                    for g in m.groups():
                        keys.add(g.replace('\\"', '"').replace("\\'", "'").replace("\\n", "\n"))
    return keys


def placeholders(text):
    return sorted(set(re.findall(r"\{(\w+)\}", text)))


def main():
    sys.stdout.reconfigure(encoding="utf-8")  # console Windows
    keys = code_keys()
    if "--keys" in sys.argv:
        print("\n".join(sorted(keys)))
        return 0
    ok = True
    for path in sorted(glob.glob(os.path.join(LOCALES, "*.json"))):
        lang = os.path.basename(path)[:-5]
        with open(path, encoding="utf-8") as f:
            cat = json.load(f)
        missing = sorted(keys - set(cat))
        extra = sorted(set(cat) - keys - SPECIAL)
        wrong = sorted(k for k in keys & set(cat) if placeholders(k) != placeholders(cat[k]))
        absent = sorted(SPECIAL - set(cat))
        print(f"{lang} : {len(cat)} textes, {len(missing)} manquants, {len(extra)} en trop, "
              f"{len(wrong)} variables différentes" + (f", sans {', '.join(absent)}" if absent else ""))
        for label, items in (("manquant", missing), ("en trop", extra), ("variables", wrong)):
            for k in items:
                print(f"   {label} : {k}")
        ok = ok and not (missing or extra or wrong or absent)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
