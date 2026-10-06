"""Météo du coin de l'écran : Open-Meteo (gratuit, sans compte, Internet requis).

La ville choisie dans l'admin est cherchée une fois (géocodage, nom en français), puis la météo
actuelle est relevée toutes les 30 min par cadre-web et rangée dans weather.json, que le
diaporama lit. Sans Internet, ou si la dernière relève a plus de 3 h, seule l'heure s'affiche.
"""
import json
import time
import urllib.parse
import urllib.request

from . import config

GEOCODE = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST = "https://api.open-meteo.com/v1/forecast"
EVERY = 30 * 60
STALE = 3 * 3600

# Codes météo WMO -> libellé court.
LABELS = {0: "ciel clair", 1: "peu nuageux", 2: "nuageux", 3: "couvert", 45: "brouillard",
          48: "brouillard", 51: "bruine", 53: "bruine", 55: "bruine", 56: "bruine verglaçante",
          57: "bruine verglaçante", 61: "pluie faible", 63: "pluie", 65: "forte pluie",
          66: "pluie verglaçante", 67: "pluie verglaçante", 71: "neige faible", 73: "neige",
          75: "forte neige", 77: "grains de neige", 80: "averses", 81: "averses",
          82: "fortes averses", 85: "averses de neige", 86: "averses de neige", 95: "orage",
          96: "orage et grêle", 99: "orage et grêle"}


def _get(url, params):
    req = urllib.request.Request(f"{url}?{urllib.parse.urlencode(params)}",
                                 headers={"User-Agent": "cadre-photo/1.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)


def load():
    try:
        with open(config.WEATHER_FILE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save(data):
    config.atomic_write_json(config.WEATHER_FILE, data)


def set_city(city):
    """Cherche la ville ; renvoie l'état enregistré. ValueError si introuvable, OSError si
    Open-Meteo est injoignable. Ville vide : plus de météo."""
    city = " ".join(str(city).split())[:80]
    if not city:
        save({})
        return {}
    res = _get(GEOCODE, {"name": city, "count": 1, "language": "fr", "format": "json"})
    if not res.get("results"):
        raise ValueError(f"ville « {city} » introuvable")
    r = res["results"][0]
    data = {"city": city, "name": r["name"], "country": r.get("country", ""),
            "lat": r["latitude"], "lon": r["longitude"]}
    save(data)
    refresh()
    return load()


def refresh():
    """Relève la météo actuelle de la ville enregistrée (silencieux en cas d'échec)."""
    data = load()
    if "lat" not in data:
        return
    try:
        cur = _get(FORECAST, {"latitude": data["lat"], "longitude": data["lon"],
                              "current": "temperature_2m,weather_code",
                              "timezone": "auto"})["current"]
    except (OSError, ValueError, KeyError):
        return
    if load().get("city") != data.get("city"):  # ville changée pendant la requête
        return
    data.update(temp=cur["temperature_2m"], code=cur["weather_code"], updated=time.time())
    save(data)


def summary(data, now=None):
    """« 18 °C, nuageux », ou None si pas de relève récente."""
    now = now or time.time()
    if "temp" not in data or now - data.get("updated", 0) > STALE:
        return None
    label = LABELS.get(data.get("code"), "")
    return f"{round(data['temp'])} °C" + (f", {label}" if label else "")


def corner_text(data, now=None):
    """« Niort 18 °C, nuageux », ou None si pas de relève récente."""
    s = summary(data, now)
    return f"{data['name']} {s}" if s else None
