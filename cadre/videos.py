"""Vidéos (album iCloud) : chacune est une « photo » (sa couverture, dans photos/, traitée comme
les autres : galerie, date, lieu, favoris…) plus un fichier MP4 du même nom dans videos/.

Le diaporama les lit avec le décodeur matériel et l'affichage direct du Pi (cadre.videoplay),
qui ne savent ni pivoter de 90° ni lire autre chose que du H.264 : chaque vidéo est donc
préparée une fois, à son arrivée, par ffmpeg (redressée si besoin, mise sur fond noir en
1280x720 ; décodage et encodage matériels ; ~10 min par minute de vidéo, en tâche de fond,
priorité minimale). Même une vidéo déjà en paysage est réencodée : telle que fournie par
iCloud (pistes de métadonnées, images B), elle fait planter le lecteur. Le
fichier reçu attend sous un nom caché (« .src-… ») ; la vidéo n'est jouée qu'une fois prête,
la couverture s'affiche comme une photo en attendant.

Le redressement occupe le décodeur matériel, que la lecture ne peut alors pas utiliser : tant
qu'il dure (fichier « .tmp-… » présent), les vidéos s'affichent comme des photos.
"""
import glob
import json
import logging
import os
import subprocess

from . import config

log = logging.getLogger("cadre.videos")

SCREEN_W, SCREEN_H = config.SCREEN_SIZE
CONVERT_TIMEOUT = 3 * 3600  # s : une vidéo de 2 min se redresse en ~30 min


def path(name):
    """Fichier vidéo d'une couverture (« AAAAMMJJ-HHMMSS_xxx.jpg » -> videos/….mp4)."""
    return os.path.join(config.VIDEOS_DIR, os.path.splitext(name)[0] + ".mp4")


def source_path(name):
    return os.path.join(config.VIDEOS_DIR, ".src-" + os.path.splitext(name)[0] + ".mp4")


def ready(name):
    return os.path.exists(path(name))


def is_video(name):
    """Vidéo prête ou en préparation."""
    return ready(name) or os.path.exists(source_path(name))


def converting():
    """Redressement en cours (le décodeur matériel est pris)."""
    return bool(glob.glob(os.path.join(config.VIDEOS_DIR, ".tmp-*")))


def clean_leftovers():
    """Fichiers temporaires laissés par un arrêt en plein redressement ou téléchargement."""
    for p in glob.glob(os.path.join(config.VIDEOS_DIR, ".tmp-*")) + glob.glob(
            os.path.join(config.VIDEOS_DIR, ".dl-*")):
        os.unlink(p)


def delete(name):
    for p in (path(name), source_path(name)):
        try:
            os.unlink(p)
        except FileNotFoundError:
            pass


def probe(src):
    """{codec, width, height, rotation} de la piste vidéo (ffprobe)."""
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=codec_name,width,height:stream_side_data=rotation",
                          "-of", "json", src], capture_output=True, text=True, timeout=60)
    stream = (json.loads(out.stdout or "{}").get("streams") or [{}])[0]
    rotation = 0
    for side in stream.get("side_data_list", []):  # matrice d'affichage, puis d'autres données
        if "rotation" in side:
            rotation = int(side["rotation"]) % 360
    return {"codec": stream.get("codec_name"), "width": stream.get("width", 0),
            "height": stream.get("height", 0), "rotation": rotation}


def filters(info):
    """Filtres ffmpeg : réduction (avant rotation : moins de pixels à tourner), rotation, bandes
    noires jusqu'à 1280x720."""
    w, h, rot = info["width"], info["height"], info["rotation"]
    shown_w, shown_h = (h, w) if rot in (90, 270) else (w, h)
    fit = min(SCREEN_W / shown_w, SCREEN_H / shown_h, 1)
    sw, sh = (max(2, round(v * fit / 2) * 2) for v in (w, h))
    # rotation (ffprobe) : sens inverse des aiguilles d'une montre, -90 = 270 -> quart horaire.
    turn = {90: "transpose=cclock", 180: "hflip,vflip", 270: "transpose=clock"}.get(rot)
    out_w, out_h = (sh, sw) if rot in (90, 270) else (sw, sh)
    chain = [f"scale={sw}:{sh}"] + ([turn] if turn else [])
    chain.append(f"pad={SCREEN_W}:{SCREEN_H}:{(SCREEN_W - out_w) // 2}:{(SCREEN_H - out_h) // 2}")
    chain.append("format=yuv420p")
    return ",".join(chain)


def convert(name):
    """Prépare la vidéo reçue pour name ; True si elle est prête (ou déjà jouable)."""
    src, dest = source_path(name), path(name)
    info = probe(src)
    chain = filters(info)
    tmp = os.path.join(config.VIDEOS_DIR, ".tmp-" + os.path.basename(dest))
    decoder = ["-c:v", "h264_v4l2m2m"] if info["codec"] == "h264" else []
    cmd = (["nice", "-n", "19", "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-noautorotate"] + decoder + ["-i", src, "-vf", chain, "-metadata:s:v", "rotate=0",
                                          "-c:v", "h264_v4l2m2m", "-b:v", "2500k",
                                          "-map", "0:v:0", "-map", "0:a:0?",
                                          "-c:a", "copy", "-movflags", "+faststart", tmp])
    log.info("Vidéo %s : redressement (%s, %s)", name, info, chain)
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=CONVERT_TIMEOUT)
    except subprocess.TimeoutExpired:
        res = None
    if res is None or res.returncode != 0 or not os.path.exists(tmp) or not os.path.getsize(tmp):
        log.warning("Vidéo %s : échec du redressement (%s)", name,
                    res.stderr[-300:] if res else "trop long")
        for p in (tmp, src):
            if os.path.exists(p):
                os.unlink(p)
        return False
    os.replace(tmp, dest)
    os.unlink(src)
    log.info("Vidéo %s prête", name)
    return True


def pending():
    """Couvertures dont la vidéo attend d'être préparée, plus anciennes d'abord."""
    srcs = sorted(glob.glob(os.path.join(config.VIDEOS_DIR, ".src-*.mp4")), key=os.path.getmtime)
    return [os.path.basename(s)[5:-4] + ".jpg" for s in srcs]
