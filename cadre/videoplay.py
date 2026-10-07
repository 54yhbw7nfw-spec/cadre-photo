"""Lecteur vidéo du diaporama : processus à part, piloté par cadre.display, une vidéo par
processus (lancé à l'avance, GStreamer déjà chargé : la vidéo suivante démarre dans un
processus neuf ; enchaîner deux lectures dans le même processus le fait planter).

GStreamer : décodage matériel H.264 (v4l2h264dec) et affichage direct par le contrôleur
d'écran (kmssink), sans copie par le processeur : seule voie fluide sur le Pi Zero (mpv, lui,
recopie chaque image). kmssink reçoit le descripteur DRM du diaporama (--fd, hérité) : il
partage ainsi son droit de piloter l'écran, sans que personne ait à le céder. Chaque vidéo est
préparée (décodée, en attente) pendant que sa photo de couverture est affichée, sans toucher à
l'écran (show-preroll-frame=false), puis démarre aussitôt sur « play ». Le processus se
termine à la fin de la vidéo.

Dialogue par lignes. stdin : « load <0|1 son> <fichier> », « play », « pause », « resume »,
« stop » ; stdout : « ready », « end », « error <message> ».

Usage : python3 -m cadre.videoplay --fd <descripteur DRM>
"""
import os
import sys
import threading

import gi

gi.require_version("Gst", "1.0")
from gi.repository import Gst  # noqa: E402

# skip-vsync : kmssink n'attend pas les événements « image affichée » du contrôleur d'écran.
# Le descripteur étant partagé, il recevrait aussi ceux du diaporama et planterait dessus.
VIDEO = ("filesrc name=src ! qtdemux name=d d.video_0 ! queue ! h264parse ! v4l2h264dec ! "
         "kmssink name=sink show-preroll-frame=false skip-vsync=true")
SOUND = " d.audio_0 ! queue ! aacparse ! avdec_aac ! audioconvert ! audioresample ! alsasink"
PREPARE_TIMEOUT = 60  # s


def say(line):
    print(line, flush=True)


class Player:
    def __init__(self, fd):
        self.fd = fd
        self.pipeline = None
        self.lock = threading.Lock()
        self.done = threading.Event()  # vidéo finie : le processus s'arrête

    def load(self, path, sound):
        self.stop(quiet=True)
        pipeline = Gst.parse_launch(VIDEO + (SOUND if sound else ""))
        pipeline.get_by_name("src").set_property("location", path)
        # Copie du descripteur pour chaque vidéo : kmssink le ferme en s'arrêtant.
        pipeline.get_by_name("sink").set_property("fd", os.dup(self.fd))
        pipeline.set_state(Gst.State.PAUSED)
        msg = pipeline.get_bus().timed_pop_filtered(
            PREPARE_TIMEOUT * Gst.SECOND, Gst.MessageType.ASYNC_DONE | Gst.MessageType.ERROR)
        if msg is None or msg.type == Gst.MessageType.ERROR:
            pipeline.set_state(Gst.State.NULL)
            say("error " + (msg.parse_error()[0].message if msg else "préparation trop longue"))
            return
        with self.lock:
            self.pipeline = pipeline
        threading.Thread(target=self.watch, args=(pipeline,), daemon=True).start()
        say("ready")

    def watch(self, pipeline):
        """Fin de lecture ou erreur : prévient le diaporama."""
        msg = pipeline.get_bus().timed_pop_filtered(Gst.CLOCK_TIME_NONE,
                                                    Gst.MessageType.EOS | Gst.MessageType.ERROR)
        with self.lock:
            if self.pipeline is not pipeline:
                return  # arrêtée entre-temps
            self.pipeline = None
        pipeline.set_state(Gst.State.NULL)
        say("end" if msg.type == Gst.MessageType.EOS else "error " + msg.parse_error()[0].message)
        self.done.set()  # le diaporama ferme alors stdin : fin du processus

    def state(self, state):
        with self.lock:
            if self.pipeline:
                self.pipeline.set_state(state)

    def stop(self, quiet=False):
        with self.lock:
            pipeline, self.pipeline = self.pipeline, None
        if pipeline:
            pipeline.set_state(Gst.State.NULL)
        if not quiet:
            say("end")


def main():
    Gst.init(None)
    player = Player(int(sys.argv[sys.argv.index("--fd") + 1]))
    for line in sys.stdin:
        cmd, _, arg = line.strip().partition(" ")
        if cmd == "load":
            sound, _, path = arg.partition(" ")
            player.load(path, sound == "1")
            if player.pipeline is None:
                break  # préparation ratée (« error » déjà dit)
        elif cmd == "play" or cmd == "resume":
            player.state(Gst.State.PLAYING)
        elif cmd == "pause":
            player.state(Gst.State.PAUSED)
        elif cmd == "stop":
            player.stop()
            break
        if player.done.is_set():
            break
    player.stop(quiet=True)


if __name__ == "__main__":
    main()
