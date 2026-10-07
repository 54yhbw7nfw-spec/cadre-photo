"""Lecture d'un album partagé iCloud public (« Site web public »), sans compte Apple.

API non officielles, celles de la page web d'Apple :
- album récent (lien photos.icloud.com/shared/album/<code>) : CloudKit. records/resolve donne
  la zone de l'album et un jeton anonyme (20 min), records/query liste photos et fichiers ;
- ancien album (lien www.icloud.com/sharedalbum/#<jeton>) : sharedstreams, webstream liste les
  photos, webasseturls donne leurs adresses de téléchargement.

fetch_album() renvoie le titre et la liste des photos : identifiant stable, adresse de
téléchargement (valable peu de temps : télécharger aussitôt) et date de prise de vue.
Vidéos ignorées ; HEIC remplacé par le JPEG 2048 px fourni par Apple (Pillow ne lit pas le HEIC).
"""
import base64
import json
import plistlib
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

TIMEOUT = 30
HEADERS = {"Content-Type": "text/plain;charset=UTF-8", "Origin": "https://www.icloud.com",
           "User-Agent": "Mozilla/5.0 (cadre-photo)"}
CK = "/database/1/com.apple.photos.cloud/production"
CK_HOST = "https://ckdatabasews.icloud.com"
READABLE = {"public.jpeg", "public.png"}  # originaux décodables tels quels par Pillow
VIDEO_MAX_MS = 2 * 60 * 1000  # vidéos plus longues ignorées (redressement : ~15 min par minute)
MAX_SIDE = 2560  # ancien format : plus grande version ne dépassant pas cette taille

CLOUDKIT_RE = re.compile(r"^https://(?:photos|www|share)\.icloud\.com/(?:shared/album|photos)/"
                         r"([A-Za-z0-9_-]{10,60})/?$")
STREAM_RE = re.compile(r"^https://www\.icloud\.com/sharedalbum/(?:[a-z-]+/)?#([A-Za-z0-9]{10,30})"
                       r"(?:;.*)?$")


class AlbumError(Exception):
    """Lien invalide, album introuvable ou réponse d'Apple inattendue (message pour l'admin)."""


def parse_link(url):
    """Renvoie ("cloudkit", code) ou ("stream", jeton) ; AlbumError si le lien n'est pas reconnu."""
    url = (url or "").strip()
    m = CLOUDKIT_RE.match(url)
    if m:
        return "cloudkit", m.group(1)
    m = STREAM_RE.match(url)
    if m:
        return "stream", m.group(1)
    raise AlbumError("lien non reconnu : attendu https://photos.icloud.com/shared/album/… "
                     "ou https://www.icloud.com/sharedalbum/#…")


def post(url, body):
    req = urllib.request.Request(url, json.dumps(body).encode(), HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.status, dict(r.headers), json.load(r)
    except urllib.error.HTTPError as exc:
        try:
            payload = json.load(exc)
        except ValueError:
            payload = {}
        return exc.code, dict(exc.headers), payload


def fetch_album(url):
    kind, key = parse_link(url)
    try:
        return _cloudkit(key) if kind == "cloudkit" else _stream(key)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise AlbumError(f"réponse d'iCloud inattendue ({exc})") from None


# --- Album récent : CloudKit --------------------------------------------------------------

def _cloudkit(code):
    status, _, res = post(f"{CK_HOST}{CK}/public/records/resolve?remapEnums=true",
                          {"shortGUIDs": [{"value": code}]})
    result = (res.get("results") or [{}])[0]
    if status != 200 or "anonymousPublicAccess" not in result:
        raise AlbumError("album introuvable : vérifiez le lien et que « Site web public » est activé")
    access, zone = result["anonymousPublicAccess"], result["zoneID"]
    title = result.get("share", {}).get("fields", {}).get("cloudkit.title", {}).get("value", "")
    params = urllib.parse.urlencode({"remapEnums": "true", "sharing_url_key": code,
                                     "publicAccessAuthToken": access["token"]})
    query_url = f"{access['databasePartition']}{CK}/shared/records/query?{params}"

    records, marker = [], None
    while True:
        body = {"query": {"recordType": "CPLAssetAndMasterByAssetDateWithoutHiddenOrDeleted",
                          "filterBy": [{"fieldName": "direction", "comparator": "EQUALS",
                                        "fieldValue": {"value": "ASCENDING", "type": "STRING"}}]},
                "zoneID": zone, "resultsLimit": 200}
        if marker:
            body["continuationMarker"] = marker
        status, _, page = post(query_url, body)
        if status != 200:
            raise AlbumError(f"liste des photos refusée par iCloud (HTTP {status})")
        records += page.get("records", [])
        marker = page.get("continuationMarker")
        if not marker or not page.get("records"):
            break

    masters = {r["recordName"]: r["fields"] for r in records if r["recordType"] == "CPLMaster"}
    photos = []
    for r in records:
        if r["recordType"] != "CPLAsset":
            continue
        f = r["fields"]
        master = masters.get(f.get("masterRef", {}).get("value", {}).get("recordName"))
        if master is None:
            continue  # fichier absent
        video = None
        if f.get("duration", {}).get("value"):
            # Vidéo : version moyenne d'Apple (H.264 720p, même si l'original est en HEVC),
            # avec son image de couverture comme « photo ».
            res_video = master.get("resVidMedRes") or master.get("resVidSmallRes")
            if (f["duration"]["value"] > VIDEO_MAX_MS or not res_video
                    or "resJPEGMedRes" not in master):
                continue
            video = res_video["value"]["downloadURL"].replace("${f}", "video.mp4")
        # Version retouchée, sinon JPEG intermédiaire d'Apple (HEIC), sinon original lisible.
        if "resJPEGFullRes" in f and not video:
            res = f["resJPEGFullRes"]
        elif "resJPEGMedRes" in master:
            res = master["resJPEGMedRes"]
        elif master.get("itemType", {}).get("value") in READABLE:
            res = master["resOriginalRes"]
        else:
            continue
        taken = None
        if "assetDate" in f:
            offset = timedelta(seconds=f.get("timeZoneOffset", {}).get("value", 0))
            taken = (datetime.fromtimestamp(f["assetDate"]["value"] / 1000, timezone.utc)
                     + offset).replace(tzinfo=None)
        photos.append({"id": r["recordName"],
                       "url": res["value"]["downloadURL"].replace("${f}", "photo.jpg"),
                       "taken": taken, "position": _position(f), "video": video})
    return title, photos


def _position(fields):
    """Position (lat, lon) de « locationEnc » (plist binaire en base64) ou None."""
    try:
        loc = plistlib.loads(base64.b64decode(fields["locationEnc"]["value"]))
        return (float(loc["lat"]), float(loc["lon"])) if loc.get("lat") else None
    except (KeyError, ValueError, TypeError, plistlib.InvalidFileException):
        return None


# --- Ancien album : sharedstreams --------------------------------------------------------------

def _stream(token):
    host = "p23-sharedstreams.icloud.com"  # la réponse 330 indique le bon serveur
    for _ in range(2):
        status, headers, data = post(f"https://{host}/{token}/sharedstreams/webstream",
                                     {"streamCtag": None})
        if status != 330:
            break
        host = data.get("X-Apple-MMe-Host") or headers.get("X-Apple-MMe-Host") or host
    if status != 200:
        raise AlbumError("album introuvable : vérifiez le lien et que « Site web public » est activé")

    chosen = {}  # photoGuid → (checksum, date)
    for p in data.get("photos", []):
        if p.get("mediaAssetType") == "video":
            continue
        derivs = [d for d in p.get("derivatives", {}).values() if d.get("checksum")]
        if not derivs:
            continue
        size = lambda d: max(int(d.get("width", 0)), int(d.get("height", 0)))
        fitting = [d for d in derivs if size(d) <= MAX_SIDE]
        best = max(fitting, key=size) if fitting else min(derivs, key=size)
        taken = None
        try:
            taken = datetime.fromisoformat(p["dateCreated"].replace("Z", "+00:00")) \
                .astimezone().replace(tzinfo=None)
        except (KeyError, ValueError):
            pass
        chosen[p["photoGuid"]] = (best["checksum"], taken)

    urls = {}
    guids = list(chosen)
    for i in range(0, len(guids), 25):
        status, _, res = post(f"https://{host}/{token}/sharedstreams/webasseturls",
                              {"photoGuids": guids[i:i + 25]})
        if status != 200:
            raise AlbumError(f"adresses des photos refusées par iCloud (HTTP {status})")
        for checksum, item in res.get("items", {}).items():
            urls[checksum] = f"https://{item['url_location']}{item['url_path']}"
    photos = [{"id": guid, "url": urls[checksum], "taken": taken}
              for guid, (checksum, taken) in chosen.items() if checksum in urls]
    return data.get("streamName", ""), photos
