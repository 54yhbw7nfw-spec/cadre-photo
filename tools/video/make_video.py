"""Mode d'emploi vidéo du cadre : diapositives commentées (voix de synthèse Windows) en MP4.

Prérequis (PC Windows) : ffmpeg, Pillow, edge-tts (pip install edge-tts, Internet), et les visuels :
  python tools/video/shots.py http://<ip du cadre> build/video/shots      captures de l'admin
    (dont admin-complet.png, page entière, découpée par section : « fichier#n » ou « #n-m »)
  écrans du cadre : tools/video/screens.py lancé sur le Pi -> build/video/screens
Usage : python tools/video/make_video.py build/video     -> build/video/cadre-photo-mode-d-emploi.mp4
"""
import os
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1920, 1080
BG = (18, 18, 20)
TEXT = (235, 235, 235)
MUTED = (160, 160, 165)
ACCENT = (110, 170, 255)
FONTS = r"C:\Windows\Fonts"
VOICE = "fr-FR-DeniseNeural"  # voix neuronale Microsoft (edge-tts)
PAUSE = 0.9  # s de silence après chaque narration
# Zones à masquer sur les captures : le lien réel de l'album iCloud (accès « contributeur »).
MASKS = {"shots/admin-haut.png": [((124, 304, 836, 332),
                                   "https://photos.icloud.com/shared/album/…")]}

# (titre, visuels « dossier/fichier », points clés à l'écran, narration)
SLIDES = [
    ("Cadre photo", ["screens/photo.png"], ["Mode d'emploi"],
     "Bienvenue. Cette vidéo explique comment utiliser le cadre photo : l'allumer, le "
     "connecter au Wi-Fi, ajouter des photos et le piloter avec la télécommande de la télé."),
    ("Brancher et allumer", ["screens/demarrage.png"],
     ["Câble HDMI vers la télé", "Puis l'alimentation : démarrage automatique",
      "Photos au bout d'1 min 30 environ"],
     "Branchez le cadre sur la télé avec le câble HDMI, puis branchez son alimentation. Il n'a "
     "pas de bouton : il démarre tout seul. Au bout d'une demi-minute, cet écran apparaît. "
     "Comptez environ une minute et demie avant les premières photos."),
    ("Wi-Fi de la maison", ["screens/qr.png"],
     ["Connexion automatique", "QR code affiché 30 secondes", "Il mène à la page de gestion"],
     "Si le cadre connaît le Wi-Fi de la maison, il s'y connecte tout seul, puis affiche "
     "pendant trente secondes ce QR code. Il mène à la page de gestion des photos."),
    ("Premier Wi-Fi", ["screens/hotspot.png"],
     ["Aucun réseau connu : le cadre crée le sien", "Scanner le QR code avec le téléphone",
      "Mot de passe affiché à l'écran"],
     "S'il ne connaît aucun réseau, par exemple chez quelqu'un d'autre, le cadre crée son "
     "propre Wi-Fi, appelé Cadre Photo Setup. Scannez ce QR code avec votre téléphone pour "
     "vous y connecter. Le mot de passe change à chaque démarrage et reste affiché à l'écran."),
    ("Choisir le Wi-Fi", ["shots/portail-wifi.png"],
     ["La page s'ouvre toute seule", "Choisir le réseau, taper son mot de passe",
      "« Se connecter »"],
     "La page de configuration s'ouvre alors toute seule sur le téléphone. Choisissez le "
     "Wi-Fi de la maison, tapez son mot de passe et touchez Se connecter. Le cadre rejoint la "
     "maison, et le QR code de la page de gestion s'affiche à la télé."),
    ("La page de gestion", ["shots/admin-haut.png"],
     ["QR code de la télé, ou http://cadre.local", "Transition, durée, ordre aléatoire",
      "Date et lieu sur les photos, veille la nuit"],
     "Pour gérer le cadre, scannez le QR code affiché à la télé, ou tapez cadre point local "
     "dans le navigateur d'un téléphone ou d'un ordinateur connecté au même Wi-Fi. En haut de "
     "la page se trouvent les réglages : la transition entre les photos, la durée "
     "d'affichage, l'ordre aléatoire, la date et le lieu sur les photos, et la mise en veille la "
     "nuit."),
    ("Ajouter des photos", ["shots/admin-photos.png"],
     ["Glisser les photos, ou toucher pour les choisir", "Visibles en quelques secondes",
      "Sélectionner puis « Supprimer la sélection »"],
     "Pour ajouter des photos, glissez-les dans la zone en pointillés, ou touchez-la pour les "
     "choisir sur votre téléphone. Elles arrivent dans la galerie et dans le diaporama "
     "quelques secondes plus tard. Pour en retirer, sélectionnez-les, puis touchez Supprimer "
     "la sélection."),
    ("Album iCloud partagé", ["shots/admin-haut.png"],
     ["iPhone : album partagé, « Site web public »", "Coller le lien dans la page de gestion",
      "Vérifié toutes les 30 minutes", "Photos de l'album entourées d'orange"],
     "Vous pouvez aussi relier un album partagé iCloud. Sur l'iPhone, ouvrez l'album, touchez "
     "l'icône des personnes et activez Site web public. Copiez ensuite le lien et collez-le "
     "dans la page de gestion. Le cadre vérifie l'album toutes les trente minutes, et ses "
     "photos sont entourées d'orange dans la galerie."),
    ("Pendant le diaporama", ["screens/photo.png"],
     ["Lieu et date de prise de vue en bas à droite", "« Afficher la date », « Afficher le lieu »",
      "Lieu : photos d'iPhone et album iCloud (WhatsApp l'efface)"],
     "Pendant le diaporama, le lieu et la date de prise de vue s'affichent en bas à droite de "
     "chaque photo. Chacun se règle dans la page de gestion. Le lieu est connu pour les photos "
     "prises avec un téléphone et pour celles de l'album iCloud, mais pas pour les photos "
     "reçues par WhatsApp, qui efface cette information."),
    ("Un message sur le cadre", ["shots/admin-complet.png#1", "screens/bandeau.png"],
     ["Section « Message sur le cadre »", "Bandeau sur les photos, ou écran entre elles",
      "Jusqu'à une date, ou « Retirer »"],
     "Pour une occasion, vous pouvez afficher un message sur le cadre. Dans la section Message "
     "sur le cadre, tapez votre texte, choisissez un bandeau en haut des photos ou un écran "
     "entre les photos, et éventuellement une date de fin. Touchez Afficher. Le message "
     "disparaît tout seul après cette date, ou quand vous touchez Retirer."),
    ("La télécommande de la télé", ["screens/pause.png"],
     ["→  photo suivante", "←  photo précédente", "↑ ou ↓  pause / reprise",
      "OK  QR code de la page de gestion"],
     "Si la télé le permet, sa télécommande pilote le cadre. Flèche droite : photo suivante. "
     "Flèche gauche : photo précédente. Flèche du haut ou du bas : pause, et de nouveau pour "
     "reprendre. Touche OK : le QR code de la page de gestion."),
    ("Éteindre et redémarrer", ["shots/admin-complet.png#8-9",
                                 "screens/extinction.png"],
     ["Boutons en bas de la page de gestion", "Débrancher quand la diode verte est éteinte",
      "Mot de passe de la page, si besoin"],
     "En bas de la page de gestion se trouvent les boutons Redémarrer et Éteindre. Avant de "
     "débrancher le cadre, éteignez-le ainsi et attendez que sa diode verte s'éteigne. C'est "
     "aussi là que vous pouvez protéger la page par un mot de passe."),
    ("Mettre à jour le cadre", ["shots/admin-complet.png#6"],
     ["Fichier « .cadre » reçu par message", "« Installer une mise à jour… »",
      "Vérifié avant, contrôlé après", "Problème : ancienne version remise"],
     "Si la personne qui s'occupe du cadre vous envoie un fichier de mise à jour, terminé par "
     "point cadre, ouvrez la page de gestion, section Mise à jour, et touchez Installer une "
     "mise à jour. Le cadre vérifie que le fichier vient bien d'elle, l'installe, puis "
     "contrôle que tout fonctionne. Au moindre problème, il remet l'ancienne version tout "
     "seul. Comptez trois minutes."),
    ("Envoyer un rapport", ["shots/admin-complet.png#7"],
     ["Section « Diagnostic »", "Cocher, choisir la période", "« Télécharger le rapport »",
      "L'envoyer par message"],
     "En cas de problème, la section Diagnostic prépare un rapport pour la personne qui "
     "s'occupe du cadre. Laissez les cases cochées, choisissez la période, puis touchez "
     "Télécharger le rapport, et envoyez-lui le fichier par message. Les mots de passe n'y "
     "figurent pas."),
    ("En cas de souci", ["screens/demarrage.png"],
     ["Ne répond plus : débrancher, rebrancher", "Wi-Fi perdu : il recrée son réseau",
      "Écran noir : vérifier l'entrée HDMI de la télé"],
     "En cas de souci : si le cadre ne répond plus, débranchez-le puis rebranchez-le ; il "
     "redémarre aussi tout seul s'il se bloque. S'il perd le Wi-Fi plus de deux minutes, il "
     "recrée son réseau de configuration. Et si l'écran reste noir, vérifiez que la télé est "
     "sur la bonne entrée HDMI."),
    ("Bon diaporama !", ["screens/photo.png"], [],
     "Voilà, vous savez tout. Bon diaporama !"),
]


def font(name, size):
    return ImageFont.truetype(os.path.join(FONTS, name), size)


def fit(img, box_w, box_h):
    img = img.convert("RGB")
    scale = min(box_w / img.width, box_h / img.height)
    return img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))),
                      Image.LANCZOS)


def framed(img):
    """Visuel posé sur une carte arrondie avec une ombre douce."""
    pad = 10
    card = Image.new("RGBA", (img.width + 2 * pad, img.height + 2 * pad), (0, 0, 0, 0))
    mask = Image.new("L", card.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, *card.size), radius=18, fill=255)
    card.paste((52, 52, 58), mask=mask)
    card.paste(img, (pad, pad))
    shadow = Image.new("RGBA", (card.width + 60, card.height + 60), (0, 0, 0, 0))
    smask = Image.new("L", shadow.size, 0)
    ImageDraw.Draw(smask).rounded_rectangle((30, 40, card.width + 30, card.height + 40),
                                            radius=18, fill=150)
    shadow.paste((0, 0, 0), mask=smask.filter(ImageFilter.GaussianBlur(18)))
    shadow.alpha_composite(card, (30, 30))
    return shadow


def cards(img):
    """Sections (cartes blanches) d'une capture de l'admin : [(haut, bas), ...] de haut en bas."""
    px, spans, top = img.load(), [], None
    for y in range(img.height):
        on_card = px[115, y][0] > 250
        if on_card and top is None:
            top = y
        elif not on_card and top is not None:
            spans.append((top, y))
            top = None
    return spans


def load_visual(base, name):
    """« dossier/fichier.png », « …png#n » (n-ième section de l'admin, à partir de 0) ou
    « …png#n-m » (sections n à m) : pas de coordonnées à refaire quand la page change."""
    name, _, sections = name.partition("#")
    img = Image.open(os.path.join(base, name)).convert("RGB")
    if sections:
        first, _, last = sections.partition("-")
        spans = cards(img)
        top, bottom = spans[int(first)][0], spans[int(last or first)][1]
        img = img.crop((90, top - 8, 1190, bottom + 8))
    d = ImageDraw.Draw(img)
    for (x0, y0, x1, y1), text in MASKS.get(name, []):
        d.rectangle((x0, y0, x1, y1), fill=img.getpixel((x0 + 2, y0 + 2)))
        d.text((x0 + 8, (y0 + y1) // 2), text, font=font("segoeui.ttf", 15),
               fill=(70, 70, 75), anchor="lm")
    return img


def render_slide(base, title, visuals, bullets, path):
    img = Image.new("RGBA", (W, H), BG + (255,))
    d = ImageDraw.Draw(img)
    d.text((90, 70), title, font=font("seguisb.ttf", 64), fill=TEXT)
    d.rectangle((90, 178, 210, 184), fill=ACCENT)
    area_w = 1180 if bullets else W - 180
    area_h = H - 290
    pics = [load_visual(base, v) for v in visuals]
    if len(pics) == 1:
        cards = [framed(fit(pics[0], area_w, area_h))]
    else:  # deux visuels empilés
        cards = [framed(fit(p, area_w, area_h // 2 - 20)) for p in pics]
    total = sum(c.height for c in cards) - 60 * (len(cards) - 1)
    y = 200 + (area_h - total) // 2 - 30
    for c in cards:
        x = 60 + (area_w - c.width) // 2 + 30
        img.alpha_composite(c, (max(0, x), max(170, y)))
        y += c.height - 60
    if bullets:
        f = font("segoeui.ttf", 40)
        y = 300
        for b in bullets:
            d.ellipse((1335, y + 20, 1349, y + 34), fill=ACCENT)
            # Guillemets collés à leur mot (espace insécable : pas de coupure de ligne).
            b = b.replace("« ", "« ").replace(" »", " »")
            words, line, lines = b.split(" "), "", []
            for w_ in words:
                trial = (line + " " + w_).strip()
                if d.textlength(trial, font=f) > 470 and line:
                    lines.append(line)
                    line = w_
                else:
                    line = trial
            lines.append(line)
            for ln in lines:
                d.text((1370, y), ln, font=f, fill=TEXT)
                y += 54
            y += 34
    img.convert("RGB").save(path)


def speak(text, path):
    """Voix neuronale de Microsoft (celle de la lecture à voix haute d'Edge) : MP3."""
    subprocess.run([sys.executable, "-m", "edge_tts", "--voice", VOICE, "--text", text,
                    "--write-media", path], check=True)


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", path], capture_output=True, text=True, check=True)
    return float(out.stdout)


def main(base):
    work = os.path.join(base, "slides")
    os.makedirs(work, exist_ok=True)
    segments = []
    for i, (title, visuals, bullets, narration) in enumerate(SLIDES, 1):
        png, voice, mp4 = (os.path.abspath(os.path.join(work, f"{i:02d}.{e}"))
                         for e in ("png", "mp3", "mp4"))
        render_slide(base, title, visuals, bullets, png)
        speak(narration, voice)
        dur = duration(voice) + PAUSE
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", png, "-i", voice,
            "-vf", f"fade=t=in:st=0:d=0.4,fade=t=out:st={dur - 0.4:.2f}:d=0.4,format=yuv420p",
            "-af", f"apad=whole_dur={dur:.2f}", "-t", f"{dur:.2f}", "-r", "25",
            "-c:v", "libx264", "-tune", "stillimage", "-c:a", "aac", "-ar", "48000", mp4],
            check=True)
        segments.append(mp4)
        print(f"{i:02d} {title} : {dur:.1f} s")
    listing = os.path.join(work, "liste.txt")
    with open(listing, "w", encoding="utf-8") as f:
        f.writelines(f"file '{s}'\n" for s in segments)
    out = os.path.abspath(os.path.join(base, "cadre-photo-mode-d-emploi.mp4"))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                    "-i", listing, "-c", "copy", "-movflags", "+faststart", out], check=True)
    print("vidéo :", out)


if __name__ == "__main__":
    main(sys.argv[1])
