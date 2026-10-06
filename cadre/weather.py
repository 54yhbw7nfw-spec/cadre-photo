"""Météo du coin de l'écran : Open-Meteo (gratuit, sans compte, Internet requis).

Position : la ville choisie dans l'admin (géocodage Open-Meteo, une fois), ou à défaut la position
approximative de la connexion Internet (ip-api.com, une fois par jour). La météo actuelle est
relevée toutes les 30 min par cadre-web et rangée dans weather.json, que le diaporama lit pour
dessiner une icône et la température. Relève de plus de 3 h ou pas d'Internet : pas de météo.
"""
import json
import time
import urllib.parse
import urllib.request

from . import config

GEOCODE = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST = "https://api.open-meteo.com/v1/forecast"
IP_LOCATE = "http://ip-api.com/json/"  # gratuit, sans clé, HTTP seulement en accès libre
EVERY = 30 * 60
LOCATE_EVERY = 24 * 3600
STALE = 3 * 3600

# Codes météo WMO -> (icône, libellé court pour l'admin).
KINDS = {0: ("clear", "ciel clair"), 1: ("partly", "peu nuageux"), 2: ("partly", "nuageux"),
         3: ("cloudy", "couvert"), 45: ("fog", "brouillard"), 48: ("fog", "brouillard"),
         51: ("rain", "bruine"), 53: ("rain", "bruine"), 55: ("rain", "bruine"),
         56: ("rain", "bruine verglaçante"), 57: ("rain", "bruine verglaçante"),
         61: ("rain", "pluie faible"), 63: ("rain", "pluie"), 65: ("rain", "forte pluie"),
         66: ("rain", "pluie verglaçante"), 67: ("rain", "pluie verglaçante"),
         71: ("snow", "neige faible"), 73: ("snow", "neige"), 75: ("snow", "forte neige"),
         77: ("snow", "grains de neige"), 80: ("rain", "averses"), 81: ("rain", "averses"),
         82: ("rain", "fortes averses"), 85: ("snow", "averses de neige"),
         86: ("snow", "averses de neige"), 95: ("storm", "orage"), 96: ("storm", "orage et grêle"),
         99: ("storm", "orage et grêle")}


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
    """Ville choisie (vide : position automatique) ; renvoie l'état enregistré. ValueError si
    la ville est introuvable, OSError si le service est injoignable."""
    city = " ".join(str(city).split())[:80]
    if city:
        res = _get(GEOCODE, {"name": city, "count": 1, "language": "fr", "format": "json"})
        if not res.get("results"):
            raise ValueError(f"ville « {city} » introuvable")
        r = res["results"][0]
        save({"city": city, "name": r["name"], "country": r.get("country", ""),
              "lat": r["latitude"], "lon": r["longitude"]})
    else:
        save({"city": ""})  # position cherchée à la prochaine relève
    refresh()
    return load()


def _locate(data):
    """Position de la connexion Internet, si aucune ville n'est choisie (une fois par jour)."""
    if data.get("city") or time.time() - data.get("located", 0) < LOCATE_EVERY:
        return data
    r = _get(IP_LOCATE, {"lang": "fr", "fields": "status,city,country,lat,lon"})
    if r.get("status") != "success":
        raise ValueError("position introuvable")
    return {"city": "", "name": r.get("city", ""), "country": r.get("country", ""),
            "lat": r["lat"], "lon": r["lon"], "located": time.time()}


def refresh():
    """Relève la météo actuelle (silencieux en cas d'échec)."""
    data = load()
    try:
        data = _locate(data)
        cur = _get(FORECAST, {"latitude": data["lat"], "longitude": data["lon"],
                              "current": "temperature_2m,weather_code,is_day",
                              "timezone": "auto"})["current"]
    except (OSError, ValueError, KeyError):
        return
    if load().get("city", "") != data.get("city", ""):  # ville changée pendant la requête
        return
    data.update(temp=cur["temperature_2m"], code=cur["weather_code"],
                day=bool(cur.get("is_day", 1)), updated=time.time())
    save(data)


def current(data, now=None):
    """(icône, température arrondie, jour) si la relève est récente, sinon None."""
    if "temp" not in data or (now or time.time()) - data.get("updated", 0) > STALE:
        return None
    return KINDS.get(data.get("code"), ("cloudy", ""))[0], round(data["temp"]), data.get("day", True)


def summary(data, now=None):
    """« 18 °C, nuageux » pour l'admin, ou None si pas de relève récente."""
    if not current(data, now):
        return None
    label = KINDS.get(data.get("code"), ("", ""))[1]
    return f"{round(data['temp'])} °C" + (f", {label}" if label else "")
