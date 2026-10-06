"""Lieu des photos, hors ligne : ville la plus proche des coordonnées GPS.

Villes de plus de 15 000 habitants (GeoNames, CC BY 4.0 : cadre/data/villes.tsv.gz) ; noms
de pays en français fournis par le paquet iso-codes. Les lieux sont calculés une fois, à
l'arrivée de la photo (admin web ou album iCloud), et rangés dans places.json : le diaporama
n'a qu'à les lire.
"""
import gettext
import gzip
import json
import math
import os
import threading

from . import config

CITIES = os.path.join(os.path.dirname(__file__), "data", "villes.tsv.gz")
ISO_JSON = "/usr/share/iso-codes/json/iso_3166-1.json"
NEAR_KM = 40       # plus près : « Ville, Pays »
COUNTRY_KM = 200   # plus près : « Pays » seulement ; au-delà (en mer…) : pas de lieu

_lock = threading.Lock()
_cities = None
_countries = None


def _load_cities():
    global _cities
    if _cities is None:
        rows = []
        with gzip.open(CITIES, "rt", encoding="utf-8") as f:
            for line in f:
                if not line.startswith("#"):
                    name, lat, lon, cc, _ = line.rstrip("\n").split("\t")
                    rows.append((math.radians(float(lat)), math.radians(float(lon)), name, cc))
        _cities = rows
    return _cities


def country_name(code):
    global _countries
    if _countries is None:
        _countries = {}
        try:
            with open(ISO_JSON) as f:
                entries = json.load(f)["3166-1"]
            fr = gettext.translation("iso_3166-1", languages=["fr"], fallback=True)
            for e in entries:
                _countries[e["alpha_2"]] = fr.gettext(e.get("common_name", e["name"]))
        except (OSError, ValueError, KeyError):
            pass
    return _countries.get(code, code)


def label(lat, lon):
    """« Ville, Pays », « Pays » ou None selon la distance à la ville la plus proche."""
    la, lo = math.radians(lat), math.radians(lon)
    cos_la = math.cos(la)
    best, best_d = None, float("inf")
    for cla, clo, name, cc in _load_cities():
        d = (cla - la) ** 2 + ((clo - lo) * cos_la) ** 2  # approximation plane, suffisante ici
        if d < best_d:
            best, best_d = (name, cc), d
    km = math.sqrt(best_d) * 6371
    if km <= NEAR_KM:
        return f"{best[0]}, {country_name(best[1])}"
    if km <= COUNTRY_KM:
        return country_name(best[1])
    return None


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
