"""Lieu des photos : commune la plus proche des coordonnées GPS.

Avec Internet : OpenStreetMap (Nominatim), nom de commune en français ; une requête par photo
au plus, espacées d'au moins 1,1 s (règles d'usage du service). Sans Internet, ou s'il ne
répond pas : villes de plus de 1 000 habitants (GeoNames, CC BY 4.0 : data/villes.tsv.gz),
chargées une fois en tableaux numpy (~4 Mo, au lieu de ~40 Mo en objets Python) ; noms de pays
en français par le paquet iso-codes. Calculé une fois à l'arrivée de la photo (admin web ou
album iCloud) et rangé dans places.json, en français : le diaporama n'a qu'à le lire, et traduit
le pays dans la langue du cadre (localize).
"""
import gettext
import gzip
import json
import math
import os
import threading
import time
import urllib.parse
import urllib.request

import numpy

from . import config

NOMINATIM = "https://nominatim.openstreetmap.org/reverse"
USER_AGENT = "cadre-photo/1.0 (cadre photo familial, Raspberry Pi)"
ONLINE_GAP = 1.1   # s entre deux requêtes
CITIES = os.path.join(os.path.dirname(__file__), "data", "villes.tsv.gz")
ISO_JSON = "/usr/share/iso-codes/json/iso_3166-1.json"
NEAR_KM = 25       # hors ligne, plus près : « Ville, Pays »
COUNTRY_KM = 200   # hors ligne, plus près : « Pays » seulement ; au-delà (en mer…) : rien

_lock = threading.Lock()
_online_lock = threading.Lock()
_last_online = 0.0
_countries = {}  # langue -> {code: nom}
_fr_codes = None
_cities = None


ISO_LANGS = {"zh": "zh_CN"}  # ar, ru, … : catalogues du même nom  # langue du cadre -> catalogue d'iso-codes


def _iso_entries():
    try:
        with open(ISO_JSON) as f:
            return json.load(f)["3166-1"]
    except (OSError, ValueError, KeyError):
        return []


def country_names(lang="fr"):
    """Code ISO -> nom du pays dans la langue (anglais : noms d'origine d'iso-codes)."""
    if lang not in _countries:
        tr = gettext.translation("iso_3166-1", languages=[ISO_LANGS.get(lang, lang)],
                                 fallback=True)
        _countries[lang] = {e["alpha_2"]: tr.gettext(e.get("common_name", e["name"]))
                            for e in _iso_entries()}
    return _countries[lang]


def country_name(code):
    return country_names().get(code, code)


def _french_codes():
    """Nom français du pays (usuel, officiel ; iso-codes et OpenStreetMap) -> code ISO."""
    global _fr_codes
    if _fr_codes is None:
        fr = gettext.translation("iso_3166-1", languages=["fr"], fallback=True)
        _fr_codes = {}
        for e in _iso_entries():
            for key in ("name", "common_name", "official_name"):
                if e.get(key):
                    _fr_codes.setdefault(fr.gettext(e[key]), e["alpha_2"])
    return _fr_codes


def localize(place, lang):
    """« Sallanches, France » (rangé en français) avec le pays dans la langue du cadre ; la
    commune garde son nom (celui d'OpenStreetMap ou de GeoNames)."""
    if not place or lang == "fr":
        return place
    head, sep, country = place.rpartition(", ")
    code = _french_codes().get(country)
    if not code:
        return place
    return f"{head}{'، ' if sep and lang == 'ar' else sep}{country_names(lang).get(code, country)}"


def online(lat, lon):
    """« Commune, Pays » d'OpenStreetMap ; None en mer ; OSError/ValueError si injoignable."""
    global _last_online
    with _online_lock:
        wait = _last_online + ONLINE_GAP - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        query = urllib.parse.urlencode({"format": "jsonv2", "lat": f"{lat:.5f}",
                                        "lon": f"{lon:.5f}", "zoom": 10, "accept-language": "fr"})
        req = urllib.request.Request(f"{NOMINATIM}?{query}", headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=8) as r:
                data = json.load(r)
        finally:
            _last_online = time.monotonic()
    addr = data.get("address") or {}
    town = next((addr[k] for k in ("city", "town", "village", "municipality", "hamlet")
                 if addr.get(k)), None)
    return ", ".join(v for v in (town, addr.get("country")) if v) or None


def _load_cities():
    """Chargé au premier besoin (~15 s sur le Pi Zero) puis gardé : tableaux numpy compacts
    (~4 Mo), noms et pays en une seule chaîne découpée à la demande."""
    global _cities
    if _cities is None:
        lats, lons, names = [], [], []
        with gzip.open(CITIES, "rt", encoding="utf-8") as f:
            for line in f:
                if not line.startswith("#"):
                    name, lat, lon, cc, _ = line.split("\t")
                    lats.append(float(lat))
                    lons.append(float(lon))
                    names.append(f"{name}\t{cc}")
        _cities = (numpy.radians(numpy.array(lats, dtype=numpy.float32)),
                   numpy.radians(numpy.array(lons, dtype=numpy.float32)), "\n".join(names))
        _cities += (numpy.cumsum([0] + [len(n) + 1 for n in names]),)
    return _cities


def offline(lat, lon):
    """« Ville, Pays », « Pays » ou None selon la distance à la ville la plus proche."""
    lats, lons, names, starts = _load_cities()
    la, lo = math.radians(lat), math.radians(lon)
    d = (lats - la) ** 2 + ((lons - lo) * math.cos(la)) ** 2  # approximation plane
    i = int(d.argmin())
    name, cc = names[starts[i]:starts[i + 1] - 1].split("\t")
    km = math.sqrt(float(d[i])) * 6371
    if km <= NEAR_KM:
        return f"{name}, {country_name(cc)}"
    if km <= COUNTRY_KM:
        return country_name(cc)
    return None


def label(lat, lon):
    try:
        return online(lat, lon) or offline(lat, lon)
    except (OSError, ValueError):
        return offline(lat, lon)


def parse(text):
    """« lat,lon » (envoyé par le navigateur) -> (lat, lon) ou None."""
    try:
        lat, lon = (float(v) for v in str(text).split(","))
    except ValueError:
        return None
    if -90 <= lat <= 90 and -180 <= lon <= 180 and (lat, lon) != (0.0, 0.0):
        return lat, lon
    return None


def load():
    try:
        with open(config.PLACES_FILE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def set_place(name, lat, lon):
    place = label(lat, lon)
    if place:
        with _lock:
            places = load()
            places[name] = place
            config.atomic_write_json(config.PLACES_FILE, places)
    return place


def remove(name):
    with _lock:
        places = load()
        if places.pop(name, None) is not None:
            config.atomic_write_json(config.PLACES_FILE, places)
