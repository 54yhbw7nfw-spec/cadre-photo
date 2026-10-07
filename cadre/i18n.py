"""Traductions de l'admin et des écrans du cadre.

Le texte français du code sert de clé : cadre/locales/<langue>.json associe chaque texte
français à sa traduction (le français n'a pas de fichier). Les parties variables s'écrivent
{nom} dans la clé comme dans la traduction.

Les messages fabriqués par les services (erreurs de mise à jour, d'iCloud, du Wi-Fi…) restent
en français dans le code et dans les fichiers d'état ; message() les traduit au moment de les
montrer, y compris ceux à parties variables (« version {v} retirée : {raison} ») : la clé sert
de modèle, et chaque partie variable est traduite à son tour si elle est connue.

Module sans dépendance : il sert aussi à l'écran de démarrage (root, avant les autres services).
"""
import json
import os
import re
import threading

LANGS = {"fr": "Français", "en": "English", "es": "Español", "de": "Deutsch",
         "pt": "Português", "ro": "Română", "zh": "中文"}
DEFAULT = "fr"
# Pour les dates du navigateur (toLocaleString) et l'attribut lang des pages.
LOCALES = {"fr": "fr-FR", "en": "en-GB", "es": "es-ES", "de": "de-DE", "pt": "pt-PT",
           "ro": "ro-RO", "zh": "zh-CN"}
LOCALES_DIR = os.path.join(os.path.dirname(__file__), "locales")

MONTHS_FR = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
             "septembre", "octobre", "novembre", "décembre")

_lock = threading.Lock()
_catalogs = {}
_patterns = {}


def valid(lang):
    return lang if lang in LANGS else DEFAULT


def catalog(lang):
    """Traductions d'une langue (vide pour le français ou si le fichier manque)."""
    lang = valid(lang)
    with _lock:
        if lang not in _catalogs:
            data = {}
            if lang != DEFAULT:
                try:
                    with open(os.path.join(LOCALES_DIR, lang + ".json"), encoding="utf-8") as f:
                        data = json.load(f)
                except (OSError, ValueError):
                    pass
            _catalogs[lang] = data
        return _catalogs[lang]


def fill(text, values):
    for key, value in values.items():
        text = text.replace("{" + key + "}", str(value))
    return text


def gettext(text, lang, **values):
    """Traduction de text (clé française), parties variables remplies."""
    return fill(catalog(lang).get(text, text) if lang != DEFAULT else text, values)


def ngettext(one, many, n, lang, **values):
    """Singulier ou pluriel : en français 0 et 1 sont au singulier, ailleurs seul 1 l'est
    (le chinois ne fait pas de différence : ses deux traductions sont identiques)."""
    single = n <= 1 if valid(lang) == DEFAULT else n == 1
    return gettext(one if single else many, lang, n=n, **values)


def _compiled(lang):
    """Clés à parties variables, transformées en expressions régulières (une fois)."""
    with _lock:
        if lang not in _patterns:
            found = []
            for key, value in _catalogs.get(lang, {}).items():
                if not isinstance(value, str):
                    continue
                parts = re.split(r"\{(\w+)\}", key)
                if len(parts) == 1:
                    continue
                regex = "".join(re.escape(p) if i % 2 == 0 else f"(?P<{p}>.+?)"
                                for i, p in enumerate(parts))
                found.append((re.compile(f"^{regex}$", re.S), value))
            # Les modèles les plus précis (le plus de texte fixe) d'abord.
            found.sort(key=lambda kv: -len(re.sub(r"\(\?P<\w+>\.\+\?\)", "", kv[0].pattern)))
            _patterns[lang] = found
        return _patterns[lang]


def message(text, lang, depth=0):
    """Traduit un message venu d'un service : texte connu, ou modèle à parties variables."""
    lang = valid(lang)
    if lang == DEFAULT or not isinstance(text, str) or not text:
        return text
    cat = catalog(lang)
    if text in cat and isinstance(cat[text], str):
        return cat[text]
    if depth < 4:
        for regex, value in _compiled(lang):
            m = regex.match(text)
            if m:
                return fill(value, {k: message(v, lang, depth + 1)
                                    for k, v in m.groupdict().items()})
    return text


def date(d, lang):
    """« 8 août 2024 » dans la langue (format et mois dans le catalogue : @date, @months)."""
    lang = valid(lang)
    cat = catalog(lang)
    months = cat.get("@months", MONTHS_FR)
    fmt = cat.get("@date", "{d} {month} {y}")
    return fill(fmt, {"d": d.day, "m": d.month, "month": months[d.month - 1], "y": d.year})


def best(accept, fallback=DEFAULT):
    """Langue préférée parmi celles du navigateur (en-tête Accept-Language déjà analysé :
    liste de codes, du préféré au moins préféré)."""
    for code in accept:
        base = code.lower().replace("_", "-").split("-")[0]
        if base in LANGS:
            return base
    return valid(fallback)


def js_catalog(lang):
    """Catalogue pour le navigateur (sans les clés spéciales @…)."""
    return {k: v for k, v in catalog(lang).items() if not k.startswith("@")}
